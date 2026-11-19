// sc3pack_golden.mjs - task sc3compat-b (2026-11-19e): the page's pack reader (sc3pack.js) against sc3pack.py.
//
//   node sc3pack_golden.mjs --golden <work>\sc3pack --game <pristine game tree>
//
// <work>\sc3pack is what sc3pack_golden.py wrote. For every pack in packs.json: the page opens it the way the player
// gives it (a .zip as one File, a folder as a webkitdirectory File list), and its report with the game (a listFS
// view, as the page gets from a folder pick) and without one must be byte-identical to the Python JSON. Then the
// install run (install, install again with overwrite + a picked kind, remove) on a listFS view of the pristine game:
// every snapshot (log + sha256 of every file under Apps/BACustom and mods/netmod/sc3pack) = the Python one.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { DirHandle } from './nodefs.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const req = createRequire(import.meta.url);
const B = req(path.join(here, '..', 'bldweb.js'));
const P = req(path.join(here, '..', 'sc3pack.js'));
const arg = (k, d = null) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const golden = arg('golden'), tree = arg('game');
function walk(d, base = d, out = []) {
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    const p = path.join(d, e.name);
    if (e.isDirectory()) walk(p, base, out); else out.push(path.relative(base, p).split(path.sep).join('/'));
  }
  return out.sort();
}
const lazyFile = (root, rel, top) => {
  const p = path.join(root, ...rel.split('/')), size = fs.statSync(p).size;
  const rd = (a, b) => { const n = Math.max(0, Math.min(b, size) - a); const buf = Buffer.alloc(n); if (n) { const fd = fs.openSync(p, 'r'); fs.readSync(fd, buf, 0, n, a); fs.closeSync(fd); } return buf.buffer.slice(buf.byteOffset, buf.byteOffset + n); };
  return { name: path.basename(p), size, webkitRelativePath: top ? top + '/' + rel : '', arrayBuffer: async () => rd(0, size), slice: (a = 0, b = size) => ({ arrayBuffer: async () => rd(a, b) }) };
};
const packs = JSON.parse(fs.readFileSync(path.join(golden, 'packs.json'), 'utf8'));
const inst = JSON.parse(fs.readFileSync(path.join(golden, 'install.json'), 'utf8'));
const total = packs.length * 2 + inst.snapshots.length * 2 + 1;
let k = 0, bad = 0;
const line = (what, ok, extra = '') => { k++; bad += !ok; console.log(`[${k}/${total}] ${what} ${ok ? 'PASS' : 'FAIL'}${extra ? ' ' + extra : ''}`); };
function firstDiff(a, b) {
  let i = 0; while (i < a.length && a[i] === b[i]) i++;
  const ln = a.slice(0, i).split('\n').length;
  return `line ${ln}: page ${JSON.stringify(a.split('\n')[ln - 1])} / py ${JSON.stringify(b.split('\n')[ln - 1])}`;
}
// the game as the page gets it from a folder pick: only what the reader looks at (Apps/Res/BA, Apps/BACustom)
const gameFiles = () => ['Apps/Res/BA', 'Apps/BACustom'].flatMap(r => walk(path.join(tree, ...r.split('/'))).map(x => r + '/' + x)).map(r => lazyFile(tree, r, 'SimCity 3000 Unlimited'));
const game = B.listFS(gameFiles());
async function open(p) {
  if (fs.statSync(p).isDirectory()) return P.openFiles(walk(p).map(r => lazyFile(p, r, path.basename(p))));
  return P.openFiles([lazyFile(path.dirname(p), path.basename(p), '')]);
}
for (let n = 0; n < packs.length; n++) {
  const t0 = Date.now();
  const ents = await open(packs[n]);
  for (const [name, g] of [['report', game], ['nogame', null]]) {
    const want = fs.readFileSync(path.join(golden, `${name}_${n}.json`), 'utf8');
    const got = P.dumps(await P.report(ents, g));
    line(`${path.basename(packs[n])} ${name === 'report' ? 'with the game' : 'no game'}: report = sc3pack.py`, got === want, got === want ? `(${ents.length} files, ${((Date.now() - t0) / 1000).toFixed(1)} s)` : firstDiff(got, want));
  }
}
async function snapshot(g, res) {
  const files = {};
  for (const root of ['Apps/BACustom', 'mods/netmod/sc3pack']) {
    const rels = [];
    const rec = async rel => { for (const n of (await g.listdir(rel)).slice().sort((a, b) => { const x = a.toLowerCase(), y = b.toLowerCase(); return x < y ? -1 : x > y ? 1 : a < b ? -1 : a > b ? 1 : 0; })) { const r = rel + '/' + n; if (await g.exists(r)) rels.push(r); else await rec(r); } };
    await rec(root);
    // listFS.listdir does not show folders that only exist in its in-memory writes (mods/netmod/sc3pack/backup/..)
    if (g.writes) for (const [, [rel]] of g.writes) if (rel.toLowerCase().startsWith(root.toLowerCase() + '/') && !rels.includes(rel) && await g.exists(rel)) rels.push(rel);
    for (const r of rels) files[r] =crypto.createHash('sha256').update(await g.read(r)).digest('hex');
  }
  return { log: res.log, files };
}
const ents = await open(inst.pack);
const snaps = [await snapshot(game, { log: [] })];
snaps.push(await snapshot(game, await P.install(game, ents, inst.name)));
snaps.push(await snapshot(game, await P.install(game, ents, inst.name, inst.overwrite, inst.kinds)));
snaps.push(await snapshot(game, await P.remove(game)));
const steps = ['before', 'install', 'install with overwrite + kind', 'remove'];
for (let s = 0; s < snaps.length; s++) {
  const got = P.dumps(snaps[s]), want = P.dumps(inst.snapshots[s]);
  line(`install run, ${steps[s]}: log + files = sc3pack.py`, got === want, got === want ? `(${snaps[s].log.length} log lines, ${Object.keys(snaps[s].files).length} files)` : firstDiff(got, want));
}
// the same run on a real folder through the File System Access surface (handleFS over nodefs: what Chrome gives
// for a folder pick with write access): a fresh copy of BACustom, Res/BA hard-linked (writes are link-safe)
const gJ = path.join(golden, 'game_js');
fs.rmSync(gJ, { recursive: true, force: true });
fs.cpSync(path.join(tree, 'Apps', 'BACustom'), path.join(gJ, 'Apps', 'BACustom'), { recursive: true });
for (const r of walk(path.join(tree, 'Apps', 'Res', 'BA'))) {
  const d = path.join(gJ, 'Apps', 'Res', 'BA', ...r.split('/'));
  fs.mkdirSync(path.dirname(d), { recursive: true }); fs.linkSync(path.join(tree, 'Apps', 'Res', 'BA', ...r.split('/')), d);
}
const hg = B.handleFS(new DirHandle(gJ));
const hs = [await snapshot(hg, { log: [] })];
hs.push(await snapshot(hg, await P.install(hg, ents, inst.name)));
hs.push(await snapshot(hg, await P.install(hg, ents, inst.name, inst.overwrite, inst.kinds)));
hs.push(await snapshot(hg, await P.remove(hg)));
for (let s = 0; s < hs.length; s++) {
  const got = P.dumps(hs[s]), want = P.dumps(inst.snapshots[s]);
  line(`real folder (handleFS), ${steps[s]}: log + files = sc3pack.py`, got === want, got === want ? '' : firstDiff(got, want));
}
const linked = walk(path.join(gJ, 'Apps', 'Res', 'BA')).every(r => fs.statSync(path.join(gJ, 'Apps', 'Res', 'BA', ...r.split('/'))).nlink > 1);
// a folder pack opened from a folder handle (Chrome showDirectoryPicker) = the File list route
const fp = packs.find(p => fs.statSync(p).isDirectory());
const viaHandle = P.dumps(await P.report(await P.openHandle(new DirHandle(fp)), game));
line(`folder handle route (${path.basename(fp)}) = File list route, Res/BA links intact`, linked && viaHandle === fs.readFileSync(path.join(golden, `report_${packs.indexOf(fp)}.json`), 'utf8'));
console.log(`${k - bad} of ${k} checks passed`);
process.exit(bad ? 1 : 0);
