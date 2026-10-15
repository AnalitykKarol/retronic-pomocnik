"""Obrona przed graczami (PK), wymaganie 1 ze SPEC_obrona_pk_1015: atak gracza rozpoznany z DANYCH
(spadek HP + obcy gracz tuż obok + żaden potwór przy nas), bez pytania modelu.

Czysta logika bez wejścia/wyjścia gry (cavebot.py podaje listę stworów, pozycję i HP; tu tylko decyzje i plik wrogów):
 - DetektorPK: okno spadku HP (jak UCIECZKA_PREDYKCJA), obcy gracz w PK_ODL (opcjonalnie PK_ODL_CZAR = zasięg czaru),
   brak potwora w odl <= 1. Własna postać (także "widmo" o tym samym nicku po relogu) nie jest obcym graczem.
 - Wrogowie: trwały plik wrogowie.json (zapis atomowy tmp + os.replace): nick -> {od, ost, ile, powod, miejsce};
   plus karencja_do (czas ścienny): do kiedy nie wracamy na spot.
Pokrętła czytane z `konf` (moduł cavebot) przy każdym wywołaniu: PK_OBRONA, PK_ODL, PK_ODL_CZAR, PK_SPADEK_PP,
PK_OKNO_S, PK_KARENCJA_MIN, PK_WROG_WAZNY_H. Tylko stdlib."""
import json
import os
import time
from pathlib import Path

import instancja

PLIK_WROGOW = instancja.S.stan / "wrogowie.json"


def _cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def klucz_nicku(nick):
    """Porównywanie nicków: bez wielkości liter i skrajnych spacji."""
    return " ".join(str(nick or "").split()).casefold()


def jest_wlasna(nazwa, wlasna):
    """Postać gracza albo jej widmo (relog zostawia w pamięci drugi wpis o tym samym nicku)."""
    return bool(wlasna) and klucz_nicku(nazwa) == klucz_nicku(wlasna)


class Wrogowie:
    """Trwała lista wrogów (nick -> dane) i karencja powrotu na spot."""

    def __init__(self, plik=None, czas=time.time, log=print):
        self.plik = Path(plik) if plik else PLIK_WROGOW
        self.czas = czas
        self.log = log
        self.dane = {}                  # klucz_nicku -> {"nick","od","ost","ile","powod","miejsce"}
        self.karencja_do = 0.0          # czas ścienny
        self.wczytaj()

    def wczytaj(self):
        try:
            d = json.loads(self.plik.read_text())
            self.dane = {klucz_nicku(k): v for k, v in (d.get("wrogowie") or {}).items() if isinstance(v, dict)}
            self.karencja_do = float(d.get("karencja_do") or 0.0)
        except (OSError, ValueError, TypeError, AttributeError):
            self.dane, self.karencja_do = {}, 0.0

    def zapisz(self):
        """Zapis atomowy (tmp + os.replace). Błąd tylko w logu: obrona nie może wywrócić bota."""
        try:
            self.plik.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.plik.with_name(self.plik.name + ".tmp")
            tmp.write_text(json.dumps({"wrogowie": self.dane, "karencja_do": self.karencja_do},
                                      ensure_ascii=False, indent=1))
            os.replace(tmp, self.plik)
            return True
        except OSError as e:
            self.log(f"PK: nie zapisałem {self.plik.name} ({e})")
            return False

    def dodaj(self, nick, powod, miejsce=None):
        """Dopisuje/odświeża wroga i zapisuje plik. -> True, gdy nick jest nowy."""
        t = self.czas()
        k = klucz_nicku(nick)
        nowy = k not in self.dane
        rec = self.dane.setdefault(k, {"nick": str(nick), "od": t, "ile": 0})
        rec.update(ost=t, powod=powod, miejsce=list(miejsce) if miejsce else rec.get("miejsce"))
        rec["ile"] = int(rec.get("ile", 0)) + 1
        self.zapisz()
        return nowy

    def widziany(self, nick):
        """Odnotowuje ponowne zobaczenie wroga (pamięć, bez zapisu na dysk co obieg)."""
        rec = self.dane.get(klucz_nicku(nick))
        if rec is not None:
            rec["ost"] = self.czas()

    def znany(self, nick, wazny_h=None):
        rec = self.dane.get(klucz_nicku(nick))
        if rec is None:
            return False
        if wazny_h and self.czas() - float(rec.get("ost", 0.0)) > wazny_h * 3600.0:
            return False
        return True

    def przedluz_karencje(self, minuty):
        """Karencja = `minuty` od TERAZ (każde zobaczenie wroga ją odsuwa). Zapis tylko, gdy realnie się wydłuża."""
        do = self.czas() + max(0.0, float(minuty)) * 60.0
        if do > self.karencja_do + 1.0:
            self.karencja_do = do
            self.zapisz()

    def karencja_aktywna(self):
        return self.czas() < self.karencja_do

    def karencja_pozostalo_s(self):
        return max(0.0, self.karencja_do - self.czas())


