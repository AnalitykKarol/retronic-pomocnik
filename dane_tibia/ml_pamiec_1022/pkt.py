from s import q
import json
r1=q(cmd="bajty",regex=r"\xa1([\x0a-\x28][\x00-\x63]){7}",limit=100)["adresy"]
print("A1 skille:",r1)
r2=q(cmd="bajty",regex=r"\xa0\xaf\x00\xaf\x00",limit=100)["adresy"]
print("A0 staty hp175:",r2)
res={}
for a in r1+r2:
    x=int(a,16)
    b=bytes.fromhex(q(cmd="hexdump",adres=hex(x),dlugosc=32)["hex"])
    res[a]=b.hex(); print(a,b.hex(" "))
json.dump({"A1":r1,"A0":r2,"bytes":res},open("pakiety.json","w"))
