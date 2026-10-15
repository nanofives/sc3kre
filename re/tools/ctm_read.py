#!/usr/bin/env python3
r"""ctm_read.py - read what sc3cartrips.dll wrote (task cartrips2): the trip dump, the log, and the A1 comparison.

  py -3.12 ctm_read.py trips <cartrips_trips.bin> [--n 5]          summary + first records
  py -3.12 ctm_read.py log <sc3cartrips.log>                          STAT / VERIFY / CALLER lines as JSON
  py -3.12 ctm_read.py a1 <inst> <arm>                                 A1: DLL vs ct_probe (same game), per phase

Dump format (sc3cartrips.c TripRec, packed): header u32 "TCT1", sizeof(TripRec), sizeof(Node), MAXSTORE; then one
variable-size record per drained viewport trip: 80-byte head + nstore x 12-byte nodes, pop order (destination first).
"""
import argparse
import collections
import json
import os
import re
import struct
import sys

HEAD = struct.Struct("<IIIIII4h8B6HI")      # 56 bytes: seq tid c1 c2 qpc_lo qpc_hi rect[4] flag..pad n first nstore nin lo hi types
NODE = struct.Struct("<4h4B")               # x0 z0 x1 z1 type prev side retry
assert HEAD.size == 56 and NODE.size == 12
HEAD_SIZE = 56 + 2 * 12


def node(t):
    x0, z0, x1, z1, ty, prev, side, retry = t
    return {"x0": x0, "z0": z0, "x1": x1, "z1": z1, "type": ty, "prev": prev, "side": side, "retry": retry}


def read_trips(path):
    b = open(path, "rb").read()
    magic, rec_size, node_size, maxstore = struct.unpack_from("<4I", b, 0)
    if magic != 0x31544354 or node_size != 12:
        raise SystemExit("not a TCT1 dump: %s" % path)
    o, out = 16, []
    while o + HEAD_SIZE <= len(b):
        h = HEAD.unpack_from(b, o)
        (seq, tid, c1, c2, qlo, qhi, rx0, rz0, rx1, rz1, flag, dkind, m5, m6, m7, trunc, vrect, _pad,
         n, first, nstore, nin, lo, hi, types) = h
        dest = node(NODE.unpack_from(b, o + 56))
        origin = node(NODE.unpack_from(b, o + 68))
        if o + HEAD_SIZE + nstore * 12 > len(b):
            break
        nodes = [NODE.unpack_from(b, o + HEAD_SIZE + 12 * i) for i in range(nstore)]
        out.append({"seq": seq, "tid": tid, "c1": c1, "c2": c2, "qpc": qhi * 2 ** 32 + qlo, "rect": [rx0, rz0, rx1, rz1],
                    "flag": flag, "dkind": dkind, "m": [m5, m6, m7], "trunc": trunc, "vrect": vrect, "n": n,
                    "first": first, "nin": nin, "lo": lo, "hi": hi, "types": types, "dest": dest, "origin": origin,
                    "nodes": nodes})
        o += HEAD_SIZE + nstore * 12
    return out


LINE = re.compile(r"^\[\s*([\d.]+) s\]\[tid (\w+)\] (\w+)> (.*)$")


def read_log(path):
    out = []
    for line in open(path, encoding="latin-1"):
        m = LINE.match(line.strip())
        if not m:
            continue
        rec = {"s": float(m.group(1)), "kind": m.group(3)}
        for k, v in re.findall(r"(\w+)=([^\s]+)", m.group(4)):
            try:
                rec[k] = float(v) if "." in v else int(v)
            except ValueError:
                rec[k] = v
        out.append(rec)
    return out


def cmd_trips(a):
    t = read_trips(a.path)
    print("%d trips" % len(t))
    c = collections.Counter()
    for r in t:
        c["flag"] += bool(r["flag"])
        c["vrect"] += r["vrect"]
        c["trunc"] += bool(r["trunc"])
        c["origin_0x80"] += r["origin"]["type"] == 0x80
    print(dict(c))
    for r in t[:a.n]:
        print(json.dumps({k: v for k, v in r.items() if k != "nodes"}), len(r["nodes"]))


def cmd_log(a):
    for r in read_log(a.path):
        print(json.dumps(r))


