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
