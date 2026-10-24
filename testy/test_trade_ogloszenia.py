import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
"""Testy offline ogłoszeń Trade (mozg.TradeOgloszenia, wyslij_na_trade, szablon, zakładki). Zero inputu do gry:
funkcje wejścia (kliknij/wpisz/zrzut) to atrapy; wpisz_na_czacie i Mysz są zablokowane."""
import random, sys, tempfile, types
sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
from pathlib import Path
from PIL import Image
import bot, cavebot, mozg, pokretla

KAT = Path(__file__).resolve().parent
tmp = Path(tempfile.mkdtemp(prefix="pomocnik-trade-"))
ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK  " if warunek else "FAIL"), nazwa, info)

def zakaz(*a, **k): raise AssertionError("INPUT DO GRY w teście!")
mozg.wpisz_na_czacie = zakaz

DEFAULT = Image.open(KAT / "dane" / "trade_zakladki_default.png").convert("RGB")   # zrzut sesji: aktywna Default

def obraz_trade():
    """Syntetyczny zrzut ze stanem "Trade aktywna": zamiana kolorów tekstu zakładek (biały <-> czerwony)."""
    im = DEFAULT.copy()
    w, h = im.size
    for nazwa, do in (("Default", "czerwony"), ("Trade", "bialy")):
        u = mozg.uklad_paska(im.size)     # 23.10: układ wg rozmiaru obrazu (fixture 734x910 = stary wzorzec)
        x0, x1 = u["zakladki_x"][nazwa]; y0, y1 = u["pasek_y"]
        for x in range(int(x0 * w), int(x1 * w) + 1):
            for y in range(int(y0 * h), int(y1 * h) + 1):
                r, g, b = im.getpixel((x, y))
                jas = max(r, g, b)
                if jas >= 100:
                    im.putpixel((x, y), (jas, 60, 60) if do == "czerwony" else (jas, jas, jas))
    return im

TRADE = obraz_trade()

class Zegar:
    def __init__(s, t=1000.0): s.t = t
    def __call__(s): return s.t

class Konf(types.SimpleNamespace): pass

def konf(**k):
    d = dict(TRADE_OGLOSZENIA=1, TRADE_MIN_S=180, TRADE_MAX_S=300, TRADE_MIN_UH=20); d.update(k)
    return Konf(**d)

# --- pokrętła -------------------------------------------------------------------------------
sprawdz("pokrętło domyślnie 0 (WYŁĄCZONE)", cavebot.TRADE_OGLOSZENIA == 0)
sprawdz("domyślne odstępy 180/300, min UH 20", (cavebot.TRADE_MIN_S, cavebot.TRADE_MAX_S, cavebot.TRADE_MIN_UH) == (180, 300, 20))
for k in ("TRADE_OGLOSZENIA", "TRADE_MIN_S", "TRADE_MAX_S", "TRADE_MIN_UH"):
    sprawdz(f"ZAKRESY zawiera {k}", k in pokretla.ZAKRESY)
okk, bl = pokretla.waliduj({"TRADE_OGLOSZENIA": 1, "TRADE_MIN_UH": 25})
sprawdz("na_zywo: poprawne wartości przyjęte", okk == {"TRADE_OGLOSZENIA": 1, "TRADE_MIN_UH": 25} and not bl, str(bl))
okk, bl = pokretla.waliduj({"TRADE_OGLOSZENIA": 2, "TRADE_MIN_UH": 5})
sprawdz("na_zywo: poza zakresem odrzucone", not okk and len(bl) == 2, str(bl))
okk, bl = pokretla.waliduj({"TRADE_OGLOSZENIA": 1}, {"TRADE_OGLOSZENIA": 0})
sprawdz("analityk nie może włączyć ogłoszeń", not okk and bl, str(bl))

