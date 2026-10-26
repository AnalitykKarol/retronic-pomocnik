#!/bin/bash
# Zaloguj postać instancji BEZ startu bota (okno zarządzania, akcja „Zaloguj postać", Karol 24.10: „nie odpalaj całego bota,
# tylko loguj same postacie"). Użycie: RETRONIC_ID=<id> ./zaloguj_postac.sh   albo   ./zaloguj_postac.sh <id>
#
# Kroki:
#   1. odmowa dla postaci straconej (profil.json `stracony`) i gdy trwa INNE logowanie (jedno naraz, także cudze: `logowanie.py
#      zaloguj|wyloguj` innej instancji; blokada flock `$XDG_RUNTIME_DIR/retronic-zaloguj.lock` obejmuje cały przebieg tego skryptu);
#   2. sesja gry nie działa -> `sesja_gry.py start` (TA SAMA droga co guzik „Uruchom grę" w oknie: profil, RETRONIC_POSTAC z profilu,
#      port podglądu wybiera sesja.sh sama, bez kolizji; otwiera też podgląd Remmina) i czekanie do 60 s na linię
#      `siec_proxy: IP wyjściowe … (zgodne z profilem)` (okno_api.py sesja -> ip.zgodne). IP spoza profilu albo brak potwierdzenia
#      = przerwanie BEZ logowania (to samo sprawdzenie robimy, gdy sesja już stała);
#   3. `zaloguj.sh --reczny-ok` (klik w oknie = świadoma decyzja Karola; kliki myszą Login i Ok, ZERO klawiszy, nic nie kliknie na
#      ekranie gry). Kod wyjścia zaloguj.sh idzie dalej bez zmian.
# NIE robi: nie usuwa STOP ani STOP_RECZNY, nie uruchamia uruchom.sh/mozg.py, nie zmienia profilu, planu ani mapy.
#
# Kody wyjścia: 0 zalogowano (albo już w grze) · 1 limit/porażka · 3 brak sesji · 4 ręczna gra · 6 zgon · 7 ekran nierozpoznany ·
# 9 zalogowano inną postać (kody 1-9 = zaloguj.sh) · 20 złe użycie · 21 postać stracona · 22 inne logowanie trwa ·
# 23 start sesji nie powiódł się · 24 IP spoza profilu albo sesja padła przed potwierdzeniem IP · 25 brak potwierdzenia IP w limicie.
# Ostatnia linia wyjścia = jedno zdanie po polsku (okno pokazuje ją Karolowi). Log logowania: instancje/<id>/logi/logowanie.log.
# Cofnięcie: ./wyloguj.sh (wylogowanie) i `sesja_gry.py zamknij` (zamknięcie gry); sam skrypt nic trwałego nie zmienia.
# Zmienne (testy): RETRONIC_ZALOGUJ_IP_LIMIT_S (60), RETRONIC_OKNO_PROC (atrapa /proc), XDG_RUNTIME_DIR.
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
ID="${1:-${RETRONIC_ID:-}}"
IP_LIMIT_S="${RETRONIC_ZALOGUJ_IP_LIMIT_S:-60}"
KROK_S="${RETRONIC_ZALOGUJ_KROK_S:-2}"

koniec() {   # $1 = kod, $2 = zdanie dla człowieka
  echo "$2"
  exit "$1"
}

if ! [[ "$ID" =~ ^[a-z0-9][a-z0-9_-]{0,23}$ ]]; then
  koniec 20 "Zaloguj postać: potrzebne ID instancji (główna instancja loguje się ręcznie)"
fi
export RETRONIC_ID="$ID"
cd "$DIR" || koniec 20 "Zaloguj postać: brak katalogu pomocnika"

# ---- 1. blokada: jedno logowanie naraz
ZAMEK="${XDG_RUNTIME_DIR:-/tmp}/retronic-zaloguj.lock"
exec 9>"$ZAMEK" || koniec 20 "Zaloguj postać: nie mogę otworzyć blokady $ZAMEK"
flock -n 9 || koniec 22 "Trwa już inne logowanie z okna (jedno naraz): poczekaj, aż skończy"

