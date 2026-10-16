"""Widmo własnej postaci po przelogowaniu: Pamiec.pozycja przy duplikacie nazwy wybiera wpis zgodny z blokiem
statystyk gracza (HP, adres). Atrapy. RDZEN_DIR = katalog z testowanym rdzen.py (domyślnie pomocnik)."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, struct
sys.dont_write_bytecode = True
sys.path.insert(0, _os.environ.get("RDZEN_DIR") or _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import rdzen

ok = []
def sprawdz(n, w, info=""):
    ok.append(bool(w)); print(("OK   " if w else "FAIL ") + n + ("" if w else f"  [{info}]"))

POZ = {0x1169ca88: (32488, 32294, 8), 0x132719f8: (32490, 32294, 8)}
class A(rdzen.Pamiec):
    def __init__(s, nazwa="Jointoramix"):
        super().__init__(); s.mem = object(); s.lista = []; s.g = {}; s.nazwa = nazwa
    def stwory(s): return s.lista
    def gracz(s): return s.g
    def czytaj(s, adres, dl):
        # adres = adres wpisu + POZYCJA_STWORA; dl = nazwa+1 - POZYCJA_STWORA
        baza = adres - rdzen.POZYCJA_STWORA
        x, y, z = POZ[baza]
        return struct.pack("<IIB", x, y, z).ljust(-rdzen.POZYCJA_STWORA, b"\0") + s.nazwa.encode("latin-1") + b"\0"

def wpis(adres, ident, hp=100):
    x, y, z = POZ[adres]
    return {"id": ident, "nazwa": "Jointoramix", "gracz": True, "x": x, "y": y, "z": z, "hp": hp, "adres": hex(adres)}

# Wybór wpisu przy duplikacie nazwy przeniesiono z rdzen.Pamiec.pozycja do bot.wybierz_wlasny (34c4842, 15.10):
# pozycja() tylko czyta zapamiętany adres_postaci, a wybór (ruch, potem HP i adres bloku) robi bot. Tu: reguły awaryjne
# (bez ruchu) bota; ruch pokrywa testy/test_widmo_zywe.py.
import bot
k1, k2 = wpis(0x132719f8, 268478551), wpis(0x1169ca88, 268852462)
w = bot.wybierz_wlasny([k2, k1], {"hp": 200, "max_hp": 200, "adres": "0x13271e68"})
sprawdz("duplikat: wybrany wpis żywej sesji (adres bloku)", w and w["adres"] == hex(0x132719f8), w)
k1, k2 = wpis(0x132719f8, 268478551, hp=75), wpis(0x1169ca88, 268852462, hp=100)
w = bot.wybierz_wlasny([k1, k2], {"hp": 150, "max_hp": 200})   # brak adresu: rozstrzyga HP
sprawdz("duplikat: rozstrzyga HP", w and w["adres"] == hex(0x132719f8), w)

a = A()
a.lista = [wpis(0x1169ca88, 268852462)]
a.g = {"hp": 200, "max_hp": 200, "adres": "0x13271e68"}
a.adres_postaci = 0x1169ca88
sprawdz("pojedynczy wpis: bez zmian", a.pozycja("Jointoramix") == {"x": 32488, "y": 32294, "z": 8})
print("WYNIK", "OK" if all(ok) else "FAIL"); sys.exit(0 if all(ok) else 1)
