import json, os, socket, sys
G = os.path.join(os.environ["XDG_RUNTIME_DIR"], "retronic-pomocnik.sock")
def zapytaj(z):
    with socket.socket(socket.AF_UNIX) as s:
        s.connect(G); s.sendall((json.dumps(z) + "\n").encode())
        return json.loads(s.makefile("rb").readline())
if __name__ == "__main__":
    print(zapytaj(json.loads(sys.argv[1])))
