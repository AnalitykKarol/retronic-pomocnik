import json, sys, math, importlib.util
from PIL import Image, ImageDraw, ImageFont

P = "/home/charlie/Games/Retronic/pomocnik"
spec = importlib.util.spec_from_file_location("mapa_bot", f"{P}/mapa.py")
mb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mb)
m = mb.mapa()

X0, X1, Y0, Y1 = 32598, 32722, 32566, 32792     # okno widoku
Z = 7
S = 7                                           # px na pole
START = (32623, 32772, Z)

# spawny swamp trolli (mapa 7.4 = mapa klienta)
mons = {x["nazwa"]: x for x in json.load(open(f"{P}/dane_tibia/serwer74/potwory_pelne.json"))["potwory"]}
st = [s for s in mons["swamp troll"]["spawny"] if X0 <= s["x"] <= X1 and Y0 <= s["y"] <= Y1]
z7 = [s for s in st if s["z"] == Z]
cx = sum(s["x"] for s in z7) // len(z7)
cy = sum(s["y"] for s in z7) // len(z7)
cel = min(z7, key=lambda s: math.hypot(s["x"] - cx, s["y"] - cy))
CEL = (cel["x"], cel["y"], Z)
droga = m.droga(START, CEL, dlugosc=1)
assert droga, "brak drogi"
print("droga", len(droga), "pol, cel", CEL, "spawnow z7:", len(z7), "wszystkich w oknie:", len(st))

W, H = (X1 - X0 + 1) * S, (Y1 - Y0 + 1) * S
img = Image.new("RGB", (W, H), (0, 0, 0))
d = ImageDraw.Draw(img)
for y in range(Y0, Y1 + 1):
    for x in range(X0, X1 + 1):
        p = m.pole(x, y, Z)
        if p is None or not p[0] & mb.WIDZIANE:
            continue
        rgb = mb._kolor_tibii(p[1])
        if p[0] & mb.SCIANA:
            rgb = tuple(v // 3 for v in rgb)
        elif p[0] & mb.BEZ_DROGI:
            rgb = (255, 220, 0)
        px, py = (x - X0) * S, (y - Y0) * S
        d.rectangle([px, py, px + S - 1, py + S - 1], fill=rgb)

def ctr(x, y):
    return ((x - X0) * S + S // 2, (y - Y0) * S + S // 2)

try:
    F = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", 15)
    Fs = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans.ttf", 12)
except Exception:
    F = Fs = ImageFont.load_default()

# swamp trolle: z7 pelne kola, inne pietra obwodka z numerem
for s in st:
    px, py = ctr(s["x"], s["y"])
    r = 5 if s["z"] == Z else 4
    if s["z"] == Z:
        d.ellipse([px - r, py - r, px + r, py + r], fill=(255, 60, 200), outline=(255, 255, 255))
    else:
        d.ellipse([px - r, py - r, px + r, py + r], outline=(255, 160, 230))
        d.text((px + 5, py - 6), str(s["z"]), fill=(255, 200, 240), font=Fs)

# trasa: biala obwodka + czerwona linia
pts = [ctr(START[0], START[1])] + [ctr(p[0], p[1]) for p in droga]
d.line(pts, fill=(255, 255, 255), width=5)
d.line(pts, fill=(235, 30, 30), width=3)
# znaczniki co 50 krokow
for i in range(49, len(droga), 50):
    px, py = ctr(droga[i][0], droga[i][1])
    d.ellipse([px - 9, py - 9, px + 9, py + 9], fill=(20, 20, 20), outline=(255, 255, 255))
    t = str(i + 1)
    w = d.textlength(t, font=Fs)
    d.text((px - w / 2, py - 7), t, fill=(255, 255, 255), font=Fs)

def etykieta(xy, tekst, kolor, dx=12, dy=-8):
    x, y = xy
    w = d.textlength(tekst, font=F)
    d.rectangle([x + dx - 3, y + dy - 2, x + dx + w + 3, y + dy + 18], fill=(15, 15, 15), outline=kolor)
    d.text((x + dx, y + dy), tekst, fill=kolor, font=F)

sx, sy = ctr(START[0], START[1])
d.ellipse([sx - 8, sy - 8, sx + 8, sy + 8], fill=(60, 220, 60), outline=(255, 255, 255), width=2)
etykieta((sx, sy), "START: Port Hope (srodek miasta)", (120, 255, 120), dx=14, dy=-30)
ex, ey = ctr(CEL[0], CEL[1])
d.ellipse([ex - 9, ey - 9, ex + 9, ey + 9], outline=(255, 255, 255), width=3)
etykieta((ex, ey), f"CEL: swamp trolle ({CEL[0]},{CEL[1]})", (255, 150, 230), dx=16, dy=-8)

# skala/kompas i legenda
d.text((W - 60, 8), "N ^", fill=(255, 255, 255), font=F)
leg = [
    ((235, 30, 30), f"trasa: {len(droga)} pol (kolka = co 50)"),
    ((255, 60, 200), f"swamp troll, to samo pietro z{Z} ({len(z7)} spawnow)"),
    ((255, 160, 230), "swamp troll, inne pietro (numer = z)"),
    ((255, 220, 0), "schody / dziury"),
]
bx, by = 10, 10
d.rectangle([bx - 4, by - 4, bx + 360, by + 22 * len(leg) + 4], fill=(15, 15, 15), outline=(200, 200, 200))
for i, (k, t) in enumerate(leg):
    d.rectangle([bx, by + i * 22 + 3, bx + 14, by + i * 22 + 17], fill=k)
    d.text((bx + 22, by + i * 22 + 2), t, fill=(240, 240, 240), font=Fs)
out = sys.argv[1]
img.save(out)
print("zapisano", out, img.size)

# opis trasy: kierunki co ~25 pol
def kier(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = "N" if dy < -abs(dx) // 2 else ("S" if dy > abs(dx) // 2 else "")
    e = "E" if dx > abs(dy) // 2 else ("W" if dx < -abs(dy) // 2 else "")
    return (n + e) or "-"
seg, prev = [], (START[0], START[1])
for i in range(24, len(droga), 25):
    seg.append((i + 1, kier(prev, droga[i]), droga[i][0], droga[i][1])); prev = droga[i]
print(seg)
json.dump({"start": START, "cel": CEL, "kroki": len(droga), "droga": droga}, open(out.replace(".png", ".json"), "w"))
