/**
 * Tests for the verified UC-Mind300 protocol — the command strings themselves.
 *
 * These assert **byte-for-byte** what goes on the wire, because every one of these spellings was
 * paid for on the bench. No hardware here: the builders and parsers are pure.
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  ANALOG_MAX, BAUD, DIFF, FN, LED_COUNT, MOTOR, PINS, PORT_NAMES, TERMINATOR,
  buttonRead, buttonsRead, checkReply, clampSpeed, display, driveMove, driveStop, driveTurn,
  ledSet, lightRead, lineTrackerRead, motorRun, motorSelector, motorStop, parseAnalog,
  parseButton, parseButtons, parseTouch, servo, soundRead, touchRead, ultrasonicRead,
  UcmakeClient, UcmakeCommandError, unsupportedOnRealtime,
} from './ucmind300.js';

/** A transport that records writes and replays queued replies. */
class FakeTransport {
  constructor(replies = []) { this.written = []; this.replies = [...replies]; this.drained = 0; this.closed = false; }
  async write(bytes) { this.written.push(...bytes); }
  async read() {
    const next = this.replies.shift();
    return next == null ? new Uint8Array() : new TextEncoder().encode(next);
  }
  async drain() { this.drained += 1; }
  async close() { this.closed = true; }
}
const textOf = (t) => new TextDecoder().decode(Uint8Array.from(t.written));

test('the wire parameters match the bench-verified notes', () => {
  assert.equal(BAUD, 115200);
  assert.equal(TERMINATOR, '\n\r', 'LF then CR');
  assert.equal(PINS.display, 18, 'display is port B, digital pin 18');
  assert.equal(PINS.ledButton, 19, 'buttons/LEDs are port A, digital pin 19');
  assert.equal(PINS.lineTracker, 16, 'tracker is port C, digital pin 16 — the NUMBER, not A2');
  assert.equal(PINS.touch, 15, 'touch is port D, digital pin 15');
  assert.equal(PINS.light, 21, 'built-in light sensor is pin 21 = A7');
  assert.deepEqual(PORT_NAMES, { display: 'A4', ledButton: 'A5', lineTracker: 'A2', touch: 'A1' });
  assert.equal(ANALOG_MAX, 1023);
});

// ---------------------------------------------------------------- motors
test('a motor is selected by NUMBER, never by pin', () => {
  assert.equal(motorRun(MOTOR.M1, 150), 'A8 1 0 0 150 0');
  assert.equal(motorRun(MOTOR.M2, 120), 'A8 2 0 0 120 0');
  assert.equal(motorRun(1, 150), 'A8 1 0 0 150 0');
  assert.equal(motorRun(2, 150), 'A8 2 0 0 150 0');
});

test('the pin-numbered motor form is REFUSED, not sent', () => {
  // 5/6/9 are the pins the stale implementation used; they are not motor numbers.
  for (const pin of [5, 6, 9, 3, 11, 0, 7]) {
    assert.throws(() => motorRun(pin, 150), /which is a pin, not a motor/, `pin ${pin} must not reach the wire`);
  }
  // 10 is a nasty overlap: a historic pin number AND the differential selector. Legal, but it
  // selects the pair — it must never be read as "motor 10".
  assert.equal(motorRun(MOTOR.DIFFERENTIAL, 150), 'A8 10 0 0 150 0');
  assert.equal(MOTOR.DIFFERENTIAL, 10);
  assert.throws(() => motorSelector('m1'), /finite number/, 'the field is numeric on the wire');
});

test('motor stop is speed 0 on the selected motor; stop-all is the vendor form', () => {
  assert.equal(motorStop(1), 'A8 1 0 0 0 0');
  assert.equal(motorStop(2), 'A8 2 0 0 0 0');
  assert.equal(driveStop(), 'A8 10 3 0 0 0', 'the vendor hardcodes this stop form');
});

test('speed is clamped to -255..255 and truncated to an integer', () => {
  assert.equal(motorRun(1, 9999), 'A8 1 0 0 255 0');
  assert.equal(motorRun(1, -9999), 'A8 1 0 0 -255 0');
  assert.equal(motorRun(1, 120.7), 'A8 1 0 0 120 0');
  assert.equal(clampSpeed(-150), -150, 'the sign IS the direction — reverse must survive');
  assert.throws(() => motorRun(1, 'fast'), /finite number/);
});

