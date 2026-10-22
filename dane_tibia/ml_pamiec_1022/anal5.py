import numpy as np
Z=[np.load(f"full_{t}.npz") for t in "ACDE"]
res=[]
for k in Z[0].files:
    if any(k not in z.files for z in Z): continue
    base=int(k,16)
    for al in (0,4):
        S=np.stack([z[k][al:len(z[k])-((len(z[k])-al)%8)].view("<f8") for z in Z])
        with np.errstate(all="ignore"):
            d=np.diff(S,axis=0)
            ok=(S>=0).all(0)&(S<=99).all(0)&(S==np.floor(S)).all(0)&(d>=0).all(0)&(d<=3).all(0)&(S[-1]!=S[0])
        for i in np.nonzero(ok)[0]: res.append((hex(base+al+8*int(i)),S[:,i].tolist()))
for r in res: print(r)
