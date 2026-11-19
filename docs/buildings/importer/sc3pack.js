// sc3pack.js - task sc3compat-b (round 2026-11-19e): the classifier page's pack reader. A transcription of
// sc3pack.py (same JSON, byte for byte: webtest/sc3pack_golden.mjs), plus the page view (SC3PACK.view).
//
//   open      a pack as downloaded: a .zip, a folder (a File list or a folder handle), a .zip inside a .zip (3 levels)
//   sort      building (.bld, version 8 SC3U or 7 1999), part (BA .tga / .bmp / prop .met), plugin (.pin + .dat,
//             identified only), readme, other (with a note)
//   report    per .bld: every texture name of its model resolved as the BA renderer does (verify/bldbat/RESULTS.md
//             step 3): color, embedded, stock (Apps/Res/BA), pack, custom (Apps/BACustom), missing; same-named files
//             byte-compared (pack against Apps/BACustom, pack against pack)
//   install   parts into Apps/BACustom/<Paints|Details|Props>, never over a different same-named file unless the
//             player named it in `overwrite`; backups + state in mods/netmod/sc3pack (bldimport's scheme); remove
//
// The game folder is any BLDWEB folder view (handleFS: File System Access, listFS: a file list with the writes kept
// in memory, then BLDWEB.zipOf(writes) is the .zip the player unpacks).
function SC3PACK_LIB(BLDWEB) {
  'use strict';
  const VERSION = '2026-11-19e';
  const MAGIC = 0x80C381D7, B_GROUP = 0xC3F8D4A9, FREE = 0xFFFFFFFF;
  const T_MODEL = 0xE3F87B0C, I_MODEL = 0xA3F8D615, T_INFO = 0xE3F87B0F, I_INFO = 0x63FBE1CC, T_TEXINFO = 0xE3F87B0D;
  const SEP = 0xEAEAEAEA;
  const PART_KIND = { 6: 'paint', 7: 'detail', 16: 'prop' };
  const KIND_DIR = { paint: 'Paints', detail: 'Details', prop: 'Props' };
  const FOLDER_KIND = { paints: 'paint', details: 'detail', props: 'prop' };
  const README_EXT = ['.txt', '.doc', '.rtf', '.htm', '.html', '.pdf', '.nfo', '.wri', '.md'];
  const INSTALLER_EXT = ['.cab', '.hdr', '.ins', '.lid', '.tag', '.inx', '.ex_', '.dl_', '.bin', '.ini', '.dll'];
  const STATE_DIR = 'mods/netmod/sc3pack', MAX_DEPTH = 3, ZIP_BAD = 'not a readable .zip';

  class PackError extends Error {}
  const sha = b => BLDWEB.sha256(b);
  const cmpKey = (a, b) => { const x = a.toLowerCase(), y = b.toLowerCase(); return x < y ? -1 : x > y ? 1 : a < b ? -1 : a > b ? 1 : 0; };
  const cmpStr = (a, b) => a < b ? -1 : a > b ? 1 : 0;
  const bytesEq = (a, b) => { if (a === b) return true; if (!a || !b || a.length !== b.length) return false; for (let k = 0; k < a.length; k++) if (a[k] !== b[k]) return false; return true; };
  const ascii = s => { const b = new Uint8Array(s.length); for (let k = 0; k < s.length; k++) b[k] = s.charCodeAt(k) & 255; return b; };
  const latin1 = b => { let s = ''; for (let k = 0; k < b.length; k += 8192) s += String.fromCharCode.apply(null, b.subarray(k, k + 8192)); return s; };
  const CP437_HI = 'ÇüéâäàåçêëèïîìÄÅÉæÆôöòûùÿÖÜ¢£¥₧ƒáíóúñÑªº¿⌐¬½¼¡«»░▒▓│┤╡╢╖╕╣║╗╝╜╛┐└┴┬├─┼╞╟╚╔╩╦╠═╬╧╨╤╥╙╘╒╓╫╪┘┌█▄▌▐▀αßΓπΣσµτΦΘΩδ∞φε∩≡±≥≤⌠⌡÷≈°∙·√ⁿ²■\u00a0';
  const cp437 = b => { let s = ''; for (const c of b) s += c < 128 ? String.fromCharCode(c) : CP437_HI[c - 128]; return s; };
  // Python str semantics over latin-1 text (str.strip / str.splitlines whitespace and line breaks)
  const PY_WS = ' \t\n\x0b\x0c\r\x1c\x1d\x1e\x1f\x85\xa0';
  const pyStrip = (s, ws = PY_WS) => { let a = 0, e = s.length; while (a < e && ws.includes(s[a])) a++; while (e > a && ws.includes(s[e - 1])) e--; return s.slice(a, e); };
  function pySplitlines(s) {
    const out = []; let cur = '';
    for (let k = 0; k < s.length; k++) {
      const c = s[k];
      if (c === '\r') { out.push(cur); cur = ''; if (s[k + 1] === '\n') k++; }
      else if ('\n\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029'.includes(c)) { out.push(cur); cur = ''; }
      else cur += c;
    }
    if (cur) out.push(cur);
    return out;
  }
  function u32(b, o) { if (o < 0 || o + 4 > b.length) throw new RangeError('read past the end'); return (b[o] | (b[o + 1] << 8) | (b[o + 2] << 16) | (b[o + 3] << 24)) >>> 0; }
  function u16(b, o) { if (o + 2 > b.length) throw new RangeError('read past the end'); return b[o] | (b[o + 1] << 8); }
  const hex8 = v => '0x' + (v >>> 0).toString(16).toUpperCase().padStart(8, '0');
  const keyOf = (g, i, t) => g + ':' + i + ':' + t;

  // ================================================================================================ open
  async function inflateRaw(data) {
    if (typeof DecompressionStream === 'undefined') throw new PackError('this browser cannot unpack .zip files (no DecompressionStream)');
    const ds = new DecompressionStream('deflate-raw');
    return new Uint8Array(await new Response(new Blob([data]).stream().pipeThrough(ds)).arrayBuffer());
  }
  function zipDir(z) {
    let eo = -1;
    for (let p = z.length - 22; p >= Math.max(0, z.length - 22 - 65535); p--) if (z[p] === 0x50 && z[p + 1] === 0x4B && z[p + 2] === 5 && z[p + 3] === 6) { eo = p; break; }
    if (eo < 0) throw new PackError(ZIP_BAD);
    const n = u16(z, eo + 10); let p = u32(z, eo + 16);
    const out = [];
    for (let k = 0; k < n; k++) {
      if (p + 46 > z.length || u32(z, p) !== 0x02014b50) throw new PackError(ZIP_BAD);
      const flags = u16(z, p + 8), method = u16(z, p + 10), crc = u32(z, p + 16), csize = u32(z, p + 20), usize = u32(z, p + 24);
      const nl = u16(z, p + 28), xl = u16(z, p + 30), cl = u16(z, p + 32), lho = u32(z, p + 42);
      const raw = z.subarray(p + 46, p + 46 + nl);
      let name = flags & 0x800 ? new TextDecoder('utf-8').decode(raw) : cp437(raw);
      const nb = name.indexOf('\0'); if (nb >= 0) name = name.slice(0, nb);
      name = name.split('\\').join('/');
      out.push({ name, raw, method, flags, crc, csize, usize, lho });
      p += 46 + nl + xl + cl;
    }
    return out;
  }
  async function zipRead(z, e) {
    if (e.lho + 30 > z.length || u32(z, e.lho) !== 0x04034b50) throw new PackError('broken .zip entry');
    const nl = u16(z, e.lho + 26), xl = u16(z, e.lho + 28);
    if (!bytesEq(z.subarray(e.lho + 30, e.lho + 30 + nl), e.raw)) throw new PackError('broken .zip entry');
    const start = e.lho + 30 + nl + xl;
    if (start + e.csize > z.length) throw new PackError('broken .zip entry');
    const raw = z.subarray(start, start + e.csize);
    let out;
    try { out = e.method === 0 ? raw : await inflateRaw(raw); } catch (x) { throw new PackError('broken .zip entry'); }
    if (out.length !== e.usize || ((BLDWEB_CRC(out) ^ 0xFFFFFFFF) >>> 0) !== e.crc) throw new PackError('broken .zip entry');
    return out;
  }
  let CRC_T = null;
  function BLDWEB_CRC(b) {
    if (!CRC_T) { CRC_T = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; CRC_T[n] = c >>> 0; } }
    let c = 0xFFFFFFFF; for (let k = 0; k < b.length; k++) c = CRC_T[(c ^ b[k]) & 255] ^ (c >>> 8); return c >>> 0;
  }
  async function zipEntries(data, prefix, depth, out) {
    const dir = zipDir(data);
    for (const e of dir) {
      if (e.name.endsWith('/')) continue;
      const path = prefix + e.name.split('/').filter(Boolean).join('/');
      if (e.flags & 1) { out.push({ path, error: 'encrypted .zip entry' }); continue; }
      if (e.method !== 0 && e.method !== 8) { out.push({ path, error: '.zip method ' + e.method + ' is not read' }); continue; }
      let b;
      try { b = await zipRead(data, e); } catch (x) { out.push({ path, error: 'broken .zip entry' }); continue; }
      await add(path, b, depth, out);
    }
  }
  async function add(path, b, depth, out) {
    if (path.toLowerCase().endsWith('.zip') && depth < MAX_DEPTH) {
      const sub = [];
      try { await zipEntries(b, path + '/', depth + 1, sub); }
      catch (x) { if (!(x instanceof PackError) && !(x instanceof RangeError)) throw x; out.push({ path, data: b, error: ZIP_BAD }); return; }
      out.push({ path, data: b, archive: true });
      out.push(...sub);
    } else out.push({ path, data: b });
  }
  const sorted = out => out.sort((a, b) => cmpKey(a.path, b.path));
  // inputs: [{ path, bytes: async () => Uint8Array }] (a folder's files, paths relative to the folder)
  async function openFolder(inputs) {
    const out = [];
    for (const it of inputs) await add(it.path, await it.bytes(), 0, out);
    return sorted(out);
  }
  async function openZip(bytes) {
    const out = [];
    try { await zipEntries(bytes, '', 1, out); } catch (x) { if (x instanceof RangeError) throw new PackError(ZIP_BAD); throw x; }
    return sorted(out);
  }
  // what the page gets: one picked .zip (File), a webkitdirectory File list, or a folder handle
  async function openFiles(files) {
    files = [...files];
    if (files.length === 1 && !files[0].webkitRelativePath && /\.zip$/i.test(files[0].name)) return openZip(new Uint8Array(await files[0].arrayBuffer()));
    return openFolder(files.map(f => {
      const parts = String(f.webkitRelativePath || f.name).split('/'); if (parts.length > 1) parts.shift();
      return { path: parts.join('/'), bytes: async () => new Uint8Array(await f.arrayBuffer()) };
    }));
  }
  async function handleInputs(dir, pre = '', out = []) {
    for await (const [name, h] of dir.entries()) {
      if (h.kind === 'directory') await handleInputs(h, pre + name + '/', out);
      else out.push({ path: pre + name, bytes: async () => new Uint8Array(await (await h.getFile()).arrayBuffer()) });
    }
    return out;
  }
  const openHandle = async dir => openFolder(await handleInputs(dir));

  // ================================================================================================ file checks
  function ixfIndex(b) {
    if (b.length < 24 || u32(b, 0) !== MAGIC) return null;
    const out = new Map(); let o = 4;
    while (o + 20 <= b.length) {
      const g = u32(b, o), i = u32(b, o + 4), t = u32(b, o + 8), off = u32(b, o + 12), sz = u32(b, o + 16); o += 20;
      if (g === 0 && i === 0 && t === 0) return out;
      if (t === FREE || off === FREE || sz === FREE) continue;
      if (off + sz > b.length) throw new PackError('record runs past the end of the file');
      const k = keyOf(g, i, t); if (!out.has(k)) out.set(k, [g, i, t, off, sz]);
    }
    throw new PackError('IXF index has no terminator');
  }
  const isTga = b => b.length >= 18 && (b[1] === 0 || b[1] === 1) && [1, 2, 3, 9, 10, 11].includes(b[2]) && u16(b, 12) > 0 && u16(b, 14) > 0 && [8, 15, 16, 24, 32].includes(b[16]);
  const isBmp = b => b.length >= 26 && b[0] === 0x42 && b[1] === 0x4D && [12, 40, 52, 56, 108, 124].includes(u32(b, 14));
  const MET_HEAD = /^[ \t]*[0-9]+[ \t]*,[ \t]*[0-9]+[ \t]*,[ \t]*[0-9]+[ \t]*:/;
  const HEX = /^[ \t]*(?:0[xX])?[0-9A-Fa-f]{1,8}[ \t]*$/;
  function metNames(b) {
    const lines = pySplitlines(latin1(b)).filter(ln => pyStrip(ln));
    if (!lines.length || !MET_HEAD.test(lines[0])) return null;
    const names = [];
    for (const ln of lines) for (const m of ln.matchAll(/"([^"]+)"/g)) if (!names.includes(m[1])) names.push(m[1]);
    return names;
  }
  function parsePin(b) {
    const out = {}; let cur = null;
    for (const ln of pySplitlines(latin1(b))) {
      const s = pyStrip(ln);
      if (!s || s.startsWith(';')) continue;
      if (s.startsWith('[') && s.endsWith(']')) { cur = pyStrip(s.slice(1, -1)).toLowerCase(); if (!(cur in out)) out[cur] = []; }
      else if (s.includes('=') && cur !== null) { const j = s.indexOf('='); out[cur].push([pyStrip(s.slice(0, j)), pyStrip(s.slice(j + 1))]); }
    }
    return out;
  }
  function pstr8(p, o) {
    if (o >= p.length) throw new PackError('info record too short');
    const n = p[o]; if (o + 1 + n > p.length) throw new PackError('info record too short');
    return [p.subarray(o + 1, o + 1 + n), o + 1 + n];
  }
  // cp1252 with errors="replace" (Python codec: 0x81 0x8D 0x8F 0x90 0x9D undefined); bldweb.js keeps its copy private
  const CP1252_HI = [0x20AC, -1, 0x201A, 0x0192, 0x201E, 0x2026, 0x2020, 0x2021, 0x02C6, 0x2030, 0x0160, 0x2039, 0x0152, -1, 0x017D, -1,
    -1, 0x2018, 0x2019, 0x201C, 0x201D, 0x2022, 0x2013, 0x2014, 0x02DC, 0x2122, 0x0161, 0x203A, 0x0153, -1, 0x017E, 0x0178];
  const cpDec = b => { let s = ''; for (const x of b) { const c = x >= 0x80 && x < 0xA0 ? CP1252_HI[x - 0x80] : x; s += c < 0 ? '�' : String.fromCharCode(c); } return s; };
  function readBld(b, idx) {
    const rec = (i, t) => { const e = idx.get(keyOf(B_GROUP, i, t)); return e ? b.subarray(e[3], e[3] + e[4]) : null; };
    const m = rec(I_MODEL, T_MODEL), info = rec(I_INFO, T_INFO);
    if (!m) throw new PackError('no model record');
    if (!info) throw new PackError('no info record');
    if (!info.length) throw new RangeError('empty');
    const lot = info[0];
    let [name, o] = pstr8(info, 1); let arch; [arch, o] = pstr8(info, o);
    if (m.length < 5) throw new RangeError('short');
    const ver = m[0], n = m[2];
    if ((ver !== 7 && ver !== 8) || m.length < 0x21 || m[4] !== 0xEA || u32(m, 0x1D) !== n * n * 4) throw new PackError('model record header is not version 7 or 8');
    o = 0x21 + n * n * 4;
    if (o + 8 > m.length || u32(m, o) !== SEP) throw new PackError('model record: no separator after the column table');
    o += 8 + u32(m, o + 4);
    if (o + 8 > m.length || u32(m, o) !== SEP) throw new PackError('model record: no separator after the cell data');
    const cnt = u32(m, o + 4); o += 8;
    const tex = [];
    for (let k = 0; k < cnt; k++) {
      if (o + 4 > m.length) throw new PackError('model record: texture list runs past the end');
      const ln = u32(m, o);
      if (o + 8 + ln > m.length) throw new PackError('model record: texture list runs past the end');
      tex.push(cpDec(m.subarray(o + 4, o + 4 + ln))); o += 8 + ln;
    }
    if (o + 4 !== m.length || u32(m, o) !== SEP) throw new PackError('model record: texture list does not end the record');
    const custom = [];
    const keys = [...idx.values()].filter(e => e[2] === T_TEXINFO).sort((x, y) => x[1] - y[1] || x[0] - y[0] || x[2] - y[2]);
    for (const e of keys) {
      const p = b.subarray(e[3], e[3] + e[4]);
      if (p.length < 61) continue;
      const nl = u32(p, 57);
      if (61 + nl + 12 > p.length) continue;
      const nm = cpDec(p.subarray(61, 61 + nl));
      const it = u32(p, 61 + nl), ig = u32(p, 65 + nl), ii = u32(p, 69 + nl);
      let kind = null;
      if (p[0] >= 8 && 61 + nl + 16 <= p.length) { const k = u32(p, 73 + nl); kind = PART_KIND[k] || ('kind ' + k); }
      custom.push({ name: nm, kind, embedded: idx.has(keyOf(ig, ii, it)) });
    }
    return { lot, name: cpDec(name), architect: cpDec(arch), version: ver, textures: tex, custom };
  }

  // ================================================================================================ sort
  const base = p => p.slice(p.lastIndexOf('/') + 1);
  const ext = p => { const b = base(p), j = b.lastIndexOf('.'); return j >= 0 ? b.slice(j).toLowerCase() : ''; };
  function folderKind(p) {
    const ds = p.split('/').slice(0, -1).reverse();
    for (const d of ds) { const k = FOLDER_KIND[d.toLowerCase()]; if (k) return k; }
    return null;
  }
  function otherNote(path) {
    const e = ext(path), bn = base(path).toLowerCase();
    if (path.toLowerCase().includes('__macosx/') || bn.startsWith('._')) return 'macOS metadata';
    if (['thumbs.db', 'desktop.ini', '.ds_store'].includes(bn)) return 'system file';
    if (e === '.exe') return 'Windows program (not run)';
    if (INSTALLER_EXT.includes(e)) return 'installer file';
    if (['.jpg', '.jpeg', '.png', '.gif'].includes(e)) return 'picture';
    if (['.tga', '.bmp', '.met'].includes(e)) return 'not a valid ' + e.slice(1) + ' file';
    if (e === '.sc3') return 'city save';
    if (e === '.dat') return 'not an IXF file';
    if (e === '.pin') return 'no [DBSegments] section';
    return 'unknown';
  }
  function sortPack(entries) {
    const files = [], bldKinds = new Map(), mets = new Map();
    for (const e of entries) {
      const row = { path: e.path };
      if (e.data != null) { row.size = e.data.length; row.sha256 = sha(e.data); }
      if (e.archive) { row.kind = 'archive'; row.note = 'opened'; files.push(row); continue; }
      if (e.error) { row.kind = 'other'; row.note = e.error; files.push(row); continue; }
      const b = e.data, ex = ext(e.path);
      let idx = null, ixfErr = null;
      try { idx = ixfIndex(b); } catch (x) { if (!(x instanceof PackError)) throw x; idx = null; ixfErr = x.message; }
      if (idx && idx.has(keyOf(B_GROUP, I_MODEL, T_MODEL))) {
        row.kind = 'building';
        try {
          let info;
          try { info = readBld(b, idx); } catch (x) { if (x instanceof RangeError) throw new PackError('unreadable .bld record'); throw x; }
          row.bld = info;
          for (const c of info.custom) if (c.kind in KIND_DIR && !bldKinds.has(c.name.toLowerCase())) bldKinds.set(c.name.toLowerCase(), c.kind);
        } catch (x) { if (!(x instanceof PackError)) throw x; row.error = x.message; }
      } else if (ex === '.pin' && 'dbsegments' in parsePin(b)) {
        row.kind = 'plugin'; row.plugin = { type: 'pin', ini: parsePin(b) };
      } else if (idx && ex === '.dat') {
        row.kind = 'plugin';
        const types = {};
        for (const v of idx.values()) { const k = hex8(v[2]); types[k] = (types[k] || 0) + 1; }
        row.plugin = { type: 'dat', records: idx.size, types, keys: new Set([...idx.keys()]) };
      } else if (ex === '.met' && metNames(b) !== null) {
        row.kind = 'part'; row.met = metNames(b); mets.set(e.path, row.met);
      } else if ((ex === '.tga' && isTga(b)) || (ex === '.bmp' && isBmp(b))) {
        row.kind = 'part';
      } else if (README_EXT.includes(ex) || base(e.path).toLowerCase().includes('readme')) {
        row.kind = 'readme';
      } else {
        row.kind = 'other';
        row.note = ixfErr ? ixfErr : (idx ? 'IXF file' : otherNote(e.path));
      }
      files.push(row);
    }
    const metOf = new Map();
    for (const mp of [...mets.keys()].sort(cmpKey)) for (const n of mets.get(mp)) if (!metOf.has(n.toLowerCase())) metOf.set(n.toLowerCase(), mp);
    for (const row of files) {
      if (row.kind !== 'part') continue;
      const bn = base(row.path).toLowerCase();
      let k = folderKind(row.path), why = 'folder';
      if (k === null && 'met' in row) { k = 'prop'; why = 'met'; }
      if (k === null && metOf.has(bn)) { k = 'prop'; why = 'met'; }
      if (k === null && bldKinds.has(bn)) { k = bldKinds.get(bn); why = 'bld'; }
      if (k === null) why = null;
      row.part_kind = k; row.kind_from = why;
      if (metOf.has(bn) && !('met' in row)) row.prop_met = metOf.get(bn);
    }
    return files;
  }

  // ================================================================================================ game side
  async function walk(game, rel, out) {
    for (const n of (await game.listdir(rel)).slice().sort(cmpKey)) {
      const r = rel + '/' + n;
      if (await game.exists(r)) out.push(r); else await walk(game, r, out);
    }
  }
  async function gameIndex(game) {
    const out = {};
    for (const [key, root] of [['stock', 'Apps/Res/BA'], ['custom', 'Apps/BACustom']]) {
      const rels = []; await walk(game, root, rels);
      const d = new Map();
      for (const r of rels.sort(cmpKey)) { const k = base(r).toLowerCase(); if (!d.has(k)) d.set(k, []); d.get(k).push(r); }
      out[key] = d;
    }
    return out;
  }
  async function existing(game, d, name) {
    for (const n of (await game.listdir(d)).slice().sort(cmpKey)) if (n.toLowerCase() === name.toLowerCase() && await game.exists(d + '/' + n)) return d + '/' + n;
    return null;
  }
  async function targetOf(game, kind, name) {
    let d = 'Apps/BACustom/' + KIND_DIR[kind];
    for (const n of (await game.listdir('Apps/BACustom')).slice().sort(cmpKey)) if (n.toLowerCase() === KIND_DIR[kind].toLowerCase()) d = 'Apps/BACustom/' + n;
    return (await existing(game, d, name)) || d + '/' + name;
  }
  const readOrNull = async (game, rel) => (await game.exists(rel)) ? game.read(rel) : null;

  // ================================================================================================ report
  async function report(entries, game = null, kinds = {}) {
    const files = sortPack(entries);
    const gi = game ? await gameIndex(game) : null;
    const parts = files.filter(f => f.kind === 'part');
    for (const p of parts) if (Object.prototype.hasOwnProperty.call(kinds, p.path)) { p.part_kind = kinds[p.path]; p.kind_from = 'chosen'; }
    const byName = new Map();
    for (const p of parts) { const k = base(p.path).toLowerCase(); if (!byName.has(k)) byName.set(k, []); byName.get(k).push(p); }
    for (const p of parts) {
      const same = byName.get(base(p.path).toLowerCase());
      p.pack_twins = same.filter(q => q !== p).map(q => q.path);
      const shas = [...new Set(same.map(q => q.sha256))];
      p.pack_differ = !(shas.length === 1 && shas[0] === p.sha256);
      if (!gi) { p.state = 'no game'; continue; }
      if (p.part_kind === null) p.state = 'kind unknown';
      else {
        const tgt = await targetOf(game, p.part_kind, base(p.path));
        p.target = tgt;
        if (await game.exists(tgt)) p.state = sha(await game.read(tgt)) === p.sha256 ? 'installed' : 'conflict';
        else p.state = 'new';
      }
      p.custom_same_name = [];
      for (const r of gi.custom.get(base(p.path).toLowerCase()) || []) p.custom_same_name.push({ rel: r, same: sha(await game.read(r)) === p.sha256 });
    }
    const blds = [];
    for (const f of files) {
      if (f.kind !== 'building') continue;
      const row = { path: f.path };
      if ('error' in f) { row.error = f.error; blds.push(row); continue; }
      const info = f.bld;
      Object.assign(row, { name: info.name, architect: info.architect, lot: info.lot, version: info.version });
      const emb = new Map();
      for (const c of info.custom) if (!emb.has(c.name.toLowerCase())) emb.set(c.name.toLowerCase(), c);
      const rows = [], seen = new Set(), counts = {};
      for (const nm of info.textures) {
        const k = nm.toLowerCase();
        if (!nm || seen.has(k)) continue;
        seen.add(k);
        const r = { name: nm };
        const c = emb.get(k);
        if (c && c.kind) r.kind = c.kind;
        const pk = byName.get(k) || [];
        if (pk.length) { r.pack = pk.map(q => q.path); r.pack_state = pk[0].pack_differ ? 'pack files differ' : (pk[0].state === undefined ? null : pk[0].state); }
        if (/~\d/.test(nm)) r.note = '8.3 short name';
        if (nm.startsWith('color ')) r.status = 'color';
        else if (c && c.embedded) r.status = 'embedded';
        else if (gi && gi.stock.has(k)) { r.status = 'stock'; r.where = gi.stock.get(k)[0]; }
        else if (pk.length) r.status = 'pack';
        else if (gi && gi.custom.has(k)) { r.status = 'custom'; r.where = gi.custom.get(k)[0]; }
        else if (!gi) r.status = 'not checked';
        else r.status = 'missing';
        counts[r.status] = (counts[r.status] || 0) + 1;
        rows.push(r);
      }
      row.parts = rows; row.counts = counts;
      row.missing = rows.filter(r => r.status === 'missing').map(r => r.name);
      row.needs_install = rows.filter(r => r.status === 'pack' && r.pack_state !== 'installed').map(r => r.name);
      blds.push(row);
    }
    const plugins = [], dats = new Map(), used = new Set();
    for (const f of files) if (f.kind === 'plugin' && f.plugin.type === 'dat') dats.set(base(f.path).toLowerCase(), f);
    for (const f of files) {
      if (f.kind !== 'plugin' || f.plugin.type !== 'pin') continue;
      const ini = f.plugin.ini, segs = [];
      for (const [, v] of ini.dbsegments || []) {
        const fn = base(v.split('\\').join('/')), d = dats.get(fn.toLowerCase());
        segs.push({ file: fn, found: d ? d.path : null });
        if (d) used.add(d.path);
      }
      const keyset = new Set();
      for (const s of segs) if (s.found) for (const k of dats.get(base(s.found).toLowerCase()).plugin.keys) keyset.add(k);
      const keys = [];
      for (const [k, v] of ini.occupantkeys || []) {
        const xs = k.split(',');
        let ok = false;
        if (xs.length === 3 && xs.every(x => HEX.test(x))) {
          const [t, g, i] = xs.map(x => parseInt(pyStrip(x, ' \t'), 16) >>> 0);
          ok = keyset.has(keyOf(g, i, t));
        }
        keys.push({ key: k, label: v, in_dat: ok });
      }
      let enabled = null;
      for (const [k, v] of ini.admin || []) if (k.toLowerCase() === 'enabled') enabled = v;
      plugins.push({ pin: f.path, enabled, segments: segs, occupants: keys, sprites: (ini.spritesegments || []).map(([k]) => k) });
    }
    for (const f of files) if (f.kind === 'plugin' && f.plugin.type === 'dat' && !used.has(f.path)) plugins.push({ dat: f.path, pin: null });
    const outFiles = [];
    for (const f of files) {
      const r = {};
      for (const k of ['path', 'kind', 'size', 'sha256', 'note', 'error']) if (k in f) r[k] = f[k];
      if (f.kind === 'part') for (const k of ['part_kind', 'kind_from', 'prop_met', 'met', 'target', 'state', 'pack_twins', 'pack_differ', 'custom_same_name']) if (k in f) r[k] = f[k];
      if (f.kind === 'plugin') { r.plugin = f.plugin.type; if (f.plugin.type === 'dat') { r.records = f.plugin.records; r.types = f.plugin.types; } }
      outFiles.push(r);
    }
    const counts = {};
    for (const f of files) counts[f.kind] = (counts[f.kind] || 0) + 1;
    return { version: VERSION, counts, files: outFiles, buildings: blds, plugins, game: !!game };
  }
  const dumps = obj => BLDWEB.pyJson(obj, 1, true);

  // ================================================================================================ install / remove
  async function loadState(game) {
    const p = STATE_DIR + '/state.json';
    return (await game.exists(p)) ? JSON.parse(new TextDecoder('utf-8').decode(await game.read(p))) : { files: {} };
  }
  const saveState = (game, st) => game.writeNew(STATE_DIR + '/state.json', ascii(dumps(st)));
  async function install(game, entries, pack, overwrite = [], kinds = {}) {
    const rep = await report(entries, game, kinds);
    const data = new Map(entries.map(e => [e.path, e.data]));
    const ow = new Set(overwrite.map(n => n.toLowerCase()));
    const st = await loadState(game);
    const log = [], done = new Set();
    for (const f of rep.files) {
      if (f.kind !== 'part') continue;
      const nm = base(f.path).toLowerCase();
      if (f.part_kind === null) { log.push([f.path, 'skipped: kind unknown']); continue; }
      if (f.pack_differ) { log.push([f.path, 'skipped: the pack has different files with this name']); continue; }
      if (done.has(nm)) { log.push([f.path, 'skipped: same file as ' + f.pack_twins[0]]); continue; }
      done.add(nm);
      const tgt = f.target, b = data.get(f.path);
      const now = await readOrNull(game, tgt);
      if (bytesEq(now, b)) { log.push([f.path, 'already installed']); continue; }
      if (now !== null && !ow.has(nm)) { log.push([f.path, 'conflict: a different ' + base(tgt) + ' is in ' + tgt.slice(0, tgt.lastIndexOf('/'))]); continue; }
      let ent = st.files[tgt];
      if (ent === undefined) {
        if (now !== null) await game.writeNew(STATE_DIR + '/backup/' + tgt, now);
        ent = { existed: now !== null };
      }
      Object.assign(ent, { written: sha(b), pack, source: f.path });
      st.files[tgt] = ent;
      await game.writeNew(tgt, b);
      log.push([f.path, now !== null ? 'replaced ' + tgt : 'installed ' + tgt]);
    }
    await saveState(game, st);
    return { log, state: st, report: rep };
  }
  async function remove(game, pack = null) {
    const st = await loadState(game), log = [];
    for (const rel of Object.keys(st.files).sort(cmpKey)) {
      const ent = st.files[rel];
      if (pack !== null && ent.pack !== pack) continue;
      const now = await readOrNull(game, rel);
      if (now !== null && sha(now) !== ent.written) { log.push([rel, 'left: changed since the install']); delete st.files[rel]; continue; }
      if (ent.existed) {
        const bk = STATE_DIR + '/backup/' + rel;
        await game.writeNew(rel, await game.read(bk));
        await game.remove(bk);
        log.push([rel, 'put back']);
      } else { await game.remove(rel); log.push([rel, 'removed']); }
      delete st.files[rel];
    }
    await saveState(game, st);
    return { log, state: st };
  }
  async function installed(game) { return (await loadState(game)).files; }

  // ================================================================================================ page view
  // view(doc, el, rep, { onInstall(overwrite, kinds), onRemove(pack) }): the sort, the per-.bld report and the
  // install controls, drawn with the page's game-UI classes (sc3ui.css: .ui-group, .ui-label, .ui-table, .ui-note, button.primary).
  const KIND_LABEL = { building: 'Buildings (.bld)', part: 'Building Architect parts', plugin: 'Plugins (.dat + .pin, identified only)', readme: 'Readmes', archive: 'Archives opened', other: 'Other files' };
  const STATUS_LABEL = { color: 'colour', embedded: 'in the .bld', stock: 'game (Res\\BA)', pack: 'this pack', custom: 'game (BACustom)', missing: 'MISSING', 'not checked': 'not checked (no game folder)' };
  function view(doc, el, rep, opt = {}) {
    const h = (tag, attrs = {}, ...kids) => {
      const e = doc.createElement(tag);
      for (const [k, v] of Object.entries(attrs)) if (k === 'class') e.className = v; else if (k.startsWith('on')) e.addEventListener(k.slice(2), v); else e.setAttribute(k, v);
      for (const c of kids.flat()) if (c != null) e.append(c && c.nodeType ? c : doc.createTextNode(String(c)));
      return e;
    };
    el.textContent = '';
    const wrap = t => h('div', { style: 'overflow-x:auto' }, t);
    const order = ['building', 'part', 'plugin', 'readme', 'archive', 'other'];
    el.append(h('p', {}, order.filter(k => rep.counts[k]).map(k => KIND_LABEL[k].replace(/ \(.*/, '') + ': ' + rep.counts[k]).join(', ')));
    const kb = n => n == null ? '' : n < 1024 ? n + ' B' : (n / 1024).toFixed(n < 10240 ? 1 : 0) + ' KB';
    const firstOf = new Map();
    for (const f of rep.files) if (f.kind === 'part' && !firstOf.has(base(f.path).toLowerCase())) firstOf.set(base(f.path).toLowerCase(), f.path);
    const bldName = new Map(rep.buildings.map(b => [b.path, b.error ? 'cannot be read: ' + b.error : b.name + ', lot ' + b.lot + 'x' + b.lot]));
    for (const k of order) {
      const fs = rep.files.filter(f => f.kind === k);
      if (!fs.length) continue;
      const rows = fs.map(f => {
        let what = f.note || '';
        if (k === 'part') {
          const dup = firstOf.get(base(f.path).toLowerCase()) !== f.path;
          what = (f.part_kind || 'kind unknown') + (f.kind_from && f.kind_from !== 'folder' ? ' (from ' + f.kind_from + ')' : '') +
            (f.pack_differ ? ', the pack has other files with this name' : dup ? ', same file as ' + firstOf.get(base(f.path).toLowerCase()) : f.state && f.state !== 'kind unknown' ? ', ' + f.state : '');
        }
        if (k === 'building') what = bldName.get(f.path) || '';
        if (k === 'plugin') what = f.plugin === 'dat' ? f.records + ' records' : 'plugin settings';
        return h('tr', {}, h('td', {}, f.path), h('td', {}, what), h('td', { style: 'white-space:nowrap;text-align:right' }, kb(f.size)));
      });
      el.append(h('details', { class: 'ui-group sc3pack-kind', open: '' }, h('summary', {}, KIND_LABEL[k] + ' (' + fs.length + ')'), wrap(h('table', { class: 'ui-table' }, rows))));
    }
    for (const b of rep.buildings) {
      if (b.error) { el.append(h('div', { class: 'ui-note' }, b.path + ': ' + b.error)); continue; }
      const head = b.name + ' (' + b.path + ', ' + (b.version === 7 ? '1999 Building Architect' : 'SC3U') + ', lot ' + b.lot + 'x' + b.lot + ')';
      const sum = Object.keys(b.counts).sort().map(s => b.counts[s] + ' ' + (STATUS_LABEL[s] || s)).join(', ');
      const rows = b.parts.filter(r => r.status !== 'color' && r.status !== 'stock').map(r => h('tr', { class: r.status === 'missing' ? 'sc3pack-missing' : '' },
        h('td', {}, r.name), h('td', {}, STATUS_LABEL[r.status] || r.status), h('td', {}, r.pack_state || r.where || ''), h('td', {}, r.note || '')));
      el.append(h('details', { class: 'ui-group' }, h('summary', {}, head + ': ' + sum + (b.missing.length ? ' (missing: ' + b.missing.join(', ') + ')' : '')), rows.length ? wrap(h('table', { class: 'ui-table' }, rows)) : h('p', { class: 'ui-label' }, 'every part is a colour, stock or in the .bld')));
    }
    for (const p of rep.plugins) {
      if (!p.pin) { el.append(h('p', { class: 'ui-label' }, p.dat + ': plugin .dat without a .pin')); continue; }
      el.append(h('details', { class: 'ui-group' }, h('summary', {}, 'Plugin ' + p.pin + ': ' + p.occupants.length + ' buildings (ploppables: not installed by this page yet)'),
        h('table', { class: 'ui-table' }, p.occupants.map(o => h('tr', {}, h('td', {}, o.label), h('td', {}, o.key), h('td', {}, o.in_dat ? 'in the .dat' : 'NOT in the .dat')))),
        h('p', { class: 'ui-label' }, 'Data files: ' + p.segments.map(s => s.file + (s.found ? '' : ' (not in the pack)')).join(', '))));
    }
    const parts = rep.files.filter(f => f.kind === 'part');
    if (rep.game && parts.length && opt.onInstall) {
      const conflicts = parts.filter(f => f.state === 'conflict' && !f.pack_differ);
      const unknown = parts.filter(f => f.part_kind === null);
      const box = h('div', { class: 'ui-group' });
      const ow = new Map(), kinds = new Map();
      if (conflicts.length) {
        box.append(h('p', { class: 'ui-note' }, 'Apps\\BACustom already has a different file with these names. Tick a name to replace the game\'s copy (it is backed up and Remove puts it back):'));
        for (const f of conflicts) { const cb = h('input', { type: 'checkbox' }); ow.set(base(f.path), cb); box.append(h('label', {}, cb, ' ' + f.target)); box.append(h('br')); }
      }
      if (unknown.length) {
        box.append(h('p', {}, 'Parts of unknown kind (no Paints / Details / Props folder, no .met, no .bld record): pick one to install them.'));
        for (const f of unknown) {
          const sel = h('select', {}, h('option', { value: '' }, 'do not install'), ...Object.keys(KIND_DIR).map(k => h('option', { value: k }, KIND_DIR[k])));
          kinds.set(f.path, sel); box.append(h('label', {}, f.path + ' ', sel)); box.append(h('br'));
        }
      }
      const todo = new Set(parts.filter(f => f.state === 'new' && !f.pack_differ).map(f => base(f.path).toLowerCase())).size;
      box.append(h('button', { class: 'primary', onclick: () => opt.onInstall([...ow].filter(([, cb]) => cb.checked).map(([n]) => n), Object.fromEntries([...kinds].filter(([, s]) => s.value).map(([p, s]) => [p, s.value]))) },
        'Install ' + todo + ' new part' + (todo === 1 ? '' : 's') + ' into Apps\\BACustom'));
      if (opt.onRemove) box.append(' ', h('button', { onclick: () => opt.onRemove(opt.pack || null) }, 'Remove the parts this page installed'));
      el.append(box);
    }
    return el;
  }

  return {
    version: VERSION, PackError, STATE_DIR, KIND_DIR,
    openZip, openFolder, openFiles, openHandle, sortPack, gameIndex, report, dumps, install, remove, installed, view,
    // pieces for the tests
    readBld, ixfIndex, parsePin, metNames, pySplitlines, pyStrip, cp437,
  };
}

globalThis.SC3PACK = SC3PACK_LIB(globalThis.BLDWEB || (typeof require === 'function' ? require('./bldweb.js') : null));
if (typeof module === 'object' && module.exports) module.exports = globalThis.SC3PACK;
