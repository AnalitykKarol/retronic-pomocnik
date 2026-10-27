"""Serwis Port Hope (25.10): TERAZ tylko krok DEPO (+ wyjście). Dane z generatora (generuj_serwis_port_hope.py), pełny serwis na atrapie świata,
rozpoznanie miasta (panel, refill_auto, serwis.wybierz_miasto), plan NPC (bank/backpack/blanki/ham) tylko jako opis "do pomiaru".
Offline: RETRONIC_TESTY=1, żadnego inputu do gry, żadnych procesów (poza generatorem z --sprawdz i `serwis.py --help`).
NIEZWERYFIKOWANE NA ŻYWO: położenie skrzyń depo i strona skrzyni, pola stania przy NPC, schody z6->z5, dialogi."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
_os.environ["RETRONIC_ID"] = "tstph"
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
KAT = Path(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
sys.path.insert(0, str(KAT))
import generuj_powrot_port_hope as GP
import generuj_serwis_port_hope as G
import mapa as _mapa
import panel
import refill_auto
import serwis as S
import wyprawa
from serwis_blad import SerwisBlad

ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


def zglasza(f):
    try:
        f()
    except SerwisBlad as e:
        return e
    return None


PLIK = KAT / "trasy" / "serwis_port_hope.json"
META = KAT / "trasy" / "serwis_port_hope.meta"
SKLEPY = KAT / "dane_tibia" / "SKLEPY_port_hope.md"
if not _mapa.PLIK_MAPY.is_file() or not PLIK.is_file():
    print("SKIP: brak mapy albo danych")
    sys.exit(0)
DANE = json.loads(PLIK.read_text())
MP = _mapa.mapa()
DEPO = tuple(GP.DEPO)

# --- 1. generator ---------------------------------------------------------------------------------------------------------

d1 = G.zbuduj(MP)
sprawdz("1a generator deterministyczny", G.tekst(d1) == G.tekst(G.zbuduj(MP)))
sprawdz("1b plik trasy/serwis_port_hope.json = wynik generatora", PLIK.read_text() == G.tekst(d1))
sprawdz("1c plik .meta = wynik generatora", META.read_text() == G.tekst(G.meta(d1, MP)))
r = subprocess.run([sys.executable, "-I", str(KAT / "generuj_serwis_port_hope.py"), "--sprawdz"], capture_output=True, text=True, timeout=120)
sprawdz("1d CLI --sprawdz: kod 0", r.returncode == 0 and "zgodne" in r.stdout, r.stdout + r.stderr)
with tempfile.TemporaryDirectory(prefix="ph_serwis_") as tmp:
    obce = Path(tmp) / "inne.json"
    obce.write_text("{}\n")
    r2 = subprocess.run([sys.executable, "-I", str(KAT / "generuj_serwis_port_hope.py"), "--sprawdz", "--wyjscie", str(obce), "--meta", str(META)],
                        capture_output=True, text=True, timeout=120)
sprawdz("1e CLI --sprawdz przy rozjeździe: kod 1", r2.returncode == 1 and "ROZJAZD" in r2.stdout, r2.stdout + r2.stderr)
meta = json.loads(META.read_text())
sprawdz("1f .meta: 'specjalne' puste, źródła, niezmierzone (skrzynie depo, plan NPC), kroki tylko depo",
        meta["specjalne"] == [] and "zrodla" in meta and any("skrzy" in x for x in meta["niezmierzone_na_zywo"])
        and any("Ferks" in x and "Clyde" in x for x in meta["niezmierzone_na_zywo"]) and meta["kroki"] == {"depo": False}, meta["kroki"])

# --- 2. dane: tylko depo ---------------------------------------------------------------------------------------------------

P = DANE["przystanki"]
sprawdz("2a miasto = port_hope (nazwa pliku serwis_port_hope.json = klucz miasta, jak edron/thais/abdendriel)", DANE["miasto"] == "port_hope" == PLIK.stem[len("serwis_"):])
sprawdz("2b kolejność = depo + wyjście, przystanki = tylko depo", DANE["kolejnosc"] == ["depo", "wyjscie"] and list(P) == ["depo"], (DANE["kolejnosc"], list(P)))
NIE_KROKI = ("bank", "backpack", "blanki", "jedzenie", "ham")
sprawdz("2c bank/backpack/blanki/jedzenie/ham NIE są w kolejności ani w przystankach", not any(k in DANE["kolejnosc"] or k in P for k in NIE_KROKI))
sprawdz("2d depo.stoi = GP.DEPO (32632,32743,z7), chodliwe; wyjście = depo (jedno źródło z trasami powrotu)",
        tuple(P["depo"]["stoi"]) == DEPO == (32632, 32743, 7) and tuple(DANE["wyjscie"]) == DEPO and G.chodliwe(MP, DEPO))
ST = [tuple(s) for s in DANE["depo_stoiska"]]
SKRZ = set(G.skrzynie_depo(MP))
sprawdz("2e kafle skrzyń z mapy: 6 w sali (2 kolumny x 3), wszystkie nieprzechodnie", len(SKRZ) == 6 and not any(G.chodliwe(MP, s) for s in SKRZ), sorted(SKRZ))
sprawdz("2f stanowiska: niepuste, chodliwe, bez powtórzeń, w sali depo, każde z kaflem skrzyni na N/E/S/W",
        ST and len(set(ST)) == len(ST) and all(G.chodliwe(MP, s) for s in ST)
        and all(DANE["depo_sala"][0] <= s[0] <= DANE["depo_sala"][2] and DANE["depo_sala"][1] <= s[1] <= DANE["depo_sala"][3] and s[2] == DANE["depo_sala"][4] for s in ST)
        and all(any((s[0] + dx, s[1] + dy, s[2]) in SKRZ for dx, dy in G.SASIEDZI) for s in ST), ST[:4])
sprawdz("2g pierwsze stanowisko leży najbliżej DEPO (<= 1 pole), pole DEPO leży w sali depo",
        max(abs(ST[0][0] - DEPO[0]), abs(ST[0][1] - DEPO[1])) <= 1
        and DANE["depo_sala"][0] <= DEPO[0] <= DANE["depo_sala"][2] and DANE["depo_sala"][1] <= DEPO[1] <= DANE["depo_sala"][3], ST[0])
sprawdz("2h bez drzwi i łączników (serwis Port Hope = jedno piętro): drzwi_miasta == [], klucze_drzwi == {}, laczniki == []",
        S.drzwi_miasta(DANE) == [] and S.klucze_drzwi(DANE) == {} and DANE["laczniki"] == [])

# --- 3. plan NPC: opis zgodny z SKLEPY_port_hope.md, poza wykonaniem ---------------------------------------------------------

PL_NPC = DANE["plan_do_pomiaru"]
tekst_md = SKLEPY.read_text()
wiersze = {}
for w in tekst_md.splitlines():
    kom = [c.strip() for c in w.strip().strip("|").split("|")]
    m = re.match(r"\*\*(\w+)\*\*", kom[1]) if len(kom) >= 5 and w.startswith("|") else None
    if m:
        poz = re.search(r"\((\d+),\s*(\d+),\s*z(\d+)\)", kom[2])
        cena = re.search(r"(\d+) gp", kom[3])
        wiersze[m.group(1)] = (tuple(int(v) for v in poz.groups()) if poz else None, int(cena.group(1)) if cena else None)
sprawdz("3a SKLEPY_port_hope.md ma wiersze Ferks, Perod, Tandros, Clyde z pozycją", {"Ferks", "Perod", "Tandros", "Clyde"} <= set(wiersze) and all(wiersze[n][0] for n in ("Ferks", "Perod", "Tandros", "Clyde")), wiersze)
sprawdz("3b pozycje NPC w planie = tabela w md: Ferks (32634,32739,z6), Perod (32634,32740,z5), Tandros (32622,32740,z5), Clyde (32574,32753,z7)",
        {k: (v["npc"], tuple(v["npc_poz"])) for k, v in PL_NPC["npc"].items()}
        == {"bank": ("Ferks", (32634, 32739, 6)), "backpack": ("Perod", (32634, 32740, 5)), "blanki": ("Tandros", (32622, 32740, 5)), "ham": ("Clyde", (32574, 32753, 7))}
        and all(tuple(v["npc_poz"]) == wiersze[v["npc"]][0] for v in PL_NPC["npc"].values()), PL_NPC["npc"])
sprawdz("3c ceny w planie = tabela w md: backpack 20, blank rune 10, ham 8, bank bez ceny",
        [PL_NPC["npc"][k]["cena"] for k in ("backpack", "blanki", "ham", "bank")] == [20, 10, 8, None]
        and [wiersze[n][1] for n in ("Perod", "Tandros", "Clyde")] == [20, 10, 8], (PL_NPC["npc"], wiersze))
dok = PL_NPC["kolejnosc_docelowa"]
sprawdz("3d kolejność docelowa: depo, schody, Ferks, schody z6->z5, Tandros, Perod, depo, Clyde",
        [any(s in x for x in dok[i:i + 1]) for i, s in enumerate(("depo", "schody z7", "Ferks", "schody z6", "Tandros", "Perod", "depo", "Clyde"))] == [True] * 8 and len(dok) == 8, dok)
sprawdz("3e plan opisany jako DO POMIARU, schody z7->z6 (32629,32749) i lista rzeczy do zmierzenia (pola stania, schody z6->z5, dialogi)",
        PL_NPC["status"] == "DO POMIARU" and tuple(PL_NPC["schody_z7_z6"]) == (32629, 32749)
        and any("pola stania" in x for x in DANE["do_pomiaru"]["reszta_refilu"]) and any("schody z6 -> z5" in x for x in DANE["do_pomiaru"]["reszta_refilu"])
        and any("dialog" in x for x in DANE["do_pomiaru"]["reszta_refilu"]))
sprawdz("3f żaden NPC z planu nie trafił do przystanków ani kolejności (serwis nie wykona planu): Ferks/Perod/Tandros/Clyde tylko w plan_do_pomiaru",
        not any(n in json.dumps(P) + json.dumps(DANE["kolejnosc"]) for n in ("Ferks", "Perod", "Tandros", "Clyde")))
sprawdz("3g schody z7 (32629,32749) to schody w mapie klienta (flaga 'bez drogi')", bool(MP.schody_lub_dziura(32629, 32749, 7)))
sprawdz("3h md: sekcja 'Stan implementacji' mówi, że działa tylko depo", "Stan implementacji" in tekst_md and "generuj_serwis_port_hope.py" in tekst_md)

# --- 4. serwis na atrapie świata -----------------------------------------------------------------------------------------------

S._czekaj_koniec_kroku = lambda: None
S._po_kroku = lambda *a, **k: None
PLN = S.Planer(wyprawa.Trasownik(MP), DANE["laczniki"], drzwi=S.drzwi_miasta(DANE), mapa=MP, klucze=S.klucze_drzwi(DANE))
droga_st = PLN.droga(DEPO, ST[0])
sprawdz("4a planer: droga z DEPO do pierwszego stanowiska i z powrotem istnieje i jest krótka", droga_st is not None and len(droga_st) <= 6 and PLN.droga(ST[0], DEPO) is not None, droga_st)
sprawdz("4b planer: każde stanowisko osiągalne z DEPO", all(PLN.droga(DEPO, s) is not None for s in ST), [s for s in ST if PLN.droga(DEPO, s) is None])


class Swiat:
    def __init__(self, poz):
        self.poz, self.odcinki = poz, []

    def chodz(self, punkty, tol=0):
        self.odcinki.append((tuple(punkty[0]), tuple(punkty[-1])))
        self.poz = tuple(punkty[-1])
        return True


class AkcjeAtrapa:
    def __init__(self, sw):
        self.log, self.sw = [], sw

    def sprawdz_start(self):
        self.log.append("start")

    def przygotuj_okna(self):
        self.log.append("okna")

    def majatek(self, tylko_glowny=False):
        return 1000

    def wolne_w_bagu(self):
        return 20

    def brakuje(self, co, cel):
        return {"ham": cel, "blank rune": cel, "backpack": 1}[co]

    def bank_zmien(self, npc):
        self.log.append(("bank", npc))

    def pole_zajete(self, pole):
        return False

    def depo_zloz(self, zostaw_platinum, odejdz=None):
        self.log.append(("depo", tuple(self.sw.poz), zostaw_platinum))
        return True

    def kup(self, npc, co, ile, prefiks=""):
        self.log.append(("kup", npc, co, ile))

    def rezerwa_na_blanki(self, blanki):
        return 0.0

    def cel_ham(self, cel, rezerwa_oz):
        return cel

    def potrzeba_baga(self):
        return True

    def przenies_blanki(self):
        self.log.append("przenies_blanki")


def serwis_atrapa():
    sw = Swiat(DEPO)
    a = AkcjeAtrapa(sw)
    return S.Serwis(DANE, a, PLN, lambda: sw.poz, sw.chodz, log=lambda *_: None, spij=lambda _s: None), a, sw


sr, a, sw = serwis_atrapa()
e = zglasza(lambda: sr.uruchom())
depo_log = [x for x in a.log if isinstance(x, tuple) and x[0] == "depo"]
sprawdz("4c serwis w domyślnej kolejności: depo u skrzyni z listy stanowisk (najbliższym wg drogi: serwis wybiera po koszcie, nie z góry listy) i wyjście, bez błędu, zero zakupów i banku",
        e is None and sr.wynik == {"depo": "ok", "wyjscie": "ok"} and len(depo_log) == 1 and depo_log[0][1] in ST and depo_log[0][1] != DEPO
        and max(abs(depo_log[0][1][0] - DEPO[0]), abs(depo_log[0][1][1] - DEPO[1])) <= 1 and depo_log[0][2] == 3
        and not any(isinstance(x, tuple) and x[0] in ("kup", "bank") for x in a.log), (e, sr.wynik, a.log))
sprawdz("4d wyjście = DEPO (marsz kończy w polu DEPO)", tuple(sw.poz[:2]) == DEPO[:2] and sw.poz[2] == DEPO[2], sw.poz)
sr, a, sw = serwis_atrapa()
e = zglasza(lambda: sr.uruchom(["bank", "depo", "jedzenie", "backpack", "blanki", "wyjscie"], pomin_brakujace=True))
sprawdz("4e refill.sh (pełna lista kroków + pomin_brakujace): bank/jedzenie/backpack/blanki pominięte jako brakujące (nie błąd), depo i wyjście ok, zero zakupów",
        e is None and sr.wynik == {"depo": "ok", "wyjscie": "ok"} and sr.kroki_przebiegu == ["depo", "wyjscie"]
        and not any(isinstance(x, tuple) and x[0] in ("kup", "bank") for x in a.log), (e, sr.wynik, a.log))
sr, a, sw = serwis_atrapa()
e = zglasza(lambda: sr.uruchom(["bank", "depo", "backpack", "blanki", "wyjscie"]))
sprawdz("4f bez pomin_brakujace brak banku/backpacka/blanków to czytelny błąd startu, zero ruchu i inputu",
        e and e.krok == "start" and "bank" in e.powod and a.log == [] and sw.odcinki == [], (e, a.log))
sr, a, sw = serwis_atrapa()
plan = sr.plan(["depo", "wyjscie"])
sprawdz("4g plan na sucho: depo -> pierwsze stanowisko, wyjście = DEPO, drogi istnieją", [p[0] for p in plan] == ["depo", "wyjscie"] and all(p[2] is not None for p in plan) and plan[0][1] == ST[0] and plan[1][1] == DEPO, plan)

# --- 5. wybór miasta, panel, refill_auto, CLI ----------------------------------------------------------------------------------

sprawdz("5a serwis.miasta() zna port_hope; wybierz_miasto('port_hope'), 'auto' z depo i bez argumentu z depo",
        "port_hope" in S.miasta() and S.wybierz_miasto("port_hope") == "port_hope" and S.wybierz_miasto("auto", DEPO) == "port_hope" and S.wybierz_miasto(None, DEPO) == "port_hope", S.miasta())
DS = panel.dane_serwisu()
ULICA = (32632, 32751, 7)
SWAMP, RATY_Z8, RATY_LAD = GP.SWAMP_WEJSCIE, GP.STOI, GP.LAD
sprawdz("5b panel: DEPO i stanowiska = (port_hope, przy depo); ulica przed depo = miasto, nie depo",
        panel.miasto_pozycji(DEPO, DS) == ("port_hope", True) and all(panel.miasto_pozycji(s, DS) == ("port_hope", True) for s in ST)
        and panel.miasto_pozycji(ULICA, DS) == ("port_hope", False), [panel.miasto_pozycji(p, DS) for p in (DEPO, ST[-1], ULICA)])
sprawdz("5c panel: piętra budynku depo z5..z7 nad depo = miasto, bez depo; z8 pod depo nie",
        panel.miasto_pozycji((32634, 32740, 6), DS) == ("port_hope", False) and panel.miasto_pozycji((32633, 32741, 5), DS) == ("port_hope", False)
        and panel.miasto_pozycji((32632, 32743, 8), DS) == (None, False))
sprawdz("5d panel: wejście do jaskini swamp (z7), jaskinia ratów (z8) i lądowanie z liny (z7) NIE są miastem",
        all(panel.miasto_pozycji(p, DS) == (None, False) for p in (SWAMP, RATY_Z8, RATY_LAD, (32662, 32741, 7))), [panel.miasto_pozycji(p, DS) for p in (SWAMP, RATY_Z8, RATY_LAD)])
sprawdz("5e inne miasta bez zmian: depo Edron, przybycie Thais, depo Ab'Dendriel",
        panel.miasto_pozycji(tuple(S.wczytaj("edron")["przystanki"]["depo"]["stoi"]), DS) == ("edron", True)
        and panel.miasto_pozycji(tuple(S.wczytaj("thais")["wyjscie"]), DS) == ("thais", True)
        and panel.miasto_pozycji(tuple(S.wczytaj("abdendriel")["przystanki"]["depo"]["stoi"]), DS) == ("abdendriel", True))
sprawdz("5f refill_auto zna Port Hope: depo = (port_hope, przy depo), swamp i raty = (None, False)",
        "port_hope" in refill_auto.MIASTA_SERWISU and refill_auto.miasto_serwisu(DEPO) == ("port_hope", True)
        and refill_auto.miasto_serwisu(SWAMP) == (None, False) and refill_auto.miasto_serwisu(RATY_Z8) == (None, False))
tmp = tempfile.mkdtemp(prefix="ph_serwis_")
wywolania = []
st1 = refill_auto.zlec(DEPO, tmp, start=lambda: wywolania.append(1), procesy=lambda *a, **k: [])
sprawdz("5g zlec: stop w depo Port Hope = czeka i startuje czekacza (atrapa) raz", st1[0] == "czeka" and "port_hope" in st1[1] and wywolania == [1], st1)
tmp2 = tempfile.mkdtemp(prefix="ph_serwis_")
st2 = refill_auto.zlec(SWAMP, tmp2, start=lambda: wywolania.append(2), procesy=lambda *a, **k: [])
sprawdz("5h zlec: stop przy wejściu do swamp = brak_planu, bez startu", st2[0] == "brak_planu" and 2 not in wywolania, st2)
tmp3 = tempfile.mkdtemp(prefix="ph_serwis_")
st3 = refill_auto.zlec(ULICA, tmp3, start=lambda: wywolania.append(3), procesy=lambda *a, **k: [])
sprawdz("5i zlec: stop na ulicy przed depo (miasto, nie przy depo) = pominięty, bez startu", st3[0] == "pominiety" and "nie stoi przy depo" in st3[1] and 3 not in wywolania, st3)
r = subprocess.run([sys.executable, "-I", str(KAT / "serwis.py"), "--help"], capture_output=True, text=True, timeout=60)
sprawdz("5j serwis.py --help: wśród miast port_hope", r.returncode == 0 and "port_hope" in r.stdout, r.stdout[-300:] + r.stderr[-300:])

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
