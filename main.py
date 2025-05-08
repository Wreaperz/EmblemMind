#!/usr/bin/env python3

import os
import time
import re
from emblemmind_snapshot import TurnSnapshot
from utils.fe_data_mappings import (
    get_item_name, get_character_name, get_class_name,
    get_weapon_type
)

def parse_fe_map_file(map_file_path):
    """
    Parse the map terrain data from fe_map.txt created by fe_memory_reader.lua

    Args:
        map_file_path: Path to fe_map.txt file

    Returns:
        dict: Map data including dimensions, terrain grid, and other info
    """
    try:
        if not os.path.exists(map_file_path):
            print(f"Map file not found: {map_file_path}")
            return None

        map_data = {
            "width": 0,
            "height": 0,
            "terrain_grid": [],
            "debug_info": {}
        }

        # Parse the map file
        with open(map_file_path, 'r') as f:
            lines = f.readlines()

        # Check if the file is valid
        if not lines or len(lines) < 3:
            print(f"Map file is empty or invalid: {map_file_path}")
            return None

        # First line has dimensions
        header = lines[0].strip()
        if header.startswith("Map size:"):
            dimensions = header.replace("Map size:", "").strip()
            width, height = map(int, dimensions.split('x'))
            map_data["width"] = width
            map_data["height"] = height

        # Skip the blank line
        terrain_start = 2
        terrain_end = terrain_start + map_data["height"]

        # Read the terrain grid
        for y in range(terrain_start, terrain_end):
            if y < len(lines):
                row_data = lines[y].strip().split()

                # Store terrain symbols directly
                terrain_row = []
                for symbol in row_data:
                    terrain_row.append(symbol)

                map_data["terrain_grid"].append(terrain_row)

        # Read terrain legend and debug info if available
        legend_info = {}
        for i in range(terrain_end, len(lines)):
            line = lines[i].strip()
            if line.startswith("Terrain Legend:"):
                # Next lines contain the legend
                legend_start = i + 1
                for j in range(legend_start, len(lines)):
                    legend_line = lines[j].strip()
                    if not legend_line or legend_line.startswith("Terrain pointer"):
                        break
                    # Store the legend information
                    legend_info[j - legend_start] = legend_line
            elif line and ":" in line:
                key, value = line.split(":", 1)
                map_data["debug_info"][key.strip()] = value.strip()

        map_data["legend"] = legend_info
        return map_data

    except Exception as e:
        print(f"Error parsing map file: {e}")
        import traceback
        traceback.print_exc()
        return None

def display_map(map_data, cursor_x=None, cursor_y=None):
    """Display a simplified ASCII version of the map"""
    if not map_data:
        return

    terrain_grid = map_data["terrain_grid"]
    print("\n=== MAP ===")
    print(f"Dimensions: {map_data['width']}x{map_data['height']}")

    # Create a representation using the exact symbols from the map file
    for y, row in enumerate(terrain_grid):
        line = ""
        for x, symbol in enumerate(row):
            # Mark cursor position
            if cursor_x is not None and cursor_y is not None and x == cursor_x and y == cursor_y:
                line += "X "
            else:
                # Use the symbol directly from the parsed map
                line += symbol + " "
        print(line)

    # Print the terrain legend from the map file
    print("\nTerrain Legend:")
    for i, legend_line in map_data.get("legend", {}).items():
        print(legend_line)
    print("X = Cursor Position (if shown)")

def parse_realtime_data_from_state_file(state_file_path):
    """Parse the REALTIME_DATA section from fe_state.txt and return a dict."""
    data = {
        'cursor_rt_x': None,
        'cursor_rt_y': None,
        'move_dest_x': None,
        'move_dest_y': None,
        'deployment_id': None
    }
    try:
        with open(state_file_path, 'r') as f:
            lines = f.readlines()
        in_realtime = False
        for line in lines:
            line = line.strip()
            if line == 'REALTIME_DATA':
                in_realtime = True
                continue
            if in_realtime:
                if line == '' or line.endswith('CHARACTERS') or line.startswith('CHARACTERS'):
                    break
                m = re.match(r'(cursor_rt_x|cursor_rt_y|move_dest_x|move_dest_y|deployment_id)=(\d+)', line)
                if m:
                    key, val = m.group(1), int(m.group(2))
                    data[key] = val
    except Exception as e:
        print(f"Error parsing REALTIME_DATA: {e}")
    return data

