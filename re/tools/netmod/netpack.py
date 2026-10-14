#!/usr/bin/env python3
r"""netpack.py - network mod packages for SimCity 3000: new / validate / build / install / uninstall / list (2026-10-13).

A package is one folder with a manifest.json (schema: netpack.schema.json, guide: re/analysis/NETPACK.md) that declares
  variants   new piece ids that behave as a stock piece (base) and draw their own art
  reskins    new art for the frames of existing pieces
  rule_edits structured TilingRules edits (netpack_rules.py, format agreed with netrules), so the tiler places the variants
  names      piece names (per language), ini  key edits inside SYS.PAK members
Art is either derived from a stock piece (recolour) or authored as PNG, one file per frame. No game art is stored in a
package unless its author puts PNGs there.

Install merges EVERY installed package into one set of files, computed from the stock files each time, in package
NAME order (so install order does not change a byte):
  Apps\Res\Occupant\OccupantAttribs_Korea.IXF   variant exemplars        (SYS.PAK [DBSegments] 0x55908ADC, not shipped)
  Apps\Res\Sprites\CSAttrib_Korea.IXF           variant frame tables     (SYS.PAK [DBSegments] 0x55908ADB, not shipped)
  Apps\Res\Sprites\4E3D00nn_netpack.DAT         new pixel + anchor records (Res\Sprites\*.DAT is enumerated, SC3U 0x0040b761)
  Apps\Res\Sprites\CSATTRIB*.IXF                copy with reskinned pieces' frames pointed at the new records
  Apps\Res\SSimData\<lang>\TrBlkAtt.IXF         copy + the variants' traffic records (base records re-keyed)
  Apps\Res\TilingRules\*.txt                    copies with the variant ids in the Set and the packages' rule edits
  Apps\Res\Text\<lang>\SC3StringsNetpack.IXF    variant names (new file; the game lists Text\<lang>\*.* at startup)
  Apps\Sys\SYS.PAK                              copy with the ini edits
plus mods\netmod\tables\<package>.txt (variant -> base, read by sc3netmod.dll).

Two install modes (ledger: <root>\mods\netmod\ledger.json):
  overlay (default)  files go to <root>\mods\netmod\overlay\<same path>; NOTHING under Apps\ is written.
                     sc3netmod.dll serves them in place of the stock files (arm F, verify/netpack/RESULTS.md).
                     Without the DLL the game is exactly stock.
  direct             files are written into Apps\ (each replaced stock file backed up to mods\netmod\backup\ first,
                     the target deleted before writing so a hard-linked tree never writes through). For a game run
                     without sc3netmod.dll; variants then lose crossings and stock-safe saves (NEW_PIECE.md 4).
Uninstall re-merges what is left; when the last package goes, every file is restored byte-identical (hash-checked)
and mods\netmod is deleted.

  py -3.12 netpack.py new <dir> [--name N] [--id 20100] [--base 29]
  py -3.12 netpack.py validate <pack> [--stock <tree>] [--tree <install tree>]
  py -3.12 netpack.py build <pack> --out <dir> [--stock <tree>]
  py -3.12 netpack.py install <pack> --tree <game root> [--mode overlay|direct] [--allow-tree]
  py -3.12 netpack.py uninstall <name> --tree <game root> [--allow-tree]
  py -3.12 netpack.py list --tree <game root>
  py -3.12 netpack.py export-art <piece id> <dir> [--stock <tree>]     # base frames as PNG, for authoring
  py -3.12 netpack.py selftest [--stock <tree>]                        # offline checks U1..U7 (verify/netpack/PRE.md; U7 rule lint)
--stock defaults to the game root found by paths.game_root() ($SC3_GAME_ROOT, walking up, or the main checkout).
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import ixf_parse        # noqa: E402
import qfs              # noqa: E402
import qfs_encode       # noqa: E402
import sprite_encode    # noqa: E402
import sprite_patch     # noqa: E402
import syspak_parse     # noqa: E402
import ixf_insert       # noqa: E402
import newpiece as NP   # noqa: E402
import netpack_rules as NR  # noqa: E402
import netpack_bridges as NB  # noqa: E402  task netbridge: inheritance, replace_base, bridges, crossings
import netramp as RAMP  # noqa: E402  ramps / on-ramps / tunnels / slopes (NET_RAMPS.md)
from PIL import Image   # noqa: E402  png_dir art (any size with anchors.json, NET_ART.md)
import netpack_lanes as NL  # noqa: E402  task lanekit: lanes (TrBlkAtt) and connects (turn matrices), NET_LANES.md
import netpack_templates as TPL  # noqa: E402  task multitile: multi-cell templates (MULTITILE.md)

SCHEMA_VERSION = 1
SCHEMA_FILE = os.path.join(HERE, "netpack.schema.json")

NETMOD = "mods/netmod"
LEDGER = NETMOD + "/ledger.json"
OVERLAY = NETMOD + "/overlay"
BACKUP = NETMOD + "/backup"
TABLES = NETMOD + "/tables"
PACKS = NETMOD + "/packs"

OCC_KOREA = NP.OCC_KOREA
CS_KOREA = NP.CS_KOREA
CROSS = NETMOD + "/cross"                      # task netbridge: <pack>.txt crossing tables for sc3netmod XCROSS
LEGACY_TABLE = NP.VARIANT_TABLE                 # newpiece.py's single-mod table
EX_TYPE, EX_GROUP, CS_TYPE = NP.EX_TYPE, NP.EX_GROUP, NP.CS_TYPE
KOREA_CS_GROUP = NP.KOREA_CS_GROUP
TRB_TYPE, TRB_GROUP = NP.TRB_TYPE, NP.TRB_GROUP
TEXT_TYPE, TEXT_GROUP = 0x2026960B, 0xA1096A4F  # exemplar prop 0x6D key {type, group, id} (netmod/exemplars.py)
ART_GROUP0 = 0x4E3D0001                         # first group of the merged art containers (newpiece's group)
ART_MAX_RECORDS = 1022                          # per container: the shipped 0x5000-byte index holds 1,024 slots
NAME_FILE = "SC3StringsNetpack.IXF"
SYSPAK = "Apps/Sys/SYS.PAK"
NETS = ("ROAD", "RAIL", "POWR", "HWAY", "PIPE", "SUBW")
RESERVED_IDS = range(15130, 15142)              # special-cased by the classifier FUN_1001a5f2 (NEW_PIECE.md 3)
PRESETS = {                                     # recolour presets on 8-bit channels: (mul r,g,b), (add r,g,b)
    "red": ((1.0, 0.35, 0.35), (60, 0, 0)),
    "gray": ((0.6, 0.6, 0.6), (40, 40, 40)),
    "yellow": ((1.0, 0.95, 0.35), (50, 45, 0)),
}
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")


class NetpackError(Exception):
    pass


def sha(b):
    return hashlib.sha256(b).hexdigest()


def rd(path):
    with open(path, "rb") as fh:
        return fh.read()


def norm(rel):
    return rel.replace("\\", "/")


# =================================================================== TKB1 (occupant exemplar) properties

def tkb1_props(buf):
    """-> [(prop, type, count, payload offset, payload length)]. Types 3 (u32 x n), 7 (u32 length + text), 8 (key
    triple x n) as newpiece.py; type 1 = n bytes, measured on pieces 11608/11636/11637 (prop 0x6e: 1 byte, then the
    next property header starts right after it)."""
    if buf[:4] != b"TKB1":
        raise NetpackError("not a TKB1 record")
    out, o = [], 4
    while o + 8 <= len(buf):
        prop, = struct.unpack_from("<I", buf, o)
        t, n = struct.unpack_from("<HH", buf, o + 4)
        o += 8
        if t == 7:
            ln = struct.unpack_from("<I", buf, o)[0] + 4
        elif t == 3:
            ln = 4 * n
        elif t == 8:
            ln = 12 * n
        elif t == 1:
            ln = n
        else:
            raise NetpackError("TKB1 prop 0x%x has unknown type %d at +0x%x" % (prop, t, o - 8))
        out.append((prop, t, n, o, ln))
        o += ln
    if o != len(buf):
        raise NetpackError("TKB1 walk ended at %d of %d bytes" % (o, len(buf)))
    return out


def tkb1_key(buf, prop):
    """-> the key triple of a type-8 single-key property, or None."""
    for p, t, n, off, ln in tkb1_props(buf):
        if p == prop and t == 8 and n == 1:
            return struct.unpack_from("<3I", buf, off)
    return None


def tkb1_set_key(buf, prop, key):
    b = bytearray(buf)
    for p, t, n, off, ln in tkb1_props(buf):
        if p == prop:
            if t != 8 or n != 1:
                raise NetpackError("prop 0x%x is type %d count %d, not one key" % (prop, t, n))
            struct.pack_into("<3I", b, off, *key)
            return bytes(b)
    raise NetpackError("prop 0x%x not present" % prop)


# =================================================================== stock view

class Stock:
    """Read-only view of the stock game files of one tree. In direct mode, files the ledger replaced are read from
    their backup, and files the ledger created read as absent."""

    def __init__(self, root, ledger=None):
        self.root = os.path.abspath(root)
        self.owned = {}
        if ledger and ledger.get("mode") == "direct":
            self.owned = ledger.get("files", {})
        if not os.path.isfile(os.path.join(self.root, "Apps", "SC3U.exe")):
            raise NetpackError("%s has no Apps\\SC3U.exe" % root)
        self._ex = None
        self._cs = None

    def path(self, rel):
        rel = norm(rel)
        o = self.owned.get(rel)
        if o is not None:
            return os.path.join(self.root, BACKUP, rel) if o.get("stock_sha256") else None
        p = os.path.join(self.root, rel)
        return p if os.path.isfile(p) else None

    def exists(self, rel):
        return self.path(rel) is not None

    def read(self, rel):
        p = self.path(rel)
        if p is None:
            raise NetpackError("stock file %s not found" % rel)
        return rd(p)

    def listdir(self, rel):
        d = os.path.join(self.root, rel)
        out = []
        for n in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            r = norm(os.path.join(rel, n))
            if os.path.isfile(os.path.join(d, n)) and self.exists(r):
                out.append(n)
        return out

    def records(self, rel):
        p = self.path(rel)
        recs, d = ixf_parse.parse(p)
        return [(r["group"], r["instance"], r["type"], d[r["offset"]:r["offset"] + r["size"]]) for r in recs]

    def exemplars(self):
        """-> {id: (container rel, payload)} over every Occupant\\*.IXF (first container in name order wins)."""
        if self._ex is None:
            self._ex = {}
            for n in self.listdir("Apps/Res/Occupant"):
                if not n.lower().endswith(".ixf"):
                    continue
                rel = "Apps/Res/Occupant/" + n
                for g, i, t, p in self.records(rel):
                    if t == EX_TYPE and g == EX_GROUP:
                        self._ex.setdefault(i, (rel, p))
        return self._ex

    def frame_tables(self):
        """-> {(type, group, instance): (container rel, payload)} over every Sprites\\CSAttrib*.IXF."""
        if self._cs is None:
            self._cs = {}
            for n in self.listdir("Apps/Res/Sprites"):
                if not (n.lower().startswith("csattrib") and n.lower().endswith(".ixf")):
                    continue
                rel = "Apps/Res/Sprites/" + n
                for g, i, t, p in self.records(rel):
                    self._cs.setdefault((t, g, i), (rel, p))
        return self._cs

    def set_ids(self, net):
        return set(NR.braced_ids(self.read("Apps/Res/TilingRules/%s_GRND_Set.txt" % net)))

    def set_files_of(self, pid):
        """-> frozenset of the Set lists (6 networks + DIAG) that hold pid."""
        out = {n for n in NETS if pid in self.set_ids(n)}
        if self.exists("Apps/Res/TilingRules/DIAG_Set.txt") and \
                pid in set(NR.braced_ids(self.read("Apps/Res/TilingRules/DIAG_Set.txt"))):
            out.add("DIAG")
        return frozenset(out)

    def ramp_tables(self):
        """netramp.py's registry with the stock values read from this tree's SIMNTWRK.DLL."""
        if getattr(self, "_rt", None) is None:
            from netmod.pe_tables import Simntwrk
            from netmod import paths as _paths
            try:
                self._rt = RAMP.tables(Simntwrk(_paths.Game(self.root)))
            except ValueError as e:
                raise NetpackError("SIMNTWRK.DLL of %s: %s" % (self.root, e))
        return self._rt

    def lang_dirs(self, sub):
        d = os.path.join(self.root, "Apps/Res", sub)
        return sorted(n for n in os.listdir(d) if os.path.isdir(os.path.join(d, n))) if os.path.isdir(d) else []

    def sprite_records(self, wanted):
        """-> {(group, instance): {type: payload}} for the wanted keys, over every Sprites\\*.DAT."""
        out = {}
        groups = {g for g, _ in wanted}
        for n in self.listdir("Apps/Res/Sprites"):
            if not n.upper().endswith(".DAT"):
                continue
            try:
                pre = int(n.split("_")[0], 16)
            except ValueError:
                pre = None
            if pre is not None and pre not in groups:
                continue
            for g, i, t, p in self.records("Apps/Res/Sprites/" + n):
                if (g, i) in wanted:
                    out.setdefault((g, i), {})[t] = p
        return out


# =================================================================== manifest

def load_manifest(pack_dir):
    p = os.path.join(pack_dir, "manifest.json")
    if not os.path.isfile(p):
        raise NetpackError("%s has no manifest.json" % pack_dir)
    try:
        with open(p, encoding="utf-8") as fh:
            m = json.load(fh)
    except ValueError as e:
        raise NetpackError("manifest.json: %s" % e)
    schema_check(m)
    return m


def schema_check(m):
    """JSON Schema (netpack.schema.json) when jsonschema is installed, plus the checks it cannot express."""
    try:
        import jsonschema
    except ImportError:
        jsonschema = None
    if jsonschema is not None:
        with open(SCHEMA_FILE, encoding="utf-8") as fh:
            schema = json.load(fh)
        errs = sorted(jsonschema.Draft202012Validator(schema).iter_errors(m), key=lambda e: list(e.path))
        if errs:
            raise NetpackError("manifest.json does not match the schema:\n  " + "\n  ".join(
                "%s: %s" % ("/".join(str(x) for x in e.path) or "(top)", e.message) for e in errs[:12]))
    if m.get("netpack") != SCHEMA_VERSION:
        raise NetpackError("manifest \"netpack\" is %r; this tool reads version %d" % (m.get("netpack"), SCHEMA_VERSION))
    if not NAME_RE.match(str(m.get("name", ""))):
        raise NetpackError("manifest \"name\" must be lower case letters, digits, - or _ (max 48)")


# =================================================================== art

def _frames_of(stock, art_piece):
    ex = stock.exemplars().get(art_piece)
    if ex is None:
        raise NetpackError("piece %d has no exemplar in Apps\\Res\\Occupant" % art_piece)
    key = tkb1_key(ex[1], 0x67)
    if not key or len(key) != 3:
        raise NetpackError("piece %d exemplar has no frame-table key (prop 0x67)" % art_piece)
    hit = stock.frame_tables().get(tuple(key))
    if hit is None:
        raise NetpackError("piece %d: frame table {0x%X,0x%X,%d} not in any CSAttrib*.IXF" % ((art_piece,) + tuple(key)))
    n, frames = NP.cs_frames(hit[1])
    return tuple(key), hit, frames


def frame_png_name(k):
    """frame position k -> PNG file name. Layout over all 380 pieces (netcat selftest): zoom (k % 20) // 4,
    rotation slot k % 4, layer k // 20."""
    z, r, layer = (k % 20) // 4, k % 4, k // 20
    return ("z%d_r%d.png" % (z, r)) if layer == 0 else ("l%d_z%d_r%d.png" % (layer, z, r))


