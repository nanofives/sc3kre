// sc4_packs.mjs - task sc4pass2 (2026-11-19f): more SimCity 4 packs through the page's converter (sc4web.js)
// against the Python route (sc4conv.py, bldimport.py), byte for byte. Needs sc4_packs_setup.py's output.
//
//   node sc4_packs.mjs --golden <dir from sc4_packs_setup.py> --packs <folder with the SC4 .zip files> --game <tree> [--frames]
//
// Checks, one line each ([N/M] name PASS|FAIL):
//   exemplars  every exemplar of each pack (the text form EQZT too) read by sc4web.js = exemplar.py's reading
//   goc        the tower zip converted in JS: OBJ + MTL text byte for byte, its 4 tiled views pixel for pixel, models.json
//              byte for byte, the file list; the notes (its ploppable + landmark lots) = sc4conv.py's; class 6700, lot
//              4x4, 12 / 14 tiles; the folder route = the zip route; bldweb.buildFiles from memory = bldimport.py pack
//              (every game file, ids.json, --frames every frame)
//   diego, im  lot-only packs: nothing converted (no files, no models.json: sc4conv.py exits 3 and writes nothing),
//              the notes = sc4conv.py's (the buildings named, DiegoDL's readme dependency list, I-M's blank model),
//              the missing list = sc4conv.py's, and the folder route = the zip route
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { DirHandle } from './nodefs.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const req = createRequire(import.meta.url);
const B = req(path.join(here, '..', 'bldweb.js'));
const W = req(path.join(here, '..', 'sc4web.js'));
const arg = k => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : null; };
const golden = arg('golden'), packs = arg('packs'), gameDir = arg('game');
const wantFrames = process.argv.includes('--frames');
if (!golden || !packs || !gameDir) { console.log('usage: node sc4_packs.mjs --golden <dir> --packs <dir> --game <tree> [--frames]'); process.exit(2); }
const PACKS = { goc: 'Global Office Center.zip', diego: 'DiegoDLGrowablePack2019_Vanilla_DN.zip', im: 'I-M manufacturers lots.zip' };

function walk(d, base = d, out = []) {
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    const p = path.join(d, e.name);
    if (e.isDirectory()) walk(p, base, out); else out.push(path.relative(base, p).split(path.sep).join('/'));
  }
  return out;
}
const fileInputs = dir => walk(dir).map(rel => ({ path: rel, bytes: async () => new Uint8Array(fs.readFileSync(path.join(dir, ...rel.split('/')))) }));
const zipInputs = key => [{ path: PACKS[key], bytes: async () => new Uint8Array(fs.readFileSync(path.join(packs, PACKS[key]))) }];
const eqBytes = (a, b) => !!a && !!b && a.length === b.length && Buffer.compare(Buffer.from(a), Buffer.from(b)) === 0;
async function samePixels(a, b) {
  const x = await B.decodePNG(a), y = await B.decodePNG(b);
  if (x.w !== y.w || x.h !== y.h) return `size ${x.w}x${x.h} vs ${y.w}x${y.h}`;
  let d = 0;
  for (let k = 0; k < x.rgb.length; k++) if (x.rgb[k] !== y.rgb[k]) d++;
  const xa = x.a || new Uint8Array(x.w * x.h).fill(255), ya = y.a || new Uint8Array(y.w * y.h).fill(255);
  for (let k = 0; k < xa.length; k++) if (xa[k] !== ya[k]) d++;
  return d ? d + ' samples differ' : '';
}
const g = (key, ...p) => path.join(golden, key, ...p);
const readJson = p => JSON.parse(fs.readFileSync(p, 'utf8'));
const pyOut = g('goc', 'out'), outFiles = fs.existsSync(pyOut) ? walk(pyOut) : [];
let total = 3 + 9 + 2 + 1 + outFiles.length + (wantFrames ? 1 : 0) + 2 * 4, k = 0, bad = 0;
const line = (what, ok, extra = '') => { k++; bad += !ok; console.log(`[${k}/${total}] ${what} ${ok ? 'PASS' : 'FAIL'}${extra ? ' ' + extra : ''}`); };
const log = s => console.log('  ' + s);

// exemplars, every pack
for (const key of Object.keys(PACKS)) {
  const want = readJson(g(key, 'exemplars.json'));
  const idx = await W.buildIndex(await W.sourcesFrom(zipInputs(key)));
  const notes = []; let text = 0;
  const val = v => v instanceof W.PyFloat ? (isFinite(v.v) ? v.v : { f: String(v.v) }) : Array.isArray(v) ? v.map(val) : v;
  for (const e of want) {
    const t = e.tgi.map(h => parseInt(h, 16));
    let got;
    try { got = W.parseExemplar(idx.read(...t)); } catch (err) { if (!e.error) notes.push(e.tgi.join('-') + ': ' + err.message); continue; }
    if (e.error) { notes.push(e.tgi.join('-') + ': read in JS, ' + e.error + ' in Python'); continue; }
    if (e.form === 'EQZT') text++;
    const props = got.order.map(pid => [pid, got.props.get(pid)[0], val(got.props.get(pid)[1])]);
    if (JSON.stringify(props) !== JSON.stringify(e.props) || JSON.stringify(got.parent) !== JSON.stringify(e.parent) || got.kind !== e.kind)
      notes.push(e.tgi.join('-') + ' differs');
  }
  line(`exemplars of ${key} (${want.length}, ${text} text form) = exemplar.py`, !notes.length && want.length > 0, notes.slice(0, 4).join('; '));
}

