# SPEC: obrona przed graczami (PK) - 15.10 wieczór

## Co się stało (logi: pomocnik-stabilny/logi/mozg-20261015-1807.log)
- Edron trolle, Jointoramix lvl 17. O 20:34:56 w widoku Krzyssxd, potem Brezniev Leonid. Nic nie pisali.
- 20:35:06: Brezniev obok (1,0), najbliższy troll 3 pola, HP 100 -> 82%. 20:35:13: Krzyssxd obok (1,0), trolle 2-5 pól, HP 48%.
  Bot uciekał "po trasie" jak przed trollem. Karol przejął sterowanie, nie zdążył uciec do miasta, postać zginęła (~10% expa, prawdopodobnie plecak z UH).
- AI (Decyzja [obcy_gracz] 20:35:11) napisało "gracze bez czaszki", choć rdzen.py NIE czyta czaszki (cavebot.py ~3444): brak danych potraktowany jak brak czaszki.
- Czat: bot odpowiedział "no idea xd" na "exura" Loveliy (czar innego gracza wzięty za wiadomość do bota).

## Wymagania (Karol)
1. **Atak gracza z danych (priorytet):** spadek HP, gdy obok (odl <= 1, ew. w zasięgu czaru) jest obcy gracz, a żaden potwór nie stoi przy nas, to atak PK. Reakcja natychmiast, bez pytania modelu:
   - ucieczka do miasta (trasa dojścia do depo w odwrotną stronę / edron_do_depo od bieżącej pozycji, wejście w strefę ochronną),
   - leczenie po drodze czym się da (exura F2, UH z plecaka na siebie, jedzenie),
   - nick na listę wrogów (plik stanu), alarm + powiadomienie Karola,
   - nie wracać na spot, dopóki wróg jest w widoku / przez X minut. Kontratak "dojdziemy do tego później".
2. **Czaszka ze screena przez Haiku:** gdy obcy gracz w widoku, zrzut ekranu (wycinek wokół nicku) do Haiku: czy obok nicku jest biała lub czerwona czaszka. Wynik do decyzji obcy_gracz (czaszka = traktuj jak wroga, uciekaj zanim zaatakuje). Kesz per nick, limit kosztu.
3. **AI nie zgaduje czaszki:** w kontekście dla modelu "czaszka: nieznana", gdy brak odczytu; prompt zakazuje pisać "bez czaszki" bez danych.
4. **Czat:** słowa czarów (exura, exura gran, utani hur, utevo lux, adura vita itd.) od innych graczy to nie wiadomość do bota.
5. (Później, przy grze) Server Log "You lose N hitpoints due to an attack by NICK" jako potwierdzenie; czaszka z pamięci (pole stwora w OTClient).

Testy offline na odtworzeniu sekwencji 20:34:56-20:35:13 z logu (stwory + HP). Nie restartować żywego bota bez słowa Karola.
