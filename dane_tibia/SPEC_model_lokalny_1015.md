# SPEC: lokalny mały model do grania (15.10) — kroki A i B zrobione 15.10 (decyzja Karola: start, zbieranie danych na dwóch komputerach)

Cel: własny, bardzo lekki model, który podejmuje szybkie decyzje w skrypcie (ruch, cel, pościg, wyjście z utknięcia,
runy). Haiku zostaje do rozmów i ogólnej oceny sytuacji (decyzja Karola 15.10). Model nie zastępuje kodu
bezpieczeństwa: ogień, HP, ucieczka, GM zostają w kodzie.

## 1. Skąd pomysł (źródła)

| Co | Fakty | Źródło |
|---|---|---|
| **Jev** (typesafe.ai) | model "System One": zwraca typowaną decyzję z prawdopodobieństwami (Choice, Noul = tak/nie, Score), nie tekst; tylko chmura; $0,042 / 1M tokenów wejścia, wyjście darmowe; kontekst 64k; nie liczy wiarygodnie (liczby liczy kod) | docs.typesafe.ai/models, /model-jaggedness/jev-1.13 |
| **Drex 2.0** (nace.ai) | ta sama idea, "szybszy niż Jev"; 35B MoE (3B aktywnych), otwarte wagi ~37 GB Q8 GGUF (Ollama/llama.cpp) — nie mieści się na tym komputerze (8 GB VRAM, 31 GB RAM, ~13 GB wolne przy grze) | nace.ai/drex |
| **Laya** | aplikacja (agregator powiadomień na lokalnych LLM), nie model | github.com/aayushch/laya |
| Test Marcina: Jev, Snake | śr. decyzja **272 ms**, 935 ruchów, 44 pkt; kod liczy fakty dla każdego ruchu (ściana/ogon/odległość do jabłka), Jev tylko wybiera, kod nic nie poprawia | Slack DM 15.10 15:08 (zrzut) |
| Test Marcina: Laya lokalnie | ~**0,8 s** na ruch i ruch w ścianę; "jednak na moim kompie jev lepiej wygląda" | Slack DM 15.10 15:39, 15:46 |

Wniosek: wzorzec "kod liczy fakty dla każdej opcji -> model wybiera opcję z prawdopodobieństwem" działa. Zamiast LLM
(lokalnie za wolny i za słaby, w chmurze zależny od sieci) robimy **własny mały model liczbowy** w tym wzorcu.

## 2. Dzisiejsze decyzje bota (punkt odniesienia, 15.10 12:00–16:00)

- Haiku: 274 decyzje, 96% "kontynuuj", mediana 11,6 s, p90 17,7 s, max 46 s; obserwator/analityk pościgu: 181 błędów
  modelu (timeout 60 s).
- Ruch i walka: kod w pętli co 50–300 ms. Problemy dnia, które są decyzjami: kieszeń przy ogniu (162 s zastoju, cel =
  schody), troll "za ścianą" porzucony (inne trolle jako przeszkody), pościg w dziurę (16:09:53) i 4 min w kieszeni z9,
  loot Ctrl+klikiem na schodach (zmiana piętra).

## 3. Model

- **Typ:** najpierw regresja logistyczna, potem mała sieć (2 warstwy po 32) albo drzewa; **sam numpy** (jest:
  numpy 2.5.2; sklearn/lightgbm nie ma i nie są potrzebne). Wagi w JSON w repo (< 100 KB).
- **Czas:** < 0,1 ms na decyzję na CPU, bez GPU (karta zostaje dla gry).
- **Wejście:** opcje przygotowane przez kod, każda z cechami (fakty liczone dziś w cavebot).
- **Wyjście:** dla każdej opcji przewidywany wynik (np. P(zabity w 15 s), oczekiwany czas, P(utknięcie)); bot bierze
  najlepszą. Pewność = margines między najlepszą a drugą opcją.
- **Bezpieczeństwo:** kod podaje tylko opcje dopuszczalne (bez ognia, bez dziury, HP ok); poniżej progu pewności albo
  bez modelu = dzisiejsza reguła. Model nigdy nie decyduje o ucieczce, leczeniu, ogniu.

## 4. Decyzje (kolejność) i cechy

| # | Decyzja | Opcje | Cechy (przykład) | Wynik do nauki | Dane dziś |
|---|---|---|---|---|---|
| D1 | wybór celu | widoczne moby-cele | odl. prosta, długość A*, HP celu, ucieka?, trolle wokół celu, gracz przy celu, ogień/dziura/schody przy celu, czy gryzie nas | zabity / zgubiony / porzucony, czas do zabicia, HP stracone | 2 087 epizodów: 1 814 zabity, 155 zgubiony, 118 porzucony |
| D2 | pościg: gonić / odpuścić / czekać | 3 | odl., HP celu, droga A* (ze skosami i bez), moby na drodze, dziura/schody na drodze, czas pościgu | zabity, kroki, "brak_ruchu"/"zawracanie" | 5 887 pościgów: 5 149 dojście, 528 cel martwy, 141 brak ruchu, 114 zawracanie |
| D3 | wyjście z utknięcia / brak drogi | krok skosem, cofnij, inny punkt, przejście piętra, czekaj | pola wokół (ściana/ogień/schody/mob), znane przejścia pięter, czas utknięcia | czas do ruszenia, HP stracone | 113 utknięć (mało: etykiety z Haiku/Jev offline) |
| D4 | miejsce patrolu | miejsca z miejsca_troll.json | dojście (s), ostatnia wizyta, zabicia historyczne, gracze | zabicia na wizytę, czas dojścia | 565 wizyt: tylko 21 z zabiciem na miejscu |
| D5 | runa teraz / później | 2 | mana, HP, moby w widoku i odl., walka | zabicia/HP po decyzji | 43 runy (za mało na start) |

