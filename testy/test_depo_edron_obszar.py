"""24.10: pole dojścia do depo Edron losowane z OBSZARU hali (Karol: „punkt dojścia do depo w Edron trzeba zmienić na jakiś neutralny
na środku albo obręb, żeby za każdym razem w to samo miejsce nie przychodził, bo może być zajęte"). Pokrętło DEPO_EDRON_OBSZAR (0 = dawne
stanowisko (33173,31796,8)). Dane rzeczywiste: trasy/serwis_edron.json, edron_do_depo.json, prawdziwa mapa. Nic nie trafia do gry."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import json
import random
import sys
import tempfile
import types
from pathlib import Path

sys.dont_write_bytecode = True
_R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _R)
import mapa as _mapa
import panel
import pokretla
import wyprawa as W

TRASY = Path(_R) / "trasy"
TMP = Path(tempfile.mkdtemp())
ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


if not _mapa.PLIK_MAPY.is_file():
    print("brak pliku mapy, pomijam test obszaru depo Edron")
    sys.exit(0)

MAPA = _mapa.Mapa()
DANE = json.loads((TRASY / "serwis_edron.json").read_text())
POLA = [tuple(p) for p in DANE["depo_obszar"]]
SALA = tuple(DANE["depo_sala"])
STOISKA = {tuple(p) for p in DANE["depo_stoiska"]}
STARE = (33173, 31796, 8)
START = (33117, 31775, 8)

# 1. dane obszaru
sprawdz("1a obszar ma 16 pól, wszystkie różne, wszystkie w sali depo, to samo piętro",
        len(POLA) == 16 and len(set(POLA)) == 16 and all(W.w_sali(p, SALA) for p in POLA), f"{len(POLA)} {SALA}")
sprawdz("1b każde pole obszaru jest chodliwe na prawdziwej mapie (widziane, nie ściana, nie schody/dziura)",
        all(MAPA.przechodnie(*p) is True and MAPA.schody_lub_dziura(*p) is False for p in POLA),
        [p for p in POLA if not (MAPA.przechodnie(*p) is True and MAPA.schody_lub_dziura(*p) is False)])
sprawdz("1c obszar nie zawiera stanowisk przy skrzyniach depo", not (set(POLA) & STOISKA), set(POLA) & STOISKA)
sprawdz("1d obszar omija kolumny wejścia z korytarza (x 33166..33170) i wiersz y=31798 przed wnękami",
        all(not (33166 <= p[0] <= 33170) and p[1] != 31798 for p in POLA))
sprawdz("1e obszar jest po obu stronach wejścia (nie jedna wnęka)", any(p[0] < 33166 for p in POLA) and any(p[0] > 33170 for p in POLA))

# 2. panel: „w depo" dla każdego pola obszaru, każdego stanowiska i całej sali; poza salą jak dotąd
bledne = [p for p in POLA if panel.miasto_pozycji(p, dane={"edron": DANE}) != ("edron", True)]
sprawdz("2a panel.miasto_pozycji: każde pole obszaru = (edron, w_depo)", not bledne, bledne)
bledne = [p for p in STOISKA if panel.miasto_pozycji(p, dane={"edron": DANE}) != ("edron", True)]
sprawdz("2b panel: każde stanowisko przy skrzyni nadal w_depo", not bledne, bledne)
sala_pola = [(x, y, SALA[4]) for x in range(SALA[0], SALA[2] + 1) for y in range(SALA[1], SALA[3] + 1)]
bledne = [p for p in sala_pola if not panel.miasto_pozycji(p, dane={"edron": DANE})[1]]
sprawdz("2c panel: cała prostokątna sala depo = w_depo", not bledne, bledne[:5])
sprawdz("2d panel: korytarz poza salą (y=31804) i inne piętro nie są w_depo",
        not panel.miasto_pozycji((33168, 31804, 8), dane={"edron": DANE})[1] and not panel.miasto_pozycji((33168, 31800, 7), dane={"edron": DANE})[1])
d_bez = {k: v for k, v in DANE.items() if k != "depo_sala"}
sprawdz("2e panel bez klucza depo_sala: dawne zachowanie (<= 2 pola od stanowiska), środek hali nie jest w_depo",
        panel.miasto_pozycji((33168, 31800, 8), dane={"edron": d_bez})[1] is False
        and panel.miasto_pozycji((33173, 31797, 8), dane={"edron": d_bez})[1] is True)
d_zly = dict(DANE, depo_sala="zepsute")
sprawdz("2f panel ze zepsutym depo_sala: bez wyjątku, dawne zachowanie", panel.miasto_pozycji((33168, 31800, 8), dane={"edron": d_zly})[1] is False)

# 3. obszar_depo / wybierz_pole_obszaru
o = W.obszar_depo(TRASY, STARE)
sprawdz("3a obszar_depo dla stanowiska Edron zwraca pola i salę", o is not None and len(o[0]) == 16 and tuple(o[1]) == SALA, o)
sprawdz("3b obszar_depo dla celu, który nie jest stanowiskiem (Thais, dowolne pole): None",
        W.obszar_depo(TRASY, (32369, 32241, 7)) is None and W.obszar_depo(TRASY, (33168, 31800, 8)) is None)
kat = Path(tempfile.mkdtemp())
sprawdz("3c brak pliku serwis_edron.json: None, bez wyjątku", W.obszar_depo(kat, STARE) is None)
(kat / W.PLIK_SERWIS_EDRON).write_text("{nie json")
sprawdz("3d zepsuty JSON: None", W.obszar_depo(kat, STARE) is None)
(kat / W.PLIK_SERWIS_EDRON).write_text(json.dumps(dict(DANE, depo_obszar=[[33100, 31700, 8]])))
sprawdz("3e obszar poza salą (zepsute dane): None", W.obszar_depo(kat, STARE) is None)
(kat / W.PLIK_SERWIS_EDRON).write_text(json.dumps({k: v for k, v in DANE.items() if k != "depo_obszar"}))
sprawdz("3f brak klucza depo_obszar: None", W.obszar_depo(kat, STARE) is None)

zaj = {(p[0], p[1]) for p in POLA[:15]}
sprawdz("3g wybierz_pole_obszaru pomija zajęte: jedyne wolne pole", all(W.wybierz_pole_obszaru(POLA, zaj) == POLA[15] for _ in range(20)))
sprawdz("3h wszystkie zajęte: None", W.wybierz_pole_obszaru(POLA, {(p[0], p[1]) for p in POLA}) is None)
rng = random.Random(7)
wyb = {W.wybierz_pole_obszaru(POLA, (), rng) for _ in range(300)}
sprawdz("3i losowanie obejmuje cały obszar (300 losowań, 16 różnych pól)", wyb == set(POLA), len(wyb))


# 4. integracja: Wyprawa
class KonfW:
    WYPRAWA_AKTYWNA = 1
    WYPRAWA_MAX_CZAS_S = 1800
    WYPRAWA_MAX_KROKOW = 6000
    WYPRAWA_STOP_PRZY_UTKNIECIU = 1
    WYPRAWA_CO_MIN = 20
    WYPRAWA_PO_DEPO_S = 900
    WYPRAWA_DEPO_POWROT = 0
    WYPRAWA_TYLKO_DEPO = 1


class KonfStare(KonfW):
    DEPO_EDRON_OBSZAR = 0


class KonfNowe(KonfW):
    DEPO_EDRON_OBSZAR = 1


class CBW:
    mapa = MAPA

    def __init__(c, poz):
        c.t = 0.0
        c.wypad_aktywny = False
        c.poz = poz
        c.ostatnie_stwory = []
        c.kroki = []
        c.postac = types.SimpleNamespace(pozycja=lambda: c.poz)

    def zegar(c):
        return c.t

    def gracz(c):
        return {"proc": 60.0}

    def _wypad_reset_klik(c):
        pass

    def droga(c, *a, **k):
        return []

    def pauza(c, *a):
        pass

    def krok_do(c, cel):
        c.kroki.append(tuple(cel))
        c.poz = tuple(cel)


class OpsW:
    def wiadomosci(o):
        return []


def nowa(poz, konf, nr=[0]):
    nr[0] += 1
    cb = CBW(poz)
    logi = []
    w = W.Wyprawa(cb, OpsW(), konf=konf(), log=logi.append, plik_stanu=TMP / f"st{nr[0]}.json",
                  plik_sklepow=TMP / "sk.json", plik_npc=TMP / "npc.json", plik_stop=TMP / f"STOP{nr[0]}",
                  czas=lambda: 5_000_000.0)
    return w, cb, logi


dane = {"powody": ["glod"], "zapas": 0, "blanki": None, "zloto": 100, "cap": 100, "hp": 90, "pochodnie": None, "depo": True}


def cel_planu(w):
    legs = w.w["legs"][0]
    idz = [e for e in legs if e["typ"] == "IDZ"]
    return tuple(idz[-1]["punkty"][-1]), tuple(w.w["stops"][0]["stoi"])


konc = []
ok_start = True
for _ in range(40):
    w, cb, logi = nowa(START, KonfNowe)
    if w._start_wyprawa("depo:glod", dane, 0.0) is not True:
        ok_start = False
        break
    konc.append(cel_planu(w))
sprawdz("4a pokrętło 1: wyprawa do depo startuje, ostatni punkt trasy = stoi = pole obszaru (40 startów)",
        ok_start and konc and all(a == b and a in set(POLA) for a, b in konc), konc[:3])
sprawdz("4b pokrętło 1: pole dojścia jest losowane (40 startów dają >= 4 różne pola), nie stałe stanowisko",
        len({a for a, _ in konc}) >= 4, len({a for a, _ in konc}))
sprawdz("4c plan zapisuje obszar (16 pól) i log o wyborze pola", len(w.w["stops"][0].get("obszar") or ()) == 16
        and any("pole dojścia" in l for l in logi), logi[-3:])
w5, cb5, logi5 = nowa(START, KonfNowe)
w5._z_poz = None
wr, blad = w5._zbuduj("edron", {"depo": True})
sprawdz("4d restart w marszu: _wznow buduje plan od nowa (_zbuduj) i też kończy w polu obszaru (z nowym losowaniem)",
        wr is not None and len(wr["stops"][0].get("obszar") or ()) == 16 and tuple(wr["stops"][0]["stoi"]) in set(POLA), (blad, logi5[-2:]))

# zajęte pola: gracze na 12 z 16 pól -> nigdy nie wybiera zajętego
zajete = POLA[:6] + POLA[8:14]
konc = []
for _ in range(40):
    w, cb, logi = nowa(START, KonfNowe)
    cb.ostatnie_stwory = [{"x": p[0], "y": p[1], "z": p[2], "hp": 100} for p in zajete]
    w._start_wyprawa("depo:glod", dane, 0.0)
    konc.append(cel_planu(w)[0])
wolne = set(POLA) - set(zajete)
sprawdz("4e zajęte pola (gracze na 12 z 16) są omijane przy wyborze pola dojścia (40 startów)", all(k in wolne for k in konc), [k for k in konc if k not in wolne][:3])
w, cb, logi = nowa(START, KonfNowe)
cb.ostatnie_stwory = [{"x": p[0], "y": p[1], "z": p[2], "hp": 100} for p in POLA]
w._start_wyprawa("depo:glod", dane, 0.0)
sprawdz("4f wszystkie pola obszaru zajęte: dawne stanowisko (33173,31796,8) i log, bez wyjątku",
        cel_planu(w) == (STARE, STARE) and not w.w["stops"][0].get("obszar") and any("wszystkie pola obszaru zajęte" in l for l in logi), logi[-3:])

# pokrętło 0 = dawne zachowanie
w, cb, logi = nowa(START, KonfStare)
w._start_wyprawa("depo:glod", dane, 0.0)
sprawdz("4g pokrętło 0: cel = stare stanowisko (33173,31796,8), bez obszaru w stopie, bez logu o obszarze",
        cel_planu(w) == (STARE, STARE) and not w.w["stops"][0].get("obszar") and not any("pole dojścia" in l for l in logi), logi[-3:])

# domyślnie (konf bez pokrętła) = 1
w, cb, logi = nowa(START, KonfW)
w._start_wyprawa("depo:glod", dane, 0.0)
sprawdz("4h konf bez pokrętła: domyślnie obszar włączony (DOMYSLNE['DEPO_EDRON_OBSZAR'] = 1)",
        W.DOMYSLNE.get("DEPO_EDRON_OBSZAR") == 1 and cel_planu(w)[0] in set(POLA), cel_planu(w))

# 5. _cel_dokroku
w, cb, logi = nowa(START, KonfNowe)
w._start_wyprawa("depo:glod", dane, 0.0)
st = w.w["stops"][0]
sprawdz("5a stoimy na polu obszaru: nic nie dokładamy (None)", all(w._cel_dokroku(p, st) is None for p in POLA))
st_wolny = dict(st, stoi=POLA[0])
poz_hala = (33168, 31800, 8)
sprawdz("5b poza obszarem, stoi wolne: dokrok na stoi", w._cel_dokroku(poz_hala, st_wolny) == POLA[0])
cb.ostatnie_stwory = [{"x": POLA[0][0], "y": POLA[0][1], "z": 8, "hp": 100}]
c = w._cel_dokroku(poz_hala, st_wolny)
sprawdz("5c stoi zajęte: najbliższe wolne pole obszaru, nie zajęte", c in set(POLA) and c != POLA[0], c)
cb.ostatnie_stwory = [{"x": p[0], "y": p[1], "z": 8, "hp": 100} for p in POLA]
sprawdz("5d wszystkie pola zajęte: None (zostajemy w sali)", w._cel_dokroku(poz_hala, st_wolny) is None)
cb.ostatnie_stwory = []
st_stare = {"stoi": STARE}
sprawdz("5e stop bez obszaru (pokrętło 0, inne miasta): stoi jak dotąd", w._cel_dokroku((33172, 31797, 8), st_stare) == STARE)

# 6. przebieg _sklep: „depo osiągnięte" po wejściu w obszar, bez dokroków; zajęte pole = dokrok na inne
w, cb, logi = nowa(START, KonfNowe)
w._start_wyprawa("depo:glod", dane, 0.0)
cel = cel_planu(w)[0]
cb.poz = cel
w._sklep(cb.poz, 1.0)
plik = Path(w.plik_stop)
sprawdz("6a stoimy w polu obszaru: DEPO osiągnięte, STOP zapisany, żadnego dokroku",
        any("DEPO osiągnięte" in l for l in logi) and plik.is_file() and not cb.kroki, (logi[-4:], cb.kroki))

ok6 = True
inf = []
for p in POLA:
    w, cb, logi = nowa(START, KonfNowe)
    w._start_wyprawa("depo:glod", dane, 0.0)
    cb.poz = p
    w._sklep(p, 1.0)
    if not (any("DEPO osiągnięte" in l for l in logi) and not cb.kroki):
        ok6 = False
        inf.append((p, logi[-2:], cb.kroki))
sprawdz("6b dla KAŻDEGO pola obszaru: DEPO osiągnięte bez dokroków", ok6, inf[:2])

# etap skończył tolerancją 3 pola od pola docelowego (poza obszarem), pole docelowe zajęte -> dokrok na inne wolne pole obszaru
w, cb, logi = nowa(START, KonfNowe)
w._start_wyprawa("depo:glod", dane, 0.0)
w.w["stops"][0]["stoi"] = list(POLA[8])               # (33162,31800,8)
cb.ostatnie_stwory = [{"x": POLA[8][0], "y": POLA[8][1], "z": 8, "hp": 100}]
cb.poz = (33168, 31800, 8)
w._sklep(cb.poz, 1.0)
sprawdz("6c pole docelowe zajęte, stoimy w sali 3 pola od obszaru: dokrok na inne WOLNE pole obszaru",
        len(cb.kroki) == 1 and cb.kroki[0] in set(POLA) and cb.kroki[0] != POLA[8], cb.kroki)
w._sklep(cb.poz, 2.0)
sprawdz("6d po dokroku (jesteśmy w obszarze): DEPO osiągnięte", any("DEPO osiągnięte" in l for l in logi), logi[-3:])

# pokrętło 0: jak dotąd, dokrok tylko z 1 pola od stanowiska
w, cb, logi = nowa(START, KonfStare)
w._start_wyprawa("depo:glod", dane, 0.0)
cb.poz = (33172, 31797, 8)
w._sklep(cb.poz, 1.0)
sprawdz("6e pokrętło 0: dokrok na stare stanowisko z 1 pola, jak dotąd", cb.kroki == [STARE], cb.kroki)
w, cb, logi = nowa(START, KonfStare)
w._start_wyprawa("depo:glod", dane, 0.0)
cb.poz = (33168, 31800, 8)
w._sklep(cb.poz, 1.0)
sprawdz("6f pokrętło 0: z 5 pól od stanowiska bez dokroku (zasięg 1 jak dotąd)", cb.kroki == [], cb.kroki)

# 7. start_pk('powrot') z pola obszaru (po ucieczce przed PK): trasa nagrana depo -> łowisko jak dotąd
w, cb, logi = nowa(START, KonfNowe)
w._start_wyprawa("depo:glod", dane, 0.0)
cb.poz = cel_planu(w)[0]
w._zakoncz_depo("depo", "ok")
w2, cb2, logi2 = nowa(cb.poz, KonfNowe)
sprawdz("7a start_pk('powrot') z pola obszaru zaczyna powrót na łowisko (cel (33117,31775,8))",
        w2.start_pk("powrot", 10.0, baza="edron") and tuple(w2.w["stops"][0]["stoi"]) == START, logi2[-3:])

# 8. pokrętło w Pokretla / przykładowy plik
sprawdz("8a ZAKRESY/KIERUNEK znają DEPO_EDRON_OBSZAR", pokretla.ZAKRESY.get("DEPO_EDRON_OBSZAR") == (0, 1)
        and "DEPO_EDRON_OBSZAR" in pokretla.KIERUNEK)
przyklad = json.loads((Path(_R) / "na_zywo.przyklad.json").read_text())
sprawdz("8b na_zywo.przyklad.json ma DEPO_EDRON_OBSZAR = 1", przyklad.get("DEPO_EDRON_OBSZAR") == 1, przyklad.get("DEPO_EDRON_OBSZAR"))
mod = types.SimpleNamespace()
logp = []
pk = pokretla.Pokretla(mod, plik=TMP / "na_zywo.json", log=logp.append)
sprawdz("8c Pokretla wstrzykuje domyślne DEPO_EDRON_OBSZAR = 1 do modułu bez tej stałej (cavebot.py jej nie ma)",
        getattr(mod, "DEPO_EDRON_OBSZAR", None) == 1 and pk.domyslne.get("DEPO_EDRON_OBSZAR") == 1, (getattr(mod, "DEPO_EDRON_OBSZAR", None), pk.domyslne))
pk.zastosuj({"DEPO_EDRON_OBSZAR": 0})
sprawdz("8d na_zywo.json DEPO_EDRON_OBSZAR=0 przełącza moduł na dawne zachowanie (Wyprawa czyta getattr(konf))", mod.DEPO_EDRON_OBSZAR == 0, logp[-2:])
w, cb, logi = nowa(START, lambda: mod)
sprawdz("8e Wyprawa z konfem = ten moduł widzi 0", int(w._kw("DEPO_EDRON_OBSZAR")) == 0)
pk.zastosuj({})
sprawdz("8f usunięcie klucza z na_zywo.json = powrót do domyślnej 1", mod.DEPO_EDRON_OBSZAR == 1, logp[-2:])
ok_w, bledy = pokretla.waliduj({"DEPO_EDRON_OBSZAR": 2})
sprawdz("8g wartość poza zakresem (2) odrzucona", "DEPO_EDRON_OBSZAR" not in ok_w and bledy, bledy)
ok_w, bledy = pokretla.waliduj({"DEPO_EDRON_OBSZAR": 0}, {"DEPO_EDRON_OBSZAR": 1})
sprawdz("8h analityk (waliduj z domyślnymi) nie obniży pokrętła do 0: kierunek nie_nizej", "DEPO_EDRON_OBSZAR" not in ok_w and bledy, (ok_w, bledy))

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
