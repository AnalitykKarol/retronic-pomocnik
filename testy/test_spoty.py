#!/usr/bin/env python3
"""spoty.py (SPEC_wybor_spotu_1021, Q5): tabela spotów i wybór spotu dla postaci. Offline, tylko odczyt.
Dowodzi na PRAWDZIWEJ tabeli i trasach: spójność z mapy.json, miasto z pozycji (Edron -> tylko Edron, Rook osobno), poziom w widełkach,
jeden bot na jaskinię, lina/łopata (False = odrzucony, None = tylko gdy nie ma nic innego), mieszanie (druga zmiana inna), brak spotu,
determinizm. Na świecie syntetycznym (katalog tymczasowy): spot bez wymagań obok spotu z liną, patrol, brak pliku tabeli.
Uruchomienie: python3 -I testy/test_spoty.py"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
KORZEN = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(KORZEN))
import spoty as SP  # noqa: E402

EDRON_DEPO = (33191, 31818, 7)        # depo Edron (serwis_edron.json)
THAIS_DEPO = (32370, 32214, 7)        # okolice depo Thais (początek thais_dojscie_kratka)
ROOK_MIASTO = (32050, 32200, 7)
CARLIN = (32360, 31782, 7)            # poza tabelą


def edron(poziom, **kw):
    return {"id": kw.pop("id", "x"), "poz": kw.pop("poz", EDRON_DEPO), "poziom": poziom, "ekwipunek": kw.pop("ekwipunek", {"lina": True, "lopata": False}), **kw}


TAB = SP.wczytaj()
# Testy sprawdzają logikę wyboru, nie bieżące decyzje Karola o włączeniu spotów: gobliny Edronu (21.10 18:10 wyłączone
# w tabeli, „za mało defa”) są tu włączone, żeby filtry miasta/poziomu/jaskini/mieszania miały z czego wybierać.
TAB.zakladane = set()       # tabela Karola zakłada łopatę u wszystkich (21.10 18:20); logika filtra ekwipunku testowana bez założeń
for _m in ("gobliny_edron", "gobliny_edron_z9"):
    if _m in TAB.spoty:
        TAB.spoty[_m].auto = True


def test_zakladany_ekwipunek_z_tabeli():
    t = SP.wczytaj()
    assert "lopata" in t.zakladane, t.zakladane


# ---------------------------------------------------------------- tabela
def test_tabela_spojna_z_mapy_json():
    assert not TAB.blad, TAB.blad
    p = SP.sprawdz(TAB)
    assert p == [], p
    mapy = json.loads((KORZEN / "mapy.json").read_text())
    nazwy = {k for k in mapy if not k.startswith("_")}
    assert nazwy == set(TAB.spoty) and not TAB.nieopisane and not TAB.osierocone, (nazwy ^ set(TAB.spoty))
    assert all(s.poziom[0] <= s.poziom[1] for s in TAB.spoty.values())
    assert all(s.poziom_zrodlo == "domyslne" for s in TAB.spoty.values()), "widełki niczyje -> oznaczone jako domyślne"


def test_wymagania_z_tras_lina_i_lopata():
    lina = {n for n, s in TAB.spoty.items() if "lina" in s.wymaga}
    assert {"trolle_edron_z9w", "trolle_edron", "trolle_edron_patrol", "gobliny_edron", "gobliny_edron_z9"} <= lina, lina
    lopata = {n for n, s in TAB.spoty.items() if "lopata" in s.wymaga}
    assert "thais_pn_z8" in lopata, lopata
    assert not TAB.spoty["raty"].wymaga and not TAB.spoty["rook_raty_z8"].wymaga


def test_miasto_z_pozycji():
    m = TAB.miasta
    assert SP.miasto_z_pozycji(EDRON_DEPO, m) == "edron"
    assert SP.miasto_z_pozycji((33110, 31742, 9), m) == "edron", "jaskinia też jest w Edronie"
    assert SP.miasto_z_pozycji(THAIS_DEPO, m) == "thais"
    assert SP.miasto_z_pozycji((32355, 32143, 8), m) == "thais"
    assert SP.miasto_z_pozycji(ROOK_MIASTO, m) == "rook"
    assert SP.miasto_z_pozycji((32662, 32741, 7), m) == "port_hope"
    assert SP.miasto_z_pozycji(CARLIN, m) is None and SP.miasto_z_pozycji(None, m) is None
    try:        # zgodność z serwisem (panel.miasto_pozycji) w obu miastach z planem serwisu
        import panel  # noqa: PLC0415
        for poz, oczek in ((EDRON_DEPO, "edron"), (THAIS_DEPO, "thais")):
            assert panel.miasto_pozycji(poz)[0] == oczek == SP.miasto_z_pozycji(poz, m)
    except ImportError:
        pass


def test_miasto_spotu_zgodne_z_geometria():
    for n, s in TAB.spoty.items():
        assert s.miasto_z_geometrii == s.miasto, (n, s.miasto, s.miasto_z_geometrii)


# ---------------------------------------------------------------- wybór: miasto, poziom, zajętość
def test_edron_tylko_edron_a_kolanosh_nie_dostaje_thais():
    for seed in range(40):
        r = SP.wybierz(edron(8, id="kolanoth"), historia=["raty"], tabela=TAB, ziarno=f"d{seed}")      # 21.10 17:02: tryb.log mówił raty (Thais)
        assert r["mapa"] and TAB.spoty[r["mapa"]].miasto == "edron", r
        assert r["mapa"] != "raty"
    r = SP.wybierz(edron(8, id="kolanoth"), tabela=TAB, ziarno="s")
    assert "miasto edron" in r["powod"] and "z innych miast" in r["powod"], r["powod"]
    for seed in range(40):
        r = SP.wybierz({"id": "k", "poz": THAIS_DEPO, "poziom": 5, "ekwipunek": {}}, tabela=TAB, ziarno=f"d{seed}")
        assert r["mapa"] == "raty", r


def test_poziom_w_widelkach():
    r8 = SP.wybierz(edron(8), tabela=TAB, ziarno="p")
    assert r8["mapa"] in ("trolle_edron_z9w", "gobliny_edron", "gobliny_edron_z9"), r8
    assert ("trolle_edron", "poziom", "poziom 8 poza 10-30") in r8["odrzucone"]
    for seed in range(30):
        assert SP.wybierz(edron(25), tabela=TAB, ziarno=f"p{seed}")["mapa"] in ("trolle_edron", "trolle_edron_patrol", "trolle_edron_z9w")   # gobliny 6-20 odpadają
    brak = SP.wybierz(edron(3), tabela=TAB)
    assert brak["mapa"] is None and brak["brak"] == "spot" and "poziom 3 poza" in brak["powod"], brak
    assert SP.wybierz(edron(60), tabela=TAB)["mapa"] is None


def test_jeden_bot_na_jaskinie_i_dwie_postacie_w_edronie():
    for seed in range(60):
        r = SP.wybierz(edron(12), zajete=["trolle_edron"], tabela=TAB, ziarno=f"z{seed}")
        assert r["mapa"] not in ("trolle_edron", "trolle_edron_patrol"), r        # ten sam spot w wariancie patrol = ta sama jaskinia
    a = SP.wybierz(edron(12, id="a"), tabela=TAB, ziarno="d")
    b = SP.wybierz(edron(12, id="b"), zajete=[a["mapa"]], tabela=TAB, ziarno="d")
    assert a["mapa"] and b["mapa"] and a["jaskinia"] != b["jaskinia"], (a["mapa"], b["mapa"])
    assert any(o[0] == a["mapa"] and o[1] == "zajete" for o in b["odrzucone"]), b["odrzucone"]
    wszystkie_jaskinie = [s.mapa for s in TAB.spoty.values() if s.miasto == "edron" and s.auto and s.poziom[0] <= 12 <= s.poziom[1]]
    r = SP.wybierz(edron(12), zajete=wszystkie_jaskinie, tabela=TAB)
    assert r["mapa"] is None and r["brak"] == "spot", r


# ---------------------------------------------------------------- ekwipunek
def test_lina_wymagana_bez_liny_odrzucony():
    for seed in range(30):
        assert SP.wybierz(edron(10, ekwipunek={"lina": True}), tabela=TAB, ziarno=f"l{seed}")["mapa"]
    r = SP.wybierz(edron(10, id="kolanoth", ekwipunek={"lina": False, "lopata": False}), tabela=TAB)     # 21.10 17:12: bez liny
    assert r["mapa"] is None and r["brak"] == "spot", r
    assert ("trolle_edron_z9w", "ekwipunek", "brak: lina") in r["odrzucone"], r["odrzucone"]
    assert "brak spotu" in r["powod"] and "lina" in r["powod"]


def test_lina_nieznana_tylko_gdy_nie_ma_innego_a_lopata_jak_lina():
    r = SP.wybierz(edron(10, ekwipunek={"lina": None}), tabela=TAB)             # w Edronie każdy spot wymaga liny: nieznane = jak mozg.sprawdz_line
    assert r["mapa"] and "nieodczytany" in r["powod"], r
    r = SP.wybierz(edron(10, ekwipunek={}), tabela=TAB)
    assert r["mapa"], r
    r = SP.wybierz({"id": "t", "poz": THAIS_DEPO, "poziom": 10, "ekwipunek": {"lopata": False}}, tabela=TAB, ziarno="1")     # trolle Thais wymagają łopaty
    assert r["mapa"] == "raty", r
    assert ("thais_pn_z8", "ekwipunek", "brak: lopata") in r["odrzucone"], r["odrzucone"]
    r = SP.wybierz({"id": "t", "poz": THAIS_DEPO, "poziom": 10, "ekwipunek": {"lopata": True}}, tabela=TAB, ziarno="1")
    assert {"thais_pn_z8", "trolle", "trolle_nowe", "trolle_patrol", "trolle_pelny"} <= set(r["kandydaci"]), r["kandydaci"]
    # None wśród pewnych kandydatów: niepewny odpada
    r = SP.wybierz({"id": "t", "poz": THAIS_DEPO, "poziom": 10, "ekwipunek": {"lopata": None}}, tabela=TAB, ziarno="1")
    assert r["mapa"] == "raty" and any(o[0] == "thais_pn_z8" and "nieznane" in o[2] for o in r["odrzucone"]), r


def test_ekwipunek_odczyt_leniwy():
    licznik = []
    r = SP.wybierz({"id": "t", "poz": THAIS_DEPO, "poziom": 3, "ekwipunek": lambda: licznik.append(1) or {"lopata": True}}, tabela=TAB)
    assert r["mapa"] == "raty" and licznik == [], "żaden kandydat nie wymaga ekwipunku: bez odczytu pamięci gry"
    SP.wybierz(edron(10, ekwipunek=lambda: licznik.append(1) or {"lina": True}), tabela=TAB)
    assert licznik == [1], "odczyt najwyżej raz"
    r = SP.wybierz(edron(10, ekwipunek=lambda: 1 / 0), tabela=TAB)
    assert r["mapa"] is not None, "błąd odczytu = nieznane, nie wyjątek"


# ---------------------------------------------------------------- mieszanie
def test_mieszanie_druga_zmiana_inna():
    for seed in range(50):
        a = SP.wybierz(edron(12, id="a"), tabela=TAB, ziarno=f"dzien{seed}|1")
        b = SP.wybierz(edron(12, id="a"), historia=[a["mapa"]], tabela=TAB, ziarno=f"dzien{seed}|2")
        assert a["mapa"] and b["mapa"] and b["jaskinia"] != a["jaskinia"], (a["mapa"], b["mapa"])
        assert ("mieszanie" in {o[1] for o in b["odrzucone"]}), b["odrzucone"]
    # wariant patrol tej samej jaskini nie jest "innym spotem"
    b = SP.wybierz(edron(12), historia=["trolle_edron"], tabela=TAB)
    assert b["mapa"] not in ("trolle_edron", "trolle_edron_patrol"), b
    # brak alternatywy: ten sam spot wolno (jedyny kandydat)
    tylko = SP.wybierz(edron(12), zajete=["trolle_edron", "trolle_edron_z9w", "gobliny_edron_z9"], historia=["gobliny_edron"], tabela=TAB)
    assert tylko["mapa"] == "gobliny_edron", tylko


def test_determinizm_i_waga():
    a = [SP.wybierz(edron(12), tabela=TAB, ziarno="2026-10-21|x")["mapa"] for _ in range(5)]
    assert len(set(a)) == 1
    wyniki = {SP.wybierz(edron(12), tabela=TAB, ziarno=f"dzien{i}")["mapa"] for i in range(80)}
    assert len(wyniki) >= 3, wyniki      # ziarno naprawdę miesza
    # wagi: waga 0 nigdy nie wygrywa, gdy są inni
    t = SP.wczytaj()
    t.spoty["gobliny_edron"].waga = 0.0
    assert all(SP.wybierz(edron(12), tabela=t, ziarno=f"w{i}")["mapa"] != "gobliny_edron" for i in range(60))


# ---------------------------------------------------------------- Rook, piętro, brak danych
def test_rook_nie_miesza_sie_z_ladem():
    rook_spoty = {n for n, s in TAB.spoty.items() if s.miasto == "rook"}
    for seed in range(40):
        r = SP.wybierz({"id": "bober", "poz": ROOK_MIASTO, "poziom": 5, "ekwipunek": {}}, tabela=TAB, ziarno=f"r{seed}")
        assert r["mapa"] in rook_spoty, r
        assert "do_smierci" not in r["mapa"] and r["mapa"] not in ("rook", "rook_bugi_z8", "rook_cave_raty_z9_glab"), r
        e = SP.wybierz(edron(12), tabela=TAB, ziarno=f"r{seed}")
        assert e["mapa"] not in rook_spoty
        t = SP.wybierz({"id": "t", "poz": THAIS_DEPO, "poziom": 5, "ekwipunek": {}}, tabela=TAB, ziarno=f"r{seed}")
        assert t["mapa"] not in rook_spoty
    r = SP.wybierz({"id": "bober", "poz": ROOK_MIASTO, "poziom": 30, "ekwipunek": {}}, tabela=TAB)
    assert r["mapa"] is None, "postać z Rooka z poziomem 30 nie dostaje spotu z lądu"


def test_pietro_startu_i_miasto_nieznane():
    r = SP.wybierz({"id": "t", "poz": (32355, 32143, 8), "poziom": 5, "ekwipunek": {}}, tabela=TAB)     # postać w jaskini z8: dojście działa tylko ze z7
    assert r["mapa"] is None and any(o[1] == "pietro" for o in r["odrzucone"]), r
    r = SP.wybierz({"id": "t", "poz": CARLIN, "poziom": 10, "ekwipunek": {}}, tabela=TAB)
    assert r["mapa"] is None and r["brak"] == "spot" and "poza znanymi miastami" in r["powod"], r


def test_brak_danych_to_nie_wybor():
    assert SP.wybierz({"id": "t", "poz": None, "poziom": 10}, tabela=TAB)["brak"] == "dane"
    assert SP.wybierz({"id": "t", "poz": EDRON_DEPO, "poziom": None}, tabela=TAB)["brak"] == "dane"
    t = SP.wczytaj(plik="/nie/ma/takiego.json")
    assert t.blad and SP.wybierz(edron(10), tabela=t)["brak"] == "dane"


# ---------------------------------------------------------------- świat syntetyczny
def swiat_syntetyczny(tmp, liny=frozenset(), zasypane=frozenset()):
    k = Path(tmp)
    (k / "trasy").mkdir()
    (k / "dane_tibia").mkdir()
    (k / "trasy" / "d_lina.json").write_text(json.dumps([[100, 100, 7], [100, 101, 7], [100, 101, 6]]))
    (k / "trasy" / "d_lopata.json").write_text(json.dumps([[200, 200, 7], [201, 200, 8]]))
    (k / "trasy" / "petla.json").write_text(json.dumps([[100, 105, 7], [100, 106, 7]]))
    (k / "trasy" / "miejsca_x.json").write_text(json.dumps({"trasa": "petla"}))
    (k / "mapy.json").write_text(json.dumps({
        "_opis": "x",
        "z_lina": {"trasa": "petla", "potwory": "Rat", "dojscie": "d_lina"},
        "z_lopata": {"trasa": "petla", "potwory": "Rat", "dojscie": "d_lopata"},
        "wolny": {"trasa": "petla", "potwory": "Rat"},
        "patrol_x": {"trasa": "patrol:x", "potwory": "Rat"},
        "nowy": {"trasa": "petla", "potwory": "Rat"}}))
    sp = lambda j, lo=1, hi=20, **kw: {"miasto": "m", "jaskinia": j, "poziom": [lo, hi], "waga": 1.0, "auto": True, **kw}      # noqa: E731
    (k / "dane_tibia" / "spoty_nadzorca.json").write_text(json.dumps({
        "miasta": {"m": {"x": [0, 1000], "y": [0, 1000]}, "inne": {"x": [2000, 3000], "y": [0, 1000]}},
        "spoty": {"z_lina": sp("j1"), "z_lopata": sp("j2"), "wolny": sp("j3"), "patrol_x": sp("j4", wymaga_dodatkowo=["pochodnia"])}}))
    return k


def test_swiat_syntetyczny_lina_lopata_patrol_i_nowa_mapa():
    with tempfile.TemporaryDirectory() as tmp:
        k = swiat_syntetyczny(tmp)
        t = SP.wczytaj(k, liny_znane={(100, 100, 7)}, zasypane={(200, 200, 7)})
        assert t.spoty["z_lina"].wymaga == {"lina"} and t.spoty["z_lopata"].wymaga == {"lopata"}, {n: s.wymaga for n, s in t.spoty.items()}
        assert not t.spoty["wolny"].wymaga and t.spoty["patrol_x"].wymaga == {"pochodnia"}
        assert t.spoty["patrol_x"].trasa == "petla", "patrol:x -> trasa awaryjna z miejsca_x.json"
        assert t.nieopisane == ["nowy"], "mapa bez wpisu w tabeli jest wykluczona i widoczna"
        assert any("nowy" in p for p in SP.sprawdz(t))
        post = {"id": "p", "poz": (50, 50, 7), "poziom": 5}
        # bez liny/łopaty/pochodni: zostaje spot bez wymagań, a nieznany ekwipunek (None) przegrywa z pewnym
        for seed in range(30):
            r = SP.wybierz({**post, "ekwipunek": {"lina": False, "lopata": False, "pochodnia": False}}, tabela=t, ziarno=str(seed))
            assert r["mapa"] == "wolny", r
            r = SP.wybierz({**post, "ekwipunek": {}}, tabela=t, ziarno=str(seed))
            assert r["mapa"] == "wolny", r
        r = SP.wybierz({**post, "ekwipunek": {"lina": True, "lopata": True, "pochodnia": True}}, tabela=t, ziarno="a")
        assert set(r["kandydaci"]) == {"z_lina", "z_lopata", "wolny", "patrol_x"}, r
        # poza miastem "m": inna kratka
        assert SP.wybierz({**post, "poz": (2500, 5, 7), "ekwipunek": {}}, tabela=t)["mapa"] is None
        # brak pliku tabeli: błąd, nie wyjątek
        os.remove(k / "dane_tibia" / "spoty_nadzorca.json")
        assert SP.wczytaj(k).blad


def test_pomocnicze_ekwipunek_i_lopata():
    odp = {"kontenery": [{"przedmioty": [{"id": SP.ID_LOPATA}]}], "ekwipunek": {"10": {"id": 3003}}}
    assert SP.ekwipunek_postaci(lambda z: odp) == {"lina": True, "lopata": True}
    assert SP.ekwipunek_postaci(lambda z: {"kontenery": [], "ekwipunek": {"1": {"id": 3355}}}) == {"lina": False, "lopata": False}
    assert SP.ekwipunek_postaci(lambda z: {"blad": "x"}) == {"lina": None, "lopata": None}
    assert SP.ekwipunek_postaci(lambda z: 1 / 0) == {"lina": None, "lopata": None}
    assert SP.wymaga_lopaty([(10, 10, 7), (11, 10, 8)], {(11, 11, 7)}) and not SP.wymaga_lopaty([(10, 10, 7), (11, 10, 8)], {(30, 30, 7)})
    assert not SP.wymaga_lopaty([(10, 10, 8), (11, 10, 7)], {(11, 11, 7)}), "tylko przejście w dół"


def test_cli_bez_zapisu_i_bez_bytecode():
    przed = {p.name for p in KORZEN.glob("__pycache__/*")} if (KORZEN / "__pycache__").is_dir() else set()
    r = subprocess.run([sys.executable, "-I", str(KORZEN / "spoty.py"), "sprawdz"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and "spójny" in r.stdout, (r.stdout, r.stderr[-300:])
    r = subprocess.run([sys.executable, "-I", str(KORZEN / "spoty.py"), "tabela"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and "trolle_edron_z9w" in r.stdout and "lina" in r.stdout and r.stdout.count("\n") >= 27, r.stdout[-300:]
    po = {p.name for p in KORZEN.glob("__pycache__/*")} if (KORZEN / "__pycache__").is_dir() else set()
    assert przed == po


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
