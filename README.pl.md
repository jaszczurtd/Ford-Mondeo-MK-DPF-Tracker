# Mondeo DPF Tracker

[English](README.md)

Mondeo DPF Tracker rejestruje pracę DPF w Fordzie Mondeo MK4 2.0 TDCi.
Mierzy temperatury spalin i napięcie czujnika różnicy ciśnień, zapisuje zmiany
stanu pompki dozującej i świecy żarowej, a telemetrię wysyła przez modem LTE
do MQTT. Dane pomagają odtworzyć fabryczny cykl regeneracji i opracować
sterownik dla innego samochodu.

Fizyczny tracker używa Waveshare RP2040-Zero. Profil NUCLEO-G474RE służy
kontroli kompilacji STM32.
Firmware korzysta z [JaszczurHAL](https://github.com/jaszczurtd/JaszczurHAL)
i zewnętrznej biblioteki Credentials do przechowywania haseł. Dołączony szablon
pozwala zbudować tę bibliotekę z własnymi danymi.

## Od czego zacząć

- [Kompilacja, przygotowanie Credentials i wgrywanie](docs/BUILDING.pl.md)
- [Połączenia, czujniki i dioda statusu](docs/HARDWARE.pl.md)
- [Wiadomości MQTT, czas i limity kolejek](docs/TELEMETRY.pl.md)
- [Ręczny test MQTT/TLS na A7670E](docs/A7670E.pl.md)
- [Instalacja backendu, baza danych i API do odczytu](backend/README.pl.md)
- [Opis biblioteki Credentials](Credentials/README.pl.md)

Backend zapisuje surowe i znormalizowane wiadomości w PostgreSQL, rozdziela
uruchomienia urządzenia na sesje, tworzy okna analityczne i udostępnia HTTP API
do odczytu. Wizualizacja i automatyczne wykrywanie regeneracji są planowane.

Obie kolejki firmware'u znajdują się w RAM. Długa przerwa w łączności może je
zapełnić, a restart usuwa oczekujące dane. Do czasu kalibracji czujnika ciśnienie
jest podawane jako napięcie; ograniczenia czasowe opisuje dokument telemetrii.

## Pliki sprzętu

[Projekt KiCad](materials/DPF_tracker/DPF_tracker.kicad_pro),
[schemat](materials/DPF_tracker/DPF_tracker.kicad_sch) i jego
[wersja PDF](materials/DPF_tracker/DPF_tracker.pdf) są w `materials/DPF_tracker/`.
Połączenia używane przez firmware określa [device_tree.json](device_tree.json).

![Mondeo DPF Tracker](materials/20260604_013234.jpg)

Autor: Marcin "Jaszczur" Kielesinski.
