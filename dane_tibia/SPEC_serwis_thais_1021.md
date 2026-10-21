# SPEC: serwis w Thais (odkładanie do depo, backpack; Frodo i Xodet za drzwiami) i ocena Rooka - 21.10 — K3, SZKIC do decyzji Karola

Faza K3 z `SPEC_nadzorca_rotacja_1021.md` (Karol 21.10 ~16:30: K1, K2, K3 i F1-F2 równolegle). Wzór: serwis Edron
(`SPEC_edron_serwis_1019.md`). Ten sam silnik (`serwis.py`, `serwis_akcje.py`), nowe są tylko dane `trasy/serwis_thais.json`
(+ `.meta`), ich generator i wybór miasta. Nic nie uruchomiono na żywo: trasa sprawdzona offline na mapie klienta.

## Stan dzisiaj (zmierzone 21.10)

- Wyprawa w Thais dochodzi do depo (32348,32225,7) i staje; `refill_auto.zlec` loguje „brak planu serwisu dla tego miasta; serwis ma: edron”
  (`refill_auto.py`, `MIASTA_SERWISU = ("edron",)`; woła go `wyprawa.py` `_zakoncz_depo`, ok. linii 2161).
- Nie było `serwis_thais.json`, `serwis.py` miał `choices=["edron"]`, `serwis.sh` na sztywno `edron`.

## Zrobione

| Plik | Co |
|---|---|
| `generuj_serwis_thais.py` | dane z mapy klienta i repo (bez nagrania); `--sprawdz` porównuje z plikami na dysku |
| `trasy/serwis_thais.json`, `.meta` | przystanki, wnęki depo, drzwi, źródła i lista niezmierzonego |
| `serwis.py` | wybór miasta (`edron` domyślnie, `thais`, `auto` = z pozycji), odrzucanie kroków za drzwiami przed pierwszym ruchem |
| `serwis.sh` | `SERWIS_MIASTO` (domyślnie `edron`) |
| `testy/test_serwis_thais.py` | 57 testów offline |
| `*.bak-20261021-k3` | kopie `serwis.py`, `serwis.sh`, `serwis_akcje.py` (ten ostatni bez zmian) |

## Kroki Thais i źródło każdej współrzędnej

Domyślna kolejność (to, co serwis umie dziś): **depo, backpack, wyjscie**. Pełna po obsłudze drzwi: depo, jedzenie, backpack, blanki, wyjscie
(pole `kolejnosc_po_drzwiach`, serwis jej nie czyta).

| Krok | NPC / punkt | Pole stania | Źródło | Zmierzone na żywo? |
|---|---|---|---|---|
| przybycie / wyjście | podłoga sali depo | (32348,32225,7) | start `depo_troll_cave`, `S7` w `generuj_trasy_thais_pn.py`, log invincible 21.10 16:13 | tak (wyprawa tam staje) |
| depo, wnęka 1 | skrzynia (32343,32225,7) | (32343,32226,7) | `wyprawa.POLE_ZLOZ_DEPO`, Use na północ | **tak, 13.10** |
| depo, wnęki 2-4 | skrzynie na północ od pola | (32341,32226,7), (32352,32226,7), (32354,32226,7) | ślepe wnęki sali depo z mapy klienta (`mapa.py`), wzór wnęki 1 i Edronu | **nie**: że tam stoi skrzynia, nie ściana |
| backpack | Gorn (32377,32200,7), 20 gp | (32377,32201,7) | ostatni punkt `troll_do_miasta.json`; NPC i cena z `npc_pelne.json` | pole tak (wyprawa kończy tam trasę), **dialog nie** |
| jedzenie | Frodo (32356,32209,7), ham 8 gp | (32358,32210,7) | `wyprawa_sklepy.json`, zmierzone 13.10 `hi -> buy 3 ham -> yes` | **tak** |
| blanki | Xodet (32399,32222,7), blank rune 10 gp | (32400,32220,7) | `wyprawa_sklepy.json`, zmierzone 14.10 `buy 20 blank rune -> yes` | **tak** |
| bank | Suzy (32320,32258,7) | **brak** | `npc_pelne.json` | **nie**: pole stania, wejście, dialog |

