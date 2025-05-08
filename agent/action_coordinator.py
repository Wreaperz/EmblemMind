from typing import List, Tuple, Optional
from emblemmind_snapshot import TurnSnapshot
from agent.action_generator import ActionGenerator, Action
from agent.state_evaluator import StateEvaluator
from agent.neural_network import NeuralNetworkInterface

class ActionCoordinator:
    """Coordinates action generation, evaluation, and neural network processing"""

    def __init__(self, snapshot: TurnSnapshot):
        self.snapshot = snapshot
        self.action_generator = ActionGenerator(snapshot)
        self.state_evaluator = StateEvaluator(snapshot)
        self.neural_network = NeuralNetworkInterface()

    def get_best_actions(self, num_actions: int = 5) -> List[Action]:
        """Get the best actions according to the neural network"""
        # Generate all possible actions
        actions = self.action_generator.generate_all_actions()

        if not actions:
            return []

        # Evaluate each action
        features = [self.state_evaluator.evaluate_action(action) for action in actions]

        # Get neural network scores
        scores = self.neural_network.evaluate_actions(actions, features)

        # Sort actions by score and return top N
        sorted_actions = sorted(zip(actions, scores), key=lambda x: x[1], reverse=True)
        return [action for action, _ in sorted_actions[:num_actions]]

    def train_on_experience(self,
                          actions: List[Action],
                          outcomes: List[float],
                          batch_size: int = 32):
        """Train the neural network on a batch of experiences"""
        # Evaluate actions to get features
        features = [self.state_evaluator.evaluate_action(action) for action in actions]

        # Train in batches
        for i in range(0, len(features), batch_size):
            batch_features = features[i:i+batch_size]
            batch_outcomes = outcomes[i:i+batch_size]

            loss = self.neural_network.train(batch_features, batch_outcomes)
            print(f"Training batch {i//batch_size + 1}, Loss: {loss:.4f}")

    def save_model(self, path: str):
        """Save the neural network model"""
        self.neural_network.save_model(path)

    def load_model(self, path: str):
        """Load a neural network model"""
        self.neural_network.load_model(path)

    def get_action_features(self, action: Action) -> dict:
        """Get the feature vector for a specific action"""
        return self.state_evaluator.evaluate_action(action)

    def evaluate_state(self) -> float:
        """Evaluate the current game state"""
        return self.state_evaluator.evaluate_state()

    def simulate_action(self, snapshot: TurnSnapshot, action: Action) -> Tuple[TurnSnapshot, float]:
        """
        Simulate the outcome of an action and return the new state and reward.
        Handles 'move' and 'attack' actions differently:
        - 'move': moves the unit to the target position.
        - 'attack': does not move the unit, but simulates an attack on the target unit if in range.
        """
        import copy
        new_snapshot = copy.deepcopy(snapshot)
        reward = -1  # Default action cost

        if action.action_type == 'move':
            # Move the unit to the target position
            for unit in new_snapshot.units:
                if unit.id == action.unit.id:
                    unit.position = action.target_position
                    unit.turn_status = 0x42  # Mark as acted
                    break
            terrain = new_snapshot.map.get_terrain_at(action.target_position[0], action.target_position[1])
            if terrain in ['F', '^']:
                reward += 10
            elif terrain == '#':
                reward -= 10

        elif action.action_type == 'attack' and action.target_unit is not None:
            # Find the acting unit and the target enemy in the new snapshot
            acting_unit = None
            target_enemy = None
            for unit in new_snapshot.units:
                if unit.id == action.unit.id:
                    acting_unit = unit
                    break
            for enemy in new_snapshot.enemies:
                if enemy.id == action.target_unit.id:
                    target_enemy = enemy
                    break
            if acting_unit is not None and target_enemy is not None:
                # Check if the enemy is in range for the selected weapon
                from utils.fe_data_mappings import ITEM_ATTACK_RANGES
                item_id = action.item_id
                if item_id in ITEM_ATTACK_RANGES:
                    min_range, max_range = ITEM_ATTACK_RANGES[item_id]
                    dist = abs(target_enemy.position[0] - acting_unit.position[0]) + abs(target_enemy.position[1] - acting_unit.position[1])
                    if min_range <= dist <= max_range:
                        # Simulate damage (simple: strength - defense)
                        attacker_str = acting_unit.stats[0] if len(acting_unit.stats) > 0 else 0
                        defender_def = target_enemy.stats[4] if len(target_enemy.stats) > 4 else 0
                        damage = max(0, attacker_str - defender_def)
                        target_enemy.hp = (max(0, target_enemy.hp[0] - damage), target_enemy.hp[1])
                        acting_unit.turn_status = 0x42  # Mark as acted
                        # Reward for defeating an enemy
                        if target_enemy.hp[0] == 0:
                            reward += 50  # Defeating an enemy is highly rewarded
                        else:
                            reward += damage  # Reward for damage dealt
                        # TODO: Add more realistic combat (weapon triangle, crit, counterattack, etc.)
        else:
            # For other action types, fallback to old logic (move to target position)
            for unit in new_snapshot.units:
                if unit.id == action.unit.id:
                    unit.position = action.target_position
                    unit.turn_status = 0x42  # Mark as acted
                    break
            terrain = new_snapshot.map.get_terrain_at(action.target_position[0], action.target_position[1])
            if terrain in ['F', '^']:
                reward += 10
            elif terrain == '#':
                reward -= 10

        return new_snapshot, reward