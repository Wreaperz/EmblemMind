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

    # Fix item parsing - in FE GBA games, items are stored as:
    # Lower byte (offset+0) = Item ID
    # Upper byte (offset+1) = Number of uses
    def get_item(offset):
        item_id = data[offset]
        uses = data[offset+1]
        return (item_id, uses)

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
        # Fix item parsing - get_item instead of get_short for both ID and uses
        'items': [
            get_item(0x1E),
            get_item(0x20),
            get_item(0x22),
            get_item(0x24),
            get_item(0x26),
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
        # For equipped items, also use get_byte for both ID and uses
        'equipped_item_after': get_byte(0x48),
        'equipped_item_after_uses': get_byte(0x49),
        'equipped_item_before': get_byte(0x4A),
        'equipped_item_before_uses': get_byte(0x4B),
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

def format_battle_struct(battle_struct, struct_name="Unit"):
    """Format battle struct into more readable sections with labels using RAM offset notes"""
    if not battle_struct:
        return "None"

    weapon_types = {
        0: "Sword", 1: "Lance", 2: "Axe", 3: "Bow",
        4: "Staff", 5: "Anima", 6: "Light", 7: "Dark"
    }

    # Unit state flags (0x0C-0x0F)
    unit_state_flags = {
        # Lower byte (0x0C)
        0x00000001: "Undeployed",
        0x00000002: "Dead",
        0x00000004: "Deployed",
        0x00000008: "Not Movable",
        0x00000010: "Has Moved",
        0x00000020: "Has Acted",
        0x00000040: "Grayed Out",
        0x00000080: "Hidden",
        0x00000100: "Rescuing",
        0x00000200: "Being Rescued",
        0x00000400: "Has Dropped",
        0x00000800: "Under Roof",
        # Byte 0x0D
        0x00001000: "Inside Ballista",
        0x00002000: "Drop Last Item",
        0x00004000: "Afa's Drops/Metis Tome",
        0x00008000: "Solo Animation 1",
        0x00010000: "Solo Animation 2",
        # Byte 0x0E
        0x00020000: "REMU'd (Not Drawn)",
        0x00040000: "Store Battle Turn Word",
        0x00080000: "Store Battle Turn Word 2",
        0x00100000: "Super-Arena Mode",
        0x00200000: "Not Deployed Previous Chapter",
        0x00400000: "Cutscene Unit (Deletable)",
        0x00800000: "Increase Portrait Index by 1",
        # Byte 0x0F
        0x01000000: "Shaking Map Sprite",
        0x02000000: "Cannot Take Part in Chapter",
        0x04000000: "REMU'd",
        0x08000000: "Link Arena Palette/Alt Palette",
        0x40000000: "Capture"
    }

    # Status effect descriptions (0x30)
    status_effect_map = {
        0: "None",
        1: "Poison",
        2: "Sleep",
        3: "Silence",
        4: "Berserk",
        5: "Attack Boost",
        6: "Defense Boost",
        7: "Critical Boost",
        8: "Avoid Boost"
    }

    # Format items with names - items are now correctly parsed
    item_list = []
    for item_id, uses in battle_struct['items']:
        if item_id > 0:
            try:
                name = get_item_name(item_id)
                item_list.append(f"{name} ({uses} uses)")
            except:
                item_list.append(f"ID:0x{item_id:02X} ({uses} uses)")

    # Format weapon ranks
    weapon_ranks = []
    rank_letters = {0: "-", 1: "E", 31: "D", 71: "C", 121: "B", 181: "A", 251: "S"}

    for weapon, rank_value in [
        ("Sword", battle_struct['sword_rank']),
        ("Lance", battle_struct['lance_rank']),
        ("Axe", battle_struct['axe_rank']),
        ("Bow", battle_struct['bow_rank']),
        ("Staff", battle_struct['staff_rank']),
        ("Anima", battle_struct['anima_rank']),
        ("Light", battle_struct['light_rank']),
        ("Dark", battle_struct['dark_rank'])
    ]:
        # Only include ranks that are not 0
        if rank_value > 0:
            # Find the closest rank letter
            rank_letter = "-"
            for threshold, letter in sorted(rank_letters.items()):
                if rank_value >= threshold:
                    rank_letter = letter
            weapon_ranks.append(f"{weapon}: {rank_letter} ({rank_value})")

    # Decode unit state flags
    state_flags = []
    for flag, description in unit_state_flags.items():
        if battle_struct['unit_state'] & flag:
            state_flags.append(description)

    # Format equipped item - now using the correct bytes for ID and uses
    equipped_before = "None"
    equipped_after = "None"

    if battle_struct['equipped_item_before'] > 0:
        try:
            name = get_item_name(battle_struct['equipped_item_before'])
            uses = battle_struct['equipped_item_before_uses']
            equipped_before = f"{name} ({uses} uses)"
        except:
            equipped_before = f"ID:0x{battle_struct['equipped_item_before']:02X} ({battle_struct['equipped_item_before_uses']} uses)"

    if battle_struct['equipped_item_after'] > 0:
        try:
            name = get_item_name(battle_struct['equipped_item_after'])
            uses = battle_struct['equipped_item_after_uses']
            equipped_after = f"{name} ({uses} uses)"
        except:
            equipped_after = f"ID:0x{battle_struct['equipped_item_after']:02X} ({battle_struct['equipped_item_after_uses']} uses)"

    # Format weapon type
    weapon_type = weapon_types.get(battle_struct['weapon_type'], f"Unknown ({battle_struct['weapon_type']})")

    # Format status effect
    status = battle_struct['status'] & 0x0F
    status_duration = battle_struct['status'] >> 4
    status_text = status_effect_map.get(status, f"Unknown ({status})")

    # Prepare all sections
    sections = {
        "Unit Info": [
            f"Position: ({battle_struct['x']}, {battle_struct['y']})",
            f"Level: {battle_struct['level']} (Exp: {battle_struct['exp']})",
            f"HP: {battle_struct['cur_hp']}/{battle_struct['max_hp']}",
            f"Deployment ID: {battle_struct['deployment']} (AI Flags: 0x{battle_struct['ai_flags']:02X})"
        ],

        "Unit State Bitfield (0x0C-0x0F)": [
            f"Raw Value: 0x{battle_struct['unit_state']:08X}",
            "Active Flags:"
        ] + ([f"  • {flag}" for flag in state_flags] if state_flags else ["  • None"]),

        "Stats": [
            f"STR: {battle_struct['str']}",
            f"SKL: {battle_struct['skl']}",
            f"SPD: {battle_struct['spd']}",
            f"DEF: {battle_struct['def']}",
            f"RES: {battle_struct['res']}",
            f"LCK: {battle_struct['lck']}",
            f"CON: {battle_struct['con_bonus']} (bonus)",
            f"MOV: {battle_struct['mov_bonus']} (bonus)"
        ],

        "Items (0x1E-0x27)": item_list if item_list else ["None"],

        "Weapon Ranks (0x28-0x2F)": weapon_ranks if weapon_ranks else ["None"],

        "Status Effect (0x30)": [
            f"Type: {status_text}",
            f"Duration: {status_duration} turns"
        ],

        "Battle Equipment (0x48-0x51)": [
            f"Equipped After Battle: {equipped_after} (0x48-0x49)",
            f"Equipped Before Battle: {equipped_before} (0x4A-0x4B)",
            f"Weapon Ability Word: 0x{battle_struct['weapon_ability_word']:08X} (0x4C)",
            f"Weapon Type: {weapon_type} (0x50)",
            f"Inventory Slot: {battle_struct['weapon_slot']} (0x51)"
        ],

        "Weapon Triangle & Terrain (0x52-0x58)": [
            f"Can Counter: {'Yes' if battle_struct['can_counter'] else 'No'} (0x52)",
            f"WTA Hit Bonus: {battle_struct['wtriangle_hit']} (0x53)",
            f"WTA Damage Bonus: {battle_struct['wtriangle_dmg']} (0x54)",
            f"Terrain ID: {battle_struct['terrain_id']} (0x55)",
            f"Terrain DEF Bonus: {battle_struct['terrain_def']} (0x56)",
            f"Terrain AVO Bonus: {battle_struct['terrain_avo']} (0x57)",
            f"Terrain RES Bonus: {battle_struct['terrain_res']} (0x58)"
        ],

        "Combat Stats (0x5A-0x6C)": [
            f"Attack: {battle_struct['attack']} (0x5A)",
            f"Defense: {battle_struct['defense']} (0x5C)",
            f"Attack Speed: {battle_struct['attack_speed']} (0x5E)",
            f"Hit: {battle_struct['hit']} (0x60)",
            f"Avoid: {battle_struct['avoid']} (0x62)",
            f"Battle Hit: {battle_struct['battle_hit']}% (Hit - Chance of Landing Hit) (0x64)",
            f"Crit: {battle_struct['crit']} (0x66)",
            f"Crit Avoid: {battle_struct['crit_avoid']} (0x68)",
            f"Battle Crit: {battle_struct['battle_crit']}% (Crit - Chance of Crit Striking) (0x6A)",
            f"Lethality: {battle_struct['lethality']}% (0x6C)"
        ],

        "Battle Results & Changes (0x6E-0x7D)": [
            f"EXP Gain: {battle_struct['exp_gain']} (0x6E)",
            f"Status to Write: {battle_struct['status_to_write']} (0x6F)",
            f"Pre-Battle Level: {battle_struct['level_pre_battle']} (0x70)",
            f"Pre-Battle EXP: {battle_struct['exp_pre_battle']} (0x71)",
            f"HP in Battle: {battle_struct['cur_hp_battle']} (0x72)",
            f"Stat Changes:",
            f"  • HP: {'+' if battle_struct['hp_change'] > 0 else ''}{battle_struct['hp_change']} (0x73)",
            f"  • STR: {'+' if battle_struct['str_change'] > 0 else ''}{battle_struct['str_change']} (0x74)",
            f"  • SKL: {'+' if battle_struct['skl_change'] > 0 else ''}{battle_struct['skl_change']} (0x75)",
            f"  • SPD: {'+' if battle_struct['spd_change'] > 0 else ''}{battle_struct['spd_change']} (0x76)",
            f"  • DEF: {'+' if battle_struct['def_change'] > 0 else ''}{battle_struct['def_change']} (0x77)",
            f"  • RES: {'+' if battle_struct['res_change'] > 0 else ''}{battle_struct['res_change']} (0x78)",
            f"  • LCK: {'+' if battle_struct['luk_change'] > 0 else ''}{battle_struct['luk_change']} (0x79)",
            f"Weapon EXP Multiplier: {battle_struct['wexp_multiplier']} (0x7B)",
            f"Damage Dealt: {'Yes' if battle_struct['nonzero_damage'] else 'No'} (0x7C)",
            f"Weapon Broke: {'Yes' if battle_struct['weapon_broke'] else 'No'} (0x7D)"
        ]
    }

    # Build the formatted output
    output = [f"\n=== {struct_name} Battle Data ==="]

    for section, items in sections.items():
        output.append(f"\n{section}:")
        for item in items:
            output.append(f"  {item}")

    return "\n".join(output)

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

            # Display battle struct info in a more human-readable format
            attacker, defender = parse_battle_structs_from_state_file(state_file_path)
            print("\n=== BATTLE DATA ===")
            if attacker:
                parsed_attacker = parse_battle_struct(state_file_path, 'attacker')
                if parsed_attacker:
                    print(format_battle_struct(parsed_attacker, "Attacker"))
                else:
                    print("Attacker: None")
            else:
                print("Attacker: None")

            if defender:
                parsed_defender = parse_battle_struct(state_file_path, 'defender')
                if parsed_defender:
                    print(format_battle_struct(parsed_defender, "Defender"))
                else:
                    print("Defender: None")
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
