#!/usr/bin/env python3
r"""sc3font_check.py - sc3ui3 (round 2026-11-19b): sc3font.js draws the game's own fonts exactly.

Opens re/tools/bldimport/sc3font_test.html in headless Chrome with the test hook ?game=<install>, so sc3font.js reads
the FBF files of that install, builds the fonts in memory and draws known strings. Then compares every string with
re/tools/sc3ui/fbf.py's rendering of the same string (the game's glyph cells laid out with the game's advances):

  1-bit fonts (MAIN9, MAIN10, SYSTEM9)        every pixel must match: ink where the game has ink, none elsewhere
  anti-aliased fonts (TITLE9, TITLE12, SERIF17) coverage within 0.02 per pixel (sc3font.js draws coverage in
                                                1/64 steps; 8-bit screenshots round a little more)
  coloured sample                              every ink pixel is the CSS colour (the COLR glyphs use the text colour)
Also checks the page's sc3ui.css type tokens switched to the game fonts, and the fallback without a game folder.

    py -3.12 re/tools/bldimport/webtest/sc3font_check.py --game <install> [--out <dir>]

Prints "[N/M] name PASS|FAIL". Nothing from the game is written outside --out (a gitignored folder).
"""
import argparse, html, json, os, pathlib, re, subprocess, sys, tempfile
import numpy as np
from PIL import Image
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'sc3ui'))
from fbf import Font  # noqa: E402
CHROME = os.environ.get('SC3_BROWSER') or r'C:\Program Files\Google\Chrome\Application\chrome.exe'  # SC3_BROWSER=<msedge.exe>: Edge
PAGE = HERE.parent / 'sc3font_test.html'
ONE_BIT = {'MAIN9', 'MAIN10', 'SYSTEM9'}
SMOOTH = {'TITLE9', 'TITLE12'}   # build_fonts.mjs / sc3font.js SMOOTH (owner 2026-11-20)


def chrome(url, extra):
    prof = tempfile.mkdtemp(prefix='sc3font')
    return subprocess.run([CHROME, '--headless=new', '--hide-scrollbars', '--force-device-scale-factor=1', '--allow-file-access-from-files',
                           '--user-data-dir=' + prof, '--virtual-time-budget=15000', '--window-size=900,760', *extra, url],
                          capture_output=True, timeout=180, text=True, encoding='utf-8', errors='replace')


def result_of(dom):
    m = re.search(r'<pre id="result">(.*?)</pre>', dom, re.S)
    return json.loads(html.unescape(m.group(1))) if m else None


def find_file(d, name):
    for f in os.listdir(d):
        if f.lower() == name.lower() + '.fbf':
            return os.path.join(d, f)
    return None


