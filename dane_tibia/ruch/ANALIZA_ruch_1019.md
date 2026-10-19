# Analiza chodzenia 19.10: czy jest gorzej i jakich danych brakuje

Analiza tylko do odczytu, telemetria 14-19.10 obu instancji (`logi/`, `instancje/test/logi/`). Kod bota bez zmian.
Skrypty: `/tmp/claude-1000/-home-charlie-omarchy/5d680069-14e2-42d0-8e1d-bcd53a88c0e9/scratchpad/ruch/a1-a8.py` (tymczasowe).

## Wnioski

1. **Marsz na expowisku nie jest wolniejszy.** Główna (Edron, gobliny): exp/h 2710 (17.10), 3728 (18.10), 4136 (19.10);
   zabić/h 119, 149, 165. Z próbek co 1 s: bez ruchu w IDZ 6% (17.10) i 4% (19.10), mediana 1,67 pola/s (Manhattan) bez zmian.
2. **Dwa boty naraz nie spowalniają się.** Główna sama / razem z testową: 2,70 / 2,62 obiegu/s, luki 27,8% / 28,8%.
3. **Więcej graczy na expowisku jest faktem, koszt umiarkowany.** Edron 17.10: 5 nicków, 19.10: 13. `mijanie` 18.10: 3 razy, 1,3 min;
   19.10: 35 razy, 17,3 min (ok. 2,7% dnia). Najczęściej: Szogun 7, Sir Harry 6, Raczek 5, Lokhard 4.
4. **Największe straty to zawieszki, nie marsz.** D3 (`d3_wynik.stoi_s`): główna 19.10 21 min, testowa 27 min (jedna 895 s w kanałach
   przy 32016,32160,11). Watchdog bezczynności testowej: 15 razy, 14 min.
5. **Wieczorny spadek głównej (19:00-21:00, ok. 2400 exp/h)** to ucieczka PK do depo (WYPAD 44% godziny, 23 min, w zasięgu do 29 nicków), nie chodzenie.
6. **Drabiny na trasie do depo Edron** zawodzą przy pierwszej próbie w każdej wyprawie (`drabina_bez_zmiany_pietra`: 4 na wyprawę 19.10, 22 na wyprawę 17.10).
   Miejsca (z poprzedzającego `wypad_krok`): (33146,31823,11) 17x, (33150,31820,10) 15x, (33167,31824,9) 10x w 17-19.10.
7. Testowa na `thais_szczury_opt` (19.10 18-19): mediana 1,0 pola/s wobec 1,67 u głównej. Przyczyna NIEUSTALONA (prędkość postaci nie jest logowana).

## Czego nie zapisujemy

| # | Brak | Skutek | Koszt dodania |
|---|---|---|---|
| D1 | `ruch_okno` liczy „stoi” na odstępach między obiegami (ok. 0,37 s), krótszych od kroku postaci | pokazuje 30% stania w IDZ, próbki co 1 s pokazują 4%; metryka zawyża i myli | mały: „stoi” dopiero bez zmiany pola przez >= 1 s albo czas kroku |
| D2 | przyczyna `inne` pokrywa 75-80% stania; brak powodów mijanie, unikanie, wypad, pauza ludzka, D3, pole zajęte, czekanie na klik | nie wiadomo, co naprawiać | mały, w `_ruch_powod` |
| D3 | luki obiegu >= 1,5 s to 28% czasu, bez informacji, który krok obiegu trwał | brak wiedzy, gdzie ucieka czas reakcji | średni: pomiar czasu faz obiegu (RPC, ogień, loot, czar, model) |
| D4 | `probka.stwory` bez id stwora | nie da się zmierzyć, ile mobów zabierają inni gracze ani czasu respawnu | mały: id już jest w `decyzja.opcje` |
| D5 | tryb trasy (pętla Edron) bez statystyk odcinków; patrol ma `zabicia_miejsce`, trasa nie | 30-38% próbek na expowisku bez moba w widoku, nie wiadomo, które odcinki są puste | średni: rekord odcinka (czas, zabicia, moby w widoku) |
| D6 | `wypad_blad` bez pozycji, pola celu i czasu | miejsca drabin trzeba było zgadywać z poprzedniego zdarzenia | mały |
| D7 | prędkość postaci (speed) i prędkość podłoża | brak sufitu, nie da się ocenić 1,0 vs 1,67 pola/s | do sprawdzenia, czy rdzeń ją zwraca |
| D8 | `poz` i `stwory` w próbce z różnych chwil: własny wpis na ±1 polu w 3285 z 25 820 próbek (13%) 19.10 | w ruchu położenia mobów w próbce przesunięte o pole; czy decyzje bota mają ten sam rozjazd: NIEUSTALONE | sprawdzić przed zmianą |
