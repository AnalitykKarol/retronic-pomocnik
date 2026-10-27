#!/usr/bin/env python3
"""Auto-refill po powrocie do depo (20.10, pokrętło WROC_REFILL=1).

Bot, który dochodzi do depo w „Wróć do miasta” (wroc.sh) albo w wyprawie tylko-do-depo, zapisuje STOP i staje. Z tego STOP-u
wyprawa.py (`_zakoncz_depo`) woła `zlec()`: gdy miasto ma plan serwisu (trasy/serwis_<miasto>.json obsługiwane przez serwis.py)
i nic innego nie trwa, rusza odłączony „czekacz” (`refill_auto.py czekaj`). Czekacz czeka, aż proces bota tej instancji zniknie
(refill.sh odmawia przy działającym bocie), sprawdza jeszcze raz STOP_RECZNY / serwis, zwalnia wejście i wykonuje
`refill.sh --tlo` (bank, depo, jedzenie, backpack, blanki, wyjście, potem start bota na spot; log `refill.log`; miasto z pozycji
postaci, kroków, których miasto nie ma, np. banku w Thais, serwis pomija).

Wyjątek (23.10, Karol): postać z flagą `zostan_w_depo` w plan_postaci.json (invincible, dawajkesh, wydra, gebelish) zostaje w depo bez
auto-refillu, nawet gdy WROC_REFILL=1 (tryby runy/uh przywracają go przy każdym starcie bota).
24.10 (Karol: „2 bp UH-ów, potem depo i wylogowanie”): `zostan_w_depo_po_refillach: N` uzbraja tę flagę dopiero po N refillach (licznik
`refille.json` dopisuje czekacz po przyjęciu zlecenia przez refill.sh --tlo, TYLKO po wyprawie z powodem `blanki`; zostan_depo.py).
24.10 (Karol ~10:00, każda postać): wyprawa do depo WYŁĄCZNIE z powodu `cap` (wyprawa_stan.json `depo_start_powody` == ["cap"]) kończy się refillem
`REFILL_KROKI=bank,cap,wyjscie` (gold -> platinum, krok `cap`: nadmiar ham/łupu do depo i minimum ham, powrót na spot; bez backpacka i blanków), nigdy nie zatrzymuje w depo (także przy `zostan_w_depo`) i nie liczy
się do 2 bp. Cykl kończy dopiero wyprawa po blanki (pełny refill). Powody cap+blanki / jedzenie / WROC / PK = jak dotąd.

Pierwszeństwo ma człowiek: STOP_RECZNY (guzik Stop, zatrzymaj.sh, refill.sh --przerwij) = bez auto-refillu. Anulowanie:
`refill_auto.py anuluj` (woła je `wroc.sh --anuluj` i `refill.sh --przerwij`). Decyzje i powody w pliku stanu instancji
`wroc_refill.json` ({"stan": czeka|uruchomiony|pominiety|brak_planu, "powod", "t"}); czyta go `panel.py --json` (pole wroc_refill).

  python3 -I refill_auto.py czekaj    czekacz (uruchamiany przez bota, nie ręcznie)
  python3 -I refill_auto.py anuluj    ubija czekacza tej instancji (jeśli jest), zapisuje powód
"""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
KATALOG = Path(__file__).resolve().parent
sys.path.insert(0, str(KATALOG))
import instancja  # noqa: E402
import zostan_depo as ZD  # noqa: E402
import przerwa as PR  # noqa: E402

TRASY = KATALOG / "trasy"
PLIK = "wroc_refill.json"
MIASTA_SERWISU = ("edron", "thais", "abdendriel", "port_hope")        # miasta, które serwis.py umie obsłużyć (jego argparse: choices); Thais od 22.10 (drzwi sklepów), Ab'Dendriel od 24.10 (drzwi na klucz), Port Hope od 25.10 (na razie tylko depo)
WZOR_BOT = r"(mozg|cavebot)\.py"
WZOR_SERWIS = r"(^|[ /])serwis\.py "
WZOR_REFILL = r"^(\S*/)?bash (\S*/)?refill\.sh *$"
WZOR_CZEKACZ = r"(^|[ /])refill_auto\.py czekaj"
KROKI_CAP = "bank,cap,wyjscie"   # 24.10: bank, potem krok cap (minimum ham gdy 0; łup-sprzęt do depo tylko przy SERWIS_CAP_DEPO_LOOT=1, ham nigdy do depo), powrót; bez backpacka i blanków
COOLDOWN_S = 1200.0                                      # min. odstęp między startami auto-refillu (pętla wyprawa → depo → refill → wyprawa)
CZEKAJ_NA_BOTA_S = 60.0                                  # tyle czekacz czeka, aż bot zniknie po STOP (potem rezygnuje, niczego nie ubija)


