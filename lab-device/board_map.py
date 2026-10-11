"""Print the pin/mode map of a UC-Mind board running the vendor link (Firmata) firmware."""
import sys

from firmata import Firmata, SerialTransport, MODE_NAMES

port = sys.argv[1] if len(sys.argv) > 1 else "/dev/cu.usbserial-1130"
baud = int(sys.argv[2]) if len(sys.argv) > 2 else 57600

t = SerialTransport(port, baud)
f = Firmata(t)
info = f.identify()
print("board: firmata=%s firmware=%s pins=%d" % (info["firmata"], info["firmware"][-28:], info["pins"]))

summary = {}
for pin, modes in enumerate(f.capabilities):
    names = [MODE_NAMES.get(m, "0x%02x" % m) for m, _r in modes]
    if not names:
        continue
    for n in names:
        summary.setdefault(n, []).append(pin)

print("\nmodes -> pins")
for mode in sorted(summary):
    pins = summary[mode]
    print("  %-9s %s" % (mode, pins if len(pins) <= 24 else "%s … (%d pins)" % (pins[:24], len(pins))))

print("\nanalog mapping (pin -> channel):", f.analog_mapping)
f.close()
