"""Run the lab device layer against a real UC-Mind board (keeps vendor firmware)."""
import sys, time
from firmata import Firmata, SerialTransport


def main(port, baud=57600):
    t = SerialTransport(port, baud)
    f = Firmata(t)
    print("port=%s baud=%d" % (port, baud))

    info = f.identify()
    print("IDENTIFY     :", info)
    print("firmware name:", f.firmware_name)

    analog = sorted(f.analog_mapping)
    print("analog pins  :", analog[:10], "(%d mapped)" % len(analog))

    if analog:
        pin = analog[0]
        f.report_analog(pin, True)
        time.sleep(0.4)
        events = f.poll(1.2)
        vals = [e.data["value"] for e in events if e.kind == "analog"]
        print("analog reads : pin %d -> %s  (%d reports)" % (pin, vals[:8], len(vals)))

    f.set_pin_mode(2, "input")
    f.report_digital(0, True)
    time.sleep(0.3)
    ev = f.poll(1.0)
    dig = [(e.data["port"], e.data["value"]) for e in ev if e.kind == "digital"]
    print("digital reads: %s" % dig[:6])

    f.set_pin_mode(2, "output")
    f.digital_write(2, 1); time.sleep(0.15); f.digital_write(2, 0)
    f.peripheral(2, 1, 301)      # vendor OneWire peripheral frame (display func 1)
    print("write path   : pin mode + digital write + OneWire frame sent")

    f.close()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/dev/cu.usbserial-1130",
         int(sys.argv[2]) if len(sys.argv) > 2 else 57600)
