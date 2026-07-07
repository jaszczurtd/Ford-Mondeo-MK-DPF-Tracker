# Mondeo DPF Tracker

Mondeo DPF Tracker is firmware and electronics documentation for monitoring the DPF system in a Ford Mondeo MK4 2.0 TDCi.

The project was created to collect real-world data from DPF operation and regeneration: exhaust gas temperatures, differential pressure signal, dosing pump activity, glow plug state, and vehicle operating context. The collected telemetry is intended to help reconstruct the factory DPF behavior and prepare a control algorithm for another car.

Author: Marcin "Jaszczur" Kielesinski.

This project requires [JaszczurHAL](https://github.com/jaszczurtd/JaszczurHAL).

The firmware uses the shared `../libraries/Credentials` Arduino library. The
`Credentials/` directory in this project is only a template/example and is not
part of the active build.

The physical tracker uses a Waveshare RP2040-Zero module. In practice the firmware only depends on RP2040 peripherals used through Arduino/JaszczurHAL, so it also builds and runs with compatible RP2040 board definitions such as Raspberry Pi Pico. Select the FQBN that matches the board support package and upload method used on the development machine.

## Build

The application uses portable app functions (`app_start()` / `app_task0()`), so there is no hand-written `.ino` file in the repository. CMake generates the small Arduino `setup()` / `loop()` wrapper under `.build/cmake/sketch/` and then calls `arduino-cli`.

The VS Code workflow is provided by JaszczurHAL's shared `jh-vscode` entrypoint.
Stable module configuration lives in `.vscode/jaszczurhal.project.json`; local
developer preferences live in `.vscode/settings.json`.

- `jaszczurhal.cliPath`
- `jaszczurhal.uploadPort`
- `jaszczurhal.root`
- `jaszczurhal.vscodeEntry`

The tracked default configuration builds with `rp2040:rp2040:rpipico`; use
`--fqbn` or update the manifest/settings locally if the physical
RP2040-Zero-specific FQBN is needed.

From this firmware directory, the same build can be run manually:

```bash
../libraries/JaszczurHAL/vscode/entry/jh-vscode build --project .
```

The default CMake fallback FQBN is `rp2040:rp2040:rpipico`, but `rp2040:rp2040:waveshare_rp2040_zero` also works fine. From the practical standpoint this makes no difference for this project.

The main generated artifacts are copied to `.build/firmware.elf`, `.build/firmware.bin`, `.build/firmware.uf2`, and `.build/firmware.map`.

## Developer Workflow

VS Code tasks and command-line workflow use the shared JaszczurHAL entrypoint:

- `Project: Build`
- `Project: Build (Debug)`
- `Project: Upload`
- `Project: Upload (UF2 / BOOTSEL)`
- `Project: Serial Monitor`
- `Project: Debug Probe Monitor`
- `Project: Refresh IntelliSense`
- `Project: Clear USB Identity`

The old local firmware helpers under `scripts/` were removed during migration.
The canonical path is now `../libraries/JaszczurHAL/vscode/entry/jh-vscode`.

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

The electronics files are in `materials/DPF_tracker/`:

- Schematic: `materials/DPF_tracker/DPF_tracker.kicad_sch`
- Exported PDF: `materials/DPF_tracker/DPF_tracker.pdf`

## Modem

Connectivity is handled by a SIMCom A7670E / A7670X Cat-1 LTE modem. The modem is connected to the RP2040 over UART and is managed through JaszczurHAL's SIMCom A76xx driver.

The firmware brings up the modem, waits for SIM and network registration, attaches the PDP context, then opens an MQTT/TLS session. It publishes telemetry to `dpf/data`, queued control-signal events to `dpf/events`, status to `dpf/status`, and listens for commands on `dpf/cmd`. The current remote command contract includes `modem_reset`, which power-cycles the modem through the relay-controlled supply path.

The modem is also used as the source for network time, GNSS location, and cellular location context. GNSS is queried every 5 seconds when the modem is ready; cellular location is queried every 15 seconds.

## MQTT Telemetry

Telemetry is sampled as compact JSON every 2 seconds and queued in RAM for `dpf/data`. While MQTT is connected, the firmware drains this queue and removes each payload only after a successful publish. This keeps short MQTT outages from creating gaps in the slow temperature/pressure trend.

Example `dpf/data` payload:

```jsonc
{
  "version": "v0.4",                 // Firmware version.
  "time": "2026-06-19T18:42:10+02:00", // Modem/network time when available.
  "egt_pre": 312.45,                 // Pre-DPF exhaust gas temperature, C.
  "egt_mid": 287.12,                 // Mid-DPF exhaust gas temperature, C.
  "dp_voltage": 1.42,                // DPF differential pressure sensor voltage.
  "dp_raw": 1762,                    // Raw ADC value for the pressure input.
  "pump_onoff_period": 2.5,          // Dosing pump frequency estimate from ON/OFF timing.
  "pump_freq_hz": 2.5,               // Dosing pump frequency estimate in Hz.
  "pump_cnt": 5,                     // Pump ON edge count since the previous payload.
  "pump": 1,                         // Current pump state: 1 = ON, 0 = OFF.
  "pump_period_ms": 400,             // Period between recent pump ON edges.
  "pump_last_on_ms": 82,             // Last completed pump ON duration.
  "pump_current_on_ms": 37,          // Current pump ON duration when pump is ON.
  "glow": 1,                         // Current vaporizer glow plug state: 1 = ON, 0 = OFF.
  "glow_dur": 1400,                  // Last completed glow plug ON duration.
  "glow_current_on_ms": 6200,        // Current glow plug ON duration when glow is ON.
  "mcu_temp": 42.38,                 // RP2040 internal temperature, C.
  "data_queue_len": 3,               // Number of queued dpf/data payloads in RAM.
  "data_overflow_count": 0,          // Dropped dpf/data payload count due to RAM queue overflow.
  "event_queue_len": 12,             // Number of queued dpf/events records in RAM.
  "event_overflow_count": 0,         // Dropped event count due to RAM queue overflow.
  "gnss_valid": 1,                   // GNSS fix validity: 1 = valid, 0 = invalid.
  "gnss_powered": 1,                 // GNSS power state: 1 = powered, 0 = off/unavailable.
  "gnss_error": 0,                   // GNSS read/status error code.
  "gnss_age_ms": 850,                // Age of the latest GNSS fix.
  "gnss_lat": 52.2297,               // GNSS latitude when valid.
  "gnss_lng": 21.0122,               // GNSS longitude when valid.
  "gnss_speed_kmh": 74.32,           // GNSS speed.
  "gnss_alt_m": 112.5,               // GNSS altitude.
  "gnss_course_deg": 184.2,          // GNSS course over ground.
  "gnss_hdop": 0.9,                  // GNSS horizontal dilution of precision.
  "gnss_sats_used": 9,               // Satellites used for the fix.
  "gnss_sats_view": 15,              // Satellites visible.
  "gnss_fix_mode": 3,                // GNSS fix mode reported by the modem.
  "gnss_utc": "164210.000",          // GNSS UTC time when provided by the fix.
  "cell_valid": 1,                   // Cellular location validity: 1 = valid, 0 = invalid.
  "cell_error": 0,                   // Cellular location error code.
  "cell_age_ms": 4200,               // Age of the latest cellular location estimate.
  "cell_speed_kmh": 72.1,            // Cellular location speed estimate.
  "cell_lat": 52.2301,               // Cellular location latitude when valid.
  "cell_lng": 21.0118,               // Cellular location longitude when valid.
  "cell_acc_m": 550,                 // Cellular location accuracy estimate in meters.
  "ms": 1234567                      // Firmware uptime in milliseconds.
}
```

Cellular location is approximate operating context, not a precise GPS route. Some GNSS and cellular location fields are omitted or set to unavailable values when no valid fix is available.

Fast control-signal transitions are queued separately in a RAM ring buffer and published to `dpf/events` in batches. Events are removed from the queue only after a successful MQTT publish, so short MQTT outages do not lose pump/glow edge timing.

Example `dpf/events` payload:

```jsonc
{
  "version": "v0.4",                 // Firmware version.
  "ms": 1234600,                     // Firmware uptime when this batch was prepared.
  "batch_count": 2,                  // Number of events in this MQTT batch.
  "queue_len": 2,                    // Queue length before or at batch preparation.
  "queue_remaining_after_batch": 0,  // Events still queued after this batch is published.
  "overflow_count": 0,               // Dropped event count due to RAM queue overflow.
  "events": [
    {
      "seq": 1201,                   // Monotonic event sequence number.
      "t_us": 1234100123,            // Firmware timestamp of the edge, microseconds.
      "t_ms": 1234100,               // Firmware timestamp of the edge, milliseconds.
      "src": "glow",                 // Event source: "pump" or "glow".
      "state": 1,                    // Edge state: 1 = ON, 0 = OFF.
      "gnss_speed_kmh": 74.32,       // Latest GNSS speed at the edge, or -1 if unavailable.
      "dp_voltage": 1.42,            // Latest sampled DPF pressure sensor voltage.
      "dp_sample_age_ms": 37         // Age of dp_voltage at the edge, or -1 if unavailable.
    },
    {
      "seq": 1202,
      "t_us": 1234123456,
      "t_ms": 1234123,
      "src": "pump",
      "state": 1,
      "gnss_speed_kmh": 74.32,
      "dp_voltage": 1.43,
      "dp_sample_age_ms": 81
    }
  ]
}
```

The telemetry queue stores up to `DATA_QUEUE_CAPACITY` fixed-size payload slots, each limited by `DATA_PAYLOAD_MAX_SIZE`. The event batch also includes `queue_len`, `queue_remaining_after_batch`, and `overflow_count`. Both queues are finite; if either fills during a long outage, its overflow counter records that the in-RAM buffer was exhausted.

DPF regeneration cycle detection should be done by combining both streams. `dpf/data` is the regular slow telemetry stream for pressure, temperature, location, and long-term state trends. `dpf/events` is the precise actuator edge stream for reconstructing pump and glow plug timing. Start/end conditions should primarily come from the pressure and temperature trends in `dpf/data`, while `dpf/events` describes what the factory controller did during that cycle.

The status topic `dpf/status` publishes an online payload after MQTT connection:

```jsonc
{
  "status": "online"                 // Tracker is connected to MQTT and publishing.
}
```

If the previous application boot was caused by a real watchdog timeout, the firmware also publishes one watchdog status payload:

```jsonc
{
  "status": "watchdog_reset",        // Status event type.
  "reason": "watchdog",              // Reset reason reported by firmware.
  "version": "v0.4",                 // Firmware version.
  "ms": 12345                        // Firmware uptime when the status was published.
}
```

Other reset causes are not reported as status events. The command topic `dpf/cmd` accepts the plain text command `modem_reset`.

## Thermocouples

The board uses two K-type thermocouple channels for exhaust gas temperature measurement:

- pre-DPF EGT probe,
- mid-DPF EGT probe.

Both probes are read through MCP9600 I2C thermocouple amplifiers on the shared I2C bus. The firmware configures them as K-type sensors with high ADC resolution, ambient compensation, filtering, and publishes the resulting values as `egt_pre` and `egt_mid`.

![Mondeo DPF Tracker](materials/20260604_013234.jpg)