# inne logowanie spoza okna (nadzorca, ręcznie `zaloguj.sh`): proces logowanie.py zaloguj|wyloguj innej instancji
inne=$(python3 -I - "$ID" <<'PY'
import os, sys
moje = sys.argv[1]
proc = os.environ.get("RETRONIC_OKNO_PROC") or "/proc"
for w in os.listdir(proc):
    if not w.isdigit() or int(w) == os.getpid():
        continue
    try:
        argv = [x.decode(errors="replace") for x in open(f"{proc}/{w}/cmdline", "rb").read().split(b"\0") if x]
        if not any(a.endswith("logowanie.py") for a in argv[:3]) or not any(a in ("zaloguj", "wyloguj") for a in argv[1:4]):
            continue
        env = open(f"{proc}/{w}/environ", "rb").read().split(b"\0")
    except OSError:
        continue
    id_ = next((e[12:].decode(errors="replace") for e in env if e.startswith(b"RETRONIC_ID=")), "")
    if id_ != moje:
        print(id_ or "główna")
        break
PY
)
[ -z "$inne" ] || koniec 22 "Trwa logowanie innej postaci ($inne): jedno naraz, poczekaj, aż skończy"

# ---- postać stracona: bez żadnych działań
eval "$(python3 -I "$DIR/instancja.py" powloka 2>/dev/null)"
if [ -n "${INST_STAN:-}" ] && python3 -I - "$INST_STAN/profil.json" <<'PY'
import json, sys
try:
    sys.exit(0 if json.load(open(sys.argv[1])).get("stracony") else 1)
except (OSError, ValueError, AttributeError):
    sys.exit(1)
PY
then
  koniec 21 "Postać $ID jest stracona (profil `stracony`): nie loguję"
fi

odczyt() {   # -> "<sesja: tak|nie|blad> <ip: zgodne|spoza|brak>"
  python3 -I "$DIR/okno_api.py" sesja --instancja "$ID" 2>/dev/null | python3 -I -c '
import json, sys
try:
    d = json.load(sys.stdin)
except ValueError:
    print("blad brak"); sys.exit()
zyje = bool(d.get("sesja") or d.get("klient_pids") or d.get("proxy_pids") or d.get("sesja_sh_pids"))
ip = d.get("ip")
print(("tak" if zyje else "nie"), ("brak" if not ip else ("zgodne" if ip.get("zgodne") else "spoza")))
'
}

# ---- 2. sesja gry (gdy nie działa) i potwierdzenie IP
read -r zyje ip <<< "$(odczyt)"
if [ "$zyje" != "tak" ]; then
  wyj=$(python3 -I "$DIR/sesja_gry.py" start 9>&- 2>&1 < /dev/null); kod=$?
  [ "$kod" = 0 ] || koniec 23 "Start sesji nie powiódł się: $(printf '%s' "$wyj" | tail -n 1)"
fi

t0=$SECONDS
while :; do
  read -r zyje ip <<< "$(odczyt)"
  [ "$ip" = "zgodne" ] && [ "$zyje" = "tak" ] && break
  [ "$ip" = "spoza" ] && koniec 24 "IP wyjściowe SPOZA profilu: nie loguję. Zamknij grę (Sesja gry) i sprawdź proxy w profilu"
  if [ "$zyje" = "nie" ] && [ $((SECONDS - t0)) -ge 6 ]; then
    koniec 24 "Sesja gry zniknęła przed potwierdzeniem IP: nie loguję (sprawdź log sesji)"
  fi
  [ $((SECONDS - t0)) -lt "$IP_LIMIT_S" ] || koniec 25 "Brak potwierdzenia IP proxy w ${IP_LIMIT_S} s: nie loguję (sprawdź sway.log sesji)"
  sleep "$KROK_S"
done

# ---- 3. logowanie (bez bota)
wyj=$("$DIR/zaloguj.sh" --reczny-ok 9>&- 2>&1 < /dev/null); kod=$?
ost=$(printf '%s\n' "$wyj" | awk 'NF { l = $0 } END { print l }')
case "$kod" in
  0) koniec 0 "Postać zalogowana (albo już była w grze); bot nie został uruchomiony" ;;
  1) koniec 1 "Logowanie nie powiodło się w limicie czasu${ost:+ ($ost)}" ;;
  3) koniec 3 "Brak sesji gry tej instancji (sesja padła w trakcie)" ;;
  4) koniec 4 "Odmowa: ręczna gra (STOP_RECZNY bez bota)" ;;
  6) koniec 6 "Odmowa: postać nie żyje (zgon), żadnych kliknięć" ;;
  7) koniec 7 "Ekran gry nierozpoznany: nic nie kliknięto (sprawdź podgląd)" ;;
  9) koniec 9 "Zalogowano INNĄ postać niż w profilu: sprawdź podgląd" ;;
  *) koniec "$kod" "Logowanie zakończone kodem $kod${ost:+ ($ost)}" ;;
esac
