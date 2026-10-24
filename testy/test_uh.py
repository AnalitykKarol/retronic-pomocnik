"""Robienie run UH (uh.py) na atrapach: bez X11, bez gry, bez gniazda (RETRONIC_TESTY=1)."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
import uh

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK  " if warunek else "FAIL"), nazwa, info)

BLANK, TARCZA, MIECZ, UHR, ZLOTO = uh.UH_BLANK_ID, 3426, 3264, 3160, 3031


class Swiat:
    """Ekwipunek + plecak (upakowany, upuszczenie na zajęte pole wstawia na początek) + mana + klawisz."""
    def __init__(s, plecak=None, pojemnosc=20, **opcje):
        s.t = 0.0
        s.ekw = {5: TARCZA, 6: MIECZ}
        s.plecak = list(plecak if plecak is not None else [ZLOTO, BLANK, ZLOTO, BLANK])
        s.pojemnosc = pojemnosc
        s.mana = 130
        s.log = []; s.drag_log = []; s.alarmy = []; s.klawisze = []
        s.stan = {}
        s.o = dict(opcje)   # cast: "ok"|"nic"|"pusty"; ignoruj_drag: {nazwa_celu: ile razy}; zrywaj_po: n odczytów
        s.odczyty = 0; s.drag_n = 0; s.przerwij_po = s.o.get("przerwij_po")
        s.ignoruj = dict(s.o.get("ignoruj", {}))   # "do_reki" / "do_plecaka": ile pierwszych przeciągnięć pominąć
        s.zerwane = False
        s.przes = s.o.get("geom_przes", 0)         # błąd mapowania indeks -> piksel (o tyle pól)
        s.weryf_ile = 0                            # ile razy wywołano weryfikację zrzutu
        s.weryf_odrzuc = s.o.get("weryf_odrzuc", 0)      # tyle pierwszych weryfikacji zgłasza niezgodność (opóźnione okno)
        s.weryf_od = s.o.get("weryf_od")                 # od której weryfikacji zawsze niezgodność

    # środowisko
    def zegar(s): return s.t
    def spij(s, d): s.t += d
    def logi(s, t): s.log.append(t)
    def alarm(s, t): s.alarmy.append(t)
    def _lacze(s):
        s.odczyty += 1
        z = s.o.get("zerwij_po")
        if z is not None and s.odczyty > z:
            s.zerwane = True
        if s.zerwane:
            raise ConnectionRefusedError("gniazdo")
    def ekwipunek(s):
        s._lacze(); s.t += 0.05
        return {k: {"id": v, "ilosc": 1} for k, v in s.ekw.items()}
    def kontenery(s):
        s._lacze()
        return [{"numer": 1, "nazwa": "backpack", "id": 2854, "pojemnosc": s.pojemnosc,
                 "przedmioty": [{"slot": i, "id": v, "ilosc": 1} for i, v in enumerate(s.plecak)]}]
    def mana_(s): return s.mana
    @staticmethod
    def _px(c): return (581 + (c % 4) * 37, 580 + (c // 4) * 37)
    def geometria(s):
        return {"reka": {5: (649, 338), 6: (576, 338)}, "plecak": [s._px(i + s.przes) for i in range(20)]}
    def weryfikuj_plecak(s, geom, kontener):
        """Atrapa porównania zrzutu z pamięcią: zgłasza niezgodność, gdy siatka nie jest zgodna z prawdziwą."""
        s.weryf_ile += 1
        if s.przes:
            return "ekran != pamięć: siatka przesunięta"
        if s.weryf_ile <= s.weryf_odrzuc or (s.weryf_od is not None and s.weryf_ile >= s.weryf_od):
            return "ekran != pamięć: okno się nie odświeżyło"
        return None
    def przerwanie(s):
        if s.o.get("po_rzucie") and s.klawisze:
            return "stwór po rzucie"
        if s.przerwij_po is not None and s.drag_n >= s.przerwij_po:
            return "stwór w widoku"
        return None
    def klawisz(s, k):
        s.klawisze.append(k)
        r = s.ekw.get(5)
        if k != uh.UH_KLAWISZ:
            return
        c = s.o.get("cast", "ok")
        if r != BLANK or c == "nic":
            return
        if c == "pusty":
            s.mana -= 100; s.ekw.pop(5); return
        if s.mana >= 100:
            s.mana -= 100; s.ekw[5] = UHR
    def _gdzie(s, xy):
        g = s.geometria()
        for sl, c in g["reka"].items():
            if c == xy:
                return ("reka", sl)
        return ("plecak", next(c for c in range(40) if s._px(c) == xy))
    def przeciagnij(s, x1, y1, x2, y2):
        s.drag_n += 1
        a, b = s._gdzie((x1, y1)), s._gdzie((x2, y2))
        s.drag_log.append((a, b))
        v = s.ekw.get(a[1]) if a[0] == "reka" else (s.plecak[a[1]] if a[1] < len(s.plecak) else None)
        cel = ("tarcza_do_reki" if b[0] == "reka" else "tarcza") if v == TARCZA else "blank" if v == BLANK else "runa"
        if s.ignoruj.get(cel, 0) > 0:
            s.ignoruj[cel] -= 1; return
        if a[0] == "reka":
            if a[1] not in s.ekw or len(s.plecak) >= s.pojemnosc:
                return
            v = s.ekw.pop(a[1])
            s.plecak.insert(0, v)          # serwer wstawia na początek kontenera
        else:
            if a[1] >= len(s.plecak) or b[1] in s.ekw:
                return
            v = s.plecak.pop(a[1])
            s.ekw[b[1]] = v

def srod(s):
    class E: pass
    e = E()
    e.zegar, e.spij, e.log, e.alarm = s.zegar, s.spij, s.logi, s.alarm
    e.ekwipunek, e.kontenery, e.mana = s.ekwipunek, s.kontenery, s.mana_
    e.geometria, e.przeciagnij, e.klawisz, e.przerwanie = s.geometria, s.przeciagnij, s.klawisz, s.przerwanie
    e.stan = s.stan
    if s.o.get("weryfikacja", True):
        e.weryfikuj_plecak = s.weryfikuj_plecak
    if hasattr(s, "weryfikuj_runy") and s.o.get("weryfikacja", True):
        e.weryfikuj_runy = s.weryfikuj_runy
    return e

def uruchom(**kw):
    s = Swiat(**kw)
    return s, uh.zrob_runa(srod(s), slot=5)

def kroki(w): return [k["nazwa"] for k in w["kroki"]]

# 0. kontrakt
sprawdz("0a domyślnie wyłączone", uh.UH_AKTYWNY == 0 and uh.UH_KLAWISZ == "F5" and uh.UH_KOSZT + uh.UH_REZERWA == 125 and uh.UH_MIN_HP == 90)

# 1. sukces
s, w = uruchom()
sprawdz("1a ok", w["wynik"] == "ok" and not w["alarm"], w)
sprawdz("1b tarcza wróciła, runa w plecaku", s.ekw[5] == TARCZA and s.ekw[6] == MIECZ and UHR in s.plecak
        and s.plecak.count(BLANK) == 1, (s.ekw, s.plecak))
sprawdz("1c kolejność", kroki(w) == ["tarcza_do_plecaka", "blank_do_reki", "cast", "runa_do_plecaka", "tarcza_do_reki", "tarcza_wrocila"], kroki(w))
sprawdz("1d jeden rzut F5, mana -100", s.klawisze == ["F5"] and s.mana == 30, (s.klawisze, s.mana))
sprawdz("1e stan wyczyszczony", "tarcza_id" not in s.stan)
sprawdz("1f spadek many w kroku cast", [k for k in w["kroki"] if k["nazwa"] == "cast"][0]["spadek_many"] == 100)

# 2. brak blank runy: zero ruchów
s, w = uruchom(plecak=[ZLOTO, ZLOTO])
sprawdz("2 brak_blank bez ruchów", w["wynik"] == "brak_blank" and s.drag_log == [] and s.ekw[5] == TARCZA, w)

# 3. brak miejsca
s, w = uruchom(plecak=[BLANK] + [ZLOTO] * 19)
sprawdz("3 brak miejsca bez ruchów", w["wynik"] == "przerwane" and "brak_miejsca" in w["powod"] and s.drag_log == [] and s.ekw[5] == TARCZA, w)

# 4. tarcza nie wróciła: pierwsza próba zignorowana, druga działa
s, w = uruchom(ignoruj={"tarcza_do_reki": 1})
sprawdz("4a druga próba przywraca", w["wynik"] == "ok" and s.ekw[5] == TARCZA and not w["alarm"], w)
sprawdz("4b dwa przeciągnięcia tarczy", kroki(w).count("tarcza_do_reki") == 2, kroki(w))
# 4c: nigdy nie wraca: alarm
s, w = uruchom(ignoruj={"tarcza_do_reki": 99})
sprawdz("4c alarm", w["wynik"] == "przerwane" and w["alarm"] and "tarcza" in w["powod"] and s.alarmy, w)
sprawdz("4d tarcza w plecaku", TARCZA in s.plecak and 5 not in s.ekw or s.ekw.get(5) != TARCZA)
sprawdz("4e stan pamięta tarczę", s.stan.get("tarcza_id") == TARCZA, s.stan)
# 4f: restart w środku: przywroc() z zapamiętanym stanem odzyskuje tarczę
s.o["ignoruj"] = {}; s.ignoruj = {}
w2 = uh.przywroc(srod(s), slot=5)
sprawdz("4f przywróć po restarcie", s.ekw[5] == TARCZA and w2["wynik"] in ("ok", "przerwane") and "tarcza_id" not in s.stan
        and s.klawisze == ["F5"] and UHR in s.plecak, (w2, s.ekw, s.plecak, s.klawisze))
s.stan.clear()
sprawdz("4g przywróć bez stanu: nic", uh.przywroc(srod(s), slot=5)["powod"] == "nic do przywrócenia")

# 5. nieudany cast (mana nie spadła, slot bez zmiany): blank wraca, tarcza wraca
s, w = uruchom(cast="nic")
sprawdz("5a przerwane", w["wynik"] == "przerwane" and "cast" in w["powod"], w)
sprawdz("5b stan wyjściowy", s.ekw[5] == TARCZA and s.plecak.count(BLANK) == 2 and not w["alarm"], (s.ekw, s.plecak))
sprawdz("5c dwa rzuty (limit)", s.klawisze == ["F5", "F5"] and s.mana == 130, s.klawisze)

# 6. slot pusty po rzuceniu (czar się nie udał): przerwanie, tarcza wraca
s, w = uruchom(cast="pusty")
sprawdz("6a przerwane", w["wynik"] == "przerwane" and "pusty" in w["powod"], w)
sprawdz("6b tarcza z powrotem", s.ekw[5] == TARCZA and s.klawisze == ["F5"], (s.ekw, s.klawisze))

# 7. stwór w trakcie: po zdjęciu tarczy natychmiastowy powrót, bez rzutu
s, w = uruchom(przerwij_po=1)
sprawdz("7a przerwane", w["wynik"] == "przerwane" and "stwór" in w["powod"], w)
sprawdz("7b tarcza wróciła, blank w plecaku, bez rzutu", s.ekw[5] == TARCZA and s.klawisze == [] and s.plecak.count(BLANK) == 2, (s.ekw, s.plecak, s.klawisze))
# 7c: stwór po rzucie: runa do plecaka, tarcza wraca
s, w = uruchom(po_rzucie=True)
sprawdz("7c po rzucie: runa schowana", w["wynik"] == "przerwane" and s.ekw[5] == TARCZA and UHR in s.plecak, (w["powod"], s.ekw, s.plecak))
# 7d: stwór od razu: nic nie rusza
s, w = uruchom(przerwij_po=0)
sprawdz("7d przed startem", w["wynik"] == "przerwane" and s.drag_log == [], w)

# 8. zerwanie połączenia
s, w = uruchom(zerwij_po=0)
sprawdz("8a na starcie: brak_odczytu, bez ruchów", w["wynik"] == "przerwane" and "brak_odczytu" in w["powod"] and s.drag_log == [], w)
s, w = uruchom(zerwij_po=8)
sprawdz("8b w trakcie: alarm, bez klawiszy po zerwaniu", w["wynik"] == "przerwane" and w["alarm"] and "brak_odczytu" in w["powod"], w)

# 9. budżet czasu: bez nieskończonej pętli
s, w = uruchom(cast="nic", ignoruj={"blank": 99})
sprawdz("9 kończy się", w["wynik"] == "przerwane" and w["czas_s"] < uh.UH_MAKS_CZAS_S + uh.UH_CZAS_POWROTU_S + 5, w["czas_s"])

# 10. slot ręki pusty / z blank na starcie
s = Swiat(); s.ekw.pop(5)
w = uh.zrob_runa(srod(s), slot=5)
# 23.10: pusty slot i brak tarczy w plecakach = runa bez tarczy (wcześniej przerwanie slot_bez_tarczy)
sprawdz("10 pusty slot, brak tarczy: runa bez tarczy", w["wynik"] == "ok" and UHR in s.plecak and 5 not in s.ekw and not w["alarm"], w)

# 11. mozna_robic
g = {"hp": 190, "max_hp": 200, "mana": 130, "max_mana": 130}
sprawdz("11a wyłączone", uh.mozna_robic(g, [], aktywny=0) == (False, "wyłączone"))
sprawdz("11b ok", uh.mozna_robic(g, [], aktywny=1) == (True, "ok"))
sprawdz("11c stwór w widoku", uh.mozna_robic(g, [{"nazwa": "Troll", "gracz": False, "hp": 100}], aktywny=1)[0] is False)
sprawdz("11d tylko ja", uh.mozna_robic(g, [{"nazwa": "Ja", "gracz": True}], aktywny=1, ja="Ja")[0] is True)
sprawdz("11e obcy gracz blokuje", uh.mozna_robic(g, [{"nazwa": "X", "gracz": True}], aktywny=1, ja="Ja")[0] is False)
sprawdz("11f HP 89%", uh.mozna_robic(dict(g, hp=178), [], aktywny=1)[0] is False)
sprawdz("11g mana 124", uh.mozna_robic(dict(g, mana=124), [], aktywny=1)[0] is False)
sprawdz("11h walka/ucieczka/loot", all(not uh.mozna_robic(g, [], aktywny=1, **{k: True})[0] for k in ("walka", "ucieczka", "loot")))
sprawdz("11i odstęp", uh.mozna_robic(g, [], aktywny=1, teraz=100, ostatnia=90)[0] is False
        and uh.mozna_robic(g, [], aktywny=1, teraz=100, ostatnia=70)[0] is True)

# 11j. inny czar: adura gran, 60 many, własny klawisz
try:
    uh.ustaw("adura gran", klawisz="F6")
    sprawdz("11j ustaw", (uh.UH_CZAR, uh.UH_KOSZT, uh.UH_KLAWISZ) == ("adura gran", 60, "F6"))
    sprawdz("11k próg many 85", uh.mozna_robic(dict(g, mana=85), [], aktywny=1)[0] is True
            and uh.mozna_robic(dict(g, mana=84), [], aktywny=1)[0] is False)
    s = Swiat(); s.mana = 70
    s_klaw = s.klawisz
    def klaw6(k, s=s):
        s.klawisze.append(k)
        if k == "F6" and s.ekw.get(5) == BLANK and s.mana >= 60:
            s.mana -= 60; s.ekw[5] = UHR
    s.klawisz = klaw6
    w = uh.zrob_runa(srod(s), slot=5)
    sprawdz("11l pełna sekwencja adura gran", w["wynik"] == "ok" and s.klawisze == ["F6"] and s.mana == 10
            and s.ekw[5] == TARCZA and [k for k in w["kroki"] if k["nazwa"] == "cast"][0]["spadek_many"] == 60, w)
    try:
        uh.ustaw("nieznany"); sprawdz("11m nieznany bez kosztu", False)
    except ValueError:
        sprawdz("11m nieznany bez kosztu", True)
finally:
    uh.ustaw("adura vita", klawisz="F5")

# 12. geometria z prawdziwego zrzutu kalibracyjnego i z przesuniętego (bez stałych pikseli)
try:
    from PIL import Image
    obraz = Image.open(_os.path.join(_os.path.dirname(__file__), "dane", "uh_zrzut.png")).convert("RGB")
    g = uh.geometria_z_obrazu(obraz)
    sprawdz("12a prawdziwy zrzut: ręce", g and g["reka"][6] == (576, 338) and g["reka"][5] == (649, 338), g and g["reka"])
    sprawdz("12b plecak 20 pól, pole 0", g and len(g["plecak"]) == 20 and g["plecak"][0] == (580, 581), g and g["plecak"][:2])
    # panel przesunięty o (-5, +0) i plecak niżej: wycinek przesunięty w prawo o 0 jest niemożliwy,
    # więc przesuwamy cały obraz o 20 px w dół (wynik: współrzędne + 20)
    pod = Image.new("RGB", (obraz.size[0], obraz.size[1] + 20), (20, 20, 20))
    pod.paste(obraz, (0, 20))
    g2 = uh.geometria_z_obrazu(pod)
    sprawdz("12c przesunięcie okna +20 px", g2 and g2["reka"][6] == (576, 358) and g2["reka"][5] == (649, 358), g2 and g2["reka"])
    sprawdz("12d pusty obraz: None", uh.geometria_z_obrazu(Image.new("RGB", (734, 910), (20, 20, 20))) is None)
except ImportError:
    pass


# 13. układ jak na żywo 12.10 21:22: blank w polach 10-15, gotowe runy HMM (3198) w 1-4 i 6, łopata na 0
LOPATA, PLAT, SZYNKA, HMM = 3457, 3035, 3582, 3198
ZYWY = [LOPATA, HMM, HMM, HMM, HMM, PLAT, HMM, SZYNKA, ZLOTO, ZLOTO] + [BLANK] * 6
s, w = uruchom(plecak=list(ZYWY))
sprawdz("13a układ jak na żywo: ok", w["wynik"] == "ok" and s.ekw[5] == TARCZA and not w["alarm"], w)
zle = [k for k in w["kroki"] if not k["ok"]]
sprawdz("13b bez nieudanych kroków", not zle, zle)
sprawdz("13c nic nie zginęło (multizbiór)", sorted(s.plecak) == sorted(ZYWY[:-1] + [UHR]) , sorted(s.plecak))
sprawdz("13d łopata i gotowe runy nietknięte (1 blank użyty)",
        s.plecak.count(LOPATA) == 1 and s.plecak.count(HMM) == 5 and s.plecak.count(PLAT) == 1 and s.plecak.count(BLANK) == 5, s.plecak)

# 13e. błąd mapowania indeks -> piksel (o jedno pole): z weryfikacją zrzutu NIC się nie rusza
s, w = uruchom(plecak=list(ZYWY), geom_przes=1)
sprawdz("13e przesunięta siatka: zero ruchów, tarcza w ręce, bez alarmu",
        w["wynik"] == "przerwane" and s.drag_log == [] and s.ekw[5] == TARCZA and s.plecak == ZYWY and not w["alarm"], (w["powod"], s.drag_log))
sprawdz("13f odmowa ma powód", any("bez ruchu" in str(k.get("powod")) for k in w["kroki"]), kroki(w))

# 13g. okno plecaka odświeża się z opóźnieniem (3 pierwsze porównania zrzutu niezgodne): czekamy i robimy
s, w = uruchom(plecak=list(ZYWY), weryf_odrzuc=3)
sprawdz("13g opóźnione okno: ok po odczekaniu", w["wynik"] == "ok" and s.ekw[5] == TARCZA and s.plecak.count(BLANK) == 5, w)

# 13h. po zdjęciu tarczy ekran przestaje się zgadzać: nie ruszamy cudzych przedmiotów, alarm o tarczy
s, w = uruchom(plecak=list(ZYWY), weryf_od=2)
sprawdz("13h tylko jedno przeciągnięcie (tarcza do plecaka), reszta odmówiona",
        len(s.drag_log) == 1 and w["alarm"] and s.stan.get("tarcza_id") == TARCZA, (len(s.drag_log), w["powod"]))
sprawdz("13i nikt poza tarczą nie ruszony", sorted(s.plecak) == sorted(ZYWY + [TARCZA]), s.plecak)

# 14. geometria: podświetlone (najechane) pole nie może przesuwać indeksów
try:
    from PIL import Image, ImageDraw
    obraz = Image.open(_os.path.join(_os.path.dirname(__file__), "dane", "uh_zrzut.png")).convert("RGB")
    g0 = uh.geometria_z_obrazu(obraz)
    bazowa = g0["plecak"]
    for idx in (0, 1, 4, 5, 6, 7, 10, 13, 19):
        im = obraz.copy()
        cx, cy = bazowa[idx]
        ImageDraw.Draw(im).rectangle((cx - 17, cy - 17, cx + 16, cy + 16), outline=(40, 160, 220))
        gi = uh.geometria_z_obrazu(im)
        sprawdz(f"14 podświetlone pole {idx}: siatka bez zmian", gi and gi["plecak"] == bazowa, gi and len(gi["plecak"]))
    # dwa podświetlone pola w jednym rzędzie (hover + zaznaczenie)
    im = obraz.copy()
    d = ImageDraw.Draw(im)
    for idx in (5, 6):
        cx, cy = bazowa[idx]
        d.rectangle((cx - 17, cy - 17, cx + 16, cy + 16), outline=(40, 160, 220))
    gi = uh.geometria_z_obrazu(im)
    sprawdz("14b dwa podświetlone pola w rzędzie", gi and gi["plecak"] == bazowa, gi and len(gi["plecak"]))
except ImportError:
    pass

# 15. zgodnosc_plecaka: porównanie zrzutu z kolejnością z pamięci (syntetyczna siatka 4x5, ikony po ID)
try:
    from PIL import Image, ImageDraw
    import random
    def wzor(ident):
        r = random.Random(ident)
        ik = Image.new("RGB", (34, 34), (30, 30, 30))
        d = ImageDraw.Draw(ik)
        for _ in range(6):
            x, y = r.randrange(4, 26), r.randrange(4, 26)
            d.rectangle((x, y, x + r.randrange(3, 8), y + r.randrange(3, 8)), fill=(r.randrange(80, 255), r.randrange(80, 255), r.randrange(80, 255)))
        return ik
    def siatka(ukl):
        im = Image.new("RGB", (200, 200), (20, 20, 20))
        for i, ident in enumerate(ukl):
            if ident:
                im.paste(wzor(ident), (10 + (i % 4) * 37, 10 + (i // 4) * 37))
        return im
    srodki = [(10 + (i % 4) * 37 + 17, 10 + (i // 4) * 37 + 17) for i in range(20)]
    przedm = [{"slot": i, "id": v, "ilosc": 1} for i, v in enumerate(ZYWY)]
    ukl = list(ZYWY) + [None] * 4
    ok_, pw = uh.zgodnosc_plecaka(siatka(ukl), srodki, przedm)
    sprawdz("15a zgodny układ", ok_, pw)
    zam = list(ukl); zam[14], zam[1] = zam[1], zam[14]       # ekran: blank tam gdzie pamięć ma gotową runę
    ok_, pw = uh.zgodnosc_plecaka(siatka(zam), srodki, przedm)
    sprawdz("15b zamienione pola: niezgodność", not ok_, pw)
    prz = [None] + ukl[:-1]                                   # ekran przesunięty o pole (nowy przedmiot z przodu)
    ok_, pw = uh.zgodnosc_plecaka(siatka(prz), srodki, przedm)
    sprawdz("15c ekran przesunięty o jedno pole: niezgodność", not ok_, pw)
    ok_, pw = uh.zgodnosc_plecaka(siatka([None] + ukl[:-1]), [(x, y) for x, y in srodki], przedm[:-1])
    sprawdz("15d pole zajęte na ekranie, wolne w pamięci: niezgodność", not ok_, pw)
except ImportError:
    pass

# 16. pojemnik na runy (Purple backpack, id 2868) otwarty obok plecaka: gotowa runa trafia do niego,
#     blank bierzemy z plecaka, a gdy go tam nie ma, z pojemnika na runy
class SwiatRuny(Swiat):
    """Plecak (numer 1) + Purple backpack (numer 0, osobna siatka pikseli, upakowany, wstawianie na początek)."""
    def __init__(s, runy=None, runy_pojemnosc=20, **opcje):
        super().__init__(**opcje)
        s.runy = list(runy if runy is not None else [])
        s.runy_poj = runy_pojemnosc
        s.weryf_runy_ile = 0
    @staticmethod
    def _pxr(c): return (581 + (c % 4) * 37, 780 + (c // 4) * 37)
    def kontenery(s):
        k = super().kontenery()
        k.insert(0, {"numer": 0, "nazwa": "purple backpack", "id": 2868, "pojemnosc": s.runy_poj,
                     "przedmioty": [{"slot": i, "id": v, "ilosc": 1} for i, v in enumerate(s.runy)]})
        return k
    def geometria(s):
        g = super().geometria()
        if not s.o.get("bez_geom_runy"):
            g["runy"] = [s._pxr(i) for i in range(20)]
        return g
    def weryfikuj_runy(s, geom, kontener):
        s.weryf_runy_ile += 1
        return "ekran != pamięć (runy): okno" if s.o.get("weryf_runy_zle") else None
    def _gdzie(s, xy):
        for c in range(20):
            if s._pxr(c) == xy:
                return ("runy", c)
        return super()._gdzie(xy)
    def przeciagnij(s, x1, y1, x2, y2):
        a, b = s._gdzie((x1, y1)), s._gdzie((x2, y2))
        if "runy" not in (a[0], b[0]):
            return super().przeciagnij(x1, y1, x2, y2)
        s.drag_n += 1
        s.drag_log.append((a, b))
        if a[0] == "reka" and b[0] == "runy":
            if a[1] in s.ekw and len(s.runy) < s.runy_poj:
                s.runy.insert(0, s.ekw.pop(a[1]))
        elif a[0] == "runy" and b[0] == "reka":
            if a[1] < len(s.runy) and b[1] not in s.ekw:
                s.ekw[b[1]] = s.runy.pop(a[1])

HMM = 3198
def uruchom_r(**kw):
    s = SwiatRuny(**kw)
    return s, uh.zrob_runa(srod(s), slot=5)

# 16a. blank w plecaku, w pojemniku wolne miejsce: gotowa runa do pojemnika, tarcza do plecaka i z powrotem
s, w = uruchom_r(plecak=[ZLOTO, BLANK], runy=[HMM] * 5)
sprawdz("16a ok", w["wynik"] == "ok" and not w["alarm"] and s.ekw[5] == TARCZA, w)
sprawdz("16b runa w pojemniku, nie w plecaku", s.runy.count(UHR) == 1 and UHR not in s.plecak
        and s.runy.count(HMM) == 5 and s.plecak == [ZLOTO], (s.runy, s.plecak))
cel_runy = [k for k in w["kroki"] if k["nazwa"] == "runa_do_plecaka"]
sprawdz("16c krok runy z dokad=runy i weryfikacja okna runy", cel_runy and cel_runy[0].get("dokad") == "runy"
        and s.weryf_runy_ile >= 1, cel_runy)
sprawdz("16d runa na pierwsze wolne pole pojemnika (pole 5)", s.drag_log[2] == (("reka", 5), ("runy", 5)), s.drag_log)

# 16e. blank tylko w pojemniku na runy (jak na żywo): źródło blank = pojemnik, runa wraca do pojemnika
ZYW_R = [BLANK] * 11 + [HMM] * 9
s, w = uruchom_r(plecak=[ZLOTO, 3035], runy=list(ZYW_R), runy_pojemnosc=20)
sprawdz("16e blank z pojemnika: ok", w["wynik"] == "ok" and s.ekw[5] == TARCZA and not w["alarm"], w)
sprawdz("16f pojemnik: -1 blank, +1 UH, nic nie zginęło", s.runy.count(BLANK) == 10 and s.runy.count(UHR) == 1
        and s.runy.count(HMM) == 9 and sorted(s.plecak) == sorted([ZLOTO, 3035]), (s.runy, s.plecak))

# 16g. pojemnik pełny, blank w plecaku: runa do plecaka (jak dotąd)
s, w = uruchom_r(plecak=[ZLOTO, BLANK], runy=[HMM] * 20)
sprawdz("16g pełny pojemnik: runa do plecaka", w["wynik"] == "ok" and UHR in s.plecak and s.runy == [HMM] * 20
        and s.ekw[5] == TARCZA, (w, s.plecak))

# 16h. okno pojemnika niewidoczne w geometrii: runa do plecaka
s, w = uruchom_r(plecak=[ZLOTO, BLANK], runy=[HMM] * 5, bez_geom_runy=True)
sprawdz("16h bez siatki runy: plecak", w["wynik"] == "ok" and UHR in s.plecak and s.runy == [HMM] * 5, (w, s.plecak))

# 16i. weryfikacja okna pojemnika odrzuca (ekran != pamięć): nic z pojemnika nie ruszone; runa zostaje w ręce
#      bezpiecznie albo trafia do plecaka (cel runy wybrany tylko, gdy weryfikacja przechodzi przy ruchu)
s, w = uruchom_r(plecak=[ZLOTO, BLANK], runy=[HMM] * 5, weryf_runy_zle=True)
sprawdz("16i zła weryfikacja runy: pojemnik nietknięty, tarcza z powrotem", s.runy == [HMM] * 5
        and s.ekw[5] == TARCZA and not w["alarm"] and sorted(s.plecak) in (sorted([ZLOTO, UHR]), sorted([ZLOTO, BLANK])), (w, s.runy, s.plecak))

# 16j. blank tylko w pojemniku, a jego okna nie ma w geometrii: nic nie ginie, tarcza wraca
s, w = uruchom_r(plecak=[ZLOTO], runy=[BLANK] + [HMM] * 5, bez_geom_runy=True)
sprawdz("16j blank poza widocznym oknem: przerwane bez alarmu", w["wynik"] == "przerwane" and s.ekw[5] == TARCZA
        and not w["alarm"] and s.runy == [BLANK] + [HMM] * 5, (w, s.runy))

# 16k. brak blank gdziekolwiek: zero ruchów
s, w = uruchom_r(plecak=[ZLOTO], runy=[HMM] * 5)
sprawdz("16k brak blank: brak_blank bez ruchów", w["wynik"] == "brak_blank" and s.drag_log == [], w)

# 16l. pojemnik na runy nie jest brany za plecak (_plecak) i działa wariant bez niego (testy 1-15)
sprawdz("16l _plecak ignoruje pojemnik", uh._plecak(SwiatRuny(plecak=[ZLOTO]).kontenery())["numer"] == 1)

# 16p. jak na żywo 13.10: okna przycięte (plecak 8 widocznych pól z 8 przedmiotami, pojemnik na runy 16 z 20),
#      brak widocznego wolnego pola: tarcza na pole z runą w pojemniku (serwer wstawia na początek), potem wraca
class SwiatPrzyciete(SwiatRuny):
    def geometria(s):
        g = super().geometria()
        g["plecak"] = g["plecak"][:s.o.get("wid_plecak", 8)]
        g["runy"] = g["runy"][:s.o.get("wid_runy", 16)]
        return g

def uruchom_p(**kw):
    s = SwiatPrzyciete(**kw)
    return s, uh.zrob_runa(srod(s), slot=5)

ZYW_P = [ZLOTO, 3035, 2854, 3456, ZLOTO, ZLOTO, 3035, ZLOTO]
s, w = uruchom_p(plecak=list(ZYW_P), runy=[BLANK] * 11 + [HMM] * 4 + [UHR], runy_pojemnosc=20)
sprawdz("16p tarcza na pole z runą, ok", w["wynik"] == "ok" and not w["alarm"] and s.ekw[5] == TARCZA, w)
sprawdz("16q krok na zajęte pole runy, plecak nietknięty", "tarcza_na_zajete_pole_runy" in kroki(w)
        and s.plecak == ZYW_P and s.drag_log[0][0] == ("reka", 5) and s.drag_log[0][1][0] == "runy", (kroki(w), s.drag_log))
sprawdz("16r pojemnik: nic nie zginęło (+1 UH, -1 blank)", s.runy.count(BLANK) == 10 and s.runy.count(UHR) == 2
        and s.runy.count(HMM) == 4 and TARCZA not in s.runy, s.runy)

# 16s. pojemnik pełny i nic widocznego: przerwane bez ruchów, bez alarmu, pauza w mozna_robic
uh._brak_miejsca_od = None
s, w = uruchom_p(plecak=list(ZYW_P), runy=[BLANK] * 11 + [HMM] * 9, runy_pojemnosc=20)
sprawdz("16s pełny pojemnik, brak widocznego pola: bez ruchów", w["wynik"] == "przerwane" and "brak_miejsca" in w["powod"]
        and s.drag_log == [] and s.ekw[5] == TARCZA and not w["alarm"], w)
g_ok = {"hp": 100, "max_hp": 100, "mana": 150}
r1 = uh.mozna_robic(g_ok, [], aktywny=1, teraz=uh._brak_miejsca_od + 30)
r2 = uh.mozna_robic(g_ok, [], aktywny=1, teraz=uh._brak_miejsca_od + uh.UH_PONOW_BRAK_MIEJSCA_S + 1)
sprawdz("16t pauza ~60 s po braku miejsca", not r1[0] and "brak miejsca" in r1[1] and r2[0], (r1, r2))

# 16u. wolne pole widoczne w pojemniku jak dotąd (bez kroku na zajęte pole)
s, w = uruchom_p(plecak=list(ZYW_P), runy=[BLANK] * 5, runy_pojemnosc=20)
sprawdz("16u wolne widoczne pole: standardowo", w["wynik"] == "ok" and "tarcza_na_zajete_pole_runy" not in kroki(w), kroki(w))

# 16m. geometria z obrazu: siatka okna pojemnika różna od siatki plecaka; role z pamięci (syntetyczny zrzut)
try:
    from PIL import Image, ImageDraw
    import numpy as _np
    import loot as _loot
    def okno_syn(im, x, y, wiersze):
        d = ImageDraw.Draw(im)
        for r in range(wiersze):
            for c in range(4):
                d.rectangle((x + c * 37, y + r * 37, x + c * 37 + 33, y + r * 37 + 33), outline=_loot.RAMKA)
    im = Image.new("RGB", (734, 910), (20, 20, 20))
    okno_syn(im, 580, 360, 2)       # plecak
    okno_syn(im, 580, 560, 2)       # pojemnik na runy
    okna_s = _loot.znajdz_okna(im)
    k_bag = {"numer": 1, "nazwa": "backpack", "id": 2854, "pojemnosc": 8, "przedmioty": []}
    k_run = {"numer": 0, "nazwa": "purple backpack", "id": 2868, "pojemnosc": 8, "przedmioty": []}
    sprawdz("16m dwa okna wykryte", len(okna_s) == 2, okna_s)
    przyp, pw = _loot.dopasuj_okna(im, okna_s, [k_run, k_bag])
    sprawdz("16n pamięć przypisuje role (pusty ekran: remis)", przyp is None or [k["nazwa"] for k in przyp]
            in (["backpack", "purple backpack"], ["purple backpack", "backpack"]), pw)
    m = _loot._maska_ramki(_np.asarray(im).astype(_np.int16))
    sprawdz("16o siatka okna pojemnika inna niż plecaka", uh._siatka_plecaka(m, okna_s[1]) != uh._siatka_plecaka(m, okna_s[0])
            and len(uh._siatka_plecaka(m, okna_s[1])) == 8, uh._siatka_plecaka(m, okna_s[1])[:2])
except ImportError:
    pass

# 17. awarie 15.10: ekwipunek nieczytelny po relogu i nieaktualny po zmianie tarczy
VIK = 3431
class SwiatEkw(Swiat):
    """Opcje: ekw_none_n (tyle pierwszych odczytów ekwipunku = None), koszt_odczytu (s zegara na odczyt),
    ekw_zamrozony (ekwipunek zawsze zwraca ten stan = nieaktualna tablica), ekw_none_po_ruchu (n odczytów None po 1. ruchu)."""
    def ekwipunek(s):
        s._lacze(); s.t += s.o.get("koszt_odczytu", 0.05)
        s.odczyty_ekw = getattr(s, "odczyty_ekw", 0) + 1
        if s.odczyty_ekw <= s.o.get("ekw_none_n", 0):
            return None
        n = s.o.get("ekw_none_po_ruchu")
        if n and s.drag_n >= 1:
            s.po_ruchu = getattr(s, "po_ruchu", 0) + 1
            if s.po_ruchu <= n:
                return None
        e = s.o.get("ekw_zamrozony", s.ekw)
        return {k: {"id": v, "ilosc": 1} for k, v in e.items()}

def srod2(s):
    e = srod(s)
    if "ekran" in s.o:
        e.tarcza_na_ekranie = lambda slot, ident, geom, kont: s.o["ekran"]
    return e

def uruchom2(**kw):
    s = SwiatEkw(**kw)
    return s, uh.zrob_runa(srod2(s), slot=5)

# 17a. ekwipunek None na starcie (co odczyt 17 s jak wolne szukanie tablicy): bez czekania, bez ruchów, bez alarmu
s, w = uruchom2(ekw_none_n=99, koszt_odczytu=17.0)
sprawdz("17a brak_ekwipunku od razu", w["wynik"] == "brak_ekwipunku" and w["powod"] == "brak_ekwipunku" and not w["alarm"]
        and s.drag_log == [] and s.klawisze == [] and s.ekw[5] == TARCZA, w)
sprawdz("17b bez 52 s czekania (jeden odczyt)", w["czas_s"] <= 20 and s.odczyty_ekw == 1, (w["czas_s"], s.odczyty_ekw))
s, w = uruchom2(ekw_none_n=0)
sprawdz("17c po powrocie ekwipunku normalny przebieg", w["wynik"] == "ok" and s.ekw[5] == TARCZA and UHR in s.plecak, w)
# 17d. wolny start: odczyt 16 s => nie ruszamy tarczy
s, w = uruchom2(koszt_odczytu=16.0)
sprawdz("17d wolny_start: bez ruchów", w["wynik"] == "przerwane" and w["powod"].startswith("wolny_start")
        and s.drag_log == [] and s.ekw[5] == TARCZA and not w["alarm"], w)

# 17e. nieaktualny ekwipunek: tarcza naprawdę zeszła do plecaka, tablica dalej pokazuje ją w slocie
s, w = uruchom2(ekw_zamrozony={5: VIK, 6: MIECZ})
s.ekw = {5: VIK, 6: MIECZ}
s2 = SwiatEkw(ekw_zamrozony={5: VIK, 6: MIECZ}); s2.ekw = {5: VIK, 6: MIECZ}
w2 = uh.zrob_runa(srod2(s2), slot=5)
sprawdz("17e krok tarcza_do_plecaka uznany przez kontenery", [k for k in w2["kroki"] if k["nazwa"] == "tarcza_do_plecaka"][0]["ok"], kroki(w2))
sprawdz("17f rozbieżność zalogowana", any(k["nazwa"] == "rozbieznosc_ekwipunku" for k in w2["kroki"]), kroki(w2))
sprawdz("17g po procedurze tarcza z powrotem w slocie, bez alarmu i bez rzutu",
        s2.ekw.get(5) == VIK and VIK not in s2.plecak and not w2["alarm"] and s2.klawisze == []
        and w2["wynik"] == "przerwane" and w2["powod"].startswith("ekwipunek_nieaktualny"), (w2, s2.ekw, s2.plecak))
sprawdz("17h bez czekania do limitu", w2["czas_s"] < 15, w2["czas_s"])

# 17i. druga próba z incydentu: tarcza już w plecaku, tablica (nieaktualna) pokazuje ją w slocie; zrzut mówi: slot pusty
s = SwiatEkw(ekw_zamrozony={5: VIK, 6: MIECZ}, ekran=False, plecak=[ZLOTO, VIK, BLANK])
s.ekw = {6: MIECZ}
w = uh.zrob_runa(srod2(s), slot=5)
sprawdz("17i start: zrzut mówi pusto => tarcza_naprawa", s.ekw.get(5) == VIK and w["wynik"] == "naprawiono"
        and s.klawisze == [] and not w["alarm"], (w, s.ekw, s.plecak))
# 17j. to samo bez zrzutu: UH próbuje zdjąć "tarczę", nic się nie dzieje, ratunek zakłada ją z plecaka
s = SwiatEkw(ekw_zamrozony={5: VIK, 6: MIECZ}, plecak=[ZLOTO, VIK, BLANK])
s.ekw = {6: MIECZ}
w = uh.zrob_runa(srod2(s), slot=5)
sprawdz("17j bez zrzutu: ratunek zakłada tarczę, nigdy bez tarczy", s.ekw.get(5) == VIK and not w["alarm"]
        and s.klawisze == [], (w, s.ekw, s.plecak))
sprawdz("17k ratunek w krokach", any(k["nazwa"] == "tarcza_ratunek_ruch" and k["ok"] for k in w["kroki"]), kroki(w))

# 17l. tarcza_naprawa na starcie (po przerwanym UH): slot pusty, tarcza w plecaku, ekwipunek poprawny
s = SwiatEkw(plecak=[ZLOTO, TARCZA, BLANK])
s.ekw = {6: MIECZ}
w = uh.naprawa(srod2(s), slot=5)
sprawdz("17l naprawa zakłada tarczę", w["wynik"] == "naprawiono" and s.ekw.get(5) == TARCZA and TARCZA not in s.plecak
        and s.klawisze == [] and "tarcza_naprawa" in kroki(w), (w, kroki(w)))
s = SwiatEkw()
w = uh.naprawa(srod2(s), slot=5)
sprawdz("17m naprawa: tarcza w slocie => nic", w["wynik"] == "ok" and s.drag_log == [], w)
s = SwiatEkw(ekw_none_n=99)
w = uh.naprawa(srod2(s), slot=5)
sprawdz("17n naprawa przy nieczytelnym ekwipunku: brak_ekwipunku, bez ruchu", w["wynik"] == "brak_ekwipunku" and s.drag_log == [], w)

# 17o. relog w trakcie: po zdjęciu tarczy ekwipunek None przez kilka odczytów, tarcza wraca wg kontenerów
s = SwiatEkw(ekw_none_po_ruchu=14)
w = uh.zrob_runa(srod2(s), slot=5)
sprawdz("17o ekwipunek None po zdjęciu: tarcza wraca, bez alarmu", s.ekw.get(5) == TARCZA and TARCZA not in s.plecak
        and not w["alarm"] and s.klawisze == [], (w, s.ekw, s.plecak, kroki(w)))

# 17p. każde przerwanie po zdjęciu tarczy kończy się tarczą w slocie (przerwania w różnych miejscach)
wszystkie = True
for n in range(0, 6):
    s = SwiatEkw(przerwij_po=n)
    w = uh.zrob_runa(srod2(s), slot=5)
    wszystkie = wszystkie and s.ekw.get(5) == TARCZA and not w["alarm"]
sprawdz("17p przerwanie po n-tym ruchu: zawsze tarcza w slocie", wszystkie)

# 18. 23.10 invincible: blank w ręce (po ręcznym UH), tarcza w plecaku => UH sam się naprawia; brak tarczy => runy bez tarczy
def ekw5(s, v):
    if v is None: s.ekw.pop(5, None)
    else: s.ekw[5] = v
    return s

# 18a. odtworzenie stanu z gniazda: blank w ręce, tarcza w plecaku, drugi blank w plecaku -> runa + tarcza z powrotem
s = ekw5(Swiat(plecak=[ZLOTO, TARCZA, BLANK, ZLOTO]), BLANK)
w = uh.zrob_runa(srod(s), slot=5)
sprawdz("18a blank w ręce, tarcza w plecaku: runa + tarcza wraca", w["wynik"] == "ok" and not w["alarm"]
        and s.ekw.get(5) == TARCZA and UHR in s.plecak and s.klawisze == ["F5"], (w["wynik"], w["powod"], s.ekw, s.plecak, s.klawisze))
sprawdz("18a2 bez zbędnego zdejmowania tarczy", "tarcza_do_plecaka" not in kroki(w), kroki(w))

# 18b. kontrola na starcie (naprawa): blank w ręce, tarcza w plecaku -> blank do plecaka, tarcza do ręki, bez rzutu
s = ekw5(Swiat(plecak=[ZLOTO, TARCZA, ZLOTO]), BLANK)
w = uh.naprawa(srod(s), slot=5)
sprawdz("18b naprawa na starcie: tarcza w ręce, blank w plecaku", w["wynik"] == "naprawiono" and s.ekw.get(5) == TARCZA
        and s.plecak.count(BLANK) == 1 and s.klawisze == [] and not w["alarm"], (w["wynik"], w["powod"], s.ekw, s.plecak))

# 18c. brak tarczy w ogóle, ręka pusta -> runa bez tarczy
s = ekw5(Swiat(), None)
w = uh.zrob_runa(srod(s), slot=5)
sprawdz("18c ręka pusta, brak tarczy: runa bez tarczy", w["wynik"] == "ok" and not w["alarm"] and UHR in s.plecak
        and 5 not in s.ekw and s.klawisze == ["F5"] and s.plecak.count(BLANK) == 1, (w["wynik"], w["powod"], s.ekw, s.plecak, s.klawisze))

# 18d. brak tarczy w ogóle, blank w ręce -> rzut, runa do plecaka, ręka pusta
s = ekw5(Swiat(plecak=[ZLOTO, ZLOTO]), BLANK)
w = uh.zrob_runa(srod(s), slot=5)
sprawdz("18d blank w ręce, brak tarczy: runa bez tarczy", w["wynik"] == "ok" and UHR in s.plecak and 5 not in s.ekw
        and s.klawisze == ["F5"] and not w["alarm"], (w["wynik"], w["powod"], s.ekw, s.plecak))

# 18e. kontrola na starcie bez tarczy w ogóle: nic do naprawy, zero ruchów
s = ekw5(Swiat(), None)
w = uh.naprawa(srod(s), slot=5)
sprawdz("18e naprawa bez tarczy: ok, bez ruchów", w["wynik"] == "ok" and s.drag_log == [], (w["wynik"], s.drag_log))

# 18f. stwór w widoku po pierwszym ruchu (blank w ręce, tarcza w plecaku): tarcza na miejscu, bez rzutu
s = ekw5(Swiat(plecak=[ZLOTO, TARCZA, BLANK, MIECZ, MIECZ], przerwij_po=0), BLANK)  # MIECZ: plecak z samymi runami/monetami byłby brany za pojemnik na runy
w = uh.zrob_runa(srod(s), slot=5)
sprawdz("18f stwór: tarcza w ręce, bez rzutu, bez alarmu", w["wynik"] == "przerwane" and s.ekw.get(5) == TARCZA
        and s.klawisze == [] and not w["alarm"], (w["wynik"], w["powod"], s.ekw, s.plecak, s.klawisze))

# 18g. stwór po pierwszym ruchu bez tarczy: ręka pusta, blank wrócił do plecaka, bez rzutu
s = ekw5(Swiat(plecak=[ZLOTO, BLANK], przerwij_po=1), None)
w = uh.zrob_runa(srod(s), slot=5)
sprawdz("18g bez tarczy + stwór: ręka pusta, blank w plecaku, bez alarmu", w["wynik"] == "przerwane" and 5 not in s.ekw
        and s.plecak.count(BLANK) == 1 and s.klawisze == [] and not w["alarm"], (w["wynik"], w["powod"], s.ekw, s.plecak))

# 18h. nieudany rzut z blankiem w ręce i tarczą w plecaku: blank do plecaka, tarcza do ręki
s = ekw5(Swiat(plecak=[ZLOTO, TARCZA], cast="nic"), BLANK)
w = uh.zrob_runa(srod(s), slot=5)
sprawdz("18h nieudany rzut: stan wyjściowy z tarczą", w["wynik"] == "przerwane" and s.ekw.get(5) == TARCZA
        and s.plecak.count(BLANK) == 1 and not w["alarm"], (w["wynik"], w["powod"], s.ekw, s.plecak))

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