def compare(tag, r, rgb, cov, lang_dir, step, side):
    for s in (r or {}).get('samples', []):
        f = Font(find_file(str(lang_dir), s['font']))
        exp = f.render(s['text'])
        h, w = exp.shape
        x, y = s['x'], s['y']
        got = cov[y:y + h, x:x + w + 4]
        exp_p = np.zeros_like(got); exp_p[:, :w] = exp
        # nothing may be drawn outside the expected box either (a shifted baseline or advance would show here)
        around = cov[max(0, y - 3):y + h + 3, max(0, x - 3):x + w + 7].sum() - got.sum()
        d = np.abs(got - exp_p)
        if s.get('color', '#000000') != '#000000':
            want = np.array([int(s['color'][k:k + 2], 16) for k in (1, 3, 5)], float)
            ink = rgb[y:y + h, x:x + w][exp > 0.99]
            err = float(np.abs(ink - want).max()) if len(ink) else 99
            step(tag + '%s in %s "%s"' % (s['font'], s['color'], s['text'][:20]), err <= 2 and len(ink) > 0,
                 '%d ink pixels, max channel difference from %s: %.0f' % (len(ink), s['color'], err))
            continue
        if s['font'] in ONE_BIT:
            wrong = int(((got > 0.5) != (exp_p > 0.5)).sum())
            ok = wrong == 0 and d.max() < 0.35 and around < 1
            detail = '%d of %d px differ (ink threshold 0.5), max coverage error %.3f' % (wrong, got.size, d.max())
        elif s['font'] in SMOOTH:
            # owner 2026-11-20 "Smooth": outlines traced from the game's coverage, not its pixels (UI_STYLE.md "Smooth
            # outlines"): measured mean error 0.064-0.084 and ink 0.97-1.01 at 100%, so the check is shape, not pixels
            ink_ratio = float(got.sum() / max(exp_p.sum(), 1e-9))
            ok = d.mean() <= 0.10 and 0.94 <= ink_ratio <= 1.06 and around < 3
            detail = 'smooth: coverage error mean %.3f, ink %.3f of the game, %.2f outside the box' % (d.mean(), ink_ratio, around)
        else:
            p99 = float(np.percentile(d, 99))
            ok = d.max() <= 0.02 and around < 1
            detail = 'coverage error mean %.3f, p99 %.3f, max %.3f' % (d.mean(), p99, d.max())
        step(tag + '%s "%s"' % (s['font'], s['text'][:28]), ok, detail)
        side.append(np.concatenate([exp_p, np.ones((h, 3)), got], 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--game', required=True)
    ap.add_argument('--out', default=str(pathlib.Path(tempfile.gettempdir()) / 'sc3font_check'))
    a = ap.parse_args()
    out = pathlib.Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    game = pathlib.Path(a.game).resolve()
    url = PAGE.as_uri() + '?game=' + game.as_uri() + '/'
    steps, results = [], []

    def step(name, ok, detail=''):
        results.append((name, ok, detail))

    r = result_of(chrome(url, ['--dump-dom']).stdout)
    step('page builds and loads every game font', bool(r and r.get('ok') and all(f['status'] == 'loaded' for f in r['fonts'].values()) and len(r['fonts']) == 6),
         json.dumps(r and r.get('fonts')))
    fam = (r or {}).get('tokens', {})
    step('sc3ui.css tokens switch to the game fonts', bool(fam) and 'SC3 MAIN9' in fam.get('t_ui', '') and 'SC3 SYSTEM9' in fam.get('t_row', '')
         and 'SC3 TITLE12' in fam.get('t_title', ''), json.dumps(fam) + ' gpx ' + str((r or {}).get('gpx')))
    fb = result_of(chrome(PAGE.as_uri(), ['--dump-dom']).stdout)
    step('no game folder: sc3ui.css fonts stay (published game font first, free font behind it)',
         bool(fb and fb.get('fallback') and not fb.get('used') and fb.get('family', '').startswith('"SC3 Main"') and 'Istok Web' in fb.get('family', '')), json.dumps(fb))
    # gamefont (round 2026-11-19d): the published web fonts (docs/assets/fonts/*.woff2) through sc3ui.css's @font-face
    pub = result_of(chrome(PAGE.as_uri() + '?published=1', ['--dump-dom']).stdout)
    step('published web fonts load through sc3ui.css (6 files)', bool(pub and pub.get('ok') and len(pub['fonts']) == 6
         and all(f['status'] == 'loaded' for f in pub['fonts'].values()) and pub.get('u') == '1px'), json.dumps(pub and pub.get('fonts')) + ' --u ' + str((pub or {}).get('u')))
    lang_dir = game / 'Apps' / 'Res' / 'Text' / (r or {}).get('lang', 'ENGLISH')
    side = []
    passes = [('', url, r), ('published ', PAGE.as_uri() + '?published=1', pub)]
    for tag, purl, res in passes:
        png = out / ('sc3font_test%s.png' % ('_published' if tag else ''))
        chrome(purl, ['--screenshot=' + str(png)])
        rgb = np.asarray(Image.open(png).convert('RGB'), float)
        cov = 1 - rgb.mean(2) / 255.0
        compare(tag, res, rgb, cov, lang_dir, step, side)
    if side:
        wmax = max(t.shape[1] for t in side)
        sheet = np.concatenate([np.pad(t, ((0, 4), (0, wmax - t.shape[1])), constant_values=0) for t in side], 0)
        im = Image.fromarray((255 - 255 * np.clip(sheet, 0, 1)).astype(np.uint8))
        im.resize((im.width * 3, im.height * 3), Image.NEAREST).save(out / 'sc3font_vs_fbf_x3.png')
    bad = 0
    for i, (name, ok, detail) in enumerate(results, 1):
        print('[%d/%d] %s %s' % (i, len(results), name, 'PASS' if ok else 'FAIL'))
        print('      ' + detail)
        bad += not ok
    print('%d of %d checks passed' % (len(results) - bad, len(results)))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
