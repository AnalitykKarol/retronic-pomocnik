import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
"""27.10: kontenery.py - flaga "zagniezdzony" (hasParent, Container +0x30) i pole "rodzic" (ustal_rodzicow). Offline: atrapa pamięci,
zero gry. Uruchom: python3 -I testy/test_kontenery_rodzic.py (KONTENERY_TEST_PLIK=<ścieżka> testuje inną kopię modułu)."""
import importlib.util
import struct
import sys
from pathlib import Path

sys.dont_write_bytecode = True
plik = _os.environ.get("KONTENERY_TEST_PLIK") or str(Path(__file__).resolve().parent.parent / "kontenery.py")
spec = importlib.util.spec_from_file_location("kontenery_test", plik)
K = importlib.util.module_from_spec(spec)
spec.loader.exec_module(K)

ok = True


def sprawdz(opis, warunek, info=""):
    global ok
    print(("OK    " if warunek else "BŁĄD "), opis, "" if warunek else info)
    ok &= bool(warunek)


def kon(numer, nazwa, ident, przedm=(), zagn=False):
    return {"numer": numer, "nazwa": nazwa, "id": ident, "zagniezdzony": zagn, "pojemnosc": 20,
            "przedmioty": [{"slot": i, "id": a, "ilosc": 1} for i, a in enumerate(przedm)]}


BLANK, UH, GOLD, ROPE = 3147, 3160, 3031, 3003

# 1. układ odchyd/kolanoth: plecak z ekwipunku (2869) z bagiem 2869 w środku, bag otwarty w osobnym oknie (zagniezdzony)
zewn = kon(1, "blue backpack", 2869, [GOLD, BLANK, 2869, ROPE, BLANK])
wewn = kon(0, "blue backpack", 2869, [BLANK] * 5 + [UH] * 2, zagn=True)
K.ustal_rodzicow([wewn, zewn], 2869)
sprawdz("1a zewnętrzne okno = ekwipunek slot 3", zewn["rodzic"] == {"typ": "ekwipunek", "slot": 3}, zewn["rodzic"])
sprawdz("1b wewnętrzne okno = kontener nr 1, w ekwipunku slot 3", wewn["rodzic"] == {"typ": "kontener", "numer": 1, "w_ekwipunku": 3}, wewn["rodzic"])

# 2. normalny układ (gerbor): plecak 2854 + zielony bag 2865 w środku
plecak = kon(0, "backpack", 2854, [GOLD, 2865, 3035])
zielony = kon(1, "green backpack", 2865, [3198] * 16 + [BLANK] * 4, zagn=True)
K.ustal_rodzicow([plecak, zielony], 2854)
sprawdz("2a normalny układ: plecak = ekwipunek, zielony = w plecaku", plecak["rodzic"]["typ"] == "ekwipunek"
        and zielony["rodzic"] == {"typ": "kontener", "numer": 0, "w_ekwipunku": 3}, (plecak, zielony))

# 3. brak tablicy ekwipunku: zewnętrzne to "korzen" (nie rozstrzygnięto), wewnętrzne nie ma w_ekwipunku
zewn, wewn = kon(1, "blue backpack", 2869, [2869]), kon(0, "blue backpack", 2869, [BLANK], zagn=True)
K.ustal_rodzicow([wewn, zewn], None)
sprawdz("3a bez tablicy ekwipunku: korzeń nierozstrzygnięty, wewnętrzne bez w_ekwipunku",
        zewn["rodzic"] == {"typ": "korzen"} and wewn["rodzic"] == {"typ": "kontener", "numer": 1, "w_ekwipunku": None}, (zewn, wewn))

# 4. zwłoki obok plecaka: zwłoki "na zewnątrz" bez ID plecaka -> inne; bag w zwłokach (zagniezdzony) -> rodzic zwłoki, nie plecak
plecak = kon(0, "backpack", 2854, [GOLD, BLANK])
zwloki = kon(1, "dead rat", 3994, [ROPE, 2865], zagn=False)
bag_w_zwlokach = kon(2, "green backpack", 2865, [GOLD], zagn=True)
K.ustal_rodzicow([plecak, zwloki, bag_w_zwlokach], 2854)
sprawdz("4a zwłoki = inne, plecak = ekwipunek", zwloki["rodzic"] == {"typ": "inne"} and plecak["rodzic"]["typ"] == "ekwipunek")
sprawdz("4b bag w zwłokach: rodzic = zwłoki (nr 1), w_ekwipunku None (nie dostaje roli z plecaka)",
        bag_w_zwlokach["rodzic"] == {"typ": "kontener", "numer": 1, "w_ekwipunku": None}, bag_w_zwlokach["rodzic"])

