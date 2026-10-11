/** Tests for the STK500v1 flasher, driven by a simulated Optiboot bootloader. */
import test from 'node:test';
import assert from 'node:assert/strict';

import { Stk500, parseIntelHex, STK } from './stk500.js';

/** A faithful-enough Optiboot: same commands, same INSYNC/OK framing. */
class MockOptiboot {
  constructor(size = 0x8000) {
    this.flash = new Uint8Array(size).fill(0xff);
    this.out = [];
    this.cmd = [];
    this.progmode = false;
    this.addr = 0;
    this.remaining = 0;
    this.log = [];
  }
  async write(bytes) { for (const b of bytes) this._byte(b); }
  async read(n, timeout = 200) {
    const deadline = Date.now() + timeout;
    while (this.out.length < n && Date.now() < deadline) await new Promise((r) => setTimeout(r, 2));
    return Uint8Array.from(this.out.splice(0, n));
  }
  async drain() { this.out.length = 0; }
  // A real bootloader knows a page's length, so data bytes that happen to equal EOP (0x20) are
  // data, not a terminator. The mock must model that or it corrupts any page containing 0x20.
  _byte(b) {
    if (this.remaining > 0) { this.cmd.push(b); this.remaining -= 1; return; }
    if (b === STK.EOP) { this._exec(); return; }
    this.cmd.push(b);
    if (this.cmd[0] === STK.PROG_PAGE && this.cmd.length === 4) {
      this.remaining = (this.cmd[1] << 8) | this.cmd[2];
    }
  }
  _exec() {
    const c = this.cmd; this.cmd = [];
    this.log.push(c[0]);
    const ok = () => this.out.push(STK.INSYNC, STK.OK);
    switch (c[0]) {
      case STK.GET_SYNC: ok(); break;
      case STK.ENTER_PROGMODE: this.progmode = true; ok(); break;   // Optiboot ignores these in
      case STK.LEAVE_PROGMODE: this.progmode = false; ok(); break;  // reality; the flasher no longer sends them
      case STK.LOAD_ADDRESS: this.addr = ((c[2] << 8) | c[1]) * 2; ok(); break;
      case STK.PROG_PAGE: {
        const len = (c[1] << 8) | c[2];
        if (c[3] !== STK.FLASH) throw new Error('expected flash page');
        this.flash.set(c.slice(4, 4 + len), this.addr);
        ok();
        break;
      }
      case STK.READ_PAGE: {
        const len = (c[1] << 8) | c[2];
        this.out.push(STK.INSYNC, ...this.flash.slice(this.addr, this.addr + len), STK.OK);
        break;
      }
      default: ok();
    }
  }
}

const hexFor = (bytes) => {
  const lines = [];
  for (let addr = 0; addr < bytes.length; addr += 16) {
    const chunk = bytes.slice(addr, addr + 16);
    const len = chunk.length;                       // the last record is usually short
    const sum = len + ((addr >> 8) & 0xff) + (addr & 0xff) + chunk.reduce((a, b) => a + b, 0);
    lines.push(':' + [len, (addr >> 8) & 0xff, addr & 0xff, 0, ...chunk, (-sum) & 0xff]
      .map((b) => b.toString(16).padStart(2, '0')).join('').toUpperCase());
  }
  lines.push(':00000001FF');
  return lines.join('\n');
};

test('parseIntelHex reads a flat image and its length', () => {
  const img = Uint8Array.from([0x0c, 0x94, 0x34, 0x00, 0xff, 0xff, 0xab]);
  const r = parseIntelHex(hexFor(img));
  assert.deepEqual([...r.bytes.slice(0, 4)], [0x0c, 0x94, 0x34, 0x00]);
  assert.equal(r.length, 7);
});

test('flash writes every byte and read-back matches', async () => {
  const mcu = new MockOptiboot();
  const flasher = new Stk500(mcu, { timeout: 200 });
  const image = Uint8Array.from({ length: 1000 }, (_, i) => (i * 7) & 0xff);
  await flasher.flash(image);
  assert.deepEqual([...mcu.flash.slice(0, image.length)], [...image]);
  const back = await flasher.read(image.length);
  assert.deepEqual([...back], [...image]);
});

test('load address counts words, and pages are 128 bytes', async () => {
  const mcu = new MockOptiboot();
  const flasher = new Stk500(mcu, { timeout: 200 });
  const image = new Uint8Array(300).fill(0x5a);
  await flasher.flash(image);
  assert.equal(mcu.flash[256], 0x5a, 'byte 256 must land at 256');
  assert.equal(mcu.flash[299], 0x5a);
  const syncCount = mcu.log.filter((c) => c === STK.GET_SYNC).length;
  assert.ok(syncCount >= 1, 'synchronises first');
  const pages = mcu.log.filter((c) => c === STK.PROG_PAGE).length;
  assert.equal(pages, Math.ceil(300 / 128), 'one PROG_PAGE per 128-byte page');
});

test('a bootloader that never answers fails loudly', async () => {
  const silent = { write: async () => {}, read: async () => new Uint8Array(0), drain: async () => {} };
  const flasher = new Stk500(silent, { timeout: 20 });
  assert.equal(await flasher.sync(2), false, 'sync reports failure rather than throwing');
  await assert.rejects(() => flasher.enterProgmode(1, 2), /could not sync with the bootloader/);
  await assert.rejects(() => flasher.flash(new Uint8Array(4), () => {}, 1), /flash failed after 1 attempts/);
});

test('a bad INSYNC is reported, not ignored', async () => {
  const rude = { write: async () => {}, read: async () => Uint8Array.from([0x99, STK.OK]), drain: async () => {} };
  const flasher = new Stk500(rude, { timeout: 20 });
  await assert.rejects(() => flasher.command([STK.GET_SYNC]), /bad INSYNC/);
});
