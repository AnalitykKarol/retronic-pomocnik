"""Analityk telemetrii: agregaty liczy Python (telemetria.agreguj), Haiku (`claude -p`, bez narzędzi)
tylko interpretuje agregaty + najgorsze przypadki i zwraca JSON z problemami i opcjonalnie pokrętłami.

Wywołanie modelu: obiekt `model(prompt, system) -> (tekst, meta)` (mozg.Claude). Uruchamiany w wątku
z mozg.py: co 3-5 min oraz od razu przy anomalii (debounce 60 s, limit 15 wywołań/h).

Obserwator (klasa na końcu pliku) rozszerza Analityka: regularny cykl co ~60 s (RETRONIC_OBSERWATOR_S, min 30),
kompaktowe wejście liczone kodem, pomijanie modelu przy braku zmian, limit 100 wywołań/h.
`python3 -I analityk.py --raz` robi jeden cykl na istniejących plikach (debug, bez bota)."""
import json
import os
import random
import re
import sys
import threading
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # python3 -I nie dodaje katalogu skryptu

import instancja  # noqa: E402
import powiadom  # noqa: E402
import telemetria  # noqa: E402
from pokretla import ZAKRESY  # noqa: E402

LOGI = instancja.S.logi
CO_ILE = (900, 1200)               # 16.10: było (180, 300)
DEBOUNCE_S = 60
LIMIT_H = 15
OKNO_S = 600

SYSTEM = (
    "Jesteś analitykiem telemetrii bota do gry Tibia 7.4 (cavebot: chodzi po trasie, atakuje, zbiera loot). "
    "Dostajesz agregaty (liczone kodem, wiarygodne) i najgorsze przypadki. Wskaż realne problemy z "
    "dowodem z danych. Nie zmyślaj. Odpowiedz WYŁĄCZNIE jednym obiektem JSON: "
    '{"problemy":[{"opis":str,"dowod":str,"czestosc":str,"propozycja":str,"priorytet":1-3,'
    '"wymaga_kodu":bool}],"pokretla":{"NAZWA":liczba},"uzasadnienie_pokretel":str}. '
    "pokretla: opcjonalne, tylko z listy dozwolonych i w podanych zakresach, najwyżej 2 naraz, "
    "tylko gdy dane wyraźnie to uzasadniają. Pokrętła pościgu i dobijania (POGON_*, DOBICIE_*, POSCIG_OKNO) "
    "wolno tylko wydłużać względem domyślnej, nigdy skracać. "
    "Pusta lista problemów jest poprawną odpowiedzią."
)


def parsuj(tekst):
    """Wyciąga obiekt JSON z odpowiedzi modelu (także w ```). -> dict albo None."""
    m = re.search(r"\{.*\}", tekst or "", re.S)
    if not m:
        return None
    try:
        d = json.loads(m[0])
    except ValueError:
        return None
    if not isinstance(d, dict):
        return None
    pr = [p for p in d.get("problemy", []) if isinstance(p, dict) and p.get("opis")]
    return {"problemy": pr[:8], "pokretla": d.get("pokretla") if isinstance(d.get("pokretla"), dict) else {},
            "uzasadnienie_pokretel": str(d.get("uzasadnienie_pokretel", ""))[:300]}


