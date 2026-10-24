"""24.10: drzwi na klucz w wypad._drzwi (Marinarra, drzwi z9 (32658,31645) Ab'Dendriel): etap DRZWI z "klucz": <id> = najpierw krok, potem Use klucza z plecaka na
kafelku drzwi (jak lina/lopata), krok. Zwykle drzwi bez zmian; brak klucza = jedna czytelna awaria drzwi_brak_klucza zamiast 6 prob. Atrapy ze test_wypad_drzwi
(swiat Frodo, drzwi (32365,32208,7)). Nic nie trafia do gry (RETRONIC_TESTY=1)."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import sys
from pathlib import Path

KAT = Path(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
_src = (KAT / "testy" / "test_wypad_drzwi.py").read_text()
_src = _src[:_src.index("# --- 1. budowa planu")]
_g = {"__file__": str(KAT / "testy" / "test_wypad_drzwi.py"), "__name__": "atrapy_drzwi"}
exec(compile(_src, "test_wypad_drzwi(atrapy)", "exec"), _g)
globals().update({k: v for k, v in _g.items() if not k.startswith("__")})
ok.clear()

KLUCZ = 2970
STOI = (32366, 32208, 7)
ZA = (32363, 32208, 7)


class OpsK(OpsD):
    """Klucz w plecaku (s.klucz) otwiera drzwi s.klucz_drzwi; bez klucza BrakPrzedmiotu jak OperacjeZywe._przedmiot_na_ekranie."""
    def uzyj_klucz(o, id_klucza, cel, poz):
        s = o.s
        s.t += 0.5
        s.klucze_uzyte.append((int(id_klucza), tuple(cel), tuple(poz)))
        if not s.klucz:
            raise wypad.BrakPrzedmiotu(f"nie widzę klucza (key {id_klucza}) w oknie plecaka")
        if max(abs(s.poz[0] - cel[0]), abs(s.poz[1] - cel[1])) > 1:
            raise wypad.BrakEkranu("za daleko")
        if tuple(cel) in s.zamkniete and s.klucz_pasuje:
            s.zamkniete.discard(tuple(cel))


def scena(klucz_w_plecaku=True, pasuje=True, zamkniete=True, klucz_id=KLUCZ, plain_otworz_od=None):
    s = swiat(otworz_od=plain_otworz_od, poz=STOI)
    s.klucz = klucz_w_plecaku
    s.klucz_pasuje = pasuje
    s.klucze_uzyte = []
    if not zamkniete:
        s.zamkniete.discard(DRZWI)
    cb, w = uruchom(s, maks=1)
    w.ops = OpsK(s)
    w.ops.log = w.logi.append
    e = {"typ": "DRZWI", "stoi": STOI, "drzwi": DRZWI}
    if klucz_id:
        e["klucz"] = klucz_id
    w.etapy = [{"typ": "IDZ", "punkty": [DO[-8], STOI]}, e, {"typ": "IDZ", "punkty": [DRZWI, ZA]}]
    w.ei, w.pi = 1, 0
    w.awarie = []
    w._awaria = lambda typ, opis, etap=None: (w.awarie.append((typ, opis)), False)[1]
    return s, cb, w, e


def biegnij(s, w, e, maks=40):
    teraz = 1000.0
    for i in range(maks):
        teraz += 5.0
        s.t += 5.0
        if w.awarie or w.ei >= 2:
            break
        w._drzwi(tuple(s.poz), e, teraz)
    return i


# 1. drzwi na klucz, klucz w plecaku: krok (nie przeszedl), klucz, krok -> przeszlismy
s, cb, w, e = scena()
biegnij(s, w, e)
sprawdz("1a drzwi na klucz: klucz uzyty raz na kafelku drzwi z pola stania, id z etapu", s.klucze_uzyte == [(KLUCZ, DRZWI, STOI)], s.klucze_uzyte)
sprawdz("1b po kluczu bot przeszedl (etap dalej, drzwi otwarte, brak awarii)", w.ei == 2 and DRZWI not in s.zamkniete and not w.awarie, (w.ei, w.awarie))
sprawdz("1c pierwsza proba to krok, nie klucz (log)", any("próba 1/6 (krok)" in l for l in w.logi) and any("próba 2/6 (klucz)" in l for l in w.logi), w.logi[-6:])

# 2. drzwi na klucz juz otwarte: sam krok, klucz nietkniety (klucz na otwartych by je zamknal)
s, cb, w, e = scena(zamkniete=False)
biegnij(s, w, e)
sprawdz("2a otwarte drzwi na klucz: przeszedl bez uzycia klucza", w.ei == 2 and s.klucze_uzyte == [] and not w.awarie, (w.ei, s.klucze_uzyte, w.awarie))

# 3. brak klucza w plecaku: jedna czytelna awaria, nie 6 prob
s, cb, w, e = scena(klucz_w_plecaku=False)
biegnij(s, w, e)
sprawdz("3a brak klucza: awaria drzwi_brak_klucza", [a[0] for a in w.awarie] == ["drzwi_brak_klucza"], w.awarie)
sprawdz("3b komunikat nazywa klucz i drzwi", w.awarie and "klucza" in w.awarie[0][1] and "2970" in w.awarie[0][1] and str(DRZWI) in w.awarie[0][1], w.awarie)
sprawdz("3c tylko jedna proba klucza i <= 2 proby w ogole (nie 6)", len(s.klucze_uzyte) == 1 and e.get("proby", 0) == 0, (s.klucze_uzyte, e))

# 4. klucz jest, ale nie pasuje: skonczona liczba prob (<= DRZWI_PROB), klucz najwyzej dwa razy, awaria drzwi_bez_wejscia
s, cb, w, e = scena(pasuje=False)
biegnij(s, w, e)
sprawdz("4a klucz nie pasuje: awaria drzwi_bez_wejscia po DRZWI_PROB probach", [a[0] for a in w.awarie] == ["drzwi_bez_wejscia"], w.awarie)
sprawdz("4b klucz uzyty co najwyzej dwa razy", len(s.klucze_uzyte) == 2, s.klucze_uzyte)

# 5. zwykle drzwi (bez "klucz") jak dotad: krok, krok, use...; klucz nigdy
s, cb, w, e = scena(klucz_id=None, plain_otworz_od=1)
biegnij(s, w, e)
sprawdz("5a zwykle drzwi: otwarte pierwszym Use, klucz nietkniety", w.ei == 2 and s.uzyc == 1 and s.klucze_uzyte == [] and not w.awarie, (w.ei, s.uzyc, s.klucze_uzyte, w.awarie))
sprawdz("5b zwykle drzwi: kolejnosc prob krok, krok, use", [("(krok)" in l, "(use)" in l) for l in w.logi if "Wypad: drzwi" in l and "próba" in l][:3]
        == [(True, False), (True, False), (False, True)], w.logi[-6:])
s, cb, w, e = scena(klucz_id=None, plain_otworz_od=None)
biegnij(s, w, e)
sprawdz("5c zwykle drzwi zawsze zamkniete: drzwi_bez_wejscia, klucz nietkniety", [a[0] for a in w.awarie] == ["drzwi_bez_wejscia"] and s.klucze_uzyte == [], (w.awarie, s.klucze_uzyte))

# 6. BrakPrzedmiotu to BrakEkranu (stare except-y lapia), a poza trybem klucz nie wywoluje awarii brak_klucza
sprawdz("6a BrakPrzedmiotu dziedziczy po BrakEkranu", issubclass(wypad.BrakPrzedmiotu, wypad.BrakEkranu))

# 7. OperacjeZywe._przedmiot_na_ekranie: brak rzeczy w otwartych pojemnikach = BrakPrzedmiotu; rzecz poza oknem / okno nieznane = zwykly BrakEkranu
import loot
_orig = (loot.znajdz_okna, loot.kontenery_z_pamieci, loot.dopasuj_okna, loot.czy_plecak)


class _Okno:
    sloty = [types_ := type("S", (), {"srodek": (10, 10)})()]


def _ops_z(kontenery):
    loot.znajdz_okna = lambda obraz: [_Okno()]
    loot.kontenery_z_pamieci = lambda: (kontenery, "")
    loot.dopasuj_okna = lambda obraz, okna, kont: (kont, "")
    loot.czy_plecak = lambda k: True
    return wypad.OperacjeZywe(zapytaj=lambda *_: {}, log=lambda *_: None)


try:
    plecak = [{"nazwa": "backpack", "id": 2854, "przedmioty": [{"id": 3031, "slot": 0}, {"id": 3457, "slot": 1}]}]
    try:
        _ops_z(plecak)._przedmiot_na_ekranie(None, KLUCZ, "klucza (key 2970)", wszystkie=True)
        rodzaj = None
    except wypad.BrakEkranu as ex:
        rodzaj = type(ex)
    sprawdz("7a klucza nie ma w plecaku: BrakPrzedmiotu", rodzaj is wypad.BrakPrzedmiotu, rodzaj)
    z_kluczem = [{"nazwa": "backpack", "id": 2854, "przedmioty": [{"id": 3031, "slot": 0}, {"id": KLUCZ, "slot": 0}]}]
    sprawdz("7b klucz w plecaku: znaleziony (srodek slotu)", _ops_z(z_kluczem)._przedmiot_na_ekranie(None, KLUCZ, "klucza", wszystkie=True) == (10, 10))
    poza = [{"nazwa": "backpack", "id": 2854, "przedmioty": [{"id": KLUCZ, "slot": 7}]}]
    try:
        _ops_z(poza)._przedmiot_na_ekranie(None, KLUCZ, "klucza", wszystkie=True)
        rodzaj = None
    except wypad.BrakEkranu as ex:
        rodzaj = type(ex)
    sprawdz("7c klucz poza widocznym oknem: zwykly BrakEkranu (nie 'brak klucza')", rodzaj is wypad.BrakEkranu, rodzaj)
finally:
    loot.znajdz_okna, loot.kontenery_z_pamieci, loot.dopasuj_okna, loot.czy_plecak = _orig

# 8. plan: tylko etapy DRZWI z PLANY_PK["klucze"] dostaja klucz
et = [{"typ": "IDZ", "punkty": [(1, 1, 9)]}, {"typ": "DRZWI", "stoi": (32658, 31644, 9), "drzwi": (32658, 31645, 9)},
      {"typ": "DRZWI", "stoi": (1, 1, 9), "drzwi": (1, 2, 9)}]
W.Wyprawa._oznacz_klucze("abdendriel_trolle_z10", et)
sprawdz("8a etap DRZWI z listy kluczy dostaje klucz, inny DRZWI i IDZ nie", et[1].get("klucz") == KLUCZ and "klucz" not in et[2] and "klucz" not in et[0], et)
et = [{"typ": "DRZWI", "stoi": (32658, 31644, 9), "drzwi": (32658, 31645, 9)}]
W.Wyprawa._oznacz_klucze("trolle_kazordoon_z9", et)
sprawdz("8b plan bez kluczy: etapy bez zmian", "klucz" not in et[0], et)

print()
print(f"{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
