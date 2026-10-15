/**
 * UCMake vendor realtime CLI — the text protocol the UCMakeDesktop app itself drives.
 *
 * UCMake does **not** talk Firmata to these boards for realtime control. It sends short text
 * commands: `A<function> <args…>` terminated by LF+CR at 115200 8N1. The firmware file is *named*
 * `arduinoUno.standardFirmata.ino.hex` — there is no Firmata in the image.
 *
 * ⚠️ **Rewritten 2026-10-14 against the bench-verified protocol.** What this file used to say, and
 * what is now known to be true:
 *
 *   old (stale)                        verified
 *   ---------------------------------  ---------------------------------------------------------
 *   `A17 <pin> 0 0 <speed> 0` (L3)     `A8 <motor> 0 0 <speed> 0`. Field 1 is a **MOTOR NUMBER**
 *                                      (1 = M1, 2 = M2), *not a pin*; `A17` is not a verb on this
 *                                      image. Sending a pin silently does nothing — the one bug
 *                                      that cost a full day.
 *   `A9 <pin> 1 <axis>` (tracker)      `A9 16 2 2 <axis>`. The `2 2` field is required (without it
 *                                      the board is silent) and the port must be the NUMBER 16 —
 *                                      the `A2` spelling saturates at 1023.
 *   display on pin 27                  `A10 18 <value>` — the display is port B = pin 18.
 *   light/sound via `A16 17 0`         light is `A16 21 0` (pin 21 = A7, built in); touch is
 *                                      `A20 15 0`; buttons/LEDs are `A3 19 …`.
 *   buzzer by any verb                 **no realtime command exists** — tone is sketch-only.
 *
 * The command spellings now live in `ucmind300.js`, with the bench evidence in comments. This module
 * is the transport-level client that the lab, the probes and the lesson pages share, plus the
 * profile table that says which pin each module sits on.
 *
 * **Writes are fire-and-forget — silence means success. Reads answer with text.** Never gate
 * progress on a reply to an actuator command.
 */

import { SerialPortTransport, WebSerialTransport } from './firmata.js';
import {
  ANALOG_MAX,
  BAUD,
  BUZZER_UNSUPPORTED,
  LED_COUNT,
  LINE_TRACKER_AXES,
  MOTOR,
  MOTOR_COUNT,
  PINS,
  PORT_NAMES,
  TERMINATOR,
  UcmakeClient,
  UcmakeCommandError,
  buttonRead,
  checkReply,
  display as buildDisplay,
  ledSet,
  lineTrackerRead,
  lightRead,
  motorRun,
  motorStop,
  parseAnalog,
  servo as buildServo,
  soundRead,
  touchRead,
  ultrasonicRead,
  unsupportedOnRealtime,
} from './ucmind300.js';

export {
  ANALOG_MAX, TERMINATOR, UcmakeCommandError, UcmakeClient, PINS,
  BAUD, BUZZER_UNSUPPORTED, LED_COUNT, LINE_TRACKER_AXES, MOTOR, MOTOR_COUNT, PORT_NAMES,
};
export const CLI_BAUD = BAUD;

/**
 * Board profiles for the CLI path — **the single profile table**, used by both this client and
 * `board.js`.
 *
 * `UC-Mind300` is the AVR kit and is **bench-verified**. `UC-Mind100` is the ESP32 kit: its pin map
 * is the vendor's own but its command set was not verified on this bench, so it is flagged
 * `verified: false` rather than presented as equally known.
 *
 * Keys are named for the module so the lesson API and the client cannot drift apart.
 */
