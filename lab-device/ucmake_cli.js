/**
 * UCMake vendor realtime protocol — the text CLI the UCMakeDesktop app itself drives.
 *
 * UCMake does NOT talk Firmata to these boards. For realtime it flashes the vendor CLI firmware
 * (`arduinoESP32Min.standardFirmata.ino.bin` / `arduinoUno.standardFirmata.ino.hex`) and then sends
 * short text commands:  `A<function> <args…>` terminated by LF+CR, 115200 8N1.
 *
 * Every template below is copied from the app's own runtime handlers (`vendors.js`), so the lab
 * sends byte-for-byte what UCMake sends. Writes are fire-and-forget; reads answer with text.
 *
 *   ESP32-min (UC-Mind100 / L2)   ESP32 + others (UC-Mind300 / L3)
 *   A8  <pin> 0 0 <speed> 0       A17 <pin> 0 0 <speed> 0     DC motor
 *   A8  10 3 0 0 0                A17 0 3 0 0 0              stop all motors
 *   A10 <pin> <value>             A10 <pin> <value>          4-digit display
 *   A5  <pin> 4                   A16 <pin> 4                ultrasonic distance (read)
 *   A9  <pin> 1 <axis>            A9  <pin> 1 <axis>         line follower (read)
 *   A4  <pin> 3 <index>           A4  <pin> 3 <index>        colour sensor (read)
 *   A3  <pin> 1 <level>           —                          LED button (read)
 *   A6  <pin> <value>             A5  <pin> <value>          360° servo
 *   A7  <pin> <0|1>               —                          BLE on/off
 *   A12 <pin> <0|1>               —                          electromagnet
 *   —                             A16 21 0 / A15 17 0        light / sound sensor (read)
 */

import { SerialPortTransport, WebSerialTransport } from './firmata.js';

export const CLI_BAUD = 115200;
export const TERMINATOR = '\n\r';          // UCMake sends LF then CR

export const PROFILES = {
  'UC-Mind100': {
    name: 'UC-Mind100', deviceId: 'arduinoEsp32Min', level: 'L2',
    motorFn: 8, servoFn: 6, hasBle: true, hasElectromagnet: true,
    displayPin: 27, motorPins: [10, 11], ledPin: 25,   // ports: A1=27 (display), A2=25 (4-LED module)
  },
  'UC-Mind300': {
    name: 'UC-Mind300', deviceId: 'arduinoUno', level: 'L3',
    motorFn: 17, servoFn: 5, hasBle: false, hasElectromagnet: false,
    displayPin: 27, motorPins: [1, 2],
  },
};

export function profileFor(name) {
  const p = PROFILES[name];
  if (!p) throw new RangeError(`unknown board ${name} (have ${Object.keys(PROFILES).join(', ')})`);
  return p;
}

const hex = (s) => Uint8Array.from([...s].map((c) => c.charCodeAt(0)));

/** The vendor firmware panics (and reboots) instead of returning an error on a bad read. */
export class BoardResetError extends Error {
  constructor(reply) {
    super('board firmware panicked and rebooted — ' + reply.split('\n')[0].slice(0, 90));
    this.name = 'BoardResetError';
    this.reply = reply;
  }
}

const PANIC = /Guru Meditation|panicked|abort\(\)/;

/** Vendor realtime CLI client. Transport-injectable, so tests need no hardware. */
export class UCMakeCli {
  constructor(transport, profile = PROFILES['UC-Mind100']) {
    this.t = transport;
    this.profile = profile;
    this.log = [];                     // every command sent, for tests and debugging
    this.sensors = {};                 // pin -> kind, declared by the lesson set-up
  }

  /**
   * Declare which modules are physically attached, e.g. `declareSensors({ 6: 'ultrasonic' })`.
   *
   * This is not bureaucracy: reading a pin with no module on it **panics the vendor firmware**
   * ("Guru Meditation Error", verified 2026-10-11 on `A5 6 4`). The board reboots, which drops the
   * session — so the lab refuses to read a pin the lesson has not declared.
   */
  declareSensors(map) { Object.assign(this.sensors, map); return this; }

  _require(pin, kind) {
    if (this.sensors[pin] !== kind) {
      throw new Error(
        `pin ${pin} is not a declared ${kind} (declared: ${JSON.stringify(this.sensors)}) — ` +
        'reading an unconfigured pin panics the vendor firmware and reboots the board');
    }
    return true;
  }

  /** Send one command, exactly as UCMake does (arguments joined by spaces, LF+CR terminated). */
  async send(...parts) {
    const line = parts.join(' ');
    this.log.push(line);
    await this.t.write(hex(line + TERMINATOR));
    return line;
  }

