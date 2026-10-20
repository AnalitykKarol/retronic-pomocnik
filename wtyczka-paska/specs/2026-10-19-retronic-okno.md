Status: approved (Q1-Q6 Karol 19.10 ~21:14) — realizacja od F1
Weight: Feature (nowe okno, QML; rozszerza `2026-10-19-retronic-wtyczka-paska.md`, pasek bez zmian)
Projekt: Retronic, zarządzanie botami z pulpitu

# Okno zarządzania Retronic (QML)

## TLDR

Obok szybkiego panelu na pasku (zostaje bez zmian: „ostatnie, co było”) powstaje normalne okno do pracy z botami, bo
ustawień robi się za dużo na popup (307 pokręteł, 12 map, 9 trybów, ratunek). Okno w QML, w stylu paska (Omarchy, Tokyo
Night, JetBrains Mono). Jak wtyczka: cienkie, cała logika i zapis w skryptach/Pythonie bota, okno tylko czyta JSON i woła
polecenia.

## Decyzje Karola (19.10)

| Temat | Decyzja |
|---|---|
| Technologia | QML jak pasek (Quickshell), nie Tkinter i nie strona w przeglądarce (web odrzucony już 17.10, `design-system/MASTER.md`) |
| Pasek | bez zmian; okno to osobna rzecz |
| Zakres v1 | Sesja gry, Mapa i tryb, Ustawienia pokręteł, Ratunek |
| Układ | wariant **B** (pasek boczny: karty postaci + menu sekcji) z **wyszukiwarką Ctrl+K** z wariantu C i **widokiem ustawień** z A (grupy, suwak/przełącznik, „niezapisane zmiany” Cofnij/Zapisz). Karol: „zajebiste” po rekomendacji B+C+A. Makiety: `specs/makiety-okno-1019/wariant-{a,b,c}.png` |

## Odpowiedzi Q1-Q6 (Karol 19.10 ~21:14)

| Q | Odpowiedź | Co z tego wynika |
|---|---|---|
| Q1 | „może być skrót i guzik po otworzeniu w pasku mini menu” | skrót klawiszowy + jeden guzik „Otwórz okno” w popupie paska (jedyna zmiana paska) |
| Q2 | „mogą być angielskie” | bez tłumaczenia 307 nazw na polski: wiersz = nazwa techniczna + opis z komentarza `pokretla.py` (interpretacja agenta) |
| Q3 | „od razu po puszczeniu” | zapis do `na_zywo.json` od razu po puszczeniu suwaka / kliknięciu przełącznika; bez paska Zapisz, jest „Cofnij ostatnią” |
| Q4 | tylko otwarcie gry, gdy jej nie ma, i zamknięcie, gdy jest; proxy będzie nowe; docelowo **10 postaci** | Sesja gry v1 = Uruchom grę / Zamknij grę; proxy jako ustawienie instancji przygotowane pod wiele proxy (bez obecnego `siec_proxy.sh` na sztywno); cały układ (pasek boczny, `okno_api stan`) liczony na 10 instancji |
| Q5 | „tak i od razu sprawdzać haiku” | „To fałszywy alarm” zapisuje etykietę; przy sygnale w oknie widać też odpowiedź Haiku (co by zrobił) — **zależy od ratunku F2a: Haiku w cieniu**, do potwierdzenia przez Karola, czy wołać Haiku przy każdym sygnale automatycznie |
| Q6 | „tak, do wyjebania” | panel Tkinter (`feat/ui-reczne-ai`, `../pomocnik-ui`) nie jest rozwijany; usunięcie worktree/brancha osobno, po zgodzie |

Skala 10 postaci: pasek boczny ma zwijane karty (nick + kropka + mini HP), lista przewijana; `okno_api stan` czyta instancje
równolegle i w limicie czasu; odświeżanie co 2 s tylko wybranej postaci, pozostałe co 5 s.

## Układ (wariant B)

- **Pasek boczny (260 px):** karta na postać (kropka stanu, nick, instancja `główna`/`test · proxy`, mapa · tryb, paski HP/MP),
  kliknięcie wybiera postać; pod kartami menu sekcji wybranej postaci: Sesja gry · Mapa i tryb · Ustawienia · Ratunek (licznik
  dzisiejszych sygnałów). Na dole: Stop/Start i ⌂ ↻ ↗ jak na pasku (te same akcje, te same reguły szarości z `RetronicModel.js`).
- **Główna część:** nagłówek sekcji + opis, treść sekcji. Stopka: stan obu botów, czas odświeżenia.
- **Ctrl+K:** paleta wyszukiwania po pokrętłach (nazwa, opis, grupa), mapach, trybach i akcjach, dla wybranej postaci;
  Enter otwiera pokrętło w Ustawieniach, Esc zamyka.

## Sekcje v1

1. **Sesja gry (Q4):** stan sesji instancji; gdy gry nie ma: Uruchom grę (`sesja.sh` z proxy z ustawień instancji); gdy jest:
   Zamknij grę (z potwierdzeniem). Proxy = pole instancji (brak / nazwa proxy), przygotowane pod wiele proxy; bez tworzenia instancji.
