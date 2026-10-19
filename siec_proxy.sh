#!/bin/bash
# Uruchamia polecenie w osobnej sieci (bez roota), której CAŁY ruch TCP idzie przez proxy SOCKS5 (Railway `retronic-proxy`).
# Użycie: siec_proxy.sh <polecenie> [argumenty...]   np.  siec_proxy.sh curl -s https://ifconfig.me
# Etap 2 z INSTANCJE.md (test 18.10). Nie dotyka głównej instancji: owija się tylko to, co dostanie jako argumenty.
#
# Jak działa:
#  - host: socat wystawia gniazdo Unix i łączy je z proxy (TCP), bo w nowej sieci nie ma łącza do internetu;
#  - nowa sieć (unshare -Urn): lo + tun0, domyślna trasa przez tun0, tun2socks mówi SOCKS5 do 127.0.0.1:1080,
#    a tamtejszy socat przerzuca to gniazdem Unix na hosta (brak pętli routingu);
#  - polecenie startuje w zagnieżdżonej przestrzeni użytkownika jako ten sam uid/gid co na hoście (wine wymaga właściciela prefiksu).
# DNS: bez UDP, idzie przez nss-resolve (gniazdo systemd-resolved). Poza TCP nic nie wychodzi (UDP/ICMP odpadają).
# Hasło: PROXY_PASSWORD z env, potem wpis keyringu instancji (service=retronic-proxy instance=$RETRONIC_ID),
# potem wspólny (service=retronic-proxy user=retronic); nigdy z repo.
# Konfiguracja: RETRONIC_PROXY_HOST, RETRONIC_PROXY_PORT, RETRONIC_PROXY_USER.
# Cofnięcie: nie używaj tego skryptu (uruchom_gre.sh sięga po niego tylko przy RETRONIC_PROXY=1).
set -u

[ "$#" -ge 1 ] || { echo "użycie: $0 <polecenie> [args...]" >&2; exit 2; }
HOST="${RETRONIC_PROXY_HOST:-shortline.proxy.rlwy.net}"
PORT="${RETRONIC_PROXY_PORT:-48152}"
PUSER="${RETRONIC_PROXY_USER:-retronic}"
T2S="${RETRONIC_TUN2SOCKS:-$HOME/.local/share/retronic-proxy/bin/tun2socks}"
[ -x "$T2S" ] || { echo "brak $T2S" >&2; exit 1; }
PW="${PROXY_PASSWORD:-}"
[ -z "$PW" ] && [ -n "${RETRONIC_ID:-}" ] && PW="$(secret-tool lookup service retronic-proxy instance "$RETRONIC_ID" 2>/dev/null)"
[ -n "$PW" ] || PW="$(secret-tool lookup service retronic-proxy user retronic 2>/dev/null)"
[ -n "$PW" ] || { echo "brak hasła proxy (PROXY_PASSWORD albo keyring retronic-proxy)" >&2; exit 1; }
unset PROXY_PASSWORD

KAT="$(mktemp -d "${XDG_RUNTIME_DIR:-/tmp}/retronic-proxy.XXXXXX")"
SOCK="$KAT/proxy.sock"
cleanup() { [ -n "${RELAY_PID:-}" ] && kill "$RELAY_PID" 2>/dev/null; rm -rf "$KAT"; }
trap cleanup EXIT INT TERM

socat "UNIX-LISTEN:$SOCK,fork,mode=600" "TCP:$HOST:$PORT" &
RELAY_PID=$!
for _ in $(seq 1 50); do [ -S "$SOCK" ] && break; sleep 0.1; done
[ -S "$SOCK" ] || { echo "socat nie wystawił gniazda" >&2; exit 1; }

# hasło tylko w pliku 0600 w katalogu 0700 (nie w argumentach procesu, które widać w ps/pgrep)
SIEC_CONF="$KAT/t2s.yaml"
( umask 077; printf 'device: tun0\nproxy: socks5://%s:%s@127.0.0.1:1080\nloglevel: warn\n' "$PUSER" "$PW" > "$SIEC_CONF" )
export SIEC_SOCK="$SOCK" SIEC_T2S="$T2S" SIEC_CONF
export SIEC_UID="$(id -u)" SIEC_GID="$(id -g)"
unset PW

# w środku: root w przestrzeni użytkownika (mapowany na naszego uida), własna sieć
unshare -Urn --kill-child bash -c '
set -u
ip link set lo up
socat TCP-LISTEN:1080,bind=127.0.0.1,fork,reuseaddr "UNIX-CONNECT:$SIEC_SOCK" &
"$SIEC_T2S" --config "$SIEC_CONF" &
for _ in $(seq 1 50); do ip link show tun0 >/dev/null 2>&1 && break; sleep 0.1; done
ip link show tun0 >/dev/null 2>&1 || { echo "tun0 nie powstał" >&2; exit 1; }
ip addr add 198.18.0.1/15 dev tun0
ip link set tun0 up
ip route add default dev tun0
unshare -U --map-user="$SIEC_UID" --map-group="$SIEC_GID" -- "$@"
rc=$?
kill $(jobs -p) 2>/dev/null
exit $rc
' siec_proxy "$@"
