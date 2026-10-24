#!/usr/bin/env python3
"""Monitor wykryć (23.10): rozmowy z NPC nie są „czatem od obcych”, a „duch w kliencie” ma własny sygnał.
Offline: katalog tymczasowy, atrapa strażnika (gniazdo unixowe z komendą „wiadomosci”), atrapa powiadomień. Nic nie startuje,
nie dotyka gry, instancji ani procesów.
Dowodzi:
  NPC:  linie z logu 22.10 (Alexander „Do you want to buy 20 blank runes”, Ebenizer, Mirabell, Beatrice, Suzy, Xodet, Gorn, „Hello,
        hiho”) i rozmowa Dawajkesha z dumpu strażnika 23.10 nie dają ani RYZYKA, ani UWAGI; prawdziwy gracz („hi”, „bot?”) nadal
        daje RYZYKO; gracz widziany w telemetrii nie jest NPC nawet pod imieniem z bazy; NPC spoza bazy uczy się ze struktury
        rozmowy (odpowiada na >= 2 własne wypowiedzi), także pierwsza jego wypowiedź odpada; gracz bez rozmowy z postacią nie;
        własny nick z profil.json („Geblish”) nie jest obcym.
  Duch: >= 3 „klików bez efektu” w ten sam cel w 5 min = jeden dymek critical z nickiem (raz na 15 min na postać); 2 kliki, różne
        cele, stare linie (> 5 min) = nic.
Stary kod (kopia monitor_wykrycia.py.bak-20261023-monitor-npc) nie przechodzi: NPC daje RYZYKO, brak sygnału ducha, „Geblish” obcy.
Uruchomienie: python3 -I testy/test_monitor_npc.py   (MONITOR_MODUL=<plik.py> sprawdza inną wersję modułu, np. kopię .bak)"""
import importlib.machinery
import importlib.util
import json
import os
import socketserver
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.dont_write_bytecode = True
KORZEN = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(KORZEN))


def _wczytaj():
    sciezka = os.environ.get("MONITOR_MODUL")
    if not sciezka:
        import monitor_wykrycia
        return monitor_wykrycia
    loader = importlib.machinery.SourceFileLoader("monitor_wykrycia_testowany", os.path.abspath(sciezka))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    m = importlib.util.module_from_spec(spec)
    loader.exec_module(m)
    return m


M = _wczytaj()


# ---------------------------------------------------------------- atrapy
class Strazniki:
    """Gniazdo unixowe jak strażnik: komenda „wiadomosci” -> kolejne zakolejkowane odpowiedzi (pierwsza to sam znacznik)."""

    def __init__(self, sciezka):
        self.kolejka = []
        outer = self

        class H(socketserver.StreamRequestHandler):
            def handle(self):
                self.rfile.readline()
                odp = outer.kolejka.pop(0) if outer.kolejka else {"wiadomosci": []}
                nr = outer.nr = getattr(outer, "nr", 0) + len(odp["wiadomosci"])
                self.wfile.write((json.dumps({"ok": True, "znacznik": nr, "epoka": "e1", **odp}) + "\n").encode())

        self.srv = socketserver.ThreadingUnixStreamServer(str(sciezka), H)
        self.watek = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.watek.start()

    def zamknij(self):
        self.srv.shutdown()
        self.srv.server_close()


