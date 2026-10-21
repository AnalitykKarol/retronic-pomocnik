#!/usr/bin/env python3
"""21.10 (K1, spec dane_tibia/SPEC_logowanie_wylogowanie_1021.md): zaloguj / wyloguj / stan-ekranu. Offline: bez gry, X11 i sesji.

Zrzuty z dysku (testy/dane/logowanie/: Character List x2, Enter Game z zamazanymi polami konta i hasła, ciemna gra) oraz atrapa Portu
(zrzut, klik, Ctrl+L, rdzeń, zegar). Czego dowodzi:
  (A) rozpoznanie ekranów: 4 zrzuty z dysku + warianty (inny rozmiar, czarny ekran) oraz wszystkie zrzuty slepoty z instancje/ (gdy są);
  (B) zaloguj: z Enter Game dokładnie 2 kliki (Login, Ok) w dobrych punktach, zero klawiszy; z Character List 1 klik; KLIK NIGDY NIE IDZIE
      przy ekranie gra, nieznanym, zgonie, ani gdy ekran zmienił się między decyzją a naciśnięciem; odmowy (brak sesji, STOP_RECZNY, zła postać);
  (C) wyloguj: odmawia przy potworze obok / bije_nas / spadającym HP / zgonie / bocie poza miastem / STOP_RECZNY; czeka do spokoju; Ctrl+L tylko
      na ekranie gra; `zamknij` zaraz po liście postaci;
  (D) zgon: dane kutangena 20.10 21:01 (HP 0, własny wpis znika) = zgon; pojedyncze zero = nie;
  (E) szablony odtwarzalne z zrzutów, skrypty .sh, kody wyjścia CLI."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import glob
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
KORZEN = Path(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
sys.path.insert(0, str(KORZEN))
from PIL import Image  # noqa: E402
import logowanie as L  # noqa: E402

DANE = KORZEN / "testy" / "dane" / "logowanie"
ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + (f"  [{info}]" if info and not warunek else ""))


def obraz(nazwa):
    return Image.open(DANE / nazwa).convert("RGB")


IM = {
    "character_list": obraz("character_list_dawajkesh.png"),
    "enter_game": obraz("enter_game_pola_zamazane.png"),
    "gra": obraz("gra_ciemna_kolanoth.png"),
    "czarny": Image.new("RGB", (1175, 910), (0, 0, 0)),
}

# ------------------------------------------------------------------------------------------------ (A) rozpoznanie
for nazwa, plik in (("character_list", "character_list_dawajkesh.png"), ("character_list", "character_list_kutangen.png"),
                    ("enter_game", "enter_game_pola_zamazane.png"), ("gra", "gra_ciemna_kolanoth.png")):
    e, sz = L.klasyfikuj(obraz(plik))
    sprawdz(f"A1 {plik} -> {nazwa}", e == nazwa, f"{e} {sz}")
cl = L.klasyfikuj(IM["character_list"])[1]
eg = L.klasyfikuj(IM["enter_game"])[1]
sprawdz("A2 marginesy: Character List własne >= 0,97 i o >= 0,40 nad Enter Game; odwrotnie dla Enter Game",
        cl["character_list"] >= 0.97 and cl["character_list"] - cl["enter_game"] >= 0.4
        and eg["enter_game"] >= 0.97 and eg["enter_game"] - eg["character_list"] >= 0.4, f"{cl} {eg}")
e, _ = L.klasyfikuj(IM["character_list"].resize((600, 465)))
sprawdz("A3 okno logowania w innym rozmiarze (600x465) = nieznany (żadnego kliku)", e == "nieznany", e)
e, _ = L.klasyfikuj(Image.new("RGB", (1175, 910), (0, 0, 0)))
sprawdz("A4 czarny ekran = nieznany", e == "nieznany", e)
okno_bledu = IM["enter_game"].copy()
okno_bledu.paste((25, 26, 24), (440, 280, 740, 330))        # ciemne okno błędu nad tytułem Enter Game: to samo tło, różni się tylko tekst
from PIL import ImageDraw  # noqa: E402
ImageDraw.Draw(okno_bledu).text((540, 291), "Connection error", fill=(200, 200, 200))
e, _ = L.klasyfikuj(okno_bledu)
sprawdz("A5 Enter Game z zasłoniętym tytułem (okno błędu) = nieznany, nie enter_game", e == "nieznany", e)
zrzuty = sorted(glob.glob(str(KORZEN / "instancje" / "*" / "logi" / "slepota" / "*.png"))
                + glob.glob(str(KORZEN / "instancje" / "_archiwum" / "*" / "logi" / "slepota" / "*.png")))
wyn = [L.klasyfikuj(Image.open(p).convert("RGB"))[0] for p in zrzuty]
print(f"INFO A6 zrzuty slepoty z instancje/: {len(zrzuty)} -> " + ", ".join(f"{k}={wyn.count(k)}" for k in sorted(set(wyn))))
sprawdz("A6 zrzuty slepoty z dysku: żaden nie jest nieznany (logowanie) ani zgon", "nieznany" not in wyn and "zgon" not in wyn, wyn)


# ------------------------------------------------------------------------------------------------ atrapa Portu
class Atrapa(L.Port):
    """Świat: ekran (enter_game | character_list | gra), zegar sztuczny. Login na enter_game -> character_list, Ok -> gra,
    Ctrl+L na gra -> character_list po `ctrl_l_do_skutku` naciśnięciach (reszta: nic, jak logout block)."""

    def __init__(self, ekran="enter_game", sesja=True, reczny=False, bot=False, miasto=None, nick="Kutangen", ctrl_l_do_skutku=1,
                 rozmiar_obrazu=None):
        self.id = "test"
        self.ekran, self.sesja, self.reczny, self.bot, self.miasto, self.nick_ = ekran, sesja, reczny, bot, miasto, nick
        self.t = 1000.0
        self.kliki, self.ctrl_ly, self.zamkniecia, self.zrzuty = [], [], [], 0
        self.ekran_przy_klikach = []
        self.przed_naciskaniem = None          # funkcja wołana między ruchem kursora a potwierdzeniem (zmiana ekranu w locie)
        self.hp = 150
        self.hp_lista = None                   # opcjonalnie sekwencja HP (po jednym odczycie)
        self.w_grze_nick = nick
        self.nicki = [] if nick is None else ["Kutangen"]
        self.stwory_f = lambda: self.domyslne_stwory()
        self.ctrl_l_do_skutku = ctrl_l_do_skutku
        self.zamknij_kod = 0
        self.log_nowy = None
        self.czarny_zrzuty = 0

    # świat
    def domyslne_stwory(self):
        return [{"id": 1, "nazwa": "Kutangen", "gracz": True, "x": 100, "y": 100, "z": 7, "hp": 100, "bije_nas": False, "atakowany": False}]

    def sesja_zyje(self): return self.sesja
    def zrzut(self):
        self.zrzuty += 1
        if self.ekran == "czarny":             # przejście po Ctrl+L: kilka zrzutów nieznanych, potem lista postaci
            self.czarny_zrzuty -= 1
            if self.czarny_zrzuty <= 0:
                self.ekran = "character_list"
        return IM[self.ekran]

    def klik(self, x, y, potwierdz):
        if self.przed_naciskaniem:
            self.przed_naciskaniem(self)
        czy = potwierdz()
        self.ekran_przy_klikach.append(self.ekran)
        if not czy:
            return False
        self.kliki.append((self.ekran, x, y))
        if self.ekran == "enter_game" and abs(x - 588) <= 4 and abs(y - 594) <= 4:
            self.ekran = "character_list"
        elif self.ekran == "character_list" and abs(x - 641) <= 4 and abs(y - 628) <= 4:
            self.ekran = "gra"
            self.nicki = self.nicki + ([self.w_grze_nick] if self.w_grze_nick else [])
        return True

    def ctrl_l(self):
        self.ctrl_ly.append(self.ekran)
        if self.ekran == "gra" and len(self.ctrl_ly) >= self.ctrl_l_do_skutku:
            self.ekran = "character_list"

    def gracz(self):
        if self.hp_lista:
            hp = self.hp_lista.pop(0) if len(self.hp_lista) > 1 else self.hp_lista[0]
        else:
            hp = self.hp
        return {"hp": hp, "max_hp": 190}

    def stwory(self): return self.stwory_f()
    def nick(self): return self.nick_
    def nicki_z_logu(self): return list(self.nicki)
    def bot_dziala(self): return self.bot
    def w_miescie(self): return self.miasto
    def stop_reczny(self): return self.reczny

    def zamknij_sesje(self):
        self.zamkniecia.append(self.ekran)
        if self.zamknij_kod == 0:
            self.sesja = False
        return self.zamknij_kod, "gra zamknięta"

    def teraz(self): return self.t
    def spij(self, s): self.t += s


def dz_tmp():
    d = tempfile.mkdtemp(prefix="logowanie-test-")
    return L.Dziennik(d, "test", "test", wypisz=False), Path(d)


# ------------------------------------------------------------------------------------------------ (B) zaloguj
p = Atrapa("enter_game")
dz, kat = dz_tmp()
kod = L.zaloguj(p, dz, limit_s=60)
sprawdz("B1 z Enter Game: kod 0, dokładnie 2 kliki: Login potem Ok, w dobrych punktach (+-2 px)",
        kod == 0 and [k[0] for k in p.kliki] == ["enter_game", "character_list"], f"kod {kod} kliki {p.kliki}")
sprawdz("B1b współrzędne", len(p.kliki) == 2 and p.kliki[0][1:] == L.PRZYCISK_LOGIN and p.kliki[1][1:] == L.PRZYCISK_OK, p.kliki)
sprawdz("B1c atrapa Portu nie ma metody klawiszy w zaloguj: Ctrl+L nigdy nie wysłane", p.ctrl_ly == [])
zd = [json.loads(w) for w in (kat / "logowanie.jsonl").read_text().splitlines()]
sprawdz("B1d jsonl: zdarzenia klik z ekranem tuż przed kliknięciem, w_grze z nickiem",
        [z["ekran_przed_klikiem"] for z in zd if z["zdarzenie"] == "klik"] == ["enter_game", "character_list"]
        and any(z["zdarzenie"] == "w_grze" and z["zalogowany"] == "Kutangen" for z in zd), zd[-3:])
sprawdz("B1e log tekstowy istnieje i opisuje oba kliki", "klik Login" in (kat / "logowanie.log").read_text()
        and "klik Ok" in (kat / "logowanie.log").read_text())

p = Atrapa("character_list")
kod = L.zaloguj(p, dz_tmp()[0], limit_s=60)
sprawdz("B2 z Character List: 1 klik (Ok), kod 0", kod == 0 and [k[0] for k in p.kliki] == ["character_list"], f"{kod} {p.kliki}")

p = Atrapa("gra")
kod = L.zaloguj(p, dz_tmp()[0], limit_s=60)
sprawdz("B3 KLIK NIGDY NIE IDZIE, gdy ekran = gra: kod 0 (już w grze), zero kliknięć", kod == 0 and p.kliki == [] and p.ekran_przy_klikach == [])

p = Atrapa("enter_game")
p.przed_naciskaniem = lambda a: setattr(a, "ekran", "gra")     # Karol zalogował w międzyczasie: ekran = gra tuż przed naciśnięciem
kod = L.zaloguj(p, dz_tmp()[0], limit_s=10)
sprawdz("B4 ekran zmienił się na grę między decyzją a naciśnięciem (incydent 07:33): klik odwołany, zero kliknięć", p.kliki == [] and p.ekran_przy_klikach[:1] == ["gra"], f"kod {kod} {p.kliki} {p.ekran_przy_klikach}")
sprawdz("B4b ...a po zmianie ekranu proces kończy się kodem 0 (klient już w grze)", kod == 0, kod)

p = Atrapa("enter_game")
p.przed_naciskaniem = lambda a: setattr(a, "ekran", "character_list")   # w międzyczasie lista postaci: Login NIE może pójść
kod = L.zaloguj(p, dz_tmp()[0], limit_s=1)
sprawdz("B5 ekran zmienił się na inne okno logowania tuż przed kliknięciem: Login nie pada na liście postaci", all(k[0] == "character_list" for k in p.kliki), p.kliki)

p = Atrapa("enter_game")
p.zrzut = lambda: Image.new("RGB", (1175, 910), (0, 0, 0))
kod = L.zaloguj(p, dz_tmp()[0], limit_s=5)
sprawdz("B6 ekran nieznany: zero kliknięć, kod 7", p.kliki == [] and kod == L.KOD_EKRAN, f"{kod} {p.kliki}")

p = Atrapa("character_list")
p.hp = 0
kod = L.zaloguj(p, dz_tmp()[0], limit_s=20)
sprawdz("B7 zgon (HP 0 w pamięci, lista postaci): zero kliknięć, kod 6", p.kliki == [] and kod == L.KOD_ZGON, f"{kod} {p.kliki}")

p = Atrapa("enter_game", sesja=False)
kod = L.zaloguj(p, dz_tmp()[0])
sprawdz("B8 brak sesji: kod 3, zero kliknięć", kod == L.KOD_BRAK_SESJI and p.kliki == [] and p.zrzuty == 0, kod)

p = Atrapa("enter_game", reczny=True)
kod = L.zaloguj(p, dz_tmp()[0])
sprawdz("B9 STOP_RECZNY bez bota (Karol gra): kod 4, zero kliknięć i zrzutów", kod == L.KOD_RECZNY and p.kliki == [] and p.zrzuty == 0, kod)
p = Atrapa("enter_game", reczny=True)
kod = L.zaloguj(p, dz_tmp()[0], reczny_ok=True)
sprawdz("B9b ... z --reczny-ok loguje", kod == 0 and len(p.kliki) == 2, f"{kod} {p.kliki}")

p = Atrapa("enter_game")
p.w_grze_nick = "Ktos Inny"
kod = L.zaloguj(p, dz_tmp()[0])
sprawdz("B10 w grze inna postać niż oczekiwana (nick z logu klienta): kod 9", kod == L.KOD_POSTAC, kod)

p = Atrapa("enter_game")
p.klik = lambda x, y, potwierdz: (p.kliki.append((p.ekran, x, y)), potwierdz(), True)[2]   # klik „nie działa”: ekran stoi
kod = L.zaloguj(p, dz_tmp()[0], limit_s=120)
sprawdz("B11 Login bez skutku: najwyżej 2 kliki, potem kod 1 (nie klika w kółko)", len(p.kliki) == L.MAX_KLIKOW and kod == L.KOD_BLAD, f"{kod} {len(p.kliki)}")

p = Atrapa("enter_game")
p.zrzut = lambda: (_ for _ in ()).throw(RuntimeError("grim wisi"))
kod = L.zaloguj(p, dz_tmp()[0], limit_s=5)
sprawdz("B12 brak zrzutu: zero kliknięć", p.kliki == [] and kod in (L.KOD_EKRAN, L.KOD_BLAD), kod)

# ------------------------------------------------------------------------------------------------ (C) wyloguj
p = Atrapa("gra", bot=False)
dz, kat = dz_tmp()
kod = L.wyloguj(p, dz, limit_s=60)
sprawdz("C1 spokój, bot zatrzymany: Ctrl+L tylko na ekranie gra, potem sesja_gry zamknij, kod 0",
        kod == 0 and p.ctrl_ly == ["gra"] and p.zamkniecia == ["character_list"], f"{kod} {p.ctrl_ly} {p.zamkniecia}")

p = Atrapa("gra", ctrl_l_do_skutku=4)
kod = L.wyloguj(p, dz_tmp()[0], limit_s=120)
sprawdz("C1b logout block przez 3 próby: Ctrl+L ponawiane co ~4 s, wszystkie tylko na ekranie gra",
        kod == 0 and len(p.ctrl_ly) == 4 and set(p.ctrl_ly) == {"gra"} and p.zamkniecia == ["character_list"], f"{kod} {p.ctrl_ly}")

p = Atrapa("gra")
p.stwory_f = lambda: p.domyslne_stwory() + [{"id": 2, "nazwa": "Troll", "gracz": False, "x": 101, "y": 101, "z": 7, "hp": 100, "bije_nas": False, "atakowany": False}]
kod = L.wyloguj(p, dz_tmp()[0], limit_s=300, czekaj_spokoj_s=10)
sprawdz("C2 WYLOGUJ ODMAWIA przy potworze obok (odległość 1): kod 5, zero Ctrl+L, sesja nie zamknięta",
        kod == L.KOD_WALKA and p.ctrl_ly == [] and p.zamkniecia == [], f"{kod} {p.ctrl_ly}")

p = Atrapa("gra")
p.stwory_f = lambda: p.domyslne_stwory() + [{"id": 2, "nazwa": "Troll", "gracz": False, "x": 130, "y": 100, "z": 7, "hp": 100, "bije_nas": True, "atakowany": False}]
kod = L.wyloguj(p, dz_tmp()[0], czekaj_spokoj_s=10)
sprawdz("C3 odmowa, gdy ktoś bije nas (nawet z daleka)", kod == L.KOD_WALKA and p.ctrl_ly == [], kod)

p = Atrapa("gra")
p.stwory_f = lambda: p.domyslne_stwory() + [{"id": 2, "nazwa": "Rat", "gracz": False, "x": 101, "y": 100, "z": 8, "hp": 100, "bije_nas": False, "atakowany": False}]
kod = L.wyloguj(p, dz_tmp()[0])
sprawdz("C4 potwór tuż obok, ale na innym piętrze (rdzeń trzyma stwory z całego widoku) = spokój", kod == 0 and p.ctrl_ly == ["gra"], f"{kod} {p.ctrl_ly}")

p = Atrapa("gra")
p.hp_lista = [150, 140, 130, 130, 130]
kod = L.wyloguj(p, dz_tmp()[0], czekaj_spokoj_s=1)
sprawdz("C5 HP spada = brak spokoju (kod 5 po limicie), potem po ustaniu spadku wylogowanie nie ma już czekania: Ctrl+L dopiero po spokoju",
        kod in (0, L.KOD_WALKA) and (kod == L.KOD_WALKA and p.ctrl_ly == [] or p.ctrl_ly == ["gra"]), f"{kod} {p.ctrl_ly}")

p = Atrapa("gra")
t_spokoj = {"n": 0}


def stwory_po_walce():
    t_spokoj["n"] += 1
    if t_spokoj["n"] <= 5:
        return p.domyslne_stwory() + [{"id": 2, "nazwa": "Troll", "gracz": False, "x": 100, "y": 101, "z": 7, "hp": 40, "bije_nas": True, "atakowany": True}]
    return p.domyslne_stwory()


p.stwory_f = stwory_po_walce
kod = L.wyloguj(p, dz_tmp()[0], limit_s=300, czekaj_spokoj_s=60)
sprawdz("C6 walka kończy się po ~5 odczytach: czeka (zero Ctrl+L w walce), potem wylogowuje", kod == 0 and p.ctrl_ly == ["gra"] and t_spokoj["n"] > 5, f"{kod} {p.ctrl_ly} {t_spokoj}")

p = Atrapa("gra", bot=True, miasto=None)
kod = L.wyloguj(p, dz_tmp()[0])
sprawdz("C7 bot działa poza miastem: kod 8, zero Ctrl+L", kod == L.KOD_BOT and p.ctrl_ly == [], kod)
p = Atrapa("gra", bot=True, miasto="thais")
kod = L.wyloguj(p, dz_tmp()[0])
sprawdz("C7b bot działa w mieście: wylogowanie dozwolone", kod == 0 and p.ctrl_ly == ["gra"], f"{kod} {p.ctrl_ly}")

p = Atrapa("gra", reczny=True)
kod = L.wyloguj(p, dz_tmp()[0])
sprawdz("C8 STOP_RECZNY bez bota: kod 4, zero Ctrl+L", kod == L.KOD_RECZNY and p.ctrl_ly == [], kod)

p = Atrapa("gra")
p.hp = 0
kod = L.wyloguj(p, dz_tmp()[0])
sprawdz("C9 zgon: kod 6, zero Ctrl+L", kod == L.KOD_ZGON and p.ctrl_ly == [], kod)

p = Atrapa("character_list")
kod = L.wyloguj(p, dz_tmp()[0])
sprawdz("C10 klient już na liście postaci (reset serwera): zero Ctrl+L, od razu zamknięcie sesji, kod 0", kod == 0 and p.ctrl_ly == [] and p.zamkniecia == ["character_list"], f"{kod} {p.ctrl_ly}")

p = Atrapa("gra")
p.zrzut = lambda: Image.new("RGB", (1175, 910), (0, 0, 0))
kod = L.wyloguj(p, dz_tmp()[0])
sprawdz("C11 ekran nieznany: zero klawiszy, kod 7", kod == L.KOD_EKRAN and p.ctrl_ly == [], kod)

p = Atrapa("gra", sesja=False)
kod = L.wyloguj(p, dz_tmp()[0])
sprawdz("C12 brak sesji = nic do zamknięcia, kod 0, zero klawiszy", kod == 0 and p.ctrl_ly == [] and p.zamkniecia == [], kod)

p = Atrapa("gra", ctrl_l_do_skutku=10 ** 6)
kod = L.wyloguj(p, dz_tmp()[0], limit_s=40)
sprawdz("C13 Ctrl+L nie skutkuje: limit czasu, kod 1, sesja NIE zamknięta (nie zamykamy klienta w grze)", kod == L.KOD_BLAD and p.zamkniecia == [], f"{kod} {len(p.ctrl_ly)}")

p = Atrapa("gra")
p.zamknij_kod = 1
kod = L.wyloguj(p, dz_tmp()[0])
sprawdz("C14 sesja_gry zamknij zwraca błąd: kod 1", kod == L.KOD_BLAD, kod)

p = Atrapa("gra")
p.stwory_f = lambda: [{"id": 9, "nazwa": "Ktos", "gracz": True, "x": 1, "y": 1, "z": 7, "hp": 100}]
kod = L.wyloguj(p, dz_tmp()[0], czekaj_spokoj_s=5)
sprawdz("C15 nie widzę własnej postaci na liście = brak spokoju (ostrożnie), zero Ctrl+L", kod == L.KOD_WALKA and p.ctrl_ly == [], kod)

p = Atrapa("gra", ctrl_l_do_skutku=1)
p.ctrl_l = lambda: (p.ctrl_ly.append(p.ekran), setattr(p, "ekran", "czarny"), setattr(p, "czarny_zrzuty", 8))[0]
kod = L.wyloguj(p, dz_tmp()[0], limit_s=60)
sprawdz("C16 po Ctrl+L klient przechodzi przez czarny ekran (nieznany): żadnego drugiego Ctrl+L w tym czasie, potem lista postaci i zamknięcie",
        kod == 0 and p.ctrl_ly == ["gra"] and p.zamkniecia == ["character_list"], f"{kod} {p.ctrl_ly} {p.zamkniecia}")

# ------------------------------------------------------------------------------------------------ (D) stan-ekranu i zgon
for ekran in ("gra", "enter_game", "character_list"):
    p = Atrapa(ekran)
    sprawdz(f"D1 stan-ekranu: {ekran}", L.stan_ekranu(p)[0] == ekran, L.stan_ekranu(p))
p = Atrapa("gra")
p.zrzut = lambda: Image.new("RGB", (1175, 910), (0, 0, 0))
sprawdz("D2 stan-ekranu: nieznany", L.stan_ekranu(p)[0] == "nieznany")
p = Atrapa("gra")
p.hp = 0
sprawdz("D3 stan-ekranu: zgon (HP 0 na ekranie gry)", L.stan_ekranu(p)[0] == "zgon")
p = Atrapa("character_list")
p.hp = 0
sprawdz("D3b stan-ekranu: zgon (HP 0 w zamrożonej pamięci na liście postaci)", L.stan_ekranu(p)[0] == "zgon")
p = Atrapa("enter_game")
p.hp = 0
sprawdz("D3c Enter Game z nieaktualnym HP 0 w pamięci: enter_game, nie zgon", L.stan_ekranu(p)[0] == "enter_game")
p = Atrapa("gra")
p.hp_lista = [0, 120]
sprawdz("D4 pojedynczy odczyt HP 0 (fałszywy) = gra", L.stan_ekranu(p)[0] == "gra")
p = Atrapa("gra")
p.gracz = lambda: (_ for _ in ()).throw(OSError("brak gniazda"))
sprawdz("D5 rdzeń niedostępny: stan z samego zrzutu (gra)", L.stan_ekranu(p)[0] == "gra")

tele = KORZEN / "instancje" / "kutangen" / "logi" / "telemetria-20261020.jsonl"
if tele.exists():
    import time as _t
    hp_seria = []
    for w in tele.read_text().splitlines():
        try:
            r = json.loads(w)
        except ValueError:
            continue
        if r.get("typ") == "probka" and "21:01:00" <= _t.strftime("%H:%M:%S", _t.localtime(r["t"])) <= "21:01:40":
            hp_seria.append((r["hp"], any(s.get("gracz") for s in r.get("stwory", []))))
    pierwszy0 = next((i for i, (h, _) in enumerate(hp_seria) if h == 0), None)
    p = Atrapa("gra")
    p.hp_lista = [h for h, _ in hp_seria[pierwszy0:]] if pierwszy0 is not None else [0]
    sprawdz(f"D6 dane z dysku (kutangen 20.10 21:01, {len(hp_seria)} próbek, pierwsze HP 0 na pozycji {pierwszy0}): zgon", L.stan_ekranu(p)[0] == "zgon")
    p = Atrapa("gra")
    p.hp_lista = [h for h, _ in hp_seria[:pierwszy0]][-3:] or [19]
    sprawdz("D6b ...a tuż przed zgonem (HP 4-19) = jeszcze gra", L.stan_ekranu(p)[0] == "gra", p.hp_lista)
else:
    print("INFO D6 brak telemetrii kutangena z 20.10 (zrotowana): test na danych z dysku pominięty")

# ------------------------------------------------------------------------------------------------ (E) szablony, skrypty, CLI
with tempfile.TemporaryDirectory() as t:
    wyjscie = Path(t) / "szablony.npz"
    L.zbuduj([str(DANE / "character_list_dawajkesh.png"), str(DANE / "character_list_kutangen.png")],
             [str(DANE / "enter_game_pola_zamazane.png")], wyjscie)
    import numpy as np
    a, b = np.load(wyjscie), np.load(L.PLIK_SZABLONOW)
    sprawdz("E1 szablony odtwarzalne z zrzutów testowych (zamazane pola nie zmieniają pasków)",
            sorted(a.files) == sorted(b.files) and all((a[k] == b[k]).all() for k in a.files), sorted(a.files))
sprawdz("E2 w paskach okien nie ma pól tekstowych konta/hasła (paski EG nie zachodzą na y 325-405)",
        all(y1 <= 325 or y0 >= 405 for (_, _, y0, y1) in L.OBSZARY["enter_game"]), L.OBSZARY["enter_game"])
for skrypt in ("zaloguj.sh", "wyloguj.sh"):
    s = KORZEN / skrypt
    sprawdz(f"E3 {skrypt}: wykonywalny i składnia bash OK", _os.access(s, _os.X_OK) and subprocess.run(["bash", "-n", str(s)]).returncode == 0)
env = {k: v for k, v in _os.environ.items() if k != "RETRONIC_ID"}
r = subprocess.run([sys.executable, "-I", str(KORZEN / "logowanie.py"), "zaloguj"], capture_output=True, text=True, env=env, timeout=30)
sprawdz("E4 CLI bez RETRONIC_ID: kod 2, bez dotykania gry", r.returncode == L.KOD_UZYCIE, (r.returncode, r.stdout[-200:]))
r = subprocess.run([sys.executable, "-I", str(KORZEN / "logowanie.py"), "stan-ekranu", "brak-sesji-x"], capture_output=True, text=True, env=env, timeout=30)
sprawdz("E5 CLI stan-ekranu bez sesji: słowo 'nieznany' i kod 3", r.stdout.strip() == "nieznany" and r.returncode == L.KOD_BRAK_SESJI, (r.returncode, r.stdout))
r = subprocess.run([sys.executable, "-I", str(KORZEN / "logowanie.py"), "zaloguj", "x", "--zla-opcja"], capture_output=True, text=True, env=env, timeout=30)
sprawdz("E6 CLI nieznana opcja: kod 2", r.returncode == L.KOD_UZYCIE, (r.returncode, r.stdout))
src = (KORZEN / "logowanie.py").read_text()
zal = src[src.index("def zaloguj("):src.index("def _nicki(")]
sprawdz("E7 w kodzie zaloguj nie ma wysyłania klawiszy (ctrl_l, Return, KeyPress)", not any(s in zal for s in ("ctrl_l", "Return", "KeyPress", "Enter\"")))

print(f"\nWYNIK: {sum(ok)} / {len(ok)}")
sys.exit(0 if all(ok) else 1)
