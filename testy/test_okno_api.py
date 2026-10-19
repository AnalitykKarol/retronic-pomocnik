"""okno_api.py (zaplecze okna zarządzania, F1): wyłącznie na atrapach — tymczasowy katalog z fałszywymi instancjami,
fałszywym /proc i fałszywym panel.py. Nic nie dotyka prawdziwych instancji, gry ani procesów (RETRONIC_TESTY=1).
Uruchomienie: python3 -I testy/test_okno_api.py"""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import hashlib, json, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.dont_write_bytecode = True
KAT = Path(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
sys.path.insert(0, str(KAT))
import okno_api, pokretla

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))

TERAZ = time.mktime((2026, 10, 19, 12, 0, 0, 0, 0, -1))        # "teraz" atrap: 2026-10-19 12:00:00 (czas lokalny)
def czas(h, m, s=0, dzien=19):
    return f"2026-10-{dzien:02d} {h:02d}:{m:02d}:{s:02d}"

FAKE_PANEL = '''import json, os, sys, time
i = os.environ.get("RETRONIC_ID", "")
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "panel_wywolania.log"), "a").write((i or "glowna") + "\\n")
tryb = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "panel_tryb." + (i or "glowna"))).read().strip() \\
    if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "panel_tryb." + (i or "glowna"))) else "ok"
if tryb == "crash":
    sys.stderr.write("Traceback: kaboom\\n"); sys.exit(3)
if tryb == "garbage":
    print("to nie jest json"); sys.exit(0)
if tryb.startswith("sleep:"):
    time.sleep(float(tryb[6:]))
print(json.dumps({"text": "RT", "tooltip": "Retronic: działa\\nHP 100/200  mana 30/60", "class": "dziala", "alt": "dziala", "id": i}))
'''
FAKE_CAVEBOT = "POGON_ZASIEG = 10     # stała\nPOGON_LIMIT = 14.0\nPOSCIG_TRZYMAJ = True\nUH_KLAWISZ = 'F6'\nRATUNEK_LIMIT_H = 20\nRATUNEK_HAIKU = 0\nKROKI_DO_ZWLOK = 30\nOGIEN_IGNORUJ_S = 0.0\nLIMIT_WALKI = 90\n"
NA_ZYWO = {"POGON_ZASIEG": 12, "UH_KLAWISZ": "F7", "_opis": "ręczna notatka", "STARY_KLUCZ": 5, "POGON_LIMIT": 20.0}

def tekst_na_zywo(d):
    return json.dumps(d, ensure_ascii=False, indent=1)

def zrob_korzen(tmp, instancje=("dwa",), na_zywo=NA_ZYWO):
    r = Path(tmp) / "pomocnik"
    (r / "instancje" / "_wspolne").mkdir(parents=True)
    (r / "instancje" / "Zla Nazwa").mkdir()
    (r / "instancje" / "plik.txt").write_text("x")
    for i in instancje:
        (r / "instancje" / i / "logi").mkdir(parents=True)
        (r / "instancje" / i / "na_zywo.json").write_text(tekst_na_zywo(dict(na_zywo, POGON_ZASIEG=11)))
    (r / "na_zywo.json").write_text(tekst_na_zywo(na_zywo))
    (r / "logi").mkdir()
    (r / "panel.py").write_text(FAKE_PANEL)
    (r / "cavebot.py").write_text(FAKE_CAVEBOT)
    (r / "mapy.json").write_text(json.dumps({"_opis": "mapy", "raty": {"opis": "Thais szczury", "trasa": "t1", "potwory": "Rat"},
                                             "trolle": {"opis": "Troll cave", "trasa": "t2"}}))
    (r / "tryby.json").write_text(json.dumps({"_opis": "tryby", "sredni": {"opis": "średnio", "pokretla": {"RUNA_AKTYWNA": 1}},
                                              "ml": {"opis": "magic level", "pokretla": {}}}))
    (r / "ostatni_start.env").write_text("MAPA=raty\nTRYB=sredni\n")
    (r / "ostatni_start.dwa.env").write_text("MAPA=trolle\nTRYB=sredni\\,ml\n")
    (Path(tmp) / "proc").mkdir()
    (Path(tmp) / "rt").mkdir()
    return r

