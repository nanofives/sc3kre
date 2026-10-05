#!/usr/bin/env python3
"""linux_match.py - pair SC3U Windows functions with Loki Linux demo functions (names come from .dynsym).

Inputs are FuncFeatures.java dumps (re/match_linux/win_<mod>.tsv, lin_<lib>.tsv):
    entry  name  size  callees(;)  strings(\\x1f)  consts(;)

Stage A - ANCHORS. A feature (a string, or a 32-bit constant) that occurs in exactly ONE Windows function
          and exactly ONE Linux function votes for that pair. A pair is accepted when it is the mutual best
          (each side's top-voted partner is the other) and has no conflicting vote.
Stage B - PROPAGATION (call graph, BinDiff-style). For every matched pair, take each side's callees that
          are still unmatched (internal functions only). If exactly one remains on each side, pair them.
          The same on callers. Iterate to a fixpoint. External imports never pair.
Stage C - HOLD-OUT CHECK (--holdout). Re-run with the constant anchors withheld, then score how many of the
          withheld constant anchors propagation re-derived identically. That is the precision estimate
          for propagated pairs; it is printed, never assumed.

Output: re/match_linux/pairs_<mod>.tsv  win_entry  lin_entry  lin_name  stage  evidence
Names produced here are [LINUX-HINT] until an SC3U-side witness confirms them (TOOLING_ADOPTION.md s4).

Usage:
    py re/tools/linux_match.py --win re/match_linux/win_simrci.tsv --lin re/match_linux/lin_libsimrci.tsv \\
        --out re/match_linux/pairs_simrci.tsv [--holdout]
"""
import argparse
import collections
import os
import random
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from read_vtables import PE  # noqa: E402

PIC_HELPERS = ("__i686.get_pc_thunk", "__x86.get_pc_thunk")


def strip_lib(name):
    """Drop the library namespace Ghidra puts on imports: Linux '<EXTERNAL>::cRZRandom::RandomUint32Uniform',
    Windows 'MSVCRT.DLL::strlen'. Without this the two builds share no FW: token at all (measured: 0 shared)."""
    head, sep, rest = name.partition("::")
    if sep and (head == "<EXTERNAL>" or head.upper().endswith((".DLL", ".SO", ".EXE"))):
        return rest
    return name


def load(path, fw=None):
    """fw: (framework_hashes, {hash: name}) from framework_names.py, or None."""
    fns = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            p = line.rstrip("\n").split("\t")
            if len(p) < 6:
                continue
            e, name, size, cal, strs, consts = p[:6]
            mhash = p[6] if len(p) > 6 else ""
            # imported library calls, normalised so MSVCRT (_sprintf, __imp__strtok) and glibc (sprintf) agree;
            # C++ runtime and GZ imports are skipped (operator new/delete etc. are everywhere and carry no identity)
            exts = set()
            for c in cal.split(";"):
                if c.startswith("EXT:"):
                    n = c[4:].lstrip("_").lower()
                    if n.startswith("imp_"):
                        n = n[4:].lstrip("_")
                    n = n.split("@")[0]
                    if n and n.isidentifier() and not n.startswith(("operator", "builtin", "rtti", "purecall",
                                                                      "eh_", "cxx", "except", "security", "chkstk")):
                        exts.add(n)
            fns[e] = dict(name=name, size=int(size or 0), exts=exts, mhash=mhash,
                          fw=set("FW:" + strip_lib(c[4:]) for c in cal.split(";") if c.startswith("EXT:")),
                          callees=[c for c in cal.split(";") if c and not c.startswith("EXT:")],
                          strs=set(s for s in strs.split("\x1f") if s),
                          consts=set(c for c in consts.split(";") if c))
    # GCC PIC helpers are called by nearly every Linux function; they carry no identity and would poison
    # the callee sets used for propagation.
    for e in [e for e, f in fns.items() if f["name"].startswith(PIC_HELPERS)]:
        del fns[e]
    callers = collections.defaultdict(set)
    for e, f in fns.items():
        for c in f["callees"]:
            if c in fns:
                callers[c].add(e)
    for e, f in fns.items():
        f["callers"] = callers.get(e, set())
        f["callees"] = set(c for c in f["callees"] if c in fns)
    if fw:
        # Windows: statically linked framework copies leave the callee graph (Linux only ever IMPORTS them) and,
        # when named, become shared FW:<name> tokens.
        hashes, names = fw
        # Only NAMED framework copies leave the graph. Measured on SIMRCI 2026-10-05: removing every multi-module
        # hash cut propagation 10 -> 1, because many shared hashes are template instantiations (vector, string)
        # that GCC ALSO instantiates inside each Linux library, i.e. internal calls on both sides. A name from the
        # Linux exe is what proves a copy is imported framework.
        fwfn = {e for e, f in fns.items() if f["mhash"] in names}
        for e, f in fns.items():
            for c in [c for c in f["callees"] if c in fwfn]:
                f["callees"].discard(c)
                n = names.get(fns[c]["mhash"])
                if n:
                    f["fw"].add("FW:" + n)
            f["callers"] -= fwfn
    return fns


