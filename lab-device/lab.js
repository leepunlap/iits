/**
 * Wonder Lab ↔ hardware session.
 *
 * Transport-injectable so the whole session can be tested without a browser:
 *   - in the lab page, omit `transport` and the session asks for a Web Serial port;
 *   - in tests, pass a MockTransport.
 *
 * The lab UI only talks to this object.
 *
 * ⚠️ **The UC-Mind300 does not run Firmata.** It runs the vendor's `A`-command text CLI at 115200
 * (bench-verified 2026-10-14). Firmata detection is kept only as a fallback for a board a teacher
 * has flashed by hand, and the CLI session now carries the full lesson API — display, both motors,
 * differential turn, line tracker, buttons, LEDs, light and touch — via `board.js`.
 *
 * `lineTracker` / `light` / `touch` are the three sensor reads that actually answer, and all three
 * live on the CLI path. There is no analog-reporting mode to call.
 */

import { Firmata, WebSerialTransport } from './firmata.js';
import { UCMindBoard } from './board.js';
import { UCMakeCli, PROFILES, CLI_BAUD, PINS } from './ucmake_cli.js';
import { checkReply } from './ucmind300.js';

export const FIRMATA_BAUD = 57600;
export { CLI_BAUD };

/**
 * Thrown when a board answers Firmata.
 *
 * The Wonder Lab's device layer is the vendor CLI. A board that answers Firmata has been flashed
 * with a non-vendor build by hand, and the lab has no motor/sensor API for it any more — saying so
 * is better than half-working. Its transports (`firmata.js`) are still used by the CLI path.
 */
export class FirmataUnsupportedError extends Error {
  constructor(info) {
    super(
      `the board answers Firmata ${(info?.firmata ?? []).join('.')}, but the Wonder Lab device ` +
      'layer speaks the vendor UC-Mind CLI — reflash the vendor realtime firmware (115200) to use ' +
      'the lab, or drive raw Firmata yourself with firmata.js',
    );
    this.name = 'FirmataUnsupportedError';
    this.info = info;
  }
}

/**
 * A UC-Mind board running the vendor CLI — what the shipped firmware actually is.
 *
 * Same surface as the old `LabSession` where the UI touches it, so `lab.html` does not branch, plus
 * the full lesson API from `board.js`. Every actuator call is fire-and-forget: the firmware is
 * silent on success, so nothing waits for an acknowledgement.
 */
export class CliSession {
  constructor(cli) {
    this.cli = cli;
    this.protocol = 'cli';
    this.profile = cli.profile;
    this.sensors = {};
    this.analog = {};                          // last reading per pin, as the old session kept

    // The lesson-level board: display / motor / drive / sensor / buttons / leds.
    // Shares the one client (and therefore the one command log) with this session.
    this.board = new UCMindBoard(cli.c, cli.profile);
  }

  // ---------------------------------------------------------------- identity
  get boardName() { return this.profile.name; }
  get level() { return this.profile.level; }
  get info() {
    return {
      protocol: 'cli',
      firmware: this.profile.deviceId,
      level: this.profile.level,
      verified: this.profile.verified === true,
      baudRate: CLI_BAUD,
    };
  }

  get usable() { return true; }

  /** What the board can do — the lab gates every control on this, not on the protocol name. */
  get capabilities() { return this.board.capabilities(); }

  // ---------------------------------------------------------------- actuators
  async display(value) { return this.board.display.show(value); }
  async led(index, on) { return this.board.leds.set(index, on); }

  /**
   * `motor(index, speed)` drives M1/M2 by number; `motor(speed)` is the one-motor shorthand the lab
   * page has always used, and drives M1.
   *
   * Both shapes are needed: the page's slider calls `session.motor(120)`, and a lesson written
   * against `board.js` calls `session.motor(1, 120)`. Reading the single argument as an index — the
   * obvious interpretation — would reject a speed of 120 as "no such motor" and break the page.
   */
  async motor(indexOrSpeed, speed) {
    return speed === undefined
      ? this.board.motor.run(1, indexOrSpeed)
      : this.board.motor.run(indexOrSpeed, speed);
  }

  /** Stop M1/M2 by number; with no argument — the page's form — stop both. */
  async motorStop(index) {
    return index === undefined ? this.board.motor.stopAll() : this.board.motor.stop(index);
  }

