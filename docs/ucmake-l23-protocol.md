# L2/L3 board protocol — driving the UC-Mind boards while they keep vendor firmware

Recovered and verified 2026-10-11. Goal: the L2/L3 Wonder Lab drives UC-Mind100/300 boards that
KEEP the UCMake vendor firmware, so students and teachers never re-flash a board.

**Headline: the boards run standard Firmata at 57600 8N1. No custom protocol needs
reverse-engineering.** The lab needs a Firmata client plus (for the ESP32 boards) the vendor's
OneWire peripheral payloads, both of which are now implemented and verified on real hardware.

---

## 1. Verified board identities

| Board | deviceId | Firmata | Baud | Firmware name reported | Pins | Analog pins |
|---|---|---|---|---|---|---|
| **UC-Mind300** | `arduinoUno` | **2.5** | 57600 | `sketch_nov16a.ino` | 20 | 1 (pin 14) |
| **UC-Mind100** | `arduinoEsp32Min` | **2.7** | 57600 | `C:\UCMakeDesktop\data\link\arduino\esp32_esp32_esp32\code\code.ino` | 40 | 7 (0,1,2,9,18,22,24) |

Both measured live on 2026-10-11 through the lab's own client (`lab-device/firmata.py`), not with
raw frames, so the parser is exercised against real board data.

The pin-count and version difference is enough for the lab to auto-detect which kit is plugged in
(20-pin Firmata 2.5 = L3/300, 40-pin Firmata 2.7 = L2/100).

Note the 100's firmware name: it is a UCMake-built **link** sketch
(`data\link\arduino\esp32_esp32_esp32\code\code.ino`), i.e. UCMake compiles and flashes its own
Firmata sketch at realtime time.

---

## 2. The firmware images — naming trap

UCMake's `firmwares/arduino/` holds two families under near-identical names. **Only the
`11`-prefixed files are the Firmata realtime firmware.**

| Board | ✅ Correct image (Firmata) | ❌ Decoy (115200 text CLI, NOT Firmata) |
|---|---|---|
| UC-Mind300 | `11arduinoUno.standardFirmata.ino.hex` (24,136 B) | `arduinoUno.standardFirmata.ino.hex` (18,688 B) |
| UC-Mind100 | `11arduinoESP32.standardFirmata.ino.bin` (267,600 B) | `arduinoESP32Min.standardFirmata.ino.bin` (223,808 B) |

The decoys are a port-based text interpreter (`A1`…`A20`, `ERROR 参数不足`, `ERROR 未知指令`), silent
on boot after a one-off `F9 01 02`, and they ignore every Firmata request. They are the reason
`README-P0.md` section 6 concluded "AVR realtime is not Firmata" — that conclusion came from
flashing the decoy and is **wrong**.

Analogous decoys exist for the other boards; the `11`-prefixed sibling is the one to use.

### Flashing (one-off, done by staff — never in class)

- UC-Mind300: UCMake's own avrdude, `-p m328p -c arduino -P <port> -b 115200 -U flash:w:<hex>:i`
- UC-Mind100: esptool, `write_flash 0x8000 <partitions>.bin 0x10000 <image>.bin`
  (partition table: nvs 0x9000, otadata 0xe000, app0 **0x10000**, app1 0x150000, spiffs 0x290000)

---

## 3. How the app drives hardware

**(a) Direct pins** — `SET_PIN_MODE`, `DIGITAL_MESSAGE`, `ANALOG_MESSAGE`, `ANALOG_READ`.
Used by the AVR board (the Uno class extends a base Arduino class whose constants are pin names).

**(b) OneWire smart-peripheral SysEx** — used by the ESP32 boards (100/500), whose peripherals are
1-wire modules addressed by port. Every block calls `this._firmata.sendOneWireWrite(pin, 0, payload)`.

```
F0 73 3C <pin> 00 x16 <payload> F7
payload = [func, 0, ...ASCII args]      'A'=65 negative marker   'B'=66 argument separator
```

Function codes read from the app's ESP32 peripheral class (mapping inferred from the app source,
not yet confirmed against hardware):

| func | block | | func | block |
|---|---|---|---|---|
| 1 | `setFourDigitDisplay` | | 14 | — |
| 3 | `setDcMotor` | | 16 | — |
| 4 | `setDcMotorMove` | | 17 | — |
| 5 | `setDcMotorMoveLR` | | 20 | RGB LED |
| 6 | `setDcMotorStop` | | 21 | `setUltrasonicLed` |
| 7 | `setDcMotorMode` | | 23, 24 | — |

Example — show `301` on the 4-digit display: `F0 73 3C <pin> 00 x16 01 00 33 30 31 F7`.

Watch out: a second peripheral implementation in the same bundle uses a *different* constant table
(`p=1, A=4, h=5, m=6, f=14, b=15, …`), so these codes are per device package, not universal.

---

## 4. The lab device layer — `lab-device/`

Two implementations of the same protocol, both dependency-free at the protocol level:

| File | Purpose |
|---|---|
| `firmata.js` | **The lab's client.** Browser (Web Serial, `WebSerialTransport`) and Node (`SerialPortTransport`); frame builders are pure and synchronous so they are testable without I/O |
| `firmata.py` | Python reference implementation (same protocol, same frames) |
| `test_firmata.js` | 14 Node tests: scripted mock + a Web-Serial-shaped fake port — no hardware needed |
| `test_firmata.py` | 18 Python tests against a scripted simulator — no hardware needed |
| `verify_hardware.js(.py)` | Runs the layer against a real board and prints what it found |
| `probe_cli.py` | Probes the **vendor CLI** protocol on a port (per-board reset: `--reset=dtr\|rts`) |
| `probe_protocol.mjs` | Reports whether a board speaks Firmata@57600 or the CLI@115200 |
| `board.js` / `test_board.js` | Lesson-level board API (motor/buzzer/servo/digital/analog) + tests |
| `board_map.py` | Prints a board's pin/mode map and analog channel mapping |
| `verify_board.mjs`, `verify_pwm.py` | Exercise the board API / PWM path on real hardware |
| `lab.js` / `test_lab.js` | Lab session layer (transport-injectable) + tests |
| `lab.html` / `check_lab_page.mjs` | The lab page and its static wiring check |
| `browser_test.mjs` | Headless-Chrome end-to-end test of the page (stubbed Web Serial) |
| `lesson_demo.mjs` | A curriculum-shaped sensor→actuator loop on real hardware |
| `ucmake_cli_probe.py` | Sends the vendor realtime CLI commands UCMake itself uses |
| `ucmake_cli.js` / `test_ucmake_cli.js` | The vendor CLI protocol client + tests |
| `verify_cli.mjs` | Drives a real board through the CLI client |
| `codegen.js` / `codegen.json` | The vendor's own 105 block→Arduino functions + shim |
| `upload.mjs` / `program.example.json` | Upload backend: blocks → sketch → compile → flash |
| `build_service.mjs` | Build service (deployed on the NUC under systemd, port 18811) |
| `wonderlab.html` / `visibility.json` / `blocks.json` | One lab, all blocks, hidden per class |

