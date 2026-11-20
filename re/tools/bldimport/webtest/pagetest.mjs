// pagetest.mjs - task bldweb (2026-11-18d): the page itself (classifier.html, file://, Web Worker) in headless Chrome.
//
//   node pagetest.mjs --golden <dir from golden_setup.py> --game <tree> [--case kenney] [--chrome <exe>]
//   node pagetest.mjs --golden <dir> --game <tree> --case sc4 --sc4zip <SC4 download .zip>   (task sc4web: the page
//        opens the .zip itself, as Open SC4 .zip does, converts it and installs from memory)
//   node pagetest.mjs --golden <dir> --game <tree> --case sc4empty --action open --sc4zip <lot-only SC4 .zip> --expect-empty "<name>,<name>"
//        (task sc4pass2: a download without building models: no cards, Install off, the note names the buildings)
//   node pagetest.mjs --golden <sc4_props_setup.py dir> --game <tree> --case sc4props --sc4zip <JMyers .zip> --sc4deps <BSC zip>
//        (task sc4props: both picked in Open SC4 .zip, the 1.7 GB pack streamed by the page, props baked, installed)
//   node pagetest.mjs --golden <dir> --game <tree> --case landmarkdesc --edit-desc "<file>=<text>"
//        (plop2: the entry's description blanked, typed into the panel's Description box, installed from the page's own
//        models.json; the outputs, ids.json included, must equal bldimport.py's on golden_setup case landmarkdesc)
//
// Opens classifier.html?bldtest=<manifest> from disk in a headless Chrome of its own (temporary profile,
// --allow-file-access-from-files so the test hook can fetch the folders), waits for the hook (webtest/pagetest.js)
// to run the page's Install path (window.bc.installWith, worker renderer), then compares the sha256 of every file
// the page wrote with bldimport.py's output for the same case. Chrome is stopped by the PID this script started.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawn, execFileSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const arg = (k, d = null) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const golden = arg('golden'), tree = arg('game'), cs = arg('case', 'kenney');
const modelsDir = arg('models', golden && path.join(golden, 'src', cs)), action = arg('action', 'install');
const apply = process.argv.includes('--apply'), compare = !process.argv.includes('--no-compare'), shot = arg('shot');
const sc4inst = arg('sc4install');         // task sc4civ: the player's SimCity 4 folder: its game .dat files are picked
const INSTALL = ['SimCity_1.dat', 'SimCity_2.dat', 'SimCity_3.dat', 'SimCity_4.dat', 'SimCity_5.dat', 'EP1.dat', 'SimCityLocale.DAT'];
const sc4zip = arg('sc4zip') || (sc4inst ? path.join(sc4inst, INSTALL[0]) : null);
const editArg = arg('edit-desc');           // plop2: "<file>=<text>"
const sc4deps = arg('sc4deps');           // task sc4props: a dependency pack picked with the download (the BSC zip)
const chrome = arg('chrome', 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe');
function walk(d, base = d, out = []) {
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    const p = path.join(d, e.name);
    if (e.isDirectory()) walk(p, base, out); else out.push(path.relative(base, p).split(path.sep).join('/'));
  }
  return out.sort();
}
const sha = b => crypto.createHash('sha256').update(b).digest('hex');
const dirUrl = d => pathToFileURL(d).href.replace(/\/?$/, '/');
const man = { models: { base: dirUrl(modelsDir), files: sc4zip ? [] : walk(modelsDir) }, game: { base: dirUrl(tree), files: walk(tree) }, action, apply,
  sc4: sc4zip ? { base: dirUrl(path.dirname(path.resolve(sc4zip))), files: sc4inst ? INSTALL.filter(f => fs.existsSync(path.join(sc4inst, f))) : [path.basename(sc4zip)],
    deps: sc4deps ? [{ base: dirUrl(path.dirname(path.resolve(sc4deps))), file: path.basename(sc4deps) }] : [] } : null,
  editDesc: editArg ? { file: editArg.slice(0, editArg.indexOf('=')), text: editArg.slice(editArg.indexOf('=') + 1) } : null };
