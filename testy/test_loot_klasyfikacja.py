import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
"""P5 (13.10): klasyfikacja braku miejsca w loot.py i wagi domyślne z danych. Offline, bez gry.
Uruchom: python3 -I test_loot_klasyfikacja.py"""
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import loot, wyprawa

ok = True


def sprawdz(opis, warunek):
    global ok
    print(("OK    " if warunek else "BŁĄD "), opis)
    ok &= bool(warunek)


class P:
    def __init__(s, zajete, pojemnosc, widoczne):
        s.kontener = {"pojemnosc": pojemnosc, "przedmioty": [{"slot": i, "id": 3003, "ilosc": 1} for i in zajete]}
        s.sloty = list(range(widoczne))


MEAT, GOLD = 3577, 3031
sprawdz("20/20 -> sloty_pelne", loot.klasyfikuj_brak_miejsca(P(range(20), 20, 16), MEAT, 1, 50)[0] == "sloty_pelne")
sprawdz("19/20, wolny slot 19, widoczne 16 -> slot_ukryty",
        loot.klasyfikuj_brak_miejsca(P(range(19), 20, 16), MEAT, 1, 50)[0] == "slot_ukryty")
sprawdz("10/20, cap 12 (meat 13 oz), meat x1 -> za_ciezki",
        loot.klasyfikuj_brak_miejsca(P(range(10), 20, 20), MEAT, 1, 12)[0] == "za_ciezki")
sprawdz("gold x5 przy cap 14 -> nie za_ciezki",
        loot.klasyfikuj_brak_miejsca(P(range(10), 20, 20), GOLD, 5, 14)[0] != "za_ciezki")
sprawdz("brak cap -> nieznany", loot.klasyfikuj_brak_miejsca(P(range(10), 20, 20), MEAT, 1, None)[0] == "nieznany")
w = wyprawa.WAGI_DOMYSLNE
sprawdz("wagi z danych: ham 20, dragon ham 30, bread 5, cheese 4",
        (w["ham"], w["dragon ham"], w["bread"], w["cheese"]) == (20.0, 30.0, 5.0, 4.0))
sprawdz("waga_id(meat) 13", loot.waga_id(MEAT) == 13.0)
print("WYNIK:", "OK" if ok else "BŁĄD")
sys.exit(0 if ok else 1)
