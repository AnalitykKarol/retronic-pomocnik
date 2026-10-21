#!/usr/bin/env python3
"""Zwięzły stan wszystkich instancji dla obchodu nadzorcy (SPEC_nadzorca_zestawu_1021, warstwa C). TYLKO ODCZYT.

  python3 -I nadzor_stan.py            tabela + lista problemów (KRYTYCZNE / UWAGA)
  python3 -I nadzor_stan.py --json     to samo jako JSON (dla skryptów)
  python3 -I nadzor_stan.py --okno 15  ile minut logu bota przeglądać (domyślnie 12)

Źródła: `okno_api.py stan` (procesy, panel, HP), `instancje/<id>/STOP_RECZNY`, `wyprawa_stan.json`,
najnowszy `logi/mozg-stdout-*.log` (alarmy, zabicia) i `logi/telemetria-<dzień>.jsonl` (ruch, wiek próbki).
Niczego nie zapisuje, nie wysyła klawiszy, nie dotyka procesów.
"""
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

DIR = Path(__file__).resolve().parent
INST = DIR / "instancje"

KRYTYCZNE = [
    (re.compile(r"ALARM_GM|ALARM: gracz"), "gracz/GM pisze albo patrzy (ALARM_GM)"),
    (re.compile(r"ALARM: PK|\[PK\] .*atak|Czaszka: .* = (?!nieczytelne|brak|bez)"), "PK / atak gracza / czaszka"),
    (re.compile(r"HP 0%|niskie HP 0%|MARTWY|SMIERC"), "możliwy zgon (HP 0%)"),
    (re.compile(r"ALARM: niskie HP"), "niskie HP (alarm bota)"),
]
UWAGI = [
    (re.compile(r"\[UCIECZKA\]"), "ucieczka"),
    (re.compile(r"Wyprawa: start|Wyprawa: WZNOWIONA|Wypad: start"), "wyprawa do miasta"),
    (re.compile(r"NIEUDANE"), "nieudane przejście pięter"),
    (re.compile(r"\[ORBITA\]"), "orbita (kręci się)"),
    (re.compile(r"\[RATUNEK\].*S[34] "), "ratunek: stoi/kręci się"),
    (re.compile(r"nie działa \(3x bez efektu"), "czar leczenia nie działa"),
    (re.compile(r"Loot: brak_plecaka"), "loot: brak otwartego plecaka"),
    (re.compile(r"ALARM: (?!gracz|PK|niskie HP)"), "inny alarm bota"),
]
GODZ = re.compile(r"^(\d\d):(\d\d):(\d\d) ")


def okno_api_stan():
    r = subprocess.run([sys.executable, "-I", str(DIR / "okno_api.py"), "stan"], cwd=DIR,
                       capture_output=True, text=True, timeout=60)
    return json.loads(r.stdout)


def najnowszy(katalog, wzor):
    pliki = sorted(katalog.glob(wzor), key=lambda p: p.stat().st_mtime) if katalog.is_dir() else []
    return pliki[-1] if pliki else None


def czas_linii(linia, dzis):
    m = GODZ.match(linia)
    if not m:
        return None
    return dzis.replace(hour=int(m[1]), minute=int(m[2]), second=int(m[3])).timestamp()


def przejrzyj_log(plik, od_ts, teraz):
    wynik = {"plik": plik.name if plik else None, "krytyczne": {}, "uwagi": {}, "zabicia": 0,
             "ostatnie_zabicie_min": None, "ostatnie_linie": []}
    if not plik:
        return wynik
    dzis = datetime.fromtimestamp(plik.stat().st_mtime).replace(microsecond=0)
    ost_zab = None
    with open(plik, encoding="utf-8", errors="replace") as f:
        linie = f.readlines()[-4000:]
    for l in linie:
        if "[OGIEN]" in l or "debug:" in l:
            continue
        t = czas_linii(l, dzis)
        if t is None:
            continue
        if "zabity" in l:
            ost_zab = t
        if t < od_ts:
            continue
        if "zabity" in l:
            wynik["zabicia"] += 1
        for wz, opis in KRYTYCZNE:
            if wz.search(l):
                wynik["krytyczne"].setdefault(opis, l.strip()[:160])
        for wz, opis in UWAGI:
            if wz.search(l):
                wynik["uwagi"].setdefault(opis, l.strip()[:160])
    if ost_zab:
        wynik["ostatnie_zabicie_min"] = round((teraz - ost_zab) / 60, 1)
    wynik["ostatnie_linie"] = [l.strip()[:160] for l in linie[-200:]
                               if "[OGIEN]" not in l and "debug:" not in l and "pokrętło" not in l][-5:]
    return wynik


def przejrzyj_telemetrie(katalog, teraz, okno_s=300):
    plik = katalog / f"telemetria-{time.strftime('%Y%m%d')}.jsonl"
    w = {"wiek_probki_s": None, "pola_odwiedzone": None, "walka_proc": None, "stoi_poza_walka_s": None}
    if not plik.is_file():
        return w
    probki = []
    with open(plik, encoding="utf-8", errors="replace") as f:
        for l in f.readlines()[-600:]:
            if '"probka"' not in l:
                continue
            try:
                r = json.loads(l)
            except ValueError:
                continue
            if r.get("t", 0) >= teraz - okno_s and r.get("poz"):
                probki.append(r)
    if not probki:
        return w
    w["wiek_probki_s"] = round(teraz - probki[-1]["t"])
    w["pola_odwiedzone"] = len({tuple(r["poz"]) for r in probki})
    w["walka_proc"] = round(100 * sum(r.get("stan") == "WALKA" for r in probki) / len(probki))
    # ile sekund pozycja stoi bez zmiany od końca, licząc tylko próbki poza walką
    ost = tuple(probki[-1]["poz"]); start = probki[-1]["t"]
    for r in reversed(probki):
        if tuple(r["poz"]) != ost:
            break
        start = r["t"]
    w["stoi_poza_walka_s"] = None if probki[-1].get("stan") == "WALKA" else round(probki[-1]["t"] - start)
    return w


