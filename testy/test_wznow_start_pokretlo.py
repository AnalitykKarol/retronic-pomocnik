#!/usr/bin/env python3
"""26.10 (Karol, test na Odchydzie): pokrętło WZNOW_START (0/1, domyślnie 1) w na_zywo.json instancji. 1 = restart bota wznawia
przerwaną wyprawę (wznow_start.sprobuj -> Wyprawa._wznow) jak dotąd; 0 = NIE wznawia, zapis przerwanej wyprawy jest zamykany
(aktywna=False, przerwana=False, wynik anulowana_pokretlo), bot idzie zwykłą logiką startu. Env RETRONIC_WZNOW_START=0
(wznow_start.WLACZONE=False) nadal wystarcza. Brak klucza / brak pliku / zła wartość = 1.
Atrapy świata jak w testy/test_wznow_start.py (wycięte z testy/test_wyprawa.py).
Uruchomienie: RETRONIC_TESTY=1 python3 -I testy/test_wznow_start_pokretlo.py"""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import json
import sys
import types
from pathlib import Path

sys.dont_write_bytecode = True
_R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _R)

_zr = (Path(_R) / "testy" / "test_wyprawa.py").read_text()
_a = _zr.index("# --- 0. dane i pokrętła")
_b0 = _zr.index("DEPO = (32348, 32225, 7)")
_b1 = _zr.index("powiad12 = []")
_ns = {"__name__": "atrapy_wyprawa", "__file__": str(Path(_R) / "testy" / "test_wyprawa.py")}
exec(compile(_zr[:_a] + "\n" + _zr[_b0:_b1], "test_wyprawa(atrapy)", "exec"), _ns)   # noqa: S102
if "MAPA" not in _ns:
    print("brak atrap")
    sys.exit(0)
nowy, pre, bieg, ev, konf_depo, sp_bez, krok_dokladny = (_ns[n] for n in ("nowy", "pre", "bieg", "ev", "konf_depo", "sp_bez", "krok_dokladny"))
TMP, Konf, W, DEPO = _ns["TMP"], _ns["Konf"], _ns["W"], _ns["DEPO"]

import powiadom as _pw
_pw.powiadom = lambda *a, **kw: None
import mozg
import wznow_start

ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


def start_depo(**kw):
    s, cb, w, k = nowy(jedzenie=0, konf=konf_depo(), sklepy=sp_bez, **kw)
    krok_dokladny(cb)
    cb.jedzenie_nie_do = s.t + 100000
    assert pre(s, cb, w), "wyprawa do depo nie wystartowała"
    return s, cb, w, k


def idz_ticki(s, cb, w, n):
    for _ in range(n):
        s.t += 0.3
        s.wall += 0.3
        cb.ruch_poz = tuple(s.poz)
        cb.ostatnie_stwory = list(s.stwory)
        cb.cel = s.cel
        w.tick()


def stan(w):
    return json.loads(w.plik_stanu.read_text())


logi = []
log = logi.append


import okno_api
import pokretla
import cavebot

logi = []
log = logi.append
PLIK = TMP / "na_zywo_pokretlo.json"


def zapisz(dane):
    if dane is None:
        PLIK.unlink(missing_ok=True)
    else:
        PLIK.write_text(dane if isinstance(dane, str) else json.dumps(dane))


def restart(s, w, poz):
    """Nowy proces po kill: nowa Wyprawa/cavebot na tym samym zapisie stanu."""
    _, cb2, w2, _ = nowy(poz=poz, konf=konf_depo(), sklepy=sp_bez, stan=w.plik_stanu, swiat=s)
    krok_dokladny(cb2)
    cb2.jedzenie_nie_do = s.t + 100000
    return cb2, w2


def scenariusz(dane_pokretla, stan_przed=None, blad=False):
    """Wyprawa do depo w drodze, kill, restart. -> (s, w, cb2, w2, stan_przed_restartem)."""
    s, cb, w, k = start_depo()
    idz_ticki(s, cb, w, 50)
    if blad:
        s.blokada_marszu = True
        bieg(s, cb, w, maks=3000)
        s.blokada_marszu = False
    zapisz(dane_pokretla)
    st0 = stan(w)
    cb2, w2 = restart(s, w, tuple(s.poz))
    return s, w, cb2, w2, st0


