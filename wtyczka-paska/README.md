# Retronic

Wtyczka paska Omarchy: status i start/stop botów Retronic z paska. Spec:
`specs/2026-10-19-retronic-wtyczka-paska.md`; guziki miasta: `specs/2026-10-19-retronic-guziki-miasto.md`.
Wtyczka jest cienka: nie ma własnej logiki bota, czyta JSON z `panel.py` i woła skrypty bota
(`zatrzymaj.sh`, `uruchom.sh`, `wroc.sh`, `refill.sh`). Zakres to **tylko bot**: nie startuje ani nie zamyka sesji gry ani proxy.

## Co pokazuje

- **Ikona `RT` na pasku.** Kolor to najgorszy stan ze wszystkich instancji: alarm (czerwony, kolor `urgent`
  motywu) > stop (bursztynowy) > działa (zielony). Stan `brak` (gra nie działa) liczy się najniżej i daje
  szarą ikonę tylko wtedy, gdy wszystkie instancje to `brak`. Hover to jedno zdanie, np.
  `2 instancje: 1 działa, 1 stop`.
- **Panel po kliknięciu ikony** (prawy klik na ikonie = odśwież od razu). Jeden wiersz na instancję:
  kropka stanu, nazwa (pusty ID = `główna`), krótki stan z czasem działania, HP/mana (gdy bot działa),
  `ostatni: <mapa>, <tryb>` z `ostatni_start[.<id>].env`, `proxy włączone/wyłączone`
  (czy proces `siec_proxy.sh` tej instancji żyje, bez pomiaru IP) i krótki błąd ostatniej akcji
  (np. `Gra nie działa`, gaśnie po 8 s).
- **Przyciski, osobne dla każdej instancji.** `■ Stop` (czerwony) gdy bot działa, `▶ Start` (zielony) gdy
  stoi. Stop działa od razu, bez potwierdzenia. Po kliknięciu przycisk blokuje się na ok. 1,5 s (`…`),
  żeby drugi klik nie trafił w przycisk, który zdążył zmienić się w przeciwny. Start jest zablokowany
  przy `brak gry` i `brak odczytu`. Przyciski są tylko pod myszą: Enter i Spacja ich nie wciskają.
  Nie ma „zatrzymaj wszystkie”.
- **Guziki miasta (osobne dla każdej instancji), w rzędzie pod wierszem:** `⌂ Miasto`, `↻ Refill` i `↗ Spot`, cykl
  spot → miasto → refill → spot bez terminala. Pełna tabela stanów w specu guzików; w skrócie:
  - `⌂ Miasto` (zielony) działa, gdy bot instancji działa, jest plan depo dla pozycji i postać nie jest jeszcze w mieście;
    woła `wroc.sh`. Po wciśnięciu `✕ Anuluj` (`wroc.sh --anuluj`) do czasu ruszenia bota, potem `w marszu…`
    (szary; zatrzymanie to zwykły `■ Stop`), na końcu linia `w depo, bot stoi`.
  - `↻ Refill` (zielony) działa, gdy bot STOI, postać jest w strefie miasta (Edron) i serwis nie trwa; woła
    `refill.sh --tlo` (= `STARTUJ=1 serwis.sh --kroki jedzenie,backpack,blanki,wyjscie`, bank i depo pominięte,
    odłączone przez `setsid`, log `instancje/<id>/refill.log`). W trakcie guzik to `■ Przerwij` (`refill.sh --przerwij`:
    ubija `refill.sh` i `serwis.sh`, daje STOP i czeka, aż `serwis.py` sam wyjdzie i puści wejście, dopiero potem TERM/KILL;
    na końcu `zatrzymaj.sh` i zwolnienie myszy/modyfikatorów; gdy nic nie biegło, nic nie robi i nie ustawia STOP) i linia `serwis w toku (krok: …)`. Po sukcesie bot sam rusza na spot.
  - `↗ Spot` (zielony) działa w tych samych warunkach co Refill, ale **bez zakupów**: woła `refill.sh --spot` (tylko krok `wyjscie`,
    potem `STARTUJ=1` rusza bota ostatnią mapą i trybem; `uruchom.sh` dodaje dojście na spot, gdy postać stoi na z7). W trakcie:
    `idę na spot…` (guzik szary), wspólne `■ Przerwij` na miejscu Refill. Poza miastem szary: „już poza miastem: użyj ▶ Start”.
  - Porażka = czerwona linia `błąd: <powód>` (do godziny, dopóki bot stoi), bez ponawiania; ponowny klik wznawia serwis.
  - Szary guzik pokazuje powód w linii pod wierszem, gdy mysz jest nad nim. W trakcie serwisu `▶ Start` jest zablokowany.
  - Te same zasady co Stop/Start: blokada ok. 1,5 s po kliknięciu, tylko mysz, zero niejawnych akcji.
