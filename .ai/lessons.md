# Lekcje pracy agenta

## 2026-10-24 — Plan naprawy musi opisywać wykonanie

- Kontekst: użytkownik zamówił analizę i plan naprawy optymalizacyjnej.
- Problem: odpowiedź eksponowała wyniki audytu; zadania naprawcze pozostały zbyt ogólne.
- Reguła: oddawać osobny plan z kolejnością, plikami/funkcjami, konkretną zmianą, zależnościami i warunkiem odbioru; wyniki analizy są materiałem wspierającym.
- Zakres: planowanie napraw i optymalizacji. Plan nie oznacza zgody na wdrożenie.

## 2026-10-24 — Plan optymalizacji wymaga zweryfikowanego kierunku

- Kontekst: druga korekta użytkownika po dopisaniu zadań i kryteriów odbioru.
- Problem: lista konkretnie nazwanych eksperymentów nadal nie rozstrzygała, co rzeczywiście poprawić; pierwszy zalecany wariant NumPy okazał się wolniejszy po sprawdzeniu.
- Reguła: przed oddaniem planu naprawy zweryfikować krytyczne zamiany w izolowanych prototypach. Do głównego zakresu wpisywać rozwiązania z dowodem zgodności i poprawy; pomysły bez dowodu oddzielić. Test integracji pozostaje wymagany, ale nie zastępuje wyboru rozwiązania.
- Zakres: analiza wydajności i plany naprawy; wynik syntetyczny zawsze oddzielać od oszczędności zmierzonej w działającym systemie.

## 2026-10-24 — Sygnatury muszą opisywać faktyczny kod, nie próbę jego załadowania

- Kontekst: naprawa CPU, warunkowe ładowanie czatu oraz włączanie/cofanie optymalizacji.
- Problem: timestampowy pyc nie widzi mtime_ns, a częściowo wykonany reload/exec zostawia funkcje zmienione przed błędem. Stary marker może wtedy zaakceptować błędny kod po przywróceniu źródła i mtime.
- Reguła: ładować aktualne źródło, podpisywać je po udanym wykonaniu i unieważniać marker PRZED każdą ścieżką reload/exec, także przy wyłączonej optymalizacji. Test błędu musi przywracać także oryginalne metadane.
- Zakres: dynamiczne ładowanie kodu. Dowód: test_cpu_wdrozenie + regression-detection-proof.json.

## 2026-10-24 — Rollback i konfiguracja wymagają własnych snapshotów

- Kontekst: wdrożenie CPU na jednej instancji, komponenty scan/chat/pid włączane osobno.
- Problem: hash celu odczytany po zapisie może już należeć do cudzego kodu; osobny odczyt manifestu dla każdej flagi miesza wersje podczas podmiany.
- Reguła: własność zapisu określa hash dokładnego payloadu przekazanego do atomic replace. Cofnięcie pomija cudze zmiany. Konfigurację czytać raz i wyprowadzać flagi z jednego niezmiennego snapshotu.
- Zakres: instalatory i przełączniki etapowego wdrożenia. Dowód: dwa testy regresji z odtworzeniem wadliwych wersji.