class DetektorPK:
    """Okno spadku HP + obcy gracz tuż obok + brak potwora przy nas = atak PK."""

    def __init__(self, konf, zegar=time.monotonic, log=print):
        self.konf, self.zegar, self.log = konf, zegar, log
        self.hist = []                      # [(czas, % HP)] z ostatnich PK_OKNO_S s

    def _k(self, nazwa, domyslna):
        return getattr(self.konf, nazwa, domyslna)

    def wlaczony(self):
        return bool(int(self._k("PK_OBRONA", 1)))

    def _okno(self):
        return float(self._k("PK_OKNO_S", self._k("UCIECZKA_PREDYKCJA_OKNO", 4.0)))

    def zapisz_hp(self, proc, teraz):
        """Dopisuje odczyt HP i zwraca spadek (pp): najwyższe HP w oknie minus obecne (>= 0)."""
        okno = self._okno()
        self.hist = [(t, p) for t, p in self.hist if teraz - t <= okno] + [(teraz, proc)]
        return max(0.0, max(p for _, p in self.hist) - proc)

    def spadek(self):
        if not self.hist:
            return 0.0
        return max(0.0, max(p for _, p in self.hist) - self.hist[-1][1])

    def obcy(self, lista, poz, wlasna, pomin=None):
        """Obcy gracze na piętrze postaci (bez nas i widm; `pomin(s)` = np. GM/CM, których nie traktujemy jak PK)."""
        wynik = []
        for s in lista:
            if not s.get("gracz") or jest_wlasna(s.get("nazwa"), wlasna) or s.get("z") != poz[2]:
                continue
            if s.get("hp", 100) <= 0:
                continue
            if pomin is not None and pomin(s):
                continue
            wynik.append(s)
        return wynik

    def wykryj_atak(self, lista, poz, wlasna, spadek, ogien=False, pomin=None):
        """-> {"gracze": [s...], "spadek": pp, "odl": najmniejsza odległość} albo None.
        Warunki: spadek >= PK_SPADEK_PP, obcy gracz w PK_ODL (albo PK_ODL_CZAR > 0), żaden żywy potwór w odl <= 1,
        postać nie stoi w polu ognia."""
        if not self.wlaczony() or ogien:
            return None
        if spadek < float(self._k("PK_SPADEK_PP", 8.0)):
            return None
        odl = max(int(self._k("PK_ODL", 1)), int(self._k("PK_ODL_CZAR", 0)))
        pozxy = (poz[0], poz[1])
        for s in lista:
            if not s.get("gracz") and s.get("z") == poz[2] and s.get("hp", 100) > 0 \
                    and _cheb((s["x"], s["y"]), pozxy) <= 1:
                return None             # potwór przy nas: to on bije (zwykła walka / UCIECZKA)
        blisko = [s for s in self.obcy(lista, poz, wlasna, pomin) if _cheb((s["x"], s["y"]), pozxy) <= odl]
        if not blisko:
            return None
        blisko.sort(key=lambda s: _cheb((s["x"], s["y"]), pozxy))
        return {"gracze": blisko, "spadek": spadek, "odl": _cheb((blisko[0]["x"], blisko[0]["y"]), pozxy)}

    def wrogowie_w_widoku(self, lista, poz, wlasna, wrogowie, pomin=None):
        """Znani wrogowie (lista Wrogowie, ważni PK_WROG_WAZNY_H godzin) widoczni teraz na piętrze postaci."""
        wazny = float(self._k("PK_WROG_WAZNY_H", 72.0))
        return [s for s in self.obcy(lista, poz, wlasna, pomin) if wrogowie.znany(s.get("nazwa"), wazny)]