wznow_start.WLACZONE = True

# --- 1. odczyt pokrętła (wznow_start.pokretlo) ------------------------------------------------------------------------
for nazwa, dane, oczek in (("brak pliku", None, 1), ("brak klucza", {"INNE": 3}, 1), ("WZNOW_START=1", {"WZNOW_START": 1}, 1),
                           ("WZNOW_START=0", {"WZNOW_START": 0}, 0), ("0.0 (float)", {"WZNOW_START": 0.0}, 0),
                           ("2 poza zakresem = domyślna", {"WZNOW_START": 2}, 1), ("-1 poza zakresem", {"WZNOW_START": -1}, 1),
                           ("tekst '0' = zły typ", {"WZNOW_START": "0"}, 1), ("False (bool) = zły typ", {"WZNOW_START": False}, 1),
                           ("uszkodzony JSON", "{nie json", 1), ("JSON nie-słownik", "[0]", 1)):
    zapisz(dane)
    sprawdz(f"1 pokrętło: {nazwa} -> {oczek}", wznow_start.pokretlo(PLIK) == oczek, wznow_start.pokretlo(PLIK))
pokretla_plik0 = pokretla.PLIK
pokretla.PLIK = PLIK                                      # domyślna ścieżka = na_zywo.json instancji (instancja.S.na_zywo)
zapisz({"WZNOW_START": 0})
sprawdz("1b domyślny plik pokręteł (pokretla.PLIK) jest czytany, gdy nie podano ścieżki", wznow_start.pokretlo() == 0)
pokretla.PLIK = pokretla_plik0

# --- 2. pokrętło 1 = dotychczasowe zachowanie (wznowienie) ------------------------------------------------------------
for nazwa, dane in (("WZNOW_START=1", {"WZNOW_START": 1}), ("brak klucza", {}), ("brak pliku", None)):
    s, w, cb2, w2, st0 = scenariusz(dane)
    wynik = wznow_start.sprobuj(w2, log, teraz_wall=s.wall, plik_pokretel=PLIK)
    sprawdz(f"2 [{nazwa}] restart wznawia wyprawę z bieżącej pozycji (jak dotąd)",
            wynik is True and cb2.wypad_aktywny and w2.w is not None and stan(w2).get("aktywna") is True, (wynik, logi[-2:]))
    n, wyst = bieg(s, cb2, w2, maks=14000)
    kon = ev(s, "wyprawa_koniec")
    sprawdz(f"2b [{nazwa}] wznowiona wyprawa dokończona w depo", wyst and tuple(s.poz) == DEPO and kon and kon[-1]["wynik"] == "depo", (s.poz, kon[-1:] if kon else kon))

# --- 3. pokrętło 0 = brak wznowienia + zapis zamknięty ----------------------------------------------------------------
logi.clear()
s, w, cb2, w2, st0 = scenariusz({"WZNOW_START": 0})
sprawdz("3a przed restartem zapis: wyprawa w toku (aktywna), kandydat do wznowienia", st0.get("aktywna") is True and wznow_start.jest_kandydat(w.plik_stanu, s.wall))
wznowien = []
oryg = w2._wznow
w2._wznow = lambda *a, **k: wznowien.append(1) or oryg(*a, **k)
wynik = wznow_start.sprobuj(w2, log, teraz_wall=s.wall, plik_pokretel=PLIK)
st1 = stan(w2)
sprawdz("3b WZNOW_START=0: nie wznawia (False), _wznow nie wołane, wypad nieaktywny", wynik is False and wznowien == [] and not cb2.wypad_aktywny and w2.w is None, (wynik, wznowien))
sprawdz("3c zapis wyprawy zamknięty: aktywna=False, przerwana=False, wynik anulowana_pokretlo, jest opis",
        st1.get("aktywna") is False and st1.get("przerwana") is False and st1.get("wynik") == "anulowana_pokretlo" and "WZNOW_START" in str(st1.get("opis")), st1)
