/** Drive a UC-Mind board through the vendor CLI client — real hardware. */
import { openCli, PROFILES } from './ucmake_cli.js';

const port = process.argv[2] ?? 'COM4';
const board = process.argv[3] ?? 'UC-Mind100';
const cli = await openCli(port, PROFILES[board]);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

console.log(`board   : ${board} (${cli.profile.deviceId}) — vendor CLI @115200`);
console.log(`alive   : A1 1 1 1 -> ${JSON.stringify(await cli.query(['A1', 1, 1, 1]))}`);

for (const v of [1234, 5678, 8888]) {
  await cli.display(v);
  console.log(`display : ${cli.log[cli.log.length - 1]}   -> should read ${v}`);
  await sleep(700);
}

if (board === 'UC-Mind100') {
  await cli.motor(10, 100);
  console.log(`motor   : ${cli.log[cli.log.length - 1]}   -> speed 100`);
  await sleep(900);
  await cli.motorStop();
  console.log(`motor   : ${cli.log[cli.log.length - 1]}   -> stopped`);
} else {
  await cli.motor(1, 100);
  console.log(`motor   : ${cli.log[cli.log.length - 1]}`);
  await sleep(900);
  await cli.motorStop();
}

if (board === 'UC-Mind100') {
  // 4-button/4-LED module on port A2 = pin 25
  for (let i = 1; i <= 4; i += 1) await cli.ledButton(25, i, true);
  console.log(`LEDs    : ${cli.log.slice(-4).join(' | ')}`);
}
console.log(`alive   : A1 1 1 1 -> ${JSON.stringify(await cli.query(['A1', 1, 1, 1]))}`);
// NB: no sensor reads here — an unconfigured pin panics the firmware (see L23-PROTOCOL.md §13)
console.log(`commands sent: ${cli.log.length}`);
await cli.close();
