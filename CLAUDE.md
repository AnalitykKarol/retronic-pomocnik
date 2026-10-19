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