def cmd_a1(a):
    """Per phase of a ct_run arm: viewport trips per second from ct_probe (sum over its thread slots) and from the
    DLL's STAT lines (epoch-stamped, every log_s); and per-trip: each ct_probe sample (complete paths only) looked up
    in the dump by (tid, node sequence)."""
    jl = os.path.join(a.inst, a.arm + ".jsonl")
    recs = [json.loads(l) for l in open(jl, encoding="utf-8") if l.strip()]
    marks = [r for r in recs if r.get("mark") == "start"]
    phases = []
    for i, m in enumerate(marks):
        end = next((r["t"] for r in recs if r.get("mark") == "end" and r["phase"] == m["phase"] and r["t"] >= m["t"]), None)
        phases.append((m["phase"], m["t"] + 3, end))           # first 3 s dropped, as the phase-1 arms
    # ct_probe: cumulative per-thread counters each second
    ticks = [r for r in recs if r.get("t") and isinstance(r.get("trips"), dict)]

    def ct_total(r, key):
        return sum(v.get(key, 0) for v in r["trips"]["by_thread"].values())
    stats = [r for r in read_log(os.path.join(a.inst, "sc3cartrips.log")) if r["kind"] == "STAT"]
    out = []
    for name, t0, t1 in phases:
        if t1 is None:
            continue
        ins = [r for r in ticks if t0 <= r["t"] <= t1]
        if len(ins) < 2:
            continue
        dt = ins[-1]["t"] - ins[0]["t"]
        row = {"phase": name, "ct_secs": round(dt, 1)}
        for key in ("vp", "vpflag", "arrived", "nodes", "vpnodes"):
            row["ct_" + key] = (ct_total(ins[-1], key) - ct_total(ins[0], key)) / dt
        # DLL: STAT windows fully inside the phase (epoch ms at the window end, dt seconds long)
        sw = [s for s in stats if t0 * 1000 <= s["epoch"] - s["dt"] * 1000 and s["epoch"] <= t1 * 1000]
        if sw:
            d = sum(s["dt"] for s in sw)
            row["dll_secs"] = round(d, 1)
            for key in ("vp", "vpflag", "paths", "nodes", "vpnodes", "drops"):
                row["dll_" + key] = sum(s[key] for s in sw) / d
            row["vp_dll_over_ct"] = row["dll_vp"] / row["ct_vp"] if row["ct_vp"] else None
        out.append(row)
        print(json.dumps(row))
    # per trip
    dump = os.path.join(a.inst, "cartrips_trips.bin")
    if os.path.exists(dump):
        trips = read_trips(dump)
        index = collections.defaultdict(list)
        for r in trips:
            key = (r["dest"]["x0"], r["dest"]["z0"], r["dest"]["type"], r["origin"]["x0"], r["origin"]["z0"], r["n"])
            index[key].append(r)
        st = collections.Counter()
        for r in recs:
            for smp in r.get("samples") or []:
                if smp["n"] > len(smp["p"]):
                    st["ct_truncated"] += 1
                    continue
                p = smp["p"]
                key = (p[0][0], p[0][1], p[0][2], p[-1][0], p[-1][1], smp["n"])
                cands = index.get(key, [])
                hit = None
                for c in cands:
                    seg = [(x0, z0, ty) for (x0, z0, x1, z1, ty, *_r) in c["nodes"]]
                    if seg == [tuple(q) for q in p[c["first"]:c["first"] + c["nstore"]]] and bool(c["flag"]) == bool(smp["flag"]):
                        hit = c
                        break
                st["ct_samples"] += 1
                st["matched" if hit else ("same_ends_no_seq" if cands else "unmatched")] += 1
        print(json.dumps({"dump_trips": len(trips), **st}))
        out.append({"per_trip": dict(st), "dump_trips": len(trips)})
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1)


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("trips"); p.add_argument("path"); p.add_argument("--n", type=int, default=5)
    p = sp.add_parser("log"); p.add_argument("path")
    p = sp.add_parser("a1"); p.add_argument("inst"); p.add_argument("arm"); p.add_argument("--json")
    a = ap.parse_args()
    {"trips": cmd_trips, "log": cmd_log, "a1": cmd_a1}[a.cmd](a)


if __name__ == "__main__":
    main()
