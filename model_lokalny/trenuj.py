"""Trening offline: python3 -I model_lokalny/trenuj.py D1|D2 [--logi DIR] [--wyjscie DIR] [--od RRRRMMDD]

Czyta telemetrię (tylko odczyt), buduje zbiór, dzieli PO SESJACH (ostatnie sesje = test), porównuje z baseline,
zapisuje <wyjscie>/<D>.json (wagi) i <wyjscie>/raport_<D>.md. Nie dotyka bota ani gry.
"""
import argparse
import os
import sys
import time

sys.dont_write_bytecode = True
_KORZEN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _KORZEN not in sys.path:  # python3 -I nie dodaje katalogu skryptu do sys.path
    sys.path.insert(0, _KORZEN)

import numpy as np

from model_lokalny import model as M
from model_lokalny import zbior as Z

UDZIAL_TESTU = 0.25     # ostatnie sesje, aż do ~25% zdarzeń
UDZIAL_WALID = 0.2      # z części treningowej: ostatnie sesje do wyboru hiperparametrów
ZIARNO = 0
FOLDY = 5

SIATKA_LR = [{"l2": l} for l in (1.0, 10.0, 100.0, 1000.0)]
SIATKA_MLP = [{"ukryte": u, "l2": l, "epoki": e} for u in ((16,), (16, 16), (32, 32)) for l in (10.0, 100.0)
              for e in (60, 150)]


def podzial_sesji(sesje, t, udzial):
    """Ostatnie (chronologicznie) sesje, które łącznie dają >= udzial zdarzeń. Zwraca maskę 'koniec'."""
    sesje = np.array(sesje, dtype=object)
    t = np.asarray(t, dtype=float)
    kolej = sorted(set(sesje.tolist()), key=lambda s: t[sesje == s].min())
    cel = udzial * len(sesje)
    wzial, maska = 0, np.zeros(len(sesje), dtype=bool)
    for s in reversed(kolej[1:]):  # zawsze zostaw co najmniej pierwszą sesję w części początkowej
        if wzial >= cel:
            break
        m = sesje == s
        maska |= m
        wzial += int(m.sum())
    return maska


def zrob(rodzaj, par):
    if rodzaj == "lr":
        return M.RegresjaLogistyczna(ziarno=ZIARNO, **par)
    return M.MLP(ziarno=ZIARNO, **par)


def wybierz_hiper(rodzaj, X, y, maska_walid):
    """Siatka -> najlepszy (po log-loss na walidacji z ostatnich sesji treningu). Zwraca (parametry, log-loss)."""
    siatka = SIATKA_LR if rodzaj == "lr" else SIATKA_MLP
    best = None
    for par in siatka:
        m = zrob(rodzaj, par).fit(X[~maska_walid], y[~maska_walid])
        ll = M.log_loss(y[maska_walid], m.predict_proba(X[maska_walid]))
        if best is None or ll < best[1]:
            best = (par, ll)
    return best


def metryki(y, p):
    return {"log_loss": M.log_loss(y, p), "auc": M.auc(y, p), "trafnosc": M.trafnosc(y, p)}


def cv_sesje(rodzaj, par, X, y, sesje, t, k=FOLDY):
    """Walidacja krzyżowa grupowana po sesjach (chronologicznie sąsiednie sesje w jednym foldzie).
    Zwraca (out-of-fold p, maski foldów, modele)."""
    sesje = np.array(sesje, dtype=object)
    kolej = sorted(set(sesje.tolist()), key=lambda s: np.asarray(t)[sesje == s].min())
    foldy = [kolej[i::k] for i in range(k)]
    oof = np.full(len(y), np.nan)
    maski, modele = [], []
    for f in foldy:
        mt = np.isin(sesje, f)
        if mt.sum() == 0 or (~mt).sum() == 0:
            continue
        m = zrob(rodzaj, par).fit(X[~mt], y[~mt])
        oof[mt] = m.predict_proba(X[mt])
        maski.append(mt)
        modele.append(m)
    return oof, maski, modele


