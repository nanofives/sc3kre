#!/usr/bin/env python3
r"""cloudgen.py - sc3ui2 (round 2026-11-18g): our own cloud texture, an SVG feTurbulence tile tuned to the game's numbers.

The game's window body is one 256x256 tile repeated from the window's top-left corner. We never ship that bitmap.
Instead this script searches feTurbulence parameters (baseFrequency, numOctaves, seed), rendered by headless Chrome
exactly as a CSS background, for the one whose texstats numbers (octave energy shares, histogram shape) are closest
to the measured tile, then maps the noise linearly onto the game's colour axis (feColorMatrix) so the mean and
spread per channel match.

    py -3.12 re/tools/sc3ui/cloudgen.py --target <tile.png> --out verify/sc3ui2/cloud
Writes <out>/search.json, <out>/ours.svg, <out>/ours_render.png (our tile as Chrome draws it) and prints the
numbers side by side plus the CSS data URI.
"""
import argparse, json, os, pathlib, subprocess, sys, tempfile, urllib.parse
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from texstats import stats

CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
T = 256


def svg(freq, octaves, seed, matrix=None):
    m = matrix or '1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 0 0 0 0 1'
    return ("<svg xmlns='http://www.w3.org/2000/svg' width='%d' height='%d' viewBox='0 0 256 256'><filter id='c' x='0' y='0' width='100%%' "
            "height='100%%' color-interpolation-filters='sRGB'><feTurbulence type='fractalNoise' baseFrequency='%s' "
            "numOctaves='%d' seed='%d' stitchTiles='stitch'/><feColorMatrix values='%s'/></filter>"
            "<rect width='100%%' height='100%%' filter='url(#c)'/></svg>") % (T, T, freq, octaves, seed, m)


def uri(s):
    return 'data:image/svg+xml,' + urllib.parse.quote(s, safe=" =:/',;()")


def render(svgs, png, cols=8, chunk=64):
    if len(svgs) > chunk:
        out = []
        for i in range(0, len(svgs), chunk):
            out += render(svgs[i:i + chunk], png, cols, chunk)
        return out
    rows = (len(svgs) + cols - 1) // cols
    cells = ''.join('<div style="position:absolute;left:%dpx;top:%dpx;width:%dpx;height:%dpx;background:url(&quot;%s&quot;)"></div>'
                    % ((i % cols) * T, (i // cols) * T, T, T, uri(s)) for i, s in enumerate(svgs))
    doc = '<!doctype html><html><body style="margin:0;background:#000">%s</body></html>' % cells
    tmp = pathlib.Path(png).resolve().parent / '_grid.html'
    tmp.write_text(doc, encoding='utf-8')
    prof = tempfile.mkdtemp(prefix='cg')
    subprocess.run([CHROME, '--headless=new', '--hide-scrollbars', '--force-device-scale-factor=1',
                    '--user-data-dir=' + prof, '--virtual-time-budget=20000',
                    '--window-size=%d,%d' % (cols * T, rows * T), '--screenshot=' + str(png), tmp.as_uri()],
                   capture_output=True, timeout=600)
    im = Image.open(png).convert('RGB')
    tiles = [im.crop(((i % cols) * T, (i // cols) * T, (i % cols) * T + T, (i // cols) * T + T)) for i in range(len(svgs))]
    tmp.unlink(); pathlib.Path(png).unlink()
    return tiles


def shape_of(st):
    p = np.array(st['lum_pct_1_10_50_90_99'])
    return (p - p[2]) / max(np.std([p[0], p[4]]), 1e-9)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--target', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    out = pathlib.Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    tgt = stats(a.target)
    to = np.array(tgt['octave_share_256_128_64_32_16_8'])
    # stitchTiles rounds the frequency to whole periods per tile, so search on k/256
    grid = [(round(k / T, 5), o, s) for k in (1, 1.5, 2, 2.5, 3) for o in (1, 2, 3, 4, 5) for s in range(1, 41)]
    tiles = render([svg(*g) for g in grid], out / '_grid.png')
    res = []
    for g, t in zip(grid, tiles):
        p = out / '_t.png'; t.save(p)
        st = stats(str(p))
        d_oct = float(np.abs(np.array(st['octave_share_256_128_64_32_16_8']) - to).sum())
        d_shape = float(np.abs(shape_of(st) - shape_of(tgt)).mean())
        res.append(dict(freq=g[0], octaves=g[1], seed=g[2], d_octave=round(d_oct, 4), d_hist=round(d_shape, 4),
                        cost=round(d_oct + 0.25 * d_shape, 4), mean=st['mean'][0], std=st['std'][0]))
    (out / '_t.png').unlink()
    res.sort(key=lambda r: r['cost'])
    json.dump(res, open(out / 'search.json', 'w'), indent=0)
    b = res[0]
    # linear map of the noise (grey, 0..1) onto the target's R and G, B constant
    mt, sd = np.array(tgt['mean']) / 255, np.array(tgt['std']) / 255
    mn, sn = b['mean'] / 255, b['std'] / 255
    gains = np.where(sd > 0, sd / max(sn, 1e-9), 0.0)
    offs = mt - gains * mn
    # every output channel reads the noise's R channel (the raw search renders R as grey)
    mat = '%.4f 0 0 0 %.4f %.4f 0 0 0 %.4f %.4f 0 0 0 %.4f 0 0 0 0 1' % (gains[0], offs[0], gains[1], offs[1], gains[2], offs[2])
    final = svg(b['freq'], b['octaves'], b['seed'], mat)
    (out / 'ours.svg').write_text(final, encoding='utf-8')
    t = render([final], out / '_one.png', cols=1)[0]
    t.save(out / 'ours_render.png')
    ours = stats(str(out / 'ours_render.png'))
    print('best: baseFrequency %s, numOctaves %d, seed %d (cost %.4f; next %s)' % (
        b['freq'], b['octaves'], b['seed'], b['cost'], [(r['freq'], r['octaves'], r['seed'], r['cost']) for r in res[1:4]]))
    for k in ('mean', 'std', 'axis', 'axis_share', 'lum_pct_1_10_50_90_99', 'octave_share_256_128_64_32_16_8',
              'spectrum_centroid_wavelength_px', 'seam_ratio', 'hex_mean'):
        print('  %-34s game %-40s ours %s' % (k, tgt[k], ours[k]))
    print('CSS: url("%s")' % uri(final))
    print('bytes:', len(uri(final)))


if __name__ == '__main__':
    main()
