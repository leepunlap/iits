/** Tests for the vendor CLI client. Every expected string is copied from vendors.js. */
import test from 'node:test';
import assert from 'node:assert/strict';

import { UCMakeCli, PROFILES, TERMINATOR, CLI_BAUD, BoardResetError } from './ucmake_cli.js';

class MockCli {
  constructor() { this.written = []; this.queue = []; this.reply = null; }
  // the board answers *after* the command arrives, so queue the reply on write
  async write(bytes) {
    this.written.push(...bytes);
    // `reply` may be a single string or a queue of them (one per command)
    const next = Array.isArray(this.reply) ? this.reply.shift() : this.reply;
    if (next != null) this.queue.push(...new TextEncoder().encode(next));
  }
  async read() { return Uint8Array.from(this.queue.splice(0)); }
  async drain() { this.queue.length = 0; }      // discards stale input before a command
  async close() { this.closed = true; }
}
const textOf = (t) => new TextDecoder().decode(Uint8Array.from(t.written));
const cli = (board = 'UC-Mind100', t = new MockCli()) => [t, new UCMakeCli(t, PROFILES[board])];

test('terminator and baud match what UCMake uses', () => {
  assert.equal(TERMINATOR, '\n\r');
  assert.equal(CLI_BAUD, 115200);
});

test('ESP32-min motor commands are byte-for-byte UCMake\'s', async () => {
  const [t, c] = cli('UC-Mind100');
  await c.motor(10, 100);
  assert.equal(textOf(t), 'A8 10 0 0 100 0\n\r');
  t.written.length = 0;
  await c.motor(10, -80);
  assert.equal(textOf(t), 'A8 10 0 0 -80 0\n\r');
  t.written.length = 0;
  await c.motorStop();
  assert.equal(textOf(t), 'A8 10 3 0 0 0\n\r');
});

test('UC-Mind300 motors use function A17', async () => {
  const [t, c] = cli('UC-Mind300');
  await c.motor(1, 120);
  assert.equal(textOf(t), 'A17 1 0 0 120 0\n\r');
  t.written.length = 0;
  await c.motorStop();
  assert.equal(textOf(t), 'A17 0 3 0 0 0\n\r');
});

test('display sends a plain decimal value (verified: 8888 shows 8888)', async () => {
  const [t, c] = cli('UC-Mind100');
  await c.display(8888);
  assert.equal(textOf(t), 'A10 27 8888\n\r');
  t.written.length = 0;
  await c.display(500, 27);
  assert.equal(textOf(t), 'A10 27 500\n\r');
});

test('4-LED button module: LEDs are addressed by port pin, index and level', async () => {
  const [t, c] = cli('UC-Mind100');
  // port A2 = pin 25 on the UC-Mind100; HIGH is sent as 0 (the vendor inverts the level)
  await c.ledButton(25, 1, true);
  assert.equal(textOf(t), 'A3 25 2 1 0\n\r');
  t.written.length = 0;
  await c.ledButton(25, 4, false);
  assert.equal(textOf(t), 'A3 25 2 4 1\n\r');
});

test('readButtons returns the four button states (confirmed: held button reads 1)', async () => {
  const [t, c] = cli('UC-Mind100');
  c.declareSensors({ 25: 'ledButton' });
  t.reply = ['1\r\n', '0\r\n', '0\r\n', '0\r\n'];
  assert.deepEqual(await c.readButtons(25), [true, false, false, false]);
  assert.deepEqual(c.log.slice(-4), ['A3 25 1 1', 'A3 25 1 2', 'A3 25 1 3', 'A3 25 1 4']);
});

test('servo / BLE / electromagnet follow the vendor functions', async () => {
  const [t, c] = cli('UC-Mind100');
  await c.servo360(1, 90);
  assert.equal(textOf(t), 'A6 1 90\n\r');
  t.written.length = 0;
  await c.ble(5, true);
  assert.equal(textOf(t), 'A7 5 1\n\r');
  t.written.length = 0;
  await c.electromagnet(5, false);
  assert.equal(textOf(t), 'A12 5 0\n\r');

  const [, l3] = cli('UC-Mind300');
  await assert.rejects(() => l3.ble(5, true), /no BLE/);
  await assert.rejects(() => l3.electromagnet(5, true), /no electromagnet/);
});

test('reading an undeclared pin is refused (it panics the firmware)', async () => {
  const [t, c] = cli('UC-Mind100');
  await assert.rejects(() => c.readUltrasonic(6), /not a declared ultrasonic/);
  assert.equal(t.written.length, 0, 'nothing may reach the board');
  c.declareSensors({ 6: 'ultrasonic' });
  t.reply = '42\r\n';
  assert.equal(await c.readUltrasonic(6), '42');
  await assert.rejects(() => c.readLineFollower(6, 1), /not a declared lineFollower/);
});

test('a panic reply is reported as a board reset, not as a reading', async () => {
  const [t, c] = cli('UC-Mind100');
  c.declareSensors({ 6: 'ultrasonic' });
  t.reply = "Guru Meditation Error: Core  1 panic'ed (IllegalInstruction). Exception was unhandled.\r\n";
  await assert.rejects(() => c.readUltrasonic(6), BoardResetError);
  await assert.rejects(() => c.readUltrasonic(6), /panicked and rebooted/);
});

test('reads use the right function per board and decode the text reply', async () => {
  const [t, c] = cli('UC-Mind100');
  c.declareSensors({ 6: 'ultrasonic', 9: 'lineFollower', 4: 'color' });
  t.reply = '180.00\r\n';
  const v = await c.readUltrasonic(6);
  assert.equal(textOf(t), 'A5 6 4\n\r');
  assert.equal(v, '180.00');

  t.written.length = 0;
  await c.readLineFollower(9, 1);
  assert.equal(textOf(t), 'A9 9 1 1\n\r');

  t.written.length = 0;
  await c.readColor(4, 2);
  assert.equal(textOf(t), 'A4 4 3 2\n\r');
});

test('L3 sensors use the AVR fixed channels', async () => {
  const [t, c] = cli('UC-Mind300');
  c.declareSensors({ 6: 'ultrasonic' });
  await c.readLight();
  assert.equal(textOf(t), 'A16 21 0\n\r');
  t.written.length = 0;
  await c.readSound();
  assert.equal(textOf(t), 'A15 17 0\n\r');
  t.written.length = 0;
  await c.readUltrasonic(6);
  assert.equal(textOf(t), 'A16 6 4\n\r');
});

test('every command is recorded for debugging', async () => {
  const [, c] = cli('UC-Mind100');
  await c.motor(10, 50);
  await c.display(1234);
  assert.deepEqual(c.log, ['A8 10 0 0 50 0', 'A10 27 1234']);
});
