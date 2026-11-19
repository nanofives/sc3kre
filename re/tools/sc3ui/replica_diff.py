#!/usr/bin/env python3
r"""replica_diff.py - sc3ui2 (round 2026-11-18g): score replica_prefs.html against the game's Preferencias dialog.

    py -3.12 re/tools/sc3ui/replica_diff.py --ref <game crop 480x472 png> --out <dir> [--html replica_prefs.html]

The reference is a native 800x600 grab of the running game cropped to the dialog (x 160..639, y 64..535 when the
dialog opens centred): it is game pixels, so it stays in a gitignored folder and is never published.

Measures, per region (dialog coordinates, measured off the grab, see UI_STYLE.md):
  dE px    mean CIEDE2000 over the region's pixels; text pixels (coverage > 0.08 in either image) excluded
  dE mean  CIEDE2000 between the region's mean colours (what a clouded area can match: our clouds are our own noise)
Edges: every 1 px line of the group grooves, plates and title bar is found in both images by exact colour and its
position compared, px. Text: per label, the ink box (left, top, right, bottom) in both, px.
Writes side_by_side.png, diff_dE.png (heat map, 0..10), text_overlay.png (red = game ink, blue = ours, purple = both),
replica.png, report.json.
"""
import argparse, json, os, pathlib, subprocess, tempfile
import numpy as np
from PIL import Image

CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
HERE = pathlib.Path(__file__).resolve().parent
W, H = 480, 472

# (name, kind, x0, y0, x1, y1) inclusive-exclusive boxes in dialog coordinates
REGIONS = [
    ('title bar', 'flat', 5, 5, 475, 34),
    ('frame clouds top', 'cloud', 1, 1, 479, 4),
    ('frame clouds under title', 'cloud', 1, 35, 479, 42),
    ('frame clouds left', 'cloud', 1, 42, 6, 422),
    ('frame clouds right', 'cloud', 474, 42, 479, 422),
    ('frame clouds between groups', 'cloud', 206, 42, 212, 342),
    ('frame clouds bottom', 'cloud', 1, 422, 430, 471),
    ('frame clouds, all', 'cloud', 0, 0, 0, 0),
    ('group left face', 'flat', 7, 43, 205, 341),
    ('group right face', 'flat', 213, 43, 473, 341),
    ('group bottom face', 'flat', 7, 347, 473, 421),
    ('sound panel', 'flat', 373, 47, 467, 155),
    ('list face', 'flat', 219, 179, 452, 307),
    ('strip', 'flat', 219, 311, 467, 337),
    ('combo face', 'flat', 19, 315, 158, 333),
    ('close button', 'button', 448, 8, 474, 32),
    ('OK button', 'button', 432, 434, 474, 467),
]
TEXT = [  # (name, box, game ink colour)
    ('title', (5, 5, 240, 34), '#dedfff'),
    ('Efectos sonido', (8, 44, 140, 64), '#7b7db5'),
    ('Trafico visible', (8, 66, 140, 86), '#7b7db5'),
    ('3 Aumentos', (30, 86, 140, 104), '#31347b'),
    ('Desactivados', (30, 140, 140, 158), '#31347b'),
    ('Sims visibles', (8, 160, 140, 180), '#7b7db5'),
    ('Resolucion de pantalla', (8, 292, 190, 312), '#7b7db5'),
    ('Sonido', (214, 44, 300, 64), '#7b7db5'),
    ('Musica', (236, 66, 330, 86), '#31347b'),
    ('Activar sonidos 3D', (236, 138, 370, 158), '#31347b'),
    ('Musicas posibles', (214, 158, 350, 178), '#7b7db5'),
    ('Updown Town', (238, 180, 350, 198), '#31347b'),
    ('Escuchar eleccion', (220, 312, 380, 336), '#31347b'),
    ('combo text', (19, 315, 176, 333), '#31347b'),
    ('Opciones generales', (8, 346, 170, 366), '#7b7db5'),
    ('Ver consejos', (32, 362, 200, 382), '#31347b'),
]
LINES = ['7b8aff', 'fff3ff', 'adb6ff']
# radio / check marks and the combo, scroll and strip button art: drawn, not part of a face colour
MARKS = [(16, 86, 32, 296), (219, 66, 237, 160), (221, 180, 238, 306), (16, 362, 33, 398), (176, 312, 196, 336),
         (452, 178, 470, 308), (440, 312, 468, 337), (378, 66, 466, 140)]


