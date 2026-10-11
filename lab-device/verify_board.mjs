/** Exercise the lesson-level board API against a real UC-Mind board. */
import { Firmata, SerialPortTransport } from './firmata.js';
import { UCMindBoard, profileFor } from './board.js';

const port = process.argv[2] ?? 'COM3';
const t = await SerialPortTransport.open(port, { baudRate: 57600 });
const f = new Firmata(t, { timeout: 900 });
const info = await f.identify();
const board = new UCMindBoard(f, profileFor(info));

console.log(`board   : ${board.profile.name}  firmata=${JSON.stringify(info.firmata)}  pins=${info.pins}`);
console.log('can do  :', JSON.stringify(board.capabilities()));

if (board.capabilities().motors) {
  console.log('motor 1 : forward 120 ->', await board.motor(0, 120));
  await new Promise((r) => setTimeout(r, 400));
  console.log('motor 1 : reverse  80 ->', await board.motor(0, -80));
  await new Promise((r) => setTimeout(r, 400));
  await board.motorStop(0);
  console.log('motor 1 : stopped');
}
if (board.capabilities().buzzer) {
  await board.buzzer(true);
  await new Promise((r) => setTimeout(r, 150));
  await board.buzzer(false);
  console.log('buzzer  : pulsed');
}
if (board.capabilities().servo) {
  await board.servo(9, 90);
  console.log('servo   : pin 9 <- 90');
}

const analogPin = board.profile.analogPin;
const values = await board.readAnalog(analogPin, 700);
console.log(`analog  : pin ${analogPin} -> [${values.slice(0, 6)}] (${values.length} reports)`);

const after = await f.identify();
console.log('healthy :', after.firmata !== null, 'firmata=' + JSON.stringify(after.firmata));
await f.close();
