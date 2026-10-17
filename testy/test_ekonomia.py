import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
"""Test dziennika ekonomii (SPEC_ekonomia_lootu_1017): linie lootu => rekord `lup` (gold, jedzenie, cenne),
przypisanie do potwora, gold:null, brak rotacji i sprzątania, bezpieczniki zapisu, raport.
Uruchom: python3 -I testy/test_ekonomia.py"""
import json
import os
import sys
import tempfile
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ekonomia, telemetria, loot

os.environ.pop("RETRONIC_TELEMETRIA", None)

ok = []
def sprawdz(opis, warunek, info=""):
    print(("OK    " if warunek else "BŁĄD "), opis, info if not warunek else "")
    ok.append(bool(warunek))

T = [1000.0]
zegar = lambda: T[0]

def czytaj(katalog):
    return [json.loads(l) for p in sorted(Path(katalog).glob("ekonomia-*.jsonl")) for l in p.read_text().splitlines()]

# --- ceny i cenne ---
ceny = ekonomia.ceny_npc()
drogi = max(ceny, key=ceny.get)
sprawdz("ceny NPC wczytane z przedmioty.json", len(ceny) > 100 and ceny[drogi] >= 100, drogi)
sprawdz("cenne: >= 100 gp tak, tani przedmiot nie",
        [x["n"] for x in ekonomia.cenne([drogi, "leather helmet", "gold coin"])] == [drogi])
sprawdz("cenne: rodzajnik 'a ' ignorowany", ekonomia.cena("a " + drogi) == ceny[drogi])
opis = ekonomia.cenne_opis(ekonomia.cenne([drogi, drogi]))
sprawdz("cenne_opis <-> parsuj_cenne", ekonomia.parsuj_cenne(opis)[0]["n"] == drogi and ekonomia.parsuj_cenne(opis)[0]["ile"] == 2, opis)

# --- lup ze zwłok: gold, jedzenie, cenne, przypisanie do potwora ---
tmp = Path(tempfile.mkdtemp())
t = telemetria.Telemetria(tmp, zegar=zegar, zapis=True)
T[0] = 1000; t.linia("Nowy cel: Goblin (100,100) HP 100%")
T[0] = 1008; t.linia("Cel Goblin zabity na (100, 100).")
T[0] = 1010
for l in ("loot: zebrano gold coin +7", "loot: zebrano gold coin +3", "loot: zebrano meat +1",
          "loot: zjedzono ze zwłok: fish", f"loot: cenne zostały {opis}", "loot: łup gold coin 10 (razem: ...)"):
    t.linia(l)
t.linia("Loot: ok")
r = [x for x in czytaj(tmp) if x["typ"] == "lup"]
sprawdz("jeden rekord lup", len(r) == 1, r)
if r:
    r = r[0]
    sprawdz("gold zsumowany 7+3", r["gold"] == 10, r)
    sprawdz("jedzenie osobno od reszty", r["jedzenie"] == {"meat": 1} and "meat" not in r["zebrano"], r)
    sprawdz("zjedzono ze zwłok zapisane", r["zjedzono"] == ["fish"], r)
    sprawdz("cenne niezebrane zapisane z ceną", r["cenne"] and r["cenne"][0]["n"] == drogi and r["cenne"][0]["cena"] >= 100, r)
    sprawdz("przypisane do ostatniego zabicia", r["n"] == "Goblin" and r["n_pewne"] is True and r["zrodlo"] == "zwloki", r)
sprawdz("akumulator wyczyszczony po rekordzie", t.lup.pusty())

# --- stare zabicie => n_pewne false; gold nieznany => null ---
T[0] = 1100
t.linia("loot: zebrano gold coin (ilość nieznana, plan z obrazka)")
t.linia("Loot: ok")
r2 = [x for x in czytaj(tmp) if x["typ"] == "lup"][-1]
sprawdz("gold:null gdy ilość nieznana", r2["gold"] is None, r2)
sprawdz("zabicie starsze niż 30 s => n_pewne false", r2["n"] == "Goblin" and r2["n_pewne"] is False, r2)

# --- loot w walce: koniec zamyka rekord ---
T[0] = 1200; t.linia("Cel Orc zabity na (1, 1).")
T[0] = 1202
t.linia("loot w walce: zebrano gold coin +12"); t.linia("loot w walce: łup gold coin 12 (razem: ...)"); t.linia("loot w walce: koniec")
r3 = [x for x in czytaj(tmp) if x["typ"] == "lup"][-1]
sprawdz("lup z walki: gold 12, zrodlo walka, potwór Orc", r3["gold"] == 12 and r3["zrodlo"] == "walka" and r3["n"] == "Orc", r3)