sprawdz("3d log mówi o pokrętle i o zamknięciu zapisu", any("WZNOW_START=0" in l and "zapis zamknięty" in l for l in logi), logi[-2:])
sprawdz("3e zapis nie jest już kandydatem: kolejny start nie wznawia", not wznow_start.jest_kandydat(w.plik_stanu, s.wall))
sprawdz("3f reszta zapisu (powód, baza, potrzeby) zostaje do wglądu", st1.get("potrzeby") == st0.get("potrzeby") and st1.get("baza") == st0.get("baza"))
# po zamknięciu nawet pokrętło 1 nie przywraca starej wyprawy
cb3, w3 = restart(s, w, tuple(s.poz))
zapisz({"WZNOW_START": 1})
wynik3 = wznow_start.sprobuj(w3, log, teraz_wall=s.wall, plik_pokretel=PLIK)
sprawdz("3g po zamknięciu zapisu przy 0 powrót pokrętła na 1 NIE wskrzesza starej wyprawy", wynik3 is False and not cb3.wypad_aktywny and logi[-1].startswith("Start: wyprawy do wznowienia brak"), logi[-1:])

# 3h: wyprawa zakończona błędem (STOP po zacięciu) też zamykana, karencja (nast_wall) nietknięta
s, w, cb2, w2, st0 = scenariusz({"WZNOW_START": 0}, blad=True)
sprawdz("3h przed restartem: wynik blad, karencja nast_wall w przyszłości", st0.get("wynik") == "blad" and st0.get("nast_wall", 0) > s.wall, st0)
wynik = wznow_start.sprobuj(w2, log, teraz_wall=s.wall, plik_pokretel=PLIK)
st1 = stan(w2)
sprawdz("3i blad + WZNOW_START=0: bez wznowienia, zapis zamknięty (anulowana_pokretlo), karencja nast_wall bez zmian",
        wynik is False and not cb2.wypad_aktywny and st1.get("wynik") == "anulowana_pokretlo" and st1.get("aktywna") is False
        and st1.get("nast_wall") == st0.get("nast_wall"), (wynik, st1))

# 3j: zapis nieaktywny i bez przerwania (np. wynik depo) - nic do zamykania, zapis nietknięty
s, cb, w, k = start_depo()
idz_ticki(s, cb, w, 50)
w._stan_zapisz(aktywna=False, przerwana=False, wynik="depo", opis="dotarła")
zapisz({"WZNOW_START": 0})
przed = stan(w)
cb2, w2 = restart(s, w, tuple(s.poz))
wynik = wznow_start.sprobuj(w2, log, teraz_wall=s.wall, plik_pokretel=PLIK)
sprawdz("3j WZNOW_START=0 i zapis bez przerwanej wyprawy: False, zapis NIE przepisany", wynik is False and stan(w2) == przed and "i tak brak" in logi[-1], (wynik, logi[-1:]))

# 3k: przerwana=True (STOP w trakcie), aktywna=False
s, cb, w, k = start_depo()
idz_ticki(s, cb, w, 50)
w._stan_zapisz(przerwana=True, zapis_wall=s.wall)
zapisz({"WZNOW_START": 0})
cb2, w2 = restart(s, w, tuple(s.poz))
wynik = wznow_start.sprobuj(w2, log, teraz_wall=s.wall, plik_pokretel=PLIK)
sprawdz("3k przerwana=True + WZNOW_START=0: zapis zamknięty (przerwana=False)", wynik is False and stan(w2).get("przerwana") is False and stan(w2).get("wynik") == "anulowana_pokretlo", stan(w2))

