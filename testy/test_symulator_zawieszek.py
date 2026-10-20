#!/usr/bin/env python3
"""16.10 (F2, SPEC_zasady_zawieszki_1016): symulator zawieszek, OFFLINE. Przypadki syntetyczne (plansze z tekstu) i znane z gry
(drabina (32506,32270) z9 w górę, drzwi (32505,32270,z8) zamknięte vs otwarte). Bez bota, X11 i zapisu do danych."""
import os
import sys
from pathlib import Path

os.environ.setdefault("RETRONIC_TESTY", "1")
sys.dont_write_bytecode = True
RAZEM = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAZEM))
sys.path.insert(0, str(RAZEM / "narzedzia"))

import symulator_zawieszek as S  # noqa: E402

wyniki = []


def sprawdz(nazwa, warunek, info=""):
    wyniki.append(bool(warunek))
    print(("OK   " if warunek else "FAIL ") + nazwa + (f"  {info}" if not warunek and info else ""))


def pietra(w):
    return {p[2] for p in w["sciezka"]}


# --- synteza: klasyfikacja zamknięty / otwarty (Z1)
POKOJ = ["#######",
         "#.....#",
         "#.....#",
         "#######"]
sw = S.Swiat.z_planszy({8: (100, 100, POKOJ)})
kl, n = S.klasyfikuj(sw, (101, 101, 8), cel=None)
sprawdz("Z1 pokój 10 pól bez wyjścia = zamknięty", kl == "zamkniety" and n == 10, f"{kl} {n}")
sprawdz("Z1 cel w pokoju = otwarty (droga do celu po piętrze)", S.klasyfikuj(sw, (101, 101, 8), cel=(104, 102, 8))[0] == "otwarty")
sprawdz("Z1 cel na innym piętrze nie otwiera pokoju", S.klasyfikuj(sw, (101, 101, 8), cel=(104, 102, 7))[0] == "zamkniety")
DUZA = ["#" * 12] + ["#" + "." * 10 + "#"] * 7 + ["#" * 12]          # 70 pól
sprawdz("Z1 obszar >= 60 pól = otwarty", S.klasyfikuj(S.Swiat.z_planszy({8: (0, 0, DUZA)}), (3, 3, 8))[0] == "otwarty")

# --- Z7: kieszeń bez wyjścia -> alarm, bez STOP
w = S.symuluj(sw, (101, 101, 8), cel=(50, 50, 8), ziarno=1)
sprawdz("Z7 kieszeń bez wyjścia: wynik brak_wyjscia", w["wynik"] == "brak_wyjscia", w["wynik"])
sprawdz("Z7 alarm=True, stop=False (decyzja Karola: alarm bez STOP)", w["alarm"] is True and w["stop"] is False)
sprawdz("Z7 nie zgaduje: pozycja się nie zmieniła, czas 0", w["poz_koniec"] == [101, 101, 8] and w["czas_s"] == 0.0)
sprawdz("Z7 próg zawieszki dla zamkniętego obszaru 15 s", w["prog_s"] == 15.0 and w["czas_od_zawieszki_s"] == 15.0)

# --- Z2: wyjście kroki -> piętro; schody w dół z pokoju na piętrze celu
DWA = ["#########",
       "#.......#",
       "#.......#",
       "#########"]
