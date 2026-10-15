# Analiza 14–15.10: desktop (tryb bez okna), błędy bota, odcisk sprzętu

Źródła: `logi/mozg-stdout-1014-*.log`, `logi/mozg-stdout-1015-*.log`, `logi/telemetria-2026101[45].jsonl`,
odczyty strażnika (`pozycja`, `gracz`, `stwory`, `kontenery`, `wiadomosci`), minimapa `mapa/map74.otmm`,
plik klienta `RetronicGL-*.exe` (strings), rejestr Wine prefiksu. Kod: gałąź `ruch-r1-1014` @ `f153c04`.
[POTW] = sprawdzone na żywo albo w danych, [HIP] = wniosek bez bezpośredniego dowodu.

## 1. Ogień: wejście dwa razy pod rząd w ogień (15.10 10:56) [POTW]

- Wokół (32497,32300,z8) 16 pól jest w **masce danych** (`do maski danych: N epizodów, bez spadku HP`, N = 3..71),
  m.in. (32497,32301) 12 ep., (32497,32300) 3 ep., (32497,32299) 71 ep., (32496,32299) 22 ep.
- 10:56:49 postać stanęła na (32497,32301), HP spadło, pole **wypadło z maski**, bot zszedł na (32498,32301)...
  10:56:51 stoi na (32497,32300) (też w masce), drugi spadek, zejście na (32497,32299).
- Teren (Charlie 15.10): przez skupisko **nie ma innego przejścia**, parzy tylko **pole środkowe (32497,32300)**;
  reszta pól jest bezpieczna i maska ma rację.
- Mechanizm błędu [POTW w `trasy/ogien_epizody.json`]: (32497,32300) i (32497,32301) mają `hp: true` z **tym samym**
  `ost` (…614.94): jeden spadek HP przypisano obu polom. Okno `OGIEN_HP_OKNO_S = 3.0` s obejmuje dwa kroki, a
  [HIP, zasada 7.4] ogień parzy jeszcze kilka tików po zejściu z pola, więc obrażenia ze środka "obciążają" sąsiada.
  Skutek: bezpieczne (32497,32301) wypada z maski i zwęża jedyne przejście.
- Propozycja: (a) spadek HP przypisywać tylko polu, na które weszliśmy **przed** pierwszym spadkiem, nie wszystkim
  polom z okna; (b) spadek w trakcie parzenia po zejściu (seria tików) nie obciąża kolejnych pól; (c) jawne pole
  "złe" (32497,32300) do omijania w drodze przez przejście; (d) poprawić dane: (32497,32301) z powrotem `hp: false`.
  NIE usuwać z maski całego skupiska (zablokowałoby jedyne przejście).
- Osobno: przy starcie `[OGIEN] nie wczytam maski stałych pól: AttributeError("'CavebotMozgu' object has no attribute 'mapa'")`
  (każdy start na `ruch-r1-1014`). Maska z epizodów się wczytuje, maska stałych pól nie.

## 2. Loot: Ctrl+klik własnego pola wspina po drabinie, bot zostaje piętro wyżej (14.10) [POTW mechanizm, HIP drabina]

- Dwa wyjścia z kanałów Thais (z8 -> z7): 20:08:44 przy (32422,32215) i 21:07:16 przy (32368,32184), oba w stanie LOOT.
- Log: `loot: Ctrl+klik ... (0,-1) pusto, (0,0) pusto, (-1,-1) pusto, (1,-1) pusto` -> `Zwłoki na innym piętrze`;
  telemetria: te same x,y, z7. Ctrl+klik = "Use"; na polu z drabiną Use wspina. Minimapa nie oznacza drabin
  (`schody_lub_dziura` = False wokół obu miejsc), więc drabiny nie potwierdzono z mapy.
- Po wyjściu bot szedł punktami trasy z8 po z7 (`[IDZ] punkt 8/91 -> 59/91`) i nie wrócił.
- Propozycja: (a) zmiana piętra po Ctrl+kliku lootu = zapis pola jako "drabina" (plik jak `pietra_zle.json`),
  nigdy więcej Use na nim, także (0,0); (b) postać na innym piętrze niż trasa -> przejście pięter (`pietra.py`) zamiast
  marszu po złym piętrze; (c) dymek przy niezamierzonej zmianie piętra.
- Rook 14.10 16:53: patrol m20 wprowadził postać po drabinie na z10 (zaułek (32048,32155)), ~20 min bez zabić
  (`Patrol: brak osiągalnego miejsca`); zejście 2 pola na wschód (32050,32155). Model w tym czasie raportował
  "szczury padają" (halucynacja). Propozycja: dymek przy powtarzanym `brak_zabic`.

## 3. Wydajność (telemetria) [POTW]

