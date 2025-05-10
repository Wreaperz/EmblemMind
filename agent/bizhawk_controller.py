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
    time.sleep(0.01)
    """Write a single keypress to the Lua input file."""
    PHYSICAL_TO_GBA = {
        'x': 'A',
        'z': 'B',
        'w': 'L',
        'e': 'R',
        'enter': 'START',
        'up': 'UP',
        'down': 'DOWN',
        'left': 'LEFT',
        'right': 'RIGHT',
        'p': 'RESET'
    }

    gba_button = PHYSICAL_TO_GBA.get(key.lower())
    if gba_button:
        input_file = os.path.join(os.getcwd(), 'data', 'emblemmind_input.txt')  # Rel to working dir
        os.makedirs(os.path.dirname(input_file), exist_ok=True)  # Ensure 'data/' exists
        with open(input_file, 'w') as f:
            f.write(gba_button)
        time.sleep(duration)
    elif key == 'p':
        keyboard.press(key)
        time.sleep(duration)
        keyboard.release(key)
    time.sleep(0.01)

def press_keys(keys, duration=0.1):
    """Press multiple keys in sequence for the given duration each."""
    for key in keys:
        press_key(key, duration)
        time.sleep(0.05)

def press_reset():
    press_key('1')
    time.sleep(0.1)
    press_key('P')
    time.sleep(0.1)
    press_key(GBA_KEY_MAP['RESET'])