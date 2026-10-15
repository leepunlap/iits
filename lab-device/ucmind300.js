/**
 * UC-Mind300 (AVR) — the vendor's **text CLI**, bench-verified 2026-10-14.
 *
 * This file is the one place the protocol facts live. Everything else in the device layer
 * (`board.js`, `ucmake_cli.js`, `lab.js`) routes through the builders here, so a correction lands
 * in one place instead of five.
 *
 * Source of truth: `../CLI-PROTOCOL-SOLVED-2026-10-14.md` (bench-verified) and the vendor's own
 * block catalogue (`../UCMAKE-SPEC-MINED.md`, mined from the shipped app data). Where the two
 * disagree the disagreement is called out in a comment rather than silently resolved — see
 * `MOVE_VS_TURN` below.
 *
 * THE THREE RULES, because each one cost real time:
 *
 *   1. NEVER block waiting for a reply after a write. Writes are fire-and-forget and are USUALLY
 *      SILENT. **Silence means success** on this firmware. Code that awaits an ack looks broken
 *      while the hardware works. Only the sensor reads answer, and they answer with text.
 *   2. The motor field is a MOTOR NUMBER (1 or 2), NOT A PIN. The pin-numbered form (`A8 10 …` /
 *      `A8 5 …`) silently does nothing on the motor you meant.
 *   3. `A8 10 …` selects a *differential pair*, not "the motor". Sending it to drive one motor
 *      still spins that motor, which is exactly how it misled everyone for a day.
 *
 * Wire format: ASCII, `\n\r` terminated (LF then CR), 115200 8N1. The firmware accepts `\n`,
 * `\r` or `\r\n` equally, and ignores extra arguments beyond `A<n> <arg1> <arg2>`.
 *
 * No transport lives here, so every builder and parser is unit-testable with no hardware.
 */

/** Command verbs (`A<n>`). Only these are implemented on this image. */
export const FN = {
  register: 1,      // A1 <port> <reg> <value>  — READ/WRITE REGISTER. Do not use as a liveness probe.
  ledButton: 3,     // A3  <pin> <1|2> …       — button read / LED write
  color: 4,         // A4  <pin> 3 <index>     — colour sensor (read)
  servo: 6,         // A6  <pin> <angle>       — 360° servo (verified against the mined catalogue)
  motor: 8,         // A8  <motor|10> 0 0 <speed> 0 — DC motors
  lineFollower: 9,  // A9  <pin> 2 2 <axis>    — line tracker (read)
  display: 10,      // A10 18 <value>          — 4-digit display
  sound: 15,        // A15 17 0                — sound sensor (read)
  light: 16,        // A16 21 0 / A16 <pin> 4  — light sensor (read) / ultrasonic distance (read)
  touch: 20,        // A20 15 0                — capacitive touch (read, BINARY)
};

/**
 * The first field of `A8` — this is a **motor selector, not a pin**, and it is the single bug that
 * cost a full day. `M1`/`M2` drive one motor; `10` drives the differential pair.
 */
export const MOTOR = { M1: 1, M2: 2, DIFFERENTIAL: 10 };

/**
 * The third field of `A8 10 …` — which differential mode.
 *
 * ⚠️ This contradicts `CLI-PROTOCOL-SOLVED-2026-10-14.md`, and the contradiction is recorded rather
 * than papered over. That file says the third field is a direction (`1`/`2`) and that
 * `A8 10 1 0 <speed> 0` drives M1 and M2 in OPPOSITE directions (a spin). The vendor's mined
 * catalogue says the opposite:
 *
 *   espMinSetDcMotorMove    "Motor Move [PIN] speed [OUT]"                 -> A8 10 1 <lrfb> <speed> 0
 *   espMinSetDcMotorMoveLR  "Left wheel speed [PIN] Right wheel speed [OUT]" -> A8 10 2 0 <-left> <right>
 *
 * i.e. `#1` is the straight-line differential move (both wheels together, pin = a left/right/
 * forward/back selector) and `#2` is the true differential drive with independent wheel speeds.
 * The same file's own measurement table labels `A8 10 1 0 150 0` "FORWARD" and `A8 10 2 0 150 0`
 * "REVERSE" — the words of the `#1`/`#2` command names, not of a spin.
 *
 * The likeliest reading is that the "opposite directions" observation came from a single-motor rig:
 * every differential command spins whichever motor is attached, which is precisely the trap the
 * file itself describes. **Not resolvable from code — `#2` is used for TURN here because that is
 * what the vendor emits for "left wheel speed / right wheel speed", and it needs one bench check.**
 */
