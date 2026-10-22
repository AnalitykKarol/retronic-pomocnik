#!/usr/bin/env python3
"""nadzor.py (SPEC_nadzor_wykonawca_1021, F2 + biała lista): wykonawca na atrapach. Offline: katalog tymczasowy z fałszywymi
instancjami, fałszywe źródła stanu i fałszywy wykonawca (nic nie uruchamia, nie dotyka gry ani procesów).
Dowodzi: STOP_RECZNY = zero akcji; NADZOR_PAUZA = zero akcji; "nadzor": false; dwa końce zmian w tej samej minucie ->
wylogowania >= 7 min od siebie; restart bierze mapę z tryb.log (nie z env); restart nie w walce; eskalacja przy PK/GM/zgonie;
cień nic nie uruchamia i przy --raz nic nie zapisuje; pełny cykl logowanie -> bot -> WROC -> miasto -> wylogowanie.
Uruchomienie: python3 -I testy/test_nadzor.py"""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.dont_write_bytecode = True
KORZEN = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(KORZEN))
import grafik as G  # noqa: E402
import nadzor as N  # noqa: E402

T0 = datetime(2026, 10, 21, 11, 20, 0)
MAPY = {"_opis": "x", "raty": {"trasa": "thais_szczury_opt"}, "rook_x": {"trasa": "rook_raty_z9_petla"},
        "trolle_edron": {"trasa": "edron_trolle_petla"}, "thais_pn_z8": {"trasa": "thais_pn_z8_petla"}}


class Zegar:
    def __init__(self, t=T0):
        self.t = t

    def __call__(self):
        return self.t

    def dalej(self, **kw):
        self.t += timedelta(**kw)


class Swiat:
    """Fałszywe źródła stanu + katalog z instancjami."""

    def __init__(self, ids=("a", "b"), zegar=None):
        self.tmp = tempfile.TemporaryDirectory()
        self.k = Path(self.tmp.name)
        self.zegar = zegar or Zegar()
        self.inst, self.ekran_map, self.ip, self.tele, self.serwis_proc = {}, {}, {}, {}, {}
        self.ekw = {}                 # id -> {"lina": ..., "lopata": ...} dla Zrodla.ekwipunek (wybór spotu)
        (self.k / "instancje" / "_wspolne").mkdir(parents=True)
        (self.k / "mapy.json").write_text(json.dumps(MAPY))
        for i in ids:
            self.dodaj(i)

    def dodaj(self, id_, profil=None):
        kat = self.k / "instancje" / id_
        (kat / "logi").mkdir(parents=True, exist_ok=True)
        (kat / "profil.json").write_text(json.dumps(profil or {"postac": id_.capitalize()}))
        self.inst[id_] = {"id": id_, "sesja": False, "gra": False, "bot": False, "gracz": None, "panel": {}, "nick": id_, "mapa": None}

    def online(self, id_, bot=True, w_grze=True, level=None, **panel):
        r = self.inst[id_]
        gracz = ({"hp": 100, "max_hp": 100, **({"level": level} if level is not None else {})}) if w_grze else None
        r.update(sesja=True, gra=True, bot=bot, gracz=gracz, panel=dict(panel))

    def offline(self, id_):
        self.inst[id_].update(sesja=False, gra=False, bot=False, gracz=None, panel={})

    def plik(self, id_, nazwa):
        return self.k / "instancje" / id_ / nazwa

    def log(self, id_, linie, nazwa="mozg-stdout-1021-0900.log"):
        """linie: [(datetime, tekst)]"""
        self.plik(id_, "logi").mkdir(parents=True, exist_ok=True)
        with open(self.plik(id_, "logi") / nazwa, "a", encoding="utf-8") as f:
            for t, txt in linie:
                f.write(f"{t:%H:%M:%S} {txt}\n")

    def tryb_log(self, id_, mapa, tryb, t=None):
        t = t or self.zegar.t - timedelta(hours=1)
        with open(self.plik(id_, "logi") / "tryb.log", "a", encoding="utf-8") as f:
            f.write(f"{t:%Y-%m-%d %H:%M:%S} [TRYB] mapa {mapa}: trasa x, potwory Rat, prog-hp 30, dojście y\n")
            f.write(f"{t:%Y-%m-%d %H:%M:%S} [TRYB] tryb {tryb}: pokrętła {{}}\n")

    def grafik(self, zmiany, data="20261021"):
        G.zapisz({"data": data, "zrodlo": "reczny", "zmiany": zmiany}, self.k, kopia=False)

    # --- interfejs Zrodla ---
    def stan(self): return [dict(v) for v in self.inst.values()]
    def ekran(self, id_): return self.ekran_map.get(id_)
    def ip_zgodne(self, id_): return self.ip.get(id_)
    def telemetria(self, id_): return self.tele.get(id_, {})
    def procesy_serwisu(self, id_): return self.serwis_proc.get(id_, [])
    def ekwipunek(self, id_): return self.ekw.get(id_, {"lina": None, "lopata": None})


class Atrapa(N.WykonawcaCien):
    """Wykonawca 'na żywo' bez skutków ubocznych poza światem testu."""
    zywy = True

    def __init__(self, swiat):
        super().__init__()
        self.s = swiat
        self.czasy = []
        self.zapisuj_tryb = False     # True: start_bota dopisuje [TRYB] do tryb.log jak uruchom.sh (testy wyboru spotu)
        self.wyniki = {}              # nazwa -> (ok, tekst) wymuszone zamiast skutku w świecie
        self.hak = {}                 # nazwa -> funkcja wołana na początku metody (np. Karol przejmuje postać)

    def _pre(self, nazwa, *a):
        if nazwa in self.hak:
            self.hak[nazwa](*a)
        if nazwa in self.wyniki:
            self.czasy.append((self.s.zegar.t, nazwa, a))
            self.wywolania.append((nazwa,) + a)
            return self.wyniki[nazwa]
        return None

    def _w(self, nazwa, *a):
        self.czasy.append((self.s.zegar.t, nazwa, a))
        return super()._w(nazwa, *a)

    def sesja_start(self, id_):
        r = self._pre("sesja_start", id_)
        if r is not None:
            return r
        self.s.inst[id_].update(sesja=True)
        return self._w("sesja_start", id_)

    def zaloguj(self, id_):
        r = self._pre("zaloguj", id_)
        if r is not None:
            return r
        self.s.inst[id_].update(gra=True, gracz={"hp": 100, "max_hp": 100})
        return self._w("zaloguj", id_)

    def start_bota(self, id_, mapa, tryb):
        r = self._pre("start_bota", id_, mapa, tryb)
        if r is not None:
            return r
        self.s.inst[id_]["bot"] = True
        self.s.plik(id_, "STOP").unlink(missing_ok=True)
        if self.zapisuj_tryb:
            self.s.tryb_log(id_, mapa, tryb or "", self.s.zegar.t)
        return self._w("start_bota", id_, mapa, tryb)

    def zatrzymaj_bota(self, id_):
        r = self._pre("zatrzymaj_bota", id_)
        if r is not None:
            return r
        self.s.inst[id_]["bot"] = False
        return self._w("zatrzymaj_bota", id_)

    def wroc(self, id_):
        self.s.plik(id_, "WROC").touch()
        return self._w("wroc", id_)

    def serwis(self, id_):
        return self._w("serwis", id_)

    def wyloguj(self, id_):
        r = self._pre("wyloguj", id_)
        if r is not None:
            return r
        self.s.offline(id_)
        return self._w("wyloguj", id_)

    def powiadom(self, id_, tytul, tresc):
        r = self._pre("powiadom", id_, tytul, tresc)
        if r is not None:
            return r
        return self._w("powiadom", id_, tytul, tresc)

    def nazwy(self):
        return [w[0] for w in self.wywolania]


def nz(swiat, zywo=True, zapis=True):
    at = Atrapa(swiat)
    n = N.Nadzorca(swiat.k, swiat.zegar, swiat, at if zywo else N.WykonawcaCien(), zywo, zapis)
    return n, at


def zmiana(id_, od="2026-10-21 09:00", koniec="2026-10-21 11:00", wylog="2026-10-21 11:15", **kw):
    return {"id": id_, "od": od, "koniec": koniec, "wylog": wylog, "mapa": None, "tryb": None, **kw}


def w_miescie(swiat, id_):
    """Bot po WROC: stoi w depo (STOP), bez bota, panel mówi: w depo, miasto bez planu serwisu."""
    swiat.inst[id_].update(bot=False, panel={"w_depo": True, "w_miescie": "thais", "wroc_refill": "brak_planu"})
    swiat.plik(id_, "STOP").touch()


# ---------------------------------------------------------------- testy blokad
def test_stop_reczny_zero_akcji():
    s = Swiat(("a",))
    s.grafik([zmiana("a", od="2026-10-21 11:00", koniec="2026-10-21 13:30", wylog="2026-10-21 13:45")])
    s.plik("a", "STOP_RECZNY").touch()
    n, at = nz(s)
    for _ in range(5):                       # offline z aktywną zmianą: nie loguje
        n.tick()
        s.zegar.dalej(minutes=1)
    assert at.wywolania == [], at.wywolania
    s.online("a", bot=False)                 # Karol gra: sesja jest, bota brak, w logu PK: nawet powiadomienie to akcja
    s.log("a", [(s.zegar.t - timedelta(seconds=30), "ALARM: PK: gracz atakuje: Xyz (czaszka), uciekam do depo")])
    n.tick()
    assert at.wywolania == [], at.wywolania
    kod, txt = n.napraw("a", "restart")
    assert kod == 3 and "STOP_RECZNY" in txt and at.wywolania == [], (kod, txt)
    assert (s.plik("a", "STOP_RECZNY")).exists(), "STOP_RECZNY nietknięty"


def test_nadzor_pauza_zero_akcji():
    s = Swiat(("a", "b"))
    s.grafik([zmiana("a", od="2026-10-21 11:00", koniec="2026-10-21 13:30", wylog="2026-10-21 13:45")])
    (s.k / "instancje" / "_wspolne" / "NADZOR_PAUZA").touch()
    s.online("b", bot=True)
    s.log("b", [(s.zegar.t - timedelta(seconds=10), "ALARM_GM: gracz pisze")])
    n, at = nz(s)
    r = n.tick()
    assert at.wywolania == [] and r and r[0]["akcja"] == "pauza", (at.wywolania, r)
    assert n.napraw("b", "wroc")[0] == 3 and at.wywolania == []
    (s.k / "instancje" / "_wspolne" / "NADZOR_PAUZA").unlink()
    n.tick()
    assert "sesja_start" in at.nazwy() and "powiadom" in at.nazwy(), at.nazwy()      # po zdjęciu pauzy działa


def test_nadzor_false_poza_pula():
    s = Swiat(("a",))
    s.dodaj("c", {"postac": "C", "nadzor": False})
    s.grafik([zmiana("a", od="2026-10-21 11:00", koniec="2026-10-21 13:30", wylog="2026-10-21 13:45"),
              zmiana("c", od="2026-10-21 11:00", koniec="2026-10-21 13:30", wylog="2026-10-21 13:45")])
    n, at = nz(s)
    n.tick()
    cele = {w[1] for w in at.wywolania if len(w) > 1}
    assert cele == {"a"}, at.wywolania
    assert n.napraw("c", "wroc")[0] == 3


