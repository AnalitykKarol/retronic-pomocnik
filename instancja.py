"""Instancje pomocnika: jedno miejsce, z którego wszystkie moduły biorą ścieżki i nazwy.

Zmienna RETRONIC_ID (domyślnie pusta) wybiera instancję. Pusta = dzisiejsze zachowanie, dokładnie te same
ścieżki i nazwy (socket retronic-pomocnik.sock, pliki w katalogu pomocnika, logi/, prefix ../prefix).
Niepusta (np. "dwa") = osobny świat:

  socket            $XDG_RUNTIME_DIR/retronic-<id>.sock
  katalog stanu     pomocnik/instancje/<id>/   (na_zywo.json, uh_stan.json, STOP, STOP_RECZNY, logi/, tryb.log, ...)
  WINEPREFIX        pomocnik/instancje/<id>/prefix
  katalog gry       pomocnik/instancje/<id>/gra   (kopie exe/dll; tu ląduje Retronic.log klienta)
  sesja sway        $XDG_RUNTIME_DIR/retronic-sesja-<id>/   (wayland, swaysock, sway.conf, sway.log)
  wspólne           pomocnik/instancje/_wspolne/   (zajete.json: rezerwacje miejsc, patrz miejsca_koord.py)

Moduł nie ma efektów ubocznych przy imporcie (nie tworzy katalogów). Dla powłoki:
  eval "$(python3 -I instancja.py powloka)"      # eksportuje INST_* i RETRONIC_ID
  python3 -I instancja.py pidy '(mozg|cavebot)\\.py'   # pidy procesów python tej instancji
  python3 -I instancja.py pidy-skrypt '^(\\S*/)?bash (\\S*/)?refill\\.sh *$'   # j.w., ale dowolny proces (skrypty powłoki)
"""
import os
import re
import shlex
import sys
from pathlib import Path
from types import SimpleNamespace

KATALOG = Path(__file__).resolve().parent
GRA = KATALOG.parent                      # ~/Games/Retronic (exe, prefix, Retronic.log)
_WZOR_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,23}$")


def sprawdz_id(wartosc):
    """Zwraca znormalizowane ID ('' = domyślna instancja); ValueError dla niedozwolonych znaków."""
    v = (wartosc or "").strip()
    if v and not _WZOR_ID.match(v):
        raise ValueError(f"niepoprawne RETRONIC_ID {v!r}: małe litery, cyfry, '-' i '_' (1-24 znaki, zaczyna się od litery/cyfry)")
    return v


def runtime(zapas="/tmp", env=None):
    return (env if env is not None else os.environ).get("XDG_RUNTIME_DIR") or zapas


def sciezki(id_="", runtime_dir="/tmp", katalog=KATALOG, gra=GRA):
    """Czysta funkcja: komplet ścieżek instancji. Dla id_ == '' zwraca dzisiejsze ścieżki."""
    id_ = sprawdz_id(id_)
    katalog, gra, rt = Path(katalog), Path(gra), Path(runtime_dir)
    if id_:
        stan = katalog / "instancje" / id_
        s = dict(gniazdo=rt / f"retronic-{id_}.sock", sesja=rt / f"retronic-sesja-{id_}",
                 prefix=stan / "prefix", gra=stan / "gra", log_klienta=stan / "gra" / "Retronic.log")
    else:
        stan = katalog
        s = dict(gniazdo=rt / "retronic-pomocnik.sock", sesja=rt / "retronic-sesja",
                 prefix=gra / "prefix", gra=gra, log_klienta=gra / "Retronic.log")
    s.update(id=id_, stan=stan, logi=stan / "logi", na_zywo=stan / "na_zywo.json", uh_stan=stan / "uh_stan.json",
             stop=stan / "STOP", stop_reczny=stan / "STOP_RECZNY", stop_nagrywania=stan / "STOP_NAGRYWANIA",
             stop_leczenie=stan / "STOP_LECZENIE", tryb_log=stan / "logi" / "tryb.log",
             uciekanie=stan / "uciekanie.json", pamiec_mozgu=stan / "mozg_pamiec.json",
             straznik_log=stan / "straznik.log", wspolne=katalog / "instancje" / "_wspolne",
             katalog=katalog)
    s["zajete"] = s["wspolne"] / "zajete.json"
    return SimpleNamespace(**s)


ID = sprawdz_id(os.environ.get("RETRONIC_ID", ""))
S = sciezki(ID, runtime("/tmp"))


def gniazdo(zapas="/tmp"):
    """Socket tej instancji; zapas = katalog, gdy brak XDG_RUNTIME_DIR (moduły różnią się dziś: /tmp albo /run/user/UID)."""
    return sciezki(ID, runtime(zapas)).gniazdo


def sesja(zapas="/tmp"):
    return sciezki(ID, runtime(zapas)).sesja


def srodowisko(id_=None, bazowe=None):
    """Zmienne środowiska dla procesów tej instancji (gra, bot): RETRONIC_ID i, dla niepustego, WINEPREFIX."""
    i = ID if id_ is None else sprawdz_id(id_)
    env = dict(os.environ if bazowe is None else bazowe)
    if i:
        s = sciezki(i, runtime("/tmp", env))
        env["RETRONIC_ID"] = i
        env["WINEPREFIX"] = str(s.prefix)
    else:
        env.pop("RETRONIC_ID", None)
    return env


