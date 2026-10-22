# Szablon ustawień „nowa postać” (22.10)

Pokrętła startowe dla świeżej postaci (Knight lvl 1, Rookgaard, bez run, blanków, many i pochodni). Kopiuje je
`nowa_instancja.sh` do `instancje/<id>/` (tylko gdy plików tam brak). NIE kopiujemy już `na_zywo.json` z katalogu głównego:
to ustawienia postaci z runami i blankami (po nich bot od razu szedł do depo po blanki).

Wzór: `instancje/gebelish/` (Geblish, Rook, lvl 7, `rook_raty_z9`, tryb `ostrozny`). Ten sam zestaw kluczy, różnice względem niej:

| klucz | szablon | Geblish / główny | czemu |
|---|---|---|---|
| UH_AKTYWNY | 0 | 1 | brak run UH i many (UH_MANA_MIN 100); 1 uruchamia też kontrolę tarczy na starcie |
| UH_W_WALCE | 0 | 1 | runa w walce wymaga UH |
| ZDROWIE_CZAR_AKTYWNY | 0 | 1 | exura jest dostępna dopiero od magic level 1 (Karol 22.10), do tego mana i czar pod F2; w logach Geblisha ani jednego `[ZDROWIE]`, więc 1 nigdy nie działało. Włączyć po osiągnięciu ML 1 |
| WYPRAWA_AKTYWNA | 0 | 1 | brak powodu do wyprawy (bez blanków i jedzenia po wyprawie); ręczne „Wróć do miasta” i ucieczka PK działają bez niego |
| WYPRAWA_BLANKI | 0 | 1 | brak run, nie ma po co trzymać celu blanków (0 = nie kupuj, nie licz) |
| WYPRAWA_DEPO_BLANKI | 0 | 0 (główny 1) | brak blanków nie jest powodem marszu do depo (decyzja Karola 22.10) |
| WROC_REFILL | 0 | 1 | auto-refill (bank, blanki, wyjście) jest dla postaci od run, nie dla świeżej |
| BLANKI_AUTO_BAG | 0 (nowy klucz) | brak = 1 | brak blanków do przenoszenia do bagu na runy |
| PK_UH_HP | 0 (nowy klucz) | brak = 40 | w ucieczce PK nie klikamy UH z plecaka, bo świeża postać go nie ma (0 = wyłączone) |

Reszta (loot, jedzenie z plecaka, mijanie graczy, pościg, `RATUNEK_HAIKU`, `WYPRAWA_TYLKO_DEPO=1` jako bezpiecznik gdyby ktoś
włączył wyprawę) jest wartością Geblisha. `WYPAD_PO_TORCHE=0`, `WYPAD_JEDZENIE=0`, `WYPRAWA_POCHODNIE=0`, `WYPRAWA_JEDZENIE=0`,
`RUNA_AKTYWNA=0`, `ML_CZAR_AKTYWNY=0`, `JEDZENIE_CZAR_AKTYWNY=0` były już wyłączone.

`uciekanie.json` to wiedza o potworach (progi HP, przy których uciekają), nie ustawienie postaci: migawka równa głównemu i
Geblishowi, bez zmian.

Tryby: `ostrozny` ustawia tylko `RUNA_AKTYWNA=0`, więc szablonu nie nadpisuje. Tryby `runy` i `uh` (tryby.json) NADPISUJĄ część
tych kluczy (`UH_AKTYWNY`, `ZDROWIE_CZAR_AKTYWNY`, `WYPRAWA_DEPO_BLANKI`, `WYPRAWA_BLANKI`, `WROC_REFILL`): dla świeżej postaci ich nie używaj.

Zmiana szablonu nie rusza już istniejących instancji. Weryfikacja wczytania: `python3 -I szablony/nowa_postac/../../testy/test_szablon_nowa_postac.py`.
