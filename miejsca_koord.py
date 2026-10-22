"""Koordynator miejsc między instancjami: instancja rezerwuje miejsce (z trasy/miejsca_troll.json) i nikt inny
go nie bierze, dopóki rezerwacja żyje.

Stan wspólny: pomocnik/instancje/_wspolne/zajete.json (słownik klucz_miejsca -> rezerwacja), dostęp pod flock
na zajete.json.lock, zapis atomowy (tmp + rename). Rezerwacja wygasa po ttl_s bez odświeżenia albo gdy proces
właściciela nie żyje (os.kill(pid, 0)), więc zabity bot nie blokuje miejsca.

Konflikt: ten sam klucz, albo (to samo piętro i odległość Chebysheva <= max(promien_a, promien_b)), gdy podano
pozycje; promien 0 = tylko ten sam klucz.

Integracja z patrolem (cavebot.py) jest opcjonalna i domyślnie wyłączona: pokrętło PATROL_KOORD = 0.
Moduł nie importuje cavebota i nie ma efektów ubocznych przy imporcie.
"""
import contextlib
import fcntl
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import instancja  # noqa: E402

TTL_S = 900.0
LOCK_TIMEOUT_S = 2.0


def klucz_miejsca(m):
    """Stały klucz miejsca z wpisu pliku miejsc: nazwa, a gdy jej brak, 'm<id>'."""
    return str(m.get("nazwa") or f"m{m['id']}")


def klucz_stanowiska(miasto):
    """Klucz rezerwacji miasta dla trybu stanowisko (stanowisko.py): jedna postać stoi w jednym mieście naraz."""
    return f"stoj_{str(miasto).strip().casefold()}"


def _pid_zyje(pid):
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def konflikt(klucz, poz, promien, k2, r2):
    """Czy miejsce (klucz, poz=(x,y,z) albo None, promien) koliduje z rezerwacją k2/r2."""
    if klucz == k2:
        return True
    if poz is None or r2.get("x") is None:
        return False
    if poz[2] != r2.get("z"):
        return False
    return max(abs(poz[0] - r2["x"]), abs(poz[1] - r2["y"])) <= max(int(promien or 0), int(r2.get("promien") or 0))


class BrakBlokady(Exception):
    pass


