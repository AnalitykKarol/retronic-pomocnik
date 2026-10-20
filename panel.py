#!/usr/bin/env python3
"""Panel i status pomocnika Retronic (tylko stdlib).

  panel.py            panel TUI (curses): s start, x stop, l pełny log w less, q wyjście
  panel.py --raz      jednorazowo wypisuje ekran (bez curses) i kończy
  panel.py --json     JSON dla paska (używa go status.sh); od 19.10 także pola guzików „Wróć do miasta” i „Refill” (niżej)
"""
import json
import os
import re
import sys
import time
from pathlib import Path

KAT = Path(__file__).resolve().parent
sys.path.insert(0, str(KAT))
import instancja  # noqa: E402

LOGI = instancja.S.logi
GNIAZDO = instancja.gniazdo("/run/user/%d" % os.getuid())
WAZNE = re.compile(r"ALARM|zabity|Okrążenie|Przerwa|HP|Loot: (?!ok)|Loot się|przerywam|Zatrzymano|Koniec|Błąd|Decyzja|Pauza")
ALARM = re.compile(r"ALARM_GM|ALARM: gracz")
CZAT = re.compile(r"Czat|wiadomosc_czatu|Wysłano|napisał|pisze|\[GRACZ\]", re.I)
DECYZJA = re.compile(r"Decyzja|Notatka|Pauza|Wznow|Zmiana trasy")
BOT_RE = re.compile(r"(^|/)(mozg|cavebot)\.py$")


def procesy_bota():
    """Lista (pid, tryb) żywych procesów mozg.py / cavebot.py."""
    wynik = []
    for p in os.listdir("/proc"):
        if not p.isdigit():
            continue
        try:
            arg = Path(f"/proc/{p}/cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        if not arg or not os.path.basename(arg[0].decode(errors="ignore")).startswith("python"):
            continue
        a = [x.decode(errors="ignore") for x in arg[1:] if x]
        skrypty = [x for x in a if BOT_RE.search(x)]
        if skrypty and instancja.nalezy(int(p)):
            tryb = os.path.basename(skrypty[0])
            if "--tryb" in a and a.index("--tryb") + 1 < len(a):
                tryb += " " + a[a.index("--tryb") + 1]
            wynik.append((int(p), tryb))
    return wynik


def czas_dzialania(pid):
    try:
        start = int(Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19])
        hz = os.sysconf("SC_CLK_TCK")
        boot = float(Path("/proc/uptime").read_text().split()[0])
        return int(boot - start / hz)
    except Exception:
        return None


def fmt_czas(s):
    if s is None:
        return "?"
    h, r = divmod(s, 3600)
    m, sek = divmod(r, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m {sek:02d}s"


def biezacy_log():
    kand = []
    for wskaznik in ("mozg-ostatni", "ostatni"):
        try:
            tekst = (LOGI / wskaznik).read_text().strip()
            sc = Path(tekst)
            if not sc.is_absolute():
                sc = LOGI / sc.name
            if sc.is_file():
                kand.append((sc.stat().st_mtime, sc))
        except OSError:
            pass
    return max(kand)[1] if kand else None


def ogon(sciezka, n=50, maks=262144):
    try:
        with open(sciezka, "rb") as f:
            f.seek(0, 2)
            rozm = f.tell()
            f.seek(max(0, rozm - maks))
            dane = f.read().decode(errors="replace")
        return dane.splitlines()[-n:]
    except OSError:
        return []


def wiek_linii(linia):
    m = re.match(r"(\d\d):(\d\d):(\d\d) ", linia)
    if not m:
        return None
    t = time.localtime()
    teraz = t.tm_hour * 3600 + t.tm_min * 60 + t.tm_sec
    return (teraz - (int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3]))) % 86400


def gracz(timeout=0.5):
    import socket
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect(str(GNIAZDO))
            s.sendall(b'{"cmd": "gracz"}\n')
            odp = json.loads(s.makefile("rb").readline())
        return odp.get("gracz") if odp.get("ok") else None
    except Exception:
        return None


