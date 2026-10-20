"""Stały profil instancji (SPEC dane_tibia/SPEC_tozsamosc_sprzetu_1020.md, rozszerzenie (b)).

<katalog stanu instancji>/profil.json, bez haseł:
  {"proxy": {"host": "p.webshare.io", "port": 80, "user": "evitnvfx-5"},
   "ip_oczekiwane": ["84.247.60.125"], "konto": "...", "postac": "..."}
Hasło proxy: keyring service=retronic-proxy instance=<id> (haslo_proxy.sh <id>).
Zasady: instancja bez profilu nie startuje; dwie instancje nie mogą dzielić endpointu proxy ani żadnego IP.
Konto (decyzja Karola 20.10: konto przypisane na stałe do IP i sprzętu instancji): dwie instancje nie mogą mieć tego
samego `konto`, a gdy klient instancji ma zapisane (config.otml `account:`) inne konto niż profil albo konto innej
instancji, start jest wstrzymany. Puste `konto` = ostrzeżenie; `przypisz` wpisuje do profilu login zapisany w kliencie.
Dla powłoki:
  eval "$(python3 -I profil.py powloka <katalog stanu>)"   # RETRONIC_PROXY_HOST/PORT/USER, SIEC_IP_OCZEKIWANE
  python3 -I profil.py przypisz <katalog stanu>            # konto z klienta -> profil.json (tylko gdy puste)
"""
import json
import re
import shlex
import sys
from pathlib import Path

_IPV4 = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")


class BladProfilu(Exception):
    pass


def wczytaj(katalog):
    plik = Path(katalog) / "profil.json"
    if not plik.exists():
        raise BladProfilu(f"brak {plik}: instancja bez stałego profilu (proxy, IP, konto) nie startuje")
    p = json.loads(plik.read_text())
    proxy = p.get("proxy") or {}
    if not (proxy.get("host") and str(proxy.get("port", "")).isdigit() and proxy.get("user")):
        raise BladProfilu(f"{plik}: proxy wymaga host, port (liczba) i user")
    ips = p.get("ip_oczekiwane") or []
    if not ips or not all(isinstance(i, str) and _IPV4.match(i) for i in ips):
        raise BladProfilu(f"{plik}: ip_oczekiwane musi być niepustą listą adresów IPv4")
    return p


def konto_klienta(katalog):
    """Login zapisany przez klienta gry w prefiksie instancji ("" gdy brak)."""
    for cfg in sorted((Path(katalog) / "prefix").glob("drive_c/users/*/AppData/Roaming/Retronic/Retronic/config.otml")):
        m = re.search(r"(?m)^account:[ \t]*(\S*)[ \t]*$", cfg.read_text(errors="replace"))
        if m:
            return m.group(1)
    return ""


def endpoint(p):
    x = p["proxy"]
    return f"{x['user']}@{x['host']}:{x['port']}"


def sprawdz_unikalnosc(katalog):
    """Profil tej instancji vs profile pozostałych w tym samym katalogu instancji; zwraca profil."""
    katalog = Path(katalog).resolve()
    p = wczytaj(katalog)
    for inny in sorted(katalog.parent.glob("*/profil.json")):
        if inny.parent == katalog:
            continue
        try:
            q = wczytaj(inny.parent)
        except (BladProfilu, ValueError):
            continue
        if endpoint(q) == endpoint(p):
            raise BladProfilu(f"proxy {endpoint(p)} ma już instancja '{inny.parent.name}' (jedno IP = jedna instancja)")
        wspolne = set(p["ip_oczekiwane"]) & set(q["ip_oczekiwane"])
        if wspolne:
            raise BladProfilu(f"IP {', '.join(sorted(wspolne))} ma już instancja '{inny.parent.name}'")
        inne_konto = (q.get("konto") or "").lower()
        if inne_konto and inne_konto in {(p.get("konto") or "").lower(), konto_klienta(katalog).lower()}:
            raise BladProfilu(f"konto przypisane do instancji '{inny.parent.name}' (jedno konto = jedno IP i sprzęt)")
    konto, w_kliencie = p.get("konto") or "", konto_klienta(katalog)
    if konto and w_kliencie and w_kliencie.lower() != konto.lower():
        raise BladProfilu("w kliencie zapisane inne konto niż w profil.json (konto przypisane na stałe do instancji)")
    if not konto:
        print("profil: UWAGA puste `konto` w profil.json (po zalogowaniu: profil.py przypisz)", file=sys.stderr)
    return p


def przypisz(katalog):
    """Wpisuje do profil.json konto zapisane w kliencie, gdy profil ma puste; zwraca opis."""
    plik = Path(katalog) / "profil.json"
    p = wczytaj(katalog)
    w_kliencie = konto_klienta(katalog)
    if p.get("konto"):
        return "konto już przypisane" + ("" if not w_kliencie or w_kliencie.lower() == p["konto"].lower() else ", W KLIENCIE INNE")
    if not w_kliencie:
        raise BladProfilu("klient nie ma zapisanego konta (zaloguj się raz)")
    p["konto"] = w_kliencie
    plik.write_text(json.dumps(p, ensure_ascii=False, indent=2) + "\n")
    sprawdz_unikalnosc(katalog)
    return "konto przypisane z klienta"


def ten_sam_host(katalog, host):
    """Instancje (rodzeństwo) z tym samym serwerem proxy: od ich wpisu w keyringu siec_proxy.sh bierze hasło, gdy ta
    instancja nie ma własnego (Webshare: jedno hasło dla wszystkich proxy konta, decyzja Karola 20.10)."""
    katalog = Path(katalog).resolve()
    wynik = []
    for inny in sorted(katalog.parent.glob("*/profil.json")):
        if inny.parent == katalog:
            continue
        try:
            if wczytaj(inny.parent)["proxy"]["host"] == host:
                wynik.append(inny.parent.name)
        except (BladProfilu, ValueError):
            pass
    return wynik


def powloka(p, haslo_z=()):
    x = p["proxy"]
    return "\n".join([
        f"export RETRONIC_PROXY_HASLO_Z={shlex.quote(' '.join(haslo_z))}",
        f"export RETRONIC_PROXY_HOST={shlex.quote(str(x['host']))}",
        f"export RETRONIC_PROXY_PORT={shlex.quote(str(x['port']))}",
        f"export RETRONIC_PROXY_USER={shlex.quote(str(x['user']))}",
        f"export SIEC_IP_OCZEKIWANE={shlex.quote(' '.join(p['ip_oczekiwane']))}",
    ])


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("powloka", "przypisz"):
        print("użycie: profil.py powloka|przypisz <katalog stanu instancji>", file=sys.stderr)
        sys.exit(2)
    try:
        if sys.argv[1] == "powloka":
            p = sprawdz_unikalnosc(sys.argv[2])
            print(powloka(p, ten_sam_host(sys.argv[2], p["proxy"]["host"])))
        else:
            print(przypisz(sys.argv[2]))
    except (BladProfilu, ValueError) as e:
        print(f"profil: {e}", file=sys.stderr)
        sys.exit(1)
