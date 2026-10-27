"""Przełącznik STÓJ (23.10, Karol): „wystarczy, żeby wyłączał chodzenie po prostu i robił runy; chciałbym móc to włączyć
w dowolnym momencie". Plik-flaga `instancje/<id>/STOJ` (jak STOP, ale bot NIE kończy pracy): działa na gorąco, na każdej
mapie i w każdym trybie, bez restartu. Obsługa: `./stoj.sh <id> on|off|stan`.

Co robi cavebot, gdy flaga istnieje (cavebot.py: `Cavebot._stoj_*`):
  * nie chodzi: żadnej trasy, dojścia, patrolu, wypraw, lootu z podejściem ani pościgu za celem (tylko cel przy nas, <= 1 pole);
  * robi runy (UH / HMM), leczy się (exura) i je, broni się w miejscu;
  * ucieka tylko tak, jak dotąd (progi HP / PK / OGIEN bez zmian);
  * zapamiętuje pole, na którym stał w chwili włączenia, i po każdym przesunięciu (pchnięcie przez gracza, ucieczka) na nie
    wraca (jak `stanowisko.py`: „nie da się go przesunąć"). Pole leży w pliku flagi (JSON), więc przeżywa restart bota;
  * nadzor.py nie liczy stania za zawieszenie (`zaciecie`), a strażniki/zwiecha/ratunek są wyłączone.
Wyłączenie: bot wraca do zwykłej pracy od najbliższego punktu trasy.
Opcjonalnie (24.10, pokrętło `STOJ_GRACZ_WYLOGUJ_ODL` w na_zywo.json, domyślnie 0 = wył.): obcy gracz (nie NPC, nie nasza postać)
bliżej niż N pól przez 2 odczyty = koniec run, wylogowanie Ctrl+L, STOP + STOP_RECZNY i koniec bota (stoj_obcy.py). Nie jest
ustawiane ani cofane przez `on`/`off`: włącza je Karol osobno (`python3 -I okno_api.py ustaw --instancja <id> STOJ_GRACZ_WYLOGUJ_ODL=3`).

Start „tu i teraz" (23.10, Karol: „żeby w tym trybie od razu stał w miejscu, w którym go włączam, żeby nie potrzebował mapy i żeby
odpisywał, jadł automatycznie"). `./stoj.sh <id> on` działa w trzech przypadkach:
  * bot chodzi w trybie z modelem (hybryda / ai): tylko flaga + zapamiętane pole = obecna pozycja (na gorąco, bez restartu);
  * bot chodzi w trybie skrypt (bez modelu, nie odpisuje na czacie; model da się włączyć tylko przy starcie): restart w hybrydzie
    na obecnej pozycji (`--bez-restartu` = sama flaga, bez odpowiadania);
  * bot nie chodzi (postać zalogowana, Karol gra albo STOP_RECZNY): `uruchom.sh` z STOJ_TU (trasa jednopunktowa
    trasy/_stoj_tu_<id>.json z obecnej pozycji, bez mapy.json i dojścia) w hybrydzie; STOP i STOP_RECZNY zdejmuje uruchom.sh.
Start świeży i restart ustawiają pokrętła (UH od lvl 11 i ML >= 11, inaczej HMM; exura zawsze; jedzenie z plecaka; exevo pan od
lvl 14) i zapisują ich poprzednie wartości w pliku flagi. `off`: na gorąco = zdjęcie flagi; po restarcie = powrót do ostatniej
mapy/trybu (ostatni_start.<id>.env, mózg jak przed STÓJ); po starcie świeżym = stop bota + STOP_RECZNY (Karol znów gra).
Pokrętła wracają do wartości sprzed STÓJ (tylko te, których od tamtej pory nikt nie zmienił)."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

NAZWA = "STOJ"
KAT = Path(__file__).resolve().parent
UH_MIN_LVL = 11                     # Karol: UH od lvl 11 i ML >= 11, niżej HMM (tryb runy z tryby.json)
UH_MIN_ML = 11
PAN_MIN_LVL = 14                    # ZAŁOŻENIE (23.10): exevo pan od lvl 14; niżej jedzenie wyłącznie z plecaka
PROG_HP = 50                        # próg ucieczki startu świeżego (jak stoj_uh_edron_horn)
MOZG_STOJ = "hybryda"               # mózg startu STÓJ: odpisuje na czacie (Karol 23.10)


# --- flaga -----------------------------------------------------------------------------------------

def plik(katalog=None):
    """Ścieżka flagi; bez argumentu: katalog stanu bieżącej instancji (RETRONIC_ID)."""
    if katalog is None:
        import instancja  # noqa: PLC0415
        katalog = instancja.S.stan
    return Path(katalog) / NAZWA


def wlaczony(katalog=None):
    try:
        return plik(katalog).exists()
    except OSError:
        return False


def dane(katalog=None):
    """Cała zawartość flagi jako słownik ({} gdy pusta / zły JSON)."""
    try:
        d = json.loads(plik(katalog).read_text() or "{}")
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def zapisz_dane(d, katalog=None):
    """Zapis atomowy całego słownika flagi. Błąd zapisu -> False (bot zachowuje pole w pamięci)."""
    f = plik(katalog)
    try:
        tmp = f.with_name(NAZWA + ".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False))
        os.replace(tmp, f)
        return True
    except OSError:
        return False


def pole(katalog=None):
    """Zapamiętane pole (x, y, z) z pliku flagi albo None (flaga pusta / bez pola / zły JSON)."""
    d = dane(katalog)
    if isinstance(d.get("pole"), (list, tuple)) and len(d["pole"]) >= 3:
        try:
            return tuple(int(v) for v in d["pole"][:3])
        except (TypeError, ValueError):
            return None
    return None


def zapisz_pole(p, katalog=None):
    """Zapisuje pole w pliku flagi, ZACHOWUJĄC pozostałe klucze (start, poprzednie pokrętła). Błąd zapisu nie przerywa pracy."""
    d = dane(katalog)
    d.update({"pole": [int(v) for v in p[:3]], "od": round(time.time())})
    return zapisz_dane(d, katalog)


def wlacz(katalog=None):
    """-> True, gdy włączone teraz; False, gdy już było włączone (pole w pliku zostaje)."""
    f = plik(katalog)
    f.parent.mkdir(parents=True, exist_ok=True)
    if f.exists():
        return False
    f.touch()
    return True


def wylacz(katalog=None):
    try:
        plik(katalog).unlink()
        return True
    except FileNotFoundError:
        return False


def opis(katalog=None):
    if not wlaczony(katalog):
        return "STÓJ: wyłączony"
    d = dane(katalog)
    p = pole(katalog)
    start = {"goracy": "na gorąco", "restart": "restart w hybrydzie", "swiezy": "start świeży"}.get(d.get("start"), "")
    return "STÓJ: włączony" + (f", pole {p}" if p else " (pole zapamięta bot przy najbliższym obiegu)") + (f", {start}" if start else "")


# --- odczyt postaci i bota (wstrzykiwalne w testach) ---------------------------------------------------

def nick_z_profilu(katalog):
    try:
        return (json.loads((Path(katalog) / "profil.json").read_text()).get("postac") or "").strip()
    except (OSError, ValueError):
        return ""


def zapytaj_gniazdo(id_):
    import instancja  # noqa: PLC0415
    import ml_zywo  # noqa: PLC0415
    return ml_zywo.zapytaj_gniazdo(instancja.sciezki(id_, instancja.runtime("/tmp"), katalog=KAT).gniazdo)


def odczytaj_postac(zapytaj, nick):
    """-> {"pole": (x, y, z), "level": int, "ml": int|None} z gniazda strażnika (same odczyty). Rzuca RuntimeError, gdy postaci nie widać."""
    if not nick:
        raise RuntimeError("profil.json bez nicka postaci (pole `postac`)")
    try:
        p = zapytaj({"cmd": "pozycja", "nazwa": nick})["pozycja"]
        poz = (int(p["x"]), int(p["y"]), int(p["z"]))
        g = zapytaj({"cmd": "gracz"})["gracz"]
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"strażnik nie widzi postaci {nick!r} ({e})") from e
    ml = None
    try:
        import ml_zywo  # noqa: PLC0415
        w = ml_zywo.odczytaj(zapytaj, g)
        ml = w["ml"] if w else None
    except Exception:  # noqa: BLE001
        ml = None
    return {"pole": poz, "level": int(g.get("level") or 0), "ml": ml}


def pozycja_gorace(zapytaj, nick):
    """Pole dla trybu gorącego: tylko pozycja (None, gdy gniazdo/postać niedostępne; wtedy bot sam zapamięta pole)."""
    try:
        p = zapytaj({"cmd": "pozycja", "nazwa": nick})["pozycja"]
        return (int(p["x"]), int(p["y"]), int(p["z"]))
    except Exception:  # noqa: BLE001
        return None


def tryb_bota(id_, procesy=None, czytaj_cmdline=None):
    """-> (jest_bot, tryb_mozgu|None). jest_bot: działa mozg.py / cavebot.py tej instancji. tryb: wartość `--tryb` mozg.py."""
    import instancja  # noqa: PLC0415
    procesy = procesy or instancja.procesy
    czytaj = czytaj_cmdline or (lambda pid: Path(f"/proc/{pid}/cmdline").read_bytes().decode(errors="replace").split("\0"))
    pidy = procesy(r"(mozg|cavebot)\.py", id_)
    tryb = None
    for pid in pidy:
        try:
            arg = czytaj(pid)
        except OSError:
            continue
        if any(a.endswith("mozg.py") for a in arg) and "--tryb" in arg:
            i = arg.index("--tryb")
            if i + 1 < len(arg):
                tryb = arg[i + 1]
    return bool(pidy), tryb


# --- pokrętła -----------------------------------------------------------------------------------------

def wczytaj_tryby(kat=KAT):
    d = json.loads((Path(kat) / "tryby.json").read_text())
    return {k: v for k, v in d.items() if not k.startswith("_")}


def pokretla_stoj(level, ml, kat=KAT):
    """Pokrętła startu STÓJ -> (słownik, nazwa trybu run). Runy: UH od lvl 11 i ML >= 11 (tryb `uh`), inaczej HMM (tryb `runy`);
    exura zawsze; jedzenie z plecaka przy głodzie, exevo pan od lvl 14; bez wypraw, refillu i stanowiska (stoimy tam, gdzie jesteśmy)."""
    tryby = wczytaj_tryby(kat)
    uh = level >= UH_MIN_LVL and ml is not None and ml >= UH_MIN_ML
    nazwa = "uh" if uh else "runy"
    k = dict(tryby[nazwa]["pokretla"])
    k.update(tryby["bez_wypraw"]["pokretla"])
    k.update({"STANOWISKO": 0, "WYPRAWA_DEPO_BLANKI": 0, "ZDROWIE_CZAR_AKTYWNY": 1, "ML_CZAR_AKTYWNY": 0,
              "JEDZENIE_CZAR_AKTYWNY": 1 if level >= PAN_MIN_LVL else 0})
    return k, nazwa


def zastosuj_pokretla(plik_na_zywo, nowe, log=print):
    """Scala `nowe` do na_zywo.json (z kopią .bak-<czas>); -> {klucz: poprzednia wartość albo None, gdy klucza nie było}."""
    import pokretla  # noqa: PLC0415
    ok, bledy = pokretla.waliduj(dict(nowe))
    if bledy:
        raise ValueError("niepoprawne pokrętła STÓJ: " + "; ".join(map(str, bledy)))
    f = Path(plik_na_zywo)
    try:
        przed = json.loads(f.read_text())
        przed = przed if isinstance(przed, dict) else {}
    except (OSError, ValueError):
        przed = {}
    poprzednie = {k: przed.get(k) for k in ok if przed.get(k, object()) != ok[k]}
    if not poprzednie:
        return {}
    if f.exists():
        f.with_name(f.name + time.strftime(".bak-%Y%m%d-%H%M%S-stoj")).write_text(f.read_text())
    f.write_text(json.dumps({**przed, **ok}, ensure_ascii=False, indent=1))
    log("STÓJ: pokrętła: " + ", ".join(f"{k} {poprzednie[k]} -> {ok[k]}" for k in poprzednie))
    return poprzednie


def cofnij_pokretla(plik_na_zywo, poprzednie, ustawione, log=print):
    """Przywraca poprzednie wartości pokręteł, ale tylko tam, gdzie obecna wartość to nadal ta ustawiona przez STÓJ."""
    f = Path(plik_na_zywo)
    try:
        teraz = json.loads(f.read_text())
        teraz = teraz if isinstance(teraz, dict) else {}
    except (OSError, ValueError):
        return []
    cofniete = []
    for k, stara in (poprzednie or {}).items():
        if k in teraz and teraz[k] == (ustawione or {}).get(k):
            if stara is None:
                del teraz[k]
            else:
                teraz[k] = stara
            cofniete.append(k)
    if cofniete:
        f.with_name(f.name + time.strftime(".bak-%Y%m%d-%H%M%S-stoj-off")).write_text(f.read_text())
        f.write_text(json.dumps(teraz, ensure_ascii=False, indent=1))
        log("STÓJ: pokrętła przywrócone: " + ", ".join(cofniete))
    return cofniete


# --- włączanie i wyłączanie ----------------------------------------------------------------------------

def nazwa_trasy(id_):
    return f"_stoj_tu_{id_ or 'domyslna'}"


def uruchom_skrypt(nazwa, id_, env_dod=None, kat=KAT):
    """Domyślny wykonawca skryptów powłoki (uruchom.sh / zatrzymaj.sh) -> kod wyjścia. W testach podmieniany."""
    env = dict(os.environ)
    if id_:
        env["RETRONIC_ID"] = id_
    env.update(env_dod or {})
    r = subprocess.run(["bash", str(Path(kat) / nazwa)], env=env, cwd=str(kat), stdin=subprocess.DEVNULL,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=300)
    print(r.stdout.strip())
    return r.returncode


def wlacz_pelny(id_, katalog, bez_restartu=False, zapytaj=None, bot=None, uruchom=None, kat=KAT, log=print):
    """`stoj.sh <id> on`. -> kod wyjścia (0 = włączone). Wszystkie zależności wstrzykiwalne (testy bez gry).
    bot() -> (jest_bot, tryb_mozgu); uruchom(skrypt, env_dod) -> kod wyjścia; zapytaj: klient gniazda strażnika."""
    katalog = Path(katalog)
    zapytaj = zapytaj or zapytaj_gniazdo(id_)
    bot = bot or (lambda: tryb_bota(id_))
    uruchom = uruchom or (lambda skrypt, env_dod=None: uruchom_skrypt(skrypt, id_, env_dod, kat))
    jest, tryb = bot()
    if wlaczony(katalog):
        if jest:
            log(f"STÓJ: już włączony ({id_}); {opis(katalog)}")
            return 0
        log(f"STÓJ: flaga bez działającego bota ({id_}): zaczynam od nowa")
        wylacz(katalog)
    nick = nick_z_profilu(katalog)
    # bot z modelem chodzi: sama flaga (na gorąco)
    if jest and (tryb != "skrypt" or bez_restartu):
        poz = pozycja_gorace(zapytaj, nick)
        d = {"start": "goracy", "mozg": tryb or "?", "od": round(time.time())}
        if poz:
            d["pole"] = list(poz)
        zapisz_dane(d, katalog)
        log(f"STÓJ: włączam na gorąco ({id_}), pole {poz or 'zapamięta bot'}"
            + ("" if tryb != "skrypt" else "; tryb skrypt: bot NIE odpisuje na czacie (--bez-restartu)"))
        return 0
    # świeży start albo restart w hybrydzie: potrzebna pozycja i poziom z gry
    try:
        o = odczytaj_postac(zapytaj, nick)
    except RuntimeError as e:
        log(f"STÓJ: nie włączam: {e}. Postać musi być zalogowana w grze.")
        return 3
    nowe, run = pokretla_stoj(o["level"], o["ml"], kat)
    poprzednie = zastosuj_pokretla(katalog / "na_zywo.json", nowe, log)
    trasa = nazwa_trasy(id_)
    (Path(kat) / "trasy").mkdir(exist_ok=True)
    (Path(kat) / "trasy" / f"{trasa}.json").write_text(json.dumps([list(o["pole"])]))
    d = {"pole": list(o["pole"]), "od": round(time.time()), "start": "restart" if jest else "swiezy",
         "mozg_przed": tryb if jest else None, "poprzednie": poprzednie, "ustawione": nowe, "runy": run}
    zapisz_dane(d, katalog)
    if jest:
        log(f"STÓJ: bot chodzi w trybie {tryb} (bez modelu): restart w hybrydzie na polu {o['pole']}")
        uruchom("zatrzymaj.sh")
    kod = uruchom("uruchom.sh", {"STOJ_TU": trasa, "MOZG_TRYB": MOZG_STOJ, "STOJ_PROG_HP": str(PROG_HP)})
    if kod != 0:
        log(f"STÓJ: start bota nie powiódł się (kod {kod}); cofam flagę i pokrętła")
        cofnij_pokretla(katalog / "na_zywo.json", poprzednie, nowe, log)
        wylacz(katalog)
        return 1
    log(f"STÓJ: włączony ({id_}): bot stoi na polu {o['pole']}, runy {run.upper() if run == 'uh' else 'HMM'}, mózg {MOZG_STOJ} (odpisuje na czacie)")
    return 0


def wylacz_pelny(id_, katalog, bot=None, uruchom=None, kat=KAT, log=print):
    """`stoj.sh <id> off`. Na gorąco: zdjęcie flagi. Po restarcie: powrót do ostatniej mapy/trybu. Po starcie świeżym: stop + STOP_RECZNY."""
    katalog = Path(katalog)
    bot = bot or (lambda: tryb_bota(id_))
    uruchom = uruchom or (lambda skrypt, env_dod=None: uruchom_skrypt(skrypt, id_, env_dod, kat))
    if not wlaczony(katalog):
        log(f"STÓJ: już wyłączony ({id_})")
        return 0
    d = dane(katalog)
    start = d.get("start")
    if start not in ("restart", "swiezy"):
        wylacz(katalog)
        log(f"STÓJ: wyłączam ({id_}): bot wraca do zwykłej pracy od najbliższego punktu trasy")
        return 0
    jest, _ = bot()
    if jest:
        uruchom("zatrzymaj.sh")                 # flaga jeszcze stoi: bot nie rusza przed zatrzymaniem
    wylacz(katalog)
    cofnij_pokretla(katalog / "na_zywo.json", d.get("poprzednie"), d.get("ustawione"), log)
    ostatni = Path(kat) / f"ostatni_start{'.' + id_ if id_ else ''}.env"
    if start == "restart" and ostatni.exists():
        kod = uruchom("uruchom.sh", {"MOZG_TRYB": d.get("mozg_przed") or "skrypt"})
        log(f"STÓJ: wyłączony ({id_}): bot wrócił do ostatniej mapy i trybu (mózg {d.get('mozg_przed') or 'skrypt'})"
            + ("" if kod == 0 else f"; UWAGA: start nie powiódł się (kod {kod})"))
        return 0 if kod == 0 else 1
    # start świeży (bot nie chodził przed STÓJ) albo brak ostatniej mapy: zostaje zatrzymany, Karol znów gra
    if not jest:
        try:
            (Path(katalog) / "STOP_RECZNY").touch()
        except OSError:
            pass
    log(f"STÓJ: wyłączony ({id_}): bot zatrzymany, STOP_RECZNY ustawiony (Karol gra)")
    return 0


def main(argv):
    arg = [a for a in argv if not a.startswith("--")]
    opcje = [a for a in argv if a.startswith("--")]
    if len(arg) != 2 or arg[1] not in ("on", "off", "stan") or any(o != "--bez-restartu" for o in opcje) \
            or (opcje and arg[1] != "on"):
        print("użycie: stoj.sh <id> on [--bez-restartu] | off | stan", file=sys.stderr)
        return 2
    import instancja  # noqa: PLC0415
    try:
        katalog = instancja.sciezki(arg[0], instancja.runtime("/tmp")).stan
    except Exception as e:  # noqa: BLE001
        print(f"zły identyfikator instancji: {e}", file=sys.stderr)
        return 2
    if not Path(katalog).is_dir():
        print(f"brak instancji {arg[0]!r} ({katalog})", file=sys.stderr)
        return 2
    if arg[1] == "on":
        return wlacz_pelny(arg[0], katalog, bez_restartu=bool(opcje))
    if arg[1] == "off":
        return wylacz_pelny(arg[0], katalog)
    print(opis(katalog))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