export const PROFILES = {
  'UC-Mind100': {
    name: 'UC-Mind100', deviceId: 'arduinoEsp32Min', level: 'L2',
    protocol: 'cli', verified: false, baudRate: BAUD,
    displayPin: 27, ledPin: 25, trackerPin: null,
    lightPin: null, touchPin: null,
    ports: { A: 25, B: 27 },
    motors: 2, differential: true,
    display: true, leds: 4, buttons: 4, lineTracker: 2,
    light: false, touch: false, servo: true,
    buzzer: false,
    hasBle: true, hasElectromagnet: true,
  },
  'UC-Mind300': {
    name: 'UC-Mind300', deviceId: 'arduinoUno', level: 'L3',
    protocol: 'cli', verified: true, baudRate: BAUD,
    displayPin: PINS.display,          // 18  — port B
    ledPin: PINS.ledButton,            // 19  — port A
    trackerPin: PINS.lineTracker,      // 16  — port C
    touchPin: PINS.touch,              // 15  — port D
    lightPin: PINS.light,              // 21  — A7, built in
    pins: PINS,
    ports: { A: PINS.ledButton, B: PINS.display, C: PINS.lineTracker, D: PINS.touch },
    motors: 2, differential: true,
    display: true, leds: 4, buttons: 4, lineTracker: 2,
    light: true, touch: true, servo: true,
    servoPins: [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
    buzzer: false,
    analogPin: PINS.light,             // the built-in light sensor, A16 21 0
    hasBle: false, hasElectromagnet: false,
  },
};

/** Accept a board name or an already-resolved profile. */
export function profileFor(name) {
  if (typeof name !== 'string') return name ?? PROFILES['UC-Mind300'];
  const p = PROFILES[name];
  if (!p) throw new RangeError(`unknown board ${name} (have ${Object.keys(PROFILES).join(', ')})`);
  return p;
}

/** The vendor firmware panics (and reboots) instead of returning an error on some bad reads. */
export class BoardResetError extends Error {
  constructor(reply) {
    super('board firmware panicked and rebooted — ' + String(reply).split('\n')[0].slice(0, 90));
    this.name = 'BoardResetError';
    this.reply = reply;
  }
}

const PANIC = /Guru Meditation|panicked|abort\(\)/;
const number = (text) => {
  const m = String(text).match(/-?\d+(?:\.\d+)?/);
  return m ? Number(m[0]) : null;
};

/**
 * Turn a raw reply into either a reading or an exception.
 *
 * Order matters: the firmware's own error strings are checked first, then a panic. A panic message
 * can contain digits, so decoding a reply *before* this check would hand a crash dump back as if it
 * were a sensor reading — which is exactly the confusion this function exists to prevent.
 */
export function decodeReply(command, raw) {
  const text = checkReply(command, raw);
  if (PANIC.test(text)) throw new BoardResetError(text);
  return text;
}

/**
 * Vendor realtime CLI client. Transport-injectable, so tests need no hardware.
 *
 * Defaults to the verified UC-Mind300 profile. Every actuator command is built by `ucmind300.js`,
 * so the spelling is asserted in exactly one place.
 */
export class UCMakeCli {
  constructor(transport, profile = PROFILES['UC-Mind300']) {
    this.profile = profileFor(profile);
    this.t = transport;
    this.c = new UcmakeClient(transport, { timeout: this.profile.readTimeout ?? 400 });
    this.log = this.c.log;                     // every command sent, for tests and debugging
    this.sensors = {};                         // pin -> kind, for optional plug-in modules
  }

  /** The raw text of the last command sent. */
  get last() { return this.c.last; }

  /**
   * Declare a plug-in module's pin before reading it, e.g. `declareSensors({ 6: 'ultrasonic' })`.
   *
   * Only for modules a lesson may or may not have attached. The fixed devices (display 18,
   * buttons/LEDs 19, tracker 16, touch 15, light 21) are known and need no declaration, so a simple
   * lesson never has to call this. The guard exists because on the ESP32 kit an unconfigured pin
   * genuinely panics the firmware and drops the session.
   */
  declareSensors(map) { Object.assign(this.sensors, map); return this; }

  _require(pin, kind) {
    if (this.sensors[pin] !== kind) {
      throw new Error(
        `pin ${pin} is not a declared ${kind} (declared: ${JSON.stringify(this.sensors)}) — ` +
        `declare it with declareSensors({ ${pin}: '${kind}' }) before reading`,
      );
    }
    return true;
  }

  // ---- transport -----------------------------------------------------------------
  /** Send one command exactly as UCMake does (space-joined args, LF+CR terminated). */
  async send(...parts) { return this.c.send(parts.join(' ')); }

  /**
   * Send a read command and return its decoded text reply ('' when the board stays silent).
   *
   * The reply is checked for the firmware's error strings *and* for a panic before it is returned:
   * both mean "this is not a reading". Reads are async, so a caller must `await` — a forgotten
   * `await` would otherwise turn a rejected read into an unhandled rejection instead of an error at
   * the call site.
   */
  async query(parts, ms) {
    const line = Array.isArray(parts) ? parts.join(' ') : String(parts);
    return decodeReply(line, await this.c.raw(line, ms ?? this.c.readTimeout));
  }

  /** A read that answers with one analog level (0..1023) — panics and errors still throw. */
  async _readNumber(line) { return parseAnalog(await this.query([line])); }

  // ---- actuators (fire-and-forget; silence means success) -------------------------
  /**
   * DC motor by **motor number** (1 = M1, 2 = M2) — not by pin — with the vendor's own
   * `A8 <motor> 0 0 <speed> 0`.
   *
   * `motor(speed)` is also accepted: it drives M1, which is the one-motor shape a first lesson
   * wants. A pin can never reach the wire here — `motorRun()` rejects anything but 1, 2 or the
   * differential pair, because a pin number is precisely the mistake that used to fail silently.
   */
  async motor(motorOrSpeed, maybeSpeed) {
    const oneArg = maybeSpeed === undefined;
    return this.c.send(motorRun(oneArg ? 1 : motorOrSpeed, oneArg ? motorOrSpeed : maybeSpeed));
  }

  /** Stop M1/M2 by number; with no argument, the vendor's stop-all. */
  async motorStop(index) {
    return index === undefined ? this.c.stopAll() : this.c.send(motorStop(index));
  }

  /** The vendor's hardcoded stop-all, `A8 10 3 0 0 0`. */
  async stopAll() { return this.c.stopAll(); }

  /** Differential turn — left wheel speed / right wheel speed, `A8 10 2 0 <left> <right>`. */
  async driveTurn(left, right) { return this.c.turn(left, right); }

  /** Straight-line differential move, `A8 10 1 <lrfb> <speed> 0`. */
  async driveMove(lrfb, speed) { return this.c.move(lrfb, speed); }

  /** 4-digit display — port B = pin 18 on the UC-Mind300. Fire-and-forget. */
  async display(value, pin = this.profile.displayPin) {
    return this.c.send(buildDisplay(value, pin));
  }

  /**
   * 4-button / 4-LED module. `index` selects the LED (the vendor starts at 1).
   *
   * All three spellings are accepted:
   *   ledButton(1, true)               lesson-shaped: index, on     (uses the profile's port)
   *   ledButton(19, 1, true)           vendor-shaped: pin, index, on
   *   setLed(1, true)                  the same thing by name
   *
   * The vendor template is `A3 <pin> 2 <index> ${"HIGH"===LEVEL?0:1}` — **HIGH is sent as 0**, so
   * `on: true` puts a `0` on the wire. `ledSet()` in `ucmind300.js` owns that inversion.
   */
  async ledButton(a, b, c) {
    const explicitPin = c !== undefined;         // (pin, index, on) vs (index, on)
    const pin = explicitPin ? a : (this.profile.ledPin ?? PINS.ledButton);
    const index = explicitPin ? b : a;
    const on = explicitPin ? c : b;
    return this.c.send(ledSet(index, !!on, pin));
  }

  /** Lesson-ordered alias: `setLed(index, on)` on the profile's LED module. */
  async setLed(index, on) { return this.c.setLed(index, on); }

  /** 360° servo: `A6 <pin> <angle>`. */
  async servo(pin, angle) { return this.c.send(buildServo(pin, angle)); }
  /** Legacy name for the same command. */
  async servo360(pin, value) { return this.servo(pin, value); }

  async ble(pin, on) {
    if (!this.profile.hasBle) throw unsupportedOnRealtime(`${this.profile.name}: BLE`);
    return this.send('A7', pin, on ? 1 : 0);
  }

  async electromagnet(pin, on) {
    if (!this.profile.hasElectromagnet) throw unsupportedOnRealtime(`${this.profile.name}: electromagnet`);
    return this.send('A12', pin, on ? 1 : 0);
  }

  /**
   * Tone is sketch-only — the vendor's block is `mechanism: "local"` and compiles to
   * `UCBuzzer::tone()`; no realtime command exists (14 verbs probed on the bench, no tone).
   * Refused explicitly so silence is never mistaken for a working buzzer. The sketch path
   * (`codegen.js` + `upload.mjs`) is the real mechanism and is not emulated here.
   */
  async tone() { throw unsupportedOnRealtime('buzzer/tone', 'sketch-only'); }
  async buzzer() { throw unsupportedOnRealtime('buzzer/tone', 'sketch-only'); }

  // ---- sensors (reads; they DO answer) --------------------------------------------
  /** Line tracker, port C = pin 16: `A9 16 2 2 <axis>`, analog 0..1023. */
  async readLineTracker(axis, pin = this.profile.trackerPin ?? PINS.lineTracker) {
    return this._readNumber(lineTrackerRead(axis, pin));
  }
  /** The vendor's block name for the same read. */
  async read2LineFollower(pinOrAxis, maybeAxis) {
    return maybeAxis === undefined ? this.readLineTracker(pinOrAxis) : this.readLineTracker(maybeAxis, pinOrAxis);
  }

  /** Built-in light sensor, pin 21 = A7: `A16 21 0`, analog ~0..1023. */
  async readLight(pin = this.profile.lightPin ?? PINS.light) {
    return this._readNumber(lightRead(pin));
  }

  /** Capacitive touch, port D = pin 15: `A20 15 0`. **Binary** — returns true/false, not a level. */
  async readTouch(pin = this.profile.touchPin ?? PINS.touch) {
    const n = number(await this.query([touchRead(pin)]));
    return n === null ? null : n !== 0;
  }

  /** Read one button (1..4) -> true when pressed. */
  async readButton(level, pin = this.profile.ledPin ?? PINS.ledButton) {
    const n = number(await this.query([buttonRead(level, pin)]));
    return n === null ? null : n !== 0;
  }

  /** All four buttons -> `[b1, b2, b3, b4]` of true/false. */
  async readButtons(pin = this.profile.ledPin ?? PINS.ledButton) {
    const replies = await Promise.all([1, 2, 3, 4].map((i) => this.query([buttonRead(i, pin)])));
    return replies.map((text) => {
      const n = number(text);
      return n === null ? null : n !== 0;
    });
  }

  /** The vendor's name for one button read ("LED button pressed?"). */
  async readLedButtonDigital(pin, level) { return this.readButton(level, pin); }

  /** Ultrasonic distance in cm — an optional module, so its pin must be declared first. */
  async readUltrasonic(pin) {
    this._require(pin, 'ultrasonic');
    return this._readNumber(ultrasonicRead(pin));
  }

  /** Sound sensor at the AVR's fixed channel (`A15 17 0`). Not bench-verified for the L3 kit. */
  async readSound(pin = 17) { return this._readNumber(soundRead(pin)); }

  // Convenience aliases matching the lesson-facing names in `board.js`.
  async lineTracker(axis) { return this.readLineTracker(axis); }
  async light() { return this.readLight(); }
  async touch() { return this.readTouch(); }
  async buttons() { return this.readButtons(); }

  async close() { await this.c.close(); }
}

/** Open a CLI session over a serial port (Node) — 115200, as UCMake uses. */
export async function openCli(port, profile = PROFILES['UC-Mind300']) {
  const t = await SerialPortTransport.open(port, { baudRate: CLI_BAUD });
  return new UCMakeCli(t, profile);
}

/** Ask the browser for a port (lab page). */
export async function requestCli(profile = PROFILES['UC-Mind300']) {
  const t = await WebSerialTransport.request({ baudRate: CLI_BAUD });
  return new UCMakeCli(t, profile);
}

export { checkReply };
