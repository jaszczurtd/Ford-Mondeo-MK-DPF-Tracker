# MQTT telemetry

[Polski](TELEMETRY.pl.md) · [Project overview](../README.md)

The firmware publishes JSON on `dpf/data`, `dpf/events` and `dpf/status`, and
accepts commands on `dpf/cmd`. [tracker.h](../tracker.h) defines the topics and
limits; [tracker.cpp](../tracker.cpp) constructs the payloads. Examples below
illustrate the current fields, not a recorded drive.

## Sampling and buffering

Sensors are sampled every 500 ms; `dpf/data` payloads are constructed every
2000 ms. While connected, one queued data payload is attempted every 250 ms
and an event batch of at most 32 records every 500 ms. GNSS/cell queries and
modem operations can block the main loop, so these are nominal intervals.

| Queue | RP2040 | STM32G474 | Limit |
| --- | ---: | ---: | --- |
| Data | 64 messages | 8 messages | 1536 bytes per slot, including the terminating NUL |
| Events | 1023 usable records | 255 usable records | Arrays of 1024/256 slots; one stays empty |

Both queues retain old records and drop new ones when full. Data payloads of
1536 bytes or more are also rejected. Drops increment the relevant counter;
event sequence gaps can reveal lost transitions. Records leave a queue only
after successful MQTT publication. Queues are RAM-only and disappear on reset.
This does not guarantee exactly-once delivery or unlimited outage coverage.

## `dpf/data`

| Field | Meaning |
| --- | --- |
| `version` | Firmware version (`VERSION`), not a separate schema version. |
| `time`, `ms` | Last network time in ISO 8601 (empty until available), and current uptime in ms. |
| `egt_pre`, `egt_mid`, `mcu_temp` | Pre-DPF, mid-DPF and MCU temperature in °C. |
| `dp_voltage`, `dp_raw` | Sensor voltage in V and raw ADC reading; no pressure calibration yet. |
| `pump_onoff_period`, `pump_freq_hz` | Both express frequency in Hz, despite the first field’s name; zero after 2 s without an ON edge. |
| `pump_cnt` | ON edges since the previous payload construction; resets during construction, even if that payload is later dropped. |
| `pump`, `glow` | Current states: 1 = ON, 0 = OFF. |
| `pump_period_ms` | Interval between recent pump ON edges, in ms; can retain the last value after pumping stops. |
| `pump_last_on_ms`, `glow_dur` | Last completed ON duration in ms. |
| `pump_current_on_ms`, `glow_current_on_ms` | Current ON duration in ms; zero when OFF. |
| `data_queue_len`, `event_queue_len` | Queue lengths at payload construction, before adding this data payload. |
| `data_overflow_count`, `event_overflow_count` | Cumulative drops in this boot; data also counts oversized payloads. |
| `gnss_valid`, `gnss_powered`, `gnss_error`, `gnss_age_ms` | Fix validity and power flags (0/1), latest HAL result, age of last good fix in ms (-1 without a fix). |
| `gnss_lat`, `gnss_lng` | Degrees; omitted without a valid fix. |
| `gnss_speed_kmh`, `gnss_alt_m`, `gnss_course_deg`, `gnss_hdop` | Speed, altitude, course and HDOP; -1 when unavailable. |
| `gnss_sats_used`, `gnss_sats_view`, `gnss_fix_mode` | Used/visible satellite counts and modem fix mode; -1 without a valid fix. |
| `gnss_utc` | Modem UTC string, included only when provided with a valid fix. |
| `cell_valid`, `cell_error`, `cell_age_ms`, `cell_speed_kmh` | Cell location flag, latest HAL result, age in ms and speed in km/h; age/speed are -1 when unavailable. |
| `cell_lat`, `cell_lng`, `cell_acc_m` | Approximate coordinates in degrees and accuracy in m; included only for valid cellular location. |

