"""23.10 przełącznik STÓJ (stoj.py, stoj.sh, cavebot.py `_stoj_*`, nadzor.py, mozg.py, uruchom.sh STOJ_TU).
Karol: „wystarczy, żeby wyłączał chodzenie po prostu i robił runy; chciałbym móc to włączyć w dowolnym momencie";
„fajny ten tryb, bo nie da się go przesunąć"; „żeby w tym trybie od razu stał w miejscu, w którym go włączam, żeby nie potrzebował
mapy i żeby odpisywał, jadł automatycznie".
Wyłącznie atrapy: bez gry, bez X11, bez prawdziwych plików instancji, bez uruchamiania bota.
  python3 -I testy/test_stoj_przelacznik.py"""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, shutil, socket, subprocess, sys, tempfile, threading, types
from pathlib import Path
sys.dont_write_bytecode = True
_R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _R)
import bot, cavebot, pokretla, stoj

CAVELOG = []
cavebot.log = lambda *a: CAVELOG.append(" ".join(map(str, a)))
cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.STRAZNIK_CEL = 0; cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ATAK_TYLKO_PRZY_CELU = False
ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

TMP = Path(tempfile.mkdtemp(prefix="test_stoj_przelacznik_"))
POLE = (100, 100, 7)


# ---------- atrapy świata (jak w test_stoj_runy.py) ----------
class Swiat:
    def __init__(s, poz=POLE, hp=100):
        s.t = 0.0; s.poz = list(poz); s.hp = hp; s.max_hp = 100
        s.stwory = []; s.klawisze = []; s.ataki = []; s.alarmy = []; s.kroki = 0
    def zegar(s): return s.t
    def spij(s, d): s.t += d
    def zapytaj(s, z):
        s.t += 0.05
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": s.hp, "max_hp": s.max_hp, "mana": 0, "max_mana": 0}}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}
            return {"stwory": [ja] + [dict(x) for x in s.stwory]}
class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k): p.s.klawisze.append(k)
    def krok(p, k):
        d = bot.KIERUNKI[k]; p.s.t += 0.2; p.s.kroki += 1
        p.s.poz[0] += d[0]; p.s.poz[1] += d[1]
        return tuple(p.s.poz)

def prosta(start, cel, zajete=(), dlugosc=1, skosy=True):
    x, y, z = start; out = []
    while (x, y) != tuple(cel[:2]):
        x += (cel[0] > x) - (cel[0] < x); y += (cel[1] > y) - (cel[1] < y); out.append((x, y, z))
    return out

def zrob(s, katalog, trasa=None):
    atak = lambda m_, g: s.ataki.append((m_["id"], s.t))
    loot = types.SimpleNamespace(zbierz=lambda zw, g: "ok")
    b = cavebot.Cavebot(P(s), trasa or [POLE, (112, 100, 7), (112, 108, 7)], zapytaj=s.zapytaj, atak=atak,
                        alarm=lambda w: s.alarmy.append(w), spij=s.spij, zegar=s.zegar, loot=loot)
    b.droga = prosta
    b._alarm_pk = lambda t: s.alarmy.append(t)
    b._pk_powiadom = lambda *a, **k: None
    b.stoj_katalog = str(katalog)
    return b

def tiki(b, n):
    for _ in range(n):
        if not b.tick():
            return False
    return True

def mob(x, y, id_=50, nazwa="Rat"):
    return {"id": id_, "nazwa": nazwa, "gracz": False, "x": x, "y": y, "z": 7, "hp": 100}

def kat(nazwa):
    k = TMP / nazwa; k.mkdir(); return k


# ---------- 1. flaga: stoj.py ----------
k = kat("flaga")
sprawdz("1a stan bez flagi", stoj.opis(k) == "STÓJ: wyłączony" and not stoj.wlaczony(k) and stoj.pole(k) is None)
sprawdz("1b wlacz tworzy flagę (True), drugi raz False", stoj.wlacz(k) is True and stoj.wlacz(k) is False and stoj.wlaczony(k))
sprawdz("1c pusta flaga: pole None", stoj.pole(k) is None)
stoj.zapisz_dane({"pole": [1, 2, 3], "start": "swiezy", "poprzednie": {"X": 1}}, k)
stoj.zapisz_pole((5, 6, 7), k)
sprawdz("1d zapisz_pole zachowuje start i poprzednie (bot nie kasuje opisu cofnięcia)", stoj.pole(k) == (5, 6, 7)
        and stoj.dane(k).get("start") == "swiezy" and stoj.dane(k).get("poprzednie") == {"X": 1}, stoj.dane(k))