class Swiat:
    def __init__(self, nick="Dawajkesh", id_="dawajkesh", z_baza_npc=True):
        self.tmp = tempfile.TemporaryDirectory()
        self.k = Path(self.tmp.name)
        self.id = id_
        (self.k / "instancje" / id_ / "logi").mkdir(parents=True)
        (self.k / "instancje" / id_ / "profil.json").write_text(json.dumps({"postac": nick}))
        if z_baza_npc:
            baza = self.k / "dane_tibia" / "serwer74"
            baza.mkdir(parents=True)
            (baza / "npc_pelne.json").write_text(json.dumps(
                {"npc": [{"nazwa": n} for n in ("Alexander", "Ebenizer", "Mirabell", "Beatrice", "Suzy", "Xodet", "Gorn",
                                                "Marvik", "Captain Seahorse", "Hanna")]}))
        if hasattr(M, "NICKI_WLASNE"):
            M.NICKI_WLASNE.clear()
        self.p = M.Postac(id_, self.k)
        self.sock = Path(self.tmp.name) / "s.sock"
        self.straznik = Strazniki(self.sock)
        self.p.s.gniazdo = self.sock
        self.p.czytaj_czat()                                   # pierwszy odczyt: tylko znacznik, bez historii

    def czat(self, wiadomosci):
        """Podaje porcję wiadomości przez gniazdo i czyta ją jak monitor."""
        self.straznik.kolejka.append({"wiadomosci": wiadomosci})
        self.p.czytaj_czat()

    def log(self, linie):
        """linie: [(sekund_temu, tekst)] -> mozg-stdout-*.log tej instancji i odczyt."""
        t0 = time.time()
        plik = self.k / "instancje" / self.id / "logi" / "mozg-stdout-1023-0750.log"
        with open(plik, "a", encoding="utf-8") as f:
            for temu, tekst in linie:
                f.write(f"{time.strftime('%H:%M:%S', time.localtime(t0 - temu))} {tekst}\n")
        self.p.czytaj_log()

    def zamknij(self):
        self.straznik.zamknij()
        self.tmp.cleanup()


def w(nadawca, tekst, kanal="Default", czas="07:40", kolor="ffff00"):
    return {"nadawca": nadawca, "tekst": tekst, "kanal": kanal, "czas": czas, "kolor": kolor}


def ocena(p):
    # `getattr`: kopia sprzed zmiany nie ma jeszcze duch(), ocena ma tam po prostu inny wynik
    return p.ocena()


def duch(p):
    return getattr(p, "duch", lambda: None)()


class Dymki:
    """Podmienia powiadomienia modułu i zbiera, co poszło."""

    def __enter__(self):
        self.wyslane = []
        self.stare = getattr(M, "_notify", None)
        M._notify = lambda tytul, tresc: self.wyslane.append((tytul, tresc))
        return self

    def __exit__(self, *a):
        if self.stare is None:
            del M._notify
        else:
            M._notify = self.stare


def dymek_duch(p):
    return getattr(M, "dymek_duch", lambda p: None)(p)


# ---------------------------------------------------------------- NPC
LINIE_22_10 = [  # z monitor-wykrycia-20261022.log
    w("Alexander", "Do you want to buy 20 blank runes for 200 gold?"),
    w("Ebenizer", "So I should change 900 of your gold coin"),
    w("Ebenizer", "Have a nice day."),
    w("Mirabell", "Do you want to buy 4 ham for 32 gold?"),
    w("Beatrice", "Hello, hiho, and ashari Invincible."),
    w("Beatrice", "Do you want to buy a blue backpack for 20 gold coins?"),
    w("Suzy", "Welcome, hello and please come in."),
    w("Xodet", "I sell blank runes."),
    w("Xodet", "Do you want to buy 20 blank runes for 200 gold?"),
    w("Gorn", "Oh, please come in, Wydra. What do you need?"),
]


def test_npc_z_logu_22_10_nie_daja_ryzyka():
    s = Swiat("Invincible", "invincible")
    try:
        s.czat(LINIE_22_10)
        poziom, powody = ocena(s.p)
        assert poziom == 0 and not powody and not s.p.czat, (poziom, powody, list(s.p.czat))
    finally:
        s.zamknij()


def test_rozmowa_dawajkesha_z_dumpu_strazy():
    s = Swiat("Dawajkesh", "dawajkesh")
    try:
        s.czat([w("Dawajkesh", "hi"), w("Captain Seahorse", "Welcome on board, Sir Dawajkesh."), w("Dawajkesh", "thais"),
                w("Dawajkesh", "yes"), w("Dawajkesh", "hi"), w("Marvik", "Nice to see you again, Dawajkesh."),
                w("Dawajkesh", "ultimate healing rune"), w("Marvik", "Here you are. Look in your spellbook."),
                w("Alexander", "Do you want to buy 20 blank runes for 200 gold?", kanal="Alexander", kolor="5ff7f7")])
        assert ocena(s.p)[0] == 0 and not s.p.czat, (ocena(s.p), list(s.p.czat))
    finally:
        s.zamknij()


