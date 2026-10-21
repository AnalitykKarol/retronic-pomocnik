# Nowy spot od zera do bota na żywo — procedura dla AI

Cel (Karol, 21.10): trasy tworzy i testuje AI od początku do końca. Karol wskazuje najwyżej miasto, postać i mówi „puszczaj”.
Ta procedura to dokładnie to, co 21.10 dało działające spoty: Edron trolle z9 wschód i **Thais północ (kutangen, żywy test)**.
Skill, który ją prowadzi: `skille/nowy-spot/SKILL.md`. Metoda map i jej granice: `README.md` obok.

Wszystko poniżej poza krokiem 7 to odczyt plików i generowanie plików w repo bota. Gra jest ruszana dopiero w kroku 7.

## 0. Kontekst, zanim cokolwiek policzysz

- Kto gdzie stoi: `python3 -I nadzor_stan.py` (wszystkie instancje) albo `RETRONIC_ID=<id> python3 -I panel.py --json`
  (pola `pozycja`, `level`, `class`). Zajęte spoty = mapy z `instancje/<id>/logi/tryb.log` (ostatni `[TRYB] mapa`).
- Poziom postaci decyduje o `--max-cios`: lvl 8–15 → 45–50 (cios = `atak_max_szac`, zawyżony, więc ostrożny).
- Życzenia Karola są ZAKAZAMI przy życiu postaci (np. „ma omijać poison spidery”): wchodzą do generatora jako strefa zakazana,
  nie jako uwaga w raporcie.

## 1. Wybór spotu: składowe mapy, nie odległość

    python3 -I narzedzia/spoty_skladowe.py --miasto Thais --pietra 7-12 --max-cios 50

- Spot = **składowa mapy** (obszar oddzielony ścianami), nie skupisko spawnów w promieniu. 20.10 grupowanie po odległości
  sklejało osobne jaskinie; 21.10 składowe pokazały np. że Edron trolle z9 to dwie osobne jaskinie (34 i 15 trolli).
- `bot: -` = nikt tam nie chodzi. Sufit exp/h to górna granica z respawnu, nie pomiar.
- Sprawdź groźne sąsiedztwo: smoki/cyklopy w składowych obok (Edron z8: 2 smoki na N; Thais północ: cyklopy na z9
  pod przejściami z z8). Te przejścia trasa ma omijać — A* bota sam nie wchodzi na pola flagi 2 w pętli.
- Za mała składowa (< ~15 potworów, pętla < ~60 pól) = doczepka do sąsiedniej, nie osobny spot (Edron z10 wschód: 35 pól).

## 2. Przejścia pięter: kierunek z mapy, typ z gry

    python3 -I narzedzia/przejscia_pieter.py --obszar x0,y0,x1,y1 --pietra 7-9

Reguły (każda kosztowała nas jedno nieudane wejście 21.10):
1. **Żółte (kolor 210) to NIE „zejście”.** Pole przejścia, nad którym na z-1 jest coś chodliwego, prowadzi W GÓRĘ
   (Thais północ (32345,32146,z7) → kutangen wszedł na z6). Zejście = flaga 2 bez niczego chodliwego wyżej, z chodliwym
   polem obok niżej (tam kolor 24).
2. **Stoi na polu i nie spada, use bez skutku = zasypana dziura → ŁOPATA.** Dopisz pole do `pietra.ZASYPANE` (kopia
   `pietra.py.bak-<data>-<tag>`, testy pięter niżej), postać musi mieć shovel. Znane: (32493,32259,7) Thais wschód,
   (32347,32123,7) Thais północ. Bot sam zejdzie z pola, odkopie i wejdzie krokiem; mapa tego nie odróżnia od zwykłej dziury.
   Od 21.10 (F4): udane zejście po łopacie zapisuje się w `dane_tibia/ruch/przejscia_nauczone.json` jako `lopata`, a pamięć
   `lopata` sama włącza łopatę (bez wpisu w `ZASYPANE`); `PIETRA_LOPATA_AUTO=1` = łopata na każdym zejściu w dół.
