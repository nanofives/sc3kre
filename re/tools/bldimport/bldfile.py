#!/usr/bin/env python3
r"""bldfile.py - task bldfile (2026-11-18c): Building Architect .bld files as growable art, no BA import needed.

A .bld is an IXF container (magic 0x80C381D7, 20-byte index, group 0xC3F8D4A9) written by SIMBABLD 0x12003bf6.
It holds the BA's block model, an info record and ONE 200x200 preview picture. It holds no game frames: the game's
20 frames only exist after the game renders the model into Apps\BARender\BAT.DAT. Format with offsets and evidence:
re/analysis/BLD_FORMAT.md.

Art for a grown .bld building, two sources (`frames()`):

  bat      the player's BAT.DAT already holds the same building (matched by the .bld id, else by name): its own
           16 frames at zooms 0-3, all four views, zoom 4 = zoom 3 doubled as in stock.
  preview  the 200x200 preview (record 0xE3F87B0E) is the BA's render of rotation slot 0 in the game's projection
           (mask IoU 0.98-0.99 against the BAT.DAT slot-0 frame, 13 of 13 matched buildings). Each zoom is the
           preview cut to its art box and resampled so the box spans the lot (n x (8 << zoom) px), bottom row on
           the lot's bottom vertex. Slots 0 and 2 use the picture, slots 1 and 3 its mirror: stock lighting puts
           the bright wall on the left in slots 0 / 2 and on the right in slots 1 / 3 (all 15 BAT.DAT buildings).
           So the building turns with the camera as a mirror twin, not as its real other sides.

  py -3.12 re/tools/bldimport/bldfile.py info  <file.bld|folder>...         fields of each file
  py -3.12 re/tools/bldimport/bldfile.py sheet <file.bld> --out x.png [--game G] [--art preview|bat]
  py -3.12 re/tools/bldimport/bldfile.py check --game <tree> <folder>        preview frames against BAT.DAT frames
  py -3.12 re/tools/bldimport/bldfile.py parts <file.bld|folder> [--game G]   texture names a .bld uses, where each resolves
  py -3.12 re/tools/bldimport/bldfile.py render <file.bld|folder>... --game <dev tree> --out x.ixf [--install]
                                                                              real 20 frames from the BA's batch renderer

render (task bldbat, 2026-11-18): runs the Building Architect's own batch export (Baapp.exe FUN_004044a9, the same
body as SIMBABLD 0x12001faf) in a patched, windowed BaappW.exe of a DEV tree (re/tools/bldbat/ba_patch.py,
ba_render.py), then writes the result as a BAT-format IXF with the keys the importers look for: group 0xBA1DBF1E,
override and frame-table instance = the .bld id, 16 pixel records on a free block of instances. --install also merges
it into the tree's Apps/BARender/BAT.DAT (backup BAT.DAT.bldbat-orig, link-safe), where bldimport.py and the
classifier page already read "bat" art. Dev side only (Frida + a dev tree). Results: verify/bldbat/RESULTS.md.
"""
import argparse
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
for p in (HERE, TOOLS, os.path.join(TOOLS, "netmod")):
    if p not in sys.path:
        sys.path.insert(0, p)

import qfs                     # noqa: E402

MAGIC = 0x80C381D7
GROUP = 0xC3F8D4A9
T_MODEL, T_TEXINFO, T_PREVIEW, T_INFO, T_TEX = 0xE3F87B0C, 0xE3F87B0D, 0xE3F87B0E, 0xE3F87B0F, 0xE3F87B10
T_STR78, T_CATEGORY, T_B9, T_99 = 0x644D7178, 0x644D7179, 0xB9EC8F72, 0x99F88B9E
I_MODEL, I_INFO, I_PREVIEW = 0xA3F8D615, 0x63FBE1CC, 0xE3F8D655
I_STR78, I_CATEGORY, I_B9, I_99 = 0xA44D71AA, 0xA44D71AB, 0x99EC9601, 0xB9F88BD2
KEY565 = 0xF81F
SEP = 0xEAEAEAEA
ZOOMS, ROTS = 5, 4
# Record 0x644D7179 as a zone: read from the 17 shipped names only (BUILDING_PICK.md 7 [UNCERTAIN]); batgrow uses
# the same three values. Tutorial House (a house) carries 0x217 like Longview Park, so anything else is no guess.
CATEGORY_ZONE = {0x208: "R", 0x209: "C", 0x20A: "I"}


BA_LOOK = {"zoom4": "double", "palette": None}   # what the BA's own BAT.DAT frames do (preview_frames)


class BldError(Exception):
    pass


# =================================================================== parse

def _records(b):
    if len(b) < 24 or struct.unpack_from("<I", b, 0)[0] != MAGIC:
        raise BldError("not an IXF container (no 0x80C381D7 magic)")
    out, o = {}, 4
    while o + 20 <= len(b):
        g, i, t, off, sz = struct.unpack_from("<5I", b, o)
        o += 20
        if (g, i, t) == (0, 0, 0):
            return out
        if 0xFFFFFFFF in (t, off, sz):
            continue
        if off + sz > len(b):
            raise BldError("record {%08X %08X %08X} runs past the end of the file" % (g, i, t))
        out.setdefault((g, i, t), b[off:off + sz])
    raise BldError("IXF index has no terminator")