2. **Mapa i tryb:** wybór mapy (`mapy.json`, z opisem) i trybów (`tryby.json`, wiele naraz), ostatnio użyte
   (`ostatni_start*.env`); „Start z tym” = `uruchom.sh` z `MAPA`/`TRYB` (+ `RETRONIC_POSTAC`). Zmiana działa przy następnym starcie
   — okno to mówi wprost.
3. **Ustawienia:** grupy pokręteł (lista z licznikiem + wyszukiwarka), w grupie wiersz: polska nazwa, nazwa techniczna i opis
   (z komentarza w `pokretla.py`), suwak z zakresem z `ZAKRESY` albo przełącznik 0/1, pole wartości; wartość różna od domyślnej
   wyróżniona; filtr „tylko zmienione”. Zapis do `na_zywo.json` instancji **przez walidację `pokretla.py`** (te same granice co bot),
   bot czyta na żywo. Pasek „N niezapisanych zmian” z Cofnij/Zapisz (Q3).
4. **Ratunek:** liczniki (dziś, ostatnia godzina / limit, najczęstszy kod, stan Haiku), lista sygnałów z `logi/ratunek-*.jsonl`
   instancji (czas, kod, co, gdzie), szczegóły wybranego (stan bota, liczby, co zrobiłby F2), „To fałszywy alarm” (Q5),
   „Pokaż w logu”. Zrzut z gry w szczegółach dopiero, gdy ratunek zacznie je zapisywać (F2).

## Zaplecze (Python, w repo bota)

Nowe `okno_api.py` (CLI, JSON na stdout, bez zależności), żeby QML nie parsował plików bota sam:
- `okno_api.py stan` — obie instancje: to, co dziś `panel.py --json`, plus sesja (procesy) i ostatnia mapa/tryb.
- `okno_api.py pokretla [--instancja ID]` — meta: klucz, grupa, zakres, domyślna, bieżąca, opis, polska nazwa (jeśli jest).
- `okno_api.py ustaw --instancja ID KLUCZ=WART …` — walidacja `pokretla.waliduj`, kopia `.bak` przy pierwszej zmianie dnia, zapis
  atomowy, wynik/błędy w JSON.
- `okno_api.py ratunek [--instancja ID] [--od DATA]` i `ratunek-oznacz --id … --falszywy` (Q5).
- `okno_api.py mapy-tryby`.

## Uruchamianie (Q1)

Osobny proces `quickshell -p <repo>/okno/` (żeby restart paska/shella nie zamykał okna i odwrotnie), skrypt `okno.sh`
(jeden egzemplarz: drugi start podnosi istniejące okno). Wejście: skrót klawiszowy i/lub pozycja w launcherze (plik `.desktop`)
— to `~/.config`/`~/.local` = poziom 2, osobna zgoda.

## Fazy (bramki)

- **F1 zaplecze:** `okno_api.py` + testy (atrapy katalogów instancji; zapis tylko przez walidację; błędne wartości odrzucone).
- **F2 szkielet okna + Ratunek + Mapa i tryb:** pasek boczny, karty postaci, akcje jak pasek, sekcje tylko do odczytu + start z mapą/trybem.
- **F3 Ustawienia + Ctrl+K:** grupy, edycja, Zapisz/Cofnij, wyszukiwarka.
- **F4 Sesja gry:** start/zamknięcie gry, podgląd, proxy. Rozpisana 20.10 (niżej, „F4: rozpiska”).
- QA każdej fazy: QML w Quickshell offscreen na atrapie (jak wtyczka 19.10) + zrzut z prawdziwymi danymi obu postaci; akcje
  zmieniające grę/bota tylko na atrapie, na żywo jedna próba za zgodą Karola.

## F4: rozpiska (20.10)

Zmiana od 19.10: proxy nie jest polem do wyboru, tylko stałym profilem instancji (`instancje/<id>/profil.json`: proxy, oczekiwane
IP, konto, postać, plus `tozsamosc.json`; `dane_tibia/SPEC_tozsamosc_sprzetu_1020.md`). Start bez profilu albo z IP spoza profilu
jest blokowany. `zamknij_sesje.sh` zamyka WSZYSTKIE sesje (`pkill -x sway`, `wineserver -k`), więc okno go nie używa.

Decyzje Karola 20.10: **D-F4-1** proxy i profil w oknie **tylko do odczytu**, ustawione na stałe (zmiana poza oknem).
**D-F4-2** próba na żywo na **nowej instancji** (działających postaci nie przerywamy).