def stan(z_graczem=True):
    s = {"gra": GNIAZDO.exists(), "procesy": procesy_bota(), "log": None, "alarm": None,
         "tryb": None, "czas": None, "gracz": None, "ostatnie": [], "zabicia": {}, "loot": {}, "czat": [], "decyzje": []}
    s["dziala"] = bool(s["procesy"])
    log = biezacy_log()
    s["log"] = log
    if s["dziala"]:
        s["tryb"] = s["procesy"][0][1]
        s["czas"] = czas_dzialania(s["procesy"][0][0])
    if log:
        # alarm: tylko świeży log (mtime) i linia nie starsza niż 60 s
        if time.time() - log.stat().st_mtime < 120:
            for l in ogon(log, 50):
                w = wiek_linii(l)
                if ALARM.search(l) and w is not None and w <= 60:
                    s["alarm"] = l[:200]
        s["ostatnie"] = [l for l in ogon(log, 400) if WAZNE.search(l) and "debug:" not in l][-3:]
    s["klasa"] = ("alarm" if s["alarm"] else "dziala" if s["dziala"] else "stop") if s["gra"] else "brak"
    if z_graczem and s["gra"] and (s["dziala"] or s.get("pelny")):
        s["gracz"] = gracz(0.3)
    return s


def statystyki(s):
    """Zabicia, łup, czat i decyzje z całego bieżącego logu."""
    log = s["log"]
    if not log:
        return
    try:
        linie = log.read_text(errors="replace").splitlines()
    except OSError:
        return
    for l in linie:
        m = re.search(r"Cel (.+?) zabity", l)
        if m:
            s["zabicia"][m[1]] = s["zabicia"].get(m[1], 0) + 1
        m = re.search(r"loot: zebrano (.+?) \+(\d+)", l)
        if m:
            s["loot"][m[1]] = s["loot"].get(m[1], 0) + int(m[2])
        if "debug:" in l:
            continue
        if CZAT.search(l) and not l[9:].startswith(("Decyzja", "ALARM")):
            s["czat"].append(l)
        if DECYZJA.search(l):
            s["decyzje"].append(l)
    s["linie"] = linie


def json_paska():
    s = stan(True)
    k = s["klasa"]
    ikona = {"dziala": "󰐊", "alarm": "󰀦", "stop": "󰓛", "brak": "󰹑"}[k]
    tekst = {"dziala": "RT", "alarm": "RT!", "stop": "RT", "brak": ""}[k]
    nazwa = {"dziala": "działa", "alarm": "ALARM", "stop": "zatrzymany", "brak": "brak gry"}[k]
    t = [f"Retronic: {nazwa}"]
    if s["tryb"]:
        t.append(f"Tryb: {s['tryb']}, działa {fmt_czas(s['czas'])}")
    g = s["gracz"]
    if g:
        t.append(f"HP {int(g['hp'])}/{int(g['max_hp'])}  mana {int(g['mana'])}/{int(g['max_mana'])}")
    if s["alarm"]:
        t.append("! " + s["alarm"])
    t += [l[:110] for l in s["ostatnie"]]
    try:
        w = (LOGI / "wniosek-ostatni.txt").read_text().strip()
        if w:
            t.append("Wniosek analityka: " + w[:140])
    except OSError:
        pass
    try:
        sys.path.insert(0, str(KAT))
        import telemetria  # noqa: PLC0415
        rek = telemetria.wczytaj_rekordy(LOGI, od_t=time.time() - 3600, tail_bajtow=8 * 1024 * 1024)
        d = telemetria.dobicie(rek)
        if d["epizody"]:
            l = f"dobicie {d['wskaznik']}% | med {telemetria._s(d['med_do_zab_s'])} (1 h, {d['zabite']}/{d['epizody']})"
            if d["exp_stracony"]:
                l += f" | stracone ~{d['exp_stracony']} exp ({d['exp_utracony_proc']}%)"
            t.append(l)
    except Exception:
        pass
    t.append("Lewy: start/stop, prawy: panel")
    wynik = {"text": f"{ikona} {tekst}".strip(), "tooltip": "\n".join(t), "class": k, "alt": k}
    try:
        wynik.update(pola_guzikow(s))
    except Exception as e:                  # pola guzików są dodatkiem: ich awaria nie psuje dotychczasowego kontraktu
        print(f"panel: pola guzików pominięte: {e!r}", file=sys.stderr)
    return wynik