wywolania = []
def planista(konfig=None, **kw):
    z = kw.pop("zegar", Zegar())
    logi = []
    args = dict(uh_ile=lambda: 100, spokoj=lambda: "", wyslij=lambda t: (wywolania.append(t) or (True, "", True)),
                losuj=random.uniform, konf=konfig or konf(), plik=tmp / "brak.txt")
    args.update(kw)
    return mozg.TradeOgloszenia(z, logi.append, **args), z, logi

# --- wyłączone: nic nie robi ----------------------------------------------------------------
wywolania.clear()
t, z, logi = planista(konf(TRADE_OGLOSZENIA=0), uh_ile=lambda: 1 / 0, spokoj=lambda: 1 / 0)
z.t += 10000
sprawdz("wyłączone: tick nic nie robi i niczego nie czyta", t.tick() is None and not wywolania and not logi)

# --- losowanie odstępu ----------------------------------------------------------------------
random.seed(7)
t, z, logi = planista()
starty = [planista()[0].nastepne - 1000.0 for _ in range(200)]
sprawdz("pierwsze ogłoszenie 60-120 s po starcie", min(starty) >= 60 and max(starty) <= 120, f"{min(starty):.0f}-{max(starty):.0f}")
od = [t.odstep() for _ in range(2000)]
sprawdz("odstęp w zakresie 180-300 s", min(od) >= 180 and max(od) <= 300, f"{min(od):.0f}-{max(od):.0f}")
srednia = sum(od) / len(od)
rozklad = [sum(1 for x in od if 180 + 30 * i <= x < 180 + 30 * (i + 1)) for i in range(4)]
sprawdz("rozkład równomierny", abs(srednia - 240) < 5 and all(380 < r < 620 for r in rozklad), f"średnia {srednia:.1f} {rozklad}")
t, z, logi = planista(konf(TRADE_MIN_S=200, TRADE_MAX_S=150))
sprawdz("MAX < MIN: odstęp obcięty do MIN", all(t.odstep() == 200 for _ in range(20)))

# --- wysyłka i planowanie następnej ---------------------------------------------------------
wywolania.clear()
t, z, logi = planista()
z.t = 1000 + 59
sprawdz("przed terminem nic", t.tick() is None and not wywolania)
z.t = t.nastepne
sprawdz("w terminie wysyła", t.tick() == "wyslane" and len(wywolania) == 1, str(wywolania))
sprawdz("ogłoszenie: 5 BP przy 100 run", wywolania and "5 bp" in wywolania[0], str(wywolania))
sprawdz("następny termin 180-300 s", 180 <= t.nastepne - z.t <= 300, f"{t.nastepne - z.t:.0f}")

# --- odroczenie przy warunkach (10-20 s, bez kolejkowania) ----------------------------------
wywolania.clear()
powody = ["walka"]
t, z, logi = planista(spokoj=lambda: powody[0] if powody else "")
z.t = t.nastepne
d0 = z.t
sprawdz("warunki niespełnione: odroczone", t.tick() == "odroczone" and not wywolania)
sprawdz("odroczenie 10-20 s", 10 <= t.nastepne - d0 <= 20, f"{t.nastepne - d0:.0f}")
sprawdz("powód w logu", any("walka" in l for l in logi))
for _ in range(5):
    z.t = t.nastepne; t.tick()
sprawdz("wielokrotne odroczenie nie kolejkuje", not wywolania and t.wyslane == 0 and t.porazki == 0)
powody.clear(); z.t = t.nastepne
sprawdz("po ustaniu warunków jedno ogłoszenie", t.tick() == "wyslane" and len(wywolania) == 1)
z.t += 1
sprawdz("brak drugiego tuż po", t.tick() is None and len(wywolania) == 1)

