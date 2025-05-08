# EmblemMind: Fire Emblem 7 Tactical AI

> Monte Carlo-inspired tactical AI for Fire Emblem 7 (Blazing Sword) using emulator memory analysis and simulated planning.

---

## Project Motivation

Fire Emblem 7 (FE7) is a classic tactical RPG for the Game Boy Advance. The goal of this project was to build an AI agent capable of playing FE7 intelligently by reading the game state directly from emulator memory, simulating possible actions, and controlling the game via automated input. This project explores reinforcement learning and planning in a complex, partially observable, turn-based environment.

---

## What Was Accomplished

- **Full memory extraction** of map, units, and game state from FE7 running in BizHawk via custom Lua scripts.
- **Internal game state modeling** in Python, including map, units, items, and turn phase.
- **Action generation and evaluation** for all player units, including move, attack, item use, and wait.
- **Heuristic and neural network-based action scoring** using PyTorch.
- **Automated input control** to play the game via BizHawk, including cursor movement, menu navigation, and action execution.
- **Reinforcement learning loop** with experience replay and reward shaping.
- **Robust error handling and recovery** for emulator state inconsistencies.
- **Memory manipulation tools** for debugging and testing gameplay scenarios.

## What WASN'T Accomplished
- **Full-scale operational gameplay** of maps and levels; AI lacks complex decision-making and long-term strategizing capabilities
- **Detailed item-usage and tactical character movement**
- **That being said...** there's lots of room for improvement and this project is one that will hopefully (since it's public) be picked up by members of the FEUniverse community to be able to continue development and innovation.

---

## Running the AI Agent

To run the AI agent, follow these steps:

1. **Set Up BizHawk and FE7**
   - Load the Fire Emblem 7 ROM (`gba/fe7.gba`) in BizHawk
   - Navigate to a battle map in-game (Lyn or Eliwood/Hector mode)

2. **Load the Lua Scripts**
   - In BizHawk, open the Lua Console (`Tools > Lua Console`)
   - Load and run these two scripts:
     - `fe_memory_reader.lua`: Extracts game state to text files
     - `listen_input.lua`: Enables the AI to control the game

3. **Run the AI**
   - Execute the main AI script:
   ```
   python trial_run_agent.py
   ```
   - The AI will begin analyzing the game state, generating possible actions, and controlling units

4. **Monitoring AI Behavior**
   - Check the console output to see the AI's decision-making process
   - The AI first probes unit movement ranges, then evaluates combat options
   - Watch as it controls units and engages enemies based on its tactical evaluation

## Demo GIF of the AI in Action

