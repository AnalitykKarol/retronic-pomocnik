"""Mały model liczbowy w samym numpy: standaryzacja, regresja logistyczna (L2) i MLP (ReLU, sigmoid).

Wagi do JSON (wynik odczytu = identyczny, bo float -> repr -> float jest bez strat). Ziarno deterministyczne.
Inferencja jednej próbki: `predict_proba(x)` z x 1-wymiarowym zwraca float.
"""
import json

import numpy as np

EPS = 1e-12


def sigmoid(z):
    return 0.5 * (1.0 + np.tanh(0.5 * z))  # stabilna numerycznie postać sigmoidu


class Standaryzacja:
    """Średnia i odchylenie z danych treningowych; stała kolumna (std~0) zostaje bez skalowania."""

    def __init__(self, sr=None, std=None):
        self.sr, self.std = sr, std

    def dopasuj(self, X):
        self.sr = X.mean(axis=0)
        s = X.std(axis=0)
        self.std = np.where(s < 1e-9, 1.0, s)
        return self

    def __call__(self, X):
        return (X - self.sr) / self.std

    def do_slownika(self):
        return {"sr": self.sr.tolist(), "std": self.std.tolist()}

    @classmethod
    def ze_slownika(cls, d):
        return cls(np.array(d["sr"], dtype=float), np.array(d["std"], dtype=float))


class _Adam:
    def __init__(self, parametry, lr=0.01, b1=0.9, b2=0.999):
        self.p, self.lr, self.b1, self.b2, self.k = parametry, lr, b1, b2, 0
        self.m = [np.zeros_like(a) for a in parametry]
        self.v = [np.zeros_like(a) for a in parametry]

    def krok(self, grad):
        self.k += 1
        for i, (a, g) in enumerate(zip(self.p, grad)):
            self.m[i] = self.b1 * self.m[i] + (1 - self.b1) * g
            self.v[i] = self.b2 * self.v[i] + (1 - self.b2) * g * g
            mh = self.m[i] / (1 - self.b1 ** self.k)
            vh = self.v[i] / (1 - self.b2 ** self.k)
            a -= self.lr * mh / (np.sqrt(vh) + 1e-8)


class RegresjaLogistyczna:
    """Regresja logistyczna z regularyzacją L2 (bez kary na wyraz wolny), uczona gradientem (Adam, cały zbiór)."""

    rodzaj = "lr"

    def __init__(self, l2=1.0, epoki=400, lr=0.05, ziarno=0):
        self.l2, self.epoki, self.lr, self.ziarno = l2, epoki, lr, ziarno
        self.std = None
        self.w = None
        self.b = 0.0

    def fit(self, X, y):
        self.std = Standaryzacja().dopasuj(X)
        Z = self.std(X)
        n, k = Z.shape
        w = np.zeros(k)
        b = np.zeros(1)
        opt = _Adam([w, b], lr=self.lr)
        for _ in range(self.epoki):
            p = sigmoid(Z @ w + b[0])
            r = p - y
            opt.krok([Z.T @ r / n + self.l2 * w / n, np.array([r.mean()])])
        self.w, self.b = w, float(b[0])
        return self

    def predict_proba(self, X):
        Z = self.std(np.asarray(X, dtype=float))
        if Z.ndim == 1:
            return float(sigmoid(Z @ self.w + self.b))
        return sigmoid(Z @ self.w + self.b)

    def do_slownika(self):
        return {"rodzaj": self.rodzaj, "std": self.std.do_slownika(), "w": self.w.tolist(), "b": self.b,
                "l2": self.l2}

    @classmethod
    def ze_slownika(cls, d):
        m = cls(l2=d.get("l2", 1.0))
        m.std = Standaryzacja.ze_slownika(d["std"])
        m.w, m.b = np.array(d["w"], dtype=float), float(d["b"])
        return m


