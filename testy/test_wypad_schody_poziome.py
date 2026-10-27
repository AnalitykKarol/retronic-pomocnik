"""25.10: wypad.zbuduj_etapy i schody W GORE z ladowaniem obok schodow (poziome), np. gobliny Ab'Dendriel (32622,31790,z7) -> (32621,31790,z6).
Nic nie wysyla do gry i niczego nie zmienia na dysku. Sprawdza: (A) sztuczna mapa: ladowanie na W / E / N od schodow daje cel = pole schodow
(schody=True), a stare przypadki bez zmian (pole domyslne (b.x, b.y-1) przechodnie = lina jak dotad; schody ze ladowaniem (x, y-1) dalej reguly z 24.10;
dwa pasujace pola / stoimy na schodach / brak flagi 2 na gornym pietrze = bez zmiany); (B) prawdziwa mapa i trasa dojscia goblinow:
etapy IDZ LINA IDZ LINA IDZ, druga LINA ma cel na schodach, nie na scianie, i ladunek (32621,31790,z6), sprawdz_plan bez uwag; pierwsze schody
(32654,31674,z8) i powrot w dol bez zmian. NIEZWERYFIKOWANE NA ZYWO: krok na schody (32622,31790,z7)."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import sys

sys.dont_write_bytecode = True
_R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _R)
import mapa as _mapa
import trasa_io
import wypad

ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


class Atrapa:
    """Mapa z listy pol: flagi(x, y, z); nieznane = 0. 1 = widziane/chodliwe, 2 = przejscie pieter, 4 = zablokowane."""

    def __init__(self, pola):
        self.pola = dict(pola)

    def flagi(self, x, y, z):
        return self.pola.get((x, y, z), 0)

    def przechodnie(self, x, y, z):
        f = self.flagi(x, y, z)
        return bool(f & 1 and not f & 4)


def plan_atrapa(s, kier, schody_gora=True, domyslne="sciana"):
    """Schody s=(x,y) na z7 i z6, ladowanie na z6 = s + kier, stoimy na z7 po przeciwnej stronie schodow (s - kier)."""
    sx, sy = s
    b = (sx + kier[0], sy + kier[1], 6)
    a = (sx - kier[0], sy - kier[1], 7)
    pola = {(sx, sy, 7): 3, (sx, sy, 6): 3 if schody_gora else 1, (b[0], b[1], 6): 1, a: 1}
    pola[(b[0], b[1] - 1, 7)] = {"sciana": 5, "chodliwe": 1}[domyslne]
    return Atrapa(pola), a, b


# A. sztuczna mapa
S = (100, 100)
for nazwa, kier in (("W", (-1, 0)), ("E", (1, 0)), ("N", (0, -1))):
    m, a, b = plan_atrapa(S, kier)
    et = wypad.zbuduj_etapy([a, b, (b[0] + kier[0], b[1] + kier[1], 6)], m)
    e = next(x for x in et if x["typ"] == "LINA")
    sprawdz(f"A1{nazwa} ladowanie na {nazwa} od schodow: cel = pole schodow, schody=True, stoi = punkt przed schodami, ladunek = b",
            tuple(e["cel"]) == (S[0], S[1], 7) and e.get("schody") is True and tuple(e["stoi"]) == a and tuple(e["ladunek"]) == b, e)
    sprawdz(f"A2{nazwa} sprawdz_plan bez uwag", not wypad.sprawdz_plan(et, m), wypad.sprawdz_plan(et, m))

# stare zachowanie bez zmian: pole domyslne przechodnie = zwykla lina/drabina na (b.x, b.y-1)
m, a, b = plan_atrapa(S, (-1, 0), domyslne="chodliwe")
e = next(x for x in wypad.zbuduj_etapy([a, b, (b[0] - 1, b[1], 6)], m) if x["typ"] == "LINA")
sprawdz("A3 pole domyslne (b.x, b.y-1) przechodnie: cel = pole domyslne, bez znacznika schody", tuple(e["cel"]) == (b[0], b[1] - 1, 7) and not e.get("schody"), e)
# bez mapy: jak dotad
e = next(x for x in wypad.zbuduj_etapy([a, b, (b[0] - 1, b[1], 6)], None) if x["typ"] == "LINA")
sprawdz("A4 bez mapy: cel = (b.x, b.y-1), bez schodow", tuple(e["cel"]) == (b[0], b[1] - 1, 7) and not e.get("schody"), e)
# schody bez flagi 2 na gornym pietrze (to nie schody w gore): bez zmiany
m, a, b = plan_atrapa(S, (-1, 0), schody_gora=False)
e = next(x for x in wypad.zbuduj_etapy([a, b, (b[0] - 1, b[1], 6)], m) if x["typ"] == "LINA")
sprawdz("A5 brak flagi 2 na gornym pietrze: bez zmiany", tuple(e["cel"]) == (b[0], b[1] - 1, 7) and not e.get("schody"), e)
# stoimy na polu przejscia: bez zmiany
m, a, b = plan_atrapa(S, (-1, 0))
m.pola[a] = 3
e = next(x for x in wypad.zbuduj_etapy([a, b, (b[0] - 1, b[1], 6)], m) if x["typ"] == "LINA")
sprawdz("A6 pole stania samo ma flage 2: bez zmiany", not e.get("schody") and tuple(e["cel"]) == (b[0], b[1] - 1, 7), e)
# dwa pasujace pola schodow obok pola stania (niejednoznaczne): nie zgadujemy, plan jak dotad
b = (99, 100, 6)
m = Atrapa({(100, 100, 7): 3, (100, 100, 6): 3, (99, 101, 7): 3, (99, 101, 6): 3, (99, 100, 6): 1, (100, 101, 7): 1, (99, 99, 7): 5})
a = (100, 101, 7)
e = next(x for x in wypad.zbuduj_etapy([a, b, (98, 100, 6)], m) if x["typ"] == "LINA")
sprawdz("A7 dwa pasujace pola schodow obok pola stania: _schody_poziome = None, cel jak dotad", wypad._schody_poziome(m, a, b) is None and not e.get("schody")
        and tuple(e["cel"]) == (99, 99, 7), e)
# stare schody z ladowaniem (x, y-1) nad schodami: ta sama regula co w 24.10 (nic nie zmieniamy)
m = Atrapa({(100, 101, 7): 3, (100, 101, 6): 3, (100, 100, 6): 1, (100, 102, 7): 1, (100, 99, 7): 5})
et = wypad.zbuduj_etapy([(100, 102, 7), (100, 100, 6), (100, 99, 6)], m)
e = next(x for x in et if x["typ"] == "LINA")
sprawdz("A8 schody z ladowaniem nad nimi (x, y-1): cel = pole schodow, schody=True", tuple(e["cel"]) == (100, 101, 7) and e.get("schody") is True, e)

# B. prawdziwa mapa i trasy goblinow Ab'Dendriel
if not _mapa.PLIK_MAPY.is_file():
    print("brak pliku mapy, pomijam czesc B")
else:
    MAPA = _mapa.Mapa()
    DOJ = [tuple(p) for p in trasa_io.wczytaj("abdendriel_gobliny_dojscie")[0]]
    et = wypad.zbuduj_etapy(DOJ, MAPA)
    sprawdz("B1 dojscie z depo na spot: etapy IDZ LINA IDZ LINA IDZ", [e["typ"] for e in et] == ["IDZ", "LINA", "IDZ", "LINA", "IDZ"], [e["typ"] for e in et])
    l1, l2 = et[1], et[3]
    sprawdz("B2 pierwsze schody (z8 -> z7) bez zmian: cel (32654,31674,z8), schody, stoi (32654,31675,z8), ladunek (32654,31673,z7)",
            tuple(l1["cel"]) == (32654, 31674, 8) and l1.get("schody") is True and tuple(l1["stoi"]) == (32654, 31675, 8) and tuple(l1["ladunek"]) == (32654, 31673, 7), l1)
    sprawdz("B3 drugie schody (z7 -> z6): cel (32622,31790,z7), schody=True, ladunek (32621,31790,z6)",
            tuple(l2["cel"]) == (32622, 31790, 7) and l2.get("schody") is True and tuple(l2["ladunek"]) == (32621, 31790, 6), l2)
    fc = int(MAPA.flagi(*l2["cel"]))
    fl = int(MAPA.flagi(*l2["ladunek"]))
    sprawdz("B4 cel to schody (flaga 2, nie sciana), ladowanie chodliwe, nie sciana", fc & 2 and not fc & 4 and fl & 1 and not fl & 4, (fc, fl))
    sprawdz("B5 stoi sasiaduje ze schodami, nie ze sciana (32621,31789)", wypad.cheb(l2["stoi"], l2["cel"]) == 1 and tuple(l2["cel"]) != (32621, 31789, 7), l2)
    sprawdz("B6 sprawdz_plan dojscia bez uwag", not wypad.sprawdz_plan(et, MAPA, {}, rampy_ok=True), wypad.sprawdz_plan(et, MAPA, {}, rampy_ok=True)[:2])
    sprawdz("B7 ostatni IDZ zaczyna sie na ladowaniu (32621,31790,z6)", tuple(et[4]["punkty"][0]) == (32621, 31790, 6), et[4]["punkty"][:1])
    POW = [tuple(p) for p in trasa_io.wczytaj("abdendriel_gobliny_do_depo")[0]]
    ep = wypad.zbuduj_etapy(POW, MAPA)
    sprawdz("B8 powrot (w dol) bez zmian: IDZ DZIURA IDZ DZIURA IDZ", [e["typ"] for e in ep] == ["IDZ", "DZIURA", "IDZ", "DZIURA", "IDZ"], [e["typ"] for e in ep])

print(f"{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
