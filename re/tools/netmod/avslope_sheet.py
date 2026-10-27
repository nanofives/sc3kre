"""avslope_sheet.py -- the owner sheet of task avslope: before / after frame dumps at the same cameras, side by side.
    py -3.12 avslope_sheet.py <frames dir> <out.png> name [name ...]     (frames <dir>/before_<name>.png, after_<name>.png)
"""
import os
import sys

from PIL import Image, ImageDraw


def main(argv):
    d, out, names = argv[1], argv[2], argv[3:]
    rows = []
    for n in names:
        b, a = os.path.join(d, "before_%s.png" % n), os.path.join(d, "after_%s.png" % n)
        if os.path.isfile(a):
            rows.append((n, Image.open(b).convert("RGB") if os.path.isfile(b) else None, Image.open(a).convert("RGB")))
    if not rows:
        return 1
    crop = (0, 20, 700, 540)                         # the view, clear of the FPS line and the right-hand HUD
    w, h = crop[2] - crop[0], crop[3] - crop[1]
    sheet = Image.new("RGB", (2 * w + 30, len(rows) * (h + 22) + 26), (24, 24, 24))
    dr = ImageDraw.Draw(sheet)
    dr.text((10, 6), "BEFORE (LAN build 2026-10-26b)", fill=(255, 255, 255))
    dr.text((w + 20, 6), "AFTER (avslope: sloped avenue / boulevard pieces)", fill=(255, 255, 255))
    for i, (n, b, a) in enumerate(rows):
        y = 26 + i * (h + 22)
        dr.text((10, y), n, fill=(255, 255, 255))
        if b is not None:
            sheet.paste(b.crop(crop), (10, y + 16))
        sheet.paste(a.crop(crop), (w + 20, y + 16))
    sheet.save(out)
    print("wrote", out, sheet.size)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