// ---------------------------------------------------------------- differential
test('the differential pair is explicit: #1 moves, #2 turns', () => {
  assert.equal(driveMove(1, 150), 'A8 10 1 1 150 0');
  assert.equal(driveMove(2, -150), 'A8 10 1 2 -150 0');
  assert.equal(driveTurn(150, 150), 'A8 10 2 0 150 150');
  assert.equal(driveTurn(-150, 150), 'A8 10 2 0 -150 150', 'equal and opposite spins on the spot');
  assert.equal(DIFF.MOVE, 1);
  assert.equal(DIFF.TURN, 2);
  assert.equal(DIFF.STOP, 3);
});

test('driveTurn never falls through to the single-motor form', () => {
  // The trap: `A8 10 …` spins whichever motor is attached, so it must never be used for one motor.
  assert.match(driveTurn(100, 100), /^A8 10 2 0 100 100$/);
  assert.doesNotMatch(driveTurn(100, 100), /^A8 [12] /);
});

// ---------------------------------------------------------------- display
test('display is A10 on pin 18, clamped to four digits', () => {
  assert.equal(display(1234), 'A10 18 1234');
  assert.equal(display(8888), 'A10 18 8888');
  assert.equal(display(0), 'A10 18 0');
  assert.equal(display(12345), 'A10 18 9999', 'four digits only');
  assert.equal(display(-5), 'A10 18 0', 'a negative would display as garbage');
  assert.equal(display(4321, 'A4'), 'A10 A4 4321', 'the vendor port-name spelling is accepted');
});

// ---------------------------------------------------------------- buttons / LEDs
test('the LED level is INVERTED — the vendor sends HIGH as 0', () => {
  assert.equal(ledSet(1, true), 'A3 19 2 1 0', 'on  -> 0');
  assert.equal(ledSet(1, false), 'A3 19 2 1 1', 'off -> 1');
  assert.equal(ledSet(4, true), 'A3 19 2 4 0');
});

test('buttons are read one at a time on pin 19; all four in order', () => {
  assert.equal(buttonRead(1), 'A3 19 1 1');
  assert.equal(buttonRead(4), 'A3 19 1 4');
  assert.deepEqual(buttonsRead(), ['A3 19 1 1', 'A3 19 1 2', 'A3 19 1 3', 'A3 19 1 4']);
});

test('button/LED indices are validated against the 4-wide module', () => {
  for (const bad of [0, 5, -1, 1.5]) {
    assert.throws(() => ledSet(bad, true), /LED index must be 1\.\.4/);
    assert.throws(() => buttonRead(bad), /button index must be 1\.\.4/);
  }
  assert.equal(LED_COUNT, 4);
});

// ---------------------------------------------------------------- sensors
test('the sensors use the verified read commands', () => {
  assert.equal(lineTrackerRead(1), 'A9 16 2 2 1');
  assert.equal(lineTrackerRead(2), 'A9 16 2 2 2');
  assert.equal(lightRead(), 'A16 21 0');
  assert.equal(touchRead(), 'A20 15 0');
  assert.equal(ultrasonicRead(6), 'A16 6 4');
  assert.equal(soundRead(), 'A15 17 0');
});

test('the tracker read includes the required "2 2" field and a numeric port', () => {
  // `A9 16 1 <axis>` is SILENT on this build, and `A9 A2 …` saturates at 1023.
  const cmd = lineTrackerRead(1);
  assert.match(cmd, / 2 2 /, 'the module-type/count field is required');
  assert.doesNotMatch(cmd, /A2/, 'the port must be the number 16, not the vendor port name');
  assert.throws(() => lineTrackerRead(3), /axis must be 1\.\.2/);
  assert.throws(() => lineTrackerRead(0), /axis must be 1\.\.2/);
});

test('servo uses A6 with the angle clamped to 0..180', () => {
  assert.equal(servo(9, 90), 'A6 9 90');
  assert.equal(servo(9, 400), 'A6 9 180');
  assert.equal(servo(9, -20), 'A6 9 0');
});

// ---------------------------------------------------------------- parsing
test('analog readings are 0..1023 and null when the board stays silent', () => {
  assert.equal(parseAnalog('988\r\n'), 988);
  assert.equal(parseAnalog('0'), 0);
  assert.equal(parseAnalog('1023\r\n'), 1023);
  assert.equal(parseAnalog('2000'), 1023, 'clamped');
  assert.equal(parseAnalog(''), null, 'silence is NOT a reading for a read command');
  assert.equal(parseAnalog('x'), null);
});

