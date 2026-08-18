#!/usr/bin/env python3
"""Walk one located C++ vtable against its SDK header and name the slots mechanically.

Replaces eleven one-off per-class scripts that disagreed with each other. The disagreements
were not cosmetic: GZCOM_INTERFACE_CATALOGUE.md section 21a traces a false negative on
cISC3DirtBag (reported 0/0 comparable, ground truth 88.2%) directly to two different arity
extractors coexisting in the toolchain. This file keeps exactly one of each decision.

WHAT IS FIXED HERE, AND WHY
  * Arity extraction is STRICT / size-bounded ONLY. Disassemble exactly the `size` bytes that
    functions.csv records for the function, collect EVERY `ret` immediate in that range, and
    accept the arity only when the set is a singleton. The loose form (first `ret` inside a
    fixed 700- or 1200-byte window) flatters a class by marking real mismatches unmeasurable.
  * Argument width is 4 bytes per parameter, 8 for a BY-VALUE int64_t/uint64_t/double. Two of
    the old scripts used a flat 4 and would mis-predict any 64-bit-by-value signature.
  * The collision audit is BLOCKING. Four checks, and a non-empty result on any of them
    excludes the affected slots from the plan rather than printing a warning next to a name.
  * Same-name overload groups are REFUSED, never guessed. 15 of 15 groups examined in this
    project were permuted against the header (catalogue section 25d), so header order carries
    no information for them. They are listed for a separate hand-read pass.

CONFIDENCE
  Rows written here are C1: the slot is confirmed by position and arity, the BODY WAS NOT READ.
  C2 in this project means the decompilation was read, so using it here would both misreport
  the work and inflate the >=C2 gate metric. Every generated note says so in words.

The SDK headers are LGPL-2.1-or-later and are NOT vendored into this repository; --headers
points at a clone outside the tree. This file contains no SDK source, only the algorithm.

USAGE
  py -3.12 re/scripts/walk_vtable_class.py \
      --headers <clone>/src/gzcom-dll/include \
      --class cISC3DisasterLayer --module SIMDSTR.DLL --vtable 0x100325a0 \
      --prefix sc3_disasterlayer_ --subsystem simdstr-layer \
      --tail "(catalogue section 26)" [--skip-slots 7,8,9] [--batch-out b.txt] [--apply]

Without --apply nothing is written and the run is a report.
"""
import argparse
import csv
import io
import os
import re
import shutil
import struct
import sys
from collections import Counter, defaultdict

from capstone import Cs, CS_ARCH_X86, CS_MODE_32

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MD = Cs(CS_ARCH_X86, CS_MODE_32)

# A trivial field getter: `mov eax, [ecx + N] ; ret`. Recognised only to enrich the note with
# the struct offset -- it never affects whether a slot is named.
GET = re.compile(r'^mov eax, dword ptr \[ecx \+ (0x[0-9a-f]+)\]$')


# --------------------------------------------------------------------------- header parsing

def split_top(s):
    """Split a parameter list on top-level commas only, so `map<a,b>` stays one parameter."""
    out, depth, cur = [], 0, ''
    for ch in s:
        if ch in '(<':
            depth += 1
        elif ch in ')>':
            depth -= 1
        if ch == ',' and depth == 0:
            out.append(cur)
            cur = ''
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    return out


def arg_bytes(params):
    """Stack bytes the callee pops: 4 per parameter, 8 for a by-value 64-bit scalar."""
    if params in ('', 'void'):
        return 0
    return sum(
        8 if re.search(r'\b(int64_t|uint64_t|double)\b', p) and '*' not in p and '&' not in p
        else 4
        for p in split_top(params))


def parse_headers(inc):
    """{class: (base, [(method, arg_bytes, params, ret), ...])} over every .h in the directory."""
    classes = {}
    for fn in sorted(os.listdir(inc)):
        if not fn.endswith('.h'):
            continue
        src = io.open(os.path.join(inc, fn), encoding='utf-8', errors='replace').read()
        for m in re.finditer(
                r'^(?:template\s*<[^>]*>\s*)?class\s+(\w+)\s*(?::\s*public\s+([\w:<>]+))?\s*\{(.*?)^\};',
                src, re.S | re.M):
            name, base, body = m.group(1), m.group(2), m.group(3)
            meth = []
            for line in body.split('\n'):
                mm = re.match(r'\s*virtual\s+(.+?)\s+(\w+)\s*\((.*)\)\s*(const)?\s*(=\s*0)?\s*;',
                              line)
                if not mm:
                    continue
                ret, nm, params = mm.group(1), mm.group(2), mm.group(3).split('//')[0].strip()
                meth.append((nm, arg_bytes(params), params, ret.strip()))
            if base:
                base = re.sub(r'<.*>', '', base).strip()
            classes[name] = (base, meth)
    return classes


