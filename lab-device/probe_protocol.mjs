/**
 * Which protocol is the board on this port speaking?
 *
 * UCMake's installation here contains two firmware families under near-identical names: a
 * Firmata family (the lab's device layer drives those) and a 115200 text CLI with Chinese
 * error replies. After UCMake has put a board into "realtime" mode, run this to find out which
 * one it flashed:
 *
 *   node probe_protocol.mjs COM3          (or /dev/cu.usbserial-XXXX)
 */
import { SerialPort } from 'serialport';

const port = process.argv[2] ?? 'COM3';

function open(path, baud) {
  return new Promise((resolve, reject) => {
    const p = new SerialPort({ path, baudRate: baud, autoOpen: false });
    p.open((e) => (e ? reject(e) : resolve(p)));
  });
}
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

function collect(p, ms = 1500) {
  const bytes = [];
  const onData = (c) => { for (const b of c) bytes.push(b); };
  p.on('data', onData);
  return wait(ms).then(() => { p.off('data', onData); return Uint8Array.from(bytes); });
}
const hex = (u8) => Buffer.from(u8).toString('hex');

async function tryFirmata() {
  const p = await open(port, 57600);
  await wait(2200);
  const boot = await collect(p, 600);
  p.write(Buffer.from([0xf9]));                      // REPORT_VERSION
  const ver = await collect(p, 1200);
  let caplen = 0;
  if (ver[0] === 0xf9) {
    p.write(Buffer.from([0xf0, 0x6b, 0xf7]));        // CAPABILITY_QUERY
    caplen = (await collect(p, 1200)).length;
  }
  p.close(() => {});
  return { boot, ver, caplen };
}

async function tryTextCli() {
  const p = await open(port, 115200);
  await wait(2200);
  const boot = await collect(p, 600);
  p.write(Buffer.from('S301\r\n'));
  const r1 = await collect(p, 800);
  p.write(Buffer.from('help\r\n'));
  const r2 = await collect(p, 800);
  p.close(() => {});
  return { boot, r1, r2 };
}

const firmata = await tryFirmata();
const looksFirmata = firmata.ver[0] === 0xf9;
console.log(`port ${port}`);
console.log(`  Firmata @57600 : ${looksFirmata ? 'YES' : 'no'}  version=${hex(firmata.ver.slice(0, 3)) || '-'} capability=${firmata.caplen}B`);

if (looksFirmata) {
  console.log('  => the board runs FIRMATA; drive it with firmata.js (the lab device layer)');
  process.exit(0);
}

const text = await tryTextCli();
const reply = Buffer.from(text.r1).toString('utf8');
const looksCli = /ERROR|错误|参数/.test(reply) || text.r1.length > 0;
console.log(`  text CLI @115200: ${looksCli ? 'YES' : 'no'}  reply=${JSON.stringify(reply.slice(0, 60))}`);
console.log(looksCli
  ? '  => the board runs the VENDOR TEXT CLI; the lab must implement that protocol, not Firmata'
  : '  => neither protocol answered — is the board in a user program, or a different baud?');