class Koordynator:
    def __init__(self, plik=None, id_instancji=None, pid=None, ttl_s=TTL_S, max_miejsc=1,
                 zegar=time.time, zyje=_pid_zyje):
        self.plik = Path(plik) if plik else instancja.S.zajete
        self.id = id_instancji if id_instancji is not None else (instancja.ID or "domyslna")
        self.pid = pid if pid is not None else os.getpid()
        self.ttl_s, self.max_miejsc = ttl_s, max_miejsc
        self.zegar, self.zyje = zegar, zyje

    # --- niski poziom: blokada i plik ----------------------------------------------------------
    @contextlib.contextmanager
    def _blokada(self):
        self.plik.parent.mkdir(parents=True, exist_ok=True)
        f = open(self.plik.with_name(self.plik.name + ".lock"), "a")
        try:
            koniec = time.monotonic() + LOCK_TIMEOUT_S
            while True:
                try:
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic() >= koniec:
                        raise BrakBlokady(str(self.plik))
                    time.sleep(0.02)
            yield
        finally:
            f.close()          # zamknięcie zwalnia flock

    def _wczytaj(self):
        try:
            d = json.loads(self.plik.read_text())
        except (OSError, ValueError):
            return {}
        return {k: v for k, v in d.items() if isinstance(v, dict) and "instancja" in v} if isinstance(d, dict) else {}

    def _zapisz(self, dane):
        tmp = self.plik.with_name(f"{self.plik.name}.tmp{os.getpid()}")
        tmp.write_text(json.dumps(dane, ensure_ascii=False, indent=1, sort_keys=True))
        os.replace(tmp, self.plik)

    def _zywa(self, r, teraz):
        if r.get("do", 0) < teraz:
            return False
        if r.get("instancja") == self.id and r.get("pid") == self.pid:
            return True
        return bool(self.zyje(r.get("pid")))

    def _aktywne(self, dane, teraz):
        return {k: r for k, r in dane.items() if self._zywa(r, teraz)}

    _konflikt = staticmethod(konflikt)

    # --- API -----------------------------------------------------------------------------------
    def zajete(self, wlacznie_moje=False):
        """Aktywne rezerwacje (klucz -> wpis); domyślnie tylko cudze."""
        with self._blokada():
            akt = self._aktywne(self._wczytaj(), self.zegar())
        return {k: r for k, r in akt.items() if wlacznie_moje or r["instancja"] != self.id}

    def czy_wolne(self, klucz, poz=None, promien=0):
        """Czy miejsce nie koliduje z rezerwacją innej instancji (moje rezerwacje nie przeszkadzają)."""
        return not any(self._konflikt(klucz, poz, promien, k, r) for k, r in self.zajete().items())

    def rezerwuj(self, klucz, poz=None, promien=0):
        """Rezerwuje miejsce atomowo. True = nasze (też gdy już było nasze: odświeża); False = zajęte przez inną
        instancję. Rezerwacje własne ponad max_miejsc (najstarsze) są zwalniane."""
        with self._blokada():
            teraz = self.zegar()
            dane = self._aktywne(self._wczytaj(), teraz)
            for k, r in dane.items():
                if r["instancja"] != self.id and self._konflikt(klucz, poz, promien, k, r):
                    self._zapisz(dane)           # przy okazji sprzątanie wygasłych
                    return False
            dane[klucz] = {"instancja": self.id, "pid": self.pid, "t": teraz, "do": teraz + self.ttl_s,
                           "x": poz[0] if poz else None, "y": poz[1] if poz else None, "z": poz[2] if poz else None,
                           "promien": int(promien or 0)}
            moje = sorted((k for k, r in dane.items() if r["instancja"] == self.id and r.get("pid") == self.pid),
                          key=lambda k: dane[k]["t"])
            for k in [k for k in moje if k != klucz][:max(0, len(moje) - self.max_miejsc)]:
                del dane[k]
            self._zapisz(dane)
            return True

    def odswiez(self):
        """Przedłuża wszystkie moje rezerwacje (heartbeat). Zwraca ich liczbę."""
        with self._blokada():
            teraz = self.zegar()
            dane = self._aktywne(self._wczytaj(), teraz)
            n = 0
            for r in dane.values():
                if r["instancja"] == self.id and r.get("pid") == self.pid:
                    r["do"] = teraz + self.ttl_s
                    n += 1
            self._zapisz(dane)
            return n

    def zwolnij(self, klucz=None):
        """Zwalnia miejsce (klucz) albo wszystkie moje (None). Zwraca ile zwolniono."""
        with self._blokada():
            dane = self._aktywne(self._wczytaj(), self.zegar())
            cele = [k for k, r in dane.items() if r["instancja"] == self.id and r.get("pid") == self.pid
                    and (klucz is None or k == klucz)]
            for k in cele:
                del dane[k]
            self._zapisz(dane)
            return len(cele)


    def zwolnij_instancje(self):
        """Zwalnia WSZYSTKIE rezerwacje tej instancji (bez względu na pid): sprzątanie po zabitym bocie."""
        with self._blokada():
            dane = self._aktywne(self._wczytaj(), self.zegar())
            cele = [k for k, r in dane.items() if r["instancja"] == self.id]
            for k in cele:
                del dane[k]
            self._zapisz(dane)
            return len(cele)


def main(argv=None):
    """python3 -I miejsca_koord.py [lista|zwolnij-instancje]: podgląd i ręczne sprzątanie rezerwacji tej instancji (RETRONIC_ID)."""
    a = list(sys.argv[1:] if argv is None else argv)
    k = Koordynator()
    if not a or a[0] == "lista":
        z = k.zajete(wlacznie_moje=True)
        for nazwa, r in sorted(z.items()):
            print(f"{nazwa}\t{r['instancja']}\tpid {r['pid']}\tjeszcze {max(0, r['do'] - time.time()):.0f} s")
        if not z:
            print("(brak rezerwacji)")
        return 0
    if a[0] == "zwolnij-instancje":
        print(f"zwolniono {k.zwolnij_instancje()}")
        return 0
    print("użycie: miejsca_koord.py [lista|zwolnij-instancje]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