(k / "STOJ").write_text("{zepsuty")
sprawdz("1e zepsuty JSON flagi = flaga włączona, pole None (bez wyjątku)", stoj.wlaczony(k) and stoj.pole(k) is None)
sprawdz("1f wylacz zdejmuje flagę", stoj.wylacz(k) is True and not stoj.wlaczony(k) and stoj.wylacz(k) is False)
sp = subprocess.run(["bash", str(Path(_R) / "stoj.sh")], capture_output=True, text=True, timeout=30)
sprawdz("1g stoj.sh bez argumentów: użycie, kod 2", sp.returncode == 2 and "użycie" in sp.stderr, sp.stderr[-120:])
sprawdz("1h stoj.sh jest wykonywalny", _os.access(Path(_R) / "stoj.sh", _os.X_OK))


# ---------- 2. cavebot: na gorąco, nie chodzi, bije obok, nie goni ----------
k = kat("cb1")
s = Swiat(); b = zrob(s, k)
tiki(b, 40)
sprawdz("2a bez flagi bot chodzi po trasie (kontrola atrapy)", tuple(s.poz) != POLE and s.kroki > 3, (s.poz, s.kroki))
s = Swiat(); b = zrob(s, k)
tiki(b, 3)
poz0 = tuple(s.poz); kroki0 = s.kroki
stoj.wlacz(k)
n0 = len(CAVELOG)
tiki(b, 120)
sprawdz("2b po włączeniu flagi stoi (zero kroków po włączeniu)", s.kroki == kroki0 and tuple(s.poz) == tuple(b.stoj_pole), (s.poz, s.kroki, kroki0))
sprawdz("2c log „STÓJ: włączony”", any("STÓJ: włączony" in l for l in CAVELOG[n0:]), CAVELOG[n0:n0 + 2])
sprawdz("2d pole zapamiętane = pozycja z chwili włączenia i zapisane w pliku", b.stoj_pole == stoj.pole(k) and stoj.pole(k) is not None, (b.stoj_pole, stoj.pole(k)))
sprawdz("2e watchdog: wyjątek (stanie nie jest zawieszeniem)", b._watchdog_wyjatek() is True)
sprawdz("2f stan PAUZA_STOJ (prefiks PAUZA: d3_zawieszka i ratunek traktują jako zamierzony)", str(b.stan).startswith("PAUZA"), b.stan)
kroki1 = s.kroki
tiki(b, 200)
sprawdz("2g stoi także po 200 kolejnych obiegach (żadnego okrążenia ani kroku)", s.kroki == kroki1, (s.kroki, kroki1))

# cel obok: bijemy; cel dalej: nie gonimy
pole = tuple(s.poz)
s.stwory = [mob(pole[0] + 1, pole[1])]
tiki(b, 15)
sprawdz("2h stwór obok: bronimy się (atak)", len(s.ataki) >= 1, s.ataki[:2])
sprawdz("2i obrona w miejscu: pozycja bez zmian", tuple(s.poz) == pole, s.poz)
s.stwory = []
s.ataki.clear(); kroki2 = s.kroki
s.stwory = [mob(pole[0] + 4, pole[1], 51)]
tiki(b, 40)
sprawdz("2j stwór 4 pola dalej: nie gonimy (brak ataku i kroków)", not s.ataki and s.kroki == kroki2 and tuple(s.poz) == pole, (s.ataki, s.kroki, s.poz))
s.stwory = []
# cel zaczął obok i odszedł: puszczamy
s.stwory = [mob(pole[0] + 1, pole[1], 52)]
tiki(b, 6)
s.stwory = [mob(pole[0] + 5, pole[1], 52)]
kroki3 = s.kroki
tiki(b, 40)
sprawdz("2k cel odszedł: nie gonimy", s.kroki == kroki3 and tuple(s.poz) == pole and b.cel is None, (s.kroki, s.poz, b.cel))
s.stwory = []

# wyłączenie: wraca do pracy
stoj.wylacz(k)
n1 = len(CAVELOG); kroki4 = s.kroki
tiki(b, 60)
sprawdz("2l po wyłączeniu bot znów chodzi po trasie", s.kroki > kroki4, (s.kroki, kroki4))
sprawdz("2m log „STÓJ: wyłączony”", any("STÓJ: wyłączony" in l for l in CAVELOG[n1:]))
sprawdz("2n po wyłączeniu stoj_wl=False, pole zapomniane", b.stoj_wl is False and b.stoj_pole is None)


