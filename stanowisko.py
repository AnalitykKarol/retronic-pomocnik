"""Tryb "stanowisko" (22.10, SPEC_stoj_runy_1022.md, F1): postać stoi w mieście poza PZ, je ham, robi runy (UH / HMM)
i obsługuje się przez istniejący serwis. Cały moduł jest nieaktywny, dopóki pokrętło STANOWISKO = 0 albo mapa nie ma wpisu
"stanowisko" (tryb.py zapisuje go do instancje/<id>/stanowisko_mapa.json obok na_zywo.json).

Cavebot wywołuje cztery haki (każdy tylko przy self.stanowisko is not None):
  * przed_ucieczka(g, poz, teraz, ucieczka)  - ucieczka HP i marsz do PZ (zamiast uciekaj po punktach trasy)
  * pk_reakcja(...)                          - zagrożenie PK (atak, wróg, czaszka): do PZ, bez pk_stan i bez wyprawy PK
  * krok(g, poz, teraz)                      - zamiast _idz_trasa: pole / powrót / PZ / serwis, zero logów okrążeń
  * ignoruj(s) / gracz_blokuje(dx, dy)       - filtr NPC i odległość obcego gracza dla UH

Stany: POLE (na polu), POWROT (wracamy na pole), PZ (marsz/postój w PZ), SERWIS (marsz do depo i refill).
Nie ma tu żadnego STOP z braku postępu ("naprawiaj, nie zatrzymuj"). STOP zapisuje wyłącznie przekazanie do refillu
(wyprawa._zapisz_stop, tylko gdy refill_auto zwrócił "czeka", czyli czekacz uruchomi bota ponownie)."""
import json
import os
import random
import time
from pathlib import Path

PLIK_MAPY = "stanowisko_mapa.json"
ZASIEG_X, ZASIEG_Y = 7, 5            # jak w cavebot.py (widok mapy)
DROGA_DO_PRZODU = (3, 5)            # jak w cavebot.py
NOWA_ZMIANA_PO_S = 1200.0           # przerwa dłuższa niż tyle = nowa zmiana (licznik 3 h od zera)
ZAPIS_STANU_S = 60.0
KOORD_S = 60.0
SERWIS_PONOW_S = 300.0              # w depo bez "czeka" z refillu: ponowienie decyzji co tyle
SERWIS_BRAK_DROGI_S = 180.0
PZ_MAX_BEZ_HP_S = 600.0             # tyle w PZ i HP >= HP_PZ + 10 wystarczy do wyjścia, gdy HP nie dochodzi do 90

DOMYSLNE = {
    "STANOWISKO_HP_PZ": 70, "STANOWISKO_PZ_KARENCJA_MIN": 30, "STANOWISKO_GRACZ_ODL": 0,
    "STANOWISKO_NPC_IGNORUJ": 1, "STANOWISKO_AKTYWNOSC_MAX_S": 0, "STANOWISKO_ROTACJA_MIN": 0,
    "STANOWISKO_ZMIANA_MAX_MIN": 180, "WROC_REFILL": 0,
}


def plik_mapy(katalog):
    return Path(katalog) / PLIK_MAPY


def wczytaj_mape(katalog):
    """-> słownik opisu stanowiska z mapy albo None (brak pliku, zły JSON, brak pól/depo)."""
    try:
        d = json.loads(plik_mapy(katalog).read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict) or not d.get("pola") or not d.get("depo"):
        return None
    try:
        d["pola"] = [tuple(int(v) for v in p[:3]) for p in d["pola"]]
        d["pz"] = [tuple(int(v) for v in p[:3]) for p in (d.get("pz") or [])]
        d["depo"] = tuple(int(v) for v in d["depo"][:3])
    except (TypeError, ValueError):
        return None
    d["miasto"] = str(d.get("miasto") or "?")
    d["pz_zmierzone"] = bool(d.get("pz_zmierzone"))
    if not d["pz"]:
        d["pz"] = [d["depo"]]
    return d


def nazwy_npc():
    """Imiona NPC z serwis_akcje (baza serwera + dopiski); brak modułu/pliku = pusty zbiór."""
    try:
        import serwis_akcje  # noqa: PLC0415
        return set(serwis_akcje.NPC_NAZWY)
    except Exception:  # noqa: BLE001
        return set()


