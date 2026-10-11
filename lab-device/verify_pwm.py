"""Verify the UC-Mind100's PWM/analog path (it exposes no digital I/O or motors)."""
import sys, time
from firmata import Firmata, SerialTransport

port = sys.argv[1] if len(sys.argv) > 1 else "/dev/cu.usbserial-1130"
t = SerialTransport(port, 57600)
f = Firmata(t)
info = f.identify()
print("board   : UC-Mind100 firmata=%s pins=%d" % (info["firmata"], info["pins"]))
pwm = [p for p, modes in enumerate(f.capabilities) if any(m == 0x03 for m, _ in modes)]
analog = sorted(f.analog_mapping)
print("pwm pins: %d (e.g. %s)" % (len(pwm), pwm[:8]))
print("analog  : %s" % analog[:8])
pin = pwm[0]
f.set_pin_mode(pin, "pwm")
f.analog_write(pin, 128)
time.sleep(0.2)
f.analog_write(pin, 0)
print("pwm     : pin %d <- 128 then 0" % pin)
apin = analog[0] if analog else 36
f.report_analog(apin, True)
time.sleep(0.3)
ev = f.poll(700)
vals = [e.data["value"] for e in ev if e.kind == "analog"]
f.report_analog(apin, False)
print("analog  : pin %s -> %s" % (apin, vals[:5]))
after = f.identify()
print("healthy :", after["firmata"] is not None, "firmata=%s" % (after["firmata"],))
f.close()
