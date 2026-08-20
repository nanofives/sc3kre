#!/usr/bin/env python3
r"""sprite_patch.py -- the WRITE path for sprite archives, end to end.

`sprite_encode.py` proved the block encoder (62,552/62,552 byte-identical) and `qfs_encode.py`
proved the compressor (63,931/63,931), but nothing joined them to a file on disk. Three links
were missing, and they are what this module adds:

  1. **the 0x14 sprite record header writer** -- `qfs.record_header()` only unpacks. The one
     field that cannot be copied verbatim is `d4`: measured across the corpus it is
     `len(stream) + 4` (e.g. 00000005_Roads.DAT rec 1: size 4545, stream 4525, d4 4529).
     Note `qfs.decode_record` reports `d4_matches_stream = (d4 == len(stream))`, which is
     **False on every shipped record** -- it is a diagnostic, not the rule.
  2. **`.IXF` record replacement** -- `ixf_parse.build()` writes payloads at their recorded
     ABSOLUTE offsets and raises on overlap; nothing recomputed offsets when a payload changed
     length. `repack()` here does, the way `syspak_parse.replace_member()` does for `SYS.PAK`.
  3. **a pixel edit that does not disturb the span structure** -- `recolor()` rewrites only
     non-key pixels, so every row's lead/span/opaque flag is unchanged and the re-encoded block
     is the same LENGTH as the shipped one. That keeps the edit to one variable: colour.

The bar these tools are held to is byte-identical, so the honest first check is that a no-op
repack reproduces the input exactly:

  py -3.12 re/tools/sprite_patch.py Apps/Res/Sprites --selftest      # identity repack, N/N
  py -3.12 re/tools/sprite_patch.py Apps/Res/Sprites --pngtest       # PNG round-trip, N/N
  py -3.12 re/tools/sprite_patch.py <file.DAT> --info
  py -3.12 re/tools/sprite_patch.py <file.DAT> --recolor F800 --out <new.DAT>

`--recolor` takes an RGB565 (or RGB555, per record) value as hex. It is a test instrument: it
paints every visible pixel of every format-1 record one flat colour, which is deliberately
unmissable rather than tasteful.

**Replacing art with your own image** -- export, edit in any editor, import:

  py -3.12 re/tools/sprite_patch.py <file.DAT> --export 21 --png mine.png
  py -3.12 re/tools/sprite_patch.py <file.DAT> --import-png 21=mine.png --out <new.DAT>

`--import-png` takes a comma-separated `slot=file.png` list, so several records can be replaced
in one pass. Three things about it are worth knowing before you draw anything:

  - **The size must match exactly.** Changing a sprite's dimensions is untested -- the type-1
    anchor record and the `.SII` span/registration values would have to move with it -- so a
    mismatch is refused with the expected size rather than guessed at.
  - **Alpha is a threshold, not a channel.** The format has no alpha, only a per-record colour
    key, so a pixel is either drawn or it is the key. `--alpha-threshold` (default 128) is where
    the cut falls.
  - **Opaque magenta is the one colour you cannot draw.** Both colour keys decode to
    (255,0,255), so an opaque magenta pixel would quantize onto the key and vanish; those are
    moved one step in blue and the count is reported.
"""
import csv
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ixf_parse
import qfs
import qfs_encode
import sprite_encode
import sprite_render as sr

FREE = 0xFFFFFFFF


class SpritePatchError(Exception):
    pass


# --- link 1: the sprite record header --------------------------------------------------

def pack_payload(hdr, stream):
    """Build a 0x14-byte sprite record header + QFS stream -> payload bytes.

    `hdr` is a dict as returned by `qfs.record_header()`. d0..d3 are carried through unchanged
    (d0 holds the format code, d2/d3 the dimensions the format-0 path uses); only d4 is
    recomputed, as `len(stream) + 4`.
    """
    out = struct.pack("<5I", hdr["d0"], hdr["d1"], hdr["d2"], hdr["d3"], len(stream) + 4)
    return out + bytes(stream)


# --- link 2: .IXF record replacement with offset recomputation -------------------------

def _live(slots):
    return [i for i, s in enumerate(slots)
            if s[3] != FREE and s[4] != FREE and s[:3] != (0, 0, 0)]


def repack(d, replacements=None):
    """Rebuild a container, substituting payloads by SLOT INDEX and recomputing the index.

    `replacements` maps slot index -> new payload bytes. Payloads are re-emitted in their
    original offset order, packed from the original first-payload offset, so the magic, the
    index and the reserved pad keep their positions and only offsets/sizes move.

    Refuses containers whose payloads are not contiguous, rather than guessing what the gaps
    mean: `ixf_parse.layout()` documents two real cases of unreferenced bytes in this corpus
    (`U-039` .SNR tails, orphaned string payloads), and silently dropping or shifting those
    would produce a file that is not the one we read.
    """
    replacements = replacements or {}
    slots = ixf_parse.read_index_slots(d)
    live = _live(slots)
    if not live:
        raise SpritePatchError("no live index slots")
    index_end = 4 + len(slots) * ixf_parse.REC
    first_data = min(slots[i][3] for i in live)
    if first_data < index_end:
        raise SpritePatchError("first payload at %d overlaps the index end %d"
                               % (first_data, index_end))
    pad = d[index_end:first_data]

    order = sorted(live, key=lambda i: slots[i][3])
    cursor = first_data
    for i in order:
        if slots[i][3] != cursor:
            raise SpritePatchError(
                "payloads are not contiguous: slot %d starts at %d, expected %d "
                "(unreferenced bytes in between -- refusing to guess)"
                % (i, slots[i][3], cursor))
        cursor += slots[i][4]
    tail = d[cursor:]

    new_slots = list(slots)
    body = bytearray()
    off = first_data
    for i in order:
        pay = replacements.get(i)
        if pay is None:
            pay = d[slots[i][3]:slots[i][3] + slots[i][4]]
        s = list(slots[i])
        s[3], s[4] = off, len(pay)
        new_slots[i] = tuple(s)
        body += pay
        off += len(pay)

    out = bytearray(struct.pack("<I", ixf_parse.MAGIC))
    for s in new_slots:
        out += struct.pack("<5I", *s)
    out += pad
    out += body
    out += tail
    return bytes(out)


