#!/usr/bin/env python3
r"""newpiece.py - add a NEW network piece id to SimCity 3000 as data (netmod stage 3, 2026-10-12).

A network piece id resolves through four data hops (re/analysis/NEW_PIECE.md):

  1. exemplar  {0xE223741F, 0xA317745F, id}    OccupantAttribs*.IXF TKB1 record      [loaded by SIMNTWRK 0x1000c80b]
  2. attrib    prop 0x67 = {0x6300, grp, inst}  CSAttrib*.IXF "BIN\r" frame table
  3. pixels    each frame -> (group, instance)  Res\Sprites\*.DAT, type 0 = pixels, type 1 = anchor
  4. traffic   {0x625C6226, 0x825C6289, id*0x100+state}  SSimData\<lang>\TrBlkAtt.IXF  [SIMNTWRK 0x1000d225]
  plus the tiler: TilingRules\<NET>_GRND_Set.txt (membership -> piece class, SIMNTWRK 0x1001a5f2) and a
  SimpleRules RESULT line that emits id*256+state.

Where the new records go, chosen so NO shipped container is rewritten except where unavoidable:
  - SYS.PAK Default.ini [DBSegments] lists CSAttrib_Korea.IXF (0x55908ADB) and OccupantAttribs_Korea.IXF
    (0x55908ADC, also [OccAttribCache] Entry5). Neither file ships with this (GOG) install, so both are
    free container names the game already opens: the exemplar and the frame table go there, new files.
  - Res\Sprites is enumerated (*.DAT -> sc3dbssprite, SC3U 0x0040b761), so the pixels go in a NEW
    <group>_<name>.DAT file.
  - TrBlkAtt.IXF (per language) and the two TilingRules text files have no free slot: they are copied
    and edited (TrBlkAtt by ixf_insert.append, old bytes kept).

  py -3.12 re/tools/netmod/newpiece.py build --stock <tree> --out <moddir> [--id 20029] [--src 29]
          [--group 0x4E3D0001] [--tint blue] [--no-trblk] [--no-rules] [--no-set]
  py -3.12 re/tools/netmod/newpiece.py install --mod <moddir> --tree <test tree> --stock <stock tree>
  py -3.12 re/tools/netmod/newpiece.py uninstall --mod <moddir> --tree <test tree> --stock <stock tree>
  py -3.12 re/tools/netmod/newpiece.py check --tree <tree> --id 20029

install refuses any tree that is the repo root's game install or Simcity_stock itself, and de-links (delete +
copy) every file it replaces, so a hard-linked test tree never writes through to the stock files.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import ixf_parse        # noqa: E402
import qfs              # noqa: E402
import qfs_encode       # noqa: E402
import sprite_encode    # noqa: E402
import sprite_patch     # noqa: E402
import ixf_insert       # noqa: E402

EX_TYPE, EX_GROUP = 0xE223741F, 0xA317745F        # network piece exemplar key (SIMNTWRK 0x1000c80b)
CS_TYPE = 0x6300                                  # attrib table type used by prop 0x67 on pieces
KOREA_CS_GROUP = 0x55908ADB                       # [DBSegments] id of Res\Sprites\CSAttrib_Korea.IXF
KOREA_OCC_SEG = 0x55908ADC                        # [DBSegments] id of Res\Occupant\OccupantAttribs_Korea.IXF
TRB_TYPE, TRB_GROUP = 0x625C6226, 0x825C6289      # SIMNTWRK 0x1000d225
LANGS = ["DUTCH", "ENGLISH", "English-UK", "FRENCH", "GERMAN", "ITALIAN", "SWEDISH"]

OCC_KOREA = "Apps/Res/Occupant/OccupantAttribs_Korea.IXF"
CS_KOREA = "Apps/Res/Sprites/CSAttrib_Korea.IXF"
SET_FILE = "Apps/Res/TilingRules/ROAD_GRND_Set.txt"
RULE_FILE = "Apps/Res/TilingRules/ROAD_GRND_SimpleRules.txt"
# The two bare straight selectors (no neighbour conditions) of ROAD_GRND_SimpleRules.txt, T2-proven
# (verify/tilingrules_constructive): mask 10 (state 1) and mask 5 (state 0) -> piece 29.
STRAIGHT_RULES = [(10, 1), (5, 0)]


class NewPieceError(Exception):
    pass


# --- TKB1 (occupant exemplar) --------------------------------------------------------------------------

def tkb1_props(buf):
    """-> [(prop, type, count, payload_offset, payload_len)] over a TKB1 record."""
    if buf[:4] != b"TKB1":
        raise NewPieceError("not a TKB1 record")
    out, o = [], 4
    while o + 8 <= len(buf):
        prop, = struct.unpack_from("<I", buf, o)
        t, n = struct.unpack_from("<HH", buf, o + 4)
        o += 8
        if t == 7:
            ln, = struct.unpack_from("<I", buf, o)
            out.append((prop, t, n, o, 4 + ln))
            o += 4 + ln
        elif t == 3:
            out.append((prop, t, n, o, 4 * n))
            o += 4 * n
        elif t == 8:
            out.append((prop, t, n, o, 12 * n))
            o += 12 * n
        else:
            raise NewPieceError("TKB1 prop 0x%x has unknown type %d at +0x%x" % (prop, t, o - 8))
    if o != len(buf):
        raise NewPieceError("TKB1 walk ended at %d of %d bytes" % (o, len(buf)))
    return out


def tkb1_set_key(buf, prop, key):
    """Rewrite a type-8 single-key property in place -> new bytes."""
    b = bytearray(buf)
    for p, t, n, off, ln in tkb1_props(buf):
        if p == prop:
            if t != 8 or n != 1:
                raise NewPieceError("prop 0x%x is type %d count %d, not one key" % (prop, t, n))
            struct.pack_into("<3I", b, off, *key)
            return bytes(b)
    raise NewPieceError("prop 0x%x not present" % prop)


def tkb1_get(buf, prop):
    for p, t, n, off, ln in tkb1_props(buf):
        if p == prop:
            if t == 8:
                return struct.unpack_from("<%dI" % (3 * n), buf, off)
            if t == 3:
                return struct.unpack_from("<%dI" % n, buf, off)
            return buf[off + 4:off + ln].decode("latin-1")
    return None


# --- IXF helpers ---------------------------------------------------------------------------------------

def read(path):
    with open(path, "rb") as fh:
        return fh.read()


def find_record(path, rtype, group, instance):
    recs, d = ixf_parse.parse(path)
    for r in recs:
        if (r["type"], r["group"], r["instance"]) == (rtype, group, instance):
            return d[r["offset"]:r["offset"] + r["size"]]
    return None


def records(path):
    recs, d = ixf_parse.parse(path)
    return [(r["group"], r["instance"], r["type"], d[r["offset"]:r["offset"] + r["size"]]) for r in recs]


# --- CSAttrib frame table ------------------------------------------------------------------------------

def cs_frames(buf):
    """-> (frame count, [(entry offset, frameIndex, group, instance, flag)]) of a BIN\\r v1 table."""
    if buf[:4] != b"BIN\r":
        raise NewPieceError("not a BIN\\r attrib table")
    n, = struct.unpack_from("<H", buf, 0x16)
    out = []
    for k in range(n):
        o = 0x18 + 15 * k
        fi, g, i, fl = struct.unpack_from("<HIIB", buf, o)
        out.append((o, fi, g, i, fl))
    if 0x18 + 15 * n != len(buf):
        raise NewPieceError("frame table: %d frames but %d bytes" % (n, len(buf)))
    return n, out


def cs_retarget(buf, mapping):
    """Rewrite each frame's (group, instance) through mapping{(g,i): (g2,i2)} -> new bytes."""
    b = bytearray(buf)
    for o, fi, g, i, fl in cs_frames(buf)[1]:
        g2, i2 = mapping[(g, i)]
        struct.pack_into("<II", b, o + 2, g2, i2)
    return bytes(b)


