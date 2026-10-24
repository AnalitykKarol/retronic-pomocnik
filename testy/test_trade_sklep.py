import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
"""Testy offline sklepu na postaci-magazynie (23.10): kalibracja zakładek czatu Trade/Default dla ekranu 1175x910,
wysyłka na Trade przy szarej (cichej) zakładce, STOP w pętli --bez-ruchu, pokrętła (trade_sklep.py) oraz skrypty
trade_start.sh / trade_stop.sh na atrapie instancji (bez gry, bez inputu; procesy-wabiki to `sleep` w pythonie).
Zero inputu do gry: kliknij/wpisz/zrzut to atrapy; wpisz_na_czacie zablokowane."""
import json, os, shutil, signal, subprocess, sys, tempfile, time, types
sys.dont_write_bytecode = True
KAT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KAT)
from pathlib import Path
from PIL import Image
import bot, mozg, trade_sklep

DANE = Path(KAT) / "testy" / "dane"
ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK  " if warunek else "FAIL"), nazwa, info)

def zakaz(*a, **k): raise AssertionError("INPUT DO GRY w teście!")
mozg.wpisz_na_czacie = zakaz

def wczytaj(nazwa, rozmiar=(1175, 910)):
    """Pasek zakładek (prawdziwy wycinek y755-800 ze zrzutu sesji) na czarnym płótnie jak ekran sesji."""
    wyc = Image.open(DANE / nazwa).convert("RGB")
    if wyc.size == rozmiar:
        return wyc
    p = Image.new("RGB", rozmiar, (0, 0, 0)); p.paste(wyc, (0, 0)); return p

# --- 1. kalibracja 1175x910 na prawdziwych zrzutach -----------------------------------------
TRADE = wczytaj("trade_zakladki_1175_trade.png")                # kutangen: Default szara, Trade biała
DEFAULT = wczytaj("trade_zakladki_1175_default.png")            # odchyd: Default biała, Trade czerwona
SZARA = wczytaj("trade_zakladki_1175_default_szara.png")        # Default biała, Trade szara (cichy kanał)
sprawdz("1a ekran 1175x910 ma układ", mozg.uklad_paska((1175, 910)) is not None)
sprawdz("1b Trade aktywna (biała)", mozg.stan_zakladek(TRADE) == {"Default": "nieaktywna", "Trade": "aktywna"}, str(mozg.stan_zakladek(TRADE)))
sprawdz("1c Default aktywna, Trade nieaktywna (czerwona)", mozg.stan_zakladek(DEFAULT) == {"Default": "aktywna", "Trade": "nieaktywna"}, str(mozg.stan_zakladek(DEFAULT)))
sprawdz("1d Trade nieaktywna także, gdy szara (bez nowych wiadomości)", mozg.stan_zakladek(SZARA) == {"Default": "aktywna", "Trade": "nieaktywna"}, str(mozg.stan_zakladek(SZARA)))
sprawdz("1e rozmiar bez kalibracji: 'brak', nie zgadujemy", mozg.stan_zakladek(Image.new("RGB", (1000, 900))) == {"Default": "brak", "Trade": "brak"})
sprawdz("1f stary wzorzec 734x910 zostaje", mozg.uklad_paska((734, 910)) is not None and mozg.uklad_paska((734, 910)) is not mozg.uklad_paska((1175, 910)))
sprawdz("1g skalowanie 2x wzorca 1175 rozpoznane", mozg.uklad_paska((2350, 1820)) is mozg.uklad_paska((1175, 910)))
u = mozg.uklad_paska((1175, 910))
sprawdz("1h pola Default i Trade nie nachodzą na Server Log ani siebie",
        u["zakladki_x"]["Default"][1] < u["zakladki_x"]["Trade"][0] and u["klik"]["Default"][0] < u["klik"]["Trade"][0])
# klik w zakładkę ląduje w jej własnych granicach na prawdziwym zrzucie (Default x46-100, Trade x196-240 px)
kl = {n: round(c[0] * 1175) for n, c in u["klik"].items()}
sprawdz("1i punkty kliku mieszczą się w zakładkach (piksele 1175, y w ramce 764-783)",
        46 <= kl["Default"] <= 100 and 196 <= kl["Trade"] <= 240 and all(764 <= round(c[1] * 910) <= 783 for c in u["klik"].values()), str(kl))

