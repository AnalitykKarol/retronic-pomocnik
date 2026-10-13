"""Koordynator miejsc (miejsca_koord.py) i opcjonalny hook w patrolu cavebota. Offline (RETRONIC_TESTY=1)."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, multiprocessing, sys, tempfile, types
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import miejsca_koord as mk

ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

tmp = Path(tempfile.mkdtemp())
plik = tmp / "wspolne" / "zajete.json"
t = [1000.0]
zyje = {1, 2, 3}
def K(id_, pid, **kw):
    return mk.Koordynator(plik, id_, pid, zegar=lambda: t[0], zyje=lambda p: p in zyje, **kw)
a, b = K("a", 1), K("b", 2)

# 1. podstawy
sprawdz("1a pierwsza rezerwacja", a.rezerwuj("z8_wschod", (32481, 32291, 8)))
sprawdz("1b to samo miejsce przez drugą instancję odmowa", not b.rezerwuj("z8_wschod", (32481, 32291, 8)))
sprawdz("1c inne miejsce wolne", b.rezerwuj("z9_gniazdo", (32472, 32271, 9)))
sprawdz("1d ponowna rezerwacja własna = ok (idempotentna)", a.rezerwuj("z8_wschod", (32481, 32291, 8)))
sprawdz("1e czy_wolne widzi cudze", not b.czy_wolne("z8_wschod") and b.czy_wolne("z8_polnoc") and a.czy_wolne("z8_wschod"))
sprawdz("1f zajete() = tylko cudze", list(a.zajete()) == ["z9_gniazdo"] and sorted(a.zajete(True)) == ["z8_wschod", "z9_gniazdo"])
sprawdz("1g plik JSON poprawny, katalog utworzony", set(json.loads(plik.read_text())) == {"z8_wschod", "z9_gniazdo"})

# 2. zwolnienie i max_miejsc=1 (przenosiny)
sprawdz("2a po zwolnieniu b może wziąć", a.zwolnij("z8_wschod") == 1 and b.rezerwuj("z8_wschod", (32481, 32291, 8)))
sprawdz("2b max_miejsc=1: nowa rezerwacja b zwolniła poprzednią", sorted(b.zajete(True)) == ["z8_wschod"] and a.czy_wolne("z9_gniazdo"))
a.rezerwuj("z9_gniazdo", (32472, 32271, 9))
sprawdz("2c zwolnij() bez klucza zwalnia wszystkie moje", b.zwolnij() == 1 and not b.zajete() == {} and "z8_wschod" not in a.zajete())

# 3. wygaśnięcie TTL i martwy proces
t[0] += 901
sprawdz("3a TTL: po 901 s rezerwacja a wygasła", b.czy_wolne("z9_gniazdo") and a.zajete(True) == {})
a.rezerwuj("m1", (1, 1, 8)); t[0] += 800
sprawdz("3b odswiez przedłuża", a.odswiez() == 1); t[0] += 800
sprawdz("3c po odświeżeniu nadal zajęte", not b.czy_wolne("m1"))
zyje.discard(1)
sprawdz("3d martwy pid właściciela zwalnia miejsce od razu", b.czy_wolne("m1") and b.rezerwuj("m1", (1, 1, 8)))
zyje.add(1)

# 4. promień (bliskość)
c = K("c", 3)
b.zwolnij()
b.rezerwuj("sala", (100, 100, 8), promien=6)
sprawdz("4a blisko tej samej sali (<=6) zajęte", not c.czy_wolne("inne", (104, 97, 8)))
sprawdz("4b dalej (>6) wolne", c.czy_wolne("inne", (107, 100, 8)))
sprawdz("4c inne piętro wolne", c.czy_wolne("inne", (101, 100, 9)))
b.zwolnij(); a.zwolnij()
a.rezerwuj("p0", (100, 100, 8), promien=0)
sprawdz("4d promień 0 po obu stronach = tylko ten sam klucz", c.czy_wolne("sasiad", (100, 101, 8), 0) and not c.czy_wolne("p0", (100, 100, 8), 0))
a.zwolnij()

# 5. uszkodzony / pusty plik
plik.write_text("{zepsute")
sprawdz("5a uszkodzony plik = brak rezerwacji, rezerwacja działa", a.rezerwuj("x", (1, 1, 1)) and "x" in json.loads(plik.read_text()))
plik.write_text("{}")
sprawdz("5b pusty obiekt (nowa_instancja.sh)", b.czy_wolne("x"))
a.zwolnij()

# 6. wyścig procesów: tylko jeden wygrywa
def _wyscig(args):
    sciezka, nr = args
    import miejsca_koord as m
    k = m.Koordynator(sciezka, f"p{nr}", _os.getpid())    # prawdziwy pid, prawdziwy zegar
    return k.rezerwuj("wspolne_miejsce", (5, 5, 8))
sciezka = tmp / "race" / "zajete.json"
with multiprocessing.get_context("fork").Pool(8) as pool:
    wyniki = pool.map(_wyscig, [(sciezka, i) for i in range(16)])
sprawdz("6a z 16 równoległych rezerwacji wygrywa dokładnie jedna", sum(wyniki) == 1, wyniki)
sprawdz("6b plik spójny", len(json.loads(sciezka.read_text())) == 1)

# 7. hook w cavebot: domyślnie wyłączony, włączony filtruje kandydatów i blokuje _patrol_nowy
import cavebot
cavebot.log = lambda *a: None
sprawdz("7a PATROL_KOORD domyślnie 0", cavebot.PATROL_KOORD == 0 and cavebot.PATROL_KOORD_PROMIEN == 0)
import pokretla
sprawdz("7b pokrętła w ZAKRESY, analityk nie włącza", pokretla.ZAKRESY.get("PATROL_KOORD") == (0, 1)
        and pokretla.KIERUNEK.get("PATROL_KOORD") == "nie_wyzej")
sprawdz("7c waliduj(PATROL_KOORD=1) ręcznie ok", pokretla.waliduj({"PATROL_KOORD": 1})[0] == {"PATROL_KOORD": 1})

MIEJSCA = [{"id": 1, "nazwa": "m_a", "x": 10, "y": 10, "z": 8}, {"id": 2, "nazwa": "m_b", "x": 30, "y": 10, "z": 8},
           {"id": 3, "x": 50, "y": 10, "z": 8}]
b0 = cavebot.Cavebot.__new__(cavebot.Cavebot)
b0.zegar = lambda: 5.0
b0.miejsca = MIEJSCA
b0.patrol_blok = {}
b0.patrol_zabicia = 0
b0._patrol_gracze = lambda z: []
b0._patrol_pietra_ok = lambda: True
b0._patrol_gniazdo_ok = lambda: True
b0._patrol_gracz_czynnik = lambda m: 1.0
b0._patrol_droga = lambda poz, m, uzyte=None: [(m["x"], m["y"], m["z"])]
b0._wypad_reset_klik = lambda: None
b0._patrol_sweep_buduj = lambda p, poz, teraz: False
b0._patrol_tele = lambda *a, **k: None
poz = (20, 10, 8)
sprawdz("7d koordynator wyłączony: wszystkie 3 kandydatów, _patrol_nowy bez rezerwacji",
        len(b0._patrol_kandydaci(poz)) == 3 and b0._patrol_nowy(poz, MIEJSCA[0], "test") is not None and not plik.parent.joinpath("hook").exists())

hook = tmp / "hook" / "zajete.json"
inna = mk.Koordynator(hook, "inna", _os.getpid())
inna.rezerwuj("m_b", (30, 10, 8))
cavebot.PATROL_KOORD = 1
try:
    orig = mk.Koordynator
    mk.Koordynator = lambda: orig(hook, "ja", _os.getpid() + 0, ttl_s=60)   # ten sam pid, inny identyfikator instancji
    # to samo pid dla obu: rozróżnia instancja ("ja" != "inna"), więc rezerwacja "inna" jest cudza
    kand = b0._patrol_kandydaci(poz)
    ids = sorted(m["id"] for m, d in kand)
    sprawdz("7e miejsce zajęte przez inną instancję odpada z kandydatów", ids == [1, 3], ids)
    sprawdz("7f _patrol_nowy na zajętym miejscu = None i blokada miejsca", b0._patrol_nowy(poz, MIEJSCA[1], "test") is None
            and b0.patrol_blok.get(2, 0) > 5.0)
    p = b0._patrol_nowy(poz, MIEJSCA[0], "test")
    sprawdz("7g _patrol_nowy na wolnym = plan i rezerwacja", p is not None and "m_a" in json.loads(hook.read_text()))
    p3 = b0._patrol_nowy(poz, MIEJSCA[2], "test")
    sprawdz("7h miejsce bez nazwy: klucz m<id>, poprzednia rezerwacja zwolniona (max 1)",
            p3 is not None and "m3" in json.loads(hook.read_text()) and "m_a" not in json.loads(hook.read_text()))
    # 7i błąd koordynatora nie zatrzymuje patrolu
    mk.Koordynator = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    b0._koord = None; b0.patrol_blok.clear()
    sprawdz("7i błąd koordynatora: patrol jedzie bez niego", len(b0._patrol_kandydaci(poz)) == 3 and b0._patrol_koord_rezerwuj(MIEJSCA[0]) is True)
finally:
    mk.Koordynator = orig
    cavebot.PATROL_KOORD = 0

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