def test_prawdziwy_gracz_nadal_daje_ryzyko():
    s = Swiat()
    try:
        s.czat([w("Elmenteloca", "hi")])
        poziom, powody = ocena(s.p)
        assert poziom == 2 and "Elmenteloca" in powody[0], (poziom, powody)
        s2 = Swiat("Invincible", "invincible")
        try:
            s2.czat([w("Czubajka Kania", "witaj :D"), w("Uszkibuszki", "u bot?")])
            assert ocena(s2.p)[0] == 2 and len(s2.p.czat) == 2, (ocena(s2.p), list(s2.p.czat))
        finally:
            s2.zamknij()
    finally:
        s.zamknij()


def test_gracz_widziany_w_telemetrii_nie_jest_npc_nawet_pod_imieniem_z_bazy():
    s = Swiat()
    try:
        t = time.time()
        s.p.obcy["Hanna"] = [t - 30, t, 2]                    # w widoku jako GRACZ (telemetria: gracz: true)
        s.czat([w("Hanna", "hi")])
        assert ocena(s.p)[0] == 2 and "Hanna" in ocena(s.p)[1][0], ocena(s.p)
    finally:
        s.zamknij()


def test_npc_spoza_bazy_uczy_sie_ze_struktury_rozmowy():
    s = Swiat("Wydra", "wydra")
    try:
        s.czat([w("Wydra", "hi"), w("Zorbax", "Hello, hiho, welcome Wydra."), w("Wydra", "blank rune"),
                w("Zorbax", "Do you want to buy a blank rune?", kanal="Zorbax", kolor="5ff7f7"), w("Wydra", "yes"),
                w("Zorbax", "Here you are.")])
        assert not s.p.czat and ocena(s.p)[0] == 0, (list(s.p.czat), ocena(s.p))
        assert "zorbax" in s.p.npc_nauczone
        s.czat([w("Zorbax", "hi")])                           # kolejna jego wypowiedź już jako znany NPC
        assert not s.p.czat
    finally:
        s.zamknij()


def test_obcy_bez_rozmowy_z_postacia_nie_uczy_sie_na_npc():
    s = Swiat("Wydra", "wydra")
    try:
        s.czat([w("Zorbax", "hi"), w("Zorbax", "bot?"), w("Zorbax", "hello")])
        assert ocena(s.p)[0] == 2 and "zorbax" not in getattr(s.p, "npc_nauczone", {}), ocena(s.p)
    finally:
        s.zamknij()


def test_gracz_w_telemetrii_odpowiadajacy_na_wlasne_wypowiedzi_nie_jest_npc():
    s = Swiat("Wydra", "wydra")
    try:
        t = time.time()
        s.p.obcy["Rozmowny"] = [t - 30, t, 3]
        s.czat([w("Wydra", "utevo lux"), w("Rozmowny", "hi"), w("Wydra", "exura"), w("Rozmowny", "u botting?")])
        assert ocena(s.p)[0] == 2 and len(s.p.czat) == 2, (ocena(s.p), list(s.p.czat))
    finally:
        s.zamknij()


def test_wlasny_nick_z_profilu_nie_jest_obcym():
    s = Swiat("Geblish", "gebelish")                          # WLASNE nie zna „Geblish” (literówka w nicku z gry)
    try:
        s.czat([w("Geblish", "hi"), w("Geblish", "yes")])
        assert ocena(s.p)[0] == 0 and not s.p.czat, (ocena(s.p), list(s.p.czat))
    finally:
        s.zamknij()


def test_brak_pliku_bazy_npc_zostaja_imiona_dodatkowe():
    s = Swiat("Invincible", "invincible", z_baza_npc=False)
    try:
        s.czat([w("Ebenizer", "So I should change 900 of your gold coin"), w("Xodet", "I sell blank runes.")])
        assert ocena(s.p)[0] == 0, ocena(s.p)
    finally:
        s.zamknij()


