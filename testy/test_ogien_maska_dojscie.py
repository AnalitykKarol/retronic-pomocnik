"""24.10 19:12 (log startu Marinarry): „[OGIEN] nie wczytam maski stałych pól: AttributeError("'CavebotDojscie' object has no attribute 'mapa'")”.
Przyczyna: Cavebot.__init__ wołał _ogien_stale_wczytaj() PRZED wczytaniem self.mapa (od 14.10, b901ad5: przy OGIEN_MASKA_TYLKO_SCIANY pole sprawdza się o mapę),
więc pierwsze wywołanie wywracało się w KAŻDYM starcie (zwykły Cavebot i CavebotDojscie, bo dziedziczy konstruktor); maskę ładowało dopiero drugie wywołanie niżej, po wczytaniu
mapy: maska NIE była tracona (brak regresji danych), ale każdy start pisał fałszywy błąd w logu. Poprawka: jedno wywołanie, po mapie.
Test: kopia trasy/ogien_stale.json + jedno pole przechodnie w katalogu tymczasowym (prawdziwy plik nietknięty), konstrukcja CavebotDojscie i Cavebot; w logu nie ma błędu maski, maska ma dokładnie
pola-ściany wg mapy z pliku (pokrętło TYLKO_SCIANY=1) albo wszystkie (=0). Czerwony na cavebot.py sprzed poprawki (log błędu). Atrapy jak test_dojscie_klucz_drzwi.py."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import sys
from pathlib import Path

KAT = Path(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
_src = (KAT / "testy" / "test_dojscie_klucz_drzwi.py").read_text()
_src = _src[:_src.index("# --- 0. jedno źródło kluczy")]
_g = {"__file__": str(KAT / "testy" / "test_dojscie_klucz_drzwi.py"), "__name__": "atrapy_dojscie_klucz"}
exec(compile(_src, "test_dojscie_klucz_drzwi(atrapy)", "exec"), _g)
globals().update({k: v for k, v in _g.items() if not k.startswith("__")})
ok.clear()
import shutil
import tempfile

ZRODLO = KAT / "trasy" / "ogien_stale.json"
if not ZRODLO.is_file():
    print("brak trasy/ogien_stale.json, pomijam test")
    sys.exit(0)
POLA_PLIK = {tuple(int(v) for v in p) for p in _json.loads(ZRODLO.read_text()).get("pola", [])}
PRZECHODNE = (32655, 31660, 9)            # pole przechodnie (korytarz z9): dopisane do KOPII; przy TYLKO_SCIANY=1 nie wolno go wpuścić do maski
POLA = POLA_PLIK | {PRZECHODNE}
SCIANY = {p for p in POLA if not (M.flagi(*p) & 1) or (M.flagi(*p) & 4)}           # to samo kryterium co Cavebot._ogien_pole_sciana (mapa: nieprzechodnie albo flaga 4)
sprawdz("0 dane: plik ma pola-ściany, a dopisane pole korytarza jest przechodnie (filtr TYLKO_SCIANY ma co odrzucić)", POLA_PLIK and SCIANY and PRZECHODNE not in SCIANY and PRZECHODNE in POLA, f"plik={len(POLA_PLIK)} ściany={len(SCIANY)}")

tmp = Path(tempfile.mkdtemp(prefix="ogien_maska_"))
try:
    kopia = tmp / "ogien_stale.json"
    kopia.write_text(_json.dumps({"opis": "kopia testowa", "pola": sorted([x, y, z] for x, y, z in POLA)}))
    stary_plik, stare_pokretlo = cavebot.PLIK_OGIEN_STALE, cavebot.OGIEN_MASKA_TYLKO_SCIANY
    cavebot.PLIK_OGIEN_STALE = kopia
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok")

    def zbuduj(klasa, **kw):
        LOG.clear()
        s = SwiatK((32655, 31660, 9))
        punkty = [(32655, 31660, 9), (32655, 31659, 9)]
        b = klasa(PK(s), punkty, okrazenia=1, zapytaj=s.zapytaj, atak=lambda m, g: None, alarm=lambda w: None, spij=s.spij,
                  zegar=s.zegar, loot=loot, mapa=M, klik=s.klik, **kw)
        return b, [l for l in LOG if "[OGIEN]" in l]

    try:
        cavebot.OGIEN_MASKA_TYLKO_SCIANY = 1
        bd, logi = zbuduj(cavebot.CavebotDojscie, tolerancja=2)
        sprawdz("1a CavebotDojscie: w logu startu nie ma błędu wczytania maski ognia", not logi, logi)
        sprawdz("1b CavebotDojscie (TYLKO_SCIANY=1): maska ognia = dokładnie pola-ściany z pliku, bez pola przechodniego (zasiew po wczytaniu mapy)", set(bd.ogien_stale) == SCIANY and SCIANY and PRZECHODNE not in bd.ogien_stale,
                f"maska={len(bd.ogien_stale)} oczekiwane={len(SCIANY)}")
        bc, logi = zbuduj(cavebot.Cavebot)
        sprawdz("2a zwykły Cavebot: w logu startu nie ma błędu wczytania maski ognia", not logi, logi)
        sprawdz("2b zwykły Cavebot (TYLKO_SCIANY=1): ta sama maska", set(bc.ogien_stale) == SCIANY, f"maska={len(bc.ogien_stale)}")
        cavebot.OGIEN_MASKA_TYLKO_SCIANY = 0
        bw, logi = zbuduj(cavebot.CavebotDojscie, tolerancja=2)
        sprawdz("3 pokrętło TYLKO_SCIANY=0: maska = wszystkie pola z pliku, bez błędu w logu", set(bw.ogien_stale) == POLA and not logi, f"maska={len(bw.ogien_stale)} pola={len(POLA)} {logi}")
    finally:
        cavebot.PLIK_OGIEN_STALE, cavebot.OGIEN_MASKA_TYLKO_SCIANY = stary_plik, stare_pokretlo
    sprawdz("4 prawdziwy plik maski nietknięty (zapis szedł tylko do kopii)", {tuple(int(v) for v in p) for p in _json.loads(ZRODLO.read_text()).get("pola", [])} == POLA_PLIK)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
