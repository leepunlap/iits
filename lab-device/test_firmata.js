/** Unit tests for the lab's JS Firmata device layer. No hardware needed: `node --test`. */
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  Firmata, MockTransport, WebSerialTransport, encode14, decode14, peripheralPayload,
  frameOneWireWrite, framePeripheral, frameDigitalWrite, frameAnalogWrite,
  frameSetPinMode, MODES, START_SYSEX, END_SYSEX, ONEWIRE_DATA, ONEWIRE_WRITE_SUBCMD,
  SET_PIN_MODE, DIGITAL_MESSAGE, ANALOG_MESSAGE, REPORT_ANALOG, ANALOG_MAPPING_RESPONSE, NEG_MARK, ARG_SEP,
} from './firmata.js';

test('14-bit round-trip', () => {
  for (const v of [0, 1, 127, 128, 255, 1000, 8191, 16383]) {
    assert.equal(decode14(...encode14(v)), v);
  }
});

test('14-bit clamps out-of-range input', () => {
  assert.equal(decode14(...encode14(99999)), 16383);
  assert.equal(decode14(...encode14(-5)), 0);
});

test('peripheral payload: positive, negative, two args, none', () => {
  assert.deepEqual([...peripheralPayload(1, 301)], [1, 0, 0x33, 0x30, 0x31]);
  assert.deepEqual([...peripheralPayload(4, -120)], [4, 0, NEG_MARK, 0x31, 0x32, 0x30]);
  assert.deepEqual([...peripheralPayload(5, 100, -50)],
    [5, 0, 0x31, 0x30, 0x30, ARG_SEP, NEG_MARK, 0x35, 0x30]);
  assert.deepEqual([...peripheralPayload(6)], [6, 0]);
});

test('identify() reads the board', async () => {
  const f = new Firmata(new MockTransport({ major: 2, minor: 7, name: 'UC-Mind' }), { timeout: 30 });
  const info = await f.identify();
  assert.deepEqual(info.firmata, [2, 7]);
  assert.equal(info.firmware, 'UC-Mind');
  assert.equal(info.pins, 1);
  assert.deepEqual(info.analogPins, [0]);
  assert.equal(info.level, 'L3'); // 1 pin in the mock
});

test('level detection: 40 pins = L2, 20 pins = L3', async () => {
  const l2 = new Firmata(new MockTransport({ pins: 40 }), { timeout: 30 });
  assert.equal((await l2.identify()).level, 'L2');

  const l3 = new Firmata(new MockTransport({ pins: 20 }), { timeout: 30 });
  assert.equal((await l3.identify()).level, 'L3');
});

test('setPinMode encodes the mode', async () => {
  const t = new MockTransport(); const f = new Firmata(t, { timeout: 20 });
  await f.setPinMode(13, 'output');
  assert.deepEqual(t.written.slice(-3), [SET_PIN_MODE, 13, MODES.output]);
});

test('digitalWrite sets and clears the right bit', async () => {
  const t = new MockTransport(); const f = new Firmata(t, { timeout: 20 });
  await f.setPinMode(13, 'output');
  t.written.length = 0;
  await f.digitalWrite(13, 1);                       // port 1, bit 5
  assert.deepEqual(t.written, [DIGITAL_MESSAGE | 1, 0x20, 0x00]);
  t.written.length = 0;
  await f.digitalWrite(13, 0);
  assert.deepEqual(t.written, [DIGITAL_MESSAGE | 1, 0x00, 0x00]);
});

test('digitalWrite port/bit maths for pin 2', async () => {
  const t = new MockTransport(); const f = new Firmata(t, { timeout: 20 });
  await f.setPinMode(2, 'output');
  t.written.length = 0;
  await f.digitalWrite(2, 1);
  assert.deepEqual(t.written, [DIGITAL_MESSAGE | 0, 0x04, 0x00]);
});

test('analogWrite encodes 14-bit value', async () => {
  const t = new MockTransport(); const f = new Firmata(t, { timeout: 20 });
  await f.analogWrite(9, 255);
  assert.deepEqual(t.written, [ANALOG_MESSAGE | 9, ...encode14(255)]);
});

test('OneWire frame shape matches the vendor protocol', () => {
  const frame = [...framePeripheral(18, 1, 301)];
  assert.equal(frame[0], START_SYSEX);
  assert.equal(frame[1], ONEWIRE_DATA);
  assert.equal(frame[2], ONEWIRE_WRITE_SUBCMD);
  assert.equal(frame[3], 18);
  assert.deepEqual(frame.slice(4, 20), new Array(16).fill(0));
  assert.deepEqual(frame.slice(20), [1, 0, 0x33, 0x30, 0x31, END_SYSEX]);
});

