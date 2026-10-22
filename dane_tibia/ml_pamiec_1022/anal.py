import numpy as np,glob,json
fs=sorted(glob.glob("heap_*.bin")); print(fs)
A=[np.fromfile(f,dtype="<i4") for f in fs]
lo=0x0a000000
st=np.stack(A)            # snaps x words
chg=(st!=st[0]).any(axis=0)
inr=((st>=0)&(st<=99)).all(axis=0)
mono=(np.diff(st.astype(np.int64),axis=0)>=0).all(axis=0)
small=((st.max(axis=0)-st.min(axis=0))<=5)
c=np.nonzero(chg&inr&mono&small)[0]
print("kandydaci pct:",len(c))
res=[]
for i in c:
    if i<3: continue
    lvl=st[0,i-1]; base=st[0,i-2]
    ok_pair = (7<=lvl<=40) and (st[:,i-1]==lvl).all()
    ok_tri = ok_pair and base==lvl
    if ok_pair:
        res.append((hex(lo+4*int(i)),int(lvl),bool(ok_tri),st[:,i].tolist()))
for r in res: print(r)
json.dump(res,open("kandydaci_pct.json","w"))