class Analityk:
    def __init__(self, tele, pokretla, model, log=print, zegar=time.time, losuj=random.uniform, logi=LOGI):
        self.tele, self.pokretla, self.model, self.log = tele, pokretla, model, log
        self.zegar, self.logi = zegar, Path(logi)
        self.nastepne = self.zegar() + losuj(*CO_ILE)
        self.losuj = losuj
        self.ostatnie = float("-inf")
        self.wywolania = []          # czasy wywołań (limit/h)
        self.koszt = 0.0
        self.koniec = False
        self.zgloszone = set()       # wnioski, o których już powiadomiono

    def prompt(self, rek, sekundy):
        ag = telemetria.agreguj(rek, sekundy)
        return json.dumps({
            "agregaty": ag,
            "najgorsze_przypadki": telemetria.najgorsze(rek, 8),
            "aktywne_pokretla": self.pokretla.aktywne,
            "dozwolone_pokretla": {k: {"zakres": v, "domyslna": self.pokretla.domyslne.get(k)}
                                   for k, v in ZAKRESY.items() if k in self.pokretla.domyslne},
            "zakazane_pokretla": list(k for k, t in self.pokretla.zakazane.items() if t > self.zegar()),
        }, ensure_ascii=False)

    def moze(self, teraz):
        self.wywolania = [t for t in self.wywolania if teraz - t < 3600]
        return len(self.wywolania) < LIMIT_H and teraz - self.ostatnie >= DEBOUNCE_S

    def obieg(self):
        """Jeden obieg (wołany co kilka sekund z wątku). -> wynik analizy albo None."""
        teraz = self.zegar()
        rek = self.tele.okno(OKNO_S)
        po = self.pokretla.oczekuje
        if po:
            self.pokretla.ocen(telemetria.agreguj(self.tele.okno(max(60, teraz - po["t"])), max(60, teraz - po["t"])))
        powod = None
        an = telemetria.anomalie(list(self.tele.rek), teraz)
        if an:
            powod = "anomalia: " + "; ".join(an)
        elif teraz >= self.nastepne:
            powod = "okresowo"
        if not powod or not self.moze(teraz):
            return None
        self.nastepne = teraz + self.losuj(*CO_ILE)
        if not any(r["typ"] != "probka" for r in rek) and "anomalia" not in powod:
            return None      # nic się nie działo
        return self.analizuj(rek, powod)

    def analizuj(self, rek, powod):
        teraz = self.zegar()
        self.ostatnie = teraz
        self.wywolania.append(teraz)
        sek = max(60, min(OKNO_S, teraz - rek[0]["t"])) if rek else 60
        try:
            tekst, meta = self.model(self.prompt(rek, sek), SYSTEM)
        except Exception as e:
            self.log(f"ANALITYK błąd modelu: {e!r}")
            return None
        koszt = float((meta or {}).get("total_cost_usd") or 0)
        self.koszt += koszt
        wynik = parsuj(tekst)
        if wynik is None:
            self.log(f"ANALITYK: nie-JSON z modelu ({powod}): {tekst[:120]!r}")
            return None
        self.log(f"ANALITYK ({powod}): {len(wynik['problemy'])} problemów, koszt ${koszt:.4f} "
                 f"(sesja ${self.koszt:.3f}, {len(self.wywolania)}/{LIMIT_H} w godz.)")
        if wynik["pokretla"]:
            self.pokretla.zmien(wynik["pokretla"], wynik["uzasadnienie_pokretel"] or powod,
                                metryki=telemetria.agreguj(rek, sek))
        self.zapisz(wynik)
        return wynik

    def zapisz(self, wynik):
        kod = [p for p in wynik["problemy"] if p.get("wymaga_kodu")]
        if kod:
            dopisz_do_poprawy(kod, self.logi, self.zegar())
        if wynik["problemy"]:
            def prio(p):
                try:
                    return int(p.get("priorytet", 3))
                except (TypeError, ValueError):
                    return 3
            self.powiadom_wnioski(wynik, prio)
            p = min(wynik["problemy"], key=prio)
            try:
                (self.logi / "wniosek-ostatni.txt").write_text(
                    re.sub(r"\s+", " ", f"{p['opis']} -> {p.get('propozycja', '')}")[:160] + "\n")
            except OSError:
                pass

    def powiadom_wnioski(self, wynik, prio):
        """Powiadomienie o każdym nowym problemie z priorytetem 1-2 (wysoki/średni): co zauważył + co proponuje/zrobił."""
        try:
            zrobil = f" Zmiana pokręteł: {wynik['pokretla']}." if wynik.get("pokretla") else ""
            for p in wynik["problemy"]:
                nazwa = re.sub(r"\W+", " ", p["opis"].lower()).strip()[:80]
                if prio(p) > 2 or nazwa in self.zgloszone:
                    continue
                self.zgloszone.add(nazwa)
                powiadom.powiadom("Analityk: nowy wniosek", f"{p['opis']} -> {p.get('propozycja', '')}.{zrobil}",
                                  klucz="wniosek:" + nazwa[:40])
        except Exception:
            pass

    def watek(self, sprawdzaj=5.0, spij=time.sleep):
        while not self.koniec:
            try:
                self.obieg()
            except Exception as e:
                self.log(f"ANALITYK błąd: {e!r}")
            spij(sprawdzaj)

    def start(self):
        t = threading.Thread(target=self.watek, daemon=True)
        t.start()
        return t


def dopisz_do_poprawy(problemy, logi=LOGI, teraz=None):
    """Dopisuje do logi/do_poprawy.md; deduplikacja po znormalizowanym opisie."""
    plik = Path(logi) / "do_poprawy.md"
    try:
        stare = plik.read_text() if plik.exists() else ""
    except OSError:
        stare = ""
    norm = lambda s: re.sub(r"\W+", " ", s.lower()).strip()[:80]
    widziane = {norm(l[2:].split(" | ")[0].split("] ", 1)[-1]) for l in stare.splitlines() if l.startswith("- ")}
    nowe = []
    for p in problemy:
        if norm(p["opis"]) in widziane:
            continue
        widziane.add(norm(p["opis"]))
        nowe.append(f"- [{time.strftime('%Y-%m-%d %H:%M', time.localtime(teraz or time.time()))}] "
                    f"{p['opis']} | dowód: {p.get('dowod', '')} | propozycja: {p.get('propozycja', '')}")
    if nowe:
        with plik.open("a") as f:
            f.write("\n".join(nowe) + "\n")
    return nowe


