#!/bin/bash
# lateguard batch, run inside one test slot: control (unguarded 7c0dfcd DLLs, unpatched exe), then the patched exe
# with the guarded DLLs from Apps (player path), then the patched exe with SC3MODS_DIR (test-harness path) while the
# same mods also sit in Apps.
set -u
P=/c/Users/maria/Desktop/Proyectos
WT=$P/Simcity_wt_lateguard
U=$P/Simcity_stock_lateguard/Apps
PA=$P/Simcity_stock_lateguard_p/Apps
MODS="sc3mods sc3resize sc3bigcity sc3overscroll sc3simrun sc3perf sc3netmod sc3undo"
D=$WT/verify/lateguard/data
cd "$WT" || exit 1

echo "[1/3] control: unpatched exe + 7c0dfcd (unguarded) DLLs in Apps"
for m in $MODS; do cp "$WT/re/harness/inst_lateguard_ctl/$m.dll" "${U:?}/"; done
rm -f "${U:?}"/sc3*.log
py -3.12 verify/lateguard/stock_run.py --tree "$P/Simcity_stock_lateguard" --out "$D/unpatched_control" --seconds 30 --grab-at 20 --arg=-intro:off
mkdir -p "$D/unpatched_control/applogs"; cp "${U:?}"/sc3*.log "$D/unpatched_control/applogs/" 2>/dev/null
cp "${U:?}/SC3U_stkdmp.txt" "$D/unpatched_control/" 2>/dev/null
for m in $MODS; do cp "$WT/re/harness/inst_lateguard/$m.dll" "${U:?}/"; done      # back to guarded

echo "[2/3] patched exe, guarded mods loaded from Apps (player path), Frankfurt"
rm -f "${PA:?}"/sc3*.log
py -3.12 verify/lateguard/stock_run.py --tree "$P/Simcity_stock_lateguard_p" --out "$D/patched_apps" --plain --seconds 60 --grab-at 45 --arg=-intro:off --city "$P/Simcity_stock_lateguard_p/Cities/Frankfurt, Germany.sc3"
mkdir -p "$D/patched_apps/applogs"; cp "${PA:?}"/sc3*.log "$D/patched_apps/applogs/" 2>/dev/null

echo "[3/3] patched exe, SC3MODS_DIR=inst_lateguard (harness path), the same mods also in Apps"
INST=$WT/re/harness/inst_lateguard
rm -f "${PA:?}"/sc3*.log "${INST:?}"/sc3*.log
py -3.12 verify/lateguard/stock_run.py --tree "$P/Simcity_stock_lateguard_p" --out "$D/patched_dir" --plain --seconds 60 --grab-at 45 --arg=-intro:off --env "SC3MODS_DIR=C:\\Users\\maria\\Desktop\\Proyectos\\Simcity_wt_lateguard\\re\\harness\\inst_lateguard" --env SC3MODS_MULTI=1 --city "$P/Simcity_stock_lateguard_p/Cities/Frankfurt, Germany.sc3"
mkdir -p "$D/patched_dir/applogs" "$D/patched_dir/instlogs"; cp "${PA:?}"/sc3*.log "$D/patched_dir/applogs/" 2>/dev/null; cp "${INST:?}"/sc3*.log "$D/patched_dir/instlogs/" 2>/dev/null
echo "[3/3] batch done"
