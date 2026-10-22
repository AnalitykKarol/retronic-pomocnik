import sys,time,json
from s import q
lo,hi,step=0x0a000000,0x0e000000,0x400000
tag=sys.argv[1]
out=bytearray(); t=time.time(); mapa=[]
a=lo
while a<hi:
    r=q(cmd="hexdump",adres=hex(a),dlugosc=step)
    b=bytes.fromhex(r["hex"]); mapa.append((hex(a),len(b)))
    if len(b)<step: b=b+bytes(step-len(b))
    out+=b; a+=step
open(f"heap_{tag}.bin","wb").write(out)
json.dump({"lo":hex(lo),"mapa":mapa,"gracz":q(cmd="gracz")["gracz"],"t":time.strftime("%H:%M:%S")},open(f"heap_{tag}.json","w"))
print(tag,time.strftime("%H:%M:%S"),round(time.time()-t,1),sum(1 for m in mapa if m[1]),"chunków czytelnych z",len(mapa))
