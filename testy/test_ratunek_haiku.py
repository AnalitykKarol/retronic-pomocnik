"""F2a ratunku (SPEC_ratunek_haiku_1019): Haiku w cieniu. Atrapa Claude i zrzutu; prawdziwy claude nigdy nie jest wołany."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, types, json, tempfile, threading, time
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import ratunek, ratunek_cien

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))

def konf(**k):
    return types.SimpleNamespace(**dict(ratunek.DOMYSLNE, RATUNEK_HAIKU=1, **k))

POZ = (33106, 31849, 6)

def sygnal(kod="S2", t=100.0, **d):
    return dict(d, kod=kod, opis=ratunek.OPISY[kod], t=t, poz=list(POZ), wolan_h=1, ponad_limit=False,
                id=f"20261019-120000-{kod}-{int(t)}")

class Atrapa:
    """Atrapa Claude: odpowiedź z listy / dowolna / wyjątek / blokada; liczy wywołania."""
    def __init__(self, odp='{"ruch": "uzyj_pola 0,-1", "dlaczego": "drabina nad postacią"}', wyjatek=None, bramka=None):
        self.odp, self.wyjatek, self.bramka, self.n, self.prompty, self.obrazy = odp, wyjatek, bramka, 0, [], []
    def fab(self, timeout):
        self.timeout = timeout
        return self
    def __call__(self, prompt, system=None, obraz=None):
        self.n += 1; self.prompty.append(prompt); self.obrazy.append(obraz)
        if self.bramka is not None:
            self.bramka.wait(10)
        if self.wyjatek:
            raise self.wyjatek
        return self.odp, {"duration_ms": 1}

def nowy(atrapa=None, zrzut=lambda: b"\xff\xd8JPEGDANE\xff\xd9"):
    return ratunek_cien.Cien(claude_fab=(atrapa or Atrapa()).fab, zrzut=zrzut)

def poczekaj(c):
    if c.watek is not None:
        c.watek.join(10)

def rekordy(plik):
    return [json.loads(l) for l in open(plik)] if Path(plik).exists() else []

def hc(plik):
    return [r for r in rekordy(plik) if r.get("rekord") == "haiku_cien"]

# --- walidacja odpowiedzi (pkt 3) ---
w = lambda t, poz=POZ: ratunek_cien.waliduj(t, poz)
sprawdz("waliduj: krok E", w('{"ruch": "krok E"}')["ruch"] == "krok E")
sprawdz("waliduj: krok małą literą -> normalizacja", w('{"ruch": "krok ne"}')["ruch"] == "krok NE")
sprawdz("waliduj: uzyj_pola 0,-1", w('{"ruch": "uzyj_pola 0,-1"}')["ruch"] == "uzyj_pola 0,-1")
sprawdz("waliduj: lina -3,2", w('{"ruch": "lina -3,2"}')["ruch"] == "lina -3,2")
sprawdz("waliduj: idz_do w widoku", w('{"ruch": "idz_do 33110,31850"}')["ruch"] == "idz_do 33110,31850")
sprawdz("waliduj: czekaj 5", w('{"ruch": "czekaj 5"}')["ruch"] == "czekaj 5")
sprawdz("waliduj: JSON w bloku ``` z tekstem dookoła", w('Oto:\n```json\n{"ruch": "krok S", "dlaczego": "x"}\n```')["ruch"] == "krok S")
x = w('{"ruch": "teleportuj 1,1"}')
sprawdz("waliduj: ruch spoza listy -> czlowiek + powód", x["ruch"] == "czlowiek" and x["powod"].startswith("poza_lista"), x)
x = w('{"ruch": "uzyj_pola 8,0"}')
sprawdz("waliduj: uzyj_pola poza widokiem (dx=8) -> czlowiek", x["ruch"] == "czlowiek" and "pole_poza_widokiem" in x["powod"], x)
x = w('{"ruch": "lina 0,6"}')
sprawdz("waliduj: lina poza widokiem (dy=6) -> czlowiek", x["ruch"] == "czlowiek" and "pole_poza_widokiem" in x["powod"], x)
x = w('{"ruch": "idz_do 33120,31849"}')
sprawdz("waliduj: idz_do poza widokiem -> czlowiek", x["ruch"] == "czlowiek" and "pole_poza_widokiem" in x["powod"], x)
x = w('{"ruch": "czekaj 11"}')
sprawdz("waliduj: czekaj > 10 -> czlowiek", x["ruch"] == "czlowiek" and "czekaj_poza_zakresem" in x["powod"], x)
x = w('{"ruch": "krok UP"}')
sprawdz("waliduj: zły kierunek -> czlowiek", x["ruch"] == "czlowiek", x)
sprawdz("waliduj: nie-JSON -> czlowiek", w("nie wiem, spróbuj iść w lewo")["powod"] == "odpowiedz_nie_json")
sprawdz("waliduj: ruch nie jest tekstem -> czlowiek", w('{"ruch": 5}')["ruch"] == "czlowiek")
x = w('{"ruch": "czlowiek", "dlaczego": "nie widzę drogi"}')
sprawdz("waliduj: model wybiera czlowiek -> powód i uzasadnienie", x["ruch"] == "czlowiek" and x["powod"] == "model_wybral_czlowieka"
        and x["dlaczego"] == "nie widzę drogi", x)
import cavebot
sprawdz("stałe widoku = cavebot.ZASIEG", (ratunek_cien.WIDOK_X, ratunek_cien.WIDOK_Y) == (cavebot.ZASIEG_X, cavebot.ZASIEG_Y))
try:
    ratunek_cien._claude_domyslny(1); sprawdz("testy: prawdziwy claude zabroniony", False)
except RuntimeError:
    sprawdz("testy: prawdziwy claude zabroniony", True)

# --- Cien: rekordy ---
with tempfile.TemporaryDirectory() as tmp:
    plik = Path(tmp) / "ratunek-20261019.jsonl"
    at = Atrapa(); c = nowy(at)
    s = sygnal("S2")
    t0 = time.monotonic()
    r = c.zglos(s, lambda rek: {"poz": POZ, "stan": "IDZ"}, plik, 20, lambda m: None)
    sprawdz("odpowiedź z listy: start", r == "start", r)
    poczekaj(c)
    rr = hc(plik)
    h = rr[0]["haiku_cien"] if rr else {}
    sprawdz("odpowiedź z listy -> rekord haiku_cien z ruchem, bez wykonania", len(rr) == 1 and h["ruch"] == "uzyj_pola 0,-1"
            and h["powod"] is None and h["wykonano"] is False and h["blad"] is None, rr)
    sprawdz("rekord powiązany z sygnałem (id, kod, poz)", rr[0]["id"] == s["id"] and rr[0]["kod"] == "S2" and rr[0]["poz"] == list(POZ), rr)
    sprawdz("rekord ma czas wywołania i odpowiedź surową", isinstance(h["czas_wywolania_s"], float) and "drabina" in h["odpowiedz"], h)
    sprawdz("zrzut zapisany w ratunek-zrzuty i podany modelowi", h["zrzut"] == f"ratunek-zrzuty/{s['id']}.jpg"
            and (Path(tmp) / h["zrzut"]).read_bytes().startswith(b"\xff\xd8") and at.obrazy[0] == str(Path(tmp) / h["zrzut"]), (h, at.obrazy))
    sprawdz("timeout modelu przekazany (limit czasu)", at.timeout == ratunek_cien.HAIKU_TIMEOUT_S)
    sprawdz("po zakończeniu pytanie wolne", c.zajety is False)

    # spoza listy
    plik2 = Path(tmp) / "b.jsonl"
    c = nowy(Atrapa('{"ruch": "teleportuj"}')); c.zglos(sygnal("S3"), None, plik2, 20, lambda m: None); poczekaj(c)
    h = hc(plik2)[0]["haiku_cien"]
    sprawdz("odpowiedź spoza listy -> czlowiek + powód poza_lista", h["ruch"] == "czlowiek" and h["powod"].startswith("poza_lista"), h)
    # pole poza widokiem
    c = nowy(Atrapa('{"ruch": "uzyj_pola 20,0"}')); c.zglos(sygnal("S3", 101.0), None, plik2, 20, lambda m: None); poczekaj(c)
    h = hc(plik2)[1]["haiku_cien"]
    sprawdz("pole poza widokiem -> czlowiek", h["ruch"] == "czlowiek" and "pole_poza_widokiem" in h["powod"], h)
    # timeout
    class BladModelu(Exception): pass
    c = nowy(Atrapa(wyjatek=BladModelu("timeout 45.0 s"))); c.zglos(sygnal("S4", 102.0), None, plik2, 20, lambda m: None); poczekaj(c)
    h = hc(plik2)[2]["haiku_cien"]
    sprawdz("timeout -> czlowiek, powód timeout, błąd w rekordzie", h["ruch"] == "czlowiek" and h["powod"] == "timeout" and "timeout" in h["blad"], h)
    # wyjątek
    c = nowy(Atrapa(wyjatek=OSError("brak claude"))); c.zglos(sygnal("S4", 103.0), None, plik2, 20, lambda m: None); poczekaj(c)
    h = hc(plik2)[3]["haiku_cien"]
    sprawdz("wyjątek -> czlowiek, powód blad_wywolania, błąd w rekordzie", h["ruch"] == "czlowiek" and h["powod"] == "blad_wywolania"
            and "brak claude" in h["blad"], h)
    sprawdz("po wyjątku pytanie znów wolne", c.zajety is False)
    # odpowiedź ucięta
    c = nowy(Atrapa("x" * 5000)); c.zglos(sygnal("S5", 104.0), None, plik2, 20, lambda m: None); poczekaj(c)
    sprawdz("odpowiedź surowa ucięta do 2000 znaków", len(hc(plik2)[4]["haiku_cien"]["odpowiedz"]) == 2000)
    # zrzut nie działa: pytamy mimo to
    def zly_zrzut(): raise OSError("grim nie działa")
    at = Atrapa(); c = nowy(at, zly_zrzut); c.zglos(sygnal("S6", 105.0), None, plik2, 20, lambda m: None); poczekaj(c)
    h = hc(plik2)[5]["haiku_cien"]
    sprawdz("błąd zrzutu: rekord z blad_zrzutu, model pytany bez obrazu", h["zrzut"] is None and "grim" in h["blad_zrzutu"]
            and at.n == 1 and at.obrazy[0] is None and h["ruch"] == "uzyj_pola 0,-1", h)
    # migawka rzuca: pomijamy z wpisem, bez wywołania
    at = Atrapa(); c = nowy(at)
    c.zglos(sygnal("S7", 106.0), lambda rek: 1 / 0, plik2, 20, lambda m: None); poczekaj(c)
    h = hc(plik2)[6]["haiku_cien"]
    sprawdz("błąd migawki -> pominięty blad_kontekstu, zero wywołań, pytanie wolne",
            h["pominiety"] == "blad_kontekstu" and at.n == 0 and c.zajety is False and len(c.wywolania) == 0, h)

# --- wątek nie blokuje, jedno wywołanie naraz ---
with tempfile.TemporaryDirectory() as tmp:
    plik = Path(tmp) / "r.jsonl"
    bramka = threading.Event(); at = Atrapa(bramka=bramka); c = nowy(at)
    t0 = time.monotonic()
    r1 = c.zglos(sygnal("S3", 100.0), None, plik, 20, lambda m: None)
    dt = time.monotonic() - t0
    sprawdz("zglos wraca od razu mimo wolnego modelu (nie czeka na wątek)", r1 == "start" and dt < 0.5 and c.watek.is_alive(), (r1, dt))
    time.sleep(0.05)
    r2 = c.zglos(sygnal("S4", 101.0), None, plik, 20, lambda m: None)
    p = hc(plik)
    sprawdz("sygnał w trakcie pytania pominięty z wpisem", r2 == "trwa_pytanie" and len(p) == 1
            and p[0]["haiku_cien"]["pominiety"] == "trwa_pytanie" and p[0]["id"].endswith("S4-101"), (r2, p))
    sprawdz("w trakcie pytania tylko jedno wywołanie modelu", at.n == 1, at.n)
    bramka.set(); poczekaj(c)
    sprawdz("po odpowiedzi rekord z ruchem i pytanie wolne", len(hc(plik)) == 2 and hc(plik)[1]["haiku_cien"]["ruch"] == "uzyj_pola 0,-1"
            and c.zajety is False)
    r3 = c.zglos(sygnal("S5", 102.0), None, plik, 20, lambda m: None); poczekaj(c)
    sprawdz("kolejny sygnał po zakończeniu znów pytany", r3 == "start" and at.n == 2, (r3, at.n))

# --- limit 20/h obejmuje wywołania ---
with tempfile.TemporaryDirectory() as tmp:
    plik = Path(tmp) / "r.jsonl"
    at = Atrapa(); c = nowy(at)
    wyn = []
    for i in range(5):
        wyn.append(c.zglos(sygnal("S3", 100.0 + i), None, plik, 3, lambda m: None)); poczekaj(c)
    sprawdz("limit: 3 wywołania w godzinie, kolejne pominięte limit_h", wyn == ["start"] * 3 + ["limit_h"] * 2 and at.n == 3, (wyn, at.n))
    sprawdz("limit: pominięcie ma rekord z powodem", [r["haiku_cien"]["pominiety"] for r in hc(plik)][3:] == ["limit_h", "limit_h"])
    c.wywolania = type(c.wywolania)(x - 3700 for x in c.wywolania)       # wywołania sprzed godziny wygasają
    sprawdz("limit: po godzinie znów można pytać", c.zglos(sygnal("S3", 200.0), None, plik, 3, lambda m: None) == "start")
    poczekaj(c)
    at = Atrapa(); c = nowy(at); s = sygnal("S3", 300.0); s["ponad_limit"] = True
    sprawdz("limit: sygnał oznaczony ponad_limit detektora nie woła modelu", c.zglos(s, None, plik, 20, lambda m: None) == "limit_h" and at.n == 0)

# --- ratunek.zglos: pokrętło, linia sygnału zgodna, id ---
with tempfile.TemporaryDirectory() as tmp:
    plik = Path(tmp) / "r.jsonl"
    ratunek._DET = None; ratunek_cien._CIEN = None
    at = Atrapa(); ratunek_cien._CIEN = nowy(at)
    d = ratunek.detektor(konf())
    sy = d.zdarzenie("porazka_trasy", 100.0, POZ, co="dojscie", trasa="gobliny")
    logi = []
    ratunek.zglos(sy, log=logi.append, plik_logu=plik, stan="IDZ", pytaj=False)
    poczekaj(ratunek_cien._CIEN)
    sprawdz("pokrętło 0 (pytaj=False): zero wywołań, brak rekordu haiku_cien", at.n == 0 and not hc(plik) and ratunek_cien._CIEN.watek is None)
    lin = rekordy(plik)[0]
    sprawdz("linia sygnału: dotychczasowe pola bez zmian + id", all(k in lin for k in ("kod", "opis", "t", "poz", "wolan_h", "ponad_limit", "tryb", "stan", "czas"))
            and lin["tryb"] == "cien" and lin["kod"] == "S1" and lin["co"] == "dojscie" and lin["id"].endswith("-S1-" + lin["id"].split("-")[-1]), lin)
    sy = d.zdarzenie("porazka_trasy", 500.0, POZ, co="wyprawa", id="cudze", opis="x")
    ratunek.zglos(sy, log=logi.append, plik_logu=plik, stan="IDZ", pytaj=True, limit_h=20)
    poczekaj(ratunek_cien._CIEN)
    l2 = [r for r in rekordy(plik) if r.get("rekord") is None][-1]
    h = hc(plik)
    sprawdz("pytaj=True: jeden rekord haiku_cien powiązany id z linią sygnału; pole `id` szczegółu nie nadpisuje id sygnału",
            at.n == 1 and len(h) == 1 and h[0]["id"] == l2["id"] and l2["x_id"] == "cudze", (h, l2))
    sprawdz("log bota mówi, że bez wykonania", any("haiku_cien" in m and "bez wykonania" in m for m in logi), logi)
    ruchy = json.loads(at.prompty[0].split("\n", 1)[1])["ostatnie_ruchy"]
    sprawdz("kontekst: ostatnie ruchy z detektora", ruchy and ruchy[-1]["rodzaj"] == "porazka_trasy" and "temu_s" in ruchy[-1], ruchy)

# --- kontekst: bez nicków, z elementami pkt 2 ---
with tempfile.TemporaryDirectory() as tmp:
    mapa = types.SimpleNamespace(flagi=lambda x, y, z: 2 if (x, y, z) in {(33106, 31848, 6), (33107, 31850, 5)} else 0)
    punkty = [(33106, 31849, 8), (33107, 31849, 8), (33100, 31840, 6), (33101, 31840, 6), (33102, 31841, 6), (33103, 31842, 6),
              (33104, 31843, 6), (33105, 31844, 6), (33108, 31845, 6)]
    kat = Path(tmp) / "k"; (kat / "trasy").mkdir(parents=True)
    (kat / "trasy" / "pietra_start.json").write_text(json.dumps({"33107,31847,6": [33107, 31848], "1,1,6": [2, 2]}))
    (kat / "trasy" / "dziury_nauczone.json").write_text(json.dumps({"dziury": [[33109, 31849, 6], [1, 1, 6]]}))
    snap = {"poz": POZ, "stan": "IDZ", "punkty": punkty, "idx": 0, "hp": 250, "max_hp": 250, "mana": 400, "max_mana": 425,
            "mapa": mapa, "katalog": kat, "wypad": False,
            "stwory": [{"gracz": True, "nazwa": "Tajny Nick", "dx": 2, "dy": 1, "hp": 100},
                       {"gracz": False, "nazwa": "Goblin", "dx": -3, "dy": 0, "hp": 80}],
            "ruchy": [{"temu_s": float(i), "rodzaj": "pozycja", "poz": [1, i, 6], "stan": "IDZ"} for i in range(15)]}
    rek = sygnal("S6", 100.0, cel="Tajny Nick", n=5)
    ctx = ratunek_cien.zbuduj_kontekst(rek, snap)
    txt = ratunek_cien.zbuduj_prompt(ctx)
    sprawdz("kontekst: żaden nick gracza w prompcie (stwory ani szczegół `cel`)", "Tajny Nick" not in txt and "Goblin" in txt, txt[:400])
    sprawdz("kontekst: cel ze szczegółu zwykłego stwora zostaje", ratunek_cien.zbuduj_kontekst(sygnal("S6", cel="Goblin", n=5), snap)["sygnal"]["liczby"]["cel"] == "Goblin")
    sprawdz("kontekst: sygnał z liczbami", ctx["sygnal"]["kod"] == "S6" and ctx["sygnal"]["liczby"]["n"] == 5, ctx["sygnal"])
    sprawdz("kontekst: pozycja, cel na piętrze docelowym (z8)", ctx["pozycja"] == list(POZ) and ctx["cel"]["pietro_docelowe"] == 8
            and ctx["cel"]["punkt_trasy"]["z"] == 8, ctx.get("cel"))
    sprawdz("kontekst: 5 najbliższych punktów trasy, to samo piętro najpierw", len(ctx["najblizsze_punkty_trasy"]) == 5
            and all(p["z"] == 6 for p in ctx["najblizsze_punkty_trasy"]), ctx["najblizsze_punkty_trasy"])
    pr = ctx["przejscia_pieter_w_promieniu_10"]
    sprawdz("kontekst: przejścia z mapy w dół/w górę (względne dx,dy)", pr["w_dol_z_mapy"] == [[0, -1]] and pr["w_gore_z_mapy"] == [[1, 1]], pr)
    sprawdz("kontekst: pola startowe znane i nauczone dziury w promieniu 10 (dalekie pominięte)",
            pr["pola_startowe_znane"][0]["przejscie"] == [1, -2] and len(pr["pola_startowe_znane"]) == 1
            and pr["dziury_nauczone_nie_wchodzic"] == [[3, 0]], pr)
    sprawdz("kontekst: ostatnie 10 ruchów", len(ctx["ostatnie_ruchy"]) == 10 and ctx["ostatnie_ruchy"][-1]["poz"] == [1, 14, 6])
    sprawdz("kontekst: HP/mana", ctx["hp_mana"] == {"hp": 250, "max_hp": 250, "mana": 400, "max_mana": 425}, ctx["hp_mana"])
    sprawdz("kontekst: stwory względnie, gracz bez nicku", {"typ": "gracz", "dx": 2, "dy": 1} in ctx["stwory_w_widoku"]
            and not any("nazwa" in s and s["nazwa"] == "Tajny Nick" for s in ctx["stwory_w_widoku"]))

# --- zrzuty: przycinanie do 200 ---
with tempfile.TemporaryDirectory() as tmp:
    kz = Path(tmp)
    for i in range(205):
        (kz / f"2026{i:05d}.jpg").write_bytes(b"x")
    ratunek_cien._przytnij_zrzuty(kz)
    zost = sorted(p.name for p in kz.glob("*.jpg"))
    sprawdz("zrzuty: zostaje 200 najnowszych", len(zost) == 200 and zost[0] == "202600005.jpg" and zost[-1] == "202600204.jpg", zost[:2])

# --- cavebot: pokrętło PYTAJ, tick nie czeka na wątek, migawka z pętli ---
import instancja
stare = cavebot.RATUNEK_HAIKU, cavebot.RATUNEK_HAIKU_PYTAJ, cavebot.log, instancja.S.logi
stare_env = _os.environ.pop("RETRONIC_TESTY")                      # cavebot._ratunek_zglos pisze plik tylko poza testami
zlog = []
with tempfile.TemporaryDirectory() as tmp:
    instancja.S.logi = Path(tmp)
    cavebot.log = zlog.append
    def atrapa_cb(**k):
        ns = types.SimpleNamespace(punkty=[(33106, 31849, 8)], wypad_aktywny=False, stan="IDZ", exp_teraz=1, tele=None, idx=0,
                                   zegar=lambda: ns.t, t=0.0, mapa=None, postac=types.SimpleNamespace(nazwa="Ja"),
                                   ratunek_g={"hp": 200, "max_hp": 250, "mana": 300, "max_mana": 425},
                                   ostatnie_stwory=[{"gracz": True, "nazwa": "Ja", "x": 33106, "y": 31849, "z": 6},
                                                    {"gracz": True, "nazwa": "Obcy", "x": 33108, "y": 31849, "z": 6, "hp": 100}], **k)
        for m in ("_ratunek_det", "_ratunek_zglos", "_ratunek_tick", "_ratunek_zdarzenie", "_ratunek_kontekst"):
            setattr(ns, m, types.MethodType(getattr(cavebot.Cavebot, m), ns))
        return ns
    def jazda(n=14):
        cb = atrapa_cb()
        for i in range(n):
            cb.t = float(i); cb._ratunek_tick(POZ, cb.t)
        return cb
    try:
        # pokrętło PYTAJ=0 (domyślne): sygnał jest, Haiku nie
        ratunek._DET = None; at = Atrapa(); ratunek_cien._CIEN = nowy(at)
        cavebot.RATUNEK_HAIKU, cavebot.RATUNEK_HAIKU_PYTAJ = 1, 0
        jazda(); poczekaj(ratunek_cien._CIEN)
        sprawdz("cavebot: PYTAJ=0 -> sygnał S2 w logu, zero wywołań Haiku", any("S2" in l for l in zlog) and at.n == 0, (zlog, at.n))
        sprawdz("cavebot: domyślna wartość pokrętła PYTAJ = 0", stare[1] == 0)
        # RATUNEK_HAIKU=0 (PYTAJ=1): nic
        ratunek._DET = None; at = Atrapa(); ratunek_cien._CIEN = nowy(at); zlog.clear()
        cavebot.RATUNEK_HAIKU, cavebot.RATUNEK_HAIKU_PYTAJ = 0, 1
        jazda(); poczekaj(ratunek_cien._CIEN)
        sprawdz("cavebot: RATUNEK_HAIKU=0 -> PYTAJ=1 nic nie robi", at.n == 0 and not zlog, (zlog, at.n))
        # oba 1: wołamy, a tick nie czeka na wolny model
        ratunek._DET = None; bramka = threading.Event(); at = Atrapa(bramka=bramka); ratunek_cien._CIEN = nowy(at); zlog.clear()
        cavebot.RATUNEK_HAIKU, cavebot.RATUNEK_HAIKU_PYTAJ = 1, 1
        t0 = time.monotonic(); cb = jazda(); dt = time.monotonic() - t0
        sprawdz("cavebot: tick nie czeka na wolny model (14 obiegów, model zablokowany)", dt < 1.0 and ratunek_cien._CIEN.watek.is_alive(), dt)
        for i in range(14, 20):                                   # dalsze obiegi w trakcie pytania: dalej bez czekania
            cb.t = float(i); cb._ratunek_tick(POZ, cb.t)
        bramka.set(); poczekaj(ratunek_cien._CIEN)
        pl = ratunek.plik_logu(Path(tmp)); h = hc(pl)
        sprawdz("cavebot: PYTAJ=1 -> jedno wywołanie, rekord haiku_cien z ruchem", at.n == 1 and len(h) == 1 and h[0]["kod"] == "S2"
                and h[0]["haiku_cien"]["ruch"] == "uzyj_pola 0,-1", (at.n, h))
        ctx = json.loads(at.prompty[0].split("\n", 1)[1])
        sprawdz("cavebot: migawka z pętli (HP, trasa, gracz bez nicku, brak nicku własnego)", ctx["hp_mana"]["hp"] == 200
                and ctx["cel"]["pietro_docelowe"] == 8 and "Obcy" not in at.prompty[0] and ctx["stwory_w_widoku"] == [{"typ": "gracz", "dx": 2, "dy": 0}], ctx)
        # limit z konfiguracji: LIMIT_H=1 -> drugi sygnał (S7) po zakończeniu pierwszego pominięty
        ratunek._DET = None; at = Atrapa(); ratunek_cien._CIEN = nowy(at)
        stary_lim = cavebot.RATUNEK_LIMIT_H; cavebot.RATUNEK_LIMIT_H = 1
        try:
            cb = jazda(); poczekaj(ratunek_cien._CIEN)
            for i in range(3):
                cb.t = 20.0 + i; cb._ratunek_zdarzenie("okrazenie", None)
            poczekaj(ratunek_cien._CIEN)
        finally:
            cavebot.RATUNEK_LIMIT_H = stary_lim
        pom = [r["haiku_cien"]["pominiety"] for r in hc(pl)][-1:]
        sprawdz("cavebot: limit z RATUNEK_LIMIT_H obejmuje wywołania Haiku", at.n == 1 and pom == ["limit_h"], (at.n, pom))
        # zrzut wołany tylko w wątku (nie w wątku pętli)
        gl = threading.current_thread()
        wat = []
        ratunek._DET = None; at = Atrapa(); ratunek_cien._CIEN = nowy(at, lambda: wat.append(threading.current_thread()) or b"\xff\xd8")
        jazda(); poczekaj(ratunek_cien._CIEN)
        sprawdz("zrzut i model w wątku-demonie, nie w pętli bota", wat and wat[0] is not gl and wat[0].daemon, wat)
    finally:
        cavebot.RATUNEK_HAIKU, cavebot.RATUNEK_HAIKU_PYTAJ, cavebot.log, instancja.S.logi = stare
        _os.environ["RETRONIC_TESTY"] = stare_env
        ratunek._DET = None; ratunek_cien._CIEN = None

# --- mozg i serwis: pokrętło PYTAJ ---
with tempfile.TemporaryDirectory() as tmp:
    import mozg, serwis, bot, io, contextlib
    stare = cavebot.RATUNEK_HAIKU, cavebot.RATUNEK_HAIKU_PYTAJ
    stare_s = instancja.S.na_zywo, instancja.S.logi
    _os.environ.pop("RETRONIC_TESTY")
    try:
        instancja.S.logi = Path(tmp)
        pos = types.SimpleNamespace(pozycja=lambda: POZ)
        for pyt, ocz in ((0, 0), (1, 1)):
            ratunek._DET = None; at = Atrapa(); ratunek_cien._CIEN = nowy(at)
            cavebot.RATUNEK_HAIKU, cavebot.RATUNEK_HAIKU_PYTAJ = 1, pyt
            mozg.ratunek_porazka(pos, "dojscie", log=lambda m: None, trasa="gobliny"); poczekaj(ratunek_cien._CIEN)
            sprawdz(f"mozg.ratunek_porazka: PYTAJ={pyt} -> {ocz} wywołań", at.n == ocz, at.n)
        instancja.S.na_zywo = Path(tmp) / "na_zywo.json"
        pos = types.SimpleNamespace(pozycja=lambda: (33176, 31828, 6))
        for js, ocz in (('{"RATUNEK_HAIKU": 1}', 0), ('{"RATUNEK_HAIKU": 1, "RATUNEK_HAIKU_PYTAJ": 1}', 1),
                        ('{"RATUNEK_HAIKU": 0, "RATUNEK_HAIKU_PYTAJ": 1}', 0)):
            instancja.S.na_zywo.write_text(js)
            ratunek._DET = None; at = Atrapa(); ratunek_cien._CIEN = nowy(at)
            with contextlib.redirect_stdout(io.StringIO()):
                serwis._ratunek_porazka(pos, "marsz", "6 nieudanych kroków", serwis.SerwisBlad("marsz", "x"), bot)
            poczekaj(ratunek_cien._CIEN)
            sprawdz(f"serwis._ratunek_porazka: {js} -> {ocz} wywołań", at.n == ocz, at.n)
    finally:
        cavebot.RATUNEK_HAIKU, cavebot.RATUNEK_HAIKU_PYTAJ = stare
        instancja.S.na_zywo, instancja.S.logi = stare_s
        _os.environ["RETRONIC_TESTY"] = "1"
        ratunek._DET = None; ratunek_cien._CIEN = None

# --- pokrętło w pokretla.py i przykładzie ---
import pokretla
sprawdz("pokretla: ZAKRESY ma RATUNEK_HAIKU_PYTAJ 0..1", pokretla.ZAKRESY.get("RATUNEK_HAIKU_PYTAJ") == (0, 1))
sprawdz("pokretla: analityk nie podnosi RATUNEK_HAIKU_PYTAJ (KIERUNEK nie_wyzej)", pokretla.KIERUNEK.get("RATUNEK_HAIKU_PYTAJ") == "nie_wyzej")
# przegląd 19.10: wyjście procesu nie czeka na cień i zawsze zabija claude, także gdy join przerwie SIGTERM (KeyboardInterrupt)
class _ModelZab:
    def __init__(self): self.zabity = False
    def zabij(self): self.zabity = True
class _WatekKI:
    def is_alive(self): return True
    def join(self, t=None): raise KeyboardInterrupt
_c = ratunek_cien.Cien(claude_fab=lambda t: None, zrzut=lambda: b"")
_c._model, _c.watek = _ModelZab(), _WatekKI()
try:
    _c._zabij(); _wyj = None
except BaseException as e:
    _wyj = e
sprawdz("wyjście: claude zabity mimo KeyboardInterrupt w join, wyjątek nie ucieka", _c._model.zabity and _wyj is None)
_c2 = ratunek_cien.Cien(claude_fab=lambda t: None, zrzut=lambda: b"")
_ev = threading.Event()
_c2._model = _ModelZab(); _c2.watek = threading.Thread(target=lambda: _ev.wait(30), daemon=True); _c2.watek.start()
_t0 = time.monotonic(); _c2._zabij(); _dt = time.monotonic() - _t0; _ev.set()
sprawdz("wyjście: wiszący wątek opóźnia koniec procesu najwyżej ~1 s", _c2._model.zabity and _dt < 1.5, f"{_dt:.2f} s")

pz = json.load(open(Path(__file__).resolve().parent.parent / "na_zywo.przyklad.json"))
sprawdz("na_zywo.przyklad.json: RATUNEK_HAIKU_PYTAJ = 0", pz.get("RATUNEK_HAIKU_PYTAJ") == 0 and pz.get("RATUNEK_HAIKU") == 0)

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
