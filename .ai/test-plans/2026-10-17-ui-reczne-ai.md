# Plan weryfikacji UI/AI — z zatwierdzonego zakresu

Przypadki wyprowadzone przed odczytem implementacji agentów, z kontraktu sekcji 4
specu. Zakres testów wynika z zatwierdzonej funkcji; żadne próby nie dotykają prawdziwej
postaci bez uzgodnienia. Wykonanie/testy szczegółowe i niezależny review po integracji.

| ID | Oczekiwane zachowanie |
|---|---|
| AI01 | Brak/uszkodzona polityka = OFF, zero uruchomień realnego modelu |
| AI02 | ON→OFF anuluje proces własnego modelu i odrzuca wynik |
| AI03 | ON→OFF→ON nie stosuje odpowiedzi z poprzedniej epoki |
| AI04 | Wszystkie kanały: decyzje, czat, obserwator, analityk pościgu, czaszki |
| AI05 | Ręczne ustawienia po zmianie/AI OFF nie są nadpisane starym rollbackiem |
| AI06 | Dwa instance IDs mają odrębne polityki |
| CF01 | Wszystkie zarejestrowane 257 parametrów mają edytor, walidację i opis domyślnych |
| CF02 | F8, koszt many i próg startu zapisują się i przeżywają ponowne otwarcie |
| CF03 | Zapis stalej rewizji odrzucony, plik i niezwiązane klucze zachowane |
| CF04 | Odczyt/otwarcie panelu nie zapisuje konfiguracji ani nie uruchamia bota |
| CF05 | Zapisana konfiguracja ≠ zastosowana; brak ack to stan oczekujący |
| TR01 | Nagranie nazwanej trasy i przypisanie nowego spotu bez edycji Pythona |
| TR02 | Konflikt nazwy, zła ścieżka, dwa rejestratory nie niszczą istniejących tras |
| TR03 | Dojście/do miasta/powrót zapisują się, a silnik korzysta z przypisania |
| CT01 | Start/stop celuje w wybraną instancję, podwójny start odrzucony |
| CT02 | STOP nie kończy gry i podglądu, zwalnia klawisze |
| UI01 | Prawdziwe widgety: zapis run, start/stop fixture, przełącznik AI i trasy |
| UI02 | UI bez obciętych kontrolek przy 800×700/1100×850, działający scroll/filtr |
| UI03 | Nieudany zapis/operacja ma widoczny błąd, nie udaje sukcesu |
| UI04 | Zmiana instancji nie gubi niejawnie niezapisanych danych ani nie zapisuje w poprzedniej |

Próby CT02 oraz produkcji run/przejścia trasy z prawdziwym klientem pozostają
NATURAL QA PENDING, jeśli użytkownik nie wskaże bezpiecznego momentu. Testy fixture
nie stanowią dowodu naturalnej gry. Istniejące regresje odróżnia baseline.
