#!/bin/bash
# Remmina z VNC do podglądu gier Retronic: obraz skalowany do okna, bot widzi stały ekran sesji (19.10). Na desktopie i laptopie.
# Użycie: bash narzedzia/remmina_podglad.sh  (hasło przez pkexec; przez ssh bez ekranu: najpierw sudo pacman -S --needed remmina libvncserver)
LOG=${XDG_STATE_HOME:-$HOME/.local/state}/retronic-remmina.log; mkdir -p "$(dirname "$LOG")"
exec > >(tee "$LOG") 2>&1
echo "== $(date '+%F %T') pacman (okienko hasła pkexec)"
pkexec pacman -S --needed --noconfirm remmina libvncserver || { notify-send -u critical "Remmina" "instalacja nieudana, log: $LOG"; exit 1; }
P=~/.local/share/remmina; mkdir -p "$P"
profil() { # nazwa port plik
  [ -e "$P/$3" ] && { echo "profil $3 już jest, zostawiam"; return; }
  cat > "$P/$3" <<PROF
[remmina]
name=Retronic $1
group=Retronic
protocol=VNC
server=127.0.0.1:$2
scale=1
quality=9
colordepth=32
viewonly=0
disableclipboard=0
showcursor=0
disableencryption=0
PROF
  echo "profil $P/$3 (port $2, skalowanie do okna)"
}
profil "Mastafian" 5901 retronic-mastafian.remmina
profil "Johny Dang" 5930 retronic-johny.remmina
echo "== wersje"; pacman -Q remmina libvncserver
ls /usr/lib/remmina/plugins/ | grep -i vnc
echo "Cofnięcie: pkexec pacman -Rns remmina libvncserver; rm $P/retronic-*.remmina"
notify-send "Remmina" "zainstalowana, profile Retronic Mastafian/Johny gotowe"
