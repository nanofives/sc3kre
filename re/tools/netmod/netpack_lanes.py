#!/usr/bin/env python3
r"""netpack_lanes.py - the `lanes` and `connects` sections of a netpack manifest (task lanekit, 2026-10-13).

  "lanes":    [{"piece": 20400, "spec": "lanes/quarter.json" | {...inline spec...}, "langs": ["ENGLISH", ...]?}]
  "connects": [{"piece": 39, "road": [["x-", "z-"], ...] | {"low": [...], "high": [...]} | "auto"?, "rail": ..., "subway": ...}]

A lane spec is lanekit's authoring format (lanekit.compile_spec, NET_LANES.md 6). Its records replace the TrBlkAtt
records of `piece` for the states it lists, in every language folder (English-UK gets the mirrored lanes, as the
shipped files do, unless the spec says "mirror_uk": false). Its own "connects" key, if any, sets the turn matrix.
A `connects` entry sets only the turn matrix (exemplar props 310 / 311 / 312), leaving the lanes alone.

`piece` is either a variant declared by an installed package (its records / exemplar are edited before they are
written into the Korea containers) or a stock piece (its stock TrBlkAtt records are replaced in copies of the
TrBlkAtt containers, its stock exemplar rewritten in a copy of the Occupant container that holds it). One piece may be
edited by one package only.

Checks (lanecheck): ERROR refuses the package, WARNING / INFO are reported in BUILD.json.
  ERROR    spec does not compile (unknown curve key, lane end not on a side, bad side name ...); piece has no exemplar
           and the entry sets connects; two packages edit one piece; a node outside 0..255; an exit code > 31
  WARNING  a lane's (entry side, exit side) turn is not in the piece's road/rail/subway matrix low half (ENGLISH
           lanes) - the tiler and the highway router will disagree with the cars; an exit on a side where the matrix
           has no arm; a matrix turn that no lane drives; a curve whose end points are not the lane's nodes in some
           language (the cars jump); a piece with lanes and no record for a state the tiler places
  INFO     stock records / exemplars replaced
"""
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import ixf_parse  # noqa: E402

from netmod import lanekit as LK   # re/tools is on sys.path (netpack.py puts it there)

TRB_TYPE, TRB_GROUP = LK.TRB_TYPE, LK.TRB_GROUP
EX_TYPE, EX_GROUP = LK.EX_TYPE, LK.EX_GROUP


class LanesError(Exception):
    pass


def replace_records(d, records):
    """IXF container bytes -> new bytes where each (group, instance, type, payload) replaces the record with that key
    (payload appended at the end of the file, the index slot re-pointed; the old payload bytes stay, unreferenced) or
    is appended as a new record (ixf_insert.append). Every other record keeps offset and bytes."""
    import ixf_insert
    d = bytearray(d)
    slots = ixf_parse.read_index_slots(bytes(d))
    pos = {s[:3]: 4 + i * ixf_parse.REC for i, s in enumerate(slots) if s[:3] != (0, 0, 0)}
    new = []
    for g, i, t, p in records:
        at = pos.get((g, i, t))
        if at is None:
            new.append((g, i, t, p))
            continue
        off = len(d)
        d += p
        struct.pack_into("<II", d, at + 12, off, len(p))
    out = bytes(d)
    if new:
        out = ixf_insert.append(out, new)
    return out


def _spec_of(pack_dir, e, where):
    s = e.get("spec")
    if isinstance(s, str):
        p = os.path.join(pack_dir, s)
        if not os.path.isfile(p):
            raise LanesError("%s: spec file %s not found" % (where, s))
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    if isinstance(s, dict):
        return json.loads(json.dumps(s))
    raise LanesError("%s: \"spec\" must be a file name or an object" % where)


