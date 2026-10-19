"""Watchdog "ślepoty" (19.10): bot po dłuższej pracy przestaje widzieć potwory (lista stworów z pamięci gry ma tylko
postać), choć na ekranie stoi tłum. Trzy razy w godzinę (21:32, 21:39, ...); restart `mozg.py` pomagał na kilka minut.
Przyczyna niepotwierdzona (hipoteza: zła kopia listy w pamięci klienta, patrz STAN.md i pamięć "retronic-slepota").

Co robi:
  * Detektor (czysta logika, testy/test_slepota.py): bot polował (exp rósł od startu procesu), od `diag_s` sekund exp
    stoi, żaden potwór nie był widoczny, a stan to marsz/walka/loot. Wtedy pierwszy raz zrzuca diagnostykę
    (`zrzuc`): surowa lista ze strażnika, to, co widzi cavebot, ogon rdzen-skan.log, zrzut ekranu. Max raz na DIAG_PRZERWA_S.
  * Po `restart_s` sekundach takiej ślepoty prosi o restart procesu (os.execv, ten sam pid i argumenty, patrz mozg.py).
    Restart najwyżej raz na RESTART_PRZERWA_S; potem tylko diagnostyka.
Pokrętła: SLEPOTA_DIAG_S (0 = wyłączone), SLEPOTA_RESTART_S (0 = bez restartu) w cavebot.py / na_zywo.json.
"""
import json
import time
from pathlib import Path

STANY_POLOWANIA = ("IDZ", "WALKA", "LOOT", "POGON")   # tylko w tych stanach brak potworów + brak expa to podejrzane
DIAG_PRZERWA_S = 600.0
RESTART_PRZERWA_S = 900.0


class Detektor:
    """probka(t, exp, stan, n_potworow) co kilka sekund; zwraca None, "diag" albo "restart"."""

    def __init__(self, diag_s=120.0, restart_s=240.0):
        self.diag_s, self.restart_s = diag_s, restart_s
        self.exp = None
        self.t_exp = None          # kiedy exp ostatnio się zmienił (albo okno zostało zresetowane)
        self.t_potwor = None       # kiedy ostatnio widziano potwora
        self.polowal = False       # exp urósł co najmniej raz w tym procesie (był na łowisku)
        self.ost_diag = float("-inf")
        self.ost_restart = float("-inf")

    def ustaw(self, diag_s, restart_s):
        self.diag_s, self.restart_s = diag_s, restart_s

    def reset_okna(self, t):
        self.t_exp = self.t_potwor = t

    def probka(self, t, exp, stan, n_potworow):
        if exp is None:
            return None
        if self.exp is None:
            self.exp = exp
            self.reset_okna(t)
            return None
        if exp != self.exp:
            if exp > self.exp:
                self.polowal = True
            self.exp = exp
            self.reset_okna(t)
            return None
        if n_potworow:
            self.t_potwor = t
        if str(stan) not in STANY_POLOWANIA:
            self.reset_okna(t)     # wypad, przerwa, wpadnięcie, UH...: długie bez expa to norma
            return None
        if not self.polowal or not self.diag_s:
            return None
        ile = min(t - self.t_exp, t - self.t_potwor)
        if self.restart_s and ile >= self.restart_s and t - self.ost_restart >= RESTART_PRZERWA_S:
            self.ost_restart = t
            self.ost_diag = t
            return "restart"
        if ile >= self.diag_s and t - self.ost_diag >= DIAG_PRZERWA_S:
            self.ost_diag = t
            return "diag"
        return None


def _tail(plik, n):
    try:
        with open(plik, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 16000))
            return f.read().decode("utf-8", "replace").splitlines()[-n:]
    except OSError:
        return []


def _skrot(lista, maks=40):
    """Lista stworów do JSON: bez ciężkich pól, max `maks` wpisów."""
    wynik = []
    for s in (lista or [])[:maks]:
        wynik.append({k: s.get(k) for k in ("id", "nazwa", "x", "y", "z", "hp", "gracz", "adres", "kopie", "widmo", "ramka")
                      if k in s})
    return wynik


def zrzuc(katalog, powod, cb, ile_s, log=print):
    """Zapisuje logi/slepota/<czas>.json i .png. Nigdy nie rzuca; zwraca ścieżkę json albo None."""
    try:
        import bot  # noqa: PLC0415
        katalog = Path(katalog)
        katalog.mkdir(parents=True, exist_ok=True)
        nazwa = time.strftime("%Y%m%d-%H%M%S")
        d = {"czas": nazwa, "powod": powod, "ile_s": round(ile_s), "stan": getattr(cb, "stan", None),
             "exp": getattr(cb, "exp_teraz", None), "idx": getattr(cb, "idx", None)}
        surowa_cb = getattr(cb, "stwory_surowe", None)
        d["cb_stwory"] = {"n": len(surowa_cb or []), "poza_graczem": sum(1 for s in surowa_cb or [] if not s.get("gracz")),
                          "wpisy": _skrot(surowa_cb)}
        for klucz, zad, pole in (("straznik_stwory", {"cmd": "stwory"}, "stwory"), ("straznik_gracz", {"cmd": "gracz"}, "gracz"),
                                 ("straznik_pozycja", {"cmd": "pozycja"}, "pozycja")):
            try:
                odp = bot._zapytaj_surowe(zad)[pole]
                d[klucz] = ({"n": len(odp), "poza_graczem": sum(1 for s in odp if not s.get("gracz")), "wpisy": _skrot(odp)}
                            if isinstance(odp, list) else odp)
            except Exception as e:      # noqa: BLE001
                d[klucz] = f"błąd: {e!r}"
        d["wlasny_wpis"] = {k: v for k, v in (bot._wlasny.get("wpis") or {}).items() if k in ("id", "adres", "x", "y", "z")}
        d["rdzen_skan_ogon"] = _tail(Path(__file__).resolve().parent / "logi" / "rdzen-skan.log", 25)
        try:
            import ekran  # noqa: PLC0415
            import ogien  # noqa: PLC0415
            obraz = ogien.zrzut_ppm(ekran.SESJA.read_text().strip())
            obraz.save(katalog / f"{nazwa}.png")
            d["zrzut"] = f"{nazwa}.png"
        except Exception as e:          # noqa: BLE001
            d["zrzut"] = f"błąd: {e!r}"
        plik = katalog / f"{nazwa}.json"
        plik.write_text(json.dumps(d, ensure_ascii=False, indent=1, default=str))
        log(f"ŚLEPOTA: {powod}, od {ile_s:.0f} s bez expa i potworów; diagnostyka w {plik.name}")
        return plik
    except Exception as e:              # noqa: BLE001
        try:
            log(f"ŚLEPOTA: diagnostyka nieudana: {e!r}")
        except Exception:               # noqa: BLE001
            pass
        return None
