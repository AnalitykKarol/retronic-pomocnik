"""Zwiecha walki (23.10, wydra: 11:08-11:38, ~29 min bez ani jednego zabitego trolla): bot stoi przy potworach, klika w nie,
klik nie trafia ("[ATAK] 5 klików bez efektu"), cel jest ignorowany 30 s i wraca. Żadna dotychczasowa osłona nie reagowała:
strażnik celu tylko ignoruje cel (i wraca), alarm "3 utknięcia" to samo powiadomienie, strażnik postępu jest domyślnie wyłączony,
a nadzorca restartuje tylko POZA walką (fantomowa walka go blokuje).

Czyste liczenie (bez cavebota, zegar wstrzykiwany): zdarzenie = "klik bez efektu" na celu (albo S2 strażnika celu). ZWIECHA =
>= N takich zdarzeń w oknie OKNO_S, a od ostatniego przyrostu expa nie padł żaden potwór. Potem drabina napraw (NAPRAWA, nigdy STOP,
CLAUDE.md „Zasada naprawiania”):
  1  miękka    zapomnij prostokąt mapy, Escape, wyczyść ignorowanie/liczniki kliknięć/cel
  2  inny punkt  j.w. + zignoruj stwory w pobliżu, zmiana celu patrolu / skok na najbliższy punkt trasy
  3  restart   restart procesu bota (ten sam mechanizm co ŚLEPOTA: os.execv, ta sama mapa i tryb)
Do następnego szczebla: >= KROK_N kolejnych zdarzeń albo >= 1 zdarzenie i KROK_S s od poprzedniego szczebla. Epizod kończy się
przyrostem expa albo ciszą CISZA_S s bez zdarzeń. Moduł nic nie wykonuje: zwraca numer szczebla, wykonuje cavebot."""

DOMYSLNE = dict(ZWIECHA_N=3, ZWIECHA_OKNO_S=300.0, ZWIECHA_KROK_N=2, ZWIECHA_KROK_S=100.0, ZWIECHA_CISZA_S=240.0,
                ZWIECHA_ODSTEP_S=15.0)
MAX_SZCZEBEL = 3


class Detektor:
    def __init__(self, konf=None):
        self.konf = konf
        self.reset()

    def k(self, nazwa):
        return getattr(self.konf, nazwa, DOMYSLNE[nazwa]) if self.konf is not None else DOMYSLNE[nazwa]

    def reset(self):
        self.zdarzenia = []          # [(t, rodzaj, poz)] epizodu
        self.szczebel = 0
        self.t_szczebla = None
        self.od_szczebla = 0         # zdarzeń od ostatniego szczebla
        self.exp_ref = None
        self.t_pierwsze = None

    def zdarzenie(self, t, rodzaj, poz=None):
        """Zlicza zdarzenie (z odstępem ODSTEP_S: S2 strażnika w tym samym obiegu co "bez efektu" to jedno). True = policzone."""
        if self.zdarzenia and t - self.zdarzenia[-1][0] < self.k("ZWIECHA_ODSTEP_S"):
            return False
        if not self.zdarzenia:
            self.t_pierwsze = t
        self.zdarzenia.append((t, rodzaj, tuple(poz) if poz else None))
        if self.szczebel:
            self.od_szczebla += 1
        return True

    def tick(self, t, exp=None):
        """Zwraca numer szczebla do wykonania (1..3) albo None. Przyrost expa kończy epizod."""
        if exp is not None:
            if self.exp_ref is not None and exp > self.exp_ref:
                self.reset()
            self.exp_ref = exp
        if not self.zdarzenia:
            return None
        if t - self.zdarzenia[-1][0] >= self.k("ZWIECHA_CISZA_S"):
            exp_ref = self.exp_ref
            self.reset()
            self.exp_ref = exp_ref
            return None
        if not self.szczebel:
            okno = [z for z in self.zdarzenia if t - z[0] <= self.k("ZWIECHA_OKNO_S")]
            self.zdarzenia = okno
            if len(okno) >= int(self.k("ZWIECHA_N")):
                return self._dalej(t)
            return None
        if self.od_szczebla >= int(self.k("ZWIECHA_KROK_N")) or \
                (self.od_szczebla >= 1 and t - self.t_szczebla >= self.k("ZWIECHA_KROK_S")):
            return self._dalej(t)
        return None

    def _dalej(self, t):
        self.szczebel = min(MAX_SZCZEBEL, self.szczebel + 1)
        self.t_szczebla = t
        self.od_szczebla = 0
        return self.szczebel

    def od_s(self, t):
        return 0.0 if self.t_pierwsze is None else t - self.t_pierwsze
