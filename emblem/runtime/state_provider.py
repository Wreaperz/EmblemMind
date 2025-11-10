"""State provider abstraction supporting file and bridge backends."""

from __future__ import annotations

import atexit
import threading

from emblem.bridge.server import BridgeServer
from emblemmind_snapshot import TurnSnapshot


class StateProvider:
    def load_snapshot(self, *, timeout: float | None = None) -> TurnSnapshot:
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover - default noop
        pass


class FileStateProvider(StateProvider):
    def __init__(self, state_file: str, map_file: str) -> None:
        self.state_file = state_file
        self.map_file = map_file

    def load_snapshot(self, *, timeout: float | None = None) -> TurnSnapshot:
        _ = timeout  # unused for file provider
        return TurnSnapshot.from_files(self.state_file, self.map_file)


class BridgeStateProvider(StateProvider):
    def __init__(self, port: int, poll_interval: float) -> None:
        self.server = BridgeServer(port=port, poll_interval=poll_interval)
        self.server.start(background=True)
        self._lock = threading.Lock()
        atexit.register(self.close)

    def load_snapshot(self, *, timeout: float | None = None) -> TurnSnapshot:
        try:
            packet = self.server.next_state(timeout=timeout)
        except TimeoutError:
            packet = self.server.latest_state
            if packet is None:
                raise
        return TurnSnapshot.from_bridge_state(packet)

    def close(self) -> None:
        with self._lock:
            if self.server is not None:
                self.server.shutdown()
                self.server = None


def create_state_provider(
    config: dict, state_file: str, map_file: str
) -> StateProvider:
    bridge_cfg = config.get("bridge", {}) if config else {}
    if bridge_cfg.get("enabled", False):
        timeout_ms = bridge_cfg.get("timeout_ms", 100)
        return BridgeStateProvider(
            port=config.get("port", 17653),
            poll_interval=timeout_ms / 1000.0,
        )
    return FileStateProvider(state_file, map_file)


__all__ = [
    "create_state_provider",
    "StateProvider",
    "BridgeStateProvider",
    "FileStateProvider",
]