# --- identyfikacja procesów po RETRONIC_ID w /proc/<pid>/environ ----------------------------------

def id_z_environ(surowe):
    """surowe: bajty z /proc/<pid>/environ albo lista wpisów (bytes). -> ID ('' gdy brak zmiennej)."""
    wpisy = surowe.split(b"\0") if isinstance(surowe, (bytes, bytearray)) else surowe
    for w in wpisy:
        if w.startswith(b"RETRONIC_ID="):
            return w[12:].decode(errors="replace").strip()
    return ""


def id_procesu(pid):
    """RETRONIC_ID procesu; None, gdy nie da się odczytać (inny użytkownik, proces zniknął)."""
    try:
        return id_z_environ(Path(f"/proc/{pid}/environ").read_bytes())
    except OSError:
        return None


def nalezy(pid, id_=None):
    """Czy proces należy do instancji id_ (domyślnie bieżącej). Nieczytelne środowisko = nie."""
    return id_procesu(pid) == (ID if id_ is None else id_)


def procesy(wzor, id_=None, proc="/proc", comm=("python", "python3")):
    """Pidy procesów python (comm python/python3), których cmdline (spacje zamiast NUL) pasuje do wzoru
    (re.search), z RETRONIC_ID == id_. Odpowiednik pętli pgrep+grep -E ze skryptów, ale per instancja.
    comm=None: bez filtra nazwy procesu (skrypty powłoki, np. refill.sh: comm to "bash" albo nazwa skryptu)."""
    cel = ID if id_ is None else sprawdz_id(id_)
    rx = re.compile(wzor)
    moj = os.getpid()
    wynik = []
    try:
        wpisy = os.listdir(proc)
    except OSError:
        return wynik
    for w in wpisy:
        if not w.isdigit() or int(w) == moj:
            continue
        try:
            nazwa_procesu = Path(f"{proc}/{w}/comm").read_text().strip()
            if comm is not None and nazwa_procesu not in comm:
                continue
            cmd = Path(f"{proc}/{w}/cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
            if not rx.search(cmd):
                continue
            if id_z_environ(Path(f"{proc}/{w}/environ").read_bytes()) != cel:
                continue
        except OSError:
            continue
        wynik.append(int(w))
    return sorted(wynik)


# --- podgląd VNC: czy ktoś jest podłączony do wayvnc sesji ------------------------------------------

def port_nasluchuje(port, proc="/proc"):
    """Czy ktoś słucha na 127.0.0.1:<port> (wayvnc sesji gotowy na podgląd): /proc/net/tcp, stan 0A = LISTEN."""
    cel = f"{int(port):04X}"
    try:
        linie = Path(f"{proc}/net/tcp").read_text().splitlines()[1:]
    except (OSError, ValueError):
        return False
    for l in linie:
        p = l.split()
        if len(p) > 3 and p[3] == "0A" and p[1].split(":")[-1] == cel and p[1].split(":")[0] in ("0100007F", "00000000"):
            return True
    return False


def podglad_polaczony(port, proc="/proc"):
    """Czy jest NAWIĄZANE połączenie TCP z 127.0.0.1:<port> (wayvnc sesji). Działa dla każdej przeglądarki VNC
    (Remmina, vncviewer), bez szukania procesu: /proc/net/tcp, stan 01 = ESTABLISHED, port lokalny = port wayvnc."""
    cel = f"0100007F:{int(port):04X}"
    try:
        linie = Path(f"{proc}/net/tcp").read_text().splitlines()[1:]
    except (OSError, ValueError):
        return False
    for l in linie:
        p = l.split()
        if len(p) > 3 and p[1] == cel and p[3] == "01":
            return True
    return False


# --- CLI dla skryptów powłoki ---------------------------------------------------------------------

def _powloka(s):
    pary = [("RETRONIC_ID", s.id), ("INST_STAN", s.stan), ("INST_LOGI", s.logi), ("INST_SOCK", s.gniazdo),
            ("INST_SESJA", s.sesja), ("INST_PREFIX", s.prefix), ("INST_GRA", s.gra),
            ("INST_STOP", s.stop), ("INST_STOP_RECZNY", s.stop_reczny), ("INST_STOP_NAGRYWANIA", s.stop_nagrywania),
            ("INST_NA_ZYWO", s.na_zywo), ("INST_LOG_KLIENTA", s.log_klienta), ("INST_WSPOLNE", s.wspolne)]
    return "\n".join(f"export {k}={shlex.quote(str(v))}" for k, v in pary)


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    try:
        if a[0] == "powloka":
            # w powłoce brak XDG_RUNTIME_DIR to /run/user/UID (jak w dotychczasowych skryptach)
            print(_powloka(sciezki(ID, runtime(f"/run/user/{os.getuid()}"))))
            return 0
        if a[0] in ("pidy", "pidy-skrypt") and len(a) == 2:
            for p in procesy(a[1], comm=None if a[0] == "pidy-skrypt" else ("python", "python3")):
                print(p)
            return 0
        if a[0] == "sciezka" and len(a) == 2 and hasattr(S, a[1]):
            print(getattr(S, a[1]))
            return 0
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    print("użycie: instancja.py powloka | pidy REGEX | pidy-skrypt REGEX | sciezka KLUCZ", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
