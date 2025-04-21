#!/usr/bin/env python3

class FEStateParser:
    """Parser for Fire Emblem state data from fe_state.txt"""

    @staticmethod
    def parse_state_file(file_path):
        """
        Parse a Fire Emblem state file into structured data

        Args:
            file_path (str): Path to the state file

        Returns:
            dict: Dictionary with game_state, characters, and enemies
        """
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()

            result = {
                'game_state': {},
                'characters': [],
                'enemies': []
            }

            section = None
            current_entity = None

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Check for section headers
                if line == "GAME_STATE":
                    section = "game_state"
                    continue
                elif line == "CHARACTERS":
                    section = "characters"
                    continue
                elif line == "ENEMIES":
                    section = "enemies"
                    continue

                # Process entities
                if section == "characters" and line.startswith("character="):
                    current_entity = {}
                    result['characters'].append(current_entity)
                    continue
                elif section == "enemies" and line.startswith("enemy="):
                    current_entity = {}
                    result['enemies'].append(current_entity)
                    continue

                # Process key-value pairs
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()

                    if section == "game_state":
                        result['game_state'][key] = FEStateParser._convert_value(key, value)
                    elif (section == "characters" or section == "enemies") and current_entity is not None:
                        current_entity[key] = FEStateParser._convert_value(key, value)

            return result
        except Exception as e:
            print(f"Error parsing state file: {e}")
            return None

    @staticmethod
    def _convert_value(key, value):
        """Convert values to appropriate types based on key names"""
        # Character ID and Class ID - these are hexadecimal values from CodeBreaker
        # In fe_state.txt they are stored as decimal but we need to convert them to hex
        if key == "id":
            try:
                # Just convert to integer, our mapping will handle the proper ID
                return int(value)
            except ValueError:
                return value
        elif key == "class":
            try:
                # Just convert to integer, our mapping will handle the proper ID
                return int(value)
            except ValueError:
                return value

        # Special case for position
        if key == "position" and "," in value:
            return tuple(map(int, value.split(",")))

        # Special case for hp
        if key == "hp" and "," in value:
            return tuple(map(int, value.split(",")))

        # Special case for stats
        if key == "stats" and "," in value:
            return tuple(map(int, value.split(",")))

        # Special case for items (comma-separated list of item IDs)
        if key == "items":
            items = []
            if value:
                item_strings = value.strip(",").split(",")
                for item_str in item_strings:
                    if ":" in item_str:
                        item_id, uses = item_str.split(":")
                        items.append((int(item_id), int(uses)))
            return items

        # Integer values
        if key in ("current_turn", "chapter_id", "gold", "cursor_x", "cursor_y",
                  "camera_x", "camera_y", "level", "exp"):
            try:
                return int(value)
            except ValueError:
                return value

        # Keep raw values as strings
        return value

    @staticmethod
    def get_unit_at_position(state_data, x, y):
        """
        Find a unit (character or enemy) at the given position

        Args:
            state_data (dict): Parsed state data
            x (int): X coordinate
            y (int): Y coordinate

        Returns:
            tuple: (unit_data, "character"/"enemy") or (None, None) if no unit at position
        """
        # Check characters
        for char in state_data['characters']:
            if 'position' in char and char['position'] == (x, y):
                return char, "character"

        # Check enemies
        for enemy in state_data['enemies']:
            if 'position' in enemy and enemy['position'] == (x, y):
                return enemy, "enemy"

        return None, None