# --- zdarzenia: zabicie, exp, uh, jedzenie, tik ---
t.zdarzenie("exp_zabicie", n="Orc", exp=25.0, zab=2)
t.zdarzenie("uh_run", wynik="ok", powod="None", alarm=False, czas_s=3.5, rzuty=2, restore=False)
t.zdarzenie("jedzenie_walka", od_s=20)
typy = [x["typ"] for x in czytaj(tmp)]
sprawdz("zabicie/exp/uh/jedzenie trafiają do dziennika", all(k in typy for k in ("zabicie", "exp", "uh", "jedzenie")), typy)
sprawdz("rekord start przed pierwszym zapisem", typy[0] == "start")
t._zapisz({"t": 1300.0, "typ": "probka", "poz": [1, 2, 7], "stan": "IDZ", "hp": 90, "mana": 5, "max_mana": 20, "exp": 500})
tik = [x for x in czytaj(tmp) if x["typ"] == "tik"]
sprawdz("tik z próbki: razem gold/uh/zab", len(tik) == 1 and tik[0]["gold_razem"] == 22 and tik[0]["uh_razem"] == 2 and tik[0]["zab_razem"] == 2, tik)
t._zapisz({"t": 1310.0, "typ": "probka", "poz": [1, 2, 7], "stan": "IDZ"})
sprawdz("tik nie częściej niż co 60 s", len([x for x in czytaj(tmp) if x["typ"] == "tik"]) == 1)

# --- bezpieczniki zapisu ---
tmp2 = Path(tempfile.mkdtemp())
t2 = telemetria.Telemetria(tmp2, zegar=zegar, zapis=False)
t2.linia("loot: zebrano gold coin +5"); t2.linia("Loot: ok")
sprawdz("zapis=False: brak pliku ekonomii", not list(tmp2.glob("ekonomia-*")))
tmp3 = Path(tempfile.mkdtemp())
t3 = telemetria.Telemetria(tmp3, zegar=zegar, zapis=True)
t3.nazwa_postaci = "Ja"
t3.linia("loot: zebrano gold coin +5"); t3.linia("Loot: ok")
sprawdz("atrapa 'Ja': brak pliku ekonomii", not list(tmp3.glob("ekonomia-*")))

# --- brak rotacji i sprzątania ---
tmp4 = Path(tempfile.mkdtemp())
t4 = telemetria.Telemetria(tmp4, zegar=zegar, zapis=True, max_bajtow=50)
for i in range(30):
    t4.linia("loot: zebrano gold coin +1"); t4.linia("Loot: ok")
sprawdz("ekonomia nie rotuje się mimo małego max_bajtow", not list(tmp4.glob("ekonomia-*.1")) and len(czytaj(tmp4)) >= 30)
for d in range(1, 16):
    (tmp4 / f"ekonomia-2026010{d % 10}{d}.jsonl").write_text("{}\n")
przed = len(list(tmp4.glob("ekonomia-*")))
t4.sprzatnij_stare()
sprawdz("sprzatnij_stare nie rusza ekonomii", len(list(tmp4.glob("ekonomia-*"))) == przed)

# --- raport ---
rek = [{"t": 0, "typ": "tik", "sesja": 1, "pid": 1}] * 60 + [
    {"t": 1, "typ": "lup", "sesja": 1, "pid": 1, "gold": 100, "jedzenie": {"meat": 2}, "cenne": [{"n": "x", "ile": 1, "cena": 150.0}]},
    {"t": 2, "typ": "lup", "sesja": 1, "pid": 1, "gold": None, "jedzenie": {}, "cenne": []},
    {"t": 3, "typ": "uh", "sesja": 1, "pid": 1, "wynik": "ok", "rzuty": 2},
    {"t": 4, "typ": "uh", "sesja": 1, "pid": 1, "wynik": "przerwane"},
    {"t": 5, "typ": "zabicie", "sesja": 1, "pid": 1, "n": "Goblin"},
    {"t": 6, "typ": "exp", "sesja": 1, "pid": 1, "exp": 25.0}]
w = ekonomia.raport(rek)
sprawdz("raport: 60 tików = 1 h", len(w) == 1 and w[0]["godz"] == 1.0, w)
sprawdz("raport: gold/h, uh/h, exp/h, zab/h", w and w[0]["gold_h"] == 100 and w[0]["uh_h"] == 2.0 and w[0]["exp_h"] == 25 and w[0]["zab_h"] == 1, w)
sprawdz("raport: gold nieznany policzony osobno, cenne i jedzenie", w and w[0]["gold_nieznany_lupow"] == 1 and w[0]["cenne_gp"] == 150 and w[0]["jedzenie"] == {"meat": 2}, w)

# --- loot._log_cenne ---
linie = []
loot._log_cenne("loot", [drogi, "leather helmet"], linie.append)
sprawdz("loot._log_cenne loguje tylko cenne", len(linie) == 1 and linie[0].startswith("loot: cenne zostały " + drogi), linie)
linie.clear(); loot._log_cenne("loot", ["leather helmet"], linie.append)
sprawdz("loot._log_cenne milczy bez cennych", not linie)

print("WYNIK:", "OK" if all(ok) else "BŁĄD", f"({sum(ok)}/{len(ok)})")
sys.exit(0 if all(ok) else 1)
