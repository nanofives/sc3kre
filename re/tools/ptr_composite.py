"""Overlay the pointer shape measured with ptrshape.exe (magenta = transparent, grey = inverted) onto a grab at the
cursor point (hotspot 0,0), then crop around it at x3. A desktop grab never contains the hardware cursor, so this is
how the frame looks on the glass with the pointer drawn at its measured size.

usage: py composite.py <grab.png> <pointer.bmp> <x> <y> <out.png>
"""
import sys

from PIL import Image

grab = Image.open(sys.argv[1]).convert("RGB")
ptr = Image.open(sys.argv[2]).convert("RGB")
x, y = int(sys.argv[3]), int(sys.argv[4])
out = grab.copy()
for py_ in range(ptr.height):
    for px in range(ptr.width):
        c = ptr.getpixel((px, py_))
        tx, ty = x + px, y + py_
        if not (0 <= tx < out.width and 0 <= ty < out.height) or c == (255, 0, 255):
            continue
        if c == (128, 128, 128):
            r, g, b = out.getpixel((tx, ty)); c = (255 - r, 255 - g, 255 - b)
        out.putpixel((tx, ty), c)
box = (max(0, x - 70), max(0, y - 60), min(out.width, x + 150), min(out.height, y + 140))
crop = out.crop(box)
crop.resize((crop.width * 3, crop.height * 3), Image.NEAREST).save(sys.argv[5])
print("crop", box)
