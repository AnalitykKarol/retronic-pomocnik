"""Tryb handlu instancji w trade_logger (SPEC_handel_johny_1019.md F1): rozpoznanie priv/kanalu, okazje
(knight axe <= 3500, dwarven shield <= 200, kupcy UH), okienka z cisza, pliki, brak okienek dla starych wiadomosci.
Wiadomosci wzorowane na zywym odczycie instancji test (19.10)."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, tempfile, pathlib, json
sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import trade_logger as tl

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))

tmp = pathlib.Path(tempfile.mkdtemp())
(tmp / "handel.json").write_text(json.dumps({
    "nick": "Johny Dang", "miasto": "edron/thais",
    "kupuje": {"Knight Axe": 3500, "dwarven shield": 200}, "sprzedaje": {"ultimate healing rune": 2300}}))
K = tl.wczytaj_konfig(tmp / "handel.json")

# 0. konfiguracja
sprawdz("0a brak pliku = stary tryb (None)", tl.wczytaj_konfig(tmp / "nie_ma.json") is None)
sprawdz("0b nazwy przedmiotow malymi literami", "knight axe" in K["kupuje"], K["kupuje"])
(tmp / "zly.json").write_text("{zly")
try:
    tl.wczytaj_konfig(tmp / "zly.json"); sprawdz("0c bledny JSON zatrzymuje", False)
except SystemExit:
    sprawdz("0c bledny JSON zatrzymuje", True)

# 1. rodzaj wiadomosci (kolory z rdzenia)
W = "Johny Dang"
sprawdz("1a priv przychodzacy", tl.rodzaj({"nadawca": "Malik", "kolor": "5ff7f7", "kanal": None}, W) == "priv")
sprawdz("1b priv w zakladce z blednym kanalem", tl.rodzaj({"nadawca": "Twocup Shakur", "kolor": "5ff7f7", "kanal": "Malik"}, W) == "priv")
sprawdz("1c wlasny wychodzacy priv (nadawca None)", tl.rodzaj({"nadawca": None, "kolor": "9f9dfd"}, W) is None)
sprawdz("1d wlasne ogloszenie pomijane", tl.rodzaj({"nadawca": W, "kolor": "ffff00"}, W) is None)
sprawdz("1e Trade z pustym kanalem", tl.rodzaj({"nadawca": "Cafar", "kolor": "ffff00", "kanal": None}, W) == "kanal")
sprawdz("1f Server Log bez nadawcy", tl.rodzaj({"nadawca": None, "kolor": "f55e5e", "kanal": "Server Log"}, W) is None)

# 2. okazje
def okazje(tekst, nick="Sprzedawca"):
    return [(typ, l) for o, typ, l in tl.okazje(tl.rozpoznaj(tekst, nick, 1, 1, "e"), K)]

r = okazje("sell knight axe 3k")
sprawdz("2a KA 3k w progu + linijka", r == [("w_progu", "*Sprzedawca* hi, ill take knight axe for 3k, where r u?")], r)
sprawdz("2b KA 4k powyzej progu: nic", okazje("sell knight axe 4k") == [])
sprawdz("2c KA dokladnie 3.5k: w progu", [t for t, _ in okazje("sell knight axe 3.5k")] == ["w_progu"])
r = okazje("SELLING - Giant Sword  / Crown Armor / Knight Axe / Vampire Shield    ----> ANKRAHMUN", "Omen")
sprawdz("2d KA bez ceny w liscie: pytanie o cene", ("bez_ceny", "*Omen* hi, how much for knight axe?") in r, r)
r = okazje("SELL SERPENT SWORD, DARK HELMET,, BROAD SWORD ,, ,  DWARVEN SHIELD, 128 BURST ARROW, PLATE LEGS")
sprawdz("2e DS bez ceny w liscie (z zywego czatu)", [t for t, _ in r] == ["bez_ceny"], r)
sprawdz("2f DS 150 w progu", [t for t, _ in okazje("sell dwarven shield 150")] == ["w_progu"])
sprawdz("2g DS 250 powyzej progu", okazje("sell dwarven shield 250") == [])
r = okazje("BUY BP UH CARLIN 2.3k SELL AXE RING", "Chlopakz Bloku")
sprawdz("2h kupiec UH: nasza cena i miasto",
        r == [("kupiec", "*Chlopakz Bloku* hi, uh 2.3k per bp, how many bps? im in edron/thais")], r)
sprawdz("2i sprzedawca UH: nic (UH sprzedajemy, nie kupujemy)", okazje("sell 3 bp uh carlin 2.5k ea") == [])
sprawdz("2j kupiec KA: nic (KA kupujemy)", okazje("buy knight axe 4k") == [])
sprawdz("2k 2 KA za 6k lacznie = 3k/szt: w progu", [t for t, _ in okazje("sell 2x knight axe 6k for all")] == ["w_progu"])

# 3. cykl na danych jak z gniazda (sucho: bez notify-send)
def wiad(nr, nadawca, tekst, kolor="ffff00", ts=1000, kanal=None):
    return {"nr": nr, "nadawca": nadawca, "tekst": tekst, "kolor": kolor, "ts": ts, "czas": "16:00", "kanal": kanal}

pliki = {"oferty": tmp / "o.jsonl", "alerty": tmp / "a.jsonl", "priv": tmp / "p.jsonl"}
dane = {"epoka": "E", "wiadomosci": [
    wiad(1, "Malik", "2k?", "5ff7f7"),
    wiad(2, None, "Johny Dang [8]: how much bags?", "9f9dfd"),
    wiad(3, "Johny Dang", "~~~~SELL~~~~5BP UH's 2.3k EDRON/THAIS"),
    wiad(4, "Cafar", "sell knight axe 3k"),
    wiad(5, "Zbor", "hi"),
    wiad(6, None, "You have been idle for 29 minutes", "f55e5e", kanal="Server Log"),
]}
st = tl.Stan()
w = tl.cykl_handlu(st, K, pliki, True, start_ts=1000, dane=dane, teraz=0.0)
sprawdz("3a jeden priv (Malik), bez wlasnych i Server Log", [p["nadawca"] for p in w["priv"]] == ["Malik"], w["priv"])
sprawdz("3b jeden alert KA od Cafar", [(a["nadawca"], a["typ"]) for a in w["alerty"]] == [("Cafar", "w_progu")], w["alerty"])
sprawdz("3c wlasne ogloszenie nie jest oferta", all(o["nadawca"] != "Johny Dang" for o in w["oferty"]))
sprawdz("3d pliki priv/alerty zapisane", len(pliki["priv"].read_text().splitlines()) == 1
        and len(pliki["alerty"].read_text().splitlines()) == 1)
w2 = tl.cykl_handlu(st, K, pliki, True, start_ts=1000, dane=dane, teraz=1.0)
sprawdz("3e drugi odczyt tych samych nr: nic nowego", w2["nowe"] == 0 and not w2["priv"] and not w2["alerty"])

# 4. okienka: cisza i stare wiadomosci (atrapa notify-send)
wywolania = []
tl.shutil.which = lambda _n: "/usr/bin/notify-send"
tl.subprocess.run = lambda cmd, **kw: wywolania.append(cmd)
st = tl.Stan()
dane4 = {"epoka": "F", "wiadomosci": [wiad(1, "Malik", "uh?", "5ff7f7", ts=5000), wiad(2, "Malik", "thais?", "5ff7f7", ts=5000),
                                       wiad(3, "Stary", "hej", "5ff7f7", ts=100)]}
w = tl.cykl_handlu(st, K, pliki, False, start_ts=5000, dane=dane4, teraz=10.0)
sprawdz("4a dwa priv Malika w minucie = jedno okienko", sum(1 for c in wywolania if "priv od Malik" in " ".join(c)) == 1, wywolania)
sprawdz("4b stara wiadomosc (sprzed startu) bez okienka, ale zapisana",
        not any("Stary" in " ".join(c) for c in wywolania) and any(p["nadawca"] == "Stary" for p in w["priv"]))
dane5 = {"epoka": "F", "wiadomosci": dane4["wiadomosci"] + [wiad(4, "Malik", "ready", "5ff7f7", ts=5100)]}
tl.cykl_handlu(st, K, pliki, False, start_ts=5000, dane=dane5, teraz=10.0 + tl.CISZA_PRIV)
sprawdz("4c po minucie kolejne okienko od Malika", sum(1 for c in wywolania if "priv od Malik" in " ".join(c)) == 2, wywolania)
sprawdz("4d okienko z tytulem i trescia", wywolania and wywolania[0][-2:] == ["Johny Dang: priv od Malik", "uh?"], wywolania[:1])

# 5. tryb glowny bez zmian: domyslny filtr Stan bierze tylko kanal Trade
st = tl.Stan()
sprawdz("5 domyslny filtr: tylko kanal Trade",
        [m["nr"] for m in st.nowe([{"kanal": "Trade", "nr": 1}, {"kanal": None, "nr": 2, "kolor": "ffff00", "nadawca": "X"}], "G")] == [1])

# 6. okazje: ogloszeniowiec co 2 min -> jedno okienko na godzine, zwykle (nie pilne); priv pilne
wywolania.clear()
st = tl.Stan()
for i in range(5):
    tl.cykl_handlu(st, K, pliki, False, start_ts=5000,
                   dane={"epoka": "H", "wiadomosci": [wiad(10 + i, "Manowar", "BUY UHS [2K/BP]", ts=5000)]}, teraz=120.0 * i)
sprawdz("6a ta sama okazja przez 10 min = jedno okienko", len(wywolania) == 1, wywolania)
sprawdz("6b okazja zwykla, priv pilne", wywolania and wywolania[0][4] == "normal"
        and tl.okienko(tl.Stan(), "p", "t", "x", False, 0.0, 60, pilne=True) and wywolania[-1][4] == "critical", wywolania)
tl.cykl_handlu(st, K, pliki, False, start_ts=5000,
               dane={"epoka": "H", "wiadomosci": [wiad(20, "Manowar", "BUY UHS [2K/BP]", ts=5000)]}, teraz=tl.CISZA_OKAZJI + 1)
sprawdz("6c po godzinie przypomnienie", sum(1 for c in wywolania if "Manowar" in " ".join(c)) == 2, wywolania)

print("\nWYNIK:", sum(ok), "/", len(ok))
sys.exit(0 if all(ok) else 1)
