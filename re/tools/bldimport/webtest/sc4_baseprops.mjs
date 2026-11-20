// sc4_baseprops.mjs - task sc4baseprops (2026-11-19): SimCity 4's own props from the player's install as a prop source
// for a download, sc4web.js against sc4conv.py --sc4 (golden from sc4_baseprops_setup.py), byte for byte.
//
//   node sc4_baseprops.mjs --golden <dir from sc4_baseprops_setup.py> --game <tree> --zip <the JMyers .zip>
//        --deps <BSC zip> --install <SimCity 4 folder> [--frames]
//
// The install's 7 game files are given as the page gets them from a file picker (size, slices; the big ones are never
// read whole) and picked together with the download: sourcesFrom keeps the download as the input and the install as its
// prop source. Checks, one line each:
//   1. the pick: the download converted, the install a prop source (7 files), the BSC zip a streamed pack; the whole
//      game folder picked alone stays the install (its Intro.dat, Sound.dat and subfolders do not make it a download)
//   2. download + BSC + install: per building OBJ / MTL byte for byte (house alone and <stem>_props.obj) and its
//      textures pixel for pixel; every sc4prop_*.png pixel for pixel; models.json byte for byte; the file list
//   3. how much of the install was read (slices), no big file read whole
//   4. the install alone (picked with the download): every file = sc4conv.py --sc4
//   5. the install remembered (Open SC4 game, then the download alone: opt.sc4): models.json = sc4conv.py --sc4
//   6. bldweb.buildFiles over the converted files (download + BSC + install) = `bldimport.py pack`: every game file,
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
const golden = arg('golden'), gameDir = arg('game'), zipPath = arg('zip'), depsPath = arg('deps'), instDir = arg('install');
const wantFrames = process.argv.includes('--frames');
if (!golden || !gameDir || !zipPath || !depsPath || !instDir) { console.log('usage: node sc4_baseprops.mjs --golden <dir> --game <tree> --zip <JMyers zip> --deps <BSC zip> --install <SimCity 4 folder> [--frames]'); process.exit(2); }

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
// a file as a file picker gives it: size, slices, a stream; reads are counted, a whole read of a big one refused
const READ = { slices: 0, whole: 0, bigWhole: [] };
function fileInput(p, rel, big = 200 << 20) {
  const st = fs.statSync(p), fd = fs.openSync(p, 'r');
  return { path: rel, size: st.size, mtime: Math.floor(st.mtimeMs),
    bytes: async () => { if (st.size >= big) { READ.bigWhole.push(rel); throw new Error(rel + ' must not be read whole'); } READ.whole += st.size; return new Uint8Array(fs.readFileSync(p)); },
    slice: async (a, b) => { const buf = Buffer.alloc(b - a); fs.readSync(fd, buf, 0, b - a, a); READ.slices += b - a; return new Uint8Array(buf.buffer, buf.byteOffset, buf.length); },
    stream: (a, b) => Readable.toWeb(fs.createReadStream(p, { start: a, end: b - 1, highWaterMark: 1 << 22 })) };
}
const INSTALL = ['SimCity_1.dat', 'SimCity_2.dat', 'SimCity_3.dat', 'SimCity_4.dat', 'SimCity_5.dat', 'EP1.dat', 'SimCityLocale.DAT'];
const instInputs = () => INSTALL.filter(f => fs.existsSync(path.join(instDir, f))).map(f => fileInput(path.join(instDir, f), f, 16 << 20));
const zipInput = () => ({ path: path.basename(zipPath), bytes: async () => new Uint8Array(fs.readFileSync(zipPath)) });

async function compareConv(what, pyConv, conv) {   // -> [lines] per building + prop textures + models.json + list
  const pyFiles = walk(pyConv), pyModels = JSON.parse(fs.readFileSync(path.join(pyConv, 'models.json'), 'utf8')).models;
  const out = [];
  for (const m of pyModels) {
    const stem = m.file.replace(/(_props)?\.obj$/i, ''), notes = [];
    const exts = ['.obj', '.mtl'].concat(fs.existsSync(path.join(pyConv, stem + '_props.obj')) ? ['_props.obj', '_props.mtl'] : []);
    for (const ext of exts) if (!eqBytes(fs.readFileSync(path.join(pyConv, stem + ext)), conv.files.get(stem + ext))) notes.push(ext + ' differs');
    for (const v of ['S', 'W', 'N', 'E']) {
      const png = `${stem}_${v}.png`, js = conv.files.get(png);
      if (!js) { notes.push(png + ' missing'); continue; }
      const d = await samePixels(fs.readFileSync(path.join(pyConv, png)), js);
      if (d) notes.push(png + ': ' + d);
    }
    const p = m.x_sc4 && m.x_sc4.props;
    out.push([`${what}: ${stem} (${exts.length} text files, 4 textures${p ? ', props ' + p.placed + ' of ' + p.rows : ''})`, !notes.length, notes.join('; ')]);
  }
  const propPngs = pyFiles.filter(f => /^sc4prop_.*\.png$/.test(f)), pn = [];
  for (const f of propPngs) { const d = await samePixels(fs.readFileSync(path.join(pyConv, f)), conv.files.get(f)); if (d) pn.push(f + ': ' + d); }
  out.push([`${what}: prop textures (${propPngs.length} sc4prop_*.png, pixel for pixel)`, !pn.length && propPngs.length > 0, pn.slice(0, 5).join('; ')]);
  out.push([`${what}: models.json`, eqBytes(fs.readFileSync(path.join(pyConv, 'models.json')), conv.files.get('models.json')),
    `${conv.files.get('models.json').length} bytes, ${conv.models.filter(m => m.x_sc4.props && m.x_sc4.props.on).length} with props on`]);
  const js = new Set(conv.files.keys()), py = new Set(pyFiles);
  const extra = [...js].filter(f => !py.has(f)), miss = [...py].filter(f => !js.has(f));
  out.push([`${what}: file list (${js.size} files)`, !extra.length && !miss.length, (extra.length ? 'extra: ' + extra.slice(0, 5).join(', ') : '') + (miss.length ? ' missing: ' + miss.slice(0, 5).join(', ') : '')]);
  return out;
}