def parse_battle_structs_from_state_file(state_file_path):
    """Parse the BATTLE_STRUCTS section from fe_state.txt and return attacker/defender battle bytes."""
    attacker = None
    defender = None
    try:
        with open(state_file_path, 'r') as f:
            lines = f.readlines()
        in_battle = False
        for line in lines:
            line = line.strip()
            if line == 'BATTLE_STRUCTS':
                in_battle = True
                continue
            if in_battle:
                if line.startswith('attacker_battle='):
                    hexstr = line.split('=', 1)[1].strip()
                    attacker = [int(b, 16) for b in hexstr.split()]
                elif line.startswith('defender_battle='):
                    hexstr = line.split('=', 1)[1].strip()
                    defender = [int(b, 16) for b in hexstr.split()]
                elif line == '' or line.endswith('CHARACTERS') or line.startswith('CHARACTERS'):
                    break
    except Exception as e:
        print(f"Error parsing BATTLE_STRUCTS: {e}")
    return attacker, defender

def parse_battle_struct(state_file_path, struct='attacker'):
    """Parse the BATTLE_STRUCTS section and return a dict of intuitive fields for the attacker or defender."""
    attacker, defender = parse_battle_structs_from_state_file(state_file_path)
    data = attacker if struct == 'attacker' else defender
    if not data:
        return None
    def get_word(offset):
        return data[offset] | (data[offset+1] << 8) | (data[offset+2] << 16) | (data[offset+3] << 24)
    def get_short(offset):
        return data[offset] | (data[offset+1] << 8)
    def get_byte(offset):
        return data[offset]
    battle_struct = {
        'level': get_byte(0x08),
        'exp': get_byte(0x09),
        'ai_flags': get_byte(0x0A),
        'deployment': get_byte(0x0B),
        'unit_state': get_word(0x0C),
        'x': get_byte(0x10),
        'y': get_byte(0x11),
        'max_hp': get_byte(0x12),
        'cur_hp': get_byte(0x13),
        'str': get_byte(0x14),
        'skl': get_byte(0x15),
        'spd': get_byte(0x16),
        'def': get_byte(0x17),
        'res': get_byte(0x18),
        'lck': get_byte(0x19),
        'con_bonus': get_byte(0x1A),
        'mov_bonus': get_byte(0x1D),
        'items': [
            (get_short(0x1E), get_short(0x1F)),
            (get_short(0x20), get_short(0x21)),
            (get_short(0x22), get_short(0x23)),
            (get_short(0x24), get_short(0x25)),
            (get_short(0x26), get_short(0x27)),
        ],
        'sword_rank': get_byte(0x28),
        'lance_rank': get_byte(0x29),
        'axe_rank': get_byte(0x2A),
        'bow_rank': get_byte(0x2B),
        'staff_rank': get_byte(0x2C),
        'anima_rank': get_byte(0x2D),
        'light_rank': get_byte(0x2E),
        'dark_rank': get_byte(0x2F),
        'status': get_byte(0x30),
        'status_duration': get_byte(0x31),
        # Battle-only fields:
        'equipped_item_after': get_short(0x48),
        'equipped_item_before': get_short(0x4A),
        'weapon_ability_word': get_word(0x4C),
        'weapon_type': get_byte(0x50),
        'weapon_slot': get_byte(0x51),
        'can_counter': get_byte(0x52),
        'wtriangle_hit': get_byte(0x53),
        'wtriangle_dmg': get_byte(0x54),
        'terrain_id': get_byte(0x55),
        'terrain_def': get_byte(0x56),
        'terrain_avo': get_byte(0x57),
        'terrain_res': get_byte(0x58),
        'attack': get_short(0x5A),
        'defense': get_short(0x5C),
        'attack_speed': get_short(0x5E),
        'hit': get_short(0x60),
        'avoid': get_short(0x62),
        'battle_hit': get_short(0x64),
        'crit': get_short(0x66),
        'crit_avoid': get_short(0x68),
        'battle_crit': get_short(0x6A),
        'lethality': get_short(0x6C),
        'exp_gain': get_byte(0x6E),
        'status_to_write': get_byte(0x6F),
        'level_pre_battle': get_byte(0x70),
        'exp_pre_battle': get_byte(0x71),
        'cur_hp_battle': get_byte(0x72),
        'hp_change': get_byte(0x73),
        'str_change': get_byte(0x74),
        'skl_change': get_byte(0x75),
        'spd_change': get_byte(0x76),
        'def_change': get_byte(0x77),
        'res_change': get_byte(0x78),
        'luk_change': get_byte(0x79),
        'con_change': get_byte(0x7A),
        'wexp_multiplier': get_byte(0x7B),
        'nonzero_damage': get_byte(0x7C),
        'weapon_broke': get_byte(0x7D),
    }
    return battle_struct