# --- pixels --------------------------------------------------------------------------------------------

TINTS = {
    # 5/6/5 channel transforms; none can reach the magenta colour key (r stays <= 12 of 31)
    "blue": lambda r, g, b: (int(r * 0.35), int(g * 0.55), min(31, int(b * 0.8) + 12)),
    "green": lambda r, g, b: (int(r * 0.35), min(63, int(g * 0.8) + 20), int(b * 0.35)),
}


def tint_payload(payload, tint):
    """-> new sprite payload with every non-key pixel put through TINTS[tint] (565 or 555)."""
    kind, block, info = qfs.decode_record(payload)
    if kind != "qfs" or info["format"] != 1:
        raise NewPieceError("pixel record is not a format-1 sprite (kind %s)" % kind)
    surf, m = sprite_encode.block_to_surface(block)
    key = m["key"]
    f = TINTS[tint]
    out = []
    for p in surf:
        if p == key:
            out.append(p)
            continue
        if key == 0x7C1F:                                  # RGB555
            r, g, b = (p >> 10) & 31, (p >> 5) & 31, p & 31
            r2, g2, b2 = f(r, g * 2, b)
            v = (r2 << 10) | ((min(63, g2) >> 1) << 5) | b2
        else:                                              # RGB565
            r, g, b = (p >> 11) & 31, (p >> 5) & 63, p & 31
            r2, g2, b2 = f(r, g, b)
            v = (r2 << 11) | (g2 << 5) | b2
        if v == key:
            v ^= 1
        out.append(v)
    nb = sprite_encode.encode(out, m["w"], m["h"], key, m["b"], m["a"])
    return sprite_patch.pack_payload(info, qfs_encode.compress_stream(nb, quick=1))


