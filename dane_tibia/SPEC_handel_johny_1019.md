# SPEC: handel na Johny Dang (instancja `test`) — obserwacja rynku, szkice wiadomości, okienka

Status: DRAFT (19.10, czeka na akcept Karola)
Instancja: `RETRONIC_ID=test`, postać `Johny Dang` (lvl 8, stoi w mieście, bez bota ruchu).

## Cel

Johny pilnuje kanału Trade i prywatnych wiadomości:
- sprzedaje UH (runy dowozi Karol z głównej postaci, Johny ich teraz nie ma),
- kupuje **knight axe ≤ 3500 gp** i **dwarven shield ≤ 200 gp** (cena za sztukę),
- sam przygotowuje wiadomość do gracza (otwiera rozmowę, wpisuje tekst), **wysyła zawsze Karol Enterem**,
- daje znać okienkiem (`notify-send`), gdy ktoś pisze na priv albo pojawia się okazja.

Bot nigdy sam nie naciska Enter po swoim tekście.

## Stan na 19.10 16:16 (zmierzone)

- Gniazdo `retronic-test.sock` odpowiada; `gracz`: lvl 8, cap 219; `kontenery`: pusty backpack (0 UH).
- Na priv pisał Malik (15:50: „2k? uh? thais?”, „i tell when i finish”) — kupiec UH na później.
- Serwer wyrzuca za bezczynność po 30 min (16:15 komunikat, 16:16 ponowne logowanie).
- `trade_logger.py` czyta tylko `retronic-pomocnik.sock` i ma nick `Jointoramix` na sztywno.
- Ceny z `ceny_trade.jsonl` (13–15.10): UH sprzedaż med. 2,5k/BP, kupno 2,2–2,4k/BP; knight axe
  sprzedaż med. 4k (706 ofert); dwarven shield sprzedaż 100–200 gp (19 ofert).

## Fazy

### F1 — obserwacja i okienka (tylko odczyt gry)
- `trade_logger.py`: gniazdo i własny nick z instancji (`RETRONIC_ID` przez `instancja.py`), osobne pliki
  wyników dla `test` (nie mieszać z głównej).
- Nowe alerty: sprzedający knight axe / dwarven shield z ceną ≤ progu albo bez ceny; kupujący UH.
- Okienko przy **każdej nowej wiadomości priv** do Johny'ego (nadawca + treść), z ciszą 60 s na nick.
- Progi i lista przedmiotów w pliku konfiguracji (`handel_johny.json`), nie w kodzie.
- Dowód: `--raz --sucho` na żywym gnieździe + testy parsera (KA/DS/UH, priv vs Trade).

### F2 — szkic wiadomości w grze (Karol wysyła Enterem)
- Na zdarzenie z F1 bot otwiera rozmowę z graczem i wpisuje tekst **bez Enter**; okienko:
  „Johny: szkic do <nick> gotowy — Enter w podglądzie”.
- Jeden szkic naraz. Wysłany = własna wiadomość widoczna w `wiadomosci`; niewysłany po 3 min = czyszczenie
  pola i następny z kolejki (porzucone > 10 min).
- Szablony (EN, krótkie, małe litery) w pliku `handel_johny.json`:
  - sprzedawca bez ceny: `hi, how much for knight axe?`
  - sprzedawca w progu: `hi, ill take dwarven shield for {cena}, where r u?`
  - kupiec UH / priv o UH: `hi, uh {cena}k per bp, how many bps? im in {miasto}`
- Te same blokady co ogłoszenia: nie pisze przy obcym graczu blisko, ataku, niskim HP, klawiszu ruchu.

### F3 — bez wyrzucania za bezczynność
- Co 8–14 min (losowo) obrót postaci (Ctrl+strzałka), tylko gdy pole czatu puste i nie ma szkicu.

## Pytania otwarte (decyzja Karola)

- **Q1 — ROZSTRZYGNIĘTE 19.10 (pomiar na żywo).** `*Nick* tekst` na Default wysyła priv (Termos 16:34,
  Typiara 16:52), ale NIE otwiera zakładki — pojawia się dopiero po odpowiedzi rozmówcy. Zakładkę otwiera
  Ctrl+O → okno „Channels” → pole „Open a private message channel” (ok. 470,595 przy ekranie 940x1030) → wpis
  nicka → „Open” (ok. 497,644): nowa zakładka od razu aktywna, w niej Enter-tekst-Enter (test do Jointoramix
  17:09: „Message sent to Jointoramix.”). F2 używa tej drogi. Decyzje: cena UH 2,3k/BP (Termos: 2k/BP za 5 BP,
  ustalone przez Karola), miasto Edron/Thais, F1 zatwierdzona i uruchomiona.
- ~~Q1 — jak otwieramy rozmowę?~~ (a) wpis `*Nick* tekst` na Default: Enter wyśle priv, ale nie wiem, czy
  klient otworzy potem zakładkę (UNKNOWN, do zmierzenia jednym próbnym wpisem bez Enter);
  (b) prawy klik na nick w Trade → „Message to” (otwiera zakładkę, wymaga kalibracji menu). Rekomendacja: (a),
  prostsze i od razu widać adresata w polu.
- **Q2 — cena UH w szkicu:** 2,3k/BP (jak dotychczasowe ogłoszenia) czy inna?
- **Q3 — miasto Johny'ego** do szkiców (Edron? Thais?).
- **Q4 — ogłoszenia na Trade** (WTS UH / WTB KA+DS) też jako szkice do Enter, czy zostają ręczne?

## Poza zakresem

- Automatyczna negocjacja i wysyłka bez Karola.
- Handel przedmiotami (trade window), przekazywanie UH z głównej postaci.
- Zapis czegokolwiek do Notion/Slacka (projekt prywatny).

## Weryfikacja i cofnięcie

- F1: żywy odczyt `test`, okienko przy prawdziwej wiadomości priv. F2: jeden szkic na żywo do gracza
  z prawdziwego alertu, Karol decyduje o Enter. F3: >35 min stania bez komunikatu o bezczynności.
- Cofnięcie: zatrzymanie procesu obserwatora; zmiany w `trade_logger.py` z kopią `*.bak-20261019-johny`.
