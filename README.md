# Mondeo DPF Tracker

Mondeo DPF Tracker is firmware and electronics documentation for monitoring the DPF system in a Ford Mondeo MK4 2.0 TDCi.

The project was created to collect real-world data from DPF operation and regeneration: exhaust gas temperatures, differential pressure signal, dosing pump activity, glow plug state, and vehicle operating context. The collected telemetry is intended to help reconstruct the factory DPF behavior and prepare a control algorithm for another car.

Author: Marcin "Jaszczur" Kielesinski.

This project requires [JaszczurHAL](https://github.com/jaszczurtd/JaszczurHAL).

The firmware also requires a local `Credentials` Arduino library. A template is included in this project tree under `Credentials/`; for a normal Arduino build it should be placed in the sketchbook libraries directory as `libraries/Credentials`, matching Arduino's library discovery rules.

The firmware runs on RP2040, using an rpi-zero board.

## Build

The application uses portable app functions (`app_start()` / `app_task0()`), so there is no hand-written `.ino` file in the repository. CMake generates the small Arduino `setup()` / `loop()` wrapper under `.build/cmake/sketch/` and then calls `arduino-cli`.

```bash
./scripts/configure-cmake.sh
cmake --build .build/cmake --target firmware
```

VS Code tasks use the same CMake targets for build, debug, upload, UF2 upload, and IntelliSense refresh.

## Board Architecture

The tracker board is built as an RP2040-Zero based telemetry controller with a small set of automotive signal frontends. The RP2040 collects local measurements, timestamps the current operating state, and sends telemetry through an LTE modem to an MQTT broker.

Main hardware blocks:

- RP2040-Zero controller board running the tracker firmware.
- Two K-type EGT thermocouple inputs, each handled by an MCP9600 I2C thermocouple amplifier.
- Analog input for the DPF differential pressure sensor, read through the RP2040 ADC.
- GPIO interrupt inputs for dosing pump pulses and vaporizer glow plug state.
- LTE Cat-1 modem interface for remote telemetry and commands.
- Modem power control through a relay, allowing the firmware to hard-reset the modem when connectivity cannot be restored.
- On-board RGB status LED for connection, error, and publish activity feedback.

## Modem

Connectivity is handled by a SIMCom A7670E / A7670X Cat-1 LTE modem. The modem is connected to the RP2040 over UART and is managed through JaszczurHAL's SIMCom A76xx driver.

The firmware brings up the modem, waits for SIM and network registration, attaches the PDP context, then opens an MQTT/TLS session. It publishes telemetry to `dpf/data`, status to `dpf/status`, and listens for commands on `dpf/cmd`. The current remote command contract includes `modem_reset`, which power-cycles the modem through the relay-controlled supply path.

## Thermocouples

The board uses two K-type thermocouple channels for exhaust gas temperature measurement:

- pre-DPF EGT probe,
- mid-DPF EGT probe.

Both probes are read through MCP9600 I2C thermocouple amplifiers on the shared I2C bus. The firmware configures them as K-type sensors with high ADC resolution, ambient compensation, filtering, and publishes the resulting values as `egt_pre` and `egt_mid`.

![Mondeo DPF Tracker](materials/20260604_013234.jpg)