const manPath = path.join(golden || os.tmpdir(), `pagetest_${cs}_${action}.json`);
fs.writeFileSync(manPath, JSON.stringify(man));
const page = pathToFileURL(path.join(here, '..', 'classifier.html')).href + '?bldtest=' + encodeURIComponent(pathToFileURL(manPath).href) + (arg('wait') ? '&wait=' + arg('wait') : '');
const prof = fs.mkdtempSync(path.join(os.tmpdir(), 'bldweb-chrome-'));
const ch = spawn(chrome, ['--headless=new', '--window-size=1280,1100', '--allow-file-access-from-files', '--remote-debugging-port=0', '--user-data-dir=' + prof,
  '--no-first-run', '--no-default-browser-check', '--enable-unsafe-swiftshader', '--use-angle=swiftshader', page], { stdio: 'ignore' });
console.log(`chrome pid ${ch.pid}, page ${page.slice(0, 120)}...`);
const stop = () => { try { execFileSync('taskkill', ['/PID', String(ch.pid), '/T', '/F'], { stdio: 'ignore' }); } catch (e) { /* already gone */ } };
const sleep = ms => new Promise(r => setTimeout(r, ms));
let total = 0, k = 0, bad = 0;
const line = (what, ok, extra = '') => { k++; bad += !ok; console.log(`[${k}/${total}] ${what} ${ok ? 'PASS' : 'FAIL'}${extra ? ' ' + extra : ''}`); };
try {
  let port = null;
  for (let t = 0; t < 100 && !port; t++) { await sleep(200); const f = path.join(prof, 'DevToolsActivePort'); if (fs.existsSync(f)) port = fs.readFileSync(f, 'utf8').split('\n')[0].trim(); }
  if (!port) throw new Error('chrome did not open a debugging port');
  let target = null;
  for (let t = 0; t < 50 && !target; t++) { await sleep(200); const l = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json(); target = l.find(x => x.type === 'page' && x.url.startsWith('file:')); }
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  let seq = 0; const waiters = new Map();
  ws.onmessage = ev => { const m = JSON.parse(ev.data); if (m.id && waiters.has(m.id)) { waiters.get(m.id)(m); waiters.delete(m.id); } };
  const evalJs = expr => new Promise(res => { const id = ++seq; waiters.set(id, m => res(m.result && m.result.result && m.result.result.value)); ws.send(JSON.stringify({ id, method: 'Runtime.evaluate', params: { expression: expr, returnByValue: true } })); });
  const t0 = Date.now(); let title = '';
  while (Date.now() - t0 < 900000) {
    title = await evalJs('document.title');
    if (/bldtest done/.test(title || '')) break;
    const prog = await evalJs("(document.getElementById('progText')||{}).textContent");
    if (prog) process.stdout.write(`\r  page: ${prog.slice(0, 100).padEnd(100)}`);
    await sleep(1000);
  }
  process.stdout.write('\n');
  const res = JSON.parse(await evalJs("document.getElementById('bldtest').textContent") || '{}');
  if (shot) {
    await evalJs(action === 'open' ? "document.getElementById('gameBox').hidden = true; window.scrollTo(0, 0); 1" : "document.getElementById('logBox').open = true; window.scrollTo(0, 0); 1");
    const id = ++seq;
    const img = await new Promise(r => { waiters.set(id, m => r(m.result && m.result.data)); ws.send(JSON.stringify({ id, method: 'Page.captureScreenshot', params: { format: 'jpeg', quality: 85, captureBeyondViewport: false } })); });
    if (img) { fs.writeFileSync(shot, Buffer.from(img, 'base64')); console.log('  screenshot ' + shot); }
  }
  ws.close();
  if (res.pass && apply) {
    // write what the page wrote: game files and removals into the tree, ids.json into the models folder; temp +
    // rename, never through a hard link (dev trees are hard-linked)
    const put = (root, rel, b64) => { const p = path.join(root, ...rel.split('/')); fs.mkdirSync(path.dirname(p), { recursive: true }); fs.writeFileSync(p + '.bldweb-tmp', Buffer.from(b64, 'base64')); fs.renameSync(p + '.bldweb-tmp', p); };
    for (const [rel, f] of Object.entries(res.files)) put(tree, rel, f.b64);
    for (const [rel, f] of Object.entries(res.models)) put(modelsDir, rel, f.b64);
    for (const rel of res.deleted) fs.rmSync(path.join(tree, ...rel.split('/')), { force: true });
    console.log(`  applied: ${Object.keys(res.files).length} game files written, ${res.deleted.length} removed, ${Object.keys(res.models).length} models-folder files`);
  }
  const expectEmpty = arg('expect-empty');  // task sc4pass2: a lot-only SC4 zip: comma list of names the note must hold
  if (res.pass && expectEmpty !== null) {
    const s4 = res.sc4 || {}, names = expectEmpty.split(',').filter(Boolean);
    total = 4;
    console.log('  note: ' + (s4.note || '').slice(0, 400));
    console.log('  status: ' + (s4.status || ''));
    line(`page: no cards, nothing to install (${s4.cards} cards, buttons ${JSON.stringify(s4.buttons)})`, res.empty === true && s4.cards === 0 && s4.recs === 0 && !!s4.buttons && s4.buttons.btnInstall && s4.buttons.btnZipInstall && s4.buttons.btnSave);
    line('page note says plainly that nothing converts', !!s4.noteShown && /No building converted: this download holds no building models/.test(s4.note || '') && /nothing can be installed from it/.test(s4.note || '') && !/One colour of each straight design/.test(s4.note || ''));
    const miss = names.filter(n => !(s4.note || '').includes(n));
    line(`page note names the missing buildings (${names.length} checked)`, !miss.length, miss.slice(0, 5).join(', '));
    line('page status line says it cannot be converted', /^No building in .* can be converted: it holds no building models/.test(s4.status || ''), s4.status);
  }
  else if (res.pass && sc4inst) {           // task sc4civ: the page on the SC4 install's .dat files (Open SC4 .zip route)
    const s4 = res.sc4 || {}, want = arg('expect-install', '').split(',').map(Number);   // <cards>,<on>
    total = 4;
    console.log('  note: ' + (s4.note || '').slice(0, 300));
    console.log('  status: ' + (s4.status || '') + '  kinds: ' + JSON.stringify(s4.kinds) + '  in ' + (s4.seconds || 0).toFixed(1) + ' s');
    line(`page: ${s4.cards} cards, ${s4.enabled} on (expected ${want.join(' / ')}), no card error`, s4.cards === want[0] && s4.enabled === want[1] && !(s4.errors || []).length, (s4.errors || []).join('; '));
    line('page note: the install line, the EA rule, no download wording', !!s4.noteShown && /(^|\. )SimCity 4 install: \d+ of its/.test(s4.note || '') && /EA's buildings from your own copy of SimCity 4/.test(s4.note || '') && !/One colour of each straight design/.test(s4.note || ''));
    line('page keeps the install read only (no folder handle, named "your SimCity 4 game")', s4.install === true && s4.dirHandle === false && s4.folderName === 'your SimCity 4 game');
    line(`page: kinds civic / reward / landmark, the Mayor's House a reward at population 500 (${JSON.stringify(s4.mayor)})`, !!s4.mayor && s4.mayor.kind === 'reward' && s4.mayor.population === 500 && s4.mayor.year === 0 &&
      (s4.kinds['civic:police'] || 0) >= 1 && (s4.kinds.landmark || 0) >= 1 && (s4.kinds.reward || 0) >= 1 && Object.keys(s4.kinds).every(k => /^(civic:|reward$|landmark$)/.test(k)));
  }
  else if (!res.pass) { total = 1; line('page ' + action + ' ran', false, res.error || title); }
  else if (!compare) { total = 1; if (res.meshes) console.log('  ' + JSON.stringify({ focus: res.focus, err: res.err, meshes: res.meshes, thumb: res.thumb, side: res.side, recs: res.recs, status: res.status })); console.log('  ' + res.rep.join('\n  ')); line(`page ${action} ran (${res.seconds.toFixed(1)} s, renderer ${res.worker})`, true); }
  else {
    const pyOut = path.join(golden, 'py', cs, 'out');
    const want = walk(pyOut);
    total = want.length + 4 + (res.sc4 ? 3 : 0) + (man.editDesc ? 3 : 0);
    if (man.editDesc) {
      const e = res.editDesc || {}, t = man.editDesc.text;
      console.log('  editDesc: ' + JSON.stringify(e));
      line('Description box hidden for a card that is not a landmark, civic look or reward', !!e.hiddenFor && e.hiddenFor[2] === true, e.hiddenFor && e.hiddenFor.join(' '));
      line('Description box shown for the landmark, empty after the blanking (and no description key written then)', e.shown === true && e.boxBefore === '' && e.blankSaved === false);
      line(`typed description reaches models.json ("${t}")`, e.saved === t && e.meta === t, String(e.saved));
    }
    if (res.sc4) {
      const s4 = res.sc4, pm = JSON.parse(fs.readFileSync(path.join(golden, 'src', cs, 'models.json'), 'utf8')).models;
      const designs = new Set(pm.map(m => m.x_sc4 && m.x_sc4.design)).size;
      console.log(`  page SC4: converted + grid in ${s4.seconds.toFixed(1)} s. ${s4.status}`);
      line(`page grid: ${s4.cards} SC4 cards, ${s4.enabled} on, ${s4.groups} design groups`, s4.recs === pm.length && s4.cards === pm.length && s4.enabled === pm.filter(m => m.enabled).length && s4.groups === designs && !s4.errors.length, s4.errors.join('; '));
      const pd = pm.filter(m => m.x_sc4 && m.x_sc4.diagonal).map(m => m.file).sort();
      line(`page marks the ${s4.diag} diagonal cards (badge + reason)`, JSON.stringify([...s4.diagFiles].sort()) === JSON.stringify(pd) && /45 degrees/.test(s4.diagTitle), s4.diagTitle.slice(0, 120));
      line('page shows the SC4 licence rule', /never share the converted buildings without the author's permission/.test(s4.note), s4.note.slice(0, 140));
    }
    console.log(`  page: ${res.seconds.toFixed(1)} s, renderer ${res.worker}, ${res.resultRows} result rows, "${res.progressShown}"`);
    for (const rel of want) {
      const got = res.files[rel], exp = sha(fs.readFileSync(path.join(pyOut, rel)));
      line(rel, !!got && got.sha === exp, got ? `${got.size} bytes` : 'not written');
    }
    const ids = res.models['sc3build/ids.json'], idsExp = sha(fs.readFileSync(path.join(golden, 'py', cs, 'folder', 'sc3build', 'ids.json')));
    line('sc3build/ids.json', !!ids && ids.sha === idsExp);
    const st = res.files['mods/netmod/bldimport/state.json'];
    line('state.json written', !!st);
    const backups = Object.keys(res.files).filter(p => p.startsWith('mods/netmod/bldimport/backup/'));
    // task plop: count the output files the game already had (the B1D10001 DAT and the landmark plugin are new files)
    const existed = want.filter(r => fs.existsSync(path.join(tree, ...r.split('/')))).length;
    line(`backups of the ${existed} files that existed (${backups.length})`, backups.length === existed);
    line('rendered in a Web Worker', /^worker/.test(res.worker || ''), res.worker);
  }
} catch (e) { total = total || 1; line('pagetest', false, String(e.stack || e)); }
finally { stop(); try { fs.rmSync(prof, { recursive: true, force: true }); } catch (e) { /* locked files of a closing chrome */ } }
console.log(`${total - bad} of ${total} passed`);
process.exit(bad ? 1 : 0);
