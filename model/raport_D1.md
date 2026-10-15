# Raport modelu lokalnego D1 (wybór celu) — krok B, przymiarka offline

Dane z telemetrii (tylko odczyt); opcje odtworzone z najbliższej wcześniejszej `probka` — przybliżenie.
Wejście: logi (pliki: 2, rekordów: 70410, złe linie: 0, od: początek)

## Zbiór

- nowy_cel: 2135
- brak_probki: 0
- probka_za_stara: 17
- brak_kandydatow: 84
- brak_dopasowania_pozycji: 3
- bez_epizodu: 9
- uzyte: 2022
- epizod_dokladny: 2022
- epizod_po_nazwie: 0
- etykieta_1: 1388
- etykieta_0: 634
- przesuniecie: {0: 1723, 1: 286, 2: 13}
- wybrany_najblizszy: 1895
- z_wieloma_kandydatami: 1162

Wiersze użyte: **2022**, sesji: 26. Odsetek etykiety 1: 0.686.

## Podział (po sesjach, nie losowo)

- trening: 1505 wierszy (odsetek 1: 0.663); z tego walidacja do doboru hiperparametrów (ostatnie sesje): 442 wierszy
- test: 517 wierszy (ostatnie sesje, odsetek 1: 0.754)

## Metryki na teście

| model | log-loss | AUC | trafność |
|---|---|---|---|
| baseline: stala_czestosc | 0.5772 | 0.5000 | 0.7544 |
| baseline: tylko_odleglosc | 0.5701 | 0.5462 | 0.7544 |
| baseline: najblizszy_kandydat | 0.5670 | 0.5921 | 0.7544 |
| regresja logistyczna {'l2': 1000.0} | 0.5724 | 0.5645 | 0.7544 |
| MLP {'ukryte': [16, 16], 'l2': 10.0, 'epoki': 150} (wybrany) | 0.5615 | 0.6048 | 0.7602 |

Baseline `najblizszy_kandydat`: częstość sukcesu osobno gdy bot wybrał najbliższego (0.678) i gdy nie (0.604), z części treningowej.

Wybór zwycięzcy: najniższy log-loss na walidacji (nie na teście).

## Walidacja krzyżowa po sesjach (5 foldów, out-of-fold)

| model | log-loss | log-loss stałej | AUC | trafność | AUC per fold |
|---|---|---|---|---|---|
| lr | 0.6232 | 0.6270 | 0.5079 | 0.6864 | 0.500, 0.611, 0.529, 0.579, 0.638 |
| mlp | 0.6242 | 0.6270 | 0.5318 | 0.6869 | 0.571, 0.561, 0.561, 0.529, 0.652 |

## Ważność cech

| cecha | waga LR (po standaryzacji) | spadek AUC po przetasowaniu (mlp, test) |
|---|---|---|
| odl | -0.042 | 0.0115 |
| adx | -0.039 | -0.0035 |
| ady | -0.027 | 0.0090 |
| hp | -0.032 | 0.0098 |
| osiag_tak | 0.008 | 0.0054 |
| osiag_nie | 0.000 | 0.0000 |
| inne_w2 | -0.032 | 0.0436 |
| odl_gracza | 0.009 | -0.0089 |
| byl_celem | 0.012 | 0.0004 |

## D1: czy model wybrałby innego kandydata niż bot

Model punktuje wszystkich kandydatów z próbki; bierzemy argmax. **Wynik znamy tylko dla celu wybranego przez bota** —
przewidywania dla innych kandydatów są ekstrapolacją (problem bandyty), nie dowodem lepszego wyboru.

- **test**: zdarzeń 517, z >=2 kandydatami 290; model wybrałby innego: 161 (0.555); model wybrałby najbliższego: 194;
  średnie P(zabity<=15 s): cel bota 0.653, cel modelu 0.732; tylko gdy inny: bot 0.654, model 0.795
- **CV out-of-fold (wszystkie sesje)**: zdarzeń 2022, z >=2 kandydatami 1162; model wybrałby innego: 592 (0.509); model wybrałby najbliższego: 787;
  średnie P(zabity<=15 s): cel bota 0.684, cel modelu 0.723; tylko gdy inny: bot 0.692, model 0.768

## Czas inferencji (1 próbka, CPU, numpy)

- wybrany (mlp): 0.0065 ms; lr: 0.0014 ms; mlp: 0.0065 ms (cel < 0,1 ms)

## Zastrzeżenia

- Etykieta znana tylko dla opcji, którą wybrał bot (selekcja); model uczy się „co się udaje po wyborze bota”.
- Cecha `droga` (długość A*) pominięta: w telemetrii 75% wartości to 0 także dla odległych celów — semantyka UNKNOWN.
- Etykiety 0 skupione: najwięcej w jednej sesji 122 z 634 (sesji z etykietą 0: 23) — sygnał może odzwierciedlać pojedyncze epizody.
- Mało sesji (26), test to ostatnie sesje: wynik zależy od podziału; patrz CV.
- Model trenowany na części treningowej; do wdrożenia wymaga ponownego treningu na całości i trybu cienia.
