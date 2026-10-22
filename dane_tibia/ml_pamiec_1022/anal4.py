import numpy as np,json,sys,collections
tags=sys.argv[1]
Z=[np.load(f"full_{t}.npz") for t in tags]
res=[]
for k in Z[0].files:
    if any(k not in z.files for z in Z): continue
    base=int(k,16)
    for nm,dt,sz in (("i32","<i4",4),("u16","<u2",2)):
        S=np.stack([z[k].view(dt).astype(np.int32) for z in Z])
        d=np.diff(S,axis=0)
        ok=(S[0]>=0)&(S[-1]<=99)&(S>=0).all(0)&(S<=99).all(0)&(d>=0).all(0)&(d<=3).all(0)&(S[-1]!=S[0])&((S[-1]-S[0])<=8)
        for i in np.nonzero(ok)[0]:
            nb=[j for j in range(-4,5) if j and 0<=i+j<S.shape[1] and (S[:,i+j]==S[0,i+j]).all() and 7<=S[0,i+j]<=40]
            res.append((base+sz*int(i),nm,S[:,i].tolist(),nb))
c=collections.Counter((r[1],tuple(r[2])) for r in res)
print(len(res))
rare=[r for r in res if c[(r[1],tuple(r[2]))]<=2]
print(len(rare))
json.dump(rare,open("rare_%s.json"%tags,"w"))
for r in rare:
    if r[3]: print(hex(r[0]),r[1],r[2],r[3])