def roundtrip(path):
    """-> (ok, detail). A no-op repack must reproduce the file byte for byte."""
    with open(path, "rb") as fh:
        d = fh.read()
    if len(d) < 4 or struct.unpack_from("<I", d, 0)[0] != ixf_parse.MAGIC:
        return None, "not an .IXF container"
    try:
        rebuilt = repack(d)
    except (SpritePatchError, ixf_parse.IxfError, struct.error) as e:
        return False, "%s: %s" % (type(e).__name__, e)
    if rebuilt == d:
        slots = ixf_parse.read_index_slots(d)
        return True, "%d slots, %d live" % (len(slots), len(_live(slots)))
    if len(rebuilt) != len(d):
        return False, "length %d != %d" % (len(rebuilt), len(d))
    for i in range(len(d)):
        if rebuilt[i] != d[i]:
            return False, "first difference at byte %d" % i
    return False, "unknown"


# --- link 3: the pixel edit ------------------------------------------------------------

# Colour keys bind to pixel layout (QFS.md): 0xF81F is magenta in RGB565, 0x7C1F in RGB555.
RED = {0xF81F: 0xF800, 0x7C1F: 0x7C00}


def recolor_record(payload, colour=None):
    """-> new payload with every non-key pixel set to `colour`, or None if not a format-1 sprite.

    Returns None (rather than raising) for records this edit does not apply to, so a caller can
    walk a whole container and leave the rest untouched.
    """
    kind, block, info = qfs.decode_record(payload)
    if kind != "qfs" or info["format"] != 1:
        return None
    surf, m = sprite_encode.block_to_surface(block)
    key = m["key"]
    tgt = colour if colour is not None else RED.get(key)
    if tgt is None:
        raise SpritePatchError("no red defined for colour key 0x%04X" % key)
    if tgt == key:
        raise SpritePatchError("colour 0x%04X is the transparency key" % tgt)
    painted = [tgt if p != key else key for p in surf]
    new_block = sprite_encode.encode(painted, m["w"], m["h"], key, m["b"], m["a"])
    if len(new_block) != len(block):
        # Recoloring must not move the span structure; if it did, the assumption is wrong.
        raise SpritePatchError("block length changed %d -> %d" % (len(block), len(new_block)))
    stream = qfs_encode.compress_stream(new_block, quick=1)
    return pack_payload(info, stream)


def recolor_container(path, out_path, colour=None, progress=None):
    """Recolor every format-1 record. -> (n_patched, n_skipped, out_bytes)."""
    with open(path, "rb") as fh:
        d = fh.read()
    slots = ixf_parse.read_index_slots(d)
    reps, skipped = {}, 0
    for n, i in enumerate(_live(slots)):
        s = slots[i]
        payload = d[s[3]:s[3] + s[4]]
        try:
            new = recolor_record(payload, colour)
        except (qfs.QfsError, struct.error):
            new = None
        if new is None:
            skipped += 1
        else:
            reps[i] = new
        if progress and n % 250 == 0:
            progress(n, len(reps), skipped)
    blob = repack(d, reps)
    with open(out_path, "wb") as fh:
        fh.write(blob)
    return len(reps), skipped, blob


# --- link 4: PNG in / PNG out ----------------------------------------------------------
#
# The quantizers below are the EXACT inverse of sprite_render's decoders, and that is measured,
# not assumed: for all 65,536 RGB565 values and all 32,768 RGB555 values,
# quantize(rgb565(v)) == v. It holds because the decoder expands with `c * 255 // 31` (or //63),
# which equals `c << 3` (or `<< 2`) plus a remainder strictly smaller than the shift, so the
# shift back recovers c. That exactness is what lets `png_roundtrip()` demand byte-identical
# output rather than "close enough".

def quantize565(r, g, b):
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def quantize555(r, g, b):
    return ((r >> 3) << 10) | ((g >> 3) << 5) | (b >> 3)