# ---------------------------------------------------------------------------------------------
# Obserwator: tani, regularny, wnioski na bieżąco (jeden wątek zamiast starego rytmu analityka)
# ---------------------------------------------------------------------------------------------
OBS_CYKL_S = 600                  # 16.10: co 10 min (było 60 s); RETRONIC_OBSERWATOR_S nadpisuje
OBS_MIN_S = 30
OBS_LIMIT_H = 100
OBS_ALERT_DEDUP_S = 600
STATUSY = ("ok", "uwaga", "problem")
RE_LOG_WAZNE = re.compile(r"ALARM|Błąd|Zatrzymano|Koniec|Nie mogę|nieosiągaln", re.I)
RE_LOG_JEDZ = re.compile(r"Zjedzono|jedzeni|głód", re.I)
RE_LOG_POCH = re.compile(r"pochodn|torch", re.I)

SYSTEM_OBS = (
    "Jesteś obserwatorem bota do gry Tibia 7.4 (cavebot chodzi po trasie, walczy, zbiera loot). Co minutę "
    "dostajesz kompaktowy stan: ostatnia minuta, trend 5 min, zdarzenia, stan postaci, ostatnie wnioski. "
    "Wyciągnij jeden aktualny wniosek, oparty na liczbach z danych; nie zmyślaj i nie powtarzaj ostatnich "
    "wniosków bez nowej przesłanki. status: ok (działa normalnie), uwaga (coś odbiega, warto zerknąć), "
    "problem (wymaga reakcji człowieka lub poprawki). Odpowiedz WYŁĄCZNIE jednym obiektem JSON: "
    '{"status":"ok|uwaga|problem","wniosek":"1 zdanie","dowod":"liczby z danych",'
    '"akcje":[{"pokretlo":"NAZWA","wartosc":liczba}],"do_kodu":["opis poprawki w kodzie bota"]}. '
    "akcje: pusta lista, chyba że dane wyraźnie uzasadniają; najwyżej 1, tylko z dozwolone_pokretla i w "
    "podanym zakresie. do_kodu: tylko realne błędy kodu, zwykle pusta lista. "
    "Dobijanie: dobicie.5min to wskaźnik dobijania moby (niedobity mob wygląda jak bot i kosztuje exp). "
    "Wskaźnik poniżej 85% w oknie 5 min przy >=6 epizodach to status uwaga, poniżej 70% problem; w "
    "wniosku wymień najczęstszy powód (dobicie.5min.powod_top) i stracony exp, jeśli jest. "
    "Reguła pokręteł dobijania: przy niskim wskaźniku dobicia pokrętła mogą tylko WYDŁUŻAĆ pościg i "
    "zasięg dobijania (POGON_LIMIT, POGON_ZASIEG, POSCIG_OKNO w górę), nigdy ich skracać; kod odrzuca "
    "zmianę w złą stronę względem domyślnej. "
    "Świeżość: wiek_stanu_s to wiek danych o stanie cavebota, pozycji, HP, celu i mobach; "
    "zrodlo_stanu=telemetria znaczy próbka sprzed kilku sekund, inaczej stan jest STARY. Nie wyciągaj "
    "wniosków o stanie cavebota ani o mobach ze stanu starszego niż 15 s (wiek_stanu_s>15): nie twierdź "
    "wtedy, w jakim stanie jest cavebot ani co stoi obok. W razie rozbieżności między polami zaufaj "
    "telemetrii (zrodlo_stanu=telemetria). "
    "Brak jedzenia (log.jedzenie.brak) to tylko informacja: bot gra dalej, dopóki HP nie spadnie do progu "
    "ucieczki; nie podnoś z jego powodu statusu ponad ok i nie rób z niego problemu."
)

PK_INSTRUKCJA_OBS = (
    " PK: pole pk (pk_stan, karencja_pozostalo_s, wrogowie, pauza_pk_trwa_s). Stan cavebota PAUZA_PK przy "
    "karencja_pozostalo_s > 0 to stan ZAMIERZONY (bot czeka w depo po ucieczce przed graczem): nie zgłaszaj go, "
    "status ok. Alert (uwaga/problem) o PAUZA_PK tylko, gdy karencja_pozostalo_s == 0 i pauza_pk_trwa_s > 300. "
    "Brak pola pk albo null = UNKNOWN, nie zgaduj."
)


def pauza_pk_trwa_s(r300, teraz):
    """Ile s z rzędu (do 300) cavebot stoi w PAUZA_PK wg ostatnich próbek telemetrii; 0 = nie stoi."""
    probki = [r for r in r300 if r["typ"] == "probka"]
    if not probki or probki[-1].get("stan") != "PAUZA_PK":
        return 0
    od = probki[-1]["t"]
    for r in reversed(probki):
        if r.get("stan") != "PAUZA_PK":
            break
        od = r["t"]
    return round(teraz - od)


PROG_UCIECZKI_OBS = 30    # % HP: próg ucieczki bota (brak jedzenia podnosi status dopiero blisko niego)
MARGINES_JEDZENIA_OBS = 15
RE_JEDZENIE_TEKST = re.compile(r"jedzeni|głód|głod|glod|food|regeneracj", re.I)