def czas_inferencji_ms(model, x, powt=5, n=2000):
    """Mediana czasu jednej predykcji (ms), 1 próbka."""
    wyniki = []
    for _ in range(powt):
        t0 = time.perf_counter()
        for _ in range(n):
            model.predict_proba(x)
        wyniki.append((time.perf_counter() - t0) / n * 1000.0)
    return float(np.median(wyniki))


def analiza_wyboru(zb, ix, model):
    """D1: czy model wybrałby innego kandydata niż bot (na zdarzeniach `ix`) i jaki ma przewidywany wynik.
    Uwaga: wynik znamy tylko dla wybranego przez bota — to NIE jest dowód, że wybór modelu byłby lepszy."""
    n = n2 = inny = inny_nie_najbl = pick_najbl = 0
    p_bot, p_mod, p_bot_inny, p_mod_inny = [], [], [], []
    for i in ix:
        C = zb.kandydaci[i]
        p = model.predict_proba(C)
        n += 1
        if len(C) < 2:
            continue
        n2 += 1
        mm = int(np.argmax(p))
        bot = zb.wybrany[i]
        p_bot.append(p[bot])
        p_mod.append(p[mm])
        pick_najbl += int(mm == zb.najblizszy[i])
        if mm != bot and p[mm] > p[bot]:
            inny += 1
            p_bot_inny.append(p[bot])
            p_mod_inny.append(p[mm])
    sr = lambda a: float(np.mean(a)) if a else None
    return {"zdarzenia": n, "z_wieloma_kandydatami": n2, "model_wybralby_innego": inny,
            "odsetek_innego": inny / n2 if n2 else None, "model_wybralby_najblizszego": pick_najbl,
            "sr_p_bota": sr(p_bot), "sr_p_modelu": sr(p_mod),
            "sr_p_bota_gdy_inny": sr(p_bot_inny), "sr_p_modelu_gdy_inny": sr(p_mod_inny)}


def f(v, n=4):
    return "—" if v is None else ("%." + str(n) + "f") % v


