# Raport modelu lokalnego D2 (pościg) — krok B, przymiarka offline

Dane z telemetrii (tylko odczyt); opcje odtworzone z najbliższej wcześniejszej `probka` — przybliżenie.
Wejście: logi (pliki: 2, rekordów: 70393, złe linie: 0, od: początek)

## Zbiór

- poscig_start: 6138
- bez_konca: 0
- brak_probki: 0
- probka_za_stara: 0
- bez_celu_w_probce: 26
- powod_pominiety: 110
- uzyte: 6002
- etykieta_1: 5717
- etykieta_0: 285
- pominiete_powody: {'gryzacy': 82, 'cel_znikl': 22, 'hp_spadek': 4, 'oscylacja': 2}

Wiersze użyte: **6002**, sesji: 26. Odsetek etykiety 1: 0.953.

## Podział (po sesjach, nie losowo)

- trening: 4466 wierszy (odsetek 1: 0.951); z tego walidacja do doboru hiperparametrów (ostatnie sesje): 1731 wierszy
- test: 1536 wierszy (ostatnie sesje, odsetek 1: 0.957)

## Metryki na teście

| model | log-loss | AUC | trafność |
|---|---|---|---|
| baseline: stala_czestosc | 0.1777 | 0.5000 | 0.9570 |
| baseline: tylko_odleglosc | 0.1140 | 0.9033 | 0.9570 |
| regresja logistyczna {'l2': 1.0} | 0.1380 | 0.8310 | 0.9570 |
| MLP {'ukryte': [32, 32], 'l2': 10.0, 'epoki': 60} (wybrany) | 0.1078 | 0.9280 | 0.9622 |

Wybór zwycięzcy: najniższy log-loss na walidacji (nie na teście).

## Walidacja krzyżowa po sesjach (5 foldów, out-of-fold)

| model | log-loss | log-loss stałej | AUC | trafność | AUC per fold |
|---|---|---|---|---|---|
| lr | 0.1419 | 0.2007 | 0.8614 | 0.9505 | 0.831, 0.874, 0.901, 0.841, 0.848 |
| mlp | 0.1152 | 0.2007 | 0.9134 | 0.9513 | 0.953, 0.848, 0.940, 0.839, 0.903 |

## Ważność cech

| cecha | waga LR (po standaryzacji) | spadek AUC po przetasowaniu (mlp, test) |
|---|---|---|
| odl | -1.491 | 0.3741 |
| hp_celu | 1.786 | 0.0621 |
| inne_w2 | -0.518 | 0.0113 |
| odl_gracza | 0.178 | 0.0021 |
| osiag_tak | -0.137 | 0.0014 |
| osiag_nie | 0.000 | 0.0000 |

## Czas inferencji (1 próbka, CPU, numpy)

- wybrany (mlp): 0.0067 ms; lr: 0.0013 ms; mlp: 0.0066 ms (cel < 0,1 ms)

## Zastrzeżenia

- Etykieta znana tylko dla opcji, którą wybrał bot (selekcja); model uczy się „co się udaje po wyborze bota”.
- Cecha `droga` (długość A*) pominięta: w telemetrii 75% wartości to 0 także dla odległych celów — semantyka UNKNOWN.
- Etykiety 0 skupione: najwięcej w jednej sesji 152 z 285 (sesji z etykietą 0: 19) — sygnał może odzwierciedlać pojedyncze epizody.
- Mało sesji (26), test to ostatnie sesje: wynik zależy od podziału; patrz CV.
- Model trenowany na części treningowej; do wdrożenia wymaga ponownego treningu na całości i trybu cienia.