def chain(classes, name, seen=None):
    """Full method list in vtable order: base-class methods first, then the class's own."""
    seen = seen or set()
    if name in seen or name not in classes:
        return []
    seen.add(name)
    base, meth = classes[name]
    pre = [] if base in (None, 'cIGZUnknown') else chain(classes, base, seen)
    return pre + meth


def bases_of(classes, name):
    """Every ancestor of `name`, nearest first. Used for the prefix-inheritance exception."""
    out, cur = [], classes.get(name, (None, None))[0]
    while cur and cur != 'cIGZUnknown' and cur in classes:
        out.append(cur)
        cur = classes[cur][0]
    return out


# ------------------------------------------------------------------------------ PE + tracker

def load_pe(path):
    d = open(path, 'rb').read()
    q = struct.unpack_from('<I', d, 0x3c)[0]
    nsec = struct.unpack_from('<H', d, q + 6)[0]
    optsz = struct.unpack_from('<H', d, q + 20)[0]
    o = q + 24
    imagebase = struct.unpack_from('<I', d, o + 28)[0]
    st = o + optsz
    secs = []
    for i in range(nsec):
        s = st + i * 40
        nm = d[s:s + 8].rstrip(b'\0').decode(errors='replace')
        vs, va, rs, rp = struct.unpack_from('<IIII', d, s + 8)
        secs.append((nm, va, vs, rp, rs))
    return d, imagebase, secs


def make_r2o(imagebase, secs):
    def r2o(rva):
        rr = rva - imagebase
        for _nm, va, _vs, rp, rs in secs:
            if rs and va <= rr < va + rs:
                return rp + (rr - va)
        return None
    return r2o


def text_range(imagebase, secs):
    for nm, va, vs, _rp, _rs in secs:
        if nm == '.text':
            return imagebase + va, imagebase + va + vs
    raise SystemExit('no .text section')


def read_tracker(path, module):
    """{rva: size} for one module, plus the raw rows keyed by rva string."""
    sizes, named = {}, {}
    with io.open(path, encoding='utf-8', newline='') as fh:
        for r in csv.DictReader(fh):
            if r['module'] != module:
                continue
            try:
                v = int(r['rva'], 16)
            except ValueError:
                continue
            if r['size']:
                sizes[v] = int(r['size'])
            if r['new_name']:
                named[v] = (r['new_name'], r['confidence'])
    return sizes, named


# ---------------------------------------------------------------------------------- analysis

def strict_arity(data, r2o, sizes, v):
    """STRICT / size-bounded. Returns the arity, or None when it is not a singleton."""
    n = sizes.get(v)
    off = r2o(v) if n else None
    if not n or off is None:
        return None
    rets = set()
    for ins in MD.disasm(data[off:off + n], v):
        if ins.mnemonic == 'ret':
            rets.add(int(ins.op_str, 0) if ins.op_str else 0)
    return rets.pop() if len(rets) == 1 else None


def trivial_field(data, r2o, sizes, v):
    n = sizes.get(v)
    off = r2o(v) if n else None
    if not n or off is None or n > 10:
        return None
    ins = list(MD.disasm(data[off:off + n], v))
    if len(ins) >= 2:
        m = GET.match(f'{ins[0].mnemonic} {ins[0].op_str}')
        if m and ins[1].mnemonic == 'ret':
            return int(m.group(1), 16)
    return None


def snake(n):
    """CamelCase -> snake_case, keeping acronyms whole.

    A naive "underscore before every capital" splits GetAgeCohortEQ into get_age_cohort_e_q.
    Splitting only at lower/digit->upper and at upper->upper+lower boundaries gives
    get_age_cohort_eq, and leaves all 104 names already committed for
    cISC3CitySpriteCellMap byte-identical (measured, not assumed).
    """
    s = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', '_', n)
    s = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', '_', s)
    return s.lower()


# -------------------------------------------------------------------------------------- main

