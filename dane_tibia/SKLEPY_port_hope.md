# Port Hope — sklepy, bank i plan refilu (25.10)

Źródło pozycji NPC: `data/world/world-spawn.xml` serwera jamera 7.6 (centrum spawnu + przesunięcie; NPC chodzi w promieniu 1–2 pól),
oferty: `data/npc/*.xml` + `scripts/runes.lua` tego samego repo. Wszystko z danych, **niepotwierdzone na żywo**; pola stania
NIEZMIERZONE. Wzorzec: `SKLEPY_abdendriel.md`. Depo: (32632,32743,z7), potwierdził Karol 25.10.

| Co | NPC | Pozycja NPC (dane) | Cena | Uwagi |
|---|---|---|---|---|
| bank, wymiana gold → platinum | **Ferks** („banker, exchange coins”) | (32634, 32739, z6) | — | pierwsze piętro nad depo; słowa wymiany niezmierzone |
| **backpack** (id 3940), bag (3939) | **Perod** | (32634, 32740, z5) | backpack 20 gp, bag 5 gp (też lina 50, łopata 50, strzały) | drugie piętro nad depo; wnęka niedostępna z sali na mapie: stać ok. (32633,32741,z5) |
| **blank rune** (id 2260) | **Tandros** (sklep run, `runes.lua`) | (32622, 32740, z5) | 10 gp | to samo piętro co Perod; dane nie podają nazwy sprzedawcy wprost: skrypt `runes.lua` ma `blank rune` 10 gp, Tandros używa tego skryptu |
| **ham** (id 2671), meat (2666) | **Clyde** (karczma) | (32574, 32753, z7) | ham 8 gp, meat 5 gp | karczma na zachodzie miasta, parter (z7), ok. 84 pola od depo |
| (poza refillem) | Brengus (zbroje/broń) (32634,32746,z6), Gail (jubiler) (32621,32739,z6), Ray (poczta) (32621,32746,z6), Zaidal (meble) (32622,32746,z5), Angus (poczta) (32670,32730,z7) | | | |

Uwaga: Sigurd z `runes.lua` stoi w (32626, 31923, z5) — to inne miasto, nie Port Hope. Nie szukać blanków u niego.

## Plan refilu (kolejność odwiedzin)

Budynek depo ma trzy piętra: z7 (depo) → z6 (Ferks) → z5 (Perod, Tandros). Schody w górę (z7→z6): (32625,32749) lub (32629,32749);
z6→z5: kafle (32626,32742) i (32630,32742) na z5 są „w dół”, więc wejście na z5 jest na z6 przy x≈32626/32630, y≈32743 (niezmierzone).

1. **Depo (z7)** — wyjąć gold i zapas; pole depo (32632,32743).
2. **Schody w górę (32629,32749) → z6**, 11 pól od depo.
3. **Ferks (z6)** — zamienić gold na platinum (prawie wszystkie zakupy po 5–20 gp; platinum tylko do zapasu); ok. 17 pól od schodów.
4. **Schody z6 → z5** (ok. (32626,32743,z6), ok. 12 pól od Ferksa).
5. **Tandros (z5)** — blank runes po 10 gp, ok. 5 pól od schodów.
6. **Perod (z5)** — backpacki po 20 gp, ok. 9 pól od Tandrosa.
7. **Powrót w dół** tymi samymi schodami do depo (z7), włożenie rzeczy do depo / wyjście na spot.
8. **Clyde (ham)** — osobny wypad, 84 pola na zachód od depo (parter); robić na końcu albo przy drodze na spot, jeśli spot jest na zachodzie.

Wszystko narysowane na żywej mapie (`http://127.0.0.1:8765/`, warstwa znaczników: piętra z7/z6/z5), znaczniki w
`dane_tibia/mapy/znaczniki.json` (punkty z `refill_ph: true`, trasy „Refill PH n/6”).

## Do zmierzenia na żywo (zanim bot zrobi to sam)

- pola stania przy Ferksie, Perodzie, Tandrosie, Clyde (odczyt pozycji przy NPC, jak w Ab'Dendriel);
- przejście z6 → z5 (dokładne kafle schodów);
- dialog zakupu (backpack/blank, ilość) i wymiany gold→platinum u Ferksa.
- Generator serwisu: patrz „Stan implementacji” niżej (refill bota w Port Hope robi tylko depo, bank/backpack/blanki/ham czekają na pomiary).

## Stan implementacji (25.10)

Generator `generuj_serwis_port_hope.py` → `trasy/serwis_port_hope.json` + `.meta` (`--sprawdz`), test `testy/test_serwis_port_hope.py`;
miasto `port_hope` jest w `refill_auto.MIASTA_SERWISU` i w `serwis.py` (`serwis.py port_hope`).

- **Działa TERAZ tylko krok DEPO** (+ wyjście = pole depo): `kolejnosc = ["depo", "wyjscie"]`. Stanowiska przy skrzyniach z mapy klienta
  (kafle skrzyń w sali depo, 6 szt.), niezmierzone na żywo (strona skrzyni, pola stania).
- **Nie działa, poza kolejnością (plan „do pomiaru”)**: bank (Ferks), backpack (Perod), blanki (Tandros), ham (Clyde). Opis, pozycje NPC
  z tabeli wyżej i docelowa kolejność siedzą w kluczu `plan_do_pomiaru` pliku serwisu (nie w `przystanki`/`kolejnosc`), więc serwis ich nie wykona;
  refill (`--pomin-brakujace`) pomija je z wpisem w logu.
- Brak: pola stania przy NPC, schody z6 → z5, dialogi (zakup backpacka/blanków/hama, wymiana gold → platinum), pomiar położenia skrzyń.
  Gdy pomiary będą, dopisać przystanki w generatorze i dodać je do `kolejnosc`.
