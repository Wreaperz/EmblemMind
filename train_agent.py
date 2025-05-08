#!/usr/bin/env python3

import os
import time
from emblemmind_snapshot import TurnSnapshot
from agent.action_coordinator import ActionCoordinator

def main():
    # Set up file paths
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(current_dir, 'data')
    state_file_path = os.path.join(data_dir, 'fe_state.txt')
    map_file_path = os.path.join(data_dir, 'fe_map.txt')

    # Check if files exist
    if not os.path.exists(state_file_path):
        print(f"Error: State file not found at {state_file_path}")
        return
    if not os.path.exists(map_file_path):
        print(f"Error: Map file not found at {map_file_path}")
        return

    # Load the current game state
    snapshot = TurnSnapshot.from_files(state_file_path, map_file_path)
    coordinator = ActionCoordinator(snapshot)

    # Get the best actions (top 5)
    best_actions = coordinator.get_best_actions(num_actions=5)

    print("\nTop 5 Actions:")
    for i, action in enumerate(best_actions, 1):
        desc = f"{action.unit.name} ({'Enemy' if action.unit.is_enemy else 'Player'}) " \
               f"{action.action_type} to {action.target_position}"
        if action.target_unit:
            desc += f" (target: {action.target_unit.name})"
        print(f"{i}. {desc} | Score: {action.score:.3f}")

    # (Optional) Train on these actions using the state evaluator as a proxy for reward
    # For demonstration, we'll use the state evaluation after the action as the reward
    actions = []
    outcomes = []
    for action in best_actions:
        # Simulate the action (not implemented yet)
        # For now, use the current state evaluation as a dummy reward
        reward = coordinator.evaluate_state()
        actions.append(action)
        outcomes.append(reward)

    # Train the neural network
    if actions:
        print("\nTraining neural network on top actions...")
        coordinator.train_on_experience(actions, outcomes)
        print("Training complete.")
    else:
        print("No actions to train on.")

if __name__ == "__main__":
    main()