def sprite_records(sprites_dir, wanted):
    """-> {(group, instance): {type: payload}} for every (group, instance) in `wanted`, any *.DAT."""
    out = {}
    groups = {g for g, _ in wanted}
    for name in sorted(os.listdir(sprites_dir)):
        if not name.upper().endswith(".DAT"):
            continue
        try:
            pre = int(name.split("_")[0], 16)
        except ValueError:
            pre = None
        if pre is not None and pre not in groups:
            continue
        for g, i, t, p in records(os.path.join(sprites_dir, name)):
            if (g, i) in wanted:
                out.setdefault((g, i), {})[t] = p
    return out


# --- text files ----------------------------------------------------------------------------------------

def set_add(text, new_id):
    """Add new_id before the closing brace of a BRACED Set file (bytes in, bytes out)."""
    ids = [int(x) for x in re.findall(rb"\d+", text)]
    if new_id in ids:
        return text
    k = text.rindex(b"}")
    return text[:k] + b", %d" % new_id + text[k:]


def rules_retarget(text, src, new_id):
    """Point the two bare straight selectors' RESULT at new_id (bytes in, bytes out)."""
    for mask, state in STRAIGHT_RULES:
        old = b"1,%d\r\n2,0\r\n4,1\r\n5,255,%d\r\n" % (mask, src * 256 + state)
        new = b"1,%d\r\n2,0\r\n4,1\r\n5,255,%d\r\n" % (mask, new_id * 256 + state)
        n = text.count(old)
        if n != 1:
            raise NewPieceError("bare straight rule mask %d -> %d found %d times, expected 1" % (mask, src, n))
        text = text.replace(old, new)
    return text


# --- build ---------------------------------------------------------------------------------------------

