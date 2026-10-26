"""Powiadomienia o czacie (powiadom_czat.py, 26.10): wisper/priv = dymek PILNY + wpis w logu (czas, nick, pełna treść), Trade
i Server Log pomijane, zerwanie gniazda strażnika i powrót (log „przerwa” / „wznowione”), brak duplikatu procesu przy dwóch
startach (--uruchom po /proc i flock w samym czytniku). Atrapa strażnika = gniazdo unix w katalogu tymczasowym; dymek =
skrypt zapisujący argumenty do pliku (nic nie idzie do prawdziwego notify-send, nic do gry).
Uruchomienie: RETRONIC_TESTY=1 python3 -I testy/test_powiadom_czat.py"""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, pathlib, socket, subprocess, sys, tempfile, threading, time
sys.dont_write_bytecode = True

tmp = pathlib.Path(tempfile.mkdtemp(prefix="pc"))
_os.environ["XDG_RUNTIME_DIR"] = str(tmp / "rt")
(tmp / "rt").mkdir()
KAT = tmp / "kat"
(KAT / "instancje" / "tst" / "logi").mkdir(parents=True)
(KAT / "instancje" / "tst" / "profil.json").write_text(json.dumps({"postac": "Kutangen", "powiadom_czat": True}))
NOTIFY = tmp / "notify.sh"
DYMKI = tmp / "dymki.txt"
NOTIFY.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "' + str(DYMKI) + '"\n')
NOTIFY.chmod(0o755)
_os.environ.update(RETRONIC_POWIADOM_NOTIFY=str(NOTIFY), RETRONIC_POWIADOM_ODSWIEZ_S="0.05", RETRONIC_POWIADOM_PONOW_S="0.1",
                   RETRONIC_POWIADOM_KATALOG=str(KAT))
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import instancja, powiadom_czat as pc

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))

def czekaj(warunek, limit=6.0):
    k = time.time() + limit
    while time.time() < k:
        if warunek():
            return True
        time.sleep(0.03)
    return False

def dymki():
    return DYMKI.read_text().splitlines() if DYMKI.exists() else []

S = instancja.sciezki("tst", tmp / "rt", KAT)
LOG = lambda: pathlib.Path(S.logi / f"powiadom-czat-{time.strftime('%Y%m%d')}.log").read_text() if (S.logi / f"powiadom-czat-{time.strftime('%Y%m%d')}.log").exists() else ""

# ---- 1. rodzaj() na samych danych (bez gniazda)
def w(tekst, nadawca=None, kolor="ffff00", kanal=None, bufor="0x1", ts=None):
    return {"tekst": tekst, "nadawca": nadawca, "kolor": kolor, "kanal": kanal, "bufor": bufor, "ts": ts}
B = pc.Bufory()
JA = "Kutangen"
sprawdz("1a priv kolorem klienta z nadawcą", pc.rodzaj(w("2k each?", "Malik", "5ff7f7"), B, {}, JA) == "priv")
sprawdz("1b wisper bez nadawcy, tylko „Nick [lvl]:” w tekście, kolor priv", pc.rodzaj(w("Buyer [45]: i buy all hmm", None, "5ff7f7"), B, {}, JA) == "priv")
sprawdz("1c wisper „Nick whispers:” żółty, bez kanału", pc.rodzaj(w("Zed whispers: sell all?", None, "ffff00"), B, {}, JA) == "priv")
sprawdz("1d nadawca „Zed whispers” (strażnik wziął czasownik do nicku)", pc.rodzaj(w("hi", "Zed whispers", "ffff00"), B, {}, JA) == "priv")
sprawdz("1e nieznany kanał + kolor spoza priv i spoza żółtego = pilny", pc.rodzaj(w("take all", "Bob", "abcdef"), B, {}, JA) == "priv")
sprawdz("1f mowa lokalna żółta w Default = zwykły dymek", pc.rodzaj(w("hello", "Bob", "ffff00", "Default"), B, {}, JA) == "obok")
sprawdz("1g zakładka nazwana inaczej niż Default = pilny", pc.rodzaj(w("psst", "Bob", "ffff00", "Bob"), B, {}, JA) == "priv")
sprawdz("1h Server Log pominięty", pc.rodzaj(w("Bob: x", "Bob", "5ff7f7", "Server Log"), B, {}, JA) is None)
sprawdz("1i Trade pominięty po nazwie", pc.rodzaj(w("sell hmm", "Bob", "ffff00", "Trade"), B, {}, JA) is None)
sprawdz("1j własna wiadomość „Kutangen [8]: …” pominięta", pc.rodzaj(w("Kutangen [8]: sell hmm", None, "9f9dfd"), B, {}, JA) is None)
sprawdz("1k wiadomość systemowa „Loot of a rat: gold” to nie gracz", pc.rodzaj(w("Loot of a rat: gold coin", None, "5ff7f7"), B, {}, JA) is None)
sprawdz("1l zwykły tekst bez nadawcy i bez [lvl]/czasownika = pomiń", pc.rodzaj(w("coś: tam", None, "5ff7f7"), B, {}, JA) is None)
for i in range(4):
    B.dodaj("0xT", "WTS hmm 1k")
