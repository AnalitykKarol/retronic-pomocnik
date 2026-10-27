#!/usr/bin/env python3
"""Kontrola okien po starcie (Karol 22.10: po padzie komputera klienci wystartowali od zera, minimapa była rozwinięta, plecaka
na łup nie było otwartego i bot chodził bez lootu: wydra "Loot: brak_plecaka" x16, UH "brak_plecaka (zero lub kilka okien plecaka)").

WYMAGANY UKŁAD (to, na czym stoją loot, UH i serwis):
- minimapa zwinięta albo wyłączona (rozwinięta zabiera ok. 130 px panelu: okna plecaków wypychane w dół, a stała pozycja plecaka
  w ekwipunku `loot.SLOT_PLECAKA_EKWIPUNEK` trafia w pustkę);
- dokładnie JEDNO okno plecaka łupu (rola "plecak" wg `loot.rola_kontenera`: nazwa backpack/bag, nie pojemnik na runy); loot
  przenosi łup tylko do niego, a `uh._plecak` przerywa runę przy zerze albo dwóch;
- gdy robimy runy: osobne okno na runy (Purple backpack albo plecak z samymi runami) - to tylko ostrzeżenie, bez naprawy.
Okna zwłok i depo (locker, depot chest) są w porządku w każdej liczbie: ich pilnują loot i serwis.

CO KONTROLA ROBI (zrzut + odczyt kontenerów z pamięci klienta przez strażnika; zero klików przy samym sprawdzaniu):
  minimapa rozwinięta  -> naprawa: klik "-" w nagłówku panelu (`serwis_akcje.przycisk_zwin_minimape`), sprawdzenie zrzutem;
  brak okna plecaka    -> naprawa: Ctrl+klik plecaka w ekwipunku (pozycja z `uklad_panelu`, nie stała), sprawdzenie w pamięci
                          klienta, rozciągnięcie okna do 5 rzędów (`loot.rozciagnij_plecak`);
  kilka okien plecaka, jedyne okno plecaka z samymi runami (nie wiadomo, czy to plecak łupu), nie udana naprawa
                       -> BEZ klikania: jedno powiadomienie critical z tym, co zrobić (bez STOP).
  okno ucięte dołem ekranu (plecak, runy) -> tylko ostrzeżenie w wyniku/logu.
Naprawa: co najwyżej jedno kliknięcie na problem, bez ponawiania w pętli; tylko poza walką, bez STOP_RECZNY (Karol gra sam).

POKRĘTŁA:
  RETRONIC_OKNA_START=0     wyłącza całość (hook w mozg.main i rodzaj `okna` nadzorcy robią nic); domyślnie 1 = sprawdź i powiadom
  RETRONIC_OKNA_NAPRAWA=1   włącza klikanie; albo plik instancje/<id>/OKNA_NAPRAWA, albo instancje/_wspolne/OKNA_NAPRAWA
                            (nadzorca z timera nie dziedziczy env). DOMYŚLNIE WYŁĄCZONE: sekwencja zwiń+otwórz nie ma jeszcze
                            zapisu udanego przebiegu na żywo w jednym przebiegu (kawałki: ręcznie 19.10, loot.otworz_plecak 18.10).
  RETRONIC_OKNA_POWIADOM_S  odstęp powtórzeń tego samego powiadomienia (domyślnie 1800 s; stan: instancje/<id>/okna_start_stan.json)

WYWOŁANIA:
  RETRONIC_ID=<id> python3 -I okna_start.py sprawdz          odczyt i ocena, zero klików, zero powiadomień (JSON)
  RETRONIC_ID=<id> python3 -I okna_start.py napraw           jak przy starcie: naprawia, gdy pokrętło włączone, inaczej powiadamia
  RETRONIC_ID=<id> python3 -I okna_start.py napraw --tak     JEDNO wywołanie testowe z klikaniem mimo wyłączonego pokrętła
  RETRONIC_ID=<id> python3 -I okna_start.py role             27.10: tylko pamięć klienta (bez zrzutu i klików): okna z rodzicem i rolą (położenie vs dawne reguły)
Kody wyjścia: 0 ok/naprawione/poza grą, 1 wymaga człowieka, 3 odroczone (walka, STOP_RECZNY, wyłączone), 4 brak odczytu.
Hooki: `mozg.main` (po `bot.Postac()`, przed wznowieniem wyprawy i dojściem) oraz `nadzor.py napraw <id> okna`
(biała lista; nadzorca zleca je, gdy log bota powtarza brak_plecaka/brak_okna). Rollback: kopie `*.bak-20261022-okna-start`."""
import json
import os
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import instancja  # noqa: E402

