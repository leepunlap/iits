/**
 * Lesson-level board API for the Wonder Lab — **UC-Mind300 running the vendor text CLI**.
 *
 * This replaces the Firmata implementation that used to live here. The board does **not** run
 * StandardFirmata: it runs the vendor's `A`-command text CLI at 115200 8N1 (bench-verified; see
 * `../CLI-PROTOCOL-SOLVED-2026-10-14.md`). The old `setPinMode` / `digitalWrite` / `analogWrite`
 * calls did not exist on the wire in any useful form, and `capabilities()` advertised a buzzer and
 * a servo that the realtime path cannot drive.
 *
 * The protocol itself lives in `ucmind300.js`; this file is the shape a lesson sees:
 *
 *   display.show(n)              motor.run(index, speed)      motor.stop(index)
 *   drive.turn(left, right)      drive.move(lrfb, speed)      drive.stop()
 *   sensor.lineTracker(axis)     sensor.light()               sensor.touch()
 *   buttons.read(level)          leds.set(index, on)          servo(pin, angle)
 *
 * Two rules are enforced here so a lesson cannot trip over them:
 *
 *   * **Writes never wait for a reply.** `display.show()` resolves as soon as the bytes are on the
 *     wire. The firmware is silent on success — waiting for an ack makes a working board look dead.
 *   * **Motor and LED indices are 1-based** (`motor.run(1, 150)`, `leds.set(1, true)`), matching
 *     the board's own M1/M2 and K1..K4 labels and the vendor's indices. The old Firmata API was
 *     0-based; that change is deliberate and is called out in `MIGRATION` below.
 *
 * Tone/buzzer is **sketch-only** and is refused explicitly rather than faked — see `buzzer()`.
 */

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
  unsupportedOnRealtime,
} from './ucmind300.js';
import { PROFILES as CLI_PROFILES, profileFor as cliProfileFor } from './ucmake_cli.js';

/**
 * Pick a profile. Accepts a board name, an existing profile, or an info object as older callers
 * passed (a `pins` count is all a bare Firmata identify ever gave us).
 */
export function profileFor(info) {
  if (typeof info === 'object' && info !== null) {
    const pins = info.pins ?? 0;
    return pins >= 32 ? PROFILES['UC-Mind100'] : PROFILES['UC-Mind300'];
  }
  return cliProfileFor(info);
}

/**
 * Board profiles — re-exported from `ucmake_cli.js`, which owns the single table.
 *
 * Before this was unified, `board.js` and `ucmake_cli.js` each carried a profile with the same name
 * and different fields (`motors` was a count in one and a pin list in the other, `displayPin` was 18
 * in one and 27 in the other). Two tables for one board is how a pin number ends up back on the
 * wire, so there is now exactly one.
 */
export const PROFILES = CLI_PROFILES;

export {
  ANALOG_MAX, BAUD, BUZZER_UNSUPPORTED, LED_COUNT, LINE_TRACKER_AXES,
  MOTOR, MOTOR_COUNT, PINS, PORT_NAMES, TERMINATOR, UcmakeClient,
};

const requireIndex1 = (index, count, what) => {
  const n = Number(index);
  // Integer check first, on the ORIGINAL value: silently truncating 2.5 to 2 would pick the wrong
  // motor/LED instead of telling the lesson about its bug.
  if (!Number.isInteger(n) || n < 1 || n > count) {
    throw new RangeError(`${what} must be 1..${count} (board labels start at 1), got ${index}`);
  }
  return n;
};

/**
 * A UC-Mind300 (or UC-Mind100) driven by the vendor CLI.
 *
 * @param {object} clientOrTransport  a `UcmakeClient`, or a transport with `write()`/`read()`
 * @param {object} [profile]          defaults to the UC-Mind300 profile
 */
export class UCMindBoard {
  constructor(clientOrTransport, profile = PROFILES['UC-Mind300']) {
    this.profile = typeof profile === 'string' ? profileFor(profile) : profile;
    this.client = clientOrTransport instanceof UcmakeClient
      ? clientOrTransport
      : new UcmakeClient(clientOrTransport);
    this.cli = this.client;                    // alias: older callers reached for `.cli`
    // `ports` is the smart-module port map ({A, B, C, D} -> digital pin), NOT the named-pin set —
    // `lab.html` and the lesson pages read `session.board.profile.analogPin` and friends.
    this.ports = this.profile.ports ?? {};
    this.declared = {};                        // pin -> kind, only for optional plug-in modules
  }

