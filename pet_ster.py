"""Sterowanie petem przywołanym czarem (utevo res "nazwa"): decyzja o przywołaniu, śledzenie peta, filtr listy
stworów i statystyki (logi/pet-<data>.jsonl przez pet.Statystyki). Czysta logika: bez gry, bez wpisywania na czacie.
Cavebot woła: obserwuj() w każdym ticku, powod_blokady() przed rzutem, rzucono() po wpisaniu czaru,
bez_peta() na liście do wyboru celów, wiadomosc() dla linii czatu/Server Log.

Zasady (Karol 17.10): pet atakuje cele bota, bot go nie bije, nie liczy jako cel i nie ucieka przed nim.
Pet nie idzie po schodach/dziurach: zmiana piętra = pet przepada. Ponowne przywołanie dopiero na nowym, ustabilizowanym
piętrze (PET_STABILNE_S) i bez zmian pięter w serii (spot wielopiętrowy = brak przywoływania)."""
import json
import re
import time
from collections import deque

import pet as pet_modul

PROMIEN_ZABICIA = 3            # pola od peta: potwór, który tu zniknął, to zabicie "obok peta"
OKNO_ZABICIA_S = 5.0           # s: pet był obok potwora (albo go atakował) nie dawniej niż tyle przed zniknięciem
OKNO_DETEKCJI_S = 12.0         # s po czarze, w których szukamy nowego stworzenia obok gracza
PROBKA_CO_S = 3.0              # s: odstęp próbek HP peta (pet.Statystyki.probka)
KOMUNIKAT_LIMIT_NA_MIN = 40    # linii komunikatów zapisywanych na minutę (ochrona logu)
# linie czatu/Server Log związane z przywołaniem i zabiciem (format serwera nieznany: zapisujemy surowo)
WZORZEC_KOMUNIKATU = re.compile(
    r"summon|utevo res|convinc|creature|master|your pet|slain|killed|dies|died|not enough|"
    r"cannot|can not|you may not|mana", re.IGNORECASE)


def odleglosc(a, b):
    return max(abs(a["x"] - b["x"]), abs(a["y"] - b["y"]))


