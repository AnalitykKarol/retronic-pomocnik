"""Powrót do depo z jaskini trolli z9z: lina z11 (33147,31824) -> z10 (22.10 13:54, dawajkesh, wyprawa:depo:blanki).
Log: „lina próba 1/4 (lina) z (33146,31823,11), pole (33147,31824)” -> lina_bez_zmiany_pietra, potem trzy próby, które liny nie
zastępują (Use na własnym polu, krok na pole liny, Use na polu liny) -> „4 nieudanych prób” -> ALARM -> STOP. W trybie trzech
sposobów lina była w liście JEDEN raz, więc jedna nieudana próba (zwłoki/rzecz na polu liny, kliknięcie w trakcie kroku, lag,
lina działająca tylko z pola ortogonalnego) kończyła wyprawę. Teraz: po pierwszej próbie liny jeszcze dwie, z korektą (zejście na
pole obok liny, zdjęcie rzeczy z pola). Atrapa gry na prawdziwej mapie i prawdziwym etapie trasy trolle_edron_z9z_do_depo."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, sys, tempfile, types
sys.dont_write_bytecode = True
_R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _R)
import mapa as _mapa, wypad

ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

PAM = _os.path.join(tempfile.mkdtemp(), "przejscia_nauczone.json")
wypad.PLIK_PRZEJSC = PAM
M = _mapa.mapa()
pts = [tuple(p) for p in json.load(open(_os.path.join(_R, "trasy", "trolle_edron_z9z_do_depo.json")))]
et = wypad.zbuduj_etapy(pts, M)
EI = next(i for i, e in enumerate(et) if e["typ"] == "LINA" and e["stoi"] == (33146, 31823, 11))
LINA, LAD, START = (33147, 31824, 11), (33147, 31825, 10), (33146, 31823, 11)
sprawdz("etap z danych trasy: stoi (33146,31823,11), pole liny (33147,31824,11), lądowanie (33147,31825,10)",
        et[EI]["cel"] == LINA and tuple(et[EI]["ladunek"]) == LAD, et[EI])
sprawdz("mapa: pole liny to zwykła podłoga z11, nad nim dziura z10 (flaga 3)",
        M.flagi(*LINA) == 1 and M.flagi(33147, 31824, 10) == 3)


def gra(start=START, zwloki=False, zawiedz_pierwsza=0, tylko_ortogonalnie=False, bez_liny=False, zapamietaj=True):
    """_lina w pętli aż do z10 albo awarii. zwloki: lina nie działa, póki nie padnie zdejmij_z_pola. zawiedz_pierwsza: tyle
    pierwszych Use liny nic nie robi. tylko_ortogonalnie: lina działa tylko z pola ortogonalnego do pola liny."""
    if zapamietaj:
        _os.path.exists(PAM) and _os.remove(PAM)
        wypad.zapisz_przejscie(LINA, 10, "lina")                     # jak w przejscia_nauczone.json: tryb lina n=5
    st = {"poz": start, "awaria": None, "zwloki": zwloki, "lina_uzyc": 0, "zdjecia": 0, "inne": []}
    logi = []

    def krok(kier):
        dx, dy = {"Up": (0, -1), "Down": (0, 1), "Left": (-1, 0), "Right": (1, 0)}[kier]
        p = st["poz"]
        q = (p[0] + dx, p[1] + dy, p[2])
        if M.przechodnie(*q):
            st["poz"] = q

    def uzyj_pole(pole, poz):
        st["inne"].append(tuple(pole))                              # Use zwykłego pola: liny nie zastąpi

    def uzyj_line(cel, poz):
        st["lina_uzyc"] += 1
        p = st["poz"]
        if bez_liny or st["lina_uzyc"] <= zawiedz_pierwsza or st["zwloki"]:
            return
        if tuple(cel) != LINA or wypad.cheb(p, cel) != 1 or tuple(p[:2]) == tuple(cel[:2]):
            return
        if tylko_ortogonalnie and p[0] != cel[0] and p[1] != cel[1]:
            return
        st["poz"] = LAD

    def zdejmij(pole, poz):
        st["zdjecia"] += 1
        st["zwloki"] = False

    cb = types.SimpleNamespace(postac=types.SimpleNamespace(krok=krok, pozycja=lambda: st["poz"]), pauza=lambda *a: None,
                               spij=lambda *a: None, _wypad_reset_klik=lambda: None, mapa=M)
    ops = types.SimpleNamespace(uzyj_pole=uzyj_pole, uzyj_line=uzyj_line)
    if hasattr(wypad.OperacjeZywe, "zdejmij_z_pola"):
        ops.zdejmij_z_pola = zdejmij
    w = types.SimpleNamespace(cb=cb, ops=ops, log=logi.append, pj_proby=0, ei=EI, pi=0, etapy=et, utk=0, postep=None,
                              przystanek_od=None, _zajete_pola=lambda poz: set(),
                              _k=lambda n, d: 1 if n == "PRZEJSCIE_TRZY_SPOSOBY" else d,
                              _pilnuj_przejscia=lambda *a: None, _tele=lambda *a, **k: None, _blad=lambda *a, **k: None)
    w._awaria = lambda typ, opis, e=None: st.__setitem__("awaria", typ) or True
    for n in ("_lina", "_zejdz_z_pola", "_kier_do_pola", "_po_przejsciu", "_nie_czas", "_porazka_przejscia"):
        setattr(w, n, types.MethodType(getattr(wypad.Wypad, n), w))
    w._proby_drabiny = wypad.Wypad._proby_drabiny
    e = dict(et[EI])
    t = 0.0
    for _ in range(20):
        t += 30.0
        w._lina(st["poz"], e, t)
        if st["poz"][2] == 10 or st["awaria"]:
            break
    return st, logi


s, l = gra()
sprawdz("A0 zwykły przebieg (jak 11:23): pierwsza lina wychodzi na z10, jedno użycie, bez zdejmowania",
        s["poz"] == LAD and s["lina_uzyc"] == 1 and s["zdjecia"] == 0 and not s["awaria"], (s["lina_uzyc"], s["zdjecia"]))

s, l = gra(zwloki=True)
sprawdz("A zwłoki na polu liny (jak 13:54): bot zdejmuje rzecz z pola i wychodzi na z10, bez awarii",
        s["poz"] == LAD and not s["awaria"] and s["zdjecia"] >= 1, (s, l))

s, l = gra(zawiedz_pierwsza=1)
sprawdz("B jednorazowa porażka liny (lag, klik w trakcie kroku): druga próba liny wychodzi na z10",
        s["poz"] == LAD and not s["awaria"] and s["lina_uzyc"] == 2, (s["lina_uzyc"], l))

s, l = gra(tylko_ortogonalnie=True)
sprawdz("C lina działa tylko z pola ortogonalnego (jak 18:07 z (33147,31823)): bot schodzi ze skosu i wychodzi na z10",
        s["poz"] == LAD and not s["awaria"] and s["lina_uzyc"] == 2, (s, l))

s, l = gra(bez_liny=True)
sprawdz("D lina naprawdę niemożliwa: ograniczona liczba prób (<= 8), awaria jak dotąd, bez pętli",
        s["awaria"] == "drabina_bez_zmiany_pietra" and s["lina_uzyc"] == 3 and s["lina_uzyc"] <= 8, (s["lina_uzyc"], s["awaria"]))

s, l = gra(zapamietaj=False, zawiedz_pierwsza=1)
sprawdz("E bez pamięci przejścia (pierwszy raz w tym miejscu): też dostaje powtórki liny",
        s["poz"] == LAD and not s["awaria"], (s["lina_uzyc"], l))

lista = wypad.proby_trzy_sposoby(START, [START, LINA], 10, plik=_os.path.join(tempfile.mkdtemp(), "p.json"))
if hasattr(wypad, "powtorz_line"):
    lista2 = wypad.powtorz_line(lista)
    sprawdz("lista: pole liny ma 3 próby liny (1 + 2 powtórki)", [t for t, q in lista2 if t == "lina" and q == LINA] == ["lina"] * 3, lista2)
else:
    sprawdz("lista: pole liny ma 3 próby liny", False, "brak powtorz_line")

print()
print(f"{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