OTW9 = ["#" * 14] + ["#" + "." * 12 + "#"] * 6 + ["#" * 14]
przej = [dict(od=(104, 101, 8), do=(104, 101, 9), rodzaj="schody", id="s1")]
sw2 = S.Swiat.z_planszy({8: (100, 100, DWA), 9: (98, 98, OTW9)}, przejscia=przej)
w = S.symuluj(sw2, (101, 101, 8), cel=(105, 103, 9), ziarno=1)
sprawdz("Z2 schody w dół: wyszedl", w["wynik"] == "wyszedl" and w["poz_koniec"][2] == 9, str(w["wynik"]))
sprawdz("Z2 czas = kroki x krok_s (2 kroki dojścia + 1 wejście)", w["kroki"] == 3 and w["czas_zakres_s"] == [1.8, 2.7], f"{w['kroki']} {w['czas_zakres_s']}")
sprawdz("Z2 parametr krok_s=1.0 -> czas 3.0 s", S.symuluj(sw2, (101, 101, 8), cel=(105, 103, 9), krok_s=1.0)["czas_s"] == 3.0)
sprawdz("Z2 zdarzenia: dojście, przejście", [z["akcja"] for z in w["zdarzenia"]] == ["dojscie", "przejscie"], str(w["zdarzenia"]))
sw2_sciana = sw2.kopia()
sw2_sciana.dziury.add((104, 101, 8))
w = S.symuluj(sw2_sciana, (101, 101, 8), cel=(105, 103, 9))
sprawdz("Z8/nauczona dziura jest ścianą: wyjście zablokowane -> brak_wyjscia", w["wynik"] == "brak_wyjscia", w["wynik"])
sw2_ogien = sw2.kopia()
sw2_ogien.ogien.add((103, 101, 8))
sw2_ogien.ogien.add((103, 102, 8))
w = S.symuluj(sw2_ogien, (101, 101, 8), cel=(105, 103, 9))
sprawdz("ogień w przejściu pokoju odcina wyjście", w["wynik"] == "brak_wyjscia", w["wynik"])

# --- Z2: kierunek pięter: dwa wyjścia, jedno bliższe w złą stronę
DOL = ["#" * 14] + ["#" + "." * 12 + "#"] * 6 + ["#" * 14]
POK = ["#######", "#.....#", "#.....#", "#######"]
przej3 = [dict(od=(101, 101, 8), do=(101, 101, 9), rodzaj="dziura", id="dol"),          # blisko, w dół
          dict(od=(105, 102, 8), do=(105, 100, 7), rodzaj="drabina", id="gora")]       # dalej, w górę
sw3 = S.Swiat.z_planszy({8: (99, 100, POK), 9: (95, 95, DOL), 7: (95, 95, DOL)}, przejscia=przej3)
w_g = S.symuluj(sw3, (103, 101, 8), cel=(100, 100, 7), ziarno=1)
w_d = S.symuluj(sw3, (103, 101, 8), cel=(100, 100, 9), ziarno=1)
sprawdz("Z2 cel na z7: wybiera drabinę w górę mimo bliższej dziury", w_g["poz_koniec"][2] == 7, str(w_g["poz_koniec"]))
sprawdz("Z2 cel na z9: wybiera dziurę w dół", w_d["poz_koniec"][2] == 9, str(w_d["poz_koniec"]))
sprawdz("Z2 bez celu wygrywa bliższe wyjście (koszt)", S.symuluj(sw3, (103, 101, 8), ziarno=1)["poz_koniec"][2] == 9)

# --- Z3: brak pętli kieszeń-kieszeń
A = ["#####", "#...#", "#...#", "#####"]
B = ["#####", "#...#", "#...#", "#####"]
petla = [dict(od=(101, 101, 8), do=(101, 101, 9), rodzaj="dziura", id="A->B"),
         dict(od=(103, 102, 9), do=(103, 102, 8), rodzaj="drabina", id="B->A")]
swp = S.Swiat.z_planszy({8: (100, 100, A), 9: (100, 100, B)}, przejscia=petla)
w = S.symuluj(swp, (103, 101, 8), cel=(500, 500, 8), ziarno=3)
sprawdz("Z3 kieszeń A -> kieszeń B (wyjście tylko z powrotem): nie wchodzi w głąb", 9 not in pietra(w), str(w["sciezka"]))
sprawdz("Z3 wynik brak_wyjscia, alarm, bez STOP", w["wynik"] == "brak_wyjscia" and w["alarm"] and not w["stop"], w["wynik"])
# kieszeń B ma prawdziwe wyjście w górę do C: schodzimy, bo z B jest wyjście
C = ["#" * 12] + ["#" + "." * 10 + "#"] * 7 + ["#" * 12]
petla2 = petla + [dict(od=(101, 102, 9), do=(105, 105, 7), rodzaj="drabina", id="B->C")]
swp2 = S.Swiat.z_planszy({8: (100, 100, A), 9: (100, 100, B), 7: (100, 100, C)}, przejscia=petla2)
w = S.symuluj(swp2, (103, 101, 8), cel=(106, 106, 7), ziarno=3)
sprawdz("Z3 kieszeń z wyjściem w górę wolno wybrać: A -> B -> C", w["wynik"] == "wyszedl" and w["poz_koniec"][2] == 7, f"{w['wynik']} {w['poz_koniec']}")
reg = [tuple(p) for p in w["sciezka"]]
pietra_kolej = [reg[0][2]] + [b[2] for a, b in zip(reg, reg[1:]) if a[2] != b[2]]
sprawdz("Z3 piętra po drodze bez powrotu: 8, 9, 7", pietra_kolej == [8, 9, 7], str(pietra_kolej))

