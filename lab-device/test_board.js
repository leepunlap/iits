/**
 * Tests for the lesson-level board API (`board.js`) — the shape a lesson sees.
 *
 * No hardware: a fake transport records the bytes and replays replies. What is asserted here is
 * that each lesson action becomes **the verified command**, and that the two traps the protocol
 * notes call out (waiting for an ack, and passing a pin as a motor) cannot happen through this API.
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  ANALOG_MAX, LED_COUNT, MOTOR, PINS, PROFILES, UCMindBoard, profileFor,
} from './board.js';

/** A transport that records writes and replays queued replies (one per read). */
class FakeTransport {
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
/** Everything sent, split into one entry per terminated command. */
const linesOf = (t) => textOf(t).split('\n\r').filter(Boolean);
const mk = (replies) => {
  const t = new FakeTransport(replies);
  return { t, b: new UCMindBoard(t, PROFILES['UC-Mind300']) };
};

test('profileFor accepts a board name or an info object', () => {
  assert.equal(profileFor('UC-Mind300').name, 'UC-Mind300');
  assert.equal(profileFor({ pins: 20 }).name, 'UC-Mind300');
  assert.equal(profileFor({ pins: 40 }).name, 'UC-Mind100');
  assert.throws(() => profileFor('UC-Mind900'), /unknown board/);
});

test('the board is the UC-Mind300 CLI, on the verified ports', () => {
  const { b } = mk();
  assert.equal(b.profile.name, 'UC-Mind300');
  assert.equal(b.profile.protocol, 'cli');
  assert.equal(b.profile.baudRate, 115200);
  assert.deepEqual(b.ports, { A: 19, B: 18, C: 16, D: 15 });
  assert.equal(b.ports.B, PINS.display);
  assert.equal(b.ports.A, PINS.ledButton);
  assert.equal(b.ports.C, PINS.lineTracker);
  assert.equal(b.ports.D, PINS.touch);
  assert.equal(b.profile.pins.light, PINS.light);
});

test('capabilities() reports what the realtime path can actually do', () => {
  const { b } = mk();
  const cap = b.capabilities();
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
  assert.equal(cap.servo, true);
  assert.equal(cap.analogMax, ANALOG_MAX);
  assert.equal(cap.buzzer, false, 'tone is sketch-only — the lab must not offer it');
  assert.equal(cap.tone, false);
  assert.deepEqual(cap.sketchOnly, ['buzzer/tone']);
});

// ---------------------------------------------------------------- display
test('display.show() sends A10 18 <value> and does NOT wait for a reply', async () => {
  const { t, b } = mk();
  assert.equal(await b.display.show(1234), 'A10 18 1234');
  assert.equal(textOf(t), 'A10 18 1234\n\r');
  assert.equal(t.reads, 0, 'a write must never read — silence is the success path');
  assert.equal(t.drains, 0, 'nor drain: there is nothing to wait for');
  assert.deepEqual(b.log, ['A10 18 1234']);
});

test('display clamps to four digits and clear() shows 0', async () => {
  const { t, b } = mk();
  await b.display.show(99999);
  await b.display.clear();
  assert.deepEqual(linesOf(t), ['A10 18 9999', 'A10 18 0']);
});

// ---------------------------------------------------------------- motors
test('motor.run() drives by MOTOR NUMBER, 1-based', async () => {
  const { t, b } = mk();
  await b.motor.run(1, 150);
  await b.motor.run(2, 120);
  assert.deepEqual(linesOf(t), ['A8 1 0 0 150 0', 'A8 2 0 0 120 0']);
});

test('motor.stop() is speed 0 on the selected motor', async () => {
  const { t, b } = mk();
  await b.motor.stop(1);
  await b.motor.stop(2);
  assert.deepEqual(linesOf(t), ['A8 1 0 0 0 0', 'A8 2 0 0 0 0']);
  t.written.length = 0;
  await b.motor.stopAll();
  assert.deepEqual(linesOf(t), ['A8 10 3 0 0 0'], "the vendor's own stop-all");
});

test('a pin can never become a motor index', () => {
  const { t, b } = mk();
  // 0 is the old 0-based "motor 0" / pin-10 world; 3, 5, 6, 9, 11 are real pins.
  // Validation is synchronous, so a bad index throws before a promise is even created.
  for (const bad of [0, 3, 5, 6, 9, 10, 11, -1]) {
    assert.throws(() => b.motor.run(bad, 150), /motor index must be 1\.\.2/, `motor ${bad}`);
  }
  assert.equal(textOf(t), '', 'nothing may reach the board');
});

test('motor speed sign is the direction and is clamped', async () => {
  const { t, b } = mk();
  await b.motor.run(1, 9999);
  await b.motor.run(1, -9999);
  assert.deepEqual(linesOf(t), ['A8 1 0 0 255 0', 'A8 1 0 0 -255 0']);
});

// ---------------------------------------------------------------- drive
test('drive.turn() is the differential pair, never a single motor', async () => {
  const { t, b } = mk();
  await b.drive.turn(150, 150);
  await b.drive.turn(-150, 150);
  assert.deepEqual(linesOf(t), ['A8 10 2 0 150 150', 'A8 10 2 0 -150 150']);
  for (const line of linesOf(t)) assert.match(line, /^A8 10 /, 'must not fall back to M1/M2');
});

test('drive.move() and drive.stop() use their own differential modes', async () => {
  const { t, b } = mk();
  await b.drive.move(1, 150);
  await b.drive.stop();
  assert.deepEqual(linesOf(t), ['A8 10 1 1 150 0', 'A8 10 3 0 0 0']);
});

// ---------------------------------------------------------------- sensors
test('sensor.lineTracker() sends A9 16 2 2 <axis> and decodes the analog reply', async () => {
  const { t, b } = mk(['978\r\n', '88\r\n']);
  assert.equal(await b.sensor.lineTracker(1), 978);
  assert.equal(await b.sensor.lineTracker(2), 88);
  assert.deepEqual(linesOf(t), ['A9 16 2 2 1', 'A9 16 2 2 2']);
});

test('sensor.light() reads the built-in sensor on pin 21', async () => {
  const { t, b } = mk(['988\r\n']);
  assert.equal(await b.sensor.light(), 988);
  assert.deepEqual(linesOf(t), ['A16 21 0']);
});

test('sensor.touch() is BINARY — a boolean, not a level', async () => {
  const { t, b } = mk(['1\r\n', '0\r\n']);
  assert.equal(await b.sensor.touch(), true);
  assert.equal(await b.sensor.touch(), false);
  assert.deepEqual(linesOf(t), ['A20 15 0', 'A20 15 0']);
});

test('a silent sensor read is null, not a fake reading', async () => {
  const { b } = mk(['', '']);
  assert.equal(await b.sensor.light(), null);
  assert.equal(await b.sensor.touch(), null);
});

test('sensor reads DO wait for a reply — that is the one place waiting is correct', async () => {
  const { t, b } = mk(['500\r\n']);
  await b.sensor.light();
  assert.equal(t.reads, 1);
  assert.equal(t.drains, 1, 'stale bytes must be dropped before the read');
});

// ---------------------------------------------------------------- buttons / LEDs
test('buttons.read() is 1-based and returns a boolean', async () => {
  const { t, b } = mk(['1\r\n', '0\r\n']);
  assert.equal(await b.buttons.read(1), true);
  assert.equal(await b.buttons.read(4), false);
  assert.deepEqual(linesOf(t), ['A3 19 1 1', 'A3 19 1 4']);
});

test('buttons.readAll() reads all four in order', async () => {
  const { t, b } = mk(['1\r\n', '0\r\n', '0\r\n', '1\r\n']);
  assert.deepEqual(await b.buttons.readAll(), [true, false, false, true]);
  assert.deepEqual(linesOf(t), ['A3 19 1 1', 'A3 19 1 2', 'A3 19 1 3', 'A3 19 1 4']);
});

test('leds.set() sends the INVERTED level the vendor expects', async () => {
  const { t, b } = mk();
  await b.leds.set(1, true);
  await b.leds.set(1, false);
  await b.leds.set(4, true);
  // HIGH is sent as 0 by the vendor's own template — getting this backwards silently inverts it.
  assert.deepEqual(linesOf(t), ['A3 19 2 1 0', 'A3 19 2 1 1', 'A3 19 2 4 0']);
});

test('leds.on/off/all are conveniences over the same command', async () => {
  const { t, b } = mk();
  await b.leds.on(2);
  await b.leds.off(3);
  await b.leds.all(false);
  assert.deepEqual(linesOf(t), [
    'A3 19 2 2 0', 'A3 19 2 3 1',
    'A3 19 2 1 1', 'A3 19 2 2 1', 'A3 19 2 3 1', 'A3 19 2 4 1',
  ]);
  assert.equal(b.leds.count, LED_COUNT);
});

test('button and LED indices are validated', () => {
  const { b } = mk();
  for (const bad of [0, 5, -3, 2.5]) {
    assert.throws(() => b.buttons.read(bad), /button index must be 1\.\.4/);
    assert.throws(() => b.leds.set(bad, true), /LED index must be 1\.\.4/);
  }
});

// ---------------------------------------------------------------- sketch-only
test('buzzer throws an explicit sketch-only error instead of pretending', async () => {
  const { t, b } = mk();
  await assert.rejects(() => b.buzzer(true), (err) => {
    assert.equal(err.name, 'UnsupportedFeatureError');
    assert.equal(err.reason, 'sketch-only');
    assert.match(err.message, /not available over the realtime serial CLI/);
    return true;
  });
  assert.equal(textOf(t), '', 'no bytes may be sent for a feature that has no command');
});

test('there is no readAnalog() any more — analog reporting does not exist over the CLI', async () => {
  const { b } = mk();
  assert.equal(b.readAnalog, undefined);
  assert.equal(b.servo, UCMindBoard.prototype.servo, 'servo survives, it has a real command');
});

// ---------------------------------------------------------------- optional modules
test('the ultrasonic module still requires a declared pin', async () => {
  const { t, b } = mk(['42\r\n']);
  assert.throws(() => b.sensor.ultrasonic(6), /not a declared ultrasonic/);
  b.declareSensors({ 6: 'ultrasonic' });
  assert.equal(await b.sensor.ultrasonic(6), 42);
  assert.deepEqual(linesOf(t), ['A16 6 4']);
});

// ---------------------------------------------------------------- plumbing
test('the board can wrap a client it is handed, and shares its log', async () => {
  const { b } = mk();
  const again = new UCMindBoard(b.client, PROFILES['UC-Mind300']);
  await again.display.show(7);
  assert.equal(again.client, b.client, 'the same client, not a second one');
  assert.deepEqual(b.log, ['A10 18 7']);
});

test('a bad motor index is refused before anything is logged', () => {
  const { b } = mk();
  assert.throws(() => b.motor.run(3, 100), RangeError);
  assert.deepEqual(b.log, []);
});

test('the ESP32 profile reports no built-in light/touch', () => {
  const cap = new UCMindBoard(new FakeTransport(), PROFILES['UC-Mind100']).capabilities();
  assert.equal(cap.board, 'UC-Mind100');
  assert.equal(cap.light, false);
  assert.equal(cap.touch, false);
  assert.equal(cap.motors, 2);
});

test('the profile object carries the motor count as a number, not a pin list', () => {
  assert.equal(typeof PROFILES['UC-Mind300'].motors, 'number');
  assert.equal(PROFILES['UC-Mind300'].motors, MOTOR.M1 + 1);
  assert.equal(PROFILES['UC-Mind300'].buzzer, false);
});