# 5. dwa kandydaci na rodzica (ten sam ID bagu w plecaku i w zwłokach): nie zgadujemy
plecak = kon(0, "backpack", 2854, [2865])
zwloki = kon(1, "dead rat", 3994, [2865])
bag = kon(2, "green backpack", 2865, [BLANK], zagn=True)
K.ustal_rodzicow([plecak, zwloki, bag], 2854)
sprawdz("5 dwóch kandydatów na rodzica: numer None", bag["rodzic"] == {"typ": "kontener", "numer": None, "w_ekwipunku": None}, bag["rodzic"])

# 6. dwa równorzędne plecaki "na zewnątrz" o ID plecaka z ekwipunku: nie rozstrzygamy
a, b = kon(0, "backpack", 2854, [GOLD]), kon(1, "backpack", 2854, [ROPE])
K.ustal_rodzicow([a, b], 2854)
sprawdz("6 dwa zewnętrzne o ID plecaka: korzeń, bez roli ekwipunku", a["rodzic"] == {"typ": "korzen"} and b["rodzic"] == {"typ": "korzen"}, (a, b))

# 7. flaga nieczytelna -> rodzic None; plecak o innym ID niż w ekwipunku -> inne
x = kon(0, "backpack", 2854, [GOLD], zagn=None)
y = kon(1, "purple backpack", 2868, [BLANK], zagn=False)
K.ustal_rodzicow([x, y], 2854)
sprawdz("7 flaga None -> rodzic None; zewnętrzny o obcym ID -> inne", x["rodzic"] is None and y["rodzic"] == {"typ": "inne"}, (x, y))

# 8. odczyt flagi z surowego Container (atrapa pamięci)
OBRAZ = (0x400000, 0x1000000)


class Pam:
    def __init__(self, bloki):
        self.bloki = bloki

    def czytaj(self, adres, dl):
        for start, b in self.bloki.items():
            if start <= adres and adres + dl <= start + len(b):
                return b[adres - start: adres - start + dl]
        return b""


def surowy_kontener(numer, flaga, nazwa=b"bag"):
    b = bytearray(0x50)
    struct.pack_into("<II", b, 0, 0x500000, 2)                       # vtable w obrazie, licznik referencji
    struct.pack_into("<iiI", b, K.KONTENER_NUMER, numer, 20, 0)      # numer, pojemność, brak przedmiotu kontenera
    b[0x18:0x18 + len(nazwa)] = nazwa
    struct.pack_into("<II", b, 0x28, len(nazwa), 15)                 # rozmiar, pojemność bufora (SSO)
    b[0x30] = flaga
    return bytes(b)


for flaga, oczek in ((0, False), (1, True), (7, None)):
    p = Pam({0x20000: surowy_kontener(3, flaga)})
    k = K._kontener(p, 0x20000, 3, OBRAZ)
    sprawdz(f"8 flaga +0x30 = {flaga} -> zagniezdzony {oczek}", k is not None and k["zagniezdzony"] is oczek and k["numer"] == 3, k)
sprawdz("8d pozostałe pola kontenera bez zmian (id, pojemnosc, przedmioty, nazwa)",
        k["id"] is None and k["pojemnosc"] == 20 and k["przedmioty"] == [] and k["nazwa"] == "bag")

# 9. wrapper kontenery(p): błąd w ustalaniu rodzica NIE psuje odczytu; sukces dopisuje pole
baza = [kon(0, "backpack", 2854, [2865]), kon(1, "green backpack", 2865, [BLANK], zagn=True)]
K._kontenery_surowe = lambda p: baza
K._plecak_z_ekwipunku = lambda p: 2854
w = K.kontenery(object())
sprawdz("9a kontenery(): lista z polem rodzic", w is baza and w[0]["rodzic"]["typ"] == "ekwipunek" and w[1]["rodzic"]["w_ekwipunku"] == 3, w)


def zly(p):
    raise RuntimeError("tablica ekwipunku padła")


K._plecak_z_ekwipunku = zly
baza2 = [kon(0, "backpack", 2854, [GOLD])]
K._kontenery_surowe = lambda p: baza2
w = K.kontenery(object())
sprawdz("9b błąd tablicy ekwipunku: lista zwrócona bez wyjątku", w is baza2 and w[0]["numer"] == 0)
K._kontenery_surowe = lambda p: []
sprawdz("9c pusta lista przechodzi", K.kontenery(object()) == [])

print("\nWYNIK:", "OK" if ok else "BŁĘDY")
sys.exit(0 if ok else 1)
