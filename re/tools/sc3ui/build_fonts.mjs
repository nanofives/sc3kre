#!/usr/bin/env node
/* build_fonts.mjs - gamefont (round 2026-11-19d): the game's UI fonts as published web fonts, built once.

   Owner call 2026-11-19: every page uses the game's own fonts (risk accepted). The .FBF files never enter the repo:
   this script reads them from a game install and writes only the built web fonts to docs/assets/fonts/.

   Same code path as the importer's run-time builder: re/tools/bldimport/sc3font.js (parseFBF + buildTTF: full-ink
   pixels as rectangles, partial pixels as full-height bars, every glyph also a COLR v1 glyph in the text colour so
   Chrome rasterises it exactly). The partial-bar widths come from the table Chrome draws (sc3font.js calibrate()),
   measured once with --measure and kept in font_calibration.json, so the build is reproducible.

   Output: one WOFF2 per font. WOFF2 with the null transform on every table (glyf / loca kept as they are, the whole
   table stream compressed with brotli from node's own zlib): no dependency, and it carries COLR / CPAL unchanged.

     node re/tools/sc3ui/build_fonts.mjs --game <install> [--out docs/assets/fonts] [--measure] [--ttf <dir>]
     node re/tools/sc3ui/build_fonts.mjs --game <install> --check      # exit 1 when docs/assets/fonts differs

   --measure  re-measures the calibration in headless Chrome (font_calib.html) and rewrites font_calibration.json
   --ttf DIR  also writes the plain TTFs there (for size comparison; keep DIR outside the repo)
*/
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import zlib from 'node:zlib';
import { execFileSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';
import os from 'node:os';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..', '..', '..');
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const CALIB = path.join(HERE, 'font_calibration.json');
// FBF -> published file. Family names inside the files; sc3ui.css maps them to roles (UI_STYLE.md "Game fonts").
export const FONTS = ['MAIN9', 'MAIN10', 'SYSTEM9', 'TITLE9', 'TITLE12', 'SERIF17'];

function args() {
  const a = { out: path.join(ROOT, 'docs', 'assets', 'fonts'), lang: 'ENGLISH' };
  const v = process.argv.slice(2);
  for (let i = 0; i < v.length; i++) {
    const k = v[i];
    if (k === '--game') a.game = v[++i]; else if (k === '--out') a.out = v[++i]; else if (k === '--ttf') a.ttf = v[++i];
    else if (k === '--lang') a.lang = v[++i]; else if (k === '--measure') a.measure = true; else if (k === '--check') a.check = true;
    else throw new Error('unknown argument ' + k);
  }
  if (!a.game) throw new Error('--game <install> is required');
  return a;
}

function loadSC3Font() {
  const src = fs.readFileSync(path.join(ROOT, 're', 'tools', 'bldimport', 'sc3font.js'), 'utf8');
  const ctx = { console };
  ctx.globalThis = ctx;
  vm.createContext(ctx);
  vm.runInContext(src, ctx, { filename: 'sc3font.js' });
  return ctx.SC3Font;
}

function measure() {
  const prof = fs.mkdtempSync(path.join(os.tmpdir(), 'sc3calib'));
  const dom = execFileSync(CHROME, ['--headless=new', '--force-device-scale-factor=1', '--allow-file-access-from-files',
    '--user-data-dir=' + prof, '--virtual-time-budget=10000', '--dump-dom', pathToFileURL(path.join(HERE, 'font_calib.html')).href],
    { encoding: 'utf8', timeout: 120000 });
  const m = /<pre id="result">(.*?)<\/pre>/s.exec(dom);
  const r = m && JSON.parse(m[1].replace(/&quot;/g, '"').replace(/&amp;/g, '&'));
  if (!r || !r.got) throw new Error('calibration failed: ' + (r && r.why));
  const ver = /Chrome\/([\d.]+)/.exec(r.ua);
  const out = { note: 'sc3font.js calibrate() in headless Chrome: got[k] = coverage drawn by a centred full-height bar k/64 of a pixel wide (build_fonts.mjs --measure)',
    chrome: ver ? ver[1] : r.ua, measured: new Date().toISOString().slice(0, 10), got: r.got.map(x => +x.toFixed(4)) };
  fs.writeFileSync(CALIB, JSON.stringify(out, null, 1) + '\n');
  return out;
}

// ------------------------------------------------------------------ WOFF2 (null transform)
const KNOWN = ['cmap', 'head', 'hhea', 'hmtx', 'maxp', 'name', 'OS/2', 'post', 'cvt ', 'fpgm', 'glyf', 'loca', 'prep', 'CFF ',
  'VORG', 'EBDT', 'EBLC', 'gasp', 'hdmx', 'kern', 'LTSH', 'PCLT', 'VDMX', 'vhea', 'vmtx', 'BASE', 'GDEF', 'GPOS', 'GSUB', 'EBSC',
  'JSTF', 'MATH', 'CBDT', 'CBLC', 'COLR', 'CPAL', 'SVG ', 'sbix', 'acnt', 'avar', 'bdat', 'bloc', 'bsln', 'cvar', 'fdsc', 'feat',
  'fmtx', 'fvar', 'gvar', 'hsty', 'just', 'lcar', 'mort', 'morx', 'opbd', 'prop', 'trak', 'Zapf', 'Silf', 'Glat', 'Gloc', 'Feat', 'Sill'];
function base128(v) {
  const out = [];
  do { out.unshift(v & 0x7f); v = Math.floor(v / 128); } while (v > 0);
  for (let i = 0; i < out.length - 1; i++) out[i] |= 0x80;
  return out;
}
export function woff2(ttf) {
  const b = Buffer.from(ttf), n = b.readUInt16BE(4), tables = [];
  for (let i = 0; i < n; i++) {
    const o = 12 + i * 16;
    tables.push({ tag: b.toString('latin1', o, o + 4), off: b.readUInt32BE(o + 8), len: b.readUInt32BE(o + 12) });
  }
  // glyf must come before loca; keep the sfnt order otherwise (sorted by tag, which already puts glyf before loca)
  const dir = [], data = [];
  let sfnt = 12 + 16 * n;
  for (const t of tables) {
    const k = KNOWN.indexOf(t.tag), nullT = (t.tag === 'glyf' || t.tag === 'loca') ? 3 : 0;
    if (k >= 0) dir.push((nullT << 6) | k); else { dir.push((nullT << 6) | 63); for (const ch of t.tag) dir.push(ch.charCodeAt(0)); }
    dir.push(...base128(t.len));
    data.push(b.subarray(t.off, t.off + t.len));
    sfnt += (t.len + 3) & ~3;
  }
  const comp = zlib.brotliCompressSync(Buffer.concat(data), { params: {
    [zlib.constants.BROTLI_PARAM_QUALITY]: 11, [zlib.constants.BROTLI_PARAM_LGWIN]: 22, [zlib.constants.BROTLI_PARAM_MODE]: zlib.constants.BROTLI_MODE_FONT } });
  const hdr = Buffer.alloc(48), body = Buffer.concat([Buffer.from(dir), comp]);
  const total = (48 + body.length + 3) & ~3;
  hdr.write('wOF2', 0, 'latin1'); hdr.writeUInt32BE(b.readUInt32BE(0), 4); hdr.writeUInt32BE(total, 8);
  hdr.writeUInt16BE(n, 12); hdr.writeUInt16BE(0, 14); hdr.writeUInt32BE(sfnt, 16); hdr.writeUInt32BE(comp.length, 20);
  hdr.writeUInt16BE(1, 24); hdr.writeUInt16BE(0, 26);                // version 1.0; no metadata, no private block
  return Buffer.concat([hdr, body, Buffer.alloc(total - 48 - body.length)]);
}

function findFBF(dir, name) {
  const hit = fs.readdirSync(dir).find(f => f.toLowerCase() === name.toLowerCase() + '.fbf');
  return hit ? path.join(dir, hit) : null;
}

function main() {
  const a = args();
  const S = loadSC3Font();
  const cal = a.measure ? measure() : JSON.parse(fs.readFileSync(CALIB, 'utf8'));
  const side = S.sideFrom(cal.got);
  const dir = path.join(a.game, 'Apps', 'Res', 'Text', a.lang);
  const built = {};
  for (const nm of FONTS) {
    const p = findFBF(dir, nm);
    if (!p) throw new Error(nm + '.FBF not found in ' + dir);
    const t = S.buildTTF(fs.readFileSync(p), 'SC3 ' + nm, { side });
    const ttf = Buffer.from(t.buffer);
    built[nm] = { ttf, woff2: woff2(ttf), info: t };
  }
  const report = [];
  let differ = 0;
  if (!a.check) fs.mkdirSync(a.out, { recursive: true });
  if (a.ttf) fs.mkdirSync(a.ttf, { recursive: true });
  for (const [nm, x] of Object.entries(built)) {
    const dst = path.join(a.out, nm + '.woff2');
    if (a.check) {
      const same = fs.existsSync(dst) && Buffer.compare(fs.readFileSync(dst), x.woff2) === 0;
      if (!same) differ++;
      report.push(`${nm}.woff2 ${same ? 'identical' : 'DIFFERS'}`);
    } else {
      fs.writeFileSync(dst, x.woff2);
      if (a.ttf) fs.writeFileSync(path.join(a.ttf, nm + '.ttf'), x.ttf);
      report.push(`${nm}.woff2 ${x.woff2.length} bytes (TTF ${x.ttf.length}, ${x.info.glyphs} glyphs, line ${x.info.line} px, baseline ${x.info.base}, ${x.info.oneBit ? '1-bit' : 'anti-aliased'})`);
    }
  }
  console.log(report.join('\n'));
  console.log('calibration: Chrome ' + cal.chrome + ' (' + cal.measured + ')');
  if (a.check) process.exit(differ ? 1 : 0);
}

main();
