"""Szablon ustawień „nowa postać” (szablony/nowa_postac/) + nowa_instancja.sh (bez X11, bez startu bota/gry).

  python3 testy/test_szablon_nowa_postac.py [skrypt_nowa_instancja.sh]   # domyślnie ../nowa_instancja.sh
Skrypt jest uruchamiany w katalogu tymczasowym (kopia instancja.py, szablonów i głównego na_zywo.json): nowa instancja ma
dostać szablon, NIE plik główny. Stary skrypt (nowa_instancja.sh.bak-20261022-nowa-postac) ma tu oblać test."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, shutil, subprocess, sys, tempfile
from pathlib import Path
sys.dont_write_bytecode = True
KAT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KAT))
import cavebot, pokretla

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK  " if warunek else "FAIL"), nazwa, info)

SZAB = KAT / "szablony" / "nowa_postac"
skrypt = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else KAT / "nowa_instancja.sh"
szablon = json.loads((SZAB / "na_zywo.json").read_text())
glowny = json.loads((KAT / "na_zywo.json").read_text())

# 1) szablon wczytuje się tym samym kodem co bot (Pokretla.odswiez na module cavebot): bez odrzuconych i bez "brak stałej"
def wczytaj_jak_bot(plik):
    logi = []
    p = pokretla.Pokretla(cavebot, plik=plik, log=logi.append)
    p.odswiez()
    return p, logi

p, logi = wczytaj_jak_bot(SZAB / "na_zywo.json")
zle = [l for l in logi if "odrzucone" in l or "brak stałej" in l or "błąd odczytu" in l]
sprawdz("szablon: wczytany jak przez bota, 0 odrzuconych", not zle and len(p.aktywne) == len(szablon), f"{len(p.aktywne)}/{len(szablon)} {zle}")
sprawdz("szablon: wartości w module cavebot",
        all(getattr(cavebot, k) == v for k, v in szablon.items()))
sprawdz("szablon: waliduj bez błędów", not pokretla.waliduj(szablon)[1])

# 2) co jest wyłączone w szablonie
WYL = ["RUNA_AKTYWNA", "UH_AKTYWNY", "UH_W_WALCE", "ML_CZAR_AKTYWNY", "JEDZENIE_CZAR_AKTYWNY", "ZDROWIE_CZAR_AKTYWNY",
       "WYPRAWA_AKTYWNA", "WYPRAWA_BLANKI", "WYPRAWA_DEPO_BLANKI", "WROC_REFILL", "BLANKI_AUTO_BAG", "PK_UH_HP",
       "WYPAD_PO_TORCHE", "WYPAD_JEDZENIE", "WYPRAWA_POCHODNIE", "WYPRAWA_JEDZENIE", "WYPRAWA_DEPO_POWROT"]
sprawdz("szablon: runy, blanki, wyprawy, mana, UH, pochodnie wyłączone", all(szablon.get(k) == 0 for k in WYL),
        str([k for k in WYL if szablon.get(k) != 0]))
sprawdz("szablon: różni się od głównego (WYPRAWA_DEPO_BLANKI)", glowny.get("WYPRAWA_DEPO_BLANKI") == 1 and szablon != glowny)

# 3) odchyd (jeśli jest): jego na_zywo.json wczytuje się tym samym kodem bez błędów (równość z szablonem: tylko przy zakładaniu)
od = KAT / "instancje" / "odchyd" / "na_zywo.json"
if od.exists():
    _, lo = wczytaj_jak_bot(od)
    sprawdz("odchyd: wczytany jak przez bota bez błędów", not [l for l in lo if "odrzucone" in l or "brak stałej" in l])

# 4) nowa_instancja.sh w katalogu tymczasowym: nowa instancja dostaje szablon, nie plik główny
with tempfile.TemporaryDirectory() as t:
    gra = Path(t) / "gra"; kat = gra / "pomocnik"
    (gra / "prefix").mkdir(parents=True); (gra / "prefix" / "system.reg").write_text("x")
    kat.mkdir()
    for n in ("instancja.py", "na_zywo.json", "uciekanie.json"):
        shutil.copy(KAT / n, kat / n)
    shutil.copytree(SZAB, kat / "szablony" / "nowa_postac")
    sk = kat / "nowa_instancja.sh"; shutil.copy(skrypt, sk)
    env = {k: v for k, v in _os.environ.items() if not k.startswith("RETRONIC_")}
    r = subprocess.run(["bash", str(sk), "testowa"], cwd=kat, env=env, capture_output=True, text=True, timeout=60)
    sprawdz("nowa_instancja.sh: kod wyjścia 0", r.returncode == 0, r.stderr.strip()[-200:])
    nz = kat / "instancje" / "testowa" / "na_zywo.json"
    sprawdz("nowa instancja: na_zywo.json istnieje", nz.exists())
    if nz.exists():
        dane = json.loads(nz.read_text())
        sprawdz("nowa instancja: na_zywo.json == szablon", dane == szablon, f"WYPRAWA_DEPO_BLANKI={dane.get('WYPRAWA_DEPO_BLANKI')}")
        sprawdz("nowa instancja: to nie plik główny", dane != glowny)
        sprawdz("nowa instancja: bez blanków i run", dane.get("WYPRAWA_AKTYWNA") == 0 and dane.get("UH_AKTYWNY") == 0)
    uc = kat / "instancje" / "testowa" / "uciekanie.json"
    sprawdz("nowa instancja: uciekanie.json == szablon", uc.exists() and uc.read_text() == (SZAB / "uciekanie.json").read_text())
    # brak szablonu = błąd, nie ciche kopiowanie pliku głównego
    shutil.rmtree(kat / "instancje" / "testowa"); shutil.rmtree(kat / "szablony")
    r2 = subprocess.run(["bash", str(sk), "testowa"], cwd=kat, env=env, capture_output=True, text=True, timeout=60)
    brak = (kat / "instancje" / "testowa" / "na_zywo.json").exists()
    sprawdz("brak szablonu: skrypt nie kopiuje pliku głównego", not brak, f"kod {r2.returncode}")

print(f"\n{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
