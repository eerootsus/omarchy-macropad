import time

import usb_cdc
from adafruit_hid.consumer_control_code import ConsumerControlCode
from adafruit_hid.keycode import Keycode
from adafruit_macropad import MacroPad

macropad = MacroPad()
macropad.pixels.brightness = 1.0
macropad.pixels.auto_write = False

# Brightness is encoded directly in the tuples: 255 = 100% on that channel.
ACTIVE = (128, 0, 0)     # focused workspace — red @ 50%
OCCUPIED = (0, 0, 128)   # has windows — blue @ 50%
MAPPED = (0, 0, 20)      # empty but bound — very dim blue
UTILITY = (25, 12, 0)    # copy/paste "mapped" hint — dim amber, contrasts with workspace blue

# Top two rows of the 3x4 grid map to workspaces 1..6.
WORKSPACE_KEYS = (0, 1, 2, 3, 4, 5)
COPY_KEY = 9
PASTE_KEY = 10
SCREENSHOT_KEY = 11

FLASH_COLOR = (255, 255, 255)
FLASH_DURATION = 0.35  # seconds — how long to fade back to UTILITY

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

STATE_COLORS = {
    ord("0"): MAPPED,
    ord("1"): OCCUPIED,
    ord("2"): ACTIVE,
}


def paint(states):
    for i, key in enumerate(WORKSPACE_KEYS):
        macropad.pixels[key] = STATE_COLORS.get(states[i], MAPPED)
    macropad.pixels[COPY_KEY] = UTILITY
    macropad.pixels[PASTE_KEY] = UTILITY
    macropad.pixels[SCREENSHOT_KEY] = UTILITY
    macropad.pixels.show()


def lerp(a, b, t):
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


paint(b"000000")

serial = usb_cdc.data
buf = b""
last_encoder = macropad.encoder
last_switch = macropad.encoder_switch
flash_start = None

while True:
    event = macropad.keys.events.get()
    if event and event.pressed:
        combo = KEYCODES.get(event.key_number)
        if combo:
            macropad.keyboard.send(*combo)
        if event.key_number == SCREENSHOT_KEY:
            flash_start = time.monotonic()
            macropad.pixels[SCREENSHOT_KEY] = FLASH_COLOR
            macropad.pixels.show()

    if flash_start is not None:
        elapsed = time.monotonic() - flash_start
        if elapsed >= FLASH_DURATION:
            macropad.pixels[SCREENSHOT_KEY] = UTILITY
            macropad.pixels.show()
            flash_start = None
        else:
            macropad.pixels[SCREENSHOT_KEY] = lerp(FLASH_COLOR, UTILITY, elapsed / FLASH_DURATION)
            macropad.pixels.show()

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
            # Protocol: b"S" + 6 ASCII chars, each '0' (empty) / '1' (occupied) / '2' (active)
            if len(line) >= 7 and line[0:1] == b"S":
                paint(line[1:7])
