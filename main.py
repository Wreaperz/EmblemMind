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

def load_tiles_data(json_path):
    """Load tile data from the tiles.json file"""
    try:
        with open(json_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading tiles data: {e}")
        return {}

def parse_map_data(chapter_id, data_dir):
    """
    Parse map data for the given chapter ID

    Args:
        chapter_id: Chapter ID as an integer
        data_dir: Directory containing map data

    Returns:
        dict: Map data including dimensions, terrain, and tile information
    """
    try:
        # Format chapter ID as hex string (e.g., 2 -> "02")
        chapter_hex = f"{chapter_id:02X}"

        # Load mappings file to find the correct address references
        mappings_path = os.path.join(data_dir, "mappings.json")
        if os.path.exists(mappings_path):
            try:
                with open(mappings_path, 'r') as f:
                    mappings = json.load(f)

                # Check if we have mapping for this chapter
                if chapter_hex in mappings:
                    print(f"Found mapping for chapter {chapter_hex}: {mappings[chapter_hex]}")
                    addresses = mappings[chapter_hex]
                else:
                    print(f"No mapping found for chapter {chapter_hex} in mappings.json")
            except Exception as e:
                print(f"Error loading mappings file: {e}")
                mappings = {}
        else:
            print(f"Mappings file not found at {mappings_path}")
            mappings = {}

        # Find corresponding spritemap and tilemap files
        chapter_hex_lower = chapter_hex.lower()
        chapter_hex_upper = chapter_hex.upper()
        spritemap_patterns = [
            f"spritemap_{chapter_hex_lower}_",
            f"spritemap_{chapter_hex_upper}_"
        ]
        tilemap_patterns = [
            f"tilemap_{chapter_hex_lower}_",
            f"tilemap_{chapter_hex_upper}_"
        ]

        spritemap_file = None
        tilemap_file = None

        # Find the right files in the directories
        spritemap_dir = os.path.join(data_dir, "spritemaps")
        tilemap_dir = os.path.join(data_dir, "tilemaps")

        if os.path.exists(spritemap_dir):
            all_files = os.listdir(spritemap_dir)
            print(f"Available spritemap files: {all_files}")
            for file in all_files:
                # Check both uppercase and lowercase patterns
                if any(file.startswith(pattern) and file.endswith(".bin") for pattern in spritemap_patterns):
                    spritemap_file = os.path.join(spritemap_dir, file)
                    print(f"Found spritemap file: {file}")
                    break

        if os.path.exists(tilemap_dir):
            all_files = os.listdir(tilemap_dir)
            print(f"Available tilemap files: {all_files}")
            for file in all_files:
                # Check both uppercase and lowercase patterns
                if any(file.startswith(pattern) and file.endswith(".bin") for pattern in tilemap_patterns):
                    tilemap_file = os.path.join(tilemap_dir, file)
                    print(f"Found tilemap file: {file}")
                    break

        if not spritemap_file:
            print(f"Spritemap file for chapter {chapter_id} (0x{chapter_hex}) not found.")
            return None

        if not tilemap_file:
            print(f"Tilemap file for chapter {chapter_id} (0x{chapter_hex}) not found.")
            return None

        # Load tile definitions
        tiles_json_path = os.path.join(data_dir, "tiles.json")
        tiles_data = load_tiles_data(tiles_json_path)

        # Read spritemap file
        with open(spritemap_file, 'rb') as f:
            spritemap_data = f.read()

        # Read width and height from the first two bytes
        width = spritemap_data[0]
        height = spritemap_data[1]

        # Parse tile IDs (2 bytes each, little-endian)
        tiles = []
        for i in range(2, len(spritemap_data), 2):
            if i + 1 < len(spritemap_data):
                tile_id = spritemap_data[i] | (spritemap_data[i+1] << 8)
                tiles.append(tile_id)

        # Reshape tiles into a 2D grid
        tile_grid = []
        for y in range(height):
            row = []
            for x in range(width):
                if y * width + x < len(tiles):
                    row.append(tiles[y * width + x])
                else:
                    row.append(0)  # Default tile if out of bounds
            tile_grid.append(row)

        # Read tilemap file for terrain data
        with open(tilemap_file, 'rb') as f:
            tilemap_data = f.read()

        # Create terrain grid based on tile IDs
        terrain_grid = []
        for row in tile_grid:
            terrain_row = []
            for tile_id in row:
                # Calculate address in tilemap for terrain
                address = (tile_id // 4) + 0x2000

                # Make sure the address is within bounds
                if address < len(tilemap_data):
                    terrain_id = tilemap_data[address]
                    # Convert to hex string for lookup in tiles.json
                    terrain_hex = f"{terrain_id:02X}"

                    # Get terrain info from tiles.json
                    terrain_info = tiles_data.get(terrain_hex, {"name": "Unknown"})
                    terrain_row.append({
                        "id": terrain_id,
                        "hex": terrain_hex,
                        "name": terrain_info.get("name", "Unknown"),
                        "avoid": terrain_info.get("avoid", 0),
                        "def": terrain_info.get("def", 0),
                        "res": terrain_info.get("res", 0)
                    })
                else:
                    terrain_row.append({"name": "Out of bounds", "id": 0, "hex": "00"})
            terrain_grid.append(terrain_row)

        return {
            "width": width,
            "height": height,
            "tile_grid": tile_grid,
            "terrain_grid": terrain_grid
        }

    except Exception as e:
        print(f"Error parsing map data for chapter {chapter_id}: {e}")
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

    # Create a simplified representation
    for y, row in enumerate(terrain_grid):
        line = ""
        for x, terrain in enumerate(row):
            # Mark cursor position
            if cursor_x is not None and cursor_y is not None and x == cursor_x and y == cursor_y:
                line += "X "
            else:
                # Use first character of terrain name as marker
                if terrain["name"] == "Plains":
                    line += ". "  # Plains
                elif terrain["name"] == "Forest":
                    line += "F "  # Forest
                elif terrain["name"] == "Hill":
                    line += "^ "  # Hill
                elif terrain["name"] == "Mountain" or terrain["name"] == "Peak":
                    line += "M "  # Mountain/Peak
                elif terrain["name"] == "River" or terrain["name"] == "Lake" or terrain["name"] == "Sea":
                    line += "~ "  # Water
                elif terrain["name"] == "Village" or terrain["name"] == "House":
                    line += "H "  # House/Village
                elif terrain["name"] == "Fort" or terrain["name"] == "Castle":
                    line += "C "  # Castle/Fort
                elif terrain["name"] == "Road" or terrain["name"] == "Bridge":
                    line += "= "  # Road/Bridge
                elif terrain["name"] == "Wall":
                    line += "# "  # Wall
                elif terrain["name"] == "Door" or terrain["name"] == "Gate":
                    line += "D "  # Door/Gate
                else:
                    line += terrain["name"][0] + " "  # First letter as fallback
        print(line)

    print("\nTerrain Legend:")
    print(". = Plains, F = Forest, ^ = Hill, M = Mountain/Peak, ~ = Water")
    print("H = House/Village, C = Castle/Fort, = = Road/Bridge, # = Wall, D = Door/Gate")
    print("X = Cursor Position (if shown)")

def monitor_fe_state(state_file_path, data_dir, interval=1):
    """
    Continuously monitor and display Fire Emblem state with human-readable data

    Args:
        state_file_path (str): Path to the fe_state.txt file
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

            # Get chapter ID
            chapter_id = state_data['game_state'].get('chapter_id', 0)

            # Parse map data for the current chapter
            map_data = parse_map_data(chapter_id, data_dir)

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
                    terrain = map_data["terrain_grid"][cursor_y][cursor_x]
                    print(f"\n=== TERRAIN AT CURSOR ({cursor_x}, {cursor_y}) ===")
                    print(f"Type: {terrain['name']} [ID: 0x{terrain['hex']}]")
                    print(f"Stats: Avoid +{terrain['avoid']}, Def +{terrain['def']}, Res +{terrain['res']}")

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

    # Check if the file exists
    if not os.path.exists(state_file_path):
        print(f"Error: State file not found at {state_file_path}")
        return

    # Start monitoring the FE state
    monitor_fe_state(state_file_path, data_dir)

if __name__ == "__main__":
    main()