# --- 2. wyslij_na_trade na zrzutach 1175 (w tym szara Trade) --------------------------------
class Ekran:
    def __init__(s, domyslny):
        s.akt, s.domyslny, s.zdarzenia = "Default", domyslny, []
    def zrzut(s): return TRADE if s.akt == "Trade" else s.domyslny
    def kliknij(s, n): s.zdarzenia.append(("klik", n)); s.akt = n
    def wpisz(s, t): s.zdarzenia.append(("wpisz", t, s.akt)); return True
    def go(s):
        return mozg.wyslij_na_trade("=== SELL 2 BP UH 2.3k each === EDRON ===", zrzut=s.zrzut, kliknij=s.kliknij,
                                     rusz_mysz=lambda: None, wpisz=s.wpisz, anuluj=lambda: s.zdarzenia.append(("escape",)),
                                     puszczone=lambda: True, spij=lambda x: None)
for nazwa, obraz in (("czerwona Trade (odchyd)", DEFAULT), ("szara Trade (kutangen, cichy kanał)", SZARA)):
    e = Ekran(obraz); w = e.go()
    sprawdz(f"2 wysyłka na 1175, {nazwa}", w == (True, "", True) and ("wpisz", "=== SELL 2 BP UH 2.3k each === EDRON ===", "Trade") in e.zdarzenia
            and e.akt == "Default", f"{w} {e.zdarzenia}")
e = Ekran(Image.new("RGB", (1000, 900))); w = e.go()
sprawdz("2c ekran bez kalibracji: nic nie wpisuje", not w[0] and not any(x[0] == "wpisz" for x in e.zdarzenia), str(w))

# --- 3. --bez-ruchu: STOP zatrzymuje pętlę, pokrętła odświeżane ------------------------------
stop_tmp = Path(tempfile.mkdtemp(prefix="pomocnik-sklep-")) / "STOP"
stare_stop, stare_env = bot.STOP, os.environ.pop("RETRONIC_TESTY")
try:
    bot.STOP = stop_tmp
    wywolania = []
    cb = types.SimpleNamespace(pokretla=types.SimpleNamespace(odswiez=lambda: wywolania.append("odswiez")), pokretla_ost=0.0)
    m = types.SimpleNamespace(cb=cb, zegar=lambda: 100.0)
    mozg.Mozg.tik_bez_ruchu(m, spij=lambda x: None)
    sprawdz("3a bez STOP: pokrętła odświeżone, pętla idzie dalej", wywolania == ["odswiez"], str(wywolania))
    stop_tmp.touch()
    try:
        mozg.Mozg.tik_bez_ruchu(m, spij=lambda x: None); zatrzymano = False
    except bot.Zatrzymano:
        zatrzymano = True
    sprawdz("3b plik STOP zatrzymuje pętlę --bez-ruchu", zatrzymano)
finally:
    bot.STOP = stare_stop
    os.environ["RETRONIC_TESTY"] = stare_env
    shutil.rmtree(stop_tmp.parent, ignore_errors=True)

# --- 4. pokrętła sklepu (trade_sklep.py) ----------------------------------------------------
tmp = Path(tempfile.mkdtemp(prefix="pomocnik-sklep-nz-"))
nz = tmp / "na_zywo.json"
sprawdz("4a brak pliku: wlacz tworzy go", trade_sklep.ustaw(nz, True) and json.loads(nz.read_text()) == {"TRADE_OGLOSZENIA": 1, "TRADE_PRIV_ODPOWIEDZI": 1})
sprawdz("4b drugie wlacz: bez zmian", trade_sklep.ustaw(nz, True) is False)
nz.write_text(json.dumps({"PROG_HP": 40, "TRADE_OGLOSZENIA": 0}))
trade_sklep.ustaw(nz, True)
d = json.loads(nz.read_text())
sprawdz("4c inne pokrętła nietknięte, kopia pliku istnieje", d["PROG_HP"] == 40 and d["TRADE_OGLOSZENIA"] == 1 and list(tmp.glob("na_zywo.json.bak-*-sklep")))
trade_sklep.ustaw(nz, False)
sprawdz("4d wylacz usuwa tylko klucze sklepu", json.loads(nz.read_text()) == {"PROG_HP": 40})
nz.write_text("{zepsute")
try:
    trade_sklep.ustaw(nz, True); zepsuty = False
except ValueError:
    zepsuty = True
sprawdz("4e zepsuty JSON: błąd i plik nietknięty", zepsuty and nz.read_text() == "{zepsute")
import pokretla
sprawdz("4f wartości przechodzą walidację pokręteł", not pokretla.waliduj({"TRADE_OGLOSZENIA": 1, "TRADE_PRIV_ODPOWIEDZI": 1})[1])
shutil.rmtree(tmp, ignore_errors=True)

