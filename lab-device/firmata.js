/**
 * Firmata device layer for the L2/L3 Wonder Lab — browser (Web Serial) and Node.
 *
 * Verified against real hardware 2026-10-11 (see ../L23-PROTOCOL.md):
 *   UC-Mind300 (arduinoUno)       Firmata 2.5   57600 8N1
 *   UC-Mind100 (arduinoEsp32Min)  Firmata 2.7   57600 8N1
 * Both boards KEEP the vendor firmware, so students and teachers never re-flash.
 *
 * Vendor peripherals on the ESP32 boards are OneWire modules reached through Firmata's
 * OneWire SysEx extension:
 *   F0 73 3C <pin> 00 x16 <payload> F7
 *   payload = [func, 0, ...ASCII args]   'A'=65 negative marker, 'B'=66 argument separator
 *
 * Frame construction is pure and synchronous (testable without I/O); the transport is async.
 */

// ---------------------------------------------------------------- constants
export const START_SYSEX = 0xf0;
export const END_SYSEX = 0xf7;
export const REPORT_VERSION = 0xf9;
export const SYSTEM_RESET = 0xff;

export const REPORT_FIRMWARE = 0x79;
export const CAPABILITY_QUERY = 0x6b;
export const CAPABILITY_RESPONSE = 0x6c;
export const ANALOG_MAPPING_QUERY = 0x69;
export const ANALOG_MAPPING_RESPONSE = 0x6a;
export const PIN_STATE_QUERY = 0x6d;
export const STRING_DATA = 0x71;
export const SET_SAMPLING_INTERVAL = 0x7a;
export const ONEWIRE_DATA = 0x73;

export const SET_PIN_MODE = 0xf4;
export const DIGITAL_MESSAGE = 0x90;
export const ANALOG_MESSAGE = 0xe0;
export const REPORT_ANALOG = 0xc0;
export const REPORT_DIGITAL = 0xd0;

export const ONEWIRE_WRITE_SUBCMD = 0x3c;

export const MODES = {
  input: 0x00, output: 0x01, analog: 0x02, pwm: 0x03, servo: 0x04,
  i2c: 0x06, onewire: 0x07, stepper: 0x08, serial: 0x09, pullup: 0x0b,
};

export const NEG_MARK = 65; // 'A'
export const ARG_SEP = 66;  // 'B'

// ---------------------------------------------------------------- codec
export function encode14(value) {
  const v = Math.max(0, Math.min(0x3fff, Math.trunc(value)));
  return [v & 0x7f, (v >> 7) & 0x7f];
}

export function decode14(lsb, msb) {
  return (lsb & 0x7f) | ((msb & 0x7f) << 7);
}

/** Vendor OneWire peripheral payload: func, 0, then ASCII args ('A' negates, 'B' separates). */
export function peripheralPayload(func, ...args) {
  const out = [func & 0xff, 0x00];
  args.forEach((raw, i) => {
    if (i) out.push(ARG_SEP);
    let value = Math.trunc(Number(raw));
    if (value < 0) { out.push(NEG_MARK); value = -value; }
    for (const ch of String(value)) out.push(ch.charCodeAt(0));
  });
  return Uint8Array.from(out);
}

// ---------------------------------------------------------------- frame builders (pure)
export const frameReportVersion = () => Uint8Array.from([REPORT_VERSION]);
export const frameSysex = (command, ...payload) =>
  Uint8Array.from([START_SYSEX, command, ...payload, END_SYSEX]);
export const frameSetPinMode = (pin, mode) => {
  const code = typeof mode === 'string' ? MODES[mode] : mode;
  return Uint8Array.from([SET_PIN_MODE, pin & 0x7f, code & 0xff]);
};
export const frameDigitalWrite = (port, state) => {
  const [lsb, msb] = encode14(state);
  return Uint8Array.from([DIGITAL_MESSAGE | (port & 0x0f), lsb, msb]);
};
export const frameAnalogWrite = (pin, value) => {
  const [lsb, msb] = encode14(value);
  return Uint8Array.from([ANALOG_MESSAGE | (pin & 0x0f), lsb, msb]);
};
export const frameReportAnalog = (channel, enable) =>
  Uint8Array.from([REPORT_ANALOG | (channel & 0x0f), enable ? 1 : 0]);
