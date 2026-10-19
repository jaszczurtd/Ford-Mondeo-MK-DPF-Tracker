# Szablon biblioteki Credentials

[English](README.md)

Szablon implementuje publiczne API Credentials bez sekretów autora i jego
prywatnego kodowania danych. Uzupełnij własne wartości i zbuduj archiwum dla
platformy firmware'u. Dane są przechowywane bez szyfrowania.

## Konfiguracja prywatnej kopii

Instalator trackera kopiuje ten katalog do `../Credentials`
i odmawia nadpisania istniejącego katalogu. Jeśli kopiujesz szablon samodzielnie,
uruchom z katalogu Credentials:

```bash
./scripts/configure.sh
```

```powershell
py -3 scripts/configure.py
```

Edytuj oba pliki: `config/CredentialsData.local.h` oraz
`config/MacHostMapping.local.cpp`. Zastąp przykładowe wartości i ustaw
`CREDENTIALS_LOCAL_CONFIGURED` na `1`. Zwykła konfiguracja zachowuje istniejące
pliki lokalne. Nie dodawaj konfiguracji prywatnej ani archiwów do Git.

Dla trackera uzupełnij `CR_MQTT_BROKER_IP`, `CR_MQTT_BROKER_SECURE_PORT`,
`CR_MQTT_USER`, `CR_MQTT_PASSWORD` i `CR_SIM_PIN`, jeśli wymaga go karta SIM.
Tracker używa pliku `ca.pem` zapisanego w modemie; ustawienie `CR_CA_CERT`
w bibliotece nie wgrywa tego pliku.

## Kompilacja dla platformy firmware'u

```bash
./scripts/build.sh rp2040
```

```powershell
py -3 scripts/build.py rp2040
```

| Platforma | Archiwum |
| --- | --- |
| `rp2040`, `rp2350-arm`, `rp2350-riscv`, `stm32g474`, `esp32`, `esp32s3` | `build/<target>/libCredentials.a` |

Skrypt szuka JaszczurHAL obok zainstalowanego katalogu Credentials. Przy innym
układzie podaj `--jaszczurhal-root /path/to/JaszczurHAL`. Korzysta z CMake,
Ninja i kompilatorów zarządzanych przez HAL, jeśli są dostępne; w przeciwnym
razie szuka narzędzi w `PATH`.
Podczas budowania dla RP i STM32 dodaje katalog wybranego kompilatora na
początek `PATH` procesów kompilacji. Dzięki temu wewnętrzne testy CMake
znajdują te same narzędzia, bez zmiany środowiska Twojej powłoki.

Platformy RP używają toolchainu Pico SDK wybranego dla danej platformy,
a STM32 — pliku toolchainu HAL. `rp2350-riscv` korzysta z wersji narzędzi
RISC-V wskazanej przez HAL. Kompilacja ESP używa ESP-IDF z HAL i jego domyślnej
konfiguracji, w tym picolibc; potrzebne narzędzia są przygotowywane przy
pierwszym użyciu. Archiwum buduj dla tego samego układu i zgodnej konfiguracji
SDK/ABI co firmware.

Obecny JaszczurHAL obsługuje archiwa przez `JH_LINK_LIBRARIES` i nagłówki przez
`JH_EXTRA_INCLUDES` na RP, STM32 oraz ESP. Ustaw te ścieżki w manifeście aplikacji.
Manifest trackera wybiera tylko RP2040 i STM32G474; pozostałe platformy
biblioteki nie dodają montaży trackera.

## API i czas życia buforów

Używaj nagłówka i archiwum z tej samej kompilacji biblioteki. Publiczny nagłówek
to [src/Credentials.h](src/Credentials.h); nagłówek główny dołącza ten plik.

- `getCredential()` zwraca zaalokowany tekst albo `NULL` przy błędnym ID lub
  nieudanej alokacji. Wymaż sekret i zwolnij bufor przez `free()` po użyciu.
- `getWireguardPrivateKey()` także zwraca zaalokowany bufor, mimo typu
  `const char *`; wywołujący musi go wymazać i zwolnić. Nieznany MAC daje `NULL`.
- `getFriendlyHostname()` i `getWireguardLocalIP()` zwracają tekst należący do
  biblioteki. Nie zwalniaj go. Zastępcza nazwa hosta korzysta ze współdzielonego
  bufora statycznego, nadpisywanego przy kolejnym takim odczycie; brak IP daje `NULL`.
- `getCredentialInt()` konwertuje przez `atoi()` i zwraca `-1`, gdy nie uzyska
  tekstu. Nie sprawdza składni liczby. `getSwitchesNumber()` zwraca `0` dla
  nieznanego MAC. `initCredentials()` w tym szablonie nic nie wykonuje.

Tracker wymazuje i zwalnia pobrane sekrety. W innych aplikacjach zachowaj te
same zasady własności buforów.

## Publiczna konfiguracja testowa

`scripts/configure.py --test` używa publicznych danych testowych z zastrzeżonymi
adresami, bez rzeczywistych sekretów. Odmawia działania, gdy istnieje choć
jeden plik konfiguracji lokalnej. Instalator trackera udostępnia tę opcję jako
`scripts/setup_credentials.py --test-config` dla nowego katalogu docelowego.
Używaj tych wartości tylko w automatycznych testach kompilacji, nie w urządzeniu.