```sh
node --test test_firmata.js          # 14 tests
python3 -m unittest test_firmata     # 18 tests
node verify_hardware.mjs COM3 57600  # real board (Node)
```

Coverage: `REPORT_VERSION`, `REPORT_FIRMWARE`, `CAPABILITY_QUERY`, `ANALOG_MAPPING_QUERY`,
`SET_PIN_MODE`, `DIGITAL_MESSAGE`, `ANALOG_MESSAGE`, `REPORT_ANALOG`, `REPORT_DIGITAL`,
`SET_SAMPLING_INTERVAL`, the vendor OneWire SysEx write, and `identify()` — which returns the
board level from the pin count (40 pins ⇒ **L2**/UC-Mind100, 20 pins ⇒ **L3**/UC-Mind300).

### Verification matrix (2026-10-11, real hardware)

| Client | Board | Result |
|---|---|---|
| `firmata.js` (Node) | UC-Mind300 @ COM3 | `firmata [2,5]`, `sketch_nov16a.ino`, 20 pins, level **L3**, **analog A0 read**, digital reports parsed |
| `firmata.py` | UC-Mind300 @ COM3 | `firmata (2,5)`, 20 pins, **analog A0 read**, digital reports parsed |
| `firmata.py` | UC-Mind100 @ macmini | `firmata (2,7)`, 40 pins, 7 analog pins, **analog read** |

Unit tests: 14/14 (Node) and 18/18 (Python), on both machines. The JS and Python clients emit
**byte-identical** frame streams (132 bytes compared across 13 operations), so the JS client is
tied to the same byte-level behaviour that was validated on the boards.

### Three bugs found by hardware verification (worth knowing)

