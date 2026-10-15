/**
 * Tests for the vendor CLI client (`ucmake_cli.js`).
 *
 * The stale version of this file sent `A17 <pin> …` for the UC-Mind300 and a `2 2`-less tracker
 * read — both wrong. These tests pin the bench-verified spellings so they cannot drift back, and
 * they pin the two behaviours that make a working board look broken when violated: writes must not
 * wait, and a pin must never reach the motor field.
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import { UCMakeCli, PROFILES, TERMINATOR, CLI_BAUD, BoardResetError, profileFor } from './ucmake_cli.js';
import { UcmakeCommandError } from './ucmind300.js';

/** Records writes and replays queued replies (one per read). */
class MockCli {
  constructor(replies = []) {
    this.written = [];
    this.replies = [...replies];
    this.reads = 0;
    this.drains = 0;
  }
  async write(bytes) { this.written.push(...bytes); }
  async read() {
    this.reads += 1;
    const next = this.replies.shift();
    return next == null ? new Uint8Array() : new TextEncoder().encode(next);
  }
  async drain() { this.drains += 1; }
  async close() { this.closed = true; }
}

const textOf = (t) => new TextDecoder().decode(Uint8Array.from(t.written));
const linesOf = (t) => textOf(t).split('\n\r').filter(Boolean);
const cli = (board = 'UC-Mind300', t = new MockCli()) => [t, new UCMakeCli(t, PROFILES[board])];

test('terminator and baud match what UCMake uses', () => {
  assert.equal(TERMINATOR, '\n\r');
  assert.equal(CLI_BAUD, 115200);
});

test('profileFor accepts a name or a profile, and rejects an unknown board', () => {
  assert.equal(profileFor('UC-Mind300').level, 'L3');
  assert.equal(profileFor(PROFILES['UC-Mind100']).name, 'UC-Mind100');
  assert.equal(profileFor(undefined).name, 'UC-Mind300', 'the verified board is the default');
  assert.throws(() => profileFor('UC-Mind500'), /unknown board/);
});

test('the UC-Mind300 is flagged verified; the ESP32 kit is explicitly not', () => {
  assert.equal(PROFILES['UC-Mind300'].verified, true);
  assert.equal(PROFILES['UC-Mind100'].verified, false);
});

// ---------------------------------------------------------------- motors
test('L3 motors use A8 with a MOTOR NUMBER — never A17, never a pin', async () => {
  const [t, c] = cli('UC-Mind300');
  await c.motor(1, 150);
  await c.motor(2, 120);
  assert.deepEqual(linesOf(t), ['A8 1 0 0 150 0', 'A8 2 0 0 120 0']);
  assert.doesNotMatch(textOf(t), /A17/, 'A17 is not a verb on this image');
  assert.doesNotMatch(textOf(t), /A8 1[05] /, 'the pin-numbered form must not come back');
});

test('motor(speed) is the one-motor shorthand for M1', async () => {
  const [t, c] = cli('UC-Mind300');
  await c.motor(100);
  assert.deepEqual(linesOf(t), ['A8 1 0 0 100 0']);
});

test('a pin can never be sent as a motor', async () => {
  const [t, c] = cli('UC-Mind300');
  // 5, 6, 9, 11 are the pins the stale implementation wrote to; none is a motor number.
  for (const pin of [5, 6, 9, 11, 0, 3]) {
    await assert.rejects(() => c.motor(pin, 150), /which is a pin, not a motor/, `pin ${pin}`);
  }
  assert.equal(textOf(t), '', 'nothing may reach the board');
});

test('stop: one motor by number, or the vendor stop-all with no argument', async () => {
  const [t, c] = cli('UC-Mind300');
  await c.motorStop(1);
  await c.motorStop(2);
  await c.motorStop();
  await c.stopAll();
  assert.deepEqual(linesOf(t), ['A8 1 0 0 0 0', 'A8 2 0 0 0 0', 'A8 10 3 0 0 0', 'A8 10 3 0 0 0']);
});

test('differential turn and move are distinct commands', async () => {
  const [t, c] = cli('UC-Mind300');
  await c.driveTurn(150, 150);
  await c.driveMove(1, 150);
  assert.deepEqual(linesOf(t), ['A8 10 2 0 150 150', 'A8 10 1 1 150 0']);
});

// ---------------------------------------------------------------- display
test('L3 display is A10 on port B = pin 18 (not 27)', async () => {
  const [t, c] = cli('UC-Mind300');
  await c.display(1234);
  assert.deepEqual(linesOf(t), ['A10 18 1234']);
  assert.equal(c.profile.displayPin, 18);
});

test('the ESP32 kit keeps its own display pin', async () => {
  const [t, c] = cli('UC-Mind100');
  await c.display(8888);
  assert.deepEqual(linesOf(t), ['A10 27 8888']);
});

// ---------------------------------------------------------------- buttons / LEDs
test('the LED level is inverted: on -> 0', async () => {
  const [t, c] = cli('UC-Mind300');
  await c.setLed(1, true);
  await c.setLed(1, false);
  assert.deepEqual(linesOf(t), ['A3 19 2 1 0', 'A3 19 2 1 1']);
});

test('ledButton accepts both the lesson and the vendor argument order', async () => {
  const [t, c] = cli('UC-Mind300');
  await c.ledButton(1, true);              // index, on
  await c.ledButton(19, 2, false);         // pin, index, on
  await c.ledButton(25, 3, true);          // an explicit pin wins over the profile's
  assert.deepEqual(linesOf(t), ['A3 19 2 1 0', 'A3 19 2 2 1', 'A3 25 2 3 0']);
});