sprawdz("1m bufor ogłoszeń (Trade po treści) = pominięty", pc.rodzaj(w("sell bp hmm", "Bob", "ffff00", None, "0xT"), B, {}, JA) is None)
sprawdz("1n wisper w buforze ogłoszeń (kolor priv) nadal pilny", pc.rodzaj(w("buy all?", "Bob", "5ff7f7", None, "0xT"), B, {}, JA) == "priv")
sprawdz("1o nie-ogłoszenie o kolorze spoza żółtego w buforze ogłoszeń = pilny", pc.rodzaj(w("how much for all", "Bob", "abcdef", None, "0xT"), B, {}, JA) == "priv")

# ---- 2. atrapa strażnika
class Straznik:
    def __init__(self, gniazdo, epoka="E1"):
        self.gniazdo, self.epoka, self.msgs, self.zywy = gniazdo, epoka, [], False
        self.zapytania = 0
    def dodaj(self, **m):
        m["nr"] = len(self.msgs) + 1
        self.msgs.append(m)
    def start(self):
        if pathlib.Path(self.gniazdo).exists():
            pathlib.Path(self.gniazdo).unlink()
        self.so = socket.socket(socket.AF_UNIX); self.so.bind(str(self.gniazdo)); self.so.listen(4); self.so.settimeout(0.1)
        self.zywy = True
        self.t = threading.Thread(target=self._pet, daemon=True); self.t.start()
    def stop(self):
        self.zywy = False; self.t.join(2); self.so.close()
        if pathlib.Path(self.gniazdo).exists():
            pathlib.Path(self.gniazdo).unlink()
    def _pet(self):
        while self.zywy:
            try:
                c, _ = self.so.accept()
            except (socket.timeout, OSError):
                continue
            with c, c.makefile("rwb") as f:
                z = json.loads(f.readline()); self.zapytania += 1
                od = z.get("od") if z.get("epoka") == self.epoka else None
                lista = [m for m in self.msgs if od is None or m["nr"] > od]
                f.write((json.dumps({"ok": True, "wiadomosci": lista, "znacznik": len(self.msgs), "epoka": self.epoka, "kanaly": {}}) + "\n").encode())
                f.flush()

sv = Straznik(S.gniazdo)
sv.dodaj(tekst="Old [30]: starocie sprzed startu", nadawca=None, kolor="5ff7f7", kanal=None, bufor="0x1", ts=time.time() - 7200, czas="07:00")
for i in range(4):
    sv.dodaj(tekst=f"WTS hmm {i}k", nadawca="Seller", kolor="ffff00", kanal=None, bufor="0xT", ts=time.time() - 3000, czas="08:00")
sv.dodaj(tekst="Kutangen [8]: sell hmm", nadawca=None, kolor="9f9dfd", kanal=None, bufor="0x1", ts=time.time() - 3000, czas="08:01")
sv.start()

