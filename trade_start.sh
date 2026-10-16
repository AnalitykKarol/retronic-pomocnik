#!/usr/bin/env bash
# Włącza ogłoszenia Trade i odpowiedzi priv: mózg w trybie --bez-ruchu (postać stoi w depo).
cd "$(dirname "$(readlink -f "$0")")" || exit 1
if pgrep -f "^python3 .*mozg.py .*--bez-ruchu" > /dev/null; then
    echo "Już działa: PID $(pgrep -f "^python3 .*mozg.py .*--bez-ruchu" | tr '\n' ' ')"
    exit 1
fi
mkdir -p logi
RETRONIC_TELEMETRIA=1 setsid nohup python3 -I -u mozg.py --tryb skrypt --model haiku --trasa stoj_trade --potwory "Troll,Bear,Swamp Troll,Frost Troll,Rat" --prog-hp 30 --bez-ruchu > logi/mozg-stdout-$(date +%m%d-%H%M).log 2>&1 < /dev/null &
sleep 1
echo "Wystartowano: PID $(pgrep -f "^python3 .*mozg.py .*--bez-ruchu" | tr '\n' ' ')"
