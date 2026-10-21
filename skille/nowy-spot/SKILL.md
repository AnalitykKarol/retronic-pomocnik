---
name: nowy-spot
description: Use when Karol wants a new Retronic hunting spot or route built and tested end to end by AI — "nowy spot", "zrób trasę na X", "znajdź spot dla <postać>", "wyślij <postać> na <miejsce>", "jakie spoty możemy obstawić", "dojście na <spot>". Picks the spot from the client map and CipSoft spawns (map components, not distance), generates loop + approach from the town depot with forbidden zones (e.g. poison spiders), validates offline, adds the mapy.json entry, then starts the chosen bot and watches it live through the floor change until the first kill. Starting a bot needs Karol's "puszczaj"; nothing goes to Notion or Slack.
---

# Nowy spot Retronic: od mapy do bota na żywo

Projekt prywatny Karola: nic do Notion ani Slacka, nie pytaj o zapis. Kod i stan: `~/Games/Retronic/pomocnik/`.
**Pełna procedura z poleceniami i przypadkiem wzorcowym: `dane_tibia/mapy/PROCEDURA_nowy_spot.md` — przeczytaj ją całą przed krokiem 1.**
Zasady bota (start, naprawy, życie postaci): `CLAUDE.md` repo. Metoda map i jej granice: `dane_tibia/mapy/README.md`.

## Przebieg (skrót procedury)

1. **Kontekst**: kto gdzie stoi i jaki ma poziom (`nadzor_stan.py`, `panel.py --json`), zajęte spoty (`tryb.log`).
   Życzenia Karola co do zagrożeń = strefy zakazane w generatorze.
2. **Wybór spotu**: `narzedzia/spoty_skladowe.py --miasto <M> --max-cios <wg lvl>`. **Spot wybiera Karol** (decyzja 21.10): pokaż 3–6 kandydatów w tabeli
   (składowa, potwory, sufit, odległość, `bot:`) i czekaj na jego wybór. Gdy Karol już wskazał miejsce — od razu dalej.
3. **Przejścia**: `narzedzia/przejscia_pieter.py --obszar … --pietra …`; kierunek W GÓRĘ/W DÓŁ wg reguł procedury
   (żółte 210 bywa w górę; stoi i nie spada = łopata → `pietra.ZASYPANE`).
   **OGIEŃ (21.10, invincible HP 91% → 58% w 30 s):** flaga 2 = „autowalk nie idzie”, ma ją też ogień. Pole flagi 2 w kolorze
   podłogi (nie 210) **poza z7** to PRZESZKODA, nigdy zejście (narzędzie pisze `PRZESZKODA`, `spot_lib.zejscia` je odrzuca).
   Prawdziwe schody/drabiny = kolor 210; zasypane dziury (kolor trawy) tylko na z7. Znany ogień (`trasy/ogien_stale.json`,
   `trasy/ogien_epizody.json`) + 1 pole bufora = ściana dla A* pętli i dojścia (wzór `generuj_trasy_edron_wschod.ogien_pola`).
4. **Generator**: nowy `generuj_trasy_<spot>.py` na wzór `generuj_trasy_thais_pn.py` (strefa zakazana, wykrywanie zejść,
   dojście z depo AŻ do pętli). Najpierw bez `--zapisz`, potem `--zapisz`.
5. **Walidacja offline**: `waliduj_trase.py` pętli i dojścia, `tryb.py --mapa … --sucho`, obejrzyj PNG (Read).
   Plus kontrola ognia: żaden NOWY punkt trasy na polu ognia ani obok (bufor 1) — wynik w raporcie.
   Wpis `mapy.json` z kopią `.bak-<data>-<tag>`; porównaj z kopią — zmienione tylko Twoje klucze.
6. **Zgoda**: pokaż Karolowi podgląd (ścieżki PNG, liczby) i komendę startu; postać, którą wyśle. Start dopiero po
   „puszczaj”/„tak” w tej sesji (postać z `STOP_RECZNY` = Karol gra; nie zabieraj postaci z expienia bez zgody).
7. **Start i test na żywo**: przygotowanie postaci (z7, `wyprawa_stan.json`, łopata/lina), potem
   `RETRONIC_ID=<id> RETRONIC_POSTAC=<nick> MAPA=<spot> TRYB=<dotychczasowy> ./uruchom.sh`.
   Dowód: `+ dojście` i `Dojście: trasa …` w logu. Monitor na log + pozycję **+ HP** do pierwszego `Cel … zabity` na spocie.
   **HP spada, gdy postać stoi w miejscu bez walki (np. na polu przejścia) = ogień → natychmiast `./zatrzymaj.sh`** i odejście
   z pola (zagrożenie życia — wyjątek od „naprawiaj, nie zatrzymuj”), potem poprawka trasy.
   Porażka przejścia → zatrzymaj, reguła z procedury, popraw generator, waliduj, start ponownie (ratunek z piętra:
   jeden klawisz do ekranu postaci z `bot.ekran_gry()`, nigdy `:1` w ciemno).
8. **Zapis**: `STAN.md` (przebieg z godzinami), nowe reguły do procedury/README/`CLAUDE.md`, kopie i testy pięter przy
   zmianie kodu. Raport dla Karola: co działa (z dowodem), co zostało otwarte. Bez commita, chyba że każe.

## Granice

- Zmiana pokręteł zwiększających ryzyko śmierci (ogień, próg ucieczki, PK, HP) — tylko po wprost zadanym pytaniu i „tak”.
- Nie restartuj innych botów ani wszystkich naraz; pracujesz na jednej, wskazanej postaci.
- Zatrzymaj Monitory i procesy, które uruchomiłeś, zanim zdasz raport (bot postaci zostaje na spocie).
