# SPEC: koniec z orbitowaniem — strażnik postępu, wpadnięcie w pościgu, lina z każdego pojemnika, skan orbit — 20.10 — ZATWIERDZONY (Karol 20.10: „przygotuj spec i wyślij agentów”), F1 w realizacji

Cel: bot nie może chodzić w kółko po kilku polach. Człowiek tak nie chodzi, a inni gracze zabijają nas wtedy, gdy zorientują się,
że to bot (Karol 20.10: „takie dziwne ruchy trzeba wyłapywać i analizować, po to mamy logi”). Zakres = cztery punkty
zaakceptowane przez Karola 20.10 po diagnozie niżej.

## Diagnoza (20.10, tylko odczyt logów i telemetrii)

**Przypadek K1 — Kutangen, Rook `rook_raty_z8`, 20.10 16:38:27–17:02:49 (24 min).**
- 16:38:18 pościg za Rat (HP 20%, odl 7) z (32078,32201,8). Klient, prowadzony klikiem ataku, wszedł w dziurę (32086,32197,8).
  Pościg trwał 9 s bez obiegu ticka (`poscig_start` 16:38:18 → `poscig_koniec` 16:38:27); pierwsza próbka po nim: (32086,32197,9).
- `Wpadniecie.obserwuj` (`wpadniecie.py:223`) porównuje z ostatnią próbką sprzed pościgu: 8 pól > `WPADNIECIE_ODL`=3 → uznane za
  teleport, brak wykrycia, brak nauki dziury, brak planu wyjścia, brak alarmu.
- Potem 24 min `IDZ` do punktu trasy na z8 rzutowanego na z9: `krok_do` 436 razy na cel (32079,32201), na zachód ściana. Wynik:
  stały cykl 12 kroków po 6 polach (x 32085–32086, y 32196–32199), każde przejście 30–49 razy, krok co ~2 s. Wzorcowe „to bot”.
- Detektor ratunku (F1, cień) zgłosił to 41 razy (S2 złe piętro, S3 stoi, S4 kręci się) i nic nie zrobił — tylko „wołałbym Haiku”.
- 17:02:52 drugi upadek w tę samą dziurę został wykryty (krótki krok), lina: „liny (3003) nie ma ani w plecaku, ani w ekwipunku”,
  choć Kutangen ma linę (Karol 20.10). Wyjście dał „plan po mapie” pieszo przez z9 na wschód w ~12 s (17:03:04 → z8 ok. 17:03:30).
- Powrót na z8 o 17:02:49 bez akcji bota w logu: UNKNOWN.

**Skan telemetrii 14–20.10** (odcinki >= 45 s w ruchu poza walką/lootem, w obszarze <= 6 pól; skrypt z diagnozy):

| Kiedy | Postać | Gdzie | Czas | Początek |
|---|---|---|---|---|
| 20.10 16:38 | Kutangen | z9 (32085,32196) | 24 min | pościg → dziura, niewykryte (K1) |
| 15.10 18:39 | główna | z9 (32506,32270) | 25 min | pościg → dziura; wykryte, „z9 na trasie” (kieszeń; poprawione 15.10 wieczorem, `testy/test_kieszen_dziura.py`) |
| 15.10 16:10 | główna | to samo miejsce | 5 min | pościg → ta sama dziura |
| 15.10 20:33 | główna | z8 (32496,32266) | 12 min | stan WYPAD |
| 14.10 16:54 / 21:08 / 21:27 | główna | z10, z7 | 17–19 min | sprzed modułu wpadnięcia |

Wspólny mechanizm: (1) dziury łapią postać w pościgu, gdy prowadzi klient; (2) bez postępu bot nigdy się nie poddaje i nie przestaje
chodzić; (3) model w `mozg.py` co minutę ocenia „ekspuję standardowo” (15.10) — orbity nie widzi.

## Zakres (F1)

### A. Wpadnięcie wykrywane także po pościgu (`wpadniecie.py`, hak w pętli pościgu `cavebot.py`)
- Ostatnia znana pozycja dla `obserwuj` aktualizowana także wewnątrz pościgu (i innych pętli, które czytają pozycję poza obiegiem
  ticka), ALBO: zmiana piętra o 1 w dół z próbką sprzed pościgu, gdy pole lądowania leży na drodze/w pobliżu celu pościgu, liczy się
  jako wpadnięcie mimo odległości > `WPADNIECIE_ODL`. Wybór techniki należy do wykonawcy; kryterium = test K1.
- Pokrętło `WPADNIECIE_POSCIG` (0/1, domyślnie 0 = bit w bit jak dziś), wpis w `pokretla.py` i `na_zywo.przyklad.json`.
- Test (`testy/test_wpadniecie_poscig.py`): odtworzenie K1 na atrapach + prawdziwej mapie (`mapa.py`): z8 (32078,32201) → pościg
  9 s → z9 (32086,32197): przy 1 = „Wpadłem”, nauka dziury (32086,32197,8), plan wyjścia; przy 0 = jak dziś (brak wykrycia).
  Teleport (inne miasto, > 15 pól) nadal nie jest wpadnięciem.

### B. Strażnik postępu, który działa (`straznik_orbity.py` nowy + hak w `cavebot.tick`)
- Wyzwalacz: poza `ratunek.STANY_WALKI` i `ratunek.STANY_ZAMIERZONE` postać przez >= `STRAZNIK_ORBITA_S` (60 s) zmienia pozycję
  (>= 8 zmian), ale wszystkie pozycje mieszczą się w <= `STRAZNIK_ORBITA_POL` (6) polach; ALBO S2 złe piętro trwa >= 60 s.
  Liczone z próbek ticka (jak `ratunek.Detektor`, ten sam zegar); walka/loot w środku nie zeruje okna, jeśli po niej postać wraca
  do tych samych pól (orbita z przerwami na szczura to nadal orbita).
