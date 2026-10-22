import sys, struct, time
from s import q
base=0xb599090; start=base-0x400; ln=0xe00
g=q(cmd="gracz")["gracz"]
r=q(cmd="hexdump",adres=hex(start),dlugosc=ln)
b=bytes.fromhex(r["hex"]); tag=time.strftime("%H%M%S")
open(f"dump_{tag}.bin","wb").write(b)
open(f"dump_{tag}.json","w").write(__import__("json").dumps({"start":hex(start),"gracz":g}))
print(tag,g,len(b))
