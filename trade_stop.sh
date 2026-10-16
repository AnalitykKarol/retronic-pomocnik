#!/usr/bin/env bash
# Wyłącza ogłoszenia Trade i odpowiedzi priv: zabija TYLKO proces mozg.py z --bez-ruchu (gra, strażnik, sway, wine zostają).
pids=$(pgrep -f "^python3 .*mozg.py .*--bez-ruchu")
if [ -z "$pids" ]; then
    echo "Nie działa (brak mozg.py --bez-ruchu)."
    exit 0
fi
kill $pids
for _ in 1 2 3 4 5 6 7 8 9 10; do
    sleep 1
    pgrep -f "^python3 .*mozg.py .*--bez-ruchu" > /dev/null || { echo "Zatrzymano PID $pids"; exit 0; }
done
kill -9 $pids
echo "Zabito (SIGKILL) PID $pids"
