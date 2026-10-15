"""Wypad: oscylacja 1 pole w tę i z powrotem nie może ukrywać braku postępu (utknięcie w ETAP_UTK_S), a etap, którego
koniec jest nieosiągalny z miejsca postaci (inna drabina, pokój bez wyjścia: "There is no way"), przesiada się na
najbliższy osiągalny punkt planu. Incydent 15.10 20:29 (wypad troll -> depo, etap 16/19). Atrapy, nic nie trafia do gry."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, types
sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import wypad

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK  " if warunek else "FAIL"), nazwa, info)

KROK_S = 5.2        # jeden obieg wypadu (krok + czekanie na klienta) trwa dłużej niż próg luki 5.0 s


class CB:
    """Atrapa Cavebota: zegar sterowany, _idz_odcinek oscyluje o 1 pole (jak w grze: "There is no way")."""
    def __init__(s, poz, osiagalne=lambda xy: True, oscyluj=True):
        s.t = 0.0; s.poz = list(poz); s.osiagalne = osiagalne; s.oscyluj = oscyluj
        s.sciany = set(); s.zablokowane = set(); s.wypad_aktywny = True; s.i = 0
    def zegar(s): return s.t
    def pauza(s, a, b): s.t += a
    def ustaw_stan(s, *a): pass
    def _wypad_reset_klik(s): pass
    def postac_poz(s): return tuple(s.poz)
    @property
    def postac(s): return types.SimpleNamespace(pozycja=lambda: tuple(s.poz))
    def droga(s, start, cel, zajete=(), dlugosc=1, skosy=True):
        return [(cel[0], cel[1], start[2])] if s.osiagalne((cel[0], cel[1])) else None
    def _idz_odcinek(s, pkt, idx):
        s.t += KROK_S
        if s.oscyluj:
            s.i += 1
            s.poz[1] += 1 if s.i % 2 else -1
        return True, idx


def wypad_z(cb, etapy, ei):
    logi = []
    w = wypad.Wypad(cb, types.SimpleNamespace(), log=logi.append, plan=(etapy, etapy))
    w.logi = logi
    w.stan = "WYPAD"; w.faza = "do"; w.etapy = etapy; w.ei = ei; w.pi = 0
    w.t_start = 0.0; w.ost_obieg = cb.t
    return w


def krok(cb, w):
    w._obieg(cb.zegar())


def uruchom(cb, w, do_s, stop_gdy=None):
    while cb.t < do_s:
        krok(cb, w)
        if stop_gdy and stop_gdy():
            break


def n_utk(w):
    return sum("błąd utkniecie" in l for l in w.logi)


# --- 1. oscylacja: utknięcie odpala się w ETAP_UTK_S mimo kroków w tę i z powrotem -----------------
z = 8
et = [{"typ": "IDZ", "punkty": [(32496, 32266, z), (32493, 32260, z)]},
      {"typ": "LINA", "stoi": (32493, 32260, z), "cel": (32493, 32259, z), "ladunek": (32493, 32260, 7)},
      {"typ": "IDZ", "punkty": [(32493, 32260, 7), (32400, 32224, 7)]}]
cb = CB((32496, 32266, z))
w = wypad_z(cb, et, 0)
uruchom(cb, w, 2 * wypad.ETAP_UTK_S + 40, stop_gdy=lambda: n_utk(w) >= 1)
sprawdz("1a oscylacja 1 pole: utknięcie odpala", n_utk(w) >= 1, f"t={cb.t:.1f}")
sprawdz("1b ... w ETAP_UTK_S (+ jeden obieg)", cb.t <= wypad.ETAP_UTK_S + 2 * KROK_S, f"t={cb.t:.1f}")
sprawdz("1c ... a nie na początku (to nie fałszywy alarm)", cb.t > wypad.ETAP_UTK_S, f"t={cb.t:.1f}")

# 1d. prawdziwa luka (walka > 5 s między obiegami) nadal zeruje postęp
cb = CB((32496, 32266, z)); w = wypad_z(cb, et, 0)
for _ in range(8):
    krok(cb, w)
t0 = w.postep[0]
cb.t += 20.0                           # walka / loot
krok(cb, w)
sprawdz("1d luka > 5 s między obiegami zeruje postęp (nowy odczyt)", w.postep is not None and w.postep[0] > t0, w.postep)

# --- 2. koniec etapu nieosiągalny, ale późniejszy etap ma osiągalny punkt -> przesiadka --------------
# plan jak w incydencie: postać stoi w kieszeni na z8 (inna drabina), koniec etapu 2 (z8) za ścianą
et2 = [{"typ": "IDZ", "punkty": [(5, 10, z), (8, 10, z)]},                                   # 0 (wcześniejszy)
       {"typ": "DZIURA", "stoi": (8, 10, z), "dziura": (8, 11, z), "ladunek": (8, 11, 9), "pewna": True},
       {"typ": "IDZ", "punkty": [(50, 50, z), (60, 50, z)]},                                 # 2 bieżący, nieosiągalny
       {"typ": "LINA", "stoi": (60, 50, z), "cel": (60, 49, z), "ladunek": (60, 50, 7)},
       {"typ": "IDZ", "punkty": [(60, 50, 7), (70, 50, 7)]},
       {"typ": "DZIURA", "stoi": (70, 50, 7), "dziura": (70, 51, 7), "ladunek": (70, 51, z), "pewna": True},
       {"typ": "IDZ", "punkty": [(12, 10, z), (20, 10, z)]}]                                 # 6 (późniejszy), osiągalny
KIESZEN = lambda xy: abs(xy[0] - 10) <= 12 and abs(xy[1] - 10) <= 3      # x 0..22, y 7..13
cb = CB((10, 10, z), osiagalne=KIESZEN); w = wypad_z(cb, et2, 2)
uruchom(cb, w, 2 * wypad.ETAP_NIEOSIAG_S + 20, stop_gdy=lambda: w.ei != 2)
sprawdz("2a nieosiągalny koniec etapu: resync na osiągalny punkt PÓŹNIEJSZEGO etapu", w.ei == 6, f"ei={w.ei} pi={w.pi}")
sprawdz("2b ... bez utknięcia, szybciej niż ETAP_UTK_S", n_utk(w) == 0 and cb.t < wypad.ETAP_UTK_S, f"t={cb.t:.1f}")

# 2c. tylko wcześniejszy etap ma osiągalny punkt
KIESZEN2 = lambda xy: abs(xy[0] - 6) <= 5 and abs(xy[1] - 10) <= 3
cb = CB((6, 10, z), osiagalne=KIESZEN2); w = wypad_z(cb, et2, 2)
uruchom(cb, w, 2 * wypad.ETAP_NIEOSIAG_S + 20, stop_gdy=lambda: w.ei != 2)
sprawdz("2c tylko wcześniejszy etap osiągalny: resync na niego", w.ei == 0, f"ei={w.ei} pi={w.pi}")

# 2d. koniec etapu osiągalny (tylko oscylacja): bez przesiadki, za to utknięcie
cb = CB((10, 10, z), osiagalne=lambda xy: True); w = wypad_z(cb, et2, 2)
uruchom(cb, w, wypad.ETAP_UTK_S + 20, stop_gdy=lambda: n_utk(w) >= 1)
sprawdz("2d osiągalny koniec etapu: zostajemy w etapie, utknięcie odpala", w.ei == 2 and n_utk(w) >= 1, f"ei={w.ei} t={cb.t:.1f}")

# 2e. nic osiągalnego na tym piętrze: utknięcie liczone szybko (3x -> awaria), nie 3 x 60 s
cb = CB((10, 10, z), osiagalne=lambda xy: xy == (10, 10)); w = wypad_z(cb, et2, 2)
uruchom(cb, w, 200, stop_gdy=lambda: w.faza != "do")
sprawdz("2e brak osiągalnych punktów: utknięcie -> awaria przed 3 x ETAP_UTK_S", w.faza != "do" and cb.t < 3 * wypad.ETAP_UTK_S,
        f"faza={w.faza} t={cb.t:.1f} utk={n_utk(w)}")

print("WYNIK", sum(ok), "/", len(ok)); sys.exit(0 if all(ok) else 1)