class MLP:
    """Sieć: wejście -> 1-2 warstwy ukryte (ReLU) -> sigmoid; log-loss + L2, Adam, minibatche, stałe ziarno."""

    rodzaj = "mlp"

    def __init__(self, ukryte=(16, 16), l2=1.0, epoki=150, lr=0.01, paczka=64, ziarno=0):
        self.ukryte, self.l2, self.epoki, self.lr, self.paczka, self.ziarno = tuple(ukryte), l2, epoki, lr, paczka, ziarno
        self.std = None
        self.W, self.B = [], []

    def _forward(self, Z):
        a = [Z]
        for i in range(len(self.W) - 1):
            a.append(np.maximum(a[-1] @ self.W[i] + self.B[i], 0.0))
        return a, sigmoid(a[-1] @ self.W[-1] + self.B[-1])[:, 0]

    def fit(self, X, y):
        rng = np.random.default_rng(self.ziarno)
        self.std = Standaryzacja().dopasuj(X)
        Z = self.std(X)
        n, k = Z.shape
        wym = [k] + list(self.ukryte) + [1]
        self.W = [rng.normal(0, np.sqrt(2.0 / wym[i]), (wym[i], wym[i + 1])) for i in range(len(wym) - 1)]
        self.B = [np.zeros(wym[i + 1]) for i in range(len(wym) - 1)]
        opt = _Adam(self.W + self.B, lr=self.lr)
        L = len(self.W)
        for _ in range(self.epoki):
            kol = rng.permutation(n)
            for s in range(0, n, self.paczka):
                ix = kol[s:s + self.paczka]
                a, p = self._forward(Z[ix])
                d = ((p - y[ix]) / len(ix))[:, None]
                gW, gB = [None] * L, [None] * L
                for i in range(L - 1, -1, -1):
                    gW[i] = a[i].T @ d + self.l2 * self.W[i] / n
                    gB[i] = d.sum(axis=0)
                    if i:
                        d = (d @ self.W[i].T) * (a[i] > 0)
                opt.krok(gW + gB)
        return self

    def predict_proba(self, X):
        X = np.asarray(X, dtype=float)
        jeden = X.ndim == 1
        Z = self.std(X[None, :] if jeden else X)
        for i in range(len(self.W) - 1):
            Z = np.maximum(Z @ self.W[i] + self.B[i], 0.0)
        p = sigmoid(Z @ self.W[-1] + self.B[-1])[:, 0]
        return float(p[0]) if jeden else p

    def do_slownika(self):
        return {"rodzaj": self.rodzaj, "std": self.std.do_slownika(), "ukryte": list(self.ukryte),
                "W": [w.tolist() for w in self.W], "B": [b.tolist() for b in self.B], "l2": self.l2}

    @classmethod
    def ze_slownika(cls, d):
        m = cls(ukryte=d["ukryte"], l2=d.get("l2", 1.0))
        m.std = Standaryzacja.ze_slownika(d["std"])
        m.W = [np.array(w, dtype=float) for w in d["W"]]
        m.B = [np.array(b, dtype=float) for b in d["B"]]
        return m


def z_slownika(d):
    """Model z zapisanego słownika (rodzaj 'lr' albo 'mlp')."""
    return {"lr": RegresjaLogistyczna, "mlp": MLP}[d["rodzaj"]].ze_slownika(d)


def zapisz_json(sciezka, dane):
    with open(sciezka, "w", encoding="utf-8") as f:
        json.dump(dane, f, ensure_ascii=False)


def wczytaj_json(sciezka):
    with open(sciezka, encoding="utf-8") as f:
        return json.load(f)


# --- metryki ---

def log_loss(y, p):
    p = np.clip(p, EPS, 1 - EPS)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def trafnosc(y, p, prog=0.5):
    return float(np.mean((p >= prog) == (y >= 0.5)))


def auc(y, p):
    """Pole pod ROC (Mann-Whitney, rangi uśrednione przy remisach). None gdy brak obu klas."""
    y = np.asarray(y)
    p = np.asarray(p, dtype=float)
    n1 = int((y >= 0.5).sum())
    n0 = len(y) - n1
    if n1 == 0 or n0 == 0:
        return None
    kol = np.argsort(p, kind="mergesort")
    ps = p[kol]
    rangi = np.empty(len(p))
    i = 0
    while i < len(p):
        j = i
        while j + 1 < len(p) and ps[j + 1] == ps[i]:
            j += 1
        rangi[kol[i:j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return float((rangi[y >= 0.5].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def waznosc_permutacyjna(model, X, y, powtorzenia=10, ziarno=0):
    """Spadek AUC po przetasowaniu kolumny (większy = ważniejsza cecha). Zwraca listę per kolumna."""
    rng = np.random.default_rng(ziarno)
    baza = auc(y, model.predict_proba(X))
    if baza is None:
        return [None] * X.shape[1]
    wynik = []
    for k in range(X.shape[1]):
        spadki = []
        for _ in range(powtorzenia):
            Xp = X.copy()
            Xp[:, k] = rng.permutation(Xp[:, k])
            spadki.append(baza - auc(y, model.predict_proba(Xp)))
        wynik.append(float(np.mean(spadki)))
    return wynik
