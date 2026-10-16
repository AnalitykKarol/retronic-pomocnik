import os as _os; _os.environ["RETRONIC_TESTY"]="1"
import json, sys, types, random
sys.dont_write_bytecode=True
R=_os.path.expanduser("~/Games/Retronic/pomocnik"); sys.path.insert(0,R); _os.chdir(R)
import cavebot, bot, mapa as _mapa, wpadniecie
from pathlib import Path
LOG=[]
cavebot.log=lambda *a: LOG.append(" ".join(map(str,a)))
cavebot.REAKCJA=(0.0,0.0); cavebot.DRUGI_CEL=0.0; cavebot.ROZRZUT_PROGU=0.0
cavebot.ODWROCENIE_TRASY=0.0; cavebot.SCINANIE=(0.0,2)
cavebot.PAUZA_KROTKA=(0.0,0.4,1.5); cavebot.PAUZA_DLUGA=(0.0,3.0,8.0)
cavebot.ATAK_TYLKO_PRZY_CELU=False
M=_mapa.Mapa()
DZ={tuple(d) for d in json.loads((Path(R)/"trasy/dziury_nauczone.json").read_text())["dziury"]}
BLOK=set()
def idzie(x,y,z):
    if (x,y,z) in BLOK: return False
    v=M.flagi(x,y,z); return bool(v&1) and not v&4 and (x,y,z) not in DZ
STAIRS=(32498,32270,8)
class Swiat:
    def __init__(s,poz): s.t=0.0; s.poz=list(poz); s.hist=[]; s.zszedl=False
    def zegar(s): return s.t
    def klik(s,dx,dy): s.cel=None
    def spij(s,d): s.t+=d
    def zapytaj(s,z):
        s.t+=0.05
        if z["cmd"]=="gracz": return {"gracz":{"hp":220,"max_hp":220,"mana":245,"max_mana":245}}
        if z["cmd"]=="stwory": return {"stwory":[{"id":1,"nazwa":"Ja","gracz":True,"x":s.poz[0],"y":s.poz[1],"z":s.poz[2],"hp":100}]}
    def ruch(s,dx,dy):
        x,y,z=s.poz[0]+dx,s.poz[1]+dy,s.poz[2]
        if (x,y,z)==STAIRS: s.zszedl=True; s.hist.append("SCHODY"); s.poz[:]=[32498,32271,9]; return
        if not idzie(x,y,z): s.hist.append(("bok",x,y)); return
        s.poz[:]=[x,y,z]; s.hist.append((x,y))
class P:
    nazwa="Ja"
    def __init__(p,s): p.s=s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p,k): pass
    def krok(p,k):
        d=bot.KIERUNKI[k]; p.s.t+=0.2; przed=tuple(p.s.poz); p.s.ruch(*d); return tuple(p.s.poz)!=przed
    def krok_skos(p,dx,dy): return False
class Ops:
    def __init__(o,s): o.s=s
    def uzyj_pole(o,pole,poz): pass
    def uzyj_line(o,pole,poz): pass
for h in ("_hak_telemetrii","_hak_pochodni","_hak_wypadu"): setattr(cavebot.Cavebot,h,lambda self:None)
cavebot.TRYB_PATROL=1; cavebot.PATROL_PLIK="miejsca_troll.json"
MI=json.loads((Path(R)/"trasy/miejsca_troll.json").read_text())
s=Swiat((32497,32270,8))
loot=types.SimpleNamespace(zbierz=lambda z,g:"ok")
b=cavebot.Cavebot(P(s),[(32497,32270,8),(32500,32270,8)],zapytaj=s.zapytaj,atak=lambda m,g:None,alarm=lambda w:None,spij=s.spij,zegar=s.zegar,loot=loot,mapa=M,klik=s.klik,okrazenia=999)
b.pietra_ops=Ops(s); b.zapis_znanych=False
w=wpadniecie.Wpadniecie(b,konf=cavebot,log=lambda t:None); w.dziury=set(DZ); b.wpadniecie=w
b._patrol_wczytaj()
m2=[m for m in b.miejsca if m["id"]==2][0]
np_=b._patrol_nowy(tuple(s.poz),m2,"test")
print("nowy:",np_ and np_["seg"][:8], LOG[-2:])
b.patrol=np_
b.krok_z=((32497,32269,8),s.t)
orig=b.krok_do
def kd(cel):
    print("krok_do",tuple(s.poz),"->",cel,"kier",cavebot.kierunki_do(s.poz[0],s.poz[1],cel[0],cel[1]),"krok_z",b.krok_z,"zablok",dict(b.zablokowane))
    return orig(cel)
BLOK.add((32497,32269,8))
b.krok_do=kd
od=b._droga_trasy
def dt(p,c):
    r=od(p,c); print("droga_trasy",p,c,"->",r and r[:5]); return r
b._droga_trasy=dt
for i in range(40):
    try: b.tick()
    except Exception as e: print("EXC",repr(e)); break
    if s.zszedl: break
print("ticki",i,"t",round(s.t),"zszedl",s.zszedl)
print(s.hist[:30])
print("\n".join(LOG[-15:]))