# ---------- 3. powrót na pole po przesunięciu (Karol: „nie da się go przesunąć”) ----------
k = kat("cb2")
s = Swiat(); b = zrob(s, k)
stoj.wlacz(k)
tiki(b, 5)
sprawdz("3a pole = pole startu", b.stoj_pole == POLE, b.stoj_pole)
s.poz[:] = [103, 99, 7]              # ktoś nas pchnął
n0 = len(CAVELOG)
tiki(b, 30)
sprawdz("3b pchnięty o 3 pola wraca na pole", tuple(s.poz) == POLE, s.poz)
sprawdz("3c po powrocie stoi (stan PAUZA_STOJ)", str(b.stan) == "PAUZA_STOJ", b.stan)
kroki = s.kroki
tiki(b, 60)
sprawdz("3d po powrocie nie rusza się dalej", s.kroki == kroki and tuple(s.poz) == POLE)
s.poz[:] = [95, 104, 7]
tiki(b, 40)
sprawdz("3e kolejne pchnięcie: znów wraca", tuple(s.poz) == POLE, s.poz)
# pole zajęte przez innego gracza / stwora: stoimy obok, nie wchodzimy i nie przepychamy
s.poz[:] = [102, 100, 7]
s.stwory = [{"id": 70, "nazwa": "Obcy", "gracz": True, "x": 100, "y": 100, "z": 7, "hp": 100}]
tiki(b, 20)
sprawdz("3f pole zajęte: stoimy obok, bez kroków", tuple(s.poz) == (102, 100, 7), s.poz)
s.stwory = []
# inne piętro: nie chodzimy (żadnego szukania drogi między piętrami)
s.poz[:] = [100, 100, 8]; kroki = s.kroki
tiki(b, 20)
sprawdz("3g inne piętro niż pole: stoi, bez kroków", s.kroki == kroki and tuple(s.poz) == (100, 100, 8), (s.poz, s.kroki, kroki))
s.poz[:] = [100, 100, 7]
# restart bota: pole przeżywa w pliku flagi
s2 = Swiat(poz=(104, 98, 7)); b2 = zrob(s2, k)
tiki(b2, 30)
sprawdz("3h nowy bot (restart) czyta pole z pliku flagi i wraca na nie", tuple(s2.poz) == POLE and b2.stoj_pole == POLE, (s2.poz, b2.stoj_pole))
# brak drogi: stoi tam, gdzie jest, nie STOP i nie wyjątek
s3 = Swiat(poz=(104, 98, 7)); b3 = zrob(s3, k)
b3.droga = lambda *a, **kw: []
r = tiki(b3, 20)
sprawdz("3i brak drogi na pole: stoi, bot żyje (tick True)", r and s3.kroki == 0 and tuple(s3.poz) == (104, 98, 7), (r, s3.kroki))


# ---------- 4. ucieczka przy zagrożeniu życia zostaje; dojście kończy się cicho ----------
k = kat("cb3")
s = Swiat(hp=100); b = zrob(s, k); b.prog_hp = 40
stoj.wlacz(k)
tiki(b, 5)
s.hp = 10; s.stwory = [mob(101, 100, 60)]
n0 = len(CAVELOG)
tiki(b, 6)
uciekl = any("ucieka" in l.lower() or "ucieczk" in l.lower() for l in CAVELOG[n0:]) or str(b.stan).startswith("UCIECZKA") or bool(s.alarmy)
sprawdz("4a HP poniżej progu przy STÓJ: ucieczka działa jak dotąd (progi bez zmian)", uciekl, (b.stan, CAVELOG[n0:n0 + 3]))
k = kat("cb4")
s = Swiat(); d = cavebot.CavebotDojscie(P(s), [(100, 100, 7), (110, 100, 7)], None, 1, 40, None, None, True) \
    if "CavebotDojscie" in dir(cavebot) else None
if d is not None:
    d.stoj_katalog = str(k); d.droga = prosta
    stoj.wlacz(k)
    n0 = len(CAVELOG)
    w = d.tick()
    sprawdz("4b dojście przy włączonym STÓJ przerywa się cicho (tick False, bez porażki)", w is False and not getattr(d, "dojscie_porazka", False)
            and any("włączony STÓJ" in l for l in CAVELOG[n0:]), (w, CAVELOG[n0:]))
else:
    sprawdz("4b CavebotDojscie istnieje", False)


# ---------- 5. nadzor: STÓJ nie jest zawieszeniem ----------
import nadzor
N = nadzor.Nadzorca.__new__(nadzor.Nadzorca)
N.korzen = TMP / "korzen"; (N.korzen / "instancje" / "a").mkdir(parents=True)
N.konf = {"stoi_min": 8, "brak_zabic_min": 20}
N._stanowisko = lambda *a: False
o = {"tele": {"wiek_probki_s": 5, "stoi_poza_walka_s": 3600}}
z0 = N.zaciecie("a", o, {}, {}, 0)
sprawdz("5a bez STOJ: stoi 60 min poza walką = zacięcie (kontrola)", z0 and "stoi" in z0, z0)
(N.korzen / "instancje" / "a" / "STOJ").touch()
sprawdz("5b ze STOJ: stanie nie jest zacięciem", N.zaciecie("a", o, {}, {}, 0) is None)
o_st = {"tele": {"wiek_probki_s": 400, "stoi_poza_walka_s": 3600}}
sprawdz("5c ze STOJ: stara telemetria (zawieszony proces) nadal jest zacięciem", "telemetria stara" in (N.zaciecie("a", o_st, {}, {}, 0) or ""))


