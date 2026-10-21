# Instancje: drugi (i N-ty) klient Tibii z własnym botem

Zmienna `RETRONIC_ID` wybiera instancję. Pusta (domyślnie) = dzisiejsze zachowanie, te same ścieżki i nazwy.
Cała parametryzacja jest w `instancja.py`; moduły i skrypty biorą stamtąd ścieżki.

| co | bez ID | z `RETRONIC_ID=dwa` |
|---|---|---|
| socket strażnika | `$XDG_RUNTIME_DIR/retronic-pomocnik.sock` | `.../retronic-dwa.sock` |
| stan (na_zywo.json, uh_stan.json, STOP, STOP_RECZNY, logi/, tryb.log, mozg_pamiec.json, uciekanie.json, straznik.log) | katalog pomocnika | `instancje/dwa/` |
| WINEPREFIX | `../prefix` | `instancje/dwa/prefix` |
| katalog gry (exe, dll, Retronic.log klienta) | `..` | `instancje/dwa/gra` |
| sesja sway (wayland, swaysock, sway.conf) | `$XDG_RUNTIME_DIR/retronic-sesja/` | `.../retronic-sesja-dwa/` |
| rezerwacje miejsc | | `instancje/_wspolne/zajete.json` (wspólne) |

Wspólne dla instancji (celowo): `znane_pola.json` (wiedza o mapie), `pochodnia_ids.json` (id przedmiotów),
`trasy/`, `mapy.json`, `tryby.json`, plik `cisza`.

## Druga instancja, krok po kroku

1. `./nowa_instancja.sh dwa` przygotowuje katalog, kopię prefiksu (reflink) i kopie exe/dll. Nie uruchamia gry.
   Najlepiej, gdy wine domyślnej gry nie zapisuje rejestru (skrypt ostrzeże, jeśli działa wineserver).
2. `RETRONIC_ID=dwa RETRONIC_POSTAC=<nick> ./sesja.sh` startuje grę w osobnym zagnieżdżonym sway
   (własny WAYLAND_DISPLAY, własny XWayland DISPLAY, strażnik na `retronic-dwa.sock`). Okno pojawia się na pulpicie.
3. Zaloguj postać ręcznie i ustaw ją w wybranym miejscu mapy.
4. `./uruchom_instancje.sh dwa trolle_patrol sredni,runy` startuje bota (jak `uruchom.sh`, z mapy.json i tryby.json).
5. Zatrzymanie: `RETRONIC_ID=dwa ./zatrzymaj.sh` (skrót Mod4+Shift+F12 w oknie instancji robi to samo).
   Status: `RETRONIC_ID=dwa ./status.sh`, panel: `RETRONIC_ID=dwa python3 -I panel.py`.
6. Inne narzędzia też czytają `RETRONIC_ID`: `nagraj.sh`, `zatrzymaj_nagrywanie.sh`, `obserwator_reczny.sh`, `tryb.py`,
   `pamiec.py`, `kalibracja_krokow.py`, `sonda_skosu.py`.

`RETRONIC_POSTAC` to jawny nick postaci instancji. Ustawiaj go zawsze przy drugiej instancji: bot inaczej szuka nicka w
`Retronic.log` klienta (patrz ryzyka).

### Rozdzielanie miejsc na mapie

`miejsca_koord.py` trzyma rezerwacje w `instancje/_wspolne/zajete.json` (flock, zapis atomowy, TTL 900 s oraz zwolnienie,
gdy proces właściciela zginął). W patrolu jest opcjonalny hook, domyślnie wyłączony:

- w `na_zywo.json` instancji: `"PATROL_KOORD": 1` (opcjonalnie `"PATROL_KOORD_PROMIEN": 6` blokuje też miejsca w tym
  promieniu na tym samym piętrze),
- instancja wybierając miejsce pomija zajęte przez inne i rezerwuje swoje (jedno naraz),
- podgląd: `python3 -I miejsca_koord.py lista`, sprzątanie po zabitym bocie: `RETRONIC_ID=dwa python3 -I miejsca_koord.py zwolnij-instancje`.

Analityk nie może włączyć tego pokrętła (tylko ręcznie).

## Tryb bez okna (domyślny od 14.10) i podgląd

`./sesja.sh` (też z `RETRONIC_ID`) uruchamia zagnieżdżony sway z backendem `headless`: jeden wirtualny output
(domyślnie 800x910: klient z 13.10 nie mieści się w 734 px; zmiana: `RETRONIC_BEZ_OKNA_ROZ=1024x768`), więc render i `grim` działają niezależnie od tego, co jest
na ekranie hosta (inny workspace, zminimalizowany podgląd). Renderer `gles2` (gra rysowana na GPU); przy szerokości 734 grim na gles2 zwracał `Invalid stride`, stąd 800 px. Awaryjnie `WLR_RENDERER=pixman` (render programowy, ok. 1,6 rdzenia na klienta).

