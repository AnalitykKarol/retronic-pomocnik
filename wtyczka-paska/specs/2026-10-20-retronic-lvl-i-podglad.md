Status: approved (Q1-Q3 Karol 20.10 ~18:40) — realizacja od L1
Weight: Light feature (dwa pola w JSON, jeden guzik w pasku i w oknie; bez nowych procesów poza podglądem)
Projekt: Retronic, wtyczka paska `charlie.retronic` + okno zarządzania (`2026-10-19-retronic-okno.md`)

# Level postaci i guzik „Zobacz postać” (pasek + okno)

## TLDR

1. W popupie paska (i w kartach postaci w oknie) brakuje levelu postaci. Dziś wiersz to `HP 170/170  mana 20/20`.
2. Po zamknięciu okna podglądu VNC trudno je otworzyć ponownie (dziś tylko `RETRONIC_ID=<id> ./podglad.sh` z terminala).
   Potrzebny guzik **„Zobacz postać”** przy każdej instancji w pasku i w oknie.

## Stan zmierzony (20.10)

- Level już jest: strażnik na `{"cmd": "gracz"}` zwraca `level` i `procent` (`rdzen.POLA_GRACZA`); `panel.py` pokazuje go w TUI
  (`lvl N (P%)`), ale `panel.py --json` (`json_paska`) wkłada do tooltipa tylko HP i manę. `gracz` jest czytany tylko, gdy gra
  działa i bot działa (`stan()`: `s["dziala"] or s.get("pelny")`) — przy zatrzymanym bocie dziś nie ma też HP.
- Podgląd: `podglad.sh` to długo żyjący proces (vncviewer + `dopasuj_okno.py`), sam sprawdza „już otwarty” po porcie.
  Skrypt akcji paska (`ACTION_SCRIPT`) czeka na koniec skryptu, więc `podglad.sh` trzeba odpalać odłączony. To samo robi
  `sesja_gry.py podglad` z F4a okna (`2026-10-19-retronic-okno.md`, „F4: rozpiska”).

## Zakres

### 1. Level
- `panel.py --json`: nowe OPCJONALNE pola `level`, `level_procent` (z `gracz`), tooltip `HP …  mana …  lvl N (P%)`.
  Stare pola bez zmian (dokładane jak pola guzików z 19.10).
- Pasek (`PanelContent.qml` / `RetronicModel.js`): wiersz `HP 170/170  mana 20/20  lvl 8 (35%)`; brak odczytu = bez części `lvl`.
- Okno: `okno_api.py stan` przenosi pola z panelu do `gracz` (`level`, `level_procent`); karta postaci w pasku bocznym pokazuje `lvl N`.

### 2. „Zobacz postać”
- Akcja `podglad` = `sesja_gry.py podglad` (F4a): odłączony `podglad.sh` z `RETRONIC_ID`; gdy podgląd już otwarty — patrz Q2.
- Pasek (Q1): klik w nick instancji + znacznik stanu podglądu przy nicku; aktywny tylko, gdy
  sesja instancji działa (jest `vnc_port` i słucha wayvnc), inaczej wyszarzony z podpowiedzią „gra nie działa”.
- Okno (Q1): klik w nick na karcie postaci + ten sam znacznik; w sekcji Sesja gry przycisk „Otwórz podgląd” / „Pokaż podgląd” (F4b) = ta sama akcja.
- „Sesja działa” = jest port podglądu (`podglad.port`, `vnc_port` z `sesja.sh`), nie gniazdo strażnika: nick klikalny już w trakcie startu gry.

## Decyzje Karola (20.10 ~18:40)