# ---------- 6. pokrętła: UH od lvl 11 i ML >= 11, inaczej HMM; jedzenie; bez wypraw ----------
kn, run = stoj.pokretla_stoj(17, 14)
sprawdz("6a lvl 17, ML 14: UH (adura vita, F7)", run == "uh" and kn["UH_KLAWISZ"] == "F7" and kn["UH_CZAR"] == "adura vita" and kn["UH_AKTYWNY"] == 1, (run, kn.get("UH_CZAR")))
kn2, run2 = stoj.pokretla_stoj(17, 9)
sprawdz("6b lvl 17, ML 9 (< 11): HMM (adori gran, F6)", run2 == "runy" and kn2["UH_CZAR"] == "adori gran" and kn2["UH_KLAWISZ"] == "F6", (run2, kn2.get("UH_CZAR")))
kn3, run3 = stoj.pokretla_stoj(10, 20)
sprawdz("6c lvl 10 (< 11): HMM", run3 == "runy")
kn4, run4 = stoj.pokretla_stoj(25, None)
sprawdz("6d ML nieznany: HMM (ostrożnie, nie zgadujemy)", run4 == "runy")
sprawdz("6e exura zawsze (ZDROWIE_CZAR_AKTYWNY=1), bez wypraw/refillu/stanowiska/ML", all(c["ZDROWIE_CZAR_AKTYWNY"] == 1 and c["WYPRAWA_AKTYWNA"] == 0
        and c["WROC_REFILL"] == 0 and c["STANOWISKO"] == 0 and c["ML_CZAR_AKTYWNY"] == 0 and c["WYPRAWA_DEPO_BLANKI"] == 0 for c in (kn, kn2, kn3, kn4)))
sprawdz("6f exevo pan od lvl 14, niżej tylko jedzenie z plecaka", kn["JEDZENIE_CZAR_AKTYWNY"] == 1 and kn3["JEDZENIE_CZAR_AKTYWNY"] == 0)
ok_, bl = pokretla.waliduj(dict(kn)); sprawdz("6g pokrętła przechodzą walidację pokretla.py", not bl and set(ok_) == set(kn), bl)
sprawdz("6h progi życia (HP/PK/OGIEN) nie są dotykane", not any(x.startswith(("OGIEN_", "PK_", "PROG")) for x in kn))


# ---------- 7. stoj.py: włączanie w trzech przypadkach (atrapy gry i skryptów) ----------
class Gra:
    def __init__(g, poz=(33165, 31828, 3), level=17, ml=14, widzi=True):
        g.poz, g.level, g.ml, g.widzi = poz, level, ml, widzi
    def zapytaj(g, z):
        if not g.widzi:
            raise RuntimeError("brak postaci")
        if z["cmd"] == "pozycja":
            return {"pozycja": {"x": g.poz[0], "y": g.poz[1], "z": g.poz[2]}}
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": 230, "max_hp": 230, "level": g.level, "mana": 100, "max_mana": 300, "adres": "0x1"}}
        if z["cmd"] == "hexdump":
            import struct
            v = [230.0, 230.0, 0, 0, 0, float(g.level), 0, 0, float(g.ml), 12.0, float(g.ml), 0.0]
            return {"hex": struct.pack("<12d", *v).hex()}
        raise RuntimeError(z)

def kopia_instancji(nazwa, na_zywo=None, ostatni=False):
    kor = TMP / nazwa; (kor / "instancje" / "inv").mkdir(parents=True)
    for f in ("tryby.json", "pokretla.py"):
        shutil.copy(Path(_R) / f, kor / f)
    (kor / "instancje" / "inv" / "profil.json").write_text(json.dumps({"postac": "Invincible"}))
    (kor / "instancje" / "inv" / "na_zywo.json").write_text(json.dumps(na_zywo if na_zywo is not None else {"UH_AKTYWNY": 0, "WYPRAWA_AKTYWNA": 1}))
    if ostatni:
        (kor / "ostatni_start.inv.env").write_text("MAPA=stoj_uh_edron_horn\nTRYB=uh\\,stoj\n")
    return kor, kor / "instancje" / "inv"

class Skrypty:
    """Atrapa wykonawcy skryptów powłoki: zapisuje wywołania (skrypt, dodatkowe środowisko)."""
    def __init__(sk, kod_uruchom=0): sk.wywolania = []; sk.kod = kod_uruchom
    def __call__(sk, skrypt, env_dod=None):
        sk.wywolania.append((skrypt, dict(env_dod or {})))
        return sk.kod if skrypt == "uruchom.sh" else 0
    def nazwy(sk): return [w[0] for w in sk.wywolania]