export const frameReportDigital = (port, enable) =>
  Uint8Array.from([REPORT_DIGITAL | (port & 0x0f), enable ? 1 : 0]);
export const frameSamplingInterval = (ms) => {
  const [lsb, msb] = encode14(ms);
  return frameSysex(SET_SAMPLING_INTERVAL, lsb, msb);
};
/** OneWire SysEx write — the vendor peripheral path. */
export const frameOneWireWrite = (pin, payload) => {
  const body = [START_SYSEX, ONEWIRE_DATA, ONEWIRE_WRITE_SUBCMD, pin & 0x7f];
  for (let i = 0; i < 16; i += 1) body.push(0);
  for (const b of payload) body.push(b);
  body.push(END_SYSEX);
  return Uint8Array.from(body);
};
export const framePeripheral = (pin, func, ...args) =>
  frameOneWireWrite(pin, peripheralPayload(func, ...args));

// ---------------------------------------------------------------- transports
/** Scripted board for tests: answers like real firmware and records everything written. */
export class MockTransport {
  constructor({ major = 2, minor = 7, name = 'mock', pins = 1 } = {}) {
    this.major = major; this.minor = minor; this.name = name; this.pins = pins;
    this.written = [];
    this.pending = [];
    this._sysex = null;
  }
  _answer(bytes) { for (const b of bytes) this.pending.push(b); }
  _onSysex(body) {
    const cmd = body[0];
    if (cmd === REPORT_FIRMWARE) {
      const out = [START_SYSEX, REPORT_FIRMWARE, this.major, this.minor];
      for (const ch of this.name) { out.push(ch.charCodeAt(0), 0); }
      out.push(END_SYSEX);
      this._answer(out);
    } else if (cmd === CAPABILITY_QUERY) {
      const out = [START_SYSEX, CAPABILITY_RESPONSE];
      for (let i = 0; i < this.pins; i += 1) out.push(0x00, 0x01, 0x01, 0x01, 0x7f);
      out.push(END_SYSEX);
      this._answer(out);
    } else if (cmd === ANALOG_MAPPING_QUERY) {
      this._answer([START_SYSEX, ANALOG_MAPPING_RESPONSE, 0x00, 0x7f, END_SYSEX]);
    }
  }
  async write(bytes) {
    for (const b of bytes) {
      this.written.push(b);
      if (this._sysex === null) {
        if (b === START_SYSEX) this._sysex = [];
        else if (b === REPORT_VERSION) this._answer([REPORT_VERSION, this.major, this.minor]);
      } else if (b === END_SYSEX) { this._onSysex(this._sysex); this._sysex = null; }
      else this._sysex.push(b);
    }
  }
  async read() {
    const out = Uint8Array.from(this.pending);
    this.pending.length = 0;
    return out;
  }
  async close() {}
}

/** Browser: Web Serial. `await WebSerialTransport.request()` prompts the student to pick a port. */
/**
 * USB vendor ids worth offering for a UC-Mind board.
 *
 * Both kits we have use a **CH340 (0x1A86, product 0x7523)** — confirmed on the ThinkPad
 * (`USB\VID_1A86&PID_7523`) and the macmini (`"USB Serial"`, idVendor 6790). The rest are the
 * bridges a UCMake board could plausibly ship with, so the chooser hides phones, modems, Bluetooth
 * serial ports and other clutter without hiding a legitimate board.
 *
 * Note this cannot separate the UC-Mind100 from the UC-Mind300 — same bridge. The board readout
 * tells you which one you actually got.
 */
export const UCMake_PORT_FILTERS = [
  { usbVendorId: 0x1a86 },   // CH340 / CH341   — both UC-Mind kits
  { usbVendorId: 0x10c4 },   // CP210x (Silicon Labs)
  { usbVendorId: 0x0403 },   // FTDI
  { usbVendorId: 0x2341 },   // Arduino
  { usbVendorId: 0x2a03 },   // Arduino (arduino.org)
  { usbVendorId: 0x303a },   // Espressif native USB
];
const UCMake_VENDOR_IDS = new Set(UCMake_PORT_FILTERS.map((f) => f.usbVendorId));