TL = [False]    # czy „trade_logger żyje” (atrapa)
stop = threading.Event()
def spij(s):
    if stop.is_set():
        raise SystemExit
    time.sleep(s)
wynik = []
def praca():
    try:
        wynik.append(pc.petla(S, "Kutangen", spij=spij, notify=str(NOTIFY), tl_zyje=lambda: TL[0]))
    except SystemExit:
        wynik.append("stop")
th = threading.Thread(target=praca, daemon=True); th.start()

sprawdz("2a start zapisany w logu", czekaj(lambda: "start: Kutangen (tst)" in LOG()), LOG())
czekaj(lambda: sv.zapytania >= 3)
sprawdz("2b historia sprzed startu nie daje dymków", dymki() == [], dymki())

sv.dodaj(tekst="Buyer [45]: hi, i buy all your hmm, how much?", nadawca=None, kolor="5ff7f7", kanal=None, bufor="0x1", ts=time.time(), czas="09:10")
sprawdz("2c wisper (nadawca w tekście) → dymek", czekaj(lambda: len(dymki()) == 1), dymki())
d = dymki()[0] if dymki() else ""
sprawdz("2d dymek PILNY (-u critical)", "-u critical" in d, d)
sprawdz("2e w dymku nick nadawcy i początek treści", "Buyer" in d and "i buy all your hmm" in d, d)
sprawdz("2f w logu pełna treść z nickiem", "Buyer: Buyer [45]: hi, i buy all your hmm, how much?" in LOG() or "Buyer [45]: hi, i buy all your hmm, how much?" in LOG(), LOG())

sv.dodaj(tekst="Zed whispers: sell me all of them, 1k each", nadawca=None, kolor="ffff00", kanal=None, bufor="0x2", ts=time.time(), czas="09:11")
sprawdz("2g „whispers” bez koloru priv → dymek pilny WISPER", czekaj(lambda: len(dymki()) == 2) and "-u critical" in dymki()[1] and "WISPER" in dymki()[1], dymki())
sprawdz("2h wpis WISPER w logu", "WISPER Zed:" in LOG() and "sell me all of them, 1k each" in LOG(), LOG())

sv.dodaj(tekst="WTS hmm 2k", nadawca="Seller", kolor="ffff00", kanal=None, bufor="0xT", ts=time.time(), czas="09:12")
sv.dodaj(tekst="Seller: x", nadawca="Seller", kolor="5ff7f7", kanal="Server Log", bufor="0x3", ts=time.time(), czas="09:12")
sv.dodaj(tekst="Kutangen [8]: wlasna", nadawca=None, kolor="9f9dfd", kanal=None, bufor="0x1", ts=time.time(), czas="09:12")
sv.dodaj(tekst="znacznik końca serii", nadawca="Bob", kolor="ffff00", kanal="Default", bufor="0x4", ts=time.time(), czas="09:12")
sprawdz("2i po serii Trade/Server Log/własna dochodzi tylko zwykły „obok” (3 dymki łącznie)", czekaj(lambda: len(dymki()) == 3), dymki())
sprawdz("2j Trade, Server Log i własna nie dały dymka ani wpisu", "Seller" not in LOG() and "wlasna" not in LOG(), LOG())
sprawdz("2k czat obok = dymek zwykły", "-u normal" in dymki()[2], dymki())

# ---- 3. zerwanie gniazda i powrót (ta sama epoka: nic nie ginie)
sv.stop()
time.sleep(0.3)
sprawdz("3a brak gniazda → w logu „przerwa:”", czekaj(lambda: "przerwa:" in LOG()), LOG())
sv.dodaj(tekst="Late [20]: are you there?", nadawca=None, kolor="5ff7f7", kanal=None, bufor="0x1", ts=time.time(), czas="09:13")
time.sleep(0.4)
sprawdz("3b w przerwie czytnik żyje (nie wyszedł)", th.is_alive() and not wynik, wynik)
sv.start()
sprawdz("3c powrót → w logu „wznowione po”", czekaj(lambda: "wznowione po" in LOG()), LOG())
sprawdz("3d wisper z przerwy (ta sama epoka) dymek i wpis", czekaj(lambda: len(dymki()) == 4) and "Late" in dymki()[3] and "Late [20]: are you there?" in LOG(), dymki())

