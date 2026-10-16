# SPEC: test gotowych modeli decyzyjnych (typu Jev) pod bota — 16.10

Status: SZKIC do uruchomienia po spotkaniu (Karol: "po spotkaniu odpalę jakieś testy"). Nic nie wgrane, bot bez zmian.
Źródło: zrzut Marcina "15 alternatives to Jev" (16.10), wpis w Notion Tech News (tylko zrzut, bez analizy tego bota).
Powiązane: `SPEC_model_D3_utkniecia_1015.md` (krok B, Q2), `SPEC_model_lokalny_1015.md`, `STAN.md` -> "Następna sesja" pkt 5.

## 1. Czym jest Jev i po co nam to

Model decyzyjny: dostaje pytanie + listę dozwolonych odpowiedzi, zwraca prawdopodobieństwa jednym przejściem (bez generowania
tekstu, bez parsowania). Pasuje do bramek "która opcja z listy". Dla nas: D3 (wyjście z utknięcia), czaszka ze zrzutu,
ewentualnie wiadomości na czacie. Nie pasuje do czystych liczb/cech (D1, D2, D4): tam nasz numpy robi to w 0,007 ms,
a D1 ma AUC 0,51 z braku sygnału w danych, nie z braku rozmiaru modelu.

## 2. Sprzęt i co się zmieści [POTW 16.10]

RTX 3060 Ti 8 GB (zajęte 4,4 GB przy sprawdzaniu; bot i gra wyłączone, więc do ponownego pomiaru), RAM 31 GB, 20 rdzeni.
Realnie 2-3 GB VRAM wolne obok gry. Nie ma jeszcze pip-owych paczek (torch/transformers/llama.cpp/systemone) ani cache HF.

| Model | Licencja / rozmiar | Lokalnie na tym sprzęcie | Źródło |
|---|---|---|---|
| Mapika Decider 0.8B | Apache-2.0, baza Qwen3.5-0.8B | GPU, swobodnie | systemonemodels.ai/mapika/decider |
| Mapika Decider 2B (v11, 1,9B, 32k) | Apache-2.0, GGUF Q8 (99,16% zgodności z bf16) | GPU 4-8 bit albo CPU; Q8 ok. 2 GB = ciasno | j.w. |
| Mapika Decider 2B-vision | Apache-2.0 | j.w., kandydat do czaszki | j.w. (wariant wymieniony na stronie) |
| Mapika Decider 4B (v2.1, 4,2B) | Apache-2.0, GGUF Q8 | tylko CPU (ok. 4,5 GB); test offline, nie na żywo | j.w. |
| Strands Decider 2B (AWS, 01.10) | Apache-2.0, 1,9B, Qwen3.5-2B-Base + LoRA r16 + pointer head, ok. 115 ms | bf16 ok. 4 GB nie zmieści się; po kwantyzacji tak; GGUF [NIEZWERYFIKOWANE] | strandsagents.com/blog/introducing-strands-decider |
| Laya (Convai, 421M; wielojęzyczna 322M) | Apache-2.0, ok. 35 ms na T4 | GPU/CPU, trywialnie; zero-shot ledwo > losowość, wymaga fine-tuningu i kalibracji | dev.to/vishalmysore (Laya vs Jev) |
| Open-Jev 27B | CC BY-NC 4.0, ok. 16,5 GB nawet w GGUF | NIE (rozmiar) | huggingface.co/openjev/openjev |

Nie sprawdzone (są na zrzucie, brak źródeł): Standard One 3B/8B, Kev-4B, GLiNER2.5-Decide, Clef, d1, Tev1-4B, Bespoke-Nimble-9B, Von.

Własne wyniki autora Mapiki (nie niezależne): 2B 75,2%, 4B 78,4%, 35B-A3B 81,0%; JevBench trudny: 57,7 / 64,9 / 67,6%.
Jev API ok. 0,042 USD/mln tokenów, 236-276 ms; Open-Jev 84% na 10 tys. pytań tekstowych (H100).

## 3. Ryzyka (z literatury)

- arXiv 2609.26758 "Type-Safe Is Not Error-Free": głowa decyzyjna idzie za NAZWĄ opcji, nie za regułą do niej dopisaną.
  -> nazwy opcji D3 muszą być jednoznaczne i opisowe (`krok_skos` OK, `opcja_a` nie); test z permutacją kolejności i nazw.
- Laya: kalibracja progu pewności (temperatura) obowiązkowa na własnych danych.
- Duża liczba etykiet (Banking77: Laya 0,425 vs Jev 0,870) -> u nas 6 opcji D3, więc mało groźne.

## 4. Decyzja o własnym modelu

Nie trenujemy własnego od zera pod ten case teraz: 54 epizody D3, 1 prawdziwy atak PvP, 19 decyzji D4 = za mało.
Najpierw etykiety i pomiar zero-shot; dotrenowanie (Mapika 0.8B albo Laya) dopiero przy kilkuset przypadkach i sygnale.
Kolejność: etykiety Haiku (krok B D3) -> zero-shot gotowych -> porównanie z regułą i z numpy -> decyzja.

