from s import q
import struct
L=r"[\x07-\x28]\x00"; P=r"[\x00-\x63]\x00"
pat={
 "u16_pary":(L+P)*7,
 "u16_trojki":(r"([\x07-\x28])\x00\1\x00"+P)*7,
 "u16_trojkiLBP_any":(L+L+P)*7,
 "i32_pary_LP_0_nonconst":(r"[\x07-\x28]\x00\x00\x00[\x00-\x63]\x00\x00\x00")*7,
 "u8_pary":(r"[\x07-\x28][\x00-\x63]")*7,
}
for n,rx in pat.items():
    r=q(cmd="bajty",regex=rx,limit=300)["adresy"]
    r=[a for a in r if int(a,16)%2==0]
    print(n,len(r),r[:25],flush=True)