def image_to_surface(img, w, h, key, alpha_threshold=128):
    """PIL image -> (surface, n_nudged). Refuses a size mismatch.

    Alpha is a threshold, not a channel: this format has **no alpha**, only a per-record colour
    key (`QFS.md`), so a pixel is either drawn or it is the key. `alpha_threshold` is where the
    cut falls, and it is a parameter because there is no right answer to inherit from the format.

    **The nudge.** Both colour keys decode to magenta (255,0,255), so an OPAQUE magenta pixel in
    a source image would quantize straight onto the key and silently turn transparent. Those
    pixels are moved by one step in blue instead, and the count is returned so a caller can say
    so out loud rather than shipping a hole in the art.
    """
    from PIL import Image                                    # noqa: F401  (import guarded here)
    if img.size != (w, h):
        raise SpritePatchError(
            "image is %dx%d but this record is %dx%d -- changing a sprite's dimensions is "
            "untested (the type-1 anchor record and the .SII span values would also have to "
            "move), so resize the image instead" % (img.width, img.height, w, h))
    img = img.convert("RGBA")
    quant = quantize555 if key == sr.KEY_555 else quantize565
    surf = [key] * (w * h)
    nudged = 0
    for i, (r, g, b, a) in enumerate(img.getdata()):
        if a < alpha_threshold:
            continue
        v = quant(r, g, b)
        if v == key:
            v = key ^ 1                                      # one step in blue, still magenta
            nudged += 1
        surf[i] = v
    return surf, nudged


def export_png(payload, path):
    """Write a format-1 record to a PNG. -> (w, h).

    Uses `sprite_render.span_to_image()`, the decoder already validated against the corpus, so
    what you edit is by construction what the game reads.
    """
    kind, block, inf = qfs.decode_record(payload)
    if kind != "qfs" or inf["format"] != 1:
        raise SpritePatchError("not a format-1 sprite record (kind %s, format %s)"
                               % (kind, inf.get("format")))
    img = sr.span_to_image(block)
    img.save(path)
    return img.width, img.height


def replace_from_png(payload, png_path, alpha_threshold=128):
    """-> (new payload, n_nudged). Substitute a record's pixels from a PNG."""
    from PIL import Image
    kind, block, inf = qfs.decode_record(payload)
    if kind != "qfs" or inf["format"] != 1:
        raise SpritePatchError("not a format-1 sprite record")
    m = sr.parse_span_block(block)
    surf, nudged = image_to_surface(Image.open(png_path), m["w"], m["h"], m["key"],
                                   alpha_threshold)
    new_block = sprite_encode.encode(surf, m["w"], m["h"], m["key"], m["b"], m["a"])
    stream = qfs_encode.compress_stream(new_block, quick=1)
    return pack_payload(inf, stream), nudged


def png_roundtrip(payload):
    """-> (ok, detail). Export a shipped record to PNG, re-import it, demand the SAME payload.

    This is the bar that makes the quantizer trustworthy. It is only passable because the
    decoder's expansion is exactly invertible and because `span_to_image` maps both unstored and
    key-valued pixels to alpha 0, which `image_to_surface` maps back to the key.
    """
    import io
    from PIL import Image
    kind, block, inf = qfs.decode_record(payload)
    if kind != "qfs" or inf["format"] != 1:
        return None, "not a format-1 sprite record"
    m = sr.parse_span_block(block)
    buf = io.BytesIO()
    sr.span_to_image(block).save(buf, format="PNG")
    buf.seek(0)
    surf, nudged = image_to_surface(Image.open(buf), m["w"], m["h"], m["key"])
    if nudged:
        return False, "%d pixel(s) collided with the colour key" % nudged
    rebuilt = sprite_encode.encode(surf, m["w"], m["h"], m["key"], m["b"], m["a"])
    if rebuilt == block:
        return True, "%dx%d" % (m["w"], m["h"])
    if len(rebuilt) != len(block):
        return False, "block length %d != %d" % (len(rebuilt), len(block))
    for i, (a, b) in enumerate(zip(rebuilt, block)):
        if a != b:
            return False, "first diff at block byte %d" % i
    return False, "unknown"


def png_selftest(target):
    """Export->import every format-1 record in a file or tree. -> (ok, bad, skipped)."""
    ok = bad = skipped = 0
    for path in qfs.archives(target):
        with open(path, "rb") as fh:
            d = fh.read()
        slots = ixf_parse.read_index_slots(d)
        for i in _live(slots):
            s = slots[i]
            try:
                res, detail = png_roundtrip(d[s[3]:s[3] + s[4]])
            except (qfs.QfsError, SpritePatchError, struct.error):
                res, detail = None, "undecodable"
            if res is None:
                skipped += 1
            elif res:
                ok += 1
            else:
                bad += 1
                print("FAIL %s slot %d: %s" % (os.path.basename(path), i, detail))
    return ok, bad, skipped


# --- link 5: the colour-index probe (which record is that thing on screen?) -------------
#
# There is no shipped table from "the building I can see" to a sprite slot. This builds the
# mapping empirically, in one run, by making the art carry its own identity: every format-1
# record is repainted a UNIQUE flat 16-bit colour, and a screenshot is then read back.
#
# It works because of a measured property of the render path: a sprite's 16-bit pixel value
# reaches the framebuffer EXACTLY, with no shading, blending or dithering. Measured on
# verify/sprite_mod_test's runs -- 99,802 screen pixels of one flat value, zero variation.
#
# One trap, and it is the reason this is written down rather than assumed: the FRAMEBUFFER
# expands 5/6/5 to 8/8/8 by SHIFTING (0xF800 -> (248,0,0)), while sprite_render's decoder
# expands by SCALING (0xF800 -> (255,0,0)). Different results, same inverse: >>3 / >>2 recovers
# the original bits from either. So screen pixels are quantized with the same function as PNGs.