# ---------- guziki „Wróć do miasta” i „Refill” (19.10) ----------
# Dodatkowe pola --json dla wtyczki paska charlie.retronic. Wszystkie OPCJONALNE i tylko dokładane: dotychczasowe
# pola (text, tooltip, class, alt) bez zmian. Spec: omarchy .ai/specs/2026-10-19-retronic-guziki-miasto.md.
TRASY = KAT / "trasy"
MARGINES_MIASTA = 8                                 # pól poza skrajnymi punktami serwisu nadal „w mieście”
SERWIS_WZOR = r"(^|[ /])serwis\.py "                 # python3 -I -u serwis.py edron ...
REFILL_WZOR = r"^(\S*/)?bash (\S*/)?refill\.sh *$"   # sama praca refill.sh (bez --tlo i --przerwij)
REFILL_LOG = "refill.log"
CZEKACZ_WZOR = r"(^|[ /])refill_auto\.py czekaj"         # czekacz auto-refillu (WROC_REFILL=1, refill_auto.py)
REFILL_AUTO_PLIK = "wroc_refill.json"                    # decyzja auto-refillu: {"stan": czeka|uruchomiony|pominiety|brak_planu, "powod", "t"}
WROC_POWOD = "depo:reczny"                          # powód wyprawy z wyprawa.py dla pliku WROC


def dane_serwisu(katalog=TRASY):
    """{miasto: dane} z trasy/serwis_<miasto>.json (te same pliki czyta serwis.py)."""
    wynik = {}
    for plik in sorted(Path(katalog).glob("serwis_*.json")):
        try:
            d = json.loads(plik.read_text())
            if isinstance(d, dict) and d.get("miasto"):
                wynik[d["miasto"]] = d
        except (OSError, ValueError):
            continue
    return wynik


def _punkty_serwisu(d):
    pts = [tuple(p["stoi"]) for p in d["przystanki"].values()]
    pts += [tuple(p) for p in d.get("depo_stoiska", [])] + [tuple(d["wyjscie"])]
    for l in d.get("laczniki", []):
        pts += [tuple(l["z"]), tuple(l["do"])]
    return pts


def miasto_pozycji(poz, dane=None, margines=MARGINES_MIASTA):
    """(miasto, w_depo) dla pozycji (x, y, z): miasto, gdy pozycja leży w prostokącie punktów serwisu (z marginesem
    na x/y, piętra od najniższego do najwyższego punktu), w_depo, gdy stoi przy polu depo (<= 2 pola). Inaczej (None, False)."""
    if poz is None:
        return None, False
    x, y, z = poz
    for nazwa, d in (dane_serwisu() if dane is None else dane).items():
        try:
            xs, ys, zs = zip(*_punkty_serwisu(d))
            stoiska = [tuple(p) for p in d.get("depo_stoiska", [])] + [tuple(d["przystanki"]["depo"]["stoi"])]
        except (KeyError, TypeError, ValueError):
            continue
        if min(xs) - margines <= x <= max(xs) + margines and min(ys) - margines <= y <= max(ys) + margines \
                and min(zs) <= z <= max(zs):
            return nazwa, any(s[2] == z and max(abs(s[0] - x), abs(s[1] - y)) <= 2 for s in stoiska)
    return None, False


def plan_depo(poz, katalog=TRASY):
    """Nazwa planu dojścia do depo z `poz`, taka jak wybrałaby ją wyprawa.py dla ręcznego „Wróć do miasta”
    (wybierz_baze w PK_PLAN_ZASIEG, potem plan z PLANY_PK w DEPO_DOJSCIE_ZASIEG), albo None, gdy planu brak
    (np. Rookgaard). Ocenia tylko położenie i pliki tras; nie liczy drogi (to robi bot w chwili startu)."""
    if poz is None:
        return None
    try:
        import wyprawa  # noqa: PLC0415
        from wypad import cheb  # noqa: PLC0415
        baza = wyprawa.punkty_bazy(katalog, nazwy=wyprawa.BAZY_PK)
        nazwa = wyprawa.wybierz_baze(baza, poz, wyprawa.PK_PLAN_ZASIEG)
        if nazwa is not None:
            return nazwa
        najl = None
        for p in wyprawa.PLANY_PK:           # jak Wyprawa._baza_dojscie: najbliższe depo planu z PLANY_PK
            if p["nazwa"] in baza:
                d = cheb(poz, baza[p["nazwa"]][0][-1])
                if d <= wyprawa.DEPO_DOJSCIE_ZASIEG and (najl is None or d < najl[0]):
                    najl = (d, p["nazwa"])
        return najl[1] if najl else None
    except Exception:
        return None


