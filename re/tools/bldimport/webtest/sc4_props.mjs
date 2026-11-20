// sc4_props.mjs - task sc4props (2026-11-19g): SC4 lot props baked into the converted buildings, sc4web.js against
// sc4conv.py --deps (golden from sc4_props_setup.py), byte for byte.
//
//   node sc4_props.mjs --golden <dir from sc4_props_setup.py> --game <tree> --zip <the JMyers .zip> --deps <BSC zip> [--frames]
//
// The dependency pack is given as the page gets it from a file picker: an input with a size, slices and a stream
// (sc4web.js sourcesFrom treats an archive over DEPS_MIN this way: never read whole). Checks, one line each:
//   1. the index streamed from the zip: prop exemplars and cohorts (counts), the prop ids the JMyers lots name resolve
//      to the same exemplars as in Python (deps.DepsIndex)
//   2. per building: OBJ / MTL text byte for byte (the house alone and <stem>_props.obj), its textures pixel for pixel;
//      every sc4prop_*.png pixel for pixel; models.json byte for byte; the file list
//   3. --no-props (opt.noProps) models.json = sc4conv.py --no-props
//   4. the rerun keeps the player's props switch (models.json vs sc4conv.py rerun)
//   5. bldweb.buildFiles over the converted files = `bldimport.py pack` of the Python output: every game file,
//      sc3build/ids.json, --frames every frame
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
const golden = arg('golden'), gameDir = arg('game'), zipPath = arg('zip'), depsPath = arg('deps');
const wantFrames = process.argv.includes('--frames');
if (!golden || !gameDir || !zipPath || !depsPath) { console.log('usage: node sc4_props.mjs --golden <dir> --game <tree> --zip <JMyers zip> --deps <BSC zip> [--frames]'); process.exit(2); }

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
// the dependency pack as a file picker gives it: size, slices, a stream of a byte range
function fileInput(p) {
  const st = fs.statSync(p), fd = fs.openSync(p, 'r');
  return { path: path.basename(p), size: st.size, mtime: Math.floor(st.mtimeMs),
    bytes: async () => { throw new Error('a dependency pack must not be read whole'); },
    slice: async (a, b) => { const buf = Buffer.alloc(b - a); fs.readSync(fd, buf, 0, b - a, a); return new Uint8Array(buf.buffer, buf.byteOffset, buf.length); },
    stream: (a, b) => Readable.toWeb(fs.createReadStream(p, { start: a, end: b - 1, highWaterMark: 1 << 22 })) };
}

const pyConv = path.join(golden, 'src', 'sc4props');
const pyFiles = walk(pyConv);
const pyModels = JSON.parse(fs.readFileSync(path.join(pyConv, 'models.json'), 'utf8')).models;
const pyOut = path.join(golden, 'py', 'sc4props', 'out');
const outFiles = walk(pyOut);
const propPngs = pyFiles.filter(f => /^sc4prop_.*\.png$/.test(f));
let total = 2 + pyModels.length + 1 + 1 + 1 + 1 + 1 + outFiles.length + 1 + (wantFrames ? 1 : 0), k = 0, bad = 0;
const line = (what, ok, extra = '') => { k++; bad += !ok; console.log(`[${k}/${total}] ${what} ${ok ? 'PASS' : 'FAIL'}${extra ? ' ' + extra : ''}`); };