def proces(tmp, pid, argv, env):
    d = Path(tmp) / "proc" / str(pid)
    d.mkdir(parents=True)
    (d / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")
    (d / "environ").write_bytes(b"\0".join(f"{k}={v}".encode() for k, v in env.items()) + b"\0")

def uruchom(tmp, *args, teraz=TERAZ):
    env = dict(_os.environ, RETRONIC_OKNO_KATALOG=str(Path(tmp) / "pomocnik"), RETRONIC_OKNO_PROC=str(Path(tmp) / "proc"),
               RETRONIC_OKNO_TERAZ=str(teraz), XDG_RUNTIME_DIR=str(Path(tmp) / "rt"))
    env.pop("RETRONIC_ID", None)
    p = subprocess.run([sys.executable, "-I", str(KAT / "okno_api.py"), *args], capture_output=True, env=env, timeout=30)
    try:
        return p.returncode, json.loads(p.stdout)
    except ValueError:
        return p.returncode, {"ok": None, "surowe": p.stdout.decode(errors="replace"), "stderr": p.stderr.decode(errors="replace")}

def bajty(*sciezki):
    return [Path(s).read_bytes() if Path(s).exists() else None for s in sciezki]

def sha(p):
    return hashlib.sha1(Path(p).read_bytes()).hexdigest()

# ================= pokretla =================
with tempfile.TemporaryDirectory() as tmp:
    r = zrob_korzen(tmp)
    kod, d = uruchom(tmp, "pokretla", "--instancja", "dwa")
    sprawdz("pokretla: ok i kod 0", kod == 0 and d["ok"] is True, d)
    lista = {p["klucz"]: p for p in d["pokretla"]}
    sprawdz("pokretla: każdy klucz ZAKRESY i TEKSTY jest w wyniku", set(lista) == set(pokretla.ZAKRESY) | set(pokretla.TEKSTY)
            and len(d["pokretla"]) == len(pokretla.ZAKRESY) + len(pokretla.TEKSTY))
    sprawdz("pokretla: komplet pól w każdym wpisie", all({"klucz", "grupa", "typ", "min", "max", "domyslna", "biezaca", "zmieniona", "opis"} <= set(p)
            for p in d["pokretla"]))
    p = lista["POGON_ZASIEG"]
    sprawdz("pokretla: zakres z ZAKRESY, typ całkowity", (p["min"], p["max"], p["typ"]) == (10, 14, "calkowita"), p)
    sprawdz("pokretla: domyślna ze stałej cavebota, bieżąca z na_zywo.json INSTANCJI (11, nie 12 z głównej)",
            p["domyslna"] == 10 and p["biezaca"] == 11 and p["zmieniona"] is True, p)
    sprawdz("pokretla: opis z komentarza w pokretla.py", p["opis"] == "max odległość pościgu za celem poza ekranem", p["opis"])
    sprawdz("pokretla: ułamkowa; bieżąca z pliku, zmieniona", lista["POGON_LIMIT"]["typ"] == "ulamkowa" and lista["POGON_LIMIT"]["biezaca"] == 20.0
            and lista["POGON_LIMIT"]["zmieniona"], lista["POGON_LIMIT"])
    sprawdz("pokretla: przełącznik 0/1, bool domyślnej -> liczba", lista["POSCIG_TRZYMAJ"]["typ"] == "przelacznik"
            and lista["POSCIG_TRZYMAJ"]["domyslna"] == 1 and lista["POSCIG_TRZYMAJ"]["domyslna"] is not True, lista["POSCIG_TRZYMAJ"])
    sprawdz("pokretla: bez wpisu w pliku = bieżąca równa domyślnej i niezmieniona", lista["KROKI_DO_ZWLOK"]["biezaca"] == 30
            and lista["KROKI_DO_ZWLOK"]["zmieniona"] is False)
    t = lista["UH_KLAWISZ"]
    sprawdz("pokretla: tekst z opcjami", t["typ"] == "tekst" and "F7" in t["opcje"] and t["biezaca"] == "F7" and t["domyslna"] == "F6", t)
    sprawdz("pokretla: grupy po prefiksie (tabela)", [lista[k]["grupa"] for k in ("POGON_ZASIEG", "UH_KLAWISZ", "WYPAD_BLOK_S", "PATROL_SWEEP",
            "PK_OBRONA", "PATROL_GRACZ_PAM", "PIETRA_LOPATA", "KROKI_DO_ZWLOK", "RATUNEK_HAIKU", "PET_WLACZONY")] ==
            ["Walka i pościg", "Leczenie i runy", "Wyprawa i serwis", "Patrol", "Gracze i PK", "Gracze i PK", "Piętra i dojście", "Loot",
             "Ratunek", "Zaawansowane"], [lista[k]["grupa"] for k in ("POGON_ZASIEG", "UH_KLAWISZ", "WYPAD_BLOK_S", "PATROL_SWEEP", "PK_OBRONA")])
    sprawdz("pokretla: każda grupa z listy GRUPY, liczniki grup sumują się do całości", {p["grupa"] for p in d["pokretla"]} <= set(okno_api.GRUPY)
            and sum(g["ile"] for g in d["grupy"]) == len(d["pokretla"]))
    sprawdz("pokretla: klucze nieznane/_ z pliku zgłoszone jako odrzucone, nie jako pokrętła", "STARY_KLUCZ" not in lista
            and any("STARY_KLUCZ" in o for o in d["odrzucone_w_pliku"]), d["odrzucone_w_pliku"])
    sprawdz("pokretla: bez --instancja = główna (na_zywo 12)", uruchom(tmp, "pokretla")[1]["pokretla"][0]["klucz"] == "POGON_ZASIEG"
            and {p["klucz"]: p for p in uruchom(tmp, "pokretla")[1]["pokretla"]}["POGON_ZASIEG"]["biezaca"] == 12)
    # tryb odczytu: nic się nie zmieniło na dysku
    sprawdz("pokretla: tylko odczyt (brak .bak, brak dziennika)", not list(r.glob("na_zywo.json.*")) and not (r / "instancje/dwa/okno_cofnij.jsonl").exists())
    (r / "instancje/dwa/na_zywo.json").write_text("{ to nie json")
    kod, d2 = uruchom(tmp, "pokretla", "--instancja", "dwa")
    sprawdz("pokretla: uszkodzony na_zywo.json = ok, bieżące domyślne, blad_pliku", kod == 0 and d2["blad_pliku"] and
            {p["klucz"]: p for p in d2["pokretla"]}["POGON_ZASIEG"]["biezaca"] == 10, d2.get("blad_pliku"))

# grupowanie (czysta funkcja i tabela)
sprawdz("grupa: najdłuższy prefiks wygrywa", okno_api.grupa_pokretla("PATROL_GRACZ_ZMIEN_R") == "Gracze i PK"
        and okno_api.grupa_pokretla("PATROL_SWEEP") == "Patrol" and okno_api.grupa_pokretla("NIC_TAKIEGO") == "Zaawansowane")
sprawdz("grupa: KROKI_DO_ZWLOK -> Loot, ale KROKI_INNE -> Zaawansowane", okno_api.grupa_pokretla("KROKI_DO_ZWLOK") == "Loot"
        and okno_api.grupa_pokretla("KROKI_INNE") == "Zaawansowane")

# ================= ustaw =================
with tempfile.TemporaryDirectory() as tmp:
    r = zrob_korzen(tmp)
    plik, plik_glowna = r / "instancje/dwa/na_zywo.json", r / "na_zywo.json"
    oryg = plik.read_bytes()
    dziennik = r / "instancje/dwa/okno_cofnij.jsonl"
    def nic_nie_zapisano(opis, *args):
        kod, d = uruchom(tmp, "ustaw", "--instancja", "dwa", *args)
        po = plik.read_bytes()
        czysto = (kod != 0 and d["ok"] is False and bool(d["blad"]) and po == oryg and not dziennik.exists()
                  and not list(plik.parent.glob("na_zywo.json.*")) and plik_glowna.read_bytes() == tekst_na_zywo(NA_ZYWO).encode())
        sprawdz(f"ustaw odrzuca: {opis} (kod != 0, plik bajtowo bez zmian, brak .bak i dziennika)", czysto, (kod, d))
    nic_nie_zapisano("nieznany klucz", "NIE_MA_TAKIEGO=1")
    nic_nie_zapisano("wartość poza zakresem (za duża)", "POGON_ZASIEG=99")
    nic_nie_zapisano("wartość poza zakresem (za mała)", "POGON_ZASIEG=1")
    nic_nie_zapisano("tekst zamiast liczby", "POGON_ZASIEG=abc")
    nic_nie_zapisano("boolean zamiast liczby", "POGON_ZASIEG=true")
    nic_nie_zapisano("NaN", "POGON_LIMIT=NaN")
    nic_nie_zapisano("ułamek w pokrętle całkowitym", "POGON_ZASIEG=12.5")
    nic_nie_zapisano("tekst spoza dozwolonych", "UH_KLAWISZ=F99")
    nic_nie_zapisano("klucz z podkreśleniem (_opis)", "_opis=hej")
    nic_nie_zapisano("brak znaku =", "POGON_ZASIEG")
    nic_nie_zapisano("ten sam klucz dwa razy", "POGON_ZASIEG=12", "POGON_ZASIEG=13")
    nic_nie_zapisano("jedna poprawna + jedna zła = zero zapisu (nic z paczki)", "POGON_ZASIEG=13", "KROKI_DO_ZWLOK=999")
    kod, d = uruchom(tmp, "ustaw", "--instancja", "nie_ma", "POGON_ZASIEG=12")
    sprawdz("ustaw: nieznana instancja = błąd, brak katalogu instancji", kod != 0 and d["ok"] is False and not (r / "instancje/nie_ma").exists(), d)
    kod, d = uruchom(tmp, "ustaw", "POGON_ZASIEG=12")
    sprawdz("ustaw: brak --instancja = błąd użycia (kod 2, JSON), nic nie zapisane", kod == 2 and d["ok"] is False and plik.read_bytes() == oryg
            and plik_glowna.read_bytes() == tekst_na_zywo(NA_ZYWO).encode(), (kod, d))

    kod, d = uruchom(tmp, "ustaw", "--instancja", "dwa", "POGON_ZASIEG=13", "KROKI_DO_ZWLOK=40", "POGON_LIMIT=25")
    sprawdz("ustaw: dobra paczka ok, zmienione + poprzednie", kod == 0 and d["ok"] is True and d["zmienione"] == {"POGON_ZASIEG": 13, "KROKI_DO_ZWLOK": 40, "POGON_LIMIT": 25}
            and d["poprzednie"] == {"POGON_ZASIEG": 11, "KROKI_DO_ZWLOK": None, "POGON_LIMIT": 20.0}, d)
    po = json.loads(plik.read_text())
    sprawdz("ustaw: zachowuje pozostałe klucze (też nieznane i _opis) i kolejność", po == dict(NA_ZYWO, POGON_ZASIEG=13, KROKI_DO_ZWLOK=40, POGON_LIMIT=25)
            and list(po)[:5] == ["POGON_ZASIEG", "UH_KLAWISZ", "_opis", "STARY_KLUCZ", "POGON_LIMIT"] and po["_opis"] == "ręczna notatka" and po["STARY_KLUCZ"] == 5, po)
    sprawdz("ustaw: format jak u bota (json.dumps ensure_ascii=False, indent=1, bez końcowego newline)",
            plik.read_text() == json.dumps(po, ensure_ascii=False, indent=1) and "ręczna" in plik.read_text())
    sprawdz("ustaw: nie ruszył innej instancji (główna bajtowo bez zmian)", plik_glowna.read_bytes() == tekst_na_zywo(NA_ZYWO).encode())
    bak = plik.parent / "na_zywo.json.bak-20261019-okno"
    sprawdz("ustaw: kopia .bak-RRRRMMDD-okno przy pierwszej zmianie dnia = oryginał bajt w bajt", bak.exists() and bak.read_bytes() == oryg)
    sprawdz("ustaw: brak plików tymczasowych po zapisie (zapis atomowy)", not [p for p in plik.parent.iterdir() if ".tmp" in p.name], [p.name for p in plik.parent.iterdir()])
    kod, d = uruchom(tmp, "ustaw", "--instancja", "dwa", "POGON_ZASIEG=14")
    sprawdz("ustaw: druga zmiana tego dnia nie nadpisuje kopii", kod == 0 and bak.read_bytes() == oryg and len(list(plik.parent.glob("na_zywo.json.bak-*"))) == 1)
    kod, d = uruchom(tmp, "ustaw", "--instancja", "dwa", "POGON_ZASIEG=14")
    sprawdz("ustaw: ta sama wartość = bez zmian, bez zapisu i bez wpisu w dzienniku", kod == 0 and d["zmienione"] == {} and d["bez_zmian"] == ["POGON_ZASIEG"]
            and len(dziennik.read_text().splitlines()) == 2, d)
    przed_jutra = plik.read_bytes()
    kod, d = uruchom(tmp, "ustaw", "--instancja", "dwa", "POGON_ZASIEG=12", teraz=TERAZ + 86400)
    nowa_bak = plik.parent / "na_zywo.json.bak-20261020-okno"
    sprawdz("ustaw: następnego dnia nowa kopia (stan sprzed tej zmiany)", kod == 0 and nowa_bak.exists() and nowa_bak.read_bytes() == przed_jutra and bak.read_bytes() == oryg)
    wpisy = [json.loads(l) for l in dziennik.read_text().splitlines()]
    sprawdz("ustaw: dziennik cofania ma poprzednie wartości i listę dodanych kluczy", len(wpisy) == 3 and wpisy[0]["przed"] == {"POGON_ZASIEG": 11, "POGON_LIMIT": 20.0}
            and sorted(wpisy[0]["brak"]) == ["KROKI_DO_ZWLOK"] and wpisy[1]["przed"] == {"POGON_ZASIEG": 13} and wpisy[0]["po"]["POGON_ZASIEG"] == 13, wpisy[0])
    kod, d = uruchom(tmp, "ustaw", "--instancja", "dwa", "UH_KLAWISZ=F9")
    sprawdz("ustaw: pokrętło tekstowe z dozwolonych", kod == 0 and json.loads(plik.read_text())["UH_KLAWISZ"] == "F9")
    kod, d = uruchom(tmp, "ustaw", "--instancja", "dwa", "POGON_LIMIT=30")
    sprawdz("ustaw: całkowita liczba w pokrętle ułamkowym zachowuje typ liczby (30)", kod == 0 and json.loads(plik.read_text())["POGON_LIMIT"] == 30)
    kod, d = uruchom(tmp, "ustaw", "--instancja", "dwa", "POGON_ZASIEG=13.0")
    sprawdz("ustaw: 13.0 w pokrętle całkowitym zapisane jako 13", kod == 0 and plik.read_text().count('"POGON_ZASIEG": 13,') == 1, plik.read_text()[:60])

    # atomowość: zapis podmienia plik (nowy inode), nie nadpisuje w miejscu
    ino0 = plik.stat().st_ino
    kod, d = uruchom(tmp, "ustaw", "--instancja", "dwa", "KROKI_DO_ZWLOK=41")
    sprawdz("ustaw: zapis atomowy = zmienia się inode na_zywo.json (os.replace), nie kopiowanie w miejscu", kod == 0 and plik.stat().st_ino != ino0, (kod, d))
    # jedna reguła całkowita/ułamek: domyślna float w cavebocie = pokrętło ułamkowe w meta i w ustaw
    kod, d = uruchom(tmp, "pokretla", "--instancja", "dwa")
    typ_ogien = {p["klucz"]: p["typ"] for p in d["pokretla"]}["OGIEN_IGNORUJ_S"]
    kod, d = uruchom(tmp, "ustaw", "--instancja", "dwa", "OGIEN_IGNORUJ_S=2.5")
    sprawdz("typ_pokretla i ustaw mają tę samą regułę: domyślna float (OGIEN_IGNORUJ_S=0.0) -> ułamkowa i ustaw przyjmuje 2.5",
            typ_ogien == "ulamkowa" and kod == 0 and json.loads(plik.read_text())["OGIEN_IGNORUJ_S"] == 2.5, (typ_ogien, kod, d))
    kod, d = uruchom(tmp, "pokretla", "--instancja", "dwa")
    lst = {p["klucz"]: p["typ"] for p in d["pokretla"]}
    sprawdz("typ: domyślna int w cavebocie nadal całkowita, bez domyślnej też całkowita", lst["POGON_ZASIEG"] == "calkowita" and lst["LIMIT_WALKI"] == "calkowita", lst["LIMIT_WALKI"])
    kod, d = uruchom(tmp, "ustaw", "--instancja", "dwa", "LIMIT_WALKI=60.5")
    sprawdz("ustaw: ułamek w pokrętle całkowitym (domyślna int) nadal odrzucony", kod != 0 and d["ok"] is False, d)

    # uszkodzony plik: odmowa, bez zapisu
    plik.write_text("{ zepsute"); b0 = plik.read_bytes(); n_dz = dziennik.read_text()
    kod, d = uruchom(tmp, "ustaw", "--instancja", "dwa", "POGON_ZASIEG=12")
    sprawdz("ustaw: uszkodzony na_zywo.json = odmowa, plik i dziennik bez zmian", kod != 0 and d["ok"] is False and plik.read_bytes() == b0 and dziennik.read_text() == n_dz, d)

# dziennik cofania przycinany do ostatnich 200 wpisów (przy zapisie)
with tempfile.TemporaryDirectory() as tmp:
    r = zrob_korzen(tmp)
    dziennik = r / "instancje/dwa/okno_cofnij.jsonl"
    dziennik.write_text("".join(json.dumps({"czas": f"stary-{i}", "epoch": i, "przed": {}, "brak": [], "po": {}}) + "\n" for i in range(250)))
    kod, d = uruchom(tmp, "ustaw", "--instancja", "dwa", "POGON_ZASIEG=13")
    wp = [json.loads(l) for l in dziennik.read_text().splitlines()]
    sprawdz("ustaw: dziennik przycięty do 200 wpisów (najstarsze odpadają, nowy na końcu)", kod == 0 and len(wp) == 200 and wp[0]["czas"] == "stary-51"
            and wp[-1]["po"] == {"POGON_ZASIEG": 13}, (len(wp), wp[0]["czas"]))

# brak pliku na_zywo.json: powstaje, bez kopii, cofnij usuwa klucz
with tempfile.TemporaryDirectory() as tmp:
    r = zrob_korzen(tmp)
    plik = r / "instancje/dwa/na_zywo.json"; plik.unlink()
    kod, d = uruchom(tmp, "ustaw", "--instancja", "dwa", "POGON_ZASIEG=12")
    sprawdz("ustaw: brak pliku -> utworzony, bez .bak", kod == 0 and json.loads(plik.read_text()) == {"POGON_ZASIEG": 12} and not list(plik.parent.glob("*.bak*")), d)
    kod, d = uruchom(tmp, "cofnij", "--instancja", "dwa")
    sprawdz("cofnij: klucz dodany przez ustaw jest usuwany (nie zerowany)", kod == 0 and json.loads(plik.read_text()) == {} and d["usuniete"] == ["POGON_ZASIEG"], d)

# ================= cofnij =================
with tempfile.TemporaryDirectory() as tmp:
    r = zrob_korzen(tmp)
    plik, dziennik = r / "instancje/dwa/na_zywo.json", r / "instancje/dwa/okno_cofnij.jsonl"
    oryg = plik.read_bytes()
    kod, d = uruchom(tmp, "cofnij", "--instancja", "dwa")
    sprawdz("cofnij: pusty dziennik = błąd, plik bez zmian", kod != 0 and d["ok"] is False and plik.read_bytes() == oryg, d)
    uruchom(tmp, "ustaw", "--instancja", "dwa", "POGON_ZASIEG=13", "KROKI_DO_ZWLOK=40")
    b1 = plik.read_bytes()
    uruchom(tmp, "ustaw", "--instancja", "dwa", "POGON_ZASIEG=14", "POGON_LIMIT=29.5")
    kod, d = uruchom(tmp, "cofnij", "--instancja", "dwa")
    sprawdz("cofnij: przywraca dokładnie stan sprzed ostatniej zmiany (bajt w bajt)", kod == 0 and d["ok"] and plik.read_bytes() == b1, d)
    sprawdz("cofnij: zwraca przywrócone wartości i zmniejsza dziennik", d["przywrocone"] == {"POGON_ZASIEG": 13, "POGON_LIMIT": 20.0}
            and d["pozostalo_w_dzienniku"] == 1 and len(dziennik.read_text().splitlines()) == 1, d)
    kod, d = uruchom(tmp, "cofnij", "--instancja", "dwa")
    sprawdz("cofnij: drugi raz cofa wcześniejszą zmianę -> oryginał bajt w bajt (też usuwa dodany klucz)", kod == 0 and plik.read_bytes() == oryg, d)
    kod, d = uruchom(tmp, "cofnij", "--instancja", "dwa")
    sprawdz("cofnij: dziennik wyczerpany = błąd", kod != 0 and d["ok"] is False and plik.read_bytes() == oryg and not dziennik.read_text().strip(), d)
    sprawdz("cofnij: nie ruszył głównej instancji", (r / "na_zywo.json").read_bytes() == tekst_na_zywo(NA_ZYWO).encode())
    # dziennik z wartościami, które nie przechodzą walidacji (np. ręcznie edytowany): zły klucz POMINIĘTY i zgłoszony, reszta cofnięta
    uruchom(tmp, "ustaw", "--instancja", "dwa", "POGON_ZASIEG=13", "KROKI_DO_ZWLOK=40")
    b_przed_cofnij = plik.read_bytes()
    wpis = json.loads(dziennik.read_text().splitlines()[-1]); wpis["przed"] = {"POGON_ZASIEG": 999, "POGON_LIMIT": 22.5}
    dziennik.write_text(json.dumps(wpis) + "\n")
    kod, d = uruchom(tmp, "cofnij", "--instancja", "dwa")
    po = json.loads(plik.read_text())
    sprawdz("cofnij: zły klucz ze starego dziennika pominięty i zgłoszony, reszta wpisu cofnięta, dziennik zmniejszony",
            kod == 0 and d["ok"] and [x["klucz"] for x in d["pominiete"]] == ["POGON_ZASIEG"] and d["przywrocone"] == {"POGON_LIMIT": 22.5}
            and po["POGON_ZASIEG"] == 13 and po["POGON_LIMIT"] == 22.5 and "KROKI_DO_ZWLOK" not in po and not dziennik.read_text().strip(), d)

    # kopia przy cofnięciu: nie nadpisuje istniejącej z tego dnia
    sprawdz("cofnij/ustaw: jedna kopia dzienna", len(list(plik.parent.glob("na_zywo.json.bak-*"))) == 1)

# REGRESJA: wartość „przed” poza zakresem (bot ją ignoruje) nie może trwale blokować cofnij
with tempfile.TemporaryDirectory() as tmp:
    r = zrob_korzen(tmp)
    plik, dziennik = r / "instancje/dwa/na_zywo.json", r / "instancje/dwa/okno_cofnij.jsonl"
    plik.write_text(tekst_na_zywo(dict(NA_ZYWO, LIMIT_WALKI=999)))
    kod, d = uruchom(tmp, "ustaw", "--instancja", "dwa", "LIMIT_WALKI=50")
    wpis = json.loads(dziennik.read_text().splitlines()[-1])
    sprawdz("ustaw: poprzednia wartość poza zakresem trafia do dziennika jako brak klucza, nie jako „przed”",
            kod == 0 and wpis["przed"] == {} and wpis["brak"] == ["LIMIT_WALKI"], wpis)
    kod, d = uruchom(tmp, "cofnij", "--instancja", "dwa")
    po = json.loads(plik.read_text())
    sprawdz("cofnij po ustaw z poprzednią wartością 999: działa i usuwa klucz (bot i tak ją ignorował)", kod == 0 and d["ok"] and "LIMIT_WALKI" not in po
            and d["usuniete"] == ["LIMIT_WALKI"] and po["POGON_ZASIEG"] == 12, (kod, d))
    kod, d = uruchom(tmp, "ustaw", "--instancja", "dwa", "LIMIT_WALKI=60")
    kod2, d2 = uruchom(tmp, "cofnij", "--instancja", "dwa")
    kod3, d3 = uruchom(tmp, "cofnij", "--instancja", "dwa")
    sprawdz("cofnij nie blokuje się na stałe: kolejne cofnięcia dalej działają, potem czysty błąd „brak zmian”", kod2 == 0 and kod3 != 0 and "brak zmian" in d3["blad"], (d2, d3))

# równoległe zapisy (blokada): żadna zmiana nie ginie
with tempfile.TemporaryDirectory() as tmp:
    r = zrob_korzen(tmp)
    klucze = ["POGON_ZASIEG=13", "KROKI_DO_ZWLOK=40", "POGON_LIMIT=25", "LOOT_MAKS_PROB=5", "PK_OBRONA=1", "POSCIG_TRZYMAJ=0", "IGNOROWANIE=50", "LIMIT_WALKI=90"]
    with ThreadPoolExecutor(8) as ex:
        wyn = list(ex.map(lambda k: uruchom(tmp, "ustaw", "--instancja", "dwa", k), klucze))
    po = json.loads((r / "instancje/dwa/na_zywo.json").read_text())
    sprawdz("równoległe ustaw (8 procesów): wszystkie zapisane, żaden nie zgubiony", all(k == 0 for k, _ in wyn) and all(po.get(p.split("=")[0]) == float(p.split("=")[1]) for p in klucze), po)
    sprawdz("równoległe ustaw: dziennik ma 8 wpisów", len((r / "instancje/dwa/okno_cofnij.jsonl").read_text().splitlines()) == 8)

# ================= ratunek =================
def wpis_sygnalu(kod, opis, czas_, poz=(1, 2, 8), **extra):
    return json.dumps(dict({"kod": kod, "opis": opis, "t": 1.0, "poz": list(poz), "wolan_h": 1, "ponad_limit": False, "tryb": "cien", "stan": "IDZ", "czas": czas_}, **extra), ensure_ascii=False)

with tempfile.TemporaryDirectory() as tmp:
    r = zrob_korzen(tmp)
    logi = r / "instancje/dwa/logi"
    (logi / "ratunek-20261019.jsonl").write_text("\n".join([
        wpis_sygnalu("S3", "stoi", czas(8, 0)),                     # 4 h temu
        wpis_sygnalu("S3", "stoi", czas(11, 30)),                   # 30 min temu
        wpis_sygnalu("S6", "klik bez skutku", czas(11, 50), haiku={"decyzja": "czekaj"}),
        "to nie jest json",
        wpis_sygnalu("S3", "stoi", czas(11, 30)),                   # identyczna treść jak linia 2 — osobny id
        ""]) + "\n")
    (logi / "ratunek-20261018.jsonl").write_text(wpis_sygnalu("S1", "porażka trasy", czas(23, 0, 0, 18)) + "\n")
    (logi / "ratunek-20261001.jsonl").write_text(wpis_sygnalu("S7", "pusta pętla", czas(10, 0, 0, 1).replace("-19", "-01")) + "\n")
    (logi / "mozg-20261019.log").write_text("nie sygnały\n")
    pliki_sygnalow = [logi / "ratunek-20261019.jsonl", logi / "ratunek-20261018.jsonl", logi / "ratunek-20261001.jsonl"]
    hash0 = [sha(p) for p in pliki_sygnalow]
    kod, d = uruchom(tmp, "ratunek", "--instancja", "dwa")
    s = d["sygnaly"]
    sprawdz("ratunek: domyślnie 7 dni, sygnały od najnowszego (4 z 19.10 + 1 z 18.10), uszkodzona linia pominięta", kod == 0 and len(s) == 5 and d["pominiete_linie"] == 1
            and [x["kod"] for x in s] == ["S6", "S3", "S3", "S3", "S1"] and d["od"] == "2026-10-13", [x["kod"] for x in s])
    sprawdz("ratunek: każdy sygnał ma stabilny id, wszystkie różne (też dwie identyczne linie)", len({x["id"] for x in s}) == 5 and all(len(x["id"]) >= 12 for x in s))
    kod, d_b = uruchom(tmp, "ratunek", "--instancja", "dwa")
    sprawdz("ratunek: id te same przy kolejnym wywołaniu", [x["id"] for x in d_b["sygnaly"]] == [x["id"] for x in s])
    sprawdz("ratunek: pola sygnału (czas, kod, opis, poz, stan, plik, linia, dane)", s[0]["czas"] == czas(11, 50) and s[0]["opis"] == "klik bez skutku" and s[0]["poz"] == [1, 2, 8]
            and s[0]["plik"] == "ratunek-20261019.jsonl" and s[0]["linia"] == 3 and s[0]["dane"]["haiku"] == {"decyzja": "czekaj"} and s[0]["etykieta"] is None, s[0])
    L = d["liczniki"]
    sprawdz("ratunek: licznik dziś = 4", L["dzis"] == 4, L)
    sprawdz("ratunek: ostatnia godzina = 3 (11:30, 11:30, 11:50)", L["ostatnia_godzina"] == 3, L)
    sprawdz("ratunek: najczęstszy kod S3 (3 razy)", L["najczestszy_kod"]["kod"] == "S3" and L["najczestszy_kod"]["ile"] == 3 and L["kody"] == {"S3": 3, "S6": 1, "S1": 1}, L)
    sprawdz("ratunek: limit_h i haiku z pokręteł instancji", L["limit_h"] == 20 and L["haiku"] == 0, L)
    kod, d2 = uruchom(tmp, "ratunek", "--instancja", "dwa", "--od", "2026-10-19")
    sprawdz("ratunek --od 2026-10-19: tylko dzisiejsze (4), bez wczorajszego", len(d2["sygnaly"]) == 4 and d2["od"] == "2026-10-19")
    kod, d3 = uruchom(tmp, "ratunek", "--instancja", "dwa", "--od", "2026-10-01")
    sprawdz("ratunek --od 2026-10-01: też stary plik (6)", len(d3["sygnaly"]) == 6)
    sprawdz("ratunek: zły format --od = błąd (kod 2)", uruchom(tmp, "ratunek", "--instancja", "dwa", "--od", "wczoraj")[0] == 2)
    sprawdz("ratunek: główna instancja nie widzi sygnałów instancji dwa", uruchom(tmp, "ratunek")[1]["sygnaly"] == [])


    # oznaczanie
    cel, inny = s[1]["id"], s[2]["id"]
    kod, o = uruchom(tmp, "ratunek-oznacz", "--instancja", "dwa", "--id", cel, "--falszywy")
    sprawdz("ratunek-oznacz: ok i wpis w ratunek-etykiety.jsonl", kod == 0 and o["ok"] and o["etykieta"] == "falszywy"
            and json.loads((logi / "ratunek-etykiety.jsonl").read_text().splitlines()[0])["id"] == cel, o)
    sprawdz("ratunek-oznacz: pliki sygnałów bajtowo bez zmian", [sha(p) for p in pliki_sygnalow] == hash0)
    kod, d4 = uruchom(tmp, "ratunek", "--instancja", "dwa")
    et = {x["id"]: x["etykieta"] for x in d4["sygnaly"]}
    sprawdz("ratunek: etykieta połączona z właściwym sygnałem, reszta bez", et[cel] == "falszywy" and sum(1 for v in et.values() if v) == 1, et)
    sprawdz("ratunek: plik etykiet nie jest czytany jako plik sygnałów (nadal 5 sygnałów, 1 pominięta linia)", len(d4["sygnaly"]) == 5 and d4["pominiete_linie"] == 1)
    sprawdz("ratunek: licznik fałszywych", d4["liczniki"]["falszywe"] == 1)
    uruchom(tmp, "ratunek-oznacz", "--instancja", "dwa", "--id", cel, "--prawdziwy")
    uruchom(tmp, "ratunek-oznacz", "--instancja", "dwa", "--id", inny, "--falszywy")
    d5 = uruchom(tmp, "ratunek", "--instancja", "dwa")[1]
    et = {x["id"]: x["etykieta"] for x in d5["sygnaly"]}
    sprawdz("ratunek-oznacz: ostatni wpis wygrywa; druga etykieta niezależna", et[cel] == "prawdziwy" and et[inny] == "falszywy"
            and len((logi / "ratunek-etykiety.jsonl").read_text().splitlines()) == 3 and d5["liczniki"]["prawdziwe"] == 1)
    sprawdz("ratunek-oznacz: pliki sygnałów nadal bez zmian", [sha(p) for p in pliki_sygnalow] == hash0)
    etyk_przed = (logi / "ratunek-etykiety.jsonl").read_bytes()
    kod, o = uruchom(tmp, "ratunek-oznacz", "--instancja", "dwa", "--id", "nieistniejacy", "--falszywy")
    sprawdz("ratunek-oznacz: nieznany id = błąd, plik etykiet bez zmian", kod != 0 and o["ok"] is False and (logi / "ratunek-etykiety.jsonl").read_bytes() == etyk_przed, o)
    kod, o = uruchom(tmp, "ratunek-oznacz", "--instancja", "dwa", "--id", cel)
    sprawdz("ratunek-oznacz: bez --falszywy/--prawdziwy = błąd użycia", kod == 2 and o["ok"] is False)
    kod, o = uruchom(tmp, "ratunek-oznacz", "--instancja", "dwa", "--id", cel, "--falszywy", "--prawdziwy")
    sprawdz("ratunek-oznacz: oba naraz = błąd użycia", kod == 2 and o["ok"] is False and (logi / "ratunek-etykiety.jsonl").read_bytes() == etyk_przed)
    kod, o = uruchom(tmp, "ratunek-oznacz", "--instancja", "nie_ma", "--id", cel, "--falszywy")
    sprawdz("ratunek-oznacz: nieznana instancja = błąd", kod != 0 and o["ok"] is False)
    # id niezależne od numeru linii i pliku: ta sama treść -> to samo id
    plik19 = logi / "ratunek-20261019.jsonl"
    zawartosc = plik19.read_text()
    plik19.write_text(wpis_sygnalu("S2", "złe piętro", czas(9, 0)) + "\n" + zawartosc)
    d6 = uruchom(tmp, "ratunek", "--instancja", "dwa")[1]
    sprawdz("ratunek: id sygnału nie zależy od numeru linii (dopisanie linii na początku nie zmienia id pozostałych)", cel in {x["id"] for x in d6["sygnaly"]} and len(d6["sygnaly"]) == 6)

# ================= mapy-tryby =================
with tempfile.TemporaryDirectory() as tmp:
    r = zrob_korzen(tmp)
    kod, d = uruchom(tmp, "mapy-tryby", "--instancja", "dwa")
    sprawdz("mapy-tryby: mapy z opisem (bez _opis)", kod == 0 and [m["nazwa"] for m in d["mapy"]] == ["raty", "trolle"] and d["mapy"][0]["opis"] == "Thais szczury"
            and d["mapy"][0]["dane"]["trasa"] == "t1", d["mapy"])
    sprawdz("mapy-tryby: tryby z opisem i pokrętłami", [t["nazwa"] for t in d["tryby"]] == ["sredni", "ml"] and d["tryby"][0]["opis"] == "średnio"
            and d["tryby"][0]["pokretla"] == {"RUNA_AKTYWNA": 1} and d["tryby"][0]["ile_pokretel"] == 1)
    sprawdz("mapy-tryby: ostatnia mapa i tryby instancji (rozpoznany \\, w .env)", d["ostatni"]["mapa"] == "trolle" and d["ostatni"]["tryb"] == ["sredni", "ml"]
            and d["ostatni"]["mapa_znana"] is True and d["ostatni"]["tryby_nieznane"] == [], d["ostatni"])
    dg = uruchom(tmp, "mapy-tryby")[1]
    sprawdz("mapy-tryby: główna czyta ostatni_start.env (nie .dwa.env)", dg["ostatni"]["mapa"] == "raty" and dg["ostatni"]["tryb"] == ["sredni"])
    (r / "ostatni_start.dwa.env").write_text("MAPA=nie_ma\nTRYB=zly\\,sredni\n")
    d2 = uruchom(tmp, "mapy-tryby", "--instancja", "dwa")[1]
    sprawdz("mapy-tryby: nieznana mapa/tryb oznaczone", d2["ostatni"]["mapa_znana"] is False and d2["ostatni"]["tryby_nieznane"] == ["zly"])
    (r / "ostatni_start.dwa.env").unlink()
    d3 = uruchom(tmp, "mapy-tryby", "--instancja", "dwa")[1]
    sprawdz("mapy-tryby: brak pliku ostatni_start = puste, bez błędu", d3["ok"] and d3["ostatni"]["mapa"] is None and d3["ostatni"]["tryb"] == [])
    (r / "mapy.json").write_text("{ zepsute")
    d4 = uruchom(tmp, "mapy-tryby")[1]
    sprawdz("mapy-tryby: uszkodzony mapy.json = blad_map, tryby nadal działają", d4["ok"] and d4["mapy"] == [] and d4["blad_map"] and len(d4["tryby"]) == 2)

# ================= stan =================
with tempfile.TemporaryDirectory() as tmp:
    r = zrob_korzen(tmp, instancje=("dwa", "trzy", "cztery"))
    (r / "instancje/dwa/logi/ratunek-20261019.jsonl").write_text("\n".join(wpis_sygnalu("S3", "stoi", czas(11, i)) for i in range(3)) + "\n")
    (r / "instancje/trzy/logi/ratunek-20261018.jsonl").write_text(wpis_sygnalu("S3", "stoi", czas(11, 0, 0, 18)) + "\n")     # wczoraj: nie liczy się
    (r / "panel_tryb.trzy").write_text("crash")
    (r / "panel_tryb.cztery").write_text("garbage")
    (Path(tmp) / "rt" / "retronic-dwa.sock").write_text("")
    (Path(tmp) / "rt" / "retronic-pomocnik.sock").write_text("")
    proces(tmp, 101, ["python3", "-I", "mozg.py", "skrypt", "--tryb", "ml"], {"RETRONIC_ID": "dwa", "RETRONIC_POSTAC": "Johny"})
    proces(tmp, 102, ["python3", "-I", "straznik.py", "wine", "RetronicGL.exe"], {"RETRONIC_ID": "dwa"})
    proces(tmp, 103, ["sway", "--unsupported-gpu", "-c", f"{tmp}/rt/retronic-sesja-dwa/sway.conf"], {})
    proces(tmp, 104, ["python3", "-I", "cavebot.py"], {"RETRONIC_ID": "trzy"})
    proces(tmp, 105, ["python3", "-I", "mozg.py"], {})                                   # główna
    proces(tmp, 106, ["sway", "-c", f"{tmp}/rt/retronic-sesja/sway.conf"], {})           # sesja głównej
    proces(tmp, 107, ["python3", "-I", "inny_skrypt.py"], {"RETRONIC_ID": "cztery"})     # nie bot
    t0 = time.monotonic(); kod, d = uruchom(tmp, "stan"); dt = time.monotonic() - t0
    ins = {x["id"]: x for x in d["instancje"]}
    sprawdz("stan: ok, instancje: główna + katalogi z poprawnym id (bez _wspolne, bez złych nazw i plików)", kod == 0 and d["ok"] and [x["id"] for x in d["instancje"]] == ["", "cztery", "dwa", "trzy"], list(ins))
    sprawdz("stan: główna nazywa się 'główna'", ins[""]["nazwa"] == "główna" and ins["dwa"]["nazwa"] == "dwa")
    w = ins["dwa"]
    sprawdz("stan: wynik panel.py --json dołączony i uruchomiony z RETRONIC_ID instancji", w["panel"]["id"] == "dwa" and ins[""]["panel"]["id"] == "" and w["klasa"] == "dziala", w["panel"])
    sprawdz("stan: HP/mana z panelu", w["gracz"] == {"hp": 100, "max_hp": 200, "mana": 30, "max_mana": 60}, w["gracz"])
    sprawdz("stan: gra (gniazdo), sesja (sway), klient, bot, nick instancji dwa", w["gra"] is True and w["sesja"] is True and w["klient_pids"] == [102]
            and w["bot"] is True and w["bot_procesy"] == [{"pid": 101, "tryb": "mozg.py ml"}] and w["nick"] == "Johny", w)
    sprawdz("stan: procesy innych instancji nie przeciekają (trzy: cavebot.py, brak gniazda/sesji; główna: własny mozg i sway)",
            ins["trzy"]["bot"] is True and ins["trzy"]["gra"] is False and ins["trzy"]["sesja"] is False and ins["trzy"]["klient_pids"] == []
            and ins[""]["bot"] is True and ins[""]["sesja"] is True and ins[""]["gra"] is True and ins[""]["bot_procesy"][0]["pid"] == 105 and ins["cztery"]["bot"] is False, (ins["trzy"], ins[""]))
    sprawdz("stan: ostatnia mapa i tryb z ostatni_start*.env", w["mapa"] == "trolle" and w["tryb"] == ["sredni", "ml"] and ins[""]["mapa"] == "raty")
    sprawdz("stan: dzisiejsze sygnały ratunku (dwa=3, trzy=0 bo wczorajszy, główna=0)", (w["ratunek_dzis"], ins["trzy"]["ratunek_dzis"], ins[""]["ratunek_dzis"]) == (3, 0, 0))
    sprawdz("stan: awaria panelu jednej instancji (crash) = pole blad w niej, panel None", ins["trzy"]["blad"] and "panel" in ins["trzy"]["blad"] and ins["trzy"]["panel"] is None, ins["trzy"]["blad"])
    sprawdz("stan: śmieci zamiast JSON z panelu = blad w niej", ins["cztery"]["blad"] and ins["cztery"]["panel"] is None)
    sprawdz("stan: awaria jednej nie psuje pozostałych (dwa i główna bez błędu, z danymi)", w["blad"] is None and ins[""]["blad"] is None and w["panel"] and ins[""]["panel"])
    sprawdz("stan: mimo awarii panelu reszta pól awarii instancji nadal wypełniona (trzy: bot z procesów, ostatnia mapa)", ins["trzy"]["bot"] is True and ins["trzy"]["bot_procesy"][0]["tryb"] == "cavebot.py")

# limit czasu pojedynczego panelu
with tempfile.TemporaryDirectory() as tmp:
    r = zrob_korzen(tmp, instancje=("wolna", "szybka"))
    (r / "panel_tryb.wolna").write_text("sleep:6")
    t0 = time.monotonic(); kod, d = uruchom(tmp, "stan"); dt = time.monotonic() - t0
    ins = {x["id"]: x for x in d["instancje"]}
    sprawdz("stan: wolny panel (6 s) odcięty limitem: blad w tej instancji, reszta ok, całość < 2,5 s", ins["wolna"]["blad"] and "limit" in ins["wolna"]["blad"] and ins["szybka"]["blad"] is None
            and ins[""]["blad"] is None and dt < 2.5, (dt, ins["wolna"]["blad"]))

# 10 instancji naraz, każdy panel 0,4 s: równolegle (sekwencyjnie byłoby > 4 s)
with tempfile.TemporaryDirectory() as tmp:
    ids = tuple(f"bot{i}" for i in range(10))
    r = zrob_korzen(tmp, instancje=ids)
    for i in ids:
        (r / f"panel_tryb.{i}").write_text("sleep:0.4")
    (r / "panel_tryb.glowna").write_text("sleep:0.4")
    t0 = time.monotonic(); kod, d = uruchom(tmp, "stan"); dt = time.monotonic() - t0
    sprawdz("stan: 10 instancji + główna, wszystkie z danymi i bez błędów", kod == 0 and len(d["instancje"]) == 11 and all(x["blad"] is None and x["panel"] for x in d["instancje"]), [x["blad"] for x in d["instancje"]])
    sprawdz("stan: 10 instancji odczytanych równolegle w limicie (< 2 s przy panelu 0,4 s każdy; sekwencyjnie > 4 s)", dt < 2.0 and d["czas_odczytu_s"] < 2.0, (dt, d["czas_odczytu_s"]))

# stan --instancja ID: tylko ta instancja i tylko jej panel.py --json
with tempfile.TemporaryDirectory() as tmp:
    r = zrob_korzen(tmp, instancje=("dwa", "trzy", "cztery"))
    proces(tmp, 101, ["python3", "-I", "mozg.py"], {"RETRONIC_ID": "dwa", "RETRONIC_POSTAC": "Johny"})
    log_panelu = r / "panel_wywolania.log"
    kod, d = uruchom(tmp, "stan", "--instancja", "dwa")
    sprawdz("stan --instancja: tylko ta instancja w wyniku, z danymi", kod == 0 and d["ok"] and [x["id"] for x in d["instancje"]] == ["dwa"]
            and d["instancje"][0]["panel"]["id"] == "dwa" and d["instancje"][0]["nick"] == "Johny", d)
    sprawdz("stan --instancja: panel.py --json wołany tylko dla niej (3 innych bez wywołania)", log_panelu.read_text().split() == ["dwa"], log_panelu.read_text() if log_panelu.exists() else None)
    kod, d = uruchom(tmp, "stan", "--instancja", "główna")
    sprawdz("stan --instancja główna: tylko główna", kod == 0 and [x["id"] for x in d["instancje"]] == [""] and log_panelu.read_text().split() == ["dwa", "glowna"])
    kod, d = uruchom(tmp, "stan", "--instancja", "../../etc")
    sprawdz("stan --instancja ze złym id = błąd, nie traceback", kod != 0 and d["ok"] is False and "surowe" not in d, d)
    kod, d = uruchom(tmp, "stan", "--instancja", "nie_ma")
    sprawdz("stan --instancja nieznana = błąd", kod != 0 and d["ok"] is False)
    log_panelu.unlink()
    kod, d = uruchom(tmp, "stan")
    sprawdz("stan bez --instancja nadal wszystkie (4), panel dla każdej", kod == 0 and len(d["instancje"]) == 4 and sorted(log_panelu.read_text().split()) == ["cztery", "dwa", "glowna", "trzy"])

# stan: przekroczony limit całości wypełnia bot/sesja/nick z już zebranego skanu procesów (nie same null)
with tempfile.TemporaryDirectory() as tmp:
    r = zrob_korzen(tmp, instancje=("wolna",))
    (r / "panel_tryb.wolna").write_text("sleep:1")
    proces(tmp, 201, ["python3", "-I", "mozg.py", "skrypt", "--tryb", "ml"], {"RETRONIC_ID": "wolna", "RETRONIC_POSTAC": "Wolny"})
    proces(tmp, 202, ["sway", "-c", f"{tmp}/rt/retronic-sesja-wolna/sway.conf"], {})
    zapas = {k: _os.environ.get(k) for k in ("RETRONIC_OKNO_KATALOG", "RETRONIC_OKNO_PROC", "RETRONIC_OKNO_TERAZ", "XDG_RUNTIME_DIR")}
    limit0 = okno_api.CALOSC_LIMIT_S
    try:
        _os.environ.update(RETRONIC_OKNO_KATALOG=str(r), RETRONIC_OKNO_PROC=str(Path(tmp) / "proc"), RETRONIC_OKNO_TERAZ=str(TERAZ),
                           XDG_RUNTIME_DIR=str(Path(tmp) / "rt"))
        okno_api.CALOSC_LIMIT_S = 0.3
        d = okno_api.cmd_stan("wolna")
    finally:
        okno_api.CALOSC_LIMIT_S = limit0
        for k, v in zapas.items():
            _os.environ.pop(k, None) if v is None else _os.environ.__setitem__(k, v)
    w = d["instancje"][0]
    sprawdz("stan: przekroczony limit całości = blad 'limit', ale bot/sesja/nick z skanu procesów (nie null)", w["blad"] and "limit" in w["blad"] and w["panel"] is None
            and w["bot"] is True and w["sesja"] is True and w["nick"] == "Wolny" and w["bot_procesy"] == [{"pid": 201, "tryb": "mozg.py ml"}], w)

# ================= błędy użycia i JSON zawsze =================
with tempfile.TemporaryDirectory() as tmp:
    zrob_korzen(tmp)
    kod, d = uruchom(tmp)
    sprawdz("brak polecenia = JSON ok:false i kod 2", kod == 2 and d["ok"] is False and d["blad"], (kod, d))
    kod, d = uruchom(tmp, "zepsuj")
    sprawdz("nieznane polecenie = JSON ok:false i kod 2", kod == 2 and d["ok"] is False)
    kod, d = uruchom(tmp, "pokretla", "--instancja", "../../etc")
    sprawdz("zła nazwa instancji (ścieżka) = błąd, nie traceback", kod != 0 and d["ok"] is False and "surowe" not in d, d)
    kod, d = uruchom(tmp, "pokretla", "--instancja", "główna")
    sprawdz("alias 'główna' = instancja główna", kod == 0 and d["instancja"] == "")


# F2a: rekord haiku_cien (osobna linia, to samo `id`) dołączany do sygnału, nie liczony jako sygnał
with tempfile.TemporaryDirectory() as tmp:
    r = zrob_korzen(tmp)
    logi = r / "instancje/dwa/logi"
    hc = {"ruch": "krok N", "powod": None, "dlaczego": "drabina", "czas_wywolania_s": 2.0, "zrzut": "ratunek-zrzuty/a1.jpg", "wykonano": False}
    (logi / "ratunek-20261019.jsonl").write_text("\n".join([
        wpis_sygnalu("S4", "kręci się", czas(11, 40), id="a1"),
        json.dumps({"rekord": "haiku_cien", "id": "a1", "kod": "S4", "poz": [1, 2, 8], "czas": czas(11, 40), "haiku_cien": hc}),
        wpis_sygnalu("S3", "stoi", czas(11, 45), id="b2"),
        json.dumps({"rekord": "haiku_cien", "id": "zz", "haiku_cien": {"ruch": "czekaj 3"}})]) + "\n")
    kod, d = uruchom(tmp, "ratunek", "--instancja", "dwa")
    s_ = {x["kod"]: x for x in d["sygnaly"]}
    sprawdz("ratunek F2a: rekordy haiku_cien nie są sygnałami (2 sygnały)", kod == 0 and len(d["sygnaly"]) == 2 and d["liczniki"]["dzis"] == 2, d["sygnaly"])
    sprawdz("ratunek F2a: odpowiedź dołączona do sygnału o tym samym id", s_["S4"]["dane"].get("haiku_cien") == hc and "haiku_cien" not in s_["S3"]["dane"], s_)
    sprawdz("ratunek F2a: ścieżka zrzutu w katalogu logów instancji", s_["S4"].get("haiku_zrzut") == str((logi / "ratunek-zrzuty/a1.jpg").resolve()), s_["S4"].get("haiku_zrzut"))
    for zly in ("/etc/passwd", "a/../../b.jpg", "../x.jpg"):
        (logi / "ratunek-20261019.jsonl").write_text(wpis_sygnalu("S4", "kręci się", czas(11, 40), id="c3") + "\n"
            + json.dumps({"rekord": "haiku_cien", "id": "c3", "haiku_cien": dict(hc, zrzut=zly)}) + "\n")
        kod, d = uruchom(tmp, "ratunek", "--instancja", "dwa")
        sprawdz(f"ratunek F2a: zrzut poza katalogiem logów odrzucony ({zly})", "haiku_zrzut" not in d["sygnaly"][0], d["sygnaly"][0].get("haiku_zrzut"))

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