# --- 4. env RETRONIC_WZNOW_START=0 nadal wystarcza (niezależnie od pokrętła) ----------------------------------------------
for nazwa, dane in (("pokrętło 1", {"WZNOW_START": 1}), ("brak klucza", None), ("pokrętło 0", {"WZNOW_START": 0})):
    wznow_start.WLACZONE = False
    s, w, cb2, w2, st0 = scenariusz(dane)
    wynik = wznow_start.sprobuj(w2, log, teraz_wall=s.wall, plik_pokretel=PLIK)
    sprawdz(f"4 env WLACZONE=False + {nazwa}: bez wznowienia", wynik is False and not cb2.wypad_aktywny)
    if dane is not None and dane.get("WZNOW_START") == 1 or dane is None:
        sprawdz(f"4b env=0 + {nazwa}: sprobuj nie dotyka zapisu (stary kod, bit w bit)", stan(w2).get("aktywna") is True and stan(w2).get("wynik") == st0.get("wynik"), stan(w2))
wznow_start.WLACZONE = True
sprawdz("4c env: RETRONIC_WZNOW_START=0 w środowisku -> WLACZONE False (import w osobnym procesie)",
        __import__("subprocess").run([sys.executable, "-I", "-c", "import sys; sys.path.insert(0, %r); import wznow_start; print(wznow_start.WLACZONE)" % _R],
                                     env={"RETRONIC_WZNOW_START": "0", "RETRONIC_TESTY": "1"}, capture_output=True, text=True).stdout.strip() == "False")

# --- 5. pokrętło widoczne dla okno_api / pokretla / przykładu / cavebota -------------------------------------------------
src = (Path(_R) / "cavebot.py").read_text()
przyklad = json.loads((Path(_R) / "na_zywo.przyklad.json").read_text())
sprawdz("5a cavebot.py: stała WZNOW_START = 1 (domyślnie wznawiaj)", "\nWZNOW_START = 1 " in src and cavebot.WZNOW_START == 1)
sprawdz("5b pokretla.ZAKRESY (0, 1), KIERUNEK nie_nizej (analityk nie wyłączy), w na_zywo.przyklad.json = 1",
        pokretla.ZAKRESY.get("WZNOW_START") == (0, 1) and pokretla.KIERUNEK.get("WZNOW_START") == "nie_nizej" and przyklad.get("WZNOW_START") == 1)
ok_, bl = pokretla.waliduj({"WZNOW_START": 0})
sprawdz("5c waliduj: 0 i 1 przyjęte, 2 i tekst odrzucone", ok_ == {"WZNOW_START": 0} and not bl and pokretla.waliduj({"WZNOW_START": 1})[0] == {"WZNOW_START": 1}
        and "WZNOW_START" not in pokretla.waliduj({"WZNOW_START": 2})[0] and "WZNOW_START" not in pokretla.waliduj({"WZNOW_START": "0"})[0])
ok_, bl = pokretla.waliduj({"WZNOW_START": 0}, {"WZNOW_START": 1})
sprawdz("5d analityk (z domyślnymi) nie może obniżyć do 0, ręczny plik może", "WZNOW_START" not in ok_ and bl, (ok_, bl))
dom, _kom = okno_api.stale_cavebota()
sprawdz("5e okno_api widzi pokrętło (domyślna z cavebot.py = 1, całkowite) -> `okno_api.py ustaw --instancja ID WZNOW_START=0` przejdzie",
        dom.get("WZNOW_START") == 1 and okno_api.calkowite_pokretlo("WZNOW_START", dom), dom.get("WZNOW_START"))
# hot-reload: Pokretla cavebota zna stałą (nie pisze 'brak stałej w cavebot.py')
komunikaty = []
mod = types.SimpleNamespace(WZNOW_START=1)
pk = pokretla.Pokretla(mod, plik=PLIK, log=komunikaty.append)
zapisz({"WZNOW_START": 0})
pk.odswiez()
sprawdz("5f Pokretla (hot-reload) przyjmuje WZNOW_START=0 bez błędu", mod.WZNOW_START == 0 and not any("odrzucone" in m or "brak stałej" in m for m in komunikaty), komunikaty)
sprawdz("5g mozg.main woła wznow_start.sprobuj PRZED dojściem i sprawdza WLACZONE (hook nietknięty)",
        "wznow_start.sprobuj(getattr(cb, \"wyprawa\", None), log)" in (Path(_R) / "mozg.py").read_text())

print()
print(f"{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