def monitor_fe_state(state_file_path, map_file_path, data_dir, interval=1):
    """
    Continuously monitor and display Fire Emblem state with human-readable data

    Args:
        state_file_path (str): Path to the fe_state.txt file
        map_file_path (str): Path to the fe_map.txt file
        data_dir (str): Path to the data directory
        interval (float): Polling interval in seconds
    """
    print("Starting Fire Emblem state monitoring. Press Ctrl+C to exit.")

    try:
        while True:
            # Clear console
            os.system('cls' if os.name == 'nt' else 'clear')

            # Create snapshot from files
            try:
                snapshot = TurnSnapshot.from_files(state_file_path, map_file_path)
            except ValueError as e:
                print(f"Failed to create snapshot: {e}")
                time.sleep(interval)
                continue

            # Display game state information
            print("\n=== GAME STATE ===")
            print(f"Turn: {snapshot.current_turn}")
            print(f"Chapter: {snapshot.chapter_id}")
            print(f"Phase: {snapshot.phase_text}")
            print(f"Cursor: {snapshot.cursor_position}")

            # Display REALTIME_DATA
            realtime = parse_realtime_data_from_state_file(state_file_path)
            print("\n=== REALTIME DATA ===")
            print(f"Cursor (realtime) X: {realtime['cursor_rt_x']}")
            print(f"Cursor (realtime) Y: {realtime['cursor_rt_y']}")
            print(f"Move destination X: {realtime['move_dest_x']}")
            print(f"Move destination Y: {realtime['move_dest_y']}")
            print(f"Deployment ID: {realtime['deployment_id']}")

            # Display battle struct bytes
            attacker, defender = parse_battle_structs_from_state_file(state_file_path)
            print("\n=== BATTLE STRUCTS (0x48-0x7D) ===")
            if attacker:
                print(f"Attacker: {attacker}")
                print(f"Attacker (hex): {' '.join(f'{b:02X}' for b in attacker)}")
                parsed_attacker = parse_battle_struct(state_file_path, 'attacker')
                if parsed_attacker:
                    print("Attacker (parsed):")
                    for k, v in parsed_attacker.items():
                        print(f"  {k}: {v}")
            else:
                print("Attacker: None")
            if defender:
                print(f"Defender: {defender}")
                print(f"Defender (hex): {' '.join(f'{b:02X}' for b in defender)}")
                parsed_defender = parse_battle_struct(state_file_path, 'defender')
                if parsed_defender:
                    print("Defender (parsed):")
                    for k, v in parsed_defender.items():
                        print(f"  {k}: {v}")
            else:
                print("Defender: None")

            # Display character information
            print("\n=== CHARACTERS ===")
            for unit in snapshot.units:
                print(f"\n{unit.name} ({unit.class_name})")
                print(f"  Position: {unit.position}")
                print(f"  Level: {unit.level}")
                print(f"  Exp: {unit.exp}")
                print(f"  HP: {unit.hp[0]}/{unit.hp[1]}")
                # Display unit state bitfield (0x0C) if available
                unit_state = None
                try:
                    with open(state_file_path, 'r') as f:
                        lines = f.readlines()
                    in_chars = False
                    curr_idx = 0
                    for line in lines:
                        line = line.strip()
                        if line == 'CHARACTERS':
                            in_chars = True
                            continue
                        if in_chars:
                            if line.startswith('character='):
                                curr_idx += 1
                            if curr_idx == snapshot.units.index(unit) + 1:
                                if '  turn_status=' in line:
                                    continue
                                if '  unit_state=' in line or '  state=' in line or '  unit_state_bitfield=' in line:
                                    val = line.split('=', 1)[1].strip()
                                    unit_state = val
                                    break
                except Exception:
                    pass
                if unit_state is not None:
                    print(f"  Unit State Bitfield (0x0C): {unit_state}")
                print(f"  Stats: STR {unit.stats[0]}, SKL {unit.stats[1]}, SPD {unit.stats[2]}, LCK {unit.stats[3]}, DEF {unit.stats[4]}, RES {unit.stats[5]}")
                print(f"  MOV: {unit.movement_range}")
                print(f"  Status: {unit.turn_status_text}")
                if unit.items:
                    print("  Items:")
                    for item_id, uses in unit.items:
                        print(f"    - {get_item_name(item_id)}: {uses} uses")

            # Display enemy information
            print("\n=== ENEMIES ===")
            for enemy in snapshot.enemies:
                if enemy.is_alive and enemy.is_visible:  # Only show visible enemies
                    print(f"\n{enemy.name} ({enemy.class_name})")
                    print(f"  Position: {enemy.position}")
                    print(f"  Level: {enemy.level}")
                    print(f"  HP: {enemy.hp[0]}/{enemy.hp[1]}")
                    print(f"  Status: {enemy.turn_status_text}")

            # Display map
            print("\n=== MAP ===")
            print(f"Dimensions: {snapshot.map.width}x{snapshot.map.height}")
            for y in range(snapshot.map.height):
                line = ""
                for x in range(snapshot.map.width):
                    terrain = snapshot.map.get_terrain_at(x, y)
                    unit = snapshot.get_unit_at(x, y)
                    if unit:
                        if unit.is_enemy:
                            line += "! "
                        else:
                            line += "P "
                    else:
                        line += terrain + " " if terrain else "? "
                print(line)

            # === MOVEMENT/RANGE MAP VISUALIZATION ===
            def parse_map_section(section_name):
                with open(state_file_path, 'r') as f:
                    lines = f.readlines()
                in_section = False
                grid = []
                for line in lines:
                    line = line.strip()
                    if line == section_name:
                        in_section = True
                        continue
                    if in_section:
                        # Stop if we hit another section header (all uppercase, possibly with underscores)
                        if not line or (line.replace('_', '').isupper() and line.replace('_', '').isalpha()):
                            break
                        # Defensive: skip lines that don't look like hex rows
                        if not all(all(c in "0123456789ABCDEFabcdef" for c in b) for b in line.split()):
                            break
                        row = [int(b, 16) for b in line.split()]
                        grid.append(row)
                return grid

            movement_map = parse_map_section('MOVEMENT_MAP')
            range_map = parse_map_section('RANGE_MAP')
            cursor_x = realtime['cursor_rt_x']
            cursor_y = realtime['cursor_rt_y']
            print("\n=== MOVEMENT/RANGE MAP (Selected Unit) ===")
            for y in range(snapshot.map.height):
                line = ""
                for x in range(snapshot.map.width):
                    unit = snapshot.get_unit_at(x, y)
                    move = (len(movement_map) > y and len(movement_map[y]) > x and movement_map[y][x] != 0xFF)
                    rng = (len(range_map) > y and len(range_map[y]) > x and range_map[y][x] != 0)
                    is_cursor = (x == cursor_x and y == cursor_y)
                    if is_cursor:
                        line += "X "
                    elif unit:
                        if unit.is_enemy:
                            line += "! "
                        else:
                            line += "P "
                    elif move and rng:
                        line += "* "  # Both move and attack
                    elif move:
                        line += "M "  # Move only
                    elif rng:
                        line += "A "  # Attack only
                    else:
                        terrain = snapshot.map.get_terrain_at(x, y)
                        line += (terrain + " ") if terrain else "? "
                print(line)

            # Wait before polling again
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main entry point"""
    # Get the current directory and set paths
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

    # Start monitoring the FE state
    monitor_fe_state(state_file_path, map_file_path, data_dir)

if __name__ == "__main__":
    main()