def _pstr8(p, o):
    n = p[o]
    return p[o + 1:o + 1 + n], o + 1 + n


def _image(p):
    """Image record: u16 format, u16 w, u16 h, u32 packed length, QFS stream. -> (format, w, h, raw bytes)."""
    fmt, w, h, n = struct.unpack_from("<HHHI", p, 0)
    raw = qfs.decompress(p, 10, n)[0]
    return fmt, w, h, raw


def preview_image(p):
    """0xE3F87B0E -> RGBA PIL image (RGB565, key 0xF81F = transparent)."""
    import numpy as np
    from PIL import Image
    fmt, w, h, raw = _image(p)
    if len(raw) != w * h * 2:
        raise BldError("preview is %d bytes, %dx%d RGB565 needs %d" % (len(raw), w, h, w * h * 2))
    a = np.frombuffer(raw, "<u2").reshape(h, w)
    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[..., 0] = ((a >> 11) & 31) * 255 // 31
    rgba[..., 1] = ((a >> 5) & 63) * 255 // 63
    rgba[..., 2] = (a & 31) * 255 // 31
    rgba[..., 3] = np.where(a == KEY565, 0, 255)
    return Image.fromarray(rgba, "RGBA")


MODEL_VERSIONS = (7, 8)   # 8 = SC3U Building Architect, 7 = the 1999 SC3 Building Architect (BLD_FORMAT.md 6)


def parse_model(p):
    """0xE3F87B0C header, layout from the writer SIMBABLD 0x1200a849 (field names = object offsets there).
    Version 7 (1999 BA) has the same byte layout; Baapp's reader FUN_00413e1a takes both and differs only in
    meaning: v7 height is stored minus 1 (the reader adds 1), and the u32 after each texture name is a per-name
    value it keeps (FUN_0041a852) where v8 has the hash it discards (BLD_FORMAT.md 6)."""
    ver, f84, n, lot, sep1 = struct.unpack_from("<5B", p, 0)
    height, = struct.unpack_from("<H", p, 5)
    f68, = struct.unpack_from("<I", p, 9)
    four, thirty2 = struct.unpack_from("<II", p, 0x11)
    nn, = struct.unpack_from("<I", p, 0x1D)
    if ver not in MODEL_VERSIONS or sep1 != 0xEA or nn != n * n * 4:
        raise BldError("model record header is not version 7 or 8 (got %d) with an n*n*4 column table" % ver)
    cols = struct.unpack_from("<%dI" % (n * n), p, 0x21)
    o = 0x21 + nn
    if struct.unpack_from("<I", p, o)[0] != SEP:
        raise BldError("model record: no separator after the column table")
    blob, = struct.unpack_from("<I", p, o + 4)
    cells = qfs.decompress(p, o + 12, blob - 4)[0]
    o += 8 + blob
    if struct.unpack_from("<I", p, o)[0] != SEP:
        raise BldError("model record: no separator after the cell data")
    cnt, = struct.unpack_from("<I", p, o + 4)
    o += 8
    names = []
    for _ in range(cnt):
        ln, = struct.unpack_from("<I", p, o)
        nm = p[o + 4:o + 4 + ln]
        h, = struct.unpack_from("<I", p, o + 4 + ln)
        names.append((nm.decode("cp1252", "replace"), h))
        o += 8 + ln
    if struct.unpack_from("<I", p, o)[0] != SEP or o + 4 != len(p):
        raise BldError("model record: texture list does not end the record")
    return {"version": ver, "f84": f84, "grid": n, "lot": lot, "height": height, "f68": f68,
            "columns": cols, "cells_raw": len(cells), "textures": names}


def derived_ident(b):
    """A 1999 .bld has no id (its info record ends after the architect). Baapp gives such a file a fresh random id
    at every load (FUN_004063c8 -> FUN_00409142 when the id is 0), so the tools use a stable stand-in: CRC-32 of
    the whole file (bldweb.js computes the same)."""
    import zlib
    return zlib.crc32(b) & 0xFFFFFFFF


