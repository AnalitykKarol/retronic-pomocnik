#!/usr/bin/env python3
"""Strategia 23.10 (Karol) w nadzorcy: wykrycie „czar bez efektu 3×” (powiadomienie, bez zmiany pokręteł), restart po zmianie kodu
(pokrętło NADZOR_RESTART_PO_KODZIE, domyślnie wyłączone) i zamknięcie sesji wylogowanej postaci (pokrętło NADZOR_ZAMYKAJ_SESJE,
domyślnie wyłączone). Offline, na atrapach z testy/test_nadzor.py. Uruchomienie: python3 -I testy/test_nadzor_strategia.py"""
import os
import sys
from datetime import timedelta
from pathlib import Path

sys.dont_write_bytecode = True
KORZEN = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(KORZEN))
sys.path.insert(0, str(KORZEN / "testy"))
import test_nadzor as T  # noqa: E402
import nadzor as N  # noqa: E402

CZAR = [("[ZDROWIE] czar exura [F2] (hp 77%, mana 35)", 0), ("[ZDROWIE] exura [F2] (hp 77%, mana 35)", 0)]


def pokretlo(s, nazwa):
    (s.k / "instancje" / "_wspolne" / nazwa).touch()


def swiat_eksp(ids=("a",)):
    s = T.Swiat(ids)
    s.grafik([T.zmiana(i, od="2026-10-21 09:00", koniec="2026-10-21 16:00", wylog="2026-10-21 16:15") for i in ids])
    for i in ids:
        s.online(i, bot=True)
        s.tryb_log(i, "raty", "ostrozny", s.zegar.t - timedelta(hours=3))
    return s


def czar_bez_efektu(s, id_="a", porazka=3, czar="exura"):
    t = s.zegar.t - timedelta(seconds=40)
    s.log(id_, [(t, f"[ZDROWIE] czar {czar} [F2] (hp 77%, mana 35)"),
                (t + timedelta(seconds=1), f"ZDROWIE: po rzucie ani HP, ani mana się nie zmieniły (35 -> 35), porażka {porazka}/3.")])


# ---------------------------------------------------------------- (a) czar bez efektu
def test_czar_analiza_logu():
    t = T.T0
    ep = lambda sec: (t - timedelta(seconds=sec)).timestamp()      # noqa: E731
    a = N.analizuj_log([(ep(30), "[ZDROWIE] czar exura [F2] (hp 77%, mana 35)"),
                        (ep(29), "ZDROWIE: po rzucie ani HP, ani mana się nie zmieniły (35 -> 35), porażka 3/3.")], t.timestamp())
    assert a["czar_bez_efektu"] and a["czar_bez_efektu"]["czar"] == "exura" and a["czar_bez_efektu"]["porazka"] == 3, a
    a = N.analizuj_log([(ep(29), "ZDROWIE: po rzucie ani HP, ani mana się nie zmieniły (35 -> 35), porażka 2/3.")], t.timestamp())
    assert a["czar_bez_efektu"] is None, a              # dopiero ostatnia porażka serii to sygnał


def test_czar_bez_efektu_powiadamia_raz_na_karencje_i_nie_ruszy_pokretel():
    s = swiat_eksp()
    czar_bez_efektu(s)
    na_zywo = s.plik("a", "na_zywo.json")
    na_zywo.write_text('{"ZDROWIE_CZAR_AKTYWNY": 1}')
    n, at = T.nz(s)
    T._eksp(n, s)
    n.tick()
    pi = [w for w in at.wywolania if w[0] == "powiadom_info"]
    assert len(pi) == 1 and "exura" in pi[0][2] + pi[0][3] and "ML" in pi[0][3], at.wywolania
    assert na_zywo.read_text() == '{"ZDROWIE_CZAR_AKTYWNY": 1}', "nadzorca nie zmienia pokręteł bota"
    s.zegar.dalej(minutes=5)
    czar_bez_efektu(s)
    n.tick()
    assert len([w for w in at.wywolania if w[0] == "powiadom_info"]) == 1, "karencja: bez drugiego powiadomienia"
    assert not [w for w in at.wywolania if w[0] in ("zatrzymaj_bota", "start_bota")], "to powiadomienie, nie naprawa"


def test_czar_porazka_1_z_3_nie_powiadamia():
    s = swiat_eksp()
    czar_bez_efektu(s, porazka=1)
    n, at = T.nz(s)
    T._eksp(n, s)
    n.tick()
    assert at.wywolania == [], at.wywolania