# ---------------------------------------------------------------- odstępy
def test_dwa_konce_zmian_w_tej_samej_minucie():
    s = Swiat(("a", "b"))
    s.grafik([zmiana("a"), zmiana("b")])                       # oba wylogowania zaplanowane na 11:15
    for i in ("a", "b"):
        s.online(i, bot=False)
        w_miescie(s, i)
    n, at = nz(s)
    for _ in range(40):
        n.tick()
        s.zegar.dalej(minutes=1)
    wyl = [(t, a[0]) for t, nazwa, a in at.czasy if nazwa == "wyloguj"]
    assert len(wyl) == 2, at.czasy
    assert (wyl[1][0] - wyl[0][0]) >= timedelta(minutes=7), wyl
    assert wyl[0][1] != wyl[1][1]
    # w jednym przebiegu nigdy dwie akcje logowania/wylogowania
    per_minuta = {}
    for t, nazwa, a in at.czasy:
        if nazwa in ("wyloguj", "sesja_start"):
            per_minuta[t] = per_minuta.get(t, 0) + 1
    assert max(per_minuta.values()) == 1, per_minuta


def test_odstep_po_zdarzeniu_zewnetrznym():
    s = Swiat(("a", "b"))
    s.grafik([zmiana("a", od="2026-10-21 11:22", koniec="2026-10-21 13:30", wylog="2026-10-21 13:45")])
    n, at = nz(s)
    n.tick()                                  # 11:20: stan odniesienia, nikt online, zmiana a jeszcze nie ruszyła
    s.zegar.dalej(minutes=3)
    s.online("b", bot=True)                   # 11:23: ktoś (Karol) zalogował b: zdarzenie zewnętrzne
    n.tick()
    assert "sesja_start" not in at.nazwy(), at.wywolania
    assert any(r["akcja"] == "odroczone" and "odstęp" in r["powod"] for r in n.dziennik.ostatnie), n.dziennik.ostatnie
    s.zegar.dalej(minutes=8)                  # 11:31: minęło > 7 min
    n.tick()
    assert "sesja_start" in at.nazwy(), at.nazwy()


def test_komplet_online():
    s = Swiat(("a", "b", "c"))
    s.grafik([zmiana(i, od="2026-10-21 11:00", koniec="2026-10-21 13:30", wylog="2026-10-21 13:45") for i in ("a", "b", "c")])
    s.k.joinpath("instancje", "_wspolne", "nadzor_konfig.json").write_text(json.dumps({"max_online": 2}))
    s.online("a")
    s.online("b")
    n, at = nz(s)
    n.tick()
    assert "sesja_start" not in at.nazwy(), at.wywolania
    assert any(r["akcja"] == "odroczone" and "komplet" in r["powod"] for r in n.dziennik.ostatnie), n.dziennik.ostatnie


def test_cisza_nocna():
    s = Swiat(("a",))
    s.zegar.t = datetime(2026, 10, 22, 2, 0, 0)
    s.grafik([zmiana("a", od="2026-10-21 23:00", koniec="2026-10-22 03:00", wylog="2026-10-22 03:15")])   # ręczna edycja łamie ciszę
    n, at = nz(s)
    n.tick()
    assert at.wywolania == [], at.wywolania


# ---------------------------------------------------------------- restart
def test_restart_mapa_z_tryb_log_a_nie_z_env():
    s = Swiat(("a",))
    s.grafik([zmiana("a", od="2026-10-21 09:00", koniec="2026-10-21 13:30", wylog="2026-10-21 13:45")])
    (s.k / "ostatni_start.a.env").write_text("MAPA=rook_x\nTRYB=ostrozny\n")      # nieaktualny env (lekcja 21.10 15:36)
    s.tryb_log("a", "raty", "ostrozny+ml", s.zegar.t - timedelta(hours=1))
    s.log("a", [(s.zegar.t - timedelta(minutes=50), "Mózg: tryb skrypt, postać A, trasa thais_szczury_opt (90 pkt, start 3), próg HP 30.0%, bez modelu.")])
    s.online("a", bot=True)
    s.tele["a"] = {"wiek_probki_s": 400, "stoi_poza_walka_s": 0}              # telemetria stara: bot zawieszony
    n, at = nz(s)
    n.tick()
    st = [w for w in at.wywolania if w[0] == "start_bota"]
    assert st and st[0][2] == "raty" and st[0][3] == "ostrozny,ml", at.wywolania
    assert "rook_x" not in json.dumps(at.wywolania)
    assert at.nazwy().index("zatrzymaj_bota") < at.nazwy().index("start_bota")
    assert not s.plik("a", "STOP_RECZNY").exists()


def test_restart_gdy_bot_wystartowal_po_wpisie_tryb_log():
    """tryb.log mówi 'raty', ale najnowszy bot (Mózg:) chodzi po trasie edron: prawda to to, co bot robi teraz."""
    s = Swiat(("a",))
    s.grafik([zmiana("a", od="2026-10-21 09:00", koniec="2026-10-21 13:30", wylog="2026-10-21 13:45")])
    s.tryb_log("a", "raty", "ostrozny", s.zegar.t - timedelta(hours=3))
    s.log("a", [(s.zegar.t - timedelta(minutes=50), "Mózg: tryb skrypt, postać A, trasa edron_trolle_petla (188 pkt, start 3), próg HP 30.0%, bez modelu.")])
    mapa, tryb, skad = N.mapa_tryb_biezace(s.k, "a", s.zegar.t)
    assert mapa == "trolle_edron" and "mozg" in skad, (mapa, tryb, skad)
    s.tryb_log("a", "thais_pn_z8", "ml", s.zegar.t - timedelta(minutes=5))        # świeższy wpis tryb.log bez nowego Mózg:
    mapa, tryb, skad = N.mapa_tryb_biezace(s.k, "a", s.zegar.t)
    assert mapa == "thais_pn_z8" and tryb == "ml" and skad == "tryb.log", (mapa, tryb, skad)


def test_restart_nie_w_walce():
    s = Swiat(("a",))
    s.grafik([zmiana("a", od="2026-10-21 09:00", koniec="2026-10-21 13:30", wylog="2026-10-21 13:45")])
    s.tryb_log("a", "raty", "ostrozny")
    s.online("a", bot=True)
    s.tele["a"] = {"wiek_probki_s": 400}
    s.log("a", [(s.zegar.t - timedelta(seconds=5), "[WALKA] Troll odl 1 HP 80%")])
    n, at = nz(s)
    n.tick()
    assert at.wywolania == [], at.wywolania
    kod, txt = n.napraw("a", "restart")
    assert kod == 3 and "walce" in txt and at.wywolania == [], (kod, txt)
    s.zegar.dalej(minutes=1)                                  # walka sprzed 65 s: spokój
    n.tick()
    assert "start_bota" in at.nazwy(), at.nazwy()


def test_wznow_po_alarmie_i_drabina():
    s = Swiat(("a",))
    s.grafik([zmiana("a", od="2026-10-21 09:00", koniec="2026-10-21 14:30", wylog="2026-10-21 14:45")])
    s.tryb_log("a", "raty", "ostrozny")
    s.online("a", bot=False)
    s.plik("a", "STOP").touch()
    s.log("a", [(s.zegar.t - timedelta(minutes=4), "ALARM: wyprawa: utkniecie: brak postępu na etapie 3"),
                (s.zegar.t - timedelta(minutes=4), "Zatrzymano (plik STOP).")])
    n, at = nz(s)
    n.stan["postacie"]["a"] = {"faza": "EXP", "bot_widziany": s.zegar.t.timestamp() - 600, "zmiana_od": "2026-10-21 09:00",
                               "login_ts": s.zegar.t.timestamp() - 7200}
    for i in range(4):
        n.tick()
        s.inst["a"]["bot"] = False                 # bot znowu pada
        s.plik("a", "STOP").touch()
        s.zegar.dalej(minutes=4)
    starty = [w for w in at.wywolania if w[0] == "start_bota"]
    assert len(starty) == 2, at.nazwy()            # wznow, wznow (brak spotu zapasowego, bot martwy: bez WROC), potem eskalacja
    nazwy = at.nazwy()
    assert nazwy.count("powiadom") == 1 and "wroc" not in nazwy, nazwy
    assert n.stan["postacie"]["a"].get("hold"), "po wyczerpaniu napraw postać wstrzymana do decyzji Karola"
    assert all(w[0] != "zatrzymaj_bota" for w in at.wywolania), "bot martwy: nie ma czego zatrzymywać"


def test_reczna_gra_bez_stop_recznego_nie_jest_przejmowana():
    """Postać w grze, bota brak, brak STOP i brak STOP_RECZNY, a nadzór nigdy nie widział tu bota: może Karol gra. Zero akcji."""
    s = Swiat(("a",))
    s.grafik([zmiana("a", od="2026-10-21 09:00", koniec="2026-10-21 14:30", wylog="2026-10-21 14:45")])
    s.tryb_log("a", "raty", "ostrozny")
    s.online("a", bot=False)
    n, at = nz(s)
    for _ in range(5):
        n.tick()
        s.zegar.dalej(minutes=3)
    assert at.wywolania == [], at.wywolania
    s.inst["a"]["bot"] = True                  # od teraz bot jest znany: jego upadek to awaria do naprawy
    n.tick()
    s.zegar.dalej(minutes=1)
    s.inst["a"]["bot"] = False
    n.tick()
    assert "start_bota" in at.nazwy(), at.nazwy()


def test_trasa_z_mozg_normalizacja_patrol_nie_jest_rookiem():
    """Regresja z cienia na żywych danych (21.10): `Mózg: … trasa patrol(troll)` a mapy.json `patrol:troll`; dopasowanie po
    prefiksie `patrol` dawało mapę 'rook' (złe miasto) dla invincible."""
    s = Swiat(("a",))
    (s.k / "mapy.json").write_text(json.dumps({**MAPY, "trolle_patrol": {"trasa": "patrol:troll"}, "rook": {"trasa": "patrol"}}))
    s.tryb_log("a", "trolle_patrol", "ostrozny+runy", s.zegar.t - timedelta(minutes=30))
    s.log("a", [(s.zegar.t - timedelta(minutes=29), "Mózg: tryb skrypt, postać A, trasa patrol(troll) (116 pkt, start 113), próg HP 30.0%, bez modelu.")])
    assert N.mapa_tryb_biezace(s.k, "a", s.zegar.t)[:2] == ("trolle_patrol", "ostrozny,runy")
    s.tryb_log("a", "rook_x", "ostrozny", s.zegar.t - timedelta(minutes=40))      # starszy wpis tryb.log, bot wystartował później
    s2 = Swiat(("b",))
    (s2.k / "mapy.json").write_text(json.dumps({**MAPY, "trolle_patrol": {"trasa": "patrol:troll"}, "rook": {"trasa": "patrol"}}))
    s2.tryb_log("b", "rook_x", "ostrozny", s2.zegar.t - timedelta(hours=2))
    s2.log("b", [(s2.zegar.t - timedelta(minutes=29), "Mózg: tryb skrypt, postać B, trasa patrol(troll) (116 pkt, start 113), próg HP 30.0%, bez modelu.")])
    assert N.mapa_tryb_biezace(s2.k, "b", s2.zegar.t)[0] == "trolle_patrol"      # prawda to to, co bot robi (nie prefiks 'rook')


