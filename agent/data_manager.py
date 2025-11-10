#!/usr/bin/env python3

import os
import time
import threading
import queue
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# Local imports
from emblemmind_snapshot import TurnSnapshot

@dataclass
class GameState:
    """Container for the current game state data"""
    snapshot: TurnSnapshot
    movement_map: List[List[int]] = None
    range_map: List[List[int]] = None
    battle_data: Dict = None
    timestamp: float = None

class DataManager:
    """
    Manages game data reading and processing

    Runs in a dedicated thread to continuously poll game state from BizHawk
    via fe_state.txt and fe_map.txt files.
    """

    def __init__(self, data_dir: str, poll_interval: float = 0.1):
        """
        Initialize the data manager

        Args:
            data_dir: Directory containing state files (fe_state.txt, fe_map.txt)
            poll_interval: Time between polling attempts in seconds
        """
        self.data_dir = data_dir
        self.state_file = os.path.join(data_dir, 'fe_state.txt')
        self.map_file = os.path.join(data_dir, 'fe_map.txt')
        self.poll_interval = poll_interval

        # Thread control
        self._running = False
        self._thread = None
        self._lock = threading.RLock()

        # Data storage
        self._current_state = None
        self._state_queue = queue.Queue(maxsize=5)  # Limited queue to avoid memory issues
        self._cached_states = {}  # Cache for specific state queries (key: query_type, value: (state, timestamp))

    def start(self):
        """Start the data manager thread"""
        if self._thread and self._thread.is_alive():
            return  # Already running

        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the data manager thread"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)

    def _run(self):
        """Main thread loop - continuously polls game state"""
        last_movement_poll = 0
        last_battle_poll = 0
        movement_poll_interval = 1.0  # Poll movement maps every 1 second
        battle_poll_interval = 0.5    # Poll battle data every 0.5 seconds

        while self._running:
            try:
                # Always fetch basic snapshot
                snapshot = self._get_snapshot()

                if snapshot:
                    now = time.time()

                    # Decide if we need to poll additional data
                    should_poll_movement = (now - last_movement_poll) >= movement_poll_interval
                    should_poll_battle = (now - last_battle_poll) >= battle_poll_interval

                    # Create state container
                    state = GameState(snapshot=snapshot, timestamp=now)

                    # Get movement and range maps periodically
                    if should_poll_movement:
                        state.movement_map = self._parse_map_section("MOVEMENT_MAP")
                        state.range_map = self._parse_map_section("RANGE_MAP")
                        last_movement_poll = now

                    # Get battle data periodically
                    if should_poll_battle:
                        state.battle_data = {
                            'attacker': self._parse_battle_struct('attacker'),
                            'defender': self._parse_battle_struct('defender')
                        }
                        last_battle_poll = now

                    # Update current state with lock protection
                    with self._lock:
                        self._current_state = state

                    # Add to queue (non-blocking)
                    try:
                        self._state_queue.put_nowait(state)
                    except queue.Full:
                        # Queue full, remove oldest item and try again
                        try:
                            self._state_queue.get_nowait()
                            self._state_queue.put_nowait(state)
                        except:
                            pass

            except Exception as e:
                print(f"[DataManager] Error polling game state: {e}")

            # Sleep before next poll
            time.sleep(self.poll_interval)

    def _get_snapshot(self) -> Optional[TurnSnapshot]:
        """Get a snapshot of the current game state"""
        try:
            return TurnSnapshot.from_files(self.state_file, self.map_file)
        except Exception as e:
            return None

    def _parse_map_section(self, section_name: str) -> Optional[List[List[int]]]:
        """Parse a named section from fe_state.txt (MOVEMENT_MAP or RANGE_MAP)"""
        try:
            return TurnSnapshot.parse_map_section(self.state_file, section_name)
        except Exception:
            return None

    def _parse_battle_struct(self, struct_type: str) -> Optional[Dict]:
        """Parse battle struct data from fe_state.txt"""
        try:
            return TurnSnapshot.parse_battle_struct(self.state_file, struct=struct_type)
        except Exception:
            return None

    def get_current_state(self) -> Optional[GameState]:
        """Get the most recent game state (thread-safe)"""
        with self._lock:
            return self._current_state

    def get_next_state(self, timeout: float = 0.5) -> Optional[GameState]:
        """Get the next state from the queue (blocks until timeout)"""
        try:
            return self._state_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def wait_for_state_change(self, prev_snapshot, timeout: float = 3.0) -> Optional[GameState]:
        """
        Wait for the state to change from the previous snapshot

        Args:
            prev_snapshot: Previous snapshot to compare against
            timeout: Maximum time to wait in seconds

        Returns:
            GameState object if state changed, None if timeout
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            state = self.get_current_state()
            if not state:
                time.sleep(0.1)
                continue

            # Check if turn or phase has changed
            if (state.snapshot.current_turn != prev_snapshot.current_turn or
                state.snapshot.turn_phase != prev_snapshot.turn_phase):
                return state

            time.sleep(0.1)

        # Return the latest state even if it didn't change
        return self.get_current_state()

    def wait_for_animation_complete(self, timeout: float = 5.0, stable_checks: int = 5) -> Optional[GameState]:
        """
        Wait for battle animations to complete by checking for stable state

        Args:
            timeout: Maximum time to wait in seconds
            stable_checks: Number of consecutive stable checks required

        Returns:
            GameState object when stable, None if timeout
        """
        start_time = time.time()
        stable_count = 0
        last_state = None

        while time.time() - start_time < timeout:
            state = self.get_current_state()
            if not state:
                time.sleep(0.1)
                continue

            # Compare with last state
            if last_state:
                # Check if units and positions are stable
                current_units = {(u.id, u.position, u.hp[0]) for u in state.snapshot.units}
                current_enemies = {(e.id, e.position, e.hp[0]) for e in state.snapshot.enemies}

                prev_units = {(u.id, u.position, u.hp[0]) for u in last_state.snapshot.units}
                prev_enemies = {(e.id, e.position, e.hp[0]) for e in last_state.snapshot.enemies}

                if current_units == prev_units and current_enemies == prev_enemies:
                    stable_count += 1
                else:
                    stable_count = 0

            last_state = state

            # Return if we have enough stable checks
            if stable_count >= stable_checks:
                return state

            time.sleep(0.1)

        # Return the latest state even if it's not stable
        return self.get_current_state()

    def get_realtime_data(self) -> Dict:
        """Get realtime cursor data from fe_state.txt"""
        try:
            return TurnSnapshot.parse_realtime_data_from_state_file(self.state_file)
        except Exception as e:
            return {
                'cursor_rt_x': None,
                'cursor_rt_y': None,
                'move_dest_x': None,
                'move_dest_y': None,
                'deployment_id': None
            }