export class WebSerialTransport {
  constructor(port) { this.port = port; this.buffer = []; this._closed = false; }

  /**
   * Ask for a port — but reuse one the origin already has permission for, so a board that has been
   * connected once reconnects without the chooser. Prefers the CH340/CP210x bridges these kits use.
   */
  static async request({ baudRate = 57600, settle = 2200, preferGranted = true,
                         filters = UCMake_PORT_FILTERS, allPorts = false } = {}) {
    if (typeof navigator === 'undefined' || !navigator.serial) {
      throw new Error('Web Serial unavailable: needs Chrome/Edge over https or http://localhost');
    }
    let port = null;
    if (preferGranted && typeof navigator.serial.getPorts === 'function') {
      try {
        const known = await navigator.serial.getPorts();
        port = known.find((p) => UCMake_VENDOR_IDS.has(p.getInfo?.().usbVendorId))
            ?? known[0] ?? null;
      } catch { port = null; }
    }
    if (!port) {
      try {
        // `filters` makes the browser's chooser show only these bridges, so a class full of laptops
        // does not offer Bluetooth serial ports, modems and everything else the OS reports.
        port = allPorts ? await navigator.serial.requestPort()
                        : await navigator.serial.requestPort({ filters });
      } catch (e) {
        if (e && e.name === 'NotFoundError') {
          throw new Error(allPorts
            ? '沒有選擇序列埠。'
            : '找不到 UC-Mind 主控板。只會顯示 CH340 / CP210x / FTDI 等序列埠 — 請檢查 USB 線是否為資料線；若主控板使用其他晶片，可按「顯示所有序列埠」。');
        }
        throw e;
      }
    }
    return WebSerialTransport.open(port, { baudRate, settle });
  }

  static async open(port, { baudRate = 57600, settle = 2200 } = {}) {
    await port.open({ baudRate, dataBits: 8, stopBits: 1, parity: 'none', flowControl: 'none' });
    const t = new WebSerialTransport(port);
    t._reader = port.readable.getReader();
    t._writer = port.writable.getWriter();
    t._pump();
    await new Promise((r) => setTimeout(r, 1500)); // let the board boot
    t.buffer.length = 0;
    return t;
  }

  async _pump() {
    try {
      for (;;) {
        const { value, done } = await this._reader.read();
        if (done) break;
        if (value) for (const b of value) this.buffer.push(b);
      }
    } catch { /* port closed */ }
  }

  async write(bytes) { await this._writer.write(bytes); }

  async drain() { this.buffer.length = 0; }

  /** Reopen the same physical port at a different baud (Web Serial cannot change it in place). */
  async reopen({ baudRate = 115200, settle = 1200 } = {}) {
    try { await this._reader?.cancel(); } catch { /* already gone */ }
    try { this._reader?.releaseLock?.(); } catch { /* ignore */ }
    try { this._writer?.releaseLock?.(); } catch { /* ignore */ }
    try { await this.port.close(); } catch { /* ignore */ }
    await this.port.open({ baudRate, dataBits: 8, stopBits: 1, parity: 'none', flowControl: 'none' });
    this._closed = false;
    this.buffer.length = 0;
    this._reader = this.port.readable.getReader();
    this._writer = this.port.writable.getWriter();
    this._pump();
    if (settle) await new Promise((r) => setTimeout(r, settle));
    this.buffer.length = 0;
    return this;
  }

  async read(_max = 4096, timeout = 200) {
    const deadline = Date.now() + timeout;
    while (!this.buffer.length && Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, 10));
    }
    const out = Uint8Array.from(this.buffer);
    this.buffer.length = 0;
    return out;
  }

  async close() {
    this._closed = true;
    try { await this._reader.cancel(); } catch {}
    try { this._reader.releaseLock(); } catch {}
    try { this._writer.releaseLock(); } catch {}
    try { await this.port.close(); } catch {}
  }
}