# 7a. bot chodzi w hybrydzie: tylko flaga, pole z gniazda, zero skryptów
kor, st = kopia_instancji("p7a"); sk = Skrypty(); gra = Gra()
kod = stoj.wlacz_pelny("inv", st, zapytaj=gra.zapytaj, bot=lambda: (True, "hybryda"), uruchom=sk, kat=kor, log=lambda *a: None)
sprawdz("7a bot w hybrydzie: sama flaga na gorąco, pole = obecna pozycja, zero skryptów", kod == 0 and stoj.pole(st) == (33165, 31828, 3)
        and stoj.dane(st)["start"] == "goracy" and not sk.wywolania, (kod, stoj.dane(st), sk.wywolania))
sprawdz("7a' pokrętła nietknięte przy gorącym włączeniu", json.loads((st / "na_zywo.json").read_text()) == {"UH_AKTYWNY": 0, "WYPRAWA_AKTYWNA": 1})
# powtórka: już włączony
kod = stoj.wlacz_pelny("inv", st, zapytaj=gra.zapytaj, bot=lambda: (True, "hybryda"), uruchom=sk, kat=kor, log=lambda *a: None)
sprawdz("7a'' drugie `on` przy działającym bocie nie zmienia pola", kod == 0 and stoj.pole(st) == (33165, 31828, 3))

# 7b. bot w skrypcie: restart w hybrydzie na obecnej pozycji
kor, st = kopia_instancji("p7b", ostatni=True); sk = Skrypty(); gra = Gra(poz=(33170, 31800, 3))
log7 = []
kod = stoj.wlacz_pelny("inv", st, zapytaj=gra.zapytaj, bot=lambda: (True, "skrypt"), uruchom=sk, kat=kor, log=lambda *a: log7.append(" ".join(map(str, a))))
sprawdz("7b bot w skrypcie: zatrzymaj.sh potem uruchom.sh", kod == 0 and sk.nazwy() == ["zatrzymaj.sh", "uruchom.sh"], sk.wywolania)
env = sk.wywolania[-1][1] if sk.wywolania else {}
sprawdz("7b' start w hybrydzie (MOZG_TRYB=hybryda), trasa jednopunktowa STOJ_TU, próg HP", env.get("MOZG_TRYB") == "hybryda"
        and env.get("STOJ_TU") == "_stoj_tu_inv" and env.get("STOJ_PROG_HP") == "50", env)
trasa = json.loads((kor / "trasy" / "_stoj_tu_inv.json").read_text())
sprawdz("7b'' trasa wygenerowana z OBECNEJ pozycji (bez mapy.json i bez pliku trasy z repo)", trasa == [[33170, 31800, 3]], trasa)
sprawdz("7b''' flaga: pole, start=restart, mózg sprzed STÓJ", stoj.pole(st) == (33170, 31800, 3) and stoj.dane(st)["start"] == "restart"
        and stoj.dane(st)["mozg_przed"] == "skrypt", stoj.dane(st))
nz_ = json.loads((st / "na_zywo.json").read_text())
sprawdz("7b'''' pokrętła ustawione: UH (lvl 17, ML 14), exura, bez wypraw", nz_["UH_AKTYWNY"] == 1 and nz_["UH_CZAR"] == "adura vita" and nz_["WYPRAWA_AKTYWNA"] == 0
        and nz_["ZDROWIE_CZAR_AKTYWNY"] == 1 and nz_["JEDZENIE_CZAR_AKTYWNY"] == 1, {k: nz_.get(k) for k in ("UH_AKTYWNY", "UH_CZAR", "WYPRAWA_AKTYWNA")})
sprawdz("7b5 zapisano kopię na_zywo.json przed zmianą", any(p.name.startswith("na_zywo.json.bak-") for p in st.iterdir()))

# 7c. skrypt + --bez-restartu: sama flaga
kor, st = kopia_instancji("p7c"); sk = Skrypty(); gra = Gra()
kod = stoj.wlacz_pelny("inv", st, bez_restartu=True, zapytaj=gra.zapytaj, bot=lambda: (True, "skrypt"), uruchom=sk, kat=kor, log=lambda *a: None)
sprawdz("7c --bez-restartu: tylko flaga, bez skryptów i bez zmiany pokręteł", kod == 0 and not sk.wywolania and stoj.dane(st)["start"] == "goracy"
        and json.loads((st / "na_zywo.json").read_text())["UH_AKTYWNY"] == 0)

