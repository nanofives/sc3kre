r"""netpack_lotcolour.py - task stylepal (2026-11-24): style copies' lot ground follows the host style.

Owner picks (2026-11-24, verify/stylepal/RESULTS.md): European and Asian copies in a North American city read as
another neighbourhood, mostly because of their lot ground: darker, duller lawn and garden-plot soil (the yard lots
3032 / 3034 / 3041 / 3042 above all). So, at package build time, on the copies' pixels only:

  "lot_colour": "lawn_soil"  (option c, European / Asian entries)
      host = the North American (stock) art of the SAME id. Lawn pixels of the copy shifted by host lawn mean - copy
      lawn mean (CIELAB, texture kept), soil pixels lifted by the same L, then soil turned into lawn with strength
      s = (copy soil share - host soil share) / copy soil share, clamped 0..1: where the host has plots too, plots stay.
  "lot_colour": "lawn"       (option a, the "00000000" North American entry)
      host = the art of the same id in the manifest's other sets (pixels of all of them pooled). Lawn shifted as above,
      soil by the same L, no soil-to-lawn. The North American copies get their OWN frame tables (group NA_CS_GROUP,
      instance = copy id) and pixels (group NA_PIX_GROUP, Res\Sprites\<group>_netpack_set.DAT), and prop 0x67 of each
      copy points at its table. Stock tables and pixels are never written.

Per id, not per class (owner pick): the means come from the building's own zoom 3 frames (table entries 12..15),
lot diamond only. A building whose host or copy shows too little lawn (MIN_LAWN pixels) gets no lawn shift. Buildings
stay as they are: only pixels inside the lot diamond with a lawn or soil colour change.

Geometry (BUILDING_ART.md 2-3): the (L, T) anchor pixel is the lot's left ground vertex, W = w / n, ground-plane
u = x/W - 2(y-T)/W, v = x/W + 2(y-T)/W, lot = 0 <= u, v <= n. Square lots only; others keep their art (reported).
Colour classes (Lab, D65): lawn = hue 95..200, chroma > 12; brown (soil share) = hue 35..95, chroma > 10; the soil
that is recoloured = hue 62..95, chroma > 14, L < 62 (measured: soil hue 65-93, roofs 37-55, light paths L > 70,
stone wall bases chroma 10-14).

Deterministic: elementwise numpy only (no matrix products: BLAS kernels sum in a CPU-dependent order), fixed record
order, QFS quick compression.
"""
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import qfs            # noqa: E402
import qfs_encode     # noqa: E402
import sprite_encode  # noqa: E402
import sprite_patch   # noqa: E402

MODES = ("lawn", "lawn_soil")
NA_CS_GROUP = 0x2627D60F       # North American copies' frame tables (CSAttrib_Korea.IXF)
NA_PIX_GROUP = 0x2627D60E      # their pixel + anchor records (Res\Sprites\2627D60E_netpack_set.DAT)
MIN_LAWN = 100                 # lawn pixels over the 4 zoom 3 frames, below which no lawn shift is made
ZOOM3 = range(12, 16)

_M = ((0.4124564, 0.3575761, 0.1804375), (0.2126729, 0.7151522, 0.0721750), (0.0193339, 0.1191920, 0.9503041))
_MI = ((3.2404542, -1.5371385, -0.4985314), (-0.9692660, 1.8760108, 0.0415560), (0.0556434, -0.2040259, 1.0572252))
_WP = (0.95047, 1.0, 1.08883)


def _mul3(m, c):
    return [m[r][0] * c[..., 0] + m[r][1] * c[..., 1] + m[r][2] * c[..., 2] for r in range(3)]


def srgb_to_lab(rgb):
    c = rgb.astype(np.float64) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    x, y, z = (v / w for v, w in zip(_mul3(_M, c), _WP))
    f = [np.where(t > 216 / 24389, np.cbrt(t), (24389 / 27 * t + 16) / 116) for t in (x, y, z)]
    return np.stack([116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])], -1)


def lab_to_srgb(lab):
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    fy = (L + 16) / 116
    fx = fy + a / 500
    fz = fy - b / 200
    e, k = 216 / 24389, 24389 / 27
    xr = np.where(fx ** 3 > e, fx ** 3, (116 * fx - 16) / k)
    yr = np.where(L > k * e, fy ** 3, L / k)
    zr = np.where(fz ** 3 > e, fz ** 3, (116 * fz - 16) / k)
    xyz = np.stack([xr * _WP[0], yr, zr * _WP[2]], -1)
    c = np.clip(np.stack(_mul3(_MI, xyz), -1), 0, 1)
    c = np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1 / 2.4) - 0.055)
    return np.clip(np.round(c * 255), 0, 255).astype(np.uint8)


def _hc(lab):
    H = (np.degrees(np.arctan2(lab[..., 2], lab[..., 1])) + 360) % 360
    return H, np.hypot(lab[..., 1], lab[..., 2])


def decode(payload):
    """-> (rgb uint8 h x w x 3, alpha 0/1, meta) or None for a record that is not a format-1 QFS sprite."""
    kind, block, info = qfs.decode_record(payload)
    if kind != "qfs" or info["format"] != 1:
        return None
    m = sprite_encode.sr.parse_span_block(block)    # sprite_encode.block_to_surface, row runs copied with numpy
    s = np.full((m["h"], m["w"]), m["key"], np.uint16)
    for y, (off, x, n, _top) in enumerate(m["rows"]):
        if n:
            s[y, x:x + n] = np.frombuffer(block, "<u2", n, m["data_start"] + off * 2)
    alpha = (s != m["key"]).astype(np.uint8)
    rgb = np.dstack([((s >> 11) & 31) << 3, ((s >> 5) & 63) << 2, (s & 31) << 3]).astype(np.uint8)
    return rgb, alpha, (info, m)


