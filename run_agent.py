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

# Prompt used for the tactical policy.  The string intentionally begins with the
# phrasing requested by the user so the model always receives the same prefix.
POLICY_PROMPT = (
    "You are a deterministic Fire Emblem 7 tactical policy. You never explain. "
    "You output JSON only that conforms exactly to the Output Schema. Choose a "
    "single legal action per allied unit and an execution order that maximizes "
    "survival of lords, progress toward objectives, and net advantage.\n\n"
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

    def serialise(self, snapshot: TurnSnapshot) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "turn": snapshot.current_turn,
            "chapter_id": snapshot.chapter_id,
            "phase": snapshot.phase_text,
            "cursor": self._coord_dict(snapshot.cursor_position),
            "map": {
                "width": snapshot.map.width,
                "height": snapshot.map.height,
            },
            "allies": [self._unit_dict(unit) for unit in snapshot.units],
            "enemies": [self._unit_dict(unit) for unit in snapshot.enemies],
        }
        return payload

    @staticmethod
    def _coord_dict(coord: Optional[Tuple[int, int]]) -> Optional[Dict[str, int]]:
        if coord is None:
            return None
        x, y = coord
        return {"x": x, "y": y}

    @staticmethod
    def _unit_dict(unit: Unit) -> Dict[str, Any]:
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
        self.serialiser = SnapshotSerialiser()

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
            # Prefer the v1 client API when available, otherwise fall back to the
            # legacy global module interface.
            client_cls = getattr(openai, "OpenAI", None)
            if client_cls is not None:
                self._client = client_cls(api_key=api_key)
            else:  # pragma: no cover - depends on installed SDK version
                openai.api_key = api_key

    # Public API -----------------------------------------------------------------

    def request_plan(self, snapshot: TurnSnapshot) -> str:
        """Serialise *snapshot* and retrieve the JSON action plan."""

        if self.dry_run:
            return self._fallback_plan(snapshot)

        payload = self.serialiser.serialise(snapshot)
        payload_text = json.dumps(payload, indent=2, sort_keys=True)
        logging.info("OpenAI tactical policy request payload:%s%s", os.linesep, payload_text)
        logging.debug(
            "Serialised snapshot payload (truncated): %s",
            shorten(payload_text, width=2000, placeholder="..."),
        )
        user_content = payload_text

        logging.info("Dispatching snapshot to OpenAI tactical policy")

        messages = [
            {"role": "system", "content": POLICY_PROMPT},
            {"role": "user", "content": user_content},
        ]

        if self._client is not None:
            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                )
                content = response.choices[0].message.content.strip()
                logging.info(
                    "OpenAI tactical policy raw response:%s%s",
                    os.linesep,
                    content,
                )
                logging.debug(
                    "Received chat.completions response (truncated): %s",
                    shorten(content, width=2000, placeholder="..."),
                )
                return content
            except AttributeError:  # pragma: no cover - SDK differences
                response = self._client.responses.create(
                    model=self.model,
                    input=messages,
                    temperature=self.temperature,
                )
                if hasattr(response, "output"):
                    # Responses API returns a list of content blocks
                    for block in response.output:
                        if getattr(block, "content", None):
                            first = block.content[0]
                            if getattr(first, "text", None):
                                content = first.text.strip()
                                logging.info(
                                    "OpenAI tactical policy raw response:%s%s",
                                    os.linesep,
                                    content,
                                )
                                logging.debug(
                                    "Received responses.create content block (truncated): %s",
                                    shorten(content, width=2000, placeholder="..."),
                                )
                                return content
                content = getattr(response, "output_text", "[]")
                logging.info(
                    "OpenAI tactical policy raw response:%s%s",
                    os.linesep,
                    content,
                )
                logging.debug(
                    "Received responses.create text (truncated): %s",
                    shorten(content, width=2000, placeholder="..."),
                )
                return content

        response = openai.ChatCompletion.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            timeout=OPENAI_TIMEOUT,
        )
        content = response["choices"][0]["message"]["content"].strip()
        logging.info(
            "OpenAI tactical policy raw response:%s%s",
            os.linesep,
            content,
        )
        logging.debug(
            "Received ChatCompletion response (truncated): %s",
            shorten(content, width=2000, placeholder="..."),
        )
        return content

    # Internals -------------------------------------------------------------------

    def _fallback_plan(self, snapshot: TurnSnapshot) -> str:
        """Return a deterministic fallback plan when the API is unavailable."""

        plan = []
        order = 1
        for unit in snapshot.get_available_units():
            plan.append(
                {
                    "unit_id": unit.id,
                    "order": order,
                    "action": {
                        "type": "wait",
                        "target": {"x": unit.position[0], "y": unit.position[1]},
                    },
                }
            )
            order += 1
        if not plan:
            plan.append(
                {
                    "unit_id": 0,
                    "order": 1,
                    "action": {"type": "end_turn"},
                }
            )
        return json.dumps(plan)


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
) -> Tuple[int, int]:
    if current_pos is None:
        current_pos = target_pos
    logging.debug("Moving cursor from %s to %s", current_pos, target_pos)

    for attempt in range(max_attempts):
        dx = target_pos[0] - current_pos[0]
        dy = target_pos[1] - current_pos[1]

        for _ in range(abs(dx)):
            press_key("RIGHT" if dx > 0 else GBA_KEY_MAP["LEFT"], duration=0.05)
            time.sleep(0.05)

        for _ in range(abs(dy)):
            press_key("DOWN" if dy > 0 else GBA_KEY_MAP["UP"], duration=0.05)
            time.sleep(0.05)

        time.sleep(0.1)
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

    cursor_pos = move_cursor_to(action.target_position, cursor_pos)
    press_key("x", duration=0.05)
    time.sleep(0.1)

    time.sleep(0.1)
    press_key("x", duration=0.05)
    time.sleep(0.1)
    press_key("x", duration=0.05)
    time.sleep(0.1)
    press_key("x", duration=0.05)
    time.sleep(0.1)

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
        cursor_pos = move_cursor_to(target_position, cursor_pos)
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
        self.executor = ActionPlanExecutor()
        self.data_gatherer = DataGatherer()
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

                plan_text = self.policy.request_plan(snapshot)
                logging.debug(
                    "Policy returned plan text (truncated): %s",
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

