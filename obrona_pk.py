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
KARENCJA_ZAPIS_S = 60.0


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
        self._karencja_zapis = 0.0      # karencja_do zapisana na dysku (zapis tylko przy przedłużeniu o >= KARENCJA_ZAPIS_S)
        self._mtime = None              # mtime_ns pliku po ostatnim odczycie/zapisie (zmiana z zewnątrz = ponowny odczyt)
        self.wczytaj()

    def wczytaj(self):
        try:
            d = json.loads(self.plik.read_text())
            self.dane = {klucz_nicku(k): v for k, v in (d.get("wrogowie") or {}).items() if isinstance(v, dict)}
            self.karencja_do = float(d.get("karencja_do") or 0.0)
        except (OSError, ValueError, TypeError, AttributeError):
            self.dane, self.karencja_do = {}, 0.0
        self._karencja_zapis = self.karencja_do
        self._mtime = self._stat()

    def _stat(self):
        try:
            return self.plik.stat().st_mtime_ns
        except OSError:
            return None

    def odswiez(self):
        """Ręczna zmiana pliku (CLI --usun) trafia do działającego bota; inaczej następny zapis by ją cofnął."""
        if self._stat() != self._mtime:
            self.wczytaj()
            return True
        return False

    def zapisz(self):
        """Zapis atomowy (tmp + os.replace). Błąd tylko w logu: obrona nie może wywrócić bota."""
        try:
            self.plik.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.plik.with_name(self.plik.name + ".tmp")
            tmp.write_text(json.dumps({"wrogowie": self.dane, "karencja_do": self.karencja_do},
                                      ensure_ascii=False, indent=1))
            os.replace(tmp, self.plik)
            self._karencja_zapis = self.karencja_do
            self._mtime = self._stat()
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
        """Karencja = `minuty` od TERAZ (każde zobaczenie wroga ją odsuwa). W pamięci zawsze, na dysk tylko przy
        przedłużeniu o >= KARENCJA_ZAPIS_S względem zapisanej (wróg w widoku nie piszy pliku co obieg)."""
        do = self.czas() + max(0.0, float(minuty)) * 60.0
        if do > self.karencja_do:
            self.karencja_do = do
        if self.karencja_do - self._karencja_zapis >= KARENCJA_ZAPIS_S:
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
        self.mob_ost = float("-inf")        # kiedy ostatnio żywy potwór stał w odl <= 1 (cios mógł być jego)

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

    def zapamietaj_moby(self, lista, poz, teraz):
        """Odnotowuje czas, gdy żywy potwór stoi przy nas (odl <= 1). Wołane też z listy poprzedniego obiegu,
        żeby wiedzieć o potworze, który zginął/odszedł tuż przed pojawieniem się przechodnia."""
        pozxy = (poz[0], poz[1])
        if any(not s.get("gracz") and s.get("z") == poz[2] and s.get("hp", 100) > 0
               and _cheb((s["x"], s["y"]), pozxy) <= 1 for s in lista or ()):
            self.mob_ost = teraz
            return True
        return False

    def wykryj_atak(self, lista, poz, wlasna, spadek, ogien=False, pomin=None, teraz=None):
        """-> {"gracze": [s...], "spadek": pp, "odl": najmniejsza odległość} albo None. `gracze` = tylko najbliżsi
        (prawdopodobny napastnik), nie każdy gracz w PK_ODL.
        Warunki: spadek >= PK_SPADEK_PP, obcy gracz w PK_ODL (albo PK_ODL_CZAR > 0), żaden żywy potwór w odl <= 1
        TERAZ ani w ostatnich PK_OKNO_S s (potwór mógł zadać cios i zginąć), postać nie stoi w polu ognia."""
        if not self.wlaczony() or ogien:
            return None
        t = self.zegar() if teraz is None else teraz
        przy_nas = self.zapamietaj_moby(lista, poz, t)
        if spadek < float(self._k("PK_SPADEK_PP", 8.0)):
            return None
        if przy_nas or t - self.mob_ost <= self._okno():
            return None                 # potwór przy nas teraz albo przed chwilą: to on bił (zwykła walka / UCIECZKA)
        odl = max(int(self._k("PK_ODL", 1)), int(self._k("PK_ODL_CZAR", 0)))
        pozxy = (poz[0], poz[1])
        blisko = [s for s in self.obcy(lista, poz, wlasna, pomin) if _cheb((s["x"], s["y"]), pozxy) <= odl]
        if not blisko:
            return None
        d0 = min(_cheb((s["x"], s["y"]), pozxy) for s in blisko)
        najblizsi = [s for s in blisko if _cheb((s["x"], s["y"]), pozxy) == d0]
        return {"gracze": najblizsi, "spadek": spadek, "odl": d0}

    def wrogowie_w_widoku(self, lista, poz, wlasna, wrogowie, pomin=None):
        """Znani wrogowie (lista Wrogowie, ważni PK_WROG_WAZNY_H godzin) widoczni teraz na piętrze postaci."""
        wazny = float(self._k("PK_WROG_WAZNY_H", 72.0))
        return [s for s in self.obcy(lista, poz, wlasna, pomin) if wrogowie.znany(s.get("nazwa"), wazny)]


def main(argv=None):
    """CLI do listy wrogów: `python3 obrona_pk.py --lista` / `--usun NICK` / `--zeruj-karencje` (opcjonalnie --plik P).
    Działający bot odczytuje zmianę pliku sam (Wrogowie.odswiez)."""
    import argparse  # noqa: PLC0415
    p = argparse.ArgumentParser(description="Lista wrogów PK (wrogowie.json)")
    p.add_argument("--plik", help="inny plik niż stan instancji")
    p.add_argument("--lista", action="store_true", help="wypisz wrogów i karencję")
    p.add_argument("--usun", metavar="NICK", help="usuń nick z listy wrogów")
    p.add_argument("--zeruj-karencje", action="store_true", help="skasuj karencję powrotu na spot")
    a = p.parse_args(argv)
    w = Wrogowie(a.plik)
    if a.usun:
        k = klucz_nicku(a.usun)
        if k in w.dane:
            del w.dane[k]
            w.zapisz()
            print(f"usunięto: {a.usun}")
        else:
            print(f"brak na liście: {a.usun}")
            return 1
    if a.zeruj_karencje:
        w.karencja_do = 0.0
        w.zapisz()
        print("karencja wyzerowana")
    if a.lista or not (a.usun or a.zeruj_karencje):
        t = w.czas()
        for k, v in sorted(w.dane.items()):
            print(f"{v.get('nick', k)}: ost {(t - float(v.get('ost', 0))) / 3600:.1f} h temu, ataków {v.get('ile', 0)}, "
                  f"{v.get('powod', '')}, miejsce {v.get('miejsce')}")
        print(f"karencja: {w.karencja_pozostalo_s() / 60:.0f} min" if w.karencja_aktywna() else "karencja: brak")
        if not w.dane:
            print("(lista pusta)")
    return 0


if __name__ == "__main__":
    import sys  # noqa: PLC0415
    sys.exit(main())
