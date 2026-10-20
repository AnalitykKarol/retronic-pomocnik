#!/bin/bash
# Start klienta gry INSTANCJI (RETRONIC_ID=<id>): własny WINEPREFIX i katalog gry, gra jako potomek strażnika
# (socket retronic-<id>.sock). Wywołuje to sesja.sh w zagnieżdżonym sway; ręcznie zwykle niepotrzebne.
# Domyślna (jedyna dziś) gra startuje przez ../retronic.sh i tego pliku nie dotyka.
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
INST=$(python3 -I "$DIR/instancja.py" powloka) || exit 1; eval "$INST"
[ -n "$RETRONIC_ID" ] || { echo "uruchom_gre.sh: ustaw RETRONIC_ID (domyślna gra: ../retronic.sh)" >&2; exit 2; }
[ -d "$INST_PREFIX" ] && [ -d "$INST_GRA" ] || { echo "brak $INST_PREFIX lub $INST_GRA: najpierw ./nowa_instancja.sh $RETRONIC_ID" >&2; exit 1; }
export WINEPREFIX="$INST_PREFIX"
export WINEDEBUG=-all
# opcje klienta wymuszane przed startem (ustawienia_klienta.py: priv we własnych zakładkach)
python3 -I "$DIR/ustawienia_klienta.py" "$WINEPREFIX" || true
cd "$INST_GRA" || exit 1
EXE="${1:-RetronicGL.exe}"
[ -f "$EXE" ] || { echo "brak $INST_GRA/$EXE (nowa_instancja.sh kopiuje exe i dll)" >&2; exit 1; }
# RETRONIC_PROXY: cały ruch gry idzie przez proxy SOCKS5 (siec_proxy.sh, etap 2 sieci). Od 20.10 DOMYŚLNIE WŁĄCZONE dla
# każdej instancji (decyzja Karola D4, lekcja: Johny wystartował bez proxy z domowego IP); bez proxy tylko jawnym RETRONIC_PROXY=0.
# Tożsamość sprzętu instancji (SPEC_tozsamosc_sprzetu_1020.md): numer wolumenu C: tutaj (.windows-serial w prefiksie),
# MAC, machine-id i ukrycie numeru dysku w siec_proxy.sh (tylko na ścieżce z proxy). Cofnięcie: kopie *.bak-20261020-tozsamosc.
SIEC=()
if [ "${RETRONIC_PROXY:-1}" = "1" ]; then
    # stały profil (rozszerzenie (b) specu): proxy, oczekiwane IP; bez profilu albo przy kolizji z inną instancją = brak startu
    PROF=$(python3 -I "$DIR/profil.py" powloka "$INST_STAN") || { echo "uruchom_gre.sh: start wstrzymany (profil)" >&2; exit 1; }
    eval "$PROF"
    TOZ=$(python3 -I "$DIR/tozsamosc.py" powloka "$INST_STAN") || { echo "uruchom_gre.sh: błąd tożsamości instancji" >&2; exit 1; }
    eval "$TOZ"
    printf '%s\n' "$TOZ_VOLUME" > "$WINEPREFIX/drive_c/.windows-serial"
    SIEC=("$DIR/siec_proxy.sh")
else
    echo "uruchom_gre.sh: UWAGA instancja $RETRONIC_ID BEZ proxy (RETRONIC_PROXY=0), IP domowe" >&2
fi
if python3 -I -c 'import numpy' 2>/dev/null; then
    exec "${SIEC[@]}" python3 -I "$DIR/straznik.py" wine "$EXE"
fi
exec "${SIEC[@]}" wine "$EXE"
