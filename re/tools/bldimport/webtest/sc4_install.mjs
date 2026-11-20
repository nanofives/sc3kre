// sc4_install.mjs - task sc4civ (2026-11-19l): the player's own SimCity 4 install through the page's converter
// (sc4web.js) against the Python route (sc4conv.py, bldimport.py), byte for byte. Needs sc4_install_setup.py's output.
//
//   node sc4_install.mjs --golden <dir from sc4_install_setup.py> --install "<SimCity 4 install folder>" --game <tree> [--frames]
//
// The install is read as the page reads a picked folder: every file listed, the 7 game files kept, the large ones read
// by slices (never whole: the test counts the bytes read). Checks, one line each ([N/M] name PASS|FAIL):
//   conv     every OBJ / MTL / models.json byte for byte, every PNG pixel for pixel (RGBA), the file list, the notes
//   kinds    SC4's civic buildings as civic looks (police, fire, ...), parks, rewards with SC4's populations, landmarks
//   rerun    models.json edited as the page saves it (a reward's population, a civic look's base, a switch), converted
//            again = sc4conv.py over the same file
//   sub      the 4-building subset (sc4conv.py --only): bldweb.buildFiles from memory = bldimport.py pack (every game
//            file, ids.json, --frames every frame)
//   bytes    the bytes read from the install, against its size
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
const golden = arg('golden'), inst = arg('install'), gameDir = arg('game');
const wantFrames = process.argv.includes('--frames');
if (!golden || !inst || !gameDir) { console.log('usage: node sc4_install.mjs --golden <dir> --install <SC4 folder> --game <tree> [--frames]'); process.exit(2); }

function walk(d, base = d, out = []) {
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    const p = path.join(d, e.name);
    if (e.isDirectory()) walk(p, base, out); else out.push(path.relative(base, p).split(path.sep).join('/'));
  }
  return out;
}
let readBytes = 0, wholeReads = 0;
function fileInput(dir, rel) {               // a picked file: size, slices, the whole file (counted)
  const p = path.join(dir, ...rel.split('/')), size = fs.statSync(p).size;
  return { path: rel, size, mtime: 0,
    bytes: async () => { wholeReads++; readBytes += size; return new Uint8Array(fs.readFileSync(p)); },
    slice: async (a, b) => {
      b = Math.min(b, size); const n = Math.max(0, b - a), buf = Buffer.alloc(n);
      const fd = fs.openSync(p, 'r'); try { fs.readSync(fd, buf, 0, n, a); } finally { fs.closeSync(fd); }
      readBytes += n; return new Uint8Array(buf.buffer, buf.byteOffset, n);
    } };
}
const installInputs = () => walk(inst).filter(rel => W.isDbpfName(rel.split('/').pop())).map(rel => fileInput(inst, rel));
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
const g = (...p) => path.join(golden, ...p);
const readJson = p => JSON.parse(fs.readFileSync(p, 'utf8'));
const pyConv = g('conv'), pyFiles = walk(pyConv), subOut = fs.existsSync(g('sub', 'out')) ? walk(g('sub', 'out')) : [];
const total = 9 + subOut.length + 1 + (wantFrames ? 1 : 0);
let k = 0, bad = 0;
const line = (what, ok, extra = '') => { k++; bad += !ok; console.log(`[${k}/${total}] ${what} ${ok ? 'PASS' : 'FAIL'}${extra ? ' ' + extra : ''}`); };
const log = s => console.log('  ' + s);

