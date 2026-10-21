# Podsumowanie 21.10 (co zrobione, co włączone, co dalej)

Szczegóły: `dane_tibia/ruch/AUDYT_1021.md` (audyt i plan naprawy), specyfikacje `dane_tibia/SPEC_*_1021.md`, stan w `STAN.md`.
Commity na `ruch-r1-1014` (bez pusha): `b61126c`, `1818c4f`, `6536f67`, `dc1a30e`, `9ced8ae`, `fd0ecef` i kolejne.

## Włączone u wszystkich 5 postaci (stan 17:37)

- **Pokrętła w `na_zywo.json` (kopie `*.bak-20261021-wszystko`):**
  - `LOOT_BEZ_DRABIN`=1;
  - `WPADNIECIE_PLAN_PULE`=1;
  - `PRZEJSCIE_TRZY_SPOSOBY`=1;
  - `WPADNIECIE_BEZ_STOP`=1;
  - `ROZLACZENIE_STOP`=1;
  - `SKAN_WIEK_*`=0,5/0,5.
- **Restart z nowym kodem (17:33–17:37), każdy na swojej bieżącej mapie:** dawajkesh (`trolle_edron`), invincible (`gobliny_edron`), kolanoth (`trolle_edron_z9w`), kutangen (`thais_pn_z8`).
- **Wydra:** `STOP_RECZNY` (gra Karol). Pokrętła wpisane, nowy kod wejdzie przy następnym starcie.
- **Powiadomienia:** plik `cisza` (od 20.10 09:45) zdjęty, teraz `cisza.wylaczona-20261021`.

## Co robi nowy kod

| Funkcja | Skrót | Spec / test |
|---|---|---|
| Kratki Thais: najpierw Use | zejście kratką z planu wpadnięcia | `SPEC_kratki_drabiny_thais_1021.md` F4, `test_pietra_kratka` |
| Loot bez Ctrl+klik na drabinach | koniec wychodzenia z jaskini po lootcie | tamże F3 |
| Przejścia: wejść / kliknąć / lina + pamięć | działający sposób zapamiętany dla wszystkich (`dane_tibia/ruch/przejscia_nauczone.json`) | `SPEC_przejscia_trzy_sposoby_1021.md`, 14/14 |
| Schody i drabina pod nogami w wyprawie | Rook (kutangen) | `test_wypad_schody_rook` 10/10 |
| Wpadnięcie bez STOP | cykle ponawiania, STOP po 150 s i 3 cyklach | `SPEC_wpadniecie_bez_stop_1021.md`, 35/35 |
| Powroty do miasta (K2) | kanały Thais przez znane drabiny pod kratkami, poprawki Edron/Rook | `SPEC_powroty_k2_1021.md`, 136/136 |
| Rozłączenie | ekran logowania → zero klawiszy, powiadomienie, wznowienie | `SPEC_rozlaczenie_1021.md`, 52/52 |
| Lina przed startem | trasa przy znanej linie bez liny w pamięci = bot nie rusza | `liny.py`, `test_lina_start` 16/16 |
| Start na spocie bez dojścia | restart nie mija rannych mobów | `test_dojscie_pomin` 7/7 |
| Dojście z depo Edronu (z8) | `dojscie_z_dowolnego_pietra` dla map Edronu | `mapy.json` |
| Rytm skanu | zmierzony jako szkodliwy (pętla −25…−37%), cofnięty | `SPEC_skan_walka_spokoj_1021.md` |

## Nadzorca (zbudowany, na żywo jeszcze NIE działa)

- **Elementy:**
  - `zaloguj.sh` / `wyloguj.sh` / `logowanie.py stan-ekranu`: zalogowanie sprawdzone na żywo 17:02 (Kolanosh, ~24 s), wylogowanie jeszcze nie;
  - `grafik.py`, `nadzor.py`, `NADZORCA.md`;
  - serwis Thais (depo + Gorn), bez jedzenia i blanków, bo sklepy są za drzwiami.
- **Decyzje Karola:**
  - 5 online, Karol dołoży konta;
  - hunt 2–3 h, przerwa 30–120 min, limit 8 h/dzień, cisza 01–08;
  - cała biała lista napraw bez pytania;
  - nadzorca wybiera i miesza spoty (Q5).
- **Brakuje:**
  - wybór spotu (Q5): tabela spotów, poziom, jeden bot na spot, wymagania ekwipunku (lina);
  - serwis Rook i jedzenie/blanki w Thais (K3b);
  - test wylogowania na żywo.
- **Uruchomienie:**
  1. Timer systemd użytkownika `retronic-nadzor` co 60 s w cieniu, czyli tylko log „co bym zrobił”.
  2. Przegląd logu `instancje/_wspolne/logi/nadzor-RRRRMMDD.jsonl`.
  3. `NADZOR_ZYWO` na jednej postaci, pełny cykl.
  4. Reszta zestawu.
  - Pauza w każdej chwili: `instancje/_wspolne/NADZOR_PAUZA`.

## Znane problemy, jeszcze do naprawy (z `AUDYT_1021.md`)

- Dojście poddaje się, gdy pole pod kratką jest zajęte. Bot czeka na samego siebie („stoi gracz Invincible”).
- Zwłoki odłożone („najpierw walka”) giną 2–4× częściej; kolejność lootu dopiero po tej naprawie.
- Wydra: plecak „slot_ukryty” (12:07, loot martwy). Wymaga rozciągnięcia okna, kod 1.3 w audycie.
- Ucieczka PK przez trolle blokujące drogę: dawajkesh 16:12, 4 × 8 s bicia. Decyzja bezpieczeństwa do Karola.
- Invincible bez leczenia w grupach trolli, `SMIERC_STOP`=0 (etap 3 audytu, decyzje Karola).
- Pętla bota nadal ~15% wolniejsza niż rano (2,4–2,8 obiegu/s wobec 3,0–3,4/s). Przyczyna nieustalona: wiek procesów albo obciążenie.
- `[OGIEN] nie wczytam maski stałych pól` (AttributeError mapa) przy starcie u wszystkich, od rana. Dane ognia z epizodów działają.

## Bober

Zgonu w logach brak (reset serwera o 10:00). Sygnały „to bot”: pytanie „bot?” bez odpowiedzi i 16,5 min stania (20.10), brak odpowiedzi na czat,
długie sesje całej floty. `dane_tibia/ruch/DIAGNOZA_bober_smierc_sygnaly_bota_1021.md`.
