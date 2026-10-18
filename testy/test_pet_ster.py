"""Testy pet_ster.py i integracji z Cavebotem na danych zmyślonych (bez gry, bez wpisywania na czacie)."""
import json, os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import pet, pet_ster, pokretla

def st(nazwa, id_, x, y, z=9, hp=100, gracz=False, atak=False):
    return {"nazwa": nazwa, "id": id_, "x": x, "y": y, "z": z, "hp": hp, "gracz": gracz, "atakowany": atak}

JA = st("Jointoramix", 1, 100, 100, gracz=True)
G = {"hp": 200, "max_hp": 200, "mana": 400, "exp": 70000}
KONF = dict(pietro_spotu=0, stabilne_s=45.0, zmiany_max=2, zmiany_okno_s=600.0, zgony_max=5)

class Zegar:
    def __init__(self): self.t = 1000.0
    def __call__(self): return self.t

def nowy(d):
    z = Zegar()
    p = pet_ster.PetSterowanie(d, teraz_scienny=z, log=lambda t: None)
    return p, z

def powod(p, z, mana=400, walka=False, wlaczony=True, poz=(100, 100, 9), **kw):
    k = {**KONF, **kw}
    return p.powod_blokady(wlaczony, mana, 360, walka, z.t, poz, **k)

def tick(p, z, lista, g=G, poz=(100, 100, 9), cel_id=None, dt=1.0):
    z.t += dt
    p.obserwuj(lista, g, poz, z.t, cel_id=cel_id)

