"""Tożsamość sprzętu instancji (SPEC dane_tibia/SPEC_tozsamosc_sprzetu_1020.md).

Plik <katalog stanu instancji>/tozsamosc.json powstaje raz, z losowymi wartościami, i potem się nie zmienia:
  volume_serial  8 cyfr hex -> drive_c/.windows-serial (wine: numer wolumenu C:)
  mac            MAC karty eth0 w sieci instancji (prefiks prawdziwego producenta, D1)
  machine_id     32 cyfry hex -> /etc/machine-id widziane tylko przez grę (wine: UUID płyty, D3)
  uzytkownik     nazwa konta Windows (wine: GetUserName, C:\\users\\<nazwa>); inna niż w pozostałych instancjach (D5)
  komputer       nazwa komputera DESKTOP-XXXXXXX (wine: domena w GetUserNameEx, COMPUTERNAME) (D5)
Pliki sprzed D5 (bez uzytkownik/komputer) są uzupełniane przy pierwszym odczycie; pozostałe pola bez zmian.
Dla powłoki:
  eval "$(python3 -I tozsamosc.py powloka <katalog stanu>)"   # TOZ_VOLUME, TOZ_MAC, TOZ_MACHINE_ID, TOZ_USER, TOZ_HOST
Cofnięcie: usunąć tozsamosc.json (przy następnym starcie powstanie nowa) albo nie startować przez uruchom_gre.sh.
"""
import json
import re
import secrets
import shlex
import sys
import uuid
from pathlib import Path

# Prefiksy (OUI) kart sieciowych spotykanych w domowych PC: Realtek, Intel Corporate.
PREFIKSY_MAC = ("00:e0:4c", "00:1b:21")
_HEX8 = re.compile(r"^[0-9a-f]{8}$")
_HEX32 = re.compile(r"^[0-9a-f]{32}$")
_MAC = re.compile(r"^([0-9a-f]{2}:){5}[0-9a-f]{2}$")
# Nazwy kont spotykane na domowych PC (bez polskich znaków: ścieżka C:\users\<nazwa>).
UZYTKOWNICY = ("Kamil", "Tomek", "Piotr", "Mateusz", "Kuba", "Marcin", "Adam", "Pawel", "Michal", "Bartek",
               "Dawid", "Krzysiek", "Lukasz", "Szymon", "Admin", "User", "Dom", "PC")
_UZYTKOWNIK = re.compile(r"^[A-Za-z][A-Za-z0-9]{1,19}$")
_KOMPUTER = re.compile(r"^DESKTOP-[A-Z0-9]{7}$")
_ZNAKI = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def zajete_nazwy(katalog):
    """Nazwy użytkowników z tozsamosc.json pozostałych instancji (rodzeństwo katalogu stanu)."""
    katalog = Path(katalog).resolve()
    wynik = set()
    for f in katalog.parent.glob("*/tozsamosc.json"):
        if f.parent != katalog:
            try:
                wynik.add(str(json.loads(f.read_text()).get("uzytkownik", "")).lower())
            except ValueError:
                pass
    return wynik


def nowy_uzytkownik(zajete=()):
    wolne = [u for u in UZYTKOWNICY if u.lower() not in zajete and u.lower() != "charlie"]
    return secrets.choice(wolne)


def nowy_komputer():
    return "DESKTOP-" + "".join(secrets.choice(_ZNAKI) for _ in range(7))


def nowa(zajete=()):
    return {
        "volume_serial": secrets.token_hex(4),
        "mac": secrets.choice(PREFIKSY_MAC) + ":" + ":".join(secrets.token_hex(1) for _ in range(3)),
        # jak systemd: losowy UUID w wersji 4 (13. cyfra = 4, 17. = 8..b), zapis bez kresek
        "machine_id": uuid.uuid4().hex,
        "uzytkownik": nowy_uzytkownik(zajete),
        "komputer": nowy_komputer(),
    }


def poprawna(t):
    return (isinstance(t, dict) and _HEX8.match(str(t.get("volume_serial", "")))
            and _MAC.match(str(t.get("mac", ""))) and _HEX32.match(str(t.get("machine_id", "")))
            and _UZYTKOWNIK.match(str(t.get("uzytkownik", ""))) and _KOMPUTER.match(str(t.get("komputer", ""))))


def _zapisz(plik, t):
    plik.parent.mkdir(parents=True, exist_ok=True)
    tmp = plik.with_suffix(".tmp")
    tmp.write_text(json.dumps(t, indent=2) + "\n")
    tmp.replace(plik)


def wczytaj_lub_utworz(katalog):
    plik = Path(katalog) / "tozsamosc.json"
    if plik.exists():
        t = json.loads(plik.read_text())
        if isinstance(t, dict) and ("uzytkownik" not in t or "komputer" not in t):
            t.setdefault("uzytkownik", nowy_uzytkownik(zajete_nazwy(katalog)))
            t.setdefault("komputer", nowy_komputer())
            if poprawna(t):
                _zapisz(plik, t)
        if not poprawna(t):
            raise ValueError(f"{plik}: niepoprawna tożsamość (usuń plik, by wygenerować nową)")
        if t["uzytkownik"].lower() in zajete_nazwy(katalog):
            raise ValueError(f"{plik}: nazwa użytkownika {t['uzytkownik']} jest już w innej instancji")
        return t
    t = nowa(zajete_nazwy(katalog))
    _zapisz(plik, t)
    return t


def powloka(t):
    return "\n".join([
        f"export TOZ_VOLUME={shlex.quote(t['volume_serial'])}",
        f"export TOZ_MAC={shlex.quote(t['mac'])}",
        f"export TOZ_MACHINE_ID={shlex.quote(t['machine_id'])}",
        f"export TOZ_USER={shlex.quote(t['uzytkownik'])}",
        f"export TOZ_HOST={shlex.quote(t['komputer'])}",
    ])


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "powloka":
        print("użycie: tozsamosc.py powloka <katalog stanu instancji>", file=sys.stderr)
        sys.exit(2)
    print(powloka(wczytaj_lub_utworz(sys.argv[2])))