export const DIFF = { MOVE: 1, TURN: 2, STOP: 3 };

/**
 * Smart-module ports. The vendor names ports by their **Arduino analog label**; the CLI wants the
 * **digital** pin number. From `UCMAKE-SPEC-MINED.md` §5 and the owner's bench map — both spellings
 * are accepted by the board (`A10 A4 4321` == `A10 18 8765`), and the numbers below are verified.
 */
export const PINS = {
  display: 18,      // port B / A4 — 4-digit display (verified: shows 1234 / 1818)
  ledButton: 19,    // port A / A5 — 4 buttons + 4 LEDs (verified: A3 19 1 1 -> '0')
  lineTracker: 16,  // port C / A2 — line tracker (verified: A9 16 2 2 <axis>)
  touch: 15,        // port D / A1 — capacitive touch (verified: A20 15 0 -> 0/1)
  light: 21,        // A7 — the board's BUILT-IN light sensor (verified: A16 21 0 -> ~988)
};

/** Port letters as the vendor writes them, for diagnostics and lesson copy. */
export const PORT_NAMES = { display: 'A4', ledButton: 'A5', lineTracker: 'A2', touch: 'A1' };

export const BAUD = 115200;
export const TERMINATOR = '\n\r';          // LF then CR — UCMake sends exactly this
export const LED_COUNT = 4;
export const MOTOR_COUNT = 2;
export const LINE_TRACKER_AXES = [1, 2];

/** Analog sensors report 0..1023; touch is binary. */
export const ANALOG_MAX = 1023;

// ------------------------------------------------------------------ validation
const finite = (value, what) => {
  const n = Number(value);
  if (!Number.isFinite(n)) throw new TypeError(`${what} must be a finite number, got ${JSON.stringify(value)}`);
  return n;
};

/** Truncate toward zero and clamp — the firmware takes an integer field. */
export const clamp = (value, lo, hi) => Math.max(lo, Math.min(hi, Math.trunc(finite(value, 'value'))));

/** Motor speed: -255..255. The **sign is the direction** (reverse is assumed, see the protocol file). */
export const clampSpeed = (speed) => clamp(speed, -255, 255);

/**
 * `A8 <motor> 0 0 <speed> 0` — one motor, or the differential pair for `motor === 10`.
 *
 * Anything else is refused **loudly**. The failure mode being guarded against is a *pin* landing in
 * this field: the board accepts such a line in silence and simply does nothing, which is how a day
 * was lost. Note the nasty overlap — `10` is both a historic pin number and the differential
 * selector, so it is legal here but never means "motor 10".
 */
export function motorSelector(motor) {
  const n = finite(motor, 'motor');
  if (n !== MOTOR.M1 && n !== MOTOR.M2 && n !== MOTOR.DIFFERENTIAL) {
    throw new RangeError(
      `motor must be the motor NUMBER ${MOTOR.M1} (M1) or ${MOTOR.M2} (M2), or ` +
      `${MOTOR.DIFFERENTIAL} for the differential pair — got ${motor}, which is a pin, not a motor`,
    );
  }
  return n;
}

const requireIndex = (index, count, what) => {
  const n = finite(index, what);
  if (!Number.isInteger(n) || n < 1 || n > count) {
    throw new RangeError(`${what} must be 1..${count}, got ${index}`);
  }
  return n;
};

const require0Based = (index, count, what) => requireIndex(finite(index, what) + 1, count, what) - 1;

// ------------------------------------------------------------------ builders (writes)
/**
 * `A10 18 <value>` — 4-digit display. **Silent on success.**
 *
 * The display is 4 digits, so the value is clamped to 0..9999 rather than truncated into nonsense
 * (negative values would display as garbage). The vendor's own codegen calls `showNumber(value)`.
 */
export const display = (value, pin = PINS.display) =>
  `A${FN.display} ${pin} ${clamp(value, 0, 9999)}`;