def test_zmien_spot_na_zapasowy():
    s = Swiat(("a", "b"))
    s.dodaj("a", {"postac": "A", "spoty_zapasowe": ["thais_pn_z8", {"mapa": "trolle_edron", "tryb": "ostrozny"}]})
    s.tryb_log("a", "raty", "ostrozny")
    s.log("a", [(s.zegar.t - timedelta(minutes=50), "Mózg: tryb skrypt, postać A, trasa thais_szczury_opt (90 pkt, start 3), próg HP 30.0%, bez modelu.")])
    s.online("a", bot=True)
    n, at = nz(s)
    n._raw = {"a": s.inst["a"]}
    mapa, tryb, _ = N.mapa_tryb_biezace(s.k, "a", s.zegar.t)
    assert n.spot_zapasowy("a", mapa, set()) == ("thais_pn_z8", None)
    assert n.spot_zapasowy("a", "thais_pn_z8", set()) == ("trolle_edron", "ostrozny")
    assert n.spot_zapasowy("a", "raty", {"thais_pn_z8"}) == ("trolle_edron", "ostrozny")      # zajęty przez inny bot: pomija
    kod, txt = n.napraw("a", "zmien_spot")
    assert kod == 0, txt
    st = [w for w in at.wywolania if w[0] == "start_bota"]
    assert st and st[0][2] == "thais_pn_z8" and st[0][3] == "ostrozny", at.wywolania


# ---------------------------------------------------------------- eskalacje
def test_eskalacja_pk():
    s = Swiat(("a",))
    s.grafik([zmiana("a", od="2026-10-21 09:00", koniec="2026-10-21 14:30", wylog="2026-10-21 14:45")])
    s.online("a", bot=True)
    s.log("a", [(s.zegar.t - timedelta(minutes=1), "ALARM: PK: gracz atakuje: Pulldunker (czaszka), uciekam do depo")])
    n, at = nz(s)
    n.tick()
    pow_ = [w for w in at.wywolania if w[0] == "powiadom"]
    assert len(pow_) == 1 and "PK" in pow_[0][3], at.wywolania
    assert set(at.nazwy()) == {"powiadom"}, "po PK żadnych napraw"
    assert n.stan["postacie"]["a"].get("hold")
    for _ in range(3):
        s.zegar.dalej(minutes=2)
        n.tick()
    assert at.nazwy() == ["powiadom"], at.nazwy()            # wstrzymana: bez ponownego powiadomienia i bez akcji
    assert n.napraw("a", "restart")[0] == 3
    assert "odblokowano" in n.odblokuj("a")
    # to samo zdarzenie nie eskaluje drugi raz po odblokowaniu
    s.zegar.dalej(minutes=2)
    n.tick()
    assert at.nazwy().count("powiadom") == 1, at.nazwy()


def test_eskalacje_gm_zgon_ip_nieustalony_i_stare_zdarzenie():
    for log_txt, klucz in (("ALARM_GM: gracz pisze 'bot?'", "GM"), ("Bot zginął: MARTWY", "zgon")):
        s = Swiat(("a",))
        s.online("a", bot=True)
        s.log("a", [(s.zegar.t - timedelta(minutes=2), log_txt)])
        n, at = nz(s)
        n.tick()
        assert at.nazwy() == ["powiadom"] and klucz.lower() in at.wywolania[0][3].lower(), (klucz, at.wywolania)
    s = Swiat(("a",))
    s.online("a", bot=True)
    s.ip["a"] = False
    n, at = nz(s)
    n.tick()
    assert at.nazwy() == ["powiadom"] and "IP" in at.wywolania[0][3], at.wywolania
    # stare zdarzenie (> 30 min) nie budzi Karola
    s = Swiat(("a",))
    s.online("a", bot=True)
    s.log("a", [(s.zegar.t - timedelta(minutes=50), "ALARM: PK: gracz atakuje: X (czaszka), uciekam do depo")])
    n, at = nz(s)
    n.tick()
    assert "powiadom" not in at.nazwy(), at.wywolania
    # stan nieustalony dopiero po 10 min
    s = Swiat(("a",))
    s.online("a", bot=False, w_grze=False)
    n, at = nz(s)
    n.tick()
    assert at.wywolania == []
    s.zegar.dalej(minutes=11)
    n.tick()
    assert at.nazwy() == ["powiadom"] and "nieustalony" in at.wywolania[0][3], at.wywolania


def test_online_bez_uwag_nic_nie_robi():
    s = Swiat(("a",))
    s.online("a", bot=True)
    n, at = nz(s)
    n.tick()
    assert at.wywolania == [], at.wywolania


# ---------------------------------------------------------------- koniec zmiany
def test_koniec_zmiany_pelny_plecak_ale_nie_slot_ukryty():
    for powod, oczekiwane in (("sloty_pelne", True), ("slot_ukryty", False), ("za_ciezki", True)):
        s = Swiat(("a",))
        s.grafik([zmiana("a", od="2026-10-21 09:00", koniec="2026-10-21 16:00", wylog="2026-10-21 16:15")])
        s.online("a", bot=True)
        s.log("a", [(s.zegar.t - timedelta(minutes=m), f"loot: pełny plecak: powód {powod} (gold coin x4; zajęte 13/20, widoczne 12, cap 115.0, waga 0.1)")
                    for m in (4, 3, 2)])
        n, at = nz(s)
        n.stan["postacie"]["a"] = {"faza": "EXP", "login_ts": s.zegar.t.timestamp() - 3600, "zmiana_od": "2026-10-21 09:00",
                                   "bot_start": s.zegar.t.timestamp() - 3000}
        n.tick()
        assert ("wroc" in at.nazwy()) == oczekiwane, (powod, at.wywolania)


def test_koniec_zmiany_brak_jedzenia_i_czas():
    s = Swiat(("a", "b"))
    s.grafik([zmiana("a", od="2026-10-21 09:00", koniec="2026-10-21 16:00", wylog="2026-10-21 16:15"),
              zmiana("b", od="2026-10-21 08:30", koniec="2026-10-21 11:10", wylog="2026-10-21 11:25")])
    s.online("a", bot=True)
    s.online("b", bot=True)
    s.log("a", [(s.zegar.t - timedelta(minutes=m), "Zjedzono: nic (brak jedzenia) [jedzenie: brak jedzenia w plecaku]") for m in (6, 3)])
    n, at = nz(s)
    for i in ("a", "b"):
        n.stan["postacie"][i] = {"faza": "EXP", "login_ts": s.zegar.t.timestamp() - 3600, "bot_start": s.zegar.t.timestamp() - 3000}
    n.tick()
    assert sorted(w[1] for w in at.wywolania if w[0] == "wroc") == ["a", "b"], at.wywolania


# ---------------------------------------------------------------- rozłączenie
def test_rozlaczenie_relog_i_wyczerpanie():
    s = Swiat(("a",))
    s.grafik([zmiana("a", od="2026-10-21 09:00", koniec="2026-10-21 16:00", wylog="2026-10-21 16:15")])
    s.online("a", bot=True, w_grze=False)
    s.inst["a"]["gra"] = True
    s.log("a", [(s.zegar.t - timedelta(minutes=3), "ROŁĄCZENIE".replace("ROŁĄ", "ROZŁĄ") + ": pamięć gry stoi 25 s, a zrzut pokazuje ekran logowania.")])
    n, at = nz(s)
    n.stan["postacie"]["a"] = {"faza": "EXP", "login_ts": s.zegar.t.timestamp() - 7200, "zmiana_od": "2026-10-21 09:00"}
    n.tick()
    assert "zaloguj" in at.nazwy() and "sesja_start" not in at.nazwy(), at.wywolania      # sesja jest: tylko zaloguj
    assert at.czasy[0][2] == ("a",)
    # trzy relogi w oknie i dalej rozłączony -> eskalacja
    for _ in range(4):
        s.zegar.dalej(minutes=8)
        s.inst["a"]["gracz"] = None
        n.stan["postacie"]["a"]["faza"] = "EXP"
        n.stan["postacie"]["a"]["akcje_ts"] = {}
        n.tick()
    assert "powiadom" in at.nazwy(), at.nazwy()


# ---------------------------------------------------------------- cień
def test_cien_nic_nie_uruchamia_i_raz_nic_nie_zapisuje():
    s = Swiat(("a", "b"))
    s.grafik([zmiana("a", od="2026-10-21 11:00", koniec="2026-10-21 13:30", wylog="2026-10-21 13:45")])
    s.online("b", bot=True)
    s.log("b", [(s.zegar.t - timedelta(seconds=30), "ALARM: PK: gracz atakuje: X (czaszka), uciekam do depo")])
    przed = sorted(str(p.relative_to(s.k)) for p in s.k.rglob("*"))
    n, at = nz(s, zywo=False, zapis=False)
    r = n.tick()
    assert at.wywolania == [], "cień nie woła wykonawcy"
    po = sorted(str(p.relative_to(s.k)) for p in s.k.rglob("*"))
    assert przed == po, set(po) ^ set(przed)
    wyniki = {(x["id"], x["akcja"], x["wynik"]) for x in r}
    assert ("a", "sesja_start", "cień") in wyniki and ("b", "eskaluj", "cień") in wyniki, wyniki
    # cień z zapisem: log i stan powstają, powtórka tej samej decyzji nie dubluje wpisów
    n, at = nz(s, zywo=False, zapis=True)
    n.tick()
    s.zegar.dalej(minutes=1)
    n.tick()
    pliki = list((s.k / "instancje" / "_wspolne" / "logi").glob("nadzor-*.jsonl"))
    assert len(pliki) == 1
    linie = [json.loads(l) for l in pliki[0].read_text().splitlines()]
    assert all(x["tryb"] == "cien" and x["powod"] for x in linie), linie
    assert sum(1 for x in linie if x["id"] == "a" and x["akcja"] == "sesja_start") == 1, "powtórka cienia nie dubluje wpisu"
    assert at.wywolania == []


def test_cien_odstep_miedzy_wirtualnymi_logowaniami():
    s = Swiat(("a", "b", "c"))
    s.grafik([zmiana(i, od="2026-10-21 11:00", koniec="2026-10-21 13:30", wylog="2026-10-21 13:45") for i in ("a", "b", "c")])
    n, at = nz(s, zywo=False, zapis=False)
    starty = []
    for minuta in range(25):
        for r in n.tick():
            if r["akcja"] == "sesja_start":
                starty.append((s.zegar.t, r["id"]))
        s.zegar.dalej(minutes=1)
    assert len(starty) == 3, starty
    assert all((b[0] - a[0]) >= timedelta(minutes=7) for a, b in zip(starty, starty[1:])), starty