class PetSterowanie:
    def __init__(self, katalog_logow, teraz_scienny=time.time, log=print):
        self.katalog = katalog_logow
        self.zegar_sc = teraz_scienny
        self.log = log
        self._stat = None
        # stan peta
        self.pet_id = None
        self.pet_z = None
        self.pet_poz = None
        self.id_przed = None          # zbiór id przed czarem (None = nie czekamy na peta)
        self.rzut_t = float("-inf")
        self.rzut_sc = float("-inf")  # czas ścienny ostatniego czaru (do filtra komunikatów)
        self.rzut_mana = None
        self.porazki = 0              # kolejne czary bez wykrytego peta
        self.wylaczony_do = float("-inf")
        self.przerwa_do = float("-inf")
        self.zgony_pietro = 0
        self.przyjety_reczny = False  # 17.10: pet przywołany poza botem (bez rzutu z bota) przyjęty raz na sesję
        # piętro
        self.z = None
        self.z_od = None
        self.zmiany_pieter = deque(maxlen=20)
        # statystyki
        self.ostatnia_probka = float("-inf")
        self.potwory = {}             # id -> {"nazwa","x","y","z","hp","pet_blisko_t"}
        self.zabicia_wlasne = 0       # zabicia obok peta, w których cel bota znikł (zabił bot albo pet)
        self.widziane_msg = deque(maxlen=300)
        self.msg_okno = deque(maxlen=KOMUNIKAT_LIMIT_NA_MIN)

    # --- zapis ---
    @property
    def stat(self):
        if self._stat is None:       # plik pet-<data>.jsonl powstaje dopiero przy pierwszym zdarzeniu
            self._stat = pet_modul.Statystyki(self.katalog, teraz=self.zegar_sc)
        return self._stat

    def _zapisz(self, wpis):
        self.stat._zapisz(wpis)

    def _gracz_dict(self, g, poz):
        g = g or {}
        return {"hp": g.get("hp"), "mana": g.get("mana"), "exp": g.get("exp"),
                "x": poz[0], "y": poz[1], "z": poz[2]}

    # --- filtr listy ---
    def bez_peta(self, lista):
        """Lista bez peta (do wyboru celów, ucieczki, lootu). Pet nigdy nie jest celem ani zagrożeniem."""
        if self.pet_id is None and self.id_przed is None:
            return lista
        return [s for s in lista if not self._to_pet(s)]

    def _to_pet(self, s):
        if self.pet_id is not None and s.get("id") == self.pet_id:
            return True
        return False

    # --- decyzja o przywołaniu ---
    def powod_blokady(self, wlaczony, mana, mana_min, walka, teraz, poz, *, pietro_spotu=0, stabilne_s=45.0,
                      zmiany_max=2, zmiany_okno_s=600.0, zgony_max=5):
        """None = można przywołać; inaczej krótki powód odmowy (do testów i debugowania)."""
        if not wlaczony:
            return "wylaczony"
        if self.pet_id is not None:
            return "jest_pet"
        if self.id_przed is not None:
            return "czeka_na_detekcje"
        if teraz < self.wylaczony_do:
            return "porazki"
        if teraz < self.przerwa_do:
            return "przerwa"
        if zgony_max and self.stat_zgony() >= zgony_max:
            return "limit_zgonow"
        if mana is None or mana < mana_min:
            return "mana"
        if walka:
            return "walka"
        if pietro_spotu:
            if poz[2] != pietro_spotu:
                return "inne_pietro"
        elif self.z is None or self.z != poz[2] or teraz - self.z_od < stabilne_s:
            return "pietro_niestabilne"
        zm = sum(1 for t in self.zmiany_pieter if teraz - t <= zmiany_okno_s)
        if zm >= zmiany_max:
            return "wiele_pieter"
        return None

    def stat_zgony(self):
        return 0 if self._stat is None else self._stat.zgony

    def rzucono(self, lista, mana, teraz, przerwa_s, tekst):
        """Po wpisaniu czaru: zapamiętaj id sprzed czaru (nowe stworzenie obok = pet)."""
        self.id_przed = {s["id"] for s in lista}
        self.rzut_t = teraz
        self.rzut_sc = self.zegar_sc()
        self.rzut_mana = mana
        self.przerwa_do = teraz + przerwa_s
        self._zapisz({"zdarzenie": "czar", "tekst": tekst, "mana": mana, "id_przed": len(self.id_przed)})

    # --- obserwacja w ticku ---
    def obserwuj(self, surowa, g, poz, teraz, *, cel_id=None, nazwa=pet_modul.NAZWA_PETA, stabilne_s=45.0,
                 porazki_max=2, przerwa_po_porazkach_s=900.0):
        """Wołane raz na tick z pełną (niefiltrowaną) listą stworów. Nie rzuca czarów."""
        # piętro
        if self.z is None:
            self.z, self.z_od = poz[2], teraz
        elif poz[2] != self.z:
            self.zmiany_pieter.append(teraz)
            self._zapisz({"zdarzenie": "zmiana_pietra", "z_przed": self.z, "z_po": poz[2],
                          "pet": self.pet_id is not None})
            self.z, self.z_od = poz[2], teraz
        # pet przepadł przy zmianie piętra
        if self.pet_id is not None and self.pet_z is not None and poz[2] != self.pet_z:
            self._utrata("pietro", g, poz, teraz)
        # po czarze: czekamy na nowe stworzenie obok gracza
        if self.id_przed is not None:
            lista = self._z_graczem(surowa, g, poz)
            nowy = pet_modul.wykryj_peta(lista, self.id_przed, nazwa=nazwa)
            if nowy is not None:
                self.pet_id, self.pet_z = nowy, poz[2]
                self.id_przed = None
                self.porazki = 0
                self.ostatnia_probka = float("-inf")
                self.potwory.clear()
                self.stat.przywolanie(nowy, self._gracz_dict(g, poz))
                self.log(f"[PET] przywołany {nazwa} id {nowy} (mana {self.rzut_mana} -> {g.get('mana')})")
            elif teraz - self.rzut_t > OKNO_DETEKCJI_S:
                self.id_przed = None
                self.porazki += 1
                self._zapisz({"zdarzenie": "brak_peta_po_czarze", "mana_przed": self.rzut_mana,
                              "mana_po": g.get("mana"), "porazka": self.porazki,
                              "w_poblizu": [s["nazwa"] for s in surowa if not s.get("gracz")][:12]})
                self.log(f"[PET] po czarze nie ma nowego {nazwa} obok (porażka {self.porazki}/{porazki_max})")
                if self.porazki >= porazki_max:
                    self.wylaczony_do = teraz + przerwa_po_porazkach_s
                    self.porazki = 0
                    self.log(f"[PET] wyłączam przywoływanie na {przerwa_po_porazkach_s / 60:.0f} min "
                             f"(zła nazwa, za mało many, brak czaru?)")
        # 17.10: pet przywołany poza botem (np. ręcznie, bot nie rzucał): nie ma id_przed, więc przyjmujemy stworzenie
        # o nazwie peta obok gracza. Tylko przed pierwszym rzutem bota i raz na sesję (zgon nie wyzwala ponownego przyjęcia).
        if self.pet_id is None and self.id_przed is None and not self.przyjety_reczny and self.rzut_t == float("-inf"):
            reczny = pet_modul.wykryj_peta(self._z_graczem(surowa, g, poz), set(), nazwa=nazwa)
            if reczny is not None:
                self.przyjety_reczny = True
                self.pet_id, self.pet_z = reczny, poz[2]
                self.ostatnia_probka = float("-inf")
                self.potwory.clear()
                # pet z poprzedniego startu bota: dopisujemy do jego pliku, z czasem życia od prawdziwego przywołania
                prz = pet_modul.pierwsze_przywolanie(self.katalog, reczny)
                if prz is not None:
                    self.stat.wznow(prz[0], reczny, prz[1])
                    self.log(f"[PET] wznowiony {nazwa} id {reczny} (przywołany {self.zegar_sc() - prz[1]:.0f} s temu)")
                else:
                    self.stat.przywolanie(reczny, self._gracz_dict(g, poz))
                    self.log(f"[PET] przyjęty {nazwa} id {reczny} (przywołany poza botem, bez rzutu)")
        # próbki HP peta i zgon
        if self.pet_id is not None and teraz - self.ostatnia_probka >= PROBKA_CO_S:
            self.ostatnia_probka = teraz
            stat = self.stat
            stat.probka(surowa, self._gracz_dict(g, poz), cel_id=cel_id)
            if stat.pet_id is None:           # pet.Statystyki zapisał "zniknal" (zgon)
                self.log(f"[PET] pet zginął (zgonów {stat.zgony})")
                self.pet_id = self.pet_z = self.pet_poz = None
        # pozycja peta i zabicia obok niego
        self._zabicia(surowa, poz, teraz, cel_id, exp=g.get("exp"))

    def _z_graczem(self, surowa, g, poz):
        """Lista z naszą postacią na pierwszym miejscu (pet.wykryj_peta bierze pierwszego gracza)."""
        ja = [s for s in surowa if s.get("gracz") and (s["x"], s["y"], s["z"]) == tuple(poz)]
        if ja:
            return ja + [s for s in surowa if s is not ja[0]]
        return [{"nazwa": "", "id": -1, "x": poz[0], "y": poz[1], "z": poz[2], "hp": 100, "gracz": True}] + list(surowa)

    def _utrata(self, powod, g, poz, teraz):
        zyl = None if self._stat is None or self._stat.t_przywolania is None else round(self.zegar_sc() - self._stat.t_przywolania, 1)
        if powod == "pietro":
            self.zgony_pietro += 1
        self._zapisz({"zdarzenie": "zniknal", "powod": powod, "pet_id": self.pet_id, "zyl_s": zyl,
                      "gracz": self._gracz_dict(g, poz)})
        self.log(f"[PET] pet przepadł ({powod})")
        if self._stat is not None:
            self._stat.pet_id = None
            self._stat.brak = 0
        self.pet_id = self.pet_z = self.pet_poz = None
        self.potwory.clear()

    def _zabicia(self, surowa, poz, teraz, cel_id, exp=None):
        pet_s = None
        if self.pet_id is not None:
            pet_s = next((s for s in surowa if s["id"] == self.pet_id), None)
            if pet_s is not None:
                self.pet_poz = (pet_s["x"], pet_s["y"], pet_s["z"])
        obecne = {}
        for s in surowa:
            if s.get("gracz") or s["id"] == self.pet_id or s.get("hp", 100) <= 0:
                continue
            obecne[s["id"]] = s
        for id_, s in obecne.items():
            wpis = self.potwory.get(id_) or {"pet_blisko_t": None, "dmg_pet": 0, "dmg_gracz": 0}
            stary_hp = wpis.get("hp")
            wpis.update(nazwa=s["nazwa"], x=s["x"], y=s["y"], z=s["z"], hp=s.get("hp"))
            if pet_s is not None and s["z"] == pet_s["z"] and odleglosc(s, pet_s) <= PROMIEN_ZABICIA:
                wpis["pet_blisko_t"] = teraz
                # 17.10 udział w obrażeniach (przybliżenie): spadek HP potwora przy becie. Cel bota = nasz,
                # reszta = pet (gniazdo nie mówi, kto zadał cios, więc to tylko przybliżenie)
                if stary_hp is not None and s.get("hp") is not None and s["hp"] < stary_hp:
                    klucz = "dmg_gracz" if id_ == cel_id else "dmg_pet"
                    wpis[klucz] += stary_hp - s["hp"]
            self.potwory[id_] = wpis
        for id_ in [i for i in self.potwory if i not in obecne]:
            w = self.potwory.pop(id_)
            if self.pet_id is None or w["z"] != poz[2]:
                continue                       # zmiana piętra albo brak peta: nie zabicie
            if w["pet_blisko_t"] is not None and teraz - w["pet_blisko_t"] <= OKNO_ZABICIA_S:
                self.stat.zabicia_obok_peta += 1
                if id_ == cel_id:
                    self.zabicia_wlasne += 1
                self._zapisz({"zdarzenie": "zabicie_obok_peta", "potwor": w["nazwa"], "hp_ostatnie": w["hp"],
                              "x": w["x"], "y": w["y"], "pet": self.pet_poz, "cel_bota": id_ == cel_id,
                              "razem": self.stat.zabicia_obok_peta, "dmg_pet": w["dmg_pet"],
                              "dmg_gracz": w["dmg_gracz"], "exp_przed": exp})

    # --- komunikaty serwera ---
    def wiadomosc(self, w, nazwa=pet_modul.NAZWA_PETA, teraz=None):
        """Surowa linia czatu/Server Log związana z petem (przywołanie, zabicie) trafia do jsonl bez zmian."""
        tekst = str(w.get("tekst", ""))
        if not tekst or not (WZORZEC_KOMUNIKATU.search(tekst) or nazwa.casefold() in tekst.casefold()):
            return False
        # tylko, gdy pet w grze albo świeżo po czarze (inaczej "mana" w rozmowie graczy zaśmiecałoby log)
        t = self.zegar_sc() if teraz is None else teraz
        if self.pet_id is None and self.id_przed is None and t - self.rzut_sc > 120:
            return False
        klucz = (w.get("nr"), w.get("autor"), tekst, w.get("czas"))
        if klucz in self.widziane_msg:
            return False
        self.widziane_msg.append(klucz)
        if len(self.msg_okno) == self.msg_okno.maxlen and t - self.msg_okno[0] < 60:
            return False
        self.msg_okno.append(t)
        self._zapisz({"zdarzenie": "komunikat", "kanal": w.get("kanal"), "autor": w.get("autor"),
                      "tekst": tekst[:300]})
        return True

    def podsumowanie(self):
        s = self._stat
        return json.dumps({"przywolania": 0 if s is None else s.przywolania, "zgony": 0 if s is None else s.zgony,
                           "zgony_pietro": self.zgony_pietro,
                           "zabicia_obok_peta": 0 if s is None else s.zabicia_obok_peta})