test('readButtons reads all four on pin 19 and decodes to booleans', async () => {
  const [t, c] = cli('UC-Mind300', new MockCli(['1\r\n', '0\r\n', '0\r\n', '1\r\n']));
  assert.deepEqual(await c.readButtons(), [true, false, false, true]);
  assert.deepEqual(linesOf(t), ['A3 19 1 1', 'A3 19 1 2', 'A3 19 1 3', 'A3 19 1 4']);
});

test('readButton/readButtons alias the vendor name and the lesson name', async () => {
  const [t, c] = cli('UC-Mind300', new MockCli(['1\r\n', '0\r\n', '1\r\n', '0\r\n', '1\r\n', '0\r\n']));
  assert.equal(await c.readButton(2), true);
  assert.equal(await c.readLedButtonDigital(19, 2), false);
  assert.deepEqual(await c.buttons(), [true, false, true, false]);
  assert.ok(t.written.length > 0);
});

// ---------------------------------------------------------------- sensors
test('the line tracker uses A9 16 2 2 <axis>', async () => {
  const [t, c] = cli('UC-Mind300', new MockCli(['978\r\n', '88\r\n']));
  assert.equal(await c.readLineTracker(1), 978);
  assert.equal(await c.read2LineFollower(16, 2), 88);
  assert.deepEqual(linesOf(t), ['A9 16 2 2 1', 'A9 16 2 2 2']);
  assert.doesNotMatch(textOf(t), /A9 16 1 /, 'the "2 2" field is required — without it it is silent');
});

test('the built-in light sensor is A16 21 0', async () => {
  const [t, c] = cli('UC-Mind300', new MockCli(['988\r\n', '988\r\n']));
  assert.equal(await c.readLight(), 988);
  assert.equal(await c.light(), 988);
  assert.deepEqual([...new Set(linesOf(t))], ['A16 21 0']);
});

test('touch is A20 15 0 and BINARY', async () => {
  const [t, c] = cli('UC-Mind300', new MockCli(['0\r\n', '1\r\n']));
  assert.equal(await c.readTouch(), false);
  assert.equal(await c.touch(), true);
  assert.deepEqual(linesOf(t), ['A20 15 0', 'A20 15 0']);
});

test('the ultrasonic module still needs a declared pin, and uses A16 <pin> 4', async () => {
  const [t, c] = cli('UC-Mind300', new MockCli(['42\r\n']));
  await assert.rejects(() => c.readUltrasonic(6), /not a declared ultrasonic/);
  assert.equal(t.written.length, 0, 'nothing may reach the board');
  c.declareSensors({ 6: 'ultrasonic' });
  assert.equal(await c.readUltrasonic(6), 42);
  assert.deepEqual(linesOf(t), ['A16 6 4']);
});

test('the sound sensor is exposed but never advertised as verified', async () => {
  const [t, c] = cli('UC-Mind300', new MockCli(['982\r\n']));
  assert.equal(await c.readSound(), 982);
  assert.deepEqual(linesOf(t), ['A15 17 0']);
});

// ---------------------------------------------------------------- protocol behaviour
test('writes never wait for a reply — silence is the success path', async () => {
  const [t, c] = cli('UC-Mind300');
  await c.motor(1, 150);
  await c.display(1234);
  await c.setLed(1, true);
  assert.equal(t.reads, 0, 'an actuator command must not read');
  assert.equal(t.drains, 0, 'and must not drain either');
});

test('reads drain stale input and report a firmware error as an error', async () => {
  const [, c] = cli('UC-Mind300', new MockCli(['ERROR 参数不足\r\n']));
  await assert.rejects(() => c.readLight(), UcmakeCommandError);
});

test('a panic reply is reported as a board reset, not as a reading', async () => {
  const panic = "Guru Meditation Error: Core  1 panic'ed (IllegalInstruction). Exception was unhandled.\r\n";
  const [, c] = cli('UC-Mind300', new MockCli([panic]));
  await assert.rejects(() => c.readLight(), (err) => {
    assert.ok(err instanceof BoardResetError);
    assert.match(err.message, /panicked and rebooted/);
    return true;
  });
});

test('tone is refused explicitly — there is no realtime buzzer command', async () => {
  const [t, c] = cli('UC-Mind300');
  await assert.rejects(() => c.tone(), (err) => {
    assert.equal(err.name, 'UnsupportedFeatureError');
    assert.equal(err.reason, 'sketch-only');
    return true;
  });
  await assert.rejects(() => c.buzzer(), /not available over the realtime serial CLI/);
  assert.equal(textOf(t), '', 'no bytes may be sent');
});

test('BLE and electromagnet exist only on the ESP32 kit', async () => {
  const [t, c] = cli('UC-Mind100');
  await c.ble(5, true);
  await c.electromagnet(5, false);
  assert.deepEqual(linesOf(t), ['A7 5 1', 'A12 5 0']);

  const [, l3] = cli('UC-Mind300');
  await assert.rejects(() => l3.ble(5, true), /not available over the realtime serial CLI/);
  await assert.rejects(() => l3.electromagnet(5, true), /not available/);
});

test('servo uses A6', async () => {
  const [t, c] = cli('UC-Mind300');
  await c.servo(9, 90);
  await c.servo360(9, 45);
  assert.deepEqual(linesOf(t), ['A6 9 90', 'A6 9 45']);
});

test('every command is recorded for debugging', async () => {
  const [, c] = cli('UC-Mind300');
  await c.motor(1, 50);
  await c.display(1234);
  assert.deepEqual(c.log, ['A8 1 0 0 50 0', 'A10 18 1234']);
  assert.equal(c.last, 'A10 18 1234');
});
