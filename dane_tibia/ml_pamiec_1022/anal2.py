import numpy as np,json
Z=[np.load(f"full_{t}.npz") for t in "ABC"]
out=[]
for k in Z[0].files:
    if k not in Z[1].files or k not in Z[2].files: continue
    a,b,c=[z[k].view("<i4") for z in Z]
    ok=(a>=0)&(a<=99)&(b>=a)&(c>=b)&(b-a<=2)&(c-b<=2)&((c!=a))
    idx=np.nonzero(ok)[0]
    base=int(k,16)
    cs=set(idx.tolist())
    for i in idx:
        # neighbor level constant 7..40 within +-4 words
        nb=[j for j in range(-4,5) if j and 0<=i+j<len(a) and a[i+j]==b[i+j]==c[i+j] and 7<=a[i+j]<=40]
        cl=[j for j in range(-12,13) if j and (i+j) in cs]
        out.append((base+4*int(i),int(a[i]),int(b[i]),int(c[i]),nb,cl))
print(len(out))
json.dump(out,open("kand_full.json","w"))
# najlepsze: sasiedni poziom i co najmniej jeden inny kandydat w klastrze
best=[o for o in out if o[4] and o[5]]
print(len(best))
for o in best[:80]: print(hex(o[0]),o[1:4],o[4],o[5])