# ---- 4. restart klienta = nowa epoka: stara historia bez dymków, nowy wisper tak
sv.stop()
time.sleep(0.3)
sv.epoka, sv.msgs = "E2", []
sv.dodaj(tekst="Hist [20]: stare po restarcie", nadawca=None, kolor="5ff7f7", kanal=None, bufor="0x1", ts=time.time(), czas="09:14")
sv.start()
czekaj(lambda: LOG().count("wznowione po") >= 2)
time.sleep(0.4)
sprawdz("4a nowa epoka: historia bez dymka", len(dymki()) == 4, dymki())
sv.dodaj(tekst="Nowy [20]: po restarcie", nadawca=None, kolor="5ff7f7", kanal=None, bufor="0x1", ts=time.time(), czas="09:15")
sprawdz("4b nowa epoka: świeży wisper z dymkiem", czekaj(lambda: len(dymki()) == 5) and "Nowy" in dymki()[4], dymki())
sprawdz("4c dwie przerwy i dwa wznowienia w logu", LOG().count("przerwa:") == 2 and LOG().count("wznowione po") == 2, LOG())

# ---- 5. wyjątek w pętli nie zabija czytnika
oryg = pc.rodzaj
pc.rodzaj = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("test-boom"))
sv.dodaj(tekst="Boom [20]: x", nadawca=None, kolor="5ff7f7", kanal=None, bufor="0x1", ts=time.time(), czas="09:16")
sprawdz("5a wyjątek zapisany w logu (raz)", czekaj(lambda: "BŁĄD w pętli" in LOG()) and LOG().count("test-boom") == 1, LOG())
pc.rodzaj = oryg
sprawdz("5b czytnik żyje po wyjątku", th.is_alive() and not wynik, wynik)
stop.set(); th.join(3)
sprawdz("5c pętla kończy się po sygnale testu", not th.is_alive(), wynik)

# ---- 6. zaległe prywatne po starcie czytnika (czytnik padł, wisper przyszedł w przerwie)
sv.epoka = "E3"; sv.msgs = []
sv.dodaj(tekst="Stary [20]: stary wisper, już zalogowany", nadawca=None, kolor="5ff7f7", kanal=None, bufor="0x1", ts=time.time() - 60, czas="09:20")
sv.dodaj(tekst="Zaleglik [20]: kupie wszystko", nadawca=None, kolor="5ff7f7", kanal=None, bufor="0x1", ts=time.time() - 120, czas="09:19")
with open(S.logi / f"powiadom-czat-{time.strftime('%Y%m%d')}.log", "a") as f:
    f.write("09:20:01 priv Stary: Stary [20]: stary wisper, już zalogowany\n")
przed = len(dymki())
stop.clear(); wynik.clear()
th = threading.Thread(target=praca, daemon=True); th.start()
sprawdz("6a zaległy wisper (≤15 min, nie ma w logu) → jeden dymek (zaległa)", czekaj(lambda: len(dymki()) == przed + 1) and "zaległa" in dymki()[-1] and "Zaleglik" in dymki()[-1], dymki())
time.sleep(0.4)
sprawdz("6b już zalogowany nie dymi drugi raz", len(dymki()) == przed + 1, dymki())
stop.set(); th.join(3)

# ---- 7. start automatyczny: flaga, brak duplikatu
prof = KAT / "instancje" / "tst" / "profil.json"
prof.write_text(json.dumps({"postac": "Kutangen"}))
sprawdz("7a bez flagi w profilu nie startuje", "wyłączony" in pc.uruchom("tst", KAT, tmp / "rt"))
prof.write_text(json.dumps({"postac": "Kutangen", "powiadom_czat": False}))
sprawdz("7b flaga false nie startuje", "wyłączony" in pc.uruchom("tst", KAT, tmp / "rt"))
prof.write_text(json.dumps({"postac": "Kutangen", "powiadom_czat": True}))

