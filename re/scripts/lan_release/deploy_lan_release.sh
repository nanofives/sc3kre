#!/usr/bin/env bash
# deploy_lan_release.sh - publish the staged SimCity 3000 dev build to the mini-server (copy of TD5RE's
# scripts/deploy_release.sh, adapted). Run from LIVING-PC (Git Bash) after stage_lan_release.py.
#
# Served by the existing td5re-files nginx (DockerApps, port 8088) from a subfolder, so the server needs no new
# service, port or firewall rule: http://mariano-server.local:8088/simcity/. TD5RE's deploy never deletes outside
# its re/assets, so the subfolder survives TD5RE publishes.
#
# Upload: first publish = the whole folder as one tar over SSH; later publishes = diff the local manifest against
# the server's and send only the changed files (then the manifest last, so a client never sees a manifest that
# names a file not uploaded yet).
set -euo pipefail

PI_HOST="${PI_HOST:-mariano@mariano-server.local}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519_rpi}"
REMOTE_DIR="${REMOTE_DIR:-/home/mariano/td5re-release/simcity}"
FILES_PORT="${FILES_PORT:-8088}"
# Staging folder: MAIN/stage/release since 2026-10-27 (re/sessions/CHILD_PROTOCOL.md section 6), the old sibling
# Proyectos/Simcity_release until it is moved.
DEFAULT_STAGE="$HOME/Desktop/Proyectos/Simcity/stage/release"
[ -d "$DEFAULT_STAGE" ] || DEFAULT_STAGE="$HOME/Desktop/Proyectos/Simcity_release"
STAGE="${1:-$DEFAULT_STAGE}"
SSH_OPTS="-o ConnectTimeout=15 -o BatchMode=yes -o StrictHostKeyChecking=accept-new"
SSH_CMD="ssh -i $SSH_KEY $SSH_OPTS"

[ -f "$STAGE/manifest.json" ] || { echo "[!] no manifest.json in $STAGE (run stage_lan_release.py first)"; exit 1; }

echo "[+] Pre-flight: $PI_HOST over SSH ..."
if ! $SSH_CMD "$PI_HOST" true 2>/dev/null; then
    echo "[!] $PI_HOST not reachable with $SSH_KEY. Nothing was published."
    exit 2
fi
$SSH_CMD "$PI_HOST" "mkdir -p '$REMOTE_DIR' && df -h '$REMOTE_DIR' | tail -1"

tmp_remote="$(mktemp)"; list="$(mktemp)"
trap 'rm -f "$tmp_remote" "$list"' EXIT
$SSH_CMD "$PI_HOST" "cat '$REMOTE_DIR/manifest.json' 2>/dev/null" > "$tmp_remote" || true

py -3.12 - "$(cygpath -w "$STAGE/manifest.json")" "$(cygpath -w "$tmp_remote")" "$(cygpath -w "$list")" <<'EOF'
import json, sys
local = json.load(open(sys.argv[1], encoding="utf-8"))
try:
    remote = {f["path"]: f["sha256"] for f in json.load(open(sys.argv[2], encoding="utf-8"))["files"]}
except Exception:
    remote = {}
changed = [f for f in local["files"] if remote.get(f["path"]) != f["sha256"]]
with open(sys.argv[3], "w", encoding="utf-8", newline="\n") as fh:
    fh.write("".join(f["path"] + "\n" for f in changed))
print("    %s publish: %d of %d file(s) to send, %.1f MB" % ("incremental" if remote else "first", len(changed),
      len(local["files"]), sum(f["size"] for f in changed) / 1e6))
EOF

if [ -s "$list" ]; then
    tar --hard-dereference -czf - -C "$STAGE" -T "$list" | $SSH_CMD "$PI_HOST" "tar -xzmf - -C '$REMOTE_DIR'"
fi
tar -czf - -C "$STAGE" manifest.json | $SSH_CMD "$PI_HOST" "tar -xzmf - -C '$REMOTE_DIR'"

echo "[+] Verifying through nginx on the Pi ..."
$SSH_CMD "$PI_HOST" "curl -fsS -o /dev/null http://localhost:$FILES_PORT/simcity/manifest.json && echo '    OK: http://mariano-server.local:$FILES_PORT/simcity/manifest.json'"
echo "[+] Done. On each PC: copy update.bat + sc3_update.ps1 into an empty folder (first time) and run update.bat."
