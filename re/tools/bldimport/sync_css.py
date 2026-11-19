#!/usr/bin/env python3
r"""sync_css.py - sc3ui (round 2026-11-18f): copy docs/assets/sc3ui.css into classifier.html.

The importer has to open from any folder (the sample pack zip ships it as importer\index.html, away from docs/), so it
carries its own copy of the shared stylesheet between the `sc3ui.css begin` / `sc3ui.css end` markers.

    py -3.12 re/tools/bldimport/sync_css.py            # rewrite the copy in classifier.html
    py -3.12 re/tools/bldimport/sync_css.py --check    # exit 1 when the copy differs from docs/assets/sc3ui.css
    py -3.12 re/tools/bldimport/sync_css.py --publish  # also copy classifier.html + bldweb.js + sc4web.js + sc3font.js + sc3pack.js to docs/buildings/importer/

sc3ui3 (round 2026-11-19b): sc3ui.css draws a few game bitmaps from docs/assets/sc3ui/ (url("sc3ui/<name>.png")). The
importer opens away from docs/, so its copy carries them inline: every such url() becomes a data: URI here.
gamefont (round 2026-11-19d): the same for the game's web fonts (url("fonts/<name>.woff2"), docs/assets/fonts/, built by
re/tools/sc3ui/build_fonts.mjs), so the importer draws the game's text from any folder or the sample pack zip. The page's
run-time builder (sc3font.js, from the player's game folder) is only the fallback when those faces fail to load.
"""
import base64, os, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
CSS = os.path.join(ROOT, 'docs', 'assets', 'sc3ui.css')
ART = os.path.join(ROOT, 'docs', 'assets', 'sc3ui')
FONTS = os.path.join(ROOT, 'docs', 'assets', 'fonts')
PAGE = os.path.join(HERE, 'classifier.html')
BEGIN, END = '/* ==== sc3ui.css begin (copy of docs/assets/sc3ui.css, re/tools/bldimport/sync_css.py) ==== */', '/* ==== sc3ui.css end ==== */'
# published next to index.html. sc4web.js: task sc4web (SC4 downloads in the page). sc3font.js: sc3ui3 (the game's
# fonts, built at run time from the player's own game folder). sc3pack.js: sc3compat-b (the SC3 pack reader)
PUBLISHED = ('bldweb.js', 'sc4web.js', 'sc3font.js', 'sc3pack.js')


def inline_art(css):
    """url("sc3ui/x.png") -> url("data:image/png;base64,...") read from docs/assets/sc3ui/x.png, and
    url("fonts/X.woff2") -> url("data:font/woff2;base64,...") read from docs/assets/fonts/X.woff2 (gamefont)"""
    def one(m):
        with open(os.path.join(ART, m.group(1)), 'rb') as fh:
            return 'url("data:image/png;base64,%s")' % base64.b64encode(fh.read()).decode('ascii')
    cache = {}
    def font(m):
        if m.group(1) not in cache:
            with open(os.path.join(FONTS, m.group(1)), 'rb') as fh:
                cache[m.group(1)] = 'url("data:font/woff2;base64,%s")' % base64.b64encode(fh.read()).decode('ascii')
        return cache[m.group(1)]
    css = re.sub(r'url\("sc3ui/([A-Za-z0-9_]+\.png)"\)', one, css)
    return re.sub(r'url\("fonts/([A-Za-z0-9_]+\.woff2)"\)', font, css)


def main():
    css = inline_art(open(CSS, encoding='utf-8').read().strip('\n'))
    page = open(PAGE, encoding='utf-8', newline='').read()
    m = re.search(re.escape(BEGIN) + r'\n(.*?)\n' + re.escape(END), page, re.S)
    if not m:
        sys.exit('markers not found in classifier.html')
    if '--check' in sys.argv:
        ok = m.group(1).replace('\r\n', '\n') == css
        print('sc3ui.css copy in classifier.html:', 'in sync' if ok else 'OUT OF SYNC')
        sys.exit(0 if ok else 1)
    nl = '\r\n' if '\r\n' in page else '\n'
    new = page[:m.start(1)] + css.replace('\n', nl) + page[m.end(1):]
    if new != page:
        open(PAGE, 'w', encoding='utf-8', newline='').write(new)
        print('classifier.html: sc3ui.css copy updated')
    else:
        print('classifier.html: already in sync')
    if '--publish' in sys.argv:
        dst = os.path.join(ROOT, 'docs', 'buildings', 'importer')
        os.makedirs(dst, exist_ok=True)
        shutil.copyfile(PAGE, os.path.join(dst, 'index.html'))
        for js in PUBLISHED:
            shutil.copyfile(os.path.join(HERE, js), os.path.join(dst, js))
        print('copied classifier.html + ' + ' + '.join(PUBLISHED) + ' to', dst)


if __name__ == '__main__':
    main()