def read_bld(path):
    """-> dict with name, architect, lot, category, ident, preview (PIL RGBA), model header, custom texture count."""
    with open(path, "rb") as fh:
        b = fh.read()
    r = _records(b)

    def rec(i, t, need=True):
        p = r.get((GROUP, i, t))
        if p is None and need:
            raise BldError("record {0x%08X, 0x%08X, 0x%08X} missing" % (GROUP, i, t))
        return p

    info = rec(I_INFO, T_INFO)
    lot = info[0]
    name, o = _pstr8(info, 1)
    arch, o = _pstr8(info, o)
    if o == len(info):
        # 1999 BA: the record ends after the architect, no owner string and no id (BLD_FORMAT.md 6)
        sl, ident, ident_from = None, derived_ident(b), "crc32"
    else:
        if o + 8 > len(info):
            raise BldError("info record too short")
        sl, = struct.unpack_from("<I", info, o)
        if o + 8 + sl != len(info):
            raise BldError("info record: %d bytes after the owner string, 4 expected" % (len(info) - o - 4 - sl))
        ident, = struct.unpack_from("<I", info, o + 4 + sl)
        ident_from = "file"
    cat = rec(I_CATEGORY, T_CATEGORY, False)
    s78 = rec(I_STR78, T_STR78, False)
    model = parse_model(rec(I_MODEL, T_MODEL))
    tex = sorted(i for (g, i, t) in r if t == T_TEX)
    out = {
        "file": os.path.basename(path), "path": path, "lot": lot, "name": name.decode("cp1252", "replace"),
        "architect": arch.decode("cp1252", "replace"), "owner_len": sl, "ident": ident, "ident_from": ident_from,
        "category": struct.unpack_from("<I", cat, 0)[0] if cat and len(cat) >= 4 else None,
        "str78": _pstr8(s78, 0)[0].decode("cp1252", "replace") if s78 else "",
        "b9": struct.unpack_from("<I", r[(GROUP, I_B9, T_B9)], 0)[0] if (GROUP, I_B9, T_B9) in r else None,
        "f99": r.get((GROUP, I_99, T_99), b"").hex(),
        "model": model, "custom_textures": len(tex),
        "preview": preview_image(rec(I_PREVIEW, T_PREVIEW)),
    }
    if not 1 <= lot <= 4:
        raise BldError("lot size %d (growables are 1x1 to 4x4)" % lot)
    if model["grid"] != 8 * lot:
        raise BldError("model grid %d is not 8 x lot %d" % (model["grid"], lot))
    return out


def zone_of(bld):
    return CATEGORY_ZONE.get(bld.get("category"))


def suggest_class(bld):
    """Default class from record 0x644D7179 and the lot (batgrow.DEFAULT_CLASS), None when the category is not R/C/I."""
    import batgrow as BG
    z = zone_of(bld)
    return BG.DEFAULT_CLASS[z][bld["lot"]] if z else None


# =================================================================== frames from the preview

def art_box(prev):
    """Box of the non-key pixels of the preview -> (x0, y0, x1, y1) inclusive."""
    import numpy as np
    a = np.asarray(prev)[..., 3] > 0
    ys, xs = np.nonzero(a)
    if not len(xs):
        raise BldError("the preview is empty")
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def _fit(prev, n, z):
    """One zoom: the art box resampled to n x W wide (premultiplied area filter), alpha cut at 128, anchor
    T = h - n x W / 4 (BAT.DAT frames: L = 0, B = n x W / 4 on all 15 shipped buildings)."""
    import numpy as np
    from PIL import Image
    W = 8 << z
    x0, y0, x1, y1 = art_box(prev)
    crop = prev.crop((x0, y0, x1 + 1, y1 + 1))
    w = n * W
    s = w / crop.width
    h = max(1, round(crop.height * s))
    im = crop.resize((w, h), Image.LANCZOS if s < 1 else Image.BICUBIC, reducing_gap=None)
    a = np.asarray(im).copy()
    a[..., 3] = np.where(a[..., 3] >= 128, 255, 0)
    a[a[..., 3] == 0] = 0
    T = h - n * W // 4
    return Image.fromarray(a, "RGBA"), (0, T)


def preview_frames(bld, style=None):
    """-> {(z, r): (image, (L, T))}, 20 frames.

    style: None (default) = the look of the BA's own BAT.DAT frames: zoom 4 = zoom 3 doubled (BAT.DAT entries 16-19
    name the zoom-3 pixels at scale 2, 15 of 15) and no palette cut (BAT.DAT zoom-3 frames hold a median of 1,418
    colours, max 2,219, against <= 255 in Maxis stock art; a 255-colour cut raised the zoom-3 RMS against them from
    19.0 to 19.5). A bldrender style name (task bldlook) applies its frame steps instead: `zoom4` ("double", or
    "native" = own zoom-4 resample when the preview has the pixels for it) and `palette`. Its light, contrast,
    saturation, grain and lawn steps correct bldrender's own renders and are never applied to BA art."""
    from PIL import Image, ImageOps
    import numpy as np
    import bldrender as R
    st = BA_LOOK if style is None else R.style_of(style)[1]
    prev, n = bld["preview"], bld["lot"]
    x0, _, x1, _ = art_box(prev)
    out = {}
    for z in range(ZOOMS):
        if z == 4 and (st.get("zoom4") == "double" or (x1 - x0 + 1) < n * 128):
            im3, (L3, T3) = out[(3, 0)]
            im, LT = im3.resize((im3.width * 2, im3.height * 2), Image.NEAREST), (0, T3 * 2)
        else:
            im, LT = _fit(prev, n, z)
            if st.get("palette"):
                im = Image.fromarray(R.palette_cut(np.asarray(im), st["palette"], st.get("dither", False)), "RGBA")
        im = R.quantize565(im)
        mir = ImageOps.mirror(im)
        for r in range(ROTS):
            out[(z, r)] = (mir if r % 2 else im, LT)
    return out


