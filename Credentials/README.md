# Credentials library template

[Polski](README.pl.md)

This template implements the public Credentials API without the author's
secrets or private encoding code. Fill it with your own data and build an
archive for the target firmware. Values are stored without encryption.

## Configure a private copy

The tracker installer copies this directory to `../libraries/Credentials`
and refuses an existing destination. If you copied the template yourself,
run from the Credentials directory:

```bash
./scripts/configure.sh
```

```powershell
py -3 scripts/configure.py
```

Edit both `config/CredentialsData.local.h` and
`config/MacHostMapping.local.cpp`. Replace the example values and set
`CREDENTIALS_LOCAL_CONFIGURED` to `1`. Normal configuration preserves
existing local files. Keep local configuration and generated archives out of Git.

For the tracker, configure `CR_MQTT_BROKER_IP`, `CR_MQTT_BROKER_SECURE_PORT`,
`CR_MQTT_USER`, `CR_MQTT_PASSWORD`, and `CR_SIM_PIN` if the SIM requires it.
The tracker uses `ca.pem` already stored in the modem; configuring `CR_CA_CERT`
in this library does not upload that file.

## Build for the firmware target

```bash
./scripts/build.sh rp2040
```

```powershell
py -3 scripts/build.py rp2040
```

| Target | Archive |
| --- | --- |
| `rp2040` | `src/cortex-m0plus/libCredentials.a` |
| `rp2350-arm`, `rp2350-riscv`, `stm32g474`, `esp32`, `esp32s3` | `build/<target>/libCredentials.a` |

The builder locates JaszczurHAL next to the installed Credentials directory.
For another layout, pass `--jaszczurhal-root /path/to/JaszczurHAL`.
It uses HAL-managed CMake, Ninja and compilers where available, otherwise
resolving tools from `PATH`.

RP targets use the Pico SDK toolchain selected for their platform; STM32 uses
the HAL toolchain file. `rp2350-riscv` uses the RISC-V toolchain version selected
by HAL. ESP builds use HAL's ESP-IDF and its default configuration, including
picolibc, and prepare the required tools on first use. Build the archive for
the same target and compatible SDK/ABI configuration as the firmware.

Current JaszczurHAL supports precompiled archives through `JH_LINK_LIBRARIES`
and headers through `JH_EXTRA_INCLUDES` for RP, STM32 and ESP. Set those paths
in the consuming project's manifest. The tracker's manifest selects only
RP2040 and STM32G474; the other library targets do not add tracker assemblies.

## API and buffer lifetime

Use the header and archive from the same library build. The public header is
[src/Credentials.h](src/Credentials.h); the root header forwards to it.

- `getCredential()` returns an allocated string or `NULL` for an invalid ID
  or allocation failure. Erase secret data and `free()` the buffer after use.
- `getWireguardPrivateKey()` also returns an allocated buffer, despite its
  `const char *` return type; the caller must erase and free it. Unknown MACs
  return `NULL`.
- `getFriendlyHostname()` and `getWireguardLocalIP()` return borrowed strings.
  Do not free them. The fallback hostname uses a shared static buffer and is
  replaced by the next fallback lookup; unknown local IPs return `NULL`.
- `getCredentialInt()` converts with `atoi()`, returning `-1` when no string
  is available. It does not validate numeric syntax. `getSwitchesNumber()`
  returns `0` for an unknown MAC. `initCredentials()` is a no-op in this template.

The tracker erases and frees the secret strings it requests. Treat other
consumers according to the same buffer ownership rules.

## Public test configuration

`scripts/configure.py --test` uses tracked example fixtures with reserved
addresses and no real secrets. It refuses to run over either existing local
configuration file. The tracker wrapper exposes this as
`scripts/setup_credentials.py --test-config` for a fresh destination.
Use these values only for automated build tests, not deployed devices.