3. Powierzchnia bywa bez flagi nad zejściem (Edron (33117,31776,z7): zwykłe pole) — wtedy kandydat z z8 („nad: z7”) albo nagranie.
4. Lina: z8 (x,y) → z7 (x,y+1). Drabina w górę bez dziury nad nią (Thais północ z9 (32339,32122)) = przejście tylko w górę.
   **Pola liny NIE da się użyć (Karol 21.10), gdy:** postać na nim stoi, stoi na nim ktoś inny (gracz, potwór) albo coś na nim
   leży (zwłoki, przedmiot). Pole stania przy linie = SĄSIAD pola liny, nigdy samo pole; przed użyciem liny pole musi być wolne
   (zejść z niego, poczekać, aż ktoś zejdzie, przesunąć przedmiot).
6. **OGIEŃ ≠ przejście (21.10, Edron (33115,31744,z8)):** flaga 2 mają też ogień i przeszkody. Flaga 2 w kolorze podłogi
   wokół (nie 210) poza z7 = PRZESZKODA (`spot_lib.przeszkoda_na_podlodze`). Invincible stał na takim „zejściu” w ogniu,
   HP 91% → 58% w 30 s; prawdziwe zejście obok miało kolor 210 (33119,31740). Znany ogień z `trasy/ogien_*.json` + bufor 1
   = ściana dla A* (`generuj_trasy_edron_wschod.ogien_pola`).
5. Jeśli dwa zejścia: wybierz to, którego droga trzyma się dalej od zakazanego (Thais północ: 23 pola vs 11), nawet
   kosztem kilku pól.

## 3. Generator spotu (jeden plik na spot)

Wzór: `generuj_trasy_thais_pn.py` (pełny: strefa zakazana, wykrywanie zejść, dojście z depo do pętli) albo
`generuj_trasy_edron_wschod.py` (dojście = istniejące nagranie + doklejone piętra). Wspólne klocki:
`generuj_trasy_rook.py` (`skladowa`, `przystanki`, `petla`, `obraz`) i `generuj_trasy_rook_raty2.py`
(`przed_przejsciem`, `ladowanie`).

Co generator musi zrobić:
- **Pętla**: składowa od spawnu celu, przystanki ze spawnów listy `CEL`, kolejność NN + 2-opt po A*. Strefa zakazana
  (promień `STREFA` wokół spawnu zakazanego potwora) wchodzi jako ściany do składowej I do A*, a przystanki trzymają się
  `STREFA + 2` od środka. Na końcu asercja: żaden punkt pętli w strefie.
- **Dojście**: start z depo miasta (Thais (32348,32225,7) = start `depo_troll_cave`; Edron: koniec `edron_depo_trolle`
  (33117,31775,8)), A* do pola PRZED zejściem, pole zejścia, lądowanie, i **dalej po z8 aż do pętli drogą omijającą strefę**
  (A* bota nie zna strefy — samo lądowanie by nie wystarczyło). Meta: `przed_zmiana_pietra` + `schody_w_dol` z opisem
  typu (łopata, lina) — bot i ludzie czytają ten komentarz.
- **Podgląd** PNG w `dane_tibia/mapy/<spot>.png` (strefa zakazana na fiolet) + JSON z przystankami.
- Bez `--zapisz` tylko liczy; z `--zapisz` pisze `trasy/<spot>_petla`, `trasy/<spot>_dojscie(.meta)`, PNG, JSON.

## 4. Walidacja offline (wszystko musi przejść, zanim gra)

    python3 -I waliduj_trase.py <spot>_petla        # „trasa OK”
    python3 -I waliduj_trase.py <spot>_dojscie      # „trasa OK” albo błąd odziedziczony z nagrania (porównaj z oryginałem)
    python3 -I tryb.py --mapa <spot> --sucho --log <scratch>/t.log --na-zywo <scratch>/nz.json   # MAPA_DOJSCIE niepuste

