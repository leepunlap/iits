"""Minimal Firmata client for the L2/L3 Wonder Lab.

Verified on real hardware 2026-10-11:

    UC-Mind300  (arduinoUno)       Firmata 2.5   57600 8N1
    UC-Mind100  (arduinoEsp32Min)  Firmata 2.7   57600 8N1

Both boards KEEP the vendor firmware, so students and teachers never re-flash.

The vendor firmware the boards actually run is the "11"-prefixed image:
    UC-Mind300 : 11arduinoUno.standardFirmata.ino.hex
    UC-Mind100 : 11arduinoESP32.standardFirmata.ino.bin
(the plainly-named <board>.standardFirmata.ino.* files in UCMake's firmwares/ folder are a
different, 115200 text-CLI firmware and are NOT Firmata).

Vendor peripherals on the ESP32 boards are OneWire modules reached through Firmata's OneWire
SysEx extension (see UCMake-re/L23-PROTOCOL.md):

    F0 73 3C <pin> 00 x16 <payload> F7
    payload = [func, 0, ...ASCII args]   'A'=65 negative marker, 'B'=66 argument separator
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------- constants
START_SYSEX = 0xF0
END_SYSEX = 0xF7
REPORT_VERSION = 0xF9
SYSTEM_RESET = 0xFF

REPORT_FIRMWARE = 0x79
CAPABILITY_QUERY = 0x6B
CAPABILITY_RESPONSE = 0x6C
ANALOG_MAPPING_QUERY = 0x69
ANALOG_MAPPING_RESPONSE = 0x6A
PIN_STATE_QUERY = 0x6D
PIN_STATE_RESPONSE = 0x6E
STRING_DATA = 0x71
SET_SAMPLING_INTERVAL = 0x7A
ONEWIRE_DATA = 0x73

SET_PIN_MODE = 0xF4
DIGITAL_MESSAGE = 0x90
ANALOG_MESSAGE = 0xE0
REPORT_ANALOG = 0xC0
REPORT_DIGITAL = 0xD0

# OneWire SysEx sub-commands (vendor firmware expects the 0x3C form for data-carrying writes)
ONEWIRE_WRITE_SUBCMD = 0x3C

MODES = {
    "input": 0x00, "output": 0x01, "analog": 0x02, "pwm": 0x03, "servo": 0x04,
    "i2c": 0x06, "onewire": 0x07, "stepper": 0x08, "serial": 0x09, "pullup": 0x0B,
}
MODE_NAMES = {v: k for k, v in MODES.items()}

# signal-argument markers used by the vendor peripheral payloads
NEG_MARK = 65   # 'A'
ARG_SEP = 66    # 'B'


# ---------------------------------------------------------------- transport
class Transport:
    """Byte transport. `read` returns whatever arrived within `timeout` (possibly b"")."""

    def write(self, data: bytes) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def read(self, max_bytes: int = 4096, timeout: float = 0.2) -> bytes:  # pragma: no cover
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover - interface
        pass


class SerialTransport(Transport):
    """pyserial-backed transport. Imported lazily so tests need no serial hardware."""

    def __init__(self, port: str, baud: int = 57600, settle: float = 2.2):
        import serial  # noqa: WPS433 (deliberate lazy import)

        self.serial = serial.Serial()
        self.serial.port = port
        self.serial.baudrate = baud
        self.serial.timeout = 0.05
        self.serial.dtr = False
        self.serial.rts = False
        self.serial.open()
        # release the ESP32/AVR reset so the sketch runs
        self.serial.setDTR(False)
        self.serial.setRTS(True)
        time.sleep(0.12)
        self.serial.setRTS(False)
        time.sleep(settle)
        self.serial.reset_input_buffer()

    def write(self, data: bytes) -> None:
        self.serial.write(data)

    def read(self, max_bytes: int = 4096, timeout: float = 0.2) -> bytes:
        self.serial.timeout = timeout
        return self.serial.read(max_bytes) or b""

    def close(self) -> None:
        try:
            self.serial.close()
        except Exception:
            pass


class SimulatedTransport(Transport):
    """Scripted board for tests: answers like the real firmware, records everything written."""

    def __init__(self, major: int = 2, minor: int = 7, name: str = "sim"):
        self.major, self.minor, self.name = major, minor, name
        self.written = bytearray()
        self.pending = bytearray()
        self._sysex = None

    # --- board side
    def _answer(self, payload: bytes) -> None:
        self.pending += payload

    def _on_sysex(self, body: bytes) -> None:
        cmd = body[0]
        if cmd == REPORT_FIRMWARE:
            self._answer(bytes([START_SYSEX, REPORT_FIRMWARE, self.major, self.minor])
                         + b"".join(bytes([ord(c), 0]) for c in self.name) + bytes([END_SYSEX]))
        elif cmd == CAPABILITY_QUERY:
            self._answer(bytes([START_SYSEX, CAPABILITY_RESPONSE])
                         + bytes([0x00, 0x01, 0x01, 0x01, 0x7F]) + bytes([END_SYSEX]))
        elif cmd == ANALOG_MAPPING_QUERY:
            self._answer(bytes([START_SYSEX, ANALOG_MAPPING_RESPONSE, 0x00, 0x7F, END_SYSEX]))
        elif cmd == SET_SAMPLING_INTERVAL:
            pass

    # --- transport side
    def write(self, data: bytes) -> None:
        self.written += data
        for byte in data:
            if self._sysex is None:
                if byte == START_SYSEX:
                    self._sysex = bytearray()
                elif byte == REPORT_VERSION:
                    self._answer(bytes([REPORT_VERSION, self.major, self.minor]))
                # other non-sysex messages are accepted silently
            else:
                if byte == END_SYSEX:
                    self._on_sysex(bytes(self._sysex))
                    self._sysex = None
                else:
                    self._sysex.append(byte)

    def read(self, max_bytes: int = 4096, timeout: float = 0.2) -> bytes:
        out = bytes(self.pending[:max_bytes])
        del self.pending[:len(out)]
        return out

    def close(self) -> None:
        pass


# ---------------------------------------------------------------- codec
def encode_14bit(value: int) -> Tuple[int, int]:
    value = max(0, min(0x3FFF, int(value)))
    return value & 0x7F, (value >> 7) & 0x7F


def decode_14bit(lsb: int, msb: int) -> int:
    return (lsb & 0x7F) | ((msb & 0x7F) << 7)


def peripheral_payload(func: int, *args: Sequence[int]) -> bytes:
    """Build the vendor OneWire peripheral payload.

    args are ASCII-encoded integers; negatives get the 'A' marker; 'B' separates arguments.
    """
    out = bytearray([func & 0xFF, 0x00])
    for i, value in enumerate(args):
        if i:
            out.append(ARG_SEP)
        value = int(value)
        if value < 0:
            out.append(NEG_MARK)
            value = -value
        out += str(value).encode("ascii")
    return bytes(out)


@dataclass
class Event:
    kind: str
    data: Dict = field(default_factory=dict)


# ---------------------------------------------------------------- client
class Firmata:
    """The lab's device layer: enough Firmata to identify and drive a UC-Mind board.

    Timeouts are in MILLISECONDS, matching firmata.js — the two implementations must not
    disagree on units (a 700-second drain is a memorable way to find out).
    """

    def __init__(self, transport: Transport, timeout: float = 800):
        self.t = transport
        self.timeout = timeout
        self.version: Optional[Tuple[int, int]] = None
        self.firmware_name: Optional[str] = None
        self.capabilities: List[List[Tuple[int, int]]] = []
        self.analog_mapping: Dict[int, int] = {}
        self._digital_ports: Dict[int, int] = {}
        self._sysex: Optional[bytearray] = None
        self._pending_cmd: Optional[str] = None
        self._pending_data: Dict = {}

    # -------------------------------------------------- low level
    def send(self, data: bytes) -> None:
        self.t.write(data)

    def send_sysex(self, command: int, *payload: int) -> None:
        self.send(bytes([START_SYSEX, command, *payload, END_SYSEX]))

    def _drain(self, milliseconds: float) -> List[Event]:
        events: List[Event] = []
        deadline = time.time() + (milliseconds / 1000.0)
        while time.time() < deadline:
            chunk = self.t.read(4096, timeout=min(0.2, max(0.02, deadline - time.time())))
            for byte in chunk:
                events += self._feed(byte)
        return events

    def _feed(self, byte: int) -> List[Event]:
        events: List[Event] = []
        if self._sysex is not None:
            if byte == END_SYSEX:
                events += self._on_sysex(bytes(self._sysex))
                self._sysex = None
            else:
                self._sysex.append(byte)
            return events
        if byte == START_SYSEX:
            self._sysex = bytearray()
        elif byte == REPORT_VERSION:
            self._pending_cmd, self._pending_data = "version", {"bytes": []}
        elif 0x90 <= byte <= 0x9F:
            self._pending_cmd, self._pending_data = "digital", {"port": byte & 0x0F, "bytes": []}
        elif 0xE0 <= byte <= 0xEF:
            self._pending_cmd, self._pending_data = "analog", {"channel": byte & 0x0F, "bytes": []}
        elif self._pending_cmd:
            self._pending_data.setdefault("bytes", []).append(byte)
            need = 2
            if len(self._pending_data["bytes"]) >= need:
                b = self._pending_data["bytes"]
                if self._pending_cmd == "version":
                    self.version = (b[0], b[1])
                    events.append(Event("version", {"major": b[0], "minor": b[1]}))
                elif self._pending_cmd == "digital":
                    events.append(Event("digital", {"port": self._pending_data["port"],
                                                    "value": decode_14bit(b[0], b[1])}))
                elif self._pending_cmd == "analog":
                    channel = self._pending_data["channel"]
                    found = next((p for p, ch in self.analog_mapping.items() if ch == channel), None)
                    events.append(Event("analog", {"channel": channel, "pin": found,
                                                   "value": decode_14bit(b[0], b[1])}))
                self._pending_cmd, self._pending_data = None, {}
        return events

    def _on_sysex(self, body: bytes) -> List[Event]:
        if not body:
            return []
        cmd, payload = body[0], body[1:]
        if cmd == REPORT_FIRMWARE and len(payload) >= 2:
            major, minor = payload[0], payload[1]
            chars = payload[2:]
            name = "".join(chr(chars[i]) for i in range(0, len(chars) - 1, 2))
            self.firmware_name = name
            return [Event("firmware", {"major": major, "minor": minor, "name": name})]
        if cmd == CAPABILITY_RESPONSE:
            pins, current = [], []
            i = 0
            while i < len(payload):
                if payload[i] == 0x7F:
                    pins.append(current)
                    current = []
                    i += 1
                else:
                    if i + 1 < len(payload):
                        current.append((payload[i], payload[i + 1]))
                    i += 2
            self.capabilities = pins
            return [Event("capability", {"pins": pins})]
        if cmd == ANALOG_MAPPING_RESPONSE:
            # one entry per DIGITAL PIN, giving that pin's analog channel; 0x7F = not analog-capable
            mapping = {pin: value for pin, value in enumerate(payload) if value != 0x7F}
            self.analog_mapping = mapping
            return [Event("analog_mapping", {"mapping": mapping})]
        return [Event("sysex", {"command": cmd, "payload": payload})]

    # -------------------------------------------------- identification
    def report_version(self, timeout: Optional[float] = None) -> Optional[Tuple[int, int]]:
        """timeout in milliseconds."""
        self.send(bytes([REPORT_VERSION]))
        self._drain(timeout or self.timeout)
        if self.version is None:
            # a board that reset on port open can miss the first request; ask once more
            self.send(bytes([REPORT_VERSION]))
            self._drain(timeout or self.timeout)
        return self.version

    def report_firmware(self, timeout: Optional[float] = None) -> Optional[str]:
        self.send_sysex(REPORT_FIRMWARE)
        self._drain(timeout or self.timeout)
        return self.firmware_name

    def query_capability(self, timeout: Optional[float] = None) -> List[List[Tuple[int, int]]]:
        self.send_sysex(CAPABILITY_QUERY)
        self._drain(timeout or self.timeout)
        return self.capabilities

    def query_analog_mapping(self, timeout: Optional[float] = None) -> Dict[int, int]:
        self.send_sysex(ANALOG_MAPPING_QUERY)
        self._drain(timeout or self.timeout)
        return self.analog_mapping

    def identify(self) -> Dict:
        """One call that names the board — the lab uses this to pick L2 vs L3 block sets."""
        self.report_version()
        name = self.report_firmware()
        self.query_capability()
        self.query_analog_mapping()
        # read state AFTER every query: a late boot banner can carry the version report
        return {
            "firmata": self.version,
            "firmware": name,
            "pins": len(self.capabilities),
            "analog_pins": len(self.analog_mapping),
        }

    # -------------------------------------------------- driving pins
    def set_pin_mode(self, pin: int, mode) -> None:
        code = MODES[mode] if isinstance(mode, str) else int(mode)
        self.send(bytes([SET_PIN_MODE, pin & 0x7F, code & 0xFF]))
        if code == MODES["output"]:
            self._digital_ports.setdefault(pin >> 3, 0)

    def digital_write(self, pin: int, value: int) -> None:
        port, bit = pin >> 3, pin & 0x07
        state = self._digital_ports.get(port, 0)
        state = (state | (1 << bit)) if value else (state & ~(1 << bit))
        self._digital_ports[port] = state
        lsb, msb = encode_14bit(state)
        self.send(bytes([DIGITAL_MESSAGE | port, lsb, msb]))

    def analog_write(self, pin: int, value: int) -> None:
        lsb, msb = encode_14bit(value)
        self.send(bytes([ANALOG_MESSAGE | (pin & 0x0F), lsb, msb]))

    def report_analog(self, pin: int, enable: bool = True) -> None:
        """Firmata's REPORT_ANALOG takes the analog CHANNEL, not the digital pin."""
        channel = self.analog_mapping.get(pin, pin)
        self.send(bytes([REPORT_ANALOG | (channel & 0x0F), 1 if enable else 0]))

    def report_digital(self, port: int, enable: bool = True) -> None:
        self.send(bytes([REPORT_DIGITAL | (port & 0x0F), 1 if enable else 0]))

    def set_sampling_interval(self, ms: int) -> None:
        lsb, msb = encode_14bit(ms)
        self.send_sysex(SET_SAMPLING_INTERVAL, lsb, msb)

    # -------------------------------------------------- vendor peripherals
    def onewire_write(self, pin: int, payload: bytes, power: int = 0) -> None:
        """Firmata OneWire SysEx write — the vendor's peripheral path (ESP32 boards)."""
        frame = bytes([START_SYSEX, ONEWIRE_DATA, ONEWIRE_WRITE_SUBCMD, pin & 0x7F])
        frame += bytes(16)                       # ROM/address + value + delay buffer
        frame += bytes(payload)
        frame += bytes([END_SYSEX])
        self.send(frame)

    def peripheral(self, pin: int, func: int, *args: int) -> None:
        """Convenience: write a vendor peripheral command (func + ASCII args)."""
        self.onewire_write(pin, peripheral_payload(func, *args))

    def poll(self, seconds: float = 0.2) -> List[Event]:
        return self._drain(seconds)

    def close(self) -> None:
        self.t.close()
