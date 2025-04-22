#!/usr/bin/env python3

import os
import time
import json
import struct
from utils.fe_state_parser import FEStateParser
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

            # Parse state file
            state_data = FEStateParser.parse_state_file(state_file_path)
            if not state_data:
                print(f"Failed to read state file: {state_file_path}")
                time.sleep(interval)
                continue

            # Parse map file
            map_data = parse_fe_map_file(map_file_path)

            # Display game state information
            print("\n=== GAME STATE ===")
            for key, value in state_data['game_state'].items():
                print(f"{key}: {value}")

            # Display character information
            print("\n=== CHARACTERS ===")
            for i, char in enumerate(state_data['characters']):
                char_id = char.get('id', 0)
                class_id = char.get('class', 0)

                print(f"\nCharacter {i+1}: {get_character_name(char_id)} [ID: 0x{char_id:04X}]")
                print(f"  Class: {get_class_name(class_id)} [ID: 0x{class_id:04X}]")

                # Display position, level, etc.
                print(f"  Position: {char.get('position', (0, 0))}")
                print(f"  Level: {char.get('level', 1)}")
                print(f"  HP: {char.get('hp', (0, 0))}")

                # Display stats
                if 'stats' in char:
                    # Handle all stats values (there are 9 values in the data)
                    stats = char['stats']
                    if len(stats) >= 6:
                        str_val, skl_val, spd_val, lck_val, def_val, res_val, mov_val, con_val, resc_val = stats[:9]
                        print(f"  Stats: STR {str_val}, SKL {skl_val}, SPD {spd_val}, LCK {lck_val}, DEF {def_val}, RES {res_val}, MOV {mov_val}, CON {con_val}, RESC {resc_val}")
                    else:
                        print(f"  Stats: {stats}")

                # Display turn status, hidden status, and status effect
                if 'turn_status' in char:
                    print(f"  Turn Status: {char.get('turn_status_text', 'Unknown')}")
                if 'hidden_status' in char:
                    print(f"  Hidden Status: {char.get('hidden_status_text', 'None')}")
                if 'status_effect' in char:
                    print(f"  Status Effect: {char.get('status_effect_text', 'None')}")

                # Display items with their names
                if 'items' in char:
                    print(f"  Items:")
                    for item_id, uses in char['items']:
                        item_name = get_item_name(item_id)
                        item_type = get_weapon_type(item_id)
                        item_type_str = f" ({item_type})" if item_type else ""
                        print(f"    - {item_name}{item_type_str}: {uses} uses [ID: 0x{item_id:02X}]")

            # Display enemy information
            print("\n=== ENEMIES ===")
            for i, enemy in enumerate(state_data['enemies']):
                enemy_id = enemy.get('id', 0)
                class_id = enemy.get('class', 0)

                print(f"\nEnemy {i+1}: {get_character_name(enemy_id)} [ID: 0x{enemy_id:04X}]")
                print(f"  Class: {get_class_name(class_id)} [ID: 0x{class_id:04X}]")

                # Display position, level, etc.
                print(f"  Position: {enemy.get('position', (0, 0))}")
                print(f"  Level: {enemy.get('level', 1)}")
                print(f"  HP: {enemy.get('hp', (0, 0))}")

                # Display stats
                if 'stats' in enemy:
                    # Handle all stats values (there are 9 values in the data)
                    stats = enemy['stats']
                    if len(stats) >= 6:
                        str_val, skl_val, spd_val, lck_val, def_val, res_val, mov_val, con_val, resc_val = stats[:9]
                        print(f"  Stats: STR {str_val}, SKL {skl_val}, SPD {spd_val}, LCK {lck_val}, DEF {def_val}, RES {res_val}, MOV {mov_val}, CON {con_val}, RESC {resc_val}")
                    else:
                        print(f"  Stats: {stats}")

                # Display turn status, hidden status, and status effect
                if 'turn_status' in enemy:
                    print(f"  Turn Status: {enemy.get('turn_status_text', 'Unknown')}")
                if 'hidden_status' in enemy:
                    print(f"  Hidden Status: {enemy.get('hidden_status_text', 'None')}")
                if 'status_effect' in enemy:
                    print(f"  Status Effect: {enemy.get('status_effect_text', 'None')}")

                # Display items with their names
                if 'items' in enemy:
                    print(f"  Items:")
                    for item_id, uses in enemy['items']:
                        item_name = get_item_name(item_id)
                        item_type = get_weapon_type(item_id)
                        item_type_str = f" ({item_type})" if item_type else ""
                        print(f"    - {item_name}{item_type_str}: {uses} uses [ID: 0x{item_id:02X}]")

            # Get cursor position and check for unit at that position
            cursor_x = state_data['game_state'].get('cursor_x')
            cursor_y = state_data['game_state'].get('cursor_y')

            if cursor_x is not None and cursor_y is not None:
                # Check if there's a unit at cursor position
                unit, unit_type = FEStateParser.get_unit_at_position(
                    state_data, cursor_x, cursor_y
                )

                if unit:
                    unit_id = unit.get('id', 0)
                    class_id = unit.get('class', 0)

                    print(f"\n=== UNIT AT CURSOR ({cursor_x}, {cursor_y}) ===")
                    print(f"Type: {unit_type}")
                    print(f"Character: {get_character_name(unit_id)} [ID: 0x{unit_id:04X}]")
                    print(f"Class: {get_class_name(class_id)} [ID: 0x{class_id:04X}]")
                    print(f"HP: {unit.get('hp', (0, 0))}")

                    # Display turn status, hidden status, and status effect
                    if 'turn_status' in unit:
                        print(f"Turn Status: {unit.get('turn_status_text', 'Unknown')}")
                    if 'hidden_status' in unit:
                        print(f"Hidden Status: {unit.get('hidden_status_text', 'None')}")
                    if 'status_effect' in unit:
                        print(f"Status Effect: {unit.get('status_effect_text', 'None')}")

                    # Display items with their names
                    if 'items' in unit:
                        print(f"Items:")
                        for item_id, uses in unit['items']:
                            item_name = get_item_name(item_id)
                            item_type = get_weapon_type(item_id)
                            item_type_str = f" ({item_type})" if item_type else ""
                            print(f"  - {item_name}{item_type_str}: {uses} uses [ID: 0x{item_id:02X}]")

                # If we have cursor position and map data, show terrain at cursor
                if map_data and cursor_x < map_data["width"] and cursor_y < map_data["height"]:
                    terrain_symbol = map_data["terrain_grid"][cursor_y][cursor_x]
                    print(f"\n=== TERRAIN AT CURSOR ({cursor_x}, {cursor_y}) ===")
                    print(f"Symbol: {terrain_symbol}")

            # Display map if we have it
            if map_data:
                display_map(map_data, cursor_x, cursor_y)

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

    # Start monitoring the FE state
    monitor_fe_state(state_file_path, map_file_path, data_dir)

if __name__ == "__main__":
    main()
