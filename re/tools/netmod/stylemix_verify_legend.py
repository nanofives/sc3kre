r"""Legend sheet for task stylemix: the base, European (e523f3fb) and Asian (6523f3d5) art of the same building ids,
closest zoom, one rotation, from the frame tables the game uses (exemplar prop 0x67). Game art: keep it out of any
public repository.  py -3.12 stylemix_verify_legend.py <tree> <out.png> <rot 0-3> <id> [<id> ...]"""
import sys, os, struct, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from netmod import netpack as np
import newpiece as NP
import sprite_patch
from PIL import Image, ImageDraw
tree, out, rot, ids = sys.argv[1], sys.argv[2], int(sys.argv[3]), [int(x) for x in sys.argv[4:]]
st = np.Stock(tree)
bld = {}
for n in st.listdir("Apps/Res/Occupant"):
    if n.lower().endswith(".ixf"):
        for g, i, t, p in st.records("Apps/Res/Occupant/" + n):
            if t == 0x207EDC0E and g == 0x57E: bld.setdefault(i, p)
cs = {}
for n in st.listdir("Apps/Res/Sprites"):
    if n.lower().startswith("csattrib"):
        for g, i, t, p in st.records("Apps/Res/Sprites/" + n): cs.setdefault((t, g, i), p)
setrec = {}
for s in ("e523f3fb", "6523f3d5"):
    d = "Apps/Res/Sprites/BuildingSets/" + s
    for n in st.listdir(d):
        for g, i, t, p in st.records(d + "/" + n):
            setrec.setdefault(s, {})[(t, g, i)] = p
pix = {}
for n in st.listdir("Apps/Res/Sprites"):
    if n.upper().endswith(".DAT"):
        for g, i, t, p in st.records("Apps/Res/Sprites/" + n):
            if t == 0: pix.setdefault((g, i), p)
for s in setrec.values():
    for (t, g, i), p in s.items():
        if t == 0: pix.setdefault((g, i), p)
def art(ex, tables):
    k = tuple(np.tkb1_key(ex, 0x67))
    tab = tables.get(k) or cs.get(k)
    n, fr = NP.cs_frames(tab) if tab[:4] == b"BIN\r" and len(tab) == 0x18 + 15 * struct.unpack_from("<H", tab, 0x16)[0] else (0, [])
    if not fr:
        return None
    _, _, g, i, _ = fr[16 + rot] if len(fr) >= 20 else fr[-1]
    f = os.path.join(tempfile.gettempdir(), "sm_leg.png")
    sprite_patch.export_png(pix[(g, i)], f)
    return Image.open(f).convert("RGBA")
rows = []
for bid in ids:
    cells = [("base %d" % bid, art(bld[bid], {}))]
    for s, off, lab in (("e523f3fb", 400000, "Euro"), ("6523f3d5", 1500000, "Asian")):
        ex = setrec[s].get((0x207EDC0E, 0x57E, bid))
        cells.append(("%s %d" % (lab, bid + off), art(ex, setrec[s]) if ex else None))
    rows.append(cells)
W = max((im.width for r in rows for _, im in r if im), default=100) + 10
H = [max((im.height for _, im in r if im), default=40) + 18 for r in rows]
sheet = Image.new("RGBA", (3 * W, sum(H)), (40, 40, 40, 255))
d = ImageDraw.Draw(sheet); y = 0
for r, h in zip(rows, H):
    for c, (lab, im) in enumerate(r):
        d.text((c * W + 4, y + 2), lab, fill=(255, 255, 0, 255))
        if im: sheet.alpha_composite(im, (c * W + 5, y + 16))
        else: d.text((c * W + 4, y + 20), "(set has none)", fill=(200, 200, 200, 255))
    y += h
sheet.save(out); print("wrote", out, sheet.size)
