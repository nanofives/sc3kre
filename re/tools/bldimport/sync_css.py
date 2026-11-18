#!/usr/bin/env python3
r"""sync_css.py - sc3ui (round 2026-11-18f): copy docs/assets/sc3ui.css into classifier.html.

The importer has to open from any folder (the sample pack zip ships it as importer\index.html, away from docs/), so it
carries its own copy of the shared stylesheet between the `sc3ui.css begin` / `sc3ui.css end` markers.

    py -3.12 re/tools/bldimport/sync_css.py            # rewrite the copy in classifier.html
    py -3.12 re/tools/bldimport/sync_css.py --check    # exit 1 when the copy differs from docs/assets/sc3ui.css
    py -3.12 re/tools/bldimport/sync_css.py --publish  # also copy classifier.html + bldweb.js to docs/buildings/importer/
"""
import os, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
CSS = os.path.join(ROOT, 'docs', 'assets', 'sc3ui.css')
PAGE = os.path.join(HERE, 'classifier.html')
BEGIN, END = '/* ==== sc3ui.css begin (copy of docs/assets/sc3ui.css, re/tools/bldimport/sync_css.py) ==== */', '/* ==== sc3ui.css end ==== */'


def main():
    css = open(CSS, encoding='utf-8').read().strip('\n')
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
        shutil.copyfile(os.path.join(HERE, 'bldweb.js'), os.path.join(dst, 'bldweb.js'))
        print('copied classifier.html + bldweb.js to', dst)


if __name__ == '__main__':
    main()