![](https://github.com/Wreaperz/EmblemMind/blob/main/videos/FE7-Demo1.gif)

As shown in the GIF:
- The AI gathers data on unit movement ranges by selecting units and moving the cursor
- It analyzes battle outcomes by navigating to the combat forecast screen
- Based on this data, it executes the actions it evaluates as optimal

---

## Technical Architecture

### Core AI Components

The AI agent operates through several coordinated systems:

1. **State Extraction** (`fe_memory_reader.lua`)
   - Reads FE7's memory structures directly from BizHawk
   - Outputs structured data to `data/fe_state.txt` and `data/fe_map.txt`

2. **Game State Modeling** (`emblemmind_snapshot.py`)
   - Parses text files into Python objects representing the game state
   - Provides interface for querying unit stats, terrain, and other game data

3. **Action Generation** (`agent/action_generator.py`)
   - Creates all possible actions for player units
   - Includes movement, attacks, item usage, and waiting

4. **Action Evaluation** (`agent/state_evaluator.py`, `neural_network.py`)
   - Scores actions based on heuristics and neural network predictions
   - Considers factors like terrain advantages, weapon effectiveness, and unit safety

5. **Action Execution** (`agent/bizhawk_controller.py`)
   - Translates high-level actions into input sequences
   - Controls BizHawk through the Lua interface

### Memory Reading & Game State Extraction

The core of EmblemMind is its ability to read the game's memory state directly from the BizHawk emulator:

1. **Memory Mapping**: Uses exact CodeBreaker memory addresses to locate game data structures.
2. **Memory Structure Access**:
   - Character data (0x0202BD50): Stats, position, items, weapon ranks
   - Enemy units (0x0202CEC0): Same structure as character data
   - Map terrain (0x0202E3D8): Width, height, and terrain grid
   - Battle structs (0x0203A3F0): Combat stats and calculations
   - Turn phase (0x0202BC07): Player (0x00), Neutral (0x40), or Enemy (0x80) phase

### Input Control System

The AI controls the game through:

1. **listen_input.lua**: Script running in BizHawk that executes joypad inputs
2. **Keyboard Automation**: Alternative input method using the `keyboard` Python package
3. **Action Coordination**: Manages input timing and sequences for complex game actions

---

## Complete Project Structure

```
EmblemMind/
├── agent/                    # AI agent components
│   ├── action_coordinator.py # Coordinates action generation and evaluation
│   ├── action_generator.py   # Generates possible actions for units
│   ├── bizhawk_controller.py # Manages input to BizHawk
│   ├── neural_network.py     # Neural network for action evaluation
│   └── state_evaluator.py    # Heuristic state evaluation
├── BizHawk/                  # BizHawk emulator files
├── data/                     # Data files generated/used by the system
│   ├── fe_map.txt            # Current map terrain data
│   ├── fe_state.txt          # Current game state data
│   ├── fe_output.txt         # Debug output
│   ├── ram_edit_command.txt  # Commands for memory editing
│   ├── spritemaps/           # Sprite mapping data
│   └── tilemaps/             # Tilemap data
├── documentation/            # Documentation files
│   ├── RAM Offset Notes.txt  # Memory address documentation
│   └── previous work/        # Reference documentation
├── gba/                      # Game ROM files
│   ├── fe7.gba               # Fire Emblem 7 ROM (primary)
│   └── saves/                # Save files
├── utils/                    # Utility functions
│   ├── fe_data_mappings.py   # Maps numeric IDs to game objects
│   ├── fe_state_parser.py    # Parses fe_state.txt
│   └── send_input.py         # Utility for sending inputs
├── videos/                   # Demo videos and GIFs
├── action_coordinator.py     # Main action coordination (root version)
├── emblemmind_snapshot.py    # Game state representation
├── fe_memory_reader.lua      # Lua script for memory reading
├── fe_memory_writer.lua      # Lua script for memory writing
├── listen_input.lua          # Lua script for input handling
├── main.py                   # State monitoring script
├── neural_network.py         # Neural network definition (root version)
├── test_control.py           # Test script for input control
├── train_agent.py            # Training script for the AI
└── trial_run_agent.py        # Main entry point for running the AI
```

---

## Measuring Success

- **Success Criteria:**
  - The AI can autonomously complete early FE7 maps without human intervention.
  - The agent avoids critical unit deaths (Eliwood, Hector, Lyn) and maximizes enemy defeats.
  - The agent learns to prefer advantageous terrain and effective attacks over time.
- **Metrics Used:**
  - Number of maps completed without resets.
  - Number of player deaths per episode.
  - Cumulative reward per episode.
  - Qualitative review of move quality and tactical soundness.

---

## Additional Tools and Capabilities

Beyond the core AI functionality, this project includes several supplementary tools for game state analysis and manipulation:

### Real-time Memory Monitoring (`main.py`)

Run `python main.py` to view a real-time display of:
- Current game state and unit statistics
- Map terrain and unit positions
- Movement and attack ranges
- Battle predictions and calculations

This tool is invaluable for understanding the game's internal state and debugging AI behavior.

### RAM Editing Tools (`edit_ram_cli.py` and `fe_memory_writer.lua`)

For testing scenarios or manipulating the game state, you can use:

```
python edit_ram_cli.py
```

This CLI tool allows you to:
- Edit unit stats (HP, STR, SKL, etc.)
- Modify inventory items and uses
- Apply various "cheats" for testing purposes

Commands are sent to the game via `fe_memory_writer.lua`, which monitors `data/ram_edit_command.txt` and writes to BizHawk's memory.

---

## Notes and Troubleshooting
- **BizHawk must remain focused** for input automation to work.
- **Lua scripts must be running** at all times during agent operation.
- If the agent gets stuck, try resetting BizHawk and reloading the Lua scripts.
- For best results, use the US version of FE7 and BizHawk 2.9+.
- **Common Issues**:
  - If memory reading fails, check that the correct ROM version is loaded
  - Input issues often relate to window focus - ensure BizHawk remains the active window

---

## License
This project is for academic/research purposes only. Fire Emblem is © Nintendo/Intelligent Systems. ROMs are not distributed.
