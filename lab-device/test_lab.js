/**
 * Tests for the lab session layer (`lab.js`), driven through mock transports.
 *
 * The shipped UC-Mind300 runs the vendor text CLI, so that is the path a lesson takes. A board
 * flashed with Firmata by hand is detected — and then **refused by name**, because the device layer
 * no longer contains a Firmata motor/sensor implementation to drive it with.
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import { MockTransport } from './firmata.js';
import { connectBoard, CliSession, FirmataUnsupportedError } from './lab.js';

// ---------------------------------------------------------------- Firmata (hand-flashed) path
test('a hand-flashed Firmata board is detected and refused by name', async () => {
  const t = new MockTransport({ pins: 20, major: 2, minor: 5, name: 'uno' });
  await assert.rejects(
    () => connectBoard({ transport: t, timeout: 20 }),
    (err) => {
      assert.ok(err instanceof FirmataUnsupportedError);
      assert.match(err.message, /answers Firmata 2\.5/);
      assert.match(err.message, /vendor UC-Mind CLI/);
      assert.deepEqual(err.info.firmata, [2, 5]);
      return true;
    },
  );
});

test('the Firmata refusal happens before the port is reopened at the CLI baud', async () => {
  const t = new MockTransport({ pins: 20, major: 2, minor: 5, name: 'uno' });
  let reopened = false;
  t.reopen = async () => { reopened = true; return t; };
  await assert.rejects(() => connectBoard({ transport: t, timeout: 20 }), FirmataUnsupportedError);
  assert.equal(reopened, false, 'there is no point probing for a CLI on a Firmata board');
});

// ---------------------------------------------------------------- vendor CLI path
/**
 * A board that answers the vendor CLI and nothing else.
 *
 * It answers the **read-only tracker probe** (`A9 16 2 2 1`) that `attachTo` now uses, and can also
 * be told to answer the legacy `A1 1 1 1` probe, so both detection routes are exercised. It records
 * everything written, so a test can assert the exact command strings.
 */
class CliMockTransport {
  constructor(reply = '512\r\n', { legacyOnly = false } = {}) {
    this.written = [];        // everything ever written — never cleared, so tests can assert on it
    this.since = [];          // bytes since the last answer — what the "board" is replying to
    this.baudRate = 57600;
    this.reply = reply;
    this.legacyOnly = legacyOnly;
    this.reads = 0;
  }
  async write(bytes) { this.written.push(...bytes); this.since.push(...bytes); }
  async read() {
    this.reads += 1;
    if (!this.reply) return new Uint8Array();                 // silent board
    const text = new TextDecoder().decode(Uint8Array.from(this.since));
    const isTracker = /A9 16 2 2 1/.test(text);
    const isLegacy = /A1 1 1 1/.test(text);
    if (isTracker && !this.legacyOnly) return this._answer('512\r\n');
    if (isLegacy) return this._answer(this.reply);
    return new Uint8Array();
  }
  /** Answer, and mark the outstanding command as consumed. */
  _answer(text) { this.since.length = 0; return new TextEncoder().encode(text); }
  async drain() { this.since.length = 0; }
  async reopen({ baudRate } = {}) { this.baudRate = baudRate; this.since.length = 0; return this; }
  async close() { this.closed = true; }
}
const cliText = (t) => new TextDecoder().decode(Uint8Array.from(t.written));
const connectCli = (t) => connectBoard({ transport: t, timeout: 20, cliProbeMs: 40, cliSettle: 0 });

test('attachTo falls back to the vendor CLI when Firmata does not answer', async () => {
  const t = new CliMockTransport();
  const s = await connectCli(t);
  assert.ok(s instanceof CliSession);
  assert.equal(s.protocol, 'cli');
  assert.equal(s.boardName, 'UC-Mind300');
  assert.equal(s.level, 'L3');
  assert.equal(t.baudRate, 115200, 'the port must be reopened at the CLI baud');
  await s.close();
});

test('detection probes with a READ-ONLY command, not the register write', async () => {
  const t = new CliMockTransport();
  const s = await connectCli(t);
  const sent = cliText(t);
  // `A1 1 1 1` is a read/WRITE register command and has left a board unresponsive until power-cycled.
  assert.doesNotMatch(sent, /A1 1 1 1/, 'the legacy register probe must not be the first thing sent');
  await s.close();
});

test('the legacy A1 probe still detects an older board', async () => {
  const t = new CliMockTransport('180.00\r\n', { legacyOnly: true });
  const s = await connectCli(t);
  assert.ok(s instanceof CliSession, 'a board that only answers A1 must still connect');
  assert.match(cliText(t), /A1 1 1 1/);
  await s.close();
});

test('a CLI session reports the full UC-Mind300 capability set', async () => {
  const t = new CliMockTransport();
  const s = await connectCli(t);
  const cap = s.capabilities;
  assert.equal(cap.board, 'UC-Mind300');
  assert.equal(cap.protocol, 'cli');
  assert.equal(cap.motors, 2);
  assert.equal(cap.differential, true);
  assert.equal(cap.display, true);
  assert.equal(cap.leds, 4);
  assert.equal(cap.buttons, 4);
  assert.equal(cap.lineTracker, 2);
  assert.equal(cap.light, true);
  assert.equal(cap.touch, true);
  assert.equal(cap.analogIn, true);
  assert.equal(cap.buzzer, false, 'tone is sketch-only — the UI must not offer it');
  await s.close();
});

