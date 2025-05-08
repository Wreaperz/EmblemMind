import keyboard
import time

print("You have 3 seconds to focus the BizHawk window...")
time.sleep(3)

# Press and release 'z'
keyboard.press('z')
time.sleep(0.1)
keyboard.release('z')

# Press and release 'x'
keyboard.press('x')
time.sleep(0.1)
keyboard.release('x')

print("Sent Z and X keypresses to BizHawk.")


#### FILE EDITING CODE
def send_emblem_action(action: str):
    with open("data/emblemmind_input.txt", "w") as f:
        f.write(action)

send_emblem_action("A")     # Presses A
send_emblem_action("UP")    # Presses UP
