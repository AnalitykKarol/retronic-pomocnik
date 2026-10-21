---
name: pilnuj-botow
description: Use when Karol wants the Retronic bots watched — "pilnuj botów", "obchód botów", "sprawdź boty", "co z botami", "jak idą boty", or as the body of `/loop 10m /pilnuj-botow`. One read-only round over all game instances (bot, HP, alarms, stuck, trips to town, players), a short report in chat and a desktop notification for anything critical. Never touches the game, the bots or their settings without Karol's explicit "tak" in this session. Private project: nothing to Notion or Slack.
---

# Obchód botów Retronic

Projekt prywatny Karola. Nic do Notion ani Slacka, nie pytaj o zapis. Kod i stan: `~/Games/Retronic/pomocnik/`.
Spec: `dane_tibia/SPEC_nadzorca_zestawu_1021.md`, tu warstwa C w wersji ręcznej: **tylko ocena i powiadomienia**.
Naprawy wolno wykonać dopiero po „tak” Karola w tej sesji.

## Jeden obchód

1. Stan wszystkich instancji, jedno polecenie (ok. 0,5 s, tylko odczyt):

       cd ~/Games/Retronic/pomocnik && python3 -I nadzor_stan.py

   `--json` daje pełne dane z ostatnimi liniami logu; `--okno 20` przegląda dłuższy kawałek logu (domyślnie 12 min).
2. Dla każdej linii `KRYTYCZNE` i dla niejasnej `UWAGA` sprawdź źródło, zanim cokolwiek powiesz:
   - log bota: najnowszy `instancje/<id>/logi/mozg-stdout-*.log` (pomiń `[OGIEN]` i `debug:`);
   - ekran, gdy trzeba zobaczyć (lista postaci, śmierć, rozłączenie, gracz obok):

         WAYLAND_DISPLAY=$(cat $XDG_RUNTIME_DIR/retronic-sesja-<id>/wayland) grim /tmp/claude-$(id -u)/retronic-<id>.png

     i obejrzyj plik narzędziem do czytania obrazów. W grze = ikony paska klienta w prawym górnym rogu.
3. Powiadomienie na pulpit **tylko** przy nowym problemie krytycznym (czas linii późniejszy niż poprzedni obchód):

       notify-send -u critical "Retronic [<id>]" "<jedno zdanie: co i gdzie>"

4. Raport w czacie, najwyżej ok. 10 linii: jedna linia na instancję (lvl, HP, mapa, zabicia w oknie), pod nią tylko to, co
   nowe albo wymaga Karola. Gdy wszystko gra, wystarczy jedno zdanie „6/6 expi, bez alarmów”.
   Przy problemie podaj propozycję naprawy z dokładnym poleceniem i czekaj na „tak”.

## Co jest krytyczne

- `ALARM_GM` / gracz pisze do postaci („bot?”, pytania). Bot sam robi pauzę. **Nie odpisuj** w grze. Powiadom Karola.
- PK, atak gracza, czaszka odczytana (nie „nieczytelne”).
- HP < 40% albo spada, a postać nie ma leczenia (patrz niżej), zgon (HP 0%, ekran wyboru postaci, `UCIECZKA HP 0%` w kółko).
- Gra nie działa (klient padł) albo instancja nie odpowiada.

## Co jest UWAGĄ (raport, bez powiadomienia, chyba że trwa > 20 min)

- Bot nie działa, a nie ma `STOP_RECZNY`.
- Brak zabić > 10 min, stoi w miejscu > 3 min poza walką, stara telemetria (zawieszony proces).
- Niespodziewana wyprawa do miasta (`Wyprawa: start`, `WZNOWIONA`). 21.10 przyczyną były `WYPRAWA_BLANKI=1` i
  `WYPRAWA_DEPO_BLANKI=1` skopiowane z Mastafiana. Naprawa (po „tak”): wyłączyć oba w `instancje/<id>/na_zywo.json`
  (kopia `*.bak-<data>-blanki`), przy aktywnej wyprawie w `wyprawa_stan.json` ustawić `aktywna: false`, `faza: null`, restart bota.
- `Loot: brak_plecaka`: Karol musi otworzyć plecak w podglądzie, bot nie musi stawać.
- `[RATUNEK] cień: S3/S4`, `[ORBITA]`, `NIEUDANE` przejście pięter: pojedyncze wpisy to szum, kilka w oknie = zgłoś.
- Dwa boty na tej samej mapie: widzą się nawzajem (czaszki, unikanie) i to wygląda na boty.
- Dobicie < 60% (porzucane uciekające moby; częste przy tłoku i dziurach).

## Wiedza o postaciach (stan 21.10, sprawdzaj, bo się zmienia)

- Postacie na Rooku (kutangen, kolanoth, bober, wydra, dawajkesh) nie mają profesji, więc `exura` u nich nie działa i leczy je
  tylko jedzenie. Kutangen zginął 20.10 przez truciznę bez leczenia.
- Invincible (Thais, `trolle_patrol`, tryb `ostrozny,ml`) uczy się magii przez `utevo lux`; `exura` dopiero od 2 poziomu
  magii. Do tego czasu „ZDROWIE: czar 'exura' nie działa” jest oczekiwane.
- `STOP_RECZNY` bez procesu bota = **Karol gra ręcznie**. Tylko patrz, niczego nie proponuj dla tej postaci.

## Zakazy (bez wyjątków)

- Nie piszesz na czacie gry, nie wysyłasz klawiszy ani klików do gry.
- Bez „tak” Karola: nie zatrzymujesz, nie uruchamiasz i nie zamykasz botów ani sesji (`zatrzymaj.sh`, `uruchom_instancje.sh`,
  `sesja_gry.py`, `wroc.sh`, `refill.sh`), nie zmieniasz `na_zywo.json`, `mapy.json`, `tryby.json`, nie ruszasz plików `STOP*`.
  Zgoda dotyczy jednej akcji, nie kolejnych.
- Reguła bota: przy zacięciu proponuj **naprawę, nie zatrzymanie** (`CLAUDE.md` bota). Wyjątek: zagrożenie życia postaci.
- Nie używaj `pkill -f` / `pgrep -f` z wzorcem we własnej komendzie i nie grepuj procesów po `RetronicGL-`
  (stary kod bota mylił wtedy okno gry).
- Nic do Notion, Slacka ani maili.

## Wywołanie

- Jeden obchód w dowolnej sesji Claude: `/pilnuj-botow`.
- Ciągłe pilnowanie: osobna sesja, np. `cd ~/Games/Retronic/pomocnik && claude --model sonnet`, w niej `/loop 10m /pilnuj-botow`.
  Pętla działa, dopóki sesja jest otwarta. Docelowo (spec, F4) obchód z timera jako świeże wywołanie.
