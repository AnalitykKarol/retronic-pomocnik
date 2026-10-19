"""Testy pet.py na danych zmyślonych (bez gry)."""
import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import pet

def st(nazwa, id_, x, y, z=9, hp=100, gracz=False, atak=False):
    return {"nazwa": nazwa, "id": id_, "x": x, "y": y, "z": z, "hp": hp, "gracz": gracz, "atakowany": atak}

gracz = st("Jointoramix", 1, 100, 100, gracz=True)
przed = {2, 3}
# nowy Elf Scout obok gracza -> wykryty
assert pet.wykryj_peta([gracz, st("Elf Scout", 4, 101, 100)], przed) == 4
# stary Elf Scout (id przed czarem) -> pomijany
assert pet.wykryj_peta([gracz, st("Elf Scout", 2, 101, 100)], przed) is None
# nowy Elf Scout daleko -> pomijany
assert pet.wykryj_peta([gracz, st("Elf Scout", 5, 110, 100)], przed) is None
# inne piętro -> pomijany
assert pet.wykryj_peta([gracz, st("Elf Scout", 6, 100, 100, z=8)], przed) is None
# inny potwór -> pomijany
assert pet.wykryj_peta([gracz, st("Goblin", 7, 100, 100)], przed) is None
# brak gracza w liście -> None
assert pet.wykryj_peta([st("Elf Scout", 8, 100, 100)], przed) is None

# stan peta
assert pet.stan_peta([gracz, st("Elf Scout", 4, 101, 100, hp=70)], 4)["hp"] == 70
assert pet.stan_peta([gracz], 4) is None

# statystyki: przywołanie, próbki, zgon po PROBKI_BRAK_DO_SMIERCI brakach
with tempfile.TemporaryDirectory() as d:
    czas = [1000.0]
    s = pet.Statystyki(d, teraz=lambda: czas[0])
    s.przywolanie(4, {"x": 100, "y": 100, "z": 9})
    czas[0] += 5
    s.probka([gracz, st("Elf Scout", 4, 101, 100, hp=90)], {"hp": 200})
    assert s.pet_id == 4 and s.zgony == 0
    for _ in range(pet.PROBKI_BRAK_DO_SMIERCI):    # brak na liście = nieobecny, jeszcze nie zgon (zasięg listy)
        czas[0] += 5
        s.probka([gracz], {"hp": 200})
    assert s.zgony == 0 and s.pet_id == 4 and s.nieobecny
    s.probka([gracz, st("Elf Scout", 4, 101, 100, hp=60)], {"hp": 200})   # wrócił na listę
    assert s.pet_id == 4 and s.zgony == 0 and not s.nieobecny
    while czas[0] - s.t_widziany < pet.ZGON_BRAK_S + 5:              # dopiero po ZGON_BRAK_S bez niego = zgon
        czas[0] += 5
        s.probka([gracz], {"hp": 200})
    assert s.zgony == 1 and s.pet_id is None
    linie = [__import__("json").loads(l)["zdarzenie"] for l in open(s.plik, encoding="utf-8")]
    assert linie == ["przywolany", "probka", "nieobecny", "wrocil", "probka", "zniknal"] or \
        linie[:4] == ["przywolany", "probka", "nieobecny", "wrocil"] and linie[-1] == "zniknal", linie
print("test_pet: OK")
