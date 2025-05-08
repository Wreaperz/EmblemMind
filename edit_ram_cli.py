#!/usr/bin/env python3

import os
from utils.fe_state_parser import FEStateParser
from utils.fe_data_mappings import get_item_name, get_character_name, get_class_name

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
STATE_FILE = os.path.join(DATA_DIR, 'fe_state.txt')
COMMAND_FILE = os.path.join(DATA_DIR, 'ram_edit_command.txt')

STAT_CODES = ['hp', 'max_hp', 'str', 'skl', 'spd', 'def', 'res', 'lck', 'mov']
STAT_NAMES = ['HP', 'Max HP', 'STR', 'SKL', 'SPD', 'DEF', 'RES', 'LCK', 'MOV']


def print_units(units):
    for idx, unit in enumerate(units, 1):
        print(f"[{idx}] {get_character_name(unit.get('id', 0))} (Class: {get_class_name(unit.get('class', 0))}) at {unit.get('position', (0, 0))}")


def select_unit(units, prompt):
    while True:
        print(f"\n{prompt}")
        print_units(units)
        sel = input("Enter number (or 'q' to quit): ").strip()
        if sel.lower() == 'q':
            return None
        if sel.isdigit() and 1 <= int(sel) <= len(units):
            return int(sel) - 1
        print("Invalid selection.")


def select_stat():
    print("\nWhich stat do you want to edit?")
    for i, name in enumerate(STAT_NAMES):
        print(f"[{i+1}] {name}")
    sel = input("Enter number (or 'q' to quit): ").strip()
    if sel.lower() == 'q':
        return None
    if sel.isdigit() and 1 <= int(sel) <= len(STAT_CODES):
        return STAT_CODES[int(sel)-1], STAT_NAMES[int(sel)-1]
    print("Invalid selection.")
    return None


def select_item(unit):
    items = unit.get('items', [])
    print("\nCurrent items:")
    for idx, (item_id, uses) in enumerate(items):
        print(f"[{idx}] {get_item_name(item_id)} (ID: {item_id}) - Uses: {uses}")
    sel = input("Select item slot to edit (0-4), or 'a' to add, or 'q' to quit: ").strip()
    if sel.lower() == 'q':
        return None, None
    if sel.lower() == 'a':
        return 'add', None
    if sel.isdigit() and 0 <= int(sel) < 5:
        return int(sel), items[int(sel)] if int(sel) < len(items) else (0, 0)
    print("Invalid selection.")
    return None, None


def write_command(command):
    with open(COMMAND_FILE, 'a') as f:
        f.write(command + '\n')
    print(f"[COMMAND SENT] {command}")


