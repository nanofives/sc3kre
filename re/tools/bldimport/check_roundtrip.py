"""Runs classifier.html?demo=1&selftest=1 in headless Chrome, reads the self-test result (DevTools) and checks the models.json round trip.
Usage: py -3.12 check_roundtrip.py   (needs Chrome; exit 0 = pass)"""
import json, os, re, subprocess, sys, tempfile, html, pathlib
here = pathlib.Path(__file__).resolve().parent
chrome = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
url = here.joinpath('classifier.html').as_uri() + '?demo=1&selftest=1'
# task sc4web: --dump-dom fires when the virtual-time budget runs out, often before the self-test has written its result
# (main's page failed 2 of 4 runs on 2026-11-19, and every run under the full suite's load). So the page is watched
# over the DevTools protocol until its title says "[selftest done]" (at most 180 s), as webtest/pagetest.mjs does. Chrome
# is stopped by the PID this script started. Without node: the old --dump-dom run.
CDP = r"""
import fs from 'node:fs';
const { startChrome } = await import(process.env.RT_HELPER);   // task suitespeed: webtest/chrome.mjs, one retry at start-up
const sleep = ms => new Promise(r => setTimeout(r, ms));
let out = '', stop = () => {}, prof = null;
try {
  const c = await startChrome(process.env.RT_CHROME, ['--headless=new', '--allow-file-access-from-files', '--enable-unsafe-swiftshader', '--use-angle=swiftshader',
    '--remote-debugging-port=0', '--no-first-run', '--no-default-browser-check'], process.env.RT_URL,
    { prefix: 'bcrt-', portMs: 30000, targetMs: 20000, findTarget: l => l.find(x => x.type === 'page' && x.url.startsWith('file:')), log: s => console.error(s) });
  ({ stop, prof } = c); const target = c.target;
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  let seq = 0; const waiters = new Map();
  ws.onmessage = ev => { const m = JSON.parse(ev.data); if (m.id && waiters.has(m.id)) { waiters.get(m.id)(m); waiters.delete(m.id); } };
  const evalJs = e => new Promise(res => { const id = ++seq; waiters.set(id, m => res(m.result && m.result.result && m.result.result.value)); ws.send(JSON.stringify({ id, method: 'Runtime.evaluate', params: { expression: e, returnByValue: true } })); });
  const t0 = Date.now();
  while (Date.now() - t0 < 180000 && !/selftest done/.test(await evalJs('document.title') || '')) await sleep(500);
  out = await evalJs("document.getElementById('selftest').textContent") || '';
  ws.close();
} finally { stop(); try { if (prof) fs.rmSync(prof, { recursive: true, force: true }); } catch (e) {} }
process.stdout.write(out);
"""
text = ''
try:
    text = subprocess.run(['node', '--input-type=module', '-e', CDP], capture_output=True, text=True, timeout=240,
                          env=dict(os.environ, RT_CHROME=chrome, RT_URL=url,
                                   RT_HELPER=here.joinpath('webtest', 'chrome.mjs').as_uri())).stdout.strip()
except (OSError, subprocess.TimeoutExpired) as e:
    print('node / DevTools route failed (%s): --dump-dom instead' % e)
    prof = tempfile.mkdtemp(prefix='bcrt')
    out = subprocess.run([chrome, '--headless=new', '--allow-file-access-from-files', '--enable-unsafe-swiftshader', '--use-angle=swiftshader',
                          '--user-data-dir=' + prof, '--virtual-time-budget=15000', '--dump-dom', url],
                         capture_output=True, text=True, timeout=120).stdout
    m = re.search(r'<pre id="selftest"[^>]*>(.*?)</pre>', out, re.S)
    text = html.unescape(m.group(1)).strip() if m else ''
if not text:
    print('FAIL: no selftest output'); sys.exit(1)
res = json.loads(text)
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
