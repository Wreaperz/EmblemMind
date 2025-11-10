#!/usr/bin/env python3

import os
import time
import threading
import queue
from typing import Dict, List, Tuple, Optional, Any
from collections import deque
import random
import torch

# Local imports
from agent.data_manager import GameState, DataManager
from agent.action_generator import ActionGenerator, Action
from agent.state_evaluator import StateEvaluator
from agent.neural_network import NeuralNetworkInterface

class Brain:
    """
    The main AI decision-making component

    Continuously evaluates game states and decides on the best actions
    to take. Operates independently from data gathering and input execution.
    """

    def __init__(self, data_manager: DataManager, model_path: str = None):
        """
        Initialize the brain

        Args:
            data_manager: DataManager instance for getting game state
            model_path: Path to saved neural network model (optional)
        """
        self.data_manager = data_manager
        self.model_path = model_path

        # States
        self.last_state = None
        self.current_action = None
        self.action_in_progress = False

        # Neural network components
        self.neural_network = NeuralNetworkInterface()
        if model_path and os.path.exists(model_path):
            self.neural_network.load_model(model_path)

        # Reinforcement learning parameters
        self.epsilon = 1.0  # Exploration rate
        self.epsilon_min = 0.1
        self.epsilon_decay = 0.995
        self.replay_buffer = deque(maxlen=1000)
        self.gamma = 0.95  # Discount factor

        # Thread control
        self._running = False
        self._thread = None
        self._action_queue = queue.Queue()
        self._reward_queue = queue.Queue()

    def start(self):
        """Start the brain thread"""
        if self._thread and self._thread.is_alive():
            return  # Already running

        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the brain thread"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)

    def _run(self):
        """Main thread loop - continuously evaluates game states and decides actions"""
        evaluation_interval = 0.5  # Evaluate state every 0.5 seconds
        last_evaluation = 0

        while self._running:
            try:
                now = time.time()

                # Check if it's time to evaluate the state
                if now - last_evaluation >= evaluation_interval:
                    # Only evaluate if we're not in the middle of an action
                    if not self.action_in_progress:
                        self._evaluate_current_state()
                    last_evaluation = now

                # Process any rewards from actions
                self._process_rewards()

                # Short sleep to avoid CPU spinning
                time.sleep(0.05)

            except Exception as e:
                print(f"[Brain] Error in main loop: {e}")
                time.sleep(0.1)

    def _evaluate_current_state(self):
        """Evaluate the current game state and decide on an action"""
        # Get the current game state
        state = self.data_manager.get_current_state()
        if not state:
            return

        # Only proceed if player phase (0x00)
        if state.snapshot.turn_phase != 0x00:
            return

        # Check if any units can act
        available_units = state.snapshot.get_available_units()
        if not available_units:
            # No units can act, suggest ending turn
            self._action_queue.put(('end_turn', None))
            return

        # Generate possible actions
        action_generator = ActionGenerator(state.snapshot)
        actions = action_generator.generate_all_actions()

        # Filter actions based on movement and range maps if available
        if state.movement_map and state.range_map:
            actions = self._filter_actions(actions, state.snapshot, state.movement_map, state.range_map)

        if not actions:
            return

        # Evaluate actions
        state_evaluator = StateEvaluator(state.snapshot)
        action_features = [state_evaluator.evaluate_action(action) for action in actions]

        # Choose action: epsilon-greedy policy
        if random.random() < self.epsilon:
            # Exploration: random action
            selected_action = random.choice(actions)
            selected_action.score = 0  # Random actions have 0 score
        else:
            # Exploitation: use neural network to score actions
            scores = self.neural_network.evaluate_actions(actions, action_features)

            # Associate scores with actions
            for action, score in zip(actions, scores):
                action.score = score

            # Select highest scoring action
            selected_action = max(actions, key=lambda a: a.score)

        # Add action to queue with the current state for later reward calculation
        self._action_queue.put(('action', (selected_action, state)))

        # Update exploration rate
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

    def _filter_actions(self, actions, snapshot, movement_map, range_map):
        """Filter out impossible or invalid actions based on movement/range maps"""
        width = len(movement_map[0]) if movement_map and movement_map[0] else 0
        height = len(movement_map) if movement_map else 0

        filtered_actions = []
        for action in actions:
            # Skip actions for units that can't act
            if not action.unit.can_act:
                continue

            # For move actions, check if the position is in movement range
            if action.action_type == 'move':
                x, y = action.target_position
                if 0 <= x < width and 0 <= y < height:
                    if movement_map[y][x] != 0xFF:  # 0xFF means not in movement range
                        filtered_actions.append(action)

            # For attack actions, ensure target is in weapon range after movement
            elif action.action_type == 'attack':
                # If moving to a position, check that first
                if action.target_position != action.unit.position:
                    x, y = action.target_position
                    if not (0 <= x < width and 0 <= y < height) or movement_map[y][x] == 0xFF:
                        continue

                # Check that target is in range from the position
                filtered_actions.append(action)

            # For other actions, add them by default
            else:
                filtered_actions.append(action)

        return filtered_actions

    def _process_rewards(self):
        """Process any rewards in the queue and update neural network"""
        # Process up to 10 rewards at a time
        for _ in range(10):
            try:
                reward_data = self._reward_queue.get_nowait()
                self._process_reward(reward_data)
                self._reward_queue.task_done()
            except queue.Empty:
                break

    def _process_reward(self, reward_data):
        """Process a single reward entry"""
        action, old_state, new_state, reward = reward_data

        # Add to replay buffer
        self.replay_buffer.append((action, old_state, new_state, reward))

        # Train on a batch if we have enough samples
        if len(self.replay_buffer) >= 32:
            self._train_on_batch()

    def _train_on_batch(self, batch_size=32):
        """Train the neural network on a batch of experiences"""
        if len(self.replay_buffer) < batch_size:
            return

        # Sample random batch
        batch = random.sample(self.replay_buffer, batch_size)

        # Prepare data for training
        actions = []
        targets = []

        for action, old_state, new_state, reward in batch:
            # Get features for this action
            state_evaluator = StateEvaluator(old_state.snapshot)
            features = state_evaluator.evaluate_action(action)

            # Calculate target Q-value
            if new_state:
                # Get best action from new state
                action_generator = ActionGenerator(new_state.snapshot)
                next_actions = action_generator.generate_all_actions()
                if next_actions:
                    next_features = [state_evaluator.evaluate_action(a) for a in next_actions]
                    next_q_values = self.neural_network.evaluate_actions(next_actions, next_features)
                    max_next_q = max(next_q_values) if next_q_values else 0
                    target = reward + self.gamma * max_next_q
                else:
                    target = reward
            else:
                # Terminal state
                target = reward

            actions.append(features)
            targets.append(target)

        # Train neural network
        self.neural_network.train(actions, targets)

        # Save model periodically
        if self.model_path:
            self.neural_network.save_model(self.model_path)

    # --- Public API ---

    def get_next_action(self, timeout: float = 0.5) -> Tuple[str, Any]:
        """
        Get the next action from the queue

        Returns:
            Tuple[str, Any]: Action type and data ('action', 'end_turn', etc.)
        """
        try:
            return self._action_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def report_action_outcome(self, action: Action, old_state: GameState, new_state: GameState, reward: float):
        """
        Report the outcome of an action for reinforcement learning

        Args:
            action: The action that was taken
            old_state: State before the action
            new_state: State after the action
            reward: Reward received for the action
        """
        self._reward_queue.put((action, old_state, new_state, reward))

    def simulate_action(self, action: Action, state: GameState) -> Tuple[float, Dict[str, Any]]:
        """
        Simulate the outcome of an action

        Args:
            action: The action to simulate
            state: Current game state

        Returns:
            Tuple[float, Dict]: Expected reward and updated state information
        """
        # Create a state evaluator for the current state
        state_evaluator = StateEvaluator(state.snapshot)

        # Start with a base reward of -1 (cost of taking any action)
        reward = -1.0

        # Action-specific simulation
        if action.action_type == 'attack':
            # Estimate damage to enemy
            expected_damage = state_evaluator._estimate_potential_damage(action)
            reward += expected_damage * 2  # 2 points per damage point

            # Bonus for potentially killing an enemy
            target_hp = action.target_unit.hp[0]
            if expected_damage >= target_hp:
                reward += 50  # Big bonus for kill

            # Check for terrain advantage
            terrain = state.snapshot.map.get_terrain_at(*action.target_position)
            if terrain in ['F', '^']:  # Forest or Hill
                reward += 5  # Bonus for attacking from advantageous terrain

        elif action.action_type == 'move':
            # Check terrain at destination
            terrain = state.snapshot.map.get_terrain_at(*action.target_position)
            if terrain in ['F', '^', '0C', '0D']:  # Good terrain types
                reward += 5  # Bonus for moving to advantageous terrain

            # Check if moving closer to enemies (generally good)
            current_min_dist = min([
                abs(action.unit.position[0] - e.position[0]) + abs(action.unit.position[1] - e.position[1])
                for e in state.snapshot.enemies if e.is_alive and e.is_visible
            ], default=float('inf'))

            new_min_dist = min([
                abs(action.target_position[0] - e.position[0]) + abs(action.target_position[1] - e.position[1])
                for e in state.snapshot.enemies if e.is_alive and e.is_visible
            ], default=float('inf'))

            if new_min_dist < current_min_dist:
                reward += 2  # Bonus for moving closer to enemies

        elif action.action_type == 'item':
            # Reward based on item type
            if action.item_id:
                # Basic estimate for healing items
                reward += 5  # Base reward for using items

        # Return expected reward and any additional info
        return reward, {'expected_damage': expected_damage if action.action_type == 'attack' else 0}