const deps = fileInput(depsPath);
const zipIn = [{ path: path.basename(zipPath), bytes: async () => new Uint8Array(fs.readFileSync(zipPath)) }, deps];
let t0 = Date.now();
const srcs = await W.sourcesFrom(zipIn);
line(`the dependency pack is streamed, not read whole (${srcs.deps.length} pack, ${(deps.size / 1e9).toFixed(2)} GB)`, srcs.deps.length === 1 && srcs.deps[0] === deps);
const conv = await W.convert(srcs, { log: s => { if (/^deps|^Lot props|^Props not/.test(s)) console.log('  ' + s); } });
console.log(`  converted with props in ${((Date.now() - t0) / 1000).toFixed(1)} s`);
{
  const di = await W.depsIndex(deps);       // cached in the page session: the same object
  const pyLog = fs.readFileSync(path.join(golden, 'sc4conv_log.txt'), 'utf8');
  const m = /(\d+) prop exemplars, (\d+) cohorts, (\d+) DBPF files|indexed (\d+) DBPF files, (\d+) prop exemplars, (\d+) cohorts/.exec(pyLog);
  const py = m ? (m[1] ? [+m[3], +m[1], +m[2]] : [+m[4], +m[5], +m[6]]) : null;
  const js = [di.dats.length, di.props.size, di.cohorts.size];
  line(`dependency index: ${js[0]} DBPF files, ${js[1]} prop exemplars, ${js[2]} cohorts (Python ${py ? py.join(' / ') : '?'})`, !!py && py.join() === js.join());
}
const pngNotes = [];
for (const m of pyModels) {
  const stem = m.x_sc4 ? m.file.replace(/(_props)?(_lot)?\.obj$/i, '') : m.file.replace(/\.obj$/i, ''), notes = [];
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
  const p = m.x_sc4 && m.x_sc4.props;
  line(`convert ${stem} (${exts.length} text files, 4 textures${p ? ', props ' + p.placed + ' of ' + p.rows : ''})`, !notes.length, notes.join('; '));
}
for (const f of propPngs) { const d = await samePixels(fs.readFileSync(path.join(pyConv, f)), conv.files.get(f)); if (d) pngNotes.push(f + ': ' + d); }
line(`prop textures (${propPngs.length} sc4prop_*.png, pixel for pixel)`, !pngNotes.length && propPngs.length > 0, pngNotes.slice(0, 5).join('; '));
line('convert models.json', eqBytes(fs.readFileSync(path.join(pyConv, 'models.json')), conv.files.get('models.json')),
  `${conv.files.get('models.json').length} bytes, ${conv.models.filter(m => m.x_sc4.props && m.x_sc4.props.on).length} with props on`);
{
  const js = new Set(conv.files.keys()), py = new Set(pyFiles);
  const extra = [...js].filter(f => !py.has(f)), miss = [...py].filter(f => !js.has(f));
  line(`convert file list (${js.size} files)`, !extra.length && !miss.length, (extra.length ? 'extra: ' + extra.slice(0, 5).join(', ') : '') + (miss.length ? ' missing: ' + miss.slice(0, 5).join(', ') : ''));
}
{
  const r = await W.convert(await W.sourcesFrom(zipIn), { noProps: true });
  line('--no-props route (models.json vs sc4conv.py --no-props)', eqBytes(fs.readFileSync(path.join(golden, 'noprops', 'models.json')), r.files.get('models.json')));
}
{
  const old = fs.readFileSync(path.join(golden, 'rerun_old.json'), 'utf8');
  const r = await W.convert(await W.sourcesFrom(zipIn), { old });
  line('rerun keeps the props switch (models.json vs sc4conv.py rerun)', eqBytes(fs.readFileSync(path.join(golden, 'rerun', 'models.json')), r.files.get('models.json')));
}

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
for (const rel of outFiles) {
  const a = fs.readFileSync(path.join(pyOut, rel)), b = files.get(rel);
  line('pack ' + rel, eqBytes(a, b), b ? `${b.length} bytes ${B.sha256(a).slice(0, 16)}` : 'not written');
}
line('pack sc3build/ids.json', eqBytes(fs.readFileSync(path.join(golden, 'py', 'sc4props', 'folder', 'sc3build', 'ids.json')), folder.written.get('sc3build/ids.json')));
if (wantFrames) {
  let nb = 0, n = 0; const notes = [];
  for (const [file, fr] of frames) {
    const stem = file.replace(/\.[^.]+$/, '');
    for (const [key, [im]] of fr) {
      const [z, r] = key.split(',');
      n++;
      const py = await B.decodePNG(fs.readFileSync(path.join(golden, 'py', 'sc4props', 'folder', 'sc3build', stem, `z${z}_r${r}.png`)));
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
