// sc3pack_pagetest.mjs - task sc3compat-b (2026-11-19e): sc3pack.js in headless Chrome (sc3pack_view.html, file://).
//
//   node sc3pack_pagetest.mjs --golden <work>\sc3pack --game <pristine game tree> [--show bld_parts.zip] [--shots <dir>]
//
// The page opens every pack of packs.json as the player gives it (a .zip, a folder's File list; Chrome's own
// DecompressionStream), reports with the game folder and compares with sc3pack.py's report_<k>.json; then it draws
// SC3PACK.view of one pack and clicks Install with one overwrite ticked and one kind picked. --shots writes a phone
// (412 px) and a desktop (1280 px) screenshot. Chrome is stopped by the PID this script started.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn, execFileSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { startChrome } from './chrome.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const arg = (k, d = null) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const golden = arg('golden'), tree = arg('game'), show = arg('show', 'bld_parts.zip'), shots = arg('shots', golden && path.join(golden, 'shots'));
const chrome = arg('chrome', 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe');
function walk(d, base = d, out = []) {
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    const p = path.join(d, e.name);
    if (e.isDirectory()) walk(p, base, out); else out.push(path.relative(base, p).split(path.sep).join('/'));
  }
  return out.sort();
}
const dirUrl = d => pathToFileURL(d).href.replace(/\/?$/, '/');
const packs = JSON.parse(fs.readFileSync(path.join(golden, 'packs.json'), 'utf8'));
const man = {
  show,
  game: { base: dirUrl(tree), files: ['Apps/Res/BA', 'Apps/BACustom'].flatMap(r => walk(path.join(tree, ...r.split('/'))).map(x => r + '/' + x)) },
  packs: packs.map((p, k) => {
    const want = pathToFileURL(path.join(golden, `report_${k}.json`)).href;
    if (fs.statSync(p).isDirectory()) return { name: path.basename(p), base: dirUrl(p), files: walk(p), want };
    return { name: path.basename(p), base: dirUrl(path.dirname(p)), zip: path.basename(p), want };
  }),
};
const manPath = path.join(golden, 'sc3pack_pagetest.json');
fs.writeFileSync(manPath, JSON.stringify(man));
const page = pathToFileURL(path.join(here, 'sc3pack_view.html')).href + '?t=' + encodeURIComponent(pathToFileURL(manPath).href);
const CHROME_FLAGS = ['--headless=new', '--window-size=1280,1100', '--allow-file-access-from-files', '--remote-debugging-port=0',
  '--no-first-run', '--no-default-browser-check'];
