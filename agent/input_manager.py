#!/usr/bin/env python3

import time
import threading
import queue
from typing import Dict, List, Tuple, Optional, Callable, Any
from dataclasses import dataclass
import subprocess
import os

# Import the BizHawk controller module
from agent.bizhawk_controller import focus_bizhawk, press_key, press_keys

@dataclass
class InputCommand:
    """Represents a command to send to BizHawk"""
    command_type: str  # 'key_press', 'cursor_move', 'sequence', 'wait', etc.
    params: Dict[str, Any] = None
    callback: Callable = None  # Optional callback when command completes

class InputManager:
    """
    Manages input sending to BizHawk

    Runs in a dedicated thread to handle input commands asynchronously,
    allowing the main AI logic to continue without waiting for inputs.
    """

    # GBA key mappings for BizHawk
    GBA_KEY_MAP = {
        'A': 'A',
        'B': 'B',
        'L': 'L',
        'R': 'R',
        'START': 'START',
        'SELECT': 'SELECT',
        'UP': 'UP',
        'DOWN': 'DOWN',
        'LEFT': 'LEFT',
        'RIGHT': 'RIGHT'
    }

    def __init__(self, input_method: str = 'lua'):
        """
        Initialize the input manager

        Args:
            input_method: Method to use for sending inputs ('lua' or 'keyboard')
        """
        self.input_method = input_method
        self.input_file = os.path.join('data', 'emblemmind_input.txt')

        # Thread control
        self._running = False
        self._thread = None
        self._command_queue = queue.Queue()

        # Status tracking
        self._last_command = None
        self._last_cursor_pos = None
        self._cursor_validity_time = 0

        # Last time we focused the BizHawk window
        self._last_focus_time = 0

    def start(self):
        """Start the input manager thread"""
        if self._thread and self._thread.is_alive():
            return  # Already running

        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

        # Focus BizHawk when starting
        print("[InputManager] Focusing BizHawk window")
        focus_bizhawk()
        self._last_focus_time = time.time()

    def stop(self):
        """Stop the input manager thread"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)

    def _run(self):
        """Main thread loop - processes commands from the queue"""
        while self._running:
            try:
                # Get next command with a 0.1s timeout
                command = self._command_queue.get(timeout=0.1)

                # Process the command
                self._execute_command(command)

                # Mark command as done
                self._command_queue.task_done()

            except queue.Empty:
                # No commands in queue, just continue
                pass
            except Exception as e:
                print(f"[InputManager] Error processing command: {e}")

    def _execute_command(self, command: InputCommand):
        """Execute a single input command"""
        params = command.params or {}

        # Ensure BizHawk is focused before executing non-arrow key commands
        # Arrow keys use the lua script and don't need focus
        if command.command_type != 'wait':
            key = params.get('key', '')
            need_focus = key not in ['UP', 'DOWN', 'LEFT', 'RIGHT']

            if need_focus and time.time() - self._last_focus_time > 5.0:
                print("[InputManager] Refocusing BizHawk window")
                focus_bizhawk()
                self._last_focus_time = time.time()
                time.sleep(0.2)  # Small delay after focusing

        try:
            if command.command_type == 'key_press':
                self._press_key(
                    key=params.get('key'),
                    duration=params.get('duration', 0.05)
                )
            elif command.command_type == 'cursor_move':
                self._move_cursor_to(
                    target_pos=params.get('target_pos'),
                    current_pos=params.get('current_pos'),
                    max_attempts=params.get('max_attempts', 3)
                )
            elif command.command_type == 'sequence':
                self._execute_sequence(params.get('commands', []))
            elif command.command_type == 'wait':
                time.sleep(params.get('duration', 0.1))
            elif command.command_type == 'reset':
                self._press_reset()
            elif command.command_type == 'focus':
                self._focus_bizhawk()

            # Execute callback if provided
            if command.callback:
                command.callback()

        except Exception as e:
            print(f"[InputManager] Command execution error: {e}")

    def _press_key(self, key: str, duration: float = 0.05):
        """Press a key on the emulator"""
        if not key:
            return

        key = key.upper()
        # if key not in self.GBA_KEY_MAP:
        #     print(f"[InputManager] Unknown key: {key}")
        #     return

        # Use the bizhawk_controller's press_key function which handles both types of input
        print(f"[InputManager] Pressing key: {key}")
        press_key(key, duration)

    def _move_cursor_to(self, target_pos: Tuple[int, int], current_pos: Tuple[int, int] = None, max_attempts: int = 3):
        """Move the cursor to a target position"""
        if not target_pos:
            return

        # Use cached position if available and current_pos not provided
        if current_pos is None and self._last_cursor_pos is not None:
            # Only use cached position if recent (within 1 second)
            if time.time() - self._cursor_validity_time < 1.0:
                current_pos = self._last_cursor_pos

        # Still no current_pos, use target_pos as fallback
        if current_pos is None:
            current_pos = target_pos

        print(f"[InputManager] Moving cursor from {current_pos} to {target_pos}")

        # Try multiple attempts if needed
        for attempt in range(max_attempts):
            # Calculate direction and distance
            dx = target_pos[0] - current_pos[0]
            dy = target_pos[1] - current_pos[1]

            # Press horizontal direction keys
            for _ in range(abs(dx)):
                dir_key = 'RIGHT' if dx > 0 else 'LEFT'
                press_key(dir_key, 0.05)
                time.sleep(0.05)

            # Press vertical direction keys
            for _ in range(abs(dy)):
                dir_key = 'DOWN' if dy > 0 else 'UP'
                press_key(dir_key, 0.05)
                time.sleep(0.05)

            # Update cached position
            self._last_cursor_pos = target_pos
            self._cursor_validity_time = time.time()

            # Success, no need for further attempts
            return

    def _execute_sequence(self, commands: List[Dict]):
        """Execute a sequence of commands"""
        for cmd in commands:
            cmd_type = cmd.get('type')
            params = cmd.get('params', {})

            if cmd_type == 'key_press':
                self._press_key(params.get('key'), params.get('duration', 0.05))
            elif cmd_type == 'wait':
                time.sleep(params.get('duration', 0.1))

    def _press_reset(self):
        """Press reset in BizHawk"""
        # Use the bizhawk_controller function
        press_key('RESET')

    def _focus_bizhawk(self):
        """Focus the BizHawk window"""
        # Use the imported function
        focus_bizhawk()
        self._last_focus_time = time.time()

    # --- Public API ---

    def queue_command(self, command: InputCommand):
        """Add a command to the queue"""
        self._command_queue.put(command)

    def press_key(self, key: str, duration: float = 0.05, callback: Callable = None):
        """Queue a key press command"""
        command = InputCommand(
            command_type='key_press',
            params={'key': key, 'duration': duration},
            callback=callback
        )
        self.queue_command(command)

    def move_cursor(self, target_pos: Tuple[int, int], current_pos: Tuple[int, int] = None, callback: Callable = None):
        """Queue a cursor movement command"""
        command = InputCommand(
            command_type='cursor_move',
            params={'target_pos': target_pos, 'current_pos': current_pos},
            callback=callback
        )
        self.queue_command(command)

    def wait(self, duration: float, callback: Callable = None):
        """Queue a wait command"""
        command = InputCommand(
            command_type='wait',
            params={'duration': duration},
            callback=callback
        )
        self.queue_command(command)

    def execute_sequence(self, sequence_name: str, callback: Callable = None):
        """Queue a predefined input sequence"""
        # Predefined sequences for common actions
        sequences = {
            'end_turn': [
                {'type': 'key_press', 'params': {'key': 'A'}},  # Select unit
                {'type': 'wait', 'params': {'duration': 0.1}},
                {'type': 'key_press', 'params': {'key': 'UP'}},  # Select "End"
                {'type': 'wait', 'params': {'duration': 0.1}},
                {'type': 'key_press', 'params': {'key': 'A'}}   # Confirm
            ],
            'attack_confirm': [
                {'type': 'key_press', 'params': {'key': 'A'}},  # Select Attack
                {'type': 'wait', 'params': {'duration': 0.1}},
                {'type': 'key_press', 'params': {'key': 'A'}},  # Select Weapon
                {'type': 'wait', 'params': {'duration': 0.1}},
                {'type': 'key_press', 'params': {'key': 'A'}}   # Confirm
            ],
            'return_to_map': [
                {'type': 'key_press', 'params': {'key': 'B'}},
                {'type': 'wait', 'params': {'duration': 0.05}},
                {'type': 'key_press', 'params': {'key': 'B'}},
                {'type': 'wait', 'params': {'duration': 0.05}},
                {'type': 'key_press', 'params': {'key': 'B'}},
                {'type': 'wait', 'params': {'duration': 0.05}},
                {'type': 'key_press', 'params': {'key': 'B'}},
                {'type': 'wait', 'params': {'duration': 0.05}},
                {'type': 'key_press', 'params': {'key': 'B'}}
            ]
        }

        if sequence_name in sequences:
            command = InputCommand(
                command_type='sequence',
                params={'commands': sequences[sequence_name]},
                callback=callback
            )
            self.queue_command(command)
        else:
            print(f"[InputManager] Unknown sequence: {sequence_name}")

    def clear_queue(self):
        """Clear the command queue"""
        while not self._command_queue.empty():
            try:
                self._command_queue.get_nowait()
                self._command_queue.task_done()
            except queue.Empty:
                break

    def wait_until_queue_empty(self, timeout: float = None):
        """Wait until all commands in the queue are processed"""
        self._command_queue.join(timeout=timeout)