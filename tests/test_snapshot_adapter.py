from emblem.bridge.server import (
    Cursor,
    ObjectivePacket,
    StatePacket,
    TerrainPacket,
    UnitPacket,
)
from emblemmind_snapshot import TurnSnapshot


def build_packet() -> StatePacket:
    unit = UnitPacket(
        id=1,
        name="Lyn",
        side="ally",
        hp=18,
        max_hp=18,
        class_name="Lord",
        x=4,
        y=5,
        mov=5,
        rng=(1, 1),
        atk=8,
        defense=2,
        res=5,
        spd=10,
        luk=5,
        weapon="Iron Sword",
        status="healthy",
    )
    enemy = UnitPacket(
        id=2,
        name="Bandit",
        side="enemy",
        hp=20,
        max_hp=20,
        class_name="Brigand",
        x=6,
        y=5,
        mov=5,
        rng=(1, 1),
        atk=10,
        defense=3,
        res=0,
        spd=6,
        luk=0,
        weapon="Iron Axe",
        status="healthy",
    )
    terrain = TerrainPacket(x=4, y=5, tile="plains", defense=0, avoid=5, cost=1)
    return StatePacket(
        frame=42,
        phase="player",
        cursor=Cursor(x=4, y=5),
        turn=3,
        units=(unit, enemy),
        terrain=(terrain,),
        objectives=ObjectivePacket(type="seize", turns_left=10),
    )


def test_turn_snapshot_from_bridge_packet():
    packet = build_packet()
    snapshot = TurnSnapshot.from_bridge_state(packet)
    assert snapshot.current_turn == 3
    assert snapshot.cursor_position == (4, 5)
    assert any(u.name == "Lyn" for u in snapshot.units)
    assert any(e.name == "Bandit" for e in snapshot.enemies)
    assert snapshot.map.get_terrain_at(4, 5) == "plains"