with tempfile.TemporaryDirectory() as d:
    # --- warunek przywołania ---
    p, z = nowy(d)
    tick(p, z, [JA])
    assert powod(p, z) == "pietro_niestabilne"           # dopiero co zaczęliśmy obserwację piętra
    z.t += 50; tick(p, z, [JA])
    assert powod(p, z) is None                           # mana 400, spokój, piętro stabilne
    assert powod(p, z, wlaczony=False) == "wylaczony"    # pokrętło 0
    assert powod(p, z, mana=359) == "mana"
    assert powod(p, z, mana=360) is None
    assert powod(p, z, mana=None) == "mana"
    assert powod(p, z, walka=True) == "walka"
    assert powod(p, z, pietro_spotu=9) is None and powod(p, z, pietro_spotu=8) == "inne_pietro"
    assert not os.listdir(d), "plik jsonl nie powstaje bez zdarzeń"

    # --- przywołanie, wykrycie peta, wykluczenie z celów ---
    p.rzucono([JA, st("Goblin", 5, 105, 100)], 400, z.t, 30.0, 'utevo res "Elf Scout"')
    assert powod(p, z) == "czeka_na_detekcje"
    pet_s = st("Elf Scout", 7, 101, 100)
    tick(p, z, [JA, st("Goblin", 5, 105, 100), pet_s], g={**G, "mana": 40})
    assert p.pet_id == 7 and p.id_przed is None
    lista = [JA, st("Goblin", 5, 105, 100), pet_s]
    assert [s["id"] for s in p.bez_peta(lista)] == [1, 5]      # pet poza listą celów
    assert powod(p, z) == "jest_pet"

    # kandydaci() w Cavebocie nie zwraca peta ani w gołej liście
    import cavebot
    cb = cavebot.Cavebot.__new__(cavebot.Cavebot)
    cb.pet, cb.potwory, cb.zegar = p, None, lambda: 0.0
    cb.ignorowane, cb.nieosiagalne = {}, {}
    cb.pole_zmiany_pietra = lambda pole: False
    cb.ignorowany = lambda s, poz, t: False
    kand = cavebot.Cavebot.kandydaci(cb, lista, (100, 100, 9))
    assert [s["id"] for s in kand] == [5], kand

    # --- zabicie obok peta: goblin zniknął przy pecie po tym, jak stali obok siebie ---
    tick(p, z, [JA, st("Goblin", 5, 102, 100, hp=10), pet_s], cel_id=5)
    tick(p, z, [JA, pet_s], cel_id=5)
    assert p.stat.zabicia_obok_peta == 1 and p.zabicia_wlasne == 1
    # goblin daleko od peta znika: nie liczy się
    tick(p, z, [JA, st("Goblin", 6, 110, 100), pet_s])
    tick(p, z, [JA, pet_s])
    assert p.stat.zabicia_obok_peta == 1
    # pet stał obok >5 s temu: nie liczy się
    tick(p, z, [JA, st("Goblin", 8, 102, 100), pet_s])
    tick(p, z, [JA, st("Goblin", 8, 110, 100), pet_s], dt=6)
    tick(p, z, [JA, pet_s])
    assert p.stat.zabicia_obok_peta == 1

    # --- komunikaty serwera trafiają do pliku ---
    assert p.wiadomosc({"tekst": "You have summoned an Elf Scout.", "kanal": "Server Log", "autor": "", "nr": 1}, "Elf Scout")
    assert not p.wiadomosc({"tekst": "You have summoned an Elf Scout.", "kanal": "Server Log", "autor": "", "nr": 1}, "Elf Scout")
    assert not p.wiadomosc({"tekst": "hej co tam", "kanal": "Default", "autor": "x", "nr": 2}, "Elf Scout")

    # --- zgon peta po PROBKI_BRAK_DO_SMIERCI próbkach bez niego ---
    zginal = False
    for _ in range(int(pet.ZGON_BRAK_S / pet_ster.PROBKA_CO_S) + 3):   # zgon dopiero po ZGON_BRAK_S
        tick(p, z, [JA], dt=pet_ster.PROBKA_CO_S)
        zginal = zginal or p.pet_id is None
    assert p.pet_id is None and p.stat.zgony == 1
    p.przerwa_do = float("-inf")
    assert powod(p, z) is None                            # po zgonie na tym samym piętrze: znów można (mana wystarcza)
    assert powod(p, z, mana=100) == "mana"

    # --- drugie przywołanie, potem zmiana piętra: pet przepada ---
    p.rzucono([JA], 400, z.t, 30.0, "x")
    tick(p, z, [JA, st("Elf Scout", 9, 100, 101)])
    assert p.pet_id == 9 and p.stat.przywolania == 2
    z.t += 100
    tick(p, z, [JA], poz=(100, 100, 8))                   # zeszliśmy/weszliśmy piętro wyżej
    assert p.pet_id is None and p.zgony_pietro == 1
    assert p.stat.zgony == 1                              # utrata przez piętro to nie zgon peta
    p.przerwa_do = float("-inf")
    assert powod(p, z, poz=(100, 100, 8)) == "pietro_niestabilne"   # nowe piętro: najpierw musi się ustabilizować
    z.t += 50
    tick(p, z, [JA], poz=(100, 100, 8))
    assert powod(p, z, poz=(100, 100, 8)) is None         # ponowne przywołanie na nowym piętrze
    # seria zmian pięter = spot wielopiętrowy: bez przywoływania
    z.t += 50; tick(p, z, [JA], poz=(100, 100, 9))
    z.t += 50; tick(p, z, [JA], poz=(100, 100, 8))
    z.t += 100; tick(p, z, [JA], poz=(100, 100, 8))
    assert powod(p, z, poz=(100, 100, 8)) == "wiele_pieter"
    z.t += 700; tick(p, z, [JA], poz=(100, 100, 8))
    assert powod(p, z, poz=(100, 100, 8)) is None         # okno minęło

    # --- porażka: czar bez peta obok ---
    p2, z2 = nowy(d)
    tick(p2, z2, [JA]); z2.t += 60; tick(p2, z2, [JA])
    for i in range(2):
        p2.rzucono([JA], 400, z2.t, 0.0, "x")
        tick(p2, z2, [JA], dt=pet_ster.OKNO_DETEKCJI_S + 1)
    assert powod(p2, z2) == "porazki"
    # nowy tej samej nazwy daleko / inna nazwa nie jest petem
    p3, z3 = nowy(d)
    p3.rzucono([JA], 400, z3.t, 0.0, "x")
    tick(p3, z3, [JA, st("Elf Scout", 4, 120, 100), st("Goblin", 5, 101, 100)])
    assert p3.pet_id is None and p3.id_przed is not None
    # limit zgonów
    p4, z4 = nowy(d); tick(p4, z4, [JA]); z4.t += 60; tick(p4, z4, [JA])
    p4.stat.zgony = 5
    assert powod(p4, z4) == "limit_zgonow" and powod(p4, z4, zgony_max=0) is None

    # --- plik jsonl ma wszystkie typy zdarzeń ---
    zd = set()
    for f in os.listdir(d):
        for l in open(os.path.join(d, f), encoding="utf-8"):
            zd.add(json.loads(l)["zdarzenie"])
    assert {"czar", "przywolany", "probka", "zabicie_obok_peta", "komunikat", "zniknal", "zmiana_pietra",
            "brak_peta_po_czarze"} <= zd, zd
    pr = [json.loads(l) for f in os.listdir(d) for l in open(os.path.join(d, f)) if '"probka"' in l]
    assert "exp" in pr[0]["gracz"] and "hp" in pr[0]["pet"]


