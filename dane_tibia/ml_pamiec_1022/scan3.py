from s import q
import struct
rx=r"([\x0a-\x0e]\x00\x00\x00){7}"
r=q(cmd="bajty",regex=rx,limit=400)["adresy"]
al=[a for a in r if int(a,16)%4==0]
print(len(r),len(al))
out=[]
for a in al:
    x=int(a,16)
    b=bytes.fromhex(q(cmd="hexdump",adres=hex(x-32),dlugosc=32+28+64)["hex"])
    w=struct.unpack("<%di"%(len(b)//4),b)
    out.append((a,w))
    print(a,w[8:8+7],"| after:",w[15:23],"| before:",w[:8])