def wygas_jedzenie(w, d, prog=PROG_UCIECZKI_OBS, margines=MARGINES_JEDZENIA_OBS):
    """Wniosek uwaga/problem o braku jedzenia przy HP > prog+margines nie podnosi statusu: ok, tylko info.
    -> True, gdy zmieniono. HP nieznane: bez zmian."""
    if w.get("status") not in ("uwaga", "problem"):
        return False
    tekst = f"{w.get('wniosek', '')} {w.get('dowod', '')}"
    if not RE_JEDZENIE_TEKST.search(tekst):
        return False
    hpy = []
    p = d.get("postac") if isinstance(d.get("postac"), dict) else {}
    for v in (p.get("hp_proc"), (d.get("minuta") or {}).get("hp_min")):
        if isinstance(v, (int, float)):
            hpy.append(v)
    if not hpy or min(hpy) <= prog + margines:
        return False
    w["status"] = "ok"
    w["wniosek"] = ("[info] " + w["wniosek"])[:220]
    w["do_kodu"] = []
    w["akcje"] = {}
    return True


STAN_SWIEZY_S = 3         # próbka telemetrii młodsza niż to = aktualny stan
RE_TW_STAN = re.compile(r"\b(?:w\s+stanie|stan(?:ie|u)?|cavebot(?:\s+w)?)\s+([A-ZĄĆĘŁŃÓŚŹŻ_]{3,})\b")
RE_TW_MOB = re.compile(r"\bstoi\s+([A-ZĄĆĘŁŃÓŚŹŻ][\w ]{1,20}?)(?=\s+(?:odl|w\s+odl|\d)|[,.;]|$)", re.U)
RE_TW_ODL = re.compile(r"\b([A-ZĄĆĘŁŃÓŚŹŻ][\wąćęłńóśźż]*(?: [A-Z][\wąćęłńóśźż]*)?)\s+odl\.?\s*(\d+)", re.U)
RE_CZAS_TRWANIA = re.compile(r"\bprzez\s+\d|\bod\s+\d+\s*(?:s|min)|\bw\s+ciągu|\bpo\s+\d+\s*(?:s|min)", re.I)

DOBICIE_UWAGA, DOBICIE_PROBLEM, DOBICIE_MIN_EPIZODOW = 85, 70, 6
_RANGA = {"ok": 0, "uwaga": 1, "problem": 2}


def ocena_dobicia(d):
    """d: dict z telemetria.dobicie. -> 'ok' | 'uwaga' | 'problem' (None, gdy za mało epizodów)."""
    if not d or (d.get("epizody") or 0) < DOBICIE_MIN_EPIZODOW or d.get("wskaznik") is None:
        return None
    if d["wskaznik"] < DOBICIE_PROBLEM:
        return "problem"
    if d["wskaznik"] < DOBICIE_UWAGA:
        return "uwaga"
    return "ok"


def dobicie_dla_modelu(tele):
    """Okno 5 min (exp referencyjny z całej sesji) + ocena wg progów."""
    try:
        d5 = tele.dobicie(300)
        out = {k: d5[k] for k in ("epizody", "zabite", "porzucone", "zgubione", "wskaznik", "med_do_zab_s",
                                  "p90_do_zab_s", "med_od30_s", "powod_top", "exp_zdobyty", "exp_stracony",
                                  "exp_utracony_proc")}
        out["ocena"] = ocena_dobicia(d5)
        s = tele.dobicie(None)
        out["sesja"] = {k: s[k] for k in ("epizody", "zabite", "porzucone", "zgubione", "wskaznik",
                                          "powod_top", "exp_stracony", "exp_utracony_proc")}
        tekst = telemetria.linia_dobicia(d5)
        if tekst and d5.get("exp_stracony"):
            out["stracone"] = f"stracone ~{d5['exp_stracony']} exp = {d5['exp_utracony_proc']}% potencjału"
        return out
    except Exception:
        return None


def norm_tekst(s):
    return re.sub(r"\W+", " ", str(s).lower()).strip()[:80]