/** Node: 'serialport' package, used for hardware verification of this same module. */
export class SerialPortTransport {
  static async open(path, { baudRate = 57600, settle = 2200 } = {}) {
    const { SerialPort } = await import('serialport');
    const port = new SerialPort({ path, baudRate, autoOpen: false });
    await new Promise((res, rej) => port.open((e) => (e ? rej(e) : res())));
    const t = new SerialPortTransport(port);
    port.on('data', (chunk) => { for (const b of chunk) t.buffer.push(b); });
    if (settle) await new Promise((r) => setTimeout(r, settle));   // Optiboot needs ~1 s, then the app boots
    t.buffer.length = 0;
    return t;
  }
  constructor(port) { this.port = port; this.buffer = []; }
  async write(bytes) {
    await new Promise((res, rej) => this.port.write(Buffer.from(bytes), (e) => (e ? rej(e) : res())));
    await new Promise((res) => this.port.drain(() => res()));
  }
  async read(_max = 4096, timeout = 200) {
    const deadline = Date.now() + timeout;
    while (!this.buffer.length && Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, 10));
    }
    const out = Uint8Array.from(this.buffer);
    this.buffer.length = 0;
    return out;
  }
  async drain() { this.buffer.length = 0; }

  /** Reopen at a different baud (Node serialport can change it in place). */
  async reopen({ baudRate = 115200, settle = 1200 } = {}) {
    await new Promise((res, rej) => this.port.update({ baudRate }, (e) => (e ? rej(e) : res())));
    this.buffer.length = 0;
    if (settle) await new Promise((r) => setTimeout(r, settle));
    this.buffer.length = 0;
    return this;
  }

  async close() { await new Promise((res) => this.port.close(() => res())); }
}

// ---------------------------------------------------------------- client
export class Firmata {
  constructor(transport, { timeout = 800 } = {}) {
    this.t = transport;
    this.timeout = timeout;
    this.version = null;
    this.firmwareName = null;
    this.capabilities = [];
    this.analogMapping = {};
    this._digitalPorts = {};
    this._sysex = null;
    this._pending = null;
  }

  async _drain(ms) {
    const events = [];
    const deadline = Date.now() + ms;
    while (Date.now() < deadline) {
      const chunk = await this.t.read(4096, Math.min(200, Math.max(20, deadline - Date.now())));
      for (const byte of chunk) events.push(...this._feed(byte));
    }
    return events;
  }

  _feed(byte) {
    const events = [];
    if (this._sysex !== null) {
      if (byte === END_SYSEX) { events.push(...this._onSysex(this._sysex)); this._sysex = null; }
      else this._sysex.push(byte);
      return events;
    }
    if (byte === START_SYSEX) this._sysex = [];
    else if (byte === REPORT_VERSION) this._pending = { kind: 'version', bytes: [] };
    else if (byte >= 0x90 && byte <= 0x9f) this._pending = { kind: 'digital', port: byte & 0x0f, bytes: [] };
    else if (byte >= 0xe0 && byte <= 0xef) this._pending = { kind: 'analog', channel: byte & 0x0f, bytes: [] };
    else if (this._pending) {
      this._pending.bytes.push(byte);
      if (this._pending.bytes.length >= 2) {
        const [a, b] = this._pending.bytes;
        if (this._pending.kind === 'version') {
          this.version = [a, b];
          events.push({ kind: 'version', major: a, minor: b });
        } else if (this._pending.kind === 'digital') {
          events.push({ kind: 'digital', port: this._pending.port, value: decode14(a, b) });
        } else if (this._pending.kind === 'analog') {
          const channel = this._pending.channel;
          const found = Object.entries(this.analogMapping).find(([, ch]) => ch === channel);
          events.push({ kind: 'analog', channel, pin: found ? Number(found[0]) : null, value: decode14(a, b) });
        }
        this._pending = null;
      }
    }
    return events;
  }