/** `A8 <motor> 0 0 <speed> 0` — run M1/M2. Negative speed is reverse (assumed, untested). */
export const motorRun = (motor, speed) =>
  `A${FN.motor} ${motorSelector(motor)} 0 0 ${clampSpeed(speed)} 0`;

/** `A8 1 0 0 0 0` / `A8 2 0 0 0 0` — stop one motor (speed 0 on the selected motor). */
export const motorStop = (motor) => motorRun(motor, 0);

/**
 * `A8 10 1 <lrfb> <speed> 0` — the vendor's `espMinSetDcMotorMove`: **straight-line** differential
 * move. `lrfb` is the vendor's left/right/forward/back selector (its own menu default is `1`;
 * forward/back are the two emitted templates, which differ only by the sign of the speed).
 */
export const driveMove = (lrfb, speed) =>
  `A${FN.motor} ${MOTOR.DIFFERENTIAL} ${DIFF.MOVE} ${finite(lrfb, 'lrfb')} ${clampSpeed(speed)} 0`;

/**
 * `A8 10 2 0 <left> <right>` — the vendor's `espMinSetDcMotorMoveLR`, i.e. **left wheel speed /
 * right wheel speed**: the real differential drive / turn.
 *
 * ⚠️ The vendor emits `-left` here (its own code negates the first wheel). We send the wheel speeds
 * as given and document the sign convention instead of copying a negation that may exist to cancel
 * a wiring quirk: `left` positive drives the left wheel forward. `drive.turn(150, 150)` is straight;
 * `drive.turn(-150, 150)` is a spin. See `DIFF` above for why `#2` is the turn.
 */
export const driveTurn = (left, right) =>
  `A${FN.motor} ${MOTOR.DIFFERENTIAL} ${DIFF.TURN} 0 ${clampSpeed(left)} ${clampSpeed(right)}`;

/** `A8 10 3 0 0 0` — the vendor's hardcoded stop-all (`espMinSetDcMotorStop`). */
export const driveStop = () => `A${FN.motor} ${MOTOR.DIFFERENTIAL} ${DIFF.STOP} 0 0 0`;

/**
 * `A3 19 2 <index> <level>` — set one LED on the 4-LED module.
 *
 * ⚠️ **The vendor inverts the level: it sends HIGH as `0`.** `"HIGH" === LEVEL ? 0 : 1` in the
 * block catalogue. So `on: true` sends 0. Getting this backwards lights the LED when the lesson
 * means to switch it off, so it is asserted in the tests.
 */
export const ledSet = (index, on, pin = PINS.ledButton) =>
  `A${FN.ledButton} ${pin} 2 ${requireIndex(index, LED_COUNT, 'LED index')} ${on ? 0 : 1}`;

/** `A6 <pin> <angle>` — 360° servo. Built here so the servo spelling has one home. */
export const servo = (pin, angle) => `A${FN.servo} ${pin} ${clamp(angle, 0, 180)}`;

// ------------------------------------------------------------------ builders (reads)
/** `A3 19 1 <level>` — read one button. Answers `0` or `1`. */
export const buttonRead = (level, pin = PINS.ledButton) =>
  `A${FN.ledButton} ${pin} 1 ${requireIndex(level, LED_COUNT, 'button index')}`;

/** `A3 19 1 <level>` for every button, in order — the lab reads all four together. */
export const buttonsRead = (pin = PINS.ledButton) => [1, 2, 3, 4].map((i) => buttonRead(i, pin));

/**
 * `A9 16 2 2 <axis>` — line tracker, ANALOG 0..1023.
 *
 * The `2 2` (module type / channel count) field is REQUIRED: `A9 16 1 <axis>` is **silent** on this
 * build. And pass the NUMBER 16 — the port-name spelling `A9 A2 …` saturates at 1023.
 */
export const lineTrackerRead = (axis, pin = PINS.lineTracker) =>
  `A${FN.lineFollower} ${pin} 2 2 ${requireIndex(axis, LINE_TRACKER_AXES.length, 'line tracker axis')}`;

/** `A16 21 0` — the board's built-in light sensor, ANALOG ~0..1023. */
export const lightRead = (pin = PINS.light) => `A${FN.light} ${pin} 0`;

