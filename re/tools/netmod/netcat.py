#!/usr/bin/env python3
r"""netcat.py -- network piece catalog / explorer (netmod stage 0). Read-only over the game files.

  py -3 re/tools/netmod/netcat.py show 29              # everything that defines piece 29
  py -3 re/tools/netmod/netcat.py show 0x45 --frames   # ... plus the 20/40 frame table
  py -3 re/tools/netmod/netcat.py from-clipboard       # the in-game "Copiar ID" block
  py -3 re/tools/netmod/netcat.py show --query block.txt
  py -3 re/tools/netmod/netcat.py list [--net HWAY] [--kind 5] [--name bridge]
  py -3 re/tools/netmod/netcat.py export 29 --png DIR  # its frames as PNG
  py -3 re/tools/netmod/netcat.py build [--out DIR]    # catalog.json + catalog.csv
  py -3 re/tools/netmod/netcat.py html [--out DIR]     # browsable static HTML + thumbnails
  py -3 re/tools/netmod/netcat.py tables               # SIMNTWRK hardcoded tables, decoded
  py -3 re/tools/netmod/netcat.py selftest

Output defaults to re/netcat_out/ (gitignored: it holds game art and must never be committed).
Game root: $SC3_GAME_ROOT, else found by walking up, else the repo's main checkout.
Schema and sources: re/analysis/NETMOD_CATALOG.md.
"""
import argparse
import os
import sys

if __package__ in (None, ""):
    # run as a script: drop this folder from sys.path (its module names must not shadow the
    # stdlib) and import the package from its parent instead
    _here = os.path.dirname(os.path.abspath(__file__))
    sys.path[:] = [p for p in sys.path if os.path.abspath(p or ".") != _here]
    sys.path.insert(0, os.path.dirname(_here))
    __package__ = "netmod"

from netmod import catalog as _cat  # noqa: E402
from netmod import paths, pe_tables, query, rules, trblkatt  # noqa: E402

KIND_NOTE = {0: "none", 1: "ROAD", 2: "HWAY", 3: "RAIL", 4: "SUBW", 5: "ROAD+RAIL",
             6: "ROAD+HWAY", 7: "RAIL+HWAY", 8: "SUBW+RAIL", 9: "PIPE", 10: "POWR",
             11: "ROAD+POWR", 12: "RAIL+POWR", 13: "HWAY+POWR", 14: "ROAD+HWAY 15130..15141",
             15: "HWAY 15130..15141"}


def frame_label(idx, hdr):
    """zoom/rotation/layer by frame index. Measured on every catalog piece (selftest
    'frame order'): widths are constant within each run of RotCount frames and grow with it."""
    zc, rc = hdr["zoom_count"] or 5, hdr["rot_count"] or 4
    per = zc * rc
    return (idx % per) // rc, idx % rc, idx // per


def _p(*a):
    print(*a)


