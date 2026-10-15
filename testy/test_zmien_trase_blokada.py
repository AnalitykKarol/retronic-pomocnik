#!/usr/bin/env python3
"""15.10: zmien_trase modelu odrzucona przy zamrożonej pozycji (martwy odczyt) albo trasie z innego obszaru.
Atrapa modelu, atrapa gniazda, wstrzyknięty zegar. Zero inputu do gry."""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ["RETRONIC_TESTY"] = "1"
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bot  # noqa: E402
import cavebot  # noqa: E402
import mozg  # noqa: E402

ok = []
tmp = Path(tempfile.mkdtemp(prefix="pomocnik-trasa-"))


def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek))
    print(("OK  " if warunek else "FAIL"), nazwa, info)


class Zegar:
    def __init__(s): s.t = 1000.0
    def __call__(s): return s.t


class Gniazdo:
    def __init__(s): s.poz = [33000, 32000, 8]
    def __call__(s, z):
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": 150, "max_hp": 165, "cap": 240, "exp": 543, "level": 4, "procent": 35,
                              "mana": 15, "max_mana": 15}}
        if z["cmd"] == "pozycja":
            return {"pozycja": dict(zip("xyz", s.poz))}
        if z["cmd"] == "stwory":
            return {"stwory": []}
        raise RuntimeError("nieznane polecenie")


ODP = {"mysl": "patrol: no path", "akcje": [{"typ": "zmien_trase", "nazwa": "blisko"},
                                            {"typ": "notatka", "tekst": "ta trasa nie działa na tym serwerze"}]}


class Model:
    def __init__(s, odp): s.odp = odp
    def __call__(s, prompt): return json.dumps(s.odp), {"duration_ms": 1}


def zrob(odp, g, trasy):
    logi = []
    z = Zegar()
    m = mozg.Mozg("doradca", zapytaj=g, nazwa="Ja", model=Model(odp), pamiec=mozg.Pamiec(tmp / "pamiec.json"),
                  log=lambda *a: logi.append(" ".join(map(str, a))), zegar=z, trasy=lambda: list(trasy),
                  losuj=lambda a, b: a, alarm=lambda w: None)
    m.z, m.logi = z, logi
    return m


stara_trasy = bot.TRASY
bot.TRASY = tmp
(tmp / "blisko.json").write_text(json.dumps([[33010, 32005, 8], [33020, 32010, 8]]))
(tmp / "thais_szczury.json").write_text(json.dumps([[32350, 32225, 7], [32348, 32224, 7]]))
typy = lambda akcje: [a["typ"] for a in akcje]   # noqa: E731

