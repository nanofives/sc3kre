#!/usr/bin/env python3
r"""animrot strip: per view, the FRAMES frames of one shots.py group side by side (crop box), rows = views 0-3.

  py -3.12 strip.py <prefix> <group> <zoom> <frames> <x0,y0,x1,y1> <out.png> [title]
"""
import pathlib
import sys

from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent


def main(a):
    pre, g, z, nf = a[0], a[1], int(a[2]), int(a[3])
    box = tuple(int(v) for v in a[4].split(","))
    out, title = a[5], (a[6] if len(a) > 6 else "")
    w, h = box[2] - box[0], box[3] - box[1]
    sheet = Image.new("RGB", (nf * (w + 4), 4 * (h + 4)), (40, 40, 40))
    for v in range(4):
        for f in range(nf):
            im = Image.open(HERE / "fd" / ("%s_%s_z%d_v%d_f%d.png" % (pre, g, z, v, f))).convert("RGB").crop(box)
            d = ImageDraw.Draw(im)
            d.rectangle((0, 0, 200, 14), fill=(0, 0, 0))
            d.text((3, 1), "view %d frame %d %s" % (v, f, title), fill=(255, 255, 0))
            sheet.paste(im, (f * (w + 4), v * (h + 4)))
    sc = float(__import__("os").environ.get("SCALE", "1"))
    if sc != 1:
        sheet = sheet.resize((int(sheet.width * sc), int(sheet.height * sc)), Image.LANCZOS)
    sheet.save(out)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
