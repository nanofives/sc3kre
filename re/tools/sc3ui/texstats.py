#!/usr/bin/env python3
r"""texstats.py - sc3ui2 (round 2026-11-18g): numbers that describe a cloud texture, to match ours to the game's.

    py -3.12 re/tools/sc3ui/texstats.py <tile.png> [<tile2.png> ...]

Per image: per-channel mean and standard deviation (0..255), the principal colour axis (the clouds vary along one
line in RGB), luminance percentiles, the radially averaged power spectrum's centroid wavelength and peak band (the
dominant cloud size, px), and the wrap seam (mean |diff| across the right/left and bottom/top edges against the
mean neighbour |diff| inside: 1.0 = seamless tile), and the share of the luminance variance per
octave of wavelength (256-128 px, 128-64, 64-32, 32-16, 16-8, 8-2).
"""
import sys, json
import numpy as np
from PIL import Image


def stats(path, crop=None):
    a = np.asarray(Image.open(path).convert('RGB'), float)
    if crop:
        x0, y0, x1, y1 = crop
        a = a[y0:y1, x0:x1]
    h, w, _ = a.shape
    px = a.reshape(-1, 3)
    mean = px.mean(0); std = px.std(0)
    cov = np.cov((px - mean).T)
    ev, evec = np.linalg.eigh(cov)
    axis = evec[:, -1] * np.sign(evec[:, -1].sum())
    expl = ev[-1] / ev.sum()
    lum = px @ np.array([0.2126, 0.7152, 0.0722])
    pct = np.percentile(lum, [1, 10, 50, 90, 99])
    # power spectrum of the luminance, radial average
    L = lum.reshape(h, w) - lum.mean()
    n = min(h, w)
    L = L[:n, :n]
    F = np.abs(np.fft.fftshift(np.fft.fft2(L))) ** 2
    yy, xx = np.indices(F.shape)
    r = np.hypot(yy - n // 2, xx - n // 2).astype(int)
    rad = np.bincount(r.ravel(), F.ravel()) / np.maximum(np.bincount(r.ravel()), 1)
    k = np.arange(len(rad))
    valid = (k >= 1) & (k <= n // 2)
    centroid_k = (k[valid] * rad[valid]).sum() / rad[valid].sum()
    # peak of k * P(k) (energy per octave), the scale that carries most variance
    kp = k[valid][np.argmax((k * rad)[valid])]
    # share of the luminance variance per octave of wavelength (px): 256-128, 128-64, 64-32, 32-16, 16-8, 8-2
    bands = []
    tot = (rad[valid] * np.bincount(r.ravel())[:len(rad)][valid]).sum()
    cnt = np.bincount(r.ravel())[:len(rad)]
    for hi, lo in [(256, 128), (128, 64), (64, 32), (32, 16), (16, 8), (8, 2)]:
        kk = (k > n / hi) & (k <= n / lo) & valid
        if hi >= n: kk = (k >= 1) & (k <= n / lo) & valid
        bands.append(round(float((rad[kk] * cnt[kk]).sum() / tot), 3))
    seam_x = np.abs(a[:, -1] - a[:, 0]).mean(); seam_y = np.abs(a[-1] - a[0]).mean()
    inner = (np.abs(np.diff(a, axis=1)).mean() + np.abs(np.diff(a, axis=0)).mean()) / 2
    return dict(file=path, size=[w, h], mean=[round(x, 1) for x in mean], std=[round(x, 2) for x in std],
                axis=[round(x, 3) for x in axis], axis_share=round(float(expl), 3),
                lum_pct_1_10_50_90_99=[round(x, 1) for x in pct],
                spectrum_centroid_wavelength_px=round(n / centroid_k, 1),
                spectrum_peak_wavelength_px=round(n / kp, 1),
                octave_share_256_128_64_32_16_8=bands,
                radial_power=[float('%.4g' % x) for x in rad[1:n // 2 + 1]],
                seam_ratio=round(float((seam_x + seam_y) / 2 / max(inner, 1e-9)), 2),
                hex_mean='#%02x%02x%02x' % tuple(int(round(x)) for x in mean))


if __name__ == '__main__':
    for p in sys.argv[1:]:
        s = stats(p)
        s.pop('radial_power')
        print(json.dumps(s))
