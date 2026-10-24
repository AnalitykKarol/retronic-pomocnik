# Ab'Dendriel — sklepy i bank (24.10)

Źródło pozycji NPC: `dane_tibia/serwer74/npc_pelne.json` (punkt spawnu, NPC chodzi w promieniu). Pola stania: NIEZMIERZONE, chyba że opisano inaczej.

| Co | NPC | Pozycja NPC (dane) | Cena | Stan |
|---|---|---|---|---|
| backpack (id 2865), bag (id 2857) | **Bashira** | (32669, 31655, z8) | backpack 20 gp, bag 4 gp | Karol potwierdził 24.10: „npc nazywa się Bashira, ten od backpacka”. **Pole stania: (32667, 31655, z8)** (Karol „jestem jeszcze raz u Bashiry”, odczyt z gry 15:25:22; wcześniejszy odczyt (32675, 31669) był w drodze). Dialog zakupu do zmierzenia przy pierwszym serwisie. |
| bank (wymiana gold → platinum) | **Briasol** (jubiler, „exchange money”) | (32635, 31667, z8) | — | Karol potwierdził 24.10 15:24: „Briasol jest od wymieniania golda”. **Pole stania: (32637, 31667, z8)** (Marianni, odczyt z gry 15:24:05, Karol stał przy nim). Słowa dialogu wymiany niezmierzone (w tematach z danych brak „change”). |
| blank rune (id 3147) | **Shiriel** | (32670, 31657, z6) | 10 gp | Karol stanął przy niej 24.10. **Pole stania: (32669, 31659, z6)** (odczyt z gry 15:28:05). Droga od Bashiry nagrana: `trasy/abdendriel_bashira_shiriel.json` (40 pkt, 66 pól; z8 → schody w górę (32682,31685→31686) z7 → schody w górę (32682,31686→31688) z6). Dialog niezmierzony. |
| meat (id 3577), ham (id 3582) | **Anerui** („mistress of the hunt”) | (32669, 31659, z7) | meat 4 gp, ham 6 gp | Tylko dane, niepotwierdzone na żywo. |

Shiriel (z6), Anerui (z7) i Bashira (z8) mają w danych prawie to samo x/y (32669–32670, 31655–31659): to jeden budynek z trzema piętrami; nagranie z 24.10 to potwierdza: z Bashiry (z8) na Shiriel (z6) idzie się dwoma schodami w górę po wschodniej stronie (x 32682).

Nie ma jeszcze `generuj_serwis_abdendriel.py`, więc refill w Ab'Dendriel pomija bank i backpack. Pole depo też NIEZMIERZONE (`DEPO_STOI` w `generuj_powrot_abdendriel.py`).
Inne miasta: backpack Edron = Beatrice (`generuj_serwis_edron.py`), Thais = Gorn (`generuj_serwis_thais.py`).
