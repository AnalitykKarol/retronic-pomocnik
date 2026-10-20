# SPEC: „Wróć do miasta” i wylogowanie na Rookgaardzie - 20.10 — ZATWIERDZONA (Karol 20.10 ~23:10: Q2 stoi, Q3 tak, Q4 nie)

Cel: `./wroc.sh` (i guzik `⌂ Miasto`) działa także na Rookgaardzie, a gdy powrotu nie ma, jest bezpieczne
wylogowanie jednym poleceniem. Zlecenie Karola 20.10 ~22:45: „sprawdź, które da się wysłać do miasta, te co nie umieją,
trzeba im dorobić powrót albo wylogować, kiedy się da”; po rozmowie: „no to zrób, przyda się na przyszłość”.

## Stan dzisiaj (zmierzone 20.10 ~22:45)

- Sześć instancji, wszystkie na Rooku (`rook`, `rook_raty_z8`, `rook_raty_z8_do_smierci`, `rook_kanaly_z11`, `rook_bugi_z10`).
  `panel.py --json` dla każdej: `plan_depo_dostepny: false`. Powód: `wyprawa.BAZY` = (`troll`, `thais_kanaly`), `PLANY_PK` = Edron;
  plan `rook` z `wypad.PLANY` (`do_miasta.json`, z z11 (32021,32159) do (32061,32180,7)) jest celowo poza trybem depo
  (SPEC_wroc_do_miasta_1019, korekta po przeglądzie 19.10).
- Każdy spot Rooka ma nagrane dojście z miasta: `trasy/rook_{raty_z8,raty_z9,raty_z10,kanaly_z11,bugi_z10}_dojscie.json`,
  wszystkie zaczynają się w (32061,32180,7), kończą na spocie; `.meta` opisuje schody/kratki (`schody_w_dol`).
  `odwroc_trase.py` odwraca trasę razem z metadanymi (`schody_w_dol` -> `schody_w_gore`).
- Wylogowanie: Ctrl+L w kliencie (OTClient) działa — 20.10 kutangen: lista postaci po 1 próbie; kolanoth: serwer odmawiał
  w walce, udało się po 30 próbach co ~4 s przy walczącym bocie. **Wszystkie klienty mają `autoReconnect: true`**: po Ctrl+L
  klient sam zalogował postać ponownie po < 60 s. Działający sposób: Ctrl+L, a po zniknięciu ikon paska klienta
  (piksele W-80,17 i W-50,17) natychmiast `sesja_gry.py zamknij`. Prototyp: skrypt w scratchpadzie sesji Claude 20.10 (`wyloguj.py`).

## Proponowane zachowanie

1. **Powrót (F1):** dla każdego spotu Rooka plan w `wyprawa.PLANY_PK`: `do` = odwrócone dojście (`<spot>_dojscie_odwrocone.json`,
   generowane `odwroc_trase.py`), `z` = dojście. Cel = (32061,32180,7) i STOP, jak w Edronie. `_droga_do_depo` liczy drogę
   z bieżącej pozycji do trasy `do` (A* po piętrze + nagrane przejścia), więc nie trzeba stać na początku nagrania.
   Ryzyko: przejścia w górę (schody z8->z7 itd.) nie były chodzone w tę stronę; `zbuduj_etapy` musi je odtworzyć.
2. **Wylogowanie (F2, tylko polecenie):** `./wyloguj.sh` (z `RETRONIC_ID`): Ctrl+L co ~4 s przy działającym bocie (bot dobija potwory),
   po wylogowaniu `sesja_gry.py zamknij`; limit czasu, log w `<stan>/logi/`. Odmawia, gdy jest `STOP_RECZNY` bez bota
   (= Karol gra ręcznie, patrz niżej).
3. **Ochrona ręcznej gry:** każde narzędzie zbiorcze („wszystkie boty”) pomija instancję z `STOP_RECZNY` i bez procesu bota,
   chyba że Karol wymieni ją z nazwy.

## Cele powrotu (Q1)

Lista celów Rooka (sklepy z7, depo z8), z `dane_tibia/serwer74/npc_pelne.json`; pole stania wyznacza A* po mapie klienta przy ladzie:
| cel | NPC / punkt | pozycja NPC |
|---|---|---|
| depo zachód | sala skrzynek na **z8** pod budynkiem Lee'Delle, zejście schodami (32027,32197,z7) | z8 ok. (32025–32035, 32190–32199) |
| depo centrum | sala skrzynek na **z8** pod sklepem Normy (za mostem Dallheima, PACC), zejście schodami (32096,32190,z7) | z8 alejki x 32101/32103/32105, y 32180–32188 |
| sklep | Al Dee (start nagranych dojść) | (32063,32180,7) |
| sklep | Lee'Delle | (32024,32196,7) |
| sklep | Norma | (32098,32180,7) |
| sklep | Obi / Dixi | (32109,32204,7) |

- Przy każdym zleceniu bot losuje cel (waga: bliższe częściej, ale nie zawsze najbliższy), a w nim losowe wolne pole w promieniu
  2–3 pól od punktu, nie to samo co ostatnio.
- Rozdzielenie instancji: cel rezerwowany w `instancje/_wspolne/zajete.json` (`miejsca_koord.py`, ten sam mechanizm co
  `PATROL_KOORD`), więc dwa boty wracające naraz nie wybierają tego samego celu, dopóki są wolne inne.
- Droga: z bieżącej pozycji do z7 odwróconym dojściem swojego spotu (przejścia pięter z nagrania), dalej A* po z7 do celu;
  depo: A* do schodów, zejście na z8 (`schody_w_dol`), A* do wylosowanego pola w sali. Zejście do depo nie było chodzone botem.

## Pytania otwarte (Karol)

- Q1: **ROZSTRZYGNIĘTE (Karol 20.10 ~23:00):** cel to jedno z depo albo sklepów, losowane, żeby boty nie schodziły się
  za każdym razem w ten sam punkt. Patrz „Cele powrotu” wyżej.
- Q1a: **ROZSTRZYGNIĘTE (Karol 20.10):** „jedno na zachodzie, drugie w centrum, pod sklepem za mostem PACC”. Położenie z mapy klienta
  (`mapa.py`, rzędy pól nieprzechodnich = skrzynki, schody flaga 2 na z7 i z8 w tym samym polu); w grze botem niesprawdzone.
- Q2: **Karol:** po dojściu bot stoi (STOP), jak w Edronie.
- Q3: **Karol:** tak, `wyloguj.sh` zamyka klienta po wylogowaniu; `autoReconnect` zostaje.
- Q4: **Karol: nie.** Bez osobnego guzika. „To jest funkcjonalność miasta, ma robić dokładnie to samo”: Rook to po prostu kolejne
  miasto dla `wroc.sh` / `⌂ Miasto`, bez osobnej ścieżki w UI. `wyloguj.sh` zostaje poleceniem w terminalu.

## Weryfikacja

- Testy: generowanie odwróconych tras + `waliduj_trase.py`; `panel.plan_depo` zwraca plan Rooka dla pozycji z każdego spotu.
- Test: losowanie celu (rozkład, nie ten sam dwa razy z rzędu, rezerwacja między instancjami).
- Na żywo (zasada „jedno wywołanie”): jedna instancja, `./wroc.sh` z każdego piętra po kolei, dojście do wylosowanego celu bez pomocy.
- `wyloguj.sh` na jednej instancji w walce: wylogowanie po końcu walki, klient zamknięty, inne instancje nietknięte.

## Poza zakresem

Zakupy na Rooku, serwis, auto-refill, powrót na spot po wylogowaniu.
