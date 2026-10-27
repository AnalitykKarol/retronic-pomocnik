#!/usr/bin/env python3
"""26.10 (Karol: „stworzyć wszystkie możliwe mapy tej samej jaskini na różnych piętrach”): wpisy RODZIN spotów.
Dopisuje do mapy.json (tylko NOWE mapy pięter) i dane_tibia/spoty_nadzorca.json (pole `rodzina` wszystkich spotów, nowe wpisy, prostokąt miasta
`abdendriel`). Każdy zapis: odczyt pliku tuż przed zmianą, zmieniane TYLKO klucze z tego pliku, zapis atomowy (tmp + os.replace), format jak
dotychczas (indent 1, bez końcowego newline). Idempotentny: drugi przebieg nic nie zmienia.

  python3 -I narzedzia_jednorazowe/rodziny_wpisy_1026.py            pokazuje, co by zmienił (nic nie zapisuje)
  python3 -I narzedzia_jednorazowe/rodziny_wpisy_1026.py --zapisz   zapisuje (kopie *.bak-20261026-rodziny robi się ręcznie PRZED pierwszym zapisem)

Cofnięcie: przywrócić kopie `mapy.json.bak-20261026-rodziny` i `dane_tibia/spoty_nadzorca.json.bak-20261026-rodziny` (jeśli inna sesja zmieniała
te pliki po 26.10 ~08:00, usunąć tylko klucze z tego skryptu: `rodzina`, nowe wpisy i miasto `abdendriel`).
"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
MAPY = ROOT / "mapy.json"
TABELA = ROOT / "dane_tibia" / "spoty_nadzorca.json"

# ---- rodziny: jedna jaskinia (ten sam rejon x,y na kolejnych piętrach, połączona dziurami/schodami/linami) albo jeden rodzaj spotu ----
RODZINY = {
    # Edron: troll cave (z8, z9 wschód, z9 zachód, z10 wschód) i jaskinia goblinów (z8, z9, trzy kieszenie z10)
    "trolle_edron": "edron_trolle", "trolle_edron_patrol": "edron_trolle", "trolle_edron_z9w": "edron_trolle",
    "trolle_edron_z9z": "edron_trolle", "trolle_edron_z10w": "edron_trolle",
    "gobliny_edron": "edron_gobliny", "gobliny_edron_z9": "edron_gobliny", "gobliny_edron_z10_zachod": "edron_gobliny",
    "gobliny_edron_z10_wschod": "edron_gobliny", "gobliny_edron_z10_poludnie": "edron_gobliny",
    "stoj_trade": "edron_trade", "stoj_uh_edron_horn": "edron_horn",
    # Thais: kanały (szczury), troll cave na wschodzie (z8+z9, kieszenie połączone schodami), jaskinia trolli na północy (z8, z9), wilki, stanowisko
    "raty": "thais_raty", "trolle": "thais_trolle_wschod", "trolle_pelny": "thais_trolle_wschod", "trolle_nowe": "thais_trolle_wschod",
    "trolle_patrol": "thais_trolle_wschod", "thais_pn_z8": "thais_pn_trolle", "thais_pn_z9": "thais_pn_trolle",
    "wilki": "thais_wilki", "stoj_runy_thais": "thais_stoj_runy",
    # Kazordoon: powierzchnia z7 nad jaskinią trolli i jaskinia z8 + z9 (z9 NIEDOZWOLONE, Karol 24.10)
    "trolle_kazordoon_z7": "kazordoon_trolle", "trolle_kazordoon_z8": "kazordoon_trolle", "trolle_kazordoon_z9": "kazordoon_trolle",
    # Rookgaard: jaskinia szczurów pod miastem (z8 kieszeń/jaskinia, z9, z10), kanały z11, jaskinie bugów
    "rook": "rook_kanaly", "rook_kanaly_z11": "rook_kanaly",
    "rook_raty_z8": "rook_raty", "rook_raty_z8_do_smierci": "rook_raty", "rook_raty_z9": "rook_raty", "rook_raty_z9_do_smierci": "rook_raty",
    "rook_raty_z10": "rook_raty", "rook_cave_raty_z9_glab": "rook_raty", "rook_raty_z8_kieszen": "rook_raty",
    "rook_raty_z9_z_kieszeni": "rook_raty", "rook_raty_z10_zachod": "rook_raty",
    "rook_bugi_z8": "rook_bugi", "rook_bugi_z10": "rook_bugi",
    # Port Hope
    "ph_raty_z8": "port_hope_raty",
    # Ab'Dendriel: jaskinia trolli z9-z12 (z9..z12 + warianty z dojściem z depo), gobliny na z6
    "abdendriel_trolle_z9": "abdendriel_trolle", "abdendriel_trolle_z10": "abdendriel_trolle", "abdendriel_trolle_z11": "abdendriel_trolle",
    "abdendriel_trolle_z12": "abdendriel_trolle", "abdendriel_trolle_z10_z9": "abdendriel_trolle", "abdendriel_trolle_z11_z9": "abdendriel_trolle",
    "abdendriel_trolle_z12_z9": "abdendriel_trolle", "abdendriel_gobliny": "abdendriel_gobliny",
}

# ---- nowe mapy pięter (mapy.json): numery z generuj_rodziny_pietra.py, stan 26.10 ----
_NIEZW = "typ przejścia NIEZWERYFIKOWANY na żywo (z mapy klienta, kolor 210, flaga 2)"
_DOJ_EDRON = ("dojście = trasa bazowa %s + z9 do przejścia i lądowanie na z10; potrzebna LINA w plecaku (przejścia liną z bazy: z11->z10, z9->z8)")
NOWE_MAPY = {
    "trolle_edron_z10w": {
        "opis": ("Edron troll cave, wschodnia jaskinia z10 (składowa 260 pól, 13 potworów: Troll 7, Bear 3, Swamp Troll 2, Frost Troll 1; 3 przystanki + 4 przystanki "
                 "pokrycia, pętla 79 pól): trolle_edron_z10w_pelna_petla z mapy klienta (generuj_rodziny_pietra.py, 26.10; stara trolle_edron_z10w_petla miała 35 pól "
                 "i dojście przez (33127,31726,z9) = PRZESZKODA, nie przejście). Dojście trolle_edron_z10w_pelna_dojscie = trolle_edron_z9w_dojscie (sprawdzone na żywo "
                 "21.10, 169 pkt) + z9 18 pól do schodów (33128,31729,z9) (kolor 210) i lądowanie (33128,31729,z10); " + _NIEZW +
                 ". MUSI mieć rope (jak z9w). Powrót do depo: wyjście liną z10 -> z9 z pola (33128,31729,z10) (wpis w wyprawa.PLANY_PK['edron'], trasa trolle_edron_z10w_pelna_do_depo, "
                 "generuj_powroty_rodziny.py, testy/test_powroty_rodziny.py); lina z10 -> z9 NIEZWERYFIKOWANA na żywo"),
        "trasa": "trolle_edron_z10w_pelna_petla", "potwory": "Troll,Bear,Swamp Troll,Frost Troll", "prog_hp": 30,
        "dojscie": "trolle_edron_z10w_pelna_dojscie", "dojscie_z_dowolnego_pietra": True},
    "gobliny_edron_z10_zachod": {
        "opis": ("Edron jaskinia goblinów, z10 zachód (składowa 241 pól, 18 goblinów, 5 przystanków + 3 pokrycia, pętla 135 pól): gobliny_edron_z10_zachod_petla "
                 "(generuj_rodziny_pietra.py, 26.10). Dojście gobliny_edron_z10_zachod_dojscie = gobliny_edron_z9_dojscie (188 pkt, kończy na z9 (33092,31836)) + z9 47 pól "
                 "(omija ogień z buforem 1) do przejścia (33063,31822,z9) i lądowanie na z10; " + _NIEZW + ". MUSI mieć rope (jak gobliny_edron_z9). Powrót do depo: wyjście liną z10 -> z9 "
                 "z pola (33063,31822,z10) (wpis w wyprawa.PLANY_PK['gobliny_edron'], trasa gobliny_edron_z10_zachod_do_depo); lina z10 -> z9 NIEZWERYFIKOWANA na żywo"),
        "trasa": "gobliny_edron_z10_zachod_petla", "potwory": "Goblin", "prog_hp": 30,
        "dojscie": "gobliny_edron_z10_zachod_dojscie", "dojscie_z_dowolnego_pietra": True},
    "gobliny_edron_z10_wschod": {
        "opis": ("Edron jaskinia goblinów, z10 wschód (składowa 224 pola, 19 goblinów + 2 Wasp, 5 przystanków + 5 pokrycia, pętla 151 pól): gobliny_edron_z10_wschod_petla "
                 "(generuj_rodziny_pietra.py, 26.10). Wasp na liście, bo trują (trucizna, bot jej nie leczy): zabić od razu. Dojście gobliny_edron_z10_wschod_dojscie = "
                 "gobliny_edron_z9_dojscie + z9 32 pola do przejścia (33102,31822,z9) i lądowanie na z10; " + _NIEZW + ". MUSI mieć rope. Powrót do depo: wyjście liną z10 -> z9 z pola (33102,31822,z10) (wpis w wyprawa.PLANY_PK['gobliny_edron'], trasa gobliny_edron_z10_wschod_do_depo); "
                 "lina z10 -> z9 NIEZWERYFIKOWANA na żywo"),
        "trasa": "gobliny_edron_z10_wschod_petla", "potwory": "Goblin,Wasp", "prog_hp": 30,
        "dojscie": "gobliny_edron_z10_wschod_dojscie", "dojscie_z_dowolnego_pietra": True},
    "gobliny_edron_z10_poludnie": {
        "opis": ("Edron jaskinia goblinów, z10 południe (składowa 125 pól, 11 goblinów w 3 przystankach + 2 pokrycia, pętla 95 pól; najmniejsza z trzech kieszeni z10, "
                 "tuż nad progiem 10 potworów): gobliny_edron_z10_poludnie_petla (generuj_rodziny_pietra.py, 26.10). Dojście gobliny_edron_z10_poludnie_dojscie = "
                 "gobliny_edron_z9_dojscie + z9 41 pól do przejścia (33069,31848,z9) i lądowanie na z10; " + _NIEZW + ". MUSI mieć rope. Powrót do depo: wyjście liną z10 -> z9 z pola (33069,31848,z10) (wpis w wyprawa.PLANY_PK['gobliny_edron'], trasa gobliny_edron_z10_poludnie_do_depo); "
                 "lina z10 -> z9 NIEZWERYFIKOWANA na żywo"),
        "trasa": "gobliny_edron_z10_poludnie_petla", "potwory": "Goblin", "prog_hp": 30,
        "dojscie": "gobliny_edron_z10_poludnie_dojscie", "dojscie_z_dowolnego_pietra": True},
    "rook_raty_z10_zachod": {
        "opis": ("Rookgaard, jaskinia szczurów z10 zachód (składowa 201 pól, 11 Rat + 5 Cave Rat, 5 przystanków + 2 pokrycia, pętla 118 pól): rook_raty_z10_zachod_petla "
                 "(generuj_rodziny_pietra.py, 26.10; trzecie piętro rodziny rook_raty obok rook_raty_z9 i rook_raty_z10). Dojście rook_raty_z10_zachod_dojscie = rook_raty_z9_dojscie "
                 "(schody w depo (32027,32197), kieszeń z8, kratka (32029,32195,z8), 57 pkt, bot jeszcze jej sam nie przeszedł) + z9 43 pola po jaskini z9 do przejścia "
                 "(32021,32180,z9) i lądowanie na z10; " + _NIEZW + ". Start z z7 (bez dojscie_z_dowolnego_pietra, jak rook_raty_z9). Powrót do depo: BRAK planu w wyprawa.PLANY_PK i brak trasy "
                 "(z10 -> z9 to dziura: w górę tylko liną, a Rookgaard zwykle bez liny; nie generowano, żeby nie zgadywać), więc WROC/wyprawa z tej pętli = 'brak drogi'"),
        "trasa": "rook_raty_z10_zachod_petla", "potwory": "Rat,Cave Rat", "prog_hp": 30, "dojscie": "rook_raty_z10_zachod_dojscie"},
}

# ---- tabela spotów: nowe wpisy (spoty, które mapy.json już zna, ale tabela jeszcze nie, oraz nowe mapy pięter) ----
_POWOD_ABD = ("26.10: wpis dopisany dla rodziny `abdendriel_trolle` (spoty_nadzorca.json nie znał Ab'Dendriel; 23.10 poprzedni be-dev zostawił wybór spotów w Ab "
              "Karolowi). auto false = nadzorca tego spotu NIE wybiera (ani zmiana spotu po 3. spotkaniu gracza); włączenie = `auto: true` po decyzji Karola")
_POWOD_NOWE = ("26.10 (rodziny): mapa piętra wygenerowana offline z mapy klienta; typ przejścia niezweryfikowany na żywo (zejście dziurą z9 -> z10 i lina z10 -> z9; jak z9z przy dopisaniu); "
               "powrót do depo: wyjście w wyprawa.PLANY_PK dopisane 26.10 (generuj_powroty_rodziny.py, test_powroty_rodziny.py); auto false do pierwszego udanego przejścia "
               "na żywo jedną postacią, potem `auto: true`")
_POWOD_ROOK_Z10 = ("26.10 (rodziny): mapa piętra wygenerowana offline z mapy klienta; typ przejścia niezweryfikowany na żywo (zejście z z9); auto false: brak planu powrotu do depo w "
                   "wyprawa.PLANY_PK (z10 -> z9 = dziura, w górę tylko liną, Rookgaard zwykle bez liny: WROC/wyprawa = 'brak drogi'), do decyzji Karola")
NOWE_WPISY = {
    "trolle_edron_z10w": {"miasto": "edron", "jaskinia": "edron_trolle_z10w", "poziom": [8, 30], "poziom_zrodlo": "domyslne", "waga": 1.0, "auto": False,
                          "powod": "Troll, Bear, Swamp Troll, Frost Troll (13 potworów, pętla 79 pól); " + _POWOD_NOWE},
    "gobliny_edron_z10_zachod": {"miasto": "edron", "jaskinia": "edron_gobliny_z10_zachod", "poziom": [6, 20], "poziom_zrodlo": "domyslne", "waga": 1.0,
                                 "auto": False, "powod": "Goblin (18); gobliny Edronu wyłączone (Karol 21.10: za mało defa); " + _POWOD_NOWE},
    "gobliny_edron_z10_wschod": {"miasto": "edron", "jaskinia": "edron_gobliny_z10_wschod", "poziom": [6, 20], "poziom_zrodlo": "domyslne", "waga": 1.0,
                                 "auto": False, "powod": "Goblin (19) + Wasp (2, trucizna); gobliny Edronu wyłączone (Karol 21.10); " + _POWOD_NOWE},
    "gobliny_edron_z10_poludnie": {"miasto": "edron", "jaskinia": "edron_gobliny_z10_poludnie", "poziom": [6, 20], "poziom_zrodlo": "domyslne", "waga": 1.0,
                                   "auto": False, "powod": "Goblin (11); gobliny Edronu wyłączone (Karol 21.10); " + _POWOD_NOWE},
    "rook_raty_z10_zachod": {"miasto": "rook", "jaskinia": "rook_raty_z10_zachod", "poziom": [1, 7], "poziom_zrodlo": "domyslne", "waga": 1.0, "auto": False,
                             "powod": "Rat + Cave Rat (16); " + _POWOD_ROOK_Z10},
    # mapy już w mapy.json, jeszcze bez wpisu w tabeli (do 26.10 test_spoty.py był przez to czerwony)
    "abdendriel_trolle_z9": {"miasto": "abdendriel", "jaskinia": "abdendriel_trolle_z9", "poziom": [8, 30], "poziom_zrodlo": "domyslne", "waga": 1.0, "auto": False,
                             "powod": _POWOD_ABD},
    "abdendriel_trolle_z10": {"miasto": "abdendriel", "jaskinia": "abdendriel_trolle_z10", "poziom": [8, 30], "poziom_zrodlo": "domyslne", "waga": 1.0, "auto": False,
                              "powod": _POWOD_ABD},
    "abdendriel_trolle_z11": {"miasto": "abdendriel", "jaskinia": "abdendriel_trolle_z11", "poziom": [8, 30], "poziom_zrodlo": "domyslne", "waga": 1.0, "auto": False,
                              "powod": _POWOD_ABD},
    "abdendriel_trolle_z12": {"miasto": "abdendriel", "jaskinia": "abdendriel_trolle_z12", "poziom": [8, 30], "poziom_zrodlo": "domyslne", "waga": 1.0, "auto": False,
                              "powod": _POWOD_ABD},
    "abdendriel_trolle_z10_z9": {"miasto": "abdendriel", "jaskinia": "abdendriel_trolle_z10", "poziom": [8, 30], "poziom_zrodlo": "domyslne", "waga": 1.0,
                                 "auto": False, "powod": "ta sama pętla co abdendriel_trolle_z10, dojście z depo (24.10); " + _POWOD_ABD},
    "abdendriel_trolle_z11_z9": {"miasto": "abdendriel", "jaskinia": "abdendriel_trolle_z11", "poziom": [8, 30], "poziom_zrodlo": "domyslne", "waga": 1.0,
                                 "auto": False, "powod": "ta sama pętla co abdendriel_trolle_z11, dojście z depo (25.10); " + _POWOD_ABD},
    "abdendriel_trolle_z12_z9": {"miasto": "abdendriel", "jaskinia": "abdendriel_trolle_z12", "poziom": [8, 30], "poziom_zrodlo": "domyslne", "waga": 1.0,
                                 "auto": False, "powod": "ta sama pętla co abdendriel_trolle_z12, dojście z depo (25.10); " + _POWOD_ABD},
    "abdendriel_gobliny": {"miasto": "abdendriel", "jaskinia": "abdendriel_gobliny_z6", "poziom": [6, 20], "poziom_zrodlo": "domyslne", "waga": 1.0, "auto": False,
                           "powod": "gobliny pod Ab na z6 (25.10, niepotwierdzone na żywo: schody (32622,31790) i depo); " + _POWOD_ABD},
    "rook_raty_z8_kieszen": {"miasto": "rook", "jaskinia": "rook_raty_z8_kieszen", "poziom": [1, 7], "poziom_zrodlo": "domyslne", "waga": 1.0, "auto": False,
                             "powod": "26.10: wpis dla rodziny rook_raty; mapa bez dojścia (start tylko, gdy postać już stoi w kieszeni z dziurami), nadzorca jej nie wybiera"},
    "rook_raty_z9_z_kieszeni": {"miasto": "rook", "jaskinia": "rook_raty_z9", "poziom": [1, 7], "poziom_zrodlo": "domyslne", "waga": 1.0, "auto": False,
                                "powod": "26.10: wpis dla rodziny rook_raty; pętla jak rook_raty_z9, dojście z kieszeni z8 (start tylko, gdy postać stoi w kieszeni), nadzorca jej nie wybiera"},
    "stoj_uh_edron_horn": {"miasto": "edron", "jaskinia": "edron_horn", "poziom": [1, 999], "poziom_zrodlo": "domyslne", "waga": 1.0, "auto": False,
                           "powod": "nie poluje: stoi na statku Horn of Plenty i robi UH (stanowisko, 23.10); wpis dla spójności tabeli z mapy.json, nadzorca nie wybiera"},
}
MIASTO_ABD = {"x": [32530, 32860], "y": [31500, 31849]}     # świątynia (32732,31634), depo (32679,31687), jaskinie z7-z12, gobliny z6 do y 31857 (pętla poniżej: Kazordoon od y 31850 w x 32550-32700)


def zapis_atomowy(plik, dane):
    tmp = Path(str(plik) + ".tmp-rodziny")
    tmp.write_text(json.dumps(dane, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, plik)


def plan():
    """(nowe_mapy, zmiany_tabeli, opis) liczone z AKTUALNEJ zawartości plików. Nic nie zapisuje."""
    mapy = json.loads(MAPY.read_text(encoding="utf-8"))
    tab = json.loads(TABELA.read_text(encoding="utf-8"))
    opis = []
    for k, v in NOWE_MAPY.items():
        if mapy.get(k) != v:
            opis.append(f"mapy.json: {'AKTUALIZACJA' if k in mapy else 'nowy'} wpis {k}")
    if tab["miasta"].get("abdendriel") != MIASTO_ABD:
        opis.append("spoty_nadzorca.json: miasto abdendriel (prostokąt)")
    for k, v in NOWE_WPISY.items():
        w = dict(v, rodzina=RODZINY[k])
        if tab["spoty"].get(k) != w:
            opis.append(f"spoty_nadzorca.json: {'AKTUALIZACJA' if k in tab['spoty'] else 'nowy'} wpis {k}")
    for k, r in RODZINY.items():
        if k in tab["spoty"] and k not in NOWE_WPISY and tab["spoty"][k].get("rodzina") != r:
            opis.append(f"spoty_nadzorca.json: {k}.rodzina = {r}")
    brak = sorted(k for k in tab["spoty"] if k not in RODZINY and k not in NOWE_WPISY)
    if brak:
        opis.append(f"UWAGA spoty bez przypisanej rodziny: {brak}")
    return mapy, tab, opis


def zastosuj():
    # mapy.json: ponowny odczyt tuż przed zapisem, zmiana tylko moich kluczy
    mapy = json.loads(MAPY.read_text(encoding="utf-8"))
    zm = False
    for k, v in NOWE_MAPY.items():
        if mapy.get(k) != v:
            mapy[k] = v
            zm = True
    if zm:
        zapis_atomowy(MAPY, mapy)
    tab = json.loads(TABELA.read_text(encoding="utf-8"))
    zt = False
    if tab["miasta"].get("abdendriel") != MIASTO_ABD:
        tab["miasta"]["abdendriel"] = dict(MIASTO_ABD)
        zt = True
    for k, v in NOWE_WPISY.items():
        w = dict(v, rodzina=RODZINY[k])
        if tab["spoty"].get(k) != w:
            tab["spoty"][k] = w
            zt = True
    for k, r in RODZINY.items():
        if k in tab["spoty"] and k not in NOWE_WPISY and tab["spoty"][k].get("rodzina") != r:
            tab["spoty"][k]["rodzina"] = r
            zt = True
    if zt:
        zapis_atomowy(TABELA, tab)
    return zm, zt


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    _, _, opis = plan()
    print("\n".join(opis) if opis else "nic do zmiany (wszystko już wpisane)")
    if "--zapisz" in argv:
        zm, zt = zastosuj()
        print(f"zapisano: mapy.json={'tak' if zm else 'bez zmian'}, spoty_nadzorca.json={'tak' if zt else 'bez zmian'}")
    else:
        print("(bez --zapisz: nic nie zapisano)")


if __name__ == "__main__":
    main()