# --- Z4: wyjście zawodzi -> złe, następne; po 3 porażkach alarm
WIELE = ["#########", "#.......#", "#.......#", "#########"]
zle3 = [dict(od=(101, 101, 8), do=(101, 101, 9), rodzaj="schody", dziala=False, id="z1"),
        dict(od=(103, 101, 8), do=(103, 101, 9), rodzaj="schody", dziala=False, id="z2"),
        dict(od=(105, 101, 8), do=(105, 101, 9), rodzaj="schody", dziala=True, id="ok")]
swz = S.Swiat.z_planszy({8: (100, 100, WIELE), 9: (98, 98, OTW9)}, przejscia=zle3)
w = S.symuluj(swz, (102, 102, 8), cel=(105, 103, 9), ziarno=2)
sprawdz("Z4 dwa wyjścia zawodzą, trzecie działa: wyszedl", w["wynik"] == "wyszedl" and w["porazki"] == 2, f"{w['wynik']} {w['porazki']}")
sprawdz("Z4 złe pola zapamiętane", len(w["zle_pola"]) == 2)
sprawdz("Z4 koszt nieudanych prób wlicza się do czasu", w["czas_s"] >= 2 * S.KOSZT_NIEUDANEJ_PROBY_S, str(w["czas_s"]))
zle_wszystkie = [dict(zle3[0]), dict(zle3[1]), dict(zle3[2], dziala=False)]
swz3 = S.Swiat.z_planszy({8: (100, 100, WIELE), 9: (98, 98, OTW9)}, przejscia=zle_wszystkie)
w = S.symuluj(swz3, (102, 102, 8), cel=(105, 103, 9), ziarno=2)
sprawdz("Z4 trzy nieudane próby -> alarm limit_prob, bez STOP", w["wynik"] == "alarm" and w["powod"] == "limit_prob" and w["porazki"] == 3 and not w["stop"],
        f"{w['wynik']} {w['powod']} {w['porazki']}")
swz2 = S.Swiat.z_planszy({8: (100, 100, WIELE), 9: (98, 98, OTW9)}, przejscia=zle_wszystkie[:2])
w = S.symuluj(swz2, (102, 102, 8), cel=(105, 103, 9), ziarno=2)
sprawdz("Z4 wszystkie wyjścia wyczerpane po 2 próbach -> alarm (nie brak_wyjscia)", w["wynik"] == "alarm" and w["powod"] == "wyczerpane_proby", f"{w['wynik']} {w['powod']}")

# --- drzwi: zamknięte vs otwarte, zablokowane
KORYT = ["#########",
         "#...D...#",
         "#########"]
KORYT_O = [r.replace("D", "d") for r in KORYT]
sdz = S.Swiat.z_planszy({8: (100, 100, KORYT)})
sdo = S.Swiat.z_planszy({8: (100, 100, KORYT_O)})
sprawdz("drzwi zamknięte: pokój zamknięty", S.klasyfikuj(sdz, (101, 101, 8), cel=(107, 101, 8))[0] == "zamkniety")
sprawdz("drzwi otwarte: ten sam układ jest otwarty (cel osiągalny)", S.klasyfikuj(sdo, (101, 101, 8), cel=(107, 101, 8))[0] == "otwarty")
wz = S.symuluj(sdz, (101, 101, 8), cel=(107, 101, 8))
wo = S.symuluj(sdo, (101, 101, 8), cel=(107, 101, 8))
sprawdz("drzwi zamknięte: używa drzwi i wychodzi", wz["wynik"] == "wyszedl" and any(z["akcja"] == "drzwi" for z in wz["zdarzenia"]), str(wz["wynik"]))
sprawdz("drzwi otwarte: bez użycia drzwi, wynik wyszedl bez zdarzeń", wo["wynik"] == "wyszedl" and not any(z["akcja"] == "drzwi" for z in wo["zdarzenia"]), str(wo["zdarzenia"]))
sprawdz("świat wejściowy nie jest zmieniany przez symulację (drzwi dalej zamknięte)", sdz.drzwi[(104, 101, 8)]["otwarte"] is False)
sbk = S.Swiat.z_planszy({8: (100, 100, [r.replace("D", "B") for r in KORYT])})
wb = S.symuluj(sbk, (101, 101, 8), cel=(107, 101, 8))
sprawdz("drzwi zablokowane (klucz): porażka, alarm, brak ruchu przez drzwi", wb["alarm"] and wb["porazki"] == 1 and wb["wynik"] == "alarm", f"{wb['wynik']} {wb['porazki']}")