test('touch is BINARY, not an analog level', () => {
  assert.equal(parseTouch('1'), true);
  assert.equal(parseTouch('0'), false);
  assert.equal(parseTouch('0\r\n'), false);
  assert.equal(parseTouch(''), null);
  // The bench saw 0/1 only — never an analog sweep like the tracker's 0..1023.
  assert.equal(parseTouch('182'), true, 'any non-zero means touched');
});

test('one button: 1 means pressed; four buttons decode in order', () => {
  assert.equal(parseButton('1'), true);
  assert.equal(parseButton('0'), false);
  assert.equal(parseButton(''), null);
  assert.deepEqual(parseButtons(['1\r\n', '0\r\n', '0\r\n', '0\r\n']), [true, false, false, false]);
  assert.deepEqual(parseButtons(['', '', '', '']), [null, null, null, null], 'unanswered is not "released"');
});

test('the firmware\'s error strings are detected — chatter means failure here', () => {
  assert.throws(() => checkReply('A10 18', 'ERROR 参数不足'), UcmakeCommandError);
  assert.throws(() => checkReply('A10', 'A10 错误: 缺少参数'), /board rejected/);
  assert.equal(checkReply('A10 18 1234', ''), '', 'silence is success — the whole point');
  assert.equal(checkReply('A10 18 1234', '   '), '');
  assert.equal(checkReply('A16 21 0', '988'), '988');
});

// ---------------------------------------------------------------- client behaviour
test('writes are fire-and-forget and send LF+CR', async () => {
  const t = new FakeTransport();
  const c = new UcmakeClient(t);
  await c.display(1234);
  assert.equal(textOf(t), 'A10 18 1234\n\r');
  await c.run(1, 150);
  assert.equal(textOf(t), 'A10 18 1234\n\rA8 1 0 0 150 0\n\r');
  assert.equal(t.drained, 0, 'a write must not even drain — it never waits for a reply');
  assert.deepEqual(c.log, ['A10 18 1234', 'A8 1 0 0 150 0']);
});

test('reads drain stale input first and decode what comes back', async () => {
  const t = new FakeTransport(['988\r\n']);
  const c = new UcmakeClient(t);
  assert.equal(await c.readLight(), 988);
  assert.equal(t.drained, 1, 'stale bytes from the previous command must not be mistaken for the answer');
  assert.equal(textOf(t), 'A16 21 0\n\r');
});

test('readTouch/readButton return booleans, readButtons returns four', async () => {
  const t = new FakeTransport(['1\r\n', '1\r\n']);
  const c = new UcmakeClient(t);
  assert.equal(await c.readTouch(), true);
  assert.equal(await c.readButton(2), true);
  assert.equal(textOf(t), 'A20 15 0\n\rA3 19 1 2\n\r');
});

test('readButtons asks for all four in order and decodes each', async () => {
  const t = new FakeTransport(['1\r\n', '0\r\n', '0\r\n', '1\r\n']);
  const c = new UcmakeClient(t);
  assert.deepEqual(await c.readButtons(), [true, false, false, true]);
  for (const cmd of ['A3 19 1 1', 'A3 19 1 2', 'A3 19 1 3', 'A3 19 1 4']) {
    assert.ok(textOf(t).includes(cmd + '\n\r'), `${cmd} must be sent`);
  }
});

test('a rejected command surfaces as an error, not as a reading', async () => {
  const t = new FakeTransport(['ERROR 参数不足\r\n', 'ERROR 参数不足\r\n']);
  const c = new UcmakeClient(t);
  await assert.rejects(() => c.readLight(), UcmakeCommandError);
  await assert.rejects(() => c.readTouch(), /参数不足/);
});

test('a client needs a real transport', () => {
  assert.throws(() => new UcmakeClient(null), /expected a transport/);
  assert.throws(() => new UcmakeClient({}), /expected a transport/);
});

test('convenience methods match their long-form names', async () => {
  const t = new FakeTransport(['500\r\n', '500\r\n', '1\r\n', '1\r\n']);
  const c = new UcmakeClient(t);
  assert.equal(await c.lineTracker(2), 500);
  assert.equal(await c.readLineTracker(2), 500);
  assert.equal(await c.touch(), true);
  assert.equal(await c.readTouch(), true);
});

// ---------------------------------------------------------------- sketch-only features
test('tone is refused on the realtime path with a named reason', () => {
  const err = unsupportedOnRealtime('buzzer/tone', 'sketch-only');
  assert.equal(err.name, 'UnsupportedFeatureError');
  assert.equal(err.reason, 'sketch-only');
  assert.match(err.message, /not available over the realtime serial CLI/);
});