PROBE_SKIP = (0x0000, sr.KEY_555, 0xF81F)      # 0 reads as black on screen; the two keys vanish


def probe_values(n, start=1):
    """-> list of n distinct 16-bit values usable as identities, skipping unusable ones."""
    vals, v = [], start
    while len(vals) < n:
        if v > 0xFFFF:
            raise SpritePatchError("ran out of 16-bit identities at %d records" % len(vals))
        if v not in PROBE_SKIP:
            vals.append(v)
        v += 1
    return vals


def build_index_probe(paths, out_dir, csv_path):
    """Repaint every format-1 record in `paths` a unique colour. -> (n_records, rows).

    Writes one modified container per input into `out_dir`, and a CSV mapping colour -> record.
    """
    os.makedirs(out_dir, exist_ok=True)
    todo = []
    for p in sorted(paths):
        with open(p, "rb") as fh:
            d = fh.read()
        slots = ixf_parse.read_index_slots(d)
        for i in _live(slots):
            s = slots[i]
            if s[2] != qfs.TYPE_PIXELS:
                continue
            try:
                kind, block, inf = qfs.decode_record(d[s[3]:s[3] + s[4]])
            except (qfs.QfsError, struct.error):
                continue
            if kind != "qfs" or inf["format"] != 1:
                continue
            todo.append((p, i, s, block, inf))

    vals = probe_values(len(todo))
    rows, per_file = [], {}
    for (p, i, s, block, inf), val in zip(todo, vals):
        m = sr.parse_span_block(block)
        surf, _ = sprite_encode.block_to_surface(block)
        key = m["key"]
        painted = [val if q != key else key for q in surf]
        nb = sprite_encode.encode(painted, m["w"], m["h"], key, m["b"], m["a"])
        stream = qfs_encode.compress_stream(nb, quick=1)
        per_file.setdefault(p, {})[i] = pack_payload(inf, stream)
        rows.append({"colour": "0x%04X" % val, "file": os.path.basename(p), "slot": i,
                     "group": "0x%08X" % s[0], "instance": "0x%08X" % s[1],
                     "w": m["w"], "h": m["h"]})

    for p, reps in per_file.items():
        with open(p, "rb") as fh:
            d = fh.read()
        out = os.path.join(out_dir, os.path.basename(p))
        with open(out, "wb") as fh:
            fh.write(repack(d, reps))

    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["colour", "file", "slot", "group", "instance", "w", "h"])
        w.writeheader()
        w.writerows(rows)
    return len(rows), rows


def decode_shot(shot_path, csv_path, box=None, at=None):
    """Read a probe screenshot back. -> list of (count, row) for records that are visible.

    `box` limits the region (the game client, to exclude UI). `at` asks about one pixel.
    """
    import collections
    from PIL import Image
    with open(csv_path, newline="", encoding="utf-8") as fh:
        table = {int(r["colour"], 16): r for r in csv.DictReader(fh)}
    img = Image.open(shot_path).convert("RGB")
    if at is not None:
        r, g, b = img.getpixel(at)
        v = quantize565(r, g, b)
        return v, table.get(v), (r, g, b)
    region = img.crop(box) if box else img
    seen = collections.Counter()
    for r, g, b in region.getdata():
        seen[quantize565(r, g, b)] += 1
    hits = [(n, table[v]) for v, n in seen.items() if v in table]
    hits.sort(reverse=True, key=lambda t: t[0])
    return hits


# --- link 6: the OBJECT index (instance layout decoded) --------------------------------
#
# INSTANCE LAYOUT -- partly decoded, and the limits are stated because a tidier version of this
# comment was written first and then FALSIFIED at corpus scale.
#
#     objectId = instance >> 16                    [CONFIRMED] groups all 62,552 pixel records
#                                                  into 1,433 coherent objects
#
# For the 596 objects whose low words are EXACTLY 0x0000..0x000F [CONFIRMED]:
#
#     low = (zoom << 2) | rotation      zoom 0..3, rotation 0..3
#
#   Evidence: 585 of those 596 have a width that is constant within each zoom and strictly
#   increasing across zooms, roughly doubling each step; and object 0x00CF of
#   0000000B_Utilities.DAT was rendered as a 4x4 contact sheet showing exactly 4 zoom levels
#   (32/64/128/256 px) x 4 isometric rotations. The 11 exceptions are content-cropping
#   artifacts (rotations differing by a few px, or two tiny zooms both landing on 4 px), not
#   counterexamples. The colour-index probe corroborates it: with the camera at max zoom and
#   rotation 0, EVERY on-screen record ended in 0x000C = (3 << 2) | 0.
#
# For the other 817 objects the low word goes far above 0x000F -- values like 0x1000..0x100F,
# 0x1014..0x101B, up to 0x11EF observed, and up to 416 pixel records for one object. There is
# clearly a further field above bit 12 plus something frame-like in the middle bits, and it is
# [UNCERTAIN]: a split of [15:12] kind / [11:4] frame / [3:2] zoom / [1:0] rotation was tried
# and does NOT hold (1,022 of 4,720 groups had a width non-monotonic in the supposed zoom bits,
# and every supposed zoom bucket had the same width range). DO NOT rely on it.
#
# PRACTICAL CONSEQUENCE, and it is the useful part: editing "a building" means editing up to 16
# records for a simple object and up to several hundred for an animated one -- never just one.
# Use `object_index()` to list them, and the colour-index probe to find which object you mean.

