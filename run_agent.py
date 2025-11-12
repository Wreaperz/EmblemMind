#!/usr/bin/env python3

"""Main tactical agent entry point.

This version of ``run_agent`` replaces the previous reinforcement-learning loop with
an OpenAI-powered tactical policy.  Each iteration of the loop collects the current
game snapshot, serialises it into JSON, sends it to the model, parses the returned
plan, and then executes the requested actions inside BizHawk.

The script is intentionally modular:

``SnapshotSerialiser``
    Converts ``TurnSnapshot`` instances into JSON friendly payloads that the model
    can reason about.

``OpenAITacticalPolicy``
    Handles prompt construction and interaction with the OpenAI Responses API.  The
    policy prompt is deterministic and enforces a strict JSON schema.  A "dry run"
    fallback is available when no API key is present so local development does not
    require network calls.

``ActionPlanParser``
    Parses the JSON reply into structured ``ActionInstruction`` objects.

``ActionPlanExecutor``
    Matches the instructions against legal in-game actions and issues controller
    inputs through BizHawk.

All behaviour (focus handling, cursor control, animation waiting, etc.) is retained
from the original agent but reorganised into re-usable helpers so the execution
pipeline cleanly mirrors ``snapshot -> policy -> plan -> execution``.
"""

from __future__ import annotations

import json
import logging
import os
import time
from textwrap import shorten
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import openai
except ImportError:  # pragma: no cover - handled at runtime
    openai = None

from emblemmind_snapshot import TurnSnapshot, Unit
from agent.action_generator import Action, ActionGenerator
from agent.bizhawk_controller import GBA_KEY_MAP, focus_bizhawk, press_key
from data_gatherer import DataGatherer
from utils.fe_data_mappings import get_item_name


# ---------------------------------------------------------------------------
# Files and constants

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
STATE_FILE = os.path.join(DATA_DIR, "fe_state.txt")
MAP_FILE = os.path.join(DATA_DIR, "fe_map.txt")

# Prompts used for the tactical policy. Both strings intentionally begin with
# the phrasing requested by the user so the model always receives the same
# prefix.  ``PLANNING_PROMPT`` steers the LLM to request attack previews, while
# ``EXECUTION_PROMPT`` consumes those previews to produce final actions.
PLANNING_PROMPT = (
    "You are a deterministic Fire Emblem 7 tactical policy. You never explain. "
    "You output JSON only that conforms exactly to the Output Schema. Choose a "
    "single legal action per allied unit and an execution order that maximizes "
    "survival of lords, progress toward objectives, and net advantage.\n\n"
    "Preview Phase Instructions:\n"
    "- Review the snapshot, full terrain map, and each ally's movement grid.\n"
    "- Movement grids use characters (0 = unit tile, + = reachable, X = blocked).\n"
    "- Request battle previews only when they meaningfully inform risk/reward; "
    "skip obvious or impossible attacks.\n"
    "- Prefer preparations that protect lords, advance objectives, and preserve "
    "resources.\n\n"
    "Output Schema:\n"
    "[\n"
    "  {\n"
    "    \"order\": <integer starting at 1>,\n"
    "    \"unit_id\": <integer>,\n"
    "    \"preview\": {\n"
    "      \"type\": \"attack\",\n"
    "      \"from\": {\"x\": <int>, \"y\": <int>},\n"
    "      \"target_unit_id\": <int>,\n"
    "      \"weapon_id\": <int>,\n"
    "      \"target_hint\": {\"x\": <int>, \"y\": <int>} (optional when "
    "enemy tiles differ from movement tile)\n"
    "    }\n"
    "  }, ...\n"
    "]"
)

EXECUTION_PROMPT = (
    "You are a deterministic Fire Emblem 7 tactical policy. You never explain. "
    "You output JSON only that conforms exactly to the Output Schema. Choose a "
    "single legal action per allied unit and an execution order that maximizes "
    "survival of lords, progress toward objectives, and net advantage.\n\n"
    "Execution Phase Instructions:\n"
    "- Use the latest snapshot, movement grids, and battle previews to decide "
    "the actual actions to take.\n"
    "- Battle previews include attacker/defender IDs, positions, HP before the "
    "attack, hit rate (byte 111), and attack speed (byte 107).\n"
    "- Round chunks show expected damage (last byte) for each combat exchange; "
    "treat chunks where attackers miss as zero damage.\n"
    "- Choose moves that remain legal with the provided movement grids and "
    "favour survival, objective progress, and net advantage.\n"
    "- If no meaningful action exists, return an empty array.\n\n"
    "Output Schema:\n"
    "[\n"
    "  {\n"
    "    \"unit_id\": <integer>,\n"
    "    \"order\": <integer execution order starting at 1>,\n"
    "    \"action\": {\n"
    "      \"type\": \"move|attack|item|rescue|wait|end_turn\",\n"
    "      \"target\": {\"x\": <int>, \"y\": <int>} (optional),\n"
    "      \"target_unit_id\": <int> (optional),\n"
    "      \"item_id\": <int> (optional)\n"
    "    }\n"
    "  }, ...\n"
    "]"
)

# Polling interval while waiting for the next actionable snapshot (seconds).
SNAPSHOT_POLL_INTERVAL = float(os.getenv("TACTICAL_AGENT_POLL", "0.5"))

# Maximum time allowed for an OpenAI response.
OPENAI_TIMEOUT = int(os.getenv("TACTICAL_AGENT_OPENAI_TIMEOUT", "60"))


# ---------------------------------------------------------------------------
# Serialisation helpers