def waliduj_obserwacje(tekst):
    """Odpowiedź modelu -> dict {status,wniosek,dowod,akcje(dict),do_kodu(list),bledy(list)} albo None.
    Pokrętła poza zakresem są odrzucane (zapisane w `bledy`), reszta odpowiedzi zostaje."""
    m = re.search(r"\{.*\}", tekst or "", re.S)
    if not m:
        return None
    try:
        d = json.loads(m[0])
    except ValueError:
        return None
    if not isinstance(d, dict):
        return None
    status = str(d.get("status", "")).strip().lower()
    wniosek = re.sub(r"\s+", " ", str(d.get("wniosek", ""))).strip()
    if status not in STATUSY or not wniosek:
        return None
    dowod = re.sub(r"\s+", " ", str(d.get("dowod", ""))).strip()
    surowe = {}
    akcje = d.get("akcje")
    if isinstance(akcje, dict):
        surowe = dict(akcje)
    elif isinstance(akcje, list):
        for a in akcje:
            if isinstance(a, dict) and "pokretlo" in a:
                surowe[str(a["pokretlo"])] = a.get("wartosc")
            elif isinstance(a, dict) and len(a) == 1:
                surowe.update(a)
    from pokretla import waliduj  # noqa: PLC0415
    ok, bledy = waliduj(surowe)
    if len(ok) > 1:                    # jedna zmiana naraz
        k = next(iter(ok))
        bledy.append(f"ponad limit 1 zmiany: odrzucono {[x for x in ok if x != k]}")
        ok = {k: ok[k]}
    kod = d.get("do_kodu")
    kod = [re.sub(r"\s+", " ", str(x)).strip()[:200] for x in kod if str(x).strip()][:3] \
        if isinstance(kod, list) else []
    return {"status": status, "wniosek": wniosek[:220], "dowod": dowod[:220], "akcje": ok,
            "do_kodu": kod, "bledy": bledy}


def _okno_stat(rek):
    """Kompaktowe liczby z listy rekordów jednego okna."""
    z = Counter(r["typ"] for r in rek)
    probki = [r for r in rek if r["typ"] == "probka"]
    hp = [r["hp"] for r in probki if r.get("hp") is not None]
    mana = [r["mana"] for r in probki if r.get("mana") is not None]
    loot = Counter(r.get("wynik") for r in rek if r["typ"] == "loot")
    odp = Counter(r.get("powod", "")[:30] for r in rek if r["typ"] == "odpuszczenie")
    return {"zabicia": z["zabicie"], "odpuszczenia": z["odpuszczenie"],
            "powody_odpuszczen": dict(odp.most_common(2)),
            "loot_ok": loot.get("ok", 0), "loot_brak_okna": loot.get("brak_okna", 0),
            "loot_inne": {k: v for k, v in loot.items() if k not in ("ok", "brak_okna")},
            "loot_przy_zywym": z["loot_przy_zywym"], "utkniecia": z["utkniecie"],
            "hp_min": min(hp) if hp else None, "hp_sr": round(sum(hp) / len(hp)) if hp else None,
            "mana_min": min(mana) if mana else None, "mana_sr": round(sum(mana) / len(mana)) if mana else None,
            "stany": dict(Counter(r["stan"] for r in probki).most_common(3))}


def czytaj_ogon(plik, n=300):
    try:
        return Path(plik).read_text(errors="replace").splitlines()[-n:]
    except OSError:
        return []


def ogon_cavebota(logi, teraz, okno_s=300):
    """Linie z logu cavebota (logi/ostatni) z ostatnich okno_s: ALARM/błędy, jedzenie, pochodnia."""
    logi = Path(logi)
    try:
        nazwa = (logi / "ostatni").read_text().strip()
        plik = Path(nazwa) if os.path.isabs(nazwa) else logi.parent / nazwa
    except OSError:
        return {"alarmy": [], "jedzenie": {}, "pochodnia": []}
    lt = time.localtime(teraz)
    teraz_s = lt.tm_hour * 3600 + lt.tm_min * 60 + lt.tm_sec
    wazne, jedz, poch = [], Counter(), []
    for l in czytaj_ogon(plik, 400):
        m = re.match(r"(\d\d):(\d\d):(\d\d) (.*)", l)
        if not m or " debug: " in f" {m[4]}":
            continue
        ts = int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3])
        if not 0 <= (teraz_s - ts) % 86400 <= okno_s:
            continue
        tr = m[4]
        if RE_LOG_WAZNE.search(tr):
            wazne.append(f"{m[1]}:{m[2]}:{m[3]} {tr[:110]}")
        if RE_LOG_JEDZ.search(tr):
            jedz["brak" if re.search(r"nic|głód", tr) else "zjedzono"] += 1
        if RE_LOG_POCH.search(tr):
            poch.append(tr[:80])
    return {"alarmy": wazne[-5:], "jedzenie": dict(jedz), "pochodnia": poch[-2:]}


def twierdzenia_sprzeczne(w, ost, teraz, swiezy_s=STAN_SWIEZY_S):
    """Wniosek (status uwaga/problem) twierdzi o BIEŻĄCYM stanie coś, co przeczy ostatniej próbce
    telemetrii? -> opis sprzeczności albo None. Bez świeżej próbki nie ocenia (None)."""
    if not ost or not 0 <= teraz - ost["t"] < swiezy_s:
        return None
    tekst = f"{w.get('wniosek', '')} {w.get('dowod', '')}"
    if RE_CZAS_TRWANIA.search(tekst):       # opis trwania/historii, nie bieżącego stanu
        return None
    for m in RE_TW_STAN.finditer(tekst):
        if m[1] != str(ost.get("stan")):
            return f"stan {m[1]} vs telemetria {ost.get('stan')}"
    moby = [x for x in ost.get("stwory") or [] if not x.get("gracz")]
    for m in RE_TW_MOB.finditer(tekst):
        nazwa = m[1].strip().lower()
        if not any(x["n"].lower() == nazwa for x in moby):
            return f"{m[1].strip()} nie ma w próbce (cel: {(ost.get('cel') or {}).get('nazwa')})"
    for m in RE_TW_ODL.finditer(tekst):
        nazwa, odl = m[1].lower(), int(m[2])
        if not any(x["n"].lower() == nazwa and x["odl"] == odl for x in moby):
            return f"{m[1]} odl {odl} nie zgadza się z próbką"
    return None


