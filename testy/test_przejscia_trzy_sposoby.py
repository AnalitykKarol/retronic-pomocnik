"""Trzy sposoby przejścia i pamięć (21.10, Karol: „postać powinna próbować 3 rzeczy: wejść na punkt, kliknąć na niego i użyć liny,
zaznaczać, który zadziałał, i już pamiętać”). Przypadek: kutangen 15:06, wyprawa do depo na Rooku, stoi na (32029,32194,z9) obok
drabiny (32029,32195,z9); stary kod klikał tylko pole „drabiny” (b.y-1 = pole, na którym stał), linę i sąsiadów E/W/N:
8 prób, ALARM, STOP. Atrapa gry: Use drabiny (z pola obok albo z niej) przenosi na (32029,32196,z8), liny brak."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, sys, tempfile, types
sys.dont_write_bytecode = True
_R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _R)
import mapa as _mapa, wypad, pietra

ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

PAM = _os.path.join(tempfile.mkdtemp(), "przejscia_nauczone.json")
wypad.PLIK_PRZEJSC = PAM
M = _mapa.mapa()
pts = [tuple(p) for p in json.load(open(_os.path.join(_R, "trasy", "rook_raty_z9_dojscie_odwrocona.json")))]
et = wypad.zbuduj_etapy(pts, M)
EI = next(i for i, e in enumerate(et) if e["typ"] == "LINA" and e["stoi"] == (32029, 32195, 9))
DRABINA, LAD = (32029, 32195, 9), (32029, 32196, 8)


def gra(start, trzy, lina_obok=False):
    """Uruchamia _lina aż do zmiany piętra albo awarii; zwraca (wynik, liczba prób, użyte pola)."""
    stan = {"poz": start, "awaria": None}
    uzyte, logi = [], []

    def krok(kier):
        dx, dy = {"Up": (0, -1), "Down": (0, 1), "Left": (-1, 0), "Right": (1, 0)}[kier]
        p = stan["poz"]
        stan["poz"] = (p[0] + dx, p[1] + dy, p[2])

    def uzyj_pole(pole, poz):
        uzyte.append(tuple(pole))
        if tuple(pole) == DRABINA and wypad.cheb(stan["poz"], pole) <= 1:
            stan["poz"] = LAD

    def uzyj_line(cel, poz):
        uzyte.append(("lina", tuple(cel), tuple(stan["poz"])))
        if lina_obok:                       # lina działa tylko z pola OBOK pola liny (nie z niego)
            if tuple(cel) == DRABINA and wypad.cheb(stan["poz"], cel) == 1 and tuple(stan["poz"][:2]) != tuple(cel[:2]):
                stan["poz"] = LAD
            return
        raise wypad.BrakEkranu("nie widzę liny (rope)")

    cb = types.SimpleNamespace(postac=types.SimpleNamespace(krok=krok, pozycja=lambda: stan["poz"]), pauza=lambda *a: None,
                               spij=lambda *a: None, _wypad_reset_klik=lambda: None)
    w = types.SimpleNamespace(cb=cb, ops=types.SimpleNamespace(uzyj_pole=uzyj_pole, uzyj_line=uzyj_line), log=logi.append,
                              pj_proby=0, ei=EI, pi=0, etapy=et, utk=0, postep=None, przystanek_od=None,
                              _zajete_pola=lambda poz: set(), _k=lambda n, d: (1 if trzy else 0) if n == "PRZEJSCIE_TRZY_SPOSOBY" else d,
                              _pilnuj_przejscia=lambda *a: None, _tele=lambda *a, **k: None, _blad=lambda *a, **k: None)
    w._awaria = lambda typ, opis, e=None: stan.__setitem__("awaria", typ) or True
    for n in ("_lina", "_zejdz_z_pola", "_kier_do_pola", "_po_przejsciu", "_nie_czas", "_porazka_przejscia"):
        setattr(w, n, types.MethodType(getattr(wypad.Wypad, n), w))
    w._proby_drabiny = wypad.Wypad._proby_drabiny
    e = dict(et[EI])
    t = 0.0
    for _ in range(20):
        t += 30.0
        w._lina(stan["poz"], e, t)
        if stan["poz"][2] == 8 or stan["awaria"]:
            break
    prob = sum(1 for l in logi if "próba" in l)
    return stan, prob, uzyte, logi


s0, n0, u0, _ = gra((32029, 32194, 9), trzy=False)
sprawdz("stary sposób (pokrętło 0): z (32029,32194) drabina nie kliknięta, awaria", s0["poz"][2] == 9 and s0["awaria"] and DRABINA not in u0,
        (s0, n0, u0))
s1, n1, u1, l1 = gra((32029, 32194, 9), trzy=True)
sprawdz("trzy sposoby: wychodzi na z8", s1["poz"] == LAD and not s1["awaria"], (s1, n1, u1))
sprawdz("trzy sposoby: najwyżej 2 próby (krok na drabinę, potem Use)", n1 <= 2, (n1, l1))
pam = wypad.przejscia_nauczone(PAM)
sprawdz("zapamiętane: Use na (32029,32195,9) -> z8", pam.get("32029,32195,9>8", {}).get("tryb") == "use", pam)
s2, n2, u2, l2 = gra((32029, 32194, 9), trzy=True)
sprawdz("drugi raz: pierwsza próba z pamięci = Use drabiny, 1 próba", s2["poz"] == LAD and n2 == 1 and u2[:1] == [DRABINA], (n2, u2))
sprawdz("licznik w pamięci rośnie", wypad.przejscia_nauczone(PAM)["32029,32195,9>8"]["n"] == 2)
s3, n3, u3, _ = gra((32029, 32195, 9), trzy=True)
sprawdz("stojąc na drabinie (jak rano 07:41): wychodzi od razu", s3["poz"] == LAD and n3 == 1, (n3, u3))

lista = wypad.proby_trzy_sposoby((32029, 32194, 9), [(32029, 32195, 9)], 8, plik=_os.path.join(tempfile.mkdtemp(), "p.json"))
sprawdz("lista bez pamięci: wejść, kliknąć, lina", [t for t, _ in lista] == ["krok", "use", "lina"], lista)
sprawdz("bez liny: lina pominięta", [t for t, _ in wypad.proby_trzy_sposoby((32029, 32194, 9), [(32029, 32195, 9)], 8, lina=False,
        plik=_os.path.join(tempfile.mkdtemp(), "p.json"))] == ["krok", "use"])

# pietra (patrol, powrót po wpadnięciu): sposób z pamięci pierwszy, w liście wszystkie trzy sposoby
def atrapa(trzy):
    p = types.SimpleNamespace(cb=types.SimpleNamespace(mapa=M), _dane=lambda: True, ops=None,
                              _k=lambda n, d: (1 if trzy else 0) if n == "PRZEJSCIE_TRZY_SPOSOBY" else d)
    for nazwa in ("_tryby", "_tryby_baza", "_stosuje", "_wybierz"):
        setattr(p, nazwa, types.MethodType(getattr(pietra.Pietra, nazwa), p))
    return p
ku = {"pole": DRABINA, "pewne": False, "lad": LAD}
stare = atrapa(False)._tryby(ku, {"z0": 9})
nowe = atrapa(True)._tryby(ku, {"z0": 9})
sprawdz("pietra: pokrętło 0 = lista jak dotąd", stare == pietra.Pietra._tryby_baza(atrapa(False), ku, {"z0": 9}), stare)
sprawdz("pietra: pamięć Use -> R pierwsze", nowe[0] == "R", nowe)
sprawdz("pietra: w górę są krok, R i lina", all(t in nowe for t in ("krok", "R", "lina")), nowe)
kd = {"pole": (32370, 32213, 7), "pewne": True, "lad": (32370, 32213, 8)}
sprawdz("pietra: w dół są krok i use, bez liny", all(t in atrapa(True)._tryby(kd, {"z0": 7}) for t in ("krok", "use"))
        and "lina" not in atrapa(True)._tryby(kd, {"z0": 7}))
w = types.SimpleNamespace(log=lambda *a: None)
pietra.Pietra._naucz(w, "krok->use_wlasne", (32370, 32213, 7), (32370, 32213, 7), 8)
sprawdz("pietra: sukces zapisuje do wspólnej pamięci", wypad.przejscia_nauczone(PAM).get("32370,32213,7>8", {}).get("tryb") == "use")

# 21.10 dawajkesh z9 (33168,31824): lina z własnego pola nie działa; bot schodzi o kratkę i używa jej z pola obok
_stara = wypad.proby_trzy_sposoby
wypad.proby_trzy_sposoby = lambda *a, **k: [("lina", DRABINA)]        # tylko lina, bez Use i kroku
s4, n4, u4, l4 = gra(DRABINA, trzy=True, lina_obok=True)
wypad.proby_trzy_sposoby = _stara
lin = [u for u in u4 if u[0] == "lina"]
sprawdz("lina: była użyta", len(lin) >= 1, u4)
sprawdz("lina: nigdy z własnego pola", all(tuple(u[2][:2]) != tuple(u[1][:2]) for u in lin), lin)
sprawdz("lina: stojąc na polu liny schodzi o kratkę i wychodzi na z8", s4["poz"] == LAD and not s4["awaria"], (s4, u4, l4))

print()
print(f"{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