  /** Send a read command and return the decoded reply ('' on timeout). */
  async query(parts, ms = 800) {
    await this.t.drain?.();
    await this.send(...parts);
    const raw = await this.t.read(256, ms);
    const text = new TextDecoder().decode(raw ?? new Uint8Array()).trim();
    // A missing module makes the firmware panic and reboot: the session is gone, so say so
    // rather than handing a crash dump back as if it were a sensor reading.
    if (PANIC.test(text)) throw new BoardResetError(text);
    return text;
  }

  // ---- actuators -----------------------------------------------------------------
  /** DC motor: sign is direction, magnitude is speed. */
  async motor(pin, speed) {
    return this.send(`A${this.profile.motorFn}`, pin, 0, 0, speed, 0);
  }
  async motorStop() {
    const f = this.profile.motorFn;
    return f === 8 ? this.send('A8', 10, 3, 0, 0, 0) : this.send('A17', 0, 3, 0, 0, 0);
  }
  /** 4-digit display, pin 27 on both kits; the value is plain decimal (8888 shows 8888). */
  async display(value, pin = this.profile.displayPin) {
    return this.send('A10', pin, value);
  }
  /**
   * 4-button / 4-LED module. `index` selects the LED (the vendor's menu starts at 1).
   * The vendor's template is `A3 <pin> 2 <index> ${"HIGH"===LEVEL?0:1}` — i.e. **HIGH is sent
   * as 0**, so `on: true` sends 0. (On the UC-Mind100 the module sits on port A2 = pin 25.)
   */
  async ledButton(pin, index, on) {
    return this.send('A3', pin, 2, index, on ? 0 : 1);
  }
  /** Read one of the four buttons; `level` is the vendor's LED-button index (1-4). */
  async readLedButtonDigital(pin, level) {
    this._require(pin, 'ledButton');
    return this.query(['A3', pin, 1, level]);
  }
  /** Read all four buttons on the module at `pin` -> [b1, b2, b3, b4] as booleans. */
  async readButtons(pin) {
    const out = [];
    for (let i = 1; i <= 4; i += 1) out.push((await this.readLedButtonDigital(pin, i)) === '1');
    return out;
  }
  async servo360(pin, value) {
    return this.send(`A${this.profile.servoFn}`, pin, value);
  }
  async ble(pin, on) {
    if (!this.profile.hasBle) throw new Error(`${this.profile.name}: no BLE block on this board`);
    return this.send('A7', pin, on ? 1 : 0);
  }
  async electromagnet(pin, on) {
    if (!this.profile.hasElectromagnet) throw new Error(`${this.profile.name}: no electromagnet on this board`);
    return this.send('A12', pin, on ? 1 : 0);
  }

  // ---- sensors (reads) -----------------------------------------------------------
  /** Ultrasonic distance in cm. */
  async readUltrasonic(pin) {
    this._require(pin, 'ultrasonic');
    const fn = this.profile.deviceId === 'arduinoEsp32Min' ? 'A5' : 'A16';
    return this.query([fn, pin, 4]);
  }
  async readLineFollower(pin, axis) {
    this._require(pin, 'lineFollower');
    return this.query(['A9', pin, 1, axis]);
  }
  async read5LineFollower(pin, axis) {
    this._require(pin, 'lineFollower');
    return this.query(['A9', pin, 2, 5, axis]);
  }
  async read2LineFollower(pin, axis) {
    this._require(pin, 'lineFollower');
    return this.query(['A9', pin, 2, 2, axis]);
  }
  async readColor(pin, index) {
    this._require(pin, 'color');
    return this.query(['A4', pin, 3, index]);
  }
  async readLedButton(pin, level) {
    this._require(pin, 'ledButton');
    return this.query(['A3', pin, 1, level]);
  }
  /** L3 only: the AVR kit has fixed channels for these. */
  async readLight() { return this.query(['A16', 21, 0]); }
  async readSound() { return this.query(['A15', 17, 0]); }

  async close() { await this.t.close?.(); }
}

/** Open a CLI session over a serial port (Node) — 115200, as UCMake uses. */
export async function openCli(port, profile = PROFILES['UC-Mind100']) {
  const t = await SerialPortTransport.open(port, { baudRate: CLI_BAUD });
  return new UCMakeCli(t, profile);
}

/** Ask the browser for a port (lab page). */
export async function requestCli(profile = PROFILES['UC-Mind100']) {
  const t = await WebSerialTransport.request({ baudRate: CLI_BAUD });
  return new UCMakeCli(t, profile);
}
