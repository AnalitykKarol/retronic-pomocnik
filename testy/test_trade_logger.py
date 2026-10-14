import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, tempfile, pathlib, json
sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import trade_logger as tl

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))

def jedna(tekst):
    oferty = tl.rozpoznaj(tekst, "Test", 1791923760, 1, "e")
    return oferty

def pola(o):
    return (o["intencja"], o["przedmiot"], o["ilosc"], o["jednostka"], o["cena"], o["cena_typ"],
            o["cena_calkowita"], o["miasto"], o["niepewne"])

# 1. parser: tekst -> oczekiwane (intencja, przedmiot, ilosc, jednostka, cena, typ, calkowita, miasto, niepewne)
PRZYKLADY = [
    ("sell guardian shield 3.5k ANKRAHMUN",
     [("sprzedaje", "guardian shield", None, None, 3500, None, None, "Ankrahmun", False)]),
    ("[SELL] 3 BP [UH] 2.5k 7k for ALL",
     [("sprzedaje", "ultimate healing rune", 3, "bp", 2500, None, 7000, None, False)]),
    ("buy uh 190 ea",
     [("kupuje", "ultimate healing rune", None, None, 190, "ea", None, None, False)]),
    ("wtb hmm 150",
     [("kupuje", "heavy magic missile rune", None, None, 150, None, None, None, False)]),
    ("sell sword",
     [("sprzedaje", "sword", None, None, None, None, None, None, False)]),
    ("sell 20 BP GFB 2,5K EACH",
     [("sprzedaje", "great fireball rune", 20, "bp", 2500, "ea", None, None, False)]),
    ("Sell 10 bp hmm - 20k",
     [("sprzedaje", "heavy magic missile rune", 10, "bp", 20000, None, None, None, False)]),
    ("SELL 6 BP HMM",
     [("sprzedaje", "heavy magic missile rune", 6, "bp", None, None, None, None, False)]),
    ("Sell 18 BP SD 4.5k Ea <<Carlin>>",
     [("sprzedaje", "sudden death rune", 18, "bp", 4500, "ea", None, "Carlin", False)]),
    ("sell warrior helmet 9 arm",
     [("sprzedaje", "warrior helmet", None, None, 9, None, None, None, True)]),
    ("Sell  Knight Axe 4k //  77 coconuts  600 gp each all for 40k  << Venore >>",
     [("sprzedaje", "knight axe", None, None, 4000, None, None, "Venore", False),
      ("sprzedaje", "coconut", 77, None, 600, "ea", 40000, "Venore", False)]),
    ("Westin | SELL  SPIKE SWORD / 3X ICE RAPIER / PLATE ARMOR/  10 X MAGIC LIGHT WAND / ANKRAHMUN",
     [("sprzedaje", "spike sword", None, None, None, None, None, "Ankrahmun", False),
      ("sprzedaje", "ice rapier", 3, None, None, None, None, "Ankrahmun", False),
      ("sprzedaje", "plate armor", None, None, None, None, None, "Ankrahmun", False)]),
    ("{{BUY}} :  ALL Bp of HMM 1,2 k each  ALL BP of UHs 2.2k;  {{SELL}} : Fire Sword ; Dragon Hammer",
     [("kupuje", "heavy magic missile rune", None, None, 1200, "ea", None, None, False),
      ("kupuje", "ultimate healing rune", None, None, 2200, None, None, None, False),
      ("sprzedaje", "fire sword", None, None, None, None, None, None, False),
      ("sprzedaje", "dragon hammer", None, None, None, None, None, None, False)]),
    ("Manowar SELL BP SD [5K] / BP GFB [2.6K BP] / BP HMM [1.6K] >> CARLIN",
     [("sprzedaje", "sudden death rune", 1, "bp", 5000, None, None, "Carlin", False),
      ("sprzedaje", "great fireball rune", 1, "bp", 2600, None, None, "Carlin", False),
      ("sprzedaje", "heavy magic missile rune", 1, "bp", 1600, None, None, "Carlin", False)]),
    ("sell /Dwarven Shield 150gp/scale armor 80gp/Soldier helmet 50gp/BUY ALL ARROWS !",
     [("sprzedaje", "dwarven shield", None, None, 150, None, None, None, False),
      ("sprzedaje", "scale armor", None, None, 80, None, None, None, False),
      ("sprzedaje", "soldier helmet", None, None, 50, None, None, None, False),
      ("kupuje", None, None, None, None, None, None, None, True)]),
    ("sell dragon hammer  BUY life rings",
     [("sprzedaje", "dragon hammer", None, None, None, None, None, None, False),
      ("kupuje", "life ring", None, None, None, None, None, None, False)]),
    ("SELLLL DWARVEN AXE - SELLL NAGINATA- SELLL TIME RING",
     [("sprzedaje", "dwarven axe", None, None, None, None, None, None, False),
      ("sprzedaje", "naginata", None, None, None, None, None, None, False),
      ("sprzedaje", "time ring", None, None, None, None, None, None, False)]),
    ("Wakabayashi | * BUYING HMM's*  BUYING BLAZZING BOW * Selling  ** Knight AXE ** Plate Legs **",
     [("kupuje", "heavy magic missile rune", None, None, None, None, None, None, False),
      ("kupuje", None, None, None, None, None, None, None, True),
      ("sprzedaje", "knight axe", None, None, None, None, None, None, False),
      ("sprzedaje", "plate legs", None, None, None, None, None, None, False)]),
    ("BUY ALL SMALL STONE !!!",
     [("kupuje", None, None, None, None, None, None, None, True)]),
    ("BUY BP UH CARLIN",
     [("kupuje", "ultimate healing rune", 1, "bp", None, None, None, "Carlin", False)]),
    ("Sell  Red Spellwand 25k",
     [("sprzedaje", None, None, None, 25000, None, None, None, True)]),
    ("sell 77 coconuts 600 gp each",
     [("sprzedaje", "coconut", 77, None, 600, "ea", None, None, False)]),
    ("SELL DEMON SHIELD 50k  ** FIRE AXE 30k * FIRE SWORD 20k ( GOOD PRICE )",
     [("sprzedaje", "demon shield", None, None, 50000, None, None, None, False),
      ("sprzedaje", "fire axe", None, None, 30000, None, None, None, False),
      ("sprzedaje", "fire sword", None, None, 20000, None, None, None, False)]),
    ("Sell 3 x magic wall rune 2k",
     [("sprzedaje", "magic wall rune", 3, None, 2000, None, None, None, False)]),
    ("wts gold coins 3 x blank rune 1.5k each",
     [("sprzedaje", "gold coin", None, None, None, None, None, None, False),
      ("sprzedaje", "blank rune", 3, None, 1500, "ea", None, None, False)]),
    ("Looking team for desert quest need ms and ed",
     []),
    ("hi all, how are you",
     []),
    ("buy hmm 1,2k ea Ankrahmun",
     [("kupuje", "heavy magic missile rune", None, None, 1200, "ea", None, "Ankrahmun", False)]),
    ("sell blue shield 3k",
     [("sprzedaje", None, None, None, 3000, None, None, None, True)]),
]

