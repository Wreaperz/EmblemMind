#!/usr/bin/env python3

import os
import time
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
            print(f"Phase: {snapshot.phase}")
            print(f"Cursor: {snapshot.cursor_position}")

            # Display character information
            print("\n=== CHARACTERS ===")
            for unit in snapshot.units:
                print(f"\n{unit.name} ({unit.class_name})")
                print(f"  Position: {unit.position}")
                print(f"  Level: {unit.level}")
                print(f"  HP: {unit.hp[0]}/{unit.hp[1]}")
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
                            if unit.is_visible:  # Only show visible enemies
                                line += "! "
                            else:
                                line += terrain + " "  # Hide invisible enemies
                        else:
                            line += "P "
                    else:
                        line += terrain + " " if terrain else "? "
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