const bothDir = path.join(golden, 'src', 'sc4baseprops'), instOnlyDir = path.join(golden, 'src', 'sc4baseprops_inst');
const nBoth = JSON.parse(fs.readFileSync(path.join(bothDir, 'models.json'), 'utf8')).models.length;
const pyOut = path.join(golden, 'py', 'sc4baseprops', 'out'), outFiles = walk(pyOut);
let total = 2 + (nBoth + 3) + 1 + 1 + 1 + 1 + outFiles.length + 1 + (wantFrames ? 1 : 0), k = 0, bad = 0;
const line = (what, ok, extra = '') => { k++; bad += !ok; console.log(`[${k}/${total}] ${what} ${ok ? 'PASS' : 'FAIL'}${extra ? ' ' + extra : ''}`); };
const quiet = s => { if (/^(deps: index|SimCity 4 install|Lot props|Props not)/.test(s)) console.log('  ' + s.slice(0, 300)); };

// 1 + 2: the download, the BSC zip and the install's 7 files picked together
const deps = fileInput(depsPath, path.basename(depsPath));
let t0 = Date.now();
const srcs = await W.sourcesFrom([zipInput(), deps].concat(instInputs()));
line(`the pick: download converted, install a prop source (${srcs.sc4 ? srcs.sc4.length : 0} files), ${srcs.deps.length} pack streamed`,
  !srcs.install && !!srcs.sc4 && srcs.sc4.length === 7 && srcs.length > 0 && srcs.deps.length === 1 && srcs.every(s => !INSTALL.includes(s.path)));
{                                           // the whole game folder picked alone (Open SC4 game) stays the install
  const all = []; (function w(d, pre) { for (const e of fs.readdirSync(d, { withFileTypes: true })) { const rel = pre + e.name; if (e.isDirectory()) w(path.join(d, e.name), rel + '/'); else if (W.isDbpfName(e.name)) all.push(fileInput(path.join(d, e.name), rel, 16 << 20)); } })(instDir, '');
  const g = await W.sourcesFrom(all);
  line(`the whole game folder picked alone (${all.length} DBPF files, Intro.dat and Sound.dat among them) is the install, not a download`, g.install === true && g.length === 7 && !g.sc4, g.map(x => x.path).join(', '));
}
const conv = await W.convert(srcs, { log: quiet });
console.log(`  converted with BSC + install props in ${((Date.now() - t0) / 1000).toFixed(1)} s`);
const readBoth = { ...READ };
const lines = await compareConv('both', bothDir, conv);
if (lines.length !== nBoth + 3) total += lines.length - (nBoth + 3);
for (const l of lines) line(...l);
line(`install read by slices: ${(readBoth.slices / 1e6).toFixed(1)} MB in slices, ${(readBoth.whole / 1e6).toFixed(1)} MB in whole small files, no big file read whole`, !readBoth.bigWhole.length, readBoth.bigWhole.join(', '));

// 4: the install alone, picked with the download
{
  const r = await W.convert(await W.sourcesFrom([zipInput()].concat(instInputs())), { log: quiet });
  const ls = await compareConv('install alone', instOnlyDir, r);
  const badL = ls.filter(l => !l[1]);
  line(`install alone (picked with the download) = sc4conv.py --sc4: ${ls.length} checks (every building's files, prop textures, models.json, file list)`, !badL.length, badL.slice(0, 3).map(l => l[0] + ' ' + l[2]).join('; '));
}
// 5: the install remembered from Open SC4 game, then the download opened alone
{
  const game = await W.sourcesFrom(instInputs());
  const r = await W.convert(await W.sourcesFrom([zipInput()]), { sc4: game.install ? game : null });
  line('install remembered (Open SC4 game, then the download alone): models.json = sc4conv.py --sc4', game.install === true &&
    eqBytes(fs.readFileSync(path.join(instOnlyDir, 'models.json')), r.files.get('models.json')));
}
// a download without the install keeps the old note text
{
  const r = await W.convert(await W.sourcesFrom([zipInput()]), {});
  const ln = r.report.find(l => /^Props not found/.test(l)) || '';
  line('without the install: the report still names SimCity 4\'s own props as missing', /SimCity 4's own props or a dependency not given/.test(ln), ln.slice(0, 120));
}

// 6: pack of download + BSC + install
t0 = Date.now();
const folder = W.overlayFS(conv.files, null);
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
line('pack sc3build/ids.json', eqBytes(fs.readFileSync(path.join(golden, 'py', 'sc4baseprops', 'folder', 'sc3build', 'ids.json')), folder.written.get('sc3build/ids.json')));
if (wantFrames) {
  let nb = 0, n = 0; const notes = [];
  for (const [file, fr] of frames) {
    const stem = file.replace(/\.[^.]+$/, '');
    for (const [key, [im]] of fr) {
      const [z, r] = key.split(',');
      n++;
      const py = await B.decodePNG(fs.readFileSync(path.join(golden, 'py', 'sc4baseprops', 'folder', 'sc3build', stem, `z${z}_r${r}.png`)));
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
