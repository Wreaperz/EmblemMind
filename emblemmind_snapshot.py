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
                is_enemy=is_enemy
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
                self.is_visible)

    @property
    def has_acted(self) -> bool:
        """Check if the unit has already acted this turn"""
        # 0x42 = moved, 0x52 = rescuer moved
        return self.turn_status in [0x42, 0x52]

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
    def level(self) -> int:
        """Get the unit's level"""
        return self.stats[7] if len(self.stats) > 7 else 0

    @property
    def class_name(self) -> str:
        """Get the unit's class name"""
        return get_class_name(self.class_id)

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
    phase: str  # "Player", "Enemy", "Other"
    cursor_position: Tuple[int, int]
    map: TerrainMap
    units: List[Unit]
    enemies: List[Unit]

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
            if unit and unit.is_alive and unit.is_visible:  # Only include alive and visible enemies
                enemies.append(unit)

        # Create terrain map
        terrain_map = TerrainMap(
            width=map_data['width'],
            height=map_data['height'],
            grid=map_data['terrain_grid'],
            legend=map_data['legend']
        )

        # Create snapshot
        return cls(
            current_turn=state_data['game_state'].get('current_turn', 0),
            chapter_id=state_data['game_state'].get('chapter_id', 0),
            phase=state_data['game_state'].get('phase', 'Unknown'),
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