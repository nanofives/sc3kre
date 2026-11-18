// zip_golden.mjs - task bldweb (2026-11-18d): the page's .zip route (no folder write access) against bldimport.py.
//
//   node zip_golden.mjs --golden <dir> --game <tree> [--case kenney]
//
// The game folder is read as a file list (what <input webkitdirectory> gives the page: BLDWEB.listFS), the models
// folder as files too (BLDWEB.filesFS, ids.json kept in memory). Install, then the removal on the same view.
// Checks: the install .zip holds exactly the files bldimport.py would write (overlay files byte-identical to
// `pack --out`, plus state.json and the backups), ids.json = the Python tool's, and after the removal every overlay
// file is the tree's own again and the files the install created are listed for deletion.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const B = createRequire(import.meta.url)(path.join(here, '..', 'bldweb.js'));
const arg = (k, d = null) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const golden = arg('golden'), tree = arg('game'), cs = arg('case', 'kenney');
function walk(d, base = d, out = []) {
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    const p = path.join(d, e.name);
    if (e.isDirectory()) walk(p, base, out); else out.push(path.relative(base, p).split(path.sep).join('/'));
  }
  return out.sort();
}
const sha = b => crypto.createHash('sha256').update(b).digest('hex');
// a File as the browser gives it for a folder pick: lazy, sliceable, with webkitRelativePath = <folder>/<rel>
const lazyFile = (root, rel, top) => {
  const p = path.join(root, ...rel.split('/')), size = fs.statSync(p).size;
  const rd = (a, b) => { const n = Math.max(0, Math.min(b, size) - a); const buf = Buffer.alloc(n); if (n) { const fd = fs.openSync(p, 'r'); fs.readSync(fd, buf, 0, n, a); fs.closeSync(fd); } return buf.buffer.slice(buf.byteOffset, buf.byteOffset + n); };
  return { name: path.basename(p), size, webkitRelativePath: top + '/' + rel, arrayBuffer: async () => rd(0, size), slice: (a = 0, b = size) => ({ arrayBuffer: async () => rd(a, b) }) };
};
function unzip(z) {                     // stored entries only (what zipOf writes)
  const out = new Map(); let o = 0;
  while (o + 30 <= z.length && z.readUInt32LE(o) === 0x04034b50) {
    const n = z.readUInt32LE(o + 18), nl = z.readUInt16LE(o + 26), name = z.subarray(o + 30, o + 30 + nl).toString('utf8');
    out.set(name, z.subarray(o + 30 + nl, o + 30 + nl + n)); o += 30 + nl + n;
  }
  return out;
}
let k = 0, bad = 0; const total = 6;
const line = (what, ok, extra = '') => { k++; bad += !ok; console.log(`[${k}/${total}] ${what} ${ok ? 'PASS' : 'FAIL'}${extra ? ' ' + extra : ''}`); };

const game1 = B.listFS(walk(tree).map(r => lazyFile(tree, r, 'SimCity 3000 Unlimited')));
const srcDir = path.join(golden, 'src', cs), map = new Map(), names = walk(srcDir);
for (const r of names) map.set(r.toLowerCase(), new Uint8Array(fs.readFileSync(path.join(srcDir, r))));
map._names = names;
const folder = B.filesFS(map);
const t0 = Date.now();
const r = await B.install(folder, game1, {});
console.log(`  install on a file list: ${((Date.now() - t0) / 1000).toFixed(1)} s, ${r.rep[r.rep.length - 1]}`);
const z1 = unzip(Buffer.from(B.zipOf([...game1.writes.values()])));
const pyOut = path.join(golden, 'py', cs, 'out'), want = walk(pyOut);
const badFiles = want.filter(rel => !z1.has(rel) || sha(z1.get(rel)) !== sha(fs.readFileSync(path.join(pyOut, rel))));
line(`install .zip: the ${want.length} overlay files = bldimport.py pack`, !badFiles.length, badFiles.slice(0, 5).join('; '));
const others = [...z1.keys()].filter(x => !want.includes(x));
const backups = others.filter(x => x.startsWith('mods/netmod/bldimport/backup/'));
line(`install .zip: state.json + ${want.length - 1} backups, nothing else (${z1.size} entries)`,
  others.includes('mods/netmod/bldimport/state.json') && backups.length === want.length - 1 && others.length === backups.length + 1);
const ids = folder.written.get('sc3build/ids.json');
line('ids.json (offered as a download) = the Python tool\'s', !!ids && sha(ids) === sha(fs.readFileSync(path.join(golden, 'py', cs, 'folder', 'sc3build', 'ids.json'))));
// removal from a game folder where the install .zip was unpacked: the tree's files, the .zip's files over them
const unpacked = new Map(walk(tree).map(rr => [rr.toLowerCase(), lazyFile(tree, rr, 'SimCity 3000 Unlimited')]));
for (const [rel, data] of z1) unpacked.set(rel.toLowerCase(), { name: path.basename(rel), size: data.length, webkitRelativePath: 'SimCity 3000 Unlimited/' + rel,
  arrayBuffer: async () => data.buffer.slice(data.byteOffset, data.byteOffset + data.length), slice: (a = 0, b = data.length) => ({ arrayBuffer: async () => data.buffer.slice(data.byteOffset + a, data.byteOffset + Math.min(b, data.length)) }) });
const game2 = B.listFS([...unpacked.values()]);
const n = await B.restore(game2);
const game = game2;
const ovl = walk(path.join(tree, 'mods', 'netmod', 'overlay')).map(x => 'mods/netmod/overlay/' + x);
const notBack = [];
for (const rel of ovl) { const now = await game.read(rel); if (sha(now) !== sha(fs.readFileSync(path.join(tree, ...rel.split('/'))))) notBack.push(rel); }
line(`removal: ${n} files restored, every overlay file is the tree's own again`, n === want.length && !notBack.length, notBack.slice(0, 5).join('; '));
const gone = [...game.removed.values()];
line('removal: the file the install created is listed for deletion', gone.length === 1 && gone[0] === B.OVL + B.PIX_DAT, gone.join('; '));
const z2 = unzip(Buffer.from(B.zipOf([...game.writes.values()])));
line(`removal .zip has the restored files and state.json (${z2.size} entries)`, z2.has('mods/netmod/bldimport/state.json') && want.filter(x => !x.endsWith('_bldimport.DAT')).every(x => z2.has(x)));
console.log(`${total - bad} of ${total} passed`);
process.exit(bad ? 1 : 0);
