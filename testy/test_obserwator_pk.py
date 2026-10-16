#!/usr/bin/env python3
"""16.10 (P10): OBSERWATOR_PK_KONTEKST. Obserwator dostaje pk_stan, karencję i wrogów oraz instrukcję, że PAUZA_PK
z aktywną karencją jest zamierzona. Pokrętło 0 = prompt i dane jak dotąd. Atrapa modelu, zero runów i gry."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import json, sys, tempfile, types
from pathlib import Path
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import telemetria, pokretla, analityk

ok = True
def sprawdz(opis, war):
    global ok
    print(("OK   " if war else "BŁĄD ") + opis); ok = ok and bool(war)

def zrob(flaga):
    T = [1_700_000_000.0]
    zegar = lambda: T[0]
    tmp = Path(tempfile.mkdtemp())
    mod = types.SimpleNamespace(POGON_LIMIT=14.0, OBSERWATOR_PK_KONTEKST=flaga)
    pk = pokretla.Pokretla(mod, plik=tmp / "na_zywo.json", log=lambda *a: None, zegar=zegar)
    tele = telemetria.Telemetria(tmp / "t", zegar=zegar, zapis=False)
    wyw, logi_t = [], []
    def model(prompt, system):
        wyw.append((prompt, system))
        return json.dumps({"status": "ok", "wniosek": "Stan zamierzony.", "dowod": "karencja", "akcje": [], "do_kodu": []}), {}
    zrodlo = lambda: {"pk": {"pk_stan": "DEPO", "karencja_pozostalo_s": 420,
                             "wrogowie": [{"nick": "Zly Gracz", "widziany_s_temu": 90}]}}
    ob = analityk.Obserwator(tele, pk, model, log=lambda *a: logi_t.append(" ".join(map(str, a))), zegar=zegar,
                             logi=tmp / "logi", cykl_s=60, zrodlo=zrodlo)
    return ob, T, wyw, logi_t

for flaga in (0, 1):
    ob, T, wyw, lg = zrob(flaga)
    d = ob.dane(T[0])
    if flaga:
        p = d.get("pk") or {}
        sprawdz("flaga 1: dane maja pk_stan, karencje i wrogow", p.get("pk_stan") == "DEPO" and p.get("karencja_pozostalo_s") == 420
                and p["wrogowie"][0]["nick"] == "Zly Gracz" and p.get("pauza_pk_trwa_s") == 0)
        ob.cykl(T[0])
        prompt, system = wyw[0]
        sprawdz("flaga 1: prompt zawiera karencje", '"karencja_pozostalo_s": 420' in prompt)
        sprawdz("flaga 1: system mowi, ze PAUZA_PK z karencja jest zamierzona", "PAUZA_PK" in system and "ZAMIERZONY" in system and "300" in system)
        sprawdz("flaga 1: log, ze obserwator dostal karencje", any("kontekst PK" in l and "420" in l for l in lg))
    else:
        sprawdz("flaga 0: brak pola pk w danych", "pk" not in d)
        ob.cykl(T[0])
        prompt, system = wyw[0]
        sprawdz("flaga 0: system i prompt bez zmian", system == analityk.SYSTEM_OBS and "karencja" not in prompt
                and not any("kontekst PK" in l for l in lg))

# czas trwania PAUZA_PK z probek telemetrii
r = [{"typ": "probka", "t": 1000 + 30 * i, "stan": "PAUZA_PK"} for i in range(12)]
sprawdz("pauza_pk_trwa_s: 330 s ciaglej pauzy", analityk.pauza_pk_trwa_s(r, 1330) == 330)
r2 = r + [{"typ": "probka", "t": 1360, "stan": "IDZ"}]
sprawdz("pauza_pk_trwa_s: inny stan na koncu = 0", analityk.pauza_pk_trwa_s(r2, 1360) == 0)
sprawdz("pauza_pk_trwa_s: brak probek = 0", analityk.pauza_pk_trwa_s([], 1000) == 0)

# pokretlo: zakres, domyslna 0, kierunek
sprawdz("pokretlo w ZAKRESY (0,1)", pokretla.ZAKRESY.get("OBSERWATOR_PK_KONTEKST") == (0, 1))
import cavebot
sprawdz("domyslnie 0 w cavebot i w przykladzie", cavebot.OBSERWATOR_PK_KONTEKST == 0
        and json.load(open(Path(__file__).parent.parent / "na_zywo.przyklad.json")).get("OBSERWATOR_PK_KONTEKST") == 0)

print("WSZYSTKO OK" if ok else "SĄ BŁĘDY")
sys.exit(0 if ok else 1)
