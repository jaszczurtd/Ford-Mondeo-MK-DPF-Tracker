# Telemetria MQTT

[English](TELEMETRY.md) · [O projekcie](../README.pl.md)

Firmware publikuje JSON na `dpf/data`, `dpf/events` i `dpf/status`, a polecenia
odbiera na `dpf/cmd`. [tracker.h](../tracker.h) definiuje tematy i limity;
[tracker.cpp](../tracker.cpp) tworzy wiadomości. Przykłady pokazują obecne pola,
nie zapis rzeczywistego przejazdu.

## Próbkowanie i buforowanie

Czujniki są odczytywane co 500 ms, a wiadomości `dpf/data` tworzone co 2000 ms.
Przy aktywnym połączeniu co 250 ms podejmowana jest próba publikacji jednej
wiadomości danych, a co 500 ms — paczki do 32 zdarzeń. Zapytania GNSS/lokalizacji
komórkowej i operacje modemu mogą blokować pętlę, więc są to odstępy nominalne.

| Kolejka | RP2040 | STM32G474 | Limit |
| --- | ---: | ---: | --- |
| Dane | 64 wiadomości | 8 wiadomości | 1536 bajtów na miejsce, razem z końcowym NUL |
| Zdarzenia | 1023 użyteczne rekordy | 255 użytecznych rekordów | Tablice 1024/256 miejsc; jedno pozostaje puste |

Po zapełnieniu obie kolejki zachowują stare rekordy i odrzucają nowe. Wiadomości
danych mające co najmniej 1536 bajtów także są odrzucane. Odrzucenia zwiększają
odpowiedni licznik; luki w numeracji zdarzeń mogą ujawniać utracone zbocza.
Rekordy opuszczają kolejkę dopiero po udanej publikacji MQTT. Kolejki są tylko
w RAM i znikają po restarcie. Nie gwarantują dostarczenia dokładnie raz ani
przetrwania dowolnie długiej przerwy w łączności.

## `dpf/data`

| Pole | Znaczenie |
| --- | --- |
| `version` | Wersja firmware’u (`VERSION`), nie osobna wersja schematu. |
| `time`, `ms` | Ostatni czas sieciowy ISO 8601 (pusty do uzyskania odczytu) i bieżący czas działania w ms. |
| `egt_pre`, `egt_mid`, `mcu_temp` | Temperatura przed DPF, w środkowym kanale DPF i MCU, w °C. |
| `dp_voltage`, `dp_raw` | Napięcie czujnika w V i odczyt ADC; bez kalibracji do jednostek ciśnienia. |
| `pump_onoff_period`, `pump_freq_hz` | Oba oznaczają częstotliwość w Hz mimo nazwy pierwszego pola; zero po 2 s bez zbocza ON. |
| `pump_cnt` | Zbocza ON od poprzedniego tworzenia wiadomości; licznik jest zerowany przy tworzeniu, również gdy wiadomość zostanie później odrzucona. |
| `pump`, `glow` | Bieżące stany: 1 = ON, 0 = OFF. |
| `pump_period_ms` | Odstęp między ostatnimi zboczami ON pompki, w ms; może zachować ostatnią wartość po zatrzymaniu. |
| `pump_last_on_ms`, `glow_dur` | Ostatni zakończony czas ON w ms. |
| `pump_current_on_ms`, `glow_current_on_ms` | Obecny czas ON w ms; zero przy OFF. |
| `data_queue_len`, `event_queue_len` | Długości kolejek przy tworzeniu wiadomości, przed dodaniem jej do kolejki danych. |
| `data_overflow_count`, `event_overflow_count` | Łączne odrzucenia w tym uruchomieniu; dane obejmują też zbyt duże wiadomości. |
| `gnss_valid`, `gnss_powered`, `gnss_error`, `gnss_age_ms` | Flagi poprawności pozycji i zasilania (0/1), ostatni wynik HAL, wiek poprawnej pozycji w ms (-1 bez pozycji). |
| `gnss_lat`, `gnss_lng` | Stopnie; pola pomijane bez poprawnej pozycji. |
| `gnss_speed_kmh`, `gnss_alt_m`, `gnss_course_deg`, `gnss_hdop` | Prędkość, wysokość, kurs i HDOP; -1 przy braku wartości. |
| `gnss_sats_used`, `gnss_sats_view`, `gnss_fix_mode` | Liczby używanych/widocznych satelitów i tryb pozycji modemu; -1 bez poprawnej pozycji. |
| `gnss_utc` | Tekst czasu UTC z modemu, dodawany tylko gdy dostępny z poprawną pozycją. |
| `cell_valid`, `cell_error`, `cell_age_ms`, `cell_speed_kmh` | Flaga lokalizacji komórkowej, ostatni wynik HAL, wiek w ms i prędkość w km/h; niedostępny wiek/prędkość to -1. |
| `cell_lat`, `cell_lng`, `cell_acc_m` | Przybliżone współrzędne w stopniach i dokładność w m; tylko przy poprawnej lokalizacji komórkowej. |

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