WLACZONE = os.environ.get("RETRONIC_OKNA_START", "1") != "0"
POWIADOM_PONOW_S = float(os.environ.get("RETRONIC_OKNA_POWIADOM_S", "1800") or 1800)
NAZWY_DEPO = ("locker", "depot chest")
NAZWY_PLECAKA = ("backpack", "bag")
PAUZA_PO_ZWINIECIU_S = 1.2           # jak w serwis_akcje.przygotuj_okna (zmierzone na żywo 19.10)
PAUZA_PO_OTWARCIU_S = 1.4


def _przepusc_stop(e):
    """Plik STOP (bot.Zatrzymano) przerywa także kontrolę okien: nie połykamy go jak zwykłego błędu."""
    if type(e).__name__ == "Zatrzymano":
        raise e


def naprawa_wlaczona(stan=None, wspolne=None, env=None):
    """True, gdy klikanie włączone: env RETRONIC_OKNA_NAPRAWA=1 albo plik OKNA_NAPRAWA (instancji / wspólny). Env "0" wyłącza."""
    env = os.environ if env is None else env
    w = (env.get("RETRONIC_OKNA_NAPRAWA") or "").strip()
    if w == "0":
        return False
    if w == "1":
        return True
    stan = Path(stan) if stan else Path(instancja.S.stan)
    wspolne = Path(wspolne) if wspolne else Path(instancja.S.wspolne)
    return (stan / "OKNA_NAPRAWA").exists() or (wspolne / "OKNA_NAPRAWA").exists()


# --- czyste: rola okien i ocena układu ---------------------------------------------------------------

def rola(kontener):
    """"depo" | "runy" | "plecak" | "zwloki" kontenera z pamięci klienta (loot.rola_kontenera + depo po nazwie)."""
    import loot  # noqa: PLC0415
    if (kontener.get("nazwa") or "").casefold() in NAZWY_DEPO:
        return "depo"
    return loot.rola_kontenera(kontener)


def role_z_pamieci(kontenery):
    return [{"rola": rola(k), "nazwa": (k.get("nazwa") or "").casefold(), "numer": k.get("numer"),
             "przedmiotow": len(k.get("przedmioty", []))} for k in kontenery or []]


def diagnoza_rol(kontenery):
    """27.10: tabela do weryfikacji klasyfikacji (tylko odczyt pamięci): numer, nazwa, ID, zagnieżdżenie, rodzic, rola wg położenia okna
    i rola wg dawnych reguł (nazwa/ID/zawartość, bez pola rodzic). `rola_wg`: "polozenie" (rodzic rozstrzyga), "depo", "zawartosc" (fallback)."""
    import loot  # noqa: PLC0415
    wynik = []
    for k in kontenery or []:
        stara = rola({x: v for x, v in k.items() if x != "rodzic"})
        nowa = rola(k)
        wg = "depo" if nowa == "depo" else ("polozenie" if loot.rola_strukturalna(k) is not None else "zawartosc")
        wynik.append({"numer": k.get("numer"), "nazwa": k.get("nazwa"), "id": k.get("id"), "zagniezdzony": k.get("zagniezdzony"),
                      "rodzic": k.get("rodzic"), "przedmiotow": len(k.get("przedmioty", [])), "pojemnosc": k.get("pojemnosc"),
                      "rola": nowa, "rola_wg": wg, "rola_dawna": stara})
    return wynik


