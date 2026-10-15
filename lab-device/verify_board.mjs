/**
 * Exercise the lesson-level board API against a real UC-Mind300 — **run by hand, real hardware**.
 *
 * The automated suite never opens a serial port. This script is the bench companion to
 * `verify_cli.mjs`: that one drives the raw client, this one drives the exact API a lesson uses, so
 * a change to `board.js` can be checked against the physical board without writing a lesson.
 *
 *   node verify_board.mjs /dev/cu.usbserial-1130
 *
 * Watch the board, not the console: the actuator commands are silent on success.
 */
import { SerialPortTransport } from './firmata.js';
import { UCMindBoard } from './board.js';
import { CLI_BAUD } from './ucmake_cli.js';

const port = process.argv[2] ?? '/dev/cu.usbserial-1130';
const t = await SerialPortTransport.open(port, { baudRate: CLI_BAUD });
const board = new UCMindBoard(t);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const say = (what, value) => console.log(`${what.padEnd(20)} ${value}`);

console.log(`board   : ${board.profile.name}  protocol=${board.profile.protocol}  baud=${board.profile.baudRate}`);
console.log('can do  :', JSON.stringify(board.capabilities()));

// ---- sensors: these read, so they print ----
say('light', await board.sensor.light());
say('tracker ch1', await board.sensor.lineTracker(1));
say('tracker ch2', await board.sensor.lineTracker(2));
say('touch', await board.sensor.touch());
say('buttons', JSON.stringify(await board.buttons.readAll()));

// ---- actuators: these are silent; watch the board ----
await board.display.show(1234);
say('display', '1234 sent — read it off the display');
await sleep(700);

await board.motor.run(1, 150);
say('M1', 'running at 150 — M2 must not move');
await sleep(1200);
await board.motor.stop(1);

await board.motor.run(2, 150);
say('M2', 'running at 150 — M1 must not move');
await sleep(1200);
await board.motor.stop(2);

await board.leds.all(true);
say('LEDs', 'all four on');
await sleep(800);
await board.leds.all(false);

await board.drive.turn(-150, 150);
say('turn', 'differential spin — BOTH wheels');
await sleep(1200);
await board.drive.stop();

try {
  await board.buzzer(true);
} catch (err) {
  say('buzzer', `${err.name}: ${err.message.slice(0, 60)}…`);
}

say('commands', `${board.log.length} sent`);
say('log tail', board.log.slice(-3).join(' | '));
await board.close();