  // ---------------------------------------------------------------- display
  /** 4-digit display: `A10 18 <value>`. Fire-and-forget — silence is success. */
  get display() {
    const board = this;
    return {
      show(value) { return board.client.display(value); },
      clear() { return board.client.display(0); },
    };
  }

  // ---------------------------------------------------------------- motors
  /**
   * M1 / M2 by **number** (1 or 2) — not by pin. `speed` is -255..255 and its sign is the
   * direction (reverse is assumed but was not part of the bench run; see the protocol file).
   */
  get motor() {
    const board = this;
    return {
      run(index, speed) { return board.client.run(board._motor(index), speed); },
      stop(index) { return board.client.stop(board._motor(index)); },
      /** Stop both motors. Uses the vendor's own stop-all form, `A8 10 3 0 0 0`. */
      stopAll() { return board.client.stopAll(); },
      get count() { return board.profile.motors; },
    };
  }

  _motor(index) {
    if (!this.profile.motors) {
      throw unsupportedOnRealtime(`${this.profile.name}: motors`, 'not exposed by this firmware build');
    }
    return requireIndex1(index, this.profile.motors, 'motor index');
  }

  // ---------------------------------------------------------------- drive
  /**
   * Differential drive.
   *
   * `turn(left, right)` is the vendor's *left wheel speed / right wheel speed* — the true
   * differential form, `A8 10 2 0 <left> <right>`. With both wheels positive it drives straight;
   * equal and opposite spins on the spot.
   *
   * `move(lrfb, speed)` is the vendor's *Motor Move* form, `A8 10 1 <lrfb> <speed> 0`, whose first
   * field is the vendor's own left/right/forward/back selector. Both are here because the protocol
   * notes and the vendor catalogue disagree about which of them is "the turn" — `driveTurn` in
   * `ucmind300.js` records the contradiction and this API does not hide it.
   */
  get drive() {
    const board = this;
    return {
      turn(left, right) { return board.client.turn(left, right); },
      move(lrfb, speed) { return board.client.move(lrfb, speed); },
      stop() { return board.client.stopAll(); },
    };
  }

  // ---------------------------------------------------------------- sensors
  /** Reads DO reply with text. `light`/`lineTracker` are analog 0..1023; `touch` is binary. */
  get sensor() {
    const board = this;
    return {
      lineTracker(axis = 1) { return board.client.readLineTracker(axis); },
      light() { return board.client.readLight(); },
      touch() { return board.client.readTouch(); },
      /** Optional plug-in module: the pin must be declared first (see `declareSensors`). */
      ultrasonic(pin) { board._requireUltrasonic(pin); return board.client.readUltrasonic(pin); },
    };
  }

  // ---------------------------------------------------------------- buttons / LEDs
  /**
   * Read one button (1..4). `true` = pressed. Answers over the wire; a read, so it does wait.
   *
   * The index is validated **synchronously**, before any promise exists, so a bad index throws at
   * the call site rather than surfacing as an unawaited rejected promise.
   */
  get buttons() {
    const board = this;
    return {
      read(level) {
        const i = requireIndex1(level, LED_COUNT, 'button index');
        return board.client.readButton(i);
      },
      /** All four at once -> `[b1, b2, b3, b4]` of true/false. */
      readAll() { return board.client.readButtons(); },
    };
  }

  /**
   * Set one LED (1..4) of the 4-LED module: `A3 19 2 <index> <level>`.
   * ⚠️ The vendor sends HIGH as `0`, so `on: true` puts `0` on the wire — `ledSet()` handles it.
   */
  get leds() {
    const board = this;
    const idx = (index) => requireIndex1(index, LED_COUNT, 'LED index');
    return {
      set(index, on = true) { return board.client.setLed(idx(index), !!on); },
      on(index) { return board.client.setLed(idx(index), true); },
      off(index) { return board.client.setLed(idx(index), false); },
      all(on = true) { return Promise.all([1, 2, 3, 4].map((i) => board.client.setLed(i, !!on))); },
      get count() { return LED_COUNT; },
    };
  }