# --- Z6: blokada gracz/mob, czekanie 5-10 s, limit prób
bl = S.Swiat.z_planszy({8: (99, 100, POK), 9: (95, 95, DOL)}, przejscia=[dict(od=(101, 101, 8), do=(101, 101, 9), rodzaj="dziura", id="dol")],
                       blokady={(101, 101, 8): 12.0})
w = S.symuluj(bl, (103, 101, 8), cel=(100, 100, 9), ziarno=5)
cz = [z["s"] for z in w["zdarzenia"] if z["akcja"] == "czekaj"]
sprawdz("Z6 blokada chwilowa: czeka 5-10 s i wychodzi", w["wynik"] == "wyszedl" and cz and all(5.0 <= c <= 10.0 for c in cz), f"{w['wynik']} {cz}")
bl_wiecz = S.Swiat.z_planszy({8: (99, 100, POK), 9: (95, 95, DOL)}, przejscia=[dict(od=(101, 101, 8), do=(101, 101, 9), rodzaj="dziura", id="dol")],
                             blokady={(101, 101, 8): float("inf")})
w = S.symuluj(bl_wiecz, (103, 101, 8), cel=(100, 100, 9), ziarno=5)
cz = [z for z in w["zdarzenia"] if z["akcja"] == "czekaj"]
sprawdz("Z6 blokada wieczna: najwyżej CZEKAJ_MAX czekań, potem porażka (brak wiecznego czekania)", len(cz) == S.CZEKAJ_MAX and w["wynik"] in ("alarm", "brak_wyjscia") and w["alarm"],
        f"{len(cz)} {w['wynik']}")

# --- Z5: otwarty obszar, oscylacja -> inny punkt, nie ten sam kierunek
OTW = ["#" * 22] + ["#" + "." * 20 + "#"] * 5 + ["#" * 22]
so = S.Swiat.z_planszy({8: (0, 0, OTW)})
punkty = [(2, 3, 8), (19, 3, 8), (10, 1, 8)]
w = S.symuluj(so, (10, 3, 8), cel=(20, 3, 8), punkty=punkty, ziarno=1)
sprawdz("Z5 otwarty: wyszedl poza promień kotwicy", w["wynik"] == "wyszedl" and w["klasa_start"] == "otwarty", f"{w['wynik']} {w['klasa_start']}")
sprawdz("Z5 próg dla otwartego obszaru 30 s", w["prog_s"] == 30.0)
sprawdz("Z5 inny punkt nie w kierunku celu (cel na wschodzie -> idzie na zachód)", w["poz_koniec"][0] < 10, str(w["poz_koniec"]))
sprawdz("Z5 czas wyjścia < 10 s (cel z sekcji 3: zmiana wzorca w <= 10 s)", w["czas_s"] <= 10.0, str(w["czas_s"]))

# --- losowość tylko wśród równorzędnych, determinizm
SYM = ["###########", "#.........#", "#.........#", "#.........#", "###########"]
ssym = S.Swiat.z_planszy({8: (100, 100, SYM), 9: (98, 98, OTW9)},
                         przejscia=[dict(od=(101, 102, 8), do=(101, 102, 9), rodzaj="schody", id="lewo"),
                                    dict(od=(109, 102, 8), do=(109, 102, 9), rodzaj="schody", id="prawo")])