for tekst, oczekiwane in PRZYKLADY:
    wynik = [pola(o) for o in jedna(tekst)]
    oczekiwane = [tuple(x) for x in oczekiwane]
    sprawdz(f"1 parser: {tekst[:60]}", wynik == oczekiwane, f"{wynik}")

sprawdz("1 liczba przykladow parsera >= 20", len(PRZYKLADY) >= 20, len(PRZYKLADY))

# parser: tekst oryginalny i autor trafiaja do rekordu, nadawca to pole osobne
o = jedna("sell sword 2k")[0]
sprawdz("1 rekord ma tekst_oryg, nadawce, nr, epoka", o["tekst_oryg"] == "sell sword 2k" and o["nadawca"] == "Test"
        and o["nr"] == 1 and o["epoka"] == "e" and o["czas"], o)
sprawdz("1 pusty tekst nie wywraca", tl.rozpoznaj("", "X") == [])

# 2. deduplikacja po nr, epoka, pomijanie innego kanalu
stan = tl.Stan()
msgs = [{"kanal": "Trade", "nr": 10, "nadawca": "A", "tekst": "sell sword"},
        {"kanal": "Trade", "nr": 11, "nadawca": "B", "tekst": "sell axe"},
        {"kanal": None, "nr": 12, "nadawca": "C", "tekst": "sell x"}]
