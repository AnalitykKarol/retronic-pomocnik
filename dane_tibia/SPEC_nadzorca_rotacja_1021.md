# SPEC: nadzorca, który zarządza (rotacja postaci, miasto, przerwy) - 21.10 — SZKIC do decyzji Karola

Rozszerza `SPEC_nadzorca_zestawu_1021.md` (zatwierdzony 07:40: grafik, wykonawca, obchód). Tamten zostaje źródłem zasad
odstępów i blokad. Ten dokument dokłada **cykl postaci z miastem i przerwą** oraz **działanie zamiast raportu**.

## Zlecenie (Karol 21.10 ~16:20)

„Agent kontrolujący ma mieć szerszy zakres, ma móc rotować i cofać do bazy. Kilka kont, kilka postaci, ale nie włączone od 8 do 20,
tylko rotacja: jak ktoś skończy expić, to idzie do miasta, odkłada, robi całą rotację i wylogowuje się na trochę, potem wraca.
Na razie 5 postaci naraz. On teraz tylko daje raport, nic nie robi, nie pomaga postaciom, a ma nimi zarządzać jak ja.”

## Stan dzisiaj (zmierzone 21.10)

| Klocek | Stan | Dowód |
|---|---|---|
| Obchód („admin”) | tylko odczyt i raport, naprawy po „tak” | `~/.claude/skills/pilnuj-botow/SKILL.md` |
| `grafik.py`, `nadzor.py` (warstwy A i B) | **nie istnieją** | brak plików |
| Logowanie | pomiar F0 zrobiony (kliki Login 588,594 i Ok 641,628, ~3 s), **skryptu brak** | `SPEC_nadzorca_zestawu_1021.md` F0 |
| Wylogowanie | prototyp `narzedzia_jednorazowe/wyloguj_prototyp_1020.py`, **`wyloguj.sh` brak** | `SPEC_powrot_rook_1020.md` F2 |
| Wykrycie wylogowania/resetu | `ROZLACZENIE_STOP`=1 u 5 postaci od 15:36–15:47 | `SPEC_rozlaczenie_1021.md` |
| Powrót do miasta | `wroc.sh` / plik WROC → wyprawa do depo i STOP | invincible 16:13 doszedł do depo w Thais |
| — jaskinia trolli → depo Thais | działa | jw. |
| — Edron trolle → depo Edron | trasy są, test na żywo pełnej drogi niezrobiony | `SPEC_edron_serwis_1019.md` |
| — kanały Thais → miasto | **zepsute**: wyjście (32360,32242,z8) nikt nigdy nie przeszedł | ALARM kutangen 15:38, `AUDYT_1021.md` |
| — Rook (raty, kanały) → miasto | plany są, przejścia zawodne (lina/drabina), dziś STOP 15:07 | `AUDYT_1021.md` 0.4, `SPEC_przejscia_trzy_sposoby_1021.md` |
| Odkładanie do depo + serwis (sprzedaż, jedzenie, blanki) | **tylko Edron** (`serwis.sh`); Thais i Rook: dojście do depo bez odkładania | `wyprawa.py` „brak planu serwisu dla tego miasta” |
| Zgon | `SMIERC_STOP`=0 wszędzie | `AUDYT_1021.md` K02 |
| Konta i postacie | 5 aktywnych (dawajkesh, invincible, kolanoth, kutangen, wydra), bober w archiwum | `INSTANCJE.md` |

**Wniosek:** nadzorca nie ma czym zarządzać. Brakuje logowania, wylogowania, pewnych powrotów i odkładania poza Edronem.
Sama zmiana promptu obchodu tego nie załatwi. Trzeba zbudować klocki, a potem wykonawcę, który ich używa.

## Proponowane zachowanie

### Cykl jednej postaci (wykonawca `nadzor.py`, deterministyczny, co ~1 min)

`OFFLINE (przerwa)` → `LOGOWANIE` (`sesja_gry.py start` + `zaloguj.sh`) → `DOJSCIE` → `EXP` → koniec zmiany → `POWROT` (WROC)
→ `MIASTO` (odłożenie do depo + serwis) → `WYLOGOWANIE` (`wyloguj.sh`, zamknięcie klienta) → `OFFLINE`.

- **Koniec zmiany, co pierwsze nastąpi:**
  - czas zmiany (losowo w widełkach);
  - pełny plecak / brak capu;
  - brak jedzenia albo blanków;
  - limit dzienny postaci.
  Wylogowanie czeka na spokojną chwilę, jak Q2 z 07:40.
- **Przerwa offline:** losowo w widełkach, potem postać wraca do kolejki.
- **Zestaw:** najwyżej N postaci online naraz. Kolejna postać z puli loguje się, gdy zwolni się miejsce.
  Między dowolnymi dwoma logowaniami/wylogowaniami jest odstęp 7–25 min (zasada z 07:40).

### Pomoc postaciom (obchód: model, świeże wywołanie; wykonawca: kod)

