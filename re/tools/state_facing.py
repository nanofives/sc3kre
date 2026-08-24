#!/usr/bin/env python3
r"""U-078, open half: the rotation SENSE and the compass zero of the network-piece `state` byte.

Two independent witnesses, both mechanical, both run by this one script.

WITNESS 1 (code) -- SIMNTWRK.DLL FUN_1000d73d @ 0x1000d73d, table DAT_1003123c @ 0x1003123c.
  That function is vtable slot +0xb0 of the class at vtable 0x1002bd04, reached from every one of
  the 22 network-piece kinds through primary slot +0x4c (FUN_1000cd35 @ 0x1000cd35), which forwards
  `state = *(u32*)(this+0x14) >> 0x1e`.  Its index arithmetic is
      iVar2 = (dir + state * 4) * 4
  into a 16-row x 4-byte table of BIT INDICES.  Reading that table tells you exactly how `state`
  permutes directions, with no interpretation left over.

WITNESS 2 (data) -- Apps\Res\TilingRules\*_final.txt, all six networks.
  Per NETWORK_RULE_ENGINE.md 4.4 that stage runs at mode 4, so its selector is an exact 4-bit
  orthogonal-neighbour mask (bit b == dir b; FUN_10022092 @ 0x10022092 plus the city-edge block of
  FUN_10019768 @ 0x10019768) and every result record sits at dir 255, the tile itself.  So each
  rule reads literally
      (set of occupied orthogonal neighbours)  ->  (pieceId, state)
  which is the cleanest constraint on facing the shipped data can offer.

Hypotheses scored against both:
  H+  the piece's canonical direction c sits at world dir (c + state) mod 4
  H-  ................................................... (c - state) mod 4

World dirs are the SIMNTWRK 5x5 offset table at 0x10032134: 0=(-1,0) 1=(0,-1) 2=(+1,0) 3=(0,+1),
labelled W/N/E/S by NETWORK_RULE_ENGINE.md 4.1.  Read-only; nothing under Apps\ is written.

  python verify/state_facing_test/state_facing.py
"""
import collections
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "re", "tools"))
from tilingrules import TilingFile                                    # noqa: E402
from pe_vtable import PE                                              # noqa: E402

RULEDIR = os.path.join(ROOT, "Apps", "Res", "TilingRules")
DLL = os.path.join(ROOT, "original", "modules", "SIMNTWRK.DLL")
LBL = {0: "W", 1: "N", 2: "E", 3: "S"}
VEC = {0: "(-1, 0)", 1: "( 0,-1)", 2: "(+1, 0)", 3: "( 0,+1)"}


def dirs_of(mask):   return frozenset(b for b in range(4) if mask >> b & 1)
def rot(s, k):       return frozenset((d + k) % 4 for d in s)
def show(s):         return "{%s}" % ",".join(LBL[d] for d in sorted(s))


# =======================================================================================
# WITNESS 1 -- the (state, dir) bit-index table inside SIMNTWRK
# =======================================================================================

def witness_code():
    pe = PE(DLL)
    base = 0x1003123C
    tab = pe.data[pe.off(base):pe.off(base) + 64]
    print("=" * 80)
    print("WITNESS 1  --  SIMNTWRK FUN_1000d73d @ 0x1000d73d, table DAT_1003123c @ 0x1003123c")
    print("=" * 80)
    print("  bit index = 4*edge + lane.  Row (state, dir) holds the four bit indices the engine")
    print("  probes when asked 'does this piece connect at world dir <dir>' for a piece at <state>.")
    print()
    plus = minus = 0
    for s in range(4):
        for d in range(4):
            row = list(tab[(d + s * 4) * 4:(d + s * 4) * 4 + 4])
            edges = {b >> 2 for b in row}
            e = edges.pop() if len(edges) == 1 else None
            tag = ""
            if e is not None:
                if e == (d - s) % 4:
                    plus += 1
                    tag = "edge %d == (dir-state) mod 4   -> H+" % e
                if e == (d + s) % 4:
                    minus += 1
                    tag = "edge %d == (dir+state) mod 4   -> H-" % e
            print("  state %d  dir %d %s : bits %-16s  %s"
                  % (s, d, VEC[d], row, tag))
    print()
    print("  rows consistent with H+ : %2d / 16" % plus)
    print("  rows consistent with H- : %2d / 16" % minus)
    print()
    print("  Read the winning form the other way round: a canonical edge c of the piece is")
    print("  answered when the world dir queried is d with (d - state) == c, i.e. edge c PRESENTS")
    print("  AT world dir (c + state) mod 4.")
    # the lane index rotates by the same amount, which is what makes it a rigid rotation
    lane_ok = all(list(tab[(d + s * 4) * 4:(d + s * 4) * 4 + 4]) ==
                  [4 * ((d - s) % 4) + (k - s) % 4 for k in range(4)]
                  for s in range(4) for d in range(4))
    print("  Full closed form  row(s,d)[k] == 4*((d-s) mod 4) + ((k-s) mod 4) holds for all 16"
          " rows: %s" % lane_ok)
    print("  (both indices of the 4x4 bit field turn together -- a rigid quarter turn, not a"
          " relabelling)")
    return plus, minus


