#!/usr/bin/env python3
"""26.10: rodziny spotów (pole `rodzina` w dane_tibia/spoty_nadzorca.json) i mapy brakujących pięter (generuj_rodziny_pietra.py).
Offline, tylko odczyt: tabela spotów, mapy.json, trasy/, mapa klienta. Nic nie trafia do gry.

Co sprawdza:
  * każdy spot ma `rodzina`; rodzina należy do jednego miasta, jaskinia do jednej rodziny; skład rodzin = migawka (zmiana składu = świadoma zmiana testu);
  * każda mapa z mapy.json ma wpis w tabeli, istniejącą trasę i (poza listą map bez dojścia) istniejące dojście; spot z `auto: true` ma dojście;
  * 5 nowych map pięter (trolle_edron_z10w, gobliny_edron_z10_{zachod,wschod,poludnie}, rook_raty_z10_zachod): pliki, geometria (pętla w jednym piętrze, krok
    <= 1 pole, dojście = trasa bazowa + przejścia pięter, koniec dojścia = start pętli), przejścia z mapy (kolor 210, nie PRZESZKODA), progi (>= 10 potworów
    celu, pętla >= 60 pól), brak pól ognia (bufor 1) w pętli i w NOWYCH odcinkach dojścia, brak groźnych potworów przy pętli, przystanki ze spawnów leżą na pętli;
  * decyzje o pominiętych kandydatach (doczepka z10 (33107,31737) < progu) są liczone z mapy, a nie wpisane z ręki;
  * zbiór `auto: false` nowych map zostaje, dopóki wyprawa.PLANY_PK nie ma planu powrotu z tych pięter (flip = świadoma zmiana testu);
  * integracja z spoty.py: ta_sama_rodzina i wybierz(rodzina_z=...) zwracają kandydatów z rodziny.
Uruchomienie: python3 -I testy/test_rodziny.py"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
KORZEN = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(KORZEN))
import spoty as SP  # noqa: E402

TAB = SP.wczytaj()
DANE = json.loads((KORZEN / "dane_tibia" / "spoty_nadzorca.json").read_text(encoding="utf-8"))
SPOTY = DANE["spoty"]
MAPY = {k: v for k, v in json.loads((KORZEN / "mapy.json").read_text(encoding="utf-8")).items() if not k.startswith("_") and isinstance(v, dict)}

NOWE = ("trolle_edron_z10w", "gobliny_edron_z10_zachod", "gobliny_edron_z10_wschod", "gobliny_edron_z10_poludnie", "rook_raty_z10_zachod")
BEZ_DOJSCIA = {"rook", "wilki", "stoj_trade", "stoj_runy_thais", "stoj_uh_edron_horn", "rook_bugi_z8", "rook_raty_z8_kieszen"}
SKLAD = {       # migawka 26.10 (46 spotów, bez wariantów-łączników); nowy spot w rodzinie = dopisać tu świadomie
    "edron_trolle": {"trolle_edron", "trolle_edron_patrol", "trolle_edron_z9w", "trolle_edron_z9z", "trolle_edron_z10w"},
    "edron_gobliny": {"gobliny_edron", "gobliny_edron_z9", "gobliny_edron_z10_zachod", "gobliny_edron_z10_wschod", "gobliny_edron_z10_poludnie"},
    "edron_trade": {"stoj_trade"}, "edron_horn": {"stoj_uh_edron_horn"},
    "thais_raty": {"raty"}, "thais_trolle_wschod": {"trolle", "trolle_pelny", "trolle_nowe", "trolle_patrol"},
    "thais_pn_trolle": {"thais_pn_z8", "thais_pn_z9"}, "thais_wilki": {"wilki"}, "thais_stoj_runy": {"stoj_runy_thais"},
    "kazordoon_trolle": {"trolle_kazordoon_z7", "trolle_kazordoon_z8", "trolle_kazordoon_z9"},
    "rook_kanaly": {"rook", "rook_kanaly_z11"},
    "rook_raty": {"rook_raty_z8", "rook_raty_z8_do_smierci", "rook_raty_z9", "rook_raty_z9_do_smierci", "rook_raty_z10", "rook_cave_raty_z9_glab",
                  "rook_raty_z8_kieszen", "rook_raty_z9_z_kieszeni", "rook_raty_z10_zachod"},
    "rook_bugi": {"rook_bugi_z8", "rook_bugi_z10"}, "port_hope_raty": {"ph_raty_z8"},
    "abdendriel_trolle": {"abdendriel_trolle_z9", "abdendriel_trolle_z10", "abdendriel_trolle_z11", "abdendriel_trolle_z12", "abdendriel_trolle_z10_z9",
                          "abdendriel_trolle_z11_z9", "abdendriel_trolle_z12_z9"},
    "abdendriel_gobliny": {"abdendriel_gobliny"},
}


def edron(poziom, **kw):
    return {"id": kw.pop("id", "x"), "poz": kw.pop("poz", (33191, 31818, 7)), "poziom": poziom, "ekwipunek": kw.pop("ekwipunek", {"lina": True, "lopata": True}), **kw}


# ---------------------------------------------------------------- pole `rodzina`
def test_kazdy_spot_ma_rodzine():
    zle = [n for n, s in SPOTY.items() if not (isinstance(s.get("rodzina"), str) and s["rodzina"] and s["rodzina"] == s["rodzina"].lower()
                                              and s["rodzina"].replace("_", "").isalnum())]
    assert not zle, f"spoty bez poprawnej rodziny: {zle}"
    assert set(SPOTY) == set(MAPY), set(SPOTY) ^ set(MAPY)
    assert all(TAB.spoty[n].rodzina == s["rodzina"] for n, s in SPOTY.items()), "spoty.wczytaj nie widzi pola rodzina"


def test_rodzina_jedno_miasto_jaskinia_jedna_rodzina():
    miasta, jask = {}, {}
    for n, s in SPOTY.items():
        miasta.setdefault(s["rodzina"], set()).add(s["miasto"])
        if s.get("jaskinia"):
            jask.setdefault(s["jaskinia"], set()).add(s["rodzina"])
    assert all(len(v) == 1 for v in miasta.values()), {k: v for k, v in miasta.items() if len(v) > 1}
    assert all(len(v) == 1 for v in jask.values()), {k: v for k, v in jask.items() if len(v) > 1}


def test_sklad_rodzin_to_migawka():
    rzecz = {}
    for n, s in SPOTY.items():
        if s.get("baza"):
            continue                # warianty-łączniki mają własny test (test_warianty_*)
        rzecz.setdefault(s["rodzina"], set()).add(n)
    assert rzecz == SKLAD, {k: (rzecz.get(k), SKLAD.get(k)) for k in set(rzecz) | set(SKLAD) if rzecz.get(k) != SKLAD.get(k)}


def test_kazordoon_z9_i_z8_zostaja_wylaczone():
    for n in ("trolle_kazordoon_z7", "trolle_kazordoon_z8", "trolle_kazordoon_z9"):
        assert SPOTY[n]["auto"] is False, f"{n}: Karol 24.10 (z9 bardzo niebezpieczne) i 24.10 (z8 zajęty): auto false"


# ---------------------------------------------------------------- mapy: dojście i trasa istnieją
def test_kazda_mapa_ma_trase_i_dojscie():
    bez = set()
    for n, m in MAPY.items():
        assert SP.punkty_trasy(KORZEN, SP.rozwiaz_trase(KORZEN, m["trasa"])), f"{n}: brak pliku trasy {m['trasa']}"
        if m.get("dojscie"):
            assert SP.punkty_trasy(KORZEN, m["dojscie"]), f"{n}: brak pliku dojścia {m['dojscie']}"
        else:
            bez.add(n)
    assert bez == BEZ_DOJSCIA, bez ^ BEZ_DOJSCIA
    zle = [n for n, s in SPOTY.items() if s["auto"] and not MAPY[n].get("dojscie")]
    assert not zle, f"spot z auto true bez dojścia: {zle}"


def test_tabela_spojna_z_trasami():
    assert SP.sprawdz(TAB) == [], SP.sprawdz(TAB)


# ---------------------------------------------------------------- nowe mapy pięter
try:
    import mapa as _mapa  # noqa: E402
    import generuj_rodziny_pietra as G  # noqa: E402
    import spot_lib  # noqa: E402
    import waliduj_trase  # noqa: E402
    MAPA_JEST = _mapa.PLIK_MAPY.is_file()
except ImportError:
    MAPA_JEST = False
M = _mapa.Mapa() if MAPA_JEST else None
OGIEN = G.ogien_pola() if MAPA_JEST else set()


def _spec(n):
    return G.SPECY[n]


def test_nowe_mapy_wpisy():
    for n in NOWE:
        assert n in MAPY and n in SPOTY, n
        s, m = SPOTY[n], MAPY[n]
        assert s["auto"] is False and "PLANY_PK" in s["powod"] and "niezweryfikowany" in s["powod"], f"{n}: auto false do planu powrotu (flip = zmiana testu)"
        assert s["poziom_zrodlo"] == "domyslne", n
        assert "NIEZWERYFIKOWANY" in m["opis"] and "PLANY_PK" in m["opis"], n
        assert m["trasa"] == _spec(n)["plik"] + "_petla" and m["dojscie"] == _spec(n)["plik"] + "_dojscie", n
        assert bool(m.get("dojscie_z_dowolnego_pietra")) == (SPOTY[n]["miasto"] == "edron"), f"{n}: z dowolnego piętra tylko Edron (baza z depo Edron)"
    assert SPOTY["trolle_edron_z10w"]["rodzina"] == "edron_trolle" and SPOTY["rook_raty_z10_zachod"]["rodzina"] == "rook_raty"
    assert all(SPOTY[n]["rodzina"] == "edron_gobliny" for n in NOWE if n.startswith("gobliny"))


def test_nowe_mapy_geometria():
    if not MAPA_JEST:
        return
    for n in NOWE:
        sp = _spec(n)
        petla = SP.punkty_trasy(KORZEN, sp["plik"] + "_petla")
        doj = SP.punkty_trasy(KORZEN, sp["plik"] + "_dojscie")
        baza = SP.punkty_trasy(KORZEN, sp["baza"])
        assert {p[2] for p in petla} == {sp["z"]}, f"{n}: pętla w jednym piętrze z{sp['z']}"
        assert all(max(abs(a[0] - b[0]), abs(a[1] - b[1])) <= 1 for a, b in zip(petla, petla[1:])), f"{n}: krok pętli > 1 pole"
        assert petla[0] == petla[-1], f"{n}: pętla zamknięta"
        assert len(petla) >= G.PROG_PETLA, (n, len(petla))
        assert doj[:len(baza)] == baza, f"{n}: dojście zaczyna się od trasy bazowej {sp['baza']}"
        assert doj[-1][2] == sp["z"] and doj[-1][:2] == petla[0][:2], f"{n}: dojście kończy się na starcie pętli: {doj[-1]} vs {petla[0]}"
        nowe = doj[len(baza) - 1:]
        zm = [(a, b) for a, b in zip(nowe, nowe[1:]) if a[2] != b[2]]
        assert len(zm) == len(sp["hops"]), f"{n}: przejść pięter w nowym odcinku {len(zm)}, w specyfikacji {len(sp['hops'])}"
        for (a, b), (T, _seed) in zip(zm, sp["hops"]):
            assert a == T and b[2] == T[2] + 1, f"{n}: przejście {a}->{b}, oczekiwane z {T}"
            assert m_flag_przejscie(T), f"{n}: {T} nie jest przejściem 210 / jest PRZESZKODĄ"
        assert all(M.przechodnie(*p) is not False for p in petla), f"{n}: punkt pętli na ścianie"
        meta = json.loads((KORZEN / "trasy" / f"{sp['plik']}_dojscie.meta").read_text())["specjalne"]
        przed = {e["idx"] for e in meta if e["typ"] == "przed_zmiana_pietra"}
        for (T, _seed) in sp["hops"]:
            assert doj.index(T, len(baza) - 1) in przed, f"{n}: brak wpisu meta przed_zmiana_pietra dla {T}"


def m_flag_przejscie(T):
    f = M.flagi(*T)
    return bool(f & _mapa.WIDZIANE and f & _mapa.BEZ_DROGI and M.pole(*T)[1] == 210 and not spot_lib.przeszkoda_na_podlodze(M, *T))


def test_nowe_mapy_bez_ognia_i_grozni():
    if not MAPA_JEST:
        return
    for n in NOWE:
        sp = _spec(n)
        petla = SP.punkty_trasy(KORZEN, sp["plik"] + "_petla")
        doj = SP.punkty_trasy(KORZEN, sp["plik"] + "_dojscie")
        baza = SP.punkty_trasy(KORZEN, sp["baza"])
        assert not [p for p in petla if p in OGIEN], f"{n}: pętla w ogniu/buforze: {[p for p in petla if p in OGIEN][:3]}"
        nowe = doj[len(baza) - 1:]
        assert not [p for p in nowe if p in OGIEN], f"{n}: nowy odcinek dojścia w ogniu/buforze: {[p for p in nowe if p in OGIEN][:3]}"
        assert G.groznicy(sp["z"], [(p[0], p[1]) for p in petla]) == [], f"{n}: groźny potwór przy pętli"


def test_nowe_mapy_waliduj_trase():
    if not MAPA_JEST:
        return
    for n in NOWE:
        sp = _spec(n)
        petla = SP.punkty_trasy(KORZEN, sp["plik"] + "_petla")
        assert not [w for w in waliduj_trase.waliduj(petla, M) if w[0] == "BLAD"], n
        doj = SP.punkty_trasy(KORZEN, sp["plik"] + "_dojscie")
        baza = SP.punkty_trasy(KORZEN, sp["baza"])
        bl_baza = {w[2] for w in waliduj_trase.waliduj(baza, M) if w[0] == "BLAD"}       # błąd odziedziczony z nagrania (edron_depo_trolle #15) jest w bazie, nie w nowym
        bl = {w[2] for w in waliduj_trase.waliduj(doj, M) if w[0] == "BLAD"}
        assert bl == bl_baza, f"{n}: nowe błędy dojścia {bl - bl_baza}"


def test_progi_i_przystanki():
    if not MAPA_JEST:
        return
    for n in NOWE:
        sp = _spec(n)
        d = json.loads((KORZEN / "dane_tibia" / "mapy" / f"{sp['plik']}.json").read_text())
        petla = {(p[0], p[1]) for p in SP.punkty_trasy(KORZEN, sp["plik"] + "_petla")}
        cel = sum(p.get("potworow", 0) for p in d["przystanki"])
        assert cel >= G.PROG_CEL, f"{n}: potworów celu {cel} < {G.PROG_CEL}"
        assert d["dlugosc_petli"] >= G.PROG_PETLA, n
        assert all((p["x"], p["y"]) in petla for p in d["przystanki"]), f"{n}: przystanek poza pętlą"
        assert (d["start"][0], d["start"][1]) in petla and d["start"][2] == sp["z"], n


def test_generator_buduje_te_same_liczby():
    """Generator liczy dziś z mapy i ognia to samo, co leży w plikach (kształt: długości, lądowanie). Czerwone = ogień/dziury zmieniły drogę: wygeneruj ponownie."""
    if not MAPA_JEST:
        return
    for n in NOWE:
        w = G.zbuduj(n, _spec(n), M)
        petla = SP.punkty_trasy(KORZEN, _spec(n)["plik"] + "_petla")
        doj = SP.punkty_trasy(KORZEN, _spec(n)["plik"] + "_dojscie")
        assert [(p[0], p[1], w["z"]) for p in w["pelna"]] == petla, f"{n}: pętla z generatora != plik (regeneruj: python3 -I generuj_rodziny_pietra.py --zapisz {n})"
        assert [tuple(p) for p in w["doj"]] == doj, f"{n}: dojście z generatora != plik"


def test_pominiete_kandydaty_to_doczepki_z_liczb():
    """Edron z10 (33107,31737): osobna składowa 133 pola pod z9 zachód (przejście (33099,31740,z9)), 7 trolli + 4 szczury: troll < PROG_CEL -> doczepka."""
    if not MAPA_JEST:
        return
    comp = spot_lib.skladowa(M, (33107, 31737, 10), [])
    assert 100 < len(comp) < 200, len(comp)
    stops = spot_lib.przystanki(spot_lib.spawny(10, G.TROLLE), comp)
    cel = sum(t["n"] for t in stops)
    assert cel < G.PROG_CEL, f"cel {cel}: jeśli >= {G.PROG_CEL}, to jest pełnoprawny spot (zaktualizuj decyzję)"
    assert not any(k for k, m in MAPY.items() if "(33107,31737" in m.get("opis", "")), "doczepka nie ma własnej mapy"


def test_info_petle_istniejacych_map_w_ogniu():
    """INFORMACJA, nie asercja: pętle ISTNIEJĄCYCH map z polami ognia (ogien_stale + ogien_epizody z n >= 2), bez bufora. Nowe mapy mają 0 (test wyżej);
    stare pętle (nagrania, starsze generatory) powstały przed większością epizodów. Lista do przeglądu Karola/lead, nie blokuje."""
    if not MAPA_JEST:
        return
    stale = {tuple(p[:3]) for p in json.loads((KORZEN / "trasy" / "ogien_stale.json").read_text()).get("pola", [])}
    ep = json.loads((KORZEN / "trasy" / "ogien_epizody.json").read_text()).get("pola", {})
    silny = stale | {tuple(int(a) for a in k.split(",")) for k, v in ep.items() if isinstance(v, dict) and v.get("n", 0) >= 2}
    wiersze = []
    for n, m in sorted(MAPY.items()):
        if n in NOWE:
            continue
        pts = SP.punkty_trasy(KORZEN, SP.rozwiaz_trase(KORZEN, m["trasa"])) or []
        w = sum(1 for p in pts if p in silny)
        if w:
            wiersze.append(f"{n} ({'auto' if SPOTY[n]['auto'] else 'off'}): {w}/{len(pts)}")
    print("   INFO pętle istniejących map z polami ognia (n >= 2 albo stałe): " + ("; ".join(wiersze) or "brak"))


# ---------------------------------------------------------------- integracja z spoty.py (wybór w rodzinie)
def test_ta_sama_rodzina():
    if not hasattr(SP, "ta_sama_rodzina"):
        return
    a, b, c = TAB.spoty["trolle_edron_z9w"], TAB.spoty["trolle_edron_z10w"], TAB.spoty["thais_pn_z8"]
    assert SP.ta_sama_rodzina(a, b) and SP.ta_sama_rodzina(TAB.spoty["trolle_edron"], b)
    assert not SP.ta_sama_rodzina(a, c) and not SP.ta_sama_rodzina(a, TAB.spoty["gobliny_edron_z10_zachod"])
    assert SP.ta_sama_rodzina(TAB.spoty["rook_raty_z10"], TAB.spoty["rook_raty_z10_zachod"])


def test_wybierz_w_rodzinie_nie_bierze_wylaczonych():
    try:
        r = SP.wybierz(edron(12), tabela=TAB, ziarno="rodz", rodzina_z="trolle_edron_z9w")
    except TypeError:
        return                      # wybierz bez rodzina_z (starsza wersja spoty.py)
    assert r["mapa"] in SKLAD["edron_trolle"], r
    assert ("trolle_edron_z10w", "auto") in {(o[0], o[1]) for o in r["odrzucone"]}, r["odrzucone"]
    assert r["mapa"] != "trolle_edron_z10w", "auto false: nowa mapa nie jest wybierana, dopóki nie ma planu powrotu"


# ---------------------------------------------------------------- dojście z dowolnego piętra jaskini (26.10 ~12:00, Karol: zmiana spotu bez wyjścia na z7)
WARIANTY = (
    "gobliny_edron__z__gobliny_edron_z10_poludnie",
    "gobliny_edron__z__gobliny_edron_z10_wschod",
    "gobliny_edron__z__gobliny_edron_z10_zachod",
    "gobliny_edron__z__gobliny_edron_z9",
    "gobliny_edron_z10_poludnie__z__gobliny_edron",
    "gobliny_edron_z10_poludnie__z__gobliny_edron_z10_wschod",
    "gobliny_edron_z10_poludnie__z__gobliny_edron_z10_zachod",
    "gobliny_edron_z10_wschod__z__gobliny_edron",
    "gobliny_edron_z10_wschod__z__gobliny_edron_z10_poludnie",
    "gobliny_edron_z10_wschod__z__gobliny_edron_z10_zachod",
    "gobliny_edron_z10_zachod__z__gobliny_edron",
    "gobliny_edron_z10_zachod__z__gobliny_edron_z10_poludnie",
    "gobliny_edron_z10_zachod__z__gobliny_edron_z10_wschod",
    "gobliny_edron_z9__z__gobliny_edron",
    "gobliny_edron_z9__z__gobliny_edron_z10_poludnie",
    "gobliny_edron_z9__z__gobliny_edron_z10_wschod",
    "gobliny_edron_z9__z__gobliny_edron_z10_zachod",
    "trolle_edron__z__trolle_edron_z10w",
    "trolle_edron__z__trolle_edron_z9w",
    "trolle_edron__z__trolle_edron_z9z",
    "trolle_edron_patrol__z__trolle_edron_z10w",
    "trolle_edron_patrol__z__trolle_edron_z9w",
    "trolle_edron_patrol__z__trolle_edron_z9z",
    "trolle_edron_z10w__z__trolle_edron_z9z",
    "trolle_edron_z9w__z__trolle_edron_z10w",
    "trolle_edron_z9w__z__trolle_edron_z9z",
    "trolle_edron_z9z__z__trolle_edron_z10w",
    "trolle_edron_z9z__z__trolle_edron_z9w",
)
# pary (pętla źródłowa -> mapa docelowa) rodziny, dla których NIE ma dojścia z całej pętli źródła ani zwykłego, ani przez wariant-łącznik; powód JAWNIE:
WYJATKI = {
    "abdendriel_trolle": {
        ("abdendriel_trolle_z10", "abdendriel_trolle_z11"),
        ("abdendriel_trolle_z10", "abdendriel_trolle_z11_z9"),
        ("abdendriel_trolle_z10", "abdendriel_trolle_z12"),
        ("abdendriel_trolle_z10", "abdendriel_trolle_z12_z9"),
        ("abdendriel_trolle_z10", "abdendriel_trolle_z9"),
        ("abdendriel_trolle_z11", "abdendriel_trolle_z10"),
        ("abdendriel_trolle_z11", "abdendriel_trolle_z10_z9"),
        ("abdendriel_trolle_z11", "abdendriel_trolle_z12"),
        ("abdendriel_trolle_z11", "abdendriel_trolle_z12_z9"),
        ("abdendriel_trolle_z11", "abdendriel_trolle_z9"),
        ("abdendriel_trolle_z12", "abdendriel_trolle_z10"),
        ("abdendriel_trolle_z12", "abdendriel_trolle_z10_z9"),
        ("abdendriel_trolle_z12", "abdendriel_trolle_z11"),
        ("abdendriel_trolle_z12", "abdendriel_trolle_z11_z9"),
        ("abdendriel_trolle_z12", "abdendriel_trolle_z9"),
        ("abdendriel_trolle_z9", "abdendriel_trolle_z10"),
        ("abdendriel_trolle_z9", "abdendriel_trolle_z11"),
        ("abdendriel_trolle_z9", "abdendriel_trolle_z12"),
    },
    "kazordoon_trolle": {
        ("trolle_kazordoon_z8", "trolle_kazordoon_z7"),
        ("trolle_kazordoon_z8", "trolle_kazordoon_z9"),
        ("trolle_kazordoon_z9", "trolle_kazordoon_z7"),
        ("trolle_kazordoon_z9", "trolle_kazordoon_z8"),
    },
    "rook_bugi": {
        ("rook_bugi_z8", "rook_bugi_z10"),
    },
    "rook_raty": {
        ("rook_cave_raty_z9_glab", "rook_raty_z10"),
        ("rook_cave_raty_z9_glab", "rook_raty_z10_zachod"),
        ("rook_cave_raty_z9_glab", "rook_raty_z8"),
        ("rook_cave_raty_z9_glab", "rook_raty_z8_do_smierci"),
        ("rook_cave_raty_z9_glab", "rook_raty_z9"),
        ("rook_cave_raty_z9_glab", "rook_raty_z9_do_smierci"),
        ("rook_cave_raty_z9_glab", "rook_raty_z9_z_kieszeni"),
        ("rook_raty_z10", "rook_cave_raty_z9_glab"),
        ("rook_raty_z10", "rook_raty_z10_zachod"),
        ("rook_raty_z10", "rook_raty_z8"),
        ("rook_raty_z10", "rook_raty_z8_do_smierci"),
        ("rook_raty_z10", "rook_raty_z9"),
        ("rook_raty_z10", "rook_raty_z9_do_smierci"),
        ("rook_raty_z10", "rook_raty_z9_z_kieszeni"),
        ("rook_raty_z10_zachod", "rook_cave_raty_z9_glab"),
        ("rook_raty_z10_zachod", "rook_raty_z10"),
        ("rook_raty_z10_zachod", "rook_raty_z8"),
        ("rook_raty_z10_zachod", "rook_raty_z8_do_smierci"),
        ("rook_raty_z10_zachod", "rook_raty_z9"),
        ("rook_raty_z10_zachod", "rook_raty_z9_do_smierci"),
        ("rook_raty_z10_zachod", "rook_raty_z9_z_kieszeni"),
        ("rook_raty_z8", "rook_cave_raty_z9_glab"),
        ("rook_raty_z8", "rook_raty_z10"),
        ("rook_raty_z8", "rook_raty_z10_zachod"),
        ("rook_raty_z8", "rook_raty_z9"),
        ("rook_raty_z8", "rook_raty_z9_do_smierci"),
        ("rook_raty_z8", "rook_raty_z9_z_kieszeni"),
        ("rook_raty_z8_kieszen", "rook_cave_raty_z9_glab"),
        ("rook_raty_z8_kieszen", "rook_raty_z10"),
        ("rook_raty_z8_kieszen", "rook_raty_z10_zachod"),
        ("rook_raty_z8_kieszen", "rook_raty_z8"),
        ("rook_raty_z8_kieszen", "rook_raty_z8_do_smierci"),
        ("rook_raty_z8_kieszen", "rook_raty_z9"),
        ("rook_raty_z8_kieszen", "rook_raty_z9_do_smierci"),
        ("rook_raty_z9", "rook_raty_z8"),
        ("rook_raty_z9", "rook_raty_z8_do_smierci"),
    },
    "thais_pn_trolle": {
        ("thais_pn_z8", "thais_pn_z9"),
        ("thais_pn_z9", "thais_pn_z8"),
    },
    "thais_trolle_wschod": {
        ("trolle", "trolle_nowe"),
        ("trolle_nowe", "trolle"),
        ("trolle_nowe", "trolle_patrol"),
        ("trolle_nowe", "trolle_pelny"),
        ("trolle_pelny", "trolle_nowe"),
    },
}
POWOD_WYJATKU = {
    "abdendriel_trolle": "wszystkie mapy auto false (nadzorca ich nie wybiera); planer łączników (rodziny_dojscie.zbuduj_lacznik) daje dla z10/z11 trasy po 1400 punktów i nie przechodzi weryfikacji",
    "kazordoon_trolle": "z9 pod Kazordoonem NIEDOZWOLONE (Karol 24.10), wszystkie auto false; z8 -> z7 to wyjście na powierzchnię",
    "rook_bugi": "jaskinia bugów Rooka bez liny w typowym ekwipunku, rook_bugi_z8 auto false",
    "rook_raty": "Rookgaard: bez lin, kierunki schodów nieznane z mapy (schody nie są dziurami), łączników nie generujemy; część spotów auto false",
    "thais_pn_trolle": "korytarz Poison Spiderów (thais_pn z9 -> z8) i schody; łącznik wymagałby tras po polach spoza nagrań",
    "thais_trolle_wschod": "schody (nie dziury/liny): planer ich nie obsługuje; luki tylko w kieszeniach pętli oddalonych >60 pól drogi od dojścia",
}
FAMILY_Z_PLANEREM = ("edron_trolle", "edron_gobliny")


def test_warianty_to_migawka():
    rzecz = tuple(sorted(n for n, s in SPOTY.items() if s.get("baza")))
    assert rzecz == tuple(sorted(WARIANTY)), set(rzecz) ^ set(WARIANTY)
    assert all(SEP in n for n in rzecz) and all(SEP not in n for n in SPOTY if n not in rzecz)


SEP = "__z__"


def test_warianty_spojne_z_baza():
    for n in WARIANTY:
        w, b = SPOTY[n], SPOTY[SPOTY[n]["baza"]]
        assert not b.get("baza") and n.startswith(w["baza"] + SEP), n
        for k in ("miasto", "jaskinia", "rodzina", "poziom"):
            assert w[k] == b[k], (n, k)
        assert w["waga"] == b["waga"] and w["auto"] is False, (n, "waga jak baza; auto false w pliku = zabezpieczenie dla starego kodu spoty.py bez obsługi `baza` w żywym procesie")
        m, mb = MAPY[n], MAPY[w["baza"]]
        assert m["trasa"] == mb["trasa"] and m["potwory"] == mb["potwory"] and m.get("prog_hp") == mb.get("prog_hp"), n
        assert m.get("dojscie_z_dowolnego_pietra") is True and m["dojscie"] != mb["dojscie"], n
        assert m["dojscie"].startswith(w["rodzina"] + "_lacznik_"), n
        s = TAB.spoty[n]
        assert s.baza == w["baza"] and s.auto == TAB.spoty[w["baza"]].auto and s.powod == TAB.spoty[w["baza"]].powod, n
        pts = SP.punkty_trasy(KORZEN, m["dojscie"])
        assert pts and all(max(abs(a[0] - b2[0]), abs(a[1] - b2[1])) <= 1 for a, b2 in zip(pts, pts[1:]) if a[2] == b2[2]), f"{n}: skok > 1 pole"
        assert all(abs(a[2] - b2[2]) == 1 and max(abs(a[0] - b2[0]), abs(a[1] - b2[1])) <= 2 for a, b2 in zip(pts, pts[1:]) if a[2] != b2[2]), f"{n}: zła zmiana piętra"   # lina: stanie obok pola liny, lądowanie pole niżej w osi y (<= 2 pola)
        w_gore = any(b2[2] < a[2] for a, b2 in zip(pts, pts[1:]))
        assert ("lina" in (w.get("wymaga_dodatkowo") or [])) == w_gore, f"{n}: wymaga_dodatkowo lina <=> łącznik idzie w górę"
        assert not any(q[2] == SP.LEKKIE_Z for q in pts), f"{n}: łącznik prowadzi przez z7"
        koniec_bazy = tuple(SP.punkty_trasy(KORZEN, mb["dojscie"])[-1])
        petla_bazy = {tuple(q) for q in SP.punkty_trasy(KORZEN, SP.rozwiaz_trase(KORZEN, mb["trasa"]))}
        assert tuple(pts[-1]) == koniec_bazy or tuple(pts[-1]) in petla_bazy, f"{n}: łącznik kończy się poza końcem dojścia bazy i poza jej pętlą"


def test_flagi_dojscia_z_dowolnego_pietra_rodzin_z_dziurami():
    """Odchyd gra w Edronie (edron_trolle) z SPOT_ZMIANA_PRZY_GRACZU=1: WSZYSTKIE mapy obu rodzin edronowych i każdy wariant mają flagę (uruchom.sh nie pomija dojścia)."""
    for n, s in SPOTY.items():
        if s["rodzina"] in FAMILY_Z_PLANEREM:
            assert MAPY[n].get("dojscie_z_dowolnego_pietra") is True, f"{n}: brak flagi dojscie_z_dowolnego_pietra"
    assert {n for n in MAPY if MAPY[n].get("dojscie_z_dowolnego_pietra")} >= set(WARIANTY)


def test_tryb_nie_pomija_dojscia_wariantu():
    import subprocess
    import tempfile
    for n in (WARIANTY[0], "trolle_edron_z9w__z__trolle_edron_z9z", "trolle_edron_patrol__z__trolle_edron_z9z"):
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run([sys.executable, "-I", str(KORZEN / "tryb.py"), "--mapa", n, "--sucho", "--na-zywo", tmp + "/nz.json", "--log", tmp + "/t.log"],
                               capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, (n, r.stderr[-300:])
        assert "MAPA_DOJSCIE_WSZEDZIE=1" in r.stdout and f"MAPA_DOJSCIE={MAPY[n]['dojscie']}" in r.stdout, (n, r.stdout[:400])


def test_stale_dojscia_zgodne_z_mozg():
    import mozg
    assert SP.DOJSCIE_START_DROGA == mozg.DOJSCIE_START_DROGA and SP.DOJSCIE_POMIN_ODL == mozg.DOJSCIE_POMIN_ODL


def test_start_dojscia_to_decyzja_mozg():
    """spoty.start_dojscia = mozg._start_po_mapie na uproszczonym dojściu (ta sama logika, nie jej kopia z innym wynikiem)."""
    import mozg
    import trasa_io
    from itertools import islice
    mp = _mapa.mapa()
    n = 0
    for nz in ("trolle_edron_z9w", "trolle_edron_z9z", "trolle_edron", "gobliny_edron_z9"):
        p = trasa_io.uprosc_petle(SP.punkty_trasy(KORZEN, MAPY[nz]["dojscie"]))
        for zr in ("trolle_edron_z9z", "trolle_edron_z9w", "trolle_edron_z10w", "trolle_edron", "gobliny_edron_z10_wschod", "gobliny_edron_z9"):
            pet = SP.punkty_trasy(KORZEN, MAPY[zr]["trasa"])
            for poz in islice(pet, 0, None, max(1, len(pet) // 4)):
                if poz[2] == SP.LEKKIE_Z:
                    continue
                assert SP.start_dojscia(p, poz, mp) == mozg._start_po_mapie(p, poz), (nz, zr, poz)
                n += 1
    assert n >= 20, n


def test_kazda_para_rodziny_ma_dojscie_albo_jawny_wyjatek():
    """Dla każdej rodziny: z próbek KAŻDEJ pętli źródłowej do każdej innej mapy rodziny z dojściem działa dojście celu albo któryś z jego wariantów-łączników
    (spoty.dojscie_dziala_z). Pary bez dojścia = WYJATKI z powodem; zbiór dokładny (naprawa luki lub nowa luka = świadoma zmiana testu)."""
    import rodziny_dojscie as RD
    mp = _mapa.mapa()
    rzecz = {}
    for fam in sorted({s["rodzina"] for s in SPOTY.values()}):
        for A, B, _ in RD.luki(TAB, fam, mp):
            rzecz.setdefault(fam, set()).add((A, B))
    assert rzecz == WYJATKI, {f: (rzecz.get(f, set()) ^ WYJATKI.get(f, set())) for f in set(rzecz) | set(WYJATKI) if rzecz.get(f) != WYJATKI.get(f)}
    assert set(WYJATKI) == set(POWOD_WYJATKU) and all(len(v) > 30 for v in POWOD_WYJATKU.values())
    for fam in FAMILY_Z_PLANEREM:
        assert fam not in rzecz, f"{fam}: planer łączników miał pokryć wszystkie pary"


def test_lacznik_dziala_z_calej_petli_zrodla():
    """Weryfikacja łączników z mapy klienta (co 12. punkt pętli źródła): dojście = łącznik zadziała jak w mozg, bez z7; wynik jak generator."""
    import rodziny_dojscie as RD
    mp = _mapa.mapa()
    for n in WARIANTY:
        w = SPOTY[n]
        A = MAPY[n]["dojscie"].split("_lacznik_", 1)[1][:-len(w["baza"]) - 1]
        zr = RD.zrodla_rodziny(TAB, w["rodzina"])
        assert A in zr, (n, A)
        pet = zr[A][0]
        for poz in pet[::12] + [pet[-1]]:
            if poz[2] == SP.LEKKIE_Z:
                continue
            ok, powod = SP.dojscie_dziala_z(TAB.spoty[n], poz, mp)
            assert ok is True, (n, poz, powod)


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
                print("BŁĄD", nazwa, repr(e)[:600])
                traceback.print_exc()
    print(f"{ok}/{ok + zle} testów zielonych")
    sys.exit(1 if zle else 0)