def trenuj(rodzaj_zb, rekordy, wyjscie, info_wejscia=None):
    """Cały przebieg dla D1 albo D2. Zwraca (słownik wyniku, tekst raportu)."""
    zb, stat = Z.zbuduj_d1(rekordy) if rodzaj_zb == "D1" else Z.zbuduj_d2(rekordy)
    if len(zb) < 40 or len(set(zb.y)) < 2:
        raise SystemExit("za mało danych w zbiorze %s: %d wierszy, klasy %s" % (rodzaj_zb, len(zb), sorted(set(zb.y))))
    X, y, ses, t = zb.X, zb.Y, zb.sesja, zb.t
    maska_test = podzial_sesji(ses, t, UDZIAL_TESTU)
    Xtr, ytr, ses_tr, t_tr = X[~maska_test], y[~maska_test], np.array(ses, dtype=object)[~maska_test], np.array(t)[~maska_test]
    Xte, yte = X[maska_test], y[maska_test]
    maska_walid = podzial_sesji(ses_tr, t_tr, UDZIAL_WALID)

    # baseline
    baza_const = float(ytr.mean())
    pb_const = np.full(len(yte), baza_const)
    baseline = {"stala_czestosc": metryki(yte, pb_const)}
    # baseline „tylko odległość”: częstość sukcesu dla danej odl (kolumna 0) z treningu, brak wartości -> stała
    o_tr, o_te = Xtr[:, 0].astype(int), Xte[:, 0].astype(int)
    tab = {o: float(ytr[o_tr == o].mean()) for o in set(o_tr.tolist())}
    baseline["tylko_odleglosc"] = metryki(yte, np.array([tab.get(o, baza_const) for o in o_te]))
    if rodzaj_zb == "D1":
        nb = np.array([zb.wybrany[i] == zb.najblizszy[i] for i in range(len(zb))], dtype=bool)
        r_n = float(ytr[nb[~maska_test]].mean()) if nb[~maska_test].any() else baza_const
        r_i = float(ytr[~nb[~maska_test]].mean()) if (~nb[~maska_test]).any() else baza_const
        pb_n = np.where(nb[maska_test], r_n, r_i)
        baseline["najblizszy_kandydat"] = metryki(yte, pb_n)
        baseline["najblizszy_kandydat"]["wyjasnienie"] = (
            "częstość sukcesu osobno gdy bot wybrał najbliższego (%.3f) i gdy nie (%.3f), z części treningowej" % (r_n, r_i))

    # hiperparametry (walidacja z końca treningu) i wynik na teście
    wyniki, modele, hip = {}, {}, {}
    for rodzaj in ("lr", "mlp"):
        par, ll_w = wybierz_hiper(rodzaj, Xtr, ytr, maska_walid)
        m = zrob(rodzaj, par).fit(Xtr, ytr)
        wyniki[rodzaj] = metryki(yte, m.predict_proba(Xte))
        wyniki[rodzaj]["log_loss_walidacja"] = ll_w
        modele[rodzaj], hip[rodzaj] = m, par
    # stała częstość na walidacji (do wyboru zwycięzcy: model musi pobić baseline, inaczej i tak raportujemy)
    wybrany = min(("lr", "mlp"), key=lambda k: wyniki[k]["log_loss_walidacja"])

    # walidacja krzyżowa po sesjach dla obu modeli (stabilniejsza niż mały test)
    cv = {}
    for rodzaj in ("lr", "mlp"):
        oof, maski, mods = cv_sesje(rodzaj, hip[rodzaj], X, y, ses, t)
        ok = ~np.isnan(oof)
        # baseline w każdym foldzie: częstość z pozostałych
        pbc = np.full(len(y), np.nan)
        for mk in maski:
            pbc[mk] = y[~mk].mean()
        cv[rodzaj] = {"log_loss": M.log_loss(y[ok], oof[ok]), "auc": M.auc(y[ok], oof[ok]),
                      "trafnosc": M.trafnosc(y[ok], oof[ok]), "log_loss_stala": M.log_loss(y[ok], pbc[ok]),
                      "auc_foldy": [M.auc(y[mk], oof[mk]) for mk in maski], "n": int(ok.sum())}
        cv[rodzaj]["_mods"], cv[rodzaj]["_maski"] = mods, maski

    # ważność cech
    lr = modele["lr"]
    waz_lr = (lr.w).tolist()
    waz_perm = M.waznosc_permutacyjna(modele[wybrany], Xte, yte, ziarno=ZIARNO)

    # D1: analiza wyboru na teście i w CV (out-of-fold)
    wybor = None
    if rodzaj_zb == "D1":
        ix_test = np.where(maska_test)[0].tolist()
        wybor = {"test": analiza_wyboru(zb, ix_test, modele[wybrany])}
        agr = None
        for mod, mk in zip(cv[wybrany]["_mods"], cv[wybrany]["_maski"]):
            a = analiza_wyboru(zb, np.where(mk)[0].tolist(), mod)
            if agr is None:
                agr = {k: ([] if "sr_" in k else 0) for k in a}
            for k, v in a.items():
                if "sr_" in k:
                    if v is not None:
                        agr[k].append((v, a["model_wybralby_innego"] if "inny" in k or "gdy" in k else a["z_wieloma_kandydatami"]))
                elif v is not None:               # fold bez zdarzeń z >=2 kandydatami: odsetek None
                    agr[k] += v
        for k in list(agr):
            if "sr_" in k:
                w = sum(c for _, c in agr[k]) or 0
                agr[k] = sum(v * c for v, c in agr[k]) / w if w else None
        agr["odsetek_innego"] = agr["model_wybralby_innego"] / agr["z_wieloma_kandydatami"] if agr["z_wieloma_kandydatami"] else None
        wybor["cv_oof"] = agr

    czas = czas_inferencji_ms(modele[wybrany], Xte[0])
    czas_inne = {k: czas_inferencji_ms(modele[k], Xte[0]) for k in ("lr", "mlp")}

    wynik = {"zbior": rodzaj_zb, "wersja": 1, "cechy": zb.nazwy, "wybrany": wybrany,
             "model": modele[wybrany].do_slownika(),
             "inny_model": modele["mlp" if wybrany == "lr" else "lr"].do_slownika(),
             "metryki_test": wyniki, "baseline_test": baseline, "hiperparametry": {k: _jsonuj(v) for k, v in hip.items()},
             "statystyki_zbioru": stat, "czas_inferencji_ms": czas,
             "podzial": {"n_trening": int((~maska_test).sum()), "n_test": int(maska_test.sum())}}
    for k in cv:
        cv[k].pop("_mods"), cv[k].pop("_maski")
    wynik["cv_sesje"] = cv

    rap = raport(rodzaj_zb, zb, stat, maska_test, maska_walid, ytr, yte, baseline, wyniki, cv, hip, wybrany,
                 waz_lr, waz_perm, wybor, czas, czas_inne, info_wejscia)
    return wynik, rap


