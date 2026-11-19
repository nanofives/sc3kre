// quick: convert a folder or zip in node, write the files to --out
import fs from 'node:fs'; import path from 'node:path'; import { createRequire } from 'node:module';
const req = createRequire(import.meta.url); const B = req('../bldweb.js'); const W = req('../sc4web.js');
const [src, out] = process.argv.slice(2);
function walk(d, pre = '', o = []) { for (const e of fs.readdirSync(d, { withFileTypes: true })) { const p = path.join(d, e.name); if (e.isDirectory()) walk(p, pre + e.name + '/', o); else o.push({ path: pre + e.name, bytes: async () => new Uint8Array(fs.readFileSync(p)) }); } return o; }
const inputs = fs.statSync(src).isDirectory() ? walk(src) : [{ path: path.basename(src), bytes: async () => new Uint8Array(fs.readFileSync(src)) }];
const t0 = Date.now();
const sources = await W.sourcesFrom(inputs);
const r = await W.convert(sources, { log: s => console.log(s) });
console.log(((Date.now() - t0) / 1000).toFixed(1) + ' s');
fs.mkdirSync(out, { recursive: true });
for (const [k, v] of r.files) fs.writeFileSync(path.join(out, k), v);