def sciezka_stanu(stan_dir):
    return Path(stan_dir) / PLIK


def czytaj_stan(stan_dir):
    try:
        d = json.loads(sciezka_stanu(stan_dir).read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def zapisz_stan(stan_dir, stan, powod="", teraz=time.time):
    """Atomowy zapis decyzji (czyta ją panel). `ostatni_start` (kiedy czekacz ostatnio wołał refill.sh) przechodzi przez kolejne zapisy:
    na nim opiera się cooldown. Błąd zapisu nie przerywa niczego."""
    p = sciezka_stanu(stan_dir)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(PLIK + ".tmp")
        d = {"stan": stan, "powod": powod, "t": round(teraz(), 1)}
        ost = czytaj_stan(stan_dir).get("ostatni_start")
        if stan == "startuje":
            ost = d["t"]
        if isinstance(ost, (int, float)):
            d["ostatni_start"] = ost
        tmp.write_text(json.dumps(d, ensure_ascii=False))
        os.replace(tmp, p)
    except OSError:
        pass
    return stan, powod


def zostaje_w_depo(stan_dir):
    """Powód (tekst) albo None: flaga `zostan_w_depo` tej instancji w instancje/_wspolne/plan_postaci.json (23.10, Karol: invincible, dawajkesh, wydra,
    gebelish). Postać z flagą po dojściu do depo zostaje w depo: ŻADNEGO auto-refillu, także gdy tryb (`runy`, `uh`) przy starcie bota przywrócił
    WROC_REFILL=1 (tryby.json nadpisuje na_zywo.json przy każdym starcie). Ręczny `refill.sh` jest poza tym strażnikiem. Plik nieczytelny = None.
    24.10: wariant `zostan_w_depo_po_refillach: N` (zostan_depo.py) działa dopiero po N refillach od `zostan_w_depo_od` (licznik refille.json).
    25.10: klucz `domyslne` planu (zostan_depo.domyslne) = ta sama flaga dla postaci bez własnego wpisu; wyłączony domyślnie."""
    stan_dir = Path(stan_dir)
    sg = ZD.spot_gracz_depo(stan_dir)      # 26.10: powrót do miasta po spotkaniach graczy (nadzorca zapisał znacznik): bez auto-refillu i bez startu na spot
    if sg:
        return sg
    try:
        d = json.loads((stan_dir.parent / "_wspolne" / "plan_postaci.json").read_text(encoding="utf-8"))
        pc = (d.get("postacie") or {}).get(stan_dir.name) or {}
        dom = ZD.domyslne(d)[0]        # 25.10 (Karol): `domyslne` planu daje flagę też postaciom bez własnej (gdy domyslne.wlaczone == true)
    except (OSError, ValueError, AttributeError):
        return None
    z = ZD.parsuj(pc, dom)
    if not ZD.uzbrojona(z, stan_dir):
        return None
    if ZD.tylko_cap(stan_dir):         # 24.10 (Karol): depo wyłącznie po cap = bank + powrót, flaga nie zatrzymuje (ani nie liczy się do 2 bp)
        return None
    return z.powod or "plan_postaci.json"


def miasto_serwisu(poz, katalog=TRASY):
    """(miasto, w_depo): miasto z planem serwisu, w którym stoi `poz` (None, gdy takiego nie ma), i czy stoimy przy depo.
    Źródło prawdy to to samo, co w panelu („w_miescie”): prostokąt punktów trasy/serwis_<miasto>.json."""
    try:
        import panel  # noqa: PLC0415
        miasto, w_depo = panel.miasto_pozycji(tuple(poz), panel.dane_serwisu(katalog))
    except Exception:
        return None, False
    return (miasto, w_depo) if miasto in MIASTA_SERWISU else (None, False)


def trwa_serwis(procesy=None):
    """Serwis, praca refill.sh albo czekacz tej instancji już działają."""
    procesy = procesy or instancja.procesy
    return bool(procesy(WZOR_SERWIS) or procesy(WZOR_REFILL, comm=None) or procesy(WZOR_CZEKACZ))


def start_czekacza():
    """Odłączony czekacz (własna sesja: przeżywa bota, który zaraz wychodzi po STOP). Dziedziczy RETRONIC_ID bota."""
    return subprocess.Popen([sys.executable, "-I", str(KATALOG / "refill_auto.py"), "czekaj"], cwd=str(KATALOG),
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True)


def zlec(poz, stan_dir, katalog=TRASY, start=start_czekacza, procesy=None, teraz=time.time, cooldown_s=COOLDOWN_S):
    """Decyzja przy STOP w depo (woła ją bot). -> (stan, powód); `start()` tylko wtedy, gdy stan == "czeka".
    brak_planu = miasto bez planu serwisu (np. Thais): nic się nie dzieje poza wpisem w logu, panelu i dymku."""
    stan_dir = Path(stan_dir)
    if (stan_dir / "STOP_RECZNY").exists():
        return zapisz_stan(stan_dir, "pominiety", "ręczny stop (STOP_RECZNY) ma pierwszeństwo")
    powod_depo = zostaje_w_depo(stan_dir)
    if powod_depo:
        return zapisz_stan(stan_dir, "pominiety", f"zostan_w_depo (plan_postaci.json): zostaje w depo, bez auto-refillu ({powod_depo})")
    miasto, w_depo = miasto_serwisu(poz, katalog)
    if miasto is None:
        return zapisz_stan(stan_dir, "brak_planu",
                           f"brak planu serwisu dla tego miasta (pozycja {tuple(poz)}); serwis ma: {', '.join(MIASTA_SERWISU)}")
    if not w_depo:
        return zapisz_stan(stan_dir, "pominiety", f"postać nie stoi przy depo {miasto} (pozycja {tuple(poz)})")
    if trwa_serwis(procesy):
        return zapisz_stan(stan_dir, "pominiety", "serwis albo refill już trwa")
    ost = czytaj_stan(stan_dir).get("ostatni_start")
    if isinstance(ost, (int, float)) and 0 <= teraz() - ost < cooldown_s:
        return zapisz_stan(stan_dir, "pominiety", f"poprzedni auto-refill ruszył {(teraz() - ost) / 60:.0f} min temu (cooldown {cooldown_s / 60:.0f} min)")
    try:
        start()
    except Exception as e:                                # noqa: BLE001
        return zapisz_stan(stan_dir, "pominiety", f"nie udało się uruchomić czekacza: {e!r}")
    wariant = " (tylko cap: bank + powrót, bez depo)" if ZD.tylko_cap(stan_dir) else ""
    return zapisz_stan(stan_dir, "czeka", f"refill {miasto} ruszy po zatrzymaniu bota{wariant}")


def czekaj(stan_dir=None, katalog=KATALOG, czekaj_s=CZEKAJ_NA_BOTA_S, procesy=None, uruchom=subprocess.run,
           spij=time.sleep, zegar=time.monotonic):
    """Czekacz: bot zniknął -> ponowna kontrola STOP_RECZNY i serwisu -> zwolnienie wejścia -> refill.sh --tlo. -> kod wyjścia."""
    stan_dir = Path(stan_dir or instancja.S.stan)
    katalog = Path(katalog)
    procesy = procesy or instancja.procesy
    zapisz_stan(stan_dir, "czeka", "czekam na zatrzymanie bota")
    t0 = zegar()
    while procesy(WZOR_BOT):
        if zegar() - t0 > czekaj_s:
            zapisz_stan(stan_dir, "pominiety", f"bot nie zatrzymał się w {czekaj_s:.0f} s po STOP")
            return 1
        spij(0.5)
    if (stan_dir / "STOP_RECZNY").exists():
        zapisz_stan(stan_dir, "pominiety", "ręczny stop (STOP_RECZNY) ma pierwszeństwo")
        return 0
    powod_depo = zostaje_w_depo(stan_dir)
    if powod_depo:          # plan mógł dostać flagę już po zleceniu czekacza
        zapisz_stan(stan_dir, "pominiety", f"zostan_w_depo (plan_postaci.json): zostaje w depo, bez auto-refillu ({powod_depo})")
        return 0
    if procesy(WZOR_SERWIS) or procesy(WZOR_REFILL, comm=None):
        zapisz_stan(stan_dir, "pominiety", "serwis albo refill już trwa")
        return 0
    try:                                                   # bot mógł wyjść z wciśniętym klawiszem; brak gry = cicho
        uruchom([sys.executable, "-I", str(katalog / "zwolnij_wejscie.py")], timeout=20, capture_output=True)
    except (OSError, subprocess.SubprocessError):
        pass
    przerwa = PR.odczyt(stan_dir)                          # 24.10: przerwa postaci niezakończona i jeszcze niewylogowana = refill bez wyjścia z miasta
    przerwa = przerwa if przerwa is not None and not przerwa.wylogowano_t else None
    cap = ZD.tylko_cap(stan_dir)                           # 24.10: powrót po samym cap = tylko bank + wyjście (bez depo i zakupów)
    liczy = ZD.liczy_sie_do_licznika(stan_dir)             # licznik 2 bp rośnie tylko po wyprawie z powodem blanki
    opis_przerwy = " + przerwa postaci (bez wyjścia z miasta)" if przerwa else ""
    zapisz_stan(stan_dir, "startuje", "wołam refill.sh --tlo" + (f" (tylko cap: {KROKI_CAP})" if cap else "") + opis_przerwy)
    try:
        # 24.10: bez zmiennych odziedziczonych po poprzednim refillu (cap: bank,wyjscie wyciekało do bota -> refill po blanki bez blanków)
        env = {k: v for k, v in os.environ.items() if k not in ("REFILL_KROKI", "REFILL_TRYB", "REFILL_BEZ_WYJSCIA")}
        env.update({**({"REFILL_KROKI": KROKI_CAP} if cap else {}), **({"REFILL_BEZ_WYJSCIA": "1"} if przerwa else {})})
        wyciek = any(k in os.environ for k in ("REFILL_KROKI", "REFILL_TRYB", "REFILL_BEZ_WYJSCIA"))
        kw = {"env": env} if (cap or przerwa or wyciek) else {}
        r = uruchom(["bash", str(katalog / "refill.sh"), "--tlo"], capture_output=True, text=True, timeout=60, **kw)
    except (OSError, subprocess.SubprocessError) as e:
        zapisz_stan(stan_dir, "pominiety", f"refill.sh nie wystartował: {e!r}")
        return 1
    if r.returncode != 0:
        wyj = (r.stderr or r.stdout or "").strip().splitlines()
        zapisz_stan(stan_dir, "pominiety", "refill.sh odmówił: " + (wyj[-1] if wyj else f"kod {r.returncode}"))
        return r.returncode
    zapisz_stan(stan_dir, "uruchomiony", "refill.sh --tlo" + (f" (tylko cap: {KROKI_CAP})" if cap else "") + opis_przerwy)
    if liczy:                                              # licznik dla `zostan_w_depo_po_refillach` (refille.json): tylko blanki; błąd zapisu niczego nie przerywa
        ZD.zapisz_refill(stan_dir, time.time())
    return 0


def anuluj(stan_dir=None, procesy=None, zabij=os.kill):
    """Ubija czekacza tej instancji (jeśli jest) i zapisuje powód. -> liczba ubitych; -1, gdy czekacz już wołał refill.sh
    (refill ruszył albo rusza: czekacz nie jest ubijany, anulować można tylko `refill.sh --przerwij`)."""
    stan_dir = Path(stan_dir or instancja.S.stan)
    procesy = procesy or instancja.procesy
    st = czytaj_stan(stan_dir).get("stan")
    if st in ("startuje", "uruchomiony") and (procesy(WZOR_SERWIS) or procesy(WZOR_REFILL, comm=None)
                                              or (st == "startuje" and procesy(WZOR_CZEKACZ))):
        return -1                                          # stary wpis „uruchomiony” po zakończonym refillu nie liczy się
    pidy = procesy(WZOR_CZEKACZ)
    for p in pidy:
        try:
            zabij(p, signal.SIGTERM)
        except OSError:
            pass
    if pidy:
        zapisz_stan(stan_dir, "pominiety", "anulowane (wroc.sh --anuluj albo refill.sh --przerwij)")
    return len(pidy)


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    if a == ["czekaj"]:
        return czekaj()
    if a == ["anuluj"]:
        n = anuluj()
        print("refill już ruszył: ./refill.sh --przerwij" if n < 0
              else "auto-refill anulowany" if n else "brak oczekującego auto-refillu")
        return 0
    print("użycie: refill_auto.py czekaj | anuluj", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