- **Podgląd**: w sesji działa `wayvnc` na 127.0.0.1 (port w `$XDG_RUNTIME_DIR/retronic-sesja[-<id>]/vnc_port`: 5901 bez ID,
  5902+ dla instancji), a na pulpicie od razu otwiera się `vncviewer` z myszą i klawiaturą (logowanie, ręczna gra).
- Zamknięcie podglądu nie zatrzymuje gry ani bota. Ponowne otwarcie: `./podglad.sh` (z `RETRONIC_ID` dla instancji).
- Wyjście z gry zamyka sesję, wayvnc i podgląd.
- `RETRONIC_PODGLAD=0`: start bez automatycznego podglądu. `RETRONIC_BEZ_OKNA=0`: dawny tryb z oknem sway na pulpicie
  (bot staje, gdy okno jest niewidoczne).

## Etap 2: sieć (osobny moduł, jeszcze nie ma)

Cel: każdy klient z innego wyjścia sieciowego. Plan: osobny network namespace na instancję (`ip netns`), w nim WireGuard
albo tun2socks do wybranego proxy/VPN, a strażnik i gra uruchamiane przez `ip netns exec`. Do ustalenia:
socket Unix strażnika musi pozostać dostępny z hosta (ścieżka w `$XDG_RUNTIME_DIR` działa między namespace, jeśli
katalog jest wspólny, ale bez `unshare --mount`), XWayland i Wayland też są socketami plikowymi, więc powinno działać.
Do tego czasu obie instancje wychodzą z tym samym IP.

## Izolacja okna i procesów: stan wiedzy (18.10)

Cel (Karol): docelowo kilka klientów naraz, każdy bot śledzi i steruje **tylko swoim oknem**.

**Poprawione 18.10 (`bot.ekran_z_procesu`, `bot.ekran_gry`, test `testy/test_ekran_gry.py` 7/7):** `ekran_gry()` brał pierwszy proces
z tekstem `retronicgl-` gdziekolwiek w wierszu poleceń, więc łapała się też powłoka z `ps | grep RetronicGL-` (`DISPLAY=:0` pulpitu).
Skutek: rozmiar ekranu skakał 940x1030 <-> 4480x1440, mapa niewykrywalna, bot stał. Teraz gra = argv[0] `RetronicGL-<n>.exe`
(lub `RetronicDX-`), `RETRONIC_ID` równe instancji i `WAYLAND_DISPLAY` równe `sesja/wayland` tej instancji.
Sprawdzone na żywo tylko dla jednej instancji. Uwaga praktyczna: nie grepuj procesów po `RetronicGL-` w poleceniach przy
działającym bocie (dla starej wersji kodu to wystarczało do awarii).

**Izolowane z konstrukcji:** gniazdo strażnika, stan (STOP, na_zywo, logi), WINEPREFIX, sesja sway/wayland, `rdzen.py` (gra tylko
wśród potomków własnego strażnika), `zatrzymaj.sh`/`status.sh`/panel (filtr po `RETRONIC_ID`).

**Niesprawdzone (do testu przed dwoma botami naraz):**
- dwa boty uruchomione jednocześnie (dotąd działała jedna sesja z botem; dwie sesje graficzne tak, bez drugiego bota);
- zapis plików wspólnych (`znane_pola.json`, `pochodnia_ids.json`) przy dwóch botach naraz (blokada? nie sprawdzono);
- `PATROL_KOORD` jest domyślnie wyłączone, więc dwa boty mogą wybrać ten sam spot;
- `Retronic.log` klienta może być wspólny: zawsze ustaw `RETRONIC_POSTAC`;
- drugi `sesja.sh` w pełnym restarcie (jak w "Znanych ryzykach");
- wspólne IP i konto serwera (etap 2).
Wcześniejsza hipoteza "winne są dwa otwarte klienty" **nie została potwierdzona**: miganie 18.10 zniknęło po poprawce `ekran_gry`,
nie po zamknięciu klienta testowego.

**Test kontrolny (do wykonania z Karolem, wymaga drugiej zalogowanej postaci):** dwie instancje z `RETRONIC_POSTAC`,
`PATROL_KOORD=1`; oczekiwane: każdy bot loguje stały rozmiar własnego okna (bez `ekran: nowy rozmiar`), własną pozycję
(`pozycja` na swoim gnieździe), `STOP` jednej instancji nie zatrzymuje drugiej, rezerwacje miejsc nie zbiegają się
(`miejsca_koord.py lista`).

## Znane ryzyka