- Reakcja, po kolei:
  1. **Stop chodzenia**: koniec kroków i klików, postać stoi (stan `ORBITA`, losowa pauza 3–8 s). Stanie wygląda po ludzku,
     wahadło nie.
  2. **Jedna próba wyjścia planem po mapie** (istniejąca maszyneria `wpadniecie.py`: wielopiętrowy plan + `pietra.py`; dla
     orbity na tym samym piętrze: A* do najbliższego osiągalnego punktu trasy/patrolu z polami orbity jako zakazanymi).
     Limit `STRAZNIK_WYJSCIE_S` (90 s).
  3. **Brak postępu** (nadal w tym samym obszarze albo na złym piętrze) → alarm: `powiadom.powiadom(..., "critical", "orbita")` i plik
     STOP, jak alarm wpadnięcia (`wpadniecie.py:690`). Postać stoi.
- Postęp = wyjście poza obszar orbity o >= 3 pola albo powrót na piętro trasy z osiągalnym punktem; wtedy normalna praca od
  najbliższego punktu trasy.
- Gdy kiedyś powstanie `RATUNEK_HAIKU=2` (SPEC_ratunek_haiku_1019 F2), Haiku idzie pierwszy, strażnik po jego limicie. Teraz
  strażnik działa niezależnie od `RATUNEK_HAIKU`.
- Pokrętło `STRAZNIK_ORBITY` (0 wyłączony, 1 cień: tylko log + telemetria `straznik_orbita`, 2 działa), domyślnie 0; progi
  `STRAZNIK_ORBITA_S`, `STRAZNIK_ORBITA_POL`, `STRAZNIK_WYJSCIE_S` jako pokrętła.
- Zapis: każde zdarzenie w logu bota (`[ORBITA] …`) i w telemetrii (`straznik_orbita`: start, pola, czas, etap, wynik).
- Testy (`testy/test_straznik_orbity.py`): (a) sekwencja pozycji K1 (6 pól, cykl 12) → wyzwolenie po 60 s, stop chodzenia, próba
  planu, alarm + STOP przy braku wyjścia; (b) wyjście w trakcie → powrót do pracy bez alarmu; (c) normalny patrol (te same miejsca,
  ale z wyjściem poza 6 pól), walka w miejscu, PAUZA/PRZERWA, mijanie gracza → brak wyzwolenia; (d) pokrętło 0 = zero zmian,
  1 = tylko log. (e) Pomiar na telemetrii 14–20.10 (`narzedzia/orbity.py` z C): ile wyzwoleń dałby strażnik i czy któreś to
  fałszywy alarm — wynik do raportu.

### C. Skan orbit w logach (`narzedzia/orbity.py`)
- Na bazie skryptu z diagnozy: wejście = pliki `telemetria-*.jsonl` (domyślnie wszystkie instancje i `logi/`, `--dni N`,
  `--instancja`), wyjście = tabela epizodów (instancja, czas, piętro, obszar, liczba pól, ruchy, stany, co było tuż przed:
  pościg/zmiana piętra/stan) i `--json`. Progi jak w B (pokrętła z linii poleceń).
- Dodatkowo wykrywa powtarzalny cykl (ta sama sekwencja >= 4 pól powtórzona >= 3 razy) i oznacza go jako „wahadło”.
- Test (`testy/test_orbity_skan.py`) na wycinku telemetrii K1 (zapisany w `testy/dane/`) i na odcinku normalnego patrolu.

### D. Lina z każdego pojemnika (`wpadniecie.py` `_uzyj_liny`, `pietra.py` tryb „lina”)
- Dziś: okno plecaka (ekran) i slot 10 ekwipunku. Kutangen ma linę, a bot jej nie widzi.
- Szukanie liny (id 3003) we wszystkich otwartych pojemnikach z pamięci gry (`kontenery.py`/rdzeń), potem ekwipunek; użycie
  z tego pojemnika, w którym leży. Gdy nie ma: log z listą sprawdzonych pojemników (nazwy/ID, liczba przedmiotów), żeby było wiadomo,
  gdzie szukać.
- Bez pokrętła (naprawa), ale zachowanie przy linie w plecaku głównym bez zmian.
- Test: atrapa z liną w drugim pojemniku → użycie; brak liny → log z listą pojemników.

## Poza zakresem

Włączanie pokręteł w `na_zywo.json` instancji, restart botów, testy na żywo (osobna zgoda Karola, zasada jednego wywołania),
Haiku w ratunku (SPEC_ratunek_haiku_1019 F2), zmiana sposobu ataku klikiem.

## Bramki

1. F1 kod w worktree na gałęziach `feat/orbity-*`, wszystkie pokrętła domyślnie 0, testy nowe + pełny zestaw `testy/` jak baza.
2. Niezależny checker (diff vs spec) → integracja do `ruch-r1-1014` bez pusha.
3. Karol: które pokrętła włączyć i na której postaci; jedno wywołanie testu na żywo, ustawienia przywrócone.

## Niewiadome

- Jak Kutangen wrócił na z8 o 17:02:49 (brak akcji bota w logu).
- W którym pojemniku Kutangen trzyma linę (sprawdzi D, logując listę pojemników).
- Czy próg 60 s / 6 pól nie łapie normalnej pracy — mierzone w B(e) na telemetrii.