- **`▣ Otwórz okno` (jeden na cały panel, w nagłówku po prawej).** Otwiera okno zarządzania Retronic (`okno.sh` z katalogu
  pomocnika; spec `specs/2026-10-19-retronic-okno.md`, Q1). Okno to osobny proces `quickshell -p okno/`, odpalany odłączonym
  `setsid -f` (wyjście do `/dev/null`): żyje po zamknięciu popupu i po restarcie paska. Jedno okno naraz: ponowne kliknięcie (albo
  skrót) tylko przenosi fokus na otwarte (`okno.sh` robi to sam). Guzik jest zawsze aktywny (nie zależy od stanu botów), działa tylko
  myszą. Po powodzeniu popup się zamyka; gdy brak `okno.sh` w katalogu pomocnika albo `quickshell` w PATH, w nagłówku jest
  czerwona linia z powodem (gaśnie po 8 s) i popup zostaje.
- Panelu nie wolno wypełniać treścią logów ani „wnioskiem analityka” z tooltipu `panel.py`: z tooltipu
  czytane są wyłącznie czas działania i HP/mana.

## Skąd dane

| Co | Jak |
|---|---|
| Status instancji | `RETRONIC_ID=<id> python3 -I panel.py --json` (`class`: `dziala` / `alarm` / `stop` / `brak`) |
| Lista instancji | główna (pusty ID) + podkatalogi `instancje/` poza `_wspolne` (wzór ID jak w `instancja.py`) |
| Stop | `RETRONIC_ID=<id> ./zatrzymaj.sh` |
| Start | `RETRONIC_ID=<id> ./uruchom.sh` (bez `MAPA`/`TRYB`: bierze `ostatni_start[.<id>].env`) |
| Wróć do miasta / Anuluj | `RETRONIC_ID=<id> ./wroc.sh` / `./wroc.sh --anuluj` (plik `WROC`; bot rusza w spokojnej chwili) |
| Refill / Przerwij | `RETRONIC_ID=<id> ./refill.sh --tlo` / `./refill.sh --przerwij` (opakowanie `serwis.sh`, odłączone) |
| Spot | `RETRONIC_ID=<id> ./refill.sh --spot` (jak Refill, ale tylko krok `wyjscie`; ten sam log i Przerwij) |
| Stan guzików miasta | dodatkowe pola `panel.py --json`: `pozycja`, `w_miescie`, `w_depo`, `plan_depo_dostepny`, `wroc_oczekuje`, `wroc_w_marszu`, `serwis_*` (w tym `serwis_tryb`) (starszy `panel.py` bez nich: guziki miasta szare) |
| Otwórz okno | `bash <helperDir>/okno.sh`, odłączone: `setsid -f`, bez RETRONIC_ID (okno samo czyta wszystkie instancje) |
| Odświeżanie | co 5 s, jedno wywołanie na instancję, bez demona; także przy zamkniętym panelu (kolor ikony) |

`Alarm` bez żywego bota (panel.py trzyma alarm do 60 s po wpisie w logu) pokazuje `▶ Start`, bo przycisk
wynika z tego, czy proces bota żyje, nie z samej klasy.

## Ustawienia

| Klucz | Domyślnie | Znaczenie |
|---|---|---|
| `helperDir` | `~/Games/Retronic/pomocnik` | katalog z `panel.py`, `zatrzymaj.sh`, `uruchom.sh`, `wroc.sh`, `refill.sh`, `instancje/` (`~` jest rozwijane) |
| `refreshIntervalSec` | `5` | odstęp odczytu statusu, 2 do 60 s |

Ustawienia siedzą we wpisie wtyczki w `~/.config/omarchy/shell.json` (jak u pozostałych wtyczek).

## Pliki

- `manifest.json` (rodzaj `bar-widget`, `activation: on-demand`), `Panel.qml` (ikona, odczyt co 5 s, popup),
  `PanelContent.qml` (nagłówek z `▣ Otwórz okno` i wiersze), `CityButton.qml` (guzik `⌂ Miasto` / `↻ Refill` / `↗ Spot` / `▣ Otwórz okno`),
  `Instance.qml` (jedna instancja: odczyt statusu i jej akcje),
  `RetronicModel.js` (cała logika bez Quickshella: parsowanie, najgorszy stan, zdanie na hover,
  stany guzików miasta, polecenia, skrócenie błędu).