Obejrzyj PNG (Read). Pętla nie może wchodzić w fiolet, start przy spawnach celu, przystanki = spawny.
Kontrola ognia: żaden nowy punkt pętli/dojścia na polu z `trasy/ogien_stale.json`/`ogien_epizody.json` ani obok.
**Powrót do depo z pętli (21.10, Kolanosh z9w 20:14 utknął):** spot na innym piętrze niż pętla planu powrotu (np. pod z8
Edron) potrzebuje wpisu w `wyprawa.PLANY_PK[...]["wyjscia"]` (pole liny, lądowanie, trasa dalej, pole stania obok) i testu
`droga_do_depo` z każdego punktu pętli do depo. Bez tego `wroc.sh`/wyprawa = „depo: brak drogi” i STOP. Wzór:
`generuj_powrot_edron_z9w.py`, `testy/test_powrot_edron_z9w.py`.

## 5. Wpis w `mapy.json`

Kopia `mapy.json.bak-<data>-<tag>` i zapis przez json (indent 2, atomowo `.tmp` + `os.replace`). Potem porównanie z kopią:
zmienione mają być TYLKO Twoje klucze (inne sesje też edytują ten plik). Pola: `opis` (skąd, ile potworów, co omija, typ
zejścia, wymagania: łopata/lina), `trasa`, `potwory` (nazwy dokładne, casefold; „Spider” ≠ „Poison Spider”), `prog_hp`, `dojscie`.

## 6. Postać przed startem

- `RETRONIC_ID=<id> python3 -I panel.py --json` → `pozycja`: dojście dostaje się tylko z **z7** (albo mapa z
  `dojscie_z_dowolnego_pietra`). Na innym piętrze najpierw ją sprowadź (krok 7 niżej, „ratunek”).
- `instancje/<id>/wyprawa_stan.json`: `aktywna: true` = po starcie bot najpierw dokończy starą wyprawę do depo i stanie
  (STOP). Wtedy daj mu dojść (zwykle chwila), potem start na nowej mapie.
- **Ekwipunek z opisu mapy** (`mapy.json` → `opis`: „MUSI mieć rope”, „ŁOPATY”): bez liny bot staje na pierwszym przejściu w górę
  liną (21.10 kolanoth 17:09: z11→z10 (33133,31805) 5 prób, STOP; po dołożeniu liny 17:25 próba 2). Łopata: zasypane dziury z7.
  Exura: `ZDROWIE_CZAR_AKTYWNY` w `instancje/<id>/na_zywo.json`.
- Postać nie na z7: jeśli mapa ma `dojscie_z_dowolnego_pietra: true`, bot rusza od najbliższego punktu dojścia na swoim
  piętrze (kolanoth 21.10 z (33167,31823,z9), czyli ze środka `edron_depo_trolle`) — wtedy nie trzeba go sprowadzać.
- `STOP_RECZNY` = Karol gra tą postacią: start dopiero na jego „puszczaj”.

## 7. Start i test na żywo (gra — tylko po „puszczaj” Karola)

    RETRONIC_ID=<id> RETRONIC_POSTAC=<nick z instancje/<id>/profil.json> MAPA=<spot> TRYB=<jak dotąd, np. ostrozny,ml> ./uruchom.sh

- **Dowód dobrego startu**: linia `Start (… + dojście)` i w `instancje/<id>/logi/mozg-stdout-*` `Dojście: trasa <spot>_dojscie`.
  Brak = bez `RETRONIC_POSTAC` skrypt czytał piętro innej postaci i PO CICHU pominął dojście → `./zatrzymaj.sh`, start ponownie.
- Pilnuj Monitorem w DWÓCH fazach (21.10: monitor na każde zabicie i „ucieka” zasypywał Karola powiadomieniami):
  1. **Dojście** (do pierwszego zabicia): log `Przejście pięter: zA -> zB w`, `NIEUDANE`, `Dojście zakończone`, `Cel … zabity`,
     `Zatrzymano`, `ALARM`, `PK`, `Koniec.` + pozycja i HP z `panel.py` co 5 s (zmiana piętra, spadek HP > 8 pp).
  2. **Na spocie** (po 1. zabiciu): tylko problemy postaci — `NIEUDANE|Zatrzymano|ALARM|Traceback|Ucieczka|PK |zgin|Koniec.`
     z `grep -v "Troll ucieka"` (ucieka POTWÓR, nie postać) + HP < 50%. Zabić nie zgłaszaj.
  Pętla monitora: każde polecenie z `|| true`, bez `set --` na wyniku (21.10 monitor padł z exit 1 w trakcie dojścia).
  „Dojście zakończone” bez zdarzenia `z8 -> z9` bywa poprawne: ostatni krok trasy wchodzi na schody (zejście bez prób,
  log `jestem przy końcu trasy (…, z9)`) — sprawdź piętro w `panel.py`, zanim uznasz, że nie zszedł.
