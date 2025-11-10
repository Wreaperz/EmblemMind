#!/usr/bin/env python3

import time
import threading
import queue
from typing import Dict, List, Tuple, Optional, Callable, Any

# Local imports
from agent.data_manager import DataManager, GameState
from agent.input_manager import InputManager, InputCommand
from agent.action_generator import Action
from agent.brain import Brain
from agent.bizhawk_controller import focus_bizhawk  # Import the focus function

class ActionExecutor:
    """
    Executes actions selected by the Brain through the InputManager

    Handles the coordination between the Brain's decisions and the InputManager's
    commands, ensuring proper synchronization and feedback of results.
    """

    def __init__(self, brain: Brain, data_manager: DataManager, input_manager: InputManager):
        """
        Initialize the action executor

        Args:
            brain: Brain instance for getting actions
            data_manager: DataManager instance for getting game state
            input_manager: InputManager instance for controlling the game
        """
        self.brain = brain
        self.data_manager = data_manager
        self.input_manager = input_manager

        # State tracking
        self.current_action = None
        self.pre_action_state = None
        self.action_in_progress = False
        self.last_cursor_pos = (0, 0)

        # Thread control
        self._running = False
        self._thread = None

    def start(self):
        """Start the action executor thread"""
        if self._thread and self._thread.is_alive():
            return  # Already running

        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the action executor thread"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)

    def _run(self):
        """Main thread loop - retrieves and executes actions"""
        execution_interval = 0.2  # Check for new actions every 0.2 seconds

        while self._running:
            try:
                # Skip if already executing an action
                if self.action_in_progress:
                    time.sleep(0.1)
                    continue

                # Get current state
                state = self.data_manager.get_current_state()
                if not state:
                    time.sleep(0.1)
                    continue

                # Only proceed if player phase (0x00)
                if state.snapshot.turn_phase != 0x00:
                    time.sleep(0.1)
                    continue

                # Get next action from brain
                action_info = self.brain.get_next_action(timeout=0.1)
                if not action_info:
                    time.sleep(execution_interval)
                    continue

                # Process the action
                action_type, action_data = action_info

                if action_type == 'action':
                    # Execute a regular action
                    action, old_state = action_data
                    self._execute_action(action, old_state)

                elif action_type == 'end_turn':
                    # Execute end turn command
                    self._end_turn()

                # Wait a bit before checking for next action
                time.sleep(execution_interval)

            except Exception as e:
                print(f"[ActionExecutor] Error in main loop: {e}")
                time.sleep(0.1)

    def _execute_action(self, action: Action, state: GameState):
        """Execute a specific action"""
        if not action or not state:
            return

        print(f"[ActionExecutor] Executing {action.action_type} action for unit {action.unit.name}")

        # First ensure BizHawk window is focused
        print("[ActionExecutor] Focusing BizHawk window")
        focus_bizhawk()

        # Mark that we're executing an action
        self.action_in_progress = True
        self.pre_action_state = state
        self.current_action = action

        # Store current cursor position for later use
        cursor_pos = state.snapshot.cursor_position
        self.last_cursor_pos = cursor_pos if cursor_pos else self.last_cursor_pos

        # Set brain's action_in_progress to prevent it from selecting new actions
        self.brain.action_in_progress = True

        # Define callback for when the action completes
        def on_action_complete():
            try:
                # Get state after action
                post_state = self.data_manager.get_current_state()

                # Calculate reward
                reward = self._calculate_reward(self.pre_action_state, post_state, action)

                # Report outcome to brain
                self.brain.report_action_outcome(action, self.pre_action_state, post_state, reward)

                # Reset action state
                self.action_in_progress = False
                self.current_action = None
                self.pre_action_state = None
                self.brain.action_in_progress = False
            except Exception as e:
                print(f"[ActionExecutor] Error in action completion callback: {e}")
                self.action_in_progress = False
                self.brain.action_in_progress = False

        try:
            # Different execution based on action type
            if action.action_type == 'move':
                self._execute_move_action(action, on_action_complete)
            elif action.action_type == 'attack':
                self._execute_attack_action(action, on_action_complete)
            elif action.action_type == 'item':
                self._execute_item_action(action, on_action_complete)
            elif action.action_type == 'wait':
                self._execute_wait_action(action, on_action_complete)
            elif action.action_type == 'rescue':
                self._execute_rescue_action(action, on_action_complete)
            else:
                print(f"[ActionExecutor] Unknown action type: {action.action_type}")
                on_action_complete()  # Still call callback to reset state
        except Exception as e:
            print(f"[ActionExecutor] Error executing action: {e}")
            self.action_in_progress = False
            self.brain.action_in_progress = False

    def _execute_move_action(self, action: Action, callback: Callable):
        """Execute a move action"""
        # Sequence:
        # 1. Move cursor to unit
        # 2. Press A to select unit
        # 3. Move cursor to target position
        # 4. Press A to confirm move
        # 5. Press B to select "Wait"

        # Store positions for convenience
        unit_pos = action.unit.position
        target_pos = action.target_position

        # Get current cursor position
        cursor_pos = self.last_cursor_pos

        # Define the command sequence
        commands = []

        # 1. Move cursor to unit
        commands.append(
            InputCommand(
                command_type='cursor_move',
                params={'target_pos': unit_pos, 'current_pos': cursor_pos}
            )
        )

        # 2. Select unit
        commands.append(
            InputCommand(
                command_type='key_press',
                params={'key': 'A', 'duration': 0.05}
            )
        )

        # Wait a moment for menu to appear
        commands.append(
            InputCommand(
                command_type='wait',
                params={'duration': 0.2}
            )
        )

        # 3. Move cursor to target position
        commands.append(
            InputCommand(
                command_type='cursor_move',
                params={'target_pos': target_pos, 'current_pos': unit_pos}
            )
        )

        # 4. Confirm move
        commands.append(
            InputCommand(
                command_type='key_press',
                params={'key': 'A', 'duration': 0.05}
            )
        )

        # Wait a moment for menu to appear
        commands.append(
            InputCommand(
                command_type='wait',
                params={'duration': 0.2}
            )
        )

        # 5. Select "Wait"
        commands.append(
            InputCommand(
                command_type='key_press',
                params={'key': 'A', 'duration': 0.05}
            )
        )

        # Define callback for the final command
        commands[-1].callback = callback

        # Queue all commands
        for cmd in commands:
            self.input_manager.queue_command(cmd)

        # Update last cursor position
        self.last_cursor_pos = target_pos

    def _execute_attack_action(self, action: Action, callback: Callable):
        """Execute an attack action"""
        # Sequence:
        # 1. Move cursor to unit
        # 2. Press A to select unit
        # 3. If target position is different from unit position, move cursor and press A
        # 4. Move cursor to "Attack" in menu and press A
        # 5. Move cursor to enemy and press A
        # 6. If weapon selection needed, select weapon and press A
        # 7. Wait for battle to complete

        # Store positions for convenience
        unit_pos = action.unit.position
        target_pos = action.target_position
        enemy_pos = action.target_unit.position

        # Get current cursor position
        cursor_pos = self.last_cursor_pos

        # Define the command sequence
        commands = []

        # 1. Move cursor to unit
        commands.append(
            InputCommand(
                command_type='cursor_move',
                params={'target_pos': unit_pos, 'current_pos': cursor_pos}
            )
        )

        # 2. Select unit
        commands.append(
            InputCommand(
                command_type='key_press',
                params={'key': 'A', 'duration': 0.05}
            )
        )

        # Wait a moment for menu to appear
        commands.append(
            InputCommand(
                command_type='wait',
                params={'duration': 0.2}
            )
        )

        # 3. If moving before attacking, move to target position
        if target_pos != unit_pos:
            commands.append(
                InputCommand(
                    command_type='cursor_move',
                    params={'target_pos': target_pos, 'current_pos': unit_pos}
                )
            )

            commands.append(
                InputCommand(
                    command_type='key_press',
                    params={'key': 'A', 'duration': 0.05}
                )
            )

            # Wait a moment for menu to appear
            commands.append(
                InputCommand(
                    command_type='wait',
                    params={'duration': 0.2}
                )
            )

        # 4. Select "Attack" from menu (usually first option, so no need to move cursor)
        commands.append(
            InputCommand(
                command_type='key_press',
                params={'key': 'A', 'duration': 0.05}
            )
        )

        # Wait a moment for attack range to appear
        commands.append(
            InputCommand(
                command_type='wait',
                params={'duration': 0.2}
            )
        )

        # 5. Move cursor to enemy and select
        current_pos = target_pos
        commands.append(
            InputCommand(
                command_type='cursor_move',
                params={'target_pos': enemy_pos, 'current_pos': current_pos}
            )
        )

        commands.append(
            InputCommand(
                command_type='key_press',
                params={'key': 'A', 'duration': 0.05}
            )
        )

        # If a specific weapon was selected, navigate to it
        # Since weapon selection is complex and varies, use a predefined sequence
        if action.item_id:
            # TODO: Implement weapon selection logic based on item_id
            # For now, just press A to select the first weapon
            commands.append(
                InputCommand(
                    command_type='wait',
                    params={'duration': 0.2}
                )
            )

            commands.append(
                InputCommand(
                    command_type='key_press',
                    params={'key': 'A', 'duration': 0.05}
                )
            )

        # Add a long wait for battle animation to complete
        commands.append(
            InputCommand(
                command_type='wait',
                params={'duration': 5.0}  # Adjust based on actual battle animation duration
            )
        )

        # Define callback for the final command to wait for stable state
        def battle_complete_check():
            # Check if battle has completed by waiting for stable state
            post_state = self.data_manager.wait_for_animation_complete(timeout=10.0)

            # Now call the original callback
            callback()

        # Assign the custom callback to the last command
        commands[-1].callback = battle_complete_check

        # Queue all commands
        for cmd in commands:
            self.input_manager.queue_command(cmd)

        # Update last cursor position
        self.last_cursor_pos = enemy_pos

    def _execute_item_action(self, action: Action, callback: Callable):
        """Execute an item usage action"""
        # Sequence:
        # 1. Move cursor to unit
        # 2. Press A to select unit
        # 3. Select "Item" from menu
        # 4. Select specific item
        # 5. Confirm item use

        # Store positions for convenience
        unit_pos = action.unit.position

        # Get current cursor position
        cursor_pos = self.last_cursor_pos

        # Define the command sequence
        commands = []

        # 1. Move cursor to unit
        commands.append(
            InputCommand(
                command_type='cursor_move',
                params={'target_pos': unit_pos, 'current_pos': cursor_pos}
            )
        )

        # 2. Select unit
        commands.append(
            InputCommand(
                command_type='key_press',
                params={'key': 'A', 'duration': 0.05}
            )
        )

        # Wait a moment for menu to appear
        commands.append(
            InputCommand(
                command_type='wait',
                params={'duration': 0.2}
            )
        )

        # 3. Navigate to "Item" in menu (usually need to press DOWN once)
        commands.append(
            InputCommand(
                command_type='key_press',
                params={'key': 'DOWN', 'duration': 0.05}
            )
        )

        commands.append(
            InputCommand(
                command_type='key_press',
                params={'key': 'A', 'duration': 0.05}
            )
        )

        # Wait a moment for item menu to appear
        commands.append(
            InputCommand(
                command_type='wait',
                params={'duration': 0.2}
            )
        )

        # 4. Select the specific item if provided
        if action.item_id:
            # Find the item's position in the inventory
            item_index = -1
            for i, (item_id, _) in enumerate(action.unit.items):
                if item_id == action.item_id:
                    item_index = i
                    break

            if item_index >= 0:
                # Navigate to the item (press DOWN 'item_index' times)
                for _ in range(item_index):
                    commands.append(
                        InputCommand(
                            command_type='key_press',
                            params={'key': 'DOWN', 'duration': 0.05}
                        )
                    )

                    commands.append(
                        InputCommand(
                            command_type='wait',
                            params={'duration': 0.05}
                        )
                    )

        # 5. Select the item
        commands.append(
            InputCommand(
                command_type='key_press',
                params={'key': 'A', 'duration': 0.05}
            )
        )

        # Wait a moment for item use animation
        commands.append(
            InputCommand(
                command_type='wait',
                params={'duration': 1.0}
            )
        )

        # Select "Use" option for the item
        commands.append(
            InputCommand(
                command_type='key_press',
                params={'key': 'A', 'duration': 0.05}
            )
        )

        # Wait for the item use to complete
        commands.append(
            InputCommand(
                command_type='wait',
                params={'duration': 2.0}
            )
        )

        # Define callback for the final command
        commands[-1].callback = callback

        # Queue all commands
        for cmd in commands:
            self.input_manager.queue_command(cmd)

        # Update last cursor position
        self.last_cursor_pos = unit_pos

    def _execute_wait_action(self, action: Action, callback: Callable):
        """Execute a wait action"""
        # Sequence:
        # 1. Move cursor to unit
        # 2. Press A to select unit
        # 3. Press B to select "Wait"

        # Store positions for convenience
        unit_pos = action.unit.position

        # Get current cursor position
        cursor_pos = self.last_cursor_pos

        # Define the command sequence
        commands = []

        # 1. Move cursor to unit
        commands.append(
            InputCommand(
                command_type='cursor_move',
                params={'target_pos': unit_pos, 'current_pos': cursor_pos}
            )
        )

        # 2. Select unit
        commands.append(
            InputCommand(
                command_type='key_press',
                params={'key': 'A', 'duration': 0.05}
            )
        )

        # Wait a moment for menu to appear
        commands.append(
            InputCommand(
                command_type='wait',
                params={'duration': 0.2}
            )
        )

        # 3. Press B to select "Wait"
        commands.append(
            InputCommand(
                command_type='key_press',
                params={'key': 'B', 'duration': 0.05}
            )
        )

        # Wait a moment for action to complete
        commands.append(
            InputCommand(
                command_type='wait',
                params={'duration': 0.5}
            )
        )

        # Define callback for the final command
        commands[-1].callback = callback

        # Queue all commands
        for cmd in commands:
            self.input_manager.queue_command(cmd)

        # Update last cursor position
        self.last_cursor_pos = unit_pos

    def _execute_rescue_action(self, action: Action, callback: Callable):
        """Execute a rescue action"""
        # Similar to attack but selecting "Rescue" instead
        # Implementation depends on specific game mechanics

        # For now, just call the callback directly
        callback()

    def _end_turn(self):
        """Execute the end turn command"""
        # Mark that we're executing an action
        self.action_in_progress = True

        # Set brain's action_in_progress to prevent it from selecting new actions
        self.brain.action_in_progress = True

        # Define callback for when the end turn completes
        def on_end_turn_complete():
            # Wait for turn phase to change
            self.data_manager.wait_for_state_change(
                self.data_manager.get_current_state().snapshot,
                timeout=5.0
            )

            # Reset action state
            self.action_in_progress = False
            self.brain.action_in_progress = False

        # Get current state
        state = self.data_manager.get_current_state()
        if not state:
            self.action_in_progress = False
            self.brain.action_in_progress = False
            return

        # Get current cursor position
        cursor_pos = state.snapshot.cursor_position
        self.last_cursor_pos = cursor_pos if cursor_pos else self.last_cursor_pos

        # Find a unit that has already moved
        moved_unit = None
        for unit in state.snapshot.units:
            if unit.turn_status == 0x02:  # "Moved" status
                moved_unit = unit
                break

        if not moved_unit:
            print("[ActionExecutor] End turn requested but no moved units found")
            self.action_in_progress = False
            self.brain.action_in_progress = False
            return

        # Define the command sequence
        commands = []

        # 1. Move cursor to moved unit
        commands.append(
            InputCommand(
                command_type='cursor_move',
                params={'target_pos': moved_unit.position, 'current_pos': self.last_cursor_pos}
            )
        )

        # 2. Select moved unit
        commands.append(
            InputCommand(
                command_type='key_press',
                params={'key': 'A', 'duration': 0.05}
            )
        )

        # Wait a moment for menu to appear
        commands.append(
            InputCommand(
                command_type='wait',
                params={'duration': 0.2}
            )
        )

        # 3. Select "End" from menu (usually need to press UP)
        commands.append(
            InputCommand(
                command_type='key_press',
                params={'key': 'UP', 'duration': 0.05}
            )
        )

        commands.append(
            InputCommand(
                command_type='key_press',
                params={'key': 'A', 'duration': 0.05}
            )
        )

        # 4. Wait for end turn to complete
        commands.append(
            InputCommand(
                command_type='wait',
                params={'duration': 2.0}
            )
        )

        # Define callback for the final command
        commands[-1].callback = on_end_turn_complete

        # Queue all commands
        for cmd in commands:
            self.input_manager.queue_command(cmd)

        # Update last cursor position
        self.last_cursor_pos = moved_unit.position

    def _calculate_reward(self, pre_state: GameState, post_state: GameState, action: Action) -> float:
        """Calculate reward for an action based on state changes"""
        if not pre_state or not post_state:
            return 0.0

        # Start with a base cost for taking any action
        reward = -1.0

        # Check for enemy defeats
        pre_enemies = {e.id: e for e in pre_state.snapshot.enemies if e.is_alive}
        post_enemies = {e.id: e for e in post_state.snapshot.enemies if e.is_alive}

        # Reward for defeating enemies
        for enemy_id, enemy in pre_enemies.items():
            if enemy_id not in post_enemies:
                # Enemy was defeated
                reward += 50.0  # Big reward for kill
            elif enemy_id in post_enemies:
                # Enemy still alive, check for damage
                pre_hp = enemy.hp[0]
                post_hp = post_enemies[enemy_id].hp[0]
                damage = max(0, pre_hp - post_hp)
                reward += damage * 2.0  # Points per damage point

        # Penalty for losing units
        pre_units = {u.id: u for u in pre_state.snapshot.units if u.is_alive}
        post_units = {u.id: u for u in post_state.snapshot.units if u.is_alive}

        for unit_id, unit in pre_units.items():
            if unit_id not in post_units:
                # Unit was lost
                reward -= 100.0  # Big penalty for unit loss
            elif unit_id in post_units:
                # Unit alive, check for damage
                pre_hp = unit.hp[0]
                post_hp = post_units[unit_id].hp[0]
                damage_taken = max(0, pre_hp - post_hp)
                reward -= damage_taken * 2.0  # Penalty per damage point

                # Bonus for healing
                healing = max(0, post_hp - pre_hp)
                reward += healing * 1.5  # Points per healing point

        # Specific action type rewards
        if action.action_type == 'attack':
            # Small bonus for attacking (encouraging offensive play)
            reward += 2.0

            # Terrain bonus
            terrain = pre_state.snapshot.map.get_terrain_at(*action.target_position)
            if terrain in ['F', '^']:  # Forest or Hill
                reward += 1.0  # Small bonus for attacking from advantageous terrain

        elif action.action_type == 'move':
            # Terrain bonus
            terrain = post_state.snapshot.map.get_terrain_at(*action.target_position)
            if terrain in ['F', '^', '0C', '0D']:  # Good terrain types
                reward += 1.0  # Small bonus for moving to advantageous terrain

        elif action.action_type == 'item':
            # Item use rewards handled by healing detection above
            pass

        return reward