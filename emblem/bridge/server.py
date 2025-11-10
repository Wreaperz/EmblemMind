"""TCP server that bridges BizHawk Lua scripts with the Python agent."""

from __future__ import annotations

import json
import selectors
import socket
import threading
import time
from dataclasses import dataclass, field
from queue import Empty, Queue
from typing import Any, Dict, Optional, Tuple

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 17653
BUFFER_SIZE = 4096
JSON_SEPARATORS = (",", ":")


class BridgeClosed(RuntimeError):
    """Raised when the bridge connection is unexpectedly closed."""


@dataclass(slots=True)
class Cursor:
    x: int
    y: int


@dataclass(slots=True)
class UnitPacket:
    id: int
    name: str
    side: str
    hp: int
    max_hp: int
    class_name: str
    x: int
    y: int
    mov: int
    rng: Tuple[int, int]
    atk: int
    defense: int
    res: int
    spd: int
    luk: int
    weapon: str
    status: str


@dataclass(slots=True)
class TerrainPacket:
    x: int
    y: int
    tile: str
    defense: int
    avoid: int
    cost: int


@dataclass(slots=True)
class ObjectivePacket:
    type: str
    turns_left: Optional[int]


@dataclass(slots=True)
class StatePacket:
    frame: int
    phase: str
    cursor: Cursor
    turn: int
    units: Tuple[UnitPacket, ...]
    terrain: Tuple[TerrainPacket, ...]
    objectives: Optional[ObjectivePacket]


@dataclass(slots=True)
class ActionPacket:
    kind: str
    unit_id: int
    path: Tuple[Tuple[int, int], ...] = field(default_factory=tuple)
    target: Optional[Cursor] = None
    weapon: Optional[str] = None