ZOOM_WIDTH = {0: 32, 1: 64, 2: 128, 3: 256}       # nominal; real sprites are cropped to content


def split_instance(instance):
    """-> (objectId, zoom, rotation). Only meaningful when `low <= 0x0F` -- see the note above.

    `zoom`/`rotation` are the low-word reading that is confirmed for the 596 simple objects. For
    an object with a larger low word the same bits still vary, but the fields above them are not
    decoded, so treat the result as a label rather than as geometry.
    """
    return (instance >> 16) & 0xFFFF, (instance >> 2) & 0x3, instance & 0x3


def make_instance(object_id, zoom, rotation):
    """-> instance. The inverse of split_instance() for simple (low <= 0x0F) objects."""
    if not 0 <= zoom <= 3 or not 0 <= rotation <= 3:
        raise SpritePatchError("zoom and rotation are 0..3 (got %r, %r)" % (zoom, rotation))
    return ((object_id & 0xFFFF) << 16) | ((zoom & 3) << 2) | (rotation & 3)


def art_names(occ_dir="Apps/Res/Occupant", ini_path="re/data/syspak/Occupant.ini",
              sprites_dir="Apps/Res/Sprites"):
    """-> {(group, instance): name} for attrib tables, from the binary occupant records.

    `OccupantAttribs*.IXF` property 0x64 is the better source than `Occupant.ini`: it is the
    authored name, **1,108/1,108** TKB1 records carry both it and property 0x67, and keying on
    0x67's full (group, instance) avoids assuming the record's own numbering. The set archives
    also carry their own TKB1 records, so they are scanned too.

    `Occupant.ini` is still merged in as a fallback for group 0x6400 only, which is the group its
    flat `instance = name` form can be trusted to mean.
    """
    names = {}
    try:
        names, _ = occupant_attribs(occ_dir, sprites_dir)
    except OSError:
        names = {}
    if os.path.exists(ini_path):
        for oid, nm in occupant_names(ini_path).items():
            names.setdefault((CSATTRIB_GROUP, oid), nm)
    return names


def art_owner_index(sprites_dir="Apps/Res/Sprites", ini_path="re/data/syspak/Occupant.ini",
                    occ_dir="Apps/Res/Occupant"):
    """-> {(group, instance): (attribInstance, name)} for every sprite record a table names.

    The authoritative reverse map: which named occupant a given sprite record belongs to, with no
    assumption about the instance's internal bit layout.
    """
    names = art_names(occ_dir, ini_path, sprites_dir)
    owner = {}
    for key, refs in frame_tables(sprites_dir).items():
        nm = names.get(key, "")
        for ref in refs:
            owner.setdefault(ref, (key[1], nm))
    return owner


def object_index(target, owner=None):
    """Group every record by (file, group, objectId). -> list of row dicts.

    This is the index that did not exist: it answers "what are all the records for this thing",
    which is what you need before editing art, since one object has up to 16 pixel records.
    Pass `owner` (from `art_owner_index()`) to attach the shipped building name.
    """
    rows = []
    for path in qfs.archives(target):
        with open(path, "rb") as fh:
            d = fh.read()
        slots = ixf_parse.read_index_slots(d)
        objs = {}
        for i in _live(slots):
            s = slots[i]
            oid, zoom, rot = split_instance(s[1])
            e = objs.setdefault((s[0], oid), {"pixel": [], "anchor": [], "dims": {}})
            if s[2] == qfs.TYPE_ANCHOR:
                e["anchor"].append(i)
                continue
            e["pixel"].append(i)
            try:
                kind, block, inf = qfs.decode_record(d[s[3]:s[3] + s[4]])
                if kind == "qfs" and inf["format"] == 1:
                    m = sr.parse_span_block(block)
                    e["dims"][(zoom, rot)] = (m["w"], m["h"])
            except (qfs.QfsError, struct.error):
                pass
        for (group, oid), e in sorted(objs.items()):
            dims = e["dims"]
            widths = sorted({w for w, _ in dims.values()})
            name, occ = "", ""
            if owner:
                for i in e["pixel"]:
                    hit = owner.get((slots[i][0], slots[i][1]))
                    if hit:
                        occ, name = "%d" % hit[0], hit[1]
                        break
            rows.append({
                "file": os.path.basename(path), "group": "0x%08X" % group,
                "object": "0x%04X" % oid, "name": name, "occupant": occ,
                "pixel_records": len(e["pixel"]),
                "anchor_records": len(e["anchor"]),
                "zooms": "".join(str(z) for z in sorted({z for z, _ in dims})),
                "rotations": "".join(str(r) for r in sorted({r for _, r in dims})),
                "widths": ",".join(str(w) for w in widths),
                "max_h": max((h for _, h in dims.values()), default=0),
                "first_slot": min(e["pixel"]) if e["pixel"] else "",
            })
    return rows


