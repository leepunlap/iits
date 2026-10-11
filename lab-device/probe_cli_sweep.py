"""Bounded sweep of the UCMake vendor CLI grammar, with crash detection.

Malformed arguments crash this firmware, so the sweep:
  * keeps every value in a small, sane range;
  * checks the board still answers after each command (a silent board = probable crash);
  * resets the board and carries on, recording which input killed it.

Usage:  python probe_cli_sweep.py <port> [--reset=dtr|rts]
"""
import sys
import time

import serial

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

port = sys.argv[1] if len(sys.argv) > 1 else "COM3"
reset = "dtr"
for a in sys.argv[1:]:
    if a.startswith("--reset="):
        reset = a.split("=", 1)[1]

ERRORS = ("ERROR",)


def open_board():
    s = serial.Serial()
    s.port = port
    s.baudrate = 115200
    s.timeout = 0.35
    s.dtr = False
    s.rts = False
    s.open()
    if reset == "dtr":
        s.setDTR(True); time.sleep(0.1); s.setDTR(False)
    else:
        s.setRTS(True); time.sleep(0.12); s.setRTS(False)
    time.sleep(2.2)
    s.reset_input_buffer()
    return s


def ask(s, cmd):
    s.reset_input_buffer()
    s.write((cmd + "\r\n").encode())
    time.sleep(0.3)
    return s.read(256).decode("utf-8", "replace").strip()


s = open_board()
alive = ask(s, "A1 1 1 1")
print("sanity check A1 1 1 1 -> %r" % alive[:24])

results = []
crashes = []
grid = []
for p in (1, 2, 3, 4):
    for sub in range(0, 8):
        grid.append("A%d %d 1 1" % (p, sub))

for cmd in grid:
    r = ask(s, cmd)
    if not r:
        r2 = ask(s, cmd)                      # one retry
        if not r2:
            crashes.append(cmd)
            s.close()
            time.sleep(0.5)
            s = open_board()                  # reset and resync
            ask(s, "A1 1 1 1")
            continue
        r = r2
    results.append((cmd, r))

print("\ntested %d commands, %d crashes" % (len(grid), len(crashes)))
print("\n=== non-error replies ===")
for c, r in results:
    if not any(e in r for e in ERRORS):
        print("  %-14s -> %s" % (c, r[:60]))
print("\n=== distinct error replies ===")
seen = {}
for c, r in results:
    if any(e in r for e in ERRORS):
        seen.setdefault(r[:30], []).append(c)
for r, cs in seen.items():
    print("  %-30s <- %s" % (r, ", ".join(cs[:5])))
if crashes:
    print("\n=== inputs that killed the board (do NOT send these) ===")
    for c in crashes:
        print("  ", c)
s.close()