# ---------------------------------------------------------------- pełny cykl
def test_pelny_cykl_postaci():
    s = Swiat(("a",))
    s.zegar.t = datetime(2026, 10, 21, 9, 0, 0)
    s.grafik([zmiana("a", od="2026-10-21 09:00", koniec="2026-10-21 11:00", wylog="2026-10-21 11:15")])
    s.tryb_log("a", "raty", "ostrozny,ml", datetime(2026, 10, 21, 8, 0, 0))
    n, at = nz(s)
    s.inst["a"]["bot"] = False
    kroki = []

    def tik(min=1):
        n.tick()
        s.zegar.dalej(minutes=min)
        kroki.append(list(at.nazwy()))

    tik()                                              # 09:00 sesja_start
    assert at.nazwy() == ["sesja_start"], at.nazwy()
    s.inst["a"]["gra"] = True                          # klient wstał, ekran logowania (gracz None)
    tik(2)
    assert at.nazwy()[-1] == "zaloguj", at.nazwy()
    tik()                                              # w grze: start bota z tryb.log
    assert at.wywolania[-1] == ("start_bota", "a", "raty", "ostrozny,ml"), at.wywolania
    assert n.stan["postacie"]["a"]["faza"] == "DOJSCIE"
    s.zegar.t = datetime(2026, 10, 21, 10, 0, 0)
    s.log("a", [(s.zegar.t - timedelta(minutes=2), "Cel Rat zabity na (1, 2, 8).")], nazwa="mozg-stdout-1021-0905.log")
    tik()
    assert n.stan["postacie"]["a"]["faza"] == "EXP" and at.nazwy().count("wroc") == 0
    s.zegar.t = datetime(2026, 10, 21, 11, 1, 0)       # koniec zmiany z grafiku
    tik()
    assert at.nazwy()[-1] == "wroc", at.nazwy()
    tik()
    assert n.stan["postacie"]["a"]["faza"] == "POWROT"
    assert at.nazwy().count("wroc") == 1, "WROC raz, potem czekanie"
    s.plik("a", "WROC").unlink()                       # bot wziął zlecenie, dojechał, stanął
    w_miescie(s, "a")
    tik()
    assert n.stan["postacie"]["a"]["faza"] in ("MIASTO", "WYLOGOWANIE"), n.stan["postacie"]["a"]
    s.zegar.t = datetime(2026, 10, 21, 11, 16, 0)
    tik()
    assert at.nazwy()[-1] == "wyloguj", at.nazwy()
    assert n.stan["postacie"]["a"]["faza"] == "OFFLINE"
    assert n.stan["minuty"]["20261021"]["a"] > 100, n.stan["minuty"]
    # po wylogowaniu ta sama zmiana nie startuje drugi raz
    for _ in range(3):
        tik(10)
    assert at.nazwy().count("sesja_start") == 1, at.nazwy()
    # wpisy w logu mają uzasadnienie
    p = next((s.k / "instancje" / "_wspolne" / "logi").glob("nadzor-*.jsonl"))
    wpisy = [json.loads(l) for l in p.read_text().splitlines()]
    assert all(w["powod"] for w in wpisy) and {w["akcja"] for w in wpisy} >= {"sesja_start", "zaloguj", "start_bota", "wroc", "wyloguj"}


def test_wylogowanie_czeka_na_spokoj_max_15_min():
    s = Swiat(("a",))
    s.grafik([zmiana("a")])
    s.online("a", bot=False)
    w_miescie(s, "a")
    n, at = nz(s)
    for minuta in range(20):
        s.log("a", [(s.zegar.t - timedelta(seconds=5), "[WALKA] Rat odl 1 HP 50%")], nazwa="mozg-stdout-1021-1100.log")
        n.tick()
        if "wyloguj" in at.nazwy():
            break
        s.zegar.dalej(minutes=1)
    assert "wyloguj" in at.nazwy(), at.nazwy()
    t_wyl = next(t for t, nazwa, _ in at.czasy if nazwa == "wyloguj")
    assert (t_wyl - T0) >= timedelta(minutes=14), t_wyl             # czekał na spokój prawie 15 min
    assert (t_wyl - T0) <= timedelta(minutes=17), t_wyl


# ---------------------------------------------------------------- biała lista
def test_biala_lista_i_zakazy():
    s = Swiat(("a",))
    s.online("a", bot=True)
    n, at = nz(s)
    for zly in ("zatrzymaj", "czat", "pokretla", "stop_reczny", "konto", "ogien"):
        kod, txt = n.napraw("a", zly)
        assert kod == 2 and "białej listy" in txt, (zly, kod, txt)
    assert at.wywolania == []
    kod, txt = n.napraw("a", "wroc")
    assert kod == 0 and at.nazwy() == ["wroc"], (kod, txt)
    assert not s.plik("a", "STOP_RECZNY").exists()
    assert set(N.BIALA_LISTA) == {"restart", "wznow", "wroc", "relog", "wyloguj", "zmien_spot", "okna"}
    kod, txt = n.napraw("a", "wyloguj")                               # bot działa: najpierw wroc
    assert kod == 3 and "wroc" in txt
    kod, txt = n.napraw("a", "wznow")
    assert kod == 3
    kod, txt = n.napraw("nieznany", "wroc")
    assert kod == 2


def test_wykonawca_zywy_brak_narzedzia_i_miekkie_zatrzymanie():
    with tempfile.TemporaryDirectory() as tmp:
        w = N.WykonawcaZywy(tmp)
        ok, txt = w._skrypt("nie_ma_takiego.sh", "a", 5)
        assert not ok and "brak narzędzia" in txt
        ok, txt = w.start_bota("a", None, None)
        assert not ok and "mapa" in txt


def test_analiza_logu_sygnaly():
    t = datetime(2026, 10, 21, 12, 0, 0)
    f = lambda sec, txt: ((t - timedelta(seconds=sec)).timestamp(), txt)       # noqa: E731
    a = N.analizuj_log([f(900, "Mózg: tryb skrypt, postać A, trasa x_petla (1 pkt, start 1), próg HP 30.0%, bez modelu."),
                        f(300, "Cel Rat zabity na (1, 2, 8)."), f(200, "[OGIEN] debug"), f(100, "ALARM: wyprawa: utkniecie: brak postępu"),
                        f(60, "Wyprawa: DEPO osiągnięte w (1, 2, 7), koniec wyprawy, zatrzymuję bota"), f(59, "Zatrzymano (plik STOP).")],
                       t.timestamp())
    assert a["trasa"] == "x_petla" and a["zabicia_od_startu"] == 1 and a["alarm"] and a["depo"] and a["stop"] and not a["walka"]
    assert a["pk"] is None and a["gm"] is None and a["zgon"] is None
    a = N.analizuj_log([f(10, "[WALKA] Troll odl 2 HP 30%")], t.timestamp())
    assert a["walka"]
    a = N.analizuj_log([f(30, "ALARM: niskie HP 35%")], t.timestamp())
    assert a["alarm"] is None, "niskie HP to nie 'inny alarm'"


# ---------------------------------------------------------------- poprawki po checkerze (B-1 .. B-5)
def test_b1_cisza_blokuje_tryb_na_zywo():
    s = Swiat(("a", "b"))
    s.grafik([zmiana("a", od="2026-10-21 11:00", koniec="2026-10-21 13:30", wylog="2026-10-21 13:45")])
    (s.k / "cisza").touch()                                  # plik cisza wycisza powiadom.py (decyzja Karola, nie ruszamy)
    s.online("b", bot=True)
    s.log("b", [(s.zegar.t - timedelta(seconds=20), "ALARM: PK: gracz atakuje: X (czaszka), uciekam do depo")])
    n, at = nz(s, zywo=True)
    r = n.tick()
    assert at.wywolania == [], "żywy tryb nie startuje: zero akcji i zero wstrzymań"
    assert not n.stan["postacie"].get("b", {}).get("hold")
    assert any(x["akcja"] == "zywy_zablokowany" and "cisza" in x["powod"] for x in r), r
    assert any(x["akcja"] == "eskaluj" and x["wynik"] == "cień" and "niewidoczne" in x["szczegol"] for x in r), r
    assert n.napraw("b", "wroc")[0] == 3 and at.wywolania == []
    st = n.podsumowanie()
    assert "plik cisza" in st["powiadomienia_wylaczone"] and any("NIEWIDOCZNE" in u for u in st["uwagi"]), st
    # cień też ostrzega
    n2, _ = nz(s, zywo=False, zapis=False)
    assert any(x["akcja"] == "ostrzezenie" and "niewidoczne: plik cisza" in x["powod"] for x in n2.tick())
    # po usunięciu pliku żywy tryb działa
    (s.k / "cisza").unlink()
    n3, at3 = nz(s, zywo=True)
    n3.tick()
    assert "powiadom" in at3.nazwy()
    # zmienna środowiskowa to ten sam wyłącznik
    os.environ["RETRONIC_POWIADOMIENIA"] = "0"
    try:
        n4, at4 = nz(s, zywo=True)
        n4.tick()
        assert at4.wywolania == [] and n4.powiadomienia_wylaczone() == "RETRONIC_POWIADOMIENIA=0"
    finally:
        del os.environ["RETRONIC_POWIADOMIENIA"]


def test_b1_hold_bez_dostarczonego_powiadomienia_jest_widoczny_i_ponawiany():
    s = Swiat(("a",))
    s.online("a", bot=True)
    s.log("a", [(s.zegar.t - timedelta(seconds=20), "ALARM_GM: gracz pisze 'bot?'")])
    n, at = nz(s, zywo=True)
    at.wyniki["powiadom"] = (False, "powiadomienie wyciszone (limit)")
    n.tick()
    h = n.stan["postacie"]["a"]["hold"]
    assert h["powiadomiono"] is False, h
    assert "NIE DOTARŁO" in n.bramka("a"), n.bramka("a")
    assert any("WSTRZYMANA BEZ DOSTARCZONEGO POWIADOMIENIA" in u for u in n.podsumowanie()["uwagi"])
    del at.wyniki["powiadom"]                                 # powiadomienia znów działają
    s.zegar.dalej(minutes=1)
    n.tick()
    assert n.stan["postacie"]["a"]["hold"]["powiadomiono"] is True
    assert at.nazwy().count("powiadom") == 2
    assert not any("WSTRZYMANA BEZ" in u for u in n.podsumowanie()["uwagi"])


def test_b2_bramka_ponownie_tuz_przed_akcja():
    # STOP_RECZNY pojawia się między decyzją a wykonaniem (w tym samym przebiegu)
    s = Swiat(("a",))
    s.grafik([zmiana("a", od="2026-10-21 11:00", koniec="2026-10-21 13:30", wylog="2026-10-21 13:45")])
    n, at = nz(s)
    oryg = n.decyduj

    def decyduj_i_przejecie(id_, o, plan, teraz):
        r = oryg(id_, o, plan, teraz)
        s.plik(id_, "STOP_RECZNY").touch()                    # Karol kliknął Stop po wydaniu decyzji
        return r
    n.decyduj = decyduj_i_przejecie
    n.tick()
    assert at.wywolania == [], at.wywolania
    # NADZOR_PAUZA tuż przed akcją
    s2 = Swiat(("a",))
    s2.grafik([zmiana("a", od="2026-10-21 11:00", koniec="2026-10-21 13:30", wylog="2026-10-21 13:45")])
    n2, at2 = nz(s2)
    o2 = n2.decyduj
    n2.decyduj = lambda *a: (lambda r: (s2.k.joinpath("instancje", "_wspolne", "NADZOR_PAUZA").touch(), r)[1])(o2(*a))
    n2.tick()
    assert at2.wywolania == [], at2.wywolania


