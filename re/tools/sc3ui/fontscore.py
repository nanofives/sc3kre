#!/usr/bin/env python3
r"""fontscore.py - sc3ui2 (round 2026-11-18g): rank free Google Fonts against the game's own FBF glyphs.

For each UI element (title bars, body labels, buttons, ...) the game string is laid out with the FBF font's own
advances (fbf.py). Every candidate (family x weight x px size) renders the same string as DOM text in headless Chrome,
the way the published pages render it. Pass 1 reads each span's natural width (--dump-dom), pass 2 renders it again
with the letter-spacing that makes the total advance equal to the game's, screenshots it, and scores:

  glyph IoU   soft IoU sum(min)/sum(max) of coverage 0..1, each glyph aligned on its own (best integer shift),
              mean weighted by the game glyph's ink: letter SHAPE and SIZE
  string IoU  the whole string at the fitted letter-spacing, best integer shift; also after a ~1 px blur (blur),
              which forgives sub-pixel placement: shape + spacing as read at normal distance
  ink ratio   candidate ink / game ink over the glyph cells: stroke WEIGHT (1.00 = same darkness)
  adv err     natural width / game width - 1 (before letter-spacing)
  ls          the letter-spacing that closes the advance gap, px
  score       0.5 glyph IoU + 0.5 blurred string IoU (the ranking)

The FBF files are read from the local game install at run time. Nothing derived from them is written to the repo:
results go to --out (a gitignored verify/ folder).

    py -3.12 re/tools/sc3ui/fontscore.py --text-dir <install>\Apps\Res\Text\ENGLISH --out verify/sc3ui2/fontscore
"""
import argparse, html, json, os, pathlib, re, subprocess, sys, tempfile
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fbf import Font

CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
SANS = ['Atkinson Hyperlegible Next', 'Arimo', 'Roboto', 'Open Sans', 'Noto Sans', 'Inter', 'Lato', 'PT Sans', 'Source Sans 3', 'Nunito Sans',
        'Work Sans', 'IBM Plex Sans', 'Fira Sans', 'Ubuntu', 'Hind', 'Libre Franklin', 'Archivo', 'Heebo', 'Karla',
        'Rubik', 'Cabin', 'Asap', 'Overpass', 'Public Sans', 'Red Hat Text', 'Figtree', 'Atkinson Hyperlegible',
        'Lexend', 'Encode Sans', 'Istok Web', 'Pontano Sans', 'Gudea', 'Albert Sans', 'Mukta', 'Signika', 'Oxygen',
        'Titillium Web', 'Raleway', 'Montserrat', 'Poppins', 'Manrope', 'DM Sans', 'Barlow', 'Sarabun',
        'Tahoma', 'Verdana', 'Arial', 'Segoe UI']
HAND = ['Comic Neue', 'Comic Relief', 'Balsamiq Sans', 'Shantell Sans', 'Playpen Sans', 'Grandstander',
        'Short Stack', 'Coming Soon', 'Patrick Hand', 'Delius', 'Mali', 'Itim', 'Kalam', 'Handlee', 'Andika',
        'Sniglet', 'Gochi Hand', 'Architects Daughter', 'Schoolbell', 'Indie Flower', 'Neucha', 'Kodchasan',
        'Sriracha', 'Gaegu', 'Baloo 2', 'Fredoka', 'Nunito', 'Quicksand', 'Varela Round', 'Comic Sans MS']
SERIF = ['Tinos', 'Libre Baskerville', 'Crimson Text', 'EB Garamond', 'Lora', 'Merriweather', 'PT Serif', 'Noto Serif',
         'Source Serif 4', 'Playfair Display', 'Cormorant', 'Spectral', 'Gelasio', 'Domine', 'Bitter', 'Cardo', 'Alegreya',
         'Libre Caslon Text', 'Old Standard TT', 'Times New Roman', 'Georgia']
LOCAL = {'Tahoma', 'Verdana', 'Arial', 'Segoe UI', 'Comic Sans MS', 'Times New Roman', 'Georgia'}   # Windows faces, reference only