# =======================================================================================
# WITNESS 2 -- the *_final.txt stage
# =======================================================================================

def final_rows():
    """[(net, file, occupied_dirset, pieceId, state)] over every *_final.txt rule."""
    out = []
    for fn in sorted(os.listdir(RULEDIR)):
        if not fn.lower().endswith("_final.txt"):
            continue
        tf = TilingFile(os.path.join(RULEDIR, fn))
        assert tf.family == "RULES", fn
        for i, r in enumerate(tf.model["rules"]):
            sel = r["selector"]
            assert sel <= 0xF, (fn, i, sel)              # stage-3 invariant, mode 4
            assert len(r["results"]) == 1 and r["results"][0][0] == 255, (fn, i)
            v = r["results"][0][1]
            if v < 256:
                continue
            out.append((fn.split("_")[0], fn, dirs_of(sel), v >> 8, v & 0xFF))
    return out


def witness_data():
    rows = final_rows()
    per = collections.defaultdict(dict)
    for net, fn, occ, pid, st in rows:
        per[(fn, pid)][st] = occ

    print("\n" + "=" * 80)
    print("WITNESS 2  --  *_final.txt : occupied orthogonal neighbours -> (pieceId, state)")
    print("=" * 80)
    print("  %d rules across %d files, %d (file,id) families"
          % (len(rows), len({r[1] for r in rows}), len(per)))
    for (fn, pid), byst in sorted(per.items()):
        print("  %-24s id %-6d  %s" % (fn, pid,
              "  ".join("s%d=%s" % (s, show(byst[s])) for s in sorted(byst))))

    print("\n  " + "-" * 76)
    print("  EQUIVARIANCE.  A family is consistent with H(sign) iff one canonical set explains")
    print("  every state it appears in: canonical(s) = rot(observed(s), -sign*s) is constant.")
    print("  Only families that appear at state 1 or 3 can tell H+ from H- at all (a half turn")
    print("  is its own inverse), and a rotationally symmetric shape cannot either.  Those are")
    print("  counted separately as DISCRIMINATING.")
    print("  " + "-" * 76)

    verdict = {}
    for sign, name in ((+1, "H+"), (-1, "H-")):
        ok = bad = 0
        fams_ok = fams_bad = []
        fams_ok, fams_bad = [], []
        for (fn, pid), byst in sorted(per.items()):
            # selector 0 is degenerate: an isolated tile constrains no facing.  Excluded from
            # the fit, and reported separately below.
            st_used = {s: o for s, o in byst.items() if o}
            if not st_used:
                continue
            canon = collections.Counter(rot(o, -sign * s) for s, o in st_used.items())
            best, n = canon.most_common(1)[0]
            ok += n
            bad += len(st_used) - n
            (fams_ok if len(canon) == 1 else fams_bad).append((fn, pid, st_used, sign))
        verdict[sign] = (ok, bad, fams_bad)
        print("\n  %s : %d rules explained, %d contradicted   (%d families clean, %d broken)"
              % (name, ok, bad, len(per) - len(fams_bad) - 0, len(fams_bad)))
        for fn, pid, st_used, sg in fams_bad:
            print("     COUNTEREXAMPLE %-24s id %-6d %s" % (fn, pid,
                  "  ".join("s%d=%s->canon %s" % (s, show(o), show(rot(o, -sg * s)))
                            for s, o in sorted(st_used.items()))))

    # discriminating subset
    disc = []
    for (fn, pid), byst in sorted(per.items()):
        st_used = {s: o for s, o in byst.items() if o}
        if not any(s in (1, 3) for s in st_used):
            continue
        cp = len(collections.Counter(rot(o, -s) for s, o in st_used.items()))
        cm = len(collections.Counter(rot(o, +s) for s, o in st_used.items()))
        if cp != cm:
            disc.append((fn, pid, sorted(st_used), cp == 1))
    print("\n  DISCRIMINATING families (H+ and H- actually differ): %d" % len(disc))
    for fn, pid, sts, plus_wins in disc:
        print("     %-24s id %-6d states %-14s -> %s"
              % (fn, pid, sts, "H+" if plus_wins else "H-"))
    n_disc_rows = sum(len(sts) for _, _, sts, _ in disc)
    print("     rows in discriminating families: %d, all favouring %s"
          % (n_disc_rows, "H+" if all(p for *_, p in disc) else "MIXED"))

    print("\n  " + "-" * 76)
    print("  THE ABSOLUTE ZERO, under H+ : the connection set a piece has at state 0.")
    print("  " + "-" * 76)
    zero = {}
    for (fn, pid), byst in sorted(per.items()):
        st_used = {s: o for s, o in byst.items() if o}
        if not st_used:
            continue
        c = collections.Counter(rot(o, -s) for s, o in st_used.items()).most_common(1)[0][0]
        zero[(fn, pid)] = c
        kind = {1: "STUB (dead end)", 2: "2-arm", 3: "T-junction", 4: "crossroads"}[len(c)]
        print("  %-24s id %-6d %-16s state0 = %-12s  states seen %s"
              % (fn, pid, kind, show(c), sorted(st_used)))

    print("\n  Grouped by state-0 set -- the shipped art uses TWO zeros, one quarter turn apart:")
    g = collections.defaultdict(list)
    for (fn, pid), c in zero.items():
        g[c].append("%s/%d" % (fn.split("_")[0], pid))
    for c, ids in sorted(g.items(), key=lambda kv: (len(kv[0]), sorted(kv[0]))):
        print("    state0 %-12s (deg %d) : %s" % (show(c), len(c), ", ".join(sorted(ids))))

    # degenerate selector-0 rules
    print("\n  Selector 0 (isolated tile, no facing constraint) rules, excluded from the fit:")
    for net, fn, occ, pid, st in rows:
        if not occ:
            print("    %-24s selector 0 -> id %d state %d" % (fn, pid, st))
    return verdict, zero