## 5. Plan testu (offline, bot bez zmian)

Wejście: 54 epizody zawieszek (z 70 h telemetrii, `model_lokalny/zbierz_dane.py`) + 62 przejęcia Karola (`pomoc-karola.jsonl`,
waga x5) + etykiety nauczyciela Haiku (do zrobienia: ~54 wywołań). Opis sytuacji jak w SPEC D3 sekcja 3.

1. Pomiar VRAM przy wyłączonej i włączonej grze (`nvidia-smi`).
2. Środowisko poza repo bota (nie wersjonować wag/venv): osobny venv, `pip install systemonemodels` (+ `systemone pull mapika/decider`),
   dla Strands wg ich README. Wagi poza gitem.
3. Etykiety Haiku dla 54 epizodów (+ nadpisanie przejęciami Karola) -> `dane_tibia/d3_etykiety.jsonl` (jeśli zawiera pozycje graczy, nie wypychać).
4. Skrypt porównujący: dla każdego epizodu i każdego modelu {Mapika 0.8B, 2B, 4B(CPU), Strands 2B} wybrana opcja + P + czas.
5. Metryki: zgodność z etykietą (top-1), czy wybrana opcja faktycznie ruszyła postać w danych (jak w SPEC D3 krok B),
   odporność na permutację kolejności/nazw opcji, czas i VRAM, kalibracja (czy P > próg = trafienie).
6. Punkty odniesienia: dzisiejsza reguła oraz własny numpy z `model_lokalny/trenuj.py`.
7. Drugi test (osobny): czaszka. Zrzuty z `czaszka.py` (Haiku jako wzorzec) vs Mapika 2B-vision; najpierw sprawdzić rozdzielczość i szum zrzutu.

## 6. Kryteria decyzji

- Model wchodzi do trybu cienia (krok C D3) tylko jeśli trafia opcję, która ruszyła postać, lepiej niż reguła, na danych,
  których nie widział, i mieści się obok gry (VRAM) w czasie < 200 ms.
- Brak przewagi nad regułą/numpy = kończymy bez kosztu, wnioski do `STAN.md`.
- Bezpieczeństwo bez zmian: model nigdy nie decyduje o ogniu, ucieczce, leczeniu (SPEC_model_lokalny).

## 7. Otwarte

- Strands Decider 2B: czy jest GGUF/kwantyzacja do 8 GB karty [NIEZWERYFIKOWANE].
- Co zajmuje 4,4 GB VRAM przy wyłączonym bocie (pomiar kroku 1).
- Licencja Open-Jev CC BY-NC: istotna tylko jeśli kiedyś komercyjnie; dziś nie używamy.
- Decyzja Karola: robi test sam (komendy z pkt 5.2), czy agent pisze skrypt porównujący (pkt 5.4).

## 8. Wyniki prób (16.10 ~11:45-12:15) [POTW]

Środowisko: `~/Games/Retronic/modele-test/` (poza repo bota; `.venv` py3.12, `modele/`, `skrypty/smoke.py`). Wagi i venv nie wchodzą do gita.
Gra i sesja bota chodziły (od 08:12), voxtype zajmował 1,5 GB VRAM, więc testy tylko na CPU (`CUDA_VISIBLE_DEVICES=""`, `nice -n 19`, 6 wątków).

- `systemone pull mapika/decider` działa bez logowania (v11: 5,8 GB, safetensors + GGUF Q8 2,0 GB). Runtime: `pip install decider-ai` (1.9.0),
  torch w wersji CPU z `download.pytorch.org/whl/cpu` (domyślny ciągnie CUDA).
- Mapika Decider 2B v11 (bf16, CPU): ładowanie 1,9 s; jedna decyzja D3 (6 opcji, syntetyczny opis zawieszki) 1,5-2,3 s.
  Ostrzeżenie: brak `causal_conv1d`/kerneli fla na CPU = wolna ścieżka referencyjna; dokumentacja Mapiki podaje 0,12-0,31 s dla Q4_K_M GGUF przez llama.cpp na 8 wątkach.
- Jakość na tym jednym syntetycznym przykładzie: rozkład płaski (0,28 / 0,24 / 0,22 / 0,22 / 0,03 / 0,01), top-1 `krok_skos` z P=0,28. To NIE jest pomiar,
  tylko dowód, że model chodzi i zwraca poprawny format. Prawdziwy pomiar wymaga etykiet (pkt 5.3).
- Do zrobienia: GGUF przez llama.cpp (`pip install decider-ai[gguf]`), Mapika 0.8B i 4B, Strands 2B, etykiety Haiku dla 54 zawieszek.

### 8b. GGUF Q8 na CPU (16.10 ~12:30) [POTW]

