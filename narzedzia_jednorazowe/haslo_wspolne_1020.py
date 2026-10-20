#!/usr/bin/env python3
"""Jednorazowo (20.10, decyzja Karola: jedno hasło Webshare dla wszystkich instancji): siec_proxy.sh, gdy instancja nie ma
własnego wpisu hasła w keyringu, bierze je z wpisu instancji na tym samym serwerze proxy (RETRONIC_PROXY_HASLO_Z z profil.py).
Uruchamia Karol (agentom edycja kodu czytającego keyring jest zablokowana):  python3 -I narzedzia_jednorazowe/haslo_wspolne_1020.py
Kopia: siec_proxy.sh.bak-20261020-haslo. Cofnięcie: przywróć kopię.
"""
import shutil
from pathlib import Path

plik = Path(__file__).resolve().parent.parent / "siec_proxy.sh"
s = plik.read_text()
znacznik = "RETRONIC_PROXY_HASLO_Z"
if znacznik in s:
    print("siec_proxy.sh: już poprawione, nic nie robię")
    raise SystemExit(0)
stara = '[ -n "$PW" ] || PW="$(secret-tool lookup service retronic-proxy user retronic 2>/dev/null)"'
if s.count(stara) != 1:
    raise SystemExit("siec_proxy.sh: nie znalazłem miejsca do zmiany, nic nie zmieniono")
nowa = ('# potem wpisy instancji z tym samym serwerem proxy (RETRONIC_PROXY_HASLO_Z z profil.py; Webshare: jedno hasło konta)\n'
        'for _inna in ${RETRONIC_PROXY_HASLO_Z:-}; do\n'
        '  [ -n "$PW" ] && break\n'
        '  PW="$(secret-tool lookup service retronic-proxy instance "$_inna" 2>/dev/null)"\n'
        'done\n' + stara)
kopia = plik.with_name("siec_proxy.sh.bak-20261020-haslo")
if not kopia.exists():
    shutil.copy2(plik, kopia)
plik.write_text(s.replace(stara, nowa, 1))
print("siec_proxy.sh poprawione: nowa instancja bierze hasło od instancji z tym samym proxy (kopia: siec_proxy.sh.bak-20261020-haslo)")