**1. `identify()` read the version too early.** It returned the value captured when
`reportVersion()` was called. A board that resets when the port opens (the AVR's DTR auto-reset)
is still inside Optiboot then, so the first request is swallowed and `version` came back `null` —
reproducibly, on the 300. Fix in **both** clients: `reportVersion()` retries once, and `identify()`
reads state *after* all queries, because a late boot banner carries the version report too. Settle
time on open raised to 2.2 s to cover Optiboot's ~1 s.

**2. Analog reporting addressed the pin, not the channel.** Firmata's `REPORT_ANALOG` takes the
**analog channel** (0–15), not the digital pin. On the UC-Mind100 the first analog pin happens to
be channel 0, so it worked by luck; on the **UC-Mind300** the only analog pin is **14** (channel
0), so the client was enabling channel 14 and got **zero readings, silently**. That would have
broken every sensor lesson in L2 (感測控制 = sensing and control). Fix in both clients:
`reportAnalog()` resolves the channel through the analog mapping, and analog reports are resolved
back to a digital pin for the caller. Verified: the 300 went from 0 readings to reading A0.

**3. The two clients disagreed on timeout units.** `firmata.js` takes milliseconds; `firmata.py`
took *seconds* under the same `timeout` name. Copying `timeout=700` from the JS convention into
the Python client produced a **700-second** drain — it looked exactly like a wedged serial port.
Both implementations now take **milliseconds**, and the Python docstring says so.

All three were invisible to unit tests and to the spec — only real boards (and real cross-language
use) exposed them.

### Peripheral frames: robustness check

The vendor OneWire frames were sent to the live UC-Mind100 (display on PORT_D/pin 27, motor on
PORT_A/pin 14, ultrasonic LED on PORT_B/pin 5) using the function codes in section 3. The board
answered `(2,7)` / 40 pins both before and after — so the frames are accepted and leave the
firmware healthy. What is still unproven is their **physical effect**: no display or motor was
attached to observe.

### Not yet done

1. **Run `WebSerialTransport` in a real browser.** The Node path is verified on hardware; the
   Web Serial path shares all the protocol code but has only been exercised for frame building.
2. **Peripheral actuation.** No display/motor was attached, so vendor OneWire frames were sent but
   their physical effect is unobserved, and the function-code table is still app-derived.
3. **Lesson integration + secure context.** Web Serial needs a secure context: `http://localhost`
   is fine, `http://<nuc-host>` is not — so the lesson pages need HTTPS, a localhost helper, or a
   local app.

---

## 5. Firmware provenance — the contradiction (RESOLVED, see section 7b)

While checking what else the boards can do, the firmware story stopped adding up.

**What the app says it wants**

- `openblock-link` device packages for the UC-Mind boards (`arduinoEsp32Min`, `arduinoUno`, …)
  **extend the Firmata base class**, and the serial config for those packages is **57600**.
- `main.js` copies firmware from the app's own `firmwares/` directory — there is **no download**
  (`download-github-release` is only a transitive dependency; the only URLs in main.js are
  telemetry and ajv schemas).
- So the app expects **Firmata at 57600** and flashes a file from `firmwares/`.

**What the bundled files actually are**

| File (named by the app) | Reality |
|---|---|
| `arduinoUno.standardFirmata.ino.hex` | 115200 **text CLI** (Chinese errors), not Firmata |
| `arduinoESP32Min.standardFirmata.ino.bin` | 115200 **text CLI**, not Firmata |
| `11arduinoUno.standardFirmata.ino.hex` | ✅ genuine **StandardFirmata 2.5** @57600, full pin modes |
| `11arduinoESP32.standardFirmata.ino.bin` | ⚠️ **Firmata 2.7** @57600 but **minimal**: advertises only
  analog + pwm, ignores every OneWire SysEx request |

Plus `… - 副本.hex/bin` copies — "副本" is *copy*. Files have clearly been added/swapped by hand in
this installation.

**The contradiction**: the app names the text-CLI files but speaks Firmata; the `11…` files are
Firmata but at least the ESP32 one lacks the OneWire extension that the app's peripheral blocks
(`sendOneWireWrite`) require. So **neither bundled ESP32 image is demonstrably the firmware UCMake
puts on a board in realtime mode.**

Measured capability maps:

```
UC-Mind300  20 pins  modes 00 INPUT 01 OUTPUT 02 ANALOG 03 PWM 04 SERVO 06 I2C 08 STEPPER 0B PULLUP  → full StandardFirmata 2.5
UC-Mind100  40 pins  modes 02 ANALOG 03 PWM only, no 07 ONEWIRE                                  → minimal build
```

**The experiment that settles it** (needs a human, ~2 minutes):

1. On the ThinkPad, open UCMakeDesktop and connect the UC-Mind100 in **realtime** mode.
2. Let it flash whatever it flashes; leave it connected.
3. Then run `verify_hardware.mjs <port>` from `lab-device/` and read the result:
   - answers Firmata at 57600 with OneWire (mode 07) → the realtime firmware is a *different*,
     fuller Firmata build, and we should capture it;
   - answers the 115200 text CLI → the vendor protocol is the text CLI, and the lab must implement
     **that**, not Firmata.

Either outcome is fine — we just need to know which. *(Settled in 7b: it is Firmata, from a UCMake-compiled link sketch.)*

## 7. (SUPERSEDED — see section 7b) the text CLI under the Firmata name

The contradiction in section 5 is now settled — by mounting the **pristine installer DMG**
(`_reorg/UCMake-Desktop-INT_v4.2.9_mac_arm64.dmg`, never previously opened) and comparing.

**The installer genuinely ships the text CLI under the Firmata-sounding name:**

| Installer file | Bytes | Content |
|---|---|---|
| `arduinoUno.standardFirmata.ino.hex` | 18,688 flash | **vendor text CLI** (md5 `a5e62c9e…`) |
| `arduinoESP32Min.standardFirmata.ino.bin` | 223,808 | **vendor text CLI** |
| `arduinoUno.standardFirmata.ino - 副本.hex` | 17,278 | vendor CLI (copy) |
| `11arduinoUno.standardFirmata.ino.hex` | 24,136 | Firmata 2.5 |
| `11arduinoESP32.standardFirmata.ino.bin` | 267,600 | Firmata 2.7 (minimal) |
| `arduinoMega2560`, `arduinoUnoUltra` | — | genuine community Firmata |

The ThinkPad's `arduinoUno.standardFirmata.ino.hex` decodes to a **byte-identical binary** to the
installer's, so the earlier test was on the right firmware. The `副本` copies and the `11…` files
are the vendor's own bundling, not user tampering.

**So UCMake's realtime firmware for the UC-Mind boards is the text CLI**, while the app's device
packages are Firmata-based (they construct `_firmata`, wait for its `ready` event, and fail with
`connectFirmataTimeout` = "Timeout when try to connect firmata, please download the firmware
first"). **That is an inconsistency inside the vendor's own build**, and a plausible explanation
for why UC-Mind realtime mode was never usable. The `11…` files are what actually speak Firmata.

Tested: no text handshake switches the CLI into Firmata (tried `FIRMATA`, `firmata`, `LINK`,
`link`, `VER`, `HELLO`, `AT`, `START`, `MODE`; `F9` answered nothing at either baud).

### The vendor CLI protocol — first recovered pieces

Both boards, now flashed with the installer's vendor firmware, answer **identically**:

| Send | Reply |
|---|---|
| `A1 1 1 1` | `180.00` |
| `A2 1 1` | `0.00` |
| `S301` | `ERROR 参数不足` (known verb, insufficient parameters) |
| `help` | `ERROR 参数不足` |
| `B1 100` | `ERROR 未知指令` (unknown verb) |
| `M1 1` | `ERROR 未知指令` |

So: 115200 8N1, CRLF-terminated, **port-addressed** (`A1`, `A2`, … up to at least A13; `A14` is an
unknown port), verbs are single letters, replies are either a numeric value or `ERROR …`.
The AVR build additionally emits `F9 01 02` once at boot.

**Hazard found:** malformed arguments **crash the ESP32** (`Guru Meditation Error: Core 0 panic`).
`A1 100 100 100`, `A2 100 1` and similar killed it; the lab must validate arguments and never
forward raw student input.

### Tools

- `lab-device/probe_cli.py` — probes the CLI on a port and prints replies.
  **Reset method matters**: `--reset=dtr` for the AVR (DTR resets it), `--reset=rts` for the ESP32
  (DTR is GPIO0 there — pulsing it drops the chip into download mode and it goes silent).
- `lab-device/probe_protocol.mjs` — reports which of the two protocols (Firmata@57600 vs
  CLI@115200) a board is speaking.

### Consequence for the objective

The lab's target protocol is the **vendor CLI**, not Firmata. The Firmata client built in
sections 4–6 stays valid for boards flashed with the `11…` images, but for the boards to "keep the
vendor firmware" the lab must implement the CLI. Next: recover the full CLI grammar
(verbs, port map, argument counts, reply formats) — safely, given the crash hazard.

## 7b. CORRECTED 2026-10-11: the realtime firmware is a compiled **link sketch** (Firmata)

Section 7 went one step too far. The decisive clue was sitting in plain sight: the UC-Mind100
reports its firmware name as

```
C:\UCMakeDesktop\data\link\arduino\esp32_esp32_esp32\code\code.ino
```

**`data\link\…` — a UCMake *link* sketch.** So the realtime path is:

1. UCMake **compiles its own link sketch** with arduino-cli (`CacheWarmer` in `main.log` shows it
   pre-compiling for both boards: "2 board(s) to warm: Arduino Uno, ESP32", using the UCMake,
   ServoESP32, BLE and Wire libraries), and
2. flashes that build, then
3. talks **Firmata** to it — matching its device packages.

The `11arduinoUno…` / `11arduinoESP32…` images **are cached builds of that link sketch**: their
embedded firmware name is the `data\link\…\code.ino` path. Verified byte-identical between the
installer DMG and the ThinkPad copies, and both boards now run them and identify as Firmata.

The plain-named `*.standardFirmata.ino.*` files are therefore a **different firmware** (a 115200
port-register text console, most likely a factory/debug interface) that the vendor bundles
alongside — not what realtime mode uses.

**Both boards are now flashed with the installer's link/Firmata images and re-verified:**

```
UC-Mind300  Firmata 2.5  sketch_nov16a.ino            20 pins  analog A0 read OK
UC-Mind100  Firmata 2.7  data\link\…\code.ino        40 pins  analog read OK
```

### The text console, for the record

Sweeping it (32 commands, AVR) showed it is a **register-addressed debug console**, not the
realtime protocol:

| Send | Reply |
|---|---|
| `A1 <reg 0-2> 1 1` | `180.00` (float) |
| `A2 <reg 0-7> 1 1` | `0.00` (float) |
| `A3 <reg 0-2> 1 1` | `0` (integer) |
| `A4 <reg 0-7> 1 1` | invalid |

Ports are `A0`–`A20` (21 entries in the string table). Its message table also contains `nan`,
`inf`, `ovf`, the axis letters `x y z`, and `白平衡` (white balance).

**10 of 32 commands crashed the board** — this console has no argument validation. It is not a
safe interface to expose to students, and it is not the interface the lab needs.

### Still open

The UC-Mind100's link build is **minimal** (analog + PWM only, no OneWire), so the vendor OneWire
peripheral blocks would not work on it. A **full** link build requires UCMake to compile one
(needs its GUI + toolchain). Capturing that build is the remaining firmware task; the lab device
layer already drives everything Firmata offers.

## 9. What the boards actually expose — and the lesson-level API

### Measured capability matrix (2026-10-11, `board_map.py`)

| | UC-Mind300 | UC-Mind100 |
|---|---|---|
| Firmata | 2.5 | 2.7 |
| pins | 20 | 40 |
| digital in/out/pullup | 2–19 | **none** |
| PWM | 3, 5, 6, 9, 10, 11 | 27 pins (0,2,4,5,12–23,25–27,32–36) |
| servo | 2–19 | none |
| analog in | 14–19 (A0–A5), channels 0–5 | 16 pins, channels as mapped |
| I2C | 18, 19 | none |
| **OneWire (mode 0x07)** | **no** | **no** |

Vendor pin map (from `UCMakeYAI.h`), i.e. where the kit's parts sit:

| | UC-Mind300 | UC-Mind100 |
|---|---|---|
| motors | M1 = PWM 10 + dir 9, M2 = PWM 5 + dir 6 (**plain pins**) | via OneWire on pin 32 |
| buzzer | pin 7 | — |
| ports A/B/C/D | 19 / 18 / 16 / 15 | 14 / 5 / 25 / 27 |

**The limitation that matters:** neither vendor build advertises Firmata's OneWire mode, so the
kit's **smart modules (4-digit display, 4-button module) are not reachable over Firmata**. On the
300 that is partly survivable (motors and buzzer are plain pins); on the **100 the motors are
OneWire modules**, so the vendor link build cannot drive them.

### `lab-device/board.js` — the lesson-level API

Sits on the Firmata layer and speaks the lab's vocabulary, refusing what a board cannot do rather
than sending frames into the void:

```js
board.capabilities()          // what this board can do -> the lab greys out the rest
await board.motor(0, 120)     // AVR: PWM 10 + dir 9, sign = direction
await board.motorStop(0)
await board.buzzer(true)      // pin 7
await board.servo(9, 90)
await board.digitalOut(pin, on)
await board.readAnalog(14, 700)
```

Profiles are selected from the reported pin count (20 ⇒ UC-Mind300, 40 ⇒ UC-Mind100), so one code
path serves L3 and L2.

### Verified on real hardware

```
UC-Mind300  can do: motors=2 buzzer=yes servo=yes digitalOut=yes smartModules=no
            motor 1 forward 120 / reverse -80 / stop   OK
            buzzer pulsed · servo pin 9 <- 90 · analog pin 14 -> [0,0]   OK
            still healthy afterwards: firmata [2,5]
UC-Mind100  pwm pins 27 · analog pins 16
            PWM pin 0 <- 128 then 0 · analog pin 0 -> [0]   OK
            still healthy: firmata (2,7)
```

### Third bug found (analog mapping parse)

`ANALOG_MAPPING_RESPONSE` is one entry **per digital pin** giving that pin's channel (0x7F = not
analog-capable). The parser treated 0x7F as a *separator*, so the UC-Mind300 collapsed to a single
bogus entry `{14: 5}` instead of `{14:0, 15:1, 16:2, 17:3, 18:4, 19:5}`. Fixed in both clients and
pinned with regression tests built from the real board payloads.

## 11. Integration: the lab session and page

`lab-device/lab.js` is the seam between the lab UI and the hardware. It is **transport-injectable**,
so the whole session runs headless in tests:

```js
import { connectBoard } from './lab.js';
const s = await connectBoard();          // asks for a Web Serial port
// or: await connectBoard({ transport: mock })   → testable without a browser
s.capabilities                           // what to show/enable in the UI
await s.motor(0, 120); await s.buzzer(true); await s.servo(9, 90)
await s.sampleAnalog(s.board.profile.analogPin, 400)
```

`lab.html` is a dependency-free page: connect/disconnect, a board readout (board · level · Firmata ·
pins), motor sliders, buzzer/servo controls and an analog readout — and it **greys out what the
board cannot do** from `capabilities()`, so an L2 kit never shows motor controls it cannot honour.

`check_lab_page.mjs` statically verifies the page wiring (every `getElementById` has a matching id,
every module import resolves, the inline module parses). The only part that needs a human is the
Web Serial port grant itself.

Test counts this round: **28 JS** (15 firmata + 8 board + 5 lab) and **20 Python**.

### Where the firmware actually comes from

`node_modules/openblock-link/script/download-firmwares.js` settles it:

```js
const user = 'openblockcc'; const repo = 'openblock-firmwares';
downloadRelease(user, repo, outputdir, ...)      // → ./firmwares
```

Firmware is downloaded at **build** time from that repo's releases (which is why nothing in the app
runtime references a URL). Checking the upstream release:

| Release | Assets |
|---|---|
| v1.5.0 | `arduino/arduinoUno.hex`, `arduinoUnoUltra.hex`, `arduinoMega2560.hex`, microPython images — **no ESP32 image** |

and upstream's `arduinoUno.hex` (25,320 bytes flash) is a different, newer build from either UCMake
Uno image. So **the ESP32 images in UCMake's bundle are vendor additions, and no fuller ESP32
Firmata is available upstream.** That closes the last avenue for fixing the UC-Mind100's missing
OneWire support without the vendor's own link build.

### Verified in a real browser (headless Chrome, via CDP)

`browser_test.mjs` drives `lab.html` in **real Chrome**: it injects a stub `navigator.serial`
*before the page's modules load* (a real port grant needs a human click, which is the only part
stubbed), then clicks connect and inspects the live DOM and the bytes reaching the fake board.

```
node browser_test.mjs http://127.0.0.1:8765/lab.html --pins=20   # UC-Mind300 profile
✔ board readout identifies the UC-Mind300   "UC-Mind300 L3 Firmata 2.5 20 pins"
✔ motor controls visible on the L3 kit
✔ motor slider drove the expected PWM + direction frames  f4 0a 03 f4 09 01 91 02 00 ea 78 00
    = SET_PIN_MODE(10,pwm) · SET_PIN_MODE(9,output) · DIGITAL_MESSAGE(port1,0x02) · ANALOG_MESSAGE(10,120)
✔ no error surfaced in the status line   "已連接：可控制馬達。"

node browser_test.mjs http://127.0.0.1:8765/lab.html --pins=40   # UC-Mind100 profile
✔ board readout identifies the UC-Mind100   "UC-Mind100 L2 Firmata 2.5 40 pins"
✔ motor controls hidden on the L2 kit
✔ status explains the board is analog/PWM only   "已連接：此固件只提供類比輸入與 PWM。"
```

