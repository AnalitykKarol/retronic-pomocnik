#!/usr/bin/env python3
"""Sonda ruchu po skosie (numpad KP_7/9/1/3 albo Q/E/Z/C): czy działa, ile trwa krok po skosie
względem prostego i czy skos opłaca się wobec dwóch kroków prostych.

URUCHAMIAĆ RĘCZNIE (nie robi tego bot), przy ZATRZYMANYM bocie (zatrzymaj.sh), postacią stojącą
na wolnym polu: wokół niej 3x3 pól przechodnich wg mapy, bez potworów i graczy w widoku.
Nie używa pliku STOP ani mózgu: klawisze idą prosto przez klawisz_x11 (skos() i wyslij()).

  python3 -I sonda_skosu.py            pełny pomiar (ok. 2-3 min), tryb numpad
  python3 -I sonda_skosu.py --szybko   po 2 powtórzenia zamiast 3 (ok. 1.5 min)
  python3 -I sonda_skosu.py --sucho    tylko kontrole bezpieczeństwa, bez klawiszy
  python3 -I sonda_skosu.py --tryb wsad   Q/E/Z/C zamiast numpadu (tylko przy wsadWalking i
                                          WYŁĄCZONYM czacie, inaczej litery lecą na czat)

Fazy:
  1. opóźnienie i skuteczność: pojedyncze wciśnięcie po 1 s ciszy (krok dokończony), 4 skosy
     tam i z powrotem + Right/Left jako odniesienie;
  2. trasy: dla każdego skosu "skos tam i z powrotem" kontra "dwa proste tam i z powrotem",
     wciśnięcia zaraz po zmianie pozycji (kolejkowanie kroku); z odstępów między zmianami
     wychodzi czas kroku prostego S i po skosie D, mnożnik D/S;
  3. zapis logi/sonda-skosu-<data>.json z rekomendacją.

Przerywa przy potworze/graczu w widoku, spadku HP, pliku STOP, pozycji innej niż oczekiwana;
zawsze wraca na pole startowe (prostymi krokami). Jedno wciśnięcie = jeden krok, bez powtórek
w oknie oczekiwania, żeby nie wyjść poza sprawdzone 3x3.
"""
import json
import statistics
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
KATALOG = Path(__file__).resolve().parent
sys.path.insert(0, str(KATALOG))

import kalibracja_krokow as kal  # noqa: E402
from kalibracja_krokow import Przerwano  # noqa: E402

SKOSY = ("UpLeft", "UpRight", "DownLeft", "DownRight")
WEKTOR = {"UpLeft": (-1, -1), "UpRight": (1, -1), "DownLeft": (-1, 1), "DownRight": (1, 1),
          "Right": (1, 0), "Left": (-1, 0), "Up": (0, -1), "Down": (0, 1)}
PRZECIWNY = {"UpLeft": "DownRight", "DownRight": "UpLeft", "UpRight": "DownLeft", "DownLeft": "UpRight",
             "Right": "Left", "Left": "Right", "Up": "Down", "Down": "Up"}
OKNO = 1.2            # s: tyle czekamy na zmianę pozycji po jednym wciśnięciu
CISZA = 1.0           # s: pauza przed wciśnięciem w fazie 1 (poprzedni krok na pewno skończony)
PROBY = 2             # ile razy ponawiamy ruch, który się nie wykonał
PRZYTRZYMANIE_MS = 70
PROG_OPLACALNOSCI = 0.95   # skos "opłaca się", gdy jego czas < 0.95 x dwóch prostych
MIN_SKUTECZNOSC = 0.9


def rozloz(nazwa):
    """Skos -> dwa kroki proste (poziomo, potem pionowo)."""
    dx, dy = WEKTOR[nazwa]
    return ["Right" if dx > 0 else "Left", "Down" if dy > 0 else "Up"]


def _wyslij(env, nazwa, tryb):
    if nazwa in SKOSY:
        env.skos(nazwa, PRZYTRZYMANIE_MS, tryb)
    else:
        env.wcisnij(nazwa, PRZYTRZYMANIE_MS)