def test_czar_w_cieniu_tylko_wpis():
    s = swiat_eksp()
    czar_bez_efektu(s)
    n, at = T.nz(s, zywo=False)
    T._eksp(n, s)
    r = n.tick()
    assert at.wywolania == [] and any("czar" in str(x.get("powod", "")) for x in r), r


# ---------------------------------------------------------------- (b) restart po zmianie kodu
def kod_swiata(s, mozg_nowszy=True):
    """mozg.py importuje pomoc.py; luzak.py nie jest importowany przez bota."""
    (s.k / "mozg.py").write_text("import pomoc\n")
    (s.k / "cavebot.py").write_text("import json\n")
    (s.k / "pomoc.py").write_text("x = 1\n")
    (s.k / "luzak.py").write_text("y = 1\n")
    stary = (s.zegar.t - timedelta(hours=2)).timestamp()
    nowy = (s.zegar.t - timedelta(minutes=20)).timestamp()
    for p in ("mozg.py", "cavebot.py", "luzak.py"):
        os.utime(s.k / p, (stary, stary))
    os.utime(s.k / "pomoc.py", (nowy if mozg_nowszy else stary,) * 2)
    os.utime(s.k / "luzak.py", (nowy,) * 2)


def bot_od(s, minut_temu=60):
    s.bot_start_ts = lambda id_: (s.zegar.t - timedelta(minutes=minut_temu)).timestamp()


def test_restart_po_kodzie_domyslnie_wylaczony():
    s = swiat_eksp()
    kod_swiata(s)
    bot_od(s)
    n, at = T.nz(s)
    T._eksp(n, s)
    n.tick()
    assert at.wywolania == [], at.wywolania


def test_restart_po_kodzie_importowany_modul_nowszy_niz_start_bota():
    s = swiat_eksp()
    kod_swiata(s)
    bot_od(s)
    pokretlo(s, "NADZOR_RESTART_PO_KODZIE")
    n, at = T.nz(s)
    T._eksp(n, s)
    n.tick()
    assert at.nazwy() == ["zatrzymaj_bota", "start_bota"], at.wywolania
    assert not n.post("a").get("naprawy"), "restart po kodzie nie zużywa drabiny napraw (3 restarty = eskalacja)"
    assert n.post("a").get("restart_kod_ts"), n.post("a")


def test_restart_po_kodzie_plik_spoza_importow_bota_nie_liczy_sie():
    s = swiat_eksp()
    kod_swiata(s, mozg_nowszy=False)         # nowszy tylko luzak.py
    bot_od(s)
    pokretlo(s, "NADZOR_RESTART_PO_KODZIE")
    n, at = T.nz(s)
    T._eksp(n, s)
    n.tick()
    assert at.wywolania == [], at.wywolania


def test_kod_bota_leniwy_import_w_korzeniu_tak_w_module_pomocniczym_nie():
    """Prawdziwy defekt z `cien --raz` (23.10): ast.walk po całym domknięciu dociągał nadzor.py/grafik.py i każda edycja nadzorcy restartowałaby boty."""
    s = swiat_eksp()
    (s.k / "mozg.py").write_text("import pomoc\ndef f():\n    import leniwy_bota\n")
    (s.k / "cavebot.py").write_text("")
    (s.k / "pomoc.py").write_text("import twardy\ndef g():\n    import narzedzie\n")
    for n_ in ("leniwy_bota", "twardy", "narzedzie"):
        (s.k / f"{n_}.py").write_text("")
    n, _at = T.nz(s)
    assert sorted(p.name for p in n.kod_bota()) == ["cavebot.py", "leniwy_bota.py", "mozg.py", "pomoc.py", "twardy.py"], n.kod_bota()


def test_restart_po_kodzie_bot_wystartowal_po_zmianie_kodu():
    s = swiat_eksp()
    kod_swiata(s)
    bot_od(s, minut_temu=5)                   # bot nowszy niż kod (zmiana sprzed 20 min)
    pokretlo(s, "NADZOR_RESTART_PO_KODZIE")
    n, at = T.nz(s)
    T._eksp(n, s)
    n.tick()
    assert at.wywolania == [], at.wywolania