class SnapshotSerialiser:
    """Convert ``TurnSnapshot`` instances into model-friendly payloads."""

    def serialise(
        self,
        snapshot: TurnSnapshot,
        *,
        map_grid: Optional[List[str]] = None,
        movement_maps: Optional[Dict[int, Any]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "turn": snapshot.current_turn,
            "chapter_id": snapshot.chapter_id,
            "phase": snapshot.phase_text,
            "cursor": self._coord_dict(snapshot.cursor_position),
            "map": {
                "width": snapshot.map.width,
                "height": snapshot.map.height,
            },
            "allies": [self._unit_dict(unit, movement_maps) for unit in snapshot.units],
            "enemies": [self._unit_dict(unit, movement_maps) for unit in snapshot.enemies],
        }
        if map_grid is not None:
            payload["map"]["grid"] = map_grid
        return payload

    @staticmethod
    def _coord_dict(coord: Optional[Tuple[int, int]]) -> Optional[Dict[str, int]]:
        if coord is None:
            return None
        x, y = coord
        return {"x": x, "y": y}

    @staticmethod
    def _unit_dict(
        unit: Unit, movement_maps: Optional[Dict[int, Any]]
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "id": unit.id,
            "name": unit.name,
            "class_id": unit.class_id,
            "class_name": unit.class_name,
            "position": {"x": unit.position[0], "y": unit.position[1]},
            "hp": {"current": unit.hp[0], "max": unit.hp[1]},
            "can_act": unit.can_act,
            "has_acted": unit.has_acted,
            "status_effect": unit.status_effect,
            "turn_status": unit.turn_status,
            "movement": unit.movement_range,
            "is_enemy": unit.is_enemy,
            "items": [
                {
                    "id": item_id,
                    "uses": uses,
                    "name": get_item_name(item_id),
                }
                for item_id, uses in unit.items
            ],
        }
        if unit.is_enemy:
            data["drops_item"] = unit.drops_item
        elif movement_maps and unit.id in movement_maps:
            data["movement_grid"] = movement_maps[unit.id]
        return data


# ---------------------------------------------------------------------------
# OpenAI policy interface


class OpenAITacticalPolicy:
    """Wrapper around the OpenAI API for tactical decision making."""

    def __init__(
        self,
        model: str = None,
        temperature: float = 0.0,
        dry_run: Optional[bool] = None,
    ) -> None:
        self.model = model or os.getenv("TACTICAL_AGENT_MODEL", "gpt-4o-mini")
        self.temperature = temperature

        api_key = os.getenv("OPENAI_API_KEY")
        if dry_run is None:
            dry_run = not api_key

        self.dry_run = dry_run
        self._client = None

        if self.dry_run:
            logging.warning(
                "OpenAI API key not configured; running in dry-run mode that emits"
                " placeholder plans."
            )
        else:
            if openai is None:
                raise RuntimeError(
                    "The 'openai' package is required for tactical policy calls."
                )
            client_cls = getattr(openai, "OpenAI", None)
            if client_cls is not None:
                self._client = client_cls(api_key=api_key)
            else:  # pragma: no cover - depends on installed SDK version
                openai.api_key = api_key

    # Public API -----------------------------------------------------------------

    def request_preview_plan(self, payload: List[Dict[str, Any]]) -> str:
        """Submit planning payload and receive preview instructions."""

        if self.dry_run:
            return self._fallback_preview_plan()

        return self._invoke_model(PLANNING_PROMPT, payload)

    def request_final_plan(self, payload: List[Dict[str, Any]]) -> str:
        """Submit execution payload and receive the final action plan."""

        if self.dry_run:
            return self._fallback_execution_plan()

        return self._invoke_model(EXECUTION_PROMPT, payload)

    # Internals -------------------------------------------------------------------

    def _invoke_model(self, system_prompt: str, payload: List[Dict[str, Any]]) -> str:
        payload_text = json.dumps(payload, indent=2, sort_keys=True)
        logging.info(
            "OpenAI tactical policy request payload:%s%s", os.linesep, payload_text
        )
        logging.debug(
            "Serialised payload (truncated): %s",
            shorten(payload_text, width=2000, placeholder="..."),
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": payload_text},
        ]

        if self._client is not None:
            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    timeout=OPENAI_TIMEOUT,
                )
                choice = response.choices[0]
                message = getattr(choice, "message", None)
                if isinstance(message, dict):
                    content = message.get("content", "")
                else:
                    content = getattr(message, "content", "")
            except AttributeError:  # pragma: no cover - SDK differences
                response = self._client.responses.create(
                    model=self.model,
                    input=messages,
                    temperature=self.temperature,
                )
                content = getattr(response, "output_text", "[]")
            except Exception as exc:  # pragma: no cover - API behaviour
                logging.error("OpenAI policy request failed: %s", exc, exc_info=True)
                raise

            logging.info(
                "OpenAI tactical policy raw response:%s%s", os.linesep, content
            )
            logging.debug(
                "Received OpenAI response (truncated): %s",
                shorten(content, width=2000, placeholder="..."),
            )
            return content

        # Legacy SDK path (openai.ChatCompletion)
        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                timeout=OPENAI_TIMEOUT,
            )
        except Exception as exc:  # pragma: no cover - API behaviour
            logging.error(
                "OpenAI policy request failed via legacy SDK: %s", exc, exc_info=True
            )
            raise

        content = response["choices"][0]["message"]["content"]
        logging.info("OpenAI tactical policy raw response:%s%s", os.linesep, content)
        logging.debug(
            "Received ChatCompletion response (truncated): %s",
            shorten(content, width=2000, placeholder="..."),
        )
        return content

    def _fallback_preview_plan(self) -> str:
        """Return an empty preview plan when the API is unavailable."""

        plan = "[]"
        logging.info(
            "Dry-run tactical policy returning placeholder preview plan:%s%s",
            os.linesep,
            plan,
        )
        return plan

    def _fallback_execution_plan(self) -> str:
        """Return a deterministic execution plan for testing without the API."""

        plan = "[]"
        logging.info(
            "Dry-run tactical policy returning placeholder execution plan:%s%s",
            os.linesep,
            plan,
        )
        return plan