def _recolor_fn(spec):
    if isinstance(spec, str) and spec in NP.TINTS:          # a {"mul", "add"} dict is not hashable
        return ("tint", spec)
    if isinstance(spec, str):
        if spec not in PRESETS:
            raise NetpackError("recolor %r: presets are %s, or {\"mul\": [r,g,b], \"add\": [r,g,b]}"
                               % (spec, ", ".join(sorted(list(NP.TINTS) + list(PRESETS)))))
        mul, add = PRESETS[spec]
    else:
        mul, add = tuple(spec.get("mul", (1, 1, 1))), tuple(spec.get("add", (0, 0, 0)))
    return ("muladd", (mul, add))


def recolor_payload(payload, spec):
    """-> new format-1 sprite payload. "blue"/"green" are newpiece's 5/6/5 tints (the game-proven 20029 art);
    everything else is mul/add on 8-bit channels. A pixel never lands on the colour key."""
    kind, arg = _recolor_fn(spec)
    if kind == "tint":
        return NP.tint_payload(payload, arg)
    mul, add = arg
    k, block, info = qfs.decode_record(payload)
    if k != "qfs" or info["format"] != 1:
        raise NetpackError("pixel record is not a format-1 sprite (kind %s)" % k)
    surf, m = sprite_encode.block_to_surface(block)
    key = m["key"]
    c = lambda v, i: max(0, min(255, int(v * mul[i] + add[i] + 0.5)))   # noqa: E731
    out = []
    for p in surf:
        if p == key:
            out.append(p)
            continue
        if key == 0x7C1F:                                   # RGB555
            r, g, b = ((p >> 10) & 31) << 3, ((p >> 5) & 31) << 3, (p & 31) << 3
            v = sprite_patch.quantize555(c(r, 0), c(g, 1), c(b, 2))
        else:                                               # RGB565
            r, g, b = ((p >> 11) & 31) << 3, ((p >> 5) & 63) << 2, (p & 31) << 3
            v = sprite_patch.quantize565(c(r, 0), c(g, 1), c(b, 2))
        if v == key:
            v ^= 1
        out.append(v)
    nb = sprite_encode.encode(out, m["w"], m["h"], key, m["b"], m["a"])
    return sprite_patch.pack_payload(info, qfs_encode.compress_stream(nb, quick=1))


def sprite_size(payload):
    k, block, info = qfs.decode_record(payload)
    if k != "qfs" or info["format"] != 1:
        return None
    _, m = sprite_encode.block_to_surface(block)
    return m["w"], m["h"]


DRAW_FLAGS_OFF = 0x12          # frame table header u32 after AnimFrames (+0x10), RegRects (+0x11); reader SIMSPR 0x10001c90
FIRST_PASS = 0x80             # -> view cell flag bit 0 (0x100192aa): drawn in the pass before every other occupant (0x1000dc17)


def _finish_art(res, art, where):
    """art.first_pass: true / false sets / clears the frame table's first-pass draw bit (NET_ART.md 8). Road pieces
    ship it set (29, 39), so a sprite TALLER than its base frame is overdrawn above the ground by the second pass
    in some view rotations (arm D, verify/artkit). -> res with "cs" edited and "warnings"."""
    res["warnings"] = []
    cs = bytearray(res["cs"])
    flags, = struct.unpack_from("<I", cs, DRAW_FLAGS_OFF)
    if "first_pass" in art:
        flags = (flags | FIRST_PASS) if art["first_pass"] else (flags & ~FIRST_PASS)
        struct.pack_into("<I", cs, DRAW_FLAGS_OFF, flags)
        res["cs"] = bytes(cs)
    elif flags & FIRST_PASS:
        src_t = res.get("src_T", {})
        taller = [k for k in res["keys"] if k in src_t and struct.unpack_from("<h", res["anchor"][k], 2)[0] > src_t[k]]
        if taller:
            res["warnings"].append("%s: %d frame(s) are taller than the source frames but the table keeps the "
                                   "first-pass draw bit (0x80): their top will be overdrawn in some rotations; "
                                   "set art.first_pass to false" % (where, len(taller)))
    return res


def compile_art(stock, pack_dir, art, default_piece, where):
    """art spec -> {"from", "cs_key", "cs_rel", "cs", "frames", "keys", "pix", "anchor"}.
    keys = the distinct (group, instance) records of the source frames, in first-use order."""
    art = art or {}
    src = art.get("from", default_piece)
    cs_key, (cs_rel, cs), frames = _frames_of(stock, src)
    keys = []
    for _, _, g, i, _ in frames:
        if (g, i) not in keys:
            keys.append((g, i))
    recs = stock.sprite_records(set(keys))
    missing = [k for k in keys if 0 not in recs.get(k, {}) or 1 not in recs.get(k, {})]
    if missing:
        raise NetpackError("%s: art of piece %d: frames without pixel+anchor records %r" % (where, src, missing[:4]))
    pix = {k: recs[k][0] for k in keys}
    if art.get("recolor") is not None:
        for k in keys:
            try:
                pix[k] = recolor_payload(pix[k], art["recolor"])
            except Exception as e:  # format-0 masks and the like: say which record
                raise NetpackError("%s: recolor of record (0x%08X, 0x%08X): %s" % (where, k[0], k[1], e))
    if art.get("recipe"):
        if art.get("png_dir"):
            raise NetpackError("%s: art has both png_dir and recipe" % where)
        rp = os.path.join(pack_dir, art["recipe"])
        if not os.path.isfile(rp):
            raise NetpackError("%s: recipe %s does not exist" % (where, art["recipe"]))
        import netart                                   # artkit compositor (NET_ART.md 6), stock frames only
        d = tempfile.mkdtemp(prefix="netpack_recipe_")
        netart.set_game(stock.root)
        try:
            netart.compose(json.load(open(rp, encoding="utf-8")), d, src_dir=os.path.dirname(rp))
        except Exception as e:
            raise NetpackError("%s: recipe %s: %s" % (where, art["recipe"], e))
        art = dict(art, png_dir=d)
    if art.get("png_dir"):
        d = os.path.join(pack_dir, art["png_dir"])
        if not os.path.isdir(d):
            raise NetpackError("%s: png_dir %s does not exist" % (where, art["png_dir"]))
        anchors = _png_anchors(d, where)
        anc = {k: recs[k][1] for k in keys}
        pos_keys = [(g, i) for _, _, g, i, _ in frames]
        owner = {}                      # record key -> (png bytes, anchor) that claimed it
        for pos, (_, _, g, i, _) in enumerate(frames):
            name = frame_png_name(pos)
            f = os.path.join(d, name)
            if not os.path.isfile(f):
                continue
            data = rd(f)
            src_pix, src_anc = recs[(g, i)][0], recs[(g, i)][1]
            try:
                img = Image.open(f)
                img.load()
                if name in anchors:
                    # any size: the sidecar gives the registration point, R/B follow from the size (NET_ART.md 3)
                    rx, ry = anchors[name]
                    pix_new, (w, h), nudged = sprite_patch.record_from_image(src_pix, img)
                    anc_new = sprite_patch.anchor_payload(rx, ry, w, h)
                else:
                    pix_new, nudged = sprite_patch.replace_from_png(src_pix, f)
                    anc_new = src_anc
            except sprite_patch.SpritePatchError as e:
                raise NetpackError("%s: %s: %s (a PNG of another size needs its registration point in "
                                   "%s)" % (where, name, e, ANCHOR_FILE))
            k = (g, i)
            if k in owner and owner[k] != (data, anc_new):
                # the stock frames share one record but the new art differs: this frame gets its own record
                k = (g, i, pos)
                keys.append(k)
            elif k in owner:
                continue
            owner[k] = (data, anc_new)
            pix[k], anc[k] = pix_new, anc_new
            pos_keys[pos] = k
        extra = sorted(set(n for n in os.listdir(d) if n.lower().endswith(".png"))
                       - {frame_png_name(p) for p in range(len(frames))})
        if extra:
            raise NetpackError("%s: png_dir has files that name no frame of piece %d: %s" % (where, src, extra[:5]))
        stray = sorted(set(anchors) - {frame_png_name(p) for p in range(len(frames))})
        if stray:
            raise NetpackError("%s: %s names no frame of piece %d: %s" % (where, ANCHOR_FILE, src, stray[:5]))
        src_T = {k: struct.unpack_from("<h", recs[k[:2]][1], 2)[0] for k in keys}
        return _finish_art({"from": src, "cs_key": cs_key, "cs_rel": cs_rel, "cs": cs, "frames": frames,
                            "keys": keys, "pix": pix, "anchor": anc, "pos_keys": pos_keys, "src_T": src_T}, art, where)
    return _finish_art({"from": src, "cs_key": cs_key, "cs_rel": cs_rel, "cs": cs, "frames": frames, "keys": keys,
                        "pix": pix, "anchor": {k: recs[k][1] for k in keys},
                        "pos_keys": [(g, i) for _, _, g, i, _ in frames]}, art, where)


