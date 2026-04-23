import usb_cdc
from adafruit_hid.keycode import Keycode
from adafruit_macropad import MacroPad

macropad = MacroPad()
macropad.pixels.brightness = 1.0
macropad.pixels.auto_write = False

# Brightness is encoded directly in the tuples: 255 = 100% on that channel.
ACTIVE = (128, 0, 0)     # focused workspace — red @ 50%
OCCUPIED = (0, 0, 128)   # has windows — blue @ 50%
MAPPED = (0, 0, 20)      # empty but bound — very dim blue, visible as a "this key does something" hint

# Top two rows of the 3x4 grid map to workspaces 1..6.
WORKSPACE_KEYS = (0, 1, 2, 3, 4, 5)

KEYCODES = (
    (Keycode.GUI, Keycode.ONE),
    (Keycode.GUI, Keycode.TWO),
    (Keycode.GUI, Keycode.THREE),
    (Keycode.GUI, Keycode.FOUR),
    (Keycode.GUI, Keycode.FIVE),
    (Keycode.GUI, Keycode.SIX),
)

STATE_COLORS = {
    ord("0"): MAPPED,
    ord("1"): OCCUPIED,
    ord("2"): ACTIVE,
}


def paint(states):
    for i, key in enumerate(WORKSPACE_KEYS):
        macropad.pixels[key] = STATE_COLORS.get(states[i], MAPPED)
    macropad.pixels.show()


paint(b"000000")

serial = usb_cdc.data
buf = b""

while True:
    event = macropad.keys.events.get()
    if event and event.pressed:
        idx = event.key_number
        if 0 <= idx < len(KEYCODES):
            macropad.keyboard.send(*KEYCODES[idx])

    if serial and serial.in_waiting:
        buf += serial.read(serial.in_waiting)
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            line = line.strip()
            # Protocol: b"S" + 6 ASCII chars, each '0' (empty) / '1' (occupied) / '2' (active)
            if len(line) >= 7 and line[0:1] == b"S":
                paint(line[1:7])