# --- 5. skrypty na atrapie instancji ----------------------------------------------------------
A, B = "tsklepa", "tsklepb"
inst = {i: Path(KAT) / "instancje" / i for i in (A, B)}
wabiki = []
def skrypt(nazwa, *arg, id_=None):
    env = {k: v for k, v in os.environ.items() if k not in ("RETRONIC_ID", "RETRONIC_POSTAC")}
    r = subprocess.run(["bash", str(Path(KAT) / nazwa), *arg], capture_output=True, text=True, timeout=60, env=env)
    return r.returncode, r.stdout + r.stderr
def wabik(id_):
    env = dict(os.environ, RETRONIC_ID=id_)
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)", "mozg.py", "--tryb", "skrypt", "--bez-ruchu"], env=env)
    wabiki.append(p); return p
def zyje(p): return p.poll() is None
try:
    for d_ in inst.values():
        (d_ / "logi").mkdir(parents=True, exist_ok=True)
    kod, wyj = skrypt("trade_start.sh"); sprawdz("5a start bez id: użycie, kod 2", kod == 2, wyj[:80])
    kod, wyj = skrypt("trade_start.sh", "nie_ma_takiej"); sprawdz("5b nieznana instancja: kod 1, nic nie tworzy", kod == 1 and not (Path(KAT) / "instancje" / "nie_ma_takiej").exists(), wyj[:80])
    kod, wyj = skrypt("trade_stop.sh"); sprawdz("5c stop bez id: użycie, kod 2", kod == 2, wyj[:80])
    # STOP_RECZNY (ktoś gra): start odmawia, nic nie kasuje, nie dotyka na_zywo.json
    (inst[A] / "STOP_RECZNY").touch(); (inst[A] / "STOP").touch()
    kod, wyj = skrypt("trade_start.sh", A)
    sprawdz("5d STOP/STOP_RECZNY bez --usun-stop: odmowa, pliki zostają", kod == 1 and "Traceback" not in wyj and "STOP_RECZNY" in wyj and (inst[A] / "STOP_RECZNY").exists() and (inst[A] / "STOP").exists()
            and not (inst[A] / "na_zywo.json").exists(), wyj[:200])
    # z --usun-stop, ale bez gry (brak gniazda): odmowa PRZED kasowaniem STOP i zapisem pokręteł
    kod, wyj = skrypt("trade_start.sh", A, "--usun-stop")
    sprawdz("5e brak gry + --usun-stop: kod 1, STOP nie skasowany, pokrętła nie ruszone", kod == 1 and (inst[A] / "STOP_RECZNY").exists()
            and (inst[A] / "STOP").exists() and not (inst[A] / "na_zywo.json").exists() and "nie działa" in wyj, wyj[:160])
    # działający mózg tej instancji blokuje start (wabik z RETRONIC_ID=A i cmdline mozg.py)
    for f in ("STOP", "STOP_RECZNY"): (inst[A] / f).unlink()
    pa, pb = wabik(A), wabik(B); time.sleep(1)
    kod, wyj = skrypt("trade_start.sh", A)
    sprawdz("5f drugi mózg na tej samej instancji: odmowa z PID", kod == 1 and str(pa.pid) in wyj and str(pb.pid) not in wyj, wyj[:160])
    # stop: zabija tylko mózg instancji A, B (cudzy bot) przeżywa; pokrętła cofnięte; STOP + STOP_RECZNY założone
    (inst[A] / "na_zywo.json").write_text(json.dumps({"PROG_HP": 40, "TRADE_OGLOSZENIA": 1, "TRADE_PRIV_ODPOWIEDZI": 1}))
    kod, wyj = skrypt("trade_stop.sh", A)
    time.sleep(0.5)
    sprawdz("5g stop: ginie tylko proces instancji A", kod == 0 and not zyje(pa) and zyje(pb), f"A={pa.poll()} B={pb.poll()} {wyj[:120]}")
    sprawdz("5h stop: pokrętła cofnięte, reszta na_zywo.json bez zmian", json.loads((inst[A] / "na_zywo.json").read_text()) == {"PROG_HP": 40})
    sprawdz("5i stop: STOP i STOP_RECZNY założone po zabiciu", (inst[A] / "STOP").exists() and (inst[A] / "STOP_RECZNY").exists())
    kod, wyj = skrypt("trade_stop.sh", A)
    sprawdz("5j stop bez procesu: kod 0, komunikat, B nadal żyje", kod == 0 and "Nie działa" in wyj and zyje(pb), wyj[:120])
finally:
    for p in wabiki:
        if p.poll() is None:
            p.send_signal(signal.SIGTERM)
            try: p.wait(5)
            except subprocess.TimeoutExpired: p.kill()
    for d_ in inst.values():
        shutil.rmtree(d_, ignore_errors=True)

print(f"WYNIK: {sum(ok)} / {len(ok)}")
sys.exit(0 if all(ok) else 1)
