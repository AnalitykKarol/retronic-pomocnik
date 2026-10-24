"""Marsz klikiem (marsz_klik.py) i auto-refill po dojściu do depo (refill_auto.py), 20.10: jednostki, pole panelu i skrypty
(refill.sh --przerwij, wroc.sh --anuluj) w atrapie katalogu. Nic nie dotyka gry, bota ani żywych instancji (własne RETRONIC_ID).
Wymaga bash, setsid. Część „Wyprawa → decyzja” jest w test_wyprawa.py (sekcja 20)."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
_os.environ["RETRONIC_ID"] = "tstwroc"                # unikalne ID: pidy/ubijanie nie dotykają prawdziwych instancji
import json, shutil, socket, subprocess, sys, tempfile, time
from pathlib import Path
sys.dont_write_bytecode = True
KAT = Path(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
sys.path.insert(0, str(KAT))
import instancja
import marsz_klik
import panel
import refill_auto

ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, "" if warunek else info)

# ---------------------------------------------------------------- 1. marsz_klik: koszt pola, najdalsze pole, klik i czekanie
class Mapa:
    def __init__(self, nad=None): self.nad = nad or {}
    def flagi(self, x, y, z): return self.nad.get((x, y, z), 1 if z in (6, 7, 8) else 0)
M = Mapa({(5, 5, 7): 1 | 4, (6, 5, 7): 0, (7, 5, 7): 3, (7, 5, 6): 2, (9, 5, 7): 3, (20, 20, 7): 3})   # (7,5) schody, (9,5) i (20,20) krzesła
k = lambda x, y, z=7: marsz_klik.koszt_pola(M, x, y, z)
sprawdz("1a zwykłe pole = 1.0", k(1, 1) == 1.0)
sprawdz("1b flaga blokady (4) i brak flagi chodliwości = None", k(5, 5) is None and k(6, 5) is None)
sprawdz("1c schody (flaga 2 z odpowiednikiem flagi 2 na piętrze obok) = None", k(7, 5) is None)
sprawdz("1d pole z flagą 2 bez odpowiednika (krzesło) = 6.0 (nie zwykłe: marsz klikiem go nie klika)", k(20, 20) == 6.0 and k(9, 5) == 6.0)
sprawdz("1e pole docelowe zawsze 1.0, pole z listy unik = None",
        marsz_klik.koszt_pola(M, 5, 5, 7, cel=(5, 5)) == 1.0 and marsz_klik.koszt_pola(M, 1, 1, 7, unik={(1, 1)}) is None)
sc = [(1 + i, 1, 7) for i in range(10)]
sprawdz("1f dalej_klik: zwykła ścieżka = KLIK_MAKS_POL", marsz_klik.dalej_klik(sc, lambda x, y, z: 1.0, 7) == marsz_klik.KLIK_MAKS_POL == 5)
sprawdz("1g dalej_klik: krótka ścieżka kończy się na ostatnim polu", marsz_klik.dalej_klik(sc[:3], lambda x, y, z: 1.0, 7) == 2)
sprawdz("1h dalej_klik: niezwykłe pole nr 3 skraca do 2", marsz_klik.dalej_klik(sc, lambda x, y, z: None if x == 4 else 1.0, 7) == 2)
sprawdz("1i dalej_klik (serwis): pole nr 1 niezwykłe nie blokuje (plan Dijkstry dopuszcza w nim pole z kosztem 6)",
        marsz_klik.dalej_klik(sc, lambda x, y, z: 6.0 if x == 2 else 1.0, 7) == 5)
# gęsta ścieżka i prostokąt z marginesem (wyprawa)
sprawdz("1i2 gesta_sciezka: punkty co 2 pola zagęszczone do sąsiednich pól, najwyżej KLIK_MAKS_POL",
        marsz_klik.gesta_sciezka((10, 10, 7), [(10, 10, 7), (12, 10, 7), (14, 10, 7), (16, 10, 7)]) == [(11, 10), (12, 10), (13, 10), (14, 10), (15, 10)])
sprawdz("1i3 gesta_sciezka: skos, zmiana piętra i wyjście poza zasięg widoku kończą ścieżkę",
        marsz_klik.gesta_sciezka((10, 10, 7), [(12, 12, 7), (13, 13, 7)]) == [(11, 11), (12, 12), (13, 13)]
        and marsz_klik.gesta_sciezka((10, 10, 7), [(11, 10, 7), (12, 10, 6)]) == [(11, 10)]
        and marsz_klik.gesta_sciezka((10, 10, 7), [(25, 10, 7)]) == [(11, 10), (12, 10), (13, 10), (14, 10), (15, 10)]
        and marsz_klik.gesta_sciezka((10, 10, 7), [(11, 10, 7), (30, 10, 7)], maks=50)[-1] == (16, 10))
pk = lambda p, pola: marsz_klik.prostokat_czysty(M, p, pola)
sprawdz("1i4 prostokat_czysty: flaga 2 (schody) w prostokącie ścieżki z marginesem 1 = nieczysty; bez niej czysty (blokada 4 to nie flaga 2)",
        not pk((6, 6, 7), [(7, 6)]) and pk((1, 1, 7), [(2, 1), (3, 1)]) and pk((1, 4, 7), [(2, 4), (3, 4)]))
sprawdz("1i5 ile_pol_klik: 4 zwykłe pola = 4; schody w marginesie skracają do 0 (poniżej 2 pól); krzesło (koszt 6) na ścieżce też",
        marsz_klik.ile_pol_klik(M, (1, 1, 7), [(2, 1), (3, 1), (4, 1), (5, 1)]) == 4
        and marsz_klik.ile_pol_klik(M, (4, 6, 7), [(5, 6), (6, 6), (7, 6)]) == 0
        and marsz_klik.ile_pol_klik(M, (3, 6, 7), [(4, 6), (5, 6)]) == 2
        and marsz_klik.ile_pol_klik(M, (17, 20, 7), [(18, 20), (19, 20), (20, 20)]) == 0)

class Sw:
    """Czas wirtualny i postać: lista pozycji zwracanych kolejnym odczytom (ostatnia się powtarza)."""
    def __init__(self, pozycje, przerwij_na=None):
        self.t, self.p, self.i = 0.0, list(pozycje), 0
    def monotonic(self): return self.t
    def time(self): return self.t
    def sleep(self, s): self.t += s
    def pozycja(self):
        v = self.p[min(self.i, len(self.p) - 1)]; self.i += 1; return v
P0, CEL = (10, 10, 7), (15, 10, 7)
def kc(pozycje, **kw):
    sw = Sw(pozycje); logi = []
    r = marsz_klik.klik_i_czekaj(sw, P0, CEL, 5, zegar=sw, log=logi.append, **kw)
    return r, logi
sprawdz("1j dojście do pola kliku = ruch", kc([(11, 10, 7), (13, 10, 7), (15, 10, 7), (15, 10, 7)])[0] == "ruch")
r, lg = kc([(10, 10, 7), (10, 10, 6)])
sprawdz("1k zmiana piętra po kliku = pietro (z logiem z prefiksem)", r == "pietro" and lg and lg[0].startswith("marsz klikiem:"), (r, lg))
sprawdz("1l postać stoi cały czas = bez_ruchu", kc([P0])[0] == "bez_ruchu")
sprawdz("1m ruszyła i stanęła (4 odczyty bez zmiany) = ruch", kc([(11, 10, 7)])[0] == "ruch")
r, lg = kc([(11, 10, 7), (12, 10, 7), (12, 10, 7), (13, 10, 7), (14, 10, 7)], przerwij=lambda p: p[0] >= 13)
sprawdz("1n przerwij() zwraca True = przerwano (sprawdzane co 3. odczyt)", r == "przerwano", (r, lg))
r, lg = kc([(11, 10, 7), (12, 10, 7), (13, 10, 7), (14, 10, 7), (15, 10, 7)], przerwij=lambda p: False)
sprawdz("1o przerwij() zwraca False = marsz trwa do pola kliku", r == "ruch")

# ---------------------------------------------------------------- 2. refill_auto: decyzja, czekacz, anulowanie
EDRON_DEPO, EDRON_ULICA, THAIS, ROOK = (33173, 31796, 8), (33170, 31810, 7), (32366, 32215, 7), (32097, 32219, 7)
THAIS_DEPO = (32348, 32225, 7)          # przybycie wyprawy do depo Thais (start trasy depo_troll_cave)
tmp = Path(tempfile.mkdtemp(prefix="test_wroc_refill_auto_"))
stan = tmp / "stan"; stan.mkdir()
def cz(): return refill_auto.czytaj_stan(stan)
def czysc():
    for f in stan.iterdir(): f.unlink()
nic = lambda wzor, **kw: []
starty = []
sprawdz("2a miasto_serwisu: depo Edron = (edron, w depo)", refill_auto.miasto_serwisu(EDRON_DEPO) == ("edron", True))
sprawdz("2b ulica Edron = (edron, nie w depo); depo Thais = (thais, w depo), ulica Thais = (thais, nie w depo) (22.10); Rook, brak = (None, False)",
        refill_auto.miasto_serwisu(EDRON_ULICA) == ("edron", False)
        and refill_auto.miasto_serwisu(THAIS_DEPO) == ("thais", True) and refill_auto.miasto_serwisu(THAIS) == ("thais", False)
        and all(refill_auto.miasto_serwisu(p) == (None, False) for p in (ROOK, (0, 0, 7))))
r = refill_auto.zlec(EDRON_DEPO, stan, start=lambda: starty.append(1), procesy=nic)
sprawdz("2c depo Edron, nic nie trwa: start czekacza raz, decyzja czeka", r[0] == "czeka" and starty == [1] and cz()["stan"] == "czeka", (r, starty))
czysc(); starty.clear()
r = refill_auto.zlec(ROOK, stan, start=lambda: starty.append(1), procesy=nic)
sprawdz("2d Rook: brak_planu, czytelny powód (miasto, pozycja, które miasta mają plan), start NIE rusza",
        r[0] == "brak_planu" and starty == [] and "brak planu serwisu" in cz()["powod"] and "edron" in cz()["powod"]
        and "thais" in cz()["powod"] and "32097" in cz()["powod"], (r, cz()))
czysc()
r = refill_auto.zlec(THAIS_DEPO, stan, start=lambda: starty.append(1), procesy=nic)
sprawdz("2d2 depo Thais, nic nie trwa: start czekacza raz, decyzja czeka (22.10: Thais ma plan serwisu)",
        r[0] == "czeka" and starty == [1] and cz()["stan"] == "czeka" and "thais" in cz()["powod"], (r, starty, cz()))
czysc(); starty.clear()
r = refill_auto.zlec(THAIS, stan, start=lambda: starty.append(1), procesy=nic)
sprawdz("2d3 ulica Thais (poza depo): pominiety, start nie rusza", r[0] == "pominiety" and starty == [] and "depo thais" in cz()["powod"], (r, cz()))
czysc()
r = refill_auto.zlec(EDRON_ULICA, stan, start=lambda: starty.append(1), procesy=nic)
sprawdz("2e Edron, ale poza depo: pominiety, start nie rusza", r[0] == "pominiety" and starty == [] and "depo" in cz()["powod"], r)
czysc()
(stan / "STOP_RECZNY").touch()
r = refill_auto.zlec(EDRON_DEPO, stan, start=lambda: starty.append(1), procesy=nic)
sprawdz("2f STOP_RECZNY: pominiety (pierwszeństwo człowieka), start nie rusza", r[0] == "pominiety" and starty == [] and "ręczny" in cz()["powod"], r)
czysc()
for nazwa, wzor_ok in (("serwis.py", lambda w: "serwis" in w), ("refill.sh", lambda w: "refill" in w), ("czekacz", lambda w: "czekaj" in w)):
    r = refill_auto.zlec(EDRON_DEPO, stan, start=lambda: starty.append(1), procesy=lambda w, **kw: [99] if wzor_ok(w) else [])
    sprawdz(f"2g {nazwa} już trwa: pominiety, drugi nie rusza", r[0] == "pominiety" and starty == [], r)
    czysc()
r = refill_auto.zlec(EDRON_DEPO, stan, start=lambda: (_ for _ in ()).throw(OSError("x")), procesy=nic)
sprawdz("2h błąd startu czekacza: pominiety z powodem, bez wyjątku", r[0] == "pominiety" and "nie udało się" in r[1], r)
czysc()

# czekacz z atrapami
class Proc:
    """procesy(): bot „żyje” przez n wywołań, serwis/refill wg flag; zapisuje kolejność wywołań uruchom()."""
    def __init__(self, bot_n=2, serwis=False): self.n, self.serwis, self.wyw = bot_n, serwis, []
    def __call__(self, wzor, **kw):
        if "mozg" in wzor:
            self.n -= 1; return [7] if self.n >= 0 else []
        return [8] if self.serwis and ("serwis" in wzor or "refill" in wzor) else []
def uruchom_atrapa(wyw, rc=0, out=""):
    def u(cmd, **kw):
        wyw.append(cmd)
        return subprocess.CompletedProcess(cmd, rc if "refill.sh" in " ".join(map(str, cmd)) else 0, out, out)
    return u
def czekaj_t(proc, rc=0, out="", czekaj_s=60.0, przed=None, **kw):
    czysc(); wyw = []; t = [0.0]
    if przed: przed()
    kod = refill_auto.czekaj(stan, procesy=proc, uruchom=uruchom_atrapa(wyw, rc, out), spij=lambda s: t.__setitem__(0, t[0] + s),
                             zegar=lambda: t[0], czekaj_s=czekaj_s, **kw)
    return kod, wyw
kod, wyw = czekaj_t(Proc(bot_n=3))
kom = [" ".join(map(str, c)) for c in wyw]
sprawdz("2i czekacz: po zniknięciu bota zwalnia wejście, potem refill.sh --tlo; decyzja uruchomiony",
        kod == 0 and len(kom) == 2 and "zwolnij_wejscie.py" in kom[0] and kom[1].endswith("refill.sh --tlo") and cz()["stan"] == "uruchomiony", (kod, kom, cz()))
kod, wyw = czekaj_t(Proc(bot_n=3), przed=lambda: (stan / "STOP_RECZNY").touch())
sprawdz("2j STOP_RECZNY pojawił się w trakcie czekania: refill nie rusza, pominiety", kod == 0 and wyw == [] and cz()["stan"] == "pominiety", (kod, wyw, cz()))
kod, wyw = czekaj_t(Proc(bot_n=3, serwis=True))
sprawdz("2k serwis wystartował w międzyczasie: refill nie rusza", wyw == [] and cz()["stan"] == "pominiety", (wyw, cz()))
kod, wyw = czekaj_t(Proc(bot_n=10 ** 6), czekaj_s=5.0)
sprawdz("2l bot nie zatrzymał się w limicie: rezygnacja (kod 1), nic nie ubijamy ani nie startujemy", kod == 1 and wyw == [] and cz()["stan"] == "pominiety", (kod, wyw, cz()))
kod, wyw = czekaj_t(Proc(bot_n=1), rc=1, out="bot działa (pid 5), zatrzymaj: ./zatrzymaj.sh")
sprawdz("2m refill.sh odmówił: pominiety z jego komunikatem, kod odmowy", kod == 1 and cz()["stan"] == "pominiety" and "bot działa" in cz()["powod"], (kod, cz()))

# zostan_w_depo (23.10, Karol): flaga w instancje/_wspolne/plan_postaci.json wyłącza auto-refill, także gdy WROC_REFILL=1 wrócił z trybu runy/uh
inst_root = tmp / "instancje"; (inst_root / "_wspolne").mkdir(parents=True)
plan_plik = inst_root / "_wspolne" / "plan_postaci.json"
plan_plik.write_text(json.dumps({"postacie": {"geb": {"zostan_w_depo": True, "zostan_w_depo_powod": "Karol 23.10"}, "inna": {"kroki": []}}}))
st_geb, st_inna = inst_root / "geb", inst_root / "inna"; st_geb.mkdir(); st_inna.mkdir()
starty.clear()
sprawdz("2n zostaje_w_depo: flaga czytana z planu (powód), brak flagi / brak wpisu = None",
        refill_auto.zostaje_w_depo(st_geb) == "Karol 23.10" and refill_auto.zostaje_w_depo(st_inna) is None
        and refill_auto.zostaje_w_depo(inst_root / "nieznana") is None)
r = refill_auto.zlec(THAIS_DEPO, st_geb, start=lambda: starty.append(1), procesy=nic)
sprawdz("2o postać z zostan_w_depo w depo Thais: pominiety, czekacz NIE rusza (mimo WROC_REFILL=1)",
        r[0] == "pominiety" and starty == [] and "zostan_w_depo" in r[1] and refill_auto.czytaj_stan(st_geb)["stan"] == "pominiety", (r, starty))
r = refill_auto.zlec(THAIS_DEPO, st_inna, start=lambda: starty.append(1), procesy=nic)
sprawdz("2p postać bez flagi: jak dotąd czeka i startuje czekacza", r[0] == "czeka" and starty == [1], (r, starty))
starty.clear()
plan_plik.write_text("{zepsute")
r = refill_auto.zlec(THAIS_DEPO, st_geb, start=lambda: starty.append(1), procesy=nic)
sprawdz("2q plan nieczytelny: strażnik nic nie wymyśla (jak przed flagą)", r[0] == "czeka" and starty == [1], (r, starty))
plan_plik.write_text(json.dumps({"postacie": {"geb": {"zostan_w_depo": True}}}))
t = [0.0]; wyw_k = []
kod_k = refill_auto.czekaj(st_geb, procesy=Proc(bot_n=1), uruchom=uruchom_atrapa(wyw_k), spij=lambda s_: t.__setitem__(0, t[0] + s_), zegar=lambda: t[0])
sprawdz("2r czekacz zlecony przed flagą: po zniknięciu bota widzi flagę, refill.sh nie rusza",
        kod_k == 0 and wyw_k == [] and refill_auto.czytaj_stan(st_geb)["stan"] == "pominiety", (kod_k, wyw_k, refill_auto.czytaj_stan(st_geb)))

# cooldown: poprzedni start młodszy niż COOLDOWN_S blokuje następny, stary nie; zapis pominięcia nie kasuje ostatniego startu
czysc(); starty.clear()
refill_auto.zapisz_stan(stan, "startuje", "x", teraz=lambda: 1000.0)
refill_auto.zapisz_stan(stan, "uruchomiony", "x", teraz=lambda: 1001.0)
r = refill_auto.zlec(EDRON_DEPO, stan, start=lambda: starty.append(1), procesy=nic, teraz=lambda: 1000.0 + 600)
sprawdz("2h2 cooldown: poprzedni auto-refill ruszył 10 min temu (< 20): pominiety z powodem, czekacz nie rusza",
        r[0] == "pominiety" and starty == [] and "cooldown" in r[1], r)
r = refill_auto.zlec(EDRON_DEPO, stan, start=lambda: starty.append(1), procesy=nic, teraz=lambda: 1000.0 + 900)
sprawdz("2h3 cooldown przetrwał zapis pominięcia (ostatni_start w pliku): nadal blokuje", r[0] == "pominiety" and starty == []
        and cz().get("ostatni_start") == 1000.0, (r, cz()))
r = refill_auto.zlec(EDRON_DEPO, stan, start=lambda: starty.append(1), procesy=nic, teraz=lambda: 1000.0 + 1300)
sprawdz("2h4 po cooldownie (21+ min) auto-refill rusza", r[0] == "czeka" and starty == [1], r)
czysc()

# anuluj
czysc(); ubite = []
n = refill_auto.anuluj(stan, procesy=lambda w, **kw: [31, 32] if "czekaj" in w else [], zabij=lambda p, s: ubite.append(p))
sprawdz("2n anuluj: ubija czekaczy tej instancji i zapisuje powód", n == 2 and ubite == [31, 32] and cz()["stan"] == "pominiety" and "anulowane" in cz()["powod"], (n, ubite, cz()))
czysc()
n = refill_auto.anuluj(stan, procesy=nic, zabij=lambda p, s: ubite.append(p))
sprawdz("2o anuluj bez czekacza: 0 i brak pliku decyzji", n == 0 and cz() == {})
refill_auto.zapisz_stan(stan, "startuje", "wołam refill.sh --tlo")
ubite.clear()
n = refill_auto.anuluj(stan, procesy=lambda w, **kw: [31] if "czekaj" in w else [], zabij=lambda p, s: ubite.append(p))
sprawdz("2o2 czekacz już woła refill.sh (stan startuje): -1, czekacz NIE ubity (komunikat 'refill już ruszył')", n == -1 and ubite == [], (n, ubite))
refill_auto.zapisz_stan(stan, "uruchomiony", "refill.sh --tlo")
n = refill_auto.anuluj(stan, procesy=lambda w, **kw: [41] if "serwis" in w else [], zabij=lambda p, s: ubite.append(p))
sprawdz("2o3 refill trwa (stan uruchomiony, serwis żyje): -1", n == -1 and ubite == [], n)
n = refill_auto.anuluj(stan, procesy=nic, zabij=lambda p, s: ubite.append(p))
sprawdz("2o4 stary wpis 'uruchomiony' po zakończonym refillu (nic nie żyje): zwykłe 'brak oczekującego', 0", n == 0, n)
czysc()

# ---------------------------------------------------------------- 3. panel: pole wroc_refill
logi = stan / "logi"; logi.mkdir()
A = lambda **k: panel.stan_auto_refill(stan, **k)
czysc() if False else None
for f in list(stan.iterdir()):
    if f.is_file(): f.unlink()
sprawdz("3a bez pliku decyzji: None i pusty komunikat", A(serwis_dziala=False, czeka=False) == {"wroc_refill": None, "wroc_refill_komunikat": ""})
refill_auto.zapisz_stan(stan, "czeka", "refill edron ruszy po zatrzymaniu bota")
sprawdz("3b czeka + czekacz żyje = czeka", A(serwis_dziala=False, czeka=True)["wroc_refill"] == "czeka")
sprawdz("3c czeka, czekacza już nie ma, serwis trwa = trwa", A(serwis_dziala=True, czeka=False)["wroc_refill"] == "trwa")
sprawdz("3d czeka, ale nic nie żyje (zerwany) = None", A(serwis_dziala=False, czeka=False)["wroc_refill"] is None)
refill_auto.zapisz_stan(stan, "uruchomiony", "refill.sh --tlo")
sprawdz("3e uruchomiony: trwa tylko dopóki serwis działa (wynik w serwis_wynik)", A(serwis_dziala=True, czeka=False)["wroc_refill"] == "trwa"
        and A(serwis_dziala=False, czeka=False)["wroc_refill"] is None)
refill_auto.zapisz_stan(stan, "brak_planu", "brak planu serwisu dla tego miasta (pozycja (32366, 32215, 7)); serwis ma: edron")
r = A(serwis_dziala=False, czeka=False)
sprawdz("3f brak_planu: pole i komunikat widoczne w panelu", r["wroc_refill"] == "brak_planu" and "brak planu" in r["wroc_refill_komunikat"], r)
refill_auto.zapisz_stan(stan, "pominiety", "ręczny stop (STOP_RECZNY) ma pierwszeństwo")
sprawdz("3g pominiety: widoczny z powodem", A(serwis_dziala=False, czeka=False)["wroc_refill"] == "pominiety")
plik = stan / refill_auto.PLIK
t_dec = json.loads(plik.read_text())["t"]
bl = logi / "mozg-stdout-1020-1200.log"; bl.write_text("Wyprawa: auto-refill pominięty\nZatrzymano (plik STOP).\n")      # bot loguje zaraz po decyzji i przy wyjściu
tl = plik.stat().st_mtime; _os.utime(bl, (tl + 60, tl + 60))
sprawdz("3h decyzja → dopisanie logu bota → panel nadal pokazuje pominięcie (log nie jest startem bota)",
        A(serwis_dziala=False, czeka=False, bot_po=lambda t: False)["wroc_refill"] == "pominiety"
        and A(serwis_dziala=False, czeka=False)["wroc_refill"] == "pominiety")
refill_auto.zapisz_stan(stan, "brak_planu", "brak planu serwisu dla tego miasta (pozycja (32366, 32215, 7)); serwis ma: edron")
sprawdz("3h2 brak_planu też zostaje po dopisaniu logu", A(serwis_dziala=False, czeka=False, bot_po=lambda t: False)["wroc_refill"] == "brak_planu")
sprawdz("3h3 dopiero start bota (proces nowszy niż decyzja) czyści pole", A(serwis_dziala=False, czeka=False, bot_po=lambda t: t > 0)["wroc_refill"] is None)
(stan / refill_auto.PLIK).write_text(json.dumps({"stan": "brak_planu", "powod": "x", "t": time.time() - 100}))      # decyzja sprzed 100 s
orig_pb, orig_cd = panel.procesy_bota, panel.czas_dzialania
try:
    panel.procesy_bota = lambda: [(4242, "mozg.py")]
    panel.czas_dzialania = lambda pid: 1000000                 # proces starszy niż decyzja
    s_stary = A(serwis_dziala=False, czeka=False)["wroc_refill"]
    panel.czas_dzialania = lambda pid: 1                        # proces młodszy niż decyzja (wystartował po niej)
    s_nowy = A(serwis_dziala=False, czeka=False)["wroc_refill"]
finally:
    panel.procesy_bota, panel.czas_dzialania = orig_pb, orig_cd
sprawdz("3h4 prawdziwe sprawdzenie startu z procesu bota: stary proces nie czyści, świeży czyści", s_stary == "brak_planu" and s_nowy is None, (s_stary, s_nowy))
refill_auto.zapisz_stan(stan, "startuje", "wołam refill.sh --tlo")
sprawdz("3h5 stan startuje + serwis działa = trwa", A(serwis_dziala=True, czeka=False)["wroc_refill"] == "trwa")
(stan / refill_auto.PLIK).write_text("{zepsute")
sprawdz("3i zepsuty plik decyzji nie psuje panelu", A(serwis_dziala=False, czeka=False)["wroc_refill"] is None)
sprawdz("3j panel.py --json zawiera pola wroc_refill i wroc_refill_komunikat obok dotychczasowych (addytywnie)",
        all(k_ in json.loads(subprocess.run([sys.executable, "-I", str(KAT / "panel.py"), "--json"], capture_output=True, text=True,
                                            env=dict(_os.environ, RETRONIC_ID="tstwroc"), timeout=30).stdout)
            for k_ in ("wroc_refill", "wroc_refill_komunikat", "wroc_oczekuje", "wroc_w_marszu", "serwis_dziala", "w_miescie", "text")))

# ---------------------------------------------------------------- 4. skrypty w atrapie katalogu: czekacz → refill.sh --tlo, --przerwij, wroc.sh --anuluj
SAND = tmp / "pomocnik"; SAND.mkdir()
for f in ("refill.sh", "wroc.sh", "instancja.py", "refill_auto.py", "zostan_depo.py", "przerwa.py"):
    shutil.copy(KAT / f, SAND / f)
BIN = tmp / "bin"; BIN.mkdir()
(BIN / "notify-send").write_text("#!/bin/bash\necho \"$@\" >> \"%s/powiadomienia.txt\"\n" % tmp); (BIN / "notify-send").chmod(0o755)
(SAND / "zatrzymaj.sh").write_text("#!/bin/bash\neval \"$(python3 -I \"$(dirname \"$0\")/instancja.py\" powloka)\"\nmkdir -p \"$INST_STAN\"; touch \"$INST_STOP\"\n"
                                   "echo zatrzymaj >> \"%s/wywolania.txt\"\n" % tmp)
(SAND / "serwis.sh").write_text("#!/bin/bash\necho \"serwis.sh STARTUJ=$STARTUJ $*\" >> \"%s/wywolania.txt\"\nexit 0\n" % tmp)
(SAND / "zwolnij_wejscie.py").write_text("from pathlib import Path\nopen(%r, 'a').write('zwolnij_wejscie\\n')\n" % str(tmp / "wywolania.txt"))
(SAND / "mozg.py").write_text("import time\ntime.sleep(120)\n")
for f in ("zatrzymaj.sh", "serwis.sh", "refill.sh", "wroc.sh"): (SAND / f).chmod(0o755)
RT = tmp / "rt"; RT.mkdir()
INST = SAND / "instancje" / "tstwroc"
srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
def ENV(**extra):
    e = {k_: v for k_, v in _os.environ.items()}
    e.update(RETRONIC_ID="tstwroc", XDG_RUNTIME_DIR=str(RT), PATH=f"{BIN}:{_os.environ['PATH']}", REFILL_CZEKAJ_STOP_S="1")
    e.update(extra); return e
def czekaj_na(warunek, s=12.0):
    koniec = time.time() + s
    while time.time() < koniec:
        if warunek(): return True
        time.sleep(0.05)
    return warunek()
def pidy(wzor): return subprocess.run([sys.executable, "-I", str(SAND / "instancja.py"), "pidy", wzor], env=ENV(), capture_output=True, text=True).stdout.split()
def start_bota(): return subprocess.Popen(["python3", "-I", str(SAND / "mozg.py")], env=ENV(), start_new_session=True)
def start_czekacza(): return subprocess.Popen([sys.executable, "-I", str(SAND / "refill_auto.py"), "czekaj"], cwd=str(SAND), env=ENV(),
                                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
def stan_pliku():
    try: return json.loads((INST / refill_auto.PLIK).read_text())
    except (OSError, ValueError): return {}
def wyw():
    try: return (tmp / "wywolania.txt").read_text()
    except OSError: return ""
def posprzataj():
    for p in pidy(r"mozg\.py") + pidy(r"refill_auto\.py czekaj"):
        subprocess.run(["kill", "-KILL", p], capture_output=True)
    for f in list(INST.glob("*")):
        if f.is_file(): f.unlink()
    (tmp / "wywolania.txt").unlink(missing_ok=True)
try:
    INST.mkdir(parents=True, exist_ok=True)
    srv.bind(str(RT / "retronic-tstwroc.sock")); srv.listen(1)
    sprawdz("4a bash -n refill.sh i wroc.sh", all(subprocess.run(["bash", "-n", str(KAT / f)]).returncode == 0 for f in ("refill.sh", "wroc.sh")))

    # a. pełny łańcuch: bot stoi → czekacz czeka → bot znika → zwolnienie wejścia → refill.sh --tlo → serwis.sh STARTUJ=1
    bot = start_bota(); time.sleep(0.4)
    cz_ = start_czekacza()
    sprawdz("4b czekacz widoczny dla wzoru pidy (tej instancji), decyzja 'czeka'", czekaj_na(lambda: pidy(r"(^|[ /])refill_auto\.py czekaj") and stan_pliku().get("stan") == "czeka"), stan_pliku())
    time.sleep(1.2)
    sprawdz("4c dopóki bot żyje: refill nie ruszył", "serwis.sh" not in wyw() and cz_.poll() is None)
    bot.kill(); bot.wait()
    sprawdz("4d po zniknięciu bota: zwolnienie wejścia, potem serwis.sh STARTUJ=1 z krokami refillu (pełna lista, brakujące w mieście pomijane)",
            czekaj_na(lambda: "serwis.sh STARTUJ=1 --kroki bank,depo,jedzenie,backpack,blanki,wyjscie --pomin-brakujace" in wyw())
            and "zwolnij_wejscie" in wyw() and wyw().index("zwolnij_wejscie") < wyw().index("serwis.sh"), wyw())
    sprawdz("4e refill.log ma START i OK, decyzja uruchomiony, czekacz zakończył się sam",
            czekaj_na(lambda: "REFILL: OK" in (INST / "refill.log").read_text() if (INST / "refill.log").exists() else False)
            and czekaj_na(lambda: stan_pliku().get("stan") == "uruchomiony") and czekaj_na(lambda: cz_.poll() == 0), stan_pliku())
    posprzataj()

    # b. STOP_RECZNY w trakcie czekania
    bot = start_bota(); time.sleep(0.4); cz_ = start_czekacza()
    czekaj_na(lambda: stan_pliku().get("stan") == "czeka")
    (INST / "STOP_RECZNY").touch()
    bot.kill(); bot.wait()
    sprawdz("4f STOP_RECZNY: czekacz kończy bez refillu, decyzja 'ręczny stop'",
            czekaj_na(lambda: cz_.poll() == 0) and "serwis.sh" not in wyw() and "ręczny" in stan_pliku().get("powod", ""), (wyw(), stan_pliku()))
    posprzataj()

    # c. refill.sh --przerwij w trakcie czekania zabija czekacza
    bot = start_bota(); time.sleep(0.4); cz_ = start_czekacza()
    czekaj_na(lambda: stan_pliku().get("stan") == "czeka")
    r = subprocess.run(["bash", str(SAND / "refill.sh"), "--przerwij"], env=ENV(), capture_output=True, text=True, timeout=30)
    sprawdz("4g refill.sh --przerwij: czekacz ubity (nie 'nic do przerwania'), decyzja anulowana, STOP ustawiony",
            r.returncode == 0 and "nic do przerwania" not in r.stdout and czekaj_na(lambda: cz_.poll() is not None) and "anulowane" in stan_pliku().get("powod", "")
            and (INST / "STOP").exists(), (r.returncode, r.stdout, r.stderr, stan_pliku()))
    bot.kill(); bot.wait(); posprzataj()

    # d2. czekacz już wołał refill.sh (stan uruchomiony, serwis żyje): wroc.sh nie mówi 'anulowany'
    refill_auto_stub = INST / refill_auto.PLIK
    refill_auto_stub.write_text(json.dumps({"stan": "uruchomiony", "powod": "refill.sh --tlo", "t": time.time()}))
    (SAND / "serwis.py").write_text("import time\ntime.sleep(60)\n")
    srv_p = subprocess.Popen(["python3", "-I", str(SAND / "serwis.py"), "edron"], env=ENV(), start_new_session=True)
    time.sleep(0.5)
    r = subprocess.run(["bash", str(SAND / "wroc.sh"), "--anuluj"], env=ENV(), capture_output=True, text=True, timeout=30)
    srv_p.kill(); srv_p.wait()
    sprawdz("4h0 wroc.sh --anuluj gdy refill już ruszył: komunikat 'refill już ruszył: ./refill.sh --przerwij', bez 'auto-refill anulowany'",
            r.returncode == 0 and "refill już ruszył" in r.stdout and "auto-refill anulowany" not in r.stdout, (r.stdout, r.stderr))
    posprzataj()
    # d. wroc.sh --anuluj anuluje oczekujący auto-refill
    bot = start_bota(); time.sleep(0.4); cz_ = start_czekacza()
    czekaj_na(lambda: stan_pliku().get("stan") == "czeka")
    r = subprocess.run(["bash", str(SAND / "wroc.sh"), "--anuluj"], env=ENV(), capture_output=True, text=True, timeout=30)
    sprawdz("4h wroc.sh --anuluj z oczekującym auto-refillem: czekacz ubity, komunikat 'auto-refill anulowany', bez 'brak zlecenia'",
            r.returncode == 0 and "auto-refill anulowany" in r.stdout and "brak zlecenia" not in r.stdout
            and czekaj_na(lambda: cz_.poll() is not None), (r.stdout, r.stderr))
    bot.kill(); bot.wait(); posprzataj()
    r = subprocess.run(["bash", str(SAND / "wroc.sh"), "--anuluj"], env=ENV(), capture_output=True, text=True, timeout=30)
    sprawdz("4i wroc.sh --anuluj bez niczego: jak dotąd 'brak zlecenia', kod 0", r.returncode == 0 and "brak zlecenia" in r.stdout and "auto-refill" not in r.stdout, r.stdout)
    r = subprocess.run(["bash", str(SAND / "refill.sh"), "--przerwij"], env=ENV(), capture_output=True, text=True, timeout=30)
    sprawdz("4j refill.sh --przerwij bez niczego: 'nic do przerwania', bez STOP", r.returncode == 0 and "nic do przerwania" in r.stdout and not (INST / "STOP").exists(), r.stdout)
finally:
    try: posprzataj()
    except Exception: pass
    srv.close()
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