# --- brak run UH ----------------------------------------------------------------------------
wywolania.clear()
t, z, logi = planista(uh_ile=lambda: 19)
z.t = t.nastepne
sprawdz("19 run UH: nie ogłasza", t.tick() == "brak_uh" and not wywolania)
t, z, logi = planista(uh_ile=lambda: 20)
z.t = t.nastepne
sprawdz("20 run UH: ogłasza 1 BP", t.tick() == "wyslane" and "1 bp" in wywolania[0], str(wywolania))
wywolania.clear()
t, z, logi = planista(uh_ile=lambda: None)
z.t = t.nastepne
sprawdz("brak odczytu kontenerów: odroczenie, nie wysyła", t.tick() == "odroczone" and not wywolania)
wywolania.clear()
t, z, logi = planista(konf(TRADE_MIN_UH=50), uh_ile=lambda: 40)
z.t = t.nastepne
sprawdz("TRADE_MIN_UH=50, 40 run: nie ogłasza", t.tick() == "brak_uh" and not wywolania)
t, z, logi = planista(konf(TRADE_MIN_UH=1))
sprawdz("TRADE_MIN_UH poniżej 20 podniesione do 20", t.ustawienia()[3] == 20)

# --- 3 porażki wyłączają ---------------------------------------------------------------------
wywolania.clear()
alarmy = []
def zla(tekst): wywolania.append(tekst); return False, "weryfikacja zakladki Trade nieudana", True
t, z, logi = planista(wyslij=zla, po_alarmie=alarmy.append)
wyniki = []
for _ in range(3):
    z.t = t.nastepne; wyniki.append(t.tick())
sprawdz("3 porażki: ostatnia = wylaczone", wyniki == ["porazka", "porazka", "wylaczone"] and t.wylaczone, str(wyniki))
sprawdz("ALARM w logu", any("ALARM" in l for l in logi))
z.t += 5000
sprawdz("po wyłączeniu nic nie wysyła", t.tick() is None and len(wywolania) == 3)
# sukces w środku zeruje licznik
seria = iter([(False, "x", True), (False, "x", True), (True, "", True), (False, "x", True), (False, "x", True)])
t, z, logi = planista(wyslij=lambda tk: next(seria))
for _ in range(5):
    z.t = t.nastepne; t.tick()
sprawdz("sukces zeruje licznik porażek (bez wyłączenia)", not t.wylaczone and t.porazki == 2)
# nie wróciliśmy na Default -> wyłączone natychmiast
alarmy.clear()
t, z, logi = planista(wyslij=lambda tk: (True, "", False), po_alarmie=alarmy.append)
z.t = t.nastepne
sprawdz("brak powrotu na Default: wyłączone + alarm", t.tick() == "wylaczone" and t.wylaczone and alarmy)
# wyjątek wysyłki = porażka
def wyjatek(tk): raise RuntimeError("x11")
t, z, logi = planista(wyslij=wyjatek)
z.t = t.nastepne
sprawdz("wyjątek wysyłki = porażka", t.tick() == "porazka" and t.porazki == 1)
# STOP przepuszczony
def stop(tk): raise bot.Zatrzymano("plik STOP")
t, z, logi = planista(wyslij=stop)
z.t = t.nastepne
try:
    t.tick(); przepuszczony = False
except bot.Zatrzymano:
    przepuszczony = True
sprawdz("Zatrzymano (STOP) nie jest połykane", przepuszczony)

# --- zakładki: klasyfikacja zrzutu ----------------------------------------------------------
sprawdz("realny zrzut: Default aktywna, Trade nieaktywna", mozg.stan_zakladek(DEFAULT) == {"Default": "aktywna", "Trade": "nieaktywna"},
        str(mozg.stan_zakladek(DEFAULT)))
sprawdz("syntetyczny: Trade aktywna, Default nieaktywna", mozg.stan_zakladek(TRADE) == {"Default": "nieaktywna", "Trade": "aktywna"},
        str(mozg.stan_zakladek(TRADE)))
sprawdz("czarny obraz: brak", set(mozg.stan_zakladek(Image.new("RGB", (734, 910))).values()) == {"brak"})
duzy = DEFAULT.resize((1468, 1820), Image.NEAREST)
sprawdz("pozycje względem rozmiaru ekranu (2x)", mozg.stan_zakladek(duzy) == {"Default": "aktywna", "Trade": "nieaktywna"})

