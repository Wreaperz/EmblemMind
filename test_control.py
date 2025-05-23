import time
from agent.bizhawk_controller import press_key, GBA_KEY_MAP, focus_bizhawk

def main():
    print("Focusing BizHawk window...")
    focus_bizhawk()
    time.sleep(1)
    # The first press_key will focus the window

    actions = [
        ("Move cursor UP", GBA_KEY_MAP['UP']),
        ("Move cursor DOWN", GBA_KEY_MAP['DOWN']),
        ("Move cursor LEFT", GBA_KEY_MAP['LEFT']),
        ("Move cursor RIGHT", GBA_KEY_MAP['RIGHT']),
        ("Press A (GBA)", GBA_KEY_MAP['A']),
        ("Press B (GBA)", GBA_KEY_MAP['B']),
    ]

    for desc, key in actions:
        print(f"Action: {desc}")
        press_key(key, duration=0.1)
        time.sleep(0.2)

    print("Test sequence complete.")

if __name__ == "__main__":
    main()