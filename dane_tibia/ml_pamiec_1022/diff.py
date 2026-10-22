import struct,glob
fs=sorted(glob.glob("zrzut_*.bin")); 
bs=[open(f,"rb").read() for f in fs]
print(len(fs),"zrzutow",fs[0],fs[-1])
a,b=bs[0],bs[-1]
for o in range(0,len(a)-3,4):
    vs=[struct.unpack_from("<i",x,o)[0] for x in bs]
    if len(set(vs))>1:
        print(f"{o-0x1000:+#06x}",vs[:2],"...",vs[-1], "n_zm=",len(set(vs)))