# 7d. bot nie chodzi (Karol gra): start świeży, bez zatrzymaj.sh
kor, st = kopia_instancji("p7d"); sk = Skrypty(); gra = Gra(poz=(32339, 32221, 7), level=9, ml=5)
kod = stoj.wlacz_pelny("inv", st, zapytaj=gra.zapytaj, bot=lambda: (False, None), uruchom=sk, kat=kor, log=lambda *a: None)
sprawdz("7d bot nie chodzi: tylko uruchom.sh (STOP/STOP_RECZNY zdejmuje uruchom.sh), start świeży", kod == 0 and sk.nazwy() == ["uruchom.sh"]
        and sk.wywolania[0][1]["MOZG_TRYB"] == "hybryda" and stoj.dane(st)["start"] == "swiezy", (kod, sk.wywolania))
sprawdz("7d' lvl 9: HMM (adori gran), exevo pan wyłączony", json.loads((st / "na_zywo.json").read_text())["UH_CZAR"] == "adori gran"
        and json.loads((st / "na_zywo.json").read_text())["JEDZENIE_CZAR_AKTYWNY"] == 0)
sprawdz("7d'' trasa z obecnej pozycji (Thais, bez mapy)", json.loads((kor / "trasy" / "_stoj_tu_inv.json").read_text()) == [[32339, 32221, 7]])

# 7e. gra nie widzi postaci: odmowa, nic nie zapisane
kor, st = kopia_instancji("p7e"); sk = Skrypty(); gra = Gra(widzi=False)
kod = stoj.wlacz_pelny("inv", st, zapytaj=gra.zapytaj, bot=lambda: (False, None), uruchom=sk, kat=kor, log=lambda *a: None)
sprawdz("7e postać niewidoczna: odmowa (kod 3), brak flagi, brak skryptów, pokrętła bez zmian", kod == 3 and not stoj.wlaczony(st) and not sk.wywolania
        and json.loads((st / "na_zywo.json").read_text())["UH_AKTYWNY"] == 0)

# 7f. uruchom.sh zawodzi: cofnięcie flagi i pokręteł
kor, st = kopia_instancji("p7f"); sk = Skrypty(kod_uruchom=3); gra = Gra()
kod = stoj.wlacz_pelny("inv", st, zapytaj=gra.zapytaj, bot=lambda: (False, None), uruchom=sk, kat=kor, log=lambda *a: None)
sprawdz("7f start nieudany: kod != 0, flaga zdjęta, pokrętła przywrócone", kod != 0 and not stoj.wlaczony(st)
        and json.loads((st / "na_zywo.json").read_text()) == {"UH_AKTYWNY": 0, "WYPRAWA_AKTYWNA": 1}, json.loads((st / "na_zywo.json").read_text()))

# 7g. flaga bez bota (stara): zaczyna od nowa
kor, st = kopia_instancji("p7g"); sk = Skrypty(); gra = Gra()
stoj.zapisz_dane({"pole": [1, 1, 1]}, st)
kod = stoj.wlacz_pelny("inv", st, zapytaj=gra.zapytaj, bot=lambda: (False, None), uruchom=sk, kat=kor, log=lambda *a: None)
sprawdz("7g stara flaga bez bota: start od nowa na obecnej pozycji", kod == 0 and stoj.pole(st) == (33165, 31828, 3) and sk.nazwy() == ["uruchom.sh"])


# ---------- 8. stoj.py: wyłączanie ----------
# 8a. na gorąco
kor, st = kopia_instancji("p8a"); sk = Skrypty(); gra = Gra()
stoj.wlacz_pelny("inv", st, zapytaj=gra.zapytaj, bot=lambda: (True, "hybryda"), uruchom=sk, kat=kor, log=lambda *a: None)
kod = stoj.wylacz_pelny("inv", st, bot=lambda: (True, "hybryda"), uruchom=sk, kat=kor, log=lambda *a: None)
sprawdz("8a off po gorącym on: sama flaga zdjęta, zero skryptów", kod == 0 and not stoj.wlaczony(st) and not sk.wywolania)
# 8b. po restarcie: powrót do ostatniej mapy i trybu, mózg jak przed STÓJ, pokrętła przywrócone
kor, st = kopia_instancji("p8b", ostatni=True); sk = Skrypty(); gra = Gra()
stoj.wlacz_pelny("inv", st, zapytaj=gra.zapytaj, bot=lambda: (True, "skrypt"), uruchom=sk, kat=kor, log=lambda *a: None)
sk.wywolania.clear()
kod = stoj.wylacz_pelny("inv", st, bot=lambda: (True, "hybryda"), uruchom=sk, kat=kor, log=lambda *a: None)
sprawdz("8b off po restarcie: zatrzymaj.sh, potem uruchom.sh bez MAPA/TRYB (czyta ostatni_start) z mózgiem skrypt", kod == 0
        and sk.nazwy() == ["zatrzymaj.sh", "uruchom.sh"] and sk.wywolania[-1][1] == {"MOZG_TRYB": "skrypt"}, sk.wywolania)
