# Building and uploading the tracker

[Polski](BUILDING.pl.md) · [Project overview](../README.md)

Run these commands from the tracker repository root. Place JaszczurHAL next to
this repository, at `../JaszczurHAL`, and prepare its managed tools with `runmefirst.sh`
on Linux or `runmefirst.ps1` on Windows. Firmware uses the official Pico SDK
for RP2040 and the HAL STM32 build for STM32G474.

## Prepare Credentials

The firmware links `../Credentials`, outside this repository.
If that directory already exists, use its matching header and archive; the
setup command refuses to replace it. The repository's `Credentials/` is a
public template, not the active library.

For a fresh workspace, install a private copy:

```bash
./scripts/setup-credentials.sh
```

```powershell
py -3 scripts/setup_credentials.py
```

Edit `../Credentials/config/CredentialsData.local.h` and
`../Credentials/config/MacHostMapping.local.cpp`. Replace the
placeholders and set `CREDENTIALS_LOCAL_CONFIGURED` to `1`. The tracker reads
`CR_MQTT_BROKER_IP`, `CR_MQTT_BROKER_SECURE_PORT`, `CR_MQTT_USER`,
`CR_MQTT_PASSWORD`, and `CR_SIM_PIN` when needed. The modem also needs its
`ca.pem` certificate, installed separately as described in the
[modem guide](A7670E.en.md).

Build the archive for the assembly you will use:

```bash
../Credentials/scripts/build.sh rp2040
# For the nucleo assembly:
../Credentials/scripts/build.sh stm32g474
```

```powershell
py -3 ../Credentials/scripts/build.py rp2040
# For the nucleo assembly:
py -3 ../Credentials/scripts/build.py stm32g474
```

The manifest links `build/<target>/libCredentials.a` for the target of the
selected assembly (`rp2040` for `rp2040-zero`, `stm32g474` for `nucleo`),
relative to the installed library.
A missing STM32 archive must be built for that target; an RP2040 archive is
not interchangeable. Keep private configuration and archives out of Git.
See [the library guide](../Credentials/README.md) for all supported targets.

## Select an assembly and build

[device_tree.json](../device_tree.json) defines the hardware. The manifest
selects `rp2040-zero` by default. `nucleo` describes an STM32 build-check
assembly, with reduced RAM queues; it is not a confirmed hardware deployment.

```bash
../JaszczurHAL/vscode/entry/jh-vscode config-dump --project . --assembly rp2040-zero
../JaszczurHAL/vscode/entry/jh-vscode build --project . --assembly rp2040-zero
../JaszczurHAL/vscode/entry/jh-vscode refresh-intellisense --project . --assembly rp2040-zero
```

On Windows:

```powershell
& ..\JaszczurHAL\vscode\entry\jh-vscode.cmd build --project . --assembly rp2040-zero
```

Replace `rp2040-zero` with `nucleo` to build STM32. `--assembly` selects the
assembly for the command. `Project: Select board` saves a local selection in
`.vscode/jaszczurhal.local.json`, together with local port choices.

Outputs are under `.build/<target>/<assembly>/`: RP2040 produces
`firmware.uf2`, `firmware.elf` and `firmware.bin`; STM32 produces ELF and BIN.
Use `config-dump` to inspect resolved artifact paths and upload settings.

## Upload and debug

Use `Project: Build`, `Project: Build (Debug)`, `Project: Upload`,
`Project: Serial Monitor`, `Project: Debug Probe Monitor` and
`Project: Refresh IntelliSense` for the selected assembly.

RP2040 defaults to serial upload with USB identity checking. For an initial
BOOTSEL upload, use `Project: Upload (UF2 / BOOTSEL)`. `nucleo` uses OpenOCD
and ST-Link. `Project: Clear USB Identity` clears a remembered USB selection.

Run and Debug has launch profiles for RP2040-Zero with CMSIS-DAP and
NUCLEO-G474RE with ST-Link. The launch file points at each assembly's ELF.
Windows HAL setup configures the managed debugger paths.

The manifest and `.vscode/settings.json` are versioned. Serial ports and
local assembly choices belong in the ignored `.vscode/jaszczurhal.local.json`.
IntelliSense uses the compile database produced by `jh-vscode`, with no
CMake Tools configuration provider. After shared task changes, regenerate:

```bash
python3 scripts/sync_vscode_project.py
python3 scripts/sync_vscode_project.py --check
```

Use `py -3` instead of `python3` on Windows.

## Verification

Host checks do not require a modem, broker, database or private credentials:

```bash
python3 -m unittest discover -s tests -v
python3 backend/scripts/run_unit_tests.py
python3 backend/scripts/validate_migrations.py
```

On Linux, `test_gpio.py` also compiles the production sensor code with
native GCC or Clang C++ and checks both assemblies with altered pull and
polarity settings. This host probe is skipped on Windows; the Windows
workflow still builds both firmware assemblies.

Both [Linux](../.github/workflows/linux-firmware.yml) and
[Windows](../.github/workflows/windows-firmware.yml) CI run the same tooling
tests from `tests/`. These require CMake, Ninja and GNU Arm, available through
HAL's host configuration or `PATH`. They check Windows compiler paths,
including spaces and network shares, and build a temporary STM32 Credentials
archive with system tool lookup disabled. This also checks compiler discovery
in CMake's nested tests when only the selected toolchain is available.

The Windows firmware workflow
installs a fresh template with `scripts/setup_credentials.py --test-config`,
builds RP2040 and STM32 Credentials archives, builds both firmware assemblies
and refreshes IntelliSense. Test credentials are public fixtures and cannot
configure a deployed device. The setup refuses an existing destination.

For a physical check, verify the [status LED and sensors](HARDWARE.md),
MQTT connection and [payload fields](TELEMETRY.md), queue drain after a short
outage, and modem reset through `dpf/cmd`. Upload, electrical behavior and
live LTE/MQTT operation require separate hardware verification.