- **HP w Monitorze** (`panel.py` co 5 s): spadek HP bez walki, gdy postać stoi = ogień → natychmiast `./zatrzymaj.sh`, zejście
  z pola jednym klawiszem do jej ekranu, poprawka trasy. Zagrożenie życia: tu wolno zatrzymać od razu.
- **Sukces** = `Przejście pięter: z7 -> z8 … (próba N, …)`, pozycja na z8 w składowej, potem `Cel … zabity`.
- **Porażka przejścia** (`NIEUDANE`, bot ponawia w kółko): `./zatrzymaj.sh`, przeczytaj `przejscia_pieter.py` dla tego pola,
  zastosuj regułę z kroku 2 (inne zejście / łopata / lina), wygeneruj ponownie, waliduj, start.
- **Postać na złym piętrze po porażce**: jeden klawisz do JEJ ekranu (nigdy domyślny `:1`):

      RETRONIC_ID=<id> python3 -I -c "import sys; sys.path.insert(0,'.'); import bot; print(bot.ekran_gry())"   # np. :5
      RETRONIC_ID=<id> python3 -I -c "import sys; sys.path.insert(0,'.'); import klawisz_x11 as k; k.wyslij('Right', None, ':5')"

  Kierunek z mapy (pole flagi 2 obok postaci na jej piętrze), potem `panel.py` potwierdza piętro.
- Po przejściu: 5–10 min obserwacji (zabicia, HP, brak wahadła), potem zostaw bota i zatrzymaj Monitor.

## 8. Zapis (zawsze, także po porażce)

- `STAN.md`: co powstało, wynik walidacji, przebieg testu z godzinami, co nie zadziałało i poprawka.
- Nowa reguła przejść → ten plik (krok 2) + `README.md` („Czego mapa NIE wie”); nowa zasada startu → `CLAUDE.md`.
- Zmiana kodu bota (np. `ZASYPANE`) → kopia `.bak-<data>-<tag>` i testy:
  `testy/test_pietra_kratka.py`, `test_pietra_zajete.py`, `test_wielopietrowa.py`, `test_symulator_pietra_zgodnosc.py`.
- Bez commita, chyba że Karol każe. Projekt prywatny: nic do Notion/Slacka.

## Przypadek wzorcowy: Thais północ, 21.10 (kutangen, lvl 9)

| Krok | Co | Wynik |
|---|---|---|
| 1 | `spoty_skladowe --miasto Thais` | z8 (32324,32134): 1000 pól, 14 trolli + szczury/pająki, `bot: -`; z9 osobno 16 trolli |
| 1 | życzenie Karola | „omijać poison spidery” → strefa 6 pól wokół (32326,32155,z8) (ślepy korytarz) |
| 3 | `generuj_trasy_thais_pn.py --zapisz` | pętla z8 334 pola, 8 przystanków, 33 potwory, 0 pól w strefie |
| 6 | start bez `RETRONIC_POSTAC` | dojście pominięte po cichu, bot utknął w depo → lekcja w `CLAUDE.md` |
| 2 | 1. zejście: żółte (32345,32146) | schody W GÓRĘ, postać na z6 → reguła 1, wykrywanie zejść w generatorze |
| 7 | ratunek z z6 | jeden `Right` do ekranu `:5` → z7 |
| 2 | 2. zejście (32347,32123), 23 pola od poison | stoi na polu, use bez skutku → reguła 2, `ZASYPANE` |
| 7 | start | łopata z pola obok, krok → z8 16:36:32, pierwsze zabicie 16:36:53 |