def role_z_tytulow(tytuly):
    """Rezerwa bez pamięci: role z tytułów okien rozpoznanych z obrazu (None = tytuł nieznany -> okno zwłok)."""
    import loot  # noqa: PLC0415
    wynik = []
    for t in tytuly:
        t = (t or "").casefold() or None
        wynik.append({"rola": "depo" if t in NAZWY_DEPO else loot.rola_z_tytulu(t), "nazwa": t or "", "numer": None, "przedmiotow": None})
    return wynik


def slot_ucieto(obraz, slot):
    """True, gdy dół slotu wystaje poza zrzut (jak serwis_akcje.slot_w_pelni_widoczny, tylko odwrotnie)."""
    rozmiar = getattr(obraz, "size", None)
    y, bok = getattr(slot, "y", None), getattr(slot, "bok", None)
    if rozmiar is None or y is None or bok is None:
        return False
    return y + bok > rozmiar[1]


def ostrzezenia_okien(obraz, okna_role):
    """[(rola, opis)] okien plecaka/runów uciętych dołem zrzutu. `okna_role`: [(okno, rola|None)]. Zwłoki i depo pomijamy."""
    wynik = []
    for okno, r in okna_role:
        if r not in ("plecak", "runy"):
            continue
        ucietych = sum(1 for s in okno.sloty if slot_ucieto(obraz, s))
        if ucietych:
            wynik.append(("okno_uciete", f"okno {r} ucięte dołem ekranu ({ucietych} slotów poza zrzutem)"))
    return wynik


def problem(kod, opis, naprawa=None, reczne=None):
    return {"kod": kod, "opis": opis, "naprawa": naprawa, "reczne": reczne}


def ocen(uklad, role, ostrzezenia=(), zrodlo="pamiec", runy_potrzebne=False):
    """Ocena układu okien. -> {"stan": "poza_gra"|"ok"|"do_naprawy"|"reczne", "minimapa", "plecaki", "runy", "zwloki", "depo",
    "problemy": [{kod, opis, naprawa, reczne}], "ostrzezenia": [...]}.
    `uklad` z serwis_akcje.uklad_panelu (minimapa None = nie ma paska HP = klient nie jest w grze), `role` z role_z_pamieci /
    role_z_tytulow, `zrodlo` "pamiec" (pewne) albo "ekran" (rezerwa: naprawa klikiem tylko z pewnych danych)."""
    plecaki = [r for r in role if r["rola"] == "plecak"]
    runy = [r for r in role if r["rola"] == "runy"]
    wynik = {"stan": "ok", "minimapa": uklad.get("minimapa"), "plecaki": len(plecaki), "runy": len(runy),
             "zwloki": sum(1 for r in role if r["rola"] == "zwloki"), "depo": sum(1 for r in role if r["rola"] == "depo"),
             "zrodlo": zrodlo, "problemy": [], "ostrzezenia": [o[1] if isinstance(o, tuple) else o for o in ostrzezenia]}
    if uklad.get("minimapa") is None:
        wynik["stan"] = "poza_gra"
        return wynik
    pr = wynik["problemy"]
    if uklad["minimapa"] == "rozwinieta":
        pr.append(problem("minimapa_rozwinieta", "minimapa rozwinięta (zabiera miejsce oknom plecaków)", naprawa="zwin_minimape",
                          reczne="kliknij \"-\" w nagłówku Minimap (prawy panel, u góry)"))
    if not plecaki:
        zwykle_runy = [r for r in runy if r["nazwa"] in NAZWY_PLECAKA]
        if zwykle_runy:
            pr.append(problem("plecak_niejednoznaczny", "jedyne okno plecaka ma same runy: nie wiem, czy to plecak łupu, "
                              "czy bag na runy (Ctrl+klik w ekwipunku mógłby je zamknąć)",
                              reczne="otwórz plecak z ekwipunku (Ctrl+klik) w osobnym oknie"))
        else:
            pr.append(problem("brak_plecaka", "brak otwartego okna plecaka na łup", naprawa="otworz_plecak" if zrodlo == "pamiec" else None,
                              reczne="otwórz plecak z ekwipunku (Ctrl+klik na plecaku)"))
    elif len(plecaki) > 1:
        pr.append(problem("kilka_plecakow", f"{len(plecaki)} okna plecaka łupu (UH i loot wymagają jednego)",
                          reczne="zamknij nadmiarowe okno Backpack (zostaw plecak łupu i ewentualnie bag na runy)"))
    if runy_potrzebne and not runy and not any(r["nazwa"] in NAZWY_PLECAKA for r in plecaki[1:]):
        wynik["ostrzezenia"].append("robienie run włączone (RUNA_AKTYWNA), ale nie widzę osobnego okna na runy")
    if pr:
        wynik["stan"] = "do_naprawy" if any(p["naprawa"] for p in pr) else "reczne"
    return wynik


