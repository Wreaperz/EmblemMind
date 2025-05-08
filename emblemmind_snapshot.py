#!/usr/bin/env python3

from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional
import os
from utils.fe_state_parser import FEStateParser
from utils.fe_data_mappings import (
    get_item_name, get_character_name, get_class_name,
    get_weapon_type
)

@dataclass
class Unit:
    """Represents a unit (character or enemy) in the game state"""
    id: int
    name: str
    class_id: int
    position: Tuple[int, int]
    hp: Tuple[int, int]
    stats: List[int]
    items: List[Tuple[int, int]]
    turn_status: int
    status_effect: int
    is_enemy: bool
    level: int
    exp: int
    raw_struct: bytes = None  # Optionally store the raw character struct bytes

    @classmethod
    def from_raw_data(cls, raw_data: dict, is_enemy: bool = False) -> Optional['Unit']:
        """Create a Unit object from raw data"""
        try:
            # Only create units that are alive and visible (for enemies)
            if is_enemy and (raw_data.get('hp', (0, 0))[0] <= 0 or raw_data.get('turn_status', 0) == 0x81):
                return None

            # Ensure turn_status is an integer
            turn_status = raw_data.get('turn_status', 0)
            if isinstance(turn_status, str):
                # Try to convert from hex string if it starts with 0x
                if turn_status.startswith('0x'):
                    turn_status = int(turn_status, 16)
                else:
                    turn_status = int(turn_status)

            return cls(
                id=raw_data.get('id', 0),
                name=get_character_name(raw_data.get('id', 0)),
                class_id=raw_data.get('class', 0),
                position=tuple(raw_data.get('position', (0, 0))),
                hp=tuple(raw_data.get('hp', (0, 0))),
                stats=raw_data.get('stats', [0] * 9),
                items=raw_data.get('items', []),
                turn_status=turn_status,
                status_effect=raw_data.get('status_effect', 0),
                is_enemy=is_enemy,
                level=raw_data.get('level', 0),
                exp=raw_data.get('exp', 0),
                raw_struct=raw_data.get('raw_struct', None)
            )
        except Exception as e:
            print(f"Error creating unit: {e}")
            return None

    @property
    def turn_status_text(self) -> str:
        """Get human-readable text for the unit's turn status"""
        status_map = {
            0x00: "Not moved",
            0x01: "Chosen for Level",
            0x09: "Not Chosen for Level",
            0x0B: "Chosen for Level",
            0x0D: "Dead",
            0x10: "Rescuer, not moved",
            0x02: "Moved",
            0x42: "Moved",
            0x52: "Rescuer, moved",
            0x21: "Rescued",
            0x81: "Invisible (under roof)"
        }
        return status_map.get(self.turn_status, f"Unknown (0x{self.turn_status:02X})")

    @property
    def status_effect_text(self) -> str:
        """Get human-readable text for the unit's status effect"""
        if self.status_effect == 0:
            return "None"

        turns = self.status_effect // 16
        effect = self.status_effect % 16

        effect_map = {
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

        effect_name = effect_map.get(effect, "Unknown")
        turns_text = "∞" if turns == 0 else str(turns)
        return f"{effect_name} ({turns_text} turns)"

    @property
    def is_alive(self) -> bool:
        """Check if the unit is alive"""
        return self.hp[0] > 0

    @property
    def can_act(self) -> bool:
        """Check if the unit can act this turn"""
        # Units can't act if they're rescued, have already moved, or are invisible
        return (self.is_alive and
                not self.is_rescued and
                not self.has_acted and
                self.is_visible and self.turn_status != 0x02)

    @property
    def has_acted(self) -> bool:
        """Check if the unit has already acted this turn"""
        # 0x02 = moved, 0x42 = moved, 0x52 = rescuer moved
        return self.turn_status in [0x02, 0x42, 0x52]

    @property
    def is_visible(self) -> bool:
        """Check if the unit is visible (not under a roof)"""
        # 0x81 = invisible (under roof)
        return self.turn_status != 0x81

    @property
    def is_rescued(self) -> bool:
        """Check if the unit is being rescued"""
        # 0x21 = rescued
        return self.turn_status == 0x21

    @property
    def is_rescuer(self) -> bool:
        """Check if the unit is rescuing another unit"""
        # 0x10 = rescuer not moved, 0x52 = rescuer moved
        return self.turn_status in [0x10, 0x52]

    @property
    def movement_range(self) -> int:
        """Get the unit's movement range"""
        return self.stats[6] if len(self.stats) > 6 else 0

    @property
    def class_name(self) -> str:
        """Get the unit's class name"""
        return get_class_name(self.class_id)

    @property
    def drops_item(self) -> bool:
        """Check if the unit will drop an item (0x10 bit in byte 0x0D of character struct)"""
        if self.raw_struct and len(self.raw_struct) > 0x0D:
            return (self.raw_struct[0x0D] & 0x10) != 0
        # Fallback: try to get from raw_data if available as 'char_struct_0D'
        if hasattr(self, 'char_struct_0D'):
            return (self.char_struct_0D & 0x10) != 0
        return False

@dataclass
class TerrainMap:
    """Represents the map terrain data"""
    width: int
    height: int
    grid: List[List[str]]  # 2D grid of terrain symbols
    legend: Dict[int, str]  # Mapping of terrain symbols to names

    def get_terrain_at(self, x: int, y: int) -> str:
        """Get terrain symbol at given coordinates"""
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.grid[y][x]
        return None

@dataclass
class TurnSnapshot:
    """Represents the complete game state at a given turn"""
    current_turn: int
    chapter_id: int
    turn_phase: int  # 0x00 = Player, 0x40 = Neutral, 0x80 = Enemy
    cursor_position: Tuple[int, int]
    map: TerrainMap
    units: List[Unit]
    enemies: List[Unit]

    @property
    def phase_text(self) -> str:
        """Get human-readable text for the current turn phase"""
        phase_map = {
            0x00: "Player",
            0x40: "Neutral",
            0x80: "Enemy"
        }
        return phase_map.get(self.turn_phase, f"Unknown (0x{self.turn_phase:02X})")

    @classmethod
    def from_files(cls, state_file_path: str, map_file_path: str) -> 'TurnSnapshot':
        """
        Create a TurnSnapshot from the state and map files

        Args:
            state_file_path: Path to fe_state.txt
            map_file_path: Path to fe_map.txt

        Returns:
            TurnSnapshot object
        """
        # Parse state data
        state_data = FEStateParser.parse_state_file(state_file_path)
        if not state_data:
            raise ValueError("Failed to parse state file")

        # Parse map data
        map_data = cls._parse_map_file(map_file_path)
        if not map_data:
            raise ValueError("Failed to parse map file")

        # Create units
        units = []
        enemies = []

        # Process characters
        for char_data in state_data['characters']:
            unit = cls._create_unit(char_data, is_enemy=False)
            if unit and unit.is_alive:  # Only include alive units
                units.append(unit)

        # Process enemies
        for enemy_data in state_data['enemies']:
            unit = cls._create_unit(enemy_data, is_enemy=True)
            # IMPORTANT - THIS CONTROLS WHETHER ENEMIES ARE MARKED OR NOT (SEEN AND UNSEEN)
            if unit and unit.is_alive:# and unit.is_visible:  # Only include alive and visible enemies
                enemies.append(unit)

        # Create terrain map
        terrain_map = TerrainMap(
            width=map_data['width'],
            height=map_data['height'],
            grid=map_data['terrain_grid'],
            legend=map_data['legend']
        )

        # Get turn_phase from turn_phase_raw
        turn_phase = state_data['game_state'].get('turn_phase_raw', 0)
        if isinstance(turn_phase, str):
            if turn_phase.startswith('0x'):
                turn_phase = int(turn_phase, 16)
            else:
                turn_phase = int(turn_phase)

        # Create snapshot
        return cls(
            current_turn=state_data['game_state'].get('current_turn', 0),
            chapter_id=state_data['game_state'].get('chapter_id', 0),
            turn_phase=turn_phase,
            cursor_position=(
                state_data['game_state'].get('cursor_x', 0),
                state_data['game_state'].get('cursor_y', 0)
            ),
            map=terrain_map,
            units=units,
            enemies=enemies
        )

    @staticmethod
    def _parse_map_file(map_file_path: str) -> Optional[Dict]:
        """Parse the map file into a dictionary"""
        try:
            if not os.path.exists(map_file_path):
                return None

            with open(map_file_path, 'r') as f:
                lines = f.readlines()

            if not lines or len(lines) < 3:
                return None

            # Parse dimensions
            header = lines[0].strip()
            if not header.startswith("Map size:"):
                return None

            dimensions = header.replace("Map size:", "").strip()
            width, height = map(int, dimensions.split('x'))

            # Parse terrain grid
            terrain_grid = []
            terrain_start = 2
            terrain_end = terrain_start + height

            for y in range(terrain_start, terrain_end):
                if y < len(lines):
                    row_data = lines[y].strip().split()
                    terrain_grid.append(row_data)

            # Parse legend
            legend = {}
            for i in range(terrain_end, len(lines)):
                line = lines[i].strip()
                if line.startswith("Terrain Legend:"):
                    legend_start = i + 1
                    for j in range(legend_start, len(lines)):
                        legend_line = lines[j].strip()
                        if not legend_line or legend_line.startswith("Terrain pointer"):
                            break
                        legend[j - legend_start] = legend_line

            return {
                'width': width,
                'height': height,
                'terrain_grid': terrain_grid,
                'legend': legend
            }

        except Exception as e:
            print(f"Error parsing map file: {e}")
            return None

    @staticmethod
    def _create_unit(raw_data: dict, is_enemy: bool = False) -> Optional['Unit']:
        """Create a Unit object from raw data"""
        try:
            # For enemies: only create if alive and visible
            if is_enemy and (raw_data.get('hp', (0, 0))[0] <= 0 or raw_data.get('turn_status', 0) == 0x81):
                return None

            # For player units: only create if chosen for the level and not dead
            if not is_enemy:
                turn_status = raw_data.get('turn_status', 0)
                if isinstance(turn_status, str):
                    if turn_status.startswith('0x'):
                        turn_status = int(turn_status, 16)
                    else:
                        turn_status = int(turn_status)

                # Skip units that aren't chosen for the level or are dead
                if turn_status in [0x09, 0x0B, 0x0D]:
                    return None

            return Unit.from_raw_data(raw_data, is_enemy)
        except Exception as e:
            print(f"Error creating unit: {e}")
            return None

    def get_unit_at(self, x: int, y: int) -> Optional[Unit]:
        """Get the unit at the given position"""
        for unit in self.units + self.enemies:
            if unit.position == (x, y):
                return unit
        return None

    def get_visible_enemies(self) -> List[Unit]:
        """Get list of visible enemies (not hidden)"""
        return [enemy for enemy in self.enemies if enemy.is_alive and enemy.is_visible]

    def get_available_units(self) -> List[Unit]:
        """Get list of units that can act this turn"""
        return [unit for unit in self.units if unit.can_act and not unit.is_rescued]

    @staticmethod
    def parse_fe_map_file(map_file_path):
        """Parse the map terrain data from fe_map.txt, including debug info and legend."""
        try:
            if not os.path.exists(map_file_path):
                return None
            map_data = {
                "width": 0,
                "height": 0,
                "terrain_grid": [],
                "debug_info": {},
                "legend": {}
            }
            with open(map_file_path, 'r') as f:
                lines = f.readlines()
            if not lines or len(lines) < 3:
                return None
            header = lines[0].strip()
            if header.startswith("Map size:"):
                dimensions = header.replace("Map size:", "").strip()
                width, height = map(int, dimensions.split('x'))
                map_data["width"] = width
                map_data["height"] = height
            terrain_start = 2
            terrain_end = terrain_start + map_data["height"]
            for y in range(terrain_start, terrain_end):
                if y < len(lines):
                    row_data = lines[y].strip().split()
                    terrain_row = [symbol for symbol in row_data]
                    map_data["terrain_grid"].append(terrain_row)
            legend_info = {}
            for i in range(terrain_end, len(lines)):
                line = lines[i].strip()
                if line.startswith("Terrain Legend:"):
                    legend_start = i + 1
                    for j in range(legend_start, len(lines)):
                        legend_line = lines[j].strip()
                        if not legend_line or legend_line.startswith("Terrain pointer"):
                            break
                        legend_info[j - legend_start] = legend_line
                elif line and ":" in line:
                    key, value = line.split(":", 1)
                    map_data["debug_info"][key.strip()] = value.strip()
            map_data["legend"] = legend_info
            return map_data
        except Exception as e:
            print(f"Error parsing map file: {e}")
            return None

    @staticmethod
    def display_map(map_data, cursor_x=None, cursor_y=None):
        """Display a simplified ASCII version of the map (for debugging)."""
        if not map_data:
            return
        terrain_grid = map_data["terrain_grid"]
        print("\n=== MAP ===")
        print(f"Dimensions: {map_data['width']}x{map_data['height']}")
        for y, row in enumerate(terrain_grid):
            line = ""
            for x, symbol in enumerate(row):
                if cursor_x is not None and cursor_y is not None and x == cursor_x and y == cursor_y:
                    line += "X "
                else:
                    line += symbol + " "
            print(line)
        print("\nTerrain Legend:")
        for i, legend_line in map_data.get("legend", {}).items():
            print(legend_line)
        print("X = Cursor Position (if shown)")

    @staticmethod
    def parse_realtime_data_from_state_file(state_file_path):
        """Parse the REALTIME_DATA section from fe_state.txt and return a dict."""
        import re
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

    @staticmethod
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

    @staticmethod
    def parse_map_section(state_file_path, section_name):
        """Parse a named section (e.g., MOVEMENT_MAP, RANGE_MAP) from fe_state.txt and return a grid."""
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
                if not line or (line.replace('_', '').isupper() and line.replace('_', '').isalpha()):
                    break
                if not all(all(c in "0123456789ABCDEFabcdef" for c in b) for b in line.split()):
                    break
                row = [int(b, 16) for b in line.split()]
                grid.append(row)
        return grid

    @staticmethod
    def parse_battle_struct(state_file_path, struct='attacker'):
        """Parse the BATTLE_STRUCTS section and return a dict of intuitive fields for the attacker or defender."""
        # Get the raw bytes
        attacker, defender = TurnSnapshot.parse_battle_structs_from_state_file(state_file_path)
        data = attacker if struct == 'attacker' else defender
        if not data:
            return None
        # Map fields using RAM Offset Notes
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