def test_baza_npc_serwera_zawiera_imiona_z_alarmow_22_10():
    imiona = M.imiona_npc(KORZEN)
    brak = {"alexander", "ebenizer", "mirabell", "beatrice", "suzy", "xodet", "gorn"} - imiona
    assert not brak, brak


# ---------------------------------------------------------------- duch w kliencie
def kliki(id_, temu, nazwa="Troll"):
    return (temu, f"[ATAK] 5 klików bez efektu w {nazwa} id{id_}, Escape i ignoruję cel na 30 s.")


def test_duch_trzy_razy_w_5_min_to_jeden_dymek_z_nickiem():
    s = Swiat("Wydra", "wydra")
    try:
        s.log([kliki("..1363", 200), kliki("..1363", 150), kliki("..1363", 20)])
        assert duch(s.p) == ("Troll", "..1363", 3), duch(s.p)
        with Dymki() as d:
            tresc = dymek_duch(s.p)
            assert tresc and len(d.wyslane) == 1, d.wyslane
            tytul, cialo = d.wyslane[0]
            assert "Wydra" in tytul and cialo.startswith("Wydra: klient widzi potwora, którego nie da się bić (duch)"), d.wyslane
            assert "restart klienta: zatrzymaj bota, sesja_gry zamknij/start, zaloguj" in cialo
            assert len(tytul.splitlines()) + len(cialo.splitlines()) <= 3, d.wyslane
            assert dymek_duch(s.p) is None and len(d.wyslane) == 1       # raz na 15 min na postać
            s.p.duch_dymek -= M.DUCH_DYMEK_CO_S + 1
            s.log([kliki("..1363", 5)])
            dymek_duch(s.p)
            assert len(d.wyslane) == 2                                   # po 15 min znowu
        poziom, powody = ocena(s.p)
        assert any("duch w kliencie" in x for x in powody), powody
    finally:
        s.zamknij()


def test_duch_dwa_razy_rozne_cele_i_stare_linie_to_cisza():
    s = Swiat("Wydra", "wydra")
    try:
        s.log([kliki("..1363", 100), kliki("..1363", 50)])                              # tylko 2
        s.log([kliki("..2043", 30), kliki("..9999", 20, "Troll Champion")])              # inne cele
        s.log([kliki("..7777", 400), kliki("..7777", 380), kliki("..7777", 360)])        # > 5 min temu
        s.log([kliki("?", 10), kliki("?", 9), kliki("?", 8)])                            # cel bez id: nie wiadomo, czy ten sam
        with Dymki() as d:
            assert duch(s.p) is None and dymek_duch(s.p) is None and not d.wyslane, (duch(s.p), d.wyslane)
    finally:
        s.zamknij()


def test_duch_osobno_na_postac():
    a, b = Swiat("Wydra", "wydra"), Swiat("Invincible", "invincible")
    try:
        a.log([kliki("..1363", 90), kliki("..1363", 60), kliki("..1363", 30)])
        b.log([kliki("..1363", 90), kliki("..1363", 60), kliki("..1363", 30)])
        with Dymki() as d:
            dymek_duch(a.p)
            dymek_duch(b.p)
            assert len(d.wyslane) == 2 and {x[0] for x in d.wyslane} == {"Duch w kliencie: Wydra", "Duch w kliencie: Invincible"}
    finally:
        a.zamknij()
        b.zamknij()


def test_duch_nie_psuje_istniejacych_sygnalow_logu():
    s = Swiat("Wydra", "wydra")
    try:
        s.log([(30, "D3 zawieszka 45 s"), kliki("..1363", 20)])
        assert [z[1] for z in s.p.zdarz] == ["zawieszka"], [z[1] for z in s.p.zdarz]
    finally:
        s.zamknij()


if __name__ == "__main__":
    ok = zle = 0
    for nazwa, f in list(globals().items()):
        if nazwa.startswith("test_") and callable(f):
            try:
                f()
                ok += 1
                print("ok  ", nazwa)
            except Exception as e:      # noqa: BLE001
                import traceback
                zle += 1
                print("BŁĄD", nazwa, repr(e)[:400])
                traceback.print_exc()
    print(f"{ok}/{ok + zle} testów zielonych")
    sys.exit(1 if zle else 0)
