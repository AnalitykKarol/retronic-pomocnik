#!/usr/bin/env python3
"""Panel i status pomocnika Retronic (tylko stdlib).

  panel.py            panel TUI (curses): s start, x stop, l pełny log w less, q wyjście
  panel.py --raz      jednorazowo wypisuje ekran (bez curses) i kończy
  panel.py --json     JSON dla paska (używa go status.sh)
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
    return {"text": f"{ikona} {tekst}".strip(), "tooltip": "\n".join(t), "class": k, "alt": k}


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
