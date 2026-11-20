// sc4_golden.mjs - task sc4web (2026-11-19): the page's SC4 conversion (sc4web.js) and its install (bldweb.js)
// against the Python route (sc4conv.py, then bldimport.py), byte for byte.
//
//   node sc4_golden.mjs --golden <dir from golden_setup.py --cases sc4 --sc4 <folder>> --game <tree>
//                       --zip <the SC4 download .zip> --folder <the same download unpacked> [--frames]
//
// Checks, one line each ([N/M] name PASS|FAIL):
//   1. the .zip converted by sc4web.js (the archive as the player downloaded it, the LEX .jar inside read as a folder):
//      per building its OBJ and MTL text byte for byte and its 4 textures pixel for pixel (RGBA) against sc4conv.py's
//      output (golden src\sc4), then models.json byte for byte, and no file more or less
//   2. the unpacked folder converted the same way gives the same files as the .zip
//   3. the rerun merge: converting again over a models.json edited the way the page saves it gives sc4conv.py's
//      rerun models.json (golden py\sc4\rerun)
//   4. bldweb.buildFiles over the converted files in memory (the page's overlay folder) against
//      `bldimport.py pack --out` of the Python output: every game file, sc3build\ids.json, --frames every frame
//   task sc4diag (2026-11-19c), after 3:
//   3a. diagonal buildings (set at 45 degrees in SC4, from the foundation model): every one written off with the note,
//       no design left on a diagonal colour while it has a straight one, the counts printed per design
//   3b. convert({ diagonal: true }) gives sc4conv.py --diagonal's models.json (golden py\sc4\diagonal)
//   3c. pickColours on made-up designs that mix diagonal and straight colours = sc4conv.pick_colours (pick_cases.json)
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
const golden = arg('golden'), gameDir = arg('game'), zipPath = arg('zip'), folderPath = arg('folder');
const wantFrames = process.argv.includes('--frames');
if (!golden || !gameDir || !zipPath || !folderPath) { console.log('usage: node sc4_golden.mjs --golden <dir> --game <tree> --zip <zip> --folder <dir> [--frames]'); process.exit(2); }

function walk(d, base = d, out = []) {
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    const p = path.join(d, e.name);
    if (e.isDirectory()) walk(p, base, out); else out.push(path.relative(base, p).split(path.sep).join('/'));
  }
  return out;
}
const fileInputs = dir => walk(dir).map(rel => ({ path: rel, bytes: async () => new Uint8Array(fs.readFileSync(path.join(dir, ...rel.split('/')))) }));
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

const pyConv = path.join(golden, 'src', 'sc4');
const pyFiles = walk(pyConv).filter(f => !f.startsWith('sc3build/'));
const pyModels = JSON.parse(fs.readFileSync(path.join(pyConv, 'models.json'), 'utf8')).models;
const pyOut = path.join(golden, 'py', 'sc4', 'out');
const outFiles = walk(pyOut);
let total = pyModels.length + 2 + 1 + 3 + 1 + outFiles.length + 1 + (wantFrames ? 1 : 0), k = 0, bad = 0;
const line = (what, ok, extra = '') => { k++; bad += !ok; console.log(`[${k}/${total}] ${what} ${ok ? 'PASS' : 'FAIL'}${extra ? ' ' + extra : ''}`); };

// 1. the .zip
let t0 = Date.now();
const zipIn = [{ path: path.basename(zipPath), bytes: async () => new Uint8Array(fs.readFileSync(zipPath)) }];
const conv = await W.convert(await W.sourcesFrom(zipIn), { log: s => console.log('  ' + s) });
console.log(`  zip converted in ${((Date.now() - t0) / 1000).toFixed(1)} s`);
for (const m of pyModels) {
  const stem = m.file.replace(/(_props)?(_lot)?\.obj$/i, ''), notes = [];   // task sc4lottex: the house's stem
  const exts = ['.obj', '.mtl'];
  for (const x of ['_props', '_lot', '_props_lot']) if (fs.existsSync(path.join(pyConv, stem + x + '.obj'))) exts.push(x + '.obj', x + '.mtl');   // task sc4lottex
  for (const ext of exts) if (!eqBytes(fs.readFileSync(path.join(pyConv, stem + ext)), conv.files.get(stem + ext))) notes.push(ext + ' differs');
  for (const v of ['S', 'W', 'N', 'E']) {
    const png = `${stem}_${v}.png`, js = conv.files.get(png);
    if (!js) { notes.push(png + ' missing'); continue; }
    const d = await samePixels(fs.readFileSync(path.join(pyConv, png)), js);
    if (d) notes.push(png + ': ' + d);
  }
  if (fs.existsSync(path.join(pyConv, stem + '_lot.png'))) { const d = await samePixels(fs.readFileSync(path.join(pyConv, stem + '_lot.png')), conv.files.get(stem + '_lot.png')); if (d) notes.push('_lot.png: ' + d); }   // task sc4lottex
  line(`convert ${m.file} (obj, mtl, 4 textures)`, !notes.length, notes.join('; '));
}
line('convert models.json', eqBytes(fs.readFileSync(path.join(pyConv, 'models.json')), conv.files.get('models.json')),
  `${conv.files.get('models.json').length} bytes, ${conv.models.length} models, ${conv.models.filter(m => m.enabled).length} enabled`);
{
  const js = new Set(conv.files.keys()), py = new Set(pyFiles);
  const extra = [...js].filter(f => !py.has(f)), miss = [...py].filter(f => !js.has(f));
  line(`convert file list (${js.size} files)`, !extra.length && !miss.length, (extra.length ? 'extra: ' + extra.slice(0, 5).join(', ') : '') + (miss.length ? ' missing: ' + miss.slice(0, 5).join(', ') : ''));
}

