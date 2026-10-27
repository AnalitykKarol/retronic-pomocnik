#!/usr/bin/env python3
"""Podgląd całej mapy serwera na żywo: kafelki z mapa/map74.otmm (każde piętro), warstwa spawnów
(dane_tibia/serwer74/potwory_pelne.json) i pozycje postaci/stworów ze strażnika (tylko odczyt, bez inputu do gry).

  mapa_live.py [--port 8765] [--host 127.0.0.1]     potem http://127.0.0.1:8765/

Instancje: domyślna + każda z instancje/<id>/ (gniazdo retronic-<id>.sock). Gdy gry nie ma, mapa i spawny
działają dalej, znacznik postaci się nie pokazuje.
"""
import argparse
import io
import json
import os
import re
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.dont_write_bytecode = True
KAT = Path(__file__).resolve().parent
sys.path.insert(0, str(KAT))

from PIL import Image  # noqa: E402

import instancja  # noqa: E402
import mapa as mapa_mod  # noqa: E402

SPAWNY_PLIK = KAT / "dane_tibia" / "serwer74" / "potwory_pelne.json"
HTML = KAT / "mapa_live.html"

_paleta = []
for _c in range(256):
    _paleta += list(mapa_mod._kolor_tibii(_c))
_maska = bytes(255 if f & mapa_mod.WIDZIANE else 0 for f in range(256))

_m = mapa_mod.mapa()
_blok_img = {}
_kafle = {}
_zamek = threading.Lock()


def obraz_bloku(bx, by, z):
    """Obraz RGBA 64x64 jednego bloku mapy (niewidziane pola przezroczyste) albo None."""
    k = (bx, by, z)
    if k in _blok_img:
        return _blok_img[k]
    b = _m._blok(mapa_mod._klucz_bloku(bx * 64, by * 64, z))
    img = None
    if b is not None:
        kolor = Image.frombytes("P", (64, 64), b[1::3])
        kolor.putpalette(_paleta)
        img = kolor.convert("RGBA")
        img.putalpha(Image.frombytes("L", (64, 64), b[0::3].translate(_maska)))
    _blok_img[k] = img
    return img