# =================================================================== frames from BAT.DAT

def bat_match(game, bld):
    """The BAT.DAT override record of the same building: by the .bld id (= BAT instance for 13 of 15 shipped
    buildings, batconvert design 1), else by name with the same lot size. -> batgrow building dict or None."""
    import batgrow as BG
    if not game.exists(BG.BAT_REL):
        return None
    bats = [b for b in BG.bat_buildings(game) if not b["problem"]]
    for b in bats:
        if b["inst"] == bld["ident"] and b["size"] == bld["lot"]:
            return b
    if bld.get("ident_from") == "crc32":
        # a 1999 .bld (no id in the file): a same-named BAT.DAT entry is another file's render (the 1999 Hotel Splash
        # is not the SC3U one: 58 against 115 texture names), so only its own render (keyed by the stand-in id) counts
        return None
    nm = bld["name"].encode("cp1252", "replace")
    for b in bats:
        if b["name"] == nm and b["size"] == bld["lot"]:
            return b
    return None


def bat_frames(b):
    """BAT.DAT table entries 0-15 -> {(z, r): (image, (L, T))}, zoom 4 = zoom 3 doubled (entries 16-19, flag 2)."""
    from PIL import Image
    import sprite_render as sr
    out = {}
    for k in range(16):
        key = b["entries"][k]
        px, an = b["pixels"][b["pix_keys"].index(key)]
        _kind, block, _inf = qfs.decode_record(px)
        L, T, _r, _b = struct.unpack("<4h", an)
        out[(k // 4, k % 4)] = (sr.span_to_image(block).convert("RGBA"), (L, T))
    for r in range(ROTS):
        im, (L, T) = out[(3, r)]
        out[(4, r)] = (im.resize((im.width * 2, im.height * 2), Image.NEAREST), (L * 2, T * 2))
    return out


# =================================================================== the side IXF (task sc3compat-a)
# render_bld.ps1 (the player's route: BaappW.exe + bawinonly.dll batch mode, no Python) writes the Building
# Architect's own render of a folder of .bld files to <folder>\bld_frames.ixf: BAT.DAT format, one random group
# per building and new instances (FUN_004534bb, FUN_00404d52), never merged into the game's BAT.DAT.
SIDE_NAME = "bld_frames.ixf"
_SIDE_CACHE = {}


def side_match(data, blds):
    """Buildings of a BA-rendered IXF (any group) -> [(bld, building dict or None)] in the order of `blds`.
    By the .bld id first (an IXF re-keyed by `render`), then by the name the renderer copied from the .bld's info
    record (FUN_004044a9 -> 0x1200be1d writes it into the override record) and the lot, each building used once and
    in the IXF's own order, so two .bld files of the same name and lot pair up in render order."""
    import batgrow as BG
    blt = [b for b in ixf_buildings(data) if not b["problem"]]
    used, out = set(), []
    for bld in blds:
        hit = None
        for k, b in enumerate(blt):
            if k not in used and b["inst"] == bld["ident"] and b["size"] == bld["lot"] and b["group"] == BG.BAT_GROUP:
                hit = k
                break
        out.append([bld, hit])
    for row in out:
        if row[1] is not None:
            used.add(row[1])
    for row in out:
        if row[1] is not None:
            continue
        nm = row[0]["name"].encode("cp1252", "replace")
        for k, b in enumerate(blt):
            if k not in used and b["name"] == nm and b["size"] == row[0]["lot"]:
                row[1] = k
                used.add(k)
                break
    return [(bld, blt[k] if k is not None else None) for bld, k in out]


def side_buildings(folder):
    """-> (path, data) of <folder>/bld_frames.ixf, or None. Cached by size and mtime."""
    path = os.path.join(folder, SIDE_NAME)
    try:
        st = os.stat(path)
    except OSError:
        return None
    key = (os.path.abspath(path), st.st_size, st.st_mtime_ns)
    if key not in _SIDE_CACHE:
        with open(path, "rb") as fh:
            _SIDE_CACHE.clear()
            _SIDE_CACHE[key] = fh.read()
    return path, _SIDE_CACHE[key]


def side_frames(bld):
    """The building's frames from the side IXF beside its .bld file, or None."""
    sb = side_buildings(os.path.dirname(os.path.abspath(bld["path"])))
    if sb is None:
        return None
    m = side_match(sb[1], [bld])[0][1]
    return bat_frames(m) if m is not None else None


def frames_from(bld, game=None, art="auto", style=None):
    """-> (frames, source, where): source 'bat' or 'preview', where 'bld_frames.ixf', 'BAT.DAT' or 'the .bld'.
    art: auto (bat when it exists), bat, preview. bat art comes from the side IXF beside the .bld (bld_frames.ixf, the
    player's own BA render) first, then from the game's BAT.DAT. style: bldrender style for preview art (BA frames
    are used as they are)."""
    if art not in ("auto", "bat", "preview"):
        raise BldError("art %r: use auto, bat or preview" % art)
    if art != "preview":
        f = side_frames(bld) if bld.get("path") else None
        if f is not None:
            return f, "bat", SIDE_NAME
        b = bat_match(game, bld) if game is not None else None
        if b is not None:
            return bat_frames(b), "bat", "BAT.DAT"
        if art == "bat":
            raise BldError("%s: neither %s beside it nor BAT.DAT holds this building" % (bld["file"], SIDE_NAME))
    return preview_frames(bld, style), "preview", "the .bld"


def frames(bld, game=None, art="auto", style=None):
    """-> (frames, source) with source 'bat' or 'preview' (frames_from without the where)."""
    return frames_from(bld, game, art, style)[:2]


def thumbnail(bld, size=160):
    """Preview on a neutral backdrop, for the classifier page / sheets."""
    from PIL import Image
    im = Image.new("RGBA", bld["preview"].size, (60, 100, 60, 255))
    im.alpha_composite(bld["preview"])
    return im.convert("RGB").resize((size, size), Image.LANCZOS)


# =================================================================== custom parts (task bldbat)

PART_KIND = {6: "paint", 7: "detail", 16: "prop"}       # last u32 of record 0xE3F87B0D (Trash & Burn, HiTech Lab)


def custom_textures(path):
    """Records 0xE3F87B0D (one per custom texture) and their embedded images 0xE3F87B10.
    Layout (the 84 records of the 17 shipped files; the 1999 records start with u8 7 and end after the key): u8 10, 8 x u32 (two rects), u32 hash (= the hash beside the name
    in the model's texture list), u32, 4 x f32 (w, h, 1/w, 1/h), u32 n, n bytes name, then the image record's key
    u32 type 0xE3F87B10, u32 group, u32 instance, and u32 kind (6 paint, 7 detail, 16 prop)."""
    with open(path, "rb") as fh:
        r = _records(fh.read())
    out = []
    for (g, i, t), pl in sorted(r.items(), key=lambda kv: kv[0][1]):
        if t != T_TEXINFO:
            continue
        h, = struct.unpack_from("<I", pl, 33)
        n, = struct.unpack_from("<I", pl, 57)
        name = pl[61:61 + n].decode("cp1252", "replace")
        if pl[0] == 7:
            # 1999 BA (BLD_FORMAT.md 6): same layout up to the image key, no trailing kind u32. Byte 36 (the top byte
            # of the u32 at 33) holds 6 or 7 in all 14 records of the 19 samples, the codes v8 stores as kind
            # [UNCERTAIN: read as kind from the values only, the v7 texture reader is not traced]
            it, ig, ii = struct.unpack_from("<3I", pl, 61 + n)
            kind = pl[36]
        else:
            it, ig, ii, kind = struct.unpack_from("<4I", pl, 61 + n)
        img = r.get((ig, ii, it))
        w = hh = None
        if img is not None:
            _f, w, hh, _n = struct.unpack_from("<HHHI", img, 0)
        out.append({"name": name, "hash": h, "kind": PART_KIND.get(kind, "kind %d" % kind), "w": w, "h": hh,
                    "embedded": img is not None, "image_key": (ig, ii, it)})
    return out


def embedded_image(path, part):
    """-> RGBA PIL image of an embedded custom texture (4 bytes per pixel as stored; written back as a 32-bit TGA
    it made the BA render the stripped .bld identically, verify/bldbat/RESULTS.md step 3)."""
    from PIL import Image
    with open(path, "rb") as fh:
        r = _records(fh.read())
    _f, w, h, raw = _image(r[tuple(part["image_key"])])
    return Image.frombuffer("RGBA", (w, h), raw, "raw", "RGBA", 0, 1)


def parts(path, game=None):
    """Every texture name the model uses and how the BA resolves it (verify/bldbat/RESULTS.md step 3):
    color = a solid colour, no file; embedded = the .bld carries the image and the renderer uses it; stock = a file
    under Apps/Res/BA; custom = a file under Apps/BACustom (used only when its content is the one the .bld was made
    with: a same-named file with other pixels was ignored); missing = drawn as a flat untextured face."""
    b = read_bld(path)
    emb = {p["name"].lower(): p for p in custom_textures(path)}
    files = {}
    if game is not None:
        for root in ("Res/BA", "BACustom"):
            for dp, _dn, fn in os.walk(game.path("Apps/" + root)):
                for f in fn:
                    files.setdefault(f.lower(), []).append(os.path.relpath(os.path.join(dp, f), game.path("Apps")))
    out, seen = [], set()
    for name, h in b["model"]["textures"]:
        k = name.lower()
        if not name or k in seen:
            continue
        seen.add(k)
        e = emb.get(k)
        row = {"name": name, "hash": h, "kind": e["kind"] if e else None, "where": None}
        if name.startswith("color "):
            row["status"] = "color"
        elif e is not None:
            row["status"] = "embedded"
        elif game is None:
            row["status"] = "file"
        else:
            hit = files.get(k, [])
            stock = [x for x in hit if x.lower().startswith("res")]
            if stock:
                row.update(status="stock", where=stock[0])
            elif hit:
                row.update(status="custom", where=hit[0])
            else:
                row["status"] = "missing"
        out.append(row)
    return out


# =================================================================== frames from the BA's batch renderer (bldbat)

def ixf_buildings(data):
    """batgrow.bat_buildings over an IXF in any group (the batch renderer draws a new group per building: LCG
    FUN_004534bb seeded by timeGetTime, FUN_004534a0). -> [building dict + 'group']."""
    import batgrow as BG

    class _G(BG.Game):
        def __init__(self):
            pass

        def read(self, rel):
            return data

    _idx, order = BG.records(data)
    out, keep = [], BG.BAT_GROUP
    groups = []
    for g, i, t in order:                   # groups in the order of their first override record (render order)
        if t == BG.OVR_TYPE and g not in groups:
            groups.append(g)
    try:
        for g in groups:
            BG.BAT_GROUP = g
            for b in BG.bat_buildings(_G()):
                b["group"] = g
                out.append(b)
    finally:
        BG.BAT_GROUP = keep
    return out


def rekey_rendered(data, blds, used=()):
    """Rendered IXF -> (records [(g, i, t, payload)], report [(file, id or None, error)]). Group -> 0xBA1DBF1E;
    override instance, table instance and the override's last u32 -> the .bld id (matched by name and lot, else by
    lot in order); the 16 pixel records -> consecutive instances on a block free in `used` (keys of the target
    BAT.DAT). The renderer's own instance is the loaded building's +0x1a8 or a new id (FUN_00404d73 / FUN_00404d52)."""
    import batgrow as BG
    idx, _order = BG.records(data)
    taken = set(i for g, i, t in used if g == BG.BAT_GROUP)
    pending = list(blds)
    recs, report = [], []
    for b in ixf_buildings(data):
        nm = b["name"].decode("cp1252", "replace")
        m = [x for x in pending if x["name"] == nm and x["lot"] == b["size"]] or \
            [x for x in pending if x["lot"] == b["size"]]
        if not m or b["problem"]:
            report.append((nm, None, b["problem"] or "no matching .bld"))
            continue
        bld = m[0]
        pending.remove(bld)
        g, inst = b["group"], b["inst"]
        ovr = bytearray(idx[(g, inst, BG.OVR_TYPE)])
        key = struct.unpack_from("<3I", ovr, 1)
        tab = bytearray(idx[(key[1], key[2], key[0])])
        new = bld["ident"]
        base = (new * 16 + 0x10) & 0xFFFFFFF0
        while any(((base + k) & 0xFFFFFFFF) in taken for k in range(16)) or base > 0xFFFFFFE0:
            base = (base + 0x1F3B0) & 0xFFFFFFF0
        remap = {pk: base + k for k, pk in enumerate(b["pix_keys"])}
        taken.update(remap.values())
        taken.add(new)
        struct.pack_into("<3I", ovr, 1, key[0], BG.BAT_GROUP, new)
        if struct.unpack_from("<I", ovr, len(ovr) - 4)[0] == inst:
            struct.pack_into("<I", ovr, len(ovr) - 4, new)
        for k in range((len(tab) - 0x18) // 15):
            pg, pi = struct.unpack_from("<II", tab, 0x18 + 15 * k + 2)
            struct.pack_into("<II", tab, 0x18 + 15 * k + 2, BG.BAT_GROUP, remap[(pg, pi)])
        recs.append((BG.BAT_GROUP, new, key[0], bytes(tab)))
        for (pg, pi), ni in remap.items():
            recs.append((BG.BAT_GROUP, ni, 1, idx[(pg, pi, 1)]))
            recs.append((BG.BAT_GROUP, ni, 0, idx[(pg, pi, 0)]))
        recs.append((BG.BAT_GROUP, new, BG.OVR_TYPE, bytes(ovr)))
        report.append((bld["file"], new, None))
    for x in pending:
        report.append((x["file"], None, "not in the render output (the BA did not load it)"))
    return recs, report


def install_bat(game, recs):
    """Merge rendered records into <game>/Apps/BARender/BAT.DAT; entries with the same override instance are replaced.
    Backup BAT.DAT.bldbat-orig once. Delete-then-write (test trees hard-link BAT.DAT). -> (records dropped, added)."""
    import batgrow as BG
    path = game.path(BG.BAT_REL)
    old = game.read(BG.BAT_REL)
    bak = path + ".bldbat-orig"
    if not os.path.exists(bak):
        with open(bak, "wb") as fh:
            fh.write(old)
    idx, order = BG.records(old)
    new_ovr = set(i for g, i, t, _p in recs if t == BG.OVR_TYPE)
    drop = set()
    for g, i, t in order:
        if t == BG.OVR_TYPE and g == BG.BAT_GROUP and i in new_ovr:
            key = struct.unpack_from("<3I", idx[(g, i, t)], 1)
            tab = idx.get((key[1], key[2], key[0]))
            drop.add((g, i, t))
            if tab is not None:
                drop.add((key[1], key[2], key[0]))
                for k in range((len(tab) - 0x18) // 15):
                    pg, pi = struct.unpack_from("<II", tab, 0x18 + 15 * k + 2)
                    drop.update({(pg, pi, 0), (pg, pi, 1)})
    keep = [(g, i, t, idx[(g, i, t)]) for g, i, t in order if (g, i, t) not in drop]
    out = BG.new_container(keep + list(recs))
    os.remove(path)
    with open(path, "wb") as fh:
        fh.write(out)
    return len(drop), len(recs)


def render_bat(paths, game, out, install=False, log=print):
    """BA batch render of .bld files -> normalised BAT-format IXF at `out` (and the game's BAT.DAT with install).
    -> (ba_render result, report, install counts or None)."""
    import batgrow as BG
    sys.path.insert(0, os.path.join(TOOLS, "bldbat"))
    import ba_render
    blds = [read_bld(p) for p in paths]
    raw = out + ".raw.ixf"
    res = ba_render.render(game.root, raw, paths, log)
    with open(raw, "rb") as fh:
        data = fh.read()
    used = BG.records(game.read(BG.BAT_REL))[1] if game.exists(BG.BAT_REL) else []
    recs, report = rekey_rendered(data, blds, used)
    with open(out, "wb") as fh:
        fh.write(BG.new_container(recs))
    os.remove(raw)
    inst = install_bat(game, recs) if install and recs else None
    return res, report, inst


# =================================================================== CLI

def _bld_paths(args):
    out = []
    for a in args:
        if os.path.isdir(a):
            out += [os.path.join(a, n) for n in sorted(os.listdir(a)) if n.lower().endswith(".bld")]
        else:
            out.append(a)
    return out


def cmd_info(a):
    bad = 0
    for p in _bld_paths(a.paths):
        try:
            b = read_bld(p)
        except (BldError, OSError, struct.error, qfs.QfsError) as e:
            print("%s: %s" % (os.path.basename(p), e))
            bad += 1
            continue
        m = b["model"]
        print("%-30s %dx%d  \"%s\" by %s  id %08X  category 0x%s -> %s  grid %d x %d x %d  %d texture names, "
              "%d custom  class %s" % (
                  b["file"], b["lot"], b["lot"], b["name"], b["architect"], b["ident"],
                  "%X" % b["category"] if b["category"] is not None else "-", zone_of(b) or "?", m["grid"],
                  m["grid"], m["height"], len(m["textures"]), b["custom_textures"], suggest_class(b)))
    return 1 if bad else 0


def cmd_sheet(a):
    import batgrow as BG
    import bldrender as R
    b = read_bld(a.file)
    game = BG.Game(a.game) if a.game else None
    fr, src = frames(b, game, a.art)
    R.sheet(fr, a.out, scale=a.scale)
    print("wrote %s (%s art)" % (a.out, src))
    return 0


def _cmp(a, b):
    import numpy as np
    A, B = np.asarray(a).astype(float), np.asarray(b).astype(float)
    H, W = min(A.shape[0], B.shape[0]), min(A.shape[1], B.shape[1])
    A, B = A[-H:, :W], B[-H:, :W]
    ma, mb = A[..., 3] >= 128, B[..., 3] >= 128
    both = ma & mb
    iou = both.sum() / max(1, (ma | mb).sum())
    rms = float(np.sqrt(((A[..., :3] - B[..., :3])[both] ** 2).mean())) if both.any() else 0.0
    return iou, rms


def cmd_check(a):
    """Preview frames against the same building's BAT.DAT frames: slot 0 per zoom (what the preview is), and
    slots 1-3 with the picture as it is against mirrored (what this tool chose)."""
    import numpy as np
    from PIL import ImageOps
    import batgrow as BG
    game = BG.Game(a.game)
    rows, s0, alt = [], {z: [] for z in range(4)}, {r: {"same": [], "mirror": []} for r in (1, 2, 3)}
    for p in _bld_paths(a.paths):
        bld = read_bld(p)
        bm = bat_match(game, bld)
        if bm is None:
            print("%-30s not in BAT.DAT" % bld["file"])
            continue
        bf, pf = bat_frames(bm), preview_frames(bld)
        cells = []
        for z in range(4):
            iou, rms = _cmp(pf[(z, 0)][0], bf[(z, 0)][0])
            dT = pf[(z, 0)][1][1] - bf[(z, 0)][1][1]
            s0[z].append((iou, rms, dT))
            cells.append("z%d IoU %.3f RMS %4.1f dT %+d" % (z, iou, rms, dT))
        for r in (1, 2, 3):
            im = pf[(3, 0)][0]
            alt[r]["same"].append(_cmp(im, bf[(3, r)][0]))
            alt[r]["mirror"].append(_cmp(ImageOps.mirror(im), bf[(3, r)][0]))
        print("%-30s %s" % (bld["file"], " | ".join(cells)))
    if not s0[0]:
        return 1
    print("\nslot 0, mean over %d buildings:" % len(s0[0]))
    for z in range(4):
        v = np.array(s0[z])
        print("  zoom %d: IoU %.3f (min %.3f)  RMS %.1f  |dT| max %d" % (
            z, v[:, 0].mean(), v[:, 0].min(), v[:, 1].mean(), int(abs(v[:, 2]).max())))
    print("slots 1-3 at zoom 3 (preview as is vs mirrored, against the real view):")
    for r in (1, 2, 3):
        sm, mi = np.array(alt[r]["same"]), np.array(alt[r]["mirror"])
        print("  slot %d: as is IoU %.3f RMS %.1f | mirrored IoU %.3f RMS %.1f" % (
            r, sm[:, 0].mean(), sm[:, 1].mean(), mi[:, 0].mean(), mi[:, 1].mean()))
    return 0


def cmd_js_expect(a):
    """Expected values for bld_js_check.mjs (the classifier page's reader and bldweb.js readBld): name, lot, category,
    id, class, model fields, and the sha256 of the preview as RGBA bytes expanded as the page does (x * 255 / 31 or 63
    stored into a Uint8ClampedArray, which rounds half to even like np.round) and as bldweb.js / preview_image do
    (floor)."""
    import hashlib
    import json
    import numpy as np
    out = {}
    for p in _bld_paths(a.paths):
        b = read_bld(p)
        with open(p, "rb") as fh:
            raw = _image(_records(fh.read())[(GROUP, I_PREVIEW, T_PREVIEW)])[3]
        v = np.frombuffer(raw, "<u2").astype(np.float64)
        rgba = np.stack([np.round(((v.astype(np.int64) >> 11) & 31) * 255 / 31),
                         np.round(((v.astype(np.int64) >> 5) & 63) * 255 / 63),
                         np.round((v.astype(np.int64) & 31) * 255 / 31),
                         np.where(v == KEY565, 0, 255)], -1).astype(np.uint8)
        out[b["file"]] = {"name": b["name"], "architect": b["architect"], "lot": b["lot"], "category": b["category"],
                          "ident": b["ident"], "ident_from": b["ident_from"], "version": b["model"]["version"],
                          "height": b["model"]["height"], "grid": b["model"]["grid"],
                          "textures": len(b["model"]["textures"]), "custom": b["custom_textures"],
                          "class": suggest_class(b),
                          "preview_sha": hashlib.sha256(rgba.tobytes()).hexdigest(),
                          "preview_sha_floor": hashlib.sha256(np.asarray(b["preview"]).tobytes()).hexdigest()}
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1)
    print("wrote %s (%d files)" % (a.out, len(out)))
    return 0


def cmd_parts(a):
    import batgrow as BG
    game = BG.Game(a.game) if a.game else None
    for p in _bld_paths(a.paths):
        rows = parts(p, game)
        cnt = {}
        for r in rows:
            cnt[r["status"]] = cnt.get(r["status"], 0) + 1
        print("%s: %s" % (os.path.basename(p), ", ".join("%d %s" % (v, k) for k, v in sorted(cnt.items()))))
        for r in rows:
            if r["status"] in ("embedded", "custom", "missing") or a.all:
                print("   %-9s %-7s %-34s %08X %s" % (r["status"], r["kind"] or "", r["name"], r["hash"],
                                                    r["where"] or ""))
    return 0


def cmd_render(a):
    import batgrow as BG
    game = BG.Game(a.game)
    res, report, inst = render_bat(_bld_paths(a.paths), game, a.out, a.install)
    bad = 0
    for f, ident, err in report:
        if err:
            bad += 1
            print("%-30s FAILED: %s" % (f, err))
        else:
            print("%-30s id %08X" % (f, ident))
    print("wrote %s (%d buildings, BA render %.1f s, display mode changes %d)" % (
        a.out, len(report) - bad, res.get("ms", 0) / 1000.0, res["mode_changes"]))
    if inst:
        print("installed into %s: replaced %d old records, added %d" % (game.path(BG.BAT_REL), inst[0], inst[1]))
    return 1 if bad else 0


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("info")
    s.add_argument("paths", nargs="+")
    s = sub.add_parser("sheet")
    s.add_argument("file")
    s.add_argument("--out", required=True)
    s.add_argument("--game")
    s.add_argument("--art", default="auto")
    s.add_argument("--scale", type=int, default=1)
    s = sub.add_parser("check")
    s.add_argument("--game", required=True)
    s.add_argument("paths", nargs="+")
    s = sub.add_parser("js-expect")
    s.add_argument("--out", required=True)
    s.add_argument("paths", nargs="+")
    s = sub.add_parser("parts")
    s.add_argument("--game")
    s.add_argument("--all", action="store_true", help="list stock files and colours too")
    s.add_argument("paths", nargs="+")
    s = sub.add_parser("render")
    s.add_argument("--game", required=True, help="dev tree with BaappW.exe + bawinonly.dll (bldbat/ba_patch.py)")
    s.add_argument("--out", required=True)
    s.add_argument("--install", action="store_true", help="also merge into the tree's Apps/BARender/BAT.DAT")
    s.add_argument("paths", nargs="+")
    a = ap.parse_args(argv)
    try:
        return {"info": cmd_info, "sheet": cmd_sheet, "check": cmd_check, "js-expect": cmd_js_expect,
                "parts": cmd_parts, "render": cmd_render}[a.cmd](a)
    except BldError as e:
        print("bldfile: %s" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
