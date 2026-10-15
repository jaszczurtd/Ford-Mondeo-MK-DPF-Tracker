# Kompilacja i wgrywanie trackera

[English](BUILDING.md) · [O projekcie](../README.pl.md)

Polecenia uruchamiaj z katalogu głównego trackera. Umieść JaszczurHAL w
`../libraries/JaszczurHAL` i przygotuj jego narzędzia przez `runmefirst.sh`
na Linuksie lub `runmefirst.ps1` na Windows. Firmware używa oficjalnego Pico SDK
dla RP2040 oraz kompilacji STM32 zapewnianej przez HAL dla STM32G474.

## Przygotowanie Credentials

Firmware linkuje `../libraries/Credentials`, poza tym repozytorium. Jeśli ten
katalog istnieje, używaj jego pasującego nagłówka i archiwum; instalator odmówi
zastąpienia go. Katalog `Credentials/` w repozytorium jest publicznym szablonem,
a nie aktywną biblioteką.

W nowym środowisku zainstaluj prywatną kopię:

```bash
./scripts/setup-credentials.sh
```

```powershell
py -3 scripts/setup_credentials.py
```

Edytuj `../libraries/Credentials/config/CredentialsData.local.h` i
`../libraries/Credentials/config/MacHostMapping.local.cpp`. Zastąp wartości
przykładowe i ustaw `CREDENTIALS_LOCAL_CONFIGURED` na `1`. Tracker odczytuje
`CR_MQTT_BROKER_IP`, `CR_MQTT_BROKER_SECURE_PORT`, `CR_MQTT_USER`,
`CR_MQTT_PASSWORD` oraz, gdy potrzeba, `CR_SIM_PIN`. Modem wymaga też certyfikatu
`ca.pem`, wgranego osobno według [instrukcji modemu](A7670E.pl.md).

Zbuduj archiwum dla wybranego montażu:

```bash
../libraries/Credentials/scripts/build.sh rp2040
# Dla montażu nucleo:
../libraries/Credentials/scripts/build.sh stm32g474
```

```powershell
py -3 ../libraries/Credentials/scripts/build.py rp2040
# Dla montażu nucleo:
py -3 ../libraries/Credentials/scripts/build.py stm32g474
```

Manifest linkuje `src/cortex-m0plus/libCredentials.a` dla RP2040 i
`build/stm32g474/libCredentials.a` dla STM32, względem zainstalowanej biblioteki.
Brakujące archiwum STM32 trzeba zbudować dla tego układu; archiwum RP2040 nie
jest zamiennikiem. Nie zapisuj prywatnej konfiguracji ani archiwów w Git.
Wszystkie obsługiwane platformy opisuje [instrukcja biblioteki](../Credentials/README.pl.md).

## Wybór montażu i kompilacja

[device_tree.json](../device_tree.json) określa sprzęt. Manifest domyślnie
wybiera `rp2040-zero`. Montaż `nucleo` służy kontroli kompilacji STM32 i ma
mniejsze kolejki RAM; nie jest potwierdzoną instalacją sprzętową.

```bash
../libraries/JaszczurHAL/vscode/entry/jh-vscode config-dump --project . --assembly rp2040-zero
../libraries/JaszczurHAL/vscode/entry/jh-vscode build --project . --assembly rp2040-zero
../libraries/JaszczurHAL/vscode/entry/jh-vscode refresh-intellisense --project . --assembly rp2040-zero
```

Na Windows:

```powershell
& ..\libraries\JaszczurHAL\vscode\entry\jh-vscode.cmd build --project . --assembly rp2040-zero
```

Zastąp `rp2040-zero` przez `nucleo`, aby zbudować STM32. `--assembly` wybiera
montaż dla polecenia. `Project: Select board` zapisuje lokalny wybór w
`.vscode/jaszczurhal.local.json`, obok lokalnych ustawień portów.

Wyniki trafiają do `.build/<target>/<assembly>/`: RP2040 tworzy `firmware.uf2`,
`firmware.elf` i `firmware.bin`; STM32 tworzy ELF i BIN. Polecenie `config-dump`
pokazuje rozwiązane ścieżki artefaktów i ustawienia wgrywania.

## Wgrywanie i debugowanie

Dla wybranego montażu używaj `Project: Build`, `Project: Build (Debug)`,
`Project: Upload`, `Project: Serial Monitor`, `Project: Debug Probe Monitor`
i `Project: Refresh IntelliSense`.

RP2040 domyślnie używa portu szeregowego z kontrolą tożsamości USB. Do pierwszego
wgrania przez BOOTSEL służy `Project: Upload (UF2 / BOOTSEL)`. `nucleo` korzysta
z OpenOCD i ST-Link. `Project: Clear USB Identity` kasuje zapamiętany wybór USB.

Widok Run and Debug zawiera profile uruchomienia RP2040-Zero z CMSIS-DAP
oraz NUCLEO-G474RE z ST-Link. Plik konfiguracji wskazuje ELF danego montażu.
Instalator HAL na Windows konfiguruje ścieżki narzędzi debuggera.

Manifest i `.vscode/settings.json` są w repozytorium. Porty szeregowe i lokalny
wybór montażu należą do ignorowanego pliku `.vscode/jaszczurhal.local.json`.
IntelliSense używa bazy kompilacji z `jh-vscode`, bez dostawcy konfiguracji
CMake Tools. Po zmianie współdzielonych zadań odtwórz pliki:

```bash
python3 scripts/sync_vscode_project.py
python3 scripts/sync_vscode_project.py --check
```

Na Windows używaj `py -3` zamiast `python3`.

## Weryfikacja

Testy hostowe nie wymagają modemu, brokera, bazy danych ani prywatnych danych:

```bash
python3 -m unittest discover -s tests -v
python3 backend/scripts/run_unit_tests.py
python3 backend/scripts/validate_migrations.py
```

CI dla [Linuksa](../.github/workflows/linux-firmware.yml) i
[Windows](../.github/workflows/windows-firmware.yml) uruchamia te same testy
narzędzi z `tests/`. Wymagają one CMake, Ninja i GNU Arm dostępnych przez
konfigurację hosta HAL lub `PATH`. Sprawdzają ścieżki kompilatorów Windows,
w tym ścieżki ze spacjami i udziały sieciowe, oraz budują tymczasowe archiwum
Credentials dla STM32 z wyłączonym szukaniem narzędzi w katalogach systemowych.
Sprawdza to również odnajdywanie kompilatora w wewnętrznych testach CMake,
gdy dostępny jest tylko wskazany toolchain.

Workflow Windows firmware
instaluje świeży szablon przez `scripts/setup_credentials.py --test-config`,
buduje archiwa Credentials dla RP2040 i STM32, oba montaże firmware'u oraz
bazy IntelliSense. Dane testowe są publiczne i nie służą konfiguracji urządzenia
w użyciu. Instalator odmawia nadpisania istniejącego katalogu.

Na sprzęcie sprawdź [diodę statusu i czujniki](HARDWARE.pl.md), połączenie MQTT,
[pola wiadomości](TELEMETRY.pl.md), opróżnianie kolejek po krótkiej przerwie
oraz restart modemu przez `dpf/cmd`. Wgrywanie, działanie obwodów i rzeczywista
łączność LTE/MQTT wymagają osobnej próby sprzętowej.