def kafel(z_pietro, tx, ty, zoom):
    """PNG 256x256: zoom Leaflet 'zoom' -> 2**zoom px na pole gry, niewidziane pola przezroczyste."""
    klucz = (z_pietro, tx, ty, zoom)
    with _zamek:
        if klucz in _kafle:
            return _kafle[klucz]
        rozmiar = int(256 / 2 ** zoom)                       # ile pól gry obejmuje kafel
        x0, y0 = tx * rozmiar, ty * rozmiar
        wynik = None
        if x0 < 40000 and y0 < 45000 and x0 >= 0 and y0 >= 0:
            plansza = None
            for by in range(y0 // 64, (y0 + rozmiar - 1) // 64 + 1):
                for bx in range(x0 // 64, (x0 + rozmiar - 1) // 64 + 1):
                    im = obraz_bloku(bx, by, z_pietro)
                    if im is None:
                        continue
                    if plansza is None:
                        plansza = Image.new("RGBA", (rozmiar, rozmiar), (0, 0, 0, 0))
                    plansza.paste(im, (bx * 64 - x0, by * 64 - y0))   # bloki się nie nakładają
            if plansza is not None:
                if rozmiar != 256:
                    metoda = Image.NEAREST if rozmiar < 256 else Image.BOX
                    plansza = plansza.resize((256, 256), metoda)
                buf = io.BytesIO()
                plansza.save(buf, "PNG", optimize=False)
                wynik = buf.getvalue()
        if len(_kafle) > 6000:
            _kafle.clear()
        _kafle[klucz] = wynik
        return wynik


_spawny_cache = None


def spawny():
    """Płaska lista spawnów: [{n, x, y, z, r, il, t}] z danych CipSoft 7.4."""
    global _spawny_cache
    if _spawny_cache is None:
        dane = json.loads(SPAWNY_PLIK.read_text())["potwory"]
        lista = []
        for p in dane:
            for s in p.get("spawny", ()):
                lista.append({"n": p["nazwa"], "x": s["x"], "y": s["y"], "z": s["z"], "r": s.get("promien", 0),
                              "il": s.get("ilosc", 1), "t": s.get("respawn_s"), "hp": p.get("hp"), "exp": p.get("exp")})
        _spawny_cache = lista
    return _spawny_cache


def _zapytaj(gniazdo, zadanie, limit=1.5):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(limit)
        s.connect(str(gniazdo))
        s.sendall((json.dumps(zadanie) + "\n").encode())
        return json.loads(s.makefile("rb").readline())


def _nazwa(sc):
    try:
        wz = re.findall(r"Connecting to character (.+?) on ", Path(sc.log_klienta).read_text(errors="replace"))
        return wz[-1] if wz else None
    except OSError:
        return None


def instancje():
    ids = [""] + sorted(p.name for p in (KAT / "instancje").iterdir() if p.is_dir() and not p.name.startswith("_")) \
        if (KAT / "instancje").is_dir() else [""]
    rt = instancja.runtime("/tmp")
    return [instancja.sciezki(i, rt) for i in ids]


def na_zywo(stwory=True):
    gracze = []
    for sc in instancje():
        if not Path(sc.gniazdo).exists():
            continue
        nazwa = os.environ.get("RETRONIC_POSTAC") if not sc.id else None
        nazwa = nazwa or _nazwa(sc)
        if not nazwa:
            continue
        wpis = {"id": sc.id or "domyslna", "nazwa": nazwa}
        try:
            o = _zapytaj(sc.gniazdo, {"cmd": "pozycja", "nazwa": nazwa})
            p = o.get("pozycja")
            if p:
                wpis.update(x=p["x"], y=p["y"], z=p["z"])
        except Exception as e:
            wpis["blad"] = f"{type(e).__name__}"
        if stwory and "x" in wpis:
            try:
                o = _zapytaj(sc.gniazdo, {"cmd": "stwory", "maks_wiek": 3})
                wpis["stwory"] = [
                    {"n": s.get("nazwa"), "x": s.get("x"), "y": s.get("y"), "z": s.get("z"),
                     "g": bool(s.get("gracz")), "hp": s.get("hp", s.get("proc_hp"))}
                    for s in o.get("stwory", ()) if s.get("x") is not None and s.get("nazwa") != nazwa]
            except Exception:
                wpis["stwory"] = []
        gracze.append(wpis)
    return {"t": time.time(), "gracze": gracze}


class Obsluga(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _wyslij(self, kod, typ, dane, cache=None):
        self.send_response(kod)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(dane)))
        if cache:
            self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(dane)

    def do_GET(self):
        u = urlparse(self.path)
        try:
            m = re.fullmatch(r"/kafel/(\d+)/(-?\d+)/(\d+)/(\d+)\.png", u.path)
            if m:
                z, zoom, tx, ty = (int(g) for g in m.groups())
                png = kafel(z, tx, ty, zoom)
                if png is None:
                    return self._wyslij(204, "image/png", b"")
                return self._wyslij(200, "image/png", png, "max-age=3600")
            if u.path == "/api/spawny":
                z = parse_qs(u.query).get("z", [None])[0]
                lista = [s for s in spawny() if z is None or s["z"] == int(z)]
                return self._wyslij(200, "application/json", json.dumps(lista).encode(), "max-age=300")
            if u.path == "/api/znaczniki":
                f = KAT / "dane_tibia" / "mapy" / "znaczniki.json"
                return self._wyslij(200, "application/json", f.read_bytes() if f.is_file() else b"{}")
            if u.path == "/api/live":
                return self._wyslij(200, "application/json", json.dumps(na_zywo()).encode())
            if u.path in ("/", "/index.html"):
                return self._wyslij(200, "text/html; charset=utf-8", HTML.read_bytes())
            if u.path.startswith("/lib/"):
                f = (KAT / "mapa_live_lib" / Path(u.path).name)
                if f.is_file():
                    typ = "text/css" if f.suffix == ".css" else "application/javascript" if f.suffix == ".js" else "image/png"
                    return self._wyslij(200, typ, f.read_bytes(), "max-age=86400")
            self._wyslij(404, "text/plain", b"nie ma")
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            self._wyslij(500, "text/plain", f"{type(e).__name__}: {e}".encode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args()
    srv = ThreadingHTTPServer((a.host, a.port), Obsluga)
    print(f"mapa na żywo: http://{a.host}:{a.port}/  (Ctrl+C kończy)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