sv.epoka, sv.msgs = "E4", []   # świeży dziennik; atrapa stoi dalej
logi_przed = LOG().count("start: Kutangen")
r1 = pc.uruchom("tst", KAT, tmp / "rt")
sprawdz("7c flaga true → wystartowany", "wystartowany" in r1, r1)
pidy = []
sprawdz("7d proces czytnika widoczny po /proc + RETRONIC_ID", czekaj(lambda: len(pc.czytniki("tst")) == 1), pc.czytniki("tst"))
pidy = pc.czytniki("tst")
r2 = pc.uruchom("tst", KAT, tmp / "rt")
r3 = pc.uruchom("tst", KAT, tmp / "rt")
sprawdz("7e drugi i trzeci start = „już działa”", "już działa" in r2 and "już działa" in r3 and str(pidy[0]) in r2, (r2, r3, pidy))
sprawdz("7f nadal dokładnie jeden czytnik tej instancji", pc.czytniki("tst") == pidy, pc.czytniki("tst"))
sprawdz("7g czytnik z --uruchom zapisał się w logu jako [auto]", czekaj(lambda: "[auto]" in LOG()), LOG())
# bezpośredni drugi czytnik (omija kontrolę po /proc) wychodzi na flock
env2 = dict(_os.environ, RETRONIC_ID="tst")
p2 = subprocess.run([sys.executable, "-I", str(pathlib.Path(pc.__file__))], env=env2, capture_output=True, text=True, timeout=10)
sprawdz("7h drugi czytnik odpalony ręcznie wychodzi na blokadzie", p2.returncode != 0 and "już działa" in (p2.stdout + p2.stderr), (p2.returncode, p2.stdout, p2.stderr))
sprawdz("7i po wszystkim nadal jeden czytnik", pc.czytniki("tst") == pidy, pc.czytniki("tst"))
# czytnik startowany z --uruchom kończy się po zdjęciu flagi (SPRAWDZ_FLAGE_S=30 s, więc sprawdzamy ścieżkę przerwy: stop atrapy)
prof.write_text(json.dumps({"postac": "Kutangen", "powiadom_czat": False}))
sv.stop()
sprawdz("7j flaga zdjęta + brak strażnika → czytnik [auto] kończy się sam", czekaj(lambda: not pc.czytniki("tst"), 6), pc.czytniki("tst"))
sprawdz("7k w logu „koniec: flaga”", "koniec: flaga powiadom_czat zdjęta" in LOG(), LOG())
for p in pc.czytniki("tst"):
    try: _os.kill(p, 15)
    except OSError: pass

# ---- 9. start usług: trade_logger razem z czytnikiem, gdy jest handel.json (atrapy Popen i /proc, nic realnego nie startuje)
class FakePopen:
    wywolania = []
    def __init__(self, cmd, **k):
        FakePopen.wywolania.append((cmd, k)); self.pid = 4242
(KAT / "instancje" / "tst").mkdir(exist_ok=True)
prof.write_text(json.dumps({"postac": "Kutangen", "powiadom_czat": True}))
if (KAT / "instancje" / "tst" / "handel.json").exists():
    (KAT / "instancje" / "tst" / "handel.json").unlink()
