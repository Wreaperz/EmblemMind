#!/usr/bin/env python3
"""
EmblemMind - Fire Emblem GBA AI Agent
Main entry point for running the agent
"""

import os
import sys
import time
import argparse
from core.emulator_interface import EmulatorInterface
from core.state_parser import StateParser
from core.map_reader import MapReader
from agent.strategy import MCTSAgent
from agent.actions import ActionGenerator

def parse_arguments():
    """Parse command line arguments for the application."""
    parser = argparse.ArgumentParser(description='EmblemMind - Fire Emblem GBA AI Agent')
    parser.add_argument('--rom', type=str, default='data/fe7.gba', help='Path to the ROM file')
    parser.add_argument('--emulator', type=str, default='bizhawk', choices=['bizhawk', 'mgba'],
                        help='Emulator to connect to (bizhawk or mgba)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--chapter', type=int, help='Target specific chapter')
    parser.add_argument('--headless', action='store_true', help='Run without GUI')
    return parser.parse_args()

def initialize_system(args):
    """Initialize the core system components."""
    print(f"Initializing EmblemMind AI system...")

    # Setup emulator interface
    emulator = EmulatorInterface(emulator_type=args.emulator)

    # Initialize game state parser
    state_parser = StateParser(emulator)

    # Initialize map reader
    map_reader = MapReader()

    # Initialize AI components
    action_generator = ActionGenerator(state_parser)
    agent = MCTSAgent(action_generator, state_parser)

    return emulator, state_parser, map_reader, agent

def main():
    """Main entry point for the EmblemMind AI agent."""
    args = parse_arguments()

    # Initialize components
    emulator, state_parser, map_reader, agent = initialize_system(args)

    print("Connecting to emulator...")
    if not emulator.connect():
        print("Failed to connect to emulator. Ensure it's running and accessible.")
        return 1

    print("EmblemMind AI is running. Press Ctrl+C to exit.")

    try:
        # Main AI loop
        while True:
            # Read current game state
            game_state = state_parser.get_game_state()

            if not game_state:
                print("Waiting for valid game state...")
                time.sleep(1)
                continue

            # Only act during player phase
            if game_state.phase == "Player":
                print(f"Player phase (Turn {game_state.turn})")

                # Generate best move using MCTS
                best_move = agent.get_best_move(game_state)

                if best_move:
                    print(f"Executing move: {best_move}")
                    agent.execute_move(best_move)
                else:
                    print("No valid moves found, waiting...")

            # Sleep to avoid excessive CPU usage
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\nExiting EmblemMind AI...")

    return 0

if __name__ == "__main__":
    sys.exit(main())