# --- odczyt na żywo ---------------------------------------------------------------------------------

def _zrzut():
    """Zrzut sesji gry w pikselach ekranu X (jak loot._zrzut, bez myszy)."""
    import ekran  # noqa: PLC0415
    obraz = ekran.zrzut()
    rozmiar = ekran._rozmiar_ekranu()
    return obraz if obraz.size == rozmiar else obraz.resize(rozmiar)


def _runy_potrzebne():
    try:
        return bool(json.loads(Path(instancja.S.na_zywo).read_text()).get("RUNA_AKTYWNA"))
    except (OSError, ValueError, AttributeError):
        return False


def odczyt(obraz=None, kontenery_fn=None):
    """Zrzut + kontenery z pamięci -> ocena. Pamięć bez kontenerów ("nie widzi otwartych") to PEWNE zero okien; pamięć
    niedostępna (strażnik, timeout) = rezerwa z tytułów okien z obrazu (zrodlo "ekran": bez naprawy klikiem).
    -> (ocena, obraz) albo (None, powód)."""
    import loot  # noqa: PLC0415
    from serwis_akcje import uklad_panelu  # noqa: PLC0415
    try:
        obraz = obraz if obraz is not None else _zrzut()
    except Exception as e:      # noqa: BLE001
        return None, f"zrzut nieudany ({type(e).__name__}: {e})"
    uklad = uklad_panelu(obraz)
    if uklad["minimapa"] is None:
        return ocen(uklad, []), obraz
    kontenery, powod = (kontenery_fn or loot.kontenery_z_pamieci)()
    okna = loot.znajdz_okna(obraz)
    if kontenery is not None:
        role, zrodlo = role_z_pamieci(kontenery), "pamiec"
    elif powod and powod.startswith("pamięć nie widzi"):
        role, zrodlo = [], "pamiec"
    else:
        role, zrodlo = role_z_tytulow([loot._nazwa_tytulu(obraz, o) for o in okna]), "ekran"
    # rola okna do ostrzeżeń: z dopasowania okno<->kontener, a bez niego z tytułu
    okna_role = []
    przypisane = None
    if kontenery is not None and okna:
        przypisane, _ = loot.dopasuj_okna(obraz, okna, kontenery)
    for i, o in enumerate(okna):
        if przypisane is not None:
            okna_role.append((o, rola(przypisane[i])))
        else:
            t = (loot._nazwa_tytulu(obraz, o) or "").casefold() or None
            okna_role.append((o, "depo" if t in NAZWY_DEPO else loot.rola_z_tytulu(t)))
    wynik = ocen(uklad, role, ostrzezenia_okien(obraz, okna_role), zrodlo, _runy_potrzebne())
    wynik["uklad"] = {"prawo": uklad["prawo"], "plecak_ekw": uklad["plecak_ekw"]}
    return wynik, obraz


# --- powiadomienie i stan ---------------------------------------------------------------------------

def _plik_stanu():
    return Path(instancja.S.stan) / "okna_start_stan.json"


def _wczytaj_stan(plik):
    try:
        d = json.loads(Path(plik).read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _zapisz_stan(plik, d):
    plik = Path(plik)
    tmp = plik.with_name(plik.name + f".tmp{os.getpid()}")
    try:
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1))
        os.replace(tmp, plik)
    except OSError:
        pass