fproc = tmp / "proc"; (fproc / "123").mkdir(parents=True)
(fproc / "123" / "comm").write_text("python3\n")
(fproc / "123" / "cmdline").write_bytes(b"python3\0-I\0trade_logger.py\0")
(fproc / "123" / "environ").write_bytes(b"RETRONIC_ID=tst\0")
(fproc / "124").mkdir()
(fproc / "124" / "comm").write_text("python3\n")
(fproc / "124" / "cmdline").write_bytes(b"python3\0-I\0trade_logger.py\0")
(fproc / "124" / "environ").write_bytes(b"RETRONIC_ID=inny\0")
r = pc.uruchom("tst", KAT, tmp / "rt", proc=str(fproc), popen=FakePopen, skrypt_tl="/x/trade_logger.py")
sprawdz("9a bez handel.json trade_logger nie startuje", "bez handel.json" in r and not any("trade_logger" in str(c[0]) for c in FakePopen.wywolania), r)
(KAT / "instancje" / "tst" / "handel.json").write_text(json.dumps({"nick": "Kutangen", "miasto": "edron", "kupuje": {}, "sprzedaje": {}}))
FakePopen.wywolania.clear()
r = pc.uruchom("tst", KAT, tmp / "rt", proc=str(fproc), popen=FakePopen, skrypt_tl="/x/trade_logger.py")
sprawdz("9b trade_logger żywy tej instancji (pid 123) → „już działa”, bez drugiego", "trade_logger: już działa (pid 123)" in r
        and not any("trade_logger" in str(c[0]) for c in FakePopen.wywolania), (r, FakePopen.wywolania))
sprawdz("9c proces INNEJ instancji (pid 124) nie liczy się", pc.trade_loggery("tst", str(fproc)) == [123] and pc.trade_loggery("inny", str(fproc)) == [124])
(fproc / "123" / "cmdline").write_bytes(b"python3\0-I\0inne.py\0")
FakePopen.wywolania.clear()
r = pc.uruchom("tst", KAT, tmp / "rt", proc=str(fproc), popen=FakePopen, skrypt_tl="/x/trade_logger.py")
tlw = [c for c in FakePopen.wywolania if "trade_logger" in str(c[0])]
sprawdz("9d brak procesu + handel.json → trade_logger startuje odłączony z RETRONIC_ID",
        len(tlw) == 1 and tlw[0][1]["env"]["RETRONIC_ID"] == "tst" and tlw[0][1]["start_new_session"] is True and "wystartowany" in r, (r, tlw))
r = pc.uruchom("tst", KAT, tmp / "rt", proc=str(fproc), popen=FakePopen, skrypt_tl="/x/trade_logger.py")
(fproc / "123" / "cmdline").write_bytes(b"python3\0-I\0trade_logger.py\0")
sprawdz("9e drugi start po /proc z żywym trade_loggerem nie dubluje", sum("trade_logger" in str(c[0]) for c in FakePopen.wywolania) == 2 and
        "trade_logger: już działa" in pc.uruchom("tst", KAT, tmp / "rt", proc=str(fproc), popen=FakePopen, skrypt_tl="/x/trade_logger.py"))

# ---- 10. jeden alert na wiadomość: trade_logger (5ff7f7 z nadawcą) albo powiadom_czat (reszta); wisper w innym kolorze nie ginie
import trade_logger as tl
pc.SPRAWDZ_TL_S = 0
sv.epoka, sv.msgs = "E5", []
sv.start(); sv.zapytania = 0
TL[0] = True
stop.clear(); wynik.clear()
th = threading.Thread(target=praca, daemon=True); th.start()
czekaj(lambda: sv.zapytania >= 3)
przed = len(dymki())
TESTOWE = [
    dict(tekst="3 bp hmm?", nadawca="Malik", kolor="5ff7f7"),                       # tl alarmuje (5ff7f7 + nadawca)
    dict(tekst="Zed whispers: buy all", nadawca=None, kolor="ffff00"),              # wisper żółty bez nadawcy: tylko my
    dict(tekst="take it all", nadawca="Bob", kolor="abcdef"),                       # wisper dziwnego koloru: tylko my
    dict(tekst="Qq [3]: sell me all", nadawca=None, kolor="5ff7f7"),                # bez nadawcy w polu: tl nie widzi, my tak
    dict(tekst="Zoe whispers: all?", nadawca="Zoe whispers", kolor="5ff7f7"),       # tl widzi (nadawca „Zoe whispers”), my nie dublujemy
]
for i, m in enumerate(TESTOWE):
    sv.dodaj(**m, kanal=None, bufor="0x1", ts=time.time(), czas="09:30")