# --- link 7: name -> sprite records, via the game's OWN mapping table -------------------
#
# The authoritative building -> art mapping is NOT arithmetic on the instance. It is a shipped
# table, and the code does no bit-packing at all: SIMSPR `FUN_100155bf` @0x100155bf builds the
# key {type 0x6301, group 0x6400, instance = occupantId} and hands it to the resource manager
# with no shift or or anywhere on the path.
#
#     Occupant.ini [OccupantKeys]      occupantId -> human name
#     CSATTRIB.IXF  group 0x6400       instance = occupantId -> a table of (group, instance)
#                                      sprite references, one per (zoom, rotation, frame) slot
#     Apps\Res\Sprites\*.DAT           those (group, instance) pairs -> pixels
#
# [CONFIRMED] on the Coal Power Plant: `Occupant.ini:158` gives occupant 207 = 0x0000_00CF =
# "Coal Power Plant"; CSATTRIB.IXF instance 0xCF is a `BIN\r` v1 record with ZoomCount 5,
# RotCount 4, Frames 20, whose frames 0..15 reference group 0x0000000B instances
# 0x00CF0000..0x00CF000F and whose frames 16..19 RE-REFERENCE 0x00CF000C..F with trailer byte
# a = 2 (the zoom-4 set reusing zoom-3 art). Independently, the colour-index probe identified the
# on-screen building as exactly 0x00CF000C -- two unrelated methods agreeing.
#
# So: to retexture "the coal power plant", read its frame table and edit the DISTINCT records it
# names. Do not compute them.

CSATTRIB_GROUP = 0x6400
CSATTRIB_MAGIC = b"BIN\r"
FRAME_ENTRY = 15