- **wayvnc drugiej instancji (naprawione 17.10)**: domyślne gniazdo sterujące wayvnc jest jedno na użytkownika, więc drugi
  wayvnc odmawiał startu (`Another wayvnc process is already running`) i podgląd instancji się nie otwierał. `sesja.sh` i
  `podglad_stroz.sh` dają teraz instancji (`RETRONIC_ID`) własne gniazdo `$XDG_RUNTIME_DIR/retronic-sesja-<id>/wayvnc.sock`
  (`wayvnc -S …`); bez ID nic się nie zmienia. Kopie sprzed zmiany: `*.bak-20261017-wayvnc-S`; cofnięcie: przywróć kopie.
  Działające już sesje czytają stary plik, poprawka obejmuje następny start. Nie testowano pełnego restartu `sesja.sh`.
- **Podgląd instancji bez `dopasuj_okno`**: automatyczne dopasowanie rozmiaru ekranu sesji wywracało wayvnc (17.10, `End of
  stream`). Dla drugiej instancji: `RETRONIC_DOPASUJ_OKNO=0 RETRONIC_ID=<id> ./podglad.sh`, okno ustaw jako pływające i dopasuj
  do ekranu sesji (np. 1190x940 dla 1175x910), inaczej obraz jest zdeformowany.
- **Retronic.log klienta**: nie wiadomo, czy klient pisze do katalogu roboczego, czy obok exe. Instancja startuje z
  `cwd = instancje/<id>/gra` z kopiami exe, więc powinna mieć własny log, ale nie sprawdzono tego. Stąd `RETRONIC_POSTAC`.
- **Ten sam IP i konto serwera**: serwer może limitować klientów z jednego IP albo wykrywać multiklient (etap 2 to
  częściowo adresuje). Osobne konto/postać wymagane.
- **Kopia prefiksu z działającej gry**: rejestr mógł być niedopisany; w razie błędów kopiuj ponownie po zamknięciu gry.
- **Zasoby**: drugi klient GL + sway + XWayland to realne CPU/GPU i RAM; sprawdź, czy dwie instancje trzymają FPS.
- **Fokus i skróty**: zagnieżdżone sway biorą klawisze tylko, gdy ich okno ma fokus na hoście; XTEST bota działa
  niezależnie od fokusu (jak dziś). Dwa okna na pulpicie mogą się na siebie nakładać.
- **Współdzielone**: `znane_pola.json` (zapis atomowy, osobne pliki tymczasowe) i `logi/rdzen-skan.log`
  (diagnostyka strażnika; `rdzen.py` jest przeładowywany na gorąco przez działającego strażnika, więc go celowo nie ruszano).
- **Powiadomienia**: `powiadom.py` nie dodaje ID do tytułu notify-send (skrypty start/stop dodają `[id]`).
- **Zły `RETRONIC_ID`** (znaki spoza `a-z0-9_-`) kończy start błędem, nie cichym przejściem na domyślną instancję.
  Wyjątek: `zatrzymaj.sh` w razie błędu zawsze ustawia STOP domyślnej instancji (awaryjnie).
- **Proces domyślnej instancji** to ten bez `RETRONIC_ID` w środowisku; bot uruchomiony przed wprowadzeniem zmiennej
  jest rozpoznawany jako domyślny.

## Stały profil instancji: jedno IP, jeden sprzęt, jedno konto (20.10)
Spec: `dane_tibia/SPEC_tozsamosc_sprzetu_1020.md` (z rozszerzeniem (b)). Każda instancja (`RETRONIC_ID`) ma:
- `instancje/<id>/profil.json`: proxy (host, port, login), `ip_oczekiwane`, `konto`, `postac`; hasło proxy w keyringu
  (`./haslo_proxy.sh <id>`, okienko). Bez profilu instancja nie startuje; ten sam endpoint albo IP w dwóch instancjach = brak startu.