def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--headers', required=True, help='SDK include dir (outside this repo)')
    ap.add_argument('--class', dest='cls', required=True)
    ap.add_argument('--module', required=True, help='e.g. SIMDSTR.DLL, or SC3U.exe')
    ap.add_argument('--vtable', required=True, help='vtable RVA, hex')
    ap.add_argument('--prefix', required=True, help='e.g. sc3_disasterlayer_')
    ap.add_argument('--subsystem', required=True)
    ap.add_argument('--tail', default='', help='provenance sentence appended to every note')
    ap.add_argument('--skip-slots', default='', help='comma list of slots to leave unnamed')
    ap.add_argument('--batch-out', default='',
                    help='write a verify_worker_rows.py batch (rva,subsystem,confidence,'
                         'new_name,evidence)')
    ap.add_argument('--root', default=ROOT)
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args(argv[1:])

    base_rva = int(a.vtable, 16)
    skip_slots = {int(x) for x in a.skip_slots.split(',') if x.strip()}
    tracker = os.path.join(a.root, 'functions.csv')
    binpath = os.path.join(a.root, 'original', 'modules', a.module)
    if not os.path.exists(binpath):
        binpath = os.path.join(a.root, 'original', a.module)
    if not os.path.exists(binpath):
        raise SystemExit(f'binary not found: {a.module}')

    classes = parse_headers(a.headers)
    if a.cls not in classes:
        raise SystemExit(f'{a.cls} not found in {a.headers}')
    sigs = chain(classes, a.cls)
    ancestors = bases_of(classes, a.cls)

    data, imagebase, secs = load_pe(binpath)
    r2o = make_r2o(imagebase, secs)
    tlo, thi = text_range(imagebase, secs)
    sizes, named = read_tracker(tracker, a.module)

    print(f'=== {a.cls} -> {a.module} vtable 0x{base_rva:08x} ===')
    print(f'chain: {" <- ".join([a.cls] + ancestors) if ancestors else a.cls}')
    print(f'{len(sigs)} declared methods -> slots 3..{len(sigs) + 2} ({len(sigs) + 3} total)')

    # ---- read the slots -------------------------------------------------------------------
    slots = {}
    nontext = []
    for k, (name, nb, params, ret) in enumerate(sigs):
        s = k + 3
        off = r2o(base_rva + s * 4)
        if off is None:
            raise SystemExit(f'slot {s} is outside the image')
        v = struct.unpack_from('<I', data, off)[0]
        if not (tlo <= v < thi):
            nontext.append(s)
        slots[s] = (name, nb, params, ret, v)

    if nontext:
        print(f'!! {len(nontext)} slot(s) do NOT hold a .text pointer: {nontext[:12]}')
        print('   the vtable is shorter than the chain, or the base address is wrong. STOP.')
        return 1

    # ---- arity tally, so the location can be cross-checked a second way --------------------
    ok = mis = unmeas = 0
    mismatches = []
    for s, (name, nb, params, ret, v) in sorted(slots.items()):
        act = strict_arity(data, r2o, sizes, v)
        if act is None:
            unmeas += 1
        elif act == nb:
            ok += 1
        else:
            mis += 1
            mismatches.append((s, name, nb, act))
    comp = ok + mis
    pct = (100.0 * ok / comp) if comp else 0.0
    print(f'arity (STRICT, size-bounded): {ok} OK, {mis} MISMATCH, {unmeas} unmeasurable '
          f'-> {ok}/{comp} = {pct:.1f}%')
    for s, name, want, got in mismatches:
        print(f'   slot {s:3d} {name:<42} want 0x{want:x}  got 0x{got:x}')

    # ---- BLOCKING collision audit ---------------------------------------------------------
    print('\n=== collision audit (blocking) ===')
    namec = Counter(n for n, _, _, _, _ in slots.values())
    overloads = {k: c for k, c in namec.items() if c > 1}
    print(f'  1. duplicate METHOD NAMES in the header: {overloads or "none"}')
    if overloads:
        print('     -> refused, not guessed: 15 of 15 overload groups in this project were')
        print('        permuted against header order (catalogue section 25d). Resolve by reading')
        print('        bodies -- arity, then struct-read vs vtable-call, then callee arity.')

    byimpl = defaultdict(list)
    for s, (n, nb, p, r, v) in slots.items():
        byimpl[v].append(s)
    shared = {v: ss for v, ss in byimpl.items() if len(ss) > 1}
    print(f'  2. implementations shared by >1 slot: {len(shared)}')
    for v, ss in sorted(shared.items()):
        print(f'       0x{v:08x} <- slots {ss} ({", ".join(slots[s][0] for s in ss)})')

    notracked = sorted(s for s, (n, nb, p, r, v) in slots.items() if v not in sizes)
    print(f'  3. slots whose impl has NO functions.csv row: {len(notracked)} {notracked[:12]}')

    # Prefix inheritance: another interface legitimately resolving to THIS vtable is expected
    # when one derives from the other (catalogue section 23, cISC3CityView / cISC3CityViewIso).
    # A shared address between UNRELATED classes would be an error instead.
    prefixes = [c for c in classes
                if c != a.cls and re.match(r'^cIS(C3|CN|S)', c)
                and chain(classes, c) and chain(classes, c) == sigs[:len(chain(classes, c))]]
    print(f'  4. interfaces whose chain is a PREFIX of this one (expected to share the vtable): '
          f'{prefixes or "none"}')

    # ---- compare against names already in the tracker --------------------------------------
    agree = disagree = 0
    disagreements = []
    for s, (name, nb, params, ret, v) in sorted(slots.items()):
        if v in named and named[v][0].startswith(a.prefix):
            want = f'{a.prefix}{snake(name)}'
            if named[v][0] == want:
                agree += 1
            else:
                disagree += 1
                disagreements.append((s, named[v][0], want))
    print(f'\nexisting rows under {a.prefix}*: {agree} agree with the header-derived name, '
          f'{disagree} disagree')
    for s, have, want in disagreements:
        print(f'   slot {s:3d} tracker={have}  derived={want}')

    # ---- build the plan --------------------------------------------------------------------
    plan = {}
    sk = Counter()
    for s, (name, nb, params, ret, v) in sorted(slots.items()):
        rv = '0x%08x' % v
        if s in skip_slots:
            sk['explicitly skipped'] += 1
            continue
        if name in overloads:
            sk['overload group (refused)'] += 1
            continue
        if len(byimpl[v]) > 1:
            sk['shared implementation'] += 1
            continue
        if v not in sizes:
            sk['no functions.csv row'] += 1
            continue
        if v in named:
            sk['already named'] += 1
            continue
        act = strict_arity(data, r2o, sizes, v)
        fld = trivial_field(data, r2o, sizes, v)
        bits = [f'vtable slot {s} = {a.cls}::{name}({params})']
        if ret and ret != 'void':
            bits.append(f'returns {ret}')
        bits.append(f'expected ret 0x{nb:x}' + (
            f', actual 0x{act:x}' if act is not None
            else ', actual unmeasurable (no singleton ret in the tracked body)'))
        if fld is not None:
            bits.append(f'trivial accessor reading +0x{fld:x}')
        bits.append(f'{sizes[v]} bytes')
        plan[rv] = (f'{a.prefix}{snake(name)}', a.subsystem, '; '.join(bits))

    print(f'\nplan: {len(plan)} new rows')
    for k, c in sorted(sk.items()):
        print(f'   skipped {c:3d}  {k}')

    dupp = {k: c for k, c in Counter(n for n, _, _ in plan.values()).items() if c > 1}
    print(f'   duplicate generated names: {dupp or "none"}')
    if dupp:
        print('   -> BLOCKING: two slots would receive the same name. Nothing written.')
        return 1

    bad = sorted(n for n, _, _ in plan.values() if not re.match(r'^sc3_[a-z0-9]+_[a-z0-9_]+$', n))
    if bad:
        print(f'   -> BLOCKING: {len(bad)} name(s) fail verify_worker_rows.py NAME_OK: {bad[:6]}')
        return 1

    # ---- write ------------------------------------------------------------------------------
    tail = f' [CONFIRMED @ %s] ({a.tail} Named MECHANICALLY from the SDK header by slot ' \
           'position -- the slot is confirmed by position and arity, the body has NOT been read)'
    with io.open(tracker, encoding='utf-8', newline='') as fh:
        rows = list(csv.DictReader(fh))
    fields = list(rows[0].keys())
    hit = 0
    for r in rows:
        if r['module'] == a.module and r['rva'] in plan:
            n, sub, note = plan[r['rva']]
            r['new_name'], r['subsystem'], r['confidence'] = n, sub, 'C1'
            r['notes'] = note + (tail % r['rva'])
            hit += 1
    print(f'matched {hit}/{len(plan)} planned rows in functions.csv')
    if hit != len(plan):
        print('   -> BLOCKING: a planned row did not match. Nothing written.')
        return 1

    if a.batch_out and plan:
        with io.open(a.batch_out, 'w', encoding='utf-8', newline='') as fh:
            for rv, (n, sub, note) in sorted(plan.items()):
                fh.write(f'{rv},{sub},C1,{n},"{note}"\n')
        print(f'batch written: {a.batch_out}')

    if a.apply:
        # functions.csv is CRLF; csv writes \r\n by default and newline='' stops any doubling.
        bak = os.path.join(os.path.dirname(a.batch_out or tracker),
                           f'functions.csv.bak_{a.cls}')
        shutil.copy2(tracker, bak)
        with io.open(tracker, 'w', encoding='utf-8', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=fields, quoting=csv.QUOTE_ALL)
            w.writeheader()
            w.writerows(rows)
        print(f'APPLIED {len(rows)} rows (backup: {bak})')
    else:
        print('DRY RUN -- nothing written')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