sprawdz("2a pierwszy odczyt: nowe Trade bez innych kanalow", [m["nr"] for m in stan.nowe(msgs, "E1")] == [10, 11])
sprawdz("2b ponowny odczyt tych samych: brak nowych", stan.nowe(msgs, "E1") == [])
sprawdz("2c nowy nr przechodzi", [m["nr"] for m in stan.nowe(msgs + [{"kanal": "Trade", "nr": 13}], "E1")] == [13])
sprawdz("2d zmiana epoki resetuje", [m["nr"] for m in stan.nowe(msgs[:1], "E2")] == [10])
sprawdz("2e brak nr jest pomijany", stan.nowe([{"kanal": "Trade", "tekst": "x"}], "E2") == [])

# 3. podsumowanie na pliku tymczasowym
tmp = pathlib.Path(tempfile.mkdtemp())
teraz = 1_800_000_000.0
rekordy = [
    {"ts": teraz - 100, "nadawca": "A", "intencja": "sprzedaje", "przedmiot": "fire sword", "cena": 20000, "cena_typ": "ea", "ilosc": None, "jednostka": None, "niepewne": False},
    {"ts": teraz - 200, "nadawca": "B", "intencja": "sprzedaje", "przedmiot": "fire sword", "cena": 30000, "cena_typ": "ea", "ilosc": None, "jednostka": None, "niepewne": False},
    {"ts": teraz - 300, "nadawca": "A", "intencja": "sprzedaje", "przedmiot": "fire sword", "cena": 20000, "cena_typ": "ea", "ilosc": None, "jednostka": None, "niepewne": False},  # duplikat ogloszenia
    {"ts": teraz - 400, "nadawca": "C", "intencja": "sprzedaje", "przedmiot": "fire sword", "cena": 25000, "cena_typ": None, "ilosc": None, "jednostka": None, "niepewne": False},  # bez ea
    {"ts": teraz - 500, "nadawca": "D", "intencja": "kupuje", "przedmiot": "ultimate healing rune", "cena": 2200, "cena_typ": "ea", "ilosc": 3, "jednostka": "bp", "niepewne": False},
    {"ts": teraz - 600, "nadawca": "E", "intencja": "kupuje", "przedmiot": "ultimate healing rune", "cena": 9999, "cena_typ": "ea", "ilosc": None, "jednostka": None, "niepewne": True},  # niepewne - pominiete
    {"ts": teraz - 3 * 86400, "nadawca": "F", "intencja": "sprzedaje", "przedmiot": "fire sword", "cena": 40000, "cena_typ": "ea", "ilosc": None, "jednostka": None, "niepewne": False},
    {"ts": teraz - 10 * 86400, "nadawca": "G", "intencja": "sprzedaje", "przedmiot": "fire sword", "cena": 1, "cena_typ": "ea", "ilosc": None, "jednostka": None, "niepewne": False},  # poza 7 dniami
    {"ts": teraz - 50, "nadawca": "H", "intencja": "sprzedaje", "przedmiot": None, "cena": 5, "cena_typ": "ea", "ilosc": None, "jednostka": None, "niepewne": False},
]
plik_ofert = tmp / "ceny.jsonl"
plik_ofert.write_text("\n".join(json.dumps(r) for r in rekordy) + "\n", encoding="utf-8")
plik_podsum = tmp / "podsum.json"
wynik = tl.przelicz_podsumowanie(plik_ofert, plik_podsum, teraz=teraz)
fs24 = wynik["okna"]["24h"]["fire sword"]
sprawdz("3a 24h: sprzedaz liczy unikalne pewne oferty", fs24["sprzedaz"]["liczba"] == 3, fs24)
sprawdz("3b 24h: mediana/min/max tylko z ea (20000, 30000)",
        fs24["sprzedaz"]["mediana"] == 25000 and fs24["sprzedaz"]["min"] == 20000 and fs24["sprzedaz"]["max"] == 30000, fs24)