def _jsonuj(par):
    return {k: (list(v) if isinstance(v, tuple) else v) for k, v in par.items()}


def raport(nazwa, zb, stat, maska_test, maska_walid, ytr, yte, baseline, wyniki, cv, hip, wybrany,
           waz_lr, waz_perm, wybor, czas, czas_inne, info):
    L = []
    a = L.append
    opis = {"D1": "wybór celu", "D2": "pościg"}[nazwa]
    a("# Raport modelu lokalnego %s (%s) — krok B, przymiarka offline" % (nazwa, opis))
    a("")
    a("Dane z telemetrii (tylko odczyt); opcje odtworzone z najbliższej wcześniejszej `probka` — przybliżenie.")
    if info:
        a("Wejście: %s" % info)
    a("")
    a("## Zbiór")
    a("")
    for k, v in stat.items():
        a("- %s: %s" % (k, v))
    a("")
    ses = set(zb.sesja)
    a("Wiersze użyte: **%d**, sesji: %d. Odsetek etykiety 1: %.3f." % (len(zb), len(ses), float(zb.Y.mean())))
    a("")
    a("## Podział (po sesjach, nie losowo)")
    a("")
    a("- trening: %d wierszy (odsetek 1: %.3f); z tego walidacja do doboru hiperparametrów (ostatnie sesje): %d wierszy"
      % (len(ytr), float(ytr.mean()), int(maska_walid.sum())))
    a("- test: %d wierszy (ostatnie sesje, odsetek 1: %.3f)" % (len(yte), float(yte.mean())))
    a("")
    a("## Metryki na teście")
    a("")
    a("| model | log-loss | AUC | trafność |")
    a("|---|---|---|---|")
    for k, m in baseline.items():
        a("| baseline: %s | %s | %s | %s |" % (k, f(m["log_loss"]), f(m["auc"]), f(m["trafnosc"])))
    for k in ("lr", "mlp"):
        m = wyniki[k]
        a("| %s %s%s | %s | %s | %s |" % ("regresja logistyczna" if k == "lr" else "MLP", _hp(hip[k]),
                                         " (wybrany)" if k == wybrany else "", f(m["log_loss"]), f(m["auc"]),
                                         f(m["trafnosc"])))
    for k, m in baseline.items():
        if m.get("wyjasnienie"):
            a("")
            a("Baseline `%s`: %s." % (k, m["wyjasnienie"]))
    a("")
    a("Wybór zwycięzcy: najniższy log-loss na walidacji (nie na teście).")
    a("")
    a("## Walidacja krzyżowa po sesjach (%d foldów, out-of-fold)" % FOLDY)
    a("")
    a("| model | log-loss | log-loss stałej | AUC | trafność | AUC per fold |")
    a("|---|---|---|---|---|---|")
    for k in ("lr", "mlp"):
        c = cv[k]
        a("| %s | %s | %s | %s | %s | %s |" % (k, f(c["log_loss"]), f(c["log_loss_stala"]), f(c["auc"]), f(c["trafnosc"]),
                                              ", ".join(f(x, 3) for x in c["auc_foldy"])))
    a("")
    a("## Ważność cech")
    a("")
    a("| cecha | waga LR (po standaryzacji) | spadek AUC po przetasowaniu (%s, test) |" % wybrany)
    a("|---|---|---|")
    for i, n in enumerate(zb.nazwy):
        a("| %s | %s | %s |" % (n, f(waz_lr[i], 3), f(waz_perm[i], 4)))
    a("")
    if wybor:
        a("## D1: czy model wybrałby innego kandydata niż bot")
        a("")
        a("Model punktuje wszystkich kandydatów z próbki; bierzemy argmax. **Wynik znamy tylko dla celu wybranego przez bota** —")
        a("przewidywania dla innych kandydatów są ekstrapolacją (problem bandyty), nie dowodem lepszego wyboru.")
        a("")
        for etyk, w in (("test", wybor["test"]), ("CV out-of-fold (wszystkie sesje)", wybor["cv_oof"])):
            a("- **%s**: zdarzeń %s, z >=2 kandydatami %s; model wybrałby innego: %s (%s); model wybrałby najbliższego: %s;"
              % (etyk, w["zdarzenia"], w["z_wieloma_kandydatami"], w["model_wybralby_innego"], f(w["odsetek_innego"], 3),
                 w["model_wybralby_najblizszego"]))
            a("  średnie P(zabity<=15 s): cel bota %s, cel modelu %s; tylko gdy inny: bot %s, model %s"
              % (f(w["sr_p_bota"], 3), f(w["sr_p_modelu"], 3), f(w["sr_p_bota_gdy_inny"], 3), f(w["sr_p_modelu_gdy_inny"], 3)))
        a("")
    a("## Czas inferencji (1 próbka, CPU, numpy)")
    a("")
    a("- wybrany (%s): %.4f ms; lr: %.4f ms; mlp: %.4f ms (cel < 0,1 ms)" % (wybrany, czas, czas_inne["lr"], czas_inne["mlp"]))
    a("")
    a("## Zastrzeżenia")
    a("")
    a("- Etykieta znana tylko dla opcji, którą wybrał bot (selekcja); model uczy się „co się udaje po wyborze bota”.")
    a("- Cecha `droga` (długość A*) pominięta: w telemetrii 75% wartości to 0 także dla odległych celów — semantyka UNKNOWN.")
    zer = {}
    for s_, y_ in zip(zb.sesja, zb.y):
        if y_ == 0:
            zer[s_] = zer.get(s_, 0) + 1
    if zer:
        a("- Etykiety 0 skupione: najwięcej w jednej sesji %d z %d (sesji z etykietą 0: %d) — sygnał może odzwierciedlać pojedyncze epizody."
          % (max(zer.values()), sum(zer.values()), len(zer)))
    a("- Mało sesji (%d), test to ostatnie sesje: wynik zależy od podziału; patrz CV." % len(ses))
    a("- Model trenowany na części treningowej; do wdrożenia wymaga ponownego treningu na całości i trybu cienia.")
    return "\n".join(L) + "\n"