wyb = {tuple(S.symuluj(ssym, (105, 102, 8), cel=(101, 101, 9), ziarno=z)["poz_koniec"]) for z in range(30)}
sprawdz("losowość: dwa równorzędne wyjścia (ten sam koszt) -> oba pojawiają się przy różnych ziarnach", len(wyb) == 2, str(wyb))
a = S.symuluj(ssym, (105, 102, 8), cel=(101, 101, 9), ziarno=7)
b = S.symuluj(ssym, (105, 102, 8), cel=(101, 101, 9), ziarno=7)
sprawdz("determinizm: to samo ziarno = ten sam wynik, ścieżka i czas", a == b)
rozne = [S.symuluj(sw3, (103, 101, 8), cel=(100, 100, 7), ziarno=z)["sciezka"] for z in range(10)]
sprawdz("brak losowości przy nierównych kosztach: ścieżka niezależna od ziarna", all(r == rozne[0] for r in rozne))
sprawdz("losowy czas czekania też deterministyczny przy ziarnie",
        S.symuluj(bl, (103, 101, 8), cel=(100, 100, 9), ziarno=9) == S.symuluj(bl, (103, 101, 8), cel=(100, 100, 9), ziarno=9))

# --- opcje D3 są zgodne z OPCJE bota
kl, op = S.opcje_d3(sw2, (101, 101, 8), cel=(105, 103, 9))
sprawdz("opcje: te same nazwy co D3 OPCJE, w tej samej kolejności", [o["akcja"] for o in op] == ["krok_skos", "cofnij", "inny_punkt", "przejscie_pietra", "czekaj", "alarm"]
        and set(o["akcja"] for o in op) == set(S.OPCJE), str([o["akcja"] for o in op]))
pp = next(o for o in op if o["akcja"] == "przejscie_pietra")
sprawdz("opcje: zamknięty -> tylko przejście pięter i alarm dopuszczalne", kl == "zamkniety" and pp["dopuszczalna"] and pp["pietro_docelowe"] == 9
        and not any(o["dopuszczalna"] for o in op if o["akcja"] in ("krok_skos", "cofnij", "inny_punkt")))

