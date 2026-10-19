"""Pet przywołany czarem (utevo res "nazwa"): wykrywanie w liście stworów i statystyki na spocie.

Czysta logika (bez gry): wykryj_peta() i Statystyki.probka(). Odczyt stworów idzie przez gniazdo
straznika, komenda "stwory" (te same pola co pamiec.py stwory). Zapis: logi/pet-<data>.jsonl,
jedna linia na próbkę i na zdarzenie (przywołany, zniknął, HP).
"""
import glob
import json
import os
import socket
import time

import instancja

NAZWA_PETA = "Elf Scout"
PROMIEN_PETA = 3          # pola od gracza, w których szukamy nowo przywołanego stworzenia
PROBKI_BRAK_DO_SMIERCI = 3  # tyle kolejnych próbek bez peta = "nieobecny" (jeszcze nie zgon)
ZGON_BRAK_S = 120.0         # s bez peta na liście, po których uznajemy zgon (17.10 fałszywy zgon po 3 próbkach)


def stwory_z_gniazda():
    """Lista stworów z straznika (ta sama, co `pamiec.py stwory`)."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(5)
        s.connect(str(instancja.gniazdo()))
        s.sendall((json.dumps({"cmd": "stwory"}) + "\n").encode())
        dane = b""
        while not dane.endswith(b"\n"):
            kawalek = s.recv(65536)
            if not kawalek:
                break
            dane += kawalek
    return json.loads(dane.decode())["stwory"]


def wykryj_peta(stwory, id_przed, nazwa=NAZWA_PETA, promien=PROMIEN_PETA):
    """Id nowo przywołanego peta: stworzenie o tej nazwie, którego nie było przed czarem (id_przed),
    stojące obok gracza. Zwraca None, gdy nic takiego nie ma. Gracze i cudze stwory są pomijane."""
    gracz = next((s for s in stwory if s.get("gracz")), None)
    if gracz is None:
        return None
    for s in stwory:
        if s.get("gracz") or s.get("nazwa") != nazwa or s["id"] in id_przed:
            continue
        odl = max(abs(s["x"] - gracz["x"]), abs(s["y"] - gracz["y"]))
        if s["z"] == gracz["z"] and odl <= promien:
            return s["id"]
    return None


def stan_peta(stwory, pet_id):
    """Dane peta z bieżącej listy (None, gdy go nie ma: zginął albo zmienił piętro).
    Bez pola "atakowany": w gniazdzie to nasz cel (ramka), pet nigdy nim nie jest, więc nic nie mówi o ataku peta."""
    for s in stwory:
        if s["id"] == pet_id:
            return {"hp": s["hp"], "x": s["x"], "y": s["y"], "z": s["z"]}
    return None


def obok_peta(stwory, pet_id, cel_id=None, promien=PROMIEN_PETA, limit=8):
    """Potwory (bez graczy i peta) w promieniu peta z ich HP. Spadek HP takiego potwora przy becie = dmg peta
    (przybliżenie, bo gniazdo nie pokazuje, kto zadał cios)."""
    pet = next((s for s in stwory if s["id"] == pet_id), None)
    if pet is None:
        return []
    wynik = []
    for s in stwory:
        if s.get("gracz") or s["id"] == pet_id or s["z"] != pet["z"]:
            continue
        odl = max(abs(s["x"] - pet["x"]), abs(s["y"] - pet["y"]))
        if odl <= promien:
            wynik.append({"id": s["id"], "nazwa": s["nazwa"], "hp": s["hp"], "odl": odl,
                          "cel": s["id"] == cel_id})   # cel = nasz cel w tej chwili (pet go nie musiał bić)
    return wynik[:limit]


def pierwsze_przywolanie(katalog_logow, pet_id):
    """(plik, t) najwcześniejszego zdarzenia "przywolany" tego peta w logach peta (bez pet-nadzor.jsonl).
    Pozwala kontynuować zapis w tym samym pliku po restarcie bota, zamiast zaczynać nowy."""
    for plik in sorted(glob.glob(os.path.join(katalog_logow, "pet-*.jsonl"))):
        if os.path.basename(plik) == "pet-nadzor.jsonl":
            continue
        with open(plik, encoding="utf-8") as f:
            for linia in f:
                try:
                    w = json.loads(linia)
                except ValueError:
                    continue
                if w.get("zdarzenie") == "przywolany" and w.get("pet_id") == pet_id:
                    return plik, w["t"]
    return None


class Statystyki:
    """Zapis zdarzeń i próbek peta do pliku jsonl. Sam nic nie czyta z gry."""

    def __init__(self, katalog_logow, teraz=time.time):
        self.teraz = teraz
        os.makedirs(katalog_logow, exist_ok=True)
        data = time.strftime("%Y%m%d-%H%M%S", time.localtime(teraz()))
        self.plik = os.path.join(katalog_logow, f"pet-{data}.jsonl")
        self.pet_id = None
        self.t_przywolania = None
        self.t_widziany = None        # ostatnia chwila, gdy pet był na liście stworów
        self.nieobecny = False        # pet zniknął z listy, ale jeszcze nie uznany za zgon
        self.brak = 0
        self.zgony = 0
        self.przywolania = 0
        self.zabicia_obok_peta = 0

    def _zapisz(self, wpis):
        wpis = {"t": round(self.teraz(), 1), **wpis}
        with open(self.plik, "a", encoding="utf-8") as f:
            f.write(json.dumps(wpis, ensure_ascii=False) + "\n")

    def przywolanie(self, pet_id, gracz):
        """Wołane, gdy wykryj_peta() znajdzie nowego peta po czarze."""
        self.pet_id = pet_id
        self.t_przywolania = self.teraz()
        self.t_widziany = self.t_przywolania
        self.brak = 0
        self.nieobecny = False
        self.przywolania += 1
        self._zapisz({"zdarzenie": "przywolany", "pet_id": pet_id, "przywolanie_nr": self.przywolania,
                      "gracz": gracz})

    def wznow(self, plik, pet_id, t_przywolania):
        """Po restarcie bota: dopisuj do pliku pierwszego przywołania tego peta, z jego czasem życia."""
        self.plik = plik
        self.pet_id = pet_id
        self.t_przywolania = t_przywolania
        self.t_widziany = self.teraz()
        self.brak = 0
        self.nieobecny = False
        self._zapisz({"zdarzenie": "wznowiony", "pet_id": pet_id, "od_przywolania_t": t_przywolania})

    def probka(self, stwory, gracz, cel_id=None):
        """Jedna próbka: stan peta i postaci. Wołać co kilka sekund w pętli bota.
        Brak peta na liście to nie od razu zgon: gracz widzi tylko część mapy, a pet może odejść poza zasięg.
        Zgon = brak na liście dłużej niż ZGON_BRAK_S."""
        if self.pet_id is None:
            return
        pet = stan_peta(stwory, self.pet_id)
        zyl = round(self.teraz() - self.t_przywolania, 1)
        if pet is None:
            self.brak += 1
            if not self.nieobecny and self.brak == PROBKI_BRAK_DO_SMIERCI:
                self.nieobecny = True
                self._zapisz({"zdarzenie": "nieobecny", "pet_id": self.pet_id, "zyl_s": zyl, "gracz": gracz})
            if self.nieobecny and self.teraz() - self.t_widziany >= ZGON_BRAK_S:
                self.zgony += 1
                self._zapisz({"zdarzenie": "zniknal", "powod": "brak_na_liscie", "pet_id": self.pet_id,
                              "zyl_s": zyl, "nieobecny_s": round(self.teraz() - self.t_widziany, 1), "gracz": gracz})
                self.pet_id = None
                self.nieobecny = False
            return
        if self.nieobecny:
            self._zapisz({"zdarzenie": "wrocil", "pet_id": self.pet_id, "pet": pet, "gracz": gracz,
                          "nieobecny_s": round(self.teraz() - self.t_widziany, 1)})
            self.nieobecny = False
        self.brak = 0
        self.t_widziany = self.teraz()
        self._zapisz({"zdarzenie": "probka", "pet_id": self.pet_id, "pet": pet, "gracz": gracz,
                      "obok": obok_peta(stwory, self.pet_id, cel_id), "zyl_s": zyl})
