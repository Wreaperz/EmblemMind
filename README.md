# Fire Emblem AI: Project EmblemMind

> Monte Carlo-inspired tactical AI for Fire Emblem 6/7/8 using emulator memory analysis and simulated planning.

---

## Project Goal

**EmblemMind** is an AI framework designed to play Fire Emblem GBA titles (6, 7, or 8) via emulator automation and game state simulation. The goal is to build a turn-based AI agent that plans out intelligent moves using:
- Heuristic scoring
- Lightweight Monte Carlo Tree Search (MCTS)-like planning
- Game state extraction from memory
- Emulator-controlled decision execution

This project is a **1-month challenge** to create a functional and interesting AI agent that can reasonably beat early maps or assist a human player with high-quality move suggestions.

---

## Supported Games

| Game Title        | Code Name  | Region | Notes |
|-------------------|------------|--------|-------|
| Fire Emblem 7     | FE7        | NA     | "Blazing Sword" |

---

## AI Design Summary

The Official AI Documentation Thread: https://feuniverse.us/t/fe7-the-official-ai-documentation-thread/348

The AI reads the current game state from an emulator's memory, simulates possible actions for the player’s units, and selects the best move using a lightweight planning method inspired by Monte Carlo Tree Search.

### Key Features:
- **Memory Extraction**: Uses memory reading (or Lua scripting) to extract map and unit data.
- **Game Logic Model**: Internal simulator to predict outcomes (attacks, movement, etc.).
- **AI Engine**:
  - **Heuristic Scoring** for evaluating unit actions.
  - **Shallow Tree Planning** to simulate multi-turn outcomes.
- **Input Automation**: Emulates keypresses to control units.

---

## Project Structure

```
emblemmind/
│
├── ai/
│   ├── mcts.py                # Monte Carlo-esque search logic
│   ├── heuristics.py          # Action scoring and rules
│   └── planner.py             # Turn simulation engine
│
├── emulator/
│   ├── reader.py              # Memory reading and RAM mapping
│   ├── controller.py          # Input automation
│   └── lua_hooks/             # Scripts for BizHawk/mGBA
│
├── game/
│   ├── gamestate.py           # Internal game state model
│   ├── unit.py                # Unit class abstraction
│   └── combat.py              # Battle prediction and damage logic
│
├── scripts/
│   ├── run_ai.py              # Main loop to run the AI
│   └── test_scenarios.py      # Simulated battles for debugging
│
├── assets/
│   └── maps/                  # JSON-formatted level layouts (optional)
│
├── README.md
└── requirements.txt
```

---


## State Space Description (Apr 18 Project Update)
Natural Language

The state includes:

    Map terrain grid (e.g., Forest, River, Wall)

    Positions and stats of all player and enemy units

    Turn phase (Player, Enemy, NPC)

    Unit status effects (e.g., Sleep, Poison)

    Inventories and items

    Map changes (e.g., broken walls, open doors)

The environment is turn-based, partially observable (e.g., fog of war), and stochastic due to combat RNG.
Mathematical

    S: Set of all game states

    A: Set of all actions

    T(s, a, s′): Transition function (stochastic)

    R(s, a): Reward function

    O(s′, o): Observation function (fog of war)

Each state s includes:

    Terrain map: Map ∈ ℕ^{H×W}

    Unit list: position, stats, items, status

    Turn phase ∈ {Player, Enemy, NPC}

    Objective flags ∈ {0,1}

Actions include move, attack, item use, and wait.


## Tech Stack

| Component        | Tool/Language           | Notes |
|------------------|--------------------------|-------|
| Emulator         | BizHawk or mGBA          | Lua scripting or memory hooks |
| Core AI          | Python                   | Planning, heuristics, simulation |
| Visualization    | Pygame / Console ASCII   | Optional battle log / AI display |
| Input Control    | PyAutoGUI / Lua          | Emulator automation |
