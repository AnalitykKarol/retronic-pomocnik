import importlib.util, json, math, itertools, sys
from PIL import Image, ImageDraw, ImageFont
spec=importlib.util.spec_from_file_location('mb','/home/charlie/Games/Retronic/pomocnik/mapa.py'); mb=importlib.util.module_from_spec(spec); spec.loader.exec_module(mb)
m=mb.Mapa('/home/charlie/Games/Retronic/pomocnik/mapa/map74.otmm')
D=json.load(open('skladowa_z8.json')); comp={tuple(p) for p in D['c']}; sp=D['sp']
Z=8; START=(33106,31849,Z)
# punkty: scal spawny bliskie sobie (<=3 pola) w jeden przystanek
stops=[]
for s in sorted(sp,key=lambda s:(s['pt'][0],s['pt'][1])):
    for t in stops:
        if max(abs(t['pt'][0]-s['pt'][0]),abs(t['pt'][1]-s['pt'][1]))<=3:
            t['n']+=s['n'];t['spawny']+=1;break
    else: stops.append({'pt':s['pt'],'n':s['n'],'spawny':1,'t':s['t']})
print('przystankow',len(stops),'goblinow',sum(t['n'] for t in stops))
nodes=[START[:2]]+[t['pt'] for t in stops]
def path(a,b):
    d=m.droga((a[0],a[1],Z),(b[0],b[1]),dlugosc=0,limit=400000)
    return None if d is None else [(p[0],p[1]) for p in d]
N=len(nodes);dist=[[0]*N for _ in range(N)];pp={}
for i in range(N):
    for j in range(i+1,N):
        p=path(nodes[i],nodes[j])
        if p is None: print('brak drogi',nodes[i],nodes[j]); dist[i][j]=dist[j][i]=10**6; continue
        dist[i][j]=dist[j][i]=len(p); pp[(i,j)]=p; pp[(j,i)]=[nodes[i]]+p[:-1][::-1][:-0 or None] if False else None
def trasa(i,j):
    if (i,j) in pp and pp[(i,j)] is not None: return pp[(i,j)]
    p=pp[(j,i)] if (j,i) in pp else None
    return list(reversed([nodes[j]]+p[:-1])) + [nodes[j]] if False else None
# kolejnosc: najblizszy sasiad + 2-opt na cyklu od startu
order=[0];left=set(range(1,N))
while left:
    k=min(left,key=lambda j:dist[order[-1]][j]);order.append(k);left.remove(k)
def dl(o): return sum(dist[o[i]][o[(i+1)%len(o)]] for i in range(len(o)))
imp=True
while imp:
    imp=False
    for i in range(1,N-1):
        for j in range(i+1,N):
            o=order[:i]+order[i:j+1][::-1]+order[j+1:]
            if dl(o)<dl(order): order=o;imp=True
print('kolejnosc',order,'dlugosc petli',dl(order),'pol')
# zloz droge: p(a,b) liczymy ponownie (A* jest deterministyczny)
full=[START[:2]]
for i in range(N):
    a,b=nodes[order[i]],nodes[order[(i+1)%N]]
    p=path(a,b); full+=p
print('petla',len(full),'pol')
out={'start':START,'przystanki':[{'kolejnosc':k,'x':nodes[o][0],'y':nodes[o][1],'z':Z,**({} if o==0 else {'goblinow':stops[o-1]['n'],'spawnow':stops[o-1]['spawny']})} for k,o in enumerate(order)],'trasa':[[x,y,Z] for x,y in full],'dlugosc_petli':len(full)}
json.dump(out,open('patrol_gobliny_z8.json','w'),ensure_ascii=False)
# obraz
X0,X1,Y0,Y1=33030,33128,31822,31888;Sx=11
img=Image.new('RGB',((X1-X0+1)*Sx,(Y1-Y0+1)*Sx),(0,0,0));d=ImageDraw.Draw(img)
for y in range(Y0,Y1+1):
    for x in range(X0,X1+1):
        p=m.pole(x,y,Z)
        if p is None or not p[0]&1: continue
        rgb=mb._kolor_tibii(p[1])
        if p[0]&4: rgb=tuple(v//3 for v in rgb)
        elif p[0]&2: rgb=(255,220,0)
        d.rectangle([(x-X0)*Sx,(y-Y0)*Sx,(x-X0)*Sx+Sx-1,(y-Y0)*Sx+Sx-1],fill=rgb)
c=lambda x,y:((x-X0)*Sx+Sx//2,(y-Y0)*Sx+Sx//2)
pts=[c(x,y) for x,y in full]
d.line(pts,fill=(255,255,255),width=5);d.line(pts,fill=(235,30,30),width=3)
F=ImageFont.load_default(size=16);Fs=ImageFont.load_default(size=13)
for k,o in enumerate(order):
    x,y=c(*nodes[o])
    if o==0:
        d.ellipse([x-10,y-10,x+10,y+10],fill=(60,220,60),outline=(255,255,255),width=2);d.text((x+13,y-9),'START (ty)',fill=(150,255,150),font=F);continue
    d.ellipse([x-11,y-11,x+11,y+11],fill=(255,60,200),outline=(255,255,255),width=2)
    t=str(k);w=d.textlength(t,font=F);d.text((x-w/2,y-9),t,fill=(255,255,255),font=F)
    d.text((x+13,y-8),f"{stops[o-1]['n']} gob.",fill=(255,200,240),font=Fs)
ex,ey=c(33107,31846)
d.ellipse([ex-9,ey-9,ex+9,ey+9],outline=(80,200,255),width=3);d.text((ex+12,ey-26),'LINA (wyjscie) 33107,31846',fill=(120,220,255),font=Fs)
ex2,ey2=c(33106,31850)
d.ellipse([ex2-7,ey2-7,ex2+7,ey2+7],outline=(80,200,255),width=2);d.text((ex2+10,ey2-4),'lina? 33106,31850',fill=(120,220,255),font=Fs)
leg=[((235,30,30),f'petla patrolowa: {len(full)} pol (z{Z})'),((255,60,200),'przystanek = spawn(y) goblinow, numer = kolejnosc'),((255,220,0),'schody / dziury'),((60,220,60),'tu stoisz teraz')]
d.rectangle([4,4,380,24*len(leg)+8],fill=(15,15,15),outline=(200,200,200))
for i,(k,t) in enumerate(leg):
    d.rectangle([10,10+i*24,24,24+i*24],fill=k);d.text((32,10+i*24),t,fill=(240,240,240),font=Fs)
img.save('patrol_gobliny_z8.png');print(img.size)