  /** Differential turn: left wheel speed / right wheel speed. */
  async turn(left, right) { return this.board.drive.turn(left, right); }
  async stopAll() { return this.board.drive.stop(); }
  async servo(pin, angle) { return this.board.servo(pin, angle); }

  /** Tone is sketch-only; this throws a clear `UnsupportedFeatureError` on the realtime path. */
  async buzzer() { return this.board.buzzer(); }

  // ---------------------------------------------------------------- sensors
  async buttons() { return this.board.buttons.readAll(); }
  async lineTracker(axis = 1) { return this.board.sensor.lineTracker(axis); }
  async light() { return this.board.sensor.light(); }
  async touch() { return this.board.sensor.touch(); }

  /**
   * The lab page's "read once" button, kept from the old Firmata session.
   *
   * There is no analog-reporting mode over the CLI, so a pin cannot be sampled generically. The
   * board does have exactly one built-in analog input — the light sensor — so a request for that pin
   * is answered, and any other pin is refused by name rather than returning a number that came from
   * somewhere else.
   */
  async sampleAnalog(pin = this.board.profile.analogPin, _ms) {
    const lightPin = this.board.profile.analogPin ?? PINS.light;
    if (pin !== undefined && pin !== null && Number(pin) !== Number(lightPin)) {
      throw new Error(
        `pin ${pin} cannot be sampled: the vendor CLI has no analog-reporting mode. ` +
        `The built-in light sensor is pin ${lightPin} (use sensor.light())`,
      );
    }
    const value = await this.light();
    this.analog[lightPin] = value;
    return value;
  }

  /** Optional ultrasonic module — the caller must declare the pin first. */
  declareSensors(map) {
    this.cli.declareSensors(map);
    Object.assign(this.sensors, map);
    this.board.declareSensors(map);
    return this;
  }

  async readSensor(pin) { return this.board.sensor.ultrasonic(pin); }

  async close() { return this.cli.close(); }
}

/**
 * Work out which firmware is on the board and return the matching session.
 *
 * The shipped UC-Mind firmware is the vendor **CLI** at 115200. Firmata is probed first only so the
 * failure can be named: a board someone flashed by hand answers at 57600, and Web Serial cannot
 * change baud in place, so we either reopen at 115200 for the CLI or report the Firmata build.
 */
export async function attachTo(transport, opts = {}) {
  const firmata = new Firmata(transport, { timeout: opts.timeout ?? 800 });
  let info = null;
  try { info = await firmata.identify(); } catch { info = null; }
  if (info && Array.isArray(info.firmata)) throw new FirmataUnsupportedError(info);

  if (typeof transport.reopen === 'function') {
    await transport.reopen({ baudRate: opts.cliBaudRate ?? CLI_BAUD, settle: opts.cliSettle ?? 1200 });
  }
  const cli = new UCMakeCli(transport, opts.cliProfile ?? PROFILES['UC-Mind300']);

  // Probe with a READ-ONLY command.
  //
  // ⚠️ The old probe was `A1 1 1 1`, and the protocol notes warn that `A1 <port> <reg> <value>` is a
  // read/WRITE register command: on at least one occasion it left the board unresponsive until a
  // power cycle. The line tracker read is side-effect free and answers 0..1023, so detection no
  // longer touches a register. The legacy `A1` probe is kept as a fallback only, for a board whose
  // tracker port is unavailable (and because older test transports answer it).
  const probes = [
    { cmd: ['A9', 16, 2, 2, 1], ok: (r) => /^\d+$/.test(r) },
    { cmd: ['A1', 1, 1, 1], ok: (r) => /^[-+]?\d/.test(r) },
  ];
  for (const probe of probes) {
    let reply = '';
    try { reply = await cli.query(probe.cmd, opts.cliProbeMs ?? 1200); } catch { reply = ''; }
    if (probe.ok(reply)) return new CliSession(cli);
  }

  throw new Error('no known firmware answered (tried Firmata @57600 and the vendor CLI @115200)');
}

/**
 * Connect to a UC-Mind board and return a session.
 * @param {{transport?: object, baudRate?: number}} opts pass `transport` to drive a fake board.
 */
export async function connectBoard(opts = {}) {
  const transport = opts.transport
    ?? await WebSerialTransport.request({ baudRate: opts.baudRate ?? FIRMATA_BAUD,
                                          allPorts: opts.allPorts === true });
  return attachTo(transport, opts);
}