def tresc_powiadomienia(id_, problemy):
    """Jedna konkretna wiadomość: co jest nie tak i co zrobić (bez STOP: bot dalej pracuje)."""
    linie = [f"{p['opis']}: {p['reczne']}" for p in problemy]
    return f"[{id_ or 'domyślna'}] okna gry do poprawienia. " + "; ".join(linie) + "."


def powiadom_raz(id_, problemy, powiadom_fn=None, zegar=time.time, plik=None):
    """Jedno powiadomienie critical za wszystkie problemy; to samo (zestaw kodów) najwyżej raz na POWIADOM_PONOW_S.
    -> True, gdy poszło."""
    if not problemy:
        return False
    plik = plik or _plik_stanu()
    stan = _wczytaj_stan(plik)
    klucz = "+".join(sorted(p["kod"] for p in problemy))
    teraz = zegar()
    ostatnio = (stan.get("powiadomienia") or {}).get(klucz)
    if ostatnio is not None and teraz - float(ostatnio) < POWIADOM_PONOW_S:
        return False
    if powiadom_fn is None:
        import powiadom as _p  # noqa: PLC0415
        powiadom_fn = _p.powiadom
    try:
        poszlo = bool(powiadom_fn(f"Retronic [{id_ or 'domyślna'}]: popraw okna", tresc_powiadomienia(id_, problemy), "critical",
                                  klucz=f"okna-{id_}-{klucz}"))
    except Exception:       # noqa: BLE001
        poszlo = False
    if poszlo:
        stan.setdefault("powiadomienia", {})[klucz] = teraz
        _zapisz_stan(plik, stan)
    return poszlo


# --- walka / ręczna gra ---------------------------------------------------------------------------------

def odroczenie(id_=None):
    """Powód, dla którego nie wolno teraz klikać w okna, albo None: STOP_RECZNY (Karol gra) lub bot w walce (log z ostatnich 20 s)."""
    if Path(instancja.S.stop_reczny).exists():
        return "STOP_RECZNY: Karol gra sam, nie ruszam okien"
    try:
        import nadzor  # noqa: PLC0415
        from datetime import datetime  # noqa: PLC0415
        teraz = datetime.now()
        a = nadzor.analizuj_log(nadzor.czytaj_log(nadzor.najnowszy_log(instancja.S.logi), teraz), teraz.timestamp())
        # walka_bez_lootu: powtarzające się "Loot: brak_plecaka" to objaw, który naprawiamy, a nie walka
        if a.get("walka_bez_lootu"):
            return "bot w walce (log z ostatnich 20 s): okna tylko poza walką"
    except Exception:       # noqa: BLE001  (brak logu/modułu: nie blokujemy, naprawa i tak ma pozostałe bramki)
        pass
    return None


# --- naprawa ----------------------------------------------------------------------------------------

def _liczba_plecakow(odczyt_fn):
    o, _ = odczyt_fn()
    return None if o is None else o


