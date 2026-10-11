"""Send the vendor realtime CLI commands UCMake itself uses, and show the replies.

Grammar recovered from the app's own runtime handlers:
    A8  <pin> 0 0 <speed> 0   DC motor      (espMinSetDcMotor)
    A8  10 3 0 0 0            stop motors   (espMinSetDcMotorStop)
    A10 <pin> <value>         4-digit display
    A5  <pin> 4               ultrasonic distance (reply = value)
Commands are terminated with LF+CR, exactly as UCMake sends them.
"""
import sys
import time

import serial

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

port = sys.argv[1] if len(sys.argv) > 1 else "COM4"
baud = int(sys.argv[2]) if len(sys.argv) > 2 else 115200
cmds = sys.argv[3:] or [
    "A8 10 0 0 100 0",     # motor on pin 10, speed 100  -> what the user's program did
    "A8 10 0 0 0 0",       # speed 0
    "A8 10 3 0 0 0",       # stop
    "A10 27 500",          # 4-digit display on pin 27
]

s = serial.Serial()
s.port = port
s.baudrate = baud
s.timeout = 0.5
s.dtr = False
s.rts = False
s.open()
s.setRTS(True); time.sleep(0.12); s.setRTS(False)
time.sleep(2.2)
s.reset_input_buffer()

for cmd in cmds:
    s.reset_input_buffer()
    s.write((cmd + "\n\r").encode())
    time.sleep(0.45)
    raw = s.read(200)
    text = raw.decode("utf-8", "replace").strip()
    print("  %-18s -> %-22s %s" % (cmd, raw[:10].hex(), text[:40].encode("ascii", "replace").decode()))
s.close()
