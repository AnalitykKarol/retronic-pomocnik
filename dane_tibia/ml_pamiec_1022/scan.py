from s import q
import sys,json
P=r"[\x07-\x1e]\x00\x00\x00[\x00-\x63]\x00\x00\x00"
for name,rx in [("pary7",P*7),("trojki7",r"([\x07-\x1e])\x00\x00\x00\1\x00\x00\x00[\x00-\x63]\x00\x00\x00"*7)]:
    try:
        r=q(cmd="bajty",regex=rx,limit=200)
    except Exception as e:
        print(name,"blad",e); continue
    print(name,r if len(str(r))<3000 else str(r)[:3000])
