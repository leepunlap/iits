# Wonder Lab — hardware device layer (L2 / L3)

Talk to UCMake **UC-Mind100** and **UC-Mind300** boards *without re-flashing them*, and run block
programs by compiling and uploading them the way UCMake itself does.

Full protocol notes live in [`docs/ucmake-l23-protocol.md`](../docs/ucmake-l23-protocol.md);
the block inventory is in [`docs/ucmake-block-catalogue.md`](../docs/ucmake-block-catalogue.md).

## One protocol: the vendor text CLI

**Neither kit runs Firmata** — the firmware file is only *named* `arduinoUno.standardFirmata.ino.hex`.
Both speak the vendor's `A`-command text CLI:

```
A<function> <args…>   LF+CR terminated, 115200 8N1
```

Bench-verified on the UC-Mind300 (2026-10-14). The three facts that cost the most time:

1. **Silence means success.** Actuator commands are usually answered with nothing at all; code that
   waits for an acknowledgement looks broken while the hardware works. Only *reads* reply, in text.
2. **A motor is a NUMBER, not a pin.** `A8 1 0 0 <speed> 0` is M1, `A8 2 …` is M2. A pin number there
   is accepted in silence and does nothing.
3. **`A8 10 …` is the differential pair, not "the motor".** With one motor attached it still spins,
   which is exactly how it misled everyone for a day.

| board | protocol | lab client |
|---|---|---|
| UC-Mind300 (L3, AVR) | the vendor CLI — **verified** | `ucmake_cli.js` + `board.js` |
| UC-Mind100 (L2, ESP32) | the vendor CLI — pin map known, **command set unverified** | `ucmake_cli.js` + `board.js` |

`lab.js` returns a `CliSession` for the CLI. A board that answers Firmata has been flashed by hand,
and is **refused by name** (`FirmataUnsupportedError`) rather than driven with commands the shipped
firmware cannot execute. Tone/buzzer is likewise refused: the vendor block is `mechanism: "local"`,
so it compiles into a sketch and has no realtime command.

## Layout

| file | what it is |
|---|---|
| `ucmind300.js` | **the protocol**: every command spelling, its evidence, and the reply parsers |
| `ucmake_cli.js` | the transport-level CLI client + the board profile table |
| `board.js` | lesson-level API: `display` / `motor` / `drive` / `sensor` / `buttons` / `leds` |
| `lab.js` | protocol detection and the session the pages talk to |
| `firmata.js` / `firmata.py` | Firmata client; the Web Serial and Node **transports** the CLI also uses |
| `stk500.js` | Optiboot / STK500v1 flasher — AVR flashing straight from the browser |
| `codegen.js` + `codegen.json` | the vendor's **own** 105 block→Arduino code generation, run verbatim |
| `upload.mjs` | CLI: blocks → sketch → compile → flash. **The only path for tone** |
| `build_service.mjs` | HTTP build service used by the page (systemd unit `wonderlab-build`) |
| `lab.html` | hardware control page (connect, display, motors, LEDs, buttons, sensors) |
| `wonderlab.html` | block catalogue + program builder + build/flash |
| `visibility.json` | which blocks each level/class **hides** (everything is present by default) |
| `blocks.json` | machine-readable inventory of all 105 hardware blocks |
| probes / verifiers | the scripts run by hand against real hardware (`verify_cli.mjs`, `verify_board.mjs`) |

### The lesson API

```js
board.display.show(1234);
board.motor.run(1, 150);        board.motor.stop(1);      // 1 = M1, 2 = M2 — motor NUMBERS
board.drive.turn(-150, 150);    board.drive.stop();       // differential pair
await board.sensor.lineTracker(1);                        // analog 0..1023
await board.sensor.light();                               // built-in, analog
await board.sensor.touch();                               // BINARY -> true/false
await board.buttons.read(1);    await board.buttons.readAll();
board.leds.set(1, true);                                  // the wire level is inverted for you
```

Writes are synchronous-ish and never wait; reads `await` and return `null` when the board stays
silent. Indices are **1-based**, matching the board's own M1/M2 and K1..K4 labels.

## Live

* https://iits.giftedintl.com/lab-hardware/lab.html
* https://iits.giftedintl.com/lab-hardware/wonderlab.html

## Tests

```
node --test test_ucmind300.js test_ucmake_cli.js test_board.js test_lab.js \
             test_firmata.js test_stk500.js
python3 -m unittest test_firmata
node browser_test.mjs http://127.0.0.1:8765/lab.html --proto=cli        # end-to-end, needs a server
```

The browser test needs the directory served over HTTP and a headless Chrome; it stubs `navigator.serial`
so no board is required.

## Deploying

Files are copied to `/var/www/iits/lab-hardware/` (served by the `iits.giftedintl.com` catch-all).
The build service runs on `127.0.0.1:18811` as systemd unit `wonderlab-build`, proxied by nginx at
`/lab-hardware/api/`. Media catalogues and assets also live under `libraries/` and `assets/`.

**Sync every copy** — this directory is the source; the same files are deployed under
`/var/www/iits/lab-hardware/`, and `UCMake-re/lab-device/` is the bench working copy. Patching one of
the others silently reverts.
