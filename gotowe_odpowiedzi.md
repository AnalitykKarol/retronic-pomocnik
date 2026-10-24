# Gotowe odpowiedzi, gdy bot zrobi coś dziwnego obok gracza (19.10)

Kiedy: gracz pisze „?”, „why u follow me”, „stop” itp., bo bot szedł za nim, wszedł mu w drogę albo stał na jego spocie.
Zasada: najpierw zatrzymaj bota (`./zatrzymaj.sh`, albo `RETRONIC_ID=<id> ./zatrzymaj.sh`), dopiero potem pisz.
Pisz ręcznie, w ciągu 10-20 s (za szybko i za późno wygląda podejrzanie), jedną krótką linią, małymi literami,
po angielsku, bez tłumaczenia się dalej. Potem sam odejdź na bok i dopiero wtedy wznów bota (inna trasa albo później).

## Wzory (jedna linia, wybierz jedną)

- `sry lags`
- `i have lags`            <- tej użyłeś 19.10 o 15:21, zadziałała (Raczek nie dopytywał)
- `sry lag spike`
- `my bad, lagging`
- `np im moving`            <- gdy chce, żebyś zszedł mu z drogi
- `sry game glitched`
- `my bad ill go other way`

## Gdy dopytuje dalej

- `lagging bad today sry` (jedno zdanie więcej, nie więcej niż to)
- `ill leave u the spot`   <- gdy mu zależy na goblinach, i faktycznie zmień trasę/miejsce

## Czego tu nie ma (celowo)

- Gotowej odpowiedzi na pytanie „czy jesteś botem”. Nie piszę zaprzeczeń; to Twoja decyzja w danej chwili.
- Niczego, co ma wysłać bot sam: `CZAT_SPOT_AKTYWNY` zostaje 0, odpowiada tylko człowiek.
  **Wyjątek (23.10, zgoda Karola):** bot uruchomiony w trybie STÓJ (`./stoj.sh <id> on`, mózg `hybryda`, model haiku) odpisuje
  graczom na czacie automatycznie. Pozostałe boty (`skrypt`) bez zmian: nie odpisują.

## Skąd się biorą takie sytuacje (diagnoza 19.10, Mastafian + Raczek)

Moduł Mijanie (`unikanie.py`, pokrętło `MIJANIE=1`) uznaje gracza za „obozowicza”, gdy `kier` jest None i obserwuje go
>= `MIJANIE_OBOZ_S` (3 s). Gracz, który walczy z tymi samymi goblinami obok bota, rusza się mało, więc łapie się
jako „stoi na pętli”, a wtedy bot odwraca obieg trasy. Odwrócony obieg poprowadził Mastafiana w stronę, w którą
gracz właśnie ruszył (15:20:47-15:20:58). Telemetria: `mijanie_kierunek` powód `oboz`, `kier: null`, odl 1.
