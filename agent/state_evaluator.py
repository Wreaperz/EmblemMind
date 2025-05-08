from typing import Dict, List
from emblemmind_snapshot import TurnSnapshot, Unit
from agent.action_generator import Action

class StateEvaluator:
    """Evaluates game states and potential outcomes"""

    def __init__(self, snapshot: TurnSnapshot):
        self.snapshot = snapshot
        self.terrain_map = snapshot.map
        self.units = snapshot.units
        self.enemies = snapshot.enemies

    def evaluate_state(self) -> float:
        """Evaluate the current game state"""
        score = 0.0

        # Unit health and positioning
        for unit in self.units:
            if unit.is_alive:
                # Health score (higher is better)
                health_ratio = unit.hp[0] / unit.hp[1]
                score += health_ratio * 10

                # Positioning score (based on distance to enemies)
                min_enemy_dist = self._get_min_enemy_distance(unit)
                if min_enemy_dist > 0:
                    score += 5 / min_enemy_dist  # Closer to enemies is better

        # Enemy threat assessment
        for enemy in self.enemies:
            if enemy.is_visible and enemy.is_alive:
                # Enemy health (lower is better)
                health_ratio = enemy.hp[0] / enemy.hp[1]
                score -= (1 - health_ratio) * 10

                # Enemy positioning (further is better)
                min_ally_dist = self._get_min_ally_distance(enemy)
                if min_ally_dist > 0:
                    score -= 5 / min_ally_dist  # Closer to allies is worse

        return score

    def evaluate_action(self, action: Action) -> Dict:
        """Evaluate a potential action and return features for the neural network"""
        num_visible_enemies = len([e for e in self.enemies if e.is_visible and e.is_alive])
        num_invisible_enemies = len([e for e in self.enemies if not e.is_visible and e.is_alive])
        min_dist_visible_enemy = self._get_min_enemy_distance(action.unit, only_visible=True)
        min_dist_any_enemy = self._get_min_enemy_distance(action.unit, only_visible=False)
        hidden_threat = 0.0
        for enemy in self.enemies:
            if not enemy.is_visible and enemy.is_alive:
                dist = self._get_distance(action.target_position, enemy.position)
                if dist <= 5:  # Arbitrary threat radius
                    hidden_threat += 1.0 / (dist + 1)
        features = {
            'action_type': self._encode_action_type(action.action_type),
            'unit_health': action.unit.hp[0] / action.unit.hp[1],
            'target_distance': self._get_distance(action.unit.position, action.target_position),
            'terrain_cost': self._get_terrain_cost(action.target_position),
            'threat_level': self._calculate_threat_level(action),
            'potential_damage': self._estimate_potential_damage(action),
            'position_value': self._evaluate_position_value(action.target_position),
            'num_visible_enemies': num_visible_enemies,
            'num_invisible_enemies': num_invisible_enemies,
            'min_dist_visible_enemy': min_dist_visible_enemy,
            'min_dist_any_enemy': min_dist_any_enemy,
            'hidden_threat': hidden_threat
        }
        if action.target_unit:
            features.update({
                'target_health': action.target_unit.hp[0] / action.target_unit.hp[1],
                'target_is_enemy': action.target_unit.is_enemy
            })
        if action.item_id:
            features['item_id'] = action.item_id
        return features

    def _encode_action_type(self, action_type: str) -> int:
        """Convert action type to numeric encoding"""
        action_types = {
            'move': 0,
            'attack': 1,
            'rescue': 2,
            'item': 3
        }
        return action_types.get(action_type, -1)

    def _get_min_enemy_distance(self, unit: Unit, only_visible: bool = True) -> float:
        """Get minimum distance to any enemy (optionally only visible)"""
        min_dist = float('inf')
        for enemy in self.enemies:
            if enemy.is_alive and (enemy.is_visible or not only_visible):
                dist = self._get_distance(unit.position, enemy.position)
                min_dist = min(min_dist, dist)
        return min_dist if min_dist != float('inf') else 0

    def _get_min_ally_distance(self, unit: Unit) -> float:
        """Get minimum distance to any ally"""
        min_dist = float('inf')
        for ally in self.units:
            if ally.is_alive and ally != unit:
                dist = self._get_distance(unit.position, ally.position)
                min_dist = min(min_dist, dist)
        return min_dist if min_dist != float('inf') else 0

    def _get_distance(self, pos1: tuple, pos2: tuple) -> float:
        """Calculate Manhattan distance between two positions"""
        return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])

    def _get_terrain_cost(self, position: tuple) -> int:
        """Get terrain cost for a position"""
        terrain = self.terrain_map.get_terrain_at(position[0], position[1])
        if terrain in ['F', '^']:  # Forest, Hill
            return 2
        elif terrain in ['~', 'M']:  # Water, Mountain
            return 3
        return 1

    def _calculate_threat_level(self, action: Action) -> float:
        """Calculate threat level for an action's target position"""
        threat = 0.0
        for enemy in self.enemies:
            if enemy.is_visible and enemy.is_alive:
                dist = self._get_distance(action.target_position, enemy.position)
                if dist <= 2:  # Consider enemies within 2 tiles
                    threat += (1 / (dist + 1)) * (enemy.hp[0] / enemy.hp[1])
        return threat

    def _estimate_potential_damage(self, action: Action) -> float:
        """Estimate potential damage for an attack action"""
        if action.action_type != 'attack' or not action.target_unit:
            return 0.0

        # Simple damage estimation based on strength and defense
        attacker_str = action.unit.stats[0]  # Strength
        defender_def = action.target_unit.stats[4]  # Defense
        return max(0, attacker_str - defender_def)

    def _evaluate_position_value(self, position: tuple) -> float:
        """Evaluate the strategic value of a position"""
        value = 0.0

        # Check for terrain advantages
        terrain = self.terrain_map.get_terrain_at(position[0], position[1])
        if terrain in ['^', 'F']:  # Hill, Forest provide defensive bonuses
            value += 0.5

        # Check proximity to objectives (simplified)
        # TODO: Add actual objective evaluation
        return value