def napraw(ocena, obraz, odczyt_fn=None, mysz_fn=None, pauza=time.sleep, log=print):
    """Wykonuje naprawy z `ocena["problemy"]` (co najwyżej jedno kliknięcie na problem), po każdej sprawdza zrzutem/pamięcią.
    -> (nowa ocena, [opis wykonanych kroków]). Kroki: "zwin_minimape" potem "otworz_plecak" (po zwinięciu pozycja plecaka
    w ekwipunku jest już inna: bierzemy ją z nowego odczytu)."""
    odczyt_fn = odczyt_fn or odczyt
    if mysz_fn is None:
        import ekran  # noqa: PLC0415
        mysz_fn = ekran.Mysz
    from serwis_akcje import przycisk_zwin_minimape  # noqa: PLC0415
    kroki = []
    with mysz_fn() as m:
        if any(p["naprawa"] == "zwin_minimape" for p in ocena["problemy"]):
            log("okna: zwijam minimapę (miejsce na plecaki)")
            m.klik(*przycisk_zwin_minimape(ocena["uklad"]["prawo"]), 1, None, drganie=1)
            pauza(PAUZA_PO_ZWINIECIU_S)
            nowa, obraz = odczyt_fn()
            if nowa is None:
                return ocena, kroki + [f"zwinięcie minimapy: brak odczytu po kliku ({obraz})"]
            ocena = nowa
            kroki.append("minimapa zwinięta" if ocena["minimapa"] != "rozwinieta" else "minimapa NIE zwinęła się")
        if any(p["naprawa"] == "otworz_plecak" for p in ocena["problemy"]) and ocena["minimapa"] != "rozwinieta":
            ekw = (ocena.get("uklad") or {}).get("plecak_ekw")
            if ekw is None:
                kroki.append("brak pozycji plecaka w ekwipunku (nie rozpoznałem panelu)")
            else:
                log("okna: otwieram plecak z ekwipunku")
                m.klik(*ekw, 1, "Control_L", drganie=2)
                pauza(PAUZA_PO_OTWARCIU_S)
                nowa, obraz = odczyt_fn()
                if nowa is None:
                    return ocena, kroki + [f"otwarcie plecaka: brak odczytu po kliku ({obraz})"]
                ocena = nowa
                if ocena["plecaki"] >= 1:
                    kroki.append("plecak otwarty")
                    try:
                        import loot  # noqa: PLC0415
                        if loot.rozciagnij_plecak(m, obraz, log=log):
                            kroki.append("plecak rozciągnięty do 5 rzędów")
                    except Exception as e:      # noqa: BLE001  (rozciąganie to dodatek: plecak jest otwarty)
                        _przepusc_stop(e)
                        kroki.append(f"rozciągnięcie plecaka pominięte ({type(e).__name__})")
                else:
                    kroki.append("plecak z ekwipunku się nie otworzył")
    return ocena, kroki


def uruchom(tryb, id_=None, naprawiaj=None, odczyt_fn=None, mysz_fn=None, pauza=time.sleep, log=print, powiadom_fn=None,
            powiadamiaj=True, odroczenie_fn=None):
    """Całość. tryb "sprawdz" (zero klików i powiadomień) albo "napraw" (naprawia, gdy `naprawiaj`/pokrętło, powiadamia o reszcie).
    -> (kod_wyjścia, wynik dict z kluczami stan, opis, kroki, ocena)."""
    id_ = instancja.ID if id_ is None else id_
    odczyt_fn = odczyt_fn or odczyt
    ocena, obraz = odczyt_fn()
    if ocena is None:
        return 4, {"stan": "brak_odczytu", "opis": f"brak odczytu: {obraz}", "kroki": [], "ocena": None}
    wynik = {"stan": ocena["stan"], "kroki": [], "ocena": ocena}
    if ocena["stan"] in ("ok", "poza_gra"):
        wynik["opis"] = "klient poza grą (brak paska HP): nic do zrobienia" if ocena["stan"] == "poza_gra" else "układ okien w porządku"
        return 0, wynik
    if tryb == "sprawdz":
        wynik["opis"] = "do poprawy: " + ", ".join(p["kod"] for p in ocena["problemy"])
        return 1, wynik
    chce = naprawa_wlaczona() if naprawiaj is None else naprawiaj
    naprawialne = [p for p in ocena["problemy"] if p["naprawa"]]
    if naprawialne and chce:
        powod = (odroczenie_fn or odroczenie)(id_)
        if powod:
            wynik["opis"] = f"odroczone: {powod}"
            wynik["stan"] = "odroczone"
            return 3, wynik
        try:
            ocena, kroki = napraw(ocena, obraz, odczyt_fn, mysz_fn, pauza, log)
        except Exception as e:      # noqa: BLE001  (naprawa przerwana: układ oceniamy z tego, co jest)
            _przepusc_stop(e)
            kroki = [f"naprawa przerwana ({type(e).__name__}: {e})"]
        wynik["kroki"], wynik["ocena"], wynik["stan"] = kroki, ocena, ocena["stan"]
    resztki = ocena["problemy"]
    if not resztki:
        wynik["opis"] = "naprawione: " + "; ".join(wynik["kroki"])
        return 0, wynik
    if naprawialne and not chce:
        wynik["opis"] = "naprawa klikiem wyłączona (RETRONIC_OKNA_NAPRAWA=1 albo plik OKNA_NAPRAWA); wykryto: " + \
            ", ".join(p["kod"] for p in resztki)
    else:
        wynik["opis"] = "wymaga człowieka: " + ", ".join(p["kod"] for p in resztki) + (" (" + "; ".join(wynik["kroki"]) + ")" if wynik["kroki"] else "")
    if powiadamiaj:
        wynik["powiadomiono"] = powiadom_raz(id_, resztki, powiadom_fn)
    return 1, wynik