`llama-cpp-python` 0.3.36 zbudowany w venv; `skrypty/smoke_gguf.py`, Mapika 2B v11 Q8_0, n_ctx 4096, `nice -n 19`, gra i bot chodzą obok.
- 4 wątki: 1,56-2,03 s na decyzję (mediana ok. 1,65 s); 8 wątków: 2,28-2,40 s (gorzej: rywalizacja o rdzenie z grą/swayem).
- Cel: ok. 330 ms (Jev przez API ok. 3 decyzje/s, test Marcina 272 ms). CPU Q8 jest 5x za wolne. Q4_K_M (1,3 GB) nie testowany;
  autorzy podają 0,12-0,31 s na 8 wątkach serwerowego CPU, u nas realnie spodziewane ok. 2x szybciej niż Q8, nie 6x [HIP].
- Wniosek roboczy: do 2-3 decyzji/s potrzebny GPU (Q8 ok. 2 GB, wolne ok. 5,7 GB przy grze) albo wykorzystanie tylko do rzadkich decyzji (D3, czaszka).

### 8c. GPU (RTX 3060 Ti), Mapika 2B v11 bf16 (16.10 ~12:00) [POTW]

Zgoda Karola ("cały czas na gpu testujemy"). Osobny venv `.venv-gpu` (torch 2.14.1+cu130, sterownik 610.57 / CUDA 13.3; bez `nvcc`, więc bez llama.cpp CUDA — silnik torch).
Skrypty: `skrypty/smoke_gpu.py`, `skrypty/gpu_dlugi.py`. Gra i bot chodziły obok; baza VRAM 2,5 GB, po teście zwolniona.
- Krótki stan (ok. 120 tokenów, 6 opcji): mediana 33 ms (min 32, p90 34, max 35), szczyt VRAM 3,87 GB. Ładowanie 6,9 s.
- Stan z mapą 15x11: 244 tokeny 46 ms, 430 tokenów 65 ms, 709 tokenów 93 ms (mediany z 15 prób).
- Cel ok. 330 ms (3 decyzje/s): spełniony z zapasem ok. 3,5x przy najdłuższym stanie. Wynik na przykładzie ten sam co na CPU (krok_skos, P=0,28).
- Zastrzeżenie: czasy zmierzone przy małym obciążeniu GPU przez grę (klient ok. 100 MB); pod pełnym renderem gry mogą być wyższe, do zmierzenia w trakcie sesji. Jakość decyzji dalej niezmierzona (brak etykiet).

### 8d. Jakość zero-shot na 54 zawieszkach (16.10 ~13:00) [POTW]

Dane: `modele-test/dane/` (epizody.jsonl = 107 epizodów z 11-16.10 wg definicji ze speca D3, ekstraktor `skrypty/epizody.py`; 97 bez zamierzonych;
próbka 54 warstwowo po czasie trwania, tylko z `po` znanym; etykiety Haiku `etykiety_haiku.jsonl`: 54/54 bez błędów, ok. 0,89 USD orientacyjnie).
Spec miał 54 epizody/162 min z krótszego okna i innej metody; mój ekstraktor daje 104 do 15.10 (269 min). Różnica NIEWYJAŚNIONA.

| Model | Zgodność top-1 z Haiku | Stabilność przy permutacji opcji | Śr. pewność | Pewność >= 0,5 | Czas (mediana, GPU) | VRAM |
|---|---|---|---|---|---|---|
| Mapika Decider 2B v11 | 0,46 | 0,22 | 0,27 | 0 przypadków | 68 ms | 3,9 GB |
| Strands Decider 2B (hobson-v19) | 0,39 | 0,30 | 0,31 | 0 przypadków | 129 ms | 3,7 GB |
| punkt odniesienia: zawsze `inny_punkt` | 0,61 | - | - | - | - | - |
| punkt odniesienia: losowo (6 opcji) | 0,17 | - | - | - | - | - |

Rozkład etykiet Haiku: inny_punkt 33, alarm 10, cofnij 5, krok_skos 3, przejscie_pietra 2, czekaj 1.

WNIOSEK: oba modele zero-shot NIE biją zgadywania klasy większościowej, są niestabilne przy zmianie kolejności opcji i nigdy nie są pewne.
Do sterowania D3 w obecnej postaci się nie nadają. Powody (część [HIP]):
- opis sytuacji ubogi: w 44 z 54 epizodów telemetria historyczna nie ma pola `cel`; brak A*, kierunku do celu, flag pól (to ma dopiero rekord D3 na żywo);
- nauczyciel słaby: Haiku trafia przejście pięter w 1 z 9 przypadków (proxy "co faktycznie się stało": 9 z dz != 0, 2 z odl > 10, 43 ruch lokalny);
  etykieta skośna (61% jedna klasa) nie jest standardem złotym; złote etykiety to przejęcia Karola (`pomoc-karola.jsonl`, 62 rekordy);
- zadanie abstrakcyjne (6 akcji o krótkich opisach) a modele są trenowane na pytaniach z tekstem; zero-shot bywa blisko losowości (tak ostrzegała też Laya).
Pomiar NIE rozstrzyga, czy dotrenowany model by działał: rozstrzyga tylko, że gotowy zero-shot nie jest rozwiązaniem.
Czas nie jest problemem (68-129 ms << 330 ms).