def hexrgb(h):
    h = h.lstrip('#')
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], float)


def srgb_to_lab(a):
    a = a / 255.0
    a = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750], [0.0193339, 0.1191920, 0.9503041]])
    xyz = a @ M.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def de2000(l1, l2):
    L1, a1, b1 = l1[..., 0], l1[..., 1], l1[..., 2]
    L2, a2, b2 = l2[..., 0], l2[..., 1], l2[..., 2]
    C1, C2 = np.hypot(a1, b1), np.hypot(a2, b2)
    Cm = (C1 + C2) / 2
    G = 0.5 * (1 - np.sqrt(Cm ** 7 / (Cm ** 7 + 25 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360
    dLp = L2 - L1
    dCp = C2p - C1p
    dh = h2p - h1p
    dh = np.where(C1p * C2p == 0, 0, np.where(dh > 180, dh - 360, np.where(dh < -180, dh + 360, dh)))
    dHp = 2 * np.sqrt(C1p * C2p) * np.sin(np.radians(dh / 2))
    Lpm = (L1 + L2) / 2
    Cpm = (C1p + C2p) / 2
    hs = h1p + h2p
    hpm = np.where(C1p * C2p == 0, hs, np.where(np.abs(h1p - h2p) <= 180, hs / 2, np.where(hs < 360, (hs + 360) / 2, (hs - 360) / 2)))
    T = (1 - 0.17 * np.cos(np.radians(hpm - 30)) + 0.24 * np.cos(np.radians(2 * hpm)) + 0.32 * np.cos(np.radians(3 * hpm + 6))
         - 0.20 * np.cos(np.radians(4 * hpm - 63)))
    dtheta = 30 * np.exp(-((hpm - 275) / 25) ** 2)
    Rc = 2 * np.sqrt(Cpm ** 7 / (Cpm ** 7 + 25 ** 7))
    Sl = 1 + 0.015 * (Lpm - 50) ** 2 / np.sqrt(20 + (Lpm - 50) ** 2)
    Sc = 1 + 0.045 * Cpm
    Sh = 1 + 0.015 * Cpm * T
    Rt = -np.sin(np.radians(2 * dtheta)) * Rc
    return np.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh))


def render(html, png):
    prof = tempfile.mkdtemp(prefix='rep')
    subprocess.run([CHROME, '--headless=new', '--hide-scrollbars', '--force-device-scale-factor=1', '--user-data-dir=' + prof,
                    '--allow-file-access-from-files', '--blink-settings=preferredColorScheme=1', '--virtual-time-budget=20000', '--window-size=%d,%d' % (W, H),
                    '--screenshot=' + str(png), pathlib.Path(html).resolve().as_uri()], capture_output=True, timeout=180)
    return np.asarray(Image.open(png).convert('RGB'), float)[:H, :W]


def text_mask(img, box, col, tol=70):
    x0, y0, x1, y1 = box
    d = np.sqrt(((img[y0:y1, x0:x1] - hexrgb(col)) ** 2).sum(2))
    return d < tol


def coverage(img, box, col):
    """0..1 per pixel: how far each pixel is from the box's median (background) towards the text colour."""
    x0, y0, x1, y1 = box
    a = img[y0:y1, x0:x1]
    t = hexrgb(col)
    bg = np.median(a.reshape(-1, 3), 0)
    v = bg - t
    return np.clip(((bg - a) @ v) / max(v @ v, 1e-9), 0, 1)


def ink_mass(img, box, col):
    x0, y0, x1, y1 = box
    a = img[y0:y1, x0:x1].reshape(-1, 3)
    t = hexrgb(col)
    bg = np.median(a, 0)
    v = bg - t
    cov = np.clip(((bg - a) @ v) / max(v @ v, 1e-9), 0, 1)
    return float(cov.sum())


def ink_box(m):
    ys, xs = np.where(m)
    if len(xs) == 0:
        return None
    return [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]


def lines(img):
    """1-px line segments of the groove / plate colours: (colour, orientation, fixed coord, start, end)."""
    out = []
    for c in LINES:
        m = (np.abs(img - hexrgb(c)).sum(2) == 0)
        for y in range(H):  # horizontal runs >= 20 px
            row = m[y]; x = 0
            while x < W:
                if row[x]:
                    s = x
                    while x < W and row[x]: x += 1
                    if x - s >= 20: out.append((c, 'h', y, s, x - 1))
                else:
                    x += 1
        for x in range(W):
            col = m[:, x]; y = 0
            while y < H:
                if col[y]:
                    s = y
                    while y < H and col[y]: y += 1
                    if y - s >= 20: out.append((c, 'v', x, s, y - 1))
                else:
                    y += 1
    return out


def match_lines(ref, rep):
    res = []
    for c, o, k, s, e in ref:
        cands = [(abs(k2 - k) + abs(s2 - s) + abs(e2 - e), k2 - k, s2 - s, e2 - e) for c2, o2, k2, s2, e2 in rep
                 if c2 == c and o2 == o and abs(k2 - k) <= 6 and min(e, e2) - max(s, s2) > 0.5 * (e - s)]
        if cands:
            best = min(cands)
            res.append(dict(colour='#' + c, orient=o, at=k, span=[s, e], d_pos=best[1], d_start=best[2], d_end=best[3]))
        else:
            res.append(dict(colour='#' + c, orient=o, at=k, span=[s, e], d_pos=None))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ref', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--html', default=str(HERE / 'replica_prefs.html'))
    a = ap.parse_args()
    out = pathlib.Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    ref = np.asarray(Image.open(a.ref).convert('RGB'), float)[:H, :W]
    rep = render(a.html, out / 'replica.png')
    L1, L2 = srgb_to_lab(ref), srgb_to_lab(rep)
    dE = de2000(L1, L2)
    # text pixels (either image) are not part of the colour regions
    textpx = np.zeros((H, W), bool)
    for name, box, col in TEXT:
        x0, y0, x1, y1 = box
        for img in (ref, rep):
            textpx[y0:y1, x0:x1] |= coverage(img, box, col) > 0.08
    # check and radio marks, list labels and the strip/list text are text too
    for img in (ref, rep):
        textpx |= (np.sqrt(((img - hexrgb('#31347b')) ** 2).sum(2)) < 60)
    for x0, y0, x1, y1 in MARKS:
        textpx[y0:y1, x0:x1] = True
    regions = []
    cloud = np.zeros((H, W), bool)
    for name, kind, x0, y0, x1, y1 in REGIONS:
        if kind == 'cloud' and x1 > x0:
            cloud[y0:y1, x0:x1] = True
    for name, kind, x0, y0, x1, y1 in REGIONS:
        if x1 == x0:   # the union of the cloud strips
            m = cloud & ~textpx
            d = dE[m]; mr = ref[m].mean(0); mp = rep[m].mean(0)
            dmean = float(de2000(srgb_to_lab(mr[None]), srgb_to_lab(mp[None]))[0])
            regions.append(dict(name=name, kind=kind, box=None, dE_px=round(float(d.mean()), 2),
                                dE_px_p90=round(float(np.percentile(d, 90)), 2), dE_mean=round(dmean, 2),
                                ref_mean='#%02x%02x%02x' % tuple(int(round(v)) for v in mr),
                                ours_mean='#%02x%02x%02x' % tuple(int(round(v)) for v in mp)))
            continue
        m = ~textpx[y0:y1, x0:x1]
        d = dE[y0:y1, x0:x1][m]
        if d.size == 0:
            print('  (region %s fully masked, skipped)' % name); continue
        mr = ref[y0:y1, x0:x1][m].mean(0); mp = rep[y0:y1, x0:x1][m].mean(0)
        dmean = float(de2000(srgb_to_lab(mr[None]), srgb_to_lab(mp[None]))[0])
        regions.append(dict(name=name, kind=kind, box=[x0, y0, x1, y1], dE_px=round(float(d.mean()), 2),
                            dE_px_p90=round(float(np.percentile(d, 90)), 2), dE_mean=round(dmean, 2),
                            ref_mean='#%02x%02x%02x' % tuple(int(round(v)) for v in mr),
                            ours_mean='#%02x%02x%02x' % tuple(int(round(v)) for v in mp)))
    texts = []
    ov = np.full((H, W, 3), 255.0)
    for name, box, col in TEXT:
        x0, y0, x1, y1 = box
        mr, mp = text_mask(ref, box, col), text_mask(rep, box, col)
        br, bp = ink_box(mr), ink_box(mp)
        sub = ov[y0:y1, x0:x1]
        sub[mr & ~mp] = (220, 30, 30); sub[mp & ~mr] = (30, 60, 230); sub[mr & mp] = (130, 30, 160)
        if br and bp:
            texts.append(dict(name=name, game=[v + o for v, o in zip(br, (x0, y0, x0, y0))],
                              ours=[v + o for v, o in zip(bp, (x0, y0, x0, y0))],
                              d_left=bp[0] - br[0], d_top=bp[1] - br[1], d_right=bp[2] - br[2], d_bottom=bp[3] - br[3],
                              ink_px_game=int(mr.sum()), ink_px_ours=int(mp.sum()),
                              ink_mass_ratio=round(ink_mass(rep, box, col) / max(ink_mass(ref, box, col), 1e-9), 3)))
        else:
            texts.append(dict(name=name, game=br, ours=bp))
    edges = match_lines(lines(ref), lines(rep))
    found = [e for e in edges if e['d_pos'] is not None]
    rep_j = dict(regions=regions, text=texts, edges=edges,
                 summary=dict(
                     frame_panels_dE_mean_max=max(r['dE_mean'] for r in regions if r['kind'] == 'flat' or r['name'] == 'frame clouds, all'),
                     flat_dE_px_max=max(r['dE_px'] for r in regions if r['kind'] == 'flat'),
                     edges_found=len(found), edges_total=len(edges),
                     edges_within_1px=sum(1 for e in found if abs(e['d_pos']) <= 1 and abs(e['d_start']) <= 1 and abs(e['d_end']) <= 1),
                     text_top_bottom_within_1px=sum(1 for t in texts if 'd_top' in t and abs(t['d_top']) <= 1 and abs(t['d_bottom']) <= 1),
                     text_total=len(texts)))
    json.dump(rep_j, open(out / 'report.json', 'w'), indent=1)
    sbs = np.concatenate([ref, np.full((H, 8, 3), 255.0), rep], 1)
    Image.fromarray(sbs.astype(np.uint8)).save(out / 'side_by_side.png')
    heat = np.clip(dE / 10, 0, 1)
    hm = np.stack([255 * heat, 255 * (1 - np.abs(heat - .5) * 2) * .6, 255 * (1 - heat) * .35], -1)
    Image.fromarray(hm.astype(np.uint8)).save(out / 'diff_dE.png')
    Image.fromarray(ov.astype(np.uint8)).save(out / 'text_overlay.png')
    s = rep_j['summary']
    print('regions:')
    for r in regions:
        print('  %-28s %-6s dE px %5.2f (p90 %5.2f)  dE mean %5.2f   game %s ours %s' % (
            r['name'], r['kind'], r['dE_px'], r['dE_px_p90'], r['dE_mean'], r['ref_mean'], r['ours_mean']))
    print('text (ours - game, px):')
    for t in texts:
        if 'd_top' in t:
            print('  %-22s left %+d top %+d right %+d bottom %+d   ink mass ours/game %.2f' % (
                t['name'], t['d_left'], t['d_top'], t['d_right'], t['d_bottom'], t['ink_mass_ratio']))
        else:
            print('  %-22s missing (game %s ours %s)' % (t['name'], t['game'], t['ours']))
    print('edges: %d of %d found, %d within 1 px' % (s['edges_found'], s['edges_total'], s['edges_within_1px']))
    for e in edges:
        if e['d_pos'] is None or abs(e['d_pos']) > 1 or abs(e['d_start']) > 1 or abs(e['d_end']) > 1:
            print('   off: %s %s at %d span %s -> %s' % (e['colour'], e['orient'], e['at'], e['span'],
                  'not found' if e['d_pos'] is None else 'pos %+d start %+d end %+d' % (e['d_pos'], e['d_start'], e['d_end'])))
    print('summary:', json.dumps(s))


if __name__ == '__main__':
    main()
