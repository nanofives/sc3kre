"""slopeend_sheet.py -- owner contact sheet of the slopeend lab: before (mod off) / after (mod on) frame dumps taken by
slopeend_shots.py at the same cameras, cropped to the city view (HUD and minimap cut off).
    py -3.12 slopeend_sheet.py <shots dir> <out.png> [--scale 0.5]
"""
import argparse
import os

from PIL import Image, ImageDraw

ROWS = [("W_z4", "zoom 4, west edge of the 1-unit plateau: stub (both ends), road up and stopping, road down"),
        ("E_z4", "zoom 4, east edge: road up and stopping, road down"),
        ("N_z4", "zoom 4, north edge (slope along the other axis)"),
        ("S_z4", "zoom 4, south edge"),
        ("P2_z4", "zoom 4, the 2-unit (steep) plateau"),
        ("P1_z3_r0", "zoom 3, view 0"), ("P1_z3_r1", "zoom 3, view 1"),
        ("P1_z3_r2", "zoom 3, view 2"), ("P1_z3_r3", "zoom 3, view 3"),
        ("P2_z3", "zoom 3, steep plateau")]
CROP = (0, 20, 700, 540)          # 800x600 dump: drop the FPS line, the right toolbar and the bottom bar


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("shots")
    ap.add_argument("out")
    ap.add_argument("--scale", type=float, default=0.5)
    a = ap.parse_args()
    w, h = int((CROP[2] - CROP[0]) * a.scale), int((CROP[3] - CROP[1]) * a.scale)
    rows = [r for r in ROWS if os.path.isfile(os.path.join(a.shots, "before_%s.png" % r[0]))]
    lab = 22
    sheet = Image.new("RGB", (2 * w + 30, 40 + len(rows) * (h + lab + 8)), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    d.text((10, 10), "BEFORE (stock: square cut on the slope)", fill=(255, 255, 255))
    d.text((w + 20, 10), "AFTER (road_slope_ends + sc3netmod SLE)", fill=(255, 220, 120))
    y = 40
    for name, text in rows:
        d.text((10, y), text, fill=(200, 200, 200))
        for k, pre in enumerate(("before", "after")):
            f = os.path.join(a.shots, "%s_%s.png" % (pre, name))
            if os.path.isfile(f):
                im = Image.open(f).convert("RGB").crop(CROP).resize((w, h), Image.LANCZOS)
                sheet.paste(im, (10 + k * (w + 10), y + lab))
        y += h + lab + 8
    sheet.save(a.out)
    print("wrote", a.out, sheet.size)


if __name__ == "__main__":
    main()