Trasa: A* serwisu (`Planer` na `wyprawa.Trasownik`) od przybycia do każdej wnęki, Gorna i z powrotem, 0 braków, najdłuższa 50 pól (przybycie -> Gorn).
Wszystko na z7, więc `laczniki` jest puste. Wnęki: najbliższa wg drogi jest wybierana pierwsza (dziś (32352,32226), 7 pól),
niezmierzona wnęka zawodzi bezpiecznie: `_otworz_depo` nie dostaje lockera, `depo_zloz` zwraca False i serwis idzie do następnej.

`depo.stoi` w pliku to punkt przybycia, nie wnęka: `panel.miasto_pozycji` liczy „w depo” (<= 2 pola) od `depo_stoiska` i `przystanki.depo.stoi`,
a wyprawa staje w (32348,32225), czyli 4-5 pól od najbliższej wnęki. Bez tego `refill_auto` uznałby „postać nie stoi przy depo”.

## Drzwi (blokuje jedzenie i blanki)

Frodo i Xodet stoją w sklepach za drzwiami, które mapa klienta widzi jako ścianę (flaga 4): `(32365,32208,7)` (chata Frodo) i `(32400,32217,7)`
(wieża Xodeta). Wyprawa je zna (etapy `DRZWI`, Use z pola obok), serwis nie. Wyprowadzone z mapy i nagranych dojść w `wyprawa_sklepy.json`
(reguła `wypad.drzwi_z_mapy`). Test 3c: bez drzwi te dwa pola stania są nieosiągalne z przybycia, z drzwiami osiągalne.

Skutek: `serwis.py` odrzuca każdą listę kroków z `jedzenie` albo `blanki` **przed pierwszym inputem** (`SerwisBlad("start", ...)`), bo bez tego A*
przeszukiwałby minutami całą mapę i dopiero potem zgłosił brak drogi. `plan` na sucho pokazuje je jako BRAK DROGI.

**Dalszy krok K3b (nie zrobiony, poza zakresem):** obsługa drzwi w `serwis.py`: łącznik „drzwi” w `Planer` (pole przed -> pole za, koszt jak łącznik),
w `chodz` podział trasy na drzwiach: dojście do pola przed, Use (Ctrl+klik jak `_otworz_depo`), kontrola otwarcia, krok przez drzwi, dalej. Wzór: `wypad._drzwi`
(do 6 prób, Use na zmianę z krokiem). Potem `Serwis.obsluga_drzwi = True` i `kolejnosc` = `kolejnosc_po_drzwiach`. ~60-80 linii + testy na atrapach.
Bez tego serwis Thais nie kupi ham ani blanków, a depo bez blanków zostawia postać bez materiału na UH.

## Co nagrać / zmierzyć (Karol)

1. **Gorn, `backpack`:** `hi` -> `backpack` -> `yes` stojąc na (32377,32201,7); oczekiwane „Do you want to buy a backpack for 20 gold?” (ta sama oferta co Beatrice w Edronie).
2. **Wnęki depo:** wejść na (32341,32226), (32352,32226), (32354,32226) i zrobić Ctrl+klik na polu na północ; czy otwiera się locker, czy to ściana.
3. **Bank Suzy:** gdzie stanąć, którędy wejść do banku (drzwi), czy `change gold` działa jak u Ebenizera (`hi`, `change gold`, liczba platinum, `yes`).
   Do tego czasu bank NIE jest w danych (nie zgadujemy). Bez banku gold zostaje goldem (bez wymiany na platinum), zakupy wystarczają.
4. **Drzwi sklepów** (K3b): przy pierwszej próbie przejść Frodo i Xodeta przy Karolu (otwarcie Use i przejście).
5. **Cały serwis Thais jedną postacią:** `SERWIS_MIASTO=thais ./serwis.sh` (depo, backpack, wyjście), plus powrót na spot po wyjściu. Wymaga postaci z bagiem z UH i >= 20 gp (poza tym nic).

## Włączenie w wyprawę (robi lead; nie moje pliki)

