from typing import List, Tuple, Optional
from dataclasses import dataclass
from emblemmind_snapshot import TurnSnapshot, Unit
from utils.fe_data_mappings import ITEM_ATTACK_RANGES, get_weapon_type, get_item_name

@dataclass
class Action:
    """Represents a potential action that can be taken in the game"""
    unit: Unit
    action_type: str  # 'move', 'attack', 'rescue', 'item'
    target_position: Tuple[int, int]  # Where the action is directed
    target_unit: Optional[Unit] = None  # For actions targeting specific units
    item_id: Optional[int] = None  # For item usage
    score: float = 0.0  # Initial score, can be updated by neural network

class ActionGenerator:
    """Generates potential actions for units in the current game state"""

    def __init__(self, snapshot: TurnSnapshot):
        self.snapshot = snapshot
        self.terrain_map = snapshot.map
        self.units = snapshot.units
        self.enemies = snapshot.enemies

    def generate_all_actions(self) -> List[Action]:
        """Generate all possible actions for all available units"""
        actions = []
        for unit in self.units:
            if unit.can_act:
                actions.extend(self._generate_unit_actions(unit))
        return actions

    def _generate_unit_actions(self, unit: Unit, movement_map=None, range_map=None) -> List[Action]:
        """Generate all possible actions for a single unit, optionally using movement and range maps for attack actions"""
        actions = []

        # Generate movement actions
        actions.extend(self._generate_movement_actions(unit))

        # Generate attack actions (pass in maps if provided)
        actions.extend(self._generate_attack_actions(unit, movement_map, range_map))

        # Generate rescue actions
        actions.extend(self._generate_rescue_actions(unit))

        # Generate item usage actions
        actions.extend(self._generate_item_actions(unit))

        return actions

    def _generate_movement_actions(self, unit: Unit) -> List[Action]:
        """Generate all possible movement actions for a unit"""
        actions = []
        movement_range = unit.movement_range

        # Get all reachable positions within movement range
        for y in range(max(0, unit.position[1] - movement_range),
                      min(self.terrain_map.height, unit.position[1] + movement_range + 1)):
            for x in range(max(0, unit.position[0] - movement_range),
                          min(self.terrain_map.width, unit.position[0] + movement_range + 1)):
                # Check if position is within movement range
                distance = abs(x - unit.position[0]) + abs(y - unit.position[1])
                if distance <= movement_range:
                    # Check if position is unoccupied
                    if not self.snapshot.get_unit_at(x, y):
                        actions.append(Action(
                            unit=unit,
                            action_type='move',
                            target_position=(x, y)
                        ))
        return actions

    def _generate_attack_actions(self, unit: Unit, movement_map=None, range_map=None) -> List[Action]:
        """Generate all possible attack actions for a unit, considering movement and range maps"""
        actions = []
        # Track (enemy_id, item_id, x, y) to avoid redundant actions
        seen = set()
        # Always consider attacks from the current position (for long-range tomes, bows, etc.)
        for item_id, uses in unit.items:
            if uses > 0 and item_id in ITEM_ATTACK_RANGES:
                min_range, max_range = ITEM_ATTACK_RANGES[item_id]
                for enemy in self.enemies:
                    if not (enemy.is_visible and enemy.is_alive):
                        continue
                    ex, ey = enemy.position
                    ux, uy = unit.position
                    dist = abs(ex - ux) + abs(ey - uy)
                    if min_range <= dist <= max_range:
                        key = (enemy.id, item_id, ux, uy)
                        if key not in seen:
                            seen.add(key)
                            actions.append(Action(
                                unit=unit,
                                action_type='attack',
                                target_position=unit.position,
                                target_unit=enemy,
                                item_id=item_id
                            ))
        # Existing logic for moving and attacking (if movement_map is provided)
        if movement_map is not None and range_map is not None:
            width = len(movement_map[0]) if movement_map else 0
            height = len(movement_map)
            for item_id, uses in unit.items:
                if uses > 0 and item_id in ITEM_ATTACK_RANGES:
                    min_range, max_range = ITEM_ATTACK_RANGES[item_id]
                    for enemy in self.enemies:
                        if not (enemy.is_visible and enemy.is_alive):
                            continue
                        ex, ey = enemy.position
                        for y in range(height):
                            for x in range(width):
                                dist = abs(ex - x) + abs(ey - y)
                                if not (min_range <= dist <= max_range):
                                    continue
                                if (x, y) == (ex, ey):
                                    continue
                                if movement_map[y][x] == 0xFF:
                                    continue
                                if self.snapshot.get_unit_at(x, y):
                                    continue
                                if (x, y) == unit.position:
                                    continue
                                key = (enemy.id, item_id, x, y)
                                if key not in seen:
                                    seen.add(key)
                                    actions.append(Action(
                                        unit=unit,
                                        action_type='attack',
                                        target_position=(x, y),
                                        target_unit=enemy,
                                        item_id=item_id
                                    ))
        print(f"[DEBUG] {unit.name} generated {len(actions)} attack actions (all weapons considered). Enemies: {[e.name for e in self.enemies if e.is_alive and e.is_visible]}")
        return actions

    def _generate_rescue_actions(self, unit: Unit) -> List[Action]:
        """Generate all possible rescue actions for a unit"""
        actions = []

        # Check each allied unit that can be rescued
        for ally in self.units:
            if ally.is_rescued and ally.position == unit.position:
                actions.append(Action(
                    unit=unit,
                    action_type='rescue',
                    target_position=ally.position,
                    target_unit=ally
                ))
        return actions

    def _generate_item_actions(self, unit: Unit) -> List[Action]:
        """Generate all possible item usage actions for a unit"""
        actions = []
        for item_id, uses in unit.items:
            if uses > 0:
                weapon_type = get_weapon_type(item_id)
                # Only allow non-weapon items (healing, stat boosters, etc.)
                if weapon_type is None or weapon_type == "Item":
                    item_name = get_item_name(item_id).lower()
                    # Only use healing items if HP is not full
                    if any(h in item_name for h in ["vulnerary", "elixir", "recover", "heal"]):
                        if unit.hp[0] < unit.hp[1]:
                            actions.append(Action(
                                unit=unit,
                                action_type='item',
                                target_position=unit.position,  # Using item on self
                                item_id=item_id
                            ))
                    # Optionally: add logic for stat boosters, etc. (skip for now)
        return actions