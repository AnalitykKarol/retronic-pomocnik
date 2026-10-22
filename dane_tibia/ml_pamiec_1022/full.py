import sys,time,json,numpy as np
from s import q
tag=sys.argv[1]; step=0x400000
t=time.time(); parts={}; 
for a in range(0,0x100000000,step):
    r=q(cmd="hexdump",adres=hex(a),dlugosc=step)
    if r.get("hex"):
        b=bytes.fromhex(r["hex"])
        if len(b)==step: parts[a]=b
np.savez(f"full_{tag}.npz",**{hex(a):np.frombuffer(b,np.uint8) for a,b in parts.items()})
print(tag,time.strftime("%H:%M:%S"),round(time.time()-t,1),len(parts),"chunks of 4MB",flush=True)