// the tower
let t0 = Date.now();
const conv = await W.convert(await W.sourcesFrom(zipInputs('goc')), { log });
log(`tower zip converted in ${((Date.now() - t0) / 1000).toFixed(1)} s`);
const pyConv = g('goc', 'conv');
const pyModels = readJson(path.join(pyConv, 'models.json')).models;
{
  const m = pyModels[0] || {}, stem = (m.file || '').replace(/(_props)?(_lot)?\.obj$/i, ''), notes = [];   // task sc4lottex: the house's stem
  const exts = ['.obj', '.mtl'];
  for (const x of ['_props', '_lot', '_props_lot']) if (fs.existsSync(path.join(pyConv, stem + x + '.obj'))) exts.push(x + '.obj', x + '.mtl');   // task sc4lottex
  for (const ext of exts) if (!eqBytes(fs.readFileSync(path.join(pyConv, stem + ext)), conv.files.get(stem + ext))) notes.push(ext + ' differs');
  line(`tower ${m.file}: OBJ + MTL text`, pyModels.length === 3 && !notes.length, notes.join('; '));
  const pn = [];
  for (const v of ['S', 'W', 'N', 'E']) {
    const png = `${stem}_${v}.png`, js = conv.files.get(png);
    if (!js) { pn.push(png + ' missing'); continue; }
    const d = await samePixels(fs.readFileSync(path.join(pyConv, png)), js);
    if (d) pn.push(png + ': ' + d);
  }
  const sizes = [];
  for (const v of ['S', 'W', 'N', 'E']) { const js = conv.files.get(`${stem}_${v}.png`); if (js) { const im = await B.decodePNG(js); sizes.push(v + ' ' + im.w + 'x' + im.h); } }
  line(`tower: 4 composed view textures pixel for pixel (${sizes.join(', ')})`, !pn.length, pn.join('; '));
  line('tower models.json', eqBytes(fs.readFileSync(path.join(pyConv, 'models.json')), conv.files.get('models.json')), `${(conv.files.get('models.json') || []).length} bytes`);
  const js = new Set(conv.files.keys()), py = new Set(walk(pyConv));
  line(`tower file list (${js.size} files)`, js.size === py.size && [...js].every(f => py.has(f)));
  const cm = conv.models[0] || { x_sc4: {} }, x = cm.x_sc4 || {};
  const tiles = x.tiles ? ['S', 'W', 'N', 'E'].map(v => x.tiles[v]).join('/') : 'none';
  line(`tower class ${cm.class}, lot ${JSON.stringify(cm.lot)}, ${cm.height_m} m, tiles ${tiles}`, cm.class === 6700 && JSON.stringify(cm.lot) === '[4,4]' && tiles === '12/14/12/14' && cm.enabled === true);
  const vs = (x.versions || []).map(v => v.kind + ':' + v.lot);
  line(`tower ploppable + landmark versions named (${vs.join(', ')})`, vs.length === 2 && vs.includes('ploppable:Global Office Center Jobs') && vs.includes('landmark:Global Office Center Landmark'));
  // plop2 (2026-11-19): the two SC4 lot versions as SC3 landmark entries (kind landmark), each a byte copy of the OBJ
  const lms = conv.models.filter(mm => mm.kind === 'landmark');
  const lmDesc = lms.map(mm => `${mm.file} ${mm.x_sc4.version} ${JSON.stringify(mm.lot)} ${mm.enabled ? 'on' : 'off'}`).join(', ');
  const obj = conv.files.get(stem + '.obj');
  line(`tower landmark entries (${lmDesc})`, lms.length === 2 && lms.every(mm => mm.class === null && JSON.stringify(mm.lot) === '[4,4]' && mm.description === 'From SimCity 4' && eqBytes(conv.files.get(mm.file), obj)) &&
    lms.filter(mm => mm.enabled).map(mm => mm.x_sc4.version).join() === 'landmark' && lms.some(mm => mm.name === 'Global Office Center - Landmark'));
  const pn2 = readJson(g('goc', 'notes.json'));
  line('tower notes = sc4conv.py', JSON.stringify(conv.notes) === JSON.stringify(pn2.notes) && conv.notes.length === 1, conv.notes[0] ? conv.notes[0].slice(0, 100) : '');
  t0 = Date.now();
  const convF = await W.convert(await W.sourcesFrom(fileInputs(g('goc', 'src'))), {});
  const diff = [...conv.files.keys()].filter(f => !eqBytes(conv.files.get(f), convF.files.get(f)));
  line(`tower folder route = .zip route (${convF.files.size} files)`, !diff.length && convF.files.size === conv.files.size, diff.join(', '));
  // plop2: a rerun keeps the player's description and switch on a landmark entry (the page's edits, as models.json)
  const oldJ = JSON.parse(new TextDecoder().decode(conv.files.get('models.json')));
  const lmOld = oldJ.models.find(mm => mm.kind === 'landmark' && mm.x_sc4.version === 'ploppable');
  lmOld.description = 'Edited in the page'; lmOld.enabled = true;
  const convR = await W.convert(await W.sourcesFrom(zipInputs('goc')), { old: JSON.stringify(oldJ, null, 2) + '\n' });
  const lmNew = convR.models.find(mm => mm.kind === 'landmark' && mm.x_sc4.version === 'ploppable');
  line('tower rerun keeps a landmark entry\'s description + switch', !!lmNew && lmNew.description === 'Edited in the page' && lmNew.enabled === true &&
    eqBytes(fs.readFileSync(g('goc', 'rerun', 'models.json')), convR.files.get('models.json')), lmNew ? lmNew.description : 'missing');
  line(`tower sc4conv.py exit ${fs.readFileSync(g('goc', 'exit.txt'), 'utf8')}`, fs.readFileSync(g('goc', 'exit.txt'), 'utf8') === '0');
}
t0 = Date.now();
const folder = W.overlayFS(conv.files, null);
const game = B.handleFS(new DirHandle(gameDir));
const frames = new Map();
let files = new Map(), rep = [];
try {
  [files, rep] = await B.buildFiles(folder, game, new Map(), { onFrames: (e, fr) => frames.set(e.model.file, fr) });
} catch (e) { console.log('  ERROR ' + (e.stack || e)); }
log(`tower rendered + packed in ${((Date.now() - t0) / 1000).toFixed(1)} s`);
for (const r of rep) log('  ' + r);
for (const rel of outFiles) {
  const a = fs.readFileSync(path.join(pyOut, rel)), b = files.get(rel);
  line('tower pack ' + rel, eqBytes(a, b), b ? `${b.length} bytes` : 'not written');
}
line('tower pack sc3build/ids.json', eqBytes(fs.readFileSync(g('goc', 'folder', 'sc3build', 'ids.json')), folder.written.get('sc3build/ids.json')));
if (wantFrames) {
  let nb = 0, n = 0, tall = 0; const notes = [];
  for (const [file, fr] of frames) {
    const stem = file.replace(/\.[^.]+$/, '');
    for (const [key, [im]] of fr) {
      const [z, r] = key.split(',');
      n++;
      tall = Math.max(tall, im.h);
      const py = await B.decodePNG(fs.readFileSync(g('goc', 'folder', 'sc3build', stem, `z${z}_r${r}.png`)));
      let diff = 0;
      if (py.w !== im.w || py.h !== im.h) diff = -1;
      else for (let q = 0; q < im.w * im.h; q++) {
        if ((py.a ? py.a[q] : 255) !== im.d[4 * q + 3]) { diff++; continue; }
        for (let ch = 0; ch < 3; ch++) if (py.rgb[3 * q + ch] !== im.d[4 * q + ch]) { diff++; break; }
      }
      if (diff) { nb++; if (notes.length < 8) notes.push(`${stem} z${z}r${r}: ${diff < 0 ? 'size' : diff + ' px'}`); }
    }
  }
  line(`tower frames vs python cache (${n}, RGBA, tallest ${tall} px)`, nb === 0 && n > 0, nb ? `${nb} differ: ${notes.join('; ')}` : '');
}

