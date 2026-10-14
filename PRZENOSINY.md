# Przenosiny na nową maszynę (desktop)

1. `mkdir -p ~/Games/Retronic && cd ~/Games/Retronic && git clone <repo> pomocnik`
2. `~/Games/Retronic/pomocnik/instaluj.sh` (zależności, klient z `klient/`, prefix wine, testy).
3. **Nie ma w repo**: konta/hasła (zaloguj się ręcznie w kliencie), `na_zywo.json` (pokrętła; wzór w `na_zywo.przyklad.json`),
   `logi/`, `instancje/`, prefix wine, katalog danych klienta (`AppData/Roaming/Retronic`: układ okien, hotkeye, minimapa).
   Układ okien i hotkeye można skopiować z laptopa: `rsync -a laptop:~/Games/Retronic/prefix/drive_c/users/*/AppData/Roaming/Retronic ...`
   (uwaga: `config.otml` zawiera konto i hasło, nie wrzucaj go do repo).
4. Skróty zakładają ścieżkę `~/Games/Retronic/pomocnik` i okno gry 734x910 (sesja.sh).
5. Mózg bota (Haiku) woła `claude -p`, więc na desktopie potrzebny jest zalogowany `claude`.
6. Trade logger: `python3 -I trade_logger.py` (read-only, PID w `~/.cache/retronic-trade-logger.pid`).