def ruch(env, nazwa, start, tryb, hp0, po_zmianie, zapisy, faza, ostatnia_zmiana):
    """Jeden ruch (z ponowieniami po nieudanej próbie). Dopisuje wpis do `zapisy`. Zwraca czas
    zmiany pozycji (zegar) albo przerywa. `po_zmianie`: ile s czekać przed wciśnięciem."""
    dx, dy = WEKTOR[nazwa]
    for proba in range(1, PROBY + 2):
        kal._straz(env, hp0, start)
        if po_zmianie:
            env.spij(po_zmianie)
        p0 = tuple(env.pozycja())
        t = env.zegar()
        _wyslij(env, nazwa, tryb)
        p, _ = kal.czekaj_na_zmiane(env, p0, OKNO)
        if p is not None:
            t_zm = env.zegar()
            if (p[0] - p0[0], p[1] - p0[1], p[2]) != (dx, dy, p0[2]):
                raise Przerwano(f"{nazwa}: pozycja {p0} -> {p}, oczekiwano przesunięcia ({dx},{dy})")
            zapisy.append(dict(faza=faza, ruch=nazwa, skos=nazwa in SKOSY, ok=True, proba=proba,
                               opoznienie=round(t_zm - t, 3),
                               od_poprzedniej=round(t_zm - ostatnia_zmiana, 3) if ostatnia_zmiana else None))
            return t_zm
        zapisy.append(dict(faza=faza, ruch=nazwa, skos=nazwa in SKOSY, ok=False, proba=proba,
                           opoznienie=None, od_poprzedniej=None))
        env.spij(0.9)                    # niech ewentualny trwający krok się dokończy
        if tuple(env.pozycja()) != p0:   # spóźniona zmiana: uznajemy, pozycję sprawdza następny ruch
            raise Przerwano(f"{nazwa}: pozycja zmieniła się dopiero po oknie {OKNO} s (kolejka kroków?)")
    raise Przerwano(f"{nazwa}: {PROBY + 1} wciśnięć bez ruchu (klawisz nie działa albo pole zajęte)")


def faza_opoznienie(env, start, tryb, hp0, powt, zapisy):
    for k in SKOSY + ("Right",):
        for _ in range(powt):
            ruch(env, k, start, tryb, hp0, CISZA, zapisy, "opoznienie", None)
            ruch(env, PRZECIWNY[k], start, tryb, hp0, CISZA, zapisy, "opoznienie", None)


def faza_trasy(env, start, tryb, hp0, powt, zapisy, trasy):
    """Proste Right/Left (odniesienie kroku), potem dla każdego skosu: skos tam-z powrotem i
    dwa proste tam-z powrotem. Łańcuchowo (bez ciszy): ruch zaraz po zmianie pozycji."""
    t_zm = None
    for _ in range(max(3, powt + 2)):
        for k in ("Right", "Left"):
            t_zm = ruch(env, k, start, tryb, hp0, 0.0, zapisy, "lancuch", t_zm)
    env.spij(CISZA)
    for k in SKOSY:
        for wariant in ("skos", "proste"):
            for _ in range(powt):
                t_zm = None
                t0 = env.zegar()
                if wariant == "skos":
                    seria = [k, PRZECIWNY[k]]
                else:
                    a, b = rozloz(k)
                    seria = [a, b, PRZECIWNY[b], PRZECIWNY[a]]
                dlugosci = []
                for r in seria:
                    t_zm = ruch(env, r, start, tryb, hp0, 0.0, zapisy, "trasa-" + wariant, t_zm)
                    dlugosci.append(r)
                trasy.append(dict(skos=k, wariant=wariant, ruchy=dlugosci,
                                  do_ostatniej_zmiany=round(t_zm - t0, 3), ostatni=seria[-1]))
                env.spij(CISZA)


# --- analiza (czysta, testowana) ---

def _med(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs), 3) if xs else None


