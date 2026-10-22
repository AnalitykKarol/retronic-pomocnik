from s import q
import time
for N in (7,8,9,10,11,12,13):
    rest=".{%d}"%(4*(N-7)) if N>7 else ""
    lvl=r"([\x07-\x1e])\x00\x00\x00"*7
    back="".join(r"\%d\x00\x00\x00"%i for i in range(1,8))
    pct=r"[\x00-\x63]\x00\x00\x00"*7
    rx=lvl+rest+back+rest+pct
    t=time.time()
    r=q(cmd="bajty",regex=rx,limit=100)
    print(N,r,round(time.time()-t,1),flush=True)