ANCHOR_FILE = "anchors.json"


def _png_anchors(d, where):
    """png_dir/anchors.json: {"z3_r0.png": [reg_x, reg_y], ...} -> {name: (x, y)}. Optional.
    A frame listed here may have any size; its anchor record is written as {x, y, w - x, h - y}."""
    p = os.path.join(d, ANCHOR_FILE)
    if not os.path.isfile(p):
        return {}
    try:
        raw = json.load(open(p, encoding="utf-8"))
    except ValueError as e:
        raise NetpackError("%s: %s: %s" % (where, ANCHOR_FILE, e))
    out = {}
    for n, v in raw.items():
        if n.startswith("_"):
            continue                    # comments
        if not (isinstance(v, list) and len(v) == 2 and all(isinstance(x, int) for x in v)):
            raise NetpackError("%s: %s: %s must be [reg_x, reg_y] integers" % (where, ANCHOR_FILE, n))
        out[n] = tuple(v)
    return out


def cs_retarget_pos(buf, pos_new):
    """Rewrite frame position k's (group, instance) to pos_new[k] -> new bytes (same size)."""
    b = bytearray(buf)
    for k, (o, fi, g, i, fl) in enumerate(NP.cs_frames(buf)[1]):
        struct.pack_into("<II", b, o + 2, pos_new[k][0], pos_new[k][1])
    return bytes(b)


# =================================================================== compile one package

def _names(v, langs):
    nm = v.get("name")
    if nm is None:
        return None
    if isinstance(nm, str):
        return {lang: nm for lang in langs}
    out = {}
    for lang in langs:
        t = nm.get(lang, nm.get(lang.upper(), nm.get("*")))
        if t is not None:
            out[lang] = t
    return out


def compile_pack(stock, pack_dir, man):
    """-> dict of everything this package contributes, checked against the stock files only."""
    pname = man["name"]
    stock_ex = stock.exemplars()
    langs_text = stock.lang_dirs("Text")
    out = {"name": pname, "variants": [], "reskins": [], "rule_edits": [], "ini": [], "warnings": [],
           "bridges": [dict(e, _pack=pname) for e in man.get("bridges", [])],              # task netbridge
           "crossings": list(man.get("crossings", [])),
           "templates": list(man.get("templates", [])),                                     # task multitile
           "auto_roundabouts": []}                                                          # task roundabout3
    for n, v in enumerate(man.get("variants", [])):
        where = "%s variant %d (id %s)" % (pname, n + 1, v.get("id"))
        vid, base, net = v["id"], v["base"], v["network"]
        if not 0 < vid <= 0xFFFF:
            raise NetpackError("%s: id must fit 16 bits (save word1 & 0xffff, SIMNTWRK 0x1000c80b)" % where)
        if vid in RESERVED_IDS:
            raise NetpackError("%s: 15130..15141 are special-cased by the classifier FUN_1001a5f2" % where)
        if vid in stock_ex:
            raise NetpackError("%s: id %d already has a stock exemplar (%s)" % (where, vid, stock_ex[vid][0]))
        if base not in stock_ex:
            raise NetpackError("%s: base %d has no stock exemplar" % (where, base))
        if base not in stock.set_ids(net):
            raise NetpackError("%s: base %d is not in %s_GRND_Set.txt (network %s)" % (where, base, net, net))
        if vid in stock.set_ids(net):
            raise NetpackError("%s: id %d is already in %s_GRND_Set.txt" % (where, vid, net))
        art = compile_art(stock, pack_dir, v.get("art"), base, where)
        out["warnings"] += art.get("warnings", [])
        ex = tkb1_set_key(stock_ex[base][1], 0x67, (CS_TYPE, KOREA_CS_GROUP, vid))
        names = _names(v, langs_text)
        if names:
            if tkb1_key(ex, 0x6D) is None:
                raise NetpackError("%s: base %d exemplar has no name key (prop 0x6D)" % (where, base))
            ex = tkb1_set_key(ex, 0x6D, (TEXT_TYPE, TEXT_GROUP, vid))
        trb = {}
        if v.get("trblkatt", "copy_base") == "copy_base":
            for lang in stock.lang_dirs("SSimData"):
                rel = _trblk_rel(stock, lang)
                if rel is None:
                    continue
                recs = [(TRB_GROUP, vid * 0x100 + (i & 0xFF), TRB_TYPE, p)
                        for g, i, t, p in stock.records(rel) if t == TRB_TYPE and g == TRB_GROUP and i >> 8 == base]
                if not recs:
                    out["warnings"].append("%s: %s has no TrBlkAtt record for base %d, none copied" % (where, rel, base))
                trb[rel] = recs
        out["variants"].append({"id": vid, "base": base, "net": net, "art": art, "exemplar": ex, "names": names,
                                "trblk": trb, "where": where, "_pack": pname,
                                "inherit": v.get("inherit", True), "replace_base": v.get("replace_base", False)})
    for n, r in enumerate(man.get("reskins", [])):
        where = "%s reskin %d (piece %s)" % (pname, n + 1, r.get("piece"))
        piece = r["piece"]
        if piece not in stock_ex:
            raise NetpackError("%s: piece %d has no stock exemplar" % (where, piece))
        art = compile_art(stock, pack_dir, r.get("art"), piece, where)
        out["warnings"] += art.get("warnings", [])
        if art["from"] != piece:
            raise NetpackError("%s: a reskin draws over the piece's own frames; \"from\" must be omitted" % where)
        if not r.get("art", {}).get("recolor") and not r.get("art", {}).get("png_dir"):
            raise NetpackError("%s: art needs recolor and/or png_dir" % where)
        sharers = sorted(i for i, (_, p) in stock_ex.items()
                         if i != piece and tkb1_key(p, 0x67) == art["cs_key"])
        if sharers:
            out["warnings"].append("%s: pieces %s draw from the same frame table and change too" % (where, sharers))
        out["reskins"].append({"piece": piece, "art": art, "where": where, "sharers": sharers})
    for e in man.get("rule_edits", []):
        out["rule_edits"].append(dict(e, _pack=pname))
    vids = {v["id"]: v for v in out["variants"]}
    for n, a in enumerate(man.get("auto_roundabouts", [])):          # task roundabout3: sc3netmod RBT block
        where = "%s auto_roundabouts %d (piece %s)" % (pname, n + 1, a.get("piece"))
        v = vids.get(a.get("piece"))
        if v is None or v["base"] != 39 or v["net"] != "ROAD":
            raise NetpackError("%s: piece must be a ROAD variant of T 39 declared in this package" % where)
        mn = a.get("min_arms", 3)
        if not isinstance(mn, int) or not 1 <= mn <= 4:
            raise NetpackError("%s: min_arms must be 1..4" % where)
        out["auto_roundabouts"].append({"piece": v["id"], "min_arms": mn, "where": where})
    if len(out["auto_roundabouts"]) > 1:
        raise NetpackError("%s: at most one auto_roundabouts entry (sc3netmod applies one piece)" % pname)
    out["ramps"] = []
    if man.get("ramps"):                                 # hardcoded SIMNTWRK tables (netramp.py, NET_RAMPS.md)
        try:
            out["ramps"] = RAMP.compile_ramps(stock.ramp_tables(), man)
        except RAMP.RampError as e:
            raise NetpackError(str(e))
    for e in man.get("ini", []):
        out["ini"].append(dict(e, _pack=pname))
    out["lanekit"] = {"lanes": [], "connects": [], "warnings": [], "info": []}
    if man.get("lanes") or man.get("connects"):          # task lanekit (netpack_lanes.py, NET_LANES.md)
        try:
            out["lanekit"] = NL.compile_entries(stock.root, pack_dir, man)
        except NL.LanesError as e:
            raise NetpackError(str(e))
    return out


def _trblk_rel(stock, lang):
    for n in stock.listdir("Apps/Res/SSimData/" + lang):
        if n.lower() == "trblkatt.ixf":
            return "Apps/Res/SSimData/%s/%s" % (lang, n)
    return None


# =================================================================== merge all packages

