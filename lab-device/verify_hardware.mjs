/** Run the JS device layer against a real UC-Mind board (vendor firmware kept). */
import { Firmata, SerialPortTransport } from './firmata.js';

const port = process.argv[2] ?? 'COM3';
const baud = Number(process.argv[3] ?? 57600);

const t = await SerialPortTransport.open(port, { baudRate: baud });
const f = new Firmata(t, { timeout: 900 });
console.log(`port=${port} baud=${baud}`);

const info = await f.identify();
console.log('IDENTIFY     :', JSON.stringify(info));
console.log('firmware name:', f.firmwareName);
console.log('analog pins  :', info.analogPins.slice(0, 12), `(${info.analogPins.length} mapped)`);

if (info.analogPins.length) {
  const pin = info.analogPins[0];
  await f.reportAnalog(pin, true);
  const ev = await f.poll(1200);
  const vals = ev.filter((e) => e.kind === 'analog').map((e) => e.value);
  console.log(`analog reads : pin ${pin} -> [${vals.slice(0, 8)}]  (${vals.length} reports)`);
}

await f.setPinMode(2, 'input');
await f.reportDigital(0, true);
const ev2 = await f.poll(900);
console.log('digital reads:', JSON.stringify(ev2.filter((e) => e.kind === 'digital').slice(0, 6)));

await f.setPinMode(2, 'output');
await f.digitalWrite(2, 1);
await new Promise((r) => setTimeout(r, 150));
await f.digitalWrite(2, 0);
await f.peripheral(2, 1, 301);          // vendor OneWire peripheral frame
console.log('write path   : pin mode + digital write + OneWire frame sent');

await f.close();