def build(a):
    stock = os.path.abspath(a.stock)
    occ_path = os.path.join(stock, "Apps/Res/Occupant/OccupantAttribs.IXF")
    ex = find_record(occ_path, EX_TYPE, EX_GROUP, a.src)
    if ex is None:
        raise NewPieceError("no exemplar for piece %d in %s" % (a.src, occ_path))
    for name in os.listdir(os.path.join(stock, "Apps/Res/Occupant")):
        p = os.path.join(stock, "Apps/Res/Occupant", name)
        if find_record(p, EX_TYPE, EX_GROUP, a.id) is not None:
            raise NewPieceError("piece id %d already has an exemplar in %s" % (a.id, name))
    cs_key = tkb1_get(ex, 0x67)
    cs = find_record(os.path.join(stock, "Apps/Res/Sprites/CSATTRIB.IXF"), *cs_key)
    if cs is None:
        raise NewPieceError("attrib table %r not found" % (cs_key,))
    nframes, frames = cs_frames(cs)
    src_keys = sorted({(g, i) for _, _, g, i, _ in frames})
    sprites_dir = os.path.join(stock, "Apps/Res/Sprites")
    art = sprite_records(sprites_dir, set(src_keys))
    missing = [k for k in src_keys if k not in art or 0 not in art[k] or 1 not in art[k]]
    if missing:
        raise NewPieceError("frames without pixel+anchor records: %r" % missing[:4])
    mapping = {(g, i): (a.group, (a.id << 16) | (i & 0xFFFF)) for g, i in src_keys}

    files = {}
    # 1. exemplar: copy of the source piece, prop 0x67 -> the new frame table in CSAttrib_Korea
    new_cs_key = (CS_TYPE, KOREA_CS_GROUP, a.id)
    ex_new = tkb1_set_key(ex, 0x67, new_cs_key)
    files[OCC_KOREA] = ixf_insert.new_container([(EX_GROUP, a.id, EX_TYPE, ex_new)])
    # 2. frame table
    files[CS_KOREA] = ixf_insert.new_container([(KOREA_CS_GROUP, a.id, CS_TYPE, cs_retarget(cs, mapping))])
    # 3. pixels: anchor (type 1) verbatim, pixels (type 0) tinted; anchor first, as Roads_2.DAT orders them
    recs = []
    for k in src_keys:
        g2, i2 = mapping[k]
        recs.append((g2, i2, 1, art[k][1]))
        recs.append((g2, i2, 0, tint_payload(art[k][0], a.tint) if a.tint != "none" else art[k][0]))
    dat_name = "Apps/Res/Sprites/%08X_NewPiece%d.DAT" % (a.group, a.id)
    files[dat_name] = ixf_insert.new_container(recs)
    # 4. traffic attributes, every language
    if not a.no_trblk:
        for lang in LANGS:
            rel = "Apps/Res/SSimData/%s/TrBlkAtt.IXF" % lang
            p = os.path.join(stock, rel)
            if not os.path.exists(p):
                continue
            d = read(p)
            add = [(TRB_GROUP, a.id * 0x100 + (i & 0xFF), TRB_TYPE, pl)
                   for g, i, t, pl in records(p) if t == TRB_TYPE and i >> 8 == a.src]
            if not add:
                raise NewPieceError("%s has no TrBlkAtt record for piece %d" % (rel, a.src))
            new = ixf_insert.append(d, add)
            probs = ixf_insert.check_append(d, new, add)
            if probs:
                raise NewPieceError("%s: %s" % (rel, probs))
            files[rel] = new
    # 5. tiler
    if not a.no_set:
        files[SET_FILE] = set_add(read(os.path.join(stock, SET_FILE)), a.id)
    if not a.no_rules:
        files[RULE_FILE] = rules_retarget(read(os.path.join(stock, RULE_FILE)), a.src, a.id)

    os.makedirs(a.out, exist_ok=True)
    manifest = {"id": a.id, "src": a.src, "group": "0x%08X" % a.group, "tint": a.tint,
                "frames": nframes, "sprite_records": len(recs), "files": {}}
    for rel, data in sorted(files.items()):
        dst = os.path.join(a.out, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as fh:
            fh.write(data)
        sp = os.path.join(stock, rel)
        manifest["files"][rel] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
                                  "replaces_stock": os.path.exists(sp),
                                  "stock_sha256": hashlib.sha256(read(sp)).hexdigest() if os.path.exists(sp) else None}
    with open(os.path.join(a.out, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)
    for rel, m in sorted(manifest["files"].items()):
        print("%-55s %8d bytes  %s" % (rel, m["bytes"], "replaces stock" if m["replaces_stock"] else "NEW file"))
    print("piece %d from %d: %d frames, %d sprite records, group 0x%08X, tint %s"
          % (a.id, a.src, nframes, len(recs), a.group, a.tint))
    return 0


# --- install / uninstall into a hard-linked test tree --------------------------------------------------

def _guard_tree(tree):
    t = os.path.normcase(os.path.abspath(tree))
    root = os.path.normcase(os.path.abspath(os.path.join(HERE, "..", "..", "..")))
    for bad in (r"C:\Users\maria\Desktop\Proyectos\Simcity", r"C:\Users\maria\Desktop\Proyectos\Simcity_stock", root):
        if t == os.path.normcase(bad):
            raise NewPieceError("refusing to write into %s (live install or stock reference)" % tree)
    if not os.path.exists(os.path.join(tree, "Apps", "SC3U.exe")):
        raise NewPieceError("%s has no Apps\\SC3U.exe" % tree)


def install(a):
    _guard_tree(a.tree)
    man = json.load(open(os.path.join(a.mod, "manifest.json")))
    for rel, m in sorted(man["files"].items()):
        dst = os.path.join(a.tree, rel)
        if os.path.exists(dst):
            os.remove(dst)                                  # de-link: never write through a hard link
        shutil.copyfile(os.path.join(a.mod, rel), dst)
        ok = hashlib.sha256(read(dst)).hexdigest() == m["sha256"]
        print("%-55s %s" % (rel, "installed" if ok else "HASH MISMATCH"))
        if not ok:
            return 1
    stock_ok = all(hashlib.sha256(read(os.path.join(a.stock, rel))).hexdigest() == m["stock_sha256"]
                   for rel, m in man["files"].items() if m["replaces_stock"])
    print("stock files unchanged: %s" % stock_ok)
    return 0 if stock_ok else 1


def uninstall(a):
    _guard_tree(a.tree)
    man = json.load(open(os.path.join(a.mod, "manifest.json")))
    for rel, m in sorted(man["files"].items()):
        dst = os.path.join(a.tree, rel)
        if os.path.exists(dst):
            os.remove(dst)
        if m["replaces_stock"]:
            os.link(os.path.join(a.stock, rel), dst)        # back to a hard link of the stock file
            print("%-55s relinked to stock" % rel)
        else:
            print("%-55s removed" % rel)
    return 0


def check(a):
    """Read the new piece back out of a tree through the same keys the game uses."""
    tree = a.tree
    occ = os.path.join(tree, OCC_KOREA)
    ex = find_record(occ, EX_TYPE, EX_GROUP, a.id) if os.path.exists(occ) else None
    print("exemplar {0x%08X,0x%08X,%d}: %s" % (EX_TYPE, EX_GROUP, a.id, "found" if ex else "MISSING"))
    if not ex:
        return 1
    key = tkb1_get(ex, 0x67)
    print("  name %r type %s prop 0x67 %s" % (tkb1_get(ex, 0x64), tkb1_get(ex, 0x65), ["0x%X" % v for v in key]))
    cs = find_record(os.path.join(tree, CS_KOREA), *key)
    n, fr = cs_frames(cs)
    print("frame table: %d frames, groups %s" % (n, sorted({"0x%08X" % g for _, _, g, _, _ in fr})))
    art = sprite_records(os.path.join(tree, "Apps/Res/Sprites"), {(g, i) for _, _, g, i, _ in fr})
    full = sum(1 for _, _, g, i, _ in fr if 0 in art.get((g, i), {}) and 1 in art.get((g, i), {}))
    print("frames with pixel+anchor records: %d/%d" % (full, n))
    for lang in LANGS:
        p = os.path.join(tree, "Apps/Res/SSimData/%s/TrBlkAtt.IXF" % lang)
        if os.path.exists(p):
            got = [i for g, i, t, _ in records(p) if t == TRB_TYPE and i >> 8 == a.id]
            print("TrBlkAtt %-11s %s" % (lang, [hex(i) for i in got]))
    s = read(os.path.join(tree, SET_FILE))
    print("ROAD Set holds %d: %s" % (a.id, a.id in [int(x) for x in re.findall(rb"\d+", s)]))
    r = read(os.path.join(tree, RULE_FILE))
    print("SimpleRules results -> %d: %d" % (a.id, sum(r.count(b"5,255,%d\r\n" % (a.id * 256 + st)) for st in range(4))))
    return 0 if full == n else 1


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--stock", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--id", type=int, default=20029)
    b.add_argument("--src", type=int, default=29)
    b.add_argument("--group", type=lambda v: int(v, 0), default=0x4E3D0001)
    b.add_argument("--tint", choices=sorted(TINTS) + ["none"], default="blue")
    b.add_argument("--no-trblk", action="store_true")
    b.add_argument("--no-rules", action="store_true")
    b.add_argument("--no-set", action="store_true")
    for name in ("install", "uninstall"):
        s = sub.add_parser(name)
        s.add_argument("--mod", required=True)
        s.add_argument("--tree", required=True)
        s.add_argument("--stock", required=True)
    c = sub.add_parser("check")
    c.add_argument("--tree", required=True)
    c.add_argument("--id", type=int, default=20029)
    a = ap.parse_args(argv[1:])
    if a.cmd == "build" and not (0 < a.id <= 0xFFFF):
        raise NewPieceError("piece id must fit 16 bits (save word1 & 0xffff, SIMNTWRK 0x1000c80b)")
    return {"build": build, "install": install, "uninstall": uninstall, "check": check}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
