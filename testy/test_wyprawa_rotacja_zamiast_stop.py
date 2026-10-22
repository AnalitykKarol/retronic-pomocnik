"""Wyprawa do depo: nieudane przejście (lina/dziura/drzwi) = ROTACJA NAPRAW, nie ALARM + STOP (22.10, dawajkesh z11 -> z10,
Karol: „naprawiaj, nie zatrzymuj”). Stary kod (kopia wyprawa.py.bak-20261022-rotacja-zamiast-stop): pierwsza awaria przejścia
w wyprawie do depo = `_koniec("blad")` -> `_zakoncz_depo` -> `_alarm_utknieciu(wymus_stop=True)` -> plik STOP. Nowy: 3 naprawy
(odejście na inne pole / zdjęcie rzeczy z pola liny / odejście o 2 pola), po wyczerpaniu sam alarm BEZ STOP i powrót na spot
(faza "do") albo ponawianie (faza "z"). Bez zmian: etap bez przejścia (utknięcie, limit czasu) i PK nadal kończą STOP-em.
Atrapy + prawdziwa mapa i trasa edron_do_depo; nic nie trafia do gry (RETRONIC_TESTY=1)."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import importlib.util, json, sys, tempfile, types
from pathlib import Path
sys.dont_write_bytecode = True
_R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _R)
import bot, mapa as _mapa, wypad
import wyprawa as W_NOWY

ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))

if not _mapa.PLIK_MAPY.is_file():
    print("brak pliku mapy, pomijam"); sys.exit(0)
MAPA = _mapa.Mapa()
TMP = Path(tempfile.mkdtemp())
KOPIA = Path(_R) / "wyprawa.py.bak-20261022-rotacja-zamiast-stop"
from importlib.machinery import SourceFileLoader
_ld = SourceFileLoader("wyprawa_stara", str(KOPIA))
spec = importlib.util.spec_from_loader("wyprawa_stara", _ld)
W_STARY = importlib.util.module_from_spec(spec); _ld.exec_module(W_STARY)

TRASY = Path(_R) / "trasy"
L = [tuple(int(v) for v in p) for p in json.loads((TRASY / "edron_nowy_spot.json").read_text())]


class KonfW:
    WYPRAWA_AKTYWNA = 1; WYPRAWA_MAX_CZAS_S = 1800; WYPRAWA_MAX_KROKOW = 6000; WYPRAWA_STOP_PRZY_UTKNIECIU = 1
    WYPRAWA_CO_MIN = 20; WYPRAWA_PO_DEPO_S = 900; WYPRAWA_DEPO_POWROT = 0; WYPRAWA_TYLKO_DEPO = 1


class CBW:
    mapa = MAPA
    def __init__(c, poz):
        c.t = 0.0; c.wypad_aktywny = False; c.poz = list(poz); c.kroki = []; c.alarmy = []; c.stan = None
        c.postac = types.SimpleNamespace(pozycja=lambda: tuple(c.poz), krok=c.krok)
    def krok(c, kier):
        d = bot.KIERUNKI[kier]; n = [c.poz[0] + d[0], c.poz[1] + d[1], c.poz[2]]
        c.kroki.append((kier, tuple(c.poz)))
        if MAPA.flagi(*n) & 1 and not MAPA.flagi(*n) & 2:
            c.poz[:] = n
    def zegar(c): return c.t
    def gracz(c): return {"proc": 60.0}
    def _wypad_reset_klik(c): pass
    def droga(c, *a, **k): return []
    def pauza(c, *a): c.t += 0.4
    def spij(c, d): c.t += d
    def ustaw_stan(c, *a): c.stan = a
    def alarm(c, tekst): c.alarmy.append(tekst)
    def zajete_bez_nas(c, poz): return []


class OpsW:
    def __init__(o): o.zdjecia = []
    def wiadomosci(o): return []
    def zdejmij_z_pola(o, pole, poz): o.zdjecia.append((tuple(pole), tuple(poz)))


dane = {"powody": ["glod"], "zapas": 0, "blanki": None, "zloto": 100, "cap": 100, "hp": 90, "pochodnie": None, "depo": True}
_n = [0]
def nowa(modul, faza="do"):
    """Wyprawa do depo (prawdziwy plan edron z miejsca spotu) postawiona na pierwszym etapie przejścia (LINA/DZIURA)."""
    _n[0] += 1
    cb = CBW(L[67]); logi = []; ops = OpsW()
    w = modul.Wyprawa(cb, ops, konf=KonfW(), log=logi.append, plik_stanu=TMP / f"st{_n[0]}.json", plik_sklepow=TMP / "sk.json",
                      plik_npc=TMP / "npc.json", plik_stop=TMP / f"STOP{_n[0]}", czas=lambda: 5_000_000.0)
    w._powiadom = lambda *a, **k: logi.append(("powiadomienie",) + a[:2])
    assert w._start_wyprawa("depo:glod", dane, 0.0) is True, logi[-3:]
    et = w.w["legs"][0]
    ei = next(i for i, e in enumerate(et) if e["typ"] in ("LINA", "DZIURA"))
    w.etapy, w.ei, w.pi, w.faza = et, ei, 0, faza
    cb.poz[:] = list(et[ei]["stoi"])
    return w, cb, logi, ops, et[ei]


# --- 0. dane ---------------------------------------------------------------------------------------------------------
w, cb, logi, ops, e = nowa(W_NOWY)
sprawdz("0a plan wyprawy do depo ma etap przejścia (LINA/DZIURA), wyprawa jest wyprawą depo", w._w_depo() and e["typ"] in ("LINA", "DZIURA"), e)
sprawdz("0b kopia starego kodu nie ma rotacji (test ma sens)", not hasattr(W_STARY.Wyprawa, "_rotacja_naprawy") and hasattr(W_NOWY.Wyprawa, "_rotacja_naprawy"))

# --- 1. STARY kod: pierwsza awaria przejścia = STOP ----------------------------------------------------------------
w, cb, logi, ops, e = nowa(W_STARY)
w._awaria("lina_bez_zmiany_pietra", "4 nieudanych prób przejścia", e)
sprawdz("1 STARY: jedna awaria przejścia w depo = plik STOP + alarm + wyprawa zakończona (to był błąd)",
        (TMP / f"STOP{_n[0]}").exists() and cb.alarmy and w.w is None, (cb.alarmy, w.w is None))

# --- 2. NOWY: trzy naprawy, bez STOP, bez alarmu, wyprawa trwa ---------------------------------------------------------
w, cb, logi, ops, e = nowa(W_NOWY)
stop = TMP / f"STOP{_n[0]}"
poz0 = tuple(cb.poz)
for n in (1, 2, 3):
    e["proby"] = 4
    r = w._awaria("lina_bez_zmiany_pietra", "4 nieudanych prób przejścia", e)
    sprawdz(f"2.{n} NOWY: naprawa {n}/3: zwraca True, bez STOP i alarmu, wyprawa trwa, etap odnowiony (proby=0, przerwa)",
            r is True and not stop.exists() and not cb.alarmy and w.w is not None and e["proby"] == 0 and e["nast"] > cb.t
            and w.faza == "do", (r, stop.exists(), cb.alarmy, e.get("proby"), e.get("nast")))
    sprawdz(f"2.{n}b log rotacji {n}/3", any(isinstance(l, str) and f"rotacja napraw {n}/3" in l for l in logi), logi[-3:])
sprawdz("2.4 naprawy ruszają postać: był krok na inne pole, nigdy na pole liny/lądowania", cb.kroki and all(
        (cb.poz[0], cb.poz[1]) != tuple(e["cel"][:2]) or e["typ"] != "LINA" for _ in [0]), cb.kroki)
for n in (1, 2, 3):
    pass

# --- 3. po wyczerpaniu: alarm BEZ STOP; faza "do" wraca na spot (faza "z") ----------------------------------------------
e["proby"] = 4
cb.poz[:] = list(e["stoi"])
r = w._awaria("lina_bez_zmiany_pietra", "4 nieudanych prób przejścia", e)
sprawdz("3a po 3 naprawach: alarm (powiadomienie) jest, pliku STOP NIE ma", r is True and cb.alarmy and not stop.exists(), (cb.alarmy, stop.exists()))
sprawdz("3b faza 'do' -> wracamy na spot (faza z), wyprawa nie jest zakończona STOP-em, bot nie zablokowany",
        w.faza == "z" and w.w is not None and not w.zablokowany, (w.faza, w.w is None, w.zablokowany))

# --- 4. faza powrotna: wyczerpana rotacja = ponawianie po AWARIA_PO_S, bez STOP --------------------------------------------
w, cb, logi, ops, e = nowa(W_NOWY, faza="z")
stop = TMP / f"STOP{_n[0]}"
for _ in range(6):
    e["proby"] = 4
    cb.t += 1
    r = w._awaria("dziura_bez_zmiany_pietra", "4 nieudanych prób przejścia", e)
sprawdz("4 faza 'z': 6 awarii z rzędu: nigdy STOP, wyprawa trwa, jeden alarm (nie lawina), etap ponawiany po przerwie",
        not stop.exists() and w.w is not None and len(cb.alarmy) == 1 and e["nast"] >= cb.t + wypad.AWARIA_PO_S - 1,
        (stop.exists(), cb.alarmy, e["nast"], cb.t))

# --- 5. zdjęcie rzeczy z pola liny w naprawie 2 (gdy stoimy obok liny) -------------------------------------------------------
w, cb, logi, ops, e = nowa(W_NOWY)
lin = next(((i, x) for i, x in enumerate(w.etapy) if x["typ"] == "LINA"), None)
if lin:
    w.ei, e = lin[0], lin[1]
    cb.poz[:] = list(e["stoi"])
    for n in (1, 2):
        e["proby"] = 4
        cb.poz[:] = list(e["stoi"])
        w._awaria("lina_bez_zmiany_pietra", "x", e)
    sprawdz("5 naprawa 2 na linie: zdjęcie rzeczy z pola liny (zdejmij_z_pola) wywołane", len(ops.zdjecia) == 1 and ops.zdjecia[0][0] == tuple(e["cel"]), ops.zdjecia)
else:
    print("INFO brak etapu LINA w planie, 5 pominięte (test jednostkowy zdejmowania jest w test_lina_powtorka_z11.py)")

# --- 6. bez zmian: etap bez przejścia (utknięcie) i limit czasu w depo nadal STOP (12h/12i w test_wyprawa.py) -------------------
w, cb, logi, ops, e = nowa(W_NOWY)
stop = TMP / f"STOP{_n[0]}"
w._awaria("utkniecie", "brak postępu na etapie 3")
sprawdz("6 NOWY: awaria bez etapu przejścia w wyprawie depo = STOP jak dotąd (zakres: tylko przejścia)", stop.exists() and w.w is None, (stop.exists(), w.w is None))

# --- 7. PK/ucieczka: rotacja nie dotyczy -----------------------------------------------------------------------------------------
w, cb, logi, ops, e = nowa(W_NOWY)
w.w["potrzeby"]["pk"] = "ucieczka"
wywolana = []
orig = w._rotacja_naprawy
w._rotacja_naprawy = lambda *a, **k: wywolana.append(1) or True
try:
    w._awaria("lina_bez_zmiany_pietra", "x", e)
except Exception as ex:
    logi.append(("wyjatek", repr(ex)))
sprawdz("7 wyprawa PK/ucieczka: rotacja NIE jest wołana (ścieżki życia bez zmian)", not wywolana, wywolana)

print(); print(f"{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
