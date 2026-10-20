# Retronic pomocnik: start headless + podgląd (czytaj ZANIM cokolwiek uruchomisz)

Karol codziennie prosi o "odpal headless i podgląd". Poprawny sposób, sprawdzony 18.10, to JEDNA komenda, bez zmiennych:

    ./zamknij_sesje.sh            # tylko gdy coś już działa (zamyka sway, wayvnc, grę, strażnika, vncviewer, dopasuj_okno)
    setsid nohup ./sesja.sh > /dev/null 2>&1 < /dev/null &

`sesja.sh` domyślnie jest headless (BEZ_OKNA=1) i sama otwiera podgląd (podglad.sh + dopasuj_okno.py). NIE dawaj:
- `RETRONIC_DOPASUJ_OKNO=0` (Karol chce dynamicznego skalowania, SPEC_okno_gry_1015),
- `RETRONIC_BEZ_OKNA=1/0` z ręki, ręcznego `hyprctl ... float/resize` na oknie vncviewera (psuje: float + zmiana rozmiaru = pętla),
- `rm STOP` (to flaga bota).

Okno podglądu ma być KAFLEM Hyprland (reguła w ~/.config/hypr/looknfeel.lua: tylko tag). Sesja idzie za kaflem, ale `dopasuj_okno.py` obcina ją do 1175x910 (wpisz_proporcje), żeby nie było czarnych pasów i zbyt dużej rozdzielczości.
SUPER+T (omarchy) przełącza okno float/kafel i je rozjeżdża: przełącz z powrotem tym samym skrótem.

Weryfikacja po starcie: `python3 -I -c "import dopasuj_okno as d; print(d.odczytaj_rozmiar(5901))"` ma dać (1175, 910) albo mniej, nigdy 1498x1820. Zrzut okna: `grim -g "x,y WxH"`.
Nie używaj `pkill -f`/`pgrep -f` z wzorcem we własnej komendzie (zabija własną powłokę): używaj ./zamknij_sesje.sh.
Bota NIE uruchamiaj przy starcie sesji, chyba że Karol o to prosi.

- Gdy gracz pyta „?” / „stop” przez zachowanie bota: `gotowe_odpowiedzi.md` (zatrzymaj bota, krótka odpowiedź ręcznie, odejdź na bok) i diagnoza Mijania obok.
Powrót do miasta na żądanie: `RETRONIC_ID=<id> ./wroc.sh` (bot w spokojnej chwili idzie do depo i staje, bez zakupów; `--anuluj` cofa, w marszu `./zatrzymaj.sh`); wymaga działającego bota tej instancji, nie rusza gry.
Refill po powrocie do miasta: `RETRONIC_ID=<id> ./refill.sh --tlo` (odłączony: `STARTUJ=1 ./serwis.sh --kroki jedzenie,backpack,blanki,wyjscie`, bez banku i depo, log `<stan>/refill.log`; `--przerwij`: STOP, serwis wychodzi sam (potem TERM), zwolnienie wejścia; bez nic do przerwania nie robi nic; bez argumentu w pierwszym planie); wymaga STOJĄCEGO bota. `./refill.sh --spot` = bez zakupów, tylko wyjście z miasta i start bota (`REFILL_KROKI=wyjscie`). Guziki `⌂ Miasto`/`↻ Refill`/`↗ Spot` w wtyczce paska wołają `wroc.sh` i `refill.sh`; `panel.py --json` ma pola `w_miescie`, `plan_depo_dostepny`, `wroc_*`, `serwis_*`.
Marsz klikiem w drodze do miasta i auto-refill (20.10, oba pokrętła domyślnie 0, spec: `dane_tibia/SPEC_wroc_do_miasta_1019.md`, sekcja „Rozszerzenie 20.10”): `WYPRAWA_MARSZ_KLIK=1` = w fazie „do” wyprawy / `wroc.sh` klik w najdalsze zwykłe pole odcinka (`marsz_klik.py`, jak serwis); `WROC_REFILL=1` = po STOP w depo Edron `refill_auto.py czekaj` czeka na wyjście bota i woła `refill.sh --tlo` (STOP_RECZNY, działający serwis i miasto bez planu, np. Thais = bez auto-refillu, powód w `wroc_refill.json` i w polu `wroc_refill` panelu); `wroc.sh --anuluj` i `refill.sh --przerwij` anulują też oczekującego czekacza.
- Wpisy-widma na liście stworów (obcy gracz na polu bota, kilku graczy na jednym polu; `widma.py`): `stwory()` oddaje listę w całości z polem `widmo`, a zajętość pól i ocena graczy (unikanie/mijanie, serwis) je pomijają; PK/czaszki/GM/model widzą wszystko. Pokrętło `STWORY_WIDMA` (cavebot.py, `na_zywo.json`; serwis: env `RETRONIC_STWORY_WIDMA=0`), 0 = stare zachowanie. Własny wpis przy duplikacie nazwy (relog): ruch (zawsze pierwszy), potem HP, potem NAJWYŻSZE id (`bot._wybierz_wlasny`; heurystyka z 19.10, kontrprzykład 13.10 Jointoramix: po restarcie serwera licznik może się odwrócić).
