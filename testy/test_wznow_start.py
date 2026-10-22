"""Start bota kontynuuje od miejsca, w którym postać stoi (Karol 22.10, dawajkesh 13:56): restart po przerwanej wyprawie
do depo nie puszcza dojścia na spot, tylko dokańcza wyprawę (wznow_start.sprobuj -> Wyprawa._wznow). Stary kod
(RETRONIC_WZNOW_START=0 / wznow_start.WLACZONE=False) = restart nie wznawia, mozg.main idzie dojściem. Do tego:
na spocie / w pętli = bez dojścia, w połowie dojścia = od najbliższego punktu, w mieście bez zadania = dojście jak dotąd.

Atrapy świata biorę wprost z testy/test_wyprawa.py (ten plik nie jest importowalny: wykonuje testy przy imporcie),
dlatego wycinam z niego sekcję definicji (do '# --- 0.') i pomocniki depo (konf_depo, sp_bez, krok_dokladny)."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import json
import sys
import types
from pathlib import Path

sys.dont_write_bytecode = True
_R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _R)

_zr = (Path(_R) / "testy" / "test_wyprawa.py").read_text()
_a = _zr.index("# --- 0. dane i pokrętła")
_b0 = _zr.index("DEPO = (32348, 32225, 7)")
_b1 = _zr.index("powiad12 = []")
_ns = {"__name__": "atrapy_wyprawa", "__file__": str(Path(_R) / "testy" / "test_wyprawa.py")}
exec(compile(_zr[:_a] + "\n" + _zr[_b0:_b1], "test_wyprawa(atrapy)", "exec"), _ns)   # noqa: S102
if "MAPA" not in _ns:
    print("brak atrap")
    sys.exit(0)
nowy, pre, bieg, ev, konf_depo, sp_bez, krok_dokladny = (_ns[n] for n in ("nowy", "pre", "bieg", "ev", "konf_depo", "sp_bez", "krok_dokladny"))
TMP, Konf, W, DEPO = _ns["TMP"], _ns["Konf"], _ns["W"], _ns["DEPO"]

import powiadom as _pw
_pw.powiadom = lambda *a, **kw: None
import mozg
import wznow_start

ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


def start_depo(**kw):
    s, cb, w, k = nowy(jedzenie=0, konf=konf_depo(), sklepy=sp_bez, **kw)
    krok_dokladny(cb)
    cb.jedzenie_nie_do = s.t + 100000
    assert pre(s, cb, w), "wyprawa do depo nie wystartowała"
    return s, cb, w, k


def idz_ticki(s, cb, w, n):
    for _ in range(n):
        s.t += 0.3
        s.wall += 0.3
        cb.ruch_poz = tuple(s.poz)
        cb.ostatnie_stwory = list(s.stwory)
        cb.cel = s.cel
        w.tick()


def stan(w):
    return json.loads(w.plik_stanu.read_text())


logi = []
log = logi.append

# --- 1. kandydat: czysta logika zapisu stanu ----------------------------------------------------------------
T = 1_000_000.0
akt = {"aktywna": True, "zapis_wall": T - 60, "potrzeby": {"depo": True}, "baza": "troll", "powod": "wyprawa:depo:glod"}
sprawdz("1a wyprawa w toku (kill/restart) = kandydat 'aktywna'", wznow_start.kandydat(akt, T)[0] == "aktywna")
sprawdz("1b zapis sprzed 5 h = nie", wznow_start.kandydat(dict(akt, zapis_wall=T - 5 * 3600), T)[0] is None)
bl = {"aktywna": False, "wynik": "blad", "zapis_wall": T - 300, "potrzeby": {"depo": True}, "baza": "troll",
      "opis": "utknięcie w marszu z11 -> z10"}
sprawdz("1c zakończona błędem (utknięcie, STOP) = kandydat 'blad'", wznow_start.kandydat(bl, T)[0] == "blad")
sprawdz("1d błąd PK / teleport = nigdy automatem",
        wznow_start.kandydat(dict(bl, potrzeby={"pk": True}), T)[0] is None
        and wznow_start.kandydat(dict(bl, opis="teleport po drodze"), T)[0] is None)
sprawdz("1e ręczne WROC zakończone błędem >30 min temu = nie, świeże = tak",
        wznow_start.kandydat(dict(bl, potrzeby={"reczny": True}, zapis_wall=T - 3600), T)[0] is None
        and wznow_start.kandydat(dict(bl, potrzeby={"reczny": True}, zapis_wall=T - 600), T)[0] == "blad")
sprawdz("1f w mieście/depo bez zadania (wynik 'depo', aktywna=False) = nie kandydat",
        wznow_start.kandydat({"aktywna": False, "wynik": "depo", "zapis_wall": T - 10}, T)[0] is None
        and wznow_start.kandydat({}, T)[0] is None)
sprawdz("1g limit 3 wznowień w 2 h: trzecie jeszcze tak, czwarte nie; po oknie licznik się zeruje",
        not wznow_start.za_wiele_prob({"wznow_start": {"n": 2, "t": T - 60}}, T)[0]
        and wznow_start.za_wiele_prob({"wznow_start": {"n": 3, "t": T - 60}}, T)[0]
        and not wznow_start.za_wiele_prob({"wznow_start": {"n": 3, "t": T - 3 * 3600}}, T)[0])
sprawdz("1h powody: 'depo:blanki+zapas' -> blanki, zapas", wznow_start.powody({"powod": "wyprawa:depo:blanki+zapas"}) == {"blanki", "zapas"})

# powód blanki już nie zachodzi (w plecaku jest >= próg) = nie wznawia
for ile, oczek in ((0, True), (500, False)):
    fake = types.SimpleNamespace(ops=types.SimpleNamespace(plecak=lambda: {"p": 1}), _ile=lambda p, n, ile=ile: ile,
                                 _kw=lambda n: 30)
    sprawdz(f"1i blanki={ile}, próg 30: powód {'zachodzi' if oczek else 'ustał'}",
            wznow_start.powod_aktualny(fake, {"powod": "wyprawa:depo:blanki"})[0] is oczek)
sprawdz("1j ręczne WROC: powód zawsze aktualny", wznow_start.powod_aktualny(None, {"powod": "wyprawa:reczny"})[0] is True)

# --- 2. przypadek dawajkesh: restart w trakcie wyprawy do depo, STAN 'aktywna' ----------------------------------
for ver in ("stary", "nowy"):
    wznow_start.WLACZONE = (ver == "nowy")
    s, cb, w, k = start_depo()
    idz_ticki(s, cb, w, 50)                                  # kilkanaście kroków drogi do depo
    poz0 = tuple(s.poz)
    plik = w.plik_stanu
    st0 = stan(w)
    sprawdz(f"2a [{ver}] przed restartem wyprawa w toku, stan zapisany, postać w drodze (nie na starcie)",
            st0.get("aktywna") and st0.get("potrzeby", {}).get("depo") and w.w is not None and poz0 != DEPO, st0)
    # kill procesu: zapis stanu zostaje, nowy proces = nowa Wyprawa/cavebot
    _, cb2, w2, _ = nowy(poz=poz0, konf=konf_depo(), sklepy=sp_bez, stan=plik, swiat=s)
    krok_dokladny(cb2)
    cb2.jedzenie_nie_do = s.t + 100000
    kand = wznow_start.jest_kandydat(plik, s.wall)
    wynik = wznow_start.sprobuj(w2, log, teraz_wall=s.wall)
    if ver == "stary":
        sprawdz("2b STARY KOD: restart nie wznawia wyprawy (mozg.main pójdzie dojściem na spot)",
                wynik is False and not cb2.wypad_aktywny and w2.w is None, (wynik, logi[-1:]))
    else:
        sprawdz("2b NOWY KOD: restart wznawia wyprawę z bieżącej pozycji (bez dojścia)",
                kand and wynik is True and cb2.wypad_aktywny and w2.w is not None, (kand, wynik, logi[-3:]))
        sprawdz("2c wznowiona wyprawa to wyprawa do depo i plan zaczyna od BIEŻĄCEJ pozycji (nie od początku trasy)",
                w2.w["potrzeby"] == {"depo": True} and w2.w.get("wznowiona") is not False
                and tuple(s.poz) == poz0, (w2.w and w2.w.get("potrzeby"), s.poz, poz0))
        n, wyst = bieg(s, cb2, w2, maks=14000)
        kon = ev(s, "wyprawa_koniec")
        sprawdz("2d dokończona z miejsca, w którym stała: dotarła do depo (koniec 'depo')",
                wyst and tuple(s.poz) == DEPO and kon and kon[-1]["wynik"] == "depo", (s.poz, kon[-1:] if kon else kon))
        sprawdz("2e stan po dokończeniu: wyprawa nieaktywna, licznik wznowień po starcie zapisany",
                stan(w2).get("aktywna") is False and (stan(w2).get("wznow_start") or {}).get("n") == 1, stan(w2))
wznow_start.WLACZONE = True

# --- 3. restart po zacięciu: stan 'blad' + STOP (dokładnie przypadek 22.10), nowy kod dokańcza ---------------------
for ver in ("stary", "nowy"):
    wznow_start.WLACZONE = (ver == "nowy")
    s, cb, w, k = start_depo()
    idz_ticki(s, cb, w, 50)
    s.blokada_marszu = True                               # utknięcie w marszu: alarm + STOP, wynik 'blad' (jak 12h)
    bieg(s, cb, w, maks=3000)
    st = stan(w)
    sprawdz(f"3a [{ver}] zacięcie: wyprawa zakończona 'blad', aktywna=False (stan z 22.10 13:5x)",
            st.get("wynik") == "blad" and st.get("aktywna") is False and st.get("nast_wall", 0) > s.wall, st)
    s.blokada_marszu = False                              # restart naprawił przyczynę (poprawka przejścia)
    poz0 = tuple(s.poz)
    _, cb2, w2, _ = nowy(poz=poz0, konf=konf_depo(), sklepy=sp_bez, stan=w.plik_stanu, swiat=s)
    krok_dokladny(cb2)
    cb2.jedzenie_nie_do = s.t + 100000
    wynik = wznow_start.sprobuj(w2, log, teraz_wall=s.wall)
    if ver == "stary":
        sprawdz("3b STARY KOD: po zacięciu restart nie wznawia (karencja 'nast_wall'): dojście na spot",
                wynik is False and not cb2.wypad_aktywny, (wynik, logi[-1:]))
    else:
        sprawdz("3b NOWY KOD: po zacięciu restart wznawia wyprawę do depo z bieżącej pozycji", wynik is True and cb2.wypad_aktywny, (wynik, logi[-3:]))
        n, wyst = bieg(s, cb2, w2, maks=14000)
        kon = ev(s, "wyprawa_koniec")
        sprawdz("3c dokończona: depo osiągnięte, bez powrotu na spot", wyst and tuple(s.poz) == DEPO and kon and kon[-1]["wynik"] == "depo"
                and cb2.wroty == [], (s.poz, kon[-1:] if kon else kon))
wznow_start.WLACZONE = True

# --- 4. wznowienie się nie udaje -> stara ścieżka bez skutków ubocznych -------------------------------------------
# 4a: zbyt wiele prób (pętla restart -> zacięcie)
s, cb, w, k = start_depo()
idz_ticki(s, cb, w, 60)
w._stan_zapisz(wznow_start={"n": 3, "t": s.wall - 60})
_, cb2, w2, _ = nowy(poz=tuple(s.poz), konf=konf_depo(), sklepy=sp_bez, stan=w.plik_stanu, swiat=s)
sprawdz("4a trzecie wznowienie w ciągu 2 h: odmowa, dojście jak dotąd", wznow_start.sprobuj(w2, log, teraz_wall=s.wall) is False and not cb2.wypad_aktywny)
# 4b: pozycja daleko od planu (postać poza zasięgiem trasy wyprawy, np. po ręcznej grze) -> bez wznowienia, stan nie psuje karencji
s, cb, w, k = start_depo()
idz_ticki(s, cb, w, 60)
st_przed = stan(w)
s.poz[:] = [33094, 31753, 8]                              # spot Edron: nie ma jej na trasie wyprawy z Thais
_, cb2, w2, _ = nowy(poz=tuple(s.poz), konf=konf_depo(), sklepy=sp_bez, stan=w.plik_stanu, swiat=s)
wynik = wznow_start.sprobuj(w2, log, teraz_wall=s.wall)
sprawdz("4b poza planem wyprawy: nie wznawia, wypad nieaktywny", wynik is False and not cb2.wypad_aktywny, (wynik, logi[-2:]))
# 4c: kill-switch środowiskowy
wznow_start.WLACZONE = False
s, cb, w, k = start_depo()
idz_ticki(s, cb, w, 60)
_, cb2, w2, _ = nowy(poz=tuple(s.poz), konf=konf_depo(), sklepy=sp_bez, stan=w.plik_stanu, swiat=s)
sprawdz("4c RETRONIC_WZNOW_START=0 (WLACZONE=False): zawsze stara ścieżka", wznow_start.sprobuj(w2, log, teraz_wall=s.wall) is False and not cb2.wypad_aktywny)
wznow_start.WLACZONE = True
# 4d: wyjątek w _wznow nie wywraca startu
s, cb, w, k = start_depo()
idz_ticki(s, cb, w, 60)
_, cb2, w2, _ = nowy(poz=tuple(s.poz), konf=konf_depo(), sklepy=sp_bez, stan=w.plik_stanu, swiat=s)
w2._wznow = lambda teraz: (_ for _ in ()).throw(RuntimeError("awaria"))
sprawdz("4d wyjątek w wznowieniu: stara ścieżka, bez wyjątku na zewnątrz", wznow_start.sprobuj(w2, log, teraz_wall=s.wall) is False)
sprawdz("4e brak obiektu wyprawy (CavebotMozgu bez wyprawy): False", wznow_start.sprobuj(None, log) is False)

# --- 5. zmiany w mozg.main: dojście i spot (prawdziwe trasy) ----------------------------------------------------
TRASY = Path(_R) / "trasy"
def trasa(n):
    return json.loads((TRASY / f"{n}.json").read_text())

def pomija(poz, punkty):
    return mozg.DOJSCIE_POMIN_ODL > 0 and mozg.blisko_trasy(types.SimpleNamespace(pozycja=lambda: poz), punkty, mozg.DOJSCIE_POMIN_ODL)

edron = trasa("edron_trolle_petla")
dojscie = trasa("edron_depo_trolle")
sprawdz("5a na spocie (33094,31753,8) / w pętli: restart idzie w pętlę, bez dojścia z depo", pomija((33094, 31753, 8), edron))
w_petli = tuple(edron[len(edron) // 2])
sprawdz("5b w dowolnym punkcie pętli: bez dojścia", pomija(w_petli, edron))
start = tuple(dojscie[0])
sprawdz("5c w mieście przy depo bez zadania: dojście jak dotąd (pełne)", not pomija(start, edron))
# w połowie dojścia: start od najbliższego punktu trasy dojścia
srodek = tuple(dojscie[len(dojscie) // 2])
import trasa_io
uproszczone = [tuple(p) for p in trasa_io.uprosc_petle(dojscie)]
suf = [tuple(p) for p in mozg.dojscie_od_pozycji(dojscie, srodek)]
sprawdz("5d w połowie dojścia: dojście ruszy od najbliższego punktu (ogon trasy, krótszy niż od depo)",
        0 < len(suf) < len(uproszczone) and suf == uproszczone[len(uproszczone) - len(suf):]
        and max(abs(suf[0][0] - srodek[0]), abs(suf[0][1] - srodek[1])) <= 3, (len(suf), len(uproszczone), suf[:1], srodek))
pelne = [tuple(p) for p in mozg.dojscie_od_pozycji(dojscie, start)]
sprawdz("5e od depo (początek dojścia): cała trasa", len(pelne) == len(uproszczone), (len(pelne), len(uproszczone)))

# --- 6. integracja: mozg.main woła wznow_start przed dojściem (kontrola źródła) ---------------------------------
zrodlo = (Path(_R) / "mozg.py").read_text()
i_wz, i_doj = zrodlo.index("wznow_start.sprobuj"), zrodlo.index("przejdz_dojscie(")
sprawdz("6a mozg.main próbuje wznowić wyprawę PRZED dojściem", i_wz < zrodlo.rindex("przejdz_dojscie("), (i_wz, i_doj))
sprawdz("6b po wznowieniu dojście jest zerowane (a.dojscie = None) i pomijane jest sprawdzanie liny spotu",
        "a.dojscie = None" in zrodlo[i_wz:i_wz + 2500] and "not wznowiona" in zrodlo)

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