Czas sieciowy jest odświeżany mniej więcej raz na minutę przy połączonym MQTT;
`time` zawiera ostatni odczyt, nie niezależnie odmierzany czas próbki.
Do odstępów w jednym uruchomieniu używaj `ms`. GNSS i lokalizacja komórkowa
mogą zachować poprzednią poprawną pozycję po błędzie odczytu: sprawdzaj wiek
i błąd obok flagi poprawności. Lokalizacja komórkowa nie daje dokładnej trasy.

## `dpf/events`

Wejścia pompki i świecy tworzą zdarzenia na obu zboczach: `state=1` oznacza ON,
a `state=0` — OFF. Przerwanie bez zmiany stanu nie dodaje zdarzenia.
Przykład zawiera dwa różne źródła w jednej paczce:

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

| Pole | Znaczenie |
| --- | --- |
| `version`, `ms` | Wersja firmware’u i czas działania przy tworzeniu paczki |
| `batch_count`, `queue_len` | Liczba rekordów paczki i długość kolejki w chwili odczytu |
| `queue_remaining_after_batch` | Odczytana długość minus paczka; ISR mógł już dodać nowe zdarzenia |
| `overflow_count` | Łączna liczba odrzuconych zdarzeń od startu |
| `seq` | Numer 32-bitowy od zera; rośnie także przy odrzuceniu zdarzenia z pełnej kolejki |
| `t_us`, `t_ms` | 32-bitowy znacznik zbocza w mikrosekundach i wynik jego dzielenia całkowitego przez 1000 |
| `src`, `state` | `pump` lub `glow` oraz 1/0 ON/OFF |
| `gnss_speed_kmh` | Ostatnia zapamiętana prędkość GNSS przy zboczu, -1 przy braku; bez wieku pozycji |
| `dp_voltage` | Ostatnia okresowa próbka napięcia; nie odczyt ADC w ISR |
| `dp_sample_age_ms` | Wiek próbki napięcia, ograniczony do 65534 ms; -1 przy braku |

`t_us` zawija się co 2^32 µs (około 71,6 minuty), a `t_ms` zdarzenia razem z nim.
Nie jest zamiennikiem głównego `ms`, który zawija się po około 49,7 dnia.
`seq` także się zawija i zeruje przy restarcie. Przed zestawieniem zdarzeń
z telemetrią uwzględnij zawinięcia, paczki i granice uruchomień. Czas paczki
opisuje jej przygotowanie do wysłania; znaczniki zboczy mogą pochodzić
z wcześniejszej aktywności oczekującej w kolejce.

## Status i polecenie

Po połączeniu MQTT firmware publikuje:

```json
{
  "status": "online"
}
```

Po rzeczywistym timeout watchdog publikuje dodatkowo jeden status na uruchomienie:

```json
{
  "status": "watchdog_reset",
  "reason": "watchdog",
  "version": "v0.5",
  "ms": 12345
}
```

Inne przyczyny resetu, w tym programowe restarty do wgrywania/BOOTSEL,
nie są zgłaszane jako watchdog. `dpf/cmd` przyjmuje dokładnie tekst
`modem_reset`, który żąda cyklu wyłączenia zasilania modemu przez przekaźnik.

## Wykorzystanie danych

Do analizy regeneracji łącz trendy temperatury/napięcia z `dpf/data`
z czasem pracy urządzeń z `dpf/events`. Projekt nie implementuje jeszcze
automatycznego wykrywania cykli ani kalibracji ciśnienia. Monitoruj długości
obu kolejek i liczniki przepełnienia, a surowe wiadomości zachowuj do ponownej
analizy.

[Instrukcja backendu](../backend/README.pl.md) opisuje wnioskowanie o sesjach
i okna analityczne. Okna używają obecnie czasu odbioru na serwerze, więc mogą
inaczej grupować zaległe dane niż wynikałoby to z czasu ich zebrania.