# element -> (FBF file, game string, candidates, weights, px sizes)
ELEMENTS = {
    'title':  ('TITLE12.FBF', 'Preferencias Indagar Presupuesto Graficas', HAND + SANS[:8], [400, 700],
               [x / 2 for x in range(28, 41)]),
    'body':   ('MAIN9.FBF', 'Efectos sonido Tr\xe1fico visible 3 Aumentos Desactivados Updown Town Night Life '
               'Opciones generales: Ver consejos al iniciar Berlin Pob: 794,278', SANS, [400, 500, 600, 700, 800],
               [x / 2 for x in range(20, 31)]),
    'button': ('TITLE9.FBF', 'Sustituir Gastos Ingresos Aceptar Cancelar', HAND + SANS[:8], [400, 700],
               [x / 2 for x in range(22, 31)]),
    'row':    ('SYSTEM9.FBF', 'Ordenanzas Tratos con vecinos Pr\xe9stamos Educaci\xf3n Sanidad p\xfablica Bomberos',
               SANS, [400, 500], [x / 2 for x in range(18, 29)]),
    'digits': ('MAIN9.FBF', 'Pob: 794,278 2/9/2067 800x600 0123456789 $117,006 -$3,796 100%', SANS, [600, 700, 800],
               [x / 2 for x in range(22, 29)]),
    'menu':   ('SERIF17.FBF', 'Nueva Ciudad Cargar Ciudad Preferencias Salir', SERIF, [400, 700],
               [x / 2 for x in range(36, 53)]),
    'name':   ('MAIN10.FBF', "Camiones O'Plenty Industrial Media Muy bajo", SANS, [600, 700, 800],
               [x / 2 for x in range(22, 33)]),
}
ROW_H = 40
PAD = 8
CW = 34          # pitch of the single-glyph cells to the right of each row's string
CHUNK = 260      # configs per Chrome page (keeps a screenshot under 11,000 px)


def glyphs_of(text):
    return sorted({c for c in text if c != ' '})


def layout(text, gw):
    """x of the glyph cells, the glyphs, row width."""
    chx = PAD + gw + 40
    g = glyphs_of(text)
    return chx, g, chx + len(g) * CW + 20


def page(configs, gw, ls=None):
    fams = sorted({c['family'] for c in configs} - LOCAL)
    links = ''
    for f in fams:
        q = f.replace(' ', '+')
        links += '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=%s:wght@100..900&display=block">' % q
        links += '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=%s:wght@400;700&display=block">' % q
    text = configs[0]['text']
    chx, gl, width = layout(text, gw)
    spans = []
    for i, c in enumerate(configs):
        y = i * ROW_H
        st = "top:%dpx;font-family:'%s';font-weight:%d;font-size:%.1fpx" % (y + PAD, c['family'], c['weight'], c['size'])
        sp = st + (';letter-spacing:%.3fpx' % ls[i] if ls is not None else '')
        spans.append('<span id="s%d" style="left:%dpx;%s">%s</span>' % (i, PAD, sp, html.escape(text)))
        for k, ch in enumerate(gl):
            spans.append('<span style="left:%dpx;%s">%s</span>' % (chx + k * CW, st, html.escape(ch)))
    js = ("<script>document.fonts.ready.then(()=>{setTimeout(()=>{const r=[];"
          "for(let i=0;i<%d;i++){const s=document.getElementById('s'+i);"
          "r.push([s.getBoundingClientRect().width,document.fonts.check(s.style.fontWeight+' '+s.style.fontSize+' '+s.style.fontFamily)]);}"
          "document.getElementById('out').textContent=JSON.stringify(r);},800);});</script>") % len(configs)
    css = ('body{margin:0;background:#fff;color:#000;position:relative;width:%dpx;height:%dpx}'
           'span{position:absolute;white-space:pre;line-height:1}#out{position:absolute;left:0;top:0;color:#fff;'
           'font-size:1px;margin:0}') % (width, len(configs) * ROW_H + 20)
    return ('<!doctype html><html><head><meta charset="utf-8">%s<style>%s</style></head><body><pre id="out"></pre>'
            '%s%s</body></html>') % (links, css, ''.join(spans), js), width


def chrome(args, timeout=900):
    prof = tempfile.mkdtemp(prefix='fsc')
    return subprocess.run([CHROME, '--headless=new', '--hide-scrollbars', '--force-device-scale-factor=1',
                           '--user-data-dir=' + prof, '--virtual-time-budget=90000'] + args,
                          capture_output=True, timeout=timeout, text=True, encoding='utf-8', errors='replace')


def blur(a):
    """separable [1 2 1]/4 blur, twice (about sigma 1 px): tolerant to sub-pixel placement."""
    k = np.array([1, 2, 1]) / 4.0
    for _ in range(2):
        a = np.apply_along_axis(lambda r: np.convolve(r, k, 'same'), 1, a)
        a = np.apply_along_axis(lambda r: np.convolve(r, k, 'same'), 0, a)
    return a


def soft_iou(a, b):
    return float(np.minimum(a, b).sum() / max(np.maximum(a, b).sum(), 1e-9))


def best_shift(game, cand, x0, y0, rx=3, ry=5):
    gh, gw = game.shape
    best = (-1.0, 0, 0)
    for dy in range(-ry, ry + 1):
        for dx in range(-rx, rx + 1):
            yy, xx = y0 + dy, x0 + dx
            if yy < 0 or xx < 0:
                continue
            c = cand[yy:yy + gh, xx:xx + gw]
            if c.shape != game.shape:
                continue
            v = soft_iou(game, c)
            if v > best[0]:
                best = (v, dx, dy)
    return best


