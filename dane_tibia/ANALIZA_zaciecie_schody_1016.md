# Analiza: zacięcie przy schodach (32498,32270,z8), 16.10.2026 14:51–14:53

Status: **ZAPISANA ANALIZA, NIC NIE NAPRAWIONE** (decyzja Karola 16.10: zapis na później, w repo trwają duże zmiany kodu).
Kod ani dane bota nie były ruszane. Skrypty odtwarzające: `dane_tibia/repro/` (atrapy, bez gry; uruchamiać z katalogu pomocnika).

## Objaw
Mastafian (trolle_patrol, tryb uh) stał 146 s (14:51:10–14:53:38) na (32497,32270,z8) obok schodów w dół (32498,32270).
Telemetria: pozycje na przemian (32497,32270) i (32497,32271) co 2–3 s, `ruch_okno`: 11–14 strzałek/30 s, w logu cisza
(tylko D3 „zawieszka 33 s” po 33 s, bez skutku). Cel patrolu: m2 (32491,32294) „przez schody_32498_32270:w_dol”.
Naprawa doraźna: jeden ręczny krok w prawo na schody 14:53:38 (bot poszedł dalej sam). Bota nie zatrzymywano.

## Mechanizm (odtworzony na atrapie)
1. Patrol celuje kilka punktów do przodu: `krok_do(cel=(32499,32270))`. Kierunek „w prawo” = pole schodów
   (32498,32270): zakazane „przy okazji” (`pole_zmiany_pietra`), więc odpada.
2. „W górę” (32497,32269) to pole, z którego postać dopiero przyszła (`KROK_WSTECZ_S` = 5 s), więc `krok_do` próbuje je
   na końcu. Zostaje „w dół” → kieszeń (32497,32271).
3. Z kieszeni wyjście na wschód (32498,32271,z8) jest zamknięte: pole siedzi w `trasy/dziury_nauczone.json` jako
   FAŁSZYWA nauczona dziura (wczytana o 12:59 z pliku; `pole_zmiany_pietra` = True, w `_zakaz_pol` jej nie ma).
   To pole lądowania po zejściu ze schodów (zwykła podłoga z8). Zostaje tylko „w górę”.
4. Pętla S–N–S–N trwa wtedy, gdy krok „w górę” (32497,32269) się nie udaje. Atrapa z wolnym polem północnym wychodzi
   po jednym odbiciu, z zablokowanym powtarza dokładnie objaw z gry (skrypt `..._polnoc_zablokowana.py`).

## Czego NIE wiemy (UNKNOWN)
Dlaczego krok „w górę” na (32497,32269) nie wychodził w grze, choć 10 s wcześniej postać tam stała. Brak potworów i
graczy w telemetrii. Hipotezy (niezweryfikowane): niewidoczny obiekt na polu; opóźnienie kroku uznane za ścianę
(`KROK_SCIANA` 0,45 s). To trzecie zacięcie w tej okolicy (wcześniej dwa przy drabinie 32497,32267, bez tego mechanizmu).

## Planowane naprawy (do zrobienia po ustabilizowaniu kodu; zmiana 1 działa dopiero po restarcie bota)
1. Usunąć `[32498,32271,8]` z `trasy/dziury_nauczone.json`; sprawdzić pozostałe wpisy (32508,32273,8), (33081,31742,8)
   i nowy (32482,32296,8) z 13:55:35 pod kątem tego samego błędu (pole obok schodów).
2. Reguła uczenia dziur (`wpadniecie.py`): nie zapisywać pola lądowania, gdy w pobliżu jest schody z mapy
   (wejście „przy okazji” na schody w marszu to nie dziura). Test regresji.
3. Wykrywanie oscylacji: powrót na te same 2–3 pola > 10 s ⇒ patrol przechodzi na drogę z A*, nie na krok „prosto do
   punktu przed nami”; punkt celowania nie może leżeć za polem zakazanym.
4. Zdarzenie `zawieszka` po 10 s + rozmowa Haiku: `SPEC_model_steruje_gra_1016.md` sekcja 8 (ta zawieszka by ją złapała).

## Dowody
- Log: `logi/mozg-20261016-1259.log` 14:51:07–14:53:38 (Wpadłem ×2 o 14:51:07/08, patrol m3→m2, D3 14:51:42).
- Telemetria: `logi/telemetria-20261016.jsonl`, decyzja D3 id 975 (`wokol`: północ „.”, schody „s”, południe „g”).
- Wczytanie dziur: log 12:59:22 „wczytano 3 nauczonych dziur ([(32498, 32271, 8), …])”.

## Dopisek 15:25 — drugie zacięcie tego samego typu (schody_32482_32296:w_dol)
- 15:24:38–15:25:50 postać stała 70+ s w (32487,32293,z8), stan IDZ, zero ruchu, w logu tylko `[OGIEN] pola` i
  „utknięcie, wracam na trasę do punktu 0”. D3 (rekord 1215): `cel` = (32488,32299,z9), `kier_cel` [1,1] (ten sam wzorzec:
  celowanie w punkt na innym piętrze), przejście `schody_32482_32296:w_dol` możliwe (wej 32482,32295, droga 7).
- Naprawa doraźna: 3 kroki w lewo po drodze z mapy bota (Left×3), potem bot sam zszedł schodami (15:25:54), bez zatrzymywania.
- Związek: pole schodów (32482,32296,z8) jest w `dziury_nauczone.json` od 13:55:35 („nauczona dziura … od teraz ściana
  dla dróg A*”), czyli znów schody zapisane jako dziura. Dwa zacięcia w 35 min przy schodach, które mają wpis w nauczonych
  dziurach ⇒ mocna hipoteza (niezweryfikowana): nauczone „dziury” na schodach są wspólną przyczyną. Do sprawdzenia przy
  naprawie 1–2: czy WSZYSTKIE 4 wpisy to schody/pola obok schodów.
