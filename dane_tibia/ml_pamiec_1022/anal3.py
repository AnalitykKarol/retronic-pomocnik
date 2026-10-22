import numpy as np,json
Z=[np.load(f"full_{t}.npz") for t in "ABC"]
res=[]
for k in Z[0].files:
    if k not in Z[1].files or k not in Z[2].files: continue
    base=int(k,16)
    for al in (0,4):
        a,b,c=[z[k][al:len(z[k])-((len(z[k])-al)%8)].view("<f8") for z in Z]
        with np.errstate(all="ignore"):
            ok=(a>=0)&(a<=99)&(a==np.floor(a))&(b>=a)&(c>=b)&(b-a<=3)&(c-b<=3)&(c!=a)&(c==np.floor(c))&(b==np.floor(b))
        idx=np.nonzero(ok)[0]
        for i in idx:
            nb=[j for j in range(-4,5) if j and 0<=i+j<len(a) and a[i+j]==b[i+j]==c[i+j] and 7<=a[i+j]<=40 and a[i+j]==np.floor(a[i+j])]
            res.append((base+al+8*int(i),float(a[i]),float(b[i]),float(c[i]),nb))
print(len(res))
for r in res:
    if r[4]: print(hex(r[0]),r[1:4],r[4])
