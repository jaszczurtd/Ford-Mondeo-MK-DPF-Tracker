# Backend DPF

[English](README.md) · [O projekcie](../README.pl.md)

Backend zapisuje wiadomości MQTT trackera w PostgreSQL, normalizuje telemetrię
i zdarzenia urządzeń, rozpoznaje sesje uruchomień, oblicza okna analityczne
oraz udostępnia HTTP API do odczytu. Wizualizacja, wykrywanie regeneracji,
publikowanie poleceń, retencja i cykliczne odświeżanie okien nie są jeszcze
zaimplementowane.

Wszystkie polecenia uruchamiaj z katalogu głównego repozytorium, o poziom wyżej
niż `backend/`. Pola i limity firmware'u opisuje [telemetria](../docs/TELEMETRY.pl.md).

## Instalacja i konfiguracja

Użyj Pythona 3.11 lub nowszego. Polecenia bazodanowe wymagają też klienta `psql`
oraz istniejącej bazy i użytkownika z prawem tworzenia schematu. Zależności
pakietu deklaruje [pyproject.toml](pyproject.toml).

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install -e backend
```

Użyj [.env.example](.env.example) jako listy ustawień, zastąp wartości przykładowe,
a prywatną konfigurację zapisz w `/etc/dpf-backend.env`. Aplikacje wczytują ten
plik automatycznie; zmienne wyeksportowane w powłoce mają pierwszeństwo.
`DPF_ENV_FILE` wskazuje inny plik. `.env.example` nie jest wczytywany
samoczynnie, a loader nie rozwija wyrażeń powłoki ani zmiennych w wartościach.

| Ustawienie | Znaczenie |
| --- | --- |
| `DPF_DATABASE_URL` | URL połączenia z przygotowaną bazą PostgreSQL |
| `DPF_MQTT_HOST`, `DPF_MQTT_PORT` | Adres brokera; domyślny port 8883 |
| `DPF_MQTT_TLS`, `DPF_MQTT_CA_FILE` | Włączenie TLS i ścieżka czytelnego pliku CA |
| `DPF_MQTT_USERNAME`, `DPF_MQTT_PASSWORD` | Dane logowania brokera, jeśli wymagane |
| `DPF_MQTT_CLIENT_ID`, `DPF_DEVICE_ID` | ID klienta odbiornika i etykieta urządzenia zapisywana z rekordami |
| `DPF_API_HOST`, `DPF_API_PORT` | Adres nasłuchu API; domyślnie `127.0.0.1:8090` |

Ustaw `DPF_MQTT_CA_FILE`, aby weryfikować certyfikat, i użyj zgodnego z nim
adresu brokera. Przy włączonym TLS bez pliku CA obecny odbiornik wyłącza
weryfikację certyfikatu. To różni się od konfiguracji modemu trackera.
ID urządzenia pochodzi z ustawień backendu; współdzielone tematy `dpf/*`
nie rozpoznają automatycznie kilku trackerów.

## Baza danych i pierwszy odbiór

Zastosuj obie migracje do skonfigurowanej bazy:

```bash
PYTHONPATH=backend/src backend/.venv/bin/python backend/scripts/apply_migrations.py
```

Skrypt odczytuje `DPF_DATABASE_URL` przez loader konfiguracji i uruchamia `psql`.
[001_initial_schema.sql](db/migrations/001_initial_schema.sql) tworzy `raw_mqtt`,
`boot_sessions`, `telemetry_data`, `actuator_events`, `status_events` i
`schema_migrations`. [002_telemetry_windows.sql](db/migrations/002_telemetry_windows.sql)
dodaje `telemetry_windows`. Domyślne przykładowe dane nie tworzą bazy ani konta.

W osobnej bazie testowej możesz wstawić przykłady bez MQTT:

```bash
PYTHONPATH=backend/src backend/.venv/bin/python backend/scripts/ingest_sample.py --topic dpf/data
PYTHONPATH=backend/src backend/.venv/bin/python backend/scripts/ingest_sample.py --topic dpf/events
PYTHONPATH=backend/src backend/.venv/bin/python backend/scripts/ingest_sample.py --topic dpf/status
```

Polecenia zapisują dane do skonfigurowanej bazy. Rzeczywisty odbiór uruchom przez:

```bash
backend/.venv/bin/dpf-mqtt-ingestor
```

Proces subskrybuje `dpf/data`, `dpf/events` i `dpf/status` z QoS 1.
Zapis dodaje surowy rekord ze statusem parsowania, a potem rekordy znormalizowane,
w jednej transakcji. Nieudana transakcja cofa oba etapy; zapis surowych danych
nie jest osobnym trwałym krokiem. Odbiornik nie publikuje poleceń.

## Odbiornik jako usługa

Najpierw potwierdź odbiór na pierwszym planie z rzeczywistymi ustawieniami MQTT
i bazy. [Instalator](scripts/install_systemd_service.sh) oraz
[przykładowa jednostka](deploy/dpf-mqtt-ingestor.service.example) zakładają konto
`pi` na Raspberry Pi. Konto potrzebuje dostępu do repozytorium, virtualenv,
certyfikatu CA i `/etc/dpf-backend.env`. Prywatny plik należący do root można
udostępnić do odczytu grupie, np. `dpf-backend`, z prawami `0640`;
dodaj `pi` do grupy i zaloguj się ponownie przed próbą na pierwszym planie.

Podaj rzeczywistą ścieżkę bezwzględną repozytorium:

```bash
bash backend/scripts/install_systemd_service.sh /home/pi/Documents/Ford-Mondeo-MK-DPF-Tracker
sudo systemctl start dpf-mqtt-ingestor
sudo systemctl status dpf-mqtt-ingestor
```

Instalator sprawdza plik konfiguracji i program, zapisuje jednostkę przez `sudo`,
przeładowuje systemd i **włącza automatyczny start**. Nie uruchamia usługi;
robi to drugie polecenie. Na hoście bez konta `pi` dostosuj użytkownika i ścieżki
przed instalacją. Jednostka uruchamia wyłącznie odbiornik MQTT.

## Sesje i okna analityczne

Nowe znormalizowane rekordy otrzymują `boot_session_id`. Rozpoznawanie sesji
zaczyna nową sesję przy pierwszym rekordzie, statusie watchdog, spadku `ms`
lub `seq`, a także po przerwie ponad 30 minut z czasem działania poniżej
5 minut. To heurystyka: opóźnione lub przestawione wiadomości i zawinięcia
liczników mogą wyglądać jak restart. Starsze nieprzypisane rekordy mogą mieć `NULL`.

Odśwież oba rozmiary okien (10 i 60 sekund) albo wybierz jeden:

```bash
PYTHONPATH=backend/src backend/.venv/bin/python backend/scripts/refresh_windows.py
PYTHONPATH=backend/src backend/.venv/bin/python backend/scripts/refresh_windows.py --bucket-seconds 10
```

Okna zawierają temperatury, napięcie, prędkość, aktywność pompki/świecy, flagi
przepełnienia i nachylenia trendów. Grupowanie używa **czasu odbioru na serwerze**
w obrębie urządzenia i sesji, więc zaległości po przerwie mogą zniekształcać
trendy czasu pomiaru. Odświeżenie przebudowuje wybrany rozmiar; nie uruchamia się
automatycznie. Ta operacja nie klasyfikuje cykli regeneracji.

## HTTP API do odczytu

Uruchom API na pierwszym planie:

```bash
backend/.venv/bin/dpf-api
```

Domyślny adres to `127.0.0.1:8090`. Repozytorium nie dostarcza jednostki systemd,
reverse proxy ani uwierzytelniania dla API. Udostępnienie go poza hostem wymaga
osobnego przygotowania względem tej lokalnej procedury odczytu.

| Endpoint | Wynik i opcjonalne filtry |
| --- | --- |
| `GET /health` | Stan procesu i wersja; bez zapytania do bazy |
| `GET /status` | Liczby rekordów i ostatnie czasy odbioru |
| `GET /raw-mqtt/recent` | Surowe rekordy; `topic`, `device_id`, `limit` |
| `GET /telemetry` | Telemetria; `from`, `to`, `device_id`, `boot_session_id`, `limit` |
| `GET /windows` | Okna; `bucket_seconds`, `from`, `to`, `device_id`, `boot_session_id`, `limit` |
| `GET /boot-sessions` | Sesje; `device_id`, `limit` |

Odpowiedzi list zawierają `count` i `rows`. `limit` domyślnie wynosi 100,
a dopuszcza 1–1000. Filtry czasu używają ISO 8601: telemetria filtruje
`received_at`, a okna `window_start`. Domyślny rozmiar okna to 10 sekund;
rekordy istnieją tylko dla wygenerowanych rozmiarów. Błędy bazy dają HTTP 503.

```bash
curl 'http://127.0.0.1:8090/health'
curl 'http://127.0.0.1:8090/telemetry?limit=100&from=2026-06-20T10:00:00Z&to=2026-06-20T11:00:00Z'
```

## Testy i diagnostyka Raspberry Pi

Testy hostowe i walidacja SQL nie łączą się z działającą bazą ani brokerem:

```bash
python3 -m compileall backend/src backend/tests
python3 backend/scripts/run_unit_tests.py
python3 backend/scripts/validate_migrations.py
PYTHONPATH=backend/src python3 -m dpf_backend.ingest.mqtt_ingestor --help
PYTHONPATH=backend/src python3 -m dpf_backend.api.server --help
```

Na docelowym Pi uruchom osobną diagnostykę:

```bash
backend/.venv/bin/python backend/scripts/diagnose_pi.py
```

Sprawdza środowisko, polecenia, połączenie PostgreSQL, migracje/tabele, liczby
rekordów, świeżość odbioru, przypisanie sesji, okna, usługę odbiornika i API.
Użyj `--skip-api` lub `--skip-systemd` przy częściowym wdrożeniu,
`--stale-after-seconds 600`, aby wybrać próg świeżości, albo `--strict-warnings`,
aby ostrzeżenia kończyły polecenie błędem. `FAIL` zawsze daje niezerowy kod;
same ostrzeżenia zwykle pozostawiają zero.

Testy jednostkowe i walidacja migracji nie potwierdzają zastosowania migracji,
automatycznego startu usługi, rzeczywistego MQTT ani działania API na serwerze.