def load_fw(path):
    hashes, names = set(), {}
    with open(path, encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            h, n = line.rstrip("\n").split("\t")[:2]
            hashes.add(h)
            if n:
                names[h] = n
    return hashes, names


def unique_index(fns, key):
    idx = collections.defaultdict(set)
    for e, f in fns.items():
        if key.endswith("_set"):
            vals = f[key[:-4]]
            # the WHOLE feature set as one key: QueryInterface bodies share single IIDs with their bases,
            # but the set of IIDs a class answers to is usually unique
            if len(vals) >= 2:
                idx[frozenset(vals)].add(e)
            continue
        for v in f[key]:
            idx[v].add(e)
    return {v: next(iter(s)) for v, s in idx.items() if len(s) == 1}


def anchors(W, L, keys):
    votes = collections.defaultdict(collections.Counter)
    rev = collections.defaultdict(collections.Counter)
    why = collections.defaultdict(list)
    for key in keys:
        wi, li = unique_index(W, key), unique_index(L, key)
        for v in wi.keys() & li.keys():
            w, l = wi[v], li[v]
            votes[w][l] += 1
            rev[l][w] += 1
            why[(w, l)].append(f"{key}:{(';'.join(sorted(v)) if isinstance(v, frozenset) else v)[:40]}")
    pairs = {}
    for w, c in votes.items():
        (l, n), = c.most_common(1)
        if len(c) > 1 and c.most_common(2)[1][1] == n:
            continue                      # tie on the Windows side
        rc = rev[l]
        (w2, n2), = rc.most_common(1)
        if w2 != w or (len(rc) > 1 and rc.most_common(2)[1][1] == n2):
            continue                      # not mutual, or tie on the Linux side
        pairs[w] = (l, "anchor", "; ".join(why[(w, l)][:3]))
    return pairs


def propagate(W, L, pairs, rels=("callees",)):
    matched_l = {v[0] for v in pairs.values()}
    changed = True
    while changed:
        changed = False
        for w, (l, _, _) in list(pairs.items()):
            for rel in rels:
                ws = [x for x in W[w][rel] if x not in pairs]
                ls = [x for x in L[l][rel] if x not in matched_l]
                if len(ws) == 1 and len(ls) == 1:
                    pairs[ws[0]] = (ls[0], f"prop-{rel}", f"via {w}<->{l}")
                    matched_l.add(ls[0])
                    changed = True
    return pairs


def win_vtables(pe_path, W):
    """Vtables of the Windows module: runs of aligned .rdata dwords that point at function entries, split at
    every address .text loads as an immediate (constructors store the vtable start; read_vtables.py)."""
    pe = PE(pe_path)
    entries = {int(e, 16) for e in W}
    text = pe.section(".text")
    tlo, thi = pe.imagebase + text[1], pe.imagebase + text[1] + text[2]
    runs, cur = [], []
    for name, va, val in pe.iter_dwords(aligned=True, only=".rdata"):
        if tlo <= val < thi:
            if cur and va != cur[-1][0] + 4:
                runs.append(cur); cur = []
            cur.append((va, val))
        else:
            if cur:
                runs.append(cur); cur = []
    if cur:
        runs.append(cur)
    members = {va for r in runs for va, _ in r}
    d, rp, rs = pe.data, text[3], text[4]
    starts = set()
    for i in range(rs - 3):
        v = struct.unpack_from("<I", d, rp + i)[0]
        if v in members:
            starts.add(v)
    vts = []
    for r in runs:
        cur = []
        for va, val in r:
            if va in starts and cur:
                vts.append(cur); cur = []
            cur.append("%08x" % val if val in entries else "-")
        if cur:
            vts.append(cur)
    return [v for v in vts if len(v) >= 2 and any(x != "-" for x in v)]


def lin_vtables(path, L):
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            a, name, slots = (line.rstrip("\n").split("\t") + ["", ""])[:3]
            sl = slots.split(";")[2:] if slots else []
            sl = [x if x in L else "-" for x in sl]
            if len(sl) >= 2 and any(x != "-" for x in sl):
                out.append(sl)
    return out


def align_vtables(Wv, Lv, pairs):
    """Pair whole vtables whose already-matched slots agree position-for-position, then pair the rest."""
    matched_l = {v[0]: w for w, v in pairs.items()}
    added = 0
    for vw in Wv:
        best, best_votes, tie = None, 0, False
        for vl in Lv:
            if len(vl) != len(vw):
                continue
            votes, bad = 0, False
            for xw, xl in zip(vw, vl):
                if xw == "-" or xl == "-":
                    continue
                if xw in pairs:
                    if pairs[xw][0] == xl:
                        votes += 1
                    else:
                        bad = True; break
                elif xl in matched_l:
                    bad = True; break
            if bad or votes == 0:
                continue
            if votes > best_votes:
                best, best_votes, tie = vl, votes, False
            elif votes == best_votes:
                tie = True
        if not best or tie:
            continue                      # ambiguous: inherited slots shared by several same-length vtables
        for xw, xl in zip(vw, best):
            if xw == "-" or xl == "-" or xw in pairs or xl in matched_l:
                continue
            pairs[xw] = (xl, "vtable", f"slot-aligned, {best_votes} agreeing slot(s)")
            matched_l[xl] = xw
            added += 1
    return added


def place_vtables(Wv, Lv, pairs, min_votes=2):
    """Linux-driven placement: slide each Linux vtable along each Windows vtable/run (which may hold several
    back-to-back vtables whose constructor-loaded start was not seen) and accept the unique offset where
    >= min_votes matched slots agree and none conflict."""
    matched_l = {v[0]: w for w, v in pairs.items()}
    pos_w = {}
    for wi, vw in enumerate(Wv):
        for i, x in enumerate(vw):
            if x != "-":
                pos_w.setdefault(x, []).append((wi, i))
    added = 0
    for vl in Lv:
        cand = collections.Counter()
        for j, xl in enumerate(vl):
            if xl in matched_l:
                for wi, i in pos_w.get(matched_l[xl], []):
                    cand[(wi, i - j)] += 1
        scored = []
        for (wi, off), _ in cand.items():
            vw = Wv[wi]
            votes, bad = 0, False
            for j, xl in enumerate(vl):
                i = j + off
                if i < 0 or i >= len(vw):
                    continue
                xw = vw[i]
                if xw == "-" or xl == "-":
                    continue
                if xw in pairs:
                    if pairs[xw][0] == xl:
                        votes += 1
                    else:
                        bad = True; break
                elif xl in matched_l:
                    bad = True; break
            if not bad:
                scored.append((votes, wi, off))
        scored.sort(reverse=True)
        if not scored or scored[0][0] < min_votes or (len(scored) > 1 and scored[1][0] == scored[0][0]):
            continue
        votes, wi, off = scored[0]
        vw = Wv[wi]
        for j, xl in enumerate(vl):
            i = j + off
            if 0 <= i < len(vw):
                xw = vw[i]
                if xw == "-" or xl == "-" or xw in pairs or xl in matched_l:
                    continue
                pairs[xw] = (xl, "vtable", f"placed at offset {off}, {votes} agreeing slot(s)")
                matched_l[xl] = xw
                added += 1
    return added


def pipeline(W, L, seed, Wv, Lv, rels=("callees",)):
    pairs = dict(seed)
    while True:
        n0 = len(pairs)
        if rels:
            propagate(W, L, pairs, rels)
        if Wv and Lv:
            align_vtables(Wv, Lv, pairs)
            place_vtables(Wv, Lv, pairs)
        if len(pairs) == n0:
            return pairs


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--win", required=True)
    ap.add_argument("--lin", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--holdout", action="store_true")
    ap.add_argument("--pe", help="Windows module (original/modules/X.DLL) for vtable alignment")
    ap.add_argument("--linvt", help="DumpElfVtables.java output for the Linux library")
    ap.add_argument("--fw", help="framework.tsv from framework_names.py")
    a = ap.parse_args(argv)
    fw = load_fw(a.fw) if a.fw else None
    W, L = load(a.win, fw), load(a.lin)
    print(f"windows {len(W)} fns, linux {len(L)} fns")

    Wv = win_vtables(a.pe, W) if a.pe else []
    Lv = lin_vtables(a.linvt, L) if a.linvt else []
    if a.pe:
        print(f"vtables: windows {len(Wv)}, linux {len(Lv)}")
    seed = anchors(W, L, ("strs", "consts", "strs_set", "consts_set", "exts_set", "fw_set"))
    pairs = pipeline(W, L, seed, Wv, Lv)
    by = collections.Counter(v[1].split("-")[0] for v in pairs.values())
    print(f"anchors {len(seed)}, final {len(pairs)} ({100 * len(pairs) / max(1, len(W)):.1f}% of windows "
          f"functions) by stage {dict(by)}")

    if a.holdout:
        agree = disagree = reached = total = 0
        for trial in range(5):
            keys = sorted(seed)
            random.Random(trial).shuffle(keys)
            half = set(keys[: len(keys) // 2])
            got = pipeline(W, L, {w: seed[w] for w in half}, Wv, Lv)
            for w in keys[len(keys) // 2:]:
                total += 1
                if w in got:
                    reached += 1
                    if got[w][0] == seed[w][0]:
                        agree += 1
                    else:
                        disagree += 1
        print(f"HOLDOUT (5 random 50/50 splits): withheld anchors {total}, re-derived {reached}: "
              f"{agree} agree, {disagree} DISAGREE"
              + (f" -> precision {100 * agree / reached:.1f}%" if reached else ""))

    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("win_entry\tlin_entry\tlin_name\tstage\tevidence\n")
        for w in sorted(pairs):
            l, stage, ev = pairs[w]
            fh.write(f"{w}\t{l}\t{L[l]['name']}\t{stage}\t{ev}\n")
    print(f"-> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