def test_restart_po_kodzie_nie_w_walce_i_ponawia_w_nastepnym_przebiegu():
    s = swiat_eksp()
    kod_swiata(s)
    bot_od(s)
    pokretlo(s, "NADZOR_RESTART_PO_KODZIE")
    s.log("a", [(s.zegar.t - timedelta(seconds=3), "[WALKA] Troll odl 1 HP 70%")])
    n, at = T.nz(s)
    T._eksp(n, s)
    n.tick()
    assert at.wywolania == [], at.wywolania
    s.zegar.dalej(minutes=5)
    n.tick()
    assert at.nazwy() == ["zatrzymaj_bota", "start_bota"], at.wywolania


def test_restart_po_kodzie_stop_reczny_i_nadzor_false_pomijane():
    s = swiat_eksp(("a", "b"))
    kod_swiata(s)
    bot_od(s)
    pokretlo(s, "NADZOR_RESTART_PO_KODZIE")
    s.plik("a", "STOP_RECZNY").touch()
    (s.plik("b", "profil.json")).write_text('{"postac": "B", "nadzor": false}')
    n, at = T.nz(s)
    for i in ("a", "b"):
        T._eksp(n, s, i)
    n.tick()
    assert at.wywolania == [], at.wywolania


def test_restart_po_kodzie_jedna_postac_na_przebieg():
    s = swiat_eksp(("a", "b", "c"))
    kod_swiata(s)
    bot_od(s)
    pokretlo(s, "NADZOR_RESTART_PO_KODZIE")
    n, at = T.nz(s)
    for i in ("a", "b", "c"):
        T._eksp(n, s, i)
    n.tick()
    assert at.nazwy() == ["zatrzymaj_bota", "start_bota"], at.wywolania            # tylko jedna
    s.inst["a"]["bot"] = True
    bot_od(s, minut_temu=60)
    s.bot_start_ts = lambda id_: (s.zegar.t - timedelta(minutes=1 if id_ == "a" else 60)).timestamp()
    s.zegar.dalej(minutes=5)
    n.tick()
    assert at.nazwy().count("start_bota") == 2, at.wywolania                      # następna w kolejnym przebiegu


def test_restart_po_kodzie_naprawy_poziom_wykonuje_na_zywo_tylko_z_pokretlem():
    s = swiat_eksp()
    kod_swiata(s)
    bot_od(s)
    at = T.Atrapa(s)
    n = N.Nadzorca(s.k, s.zegar, s, T.N.WykonawcaCien(), False, True, naprawy_poziom=True, wykonawca_poziom=at)
    T._eksp(n, s)
    n.tick()
    assert at.wywolania == [], "bez pokrętła nic"
    pokretlo(s, "NADZOR_RESTART_PO_KODZIE")
    n = N.Nadzorca(s.k, s.zegar, s, T.N.WykonawcaCien(), False, True, naprawy_poziom=True, wykonawca_poziom=at)
    T._eksp(n, s)
    n.tick()
    assert at.nazwy() == ["zatrzymaj_bota", "start_bota"], at.wywolania


# ---------------------------------------------------------------- (c) zamknięcie sesji wylogowanej postaci
class AtrapaSesji(T.Atrapa):
    def zamknij_sesje(self, id_):
        r = self._pre("zamknij_sesje", id_)
        if r is not None:
            return r
        self.s.offline(id_)
        return self._w("zamknij_sesje", id_)


def swiat_wylogowany(ids=("a",), ekran="lista"):
    s = T.Swiat(ids)
    s.grafik([T.zmiana(i, od="2026-10-21 18:00", koniec="2026-10-21 20:00", wylog="2026-10-21 20:15") for i in ids])     # zmiana dopiero wieczorem
    for i in ids:
        s.online(i, bot=False, w_grze=False)
        s.ekran_map[i] = ekran
    return s


def nz_sesji(s, zywo=True):
    at = AtrapaSesji(s)
    return N.Nadzorca(s.k, s.zegar, s, at if zywo else N.WykonawcaCien(), zywo, True), at


def test_zamykanie_sesji_domyslnie_wylaczone():
    s = swiat_wylogowany()
    n, at = nz_sesji(s)
    n.tick()
    assert "zamknij_sesje" not in at.nazwy(), at.wywolania


def test_zamykanie_sesji_lista_postaci_bez_bota_poza_zmiana():
    s = swiat_wylogowany(ekran="lista")
    pokretlo(s, "NADZOR_ZAMYKAJ_SESJE")
    n, at = nz_sesji(s)
    n.tick()
    assert at.nazwy() == ["zamknij_sesje"], at.wywolania
    assert not s.inst["a"]["sesja"], "sesja zamknięta"


