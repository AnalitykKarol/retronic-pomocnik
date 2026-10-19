# Diagnoza: fałszywe „Wpadłem” z9 -> z8, bot chodzi po złym piętrze (Johny, 19.10 ~22:45, tylko odczyt)

Zgłoszenie Karola: „Johny Dang się wyjebał, znów się zawiesił”.

Przebieg (`instancje/test/logi/mozg-20261019-2120.log`):
- 22:41:29 `Przejście pięter: z8 -> z9 w (32482, 32296, 9)` — zamierzone zejście dziurą na trasie patrolu, potem loot na z9.
- 22:41:34 `Wpadłem: (32482,32296,9) -> (32482,32297,8)` + `Wpadnięcie: z8 jest na trasie/patrolu, dalej normalnie`. FAŁSZ: gra cały czas
  pokazuje postać na z9 (RPC `{"cmd":"pozycja","nazwa":"Johny Dang"}` -> (32489, 32298, 9); własny wpis na liście `stwory` też z9).
  To samo wcześniej o 22:40:44 (`(32483,32297,9) -> (32482,32297,8)`).
- Od 22:41:35 bot idzie po mapie z8 („[IDZ] patrol m8”), kroki „nie ruszył”, co ~30 s „utknięcie, wracam na trasę do punktu 0”,
  ratunek w cieniu: S4 22:41:45 i 22:43:46 (wizyt 15, oscylacje 27), S3 22:42:05 i 22:44:07 (stoi 152 s).

Hipoteza (niepotwierdzona w kodzie): chwilowy odczyt pozycji z8 (stary/zamrożony wpis własnej postaci, rodzina „widmo postaci” 18.10,
STAN.md pkt 3) uruchamia wykrycie wpadnięcia bez drugiego potwierdzenia. Do sprawdzenia: `wpadniecie`/`pietra.py` (skąd bierze z),
czy wymaga 2 zgodnych odczytów, i czy po fałszywym wpadnięciu jest powrót do prawdy (RPC pokazuje z9, a bot zostaje przy z8).
Kierunek naprawy (do spec, decyzja Karola): wpadnięcie tylko po >= 2 zgodnych odczytach RPC `pozycja` w odstępie; okresowa zgodność
piętra trasy z RPC (rozjazd > N s = synchronizacja z RPC zamiast „utknięcie, wracam na trasę”).
