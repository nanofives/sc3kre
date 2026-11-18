"""Runs classifier.html?demo=1&selftest=1 in headless Chrome, dumps the DOM and checks the models.json round trip.
Usage: py -3.12 check_roundtrip.py   (needs Chrome; exit 0 = pass)"""
import json, os, re, subprocess, sys, tempfile, html, pathlib
here = pathlib.Path(__file__).resolve().parent
chrome = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
url = here.joinpath('classifier.html').as_uri() + '?demo=1&selftest=1'
prof = tempfile.mkdtemp(prefix='bcrt')
out = subprocess.run([chrome, '--headless=new', '--allow-file-access-from-files', '--enable-unsafe-swiftshader', '--use-angle=swiftshader',
                      '--user-data-dir=' + prof, '--virtual-time-budget=15000', '--dump-dom', url],
                     capture_output=True, text=True, timeout=120).stdout
m = re.search(r'<pre id="selftest"[^>]*>(.*?)</pre>', out, re.S)
if not m or not m.group(1).strip():
    print('FAIL: no selftest output'); sys.exit(1)
res = json.loads(html.unescape(m.group(1)))
if 'error' in res:
    print('FAIL', res['error']); sys.exit(1)
saved = json.loads(res.pop('savedText'))
orig = json.loads((here / 'samples' / 'models.json').read_text(encoding='utf-8'))
checks = {
  'page selftest pass flag': res['pass'],
  'top-level unknown key "generator" kept': saved.get('generator') == orig['generator'],
  'entry unknown key x_bldrender kept': saved['models'][0].get('x_bldrender') == orig['models'][0]['x_bldrender'],
  'entry unknown key author kept': saved['models'][1].get('author') == 'me',
  'entry for missing file kept': any(e['file'] == 'missing_building.obj' for e in saved['models']),
  'new model (factory) added with all known keys': any(e['file'] == 'factory_a.obj' and {'file','name','kind','class','lot','weight','height_m','scale','rotate_deg','style','enabled','notes'} <= set(e) for e in saved['models']),
  'multi-edit applied to 2 models': sum(1 for e in saved['models'] if e.get('class') == 3500 and e.get('notes') == 'edited in selftest') == 2,
  'second save identical to first': res['stable'],
}
for k, v in checks.items(): print(('PASS ' if v else 'FAIL ') + k)
print(json.dumps(res))
sys.exit(0 if all(checks.values()) else 1)