sprawdz("8b' flaga zdjęta, pokrętła z powrotem jak przed STÓJ", not stoj.wlaczony(st)
        and json.loads((st / "na_zywo.json").read_text()) == {"UH_AKTYWNY": 0, "WYPRAWA_AKTYWNA": 1}, json.loads((st / "na_zywo.json").read_text()))
# 8c. po starcie świeżym: stop + STOP_RECZNY
kor, st = kopia_instancji("p8c"); sk = Skrypty(); gra = Gra()
stoj.wlacz_pelny("inv", st, zapytaj=gra.zapytaj, bot=lambda: (False, None), uruchom=sk, kat=kor, log=lambda *a: None)
sk.wywolania.clear()
kod = stoj.wylacz_pelny("inv", st, bot=lambda: (True, "hybryda"), uruchom=sk, kat=kor, log=lambda *a: None)
sprawdz("8c off po starcie świeżym: bot zatrzymany (zatrzymaj.sh), nie startuje na żadnej mapie, pokrętła wróciły", kod == 0
        and sk.nazwy() == ["zatrzymaj.sh"] and not stoj.wlaczony(st)
        and json.loads((st / "na_zywo.json").read_text()) == {"UH_AKTYWNY": 0, "WYPRAWA_AKTYWNA": 1}, (sk.wywolania, json.loads((st / "na_zywo.json").read_text())))
# 8c'. bot już nie chodzi: STOP_RECZNY stawia stoj.py
kor, st = kopia_instancji("p8d"); sk = Skrypty(); gra = Gra()
stoj.wlacz_pelny("inv", st, zapytaj=gra.zapytaj, bot=lambda: (False, None), uruchom=sk, kat=kor, log=lambda *a: None)
sk.wywolania.clear()
stoj.wylacz_pelny("inv", st, bot=lambda: (False, None), uruchom=sk, kat=kor, log=lambda *a: None)
sprawdz("8d off po starcie świeżym, bot już nie chodzi: STOP_RECZNY ustawiony, bez skryptów", (st / "STOP_RECZNY").exists() and not sk.wywolania)
# 8e. restart bez ostatniego startu: nie startuje na domyślnej mapie (raty)
kor, st = kopia_instancji("p8e", ostatni=False); sk = Skrypty(); gra = Gra()
stoj.wlacz_pelny("inv", st, zapytaj=gra.zapytaj, bot=lambda: (True, "skrypt"), uruchom=sk, kat=kor, log=lambda *a: None)
sk.wywolania.clear()
stoj.wylacz_pelny("inv", st, bot=lambda: (True, "hybryda"), uruchom=sk, kat=kor, log=lambda *a: None)
sprawdz("8e brak ostatni_start: nie uruchamia domyślnej mapy, tylko zatrzymuje", "uruchom.sh" not in sk.nazwy() and not stoj.wlaczony(st), sk.wywolania)
# 8f. pokrętło zmienione ręcznie po STÓJ nie jest cofane
kor, st = kopia_instancji("p8f", ostatni=True); sk = Skrypty(); gra = Gra()
stoj.wlacz_pelny("inv", st, zapytaj=gra.zapytaj, bot=lambda: (True, "skrypt"), uruchom=sk, kat=kor, log=lambda *a: None)
d = json.loads((st / "na_zywo.json").read_text()); d["UH_MIN_HP"] = 77; d["WYPRAWA_AKTYWNA"] = 1
(st / "na_zywo.json").write_text(json.dumps(d))
stoj.wylacz_pelny("inv", st, bot=lambda: (True, "hybryda"), uruchom=sk, kat=kor, log=lambda *a: None)
d2 = json.loads((st / "na_zywo.json").read_text())
sprawdz("8f pokrętło zmienione po STÓJ przez kogoś innego zostaje (cofamy tylko własne zmiany)", d2["UH_MIN_HP"] == 77 and d2["WYPRAWA_AKTYWNA"] == 1, d2)


# ---------- 9. uruchom.sh z STOJ_TU: hybryda, trasa tu i teraz, bez mapy, bez ostatni_start ----------
NICK = "Testowanix"
def strazak(sciezka, nick, z):
    srv = socket.socket(socket.AF_UNIX); srv.bind(str(sciezka)); srv.listen(5); srv.settimeout(0.2)
    stop = threading.Event()
    def petla():
        while not stop.is_set():
            try:
                c, _ = srv.accept()
            except OSError:
                continue
            try:
                zad = json.loads(c.recv(400).decode())
                c.sendall((json.dumps({"pozycja": {"x": 1, "y": 2, "z": z}} if zad.get("nazwa") == nick else {"blad": "brak postaci"}) + "\n").encode())
            except Exception:
                pass
            c.close()
    t = threading.Thread(target=petla, daemon=True); t.start()
    return lambda: (stop.set(), t.join(2), srv.close())

