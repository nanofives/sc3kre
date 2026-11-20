// sc4_lottex.mjs - task sc4lottex (2026-11-20): SC4 lot textures drawn on the ground under the converted building,
// sc4web.js against sc4conv.py (golden from sc4_lottex_setup.py), byte for byte.
//
//   node sc4_lottex.mjs --golden <dir from sc4_lottex_setup.py> --game <tree> --zip <the JMyers .zip> --deps <BSC zip>
//        --install <SimCity 4 folder> [--frames]
//
// The BSC zip and the install's 7 game files are given as the page gets them from a file picker (size, slices, a stream).
// Checks, one line each:
//   1. per source set (the download alone, + the BSC pack, + the install, both): the report lines "Lot props", "Lot
//      textures", "Textures not found" = sc4conv.py; with both, every file of the conversion byte for byte (text) or
//      pixel for pixel (PNG, the <stem>_lot.png canvases among them) and the file list
//   2. --no-textures (opt.noTextures): models.json = sc4conv.py --no-textures
//   3. the rerun keeps the player's two switches (models.json = sc4conv.py rerun; files <stem>_props.obj and <stem>_lot.obj)
//   4. bldweb.buildFiles over the rerun = `bldimport.py pack` of the Python rerun: every game file, ids.json, --frames
//      every frame (one building drawn without its ground art, one with it and no props)
import fs from 'node:fs';
import path from 'node:path';
import { Readable } from 'node:stream';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { DirHandle } from './nodefs.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const req = createRequire(import.meta.url);
const B = req(path.join(here, '..', 'bldweb.js'));
const W = req(path.join(here, '..', 'sc4web.js'));
const arg = k => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : null; };
const golden = arg('golden'), gameDir = arg('game'), zipPath = arg('zip'), depsPath = arg('deps'), instDir = arg('install');
const wantFrames = process.argv.includes('--frames');
if (!golden || !gameDir || !zipPath || !depsPath || !instDir) { console.log('usage: node sc4_lottex.mjs --golden <dir> --game <tree> --zip <JMyers zip> --deps <BSC zip> --install <SimCity 4 folder> [--frames]'); process.exit(2); }

function walk(d, base = d, out = []) {
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    const p = path.join(d, e.name);
    if (e.isDirectory()) walk(p, base, out); else out.push(path.relative(base, p).split(path.sep).join('/'));
  }
  return out;
}
const eqBytes = (a, b) => !!a && !!b && a.length === b.length && Buffer.compare(Buffer.from(a), Buffer.from(b)) === 0;
async function samePixels(a, b) {
  const x = await B.decodePNG(a), y = b instanceof Uint8Array ? await B.decodePNG(b) : null;
  if (!y) return 'not a PNG';
  if (x.w !== y.w || x.h !== y.h) return `size ${x.w}x${x.h} vs ${y.w}x${y.h}`;
  let d = 0;
  for (let k = 0; k < x.rgb.length; k++) if (x.rgb[k] !== y.rgb[k]) d++;
  const xa = x.a || new Uint8Array(x.w * x.h).fill(255), ya = y.a || new Uint8Array(y.w * y.h).fill(255);
  for (let k = 0; k < xa.length; k++) if (xa[k] !== ya[k]) d++;
  return d ? d + ' samples differ' : '';
}
function fileInput(p, rel, big = 200 << 20) {
  const st = fs.statSync(p), fd = fs.openSync(p, 'r');
  return { path: rel, size: st.size, mtime: Math.floor(st.mtimeMs),
    bytes: async () => { if (st.size >= big) throw new Error(rel + ' must not be read whole'); return new Uint8Array(fs.readFileSync(p)); },
    slice: async (a, b) => { const buf = Buffer.alloc(b - a); fs.readSync(fd, buf, 0, b - a, a); return new Uint8Array(buf.buffer, buf.byteOffset, buf.length); },
    stream: (a, b) => Readable.toWeb(fs.createReadStream(p, { start: a, end: b - 1, highWaterMark: 1 << 22 })) };
}
const INSTALL = ['SimCity_1.dat', 'SimCity_2.dat', 'SimCity_3.dat', 'SimCity_4.dat', 'SimCity_5.dat', 'EP1.dat', 'SimCityLocale.DAT'];
const instInputs = () => INSTALL.filter(f => fs.existsSync(path.join(instDir, f))).map(f => fileInput(path.join(instDir, f), f, 16 << 20));
const zipInput = () => ({ path: path.basename(zipPath), bytes: async () => new Uint8Array(fs.readFileSync(zipPath)) });
const deps = fileInput(depsPath, path.basename(depsPath));
const KEEP = /^(Lot props|Lot textures|Textures not found)/;
const counts = JSON.parse(fs.readFileSync(path.join(golden, 'counts.json'), 'utf8'));
const pyOut = path.join(golden, 'py', 'rerun', 'out'), outFiles = walk(pyOut);
const total = 4 + 3 + 1 + 3 + outFiles.length + 1 + (wantFrames ? 1 : 0);
let k = 0, bad = 0;
const line = (what, ok, extra = '') => { k++; bad += !ok; console.log(`[${k}/${total}] ${what} ${ok ? 'PASS' : 'FAIL'}${extra ? ' ' + extra : ''}`); };
const inputs = { dl: () => [zipInput()], bsc: () => [zipInput(), deps], inst: () => [zipInput()].concat(instInputs()), both: () => [zipInput(), deps].concat(instInputs()) };

