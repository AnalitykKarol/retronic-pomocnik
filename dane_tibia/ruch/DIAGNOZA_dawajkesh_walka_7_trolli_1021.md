# DIAGNOZA: dawajkesh, walka z 7 trollami w Edronie, 21.10 12:52:28–12:54:35 (tylko odczyt)

Zgłoszenie Karola ~12:56: „przeanalizuj ostatnią walkę z wieloma potworami dawajkesha”. Postać lvl 8, HP 185, mana 35, `trolle_edron`,
tryb `ostrozny,ml`, `ML_CZAR_W_WALCE`=1, `ZDROWIE_CZAR_HP`=80, próg ucieczki 30%. Źródła: `instancje/dawajkesh/logi/telemetria-20261021.jsonl`,
`mozg-stdout-1021-1240.log`.

## Przebieg

- 12:52:15 `ml_czar` utevo lux: mana 22 → 3 (19 wydane), HP 100%, spokój.
- 12:52:28 w widoku 4 trolle (odl. 5–6); 12:52:29 pościg do pierwszego, 12:52:32 walka. Do 12:52:45 w widoku 7 trolli, 6 na polach obok.
- HP: 100% (12:52:35) → 75% (12:53:00) → 50% (12:53:22) → 42% (12:53:36), dalej 42–44% do 12:54:27.
- Leczenie: pierwsza `exura` 12:54:27 przy HP 44% i manie 25 (koszt exury 25). Od 12:52:40 HP < 80% (próg leczenia), ale mana 3→25 rosła ~1 pkt/5 s.
- Cele: 12:52:45, 12:53:00, 12:53:14, 12:53:26 „Zmiana celu: Troll stoi obok, Troll jest 2 pól dalej” → porzucone trolle z HP 6%, 18%, 20% (uciekały 1 pole).
  Wynik 11 epizodów: 5 zabitych, 4 porzucone („zmiana celu na świeżego”), 2 zgubione („zniknął z widoku żywy”: 4% i 16–18%).
  Pierwsze zabicie dopiero 12:53:40 (71 s walki); obrażenia rozłożone na 4 trolle naraz.
- Loot: 5× „Loot odłożony … najpierw walka”, potem 1 loot w walce ok (12:54:31), 1 loot po walce ok.

## Mechanizm (potwierdzony danymi)

1. **Mana na ML tuż przed walką**: przy puli 35 jeden utevo lux (19–20) zostawia < 25 = brak exury przez ~2 min. `ML_BLOK_HP` (80) blokuje ML
   tylko przy niskim HP w walce; w spokoju przed pullem nic nie trzyma rezerwy na exurę. Pokrętła rezerwy many dla leczenia brak.
2. **Zmiana celu na świeżego trolla obok** porzuca ranne uciekające trolle (6–20% HP) — exp traci się, a walka się wydłuża; pościg
   za uciekającym nie startuje, bo reguła woli moba obok.
3. Bot wszedł w grupę 4+ trolli na lvl 8 (brak limitu liczby mobów przy wyborze celu/podejściu — niesprawdzone w kodzie).

## Czego nie ustalono

- Czy reguła „świeży obok” ma pokrętło progu HP celu (kod niesprawdzony).
- Czy zmniejszenie liczby skanów stworów (commit `1705fd9`, 20.10 19:04) wpływa na pościg/loot — pomiar przerwany na rzecz tej analizy.

## 21.10 13:34: dawajkesh minął trolla z 30% HP (zgłoszenie Karola ~13:35)

- 13:34:10 restart bota przy wdrożeniu `SKAN_WIEK_*` (moja zmiana) → `Dojście: trasa edron_depo_trolle`, `Start: trasa 1 pkt` → `[IDZ] punkt 0/1` do ~13:34:40.
  Dojście (`CavebotDojscie`) z założenia biegnie bez walki i lootu, więc troll z 30% HP 1–6 pól obok (13:34:11–13:34:22, (0,-1) o 13:34:17) został pominięty.
  Postać już była na spocie (33094,31753), a dojście prowadziło do jego końca ~25 pól dalej.
- ML: o 13:33:06 druga sesja (admin) przywróciła `ML_CZAR_AKTYWNY`=1 (kopia `na_zywo.json.bak-20261021-ml`); `ML_CZAR_W_WALCE` zostało 0.
  Utevo lux 13:34:28 (mana 43) i 13:34:32 (mana 24). Moje wyłączenie z 12:59 nadpisane — sprzeczne polecenia dwóch sesji.
- Do poprawki (spec): restart bota na spocie nie powinien uruchamiać dojścia (albo dojście powinno dobijać ranne moby obok).