# --- świat z prawdziwej mapy: drabina (32506,32270) z9 i drzwi (32505,32270,z8)
if (RAZEM / "mapa" / "map74.otmm").is_file() and (RAZEM / "trasy" / "miejsca_troll.json").is_file():
    sz = S.swiat_z_repo(drzwi_otwarte=False)
    kl, n = S.klasyfikuj(sz, (32508, 32273, 9))
    sprawdz("mapa: kieszeń z9 (32508,32273) = zamknięty obszar 12 pól", kl == "zamkniety" and n == 12, f"{kl} {n}")
    w = S.symuluj(sz, (32508, 32273, 9), cel=(32502, 32270, 8), ziarno=1)
    prz = [z for z in w["zdarzenia"] if z["akcja"] == "przejscie"]
    sprawdz("mapa: kieszeń z9 -> wychodzi na z8", w["wynik"] == "wyszedl" and prz and prz[0]["z_do"] == 8, f"{w['wynik']} {prz}")
    sprawdz("mapa: wyjście drabiną z pola (32506,32269|32270) z9, ścieżka przez (32507,32270)", prz and prz[0]["rodzaj"] == "drabina"
            and tuple(w["sciezka"][0]) == (32508, 32273, 9) and any(tuple(p)[:2] == (32507, 32270) for p in w["sciezka"]), str(w["sciezka"]))
    ent = [z for z in w["zdarzenia"] if z["akcja"] == "dojscie"][0]
    sprawdz("mapa: dojście do drabiny w <= 4 krokach (wyrocznia: dystans 3)", ent["dlugosc"] <= 4, str(ent))
    sprawdz("mapa: wynik niezależny od ziarna (jedno wyjście)", all(tuple(S.symuluj(sz, (32508, 32273, 9), cel=(32502, 32270, 8), ziarno=k)["sciezka"]) == tuple(w["sciezka"]) for k in range(5)))
    # drzwi
    zam = S.swiat_z_repo(drzwi_otwarte=False)
    otw = S.swiat_z_repo(drzwi_otwarte=True)
    start = (32507, 32270, 8)
    cel = (32502, 32270, 8)
    k_z, n_z = S.klasyfikuj(zam, start, cel)
    k_o, n_o = S.klasyfikuj(otw, start, cel)
    sprawdz("mapa: drzwi (32505,32270,z8) zamknięte = pokój zamknięty", k_z == "zamkniety", f"{k_z} {n_z}")
    sprawdz("mapa: drzwi otwarte = obszar otwarty (cel osiągalny)", k_o == "otwarty", f"{k_o} {n_o}")
    wz = S.symuluj(zam, start, cel=cel, ziarno=1)
    wo = S.symuluj(otw, start, cel=cel, ziarno=1)
    dr = [z for z in wz["zdarzenia"] if z["akcja"] == "drzwi"]
    sprawdz("mapa: drzwi zamknięte -> podchodzi do (32506,32270) i używa drzwi", wz["wynik"] == "wyszedl" and dr and dr[0]["poz"] == [32506, 32270, 8], f"{wz['wynik']} {dr}")
    sprawdz("mapa: drzwi zamknięte -> wyjście w kilka sekund, nie w 766 s", wz["czas_s"] < 10.0, str(wz["czas_s"]))
    sprawdz("mapa: drzwi otwarte -> bez użycia drzwi, dochodzi do celu", wo["wynik"] == "wyszedl" and not any(z["akcja"] == "drzwi" for z in wo["zdarzenia"]), str(wo["zdarzenia"]))
    sprawdz("mapa: kontrola jednej zmiennej (tylko flaga drzwi) zmienia ścieżkę", wz["sciezka"] != wo["sciezka"] or wz["zdarzenia"] != wo["zdarzenia"])
    # nauczone dziury z repo są ścianami ((32498,32271,8) usunięta 20.10 jako fałszywa — patrz test_dane_schody_troll)
    sprawdz("mapa: nauczone dziury z trasy/dziury_nauczone.json wczytane jako ściany", (32508, 32273, 8) in sz.dziury and not sz.wolne((32508, 32273, 8)))
    # walidacja na danych
    wal = S.waliduj(sz)
    e = wal["epizody"]
    if e is not None:
        sprawdz("walidacja: klasa zamknięty/otwarty zgodna z przyczyny.json we wszystkich 99 epizodach", e["porownanych"] >= 99 and e["zgodna_klasa"] == e["porownanych"], f"{e['zgodna_klasa']}/{e['porownanych']}")
        roz = [x for x in e["wiersze"] if x["sim_obszar"] != x["ref_obszar"]]
        sprawdz("walidacja: różnice rozmiaru tylko o 1 (nauczona dziura) albo limit BFS", all(x["ucieta"] or x["ref_obszar"] - x["sim_obszar"] == 1 for x in roz), str(roz[:3]))
    else:
        print("SKIP walidacja epizodów (UNKNOWN: brak ~/Games/Retronic/modele-test/dane)")
    o = wal["wyrocznia"]
    if o is not None and o["wiersze"]:
        wi = o["wiersze"]
        sprawdz("walidacja: wszystkie zamknięte obszary z potwierdzonym wyjściem kończą 'wyszedl'", all(x["wynik"] == "wyszedl" for x in wi), str([x["poz"] for x in wi if x["wynik"] != "wyszedl"]))
        sprawdz("walidacja: czas symulacji < rzeczywisty we wszystkich przypadkach", all(x["sim_s"] < x["real_s"] for x in wi))
    else:
        print("SKIP walidacja wyroczni (UNKNOWN: brak oracle_wyjscie.json)")
    # --- walidacja rozszerzona (16.10): odtworzenie epizodów, siatka, wyrocznia, znane przypadki
    ext = S.waliduj_rozszerzona(sz)
    E = ext["epizody"]
    if E is not None:
        sprawdz("odtworzenie: wszystkie 107 epizodów zasymulowane we wszystkich wariantach A, B, C", E["epizodow"] >= 107 and len(E["wiersze"]) == E["epizodow"]
                and all(set(w["wariant"]) == {"A", "B", "C"} for w in E["wiersze"]))
        sprawdz("odtworzenie: 'brak_wyjscia' (Z7) tylko w zamkniętych obszarach, nigdy w otwartych", all(w["wariant"][v]["wynik"] != "brak_wyjscia" for w in E["wiersze"] for v in "ABC" if w["wariant"][v]["klasa_start"] == "otwarty"))
        sprawdz("odtworzenie: otwarty bez celu i punktów = brak_danych, bez alarmu (UNKNOWN, nie Z7)", all(w["wariant"]["A"]["alarm"] is False for w in E["wiersze"] if w["wariant"]["A"]["wynik"] == "brak_danych"))
        sprawdz("odtworzenie: stop zawsze False", all(w["wariant"][v]["stop"] is False for w in E["wiersze"] for v in "ABC"))
        sprawdz("odtworzenie: z punktami trasy wszystkie otwarte epizody wychodzą (B)", all(w["wariant"]["B"]["wynik"] == "wyszedl" for w in E["wiersze"] if w["ref_zamkniety"] is False))
        b = S.blad_czasu(E["wiersze"], "A")
        sprawdz("błąd czasu: >= 20 zamkniętych epizodów z rzeczywistym wyjściem, mediana i p90 policzone", len(b) >= 20 and S._mediana([abs(x["blad_s"]) for x in b]) is not None
                and S._p90([abs(x["blad_s"]) for x in b]) >= S._mediana([abs(x["blad_s"]) for x in b]), str(len(b)))
        sprawdz("kieszeń z7 (32338-32340,32200-32202) bez wyjścia w symulatorze (flaga 2 bez ważnego lądowania) i w telemetrii",
                all(w["wariant"]["A"]["wynik"] == "brak_wyjscia" for w in E["wiersze"] if w["poz"][2] == 7 and 32338 <= w["poz"][0] <= 32340 and 32200 <= w["poz"][1] <= 32202))
    sg = ext["siatka"]
    if sg is not None:
        sprawdz("siatka 15x11: >= 99,8% pól zgodnych, różnice tylko na nauczonych dziurach", sg["zgodnych"] / sg["pol"] >= 0.998 and sg["pol"] - sg["zgodnych"] == sum(sg["rozne"].values()), f"{sg['zgodnych']}/{sg['pol']}")
    orr = ext["wyrocznia"]
    if orr is not None:
        sprawdz("wyrocznia: 43 wpisy, symulator nie wyrzuca wyjątków, wynik 'wyszedl' albo jawny brak_wyjscia", orr["przypadkow"] >= 43 and all(x["sim_wynik"] in ("wyszedl", "brak_wyjscia") for x in orr["wiersze"]))
        dr9 = [x for x in orr["wiersze"] if x["poz"] == [32506, 32270, 9]]
        sprawdz("wyrocznia: drabina (32506,32270) z9 znaleziona przez symulator", dr9 and all(x["sim_rodzaj"] == "drabina" for x in dr9))
    zn = {z["nazwa"]: z for z in ext["znane"]}
    sprawdz("znane: pokój za drzwiami: zamknięte = 2 kroki (drzwi), otwarte = 9 kroków (schody), czyli '2 vs 8'",
            zn["pokój za drzwiami, drzwi ZAMKNIĘTE, cel (32478,32290,z8)"]["kroki"] == 2 and zn["pokój za drzwiami, drzwi OTWARTE, cel (32478,32290,z8)"]["kroki"] == 9)
    sprawdz("znane: kieszeń z9 bez celu schodzi na z10, z celem na z8 idzie drabiną w górę",
            zn["kieszeń z9, bez celu"]["koniec"][2] == 10 and zn["kieszeń z9, cel (32502,32270,z8)"]["koniec"][2] == 8)
    sprawdz("zdarzenie 'przejscie' zawiera pole wejścia (od)", all("od" in z for z in S.symuluj(sz, (32506, 32270, 9), ziarno=1)["zdarzenia"] if z["akcja"] == "przejscie"))
    k = wal["karol"]
    if k is not None:
        sprawdz("walidacja: przejęcia Karola >= 62 jako przypadki, wszystkie symulują się bez wyjątku", k["przypadkow"] >= 62, str(k["przypadkow"]))
        zam = [x for x in k["wiersze"] if x["klasa"] == "zamkniety"]
        sprawdz("walidacja: zamknięte starty Karola: symulacja kończy 'wyszedl' albo jawny brak_wyjscia (Z7), bez nieoczekiwanych wyników",
                all(x["sim_wynik"] in ("wyszedl", "brak_wyjscia") for x in zam), str([x["sim_wynik"] for x in zam]))
    else:
        print("SKIP walidacja przejęć (UNKNOWN: brak logi/pomoc-karola.jsonl)")
else:
    print("SKIP testy na prawdziwej mapie (brak mapa/map74.otmm albo trasy/miejsca_troll.json)")

print(f"\n{sum(wyniki)}/{len(wyniki)} OK")
sys.exit(0 if all(wyniki) else 1)