# ---------------------------------------------------------------------------
# Plan parsing


@dataclass
class ActionInstruction:
    """Structured representation of a single action from the policy."""

    order: int
    unit_id: int
    action_type: str
    target: Optional[Tuple[int, int]] = None
    target_unit_id: Optional[int] = None
    item_id: Optional[int] = None
    raw: Dict[str, Any] = None


class ActionPlanParser:
    """Parse and validate a JSON plan returned by the OpenAI policy."""

    def parse(self, content: str) -> List[ActionInstruction]:
        if not content.strip():
            logging.error("Policy response was empty; cannot parse instructions")
            return []

        normalised = self._extract_json_payload(content)
        if normalised is None:
            logging.error("Unable to locate JSON array in policy response")
            logging.debug(
                "Unparseable policy response (truncated): %s",
                shorten(content, width=2000, placeholder="..."),
            )
            return []

        if normalised != content.strip():
            logging.info("Normalised policy response by extracting JSON payload")

        try:
            data = json.loads(normalised)
        except json.JSONDecodeError as exc:
            logging.error("Failed to decode policy response: %s", exc)
            logging.debug(
                "Raw policy response that failed to decode (truncated): %s",
                shorten(content, width=2000, placeholder="..."),
            )
            return []

        if not isinstance(data, list):
            logging.error("Policy response must be a JSON array; received %s", type(data))
            logging.debug(
                "Unexpected policy response structure (truncated): %s",
                shorten(content, width=2000, placeholder="..."),
            )
            return []

        instructions: List[ActionInstruction] = []
        for idx, entry in enumerate(data):
            if not isinstance(entry, dict):
                logging.warning("Skipping malformed plan entry at index %s: %r", idx, entry)
                continue

            unit_id = entry.get("unit_id")
            action_block = entry.get("action", {})
            action_type = None
            target: Optional[Tuple[int, int]] = None
            target_unit_id: Optional[int] = None
            item_id: Optional[int] = None

            if isinstance(action_block, dict):
                action_type = action_block.get("type")
                target_dict = action_block.get("target")
                if isinstance(target_dict, dict) and {"x", "y"} <= set(target_dict):
                    try:
                        target = (int(target_dict["x"]), int(target_dict["y"]))
                    except (TypeError, ValueError):
                        target = None
                if "target_unit_id" in action_block:
                    try:
                        target_unit_id = int(action_block["target_unit_id"])
                    except (TypeError, ValueError):
                        target_unit_id = None
                if "item_id" in action_block:
                    try:
                        item_id = int(action_block["item_id"])
                    except (TypeError, ValueError):
                        item_id = None
            elif isinstance(entry.get("action_type"), str):
                action_type = entry.get("action_type")
                target = self._parse_target(entry)
                target_unit_id = entry.get("target_unit_id")
                item_id = entry.get("item_id")

            if unit_id is None:
                logging.warning("Plan entry missing unit_id: %r", entry)
                continue
            if not action_type:
                logging.warning("Plan entry missing action type: %r", entry)
                continue

            order = entry.get("order", idx + 1)
            try:
                instruction = ActionInstruction(
                    order=int(order),
                    unit_id=int(unit_id),
                    action_type=str(action_type).lower(),
                    target=target,
                    target_unit_id=int(target_unit_id) if target_unit_id is not None else None,
                    item_id=int(item_id) if item_id is not None else None,
                    raw=entry,
                )
            except (TypeError, ValueError):
                logging.warning("Failed to normalise plan entry: %r", entry)
                continue

            instructions.append(instruction)

        instructions.sort(key=lambda inst: inst.order)
        return instructions

    @staticmethod
    def _parse_target(entry: Dict[str, Any]) -> Optional[Tuple[int, int]]:
        target = entry.get("target")
        if isinstance(target, dict) and {"x", "y"} <= set(target):
            try:
                return int(target["x"]), int(target["y"])
            except (TypeError, ValueError):
                return None
        return None

    @staticmethod
    def _extract_json_payload(content: str) -> Optional[str]:
        """Attempt to isolate a JSON array from *content*."""

        stripped = content.strip()
        if stripped.startswith("["):
            return stripped

        if stripped.startswith("```"):
            blocks = stripped.split("```")
            for block in blocks:
                candidate = block.strip()
                if not candidate:
                    continue
                if candidate.lower().startswith("json"):
                    candidate = candidate[4:].strip()
                if candidate.startswith("["):
                    return candidate

        start = stripped.find("[")
        if start == -1:
            return None

        depth = 0
        in_string = False
        escaped = False
        for idx in range(start, len(stripped)):
            ch = stripped[idx]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue

            if ch == '"':
                in_string = True
                continue
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    return stripped[start : idx + 1]

        return None


# ---------------------------------------------------------------------------
# Preview parsing helpers


@dataclass
class PreviewInstruction:
    order: int
    unit_id: int
    from_tile: Tuple[int, int]
    target_unit_id: int
    weapon_id: int
    target_tile: Optional[Tuple[int, int]] = None
    raw: Dict[str, Any] = None


