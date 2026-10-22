import socket, json, sys
def q(**z):
    s=socket.socket(socket.AF_UNIX); s.connect("/run/user/1000/retronic-odchyd.sock")
    s.sendall((json.dumps(z)+"\n").encode()); b=b""
    while not b.endswith(b"\n"):
        c=s.recv(1<<20)
        if not c: break
        b+=c
    return json.loads(b)
if __name__=="__main__":
    print(q(cmd="gracz"))
