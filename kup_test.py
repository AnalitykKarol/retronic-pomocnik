"""Jednorazowy zakup u NPC stojącego obok (wspólny kod: wyprawa.kup_u_npc), weryfikacja w plecaku.
Użycie: python3 -I kup_test.py [N] [przedmiot] [limit_gp]   (domyślnie 3 ham 150; limit 0 = bez limitu)
Przykład: kup_test.py 20 "blank rune" 500. Nie wymaga uruchomionego bota; wpisuje na Default przez XTEST."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mozg, wypad, wyprawa

N = int(sys.argv[1]) if len(sys.argv) > 1 else 3
PRZEDMIOT = sys.argv[2] if len(sys.argv) > 2 else "ham"
LIMIT = int(sys.argv[3]) if len(sys.argv) > 3 else 150
ops = wypad.OperacjeZywe(log=print, wyslij=lambda t: mozg.wpisz_na_czacie(t))
ID = {3147} if "blank" in PRZEDMIOT.lower() else set(ops.id_ham)

def ile():
    p = ops.plecak()
    return None if p is None else sum(v for k, v in p["id"].items() if k in ID)

przed = ile(); print(f"{PRZEDMIOT} przed:", przed)
w = wyprawa.kup_u_npc("NPC", PRZEDMIOT, N, LIMIT or None, ops=ops, log=print, ja="Jointoramix")
print("wynik:", w)
if not w["ok"]:
    sys.exit({"brak_powitania": 2, "brak_oferty": 3, "za_drogo": 4, "zla_zakladka": 5}.get(w["powod"], 1))
time.sleep(2.0)
print(f"{PRZEDMIOT} po:", ile())
