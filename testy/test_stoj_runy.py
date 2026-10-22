"""22.10 F1 SPEC_stoj_runy_1022: tryb "stoj" (stanowisko.py): mapa stoj_runy_thais, pokrętła, tryb.py, haki w cavebot.py
(ucieczka do PZ, reakcja PK, serwis zamiast wyprawy, filtr NPC dla UH, wyjątek watchdoga), wyjątek nadzorcy, Koordynator miast.
Wyłącznie atrapy: bez gry, bez X11, bez powiadomień pulpitu, bez prawdziwych plików instancji."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, subprocess, sys, tempfile, types
from pathlib import Path
sys.dont_write_bytecode = True
_R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _R)
import bot, cavebot, miejsca_koord, nadzor, pokretla, stanowisko, wyprawa

CAVELOG = []
_log0 = cavebot.log
cavebot.log = lambda *a: CAVELOG.append(" ".join(map(str, a)))
cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.STRAZNIK_CEL = 0; cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ATAK_TYLKO_PRZY_CELU = False
POWIADOMIENIA = []
stanowisko._powiadom = lambda tytul, tresc, poziom, klucz: POWIADOMIENIA.append((tytul, klucz))
ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

TMP = Path(tempfile.mkdtemp(prefix="test_stoj_runy_"))
POLE = (100, 100, 7)
PZ = (94, 100, 7)
DEPO = (94, 102, 7)
MAPA = {"miasto": "testowo", "pola": [POLE], "pz": [PZ], "depo": DEPO, "pz_zmierzone": True}


# ---------- 1. dane: mapa, trasa, tryb, pokrętła ----------
mapy = json.loads((Path(_R) / "mapy.json").read_text())
tryby = json.loads((Path(_R) / "tryby.json").read_text())
m = mapy.get("stoj_runy_thais") or {}
st = m.get("stanowisko") or {}
sprawdz("1a mapa stoj_runy_thais ma stanowisko: miasto, pole, pz, depo", st.get("miasto") == "thais"
        and st.get("pola") == [[32339, 32221, 7]] and st.get("pz") and st.get("depo") == [32348, 32225, 7], st)
trasa = json.loads((Path(_R) / "trasy" / "stoj_runy_thais.json").read_text())
sprawdz("1b trasa to jeden punkt = pole stanowiska", trasa == [[32339, 32221, 7]], trasa)
sprawdz("1c potwory mapy to nazwa, której nie ma w grze (nic nie jest celem)", m.get("potwory") and "rat" not in m["potwory"].casefold())
serw = json.loads((Path(_R) / "trasy" / "serwis_thais.json").read_text())
sprawdz("1d depo stanowiska = depo serwisu Thais", serw["przystanki"]["depo"]["stoi"] == st.get("depo"), serw["przystanki"]["depo"]["stoi"])
sprawdz("1e pz_zmierzone jest false (pomiar Karola jeszcze nie zrobiony)", st.get("pz_zmierzone") is False)
sprawdz("1f tryb stoj istnieje i włącza STANOWISKO + serwis tylko-do-depo", (tryby.get("stoj") or {}).get("pokrętła", (tryby.get("stoj") or {}).get("pokretla", tryby.get("stoj", {}))).get("STANOWISKO") == 1
        if isinstance(tryby.get("stoj"), dict) else False, list(tryby.get("stoj", {}))[:6])
for k, v in {"STANOWISKO": 1, "STANOWISKO_HP_PZ": 70, "STANOWISKO_PZ_KARENCJA_MIN": 30, "STANOWISKO_ZMIANA_MAX_MIN": 180,
             "STANOWISKO_AKTYWNOSC_MAX_S": 240}.items():
    w = pokretla.waliduj({k: v})
    sprawdz(f"1g pokrętło {k}={v} przechodzi walidację", w[0] if isinstance(w, tuple) else w, w)
for k, v in {"STANOWISKO": 2, "STANOWISKO_HP_PZ": 10, "STANOWISKO_PZ_KARENCJA_MIN": 1, "STANOWISKO_GRACZ_ODL": 99,
             "STANOWISKO_ZMIANA_MAX_MIN": 5000}.items():
    w = pokretla.waliduj({k: v})
    przyj = w[0] if isinstance(w, tuple) else w
    sprawdz(f"1h pokrętło {k}={v} poza zakresem jest odrzucone", not przyj or k not in przyj, w)
for k in ("STANOWISKO", "STANOWISKO_HP_PZ", "STANOWISKO_PZ_KARENCJA_MIN", "STANOWISKO_GRACZ_ODL", "STANOWISKO_NPC_IGNORUJ",
          "STANOWISKO_WOLNE_SLOTY_MIN", "STANOWISKO_AKTYWNOSC_MAX_S", "STANOWISKO_ROTACJA_MIN", "STANOWISKO_ZMIANA_MAX_MIN"):
    sprawdz(f"1i stała cavebot.{k} istnieje (domyślnie wyłączone/bezpieczne)", hasattr(cavebot, k))
sprawdz("1j domyślnie STANOWISKO=0, HP_PZ=70, ZMIANA=180 (decyzja Karola 3 h)", cavebot.STANOWISKO == 0
        and cavebot.STANOWISKO_HP_PZ == 70 and cavebot.STANOWISKO_ZMIANA_MAX_MIN == 180)
sprawdz("1k domyślne cavebot = DOMYSLNE stanowiska", all(getattr(cavebot, k) == v for k, v in stanowisko.DOMYSLNE.items() if k != "WROC_REFILL"))


# ---------- 2. tryb.py zapisuje i kasuje stanowisko_mapa.json ----------
kat = TMP / "inst"; kat.mkdir()
(kat / "na_zywo.json").write_text("{}")
def tryb_py(mapa, tryb):
    return subprocess.run([sys.executable, "-I", str(Path(_R) / "tryb.py"), "--mapa", mapa, "--tryb", tryb,
                           "--na-zywo", str(kat / "na_zywo.json"), "--log", str(kat / "tryb.log")],
                          capture_output=True, text=True, timeout=60, cwd=_R, env=dict(_os.environ, RETRONIC_TESTY="1"))
r = tryb_py("stoj_runy_thais", "uh,stoj")
plik = kat / "stanowisko_mapa.json"
sprawdz("2a tryb.py stoj_runy_thais zapisuje stanowisko_mapa.json obok na_zywo.json", r.returncode == 0 and plik.exists(), r.stderr[-300:])
zaw = json.loads(plik.read_text()) if plik.exists() else {}
sprawdz("2b zawartość = wpis stanowisko z mapy", zaw.get("pola") == [[32339, 32221, 7]] and zaw.get("depo") == [32348, 32225, 7])
nz = json.loads((kat / "na_zywo.json").read_text())
sprawdz("2c na_zywo.json: STANOWISKO=1, UH_AKTYWNY=1", nz.get("STANOWISKO") == 1 and nz.get("UH_AKTYWNY") == 1, nz)
sprawdz("2d MAPA_TRASA=stoj_runy_thais w wyniku", "MAPA_TRASA=stoj_runy_thais" in r.stdout)
sprawdz("2e brak OGIEN_/PK_/HP-progów w zmianach trybu (życie postaci bez zmian)",
        not any(k.startswith(("OGIEN_", "PK_", "PROG")) for k in nz), sorted(nz))
mw = wczyt = stanowisko.wczytaj_mape(kat)
sprawdz("2f wczytaj_mape czyta plik (krotki, miasto)", mw and mw["pola"] == [(32339, 32221, 7)] and mw["miasto"] == "thais", mw)
r2 = tryb_py("raty", "")
sprawdz("2g inna mapa (raty) kasuje stanowisko_mapa.json", r2.returncode == 0 and not plik.exists(), r2.stderr[-300:])
sprawdz("2h wczytaj_mape bez pliku = None", stanowisko.wczytaj_mape(kat) is None)
(kat / "stanowisko_mapa.json").write_text("{zepsuty")
sprawdz("2i zepsuty JSON = None (bez wyjątku)", stanowisko.wczytaj_mape(kat) is None)


cavebot.STANOWISKO = 1       # pokrętło włączone (tryb stoj); testy stanowiska podają własny obiekt Stanowisko


# ---------- atrapy świata do testów na prawdziwym Cavebot ----------
class Swiat:
    def __init__(s, poz=POLE, hp=100):
        s.t = 0.0; s.poz = list(poz); s.hp = hp; s.max_hp = 100
        s.stwory = []; s.klawisze = []; s.ataki = []; s.alarmy = []
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
        d = bot.KIERUNKI[k]; p.s.t += 0.2
        p.s.poz[0] += d[0]; p.s.poz[1] += d[1]
        return tuple(p.s.poz)

def prosta(start, cel, zajete=(), dlugosc=1, skosy=True):
    x, y, z = start; out = []
    while (x, y) != tuple(cel[:2]):
        x += (cel[0] > x) - (cel[0] < x); y += (cel[1] > y) - (cel[1] < y); out.append((x, y, z))
    return out

def zrob(s, knobs=None, mapa=MAPA, wall=None, npc=("npc jeden",), koord=None, plik_stanu=None):
    atak = lambda m_, g: s.ataki.append((m_["id"], s.t))
    loot = types.SimpleNamespace(zbierz=lambda zw, g: "ok")
    b = cavebot.Cavebot(P(s), [POLE], zapytaj=s.zapytaj, atak=atak, alarm=lambda w: s.alarmy.append(w),
                        spij=s.spij, zegar=s.zegar, loot=loot)
    b.droga = prosta
    b._alarm_pk = lambda t: s.alarmy.append(t)
    b._pk_powiadom = lambda *a, **k: None
    kn = dict(knobs or {})
    w = wall or (lambda: s.t + 1000.0)
    slog = []
    b.stanowisko = stanowisko.Stanowisko(b, mapa, k=lambda n, d=0: kn.get(n, stanowisko.DOMYSLNE.get(n, d)), npc=set(npc), wall=w,
                                         koord=koord, plik_stanu=plik_stanu, log=lambda *a: slog.append(" ".join(map(str, a))))
    b.slog = slog
    return b

def tiki(b, n):
    for _ in range(n):
        if not b.tick():
            return False
    return True


# ---------- 3. stoi na polu, zero okrążeń, brak STOP ----------
s = Swiat(); b = zrob(s)
n0 = len(CAVELOG)
tiki(b, 300)
sprawdz("3a stoi na polu: pozycja bez zmian po 300 obiegach", tuple(s.poz) == POLE, s.poz)
sprawdz("3b zero logów 'Okrążenie' i okrążenie=0", not any("Okrążenie" in l for l in CAVELOG[n0:]) and b.okrazenie == 0)
sprawdz("3c stan STOJ, stanowisko POLE", b.stan == "STOJ" and b.stanowisko.stan == "POLE", (b.stan, b.stanowisko.stan))
sprawdz("3d watchdog: wyjątek (stanie nie jest zawieszeniem)", b._watchdog_wyjatek() is True)
sprawdz("3e bez klawiszy i ataków", not s.klawisze and not s.ataki)

# zepchnięta z pola: wraca
s = Swiat(poz=(103, 99, 7)); b = zrob(s)
tiki(b, 20)
sprawdz("3f zepchnięta z pola wraca na pole", tuple(s.poz) == POLE, s.poz)

# aktywność (anty-idle): po AKTYWNOSC_MAX_S bez akcji krok w bok i z powrotem
s = Swiat(); b = zrob(s, {"STANOWISKO_AKTYWNOSC_MAX_S": 60}); b.aktywnosc_ts = 0
ruchy = set()
for _ in range(1500):
    b.tick(); ruchy.add(tuple(s.poz))
    if s.t > 900: break
sprawdz("3g anty-idle: bez akcji >60 s robi krok w bok i wraca", len(ruchy) >= 2 and tuple(s.poz) in ruchy and any("krok w bok" in l for l in b.slog), (sorted(ruchy)[:4], s.t))
sprawdz("3h anty-idle kończy na polu", tuple(s.poz) == POLE or max(abs(s.poz[0] - POLE[0]), abs(s.poz[1] - POLE[1])) <= 1, s.poz)
s = Swiat(); b = zrob(s, {"STANOWISKO_AKTYWNOSC_MAX_S": 0}); b.aktywnosc_ts = 0
tiki(b, 400)
sprawdz("3i AKTYWNOSC_MAX_S=0: nigdy nie rusza się z pola", tuple(s.poz) == POLE and s.t > 30, (s.poz, s.t))


# ---------- 4. PZ: atak, wróg, czaszka, HP ----------
def gracz(nazwa="Obcy", x=104, y=100, **kw):
    return {"id": 12, "nazwa": nazwa, "gracz": True, "x": x, "y": y, "z": 7, "hp": 100, **kw}

def do_pz(b, s, n=60):
    for _ in range(n):
        b.tick()
        if tuple(s.poz) == PZ: return True
    return False

s = Swiat(); s.stwory = [gracz(czaszka=1)]; b = zrob(s)
sprawdz("4a groźna czaszka: dociera do PZ", do_pz(b, s), s.poz)
sprawdz("4b w PZ: stan PZ, pk_stan nietknięty (None), brak wyprawy PK", b.stanowisko.stan == "PZ" and b.pk_stan is None, (b.stanowisko.stan, b.pk_stan))
sprawdz("4c alarm PK poszedł raz (krytyczny alarm tylko dla PK)", len(s.alarmy) >= 1, s.alarmy[:2])
tiki(b, 100)
sprawdz("4d czaszka dalej w widoku: zostaje w PZ", tuple(s.poz) == PZ and b.stanowisko.stan == "PZ", s.poz)
s.stwory.clear()
tiki(b, 200)
sprawdz("4e karencja trwa (30 min): po zniknięciu napastnika nadal w PZ", tuple(s.poz) == PZ and b.stanowisko.stan == "PZ", (s.poz, b.stanowisko.stan, round(s.t)))
s.t += 31 * 60
tiki(b, 40)
sprawdz("4f po karencji wraca na pole", tuple(s.poz) == POLE and b.stanowisko.stan == "POLE", (s.poz, b.stanowisko.stan))

# zwykły obcy gracz i rozmowa: bez reakcji
s = Swiat(); s.stwory = [gracz("Zwykly", 102, 100)]; b = zrob(s)
tiki(b, 120)
sprawdz("4g zwykły obcy gracz obok: bez ucieczki do PZ", tuple(s.poz) == POLE and b.stanowisko.stan == "POLE" and not s.alarmy, (s.poz, s.alarmy))

# GM w widoku: nie PK, bez PZ (obsługuje go istniejący stan GRACZ; spec: bez specjalnej reakcji)
s = Swiat(); s.stwory = [gracz("GM Test", 103, 100)]; b = zrob(s)
tiki(b, 30)
sprawdz("4h GM w widoku nie wysyła do PZ", b.stanowisko.stan != "PZ" and b.pk_stan is None, (b.stanowisko.stan, b.pk_stan))

# atak z danych: spadek HP bez potwora + gracz obok
s = Swiat(hp=100); s.stwory = [gracz("Napastnik", 101, 100)]; b = zrob(s)
tiki(b, 3)
s.hp = 70
tiki(b, 3)
s.hp = 40
wejscie = do_pz(b, s, 80)
sprawdz("4i atak gracza (spadek HP, brak potwora): do PZ", wejscie and b.stanowisko.pz_powod in ("atak", "HP", "HP niskie") or b.stanowisko.stan == "PZ", (s.poz, b.stanowisko.stan, b.stanowisko.pz_powod))
sprawdz("4j nie ustawia pk_stan ani wyprawy", b.pk_stan is None and not b.wypad_aktywny)

# znany wróg w widoku
s = Swiat(); b = zrob(s)
det, wr = b._pk_dane(); wr.dodaj("Znany Wrog", "test", (104, 100, 7))
s.stwory = [gracz("Znany Wrog", 105, 100)]
sprawdz("4k znany wróg w widoku: do PZ", do_pz(b, s), s.poz)

# niskie HP bez napastnika: do PZ i zostaje do 90%
s = Swiat(hp=40); b = zrob(s)
sprawdz("4l niskie HP (40%): marsz do PZ", do_pz(b, s), (s.poz, b.stanowisko.stan))
tiki(b, 30)
sprawdz("4m HP niskie: zostaje w PZ", tuple(s.poz) == PZ, s.poz)
s.hp = 95
tiki(b, 40)
sprawdz("4n HP 95%: wraca na pole (HP-powód bez karencji)", tuple(s.poz) == POLE and b.stanowisko.stan == "POLE", (s.poz, b.stanowisko.stan))

# regresja: ucieczka HP nie używa trasy ani flag uciekania po punktach
s = Swiat(hp=20); b = zrob(s)
do_pz(b, s)
sprawdz("4o ucieczka HP (20%): stan PZ, ucieczka po trasie nieużyta", b.stanowisko.stan == "PZ" and b.pk_stan is None)


# ---------- 5. filtr NPC i obcy gracz dla UH ----------
s = Swiat(); b = zrob(s, npc=("ebenizer", "mirabell"))
npc = {"id": 40, "nazwa": "Ebenizer", "gracz": True, "x": 103, "y": 100, "z": 7, "hp": 100}
obcy = gracz("Prawdziwy", 103, 101)
poz = POLE
sprawdz("5a NPC nie blokuje UH", b._uh_widoczny(npc, poz) is False)
sprawdz("5b obcy gracz blokuje UH (GRACZ_ODL=0)", b._uh_widoczny(obcy, poz) is True)
sprawdz("5c NPC nie jest obcym graczem", b.inni_gracze([npc, obcy], poz) == [obcy], [x["nazwa"] for x in b.inni_gracze([npc, obcy], poz)])
sprawdz("5d NPC z czaszką (podszywka) nie jest ignorowany", b.stanowisko.ignoruj(dict(npc, czaszka=1)) is False)
b2 = zrob(s, {"STANOWISKO_GRACZ_ODL": 3}, npc=("ebenizer",))
sprawdz("5e GRACZ_ODL=3: obcy w odl 3 nie blokuje, w odl 2 blokuje",
        b2._uh_widoczny(gracz("A", 103, 100), poz) is False and b2._uh_widoczny(gracz("A", 102, 100), poz) is True)
b3 = zrob(s, {"STANOWISKO_NPC_IGNORUJ": 0}, npc=("ebenizer",))
sprawdz("5f NPC_IGNORUJ=0: NPC blokuje jak gracz", b3._uh_widoczny(npc, poz) is True)
sprawdz("5g nazwy_npc() czyta serwis_akcje (co najmniej jeden NPC Thais)", len(stanowisko.nazwy_npc()) > 0, len(stanowisko.nazwy_npc()))
# regresja: bez stanowiska NPC i graczy liczy dawna logika
sb = Swiat(); bb = cavebot.Cavebot(P(sb), [POLE], zapytaj=sb.zapytaj, atak=lambda *a: None, alarm=lambda w: None, spij=sb.spij, zegar=sb.zegar)
sprawdz("5h bez stanowiska: NPC-gracz blokuje UH i liczy się jako obcy (zachowanie jak dotąd)",
        bb.stanowisko is None and bb._uh_widoczny(npc, poz) is True and bb.inni_gracze([npc, obcy], poz) == [npc, obcy])
sprawdz("5i bez stanowiska: watchdog nie ma wyjątku w IDZ", bb._watchdog_wyjatek() is False)


# ---------- 6. serwis zamiast wyprawy; refill; brak STOP z braku postępu ----------
class FakeWyprawa:
    def __init__(s, refill=("czeka", "ok")):
        s.refill = refill; s.stopy = []; s.starty = []; s.pow = []
    def _auto_refill(s, poz): return s.refill
    def _zapisz_stop(s, powod): s.stopy.append(powod)
    def _auto_refill_start(s, r): s.starty.append(r)
    def _powiadom(s, *a, **k): s.pow.append(a)

s = Swiat(); b = zrob(s, {"WROC_REFILL": 1}); w = FakeWyprawa(); b.wyprawa = w
sprawdz("6a zlec_serwis zwraca True za pierwszym razem", b.stanowisko.zlec_serwis("zapas", {}, s.t) is True)
sprawdz("6b drugi raz idempotentny (False)", b.stanowisko.zlec_serwis("zapas", {}, s.t) is False)
for _ in range(80):
    b.tick()
    if w.stopy: break
sprawdz("6c dochodzi do depo", tuple(s.poz) == DEPO, s.poz)
sprawdz("6d refill 'czeka': jeden STOP z powodem + start refillu", len(w.stopy) == 1 and len(w.starty) == 1, (w.stopy, w.starty))

s = Swiat(); b = zrob(s, {"WROC_REFILL": 1}); w = FakeWyprawa(("pominiety", "pelny")); b.wyprawa = w
b.stanowisko.zlec_serwis("glod", {}, s.t); tiki(b, 120)
sprawdz("6e refill 'pominiety': zero STOP, stoi w depo i ponawia", tuple(s.poz) == DEPO and not w.stopy and not w.starty, (s.poz, w.stopy))
t0 = s.t; tiki(b, 400)
sprawdz("6f ponowienie decyzji co 300 s bez STOP", not w.stopy and s.t - t0 > 60, (round(s.t - t0), w.stopy))
sprawdz("6g powiadomienie 'serwis czeka' bez poziomu critical", any(k == "stanowisko_serwis" for _, k in POWIADOMIENIA))

s = Swiat(); b = zrob(s, {"WROC_REFILL": 0}); w = FakeWyprawa(); b.wyprawa = w
b.stanowisko.zlec_serwis("blanki", {}, s.t); tiki(b, 120)
sprawdz("6h WROC_REFILL=0: nie startuje refillu ani STOP (człowiek decyduje)", not w.stopy and not w.starty and tuple(s.poz) == DEPO)

# _start_wyprawa z Wyprawy deleguje do stanowiska (bez planu wyprawy)
s = Swiat(); b = zrob(s, {"WROC_REFILL": 1}); w = wyprawa.Wyprawa.__new__(wyprawa.Wyprawa)
w.cb = b; w.glod_potw_do = 0.0; w.nast_wyprawa = 0.0; w.potw_w = 5; w.log = lambda *a: None; w._tele = lambda *a, **k: None
odl = []; w._odloz = lambda teraz, powod, sek: odl.append((powod, sek))
sprawdz("6i _start_wyprawa przy stanowisku: serwis stanowiska, True", w._start_wyprawa("depo:zapas", {"depo": True}, 5.0) is True and b.stanowisko.stan == "SERWIS")
sprawdz("6j ponowny _start_wyprawa: False + odroczenie 120 s", w._start_wyprawa("depo:zapas", {"depo": True}, 6.0) is False and odl and odl[-1][1] == 120.0, odl)
w._uh_blokuje = lambda: False
sprawdz("6k _blokada_startu nie blokuje 'gracz' przy stanowisku", w._blokada_startu(7.0, POLE, [gracz("Obcy", 105, 100)]) is None, w._blokada_startu(7.0, POLE, [gracz("Obcy", 105, 100)]))

# serwis z HP < HP_PZ nie jest przerywany przez PZ (depo to PZ), ale atak przerywa
s = Swiat(); b = zrob(s, {"WROC_REFILL": 1}); b.wyprawa = FakeWyprawa(("pominiety", "x"))
b.stanowisko.zlec_serwis("zapas", {}, s.t); s.stwory = [gracz(czaszka=1)]
tiki(b, 40)
sprawdz("6l atak w trakcie serwisu: stan PZ, serwis anulowany", b.stanowisko.stan == "PZ" and b.stanowisko.serwis is None, b.stanowisko.stan)


# ---------- 7. limit zmiany (3 h) ----------
fw = [10_000.0]
s = Swiat(); b = zrob(s, {"STANOWISKO_ZMIANA_MAX_MIN": 180}, wall=lambda: fw[0], plik_stanu=TMP / "stan1.json")
tiki(b, 20)
sprawdz("7a w trakcie zmiany stoi na polu", tuple(s.poz) == POLE and not b.stanowisko.koniec_zmiany)
fw[0] += 181 * 60
tiki(b, 60)
sprawdz("7b po 3 h: koniec zmiany, do PZ (bez STOP)", b.stanowisko.koniec_zmiany and tuple(s.poz) == PZ and b.stanowisko.stan == "PZ", (s.poz, b.stanowisko.stan))
tiki(b, 200)
sprawdz("7c po końcu zmiany nie wraca na pole", tuple(s.poz) == PZ)
sprawdz("7d powiadomienie o końcu zmiany nie jest krytyczne", any(k == "stanowisko_zmiana" for _, k in POWIADOMIENIA))
# restart w tej samej zmianie: licznik trwa; po dłuższej przerwie od zera
b_re = zrob(Swiat(), {"STANOWISKO_ZMIANA_MAX_MIN": 180}, wall=lambda: fw[0] + 60, plik_stanu=TMP / "stan1.json")
b_re.stanowisko._zapisz_stan(fw[0] + 60, wymus=True)
b_re2 = zrob(Swiat(), {"STANOWISKO_ZMIANA_MAX_MIN": 180}, wall=lambda: fw[0] + 120, plik_stanu=TMP / "stan1.json")
sprawdz("7e restart tuż po zapisie dziedziczy początek zmiany", abs(b_re2.stanowisko.zmiana_start - b_re.stanowisko.zmiana_start) < 1.0, (b_re.stanowisko.zmiana_start, b_re2.stanowisko.zmiana_start))
b_re3 = zrob(Swiat(), {"STANOWISKO_ZMIANA_MAX_MIN": 180}, wall=lambda: fw[0] + 60 + 2 * 3600, plik_stanu=TMP / "stan1.json")
sprawdz("7f po przerwie > 20 min nowa zmiana (licznik od zera)", b_re3.stanowisko.zmiana_start >= fw[0] + 3600, b_re3.stanowisko.zmiana_start)
s = Swiat(); b = zrob(s, {"STANOWISKO_ZMIANA_MAX_MIN": 0}, wall=lambda: fw[0] + 99 * 3600)
tiki(b, 20)
sprawdz("7g ZMIANA_MAX_MIN=0: bez limitu", not b.stanowisko.koniec_zmiany and tuple(s.poz) == POLE)


# ---------- 8. Koordynator: jedna postać na miasto ----------
plik_k = TMP / "zajete.json"
zywe = {111, 222}
tk = [1000.0]
kA = miejsca_koord.Koordynator(plik=plik_k, id_instancji="a", pid=111, zegar=lambda: tk[0], zyje=lambda p: p in zywe)
kB = miejsca_koord.Koordynator(plik=plik_k, id_instancji="b", pid=222, zegar=lambda: tk[0], zyje=lambda p: p in zywe)
sA = Swiat(); bA = zrob(sA, koord=kA, mapa=dict(MAPA, miasto="Koordtown"))
sB = Swiat(); bB = zrob(sB, koord=kB, mapa=dict(MAPA, miasto="Koordtown"))
tiki(bA, 5)
tiki(bB, 5)
sprawdz("8a pierwsza postać dostaje miasto", bA.stanowisko.koord_ok is True)
sprawdz("8b druga (to samo miasto) nie dostaje: czeka w PZ, bez STOP", bB.stanowisko.koord_ok is False and bB.stanowisko.stan == "PZ", (bB.stanowisko.koord_ok, bB.stanowisko.stan))
tiki(bB, 60)
sprawdz("8c druga stoi w PZ, nie na polu", tuple(sB.poz) == PZ)
sprawdz("8d klucz rezerwacji = stoj_<miasto>", miejsca_koord.klucz_stanowiska("Koordtown") == "stoj_koordtown" and "stoj_koordtown" in json.loads(plik_k.read_text()))
zywe.discard(111)                                       # pierwszy proces umarł bez zwolnienia
tk[0] += 100.0
bB.stanowisko.koord_ost = float("-inf")
tiki(bB, 80)
sprawdz("8e po śmierci pierwszej druga przejmuje miasto i wraca na pole", bB.stanowisko.koord_ok is True and tuple(sB.poz) == POLE, (bB.stanowisko.koord_ok, sB.poz))
bB.stanowisko.zamknij()
sprawdz("8f zamknij() zwalnia rezerwację", "stoj_koordtown" not in json.loads(plik_k.read_text()))
s = Swiat(); b = zrob(s, koord=miejsca_koord.Koordynator(plik=plik_k, id_instancji="c", pid=222, zegar=lambda: tk[0], zyje=lambda p: True), mapa=dict(MAPA, miasto="Inne"))
tiki(b, 5)
sprawdz("8g inne miasto = osobny klucz, brak konfliktu", b.stanowisko.koord_ok is True)


# ---------- 9. _stanowisko_sync: podwójne bramkowanie (pokrętło + plik mapy) ----------
orig_inst, orig_kk, orig_st = cavebot.instancja, miejsca_koord.Koordynator, cavebot.STANOWISKO
try:
    kat2 = TMP / "inst2"; kat2.mkdir()
    cavebot.instancja = types.SimpleNamespace(S=types.SimpleNamespace(stan=kat2), ID="t")
    miejsca_koord.Koordynator = lambda *a, **k: miejsca_koord.Koordynator.__wrapped__(*a, **k) if False else orig_kk(plik=TMP / "z2.json", id_instancji="t", pid=222, zyje=lambda p: True)
    s = Swiat()
    b = cavebot.Cavebot(P(s), [POLE], zapytaj=s.zapytaj, atak=lambda *a: None, alarm=lambda w: None, spij=s.spij, zegar=s.zegar)
    cavebot.STANOWISKO = 0
    b._stanowisko_sync()
    sprawdz("9a STANOWISKO=0: moduł nieaktywny", b.stanowisko is None)
    cavebot.STANOWISKO = 1
    b._stanowisko_sync()
    sprawdz("9b STANOWISKO=1 bez pliku mapy: nieaktywne, jedna próba", b.stanowisko is None and b.stanowisko_proba is True
            and any("brak poprawnego stanowisko_mapa.json" in l for l in CAVELOG))
    (kat2 / "stanowisko_mapa.json").write_text(json.dumps(MAPA | {"pola": [list(POLE)], "pz": [list(PZ)], "depo": list(DEPO)}))
    b._stanowisko_sync()
    sprawdz("9c jedna próba na włączenie: plik pojawia się, ale bez zmiany pokrętła nadal nieaktywne", b.stanowisko is None)
    cavebot.STANOWISKO = 0; b._stanowisko_sync(); cavebot.STANOWISKO = 1; b._stanowisko_sync()
    sprawdz("9d po cyklu 0->1 z plikiem: aktywne, pokrętła czytane z modułu cavebot", b.stanowisko is not None and b.stanowisko.pole == POLE
            and b.stanowisko.k("STANOWISKO_HP_PZ") == cavebot.STANOWISKO_HP_PZ)
    cavebot.STANOWISKO_HP_PZ = 55
    sprawdz("9e pokrętło na żywo (gorące przeładowanie) działa", b.stanowisko.k("STANOWISKO_HP_PZ") == 55)
    cavebot.STANOWISKO_HP_PZ = 70
    cavebot.STANOWISKO = 0; b._stanowisko_sync()
    sprawdz("9f STANOWISKO=0 w locie: moduł zwolniony", b.stanowisko is None and b.stanowisko_proba is False)
finally:
    cavebot.instancja, miejsca_koord.Koordynator, cavebot.STANOWISKO = orig_inst, orig_kk, orig_st


# ---------- 10. nadzorca: stanowisko nie jest zacięciem ----------
class FakeNadz:
    konf = {"stoi_min": 10, "brak_zabic_min": 20}
    korzen = TMP
_N = nadzor.Nadzorca.__dict__["zaciecie"]
fn = FakeNadz()
fn._stanowisko = lambda id_, teraz: nadzor.Nadzorca._stanowisko(fn, id_, teraz)
tele_stoi = {"tele": {"wiek_probki_s": 5, "stoi_poza_walka_s": 3600}}
orig_mt = nadzor.mapa_tryb_biezace
try:
    nadzor.mapa_tryb_biezace = lambda korzen, id_, teraz=None: ("raty", "raty", "tryb.log")
    sprawdz("10a zwykła mapa: stanie 1 h poza walką = zacięcie (jak dotąd)", _N(fn, "x", tele_stoi, {}, {}, 0) is not None)
    nadzor.mapa_tryb_biezace = lambda korzen, id_, teraz=None: ("stoj_runy_thais", "uh,stoj", "tryb.log")
    sprawdz("10b stoj_runy_thais: stanie 1 h nie jest zacięciem", _N(fn, "x", tele_stoi, {}, {}, 0) is None)
    sprawdz("10c stoj_runy_thais: stara telemetria nadal = zawieszenie", _N(fn, "x", {"tele": {"wiek_probki_s": 300}}, {}, {}, 0) is not None)
    def wywal(*a, **k): raise RuntimeError("tryb.log nieczytelny")
    nadzor.mapa_tryb_biezace = wywal
    sprawdz("10d błąd odczytu mapy: zachowanie jak dotąd (nie stanowisko)", _N(fn, "x", tele_stoi, {}, {}, 0) is not None)
finally:
    nadzor.mapa_tryb_biezace = orig_mt


# ---------- 11. regresja: mapa bez stanowiska ----------
cavebot.STANOWISKO = 0
sb = Swiat(); bb = cavebot.Cavebot(P(sb), [(100 + i, 100, 7) for i in range(1, 6)], zapytaj=sb.zapytaj, atak=lambda *a: None,
                                   alarm=lambda w: None, spij=sb.spij, zegar=sb.zegar, okrazenia=1)
tiki(bb, 20)
sprawdz("11a bez stanowiska trasa idzie jak dotąd (ruch wzdłuż trasy)", sb.poz[0] > 100 and bb.stanowisko is None, sb.poz)
sb = Swiat(); sb.stwory = [gracz(czaszka=1)]
bb = cavebot.Cavebot(P(sb), [(100 + i, 100, 7) for i in range(1, 6)], zapytaj=sb.zapytaj, atak=lambda *a: None,
                     alarm=lambda w: None, spij=sb.spij, zegar=sb.zegar)
bb._alarm_pk = lambda t: None; bb._pk_powiadom = lambda *a, **k: None
tiki(bb, 3)
sprawdz("11b bez stanowiska czaszka = zwykła ucieczka PK (pk_stan UCIECZKA)", bb.pk_stan == "UCIECZKA", bb.pk_stan)

wyniki = [x for x in ok]
print(f"\n{sum(wyniki)}/{len(wyniki)} OK")
sys.exit(0 if all(wyniki) else 1)
