# GEMINI Instructions for `testing/esp32/`

## Scope
This folder contains an alternate/simple ESP32 firmware example (`jarvis_esp32.ino`) for environment sensor exchange.

## Firmware Characteristics
- Baud: `9600` (`SERIAL_BAUD`)
- Command model: host sends `GET_ENV`
- Response format: `TEMP:<value>,HUM:<value>`

## Important Compatibility Note
This protocol differs from the `src/` core stack (which commonly uses `115200` and snapshot-oriented behavior).

If this `.ino` firmware is flashed, laptop-side serial code must match:
- Port as appropriate (`COMx`)
- Baud `9600`
- `GET_ENV` request/response expectations

## Upload and Validation
- Flash via Arduino IDE to ESP32.
- Open serial monitor at `9600` to verify output behavior.
- From host, send `GET_ENV` and confirm parseable `TEMP/HUM` response.

## Recommended Usage
- Use this folder for quick sensor bring-up and protocol sanity checks.
- Use `src/` firmware for full belief-core architecture demos.

## Do Not
- Assume this firmware emits snapshot protocol lines.
- Mix this protocol with `115200` snapshot clients without adapting parser logic.
