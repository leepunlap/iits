# Block semantics from the UCMake packages

Where a block's *meaning* comes from — deduced from the vendor's own sources rather than by
attaching every module:

1. **The UCMake Arduino library** (`~/.arduino15/libraries/UCMake/src`, **143 classes**) — the
   firmware-side maths: units, scaling, ranges, byte layouts. Extracted mechanically (method
   signatures from the headers, the arithmetic from the bodies).
2. **The app bundle** — block argument menus (valid values) and i18n text (which usually states the
   unit).
3. **Hardware** — only to confirm that the *realtime* firmware formats replies the way the library
   suggests.

**The distinction that matters:** the **upload** path compiles against this library, so its semantics
are **exact**. The **realtime** path is answered by firmware whose source we do not have, so those
replies are **inferred** from the same maths and want one confirmation each.

## Sensors

| block | library | semantics | realtime | verified |
|---|---|---|---|---|
| ultrasonic | `UCUltrasonicSensor::distanceCm()` | `distance = raw / 17.57`, clamped to **500 cm**; 500 if no reply | `A5 <pin> 4` | ⚠️ panics with no module |
| light (RJ) | `UCLightSensor_RJ::read()` | `value * 1023.0 / 255.0` → **0–1023** | `A16 21 0` (AVR) | ⚠️ |
| sound (RJ) | `UCSoundSensor_RJ::read()` | `value * 1023.0 / 255.0` → **0–1023** | `A15 17 0` (AVR) | ⚠️ |
| colour | `UCColorSensor::readColorData()` | 8 bytes, four **16-bit little-endian** pairs: `R=d[1]<<8\|d[0]`, `G=d[3]<<8\|d[2]`, `B=d[5]<<8\|d[4]`, `Color=d[7]<<8\|d[6]`; display clamps to 255 | `A4 <pin> 3 <index>` | ⚠️ |
| joystick | `UCJoystick::readData()` | `X = 255 − byte` (**inverted**), `Y = byte`, then a button | `A2 <n> …` | ⚠️ |
| gyro / IMU | `UCGyroSensor::update()` | 20 I2C bytes; `accX=(d[0]<<8)\|d[1]` — **signed 16-bit big-endian**, integrated over `dt` | `A1 <n> <index> <axis>` | ⚠️ see note |
| compass | `UCCompassSensor::update()` | `head_X=(d[0]<<8)\|d[1]`, `head_Y=(d[2]<<8)\|d[3]`, `head_Z=(d[4]<<8)\|d[5]` — **16-bit big-endian**; plus heading and intensities | `A13 <n> <axis>` | ⚠️ |
| barometer | `UCBarometerSensor` | `readHeight()` returns `height/100`, plus `readPressure()`, `readTemp()` | — | ⚠️ |
| temperature | `UCTemperature::temperature()` | DS18B20 over OneWire → **celsius** | — | ⚠️ |
| flame | `UCFlameSensor` | three channels, `readValue(1..3)` | — | ⚠️ |
| touch | `UCTouchSensor` | `touched()`, `setMode(v)` | `A20 <n> 0` | ⚠️ |
| touch (funny) | `UCFunnyTouchSensor::readValue()` | single value | `A20 <n> 0` | ⚠️ |
| PIR | `UCPIRSensor::readSensor()` | presence | `A20 <n> 0` | ⚠️ |
| line follower | `UCLineFollower::startRead()` / `startRead5()` | one byte per sensor | `A9 <pin> 1 <axis>` | ⚠️ |
| 2.4G remote | `UC24GController` | `key_flags = (rx[1]<<8) \| rx[2]` — a **bitmask**; `buttonPressed_X/Y/A/B/L/D` decode bits | `A5`/`A8 <index> 10` | ⚠️ |

No dedicated library class exists for **humidity, moisture, rain or voltage** — those blocks map to
`A11` / `A18` / `A19` in the realtime firmware, so their semantics live in firmware we do not have
and are the least certain of the set.

## Actuators

| block | library | semantics | realtime | verified |
|---|---|---|---|---|
| DC motor | `UCDCMotor::runMin(speed)` | speed **−255…255**, direction in the sign; `UC130DCMotor::run()` maps `value = speed/2.55` (0–100) and sends `reset; write 0x02; reset; write value` | `A8 <pin> 0 0 <speed> 0` | ✅ hardware |
| encoder motor | `UCEncoderMotor::run()` | `speed/2.55`, command bytes `0x02`/`0x03` | `A8 <index> 2 <speed>` | ⚠️ |
| 36-encoder motor | `UC36EncoderMotor` | `count_pulse = (Wire.read()<<8) + count_pulse`; `float f = ENCODER_ONECIRCLE_NUM / 360.0` → **degrees**; `moveEncoder(speed, counts)`, `moveCircle`, `moveDegree`, `getCurrentPosition()` | `A8 <index> 3..9` | ⚠️ |
| servo | `UCServo::write(angle)` | pulse ≈ `angle * 8 + 400` µs | `A6 <pin> <angle>` | ⚠️ |
| 360° servo | `UCServo360::write(angle)` | pulse ≈ `angle * 4.3 + 400` µs | `A5 <pin> <value>` | ⚠️ |
| 4-digit display | `UC7SegmentDisplay::showNumber(v)` | plain decimal | `A10 <pin> <value>` | ✅ hardware (8888) |
| 4-LED module | `UC4LEDButton::setLed(i,on)` | `i` = 1…4 | `A3 <pin> 2 <i> <0\|1>` (HIGH → 0) | ✅ hardware |
| buttons | `UC4LEDButton::readValue()` | **bitmask** 1/2/4/8 for buttons 1–4. The CLI answers `0`/`1` per index instead | `A3 <pin> 1 <i>` | ✅ hardware |
| buzzer | `UCBuzzer::tone(freq, duration)` | software tone: `period = 1e6/freq`, half-period pulses; duration in ms | — | ⚠️ |
| Bluetooth | `UCBluetoothController` | `buttonPressed(button)`, `readAnalog(button)`, packet parsing | `A7 <pin> <0\|1>` | ⚠️ |

## The OneWire peripheral protocol

The 31 blocks that use `sendOneWireWrite` talk to modules through `UCAdapter`, whose command bytes are
now known: `reset; write 0x02; reset; write <pin>; write <angle>` for `write()`, and
`reset; write 0x03; reset; write <pin>, <index>, <r>, <g>, <b>` for `RGBshow()`. That is the missing
half of the OneWire path if it is ever needed — the other half being firmware that implements it.

## The one unexplained reading

`A1 1 1 1` returns **`180.00`** on *both* boards. `A1` is the gyro reader and `UCGyroSensor`
integrates an IMU, so a float angle is plausible — but 180.00 is suspiciously round and identical
across two different boards. Worth one experiment with an IMU attached before trusting it.

## What this buys

Every block now has a **value domain** (units, range, encoding, byte order) rather than a bare
command. Verification becomes a checklist of predictions — attach an ultrasonic module and expect
≈`raw/17.57` cm — instead of an investigation. Nine classes were read in detail and the rest
enumerated; the remaining uncertainty is concentrated in the four blocks with no library class at all.