// 2. the unpacked folder
t0 = Date.now();
const convF = await W.convert(await W.sourcesFrom(fileInputs(folderPath)), {});
{
  const diff = [...conv.files.keys()].filter(f => !eqBytes(conv.files.get(f), convF.files.get(f)));
  line(`folder route = .zip route (${convF.files.size} files, ${((Date.now() - t0) / 1000).toFixed(1)} s)`, !diff.length && convF.files.size === conv.files.size, diff.slice(0, 5).join(', '));
}

// 3. the rerun merge
{
  const old = fs.readFileSync(path.join(golden, 'py', 'sc4', 'rerun_old.json'), 'utf8');
  const r = await W.convert(await W.sourcesFrom(zipIn), { old });
  const want = fs.readFileSync(path.join(golden, 'py', 'sc4', 'rerun', 'models.json'));
  line('rerun keeps the page edits (models.json vs sc4conv.py rerun)', eqBytes(want, r.files.get('models.json')), `${want.length} bytes`);
}

// 3a-3c. diagonal buildings (task sc4diag)
{
  const ms = conv.models, bad = [];
  const byDesign = new Map();
  for (const m of ms) { const d = m.x_sc4.design; if (!byDesign.has(d)) byDesign.set(d, []); byDesign.get(d).push(m); }
  for (const m of ms) {
    if (m.x_sc4.diagonal && m.enabled) bad.push(m.file + ' diagonal but on');
    if (m.x_sc4.diagonal && !/^Diagonal, off by default: /.test(m.notes)) bad.push(m.file + ' no note');
    if (!m.x_sc4.diagonal && /^Diagonal/.test(m.notes)) bad.push(m.file + ' note on a straight building');
  }
  const rows = [];
  for (const [d, list] of byDesign) {
    const nd = list.filter(m => m.x_sc4.diagonal).length, on = list.filter(m => m.enabled).length;
    if (nd < list.length && on !== 1) bad.push(d + ': ' + on + ' on, want 1 straight colour');
    if (nd === list.length && on) bad.push(d + ': every colour diagonal but ' + on + ' on');
    rows.push(`${d} ${nd}/${list.length}${nd ? ' diagonal' : ''}`);
  }
  console.log('  ' + rows.join(', '));
  const nd = ms.filter(m => m.x_sc4.diagonal).length;
  line(`diagonal buildings off with the note (${nd} of ${ms.length}, ${ms.filter(m => m.enabled).length} on)`, !bad.length && nd > 0, bad.slice(0, 5).join('; '));
  const r = await W.convert(await W.sourcesFrom(zipIn), { diagonal: true });
  const want = fs.readFileSync(path.join(golden, 'py', 'sc4', 'diagonal', 'models.json'));
  line(`--diagonal route (models.json vs sc4conv.py --diagonal, ${r.models.filter(m => m.enabled).length} on)`, eqBytes(want, r.files.get('models.json')), `${want.length} bytes`);
  const pc = JSON.parse(fs.readFileSync(path.join(golden, 'py', 'sc4', 'pick_cases.json'), 'utf8'));
  const got = W.pickColours(pc.groups, m => m[1] === 1).map(c => c ? c[0] : null);
  line(`colour pick on mixed designs (${pc.groups.length} designs: ${got.map(x => x || '-').join(' ')})`, JSON.stringify(got) === JSON.stringify(pc.picked), JSON.stringify(pc.picked));
}

// 4. render + pack from the converted files in memory
t0 = Date.now();
const folder = W.overlayFS(conv.files, null);
const game = B.handleFS(new DirHandle(gameDir));
const frames = new Map();
let files = new Map(), rep = [];
try {
  [files, rep] = await B.buildFiles(folder, game, new Map(), {
    onModel: (i, n, e) => process.stdout.write(`\r  render ${i}/${n} ${e.file.padEnd(40)}`),
    onFrames: (e, fr) => frames.set(e.model.file, fr),
  });
  process.stdout.write('\n');
} catch (e) { console.log('  ERROR ' + (e.stack || e)); }
console.log(`  rendered + packed in ${((Date.now() - t0) / 1000).toFixed(1)} s`);
for (const r of rep) console.log('    ' + r);
for (const rel of outFiles) {
  const a = fs.readFileSync(path.join(pyOut, rel)), b = files.get(rel);
  line('pack ' + rel, eqBytes(a, b), b ? `${b.length} bytes ${B.sha256(a).slice(0, 16)}` : 'not written');
}
for (const rel of files.keys()) if (!outFiles.includes(rel)) console.log('  extra file written by bldweb: ' + rel);
line('pack sc3build/ids.json', eqBytes(fs.readFileSync(path.join(golden, 'py', 'sc4', 'folder', 'sc3build', 'ids.json')), folder.written.get('sc3build/ids.json')));
if (wantFrames) {
  let nb = 0, n = 0; const notes = [];
  for (const [file, fr] of frames) {
    const stem = file.replace(/\.[^.]+$/, '');
    for (const [key, [im]] of fr) {
      const [z, r] = key.split(',');
      n++;
      const py = await B.decodePNG(fs.readFileSync(path.join(golden, 'py', 'sc4', 'folder', 'sc3build', stem, `z${z}_r${r}.png`)));
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
