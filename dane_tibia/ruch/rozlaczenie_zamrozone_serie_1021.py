# Serie zamrożonej pamięci w telemetrii 20-21.10 (SPEC_rozlaczenie_1021, pkt 2): ile fałszywych (zdrowa gra) i prawdziwych (wylogowanie). Uruchom: python3 -I rozlaczenie_zamrozone_serie_1021.py
import json,glob,time,os
base=os.path.expanduser('~/Games/Retronic/pomocnik/instancje')
pliki=sorted(glob.glob(base+'/*/logi/telemetria-2026102[01].jsonl')+glob.glob(base+'/_archiwum/*/logi/telemetria-2026102[01].jsonl'))
def klucz(d):
    st=tuple((s['n'],s['dx'],s['dy'],s['hp']) for s in d.get('stwory',[]))
    return (tuple(d['poz']),d.get('hp'),d.get('mana'),d.get('max_mana'),d.get('exp'),st)
def prawdziwe(inst,t0):
    lt=time.localtime(t0)
    hm=(lt.tm_mday,lt.tm_hour,lt.tm_min)
    if hm[0] in(20,21) and ((hm[1]==9 and hm[2]>=59) or (hm[1]==10 and hm[2]==0)): return True   # 10:00 reset
    if 'kutangen' in inst and hm[0]==20 and (hm[1]==21 and hm[2]>=1 or hm[1]==22 and hm[2]<=45): return 'U'
    if 'bober' in inst and hm[0]==21 and hm[1]==11 and 18<=hm[2]<=19: return True
    return False
import collections
stany=collections.Counter()
unk={10:0,25:0}
tot={10:[0,0],25:[0,0]}; prawd={10:0,25:0}; nobs=0; shots=0
wiersze=[]
for p in pliki:
    inst=p.split('instancje/')[1].split('/logi')[0]
    pr=[]
    for l in open(p):
        try:d=json.loads(l)
        except: continue
        if d.get('typ')=='probka' and d.get('poz'): pr.append(d)
    pr.sort(key=lambda d:d['t'])
    obs=sum(min(b['t']-a['t'],10) for a,b in zip(pr,pr[1:]))
    nobs+=obs
    i=0
    nf={10:0,25:0}; np_={10:0,25:0}
    while i<len(pr):
        j=i;k=klucz(pr[i])
        while j+1<len(pr) and klucz(pr[j+1])==k: j+=1
        dt=pr[j]['t']-pr[i]['t']
        for th in (10,25):
            if dt>=th:
                c=prawdziwe(inst,pr[i]['t'])
                if c=='U': unk[th]+=1
                elif c: np_[th]+=1; prawd[th]+=1
                else:
                    nf[th]+=1; tot[th][0]+=1; tot[th][1]+=dt
                    if th==25: stany[pr[i].get('stan')]+=1
                    if th==10: shots+=int((dt-10)/5)+1
        i=j+1
    wiersze.append((inst.replace('_archiwum/',''),p[-14:-6].lstrip('-') or p[-14:-6],round(obs/3600,1),nf[10],nf[25],np_[25]))
print('instancja/dzien, godz. obserwacji, serie>=10s (nie-wylogowanie), serie>=25s (nie-wylog.), serie>=25s wylogowanie')
for w in wiersze: print(w)
print('RAZEM godz obs',round(nobs/3600,1),'nie-wylog >=10s',tot[10],'>=25s',tot[25],'wylogowan >=25s',prawd[25],'zrzutow (co 5 s) przy 10s-prefiltrze',shots)

print(stany)

print('nieznane (kutangen 20.10 zgon)',unk)
