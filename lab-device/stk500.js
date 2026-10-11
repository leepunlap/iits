/**
 * STK500v1 flasher for Optiboot AVR boards — the UC-Mind300's ATmega328P.
 *
 * esptool-js covers ESP32 only; the AVR path needs the Arduino bootloader protocol. Transport
 * agnostic, so the same code runs in the browser and in Node (where it can be verified on hardware).
 *
 * Protocol notes that cost real debugging time, all measured on a UC-Mind300:
 *
 *  * Optiboot implements only a *subset* of STK500v1 — GET_SYNC, LOAD_ADDRESS, PROG_PAGE, READ_PAGE
 *    and friends. It does **not** implement ENTER_PROGMODE (0x50) / LEAVE_PROGMODE (0x51) and ignores
 *    them silently. Waiting for a reply to those spans the bootloader's window, the application
 *    boots, and its banner (0xf90102) returns as a bogus "bad INSYNC".
 *  * The window is short (~600 ms here), so GET_SYNC must be hammered with *short* read timeouts;
 *    with long ones the sync lands at the very end and the next command misses.
 *  * Opening the serial port asserts DTR, which resets the board into Optiboot — the most reliable
 *    window. Explicit DTR pulses are kept for retries.
 *  * Losing the window mid-write is normal, so the whole write is retried.
 */

export const STK = {
  OK: 0x10, INSYNC: 0x14, EOP: 0x20,
  GET_SYNC: 0x30, ENTER_PROGMODE: 0x50, LEAVE_PROGMODE: 0x51,
  LOAD_ADDRESS: 0x55, PROG_PAGE: 0x64, READ_PAGE: 0x74, GET_PARAMETER: 0x41,
  FLASH: 0x46,          // 'F'
};

/** Parse Intel HEX into a flat flash image (0xFF-filled) plus which bytes were actually given. */
export function parseIntelHex(text, size = 0x8000) {
  const bytes = new Uint8Array(size).fill(0xff);
  const present = new Uint8Array(size);
  let upper = 0;
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line.startsWith(':') || line.length < 11) continue;
    const len = parseInt(line.substr(1, 2), 16);
    const addr = parseInt(line.substr(3, 4), 16);
    const type = parseInt(line.substr(7, 2), 16);
    if (type === 1) break;                                  // EOF
    if (type === 4) { upper = parseInt(line.substr(9, 4), 16) << 16; continue; }
    if (type !== 0) continue;
    for (let i = 0; i < len; i += 1) {
      const b = parseInt(line.substr(9 + i * 2, 2), 16);
      if (upper + addr + i < size) { bytes[upper + addr + i] = b; present[upper + addr + i] = 1; }
    }
  }
  let last = 0;
  for (let i = 0; i < size; i += 1) if (present[i]) last = i;
  return { bytes, present, length: last + 1 };
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export class Stk500 {
  constructor(transport, { pageSize = 128, log = () => {}, timeout = 1200, reset = null } = {}) {
    this.t = transport;
    this.pageSize = pageSize;
    this.log = log;
    this.timeout = timeout;
    this.reset = reset;      // async fn that pulses the board into Optiboot, for retries
  }

  /** Send a command, expect INSYNC…OK. Returns the payload between them. */
  async command(bytes, expectPayload = 0, timeout = this.timeout) {
    await this.t.write(Uint8Array.from([...bytes, STK.EOP]));
    const reply = await this.t.read(expectPayload + 2, timeout);
    if (!reply || reply.length < 2) {
      throw new Error(`no reply (${reply ? reply.length : 0} bytes) — bootloader window lost?`);
    }
    if (reply[0] !== STK.INSYNC) throw new Error(`bad INSYNC: 0x${reply[0].toString(16)}`);
    if (reply[reply.length - 1] !== STK.OK) {
      throw new Error(`bad OK trailer: 0x${reply[reply.length - 1].toString(16)}`);
    }
    return reply.slice(1, reply.length - 1);
  }

  /**
   * Hammer GET_SYNC into the bootloader window and *scan* each reply, because application bytes can
   * arrive mixed in. Short timeouts matter: a long one means the sync lands at the window's end.
   */
  async sync(attempts = 30, perTry = 25) {
    for (let i = 0; i < attempts; i += 1) {
      await this.t.drain?.();
      await this.t.write(Uint8Array.from([STK.GET_SYNC, STK.EOP]));
      const reply = await this.t.read(64, perTry);
      if (reply) {
        for (let j = 0; j + 1 < reply.length; j += 1) {
          if (reply[j] === STK.INSYNC && reply[j + 1] === STK.OK) return true;
        }
      }
      await sleep(10);
    }
    return false;
  }

  /** Sync — first using the window from opening the port, then by pulsing the reset lines. */
  async enterProgmode(cycles = 4, triesPerCycle = 32) {
    for (let c = 0; c <= cycles; c += 1) {
      if (c > 0 && this.reset) await this.reset();
      // avrdude uses Timeout=200ms and SyncLoops=32 for this part; matching them keeps the window
      // open long enough to catch Optiboot on slower bridges.
      if (await this.sync(triesPerCycle, 200)) return true;
    }
    throw new Error(`could not sync with the bootloader after ${cycles} attempts`);
  }

  /** Write every page. Retried as a whole, since losing the window mid-write just needs a restart. */
  async flash(image, onProgress = () => {}, attempts = 4) {
    let lastErr = null;
    for (let a = 0; a < attempts; a += 1) {
      try {
        await this.enterProgmode();
        const total = Math.ceil(image.length / this.pageSize);
        for (let page = 0; page < total; page += 1) {
          const start = page * this.pageSize;
          const chunk = image.slice(start, start + this.pageSize);
          const word = start >> 1;                          // LOAD_ADDRESS counts WORDS
          await this.command([STK.LOAD_ADDRESS, word & 0xff, (word >> 8) & 0xff]);
          await this.command([STK.PROG_PAGE, (chunk.length >> 8) & 0xff, chunk.length & 0xff, STK.FLASH, ...chunk]);
          onProgress((page + 1) / total);
        }
        return true;
      } catch (e) { lastErr = e; }
    }
    throw new Error(`flash failed after ${attempts} attempts: ${lastErr && lastErr.message}`);
  }

  /** Read the flash back — the strongest check available without eyes on the board. */
  async read(length, attempts = 4) {
    let lastErr = null;
    for (let a = 0; a < attempts; a += 1) {
      try {
        await this.enterProgmode();
        const out = new Uint8Array(length);
        const total = Math.ceil(length / this.pageSize);
        for (let page = 0; page < total; page += 1) {
          const start = page * this.pageSize;
          const len = Math.min(this.pageSize, length - start);
          const word = start >> 1;
          await this.command([STK.LOAD_ADDRESS, word & 0xff, (word >> 8) & 0xff]);
          const data = await this.command([STK.READ_PAGE, (len >> 8) & 0xff, len & 0xff, STK.FLASH], len);
          out.set(data.slice(0, len), start);
        }
        return out;
      } catch (e) { lastErr = e; }
    }
    throw new Error(`read failed after ${attempts} attempts: ${lastErr && lastErr.message}`);
  }
}