Both profiles pass repeatedly (deterministic — the page sets `window.__labReady` once its module
has wired up, which the test waits for; clicking before that is a race the test previously hit).

Two harness bugs were worth the trouble: the CDP WebSocket needs `--remote-allow-origins=*`, and a
nested `${...}` in the stub template made the stub throw, so the page silently fell through to the
**real** `navigator.serial` and correctly refused with *"Must be handling a user gesture"* — a good
sign that the page does use the genuine Web Serial API when the stub is absent.

### A curriculum-shaped activity on real hardware

Most L2/L3 lessons reduce to: read a sensor, decide, drive an actuator. That shape runs on the
vendor firmware through the board API alone:

```
$ node lesson_demo.mjs COM3
board UC-Mind300  firmata=[2,5]  sensor pin 14
rule: sensor < 200  ->  motor 1 forward 150, else stop
  t0  sensor=    0  ->  motor forward 150
  t1  sensor=    0  ->  motor forward 150
  t2  sensor=    0  ->  motor forward 150
  t3  sensor=    0  ->  motor forward 150
decisions: 4 run / 0 stop · board still healthy: true
```

(sensor reads 0 because A0 is unconnected on the bench — the loop itself is what is being shown.)

### Deployed

Served at **https://iits.giftedintl.com/lab-hardware/lab.html** (public path on the existing
`iits.giftedintl.com` vhost, which already has a catch-all `location /` for `/var/www/iits` — no
nginx change was needed). Four files only: `lab.html`, `lab.js`, `board.js`, `firmata.js`.
Deployed bytes md5-match the tested copies; verified over HTTPS from both the LAN address and the
public edge (1.64.96.110) with correct `application/javascript` MIME types.

**The owner has since connected real boards through Chrome from this page on both levels** — the
last unverified step:

* **UC-Mind300** on the ThinkPad → `UC-Mind300 · L3 · Firmata 2.5 · 20 pins`, motor controls shown.
* **UC-Mind100** on the macmini → `UC-Mind100 · L2 · Firmata 2.7 · 40 pins`, motor controls
  correctly absent, status 已連接：此固件只提供類比輸入與 PWM。

Both levels are therefore confirmed end to end on real hardware. (While the owner's browser held the
port, `lsof` showed `Google Chrome` owning `/dev/cu.usbserial-1130` — the Web Serial claim is
exclusive, which is why a concurrent probe could not open it.)

Practical note for a two-board bench: with both kits plugged into one machine the Web Serial chooser
lists two ports, and picking the wrong one silently gives the *other* level's profile. The board
readout on the page is the check — `UC-Mind300 · L3 · 2.5 · 20 pins` vs
`UC-Mind100 · L2 · 2.7 · 40 pins`.

### What "verified" covers, and what it does not

| Layer | How verified |
|---|---|
| Firmata frames + parsing | real boards, both (rounds 2–3) |
| Board API (motor/buzzer/servo/analog) | real board, UC-Mind300 (round 7) |
| PWM/analog path | real board, UC-Mind100 (round 7) |
| Lab session + page + capability gating | real Chrome with a stubbed port (above) |
| OS-level Web Serial port grant | **confirmed by the owner on both boards**, 2026-10-11: UC-Mind300 on the ThinkPad (L3 profile) and UC-Mind100 on the macmini (L2 profile, `Firmata 2.7 · 40 pins`, motor controls correctly absent) |

## 13. CORRECTED AGAIN 2026-10-11: the vendor realtime protocol *is* the text CLI

Section 7 was right and section 7b was wrong to dismiss it. The evidence is now conclusive, because
the app's own runtime handlers were read out of `vendors.js`:

```js
espMinSetDcMotor(e)      { this._peripheral.send(`A8 ${e.PIN} 0 0 ${e.OUT} 0\n\r`) }
espMinSetDcMotorStop(e)  { this._peripheral.send("A8 10 3 0 0 0\n\r") }
espSetFourDigitDisplay(e){ this._peripheral.send(`A10 ${e.PIN} ${e.OUT}\n\r`) }
esp32ReadUltrasonicDistanceCm(e) { this._peripheral.send(`A5 ${e.PIN} 4\n\r`) }
```

**Grammar: `A<function> <args…>` terminated with LF+CR, at 115200 8N1.** The `A1`…`A20` null-terminated
strings in the firmware are the **function numbers**, not ports — which is why earlier black-box
probing produced confusing results. Writes are fire-and-forget (no reply); reads reply.

### Function map (from every `.send()` in the app, 74 methods)

