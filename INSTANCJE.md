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

## Tryb bez okna (RETRONIC_BEZ_OKNA=1)

`RETRONIC_ID=dwa RETRONIC_BEZ_OKNA=1 ./sesja.sh` uruchamia zagnieżdżony sway z backendem `headless`: jeden wirtualny output
(domyślnie 734x910, zmiana: `RETRONIC_BEZ_OKNA_ROZ=1024x768`), brak okna na pulpicie hosta, więc render i `grim` działają
niezależnie od workspace'a. Nic nie jest tworzone w sway/Hyprlandzie hosta. Domyślnie (bez zmiennej) bez zmian.
Ograniczenia: brak okna do ręcznego logowania i podglądu. Podgląd na życzenie (koszt zerowy bez klienta):
`WAYLAND_DISPLAY=$(cat $XDG_RUNTIME_DIR/retronic-sesja-dwa/wayland) wayvnc -d -f 10 127.0.0.1 5903`, potem
`vncviewer 127.0.0.1::5903` (port inny na instancję; localhost, bez hasła). Zrzut: `grim` na tym gnieździe.
Logowanie postaci: przez wayvnc z włączonym wejściem (bez `-d`) albo zapamiętane dane konta na ekranie logowania
(klawisz_x11/XTEST po DISPLAY sesji działa tak samo).

## Etap 2: sieć (osobny moduł, jeszcze nie ma)

Cel: każdy klient z innego wyjścia sieciowego. Plan: osobny network namespace na instancję (`ip netns`), w nim WireGuard
albo tun2socks do wybranego proxy/VPN, a strażnik i gra uruchamiane przez `ip netns exec`. Do ustalenia:
socket Unix strażnika musi pozostać dostępny z hosta (ścieżka w `$XDG_RUNTIME_DIR` działa między namespace, jeśli
katalog jest wspólny, ale bez `unshare --mount`), XWayland i Wayland też są socketami plikowymi, więc powinno działać.
Do tego czasu obie instancje wychodzą z tym samym IP.

## Znane ryzyka

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
