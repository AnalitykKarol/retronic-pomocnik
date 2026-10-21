# ANALIZA: wpływ wolniejszego skanu stworów (commit 1705fd9, 20.10 19:04) na pościg i loot — 21.10 ~13:10, tylko odczyt

Zgłoszenie Karola: „dość mocno czuć tę ilość akcji i odczytu, którą obniżyliśmy: czasem pościg nie startuje, loot w walce słabo działa, dużo się gubi”.

## Co zmienił commit
`rdzen.Pamiec`: skan stworów w tle tylko wtedy, gdy wynik zbliża się do `WIEK_STWORY` (0,5 s) / `WIEK_PUSTO`; wcześniej co 0,05 s (stwory) /
0,15 s (pusto), 7–8 skanów/s, z czego 4 z 5 „do kosza”. Skaner działa w procesie gry (`straznik.py`), więc nowy kod obowiązuje od startu sesji gry.

## Kto na czym (straznik.log)
20.10: sesje gry 14:55–15:26 → do ~22:50 = **stary skaner** cały dzień (wydra 20:00 = nowy). 21.10: wszystkie sesje od 07:12–07:18 = **nowy**.

## Pomiary
- `logi/rdzen-skan.log` 21.10: szybki skan **śr. 0,18–0,28 s, max 0,56 s**, ~1,7 skanu/s; 93–100% zapytań bota z cache.
  Wiek danych o stworach przy decyzji: do ~0,5 s (limit) + czas skanu ≈ do 0,8 s. Danych sprzed zmiany (czas skanu przy 7–8/s) brak — log zrotowany.
- Telemetria (epizody celów, pościgi, loot), 20.10 vs 21.10:

| Instancja | ranne zgubione / (zgubione+zabite) | loot ok | loot w walce ok | pościg <=30% HP: odl. start (med) | skuteczny pościg |
|---|---|---|---|---|---|
| invincible | 9,1% → 18,3% | 93% → 86% | 99% → 100% | 2 → 2 | 89% → 95% |
| dawajkesh | 6,9% → 5,3% | 94% → 93% | 99% → 100% | 2 → 2 | 91% → 94% |
| kolanoth | 2,8% → 4,2% | 92% → 96% | 100% → 100% | 2 → 2 | 94% → 94% |
| kutangen | 2,5% → 5,9% | 93% → 87% | 99% → 94% | 2 → 2 | 97% → 94% |
| wydra | 2,5% → 7,0% | 90% → 79% | 97% → 85% | 2 → 2 | 97% → 94% |

  Zgubione ranne bez żadnego kroku pościgu: 40–53% w oba dni (bez zmiany udziału).

## Zakłócenia (dlatego to NIE jest dowód)
Mapy: invincible 20.10 Rook (trasa awaryjna) → 21.10 trolle (trolle uciekają, ogień w korytarzu); kutangen z8 → z9; wydra z8 → kanały z11;
dawajkesh Rook → Thais/Edron trolle. 21.10: reset serwera 10:00, ML u invincible/dawajkesh, 6 instancji (20.10: 4–5) = większe obciążenie CPU.
Najbardziej porównywalny kolanoth (`rook_raty_z8` oba dni): zgubione 2,8% → 4,2%, loot lepszy.

## Wniosek
- Odległość startu pościgu i skuteczność rozpoczętych pościgów **bez pogorszenia**. Wzrost zgubionych ranych celów u 4/5 botów jest, ale
  nie da się go przypisać skanerowi przy zmianach map/mobów.
- Mierzalny problem świeżości: sam skan trwa 0,2–0,3 s (obciążenie 6 gier + strażników), więc dane bywają stare niezależnie od częstotliwości.

## Jak rozstrzygnąć (propozycja, decyzja Karola)
A/B na jednej instancji, ta sama mapa, 1–2 h: stary rytm skanu (pokrętło env w `rdzen.Pamiec`, np. `RETRONIC_SKAN_CIAGLY=1` = 0,05 s, domyślnie
nowy) vs nowy na drugiej. Wymaga zmiany kodu i restartu sesji gry tej instancji (relog).