class Obserwator(Analityk):
    """Cykl co `cykl_s` s: Python składa kompaktowe wejście, Haiku zwraca status/wniosek/akcje/do_kodu.
    `zrodlo()` (opcjonalne) -> dict z danych spoza telemetrii: gracz, czat, gracze, cavebot, exp_na_h."""

    def __init__(self, tele, pokretla, model, log=print, zegar=time.time, logi=LOGI, zrodlo=None,
                 cykl_s=None, logi_we=None, limit_h=OBS_LIMIT_H):
        super().__init__(tele, pokretla, model, log=log, zegar=zegar, losuj=lambda a, b: a, logi=logi)
        if cykl_s is None:
            try:
                cykl_s = float(os.environ.get("RETRONIC_OBSERWATOR_S", OBS_CYKL_S))
            except ValueError:
                cykl_s = OBS_CYKL_S
        self.cykl_s = max(OBS_MIN_S, cykl_s)
        self.limit_h = limit_h
        self.zrodlo = zrodlo
        self.logi_we = Path(logi_we or logi)     # skąd czytamy logi/ostatni (--raz pisze gdzie indziej)
        self.nastepne = self.zegar() + self.cykl_s
        self.podpis = None
        self.wnioski = []            # ostatnie 3 wnioski (anty-powtórki)
        self.alerty = {}             # norm(wniosek) -> czas ostatniego zapisu w obserwator-alerty.log
        self.pominiete = 0

    # --- wejście ---
    def dane(self, teraz):
        r60, r300 = self.tele.okno(60), self.tele.okno(300)
        probki = [r for r in r60 if r["typ"] == "probka"]
        ost = probki[-1] if probki else None
        moby, obcy = [], []
        if ost:
            for w in ost["stwory"]:
                if w.get("gracz"):
                    if w["odl"] > 0:
                        obcy.append(w["n"])
                else:
                    moby.append(w)
        ex = {}
        if self.zrodlo:
            try:
                ex = self.zrodlo() or {}
            except Exception as e:
                self.log(f"OBSERWATOR: błąd źródła danych: {e!r}")
        lg = ogon_cavebota(self.logi_we, teraz)
        poz = self.pokretla
        # AKTUALNY stan z ostatniej próbki telemetrii; stary snapshot (zbuduj_stan) tylko awaryjnie
        wiek = round(teraz - ost["t"], 1) if ost else None
        swiezy = ost is not None and 0 <= wiek < STAN_SWIEZY_S
        if swiezy:
            cb_stan = ost.get("stan")
            postac = dict(ex.get("gracz") or {})
            if ost.get("hp") is not None:
                postac["hp_proc"] = ost["hp"]
            if ost.get("mana") is not None:
                postac["mana"] = ost["mana"]
            stan_zywy = {"zrodlo_stanu": "telemetria", "wiek_stanu_s": wiek, "poz": ost.get("poz"),
                         "cel": ost.get("cel")}
        else:
            cb_stan = ex.get("cavebot") or (ost or {}).get("stan")
            postac = ex.get("gracz")
            w_s = ex.get("wiek_s")
            if w_s is None and ost is not None:
                w_s = wiek
            stan_zywy = {"zrodlo_stanu": "STARY snapshot (brak świeżej telemetrii)" if ex.get("cavebot")
                         else "stara telemetria" if ost else "brak", "wiek_stanu_s": w_s}
        return {
            "minuta": _okno_stat(r60), "trend_5min": _okno_stat(r300),
            "cavebot": cb_stan, "stan_zywy": stan_zywy, "wiek_stanu_s": stan_zywy["wiek_stanu_s"],
            "zrodlo_stanu": stan_zywy["zrodlo_stanu"],
            "pobliskie_moby": {"liczba": len(moby), "najblizszy": (
                {"n": moby[0]["n"], "odl": moby[0]["odl"], "hp": moby[0].get("hp")} if moby else None)},
            "obcy_gracze_na_ekranie": sorted(set(obcy) | set(ex.get("gracze") or [])),
            "postac": postac, "exp_na_h": ex.get("exp_na_h"),
            "czat": ex.get("czat"), "log": lg, "dobicie": {"5min": dobicie_dla_modelu(self.tele)},
            "pokretla": {"aktywne": poz.aktywne,
                         "dozwolone": {k: {"zakres": v, "domyslna": poz.domyslne.get(k)}
                                       for k, v in ZAKRESY.items() if k in poz.domyslne},
                         "zakazane": [k for k, t in poz.zakazane.items() if t > teraz],
                         "oczekuje_oceny": bool(poz.oczekuje)},
            "ostatnie_wnioski": self.wnioski[-3:],
            **({"pk": {**(ex.get("pk") or {}), "pauza_pk_trwa_s": pauza_pk_trwa_s(r300, teraz)}}
               if getattr(poz.modul, "OBSERWATOR_PK_KONTEKST", 0) else {}),
        }

    @staticmethod
    def sygnatura(d, r60):
        """Podpis zmian: jeśli taki sam jak poprzedni cykl, model nie jest potrzebny."""
        zd = sorted((r["typ"], r["t"]) for r in r60 if r["typ"] != "probka")
        czat = d.get("czat")
        czat = [(w.get("autor"), w.get("tekst")) for w in czat[-4:]] if isinstance(czat, list) else czat
        return json.dumps([zd, d["cavebot"], d["obcy_gracze_na_ekranie"], d["pobliskie_moby"]["liczba"],
                           czat, d["log"]["alarmy"], d["pokretla"]["aktywne"], d["minuta"]["hp_min"] is not None
                           and d["minuta"]["hp_min"] < 50], default=str)

    # --- cykl ---
    def moze_obs(self, teraz):
        self.wywolania = [t for t in self.wywolania if teraz - t < 3600]
        return len(self.wywolania) < self.limit_h

    def obieg(self):
        teraz = self.zegar()
        po = self.pokretla.oczekuje
        if po:
            s = max(60, teraz - po["t"])
            self.pokretla.ocen(telemetria.agreguj(self.tele.okno(s), s))
        if teraz < self.nastepne:
            return None
        self.nastepne = teraz + self.cykl_s
        return self.cykl(teraz)

    def wiersz(self, teraz, **d):
        w = {"t": round(teraz), "godz": time.strftime("%H:%M:%S", time.localtime(teraz)), **d,
             "koszt": d.get("koszt", 0.0), "suma": round(self.koszt, 4), "wywolan_h": len(self.wywolania)}
        try:
            self.logi.mkdir(exist_ok=True)
            with (self.logi / "obserwator.jsonl").open("a") as f:
                f.write(json.dumps(w, ensure_ascii=False, separators=(",", ":")) + "\n")
        except OSError:
            pass
        return w

    def cykl(self, teraz):
        d = self.dane(teraz)
        r60 = self.tele.okno(60)
        pod = self.sygnatura(d, r60)
        if pod == self.podpis:
            self.pominiete += 1
            return self.wiersz(teraz, status="bez_zmian", pominiete=self.pominiete)
        if not self.moze_obs(teraz):
            return self.wiersz(teraz, status="limit_h", limit=self.limit_h)
        self.podpis = pod
        self.wywolania.append(teraz)
        try:
            system = SYSTEM_OBS
            if d.get("pk") is not None:
                system += PK_INSTRUKCJA_OBS
                self.log(f"OBSERWATOR: kontekst PK: stan={d['pk'].get('pk_stan')} karencja={d['pk'].get('karencja_pozostalo_s')} s")
            tekst, meta = self.model(json.dumps(d, ensure_ascii=False), system)
        except Exception as e:
            self.log(f"OBSERWATOR błąd modelu: {e!r}")
            return self.wiersz(teraz, status="blad_modelu", blad=repr(e)[:120])
        koszt = float((meta or {}).get("total_cost_usd") or 0)
        self.koszt += koszt
        w = waliduj_obserwacje(tekst)
        if w is None:
            self.log(f"OBSERWATOR: niepoprawny JSON z modelu: {str(tekst)[:100]!r}")
            return self.wiersz(teraz, status="blad_json", koszt=koszt, surowe=str(tekst)[:120])
        # zabezpieczenie: twierdzenie o bieżącym stanie sprzeczne z najświeższą próbką = nieaktualne
        if w["status"] in ("uwaga", "problem"):
            probki = [r for r in self.tele.okno(10) if r["typ"] == "probka"]
            sprz = twierdzenia_sprzeczne(w, probki[-1] if probki else None, teraz)
            if sprz:
                self.log(f"OBSERWATOR: nieaktualny wniosek odrzucony ({sprz}): {w['wniosek']}")
                w["status"] = "ok"
                w["wniosek"] = ("[nieaktualne] " + w["wniosek"])[:220]
                w["do_kodu"] = []
                w["akcje"] = {}
                w["nieaktualne"] = sprz
        # brak jedzenia przy HP wyraźnie nad progiem ucieczki: tylko info, status ok
        if wygas_jedzenie(w, d):
            self.log("OBSERWATOR: brak jedzenia przy HP nad progiem: tylko info (status ok).")
        # twarda podłoga: wskaźnik dobicia poniżej progów podnosi status, niezależnie od modelu
        ocena = (d.get("dobicie", {}).get("5min") or {}).get("ocena")
        if ocena in ("uwaga", "problem") and _RANGA[w["status"]] < _RANGA[ocena]:
            db = d["dobicie"]["5min"]
            w["status"] = ocena
            dod = f" Dobicie {db['wskaznik']}% ({db['zabite']}/{db['epizody']}), powód: {db.get('powod_top') or '?'}."
            w["wniosek"] = (w["wniosek"].rstrip() + dod)[:220]
        for b in w["bledy"]:
            self.log(f"OBSERWATOR: akcja odrzucona: {b}")
        if w["akcje"]:
            try:
                zm = self.pokretla.zmien(w["akcje"], w["wniosek"], metryki=telemetria.agreguj(
                    self.tele.okno(300), 300))
            except Exception as e:
                self.log(f"OBSERWATOR: zmiana pokręteł nie powiodła się: {e!r}")
                zm = []
            w["zmienione"] = zm
        self.log(f"OBSERWATOR [{w['status']}]: {w['wniosek']} (${koszt:.4f}, sesja ${self.koszt:.3f}, "
                 f"{len(self.wywolania)}/{self.limit_h} w godz.)")
        if w.get("nieaktualne"):     # bez alertu, powiadomienia, plików ostatni ani anty-powtórek
            return self.wiersz(teraz, status="nieaktualne", wniosek=w["wniosek"], dowod=w["dowod"],
                               powod=w["nieaktualne"], koszt=round(koszt, 5))
        self.wnioski = (self.wnioski + [f"{w['status']}: {w['wniosek']}"[:160]])[-3:]
        self.zapisz_obs(w, teraz)
        return self.wiersz(teraz, status=w["status"], wniosek=w["wniosek"], dowod=w["dowod"],
                           akcje=w["akcje"], do_kodu=w["do_kodu"], koszt=round(koszt, 5))

    def zapisz_obs(self, w, teraz):
        linia = re.sub(r"\s+", " ", ("" if w["status"] == "ok" else f"[{w['status']}] ") + w["wniosek"])[:200]
        try:
            self.logi.mkdir(exist_ok=True)
            for n in ("obserwator-ostatni.txt", "wniosek-ostatni.txt"):   # panel/tooltip czyta drugi
                (self.logi / n).write_text(linia + "\n")
        except OSError:
            pass
        if w["do_kodu"]:
            dopisz_do_poprawy([{"opis": o, "dowod": w["dowod"], "propozycja": ""} for o in w["do_kodu"]],
                              self.logi, teraz)
        if w["status"] == "ok":
            return
        klucz = norm_tekst(w["wniosek"])
        if teraz - self.alerty.get(klucz, float("-inf")) >= OBS_ALERT_DEDUP_S:
            self.alerty[klucz] = teraz
            try:
                with (self.logi / "obserwator-alerty.log").open("a") as f:
                    f.write(re.sub(r"\s+", " ", f"{time.strftime('%H:%M:%S', time.localtime(teraz))} "
                                   f"[{w['status']}] {w['wniosek']} | {w['dowod']}") + "\n")
            except OSError:
                pass
            if w["status"] == "problem":
                try:
                    powiadom.powiadom("Obserwator: problem", w["wniosek"], "normal", klucz="obs:" + klucz[:40])
                except Exception:
                    pass