Nadzorca **sam** (bez pytania) robi rzeczy z białej listy, każdą z wpisem w logu nadzoru i jednym zdaniem uzasadnienia:
- restart bota na **bieżącej** mapie i trybie (`tryb.log`, nie `ostatni_start`; lekcja z 15:36);
- zdjęcie STOP po alarmie bota i wznowienie (alarm przejścia, wpadnięcie, „trzy punkty nieosiągalne”) z rotacją napraw z `CLAUDE.md`;
- powrót do miasta (WROC), gdy postać się kręci, spada jej tempo albo kończy się zmiana;
- ponowne logowanie po rozłączeniu albo resecie serwera (10:00);
- wylogowanie i przerwa zgodnie z grafikiem;
- zmiana spotu na zapasowy z listy postaci, gdy spot jest zajęty przez graczy albo drugiego bota (lista zapasowych spotów w `profil.json`).

**Nigdy** (blokady w kodzie):
- czat gry;
- pokrętła ryzyka śmierci (ogień, próg ucieczki, PK, HP);
- ruszanie `STOP_RECZNY` (gra Karola);
- zakładanie kont;
- handel.

**Zawsze woła Karola** (powiadomienie critical):
- PK lub atak gracza;
- zgon;
- „bot?” i GM;
- IP proxy niezgodne;
- wyczerpana rotacja napraw;
- stan, którego nie umie ustalić.

## Fazy (każda: spec do akceptu → test → checker → jedna postać na żywo → reszta)

1. **K1 klocki wejścia i wyjścia:** `zaloguj.sh` (zrzut przed każdym klikiem), `wyloguj.sh`, `SMIERC_STOP` na ekranie wyboru postaci.
2. **K2 pewne powroty:**
   - kanały Thais przez znaną drabinę pod kratką;
   - Rook z przejściami „trzy sposoby”;
   - test pełnej drogi Edron.
   Każdy powrót: jedno wywołanie na żywo.
3. **K3 odkładanie w Thais i na Rooku:** wzór `serwis.sh` z Edronu, czyli depo, sprzedaż i jedzenie. Wymaga nagrania przez Karola trasy po mieście i rozmów z NPC, jak w Edronie.
4. **F1 grafik + F2 wykonawca w cieniu** (dzień logów „co bym zrobił”), **F3 na żywo na 1 postaci** pełnym cyklem, **F4 obchód z białą listą**, **F5 cały zestaw i pula > 5**.

Kolejność proponowana: K1 → K2 (Edron najpierw, bo ma serwis) → F1–F3 na dawajkeshu (Edron = jedyne miasto z pełnym serwisem) → K3 → reszta.

## Decyzje (Karol 21.10 ~16:30)

- Q1: **5 online, Karol dołoży konta.** Do czasu nowych kont przerwy offline biorą się z puli 5: online jest tylu, ilu pozwala grafik.
- Q2: **zmiana = jeden hunt, zwykle 2–3 h.** Przerwa offline nie została podana; domyślnie 30–120 min, do zmiany w `grafik` (pole konfiguracji).
  Limit dzienny 8 h i cisza 01:00–08:00 zostają z 07:40.
- Q3: **cała biała lista bez pytania.** Eskalacje jak wyżej.
- Q4: **wszystko naraz:** K1, K2, K3 i F1–F2 równolegle (osobni agenci, rozłączne pliki); na żywo nadal po kolei, jedna postać.

- Q5 (Karol 21.10 ~17:05): **wybór spotu też robi nadzorca i miesza postacie między spotami.** Wymagania:
  - spot musi pasować do miasta, w którym postać faktycznie stoi (pozycja z gry, nie `tryb.log`/`ostatni_start`);
  - poziom postaci w widełkach spotu;
  - na jednym spocie najwyżej jeden własny bot;
  - kolejna zmiana tej samej postaci bierze, gdy się da, inny spot niż poprzednia.
  - Spot ma wymagania ekwipunku: lina, łopata, pochodnia. Nadzorca sprawdza ekwipunek przed wyborem spotu.
    - Przypadek: 21.10 17:12 dojście `trolle_edron_z9w_dojscie` wymaga liny (z11→z10→z9→z8→z7 liną).
    - Kolanosh poszedł bez liny i utknął na (33134,31806,z11); Karol go wylogował, wyciągnie ręcznie.
  - Do zbudowania: tabela spotów (miasto, piętra, widełki poziomu, potwory, dojście z depo) z `mapy.json` + `nowy-spot`, oraz wybór w `nadzor.py` przed `start_bota`.
  - Przypadek: 17:02 Kolanosh zalogowany w Edronie (depo), bot uruchomiony na `raty` (Thais) z `tryb.log` 15:22; zatrzymany po ~1 min, HP 100%.

## Pytania do Karola (zamknięte, odpowiedzi wyżej)

- Q1 pula: ile postaci i kont w rotacji (dziś 5 aktywnych = 5 online, czyli bez przerw)? Czy dojdą nowe konta? Przy 5 online
  i przerwach trzeba co najmniej 7–8 postaci.
- Q2 widełki: zmiana (propozycja 1,5–3 h), przerwa offline (propozycja 30–120 min), limit dzienny (dziś 8 h), cisza (01:00–08:00)?
- Q3 autonomia: czy biała lista „pomoc postaciom” wyżej jest OK bez pytania? Zwłaszcza zdjęcie STOP po alarmie bota i zmiana spotu.
- Q4 kolejność: K1 → K2 → cykl na dawajkeshu w Edronie jako pierwszy pełny przebieg?