class PozycjaPrzekroczona(BaseException):
    """Limit czasu odczytu pozycji. BaseException celowo: `except Exception` w bot.wlasny_wpis nie może go połknąć
    (wtedy limit nie byłby twardy: alarm jednorazowy, a odczyt szedłby dalej kolejnymi zapytaniami)."""


def pozycja_postaci(limit_s=2.0):
    """(x, y, z) postaci z gniazda gry tej instancji albo None (brak gry, postaci albo odpowiedzi). Twardy limit czasu."""
    import signal
    import socket

    def _czas(*_):
        raise PozycjaPrzekroczona()
    stary = signal.signal(signal.SIGALRM, _czas)
    signal.setitimer(signal.ITIMER_REAL, limit_s)
    try:
        import bot  # noqa: PLC0415
        socket.setdefaulttimeout(1.0)
        p = bot.zapytaj({"cmd": "pozycja", "nazwa": bot.nazwa_postaci()})["pozycja"]
        return (p["x"], p["y"], p["z"])
    except (Exception, SystemExit, PozycjaPrzekroczona):   # nazwa_postaci() kończy się sys.exit bez logowania w logu klienta
        return None
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, stary)


def _json_pliku(sciezka):
    try:
        d = json.loads(Path(sciezka).read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def stan_wroc(stan_dir, bot_dziala):
    """„Wróć do miasta”: czy zlecenie (plik WROC) czeka i czy bot jest w marszu do depo (wyprawa ręczna aktywna)."""
    ws = _json_pliku(Path(stan_dir) / "wyprawa_stan.json")
    reczna = ws.get("powod") == WROC_POWOD
    return {"wroc_oczekuje": (Path(stan_dir) / "WROC").exists(),
            "wroc_w_marszu": bool(bot_dziala and reczna and ws.get("aktywna"))}


def _bot_startowal_po(logi, log):
    """Czy któryś stdout bota (logi/mozg-stdout-*.log, tworzy go uruchom.sh przy KAŻDYM starcie) był pisany po ostatnim zapisie
    refill.log. Bot nie biegnie w trakcie refillu (serwis odmawia), więc nowszy log = bot wystartował po nim (ręcznie, ▶ Start albo
    STARTUJ=1) i wynik refillu przestaje obowiązywać także po jego późniejszym Stop."""
    try:
        t_log = Path(log).stat().st_mtime
        return any(f.stat().st_mtime > t_log for f in Path(logi).glob("mozg-stdout-*.log"))
    except OSError:
        return False


def stan_serwisu(stan_dir, teraz=None, dziala=None, kolejnosc=None):
    """„Refill”: czy serwis tej instancji trwa (serwis.py albo praca refill.sh), na jakim kroku, jak skończył się
    ostatni refill (refill.log: znaczniki `REFILL: START|OK|BLAD <powód>|PRZERWANO` pisze refill.sh)."""
    stan_dir = Path(stan_dir)
    teraz = time.time() if teraz is None else teraz
    if dziala is None:
        dziala = bool(instancja.procesy(SERWIS_WZOR) or instancja.procesy(REFILL_WZOR, comm=None))
    log = stan_dir / REFILL_LOG
    linie = ogon(log, 300)
    start = koniec = -1
    wynik, komunikat, krok, tryb = None, "", None, None
    for i, l in enumerate(linie):
        if l.startswith("REFILL: START"):
            start = i
            m = re.match(r"REFILL: START \d+ (\w+)", l)
            tryb = m[1] if m else None          # refill | spot (refill.sh --spot: tylko wyjście z miasta + start bota)
        m = re.match(r"REFILL: (OK|BLAD|PRZERWANO)\b ?(.*)", l)
        if m:
            koniec, wynik, komunikat = i, m[1].lower(), m[2].strip()
        m = re.match(r"serwis: krok (\w+)\s*$", l)
        if m and i > start:
            krok = m[1]
    if wynik and koniec < start:                  # nowy START po starym wyniku: tamten już nieaktualny
        wynik, komunikat = None, ""
    if dziala:
        wynik, komunikat = None, ""
    elif wynik is None and start >= 0:            # proces zniknął bez znacznika (zabity siłą)
        wynik = "przerwano"
    if wynik and _bot_startowal_po(stan_dir / "logi", log):    # bot ruszył po refillu: stary wynik (np. błąd) jest nieaktualny
        wynik, komunikat = None, ""
    st = _json_pliku(stan_dir / "serwis_stan.json")
    ukonczone = [] if st.get("koniec") else [k for k in st.get("ukonczone", []) if isinstance(k, str)]
    # serwis puszczony z terminala (log nie jest w refill.log); przy własnym znaczniku START bez linii kroku brak kroku = nie zgadujemy
    if dziala and krok is None and kolejnosc and start < 0:
        krok = next((k for k in kolejnosc if k not in ukonczone), None)
    try:
        wiek = int(teraz - log.stat().st_mtime)
    except OSError:
        wiek = None
    return {"serwis_dziala": bool(dziala), "serwis_krok": krok if dziala else None, "serwis_ukonczone": ukonczone,
            "serwis_tryb": tryb if dziala else None, "serwis_wynik": wynik, "serwis_komunikat": komunikat[:200], "serwis_wiek_s": wiek}


def _start_bota_po(t):
    """Czy żywy proces bota tej instancji wystartował po chwili `t` (czas ścienny). Start liczymy z uptime procesu (ps/proc)."""
    teraz = time.time()
    for pid, _tryb in procesy_bota():
        wiek = czas_dzialania(pid)
        if wiek is not None and teraz - wiek > t + 1.0:
            return True
    return False


def stan_auto_refill(stan_dir, serwis_dziala, czeka=None, bot_po=None):
    """Auto-refill po dojściu do depo (WROC_REFILL=1): wroc_refill = "czeka" (czekacz żyje, bot jeszcze się zatrzymuje),
    "trwa" (refill ruszył i serwis działa), "pominiety" (powód w komunikacie: ręczny stop, serwis już trwał, anulowano, cooldown...),
    "brak_planu" (miasto bez planu serwisu) albo None. Pominięty / brak planu zostają widoczne do NASTĘPNEGO STARTU bota (żywy proces
    bota nowszy niż decyzja), nie do pierwszej linii logu: bot sam loguje zaraz po decyzji. Wynik samego refillu (ok/błąd) jest
    w serwis_wynik, tu go nie powtarzamy. `bot_po(t)` podmienia sprawdzenie startu bota (testy)."""
    stan_dir = Path(stan_dir)
    d = _json_pliku(stan_dir / REFILL_AUTO_PLIK)
    st, powod = d.get("stan"), str(d.get("powod") or "")
    if czeka is None:
        czeka = bool(instancja.procesy(CZEKACZ_WZOR))
    wynik = None
    if st == "czeka" and czeka:
        wynik = "czeka"
    elif st in ("czeka", "startuje", "uruchomiony") and serwis_dziala:
        wynik = "trwa"
    elif st in ("pominiety", "brak_planu"):
        t = d.get("t")
        po = (bot_po or _start_bota_po)(t) if isinstance(t, (int, float)) else False
        if not po:
            wynik = st
    return {"wroc_refill": wynik, "wroc_refill_komunikat": powod[:200] if wynik else ""}


def pola_guzikow(s):
    """Dodatkowe pola --json dla guzików „Wróć do miasta” i „Refill”. s = wynik stan()."""
    poz = pozycja_postaci() if s["gra"] else None
    dane = dane_serwisu()
    miasto, w_depo = miasto_pozycji(poz, dane)
    kolejnosc = (dane.get(miasto) or next(iter(dane.values()), {})).get("kolejnosc")
    pola = {"pozycja": list(poz) if poz else None, "w_miescie": miasto, "w_depo": w_depo,
            "plan_depo_dostepny": None if poz is None else plan_depo(poz) is not None}
    pola.update(stan_wroc(instancja.S.stan, s["dziala"]))
    pola.update(stan_serwisu(instancja.S.stan, kolejnosc=kolejnosc))
    pola.update(stan_auto_refill(instancja.S.stan, pola["serwis_dziala"]))
    return pola


# ---------- widok ----------
def zbuduj(s, szer=88):
    """Lista (tekst, styl) wierszy; styl: n, tyt, ok, zle, dim, duze."""
    w = []
    k = s["klasa"]
    if k == "alarm":
        w += [("  ###  S T O P  -  A L A R M  ###", "duze"), ("  " + (s["alarm"] or "")[:szer - 4], "zle"), ("", "n")]
    etyk = {"dziala": ("DZIAŁA", "ok"), "stop": ("ZATRZYMANY", "dim"), "alarm": ("ALARM", "zle"), "brak": ("BRAK GRY (brak socketu)", "dim")}[k]
    w.append((f" Status: {etyk[0]}   {s['tryb'] or ''}   {('czas ' + fmt_czas(s['czas'])) if s['dziala'] else ''}", etyk[1]))
    g = s["gracz"]
    if g:
        w.append((f" HP {int(g['hp'])}/{int(g['max_hp'])}   mana {int(g['mana'])}/{int(g['max_mana'])}   cap {g['cap']:g}   "
                  f"exp {int(g['exp'])}   lvl {int(g['level'])} ({g['procent']:g}%)", "n"))
    else:
        w.append((" HP/mana/cap/exp: brak odczytu", "dim"))
    w.append(("", "n"))
    zab = sum(s["zabicia"].values())
    w.append((f" Zabicia: {zab}  " + ", ".join(f"{k2} x{v}" for k2, v in s["zabicia"].items()), "tyt"))
    w.append((" Łup: " + (", ".join(f"{k2} +{v}" for k2, v in s["loot"].items()) or "nic"), "tyt"))
    w.append(("", "n"))
    w.append((" Czat (ostatnie):", "tyt"))
    w += [("  " + l[:szer - 3], "n") for l in s["czat"][-4:]] or [("  -", "dim")]
    w.append((" Decyzje mózgu:", "tyt"))
    w += [("  " + l[:szer - 3], "n") for l in s["decyzje"][-5:]] or [("  -", "dim")]
    w.append(("", "n"))
    w.append((" Log" + (f" ({s['log'].name})" if s["log"] else "") + ":", "tyt"))
    w += [("  " + l[:szer - 3], "dim") for l in s.get("linie", [])[-10:]]
    return w


def pelny():
    s = stan(True)
    s["pelny"] = True
    statystyki(s)
    return s


def uruchom(skrypt):
    import subprocess
    subprocess.Popen(["bash", str(KAT / skrypt)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     stdin=subprocess.DEVNULL, start_new_session=True)


def tui(scr):
    import curses
    import subprocess
    curses.curs_set(0)
    curses.use_default_colors()
    BG, KART, RAMKA = 233, 235, 238
    curses.start_color()
    def p(i, fg, bg=-1):
        curses.init_pair(i, fg, bg)
    p(1, 114); p(2, 203); p(3, 244); p(4, 111); p(5, 255, 160); p(6, 252)
    st = {"n": curses.color_pair(6), "tyt": curses.color_pair(4) | curses.A_BOLD, "ok": curses.color_pair(1) | curses.A_BOLD,
          "zle": curses.color_pair(2) | curses.A_BOLD, "dim": curses.color_pair(3), "duze": curses.color_pair(5) | curses.A_BOLD}
    scr.timeout(1000)
    komunikat = ""
    while True:
        s = pelny()
        h, wsz = scr.getmaxyx()
        scr.erase()
        wiersze = zbuduj(s, wsz)
        mig = s["klasa"] == "alarm" and int(time.time()) % 2 == 0
        for i, (t, stl) in enumerate(wiersze[:h - 2]):
            a = st[stl]
            if stl == "duze" and mig:
                a = st["zle"]
            try:
                scr.addnstr(i, 0, t.ljust(wsz) if stl == "duze" else t, wsz - 1, a)
            except curses.error:
                pass
        try:
            scr.addnstr(h - 1, 0, " s start   x stop   l log   q wyjście   " + komunikat, wsz - 1, st["dim"])
        except curses.error:
            pass
        scr.refresh()
        c = scr.getch()
        if c in (ord("q"), 27):
            return
        if c == ord("s"):
            uruchom("uruchom.sh"); komunikat = "start..."
        elif c == ord("x"):
            uruchom("zatrzymaj.sh"); komunikat = "stop..."
        elif c == ord("l") and s["log"]:
            curses.endwin()
            subprocess.call(["less", "+G", str(s["log"])])
            scr.refresh()


def main():
    if "--json" in sys.argv:
        print(json.dumps(json_paska(), ensure_ascii=False))
    elif "--raz" in sys.argv:
        for t, _ in zbuduj(pelny()):
            print(t)
    else:
        import curses
        os.environ.setdefault("ESCDELAY", "25")
        curses.wrapper(tui)


if __name__ == "__main__":
    main()