try:
    # 1. normalna trasa blisko, pozycja się rusza -> przechodzi (z notatką)
    g = Gniazdo(); m = zrob(ODP, g, ["blisko", "thais_szczury"])
    for i in range(5):
        g.poz[0] += 1; m.z.t += 60
        mysl, akcje, _ = m.zdecyduj(m.zbuduj_stan())
    sprawdz("1 blisko + ruch: zmien_trase przechodzi razem z notatką", typy(akcje) == ["zmien_trase", "notatka"], akcje)

    # 2. zamrożona pozycja >= 180 s -> odrzucona, notatka też, log "Odrzucam zmien_trase"
    g = Gniazdo(); m = zrob(ODP, g, ["blisko"])
    m.zdecyduj(m.zbuduj_stan())
    m.z.t += cavebot.MODEL_TRASA_ZAMROZENIE_S - 1
    _, akcje, _ = m.zdecyduj(m.zbuduj_stan())
    sprawdz("2a tuż przed progiem zamrożenia: jeszcze przechodzi", "zmien_trase" in typy(akcje), akcje)
    m.z.t += 1
    _, akcje, _ = m.zdecyduj(m.zbuduj_stan())
    sprawdz("2b pozycja stoi >= 180 s: odrzucona, notatka też",
            akcje == [{"typ": "kontynuuj"}] and any("Odrzucam zmien_trase" in l and "stoi" in l for l in m.logi),
            (akcje, m.logi[-3:]))

    # 2c. ruch zeruje licznik
    g.poz[1] += 1
    _, akcje, _ = m.zdecyduj(m.zbuduj_stan())
    sprawdz("2c pozycja ruszyła: znów przechodzi", "zmien_trase" in typy(akcje), akcje)

    # 2d. progi z pokrętła
    stare = cavebot.MODEL_TRASA_ZAMROZENIE_S
    try:
        cavebot.MODEL_TRASA_ZAMROZENIE_S = 30
        m.z.t += 30
        _, akcje, _ = m.zdecyduj(m.zbuduj_stan())
        sprawdz("2d pokrętło MODEL_TRASA_ZAMROZENIE_S=30 działa", akcje == [{"typ": "kontynuuj"}], akcje)
    finally:
        cavebot.MODEL_TRASA_ZAMROZENIE_S = stare

    # 3. trasa z innego obszaru (Thais) -> odrzucona; notatka też
    odp = {"mysl": "no path", "akcje": [{"typ": "zmien_trase", "nazwa": "thais_szczury"},
                                         {"typ": "notatka", "tekst": "ta trasa nie działa na tym serwerze"}]}
    g = Gniazdo(); m = zrob(odp, g, ["blisko", "thais_szczury"])
    _, akcje, _ = m.zdecyduj(m.zbuduj_stan())
    sprawdz("3a daleka trasa odrzucona (+ notatka)",
            akcje == [{"typ": "kontynuuj"}] and any("inny obszar" in l for l in m.logi), (akcje, m.logi[-3:]))

    # 3b. ta sama trasa, gdy postać jest przy niej (daleko od 33000,32000): przechodzi
    g.poz = [32349, 32226, 8]
    _, akcje, _ = m.zdecyduj(m.zbuduj_stan())
    sprawdz("3b to samo z pozycją przy trasie (inne piętro, z ignorowane): przechodzi", "zmien_trase" in typy(akcje), akcje)

    # 3c. granica: dokładnie MAX_ODL przechodzi, +1 nie (Chebyshev)
    (tmp / "granica.json").write_text(json.dumps([[33000 + cavebot.MODEL_TRASA_MAX_ODL, 32000, 1]]))
    (tmp / "za_daleko.json").write_text(json.dumps([[33000 + cavebot.MODEL_TRASA_MAX_ODL + 1, 32000, 8]]))
    for nazwa, oczekiwane in (("granica", True), ("za_daleko", False)):
        g = Gniazdo(); m = zrob({"akcje": [{"typ": "zmien_trase", "nazwa": nazwa}]}, g, [nazwa])
        _, akcje, _ = m.zdecyduj(m.zbuduj_stan())
        sprawdz(f"3c granica {nazwa}", ("zmien_trase" in typy(akcje)) == oczekiwane, akcje)

    # 4. brak odczytu pozycji -> odrzucamy (nie wiemy, czy odczyt żyje)
    class GniazdoBezPoz(Gniazdo):
        def __call__(s, z):
            if z["cmd"] == "pozycja": raise RuntimeError("brak")
            return super().__call__(z)
    m = zrob(ODP, GniazdoBezPoz(), ["blisko"])
    _, akcje, _ = m.zdecyduj(m.zbuduj_stan())
    sprawdz("4 brak pozycji: odrzucona", akcje == [{"typ": "kontynuuj"}] and any("brak odczytu" in l for l in m.logi), akcje)

    # 5. notatka bez zmien_trase zostaje; inne akcje obok odrzuconego zmien_trase zostają
    m = zrob({"akcje": [{"typ": "pauza_bota", "sekundy": 30}, {"typ": "zmien_trase", "nazwa": "thais_szczury"}]},
             Gniazdo(), ["thais_szczury"])
    _, akcje, _ = m.zdecyduj(m.zbuduj_stan())
    sprawdz("5a pauza_bota obok odrzuconego zmien_trase zostaje", typy(akcje) == ["pauza_bota"], akcje)
    m = zrob({"akcje": [{"typ": "notatka", "tekst": "ok"}]}, Gniazdo(), [])
    _, akcje, _ = m.zdecyduj(m.zbuduj_stan())
    sprawdz("5b sama notatka nietknięta", typy(akcje) == ["notatka"], akcje)

    # 6. obieg hybrydy: próbka pozycji w tle liczy zamrożenie bez pytania modelu
    class P:
        nazwa = "Ja"
        def pozycja(s): return (33000, 32000, 8)
    cb = type("CB", (), {"postac": P(), "stan": "IDZ"})()
    m = zrob(ODP, Gniazdo(), ["blisko"]); m.cb = cb; m.model = None
    m._sledz_pozycje((33000, 32000, 8)); m.z.t += 200
    m._sledz_pozycje((33000, 32000, 8))
    sprawdz("6 _sledz_pozycje: ta sama pozycja nie zeruje licznika", m.zegar() - m._poz_od == 200, m.zegar() - m._poz_od)
finally:
    bot.TRASY = stara_trasy
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
