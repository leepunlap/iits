/**
 * Wonder Lab ↔ hardware session.
 *
 * Transport-injectable so the whole session can be tested without a browser:
 *   - in the lab page, omit `transport` and the session asks for a Web Serial port;
 *   - in tests, pass a MockTransport.
 *
 * The lab UI only talks to this object; everything below it (Firmata framing, board profiles,
 * capability gating) is already hardware-verified — see ../L23-PROTOCOL.md.
 */

import { Firmata, WebSerialTransport } from './firmata.js';
import { UCMindBoard, profileFor } from './board.js';
import { UCMakeCli, PROFILES } from './ucmake_cli.js';

export const FIRMATA_BAUD = 57600;
export const CLI_BAUD = 115200;

export class LabSession {
  constructor(firmata, board, info) {
    this.f = firmata;
    this.board = board;
    this.info = info;
    this.analog = {};
  }

  get boardName() { return this.board.profile.name; }
  get level() { return this.info.level; }
  get capabilities() { return this.board.capabilities(); }

  /** True when the lab may show hardware controls at all. */
  get usable() { return this.info.firmata !== null; }

  async motor(index, speed) { return this.board.motor(index, speed); }
  async motorStop(index) { return this.board.motorStop(index); }
  async buzzer(on) { return this.board.buzzer(on); }
  async servo(pin, angle) { return this.board.servo(pin, angle); }
  async digitalOut(pin, on) { return this.board.digitalOut(pin, on); }

  /** Sample one analog pin and remember the latest reading. */
  async sampleAnalog(pin, ms = 300) {
    const values = await this.board.readAnalog(pin, ms);
    const latest = values.length ? values[values.length - 1] : null;
    this.analog[pin] = latest;
    return latest;
  }

  async close() { await this.f.close(); }
}

/**
 * A UC-Mind board running the vendor CLI (what UCMake flashes in realtime mode).
 * Same surface as LabSession where it matters, so the UI does not branch on protocol.
 */
export class CliSession {
  constructor(cli) {
    this.cli = cli;
    this.protocol = 'cli';
    this.profile = cli.profile;
    this.sensors = {};
  }

  get boardName() { return this.profile.name; }
  get level() { return this.profile.level; }
  get info() { return { protocol: 'cli', firmware: this.profile.deviceId, level: this.profile.level }; }
  get usable() { return true; }

  get capabilities() {
    return {
      board: this.profile.name, protocol: 'cli',
      motors: this.profile.motorPins.length, display: true,
      leds: 4, buttons: 4, sensors: true,
      buzzer: false, servo: true, digitalOut: false, smartModules: true,
    };
  }

  /** Declare what is physically plugged in — the firmware panics on an unconfigured pin. */
  declareSensors(map) {
    this.cli.declareSensors(map);
    Object.assign(this.sensors, map);
    return this;
  }

  async motor(speed) { return this.cli.motor(this.profile.motorPins[0], speed); }
  async motorStop() { return this.cli.motorStop(); }
  async display(value) { return this.cli.display(value); }
  async led(index, on) { return this.cli.ledButton(this.profile.ledPin, index, on); }
  async buttons() { return this.cli.readButtons(this.profile.ledPin); }
  /** Read the ultrasonic module. The caller must have declared the pin — see declareSensors. */
  async readSensor(pin) { return this.cli.readUltrasonic(pin); }
  async close() { await this.cli.close(); }
}

/**
 * Work out which firmware is on the board and return the matching session.
 *
 * UCMake leaves one of two things on a UC-Mind board: the vendor **CLI** (what realtime mode
 * flashes) or a **Firmata** build. They use different baud rates, and Web Serial cannot change
 * baud in place — so we try Firmata at 57600, then reopen at 115200 and probe the CLI.
 */
export async function attachTo(transport, opts = {}) {
  const firmata = new Firmata(transport, { timeout: opts.timeout ?? 800 });
  let info = null;
  try { info = await firmata.identify(); } catch { info = null; }
  if (info && Array.isArray(info.firmata)) {
    const board = new UCMindBoard(firmata, profileFor(info));
    return new LabSession(firmata, board, { ...info, protocol: 'firmata' });
  }

  if (typeof transport.reopen === 'function') {
    await transport.reopen({ baudRate: opts.cliBaudRate ?? CLI_BAUD, settle: opts.cliSettle ?? 1200 });
  }
  const cli = new UCMakeCli(transport, opts.cliProfile ?? PROFILES['UC-Mind100']);
  let reply = '';
  try { reply = await cli.query(['A1', 1, 1, 1], opts.cliProbeMs ?? 1200); } catch { reply = ''; }
  if (/^[-+]?\d/.test(reply)) return new CliSession(cli);

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