def _powiadom(tytul, tresc, poziom, klucz):
    try:
        import powiadom  # noqa: PLC0415
        powiadom.powiadom(tytul, tresc, poziom, klucz)
    except Exception:  # noqa: BLE001
        pass


class Stanowisko:
    def __init__(self, cb, mapa, k=None, plik_stanu=None, koord=None, npc=None, wall=time.time, log=print):
        self.cb, self.m = cb, mapa
        self._k = k or (lambda n, d=0: DOMYSLNE.get(n, d))
        self.log = log
        self.wall = wall
        self.miasto = mapa["miasto"]
        self.pola = [tuple(p) for p in mapa["pola"]]
        self.pole = self.pola[0]
        self.pz = [tuple(p) for p in mapa["pz"]]
        self.depo = tuple(mapa["depo"])
        self.stan = "POLE"
        self.plik_stanu = Path(plik_stanu) if plik_stanu else None
        self.koord = koord
        self.npc = {n.casefold() for n in (npc if npc is not None else nazwy_npc())}
        self.pz_cel = None
        self.pz_powod = ""
        self.pz_od = 0.0
        self.pz_do = 0.0
        self.alarm_ost = float("-inf")
        self.brak_drogi_log = {}
        self.serwis = None                       # {"powod", "od", "dojechal", "ponow"}
        self.serwis_nast = float("-inf")
        self.koord_ost = float("-inf")
        self.koord_ok = True
        self.zajete_log = float("-inf")
        self.akt_ts = None
        self.akt_prog = None
        self.rot_ts = None
        self.stan_zapis = float("-inf")
        self.koniec_zmiany = False
        self.zmiana_start = self.wall()
        self._wczytaj_stan()
        if not self.m.get("pz_zmierzone"):
            self.log("Stanowisko: UWAGA, pola PZ niezmierzone (cele ucieczki to pola depo), pomiar Karola w mapy.json: "
                     "stanowisko.pz + pz_zmierzone")
        self.log(f"Stanowisko {self.miasto}: pole {self.pole}, PZ {self.pz}, depo {self.depo}, "
                 f"zmiana od {time.strftime('%H:%M', time.localtime(self.zmiana_start))}")

    # --- pokrętła i stan trwały ---

    def k(self, nazwa):
        return self._k(nazwa, DOMYSLNE.get(nazwa, 0))

    def _wczytaj_stan(self):
        if self.plik_stanu is None:
            return
        try:
            d = json.loads(self.plik_stanu.read_text())
        except (OSError, ValueError):
            return
        if not isinstance(d, dict):
            return
        teraz = self.wall()
        if teraz - float(d.get("ostatnio", 0)) <= NOWA_ZMIANA_PO_S and d.get("miasto") == self.miasto:
            self.zmiana_start = float(d.get("zmiana_start", teraz))
            self.serwis_nast = float("-inf")
        poprz = d.get("pole")
        if len(self.pola) > 1 and poprz and tuple(poprz) in self.pola:
            inne = [p for p in self.pola if p != tuple(poprz)]
            self.pole = random.choice(inne)          # rotacja między zmianami (spec pkt 6)

    def _zapisz_stan(self, teraz, wymus=False):
        if self.plik_stanu is None or (not wymus and teraz - self.stan_zapis < ZAPIS_STANU_S):
            return
        self.stan_zapis = teraz
        try:
            self.plik_stanu.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.plik_stanu.with_name(self.plik_stanu.name + f".tmp{os.getpid()}")
            tmp.write_text(json.dumps({"miasto": self.miasto, "zmiana_start": self.zmiana_start,
                                       "ostatnio": self.wall(), "pole": list(self.pole)}))
            os.replace(tmp, self.plik_stanu)
        except OSError:
            pass

    # --- filtr dla UH ---

    def ignoruj(self, s):
        """True: byt to NPC (nie blokuje rzutu runy). Gracz z czaszką/PK nigdy nie jest tu NPC."""
        if not int(self.k("STANOWISKO_NPC_IGNORUJ")):
            return False
        if s.get("czaszka") or s.get("skull") or s.get("pk"):
            return False
        return (s.get("nazwa") or "").casefold() in self.npc

    def gracz_blokuje(self, dx, dy):
        """STANOWISKO_GRACZ_ODL: 0 = każdy obcy w widoku blokuje (jak dziś); N > 0 = tylko bliżej niż N pól."""
        n = int(self.k("STANOWISKO_GRACZ_ODL"))
        return True if n <= 0 else max(dx, dy) < n

    # --- ruch ---

    def _idz(self, poz, cel):
        """Jeden obieg marszu do pola cel=(x,y,z): True = ruch, None = brak drogi."""
        cb = self.cb
        if poz[2] != cel[2]:
            return None
        prowadz = cb.droga(tuple(poz), cel[:2], dlugosc=0)
        if not prowadz:
            return None
        x, y = poz[0], poz[1]
        if cb.klik is not None:
            zasieg = random.randint(*DROGA_DO_PRZODU)
            j = 0
            for i, q in enumerate(prowadz[:zasieg]):
                if abs(q[0] - x) > ZASIEG_X - 1 or abs(q[1] - y) > ZASIEG_Y - 1:
                    break
                j = i
            cb.idz_do(prowadz[j][:2], tuple(poz), krok=prowadz[0][:2])
        else:
            cb.krok_do(prowadz[0])
        return True

    def _dlugosc(self, poz, cel):
        if poz[2] != cel[2]:
            return None
        if tuple(poz[:2]) == tuple(cel[:2]):
            return 0
        d = self.cb.droga(tuple(poz), cel[:2], dlugosc=0)
        return len(d) if d else None

    def _brak_drogi(self, co, poz, cel, teraz):
        if teraz - self.brak_drogi_log.get(co, float("-inf")) > 30.0:
            self.brak_drogi_log[co] = teraz
            self.log(f"Stanowisko: brak drogi {co} z {tuple(poz)} do {cel}, czekam i ponawiam (bez STOP).")
        self.cb.pauza(0.8, 1.6)

    @staticmethod
    def _tu(poz, cel):
        return tuple(poz[:3]) == tuple(cel[:3])

    # --- PZ ---

    def w_pz_drodze(self, poz):
        """Marsz do PZ trwa (stan PZ i jeszcze nie na polu PZ): potrzebne, by hak przerwał resztę obiegu."""
        return self.stan == "PZ" and not (self.pz_cel and self._tu(poz, self.pz_cel))

    def wejdz_pz(self, powod, teraz, nicki=(), g=None, poz=None, karencja_s=None):
        """Wejście w obronę: stan PZ z karencją (STANOWISKO_PZ_KARENCJA_MIN albo karencja_s); ponowne wejście ją przedłuża."""
        cb = self.cb
        kar = float(karencja_s) if karencja_s is not None else float(self.k("STANOWISKO_PZ_KARENCJA_MIN")) * 60.0
        nowy = self.stan != "PZ"
        self.pz_do = max(self.pz_do, teraz + kar) if not nowy else teraz + kar
        if nowy:
            self.stan = "PZ"
            self.pz_powod = powod
            self.pz_od = teraz
            self.pz_cel = None
            self.serwis = None
            cb.cel = None
            try:
                cb.zatrzymaj_klik(tuple(poz) if poz else cb.postac.pozycja())
            except Exception:  # noqa: BLE001
                pass
            hp = f"{g['proc']:.0f}" if g else "?"
            self.log(f"Stanowisko: do PZ ({powod}; wrogowie: {', '.join(nicki) or '-'}; HP {hp}%), "
                     f"karencja {kar / 60:.0f} min.")
        if nowy and powod in ("atak", "czaszka", "wróg w widoku", "karencja po restarcie") \
                and teraz - self.alarm_ost > 20.0:
            self.alarm_ost = teraz
            tekst = f"{powod}: {', '.join(nicki) or '?'}, uciekam do PZ"
            try:
                cb._alarm_pk("PK: " + tekst)
            except Exception as e:  # noqa: BLE001
                self.log(f"Stanowisko: alarm nie zadziałał ({e!r})")
            try:
                cb._pk_powiadom("PK: stanowisko, uciekam do PZ",
                                f"{tekst}. HP {g['proc']:.0f}%, poz {tuple(poz)}." if g and poz else tekst, "pk_atak")
            except Exception:  # noqa: BLE001
                pass

    def _wybierz_pz(self, poz, teraz):
        """Najbliższe (wg A*) pole PZ; None = żadne nieosiągalne."""
        if self.pz_cel is not None:
            return self.pz_cel
        najlepsze = None
        for c in self.pz:
            d = self._dlugosc(poz, c)
            if d is not None and (najlepsze is None or d < najlepsze[0]):
                najlepsze = (d, c)
        if najlepsze is None:
            return None
        self.pz_cel = najlepsze[1]
        self.log(f"Stanowisko: cel PZ {self.pz_cel} ({najlepsze[0]} kroków).")
        return self.pz_cel

    def _pz(self, g, poz, teraz):
        cb = self.cb
        cel = self._wybierz_pz(poz, teraz)
        if cel is None:
            self._brak_drogi("do PZ", poz, self.pz, teraz)
            return True
        if not self._tu(poz, cel):
            cb.ustaw_stan("STOJ", f"do PZ {cel} ({self.pz_powod})")
            if self._idz(poz, cel) is None:
                self.pz_cel = None
                self._brak_drogi("do PZ", poz, cel, teraz)
            return True
        cb.ustaw_stan("STOJ", f"w PZ ({self.pz_powod})")
        if self._pz_koniec(g, teraz):
            self._wyjdz_pz(teraz)
            return False
        cb.pauza(0.5, 1.0)
        return True

    def _pz_koniec(self, g, teraz):
        if self.koniec_zmiany or not self.koord_ok:
            return False
        if teraz < self.pz_do:
            return False
        hp = g["proc"]
        return hp >= 90 or (teraz - self.pz_od >= PZ_MAX_BEZ_HP_S and hp >= float(self.k("STANOWISKO_HP_PZ")) + 10)

    def _wyjdz_pz(self, teraz):
        self.log(f"Stanowisko: koniec obrony ({self.pz_powod}, w PZ {teraz - self.pz_od:.0f} s), wracam na pole {self.pole}.")
        self.stan = "POWROT"
        self.pz_cel = None
        self.pz_powod = ""

    # --- haki cavebota ---

    def przed_ucieczka(self, g, poz, teraz, ucieczka):
        """Hak A (przed `if self.ucieczka`). True = obieg zużyty."""
        cb = self.cb
        if self.stan == "SERWIS" and not ucieczka and g["proc"] >= float(self.k("STANOWISKO_HP_PZ")):
            return False                          # serwis jest w drodze do depo (PZ): idzie przez krok()
        if ucieczka:
            if self.stan != "PZ":
                self.wejdz_pz("HP", teraz, g=g, poz=poz, karencja_s=0.0)
            if not self._tu(poz, self._wybierz_pz(poz, teraz) or ()):
                return self._pz(g, poz, teraz)
            cb.ustaw_stan("UCIECZKA", f"w PZ, HP {g['proc']:.0f}%")
            if cb.jedzenie_potrzebne(g, teraz, poz):
                cb.zjedz(teraz, g)
                return True
            cb.pauza(0.5, 1.0)
            return True
        if self.stan != "PZ" and g["proc"] < float(self.k("STANOWISKO_HP_PZ")):
            if not self._potwor_blisko(poz):
                self.wejdz_pz("HP niskie", teraz, g=g, poz=poz, karencja_s=0.0)
        if self.w_pz_drodze(poz):
            return self._pz(g, poz, teraz)
        return False

    def _potwor_blisko(self, poz, odl=3):
        """Żywy nie-gracz (poza NPC) w odl polach: wtedy niskie HP obsługuje zwykła walka/ucieczka, nie sam marsz do PZ."""
        for s in getattr(self.cb, "ostatnie_stwory", None) or ():
            if s.get("gracz") or s.get("z") != poz[2] or s.get("hp", 100) <= 0 or self.ignoruj(s):
                continue
            if max(abs(s["x"] - poz[0]), abs(s["y"] - poz[1])) <= odl:
                return True
        return False

    def pk_reakcja(self, g, poz, teraz, atak, widoczni, czaszki, nicki, wr=None):
        """Zagrożenie PK (atak z danych, wróg z listy w widoku, groźna czaszka): do PZ. Nie ustawia pk_stan."""
        powod = "atak" if atak else ("czaszka" if czaszki else "wróg w widoku")
        self.wejdz_pz(powod, teraz, nicki, g, poz)
        return self._pz(g, poz, teraz)

    def start_karencja(self, g, poz, teraz, pozostalo_s):
        """Restart w trwającej karencji (wrogowie.json): od razu do PZ."""
        self.wejdz_pz("karencja po restarcie", teraz, [], g, poz, karencja_s=pozostalo_s)
        return self._pz(g, poz, teraz)

    # --- Koordynator, zmiana ---

    def _koordynator(self, teraz):
        if self.koord is None or teraz - self.koord_ost < KOORD_S:
            return
        self.koord_ost = teraz
        try:
            import miejsca_koord  # noqa: PLC0415
            klucz = miejsca_koord.klucz_stanowiska(self.miasto)
            ok = self.koord.rezerwuj(klucz, self.pole, 0)
        except Exception as e:  # noqa: BLE001
            self.log(f"Stanowisko: koordynator niedostępny ({e!r}), stoję dalej")
            return
        if ok != self.koord_ok:
            self.koord_ok = ok
            if ok:
                self.log(f"Stanowisko: miasto {self.miasto} wolne, wracam na pole.")
            else:
                self.log(f"Stanowisko: miasto {self.miasto} zajęte przez inną postać (klucz {klucz}), "
                         "czekam w PZ i ponawiam (bez STOP).")
                _powiadom("Stanowisko: miasto zajęte", f"Inna postać stoi w {self.miasto}, ta czeka w PZ.",
                          "normal", "stanowisko_zajete")

    def zamknij(self):
        """Zwolnienie rezerwacji miasta (wyjście procesu)."""
        if self.koord is not None:
            try:
                import miejsca_koord  # noqa: PLC0415
                self.koord.zwolnij(miejsca_koord.klucz_stanowiska(self.miasto))
            except Exception:  # noqa: BLE001
                pass

    def _zmiana(self, teraz):
        maks = float(self.k("STANOWISKO_ZMIANA_MAX_MIN"))
        if maks <= 0 or self.koniec_zmiany:
            return
        if self.wall() - self.zmiana_start >= maks * 60.0:
            self.koniec_zmiany = True
            self.log(f"Stanowisko: koniec zmiany ({maks:.0f} min stania), zostaję w PZ do wylogowania z grafiku.")
            _powiadom("Stanowisko: koniec zmiany", f"{maks:.0f} min stania, postać czeka w PZ.", "normal",
                      "stanowisko_zmiana")

    # --- serwis ---

    def zlec_serwis(self, powod, dane, teraz):
        """Wywoływane z wyprawa._start_wyprawa zamiast wyprawy. Idempotentne; marsz do depo i refill robi krok()."""
        if self.stan == "SERWIS" or self.stan == "PZ" or self.koniec_zmiany or teraz < self.serwis_nast:
            return False
        self.stan = "SERWIS"
        self.serwis = {"powod": powod, "od": teraz, "dojechal": None, "ponow": float("-inf"), "stop": False}
        self.log(f"Stanowisko: serwis ({powod}), idę do depo {self.depo}.")
        return True

    def _serwis(self, g, poz, teraz):
        cb = self.cb
        s = self.serwis or {}
        cb.ustaw_stan("STOJ", f"serwis w depo {self.depo} ({s.get('powod', '?')})")
        if not self._tu(poz, self.depo):
            if self._idz(poz, self.depo) is None:
                self._brak_drogi("do depo", poz, self.depo, teraz)
                if teraz - s.get("od", teraz) > SERWIS_BRAK_DROGI_S:
                    self.log("Stanowisko: depo nieosiągalne, rezygnuję z serwisu na 5 min.")
                    self._koniec_serwisu(teraz)
            return True
        if teraz < s.get("ponow", float("-inf")):
            cb.pauza(0.6, 1.2)
            return True
        s["ponow"] = teraz + SERWIS_PONOW_S
        w = getattr(cb, "wyprawa", None)
        refill = None
        if w is not None and int(self.k("WROC_REFILL")):
            refill = w._auto_refill(poz)
        if refill is not None and refill[0] == "czeka":
            self.log(f"Stanowisko: w depo {tuple(poz)}, oddaję bota refillowi ({refill[1]}).")
            w._powiadom("Stanowisko: serwis w depo", f"Bot w depo {tuple(poz)}, refill startuje sam ({s.get('powod')}).",
                        "critical", "wyprawa_depo")
            w._zapisz_stop(f"stanowisko: serwis w depo {tuple(poz)}")
            w._auto_refill_start(refill)
            s["stop"] = True
            return True
        powod = refill[1] if refill is not None else "WROC_REFILL=0 albo błąd decyzji"
        if s.get("log_powod") != powod:
            s["log_powod"] = powod
            self.log(f"Stanowisko: w depo, refill niemożliwy teraz ({powod}); stoję w PZ i ponawiam co "
                     f"{SERWIS_PONOW_S:.0f} s (bez STOP).")
            _powiadom("Stanowisko: serwis czeka", f"Refill pominięty: {powod}. Postać stoi w depo.", "normal",
                      "stanowisko_serwis")
        cb.pauza(0.6, 1.2)
        return True

    def _koniec_serwisu(self, teraz):
        self.serwis = None
        self.serwis_nast = teraz + SERWIS_PONOW_S
        self.stan = "POWROT"

    # --- Hak B: zamiast _idz_trasa ---

    def krok(self, g, poz, teraz):
        cb = self.cb
        self._koordynator(teraz)
        self._zmiana(teraz)
        self._zapisz_stan(teraz)
        if (self.koniec_zmiany or not self.koord_ok) and self.stan != "PZ":
            self.wejdz_pz("zmiana zakończona" if self.koniec_zmiany else "miasto zajęte", teraz, g=g, poz=poz,
                          karencja_s=0.0)
        if self.stan == "PZ":
            if self._pz(g, poz, teraz):
                return True
            # _pz zwróciło False: obrona skończona, wracamy na pole w tym samym obiegu
        if self.stan == "SERWIS":
            return self._serwis(g, poz, teraz)
        pole = self.pole
        if not self._tu(poz, pole):
            self.stan = "POWROT"
            cb.ustaw_stan("STOJ", f"wracam na pole {pole}")
            if self._idz(poz, pole) is None:
                self._brak_drogi("na pole", poz, pole, teraz)
            return True
        if self.stan != "POLE":
            self.log(f"Stanowisko: na polu {pole}.")
        self.stan = "POLE"
        cb.ustaw_stan("STOJ", f"na polu {pole}")
        if self._rotacja(poz, teraz) or self._aktywnosc(poz, teraz):
            return True
        cb.pauza(0.3, 0.8)
        return True

    def _rotacja(self, poz, teraz):
        """STANOWISKO_ROTACJA_MIN > 0: co tyle minut inne pole z `pola` (gdy poza rzutem i bez obcych w widoku)."""
        co = float(self.k("STANOWISKO_ROTACJA_MIN"))
        if co <= 0 or len(self.pola) < 2:
            return False
        if self.rot_ts is None:
            self.rot_ts = teraz
            return False
        if teraz - self.rot_ts < co * 60.0 or teraz - getattr(self.cb, "aktywnosc_ts", 0) < 8.0:
            return False
        try:
            if self.cb.inni_gracze(self.cb.ostatnie_stwory or [], poz):
                return False
        except Exception:  # noqa: BLE001
            return False
        self.rot_ts = teraz
        nowe = random.choice([p for p in self.pola if p != self.pole])
        self.log(f"Stanowisko: rotacja pola {self.pole} -> {nowe}.")
        self.pole = nowe
        self._zapisz_stan(teraz, wymus=True)
        return True

    def _aktywnosc(self, poz, teraz):
        """STANOWISKO_AKTYWNOSC_MAX_S > 0: bez żadnej akcji tyle (z losowym zapasem) = jeden krok w bok; powrót robi krok()."""
        maks = float(self.k("STANOWISKO_AKTYWNOSC_MAX_S"))
        if maks <= 0:
            self.akt_prog = None
            return False
        cb = self.cb
        ostatnia = max(float(getattr(cb, "aktywnosc_ts", 0) or 0), float(getattr(cb, "ruch_czas", 0) or 0),
                       self.akt_ts or 0.0)
        if self.akt_prog is None:
            self.akt_prog = random.uniform(0.55, 0.95) * maks
        if ostatnia <= 0:
            self.akt_ts = teraz
            return False
        if teraz - ostatnia < self.akt_prog:
            return False
        kier = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        random.shuffle(kier)
        for dx, dy in kier:
            cel = (poz[0] + dx, poz[1] + dy)
            d = cb.droga(tuple(poz), cel, dlugosc=0)
            if d and len(d) == 1:
                self.log(f"Stanowisko: bez akcji od {teraz - ostatnia:.0f} s, krok w bok {cel} i z powrotem.")
                cb.krok_do(d[0])
                self.akt_ts = teraz
                self.akt_prog = None
                return True
        self.akt_ts = teraz
        return False
