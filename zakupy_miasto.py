"""Jednorazowo (13.10): z miasta do Frodo (buy 3 ham -> zjedz -> buy 5 ham), potem do Xodeta po blank runy.
Użycie: python3 -I zakupy_miasto.py [blanki]  (domyślnie 20). Bez bota w tle; na koniec stoi przy Xodecie."""
import json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bot, mozg, wypad, wyprawa

BLANKI = int(sys.argv[1]) if len(sys.argv) > 1 else 20
KAT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trasy")
sk = json.load(open(os.path.join(KAT, "wyprawa_sklepy.json")))["przystanki"]
frodo, xodet = sk["frodo"], sk["xodet"]
P = lambda l: [tuple(p) for p in l]
postac = bot.Postac()
ops = wyprawa.OperacjeZywe(log=print, wyslij=lambda t: mozg.wpisz_na_czacie(t))
import mapa as mapa_mod
trasownik = wyprawa.Trasownik(mapa_mod.mapa())


def idz(punkty, nazwa, tol=0):
    punkty = P(punkty)
    print(f"[IDZ] {nazwa}: {len(punkty)} pkt, cel {punkty[-1]}, start {postac.pozycja()}", flush=True)
    ok = mozg.przejdz_dojscie(postac, punkty, prog_hp=40, jedzenie=None, potwory=None, graczy=True,
                              stop_przy_graczach=False, tolerancja=tol, proby=4)
    print(f"[IDZ] {nazwa}: {'OK' if ok else 'NIE DOTARŁEM'}, poz {postac.pozycja()}", flush=True)
    return ok


def czekaj(wzor, s=9.0):
    t0 = time.time()
    while time.time() - t0 < s:
        for w in ops.wiadomosci():
            print(f"  [{w['autor']}/{w['kanal']}] {w['tekst']}", flush=True)
            if w["autor"] == "Jointoramix" and w["kanal"] not in ("Default", ""):
                print(f"STOP: wiadomość poszła na kanał {w['kanal']}, przełącz zakładkę na Default"); sys.exit(5)
            if w["autor"] != "Jointoramix" and re.search(wzor, w["tekst"], re.I):
                return w["tekst"]
        time.sleep(0.6)
    return None


def ile(ids):
    p = ops.plecak()
    return None if p is None else sum(v for k, v in p["id"].items() if k in ids)


def kup(n, slowo, maks_cena, ids):
    przed = ile(ids)
    ops.wiadomosci()
    if os.environ.get("TYLKO_BLANKI"):   # rozmowa z NPC mogła zostać otwarta: zamykamy i zaczynamy od nowa
        ops.czat("bye"); time.sleep(3.0); ops.wiadomosci()
    time.sleep(2.0)                      # po dojściu chwila na zatrzymanie i widok NPC
    for proba in range(4):
        ops.czat("hi")
        if czekaj(r"hello|welcome|hi\b|come in|what do you need|how can i help", 6) is not None:
            break
        print(f"brak odpowiedzi na hi (próba {proba + 1}/4), czekam", flush=True)
        time.sleep(3.0)
    else:
        print("BRAK ODPOWIEDZI NPC na hi"); return False
    ops.czat(f"buy {n} {slowo}")
    r = czekaj(r"want to buy|buy\s+\d+", 9)
    m = wyprawa.ODP_OFERTA.search(r or "")
    if not m:
        print("BRAK OFERTY", r); ops.czat("bye"); return False
    szt, cena = int(m[1]), int(m[3])
    print(f"oferta: {szt} za {cena} gp", flush=True)
    if szt > n or cena > maks_cena:
        ops.czat("no"); print("oferta poza limitem, odmówiłem"); return False
    ops.czat("yes"); czekaj(r"bought|thank", 8)
    ops.czat("bye")
    time.sleep(2.0)
    po = ile(ids)
    print(f"{slowo}: przed {przed}, po {po}", flush=True)
    return po is not None and przed is not None and po > przed


ID_HAM = ops.id_ham if hasattr(ops, "id_ham") else set()
print("start:", postac.pozycja(), "ham:", ile(ID_HAM), flush=True)
if os.environ.get("TYLKO_BLANKI"):
    ok = kup(BLANKI, "blank rune", 20 * BLANKI, wyprawa.ID_BLANK)
    print("KONIEC", "OK" if ok else "blanki nie kupione", postac.pozycja(), flush=True)
    sys.exit(0 if ok else 1)
poz = tuple(postac.pozycja())
if poz[2] != 7:
    print("nie na z7, przerywam"); sys.exit(1)
if os.environ.get("DO_XODETA"):      # stoimy już w drodze do Xodeta: od najbliższego punktu nagrania, potem blanki
    pts = list(reversed(P(xodet["powrot"]))) + [tuple(xodet["stoi"])]
    pz = tuple(postac.pozycja())
    a = trasownik.odcinek(pz, pts[0])    # z dowolnego miejsca w mieście: A* do początku nagrania, potem nagranie
    if not a:
        print("brak drogi A* do początku trasy Xodeta"); sys.exit(7)
    if not idz(a + pts[1:], "do Xodeta (A* + nagranie)"):
        sys.exit(7)
    ok = kup(BLANKI, "blank rune", 20 * BLANKI, wyprawa.ID_BLANK)
    print("KONIEC", "OK" if ok else "blanki nie kupione", postac.pozycja(), flush=True)
    sys.exit(0 if ok else 1)
if os.environ.get("BEZ_FRODO"):      # ham kupiony ręcznie: tylko jedzenie, potem Gorn -> Xodet
    for i in range(14):
        z = ops.zjedz()
        print("zjedzono:", z, flush=True)
        if not z:
            break
        time.sleep(1.5)
else:
    dojscie_f = P(frodo["dojscie"])
    stoi_f = tuple(frodo["stoi"])
    if max(abs(poz[0] - stoi_f[0]), abs(poz[1] - stoi_f[1])) <= 4:
        ok_f = idz([stoi_f], "krok na pole Frodo")
    else:
        a = trasownik.odcinek(poz, dojscie_f[0])
        if not a:
            print("brak drogi A* do początku dojścia Frodo"); sys.exit(2)
        ok_f = idz(a + dojscie_f[1:] + [stoi_f], "do Frodo")
    if not ok_f:
        sys.exit(3)
    if not kup(3, "ham", 150, ID_HAM):
        sys.exit(4)
    for i in range(14):
        z = ops.zjedz()
        print("zjedzono:", z, flush=True)
        if not z:
            break
        time.sleep(1.5)
    if not kup(4, "ham", 150, ID_HAM):
        sys.exit(5)
if not idz(P(frodo["powrot"]), "Frodo -> Gorn"):
    sys.exit(6)
if not idz(list(reversed(P(xodet["powrot"]))) + [tuple(xodet["stoi"])], "do Xodeta"):
    sys.exit(7)
ok = kup(BLANKI, "blank rune", 20 * BLANKI, wyprawa.ID_BLANK)
print("KONIEC", "OK" if ok else "blanki nie kupione", postac.pozycja(), flush=True)
