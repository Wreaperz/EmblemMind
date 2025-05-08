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

---

<video src="videos/FE7-Demo1.mp4" autoplay loop muted playsinline style="max-width: 100%; height: auto;"></video>

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

## Software and Hardware Requirements

- **Operating System:** Windows 10/11 (required for BizHawk and pywinauto)
- **Emulator:** [BizHawk 2.9+](https://tasvideos.org/BizHawk/ReleaseHistory) (tested on 2.9.1)
- **Game ROM:** Fire Emblem 7 (Blazing Sword) US GBA ROM (not included)
- **Python:** 3.8+
- **Hardware:**
  - CPU: Any modern x86_64 processor
  - RAM: 4GB minimum
  - Disk: <100MB for code and data

### Python Dependencies

Install all dependencies with:

```
pip install -r requirements.txt
```

**requirements.txt** includes:
- numpy
- torch
- matplotlib
- pytest
- pywinauto
- pyautogui
- keyboard

---

## Data Sources

- **Game Data:** Extracted live from FE7 running in BizHawk using custom Lua scripts.
- **No external datasets** are required; all data is generated from emulator memory.
- **Official AI Documentation:** https://feuniverse.us/t/fe7-the-official-ai-documentation-thread/348

---

## Project Structure (Key Files)

```
EmblemMind/
├── agent/
│   ├── action_coordinator.py
│   ├── action_generator.py
│   ├── bizhawk_controller.py
│   ├── neural_network.py
│   └── state_evaluator.py
├── utils/
│   ├── fe_data_mappings.py
│   ├── fe_state_parser.py
│   └── send_input.py
├── fe_memory_reader.lua      # Lua script for BizHawk: dumps game state to data/fe_state.txt
├── listen_input.lua          # Lua script for BizHawk: listens for input commands
├── trial_run_agent.py        # Main Python entry point for running the AI
├── requirements.txt
└── README.md
```

---

## How to Reproduce (Step-by-Step)

### 1. Set Up BizHawk and FE7
- Download and extract [BizHawk](https://tasvideos.org/BizHawk/ReleaseHistory) (2.9+ recommended).
- Obtain a US version of the Fire Emblem 7 GBA ROM (included in /gba).
- Launch BizHawk, open the FE7 ROM (gba/fe7.gba).

### 2. Load Lua Scripts in BizHawk
- In BizHawk, go to `Tools > Lua Console`.
- In the Lua Console, load and run both scripts:
  1. `fe_memory_reader.lua` (outputs game state to `data/fe_state.txt` and `data/fe_map.txt`)
  2. `listen_input.lua` (enables external input control)
- Both scripts must be running for the AI to function.

### 3. Install Python Dependencies
- Open a terminal in the project root directory.
- Run:
  ```
  pip install -r requirements.txt
  ```

### 4. Run the AI Agent
- With BizHawk and the Lua scripts running, start the agent:
  ```
  python trial_run_agent.py
  ```
- The agent will read the game state, plan actions, and control the game automatically.

---

## State Space Description

The state includes:
- Map terrain grid (e.g., Forest, River, Wall)
- Positions and stats of all player and enemy units
- Turn phase (Player, Enemy, NPC)
- Unit status effects (e.g., Sleep, Poison)
- Inventories and items
- Map changes (e.g., broken walls, open doors)

The environment is turn-based, partially observable (e.g., fog of war), and stochastic due to combat RNG.

---

## Tech Stack

| Component        | Tool/Language           | Notes |
|------------------|------------------------|-------|
| Emulator         | BizHawk (Lua scripting)| Memory extraction, input control |
| Core AI          | Python 3.8+            | Planning, heuristics, simulation |
| Neural Network   | PyTorch                | Action evaluation |
| Automation       | pywinauto, pyautogui   | Window focus, input scripting |
| Data Handling    | numpy                  | State representation |

---

## Notes and Troubleshooting
- **BizHawk must remain focused** for input automation to work.
- **Lua scripts must be running** at all times during agent operation.
- If the agent gets stuck, try resetting BizHawk and reloading the Lua scripts.
- For best results, use the US version of FE7 and BizHawk 2.9+.

---

## License
This project is for academic/research purposes only. Fire Emblem is © Nintendo/Intelligent Systems. ROMs are not distributed.
