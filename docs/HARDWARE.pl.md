# Połączenia i czujniki trackera

[English](HARDWARE.md) · [O projekcie](../README.pl.md)

Fizyczny tracker używa Waveshare RP2040-Zero. Montaż `nucleo` przypisuje
urządzenia do NUCLEO-G474RE w celu kontroli kompilacji; jego działanie
sprzętowe pozostaje niezweryfikowane. [device_tree.json](../device_tree.json)
określa połączenia używane przez firmware. [Schemat PDF](../materials/DPF_tracker/DPF_tracker.pdf)
pokazuje obwody wejściowe i zasilanie.

## Połączenia

| Sygnał | `rp2040-zero` | `nucleo` (złącze Arduino) |
| --- | --- | --- |
| MCP9600 SDA / SCL | GP0 / GP1, I2C0 | PB9 D14 / PB8 D15, I2C1 |
| UART TX / RX MCU do RX / TX modemu | GP4 / GP5, UART1 | PA9 D8 / PA10 D2, USART1 |
| Przekaźnik zasilania modemu | GP6 | PB5 D4 |
| Wejście pompki dozującej | GP2 | PB4 D5 |
| Wejście świecy żarowej | GP3 | PB10 D6 |
| ADC ciśnienia DPF | GP26 | PA0 A0 |
| Dioda statusu WS2812 | GP16, na płytce | PA8 D7, zewnętrzna |

I2C pracuje z częstotliwością 100 kHz. MCP9600 przed DPF ma adres `0x60`,
a kanał środkowy `0x67`. UART modemu używa 115200 baud, 8N1. USART2 na STM32
(PA2/PA3) pozostaje dostępny dla konsoli diagnostycznej.

Wejścia pompki i świecy mają podciąganie oraz przerwania na obu zboczach.
Sygnały po obwodach wejściowych są aktywne stanem niskim: zbocze opadające
oznacza ON, a narastające OFF. Sygnały samochodu podłączaj przez obwody ze
schematu. Firmware zapisuje zmiany, ignorując odczyty niezmienionego stanu.

## Pomiary

Obie termopary są typu K. Firmware ustawia MCP9600 na 18-bitowy ADC,
rozdzielczość temperatury otoczenia 0,0625°C i filtr `3`, po czym odczytuje
czujniki co 500 ms, gdy może wykonać się pętla główna.

`dp_raw` jest odczytem ADC. `dp_voltage` odtwarza napięcie czujnika jako
`dp_raw / 4095 × 3.3 × 1.515`, według stałych w [tracker.h](../tracker.h).
Wartość nie jest jeszcze skalibrowana do jednostek ciśnienia. Zdarzenia
zawierają ostatnią okresową próbkę napięcia i jej wiek; ISR nie wykonuje
konwersji ADC.

Gdy modem jest gotowy, GNSS jest odpytywany co 5 sekund, a lokalizacja
komórkowa co 15 sekund. Operacje mogą opóźniać pętlę główną. Zachowana pozycja
może być stara; uwzględniaj pola poprawności, wieku i błędu opisane w
[telemetrii](TELEMETRY.pl.md). Lokalizacja komórkowa jest przybliżona.

## Modem i dioda

SIMCom A7670E/A7670X korzysta ze sterownika A76xx w HAL. Firmware włącza
zasilanie przez przekaźnik, sprawdza gotowość SIM, sieci i PDP, a następnie
łączy MQTT przez TLS. `modem_reset` żąda cyklu wyłączenia zasilania modemu.
Odrzucony `CR_SIM_PIN` nie jest wysyłany ponownie aż do restartu firmware'u.
Wgrywanie certyfikatu i ręczną diagnostykę AT opisuje
[instrukcja modemu](A7670E.pl.md).

| Dioda | Stan firmware'u |
| --- | --- |
| Zielona, przełączana co 250 ms | Łączenie |
| Zielona stale | Połączenie aktywne |
| Czerwona, przełączana co 300 ms | Błąd |
| Fioletowa podczas publikacji | Wysyłanie; potem wraca poprzedni stan |

Firmware używa adresowalnej diody statusu i kolejności kolorów wskazanych
przez montaż. Pozostaw ją podłączoną podczas sprawdzania startu, łączenia
oraz publikowania wiadomości.