/** `A20 15 0` — capacitive touch. **BINARY**, not an analog level. */
export const touchRead = (pin = PINS.touch) => `A${FN.touch} ${pin} 0`;

/** `A16 <pin> 4` — ultrasonic distance in cm. Optional hardware; the pin must be declared. */
export const ultrasonicRead = (pin) => `A${FN.light} ${pin} 4`;

/**
 * Sound sensor, for callers that have one. The UC-Mind300's fixed channel is `A15 17 0`; this was
 * never bench-verified for the L3 kit, so it is exposed but not advertised in `capabilities()`.
 */
export const soundRead = (pin = 17) => `A${FN.sound} ${pin} 0`;

// ------------------------------------------------------------------ parsers (replies)
/** True for the firmware's own error strings (UTF-8 Chinese) — chatter means FAILURE here. */
const ERROR_RE = /ERROR\b|错误|缺少参数/;

const asText = (raw) => {
  if (raw == null) return '';
  if (typeof raw === 'string') return raw.trim();
  return new TextDecoder().decode(raw).trim();
};

/** Thrown when the firmware answers with one of its error strings. */
export class UcmakeCommandError extends Error {
  constructor(command, reply) {
    super(`board rejected "${command}": ${reply.split('\n')[0].slice(0, 120)}`);
    this.name = 'UcmakeCommandError';
    this.command = command;
    this.reply = reply;
  }
}

/** Throw when a reply is an error string, else return it. An empty reply is silence = success. */
export function checkReply(command, raw) {
  const text = asText(raw);
  if (ERROR_RE.test(text)) throw new UcmakeCommandError(command, text);
  return text;
}

const firstNumber = (text) => {
  const m = text.match(/-?\d+(?:\.\d+)?/);
  return m ? Number(m[0]) : null;
};

/** Analog sensors answer 0..1023. `null` when nothing came back (silence) or the reply was junk. */
export function parseAnalog(raw) {
  const n = firstNumber(asText(raw));
  return n === null ? null : clamp(n, 0, ANALOG_MAX);
}

/** Touch is binary: `1` touched, `0` not. */
export function parseTouch(raw) {
  const n = firstNumber(asText(raw));
  return n === null ? null : n !== 0;
}

/** One button: `1` means pressed. */
export function parseButton(raw) {
  const n = firstNumber(asText(raw));
  return n === null ? null : n !== 0;
}

/** Four button replies -> `[b1, b2, b3, b4]`. Unanswered buttons read as `null`, never `false`. */
export const parseButtons = (replies) => replies.map(parseButton);

// ------------------------------------------------------------------ client
/**
 * The serial client for one board. Writes never wait; reads always do (with a timeout).
 *
 * **The `\n\r` terminator is added here**, at the single point where a command becomes bytes — the
 * builders in this file return the line without it. That is why the tests can compare builder output
 * to the protocol notes verbatim and still see `\n\r` on the wire.
 *
 * Transport-injectable: anything with `write(bytes)`, `read(max, timeout)`, optional `drain()` and
 * `close()` — `SerialPortTransport` and `WebSerialTransport` from `firmata.js` both qualify, and so
 * does a mock in a test.
 */
export class UcmakeClient {
  constructor(transport, { timeout = 400 } = {}) {
    if (!transport || typeof transport.write !== 'function') {
      throw new TypeError('expected a transport with write()/read()');
    }
    this.t = transport;
    this.readTimeout = timeout;
    this.log = [];                       // every command sent, in order, for tests and debugging
  }

  /** The raw text of the last command sent (handy in a REPL). */
  get last() { return this.log[this.log.length - 1]; }

  /**
   * Send one line and **do not wait for a reply**. This is the correct shape for every actuator
   * command: the firmware executes them silently, so waiting would only make a working board look
   * dead (rule 1 at the top of this file). The terminator is appended here, once.
   */
  async send(line) {
    this.log.push(line);
    await this.t.write(Uint8Array.from([...line + TERMINATOR].map((c) => c.charCodeAt(0))));
    return line;
  }

