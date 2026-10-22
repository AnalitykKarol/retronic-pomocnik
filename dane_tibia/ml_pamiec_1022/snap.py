import json,time
from s import q
base=0xb599090; start=base-0x1000; ln=0x1400
for i in range(14):
    g=q(cmd="gracz")["gracz"]
    b=bytes.fromhex(q(cmd="hexdump",adres=hex(start),dlugosc=ln)["hex"])
    t=time.strftime("%H%M%S")
    open(f"zrzut_{t}.bin","wb").write(b)
    open(f"zrzut_{t}.json","w").write(json.dumps({"start":hex(start),"gracz":g}))
    print(t,g["exp"],g["procent"],flush=True)
    time.sleep(30)