def test_b2_start_bota_nigdy_gdy_stop_reczny_pojawil_sie_w_trakcie_restartu():
    s = Swiat(("a",))
    s.grafik([zmiana("a", od="2026-10-21 09:00", koniec="2026-10-21 13:30", wylog="2026-10-21 13:45")])
    s.tryb_log("a", "raty", "ostrozny")
    s.online("a", bot=True)
    s.tele["a"] = {"wiek_probki_s": 400}                      # zawieszony -> restart
    n, at = nz(s)
    at.hak["zatrzymaj_bota"] = lambda id_: s.plik(id_, "STOP_RECZNY").touch()      # Karol przejmuje w czasie zatrzymania bota
    n.tick()
    assert "zatrzymaj_bota" in at.nazwy() and "start_bota" not in at.nazwy(), at.nazwy()
    assert s.plik("a", "STOP_RECZNY").exists()
    # to samo dla zaplanowanego startu po zalogowaniu
    s = Swiat(("a",))
    s.grafik([zmiana("a", od="2026-10-21 09:00", koniec="2026-10-21 13:30", wylog="2026-10-21 13:45")])
    s.zegar.t = datetime(2026, 10, 21, 9, 5)
    s.tryb_log("a", "raty", "ostrozny")
    n, at = nz(s)
    n.tick()                                                 # sesja_start
    s.inst["a"].update(gra=True, gracz={"hp": 1, "max_hp": 1})
    at.hak["start_bota"] = lambda id_, mapa, tryb: s.plik(id_, "STOP_RECZNY").touch()
    s.zegar.dalej(minutes=2)
    n.tick()
    assert "start_bota" in at.nazwy()                        # hak woła się przy wejściu do metody; bramka sprawdzona PRZED nią nie widziała pliku


def test_b3_stop_bez_dowodu_miasta_to_nie_serwis_ani_wylogowanie():
    s = Swiat(("a",))
    s.grafik([zmiana("a")])                                  # koniec zmiany już minął (11:00 < 11:20)
    s.online("a", bot=False)                                 # w grze, bez bota, STOP po alarmie w połowie WROC
    s.plik("a", "STOP").touch()
    s.tryb_log("a", "raty", "ostrozny")
    s.log("a", [(s.zegar.t - timedelta(minutes=3), "Wyprawa: start (depo:reczny), baza troll, przystanki ['depo']"),
                (s.zegar.t - timedelta(minutes=2), "ALARM: wyprawa: utkniecie: brak postępu na etapie 2"),
                (s.zegar.t - timedelta(minutes=2), "Zatrzymano (plik STOP).")])
    n, at = nz(s)
    n.stan["postacie"]["a"] = {"faza": "POWROT", "bot_widziany": s.zegar.t.timestamp() - 600, "zmiana_od": "2026-10-21 09:00",
                               "login_ts": s.zegar.t.timestamp() - 7200, "powrot_od": s.zegar.t.timestamp() - 300, "koniec": "czas"}
    n.tick()
    assert "wyloguj" not in at.nazwy() and "serwis" not in at.nazwy(), at.nazwy()
    assert at.nazwy() == ["start_bota"], at.nazwy()          # wznowienie (potem koniec zmiany znów zleci WROC)
    assert n.stan["postacie"]["a"]["faza"] != "MIASTO"
    # ten sam stan, ale z dodatnim dowodem (panel: w_depo) -> miasto i wylogowanie
    s2 = Swiat(("a",))
    s2.grafik([zmiana("a")])
    s2.online("a", bot=False)
    w_miescie(s2, "a")
    n2, at2 = nz(s2)
    n2.stan["postacie"]["a"] = {"faza": "POWROT", "bot_widziany": s2.zegar.t.timestamp() - 600, "zmiana_od": "2026-10-21 09:00",
                                "login_ts": s2.zegar.t.timestamp() - 7200, "koniec": "czas"}
    n2.tick()
    assert at2.nazwy() == ["wyloguj"], at2.nazwy()


def test_b4_zalegajacy_stop_nie_blokuje_startu_nastepnej_zmiany():
    s = Swiat(("a",))
    s.zegar.t = datetime(2026, 10, 21, 9, 0)
    s.grafik([zmiana("a", od="2026-10-21 09:00", koniec="2026-10-21 11:00", wylog="2026-10-21 11:15"),
              zmiana("a", od="2026-10-21 13:00", koniec="2026-10-21 15:00", wylog="2026-10-21 15:15")])
    s.tryb_log("a", "raty", "ostrozny", datetime(2026, 10, 21, 8, 0))
    n, at = nz(s)

    def tik(m=1):
        n.tick()
        s.zegar.dalej(minutes=m)
    tik()
    s.inst["a"]["gra"] = True
    tik(2)
    tik()
    assert "start_bota" in at.nazwy()
    s.zegar.t = datetime(2026, 10, 21, 11, 1)
    tik()                                                    # wroc
    s.plik("a", "WROC").unlink()
    w_miescie(s, "a")                                        # zostaje plik STOP
    tik()
    s.zegar.t = datetime(2026, 10, 21, 11, 16)
    tik()
    assert at.nazwy()[-1] == "wyloguj" and s.plik("a", "STOP").exists(), at.nazwy()
    # druga zmiana: STOP nadal leży w katalogu instancji (Atrapa.start_bota w tym teście go nie kasuje do chwili wywołania)
    s.zegar.t = datetime(2026, 10, 21, 13, 0)
    tik()
    assert at.nazwy().count("sesja_start") == 2, at.nazwy()
    s.inst["a"].update(gra=True, gracz={"hp": 1, "max_hp": 1})
    s.plik("a", "STOP").touch()
    stare = at.nazwy().count("start_bota")
    tik(2)
    tik()
    assert at.nazwy().count("start_bota") == stare + 1, at.nazwy()
    ost = [x for x in n.dziennik.ostatnie if x["akcja"] == "start_bota"][-1]
    assert ost["powod"].startswith("zalogowany, start bota") and "zalegający STOP" in ost["powod"], ost      # planowy start, nie "naprawa"
    assert not n.stan["postacie"]["a"].get("naprawy"), "zalegający STOP nie liczy się jako awaria"
    # a przy STOP_RECZNY nic: ani logowanie, ani start
    s2 = Swiat(("a",))
    s2.zegar.t = datetime(2026, 10, 21, 13, 5)
    s2.grafik([zmiana("a", od="2026-10-21 13:00", koniec="2026-10-21 15:00", wylog="2026-10-21 15:15")])
    s2.plik("a", "STOP_RECZNY").touch()
    n2, at2 = nz(s2)
    n2.tick()
    assert at2.wywolania == []


def test_b5_wylogowanie_nieudane_trzy_razy_eskaluje():
    for kod_txt, oczekiwany_hold in (("kod 5: brak spokoju (walka)", False), ("kod 7: ekran nierozpoznany", False), ("kod 6: zgon", True)):
        s = Swiat(("a",))
        s.grafik([zmiana("a")])
        s.online("a", bot=False)
        w_miescie(s, "a")
        n, at = nz(s)
        at.wyniki["wyloguj"] = (False, kod_txt)
        for _ in range(6):
            n.tick()
            s.zegar.dalej(minutes=3)
        nazwy = at.nazwy()
        if oczekiwany_hold:
            assert nazwy.count("wyloguj") == 1 and nazwy.count("powiadom") == 1 and n.stan["postacie"]["a"].get("hold"), nazwy
        else:
            assert nazwy.count("wyloguj") == 3 and nazwy.count("powiadom") == 1, nazwy
            assert "nieustalony" in at.wywolania[-1][3] and not n.stan["postacie"]["a"].get("hold")
        # pomyślne wylogowanie czyści licznik
    s = Swiat(("a",))
    s.grafik([zmiana("a")])
    s.online("a", bot=False)
    w_miescie(s, "a")
    n, at = nz(s)
    at.wyniki["wyloguj"] = (False, "kod 5: brak spokoju")
    n.tick()
    s.zegar.dalej(minutes=3)
    n.tick()
    assert n.stan["postacie"]["a"]["wylog_bl"] == 2
    del at.wyniki["wyloguj"]
    s.zegar.dalej(minutes=8)
    n.tick()
    assert "wylog_bl" not in n.stan["postacie"]["a"] and n.stan["postacie"]["a"]["faza"] == "OFFLINE"


def test_b5_zaloguj_kod_9_zla_postac_to_eskalacja():
    s = Swiat(("a",))
    s.zegar.t = datetime(2026, 10, 21, 9, 5)
    s.grafik([zmiana("a", od="2026-10-21 09:00", koniec="2026-10-21 11:00", wylog="2026-10-21 11:15")])
    n, at = nz(s)
    n.tick()
    s.inst["a"]["gra"] = True
    at.wyniki["zaloguj"] = (False, "kod 9: zalogowano inną postać")
    s.zegar.dalej(minutes=2)
    n.tick()
    assert at.nazwy().count("powiadom") == 1 and "INNĄ postać" in at.wywolania[-1][3], at.wywolania
    assert n.stan["postacie"]["a"].get("hold"), "zła postać = wstrzymanie do decyzji Karola"
    at2 = at
    s.zegar.dalej(minutes=5)
    n.tick()
    assert at2.nazwy().count("zaloguj") == 1, "wstrzymana: bez kolejnych prób logowania"


def test_b5_zmien_spot_nie_w_walce():
    s = Swiat(("a",))
    s.dodaj("a", {"postac": "A", "spoty_zapasowe": ["thais_pn_z8"]})
    s.tryb_log("a", "raty", "ostrozny")
    s.online("a", bot=True)
    s.log("a", [(s.zegar.t - timedelta(seconds=4), "[WALKA] Troll odl 1 HP 70%")])
    n, at = nz(s)
    kod, txt = n.napraw("a", "zmien_spot")
    assert kod == 3 and "walce" in txt and at.wywolania == [], (kod, txt)
    # strażnik także w samym _restart (omija bramkę CLI)
    n._raw = {"a": s.inst["a"]}
    ok, txt = n._restart(s.zegar.t, "a", "zmien_spot", n.post("a"))
    assert not ok and "walce" in txt and at.wywolania == [], (ok, txt)


