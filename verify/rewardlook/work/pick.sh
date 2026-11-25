#!/usr/bin/env bash
# rewardlook lab: one reward through the real Rewards list and the look window, then placed by a posted click.
#   pick.sh <rewards row> <look row> <cam x> <cam z> <tag>
# Rows are 0-based list rows (y = 158 + 14 * row). Run from verify/rewardlook/work with SC3_PID set.
set -e
row=$1; look=$2; cx=$3; cz=$4; tag=$5
export PYTHONDONTWRITEBYTECODE=1
is_open() {   # the Rewards list's picture box (300,140) is near white; the map there is green / blue
  py -3.12 lab.py dump "${tag}_open" > /dev/null
  py -3.12 -c "from PIL import Image; import sys; p = Image.open('fd/${tag}_open.png').convert('RGB').getpixel((300, 140)); sys.exit(0 if min(p) > 190 else 1)"
}
if [ "${OPEN:-1}" = 1 ]; then        # the real button: civic flyout (765,160) > "Premios y oportunidades" (717,216)
  for try in 1 2 3; do               # (the Frida hotkey job 0x3b never returned its result: lab trap, RESULTS.md)
    py -3.12 lab.py click 765 160    # the flyout button toggles, so check and retry
    sleep 1.5
    py -3.12 lab.py click 717 216
    sleep 2.5
    if is_open; then break; fi
    py -3.12 lab.py key 0x1b; sleep 1
    [ $try = 3 ] && { echo "Rewards list did not open"; exit 1; }
  done
fi
py -3.12 lab.py click 440 $((158 + 14 * row))
sleep 1.5
py -3.12 lab.py dump "${tag}_a_rewards"
py -3.12 lab.py click 556 480
sleep 4
py -3.12 lab.py click 440 $((158 + 14 * look))
sleep 1.5
py -3.12 lab.py dump "${tag}_b_looks"
py -3.12 lab.py click 556 480
sleep 4
py -3.12 lab.py cam "$cx" "$cz" 2 0 > /dev/null   # a recentre needs a zoom change (showcase trap)
py -3.12 lab.py cam "$cx" "$cz" 3 0 > /dev/null
py -3.12 lab.py move 400 300
sleep 1
py -3.12 lab.py dump "${tag}_c_tool"
py -3.12 lab.py click 400 300
sleep 2
py -3.12 lab.py move 650 60
sleep 1
py -3.12 lab.py dump "${tag}_d_placed"
grep -a "REWARDLOOK>\|CIVDLG> base" resize.log | tail -2
py -3.12 lab.py occ $((cx - 4)) $((cz - 4)) $((cx + 4)) $((cz + 4)) | py -3.12 -c "
import json, sys
for o in json.loads(sys.stdin.read())[0]['occ']:
    if o['key'][0] == '0x207edc0e': print('OCC', o['key'][2], int(o['key'][2], 16), 'type', o['type'], 'rect', o['rect'], 'rot', o['rot'])"
