# Block semantics from the UCMake packages

Where a block's *meaning* comes from — deduced from the vendor's own sources rather than by
attaching every module:

1. **The UCMake Arduino library** (`~/.arduino15/libraries/UCMake/src`, 143 classes) — the
   firmware-side maths. This gives units, scaling, ranges and byte layouts directly.
2. **The app bundle** — block argument menus (valid values) and i18n text (which usually states
   units).
3. **Hardware** — only needed to confirm that the *realtime* firmware formats its replies the way the
   library suggests.

The distinction that matters: the **upload** path compiles against this library, so its semantics are
**exactly** what is written below. The **realtime** path is answered by firmware we have no source
for, so those replies are *inferred* from the same maths and want one confirmation each.

## What the library says

| block | library call | semantics | realtime command | verified |
|---|---|---|---|---|
| DC motor | `UCDCMotor::runMin(speed)` | speed −255…255; direction encoded in the sign. `UC130DCMotor::run()` maps to `value = speed/2.55` (0–100) and sends `reset; write 0x02; reset; write value` over OneWire | `A8 <pin> 0 0 <speed> 0` | ✅ hardware |
| 4-digit display | `UC7SegmentDisplay::showNumber(v)` | plain decimal | `A10 <pin> <value>` | ✅ hardware (8888) |
| 4-LED module | `UC4LEDButton::setLed(i, on)` | `i` = 1…4 | `A3 <pin> 2 <i> <0\|1>` (HIGH → 0) | ✅ hardware |
| buttons | `UC4LEDButton::readValue()` | **bitmask** 1/2/4/8 for buttons 1–4. The CLI instead answers `0`/`1` per index | `A3 <pin> 1 <i>` | ✅ hardware |
| ultrasonic | `UCUltrasonicSensor::distanceCm()` | `distance = raw / 17.57`, clamped to **500 cm**; returns 500 if the module does not respond | `A5 <pin> 4` | ⚠️ panics with no module |
| light (RJ) | `UCLightSensor_RJ::read()` | `value * 1023.0 / 255.0` → **0–1023** | `A16 21 0` (AVR) | ⚠️ |
| sound (RJ) | `UCSoundSensor_RJ::read()` | `value * 1023.0 / 255.0` → **0–1023** | `A15 17 0` (AVR) | ⚠️ |
| colour | `UCColorSensor::readColorData()` | 8 bytes: `R = d[1]<<8\|d[0]`, `G = d[3]<<8\|d[2]`, `B = d[5]<<8\|d[4]`, `Color = d[7]<<8\|d[6]` — **16-bit little-endian pairs**; display clamps to 255 | `A4 <pin> 3 <index>` | ⚠️ |
| joystick | `UCJoystick::readData()` | `X = 255 − byte` (inverted), `Y = byte`, then a button | `A2 <n> …` | ⚠️ |
| gyro / IMU | `UCGyroSensor::update()` | 20 bytes of I2C; `accX = (d[0]<<8)\|d[1]` etc. — **signed 16-bit big-endian**, integrated over `dt` | `A1 <n> <index> <axis>` | ⚠️ see note |
| temperature | `UCTemperature::temperature()` | DS18B20 over OneWire → **celsius** | — | ⚠️ |
| line follower | `UCLineFollower::startRead()` / `startRead5()` | one byte per sensor | `A9 <pin> 1 <axis>` | ⚠️ |
| buzzer | `UCBuzzer::tone(freq, duration)` | software tone: `period = 1e6/freq`, half-period pulses; duration in ms | — | ⚠️ |
| compass / barometer / flame / touch / PIR / humidity / rain / moisture | classes exist (`UCCompassSensor`, `UCBarometerSensor`, `UCFlameSensor`, `UCTouchSensor`, `UCPIRSensor`, …) | byte layouts readable from the same sources | `A13`, `A11`, `A18`–`A20` | ⚠️ |

## The one unexplained reading

`A1 1 1 1` returns **`180.00`** on *both* boards. `A1` is the gyro reader
(`A1 <n> <index> <axis>`), and `UCGyroSensor` integrates an IMU — so a float angle is plausible, but
180.00 is suspiciously round for an uncalibrated axis, and it is identical on two different boards.
Worth one experiment with an IMU attached before trusting it.

## Consequence

Most blocks move from "template only" to **"semantics known for upload, inferred for realtime"** —
which is enough to implement them, with one hardware confirmation each. Only the realtime *reply
format* genuinely needs a module in hand, and even that is now a predicted value rather than a guess:
attach an ultrasonic module and expect ≈`raw/17.57` cm, not an arbitrary number.