def _raz():
    """Jeden cykl na istniejących plikach (bez bota): rekordy z dzisiejszego telemetria-*.jsonl."""
    pliki = sorted(LOGI.glob("telemetria-*.jsonl"))
    rek = []
    for l in czytaj_ogon(pliki[-1], 4000) if pliki else []:
        try:
            r = json.loads(l)
            if isinstance(r, dict) and "t" in r and "typ" in r:
                rek.append(r)
        except ValueError:
            pass
    if not rek:
        print("Brak telemetrii w logi/.")
        return 1
    t_koniec = rek[-1]["t"]
    tele = telemetria.Telemetria(LOGI, zegar=lambda: t_koniec, zapis=False)
    tele.rek.extend(rek)
    import mozg  # noqa: PLC0415
    import types  # noqa: PLC0415
    import cavebot  # noqa: PLC0415
    from pokretla import Pokretla  # noqa: PLC0415
    os.environ["RETRONIC_POWIADOMIENIA"] = "0"
    import tempfile  # noqa: PLC0415
    pk = Pokretla(cavebot, plik=Path(tempfile.mkdtemp()) / "na_zywo.json", log=lambda *a: None)  # bez ruszania prawdziwego pliku
    ob = Obserwator(tele, pk, mozg.Claude(), log=print, zegar=lambda: t_koniec,
                    logi=Path(tempfile.mkdtemp()), logi_we=LOGI)   # wyniki tylko na stdout, nie do logi/
    w = ob.cykl(t_koniec)
    print(json.dumps(w, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    if "--raz" in sys.argv:
        sys.exit(_raz())
    print(__doc__)