Start: **D1 + D2** (najwięcej danych, jasny wynik).

## 5. Dane: luka i jak ją zamknąć

- **Luka:** telemetria zapisuje tylko wybrany cel i jego wynik (`nowy_cel`, `epizod_celu`), nie zapisuje innych opcji
  z chwili wyboru. Model wyboru potrzebuje całego zbioru opcji z cechami.
- **Krok A (bez zmiany zachowania):** rekord `decyzja` w telemetrii: `{id, rodzaj, opcje: [{cechy...}], wybrana}`,
  a wynik dopisywany po id (`epizod_celu`, `poscig_koniec`, `utkniecie`). Pokrętło `DECYZJE_LOG`.
- **Krok B:** przymiarka na starych danych: opcje odtworzone z najbliższej `probka` (stwory z dx/dy/hp co ~1–5 s) —
  przybliżenie, tylko do oceny, czy wynik da się przewidzieć.
- **Etykiety bez danych:** tam gdzie mało przykładów (D3), jednorazowe oznaczenie sytuacji z logów przez Haiku albo Jev
  (nauczyciel offline); w grze działa tylko nasz model.
- **Ręczne przejęcia Karola** (`obserwator_reczny.py` -> `logi/pomoc-karola.jsonl`) jako etykiety o największej wadze.
  UNKNOWN: plik dziś nie istnieje na tym komputerze (obserwator nie był uruchomiony).
- **Problem "bandyty":** wynik znamy tylko dla wybranej opcji. Model przewiduje wynik opcji (nie "co wybrał bot"), plus
  mały odsetek eksploracji w trybie cienia albo etykiety nauczyciela, żeby nie kopiować tylko dzisiejszych reguł.

## 6. Trening i ocena

- `python3 trenuj.py D1 [--od RRRRMMDD]`: czyta telemetrię, buduje zbiór, dzieli po sesjach (nie losowo), uczy,
  zapisuje `model/D1.json` + raport (trafność, kalibracja, ważność cech).
- Ocena offline: na odłożonych sesjach — czy model przewiduje wynik lepiej niż reguła (log-loss, trafność wyboru
  "szybko zabity").
- **Tryb cienia:** model działa obok reguły i tylko zapisuje swój wybór; porównanie wyników tam, gdzie wybrałby inaczej.
- **Włączenie:** pokrętło `MODEL_D1=1`, `MODEL_PROG` (próg pewności); miary: exp/h (dziś ~2 450), porzucone cele/h,
  czas pościgu, czas utknięć. Cofnięcie = pokrętło 0.
- Ponowne uczenie co kilka dni na nowych danych (ręcznie, skrypt).

## 7. Plan (bramki)

1. Ta specyfikacja: akcept Karola (Q1–Q4).
2. Krok A: logowanie decyzji D1+D2 (bez zmiany zachowania), testy, restart.
3. Krok B: przymiarka na starych danych + raport (czy jest sygnał).
4. 2–3 dni zbierania, pierwszy model D1, tryb cienia.
5. Włączenie D1 przy wysokiej pewności, pomiar; potem D2, D3 (z nauczycielem), D4, D5.

## 8. Pytania do Karola

- Q1 Start od D1+D2 (wybór celu, pościg)? Alternatywa: D3 (utknięcia) od razu z etykietami Haiku/Jev.
- Q2 Nauczyciel offline do etykiet: Haiku (subskrypcja, wolniej) czy Jev przez API (klucz, ~$0,00006 / sytuację)?
- Q3 Uruchamiać `obserwator_reczny` w trakcie gry, żeby zbierać Twoje przejęcia jako etykiety?
- Q4 Eksploracja w trybie cienia (czasem wybór innej opcji niż reguła, tylko gdy bezpieczna): tak/nie?

## 9. Wynik kroków A i B (15.10, workflow wf_842110b1-7c1, checker NITS x2)

- Krok A: rekord `decyzja` (D1 wybór celu, D2 start pościgu) z opcjami i cechami, `decyzja_id` w `nowy_cel`,
  `epizod_celu`, `poscig_start`, `poscig_koniec`; pokrętło `DECYZJE_LOG` (domyślnie 1); bez A* i zapytań do gry.
  `nowy_cel` powstaje w telemetria.py z linii logu, stąd zmiana także tam. D2 ma na razie jedną opcję ("gonic"):
  "odpuść/czekaj" nie są decyzjami w kodzie. D1: droga = null (cavebot nie liczy A* przy wyborze celu).
- Krok B: `model_lokalny/` (zbior, model numpy LR/MLP, trenuj), testy 44/44, inferencja 0,0065 ms, wagi 16–36 KB.
  D1: brak sygnału (CV AUC ~0,54; bot bierze najbliższego w 94%). D2: AUC ~0,93, ale sama odległość daje ~0,90
  (odl 2: 99% udanych). Wniosek: potrzebne dane z kroku A i decyzje, gdzie są realne straty (utknięcia, D3).
- Poprawki po recenzji: agregacja CV bez TypeError przy foldzie bez >=2 kandydatów; `cel_znikl` nie jest porażką
  pościgu (pomijany); test 7b sprawdza wartość pokrętła, nie tekst źródła.
