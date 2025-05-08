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

    def simulate_action(self, action: Action) -> Tuple[TurnSnapshot, float]:
        """Simulate the outcome of an action and return the new state and reward"""
        # TODO: Implement state simulation
        # This would involve:
        # 1. Creating a copy of the current state
        # 2. Applying the action
        # 3. Simulating enemy responses
        # 4. Calculating the reward
        pass