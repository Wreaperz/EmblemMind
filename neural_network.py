import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from typing import List, Dict
from agent.action_generator import Action

class ActionEvaluator(nn.Module):
    """Neural network for evaluating actions"""

    def __init__(self, input_size: int = 10):
        super(ActionEvaluator, self).__init__()

        # Define the network architecture
        self.network = nn.Sequential(
            nn.Linear(input_size, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 1)
        )

        # Initialize weights
        self._init_weights()

    def _init_weights(self):
        """Initialize network weights"""
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                nn.init.zeros_(m.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass through the network"""
        return self.network(x)

class NeuralNetworkInterface:
    """Interface between the game and the neural network"""

    def __init__(self):
        self.model = ActionEvaluator()
        self.optimizer = optim.Adam(self.model.parameters(), lr=0.001)
        self.criterion = nn.MSELoss()

    def evaluate_actions(self, actions: List[Action], features: List[Dict]) -> List[float]:
        """Evaluate a list of actions using the neural network"""
        # Convert features to tensor
        feature_tensor = self._features_to_tensor(features)

        # Get predictions
        with torch.no_grad():
            scores = self.model(feature_tensor)

        # Update action scores
        for action, score in zip(actions, scores):
            action.score = score.item()

        return [score.item() for score in scores]

    def train(self, features: List[Dict], targets: List[float]):
        """Train the neural network on a batch of data"""
        # Convert to tensors
        feature_tensor = self._features_to_tensor(features)
        target_tensor = torch.tensor(targets, dtype=torch.float32).view(-1, 1)

        # Forward pass
        self.optimizer.zero_grad()
        outputs = self.model(feature_tensor)
        loss = self.criterion(outputs, target_tensor)

        # Backward pass and optimize
        loss.backward()
        self.optimizer.step()

        return loss.item()

    def _features_to_tensor(self, features: List[Dict]) -> torch.Tensor:
        """Convert feature dictionaries to a tensor"""
        # Extract and normalize features
        feature_list = []
        for feat in features:
            # Basic features
            feature_vector = [
                feat['action_type'] / 3.0,  # Normalize to [0,1]
                feat['unit_health'],
                feat['target_distance'] / 10.0,  # Normalize assuming max distance of 10
                feat['terrain_cost'] / 3.0,  # Normalize to [0,1]
                feat['threat_level'],
                feat['potential_damage'] / 20.0,  # Normalize assuming max damage of 20
                feat['position_value']
            ]

            # Optional features
            if 'target_health' in feat:
                feature_vector.extend([
                    feat['target_health'],
                    float(feat['target_is_enemy'])
                ])
            else:
                feature_vector.extend([0.0, 0.0])

            if 'item_id' in feat:
                feature_vector.append(feat['item_id'] / 1000.0)  # Normalize item ID
            else:
                feature_vector.append(0.0)

            feature_list.append(feature_vector)

        return torch.tensor(feature_list, dtype=torch.float32)

    def save_model(self, path: str):
        """Save the model to a file"""
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict()
        }, path)

    def load_model(self, path: str):
        """Load the model from a file"""
        checkpoint = torch.load(path)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])