def merge(stock, packs):
    """packs: [(pack_dir, manifest)] -> (files {rel: bytes}, tables {name: bytes}, report).
    Packages are merged in NAME order; every container is rebuilt from the stock files."""
    packs = sorted(packs, key=lambda pm: pm[1]["name"])
    names = [m["name"] for _, m in packs]
    if len(set(names)) != len(names):
        raise NetpackError("two packages are named %r" % [n for n in names if names.count(n) > 1][0])
    comp = [compile_pack(stock, d, m) for d, m in packs]
    files, tables, report = {}, {}, {"warnings": [], "info": [], "variants": [], "reskins": []}
    for c in comp:
        report["warnings"] += c["warnings"]

    # ---- collisions between packages
    seen = {}
    for c in comp:
        for v in c["variants"]:
            if v["id"] in seen:
                raise NetpackError("variant id %d is declared by both %s and %s" % (v["id"], seen[v["id"]], c["name"]))
            seen[v["id"]] = c["name"]
    rs = {}
    for c in comp:
        for r in c["reskins"]:
            k = r["art"]["cs_key"]
            if k in rs:
                raise NetpackError("frame table of piece %d is reskinned by both %s and %s" % (r["piece"], rs[k], c["name"]))
            rs[k] = c["name"]

    # ---- art: every record gets (group, (piece << 16) | ordinal), groups filled up to ART_MAX_RECORDS
    items = [("v", v["id"], v) for c in comp for v in c["variants"]] + \
            [("r", r["piece"], r) for c in comp for r in c["reskins"]]
    dats, cur, group = [], [], ART_GROUP0
    for kind, piece, it in items:
        a = it["art"]
        if len(cur) + 2 * len(a["keys"]) > ART_MAX_RECORDS:
            dats.append((group, cur))
            cur, group = [], group + 1
        mp = {}
        for j, k in enumerate(a["keys"]):
            nk = (group, (piece << 16) | j)
            mp[k] = nk
            cur.append((nk[0], nk[1], 1, a["anchor"][k]))     # anchor first, as Roads_2.DAT orders them
            cur.append((nk[0], nk[1], 0, a["pix"][k]))
        it["table"] = cs_retarget_pos(a["cs"], [mp[k] for k in a["pos_keys"]])
    if cur:
        dats.append((group, cur))
    for g, recs in dats:
        files["Apps/Res/Sprites/%08X_netpack.DAT" % g] = ixf_insert.new_container(recs)

    variants = sorted((v for c in comp for v in c["variants"]), key=lambda v: v["id"])
    try:                                    # task lanekit: edits variant exemplars / records, writes stock copies
        NL.merge(stock, [(c["name"], c["lanekit"]) for c in comp], {v["id"]: v for v in variants}, files, report)
    except NL.LanesError as e:
        raise NetpackError(str(e))
    if variants:
        files[OCC_KOREA] = ixf_insert.new_container([(EX_GROUP, v["id"], EX_TYPE, v["exemplar"]) for v in variants])
        files[CS_KOREA] = ixf_insert.new_container([(KOREA_CS_GROUP, v["id"], CS_TYPE, v["table"]) for v in variants])

    # ---- reskins: same-size rewrite of the piece's frame-table payload inside a copy of its CSAttrib container
    by_cont = {}
    for c in comp:
        for r in c["reskins"]:
            by_cont.setdefault(r["art"]["cs_rel"], []).append(r)
    for rel, lst in sorted(by_cont.items()):
        data = bytearray(stock.read(rel))
        recs, d = ixf_parse.parse(stock.path(rel))
        idx = {(x["type"], x["group"], x["instance"]): x for x in recs}
        for r in lst:
            x = idx[r["art"]["cs_key"]]
            assert len(r["table"]) == x["size"]
            data[x["offset"]:x["offset"] + x["size"]] = r["table"]
        files[rel] = bytes(data)

    # ---- traffic records, per language
    trb = {}
    for v in variants:
        for rel, recs in v["trblk"].items():
            trb.setdefault(rel, []).extend(recs)
    for rel, recs in sorted(trb.items()):
        if not recs:
            continue
        old = files.get(rel) or stock.read(rel)          # task lanekit may have replaced stock records already
        recs = sorted(recs, key=lambda r: r[1])
        try:
            new = ixf_insert.append(old, recs)
        except ixf_insert.IxfInsertError as e:
            raise NetpackError("%s: %s" % (rel, e))
        probs = ixf_insert.check_append(old, new, recs)
        if probs:
            raise NetpackError("%s: %s" % (rel, probs))
        files[rel] = new

    # ---- names: one new string container per language folder
    langs = stock.lang_dirs("Text")
    for lang in langs:
        recs = []
        for v in variants:
            t = (v["names"] or {}).get(lang)
            if t is not None:
                b = t.encode("cp1252")
                recs.append((TEXT_GROUP, v["id"], TEXT_TYPE, struct.pack("<I", len(b)) + b))
        if recs:
            if stock.exists("Apps/Res/Text/%s/%s" % (lang, NAME_FILE)):
                raise NetpackError("Apps\\Res\\Text\\%s\\%s exists in the stock tree" % (lang, NAME_FILE))
            files["Apps/Res/Text/%s/%s" % (lang, NAME_FILE)] = ixf_insert.new_container(recs)

    # ---- TilingRules: Set membership for every variant, then the packages' edits (one parse per file)
    edits = {}
    for net in NETS:
        ids = [v["id"] for v in variants if v["net"] == net]
        if ids:
            edits.setdefault("%s_GRND_Set.txt" % net, []).append({"op": "list_add", "ids": ids, "_pack": "(variants)"})
    # ---- task netbridge: variants inherit the base's Set / DIAG / Protected membership and Convert rows, and
    # "replace_base" retargets every rule RESULT that places the base (netpack_bridges.py, NETBRIDGE.md)
    for fname, el in sorted(NB.inherit_edits(stock, variants).items()):
        edits.setdefault(fname, []).extend(el)
    for v in variants:
        if v["replace_base"]:
            for fname, el in sorted(NB.replace_base_edits(stock, v).items()):
                edits.setdefault(fname, []).extend(el)
    # ---- task netramp: hardcoded piece tables (on-ramps, tunnels, slope pieces), netramp.py / NET_RAMPS.md
    try:
        ramps = RAMP.check_merged([(c["name"], c["ramps"]) for c in comp], {v["id"]: v for v in variants},
                                  stock.set_files_of, report["warnings"])
    except RAMP.RampError as e:
        raise NetpackError(str(e))
    # ---- task roundabout3: one automatic roundabout piece across all packages (sc3netmod RBT applies one)
    autos = [a for c in comp for a in c["auto_roundabouts"]]
    if len(autos) > 1:
        raise NetpackError("auto_roundabouts: %s and %s both declare one; sc3netmod applies a single piece" %
                           (autos[0]["where"], autos[1]["where"]))
    # ---- task multitile: templates (netpack_templates.py, MULTITILE.md). Their cell pieces go into the Protected
    # list of their network so a later re-tile never replaces a template cell.
    try:
        inh = NB.inherit_edits(stock, variants)
        tdir = stock.listdir("Apps/Res/TilingRules")
        set_m, prot_m, prot_f = {}, {}, {}
        for n in NETS:
            set_m[n] = stock.set_ids(n) | {v["id"] for v in variants if v["net"] == n}
            for e in inh.get("%s_GRND_Set.txt" % n, []):
                set_m[n] |= set(e.get("ids", []))
            f = [x for x in tdir if x.lower() == ("%s_grnd_protected.txt" % n).lower()]
            prot_f[n] = f[0] if f else None
            prot_m[n] = {int(x) for x in NR.counted(stock.read("Apps/Res/TilingRules/" + f[0]))[0]
                         if x.strip().isdigit()} if f else set()
            for e in inh.get(prot_f[n] or "", []):
                prot_m[n] |= set(e.get("ids", []))
        templates, tprot = TPL.compile_all(stock, [(c["name"], c["templates"]) for c in comp], variants, set_m, prot_m,
                                           report["warnings"])
    except TPL.TemplateError as e:
        raise NetpackError(str(e))
    for n, ids in sorted(tprot.items()):
        if not prot_f[n]:
            raise NetpackError("templates: no %s_GRND_Protected.txt in the stock tree" % n)
        edits.setdefault(prot_f[n], []).append({"op": "list_add", "ids": ids, "_pack": "(templates)"})
    for c in comp:
        for e in c["rule_edits"]:
            edits.setdefault(e["file"], []).append(e)
    low = {}                                      # one entry per real file, whatever case each edit used
    for fname in list(edits):
        low.setdefault(fname.lower(), []).append(fname)
    for k, names_ in low.items():
        if len(names_) > 1:
            keep = names_[0]
            for o in names_[1:]:
                edits[keep].extend(edits.pop(o))
    tr = {}
    for fname, el in sorted(edits.items()):
        rel = "Apps/Res/TilingRules/" + fname
        real = [n for n in stock.listdir("Apps/Res/TilingRules") if n.lower() == fname.lower()]
        if not real:
            raise NetpackError("rule edit names %s, which is not in Apps\\Res\\TilingRules" % fname)
        rel = "Apps/Res/TilingRules/" + real[0]
        try:
            files[rel] = NR.apply(real[0], stock.read(rel), el)
        except NR.RuleEditError as e:
            raise NetpackError(str(e))
        tr[real[0]] = files[rel]
    # what the merged rules add to the stock findings, by the checks `netrules lint` runs (rulecheck.py): ERROR
    # refuses the merge, WARNING / INFO are reported (TILER_SIM.md section 11)
    if tr:
        stock_tr = {n: stock.read("Apps/Res/TilingRules/" + n) for n in stock.listdir("Apps/Res/TilingRules")}
        found = NR.check(stock_tr, tr)
        errs = [f for f in found if f.severity == NR.RC.ERROR]
        if errs:
            raise NetpackError("rule edits: " + "; ".join("%s: %s" % (f.kind, f.text()) for f in errs))
        for f in found:
            report["warnings" if f.severity == NR.RC.WARNING else "info"].append("%s: %s" % (f.kind, f.text()))

    # ---- task netbridge: Collapse.txt groups (removal of multi-tile pieces), Bridges records (ROAD / RAIL / HWAY /
    # POWR, the four files FUN_10017f98 loads) and crossings
    cfn = [n for n in stock.listdir("Apps/Res/TilingRules") if n.lower() == "collapse.txt"]
    if cfn and variants:
        try:
            cdata = NB.collapse_inherit(stock.read("Apps/Res/TilingRules/" + cfn[0]), variants, report["warnings"])
        except NB.BridgeError as e:
            raise NetpackError(str(e))
        if cdata is not None:
            files["Apps/Res/TilingRules/" + cfn[0]] = cdata
    # task multitile: one Collapse group per package holding its template pieces, so removing one template cell
    # removes the template (FUN_1001da5f: first group holding the id, 4-connected flood within +-8 cells plus the
    # straight walks from the clicked cell; MULTITILE.md)
    tgroups = TPL.collapse_groups(templates)
    if cfn and tgroups:
        rel = "Apps/Res/TilingRules/" + cfn[0]
        try:
            groups = NB.parse_collapse(files.get(rel) or stock.read(rel))
            TPL.add_collapse(groups, tgroups, NB.COLLAPSE_MAX)
        except (NB.BridgeError, TPL.TemplateError) as e:
            raise NetpackError(str(e))
        files[rel] = NB.render_collapse(groups)
    bed = {}
    for c in comp:
        for e in c["bridges"]:
            net = e.get("network")
            if net not in NB.BRIDGE_NETS:
                raise NetpackError("%s bridges: network %r; the game loads Bridges files for %s only (FUN_10017f98)"
                                   % (c["name"], net, sorted(NB.BRIDGE_NETS)))
            bed.setdefault(net, []).append(e)
    report["bridges"] = {}
    for net, el in sorted(bed.items()):
        fn = [n for n in stock.listdir("Apps/Res/TilingRules") if n.lower() == ("%s_grnd_bridges.txt" % net).lower()][0]
        setf = [n for n in stock.listdir("Apps/Res/TilingRules") if n.lower() == ("%s_grnd_set.txt" % net).lower()][0]
        set_ids = set(NR.braced_ids(tr.get(setf) or stock.read("Apps/Res/TilingRules/" + setf)))
        try:
            data = NB.apply_bridge_edits(net, stock.read("Apps/Res/TilingRules/" + fn), el, set_ids)
        except NB.BridgeError as e:
            raise NetpackError(str(e))
        files["Apps/Res/TilingRules/" + fn] = data
        recs = NB.parse_bridges(data)
        report["bridges"][net] = {"records": len(recs), "winners": NB.winners(recs, net)}
        if net == "HWAY":
            mine = {(e.get("record") or {}).get("axis") for e in el if e.get("op") == "insert"}
            for a, b in ((0, 2), (1, 3)):
                if (a in mine) != (b in mine):
                    report["warnings"].append("HWAY bridges: axis %d is replaced but its other lane (axis %d) is not; "
                                              "FUN_10002693 builds the two lanes from the two records" % ((a, b) if a in mine else (b, a)))
    vby = {v["id"]: v for v in variants}
    try:
        report["cross"] = NB.check_crossings(stock, [(c["name"], c["crossings"]) for c in comp], vby)
    except NB.BridgeError as e:
        raise NetpackError(str(e))

    # ---- ini edits inside SYS.PAK members. The names container is opened only if Default.ini [DBSegments] lists it
    # (arm O: GZResourceD opens Text\<lang>\*.IXF by the names listed there; a file merely present is not read).
    # The shipped list repeats key 0xa1096a4f for SC3StringsBuildings.IXF and SC3StringsBuildings_Holidays.IXF.
    ini = []
    if any(v["names"] for v in variants):
        ini.append({"file": "Default.ini", "section": "DBSegments", "key": "0xa1096a4f", "op": "append",
                    "value": r"0x80c381d7;Res\Text\%%Language%%\%s" % NAME_FILE, "_pack": "(variant names)"})
    ini += [e for c in comp for e in c["ini"]]
    if ini:
        files[SYSPAK] = apply_ini(stock.read(SYSPAK), ini)

    # ---- variant tables for sc3netmod.dll, one per package
    for c in comp:
        mine = [t for t in templates if t["pack"] == c["name"]]
        if c["variants"] or c["ramps"] or mine or c["auto_roundabouts"]:
            tables[c["name"]] = ("# netpack %s: <variant id> <base id>, read by sc3netmod.dll\r\n" % c["name"]).encode() + \
                b"".join(b"%d %d\r\n" % (v["id"], v["base"]) for v in sorted(c["variants"], key=lambda v: v["id"])) + \
                RAMP.table_lines(c["ramps"]) + TPL.table_lines(mine) + \
                b"".join(b"rbt %d %d\r\n" % (a["piece"], a["min_arms"]) for a in c["auto_roundabouts"])

    # ---- report + checks that need the merged result
    placed = set()
    for fn in stock.listdir("Apps/Res/TilingRules"):
        if NR.family(fn) == "RULES" and NR.stage_mode(fn):
            placed |= NR.result_ids(tr.get(fn) or stock.read("Apps/Res/TilingRules/" + fn))
    for rel, data in files.items():                     # task netbridge: bridge records and crossing pieces place too
        if rel.lower().endswith("_grnd_bridges.txt"):
            placed |= {val >> 8 for rec in NB.parse_bridges(data) for l in rec[2] for val in l}
    for c in comp:
        placed |= {e.get("piece") for e in c["crossings"]}
    placed |= {r["to"] >> 8 for r in ramps}                 # a table slot places it (netramp.py)
    placed |= {c[0] for t in templates for c in t["cells"].values()}   # a template places it (task multitile)
    placed |= {a["piece"] for a in autos}                    # sc3netmod RBT places it (task roundabout3)
    for v in variants:
        if v["id"] not in placed:
            report["warnings"].append("%s: no rule RESULT places %d, so the tiler never builds it" % (v["where"], v["id"]))
        report["variants"].append({"id": v["id"], "base": v["base"], "net": v["net"], "art_from": v["art"]["from"],
                                   "frames": len(v["art"]["frames"]), "records": 2 * len(v["art"]["keys"])})
    for c in comp:
        for r in c["reskins"]:
            report["reskins"].append({"piece": r["piece"], "frames": len(r["art"]["frames"]), "sharers": r["sharers"]})
    report["ramps"] = [{"table": r["table"], "slot": r["slot"], "from": r["from"], "to": r["to"]} for r in ramps]
    report["auto_roundabouts"] = [{"piece": a["piece"], "min_arms": a["min_arms"]} for a in autos]
    report["templates"] = [{"name": t["name"], "pack": t["pack"], "orientations": len(t["orients"]), "cost": t["cost"],
                            "cells": len(t["cells"]), "protect_add": t["protect_add"],
                            "picture": [TPL.render(t, k) for k in range(len(t["orients"]))]} for t in templates]
    return files, tables, report


