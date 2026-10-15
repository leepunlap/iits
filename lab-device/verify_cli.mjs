/**
 * Drive a UC-Mind board through the vendor CLI client — **real hardware, run by hand**.
 *
 * Nothing in the automated test suite opens a serial port; this script is for a bench session. It
 * never writes a register: the old `A1 1 1 1` "liveness" probe is a read/WRITE register command and
 * has left a board unresponsive until power-cycled (see `../CLI-PROTOCOL-SOLVED-2026-10-14.md`).
 * Every read here is a plain sensor read, which is a safe liveness check on its own.
 *
 *   node verify_cli.mjs /dev/cu.usbserial-1130 UC-Mind300
 *
 * Remember while watching it: **the write commands are silent on success.** The display lighting up
 * and the motor turning ARE the result. Only the sensor reads print a value.
 */
import { openCli, PROFILES } from './ucmake_cli.js';
import { UCMindBoard } from './board.js';

const port = process.argv[2] ?? '/dev/cu.usbserial-1130';
const name = process.argv[3] ?? 'UC-Mind300';
const cli = await openCli(port, PROFILES[name]);
const board = new UCMindBoard(cli.c, cli.profile);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const say = (what, value) => console.log(`${what.padEnd(24)} ${value}`);

console.log(`board      : ${name} (${cli.profile.deviceId}) — vendor CLI @115200`);
console.log(`verified   : ${cli.profile.verified === true ? 'yes' : 'NO — this profile is unverified'}`);
say('capabilities', JSON.stringify(board.capabilities()));

// A read is a safe liveness check; a write is not a probe.
say('light (A16 21 0)', await cli.readLight());
say('tracker ch1 (A9 16 2 2 1)', await cli.readLineTracker(1));
say('tracker ch2 (A9 16 2 2 2)', await cli.readLineTracker(2));
say('touch (A20 15 0)', await cli.readTouch());
say('buttons (K1..K4)', JSON.stringify(await cli.readButtons()));

if (name === 'UC-Mind300') {
  for (const v of [1234, 5678, 8888]) {
    await board.display.show(v);
    console.log(`display    : ${v}  <- should be readable on the display (the command is silent)`);
    await sleep(700);
  }

  await board.motor.run(1, 150);
  console.log('motor M1   : A8 1 0 0 150 0  <- M1 only; M2 must NOT move');
  await sleep(1200);
  await board.motor.stop(1);
  console.log('motor M1   : A8 1 0 0 0 0    <- stopped');

  await board.motor.run(2, 150);
  console.log('motor M2   : A8 2 0 0 150 0  <- M2 only; M1 must NOT move');
  await sleep(1200);
  await board.motor.stop(2);
  console.log('motor M2   : A8 2 0 0 0 0    <- stopped');

  // ⚠️ Watch this one with BOTH wheels on the ground: `A8 10 …` is the differential pair, so unlike
  // the single-motor commands above it drives or turns BOTH motors. See DIFF in ucmind300.js.
  await board.drive.turn(-150, 150);
  console.log('turn       : A8 10 2 0 -150 150  <- opposite wheels: spins on the spot');
  await sleep(1200);
  await board.drive.stop();
  console.log('turn       : A8 10 3 0 0 0       <- stop all');

  for (let i = 1; i <= 4; i += 1) { await board.leds.set(i, true); await sleep(150); }
  console.log('LEDs       : A3 19 2 <1..4> 0   <- all four on (the level is inverted on the wire)');
  await sleep(800);
  for (let i = 1; i <= 4; i += 1) await board.leds.set(i, false);
  console.log('LEDs       : off');
}

try {
  await board.buzzer(true);
} catch (err) {
  console.log(`buzzer     : ${err.name} — ${err.message}`);
}

console.log(`commands sent: ${cli.log.length}`);
await cli.close();
