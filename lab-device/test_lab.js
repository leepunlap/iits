/** Tests for the lab session, driven through a mock transport. */
import test from 'node:test';
import assert from 'node:assert/strict';

import { MockTransport, ANALOG_MESSAGE, DIGITAL_MESSAGE, SET_PIN_MODE, MODES } from './firmata.js';
import { connectBoard, CliSession } from './lab.js';

const connect = (opts = {}) => connectBoard({ transport: new MockTransport({ pins: 20, major: 2, minor: 5, name: 'uno' }), timeout: 20, ...opts });

test('connectBoard identifies the board and its level', async () => {
  const s = await connect();
  assert.equal(s.boardName, 'UC-Mind300');
  assert.equal(s.level, 'L3');
  assert.equal(s.usable, true);
  assert.deepEqual(s.info.firmata, [2, 5]);
  await s.close();
});

test('the session exposes capabilities the UI can gate on', async () => {
  const s = await connect();
  assert.deepEqual(s.capabilities, {
    board: 'UC-Mind300', motors: 2, buzzer: true, servo: true,
    digitalOut: true, analogIn: true, smartModules: false,
  });
  await s.close();
});

test('motor/buzzer/servo reach the wire through the session', async () => {
  const t = new MockTransport({ pins: 20 });
  const s = await connectBoard({ transport: t, timeout: 20 });
  t.written.length = 0;                       // drop the identify() traffic
  await s.motor(0, 100);
  const w = [...t.written];
  assert.deepEqual(w.slice(0, 3), [SET_PIN_MODE, 10, MODES.pwm]);
  assert.deepEqual(w.slice(6, 9), [DIGITAL_MESSAGE | 1, 0x02, 0x00]);
  assert.deepEqual(w.slice(9, 12), [ANALOG_MESSAGE | 10, 100, 0x00]);

  t.written.length = 0;
  await s.buzzer(true);
  assert.deepEqual([...t.written], [SET_PIN_MODE, 7, MODES.output, DIGITAL_MESSAGE | 0, 0x00, 0x01]);

  t.written.length = 0;
  await s.servo(9, 45);
  assert.deepEqual([...t.written], [SET_PIN_MODE, 9, MODES.servo, ANALOG_MESSAGE | 9, 45, 0x00]);
  await s.close();
});

test('sampleAnalog remembers the latest reading', async () => {
  const t = new MockTransport({ pins: 20 });
  const s = await connectBoard({ transport: t, timeout: 20 });
  s.f.analogMapping = { 14: 0 };
  t._answer([0xe0, 0x34, 0x02]);              // channel 0 -> pin 14, value 0x134
  const v = await s.sampleAnalog(14, 30);
  assert.equal(v, 0x134);
  assert.equal(s.analog[14], 0x134);
  await s.close();
});

test('a 40-pin board is treated as the L2 kit, and motors are refused', async () => {
  const s = await connectBoard({ transport: new MockTransport({ pins: 40, major: 2, minor: 7 }), timeout: 20 });
  assert.equal(s.boardName, 'UC-Mind100');
  assert.equal(s.level, 'L2');
  assert.equal(s.capabilities.motors, 0);
  await assert.rejects(() => s.motor(0, 100), /OneWire/);
  await s.close();
});

// A board that never answers Firmata but does answer the vendor CLI probe.
class CliMockTransport {
  constructor(reply = '180.00\r\n') { this.written = []; this.baudRate = 57600; this.reply = reply; }
  async write(bytes) { this.written.push(...bytes); }
  async read() {
    const text = new TextDecoder().decode(Uint8Array.from(this.written));
    if (this.reply && /A1 1 1 1/.test(text)) return new TextEncoder().encode(this.reply);
    return new Uint8Array();
  }
  async drain() {}
  async reopen({ baudRate } = {}) { this.baudRate = baudRate; this.written.length = 0; return this; }
  async close() { this.closed = true; }
}
const cliText = (t) => new TextDecoder().decode(Uint8Array.from(t.written));

test('attachTo falls back to the vendor CLI when Firmata does not answer', async () => {
  const t = new CliMockTransport();
  const s = await connectBoard({ transport: t, timeout: 20, cliProbeMs: 40, cliSettle: 0 });
  assert.ok(s instanceof CliSession);
  assert.equal(s.protocol, 'cli');
  assert.equal(s.boardName, 'UC-Mind100');
  assert.equal(s.level, 'L2');
  assert.equal(t.baudRate, 115200, 'the port must be reopened at the CLI baud');
  assert.deepEqual(s.capabilities.leds, 4);
  await s.close();
});

test('a CLI session sends the confirmed commands for each L2 block', async () => {
  const t = new CliMockTransport();
  const s = await connectBoard({ transport: t, timeout: 20, cliProbeMs: 40, cliSettle: 0 });
  t.written.length = 0;
  await s.display(8888);
  await s.led(1, true);
  await s.led(4, false);
  await s.motor(100);
  await s.motorStop();
  const sent = cliText(t);
  assert.match(sent, /A10 27 8888/);
  assert.match(sent, /A3 25 2 1 0/);
  assert.match(sent, /A3 25 2 4 1/);
  assert.match(sent, /A8 10 0 0 100 0/);
  assert.match(sent, /A8 10 3 0 0 0/);
  await s.close();
});

test('a CLI session reports clearly when nothing answers', async () => {
  const t = new CliMockTransport(null);          // silent board
  await assert.rejects(
    () => connectBoard({ transport: t, timeout: 20, cliProbeMs: 40, cliSettle: 0 }),
    /no known firmware answered/);
  await t.close();
});