czekaj(lambda: len(dymki()) >= przed + 3)
time.sleep(0.5)
nowe_dymki = dymki()[przed:]
sprawdz("10a powiadom_czat dymi tylko to, czego tl nie obejmuje (3 z 5)", len(nowe_dymki) == 3 and all("Malik" not in d and "Zoe" not in d for d in nowe_dymki), nowe_dymki)
sprawdz("10b wszystkie 5 wiadomości w logu powiadom_czat (też te od tl)", all(x in LOG() for x in ("Malik: 3 bp hmm?", "Zed: Zed whispers: buy all", "Bob: take it all", "Qq: Qq [3]: sell me all", "Zoe: Zoe whispers: all?")), LOG())
sprawdz("10c wiadomości pokryte przez tl oznaczone w logu", "Malik: 3 bp hmm? [dymek: trade_logger]" in LOG() and "[dymek: trade_logger]" not in LOG().split("Zed: Zed whispers")[1].splitlines()[0])
# zgodność z prawdziwym trade_logger.rodzaj i „dokładnie jeden alert” liczony po obu stronach
okna = []
oryg_okienko = tl.okienko
tl.okienko = lambda stan, klucz, tytul, tresc, sucho, teraz, cisza, pilne=False: okna.append(klucz) or True
stan_tl = tl.Stan(plik_seed=None)
dane = {"epoka": "E5", "wiadomosci": [dict(m, nr=i + 1, ts=time.time(), czas="09:30", kanal=None, bufor="0x1") for i, m in enumerate(TESTOWE)]}
tl.cykl_handlu(stan_tl, {"nick": "Kutangen", "kupuje": {}, "sprzedaje": {}, "szablony": tl.DOMYSLNE_SZABLONY, "miasto": ""},
               {"oferty": tmp / "o.jsonl", "alerty": tmp / "a.jsonl", "priv": tmp / "p.jsonl"}, False, 0, dane=dane, teraz=1.0)
tl.okienko = oryg_okienko
tl_nicki = {k[1] for k in okna if k[0] == "priv"}
sprawdz("10d tl alarmuje dokładnie Malik i „Zoe whispers” (to, co pc uznaje za pokryte)", tl_nicki == {"Malik", "Zoe whispers"}, tl_nicki)
sprawdz("10e zgodność trade_logger_obejmuje z tl.rodzaj dla wszystkich próbek", all(
    pc.trade_logger_obejmuje(m, "Kutangen") == (tl.rodzaj(m, "Kutangen") == "priv") for m in TESTOWE))
sprawdz("10f razem: każda z 5 wiadomości ma dokładnie jeden alert (tl + pc)", len(tl_nicki) + len(nowe_dymki) == 5, (tl_nicki, nowe_dymki))
# tl padł → pc przejmuje także 5ff7f7
przed = len(dymki())
TL[0] = False
sv.dodaj(tekst="Przejecie?", nadawca="Nina", kolor="5ff7f7", kanal=None, bufor="0x1", ts=time.time(), czas="09:31")
sprawdz("10g trade_logger nie żyje → pc dymi też 5ff7f7 (przejęcie)", czekaj(lambda: len(dymki()) == przed + 1) and "Nina" in dymki()[-1], dymki()[przed:])
stop.set(); th.join(3)
sv.stop()

# ---- 11. "okienka": false w handel.json (Karol 26.10: kutangen tylko powiadamia): trade_logger bez notify-send, WSZYSTKIE alerty z powiadom_czat
import subprocess as _sp, shutil as _sh
HJ = KAT / "instancje" / "tst" / "handel.json"
HJ.write_text(json.dumps({"nick": "Kutangen", "miasto": "edron", "kupuje": {}, "sprzedaje": {}, "okienka": False}))
uruch = []
orig_run, orig_which = tl.subprocess.run, tl.shutil.which
tl.subprocess.run = lambda cmd, **k: uruch.append(cmd)
tl.shutil.which = lambda n: "/usr/bin/" + n
PLIKI = {"oferty": tmp / "o2.jsonl", "alerty": tmp / "a2.jsonl", "priv": tmp / "p2.jsonl"}
def cykl(konfig, epoka):
    d = {"epoka": epoka, "wiadomosci": [dict(m, nr=i + 1, ts=time.time(), czas="09:40", kanal=None, bufor="0x1") for i, m in enumerate(TESTOWE)]}
    tl.cykl_handlu(tl.Stan(plik_seed=None), konfig, PLIKI, False, 0, dane=d, teraz=1.0)
