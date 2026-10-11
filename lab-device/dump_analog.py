"""Dump the raw ANALOG_MAPPING_RESPONSE so the parser can be checked against the spec."""
import sys, time
from firmata import Firmata, SerialTransport, START_SYSEX, END_SYSEX

port = sys.argv[1] if len(sys.argv) > 1 else "/dev/cu.usbserial-1130"
baud = int(sys.argv[2]) if len(sys.argv) > 2 else 57600

t = SerialTransport(port, baud)
f = Firmata(t)
f.identify()
t.write(bytes([START_SYSEX, 0x69, END_SYSEX]))     # ANALOG_MAPPING_QUERY
time.sleep(0.6)
raw = t.read(4096, 0.6)
print("raw response:", raw.hex())
body = raw
if len(body) >= 3 and body[0] == START_SYSEX:
    body = body[2:-1] if body[-1] == END_SYSEX else body[2:]
print("payload bytes (%d): %s" % (len(body), list(body)))
print("spec reading (index = analog channel -> digital pin, 0x7F = none):")
for ch, pin in enumerate(body):
    if pin != 0x7F:
        print("   channel %-2d -> pin %d" % (ch, pin))
f.close()
