# UI ręczne / AI OFF
Baza 722a8c1, branch feat/ui-reczne-ai. Spec: dane_tibia/SPEC_ui_reczne_ai_1017.md.
Cudze zmiany trasy/dziury_nauczone.json zachować. STAN.md zawiera pamięć tej sesji.
Użytkownik zatwierdził realizację, brak zgody na commit/push.
Team: AI + serwis + UI we własnych worktree, integracja diffów bez commitów.
F1/F2 równolegle → integracja → GUI → niezależne review/QA.

```yaml
ownership:
  F1: [polityka_ai.py, mozg.py, pokretla.py, analityk.py, analityk_poscigu.py, czaszka.py, testy/test_polityka_ai.py]
  F2: [sterowanie.py, uruchom.sh, wyprawa.py, testy/test_sterowanie.py]
  F3: [panel_gui.py, panel_gui.sh, testy/test_panel_gui.py]
  lead: [dane_tibia/SPEC_ui_reczne_ai_1017.md, design-system/MASTER.md, STAN.md]
```
Brak aktywnego CLAUDE_PLUGIN_ROOT/ownership-check; rozłączność plików sprawdzona ręcznie.
GUI: oczekuje wyboru biblioteki. Brak serwerów DB/HTTP. Testy gry: fixture, nie konto.
