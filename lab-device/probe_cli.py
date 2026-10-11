"""Probe the UCMake vendor realtime firmware (the 115200 port-based text CLI).

The installer names `arduinoUno.standardFirmata.ino.hex` / `arduinoESP32Min.standardFirmata.ino.bin`
for the UC-Mind boards; despite the name those are a text CLI, not Firmata:

    A1 1 1 1  -> 180.00        (a reading)
    S301      -> ERROR 参数不足   (known verb, insufficient parameters)
    T L3 OK   -> ERROR 未知指令   (unknown verb)

Usage:  python probe_cli.py COM3 [baud] [cmd ...]
"""
import sys
import time

import serial

try:                      # Windows console defaults to cp1252 and cannot print the CLI's Chinese
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

port = sys.argv[1] if len(sys.argv) > 1 else "/dev/cu.usbserial-1130"
baud = int(sys.argv[2]) if len(sys.argv) > 2 else 115200
reset = "rts"
cmds = []
for a in sys.argv[3:]:
    if a.startswith("--reset="):
        reset = a.split("=", 1)[1]
    else:
        cmds.append(a)
cmds = cmds or ["A1 1 1 1", "A2 1 1", "S301", "help", "B1 100", "M1 1"]

s = serial.Serial()
s.port = port
s.baudrate = baud
s.timeout = 0.4
s.dtr = False
s.rts = False
s.open()
# AVR resets on DTR; ESP32 resets on RTS (DTR is GPIO0 there, so pulsing it drops the chip into
# download mode and it goes silent).
if reset == "dtr":
    s.setDTR(True); time.sleep(0.1); s.setDTR(False)
elif reset == "rts":
    s.setRTS(True); time.sleep(0.12); s.setRTS(False)
time.sleep(2.2)

boot = s.read(512)
print("port=%s baud=%d" % (port, baud))
print("boot after reset: %d bytes %s" % (len(boot), boot[:40].hex()))

for cmd in cmds:
    s.reset_input_buffer()
    s.write((cmd + "\r\n").encode())
    time.sleep(0.32)
    raw = s.read(200)
    text = raw.decode("utf-8", "replace").strip()
    print("  %-12s -> %-24s %s" % (cmd, raw[:10].hex(), text[:40].encode("ascii", "replace").decode()))

s.close()