def show(C, pid, frames=False, state=None, rules_limit=None):
    p = C.piece(pid)
    ex = p["exemplar"] or {}
    ln = p.get("names_localized") or {}
    occ = p["occupant_ini"] or {}
    title = ex.get("name") or occ.get("name") or "(no name)"
    _p("piece %d (0x%04X)  %s" % (pid, pid, title)
       + ("  |  ES %r  EN %r" % (ln.get("ENGLISH"), ln.get("English-UK")) if ln else ""))
    if state is not None:
        _p("  state from the block: %d (quarter turns)" % state)
    nets = [n for n in p["sets"] if n != "DIAG"]
    _p("  networks: %s" % (", ".join("%s (%s_GRND_Set.txt:%d, netType %s, save inst %s)"
                                     % (n, n, p["set_lines"][n],
                                        next(k for k, v in rules.NETTYPE.items() if v == n),
                                        rules.SAVE_INSTANCE[n]) for n in nets) or "none"))
    if "DIAG" in p["sets"]:
        _p("  also in DIAG_Set.txt:%d" % p["set_lines"]["DIAG"])
    cv = p["class_vtables"]
    _p("  class kind %d (%s) by FUN_1001a5f2%s" % (
        p["class_kind"], p["class_kind_why"],
        ("; factory FUN_1000bdcd -> size 0x%x vt1 %s, occupant vt %s = Copiar ID object.class %s"
         % (cv["size"], cv["vt1"], cv["vt2_occupant"], cv["query_object_class"])) if cv else ""))
    if occ:
        _p("  Occupant.ini (SYS.PAK) line %d: %s" % (occ["line"], occ["text"]))
    else:
        _p("  Occupant.ini: no [OccupantKeys] line for this id")
    if ex:
        chain = " < ".join("%s %s" % (c["type"], c["name"]) for c in ex["agent_chain"])
        _p("  exemplar %s {0xE223741F, %s, 0x%08X} (%d B): name %r, agent type %s, "
           "footprint %s" % (ex["file"], ex["group"], pid, ex["size"], ex["name"], chain,
                             "x".join(str(v) for v in ex["footprint"] or [])))
        if ex["agent_chain"] and ex["agent_chain"][0]["citysim_line"]:
            _p("      CitySim.ini [AgentTypes] line %d" % ex["agent_chain"][0]["citysim_line"])
        if p.get("budget"):
            b = p["budget"]
            _p("      SC3BudgetLayer.ini:%d [%s] %s=%s %s" % (b["line"], b["section"],
                                                            ex["agent_type"], b["value"],
                                                            b["comment"]))
        if ex["raw"]:
            _p("      other props: " + ", ".join("%s=%s" % (k, _fmt(v)) for k, v in
                                                ex["raw"].items() if v not in (0, [0, 0, 0])))
    else:
        _p("  exemplar: NONE in OccupantAttribs*.IXF (the factory's exemplar load has no record)")
    art = p["art"]
    if art["csattrib"]:
        cs = art["csattrib"]
        h = cs["hdr"]
        _p("  art: %s {%s, 0x6400, %d}%s: zoom %d x rot %d, %d frames, layer_flags 0x%08X"
           % (cs["file"], cs["type"], cs["instance"],
              " (SHARED: exemplar 0x67 points at piece %d's table)" % art["shared_from"]
              if art.get("shared_from") else "", h["zoom_count"], h["rot_count"], h["frames"],
              h["layer_flags"]))
        for o in art["objects"]:
            _p("      %s group %s object %s" % (o["container"], o["group"], o["object"]))
        slots = [f["slot"] for f in art["frames"] if f["slot"] is not None]
        if slots:
            _p("      pixel slots %d..%d (%d distinct records)" % (
                min(slots), max(slots), len({(f['container'], f['slot']) for f in art['frames']
                                             if f['slot'] is not None})))
        if frames:
            _p("      (z = zoom, r = rotation slot = idx % RotCount; whether r is the camera view or "
               "the piece state is [UNCERTAIN])")
            _p("      frame  z r L  group      instance    container               slot  anchor  w x h  flag")
            for f in art["frames"]:
                z, r, L = frame_label(f["frame"], h)
                _p("      %5d  %d %d %d  0x%08X 0x%08X  %-22s %5s  %6s  %s  %d" % (
                    f["frame"], z, r, L, f["group"], f["instance"], f["container"] or "-",
                    f["slot"], f["anchor_slot"],
                    "%dx%d" % (f["w"], f["h"]) if f.get("w") else "-", f["flag"]))
    else:
        _p("  art: no CSATTRIB table (%s)" % art["via"])
    rs = C.rules.refs_of(pid)
    _p("  rules: %d references  %s" % (len(rs), "  ".join(
        "%s=%d" % kv for kv in sorted(p["rule_summary"].items()))))
    print_refs(rs, nets, full=rules_limit is None)
    if p["hardcoded"]:
        _p("  hardcoded in SIMNTWRK.DLL:")
        for h in p["hardcoded"]:
            _p("      %s @ %s: %s" % (h["where"], h["rva"], h["what"]))
    else:
        _p("  hardcoded in SIMNTWRK.DLL: none of the decoded tables/constants")
    t = p["trblkatt"]
    if t:
        _p("  TrBlkAtt (SSimData\\%s\\TRBLKATT.IXF, traffic paths): states %s%s" % (
            t["lang"], t["states"],
            "" if t["same_in_all_langs"] else "  (bytes differ in another language folder)"))
        for st in t["states"]:
            _p("      state %d (%d B): %s" % (st, t["sizes"][st], t["decoded"][st]))
    else:
        _p("  TrBlkAtt: no {0x625C6226, 0x825C6289, id*0x100+state} record for any state")
    return p


ROLE_ORDER = ["RESULT", "condition", "convert TO", "convert FROM", "protected", "bridge",
              "collapse", "set member", "exits entry", "value in dead file"]


def _role_key(r):
    for i, k in enumerate(ROLE_ORDER):
        if r.role.startswith(k):
            return i
    return len(ROLE_ORDER)


