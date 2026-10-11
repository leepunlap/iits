# Wonder Lab — hardware device layer (L2 / L3)

Talk to UCMake **UC-Mind100** and **UC-Mind300** boards *without re-flashing them*, and run block
programs by compiling and uploading them the way UCMake itself does.

Full protocol notes live in [`docs/ucmake-l23-protocol.md`](../docs/ucmake-l23-protocol.md);
the block inventory is in [`docs/ucmake-block-catalogue.md`](../docs/ucmake-block-catalogue.md).

## Two firmwares, two protocols

UCMake leaves one of two things on a board, and they are **not** interchangeable:

| board | firmware | protocol | lab client |
|---|---|---|---|
| UC-Mind100 (L2) | the vendor realtime CLI | `A<function> <args…>` LF+CR @115200 | `ucmake_cli.js` |
| UC-Mind300 (L3) | Firmata 2.5 | Firmata @57600 | `firmata.js` |

`lab.js` detects which one is present (Firmata first, then a reopen at 115200 and a CLI probe) and
returns the matching session, so the pages never branch on protocol themselves.

## Layout

| file | what it is |
|---|---|
| `firmata.js` / `firmata.py` | Firmata client; transports for the browser (Web Serial) and Node |
| `ucmake_cli.js` | the vendor realtime CLI (commands copied from the app's own handlers) |
| `stk500.js` | Optiboot / STK500v1 flasher — AVR flashing straight from the browser |
| `board.js` | lesson-level API: motors, buzzer, servo, LEDs, buttons, sensors |
| `lab.js` | protocol detection, sessions, CLI session |
| `codegen.js` + `codegen.json` | the vendor's **own** 105 block→Arduino code generation, run verbatim |
| `upload.mjs` | CLI: blocks → sketch → compile → flash |
| `build_service.mjs` | HTTP build service used by the page (systemd unit `wonderlab-build`) |
| `lab.html` | hardware control page (connect, motors, display, LEDs, buttons, sensors) |
| `wonderlab.html` | block catalogue + program builder + build/flash |
| `visibility.json` | which blocks each level/class **hides** (everything is present by default) |
| `blocks.json` | machine-readable inventory of all 105 hardware blocks |
| probes / verifiers | the scripts used against real hardware while working this out |

## Live

* https://iits.giftedintl.com/lab-hardware/lab.html
* https://iits.giftedintl.com/lab-hardware/wonderlab.html

## Tests

```
node --test test_firmata.js test_board.js test_lab.js test_ucmake_cli.js test_stk500.js
python3 -m unittest test_firmata
```

## Deploying

Files are copied to `/var/www/iits/lab-hardware/` (served by the `iits.giftedintl.com` catch-all).
The build service runs on `127.0.0.1:18811` as systemd unit `wonderlab-build`, proxied by nginx at
`/lab-hardware/api/`. Media catalogues and assets also live under `libraries/` and `assets/`.
