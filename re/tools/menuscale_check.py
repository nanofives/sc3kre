"""Offline check of a MENUSCALE dump (sc3resize SC3RESIZE_MENUSCALE_DUMP): recompute the scaled rect from the dumped
frame, background mask and cover picture with the same integer math as rz_ms_axis / rz_ms_compose, compare it with
the dumped client pixel for pixel, and check the margins equal the picture.

    py re/tools/menuscale_check.py <prefix> --filter bilinear|nearest
    (<prefix>_client.png, _frame.png, _mask.png, _picture.png as written by the session driver)
"""
import argparse
import numpy as np
from PIL import Image

W, H = 800, 600


def rect(cw, ch):
    if cw * H >= ch * W:
        rh = ch; rw = ch * W // H
    else:
        rw = cw; rh = cw * H // W
    return (cw - rw) // 2, (ch - rh) // 2, rw, rh


def axis(rl, nat, filt):
    i = np.arange(rl, dtype=np.int64)
    if filt:
        u = (2 * i + 1) * nat * 256 // (2 * rl) - 128
        u = np.maximum(u, 0)
        s, f = u >> 8, u & 255
        last = s >= nat - 1
        s[last] = nat - 1; f[last] = 0
        return s, f
    return (2 * i + 1) * nat // (2 * rl), np.zeros(rl, dtype=np.int64)


def lerp(a, b, f):
    w = 256 - f
    rb = (((a & 0xFF00FF) * w + (b & 0xFF00FF) * f) >> 8) & 0xFF00FF
    g = (((a & 0x00FF00) * w + (b & 0x00FF00) * f) >> 8) & 0x00FF00
    return rb | g


def pack(im):
    a = np.asarray(im.convert("RGB")).astype(np.int64)
    return (a[..., 0] << 16) | (a[..., 1] << 8) | a[..., 2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prefix")
    ap.add_argument("--filter", choices=["bilinear", "nearest"], default="bilinear")
    a = ap.parse_args()
    cl = pack(Image.open(a.prefix + "_client.png"))
    fr = pack(Image.open(a.prefix + "_frame.png"))
    bg = pack(Image.open(a.prefix + "_mask.png")) != 0
    pic = pack(Image.open(a.prefix + "_picture.png"))
    ch, cw = cl.shape
    rx, ry, rw, rh = rect(cw, ch)
    filt = a.filter == "bilinear"
    xs, xf = axis(rw, W, filt)
    ys, yf = axis(rh, H, filt)
    p = pic[ry:ry + rh, rx:rx + rw]
    X0 = xs[None, :]; Y0 = ys[:, None]
    if not filt:
        exp = np.where(bg[Y0, X0], p, fr[Y0, X0])
    else:
        X1 = np.minimum(X0 + 1, W - 1); Y1 = np.minimum(Y0 + 1, H - 1)
        def tap(Y, X):
            return np.where(bg[Y, X], p, fr[Y, X])
        ta, tb, tc, td = tap(Y0, X0), tap(Y0, X1), tap(Y1, X0), tap(Y1, X1)
        fx = xf[None, :]; fy = yf[:, None]
        exp = lerp(lerp(ta, tb, fx), lerp(tc, td, fx), fy)
        allbg = bg[Y0, X0] & bg[Y0, X1] & bg[Y1, X0] & bg[Y1, X1]
        exp = np.where(allbg, p, exp)
    got = cl[ry:ry + rh, rx:rx + rw]
    bad = got != exp
    marg = np.ones_like(cl, dtype=bool); marg[ry:ry + rh, rx:rx + rw] = False
    mbad = (cl != pic) & marg
    print(f"client {cw}x{ch} rect [{rx} {ry} {rx + rw} {ry + rh}] {a.filter}: rect pixels {got.size}, "
          f"mismatches {int(bad.sum())}; margin pixels {int(marg.sum())}, mismatches {int(mbad.sum())}; "
          f"frame background pixels {int(bg.sum())} of {W * H}")
    if bad.any():
        yy, xx = np.nonzero(bad)
        print("first mismatches (rect coords):", list(zip(yy[:5].tolist(), xx[:5].tolist())))


if __name__ == "__main__":
    main()