- **F4a zaplecze:** `okno_api.py sesja --instancja ID` (tylko odczyt: sesja, gra, bot, proxy, od kiedy, port VNC i czy podgląd
  otwarty, profil bez hasła, tożsamość, czy start możliwy, ostatnie linie logu startu, wynik sprawdzenia IP).
  `sesja_gry.py start|zamknij|podglad` (akcja dla `RETRONIC_ID`, jak inne skrypty akcji okna):
  start = sprawdzenie profilu (`profil.sprawdz_unikalnosc`), odmowa przy działającej sesji, `sesja.sh` odłączony z `RETRONIC_POSTAC`
  z profilu, log `logi/sesja-RRRRMMDD.log`; zamknij = tylko ta instancja: `zatrzymaj.sh` (bot), `swaymsg -s <swaysock tej sesji> exit`,
  czekanie, awaryjnie TERM strażnika tej instancji i `wineserver -k` z jej `WINEPREFIX`; podgląd = `podglad.sh` odłączony.
  Główna instancja: bez akcji z okna.
  **Wykonane 20.10 (bez commita):** `okno_api.py sesja`, `sesja_gry.py`, `testy/test_sesja_gry.py` 48/48 (atrapy: m.in. `dwa` vs `dwa2`
  i główna nietknięte przy zamknięciu `dwa`, prawdziwe `subprocess`/`setsid` na nieszkodliwym poleceniu), `test_okno_api` 136/136,
  checker NITS (wszystkie poprawione). Na żywo tylko odczyt `sesja` dla 4 instancji (IP zgodne) i odmowy dla głównej/nieznanej.
  **NIEZWERYFIKOWANE do F4c:** czy `swaymsg exit` faktycznie kończy grę wine, strażnika i `siec_proxy.sh` (jest ścieżka awaryjna TERM).
- **F4b okno:** sekcja odblokowana w menu, karta stanu, blok profilu tylko do odczytu (IP zgodne/niezgodne), Uruchom grę / Zamknij grę
  (potwierdzenie; przy działającym bocie dodatkowe ostrzeżenie) / Otwórz podgląd, ostatnie linie logu startu, podpowiedź
  „zaloguj postać w podglądzie”.
  **Wykonane 20.10 (agenci fe-dev, bez commita):** `okno/SesjaView.qml` (stan, profil tylko do odczytu z odznaką IP, Uruchom / Zamknij z
  potwierdzeniem i ostrzeżeniem o bocie / podgląd), level i klik w nick na kartach, blokada akcji per instancja (`ActionRun.qml`; zamykanie
  jednej postaci nie blokuje Stop innych), limit akcji sesji 120 s. Testy: node 203/203, `qml-atrapa`/`qml-ustawienia`/`qml-sesja` WSZYSTKO OK
  (scenariusz G: wolne zamykanie `ipzle`, Stop `dzial` klikalny), checker NITS poprawione. Na żywo tylko zrzut odczytu (invincible).
- **F4c QA:** Quickshell offscreen na atrapie, zrzut z prawdziwymi danymi (odczyt), jedna próba start → zamknij na żywo na nowej
  instancji (za zgodą Karola), README okna, `STAN.md`; Q6 (usunięcie panelu Tkinter) osobna zgoda.
  **Wykonane 20.10 ~19:17 na żywo (zgoda Karola „zrób to jeszcze”):** nowa instancja testowa `proba` (świeży prefiks, Webshare nr 3
  92.119.182.109, bez konta), polecenie przycisków okna: `sesja_gry.py start` → IP zgodne, klient do ekranu aktualizacji, Remmina otwarta
  sama; `zamknij` → najpierw awaryjny TERM (swaymsg exit zwraca „Unable to receive IPC response”, bo sway kończy się przed odpowiedzią),
  poprawione: drugi przebieg `sway: exit` w 3 s, bez TERM, okno Remmina zamknięte, pozostałe 4 sesje i boty nietknięte.
  `proba` w `instancje/_archiwum/proba-f4c-20261020`, profil Remmina w `~/.local/share/remmina/archiwum/`. Klikanie w samym oknie QML:
  sprawdzone tylko na atrapie (`qml-sesja.sh`), na żywo wołane to samo polecenie.

## Pytania otwarte (decyzja Karola)

- **Q1 Jak otwierać okno:** skrót klawiszowy (np. Super+Shift+R) czy launcher (Walker), czy oba? Czy na pasku ma się pojawić
  jedna linia „Otwórz okno” (to jedyna zmiana paska)? Rekomendacja: skrót + launcher, pasek bez zmian.
- **Q2 Polskie nazwy pokręteł:** dla wszystkich 307 czy dla ok. 60 najczęściej zmienianych (reszta w grupie „Zaawansowane” po nazwie
  technicznej i opisie z komentarza)? Rekomendacja: 60 w v1.
- **Q3 Zapis:** przyciskiem Zapisz (makieta A) czy od razu po puszczeniu suwaka? Rekomendacja: Zapisz (bot czyta na żywo, łatwo
  o przypadkową zmianę przy działającej postaci).
- **Q4 Sesja gry w v1:** tylko start/zamknięcie/podgląd/proxy, bez tworzenia nowej instancji (zostaje `nowa_instancja.sh`)?
- **Q5 „To fałszywy alarm”:** zapisujemy etykietę przy sygnale (dane do strojenia progów przed F2 ratunku)?
- **Q6 Panel Tkinter** (`feat/ui-reczne-ai`): po F4 do archiwum (nie rozwijamy dwóch okien)?

## Poza zakresem v1

Nagrywanie tras i spotów, robienie run, handel, podgląd gry osadzony w oknie (VNC zostaje osobnym oknem), wykresy exp.
