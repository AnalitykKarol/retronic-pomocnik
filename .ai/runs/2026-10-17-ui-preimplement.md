# Pre-implement UI/AI
Verdict: READY F1/F2; F3 po wyborze biblioteki.
Feature weight: nowy UI i kontrakt współbieżnych procesów. Bez HTTP/SQL.
Zachować publiczne sygnatury/formaty tras. Zamierzona zmiana: brak polityki = AI OFF.
Ryzyka: stara odpowiedź po OFF/ON, auto-rollback starego pliku, blokada procesu.
Mitigacje: epoka, guard skutków, anulowanie procesów tej instancji, CAS i testy wyścigów.
Trasy miejskie mają dziś nazwy zaszyte w wyprawa.py — formularz musi zmieniać wykonanie.
Pozostałe ryzyko: naturalna gra i restart sesji wymagają osobnego dowodu na żywo.
