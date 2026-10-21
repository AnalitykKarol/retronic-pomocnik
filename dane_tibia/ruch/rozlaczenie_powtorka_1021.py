# Powtórka detektora rozłączenia na telemetrii 20-21.10 (SPEC_rozlaczenie_1021, pkt 2). Wyrocznia zrzutu = znane okna wylogowania. Uruchom: python3 -I rozlaczenie_powtorka_1021.py
import json,glob,time,os,sys
sys.path.insert(0,os.path.expanduser('~/Games/Retronic/pomocnik'))
import rozlaczenie as R
base=os.path.expanduser('~/Games/Retronic/pomocnik/instancje')
pliki=sorted(glob.glob(base+'/*/logi/telemetria-2026102[01].jsonl')+glob.glob(base+'/_archiwum/*/logi/telemetria-2026102[01].jsonl'))
def wylog(inst,t):   # prawdziwe wylogowania (zrzut z ekranem logowania istnieje): okna czasowe
    lt=time.localtime(t); hm=lt.tm_hour*60+lt.tm_min
    if lt.tm_mday in (20,21) and (9*60+59<=hm<=10*60+40): return True       # 10:00 reset (do restartu przez admina)
    if 'bober' in inst and lt.tm_mday==21 and 11*60+18<=hm<=11*60+25: return True
    return False
tot_alarm=0; tot_zrz=0
for p in pliki:
    inst=p.split('instancje/')[1].split('/logi')[0].replace('_archiwum/','')
    pr=[]
    for l in open(p):
        try:d=json.loads(l)
        except: continue
        if d.get('typ')=='probka' and d.get('poz'): pr.append(d)
    pr.sort(key=lambda d:d['t'])
    det=R.Detektor(); zr=[0]; al=[]; wzn=[]
    for i,d in enumerate(pr):
        o=R.odcisk({'hp':d.get('hp'),'mana':d.get('mana'),'max_mana':d.get('max_mana'),'exp':d.get('exp')},d['poz'],[{'id':k,'x':s['dx'],'y':s['dy'],'z':0,'hp':s['hp']} for k,s in enumerate(d.get('stwory',[]))])
        def z(d=d):
            zr[0]+=1
            return wylog(inst,d['t'])
        w=det.krok(d['t'],o,z)
        if w=='rozlaczenie': al.append(d['t'])
        if w=='wznowienie': wzn.append(d['t'])
    # opóźnienie od początku zamrożenia
    opis=[]
    for t in al:
        # t_zm w chwili alarmu nie przechowujemy; policz wstecz: ostatnia zmiana odcisku
        opis.append(time.strftime('%d %H:%M:%S',time.localtime(t)))
    tot_alarm+=len(al); tot_zrz+=zr[0]
    print(f'{inst:24s} {p[-14:-6]} probek {len(pr):6d} zrzutow {zr[0]:4d} alarmow {len(al)} {opis} wznowien {len(wzn)}')
print('RAZEM alarmow',tot_alarm,'zrzutow',tot_zrz)