class PreviewPlanParser:
    """Parse planning phase output into structured preview requests."""

    def parse(self, content: str) -> List[PreviewInstruction]:
        if not content.strip():
            return []

        json_payload = ActionPlanParser._extract_json_payload(content)
        if json_payload is None:
            logging.error("Unable to extract preview JSON payload")
            logging.debug(
                "Preview response (truncated) without JSON: %s",
                shorten(content, width=2000, placeholder="..."),
            )
            return []

        try:
            data = json.loads(json_payload)
        except json.JSONDecodeError as exc:
            logging.error("Failed to decode preview plan: %s", exc)
            logging.debug(
                "Preview response (truncated) that failed to decode: %s",
                shorten(content, width=2000, placeholder="..."),
            )
            return []

        if not isinstance(data, list):
            logging.error("Preview plan must be a JSON array; received %s", type(data))
            return []

        instructions: List[PreviewInstruction] = []
        for idx, entry in enumerate(data):
            if not isinstance(entry, dict):
                continue

            preview = entry.get("preview")
            if not isinstance(preview, dict):
                continue

            from_tile = preview.get("from") or preview.get("attack_from")
            target_hint = preview.get("target_hint")
            try:
                from_coords = (
                    int(from_tile["x"]),
                    int(from_tile["y"]),
                )
            except (TypeError, ValueError, KeyError):
                logging.debug("Preview entry missing origin tile: %r", entry)
                continue

            try:
                target_unit_id = int(preview.get("target_unit_id"))
                weapon_id = int(preview.get("weapon_id"))
            except (TypeError, ValueError):
                logging.debug("Preview entry missing identifiers: %r", entry)
                continue

            target_tile = None
            if isinstance(target_hint, dict):
                try:
                    target_tile = (
                        int(target_hint["x"]),
                        int(target_hint["y"]),
                    )
                except (TypeError, ValueError, KeyError):
                    target_tile = None

            try:
                instruction = PreviewInstruction(
                    order=int(entry.get("order", idx + 1)),
                    unit_id=int(entry.get("unit_id")),
                    from_tile=from_coords,
                    target_unit_id=target_unit_id,
                    weapon_id=weapon_id,
                    target_tile=target_tile,
                    raw=entry,
                )
            except (TypeError, ValueError):
                logging.debug("Skipping malformed preview entry: %r", entry)
                continue

            instructions.append(instruction)

        instructions.sort(key=lambda item: item.order)
        return instructions


# ---------------------------------------------------------------------------
# Snapshot augmentation helpers


@dataclass
class BattlePreview:
    order: int
    unit_id: int
    target_unit_id: int
    weapon_id: int
    from_tile: Tuple[int, int]
    target_tile: Tuple[int, int]
    attacker: Dict[str, Any]
    defender: Dict[str, Any]
    rounds: List[Dict[str, Any]]


