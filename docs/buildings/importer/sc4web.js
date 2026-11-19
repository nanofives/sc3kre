// sc4web.js - task sc4web (2026-11-19): SimCity 4 buildings into the importer page (classifier.html), byte for byte.
//
// Players have no Python, so this file does in the browser what re/tools/sc4conv/sc4conv.py does: it reads the
// player's own SC4 download (a folder, or the .zip / .jar as downloaded: LEX installers are jars), finds the
// buildings and writes, in memory, the same OBJ + MTL + PNG + models.json the Python converter writes. bldweb.js
// (bldimport in the page) then renders and installs them as any models folder. A transcription of:
//
//   sc4conv/dbpf.py      DBPF 1.0 / 1.1 index + directory, QFS / RefPack
//   sc4conv/exemplar.py  binary exemplar / cohort, LText
//   sc4conv/s3d.py       S3D '3DMD' walker (by content: the chunk lengths are wrong in the files)
//   sc4conv/fsh.py       FSH 'SHPI' first bitmap: DXT1 / DXT3 / DXT5, 8888, 888, 565, 1555, 4444
//   sc4conv/catalog.py   the plugin index (a later file wins), buildings, lots, families
//   sc4conv/views.py     the four zoom-5 view models in one model frame, the camera fit, view per SC3 slot, the
//                        hidden back walls + floor
//   sc4conv/sc4conv.py   class / lot / name rules, OBJ / MTL / models.json text, one colour per design, the
//                        rerun merge that keeps the player's edits (x_sc4.auto)
//
// Byte identity (webtest/sc4_golden.mjs): the OBJ, MTL and models.json text equal sc4conv.py's to the byte, the
// textures equal its PNGs pixel for pixel (alpha too; the PNG bytes differ: PIL deflates, this file stores), and
// what bldweb.js installs from them equals bldimport.py's install from the Python output. Numbers are printed as
// Python prints them (%.Nf correctly rounded half to even on the exact binary value, round(), repr()), the camera
// fit uses views.py's fixed-order normal equations. atan2 / asin come from the browser's maths library: they only
// pick the view per slot (a nearest angle) and the rounded camera angles in x_sc4.
//
// One classic script, no imports: the page loads it after bldweb.js; node: require('./sc4web.js').
'use strict';

