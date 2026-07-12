# Credentials template

This is a complete, buildable example for the `Credentials` library with secrets,
used by the Mondeo DPF Tracker. It contains no project author's secrets and no 
private encoding/decoding code. You have to fill it with your own data.

Create private configuration files first:

```bash
./scripts/configure.sh
```

Then edit `config/CredentialsData.local.h`: CR_MQTT_USER, CR_MQTT_PASSWORD

Build the archive required by an RP2040 project:

```bash
./scripts/build.sh rp2040
```

The result is `src/cortex-m0plus/libCredentials.a`. For STM32G474 use:

```bash
./scripts/build.sh stm32g474
```

The result is `build/stm32g474/libCredentials.a`.

`getCredential()` and `getWireguardPrivateKey()` return dynamically allocated
buffers. The caller must erase and `free()` them. The Tracker already follows
this contract.
