"""Unit tests for the lab's Firmata device layer. No hardware needed."""

import unittest

from firmata import (Firmata, SimulatedTransport, peripheral_payload, encode_14bit,
                     decode_14bit, START_SYSEX, END_SYSEX, ONEWIRE_DATA,
                     ONEWIRE_WRITE_SUBCMD, SET_PIN_MODE, DIGITAL_MESSAGE, ANALOG_MESSAGE,
                     MODES, NEG_MARK, ARG_SEP, REPORT_ANALOG, ANALOG_MAPPING_RESPONSE)


class TestCodec(unittest.TestCase):
    def test_14bit_roundtrip(self):
        for v in (0, 1, 127, 128, 255, 1000, 8191, 16383):
            lsb, msb = encode_14bit(v)
            self.assertEqual(decode_14bit(lsb, msb), v)

    def test_14bit_clamps(self):
        self.assertEqual(decode_14bit(*encode_14bit(99999)), 16383)
        self.assertEqual(decode_14bit(*encode_14bit(-5)), 0)

    def test_peripheral_payload_positive(self):
        self.assertEqual(peripheral_payload(1, 301), bytes([1, 0]) + b"301")

    def test_peripheral_payload_negative(self):
        self.assertEqual(peripheral_payload(4, -120), bytes([4, 0, NEG_MARK]) + b"120")

    def test_peripheral_payload_two_args(self):
        self.assertEqual(peripheral_payload(5, 100, -50),
                         bytes([5, 0]) + b"100" + bytes([ARG_SEP, NEG_MARK]) + b"50")

    def test_peripheral_payload_no_args(self):
        self.assertEqual(peripheral_payload(6), bytes([6, 0]))


class TestSimulatedIdentity(unittest.TestCase):
    def test_report_version(self):
        f = Firmata(SimulatedTransport(major=2, minor=7), timeout=50)
        self.assertEqual(f.report_version(), (2, 7))
        self.assertEqual(f.version, (2, 7))

    def test_report_firmware_name(self):
        f = Firmata(SimulatedTransport(major=3, minor=2, name="UC-Mind"), timeout=50)
        self.assertEqual(f.report_firmware(), "UC-Mind")
        self.assertEqual(f.firmware_name, "UC-Mind")

    def test_capability_and_mapping(self):
        f = Firmata(SimulatedTransport(), timeout=50)
        self.assertEqual(f.query_capability(), [[(0, 1), (1, 1)]])
        self.assertEqual(f.query_analog_mapping(), {0: 0})

    def test_identify(self):
        f = Firmata(SimulatedTransport(major=2, minor=5, name="uno"), timeout=50)
        info = f.identify()
        self.assertEqual(info["firmata"], (2, 5))
        self.assertEqual(info["firmware"], "uno")
        self.assertEqual(info["pins"], 1)


class TestAnalogMappingParse(unittest.TestCase):
    def test_mapping_is_indexed_by_digital_pin(self):
        f = Firmata(SimulatedTransport(), timeout=50)
        # UC-Mind300: pins 0-13 not analog, pins 14-19 are A0-A5
        payload = [0x7F] * 14 + [0, 1, 2, 3, 4, 5]
        f._on_sysex(bytes([ANALOG_MAPPING_RESPONSE] + payload))
        self.assertEqual(f.analog_mapping, {14: 0, 15: 1, 16: 2, 17: 3, 18: 4, 19: 5})

    def test_0x7f_is_not_a_separator(self):
        f = Firmata(SimulatedTransport(), timeout=50)
        f._on_sysex(bytes([ANALOG_MAPPING_RESPONSE, 11, 0x7F, 12, 0x7F, 10, 0x7F, 0x7F]))
        self.assertEqual(f.analog_mapping, {0: 11, 2: 12, 4: 10})


class TestAnalogChannel(unittest.TestCase):
    def test_report_analog_uses_the_channel_not_the_pin(self):
        t = SimulatedTransport()
        f = Firmata(t, timeout=50)
        f.analog_mapping = {14: 0}          # the 300's only analog pin is 14 -> channel 0
        f.report_analog(14, True)
        self.assertEqual(bytes(t.written), bytes([REPORT_ANALOG | 0, 1]))

    def test_analog_report_resolves_channel_back_to_pin(self):
        f = Firmata(SimulatedTransport(), timeout=50)
        f.analog_mapping = {14: 0}
        events = []
        for byte in (0xE0, 0x34, 0x02):
            events += f._feed(byte)
        self.assertEqual(events[0].kind, "analog")
        self.assertEqual(events[0].data["channel"], 0)
        self.assertEqual(events[0].data["pin"], 14)
        self.assertEqual(events[0].data["value"], decode_14bit(0x34, 0x02))


class TestOutboundFrames(unittest.TestCase):
    def setUp(self):
        self.t = SimulatedTransport()
        self.f = Firmata(self.t, timeout=50)

    def test_set_pin_mode(self):
        self.f.set_pin_mode(13, "output")
        self.assertEqual(bytes(self.t.written)[-3:], bytes([SET_PIN_MODE, 13, MODES["output"]]))

    def test_digital_write_sets_and_clears_the_bit(self):
        self.f.set_pin_mode(13, "output")
        self.t.written.clear()
        self.f.digital_write(13, 1)                      # port 1, bit 5
        self.assertEqual(bytes(self.t.written), bytes([DIGITAL_MESSAGE | 1, 0x20, 0x00]))
        self.t.written.clear()
        self.f.digital_write(13, 0)
        self.assertEqual(bytes(self.t.written), bytes([DIGITAL_MESSAGE | 1, 0x00, 0x00]))

    def test_digital_write_port_and_bit_maths(self):
        self.f.set_pin_mode(2, "output")                 # port 0, bit 2
        self.t.written.clear()
        self.f.digital_write(2, 1)
        self.assertEqual(bytes(self.t.written), bytes([DIGITAL_MESSAGE | 0, 0x04, 0x00]))

    def test_analog_write(self):
        self.f.analog_write(9, 255)
        lsb, msb = encode_14bit(255)
        self.assertEqual(bytes(self.t.written), bytes([ANALOG_MESSAGE | 9, lsb, msb]))

    def test_onewire_write_frame_shape(self):
        self.f.peripheral(18, 1, 301)                    # 4-digit display, func 1
        frame = bytes(self.t.written)
        self.assertEqual(frame[0], START_SYSEX)
        self.assertEqual(frame[1], ONEWIRE_DATA)
        self.assertEqual(frame[2], ONEWIRE_WRITE_SUBCMD)
        self.assertEqual(frame[3], 18)                   # pin
        self.assertEqual(frame[4:20], bytes(16))         # 16-byte buffer
        self.assertEqual(frame[20:], bytes([1, 0]) + b"301" + bytes([END_SYSEX]))

    def test_onewire_write_pin_is_masked(self):
        self.f.onewire_write(0x81, b"\x01")
        self.assertEqual(bytes(self.t.written)[3], 0x01)


if __name__ == "__main__":
    unittest.main(verbosity=2)