def apply_ini(pak, edits):
    names, offs, toc_end, recs = syspak_parse.parse(pak)
    lines = [list(r["lines"]) for r in recs]
    for e in edits:
        where = "%s ini %s [%s] %s" % (e["_pack"], e["file"], e["section"], e["key"])
        hit = [i for i, n in enumerate(names) if n.lower() == e["file"].lower()]
        if len(hit) != 1:
            raise NetpackError("%s: SYS.PAK has %d members named %s" % (where, len(hit), e["file"]))
        L = lines[hit[0]]
        sec = [i for i, t in enumerate(L) if t.strip().lower() == "[%s]" % e["section"].lower()]
        if len(sec) != 1:
            raise NetpackError("%s: section found %d times" % (where, len(sec)))
        end = next((i for i in range(sec[0] + 1, len(L)) if L[i].strip().startswith("[")), len(L))
        keys = [i for i in range(sec[0] + 1, end) if "=" in L[i] and L[i].split("=", 1)[0].strip().lower() == e["key"].lower()]
        op = e.get("op", "set")
        if op == "set":
            if len(keys) != 1:
                raise NetpackError("%s: set needs the key exactly once, found %d" % (where, len(keys)))
            L[keys[0]] = "%s=%s" % (L[keys[0]].split("=", 1)[0], e["value"])
        elif op in ("add", "append"):
            if keys and op == "add":
                raise NetpackError("%s: add refuses an existing key (use append for list sections such as "
                                   "[DBSegments], where the shipped Default.ini repeats keys)" % where)
            if any(L[i].strip() == "%s=%s" % (e["key"], e["value"]) for i in range(sec[0] + 1, end)):
                continue
            k = end
            while k > sec[0] + 1 and not L[k - 1].strip():
                k -= 1
            L.insert(k, "%s=%s" % (e["key"], e["value"]))
        else:
            raise NetpackError("%s: op %r" % (where, op))
    out = syspak_parse.build(names, lines)
    n2, _, _, r2 = syspak_parse.parse(out)
    if n2 != names or [r["lines"] for r in r2] != lines:
        raise NetpackError("SYS.PAK rebuild did not read back")
    return out


# =================================================================== ledger + install

def ledger_path(tree):
    return os.path.join(tree, LEDGER)


def ledger_load(tree):
    p = ledger_path(tree)
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def ledger_save(tree, led):
    p = ledger_path(tree)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p + ".tmp", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(led, fh, indent=1, sort_keys=True)
    os.replace(p + ".tmp", p)


def guard_tree(tree, allow):
    t = os.path.normcase(os.path.abspath(tree))
    if not os.path.isfile(os.path.join(tree, "Apps", "SC3U.exe")):
        raise NetpackError("%s has no Apps\\SC3U.exe" % tree)
    if allow:
        return
    root = os.path.normcase(os.path.abspath(os.path.join(HERE, "..", "..", "..")))
    for bad in (r"C:\Users\maria\Desktop\Proyectos\Simcity", r"C:\Users\maria\Desktop\Proyectos\Simcity_stock", root):
        if t == os.path.normcase(bad):
            raise NetpackError("refusing %s (dev install or stock reference); pass --allow-tree for a real install" % tree)


