import time
import pydirectinput
import pygetwindow as gw

# Mapping of GBA controls to pyautogui key names
GBA_KEY_MAP = {
    'A': 'x',      # GBA A button
    'B': 'z',      # GBA B button
    'L': 'w',      # GBA L bumper
    'R': 'e',      # GBA R bumper
    'START': 'enter',  # GBA Start/Select
    'UP': 'up',
    'DOWN': 'down',
    'LEFT': 'left',
    'RIGHT': 'right'
}

BIZHAWK_WINDOW_TITLE = 'Fire Emblem'  # Partial window title (case-insensitive)

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
    """Press a single key for the given duration (in seconds)."""
    if not focus_bizhawk():
        print("Cannot focus BizHawk window.")
        return
    pydirectinput.keyDown(key)
    time.sleep(duration)
    pydirectinput.keyUp(key)

def press_keys(keys, duration=0.1):
    """Press multiple keys in sequence for the given duration each."""
    if not focus_bizhawk():
        print("Cannot focus BizHawk window.")
        return
    for key in keys:
        pydirectinput.keyDown(key)
        time.sleep(duration)
        pydirectinput.keyUp(key)
        time.sleep(0.05)