#!/usr/bin/env python3
r"""animrot montage: 2 x 2 sheet of the four views of one shots.py group, game area only (HUD cropped), labelled.

  py -3.12 montage.py <prefix> <group> <zoom> <out.png> [title]
"""
import pathlib
import sys

from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent


def main(a):
    pre, g, z, out = a[0], a[1], int(a[2]), a[3]
    title = a[4] if len(a) > 4 else ""
    tiles = []
    for v in range(4):
        im = Image.open(HERE / "fd" / ("%s_%s_z%d_v%d.png" % (pre, g, z, v))).convert("RGB")
        im = im.crop((0, 20, 700, 540))
        d = ImageDraw.Draw(im)
        d.rectangle((0, 0, 260, 18), fill=(0, 0, 0))
        d.text((4, 3), "%s view %d zoom %d %s" % (g, v, z, title), fill=(255, 255, 0))
        tiles.append(im)
    w, h = tiles[0].size
    sheet = Image.new("RGB", (w * 2 + 4, h * 2 + 4), (40, 40, 40))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % 2) * (w + 4), (i // 2) * (h + 4)))
    sheet.save(out)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
