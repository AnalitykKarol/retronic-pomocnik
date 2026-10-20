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
# potem wpisy instancji z tym samym serwerem proxy (RETRONIC_PROXY_HASLO_Z z profil.py; Webshare: jedno hasło konta)
for _inna in ${RETRONIC_PROXY_HASLO_Z:-}; do
  [ -n "$PW" ] && break
  PW="$(secret-tool lookup service retronic-proxy instance "$_inna" 2>/dev/null)"
done
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
export SIEC_SOCK="$SOCK" SIEC_T2S="$T2S" SIEC_CONF SIEC_IP_OCZEKIWANE="${SIEC_IP_OCZEKIWANE:-}"
export SIEC_UID="$(id -u)" SIEC_GID="$(id -g)"
unset PW

# Tożsamość sprzętu (SPEC_tozsamosc_sprzetu_1020.md; ustawia uruchom_gre.sh): TOZ_MAC -> karta eth0 (tap) z tym MAC,
# TOZ_MACHINE_ID -> prywatny bind-mount /etc/machine-id (osobna przestrzeń montowania, system nietknięty),
# a przy dowolnej z nich systemowy D-Bus odcięty dla gry (wine nie czyta numeru dysku z UDisks2 -> WINEHDISK).
MONT=""
export SIEC_MAC="${TOZ_MAC:-}" SIEC_MID=""
if [ -n "${TOZ_MACHINE_ID:-}" ]; then
  SIEC_MID="$KAT/machine-id"; printf '%s\n' "$TOZ_MACHINE_ID" > "$SIEC_MID"; MONT="m"
fi
if [ -n "${TOZ_MAC:-}${TOZ_MACHINE_ID:-}" ]; then export DBUS_SYSTEM_BUS_ADDRESS="unix:path=/nonexistent"; fi
# D5: TOZ_USER -> prywatny /etc/passwd z tą nazwą dla naszego uida (wine bierze z niego GetUserName i C:\users\<nazwa>)
# oraz USER/LOGNAME gry; TOZ_HOST -> własna przestrzeń UTS z tą nazwą hosta (wine: nazwa komputera).
UTS=""
export SIEC_USER="${TOZ_USER:-}" SIEC_PASSWD="" SIEC_HOST="${TOZ_HOST:-}"
if [ -n "$SIEC_USER" ]; then
  SIEC_PASSWD="$KAT/passwd"
  awk -F: -v OFS=: -v u="$(id -u)" -v n="$SIEC_USER" '$3==u{$1=n;$5=n}1' /etc/passwd > "$SIEC_PASSWD"; MONT="m"
fi
[ -n "$SIEC_HOST" ] && UTS="u"

# w środku: root w przestrzeni użytkownika (mapowany na naszego uida), własna sieć
unshare -Urn$MONT$UTS --kill-child bash -c '
set -u
ip link set lo up
if [ -n "$SIEC_MID" ]; then mount --bind "$SIEC_MID" /etc/machine-id || { echo "machine-id: bind nieudany" >&2; exit 1; }; fi
if [ -n "$SIEC_PASSWD" ]; then mount --bind "$SIEC_PASSWD" /etc/passwd || { echo "passwd: bind nieudany" >&2; exit 1; }; fi
if [ -n "$SIEC_HOST" ]; then hostname "$SIEC_HOST" || { echo "hostname nieudany" >&2; exit 1; }; fi
if [ -n "$SIEC_MAC" ]; then
  ip tuntap add dev eth0 mode tap && ip link set eth0 address "$SIEC_MAC" && ip link set eth0 up \
    || { echo "eth0 (tap) z MAC nieudane" >&2; exit 1; }
fi
socat TCP-LISTEN:1080,bind=127.0.0.1,fork,reuseaddr "UNIX-CONNECT:$SIEC_SOCK" &
"$SIEC_T2S" --config "$SIEC_CONF" &
for _ in $(seq 1 50); do ip link show tun0 >/dev/null 2>&1 && break; sleep 0.1; done
ip link show tun0 >/dev/null 2>&1 || { echo "tun0 nie powstał" >&2; exit 1; }
ip addr add 198.18.0.1/15 dev tun0
ip link set tun0 up
ip route add default dev tun0
# SIEC_IP_OCZEKIWANE (profil instancji): IP wyjściowe sprawdzane w tej sieci PRZED startem polecenia; inne = brak startu
if [ -n "${SIEC_IP_OCZEKIWANE:-}" ]; then
  IPW=""
  for _ in 1 2 3; do IPW=$(curl -s --max-time 10 https://api.ipify.org) && [ -n "$IPW" ] && break; sleep 2; done
  case " $SIEC_IP_OCZEKIWANE " in
    *" $IPW "*) echo "siec_proxy: IP wyjściowe $IPW (zgodne z profilem)" >&2 ;;
    *) echo "siec_proxy: IP wyjściowe \"$IPW\" spoza profilu ($SIEC_IP_OCZEKIWANE), NIE startuję" >&2; kill $(jobs -p) 2>/dev/null; exit 1 ;;
  esac
fi
[ -n "$SIEC_USER" ] && set -- env USER="$SIEC_USER" LOGNAME="$SIEC_USER" "$@"
unshare -U --map-user="$SIEC_UID" --map-group="$SIEC_GID" -- "$@"
rc=$?
kill $(jobs -p) 2>/dev/null
exit $rc
' siec_proxy "$@"