# --- wyslij_na_trade: przebieg z atrapą ekranu ----------------------------------------------
class Ekran:
    def __init__(s, dziala=True, start="Default", trzymany=False, wyjatek=False, wrocic=True):
        s.akt, s.dziala, s.zdarzenia, s.trzymany, s.wyjatek, s.wrocic = start, dziala, [], trzymany, wyjatek, wrocic
    def zrzut(s): return TRADE if s.akt == "Trade" else DEFAULT
    def kliknij(s, n):
        s.zdarzenia.append(("klik", n))
        if n == "Trade" and not s.dziala: return
        if n == "Default" and not s.wrocic: return
        s.akt = n
    def wpisz(s, t):
        s.zdarzenia.append(("wpisz", t, s.akt))
        if s.wyjatek: raise RuntimeError("X zerwany")
        return True
    def go(s):
        return mozg.wyslij_na_trade("[sell] 2 bp [uh] 2.4k each", zrzut=s.zrzut, kliknij=s.kliknij,
                                     rusz_mysz=lambda: s.zdarzenia.append(("mysz",)), wpisz=s.wpisz,
                                     anuluj=lambda: s.zdarzenia.append(("escape",)), puszczone=lambda: not s.trzymany,
                                     spij=lambda x: None)
e = Ekran(); w = e.go()
sprawdz("przebieg: klik Trade, weryfikacja, wpis NA Trade, powrót na Default",
        w == (True, "", True) and [x for x in e.zdarzenia if x[0] != "mysz"] ==
        [("klik", "Trade"), ("wpisz", "[sell] 2 bp [uh] 2.4k each", "Trade"), ("klik", "Default")] and e.akt == "Default", str(e.zdarzenia))
e = Ekran(dziala=False); w = e.go()
sprawdz("brak weryfikacji zakładki: NIE wpisuje", not w[0] and not any(x[0] == "wpisz" for x in e.zdarzenia), str(w))
e = Ekran(trzymany=True); w = e.go()
sprawdz("klawisz ruchu trzymany: nic nie robi", not w[0] and not e.zdarzenia, str(w))
e = Ekran(start="Trade"); w = e.go()
sprawdz("Trade już aktywna: bez kliku w Trade, wpis, powrót", w[0] and ("klik", "Trade") not in e.zdarzenia and e.akt == "Default")
e = Ekran(wyjatek=True); w = e.go()
sprawdz("wyjątek w trakcie pisania: Escape + powrót na Default", not w[0] and ("escape",) in e.zdarzenia and e.akt == "Default", str(w))
e = Ekran(wrocic=False); w = e.go()
sprawdz("brak powrotu na Default raportowany", w[0] and w[2] is False, str(w))
class Czarny(Ekran):
    def zrzut(s): return Image.new("RGB", (734, 910))
e = Czarny(); w = e.go()
sprawdz("zakładki nierozpoznane: nic nie klika ani nie wpisuje", not w[0] and not e.zdarzenia, str(w))