def test_b5_bez_zapisu_bytecode():
    import subprocess
    pyc = KORZEN / "__pycache__"
    przed = {p.name: p.stat().st_mtime for p in pyc.glob("*")} if pyc.is_dir() else {}
    assert sys.dont_write_bytecode
    r = subprocess.run([sys.executable, "-I", str(KORZEN / "nadzor.py"), "stan"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and '"postacie"' in r.stdout, r.stderr[-300:]
    po = {p.name: p.stat().st_mtime for p in pyc.glob("*")} if pyc.is_dir() else {}
    assert przed == po, set(po.items()) ^ set(przed.items())
    assert not [n for n in po if n.startswith(("grafik.", "nadzor."))] or all(n in przed for n in po)


# ---------------------------------------------------------------- wybór spotu (Q5, SPEC_wybor_spotu_1021)
EDRON = [33191, 31818, 7]                     # depo Edron
THAIS = [32370, 32214, 7]
ED_MIASTA = {"edron": {"x": [32900, 33400], "y": [31500, 32100]}, "thais": {"x": [32200, 32700], "y": [32000, 32450]}}


def tabela_q5(swiat, widelki=None, bez=()):
    """mapy.json + dane_tibia/spoty_nadzorca.json w świecie testu: raty (Thais), ed_a/ed_b/ed_c (Edron; ed_c wymaga liny)."""
    mapy = {"_opis": "x", "raty": {"trasa": "x", "potwory": "Rat"}, "ed_a": {"trasa": "x", "potwory": "Troll"},
            "ed_b": {"trasa": "x", "potwory": "Troll"}, "ed_c": {"trasa": "x", "potwory": "Troll"}}
    w = widelki or {}
    sp = lambda m, j, lo, hi, **kw: {"miasto": m, "jaskinia": j, "poziom": w.get(j, [lo, hi]), "waga": 1.0, "auto": True, **kw}      # noqa: E731
    spoty = {"raty": sp("thais", "j_raty", 1, 12), "ed_a": sp("edron", "j_a", 5, 30), "ed_b": sp("edron", "j_b", 5, 30),
             "ed_c": sp("edron", "j_c", 5, 30, wymaga_dodatkowo=["lina"])}
    for b in bez:
        spoty.pop(b)
    (swiat.k / "mapy.json").write_text(json.dumps(mapy))
    (swiat.k / "dane_tibia").mkdir(exist_ok=True)
    (swiat.k / "dane_tibia" / "spoty_nadzorca.json").write_text(json.dumps({"miasta": ED_MIASTA, "spoty": spoty}))


def w_grze_q5(swiat, id_, poz, level, bot=False):
    swiat.inst[id_].update(sesja=True, gra=True, bot=bot, gracz={"hp": 100, "max_hp": 100, "level": level},
                           panel={"pozycja": list(poz), "level": level})


def start_q5(swiat, n, at, id_):
    """Do chwili, w której nadzorca zalogował postać i (jeśli może) wystartował bota; zwraca wywołania start_bota."""
    swiat.zegar.t = datetime(2026, 10, 21, 9, 0, 0)
    n.tick()                                            # sesja_start
    swiat.inst[id_]["gra"] = True
    swiat.zegar.dalej(minutes=2)
    n.tick()                                            # zaloguj
    return n


def test_q5_start_zmiany_miasto_z_pozycji_kolanosh():
    s = Swiat(("a",))
    tabela_q5(s)
    s.grafik([zmiana("a", od="2026-10-21 09:00", koniec="2026-10-21 11:00", wylog="2026-10-21 11:15")])
    s.tryb_log("a", "raty", "ostrozny,ml", datetime(2026, 10, 21, 8, 0, 0))          # ostatnia mapa w tryb.log = Thais (jak Kolanosh 21.10 17:02)
    s.ekw["a"] = {"lina": True, "lopata": False}
    n, at = nz(s)
    at.zapisuj_tryb = True
    s.zegar.t = datetime(2026, 10, 21, 9, 0, 0)
    n.tick()
    s.inst["a"]["gra"] = True
    s.zegar.dalej(minutes=2)
    n.tick()
    w_grze_q5(s, "a", EDRON, 8)                          # stoi w depo w Edronie
    s.zegar.dalej(minutes=1)
    n.tick()
    st = [w for w in at.wywolania if w[0] == "start_bota"]
    assert len(st) == 1 and st[0][2] in ("ed_a", "ed_b", "ed_c") and st[0][2] != "raty", at.wywolania
    assert st[0][3] == "ostrozny,ml", "tryb zostaje bieżący z tryb.log (cecha postaci)"
    ost = [x for x in n.dziennik.ostatnie if x["akcja"] == "start_bota"][-1]
    assert "wybór spotu" in ost["powod"] and "miasto edron" in ost["powod"] and "odrzucone" in ost["powod"], ost["powod"]
    stp = n.stan["postacie"]["a"]
    assert stp["spot"]["mapa"] == st[0][2] and stp["spoty_hist"][-1]["mapa"] == st[0][2], stp


def test_q5_dwie_postacie_w_edronie_w_jednym_przebiegu_rozne_spoty():
    s = Swiat(("a", "b"))
    tabela_q5(s, widelki={"j_c": [40, 50]})              # ed_c poza widełkami: zostają ed_a i ed_b
    s.grafik([zmiana("a", od="2026-10-21 09:00"), zmiana("b", od="2026-10-21 09:00")])
    s.zegar.t = datetime(2026, 10, 21, 9, 30, 0)
    n, at = nz(s)
    for i in ("a", "b"):
        w_grze_q5(s, i, EDRON, 12)
        n.post(i).update(faza="DOJSCIE", sesja_nasza=True, login_ts=ts(s), zmiana_od="2026-10-21 09:00")
    n.tick()
    st = {w[1]: w[2] for w in at.wywolania if w[0] == "start_bota"}
    assert set(st) == {"a", "b"} and st["a"] != st["b"] and set(st.values()) == {"ed_a", "ed_b"}, at.wywolania


def ts(s):
    return s.zegar.t.timestamp()


def test_q5_lina_wymagana_bez_liny_to_eskalacja_a_nie_start():
    s = Swiat(("a",))
    tabela_q5(s, widelki={"j_a": [40, 50], "j_b": [40, 50]})                       # zostaje tylko ed_c (wymaga liny)
    s.grafik([zmiana("a", od="2026-10-21 09:00")])
    s.zegar.t = datetime(2026, 10, 21, 9, 30, 0)
    n, at = nz(s)
    w_grze_q5(s, "a", EDRON, 8)
    n.post("a").update(faza="DOJSCIE", sesja_nasza=True, login_ts=ts(s), zmiana_od="2026-10-21 09:00")
    s.ekw["a"] = {"lina": False, "lopata": False}
    n.tick()
    assert "start_bota" not in at.nazwy(), at.wywolania
    assert "powiadom" in at.nazwy(), "eskalacja brak spotu idzie do Karola"
    esk = [x for x in n.dziennik.ostatnie if x["akcja"] == "eskaluj"]
    assert esk and "brak spotu" in esk[-1]["powod"] and "lina" in esk[-1]["powod"], esk
    assert not n.post("a").get("hold"), "brak spotu nie wstrzymuje postaci: kolejny przebieg próbuje znów"
    s.zegar.dalej(minutes=1)
    s.ekw["a"] = {"lina": True, "lopata": False}                                   # Karol dał linę
    n.tick()
    assert [w for w in at.wywolania if w[0] == "start_bota"][0][2] == "ed_c", at.wywolania
    # lina nieznana (brak odczytu), jedyny spot wymaga liny: start jak w mozg.sprawdz_line
    s2 = Swiat(("a",))
    tabela_q5(s2, widelki={"j_a": [40, 50], "j_b": [40, 50]})
    s2.grafik([zmiana("a", od="2026-10-21 09:00")])
    s2.zegar.t = datetime(2026, 10, 21, 9, 30, 0)
    n2, at2 = nz(s2)
    w_grze_q5(s2, "a", EDRON, 8)
    n2.post("a").update(faza="DOJSCIE", sesja_nasza=True, login_ts=ts(s2), zmiana_od="2026-10-21 09:00")
    n2.tick()
    assert [w for w in at2.wywolania if w[0] == "start_bota"], at2.wywolania


def test_q5_mieszanie_druga_zmiana_inna_niz_pierwsza():
    s = Swiat(("a",))
    tabela_q5(s, widelki={"j_c": [40, 50]})                                        # dwa spoty w Edronie: ed_a, ed_b
    s.zegar.t = datetime(2026, 10, 21, 9, 0)
    s.grafik([zmiana("a", od="2026-10-21 09:00", koniec="2026-10-21 11:00", wylog="2026-10-21 11:15"),
              zmiana("a", od="2026-10-21 13:00", koniec="2026-10-21 15:00", wylog="2026-10-21 15:15")])
    s.tryb_log("a", "raty", "ostrozny", datetime(2026, 10, 21, 8, 0))
    n, at = nz(s)
    at.zapisuj_tryb = True

    def tik(m=1):
        n.tick()
        s.zegar.dalej(minutes=m)
    tik()
    s.inst["a"]["gra"] = True
    tik(2)
    w_grze_q5(s, "a", EDRON, 12)
    tik()
    pierwszy = [w for w in at.wywolania if w[0] == "start_bota"][-1][2]
    assert pierwszy in ("ed_a", "ed_b"), at.wywolania
    s.zegar.t = datetime(2026, 10, 21, 11, 1)
    tik()                                                                          # wroc
    s.plik("a", "WROC").unlink()
    w_miescie(s, "a")
    tik()
    s.zegar.t = datetime(2026, 10, 21, 11, 16)
    tik()
    assert at.nazwy()[-1] == "wyloguj" and n.stan["postacie"]["a"].get("spot") is None, at.nazwy()
    s.zegar.t = datetime(2026, 10, 21, 13, 0)
    tik()
    assert at.nazwy().count("sesja_start") == 2, at.nazwy()
    s.inst["a"]["gra"] = True
    tik(2)
    w_grze_q5(s, "a", EDRON, 12)
    tik()
    drugi = [w for w in at.wywolania if w[0] == "start_bota"][-1][2]
    assert len([w for w in at.wywolania if w[0] == "start_bota"]) == 2 and drugi != pierwszy and drugi in ("ed_a", "ed_b"), (pierwszy, drugi)
    assert [h["mapa"] for h in n.stan["postacie"]["a"]["spoty_hist"]] == [pierwszy, drugi]


def test_q5_zmien_spot_z_tabeli_i_brak_alternatywy():
    s = Swiat(("a", "b"))
    tabela_q5(s)
    for i, m in (("a", "ed_a"), ("b", "ed_b")):
        s.tryb_log(i, m, "ostrozny")
        w_grze_q5(s, i, [33110, 31742, 8], 12, bot=True)                           # w jaskini, w prostokącie Edronu
    s.ekw["a"] = {"lina": True, "lopata": False}
    n, at = nz(s)
    kod, txt = n.napraw("a", "zmien_spot")
    assert kod == 0, txt
    st = [w for w in at.wywolania if w[0] == "start_bota"]
    assert st and st[0][2] == "ed_c" and st[0][3] == "ostrozny", at.wywolania       # ed_a to jego własna jaskinia, ed_b zajęte przez b
    assert n.stan["postacie"]["a"]["spot"]["mapa"] == "ed_c"
    # bez liny jedyna alternatywa odpada: zmiana niemożliwa, nic nie startuje
    s2 = Swiat(("a", "b"))
    tabela_q5(s2)
    for i, m in (("a", "ed_a"), ("b", "ed_b")):
        s2.tryb_log(i, m, "ostrozny")
        w_grze_q5(s2, i, [33110, 31742, 8], 12, bot=True)
    s2.ekw["a"] = {"lina": False, "lopata": False}
    n2, at2 = nz(s2)
    kod, txt = n2.napraw("a", "zmien_spot")
    assert kod == 1 and "niemożliwa" in txt and not [w for w in at2.wywolania if w[0] == "start_bota"], (kod, txt, at2.wywolania)
    n2._raw = {i: s2.inst[i] for i in s2.inst}
    assert not n2._alternatywa_spotu("a", n2.obserwuj("a", s2.inst["a"], s2.zegar.t), "ed_a", s2.zegar.t), "drabina nie dostaje szczebla zmien_spot bez alternatywy"
    s2.ekw["a"] = {"lina": True, "lopata": False}
    assert n2._alternatywa_spotu("a", n2.obserwuj("a", s2.inst["a"], s2.zegar.t), "ed_a", s2.zegar.t)


def test_q5_cien_raz_podglad_spotow_zero_zapisow():
    s = Swiat(("a", "b", "c"))
    tabela_q5(s)
    for i, (m, poz, lvl) in {"a": ("ed_a", EDRON, 12), "b": ("ed_b", EDRON, 12), "c": ("raty", THAIS, 5)}.items():
        s.tryb_log(i, m, "ostrozny")
        w_grze_q5(s, i, poz, lvl, bot=True)
        s.log(i, [(s.zegar.t - timedelta(seconds=40), "Cel Rat zabity na (1, 2, 8).")])
    s.ekw["a"] = s.ekw["b"] = {"lina": True, "lopata": False}
    s.grafik([zmiana(i, od="2026-10-21 10:00") for i in "abc"])

    def migawka():
        return sorted((str(p.relative_to(s.k)), p.stat().st_size, p.stat().st_mtime_ns) for p in s.k.rglob("*") if p.is_file())
    przed = migawka()
    n, at = nz(s, zywo=False, zapis=False)
    r = n.tick()
    pod = {x["id"]: x for x in r if x["akcja"] == "spot_podglad"}
    assert set(pod) == {"a", "b", "c"}, [x["akcja"] for x in r]
    assert migawka() == przed and at.wywolania == [], "cień --raz: zero zapisów i zero akcji"
    assert all(x["wynik"] == "cień" and "teraz na" in x["powod"] for x in pod.values())
    wybrane = {i: x["powod"].split("wybrano ")[1].split(":")[0] for i, x in pod.items()}
    assert wybrane["a"] != "ed_a" and wybrane["b"] != "ed_b" and wybrane["c"] == "raty", wybrane      # mieszanie (a, b), raty to jedyny spot Thais
    assert wybrane["a"] != wybrane["b"], wybrane                                    # plan bez dubli w Edronie
    # z zapisem: wpis najwyżej raz na 30 min
    s.zegar.t = datetime(2026, 10, 21, 10, 0)
    n2, _ = nz(s, zywo=False, zapis=True)
    n2.tick()
    s.zegar.dalej(minutes=5)
    n2.tick()
    p = next((s.k / "instancje" / "_wspolne" / "logi").glob("nadzor-*.jsonl"))
    assert sum(json.loads(l)["akcja"] == "spot_podglad" for l in p.read_text().splitlines()) == 3, p.read_text()


def test_q5_brak_tabeli_jak_dotad_i_brak_danych():
    s = Swiat(("a",))                                                              # bez dane_tibia/spoty_nadzorca.json
    s.tryb_log("a", "raty", "ostrozny")
    n, at = nz(s)
    st = n.post("a")
    wyn = n._wybor_startu("a", {"panel": {}, "gracz": None}, st, zmiana("a"), s.zegar.t)
    assert wyn["mapa"] == "raty" and wyn["spot"] is None and "tryb.log" in wyn["skad"], wyn
    assert any(x["akcja"] == "ostrezenie" or x["akcja"] == "ostrzezenie" for x in n.dziennik.ostatnie), n.dziennik.ostatnie
    wyn = n._wybor_startu("a", {"panel": {}, "gracz": None}, st, zmiana("a", mapa="ed_a", tryb="x"), s.zegar.t)
    assert wyn["mapa"] == "ed_a" and wyn["skad"] == "grafik", "jawna mapa Karola z grafiku wygrywa nad wyborem"
    # tabela jest, ale poziom nieczytelny: czekaj, po 10 min od logowania eskalacja nieustalony (bez wstrzymania)
    tabela_q5(s)
    n, at = nz(s)
    st = n.post("a")
    st["login_ts"] = ts(s)
    o = {"panel": {"pozycja": EDRON}, "gracz": {"hp": 1, "max_hp": 1}}
    d = n._wybor_startu("a", o, st, zmiana("a"), s.zegar.t)
    assert d["akcja"] == "czekaj" and d["kod"] == "spot-dane", d
    s.zegar.dalej(minutes=11)
    d = n._wybor_startu("a", o, st, zmiana("a"), s.zegar.t)
    assert d["akcja"] == "eskaluj" and d["arg"]["kod_eskalacji"] == "nieustalony", d


def test_q5_zajetosc_z_tryb_log_a_nie_z_pola_mapa_okno_api():
    """okno_api podaje w `mapa` ostatni_start.env (lekcja 21.10 15:36): zajętość musi iść z tryb.log (+ stan nadzorcy), a przypisanie z tego przebiegu blokuje spot."""
    s = Swiat(("a", "b"))
    tabela_q5(s, widelki={"j_c": [40, 50]})
    s.tryb_log("b", "ed_a", "ostrozny")
    w_grze_q5(s, "b", [33110, 31742, 8], 12, bot=True)
    s.inst["b"]["mapa"] = "raty"                                  # stare ostatni_start.env
    w_grze_q5(s, "a", EDRON, 12)
    n, at = nz(s)
    n._raw = {i: s.inst[i] for i in s.inst}
    assert n.mapy_zajete("a", s.zegar.t) == {"b": {"ed_a"}}, n.mapy_zajete("a", s.zegar.t)
    assert n._zajete_mapy("a") == {"ed_a"}
    n.post("b")["spot"] = {"mapa": "ed_b"}                          # nadzorca zapisał inny spot: liczą się oba źródła
    assert n.mapy_zajete("a", s.zegar.t) == {"b": {"ed_a", "ed_b"}}
    # przypisanie z tego przebiegu (bot jeszcze nie ruszył): spot zajęty
    n2, _ = nz(s)
    n2._raw = {"a": s.inst["a"]}
    n2._przypisane = {"b": "ed_a"}
    for d in range(30):
        zegar = datetime(2026, 10, 1 + d, 9, 0)
        w = n2.wybierz_spot("a", s.inst["a"]["panel"], s.inst["a"]["gracz"], zegar, None, "start")
        assert w["mapa"] == "ed_b", w


# ---------------------------------------------------------------- kontrola okien (okna_start.py, 22.10)
def _brak_plecaka(s, ile=6, id_="a", jak="Loot: brak_plecaka"):
    s.log(id_, [(s.zegar.t - timedelta(seconds=20 + 15 * i), jak) for i in range(ile)])


def _eksp(n, s, id_="a"):
    n.stan["postacie"][id_] = {"faza": "EXP", "login_ts": s.zegar.t.timestamp() - 3600, "zmiana_od": "2026-10-21 09:00",
                               "bot_start": s.zegar.t.timestamp() - 300}      # świeży start: zacięcie ("brak zabić") jeszcze nie zachodzi


def test_okna_analiza_logu_liczy_brak_plecaka_i_walke_bez_lootu():
    t = datetime(2026, 10, 21, 12, 0, 0)
    f = lambda sec, txt: ((t - timedelta(seconds=sec)).timestamp(), txt)       # noqa: E731
    a = N.analizuj_log([f(400, "Loot: brak_plecaka"), f(100, "Loot: brak_plecaka"), f(50, "brak_plecaka (zero lub kilka okien plecaka)"),
                        f(30, "Loot: brak_okna"), f(10, "Loot: brak_plecaka")], t.timestamp())
    assert a["brak_plecaka"] == 3 and a["brak_okna"] == 1, a            # linia sprzed 5 min nie liczy się
    assert a["walka"] is True and a["walka_bez_lootu"] is False         # same linie lootu to nie walka
    a = N.analizuj_log([f(5, "[WALKA] Troll odl 1 HP 70%")], t.timestamp())
    assert a["walka_bez_lootu"] is True


def test_okna_log_z_brakiem_plecaka_zleca_kontrole_raz_na_karencje():
    s = Swiat(("a",))
    s.grafik([zmiana("a", od="2026-10-21 09:00", koniec="2026-10-21 16:00", wylog="2026-10-21 16:15")])
    s.online("a", bot=True)
    _brak_plecaka(s)
    n, at = nz(s)
    _eksp(n, s)
    n.tick()
    assert at.nazwy() == ["okna"], at.wywolania
    s.zegar.dalej(minutes=3)
    _brak_plecaka(s)
    n.tick()
    assert at.nazwy() == ["okna"], "karencja 15 min: bez drugiego wywołania"
    s.zegar.dalej(minutes=16)
    _brak_plecaka(s)
    n.tick()
    assert at.nazwy() == ["okna", "okna"], at.wywolania


def test_okna_ponizej_progu_i_brak_okna_zwlok_nie_zlecaja():
    s = Swiat(("a", "b"))
    s.grafik([zmiana(i, od="2026-10-21 09:00", koniec="2026-10-21 16:00", wylog="2026-10-21 16:15") for i in ("a", "b")])
    for i in ("a", "b"):
        s.online(i, bot=True)
    _brak_plecaka(s, ile=3, id_="a")
    _brak_plecaka(s, ile=8, id_="b", jak="Loot: brak_okna")        # brak okna zwłok to zwykła rzecz: próg 15
    n, at = nz(s)
    _eksp(n, s, "a")
    _eksp(n, s, "b")
    n.tick()
    assert at.nazwy() == [], at.wywolania


def test_okna_w_walce_odroczone():
    s = Swiat(("a",))
    s.grafik([zmiana("a", od="2026-10-21 09:00", koniec="2026-10-21 16:00", wylog="2026-10-21 16:15")])
    s.online("a", bot=True)
    _brak_plecaka(s)
    s.log("a", [(s.zegar.t - timedelta(seconds=3), "[WALKA] Troll odl 1 HP 70%")])
    n, at = nz(s)
    _eksp(n, s)
    n.tick()
    assert at.wywolania == [], at.wywolania


def test_okna_napraw_cli_blokady_i_wykonanie():
    s = Swiat(("a", "b"))
    s.online("a", bot=True)
    s.offline("b")
    n, at = nz(s)
    kod, txt = n.napraw("b", "okna")
    assert kod == 3 and "offline" in txt and at.wywolania == [], (kod, txt)
    kod, txt = n.napraw("a", "okna")
    assert kod == 0 and at.nazwy() == ["okna"], (kod, txt)
    s.log("a", [(s.zegar.t - timedelta(seconds=3), "[WALKA] Troll odl 1 HP 70%")])
    n2, at2 = nz(s)
    kod, txt = n2.napraw("a", "okna")
    assert kod == 3 and "walce" in txt and at2.wywolania == [], (kod, txt)
    s.plik("a", "STOP_RECZNY").touch()
    n3, at3 = nz(s)
    kod, txt = n3.napraw("a", "okna")
    assert kod == 3 and at3.wywolania == [], (kod, txt)               # Karol gra sam: zero akcji


def test_okna_wykonawca_zywy_wola_okna_start_napraw():
    w = N.WykonawcaZywy("/nie/ma")
    wywolano = []
    w._uruchom = lambda argv, id_, limit, odlacz=False: wywolano.append((list(map(str, argv)), id_, limit)) or (True, "kod 0")
    assert w.okna("a") == (True, "kod 0")
    argv, id_, limit = wywolano[0]
    assert argv[1] == "-I" and argv[2].endswith("okna_start.py") and argv[3] == "napraw" and id_ == "a" and limit == 90, wywolano



# ---------------------------------------------------------------- 22.10: grafik nie ponawia `wroc` w kółko, nadzór zna poziom (regresja z dziennika wydry)
WYDRA_A = zmiana("a", od="2026-10-22 08:50", koniec="2026-10-22 11:13", wylog="2026-10-22 11:28")
WYDRA_B = zmiana("a", od="2026-10-22 13:30", koniec="2026-10-22 16:10", wylog="2026-10-22 16:25")


def _wydra(zywo, start=(11, 15)):
    """Wydra z dziennika 22.10: zmiana A (koniec 11:13) i B (13:30-16:10), bot online przez cały czas, `wroc` nic w świecie nie zmienia."""
    s = Swiat(("a",), Zegar(datetime(2026, 10, 22, *start)))
    s.grafik([WYDRA_A, WYDRA_B], data="20261022")
    s.online("a", bot=True)
    n, at = nz(s, zywo=zywo, zapis=False)
    n.stan["postacie"]["a"] = {"faza": "EXP", "zmiana_od": WYDRA_A["od"], "login_ts": 0, "bot_start": 0}
    return s, n, at


def _wydra_do(s, n, do, po_ticku=None, przed_tickiem=None):
    """Tyknięcia co 5 min do `do` włącznie; login_ts i bot_start odświeżane (limit dzienny i brak zabić to nie ten test). -> raport."""
    raport = []
    while s.zegar.t <= do:
        st = n.post("a")
        st["login_ts"], st["bot_start"] = s.zegar.t.timestamp() - 3600, s.zegar.t.timestamp() - 600
        if przed_tickiem:
            przed_tickiem(s.zegar.t)
        raport += n.tick()
        if po_ticku:
            po_ticku(s.zegar.t)
        s.zegar.dalej(minutes=5)
    return raport


def test_grafik_wada1_cien_wroc_raz_na_zmiane_a_nie_co_30_min():
    s, n, _ = _wydra(zywo=False)
    r = _wydra_do(s, n, datetime(2026, 10, 22, 16, 40))
    wroc = [x for x in r if x["akcja"] == "wroc"]
    assert [x["t"][11:16] for x in wroc] == ["11:15", "16:10"], [(x["t"][11:16], x["powod"]) for x in wroc]
    assert "(11:13)" in wroc[0]["powod"] and "(16:10)" in wroc[1]["powod"], [x["powod"] for x in wroc]
    esk = [x for x in r if x["akcja"] == "eskaluj"]
    assert len(esk) == 2 and "powrót" in esk[0]["powod"] and "bez efektu" in esk[0]["powod"], [(x["t"][11:16], x["powod"]) for x in esk]
    assert n.post("a")["zmiana_od"] == WYDRA_B["od"], "po 13:30 zmiana to B, nie przypięta A"


def test_grafik_wada1_zywo_jedno_zlecenie_jedna_eskalacja_potem_cisza():
    s, n, at = _wydra(zywo=True)
    _wydra_do(s, n, datetime(2026, 10, 22, 12, 30), przed_tickiem=lambda t: s.plik("a", "WROC").unlink(missing_ok=True))      # wroc "nie łapie"
    assert at.nazwy().count("wroc") == 1, at.nazwy()
    assert at.nazwy().count("powiadom") == 1, at.nazwy()
    assert not n.post("a").get("hold"), "nieustalony nie wstrzymuje postaci"
    assert n.post("a")["wroc_koniec"]["eskalowano"], n.post("a")


def test_grafik_wada1_przejecie_przez_karola_czysci_zlecenie_i_nie_wraca_stara_zmiana():
    s, n, at = _wydra(zywo=True)

    def karol(t):
        if t == datetime(2026, 10, 22, 11, 25):
            s.plik("a", "STOP_RECZNY").touch()
        if t == datetime(2026, 10, 22, 13, 35):
            s.plik("a", "STOP_RECZNY").unlink()
    _wydra_do(s, n, datetime(2026, 10, 22, 11, 30), przed_tickiem=lambda t: (s.plik("a", "WROC").unlink(missing_ok=True), karol(t)))
    assert "wroc_koniec" not in n.post("a"), "STOP_RECZNY (Karol gra) kasuje zlecenie powrotu"
    s.zegar.t = datetime(2026, 10, 22, 13, 35)
    _wydra_do(s, n, datetime(2026, 10, 22, 14, 30), przed_tickiem=lambda t: (s.plik("a", "WROC").unlink(missing_ok=True), karol(t)))
    assert at.nazwy().count("wroc") == 1, ("po przejęciu i oddaniu postaci w trakcie zmiany B nie ma wroc ze starej zmiany", at.nazwy())


def test_grafik_wada1_zmiana_postaci_przelacza_tylko_wygasle_przypiecie():
    s = Swiat(("a",))
    n, _ = nz(s)
    plan = {"zmiany": [WYDRA_A, WYDRA_B]}
    n.post("a")["zmiana_od"] = WYDRA_A["od"]
    for kiedy, oczekiwana in (((11, 20), WYDRA_A), ((12, 30), WYDRA_A), ((13, 35), WYDRA_B)):      # 12:30: nie ma innej aktywnej, przypięcie zostaje
        z = n.zmiana_postaci(plan, "a", datetime(2026, 10, 22, *kiedy), True)
        assert z["od"] == oczekiwana["od"], (kiedy, z)
    assert n.post("a")["zmiana_od"] == WYDRA_B["od"]


def test_grafik_wada1_zlecenie_z_cienia_nie_tlumi_wroc_na_zywo():
    s, n1, _ = _wydra(zywo=False)
    n1.tick()
    assert n1.post("a")["wroc_koniec"]["tryb"] == "cien"
    n2, at = nz(s, zywo=True)
    n2.stan = n1.stan                                            # ten sam plik stanu, po włączeniu NADZOR_ZYWO
    s.zegar.dalej(minutes=5)
    n2.tick()
    assert at.nazwy().count("wroc") == 1, "zlecenie zapisane w cieniu nie liczy się jako zlecone naprawdę"
    assert n2.post("a")["wroc_koniec"]["tryb"] == "zywo"


def test_grafik_wada1_zlecenie_wygasa_gdy_bot_nie_dziala_i_po_wylogowaniu():
    s, n, at = _wydra(zywo=True)
    n.tick()
    assert "wroc_koniec" in n.post("a")
    assert n.post("a")["wroc_koniec"]["tryb"] == "zywo"
    s.plik("a", "WROC").unlink()                                 # bot wziął zlecenie, dojechał, stanął
    s.inst["a"]["bot"] = False
    w_miescie(s, "a")
    s.zegar.dalej(minutes=5)
    n.tick()
    assert "wroc_koniec" not in n.post("a"), "bot stoi (powrót się udał): zlecenie zamknięte"
    s.offline("a")
    n.post("a")["wroc_koniec"] = {"tryb": "zywo", "zmiana": WYDRA_A["od"], "ts": 0, "powod": "x"}
    s.zegar.dalej(minutes=5)
    n.tick()
    assert "wroc_koniec" not in n.post("a"), "offline: zlecenie zamknięte"


def _poziom_swiat(level=12):
    s = Swiat(("a",))
    tabela_q5(s)
    s.tryb_log("a", "raty", "ostrozny")
    s.grafik([zmiana("a", od="2026-10-21 10:00")])
    w_grze_q5(s, "a", THAIS, level, bot=True)
    s.log("a", [(s.zegar.t - timedelta(seconds=40), "Cel Rat zabity na (1, 2, 8).")])
    return s


def test_poziom_wada2_ostatni_znany_poziom_z_data_przy_chwilowym_braku_odczytu():
    s = _poziom_swiat(12)
    n0, _ = nz(s, zywo=False, zapis=False)
    n0.tick()                                                     # odczyt udany: poziom zapamiętany z datą
    assert n0.post("a")["poziom"] == {"wartosc": 12, "t": s.zegar.t.strftime(N.FMT)}, n0.post("a")
    n, _ = nz(s, zywo=False, zapis=False)                         # kolejny przebieg (stan trwały z poprzedniego, bez dedupu wpisów cienia)
    n.stan["postacie"] = n0.stan["postacie"]
    s.inst["a"].update(gracz={"hp": 100, "max_hp": 100}, panel={"pozycja": list(THAIS)})      # strażnik nie odpowiedział w limicie: brak level
    s.zegar.dalej(minutes=5)
    r = n.tick()
    pod = next(x for x in r if x["id"] == "a" and x["akcja"] == "spot_podglad")
    assert "poziom postaci nieznany" not in pod["powod"] and "wybrano raty" in pod["powod"] and "poziom 12 z odczytu 11:20" in pod["powod"], pod["powod"]
    f = n.fakty_postaci("a", {}, {"hp": 1})
    assert f["poziom"] == 12 and f["poziom_odczyt"] == "2026-10-21 11:20", f
    s.zegar.dalej(hours=25)                                      # za stary odczyt (poziom_max_wiek_h = 24) nie jest zgadywany
    assert n.fakty_postaci("a", {}, {"hp": 1})["poziom"] is None
    n.fakty_postaci("a", {}, {"level": 13})                      # świeży odczyt zawsze wygrywa z zapamiętanym
    assert n.fakty_postaci("a", {}, {"level": 13})["poziom"] == 13


def test_poziom_wada2_stan_pokazuje_poziom_odczyt_ostatni_znany_albo_powod():
    s = _poziom_swiat(12)
    n, _ = nz(s, zywo=False, zapis=False)
    p = n.podsumowanie()["postacie"]["a"]["poziom"]
    assert p["wartosc"] == 12 and p["zrodlo"] == "odczyt teraz", p
    s.inst["a"].update(gracz={"hp": 100, "max_hp": 100}, panel={})
    p = n.podsumowanie()["postacie"]["a"]["poziom"]
    assert p["wartosc"] is None and "brak odczytu" in p["powod"], p                 # nic nie zapamiętane: jawny powód, nie zgadywanie
    n.tick()
    s.inst["a"].update(gracz={"hp": 100, "max_hp": 100, "level": 14}, panel={})
    n.tick()
    s.inst["a"].update(gracz={"hp": 100, "max_hp": 100}, panel={})
    p = n.podsumowanie()["postacie"]["a"]["poziom"]
    assert p["wartosc"] == 14 and p["zrodlo"] == "ostatni znany" and p["odczyt"], p
    s.offline("a")
    p = n.podsumowanie()["postacie"]["a"]["poziom"]
    assert p["wartosc"] == 14 and "offline" in (p.get("powod") or ""), p


def test_poziom_wada2_zrodla_stan_prosi_o_szersze_limity_odczytu_gracza():
    z = N.Zrodla(KORZEN)
    wywolano = {}

    class Wynik:
        stdout = '{"instancje": []}'
    zapas = N.subprocess.run
    N.subprocess.run = lambda argv, **kw: (wywolano.update(kw), Wynik())[1]
    try:
        assert z.stan() == []
    finally:
        N.subprocess.run = zapas
    env = wywolano["env"]
    assert float(env["RETRONIC_PANEL_GRACZ_S"]) >= 1.5 and env["RETRONIC_PANEL_GRACZ_BEZ_PAUZY"] == "1", env
    assert float(env["RETRONIC_OKNO_PANEL_LIMIT_S"]) > 1.5 and float(env["RETRONIC_OKNO_CALOSC_LIMIT_S"]) > float(env["RETRONIC_OKNO_PANEL_LIMIT_S"]), env


if __name__ == "__main__":
    ok = zle = 0
    for nazwa, f in list(globals().items()):
        if nazwa.startswith("test_") and callable(f):
            try:
                f()
                ok += 1
                print("ok  ", nazwa)
            except Exception as e:      # noqa: BLE001
                import traceback
                zle += 1
                print("BŁĄD", nazwa, repr(e)[:500])
                traceback.print_exc()
    print(f"{ok}/{ok + zle} testów zielonych")
    sys.exit(1 if zle else 0)