Punkt, o który pytałeś, **nie jest w `wyprawa.py`**: komunikat pochodzi z `refill_auto.py:106`, który woła `wyprawa.py:2161` (`_zakoncz_depo`).
`wyprawa.py` nie wymaga zmian. Diff w raporcie: `refill_auto.py` (`MIASTA_SERWISU`) i `refill.sh` (miasto z pozycji).
Uwaga: `refill.sh` domyślnie robi `jedzenie,backpack,blanki,wyjscie` (bez depo, decyzja 19.10), więc dla Thais zakończy się porażką na starcie (drzwi).
Dla Thais bez drzwi: `REFILL_KROKI=depo,backpack,wyjscie`, ale wtedy postać startuje bez ham i blanków. Rekomendacja: nie włączać auto-refillu Thais przed K3b.
Skutki uboczne wpisu `serwis_thais.json`: `panel.miasto_pozycji` uznaje Thais za miasto (guziki paska), więc `test_refill.py` 1c (Thais „nie w mieście”) jest czerwony z założenia.

## Rook: ocena wykonalności (bez kodu)

Rook (`SPEC_powrot_rook_1020`): cel powrotu (32061,32180,7) i STOP, depo na z8: zachód (sala ok. x 32023..32035, y 32193..32198, wejście schodami (32027,32197,z7))
i centrum (alejki x 32101/32103/32105, y 32180..32188, schody (32096,32190,z7)). Widoczne na mapie klienta jako wnęki jak w Thais.

Wykonalne, ale to osobna praca, nie kopia Thais:
1. **Akcja „odłóż łup” zamiast `depo_zloz`.** Na Rooku nie ma baga z UH ani platinum (poniżej poziomu 8 brak UH, waluta to gold); `depo_zloz` odkłada bag z UH i platinum ponad 3.
   Trzeba nowej akcji (np. `depo_loot`): przenieść do skrzyni wskazane przedmioty z plecaka (łup), zostawić jedzenie i gold. Wymaga decyzji Karola, **co zostaje w plecaku**.
2. **Łączniki pięter.** Rook ma z7 (miasto) i z8 (depo): `laczniki` nie może być puste. Schody (32027,32197) i (32096,32190) z mapy (`serwis.pola_schodow`), generator mógłby
   je wyprowadzić, ale zejście do depo Rooka **nie było chodzone botem** (`SPEC_powrot_rook_1020`), a przejścia pięter na Rooku są zawodne (lina/drabina, `AUDYT_1021.md`).
3. **Wnęki depo na z8** z mapy (jak w Thais, pole stania + skrzynia na N lub S) i **skrzynia Rooka może być jednopoziomowa** (nie locker -> depot chest): niezmierzone, `_otworz_depo` zakłada dwa poziomy.
4. **NPC:** brak banku i brak blanków (Rook nie ma run). Jedzenie: Billy (32037,32205,7) i Willie (32047,32204,7), ham 8 gp, po stronie farmy; backpack 10 gp u Al Dee,
   Lee'Delle, Norma, Obi, Dixi (`npc_pelne.json`). Pola stania, drzwi i dialogi niezmierzone. `LIMITY_CENY` (ham 12, backpack 25) pasują.
5. **Dane i dalszy krok:** `generuj_serwis_rook.py` (analogiczny), `trasy/serwis_rook.json`, `choices` w serwisie już się dostosuje (plik = miasto); `refill_auto.MIASTA_SERWISU`.
   Najpierw K2 (pewny powrót na Rooku), potem pomiar zejścia do depo przy Karolu.

Ocena: depo + ham na Rooku to jedna faza po K2 (szacunek bez pomiaru); największe ryzyko to przejścia pięter i brak pomiaru skrzyni depo Rooka.

## Ryzyka

- Wnęki 2-4 depo niezmierzone (mogą być ścianą); fallback istnieje, ale pierwsza próba może zająć kilka sekund Ctrl+kliknięć w ścianę.
- Gorn: dialog niezmierzony; gdyby oferta miała inną postać niż `buy a <rzecz> for N gold`, `zamow` odrzuci zakup (zakup nie dojdzie do skutku, nic nie wydane).
- Pole stania u Gorna (32377,32201,7) może być zajęte przez gracza (tolerancja 0): serwis zgłosi błąd i STOP, nie szuka innego miejsca.
- Serwis bez Frodo/Xodeta zostawia postać bez ham i blanków (patrz „Włączenie w wyprawę”).
- Trasa i drzwi to tylko mapa klienta; w grze mogą stać gracze, meble, zamknięte inne drzwi na A*.