| Sesja | h | exp/h | zabić/h | WALKA / IDZ |
|---|---|---|---|---|
| szczury Rook 14.10 11:49–17:12 | 5,4 | 630 | 125 | 65% / 30% |
| szczury Thais 14.10 20:08–21:46 | 1,6 | 203 | 41 | 39% / 57% |
| trolle `patrol:troll` 15.10 08:20–09:38 (nowy kod) | 1,3 | 2244 | 108 | 65% / 30% |

- Trolle: 65 wizyt, 17 pustych (0 zabić na miejscu i w drodze), zabicia głównie w drodze (śr. 2,2), na miejscu 0,0;
  dojście mediana 65 s, max 229 s; 146 przejść pięter w ~80 min. `PATROL_RUNDA=1` odwiedza każde miejsce raz na rundę,
  także świeżo wybite. Propozycja: w rundzie pomijać miejsca wyczyszczone < T min temu.
- Złoto na trollach: 706 gp / 2,35 h ~ 300 gp/h (przy pełnym capie, 6 oz wolne).

## 4. Odcisk sprzętu: co klient może odczytać [POTW w binarce i rejestrze; wysyłka do serwera NIEZNANA]

Logika klienta (Lua w `data.zip`) jest szyfrowana, więc nie wiadomo, co trafia do serwera. W `RetronicGL.exe` są:

| Dane | API / klucz | Wartość pod Wine na desktopie |
|---|---|---|
| ID instalacji | `SOFTWARE\Microsoft\Cryptography\MachineGuid` | z prefiksu (`system.reg`), **kopiowany przez `nowa_instancja.sh`** |
| Płyta, BIOS | `HARDWARE\DESCRIPTION\System\BIOS`, `GetSystemFirmwareTable` | producent/model płyty, wersja BIOS (seriale i UUID: Linux tylko dla roota) |
| CPU | `HARDWARE\DESCRIPTION\System\CentralProcessor\0` | model procesora |
| Sieć | `GetAdaptersAddresses` | prawdziwe MAC kart hosta |
| Dysk | `\\.\PhysicalDrive` + `DeviceIoControl`, `GetVolumeInformation` | nie sprawdzono, co zwraca Wine |
| Użytkownik | `GetUserNameA` | nazwa użytkownika Linuksa |
| Inne | `GlobalMemoryStatusEx`, `GetTimeZoneInformation`, OpenGL | RAM, strefa czasowa, model GPU |

- Antycheat w kliencie: `CreateToolhelp32Snapshot`/`Process32*`, `Module32*`, `EnumWindows`+`GetWindowTextA`,
  `IsDebuggerPresent`. Pod Wine widzą tylko procesy prefiksu i okna zagnieżdżonej sesji: bot (Python w Linuksie,
  odczyt pamięci przez strażnika, XTEST) jest poza ich zasięgiem.
- Sieć: klient trzyma 5 połączeń naraz z bramkami (porty 5001/5501/6501: OVH, Hetzner, Hosteons, Cloudflare);
  każda widzi publiczne IP.
- Wnioski dla wielu instancji: ten sam sprzęt i MAC na jednym komputerze; **identyczny `MachineGuid`** w instancjach
  z kopii prefiksu. Propozycja: `nowa_instancja.sh` losuje nowy `MachineGuid`; MAC zmieni namespace sieciowy (Etap 2).

## 5. Testy na `ruch-r1-1014` [POTW]

Te same błędy na czystej gałęzi i po scaleniu z desktopem (nie wynikają ze zmian desktopu):
`test_cavebot` 474/479, `test_ogien` 101/102, `test_wielopietrowa` 90/95, `test_rdzen_widmo` (3 FAIL),
`test_ruch_okno` (2 FAIL). Pozostałe 48 zestawów OK; `test_loot_jedzenie`, `test_loot_zbierz` pomijane (brak zrzutów).

## 6. Gra i dane: ustalenia z rozmowy

- Klient 6.50 (13.10) rysuje min. 800 px szerokości; tryb bez okna 800x910, render gles2 (GPU). Instancja: ~0,8 rdzenia
  (było ~2,7 przy pixman).
- Minimapa klienta: `AppData/Roaming/Retronic/Retronic/map74.otmm`, wczytywana raz po starcie klienta, zapis przy
  wylogowaniu. Pełną mapę wstawiać przy zamkniętym kliencie.
- Retronic: czary od 8 lvl, wymagany tylko magic level (exura od ML 1). Banku brak (depo per miasto).
- NPC sprzedający runy (np. Alexander, Edron) w Tibii od 7.5; na Retronic nie znaleziony. Blanki: Xodet (Thais).
  Dane `przedmioty.json` (Tibiantis 2005) mogą zawierać rzeczy z 7.5–7.6.
- Brass helmet w Thais: Gamel (piwnica przy dokach, NW od depo), nie Sam. Lepszy: soldier helmet (Ulrik, Greenshore).
- Edron troll cave: wejście z7 (33117,31775); brak drogi z miasta po mapie (285 przeszukanych obszarów pięter) – przejście czymś,
  czego minimapa nie oznacza.
