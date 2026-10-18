# Panel Retronic — projekt UI

Desktop, polski interfejs, osobno od VNC. Tkinter proponowany, wybór biblioteki oczekuje odpowiedzi.
Nagłówek + instancja + stale widoczny Start/Stop/AI. Zakładki: Stan, Ustawienia,
Spoty i trasy, Runy, Zaawansowane. Status zapisu/błędu u dołu. AI OFF to osobny
stan od BOT STOP. To wyróżniający element: „AI wyłączone — reguły człowieka”.

Tokens: background #eef1ee, surface #fafbf8, ink #202b28, muted #52615b,
accent #245b46, danger #a52e31, border #c6cec8. Sans systemowy 11/13/20,
monospace 10 dla logu. Okno minimum 800×700, rozmiar docelowy 1100×850.
Jasny, spokojny warsztat obok ciemnej gry, bez dekoracyjnych kart i gradientów.
Jeden zapis na sekcję. Brak zapisów przy otwarciu. Filtr zaawansowanych, pionowy scroll.
Koszt many i próg rozpoczęcia to osobne opisane pola. Widoczne błędy i zmiany niezapisane.
Stan AI pokazuje odczyt potwierdzonej polityki, a nie tylko intencję kliknięcia.
Brak gry nie blokuje edycji ustawień, blokuje start z podanym powodem.
Procesy/sockety nie blokują pętli UI; Tab/Shift+Tab i wyraźny fokus.
Pomiary kontrolek przez Tk winfo/bbox przy 800×700 oraz 1100×850 + screenshot.
DOM probe n/a: natywny interfejs nie posiada DOM; instrumentem jest drzewo widgetów Tk.
Design log: panel web odrzucony przez Karola; bez osadzania obrazu VNC.