KONF = {"nick": "Kutangen", "kupuje": {}, "sprzedaje": {}, "szablony": tl.DOMYSLNE_SZABLONY, "miasto": ""}
cykl(dict(KONF, okienka=False), "E6")
sprawdz("11a trade_logger z okienka:false nie woła notify-send", uruch == [], uruch)
zapis = [json.loads(l) for l in PLIKI["priv"].read_text().splitlines()]
sprawdz("11b ...ale zapisuje priv (Malik i „Zoe whispers”) z pełną treścią", {z["nadawca"] for z in zapis} == {"Malik", "Zoe whispers"} and any(z["tekst"] == "3 bp hmm?" for z in zapis), zapis)
cykl(KONF, "E7")
sprawdz("11c bez klucza okienka zachowanie jak dotąd (2 okienka priv)", len(uruch) == 2 and all("critical" in c for c in uruch), uruch)
tl.subprocess.run, tl.shutil.which = orig_run, orig_which

POKRYTE_PRZED = LOG().count("[dymek: trade_logger]")
sv.epoka, sv.msgs = "E6", []
sv.start(); sv.zapytania = 0
TL[0] = True        # trade_logger „żyje”, a mimo to powiadom_czat ma dymić wszystko (okienka:false)
stop.clear(); wynik.clear()
th = threading.Thread(target=praca, daemon=True); th.start()
czekaj(lambda: sv.zapytania >= 3)
przed = len(dymki())
for m in TESTOWE + [dict(tekst="jeszcze raz", nadawca="Malik", kolor="5ff7f7")]:
    sv.dodaj(**m, kanal=None, bufor="0x1", ts=time.time(), czas="09:41")
sprawdz("11d powiadom_czat dymi KAŻDĄ z 6 wiadomości (też 5ff7f7 i drugą od Malika w 60 s)", czekaj(lambda: len(dymki()) == przed + 6), dymki()[przed:])
time.sleep(0.4)
sprawdz("11e dokładnie 6 dymków (żadnych dubli)", len(dymki()) == przed + 6, dymki()[przed:])
sprawdz("11f w logu z okienka:false żadna wiadomość nie jest „pokryta przez trade_logger”", LOG().count("[dymek: trade_logger]") == POKRYTE_PRZED and "Malik: jeszcze raz" in LOG(), LOG().count("[dymek: trade_logger]"))
sprawdz("11g dymki pilne dla priv i wisperów (kolory 5ff7f7, abcdef, żółty+whispers)", sum("-u critical" in d for d in dymki()[przed:]) == 6, dymki()[przed:])
sprawdz("11h każdy dymek ma nick i treść", all(n in " ".join(dymki()[przed:]) for n in ("Malik", "Zed", "Bob", "Qq", "Zoe", "buy all", "take it all")), dymki()[przed:])
stop.set(); th.join(3); sv.stop()

# ---- 8. skrypt powłoki
sprawdz("8a sesja.sh: składnia", subprocess.run(["bash", "-n", str(pathlib.Path(pc.__file__).with_name("sesja.sh"))]).returncode == 0)
sprawdz("8b sesja.sh woła powiadom_czat.py --uruchom", "powiadom_czat.py\" --uruchom" in pathlib.Path(pc.__file__).with_name("sesja.sh").read_text())

print("\nWYNIK:", sum(ok), "/", len(ok))
sys.exit(0 if all(ok) else 1)
