"""trblkatt.py -- Apps\\Res\\SSimData\\<lang>\\TRBLKATT.IXF, the per-(piece, state) exemplars.

Key {type 0x625C6226, group 0x825C6289, instance pieceId * 0x100 + state} is what SIMNTWRK
FUN_1000d225 / FUN_1000d1cf and STRTSIM FUN_10013397 load [CONFIRMED @ SIMNTWRK 0x1000d225,
STRTSIM 0x10013397]. Measured 2026-10-12: 862 records in every one of the 7 language folders
(7 x 862 = 6,034, the count the capability map gives for "all" of them).

The blob is a nested `BIN\\r` serialization. Its field layout: see `parse()` and
NETMOD_CATALOG.md "TrBlkAtt"; anything not decoded is kept as raw bytes.
"""
import hashlib
import os
import struct
import sys

from . import paths

sys.path.insert(0, paths.TOOLS)
import ixf_parse  # noqa: E402

T_TYPE = 0x625C6226
T_GROUP = 0x825C6289


def records(path):
    recs, d = ixf_parse.parse(path)
    out = {}
    for r in recs:
        if r["type"] == T_TYPE and r["group"] == T_GROUP:
            out[r["instance"]] = d[r["offset"]:r["offset"] + r["size"]]
    return out


def index(game, lang="ENGLISH"):
    """-> {pieceId: {"states": [..], "sizes": {state: n}, "same_in_all_langs": bool}}."""
    base = records(game.trblkatt(lang))
    langs = game.trblkatt_langs()
    others = {l: records(game.trblkatt(l)) for l in langs if l != lang}
    out = {}
    for inst, blob in base.items():
        pid, st = inst >> 8, inst & 0xFF
        e = out.setdefault(pid, {"states": [], "sizes": {}, "same_in_all_langs": True,
                                 "lang": lang})
        e["states"].append(st)
        e["sizes"][st] = len(blob)
        try:
            e.setdefault("decoded", {})[st] = summary(blob)
        except (TrbError, struct.error, ValueError) as ex:
            e.setdefault("decoded", {})[st] = "PARSE ERROR: %s" % ex
        for o in others.values():
            if o.get(inst) != blob:
                e["same_in_all_langs"] = False
    for e in out.values():
        e["states"].sort()
    return out


def lang_summary(game):
    """-> [(lang, n_records, sha256 of the concatenated sorted payloads)]."""
    out = []
    for l in game.trblkatt_langs():
        r = records(game.trblkatt(l))
        h = hashlib.sha256()
        for k in sorted(r):
            h.update(struct.pack("<I", k) + r[k])
        out.append((l, len(r), h.hexdigest()[:16]))
    return out


def hexdump(b, width=16):
    lines = []
    for i in range(0, len(b), width):
        chunk = b[i:i + width]
        lines.append("%04x  %-*s %s" % (i, width * 3, " ".join("%02x" % c for c in chunk),
                                        "".join(chr(c) if 32 <= c < 127 else "." for c in chunk)))
    return "\n".join(lines)


# ----------------------------------------------------------------------------- parse
#
# Binary layout, read from the STRTSIM deserializers (2026-10-12, netcat child; class names
# from the Loki Linux demo libStrtSim.so are [LINUX-HINT]). Field values little-endian.
#
#   "BIN\r"                         line read byte by byte up to \r, first 3 chars vs "BIN"
#                                   (FUN_10013416, FUN_10021e2e); otherwise a text format
#   TrBlockAttrib  FUN_10016aa5     s32 x4 -> +0x14 [0], +0x20 [3], +0x1c [2], +0x18 [1], each
#                                   >> 8 (per-rotation altitude offset, read by FUN_1001c510);
#                                   u8 -> +0x24 bool (no reader found)
#   PPathGraphAttrib FUN_1000cf69   "BIN\r", u32 nodeCount, per node: u32 idx (discarded),
#                                   s32 v0 v1 v2, u32 edgeCount, per edge: s8 e0 (1-based target
#                                   node, -1 = exit), u8 e1, u32 e2 (PPATHATT key), u32 e3 (==1 flag)
#   VPathGraphAttrib FUN_1002066a   "BIN\r", u32 nodeCount, per node: u32 idx (discarded), s8 b0,
#                                   s32 x3, u32 edgeCount, per edge: s8 e0, u8 e1, u32 e2
#                                   (VPATHATT key), u32 e3 (stored as float e3 * 2.2222e-09)


class TrbError(Exception):
    pass


def _bin_line(b, o):
    j = b.index(b"\r", o)
    line = b[o:j].replace(b"\n", b"")
    if line[:3] != b"BIN":
        raise TrbError("text-format block at 0x%x (%r): not handled" % (o, line[:8]))
    return j + 1


def _graph(b, o, vpath):
    o = _bin_line(b, o)
    n, = struct.unpack_from("<I", b, o)
    o += 4
    nodes = []
    for _ in range(n):
        idx, = struct.unpack_from("<I", b, o)
        o += 4
        if vpath:
            b0, = struct.unpack_from("<b", b, o)
            o += 1
        else:
            b0 = None
        v = list(struct.unpack_from("<iii", b, o))
        o += 12
        ne, = struct.unpack_from("<I", b, o)
        o += 4
        edges = []
        for _ in range(ne):
            e0, e1, e2, e3 = struct.unpack_from("<bBII", b, o)
            o += 10
            edges.append({"to": e0 - 1 if e0 >= 0 else -1, "e1": e1, "key": e2, "e3": e3})
        node = {"idx": idx, "v": v, "edges": edges}
        if vpath:
            node["b0"] = b0
        nodes.append(node)
    return nodes, o


def parse(blob):
    """-> {"alt_offsets": [r0, r1, r2, r3], "flag": int, "ppath": [...], "vpath": [...]}.
    Raises TrbError unless the walk ends exactly at the end of the blob."""
    o = _bin_line(blob, 0)
    raw = struct.unpack_from("<iiii", blob, o)
    o += 16
    alt = [raw[0] >> 8, raw[3] >> 8, raw[2] >> 8, raw[1] >> 8]   # stored at +0x14 + i*4
    flag = blob[o]
    o += 1
    pp, o = _graph(blob, o, False)
    vp, o = _graph(blob, o, True)
    if o != len(blob):
        raise TrbError("walk ended at %d of %d bytes" % (o, len(blob)))
    return {"alt_offsets": alt, "flag": flag, "ppath": pp, "vpath": vp}


def summary(blob):
    p = parse(blob)
    pe = sum(len(n["edges"]) for n in p["ppath"])
    ve = sum(len(n["edges"]) for n in p["vpath"])
    pexit = sorted({e["e1"] for n in p["ppath"] for e in n["edges"] if e["to"] < 0})
    vexit = sorted({e["e1"] for n in p["vpath"] for e in n["edges"] if e["to"] < 0})
    return ("alt %s flag %d | ped %d nodes %d edges exits e1 %s | veh %d nodes %d edges exits e1 %s"
            % (p["alt_offsets"], p["flag"], len(p["ppath"]), pe, pexit, len(p["vpath"]), ve,
               vexit))