def main():
    print("==== Fire Emblem Real-Time RAM Editor ====")
    print("This tool lets you edit player/enemy stats and items in real time.")
    print("All changes are sent to BizHawk via ram_edit_command.txt.")

    data = FEStateParser.parse_state_file(STATE_FILE)
    if not data:
        print("Failed to parse fe_state.txt")
        return

    while True:
        print("\nWhat do you want to edit?")
        print("1. Player characters")
        print("2. Enemies")
        print("3. Cheats")
        print("4. Exit")
        choice = input("Select option: ").strip()
        if choice == '1':
            units = data['characters']
            unit_type = 'character'
        elif choice == '2':
            units = data['enemies']
            unit_type = 'enemy'
        elif choice == '3':
            print("\nCheats Menu:")
            print("1. Set HP/Max HP to 80 for all player characters")
            print("2. Set all items to 50 uses for all player characters")
            print("3. Add 10 to move stat for all player characters")
            print("4. Add 15 to HP for all player characters")
            print("5. Add 15 to Max HP for all player characters")
            print("6. Add 15 to STR for all player characters")
            print("7. Add 15 to SKL for all player characters")
            print("8. Add 15 to SPD for all player characters")
            print("9. Add 15 to DEF for all player characters")
            print("10. Add 15 to RES for all player characters")
            print("11. Add 15 to LCK for all player characters")
            print("12. Add 15 to MOV for all player characters")
            print("13. Max all weapon ranks for all player characters")
            print("14. Back")
            cheat_choice = input("Select cheat: ").strip()
            if cheat_choice == '1':
                for idx, unit in enumerate(data['characters']):
                    command_hp = f"set_stat character {idx+1} hp 80"
                    command_maxhp = f"set_stat character {idx+1} max_hp 80"
                    write_command(command_hp)
                    write_command(command_maxhp)
                print("Set HP and Max HP to 80 for all player characters.")
            elif cheat_choice == '2':
                for idx, unit in enumerate(data['characters']):
                    items = unit.get('items', [])
                    for slot, (item_id, uses) in enumerate(items):
                        if item_id != 0:
                            command = f"set_item character {idx+1} {slot} {item_id} 50"
                            write_command(command)
                print("Set all item uses to 50 for all player characters.")
            elif cheat_choice == '3':
                for idx, unit in enumerate(data['characters']):
                    stats = unit.get('stats', [0]*9)
                    new_move = stats[6] + 10 if len(stats) > 6 else 10
                    command = f"set_stat character {idx+1} mov {new_move}"
                    write_command(command)
                print("Added 10 to move stat for all player characters.")
            elif cheat_choice == '4':  # +15 HP
                for idx, unit in enumerate(data['characters']):
                    stats = unit.get('stats', [0]*9)
                    hp = unit.get('hp', (0, 0))[0]
                    new_hp = hp + 15
                    command = f"set_stat character {idx+1} hp {new_hp}"
                    write_command(command)
                print("Added 15 to HP for all player characters.")
            elif cheat_choice == '5':  # +15 Max HP
                for idx, unit in enumerate(data['characters']):
                    stats = unit.get('stats', [0]*9)
                    max_hp = unit.get('hp', (0, 0))[1]
                    new_max_hp = max_hp + 15
                    command = f"set_stat character {idx+1} max_hp {new_max_hp}"
                    write_command(command)
                print("Added 15 to Max HP for all player characters.")
            elif cheat_choice == '6':  # +15 STR
                for idx, unit in enumerate(data['characters']):
                    stats = unit.get('stats', [0]*9)
                    new_str = stats[0] + 15 if len(stats) > 0 else 15
                    command = f"set_stat character {idx+1} str {new_str}"
                    write_command(command)
                print("Added 15 to STR for all player characters.")
            elif cheat_choice == '7':  # +15 SKL
                for idx, unit in enumerate(data['characters']):
                    stats = unit.get('stats', [0]*9)
                    new_skl = stats[1] + 15 if len(stats) > 1 else 15
                    command = f"set_stat character {idx+1} skl {new_skl}"
                    write_command(command)
                print("Added 15 to SKL for all player characters.")
            elif cheat_choice == '8':  # +15 SPD
                for idx, unit in enumerate(data['characters']):
                    stats = unit.get('stats', [0]*9)
                    new_spd = stats[2] + 15 if len(stats) > 2 else 15
                    command = f"set_stat character {idx+1} spd {new_spd}"
                    write_command(command)
                print("Added 15 to SPD for all player characters.")
            elif cheat_choice == '9':  # +15 DEF
                for idx, unit in enumerate(data['characters']):
                    stats = unit.get('stats', [0]*9)
                    new_def = stats[4] + 15 if len(stats) > 4 else 15
                    command = f"set_stat character {idx+1} def {new_def}"
                    write_command(command)
                print("Added 15 to DEF for all player characters.")
            elif cheat_choice == '10':  # +15 RES
                for idx, unit in enumerate(data['characters']):
                    stats = unit.get('stats', [0]*9)
                    new_res = stats[5] + 15 if len(stats) > 5 else 15
                    command = f"set_stat character {idx+1} res {new_res}"
                    write_command(command)
                print("Added 15 to RES for all player characters.")
            elif cheat_choice == '11':  # +15 LCK
                for idx, unit in enumerate(data['characters']):
                    stats = unit.get('stats', [0]*9)
                    new_lck = stats[3] + 15 if len(stats) > 3 else 15
                    command = f"set_stat character {idx+1} lck {new_lck}"
                    write_command(command)
                print("Added 15 to LCK for all player characters.")
            elif cheat_choice == '12':  # +15 MOV
                for idx, unit in enumerate(data['characters']):
                    stats = unit.get('stats', [0]*9)
                    new_mov = stats[6] + 15 if len(stats) > 6 else 15
                    command = f"set_stat character {idx+1} mov {new_mov}"
                    write_command(command)
                print("Added 15 to MOV for all player characters.")
            elif cheat_choice == '13':  # Max weapon ranks
                for idx, unit in enumerate(data['characters']):
                    for rank in ['sword','lance','axe','bow','staff','anima','light','dark']:
                        command = f"set_rank character {idx+1} {rank} 251"
                        write_command(command)
                print("Maxed all weapon ranks for all player characters.")
            elif cheat_choice == '14':
                continue
            else:
                print("Invalid cheat option.")
            continue
        elif choice == '4':
            print("Exiting.")
            break
        else:
            print("Invalid option.")
            continue

        idx = select_unit(units, f"Select a {unit_type} to edit:")
        if idx is None:
            continue
        unit = units[idx]
        print(f"\nSelected: {get_character_name(unit.get('id', 0))} (Class: {get_class_name(unit.get('class', 0))})")
        print(f"  Position: {unit.get('position', (0, 0))}")
        print(f"  Stats: {unit.get('stats', [0]*9)}")
        print(f"  Items: {unit.get('items', [])}")

        while True:
            print("\nWhat do you want to edit?")
            print("1. Stats")
            print("2. Items")
            print("3. Back")
            sub = input("Select option: ").strip()
            if sub == '1':
                stat_code, stat_name = select_stat() or (None, None)
                if not stat_code:
                    continue
                new_val = input(f"Enter new value for {stat_name}: ").strip()
                if not new_val.isdigit():
                    print("Invalid value.")
                    continue
                command = f"set_stat {unit_type} {idx+1} {stat_code} {int(new_val)}"
                write_command(command)
            elif sub == '2':
                slot, item = select_item(unit)
                if slot is None:
                    continue
                if slot == 'add':
                    item_id = input("  Enter new item ID: ").strip()
                    uses = input("  Enter uses: ").strip()
                    if not (item_id.isdigit() and uses.isdigit()):
                        print("  Invalid input.")
                        continue
                    # Find first empty slot
                    for s in range(5):
                        if s >= len(unit.get('items', [])) or unit['items'][s][0] == 0:
                            slot = s
                            break
                    else:
                        print("  No empty item slots.")
                        continue
                    command = f"set_item {unit_type} {idx+1} {slot} {int(item_id)} {int(uses)}"
                    write_command(command)
                else:
                    item_id = input(f"  New item ID (current {item[0]}): ").strip()
                    uses = input(f"  New uses (current {item[1]}): ").strip()
                    new_id = int(item_id) if item_id.isdigit() else item[0]
                    new_uses = int(uses) if uses.isdigit() else item[1]
                    command = f"set_item {unit_type} {idx+1} {slot} {new_id} {new_uses}"
                    write_command(command)
            elif sub == '3':
                break
            else:
                print("Invalid option.")

if __name__ == "__main__":
    main()