// 1. the four source sets
let both = null;
for (const [cs, mk] of Object.entries(inputs)) {
  const t0 = Date.now();
  const r = await W.convert(await W.sourcesFrom(mk()), { log: () => {} });
  const js = r.report.filter(l => KEEP.test(l)), py = counts[cs];
  const tl = js.find(l => /^Lot textures/.test(l)) || '';
  line(`${cs}: report lines = sc4conv.py (${((Date.now() - t0) / 1000).toFixed(1)} s)`, JSON.stringify(js) === JSON.stringify(py), tl.slice(0, 150));
  if (cs === 'both') both = r;
}
{
  const pyConv = path.join(golden, 'src', 'both'), pyFiles = walk(pyConv), diff = [], pix = [];
  for (const rel of pyFiles) {
    const js = both.files.get(rel);
    if (!js) { diff.push(rel + ' missing'); continue; }
    if (rel.endsWith('.png')) { const d = await samePixels(fs.readFileSync(path.join(pyConv, rel)), js); if (d) pix.push(rel + ': ' + d); }
    else if (!eqBytes(fs.readFileSync(path.join(pyConv, rel)), js)) diff.push(rel + ' differs');
  }
  const nText = pyFiles.filter(f => !f.endsWith('.png')).length, nLot = pyFiles.filter(f => /_lot\.(obj|png)$/.test(f)).length;
  line(`both: ${nText} OBJ / MTL / models.json files byte for byte (${nLot} _lot OBJ + PNG among the files)`, !diff.length && nLot > 0, diff.slice(0, 6).join('; '));
  line(`both: ${pyFiles.length - nText} PNG pixel for pixel (the <stem>_lot.png canvases among them)`, !pix.length, pix.slice(0, 6).join('; '));
  const js = new Set(both.files.keys());
  line(`both: file list (${js.size} files)`, js.size === pyFiles.length && pyFiles.every(f => js.has(f)));
}
// 2. --no-textures
{
  const r = await W.convert(await W.sourcesFrom(inputs.both()), { noTextures: true, log: () => {} });
  const ms = r.models.filter(m => m.x_sc4.textures);
  line(`--no-textures route (models.json vs sc4conv.py --no-textures; ${ms.length} with texture rows, all off)`, eqBytes(fs.readFileSync(path.join(golden, 'notex', 'models.json')), r.files.get('models.json')) &&
    ms.length > 0 && ms.every(m => !m.x_sc4.textures.on && !/_lot\.obj$/.test(m.file)));
}
// 3. the rerun
let rerun = null;
{
  const old = fs.readFileSync(path.join(golden, 'rerun_old.json'), 'utf8');
  rerun = await W.convert(await W.sourcesFrom(inputs.both()), { old, log: () => {} });
  line('rerun keeps the two switches (models.json vs sc4conv.py rerun)', eqBytes(fs.readFileSync(path.join(golden, 'rerun', 'models.json')), rerun.files.get('models.json')));
  const on = rerun.models.filter(m => m.enabled).map(m => m.file);
  line(`rerun: the enabled pair names <stem>_props.obj and <stem>_lot.obj (${on.join(', ')})`, on.length === 2 && on.some(f => /_props\.obj$/.test(f)) && on.some(f => /[^s]_lot\.obj$/.test(f) && !/_props_lot\.obj$/.test(f)));
  const lotOnly = on.find(f => /_lot\.obj$/.test(f)), txt = lotOnly ? new TextDecoder().decode(rerun.files.get(lotOnly)) : '';
  line(`rerun: ${lotOnly} holds the house and the ground quad, no props`, /\ng sc3ground\n/.test(txt) && !/usemtl sc4p_/.test(txt) && !/\ng sc4lot\n/.test(txt));
}
// 4. pack of the rerun
const t0 = Date.now();
const folder = W.overlayFS(rerun.files, null);
const game = B.handleFS(new DirHandle(gameDir));
const frames = new Map();
let files = new Map();
try {
  [files] = await B.buildFiles(folder, game, new Map(), {
    onModel: (i, n, e) => process.stdout.write(`\r  render ${i}/${n} ${e.file.padEnd(40)}`),
    onFrames: (e, fr) => frames.set(e.model.file, fr),
  });
  process.stdout.write('\n');
} catch (e) { console.log('  ERROR ' + (e.stack || e)); }
console.log(`  rendered + packed in ${((Date.now() - t0) / 1000).toFixed(1)} s`);
for (const rel of outFiles) {
  const a = fs.readFileSync(path.join(pyOut, rel)), b = files.get(rel);
  line('pack ' + rel, eqBytes(a, b), b ? `${b.length} bytes ${B.sha256(a).slice(0, 16)}` : 'not written');
}
line('pack sc3build/ids.json', eqBytes(fs.readFileSync(path.join(golden, 'py', 'rerun', 'folder', 'sc3build', 'ids.json')), folder.written.get('sc3build/ids.json')));
if (wantFrames) {
  let nb = 0, n = 0; const notes = [];
  for (const [file, fr] of frames) {
    const stem = file.replace(/\.[^.]+$/, '');
    for (const [key, [im]] of fr) {
      const [z, r] = key.split(',');
      n++;
      const py = await B.decodePNG(fs.readFileSync(path.join(golden, 'py', 'rerun', 'folder', 'sc3build', stem, `z${z}_r${r}.png`)));
      let diff = 0;
      if (py.w !== im.w || py.h !== im.h) diff = -1;
      else for (let q = 0; q < im.w * im.h; q++) {
        if ((py.a ? py.a[q] : 255) !== im.d[4 * q + 3]) { diff++; continue; }
        for (let ch = 0; ch < 3; ch++) if (py.rgb[3 * q + ch] !== im.d[4 * q + ch]) { diff++; break; }
      }
      if (diff) { nb++; if (notes.length < 8) notes.push(`${stem} z${z}r${r}: ${diff < 0 ? 'size' : diff + ' px'}`); }
    }
  }
  line(`frames vs python cache (${n}, RGBA)`, nb === 0 && n > 0, nb ? `${nb} differ: ${notes.join('; ')}` : '');
}
console.log(`${total - bad} of ${total} passed`);
process.exit(bad ? 1 : 0);