def read_map_grid() -> List[str]:
    grid: List[str] = []
    try:
        with open(MAP_FILE, "r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    if grid:
                        break
                    continue
                if ":" in stripped and not stripped.startswith((".", "H", "^", "#", "F", "C", "T", "D", "R", "=", "~", "M", "X")):
                    if grid:
                        break
                    continue
                tokens = stripped.split()
                if tokens:
                    grid.append("".join(tokens))
    except FileNotFoundError:
        logging.error("Map file %s not found", MAP_FILE)
    except Exception as exc:
        logging.error("Failed to read map grid: %s", exc)
    return grid


def summarise_movement_grid(grid: List[List[int]]) -> List[str]:
    """Compress movement grids into reachability masks for the model."""

    summary: List[str] = []
    for row in grid:
        chars: List[str] = []
        for value in row:
            if value == 0:
                chars.append("0")
            elif value >= 0xFF:
                chars.append("X")
            elif value > 0:
                chars.append("+")
            else:
                chars.append("X")
        summary.append("".join(chars))
    return summary


def _parse_hex_stream(text: str) -> List[int]:
    return [int(token, 16) for token in text.split() if token]


def read_battle_snapshot() -> Optional[Dict[str, Any]]:
    attacker: Optional[List[int]] = None
    defender: Optional[List[int]] = None
    rounds: List[List[int]] = []

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as handle:
            state = "search"
            for raw_line in handle:
                line = raw_line.strip()
                if state == "search":
                    if line == "BATTLE_STRUCTS":
                        state = "battle"
                    continue

                if not line:
                    break

                if line.replace("_", "").isupper() and not line.startswith("7-"):
                    break

                if line == "ROUNDS_DATA":
                    state = "rounds"
                    continue

                if state == "battle":
                    if line.startswith("attacker_battle="):
                        attacker = _parse_hex_stream(line.split("=", 1)[1])
                    elif line.startswith("defender_battle="):
                        defender = _parse_hex_stream(line.split("=", 1)[1])
                elif state == "rounds":
                    if line.startswith("7-round_data="):
                        rounds.append(_parse_hex_stream(line.split("=", 1)[1]))
                    else:
                        break
    except FileNotFoundError:
        logging.error("State file %s not found", STATE_FILE)
        return None
    except Exception as exc:
        logging.error("Failed to read battle snapshot: %s", exc)
        return None

    if not attacker or not defender:
        return None

    return {"attacker": attacker, "defender": defender, "rounds": rounds}


def _le16(values: List[int], offset: int) -> Optional[int]:
    if offset + 1 >= len(values):
        return None
    return values[offset] | (values[offset + 1] << 8)


def summarise_battle_struct(values: List[int]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "raw_hex": " ".join(f"{byte:02X}" for byte in values),
    }
    if not values:
        return summary

    unit_id = _le16(values, 0)
    if unit_id is not None:
        summary["unit_id"] = unit_id

    class_id = _le16(values, 4)
    if class_id is not None:
        summary["class_id"] = class_id

    if len(values) > 17:
        summary["position"] = {"x": values[16], "y": values[17]}
    if len(values) > 19:
        summary["hp"] = {"max": values[18], "current": values[19]}
    if len(values) > 106:
        summary["attack_speed"] = values[106]
    if len(values) > 110:
        summary["hit_rate"] = values[110]

    return summary


def summarise_rounds(round_rows: List[List[int]]) -> List[Dict[str, Any]]:
    rounds: List[Dict[str, Any]] = []
    for idx, row in enumerate(round_rows):
        entry = {
            "index": idx + 1,
            "raw_hex": " ".join(f"{value:02X}" for value in row),
            "chunks": [],
        }
        for offset in range(0, len(row), 4):
            chunk = row[offset : offset + 4]
            if len(chunk) < 4:
                continue
            entry["chunks"].append(
                {
                    "bytes": [int(value) for value in chunk],
                    "expected_damage": chunk[-1],
                }
            )
        rounds.append(entry)
    return rounds


# ---------------------------------------------------------------------------
# BizHawk interaction utilities (derived from the original run_agent)


def read_snapshot() -> Optional[TurnSnapshot]:
    try:
        return TurnSnapshot.from_files(STATE_FILE, MAP_FILE)
    except Exception as exc:  # pragma: no cover - runtime feedback only
        logging.error("Unable to read snapshot: %s", exc)
        return None


def wait_for_action_followthrough(
    prev_snapshot: TurnSnapshot,
    check_fn,
    timeout: float = 1.0,
) -> TurnSnapshot:
    """Poll the state file until ``check_fn`` returns True or timeout expires."""

    start = time.time()
    latest = prev_snapshot
    while time.time() - start < timeout:
        snapshot = read_snapshot()
        if snapshot is None:
            time.sleep(0.1)
            continue
        latest = snapshot
        try:
            if check_fn(snapshot):
                return snapshot
        except Exception:
            pass
        time.sleep(0.05)
    return latest


def wait_for_animation_complete(
    prev_snapshot: TurnSnapshot,
    timeout: float = 5.0,
    stable_checks: int = 5,
) -> TurnSnapshot:
    """Wait for animations by checking for stable unit positions."""

    last_positions: List[List[Tuple[int, Tuple[int, int]]]] = []
    start = time.time()
    snapshot = prev_snapshot
    while time.time() - start < timeout:
        snapshot = read_snapshot()
        if snapshot is None:
            time.sleep(0.2)
            continue
        positions = [(u.id, u.position) for u in snapshot.units]
        last_positions.append(positions)
        if len(last_positions) > stable_checks:
            last_positions.pop(0)
            if all(p == last_positions[0] for p in last_positions):
                return snapshot
        time.sleep(0.3)
    return snapshot


def wait_for_battle_data(timeout: float = 3.0, poll: float = 0.1) -> Optional[Dict[str, Any]]:
    """Poll the state file until battle structs are populated or timeout."""

    start = time.time()
    while time.time() - start < timeout:
        battle = read_battle_snapshot()
        if battle:
            return battle
        time.sleep(poll)
    return None


def get_cursor_position() -> Optional[Tuple[int, int]]:
    for _ in range(3):
        snapshot = read_snapshot()
        if snapshot and snapshot.cursor_position is not None:
            return snapshot.cursor_position
        time.sleep(0.1)
    return None


def move_cursor_to(
    target_pos: Tuple[int, int],
    current_pos: Optional[Tuple[int, int]],
    max_attempts: int = 3,
    *,
    verify: bool = True,
    step_delay: float = 0.05,
) -> Tuple[int, int]:
    if current_pos is None:
        current_pos = target_pos
    logging.debug("Moving cursor from %s to %s", current_pos, target_pos)

    for attempt in range(max_attempts):
        dx = target_pos[0] - current_pos[0]
        dy = target_pos[1] - current_pos[1]

        for _ in range(abs(dx)):
            press_key(
                GBA_KEY_MAP["RIGHT"] if dx > 0 else GBA_KEY_MAP["LEFT"],
                duration=0.05,
            )
            time.sleep(step_delay)

        for _ in range(abs(dy)):
            press_key(
                GBA_KEY_MAP["DOWN"] if dy > 0 else GBA_KEY_MAP["UP"],
                duration=0.05,
            )
            time.sleep(step_delay)

        if not verify:
            time.sleep(0.2)
            return target_pos

        time.sleep(0.2)
        pos = get_cursor_position()
        if pos == target_pos:
            return target_pos

        logging.warning(
            "Cursor failed to reach %s on attempt %s; retrying after returning to map",
            target_pos,
            attempt + 1,
        )
        return_to_map()
        current_pos = get_cursor_position() or current_pos

    logging.error("Could not position cursor at %s", target_pos)
    return current_pos


def return_to_map() -> None:
    for _ in range(5):
        press_key("z", duration=0.01)  # B button
        time.sleep(0.05)


def is_menu_open() -> bool:
    before = get_cursor_position()
    if before is None:
        return False
    press_key(GBA_KEY_MAP["RIGHT"], duration=0.01)
    time.sleep(0.05)
    after = get_cursor_position()
    if after is not None and after != before:
        # Restore cursor
        press_key(GBA_KEY_MAP["LEFT"], duration=0.01)
    return before == after


def perform_attack_action(action: Action, cursor_pos: Optional[Tuple[int, int]]) -> Tuple[int, int]:
    if action.target_unit is None:
        logging.error("Attack action missing target unit: %s", action)
        return cursor_pos or action.unit.position

    cursor_pos = move_cursor_to(action.unit.position, cursor_pos)
    press_key("x", duration=0.05)
    time.sleep(0.1)

    if action.target_position != action.unit.position:
        cursor_pos = move_cursor_to(
            action.target_position, cursor_pos, verify=False
        )
        time.sleep(0.2)
        press_key("x", duration=0.05)
        time.sleep(0.1)

    # Select weapon if needed
    if action.item_id is not None:
        time.sleep(0.1)
        press_key("x", duration=0.05)
        time.sleep(0.1)

    enemy_pos = action.target_unit.position
    cursor_pos = move_cursor_to(enemy_pos, cursor_pos, verify=False)
    time.sleep(0.2)
    press_key("x", duration=0.05)
    time.sleep(0.2)

    return cursor_pos


def execute_action_in_bizhawk(
    action: Action,
    cursor_pos: Optional[Tuple[int, int]],
    prev_snapshot: TurnSnapshot,
) -> Tuple[Tuple[int, int], TurnSnapshot]:
    logging.info(
        "Executing %s action for unit %s", action.action_type, action.unit.name
    )

    if action.action_type == "attack":
        cursor_pos = perform_attack_action(action, cursor_pos)
    else:
        cursor_pos = move_cursor_to(action.unit.position, cursor_pos)
        pos_check = get_cursor_position()
        if pos_check != action.unit.position:
            logging.error(
                "Cursor mismatch when selecting unit %s: expected %s got %s",
                action.unit.name,
                action.unit.position,
                pos_check,
            )
            return cursor_pos, prev_snapshot

        press_key("x", duration=0.05)
        time.sleep(0.1)

        target_position = action.target_position or action.unit.position
        cursor_pos = move_cursor_to(target_position, cursor_pos, verify=False)
        time.sleep(0.2)
        press_key("x", duration=0.05)
        time.sleep(0.2)

        # Default to wait at the end of movement
        time.sleep(0.2)
        press_key("UP", duration=0.05)
        time.sleep(0.05)
        press_key("x", duration=0.05)

    def action_completed(snapshot: TurnSnapshot) -> bool:
        unit_after = next((u for u in snapshot.units if u.id == action.unit.id), None)
        return bool(unit_after and (not unit_after.can_act or unit_after.position != action.unit.position))

    snapshot = wait_for_action_followthrough(prev_snapshot, action_completed)
    snapshot = wait_for_animation_complete(snapshot, timeout=2.0, stable_checks=5)

    if is_menu_open():
        logging.debug("Menu detected after action; returning to map")
        return_to_map()
        cursor_pos = get_cursor_position() or cursor_pos

    cursor_pos = get_cursor_position() or cursor_pos or action.target_position
    return cursor_pos, snapshot


def end_turn_in_bizhawk(
    cursor_pos: Optional[Tuple[int, int]],
    snapshot: TurnSnapshot,
) -> Tuple[Tuple[int, int], TurnSnapshot]:
    moved_unit = next((u for u in snapshot.units if u.turn_status == 0x02), None)
    if not moved_unit:
        logging.warning("No moved unit available to end turn on; skipping end turn")
        return cursor_pos or (0, 0), snapshot

    cursor_pos = move_cursor_to(moved_unit.position, cursor_pos)
    press_key("x", duration=0.05)
    time.sleep(0.1)
    press_key("UP", duration=0.05)
    time.sleep(0.1)
    press_key("x", duration=0.05)
    time.sleep(0.5)

    snapshot = wait_for_animation_complete(snapshot, timeout=3.0, stable_checks=5)
    cursor_pos = get_cursor_position() or cursor_pos or moved_unit.position
    return cursor_pos, snapshot


# ---------------------------------------------------------------------------
# Plan execution


class ActionPlanExecutor:
    """Match plan instructions to legal actions and execute them."""

    def __init__(self) -> None:
        self.cursor_pos: Optional[Tuple[int, int]] = None

    def execute_plan(
        self,
        snapshot: TurnSnapshot,
        instructions: Iterable[ActionInstruction],
    ) -> TurnSnapshot:
        current_snapshot = snapshot

        for instruction in instructions:
            if instruction.action_type == "end_turn":
                self.cursor_pos, current_snapshot = end_turn_in_bizhawk(
                    self.cursor_pos, current_snapshot
                )
                continue

            action = self._instruction_to_action(current_snapshot, instruction)
            if action is None:
                logging.warning("Unable to map instruction to action: %s", instruction)
                continue

            self.cursor_pos, current_snapshot = execute_action_in_bizhawk(
                action, self.cursor_pos, current_snapshot
            )

        return current_snapshot

    # Internals -----------------------------------------------------------------

    def _instruction_to_action(
        self, snapshot: TurnSnapshot, instruction: ActionInstruction
    ) -> Optional[Action]:
        unit = next((u for u in snapshot.units if u.id == instruction.unit_id), None)
        if unit is None:
            logging.warning("Unit %s not present in snapshot", instruction.unit_id)
            return None

        if instruction.action_type == "wait":
            return Action(unit=unit, action_type="wait", target_position=unit.position)

        actions = ActionGenerator(snapshot).generate_all_actions()
        for action in actions:
            if action.unit.id != unit.id:
                continue
            if action.action_type != instruction.action_type:
                continue
            if instruction.target and action.target_position != instruction.target:
                continue
            if (
                instruction.target_unit_id is not None
                and action.target_unit
                and action.target_unit.id != instruction.target_unit_id
            ):
                continue
            if instruction.item_id is not None and action.item_id != instruction.item_id:
                continue
            return action

        # If we reach this point and the instruction is a move with a target tile,
        # fabricate an action so the executor still attempts the manoeuvre.
        if instruction.action_type == "move" and instruction.target:
            return Action(unit=unit, action_type="move", target_position=instruction.target)

        logging.debug(
            "No matching legal action found for %s (unit %s)",
            instruction.action_type,
            unit.name,
        )
        return None


# ---------------------------------------------------------------------------
# Tactical agent orchestrator


class TacticalAgent:
    """Main orchestrator that drives the tactical loop."""

    def __init__(self) -> None:
        self.policy = OpenAITacticalPolicy()
        self.parser = ActionPlanParser()
        self.preview_parser = PreviewPlanParser()
        self.executor = ActionPlanExecutor()
        self.data_gatherer = DataGatherer()
        self.serialiser = SnapshotSerialiser()
        self.map_grid = read_map_grid()
        self.last_signature: Optional[Tuple[int, Tuple[Tuple[int, int], ...]]] = None

    def run(self) -> None:
        focus_bizhawk()
        logging.info("Starting tactical agent loop")

        try:
            while True:
                snapshot = self.data_gatherer.get_snapshot()
                if snapshot is None:
                    time.sleep(SNAPSHOT_POLL_INTERVAL)
                    continue

                if snapshot.turn_phase != 0x00:
                    time.sleep(SNAPSHOT_POLL_INTERVAL)
                    continue

                if not self.map_grid:
                    self.map_grid = read_map_grid()

                logging.debug(
                    "Snapshot ready: turn=%s phase_text=%s allies=%d enemies=%d",
                    snapshot.current_turn,
                    snapshot.phase_text,
                    len(snapshot.units),
                    len(snapshot.enemies),
                )

                signature = self._snapshot_signature(snapshot)
                if signature == self.last_signature:
                    time.sleep(SNAPSHOT_POLL_INTERVAL)
                    continue

                self.last_signature = signature

                movement_maps = self._collect_movement_maps(snapshot)
                planning_payload = self._build_planning_payload(snapshot, movement_maps)
                preview_text = self.policy.request_preview_plan(planning_payload)
                logging.debug(
                    "Preview planner returned (truncated): %s",
                    shorten(preview_text, width=2000, placeholder="..."),
                )
                preview_instructions = self.preview_parser.parse(preview_text)
                if preview_instructions:
                    logging.debug(
                        "Received %d preview requests", len(preview_instructions)
                    )

                battle_previews = []
                if preview_instructions:
                    battle_previews = self._collect_battle_previews(
                        snapshot, preview_instructions
                    )

                # Refresh snapshot after previews in case positions updated
                snapshot = self.data_gatherer.get_snapshot() or snapshot

                execution_payload = self._build_execution_payload(
                    snapshot,
                    movement_maps,
                    preview_instructions,
                    battle_previews,
                )
                plan_text = self.policy.request_final_plan(execution_payload)
                logging.debug(
                    "Execution policy returned (truncated): %s",
                    shorten(plan_text, width=2000, placeholder="..."),
                )
                instructions = self.parser.parse(plan_text)
                if instructions:
                    summary = [
                        f"{inst.order}:{inst.unit_id}:{inst.action_type}"
                        for inst in instructions
                    ]
                    logging.debug(
                        "Parsed %d instructions (order:unit:action): %s",
                        len(instructions),
                        ", ".join(summary),
                    )

                if not instructions:
                    logging.warning("No actionable instructions returned; waiting")
                    time.sleep(SNAPSHOT_POLL_INTERVAL)
                    continue

                self.executor.cursor_pos = get_cursor_position()
                snapshot = self.executor.execute_plan(snapshot, instructions)
                self.last_signature = self._snapshot_signature(snapshot)

        except KeyboardInterrupt:  # pragma: no cover - user driven
            logging.info("Tactical agent interrupted; shutting down")
        finally:
            self.data_gatherer.stop()

    @staticmethod
    def _snapshot_signature(snapshot: TurnSnapshot) -> Tuple[int, Tuple[Tuple[int, int], ...]]:
        statuses = tuple(sorted((unit.id, unit.turn_status) for unit in snapshot.units))
        return snapshot.current_turn, statuses

    # Helpers --------------------------------------------------------------------

    def _collect_movement_maps(self, snapshot: TurnSnapshot) -> Dict[int, List[str]]:
        movement_maps: Dict[int, List[str]] = {}
        cursor_pos = get_cursor_position() or snapshot.cursor_position
        for unit in snapshot.units:
            if unit.hp[0] <= 0:
                continue

            cursor_pos = move_cursor_to(unit.position, cursor_pos)
            press_key("x", duration=0.05)
            time.sleep(0.2)

            grid = self._read_movement_grid()
            if grid:
                movement_maps[unit.id] = summarise_movement_grid(grid)
            else:
                logging.warning("Failed to read movement grid for unit %s", unit.name)

            return_to_map()
            time.sleep(0.1)
            cursor_pos = get_cursor_position() or cursor_pos

        return movement_maps

    def _read_movement_grid(self, attempts: int = 5, delay: float = 0.1) -> List[List[int]]:
        for _ in range(attempts):
            grid = self.data_gatherer.parse_map_section("MOVEMENT_MAP")
            if grid:
                return grid
            time.sleep(delay)
        return []

    def _build_planning_payload(
        self,
        snapshot: TurnSnapshot,
        movement_maps: Dict[int, List[str]],
    ) -> List[Dict[str, Any]]:
        base = self.serialiser.serialise(
            snapshot,
            map_grid=self.map_grid,
            movement_maps=movement_maps,
        )
        movement_blob = {
            str(unit_id): movement_maps[unit_id]
            for unit_id in movement_maps
        }
        return [
            {"snapshot": base},
            {"movement_grids": movement_blob},
            {
                "notes": {
                    "movement": "Rows of 0/+/X showing unit tile, reachable tiles, and blocks",
                    "map": "Map grid comes from fe_map.txt characters",
                }
            },
        ]

    def _build_execution_payload(
        self,
        snapshot: TurnSnapshot,
        movement_maps: Dict[int, List[str]],
        preview_instructions: List[PreviewInstruction],
        battle_previews: List[BattlePreview],
    ) -> List[Dict[str, Any]]:
        base = self.serialiser.serialise(
            snapshot,
            map_grid=self.map_grid,
            movement_maps=movement_maps,
        )
        previews_blob = [self._preview_to_dict(inst) for inst in preview_instructions]
        battle_blob = [self._battle_to_dict(preview) for preview in battle_previews]
        return [
            {"snapshot": base},
            {"movement_grids": {
                str(unit_id): movement_maps[unit_id]
                for unit_id in movement_maps
            }},
            {"preview_plan": previews_blob},
            {"battle_previews": battle_blob},
        ]

    def _preview_to_dict(self, instruction: PreviewInstruction) -> Dict[str, Any]:
        payload = {
            "order": instruction.order,
            "unit_id": instruction.unit_id,
            "from": {"x": instruction.from_tile[0], "y": instruction.from_tile[1]},
            "target_unit_id": instruction.target_unit_id,
            "weapon_id": instruction.weapon_id,
        }
        if instruction.target_tile:
            payload["target_hint"] = {
                "x": instruction.target_tile[0],
                "y": instruction.target_tile[1],
            }
        return payload

    def _battle_to_dict(self, preview: BattlePreview) -> Dict[str, Any]:
        return {
            "order": preview.order,
            "unit_id": preview.unit_id,
            "target_unit_id": preview.target_unit_id,
            "weapon_id": preview.weapon_id,
            "from": {"x": preview.from_tile[0], "y": preview.from_tile[1]},
            "target_tile": {
                "x": preview.target_tile[0],
                "y": preview.target_tile[1],
            },
            "attacker": preview.attacker,
            "defender": preview.defender,
            "rounds": preview.rounds,
        }

    def _collect_battle_previews(
        self,
        snapshot: TurnSnapshot,
        instructions: List[PreviewInstruction],
    ) -> List[BattlePreview]:
        previews: List[BattlePreview] = []
        cursor_pos = get_cursor_position() or snapshot.cursor_position

        unit_lookup = {unit.id: unit for unit in snapshot.units}
        enemy_lookup = {enemy.id: enemy for enemy in snapshot.enemies}

        for instruction in instructions:
            unit = unit_lookup.get(instruction.unit_id)
            enemy = enemy_lookup.get(instruction.target_unit_id)
            if not unit or not enemy:
                logging.warning(
                    "Preview request references unknown units: %s -> %s",
                    instruction.unit_id,
                    instruction.target_unit_id,
                )
                continue

            weapon_slot = self._weapon_slot_for(unit, instruction.weapon_id)
            if weapon_slot is None:
                logging.warning(
                    "Unit %s missing weapon %s for preview",
                    unit.name,
                    instruction.weapon_id,
                )
                continue

            cursor_pos, preview = self._execute_preview(
                unit,
                enemy,
                instruction,
                cursor_pos,
                weapon_slot,
            )
            if preview:
                previews.append(preview)

        return previews

    @staticmethod
    def _weapon_slot_for(unit: Unit, weapon_id: int) -> Optional[int]:
        for idx, (item_id, _) in enumerate(unit.items):
            if item_id == weapon_id:
                return idx
        return None

    def _execute_preview(
        self,
        unit: Unit,
        enemy: Unit,
        instruction: PreviewInstruction,
        cursor_pos: Optional[Tuple[int, int]],
        weapon_slot: int,
    ) -> Tuple[Optional[Tuple[int, int]], Optional[BattlePreview]]:
        logging.info(
            "Gathering preview for %s attacking %s", unit.name, enemy.name
        )

        cursor_pos = move_cursor_to(unit.position, cursor_pos)
        press_key("x", duration=0.05)
        time.sleep(0.2)

        attack_tile = instruction.from_tile
        if attack_tile != unit.position:
            cursor_pos = move_cursor_to(attack_tile, cursor_pos, verify=False)
            time.sleep(0.2)

        press_key("x", duration=0.05)
        time.sleep(0.2)

        press_key("x", duration=0.05)  # Attack command
        time.sleep(0.2)

        for _ in range(weapon_slot):
            press_key("DOWN", duration=0.05)
            time.sleep(0.05)
        press_key("x", duration=0.05)  # Select weapon
        time.sleep(0.4)

        for _ in range(4):
            press_key("z", duration=0.05)
            time.sleep(0.05)

        press_key("LEFT", duration=0.05)
        time.sleep(0.05)
        press_key("RIGHT", duration=0.05)
        time.sleep(0.05)

        battle = wait_for_battle_data()
        preview: Optional[BattlePreview] = None
        if battle:
            preview = BattlePreview(
                order=instruction.order,
                unit_id=unit.id,
                target_unit_id=enemy.id,
                weapon_id=instruction.weapon_id,
                from_tile=instruction.from_tile,
                target_tile=instruction.target_tile or enemy.position,
                attacker=summarise_battle_struct(battle["attacker"]),
                defender=summarise_battle_struct(battle["defender"]),
                rounds=summarise_rounds(battle.get("rounds", [])),
            )
        else:
            logging.warning(
                "No battle data captured for preview %s -> %s",
                unit.name,
                enemy.name,
            )

        return_to_map()
        cursor_pos = get_cursor_position() or cursor_pos or unit.position
        return cursor_pos, preview


# ---------------------------------------------------------------------------
# Entry point


def configure_logging() -> None:
    level_name = os.getenv("TACTICAL_AGENT_LOG", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="[%(asctime)s] %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> None:
    configure_logging()
    agent = TacticalAgent()
    agent.run()


if __name__ == "__main__":
    main()

