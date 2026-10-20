"""wyloguj.py <id> <DISPLAY> [limit_s]: Ctrl+L co ~4 s aż klient pokaże ekran poza grą, wtedy sesja_gry.py zamknij."""
import io, os, subprocess, sys, time
from PIL import Image
from Xlib import X, XK, display
from Xlib.ext import xtest
POM = os.path.expanduser("~/Games/Retronic/pomocnik")
ID, DISP = sys.argv[1], sys.argv[2]; LIMIT = float(sys.argv[3]) if len(sys.argv) > 3 else 900
WL = open(f"{os.environ['XDG_RUNTIME_DIR']}/retronic-sesja-{ID}/wayland").read().strip()
def log(m): print(time.strftime("%H:%M:%S"), ID, m, flush=True)
def w_grze():
    png = subprocess.run(["grim", "-t", "png", "-"], env=dict(os.environ, WAYLAND_DISPLAY=WL), capture_output=True, timeout=10).stdout
    im = Image.open(io.BytesIO(png)).convert("RGB"); W = im.width
    a, b = im.getpixel((W - 80, 17)), im.getpixel((W - 50, 17))
    return (a[2] > 150 and a[0] < 60) or (b[1] > 150 and b[0] < 90)
def ctrl_l():
    d = display.Display(DISP)
    c = d.keysym_to_keycode(XK.string_to_keysym("Control_L")); l = d.keysym_to_keycode(XK.string_to_keysym("l"))
    for ev, k, s in ((X.KeyPress, c, .05), (X.KeyPress, l, .06), (X.KeyRelease, l, .04), (X.KeyRelease, c, 0)):
        xtest.fake_input(d, ev, k); d.sync(); time.sleep(s)
    d.close()
t0 = time.time(); proby = 0
while time.time() - t0 < LIMIT:
    if not w_grze():
        log(f"poza grą po {proby} próbach Ctrl+L, zamykam sesję")
        r = subprocess.run([sys.executable, "-I", f"{POM}/sesja_gry.py", "zamknij"], cwd=POM, env=dict(os.environ, RETRONIC_ID=ID), capture_output=True, text=True, timeout=120)
        log(f"zamknij: kod {r.returncode} {r.stdout.strip()[-300:]} {r.stderr.strip()[-200:]}"); sys.exit(0)
    ctrl_l(); proby += 1
    time.sleep(2.0 if proby == 1 else 4.0)
    if proby % 15 == 0: log(f"nadal w grze (walka?), próba {proby}")
log("limit czasu: nie udało się wylogować"); sys.exit(1)