def analiza(zapisy, trasy, tryb="numpad"):
    wynik = {"tryb": tryb}
    per = {}
    for k in SKOSY:
        zk = [z for z in zapisy if z["faza"] == "opoznienie" and z["ruch"] == k]
        pierwsze = [z for z in zk if z["proba"] == 1]
        per[k] = dict(prob=len(pierwsze), ok=sum(1 for z in pierwsze if z["ok"]),
                      opoznienie_med=_med([z["opoznienie"] for z in pierwsze if z["ok"]]))
        per[k]["skutecznosc"] = round(per[k]["ok"] / per[k]["prob"], 3) if per[k]["prob"] else None
    wynik["kierunki"] = per
    pr = [z for z in zapisy if z["faza"] == "opoznienie" and z["ruch"] in ("Right", "Left") and z["proba"] == 1]
    wynik["opoznienie_prosty_med"] = _med([z["opoznienie"] for z in pr if z["ok"]])
    wynik["opoznienie_skos_med"] = _med([z["opoznienie"] for k in SKOSY for z in zapisy
                                         if z["faza"] == "opoznienie" and z["ruch"] == k and z["ok"] and z["proba"] == 1])
    # czas kroku: odstęp między zmianami, gdy ruch poszedł z pierwszego wciśnięcia (kolejkowany).
    # Odstęp przed ruchem N to czas trwania kroku N-1, więc przypisujemy go poprzedniemu ruchowi.
    lancuch = [z for z in zapisy if z["faza"] in ("lancuch", "trasa-skos", "trasa-proste")]
    proste, skosy = [], []
    for a, b in zip(lancuch, lancuch[1:]):
        if b["ok"] and b["proba"] == 1 and b["od_poprzedniej"] is not None and a["ok"]:
            (skosy if a["skos"] else proste).append(b["od_poprzedniej"])
    S, D = _med(proste), _med(skosy)
    wynik.update(krok_prosty_s=S, krok_skos_s=D, probek_prostych=len(proste), probek_skosow=len(skosy),
                 mnoznik=round(D / S, 2) if S and D else None)
    wciski = [z for z in zapisy if z["faza"] != "opoznienie"]
    pierwsze = [z for z in wciski if z["proba"] == 1]
    wynik["lancuch_odrzucone"] = round(1 - sum(1 for z in pierwsze if z["ok"]) / len(pierwsze), 3) if pierwsze else None
    wszystkie = [z for z in zapisy if z["skos"] and z["proba"] == 1]
    wynik["skutecznosc_skosu"] = round(sum(1 for z in wszystkie if z["ok"]) / len(wszystkie), 3) if wszystkie else None
    # trasy: czas do końca = czas do ostatniej zmiany + czas trwania ostatniego kroku
    def koniec(t):
        dl = D if t["ostatni"] in SKOSY else S
        return t["do_ostatniej_zmiany"] + (dl or 0.0)
    tr = {}
    for k in SKOSY:
        a = _med([koniec(t) for t in trasy if t["skos"] == k and t["wariant"] == "skos"])
        b = _med([koniec(t) for t in trasy if t["skos"] == k and t["wariant"] == "proste"])
        tr[k] = dict(skos_tam_z_powrotem=a, dwa_proste_tam_z_powrotem=b,
                     stosunek=round(a / b, 2) if a and b else None)
    wynik["trasy"] = tr
    stosunki = [v["stosunek"] for v in tr.values() if v["stosunek"]]
    wynik["stosunek_tras_med"] = _med(stosunki)
    dziala = all((v["skutecznosc"] or 0) >= MIN_SKUTECZNOSC for v in per.values())
    oplaca = None
    if wynik["mnoznik"] is not None:
        oplaca = wynik["mnoznik"] < 2 * PROG_OPLACALNOSCI
    if stosunki:
        oplaca = (statistics.median(stosunki) < PROG_OPLACALNOSCI) and bool(oplaca is not False)
    rek = {"klawisze_dzialaja": dziala, "skos_oplaca_sie": bool(oplaca) if oplaca is not None else None,
           "SKOS_TRYB": tryb if dziala else None,
           "SKOS_KROK_S": D, "KROK_PROSTY_S": S, "SKOS_MNOZNIK": wynik["mnoznik"]}
    if not dziala:
        rek["uwaga"] = "co najmniej jeden skos nie wykonuje się w >=90% wciśnięć: nie używać skosu"
    elif oplaca:
        rek["uwaga"] = ("skos szybszy niż dwa proste: w pościgu używać skos(), przewidywany czas kroku "
                        f"po skosie {D} s (x{wynik['mnoznik']} prostego)")
    else:
        rek["uwaga"] = ("skos nie szybszy niż dwa proste: zostać przy strzałkach; skos tylko, gdy "
                        "nie ma wolnego pola pośredniego (róg) albo przy ucieczce celu po skosie")
    wynik["rekomendacja"] = rek
    return wynik


