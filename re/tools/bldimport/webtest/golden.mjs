// golden.mjs - task bldweb (2026-11-18d): bldweb.js (the page's importer) against bldimport.py, byte for byte.
//
//   node golden.mjs --golden <dir from golden_setup.py> --game <tree> [--cases testmodels,bld,kenney] [--frames]
//
// Per case: copies <dir>\src\<case> to <dir>\js\<case>\folder, runs bldweb.buildFiles (the code the page runs) over it
// with the game folder read through the File System Access adapter (nodefs.mjs), and compares every file with what
// `bldimport.py pack --out` wrote (<dir>\py\<case>\out) plus sc3build\ids.json. --frames also compares each
// rendered frame with the Python tool's cached PNG (sc3build\<stem>\z<z>_r<r>.png) to localise a difference.
// One line per check: [N/M] <case> <file> PASS|FAIL.
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { DirHandle } from './nodefs.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const B = createRequire(import.meta.url)(path.join(here, '..', 'bldweb.js'));
const arg = k => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : null; };
const golden = arg('golden'), gameDir = arg('game');
const cases = (arg('cases') || 'testmodels,bld,kenney').split(',');
const wantFrames = process.argv.includes('--frames');
if (!golden || !gameDir) { console.log('usage: node golden.mjs --golden <dir> --game <tree> [--cases a,b] [--frames]'); process.exit(2); }

function walk(d, base = d, out = []) {
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    const p = path.join(d, e.name);
    if (e.isDirectory()) walk(p, base, out); else out.push(path.relative(base, p).split(path.sep).join('/'));
  }
  return out;
}
function copyDir(a, b) { fs.rmSync(b, { recursive: true, force: true }); fs.mkdirSync(b, { recursive: true }); fs.cpSync(a, b, { recursive: true }); }

const results = [];
let total = 0;
const plannedPerCase = {};
for (const c of cases) {
  const out = path.join(golden, 'py', c, 'out');
  plannedPerCase[c] = walk(out).length + 1 + (wantFrames ? 1 : 0);
  total += plannedPerCase[c];
}
let k = 0;
const line = (c, what, ok, extra = '') => { k++; results.push(ok); console.log(`[${k}/${total}] ${c} ${what} ${ok ? 'PASS' : 'FAIL'}${extra ? ' ' + extra : ''}`); };

for (const c of cases) {
  const t0 = Date.now();
  const jsFolder = path.join(golden, 'js', c, 'folder');
  copyDir(path.join(golden, 'src', c), jsFolder);
  const folder = B.handleFS(new DirHandle(jsFolder));
  const game = B.handleFS(new DirHandle(gameDir));
  const frames = new Map();
  let files, rep;
  try {
    [files, rep] = await B.buildFiles(folder, game, new Map(), {
      onModel: (i, n, e) => console.log(`  ${c}: model ${i}/${n} ${e.file}`),
      onFrames: (e, fr) => frames.set(e.model.file, fr),
    });
  } catch (e) { console.log(`  ${c}: ERROR ${e.stack || e}`); for (let q = 0; q < plannedPerCase[c]; q++) line(c, '(error)', false); continue; }
  console.log(`  ${c}: ${((Date.now() - t0) / 1000).toFixed(1)} s`);
  for (const r of rep) console.log('    ' + r);
  const pyOut = path.join(golden, 'py', c, 'out');
  const want = walk(pyOut);
  for (const rel of want) {
    const a = fs.readFileSync(path.join(pyOut, rel)), b = files.get(rel);
    const ok = !!b && Buffer.compare(a, Buffer.from(b)) === 0;
    let extra = ok ? `${a.length} bytes ${B.sha256(a).slice(0, 16)}` : (b ? `${b.length} vs python ${a.length} bytes` : 'not written');
    if (!ok && b && rel.endsWith('_bldimport.DAT')) {
      // which records differ
      const ra = B.records(new Uint8Array(a)), rb = B.records(b);
      const bad = [];
      for (const [kk, pa] of ra.idx) { const pb = rb.idx.get(kk); if (!pb || Buffer.compare(Buffer.from(pa), Buffer.from(pb))) bad.push(kk); }
      extra += ' records differ: ' + bad.slice(0, 12).map(s => { const [, i, t] = s.split(':').map(Number); return `${i >>> 16}/${i & 0xFFFF}/${t}`; }).join(' ') + (bad.length > 12 ? ` (+${bad.length - 12})` : '');
    }
    line(c, rel, ok, extra);
  }
  for (const rel of files.keys()) if (!want.includes(rel)) console.log(`  ${c}: extra file written by bldweb: ${rel}`);
  const ia = path.join(golden, 'py', c, 'folder', 'sc3build', 'ids.json'), ib = path.join(jsFolder, 'sc3build', 'ids.json');
  const idsOk = fs.existsSync(ib) && Buffer.compare(fs.readFileSync(ia), fs.readFileSync(ib)) === 0;
  line(c, 'sc3build/ids.json', idsOk);
  if (wantFrames) {
    let bad = 0, n = 0; const notes = [];
    for (const [file, fr] of frames) {
      const stem = file.replace(/\.[^.]+$/, '');
      for (const [key, [im, LT]] of fr) {
        const [z, r] = key.split(',');
        const p = path.join(golden, 'py', c, 'folder', 'sc3build', stem, `z${z}_r${r}.png`);
        n++;
        const py = await B.decodePNG(fs.readFileSync(p));
        let diff = 0;
        if (py.w !== im.w || py.h !== im.h) diff = -1;
        else {
          // the cache PNG is RGBA: decodePNG gives RGB only, so compare RGB of opaque pixels and the alpha from a raw read
          for (let q = 0; q < im.w * im.h; q++) for (let ch = 0; ch < 3; ch++) if (py.rgb[3 * q + ch] !== im.d[4 * q + ch]) { diff++; break; }
        }
        if (diff) { bad++; if (notes.length < 8) notes.push(`${stem} z${z}r${r}: ${diff < 0 ? `size ${im.w}x${im.h} vs ${py.w}x${py.h}` : diff + ' px'}`); }
      }
    }
    line(c, `frames vs python cache (${n})`, bad === 0, bad ? `${bad} differ: ${notes.join('; ')}` : '');
  }
}
const nb = results.filter(x => !x).length;
console.log(`${results.length - nb} of ${results.length} passed`);
process.exit(nb ? 1 : 0);