def occupant_names(ini_path="re/data/syspak/Occupant.ini"):
    """Parse `[OccupantKeys]` -> {occupantId: name}. Lines look like

        0x207EDC0E,0x0000057E,0x000000CF=(207) Coal Power Plant
    """
    names, in_section = {}, False
    with open(ini_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("["):
                in_section = line.lower().startswith("[occupantkeys")
                continue
            if not in_section or "=" not in line or line.startswith(";"):
                continue
            key, _, val = line.partition("=")
            parts = key.split(",")
            if len(parts) != 3:
                continue
            try:
                inst = int(parts[2], 16)
            except ValueError:
                continue
            val = val.strip()
            if val.startswith("("):
                _, _, val = val.partition(")")
            names[inst] = val.strip()
    return names


TKB1_MAGIC = b"TKB1"
PROP_NAME = 0x64            # type 7, the authored building name
PROP_FOOTPRINT = 0x66       # type 3 x3, tiles
PROP_SPRITEDEF = 0x67       # type 8, {type, group, instance} -> the CSAttrib record

# Property payload encoding [CONFIRMED by reading OccupantAttribs.IXF instance 0xCF byte by byte]:
#   [u32 propId][u16 type][u16 count][payload]
#     type 7 = string : u32 length, then `length` chars
#     type 3 = u32    : `count` dwords
#     type 8 = GZ key : `count` x 3 dwords (type, group, instance)


def parse_tkb1(buf):
    """Parse one TKB1 occupant record -> {propId: value}. Unknown types stop the walk."""
    if buf[:4] != TKB1_MAGIC:
        raise SpritePatchError("not a TKB1 record")
    out, o, n = {}, 4, len(buf)
    while o + 8 <= n:
        prop, = struct.unpack_from("<I", buf, o)
        ptype, count = struct.unpack_from("<HH", buf, o + 4)
        o += 8
        if ptype == 7:
            if o + 4 > n:
                break
            ln, = struct.unpack_from("<I", buf, o)
            o += 4
            out[prop] = buf[o:o + ln].decode("latin-1")
            o += ln
        elif ptype == 3:
            vals = struct.unpack_from("<%dI" % count, buf, o)
            out[prop] = vals if count > 1 else vals[0]
            o += 4 * count
        elif ptype == 8:
            keys = [struct.unpack_from("<3I", buf, o + 12 * i) for i in range(count)]
            out[prop] = keys if count > 1 else keys[0]
            o += 12 * count
        else:
            break                      # unknown type: stop rather than mis-stride
    return out


def _containers(*roots):
    """Every .IXF-magic container under the given files/dirs, recursively."""
    for root in roots:
        if os.path.isfile(root):
            yield root
            continue
        for base, _, names in os.walk(root):
            for n in sorted(names):
                yield os.path.join(base, n)


def occupant_attribs(*roots):
    """Walk containers for TKB1 records -> ({(group, instance): name}, n_records).

    Keyed on property 0x67's FULL key (group, instance), not on the record's own instance and not
    on the instance alone. Both shortcuts break: the building/flora SET archives
    (`BuildingSets/*/BST_*.dat`, `FloraSets/*/Flora_*.dat`) carry their own attrib tables at their
    own group ids, so instance numbers collide across sets.
    """
    names, seen = {}, 0
    for path in _containers(*roots):
        try:
            recs, d = ixf_parse.parse(path)
        except (ixf_parse.IxfError, struct.error, OSError):
            continue
        for r in recs:
            b = d[r["offset"]:r["offset"] + r["size"]]
            if b[:4] != TKB1_MAGIC:
                continue
            seen += 1
            try:
                props = parse_tkb1(b)
            except (SpritePatchError, struct.error):
                continue
            name = props.get(PROP_NAME)
            key = props.get(PROP_SPRITEDEF)
            if not name or not key:
                continue
            names.setdefault((key[1], key[2]), name)     # key = (type, group, instance)
    return names, seen


def frame_tables(*roots):
    """Every `BIN\\r` attrib record under the given roots -> {(group, instance): [(g, i), ...]}.

    Detects by MAGIC, not by filename or group, so it picks up `CSATTRIB*.IXF` (group 0x6400) and
    the tables embedded in the building/flora set archives alike.
    """
    out = {}
    for path in _containers(*roots):
        try:
            recs, d = ixf_parse.parse(path)
        except (ixf_parse.IxfError, struct.error, OSError):
            continue
        for r in recs:
            p = d[r["offset"]:r["offset"] + r["size"]]
            if len(p) < 0x18 or p[:4] != CSATTRIB_MAGIC:
                continue
            n, = struct.unpack_from("<H", p, 0x16)
            seen, refs = set(), []
            for i in range(n):
                o = 0x18 + i * FRAME_ENTRY
                if o + FRAME_ENTRY > len(p):
                    break
                _, g, inst, _flag, _b, _c = struct.unpack_from("<HIIBHH", p, o)
                if (g, inst) not in seen:
                    seen.add((g, inst))
                    refs.append((g, inst))
            out[(r["group"], r["instance"])] = refs
    return out


def csattrib_frames(path):
    """Parse a CSAttrib container -> {occupantId: [(group, instance), ...]} (distinct, in order).

    Header: `BIN\\r`, u32 version, u32 SprInstCLSID, u8 ZoomCount, u8 RotCount, u8 ZoomSetCount,
    u32 LayerFlags @0x10, u16 Frames @0x16, then `Frames` x 15-byte entries
    {u16 frameIndex, u32 group, u32 instance, u8 flag, u16, u16}.
    """
    recs, d = ixf_parse.parse(path)
    out = {}
    for r in recs:
        if r["group"] != CSATTRIB_GROUP:
            continue
        p = d[r["offset"]:r["offset"] + r["size"]]
        if len(p) < 0x18 or p[:4] != CSATTRIB_MAGIC:
            continue
        n, = struct.unpack_from("<H", p, 0x16)
        seen, refs = set(), []
        for i in range(n):
            o = 0x18 + i * FRAME_ENTRY
            if o + FRAME_ENTRY > len(p):
                break
            _, g, inst, _flag, _b, _c = struct.unpack_from("<HIIBHH", p, o)
            if (g, inst) not in seen:
                seen.add((g, inst))
                refs.append((g, inst))
        out[r["instance"]] = refs
    return out


def find_art(name_query, sprites_dir="Apps/Res/Sprites",
             ini_path="re/data/syspak/Occupant.ini", occ_dir="Apps/Res/Occupant"):
    """Resolve a building name to the sprite records that draw it. -> list of dicts."""
    names = art_names(occ_dir, ini_path, sprites_dir)
    q = name_query.lower()
    matches = {key: nm for key, nm in names.items() if q in nm.lower()}
    if not matches:
        return []
    frames = frame_tables(sprites_dir)
    # which container holds which group
    where = {}
    for path in qfs.archives(sprites_dir):
        with open(path, "rb") as fh:
            d = fh.read()
        try:
            for s in ixf_parse.read_index_slots(d):
                if s[:3] != (0, 0, 0):
                    where.setdefault(s[0], os.path.basename(path))
        except struct.error:
            pass
    rows = []
    for key, nm in sorted(matches.items()):
        refs = frames.get(key)
        rows.append({"attrib": "0x%08X:0x%08X" % key, "id": key[1], "name": nm,
                     "records": refs if refs else [],
                     "container": where.get(refs[0][0]) if refs else None})
    return rows


def info(path):
    with open(path, "rb") as fh:
        d = fh.read()
    slots = ixf_parse.read_index_slots(d)
    live = _live(slots)
    print("%s: %d bytes, %d slots, %d live" % (path, len(d), len(slots), len(live)))
    ok, detail = roundtrip(path)
    print("  identity repack: %s (%s)" % ("OK" if ok else "FAIL", detail))
    fmts = {}
    for i in live:
        s = slots[i]
        try:
            _, _, inf = qfs.decode_record(d[s[3]:s[3] + s[4]])
            fmts[inf["format"]] = fmts.get(inf["format"], 0) + 1
        except (qfs.QfsError, struct.error):
            fmts["err"] = fmts.get("err", 0) + 1
    print("  formats: %s" % fmts)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    target = argv[1]
    if "--selftest" in argv:
        files = []
        if os.path.isdir(target):
            for root, _, names in os.walk(target):
                files += [os.path.join(root, x) for x in sorted(names)]
        else:
            files = [target]
        ok = bad = skip = 0
        for f in files:
            res, detail = roundtrip(f)
            if res is None:
                skip += 1
            elif res:
                ok += 1
            else:
                bad += 1
                print("FAIL %s: %s" % (f, detail))
        print("identity repack: %d/%d containers byte-identical (%d non-container skipped)"
              % (ok, ok + bad, skip))
        return 0 if bad == 0 else 1
    if "--find-art" in argv:
        q = argv[argv.index("--find-art") + 1]
        rows = find_art(q, target if os.path.isdir(target) else "Apps/Res/Sprites")
        if not rows:
            print("no occupant name contains %r" % q)
            return 1
        for r in rows:
            print("%s  (attrib %s)  container %s"
                  % (r["name"], r["attrib"], r["container"]))
            if not r["records"]:
                print("    no CSAttrib frame table found for this occupant")
                continue
            print("    %d distinct sprite record(s) draw it:" % len(r["records"]))
            for g, inst in r["records"]:
                print("      group 0x%08X  instance 0x%08X" % (g, inst))
        return 0
    if "--objects" in argv:
        owner = None
        if "--no-names" not in argv:
            try:
                owner = art_owner_index(target if os.path.isdir(target) else "Apps/Res/Sprites")
            except OSError:
                owner = None
        rows = object_index(target, owner)
        if "--csv" in argv:
            out = argv[argv.index("--csv") + 1]
            with open(out, "w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
            print("%d objects -> %s" % (len(rows), out))
        only = argv[argv.index("--object") + 1].lower() if "--object" in argv else None
        shown = 0
        for r in rows:
            if only and r["object"].lower() != only:
                continue
            print("  %s %s obj %s  %-28s %d pixel + %d anchor  widths %s  first slot %s"
                  % (r["file"], r["group"], r["object"], r["name"] or "(unnamed)",
                     r["pixel_records"], r["anchor_records"], r["widths"], r["first_slot"]))
            shown += 1
            if shown >= 40 and not only:
                print("  ... (%d objects total; use --csv for all)" % len(rows))
                break
        if not shown:
            print("no object matched %s" % only)
        return 0
    if "--index-probe" in argv:
        # target is a comma-separated list of containers
        paths = [x for x in target.split(",") if x]
        out_dir = argv[argv.index("--out-dir") + 1]
        csv_path = argv[argv.index("--csv") + 1]
        n, _ = build_index_probe(paths, out_dir, csv_path)
        print("probe built: %d records given unique colours across %d container(s)"
              % (n, len(paths)))
        print("  containers -> %s" % out_dir)
        print("  colour map -> %s" % csv_path)
        return 0
    if "--decode-shot" in argv:
        csv_path = argv[argv.index("--csv") + 1]
        if "--at" in argv:
            x, y = (int(v) for v in argv[argv.index("--at") + 1].split(","))
            v, row, rgb = decode_shot(target, csv_path, at=(x, y))
            print("pixel (%d,%d) = RGB%s -> 0x%04X" % (x, y, rgb, v))
            print("  %s" % (row if row else "no record carries that colour"))
            return 0
        box = None
        if "--box" in argv:
            box = tuple(int(v) for v in argv[argv.index("--box") + 1].split(","))
        hits = decode_shot(target, csv_path, box=box)
        print("%d probed record(s) visible:" % len(hits))
        for n, r in hits:
            print("  %7d px  %s slot %-6s %s:%s  %sx%s"
                  % (n, r["file"], r["slot"], r["group"], r["instance"], r["w"], r["h"]))
        return 0
    if "--pngtest" in argv:
        ok, bad, skipped = png_selftest(target)
        print("PNG export->import: %d/%d records byte-identical (%d non-sprite skipped)"
              % (ok, ok + bad, skipped))
        return 0 if bad == 0 else 1
    if "--info" in argv:
        info(target)
        return 0
    if "--export" in argv:
        slot = int(argv[argv.index("--export") + 1], 0)
        out = argv[argv.index("--png") + 1]
        with open(target, "rb") as fh:
            d = fh.read()
        s = ixf_parse.read_index_slots(d)[slot]
        w, h = export_png(d[s[3]:s[3] + s[4]], out)
        print("slot %d (0x%08x:0x%08x) -> %s  %dx%d" % (slot, s[0], s[1], out, w, h))
        print("edit it, keep the size at %dx%d, then --import-png %d=%s" % (w, h, slot, out))
        return 0
    if "--import-png" in argv:
        specs = argv[argv.index("--import-png") + 1]
        out = argv[argv.index("--out") + 1]
        thr = 128
        if "--alpha-threshold" in argv:
            thr = int(argv[argv.index("--alpha-threshold") + 1], 0)
        with open(target, "rb") as fh:
            d = fh.read()
        slots = ixf_parse.read_index_slots(d)
        reps, total_nudged = {}, 0
        for spec in specs.split(","):
            slot_s, png = spec.split("=", 1)
            slot = int(slot_s, 0)
            s = slots[slot]
            pay, nudged = replace_from_png(d[s[3]:s[3] + s[4]], png, thr)
            reps[slot] = pay
            total_nudged += nudged
            print("slot %d <- %s  (payload %d -> %d bytes)"
                  % (slot, png, s[4], len(pay)))
        blob = repack(d, reps)
        with open(out, "wb") as fh:
            fh.write(blob)
        if total_nudged:
            print("NOTE: %d opaque pixel(s) quantized onto the colour key and were moved one "
                  "step in blue, so they draw instead of vanishing." % total_nudged)
        print("wrote %s (%d bytes, %d record(s) replaced)" % (out, len(blob), len(reps)))
        return 0
    if "--recolor" in argv:
        colour = int(argv[argv.index("--recolor") + 1], 16)
        out = argv[argv.index("--out") + 1]
        def prog(n, p, s):
            sys.stderr.write("\r  %d records, %d patched, %d skipped" % (n, p, s))
            sys.stderr.flush()
        n, s, blob = recolor_container(target, out, colour, prog)
        sys.stderr.write("\n")
        print("patched %d, skipped %d -> %s (%d bytes)" % (n, s, out, len(blob)))
        return 0
    info(target)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