def drukuj(w):
    print(f"\nTryb: {w['tryb']}")
    for k, v in w["kierunki"].items():
        print(f"  {k:10} wciśnięć {v['prob']:2}  ok {v['ok']:2}  skut. {v['skutecznosc']}  opóźn. med {v['opoznienie_med']}")
    print(f"  opóźnienie: prosty {w['opoznienie_prosty_med']} s, skos {w['opoznienie_skos_med']} s")
    print(f"  krok: prosty {w['krok_prosty_s']} s (n={w['probek_prostych']}), "
          f"skos {w['krok_skos_s']} s (n={w['probek_skosow']}), mnożnik {w['mnoznik']}")
    for k, v in w["trasy"].items():
        print(f"  trasa {k:10} skos {v['skos_tam_z_powrotem']} s, dwa proste {v['dwa_proste_tam_z_powrotem']} s, "
              f"stosunek {v['stosunek']}")
    print("Rekomendacja:", json.dumps(w["rekomendacja"], ensure_ascii=False))


def zapisz(katalog, dane):
    katalog = Path(katalog)
    katalog.mkdir(parents=True, exist_ok=True)
    plik = katalog / time.strftime("sonda-skosu-%Y%m%d-%H%M%S.json")
    plik.write_text(json.dumps(dane, ensure_ascii=False, indent=1))
    return plik


def sprawdz_pole(env, start):
    """3x3 wokół pozycji: wszystkie pola przechodnie wg mapy."""
    x, y, z = start
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if env.przechodnie(x + dx, y + dy, z) is not True:
                raise Przerwano(f"pole ({x + dx},{y + dy},{z}) nieprzechodnie albo nieznane na mapie: "
                                "stań na środku wolnego 3x3")


def uruchom(env, tryb="numpad", powt=3):
    """Cały pomiar na przygotowanym środowisku (Srodowisko + env.skos(nazwa, ms, tryb)).
    Zwraca (zapisy, trasy, przerwano)."""
    start = tuple(env.pozycja())
    hp0 = env.hp()
    zapisy, trasy, przerwano = [], [], None
    try:
        faza_opoznienie(env, start, tryb, hp0, powt, zapisy)
        faza_trasy(env, start, tryb, hp0, powt - 1 if powt > 2 else powt, zapisy, trasy)
    except (Przerwano, KeyboardInterrupt) as e:
        przerwano = str(e) or "Ctrl+C"
    finally:
        kal.wroc(env, start)
    return zapisy, trasy, przerwano


def main(argv):
    sucho = "--sucho" in argv
    powt = 2 if "--szybko" in argv else 3
    tryb = argv[argv.index("--tryb") + 1] if "--tryb" in argv else "numpad"
    if tryb not in ("numpad", "wsad"):
        print("--tryb: numpad albo wsad")
        return 2
    for w in kal.sprawdz_bezpieczenstwo():
        print("UWAGA:", w)
    env = kal.srodowisko_gry()
    import bot
    import klawisz_x11
    ekran = bot.ekran_gry()
    env.skos = lambda nazwa, ms, tr: klawisz_x11.skos(nazwa, ms, ekran=ekran, tryb=tr)
    start = tuple(env.pozycja())
    sprawdz_pole(env, start)
    kal._straz(env, env.hp(), start)
    print(f"Start {start}, HP {env.hp():.0f}%, tryb {tryb}. Kontrole OK." + (" (--sucho: koniec)" if sucho else ""))
    if tryb == "wsad":
        print("UWAGA: tryb wsad działa tylko przy wyłączonym czacie (litery nie mogą trafić na czat).")
    if sucho:
        return 0
    print("Za 5 s zaczynam (Ctrl+C przerywa; postać wróci na start).")
    time.sleep(5)
    zapisy, trasy, przerwano = uruchom(env, tryb, powt)
    if przerwano:
        print(f"PRZERWANO: {przerwano}")
    if not zapisy:
        return 1
    w = analiza(zapisy, trasy, tryb)
    w["przerwano"] = przerwano
    drukuj(w)
    plik = zapisz(kal.instancja.S.logi, {"start": list(start), "czas": time.strftime("%F %T"),
                                      "zapisy": zapisy, "trasy": trasy, "wynik": w})
    print("Zapisano:", plik)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
