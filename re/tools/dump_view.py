"""Convert the mod's surface dumps to viewable PNGs.

Usage: dump_view.py [dumpdir] [--strip x0 x1]
Writes <name>_half.png (whole frame, 50%) and <name>_strip.png (a crop) next to the BMPs.
"""
import glob
import os
import sys

from PIL import Image

d = sys.argv[1] if len(sys.argv) > 1 else "verify/resize_clicklab/dumps"
x0, x1 = 1780, 2048
if "--strip" in sys.argv:
    i = sys.argv.index("--strip")
    x0, x1 = int(sys.argv[i + 1]), int(sys.argv[i + 2])

made = 0
for f in sorted(glob.glob(os.path.join(d, "*.bmp"))):
    im = Image.open(f).convert("RGB")
    base = os.path.splitext(f)[0]
    im.resize((im.width // 2, im.height // 2)).save(base + "_half.png")
    made += 1
    print(f"{os.path.basename(f)}  {im.width}x{im.height} -> _half.png")
    if im.width > x1 - x0 + 100:
        im.crop((x0, 0, min(x1, im.width), im.height)).save(base + "_strip.png")
        print(f"    strip x{x0}..{x1} -> _strip.png")
print(f"{made} dump(s) converted")