def uruchom_sh(env_dod, z=3):
    with tempfile.TemporaryDirectory(prefix="stoj_uruchom_") as td:
        T = Path(td) / "pom"; T.mkdir(); rt = Path(td) / "rt"; rt.mkdir(); bin_ = Path(td) / "bin"; bin_.mkdir()
        for f in ("instancja.py", "profil.py", "tryb.py", "pokretla.py", "mapy.json", "tryby.json", "w_scope.sh"):
            shutil.copy(Path(_R) / f, T / f)
        shutil.copy(Path(_R) / "uruchom.sh", T / "uruchom.sh"); _os.chmod(T / "uruchom.sh", 0o755)
        (T / "mozg.py").write_text("import sys,os\nopen(os.environ['ATRAPA_ARGS'],'w').write(' '.join(sys.argv[1:]))\n")
        (T / "obserwator_z_botem.sh").write_text("#!/bin/bash\nexit 0\n"); _os.chmod(T / "obserwator_z_botem.sh", 0o755)
        (bin_ / "notify-send").write_text("#!/bin/bash\nexit 0\n"); _os.chmod(bin_ / "notify-send", 0o755)
        st = T / "instancje" / "tst"; st.mkdir(parents=True)
        (st / "profil.json").write_text(json.dumps({"proxy": {"host": "h", "port": 80, "user": "u"}, "ip_oczekiwane": ["1.2.3.4"], "postac": NICK}))
        (st / "STOP").write_text(""); (st / "STOP_RECZNY").write_text("")
        zamknij = strazak(rt / "retronic-tst.sock", NICK, z)
        env = {k: v for k, v in _os.environ.items() if not k.startswith(("RETRONIC_", "MAPA", "TRYB", "MOZG_", "STOJ_"))}
        env.update(XDG_RUNTIME_DIR=str(rt), PATH=f"{bin_}:{_os.environ['PATH']}", ATRAPA_ARGS=str(Path(td) / "args"),
                   RETRONIC_CZEKAJ_POSTAC_S="2", RETRONIC_ID="tst", RETRONIC_TESTY="1", **env_dod)   # TESTY: w_scope.sh bez prawdziwych jednostek
        try:
            r = subprocess.run(["bash", str(T / "uruchom.sh")], env=env, capture_output=True, text=True, timeout=60, cwd=str(T))
            import time; time.sleep(0.5)
        finally:
            zamknij()
        args = Path(td, "args").read_text() if Path(td, "args").exists() else None
        return r.returncode, r.stdout, r.stderr, args, (T / "ostatni_start.tst.env").exists(), (st / "STOP").exists(), (st / "STOP_RECZNY").exists()

kod, out, err, args, ostatni, stop, stopr = uruchom_sh({"STOJ_TU": "_stoj_tu_tst", "MOZG_TRYB": "hybryda", "STOJ_PROG_HP": "50"})
sprawdz("9a STOJ_TU: mózg hybryda w poleceniu startu (odpisuje na czacie)", kod == 0 and args and "--tryb hybryda" in args and "--model haiku" in args, (kod, args, err.strip()[-150:]))
sprawdz("9b trasa jednopunktowa tu i teraz, bez dojścia, próg HP 50", args and "--trasa _stoj_tu_tst" in args and "--dojscie" not in args and "--prog-hp 50" in args, args)
sprawdz("9c bez --potwory z nazwą (każdy stwór obok jest celem obrony)", args and "--potwory" in args and "Rat" not in args, args)
sprawdz("9d bez mapy: nie zapisuje ostatni_start (powrót po off bierze poprzednią mapę), STOP i STOP_RECZNY zdjęte", not ostatni and not stop and not stopr, (ostatni, stop, stopr))
kod, out, err, args, ostatni, stop, stopr = uruchom_sh({"MAPA": "rook_bugi_z8", "TRYB": ""}, z=8)
sprawdz("9e zwykły start (bez STOJ_TU) nadal domyślnie `--tryb skrypt` (inne starty bez zmian)", kod == 0 and args and "--tryb skrypt" in args
        and "--trasa" in args and "_stoj_tu" not in args and ostatni, (kod, args, err.strip()[-120:]))


# ---------- 10. mozg.py: wiring w kodzie (bez uruchamiania mózgu) ----------
src = (Path(_R) / "mozg.py").read_text()
sprawdz("10a mozg.py: dojście i wznowienie pomijane przy STÓJ (_stoj_wlaczony w main i przejdz_dojscie)", src.count("_stoj_wlaczony()") >= 4 and "def _stoj_wlaczony" in src)
src_n = (Path(_R) / "nadzor.py").read_text()
sprawdz("10b nadzor.py: zaciecie wyłączone przy STOJ", "def stoj_wlaczony(korzen, id_)" in src_n and "if stoj_wlaczony(self.korzen, id_)" in src_n)

print(f"{sum(ok)}/{len(ok)}")
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(0 if all(ok) else 1)
