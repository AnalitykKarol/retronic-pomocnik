# Kolanosh utknął w powrocie z trolle_edron_z9w (21.10 20:13–20:14)

Status: NAPRAWIONE OFFLINE — na żywo niesprawdzone (pierwszy powrót z z9w). Postać wyprowadził ręcznie Karol.

## Przebieg (instancje/kolanoth/logi/mozg-stdout-1021-2008.log)

- 20:08:38 start na `trolle_edron_z9w` z dojściem; 20:09:41 dojście zakończone na (33119,31740,z9), pętla.
- 20:13:38 żądanie powrotu (`depo:reczny`), baza `edron`:
  `Wyprawa: depo: brak drogi z (33123, 31749, 9), idę starą trasą`.
- „Stara trasa” = całe `edron_do_depo` od początku; wypad szedł A* do (33131,31806), z z9w nieosiągalne:
  kroki Down/Right „nie ruszył” w (33121..33123, 31751..31756, 9), 3× `etap_nieosiagalny` (etap 6).
- 20:14:52 `ALARM: wyprawa: utkniecie: brak postępu na etapie 6 w (33121, 31756, 9)` → STOP. HP 188/195.

## Mechanizm

`wyprawa.droga_do_depo` szuka drogi po pętli łowiska do trasy „do” albo przez `wyjscia` planu. Pętla z9w jest
cała na z9, „do” planu `edron` zaczyna się na z8, a `wyjscia` miały tylko gobliny z9 (33092,31837). Spot z9w
(wygenerowany 21.10) dostał dojście, ale nie dostał wyjścia w planie powrotu.

## Poprawka

- `wyprawa.PLANY_PK["edron"]["wyjscia"]`: lina na (33119,31740,z9) (dziura, którą dojście schodzi z z8; mapa: kandydat
  pewny), stanie (33119,31739,z9) (pole liny wolne), lądowanie (33119,31741,z8), dalej `trolle_edron_z9w_do_depo`.
- `trasy/trolle_edron_z9w_do_depo.json` (`generuj_powrot_edron_z9w.py`): odwrócony odcinek z8 dojścia z9w (przebyty
  dziś 2×) bez pola dziury + `edron_do_depo` od liny (33117,31774,z8) (powrót sprawdzony, Dawajkesh 18:24).
- Kopia: `wyprawa.py.bak-20261021-z9w-powrot`.

## Dowód (offline)

- `testy/test_powrot_edron_z9w.py` 100/100: bez nowego wyjścia `brak drogi` (objaw), z nim droga do depo z miejsc
  zacięcia i co 10. punktu pętli, pierwsze przejście lina (33119,31739,9)→(33119,31741,8), bez dziury z8, bez ognia.
- `zbuduj_etapy` + `sprawdz_plan`: etap `LINA` stoi (33119,31739,9), cel (33119,31740,9), bez błędów.
- Bez regresji: test_wyprawa 216/216, test_wyprawa_droga_depo 50/50, test_wyprawa_dojscie 25/25,
  test_trasa_lina_edron 9/9, test_patrol_edron 17/17, test_wyprawa_dziura_zajeta 21/21.
- `waliduj_trase.py trolle_edron_z9w_do_depo`: 1 błąd (33166,31820,7)→(33166,31816,7) — odziedziczony, ten sam w
  `edron_do_depo` i `trolle_edron_z9w_dojscie` (obie przebyte na żywo).

## Otwarte

- Pierwszy powrót na żywo z z9w (lina z9→z8 nie jest w `przejscia_nauczone.json`).
- `trolle_edron_z9z` ma tę samą lukę: `droga_do_depo` = brak drogi z 14/14 punktów pętli. Do zrobienia przed
  pierwszym wejściem (plan 22.10 pkt 5).
- Działające boty mają stary kod do restartu.
