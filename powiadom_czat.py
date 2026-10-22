#!/usr/bin/env python3
"""Powiadomienia o wiadomościach do postaci (22.10, Karol: kutangen sprzedaje HMM ręcznie, „niech tylko powiadomienia mi
wysyła, jak ktoś napisze”). TYLKO ODCZYT: co ODSWIEZ_S pyta strażnika instancji (komenda "wiadomosci", bez skanu) i dla
nowych wpisów od innych graczy daje dymek `notify-send`. Nic nie klika i nic nie pisze w grze.

Kanały: strażnik nie zawsze przypisuje bufor do zakładki (u kutangena wszystko ma kanal=None), więc Trade rozpoznajemy po
treści: bufor, w którym większość wpisów to ogłoszenia (sell/buy), uznajemy za Trade i pomijamy. Server Log pomijamy po
nazwie. Prywatne (kolor jasnoniebieski klienta albo bufor nowej zakładki) = dymek pilny; czat obok (Default) = zwykły.

Użycie:  RETRONIC_ID=kutangen python3 -I powiadom_czat.py        (w tle: setsid nohup ... &)
Log:     instancje/<id>/logi/powiadom-czat-RRRRMMDD.log. Koniec: kill procesu (pkill -f 'powiadom_czat.py').
"""
import json
import os
import re
import socket
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import instancja  # noqa: E402

ODSWIEZ_S = 3.0
OGLOSZENIE = re.compile(r"\b(sell|buy|wts|wtb|trade)\b|/bp|k/|>>|<<", re.I)
KOLORY_PRIV = {"5ff7f7", "9f9dfd"}                 # OTClient: prywatna od gracza (jasnoniebieski)
MIN_WPISOW_TRADE = 3


def zapytaj(gniazdo, z):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as so:
        so.settimeout(3)
        so.connect(str(gniazdo))
        so.sendall((json.dumps(z) + "\n").encode())
        return json.loads(so.makefile("rb").readline())


class Bufory:
    """Statystyka buforów czatu: ile wpisów, ile ogłoszeń; bufor z przewagą ogłoszeń = Trade."""

    def __init__(self):
        self.n, self.ogl = {}, {}

    def dodaj(self, bufor, tekst):
        self.n[bufor] = self.n.get(bufor, 0) + 1
        self.ogl[bufor] = self.ogl.get(bufor, 0) + bool(OGLOSZENIE.search(tekst or ""))

    def trade(self, bufor):
        n = self.n.get(bufor, 0)
        return n >= MIN_WPISOW_TRADE and self.ogl.get(bufor, 0) / n >= 0.6


def rodzaj(w, bufory, nazwy_kanalow, ja):
    """None = pomiń, inaczej "priv" albo "obok"."""
    autor = (w.get("nadawca") or w.get("autor") or "").strip()
    if not autor or autor.lower() == ja.lower():
        return None
    kanal = (w.get("kanal") or nazwy_kanalow.get(w.get("bufor")) or "").lower()
    if kanal in ("server log", "trade", "game-chat", "help", "advertising", "npcs"):
        return None
    if (w.get("kolor") or "").lower() in KOLORY_PRIV:
        return "priv"
    if bufory.trade(w.get("bufor")):
        return None
    if kanal and kanal not in ("default",):
        return "priv"                               # nazwana zakładka inna niż Default = rozmowa prywatna
    return "obok"


def main():
    id_ = os.environ.get("RETRONIC_ID")
    if not id_:
        sys.exit("ustaw RETRONIC_ID (np. kutangen)")
    s = instancja.sciezki(id_, instancja.runtime(f"/run/user/{os.getuid()}"))
    ja = id_.capitalize()
    try:
        ja = json.loads((s.stan / "profil.json").read_text()).get("postac") or ja
    except Exception:
        pass
    logi = s.stan / "logi"
    logi.mkdir(parents=True, exist_ok=True)

    def log(t):
        with open(logi / f"powiadom-czat-{time.strftime('%Y%m%d')}.log", "a") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {t}\n")

    bufory, nr, epoka = Bufory(), None, None
    log(f"start: {ja} ({id_}), gniazdo {s.gniazdo}")
    while True:
        z = {"cmd": "wiadomosci", "limit": 100}
        if nr is not None:
            z.update(od=nr, epoka=epoka)
        try:
            odp = zapytaj(s.gniazdo, z)
        except (OSError, ValueError):
            time.sleep(10)
            continue
        if not odp.get("ok"):
            time.sleep(10)
            continue
        nazwy = {k: v for k, v in (odp.get("kanaly") or {}).items()}
        pierwszy = nr is None or odp.get("epoka") != epoka
        nr, epoka = odp.get("znacznik"), odp.get("epoka")
        for w in odp.get("wiadomosci", []):
            r = rodzaj(w, bufory, nazwy, ja)          # ocena przed dodaniem: pierwsze wpisy nowego bufora nie są „Trade”
            bufory.dodaj(w.get("bufor"), w.get("tekst"))
            if pierwszy or r is None:
                continue                                # start: tylko nauka buforów, bez starej historii
            autor, tekst = w.get("nadawca") or w.get("autor"), (w.get("tekst") or "").strip()
            log(f"{r} {autor}: {tekst}")
            tytul = f"{ja}: {'prywatna' if r == 'priv' else 'czat obok'} od {autor}"
            subprocess.run(["notify-send", "-u", "critical" if r == "priv" else "normal", "-a", "Retronic sklep",
                            tytul, tekst[:200]], check=False)
        time.sleep(ODSWIEZ_S)


if __name__ == "__main__":
    main()
