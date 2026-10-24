#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
case "$(uname -m)" in
    x86_64) ;;
    *) echo 'Skaner natywny wymaga x86_64; użyj zgodnego fallbacku NumPy.' >&2; exit 1 ;;
esac
tmp=$(mktemp "$root/native/skan_stworow.so.XXXXXX")
trap 'rm -f -- "$tmp"' EXIT HUP INT TERM
"${CC:-cc}" -std=c11 -O3 -Wall -Wextra -Werror -fPIC -shared \
    "$root/native/skan_stworow.c" -o "$tmp"
chmod 755 "$tmp"
mv -f -- "$tmp" "$root/native/skan_stworow.so"
echo "Zbudowano: $root/native/skan_stworow.so (ABI 1)"
