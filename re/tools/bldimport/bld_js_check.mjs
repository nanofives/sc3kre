// bld_js_check.mjs - task bldfile (2026-11-18c): the .bld readers of the page against bldfile.py.
// sc3compat-a (2026-11-19e): also bldweb.js readBld (the importer's reader), and 1999 .bld files.
//
//   node re/tools/bldimport/bld_js_check.mjs [--reader page|bldweb] <expected.json> <file.bld>...
//
// expected.json comes from `py -3.12 re/tools/bldimport/bldfile.py js-expect <files>` (name, lot, category, id,
// model fields and a sha256 of the preview RGBA). --reader page (default): the BLD-BEGIN .. BLD-END block of
// classifier.html (plain JS, no DOM). --reader bldweb: readBld of bldweb.js, every field bldfile.read_bld gives.
// One line per file: [N/M] <file> PASS|FAIL.
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const here = path.dirname(fileURLToPath(import.meta.url));
let args = process.argv.slice(2), reader = 'page';
if (args[0] === '--reader') { reader = args[1]; args = args.slice(2); }
let parse;
if (reader === 'page') {
  const html = readFileSync(path.join(here, 'classifier.html'), 'utf8');
  const m = html.match(/\/\/ BLD-BEGIN[^\n]*\n([\s\S]*?)\/\/ BLD-END/);
  if (!m) { console.log('classifier.html has no BLD-BEGIN .. BLD-END block'); process.exit(1); }
  const api = new Function(m[1] + '\nreturn { parseBld, bldSuggest };')();
  parse = (b) => {
    const r = api.parseBld(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength));
    return { r, rgba: r.preview.rgba, w: r.preview.w, h: r.preview.h, cls: api.bldSuggest(r).set.class, keys: ['name', 'architect', 'lot', 'category', 'ident'], sha: 'preview_sha' };
  };
} else if (reader === 'bldweb') {
  const B = createRequire(import.meta.url)(path.join(here, 'bldweb.js'));
  parse = (b, f) => {
    const r = B.readBld(new Uint8Array(b.buffer, b.byteOffset, b.byteLength), path.basename(f));
    const flat = Object.assign({}, r, { version: r.model.version, height: r.model.height, grid: r.model.grid, textures: r.model.textures, custom: r.custom_textures });
    return { r: flat, rgba: r.preview.d, w: r.preview.w, h: r.preview.h, cls: B.suggestClass ? B.suggestClass(r) : undefined,
      keys: ['name', 'architect', 'lot', 'category', 'ident', 'ident_from', 'version', 'height', 'grid', 'textures', 'custom'], sha: 'preview_sha_floor' };
  };
} else { console.log('--reader page|bldweb'); process.exit(2); }

const [expPath, ...files] = args;
const exp = JSON.parse(readFileSync(expPath, 'utf8'));
let bad = 0;
files.forEach((f, k) => {
  const name = path.basename(f), want = exp[name];
  let why = '';
  try {
    const p = parse(readFileSync(f), f);
    const sha = createHash('sha256').update(Buffer.from(p.rgba.buffer, p.rgba.byteOffset, p.rgba.byteLength)).digest('hex');
    if (!want) why = 'no expected values';
    else {
      for (const key of p.keys) if (p.r[key] !== want[key]) why += ` ${key} ${p.r[key]} != ${want[key]}`;
      if (sha !== want[p.sha]) why += ' preview pixels differ';
      if (p.w !== 200 || p.h !== 200) why += ` preview ${p.w}x${p.h}`;
      if (p.cls !== undefined && p.cls !== want.class) why += ` class ${p.cls} != ${want.class}`;
    }
  } catch (e) { why = ' ' + (e.message || e); }
  if (why) bad++;
  console.log(`[${k + 1}/${files.length}] ${name} ${why ? 'FAIL' + why : 'PASS'}`);
});
console.log(`${reader}: ${files.length - bad} of ${files.length} passed`);
process.exit(bad ? 1 : 0);