# --- szablon: hot reload, fallback, ASCII, 80 znaków ----------------------------------------
p = tmp / "szablon.txt"
p.write_text("[SELL] {bp} BP [UH] 2.4k each\n", encoding="utf-8")
sprawdz("szablon domyślny z pliku", mozg.tresc_ogloszenia(45, p) == ("[sell] 2 bp [uh] 2.4k each", "plik"), str(mozg.tresc_ogloszenia(45, p)))
sprawdz("{bp} = floor(run/20), min 1", [mozg.tresc_ogloszenia(n, p)[0].split()[1] for n in (20, 39, 40, 100)] == ["1", "1", "2", "5"])
p.write_text("WTS {bp} backpack UH cheap\n", encoding="utf-8")
sprawdz("hot reload: nowa treść bez restartu", mozg.tresc_ogloszenia(60, p) == ("wts 3 backpack uh cheap", "plik"))
sprawdz("brak pliku: fallback do domyślnego", mozg.tresc_ogloszenia(60, tmp / "nie_ma.txt") == ("[sell] 3 bp [uh] 2.4k each", "domyslny"))
for nazwa, tresc in (("pusty", "\n"), ("polskie znaki", "sprzedam zażółć {bp} bp\n"), ("za długi", "x" * 81 + "\n"),
                     ("nieznane pole", "sell {ile} bp\n"), ("wiele linii", "a {bp}\nb\n"), ("komenda", "/pm {bp}\n")):
    p.write_text(tresc, encoding="utf-8")
    sprawdz(f"niepoprawny szablon ({nazwa}): fallback", mozg.tresc_ogloszenia(60, p) == ("[sell] 3 bp [uh] 2.4k each", "domyslny"))
p.write_bytes(b"\xff\xfe sell")
sprawdz("szablon nie-UTF8: fallback", mozg.tresc_ogloszenia(60, p)[1] == "domyslny")
p.write_text("a" * 80 + "\n", encoding="utf-8")
sprawdz("dokładnie 80 znaków przechodzi", len(mozg.tresc_ogloszenia(60, p)[0]) == 80)
for n in (20, 99, 100, 999, 100000):
    tk = mozg.tresc_ogloszenia(n, tmp / "nie_ma.txt")[0]
    sprawdz(f"tekst ASCII <= 80 i bezpieczny ({n} run)", tk.isascii() and len(tk) <= 80 and mozg.bezpieczna_wiadomosc(tk)[0], tk)

# --- policz_uh, atak_pk ---------------------------------------------------------------------
kont = [{"nazwa": "Backpack", "przedmioty": [{"id": 3160, "ilosc": 12}, {"id": 3147, "ilosc": 1}, {"id": 3160}]},
        {"nazwa": "Purple Backpack", "przedmioty": [{"id": 3160, "ilosc": 20}]},
        {"nazwa": "Dead Troll", "przedmioty": [{"id": 3160, "ilosc": 5}]}]
sprawdz("policz_uh: plecaki tak, zwłoki nie", mozg.policz_uh(kont) == 33, str(mozg.policz_uh(kont)))
sprawdz("policz_uh: brak odczytu = None", mozg.policz_uh([]) is None and mozg.policz_uh(None) is None)
sprawdz("atak_pk: gracz/PK", mozg.atak_pk("You lose 10 hitpoints due to an attack by Bob.") and mozg.atak_pk("Bob has a red skull")
        and mozg.atak_pk("PK!!"))
sprawdz("atak_pk: potwór/zwykły czat nie", not mozg.atak_pk("You lose 4 hitpoints due to an attack by a rat.")
        and not mozg.atak_pk("exura") and not mozg.atak_pk("[sell] 2 bp [uh]"))

# --- Mozg.trade_spokoj: te same warunki co czat + zaostrzone --------------------------------
def mozg_z(bez_ruchu=False, **cbk):
    z = Zegar(5000.0)
    cb = types.SimpleNamespace(stan="IDZ", cel=None, ucieczka=False, ostrozny=False, w_poscigu=False, w_lootcie=False,
                               lww=None, lww_zalegle=None, wypad_aktywny=False, dojscie_aktywne=False, wyprawa=None,
                               uh_tryb_walki=False, uh_hold_od=None, wstrzymany_do=None,
                               ostatni_gracz=(z(), {"hp": 160, "max_hp": 200}),
                               odczyt_stworow=(z(), [{"nazwa": "Ja", "gracz": True, "x": 100, "y": 100, "z": 8}]),
                               postac=types.SimpleNamespace(ekran=None))
    for k, v in cbk.items(): setattr(cb, k, v)
    m = mozg.Mozg("hybryda", zapytaj=lambda q: {}, nazwa="Ja", model=lambda p: ("", {}), cb=cb,
                  pamiec=mozg.Pamiec(tmp / "pamiec.json"), log=lambda *a: None, zegar=z, czat_wyslij=lambda t: None,
                  trasy=lambda: [], losuj=lambda a, b: a, bez_ruchu=bez_ruchu)
    m._trade_z = (8, -1e9)
    return m, cb, z