// the whole install
let t0 = Date.now();
const src = await W.sourcesFrom(installInputs());
const conv = await W.convert(src, { log: () => {} });
const secs = ((Date.now() - t0) / 1000).toFixed(1);
log(`install converted in ${secs} s, ${conv.models.length} models, ${(readBytes / 1048576).toFixed(1)} MB read`);
{
  const diff = [], pix = [];
  for (const rel of pyFiles) {
    const js = conv.files.get(rel);
    if (!js) { diff.push(rel + ' missing'); continue; }
    if (rel.endsWith('.png')) { const d = await samePixels(fs.readFileSync(path.join(pyConv, rel)), js); if (d) pix.push(rel + ': ' + d); }
    else if (!eqBytes(fs.readFileSync(path.join(pyConv, rel)), js)) diff.push(rel + ' differs');
  }
  const nText = pyFiles.filter(f => !f.endsWith('.png')).length;
  line(`install: ${nText} OBJ / MTL / models.json files byte for byte`, !diff.length && nText > 0, diff.slice(0, 6).join('; '));
  line(`install: ${pyFiles.length - nText} textures pixel for pixel`, !pix.length, pix.slice(0, 6).join('; '));
  const js = new Set(conv.files.keys());
  line(`install: file list (${js.size} files)`, js.size === pyFiles.length && pyFiles.every(f => js.has(f)));
  const pn = readJson(g('notes.json'));
  line('install: notes = sc4conv.py', JSON.stringify(conv.notes) === JSON.stringify(pn.notes) && /^SimCity 4 install: /.test(conv.notes[0] || ''), (conv.notes[0] || '').slice(0, 110));
  const by = new Map(conv.models.map(m => [m.x_sc4.exemplar, m]));
  const want = [['CV24X24_4carLocalPrecinct_030C', 'civic', 'police'], ['CV12x14_2engineStationHouse_0310', 'civic', 'fire'],
    ['PZ11x9x11_Gazebo_1DDE', 'civic', 'small_park'], ['PZBaseball16x16x11_Backstop_1DBE', 'civic', 'baseball'],
    ['RW16x14_MayorsHouse_031F', 'reward', 500], ['RW44x28_CourtHouse_0322', 'reward', 40000], ['Lm16x16_Big Ben_04CD', 'landmark', null]];
  const got = want.map(([ex, kind, v]) => { const m = by.get(ex); return m ? `${ex.split('_').slice(1, 2)}=${m.kind}:${m.base || m.population || ''}` : ex + ' missing'; });
  line(`install: kinds (${got.join(', ')})`, want.every(([ex, kind, v]) => { const m = by.get(ex); return m && m.kind === kind && (v === null || m.base === v || m.population === v); }));
  line(`install: read by slices (${(readBytes / 1048576).toFixed(1)} MB of ${(src.reduce((s, x) => s + x.size, 0) / 1048576).toFixed(0)} MB, ${wholeReads} whole reads of files under 16 MB)`,
    readBytes < src.reduce((s, x) => s + x.size, 0) / 2 && src.filter(x => x.size >= (16 << 20)).length >= 5);
}
// rerun: the player's edits kept
{
  const oldText = fs.readFileSync(g('rerun', 'old.json'), 'utf8');   // sc4_install_setup.py's edits, as the page saves them
  const convR = await W.convert(await W.sourcesFrom(installInputs()), { old: oldText, log: () => {} });
  const a = convR.models.find(m => m.x_sc4.exemplar === 'RW16x14_MayorsHouse_031F'), b = convR.models.find(m => m.x_sc4.exemplar === 'PZ11x9x11_Gazebo_1DDE');
  line('install rerun keeps a reward\'s population + switch and a civic look\'s base (= sc4conv.py)', a.population === 1234 && a.enabled === false && b.base === 'fountain' &&
    eqBytes(fs.readFileSync(g('rerun', 'models.json')), convR.files.get('models.json')));
}
// a second pick of the same folder gives the same files
{
  const convB = await W.convert(await W.sourcesFrom(installInputs()), { log: () => {} });
  const d = [...conv.files.keys()].filter(f => !eqBytes(conv.files.get(f), convB.files.get(f)));
  line(`install converted twice: the same ${convB.files.size} files`, !d.length && convB.files.size === conv.files.size, d.slice(0, 4).join(', '));
}
// the subset, rendered and packed
const subConv = g('sub', 'conv');
const mem = new Map();
for (const rel of walk(subConv)) mem.set(rel, new Uint8Array(fs.readFileSync(path.join(subConv, rel))));
{
  const pyM = readJson(path.join(subConv, 'models.json')).models;
  const okFiles = [...mem.keys()].filter(f => !f.endsWith('.png') && f !== 'models.json').every(f => eqBytes(mem.get(f), conv.files.get(f)));
  line(`subset: ${pyM.length} models (${pyM.map(m => m.kind + (m.base ? ':' + m.base : '')).join(', ')}), OBJ / MTL = the whole install's`, pyM.length === 4 && okFiles);
}
t0 = Date.now();
const folder = W.overlayFS(mem, null);
const game = B.handleFS(new DirHandle(gameDir));
const frames = new Map();
let files = new Map(), rep = [];
try { [files, rep] = await B.buildFiles(folder, game, new Map(), { onFrames: (e, fr) => frames.set(e.model.file, fr) }); }
catch (e) { console.log('  ERROR ' + (e.stack || e)); }
log(`subset rendered + packed in ${((Date.now() - t0) / 1000).toFixed(1)} s`);
for (const r of rep) log('  ' + r);
for (const rel of subOut) {
  const a = fs.readFileSync(g('sub', 'out', rel)), b = files.get(rel);
  line('subset pack ' + rel, eqBytes(a, b), b ? `${b.length} bytes` : 'not written');
}
line('subset pack sc3build/ids.json', eqBytes(fs.readFileSync(g('sub', 'folder', 'sc3build', 'ids.json')), folder.written.get('sc3build/ids.json')));
if (wantFrames) {
  let nb = 0, n = 0; const notes = [];
  for (const [file, fr] of frames) {
    const stem = file.replace(/\.[^.]+$/, '');
    for (const [key, [im]] of fr) {
      const [z, r] = key.split(',');
      n++;
      const py = await B.decodePNG(fs.readFileSync(g('sub', 'folder', 'sc3build', stem, `z${z}_r${r}.png`)));
      let diff = 0;
      if (py.w !== im.w || py.h !== im.h) diff = -1;
      else for (let q = 0; q < im.w * im.h; q++) {
        if ((py.a ? py.a[q] : 255) !== im.d[4 * q + 3]) { diff++; continue; }
        for (let ch = 0; ch < 3; ch++) if (py.rgb[3 * q + ch] !== im.d[4 * q + ch]) { diff++; break; }
      }
      if (diff) { nb++; if (notes.length < 8) notes.push(`${stem} z${z}r${r}: ${diff < 0 ? 'size' : diff + ' px'}`); }
    }
  }
  line(`subset frames vs python cache (${n}, RGBA)`, nb === 0 && n > 0, nb ? `${nb} differ: ${notes.join('; ')}` : '');
}
console.log(`${total - bad} of ${total} passed`);
process.exit(bad ? 1 : 0);