def przy_starcie(log=print):
    """Hook startu bota (mozg.main, przed wznowieniem wyprawy i dojściem). Nigdy nie rzuca; domyślnie sprawdza i powiadamia,
    klika tylko przy włączonym pokrętle. -> wynik albo None."""
    if not WLACZONE or os.environ.get("RETRONIC_TESTY"):
        return None
    try:
        kod, w = uruchom("napraw", log=lambda *a: log(*a))
    except Exception as e:      # noqa: BLE001  (start nie może się wywrócić na kontroli okien; STOP i Ctrl+C przechodzą)
        _przepusc_stop(e)
        log(f"Okna po starcie: kontrola pominięta ({type(e).__name__}: {e})")
        return None
    o = w.get("ocena") or {}
    log(f"Okna po starcie: {w['opis']} (minimapa {o.get('minimapa')}, plecaków {o.get('plecaki')}, runy {o.get('runy')}, "
        f"zwłok {o.get('zwloki')}, depo {o.get('depo')}, kod {kod})" + ("; ostrzeżenia: " + "; ".join(o["ostrzezenia"]) if o.get("ostrzezenia") else ""))
    return w


def main(argv=None):
    import argparse  # noqa: PLC0415
    ap = argparse.ArgumentParser(prog="okna_start.py")
    ap.add_argument("tryb", choices=("sprawdz", "napraw", "role"), help="role: tylko pamięć klienta (bez zrzutu i klików), tabela okien z rodzicem i rolą")
    ap.add_argument("--tak", action="store_true", help="napraw: kliknij mimo wyłączonego pokrętła (jedno wywołanie testowe)")
    a = ap.parse_args(argv)
    if a.tryb == "role":
        import loot  # noqa: PLC0415
        kontenery, powod = loot.kontenery_z_pamieci()
        if kontenery is None:
            print(f"okna_start role: brak odczytu pamięci ({powod})")
            return 4
        tabela = diagnoza_rol(kontenery)
        print(f"== {instancja.ID or '(domyślna)'}: okien {len(tabela)}, plecaków {sum(1 for t in tabela if t['rola'] == 'plecak')}, "
              f"runy {sum(1 for t in tabela if t['rola'] == 'runy')} (dawne reguły: plecaków {sum(1 for t in tabela if t['rola_dawna'] == 'plecak')}, "
              f"runy {sum(1 for t in tabela if t['rola_dawna'] == 'runy')})")
        for t in tabela:
            print("  " + json.dumps(t, ensure_ascii=False))
        return 0
    if not WLACZONE:
        print("okna_start: wyłączone (RETRONIC_OKNA_START=0)")
        return 3
    kod, w = uruchom(a.tryb, naprawiaj=True if a.tak else None, powiadamiaj=(a.tryb == "napraw"))
    o = w.get("ocena") or {}
    print(json.dumps({"instancja": instancja.ID or "(domyślna)", "stan": w["stan"], "minimapa": o.get("minimapa"),
                      "plecaki": o.get("plecaki"), "runy": o.get("runy"), "zwloki": o.get("zwloki"), "depo": o.get("depo"),
                      "zrodlo": o.get("zrodlo"), "problemy": [p["kod"] for p in o.get("problemy", [])],
                      "ostrzezenia": o.get("ostrzezenia", []), "kroki": w["kroki"]}, ensure_ascii=False))
    print(f"okna_start {a.tryb}: {w['opis']}")
    return kod


if __name__ == "__main__":
    sys.exit(main())
