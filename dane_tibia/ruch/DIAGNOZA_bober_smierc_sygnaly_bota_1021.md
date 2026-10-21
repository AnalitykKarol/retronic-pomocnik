# DIAGNOZA: bober („Bober Qrwa”), zgłoszona śmierć 21.10 ok. 10:00. Co mogło zdradzić bota? (tylko odczyt)

Pytanie Karola: bober zginął dziś koło 10. Co mogło sprawić, że gracze uznali go za bota?
- Źródła: `instancje/_archiwum/bober-20261021/logi/` (telemetria, mozg-stdout, ratunek) i `gra/Retronic.log`.
- Skrypty agenta leżą w scratchpadzie sesji (`bober/an1-3.py`).

## Fakt śmierci: logi go nie potwierdzają

- **10:00:01 reset serwera.** Wszystkie 6 postaci Karola mają w `Retronic.log` wpis `Minimap saved` o tej samej sekundzie. Przyczyną jest reset serwera, nie śmierć (STAN.md:26).
- **Przed 10:00 nikogo nie było.** Między 07:34 a 10:00 telemetria nie pokazuje żadnego innego gracza w widoku. HP wynosiło 98–99%, ostatni Cave Rat padł 10:00:02 na (32037,32226,z9).
- **10:00:12–10:05:11 bot jeździł po wylogowanym kliencie.**
  - Bot nadal klikał strzałki, ratunek S3/S5, bo pamięć klienta stała na ostatnim stanie (HP 99).
  - Zrzut `logi/slepota/20261021-100201.png` pokazuje „Character List”.
  - Bot zakończył się sam: „Trzy punkty z rzędu nieosiągalne”.
- **Logowania po resecie:** 10:09:16, 10:13:08 → 10:15:47 i 10:18:59 → 10:19:02.
  - Między 10:05 a 10:33 nie ma telemetrii, bo bot nie działał.
  - **Jeśli była śmierć, to najpewniej tutaj (HIPOTEZA): 10:09–10:33.** Wylogowanie o 10:13:08 może być śmiercią.
- **10:33:50 restart bota:** HP 99%, a do 11:18 HP ≥ 96%, bez graczy w widoku.
- **11:18:24 wylogowanie przy HP 100%.** Logowanie o 11:18:28 się nie udało (ekran „Enter Game”). Bot znowu przez 6 minut klikał po martwym kliencie.

## Sygnały „to bot” (20.10, wtedy byli gracze obok)

1. **MOCNY: pytanie bez odpowiedzi.**
   - 20.10 20:36:16 Trikin zapytał „bot?” (`mozg-20261020-2027.log:580`).
   - Zadziałał `ALARM_GM`, a bot wszedł w `PAUZA do odwołania` (mozg.py:3306-3327, `wstrzymaj(inf)`).
   - Postać stała bez ruchu i bez odpowiedzi 16,5 minuty, do ręcznego restartu o 20:52:49. Szczury obok porzucała.
2. **MOCNY: nigdy nie odpowiada na czat.**
   - Tryb `skrypt` nie ma modelu (mozg.py:2277). Czat jest czytany tylko pod alarm GM.
   - Wiadomości od obcych nie są nigdzie zapisywane, więc nie wiadomo, co pisali inni gracze.
3. **ŚREDNI: długie sesje całej floty naraz.**
   - Bot działał bez przerwy 143 minuty (20.10) i 123 minuty (21.10).
   - Po resecie o 10:00 wszystkie postacie wróciły w ciągu 7 minut (10:09–10:16).
4. **ŚREDNI: powtarzalna pętla.**
   - Pętla `rook_cave_raty_z9_glab` trwa około 8 minut. Najczęstsze pola bot odwiedzał 12–14 razy w ciągu 2 godzin.
   - W każdym okrążeniu zmienia kierunek: „Następne okrążenie w drugą stronę”, 149 razy.
5. **ŚREDNI: dreptanie i zacięcia przy graczach.**
   - 20.10 20:27–20:36 bot spędził 9 minut na złym piętrze (z8 zamiast z9), wysyłając kroki „nie ruszył”.
   - W tym czasie obok przechodził Muratov (odległość 1).
   - `utkniecie` 14 razy (20.10) i około 20 razy w grze (21.10).
6. **SŁABY–ŚREDNI: kilka niskopoziomowych botów w jednej jaskini.**
   - Kolanosh był w widoku bobra w 290 próbkach, Wydra w 163.
   - Gracz Stopy Skolima był w widoku 134 próbki, raz z odległości 0–1, a bot „gra dalej”.
7. **SŁABY: czasy reakcji.** Pierwszy krok pościgu: mediana 0,21 s; 39 z 980 krótszych niż 0,1 s.

Wcześniejszych ataków PK ani czaszek przy bobrze w logach nie ma.

## Rekomendacje (do decyzji Karola; [BEZP] = bezpieczeństwo postaci lub ryzyko bana)

1. **[BEZP] Ekran logowania lub wyboru postaci:** natychmiast STOP i żadnych klawiszy. `SMIERC_STOP` tu nie zadziała, bo pamięć stoi. Ten sam problem miał kutangen (STAN.md:28).
2. **Zapis czatu od obcych w telemetrii,** także w trybie skrypt.
3. **[BEZP] Limit `ALARM_GM`:** 2–3 minuty zamiast stania „do odwołania”. Potem krótka odpowiedź z puli albo spokojne wylogowanie.
4. **[BEZP] Rozłożone sesje:**
   - przerwy co 60–90 minut,
   - różne godziny startu postaci,
   - po resecie serwera bez powrotu wszystkich w ciągu kilku minut.
5. **[BEZP] Nie więcej niż jeden bot na jaskinię i spot.**
6. **[BEZP] Sprawdzenie piętra przed startem,** żeby bot nie dreptał przy graczach.

## Czego nie ustalono

- Czy i kiedy bober zginął, i kto go zabił. Potrzebny komunikat śmierci z gry albo „latest deaths” na stronie postaci.
- Co działo się 10:05–10:33 (bot nie działał; może Karol grał ręcznie).
- Co pisali gracze poza pytaniem Trikina, bo czatu od obcych nikt nie zapisuje.
- Dlaczego o 11:18–11:19 wylogowały się 3 postacie i nie udało się ponowne logowanie.
