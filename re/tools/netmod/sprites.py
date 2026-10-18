"""sprites.py -- piece art: CSATTRIB frame tables -> sprite records -> PNG.

Chain, all on disk (`formats/SPRITE_MODDING.md` for the building case):
  exemplar prop 0x67 {0x6300, 0x6400, n}
  -> `Apps\\Res\\Sprites\\CSATTRIB*.IXF` record (type 0x6300, group 0x6400, instance n), `BIN\\r`
     v1: +0x0c u8 ZoomCount, +0x0d u8 RotCount, +0x10 u32 LayerFlags (raw), +0x16 u16 Frames,
     then Frames x 15 bytes {u16 frameIndex, u32 group, u32 instance, u8 flag, u16, u16}
  -> the (group, instance) type-0 pixel record in a `Sprites\\*.DAT` container.

[UNCERTAIN] that the RUNTIME takes this same route for network pieces: the piece -> sprite lookup
was never traced live (NETMOD capability map 1). The join is exact as data (every network
exemplar's 0x67 names a CSATTRIB record, and road 29's frames are the Roads.DAT records the
2026-08-19 recolour test turned red), but no breakpoint has watched SIMSPR read it for a piece.
"""
import os
import struct
import sys

from . import paths

sys.path.insert(0, paths.TOOLS)
import ixf_parse  # noqa: E402
import qfs  # noqa: E402
import sprite_patch as _sp  # noqa: E402
import sprite_render as _sr  # noqa: E402

CS_GROUP = 0x6400
FRAME = 15
TYPE_PIXEL, TYPE_ANCHOR = 0, 1
# The containers network art lives in (measured over all 420 Set ids): Roads, Roads_2,
# Utilities, Other. Scanning every Sprites\*.DAT would take ~10x longer for no extra hits.
NET_CONTAINERS = ("00000005_Roads.DAT", "5544F8BD_Roads_2.DAT", "0000000B_Utilities.DAT",
                  "00000008_Other.DAT")


def csattrib(game):
    """-> {(type, instance): {"file", "hdr", "frames": [(idx, g, i, flag, u1, u2)]}} for
    group 0x6400 across every CSATTRIB*.IXF (first file wins, as listed sorted)."""
    out = {}
    for f in sorted(os.listdir(game.sprites)):
        if not f.lower().startswith("csattrib") or not f.lower().endswith(".ixf"):
            continue
        recs, d = ixf_parse.parse(os.path.join(game.sprites, f))
        for r in recs:
            if r["group"] != CS_GROUP:
                continue
            p = d[r["offset"]:r["offset"] + r["size"]]
            if len(p) < 0x18 or p[:4] != b"BIN\r":
                continue
            ver, clsid = struct.unpack_from("<II", p, 4)
            zc, rc, b0e, b0f = p[0x0C], p[0x0D], p[0x0E], p[0x0F]
            layer, = struct.unpack_from("<I", p, 0x10)
            u14, n = struct.unpack_from("<HH", p, 0x14)
            frames = []
            for k in range(n):
                o = 0x18 + k * FRAME
                if o + FRAME > len(p):
                    break
                frames.append(struct.unpack_from("<HIIBHH", p, o))
            out.setdefault((r["type"], r["instance"]), {
                "file": f, "size": r["size"],
                "hdr": {"version": ver, "clsid": clsid, "zoom_count": zc, "rot_count": rc,
                        "b0e": b0e, "b0f": b0f, "layer_flags": layer, "u14": u14,
                        # artkit 2026-10-13: the reader's field order (SIMSPR 0x10001c90) puts AnimFrames at +0x10,
                        # RegRects at +0x11 and the u32 LayerFlags at +0x12; "layer_flags" above is the raw dword at
                        # +0x10 (kept for the selftest's layer count, its low byte). draw_flags & 0x80 = first pass.
                        "anim_frames": p[0x10], "reg_rects": p[0x11],
                        "draw_flags": struct.unpack_from("<I", p, 0x12)[0],
                        "frames": n},
                "frames": frames})
    return out


class Containers:
    """Index of the network sprite containers: (group, instance, type) -> (file, slot)."""

    def __init__(self, game, names=NET_CONTAINERS):
        self.game = game
        self.where = {}
        self.data = {}
        self.slots = {}
        for f in names:
            p = os.path.join(game.sprites, f)
            if not os.path.isfile(p):
                continue
            with open(p, "rb") as fh:
                d = fh.read()
            self.data[f] = d
            sl = ixf_parse.read_index_slots(d)
            self.slots[f] = sl
            for i, s in enumerate(sl):
                if s[3] == 0xFFFFFFFF or s[:3] == (0, 0, 0):
                    continue
                self.where.setdefault((s[0], s[1], s[2]), (f, i))
        self._dims = {}

    def find(self, group, inst, rtype=TYPE_PIXEL):
        return self.where.get((group, inst, rtype))

    def payload(self, f, slot):
        s = self.slots[f][slot]
        return self.data[f][s[3]:s[3] + s[4]]

    def dims(self, f, slot):
        k = (f, slot)
        if k not in self._dims:
            try:
                kind, block, inf = qfs.decode_record(self.payload(f, slot))
                if kind == "qfs" and inf["format"] == 1:
                    m = _sr.parse_span_block(block)
                    self._dims[k] = (m["w"], m["h"], inf["format"])
                else:
                    self._dims[k] = (None, None, inf.get("format") if isinstance(inf, dict)
                                     else None)
            except (qfs.QfsError, struct.error, KeyError):
                self._dims[k] = (None, None, None)
        return self._dims[k]

    def objects(self, f):
        """Distinct (group, instance >> 16) objects among type-0 records of one container."""
        out = {}
        for i, s in enumerate(self.slots.get(f, [])):
            if s[3] == 0xFFFFFFFF or s[:3] == (0, 0, 0) or s[2] != TYPE_PIXEL:
                continue
            out.setdefault((s[0], s[1] >> 16), []).append(i)
        return out

    def export_png(self, f, slot, path):
        return _sp.export_png(self.payload(f, slot), path)


def frame_rows(table, cont, with_dims=True):
    """CSATTRIB frames -> rows with container/slot/size."""
    rows = []
    for idx, g, inst, flag, u1, u2 in table["frames"]:
        hit = cont.find(g, inst)
        anc = cont.find(g, inst, TYPE_ANCHOR)
        row = {"frame": idx, "group": g, "instance": inst, "flag": flag, "u1": u1, "u2": u2,
               "container": hit[0] if hit else None, "slot": hit[1] if hit else None,
               "anchor_slot": anc[1] if anc else None}
        if hit and with_dims:
            w, h, fmt = cont.dims(*hit)
            row.update(w=w, h=h, format=fmt)
        rows.append(row)
    return rows
