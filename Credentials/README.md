# Credentials template

This is a complete, buildable example for the `Credentials` library with secrets,
used by the Mondeo DPF Tracker. It contains no project author's secrets and no 
private encoding/decoding code. You have to fill it with your own data.

Create private configuration files first. The Python entrypoint works in
PowerShell, cmd and POSIX shells and never overwrites existing local files:

```powershell
py -3 scripts/configure.py
```

```bash
./scripts/configure.sh
```

Then edit `config/CredentialsData.local.h`: CR_MQTT_USER, CR_MQTT_PASSWORD

Build the archive required by an RP2040 project. The builder uses the managed
JaszczurHAL CMake, Ninja and GNU Arm tools when its host environment is
available, and otherwise resolves them from `PATH`:

```powershell
py -3 scripts/build.py rp2040
```

```bash
./scripts/build.sh rp2040
```

The result is `src/cortex-m0plus/libCredentials.a`. For STM32G474 use:

```bash
./scripts/build.sh stm32g474
```

The result is `build/stm32g474/libCredentials.a`.

The builder locates JaszczurHAL next to the installed `Credentials` directory.
For a different workspace layout, pass
`--jaszczurhal-root /path/to/JaszczurHAL`.

CI may create a fresh template with `scripts/configure.py --test`. That option
uses only tracked, reserved example values (`example.invalid`, RFC 5737 IP
addresses and a locally administered MAC). It refuses to run over any existing
local configuration and must not be used for deployed firmware.

`getCredential()` and `getWireguardPrivateKey()` return dynamically allocated
buffers. The caller must erase and `free()` them. The Tracker already follows
this contract.
