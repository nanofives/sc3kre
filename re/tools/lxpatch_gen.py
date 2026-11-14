"""Regenerate the patch data block of re/scripts/sc3mods_patch.sh from the real sc3mods_patch.ps1 output.

For each stock SC3U.exe build this runs the .ps1 on a COPY, compares the result with the input and records:
  - the few header byte ranges that change inside the original file length,
  - the tail appended after the original length (padding + the .sc3mod section),
  - the SHA-256 of the stock build and of the patched result.
The shell script carries that as data (printf octal escapes + dd), so it needs no PE logic of its own.

    py -3.12 re/tools/lxpatch_gen.py [--stock 2.0.0.3=path] [--stock 2.0.949=path] [--check]

--check regenerates in memory and exits 1 when the block in the .sh is out of date.
Run it again whenever sc3mods_patch.ps1 changes. Needs pwsh. Never run at the player's end.
"""
import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PS1 = ROOT / 're' / 'scripts' / 'sc3mods_patch.ps1'
SH = ROOT / 're' / 'scripts' / 'sc3mods_patch.sh'
BEGIN, END = '# BEGIN GENERATED', '# END GENERATED'

# the main checkout holds the (gitignored) stock exes; a worktree has none
def find_original(rel: str) -> Path:
    for base in [ROOT] + list(ROOT.parents):
        p = base / rel
        if p.is_file():
            return p
    raise SystemExit(f'stock exe not found: {rel}')

BUILDS = [  # (build name, shell id, relative path)
    ('2.0.0.3', 'v2003', 'original/SC3U.exe'),
    ('2.0.949', 'v2949', 'original/gog_2.0.949/Apps/SC3U.exe'),
]
# the anchor hash of 2.0.0.3 is listed in the .ps1 in upper case: read both from it so they cannot drift
def ps1_anchors() -> dict:
    out = {}
    for line in PS1.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if len(line) > 70 and line.startswith("'") and "' = '" in line:
            h, name = line.split("' = '")
            out[name.rstrip("'")] = h.strip("'").lower()
    return out


def octal(b: bytes) -> str:
    return ''.join('\\%03o' % x for x in b)


def run_ps1(stock: Path, work: Path) -> bytes:
    d = work / stock.parent.name
    d.mkdir(parents=True, exist_ok=True)
    exe = d / 'SC3U.exe'
    shutil.copyfile(stock, exe)
    r = subprocess.run(['pwsh', '-NoProfile', '-File', str(PS1), '-Apps', str(d)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f'.ps1 failed on {stock}:\n{r.stdout}\n{r.stderr}')
    return exe.read_bytes()


def diff_ranges(a: bytes, b: bytes, gap: int = 8):
    """Ranges (start, end) where b differs from a over len(a), neighbours closer than `gap` merged."""
    idx = [i for i in range(len(a)) if a[i] != b[i]]
    rng = []
    for i in idx:
        if rng and i - rng[-1][1] <= gap:
            rng[-1][1] = i + 1
        else:
            rng.append([i, i + 1])
    return rng


def printf_lines(data: bytes, indent: str, target: str) -> list:
    lines = []
    for i in range(0, len(data), 48):
        lines.append(f"{indent}printf '{octal(data[i:i + 48])}' {target}")
    return lines


def build_block() -> str:
    anchors = ps1_anchors()
    work = Path(tempfile.mkdtemp(prefix='lxpatch_gen_'))
    try:
        info, funcs = [], []
        for name, sid, rel in BUILDS:
            stock = find_original(rel).read_bytes()
            sha = hashlib.sha256(stock).hexdigest()
            assert anchors[name] == sha, f'{name}: .ps1 anchor {anchors[name]} != file {sha}'
            tmp = work / sid
            tmp.mkdir()
            src = tmp / 'SC3U.exe'
            src.write_bytes(stock)
            out = run_ps1(src, work / ('run_' + sid))
            assert len(out) > len(stock)
            psha = hashlib.sha256(out).hexdigest()
            rngs = diff_ranges(stock, out[:len(stock)])
            tail = out[len(stock):]
            info.append((name, sid, sha, psha))
            f = [f'apply_{sid}() {{   # {name}: {len(rngs)} header ranges + {len(tail)} appended bytes']
            for s, e in rngs:
                f.append(f'    # {e - s} bytes at {s}')
                f.append(f'    printf \'{octal(out[s:e])}\' | dd of="$1" bs=1 seek={s} conv=notrunc 2>/dev/null')
            f.append(f'    # appended tail, {len(tail)} bytes (padding + the .sc3mod section)')
            f += printf_lines(tail, '    ', '>> "$1"')
            f.append('}')
            funcs.append('\n'.join(f))
        L = ['build_info() {   # $1 = SHA-256 -> BUILD, ID, PATCHED_SHA; fails when it is not a stock build',
             '    case "$1" in']
        for name, sid, sha, psha in info:
            L.append(f'        {sha}) BUILD={name}; ID={sid}; PATCHED_SHA={psha} ;;')
        L += ['        *) return 1 ;;', '    esac', '    return 0', '}', 'apply_patch() { "apply_$1" "$2"; }']
        return '\n'.join(L) + '\n' + '\n'.join(funcs) + '\n'
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()
    block = build_block()
    text = SH.read_bytes().decode('utf-8')
    i, j = text.index(BEGIN), text.index(END)
    new = text[:i + len(BEGIN)] + '\n' + block + text[j:]
    if args.check:
        sys.exit(0 if new == text else 1)
    SH.write_bytes(new.encode('utf-8'))   # bytes: keep LF
    print(f'wrote {SH} ({len(block.splitlines())} generated lines)')


if __name__ == '__main__':
    main()