# --- Cavebot._pet: wpisuje czar z cudzysłowem tylko w spokoju (atrapa bez gry) ---
class Atrapa(cavebot.Cavebot):
    def __init__(self, d):
        self.zegar_t = 5000.0
        self.pet = pet_ster.PetSterowanie(d, teraz_scienny=lambda: 1.0, log=lambda t: None)
        self.stwory_surowe = []
        self.cel, self.w_poscigu, self.pamiec, self.stan = None, False, None, "TRASA"
        self.czar_ostatni = float("-inf")
        self.zd_oczekuje = self.jc_oczekuje = None
        self.wyslane, self.rejestr = [], []
        self.wypad_wyslij = self.wyslane.append
        self.aktywnosc_ts = 0
        self.potwory = None
    def _ml_blokada(self, lista, poz): return getattr(self, "blokada", None)
    def zywy_w_poblizu(self, lista, poz): return getattr(self, "mob", None)
    def _poscig_puszcz(self): pass
    def ustaw_stan(self, stan, szczegol=""): self.stan = stan
    def _wypad_zarejestruj_tekst(self, t): self.rejestr.append(t)
    def pauza(self, a=0, b=0): pass

with tempfile.TemporaryDirectory() as d:
    cb = Atrapa(d)
    cavebot.PET_WLACZONY = 0
    cb.pet.obserwuj([JA], G, (100, 100, 9), 5000.0)
    assert cb._pet_tick(G, (100, 100, 9), [JA], 5100.0) is False and not cb.wyslane      # pokrętło 0
    cavebot.PET_WLACZONY = 1
    try:
        cb.pet.obserwuj([JA], G, (100, 100, 9), 5100.0)
        cb.stwory_surowe = [JA]
        cb.mob = st("Goblin", 5, 103, 100)
        assert cb._pet_tick(G, (100, 100, 9), [JA], 5100.0) is False and not cb.wyslane  # mob blisko = walka
        cb.mob, cb.blokada = None, "ucieczka"
        assert cb._pet_tick(G, (100, 100, 9), [JA], 5100.0) is False and not cb.wyslane
        cb.blokada = None
        assert cb._pet_tick({**G, "mana": 300}, (100, 100, 9), [JA], 5100.0) is False and not cb.wyslane  # za mało many
        assert cb._pet_tick(G, (100, 100, 9), [JA], 5100.0) is True
        assert cb.wyslane == ['utevo res "Elf Scout"'] == cb.rejestr, cb.wyslane
        assert cb._pet_tick(G, (100, 100, 9), [JA], 5101.0) is False and len(cb.wyslane) == 1   # czeka na peta
        import mozg
        t = mozg.oczysc_wiadomosc(cb.wyslane[0])
        assert mozg.bezpieczna_wiadomosc(t)[0], t
    finally:
        cavebot.PET_WLACZONY = 0
    # stwory() zwraca listę bez peta
    cb.pet.pet_id = 7
    cb.zapytaj = lambda z: {"stwory": [JA, st("Elf Scout", 7, 101, 100), st("Goblin", 5, 105, 100)]}
    assert [s["id"] for s in cb.stwory()] == [1, 5] and len(cb.stwory_surowe) == 3

# --- pokrętła ---
ok, bl = pokretla.waliduj({"PET_WLACZONY": 1, "PET_MANA_MIN": 380, "PET_NAZWA": "Scarab", "PET_PIETRO": 9})
assert not bl and len(ok) == 4, (ok, bl)
ok, bl = pokretla.waliduj({"PET_MANA_MIN": 50, "PET_NAZWA": "Dragon", "PET_PIETRO": 99})
assert len(bl) == 3, bl
# analityk (z domyślnymi): nie włączy, nie obniży progu many
dom = {"PET_WLACZONY": 0, "PET_MANA_MIN": 360}
ok, bl = pokretla.waliduj({"PET_WLACZONY": 1, "PET_MANA_MIN": 300}, dom)
assert not ok and len(bl) == 2, (ok, bl)
for k in [k for k in pokretla.ZAKRESY if k.startswith("PET_")] + ["PET_NAZWA"]:
    assert hasattr(cavebot, k), k
assert cavebot.PET_WLACZONY == 0
przyklad = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "na_zywo.przyklad.json")))
ok, bl = pokretla.waliduj({k: v for k, v in przyklad.items() if k.startswith("PET_")})
assert not bl and len(ok) == 11, (ok, bl)
print("test_pet_ster: OK")