def print_refs(rs, own_nets, full=False):
    """RESULT lines (where the tiler PRODUCES the piece) one by one; the rest grouped per file
    unless `full`. Own-network files first, dead files last."""
    def fkey(r):
        return (r.status == "DEAD", r.net not in own_nets, r.file)
    groups = {}
    for r in rs:
        groups.setdefault((_role_key(r), fkey(r), r.file), []).append(r)
    for (rk, _fk, f), lst in sorted(groups.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        tag = "[%s] " % lst[0].status if lst[0].status != "live" else ""
        role = ROLE_ORDER[rk] if rk < len(ROLE_ORDER) else lst[0].role
        if full or role in ("RESULT", "protected", "bridge", "set member") or len(lst) <= 3:
            for r in lst:
                _p("      " + tag + r.short())
        else:
            rules_ = sorted({r.rule for r in lst if r.rule is not None})
            lines = [r.line for r in lst]
            what = ("rules " + _ranges(rules_)) if rules_ else ("lines " + _ranges(lines))
            states = sorted({r.state for r in lst if r.state is not None})
            _p("      %s%s: %d x %s, %s%s" % (tag, f, len(lst), role, what,
                                             ", states %s" % states if states else ""))


def _ranges(nums):
    out, start, prev = [], None, None
    for n in sorted(set(nums)):
        if start is None:
            start = prev = n
        elif n == prev + 1:
            prev = n
        else:
            out.append(str(start) if start == prev else "%d-%d" % (start, prev))
            start = prev = n
    if start is not None:
        out.append(str(start) if start == prev else "%d-%d" % (start, prev))
    return ",".join(out)


def _fmt(v):
    if isinstance(v, list):
        return "(" + ",".join(_fmt(x) for x in v) + ")"
    if isinstance(v, int) and v > 9:
        return "0x%X" % v
    return str(v)


def cmd_list(C, a):
    n = 0
    for pid in C.ids:
        sets = C.rules.sets_of(pid)
        if a.net and a.net.upper() not in sets:
            continue
        kind, _ = pe_tables.classify(pid, [s for s in sets if s != "DIAG"])
        if a.kind is not None and kind != a.kind:
            continue
        ex = C.ex.get(pid)
        name = (ex["props"].get(0x64) if ex else None) or (C.occ.get(pid) or {}).get("name", "")
        if a.name and a.name.lower() not in (name or "").lower():
            continue
        refs = C.rules.refs_of(pid)
        _p("%6d 0x%04X  %-22s kind %2d  %-28s rules %3d  results %3d" % (
            pid, pid, " ".join(sets), kind, (name or "")[:28], len(refs),
            sum(1 for r in refs if r.role == "RESULT")))
        n += 1
    _p("%d pieces" % n)


def cmd_export(C, pid, outdir):
    p = C.piece(pid)
    art = p["art"]
    if not art["csattrib"]:
        raise SystemExit("piece %d has no CSATTRIB frame table: nothing to export" % pid)
    os.makedirs(outdir, exist_ok=True)
    h = art["csattrib"]["hdr"]
    n = 0
    for f in art["frames"]:
        if f["slot"] is None:
            _p("frame %d: record 0x%08X:0x%08X not found" % (f["frame"], f["group"],
                                                              f["instance"]))
            continue
        z, r, L = frame_label(f["frame"], h)
        name = "%05d_f%02d_z%d_r%d%s.png" % (pid, f["frame"], z, r, "_L%d" % L if L else "")
        try:
            w, hh = C.cont.export_png(f["container"], f["slot"], os.path.join(outdir, name))
        except Exception as e:  # format-0 records are alpha masks, sprite_patch refuses them
            _p("frame %d: %s" % (f["frame"], e))
            continue
        n += 1
    _p("wrote %d PNGs to %s" % (n, outdir))


def cmd_tables(C):
    t = pe_tables.dump_tables(C.pe)
    cm = t["crossing_matrix"]
    _p("crossing matrix @0x%08X  %s" % (cm["va"], cm["shape"]))
    _p("  E (existing piece id -> index): %s" % cm["E_from_existing_id"])
    _p("  N: %s" % cm["N"])
    for r, row in enumerate(cm["cells"]):
        _p("  [%d] " % r + "  ".join("%5d.%d" % (c["id"], c["state"]) if c else "    -  "
                                    for c in row))
    sp = t["slope_patterns"]
    _p("slope patterns @0x%08X %s: %s" % (sp["va"], sp["shape"], sp["rows"]))
    for e in t["slope_results"]:
        _p("slope result @0x%08X %s (%s): %s" % (e["va"], e["net"], e["rule"], _cells(e["cells"])))
    for e in t["ramps"]:
        _p("ramp @0x%08X %s (%s): %s" % (e["va"], e["net"], e["use"], _cells(e["cells"])))
    for e in t["legacy"]:
        _p("legacy import @0x%08X base %d stride %d (%s): %d records" % (
            e["va"], e["base"], e["stride"], e["use"], len(e["records"])))
        _p("    " + "  ".join("%d->%d.%d" % (r["code"], r["id"], r["state"]) for r in e["records"]))
    for e in t["id_lists"]:
        _p("id list @0x%08X count %d (%s): %s" % (e["va"], e["count"], e["use"],
                                                  " ".join(str(v) for v in e["values"])))
        _p("    note: " + e["note"])
    _p("bridges (TilingRules\\*_GRND_Bridges.txt, decoded record = [len, axis, minLen, A, B, C, D, E]):")
    for net, b in sorted(C.rules.bridges.items()):
        for r in b["records"]:
            _p("  %s line %d: axis %d minLen %d  " % (net, r["line"], r["a"], r["b"]) + "  ".join(
                "%s=[%s]" % ("ABCDE"[k], " ".join("%d.%d" % (v >> 8, v & 0xFF) for _, v in lst))
                for k, lst in enumerate(r["lists"])))


def _cells(cells):
    return " ".join("%d.%d" % (c["id"], c["state"]) if c else "-" for c in cells)


def cmd_selftest(C):
    res = list(C.rules.selftest())
    res.append(("SIMNTWRK.DLL is the stock build", C.pe.sha256 == pe_tables.SHA256_STOCK,
                C.pe.sha256[:16]))
    sb = C.pe.check_set_binding()
    res.append(("7 Set loads bind file -> global as ROAD 48 HWAY 4c RAIL 50 SUBW 54 PIPE 58 "
                "POWR 5c DIAG 60", len(sb) == 7 and all(x[4] for x in sb),
                "; ".join("%s@0x%x" % (x[2], x[0]) for x in sb)))
    pr = C.pe.check_predicates()
    want = ["ROAD", "HWAY", "RAIL", "SUBW", "PIPE", "POWR"]
    res.append(("classifier predicates +0x11c..+0x130 scan ROAD HWAY RAIL SUBW PIPE POWR",
                [x[3] for x in pr] == want, " ".join("%x:%s" % (x[0], x[3]) for x in pr)))
    miss = C.pe.check_factory()
    res.append(("22 factory vtable pairs present in FUN_1000bdcd", not miss, str(miss)))
    # sprite objects in the two Roads containers
    n_obj = sum(len(C.cont.objects(f)) for f in ("00000005_Roads.DAT", "5544F8BD_Roads_2.DAT"))
    res.append(("Roads.DAT + Roads_2.DAT sprite objects", n_obj == 296, "%d (map says 296)" % n_obj))
    # exemplar coverage
    ids = set(C.ids)
    exs = set(C.ex)
    res.append(("network exemplars in OccupantAttribs*.IXF", True,
                "%d records, %d of the %d Set ids, %d exemplars in no Set" %
                (len(exs), len(ids & exs), len(ids), len(exs - ids))))
    # frame order: within each layer of ZoomCount x RotCount frames, runs of RotCount frames
    # share a zoom: the widest frame of each run must grow from run to run.
    bad, checked, used = [], 0, set()
    for pid in C.ids:
        art = C.art(pid, C.ex.get(pid))
        if not art["csattrib"]:
            continue
        h = art["csattrib"]["hdr"]
        used.add((int(art["csattrib"]["type"], 16), art["csattrib"]["instance"]))
        byz = {}
        for f in art["frames"]:
            if f.get("w") is None:
                continue
            z, r, L = frame_label(f["frame"], h)
            byz.setdefault(L, {}).setdefault(z, []).append(f["w"])
        checked += 1
        zs = byz.get(0, {})                # layer 1 (bridge overlays) has ragged sizes
        mx = [max(zs[z]) for z in sorted(zs)]
        if any(b < a for a, b in zip(mx, mx[1:])):
            bad.append(pid)
    res.append(("frame order: zoom = (idx % (Z*R)) // R; layer 0 widest frame never shrinks "
                "with zoom (zoom 4 may reuse zoom 3 art)",
                not bad, "%d of %d pieces break it %s" % (len(bad), checked, bad[:8])))
    lay = [k[1] for k in used if C.cs[k]["hdr"]["frames"] !=
           C.cs[k]["hdr"]["b0f"] * (C.cs[k]["hdr"]["layer_flags"] & 0xFF)]
    res.append(("CSATTRIB frames == hdr[0x0f] x (layer_flags & 0xff), tables the catalog uses",
                not lay, "%d of %d differ %s" % (len(lay), len(used), sorted(lay)[:8])))
    n_ok = n_all = 0
    for lang in C.game.trblkatt_langs():
        for blob in trblkatt.records(C.game.trblkatt(lang)).values():
            n_all += 1
            try:
                trblkatt.parse(blob)
                n_ok += 1
            except (trblkatt.TrbError, ValueError, IndexError):
                pass
    res.append(("TrBlkAtt records parse to their exact size", n_ok == n_all,
                "%d / %d" % (n_ok, n_all)))
    tl = trblkatt.lang_summary(C.game)
    res.append(("TRBLKATT.IXF records per language x languages = 6,034",
                sum(n for _, n, _ in tl) == 6034,
                " ".join("%s:%d" % (l, n) for l, n, _ in tl)))
    ok = True
    for name, good, detail in res:
        ok &= bool(good)
        _p("%s  %-80s %s" % ("PASS" if good else "FAIL", name, detail))
    _p("selftest: %s" % ("ALL PASS" if ok else "FAILURES"))
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="netcat", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("show")
    s.add_argument("id", nargs="?")
    s.add_argument("--query", help="file holding a pasted 'SC3 query id v1' block")
    s.add_argument("--frames", action="store_true")
    s.add_argument("--all-rules", action="store_true")
    s.add_argument("--json", action="store_true")
    c = sub.add_parser("from-clipboard")
    c.add_argument("--frames", action="store_true")
    c.add_argument("--all-rules", action="store_true")
    l_ = sub.add_parser("list")
    l_.add_argument("--net")
    l_.add_argument("--kind", type=int)
    l_.add_argument("--name")
    e = sub.add_parser("export")
    e.add_argument("id")
    e.add_argument("--png", required=True, help="output folder (keep it out of git)")
    b = sub.add_parser("build")
    b.add_argument("--out", default=paths.default_out())
    h = sub.add_parser("html")
    h.add_argument("--out", default=os.path.join(paths.default_out(), "html"))
    h.add_argument("--all-frames", action="store_true",
                   help="write every frame PNG for the detail pages (slower)")
    sub.add_parser("tables")
    sub.add_parser("selftest")
    a = ap.parse_args(argv)

    C = _cat.Catalog()
    if a.cmd in ("show", "from-clipboard"):
        state = None
        if a.cmd == "from-clipboard" or a.query:
            text = query.clipboard_text() if a.cmd == "from-clipboard" else \
                open(a.query, encoding="utf-8", errors="replace").read()
            try:
                blk = query.parse(text)
            except ValueError:
                pid = query.ids_in_text(text)
                if pid is None:
                    raise SystemExit("no 'SC3 query id v1' block (and not a bare id)")
                blk = {}
            else:
                pid, state, how = query.piece_of(blk)
                if pid is None:
                    raise SystemExit("not a network piece: %s (cell %s, object.name %r)" %
                                     (how, blk.get("cell"), blk.get("object.name")))
                _p("from the block (%s): cell %s, object.name %r" %
                   (how, blk.get("cell"), blk.get("object.name")))
        else:
            if a.id is None:
                raise SystemExit("show needs an id or --query FILE")
            pid = int(a.id, 0)
        if getattr(a, "json", False):
            import json
            print(json.dumps(C.piece(pid), indent=1, ensure_ascii=False, default=str))
            return 0
        show(C, pid, frames=a.frames, state=state,
             rules_limit=None if a.all_rules else 40)
        return 0
    if a.cmd == "list":
        cmd_list(C, a)
        return 0
    if a.cmd == "export":
        cmd_export(C, int(a.id, 0), a.png)
        return 0
    if a.cmd == "build":
        cat = C.build()
        _cat.write_json(cat, os.path.join(a.out, "catalog.json"))
        _cat.write_csv(cat, os.path.join(a.out, "catalog.csv"))
        _p("wrote %s and catalog.csv: %d pieces" % (os.path.join(a.out, "catalog.json"),
                                                     len(cat["pieces"])))
        return 0
    if a.cmd == "html":
        from netmod import htmlcat as _html
        _html.build(C, a.out, all_frames=a.all_frames)
        return 0
    if a.cmd == "tables":
        cmd_tables(C)
        return 0
    if a.cmd == "selftest":
        return cmd_selftest(C)
    return 2


if __name__ == "__main__":
    sys.exit(main())