function SC4WEB_LIB(B) {
  'use strict';
  class Sc4Error extends Error {}            // what the Python tool raises as ValueError (a skipped file / building)

  // ================================================================================================ Python numbers
  const _dv = new DataView(new ArrayBuffer(8));
  function f64parts(x) {                    // finite x -> [sign, BigInt mantissa, exponent] with |x| = m * 2^e
    _dv.setFloat64(0, x);
    const hi = _dv.getUint32(0), lo = _dv.getUint32(4);
    const sign = hi >>> 31, ex = (hi >>> 20) & 0x7FF;
    let m = (BigInt(hi & 0xFFFFF) << 32n) | BigInt(lo);
    let e;
    if (ex === 0) e = -1074; else { m |= 1n << 52n; e = ex - 1075; }
    return [sign, m, e];
  }
  // '%.<d>f' % x: the exact binary value rounded half to even (CPython's dtoa), sign kept (also for -0.0)
  function pyFixed(x, d) {
    if (x !== x) return 'nan';
    if (x === Infinity) return 'inf';
    if (x === -Infinity) return '-inf';
    const [sign, m, e] = f64parts(x);
    const p = 10n ** BigInt(d);
    let q;
    if (e >= 0) q = (m << BigInt(e)) * p;
    else {
      const num = m * p, den = 1n << BigInt(-e);
      q = num / den;
      const r2 = (num % den) * 2n;
      if (r2 > den || (r2 === den && (q & 1n))) q += 1n;
    }
    let s = q.toString();
    if (d > 0) { s = s.padStart(d + 1, '0'); s = s.slice(0, s.length - d) + '.' + s.slice(s.length - d); }
    return (sign ? '-' : '') + s;
  }
  const pyRound = (x, n) => parseFloat(pyFixed(x, n));      // round(x, n): correctly rounded, then the nearest double
  function pyRepr(x) {                       // repr(float)
    if (x !== x) return 'NaN';               // json.dumps spelling
    if (x === Infinity) return 'Infinity';
    if (x === -Infinity) return '-Infinity';
    if (x === 0) return Object.is(x, -0) ? '-0.0' : '0.0';
    const neg = x < 0, s = Math.abs(x).toExponential();      // shortest round-trip digits
    const [mant, ex] = s.split('e');
    const digits = mant.replace('.', ''), decpt = parseInt(ex, 10) + 1;
    let out;
    if (decpt > -4 && decpt <= 16) {
      if (decpt <= 0) out = '0.' + '0'.repeat(-decpt) + digits;
      else if (decpt >= digits.length) out = digits + '0'.repeat(decpt - digits.length) + '.0';
      else out = digits.slice(0, decpt) + '.' + digits.slice(decpt);
    } else {
      const e = decpt - 1;
      out = digits[0] + (digits.length > 1 ? '.' + digits.slice(1) : '') + 'e' + (e < 0 ? '-' : '+') + String(Math.abs(e)).padStart(2, '0');
    }
    return (neg ? '-' : '') + out;
  }
  const hexU = (v, w) => (v >>> 0).toString(16).toUpperCase().padStart(w, '0');   // '%0<w>X'
  // a Python float in a JSON value (JS numbers cannot tell 1.0 from 1)
  class PyFloat { constructor(v) { this.v = v; } valueOf() { return this.v; } toJSON() { return this.v; } }
  const num = v => v instanceof PyFloat ? v.v : v;
  // json.dumps(v, indent=k) (ensure_ascii, separators ',' / ': '), PyFloat and non-integer numbers as repr()
  function pyDump(v, indent, level = 0) {
    if (v === null || v === undefined) return 'null';
    if (v === true) return 'true';
    if (v === false) return 'false';
    if (v instanceof PyFloat) return pyRepr(v.v);
    if (typeof v === 'number') return Number.isInteger(v) && !Object.is(v, -0) ? String(v) : pyRepr(v);
    if (typeof v === 'bigint') return v.toString();
    if (typeof v === 'string') return B.pyJsonStr(v);
    const pad = '\n' + ' '.repeat(indent * (level + 1)), end = '\n' + ' '.repeat(indent * level);
    if (Array.isArray(v)) {
      if (!v.length) return '[]';
      return '[' + v.map(x => pad.slice(0) + pyDump(x, indent, level + 1)).join(',') + end + ']';
    }
    const keys = Object.keys(v);
    if (!keys.length) return '{}';
    return '{' + keys.map(k => pad + B.pyJsonStr(k) + ': ' + pyDump(v[k], indent, level + 1)).join(',') + end + '}';
  }
  // json.loads that keeps Python's int / float distinction (floats as PyFloat); duplicate keys: the last wins
  function pyLoad(text) {
    let i = 0;
    const ws = () => { while (i < text.length && ' \t\n\r'.includes(text[i])) i++; };
    const fail = () => { throw new Sc4Error('models.json: not valid JSON at character ' + i); };
    function val() {
      ws();
      const c = text[i];
      if (c === '{') {
        i++; const o = {}; ws();
        if (text[i] === '}') { i++; return o; }
        for (;;) {
          ws(); if (text[i] !== '"') fail();
          const k = str(); ws(); if (text[i] !== ':') fail(); i++;
          o[k] = val(); ws();
          if (text[i] === ',') { i++; continue; }
          if (text[i] === '}') { i++; return o; }
          fail();
        }
      }
      if (c === '[') {
        i++; const a = []; ws();
        if (text[i] === ']') { i++; return a; }
        for (;;) {
          a.push(val()); ws();
          if (text[i] === ',') { i++; continue; }
          if (text[i] === ']') { i++; return a; }
          fail();
        }
      }
      if (c === '"') return str();
      if (text.startsWith('true', i)) { i += 4; return true; }
      if (text.startsWith('false', i)) { i += 5; return false; }
      if (text.startsWith('null', i)) { i += 4; return null; }
      if (text.startsWith('NaN', i)) { i += 3; return new PyFloat(NaN); }
      if (text.startsWith('Infinity', i)) { i += 8; return new PyFloat(Infinity); }
      if (text.startsWith('-Infinity', i)) { i += 9; return new PyFloat(-Infinity); }
      const m = /^-?(0|[1-9]\d*)(\.\d+)?([eE][+-]?\d+)?/.exec(text.slice(i, i + 400));
      if (!m) fail();
      i += m[0].length;
      if (m[2] || m[3]) return new PyFloat(parseFloat(m[0]));
      const n = Number(m[0]);
      return Number.isSafeInteger(n) ? n : BigInt(m[0]);
    }
    function str() {
      i++; let s = '';
      for (;;) {
        const c = text[i++];
        if (c === undefined) fail();
        if (c === '"') return s;
        if (c === '\\') {
          const e = text[i++];
          if (e === 'u') { s += String.fromCharCode(parseInt(text.slice(i, i + 4), 16)); i += 4; }
          else s += { b: '\b', f: '\f', n: '\n', r: '\r', t: '\t', '"': '"', '\\': '\\', '/': '/' }[e] ?? fail();
        } else s += c;
      }
    }
    const v = val(); ws();
    if (i !== text.length) fail();
    return v;
  }
  // Python == between JSON values (1 == 1.0 == True)
  function pyEq(a, b) {
    const sc = x => x instanceof PyFloat ? x.v : typeof x === 'boolean' ? +x : typeof x === 'bigint' ? Number(x) : x;
    a = sc(a); b = sc(b);
    if (typeof a === 'number' && typeof b === 'number') return a === b;
    if (Array.isArray(a) || Array.isArray(b)) return Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((x, k) => pyEq(x, b[k]));
    if (a && b && typeof a === 'object' && typeof b === 'object') {
      const ka = Object.keys(a), kb = Object.keys(b);
      return ka.length === kb.length && ka.every(k => Object.prototype.hasOwnProperty.call(b, k) && pyEq(a[k], b[k]));
    }
    return a === b;
  }
  // str.isspace() / strip() / splitlines() of Python
  const PY_SPACE = new Set([0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x1C, 0x1D, 0x1E, 0x1F, 0x20, 0x85, 0xA0, 0x1680, 0x2000, 0x2001,
    0x2002, 0x2003, 0x2004, 0x2005, 0x2006, 0x2007, 0x2008, 0x2009, 0x200A, 0x2028, 0x2029, 0x202F, 0x205F, 0x3000]);
  const pyStrip = s => { let a = 0, b = s.length; while (a < b && PY_SPACE.has(s.charCodeAt(a))) a++; while (b > a && PY_SPACE.has(s.charCodeAt(b - 1))) b--; return s.slice(a, b); };
  const pySplitlines = s => {
    const out = []; let cur = '';
    for (let k = 0; k < s.length; k++) {
      const c = s.charCodeAt(k);
      if (c === 0x0D && s.charCodeAt(k + 1) === 0x0A) { out.push(cur); cur = ''; k++; continue; }
      if ([0x0A, 0x0B, 0x0C, 0x0D, 0x1C, 0x1D, 0x1E, 0x85, 0x2028, 0x2029].includes(c)) { out.push(cur); cur = ''; continue; }
      cur += s[k];
    }
    if (cur) out.push(cur);
    return out;
  };
  const latin1 = b => { let s = ''; for (let k = 0; k < b.length; k += 8192) s += String.fromCharCode.apply(null, b.subarray(k, k + 8192)); return s; };
  // Python float % float (the sign of the divisor)
  function pyMod(a, b) { let m = a % b; if (m !== 0) { if ((b < 0) !== (m < 0)) m += b; } else m = b < 0 ? -0 : 0; return m; }
  const degrees = x => x * (180.0 / Math.PI);

  // ================================================================================================ byte reader
  // struct.unpack_from: reads past the end raise (struct.error -> a skipped exemplar / file, as in Python)
  class Rd {
    constructor(b) { this.b = b; this.v = new DataView(b.buffer, b.byteOffset, b.byteLength); }
    need(p, n) { if (p < 0 || p + n > this.b.length) throw new Sc4Error('read past the end (' + (p + n) + ' > ' + this.b.length + ')'); }
    u8(p) { this.need(p, 1); return this.b[p]; }
    u16(p) { this.need(p, 2); return this.v.getUint16(p, true); }
    u32(p) { this.need(p, 4); return this.v.getUint32(p, true); }
    i32(p) { this.need(p, 4); return this.v.getInt32(p, true); }
    i64(p) { this.need(p, 8); return Number(this.v.getBigInt64(p, true)); }
    f32(p) { this.need(p, 4); return this.v.getFloat32(p, true); }
  }

  // ================================================================================================ DBPF + QFS
  const T_DIR = 0xE86B1EEF, T_EXEMPLAR = 0x6534284A, T_COHORT = 0x05342861, T_S3D = 0x5AD0E817, T_FSH = 0x7AB50E44, T_LTEXT = 0x2026960B;
  const DBPF_EXT = ['.dat', '.sc4desc', '.sc4lot', '.sc4model'];
  const isDbpfName = n => DBPF_EXT.some(x => n.toLowerCase().endsWith(x));

  function qfsDecompress(data, off = 0) {   // dbpf.qfs_decompress
    if (data[off + 4] === 0x10 && data[off + 5] === 0xFB) off += 4;
    if (!(data[off] === 0x10 && data[off + 1] === 0xFB) && data[off + 1] !== 0xFB) throw new Sc4Error('no QFS magic');
    const flags = data[off];
    const usize = (data[off + 2] << 16) | (data[off + 3] << 8) | data[off + 4];
    let p = off + 5;
    if (flags & 0x01) p += 3;
    const out = new Uint8Array(usize);
    let o = 0;
    const n = data.length;
    const put = (src, a, cnt) => { for (let k = 0; k < cnt; k++) { if (o >= usize) throw new Sc4Error('QFS output overrun'); out[o++] = src[a + k]; } };
    while (p < n) {
      const b0 = data[p];
      let plain, clen, coff;
      if (b0 < 0x80) { const b1 = data[p + 1]; p += 2; plain = b0 & 3; clen = ((b0 & 0x1C) >> 2) + 3; coff = ((b0 & 0x60) << 3) + b1 + 1; }
      else if (b0 < 0xC0) { const b1 = data[p + 1], b2 = data[p + 2]; p += 3; plain = (b1 >> 6) & 3; clen = (b0 & 0x3F) + 4; coff = ((b1 & 0x3F) << 8) + b2 + 1; }
      else if (b0 < 0xE0) { const b1 = data[p + 1], b2 = data[p + 2], b3 = data[p + 3]; p += 4; plain = b0 & 3; clen = ((b0 & 0x0C) << 6) + b3 + 5; coff = ((b0 & 0x10) << 12) + (b1 << 8) + b2 + 1; }
      else if (b0 < 0xFC) { p += 1; plain = ((b0 & 0x1F) << 2) + 4; clen = 0; coff = 0; }
      else { p += 1; plain = b0 & 3; put(data, p, Math.min(plain, n - p)); break; }
      put(data, p, Math.min(plain, n - p));
      p += plain;
      if (clen) { const s = o - coff; if (s < 0) throw new Sc4Error('QFS back reference before the start'); for (let k = 0; k < clen; k++) { if (o >= usize) throw new Sc4Error('QFS output overrun'); out[o] = out[s + k]; o++; } }
    }
    if (o !== usize) throw new Sc4Error('QFS size mismatch ' + o + ' != ' + usize);
    return out;
  }
  const tgiKey = (t, g, i) => t + ':' + g + ':' + i;
  function readDbpf(path, d) {              // dbpf.DBPF
    if (!(d[0] === 0x44 && d[1] === 0x42 && d[2] === 0x50 && d[3] === 0x46)) throw new Sc4Error(path + ': not a DBPF file');
    const r = new Rd(d);
    const major = r.u32(4), minor = r.u32(8);
    const count = r.u32(0x24), ioff = r.u32(0x28), isize = r.u32(0x2C);
    const indexMinor = minor >= 1 ? r.u32(0x3C) : 0;
    const esz = indexMinor === 2 ? 24 : 20;
    if (count && isize !== count * esz) throw new Sc4Error(path + ': index size ' + isize + ' != ' + count + ' x ' + esz);
    const entries = [];
    for (let k = 0; k < count; k++) {
      const p = ioff + k * esz;
      entries.push({ type: r.u32(p), group: r.u32(p + 4), instance: r.u32(p + 8), offset: r.u32(p + esz - 8), size: r.u32(p + esz - 4), usize: 0, packed: false });
      entries[k].usize = entries[k].size;
    }
    const byTgi = new Map(); for (const e of entries) byTgi.set(tgiKey(e.type, e.group, e.instance), e);
    const dsz = indexMinor === 2 ? 20 : 16;
    for (const e of entries) {
      if (e.type !== T_DIR) continue;
      const raw = d.subarray(e.offset, e.offset + e.size), rr = new Rd(raw);
      for (let p = 0; p + dsz <= raw.length; p += dsz) {
        const x = byTgi.get(tgiKey(rr.u32(p), rr.u32(p + 4), rr.u32(p + 8)));
        if (x) { x.packed = true; x.usize = rr.u32(p + dsz - 4); }
      }
    }
    return { path, data: d, major, minor, indexMinor, entries,
      read(e) { const raw = d.subarray(e.offset, e.offset + e.size); return e.packed ? qfsDecompress(raw) : raw; } };
  }

  // ================================================================================================ exemplar + LText
  const VT = { 0x0100: ['B', 1], 0x0200: ['H', 2], 0x0300: ['I', 4], 0x0700: ['i', 4], 0x0800: ['q', 8], 0x0900: ['f', 4], 0x0B00: ['?', 1], 0x0C00: ['c', 1] };
  function readValue(r, fmt, p) {
    switch (fmt) {
      case 'B': return r.u8(p); case 'H': return r.u16(p); case 'I': return r.u32(p); case 'i': return r.i32(p);
      case 'q': return r.i64(p); case 'f': return new PyFloat(r.f32(p)); case '?': return r.u8(p) !== 0;
    }
    throw new Sc4Error('value type');
  }
  function parseExemplar(b) {               // exemplar.parse_exemplar; float values are PyFloat (they print as floats)
    const sig = latin1(b.subarray(0, 4));
    if (sig !== 'EQZB' && sig !== 'CQZB') throw new Sc4Error('not a binary exemplar');
    const r = new Rd(b);
    const parent = [r.u32(8), r.u32(12), r.u32(16)];
    const n = r.u32(20);
    let p = 24;
    const props = new Map(), order = [];
    for (let k = 0; k < n; k++) {
      const pid = r.u32(p), vt = r.u16(p + 4), kt = r.u16(p + 6);
      p += 8;
      if (!VT[vt]) throw new Sc4Error('value type 0x' + vt.toString(16));
      const [fmt, sz] = VT[vt];
      let val;
      if (kt === 0x80) {
        p += 1;
        const cnt = r.u32(p);
        p += 4;
        if (vt === 0x0C00) val = latin1(b.subarray(p, p + cnt));
        else { r.need(p, cnt * sz); val = []; for (let q = 0; q < cnt; q++) val.push(readValue(r, fmt, p + q * sz)); }
        p += cnt * sz;
      } else {
        p += 1;
        if (vt === 0x0C00) throw new Sc4Error('single string');
        val = readValue(r, fmt, p);
        p += sz;
      }
      props.set(pid, [vt, val]);
      order.push(pid);
    }
    return { kind: sig, parent, props, order };
  }
  function ltext(b) {
    const r = new Rd(b);
    const n = r.u16(0), mark = r.u16(2);
    if (mark === 0x1000) {
      const seg = b.subarray(4, 4 + 2 * n);
      return new TextDecoder('utf-16le', { fatal: true }).decode(seg.subarray(0, seg.length & ~1).length === seg.length ? seg : seg.subarray(0, seg.length & ~1));
    }
    return latin1(b.subarray(4, 4 + n));
  }

  // ================================================================================================ S3D
  function readS3D(b) {                     // s3d.S3D
    if (latin1(b.subarray(0, 4)) !== '3DMD') throw new Sc4Error('not 3DMD');
    const r = new Rd(b);
    let p = 8;
    const tag = expect => {
      const t = latin1(b.subarray(p, p + 4));
      if (t !== expect) throw new Sc4Error('expected ' + expect + ' at ' + p + ', got ' + JSON.stringify(t));
      r.u32(p + 4); p += 8;
    };
    const u16 = () => { const v = r.u16(p); p += 2; return v; };
    const u32 = () => { const v = r.u32(p); p += 4; return v; };
    const u8 = () => { const v = r.u8(p); p += 1; return v; };
    const name = nl => { r.need(p, 0); let s = latin1(b.subarray(p, p + nl)); s = s.replace(/\0+$/, ''); p += nl; return s; };
    tag('HEAD'); u16(); u16();
    tag('VERT');
    const verts = [];
    for (let g = 0, ng = u32(); g < ng; g++) {
      const flags = u16(), cnt = u16(), fmt = u32();
      if (fmt !== 0x80004001) throw new Sc4Error('vertex format 0x' + hexU(fmt, 8) + ' not read');
      r.need(p, 20 * cnt);
      const vs = [];
      for (let k = 0; k < cnt; k++) { const q = p + 20 * k; vs.push([r.f32(q), r.f32(q + 4), r.f32(q + 8), r.f32(q + 12), r.f32(q + 16)]); }
      p += 20 * cnt;
      verts.push({ flags, v: vs });
    }
    tag('INDX');
    const indices = [];
    for (let g = 0, ng = u32(); g < ng; g++) {
      u16(); const stride = u16(), cnt = u16();
      if (stride !== 2) throw new Sc4Error('index stride ' + stride);
      r.need(p, 2 * cnt);
      const ix = []; for (let k = 0; k < cnt; k++) ix.push(r.u16(p + 2 * k));
      p += 2 * cnt;
      indices.push(ix);
    }
    tag('PRIM');
    const prims = [];
    for (let g = 0, ng = u32(); g < ng; g++) { const n = u16(); const ps = []; for (let k = 0; k < n; k++) ps.push([u32(), u32(), u32()]); prims.push(ps); }
    tag('MATS');
    const mats = [];
    for (let g = 0, ng = u32(); g < ng; g++) {
      u32(); u8(); u8(); u8(); u8(); u16(); u32(); u8();
      const ntex = u8(), tex = [];
      for (let k = 0; k < ntex; k++) { const id = u32(); u8(); u8(); u8(); u8(); u16(); u16(); const nl = u8(); tex.push({ id, name: name(nl) }); }
      mats.push({ tex });
    }
    tag('ANIM');
    const nfr = u16(); u16(); u16(); u32(); r.f32(p); p += 4;
    const meshes = [];
    for (let m = 0, nm = u16(); m < nm; m++) {
      const nl = u8(); u8();
      const nmName = name(nl);
      const frames = []; for (let f = 0; f < nfr; f++) frames.push([u16(), u16(), u16(), u16()]);
      meshes.push({ name: nmName, frames });
    }
    tag('PROP'); if (u32()) throw new Sc4Error('PROP entries not read');
    tag('REGP'); if (u32()) throw new Sc4Error('REGP entries not read');
    if (p !== b.length) throw new Sc4Error('S3D: ' + (b.length - p) + ' bytes left after REGP');
    // meshes(): (positions, uvs, triangles, material, name) per ANIM mesh, frame 0
    return meshes.map(m => {
      const [vg, ig, pg, mg] = m.frames[0];
      if (!verts[vg] || !indices[ig] || !prims[pg] || !mats[mg]) throw new Sc4Error('S3D: mesh group out of range');
      const vs = verts[vg].v, idx = indices[ig], tris = [];
      for (const [ptype, first, cnt] of prims[pg]) {
        if (ptype !== 0) throw new Sc4Error('prim type ' + ptype);
        const seg = idx.slice(first, first + cnt);
        for (let k = 0; k < seg.length - 2; k += 3) tris.push([seg[k], seg[k + 1], seg[k + 2]]);
      }
      return { P: vs.map(v => [v[0], v[1], v[2]]), UV: vs.map(v => [v[3], v[4]]), tris, mat: mats[mg], name: m.name };
    });
  }

  // ================================================================================================ FSH
  const x565 = c => { const r = (c >> 11) & 31, g = (c >> 5) & 63, b = c & 31; return [(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)]; };
  function colourBlock(raw, q, alpha1bit, out, px) {   // fsh._dxt_colour_block for one block at raw[q..q+8] -> out RGBA x16 at px
    const c0 = raw[q] | (raw[q + 1] << 8), c1 = raw[q + 2] | (raw[q + 3] << 8);
    const bits = (raw[q + 4] | (raw[q + 5] << 8) | (raw[q + 6] << 16) | (raw[q + 7] << 24)) >>> 0;
    const a = x565(c0), b = x565(c1);
    const four = c0 > c1 || !alpha1bit;
    const pal = [[a[0], a[1], a[2], 255], [b[0], b[1], b[2], 255], [0, 0, 0, 255], [0, 0, 0, 255]];
    for (let k = 0; k < 3; k++) {
      pal[2][k] = four ? Math.floor((2 * a[k] + b[k]) / 3) : Math.floor((a[k] + b[k]) / 2);
      pal[3][k] = four ? Math.floor((a[k] + 2 * b[k]) / 3) : 0;
    }
    if (alpha1bit) pal[3][3] = four ? 255 : 0;
    for (let i = 0; i < 16; i++) { const c = pal[(bits >>> (2 * i)) & 3]; out.set(c, px + 4 * i); }
  }
  function fshDecode(code, b, p, w, h) {   // fsh.decode -> [RGBA Uint8Array, bytes used]
    const r = new Rd(b);
    if (code === 0x60 || code === 0x61 || code === 0x62) {
      const bw = Math.max(1, (w + 3) >> 2), bh = Math.max(1, (h + 3) >> 2), n = bw * bh, bs = code === 0x60 ? 8 : 16;
      r.need(p, n * bs);
      const blk = new Uint8Array(n * 64);
      for (let k = 0; k < n; k++) {
        const q = p + k * bs;
        if (code === 0x60) colourBlock(b, q, true, blk, 64 * k);
        else {
          colourBlock(b, q + 8, false, blk, 64 * k);
          if (code === 0x61) {
            for (let j = 0; j < 8; j++) { blk[64 * k + 4 * (2 * j) + 3] = (b[q + j] & 15) * 17; blk[64 * k + 4 * (2 * j + 1) + 3] = (b[q + j] >> 4) * 17; }
          } else {
            const a0 = b[q], a1 = b[q + 1], tab = [a0, a1, 0, 0, 0, 0, 0, 0];
            if (a0 > a1) for (let t = 1; t < 7; t++) tab[t + 1] = Math.floor(((7 - t) * a0 + t * a1) / 7);
            else { for (let t = 1; t < 5; t++) tab[t + 1] = Math.floor(((5 - t) * a0 + t * a1) / 5); tab[6] = 0; tab[7] = 255; }
            let lo = (b[q + 2] | (b[q + 3] << 8) | (b[q + 4] << 16)) >>> 0, hi = (b[q + 5] | (b[q + 6] << 8) | (b[q + 7] << 16)) >>> 0;
            for (let i = 0; i < 16; i++) {
              const v = i < 8 ? (lo >>> (3 * i)) & 7 : (hi >>> (3 * (i - 8))) & 7;
              blk[64 * k + 4 * i + 3] = tab[v];
            }
          }
        }
      }
      const out = new Uint8Array(w * h * 4);
      for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
        const k = (y >> 2) * bw + (x >> 2), i = (y & 3) * 4 + (x & 3), s = 64 * k + 4 * i, t = 4 * (y * w + x);
        out[t] = blk[s]; out[t + 1] = blk[s + 1]; out[t + 2] = blk[s + 2]; out[t + 3] = blk[s + 3];
      }
      return [out, n * bs];
    }
    const out = new Uint8Array(w * h * 4);
    if (code === 0x7D) { r.need(p, w * h * 4); for (let k = 0; k < w * h; k++) { out[4 * k] = b[p + 4 * k + 2]; out[4 * k + 1] = b[p + 4 * k + 1]; out[4 * k + 2] = b[p + 4 * k]; out[4 * k + 3] = b[p + 4 * k + 3]; } return [out, w * h * 4]; }
    if (code === 0x7F) { r.need(p, w * h * 3); for (let k = 0; k < w * h; k++) { out[4 * k] = b[p + 3 * k + 2]; out[4 * k + 1] = b[p + 3 * k + 1]; out[4 * k + 2] = b[p + 3 * k]; out[4 * k + 3] = 255; } return [out, w * h * 3]; }
    if (code === 0x78 || code === 0x7E || code === 0x6D) {
      r.need(p, w * h * 2);
      for (let k = 0; k < w * h; k++) {
        const c = b[p + 2 * k] | (b[p + 2 * k + 1] << 8);
        let px;
        if (code === 0x78) px = [...x565(c), 255];
        else if (code === 0x7E) { px = [10, 5, 0].map(s => { const v = (c >> s) & 31; return (v << 3) | (v >> 2); }); px.push(c & 0x8000 ? 255 : 0); }
        else px = [((c >> 8) & 15) * 17, ((c >> 4) & 15) * 17, (c & 15) * 17, ((c >> 12) & 15) * 17];
        out.set(px, 4 * k);
      }
      return [out, w * h * 2];
    }
    throw new Sc4Error('FSH code 0x' + hexU(code, 2) + ' not read');
  }
  function readFshFirst(b) {                // fsh.read_fsh(b)[0]
    if (latin1(b.subarray(0, 4)) !== 'SHPI') throw new Sc4Error('not SHPI');
    const r = new Rd(b);
    const count = r.u32(8);
    if (!count) throw new Sc4Error('FSH without bitmaps');
    let first = null;
    for (let k = 0; k < count; k++) {          // read_fsh decodes every bitmap: one it cannot read skips the building
      const off = r.u32(20 + 8 * k);
      const code = r.u32(off) & 0xFF, w = r.u16(off + 4), h = r.u16(off + 6);
      const [img] = fshDecode(code, b, off + 16, w, h);
      if (!first) first = { code, w, h, image: img };
    }
    return first;
  }

  // ================================================================================================ catalogue
  // Sources: [{ path, bytes: async () => Uint8Array }] in sc4conv's walk order (catalog.dbpf_files)
  async function buildIndex(sources, log) {
    const files = [], tgi = new Map();
    for (const s of sources) {
      let f;
      try { f = readDbpf(s.path, await s.bytes()); }
      catch (e) { if (log) log('  skip ' + s.path + ': ' + (e.message || e)); continue; }
      files.push(f);
      for (const e of f.entries) if (e.type !== T_DIR) tgi.set(tgiKey(e.type, e.group, e.instance), [f, e]);
    }
    return {
      files, tgi,
      has: (t, g, i) => tgi.has(tgiKey(t, g, i)),
      read(t, g, i) { const x = tgi.get(tgiKey(t, g, i)); if (!x) throw new Sc4Error('TGI not found'); return x[0].read(x[1]); },
      ofType(t) { const out = []; for (const [k, [, e]] of tgi) if (e.type === t) out.push([e.type, e.group, e.instance]); return out; },
    };
  }
  const pv = (ex, pid, dflt = null) => { const v = ex.props.get(pid); return v === undefined ? dflt : v[1]; };
  const asList = v => Array.isArray(v) ? v : [v];
  const isNum = v => typeof v === 'number' || v instanceof PyFloat;
  const pyInt = v => typeof v === 'boolean' ? +v : Math.trunc(num(v));
  function buildings(idx) {                 // catalog.buildings -> [buildings, lots]
    const exes = [];
    for (const k of idx.ofType(T_EXEMPLAR)) {
      try { exes.push([k, parseExemplar(idx.read(...k))]); } catch (e) { if (!(e instanceof Sc4Error)) throw e; }
    }
    const lots = [];
    for (const [k, ex] of exes) {
      const t = pv(ex, 0x10);
      if (t !== 0x10) continue;
      const objs = [];
      for (const pid of ex.order) {
        if (pid >= 0x88EDC900 && pid <= 0x88EDCDFF) {
          const r = asList(pv(ex, pid)).map(x => pyInt(x) >>> 0);
          const sgn = r.map(x => x & 0x80000000 ? x - 4294967296 : x);
          objs.push({ type: r[0], rot: r[2] & 3, x: sgn[3] / 65536.0, z: sgn[5] / 65536.0, ids: r.slice(12) });
        }
      }
      const sz = asList(pv(ex, 0x88EDC790, [0, 0]));
      lots.push({ tgi: k, name: pv(ex, 0x20, ''), size: [pyInt(sz[0]), pyInt(sz[1])], stage: pv(ex, 0x27812837), objects: objs });
    }
    const out = [];
    for (const [k, ex] of exes) {
      if (pv(ex, 0x10) !== 2) continue;
      const rk = pv(ex, 0x27812821);
      if (!Array.isArray(rk) || rk.length < 3 || rk[0] !== T_S3D) continue;
      const nk = pv(ex, 0x8A416A99);
      let title = null;
      if (Array.isArray(nk) && nk.length === 3 && idx.has(...nk)) title = pyStrip(ltext(idx.read(...nk)));
      const fams = asList(pv(ex, 0x27812870, [])).map(x => pyInt(x) >>> 0);
      const cap = asList(pv(ex, 0x27812834, []));
      const capPairs = []; for (let i = 0; i + 1 < cap.length; i += 2) capPairs.push([cap[i], cap[i + 1]]);
      const b = { tgi: k, name: pv(ex, 0x20, ''), title, model: rk.slice(0, 3), size_m: asList(pv(ex, 0x27812810, [0, 0, 0])).map(x => Number(num(x))),
        wealth: pv(ex, 0x27812832), purpose: pv(ex, 0x27812833), capacity: capPairs, families: fams, lots: [] };
      for (const lot of lots) for (const o of lot.objects) {
        if (o.type === 0 && (o.ids.includes(k[2]) || fams.some(f => o.ids.includes(f))))
          b.lots.push({ name: lot.name, size: lot.size, stage: lot.stage, rot: o.rot, x: o.x, z: o.z, via: o.ids.includes(k[2]) ? 'building' : 'family' });
      }
      out.push(b);
    }
    // sorted(key=name.lower()), stable
    const low = s => String(s).toLowerCase();
    out.sort((a, b) => { const x = low(a.name), y = low(b.name); return x < y ? -1 : x > y ? 1 : 0; });
    return [out, lots];
  }

  // ================================================================================================ views
  const VIEW_NAMES = ['S', 'W', 'N', 'E'];
  const SC3_SLOT_AZ = [-45.0, -135.0, 135.0, 45.0];
  const toModel1 = (p, r) => { let [x, y, z] = p; for (let k = 0; k < ((r % 4) + 4) % 4; k++) { const nx = z, nz = -x; x = nx; z = nz; } return [x, y, z]; };
  function solve(G, R) {                    // views._solve
    const n = G.length, m = R[0].length;
    const a = G.map((row, i) => row.concat(R[i]));
    for (let c = 0; c < n; c++) {
      let p = c;
      for (let i = c + 1; i < n; i++) if (Math.abs(a[i][c]) > Math.abs(a[p][c])) p = i;
      if (a[p][c] === 0.0) throw new Sc4Error('camera fit: singular normal equations');
      const t = a[c]; a[c] = a[p]; a[p] = t;
      for (let i = c + 1; i < n; i++) {
        const f = a[i][c] / a[c][c];
        for (let j = c; j < n + m; j++) a[i][j] = a[i][j] - f * a[c][j];
      }
    }
    const x = []; for (let i = 0; i < n; i++) x.push(new Array(m).fill(0.0));
    for (let i = n - 1; i >= 0; i--) for (let j = 0; j < m; j++) {
      let s = a[i][n + j];
      for (let k = i + 1; k < n; k++) s = s - a[i][k] * x[k][j];
      x[i][j] = s / a[i][i];
    }
    return x;
  }
  function fitCamera(P, UV, tw, th) {       // views.fit_camera -> [A, err, d]
    const X = P.map(p => [p[0], p[1], p[2], 1.0]), T = UV.map(t => [t[0] * tw, t[1] * th]);
    const G = [], R = [];
    for (let i = 0; i < 4; i++) {
      G.push([]); R.push([]);
      for (let j = 0; j < 4; j++) { let s = 0.0; for (let k = 0; k < X.length; k++) s = s + X[k][i] * X[k][j]; G[i].push(s); }
      for (let j = 0; j < 2; j++) { let s = 0.0; for (let k = 0; k < X.length; k++) s = s + X[k][i] * T[k][j]; R[i].push(s); }
    }
    const A = solve(G, R);
    let err = 0.0;
    for (let k = 0; k < X.length; k++) for (let j = 0; j < 2; j++)
      err = Math.max(err, Math.abs((((X[k][0] * A[0][j] + X[k][1] * A[1][j]) + X[k][2] * A[2][j]) + A[3][j]) - T[k][j]));
    const m0 = [A[0][0], A[1][0], A[2][0]], m1 = [A[0][1], A[1][1], A[2][1]];
    let d = [m0[1] * m1[2] - m0[2] * m1[1], m0[2] * m1[0] - m0[0] * m1[2], m0[0] * m1[1] - m0[1] * m1[0]];
    const ln = Math.sqrt((d[0] * d[0] + d[1] * d[1]) + d[2] * d[2]);
    d = [d[0] / ln, d[1] / ln, d[2] / ln];
    if (d[1] > 0) d = [-d[0], -d[1], -d[2]];
    return [A, err, d];
  }
  function loadViews(idx, b, zoom = 4) {     // views.load_views
    const [t, g, base] = b.model, out = [];
    for (let r = 0; r < 4; r++) {
      const inst = (base + (zoom << 8) + (r << 4)) >>> 0;
      if (!idx.has(t, g, inst)) throw new Sc4Error(b.name + ' view ' + r + ': S3D ' + hexU(inst, 8) + ' not found');
      const meshes = readS3D(idx.read(t, g, inst));
      if (meshes.length !== 1 || meshes[0].mat.tex.length !== 1) throw new Sc4Error(b.name + ' view ' + r + ': ' + meshes.length + ' meshes, only one textured mesh is read');
      const { P, UV, tris, mat } = meshes[0];
      const tid = mat.tex[0].id;
      if (!idx.has(T_FSH, g, tid)) throw new Sc4Error(b.name + ' view ' + r + ': texture ' + hexU(tid, 8) + ' not found');
      const bm = readFshFirst(idx.read(T_FSH, g, tid));
      const [A, err, d] = fitCamera(P, UV, bm.w, bm.h);
      const dm = toModel1(d, r);
      out.push({ r, name: VIEW_NAMES[r], P_view: P, P: P.map(p => toModel1(p, r)), A, tex_size: [bm.w, bm.h], UV, tris, tex: bm.image,
        cam: { fit_err_px: err, forward_view: d, azimuth_model: degrees(Math.atan2(-dm[0], -dm[2])), elevation: degrees(Math.asin(-d[1])),
          px_per_m: Math.sqrt((A[0][0] * A[0][0] + A[1][0] * A[1][0]) + A[2][0] * A[2][0]) } });
    }
    return out;
  }
  function matchView(vs, slot) {             // min(): the first of equal keys
    const a = SC3_SLOT_AZ[slot];
    let best = null, bk = Infinity;
    for (const v of vs) { const k = Math.abs(pyMod(v.cam.azimuth_model - a + 180, 360) - 180); if (best === null || k < bk) { best = v; bk = k; } }
    return best;
  }
  function hiddenFaces(v, floorY = 0.05) {   // views.hidden_faces
    const Pv = v.P_view;
    if (Pv.length !== 7) return null;
    // ndarray.min(0) / max(0): on equal values (0.0 / -0.0) numpy keeps the later one
    const lo = [0, 1, 2].map(c => Pv.slice(1).reduce((m, p) => m < p[c] ? m : p[c], Pv[0][c]));
    const hi = [0, 1, 2].map(c => Pv.slice(1).reduce((m, p) => m > p[c] ? m : p[c], Pv[0][c]));
    const d = v.cam.forward_view, quads = [];
    for (const ax of [0, 2]) for (const [side, val] of [[-1, lo[ax]], [1, hi[ax]]]) {
      if (side * d[ax] > 0) {
        const o = ax === 0 ? 2 : 0, q = [];
        for (const [a_, b_] of [[lo[o], lo[1]], [hi[o], lo[1]], [hi[o], hi[1]], [lo[o], hi[1]]]) { const p = [0.0, 0.0, 0.0]; p[ax] = val; p[o] = a_; p[1] = b_; q.push(p); }
        quads.push(q);
      }
    }
    const y = lo[1] + floorY;
    quads.push([[lo[0], y, lo[2]], [hi[0], y, lo[2]], [hi[0], y, hi[2]], [lo[0], y, hi[2]]]);
    const P = quads.flat(), A = v.A, [tw, th] = v.tex_size;
    const UV = P.map(p => [0, 1].map(j => (((p[0] * A[0][j] + p[1] * A[1][j]) + p[2] * A[2][j]) + A[3][j]) / [tw, th][j]));
    const tris = []; for (let k = 0; k < quads.length; k++) tris.push([4 * k, 4 * k + 1, 4 * k + 2], [4 * k, 4 * k + 2, 4 * k + 3]);
    return [P.map(p => toModel1(p, v.r)), UV, tris];
  }

  // ================================================================================================ sc4conv rules
  const EDITABLE = ['name', 'class', 'lot', 'weight', 'enabled', 'scale', 'rotate_deg', 'notes', 'x_bldrender'];
  const CELL_M = 16.0, ZOOM5 = 4;
  const CLASS_LOTS = { 3100: [1], 3300: [1], 3500: [1, 2], 3700: [2, 3], 3900: [2] };
  const CLASS_FALLBACK = { 3100: [3700], 3300: [3900], 3500: [3500] };
  const pyReprVal = v => v === null || v === undefined ? 'None' : v === true ? 'True' : v === false ? 'False' : v instanceof PyFloat ? pyRepr(v.v)
    : Array.isArray(v) ? '[' + v.map(pyReprVal).join(', ') + ']' : typeof v === 'string' ? "'" + v + "'" : String(v);
  const pyTruthy = v => !(v === null || v === undefined || v === false || num(v) === 0 || v === '' || (Array.isArray(v) && !v.length));
  function lotFor(b) {
    const [w, , d] = b.size_m;
    return Math.max(1, Math.trunc(Math.ceil(Math.max(w, d) / CELL_M - 1e-6)));
  }
  function classFor(b) {                    // sc4conv.class_for -> [class, why]
    const w = pyTruthy(b.wealth) ? b.wealth : 1;
    const cap = b.capacity.length ? b.capacity.reduce((s, [, c]) => s + num(c), 0) : 0;
    if (!(num(b.purpose) === 1 || b.purpose === true)) return [null, 'purpose ' + pyReprVal(b.purpose) + ': only residential (1) is mapped'];
    const dens = cap <= 60 ? 0 : (cap <= 400 ? 1 : 2);
    let cls = [3100, 3700, 4300][dens] + 200 * (Math.min(Math.max(num(w), 1), 3) - 1);
    let why = 'SC4 residential, wealth ' + Math.trunc(num(w)) + ', capacity ' + Math.trunc(cap) + ' -> ' + ['light', 'medium', 'dense'][dens] + ' density';
    const n = lotFor(b);
    if (!(CLASS_LOTS[cls] || [n]).includes(n)) {
      const alt = (CLASS_FALLBACK[cls] || []).filter(c => (CLASS_LOTS[c] || []).includes(n));
      if (alt.length) { why += '; class ' + cls + ' has no ' + n + 'x' + n + ' base, ' + alt[0] + ' does'; cls = alt[0]; }
    }
    return [cls, why];
  }
  function designOf(name) {
    let m = /^JFM_(.+?)[ _](blue|blu|gray|gry|grey|green|grn|mauve|white|wht|yellow|yllw)(?=[ _]|$)/i.exec(name);
    if (m) return [m[1].replace(/_/g, ' '), m[2]];
    m = /^JFM_([A-Za-z]+?)(Blue|Gray|Green|Mauve|White|Yellow)/.exec(name);
    if (m) return [m[1], m[2]];
    return [name, ''];
  }
  const stemOf = name => name.replace(/[^A-Za-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
  const jv = v => Array.isArray(v) ? v.map(jv) : v;          // exemplar values print as they are (floats are PyFloat)
  const tgiHex = t => t.map(x => hexU(x, 8)).join('-');
  const textBytes = s => { const b = B.cp1252Encode(s); return b || new TextEncoder().encode(s); };   // open(..., 'w'): cp1252

  function writeBuilding(idx, b, files, enabled, style, fill) {   // sc4conv.write_building -> entry
    const vs = loadViews(idx, b, ZOOM5);
    const stem = stemOf(b.name);
    const obj = ['# ' + b.name + ', converted from SimCity 4 by sc4conv.py (local use only: see the pack licence)', 'mtllib ' + stem + '.mtl'];
    const mtl = [], pngs = [];
    for (const v of vs) {
      const png = stem + '_' + v.name + '.png';
      pngs.push([png, { w: v.tex_size[0], h: v.tex_size[1], d: v.tex }]);
      mtl.push('newmtl sc4_' + v.name, 'Kd 1 1 1', 'map_Kd ' + png, '');
    }
    let vbase = 1;
    const emit = (P, UV, tris) => {
      for (const p of P) obj.push('v ' + pyFixed(p[0], 5) + ' ' + pyFixed(p[1], 5) + ' ' + pyFixed(p[2], 5));
      for (const uv of UV) obj.push('vt ' + pyFixed(uv[0], 6) + ' ' + pyFixed(1.0 - uv[1], 6));
      for (const t of tris) obj.push('f ' + t.map(i => (vbase + i) + '/' + (vbase + i)).join(' '));
      vbase += P.length;
    };
    for (let slot = 0; slot < 4; slot++) {
      const v = matchView(vs, slot);
      obj.push('g sc3slot' + slot, 'usemtl sc4_' + v.name);
      emit(v.P, v.UV, v.tris);
      const hf = fill ? hiddenFaces(v) : null;
      if (hf) emit(...hf);
    }
    const [cls, why] = classFor(b);
    const n = lotFor(b);
    const [design, colour] = designOf(b.name);
    const lines = pySplitlines(b.title || b.name);
    if (!lines.length) throw new Sc4Error(b.name + ': empty name');
    const title = pyStrip(lines[0]).replace(/,+$/, '');
    const sc4lots = [...new Set(b.lots.map(l => { const s = l.size.slice().sort((x, y) => x - y); return s[0] + 'x' + s[1]; }))].sort();
    const entry = {
      file: stem + '.obj', name: title, kind: 'growable', class: cls, lot: [n, n], weight: 1,
      height_m: new PyFloat(pyRound(b.size_m[1], 2)), scale: new PyFloat(1.0), rotate_deg: 0, style: 'any',
      enabled: !!(enabled && cls !== null),
      notes: why + '. SC4 lots ' + (sc4lots.join(', ') || 'none') + ', the SC3 lot keeps the house (' + pyFixed(b.size_m[0], 1) + ' x ' + pyFixed(b.size_m[2], 1) + ' m) and drops the yard.',
      x_bldrender: { style },
      x_sc4: {
        exemplar: b.name, design, colour, building_tgi: tgiHex(b.tgi), model_key: tgiHex(b.model),
        wealth: jv(b.wealth), purpose: jv(b.purpose),
        capacity: b.capacity.map(([g, c]) => [hexU(num(g), 4), jv(c)]),
        family: b.families.map(f => hexU(f, 8)), size_m: b.size_m.map(x => new PyFloat(pyRound(x, 3))),
        lots: b.lots.map(l => ({ size: l.size, stage: jv(l.stage), name: l.name })),
        views: Object.fromEntries([0, 1, 2, 3].map(s => ['slot' + s, matchView(vs, s).name])),
        camera: Object.fromEntries(vs.map(v => [v.name, { azimuth: new PyFloat(pyRound(v.cam.azimuth_model, 2)),
          elevation: new PyFloat(pyRound(v.cam.elevation, 2)), px_per_m: new PyFloat(pyRound(v.cam.px_per_m, 3)) }])),
      },
    };
    files.set(stem + '.obj', textBytes(obj.join('\n') + '\n'));
    files.set(stem + '.mtl', textBytes(mtl.join('\n')));
    for (const [png, im] of pngs) files.set(png, im);         // RGBA image; png() turns it into PNG bytes
    return entry;
  }

  // convert(sources, opt) -> { files: Map rel -> Uint8Array (OBJ, MTL, PNG, models.json), models, report }
  //   opt.old: the previous models.json text (keeps the fields the player changed since the converter wrote them)
  //   opt.all, opt.style ('baked'), opt.fill (true), opt.log, opt.progress(i, n)
  async function convert(sources, opt = {}) {
    const log = opt.log || (() => {}), style = opt.style || 'baked', fill = opt.fill !== false;
    const idx = await buildIndex(sources, log);
    const [bs, lots] = buildings(idx);
    const report = [idx.files.length + ' DBPF files, ' + bs.length + ' buildings with S3D models, ' + lots.length + ' lots'];
    log(report[0]);
    const old = new Map();
    if (opt.old) { const j = pyLoad(opt.old); for (const m of (j && j.models) || []) old.set(m.file, m); }
    const keyOf = b => b.families.length ? 'F' + b.families.join(',') : 'D' + designOf(b.name)[0].toLowerCase();
    const fam = new Map();
    for (const b of bs) { const k = keyOf(b); if (!fam.has(k)) fam.set(k, []); fam.get(k).push(b); }
    const pick = new Map(); let kk = 0;
    for (const [d, members] of fam) pick.set(d, members[kk++ % members.length].tgi);
    const files = new Map(), models = [];
    for (let bi = 0; bi < bs.length; bi++) {
      const b = bs[bi];
      if (opt.progress) await opt.progress(bi, bs.length, b);
      const first = pick.get(keyOf(b)) === b.tgi;
      let e;
      try { e = writeBuilding(idx, b, files, opt.all || first, style, fill); }
      catch (ex) { if (!(ex instanceof Sc4Error)) throw ex; const line = '  skip ' + b.name + ': ' + ex.message; log(line); report.push(line); continue; }
      const auto = {}; for (const k of EDITABLE) auto[k] = e[k];
      e.x_sc4.auto = auto;
      const o = old.get(e.file);
      if (o) {
        const prev = (o.x_sc4 && o.x_sc4.auto) || {};
        for (const k of EDITABLE) if (k in o && k in prev && !pyEq(o[k], prev[k])) e[k] = o[k];
      }
      models.push(e);
    }
    const text = pyDump({ sc3models: 1, models }, 1);
    for (const [k, v] of files) if (!(v instanceof Uint8Array)) files.set(k, B.encodePNG(v));
    files.set('models.json', new TextEncoder().encode(text));
    const ne = models.filter(m => m.enabled).length;
    report.push(models.length + ' models, ' + ne + ' enabled');
    log(report[report.length - 1]);
    return { files, models: JSON.parse(text).models, text, report };
  }

  // ================================================================================================ inputs
  // Python's walk (catalog.dbpf_files): a folder's files sorted, then its folders sorted, depth first
  function walkOrder(tree) {               // tree: { files: Map name -> src, dirs: Map name -> tree }
    const out = [];
    const rec = (t, pre) => {
      for (const n of [...t.files.keys()].sort()) if (isDbpfName(n)) out.push(Object.assign({ path: pre + n }, t.files.get(n)));
      for (const n of [...t.dirs.keys()].sort()) rec(t.dirs.get(n), pre + n + '/');
    };
    rec(tree, '');
    return out;
  }
  const newTree = () => ({ files: new Map(), dirs: new Map() });
  function treeAdd(tree, parts, src) {
    let t = tree;
    for (const p of parts.slice(0, -1)) { if (!t.dirs.has(p)) t.dirs.set(p, newTree()); t = t.dirs.get(p); }
    t.files.set(parts[parts.length - 1], src);
  }
  const isArchive = n => /\.(zip|jar)$/i.test(n);
  // .zip / .jar reader (stored and deflate entries; an archive inside is read as a folder of the same name)
  async function inflateRaw(data) {
    if (typeof DecompressionStream === 'undefined') throw new Sc4Error('this browser cannot unpack .zip files (no DecompressionStream)');
    const ds = new DecompressionStream('deflate-raw');
    return new Uint8Array(await new Response(new Blob([data]).stream().pipeThrough(ds)).arrayBuffer());
  }
  function zipEntries(z) {
    const r = new Rd(z);
    let eo = -1;
    for (let p = z.length - 22; p >= Math.max(0, z.length - 22 - 65535); p--) if (z[p] === 0x50 && z[p + 1] === 0x4B && z[p + 2] === 5 && z[p + 3] === 6) { eo = p; break; }
    if (eo < 0) throw new Sc4Error('not a .zip file');
    const n = r.u16(eo + 10); let p = r.u32(eo + 16);
    if (p === 0xFFFFFFFF || n === 0xFFFF) throw new Sc4Error('ZIP64 archives are not read: unpack it and pick the folder');
    const out = [];
    for (let k = 0; k < n; k++) {
      if (r.u32(p) !== 0x02014b50) throw new Sc4Error('broken .zip directory');
      const flags = r.u16(p + 8), method = r.u16(p + 10), csize = r.u32(p + 20), usize = r.u32(p + 24);
      const nl = r.u16(p + 28), xl = r.u16(p + 30), cl = r.u16(p + 32), lho = r.u32(p + 42);
      const raw = z.subarray(p + 46, p + 46 + nl);
      const name = flags & 0x800 ? new TextDecoder('utf-8').decode(raw) : latin1(raw);
      out.push({ name, method, csize, usize, lho, flags });
      p += 46 + nl + xl + cl;
    }
    return out;
  }
  async function zipRead(z, e) {
    const r = new Rd(z);
    if (r.u32(e.lho) !== 0x04034b50) throw new Sc4Error(e.name + ': broken .zip entry');
    if (e.flags & 1) throw new Sc4Error(e.name + ': encrypted .zip entries are not read');
    const start = e.lho + 30 + r.u16(e.lho + 26) + r.u16(e.lho + 28);
    const raw = z.subarray(start, start + e.csize);
    if (e.method === 0) return raw;
    if (e.method === 8) return inflateRaw(raw);
    throw new Sc4Error(e.name + ': .zip method ' + e.method + ' is not read');
  }
  async function addArchive(tree, bytes, depth = 0) {
    for (const e of zipEntries(bytes)) {
      if (e.name.endsWith('/')) continue;
      const parts = e.name.split('/').filter(Boolean);
      const leaf = parts[parts.length - 1];
      if (isArchive(leaf) && depth < 3) {
        let t = tree; for (const p of parts) { if (!t.dirs.has(p)) t.dirs.set(p, newTree()); t = t.dirs.get(p); }
        await addArchive(t, await zipRead(bytes, e), depth + 1);
      } else if (isDbpfName(leaf)) {
        let cache = null;
        treeAdd(tree, parts, { bytes: async () => cache || (cache = await zipRead(bytes, e)) });
      }
    }
  }
  // inputs: [{ path: 'a/b/x.dat', bytes: async () => Uint8Array }] (folder listing or File objects), archives read
  async function sourcesFrom(inputs) {
    const tree = newTree();
    for (const it of inputs) {
      const parts = it.path.split('/').filter(Boolean), leaf = parts[parts.length - 1];
      if (isArchive(leaf)) {
        let t = tree; for (const p of parts) { if (!t.dirs.has(p)) t.dirs.set(p, newTree()); t = t.dirs.get(p); }
        await addArchive(t, await it.bytes());
      } else if (isDbpfName(leaf)) treeAdd(tree, parts, { bytes: it.bytes });
    }
    return walkOrder(tree);
  }
  // a File System Access folder handle -> inputs (recursive)
  async function handleInputs(dir, pre = '', out = []) {
    for await (const [name, h] of dir.entries()) {
      if (h.kind === 'directory') { if (name !== 'sc3build') await handleInputs(h, pre + name + '/', out); }
      else if (isDbpfName(name) || isArchive(name)) out.push({ path: pre + name, bytes: async () => new Uint8Array(await (await h.getFile()).arrayBuffer()) });
    }
    return out;
  }
  // File objects (webkitdirectory list, or picked .zip / .jar files) -> inputs
  const fileInputs = files => files.filter(f => isDbpfName(f.name) || isArchive(f.name)).map(f => {
    const parts = String(f.webkitRelativePath || f.name).split('/'); if (parts.length > 1) parts.shift();
    return { path: parts.join('/'), bytes: async () => new Uint8Array(await f.arrayBuffer()) };
  });

  // The models-folder view the importer installs from: the converted files in memory over an optional real folder
  // (the picked SC4 folder: models.json and sc3build\ids.json are saved there so the choices and the ids stay).
  function overlayFS(mem, base) {
    const lk = new Map([...mem.keys()].map(k => [k.toLowerCase(), k]));
    const put = new Map();
    return {
      async get(rel) {
        const k = String(rel).toLowerCase();
        if (put.has(k)) return put.get(k);
        if (lk.has(k)) return mem.get(lk.get(k));
        return base ? base.get(rel) : null;
      },
      async exists(rel) { const k = String(rel).toLowerCase(); return put.has(k) || lk.has(k) || (base ? base.exists(rel) : false); },
      async put(rel, data) { if (base) await base.put(rel, data); else put.set(String(rel).toLowerCase(), data); },
      async list() { const names = new Set([...mem.keys()].filter(n => !n.includes('/'))); if (base) for (const n of await base.list()) names.add(n); return [...names]; },
      written: put,
    };
  }

  return {
    version: '2026-11-19', Sc4Error, PyFloat,
    pyFixed, pyRound, pyRepr, pyDump, pyLoad, pyEq,
    qfsDecompress, readDbpf, parseExemplar, ltext, readS3D, readFshFirst, fshDecode,
    buildIndex, buildings, loadViews, fitCamera, matchView, hiddenFaces, classFor, lotFor, designOf, stemOf,
    convert, sourcesFrom, handleInputs, fileInputs, zipEntries, zipRead, overlayFS, isDbpfName, isArchive,
  };
}

globalThis.SC4WEB = SC4WEB_LIB(globalThis.BLDWEB || (typeof require === 'function' ? require('./bldweb.js') : null));
if (typeof module === 'object' && module.exports) module.exports = globalThis.SC4WEB;