test('OneWire pin is masked to 7 bits', () => {
  assert.equal(frameOneWireWrite(0x81, Uint8Array.from([1]))[3], 0x01);
});

test('reportAnalog sends the analog CHANNEL, not the digital pin', async () => {
  const t = new MockTransport(); const f = new Firmata(t, { timeout: 20 });
  f.analogMapping = { 14: 0 };                 // the 300's only analog pin is 14 -> channel 0
  await f.reportAnalog(14, true);
  assert.deepEqual(t.written, [REPORT_ANALOG | 0, 1]);
});

test('analog reports resolve the channel back to the pin', () => {
  const f = new Firmata(new MockTransport());
  f.analogMapping = { 14: 0, 15: 1 };
  const ch0 = [];
  for (const b of [0xe0, 0x34, 0x02]) ch0.push(...f._feed(b));
  assert.equal(ch0[0].kind, 'analog');
  assert.equal(ch0[0].channel, 0);
  assert.equal(ch0[0].pin, 14);
  assert.equal(ch0[0].value, decode14(0x34, 0x02));

  const ch1 = [];
  for (const b of [0xe1, 0x10, 0x00]) ch1.push(...f._feed(b));
  assert.equal(ch1[0].pin, 15);
});

test('WebSerialTransport drives a Web-Serial-shaped port', async () => {
  class FakePort {
    // Web-Serial-shaped fake: waiter-based reader (no polling, so the test process can exit)
    constructor() { this.pending = []; this.waiters = []; this.written = []; this.closed = false; }
    _deliver() {
      while (this.pending.length && this.waiters.length) {
        const resolve = this.waiters.shift();
        resolve({ value: Uint8Array.from(this.pending.splice(0)), done: false });
      }
    }
    emit(bytes) { this.pending.push(...bytes); this._deliver(); }
    get readable() {
      const self = this;
      return { getReader: () => ({
        read: () => new Promise((resolve) => { self.waiters.push(resolve); self._deliver(); }),
        cancel: async () => { for (const w of self.waiters.splice(0)) w({ value: undefined, done: true }); },
        releaseLock: () => {},
      }) };
    }
    get writable() {
      const self = this;
      return { getWriter: () => ({
        write: async (bytes) => { self.written.push(...bytes); },
        releaseLock: () => {},
      }) };
    }
    async open(opts) { this.opened = opts; }
    async close() { this.closed = true; }
  }

  const port = new FakePort();
  const t = await WebSerialTransport.open(port, { baudRate: 57600, settle: 0 });
  assert.equal(port.opened.baudRate, 57600);
  assert.equal(port.opened.dataBits, 8);

  await t.write(Uint8Array.from([0x01, 0x02]));
  assert.deepEqual(port.written, [0x01, 0x02]);

  port.emit([0xf9, 0x02, 0x07]);
  const got = await t.read(16, 300);
  assert.deepEqual([...got], [0xf9, 0x02, 0x07]);

  assert.deepEqual(await t.read(16, 30), new Uint8Array(0));   // timeout path
  await t.close();
  assert.equal(port.closed, true);
});

test('analog mapping is indexed by DIGITAL PIN (real board payloads)', () => {
  const f = new Firmata(new MockTransport());
  // UC-Mind300 (Uno, 20 pins): pins 0-13 are not analog, pins 14-19 are A0-A5
  const uno = [...new Array(14).fill(0x7f), 0, 1, 2, 3, 4, 5];
  f._onSysex([ANALOG_MAPPING_RESPONSE, ...uno]);
  assert.deepEqual(f.analogMapping, { 14: 0, 15: 1, 16: 2, 17: 3, 18: 4, 19: 5 });
  assert.equal(Object.keys(f.analogMapping).length, 6);

  // earlier bug: 0x7F treated as a separator collapsed this to one bogus entry
  const esp32 = [11, 0x7f, 12, 0x7f, 10, 0x7f, 0x7f, 0x7f];
  const g = new Firmata(new MockTransport());
  g._onSysex([ANALOG_MAPPING_RESPONSE, ...esp32]);
  assert.deepEqual(g.analogMapping, { 0: 11, 2: 12, 4: 10 });
});
