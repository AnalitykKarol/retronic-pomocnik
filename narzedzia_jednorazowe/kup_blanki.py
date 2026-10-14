"""Jednorazowy test zakupu ham u NPC stojącego obok (13.10): hi -> buy N ham -> yes, weryfikacja w plecaku.
Użycie: python3 -I kup_test.py [N] (domyślnie 3). Nie wymaga uruchomionego bota; wpisuje na Default przez XTEST."""
import os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mozg, wypad, wyprawa

N = int(sys.argv[1]) if len(sys.argv) > 1 else 3
ops = wypad.OperacjeZywe(log=print, wyslij=lambda t: mozg.wpisz_na_czacie(t))

def blank():
    p = ops.plecak()
    return None if p is None else sum(v for k, v in p["id"].items() if k in {3147})

def czekaj(wzor, s=9.0):
    t0 = time.time(); wid = []
    while time.time() - t0 < s:
        for w in ops.wiadomosci():
            print(f"  [{w['autor']}/{w['kanal']}] {w['tekst']}"); wid.append(w["tekst"])
            if w["autor"] == "Jointoramix" and w["kanal"] not in ("Default", ""):
                print(f"STOP: moja wiadomość poszła na kanał {w['kanal']}, przełącz zakładkę na Default"); sys.exit(5)
            if w["autor"] != "Jointoramix" and re.search(wzor, w["tekst"], re.I):
                return w["tekst"], wid
        time.sleep(0.6)
    return None, wid

ops.wiadomosci()
przed = blank(); print("blank przed:", przed)
ops.czat(f"buy {N} blank rune"); r, _ = czekaj(r"want to buy|buy\s+\d+")
if r is None:
    print("BRAK OFERTY"); sys.exit(3)
m = wyprawa.ODP_OFERTA.search(r)
print("oferta:", m.groups() if m else r)
if m and int(m[1]) <= N and int(m[3]) <= 500:
    ops.czat("yes"); czekaj(r"bought|thank", 8)
else:
    ops.czat("no"); print("oferta poza limitem, odmówiłem"); sys.exit(4)
time.sleep(2.0)
po = blank(); print("blank po:", po)