  // ---------------------------------------------------------------- other actuators
  /** 360° servo: `A6 <pin> <angle>`. Pin-validated against the profile's servo pins. */
  async servo(pin, angle) {
    if (!this.profile.servo) throw unsupportedOnRealtime(`${this.profile.name}: servo`);
    const allowed = this.profile.servoPins;
    if (allowed && !allowed.includes(Number(pin))) {
      throw new RangeError(`${this.profile.name}: pin ${pin} is not a servo pin (have ${allowed.join(', ')})`);
    }
    return this.client.setServo(pin, angle);
  }

  /**
   * Tone is **not reachable over the realtime CLI** — the vendor's block is `mechanism: "local"`
   * and compiles to `UCBuzzer::tone()` in the sketch, and 14 verbs were probed on the bench with no
   * tone. This throws instead of pretending; the build-and-upload path (`codegen.js` + `upload.mjs`)
   * is the real mechanism for tone and is deliberately not emulated here.
   */
  async buzzer() { throw unsupportedOnRealtime('buzzer/tone', 'sketch-only'); }

  // ---------------------------------------------------------------- optional modules
  /**
   * Declare a plug-in module's pin before reading it, e.g. `declareSensors({ 6: 'ultrasonic' })`.
   *
   * Only the *optional* module needs this. The built-in devices (light sensor), the on-board
   * motors, and the smart modules the lesson is required to drive (display on 18, buttons/LEDs on
   * 19, tracker on 16, touch on 15) are fixed pins and need no declaration — so the simple lesson
   * API stays simple.
   */
  declareSensors(map) { Object.assign(this.declared, map); return this; }

  _requireUltrasonic(pin) {
    if (this.declared[pin] !== 'ultrasonic') {
      throw new Error(
        `pin ${pin} is not a declared ultrasonic module (declared: ${JSON.stringify(this.declared)}) — ` +
        'declare it with declareSensors({ <pin>: \'ultrasonic\' }) before reading',
      );
    }
    return true;
  }

  // ---------------------------------------------------------------- capability report
  /** What this board can actually do — the lab gates its controls on this, not on the protocol name. */
  capabilities() {
    const p = this.profile;
    const has = (v) => !!v;
    return {
      board: p.name,
      level: p.level,
      protocol: p.protocol ?? 'cli',
      firmware: p.deviceId,
      motors: p.motors ?? 0,
      differential: has(p.differential),        // A8 10 … (turn / move)
      display: has(p.display),
      leds: p.leds ?? 0,
      buttons: p.buttons ?? 0,
      lineTracker: p.lineTracker ?? 0,
      light: has(p.light),
      touch: has(p.touch),
      servo: has(p.servo),
      ultrasonic: true,                          // optional module; needs declareSensors()
      analogIn: true,
      buzzer: false,                             // sketch-only, by design — see buzzer()
      tone: false,
      realtime: true,
      sketchOnly: p.buzzer ? [] : ['buzzer/tone'],
      analogMax: ANALOG_MAX,
    };
  }

  /** Every command this board has been asked to send, in order. */
  get log() { return this.client.log; }

  async close() { return this.client.close(); }
}

/**
 * ⚠️ MIGRATION from the Firmata board API that used to live in this file.
 *
 * 0-based -> 1-based: `motor(0, 120)` is now `motor.run(1, 120)`, `motorStop(0)` is
 * `motor.stop(1)`, `led(1)` is `leds.set(1, …)` — M1/M2 and K1..K4 are the board's own labels.
 * `readAnalog(pin)` is gone (there is no analog-reporting mode over the CLI); use
 * `sensor.light()` / `sensor.lineTracker(axis)` / `sensor.touch()`.
 * `buzzer(on)` is gone by design: tone is sketch-only and now throws.
 */
export const MIGRATION = 'motor(0)->motor.run(1); motorStop(0)->motor.stop(1); readAnalog()->sensor.*';

/** Convenience: a board on an already-open transport, at the CLI baud. */
export function boardOn(transport, { profile = PROFILES['UC-Mind300'], timeout } = {}) {
  return new UCMindBoard(new UcmakeClient(transport, timeout ? { timeout } : {}), profile);
}
