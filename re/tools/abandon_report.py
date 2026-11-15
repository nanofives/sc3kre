#!/usr/bin/env python3
r"""abandon_report.py - compare abandon_probe.py runs (task abandon, 2026-11-15).

  py -3.12 re/tools/abandon_report.py A.json B.json [...]     one column per run

Per run: game days, first and last snapshot (population = valve 3000 vt+0x28, jobs = valve 7000 vt+0x2c, abandoned
tiles, unpowered tiles, R/C/I valve value), flag-2 posts per site, sc3simrun_abandon counters, and the negative-demand
draws binned by raw valve value (cbucket) and the abandonments binned the same way (cpost).
"""
import json
import sys

ZB = ["a", "b", "c", "d", "p", "farm"]


def load(p):
    with open(p) as f:
        return json.load(f)


def main(paths):
    runs = [(p.split("\\")[-1].split("/")[-1], load(p)) for p in paths]
    for name, d in runs:
        sn = d.get("snaps") or []
        print("==", name, "days", d.get("days"), "taxed", d.get("taxed"))
        for tag, s in (("first", sn[0] if sn else None), ("last", sn[-1] if sn else None)):
            if not s:
                continue
            print("  %-5s day %4d pop %8s jobs %8s abandoned %5s unpowered %6s R %5s C %5s I %5s tax %s" % (
                tag, s["day"], s.get("rpop"), s.get("jobs"), s.get("abandoned_tiles"), s.get("unpowered_tiles"),
                s.get("R", {}).get("v"), s.get("C", {}).get("v"), s.get("I", {}).get("v"), s.get("tax")))
        if sn:
            mx = max(s.get("abandoned_tiles", 0) for s in sn)
            print("  abandoned tiles max %d; pop min %s max %s; jobs min %s max %s" % (
                mx, min(s.get("rpop", 0) for s in sn), max(s.get("rpop", 0) for s in sn),
                min(s.get("jobs", 0) for s in sn), max(s.get("jobs", 0) for s in sn)))
        posts = {k: v for k, v in (d.get("posts") or {}).items() if "flags=0x2" in k or "0x102" in k or "0x202" in k}
        print("  flag-2 posts:", sum(posts.values()), json.dumps(posts, sort_keys=True))
        sa = d.get("simrun_abandon")
        if sa:
            for zi, z in enumerate(("res", "com", "ind")):
                w = sa[zi * 6:zi * 6 + 6]
                b = sa[18 + zi * 6:18 + zi * 6 + 6]
                print("  simrun %s would %s blocked %s gentle-held %d" % (z, dict(zip(ZB, w)), dict(zip(ZB, b)), sa[36 + zi]))
            print("  simrun sandbox=%d gentle=%d share=%d" % (sa[39], sa[40], sa[41]))
        shares(d)


def bar(v, lo=-2000):
    """the RCI bar as the HUD draws it, -1000..0 for a negative value (SIMRCI 0x10042e89)"""
    return v * -1000 // lo


def shares(d, lo=-2000, hi=2000):
    cb, cp = d.get("cbucket") or {}, d.get("cpost") or {}
    if not cb and not cp:
        return
    zones = sorted({k.split(":")[0] for k in list(cb) + list(cp)})
    for z in zones:
        draws = {int(k.split(":")[1]): v for k, v in cb.items() if k.startswith(z + ":")}
        posts = {int(k.split(":")[1]): v for k, v in cp.items() if k.startswith(z + ":")}
        if draws:
            print("  %s negative-demand draws by raw valve bucket (bar): draws / stock fires" % z)
            for b in sorted(draws):
                print("    %6d..%6d (bar %5d..%5d): %6d / %4d" % (b, b + 99, bar(b), bar(b + 99), draws[b][0], draws[b][1]))
        if posts:
            print("  %s abandonments (c) by raw valve bucket: %s" % (z, json.dumps(dict(sorted(posts.items())))))
        if draws:
            tot = sum(v[1] for v in draws.values())
            print("  %s share_pct -> line (bar) -> stock fires the line would hold, of %d" % (z, tot))
            for sh in (0, 10, 20, 25, 30, 40, 50):
                thr = lo + (hi - lo) * sh // 100
                held = sum(v[1] for b, v in draws.items() if b >= thr)
                print("    %3d%% -> %6d (bar %5d): %5d (%.0f%%)" % (sh, thr, bar(thr), held, 100.0 * held / tot if tot else 0))


if __name__ == "__main__":
    main(sys.argv[1:])