  /**
   * Transport-level read: send, then return the raw decoded text with **no interpretation**.
   * Prefer `query()`. This exists so a caller that needs its own error handling (for example to
   * detect the ESP32 firmware's panic message, which arrives as ordinary text) can get at the
   * undecoded reply without decoding it first.
   */
  async raw(line, ms = this.readTimeout) {
    await this.t.drain?.();              // stale bytes from the previous command are not the answer
    await this.send(line);
    return asText(await this.t.read(256, ms));
  }

  /** Send a **read** command and decode its text reply ('' when the board stays silent). */
  async query(line, ms = this.readTimeout) {
    return checkReply(line, await this.raw(line, ms));
  }

  /** A read that answers with one analog level (0..1023), or `null` when nothing came back. */
  async queryNumber(line, ms = this.readTimeout) {
    return parseAnalog(await this.query(line, ms));
  }

  // ---- actuators (fire-and-forget; return the exact line sent) ----
  display(value) { return this.send(display(value)); }
  run(motor, speed) { return this.send(motorRun(motor, speed)); }
  stop(motor) { return this.send(motorStop(motor)); }
  move(lrfb, speed) { return this.send(driveMove(lrfb, speed)); }
  turn(left, right) { return this.send(driveTurn(left, right)); }
  stopAll() { return this.send(driveStop()); }
  setLed(index, on) { return this.send(ledSet(index, on)); }
  setServo(pin, angle) { return this.send(servo(pin, angle)); }

  // ---- sensors (reads; these DO answer) ----
  async readLineTracker(axis) { return this.queryNumber(lineTrackerRead(axis)); }
  async readLight() { return this.queryNumber(lightRead()); }
  async readTouch() { return parseTouch(await this.query(touchRead())); }
  async readButton(level) { return parseButton(await this.query(buttonRead(level))); }
  /** All four buttons: `[b1..b4]` of true/false/null. */
  async readButtons() { return parseButtons(await Promise.all(buttonsRead().map((c) => this.query(c)))); }
  async readUltrasonic(pin) { return this.queryNumber(ultrasonicRead(pin)); }
  async readSound() { return this.queryNumber(soundRead()); }

  // Aliases: the sensor names a lesson uses, and the vendor's own function names. Both spellings
  // exist because the probes and the lesson pages were written at different times; a caller should
  // not have to care which one it picked up.
  async lineTracker(axis) { return this.readLineTracker(axis); }
  async light() { return this.readLight(); }
  async touch() { return this.readTouch(); }
  async button(level) { return this.readButton(level); }
  async buttons() { return this.readButtons(); }
  async ultrasonic(pin) { return this.readUltrasonic(pin); }
  async sound() { return this.readSound(); }
  /** Light sensor via the vendor's `readLightSensor` block name. */
  async readLightSensor() { return this.readLight(); }

  async close() { await this.t.close?.(); }
}

/**
 * Why there is no `buzzer()` on this class.
 *
 * Tone is a **build-and-upload** feature: the vendor's `setBuzzer` block is `mechanism: "local"`,
 * carries no `commands` array anywhere in the catalogue, and its codegen is a library call
 * (`UCBuzzer buzzer(OnBoard_Buzzer); buzzer.tone(note, beat);`) compiled into the sketch. Fourteen
 * verbs were probed with `440 400` on the bench and none produced a tone.
 *
 * So the realtime path must say so out loud rather than pretend. The sketch path is real and
 * separate (`codegen.js` + `upload.mjs`) — it is not faked here either.
 */
export const BUZZER_UNSUPPORTED =
  'buzzer/tone has no realtime serial command on the UC-Mind300: the vendor block is ' +
  'mechanism "local" and its codegen is a library call (UCBuzzer buzzer(OnBoard_Buzzer); ' +
  'buzzer.tone(note, beat);) compiled into the sketch, and 14 verbs were probed with "440 400" ' +
  'with no tone. Tone is a BUILD-AND-UPLOAD feature — use the sketch path (codegen.js + upload.mjs).';

/**
 * The standard error for a sketch-only feature reached over the realtime path. Carries `reason`
 * so a lesson page can branch ("this needs a sketch upload") without matching on the message.
 */
export function unsupportedOnRealtime(what, reason = 'sketch-only') {
  const err = new Error(`${what} is not available over the realtime serial CLI (${reason})`);
  err.name = 'UnsupportedFeatureError';
  err.reason = reason;
  return err;
}