def run(el, text_dir, out):
    fbf, text, fams, weights, sizes = ELEMENTS[el]
    f = Font(os.path.join(text_dir, fbf))
    game = f.render(text)
    gw = game.shape[1]
    chx, gl, _ = layout(text, gw)
    gcells = {ch: f.cell(ch.encode('latin1')[0])[0] for ch in gl}
    gink = {ch: gcells[ch].sum() for ch in gl}
    configs = [dict(family=fa, weight=w, size=s, text=text) for fa in fams for w in weights for s in sizes]
    tmp = pathlib.Path(out).resolve() / ('_' + el)
    tmp.mkdir(parents=True, exist_ok=True)
    rows = []
    for c0 in range(0, len(configs), CHUNK):
        part = configs[c0:c0 + CHUNK]
        p1 = tmp / 'p1.html'
        p1.write_text(page(part, gw)[0], encoding='utf-8')
        r = chrome(['--dump-dom', p1.as_uri()])
        m = re.search(r'<pre id="out">(.*?)</pre>', r.stdout, re.S)
        if not m or not m.group(1).strip():
            raise SystemExit('pass 1 returned no measurements (stderr: %s)' % r.stderr[-400:])
        meas = json.loads(html.unescape(m.group(1)))
        ls = [(gw - wd) / len(text) for wd, _ in meas]
        p2 = tmp / 'p2.html'
        doc, width = page(part, gw, ls)
        p2.write_text(doc, encoding='utf-8')
        png = tmp / 'p2.png'
        chrome(['--window-size=%d,%d' % (width, len(part) * ROW_H + 20), '--screenshot=' + str(png), p2.as_uri()])
        cov = 1 - np.asarray(Image.open(png).convert('L'), float) / 255.0
        for i, c in enumerate(part):
            y = i * ROW_H
            band = cov[y:y + ROW_H]
            v, dx, dy = best_shift(game, band, PAD, PAD)
            cc = band[PAD + dy:PAD + dy + game.shape[0], PAD + dx:PAD + dx + gw]
            vb = soft_iou(blur(game), blur(cc)) if cc.shape == game.shape else 0.0
            num = den = ink_c = 0.0
            for k, ch in enumerate(gl):
                gc = gcells[ch]
                gv, gdx, gdy = best_shift(gc, band, chx + k * CW, PAD, rx=5, ry=5)
                num += gv * gink[ch]; den += gink[ch]
                ink_c += band[:, chx + k * CW - 4:chx + k * CW + CW - 4].sum()
            rows.append(dict(family=c['family'], weight=c['weight'], size=c['size'],
                             glyph_iou=round(num / max(den, 1e-9), 4), string_iou=round(v, 4),
                             string_iou_blur=round(vb, 4), ink_ratio=round(ink_c / max(den, 1e-9), 3),
                             adv_err=round(meas[i][0] / gw - 1, 4), ls=round(ls[i], 3),
                             loaded=bool(meas[i][1]) or c['family'] in LOCAL, dx=dx, dy=dy))
        png.unlink()
    rows = [r for r in rows if r['loaded']]
    for r in rows:
        r['score'] = round(0.5 * r['glyph_iou'] + 0.5 * r['string_iou_blur'], 4)
    rows.sort(key=lambda r: -r['score'])
    tag = '_only' if len(fams) < 5 else ''
    json.dump(dict(fbf=fbf, text=text, game_width=gw, line=f.line, rows=rows),
              open(pathlib.Path(out) / (el + tag + '.json'), 'w'), indent=0)
    return rows, f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--text-dir', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--el', nargs='*', default=list(ELEMENTS))
    ap.add_argument('--only', nargs='*', help='score only these families (results go to <el>_only.json)')
    ap.add_argument('--weights', nargs='*', type=int, help='override the element weights')
    a = ap.parse_args()
    if a.only:
        for el in a.el:
            fb, tx, fams, w, sz = ELEMENTS[el]
            ELEMENTS[el] = (fb, tx, [f for f in a.only], a.weights or w, sz)
    for el in a.el:
        rows, f = run(el, a.text_dir, a.out)
        print('== %s (%s, line %d px): %d configs loaded and scored' % (el, ELEMENTS[el][0], f.line, len(rows)))
        seen = set()
        for r in rows:
            if r['family'] in seen:
                continue
            seen.add(r['family'])
            print('  %-22s w%d %5.1fpx  score %.3f  glyph %.3f  string %.3f/blur %.3f  ink %.2f  adv %+5.1f%%  ls %+.2f%s' % (
                r['family'], r['weight'], r['size'], r['score'], r['glyph_iou'], r['string_iou'], r['string_iou_blur'],
                r['ink_ratio'], 100 * r['adv_err'], r['ls'],
                '  (local Windows face)' if r['family'] in LOCAL else ''))
            if len(seen) >= 12:
                break
        sys.stdout.flush()


if __name__ == '__main__':
    main()