- `test/RetronicModel.test.js`: testy modelu oraz poleceń na atrapie katalogu pomocnika.

## Testy

```bash
cd wtyczka-paska && node --test test/*.test.js
```

Testy poleceń uruchamiają się na atrapie (`mktemp`) z własnymi stubami `panel.py`, `zatrzymaj.sh`,
`uruchom.sh`, `wroc.sh`, `refill.sh` i `instancje/`; prawdziwych skryptów bota nie dotykają. Bez `Process`/Quickshella nie da się
sprawdzić samego popupu: wygląd w prawdziwym pasku trzeba obejrzeć po instalacji.
Składnia QML: `/usr/lib/qt6/bin/qmllint wtyczka-paska/*.qml` (0 błędów; ostrzeżenia `unqualified` są
dlatego, że `qs.Commons` nie jest tu widoczny). Strona bota (`panel.py`, `refill.sh`): w repo pomocnika
`python3 testy/test_refill.py` i `python3 testy/test_instancja.py`.

## Zależności po stronie bota

`▣ Otwórz okno` wymaga w katalogu pomocnika `okno.sh` (i katalogu `okno/` z QML okna, F2 specu okna); bez nich guzik
pokazuje błąd `brak okno.sh…`, reszta wtyczki działa bez zmian. Guziki miasta wymagają w katalogu pomocnika: `wroc.sh` (jest od 19.10), `refill.sh` i rozszerzonego `panel.py --json`
(branch `feat/guziki-miasto` repo bota). Bez nich wtyczka dalej działa: Stop/Start jak dotąd, guziki miasta szare.

## Instalacja (poziom 2: zmiana w `~/.config`, osobna zgoda)

```bash
ln -s /home/charlie/Games/Retronic/pomocnik/wtyczka-paska ~/.config/omarchy/plugins/charlie.retronic
omarchy-shell shell rescanPlugins
omarchy plugin enable charlie.retronic
omarchy bar move charlie.retronic <sekcja>     # opcjonalnie; domyślnie środek paska
```

Potem wpis w `.ai/system/omarchy-plugins/STATE.md` (jak pozostałe wtyczki).

## Skrót klawiszowy do okna (opcjonalnie, poziom 2: zmiana w `~/.config/hypr`, osobna zgoda)

Nie jest zainstalowany; gotowa linia do wklejenia na koniec `~/.config/hypr/bindings.lua` (Hyprland z konfiguracją w Lua,
tak jak pozostałe osobiste bindy tam; `o.bind(klawisze, opis, polecenie)` z `/usr/share/omarchy/default/hypr/helpers.lua`):

```lua
o.bind("SUPER + SHIFT + R", "Retronic: okno zarządzania", "setsid -f /home/charlie/Games/Retronic/pomocnik/okno.sh")
```

Sprawdzone 20.10: `SUPER + SHIFT + R` jest **wolne**. Żywa lista (`hyprctl binds -j`) ma przy `R` tylko `SUPER + CTRL + R`
(przypomnienie), `SUPER + CTRL + ALT + R` i `SUPER + SHIFT + CTRL + R`; w `bindings.lua` jest wyłącznie zakomentowany przykład
z szablonu (`-- o.bind("SUPER + SHIFT + R", "SSH", …)`). Skrót i guzik wołają to samo `okno.sh`: drugie wywołanie nie otwiera drugiego
okna, tylko przenosi fokus. Po wklejeniu: `hyprctl reload` (albo ponowne zalogowanie). Cofnięcie: usuń tę linię i przeładuj.

## Cofnięcie

```bash
omarchy plugin disable charlie.retronic
rm ~/.config/omarchy/plugins/charlie.retronic     # tylko symlink; źródło zostaje w repo bota (wtyczka-paska/)
omarchy-shell shell rescanPlugins
```

Boty ani gra nie są ruszane przez instalację ani cofnięcie. **Uwaga:** wyłączenie wtyczki nie zatrzyma odłączonego
serwisu (`refill.sh --tlo` żyje poza paskiem). W trakcie Refillu najpierw użyj `■ Przerwij` (albo `./refill.sh --przerwij`
z katalogu pomocnika), dopiero potem wyłącz wtyczkę.
