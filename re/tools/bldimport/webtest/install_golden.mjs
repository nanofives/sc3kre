// install_golden.mjs - task bldweb (2026-11-18d): install, re-install and restore by the page's code against
// bldimport.py build / restore, on two hard-linked copies of a game tree.
//
//   node install_golden.mjs --golden <dir> --game <tree> [--case kenney] [--py <python exe>]
//
// Steps, the same on both sides: install <case>; edit models.json (weight of the first entry 7, the second disabled)
// and install again; restore. After each step every file under mods\netmod (overlay, bldimport\state.json,
// bldimport\backup\...) and sc3build\ids.json must be byte-identical. After the restore the overlay must equal the
// tree's own files again, and the tree itself (hard-link source) must be untouched by both tools.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { DirHandle } from './nodefs.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const B = createRequire(import.meta.url)(path.join(here, '..', 'bldweb.js'));
const arg = (k, d = null) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const golden = arg('golden'), tree = arg('game'), cs = arg('case', 'kenney');
const py = arg('py', process.env.LOCALAPPDATA + '\\Programs\\Python\\Python312\\python.exe');
const TOOL = path.join(here, '..', 'bldimport.py');

function walk(d, base = d, out = []) {
  if (!fs.existsSync(d)) return out;
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    const p = path.join(d, e.name);
    if (e.isDirectory()) walk(p, base, out); else out.push(path.relative(base, p).split(path.sep).join('/'));
  }
  return out.sort();
}
const sha = p => crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
function linkTree(src, dst) {
  fs.rmSync(dst, { recursive: true, force: true });
  for (const rel of walk(src)) { const t = path.join(dst, rel); fs.mkdirSync(path.dirname(t), { recursive: true }); fs.linkSync(path.join(src, rel), t); }
}
const work = path.join(golden, 'install', cs);
const gP = path.join(work, 'gameP'), gJ = path.join(work, 'gameJ'), fP = path.join(work, 'folderP'), fJ = path.join(work, 'folderJ');
const before = new Map(walk(path.join(tree, 'mods')).map(r => [r, sha(path.join(tree, 'mods', r))]));
linkTree(tree, gP); linkTree(tree, gJ);
for (const f of [fP, fJ]) { fs.rmSync(f, { recursive: true, force: true }); fs.cpSync(path.join(golden, 'src', cs), f, { recursive: true }); }

const steps = ['install', 'edit + install again', 'restore'];
const total = steps.length * 2 + 2;
let k = 0, bad = 0;
const line = (what, ok, extra = '') => { k++; bad += !ok; console.log(`[${k}/${total}] ${what} ${ok ? 'PASS' : 'FAIL'}${extra ? ' ' + extra : ''}`); };
function compare(step) {
  const a = walk(path.join(gP, 'mods', 'netmod')), b = walk(path.join(gJ, 'mods', 'netmod'));
  const diff = [];
  for (const r of new Set([...a, ...b])) {
    const pa = path.join(gP, 'mods', 'netmod', r), pb = path.join(gJ, 'mods', 'netmod', r);
    if (!fs.existsSync(pa) || !fs.existsSync(pb) || sha(pa) !== sha(pb)) diff.push(r + (!fs.existsSync(pa) ? ' (only page)' : !fs.existsSync(pb) ? ' (only python)' : ''));
  }
  line(`${step}: ${a.length} files under mods/netmod`, !diff.length, diff.slice(0, 6).join('; '));
  const ia = path.join(fP, 'sc3build', 'ids.json'), ib = path.join(fJ, 'sc3build', 'ids.json');
  line(`${step}: sc3build/ids.json`, fs.existsSync(ia) === fs.existsSync(ib) && (!fs.existsSync(ia) || sha(ia) === sha(ib)));
}
const jsGame = () => B.handleFS(new DirHandle(gJ)), jsFolder = () => B.handleFS(new DirHandle(fJ));
const runPy = (...a) => execFileSync(py, [TOOL, ...a], { encoding: 'utf8' });

// 1 install
console.log(runPy('build', fP, '--game', gP).trim().split('\n').slice(-3).join('\n'));
let r = await B.install(jsFolder(), jsGame(), {});
console.log('page: ' + r.rep[r.rep.length - 1] + ', ' + Object.keys(r.state.files).length + ' files in state.json');
compare(steps[0]);
// 2 edit + install again
for (const f of [fP, fJ]) {
  const p = path.join(f, 'models.json'), j = JSON.parse(fs.readFileSync(p, 'utf8'));
  j.models[0].weight = 7; j.models[1].enabled = false;
  fs.writeFileSync(p, JSON.stringify(j, null, 1));
}
console.log(runPy('build', fP, '--game', gP).trim().split('\n').slice(-3).join('\n'));
r = await B.install(jsFolder(), jsGame(), {});
console.log('page: ' + r.rep[r.rep.length - 1]);
compare(steps[1]);
// 3 restore
console.log(runPy('restore', '--game', gP).trim());
console.log('page: restored ' + await B.restore(jsGame()) + ' file(s)');
compare(steps[2]);
// the overlay is the tree's own again, and the tree was never written through a hard link
const ovl = walk(path.join(tree, 'mods', 'netmod', 'overlay'));
const back = ovl.filter(rr => sha(path.join(tree, 'mods', 'netmod', 'overlay', rr)) !== sha(path.join(gJ, 'mods', 'netmod', 'overlay', rr)));
const extra = walk(path.join(gJ, 'mods', 'netmod', 'overlay')).filter(rr => !ovl.includes(rr));
line('after restore the page copy overlay = the tree overlay', !back.length && !extra.length, [...back, ...extra.map(x => x + ' (extra)')].slice(0, 6).join('; '));
const changed = [...before].filter(([rr, h]) => !fs.existsSync(path.join(tree, 'mods', rr)) || sha(path.join(tree, 'mods', rr)) !== h).map(([rr]) => rr);
line(`hard-link source tree untouched (${before.size} files under mods)`, !changed.length, changed.slice(0, 6).join('; '));
console.log(`${total - bad} of ${total} passed`);
process.exit(bad ? 1 : 0);