def _write_new(path, data):
    """Delete then write: never opens an existing file for writing, so a hard link is never written through."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.lexists(path):
        os.remove(path)
    with open(path, "wb") as fh:
        fh.write(data)
    if sha(rd(path)) != sha(data):
        raise NetpackError("write of %s did not read back" % path)


def _prune(d, stop):
    d = os.path.abspath(d)
    stop = os.path.abspath(stop)
    while d.startswith(stop) and d != stop and os.path.isdir(d) and not os.listdir(d):
        os.rmdir(d)
        d = os.path.dirname(d)


def installed_packs(tree, led):
    return [(os.path.join(tree, PACKS, p["name"]), load_manifest(os.path.join(tree, PACKS, p["name"])))
            for p in led.get("packs", [])]


def apply_outputs(tree, led, files, tables, cross=None):
    """Make the tree hold exactly `files` (+ tables, + crossing tables) for led["mode"]; restore whatever is no longer
    produced."""
    mode = led["mode"]
    old = led.get("files", {})
    new_led = {}
    if mode == "overlay":
        for rel, data in sorted(files.items()):
            dst = os.path.join(tree, OVERLAY, rel)
            if not (os.path.isfile(dst) and sha(rd(dst)) == sha(data)):
                _write_new(dst, data)
            new_led[rel] = {"sha256": sha(data)}
        for rel in sorted(set(old) - set(files)):
            dst = os.path.join(tree, OVERLAY, rel)
            if os.path.lexists(dst):
                os.remove(dst)
            _prune(os.path.dirname(dst), os.path.join(tree, NETMOD))
    else:
        for rel, data in sorted(files.items()):
            dst = os.path.join(tree, rel)
            ent = dict(old.get(rel, {}))
            if rel not in old:
                if os.path.isfile(dst):
                    b = rd(dst)
                    _write_new(os.path.join(tree, BACKUP, rel), b)
                    ent["stock_sha256"] = sha(b)
                else:
                    ent["stock_sha256"] = None
            if not (os.path.isfile(dst) and sha(rd(dst)) == sha(data)):
                _write_new(dst, data)
            ent["sha256"] = sha(data)
            new_led[rel] = ent
        for rel in sorted(set(old) - set(files)):
            restore_one(tree, rel, old[rel])
    led["files"] = new_led
    tdir = os.path.join(tree, TABLES)
    want = {"%s.txt" % n: b for n, b in tables.items()}
    for n, b in sorted(want.items()):
        p = os.path.join(tdir, n)
        if not (os.path.isfile(p) and rd(p) == b):
            _write_new(p, b)
    if os.path.isdir(tdir):
        for n in sorted(os.listdir(tdir)):
            if n not in want:
                os.remove(os.path.join(tdir, n))
        _prune(tdir, os.path.join(tree, NETMOD))
    # task netbridge: crossing tables, mods\netmod\cross\<package>.txt (sc3netmod.dll XCROSS), same rules as tables
    xdir = os.path.join(tree, CROSS)
    xwant = {"%s.txt" % n: b for n, b in (cross or {}).items()}
    for n, b in sorted(xwant.items()):
        p = os.path.join(xdir, n)
        if not (os.path.isfile(p) and rd(p) == b):
            _write_new(p, b)
    if os.path.isdir(xdir):
        for n in sorted(os.listdir(xdir)):
            if n not in xwant:
                os.remove(os.path.join(xdir, n))
        _prune(xdir, os.path.join(tree, NETMOD))


def restore_one(tree, rel, ent):
    dst = os.path.join(tree, rel)
    if os.path.lexists(dst):
        os.remove(dst)
    if ent.get("stock_sha256"):
        bk = os.path.join(tree, BACKUP, rel)
        b = rd(bk)
        if sha(b) != ent["stock_sha256"]:
            raise NetpackError("backup of %s does not match the ledger hash; NOT restored, backup kept" % rel)
        _write_new(dst, b)
        os.remove(bk)
        _prune(os.path.dirname(bk), os.path.join(tree, NETMOD))


def _check_legacy(stock, led):
    """A newpiece.py install in Apps\\Res would be read as 'stock' and merged over: refuse it."""
    if led and led.get("mode") == "direct" and led.get("files"):
        return
    for rel in (OCC_KOREA, CS_KOREA, LEGACY_TABLE):
        if os.path.isfile(os.path.join(stock.root, rel)) and not (led and rel in led.get("files", {})):
            raise NetpackError("%s exists but no netpack ledger owns it (a newpiece.py install?). Remove it first "
                               "(newpiece.py uninstall), then install packages with netpack." % rel)


def _copy_pack(src, dst):
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    for dp, dns, fns in os.walk(src):
        dns[:] = sorted(n for n in dns if n not in ("build", ".git") and not n.startswith("."))
        for fn in sorted(fns):
            s = os.path.join(dp, fn)
            d = os.path.join(dst, os.path.relpath(s, src))
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copyfile(s, d)


def install(pack_dir, tree, mode=None, allow=False):
    guard_tree(tree, allow)
    led = ledger_load(tree) or {"netpack_ledger": 1, "mode": mode or "overlay", "packs": [], "files": {}}
    if mode and led["packs"] and mode != led["mode"]:
        raise NetpackError("this tree already holds packages in %s mode; uninstall them to switch" % led["mode"])
    if not led["packs"]:
        led["mode"] = mode or led.get("mode") or "overlay"
    man = load_manifest(pack_dir)
    if any(p["name"] == man["name"] for p in led["packs"]):
        raise NetpackError("package %s is already installed (uninstall it first)" % man["name"])
    if not led["packs"] and os.path.isdir(os.path.join(tree, NETMOD)) and not os.path.isfile(ledger_path(tree)):
        raise NetpackError("%s exists without a ledger (files not installed by netpack); move it away first"
                           % os.path.join(tree, NETMOD))
    stock = Stock(tree, led)
    _check_legacy(stock, led)
    check_anchors(stock, man)
    packs = installed_packs(tree, led) + [(pack_dir, man)]
    files, tables, report = merge(stock, packs)          # every refusal happens before anything is written
    _copy_pack(pack_dir, os.path.join(tree, PACKS, man["name"]))
    led["packs"].append({"name": man["name"], "version": man.get("version"),
                         "manifest_sha256": sha(rd(os.path.join(pack_dir, "manifest.json")))})
    apply_outputs(tree, led, files, tables, report.get("cross"))
    ledger_save(tree, led)
    return led, report


def uninstall(name, tree, allow=False):
    guard_tree(tree, allow)
    led = ledger_load(tree)
    if not led or not any(p["name"] == name for p in led["packs"]):
        raise NetpackError("package %s is not installed in %s" % (name, tree))
    stock = Stock(tree, led)
    led["packs"] = [p for p in led["packs"] if p["name"] != name]
    if led["packs"]:
        files, tables, report = merge(stock, installed_packs(tree, led))
    else:
        files, tables, report = {}, {}, None
    apply_outputs(tree, led, files, tables, (report or {}).get("cross"))
    shutil.rmtree(os.path.join(tree, PACKS, name))
    if led["packs"]:
        ledger_save(tree, led)
    else:
        left = [os.path.relpath(os.path.join(dp, f), tree) for dp, _, fs in os.walk(os.path.join(tree, NETMOD))
                for f in fs if os.path.abspath(os.path.join(dp, f)) != os.path.abspath(ledger_path(tree))]
        if left:
            raise NetpackError("last package removed but these remain under mods\\netmod (kept): %s" % left[:5])
        shutil.rmtree(os.path.join(tree, NETMOD))
        _prune(os.path.join(tree, "mods"), tree)
    return led


def check_anchors(stock, man):
    for rel, want in sorted((man.get("game") or {}).items()):
        if not stock.exists(rel):
            raise NetpackError("game anchor %s: file not found" % rel)
        got = sha(stock.read(rel))
        if got.lower() != want.lower():
            raise NetpackError("game anchor %s: sha256 %s, package expects %s" % (rel, got[:16], want[:16]))


# =================================================================== CLI commands

def default_stock(a):
    if getattr(a, "stock", None):
        return a.stock
    import paths
    return paths.game_root()


def cmd_new(a):
    d = a.dir
    if os.path.exists(os.path.join(d, "manifest.json")):
        raise NetpackError("%s already has a manifest.json" % d)
    name = a.name or os.path.basename(os.path.abspath(d)).lower()
    if not NAME_RE.match(name):
        raise NetpackError("package name %r: lower case letters, digits, - or _" % name)
    stock = Stock(default_stock(a))
    net = next((n for n in NETS if a.base in stock.set_ids(n)), None)
    if net is None:
        raise NetpackError("base %d is in no network Set" % a.base)
    simple = [n for n in stock.listdir("Apps/Res/TilingRules") if n.lower() == ("%s_grnd_simplerules.txt" % net).lower()]
    edits = []
    if simple:
        rules, _ = NR.parse_rules(stock.read("Apps/Res/TilingRules/" + simple[0]))
        # the bare (no-condition) rules that place the base: retarget the two plain straight selectors when present
        # (mask 10 and 5, T2-proven for road 29), else the first bare rule, so the scaffold places the variant at once
        bare = [r for r in rules if not r.conds and len(r.results) == 1 and r.results[0][0] == 255
                and r.results[0][1] >> 8 == a.base]
        pick = [r for r in bare if r.sel in (10, 5)] or bare[:1]
        for r in pick:
            st = r.results[0][1] & 0xFF
            edits.append({"op": "set_results", "file": simple[0], "rule": r.stock_no, "expect": r.as_dict(),
                          "results": [[255, a.id, st]]})
    man = {
        "netpack": SCHEMA_VERSION, "name": name, "version": "0.1.0", "author": a.author or "",
        "description": "Describe the package in one line.",
        "game": {"Apps/SIMNTWRK.DLL": sha(stock.read("Apps/SIMNTWRK.DLL"))},
        "variants": [{
            "id": a.id, "base": a.base, "network": net, "name": "Variant of %d" % a.base,
            "art": {"from": a.base, "recolor": "green"}, "trblkatt": "copy_base"}],
        "reskins": [],
        "rule_edits": edits,
        "ini": []}
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "manifest.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(man, fh, indent=2)
        fh.write("\n")
    print("new package %s in %s (variant %d of %d, green; edit manifest.json, then: netpack.py validate %s)"
          % (name, d, a.id, a.base, d))
    return 0


def _print_report(report):
    for v in report["variants"]:
        print("  variant %d  base %d  %s  art from %d, %d frames, %d records"
              % (v["id"], v["base"], v["net"], v["art_from"], v["frames"], v["records"]))
    for r in report["reskins"]:
        print("  reskin  %d  %d frames%s" % (r["piece"], r["frames"],
                                             ("  (also changes %s)" % r["sharers"]) if r["sharers"] else ""))
    for net, b in sorted(report.get("bridges", {}).items()):                    # task netbridge
        print("  bridges %s: %d record(s); record the builder picks per axis (road/rail/power: per crossing length):"
              % (net, b["records"]))
        for axis, runs in sorted(b["winners"].items()):
            print("    axis %d: %s" % (axis, ("record %s" % runs) if net == "HWAY" else
                                       ", ".join("L %d..%d: record %s" % (a, z, w) for a, z, w in runs)))
    for n, b in sorted(report.get("cross", {}).items()):
        print("  crossings %s: %s" % (n, b.decode().strip().splitlines()[1:]))
    for r in report.get("ramps", []):
        print("  ramp    %s slot %d  %d.%d -> %d.%d" % (r["table"], r["slot"], r["from"] >> 8, r["from"] & 0xFF,
                                                       r["to"] >> 8, r["to"] & 0xFF))
    for r in report.get("auto_roundabouts", []):                                # task roundabout3
        print("  auto roundabout: piece %d, 2x2 road blocks with >= %d arm(s) (sc3netmod RBT)" % (r["piece"], r["min_arms"]))
    for t in report.get("templates", []):                                       # task multitile
        print("  template %s/%s  %d cell(s), %d orientation(s), cost %d, Protected += %s"
              % (t["pack"], t["name"], t["cells"], t["orientations"], t["cost"], t["protect_add"] or "-"))
        for pic in t["picture"]:
            print("    " + pic.replace("\n", "\n    "))
    for w in report["warnings"]:
        print("  WARNING " + w)
    for w in report.get("info", []):
        print("  INFO " + w)


def cmd_validate(a):
    man = load_manifest(a.pack)
    tree = a.tree or default_stock(a)
    led = ledger_load(tree) if a.tree else None
    stock = Stock(tree, led)
    check_anchors(stock, man)
    packs = [(d, m) for d, m in (installed_packs(tree, led) if led else []) if m["name"] != man["name"]]
    files, tables, report = merge(stock, packs + [(a.pack, man)])
    print("package %s %s: OK (%d file(s) after merge with %d installed package(s))"
          % (man["name"], man.get("version", ""), len(files), len(packs)))
    _print_report(report)
    return 0


def cmd_build(a):
    man = load_manifest(a.pack)
    stock = Stock(default_stock(a))
    check_anchors(stock, man)
    files, tables, report = merge(stock, [(a.pack, man)])
    out = os.path.abspath(a.out)
    if os.path.isdir(out):
        shutil.rmtree(out)
    listing = {}
    for rel, data in sorted(files.items()):
        _write_new(os.path.join(out, "files", rel), data)
        listing[rel] = {"sha256": sha(data), "bytes": len(data), "replaces_stock": stock.exists(rel)}
    for n, b in sorted(tables.items()):
        _write_new(os.path.join(out, "tables", n + ".txt"), b)
    for n, b in sorted(report.get("cross", {}).items()):                        # task netbridge
        _write_new(os.path.join(out, "cross", n + ".txt"), b)
    with open(os.path.join(out, "BUILD.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"package": man["name"], "version": man.get("version"), "files": listing,
                   "tables": {n: sha(b) for n, b in tables.items()}, "warnings": report["warnings"],
                   "cross": {n: sha(b) for n, b in report.get("cross", {}).items()}},
                  fh, indent=1, sort_keys=True)
    for rel, m in sorted(listing.items()):
        print("%-58s %9d  %s" % (rel, m["bytes"], "replaces stock" if m["replaces_stock"] else "new file"))
    _print_report(report)
    return 0


def cmd_install(a):
    led, report = install(a.pack, a.tree, a.mode, a.allow_tree)
    print("installed into %s (%s mode): %s" % (a.tree, led["mode"], ", ".join(p["name"] for p in led["packs"])))
    _print_report(report)
    print("%d file(s) %s" % (len(led["files"]), "in mods\\netmod\\overlay (needs sc3netmod.dll)" if led["mode"] == "overlay"
                             else "written into Apps (stock copies in mods\\netmod\\backup)"))
    return 0


def cmd_uninstall(a):
    led = uninstall(a.name, a.tree, a.allow_tree)
    if led["packs"]:
        print("removed %s; still installed: %s" % (a.name, ", ".join(p["name"] for p in led["packs"])))
    else:
        print("removed %s; no packages left, every file restored and mods\\netmod deleted" % a.name)
    return 0


def cmd_list(a):
    led = ledger_load(a.tree)
    if not led or not led.get("packs"):
        print("no netpack packages in %s" % a.tree)
        return 0
    print("%s mode, %d package(s):" % (led["mode"], len(led["packs"])))
    for p in led["packs"]:
        m = load_manifest(os.path.join(a.tree, PACKS, p["name"]))
        print("  %-24s %-8s variants %s  reskins %s  rule edits %d" % (
            p["name"], p.get("version") or "", [v["id"] for v in m.get("variants", [])],
            [r["piece"] for r in m.get("reskins", [])], len(m.get("rule_edits", []))))
    for rel in sorted(led["files"]):
        e = led["files"][rel]
        print("    %s%s" % (rel, "" if led["mode"] == "overlay" else
                            ("  (replaces stock)" if e.get("stock_sha256") else "  (new)")))
    return 0


def cmd_export_art(a):
    stock = Stock(default_stock(a))
    key, (rel, cs), frames = _frames_of(stock, a.piece)
    keys = {(g, i) for _, _, g, i, _ in frames}
    recs = stock.sprite_records(keys)
    os.makedirs(a.dir, exist_ok=True)
    n = 0
    for pos, (_, _, g, i, _) in enumerate(frames):
        p = recs.get((g, i), {}).get(0)
        if p is None:
            continue
        w, h = sprite_patch.export_png(p, os.path.join(a.dir, frame_png_name(pos)))
        n += 1
    print("piece %d: %d of %d frames written to %s (zN_rM.png; edit, keep the size, transparent = colour key)"
          % (a.piece, n, len(frames), a.dir))
    print("game art: keep these files out of any public repository")
    return 0


# =================================================================== selftest (offline U1..U10)

def tree_hashes(root, skip=("re", ".git")):      # .git: other sessions commit while the selftest runs
    out = {}
    for dp, dns, fns in os.walk(root):
        rel_dp = os.path.relpath(dp, root)
        if rel_dp == ".":
            dns[:] = [d for d in dns if d not in skip]
        for fn in fns:
            p = os.path.join(dp, fn)
            out[norm(os.path.relpath(p, root))] = sha(rd(p))
    return out


def cmd_selftest(a):
    import link_tree
    stock_root = os.path.abspath(default_stock(a))
    ex_dir = os.path.join(HERE, "examples")
    A, B = os.path.join(ex_dir, "example_blue_road"), os.path.join(ex_dir, "example_reskin")
    fails = []

    def check(ok, what):
        print("  %-4s %s" % ("ok" if ok else "FAIL", what))
        if not ok:
            fails.append(what)

    tmp = tempfile.mkdtemp(prefix="netpack_selftest_")
    try:
        # U3: deterministic merge, order independent
        st = Stock(stock_root)
        f1, t1, _ = merge(st, [(A, load_manifest(A)), (B, load_manifest(B))])
        f2, t2, _ = merge(Stock(stock_root), [(B, load_manifest(B)), (A, load_manifest(A))])
        stock_ref = {rel: sha(rd(os.path.join(stock_root, rel))) for rel in f1
                     if os.path.isfile(os.path.join(stock_root, rel))}     # every stock file the packages replace
        check({k: sha(v) for k, v in f1.items()} == {k: sha(v) for k, v in f2.items()} and t1 == t2,
              "U3 merge A+B == B+A, %d files" % len(f1))
        check(NR.apply("ROAD_GRND_SimpleRules.txt", st.read("Apps/Res/TilingRules/ROAD_GRND_SimpleRules.txt"),
                       load_manifest(A)["rule_edits"]) == NP.rules_retarget(
                  st.read("Apps/Res/TilingRules/ROAD_GRND_SimpleRules.txt"), 29, 20029),
              "example_blue_road rules == newpiece.py rules_retarget (the game-proven 20029 edit)")
        # U5: validate refusals
        def refuses(mut, what):
            m = load_manifest(A)
            mut(m)
            d = os.path.join(tmp, "bad")
            if os.path.isdir(d):
                shutil.rmtree(d)
            shutil.copytree(A, d)
            with open(os.path.join(d, "manifest.json"), "w") as fh:
                json.dump(m, fh)
            try:
                merge(Stock(stock_root), [(d, load_manifest(d))])
                check(False, "U5 refuses " + what)
            except NetpackError as e:
                check(True, "U5 refuses %s: %s" % (what, str(e).splitlines()[0][:110]))
        refuses(lambda m: m["variants"][0].update(id=73), "an id with a stock exemplar")
        refuses(lambda m: m["variants"][0].update(base=44), "a base on another network")
        refuses(lambda m: m["rule_edits"][0]["expect"].update(selector=11), "an edit whose expect differs from the stock rule")
        refuses(lambda m: m["rule_edits"][1].update(rule=15), "two edits of one stock rule (the second sees the first's result)")
        refuses(lambda m: m["rule_edits"][0].update(rule=100000), "a rule index past the stock file")
        d = os.path.join(tmp, "badpng")
        shutil.copytree(A, d)
        os.makedirs(os.path.join(d, "art"))
        from PIL import Image
        Image.new("RGBA", (7, 5), (0, 0, 255, 255)).save(os.path.join(d, "art", "z0_r0.png"))
        m = load_manifest(d)
        m["variants"][0]["art"]["png_dir"] = "art"
        with open(os.path.join(d, "manifest.json"), "w") as fh:
            json.dump(m, fh)
        try:
            merge(Stock(stock_root), [(d, load_manifest(d))])
            check(False, "U5 refuses a PNG whose size differs from the base frame")
        except NetpackError as e:
            check("is 7x5" in str(e), "U5 refuses a PNG whose size differs from the base frame: %s" % str(e)[:110])

        # U7: rule edits are judged by rulecheck (the netrules lint checks), ERROR refuses, WARNING / INFO pass
        def with_edits(extra, tag):
            m = load_manifest(A)
            m["rule_edits"] = m["rule_edits"] + extra
            d = os.path.join(tmp, "u7_" + tag)
            shutil.copytree(A, d)
            with open(os.path.join(d, "manifest.json"), "w") as fh:
                json.dump(m, fh)
            return d

        def lint_of(extra, tag):
            """-> (error text or None, [(severity, kind, text)] the merge reports, same from netrules lint)."""
            from netmod import netrules as NRL
            d = with_edits(extra, tag)
            try:
                _, _, rep = merge(Stock(stock_root), [(d, load_manifest(d))])
            except NetpackError as e:
                return str(e), [], []
            got = [("WARNING",) + tuple(w.split(": ", 1)) for w in rep["warnings"] if ": " in w and " rule #" in w] + \
                  [("INFO",) + tuple(w.split(": ", 1)) for w in rep["info"]]
            edits, _ = NRL.load_edits([os.path.join(d, "manifest.json")])
            out = os.path.join(tmp, "u7_rules_" + tag)
            stock_tiling = os.path.join(stock_root, "Apps", "Res", "TilingRules")
            NRL.apply_edits(stock_tiling, out, edits)
            ref = [(f.severity, f.kind, f.text()) for f in NRL.lint_dir(out, stock_tiling)]
            return None, sorted(got), sorted(ref)

        def rule(sel, conds, results):
            return {"selector": sel, "conds": conds, "results": results}

        u7 = [
            ("final-stage result at a neighbour dir (2) and a Simple result at dir 16: FUN_10016327 never checks "
             "result dirs", "resdir",
             [{"op": "insert_rule", "file": "ROAD_GRND_final.txt", "at": 0,
               "rule": rule(1, [[255, 20029, 2]], [[2, 29, 0]])},
              {"op": "insert_rule", "file": "ROAD_GRND_SimpleRules.txt", "at": 0,
               "rule": rule(0x100, [[255, 20029, 2], [0, 29, 0]], [[16, 29, 0]])}], None, set()),
            ("final-stage condition at diagonal dir 5: the 3x3 collector reports it (FUN_1001a056)", "conddiag",
             [{"op": "insert_rule", "file": "ROAD_GRND_final.txt", "at": 0,
               "rule": rule(1, [[5, 20029, 1]], [[255, 29, 0]])}], None, set()),
            ("ComplexRules selector 5: WARNING never-matches, merge passes", "cxsel",
             [{"op": "insert_rule", "file": "ROAD_GRND_ComplexRules.txt", "at": 0,
               "rule": rule(5, [[255, 20029, 0], [12, 29, 0]], [[255, 29, 1]])}], None, {("WARNING", "never-matches")}),
            ("ComplexRules selector 0x100 and 0: no selector finding", "cxok",
             [{"op": "insert_rule", "file": "ROAD_GRND_ComplexRules.txt", "at": 0,
               "rule": rule(0x100, [[255, 20029, 3], [12, 20029, 3]], [[255, 29, 1]])},
              {"op": "insert_rule", "file": "ROAD_GRND_ComplexRules.txt", "at": 0,
               "rule": rule(0, [[255, 20029, 2], [12, 20029, 2]], [[255, 29, 1]])}], None, set()),
            ("a rule shadowed by stock rule 15 (bare, selector 10): WARNING shadowed, merge passes", "shadow",
             [{"op": "insert_rule", "file": "ROAD_GRND_SimpleRules.txt", "at": "end",
               "rule": rule(10, [], [[255, 29, 0]])}], None, {("WARNING", "shadowed")}),
            ("a result dir 24 (zero offsets at 0x10032164 in the FUN_1002205c table): ERROR, refused", "dir24",
             [{"op": "insert_rule", "file": "ROAD_GRND_final.txt", "at": "end",
               "rule": rule(1, [], [[24, 29, 0]])}], ("outside the 25-entry table", "rule/results/0/0: 24"), set()),
        ]
        for what, tag, extra, err, kinds in u7:
            e, got, ref = lint_of(extra, tag)
            if err:
                check(e is not None and any(x in e for x in err), "U7 %s (%s)" % (what, (e or "accepted")[:90]))
                continue
            seen = {(s, k) for s, k, _ in got}
            check(e is None and seen == kinds and got == ref,
                  "U7 %s: %s, netrules lint reports the same %d finding(s)%s"
                  % (what, "accepted" if e is None else "REFUSED " + e[:80], len(ref),
                     "" if got == ref else " MISMATCH netpack %s / netrules %s" % (got, ref)))
        try:
            NR.records([[24, 29, 0]], "U7")
            check(False, "U7 netpack_rules.records refuses dir 24 through rulecheck.record_problem")
        except NR.RuleEditError as e:
            check("outside the 25-entry table" in str(e), "U7 netpack_rules.records refuses dir 24: %s" % str(e)[:90])
        # the schema is the authors' contract; pin its record domain to rulecheck's so the two cannot drift
        try:
            import jsonschema
        except ImportError:
            jsonschema = None
        if jsonschema is None:
            print("  skip U7 schema vs rulecheck record domain (jsonschema not installed)")
        else:
            with open(SCHEMA_FILE, encoding="utf-8") as fh:
                sch = json.load(fh)["$defs"]
            ok_rec = jsonschema.Draft202012Validator(sch["record"]).is_valid
            ok_ps = jsonschema.Draft202012Validator(sch["piece_state"]).is_valid
            bad = [d for d in range(-2, 300) if ok_rec([d, 29, 0]) != (NR.RC.record_problem(d, 29, 0) is None)
                   and d != NR.RC.tiler.SELF]      # 31 reads as self like 255; the manifest form for self is 255
            bad += [(i, s) for i in (0, 1, 29, 65535, 65536) for s in range(-1, 7)
                    if NR.RC.record_problem(255, i, s) is None and not (ok_ps([i, s]) and ok_rec([255, i, s]))]
            check(not bad, "U7 every record rulecheck accepts the schema accepts, dirs both ways%s"
                  % (" MISMATCH %s" % bad[:6] if bad else ""))
        # U7 misparse: a rule declared `4,0` runs into the next one in FUN_10022676 -> ERROR (netrules lint exit 1)
        sname = "ROAD_GRND_SimpleRules.txt"
        stock_tr = {n: st.read("Apps/Res/TilingRules/" + n) for n in st.listdir("Apps/Res/TilingRules")}
        bad = stock_tr[sname].replace(b"\r\n4,1\r\n5,255,7425\r\n", b"\r\n4,0\r\n", 1)
        found = NR.check(stock_tr, {sname: bad})
        check(bad != stock_tr[sname] and [f.kind for f in found if f.severity == NR.RC.ERROR] == ["misparse"],
              "U7 a `4,0` rule is an ERROR misparse (%s)" % (found[0].text()[:90] if found else "no finding"))

        # U8..U10 (task netbridge): bridges, inheritance / replace_base, crossings
        HV, BS, XC = (os.path.join(ex_dir, n) for n in ("example_hway_variant", "example_bridge_style",
                                                         "example_blue_crossing"))
        raw = st.read("Apps/Res/TilingRules/Collapse.txt")
        check(NB.render_collapse(NB.parse_collapse(raw)) == raw,
              "U8 Collapse.txt parse + render == stock bytes (%d groups)" % len(NB.parse_collapse(raw)))
        for net in sorted(NB.BRIDGE_NETS):
            raw = st.read("Apps/Res/TilingRules/%s_GRND_Bridges.txt" % net)
            check(NB.render_bridges(NB.parse_bridges(raw)) == raw,
                  "U8 %s_GRND_Bridges.txt parse + render == stock bytes (%d records)" % (net, len(NB.parse_bridges(raw))))
        fb, _, rb = merge(Stock(stock_root), [(BS, load_manifest(BS))])
        recs = NB.parse_bridges(fb["Apps/Res/TilingRules/ROAD_GRND_Bridges.txt"])
        w = rb["bridges"]["ROAD"]["winners"]
        check(len(recs) == 10 and recs[6][2][2] == [20087 * 256, 20088 * 256] and w[0][0] == [1, 5, 6]
              and w[1][0] == [1, 5, 7] and w[0][1][2] == 4,
              "U8 example_bridge_style: 10 ROAD records, crossings of 1..5 cells pick the pack's records 6 / 7, 6..9 stock 4")

        def brefuses(mut, what):
            m = load_manifest(BS)
            mut(m)
            d = os.path.join(tmp, "badb")
            if os.path.isdir(d):
                shutil.rmtree(d)
            shutil.copytree(BS, d)
            with open(os.path.join(d, "manifest.json"), "w") as fh:
                json.dump(m, fh)
            try:
                merge(Stock(stock_root), [(d, load_manifest(d))])
                check(False, "U8 refuses " + what)
            except NetpackError as e:
                check(True, "U8 refuses %s: %s" % (what, str(e).splitlines()[0][:110]))
        cg = NB.parse_collapse(fb["Apps/Res/TilingRules/Collapse.txt"])
        check(20087 in cg[4] and 20088 in cg[1] and 20088 in cg[4] and 28051 in cg[1] and all(len(g) + 1 <= 0x1D for g in cg),
              "U8 example_bridge_style: the variants join their bases' Collapse.txt groups (20087 in group 4, 20088 in 1 and 4)")
        brefuses(lambda m: m["bridges"][0]["record"].update(span=[[20087, 0]] * 21), "a span of 21 (20-slot stack buffer)")
        brefuses(lambda m: m["bridges"][0]["record"].update(a=[[28051, 2]] * 6), "a ramp list of 6 (5-slot buffer)")
        brefuses(lambda m: m["bridges"][0]["record"].update(b=[]), "an empty pad list (B[0] is read)")
        brefuses(lambda m: m["bridges"][0]["record"].update(e=[[44, 0]]), "a piece that is not in ROAD_GRND_Set.txt")
        brefuses(lambda m: m["bridges"][0]["record"].update(axis=2), "axis 2 on a road (0..1)")
        brefuses(lambda m: m["bridges"][0].update(network="PIPE"), "a PIPE bridge (FUN_10017f98 loads 4 files)")
        brefuses(lambda m: m["bridges"].append({"op": "delete", "network": "ROAD", "record": 0,
                                                "expect": NB.rec_to_manifest(recs[1])}), "a delete whose expect differs")
        fh_, _, rh = merge(Stock(stock_root), [(HV, load_manifest(HV))])
        conv = NB.convert_table(fh_["Apps/Res/TilingRules/HWAY_GRND_Convert.txt"])
        left = set()
        for fn in ("HWAY_GRND_SIMPLERULES.txt", "HWAY_GRND_COMPLEXRULES.txt", "HWAY_GRND_final.txt"):
            left |= {i for i in NR.result_ids(fh_["Apps/Res/TilingRules/" + fn]) if i == 73}
        check(all(conv.get((20073, s)) == (73, s) for s in range(4)) and not left
              and 20073 in NR.braced_ids(fh_["Apps/Res/TilingRules/HWAY_GRND_Set.txt"]),
              "U9 example_hway_variant: Convert rows 20073/s -> 73/s, no stage rule places 73 any more, 20073 in the Set")
        fx, _, rx = merge(Stock(stock_root), [(A, load_manifest(A)), (XC, load_manifest(XC))])
        check(rx["cross"].get("example_blue_crossing", b"").endswith(b"20029 69 20069" + NB.CRLF)
              and 20069 in NR.braced_ids(fx["Apps/Res/TilingRules/RAIL_GRND_Set.txt"])
              and NB.CRLF + b"20069" + NB.CRLF in fx["Apps/Res/TilingRules/ROAD_GRND_Protected.txt"],
              "U10 blue crossing: table line 20029 69 20069, 20069 inherits 69's RAIL Set and ROAD Protected membership")
        try:
            merge(Stock(stock_root), [(XC, load_manifest(XC))])
            check(False, "U10 refuses a crossing over a piece no package declares")
        except NetpackError as e:
            check(True, "U10 refuses a crossing over a piece no package declares: %s" % str(e)[:90])
        m = load_manifest(XC)
        m["crossings"][0]["crossing"] = 67
        d = os.path.join(tmp, "badx")
        shutil.copytree(XC, d)
        with open(os.path.join(d, "manifest.json"), "w") as fh:
            json.dump(m, fh)
        try:
            merge(Stock(stock_root), [(A, load_manifest(A)), (d, load_manifest(d))])
            check(False, "U10 refuses a replacement that is not a variant of the crossing piece")
        except NetpackError as e:
            check(True, "U10 refuses a replacement that is not a variant of the crossing piece: %s" % str(e)[:90])

        # U6: authoring path. export-art writes the stock frames, png_dir re-imports them: same pixels as the source
        d = os.path.join(tmp, "pngpack")
        shutil.copytree(A, d)
        m = load_manifest(d)
        m["variants"][0]["art"] = {"from": 29, "png_dir": "art"}
        with open(os.path.join(d, "manifest.json"), "w") as fh:
            json.dump(m, fh)
        with open(os.devnull, "w") as dn:
            so = sys.stdout
            sys.stdout = dn
            try:
                cmd_export_art(argparse.Namespace(piece=29, dir=os.path.join(d, "art"), stock=stock_root))
            finally:
                sys.stdout = so
        art = compile_art(Stock(stock_root), d, m["variants"][0]["art"], 29, "U6")
        src = Stock(stock_root).sprite_records(set(art["keys"]))
        surf = lambda p: sprite_encode.block_to_surface(qfs.decode_record(p)[1])[0]   # noqa: E731
        same = all(surf(art["pix"][k]) == surf(src[k][0]) for k in art["keys"])
        check(same and len(os.listdir(os.path.join(d, "art"))) == len(art["frames"]),
              "U6 export-art -> png_dir re-import: %d frames, decoded pixels identical to the stock frames"
              % len(art["frames"]))

        # U11 (artkit): a frame of ANOTHER size with its registration point in anchors.json, and new art on a
        # frame whose stock record is shared with another frame (the frame gets its own record)
        shared = {}
        for pos, (_, _, g, i, _) in enumerate(art["frames"]):
            shared.setdefault((g, i), []).append(pos)
        twin = next((ps for ps in shared.values() if len(ps) > 1), None)
        big = Image.new("RGBA", (80, 50), (0, 0, 0, 0))
        big.paste(Image.new("RGBA", (70, 30), (0, 200, 0, 255)), (5, 15))
        big.save(os.path.join(d, "art", "z3_r1.png"))
        with open(os.path.join(d, "art", ANCHOR_FILE), "w") as fh:
            json.dump({"z3_r1.png": [8, 31]}, fh)
        if twin:
            Image.open(os.path.join(d, "art", frame_png_name(twin[1]))).convert("RGBA").transpose(
                Image.FLIP_LEFT_RIGHT).save(os.path.join(d, "art", frame_png_name(twin[1])))
        art2 = compile_art(Stock(stock_root), d, m["variants"][0]["art"], 29, "U11")
        k13 = art2["pos_keys"][13]
        a13 = struct.unpack("<4h", art2["anchor"][k13])
        ok_size = sprite_size(art2["pix"][k13]) == (80, 50) and a13 == (8, 31, 72, 19) \
            and qfs.record_header(art2["pix"][k13])["d2"] == 80
        ok_split = (twin is None) or (art2["pos_keys"][twin[0]] != art2["pos_keys"][twin[1]]
                                      and len(art2["keys"]) == len(art["keys"]) + 1)
        files_u11, _, _ = merge(Stock(stock_root), [(d, m)])
        check(ok_size and ok_split,
              "U11 80x50 frame + anchors.json -> record 80x50, anchor %r; shared-record split %s"
              % (a13, "checked on frames %r" % (twin,) if twin else "not exercised (road 29 shares no record)"))

        # U12 (artkit): art.first_pass clears / sets the frame table's first-pass draw bit (header +0x12, 0x80)
        m12 = dict(m["variants"][0]["art"])
        fp = {}
        for val in (False, True):
            a12 = compile_art(Stock(stock_root), d, dict(m12, first_pass=val), 29, "U12")
            fp[val] = struct.unpack_from("<I", a12["cs"], DRAW_FLAGS_OFF)[0]
        check(not fp[False] & FIRST_PASS and fp[True] & FIRST_PASS and art2.get("warnings"),
              "U12 first_pass false -> flags 0x%X, true -> 0x%X; taller frames with the bit kept warn: %s"
              % (fp[False], fp[True], (art2.get("warnings") or ["NO WARNING"])[0][:70]))

        # U1/U2/U4: round trips on a hard-linked copy of the stock tree, both modes
        for mode in ("overlay", "direct"):
            t = os.path.join(tmp, "tree_" + mode)
            with open(os.devnull, "w") as dn:
                so = sys.stdout
                sys.stdout = dn
                try:
                    link_tree.link(stock_root, t)
                finally:
                    sys.stdout = so
            before = tree_hashes(t)
            install(A, t, mode)
            install(B, t, mode)
            mid = tree_hashes(t)
            apps_changed = sorted(k for k in mid if k.startswith("Apps/") and mid[k] != before.get(k))
            if mode == "overlay":
                check(not apps_changed, "U1 overlay: nothing under Apps changed after installing both")
            else:
                check(len(apps_changed) > 0, "direct: %d file(s) under Apps written" % len(apps_changed))
            # U4: id collision refused, tree unchanged
            c = os.path.join(tmp, "clash_" + mode)
            shutil.copytree(A, c)
            m = load_manifest(c)
            m["name"] = "clash"
            with open(os.path.join(c, "manifest.json"), "w") as fh:
                json.dump(m, fh)
            try:
                install(c, t, mode)
                check(False, "U4 %s: a second package with id 20029 is refused" % mode)
            except NetpackError as e:
                check(tree_hashes(t) == mid, "U4 %s: id clash refused (%s), tree unchanged" % (mode, str(e)[:60]))
            uninstall("example_reskin", t)
            uninstall("example_blue_road", t)
            after = tree_hashes(t)
            diff = sorted(set(before) ^ set(after)) + sorted(k for k in before if k in after and before[k] != after[k])
            check(not diff, "U1 %s: tree byte-identical after install A, B, uninstall B, A (%d files)%s"
                  % (mode, len(before), (" diff %s" % diff[:4]) if diff else ""))
            check(not os.path.exists(os.path.join(t, "mods")), "U1 %s: mods\\ removed with the last package" % mode)
        check(all(sha(rd(os.path.join(stock_root, r))) == h for r, h in stock_ref.items()),
              "U2 the %d stock files the packages replace are unchanged in the hard-link source" % len(stock_ref))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("netpack selftest: %d failure(s)" % len(fails))
    return 1 if fails else 0


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("new")
    s.add_argument("dir")
    s.add_argument("--name")
    s.add_argument("--author")
    s.add_argument("--id", type=int, default=20100)
    s.add_argument("--base", type=int, default=29)
    s.add_argument("--stock")
    s = sub.add_parser("validate")
    s.add_argument("pack")
    s.add_argument("--stock")
    s.add_argument("--tree", help="also merge with the packages installed in this tree")
    s = sub.add_parser("build")
    s.add_argument("pack")
    s.add_argument("--out", required=True)
    s.add_argument("--stock")
    s = sub.add_parser("install")
    s.add_argument("pack")
    s.add_argument("--tree", required=True)
    s.add_argument("--mode", choices=("overlay", "direct"))
    s.add_argument("--allow-tree", action="store_true")
    s = sub.add_parser("uninstall")
    s.add_argument("name")
    s.add_argument("--tree", required=True)
    s.add_argument("--allow-tree", action="store_true")
    s = sub.add_parser("list")
    s.add_argument("--tree", required=True)
    s = sub.add_parser("export-art")
    s.add_argument("piece", type=int)
    s.add_argument("dir")
    s.add_argument("--stock")
    s = sub.add_parser("selftest")
    s.add_argument("--stock")
    a = ap.parse_args(argv[1:])
    try:
        return {"new": cmd_new, "validate": cmd_validate, "build": cmd_build, "install": cmd_install,
                "uninstall": cmd_uninstall, "list": cmd_list, "export-art": cmd_export_art,
                "selftest": cmd_selftest}[a.cmd](a)
    except NetpackError as e:
        print("netpack: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
