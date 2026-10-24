"""Wykrywanie zatrucia i jego leczenie (23.10, zgon odchyda i gebelisha pod dziurą (32354,32131,z8), Scorpion: „okropna trucizna”).

Odczyt flag statusu z pamięci klienta (`m_states`, u32) NIE jest zmierzony (dane_tibia/AUDYT_odczyt_i_mapa.md: [BRAK]), więc:
 1. jeśli odpowiedź `gracz` ma pole `stany` (bitmaska), bit TRUCIZNA = 1 jest wiarygodny (po pomiarze na żywo; patrz pomiar niżej),
 2. inaczej wnioskujemy z HP: w oknie OKNO_S spadek >= SPADEK_HP w >= MIN_SPADKOW osobnych spadkach, przy czym żaden stwór nie stoi
    obok nas (melee) i nie stoimy w ogniu. Trucizna tyka po 1-3 HP co 2-3 s; cios w zwarciu jest większy i nieregularny.
Pomiar na żywo do zrobienia (nie wykonany): postać zatruta (np. Scorpion/Poison Spider albo ręcznie), odczyt `bajty` bloku gracza
przed/po i różnica; potem `STANY_TRUCIZNA_BIT` w tym pliku.

Leczenie (kolejność): czar `exana pox` (klawisz ZATRUCIE_CZAR_KLAWISZ, mana >= ZATRUCIE_CZAR_KOSZT) -> antidote rune (id 3153) użyta na siebie
(Ctrl+klik runy, klik na własne pole; wypad.OperacjeZywe.uzyj_antidote). Po każdej próbie przerwa PRZERWA_S; 3 próby bez końca zatrucia = przerwa 5 min.
"""
from __future__ import annotations

ID_ANTIDOTE_RUNE = 3153          # dane_tibia/przedmioty.json: "antidote rune" id_klienta 3153
STANY_TRUCIZNA_BIT = 1           # HIPOTEZA (Tibia: PZ_POISON = 1<<0), niezmierzona w tym kliencie; używana tylko gdy `gracz` zwróci `stany`
OKNO_S = 12.0
SPADEK_HP = 4                    # łączny spadek HP w oknie
MIN_SPADKOW = 3                  # osobnych spadków (tyknięć)
PRZERWA_S = 8.0
PORAZKI_MAX = 3
PRZERWA_PO_PORAZKACH_S = 300.0


class Zatrucie:
    def __init__(self, okno_s=OKNO_S, spadek_hp=SPADEK_HP, min_spadkow=MIN_SPADKOW):
        self.okno_s, self.spadek_hp, self.min_spadkow = okno_s, spadek_hp, min_spadkow
        self.hist = []               # [(t, hp)]
        self.do = float("-inf")      # nie leczymy przed tą chwilą
        self.porazki = 0
        self.ostatnia = None         # t ostatniej próby leczenia
        self.zrodlo = None

    def odczyt(self, teraz, hp, stany=None, stwor_obok=False, ogien=False):
        """True = podejrzenie/pewność zatrucia. `stany`: bitmaska z pamięci (None = brak odczytu)."""
        if stany is not None:
            self.zrodlo = "pamiec"
            return bool(int(stany) & STANY_TRUCIZNA_BIT)
        h = self.hist
        if h and hp > h[-1][1] + 2:      # leczenie/wzrost HP: okno liczymy od nowa
            h.clear()
        h.append((teraz, hp))
        self.hist = h = [(t, v) for t, v in h if teraz - t <= self.okno_s]
        if stwor_obok or ogien:
            return False
        spadki = [a[1] - b[1] for a, b in zip(h, h[1:]) if b[1] < a[1]]
        if len(spadki) >= self.min_spadkow and sum(spadki) >= self.spadek_hp and all(s <= 6 for s in spadki):
            self.zrodlo = "hp"
            return True
        return False

    def gotowy(self, teraz):
        return teraz >= self.do and (self.ostatnia is None or teraz - self.ostatnia >= PRZERWA_S)

    def po_probie(self, teraz, nadal):
        """`nadal`: czy zatrucie trwa po poprzedniej próbie. Zlicza porażki i ustawia przerwy."""
        if self.ostatnia is not None and nadal:
            self.porazki += 1
        elif not nadal:
            self.porazki = 0
        self.ostatnia = teraz
        if self.porazki >= PORAZKI_MAX:
            self.porazki = 0
            self.do = teraz + PRZERWA_PO_PORAZKACH_S