  _onSysex(body) {
    if (!body.length) return [];
    const [cmd, ...payload] = body;
    if (cmd === REPORT_FIRMWARE && payload.length >= 2) {
      const [major, minor] = payload;
      let name = '';
      for (let i = 2; i + 1 < payload.length; i += 2) name += String.fromCharCode(payload[i]);
      this.firmwareName = name;
      return [{ kind: 'firmware', major, minor, name }];
    }
    if (cmd === CAPABILITY_RESPONSE) {
      const pins = []; let current = [];
      for (let i = 0; i < payload.length;) {
        if (payload[i] === 0x7f) { pins.push(current); current = []; i += 1; }
        else { current.push([payload[i], payload[i + 1]]); i += 2; }
      }
      this.capabilities = pins;
      return [{ kind: 'capability', pins }];
    }
    if (cmd === ANALOG_MAPPING_RESPONSE) {
      // one entry per DIGITAL PIN, giving that pin's analog channel; 0x7F = not analog-capable
      const mapping = {};
      payload.forEach((value, pin) => { if (value !== 0x7f) mapping[pin] = value; });
      this.analogMapping = mapping;
      return [{ kind: 'analogMapping', mapping }];
    }
    return [{ kind: 'sysex', command: cmd, payload }];
  }

  // ---- identification
  async reportVersion(ms = this.timeout) {
    await this.t.write(frameReportVersion());
    await this._drain(ms);
    if (this.version === null) {
      // a board that reset on port open can miss the first request; ask once more
      await this.t.write(frameReportVersion());
      await this._drain(ms);
    }
    return this.version;
  }
  async reportFirmware(ms = this.timeout) {
    await this.t.write(frameSysex(REPORT_FIRMWARE));
    await this._drain(ms);
    return this.firmwareName;
  }
  async queryCapability(ms = this.timeout) {
    await this.t.write(frameSysex(CAPABILITY_QUERY));
    await this._drain(ms);
    return this.capabilities;
  }
  async queryAnalogMapping(ms = this.timeout) {
    await this.t.write(frameSysex(ANALOG_MAPPING_QUERY));
    await this._drain(ms);
    return this.analogMapping;
  }
  /** Name the board — the lab uses pin count to tell L2 (40) from L3 (20). */
  async identify() {
    await this.reportVersion();
    const firmware = await this.reportFirmware();
    await this.queryCapability();
    await this.queryAnalogMapping();
    // read state AFTER every query: a late boot banner can carry the version report
    const firmata = this.version;
    const pins = this.capabilities.length;
    return {
      firmata, firmware, pins,
      analogPins: Object.keys(this.analogMapping).map(Number),
      level: pins >= 32 ? 'L2' : (pins ? 'L3' : null),
    };
  }

  // ---- driving pins
  async setPinMode(pin, mode) {
    if (mode === 'output') this._digitalPorts[pin >> 3] ??= 0;
    await this.t.write(frameSetPinMode(pin, mode));
  }
  async digitalWrite(pin, value) {
    const port = pin >> 3; const bit = pin & 0x07;
    const state = this._digitalPorts[port] ?? 0;
    this._digitalPorts[port] = value ? (state | (1 << bit)) : (state & ~(1 << bit));
    await this.t.write(frameDigitalWrite(port, this._digitalPorts[port]));
  }
  async analogWrite(pin, value) { await this.t.write(frameAnalogWrite(pin, value)); }
  /** Firmata's REPORT_ANALOG takes the analog CHANNEL, not the digital pin. */
  async reportAnalog(pin, enable = true) {
    const channel = this.analogMapping[pin] ?? (pin & 0x0f);
    await this.t.write(frameReportAnalog(channel, enable));
  }
  async reportDigital(port, enable = true) { await this.t.write(frameReportDigital(port, enable)); }
  async setSamplingInterval(ms) { await this.t.write(frameSamplingInterval(ms)); }

  // ---- vendor peripherals
  async oneWireWrite(pin, payload) { await this.t.write(frameOneWireWrite(pin, payload)); }
  async peripheral(pin, func, ...args) { await this.t.write(framePeripheral(pin, func, ...args)); }

  async poll(ms = 200) { return this._drain(ms); }
  async close() { await this.t.close(); }
}