# =======================================================================================
# Widened sample -- stage 1, where the constraint is a SUBSET relation, not equality
# =======================================================================================

def widened(zero_by_id):
    """Stage 1 (*SIMPLERULES*, mode 8).

    The selector says a same-network neighbour is PRESENT, not that the placed piece connects to
    it, so equality is the wrong test here; the honest invariant is
        rot(shape, state)  subset of  (selector & 0xf).
    Scored for both signs; a rule discriminates only when exactly one sign satisfies it.
    """
    shape = {}
    for (fn, pid), c in zero_by_id.items():
        shape[(fn.split("_")[0], pid)] = c

    print("\n" + "=" * 80)
    print("WIDENED SAMPLE  --  stage 1 (*SIMPLERULES*.txt, mode 8), subset test")
    print("=" * 80)
    tot = unk = 0
    both = neither = onlyp = onlym = 0
    ex_m = []
    for fn in sorted(os.listdir(RULEDIR)):
        if "simplerules" not in fn.lower():
            continue
        net = fn.split("_")[0]
        tf = TilingFile(os.path.join(RULEDIR, fn))
        f = collections.Counter()
        for r in tf.model["rules"]:
            orth = dirs_of(r["selector"] & 0xF)
            for d, v in r["results"]:
                if d != 255 or v < 256:
                    continue
                tot += 1
                sh = shape.get((net, v >> 8))
                if sh is None:
                    unk += 1
                    f["unknown"] += 1
                    continue
                st = v & 0xFF
                p = rot(sh, +st) <= orth
                m = rot(sh, -st) <= orth
                if p and m:
                    both += 1; f["both"] += 1
                elif p:
                    onlyp += 1; f["H+ only"] += 1
                elif m:
                    onlym += 1; f["H- only"] += 1
                    ex_m.append((net, v >> 8, st, r["selector"]))
                else:
                    neither += 1; f["neither"] += 1
        print("  %-28s %s" % (fn, dict(f)))
    print("\n  centre results %d   (shape unknown %d)" % (tot, unk))
    print("  satisfied by BOTH signs (non-discriminating) : %d" % both)
    print("  satisfied by H+ ONLY                          : %d" % onlyp)
    print("  satisfied by H- ONLY                          : %d" % onlym)
    print("  satisfied by NEITHER                          : %d" % neither)
    for e in ex_m[:20]:
        print("    H- only: net %s id %d state %d selector 0x%02x" % e)