def test_zamykanie_sesji_pojedynczo_z_odstepem():
    s = swiat_wylogowany(("a", "b"), ekran="logowanie")
    pokretlo(s, "NADZOR_ZAMYKAJ_SESJE")
    n, at = nz_sesji(s)
    n.tick()
    assert at.nazwy() == ["zamknij_sesje"], at.wywolania
    s.zegar.dalej(minutes=2)
    n.tick()
    assert at.nazwy() == ["zamknij_sesje"], "odstęp między zdarzeniami logowania: druga postać jeszcze nie"
    s.zegar.dalej(minutes=10)
    n.tick()
    assert at.nazwy() == ["zamknij_sesje", "zamknij_sesje"], at.wywolania


def test_zamykanie_sesji_wyjatki():
    for przygotuj, opis in (
        (lambda s: s.plik("a", "STOP_RECZNY").touch(), "STOP_RECZNY"),
        (lambda s: s.inst["a"].update(bot=True), "bot działa"),
        (lambda s: s.ekran_map.update(a="smierc"), "ekran śmierci (eskalacja, nie zamykanie)"),
        (lambda s: s.ekran_map.update(a=None), "ekran nierozpoznany"),
        (lambda s: s.ekran_map.update(a="gra"), "klient w grze"),
        (lambda s: s.plik("a", "profil.json").write_text('{"postac": "A", "nadzor": false}'), "nadzor:false"),
    ):
        s = swiat_wylogowany()
        pokretlo(s, "NADZOR_ZAMYKAJ_SESJE")
        przygotuj(s)
        n, at = nz_sesji(s)
        n.tick()
        assert "zamknij_sesje" not in at.nazwy(), (opis, at.wywolania)


def test_zamykanie_sesji_w_trakcie_zmiany_nadal_relog_nie_zamykanie():
    s = swiat_wylogowany(ekran="logowanie")
    s.grafik([T.zmiana("a", od="2026-10-21 09:00", koniec="2026-10-21 16:00", wylog="2026-10-21 16:15")])
    pokretlo(s, "NADZOR_ZAMYKAJ_SESJE")
    n, at = nz_sesji(s)
    n.stan["postacie"]["a"] = {"faza": "EXP", "login_ts": s.zegar.t.timestamp() - 3600, "zmiana_od": "2026-10-21 09:00"}
    n.tick()
    assert "zamknij_sesje" not in at.nazwy(), at.wywolania


def test_zamykanie_sesji_cien_tylko_wpis():
    s = swiat_wylogowany()
    pokretlo(s, "NADZOR_ZAMYKAJ_SESJE")
    n, at = nz_sesji(s, zywo=False)
    r = n.tick()
    assert any(x.get("akcja") == "zamknij_sesje" for x in r) and s.inst["a"]["sesja"], r


def test_zamykanie_sesji_napraw_cli():
    assert "zamknij_sesje" in N.BIALA_LISTA and "zamknij_sesje" in N.NAPRAWY_BEZ_ZYWO
    s = swiat_wylogowany()
    n, at = nz_sesji(s)
    kod, txt = n.napraw("a", "zamknij_sesje")
    assert kod == 0 and at.nazwy() == ["zamknij_sesje"], (kod, txt, at.wywolania)
    s = swiat_wylogowany(ekran="gra")
    n, at = nz_sesji(s)
    kod, txt = n.napraw("a", "zamknij_sesje")
    assert kod == 3 and at.wywolania == [], (kod, txt)
    s = swiat_wylogowany()
    s.inst["a"]["bot"] = True
    n, at = nz_sesji(s)
    kod, txt = n.napraw("a", "zamknij_sesje")
    assert kod == 3 and at.wywolania == [], (kod, txt)


def test_zamykanie_sesji_wykonawca_zywy_wola_sesja_gry_zamknij():
    w = N.WykonawcaZywy(KORZEN)
    wywolane = []
    w._uruchom = lambda argv, id_, limit, odlacz=False: (wywolane.append((list(map(str, argv)), id_)) or (True, "kod 0"))
    assert w.zamknij_sesje("a") == (True, "kod 0")
    assert wywolane[0][0][-2:] == [str(KORZEN / "sesja_gry.py"), "zamknij"][-2:] or wywolane[0][0][-1] == "zamknij", wywolane
    assert wywolane[0][1] == "a"


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
                print("BŁĄD", nazwa, repr(e)[:500])
                traceback.print_exc()
    print(f"{ok}/{ok + zle} testów zielonych")
    sys.exit(1 if zle else 0)
