#!/usr/bin/env python3
r"""animrot: grab the game window's client area with PrintWindow (PW_RENDERFULLCONTENT), no raise, no focus.

  py -3.12 pwgrab.py <out.png>        (SC3_PID = the game)

For the -Stock control, which loads no sc3resize and so has no SC3RESIZE_FRAMEDUMP.
"""
import ctypes
import os
import pathlib
import sys
from ctypes import wintypes

from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "re" / "tools"))
import sc3io  # noqa: E402

u32, g32 = ctypes.windll.user32, ctypes.windll.gdi32


def main(a):
    h = sc3io.game_hwnd(int(os.environ["SC3_PID"]))
    r = wintypes.RECT()
    u32.GetClientRect(h, ctypes.byref(r))
    w, hh = r.right, r.bottom
    wdc = u32.GetWindowDC(h)
    mdc = g32.CreateCompatibleDC(wdc)
    bmp = g32.CreateCompatibleBitmap(wdc, w, hh)
    g32.SelectObject(mdc, bmp)
    ok = u32.PrintWindow(h, mdc, 1 | 2)          # PW_CLIENTONLY | PW_RENDERFULLCONTENT
    buf = ctypes.create_string_buffer(w * hh * 4)

    class BIH(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                    ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
                    ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]
    bi = BIH(ctypes.sizeof(BIH), w, -hh, 1, 32, 0, 0, 0, 0, 0, 0)
    g32.GetDIBits(mdc, bmp, 0, hh, buf, ctypes.byref(bi), 0)
    Image.frombuffer("RGBA", (w, hh), buf, "raw", "BGRA", 0, 1).convert("RGB").save(a[0])
    g32.DeleteObject(bmp)
    g32.DeleteDC(mdc)
    u32.ReleaseDC(h, wdc)
    print(a[0], "PrintWindow", ok, w, hh)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