ur = wynik["okna"]["24h"]["ultimate healing rune"]
sprawdz("3c 24h: kupno UH bez niepewnych", ur["kupno"]["liczba"] == 1 and ur["kupno"]["mediana"] == 2200, ur)
sprawdz("3d 7d: wlacza starsze, pomija >7 dni", wynik["okna"]["7d"]["fire sword"]["sprzedaz"]["max"] == 40000
        and wynik["okna"]["7d"]["fire sword"]["sprzedaz"]["liczba"] == 4, wynik["okna"]["7d"]["fire sword"])
sprawdz("3e brak przedmiotu nie trafia do podsumowania", None not in wynik["okna"]["24h"])
sprawdz("3f plik podsumowania zapisany", json.loads(plik_podsum.read_text(encoding="utf-8"))["okna"]["24h"] == wynik["okna"]["24h"])
wynik_pusty = tl.przelicz_podsumowanie(tmp / "brak.jsonl", tmp / "p2.json", teraz=teraz)
sprawdz("3g brak pliku ofert nie wywraca", wynik_pusty["okna"]["24h"] == {})

# 4. alerty: zapis do pliku, bez notify-send w tescie (sucho, notyfikuj=False)
plik_alertow = tmp / "alerty.jsonl"
stan_al = tl.Stan()
oferty_al = (jedna("buy uh 190 ea") + jedna("wtb hmm 150") + jedna("sell sword 3k") + jedna("buy blank rune 40"))
oferty_al[0]["nadawca"] = "Kupiec1"
for o in oferty_al:
    o.setdefault("tekst_oryg", "x")
alerty = tl.alerty_z_ofert(oferty_al, stan_al, sucho=True, plik_alertow=plik_alertow, teraz=1000.0, notyfikuj=False)
sprawdz("4a alerty tylko dla UH/HMM/blank kupno", [a["przedmiot"] for a in alerty] ==
        ["ultimate healing rune", "heavy magic missile rune", "blank rune"], alerty)
sprawdz("4b alert zapisany w pliku", len(plik_alertow.read_text(encoding="utf-8").splitlines()) == 3)
sprawdz("4c sucho: powiadomienie nie idzie", all(not a["powiadomiono"] for a in alerty))
st = tl.Stan()
st.ostatnio_powiadomiono["X"] = 0.0
sprawdz("4d limit: powiadom odrzuca przed uplywem 10 min (bez realnego notify-send)",
        tl.powiadom(st, "X", "t", False, 300.0) is False)
sprawdz("4e sucho: powiadom nie wywoluje nic i zwraca False", tl.powiadom(tl.Stan(), "Y", "t", True, 0.0) is False)

# 5. zaladowanie przedmiotow z bazy projektu (tylko odczyt)
nazwy = tl.zaladuj_przedmioty()
sprawdz("5 przedmioty.json daje nazwy (UH jako pelna nazwa, skrot nie)",
        "ultimate healing rune" in nazwy and "sword" in nazwy and "uh" not in nazwy and len(nazwy) > 100, len(nazwy))

print("\nWYNIK:", sum(ok), "/", len(ok))
sys.exit(0 if all(ok) else 1)
