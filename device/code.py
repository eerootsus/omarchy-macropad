import time

import usb_cdc
from adafruit_hid.consumer_control_code import ConsumerControlCode
from adafruit_hid.keycode import Keycode
from adafruit_macropad import MacroPad

macropad = MacroPad()
macropad.pixels.brightness = 1.0
macropad.pixels.auto_write = False

# Brightness is encoded directly in the tuples: 255 = 100% on that channel.
ACTIVE = (128, 0, 0)        # focused workspace — red @ 50%
OCCUPIED_LOW = (0, 0, 40)   # occupied breath trough — soft blue
OCCUPIED_HIGH = (0, 0, 160) # occupied breath peak
MAPPED = (0, 0, 20)         # empty but bound — very dim blue
UTILITY = (25, 12, 0)       # copy/paste / screenshot "mapped" hint — dim amber

# Top two rows of the 3x4 grid map to workspaces 1..6.
WORKSPACE_KEYS = (0, 1, 2, 3, 4, 5)
COPY_KEY = 9
PASTE_KEY = 10
SCREENSHOT_KEY = 11

FLASH_COLOR = (255, 255, 255)
FLASH_DURATION = 0.35      # seconds — one-shot fade back to UTILITY on key press
PULSE_PERIOD = 1.2         # seconds — breathing cycle while slurp is active
OCCUPIED_PERIOD = 2.5      # seconds — breathing cycle for occupied workspaces
RENDER_INTERVAL = 1 / 30   # cap pixel updates at ~30fps

KEYCODES = {
    0: (Keycode.GUI, Keycode.ONE),
    1: (Keycode.GUI, Keycode.TWO),
    2: (Keycode.GUI, Keycode.THREE),
    3: (Keycode.GUI, Keycode.FOUR),
    4: (Keycode.GUI, Keycode.FIVE),
    5: (Keycode.GUI, Keycode.SIX),
    COPY_KEY: (Keycode.CONTROL, Keycode.SHIFT, Keycode.C),
    PASTE_KEY: (Keycode.CONTROL, Keycode.SHIFT, Keycode.V),
    SCREENSHOT_KEY: (Keycode.GUI, Keycode.SHIFT, Keycode.S),
}

def lerp(a, b, t):
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def triangle(now, period):
    phase = (now % period) / period
    return phase * 2 if phase < 0.5 else (1 - phase) * 2


serial = usb_cdc.data
buf = b""
last_encoder = macropad.encoder
last_switch = macropad.encoder_switch
flash_start = None
pulse_mode = False  # toggled by host when slurp opens/closes its layer
workspace_states = bytearray(b"000000")
last_render = 0.0

while True:
    event = macropad.keys.events.get()
    if event and event.pressed:
        combo = KEYCODES.get(event.key_number)
        if combo:
            macropad.keyboard.send(*combo)
        if event.key_number == SCREENSHOT_KEY and not pulse_mode:
            flash_start = time.monotonic()

    position = macropad.encoder
    if position != last_encoder:
        delta = position - last_encoder
        code = ConsumerControlCode.VOLUME_INCREMENT if delta > 0 else ConsumerControlCode.VOLUME_DECREMENT
        for _ in range(abs(delta)):
            macropad.consumer_control.send(code)
        last_encoder = position

    switch = macropad.encoder_switch
    if switch and not last_switch:
        macropad.consumer_control.send(ConsumerControlCode.MUTE)
    last_switch = switch

    if serial and serial.in_waiting:
        buf += serial.read(serial.in_waiting)
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            line = line.strip()
            # Protocol:
            #   S<6 chars>  — workspace state, each '0' (empty) / '1' (occupied) / '2' (active)
            #   F<0|1>      — pulse the screenshot key on (slurp active) / off
            if len(line) >= 7 and line[0:1] == b"S":
                workspace_states[:] = line[1:7]
            elif len(line) >= 2 and line[0:1] == b"F":
                pulse_mode = line[1:2] == b"1"
                if not pulse_mode:
                    flash_start = None

    now = time.monotonic()
    if now - last_render >= RENDER_INTERVAL:
        last_render = now

        occupied_color = lerp(OCCUPIED_LOW, OCCUPIED_HIGH, triangle(now, OCCUPIED_PERIOD))
        for i, key in enumerate(WORKSPACE_KEYS):
            s = workspace_states[i]
            if s == ord("2"):
                macropad.pixels[key] = ACTIVE
            elif s == ord("1"):
                macropad.pixels[key] = occupied_color
            else:
                macropad.pixels[key] = MAPPED

        macropad.pixels[COPY_KEY] = UTILITY
        macropad.pixels[PASTE_KEY] = UTILITY

        if pulse_mode:
            macropad.pixels[SCREENSHOT_KEY] = lerp(UTILITY, FLASH_COLOR, triangle(now, PULSE_PERIOD))
        elif flash_start is not None:
            elapsed = now - flash_start
            if elapsed >= FLASH_DURATION:
                macropad.pixels[SCREENSHOT_KEY] = UTILITY
                flash_start = None
            else:
                macropad.pixels[SCREENSHOT_KEY] = lerp(FLASH_COLOR, UTILITY, elapsed / FLASH_DURATION)
        else:
            macropad.pixels[SCREENSHOT_KEY] = UTILITY

        macropad.pixels.show()