let prof = null, ch = { pid: 0 }, stop = () => {};   // suitespeed: started in try (chrome.mjs, one retry)
const sleep = ms => new Promise(r => setTimeout(r, ms));
let total = packs.length + 3, k = 0, bad = 0;
const line = (what, ok, extra = '') => { k++; bad += !ok; console.log(`[${k}/${total}] ${what} ${ok ? 'PASS' : 'FAIL'}${extra ? ' ' + extra : ''}`); };
try {
  const c = await startChrome(chrome, CHROME_FLAGS, page, { prefix: 'sc3pack-chrome-', findTarget: l => l.find(x => x.type === 'page' && x.url.startsWith('file:')) });
  ({ ch, prof, stop } = c); const port = c.port, target = c.target;
  console.log(`chrome pid ${ch.pid}, page ${page.slice(0, 120)}...`);
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  let seq = 0; const waiters = new Map();
  ws.onmessage = ev => { const m = JSON.parse(ev.data); if (m.id && waiters.has(m.id)) { waiters.get(m.id)(m); waiters.delete(m.id); } };
  const send = (method, params = {}) => new Promise(res => { const id = ++seq; waiters.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
  const evalJs = async expr => { const m = await send('Runtime.evaluate', { expression: expr, returnByValue: true }); return m.result && m.result.result && m.result.result.value; };
  const t0 = Date.now();
  while (Date.now() - t0 < 300000 && await evalJs('document.title') !== 'sc3pack done') await sleep(500);
  const res = JSON.parse(await evalJs("document.getElementById('result').textContent") || '{}');
  if (!res.pass) { total = 1; line('page ran', false, res.error || 'timeout'); }
  else {
    for (const c of res.checks) line(`${c.name} in Chrome: report = sc3pack.py`, c.ok, `(${c.files} files, ${c.seconds.toFixed(1)} s)`);
    const v = res.view;
    line(`view of ${show}: ${v.groups} groups, ${v.missingRows} missing row(s), ${v.checkboxes} overwrite box(es), ${v.selects} kind pick(s)`,
      v.groups > 3 && v.missingRows >= 1 && v.checkboxes >= 1 && v.selects >= 1, JSON.stringify(v.buttons));
    line('Install click passes the ticked overwrite and the picked kind', JSON.stringify(res.click) === JSON.stringify({ ow: ['Mariners 04.tga'], kinds: { 'sc3pt loose.tga': 'detail' } }), JSON.stringify(res.click));
    let wide = false;
    if (shots) {
      fs.mkdirSync(shots, { recursive: true });
      await evalJs("document.querySelectorAll('details').forEach(d => d.open = true); 1");
      for (const [w, h, name] of [[412, 915, 'phone'], [1280, 1100, 'desktop']]) {
        await send('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: w < 600 ? 2 : 1, mobile: w < 600 });
        await sleep(300);
        if (w < 600) wide = await evalJs('document.documentElement.scrollWidth > document.documentElement.clientWidth');
        const m = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true, clip: { x: 0, y: 0, width: w, height: Math.min(await evalJs('document.documentElement.scrollHeight'), 2400), scale: 1 } });
        fs.writeFileSync(path.join(shots, `sc3pack_view_${name}.png`), Buffer.from(m.result.data, 'base64'));
      }
      console.log('  screenshots in ' + shots);
    }
    line('no horizontal page scroll at phone width (412 px)', !wide);
    // the hook in the importer itself (classifier.html): Open SC3 pack on the same .zip, then its buildings in the grid
    await send('Emulation.clearDeviceMetricsOverride');
    const sp = man.packs.find(p => p.name === show);
    await send('Page.navigate', { url: pathToFileURL(path.join(here, '..', 'classifier.html')).href });
    const t1 = Date.now();
    while (Date.now() - t1 < 60000 && !(await evalJs('!!(window.bc && window.bc.openPack && document.readyState === "complete")'))) await sleep(300);
    const m = await send('Runtime.evaluate', { awaitPromise: true, returnByValue: true, expression: `(async () => {
      const url = ${JSON.stringify(sp.base + encodeURIComponent(sp.zip || ''))};
      const f = new File([await (await fetch(url)).arrayBuffer()], ${JSON.stringify(sp.zip || '')});
      const rep = await window.bc.openPack(await window.bc.PK.openFiles([f]), f.name);
      const v = document.getElementById('packView');
      const out = { shown: !document.getElementById('packBox').hidden, counts: rep.counts, groups: v.querySelectorAll('details').length,
        hint: document.getElementById('packHint').textContent, status: document.getElementById('status').textContent,
        bldBtn: document.getElementById('btnPackBld').textContent };
      document.getElementById('btnPackBld').click();
      for (let t = 0; t < 100 && window.bc.S.recs.length < 1; t++) await new Promise(r => setTimeout(r, 100));
      out.recs = window.bc.S.recs.map(r => r.file || (r.meta && r.meta.file) || '');
      return JSON.stringify(out); })()` });
    const hk = JSON.parse((m.result && m.result.result && m.result.result.value) || '{}');
    total += 2;
    line(`classifier.html: Open SC3 pack shows ${show} (${JSON.stringify(hk.counts)}, ${hk.groups} groups)`, hk.shown && hk.groups > 3 && /Choose the Game folder/.test(hk.hint || ''), hk.status);
    line(`classifier.html: "${hk.bldBtn}" puts them in the grid (${(hk.recs || []).length})`, (hk.recs || []).length === (hk.counts && hk.counts.building), JSON.stringify(hk.recs));
    if (shots) {
      await evalJs("document.getElementById('packBox').scrollIntoView(); document.querySelectorAll('#packView details').forEach(d => d.open = false); 1");
      await sleep(300);
      const sm = await send('Page.captureScreenshot', { format: 'png' });
      fs.writeFileSync(path.join(shots, 'sc3pack_classifier.png'), Buffer.from(sm.result.data, 'base64'));
    }
  }
  ws.close();
} catch (e) { total = total || 1; line('pagetest', false, String(e.stack || e)); }
finally { stop(); try { if (prof) fs.rmSync(prof, { recursive: true, force: true }); } catch (e) { /* locked files of a closing chrome */ } }
console.log(`${k - bad} of ${k} passed`);
process.exit(bad ? 1 : 0);