def compile_entries(stock_root, pack_dir, man):
    """-> {"lanes": [...], "connects": [...], "warnings": [...], "info": [...]} for one package."""
    g = LK.Game(stock_root)
    out = {"lanes": [], "connects": [], "warnings": [], "info": []}
    for n, e in enumerate(man.get("lanes", [])):
        where = "%s lanes %d (piece %s)" % (man["name"], n + 1, e.get("piece"))
        pid = e["piece"]
        spec = _spec_of(pack_dir, e, where)
        spec["piece"] = pid
        langs = e.get("langs") or g.langs()
        recs, masks = {}, None
        for lang in langs:
            if lang not in g.langs():
                raise LanesError("%s: language folder %r is not in Apps\\Res\\SSimData" % (where, lang))
            try:
                c = LK.compile_spec(spec, g, lang)
            except (LK.LaneError, KeyError, ValueError, TypeError) as ex:
                raise LanesError("%s (%s): %s" % (where, lang, ex))
            recs[lang] = [(TRB_GROUP, pid * 0x100 + st, TRB_TYPE, b) for st, b in sorted(c["records"].items())]
            for w in c["warnings"]:
                out["info"].append("%s (%s): %s" % (where, lang, w))
            out["warnings"] += ["%s (%s): %s" % (where, lang, w) for w in check_record(c["rec0"], g, lang)]
            if masks is None:
                masks = c["masks"]
        try:
            rec0 = LK.compile_spec(spec, g, "ENGLISH", mirror=False)["rec0"]      # the low-half lanes, for check_turns
        except LK.LaneError as ex:
            raise LanesError("%s: %s" % (where, ex))
        out["lanes"].append({"piece": pid, "records": recs, "masks": masks or {}, "where": where,
                             "_pack": man["name"], "rec0": rec0, "states": sorted(spec.get("states", [0, 1, 2, 3]))})
    for n, e in enumerate(man.get("connects", [])):
        where = "%s connects %d (piece %s)" % (man["name"], n + 1, e.get("piece"))
        if any(e.get(k) == "auto" for k in LK.CONN_PROPS):
            raise LanesError("%s: \"auto\" needs lanes; put the connects in the lane spec instead" % where)
        try:
            m = LK.compile_connects({k: v for k, v in e.items() if k in LK.CONN_PROPS}, set(), out["warnings"])
        except LK.LaneError as ex:
            raise LanesError("%s: %s" % (where, ex))
        if not m:
            raise LanesError("%s: names no network (road / rail / subway)" % where)
        out["connects"].append({"piece": e["piece"], "masks": m, "where": where, "_pack": man["name"]})
    return out


def check_record(rec, g, lang):
    """Structural findings on one compiled state-0 record (raised to ERROR by the caller when fatal)."""
    w = []
    P = g.paths(lang)
    for kind in ("ped", "veh"):
        for i, n in enumerate(rec[kind]):
            if not (-16 <= n["x"] <= 271 and -16 <= n["z"] <= 271):
                raise LanesError("%s node %d at (%d, %d): STRTSIM buckets nodes by (c + 16) / 72 in 0..3 "
                                 "(FUN_10020108), so a node outside -16..271 is never found" % (kind, i, n["x"], n["z"]))
            for e in n["edges"]:
                if e["to"] is None and e["code"] > 31:
                    raise LanesError("%s node %d: exit code %d > 31 (EXIT_STEP has 8 entries, code >> 2)" % (kind, i, e["code"]))
                if kind == "veh" and e["to"] is not None:
                    p = P.veh.get(e["path"])
                    m = rec["veh"][e["to"]]
                    if p and ((p["pts"][0][0], p["pts"][0][2]) != (n["x"], n["z"]) or
                              (p["pts"][-1][0], p["pts"][-1][2]) != (m["x"], m["z"])):
                        w.append("vehicle edge %d->%d: curve %d runs (%d,%d)->(%d,%d) in %s, the nodes are (%d,%d)->(%d,%d)"
                                 % (i, e["to"], e["path"], p["pts"][0][0], p["pts"][0][2], p["pts"][-1][0],
                                    p["pts"][-1][2], lang, n["x"], n["z"], m["x"], m["z"]))
    return w


def check_turns(entry, masks, warns):
    """WARNING when the ENGLISH lanes and the matrix low half disagree."""
    rec = entry["rec0"]
    for net, cls in (("road", 0), ("rail", 1), ("subway", 2)):
        m = masks.get(net)
        if m is None:
            continue
        lt = LK.lane_turns(rec, cls)
        lo, hi = m & 0xFFFF, m >> 16
        # the tiler's final stage counts side s as an arm when row s (entry side s) has a bit in either half
        # (FUN_10019768 asks FUN_1000d73d with half 1, then half 0; TILER_SIM.md 6)
        arms = {f for f, _ in LK.mask_turns(lo) + LK.mask_turns(hi)}
        for f, t in sorted(lt):
            if not lo >> (4 * f + t) & 1:
                warns.append("%s: a %s lane drives %s -> %s, which the %s matrix (low half) does not allow"
                             % (entry["where"], LK.VCLASS[cls], LK.SIDES[f], LK.SIDES[t], net))
            for side in (f, t):
                if side not in arms:
                    warns.append("%s: a %s lane uses side %s, which the %s matrix does not count as an arm (empty row "
                                 "in both halves), so the tiler will not connect the neighbour there"
                                 % (entry["where"], LK.VCLASS[cls], LK.SIDES[side], net))
        for f, t in LK.mask_turns(lo):
            if lt and (f, t) not in lt:
                warns.append("%s: the %s matrix allows %s -> %s but no %s lane drives it"
                             % (entry["where"], net, LK.SIDES[f], LK.SIDES[t], LK.VCLASS[cls]))


