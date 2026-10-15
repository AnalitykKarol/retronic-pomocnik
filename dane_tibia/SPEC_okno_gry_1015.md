# SPEC: okno gry bez szarych pasków (15.10 wieczór) — SZKIC do akceptu (decyzja Karola: stały rozmiar + dopasowanie w locie)

Cel: podgląd gry (vncviewer na pulpicie) bez ciemnej ramki wokół i bez czarnych pasów nad/pod mapą w kliencie.

## 1. Fakty [POTW, 15.10 ~22:20, sesja testowa bez gry, posprzątana]

- Ramka wokół: okno vncviewer na pulpicie (kafel Hyprlanda, np. 941x1030) jest większe niż ekran sesji gry (`sesja.sh`
  `RETRONIC_BEZ_OKNA_ROZ`, domyślnie 800x910); `podglad.sh` uruchamia `vncviewer -RemoteResize=0`.
- wayvnc 0.10.1 (headless sway) **zmienia rozdzielczość wyjścia na prośbę klienta**: surowy komunikat RFB SetDesktopSize
  (typ 251) 1000x950 zmienił HEADLESS-1 z 800x910 na 1000x950.
- TigerVNC 1.16.2 z `-RemoteResize=1` **nie wysłał** takiej prośby przy połączeniu (okno 941x1030, wyjście 800x910 przez 9 s).
- Pasy w kliencie: mapa 15:11 wypełnia szerokość lewej części (prawy panel ok. 185 px); przy wysokości 910 pasy znikają przy
  szerokości ok. 1175 px [HIP z geometrii, do sprawdzenia zrzutem]. Klient potrzebuje min. 800 px szerokości (14.10).
- Bot: `ekran.prostokat_mapy` wykrywa mapę dynamicznie i keszuje wynik po rozmiarze obrazu - nowy rozmiar = nowe wykrycie.

## 2. Zmiany

1. `sesja.sh`: domyślnie `RETRONIC_BEZ_OKNA_ROZ=1175x910` (po sprawdzeniu zrzutem; inaczej wartość z pomiaru).
2. Nowy `dopasuj_okno.py` (start z `podglad.sh` w tle, kończy się z podglądem): co ~1 s czyta rozmiar okna vncviewer
   (`hyprctl clients -j`, klasa Vncviewer i port w tytule/argumentach), a gdy różni się od wyjścia sesji o >= 8 px i stoi
   >= 1 s (debounce), wysyła SetDesktopSize do wayvnc sesji (min. szerokość 800, min. wysokość 600, parzyste wymiary).
   Pokrętło/zmienna `RETRONIC_DOPASUJ_OKNO=1` (0 = wyłączone, dzisiejsze zachowanie).
3. Bot: po zmianie rozmiaru ekranu - log jednej linii "ekran: nowy rozmiar WxH, nowe wykrycie mapy"; sprawdzić, że
   kliknięcia (atak, loot, plecak, Use with runą) trafiają po zmianie (prostokąt mapy, panele z prawej).

## 3. Weryfikacja

- Zrzut gry przy 1175x910: brak czarnych pasów nad/pod mapą; panel z prawej kompletny.
- Zmiana rozmiaru okna podglądu: wyjście sesji podąża (swaymsg get_outputs), ramka znika.
- Bot zatrzymany: `ekran.prostokat_mapy` na zrzutach 800x910, 1175x910 i po zmianie w locie; potem krótki test z botem
  (atak, loot, runa) przy Karolu.
- Cofnięcie: `RETRONIC_DOPASUJ_OKNO=0` i `RETRONIC_BEZ_OKNA_ROZ=800x910`.

## 4. Pytania

- Q1 Zmiana rozmiaru w trakcie gry bota: dopuszczalna (bot sam wykryje mapę od nowa), czy dopasowanie tylko przy
  zatrzymanym bocie (bezpieczniej)?
- Q2 Minimalny rozmiar okna: 800x600 OK?
