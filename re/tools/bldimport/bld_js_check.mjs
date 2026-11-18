// bld_js_check.mjs - task bldfile (2026-11-18c): the .bld reader inside classifier.html against bldfile.py.
//
//   node re/tools/bldimport/bld_js_check.mjs <expected.json> <file.bld>...
//
// expected.json comes from `py -3.12 re/tools/bldimport/bldfile.py js-expect <files>` (name, lot, category, id and
// a sha256 of the preview RGBA). The page's BLD-BEGIN .. BLD-END block is plain JS with no DOM, so it runs here
// as it runs in the browser. One line per file: [N/M] <file> PASS|FAIL.
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const here = path.dirname(fileURLToPath(import.meta.url));
const html = readFileSync(path.join(here, 'classifier.html'), 'utf8');
const m = html.match(/\/\/ BLD-BEGIN[^\n]*\n([\s\S]*?)\/\/ BLD-END/);
if (!m) { console.log('classifier.html has no BLD-BEGIN .. BLD-END block'); process.exit(1); }
const api = new Function(m[1] + '\nreturn { parseBld, bldSuggest };')();

const [expPath, ...files] = process.argv.slice(2);
const exp = JSON.parse(readFileSync(expPath, 'utf8'));
let bad = 0;
files.forEach((f, k) => {
  const name = path.basename(f), want = exp[name];
  let why = '';
  try {
    const b = readFileSync(f);
    const r = api.parseBld(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength));
    const sha = createHash('sha256').update(Buffer.from(r.preview.rgba.buffer)).digest('hex');
    const s = api.bldSuggest(r);
    if (!want) why = 'no expected values';
    else {
      for (const key of ['name', 'architect', 'lot', 'category', 'ident']) if (r[key] !== want[key]) why += ` ${key} ${r[key]} != ${want[key]}`;
      if (sha !== want.preview_sha) why += ' preview pixels differ';
      if (r.preview.w !== 200 || r.preview.h !== 200) why += ` preview ${r.preview.w}x${r.preview.h}`;
      if (s.set.class !== want.class) why += ` class ${s.set.class} != ${want.class}`;
    }
  } catch (e) { why = ' ' + (e.message || e); }
  if (why) bad++;
  console.log(`[${k + 1}/${files.length}] ${name} ${why ? 'FAIL' + why : 'PASS'}`);
});
console.log(`${files.length - bad} of ${files.length} passed`);
process.exit(bad ? 1 : 0);