| Q | Odpowiedź | Co z tego wynika |
|---|---|---|
| Q1 | „po kliknięciu na nick albo coś takiego i niech pokazuje, czy jest otwarte okno, czy nie” | bez czwartego guzika: **klik w nick** otwiera podgląd; przy nicku znacznik stanu podglądu (otwarty / zamknięty / brak gry). W oknie to samo na karcie postaci. Pole `podglad` w `panel.py --json` |
| Q2 | tak | podgląd już otwarty = fokus na jego okno (`hyprctl dispatch focuswindow pid:<vncviewer>`) |
| Q3 | tak | `gracz` czytany zawsze, gdy gra jest (także przy zatrzymanym bocie) |

## Pytania (archiwum, przed decyzją)

- **Q1 Miejsce w pasku:** czwarty guzik w rzędzie (`👁 Podgląd`, rząd robi się ciaśniejszy) czy klikalny nick/ikona przy nicku
  (rząd bez zmian)? Rekomendacja: czwarty guzik — widoczny i spójny z resztą.
- **Q2 Podgląd już otwarty:** guzik ma przenieść fokus na istniejące okno podglądu (Hyprland, po tytule okna vncviewera z portem)
  czy tylko powiedzieć „już otwarty”? Rekomendacja: fokus (to jest właśnie „łatwo znaleźć okno”).
- **Q3 Level przy zatrzymanym bocie:** czytać `gracz` także, gdy gra jest, a bot stoi (jedno zapytanie do strażnika, limit 0,3 s)?
  Wtedy HP/mana/lvl są widoczne też przy zatrzymanej postaci. Rekomendacja: tak.

## Fazy

- **L1 zaplecze:** pola w `panel.py --json` (+ Q3), `okno_api.py stan`, akcja `podglad` (zależy od `sesja_gry.py` z F4a okna).
  Testy: `testy/test_okno_api.py`, test JS modelu paska (nowe pola opcjonalne, brak pola = stary wiersz).
- **L2 UI:** pasek i okno; QA Quickshell offscreen na atrapie + zrzut popupu z prawdziwymi danymi 4 instancji; jedno prawdziwe
  „Zobacz postać” na żywo (otwiera tylko podgląd, gry ani bota nie rusza).

## Postęp (20.10)

- L1 + L2 zrobione (agenci be-dev, fe-dev pasek, fe-dev okno; bez commita): `panel.py --json` (`level`, `level_procent`, `podglad`),
  Q3 z pamięcią nieudanego odczytu (`gracz_brak`, 30 s, tylko przy zatrzymanym bocie), `okno_api.py stan`, fokus podglądu
  (`hyprctl dispatch 'hl.dsp.focus({ window = "pid:N" })'`, składnia Lua Hyprland 0.56, zmierzone), pasek i okno. Checker NITS, poprawki.
- Na żywo: tylko odczyt (level 4 instancji, porty podglądu). Klik w nick i fokus na prawdziwym oknie podglądu: NIEZWERYFIKOWANE (F4c / przy Karolu).

- **Poprawka 20.10 ~19:05 (Karol: „podgląd źle się otwiera, ustaw jak na invincible”):** akcja `podglad` otwierała TigerVNC
  (`podglad.sh` + `dopasuj_okno.py`), a Karol używa okien Remmina (`~/.local/share/remmina/retronic-<id>.remmina`, skalowanie do okna,
  ekran gry stały). Teraz: `remmina --disable-toolbar -c <profil>` (brak profilu = tworzony z wzoru `narzedzia/remmina_podglad.sh`),
  otwarty = fokus po adresie okna (tytuł = `name=` z profilu). „Otwarty” wykrywany po nawiązanym połączeniu z portem wayvnc
  (`instancja.podglad_polaczony`, `/proc/net/tcp`), nie po procesie vncviewer. Na żywo: fokus na okno Remmina invincible, pasek po
  `omarchy restart shell` pokazuje lvl i znaczniki 4/4. Testy: `test_sesja_gry` 55/55, `test_panel_lvl` 33/33.

## Poza zakresem

Exp/h, pasek postępu levelu, skille, osadzanie podglądu w oknie.

## Cofnięcie

Pola są opcjonalne: wycofanie = revert commitów; pasek bez nowych pól działa jak dziś.