## Przypadek: Edron trolle z9 wschód, 21.10 (invincible lvl 12, kolanoth/Kolanosh lvl 8)

| Krok | Co | Wynik |
|---|---|---|
| 1 | składowe Edron | z9 wschód: osobna składowa 309 pól, 15 trolli; wejście z z8 |
| 2 | wejście z mapy: (33115,31744,z8) flaga 2 | **to OGIEŃ**: invincible stał na nim 17:14:20–51, HP 91% → 58% → reguła 6 (przeszkoda w kolorze podłogi) |
| 3 | poprawka | schody (33119,31740) kolor 210 + omijanie ognia `trasy/ogien_*.json` z buforem 1; 0 nowych punktów przy ogniu |
| 6 | kolanoth bez liny | 17:09 STOP na z11→z10 (33133,31805) — przejście w górę liną w nagranym `edron_depo_trolle` |
| 7 | kolanoth z liną, start z z9 | z11→z10 i z9→z8 liną (próba 2), dziura z7→z8, schody (33119,31740) krokiem 17:27:40, troll 17:27:58, 3 trolle w 30 s, HP 100% |
| 8 | powrót do depo (20:13, żądanie ręczne) | **brak wyjścia z z9w w planie „edron”** → stanie w (33121,31756,z9), ALARM/STOP 20:14; poprawka: lina (33119,31740,z9) ze stania (33119,31739), trasa `trolle_edron_z9w_do_depo`, test 100/100; na żywo NIESPRAWDZONE |

## Przypadek: Edron troll cave z9 zachód, 21.10 (Karol wskazał spot z nagrania `edron_nowy_spot`)

| Krok | Co | Wynik |
|---|---|---|
| 1 | składowe Edron (obszar 33040,31690,33150,31790, z8–z10) | z9 (33077,31728): 871 pól, 34 Troll + 5 Bear, osobna od `trolle_edron` (z8) i `trolle_edron_z9w`; `bot:` tylko nagranie |
| 2 | wejście | tylko z z8 składowej `trolle_edron`: schody 210 (33081,31742,z8) i (33071,31752,z8); dojście = `edron_depo_trolle` + 68 pól po z8 (też trolle) |
| 3 | `generuj_trasy_edron_z9z.py` | pętla 343 pola, 7 przystanków, 30 potworów; 9 trolli za ogniem i 8 na polach ognia odpadło |
| 5 | wpis `mapy.json` + `spoty_nadzorca.json` | jaskinia `edron_trolle_z9z`; testy `test_spoty` wymagają dopisania nowego spotu Edronu do list oczekiwanych |

Reguły z tego przebiegu (krok 3): (a) **`trasy/ogien_epizody.json` ma format `{"pola": {"x,y,z": {...}}}`** — czytaj klucze słownika `pola` (starsza `ogien_pola()` z `generuj_trasy_edron_wschod.py` czyta tylko listy i zgubiłaby epizody);
(b) droga A* dojścia musi dostać ogień w `zajete` (`m.droga(..., zajete=...)`): `spot_lib.przed_przejsciem` omija ścianę tylko przy wyborze pola obok przejścia, więc generator liczy dojście własnym `droga_z_omijaniem`;
(c) spawn na polu ognia albo za nim (bufor 1 odcina korytarz) wypada z pętli — zapisz go w opisie mapy (ile potworów odpadło i dlaczego), nie przesuwaj ognia;
(d) dojście przez składową innego spotu (tu: z8 `trolle_edron`) przechodzi przez jej potwory: ostrzeż w opisie, nie buduj obejścia, jeśli go nie ma.

## Czego jeszcze brakuje (następny krok, wymaga specu)

- Jeden ogólny generator (`generuj_spot.py --miasto --obszar --cel --zakazane --start`) zamiast pliku na spot.
- ~~Automatyczne wykrycie zasypanej dziury~~ — ZROBIONE 21.10 (F4: pamięć „lopata”, `PIETRA_LOPATA_AUTO`).
- Rozpoznanie przejścia z8 → z9 Thais północ (16 trolli na z9 bez dojścia).
