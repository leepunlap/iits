/** Tests for the lesson-level board API. No hardware. */
import test from 'node:test';
import assert from 'node:assert/strict';

import { Firmata, MockTransport, ANALOG_MESSAGE, DIGITAL_MESSAGE, SET_PIN_MODE, MODES } from './firmata.js';
import { UCMindBoard, PROFILES, profileFor } from './board.js';

const newBoard = (name, pins) => {
  const t = new MockTransport({ pins: pins ?? 20 });
  const f = new Firmata(t, { timeout: 20 });
  f.capabilities = new Array(pins ?? 20).fill([]);
  return { t, f, b: new UCMindBoard(f, PROFILES[name]) };
};

test('profileFor picks the board by pin count', () => {
  assert.equal(profileFor({ pins: 20 }).name, 'UC-Mind300');
  assert.equal(profileFor({ pins: 40 }).name, 'UC-Mind100');
});

test('capabilities() reflects the real limits of each profile', () => {
  const { b } = newBoard('UC-Mind300');
  assert.deepEqual(b.capabilities(), {
    board: 'UC-Mind300', motors: 2, buzzer: true, servo: true,
    digitalOut: true, analogIn: true, smartModules: false,
  });
  const { b: e } = newBoard('UC-Mind100', 40);
  assert.equal(e.capabilities().motors, 0);
  assert.equal(e.capabilities().buzzer, false);
  assert.equal(e.capabilities().digitalOut, false);
});

test('motor() drives PWM + direction, sign picks the direction', async () => {
  const { t, b } = newBoard('UC-Mind300');
  await b.motor(0, 120);                       // M1 = pwm 10, dir 9
  const wire = [...t.written];
  assert.deepEqual(wire.slice(0, 3), [SET_PIN_MODE, 10, MODES.pwm]);
  assert.deepEqual(wire.slice(3, 6), [SET_PIN_MODE, 9, MODES.output]);
  assert.deepEqual(wire.slice(6, 9), [DIGITAL_MESSAGE | 1, 0x02, 0x00]);   // pin 9 high = forward
  assert.deepEqual(wire.slice(9, 12), [ANALOG_MESSAGE | 10, 120, 0x00]);

  t.written.length = 0;
  await b.motor(1, -80);                       // M2 = pwm 5, dir 6, reverse
  const w2 = [...t.written];
  assert.deepEqual(w2.slice(6, 9), [DIGITAL_MESSAGE | 0, 0x00, 0x00]);     // pin 6 low = reverse
  assert.deepEqual(w2.slice(9, 12), [ANALOG_MESSAGE | 5, 80, 0x00]);
});

test('motor() clamps and validates', async () => {
  const { b } = newBoard('UC-Mind300');
  assert.equal(await b.motor(0, 9999), 255);
  await assert.rejects(() => b.motor(2, 100), /no motor 2/);
});

test('motors are refused on the ESP32 profile (OneWire modules)', async () => {
  const { b } = newBoard('UC-Mind100', 40);
  await assert.rejects(() => b.motor(0, 100), /OneWire/);
  await assert.rejects(() => b.buzzer(true), /buzzer/);
});

test('buzzer uses the on-board pin', async () => {
  const { t, b } = newBoard('UC-Mind300');
  await b.buzzer(true);
  assert.deepEqual([...t.written], [SET_PIN_MODE, 7, MODES.output, DIGITAL_MESSAGE | 0, 0x00, 0x01]);
});

test('servo validates the pin set', async () => {
  const { t, b } = newBoard('UC-Mind300');
  await b.servo(9, 90);
  assert.deepEqual([...t.written], [SET_PIN_MODE, 9, MODES.servo, ANALOG_MESSAGE | 9, 90, 0x00]);
  await assert.rejects(() => b.servo(14, 90), /not a servo pin/);
});

test('readAnalog enables reporting, samples, then disables it', async () => {
  const { t, f, b } = newBoard('UC-Mind300');
  f.analogMapping = { 14: 0 };
  t._answer([0xe0, 0x34, 0x02]);                        // a channel-0 report waiting on the wire
  const values = await b.readAnalog(14, 30);
  assert.deepEqual(values, [0x134]);
  assert.equal(f.analogMapping[14], 0);
});
