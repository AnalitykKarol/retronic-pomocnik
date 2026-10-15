# SPEC: walka z graczami (PvP) - 15.10 wieczór — ZATWIERDZONY 15.10 ~21:50 (decyzje Karola niżej)

Cel: gdy atakuje nas gracz, bot nie tylko ucieka (SPEC_obrona_pk_1015.md), ale umie się bronić: bije napastnika
runami HMM (adori gran) i leczy się UH (adura vita) / exurą. Karol nosi HMM i UH w plecaku. Każde starcie jest zapisane
w telemetrii, z tego później uczymy lokalny model decyzji "walcz / uciekaj / lecz" (D6).

## Co już jest (punkt wyjścia)

- `obrona_pk.py` + `_pk_tick` (gałąź int/obrona-pk, czeka na recenzję): wykrycie ataku gracza, lista `wrogowie.json`,
  ucieczka do depo, leczenie po drodze (exura F2, UH na siebie przez `runa_klik.strzel` przy HP <= PK_UH_HP).
- `runa_klik.strzel(env, cel, runa_id)`: strzał runą z plecaka na pole celu (prawy klik -> "Use with" -> lewy klik),
  z weryfikacją (licznik runy / HP celu). Dziś używane na moby.
- `czaszka.py`: odczyt czaszki przy nicku (Haiku ze zrzutu), `czaszka_gracza(nick)`.

## Zachowanie (propozycja)

Po wykryciu ataku (warunki z obrony PK) bot co obieg wybiera jedną akcję, w tej kolejności:
1. **Lecz:** HP <= PVP_UH_HP (50%) -> UH na siebie; HP <= PVP_EXURA_HP (80%) i mana -> exura. Leczenie zawsze przed atakiem.
2. **Uciekaj:** gdy którykolwiek warunek walki nie jest spełniony (niżej) -> dzisiejsza ucieczka do depo (obrona PK).
3. **Atakuj:** HMM w napastnika (ten, który nas bije; przy kilku - najniższe HP), co PVP_HMM_CO_S (2 s, cooldown runy),
   z odległości 1-PVP_ZASIEG (7) w linii widoku; bot nie goni dalej niż PVP_POGON pól od miejsca startu walki.

Warunki walki (wszystkie): napastnik 1 (PVP_MAX_WROGOW), nasze HP >= PVP_HP_MIN (40%), UH w plecaku >= PVP_UH_MIN (2),
HMM >= PVP_HMM_MIN (5), napastnik nie jest GM, pokrętło PVP_WALKA=1. Gdy przegrywamy (nasze HP spada szybciej niż jego
albo HP < PVP_HP_MIN), przechodzimy w ucieczkę i już nie wracamy do walki z tym nickiem w tym starciu.

## Dane pod model (D6)

Rekord `pvp` co obieg w starciu: nasze HP/mana, HP napastnika, odległość, liczba wrogów, zapas UH/HMM, akcja (lecz / atak /
ucieczka), wynik starcia (zabity, uciekł on, uciekliśmy, śmierć). Do modelu po kilkudziesięciu starciach; do tego czasu
decyduje reguła wyżej. Ręczne walki Karola (`obserwator_reczny`) jako przykłady o najwyższej wadze.

## Testy

`testy/test_walka_pvp.py` na atrapach: sekwencja 20:34:56-20:35:13 (dwóch napastników -> ucieczka, nie walka); jeden
napastnik, HP 90% -> HMM co 2 s; HP spada do 50% -> UH przed HMM; brak UH -> ucieczka; GM -> brak ataku; pościg ograniczony.

## Pytania do Karola

- Q1 Kogo bot może atakować: (a) tylko gracza, który nas zaatakował (obrona, polecam), (b) też każdego z czaszką w widoku,
  (c) też wrogów z listy, zanim zaatakują? Uwaga: atak na gracza bez czaszki, który nas nie uderzył, daje nam czaszkę.
- Q2 Progi: walka tylko 1 na 1, HP >= 40%, UH >= 2, HMM >= 5 - OK?
- Q3 UH na siebie przy 50%, exura przy 80% - OK? (dziś HMM robi F6, UH nauczony?)
- Q4 Ucieczka po przegranej wymianie: zostaje jak w obronie PK (depo, karencja 30 min)?
- Q5 Najpierw sprawdzenie na żywo strzału HMM i UH na siebie (próba na mobie / na sobie), potem walka - OK?

## Decyzje Karola 15.10 ~21:50

- Q1: atakujemy **tylko napastnika** (gracza, który nas uderzył; detekcja z obrony PK). Nikogo innego.
- Q2/Q3: **UH na siebie przy HP <= 20%**; HMM "napierdalamy w nich ile wlezie": strzał HMM przy każdej okazji (cooldown runy),
  bez progu zapasu HMM i bez progu UH do rozpoczęcia walki. Pozostałe progi (1 na 1, HP >= 40% do wejścia w walkę, exura 80%)
  zostają jako pokrętła z wartościami ze szkicu; ucieczka przy HP < PVP_HP_MIN albo braku HMM.
- Q4: po przegranej wymianie ucieczka jak w obronie PK (depo, karencja 30 min).
- Q5: przed walką z ludźmi próba na żywo strzału HMM i UH na siebie (na mobie / na sobie).