```json
{
  "version": "v0.5",
  "time": "2026-06-19T18:42:10+02:00",
  "egt_pre": 312.45,
  "egt_mid": 287.12,
  "dp_voltage": 1.42,
  "dp_raw": 1762,
  "pump_onoff_period": 2.5,
  "pump_freq_hz": 2.5,
  "pump_cnt": 5,
  "pump": 1,
  "pump_period_ms": 400,
  "pump_last_on_ms": 82,
  "pump_current_on_ms": 37,
  "glow": 1,
  "glow_dur": 1400,
  "glow_current_on_ms": 6200,
  "mcu_temp": 42.38,
  "data_queue_len": 3,
  "data_overflow_count": 0,
  "event_queue_len": 12,
  "event_overflow_count": 0,
  "gnss_valid": 1,
  "gnss_powered": 1,
  "gnss_error": 0,
  "gnss_age_ms": 850,
  "gnss_lat": 52.2297,
  "gnss_lng": 21.0122,
  "gnss_speed_kmh": 74.32,
  "gnss_alt_m": 112.5,
  "gnss_course_deg": 184.2,
  "gnss_hdop": 0.9,
  "gnss_sats_used": 9,
  "gnss_sats_view": 15,
  "gnss_fix_mode": 3,
  "gnss_utc": "164210.000",
  "cell_valid": 1,
  "cell_error": 0,
  "cell_age_ms": 4200,
  "cell_speed_kmh": 72.1,
  "cell_lat": 52.2301,
  "cell_lng": 21.0118,
  "cell_acc_m": 550,
  "ms": 1234567
}
```

Network time is refreshed about once per minute while MQTT is connected;
`time` is therefore the last read value, not an independently advancing sample
clock. Use `ms` for relative timing within a boot. GNSS and cellular state may
retain a previous valid fix after a query error: check age and error as well
as validity. Cellular location is approximate, not a precise route.

## `dpf/events`

Pump and glow inputs produce events on both edges: `state=1` means ON,
`state=0` means OFF. Duplicate/no-change interrupts do not add events.
The example contains two different sources in one batch:

```json
{
  "version": "v0.5",
  "ms": 1234600,
  "batch_count": 2,
  "queue_len": 2,
  "queue_remaining_after_batch": 0,
  "overflow_count": 0,
  "events": [
    {
      "seq": 1201,
      "t_us": 1234100123,
      "t_ms": 1234100,
      "src": "glow",
      "state": 1,
      "gnss_speed_kmh": 74.32,
      "dp_voltage": 1.42,
      "dp_sample_age_ms": 37
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

| Field | Meaning |
| --- | --- |
| `version`, `ms` | Firmware version and uptime when the batch is built |
| `batch_count`, `queue_len` | Records in this batch and queue length at the snapshot |
| `queue_remaining_after_batch` | Snapshot queue length minus batch size; new ISR events may already have arrived |
| `overflow_count` | Cumulative event drops since boot |
| `seq` | 32-bit sequence starting at zero; advances even for an event dropped on overflow |
| `t_us`, `t_ms` | 32-bit microsecond timestamp of the edge and its integer division by 1000 |
| `src`, `state` | `pump` or `glow`, and 1/0 ON/OFF |
| `gnss_speed_kmh` | Latest cached GNSS speed at the edge, -1 if unavailable; no fix age is included |
| `dp_voltage` | Latest periodic voltage sample; not an ADC reading taken in the ISR |
| `dp_sample_age_ms` | Voltage sample age, capped at 65534 ms; -1 when unavailable |

`t_us` wraps every 2^32 µs (about 71.6 minutes), and event `t_ms` wraps with it.
It is not interchangeable with the top-level `ms`, which wraps after about
49.7 days. `seq` also wraps and resets on reboot. Account for wraps, batches
and boot boundaries before aligning events with telemetry. The batch timestamp
is the send-time snapshot; queued edge timestamps describe earlier activity.

## Status and command

After an MQTT connection, the firmware publishes:

```json
{
  "status": "online"
}
```

After a real watchdog timeout it also publishes one status event per boot:

```json
{
  "status": "watchdog_reset",
  "reason": "watchdog",
  "version": "v0.5",
  "ms": 12345
}
```

Other reset causes, including programmatic upload/BOOTSEL resets, are not
reported as watchdog events. `dpf/cmd` accepts the exact plain-text payload
`modem_reset`, which requests a relay power cycle of the modem.

## Using the data

Combine `dpf/data` temperature/voltage trends with `dpf/events` actuator timing
to study regeneration. The project does not yet implement automatic cycle
detection or pressure calibration. Monitor both queue lengths and overflow
counters, and retain raw messages so later analyses can be repeated.

The [backend guide](../backend/README.md) explains session inference and
analytical windows. Those windows currently use server receive time, which
can group delayed offline data differently from its acquisition time.