def convert_test():
    """*_Convert.txt : (fromId,fromState) -> (toId,toState).  A substitution must preserve world
    geometry, so fromState -> toState has to be equivariant (s -> s+1 turns into t -> t+1) modulo
    the target's own rotational symmetry.  Sign-blind, but it proves `state` is the same rotation
    index on both sides of a substitution."""
    print("\n" + "=" * 80)
    print("CROSS-CHECK  --  *_Convert.txt / *_Complex_Convert.txt state equivariance")
    print("=" * 80)
    tot = ok = 0
    for fn in sorted(os.listdir(RULEDIR)):
        if "convert" not in fn.lower():
            continue
        tf = TilingFile(os.path.join(RULEDIR, fn))
        if tf.family != "COUNTED_PAIRS":
            print("  %-32s family %s -- skipped" % (fn, tf.family))
            continue
        m = collections.defaultdict(dict)
        for a, b in tf.model["pairs"]:
            if a >= 256 and b >= 256:
                m[(a >> 8, b >> 8)][a & 0xFF] = b & 0xFF
        f_ok = f_bad = 0
        for (fid, tid), mp in sorted(m.items()):
            if len(mp) < 2:
                continue
            per = max(len(set(mp.values())), 1)
            good = all(((mp[(s + 1) % 4] - mp[s]) % 4) % per == 1 % per
                       for s in mp if (s + 1) % 4 in mp)
            tot += 1
            if good:
                f_ok += 1
            else:
                f_bad += 1
                print("    NON-EQUIVARIANT %s id %d -> %d : %s" % (fn, fid, tid, mp))
        ok += f_ok
        print("  %-32s %3d id-pairs with >=2 states : %3d equivariant, %3d not"
              % (fn, f_ok + f_bad, f_ok, f_bad))
    print("\n  TOTAL %d id-pairs : %d equivariant, %d not" % (tot, ok, tot - ok))


if __name__ == "__main__":
    witness_code()
    _v, zero = witness_data()
    widened(zero)
    convert_test()


# =======================================================================================
# NOT EVIDENCE-GRADE -- the exemplar-blob probe.  Kept because it is reproducible and
# because it says where the remaining work is, not because it proves anything.
# =======================================================================================

def exemplar_probe():
    r"""The key FUN_1000d1cf builds, {0x625c6226, 0x825c6289, id*0x100 + state}, resolves to
    Apps\Res\SSimData\<lang>\TrBlkAtt.IXF -- 179..322-byte "BIN\r" PROPERTY BLOBS, not bitmaps.
    Those blobs are variable length and the format is NOT parsed, so a fixed byte offset is not
    guaranteed to name the same field in two records of different length.  This probe therefore
    reports a pattern, not a fact."""
    sys.path.insert(0, os.path.join(ROOT, "re", "tools"))
    from ixf_parse import parse
    KEY = {0x625C6226, 0x825C6289}
    path = os.path.join(ROOT, "Apps", "Res", "SSimData", "English-UK", "TrBlkAtt.IXF")
    recs, d = parse(path)
    blob = collections.defaultdict(dict)
    for r in recs:
        if {r["group"], r["type"]} == KEY:
            blob[r["instance"] >> 8][r["instance"] & 0xFF] = d[r["offset"]:r["offset"] + r["size"]]

    print("\n" + "=" * 80)
    print("NOT EVIDENCE-GRADE PROBE -- TrBlkAtt.IXF exemplar blobs")
    print("=" * 80)
    print("  %d piece ids carry a {0x625c6226,0x825c6289,id*0x100+state} record here." % len(blob))
    print("  Looking for any byte that steps by a constant multiple of 8 (mod 32) as state")
    print("  advances 0->1->2->3.  8/32 of a turn == 90 degrees.")
    hist = collections.Counter()
    lens = {}
    for pid, st in sorted(blob.items()):
        sts = sorted(st)
        if len(sts) < 3:
            continue
        L = min(len(st[s]) for s in sts)
        for off in range(L):
            vals = [st[s][off] for s in sts]
            if len(set(vals)) != len(sts) or any(v >= 32 for v in vals):
                continue
            steps = {(vals[i + 1] - vals[i]) % 32 for i in range(len(vals) - 1)}
            if len(steps) == 1:
                step = steps.pop()
                if step % 8 == 0 and step:
                    hist[step] += 1
                    lens.setdefault(step, []).append((pid, off, vals,
                                                      [len(st[s]) for s in sts]))
    print("\n  step histogram: %s   (+8 = the H+ sense, +24 = -8 = the H- sense)" % dict(hist))
    for step in sorted(lens):
        print("\n  step +%d, %d (piece, offset) hits:" % (step, len(lens[step])))
        for pid, off, vals, ln in lens[step]:
            print("     id %-6d off 0x%03x vals %-20s record lens %s" % (pid, off, vals, ln))
    print("\n  READ THIS CAREFULLY: the two step -8 hits sit at offset 0x64 in records of length")
    print("  281 and 322, while the step +8 hits at 0x64 are in records of length 179.  Different")
    print("  lengths mean offset 0x64 is not known to be the same field, so these are NOT")
    print("  counterexamples to H+ -- they are an artefact of probing an unparsed format.")
    print("  Closing this properly needs the BIN\r property-blob format decoded.  Until then this")
    print("  section supports nothing and refutes nothing.")


if __name__ == "__main__":
    exemplar_probe()