m, cb, z = mozg_z()
sprawdz("spokój: wszystko w porządku -> wolno", m.trade_spokoj() == "", m.trade_spokoj())
for nazwa, mod in (("stan WALKA", dict(stan="WALKA")), ("cel", dict(cel=object())), ("ucieczka", dict(ucieczka=True)),
                   ("HP 60%", dict(ostatni_gracz=(5000.0, {"hp": 120, "max_hp": 200}))),
                   ("HP 69%", dict(ostatni_gracz=(5000.0, {"hp": 138, "max_hp": 200}))),
                   ("loot", dict(w_lootcie=True)), ("wypad", dict(wypad_aktywny=True)),
                   ("wyprawa", dict(wyprawa=types.SimpleNamespace(aktywny=True))), ("UH", dict(uh_hold_od=1.0)),
                   ("pauza", dict(wstrzymany_do=9999.0)),
                   ("potwór 5 pól", dict(odczyt_stworow=(5000.0, [{"nazwa": "Ja", "gracz": True, "x": 100, "y": 100, "z": 8},
                                                                  {"nazwa": "Rat", "gracz": False, "x": 105, "y": 100, "z": 8, "hp": 100}]))),
                   ("obcy gracz 8 pól", dict(odczyt_stworow=(5000.0, [{"nazwa": "Ja", "gracz": True, "x": 100, "y": 100, "z": 8},
                                                                      {"nazwa": "Bob", "gracz": True, "x": 108, "y": 92, "z": 8}]))),
                   ("stary odczyt", dict(odczyt_stworow=(4000.0, [{"nazwa": "Ja", "gracz": True, "x": 100, "y": 100, "z": 8}])))):
    m, cb, z = mozg_z(**mod)
    sprawdz(f"odroczenie: {nazwa}", m.trade_spokoj() != "", m.trade_spokoj())
m, cb, z = mozg_z(odczyt_stworow=(5000.0, [{"nazwa": "Ja", "gracz": True, "x": 100, "y": 100, "z": 8},
                                           {"nazwa": "Bob", "gracz": True, "x": 109, "y": 100, "z": 8},
                                           {"nazwa": "Rat", "gracz": False, "x": 110, "y": 100, "z": 8, "hp": 100}]))
sprawdz("obcy gracz 9 pól i potwór 10 pól: wolno", m.trade_spokoj() == "", m.trade_spokoj())
m, cb, z = mozg_z()
m.czat.atak_ts = z() - 30
sprawdz("odroczenie: atak/PK 30 s temu", "atak" in m.trade_spokoj())
m.czat.atak_ts = z() - 61
sprawdz("po 60 s od ataku wolno", m.trade_spokoj() == "")
m.alarm_gm = True
sprawdz("alarm_gm blokuje", m.trade_spokoj() != "")
m, cb, z = mozg_z(); m.zalegly_czat = ("hej", z() + 5)
sprawdz("zaległa odpowiedź na Default blokuje", m.trade_spokoj() != "")
m, cb, z = mozg_z(); m.czat.wyslane_czasy.append(z() - 5)
sprawdz("świeża odpowiedź na Default blokuje (30 s)", m.trade_spokoj() != "")
m, cb, z = mozg_z(); m.cb = None
sprawdz("doradca (bez cavebota): nigdy", m.trade_spokoj() != "")
# integracja: pokrętło domyślnie 0 -> obieg_hybrydy nie wysyła i niczego nie ryzykuje
m, cb, z = mozg_z()
m.trade.wyslij = zakaz
z.t += 10000
m.trade_tick()
sprawdz("Mozg: pokrętło 0 -> trade_tick nic nie wysyła", m.trade.wyslane == 0)