def lot_mask(alpha, anchor, n):
    h, w = alpha.shape
    W = w / n
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float64)
    x = xs + 0.5 - anchor[0]
    y = ys + 0.5 - anchor[1]
    u = x / W - 2 * y / W
    v = x / W + 2 * y / W
    return (alpha > 0) & (u >= 0) & (u <= n) & (v >= 0) & (v <= n)


_LOT = {}


def lot_pixels(frames, n):
    """frames = [(pixel payload, anchor payload)] -> Lab pixels inside the lot diamond, pooled. Memoized per frame:
    the same stock and set frames are measured for several entries."""
    out = []
    for pix, anc in frames:
        k = (pix, anc, n)
        if k not in _LOT:
            d = decode(pix)
            if d is None:
                _LOT[k] = np.zeros((0, 3))
            else:
                rgb, alpha, _ = d
                L, T = struct.unpack("<4h", anc)[:2]
                _LOT[k] = srgb_to_lab(rgb[lot_mask(alpha, (L, T), n)])
        out.append(_LOT[k])
    return np.concatenate(out) if out else np.zeros((0, 3))


def stats(lab):
    """-> {lawn mean, lawn count, brown share, brown mean}"""
    if not len(lab):
        return {"n": 0, "lawn_n": 0, "lawn": None, "brown": 0.0, "brown_mean": None}
    H, C = _hc(lab)
    g = (H >= 95) & (H < 200) & (C > 12)
    br = (H >= 35) & (H < 95) & (C > 10)
    return {"n": int(len(lab)), "lawn_n": int(g.sum()), "lawn": lab[g].mean(0) if g.any() else None,
            "brown": float(br.mean()), "brown_mean": lab[br].mean(0) if br.any() else None}


def params(copy, host, mode):
    """-> per-building transform parameters, or None when nothing would change."""
    p = {"dG": np.zeros(3), "s": 0.0, "hostG": None, "soil": None}
    if copy["lawn_n"] >= MIN_LAWN and host["lawn_n"] >= MIN_LAWN:
        p["dG"] = host["lawn"] - copy["lawn"]
    if mode == "lawn_soil" and host["lawn_n"] >= MIN_LAWN and copy["brown"] > 0 and copy["brown_mean"] is not None:
        p["s"] = float(np.clip((copy["brown"] - host["brown"]) / copy["brown"], 0, 1))
        p["hostG"], p["soil"] = host["lawn"], copy["brown_mean"]
    if not p["dG"].any() and p["s"] == 0:
        return None
    return p


def recolour(payload, anchor_payload, n, p):
    """-> the pixel record with the lot ground recoloured (same header, new QFS stream)."""
    d = decode(payload)
    if d is None:
        return payload
    rgb, alpha, (info, m) = d
    L0, T0 = struct.unpack("<4h", anchor_payload)[:2]
    lot = lot_mask(alpha, (L0, T0), n)
    lab = np.zeros(rgb.shape, np.float64)
    lab[lot] = srgb_to_lab(rgb[lot])                # Lab of the lot pixels only (the rest is never read)
    H, C = _hc(lab)
    green = lot & (H >= 95) & (H < 200) & (C > 12)
    soil = lot & (H >= 62) & (H < 95) & (C > 14) & (lab[..., 0] < 62)
    if not green.any() and not soil.any():
        return payload
    out = lab.copy()
    out[green] += p["dG"]
    out[soil, 0] += p["dG"][0]
    if p["s"] > 0 and soil.any():
        S = lab[soil]
        tgt = np.stack([out[soil, 0] - p["soil"][0] + p["hostG"][0],
                        p["hostG"][1] + (S[:, 1] - p["soil"][1]) * 0.5,
                        p["hostG"][2] + (S[:, 2] - p["soil"][2]) * 0.5], -1)
        out[soil] = (1 - p["s"]) * out[soil] + p["s"] * tgt
    chg = green | soil
    res = rgb.copy()
    res[chg] = lab_to_srgb(out[chg])
    key = m["key"]
    v = ((res[..., 0].astype(np.uint16) >> 3) << 11) | ((res[..., 1].astype(np.uint16) >> 2) << 5) | \
        (res[..., 2].astype(np.uint16) >> 3)
    v[(v == key) & (alpha > 0)] ^= 1
    v[alpha == 0] = key
    nb = sprite_encode.encode([int(x) for x in v.ravel()], m["w"], m["h"], key, m["b"], m["a"])
    return sprite_patch.pack_payload(info, qfs_encode.compress_stream(nb, quick=1))


def table_refs(tab):
    """-> [(entry offset, group, instance)] of a BIN\\r frame table (15-byte entries from +0x18)."""
    return [(o,) + struct.unpack_from("<II", tab, o + 2) for o in range(0x18, len(tab) - 14 + 1, 15)]


def zoom3_frames(tab, pix):
    """pix = {(g, i): (pixel payload, anchor payload)} -> the zoom 3 frames of a 16-entry table, or None."""
    refs = table_refs(tab)
    if len(refs) < 16:
        return None
    out = []
    for k in ZOOM3:
        _, g, i = refs[k]
        if (g, i) not in pix:
            return None
        out.append(pix[(g, i)])
    return out


def retarget(tab, keymap):
    """frame table copy with every entry's (group, instance) mapped through keymap."""
    b = bytearray(tab)
    for o, g, i in table_refs(tab):
        if (g, i) in keymap:
            struct.pack_into("<II", b, o + 2, *keymap[(g, i)])
    return bytes(b)
