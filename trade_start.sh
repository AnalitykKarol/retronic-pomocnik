#!/usr/bin/env bash
# Sklep (ogłoszenia Trade + odpowiedzi priv) na postaci-magazynie instancji <id>: mozg.py --bez-ruchu (postać stoi, nic nie chodzi,
# nie walczy i nie loota; cavebot.tick() nie działa). Instancyjny jak uruchom_instancje.sh: RETRONIC_ID wybiera grę, gniazdo strażnika,
# logi, pliki STOP i na_zywo.json; procesy szukamy po RETRONIC_ID w /proc (nigdy globalny pgrep: nie ruszamy cudzego bota).
# Użycie: ./trade_start.sh <id> [--usun-stop]        np. ./trade_start.sh kutangen --usun-stop
#   STOP / STOP_RECZNY w instancji = ktoś zatrzymał postać ręcznie (STOP_RECZNY = "Karol gra"): bez --usun-stop odmawiamy,
#   z --usun-stop kasujemy oba (jak uruchom.sh). Zgoda na to jest po stronie wywołującego.
# Efekt: pokrętła TRADE_OGLOSZENIA=1 i TRADE_PRIV_ODPOWIEDZI=1 w instancje/<id>/na_zywo.json (trade_sklep.py, kopia pliku),
#   proces mozg.py --bez-ruchu w tle (log: instancje/<id>/logi/mozg-stdout-trade-*.log). Cofnięcie: ./trade_stop.sh <id>.
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
uzycie() { echo "użycie: $0 <id> [--usun-stop]" >&2; exit 2; }
ID="${RETRONIC_ID:-}"; USUN_STOP=0
for a in "$@"; do
  case "$a" in
    --usun-stop) USUN_STOP=1 ;;
    -*) uzycie ;;
    *) ID="$a" ;;
  esac
done
[ -n "$ID" ] || uzycie
[ -d "$DIR/instancje/$ID" ] || { echo "brak instancji '$ID' (instancje/$ID)" >&2; exit 1; }
export RETRONIC_ID="$ID"
INST=$(python3 -I "$DIR/instancja.py" powloka) || exit 1; eval "$INST"      # INST_STAN, INST_LOGI, INST_SOCK, INST_STOP...
cd "$DIR" || exit 1
# nie startujemy drugiego mózgu na tej samej postaci (zwykły bot albo sklep)
p=$(python3 -I "$DIR/instancja.py" pidy '(mozg|cavebot)\.py' | tr '\n' ' ')
[ -z "$p" ] || { echo "Na instancji '$ID' już działa bot (PID $p): nie startuję." >&2; exit 1; }
# STOP / STOP_RECZNY: ktoś zatrzymał postać (ręcznie); kasujemy tylko na wyraźne --usun-stop
if [ -e "$INST_STOP" ] || [ -e "$INST_STOP_RECZNY" ]; then
  if [ "$USUN_STOP" != 1 ]; then
    echo "Instancja '$ID' ma STOP/STOP_RECZNY ($(ls "$INST_STOP" "$INST_STOP_RECZNY" 2>/dev/null | xargs -n1 basename | tr '\n' ' ')): może grać człowiek. Z --usun-stop skasuję oba i wystartuję." >&2
    exit 1
  fi
fi
[ -S "$INST_SOCK" ] || { echo "Gra instancji '$ID' nie działa (brak $INST_SOCK)." >&2; exit 1; }
# nick z profilu instancji (jak uruchom.sh): strażnik pyta o pozycję po nicku
if [ -z "${RETRONIC_POSTAC:-}" ]; then
  RETRONIC_POSTAC=$(python3 -I -c "
import sys,json; sys.path.insert(0,sys.argv[1]); import profil
try: p=profil.wczytaj(sys.argv[2])
except Exception:
    try: p=json.load(open(sys.argv[2]+'/profil.json'))
    except Exception: p={}
print((p.get('postac') or '').strip())" "$DIR" "$INST_STAN" 2>/dev/null)
  export RETRONIC_POSTAC
fi
[ -n "${RETRONIC_POSTAC:-}" ] || { echo "Nie znam nicka postaci instancji '$ID' (profil.json, pole postac)." >&2; exit 1; }
Z=$(python3 -I -c "
import socket,json
s=socket.socket(socket.AF_UNIX);s.settimeout(3);s.connect('$INST_SOCK')
s.sendall(b'{\"cmd\":\"pozycja\",\"nazwa\":\"$RETRONIC_POSTAC\"}\n');p=json.loads(s.recv(400))['pozycja'];print(p['x'],p['y'],p['z'])" 2>/dev/null)
[ -n "$Z" ] || { echo "Strażnik nie widzi postaci '$RETRONIC_POSTAC' (niezalogowana?). Nie startuję." >&2; exit 3; }
# od tego miejsca zmieniamy stan: najpierw pokrętła, potem STOP, na końcu proces
python3 -I "$DIR/trade_sklep.py" wlacz || exit 1
[ "$USUN_STOP" = 1 ] && rm -f "$INST_STOP" "$INST_STOP_RECZNY"
mkdir -p "$INST_LOGI"
LOG="$INST_LOGI/mozg-stdout-trade-$(date +%m%d-%H%M).log"
RETRONIC_TELEMETRIA=1 setsid nohup python3 -I -u mozg.py --tryb skrypt --model haiku --trasa stoj_trade --potwory "Troll,Bear,Swamp Troll,Frost Troll,Rat" --prog-hp 30 --bez-ruchu > "$LOG" 2>&1 < /dev/null &
sleep 3
p=$(python3 -I "$DIR/instancja.py" pidy 'mozg\.py .*--bez-ruchu' | tr '\n' ' ')
if [ -z "$p" ]; then
  echo "mozg --bez-ruchu NIE wystartował (instancja '$ID'). Ogon logu $LOG:" >&2; tail -5 "$LOG" >&2
  python3 -I "$DIR/trade_sklep.py" wylacz >&2
  exit 1
fi
echo "Sklep wystartował: instancja '$ID', postać $RETRONIC_POSTAC na ($Z), PID $p, log $LOG"