# --- tryb --bez-ruchu (16.10): postać stoi w depo, cb.tick() nie działa -> pomijamy warunki walki/ruchu/HP ---------
ZLE = dict(stan="WALKA", cel=object(), ucieczka=True, ostatni_gracz=(1.0, {"hp": 10, "max_hp": 200}),
           odczyt_stworow=(1.0, [{"nazwa": "Bob", "gracz": True, "x": 1, "y": 1, "z": 8}]))
m, cb, z = mozg_z(bez_ruchu=True, **ZLE)
m.czat.atak_ts = z() - 5
sprawdz("bez ruchu: walka/HP/odczyt/atak PK nie blokują", m.trade_spokoj() == "", m.trade_spokoj())
sprawdz("bez ruchu: priv_spokoj też wolno", m.priv_spokoj() == "", m.priv_spokoj())
m, cb, z = mozg_z(bez_ruchu=False, **ZLE)
m.czat.atak_ts = z() - 5
sprawdz("z ruchem: te same warunki nadal blokują", m.trade_spokoj() != "", m.trade_spokoj())
m, cb, z = mozg_z(bez_ruchu=True, **ZLE); m.alarm_gm = True
sprawdz("bez ruchu: alarm_gm nadal blokuje", m.trade_spokoj() == "alarm_gm")
m, cb, z = mozg_z(bez_ruchu=True, **ZLE); m.czat.zablokowany = True
sprawdz("bez ruchu: czat zablokowany nadal blokuje", m.trade_spokoj() != "")
m, cb, z = mozg_z(bez_ruchu=True, **ZLE); m.zalegly_czat = ("hej", z() + 5)
sprawdz("bez ruchu: zaległa odpowiedź na Default blokuje", m.trade_spokoj() != "")
m, cb, z = mozg_z(bez_ruchu=True, **ZLE); m.rozmowa_od = z()
sprawdz("bez ruchu: rozmowa w toku blokuje", m.trade_spokoj() != "")
m, cb, z = mozg_z(bez_ruchu=True, **ZLE); m.czat.wyslane_czasy.append(z() - 5)
sprawdz("bez ruchu: świeża odpowiedź na Default blokuje", m.trade_spokoj() != "")
m, cb, z = mozg_z(bez_ruchu=True, **ZLE); m.cb = None
sprawdz("bez ruchu: doradca (bez cavebota) nadal nigdy", m.trade_spokoj() != "")
# bez UH: ogłoszenie ze stałej wartości, bez odczytu kontenerów i bez progu TRADE_MIN_UH
wywolania.clear()
t, z, logi = planista(konf(TRADE_MIN_UH=500), uh_ile=lambda: 1 / 0, bez_uh=True)
z.t = t.nastepne
sprawdz("bez UH: wysyła bez odczytu kontenerów i progu", t.tick() == "wyslane" and len(wywolania) == 1, str(logi))
sprawdz("bez UH: tekst ze stałej (2 bp)", "2 bp" in wywolania[0], str(wywolania))
sprawdz("bez UH: log bez liczby run", any("bez UH" in l and "wysłano" in l for l in logi), str(logi))
wywolania.clear()
t, z, logi = planista(konf(TRADE_MIN_UH=500), uh_ile=lambda: 40)
z.t = t.nastepne
sprawdz("z UH (domyślnie): próg nadal obowiązuje", t.tick() == "brak_uh" and not wywolania)
t, z, logi = planista(bez_uh=True, wyslij=zla)
z.t = t.nastepne
sprawdz("bez UH: integralność wysyłki (porażka liczona)", t.tick() == "porazka" and t.porazki == 1)
sprawdz("Mozg: bez_ruchu włącza bez_uh w planiście", mozg_z(bez_ruchu=True)[0].trade.bez_uh is True
        and mozg_z()[0].trade.bez_uh is False)

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