| Fn | ESP32-min (UC-Mind100) | AVR / other |
|---|---|---|
| A1 | — | gyro `A1 <n> <index> <axis>` |
| A2 | — | joystick |
| A3 | LED button `A3 <pin> 1 <level>` / `A3 <pin> 2 <index> …` | same |
| A4 | colour sensor (wb / set / read) | same |
| A5 | ultrasonic `A5 <pin> 4` | 360 servo |
| A6 | 360 servo | — |
| A7 | BLE on/off | — |
| **A8** | **DC motor** `A8 <pin> 0 0 <speed> 0`, stop `A8 10 3 0 0 0`, 36-encoder motor | — |
| A9 | line follower (1/2/5-way, contrast) | same |
| A10 | 4-digit display `A10 <pin> <value>` | same |
| A11 | humidity | same |
| A12 | electromagnet | same |
| A13 | — | compass |
| A14 | — | gesture |
| A15 | — | sound sensor `A15 17 0` |
| A16 | big-board ultrasonic/humidity | light sensor `A16 21 0` |
| **A17** | — | DC motor (non-min boards) `A17 <pin> 0 0 <speed> 0` |
| A18 | — | rain drop |
| A19 | — | moisture |
| A20 | — | PIR / touch |

### Verified on real hardware (UC-Mind100, COM4, 2026-10-11)

The owner ran UCMake's motor block on the 100, which **flashed** the CLI firmware first
(`%APPDATA%\UCMake\logs\upload.log`: two uploads to COM4, `fqbn=esp32:esp32:esp32:UploadSpeed=921600`,
and `arduino\esp32_esp32_esp32\testusercode\auth.ino.bin`, 227,952 B). The board then answered the CLI.

Sending UCMake's own command works:

```
A1 1 1 1          -> 180.00          (read; proves the board is alive)
A8 10 0 0 100 0   -> (silent)        motor on pin 10, speed 100  — exactly the sb3's block
A1 1 1 1          -> 180.00          board survived
A8 10 3 0 0 0     -> (silent)        stop
A1 1 1 1          -> 180.00
```

**So the lab CAN drive the UC-Mind100's motors after all** — over the vendor CLI, on the very
firmware UCMake itself uses. This supersedes the "motors unreachable on the 100" conclusion in
sections 7b/9, which was true only of the *Firmata link* image, not of the vendor's realtime path.

The `.sb3` the owner saved (`OpenBlock Project.sb3`) confirms the block vocabulary:

| opcode | fields |
|---|---|
| `arduino_dcMotor_espMinSetDcMotor` | `PIN: "10"`, `OUT: 100` |
| `arduino_digitDisplay_espSetFourDigitDisplay` | `PIN: "27"`, `OUT: 500` |

with `device: "arduinoEsp32Min"`, `deviceType: "arduino"`, `programMode: "realtime"`.

### `lab-device/ucmake_cli.js` — the CLI implemented in the lab device layer

The recovered protocol, implemented and driving real hardware. Every template is copied from the
app's own handlers, so the lab sends byte-for-byte what UCMake sends:

```js
import { openCli, PROFILES } from './ucmake_cli.js';
const cli = await openCli('COM4', PROFILES['UC-Mind100']);   // 115200 8N1
await cli.display(8888);          // A10 27 8888
await cli.motor(10, 100);         // A8 10 0 0 100 0
await cli.motorStop();            // A8 10 3 0 0 0
cli.declareSensors({ 6: 'ultrasonic' });
await cli.readUltrasonic(6);      // A5 6 4   -> text reply
```

Profiles cover both kits (L2 `arduinoEsp32Min` motor fn `A8`; L3 `arduinoUno` motor fn `A17`, light
`A16 21 0`, sound `A15 17 0`). 9 tests pin the exact strings against the vendor templates.

**Verified on real hardware (UC-Mind100, COM4, 2026-10-11):**

```
board   : UC-Mind100 (arduinoEsp32Min) — vendor CLI @115200
alive   : A1 1 1 1 -> "180.00"
display : A10 27 1234 / 5678 / 8888        (owner confirmed the display reads the value)
motor   : A8 10 0 0 100 0  … A8 10 3 0 0 0
alive   : A1 1 1 1 -> "180.00"
```

### Hazard: reading an unconfigured pin panics the firmware

```
sensor  : A5 6 4 -> "Guru Meditation Error: Core 1 panic'ed (IllegalInstruction)…
                    Core 1 register d…"
```

There was no ultrasonic module on pin 6, and the **firmware panicked and rebooted** (it came back
~4 s later, and the display/liveness worked again). This is the same missing-validation defect seen
in the CLI sweep earlier (10 of 32 malformed commands crashed the AVR too).

The lab therefore **refuses to read a pin the lesson has not declared** — `declareSensors({...})`,
enforced in `_require()`, with a test asserting that nothing reaches the board when it fails. A
crash costs the session, so this is a correctness requirement, not politeness.

### Port map for the UC-Mind100 (corrected)

The app's own table — **not** the `PORT_A/B/C/D` values I had been carrying from the headers:

| menu value | pin | notes |
|---|---|---|
| `A0` | "A0" | literal |
| **`A1`** | **27** | where the 4-digit display sits (matches the sb3's `PIN: "27"`) |
| **`A2`** | **25** | the 4-button / 4-LED module |
| `A3` | "A3" | literal |
| `A4` | **5** | |
| `A5` | **14** | |

`parsePin()` is `"A"===first ? parseInt(rest,10)+14 : parseInt(x,10)` — but the menu already supplies
numeric strings ("27", "25"), so the port labels resolve directly. Aiming at pin 15 (what a naive
reading of `parsePin` suggests) does nothing at all.

### 4-button / 4-LED module

```js
await cli.ledButton(25, 1, true);      // A3 25 2 1 0     LED 1 on   (port A2)
await cli.ledButton(25, 4, false);     // A3 25 2 4 1     LED 4 off
await cli.readLedButtonDigital(pin, level);   // A3 <pin> 1 <level>
```

The vendor template is `A3 <pin> 2 <index> ${"HIGH"===LEVEL?0:1}` — **HIGH is sent as 0**, so `on`
sends 0.

**Confirmed on real hardware by the owner: all four LEDs lit** from
`A3 25 2 1 0 | A3 25 2 2 0 | A3 25 2 3 0 | A3 25 2 4 0` — i.e. port A2 (pin 25), indices 1-4, level 0
= on. Along with the display (`A10 27 8888` → shows 8888) and the motor (`A8 10 0 0 100 0`), these are
the first three L2 blocks verified end to end against the physical kit through the lab's own client.

### Buttons (confirmed)

`A3 <pin> 1 <index>` returns `1` while that button is held and `0` otherwise — **verified by the
owner holding button 1** (`A3 25 1 1` -> `1`, the other three `0`). The indexes map straight through
1-4; the `1/2/4/8` bitmask in the vendor's *upload* code is a comparison table, not the wire format.
`cli.readButtons(pin)` returns `[b1, b2, b3, b4]` as booleans.

### The page now drives both protocols

`lab.js` gained `CliSession` and `attachTo()`: it tries **Firmata @57600**, and if nothing identifies,
reopens the port at **115200** and probes the CLI (`A1 1 1 1`). Web Serial cannot change baud in
place, so both transports grew `reopen()`. `lab.html` then shows CLI controls (motor, 4-digit display,
4 LEDs, buttons, sensor) or Firmata controls (motor/buzzer/servo/analog) — and **gates every control
on `capabilities()`**, not on the protocol, so a 40-pin board on Firmata is not offered motor sliders
it cannot honour.

Sensor reads require the operator to tick **已接上** first; without it the page refuses and nothing
reaches the board (asserted in the browser test), because an unconfigured read panics the firmware.

Verified in headless Chrome against the **deployed** URL, all three shapes:
`--pins=20` (L3/Firmata), `--pins=40` (L2 board on Firmata), `--proto=cli` (L2 on the vendor CLI).
The CLI run asserts the exact bytes the page emits: `A10 27 8888`, `A3 25 2 1 0`, `A8 10 0 0 120 0`.

### Panic detection

The client now raises `BoardResetError` when the firmware answers with a crash dump
(`Guru Meditation Error`, `panicked`, `abort()`) instead of returning it as a sensor reading. This
was prompted by the owner confirming **no ultrasonic sensor was connected** — which is exactly the
condition that panicked the board on `A5 6 4`.

## 15. Upload backend — blocks → sketch → compile → flash (working end to end)

The 89% of blocks that realtime mode cannot run are the ones the vendor generates code for. Rather
than reimplement that, the lab **runs the vendor's own code generation**:

* all **105** code-generation functions extracted verbatim from the bundle into `codegen.json`
  (`Blockly.Arduino.<category>_<opcode> = function (block) { … }`);
* they touch only **seven** things on the Blockly Arduino namespace — `definitions_`, `includes_`,
  `setups_`, `loops_`, `valueToCode`, `ORDER_ATOMIC`, `ORDER_UNARY_POSTFIX` — so `codegen.js`
  supplies a 7-line shim and runs them unchanged.

**Verified end to end on the UC-Mind100 (2026-10-11):**

```
blocks      : 2   (DC motor pin 10 @ 100, 4-digit display 8888)
definitions : UCDCMotor dc_10(10); UC7SegmentDisplay seven_segment_D(PORT_D);
compile     : arduino-cli 0.27.1 · esp32:esp32 1.0.6 · UCMake 1.0 library
              Sketch uses 284154 bytes (21%) of program storage space.   exit=0
flash       : esptool → 0x10000, 284272 bytes, "Hash of data verified."
result      : board booted the generated program; the vendor CLI no longer answers  (expected —
              the program replaced the firmware, exactly as UCMake's own upload does)
```

Tooling: `upload.mjs` (generate → compile → flash, `--dry-run` to inspect), `codegen.js`, `codegen.json`,
`program.example.json`. The ThinkPad needs `wlab-cli.yaml` pointing `directories.data` at
`%APPDATA%\UCMake\tools\Arduino` — the app's own `arduino-cli.yaml` points at `C:\Arduino`, which
does not hold the cores, so the fqbn silently fails to resolve.

### The operational consequence for lesson design

An upload **replaces the program on the board**, so after it the board is no longer a CLI board and
**realtime mode is unavailable until the vendor CLI image is put back** (`arduinoESP32Min.standardFirmata.ino.bin`,
223,808 B, kept in `laptop-firmwares/arduino/`). Students never manage firmware — but a lesson sits in
one mode or the other:

| | blocks | speed | board state after |
|---|---|---|---|
| realtime CLI | 12 | instant | still a CLI board |
| upload | **105** | ~10–30 s | runs the student's program |

## 17. The lab can now build programs — page → service → arduino-cli → binary

The page cannot shell out, so the build step runs as a small service on the same host as the page.

```
browser (wonderlab.html)
   │  POST /lab-hardware/api/build   { board, program:{title, blocks[]} }
   ▼
nginx  iits.giftedintl.com  →  proxy_pass 127.0.0.1:18811
   ▼
wonderlab-build.service  (node, systemd, enabled)
   │  codegen.js + codegen.json  → vendor's own block→source
   │  arduino-cli 0.35.3 --config-file ~/.arduino15/cli-uc.yaml
   ▼
{ ok, sketch, definitions, log, bytes, binary (base64), flashOffset }
```

Same origin, so no CORS and no toolchain in the browser. The NUC already had everything needed:
arduino-cli 0.35.3, **esp32:esp32 1.0.6** (the version UCMake uses), arduino:avr 1.8.8, and the
UCMake library in `~/.arduino15/libraries` (`UCMakeDrive`, `ServoESP32`, `Servo`, `avr-stl`).

**Verified in headless Chrome against the deployed URL — 16 checks:**

```
✔ clicking a palette block adds a program step
✔ its arguments became editable inputs
✔ the page compiled a program through the build service   {"bytes":282176,"ms":13315}
✔ the service returned a real binary                        282176 bytes in 13.3s
✔ the page shows the generated sketch                       ✅ 編譯成功 · 276 KB · 13.3 秒
✔ and a flash command                                       esptool --port <PORT> … 0x10000
```

### Pieces

| | |
|---|---|
| `build_service.mjs` | node HTTP service; `POST /api/build`, `GET /api/health` |
| `wonderlab-build.service` | systemd unit on the NUC (enabled, Restart=always, port 18811) |
| nginx | `location /lab-hardware/api/` → `127.0.0.1:18811/api/` (backup of the vhost taken) |
| `wonderlab.html` | palette → program builder (fields vs inputs decided by whether the arg has a menu) → 執行（編譯）, shows sketch, size, download link and the flash command |

### Flashing from the browser

The page now flashes the binary itself — no toolchain, no install, on the machine the board is
attached to:

```
compile  →  燒錄到主控板  →  Web Serial (navigator.serial)  →  esptool-js  →  0x10000
```

`esptool-js` 0.7.0 (313 KB, ESM) is **mirrored at `/lab-hardware/vendor/esptool-js/bundle.js`**, not
pulled from a CDN, so a classroom network can't break it. It is imported lazily, only when the flash
button is pressed. `writeFlash` requires `Uint8Array` (not a binary string); the browser's `atob`
output is converted per byte.

**Verified:** the flash button appears after a successful build, and `esptool-js` loads from our own
mirror exposing `ESPLoader` + `Transport` (headless Chrome, deployed URL).
**Not verified:** the flash transaction itself — it needs a real board and a human to grant the port.

### AVR flashing in the browser — `stk500.js`

esptool-js covers ESP32 only, but the UC-Mind300's ATmega328P runs **Optiboot**, which speaks
**STK500v1** — small enough to implement directly over Web Serial. `lab-device/stk500.js` does that:
Intel HEX parsing, `GET_SYNC` → `ENTER_PROGMODE` → `LOAD_ADDRESS` (in **words**) → `PROG_PAGE`
(128-byte pages) → `LEAVE_PROGMODE`, every command framed `… 0x20` and answered `0x14 … 0x10`.

It is transport-agnostic, so the same code runs in the browser and in Node — which is how it can be
tested. **5 tests against a simulated Optiboot**, including the subtlety that a page's *data* may
contain `0x20` (the terminator byte) and must not be treated as one — a naive receiver corrupts any
page containing it, which is exactly what my first mock did.

The page flashes the AVR board with it, and **reads the flash back afterwards and compares**, so a
bad write is reported rather than assumed good.

### Board-aware palette

Selecting a board now filters the palette (`esp*` opcodes are the ESP32 kits, the rest the AVR
family) and the level drives the board. This matters: compiling an `espMin*` block for the AVR board
produces calls that do not exist there (`runMin()` is ESP32-only), which is precisely the failure the
first AVR build test hit.

**Verified:** palette re-filtering (L3/AVR shows 43 of 105), AVR build via the service (12,180-byte
`.hex` in 1.6 s), `stk500.js` loads in the page, and 5 flasher unit-tests pass.

**WORKING — verified on hardware, byte-for-byte.** After several wrong turns the entry sequence is
solved, and the cause was none of the things first suspected:

```
$ node flash_avr.mjs COM3 wlab_avr.hex
port COM3 · 4322 bytes of flash to write
writing 3% … 100%
written; reading back to verify…
verify: 4322/4322 bytes match ✅
```

**The root cause: the USB bridge drops writes for a few hundred milliseconds after the port opens.**
Syncing immediately therefore only ever landed at the *tail* of Optiboot's window (measured 485 ms in,
window closing ~590 ms), so the next command was answered by the application. Settle first, *then*
pulse the reset. The verified recipe:

1. open the port, **wait 500 ms** for the CH340 to settle
2. avrdude's reset order: deassert DTR/RTS → 250 ms → assert → 50 ms
3. sync with **avrdude's own parameters**: 200 ms read timeout, up to 32 loops
4. page writes immediately after — continuous traffic keeps Optiboot's watchdog alive

Two red herrings worth recording, both disproved by measurement rather than argument:

* "Optiboot dies after one command" — false. `avrdude -vvvv` shows it answering a whole burst of
  `GET_PARAMETER` commands after the sync. What looked like death was the app booting while my
  command sat unread.
* The reset *polarity* matters (assert→release boots the application) but was never the blocker.

**How avrdude itself was used as the reference:** it is GPL-2.0, but the decisive evidence was
`avrdude -vvvv`, which prints the whole exchange. Its framing turned out to be identical to ours —
`55 <word address> 20` and `64 00 80 46 <128 bytes> 20`, 34 pages — so the protocol was right from
the start and only the entry timing was wrong.

Also kept from this detour: **Optiboot implements a subset of STK500v1** — no `ENTER_PROGMODE (0x50)`
or `LEAVE_PROGMODE (0x51)`, ignored *silently*, so waiting for their replies spans the window and the
app's banner comes back as a bogus `bad INSYNC: 0xf9`.

Verified in Node with the same `stk500.js` the page loads; the page's own button uses the same reset
recipe, so the browser transaction should behave identically (the click itself needs a human).

## 19. Hiding irrelevant serial ports in the chooser

Web Serial's `requestPort({ filters })` makes the browser's own chooser list only matching devices, so
a room full of laptops no longer offers Bluetooth serial ports, modems and everything else the OS
reports.

Both kits use a **CH340 — `idVendor 0x1A86` (6790), `idProduct 0x7523`** — confirmed on the ThinkPad
(`USB\VID_1A86&PID_7523`) and the macmini (`"USB Serial"`, idVendor 6790). The filter list adds the
bridges a UCMake board could plausibly ship with:

```js
export const UCMake_PORT_FILTERS = [
  { usbVendorId: 0x1a86 },   // CH340 / CH341   — both UC-Mind kits
  { usbVendorId: 0x10c4 },   // CP210x
  { usbVendorId: 0x0403 },   // FTDI
  { usbVendorId: 0x2341 },   // Arduino
  { usbVendorId: 0x2a03 },   // Arduino (arduino.org)
  { usbVendorId: 0x303a },   // Espressif native USB
];
```

**Verified in a real browser** — the options the page passes are captured by the test stub:

```
✔ the chooser is filtered to likely UC-Mind bridges (CH340 etc.)
  {"filters":[{"usbVendorId":6790},{"usbVendorId":4292},{"usbVendorId":1027},…]}
```

Applied at all three places that request a port: the hardware page's connect, the ESP32 flash button,
and the AVR flash button. Two safeguards because a filter can also hide a legitimate board:

* **「顯示所有序列埠」** on the hardware page retries unfiltered (`connectBoard({ allPorts: true })`);
* if the filtered chooser finds nothing, the error says so explicitly and points at the cable/driver
  rather than failing silently.

**Limitation, stated plainly:** the filter cannot tell the UC-Mind100 from the UC-Mind300 — same
bridge. Which one you actually got is decided by the board readout and the protocol detection, not by
the chooser.

## 20. Artefacts

- This document: `UCMake-re/L23-PROTOCOL.md`
- Lab device layer (JS + Python) and tests: `UCMake-re/lab-device/`
- All 22 firmware images from the ThinkPad: `UCMake-re/laptop-firmwares/arduino/`
- Disassembly of the decoy AVR image: `UCMake-re/re/uno-vendor.{asm,bin}`
- UCMake app bundle extracted on the macmini: `/tmp/vendors.js`
