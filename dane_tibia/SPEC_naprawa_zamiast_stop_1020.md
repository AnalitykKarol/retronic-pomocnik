# SPEC: naprawa zamiast STOP w starym kodzie — 20.10 — SZKIC do akceptu Karola

Cel: zasada naprawiania (`CLAUDE.md`, Karol 20.10: „nie stop tylko naprawa… zawsze”) obejmuje też kod sprzed strażnika orbit.
Bot, który utknął, ma próbować kolejnych sposobów naprawy, a nie zapisywać STOP ani wysyłać alarmu krytycznego. Wzór i silnik:
`straznik_orbity.Reakcja` (rotacja sposobów, losowe pauzy, flaga `bez_alarmu` w `wpadniecie.py`), `SPEC_orbity_straznik_1020.md`.

## Miejsca (lista z przeglądu 20.10, plik:linia na `646a999`)

| # | Miejsce | Dziś | Po zmianie (propozycja) |
|---|---|---|---|
| N1 | `wpadniecie.py` `_alarm` (limit `PIETRA_MAX_S` 150 s ~364, „lina i plan nie działają” ~377) | critical + STOP | przekazanie do rotacji napraw strażnika (tryb „złe piętro”: plan, klik, krok, …), bez końca, rzadkie zwykłe powiadomienie |
| N2 | `wyprawa.py` `_alarm_utknieciu` (~2104, `WYPRAWA_STOP_PRZY_UTKNIECIU=1`) | critical + STOP | utknięcie w drodze: ponowienie odcinka inną drogą / klik obok / cofnięcie do poprzedniego punktu etapu, potem powrót na łowisko bez zakupów (jak awaria wypadu); patrz Q1 dla teleportu |
| N3 | `pietra.py` `_porazka` (~853, `PIETRA_PORAZKI_STOP=3`) | po 3 porażkach critical + „przerywam” | po 3 porażkach rotacja: inne pole przejścia, inny punkt trasy na docelowym piętrze, plan po mapie; powiadomienie zwykłe |
| N4 | `cavebot.py` ~9882 i kolejne („trzy punkty z rzędu nieosiągalne, przerywam”) | koniec trasy | rotacja punktu: dalszy punkt, odwrócenie pętli, A* z polami zakazanymi, potem rotacja strażnika |
| N5 | `mozg.py` ~3966 dojście nieudane daleko od trasy | critical, trasa nie startuje | ponowienie dojścia od najbliższego punktu dojścia (do N razy, różne podejścia), potem plan po mapie do najbliższego punktu trasy |
| N6 | critical bez STOP: `STRAZNIK_POSTEP_S3` (`cavebot.py:456`, ~5035), `wypad.py` ~1342 / ~1894 / ~1924, `d3_zawieszka.py:280`, `mozg.py:3609` ślepota (restart) | critical | zwykłe powiadomienie, rzadko; tam, gdzie dziś jest tylko alarm (S3, D3), uruchomienie rotacji napraw |

Bez zmian (wyjątek zasady): PK (`cavebot.py` `_pk_stop` ~7678), niskie HP / ucieczka, zgon (`SMIERC_STOP`), polecenie Karola
(`zatrzymaj.sh`, STOP_RECZNY, przycisk AI OFF).

## Wspólne zasady wykonania
- Jedno pokrętło `NAPRAWA_ZAMIAST_STOP` (0/1, domyślnie 0 = bit w bit jak dziś; analityk nie może wyłączyć, gdy Karol włączył).
- Naprawa idzie przez jeden silnik (rozszerzenie `straznik_orbity.Reakcja` o wejścia „z alarmu”: N1, N3, N4, N6), żeby rotacja,
  pauzy, limity i powiadomienia były w jednym miejscu. Wyprawa (N2) i dojście (N5) mają własne cele, więc naprawa tam = ponowienie
  odcinka/etapu inną drogą w ich module, z tymi samymi zasadami (losowe pauzy, różne pola, bez wahadła).
- Powiadomienia: critical tylko dla wyjątków życia; reszta `normal`, najwyżej raz na 30 min na rodzaj.
- Każda zmiana z testem: dziś STOP/critical → przy pokrętle 1 rotacja, zero STOP, zero critical; przy 0 jak dziś.

## Pytania do Karola
- **Q1 teleport w mieście w trakcie wyprawy** (`wyprawa.py`, `wymus_stop`): to zwykle zgon albo GM. Zostawić STOP (wyjątek życia)? Rekomendacja: tak.
- **Q2 dojście nieudane (N5)**: po ilu ponowieniach zamiast łowiska przejść do planu po mapie? Rekomendacja: 3.
- **Q3 kolejność**: N1+N3+N4+N6 (jeden silnik, jeden agent) i N2+N5 (wyprawa, dojście, drugi agent) równolegle. Rekomendacja: tak.

## Poza zakresem
Włączanie pokrętła na postaciach i restart (osobna zgoda), zmiana wyjątków życia, Haiku w ratunku.