test('a CLI session sends the verified commands for every lesson action', async () => {
  const t = new CliMockTransport();
  const s = await connectCli(t);

  s.cli.declareSensors({ 6: 'ultrasonic' });
  t.written.length = 0;

  await s.display(8888);
  await s.led(1, true);
  await s.led(4, false);
  await s.motor(1, 150);
  await s.motor(2, 120);
  await s.motorStop(1);
  await s.turn(150, -150);
  await s.stopAll();
  const sent = cliText(t);

  assert.match(sent, /A10 18 8888/, 'display is on port B = pin 18');
  assert.match(sent, /A3 19 2 1 0/, 'LED 1 on — the vendor sends HIGH as 0');
  assert.match(sent, /A3 19 2 4 1/, 'LED 4 off');
  assert.match(sent, /A8 1 0 0 150 0/, 'M1 by motor NUMBER');
  assert.match(sent, /A8 2 0 0 120 0/, 'M2 by motor NUMBER');
  assert.match(sent, /A8 1 0 0 0 0/, 'stop M1');
  assert.match(sent, /A8 10 2 0 150 -150/, 'differential turn');
  assert.match(sent, /A8 10 3 0 0 0/, 'stop all');
  assert.doesNotMatch(sent, /A17/, 'A17 is not a verb on this board');
  await s.close();
});

test('the one-argument motor(speed) shorthand drives M1 — the lab page relies on it', async () => {
  const t = new CliMockTransport();
  const s = await connectCli(t);
  t.written.length = 0;
  // lab.html's slider calls session.motor(120); reading 120 as a motor index would throw.
  await s.motor(120);
  assert.match(cliText(t), /A8 1 0 0 120 0/);

  t.written.length = 0;
  await s.motorStop();                       // and the page's stop sends the stop-all form
  assert.match(cliText(t), /A8 10 3 0 0 0/);
  await s.close();
});

test('a CLI session reads the sensors with the verified commands', async () => {
  const t = new CliMockTransport();
  const s = await connectCli(t);

  // Detection is done; from here the mock answers reads from a queue, one reply per command.
  t.since.length = 0;
  const replies = ['500\r\n', '0\r\n', '1\r\n'];
  t.read = async () => {
    const next = replies.shift();
    return next ? new TextEncoder().encode(next) : new Uint8Array();
  };
  t.written.length = 0;

  assert.equal(await s.lineTracker(1), 500);
  assert.equal(await s.touch(), false);
  assert.equal(await s.light(), 1, 'the light sensor is analog 0..1023');
  assert.match(cliText(t), /A9 16 2 2 1/);
  assert.match(cliText(t), /A20 15 0/);
  assert.match(cliText(t), /A16 21 0/);
  await s.close();
});

test('buttons() reads all four and returns booleans', async () => {
  const t = new CliMockTransport();
  const s = await connectCli(t);
  t.since.length = 0;
  const replies = ['1\r\n', '0\r\n', '0\r\n', '1\r\n'];
  t.read = async () => {
    const next = replies.shift();
    return next ? new TextEncoder().encode(next) : new Uint8Array();
  };
  t.written.length = 0;
  assert.deepEqual(await s.buttons(), [true, false, false, true]);
  assert.match(cliText(t), /A3 19 1 1/);
  await s.close();
});

test('a CLI session refuses tone with a clear error rather than pretending', async () => {
  const t = new CliMockTransport();
  const s = await connectCli(t);
  t.written.length = 0;
  await assert.rejects(() => s.buzzer(), (err) => {
    assert.equal(err.name, 'UnsupportedFeatureError');
    assert.equal(err.reason, 'sketch-only');
    return true;
  });
  assert.equal(cliText(t), '', 'nothing may be sent for a feature with no command');
  await s.close();
});

test('declareSensors still gates the optional ultrasonic module', async () => {
  const t = new CliMockTransport();
  const s = await connectCli(t);
  await assert.rejects(() => s.readSensor(6), /not a declared ultrasonic/);
  s.declareSensors({ 6: 'ultrasonic' });
  t.read = async () => new TextEncoder().encode('42\r\n');
  assert.equal(await s.readSensor(6), 42);
  await s.close();
});

test('the CLI session exposes the lesson-level board, sharing one command log', async () => {
  const t = new CliMockTransport();
  const s = await connectCli(t);
  t.written.length = 0;
  await s.board.display.show(1234);
  await s.board.motor.run(1, 100);
  assert.deepEqual(s.cli.log.slice(-2), ['A10 18 1234', 'A8 1 0 0 100 0']);
  assert.equal(s.board.client, s.cli.c, 'one client, one log');
  await s.close();
});

test('a CLI session reports clearly when nothing answers', async () => {
  const t = new CliMockTransport(null);          // silent board
  await assert.rejects(() => connectCli(t), /no known firmware answered/);
  await t.close();
});
