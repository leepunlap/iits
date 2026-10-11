/**
 * Lesson-level board API for the L2/L3 Wonder Lab, on top of the Firmata device layer.
 *
 * The lab thinks in "motor 1", "the buzzer", "a sensor" — this maps those onto the pins each
 * board's vendor firmware actually exposes. Pin facts come from the vendor's own headers plus
 * what the two boards report over Firmata (see ../L23-PROTOCOL.md and `board_map.py`).
 *
 *   UC-Mind300 (AVR, full StandardFirmata): digital 2-19, PWM 3/5/6/9/10/11, analog 14-19,
 *       servo 2-19, I2C 18/19.  On-board motor ports M1=(pwm 10, dir 9), M2=(pwm 5, dir 6);
 *       on-board buzzer = pin 7.  Smart-module ports A/B/C/D = pins 19/18/16/15.
 *
 *   UC-Mind100 (ESP32, minimal link build): PWM and analog only — no digital I/O and no OneWire,
 *       so the kit's smart modules (display, 4-button module) are NOT reachable.  Ports
 *       A/B/C/D = pins 14/5/25/27.
 */

import { Firmata } from './firmata.js';

export const PROFILES = {
  'UC-Mind300': {
    name: 'UC-Mind300',
    deviceId: 'arduinoUno',
    minPins: 0,
    maxPins: 31,
    motors: [{ pwm: 10, dir: 9 }, { pwm: 5, dir: 6 }],   // on-board M1, M2 (direct pins)
    buzzer: 7,
    servoPins: [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
    ports: { A: 19, B: 18, C: 16, D: 15 },               // smart-module ports (OneWire modules)
    digitalOut: true,
    analogPin: 14,                                        // A0
  },
  'UC-Mind100': {
    name: 'UC-Mind100',
    deviceId: 'arduinoEsp32Min',
    minPins: 32,
    maxPins: 999,
    motors: null,                                        // driven over OneWire on pin 32 — not exposed
    buzzer: null,
    servoPins: [],
    ports: { A: 14, B: 5, C: 25, D: 27 },
    digitalOut: false,
    analogPin: 36,                                        // channel 0 on this build
  },
};

export function profileFor(info) {
  const pins = info?.pins ?? 0;
  return pins >= 32 ? PROFILES['UC-Mind100'] : PROFILES['UC-Mind300'];
}

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

export class UCMindBoard {
  constructor(firmata, profile) {
    if (!(firmata instanceof Firmata)) throw new TypeError('expected a Firmata instance');
    this.f = firmata;
    this.profile = profile ?? profileFor({ pins: firmata.capabilities.length });
    this.port = profile?.ports ?? this.profile.ports;
  }

  /** What this board can do — the lab uses it to grey out unsupported blocks. */
  capabilities() {
    const p = this.profile;
    return {
      board: p.name,
      motors: p.motors ? p.motors.length : 0,
      buzzer: p.buzzer !== null,
      servo: p.servoPins.length > 0,
      digitalOut: p.digitalOut,
      analogIn: true,
      smartModules: false,        // OneWire modules are not reachable over Firmata on either board
    };
  }

  _motor(index) {
    const motors = this.profile.motors;
    if (!motors) {
      throw new Error(`${this.profile.name}: motors are OneWire modules and this firmware build does not expose them`);
    }
    const m = motors[index];
    if (!m) throw new RangeError(`no motor ${index} on ${this.profile.name} (have ${motors.length})`);
    return m;
  }

  /** speed: -255..255 (sign = direction). The AVR uses a PWM pin plus a direction pin. */
  async motor(index, speed) {
    const m = this._motor(index);
    const value = clamp(Math.trunc(speed), -255, 255);
    await this.f.setPinMode(m.pwm, 'pwm');
    await this.f.setPinMode(m.dir, 'output');
    await this.f.digitalWrite(m.dir, value < 0 ? 0 : 1);
    await this.f.analogWrite(m.pwm, Math.abs(value));
    return value;
  }

  async motorStop(index) {
    const m = this._motor(index);
    await this.f.analogWrite(m.pwm, 0);
  }

  /** AVR only: the on-board buzzer is a plain digital pin. */
  async buzzer(on) {
    if (this.profile.buzzer === null) {
      throw new Error(`${this.profile.name}: no on-board buzzer pinned by this firmware build`);
    }
    await this.f.setPinMode(this.profile.buzzer, 'output');
    await this.f.digitalWrite(this.profile.buzzer, on ? 1 : 0);
  }

  async digitalOut(pin, on) {
    if (!this.profile.digitalOut) {
      throw new Error(`${this.profile.name}: this firmware build exposes no digital output mode`);
    }
    await this.f.setPinMode(pin, 'output');
    await this.f.digitalWrite(pin, on ? 1 : 0);
  }

  async servo(pin, angle) {
    if (!this.profile.servoPins.includes(pin)) {
      throw new RangeError(`${this.profile.name}: pin ${pin} is not a servo pin`);
    }
    await this.f.setPinMode(pin, 'servo');
    await this.f.analogWrite(pin, clamp(Math.trunc(angle), 0, 180));
  }

  /** Turn on reporting and sample for `ms`, returning the readings for that pin. */
  async readAnalog(pin, ms = 300) {
    await this.f.setPinMode(pin, 'analog');
    await this.f.reportAnalog(pin, true);
    const events = await this.f.poll(ms);
    await this.f.reportAnalog(pin, false);
    return events.filter((e) => e.kind === 'analog' && e.pin === pin).map((e) => e.value);
  }
}
