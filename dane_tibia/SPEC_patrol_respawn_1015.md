# SPEC: patrol według respawnu (15.10) — kroki 1–2 zrobione 15.10 (akcept Karola: wariant A, tryb cienia; włączenie po porównaniu)

Cel: mniej chodzenia na puste miejsca, więcej zabić na godzinę. Bot wybiera następny kierunek patrolu po tym, gdzie
trolle **powinny już być** (czas od wyczyszczenia, czas respawnu nauczony z danych), a nie losowo po wagach.
To też pierwsza "mapa obecności" mobów, z której skorzysta przyszły lokalny model (decyzja D4 w
`SPEC_model_lokalny_1015.md`).

## 1. Fakty z danych (telemetria 14–15.10, jaskinia trolli, 7,7 h) [POTW]

- Czas: walka 56%, chodzenie (IDZ) 35%, loot 6%. Dojścia do miejsc, z których wizyta była pusta (0 zabić na miejscu
  i w drodze): 28 min.
- **Zabicia dzieją się w drodze, nie na miejscu:** na 8 głównych miejscach (m1–m8, ~50 wizyt każde) zabicia na samym
  miejscu to 0–3 na ~50 wizyt, a w drodze śr. 1,8–4,2 na wizytę. Trolle chodzą po jaskini, miejsce patrolu to raczej
  kierunek niż cel.
- Mapa obecności (20 981 obserwacji mobów w próbkach, komórki 4x4): najgęstsze (32496,32268,z8) 2130,
  (32484,32296,z9) 2097, (32500,32268,z8) 1704, (32500,32280,z9) 1689, (32480,32292,z8) 1477, (32496,32280,z9) 1309,
  (32500,32276,z9) 1248; dalej 850 i mniej.
- Respawn [HIP z danych]: po zabiciu, następny mob w promieniu 3 pól: połowa w ≤7 s (to inny troll z grupy), 75% w
  ≤303 s, 90% w ≤482 s (864 z 1 879 zabić, tylko gdy bot widział to miejsce). Czyli realny respawn ~5–8 min.
- Obecny patrol: losowy wybór miejsca wg wag (`PATROL_RUNDA`: każde raz na rundę), zawrót z pustego miejsca w
  widoku (`PATROL_ZAWROT`, 15.10). Odstęp między wizytami tego samego miejsca: mediana 450–710 s.

## 2. Pomysł

1. **Mapa obecności na żywo** (`obecnosc.py`, czysta logika): siatka komórek (4x4 pola, per piętro) w jaskini.
   Każda komórka pamięta: kiedy ostatnio była w widoku, kiedy widziano tam moba, kiedy zabito tam moba i ile.
   Komórka "wyczyszczona" = w widoku i pusta. Stan zapisywany do pliku (przeżywa restart).
2. **Oczekiwana liczba mobów** w komórce teraz: `gęstość_komórki × f(czas od wyczyszczenia / respawn)`, gdzie
   gęstość = średnia historyczna (z telemetrii, odświeżana), respawn uczony z danych (start 300 s, rozkład per
   komórka, gdy danych dość).
3. **Wybór celu patrolu:** dla każdego miejsca (m1..m8 + przejścia pięter) wartość = suma oczekiwanych mobów w
   komórkach **na drodze A*** i przy miejscu, podzielona przez czas dojścia (pola × czas kroku + koszt schodów).
   Bierzemy max; remis/niska pewność = dzisiejszy wybór. Miejsce świeżo wyczyszczone (< respawn) ma wartość ~0.
4. **Bez zmian:** walka, ogień, unikanie graczy, zawrót z pustego miejsca, wyprawy. Gracz przy komórce obniża jej
   wartość (moby zabiera on).

## 3. Kroki (bramki)

1. **Analiza offline** (`obecnosc.py --raport`): z telemetrii gęstość per komórka, respawn per komórka, symulacja:
   jak nowy wybór celu wypadłby na historycznych przebiegach (ile zabić "w drodze" przy oczekiwanych mobach vs
   faktyczne). Wynik: raport md. Bez zmian w bocie.
2. **Tryb cienia:** bot liczy mapę obecności na żywo i zapisuje w telemetrii `patrol_cel` także wybór nowej metody
   (`cel_respawn`, wartości), ale idzie jak dziś. Porównanie po kilku godzinach.
3. **Włączenie:** pokrętło `PATROL_RESPAWN=1`; miary: exp/h (dziś ~2 450), udział IDZ (35%), puste dojścia/h.
   A/B: na zmianę godzina z i bez (albo jeden komputer z, drugi bez). Cofnięcie = pokrętło 0.
4. Dane trafiają też do rekordów `decyzja` (D4: wybór miejsca patrolu, opcje z cechami: wartość, dojście,
   oczekiwane moby) — pod lokalny model.

## 4. Testy

- `testy/test_obecnosc.py`: komórka w widoku i pusta = wyczyszczona; po czasie respawnu wartość rośnie; zabicie
  aktualizuje; zapis/odczyt stanu; wybór celu: świeżo wyczyszczone miejsce przegrywa z dawno niewidzianym przy
  podobnej drodze; dłuższa droga z mobami po drodze wygrywa z krótką pustą; brak danych = dzisiejszy wybór.
- Regresja: test_patrol*, test_cavebot (te same FAIL co przed).

## 5. Pytania do Karola

- Q1 Zaczynamy od kroku 1 (analiza offline, sam raport) i 2 (tryb cienia), włączenie dopiero po porównaniu? (polecam)
- Q2 A/B: na zmianę godzinami na jednym komputerze, czy jeden komputer z nową metodą, drugi bez?
- Q3 Czy miejsca patrolu (m1–m8) zostają jako jedyne cele, czy bot może celować w każdą gęstą komórkę mapy
  obecności (więcej swobody, trudniej przewidzieć trasę)?

## 6. Wynik kroków 1–2 (15.10, workflow wf_279f8751-df4, checker NITS)

- `obecnosc.py` (mapa obecności, respawn, wybór celu, `--raport`), raport `dane_tibia/RAPORT_obecnosc_1015.md`.
- Najmocniejszy wynik: 54% wizyt bota szło do miejsc wyczyszczonych < 300 s temu: 1,85 zabicia/wizytę i 42% pustych,
  pozostałe 3,27 i 13%. Spearman(wartość modelu, zabicia wizyty) 0,60 (cząstkowa po długości drogi 0,52). Respawn:
  mediana ~465 s (górne ograniczenie). Zysku w exp/h symulacja nie rozstrzyga — tylko A/B.
- Tryb cienia (`PATROL_RESPAWN_CIEN=1`): `patrol_cel` + `cel_respawn`, `wartosci`, `zgodny` (None = metoda bez zdania),
  rekord `decyzja` D4; ruch bez zmian. Poprawki po recenzji: droga cienia po grafie pliku miejsc (`DrogiGraf`, bez A*,
  0,25 ms) zamiast linii prostej; martwe pokrętło `PATROL_RESPAWN` usunięte (wróci w kroku 3); mapa tylko dla trolli;
  `gracz_przy` liczony przy samym miejscu. Testy: test_obecnosc 60/60, test_patrol_respawn_cien 47/47.
