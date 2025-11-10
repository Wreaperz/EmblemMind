import json
import socket
import time

import pytest

from emblem.bridge.server import (
    ActionPacket,
    BridgeServer,
    StatePacket,
    decode_state,
    encode_action,
)


@pytest.fixture
def sample_state_dict():
    return {
        "t": "state",
        "frame": 123,
        "phase": "player",
        "cursor": {"x": 5, "y": 7},
        "turn": 3,
        "units": [
            {
                "id": 1,
                "name": "Lyn",
                "side": "ally",
                "hp": 18,
                "max_hp": 18,
                "class": "Lord",
                "x": 5,
                "y": 7,
                "mov": 5,
                "rng": [1, 1],
                "atk": 8,
                "def": 2,
                "res": 5,
                "spd": 10,
                "luk": 5,
                "weapon": "Iron Sword",
                "status": "healthy",
            }
        ],
        "terrain": [{"x": 5, "y": 7, "tile": "plain", "def": 0, "avoid": 5, "cost": 1}],
        "objectives": {"type": "seize", "turns_left": 10},
    }


def test_decode_state_round_trip(sample_state_dict):
    packet = decode_state(json.dumps(sample_state_dict))
    assert isinstance(packet, StatePacket)
    assert packet.frame == 123
    assert packet.phase == "player"
    assert packet.cursor.x == 5 and packet.cursor.y == 7
    assert packet.turn == 3
    assert len(packet.units) == 1
    unit = packet.units[0]
    assert unit.name == "Lyn"
    assert unit.weapon == "Iron Sword"
    assert packet.objectives.type == "seize"


def test_encode_action_minimal():
    action = ActionPacket(kind="wait", unit_id=1, path=((5, 7),))
    message = encode_action(action)
    parsed = json.loads(message)
    assert parsed["t"] == "action"
    assert parsed["kind"] == "wait"
    assert parsed["unit_id"] == 1
    assert parsed["path"] == [[5, 7]]
    assert "target" not in parsed


def test_bridge_server_integration(sample_state_dict):
    server = BridgeServer(port=0, poll_interval=0.01)
    server.start()

    try:
        client = socket.create_connection(("127.0.0.1", server.port), timeout=1)
        client.settimeout(0.2)
        state_line = json.dumps(sample_state_dict) + "\n"
        client.sendall(state_line.encode("utf-8"))
        # Send ping
        client.sendall(json.dumps({"t": "ping", "frame": 123}).encode("utf-8") + b"\n")

        # Spin server loop briefly
        for _ in range(10):
            server.serve_once()
            time.sleep(0.01)

        state = server.latest_state
        assert state is not None
        assert state.frame == 123

        # Ensure pong was sent back
        data = client.recv(1024)
        assert b"\npong" in data or b'"t":"pong"' in data

        server.queue_action(ActionPacket(kind="wait", unit_id=1, path=((5, 7),)))
        for _ in range(5):
            server.serve_once()
            time.sleep(0.01)

        response = client.recv(1024)
        assert b'"t":"action"' in response
    finally:
        server.shutdown()
        client.close()
