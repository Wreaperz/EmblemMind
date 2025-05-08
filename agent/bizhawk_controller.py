import time
import keyboard
import pygetwindow as gw
import os

# Mapping of GBA controls to key names or file actions
GBA_KEY_MAP = {
    'A': 'x',      # GBA A button
    'B': 'z',      # GBA B button
    'L': 'w',      # GBA L bumper
    'R': 'e',      # GBA R bumper
    'START': 'enter',  # GBA Start/Select
    'UP': 'UP',
    'DOWN': 'DOWN',
    'LEFT': 'LEFT',
    'RIGHT': 'RIGHT',
    'RESET': 'p'
}

BIZHAWK_WINDOW_TITLE = 'Fire Emblem (USA, Australia) [Gameboy Advance]'  # Partial window title (case-insensitive)

_last_focus_time = 0

def focus_bizhawk():
    """Focus the BizHawk window by partial title."""
    global _last_focus_time
    try:
        windows = gw.getWindowsWithTitle(BIZHAWK_WINDOW_TITLE)
        if not windows:
            print(f"BizHawk window with title containing '{BIZHAWK_WINDOW_TITLE}' not found.")
            return False
        win = windows[0]
        win.activate()
        time.sleep(0.5)  # Give time for focus
        _last_focus_time = time.time()
        return True
    except Exception as e:
        print(f"Error focusing BizHawk: {e}")
        return False

def press_key(key, duration=0.05):
    time.sleep(0.02)
    """Press a single key for the given duration (in seconds). Arrow keys use file-based input, others use keyboard lib."""
    if key in ['UP', 'DOWN', 'LEFT', 'RIGHT']:
        # Write to file for Lua script to pick up
        input_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../data/emblemmind_input.txt')
        with open(input_file, 'w') as f:
            f.write(key)
        time.sleep(duration)
    else:
        keyboard.press(key)
        time.sleep(duration)
        keyboard.release(key)
    time.sleep(0.02)

def press_keys(keys, duration=0.1):
    """Press multiple keys in sequence for the given duration each."""
    for key in keys:
        press_key(key, duration)
        time.sleep(0.05)

def press_reset():
    press_key(GBA_KEY_MAP['RESET'])