# Tracker wiring and sensors

[Polski](HARDWARE.pl.md) · [Project overview](../README.md)

The physical tracker is built around a Waveshare RP2040-Zero. The `nucleo`
assembly maps the devices to NUCLEO-G474RE for build checks; hardware operation
on that assembly remains unverified. [device_tree.json](../device_tree.json)
is the firmware wiring definition. The [schematic PDF](../materials/DPF_tracker/DPF_tracker.pdf)
shows the signal frontends and power circuitry.

## Connections

| Signal | `rp2040-zero` | `nucleo` (Arduino header) |
| --- | --- | --- |
| MCP9600 SDA / SCL | GP0 / GP1, I2C0 | PB9 D14 / PB8 D15, I2C1 |
| MCU UART TX / RX to modem RX / TX | GP4 / GP5, UART1 | PA9 D8 / PA10 D2, USART1 |
| Modem power relay | GP6 | PB5 D4 |
| Dosing-pump input | GP2 | PB4 D5 |
| Glow-plug input | GP3 | PB10 D6 |
| DPF pressure ADC | GP26 | PA0 A0 |
| WS2812 status LED | GP16, on board | PA8 D7, external |

I2C runs at 100 kHz. The pre-DPF MCP9600 address is `0x60`, and the mid-DPF
address is `0x67`. The modem UART uses 115200 baud, 8N1. STM32 USART2
(PA2/PA3) remains available for the debug console.

The pump and glow inputs use pull-ups and interrupts on both edges. The
conditioned MCU signals are active low: falling means ON and rising means
OFF. Use the schematic's input frontends for vehicle signals. The firmware
records transitions and ignores repeated reads of an unchanged state.

Input `pull` and `activeLow` come from `pumpPulse` and `glowPlug` in
`device_tree.json`. Firmware applies them both during initial sampling and
in the interrupt handlers. The supplied assemblies retain the levels above.

## Measurements

Both thermocouples are type K. Firmware configures MCP9600 for 18-bit ADC,
0.0625°C ambient resolution and filter value `3`, then samples sensors every
500 ms when the main loop can run.

`dp_raw` is the ADC reading. `dp_voltage` reconstructs sensor voltage as
`dp_raw / 4095 × 3.3 × 1.515`, using the constants in [tracker.h](../tracker.h).
It is not yet calibrated to pressure units. Event records carry the latest
periodic voltage sample and its age; the ISR does not perform an ADC conversion.

GNSS is queried every 5 seconds and cellular location every 15 seconds when
the modem is ready. These operations may delay the main loop. A retained fix
can be old; use the validity, age and error fields described in
[telemetry](TELEMETRY.md). Cellular location is approximate.

## Modem and LED

The SIMCom A7670E/A7670X uses the HAL A76xx driver. Firmware powers it through
a relay, checks SIM/network/PDP readiness and connects MQTT over TLS.
`modem_reset` requests a relay power cycle. A rejected `CR_SIM_PIN` is not
sent again until the firmware reboots. Certificate installation and manual
AT diagnostics are in [the modem guide](A7670E.en.md).

| LED indication | Firmware state |
| --- | --- |
| Green, toggled every 250 ms | Connecting |
| Steady green | Connected |
| Red, toggled every 300 ms | Error |
| Purple during publish | Sending; returns to the previous state afterward |

The LED comes from the assembly's addressable status LED and color order.
Keep it connected when checking startup, connection and publishing.