- `instancje/<id>/tozsamosc.json`: wolumen C:, MAC (Realtek/Intel), machine-id; generowane raz, stałe.
- start zawsze przez proxy (`RETRONIC_PROXY=0` tylko jawnie, z ostrzeżeniem); przed startem gry `siec_proxy.sh` sprawdza IP wyjściowe.
Nowa instancja: świeży prefiks (`WINEPREFIX=instancje/<id>/prefix wineboot -i`, potem `./nowa_instancja.sh <id>`; NIE kopia
prefiksu Mastafiana: MachineGuid, uuid klienta, konto z autoReconnect), `profil.json`, hasło proxy, pierwszy start i zamknięcie
klienta (własny uuid), potem `python3 -I kopiuj_ustawienia.py ../prefix instancje/<id>/prefix` przy zamkniętej grze.
Stan 20.10 ~13:20: jedyna aktywna instancja `invincible`. `test` (Johny) zarchiwizowana w `instancje/_archiwum/test-johny-20261020`;
główna gra (Mastafian) zamknięta, prefiks zostaje jako źródło ustawień, bez zapisanego konta. Proxy Railway usunięte.
Stan 20.10 ~15:00: druga instancja `kutangen` (Webshare nr 2, Londyn 45.38.107.97, zmierzone 5/5; własny prefiks, uuid, sprzęt), ustawienia od Mastafiana; podgląd Remmina VNC 5928. Webshare 20.10: nr 8 = DE Kelsterbach 64.137.10.153, nr 10 = ES Madryt, reszta US (1,3,4,6,7,9).
Stan 20.10 ~15:35: trzy instancje: `invincible` (nr 5 PT, Michal), `kutangen` (nr 2 GB, Pawel), `dawajkesh` (nr 8 DE 64.137.10.153, Kuba, VNC 5952). Wolne proxy Webshare: nr 10 ES, reszta US. Nowa instancja: po `wineboot -i` i `nowa_instancja.sh` uruchom `python3 -I tozsamosc.py powloka instancje/<id>` i `zmien_uzytkownika.py instancje/<id>/prefix <uzytkownik>`; konto po zalogowaniu `profil.py przypisz instancje/<id>`.
Stan 20.10 ~16:25: cztery instancje, czwarta `kolanoth` (nr 10 ES 64.137.96.74, Admin, DESKTOP-SY2EGQM, VNC 5920). Hasło proxy: bez okienka, `siec_proxy.sh` bierze wpis instancji z tym samym serwerem proxy (`RETRONIC_PROXY_HASLO_Z` z `profil.py`; poprawka wykonana przez Karola, `narzedzia_jednorazowe/haslo_wspolne_1020.py`). Wszystkie europejskie proxy Webshare zajęte; zostały US (1, 3, 4, 6, 7, 9).
Stan 20.10 ~19:45: pięć instancji, piąta `bober` (Webshare nr 3 US 92.119.182.109, zmierzone 4/4; Piotr, DESKTOP-X21SKEC; VNC 5954). Świeży prefiks (`wineboot -i`), `nowa_instancja.sh`, tożsamość, `zmien_uzytkownika.py`, `profil.json`, pierwszy start i zamknięcie, `kopiuj_ustawienia.py ../prefix` (mapa i ustawienia jak u reszty; krok łatwo pominąć), `profil.py przypisz`. Login i hasło zapisane w kliencie gry (nie w repo). Wolne proxy: US 1, 4, 6, 7, 9.
Stan 20.10 ~20:05: sześć instancji, szósta `wydra` (Webshare nr 1 US 82.22.234.33, zmierzone 3/3; Adam, DESKTOP-L1HS790; VNC 5965). Receptura jak `bober`: świeży prefiks, `nowa_instancja.sh`, tożsamość, `zmien_uzytkownika.py`, `profil.json` (konto i postać puste do `profil.py przypisz`), pierwszy start + zamknięcie (`swaymsg -s /run/user/1000/sway-ipc.1000.<pid sway>.sock exit`, kod 1 = sukces), `kopiuj_ustawienia.py ../prefix` przy ZAMKNIĘTEJ grze, start `sesja_gry.py start`. Przeglądarka przez to samo proxy: `eval "$(python3 -I profil.py powloka instancje/wydra)"; RETRONIC_ID=wydra ./siec_proxy.sh chromium --no-sandbox --disable-features=AsyncDns --user-data-dir=~/.local/share/retronic-chromium/wydra https://retronic.online` (Chromium widzi IP z profilu; strona za Cloudflare). Wolne proxy: US 4 (82.22.234.172), 6 (31.57.88.146), 7 (194.39.33.227), 9 (45.151.163.53).
Stan 21.10 ~12:45: pięć instancji (`dawajkesh`, `invincible`, `kolanoth`, `kutangen`, `wydra`). `bober` usunięty ze spisu na polecenie Karola („już go nie ma i nie będzie”): sesja zamknięta `RETRONIC_ID=bober sesja_gry.py zamknij` (pozostałe 5 nietknięte), katalog z prefiksem, profilem, logami i `ostatni_start.bober.env` przeniesiony do `instancje/_archiwum/bober-20261021` (`okno_api.lista_instancji()` i `okno_api.py stan` bez bobra). Zwolnione proxy Webshare nr 3 (US 92.119.182.109). Profil Remminy `retronic-bober.remmina` też w archiwum (zasada Karola: instancje archiwizujemy, nie kasujemy, i nie używamy ich ustawień). Cofnięcie: `mv instancje/_archiwum/bober-20261021 instancje/bober` (+ `ostatni_start.bober.env` do katalogu głównego, `retronic-bober.remmina` do `~/.local/share/remmina/`).