// lot-only packs
for (const key of ['diego', 'im']) {
  const r = await W.convert(await W.sourcesFrom(zipInputs(key)), {});
  const pn = readJson(g(key, 'notes.json')), code = fs.readFileSync(g(key, 'exit.txt'), 'utf8');
  line(`${key}: nothing converted (${r.files.size} files, ${r.models.length} models; sc4conv.py exit ${code}, ${fs.existsSync(g(key, 'conv')) ? 'wrote ' + walk(g(key, 'conv')).length + ' files' : 'wrote nothing'})`,
    r.empty === true && r.files.size === 0 && r.models.length === 0 && code === '3' && !fs.existsSync(g(key, 'conv')));
  line(`${key}: notes = sc4conv.py (${r.notes.length} lines)`, JSON.stringify(r.notes) === JSON.stringify(pn.notes) && /^No building converted: /.test(r.notes[0] || ''), (r.notes[1] || '').slice(0, 140));
  line(`${key}: buildings without a model = sc4conv.py (${r.missing.length}: ${r.missing.slice(0, 3).map(m => m.name).join(', ')}...)`, JSON.stringify(r.missing) === JSON.stringify(pn.missing) && r.missing.length > 0);
  const rf = await W.convert(await W.sourcesFrom(fileInputs(g(key, 'src'))), {});
  line(`${key}: folder route = .zip route`, JSON.stringify(rf.notes) === JSON.stringify(r.notes) && JSON.stringify(rf.missing) === JSON.stringify(r.missing) && rf.files.size === 0);
}
console.log(`${total - bad} of ${total} passed`);
process.exit(bad ? 1 : 0);