def merge(stock, comps, variants, files, report):
    """Apply every package's lanes / connects. comps: [(pack name, compile_entries() result)]. variants: {id: variant
    dict of netpack.merge} (their "exemplar" and "trblk" are edited in place, before the Korea containers are
    written). files: netpack's output dict, extended with the stock containers this changes."""
    owner = {}
    for name, c in comps:
        report["warnings"] += c["warnings"]
        report["info"] += c["info"]
        for e in c["lanes"] + c["connects"]:
            kind = "lanes" if "records" in e else "connects"
            k = (kind, e["piece"])
            if k in owner and owner[k] != name:
                raise LanesError("piece %d: %s edited by both %s and %s" % (e["piece"], kind, owner[k], name))
            owner[k] = name
    stock_trb, stock_ex = {}, {}
    stock_exs = stock.exemplars()
    lane_entries = [e for _, c in comps for e in c["lanes"]]
    conn_entries = [e for _, c in comps for e in c["connects"]]
    for e in lane_entries:
        pid = e["piece"]
        masks = dict(e["masks"])
        for ce in conn_entries:
            if ce["piece"] == pid:
                masks.update(ce["masks"])
        base_masks = None
        if pid in variants:
            base_masks = LK.Game.masks_of(variants[pid]["exemplar"])
        elif pid in stock_exs:
            base_masks = LK.Game.masks_of(stock_exs[pid][1])
        check_turns(e, dict(base_masks or {}, **masks), report["warnings"])
        for lang, recs in e["records"].items():
            rel = _trb_rel(stock, lang)
            if pid in variants:
                cur = variants[pid]["trblk"].setdefault(rel, [])
                keep = [r for r in cur if r[1] not in {x[1] for x in recs}]
                variants[pid]["trblk"][rel] = keep + recs
            else:
                stock_trb.setdefault(rel, []).extend(recs)
        if pid not in variants:
            report["info"].append("%s: replaces the stock TrBlkAtt records of %d, states %s" % (e["where"], pid, e["states"]))
    for e in lane_entries + conn_entries:
        pid = e["piece"]
        masks = e["masks"]
        if not masks:
            continue
        if pid in variants:
            ex = variants[pid]["exemplar"]
            for net, m in masks.items():
                ex = LK.tkb1_set_u32(ex, LK.CONN_PROPS[net], m)
            variants[pid]["exemplar"] = ex
        elif pid in stock_exs:
            rel, payload = stock_exs[pid]
            cur = stock_ex.get((rel, pid), payload)
            for net, m in masks.items():
                cur = LK.tkb1_set_u32(cur, LK.CONN_PROPS[net], m)
            stock_ex[(rel, pid)] = cur
            report["info"].append("%s: stock exemplar %d props %s rewritten" % (
                e["where"], pid, ", ".join("%d=0x%08x" % (LK.CONN_PROPS[n], v) for n, v in sorted(masks.items()))))
        else:
            raise LanesError("%s: piece %d has no exemplar (stock or variant), so it has no turn matrix" % (e["where"], pid))
    for rel, recs in sorted(stock_trb.items()):
        files[rel] = replace_records(files.get(rel) or stock.read(rel), recs)
    by_rel = {}
    for (rel, pid), payload in stock_ex.items():
        by_rel.setdefault(rel, []).append((EX_GROUP, pid, EX_TYPE, payload))
    for rel, recs in sorted(by_rel.items()):
        files[rel] = replace_records(files.get(rel) or stock.read(rel), sorted(recs, key=lambda r: r[1]))
    report["lanes"] = [{"piece": e["piece"], "states": e["states"], "langs": sorted(e["records"]),
                        "masks": {k: "0x%08x" % v for k, v in e["masks"].items()}} for e in lane_entries]
    report["connects"] = [{"piece": e["piece"], "masks": {k: "0x%08x" % v for k, v in e["masks"].items()}}
                          for e in conn_entries]


def _trb_rel(stock, lang):
    for n in stock.listdir("Apps/Res/SSimData/" + lang):
        if n.lower() == "trblkatt.ixf":
            return "Apps/Res/SSimData/%s/%s" % (lang, n)
    raise LanesError("Apps\\Res\\SSimData\\%s has no TrBlkAtt.IXF" % lang)
