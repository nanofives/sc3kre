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
//   sc4conv/deps.py      task sc4props: dependency packs (the 1.7 GB BSC zip) read by streaming: the zip's central
//                        directory by slices, the jar inside inflated front to back, prop exemplars + entry index
//   sc4conv/props.py     the lot's props resolved, turned and placed in the house's frame (sc4conv.write_props)
//   sc4conv/rewards.py   task sc4civ: SC4's reward conditions from its Lua scripts; the player's SC4 install as a source
//                        (catalog.install_files, read by slices), SC4's civic buildings, parks, rewards and landmarks as
//                        bldimport kinds civic / reward / landmark (sc4conv.service_for), SC4's atlas views
//                        (views.compose_atlas), cohort parents (catalog.Index.full)
//   sc4conv.py --sc4     task sc4baseprops: the install as the last prop source of a download (installSource: picked
//                        with the download, or remembered from Open SC4 game), families pooled over all sources,
//                        a prop's model from the first source holding its views (props.resolve / plan)
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
  // task sc4pass2: text exemplars 'EQZT1###' (exemplar.parse_text_exemplar, the same steps)
  const TEXT_VT = { uint8: 0x0100, uint16: 0x0200, uint32: 0x0300, sint32: 0x0700, sint64: 0x0800, float32: 0x0900, bool: 0x0B00, string: 0x0C00 };
  const TEXT_BITS = { 0x0100: 8n, 0x0200: 16n, 0x0300: 32n, 0x0700: 32n, 0x0800: 64n };
  function textValue(vt, tok) {
    tok = pyStrip(tok);
    if (vt === 0x0900) {                    // float(tok) packed as float32 (struct.pack raises on overflow)
      let f;
      if (/^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/.test(tok)) f = Number(tok);
      else if (/^[+-]?(inf|infinity)$/i.test(tok)) f = tok[0] === '-' ? -Infinity : Infinity;
      else if (/^[+-]?nan$/i.test(tok)) f = NaN;
      else throw new Sc4Error('text exemplar: float ' + tok);
      const r = Math.fround(f);
      if (isFinite(f) && !isFinite(r)) throw new Sc4Error('text exemplar: float out of range');
      return new PyFloat(r);
    }
    if (vt === 0x0B00) {
      const l = tok.toLowerCase();
      if (l === 'true' || l === '1' || l === '0x01') return true;
      if (l === 'false' || l === '0' || l === '0x00') return false;
      throw new Sc4Error('text exemplar: bool ' + tok);
    }
    let v;
    try {                                   // int(tok, 16) after a '0x' prefix, else int(tok)
      if (tok.toLowerCase().startsWith('0x')) { if (!/^0[xX][0-9a-fA-F]+$/.test(tok)) throw new Error(); v = BigInt(tok); }
      else { if (!/^[+-]?\d+$/.test(tok)) throw new Error(); v = BigInt(tok.replace(/^\+/, '')); }
    } catch (e) { throw new Sc4Error('text exemplar: number ' + tok); }
    const bits = TEXT_BITS[vt];
    v &= (1n << bits) - 1n;
    if ((vt === 0x0700 || vt === 0x0800) && (v >> (bits - 1n))) v -= 1n << bits;
    return Number(v);
  }
  function parseTextExemplar(b) {
    const t = latin1(b);
    const lines = t.split('\r').join('\n').split('\n').map(pyStrip).filter(x => x);
    let parent = [0, 0, 0];
    const props = new Map(), order = [];
    const need = (i, what) => { if (i < 0) throw new Sc4Error('text exemplar: ' + what); return i; };
    const pyHexInt = s => { s = pyStrip(s); if (!/^[+-]?(0[xX])?[0-9a-fA-F]+$/.test(s)) throw new Sc4Error('text exemplar: ' + s); const neg = s[0] === '-'; let v = BigInt(/0[xX]/.test(s) ? s.replace(/^[+-]/, '') : '0x' + s.replace(/^[+-]/, '')); if (neg) v = -v; return v; };
    for (const ln of lines.slice(1)) {
      if (ln.startsWith('ParentCohort=')) {
        const ks = ln.slice(need(ln.indexOf('{'), 'cohort') + 1, need(ln.lastIndexOf('}'), 'cohort')).split(',');
        parent = ks.slice(0, 3).map(k => Number(pyHexInt(k) & 0xFFFFFFFFn));
        continue;
      }
      if (ln.startsWith('PropCount=')) continue;
      const c = need(ln.indexOf(':'), 'property');
      const pid = Number(pyHexInt(ln.slice(0, c)) & 0xFFFFFFFFn);
      const e = need(ln.indexOf('}=', c), 'property');
      const rest = ln.slice(e + 2);
      const c1 = rest.indexOf(':'), c2 = c1 < 0 ? -1 : rest.indexOf(':', c1 + 1);
      if (c2 < 0) throw new Sc4Error('text exemplar: property');
      const typ = rest.slice(0, c1), cntS = rest.slice(c1 + 1, c2), vals = rest.slice(c2 + 1);
      const vt = TEXT_VT[pyStrip(typ).toLowerCase()];
      if (vt === undefined) throw new Sc4Error('text exemplar: value type ' + typ);
      const cs = pyStrip(cntS);
      let cnt;
      if (cs.toLowerCase().startsWith('0x')) cnt = Number(pyHexInt(cs)); else { if (!/^[+-]?\d+$/.test(cs)) throw new Sc4Error('text exemplar: count'); cnt = parseInt(cs, 10); }
      const body = vals.slice(need(vals.indexOf('{'), 'values') + 1, need(vals.lastIndexOf('}'), 'values'));
      let val;
      if (vt === 0x0C00) {
        const q0 = body.indexOf('"'), q1 = body.lastIndexOf('"');
        val = q0 >= 0 && q1 > q0 ? body.slice(q0 + 1, q1) : body;
      } else {
        const toks = body.split(',').filter(x => pyStrip(x));
        const vs = toks.map(x => textValue(vt, x));
        if (!cnt && !vs.length) throw new Sc4Error('text exemplar: no value');
        val = cnt ? vs : vs[0];
      }
      props.set(pid, [vt, val]);
      order.push(pid);
    }
    return { kind: latin1(b.subarray(0, 4)), parent, props, order };
  }
  function parseExemplar(b) {               // exemplar.parse_exemplar; float values are PyFloat (they print as floats)
    const sig = latin1(b.subarray(0, 4));
    if (sig === 'EQZT' || sig === 'CQZT') return parseTextExemplar(b);
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
    const files = [], tgi = new Map(), exc = new Map();
    for (const s of sources) {
      let f;
      try { f = sources.install && s.slice && s.size >= MAP_FROM ? await readDbpfLazy(s.path, s) : readDbpf(s.path, await s.bytes()); }   // task sc4civ
      catch (e) { if (log) log('  skip ' + s.path + ': ' + (e.message || e)); continue; }
      files.push(f);
      for (const e of f.entries) if (e.type !== T_DIR) tgi.set(tgiKey(e.type, e.group, e.instance), [f, e]);
    }
    const idx = {
      files, tgi, install: !!sources.install,
      has: (t, g, i) => tgi.has(tgiKey(t, g, i)),
      read(t, g, i) { const x = tgi.get(tgiKey(t, g, i)); if (!x) throw new Sc4Error('TGI not found'); return x[0].read(x[1]); },
      ofType(t) { const out = []; for (const [k, [, e]] of tgi) if (e.type === t) out.push([e.type, e.group, e.instance]); return out; },
      exemplar(k) { const kk = tgiKey(...k); if (!exc.has(kk)) exc.set(kk, parseExemplar(idx.read(...k))); return exc.get(kk); },
      full(k, depth = 0) {                  // catalog.Index.full (task sc4civ): the parent cohort's properties under its own
        const ex = idx.exemplar(k), par = ex.parent.map(x => x >>> 0);
        if (!par.some(x => x) || depth >= 8 || !idx.has(...par)) return ex;
        let pe; try { pe = idx.full(par, depth + 1); } catch (e) { if (e instanceof Sc4Error || e instanceof RangeError) return ex; throw e; }
        const props = new Map(pe.props); for (const [k2, v] of ex.props) props.set(k2, v);
        return Object.assign({}, ex, { props, order: pe.order.concat(ex.order.filter(k2 => !pe.props.has(k2))) });
      },
    };
    return idx;
  }
  const pv = (ex, pid, dflt = null) => { const v = ex.props.get(pid); return v === undefined ? dflt : v[1]; };
  const asList = v => Array.isArray(v) ? v : [v];
  const sc = v => Array.isArray(v) && v.length === 1 ? v[0] : v;     // catalog.sc (task sc4pass2)
  const isNum = v => typeof v === 'number' || v instanceof PyFloat;
  const pyInt = v => typeof v === 'boolean' ? +v : Math.trunc(num(v));
  function buildings(idx) {                 // catalog.buildings -> [buildings, lots]
    const exes = [];
    for (const k of idx.ofType(T_EXEMPLAR)) {
      try { exes.push([k, idx.full(k)]); } catch (e) { if (!(e instanceof Sc4Error)) throw e; }
    }
    const lots = [];
    for (const [k, ex] of exes) {
      const t = sc(pv(ex, 0x10));
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
      if (sc(pv(ex, 0x10)) !== 2) continue;
      const rk = pv(ex, 0x27812821);
      if (!Array.isArray(rk) || rk.length < 3 || rk[0] !== T_S3D) continue;
      const nk = pv(ex, 0x8A416A99);
      let title = null;
      if (Array.isArray(nk) && nk.length === 3 && idx.has(...nk)) title = pyStrip(ltext(idx.read(...nk)));
      const fams = asList(pv(ex, 0x27812870, [])).map(x => pyInt(x) >>> 0);
      const cap = asList(pv(ex, 0x27812834, []));
      const capPairs = []; for (let i = 0; i + 1 < cap.length; i += 2) capPairs.push([cap[i], cap[i + 1]]);
      const b = { tgi: k, name: pv(ex, 0x20, ''), title, model: rk.slice(0, 3), size_m: asList(pv(ex, 0x27812810, [0, 0, 0])).map(x => Number(num(x))),
        wealth: sc(pv(ex, 0x27812832)), purpose: sc(pv(ex, 0x27812833)), capacity: capPairs, families: fams, foundation: pv(ex, 0x88FCD877), lots: [],
        groups: groupsOf(ex) };
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
  // task sc4pass2 (views.compose_tiles): a view drawn as several textured meshes (the tall tower's zoom-5 views are
  // 12 / 14 tiles of 256 x 256) becomes one mesh on one canvas; same float order as views.py
  const TILE_SNAP = 0.35;
  function composeTiles(idx, g, meshes, label) {
    const pieces = [];
    for (const m of meshes) {
      const tid = m.mat.tex[0].id, fk = texKey(idx, g, tid);
      if (!idx.has(...fk)) throw new Sc4Error(label + ': texture ' + hexU(tid, 8) + ' not found');
      const bm = readFshFirst(idx.read(...fk));
      pieces.push({ P: m.P, q: m.UV.map(uv => [uv[0] * bm.w, uv[1] * bm.h]), tris: m.tris, bm, tid });
    }
    const G = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]], R = [[0.0, 0.0], [0.0, 0.0], [0.0, 0.0]], means = [];
    for (const pc of pieces) {
      const n = pc.P.length;
      if (!n) throw new Sc4Error(label + ': a tile without vertices');
      let mp = [0.0, 0.0, 0.0], mq = [0.0, 0.0];
      for (let k = 0; k < n; k++) {
        for (let c = 0; c < 3; c++) mp[c] = mp[c] + pc.P[k][c];
        for (let c = 0; c < 2; c++) mq[c] = mq[c] + pc.q[k][c];
      }
      mp = mp.map(x => x / n); mq = mq.map(x => x / n);
      means.push([mp, mq]);
      for (let k = 0; k < n; k++) {
        const dp = [0, 1, 2].map(c => pc.P[k][c] - mp[c]), dq = [0, 1].map(c => pc.q[k][c] - mq[c]);
        for (let i = 0; i < 3; i++) {
          for (let j = 0; j < 3; j++) G[i][j] = G[i][j] + dp[i] * dp[j];
          for (let j = 0; j < 2; j++) R[i][j] = R[i][j] + dp[i] * dq[j];
        }
      }
    }
    const L = solve(G, R);
    const ts = means.map(([mp, mq]) => [0, 1].map(j => mq[j] - ((mp[0] * L[0][j] + mp[1] * L[1][j]) + mp[2] * L[2][j])));
    for (let i = 0; i < pieces.length; i++) {   // task sc4civ: one screen picture, else an atlas (null)
      const pc = pieces[i], t = ts[i];
      for (let k = 0; k < pc.P.length; k++) for (let j = 0; j < 2; j++) {
        const e = ((pc.P[k][0] * L[0][j] + pc.P[k][1] * L[1][j]) + pc.P[k][2] * L[2][j]) + t[j] - pc.q[k][j];
        if (Math.abs(e) > TILE_FIT) return null;
      }
    }
    let offs = [];
    for (const t of ts) {
      const o = [];
      for (let j = 0; j < 2; j++) { const x = ts[0][j] - t[j], r = Math.floor(x + 0.5); if (Math.abs(x - r) > TILE_SNAP) return null; o.push(r); }
      offs.push(o);
    }
    const x0 = Math.min(...offs.map(o => o[0])), y0 = Math.min(...offs.map(o => o[1]));
    offs = offs.map(o => [o[0] - x0, o[1] - y0]);
    const W = Math.max(...offs.map((o, i) => o[0] + pieces[i].bm.w)), H = Math.max(...offs.map((o, i) => o[1] + pieces[i].bm.h));
    const canvas = new Uint8Array(W * H * 4);
    offs.forEach((o, i) => {
      const { w, h, image } = pieces[i].bm;
      for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
        const s = 4 * (y * w + x), d = 4 * ((o[1] + y) * W + o[0] + x);
        if (image[s + 3] > canvas[d + 3]) { canvas[d] = image[s]; canvas[d + 1] = image[s + 1]; canvas[d + 2] = image[s + 2]; canvas[d + 3] = image[s + 3]; }
      }
    });
    const P = [], UV = [], tris = [];
    offs.forEach((o, i) => {
      const pc = pieces[i], base = P.length;
      for (const t of pc.tris) tris.push(t.map(k => base + k));
      for (const p of pc.P) P.push([p[0], p[1], p[2]]);
      for (const qq of pc.q) UV.push([(qq[0] + o[0]) / W, (qq[1] + o[1]) / H]);
    });
    return { P, UV, tris, bm: { w: W, h: H, image: canvas, code: pieces[0].bm.code }, tid: pieces[0].tid, tiles: pieces.length };
  }
  function loadViews(idx, b, zoom = 4) {     // views.load_views
    const [t, g, base] = b.model, out = [];
    for (let r = 0; r < 4; r++) {
      const inst = (base + (zoom << 8) + (r << 4)) >>> 0;
      if (!idx.has(t, g, inst)) throw new Sc4Error(b.name + ' view ' + r + ': S3D ' + hexU(inst, 8) + ' not found');
      const meshes = readS3D(idx.read(t, g, inst));
      if (!meshes.length || meshes.some(m => m.mat.tex.length !== 1)) throw new Sc4Error(b.name + ' view ' + r + ': ' + meshes.length + ' meshes, only meshes with one texture each are read');
      let P, UV, tris, bm, tiles;
      if (meshes.length === 1) {
        ({ P, UV, tris } = meshes[0]);
        const tid = meshes[0].mat.tex[0].id, fk = texKey(idx, g, tid);
        if (!idx.has(...fk)) throw new Sc4Error(b.name + ' view ' + r + ': texture ' + hexU(tid, 8) + ' not found');
        bm = readFshFirst(idx.read(...fk));
        tiles = 1;
      } else ({ P, UV, tris, bm, tiles } = composeTiles(idx, g, meshes, b.name + ' view ' + r) || composeAtlas(idx, g, meshes, b.name + ' view ' + r));
      const [A, err, d] = fitCamera(P, UV, bm.w, bm.h);
      const dm = toModel1(d, r);
      out.push({ r, name: VIEW_NAMES[r], P_view: P, P: P.map(p => toModel1(p, r)), A, tex_size: [bm.w, bm.h], UV, tris, tex: bm.image, tiles,
        cam: { fit_err_px: err, forward_view: d, azimuth_model: degrees(Math.atan2(-dm[0], -dm[2])), elevation: degrees(Math.asin(-d[1])),
          px_per_m: Math.sqrt((A[0][0] * A[0][0] + A[1][0] * A[1][0]) + A[2][0] * A[2][0]) } });
    }
    return out;
  }
  function modelState(idx, b, zoom = 4) {    // views.model_state -> [state, why]
    const [t, g, base] = b.model;
    const keys = [0, 1, 2, 3].map(r => [t, g, (base + (zoom << 8) + (r << 4)) >>> 0]);
    const miss = keys.filter(k => !idx.has(...k));
    if (miss.length) return ['missing', 'no model in this download (S3D ' + tgiHex(miss[0]) + ')'];
    try {
      for (const k of keys) for (const m of readS3D(idx.read(...k))) for (const tx of m.mat.tex) {
        const fk = texKey(idx, g, tx.id);
        if (!idx.has(...fk)) continue;
        const im = readFshFirst(idx.read(...fk)).image;
        for (let i = 3; i < im.length; i += 4) if (im[i] > 0) return ['ok', null];
      }
    } catch (e) { if (!(e instanceof Sc4Error) && !(e instanceof RangeError)) throw e; return ['ok', null]; }
    return ['blank', 'a blank placeholder model (every texel transparent)'];
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

  // ================================================================================================ diagonal (task sc4diag)
  // views.foundation_diagonal: an SC4 lot turns a building in quarter turns only, so a house set at 45 degrees is told
  // by its foundation model (exemplar 0x88FCD877 -> type 0x11 exemplar, group 0x361CF9D5): the share of its
  // horizontal outline that runs at 26.6-63.4 degrees. Same steps and float order as views.py (byte identity).
  const FND_GROUP = 0x361CF9D5, DIAG_SHARE = 0.5;
  const cross3 = (P, t) => {
    const a = P[t[0]], b = P[t[1]], c = P[t[2]];
    const u = [b[0] - a[0], b[1] - a[1], b[2] - a[2]], v = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
    return [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]];
  };
  const lexLE = (a, b) => { for (let i = 0; i < 3; i++) { if (a[i] < b[i]) return true; if (a[i] > b[i]) return false; } return true; };
  function outlineShare45(P, tris) {        // views.outline_share_45 -> [share, length] or null
    const edges = new Map();
    for (let ti = 0; ti < tris.length; ti++) {
      const t = tris[ti];
      for (let i = 0; i < 3; i++) {
        const a = P[t[i]], b = P[t[(i + 1) % 3]];
        const [x, y] = lexLE(a, b) ? [a, b] : [b, a];
        const key = x.join(',') + '|' + y.join(',');
        if (!edges.has(key)) edges.set(key, { a: x, b: y, ts: [] });
        edges.get(key).ts.push(ti);
      }
    }
    let tot = 0.0, diag = 0.0;
    for (const { a, b, ts } of edges.values()) {
      if (ts.length === 2) {
        const n1 = cross3(P, tris[ts[0]]), n2 = cross3(P, tris[ts[1]]);
        const d = (n1[0] * n2[0] + n1[1] * n2[1]) + n1[2] * n2[2];
        const l1 = (n1[0] * n1[0] + n1[1] * n1[1]) + n1[2] * n1[2];
        const l2 = (n2[0] * n2[0] + n2[1] * n2[1]) + n2[2] * n2[2];
        if (d > 0 && d * d >= 0.998 * (l1 * l2)) continue;
      }
      const dx = Math.abs(b[0] - a[0]), dy = Math.abs(b[1] - a[1]), dz = Math.abs(b[2] - a[2]);
      const ln = Math.sqrt(dx * dx + dz * dz);
      if (dy > 0.05 || ln < 0.05) continue;
      tot += ln;
      if (Math.min(dx, dz) >= 0.5 * Math.max(dx, dz)) diag += ln;
    }
    return tot > 0 ? [diag / tot, tot] : null;
  }
  function foundationDiagonal(idx, b, zoom = 4) {   // views.foundation_diagonal -> { diagonal, foundation, share_45 } or null
    const inst = b.foundation;
    if (typeof inst !== 'number' || !Number.isInteger(inst)) return null;
    const k = [T_EXEMPLAR, FND_GROUP, inst >>> 0];
    if (!idx.has(...k)) return null;
    let ex;
    const P = [], tris = [];
    try {
      ex = parseExemplar(idx.read(...k));
      const rk = pv(ex, 0x27812821);
      if (!Array.isArray(rk) || rk.length < 3 || rk[0] !== T_S3D) return null;
      const key = [rk[0], rk[1], rk[2] + (zoom << 8)];
      if (!idx.has(...key)) return null;
      for (const m of readS3D(idx.read(...key))) {
        const base = P.length;
        for (const t of m.tris) tris.push(t.map(i => base + i));
        for (const p of m.P) P.push(p);
      }
    } catch (e) { if (!(e instanceof Sc4Error) && !(e instanceof RangeError)) throw e; return null; }
    const r = outlineShare45(P, tris);
    if (!r) return null;
    const name = pv(ex, 0x20);
    return { diagonal: r[0] >= DIAG_SHARE, foundation: name !== null ? name : hexU(k[2], 8), share_45: r[0] };
  }
  function pickColours(groups, isDiag) {    // sc4conv.pick_colours
    return groups.map((members, k) => {
      let c = members[k % members.length];
      if (isDiag(c)) { const ok = members.filter(m => !isDiag(m)); c = ok.length ? ok[k % ok.length] : null; }
      return c;
    });
  }
  const pct = x => Math.trunc(Number(pyFixed(x * 100, 0)));   // int(round(x * 100))
  const diagNote = dg => 'Diagonal, off by default: the SC4 author set this house at 45 degrees on its lot (its foundation ' + dg.foundation +
    ' runs at 45 degrees for ' + pct(dg.share_45) + '% of its outline), and SC3 has no diagonal buildings. ';

  // ================================================================================================ sc4conv rules
  const EDITABLE = ['name', 'class', 'lot', 'weight', 'enabled', 'scale', 'rotate_deg', 'notes', 'x_bldrender'];
  const CELL_M = 16.0, ZOOM5 = 4;
  const CLASS_LOTS = { 3100: [1], 3300: [1], 3500: [1, 2], 3700: [2, 3], 3900: [2],
    5100: [1], 5500: [1, 2], 5700: [2, 3, 4], 6100: [2, 3], 6300: [2, 3], 6700: [3, 4],
    8100: [1], 8300: [2], 8500: [1, 2, 3], 8700: [1, 2], 8900: [2, 3], 9100: [3, 4], 9300: [1, 2, 3] };
  const CLASS_FALLBACK = { 3100: [3700], 3300: [3900], 3500: [3500],
    5100: [5700, 6300], 5500: [6100, 6700], 5700: [6300, 5100], 6100: [6700, 5500], 6300: [5700, 5100], 6700: [6100, 5500],
    8100: [8300, 8500], 8300: [8500, 8100], 8500: [8300, 8100], 8700: [8900, 9100], 8900: [9100, 8700], 9100: [8900, 8700] };
  const PURPOSE_NAME = { 2: 'service commercial', 3: 'office', 5: 'agriculture', 6: 'dirty industry', 7: 'manufacturing', 8: 'high-tech industry' };
  const pyReprVal = v => v === null || v === undefined ? 'None' : v === true ? 'True' : v === false ? 'False' : v instanceof PyFloat ? pyRepr(v.v)
    : Array.isArray(v) ? '[' + v.map(pyReprVal).join(', ') + ']' : typeof v === 'string' ? "'" + v + "'" : String(v);
  const pyTruthy = v => !(v === null || v === undefined || v === false || num(v) === 0 || v === '' || (Array.isArray(v) && !v.length));
  function lotFor(b) {
    const [w, , d] = b.size_m;
    return Math.max(1, Math.trunc(Math.ceil(Math.max(w, d) / CELL_M - 1e-6)));
  }
  const pyEqInt = (v, k) => !Array.isArray(v) && v !== null && v !== undefined && typeof v !== 'string' && num(typeof v === 'boolean' ? +v : v) === k;
  function classFor(b) {                    // sc4conv.class_for -> [class, why]
    const w = pyTruthy(b.wealth) ? b.wealth : 1;
    const cap = b.capacity.length ? b.capacity.reduce((s, [, c]) => s + num(c), 0) : 0;
    const n = lotFor(b), p = b.purpose, wi = Math.trunc(num(w)), D3 = ['light', 'medium', 'dense'];
    let cls, why;
    if (pyEqInt(p, 1)) {
      const dens = cap <= 60 ? 0 : (cap <= 400 ? 1 : 2);
      cls = [3100, 3700, 4300][dens] + 200 * (Math.min(Math.max(num(w), 1), 3) - 1);
      why = 'SC4 residential, wealth ' + wi + ', capacity ' + Math.trunc(cap) + ' -> ' + D3[dens] + ' density';
    } else if (pyEqInt(p, 2) || pyEqInt(p, 3)) {
      const dens = cap <= 100 ? 0 : (cap <= 1000 ? 1 : 2), hi = Math.min(Math.max(num(w), 1), 3) >= 2 ? 1 : 0;
      cls = [[5100, 5700, 6300], [5500, 6100, 6700]][hi][dens];
      why = 'SC4 ' + PURPOSE_NAME[num(p)] + ', wealth ' + wi + ', ' + Math.trunc(cap) + ' jobs -> commercial ' + D3[dens] + ', ' + ['low', 'high'][hi] +
        ' wealth (SC3 has one commercial zone and two wealths: SC4 $ -> low, $$ and $$$ -> high)';
    } else if ([5, 6, 7, 8].some(k => pyEqInt(p, k))) {
      if (pyEqInt(p, 5)) { cls = 9300; why = 'SC4 agriculture -> farm'; }
      else {
        const dens = cap <= 100 ? 0 : (cap <= 1000 ? 1 : 2), clean = pyEqInt(p, 8) ? 1 : 0;
        cls = [[8100, 8300, 8500], [8700, 8900, 9100]][clean][dens];
        why = 'SC4 ' + PURPOSE_NAME[num(p)] + ', ' + Math.trunc(cap) + ' jobs -> industrial ' + ['dirty', 'clean'][clean] + ', ' + D3[dens];
      }
    } else return [null, 'purpose ' + pyReprVal(p) + ': not mapped'];
    if (n > 4) return [null, why + '; it needs a ' + n + 'x' + n + ' lot and SC3 lots are 1x1 to 4x4'];
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

  function writeBuilding(idx, b, files, enabled, style, fill, dg = null, keepDiag = false, versions = null, pctx = null) {   // sc4conv.write_building -> entry
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
    const svc = pctx && pctx.services ? pctx.services.get(tgiKey(...b.tgi)) || null : null;   // task sc4civ
    const [cls, why] = svc ? [null, svc.why] : classFor(b);
    const n = svc ? svc.lot : lotFor(b);
    const [design, colour] = designOf(b.name);
    const lines = pySplitlines(b.title || b.name);
    if (!lines.length) throw new Sc4Error(b.name + ': empty name');
    const title = pyStrip(lines[0]).replace(/,+$/, '');
    const sc4lots = [...new Set(b.lots.map(l => { const s = l.size.slice().sort((x, y) => x - y); return s[0] + 'x' + s[1]; }))].sort();
    const diag = !!(dg && dg.diagonal);
    const what = pyEqInt(b.purpose, 1) ? 'house' : 'building';
    const entry = {
      file: stem + '.obj', name: title, kind: 'growable', class: cls, lot: [n, n], weight: 1,
      height_m: new PyFloat(pyRound(b.size_m[1], 2)), scale: new PyFloat(1.0), rotate_deg: 0, style: 'any',
      enabled: !!(enabled && cls !== null && (keepDiag || !diag)),
      notes: (diag ? diagNote(dg) : '') + why + '. SC4 lots ' + (sc4lots.join(', ') || 'none') + ', the SC3 lot keeps the ' + what + ' (' + pyFixed(b.size_m[0], 1) + ' x ' + pyFixed(b.size_m[2], 1) + ' m) and drops the yard.',
      x_bldrender: { style },
      x_sc4: {
        exemplar: b.name, design, colour, building_tgi: tgiHex(b.tgi), model_key: tgiHex(b.model),
        wealth: jv(b.wealth), purpose: jv(b.purpose),
        capacity: b.capacity.map(([g, c]) => [hexU(num(g), 4), jv(c)]),
        family: b.families.map(f => hexU(f, 8)), size_m: b.size_m.map(x => new PyFloat(pyRound(x, 3))),
        lots: b.lots.map(l => ({ size: l.size, stage: jv(l.stage), name: l.name })),
        diagonal: diag,
        foundation: dg ? { name: dg.foundation, share_45: new PyFloat(pyRound(dg.share_45, 2)) } : null,
        views: Object.fromEntries([0, 1, 2, 3].map(s => ['slot' + s, matchView(vs, s).name])),
        camera: Object.fromEntries(vs.map(v => [v.name, { azimuth: new PyFloat(pyRound(v.cam.azimuth_model, 2)),
          elevation: new PyFloat(pyRound(v.cam.elevation, 2)), px_per_m: new PyFloat(pyRound(v.cam.px_per_m, 3)) }])),
      },
    };
    if (svc) {                              // task sc4civ: a civic look, a reward or a landmark (sc4conv.service_for)
      entry.kind = svc.kind;
      entry.enabled = !!(enabled && svc.ok && (keepDiag || !diag));
      entry.notes = (diag ? diagNote(dg) : '') + svc.note;
      if (svc.kind === 'reward') entry.name = pyStrip(title.replace(/[;=\r\n]+/g, ' ')) || b.name;
      entry.x_sc4.service = svc.x;
      for (const k of ['base', 'population', 'year', 'description']) if (k in svc) entry[k] = svc[k];
    }
    if (Math.max(...vs.map(v => v.tiles)) > 1) entry.x_sc4.tiles = Object.fromEntries(vs.map(v => [v.name, v.tiles]));
    if (versions && versions.length) entry.x_sc4.versions = versions;
    files.set(stem + '.obj', textBytes(obj.join('\n') + '\n'));
    files.set(stem + '.mtl', textBytes(mtl.join('\n')));
    const pinfo = pctx ? writeProps(b, vs, stem, obj, mtl, files, pctx, fill, n) : null;
    if (pinfo) { entry.x_sc4.props = pinfo; if (pinfo.on) entry.file = stem + '_props.obj'; }   // task sc4props
    for (const [png, im] of pngs) files.set(png, im);         // RGBA image; png() turns it into PNG bytes
    return entry;
  }

  // ================================================================================================ lot props (task sc4props)
  // sc4conv/deps.py + props.py + sc4conv.write_props, the same steps and float order: the props of the building's
  // smallest SC4 lot, from the download itself and from dependency packs read by streaming (a 1.7 GB zip holding a
  // 1.64 GB jar: never read whole; its central directory by slices, the jar inflated front to back, one .dat at a time).
  const DEPS_MIN = 200 * 1024 * 1024;       // an archive this large is a dependency pack, streamed (sourcesFrom)
  const P_TYPE = 0x10, P_NAME = 0x20, P_FAMILY = 0x27812870, P_RKT0 = 0x27812820, P_RKT1 = 0x27812821, P_RKT4 = 0x27812824;
  const P_INTERVAL = 0x0A751675, P_START = 0xCA7515CC, P_DURATION = 0x4A764564;
  const PROP_DATE = [7, 1], MONTH_DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31], NUDGE_M = 1.0;
  const turn = (x, z, q) => { for (let k = 0; k < ((q % 4) + 4) % 4; k++) { const nx = -z, nz = x; x = nx; z = nz; } return [x, z]; };  // props.turn, QUARTER -1
  const dayOfYear = (m, d) => { let s = 0; for (let k = 0; k < Math.max(0, Math.min(12, pyInt(m)) - 1); k++) s += MONTH_DAYS[k]; return s + pyInt(d) - 1; };
  const isInt = v => typeof v === 'number' && Number.isInteger(v);
  function propValue(src, inst, pid, dflt = null) {   // DepsIndex / OwnSource.prop_value (cohort parents, 8 deep)
    let rec = src.props.get(inst), seen = 0;
    while (rec && seen < 8) {
      if (rec.p.has(pid)) { const v = rec.p.get(pid); if (v !== null && v !== undefined) return v; }
      const par = rec.parent;
      rec = par.some(x => x) ? src.cohorts.get(tgiKey(par[0] >>> 0, par[1] >>> 0, par[2] >>> 0)) : null;
      seen++;
    }
    return dflt;
  }
  function familyMembers(src, fam) {
    if (!src.fam) {
      src.fam = new Map();
      for (const inst of src.props.keys()) {
        const v = propValue(src, inst, P_FAMILY);
        for (const f of (Array.isArray(v) ? v : v !== null ? [v] : [])) {
          const k = pyInt(f) >>> 0; if (!src.fam.has(k)) src.fam.set(k, []); src.fam.get(k).push(inst);
        }
      }
      for (const v of src.fam.values()) v.sort((a, b) => a - b);
    }
    return src.fam.get(fam) || [];
  }
  function exRec(ex, g) { const p = new Map(); for (const [k, v] of ex.props) p.set(k, v[1]); return { g, parent: ex.parent.map(x => x >>> 0), p }; }
  function propType(ex) { let t = ex.props.get(P_TYPE); t = t ? t[1] : null; return Array.isArray(t) && t.length === 1 ? t[0] : t; }
  function ownSource(idx) {                 // props.OwnSource: the download's own prop exemplars
    const props = new Map(), cohorts = new Map();
    for (const k of idx.ofType(T_EXEMPLAR).concat(idx.ofType(T_COHORT))) {
      let ex; try { ex = parseExemplar(idx.read(...k)); } catch (e) { if (e instanceof Sc4Error || e instanceof RangeError) continue; throw e; }
      if (k[0] === T_COHORT) cohorts.set(tgiKey(...k), exRec(ex, k[1]));
      else if (propType(ex) === 0x1E) props.set(k[2], exRec(ex, k[1]));
    }
    return { own: true, props, cohorts, fam: null, has: (t, g, i) => idx.has(t, g, i), read: (t, g, i) => idx.read(t, g, i) };
  }
  function propActive(src, inst) {          // props.active
    if (propValue(src, inst, P_INTERVAL) !== 365) return true;
    const st = propValue(src, inst, P_START), du = propValue(src, inst, P_DURATION);
    if (!Array.isArray(st) || st.length < 2 || !isInt(du)) return true;
    return pyMod(dayOfYear(...PROP_DATE) - dayOfYear(st[0], st[1]), 365) < du;
  }
  function modelOf(src, inst) {             // props.model_of -> [model, null] or [null, why]
    const r1 = propValue(src, inst, P_RKT1);
    if (Array.isArray(r1) && r1.length >= 3) return [[r1[0] >>> 0, r1[1] >>> 0, r1[2] >>> 0], null];
    const r4 = propValue(src, inst, P_RKT4);
    if (Array.isArray(r4) && r4.length >= 8) {
      const recs = []; for (let k = 0; k + 7 < r4.length; k += 8) recs.push(r4.slice(k, k + 8));
      const ok = recs.filter(r => r[4] === P_RKT1);
      const pick = ok.find(r => r[0] === 0) || (ok.length ? ok[0] : null);
      if (pick) return [[pick[5] >>> 0, pick[6] >>> 0, pick[7] >>> 0], null];
      return [null, 'resource key type 4 without a type-1 record'];
    }
    if (propValue(src, inst, P_RKT0) !== null) return [null, 'resource key type 0 (not read)'];
    return [null, 'no model key'];
  }
  const propOwner = (sources, inst) => sources.find(s => s.props.has(inst)) || null;   // props.owner
  function resolveProp(sources, pid, row) {   // props.resolve -> [src, inst, null] or [null, null, why]
    const o = propOwner(sources, pid);
    if (o) return propActive(o, pid) ? [o, pid, null] : [null, null, 'season'];
    const cand = new Set();                 // task sc4baseprops: a family's members pooled over all sources
    for (const s of sources) for (const m of familyMembers(s, pid)) cand.add(m);
    if (!cand.size) return [null, null, 'missing'];
    const live = [];
    for (const m of [...cand].sort((a, b) => a - b)) { const s = propOwner(sources, m); if (familyMembers(s, pid).includes(m) && propActive(s, m)) live.push([s, m]); }
    if (!live.length) return [null, null, 'season'];
    const [s, m] = live[row % live.length];
    return [s, m, null];
  }
  const viewKeys = (m, zoom = 4) => [0, 1, 2, 3].map(r => [m[0], m[1], (m[2] + (zoom << 8) + (r << 4)) >>> 0]);
  function chooseLot(b, lots) {             // props.choose_lot
    let best = null;
    b.lots.forEach((bl, k) => {
      const lot = lots.find(l => l.name === bl.name && l.size[0] === bl.size[0] && l.size[1] === bl.size[1]);
      if (!lot) return;
      const row = lot.objects.find(o => o.type === 0);
      if (!row) return;
      const key = [lot.size[0] * lot.size[1], k];
      if (!best || key[0] < best[0][0] || (key[0] === best[0][0] && key[1] < best[0][1])) best = [key, lot, row];
    });
    return best ? [best[1], best[2]] : null;
  }
  function windowAxis(L0, L1, h0, h1, S, front) {
    if (L1 - L0 <= S) { const c = (L0 + L1) / 2.0; return [c - S / 2.0, c + S / 2.0]; }
    if (front) { const w1 = Math.min(L1, h0 + S); return [w1 - S, w1]; }
    const c = (h0 + h1) / 2.0;
    let w0 = c - S / 2.0; w0 = Math.max(L0, Math.min(w0, L1 - S));
    return [w0, w0 + S];
  }
  function propPlan(b, lots, sources, box, n) {   // props.plan
    const got = chooseLot(b, lots);
    if (!got) return null;
    const [lot, hrow] = got, kb = hrow.rot & 3;
    const W = lot.size[0] * CELL_M, Dp = lot.size[1] * CELL_M;
    const cs = [[0.0, 0.0], [W, Dp]].map(([cx, cz]) => turn(cx - hrow.x, cz - hrow.z, -(kb - 2)));
    const L = [Math.min(cs[0][0], cs[1][0]), Math.max(cs[0][0], cs[1][0]), Math.min(cs[0][1], cs[1][1]), Math.max(cs[0][1], cs[1][1])];
    const S = n * CELL_M;
    const wx = windowAxis(L[0], L[1], box[0], box[1], S, false), wz = windowAxis(L[2], L[3], box[2], box[3], S, true);
    const win = [wx[0], wx[1], wz[0], wz[1]], rows = [];
    lot.objects.forEach((o, k) => {
      if (o.type !== 1 || !o.ids.length) return;
      const pid = o.ids[0] >>> 0;
      const [s, inst, why] = resolveProp(sources, pid, k);
      const [x, z] = turn(o.x - hrow.x, o.z - hrow.z, -(kb - 2));
      const r = { row: k, id: pid, inst, name: null, src: s, msrc: null, model: null, x, z, q: pyMod((o.rot & 3) - kb, 4), state: why || 'ok' };
      if (s) {
        const nm = propValue(s, inst, P_NAME);
        r.name = nm || hexU(inst, 8);
        const [m, mwhy] = modelOf(s, inst);
        if (!m) r.state = mwhy;
        else {                              // task sc4baseprops: the model from the first source holding its 4 views, the prop's own first
          r.model = m;
          const vk = viewKeys(m);
          r.msrc = [s].concat(sources.filter(x => x !== s)).find(s2 => vk.every(k2 => s2.has(...k2))) || null;
          if (!r.msrc) r.state = 'model not in the packs';
        }
      }
      if (r.state === 'ok' && !(win[0] <= x && x <= win[1] && win[2] <= z && z <= win[3])) r.state = 'outside';
      rows.push(r);
    });
    return { lot, house: hrow, kb, window: win, lot_box: L, rows };
  }
  function propViews(src, model, label) {   // props.prop_views
    const [, g] = model, out = [];
    viewKeys(model).forEach((key, r) => {
      if (!src.has(...key)) throw new Sc4Error(label + ': S3D ' + tgiHex(key) + ' not found');
      const meshes = [];
      for (const m of readS3D(src.read(...key))) {
        if (!m.mat.tex.length || !m.tris.length) continue;
        const fk = texKey(src, g, m.mat.tex[0].id >>> 0);   // task sc4civ: SC4's own props keep theirs in 0x1ABE787D
        if (!src.has(...fk)) throw new Sc4Error(label + ': texture ' + hexU(fk[2], 8) + ' not found');
        meshes.push([m.P, m.UV, m.tris, fk]);
      }
      if (!meshes.length) throw new Sc4Error(label + ' view ' + r + ': no textured mesh');
      let fill = null;
      if (meshes.length === 1 && meshes[0][0].length === 7) {
        const [P, UV, , fk] = meshes[0];
        const bm = readFshFirst(src.read(...fk));
        const [A, , d] = fitCamera(P, UV, bm.w, bm.h);
        fill = hiddenFaces({ r, P_view: P, A, tex_size: [bm.w, bm.h], cam: { forward_view: d } });
      }
      out.push({ r, meshes: meshes.map(([P, UV, tris, fk]) => [P.map(p => toModel1(p, r)), UV, tris, fk]), fill, fill_key: meshes[0][3],
        az: pyMod(22.5 + 90.0 * r + 180.0, 360.0) - 180.0 });
    });
    return out;
  }
  const rad = x => x * (Math.PI / 180.0);
  function azTurned(az, q) { const [x, z] = turn(Math.sin(rad(az)), Math.cos(rad(az)), q); return degrees(Math.atan2(x, z)); }
  function matchPropView(pv, q, slot) {
    const a = SC3_SLOT_AZ[slot];
    let best = null, bk = Infinity;
    for (const v of pv) { const k = Math.abs(pyMod(azTurned(v.az, q) - a + 180, 360) - 180); if (best === null || k < bk) { best = v; bk = k; } }
    return best;
  }
  function nudge(lo, hi, w0, w1) {
    if (hi - lo > w1 - w0) return null;
    let d = 0.0;
    if (lo < w0) d = w0 - lo; else if (hi > w1) d = w1 - hi;
    return Math.abs(d) <= NUDGE_M ? d : null;
  }
  function placedMeshes(pl, cache, fill = true) {   // props.placed_meshes
    const slots = [[], [], [], []], [x0w, x1w, z0w, z1w] = pl.window;
    for (const r of pl.rows) {
      if (r.state !== 'ok') continue;
      if (!r.msrc.cid) r.msrc.cid = ++srcSerial;
      const ck = r.model.join(':') + '@' + r.msrc.cid;
      if (!cache.has(ck)) {
        try { cache.set(ck, propViews(r.msrc, r.model, r.name)); }
        catch (e) { if (!(e instanceof Sc4Error) && !(e instanceof RangeError)) throw e; cache.set(ck, String(e.message || e)); }
      }
      const pv = cache.get(ck);
      if (typeof pv === 'string') { r.state = 'unreadable'; r.why = pv; continue; }
      let xmin = Infinity, xmax = -Infinity, zmin = Infinity, zmax = -Infinity;
      for (const v of pv) for (const m of v.meshes) for (const p of m[0]) {
        const [x, z] = turn(p[0], p[2], r.q), X = x + r.x, Z = z + r.z;
        if (X < xmin) xmin = X; if (X > xmax) xmax = X; if (Z < zmin) zmin = Z; if (Z > zmax) zmax = Z;
      }
      const dx = nudge(xmin, xmax, x0w, x1w), dz = nudge(zmin, zmax, z0w, z1w);
      if (dx === null || dz === null) { r.state = 'outside'; continue; }
      if (dx || dz) r.nudge_m = [dx, dz];
      const ox = r.x + dx, oz = r.z + dz;
      for (let slot = 0; slot < 4; slot++) {
        const v = matchPropView(pv, r.q, slot);
        const parts = v.meshes.slice();
        if (fill && v.fill) parts.push([v.fill[0], v.fill[1], v.fill[2], v.fill_key]);
        for (const [P, UV, tris, fk] of parts) {
          const Pt = P.map(p => { const [x, z] = turn(p[0], p[2], r.q); return [x + ox, p[1], z + oz]; });
          slots[slot].push([Pt, UV, tris, fk, r.msrc]);
        }
      }
    }
    return slots;
  }
  let srcSerial = 0;
  const countBy = (xs) => { const m = new Map(); for (const x of xs) m.set(x, (m.get(x) || 0) + 1); return m; };
  const cmpStr = (a, b) => a < b ? -1 : a > b ? 1 : 0;
  function propSummary(pl) {                // props.summary, with 'on' first (sc4conv.write_props)
    const st = countBy(pl.rows.map(r => r.state));
    const miss = countBy(pl.rows.filter(r => r.state === 'missing').map(r => r.id));
    const used = countBy(pl.rows.filter(r => r.state === 'ok').map(r => r.name));
    let unread = 0; for (const [k, v] of st) if (!['ok', 'outside', 'season', 'missing'].includes(k)) unread += v;
    return { lot: pl.lot.name, rows: pl.rows.length, placed: st.get('ok') || 0,
      nudged: pl.rows.filter(r => r.state === 'ok' && r.nudge_m).length,
      outside_sc3_lot: st.get('outside') || 0, other_season: st.get('season') || 0, missing: st.get('missing') || 0, unreadable: unread,
      window_m: pl.window.map(x => new PyFloat(pyRound(x, 2))),
      used: [...used.entries()].sort((a, b) => cmpStr(a[0], b[0])).map(([k, v]) => [k, v]),
      missing_ids: [...miss.entries()].map(([k, v]) => [hexU(k, 8), v]).sort((a, b) => cmpStr(a[0], b[0])) };
  }
  const houseBox = vs => { const P = vs[0].P; let a = Infinity, b = -Infinity, c = Infinity, d = -Infinity; for (const p of P) { if (p[0] < a) a = p[0]; if (p[0] > b) b = p[0]; if (p[2] < c) c = p[2]; if (p[2] > d) d = p[2]; } return [a, b, c, d]; };
  function writeProps(b, vs, stem, obj, mtl, files, pctx, fill, n = null) {   // sc4conv.write_props -> x_sc4.props or null
    const pl = propPlan(b, pctx.lots, pctx.sources, houseBox(vs), n === null ? lotFor(b) : n);
    if (!pl) return null;
    const slots = placedMeshes(pl, pctx.cache, fill);
    const s = propSummary(pl);
    const info = Object.assign({ on: s.placed > 0 && !pctx.off }, s);
    pctx.plans.push([b, pl]);
    if (!s.placed) return info;
    const pobj = [obj[0], 'mtllib ' + stem + '_props.mtl'].concat(obj.slice(2)), pmtl = mtl.slice(), seen = new Set();
    let vbase = obj.filter(l => l.startsWith('v ')).length, tbase = obj.filter(l => l.startsWith('vt ')).length;
    for (let slot = 0; slot < 4; slot++) {
      pobj.push('g sc3slot' + slot);
      let cur = null;
      for (const [P, UV, tris, fk, src] of slots[slot]) {
        const mname = 'sc4p_' + hexU(fk[1], 8) + '_' + hexU(fk[2], 8);
        if (!seen.has(mname)) {
          seen.add(mname);
          const png = 'sc4prop_' + hexU(fk[1], 8) + '_' + hexU(fk[2], 8) + '.png';
          if (!files.has(png)) { const bm = readFshFirst(src.read(...fk)); files.set(png, { w: bm.w, h: bm.h, d: bm.image }); }
          pmtl.push('newmtl ' + mname, 'Kd 1 1 1', 'map_Kd ' + png, '');
        }
        if (mname !== cur) { pobj.push('usemtl ' + mname); cur = mname; }
        for (const p of P) pobj.push('v ' + pyFixed(p[0], 5) + ' ' + pyFixed(p[1], 5) + ' ' + pyFixed(p[2], 5));
        for (const uv of UV) pobj.push('vt ' + pyFixed(uv[0], 6) + ' ' + pyFixed(1.0 - uv[1], 6));
        for (const t of tris) pobj.push('f ' + t.map(i => (vbase + 1 + i) + '/' + (tbase + 1 + i)).join(' '));
        vbase += P.length; tbase += UV.length;
      }
    }
    const [x0, x1, z0, z1] = pl.window;
    let y0 = Infinity; for (const v of vs) for (const p of v.P) if (p[1] < y0) y0 = p[1];
    const V3 = (x, y, z) => 'v ' + pyFixed(x, 5) + ' ' + pyFixed(y, 5) + ' ' + pyFixed(z, 5);
    pobj.push('g sc4lot', 'usemtl sc4lot', V3(x0, y0, z0), V3(x1, y0, z1), V3(x1, y0, z1), 'f ' + (vbase + 1) + ' ' + (vbase + 2) + ' ' + (vbase + 3));
    pmtl.push('newmtl sc4lot', 'Kd 1 1 1', '');
    files.set(stem + '_props.obj', textBytes(pobj.join('\n') + '\n'));
    files.set(stem + '_props.mtl', textBytes(pmtl.join('\n')));
    return info;
  }
  function propsNotes(plans, sc4 = false) {   // sc4conv.props_notes
    if (!plans.length) return [];
    const st = new Map([['ok', 0], ['outside', 0], ['season', 0], ['missing', 0], ['unreadable', 0]]), miss = new Map();
    let tot = 0;
    for (const [, pl] of plans) for (const r of pl.rows) {
      const k = ['ok', 'outside', 'season', 'missing'].includes(r.state) ? r.state : 'unreadable';
      st.set(k, st.get(k) + 1); tot++;
      if (r.state === 'missing') miss.set(r.id, (miss.get(r.id) || 0) + 1);
    }
    const nb = plans.filter(([, pl]) => pl.rows.some(r => r.state === 'ok')).length;
    const lines = ['Lot props: ' + st.get('ok') + ' of ' + tot + ' prop rows placed (' + nw(nb, 'building', 'buildings') + '), ' + st.get('outside') +
      ' outside the SC3 lot, ' + st.get('season') + ' of another season, ' + st.get('missing') + ' in no pack given, ' + st.get('unreadable') + ' without a readable model'];
    if (miss.size) lines.push("Props not found (" + miss.size + " ids, rows in brackets; " + (sc4 ? 'a dependency not given' : "SimCity 4's own props or a dependency not given") + '): ' +
      [...miss.entries()].sort((a, b) => b[1] - a[1] || a[0] - b[0]).map(([k, v]) => hexU(k, 8) + ' (' + v + ')').join(', '));
    return lines;
  }
  async function propsContext(idx, bs, lots, deps, fill, off, log, services = null, sc4 = null) {   // sc4conv.props_context
    const sources = [ownSource(idx)];
    for (const d of deps) sources.push(await depsIndex(d, log));
    const withSc4 = !!(sc4 && sc4.length && !idx.install);   // task sc4baseprops: the player's SC4 install, the last source
    if (withSc4) sources.push(await installSource(sc4, log));
    const ctx = { lots, sources, cache: new Map(), plans: [], off: !!off, services: services || new Map(), sc4: withSc4 };
    const want = new Map(), own = [];
    for (const b of bs) {
      let vs; try { vs = loadViews(idx, b, ZOOM5); } catch (e) { if (e instanceof Sc4Error || e instanceof RangeError) continue; throw e; }
      const sv = ctx.services.get(tgiKey(...b.tgi));
      const pl = propPlan(b, lots, sources, houseBox(vs), sv ? sv.lot : lotFor(b));
      if (!pl) continue;
      for (const r of pl.rows) if (r.state === 'ok' && !r.msrc.own) {   // task sc4baseprops: from the source holding the model
        if (!want.has(r.msrc)) want.set(r.msrc, new Map());
        for (const k of viewKeys(r.model)) want.get(r.msrc).set(tgiKey(...k), k);
      } else if (r.state === 'ok' && idx.install) own.push(r.model);   // task sc4civ: SC4's own props, by slices
    }
    for (const [s, keys] of want) await s.fetch([...keys.values()], log);
    if (own.length) await fetchModels(idx, own);
    return ctx;
  }

  // ---- task sc4baseprops: the player's SimCity 4 install as a prop source for a download (sc4conv.py --sc4): its
  //      exemplars and cohorts read by slices once per page session, the S3D and FSH of the props placed when fetched
  const INSTALL_CACHE = new WeakMap();      // the install's inputs -> source
  async function installSource(inputs, log = () => {}) {
    if (INSTALL_CACHE.has(inputs)) return INSTALL_CACHE.get(inputs);
    const list = inputs.slice(); list.install = true;
    const iidx = await buildIndex(list, log);
    await fetchTypes(iidx, [T_EXEMPLAR, T_COHORT]);
    const src = ownSource(iidx);
    src.own = false; src.install = true;
    src.fetch = async keys => fetchModels(iidx, keys.map(k => k.concat(['one'])));
    log('SimCity 4 install as a prop source: ' + src.props.size + ' prop exemplars, ' + src.cohorts.size + ' cohorts');
    INSTALL_CACHE.set(inputs, src);
    return src;
  }

  // ---- dependency packs by streaming (deps.DepsIndex). input: { path, size, mtime, slice(a, b) -> Promise<Uint8Array>,
  //      stream(a, b) -> ReadableStream<Uint8Array> } (a File: Blob.slice; node: fs ranges)
  class ByteStream {                        // deps._Stream: take / skip over a ReadableStream of chunks
    constructor(rs) { this.r = rs.getReader(); this.q = []; this.have = 0; this.done = false; }
    async fill(n) { while (this.have < n && !this.done) { const { value, done } = await this.r.read(); if (done) { this.done = true; break; } if (value && value.length) { this.q.push(value); this.have += value.length; } } }
    async take(n) {
      await this.fill(n);
      const k = Math.min(n, this.have), out = new Uint8Array(k);
      let o = 0;
      while (o < k) { const c = this.q[0], m = Math.min(c.length, k - o); out.set(c.subarray(0, m), o); o += m; if (m === c.length) this.q.shift(); else this.q[0] = c.subarray(m); }
      this.have -= k; return out;
    }
    async skip(n) {
      while (n > 0) {
        if (!this.have) { await this.fill(1); if (!this.have) return; }
        const c = this.q[0], m = Math.min(c.length, n);
        if (m === c.length) this.q.shift(); else this.q[0] = c.subarray(m);
        this.have -= m; n -= m;
      }
    }
    cancel() { try { this.r.cancel(); } catch (e) { /* closed */ } }
  }
  const DAT_RE = /\.(dat|sc4desc|sc4lot|sc4model)$/i;
  async function zipDirOf(input) {          // the central directory of a big zip, read by slices
    const tail = Math.min(input.size, 65557);
    const t = await input.slice(input.size - tail, input.size);
    let eo = -1;
    for (let p = t.length - 22; p >= 0; p--) if (t[p] === 0x50 && t[p + 1] === 0x4B && t[p + 2] === 5 && t[p + 3] === 6) { eo = p; break; }
    if (eo < 0) throw new Sc4Error(input.path + ': not a .zip file');
    const r = new Rd(t), n = r.u16(eo + 10), cdSize = r.u32(eo + 12), cdOff = r.u32(eo + 16);
    if (cdOff === 0xFFFFFFFF || n === 0xFFFF) throw new Sc4Error(input.path + ': ZIP64 archives are not read');
    const cd = await input.slice(cdOff, cdOff + cdSize), c = new Rd(cd), out = [];
    let p = 0;
    for (let k = 0; k < n; k++) {
      if (c.u32(p) !== 0x02014b50) throw new Sc4Error(input.path + ': broken .zip directory');
      const flags = c.u16(p + 8), method = c.u16(p + 10), csize = c.u32(p + 20), usize = c.u32(p + 24);
      const nl = c.u16(p + 28), xl = c.u16(p + 30), cl = c.u16(p + 32), lho = c.u32(p + 42);
      const raw = cd.subarray(p + 46, p + 46 + nl);
      out.push({ name: flags & 0x800 ? new TextDecoder('utf-8').decode(raw) : latin1(raw), method, csize, usize, lho, flags });
      p += 46 + nl + xl + cl;
    }
    return out;
  }
  async function memberStart(input, e) { const h = await input.slice(e.lho, e.lho + 30), r = new Rd(h); if (r.u32(0) !== 0x04034b50) throw new Sc4Error(e.name + ': broken .zip entry'); return e.lho + 30 + r.u16(26) + r.u16(28); }
  async function inflateMember(method, raw, name) { if (method === 0) return raw; if (method === 8) return inflateRaw(raw); throw new Sc4Error(name + ': .zip method ' + method + ' is not read'); }
  // deps.walk: every DBPF file of the pack in load order -> cb(path, bytes or null); want(path) false: not inflated
  async function walkDeps(input, cb, want = null) {
    const ents = await zipDirOf(input);
    const names = ents.map(e => e.name).sort(cmpStr), byName = new Map(ents.map(e => [e.name, e]));
    for (const n of names) {
      if (!/\.jar$/i.test(n)) continue;
      const e = byName.get(n), start = await memberStart(input, e);
      let rs = input.stream(start, start + e.csize);
      if (e.method === 8) rs = rs.pipeThrough(new DecompressionStream('deflate-raw'));
      else if (e.method !== 0) throw new Sc4Error(n + ': .zip method ' + e.method + ' is not read');
      const s = new ByteStream(rs), label = input.path + '!' + n;
      for (;;) {
        const h = await s.take(30);
        if (h.length < 30 || !(h[0] === 0x50 && h[1] === 0x4B && h[2] === 3 && h[3] === 4)) break;
        const r = new Rd(h), flag = r.u16(6), meth = r.u16(8), cs = r.u32(18), us = r.u32(22), nl = r.u16(26), el = r.u16(28);
        const nb = await s.take(nl), name = flag & 0x800 ? new TextDecoder('utf-8').decode(nb) : cp437(nb);
        await s.skip(el);
        if (flag & 8) throw new Sc4Error(label + ': member ' + name + ' uses a data descriptor, the streaming reader needs sizes in the local header');
        const path = label + '!' + name;
        if (!DAT_RE.test(name)) { await s.skip(cs); continue; }
        if (want && !want(path)) { await s.skip(cs); await cb(path, null); continue; }
        const data = await inflateMember(meth, await s.take(cs), name);
        if (data.length !== us) throw new Sc4Error(label + ': member ' + name + ' inflated to ' + data.length + ' bytes, header says ' + us);
        await cb(path, data);
      }
      s.cancel();
    }
    if (names.some(n => DAT_RE.test(n))) {
      for (const n of names) {
        if (!DAT_RE.test(n)) continue;
        const path = input.path + '!' + n;
        if (want && !want(path)) { await cb(path, null); continue; }
        const e = byName.get(n), start = await memberStart(input, e);
        await cb(path, await inflateMember(e.method, await input.slice(start, start + e.csize), n));
      }
    }
  }
  const CP437_HI = 'ÇüéâäàåçêëèïîìÄÅÉæÆôöòûùÿÖÜ¢£¥₧ƒáíóúñÑªº¿⌐¬½¼¡«»░▒▓│┤╡╢╖╕╣║╗╝╜╛┐└┴┬├─┼╞╟╚╔╩╦╠═╬╧╨╤╥╙╘╒╓╫╪┘┌█▄▌▐▀αßΓπΣσµτΦΘΩδ∞φε∩≡±≥≤⌠⌡÷≈°∙·√ⁿ²■ ';
  const cp437 = b => { let s = ''; for (const c of b) s += c < 128 ? String.fromCharCode(c) : CP437_HI[c - 128]; return s; };
  const DEPS_CACHE = new Map();             // pack (path, size, mtime) -> index, for the page session (Python: on disk)
  async function depsIndex(input, log = () => {}) {
    const ck = input.path + '|' + input.size + '|' + (input.mtime || 0);
    if (DEPS_CACHE.has(ck)) { log('deps: index ' + input.path + ' (cached in this page)'); return DEPS_CACHE.get(ck); }
    const t0 = Date.now(), dats = [], props = new Map(), cohorts = new Map();
    const mt = [[], [], [], []];            // map rows: type (0 S3D, 1 FSH), group, instance, dat
    await walkDeps(input, async (path, data) => {
      const di = dats.length; dats.push(path);
      let f; try { f = readDbpf(path, data); } catch (e) { if (e instanceof Sc4Error || e instanceof RangeError) { log('  deps: skip ' + path + ': ' + (e.message || e)); return; } throw e; }
      for (const e of f.entries) {
        if (e.type === T_S3D || e.type === T_FSH) { mt[0].push(e.type === T_S3D ? 0 : 1); mt[1].push(e.group); mt[2].push(e.instance); mt[3].push(di); }
        else if (e.type === T_EXEMPLAR || e.type === T_COHORT) {
          let ex; try { ex = parseExemplar(f.read(e)); } catch (x) { if (x instanceof Sc4Error || x instanceof RangeError) continue; throw x; }
          const rec = exRec(ex, e.group); rec.dat = di;
          if (e.type === T_COHORT) cohorts.set(tgiKey(e.type, e.group, e.instance), rec);
          else if (propType(ex) === 0x1E) props.set(e.instance, rec);   // a later file wins (Python: the dict keeps the first position)
        }
      }
      if (dats.length % 16 === 0) log('deps: ' + dats.length + ' DBPF files read');
      await new Promise(res => setTimeout(res, 0));
    });
    // lookup: per type, rows sorted by (group, instance, row) -> binary search, the last equal row wins
    const N = mt[0].length, T = Uint8Array.from(mt[0]), G = Uint32Array.from(mt[1]), I = Uint32Array.from(mt[2]), Dd = Uint32Array.from(mt[3]);
    const ord = Uint32Array.from({ length: N }, (_, k) => k).sort((a, b) => T[a] - T[b] || G[a] - G[b] || I[a] - I[b] || a - b);
    const find = (t, g, i) => {
      const tt = t === T_S3D ? 0 : t === T_FSH ? 1 : -1;
      if (tt < 0) return -1;
      let lo = 0, hi = N;               // first row > key
      while (lo < hi) { const m = (lo + hi) >> 1, k = ord[m]; const c = T[k] - tt || G[k] - g || I[k] - i; if (c <= 0) lo = m + 1; else hi = m; }
      if (lo === 0) return -1;
      const k = ord[lo - 1];
      return T[k] === tt && G[k] === g && I[k] === i ? Dd[k] : -1;
    };
    const entries = new Map();
    const src = { own: false, path: input.path, dats, props, cohorts, fam: null, entries,
      has: (t, g, i) => find(t >>> 0, g >>> 0, i >>> 0) >= 0,
      read(t, g, i) { const x = entries.get(tgiKey(t >>> 0, g >>> 0, i >>> 0)); if (!x) throw new Sc4Error(hexU(t, 8) + '-' + hexU(g, 8) + '-' + hexU(i, 8) + ' not fetched'); return x; },
      async fetch(keys, flog = log) {     // deps.DepsIndex.fetch: the S3D and every FSH they name, rounds as in Python
        let want = keys.filter(k => src.has(...k) && !entries.has(tgiKey(...k))), rounds = 0, wrote = 0;
        while (want.length && rounds < 3) {
          rounds++;
          const t1 = Date.now(), dset = new Set(want.map(k => find(...k))), names = new Map([...dset].map(d => [dats[d], d]));
          const more = new Map();
          await walkDeps(input, async (path, data) => {
            if (!data) return;
            const f = readDbpf(path, data), di = names.get(path), byTgi = new Map(f.entries.map(e => [tgiKey(e.type, e.group, e.instance), e]));
            for (const t of want) {
              if (find(...t) !== di) continue;
              const e = byTgi.get(tgiKey(...t)); if (!e) continue;
              const b = f.read(e); entries.set(tgiKey(...t), b); wrote++;
              if (t[0] !== T_S3D) continue;
              let ms = []; try { ms = readS3D(b); } catch (x) { if (!(x instanceof Sc4Error) && !(x instanceof RangeError)) throw x; }
              for (const m of ms) for (const tx of m.mat.tex) {
                const k = [T_FSH, t[1], tx.id >>> 0], kk = tgiKey(...k);
                if (!src.has(...k) || entries.has(kk)) continue;
                const e2 = find(...k) === di ? byTgi.get(kk) : null;
                if (e2) { entries.set(kk, f.read(e2)); wrote++; } else more.set(kk, k);
              }
            }
          }, p => names.has(p));
          flog('deps: fetch round ' + rounds + ': ' + dset.size + ' DBPF files read, ' + wrote + ' entries cached, ' + Math.round((Date.now() - t1) / 1000) + ' s');
          want = [...more.values()].filter(k => !entries.has(tgiKey(...k)));
        }
        return wrote;
      } };
    log('deps: indexed ' + dats.length + ' DBPF files, ' + props.size + ' prop exemplars, ' + cohorts.size + ' cohorts, ' + N + ' S3D / FSH entries in ' + Math.round((Date.now() - t0) / 1000) + ' s');
    DEPS_CACHE.set(ck, src);
    return src;
  }

  // ================================================================================================ lot-only packs (task sc4pass2)
  // sc4conv.pack_notes and its helpers, the same steps and text: buildings without a model in the download, blank
  // placeholder models, lots naming a building the download lacks, the readme's dependency list, and the ploppable /
  // landmark lots that show a converted model as a lot prop.
  function others(idx) {                    // catalog.others -> [buildings without a model key, props {instance -> prop}]
    const blds = [], props = new Map();
    for (const k of idx.ofType(T_EXEMPLAR)) {
      let ex;
      try { ex = idx.full(k); } catch (e) { if (!(e instanceof Sc4Error)) throw e; continue; }
      const t = sc(pv(ex, 0x10)), rk = pv(ex, 0x27812821);
      const hasModel = Array.isArray(rk) && rk.length >= 3 && rk[0] === T_S3D;
      if (t === 0x1E && hasModel) props.set(k[2], { tgi: k, name: pv(ex, 0x20, ''), model: rk.slice(0, 3) });
      else if (t === 2 && !hasModel) {
        const nk = pv(ex, 0x8A416A99);
        let title = null;
        if (Array.isArray(nk) && nk.length === 3 && idx.has(...nk)) title = pyStrip(ltext(idx.read(...nk)));
        blds.push({ tgi: k, name: pv(ex, 0x20, ''), title, landmark: ex.props.has(0x2781284F), jobs: ex.props.has(0x27812834), groups: groupsOf(ex) });
      }
    }
    return [blds, props];
  }
  const README_RE = /readme/i, isReadme = n => README_RE.test(n) && /\.(htm|html|txt)$/i.test(n);
  const WS_RE = /[ \t\r\n\f\v]+/g;
  const ENTITIES = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ' };
  const stripSp = s => s.replace(/^ +| +$/g, '');
  function unentity(s) {
    return s.replace(/&(#[0-9]+|#[xX][0-9a-fA-F]+|[A-Za-z]+);/g, (m, k) => {
      if (k[0] === '#') {
        const c = k[1] === 'x' || k[1] === 'X' ? parseInt(k.slice(2), 16) : parseInt(k.slice(1), 10);
        return c > 0 && c < 0x110000 ? String.fromCodePoint(c) : m;
      }
      const v = ENTITIES[k.toLowerCase()];
      return v === undefined ? m : v;
    });
  }
  const flat = s => stripSp(unentity(s.replace(/<[^>]*>/g, ' ')).replace(WS_RE, ' '));
  function readmeDeps(text) {               // sc4conv.readme_deps -> [[name, url]]
    const low = text.toLowerCase(), i = low.indexOf('dependenc');
    if (i < 0) return [];
    const u = low.indexOf('<ul', i), out = [];
    if (u >= 0) {
      const e = low.indexOf('</ul>', u);
      const seg = text.slice(u, e >= 0 ? e : text.length);
      for (const m of seg.matchAll(/<li\b[^>]*>([\s\S]*?)<\/li>/gi)) {
        const it = m[1], h = /href\s*=\s*"([^"]*)"/i.exec(it), name = flat(it);
        if (name) out.push([name, h ? unentity(h[1]) : '']);
      }
      return out;
    }
    for (const ln of pySplitlines(text.slice(i)).slice(1)) if (ln.includes('http')) out.push([stripSp(ln.replace(WS_RE, ' ')), '']);
    return out;
  }
  const nw = (n, one, many) => n + ' ' + (n === 1 ? one : many);
  function labelOf(b) {
    const lines = pySplitlines(b.title || b.name || '');
    return lines.length ? pyStrip(lines[0]).replace(/,+$/, '') : b.name;
  }
  function packNotes(idx, bs, states, lots, deps) {   // sc4conv.pack_notes -> [lines, missing, versions Map]
    const lines = [], missing = [];
    const st = b => states.get(b)[0];
    const conv = bs.filter(b => st(b) === 'ok'), gone = bs.filter(b => st(b) === 'missing'), blank = bs.filter(b => st(b) === 'blank');
    for (const b of gone.concat(blank)) missing.push({ name: labelOf(b), exemplar: b.name, reason: st(b), lots: b.lots.map(l => l.name) });
    const known = new Set();
    for (const b of bs) { known.add(b.tgi[2]); for (const f of b.families) known.add(f); }
    const [oblds, props] = others(idx);
    for (const ob of oblds) known.add(ob.tgi[2]);
    const unres = [];
    for (const lot of lots) for (const o of lot.objects)
      if (o.type === 0 && o.ids.length && !o.ids.some(i => known.has(i))) unres.push(lot.name + ' (building ' + o.ids.map(i => hexU(i, 8)).join(', ') + ')');
    const versions = new Map(), byModel = new Map();
    for (const b of conv) { const k = b.model.join(','); if (!byModel.has(k)) byModel.set(k, b); }
    for (const lot of lots) {
      let bld = null;
      for (const o of lot.objects) if (o.type === 0) bld = oblds.find(ob => o.ids.includes(ob.tgi[2])) || null;
      if (!bld) continue;
      for (const o of lot.objects) {
        if (o.type !== 1) continue;
        for (const i of o.ids) {
          const pr = props.get(i), b = pr ? byModel.get(pr.model.join(',')) : undefined;
          if (b) {
            if (!versions.has(b.tgi)) versions.set(b.tgi, []);
            versions.get(b.tgi).push({ lot: lot.name, kind: bld.landmark ? 'landmark' : 'ploppable', building: labelOf(bld), jobs: !!bld.jobs,
              exemplar: bld.name, building_tgi: tgiHex(bld.tgi) });
          }
        }
      }
    }
    if (!conv.length) lines.push('No building converted: this download holds no building models, only ' + nw(lots.length, 'lot', 'lots') + ' and ' +
      nw(bs.length + oblds.length, 'building description', 'building descriptions'));
    if (gone.length) lines.push(gone.length + ' ' + (gone.length > 1 ? 'buildings need' : 'building needs') + ' their model from a separate download: ' + gone.map(labelOf).join(', '));
    if (deps.length) lines.push("The download's readme lists the models to get: " + deps.map(([n, u]) => u ? n + ' (' + u + ')' : n).join(', '));
    for (const b of blank) {
      const ln = b.lots.map(l => l.name);
      lines.push(ln.length + ' ' + (ln.length !== 1 ? 'lots' : 'lot') + ' use ' + labelOf(b) + ", a blank placeholder building: what shows in SimCity 4 is lot props (SimCity 4's" +
        ' own buildings or other downloads), not in this download: ' + (ln.join(', ') || 'no lot'));
    }
    if (unres.length) lines.push(unres.length + ' ' + (unres.length > 1 ? 'lots name' : 'lot names') + ' a building that is not in this download: ' + unres.join(', '));
    for (const b of conv) {
      const vs = versions.get(b.tgi);
      if (!(vs && vs.length)) continue;
      const n = lotFor(b);
      let tail;
      if (!LANDMARK_LOTS.includes(n)) tail = 'not converted: SC3 landmarks are 1x1 to 4x4 and this building needs ' + n + 'x' + n;
      else {
        const on = vs.filter(v => versionOn(vs, v, n)).map(v => v.lot), off = vs.filter(v => !versionOn(vs, v, n)).map(v => v.lot);
        tail = 'converted as ' + (vs.length > 1 ? 'SC3 landmarks' : 'an SC3 landmark') + ' for the landmark menu (kind landmark), ' + (on.join(', ') || 'none') + ' on';
        if (off.length) tail += ', ' + off.join(', ') + ' off (the same building again, and SC3 landmarks have no jobs)';
      }
      lines.push(labelOf(b) + ' also comes as ' + vs.map(v => 'the ' + v.kind + ' lot ' + v.lot + ' (building ' + v.building + ')').join(', ') + ': ' + tail);
    }
    return [lines, missing, versions];
  }

  // ================================================================================================ SC4 landmarks (task plop2)
  // sc4conv.landmark_entry and helpers: an SC4 landmark / ploppable lot of a converted building becomes an SC3 landmark
  // entry (kind landmark) whose OBJ is a byte copy of the building's own <stem>.obj.
  const LANDMARK_LOTS = [1, 2, 3, 4], LANDMARK_DESC = 'From SimCity 4';
  const LANDMARK_EDITABLE = EDITABLE.concat(['kind', 'description']);
  function versionOn(vs, v, n) {
    if (!LANDMARK_LOTS.includes(n)) return false;
    if (v.kind === 'landmark') return true;
    return !vs.some(x => x.kind === 'landmark') && v === vs[0];
  }
  function landmarkFile(b, v, vs) {
    const same = vs.filter(x => x.kind === v.kind), k = same.indexOf(v);
    return stemOf(b.name) + '_' + v.kind + (k === 0 ? '' : String(k + 1)) + '.obj';
  }
  function landmarkEntry(b, e, v, vs, style, keepDiag) {
    const n = lotFor(b), x = e.x_sc4, diag = !!x.diagonal;
    let notes = 'SC4 ' + v.kind + ' lot ' + v.lot + ' (building ' + v.building + ') as an SC3 landmark: the landmark menu, one per city, stats of a stock' +
      " landmark of the lot. The model is " + labelOf(b) + " without the SC4 lot's props.";
    if (!LANDMARK_LOTS.includes(n)) notes += ' Off: SC3 landmarks are 1x1 to 4x4, this building needs ' + n + 'x' + n + '.';
    else if (!versionOn(vs, v, n)) notes += ' Off by default: the same building as the landmark entry, and SC3 landmarks have no jobs.';
    return {
      file: landmarkFile(b, v, vs), name: v.building, kind: 'landmark', class: null, lot: [n, n], weight: 1, height_m: e.height_m,
      scale: new PyFloat(1.0), rotate_deg: 0, style: 'any', enabled: !!(versionOn(vs, v, n) && (keepDiag || !diag)),
      description: LANDMARK_DESC, notes,
      x_bldrender: { style },
      x_sc4: { exemplar: v.exemplar, design: v.building, colour: null, version: v.kind, sc4_lot: v.lot, model_of: b.name,
        building_tgi: v.building_tgi, model_key: x.model_key, size_m: x.size_m, diagonal: diag, foundation: x.foundation, views: x.views },
    };
  }
  async function depsOf(readmes) {          // every readme of the input, in walk order; a pair once
    const deps = [], seen = new Set();
    for (const r of readmes || []) {
      const text = new TextDecoder('utf-8').decode(await r.bytes());
      for (const d of readmeDeps(text)) { const k = d[0] + '\u0000' + d[1]; if (!seen.has(k)) { seen.add(k); deps.push(d); } }
    }
    return deps;
  }

  // convert(sources, opt) -> { files: Map rel -> Uint8Array (OBJ, MTL, PNG, models.json), models, report }
  //   opt.old: the previous models.json text (keeps the fields the player changed since the converter wrote them)
  //   opt.all, opt.style ('baked'), opt.fill (true), opt.log, opt.progress(i, n)
  //   opt.diagonal: treat buildings set at 45 degrees as any other (sc4conv.py --diagonal; default: off, with a note)
  async function convert(sources, opt = {}) {
    const log = opt.log || (() => {}), style = opt.style || 'baked', fill = opt.fill !== false;
    const idx = await buildIndex(sources, log);
    if (idx.install) await fetchTypes(idx, [T_EXEMPLAR, T_COHORT, T_LTEXT, T_LUA]);   // task sc4civ: by slices
    let [bs, lots] = buildings(idx);
    const report = [idx.files.length + ' DBPF files, ' + bs.length + ' buildings with S3D models, ' + lots.length + ' lots'];
    log(report[0]);
    const rw = luaRewards(idx), services = new Map();   // task sc4civ: SC4's civic buildings, parks, rewards, landmarks
    for (const b of bs) { const sv = serviceFor(b, rw); if (sv) services.set(tgiKey(...b.tgi), sv); }
    let states, notes, missing, versions;
    if (idx.install) {                      // from an install only those, by slices
      const oth = others(idx)[0], nAll = bs.length + oth.length;
      bs = bs.filter(b => services.has(tgiKey(...b.tgi)));
      [notes, missing, versions] = [installNotes(nAll, bs, oth), [], new Map()];
      await fetchModels(idx, buildingModels(idx, bs));
      states = new Map(bs.map(b => [b, modelState(idx, b)]));
    } else {
      // task sc4pass2: buildings without a model (lot-only packs), the readme's dependency list, ploppable versions
      states = new Map(bs.map(b => [b, modelState(idx, b)]));
      [notes, missing, versions] = packNotes(idx, bs, states, lots, await depsOf(sources.readmes));
    }
    for (const ln of notes) { log(ln); report.push(ln); }
    bs = bs.filter(b => states.get(b)[0] === 'ok');
    lastEmpty = !bs.length;
    if (!bs.length) {                       // sc4conv.py writes nothing and exits 3: no models.json, nothing to install
      lastDiag.clear();
      return { files: new Map(), models: [], text: pyDump({ sc3models: 1, models: [] }, 1), report, notes, missing, empty: true };
    }
    const old = new Map();
    if (opt.old) { const j = pyLoad(opt.old); for (const m of (j && j.models) || []) { old.set('F' + m.file, m); if (m.x_sc4 && m.x_sc4.exemplar) old.set('X' + m.x_sc4.exemplar, m); } }
    const keyOf = b => { const sv = services.get(tgiKey(...b.tgi)); return sv ? 'S' + sv.kind + '\u0000' + labelOf(b).toLowerCase()   // sc4conv.design_key
      : b.families.length ? 'F' + b.families.join(',') : 'D' + designOf(b.name)[0].toLowerCase(); };
    const fam = new Map();
    for (const b of bs) { const k = keyOf(b); if (!fam.has(k)) fam.set(k, []); fam.get(k).push(b); }
    const diag = new Map(bs.map(b => [b, foundationDiagonal(idx, b)]));
    const isDiag = opt.diagonal ? (() => false) : (b => !!(diag.get(b) && diag.get(b).diagonal));
    const pick = new Map(), chosen = pickColours([...fam.values()], isDiag);
    [...fam.keys()].forEach((d, i) => pick.set(d, chosen[i] ? chosen[i].tgi : null));
    for (const [d, ms] of fam) if (d[0] === 'S') { const c = ms.find(m => !isDiag(m)); pick.set(d, c ? c.tgi : null); }   // task sc4civ: the first is on
    const files = new Map(), models = [];
    const pctx = await propsContext(idx, bs, lots, sources.deps || opt.deps || [], fill, opt.noProps, log, services,
      sources.sc4 || opt.sc4 || null);      // task sc4props; task sc4baseprops: the SC4 install's own props
    for (let bi = 0; bi < bs.length; bi++) {
      const b = bs[bi];
      if (opt.progress) await opt.progress(bi, bs.length, b);
      const first = pick.get(keyOf(b)) === b.tgi;
      let e;
      try { e = writeBuilding(idx, b, files, opt.all || first, style, fill, diag.get(b), !!opt.diagonal, versions.get(b.tgi) || null, pctx); }
      catch (ex) { if (!(ex instanceof Sc4Error)) throw ex; const line = '  skip ' + b.name + ': ' + ex.message; log(line); report.push(line); continue; }
      const ed = editableOf(e), auto = {}; for (const k of ed) auto[k] = e[k];   // task sc4civ: + the service fields
      e.x_sc4.auto = auto;
      const pr = e.x_sc4.props || null;
      if (pr) auto.props_on = pr.on;
      const o = old.get('X' + e.x_sc4.exemplar) || old.get('F' + e.file);
      if (o) {
        const prev = (o.x_sc4 && o.x_sc4.auto) || {};
        for (const k of ed) if (k in o && k in prev && !pyEq(o[k], prev[k])) e[k] = o[k];
        const op = o.x_sc4 && o.x_sc4.props;   // task sc4props: the player's props switch
        if (pr && op && typeof op === 'object' && !Array.isArray(op) && 'props_on' in prev && !pyEq(op.on, prev.props_on)) {
          pr.on = !!op.on && pr.placed > 0;
          e.file = stemOf(b.name) + (pr.on ? '_props.obj' : '.obj');
        }
      }
      models.push(e);
      const vs = versions.get(b.tgi) || [];
      for (const v of vs) {                 // task plop2: the building's SC4 landmark / ploppable lots as SC3 landmarks
        const le = landmarkEntry(b, e, v, vs, style, !!opt.diagonal);
        files.set(le.file, files.get(stemOf(b.name) + '.obj'));
        const la = {}; for (const k of LANDMARK_EDITABLE) la[k] = le[k];
        le.x_sc4.auto = la;
        const o = old.get('X' + le.x_sc4.exemplar) || old.get('F' + le.file);
        if (o) {                            // the player's edits since the last run (description included)
          const prev = (o.x_sc4 && o.x_sc4.auto) || {};
          for (const k of LANDMARK_EDITABLE) if (k in o && k in prev && !pyEq(o[k], prev[k])) le[k] = o[k];
        }
        models.push(le);
      }
    }
    for (const ln of propsNotes(pctx.plans, pctx.sc4)) { log(ln); report.push(ln); }
    const top = { sc3models: 1, models };
    if (missing.length) top.x_sc4_missing = missing;  // task sc4pass2: the download's buildings without a model, by name
    const text = pyDump(top, 1);
    for (const [k, v] of files) if (!(v instanceof Uint8Array)) files.set(k, B.encodePNG(v));
    files.set('models.json', new TextEncoder().encode(text));
    const ne = models.filter(m => m.enabled).length, nd = models.filter(m => m.x_sc4.diagonal);
    report.push(models.length + ' models, ' + ne + ' enabled' + (nd.length ? ', ' + nd.length + ' set at 45 degrees in SC4 (' +
      new Set(nd.map(m => m.x_sc4.design)).size + ' designs) off by default since SC3 has no diagonal buildings' : ''));
    lastDiag.clear();
    for (const m of models) if (m.x_sc4.diagonal) lastDiag.set(m.file.toLowerCase(), m.x_sc4.foundation);
    log(report[report.length - 1]);
    return { files, models: JSON.parse(text).models, text, report, notes, missing, empty: false };
  }

  // ================================================================================================ page note (task sc4diag)
  // The importer's cards come from classifier.html (not edited by this task): this marks the card of every building
  // the last convert() found set at 45 degrees with a 'diagonal' badge and the reason as its tooltip.
  const lastDiag = new Map();               // OBJ file name (lower case) -> x_sc4.foundation
  let lastEmpty = false;                    // task sc4pass2: the last convert() found no building it can convert
  function markDiagonalCards(root) {
    if (!root || !root.querySelectorAll) return 0;
    let n = 0;
    for (const card of root.querySelectorAll('.card')) {
      const f = lastDiag.get(String(card.dataset.file || '').toLowerCase());
      if (!f || card.querySelector('.b.diag')) continue;
      const bd = card.querySelector('.badges');
      if (!bd) continue;
      const sp = card.ownerDocument.createElement('span');
      sp.className = 'b off diag'; sp.textContent = 'diagonal';
      sp.title = 'Set at 45 degrees on its SimCity 4 lot (its foundation ' + f.name + ' runs at 45 degrees for ' +
        pct(num(f.share_45)) + '% of its outline). SC3 has no diagonal buildings, so it is off by default.';
      bd.appendChild(sp); n++;
    }
    return n;
  }
  if (typeof document !== 'undefined' && typeof MutationObserver !== 'undefined') {
    const watch = () => {
      const grid = document.getElementById('grid');
      if (grid) new MutationObserver(() => { if (lastDiag.size) markDiagonalCards(grid); }).observe(grid, { childList: true });
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', watch); else watch();
  }

  // task sc4pass2: a lot-only download converts to nothing. classifier.html (not edited by this task) then shows an
  // empty grid, a note with the report and its usual tail about colours, and a status line about saving: this
  // rewrites the two so the page says plainly that nothing can be converted or installed (Install stays disabled,
  // the page enables it only with models).
  const EMPTY_TAIL = /, converted on this PC in [0-9.]+ s\. One colour of each straight design is on, the others are off: switch them in the panel\. /;
  function fixEmptyNote(doc) {
    if (!lastEmpty || !doc) return false;
    let changed = false;
    const note = doc.getElementById('sc4Note');
    if (note && EMPTY_TAIL.test(note.textContent)) {
      note.textContent = note.textContent.replace(EMPTY_TAIL, '. Nothing was converted and nothing can be installed from it. ');
      changed = true;
    }
    const st = doc.getElementById('status');
    const m = st && /^0 SimCity 4 buildings from (.*?) \(0 on\)\./.exec(st.textContent);
    if (m) { st.textContent = 'No building in ' + m[1] + ' can be converted: it holds no building models (see the note above the grid).'; changed = true; }
    return changed;
  }
  if (typeof document !== 'undefined' && typeof MutationObserver !== 'undefined') {
    const watch2 = () => {
      const obs = new MutationObserver(() => fixEmptyNote(document));
      for (const id of ['sc4Note', 'status']) { const el = document.getElementById(id); if (el) obs.observe(el, { childList: true, characterData: true, subtree: true }); }
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', watch2); else watch2();
  }

  // ================================================================================================ SC4 install (task sc4civ)
  // The player's own SimCity 4 install as a source (catalog.install_files): a folder holding SimCity_1.dat at its top is
  // read as the game's 7 data files only. The large ones (100-170 MB) are never read whole: their header, index and
  // directory by slices, then the entries the conversion reads, fetched in batches before each step that reads them
  // (fetchTypes: every exemplar, cohort, LText and Lua script; fetchModels: S3D views, then the FSH textures they name).
  // A read of an entry not fetched raises an Sc4Error (the building is skipped with a log line), never a wrong answer.
  const INSTALL_FILES = ['SimCity_1.dat', 'SimCity_2.dat', 'SimCity_3.dat', 'SimCity_4.dat', 'SimCity_5.dat', 'EP1.dat', 'SimCityLocale.DAT'];
  const INSTALL_OTHER = ['Intro.dat', 'Sound.dat'];   // task sc4baseprops: the game folder's other top-level DBPF files (Steam)
  const MAP_FROM = 16 << 20, T_LUA = 0xCA63E2A3;
  function installOf(tree) {                // catalog.install_files on the input tree -> [sources] or null
    const top = new Map([...tree.files.keys()].map(n => [n.toLowerCase(), n]));
    if (!top.has(INSTALL_FILES[0].toLowerCase())) return null;
    const out = [];
    for (const n of INSTALL_FILES) { const k = top.get(n.toLowerCase()); if (k !== undefined) out.push(Object.assign({ path: k }, tree.files.get(k))); }
    const loc = INSTALL_FILES[INSTALL_FILES.length - 1].toLowerCase();
    if (!top.has(loc)) for (const d of [...tree.dirs.keys()].sort()) {
      const t = tree.dirs.get(d), m = [...t.files.keys()].find(n => n.toLowerCase() === loc);
      if (m !== undefined) { out.push(Object.assign({ path: d + '/' + m }, t.files.get(m))); break; }
    }
    return out;
  }
  async function readDbpfLazy(path, src) {  // dbpf.DBPF over slices: the same checks, entries read when fetched
    const h = await src.slice(0, 96);
    if (!(h[0] === 0x44 && h[1] === 0x42 && h[2] === 0x50 && h[3] === 0x46)) throw new Sc4Error(path + ': not a DBPF file');
    const r = new Rd(h);
    const major = r.u32(4), minor = r.u32(8);
    const count = r.u32(0x24), ioff = r.u32(0x28), isize = r.u32(0x2C);
    const indexMinor = minor >= 1 ? r.u32(0x3C) : 0;
    const esz = indexMinor === 2 ? 24 : 20;
    if (count && isize !== count * esz) throw new Sc4Error(path + ': index size ' + isize + ' != ' + count + ' x ' + esz);
    const ix = count ? await src.slice(ioff, ioff + count * esz) : new Uint8Array(0), ri = new Rd(ix);
    const entries = [];
    for (let k = 0; k < count; k++) {
      const p = k * esz;
      const e = { type: ri.u32(p), group: ri.u32(p + 4), instance: ri.u32(p + 8), offset: ri.u32(p + esz - 8), size: ri.u32(p + esz - 4), usize: 0, packed: false };
      e.usize = e.size; entries.push(e);
    }
    const byTgi = new Map(); for (const e of entries) byTgi.set(tgiKey(e.type, e.group, e.instance), e);
    const dsz = indexMinor === 2 ? 20 : 16;
    for (const e of entries) {
      if (e.type !== T_DIR) continue;
      const raw = await src.slice(e.offset, e.offset + e.size), rr = new Rd(raw);
      for (let p = 0; p + dsz <= raw.length; p += dsz) {
        const x = byTgi.get(tgiKey(rr.u32(p), rr.u32(p + 4), rr.u32(p + 8)));
        if (x) { x.packed = true; x.usize = rr.u32(p + dsz - 4); }
      }
    }
    const got = new Map();                  // entry -> its raw bytes
    return { path, data: null, major, minor, indexMinor, entries, lazy: true,
      has: e => got.has(e),
      async fetch(es) {                     // nearby entries in one slice (gap <= 256 KB, slice <= 16 MB)
        const want = es.filter(e => !got.has(e)).sort((a, b) => a.offset - b.offset);
        for (let i = 0; i < want.length;) {
          let j = i + 1, end = want[i].offset + want[i].size;
          while (j < want.length && want[j].offset - end <= (256 << 10) && want[j].offset + want[j].size - want[i].offset <= MAP_FROM) { end = Math.max(end, want[j].offset + want[j].size); j++; }
          const buf = await src.slice(want[i].offset, end);
          for (let k = i; k < j; k++) got.set(want[k], buf.subarray(want[k].offset - want[i].offset, want[k].offset - want[i].offset + want[k].size));
          i = j;
        }
      },
      read(e) {
        const raw = got.get(e);
        if (!raw) throw new Sc4Error(path + ': entry ' + tgiHex([e.type, e.group, e.instance]) + ' was not fetched');
        return e.packed ? qfsDecompress(raw) : raw;
      } };
  }
  async function fetchKeys(idx, keys) {     // the lazy entries of these TGIs, per file
    const per = new Map();
    for (const k of keys) {
      const x = idx.tgi.get(tgiKey(k[0] >>> 0, k[1] >>> 0, k[2] >>> 0));
      if (!x || !x[0].lazy || x[0].has(x[1])) continue;
      if (!per.has(x[0])) per.set(x[0], []);
      per.get(x[0]).push(x[1]);
    }
    for (const [f, es] of per) await f.fetch(es);
  }
  async function fetchTypes(idx, types) {
    const per = new Map();
    for (const [f, e] of idx.tgi.values()) if (f.lazy && types.includes(e.type)) { if (!per.has(f)) per.set(f, []); per.get(f).push(e); }
    for (const [f, es] of per) await f.fetch(es);
  }
  async function fetchModels(idx, models, src = idx) {   // S3D views of the models (zoom 4), then their textures
    const keys = [];
    for (const m of models) for (const k of (m.length === 4 ? [m.slice(0, 3)] : viewKeys(m))) keys.push(k);
    await fetchKeys(idx, keys);
    const tex = [];
    for (const k of keys) {
      if (!idx.has(...k)) continue;
      let ms; try { ms = readS3D(idx.read(...k)); } catch (e) { if (e instanceof Sc4Error || e instanceof RangeError) continue; throw e; }
      for (const m of ms) for (const tx of m.mat.tex) tex.push(texKey(src, k[1], tx.id >>> 0));
    }
    await fetchKeys(idx, tex);
  }
  function buildingModels(idx, bs, zoom = 4) {   // the S3D keys load_views, model_state and foundation_diagonal read
    const out = [];
    for (const b of bs) {
      out.push(b.model);
      const inst = b.foundation;
      if (typeof inst !== 'number' || !Number.isInteger(inst)) continue;
      const k = [T_EXEMPLAR, FND_GROUP, inst >>> 0];
      if (!idx.has(...k)) continue;
      let ex; try { ex = parseExemplar(idx.read(...k)); } catch (e) { if (e instanceof Sc4Error || e instanceof RangeError) continue; throw e; }
      const rk = pv(ex, 0x27812821);
      if (Array.isArray(rk) && rk.length >= 3 && rk[0] === T_S3D) out.push([rk[0], rk[1], (rk[2] + (zoom << 8)) >>> 0, 'one']);
    }
    return out;
  }

  // ---- views.tex_key: SC4's own models (S3D group 0xBADB57F1) keep their textures in FSH group 0x1ABE787D
  const MAXIS_S3D_GROUP = 0xBADB57F1, MAXIS_FSH_GROUP = 0x1ABE787D;
  function texKey(src, g, tid) {
    if (g === MAXIS_S3D_GROUP && !src.has(T_FSH, g, tid) && src.has(T_FSH, MAXIS_FSH_GROUP, tid)) return [T_FSH, MAXIS_FSH_GROUP, tid];
    return [T_FSH, g, tid];
  }

  // ---- views.compose_atlas: a view whose meshes are pieces of one screen render packed into textures
  const TILE_FIT = 2.0, ATLAS_FIT = 2.0;
  function atlasCovered(q, tris, w, h) {    // views._covered -> Uint8Array(h * w)
    const out = new Uint8Array(w * h);
    for (const t of tris) {
      const a = q[t[0]], b = q[t[1]], c = q[t[2]];
      const ar = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
      if (ar === 0.0) continue;
      const sg = ar > 0 ? 1.0 : -1.0;
      const x0 = Math.max(0, Math.floor(Math.min(a[0], b[0], c[0]))), x1 = Math.min(w - 1, Math.ceil(Math.max(a[0], b[0], c[0])) - 1);
      const y0 = Math.max(0, Math.floor(Math.min(a[1], b[1], c[1]))), y1 = Math.min(h - 1, Math.ceil(Math.max(a[1], b[1], c[1])) - 1);
      if (x1 < x0 || y1 < y0) continue;
      const edges = [[a, b], [b, c], [c, a]];
      for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) {
        let ok = true;
        for (const [p_, r_] of edges) {
          const ex = r_[0] - p_[0], ey = r_[1] - p_[1];
          let inside = false;
          for (const [dx, dy] of [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [1.0, 1.0]]) {
            if (sg * (ex * ((y + dy) - p_[1]) - ey * ((x + dx) - p_[0])) >= 0.0) { inside = true; break; }
          }
          if (!inside) { ok = false; break; }
        }
        if (ok) out[y * w + x] = 1;
      }
    }
    return out;
  }
  function composeAtlas(idx, g, meshes, label) {
    const pieces = [];
    for (const m of meshes) {
      const tid = m.mat.tex[0].id, fk = texKey(idx, g, tid);
      if (!idx.has(...fk)) throw new Sc4Error(label + ': texture ' + hexU(tid, 8) + ' not found');
      const bm = readFshFirst(idx.read(...fk));
      pieces.push({ P: m.P, UV: m.UV, q: m.UV.map(uv => [uv[0] * bm.w, uv[1] * bm.h]), tris: m.tris, bm, tid });
    }
    let ref = 0;
    pieces.forEach((pc, i) => { if (pc.P.length > pieces[ref].P.length) ref = i; });
    const [A] = fitCamera(pieces[ref].P, pieces[ref].UV, pieces[ref].bm.w, pieces[ref].bm.h);
    const placed = [];
    for (const pc of pieces) {
      const n = pc.P.length;
      const c = pc.P.map(p => [0, 1].map(j => ((p[0] * A[0][j] + p[1] * A[1][j]) + p[2] * A[2][j]) + A[3][j]));
      const G = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]], R = [[0.0, 0.0], [0.0, 0.0], [0.0, 0.0]];
      for (let k = 0; k < n; k++) {
        const x = [c[k][0], c[k][1], 1.0];
        for (let i = 0; i < 3; i++) {
          for (let j = 0; j < 3; j++) G[i][j] = G[i][j] + x[i] * x[j];
          for (let j = 0; j < 2; j++) R[i][j] = R[i][j] + x[i] * pc.q[k][j];
        }
      }
      const M = solve(G, R);
      const tr = (M[0][0] * M[1][1] - M[0][1] * M[1][0]) < 0.0;
      const cc = c.map(ck => tr ? [ck[1], ck[0]] : [ck[0], ck[1]]);
      const off = [0, 1].map(j => { let sm = 0.0; for (let k = 0; k < n; k++) sm = sm + (pc.q[k][j] - cc[k][j]); return Math.floor(sm / n + 0.5); });
      for (let k = 0; k < n; k++) for (let j = 0; j < 2; j++) {
        const e = Math.abs((cc[k][j] + off[j]) - pc.q[k][j]);
        if (e > ATLAS_FIT) throw new Sc4Error(label + ': atlas piece of texture ' + hexU(pc.tid, 8) + " is " + pyFixed(e, 2) + " px off the view's projection");
      }
      const cov = atlasCovered(pc.q, pc.tris, pc.bm.w, pc.bm.h), xs = [], ys = [];
      for (let y = 0; y < pc.bm.h; y++) for (let x = 0; x < pc.bm.w; x++) if (cov[y * pc.bm.w + x]) { xs.push(x); ys.push(y); }
      placed.push({ pc, tr, off, xs, ys });
    }
    const toCanvas = (tr, off, x, y) => tr ? [y - off[1], x - off[0]] : [x - off[0], y - off[1]];
    let box = null;
    for (const { tr, off, xs, ys } of placed) for (let k = 0; k < xs.length; k++) {
      const [cx, cy] = toCanvas(tr, off, xs[k], ys[k]);
      if (!box) box = [cx, cy, cx, cy];
      else { if (cx < box[0]) box[0] = cx; if (cy < box[1]) box[1] = cy; if (cx > box[2]) box[2] = cx; if (cy > box[3]) box[3] = cy; }
    }
    if (!box) throw new Sc4Error(label + ': the atlas pieces cover no texel');
    const X0 = box[0], Y0 = box[1], W = box[2] - X0 + 1, H = box[3] - Y0 + 1;
    const canvas = new Uint8Array(W * H * 4);
    for (const { pc, tr, off, xs, ys } of placed) {
      const im = pc.bm.image, w = pc.bm.w;
      for (let k = 0; k < xs.length; k++) {
        const [cx, cy] = toCanvas(tr, off, xs[k], ys[k]);
        const s = 4 * (ys[k] * w + xs[k]), d = 4 * ((cy - Y0) * W + (cx - X0));
        if (im[s + 3] > canvas[d + 3]) { canvas[d] = im[s]; canvas[d + 1] = im[s + 1]; canvas[d + 2] = im[s + 2]; canvas[d + 3] = im[s + 3]; }
      }
    }
    const P = [], UV = [], tris = [];
    for (const { pc, tr, off } of placed) {
      const base = P.length;
      for (const t of pc.tris) tris.push(t.map(k => base + k));
      for (const p of pc.P) P.push([p[0], p[1], p[2]]);
      for (const qq of pc.q) { const [ux, uy] = toCanvas(tr, off, qq[0], qq[1]); UV.push([(ux - X0) / W, (uy - Y0) / H]); }
    }
    return { P, UV, tris, bm: { w: W, h: H, image: canvas, code: pieces[0].bm.code }, tid: pieces[0].tid, tiles: pieces.length };
  }

  // ---- rewards.lua_rewards: SC4's reward conditions from its own Lua scripts
  const RW_FAIR = ['g_population', 'g_city_r_population', 'g_city_r1_population+g_city_r2_population+g_city_r3_population'];
  const RW_POPVAR = 'game\\.g_[a-z0-9_]*population';
  function luaRewards(idx) {
    const texts = [];
    for (const k of idx.ofType(T_LUA)) { let b; try { b = idx.read(...k); } catch (e) { if (e instanceof Sc4Error) continue; throw e; } texts.push(latin1(b).replace(/--[^\n]*/g, '')); }
    const consts = new Map();
    for (const t of texts) for (const m of t.matchAll(/^[ \t]*tuning_constants\.([A-Za-z0-9_]+)[ \t]*=[ \t]*(-?[0-9]+(?:\.[0-9]+)?)/gm)) {
      const v = Number(m[2]); consts.set(m[1], Number.isInteger(v) ? v : new PyFloat(v));
    }
    const thresh = '(?:([0-9]+(?:\\.[0-9]+)?)[ \\t]*\\*[ \\t]*)?(tuning_constants\\.[A-Za-z0-9_]+)|([0-9]+(?:\\.[0-9]+)?)(?![0-9.])';
    const cmpRe = new RegExp('(' + RW_POPVAR + '(?:[ \\t]*\\+[ \\t]*' + RW_POPVAR + ')*)[ \\t]*<[ \\t]*(?:' + thresh + ')', 'g');
    const out = new Map();
    for (const t of texts) {
      const heads = [...t.matchAll(/^[ \t]*a[ \t]*=[ \t]*create_reward_([A-Za-z_]+)[ \t]*\([ \t]*'([0-9A-Fa-f]{8})'[ \t]*\)/gm)];
      heads.forEach((h, n) => {
        const body = t.slice(h.index + h[0].length, n + 1 < heads.length ? heads[n + 1].index : t.length);
        const cm = /function[ \t]+a\.condition[ \t]*\([ \t]*\)([\s\S]*?)\nend/.exec(body), cond = cm ? cm[1] : '';
        const cmps = [];
        for (const m of cond.matchAll(cmpRe)) {
          const v = m[1].split('+').map(x => pyStrip(x).slice(5)).join('+'), fac = m[2], th = m[3], lit = m[4];
          let val;                          // a tuning constant, times a factor (the Casino), or a number
          if (th) { val = consts.has(th.slice(17)) ? consts.get(th.slice(17)) : null; if (val !== null && fac) val = new PyFloat(Number(fac) * num(val)); }
          else val = new PyFloat(Number(lit));
          if (val instanceof PyFloat && Number.isInteger(val.v)) val = val.v;
          cmps.push({ measure: v, threshold: th ? (fac ? fac + ' * ' : '') + th : null, value: val });
        }
        let best = null;
        for (const c of cmps) if (RW_FAIR.includes(c.measure) && typeof c.value === 'number' && Number.isInteger(c.value) && (!best || c.value > best.value)) best = c;
        const pops = new Set(cmps.map(c => c.measure)), others = [];
        for (const m of cond.matchAll(/game\.([A-Za-z0-9_]+)/g)) {
          const v = m[1];
          if (!others.includes(v) && ![...pops].some(p => p.split('+').includes(v))) others.push(v);
        }
        others.sort(cmpStr);
        out.set(parseInt(h[2], 16), { advisor: h[1], population: best ? best.value : null, measure: best ? best.measure : null,
          threshold: best ? best.threshold : null, compares: cmps.map(c => [c.measure, c.value]), others });
      });
    }
    return out;
  }

  // ---- sc4conv.service_for: SC4 civic buildings, parks, rewards, landmarks -> bldimport kinds civic / reward / landmark
  const G_CIVIC = 0x1005, G_PARK = 0x1006, G_REWARD = 0x150B, G_LANDMARK = 0x150A, P_GROUPS = 0xAA1DD396;
  const CIVIC_SERVICE = new Map([[0x1500, 'police'], [0x1501, 'jail'], [0x1502, 'fire'], [0x1503, 'school'], [0x1504, 'college'],
    [0x1505, 'library'], [0x1506, 'museum'], [0x1507, 'hospital'], [0x1702, 'zoo']]);
  const CIVIC_LOT = { police: 3, jail: 3, fire: 3, hospital: 3, school: 3, college: 3, library: 2, museum: 3, small_park: 1, big_park: 3, zoo: 4,
    baseball: 4, playground: 2, pond: 2, fountain: 1, bus_stop: 1, train_station: 2 };
  const CIVIC_LABEL = { police: 'Police Station', jail: 'Jail', fire: 'Fire Station', hospital: 'Hospital', school: 'School', college: 'College',
    library: 'Library', museum: 'Museum', small_park: 'Small Park', big_park: 'Big Park', zoo: 'Zoo', baseball: 'Baseball Field',
    playground: 'Playground', pond: 'Pond', fountain: 'Fountain', bus_stop: 'Bus Stop', train_station: 'Train Station' };
  const PARK_WORDS = [['softball', 'baseball'], ['baseball', 'baseball'], ['playground', 'playground'], ['fountain', 'fountain'], ['pond', 'pond'], ['zoo', 'zoo']];
  const REWARD_POP = 20000, SC4_DESC = 'From SimCity 4';
  const SERVICE_EDITABLE = ['kind', 'base', 'population', 'year', 'description'];
  const editableOf = e => e.x_sc4 && e.x_sc4.service ? EDITABLE.concat(SERVICE_EDITABLE.filter(k => k in e)) : EDITABLE;
  const groupsHex = gs => gs.map(g => g < 0x10000 ? hexU(g, 4) : hexU(g, 8));
  const groupsOf = ex => asList(pv(ex, P_GROUPS, [])).filter(x => typeof x === 'number').map(x => x >>> 0);
  const pyStrV = v => v === null || v === undefined ? 'None' : v instanceof PyFloat ? pyRepr(v.v) : String(v);
  function rewardWords(r) {
    if (!r) return '';
    const cmp = r.compares.map(([m, v]) => m + ' ' + pyStrV(v)).join(', ') || 'no population';
    const oth = r.others.join(', ');
    return 'SC4 offers it as a reward when ' + cmp + (oth ? ' (also: ' + oth + ')' : '');
  }
  function serviceFor(b, rw) {
    const gs = b.groups || [];
    let sk;
    if (gs.includes(G_LANDMARK)) sk = 'landmark'; else if (gs.includes(G_REWARD)) sk = 'reward';
    else if (gs.includes(G_PARK)) sk = 'park'; else if (gs.includes(G_CIVIC)) sk = 'civic'; else return null;
    const n = lotFor(b), title = labelOf(b), svc = gs.filter(g => CIVIC_SERVICE.has(g)).map(g => CIVIC_SERVICE.get(g));
    const r = rw.get(b.tgi[2]) || null;
    const x = { sc4_kind: sk, groups: groupsHex(gs) };
    if (r) x.reward = { advisor: r.advisor, compares: r.compares.map(([m, v]) => [m, v]), others: r.others };
    const size = 'footprint ' + pyFixed(b.size_m[0], 1) + ' x ' + pyFixed(b.size_m[2], 1) + ' m';
    const rwn = rewardWords(r);
    let why0 = null;
    if (sk === 'civic' && !svc.length) { sk = 'landmark'; why0 = 'SC4 civic building (group 1005) of no service SC3 has a button for'; }
    if (sk === 'civic' || sk === 'park') {
      let base, why;
      if (sk === 'park') {
        const low = title.toLowerCase(), w = PARK_WORDS.find(([wd]) => low.includes(wd));
        base = w ? w[1] : (n <= 1 ? 'small_park' : 'big_park');
        why = w ? 'SC4 park (group 1006), its name says ' + w[0] + ': SC3 ' + CIVIC_LABEL[base] : 'SC4 park (group 1006), ' + size + ': SC3 ' + CIVIC_LABEL[base];
      } else {
        base = svc[0];
        why = 'SC4 civic building, service ' + base + ' (groups ' + groupsHex(gs).join(', ') + '): SC3 ' + CIVIC_LABEL[base];
      }
      const bl = CIVIC_LOT[base], ok = n <= bl;
      let note = why + '. A look of the SC3 ' + CIVIC_LABEL[base] + " button: the stock building's type, coverage and price on its " + bl + 'x' + bl + ' lot.';
      if (!ok) note += ' Off: its ' + size + ' needs ' + n + 'x' + n + '.';
      if (rwn) note += ' ' + rwn + '; in SC3 it is a look like the others.';
      return { kind: 'civic', base, lot: bl, ok, why, note, x };
    }
    if (sk === 'reward') {
      const pop = r && r.population !== null ? r.population : null;
      let why = 'SC4 reward (group 150B)';
      if (svc.length) why += ', also SC4 ' + svc.join('/') + ' service';
      const ok = LANDMARK_LOTS.includes(n);
      const popw = pop !== null ? 'SC3 population ' + pop + ' (' + r.measure + ')'
        : 'SC3 population ' + REWARD_POP + ', the default: ' + (r ? 'no SC4 condition counts the whole city' : 'no SC4 reward condition found');
      let note = why + '. ' + (rwn || 'No SC4 reward record') + '. ' + popw + ', year 0 (no SC4 reward condition reads the year).';
      if (svc.length && svc[0] in CIVIC_LOT) note += ' As a look of the SC3 ' + CIVIC_LABEL[svc[0]] + ' button instead: kind civic, base ' + svc[0] + '.';
      if (!ok) note += ' Off: its ' + size + ' needs ' + n + 'x' + n + ' and SC3 rewards are 1x1 to 4x4.';
      return { kind: 'reward', lot: n, ok, why, note, x, population: pop !== null ? pop : REWARD_POP, year: 0, description: SC4_DESC };
    }
    const why = why0 || 'SC4 landmark (group 150A)', ok = LANDMARK_LOTS.includes(n) && !why0;
    let note = why + ': an SC3 landmark (the landmark menu, one per city).';
    if (why0) note += ' Off: SC3 has no button for it.';
    else if (!ok) note += ' Off: its ' + size + ' needs ' + n + 'x' + n + ' and SC3 landmarks are 1x1 to 4x4.';
    return { kind: 'landmark', lot: n, ok, why, note, x, description: SC4_DESC };
  }
  function installNotes(nAll, bs, oth) {    // sc4conv.install_notes
    const nolook = oth.filter(o => o.groups.some(g => [G_CIVIC, G_PARK, G_REWARD, G_LANDMARK].includes(g)));
    const lines = ['SimCity 4 install: ' + bs.length + ' of its ' + nAll + ' buildings are civic buildings, parks, rewards or landmarks with a model;' +
      ' the others (homes, shops, offices, industry, utilities, transport) are not converted from an install'];
    if (nolook.length) lines.push(nolook.length + ' more civic buildings, parks, rewards or landmarks have no model of their own (their look is lot' +
      ' props), not converted: ' + nolook.map(labelOf).join(', '));
    return lines;
  }

  // ================================================================================================ inputs
  // Python's walk (catalog.dbpf_files): a folder's files sorted, then its folders sorted, depth first
  function walkOrder(tree, want = isDbpfName) {   // tree: { files: Map name -> src, dirs: Map name -> tree }
    const out = [];
    const rec = (t, pre) => {
      for (const n of [...t.files.keys()].sort()) if (want(n)) out.push(Object.assign({ path: pre + n }, t.files.get(n)));
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
      } else if (isDbpfName(leaf) || isReadme(leaf)) {    // task sc4pass2: readmes too (the dependency list)
        let cache = null;
        treeAdd(tree, parts, { bytes: async () => cache || (cache = await zipRead(bytes, e)) });
      }
    }
  }
  // inputs: [{ path: 'a/b/x.dat', bytes: async () => Uint8Array }] (folder listing or File objects), archives read
  async function sourcesFrom(inputs) {
    const tree = newTree(), deps = [];
    for (const it of inputs) {
      const parts = it.path.split('/').filter(Boolean), leaf = parts[parts.length - 1];
      if (isArchive(leaf) && it.size > DEPS_MIN && it.slice && it.stream) { deps.push(it); continue; }   // task sc4props
      if (isArchive(leaf)) {
        let t = tree; for (const p of parts) { if (!t.dirs.has(p)) t.dirs.set(p, newTree()); t = t.dirs.get(p); }
        await addArchive(t, await it.bytes());
      } else if (isDbpfName(leaf) || isReadme(leaf)) treeAdd(tree, parts, { bytes: it.bytes, size: it.size, slice: it.slice });
    }
    const inst = installOf(tree);           // task sc4civ: the player's SC4 install, its 7 game files only
    // task sc4baseprops: the install's files picked together with a download (another .dat / SC4 file or archive at the
    // top of the pick) are a prop source for it, not the input: the download is converted, the install lends its props
    // (an archive is unpacked into a folder of its own name; the game's own subfolders, Plugins included, and its other
    // top-level files, Intro.dat and Sound.dat, never count: a pick of the whole game folder stays the install)
    const game = new Set(INSTALL_FILES.concat(INSTALL_OTHER).map(f => f.toLowerCase()));
    const rest = !!inst && ([...tree.files.keys()].some(n => isDbpfName(n) && !game.has(n.toLowerCase())) || [...tree.dirs.keys()].some(isArchive));
    if (inst && !rest) { inst.readmes = []; inst.deps = deps; inst.install = true; return inst; }
    if (inst) for (const f of inst) { const parts = f.path.split('/'); let t = tree; for (const p of parts.slice(0, -1)) t = t.dirs.get(p); t.files.delete(parts[parts.length - 1]); }
    const out = walkOrder(tree);
    out.readmes = walkOrder(tree, isReadme);   // task sc4pass2: sc4conv.readme_files, the same walk
    out.deps = deps;                          // task sc4props: dependency packs, read by streaming (depsIndex)
    if (inst) out.sc4 = inst;                 // task sc4baseprops
    return out;
  }
  // a File System Access folder handle -> inputs (recursive)
  async function handleInputs(dir, pre = '', out = []) {
    for await (const [name, h] of dir.entries()) {
      if (h.kind === 'directory') { if (name !== 'sc3build') await handleInputs(h, pre + name + '/', out); }
      else if (isArchive(name)) out.push(blobInput(pre + name, await h.getFile()));   // task sc4props: size, slices, stream
      else if (isDbpfName(name)) out.push(blobInput(pre + name, await h.getFile()));   // task sc4civ: an install's files are read by slices
      else if (isReadme(name)) out.push({ path: pre + name, bytes: async () => new Uint8Array(await (await h.getFile()).arrayBuffer()) });
    }
    return out;
  }
  // File objects (webkitdirectory list, or picked .zip / .jar files) -> inputs
  const fileInputs = files => files.filter(f => isDbpfName(f.name) || isArchive(f.name) || isReadme(f.name)).map(f => {
    const parts = String(f.webkitRelativePath || f.name).split('/'); if (parts.length > 1) parts.shift();
    return blobInput(parts.join('/'), f);
  });
  // task sc4props: a File / Blob as an input that can also be read by slices and streamed (dependency packs)
  function blobInput(path, f) {
    return { path, size: f.size, mtime: f.lastModified || 0, bytes: async () => new Uint8Array(await f.arrayBuffer()),
      slice: async (a, b) => new Uint8Array(await f.slice(a, b).arrayBuffer()), stream: (a, b) => f.slice(a, b).stream() };
  }

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
    outlineShare45, foundationDiagonal, pickColours, markDiagonalCards,
    parseTextExemplar, composeTiles, modelState, others, packNotes, readmeDeps, fixEmptyNote,
    convert, sourcesFrom, handleInputs, fileInputs, zipEntries, zipRead, overlayFS, isDbpfName, isArchive,
    depsIndex, walkDeps, propPlan, propSummary, propsNotes, ownSource, modelOf, resolveProp, DEPS_MIN,
    luaRewards, serviceFor, composeAtlas, texKey, installOf, INSTALL_FILES,
  };
}

globalThis.SC4WEB = SC4WEB_LIB(globalThis.BLDWEB || (typeof require === 'function' ? require('./bldweb.js') : null));
if (typeof module === 'object' && module.exports) module.exports = globalThis.SC4WEB;
