# Diagnoza: „widmo potworów” / niewidzialna blokada kroku (19.10 ~22:20, tylko odczyt)

Zgłoszenie Karola: „cały czas problem z jakimiś widmo potworami” → bota blokuje coś niewidocznego.
Wynik: to NIE są wpisy-widma potworów. Pole docelowe puste w 97% porażek, pozycje stworów świeże, konsumenci filtrują piętro.

| | Mastafian 20:54–21:58 | Johny 21:20–21:58 |
|---|---|---|
| wywołania strzałką (`krok_do`) | 132 | 273 |
| wywołania z porażką | 39 (30%) | 79 (29%) |
| linie „nie ruszył” | 61 (~92 s straty, 2,3%) | 123 (~185 s, 7,8%) |
| pole docelowe zajęte przez moba | 1 | 3 |

A (~95%): pojedynczy klawisz gubiony tuż po poprzednim kroku. `bot.py` `Postac.krok` (~307) kończy czekanie, gdy RPC `pozycja`
pokaże nowe pole, a `pozycja` wyprzedza własny wpis na liście o 1 krok → następne naciśnięcie trafia w trwający krok. `krok_do`
(`cavebot.py` ~3614) nie ponawia klawisza, przechodzi do prostopadłego (stąd `mapa przechodnie False` i zygzak), każda porażka 1,5 s.
Pewność średnia; rozstrzygnie rekord na każde naciśnięcie (czas od ostatniej zmiany pola).

B (2×/h): pole „zablokowane” ~35 s w korytarzu (Mastafian 21:12:59 (33055,31832); Johny 21:48:01 (32484,32293)), lista pusta, rozjazd
`poz`/lista o 1 pole, drugi wpis własnego nicka; puszcza dopiero D3 (`inny_punkt`). Przyczyna nieustalona (alternatywa: serwer odrzuca
krok, rubber-band). Komunikaty serwera („Sorry, not possible”) nie są logowane.

Poboczne: log `na polu` w `krok_do` dopasowuje (x,y) bez piętra (Rotwormy z z10 w logu Johny'ego) — myli przy czytaniu, nie wpływa
na decyzje. Nie ma tego w `SPEC_telemetria_ruchu_1019.md` (T1–T5 bez rekordu nieudanego naciśnięcia).

Kierunek naprawy (do spec, decyzja Karola): po kroku czekać na koniec kroku; przy pierwszej porażce na wolne pole ponowić ten sam
klawisz po ~0,3 s; mob wylistowany na polu (to samo piętro) = od razu inny kierunek; seria B: zmiana punktu po ≥3 porażkach z tego
samego pola zamiast ~35 s D3; rekord telemetrii na naciśnięcie. Skrypty i surowe odczyty: scratchpad sesji omarchy-7e (a1–a12.py, poll*.jsonl).
