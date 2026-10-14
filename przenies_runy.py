"""Jednorazowo: przenosi blanki/runy z głównego plecaka do pojemnika na runy (loot.przenies_do_runow)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loot
print("przeniesiono", loot.przenies_do_runow(), flush=True)
