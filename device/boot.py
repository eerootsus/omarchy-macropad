import usb_cdc

# Expose a second serial endpoint (/dev/ttyACM* data interface) so the host
# daemon can push workspace state to the device. Replug the macropad after
# changing this file — boot.py only runs at USB enumeration time.
usb_cdc.enable(console=True, data=True)
