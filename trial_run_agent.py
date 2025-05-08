#!/usr/bin/env python3

import os
import time
import random
from collections import deque
from emblemmind_snapshot import TurnSnapshot
from agent.action_coordinator import ActionCoordinator
from agent.action_generator import Action
from agent.bizhawk_controller import press_key, press_reset, GBA_KEY_MAP, focus_bizhawk
from utils.fe_data_mappings import ITEM_ATTACK_RANGES

# Paths
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
STATE_FILE = os.path.join(DATA_DIR, 'fe_state.txt')
MAP_FILE = os.path.join(DATA_DIR, 'fe_map.txt')

# RL parameters
EPSILON_START = 1.0
EPSILON_END = 0.1
EPSILON_DECAY = 500  # Number of episodes to decay over
REPLAY_BUFFER_SIZE = 1000
BATCH_SIZE = 32
replay_buffer = deque(maxlen=REPLAY_BUFFER_SIZE)
SIMULATION_MODE = False  # Set to True to use fast simulation for RL, False for real BizHawk

# --- Utility: Identify good terrain tiles by symbol ---
GOOD_TERRAIN_SYMBOLS = {'F', '^', '0C', '0D', '11', '0A', '0B', '1F', 'C', 'T'}  # Forest, Thicket, Hill, Fort, Gate, Throne, etc.
GOOD_TERRAIN_MIN_DEF = 1  # Minimum defense bonus to consider a tile 'good' (for struct-based fallback)
GOOD_TERRAIN_MAX_PROBES = 2  # Only probe up to this many 'good' tiles per enemy

# --- Helper Functions ---
def wait_for_state_update(prev_snapshot, timeout=3):
    """Wait for the state file to update (turn or phase change)."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            snapshot = TurnSnapshot.from_files(STATE_FILE, MAP_FILE)
        except Exception:
            time.sleep(0.1)
            continue
        if snapshot.current_turn != prev_snapshot.current_turn or snapshot.turn_phase != prev_snapshot.turn_phase:
            return snapshot
    return snapshot

def is_player_dead(snapshot):
    # Only return True if a critical character (Eliwood=0x01, Hector=0x02, Lyn=0x03) is dead
    CRITICAL_IDS = {0x01, 0x02, 0x03}
    for unit in snapshot.units:
        if unit.id in CRITICAL_IDS and unit.hp[0] == 0:
            return True
    return False

def is_level_beaten(snapshot):
    # Level is beaten if all enemies are dead and at least one enemy has hidden_status != 0x20 (not just item droppers left)
    return (not any(e.is_alive for e in snapshot.enemies)) and any(e.hidden_status != 0x20 for e in snapshot.enemies)

def find_empty_tile(snapshot):
    """Find a tile with no units on it (returns (x, y))."""
    for y in range(snapshot.map.height):
        for x in range(snapshot.map.width):
            if not snapshot.get_unit_at(x, y):
                return (x, y)
    # Fallback: top-left
    return (0, 0)

def end_turn_in_bizhawk(cursor_pos, snapshot):
    # Only block ending turn if the unit with id==1 (Eliwood) can still act or hasn't acted
    for unit in snapshot.units:
        if unit.id == 1 and (unit.can_act or not unit.has_acted):
            print(f"[END TURN BLOCKED] Eliwood (id=1) can still act (can_act={unit.can_act}, has_acted={unit.has_acted}, turn_status=0x{unit.turn_status:02X}).")
            return cursor_pos
    # Find a MOVED unit (turn_status == 0x02) to end turn on
    moved_unit = next((u for u in snapshot.units if u.turn_status == 0x02), None)
    if not moved_unit:
        print("[END TURN ERROR] No MOVED unit found to end turn on.")
        return cursor_pos
    cursor_pos = move_cursor_to(moved_unit.position, cursor_pos)
    time.sleep(0.1)
    press_key(GBA_KEY_MAP['A'], duration=0.05)  # Select MOVED unit
    time.sleep(0.1)
    press_key(GBA_KEY_MAP['UP'], duration=0.05)  # Move to 'End' in menu
    time.sleep(0.1)
    press_key(GBA_KEY_MAP['A'], duration=0.05)  # Confirm 'End'
    time.sleep(0.1)
    # Wait for enemy phase to start by detecting cursor movability
    for _ in range(100):  # Up to 10 seconds
        time.sleep(0.1)
        pos = get_cursor_position()
        if pos is not None:
            # Try moving cursor to see if it's movable (should not be during enemy phase)
            press_key(GBA_KEY_MAP['LEFT'], duration=0.05)
            time.sleep(0.1)
            new_pos = get_cursor_position()
            if new_pos != pos:
                print(f"[END TURN] Enemy phase started or ended, cursor is movable at {new_pos}.")
                break
    cursor_pos = get_cursor_position() or moved_unit.position
    return cursor_pos

def return_to_map():
    # Press 'B' several times to ensure we're back on the map
    for _ in range(5):
        press_key(GBA_KEY_MAP['B'], duration=0.01)  # 'B' button
    # After returning, check map state resumed
    x, y = get_cursor_xy_from_state(STATE_FILE)
    if x is None or y is None:
        print("[ERROR] Map state not resumed after return_to_map.")

def get_cursor_position():
    # Retry up to 3 times with 100ms delay to ensure cursor has settled
    for attempt in range(3):
        try:
            snapshot = TurnSnapshot.from_files(STATE_FILE, MAP_FILE)
            pos = snapshot.cursor_position
            if pos is not None:
                if attempt == 0:
                    last_pos = pos
                else:
                    if pos == last_pos:
                        return pos
                    last_pos = pos
            time.sleep(0.1)
        except Exception:
            time.sleep(0.1)
    return pos if 'pos' in locals() else None

def move_cursor_to(target_pos, current_pos, max_attempts=3):
    if current_pos is None:
        print(f"[CURSOR] Warning: current_pos is None, defaulting to target_pos {target_pos}")
        current_pos = target_pos
    print(f"[CURSOR] Moving from {current_pos} to {target_pos}")
    for attempt in range(max_attempts):
        dx = target_pos[0] - current_pos[0]
        dy = target_pos[1] - current_pos[1]
        for _ in range(abs(dx)):
            press_key(GBA_KEY_MAP['RIGHT'] if dx > 0 else GBA_KEY_MAP['LEFT'], duration=0.05)
        for _ in range(abs(dy)):
            press_key(GBA_KEY_MAP['DOWN'] if dy > 0 else GBA_KEY_MAP['UP'], duration=0.05)
        time.sleep(0.1)
        pos = get_cursor_position()
        print(f"[CURSOR] After move, at {pos}")
        if pos == target_pos:
            return target_pos
        print(f"[WARN] Cursor not at target after move (attempt {attempt+1})")
        return_to_map()
        current_pos = get_cursor_position() or current_pos
    print(f"[ERROR] Could not move cursor to {target_pos}, stuck at {current_pos}")
    return (0, 0) if current_pos is None else current_pos

def get_cursor_xy_from_state(state_file):
    """Reads cursor_x and cursor_y from fe_state.txt (not REALTIME_DATA, but main block)."""
    try:
        with open(state_file, 'r') as f:
            lines = f.readlines()
        x, y = None, None
        for line in lines:
            if line.startswith('cursor_x='):
                x = int(line.split('=', 1)[1])
            elif line.startswith('cursor_y='):
                y = int(line.split('=', 1)[1])
            if x is not None and y is not None:
                break
        return x, y
    except Exception as e:
        print(f"[ERROR] Failed to read cursor_x/y: {e}")
        return None, None

def is_menu_open_via_cursor(state_file, press_key_fn):
    """Press an arrow key and check if cursor_x/y change. If not, we're in a menu."""
    x1, y1 = get_cursor_xy_from_state(state_file)
    press_key_fn(GBA_KEY_MAP['RIGHT'], duration=0.01)
    x2, y2 = get_cursor_xy_from_state(state_file)
    # Optionally, press left to return cursor if it moved
    if x2 is not None and x1 is not None and x2 > x1:
        press_key_fn(GBA_KEY_MAP['LEFT'], duration=0.01)
    # If x/y didn't change, we're in a menu
    return (x1 == x2 and y1 == y2)