def _hp(par):
    return str({k: (list(v) if isinstance(v, tuple) else v) for k, v in par.items()})


def main(argv=None):
    ap = argparse.ArgumentParser(description="Trening lokalnego modelu D1/D2 z telemetrii (offline).")
    ap.add_argument("zbior", choices=["D1", "D2"])
    ap.add_argument("--logi", default=os.path.join(_KORZEN, "logi"))
    ap.add_argument("--wyjscie", default=os.path.join(_KORZEN, "model"))
    ap.add_argument("--od", default=None, help="RRRRMMDD: tylko pliki telemetria-RRRRMMDD.jsonl od tej daty")
    a = ap.parse_args(argv)
    t0 = time.time()
    rek, st = Z.wczytaj_telemetrie(a.logi, a.od)
    if not rek:
        raise SystemExit("brak telemetrii w %s" % a.logi)
    os.makedirs(a.wyjscie, exist_ok=True)
    wynik, rap = trenuj(a.zbior, rek, a.wyjscie, "%s (pliki: %d, rekordów: %d, złe linie: %d, od: %s)"
                        % (a.logi, st["pliki"], st["rekordy"], st["zle_linie"], a.od or "początek"))
    M.zapisz_json(os.path.join(a.wyjscie, a.zbior + ".json"), wynik)
    with open(os.path.join(a.wyjscie, "raport_%s.md" % a.zbior), "w", encoding="utf-8") as fh:
        fh.write(rap)
    print(rap)
    print("zapisano %s i raport_%s.md w %s (%.1f s)" % (a.zbior + ".json", a.zbior, a.wyjscie, time.time() - t0))


if __name__ == "__main__":
    main()