def ocen(i, log, tele, stop_reczny, wyprawa):
    kryt, uwagi = [], []
    gracz = i.get("gracz") or {}
    hp = round(100 * gracz["hp"] / gracz["max_hp"]) if gracz.get("max_hp") else None
    if not i.get("gra"):
        kryt.append("gra nie działa")
    reczna = stop_reczny and not i.get("bot")
    if i.get("gra") and not i.get("bot") and not reczna:
        uwagi.append("bot nie działa (bez STOP_RECZNY)")
    if hp is not None and hp < 40:
        kryt.append(f"HP {hp}%")
    kryt += [f"{k}: {v}" for k, v in log["krytyczne"].items()]
    if i.get("bot"):
        uwagi += [f"{k}: {v}" for k, v in log["uwagi"].items()]
        if log["ostatnie_zabicie_min"] is not None and log["ostatnie_zabicie_min"] > 10:
            uwagi.append(f"brak zabić od {log['ostatnie_zabicie_min']} min")
        if (tele["stoi_poza_walka_s"] or 0) > 180:
            uwagi.append(f"stoi w miejscu {tele['stoi_poza_walka_s']} s poza walką")
        if (tele["wiek_probki_s"] or 0) > 120:
            uwagi.append(f"telemetria stara ({tele['wiek_probki_s']} s): bot zawieszony?")
        if wyprawa:
            uwagi.append(f"aktywna wyprawa ({wyprawa})")
        m = re.search(r"dobicie (\d+)%", (i.get("panel") or {}).get("tooltip", ""))
        if m and int(m[1]) < 60:
            uwagi.append(f"dobicie {m[1]}%")
    return hp, kryt, uwagi


def main():
    okno_min = 12.0
    if "--okno" in sys.argv:
        okno_min = float(sys.argv[sys.argv.index("--okno") + 1])
    teraz = time.time()
    stan = okno_api_stan()
    wyniki = []
    for i in stan.get("instancje", []):
        id_ = i["id"]
        kat = INST / id_
        stop_reczny = (kat / "STOP_RECZNY").exists()
        wyprawa = None
        try:
            ws = json.loads((kat / "wyprawa_stan.json").read_text())
            wyprawa = ws.get("powod") if ws.get("aktywna") else None
        except (OSError, ValueError):
            pass
        log = przejrzyj_log(najnowszy(kat / "logi", "mozg-stdout-*.log"), teraz - okno_min * 60, teraz)
        tele = przejrzyj_telemetrie(kat / "logi", teraz)
        hp, kryt, uwagi = ocen(i, log, tele, stop_reczny, wyprawa)
        wyniki.append({
            "id": id_, "nick": i.get("nick"), "gra": i.get("gra"), "bot": i.get("bot"),
            "reczna_gra": stop_reczny and not i.get("bot"), "mapa": i.get("mapa"), "tryb": i.get("tryb"),
            "pozycja": (i.get("panel") or {}).get("pozycja"), "hp_proc": hp, "gracz": i.get("gracz"),
            "zabicia_w_oknie": log["zabicia"], "ostatnie_zabicie_min": log["ostatnie_zabicie_min"],
            "telemetria": tele, "krytyczne": kryt, "uwagi": uwagi, "ostatnie_linie": log["ostatnie_linie"],
        })
    # dwa własne boty na jednej mapie = widzą się nawzajem (czaszki, unikanie), wzór wygląda na boty
    for w in wyniki:
        inni = [x["id"] for x in wyniki if x is not w and x["bot"] and w["bot"] and x["mapa"] == w["mapa"]]
        if inni:
            w["uwagi"].append(f"ta sama mapa co {', '.join(inni)}")
    if "--json" in sys.argv:
        print(json.dumps({"czas": time.strftime("%H:%M:%S"), "okno_min": okno_min, "instancje": wyniki},
                         ensure_ascii=False, indent=1))
        return
    print(f"Stan {time.strftime('%H:%M:%S')} (log z ostatnich {okno_min:g} min)")
    for w in wyniki:
        g = w["gracz"] or {}
        stan_txt = "RĘCZNA GRA" if w["reczna_gra"] else ("bot" if w["bot"] else ("gra bez bota" if w["gra"] else "WYŁĄCZONA"))
        print(f"- {w['id']:<11} {stan_txt:<12} lvl {g.get('level')} ({g.get('level_procent')}%)  HP {w['hp_proc']}%  "
              f"{w['mapa']} {','.join(w['tryb'] or [])}  poz {w['pozycja']}  zabicia {w['zabicia_w_oknie']}"
              f" (ostatnie {w['ostatnie_zabicie_min']} min temu)")
        for k in w["krytyczne"]:
            print(f"    KRYTYCZNE {k}")
        for u in w["uwagi"]:
            print(f"    UWAGA {u}")


if __name__ == "__main__":
    main()