def is_menu_open():
    # Heuristic: if cursor position doesn't change after pressing 'B', likely in menu
    # pos1 = get_cursor_position()
    # press_key(GBA_KEY_MAP['B'], duration=0.01)
    # time.sleep(0.1)
    # pos2 = get_cursor_position()
    # return pos1 == pos2
    # Improved: use cursor_x/y logic
    return is_menu_open_via_cursor(STATE_FILE, press_key)

def wait_for_action_followthrough(prev_snapshot, check_fn, timeout=1.0):
    """Poll the state file every 50ms until check_fn returns True or timeout."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            snapshot = TurnSnapshot.from_files(STATE_FILE, MAP_FILE)
            if check_fn(snapshot):
                return snapshot
        except Exception:
            pass
        time.sleep(0.05)
    print('[WARN] Action follow-through timeout.')
    return prev_snapshot

def get_realtime_move_dest(state_file):
    """Reads move_dest_x and move_dest_y from REALTIME_DATA in fe_state.txt"""
    try:
        with open(state_file, 'r') as f:
            lines = f.readlines()
        in_realtime = False
        data = {}
        for line in lines:
            line = line.strip()
            if line == 'REALTIME_DATA':
                in_realtime = True
                continue
            if in_realtime:
                # Stop if we hit another section header (all uppercase, possibly with underscores, or starts with 'character=')
                if not line or (line.replace('_', '').isupper() and line.replace('_', '').isalpha()) or line.startswith('character='):
                    break
                if '=' in line:
                    k, v = line.split('=', 1)
                    try:
                        data[k] = int(v)
                    except ValueError:
                        continue
        return data.get('move_dest_x'), data.get('move_dest_y')
    except Exception as e:
        print(f"[ERROR] Failed to read REALTIME_DATA: {e}")
        return None, None

def confirm_move_possible(target_x, target_y, state_file, press_key_fn):
    time.sleep(0.1)
    press_key(GBA_KEY_MAP['B'], duration=0.01)
    time.sleep(0.05)
    press_key(GBA_KEY_MAP['B'], duration=0.01)
    time.sleep(0.05)
    move_dest_x, move_dest_y = get_realtime_move_dest(state_file)
    if move_dest_x is None or move_dest_y is None:
        return False
    return (move_dest_x == target_x and move_dest_y == target_y)

def discard_last_item_sequence():
    # Press DOWN 5 times to select the last item
    for _ in range(5):
        press_key(GBA_KEY_MAP['DOWN'], duration=0.05)
        time.sleep(0.05)
    # Press A to select the item
    press_key(GBA_KEY_MAP['A'], duration=0.05)
    time.sleep(0.05)
    # Press LEFT to select "discard"
    press_key(GBA_KEY_MAP['LEFT'], duration=0.05)
    time.sleep(0.05)
    # Press A to confirm discard
    press_key(GBA_KEY_MAP['A'], duration=0.05)
    time.sleep(0.5)  # Wait for the animation/game to update

def perform_attack_action(action, cursor_pos, probe=False):
    print(f"[ACTION] {action.unit.name} moving to {action.target_position} to ATTACK {action.target_unit.name if action.target_unit else ''}{' [PROBE]' if probe else ''}")
    # Move cursor to unit
    cursor_pos = move_cursor_to(action.unit.position, cursor_pos)
    pos_check = get_cursor_position()
    if pos_check != action.unit.position:
        print(f"[ERROR] Cursor not on expected unit {action.unit.name} at {action.unit.position}, but at {pos_check}. Attempting recovery.")
        return_to_map()
        cursor_pos = move_cursor_to(action.unit.position, cursor_pos)
        pos_check = get_cursor_position()
        if pos_check != action.unit.position:
            print(f"[FATAL] Still not on expected unit after recovery. Skipping action.")
            return cursor_pos if probe else (cursor_pos, None)
    # Select unit
    time.sleep(0.1)
    press_key(GBA_KEY_MAP['A'], duration=0.05)
    time.sleep(0.05)
    # Move cursor to target
    cursor_pos = move_cursor_to(action.target_position, cursor_pos)
    # Dynamic sleep based on distance moved (animation timing)
    dist = abs(action.unit.position[0] - action.target_position[0]) + abs(action.unit.position[1] - action.target_position[1])
    pos_check = get_cursor_position()
    if pos_check != action.target_position:
        print(f"[ERROR] Cursor not on expected target tile {action.target_position}, but at {pos_check}. Attempting recovery.")
        return_to_map()
        cursor_pos = move_cursor_to(action.target_position, cursor_pos)
        pos_check = get_cursor_position()
        if pos_check != action.target_position:
            print(f"[FATAL] Still not on expected target after recovery. Skipping action.")
            return cursor_pos if probe else (cursor_pos, None)
    # Confirm move
    press_key(GBA_KEY_MAP['A'], duration=0.05)
    time.sleep(0.2 + 0.15 * dist)
    # 1. Select 'Attack' (A)
    press_key(GBA_KEY_MAP['A'], duration=0.05)
    time.sleep(0.05)
    # 2. Select weapon (A)
    press_key(GBA_KEY_MAP['A'], duration=0.05)
    time.sleep(0.25)
    if probe:
        # Return to map (B x4)
        for _ in range(4):
            press_key(GBA_KEY_MAP['B'], duration=0.05)
            time.sleep(0.05)
        press_key(GBA_KEY_MAP['UP'])
        time.sleep(0.05)
        press_key(GBA_KEY_MAP['DOWN'])
        # Do NOT press the final A, just return the battle struct
        battle_struct = TurnSnapshot.parse_battle_struct(STATE_FILE, struct='attacker')
        cursor_pos = get_cursor_position() or cursor_pos
        return cursor_pos, battle_struct
    # 3. Confirm attack (A)
    press_key(GBA_KEY_MAP['A'], duration=0.05)
    time.sleep(0.1)
    print(f"[ACTION] {action.unit.name} initiated attack at {action.target_position}. Waiting for battle to finish...")
    # Wait for battle to finish: cursor becomes movable again
    for _ in range(100):  # Up to 10 seconds
        time.sleep(0.1)
        pos = get_cursor_position()
        if pos is not None:
            # Try moving cursor to see if it's movable
            press_key(GBA_KEY_MAP['LEFT'], duration=0.05)
            time.sleep(0.1)
            new_pos = get_cursor_position()
            if new_pos != pos:
                print(f"[ACTION] Battle finished, cursor is movable at {new_pos}.")
                break
    return get_cursor_position() or cursor_pos

def execute_action_in_bizhawk(action, cursor_pos, prev_snapshot):
    print(f"[ACTION] {action.unit.name} preparing to {action.action_type} at {action.target_position}")
    if action.action_type == 'attack':
        cursor_pos = perform_attack_action(action, cursor_pos)
    elif action.action_type == 'wait' or action.action_type == 'move':
        print(f"[ACTION] {action.unit.name} moving to {action.target_position} to {action.action_type.upper()}")
        cursor_pos = move_cursor_to(action.unit.position, cursor_pos)
        pos_check = get_cursor_position()
        if pos_check != action.unit.position:
            print(f"[ERROR] Cursor not on expected unit {action.unit.name} at {action.unit.position}, but at {pos_check}. Attempting recovery.")
            return_to_map()
            cursor_pos = move_cursor_to(action.unit.position, cursor_pos)
            pos_check = get_cursor_position()
            if pos_check != action.unit.position:
                print(f"[FATAL] Still not on expected unit after recovery. Skipping action.")
                return cursor_pos, prev_snapshot
        press_key(GBA_KEY_MAP['A'], duration=0.05)
        time.sleep(0.1)
        cursor_pos = move_cursor_to(action.target_position, cursor_pos)
        pos_check = get_cursor_position()
        if pos_check != action.target_position:
            print(f"[ERROR] Cursor not on expected target tile {action.target_position}, but at {pos_check}. Attempting recovery.")
            return_to_map()
            cursor_pos = move_cursor_to(action.target_position, cursor_pos)
            pos_check = get_cursor_position()
            if pos_check != action.target_position:
                print(f"[FATAL] Still not on expected target after recovery. Skipping action.")
                return cursor_pos, prev_snapshot
        press_key(GBA_KEY_MAP['A'], duration=0.05)  # Confirm move
        time.sleep(0.3)
        # Wait is always at the bottom, so just press up and A/x
        time.sleep(0.2)
        press_key(GBA_KEY_MAP['UP'])
        time.sleep(0.05)
        press_key(GBA_KEY_MAP['A'])
    else:
        print(f"[ACTION] {action.unit.name} performing {action.action_type} at {action.target_position}")
        # Implement other action types as needed
    # Confirm the action succeeded (e.g., unit moved or acted)
    def check_fn(snapshot):
        for u in snapshot.units:
            if u.id == action.unit.id and (u.position != action.unit.position or not u.can_act):
                return True
        return False
    snapshot = wait_for_action_followthrough(prev_snapshot, check_fn)
    snapshot = wait_for_animation_complete(snapshot, timeout=2.0, stable_checks=5)
    if is_menu_open():
        print("[RECOVERY] Menu open after action, returning to map.")
        return_to_map()
        cursor_pos = get_cursor_position() or cursor_pos
    print(f"[RESULT] {action.unit.name} {action.action_type} to {action.target_position}")
    cursor_pos = get_cursor_position() or cursor_pos
    return cursor_pos, snapshot

def log_state(snapshot):
    print(f"\n=== TURN {snapshot.current_turn} | PHASE: {snapshot.phase_text} ===")
    print(f"Alive Players: {sum(1 for u in snapshot.units if u.is_alive)} | Alive Enemies: {sum(1 for e in snapshot.enemies if e.is_alive)}")
    print("Units left to act:")
    for u in snapshot.get_available_units():
        if not u.has_acted and u.can_act:
            print(f"  - {u.name} at {u.position} HP: {u.hp[0]}/{u.hp[1]} Status: {u.turn_status_text}")

def compute_reward(prev_snapshot, curr_snapshot, action=None, level_beaten=False, player_dead=False):
    reward = 0
    prev_enemies = {e.id: e for e in prev_snapshot.enemies}
    curr_enemies = {e.id: e for e in curr_snapshot.enemies}
    prev_units = {u.id: u for u in prev_snapshot.units}
    curr_units = {u.id: u for u in curr_snapshot.units}
    # Enemy deaths
    killed_enemy = False
    for eid, prev_e in prev_enemies.items():
        if eid in curr_enemies and prev_e.is_alive and not curr_enemies[eid].is_alive:
            reward += 100
            killed_enemy = True
    # Player deaths
    for uid, prev_u in prev_units.items():
        if uid in curr_units and prev_u.is_alive and not curr_units[uid].is_alive:
            reward -= 100
    # Damage dealt/taken
    for eid, prev_e in prev_enemies.items():
        if eid in curr_enemies:
            reward += 10 * max(0, prev_e.hp[0] - curr_enemies[eid].hp[0])
    for uid, prev_u in prev_units.items():
        if uid in curr_units:
            reward -= 10 * max(0, prev_u.hp[0] - curr_units[uid].hp[0])
    # Terrain scoring for move actions
    if action is not None:
        if action.action_type == 'move':
            terrain = curr_snapshot.map.get_terrain_at(action.target_position[0], action.target_position[1])
            terrain_bonus = 0
            if terrain in ['F', '^']:
                terrain_bonus = 5
            elif terrain == '#':
                terrain_bonus = -10
            elif terrain in ['M']:
                terrain_bonus = -10
            elif terrain in ['0C', '0D', '11']:
                terrain_bonus = 5
            elif terrain in ['0A', '0B', '1F']:
                terrain_bonus = 10
            elif terrain in ['1A', '12']:
                terrain_bonus = -10
            reward += terrain_bonus
        elif action.action_type == 'attack':
            reward += 70
        elif action.action_type == 'item':
            reward += 2
        elif action.action_type == 'rescue':
            reward += 1
        elif action.action_type == 'wait':
            reward -= 2
    # Penalize idle 'wait' actions if low HP and in enemy range
    if action is not None and action.action_type == 'wait' and action.unit.hp[0] < action.unit.hp[1] * 0.3:
        for enemy in curr_snapshot.enemies:
            if enemy.is_alive and abs(action.unit.position[0] - enemy.position[0]) + abs(action.unit.position[1] - enemy.position[1]) <= 2:
                reward -= 10
                break
    # Penalize unproductive actions
    if action is not None and action.unit.position == action.target_position and not killed_enemy:
        reward -= 10
    # Penalty if unit's turn_status did not change to 0x42 after action
    if action is not None:
        unit_after = next((u for u in curr_snapshot.units if u.id == action.unit.id), None)
        if unit_after and unit_after.turn_status != 0x02:
            reward -= 20
    # Penalty for being unselectable or not deployed
    for unit in curr_snapshot.units:
        if hasattr(unit, 'turn_status'):
            if unit.turn_status & 0x02:
                reward -= 10
            if unit.turn_status & 0x08:
                reward -= 10
    if level_beaten:
        reward += 5000
    if player_dead:
        reward -= 5000
    return reward

def sample_experiences(buffer, batch_size):
    return random.sample(buffer, min(len(buffer), batch_size))

def train_neural_network(coordinator, buffer):
    if len(buffer) < BATCH_SIZE:
        return
    # Discard ineffective/broken actions
    filtered = [exp for exp in buffer if exp[0] != exp[3] or exp[2] != 0]
    if not filtered:
        print("[TRAIN] No effective experiences to train on.")
        return
    batch = sample_experiences(filtered, BATCH_SIZE)
    actions = [exp[1] for exp in batch]
    rewards = [exp[2] for exp in batch]
    coordinator.train_on_experience(actions, rewards)
    print(f"[TRAIN] Trained on {len(batch)} experiences.")

def wait_for_animation_complete(prev_snapshot, timeout=5.0, stable_checks=5):
    last_positions = []
    start = time.time()
    while time.time() - start < timeout:
        try:
            snapshot = TurnSnapshot.from_files(STATE_FILE, MAP_FILE)
            positions = [(u.id, u.position) for u in snapshot.units]
            last_positions.append(positions)
            if len(last_positions) > stable_checks:
                last_positions.pop(0)
                if all(p == last_positions[0] for p in last_positions):
                    return snapshot
        except Exception:
            pass
        time.sleep(0.3)
    return snapshot

def filter_actions(actions, snapshot=None, movement_map=None, range_map=None):
    # Exclude actions for dead, unselectable, not deployed, rescued, or invisible units
    filtered = []
    for a in actions:
        if not a.unit.is_alive:
            continue
        if hasattr(a.unit, 'turn_status'):
            if a.unit.turn_status in [0x09, 0x0D, 0x21, 0x81]:
                continue
            if a.unit.turn_status & 0x02:
                continue
            if a.unit.turn_status & 0x08:
                continue
        # Exclude move actions to occupied or unreachable tiles
        if a.action_type == 'move' and snapshot is not None and movement_map is not None:
            x, y = a.target_position
            if snapshot.get_unit_at(x, y):
                continue
            if y >= len(movement_map) or x >= len(movement_map[y]) or movement_map[y][x] == 0xFF:
                continue
        # Exclude attack actions out of range
        if a.action_type == 'attack' and snapshot is not None and range_map is not None:
            x, y = a.target_position
            if y >= len(range_map) or x >= len(range_map[y]) or range_map[y][x] == 0:
                continue
        filtered.append(a)
    # Prefer attacking if possible
    attack_actions = [a for a in filtered if a.action_type == 'attack']
    if attack_actions:
        return attack_actions
    move_actions = [a for a in filtered if a.action_type == 'move']
    if move_actions:
        return move_actions
    item_actions = [a for a in filtered if a.action_type == 'item']
    if item_actions:
        return item_actions
    rescue_actions = [a for a in filtered if a.action_type == 'rescue']
    if rescue_actions:
        return rescue_actions
    return filtered

def parse_map_section(section_name):
    with open(STATE_FILE, 'r') as f:
        lines = f.readlines()
    in_section = False
    grid = []
    for line in lines:
        line = line.strip()
        if line == section_name:
            in_section = True
            continue
        if in_section:
            if not line or (line.replace('_', '').isupper() and line.replace('_', '').isalpha()):
                break
            if not all(all(c in "0123456789ABCDEFabcdef" for c in b) for b in line.split()):
                break
            row = [int(b, 16) for b in line.split()]
            grid.append(row)
    return grid

# --- Survivability and Battle Struct Utilities ---
def enemy_can_attack_tile(enemy, x, y, snapshot):
    move_range = enemy.movement_range
    for item_id, uses in enemy.items:
        if uses > 0 and item_id in ITEM_ATTACK_RANGES:
            min_range, max_range = ITEM_ATTACK_RANGES[item_id]
            for dx in range(-move_range, move_range + 1):
                for dy in range(-move_range, move_range + 1):
                    ex, ey = enemy.position[0] + dx, enemy.position[1] + dy
                    if 0 <= ex < snapshot.map.width and 0 <= ey < snapshot.map.height:
                        if abs(dx) + abs(dy) <= move_range:
                            dist = abs(ex - x) + abs(ey - y)
                            if min_range <= dist <= max_range:
                                if not snapshot.get_unit_at(ex, ey):
                                    return True
    return False

def probe_battle_struct_for_attack(attacker, defender, target_tile, state_file, move_cursor_to, press_key, get_cursor_position):
    from agent.action_generator import Action
    action = Action(
        unit=attacker,
        action_type='attack',
        target_position=target_tile,
        target_unit=defender
    )
    cursor_pos = get_cursor_position()
    cursor_pos, battle_struct = perform_attack_action(action, cursor_pos, probe=True)
    return battle_struct

def score_tile_for_survivability(unit, x, y, snapshot, state_file, move_cursor_to, press_key, get_cursor_position):
    total_expected_damage = 0
    death_risk = 0
    for enemy in snapshot.enemies:
        if not enemy.is_alive or not enemy.is_visible:
            continue
        if enemy_can_attack_tile(enemy, x, y, snapshot):
            battle_struct = probe_battle_struct_for_attack(enemy, unit, (x, y), state_file, move_cursor_to, press_key, get_cursor_position)
            if battle_struct:
                predicted_damage = max(0, battle_struct['attack'] - unit.stats[4])
                total_expected_damage += predicted_damage
                if predicted_damage >= unit.hp[0]:
                    death_risk += 1
    terrain = snapshot.map.get_terrain_at(x, y)
    terrain_bonus = 0
    if terrain in ['F', '^']:
        terrain_bonus += 2
    return -10 * death_risk - total_expected_damage + terrain_bonus

def probe_all_weapons_battle_structs(attacker, defender, target_tile, state_file, move_cursor_to, press_key, get_cursor_position):
    from agent.action_generator import Action
    results = []
    for slot_idx, (item_id, uses) in enumerate(attacker.items):
        if uses > 0:
            action = Action(
                unit=attacker,
                action_type='attack',
                target_position=target_tile,
                target_unit=defender,
                item_id=item_id
            )
            cursor_pos = get_cursor_position()
            cursor_pos, battle_struct = perform_attack_action(action, cursor_pos, probe=True)
            if battle_struct is not None:
                results.append((battle_struct, item_id, slot_idx))
    return results

def trial_run():
    print("==== Fire Emblem Autonomous Agent Trial Run ====")
    global coordinator
    episode = 0
    while True:
        episode += 1
        epsilon = EPSILON_END + (EPSILON_START - EPSILON_END) * max(0, (EPSILON_DECAY - episode) / EPSILON_DECAY)
        print(f"\n[EPISODE {episode}] Resetting level... (epsilon={epsilon:.3f})")
        if not SIMULATION_MODE:
            press_reset()
            time.sleep(0.5)
        try:
            snapshot = TurnSnapshot.from_files(STATE_FILE, MAP_FILE)
        except Exception as e:
            print(f"Error loading state: {e}")
            time.sleep(0.1)
            continue
        done = False
        episode_experience = []
        while not done:
            log_state(snapshot)
            if is_player_dead(snapshot):
                print("A player unit has died. Resetting level.")
                break
            if is_level_beaten(snapshot):
                print("Level beaten! Agent succeeded.")
                done = True
                break
            if not SIMULATION_MODE and snapshot.phase_text != 'Player':
                print("Waiting for player phase...")
                snapshot = wait_for_state_update(snapshot)
                continue
            coordinator = ActionCoordinator(snapshot)
            cursor_pos = snapshot.cursor_position
            player_died = False
            # --- PROBE ALL ACTIONABLE UNITS ONCE ---
            # Build actionable_units/actions at the start of the phase
            actionable_units = []
            actionable_actions = []
            # Only probe units that have not acted and can act (exclude 'moved')
            initial_units = [u for u in snapshot.get_available_units() if not u.has_acted and u.can_act]
            unit_positions = {u.id: u.position for u in initial_units}
            unit_statuses = {u.id: u.turn_status for u in initial_units}
            for unit in initial_units:
                print(f"[DEBUG] Probing unit: {unit.name} at {unit.position}, can_act={unit.can_act}, has_acted={unit.has_acted}")
                print(f"[DEBUG] {unit.name} items: {unit.items}")
                cursor_pos = move_cursor_to(unit.position, cursor_pos)
                pos_check = get_cursor_position()
                if pos_check != unit.position:
                    print(f"[ERROR] Cursor not on expected unit {unit.name} at {unit.position}, but at {pos_check}. Skipping unit.")
                    continue
                press_key(GBA_KEY_MAP['A'], duration=0.05)
                time.sleep(0.05)
                press_key(GBA_KEY_MAP['UP'], duration=0.05)
                time.sleep(0.05)
                press_key(GBA_KEY_MAP['DOWN'], duration=0.05)
                time.sleep(0.05)
                movement_map = parse_map_section('MOVEMENT_MAP')
                range_map = parse_map_section('RANGE_MAP')
                actions = coordinator.action_generator._generate_unit_actions(unit, movement_map, range_map)
                non_wait_actions = [a for a in actions if not (a.action_type == 'wait' and a.target_position == unit.position)]
                filtered_actions = filter_actions(non_wait_actions, snapshot, movement_map, range_map)
                print(f"[DEBUG] Filtered actions for {unit.name}: {[a.action_type for a in filtered_actions]}")
                if filtered_actions:
                    actionable_units.append(unit)
                    actionable_actions.append(filtered_actions)
                return_to_map()
                cursor_pos = get_cursor_position() or cursor_pos
                time.sleep(0.1)
            # --- MAIN ACTION LOOP ---
            # Maintain internal enemy list for this turn
            internal_enemies = [e for e in snapshot.enemies if e.is_alive and e.is_visible]
            # --- NEW: Check if all actionable units have no attack actions ---
            all_no_attack = True
            for actions in actionable_actions:
                if any(a.action_type == 'attack' for a in actions):
                    all_no_attack = False
                    break
            if all_no_attack:
                print("[INFO] No attack actions available for any unit. Ending player turn.")
                if not SIMULATION_MODE:
                    cursor_pos = end_turn_in_bizhawk(cursor_pos, snapshot)
                    cursor_pos = get_cursor_position() or cursor_pos
                    print("Waiting for enemy phase to complete...")
                    snapshot = wait_for_state_update(snapshot)
                else:
                    done = True
                break
            while actionable_units:
                # Prioritize attack units first
                attack_first_units = []
                attack_first_actions = []
                other_units = []
                other_actions = []
                for unit, actions in zip(actionable_units, actionable_actions):
                    # Filter out attack actions on already-defeated enemies
                    filtered_actions = []
                    for a in actions:
                        if a.action_type == 'attack' and a.target_unit is not None:
                            if not any(e.id == a.target_unit.id for e in internal_enemies):
                                continue  # Target already dead
                        filtered_actions.append(a)
                    if any(a.action_type == 'attack' for a in filtered_actions):
                        attack_first_units.append(unit)
                        attack_first_actions.append(filtered_actions)
                    else:
                        other_units.append(unit)
                        other_actions.append(filtered_actions)
                acted = False
                # Use attack-first, then others
                for idx, (unit, actions) in enumerate(list(zip(attack_first_units + other_units, attack_first_actions + other_actions))):
                    print(f"[DEBUG] Acting with unit: {unit.name}")
                    attack_actions = [a for a in actions if a.action_type == 'attack']
                    if attack_actions:
                        print(f"[DEBUG] {unit.name} has {len(attack_actions)} attack actions available.")
                        scored_attacks = []
                        probed_pairs = set()
                        for a in attack_actions:
                            # Deduplicate by (target_position, target_unit.id)
                            probe_key = (a.target_position, a.target_unit.id if a.target_unit else None)
                            if probe_key in probed_pairs:
                                continue
                            probed_pairs.add(probe_key)
                            # Pre-filter: Only probe 'good' tiles if there are few, else probe all
                            candidate_tiles = []
                            for aa in attack_actions:
                                if is_good_terrain(snapshot, aa.target_position[0], aa.target_position[1]):
                                    candidate_tiles.append(aa)
                            if 0 < len(candidate_tiles) <= GOOD_TERRAIN_MAX_PROBES:
                                # Only probe good tiles
                                if not is_good_terrain(snapshot, a.target_position[0], a.target_position[1]):
                                    continue  # Skip bad tiles
                            # Probe all weapons for this attack action
                            weapon_results = probe_all_weapons_battle_structs(unit, a.target_unit, a.target_position, STATE_FILE, move_cursor_to, press_key, get_cursor_position)
                            for battle_struct, item_id, slot_idx in weapon_results:
                                if battle_struct:
                                    will_kill = battle_struct['attack'] >= a.target_unit.hp[0] or battle_struct.get('cur_hp', 1) <= 0
                                    will_die = battle_struct['cur_hp'] <= 0 or battle_struct['attack'] >= unit.hp[0]
                                    score = 0
                                    # --- Use actual terrain defense/avoid/resistance from battle struct ---
                                    terrain_def = battle_struct.get('terrain_def', 0)
                                    terrain_avo = battle_struct.get('terrain_avo', 0)
                                    terrain_res = battle_struct.get('terrain_res', 0)
                                    terrain_bonus = 0
                                    if terrain_def > 0 or terrain_avo > 0 or terrain_res > 0:
                                        # Prioritize tiles with any defensive bonus
                                        terrain_bonus = 10 + terrain_def * 2 + terrain_avo + terrain_res
                                    score += terrain_bonus
                                    # --- End terrain bonus ---
                                    if will_kill:
                                        score += 100
                                    if will_die:
                                        score -= 100
                                    score += battle_struct['attack']
                                    score += battle_struct['hit'] // 10
                                    score += battle_struct['crit'] // 10
                                    # Create a new action for this weapon
                                    weapon_action = Action(
                                        unit=a.unit,
                                        action_type=a.action_type,
                                        target_position=a.target_position,
                                        target_unit=a.target_unit,
                                        item_id=item_id
                                    )
                                    scored_attacks.append((score, weapon_action, will_kill))
                                else:
                                    scored_attacks.append((0, a, False))
                        if not scored_attacks:
                            print(f"[WARN] No valid attack actions for {unit.name}. Skipping unit.")
                            continue
                        scored_attacks.sort(reverse=True, key=lambda x: x[0])
                        chosen_action = scored_attacks[0][1]
                        chosen_will_kill = scored_attacks[0][2]
                    else:
                        print(f"[DEBUG] {unit.name} has {len(actions)} non-attack actions available.")
                        move_actions = [a for a in actions if a.action_type == 'move']
                        if move_actions:
                            scored_moves = []
                            for a in move_actions:
                                # Score by negative distance to nearest enemy
                                min_enemy_dist = float('inf')
                                for enemy in internal_enemies:
                                    dist = abs(a.target_position[0] - enemy.position[0]) + abs(a.target_position[1] - enemy.position[1])
                                    if dist < min_enemy_dist:
                                        min_enemy_dist = dist
                                # Prefer closer to enemy
                                score = -min_enemy_dist
                                scored_moves.append((score, a))
                            if not scored_moves:
                                print(f"[WARN] No valid move actions for {unit.name}. Skipping unit.")
                                continue
                            scored_moves.sort(reverse=True, key=lambda x: x[0])
                            chosen_action = scored_moves[0][1]
                        else:
                            if not actions:
                                print(f"[WARN] No available actions for {unit.name}. Skipping unit.")
                                continue
                            if random.random() < epsilon:
                                chosen_action = random.choice(actions)
                            else:
                                features = [coordinator.get_action_features(a) for a in actions]
                                scores = coordinator.neural_network.evaluate_actions(actions, features)
                                best_idx = max(range(len(scores)), key=lambda i: scores[i])
                                chosen_action = actions[best_idx]
                        chosen_will_kill = False
                    print(f"[DEBUG] Chosen action for {unit.name}: {chosen_action.action_type} to {chosen_action.target_position}")
                    prev_snapshot = snapshot
                    if SIMULATION_MODE:
                        snapshot, reward = coordinator.simulate_action(prev_snapshot, chosen_action)
                        for u in actionable_units:
                            if u.id == unit.id:
                                u.position = chosen_action.target_position
                                u.turn_status = 0x02  # Mark as acted
                        # Remove enemy if killed
                        if chosen_action.action_type == 'attack' and chosen_action.target_unit is not None and chosen_will_kill:
                            internal_enemies = [e for e in internal_enemies if e.id != chosen_action.target_unit.id]
                    else:
                        cursor_pos, snapshot = execute_action_in_bizhawk(chosen_action, cursor_pos, prev_snapshot)
                        reward = compute_reward(prev_snapshot, snapshot, chosen_action)
                        # --- Check if unit is marked as moved in new snapshot ---
                        acted_unit = next((u for u in snapshot.units if u.id == unit.id), None)
                        if acted_unit and acted_unit.turn_status not in [0x02]:
                            print(f"[WARN] Unit {unit.name} (id={unit.id}) not marked as moved after action. Forcibly marking as moved.")
                            # Update actionable_units/actions to prevent re-acting
                            for u in actionable_units:
                                if u.id == unit.id:
                                    u.turn_status = 0x02
                        # Update the acting unit's position after any action
                        for u in actionable_units:
                            if u.id == unit.id:
                                u.position = chosen_action.target_position
                        # Remove enemy if killed (use battle struct info)
                        if chosen_action.action_type == 'attack' and chosen_action.target_unit is not None and chosen_will_kill:
                            internal_enemies = [e for e in internal_enemies if e.id != chosen_action.target_unit.id]
                        # --- NEW: After a non-lethal attack, update the acting unit's position to match the new snapshot ---
                        if chosen_action.action_type == 'attack' and (not chosen_will_kill):
                            # Find the latest position of the acting unit in the new snapshot
                            updated_unit = next((u for u in snapshot.units if u.id == unit.id), None)
                            if updated_unit:
                                for u in actionable_units:
                                    if u.id == unit.id:
                                        u.position = updated_unit.position
                    replay_buffer.append((prev_snapshot, chosen_action, reward, snapshot))
                    episode_experience.append((prev_snapshot, chosen_action, reward, snapshot))
                    if is_player_dead(snapshot):
                        print("A player unit has died during action. Resetting level.")
                        player_died = True
                        break
                    acted = True
                    remove_idx = actionable_units.index(unit)
                    actionable_units.pop(remove_idx)
                    actionable_actions.pop(remove_idx)
                    break  # Only act with one unit per loop, then re-prioritize
                if player_died or not acted:
                    break
            if not player_died:
                if not SIMULATION_MODE:
                    cursor_pos = end_turn_in_bizhawk(cursor_pos, snapshot)
                    cursor_pos = get_cursor_position() or cursor_pos
                    print("Waiting for enemy phase to complete...")
                    snapshot = wait_for_state_update(snapshot)
                else:
                    done = True
        if episode_experience:
            train_neural_network(coordinator, replay_buffer)
        if done:
            print(f"[EPISODE {episode}] Success! Restarting for next trial...")
            time.sleep(0.2)
        if episode % 10 == 0:
            try:
                with open(REPLAY_BUFFER_PATH, 'wb') as f:
                    pickle.dump(list(replay_buffer), f)
                print(f"[REPLAY BUFFER] Saved to {REPLAY_BUFFER_PATH} at episode {episode}")
            except Exception as e:
                print(f"[REPLAY BUFFER ERROR] {e}")

def is_good_terrain(snapshot, x, y):
    symbol = snapshot.map.get_terrain_at(x, y)
    return symbol in GOOD_TERRAIN_SYMBOLS

if __name__ == "__main__":
    try:
        time.sleep(0.5)
        focus_bizhawk()
        trial_run()
    except KeyboardInterrupt:
        print("\n[INTERRUPT] Trial run stopped. Saving model...")
        if 'coordinator' in locals():
            coordinator.save_model("saved_model.pt")
            print("Model saved to saved_model.pt.")
        else:
            print("Coordinator not defined, model not saved.")