def _ensure_int(value: Any, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric, got {type(value)!r}")
    return int(value)


def decode_state(message: str) -> StatePacket:
    payload = json.loads(message)
    if payload.get("t") != "state":
        raise ValueError("Message is not a state packet")

    cursor_data = payload.get("cursor") or {}
    cursor = Cursor(
        x=_ensure_int(cursor_data.get("x", 0), field_name="cursor.x"),
        y=_ensure_int(cursor_data.get("y", 0), field_name="cursor.y"),
    )

    def build_unit(raw: Dict[str, Any]) -> UnitPacket:
        return UnitPacket(
            id=_ensure_int(raw.get("id", 0), field_name="unit.id"),
            name=str(raw.get("name", "")),
            side=str(raw.get("side", "ally")),
            hp=_ensure_int(raw.get("hp", 0), field_name="unit.hp"),
            max_hp=_ensure_int(raw.get("max_hp", 0), field_name="unit.max_hp"),
            class_name=str(raw.get("class", "")),
            x=_ensure_int(raw.get("x", 0), field_name="unit.x"),
            y=_ensure_int(raw.get("y", 0), field_name="unit.y"),
            mov=_ensure_int(raw.get("mov", 0), field_name="unit.mov"),
            rng=(
                _ensure_int((raw.get("rng") or (0, 0))[0], field_name="unit.rng_min"),
                _ensure_int((raw.get("rng") or (0, 0))[1], field_name="unit.rng_max"),
            ),
            atk=_ensure_int(raw.get("atk", 0), field_name="unit.atk"),
            defense=_ensure_int(raw.get("def", 0), field_name="unit.def"),
            res=_ensure_int(raw.get("res", 0), field_name="unit.res"),
            spd=_ensure_int(raw.get("spd", 0), field_name="unit.spd"),
            luk=_ensure_int(raw.get("luk", 0), field_name="unit.luk"),
            weapon=str(raw.get("weapon") or ""),
            status=str(raw.get("status") or "none"),
        )

    def build_terrain(raw: Dict[str, Any]) -> TerrainPacket:
        return TerrainPacket(
            x=_ensure_int(raw.get("x", 0), field_name="terrain.x"),
            y=_ensure_int(raw.get("y", 0), field_name="terrain.y"),
            tile=str(raw.get("tile", "")),
            defense=_ensure_int(raw.get("def", 0), field_name="terrain.def"),
            avoid=_ensure_int(raw.get("avoid", 0), field_name="terrain.avoid"),
            cost=_ensure_int(raw.get("cost", 0), field_name="terrain.cost"),
        )

    objective = payload.get("objectives")
    if objective is not None:
        objective_packet = ObjectivePacket(
            type=str(objective.get("type", "")),
            turns_left=(
                None
                if objective.get("turns_left") is None
                else _ensure_int(
                    objective.get("turns_left"), field_name="objectives.turns_left"
                )
            ),
        )
    else:
        objective_packet = None

    units = tuple(build_unit(unit) for unit in payload.get("units", []))
    terrain = tuple(build_terrain(tile) for tile in payload.get("terrain", []))

    return StatePacket(
        frame=_ensure_int(payload.get("frame", 0), field_name="frame"),
        phase=str(payload.get("phase", "other")),
        cursor=cursor,
        turn=_ensure_int(payload.get("turn", 0), field_name="turn"),
        units=units,
        terrain=terrain,
        objectives=objective_packet,
    )


def encode_action(packet: ActionPacket) -> str:
    payload: Dict[str, Any] = {
        "t": "action",
        "kind": packet.kind,
        "unit_id": packet.unit_id,
        "path": [[step[0], step[1]] for step in packet.path],
    }
    if packet.target is not None:
        payload["target"] = {"x": packet.target.x, "y": packet.target.y}
    if packet.weapon is not None:
        payload["weapon"] = packet.weapon
    return json.dumps(payload, separators=JSON_SEPARATORS)


def encode_pong(frame: int) -> str:
    return json.dumps({"t": "pong", "frame": frame}, separators=JSON_SEPARATORS)


class BridgeServer:
    """Non-blocking TCP server speaking the BizHawk bridge protocol."""

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        *,
        poll_interval: float = 0.01,
        state_queue_size: int = 8,
    ) -> None:
        self.host = host
        self.port = port
        self.poll_interval = poll_interval
        self._selector = selectors.DefaultSelector()
        self._server: Optional[socket.socket] = None
        self._client: Optional[socket.socket] = None
        self._client_addr: Optional[Tuple[str, int]] = None
        self._recv_buffer = ""
        self._send_buffer = ""
        self._state_queue: "Queue[StatePacket]" = Queue(maxsize=state_queue_size)
        self._latest_state: Optional[StatePacket] = None
        self._running = False
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None

    @property
    def latest_state(self) -> Optional[StatePacket]:
        return self._latest_state

    def start(self, *, background: bool = False) -> None:
        if self._server is not None:
            raise RuntimeError("BridgeServer already started")
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind((self.host, self.port))
        self.port = self._server.getsockname()[1]
        self._server.listen(1)
        self._server.setblocking(False)
        self._selector.register(self._server, selectors.EVENT_READ, self._accept)
        self._running = True
        if background:
            self._thread = threading.Thread(target=self.serve_forever, daemon=True)
            self._thread.start()

    def serve_forever(self) -> None:
        while self._running:
            self.serve_once()

    def serve_once(self, timeout: Optional[float] = None) -> None:
        if not self._running:
            return
        timeout = self.poll_interval if timeout is None else timeout
        events = self._selector.select(timeout)
        for key, mask in events:
            callback = key.data
            callback(key.fileobj, mask)
        self._flush_outgoing()

    def shutdown(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=0.2)
        if self._client is not None:
            try:
                self._selector.unregister(self._client)
            except Exception:
                pass
            try:
                self._client.close()
            except OSError:
                pass
            self._client = None
        if self._server is not None:
            try:
                self._selector.unregister(self._server)
            except Exception:
                pass
            try:
                self._server.close()
            except OSError:
                pass
            self._server = None
        self._selector.close()

    def next_state(self, timeout: Optional[float] = None) -> StatePacket:
        deadline = None if timeout is None else time.time() + timeout
        while True:
            try:
                if deadline is None:
                    return self._state_queue.get(timeout=self.poll_interval)
                remaining = deadline - time.time()
                if remaining <= 0:
                    raise TimeoutError("Timed out waiting for state")
                return self._state_queue.get(timeout=remaining)
            except Empty:
                if not self._running:
                    raise BridgeClosed("Bridge stopped while waiting for state")
                continue

    def queue_action(self, action: ActionPacket) -> None:
        encoded = encode_action(action) + "\n"
        with self._lock:
            self._send_buffer = encoded

    # Internal callbacks -------------------------------------------------

    def _accept(self, sock: socket.socket, _mask: int) -> None:
        try:
            client, address = sock.accept()
            client.setblocking(False)
        except BlockingIOError:
            return
        if self._client is not None:
            # Replace previous client
            try:
                self._selector.unregister(self._client)
            except Exception:
                pass
            try:
                self._client.close()
            except OSError:
                pass
        self._client = client
        self._client_addr = address
        self._recv_buffer = ""
        self._send_buffer = ""
        self._selector.register(client, selectors.EVENT_READ, self._read_client)

    def _read_client(self, sock: socket.socket, _mask: int) -> None:
        try:
            chunk = sock.recv(BUFFER_SIZE)
        except BlockingIOError:
            return
        except ConnectionResetError:
            self._handle_disconnect()
            return
        if not chunk:
            self._handle_disconnect()
            return
        self._recv_buffer += chunk.decode("utf-8")
        self._drain_lines()

    def _flush_outgoing(self) -> None:
        if not self._client or not self._send_buffer:
            return
        with self._lock:
            data = self._send_buffer.encode("utf-8")
            try:
                sent = self._client.send(data)
            except (BlockingIOError, BrokenPipeError):
                return
            if sent >= len(data):
                self._send_buffer = ""
            else:
                # Keep remaining bytes
                remaining = data[sent:].decode("utf-8")
                self._send_buffer = remaining

    def _drain_lines(self) -> None:
        while "\n" in self._recv_buffer:
            line, self._recv_buffer = self._recv_buffer.split("\n", 1)
            if not line:
                continue
            self._handle_message(line)

    def _handle_message(self, message: str) -> None:
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            return
        msg_type = payload.get("t")
        if msg_type == "ping":
            frame = int(payload.get("frame", 0))
            self._enqueue_raw(encode_pong(frame))
            return
        if msg_type != "state":
            return
        try:
            state = decode_state(message)
        except (TypeError, ValueError):
            return
        self._latest_state = state
        if self._state_queue.full():
            try:
                self._state_queue.get_nowait()
            except Empty:
                pass
        self._state_queue.put_nowait(state)

    def _enqueue_raw(self, payload: str) -> None:
        with self._lock:
            self._send_buffer = payload + "\n"

    def _handle_disconnect(self) -> None:
        if self._client is not None:
            try:
                self._selector.unregister(self._client)
            except Exception:
                pass
            try:
                self._client.close()
            except OSError:
                pass
        self._client = None
        self._client_addr = None
        self._recv_buffer = ""
        self._send_buffer = ""


__all__ = [
    "BridgeServer",
    "BridgeClosed",
    "StatePacket",
    "ActionPacket",
    "UnitPacket",
    "TerrainPacket",
    "ObjectivePacket",
    "Cursor",
    "decode_state",
    "encode_action",
]
