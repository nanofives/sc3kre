// bldweb.js - task bldweb (2026-11-18d): bldimport.py inside the browser (classifier.html), byte for byte.
//
// Players have no Python, so this file renders 3D models (OBJ / MTL / PNG) and Building Architect .bld files into
// SimCity 3000 building art and packs, installs and removes them in the game folder, writing the same files, ids
// (<models>\sc3build\ids.json), backups and state.json as re/tools/bldimport/bldimport.py. It is a transcription:
//
//   bldrender.py  render_model / render_frame (numpy float64 / float32 steps kept in numpy's order and precision,
//                 numpy-on-OpenBLAS's fused multiply-add matmul included, see fma() below)
//   bldfile.py    read_bld, preview_frames, bat_frames
//   bldimport.py  read_models, ids_for, plan, build_files, sources, apply (install), restore, PORTS / port_table
//                 (task airsea 2026-11-19: kinds airport / seaport, re/analysis/PORT_PICK.md)
//   batgrow.py    IXF / TKB1 helpers, class_table, stock_buildings, bat_buildings
//   sprite_patch.py, sprite_encode.py, qfs.py, qfs_encode.py (the transcribed GZResourceD compressor)
//   Pillow 12.3.0 Quant.c median cut (palette_cut), Resample.c LANCZOS / BICUBIC + RGBa premultiply (.bld previews)
//
// The golden test (webtest/golden.mjs) runs this file under node against the Python tool's output.
// One classic script, no imports: the page loads it with <script src>, the Web Worker is built from the
// BLDWEB_LIB function's own source (a Blob URL works from file://), node loads it with require().
//
// pilMedianCut, QHash and pilResize are transcribed from Pillow 12.3.0 (src/libImaging/Quant.c, QuantHash.c,
// QuantHeap.c, Resample.c, Convert.c). Pillow's notice, as its LICENSE requires:
//
//   The Python Imaging Library (PIL) is
//       Copyright (c) 1997-2011 by Secret Labs AB
//       Copyright (c) 1995-2011 by Fredrik Lundh and contributors
//   Pillow is the friendly PIL fork. It is
//       Copyright (c) 2010 by Jeffrey 'Alex' Clark and contributors
//   Quant.c: Written by Toby J Sargeant. Copyright (c) 1998 by Toby J Sargeant.
//
//   Permission to use, copy, modify and distribute this software and its documentation for any purpose and without
//   fee is hereby granted, provided that the above copyright notice appears in all copies, and that both that
//   copyright notice and this permission notice appear in supporting documentation, and that the name of Secret
//   Labs AB or the author not be used in advertising or publicity pertaining to distribution of the software without
//   specific, written prior permission.
//
//   SECRET LABS AB AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE, INCLUDING ALL IMPLIED
//   WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL SECRET LABS AB OR THE AUTHOR BE LIABLE FOR ANY
//   SPECIAL, INDIRECT OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS,
//   WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE
//   USE OR PERFORMANCE OF THIS SOFTWARE.
'use strict';

function BLDWEB_LIB() {
  'use strict';
  const fr = Math.fround;

  // ================================================================================================ small helpers
  class BldError extends Error {}
  const u8cat = arrs => {
    let n = 0; for (const a of arrs) n += a.length;
    const out = new Uint8Array(n); let o = 0;
    for (const a of arrs) { out.set(a, o); o += a.length; }
    return out;
  };
  const rdU32 = (b, o) => (b[o] | (b[o + 1] << 8) | (b[o + 2] << 16) | (b[o + 3] << 24)) >>> 0;
  const rdU16 = (b, o) => b[o] | (b[o + 1] << 8);
  const rdI16 = (b, o) => { const v = rdU16(b, o); return v >= 0x8000 ? v - 0x10000 : v; };
  const wrU32 = (b, o, v) => { b[o] = v & 255; b[o + 1] = (v >>> 8) & 255; b[o + 2] = (v >>> 16) & 255; b[o + 3] = (v >>> 24) & 255; };
  const wrU16 = (b, o, v) => { b[o] = v & 255; b[o + 1] = (v >>> 8) & 255; };
  const packU32s = (...vals) => { const b = new Uint8Array(4 * vals.length); vals.forEach((v, k) => wrU32(b, 4 * k, v >>> 0)); return b; };
  const ascii = s => { const b = new Uint8Array(s.length); for (let k = 0; k < s.length; k++) b[k] = s.charCodeAt(k) & 255; return b; };
  const latin1 = b => { let s = ''; for (let k = 0; k < b.length; k += 8192) s += String.fromCharCode.apply(null, b.subarray(k, k + 8192)); return s; };
  const bytesEq = (a, b) => {
    if (a === b) return true;
    if (!a || !b || a.length !== b.length) return false;
    for (let k = 0; k < a.length; k++) if (a[k] !== b[k]) return false;
    return true;
  };
  const hex8 = v => (v >>> 0).toString(16).toUpperCase().padStart(8, '0');
  const lowerSort = names => names.slice().sort((a, b) => { const x = a.toLowerCase(), y = b.toLowerCase(); return x < y ? -1 : x > y ? 1 : 0; });
  // Python truthiness of a JSON value
  const pyTrue = v => !(v === null || v === undefined || v === false || v === 0 || v === '' ||
    (Array.isArray(v) && !v.length) || (typeof v === 'object' && !Array.isArray(v) && !Object.keys(v).length));
  const PY_WS = /[\s\x1c-\x1f\x85]/;    // str.isspace() (JS \s also holds ﻿, which Python does not strip)
  const pySplit = s => {               // str.split() with no argument
    const out = []; let cur = '';
    for (const ch of s) {
      if (ch !== '﻿' && PY_WS.test(ch)) { if (cur) { out.push(cur); cur = ''; } } else cur += ch;
    }
    if (cur) out.push(cur);
    return out;
  };
  const pyStrip = s => { let a = 0, b = s.length; while (a < b && s[a] !== '﻿' && PY_WS.test(s[a])) a++; while (b > a && s[b - 1] !== '﻿' && PY_WS.test(s[b - 1])) b--; return s.slice(a, b); };
  const pyLines = s => {               // text-mode iteration: universal newlines, line keeps its end (split drops it)
    return s.split(/\r\n|\r|\n/);
  };
  function pyFloat(t) {
    let s = pyStrip(t);
    if (/^[+-]?(inf|infinity)$/i.test(s)) return s[0] === '-' ? -Infinity : Infinity;
    if (/^[+-]?nan$/i.test(s)) return NaN;
    if (/\d_\d/.test(s)) { if (/(^|[^\d])_|_($|[^\d])/.test(s)) throw new BldError("could not convert string to float: '" + t + "'"); s = s.replace(/_/g, ''); }
    if (!/^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/.test(s)) throw new BldError("could not convert string to float: '" + t + "'");
    return parseFloat(s);
  }
  function pyInt(t) {
    let s = pyStrip(t);
    if (/\d_\d/.test(s)) s = s.replace(/(\d)_(?=\d)/g, '$1');
    if (!/^[+-]?\d+$/.test(s)) throw new BldError("invalid literal for int() with base 10: '" + t + "'");
    return parseInt(s, 10);
  }
  // round half to even (np.rint, Python round)
  const rint = x => { const f = Math.floor(x), d = x - f; if (d > 0.5) return f + 1; if (d < 0.5) return f; return (f % 2 === 0) ? f : f + 1; };

  // cp1252 (Python codec: 0x81 0x8D 0x8F 0x90 0x9D undefined)
  const CP1252_HI = [0x20AC, -1, 0x201A, 0x0192, 0x201E, 0x2026, 0x2020, 0x2021, 0x02C6, 0x2030, 0x0160, 0x2039, 0x0152, -1, 0x017D, -1,
    -1, 0x2018, 0x2019, 0x201C, 0x201D, 0x2022, 0x2013, 0x2014, 0x02DC, 0x2122, 0x0161, 0x203A, 0x0153, -1, 0x017E, 0x0178];
  const CP1252_ENC = new Map();
  for (let k = 0; k < 256; k++) { const c = k >= 0x80 && k < 0xA0 ? CP1252_HI[k - 0x80] : k; if (c >= 0) CP1252_ENC.set(c, k); }
  function cp1252Encode(s, replace) {      // -> Uint8Array, or null when not encodable (replace: '?' instead)
    const out = [];
    for (const ch of s) {
      const b = CP1252_ENC.get(ch.codePointAt(0));
      if (b === undefined) { if (!replace) return null; out.push(0x3F); } else out.push(b);
    }
    return Uint8Array.from(out);
  }
  function cp1252Decode(b) {              // errors="replace"
    let s = '';
    for (const x of b) { const c = x >= 0x80 && x < 0xA0 ? CP1252_HI[x - 0x80] : x; s += c < 0 ? '�' : String.fromCharCode(c); }
    return s;
  }
  const utf8Dec = () => new TextDecoder('utf-8', { ignoreBOM: true });   // Python encoding="utf-8": BOM kept, errors replace

  // json.dumps(obj, indent=k, sort_keys=s) with ensure_ascii (strings, ints, bools, null, lists, dicts)
  function pyJsonStr(s) {
    let o = '"';
    for (let k = 0; k < s.length; k++) {
      const c = s.charCodeAt(k), ch = s[k];
      if (ch === '"') o += '\\"'; else if (ch === '\\') o += '\\\\'; else if (ch === '\n') o += '\\n';
      else if (ch === '\r') o += '\\r'; else if (ch === '\t') o += '\\t'; else if (ch === '\b') o += '\\b';
      else if (ch === '\f') o += '\\f'; else if (c < 0x20 || c > 0x7e) o += '\\u' + c.toString(16).padStart(4, '0');
      else o += ch;
    }
    return o + '"';
  }
  function pyJson(v, indent, sortKeys, level = 0) {
    if (v === null || v === undefined) return 'null';
    if (v === true) return 'true';
    if (v === false) return 'false';
    if (typeof v === 'number') {
      if (!Number.isInteger(v)) throw new BldError('pyJson: floats are not used in the files this tool writes');
      return String(v);
    }
    if (typeof v === 'string') return pyJsonStr(v);
    const pad = ' '.repeat(indent * (level + 1)), end = ' '.repeat(indent * level);
    if (Array.isArray(v)) {
      if (!v.length) return '[]';
      return '[\n' + v.map(x => pad + pyJson(x, indent, sortKeys, level + 1)).join(',\n') + '\n' + end + ']';
    }
    let keys = Object.keys(v);
    if (!keys.length) return '{}';
    if (sortKeys) keys = keys.slice().sort((a, b) => a < b ? -1 : a > b ? 1 : 0);
    return '{\n' + keys.map(k => pad + pyJsonStr(k) + ': ' + pyJson(v[k], indent, sortKeys, level + 1)).join(',\n') + '\n' + end + '}';
  }

  // sha256 (sync, no crypto.subtle needed)
  const SHA_K = new Uint32Array([0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
    0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
    0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb,
    0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f,
    0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2]);
  function sha256(data) {
    const n = data.length, tot = ((n + 9 + 63) >> 6) << 6;
    const m = new Uint8Array(tot); m.set(data); m[n] = 0x80;
    const bits = n * 8; for (let k = 0; k < 8; k++) m[tot - 1 - k] = Math.floor(bits / Math.pow(2, 8 * k)) & 255;
    const H = new Uint32Array([0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]);
    const w = new Uint32Array(64);
    for (let o = 0; o < tot; o += 64) {
      for (let t = 0; t < 16; t++) w[t] = (m[o + 4 * t] << 24) | (m[o + 4 * t + 1] << 16) | (m[o + 4 * t + 2] << 8) | m[o + 4 * t + 3];
      for (let t = 16; t < 64; t++) {
        const x = w[t - 15], y = w[t - 2];
        const s0 = ((x >>> 7) | (x << 25)) ^ ((x >>> 18) | (x << 14)) ^ (x >>> 3);
        const s1 = ((y >>> 17) | (y << 15)) ^ ((y >>> 19) | (y << 13)) ^ (y >>> 10);
        w[t] = (w[t - 16] + s0 + w[t - 7] + s1) | 0;
      }
      let a = H[0], b = H[1], c = H[2], d = H[3], e = H[4], f = H[5], g = H[6], h = H[7];
      for (let t = 0; t < 64; t++) {
        const S1 = ((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7));
        const ch = (e & f) ^ (~e & g);
        const t1 = (h + S1 + ch + SHA_K[t] + w[t]) | 0;
        const S0 = ((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10));
        const mj = (a & b) ^ (a & c) ^ (b & c);
        const t2 = (S0 + mj) | 0;
        h = g; g = f; f = e; e = (d + t1) | 0; d = c; c = b; b = a; a = (t1 + t2) | 0;
      }
      H[0] += a; H[1] += b; H[2] += c; H[3] += d; H[4] += e; H[5] += f; H[6] += g; H[7] += h;
    }
    return Array.from(H, x => x.toString(16).padStart(8, '0')).join('');
  }

  // ================================================================================================ exact FMA
  // numpy 2.5 on OpenBLAS 0.3.34 (Haswell kernel, the Python tool's runtime) evaluates a float64 (N,3) @ (3,) as
  // fma(x2, v2, fma(x0, v0, x1 * v1)), measured bit for bit on 2D and 3D operands of every size 1..1003
  // (webtest/README). JS has no fma: this is Boldo & Melquiond's emulation (exact product, TwoSum, round to odd).
  const SPLIT = 134217729;
  const _f64 = new Float64Array(1), _u32 = new Uint32Array(_f64.buffer);
  function nextToward(v, dirPositive) {
    _f64[0] = v;
    let lo = _u32[0], hi = _u32[1];
    const up = (v > 0) === dirPositive || v === 0;          // magnitude grows
    if (v === 0) { return dirPositive ? 5e-324 : -5e-324; }
    if (up) { lo = (lo + 1) >>> 0; if (lo === 0) hi = (hi + 1) >>> 0; } else { if (lo === 0) hi = (hi - 1) >>> 0; lo = (lo - 1) >>> 0; }
    _u32[0] = lo; _u32[1] = hi;
    return _f64[0];
  }
  function fma(a, b, c) {
    const p = a * b;
    const a1 = SPLIT * a, ah = a1 - (a1 - a), al = a - ah;
    const b1 = SPLIT * b, bh = b1 - (b1 - b), bl = b - bh;
    const pe = ((ah * bh - p) + ah * bl + al * bh) + al * bl;  // a*b = p + pe exactly
    const s = c + p, bb = s - c, t = (c - (s - bb)) + (p - bb);  // c + p = s + t exactly
    let v = t + pe;
    const bv = v - t, w = (t - (v - bv)) + (pe - bv);           // t + pe = v + w exactly
    if (w !== 0) { _f64[0] = v; if ((_u32[0] & 1) === 0) v = nextToward(v, w > 0); }   // round to odd
    return s + v;
  }
  const mm3 = (x0, x1, x2, v) => fma(x2, v[2], fma(x0, v[0], x1 * v[1]));        // float64 (N,3) @ (3,)
  // float32 (N,3) @ (3,) float32: N >= 2 sequential float32 (sgemv); N == 1 accumulates in double (sdot path)
  const mm3f = (x0, x1, x2, v, one) => one ? fr(x0 * v[0] + x1 * v[1] + x2 * v[2]) : fr(fr(fr(x0 * v[0]) + fr(x1 * v[1])) + fr(x2 * v[2]));

  // ================================================================================================ bldrender constants
  const ZOOMS = 5, ROTS = 4;
  const VSCALE = 0.6123724356957945;                                  // cos(30 deg) / sqrt(2)
  const F = [-0.6123724356957945, 0.6123724356957945, -0.49999999999999994];
  const SUN = [0.19813745600514793, -0.5283665493470612, 0.8255727333547831];
  const SM_A = [-0.9363291775690445, -0.3511234415883917, 0.0];         // _shadow_map basis for SUN
  const SM_B = [0.2898779394170671, -0.7730078384455121, -0.5642957220652238];
  const CALIB = {
    0: [0.0, 0.75, { 1: 0.5, 2: 0.5, 3: 0.25, 4: 0.5 }],
    1: [0.0, 0.25, { 1: 0.5, 2: 1.0, 3: 1.0, 4: 1.0 }],
    2: [0.0, 0.25, { 1: 0.5, 2: 1.0, 3: 1.0, 4: 1.0 }],
    3: [0.0, 0.5, { 1: 0.25, 2: 0.25, 3: 0.75, 4: 0.75 }],
    4: [0.0, 1.0, { 1: 0.25, 2: 0.5, 3: 0.5, 4: 0.5 }]};
  const AMBIENT = 0.50, DIFFUSE = 0.62, SHADOW_KEEP = 0.65;
  const STYLES = {
    clean: { light: 'sun', ambient: AMBIENT, diffuse: DIFFUSE, shadow_keep: SHADOW_KEEP, zoom4: 'native', palette: null, dither: false,
      sat: 1.0, contrast: 1.0, pivot: 0.45, grain: 0.0, edge: 0.0, grass: null, grass_amp: 0.07 },
    stock: { light: 'axis', ambient: 0.47, top: 0.42, ku: 0.37, kv: 0.20, shadow_sun: null,
      shadow_keep: { 0: 0.25, 1: 0.40, 2: 0.55, 3: 0.70 }, zoom4: 'double', palette: 255, dither: false,
      sat: { 0: 2.6, 1: 2.2, 2: 2.0, 3: 2.0 }, contrast: { 0: 1.4, 1: 1.2, 2: 1.3, 3: 1.35 }, pivot: 0.42,
      grain: { 0: 0.12, 1: 0.18, 2: 0.24, 3: 0.30 }, edge: 0.0,
      rim: { width: 0.30, dark: { 0: 0.10, 1: 0.30, 2: 0.50, 3: 0.62 } },
      grass: { 0: [120, 144, 110], 1: [106, 134, 93], 2: [102, 138, 84], 3: [100, 145, 78] }, grass_amp: 0.10 }};
  STYLES.stock_sharp = Object.assign({}, STYLES.stock, { zoom4: 'native' });
  // task sc4web: bldrender's task sc4conv styles for art with its light painted in (SC4 BAT renders)
  STYLES.baked = Object.assign({}, STYLES.stock, { light: 'sun', ambient: 1.0, diffuse: 0.0, shadow_keep: 0.0, sat: 1.0,
    contrast: 1.0, grain: 0.0, tone: [0.75, 1.33] });
  STYLES.baked_raw = Object.assign({}, STYLES.baked, { tone: null });
  STYLES.baked_sharp = Object.assign({}, STYLES.baked, { zoom4: 'native' });
  const PEEL_LAYERS = 4;
  // np.power(float32, float32 0.75) on the Python tool's numpy is not correctly rounded: over every luminance a
  // texel can give (641,191 float32 values, both matmul paths) it differs from fround(Math.pow) on these 67, as
  // [input bits, numpy result bits] (task sc4web, measured with numpy 2.5 on this PC). Other inputs: fround(Math.pow).
  const POW075_EXC = new Map([[1028467553, 1037621169], [1032253282, 1040526007], [1036284025, 1043365332], [1041560361, 1047605256], [1041569834, 1047616759], [1041966436, 1048095889], [1042746740, 1048800596], [1044645526, 1049898297], [1045236612, 1050231509], [1045608473, 1050439257], [1046610370, 1050992177], [1047968600, 1051727072], [1048453890, 1051985857], [1048643372, 1052122062], [1048756800, 1052241930], [1048762589, 1052248037], [1048771143, 1052257059], [1049012734, 1052510950], [1049387491, 1052901381], [1049960285, 1053490552], [1050521236, 1054059226], [1050535315, 1054073398], [1050985341, 1054523901], [1050997052, 1054535561], [1051029158, 1054567511], [1051320094, 1054855966], [1051453259, 1054987365], [1052875835, 1056367958], [1053561399, 1056991959], [1053823651, 1057115430], [1053840493, 1057123339], [1053974186, 1057186035], [1054199591, 1057291397], [1055076875, 1057697519], [1056392868, 1058295721], [1056809731, 1058482644], [1056813154, 1058484174], [1057534311, 1059055717], [1057678792, 1059182227], [1058470017, 1059866403], [1058915633, 1060245676], [1059066761, 1060373370], [1059183347, 1060471564], [1059534154, 1060765419], [1060195176, 1061312833], [1060514469, 1061574446], [1060535788, 1061591851], [1060687768, 1061715705], [1060702178, 1061727428], [1061226351, 1062151533], [1062021985, 1062786993], [1062325028, 1063026536], [1062574383, 1063222652], [1062784854, 1063387507], [1062794462, 1063395018], [1063193758, 1063706056], [1063627991, 1064041908], [1063822938, 1064191897], [1063844715, 1064208622], [1064096966, 1064401922], [1064278751, 1064540737], [1064307502, 1064562655], [1064499025, 1064708406], [1064754895, 1064902444], [1064755224, 1064902693], [1064764105, 1064909414], [1064798516, 1064935447]]);
  const _f32 = new Float32Array(1), _f32u = new Uint32Array(_f32.buffer);
  function powf(x, g) {
    if (g === 0.75) { _f32[0] = x; const e = POW075_EXC.get(_f32u[0]); if (e !== undefined) { _f32u[0] = e; return _f32[0]; } }
    return fr(Math.pow(x, g));
  }
  const DEFAULT_STYLE = 'stock';
  const BA_LOOK = { zoom4: 'double', palette: null };
  const pz = (v, z) => {                  // _pz: {zoom: value}, highest key <= z, else the smallest key
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      const ks = Object.keys(v).map(Number).sort((a, b) => a - b);
      const le = ks.filter(k => k <= z);
      return v[le.length ? le[le.length - 1] : ks[0]];
    }
    return v;
  };
  function styleOf(style, env) {
    if (style && typeof style === 'object') return [style.name || 'custom', style];
    const name = style || env || DEFAULT_STYLE;
    if (!STYLES[name]) throw new BldError('render style ' + JSON.stringify(name) + ': choose one of ' + Object.keys(STYLES).sort().join(', '));
    return [name, STYLES[name]];
  }

  // ================================================================================================ images
  // image = { w, h, d: Uint8ClampedArray|Uint8Array RGBA }
  const newImg = (w, h) => ({ w, h, d: new Uint8Array(w * h * 4) });
  function imgNearest2x(im) {
    const o = newImg(im.w * 2, im.h * 2);
    for (let y = 0; y < o.h; y++) for (let x = 0; x < o.w; x++) {
      const s = ((y >> 1) * im.w + (x >> 1)) * 4, t = (y * o.w + x) * 4;
      o.d[t] = im.d[s]; o.d[t + 1] = im.d[s + 1]; o.d[t + 2] = im.d[s + 2]; o.d[t + 3] = im.d[s + 3];
    }
    return o;
  }
  function imgMirror(im) {
    const o = newImg(im.w, im.h);
    for (let y = 0; y < im.h; y++) for (let x = 0; x < im.w; x++) {
      const s = (y * im.w + x) * 4, t = (y * im.w + (im.w - 1 - x)) * 4;
      for (let c = 0; c < 4; c++) o.d[t + c] = im.d[s + c];
    }
    return o;
  }
  function imgCrop(im, x0, y0, x1, y1) {   // PIL crop((x0, y0, x1, y1)), inside the image
    const o = newImg(x1 - x0, y1 - y0);
    for (let y = 0; y < o.h; y++) o.d.set(im.d.subarray(((y + y0) * im.w + x0) * 4, ((y + y0) * im.w + x1) * 4), y * o.w * 4);
    return o;
  }
  function quantize565(im) {              // bldrender.quantize565
    const o = newImg(im.w, im.h), a = im.d, b = o.d;
    for (let k = 0; k < a.length; k += 4) {
      if (a[k + 3] < 128) continue;        // a[alpha < 128] = 0 (all four channels)
      const r5 = a[k] >> 3, g6 = a[k + 1] >> 2; let b5 = a[k + 2] >> 3;
      if (r5 === 31 && g6 === 0 && b5 === 31) b5 = 30;
      b[k] = Math.floor(r5 * 255 / 31); b[k + 1] = Math.floor(g6 * 255 / 63); b[k + 2] = Math.floor(b5 * 255 / 31); b[k + 3] = a[k + 3];
    }
    return o;
  }

  // ------------------------------------------------------------------------------------------------ PNG decoder
  // Decodes to what PIL's Image.open(p).convert("RGB") gives: 16-bit samples keep their high byte (RGB;16B,
  // RGBA;16B, LA;16B), 16-bit grey is I;16 -> RGB (value, 255 above 255), 1/2/4-bit grey is scaled (1, L;2, L;4),
  // palette indices past the PLTE entries take PIL's grey ramp, alpha / tRNS / gamma / ICC are ignored.
  async function inflate(data) {
    if (typeof DecompressionStream === 'undefined') throw new BldError('this browser has no DecompressionStream (PNG)');
    const ds = new DecompressionStream('deflate');
    const out = new Response(new Blob([data]).stream().pipeThrough(ds));
    return new Uint8Array(await out.arrayBuffer());
  }
  async function decodePNG(buf) {
    const b = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
    const sig = [137, 80, 78, 71, 13, 10, 26, 10];
    for (let k = 0; k < 8; k++) if (b[k] !== sig[k]) throw new BldError('not a PNG file');
    let o = 8, W = 0, H = 0, depth = 0, ctype = 0, inter = 0, plte = null, trns = null; const idat = [];
    while (o + 8 <= b.length) {
      const len = ((b[o] << 24) | (b[o + 1] << 16) | (b[o + 2] << 8) | b[o + 3]) >>> 0;
      const typ = String.fromCharCode(b[o + 4], b[o + 5], b[o + 6], b[o + 7]);
      const d = b.subarray(o + 8, o + 8 + len);
      if (typ === 'IHDR') { W = ((d[0] << 24) | (d[1] << 16) | (d[2] << 8) | d[3]) >>> 0; H = ((d[4] << 24) | (d[5] << 16) | (d[6] << 8) | d[7]) >>> 0; depth = d[8]; ctype = d[9]; inter = d[12]; }
      else if (typ === 'PLTE') plte = d;
      else if (typ === 'tRNS') trns = d.slice();
      else if (typ === 'IDAT') idat.push(d);
      else if (typ === 'IEND') break;
      o += 12 + len;
    }
    const ch = { 0: 1, 2: 3, 3: 1, 4: 2, 6: 4 }[ctype];
    if (!ch || !W || !H) throw new BldError('unsupported PNG (colour type ' + ctype + ')');
    const raw = await inflate(u8cat(idat));
    const bitsPP = ch * depth, bpp = Math.max(1, bitsPP >> 3);
    const samples = new Uint16Array(W * H * ch);        // raw sample values
    let rp = 0;
    const passes = inter ? [[0, 0, 8, 8], [4, 0, 8, 8], [0, 4, 4, 8], [2, 0, 4, 4], [0, 2, 2, 4], [1, 0, 2, 2], [0, 1, 1, 2]] : [[0, 0, 1, 1]];
    for (const [x0, y0, dx, dy] of passes) {
      const pw = Math.ceil((W - x0) / dx), ph = Math.ceil((H - y0) / dy);
      if (pw <= 0 || ph <= 0) continue;
      const stride = Math.ceil(pw * bitsPP / 8);
      let prev = new Uint8Array(stride), cur = new Uint8Array(stride);
      for (let y = 0; y < ph; y++) {
        const ft = raw[rp++];
        for (let x = 0; x < stride; x++) {
          const v = raw[rp++], a = x >= bpp ? cur[x - bpp] : 0, up = prev[x], c = x >= bpp ? prev[x - bpp] : 0;
          let r;
          if (ft === 0) r = v; else if (ft === 1) r = v + a; else if (ft === 2) r = v + up; else if (ft === 3) r = v + ((a + up) >> 1);
          else if (ft === 4) { const p = a + up - c, pa = Math.abs(p - a), pb = Math.abs(p - up), pc = Math.abs(p - c); r = v + (pa <= pb && pa <= pc ? a : pb <= pc ? up : c); }
          else throw new BldError('bad PNG filter ' + ft);
          cur[x] = r & 255;
        }
        const yy = y0 + y * dy;
        for (let x = 0; x < pw; x++) {
          const xx = x0 + x * dx;
          for (let c = 0; c < ch; c++) {
            let v;
            if (depth === 8) v = cur[x * ch + c];
            else if (depth === 16) v = (cur[(x * ch + c) * 2] << 8) | cur[(x * ch + c) * 2 + 1];
            else { const bit = (x * ch + c) * depth; v = (cur[bit >> 3] >> (8 - depth - (bit & 7))) & ((1 << depth) - 1); }
            samples[(yy * W + xx) * ch + c] = v;
          }
        }
        const t = prev; prev = cur; cur = t;
      }
    }
    const rgb = new Uint8Array(W * H * 3);
    const hiByte = v => depth === 16 ? v >> 8 : v;
    for (let k = 0; k < W * H; k++) {
      let r, g, bl;
      if (ctype === 0) {
        const v = samples[k];
        const L = depth === 1 ? (v ? 255 : 0) : depth === 2 ? v * 85 : depth === 4 ? v * 17 : depth === 8 ? v : (v < 256 ? v : 255);
        r = g = bl = L;
      } else if (ctype === 4) { r = g = bl = hiByte(samples[k * 2]); }
      else if (ctype === 3) {
        const i = samples[k];
        if (plte && 3 * i + 2 < plte.length) { r = plte[3 * i]; g = plte[3 * i + 1]; bl = plte[3 * i + 2]; } else r = g = bl = i;
      } else { r = hiByte(samples[k * ch]); g = hiByte(samples[k * ch + 1]); bl = hiByte(samples[k * ch + 2]); }
      rgb[3 * k] = r; rgb[3 * k + 1] = g; rgb[3 * k + 2] = bl;
    }
    // task sc4web: alpha as Image.open(p).convert("RGBA") gives it, when PIL reports an alpha band (LA, RGBA) or
    // "transparency" (a tRNS chunk): palette alpha per index (255 past the table), a grey / RGB colour key (8-bit)
    let a = null;
    if (ctype === 4 || ctype === 6) {
      a = new Uint8Array(W * H);
      for (let k = 0; k < W * H; k++) a[k] = hiByte(samples[k * ch + ch - 1]);
    } else if (trns && (ctype === 3 || depth === 8)) {
      a = new Uint8Array(W * H).fill(255);
      if (ctype === 3) { for (let k = 0; k < W * H; k++) { const i = samples[k]; if (i < trns.length) a[k] = trns[i]; } }
      else if (ctype === 0 && trns.length >= 2) { const key = (trns[0] << 8) | trns[1]; for (let k = 0; k < W * H; k++) if (samples[k] === key) a[k] = 0; }
      else if (ctype === 2 && trns.length >= 6) {
        const kr = (trns[0] << 8) | trns[1], kg = (trns[2] << 8) | trns[3], kb = (trns[4] << 8) | trns[5];
        for (let k = 0; k < W * H; k++) if (samples[3 * k] === kr && samples[3 * k + 1] === kg && samples[3 * k + 2] === kb) a[k] = 0;
      }
    }
    return { w: W, h: H, rgb, a };
  }
  // JPEG and other formats: the browser's own decoder (PIL uses libjpeg-turbo too; not checked byte for byte)
  async function decodeOther(buf) {
    if (typeof createImageBitmap === 'undefined' || typeof OffscreenCanvas === 'undefined') throw new BldError('no image decoder for this texture here');
    const bm = await createImageBitmap(new Blob([buf]), { colorSpaceConversion: 'none', premultiplyAlpha: 'none' });
    const c = new OffscreenCanvas(bm.width, bm.height), g = c.getContext('2d');
    g.drawImage(bm, 0, 0);
    const d = g.getImageData(0, 0, bm.width, bm.height).data, rgb = new Uint8Array(bm.width * bm.height * 3);
    for (let k = 0; k < bm.width * bm.height; k++) { rgb[3 * k] = d[4 * k]; rgb[3 * k + 1] = d[4 * k + 1]; rgb[3 * k + 2] = d[4 * k + 2]; }
    return { w: bm.width, h: bm.height, rgb };
  }
  async function decodeImage(buf) {
    const b = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
    if (b[0] === 137 && b[1] === 80 && b[2] === 78 && b[3] === 71) return decodePNG(b);
    return decodeOther(b);
  }

  // ------------------------------------------------------------------------------------------------ PNG encoder (stored)
  function crc32Table() { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; }
  let CRC_T = null;
  function crc32(b, c = 0xFFFFFFFF) { CRC_T = CRC_T || crc32Table(); for (let k = 0; k < b.length; k++) c = CRC_T[(c ^ b[k]) & 255] ^ (c >>> 8); return c; }
  function adler32(b) { let a = 1, s = 0; for (let k = 0; k < b.length; k++) { a = (a + b[k]) % 65521; s = (s + a) % 65521; } return ((s << 16) | a) >>> 0; }
  function encodePNG(im) {               // RGBA, zlib stored blocks (for previews and test dumps only)
    const rowLen = im.w * 4 + 1, raw = new Uint8Array(rowLen * im.h);
    for (let y = 0; y < im.h; y++) { raw[y * rowLen] = 0; raw.set(im.d.subarray(y * im.w * 4, (y + 1) * im.w * 4), y * rowLen + 1); }
    const blocks = [Uint8Array.from([0x78, 0x01])];
    for (let o = 0; o < raw.length || o === 0; o += 65535) {
      const n = Math.min(65535, raw.length - o), last = o + n >= raw.length;
      const h = new Uint8Array(5); h[0] = last ? 1 : 0; wrU16(h, 1, n); wrU16(h, 3, ~n & 0xFFFF);
      blocks.push(h, raw.subarray(o, o + n));
      if (last) break;
    }
    const ad = adler32(raw); blocks.push(Uint8Array.from([ad >>> 24, (ad >>> 16) & 255, (ad >>> 8) & 255, ad & 255]));
    const z = u8cat(blocks);
    const chunk = (typ, d) => {
      const out = new Uint8Array(12 + d.length);
      out[0] = d.length >>> 24; out[1] = (d.length >>> 16) & 255; out[2] = (d.length >>> 8) & 255; out[3] = d.length & 255;
      out.set(ascii(typ), 4); out.set(d, 8);
      const c = (crc32(out.subarray(4, 8 + d.length)) ^ 0xFFFFFFFF) >>> 0;
      out[8 + d.length] = c >>> 24; out[9 + d.length] = (c >>> 16) & 255; out[10 + d.length] = (c >>> 8) & 255; out[11 + d.length] = c & 255;
      return out;
    };
    const ih = new Uint8Array(13); ih.set([im.w >>> 24, (im.w >>> 16) & 255, (im.w >>> 8) & 255, im.w & 255, im.h >>> 24, (im.h >>> 16) & 255, (im.h >>> 8) & 255, im.h & 255, 8, 6, 0, 0, 0]);
    return u8cat([Uint8Array.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', ih), chunk('IDAT', z), chunk('IEND', new Uint8Array(0))]);
  }

  // ------------------------------------------------------------------------------------------------ PIL median cut
  // Pillow 12.3.0 src/libImaging/Quant.c quantize() with kmeans 0 (Image.quantize(method=MEDIANCUT)), QuantHash.c and
  // QuantHeap.c transcribed, including the hash table's bucket order (it decides the list order before the merge
  // sorts) and the pixel hash that merges colours whose PIXEL_HASH collides.
  const PIXEL_HASH = (r, g, b) => (Math.imul(r, 463) ^ Math.imul(g << 8, 10069) ^ Math.imul(b << 16, 64997)) >>> 0;
  const UNIT = [0, 1, 0, 1, 0, 0, 0, 1, 0, 1, 0, 1, 0, 1, 0, 0];
  function findPrime(start, dir) { start >>>= 0; while (start > 1) { if (!UNIT[start & 15]) { start = (start + dir) >>> 0; continue; } break; } return start; }
  class QHash {                          // pixel_hash / pixel_cmp on scaled pixels
    constructor() { this.length = 11; this.count = 0; this.scale = 0; this.table = new Array(11).fill(null); }
    hk(r, g, b) { const s = this.scale; return PIXEL_HASH(r >> s, g >> s, b >> s); }
    insertNode(node, resize, cf) {
      const hv = node.h; let idx = hv % this.length;
      let prev = null, n = this.table[idx];
      for (; n; prev = n, n = n.next) {
        if (n.h === hv) { n.r = node.r; n.g = node.g; n.b = node.b; if (cf) n.value += node.value; else n.value = node.value; return; }
        if (n.h > hv) break;
      }
      node.next = n; if (prev) prev.next = node; else this.table[idx] = node;
      this.count++;
      if (resize) this.resize();
    }
    rehash(cf, newSize) {
      const old = this.table, oldSize = this.length;
      this.table = new Array(newSize).fill(null); this.length = newSize; this.count = 0;
      for (let i = 0; i < oldSize; i++) for (let n = old[i], nn; n; n = nn) { nn = n.next; n.h = this.hk(n.r, n.g, n.b); n.next = null; this.insertNode(n, false, cf); }
    }
    resize() {
      const oldSize = this.length; let newSize = oldSize;
      if (this.count * 3 < this.length) newSize = findPrime(Math.floor(this.length / 2) - 1, -1);
      else if (this.length * 3 < this.count) newSize = findPrime(this.length * 2 + 1, +1);
      if (newSize < 11) newSize = oldSize;
      if (newSize !== oldSize) this.rehash(false, newSize);
    }
    insertOrCount(r, g, b) {             // hashtable_insert_or_update_computed(new_count_func, exists_count_func)
      const hv = this.hk(r, g, b), idx = hv % this.length;
      let prev = null, n = this.table[idx];
      for (; n; prev = n, n = n.next) { if (n.h === hv) { n.value += 1; return; } if (n.h > hv) break; }
      const t = { r, g, b, h: hv, value: 1, next: n };
      if (prev) prev.next = t; else this.table[idx] = t;
      this.count++;
      this.resize();
    }
  }
  function pilMedianCut(px, n, nQuant) {  // px: Uint8Array RGB x n -> { pal: [[r,g,b]], idx: Uint32Array }
    const h = new QHash();
    for (let i = 0; i < n; i++) {
      h.insertOrCount(px[3 * i], px[3 * i + 1], px[3 * i + 2]);
      while (h.count > 65536) { h.scale++; h.rehash(true, h.length); }
    }
    const s = h.scale;
    // hash_to_list: PixelList nodes prepended per axis, in bucket order
    const hl = [null, null, null];
    for (let x = 0; x < h.length; x++) for (let nd = h.table[x]; nd; nd = nd.next) {
      const p = { v: [nd.r >> s, nd.g >> s, nd.b >> s], count: nd.value, flag: 0, next: [null, null, null], prev: [null, null, null] };
      for (let i = 0; i < 3; i++) { p.next[i] = hl[i]; p.prev[i] = null; if (hl[i]) hl[i].prev[i] = p; hl[i] = p; }
    }
    function msort(head, i) {
      if (!head || !head.next[i]) { if (head) { head.next[i] = null; head.prev[i] = null; } return head; }
      let c = head, t = head;
      while (c && t) { c = c.next[i]; t = t.next[i] ? t.next[i].next[i] : null; }
      if (c) { if (c.prev[i]) c.prev[i].next[i] = null; c.prev[i] = null; }
      let a = msort(head, i), b = msort(c, i);
      head = null; let p = null;
      while (a && b) {
        if (a.v[i] > b.v[i]) { c = a; a = a.next[i]; } else { c = b; b = b.next[i]; }
        c.prev[i] = p; c.next[i] = null; if (p) p.next[i] = c; p = c; if (!head) head = c;
      }
      if (a) { c.next[i] = a; a.prev[i] = c; } else if (b) { c.next[i] = b; b.prev[i] = c; }
      return head;
    }
    for (let i = 0; i < 3; i++) hl[i] = msort(hl[i], i);
    // median_cut with QuantHeap (max-heap on pixelCount, 1-based)
    const root = { l: null, r: null, head: [hl[0], hl[1], hl[2]], tail: [null, null, null], axis: -1, volume: -1, pixelCount: n };
    for (let i = 0; i < 3; i++) { let t = hl[i]; while (t && t.next[i]) t = t.next[i]; root.tail[i] = t; }
    const heap = [null]; let hc = 0;
    const cmp = (a, b) => (a.pixelCount | 0) - (b.pixelCount | 0);
    const hadd = v => { let k = ++hc; while (k !== 1) { if (cmp(v, heap[k >> 1]) <= 0) break; heap[k] = heap[k >> 1]; k >>= 1; } heap[k] = v; };
    const hrem = () => {
      if (!hc) return null;
      const r = heap[1], v = heap[hc--]; let k = 1, l;
      for (; k * 2 <= hc; k = l) { l = k * 2; if (l < hc && cmp(heap[l], heap[l + 1]) < 0) l++; if (cmp(v, heap[l]) > 0) break; heap[k] = heap[l]; }
      heap[k] = v; return r;
    };
    const volume = b => {
      if (b.volume >= 0) return b.volume;
      if (!b.head[0]) b.volume = 0;
      else b.volume = (b.head[0].v[0] - b.tail[0].v[0] + 1) * (b.head[1].v[1] - b.tail[1].v[1] + 1) * (b.head[2].v[2] - b.tail[2].v[2] + 1);
      return b.volume;
    };
    function split(node) {
      const f = [(node.head[0].v[0] - node.tail[0].v[0]) * 77, (node.head[1].v[1] - node.tail[1].v[1]) * 150, (node.head[2].v[2] - node.tail[2].v[2]) * 29];
      let best = f[0], axis = 0;
      for (let i = 1; i < 3; i++) if (best < f[i]) { best = f[i]; axis = i; }
      node.axis = axis;
      // splitlists
      const nCount = [0, 0]; let nRight = 0, left = 0, c;
      for (c = node.head[axis]; c;) { left += c.count; nCount[0] += c.count; c.flag = 0; c = c.next[axis]; if (left * 2 > node.pixelCount) break; }
      if (c) {
        const sv = c.prev[axis].v[axis];
        for (; c; c = c.next[axis]) { if (sv !== c.v[axis]) break; c.flag = 0; nCount[0] += c.count; }
      }
      for (; c; c = c.next[axis]) { c.flag = 1; nRight++; nCount[1] += c.count; }
      if (!nRight) {
        const sv = node.tail[axis].v[axis];
        for (c = node.tail[axis]; c; c = c.prev[axis]) { if (sv !== c.v[axis]) break; c.flag = 1; nRight++; nCount[0] -= c.count; nCount[1] += c.count; }
      }
      const nh = [[null, null, null], [null, null, null]], nt = [[null, null, null], [null, null, null]];
      for (let i = 0; i < 3; i++) {
        let l = null, r = null;
        for (let cc = node.head[i], nn; cc; cc = nn) {
          nn = cc.next[i];
          if (cc.flag) { if (r) r.next[i] = cc; else nh[1][i] = cc; cc.prev[i] = r; r = cc; }
          else { if (l) l.next[i] = cc; else nh[0][i] = cc; cc.prev[i] = l; l = cc; }
        }
        if (l) l.next[i] = null; if (r) r.next[i] = null;
        nt[0][i] = l; nt[1][i] = r;
      }
      const L = { l: null, r: null, head: nh[0], tail: nt[0], axis: -1, volume: -1, pixelCount: nCount[0] };
      const R = { l: null, r: null, head: nh[1], tail: nt[1], axis: -1, volume: -1, pixelCount: nCount[1] };
      node.head = [null, null, null]; node.tail = [null, null, null];
      node.l = L; node.r = R;
    }
    hadd(root);
    let np = nQuant;
    outer: while (--np) {
      let th;
      do { th = hrem(); if (!th) break outer; } while (volume(th) === 1);
      split(th); hadd(th.l); hadd(th.r);
    }
    // annotate_hash_table -> box per scaled hash
    const boxOf = new Map(); let nBox = 0;
    (function annotate(nd) {
      if (nd.l && nd.r) { annotate(nd.l); annotate(nd.r); return; }
      for (let p = nd.head[0]; p; p = p.next[0]) boxOf.set(PIXEL_HASH(p.v[0], p.v[1], p.v[2]), nBox);
      if (nd.head[0]) nBox++;
    })(root);
    const sumR = new Float64Array(nBox), sumG = new Float64Array(nBox), sumB = new Float64Array(nBox), cnt = new Float64Array(nBox);
    const boxAt = new Uint32Array(n);
    for (let i = 0; i < n; i++) {
      const b = boxOf.get(PIXEL_HASH(px[3 * i] >> s, px[3 * i + 1] >> s, px[3 * i + 2] >> s));
      boxAt[i] = b; sumR[b] += px[3 * i]; sumG[b] += px[3 * i + 1]; sumB[b] += px[3 * i + 2]; cnt[b]++;
    }
    const pal = [];
    for (let i = 0; i < nBox; i++) pal.push([Math.trunc(.5 + sumR[i] / cnt[i]) & 255, Math.trunc(.5 + sumG[i] / cnt[i]) & 255, Math.trunc(.5 + sumB[i] / cnt[i]) & 255]);
    const dist = (p, r, g, b) => (p[0] - r) * (p[0] - r) + (p[1] - g) * (p[1] - g) + (p[2] - b) * (p[2] - b);
    const avgDist = new Uint32Array(nBox * nBox), sortKey = new Uint32Array(nBox * nBox);
    for (let i = 0; i < nBox; i++) for (let j = 0; j < i; j++) avgDist[j * nBox + i] = avgDist[i * nBox + j] = dist(pal[i], pal[j][0], pal[j][1], pal[j][2]);
    for (let i = 0; i < nBox; i++) {
      const js = Array.from({ length: nBox }, (_, j) => j);
      js.sort((a, b) => avgDist[i * nBox + a] - avgDist[i * nBox + b] || a - b);
      for (let j = 0; j < nBox; j++) sortKey[i * nBox + j] = js[j];
    }
    const idx = new Uint32Array(n), seen = new Map();
    for (let i = 0; i < n; i++) {
      const r = px[3 * i], g = px[3 * i + 1], b = px[3 * i + 2], key = (r << 16) | (g << 8) | b;
      const hit = seen.get(key);
      if (hit !== undefined) { idx[i] = hit; continue; }
      const pv = boxAt[i];
      let initial = dist(pal[pv], r, g, b), bestdist = initial, best = pv;
      initial = initial * 4;
      for (let j = 0; j < nBox; j++) {
        const k = sortKey[pv * nBox + j];
        if (avgDist[pv * nBox + k] <= initial) { const d = dist(pal[k], r, g, b); if (d < bestdist) { bestdist = d; best = k; } }
        else break;
      }
      idx[i] = best; seen.set(key, best);
    }
    return { pal, idx };
  }
  function paletteCut(im, colours) {     // bldrender.palette_cut (dither is never set by a style)
    const a = im.d, ops = [];
    for (let k = 0; k < a.length; k += 4) if (a[k + 3] >= 128) ops.push(k);
    if (!ops.length) return im;
    const uniq = new Set(); for (const k of ops) uniq.add((a[k] << 16) | (a[k + 1] << 8) | a[k + 2]);
    if (uniq.size <= colours) return im;
    const px = new Uint8Array(ops.length * 3);
    ops.forEach((k, i) => { px[3 * i] = a[k]; px[3 * i + 1] = a[k + 1]; px[3 * i + 2] = a[k + 2]; });
    const q = pilMedianCut(px, ops.length, colours);
    const o = { w: im.w, h: im.h, d: new Uint8Array(a) };
    ops.forEach((k, i) => { const p = q.pal[q.idx[i]]; o.d[k] = p[0]; o.d[k + 1] = p[1]; o.d[k + 2] = p[2]; });
    return o;
  }

  // ------------------------------------------------------------------------------------------------ PIL resize
  // Image.resize(size, LANCZOS | BICUBIC, reducing_gap=None) on RGBA: RGBA -> RGBa (MULDIV255), Resample.c two
  // passes with 22-bit fixed-point coefficients, RGBa -> RGBA.
  const bicubic = x => { const a = -0.5; if (x < 0) x = -x; if (x < 1) return ((a + 2.0) * x - (a + 3.0)) * x * x + 1; if (x < 2) return (((x - 5) * x + 8) * x - 4) * a; return 0.0; };
  const sinc = x => { if (x === 0.0) return 1.0; x = x * Math.PI; return Math.sin(x) / x; };
  const lanczos = x => (-3.0 <= x && x < 3.0) ? sinc(x) * sinc(x / 3) : 0.0;
  const FILTERS = { LANCZOS: [lanczos, 3.0], BICUBIC: [bicubic, 2.0] };
  const PREC = 22;
  function coeffs(inSize, in0, in1, outSize, filt) {
    const [fn, sup] = filt;
    let scale = (in1 - in0) / outSize, fs = scale; if (fs < 1.0) fs = 1.0;
    const support = sup * fs, ksize = Math.ceil(support) * 2 + 1;
    const kk = new Float64Array(outSize * ksize), bounds = new Int32Array(outSize * 2);
    const inv = 1.0 / fs;
    for (let xx = 0; xx < outSize; xx++) {
      const center = in0 + (xx + 0.5) * scale; let ww = 0.0;
      let xmin = Math.trunc(center - support + 0.5); if (xmin < 0) xmin = 0;
      let xmax = Math.trunc(center + support + 0.5); if (xmax > inSize) xmax = inSize;
      xmax -= xmin;
      for (let x = 0; x < xmax; x++) { const w = fn((x + xmin - center + 0.5) * inv); kk[xx * ksize + x] = w; ww += w; }
      if (ww !== 0.0) for (let x = 0; x < xmax; x++) kk[xx * ksize + x] /= ww;
      bounds[2 * xx] = xmin; bounds[2 * xx + 1] = xmax;
    }
    const ik = new Int32Array(outSize * ksize);
    for (let k = 0; k < ik.length; k++) ik[k] = kk[k] < 0 ? Math.trunc(-0.5 + kk[k] * (1 << PREC)) : Math.trunc(0.5 + kk[k] * (1 << PREC));
    return { ksize, bounds, k: ik };
  }
  const clip8 = v => { const i = v >> PREC; return i < 0 ? 0 : i > 255 ? 255 : i; };
  function pilResize(im, w, h, filter) {
    if (im.w === w && im.h === h) return { w, h, d: new Uint8Array(im.d) };
    const filt = FILTERS[filter];
    // RGBA -> RGBa
    const src = new Int32Array(im.w * im.h * 4);
    for (let k = 0; k < im.w * im.h; k++) {
      const a = im.d[4 * k + 3];
      for (let c = 0; c < 3; c++) { const t = im.d[4 * k + c] * a + 128; src[4 * k + c] = ((t >> 8) + t) >> 8; }
      src[4 * k + 3] = a;
    }
    const cv = coeffs(im.h, 0, im.h, h, filt);
    const yFirst = cv.bounds[0], yLast = cv.bounds[h * 2 - 2] + cv.bounds[h * 2 - 1];
    let cur = src, cw = im.w, chh = im.h;
    const needH = w !== im.w, needV = h !== im.h;
    if (needH) {
      const ch = coeffs(im.w, 0, im.w, w, filt);
      for (let i = 0; i < h; i++) cv.bounds[2 * i] -= yFirst;
      const th = yLast - yFirst, tmp = new Int32Array(w * th * 4);
      for (let yy = 0; yy < th; yy++) for (let xx = 0; xx < w; xx++) {
        const xmin = ch.bounds[2 * xx], xmax = ch.bounds[2 * xx + 1], ko = xx * ch.ksize;
        let s0 = 1 << (PREC - 1), s1 = s0, s2 = s0, s3 = s0;
        for (let x = 0; x < xmax; x++) {
          const k = ch.k[ko + x], p = ((yy + yFirst) * im.w + x + xmin) * 4;
          s0 += cur[p] * k; s1 += cur[p + 1] * k; s2 += cur[p + 2] * k; s3 += cur[p + 3] * k;
        }
        const o = (yy * w + xx) * 4; tmp[o] = clip8(s0); tmp[o + 1] = clip8(s1); tmp[o + 2] = clip8(s2); tmp[o + 3] = clip8(s3);
      }
      cur = tmp; cw = w; chh = th;
    }
    let out = cur;
    if (needV) {
      out = new Int32Array(cw * h * 4);
      for (let yy = 0; yy < h; yy++) {
        const ymin = cv.bounds[2 * yy], ymax = cv.bounds[2 * yy + 1], ko = yy * cv.ksize;
        for (let xx = 0; xx < cw; xx++) {
          let s0 = 1 << (PREC - 1), s1 = s0, s2 = s0, s3 = s0;
          for (let y = 0; y < ymax; y++) {
            const k = cv.k[ko + y], p = ((y + ymin) * cw + xx) * 4;
            s0 += cur[p] * k; s1 += cur[p + 1] * k; s2 += cur[p + 2] * k; s3 += cur[p + 3] * k;
          }
          const o = (yy * cw + xx) * 4; out[o] = clip8(s0); out[o + 1] = clip8(s1); out[o + 2] = clip8(s2); out[o + 3] = clip8(s3);
        }
      }
    }
    // RGBa -> RGBA
    const res = newImg(w, h);
    for (let k = 0; k < w * h; k++) {
      const a = out[4 * k + 3];
      for (let c = 0; c < 3; c++) {
        let v = out[4 * k + c];
        if (a !== 255 && a !== 0) { v = Math.trunc((255 * v) / a); v = v <= 0 ? 0 : v < 256 ? v : 255; }
        res.d[4 * k + c] = v;
      }
      res.d[4 * k + 3] = a;
    }
    return res;
  }

  // ================================================================================================ OBJ (bldrender)
  // folder = { get(relPath) -> Promise<Uint8Array|null> } relative to the models folder, '/' separated
  const joinRel = (base, name) => {
    const parts = (base ? base.split('/') : []).concat(String(name).split(/[\\/]+/));
    const out = [];
    for (const p of parts) { if (!p || p === '.') continue; if (p === '..') { if (!out.length) return null; out.pop(); } else out.push(p); }
    return out.join('/');
  };
  const dirOf = rel => rel.includes('/') ? rel.slice(0, rel.lastIndexOf('/')) : '';
  async function readMtl(folder, rel, texCache) {
    const mats = new Map(); let cur = null;
    const data = rel === null ? null : await folder.get(rel);
    if (!data) return mats;
    const base = dirOf(rel);
    for (const ln of pyLines(utf8Dec().decode(data))) {
      const p = pySplit(ln);
      if (!p.length || p[0].startsWith('#')) continue;
      const k = p[0].toLowerCase();
      if (k === 'newmtl') { const nm = p.slice(1).join(' '); if (!mats.has(nm)) mats.set(nm, { kd: [0.8, 0.8, 0.8], tex: null }); cur = mats.get(nm); }
      else if (cur === null) continue;
      else if (k === 'kd' && p.length >= 4) cur.kd = p.slice(1, 4).map(pyFloat);
      else if (k === 'map_kd' && p.length >= 2) {
        const name = p[p.length - 1], tp = joinRel(base, name);
        const tb = tp === null ? null : await folder.get(tp);
        if (tb) {
          let tex = texCache.get(tp);
          if (!tex) {
            const im = await decodeImage(tb);
            const f = new Float32Array(im.w * im.h * 3);
            for (let q = 0; q < f.length; q++) f[q] = fr(im.rgb[q] / 255);
            tex = { w: im.w, h: im.h, d: f };
            // task sc4web (bldrender task sc4conv): texture alpha, kept only when some texel is below 128
            if (im.a && im.a.some(x => x < 128)) {
              const al = new Float32Array(im.w * im.h * 3);           // one channel, laid out like tex.d (texIndex)
              for (let q = 0; q < im.w * im.h; q++) al[3 * q] = fr(im.a[q] / 255);
              tex.alpha = { w: im.w, h: im.h, d: al };
            }
            texCache.set(tp, tex);
          }
          cur.tex = tex; cur.tex_file = name;
          if (tex.alpha) cur.alpha = tex.alpha; else delete cur.alpha;
        }
      }
    }
    return mats;
  }
  async function loadObj(folder, rel) {
    const data = await folder.get(rel);
    if (!data) throw new BldError(rel + ': not found');
    const V = [], VT = [], tris = [], uvs = [], has = [], mid = [], slots = [];
    let curSlot = -1;
    const mats = new Map(), texCache = new Map();
    const matNames = ['_default'], matList = [{ kd: [0.8, 0.8, 0.8], tex: null, name: '_default' }];
    let cur = 0;
    const base = dirOf(rel);
    for (const ln of pyLines(utf8Dec().decode(data))) {
      const p = pySplit(ln);
      if (!p.length || p[0].startsWith('#')) continue;
      const k = p[0];
      if (k === 'v') V.push(p.slice(1, 4).map(pyFloat));
      else if (k === 'vt') VT.push(p.length >= 3 ? p.slice(1, 3).map(pyFloat) : [pyFloat(p[1]), 0.0]);
      else if (k === 'mtllib') { for (const name of p.slice(1)) { const m = await readMtl(folder, joinRel(base, name), texCache); for (const [a, b] of m) mats.set(a, b); } }
      else if (k === 'usemtl') {
        const name = p.slice(1).join(' ');
        if (!matNames.includes(name)) {
          const m = Object.assign({}, mats.get(name) || { kd: [0.8, 0.8, 0.8], tex: null }); m.name = name;
          matNames.push(name); matList.push(m);
        }
        cur = matNames.indexOf(name);
      } else if (k === 'g' || k === 'o') {
        // task sc4web (bldrender task sc4conv): faces in a group / object named sc3slot<r> are drawn in slot r only
        const nm = p.slice(1).join(' ').toLowerCase();
        curSlot = nm.startsWith('sc3slot') && nm.length >= 8 && '0123'.includes(nm[7]) ? +nm[7] : -1;
      } else if (k === 'f') {
        const idx = [];
        for (const t of p.slice(1)) {
          const a = t.split('/');
          let vi = pyInt(a[0]); vi = vi > 0 ? vi - 1 : V.length + vi;
          let ti = null;
          if (a.length > 1 && a[1]) { ti = pyInt(a[1]); ti = ti > 0 ? ti - 1 : VT.length + ti; }
          idx.push([vi, ti]);
        }
        for (let j = 1; j < idx.length - 1; j++) {
          const tri = [idx[0], idx[j], idx[j + 1]];
          tris.push(tri.map(([a]) => { const v = V.at(a); if (!v) throw new BldError('face index out of range'); return v.slice(0, 3); }));
          const ok = tri.every(([, b]) => b !== null);
          uvs.push(ok ? tri.map(([, b]) => { const v = VT.at(b); if (!v) throw new BldError('uv index out of range'); return v; }) : [[0, 0], [0, 0], [0, 0]]);
          has.push(ok); mid.push(cur); slots.push(curSlot);
        }
      }
    }
    if (!tris.length) throw new BldError(rel + ': no faces');
    const N = tris.length, tri = new Float64Array(N * 9), uv = new Float64Array(N * 6);
    for (let i = 0; i < N; i++) for (let j = 0; j < 3; j++) {
      for (let c = 0; c < 3; c++) tri[i * 9 + j * 3 + c] = tris[i][j][c];
      uv[i * 6 + j * 2] = uvs[i][j][0]; uv[i * 6 + j * 2 + 1] = uvs[i][j][1];
    }
    return { n: N, tri, uv, has_uv: Uint8Array.from(has.map(Number)), mat: Int32Array.from(mid), mats: matList, slot: Int8Array.from(slots) };
  }
  function slotMesh(mesh, r) {           // bldrender.slot_mesh: the faces drawn in rotation slot r
    const s = mesh.slot;
    if (!s || !s.some(x => x >= 0)) return mesh;
    const keep = []; for (let i = 0; i < mesh.n; i++) if (s[i] < 0 || s[i] === r) keep.push(i);
    const N = keep.length, tri = new Float64Array(N * 9), uv = new Float64Array(N * 6), hu = new Uint8Array(N), mt = new Int32Array(N), sl = new Int8Array(N);
    keep.forEach((i, j) => { tri.set(mesh.tri.subarray(9 * i, 9 * i + 9), 9 * j); uv.set(mesh.uv.subarray(6 * i, 6 * i + 6), 6 * j); hu[j] = mesh.has_uv[i]; mt[j] = mesh.mat[i]; sl[j] = s[i]; });
    return Object.assign({}, mesh, { n: N, tri, uv, has_uv: hu, mat: mt, slot: sl });
  }
  function place(mesh, n, cellM, scale, rotDeg) {
    const N = mesh.n, P = N * 3, sc = scale;
    const a = rotDeg * (Math.PI / 180), c = Math.cos(a), s = Math.sin(a);
    const X = new Float64Array(P), Z = new Float64Array(P), Y = new Float64Array(P);
    for (let k = 0; k < P; k++) {
      const p0 = mesh.tri[3 * k] * sc, p1 = mesh.tri[3 * k + 1] * sc, p2 = mesh.tri[3 * k + 2] * sc;
      X[k] = p0 * c + p2 * s; Z[k] = -p0 * s + p2 * c; Y[k] = p1;
    }
    const mn = a_ => { let m = a_[0]; for (let k = 1; k < a_.length; k++) if (a_[k] < m || (m !== m)) m = a_[k]; return m; };
    const mx = a_ => { let m = a_[0]; for (let k = 1; k < a_.length; k++) if (a_[k] > m || (m !== m)) m = a_[k]; return m; };
    const x0 = mn(X), x1 = mx(X), z0 = mn(Z), z1 = mx(Z), y0 = mn(Y), y1 = mx(Y);
    const t = new Float64Array(P * 3);
    for (let k = 0; k < P; k++) {
      t[3 * k] = (X[k] - (x0 + x1) / 2.0) / cellM + n / 2.0;
      t[3 * k + 1] = (Z[k] - (z0 + z1) / 2.0) / cellM + n / 2.0;
      t[3 * k + 2] = (Y[k] - y0) / cellM;
    }
    const out = Object.assign({}, mesh, { tri: t });
    const info = { size_m: [x1 - x0, y1 - y0, z1 - z0], lot_m: n * cellM, fits: (x1 - x0 <= n * cellM + 1e-6 && z1 - z0 <= n * cellM + 1e-6) };
    return [out, info];
  }

  // ================================================================================================ raster (bldrender)
  function rotPts(src, n, r) {           // _rot_slot on an array of (u, v, h) triples -> new Float64Array
    const out = new Float64Array(src);
    for (let k = 0; k < out.length; k += 3) {
      let u = out[k], v = out[k + 1];
      for (let q = 0; q < (r % 4 + 4) % 4; q++) { const nu = v, nv = n - u; u = nu; v = nv; }
      out[k] = u; out[k + 1] = v;
    }
    return out;
  }
  function rasterize(sx, sy, dep, nt, w, h, withBary, zmin) {   // sx, sy, dep: Float64Array nt*3; zmin: depth peeling
    const zb = new Float64Array(w * h).fill(Infinity);
    const ib = withBary ? new Int32Array(w * h).fill(-1) : null;
    const bb = withBary ? new Float32Array(w * h * 3) : null;
    for (let k = 0; k < nt; k++) {
      const x0 = sx[3 * k], x1 = sx[3 * k + 1], x2 = sx[3 * k + 2], y0 = sy[3 * k], y1 = sy[3 * k + 1], y2 = sy[3 * k + 2];
      const area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0);
      if (Math.abs(area) < 1e-12) continue;
      const i0 = Math.max(Math.floor(Math.min(x0, x1, x2) - 0.5), 0), i1 = Math.min(Math.ceil(Math.max(x0, x1, x2) - 0.5), w - 1);
      const j0 = Math.max(Math.floor(Math.min(y0, y1, y2) - 0.5), 0), j1 = Math.min(Math.ceil(Math.max(y0, y1, y2) - 0.5), h - 1);
      if (i0 > i1 || j0 > j1) continue;
      const d0 = dep[3 * k], d1 = dep[3 * k + 1], d2 = dep[3 * k + 2];
      for (let j = j0; j <= j1; j++) {
        const py = j + 0.5, row = j * w;
        for (let i = i0; i <= i1; i++) {
          const px = i + 0.5;
          const w0 = ((x1 - px) * (y2 - py) - (x2 - px) * (y1 - py)) / area;
          const w1 = ((x2 - px) * (y0 - py) - (x0 - px) * (y2 - py)) / area;
          const w2 = 1.0 - w0 - w1;
          if (!(w0 >= -1e-9 && w1 >= -1e-9 && w2 >= -1e-9)) continue;
          const d = w0 * d0 + w1 * d1 + w2 * d2;
          const q = row + i;
          if (!(d < zb[q])) continue;
          if (zmin && !(d > zmin[q] + 1e-7)) continue;
          zb[q] = d;
          if (withBary) { ib[q] = k; bb[3 * q] = w0; bb[3 * q + 1] = w1; bb[3 * q + 2] = w2; }
        }
      }
    }
    return { ib, bb, zb };
  }
  function faceNormals(t, nt) {          // (u, v, h) triangles -> unit normals in (v, u, h)
    const out = new Float64Array(nt * 3);
    for (let k = 0; k < nt; k++) {
      const o = 9 * k;
      const p0v = t[o + 1], p0u = t[o], p0h = t[o + 2];
      const a0 = t[o + 4] - p0v, a1 = t[o + 3] - p0u, a2 = t[o + 5] - p0h;
      const b0 = t[o + 7] - p0v, b1 = t[o + 6] - p0u, b2 = t[o + 8] - p0h;
      const c0 = a1 * b2 - a2 * b1, c1 = a2 * b0 - a0 * b2, c2 = a0 * b1 - a1 * b0;
      let ln = Math.sqrt((c0 * c0 + c1 * c1) + c2 * c2); if (ln === 0) ln = 1;
      out[3 * k] = c0 / ln; out[3 * k + 1] = c1 / ln; out[3 * k + 2] = c2 / ln;
    }
    return out;
  }
  function shadowMap(t, nt, res = 0.004) {   // t: model triangles of this slot (u, v, h); along SUN
    const a = SM_A, b = SM_B, L = SUN;
    const NP = nt * 3, pa = new Float64Array(NP), pb = new Float64Array(NP), pl = new Float64Array(NP);
    for (let k = 0; k < NP; k++) {
      const v = t[3 * k + 1], u = t[3 * k], h = t[3 * k + 2];
      pa[k] = mm3(v, u, h, a); pb[k] = mm3(v, u, h, b); pl[k] = mm3(v, u, h, L);
    }
    let pamin = Infinity, pamax = -Infinity, pbmin = Infinity, pbmax = -Infinity;
    for (let k = 0; k < NP; k++) { pamin = Math.min(pamin, pa[k]); pamax = Math.max(pamax, pa[k]); pbmin = Math.min(pbmin, pb[k]); pbmax = Math.max(pbmax, pb[k]); }
    for (;;) {
      const amin = pamin - 4 * res, bmin = pbmin - 4 * res;
      const W = Math.ceil((pamax - amin) / res) + 8, H = Math.ceil((pbmax - bmin) / res) + 8;
      if (W * H > 60e6) { res *= Math.sqrt(W * H / 60e6); continue; }
      const sx = new Float64Array(NP), sy = new Float64Array(NP), dp = new Float64Array(NP);
      for (let k = 0; k < NP; k++) { sx[k] = (pa[k] - amin) / res; sy[k] = (pb[k] - bmin) / res; dp[k] = -pl[k]; }
      const { zb } = rasterize(sx, sy, dp, nt, W, H, false);
      return { amin, bmin, res, zb, W, H };
    }
  }
  function inShadow(u, v, h, sm, bias) {
    const pa = mm3(v, u, h, SM_A), pb = mm3(v, u, h, SM_B), pl = mm3(v, u, h, SUN);
    let i = Math.trunc((pa - sm.amin) / sm.res), j = Math.trunc((pb - sm.bmin) / sm.res);
    i = i < 0 ? 0 : i > sm.W - 1 ? sm.W - 1 : i; j = j < 0 ? 0 : j > sm.H - 1 ? sm.H - 1 : j;
    return sm.zb[j * sm.W + i] < (-pl - bias);
  }
  // _sample_tex: nearest texel, wraps. -> index of the texel's R in tex.d
  function texIndex(tex, u, v) {
    let mu = u % 1.0; if (mu !== 0 && mu < 0) mu += 1.0;
    let mv = v % 1.0; if (mv !== 0 && mv < 0) mv += 1.0;
    const x = mu * (tex.w - 1), y = (1.0 - mv) * (tex.h - 1);
    let yi = rint(y), xi = rint(x);
    yi = yi < 0 ? 0 : yi > tex.h - 1 ? tex.h - 1 : yi; xi = xi < 0 ? 0 : xi > tex.w - 1 ? tex.w - 1 : xi;
    return (yi * tex.w + xi) * 3;
  }
  // _hash_noise on an integer voxel: int64 arithmetic in 32-bit halves (bits 0..15 of the result are all that count)
  function mulHi32(a, b) {               // high 32 bits of the 64-bit product of two uint32
    const a0 = a & 0xFFFF, a1 = a >>> 16, b0 = b & 0xFFFF, b1 = b >>> 16;
    const t = a0 * b0, m1 = a1 * b0 + Math.floor(t / 65536), m2 = a0 * b1 + (m1 % 65536);
    return (a1 * b1 + Math.floor(m1 / 65536) + Math.floor(m2 / 65536)) >>> 0;
  }
  function mul64(hi, lo, K) { return [(Math.imul(hi, K) + mulHi32(lo, K)) >>> 0, Math.imul(lo, K) >>> 0]; }
  const seedTerm = new Map();
  function hashNoise(q0, q1, q2, seed) {
    // q: integers (float), possibly negative
    const h0 = mul64(q0 < 0 ? 0xFFFFFFFF : 0, q0 >>> 0, 73856093);
    const h1 = mul64(q1 < 0 ? 0xFFFFFFFF : 0, q1 >>> 0, 19349663);
    const h2 = mul64(q2 < 0 ? 0xFFFFFFFF : 0, q2 >>> 0, 83492791);
    let st = seedTerm.get(seed);
    if (!st) { const s = BigInt.asUintN(64, BigInt(seed) * 2654435761n); st = [Number(s >> 32n) >>> 0, Number(s & 0xFFFFFFFFn) >>> 0]; seedTerm.set(seed, st); }
    let hi = (h0[0] ^ h1[0] ^ h2[0] ^ st[0]) >>> 0, lo = (h0[1] ^ h1[1] ^ h2[1] ^ st[1]) >>> 0;
    // h = (h ^ (h >> 13)) * 1274126177   (arithmetic shift)
    let shi = hi >> 13, slo = ((lo >>> 13) | (hi << 19)) >>> 0;
    const m = mul64((hi ^ shi) >>> 0, (lo ^ slo) >>> 0, 1274126177); hi = m[0]; lo = m[1];
    // h = h ^ (h >> 16)
    slo = ((lo >>> 16) | (hi << 16)) >>> 0;
    lo = (lo ^ slo) >>> 0;
    return fr(fr((lo & 0xFFFF) / 32767.5) - 1.0);
  }
  const CORNERS = [[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0], [0, 0, 1], [1, 0, 1], [0, 1, 1], [1, 1, 1]];
  function valueNoise(p0, p1, p2, freq, seed) {   // one point -> float32
    const q0 = p0 * freq, q1 = p1 * freq, q2 = p2 * freq;
    const i0 = Math.floor(q0), i1 = Math.floor(q1), i2 = Math.floor(q2);
    let f0 = q0 - i0, f1 = q1 - i1, f2 = q2 - i2;
    f0 = f0 * f0 * (3 - 2 * f0); f1 = f1 * f1 * (3 - 2 * f1); f2 = f2 * f2 * (3 - 2 * f2);
    let out = 0;
    for (const o of CORNERS) {
      const w = ((o[0] ? f0 : 1 - f0) * (o[1] ? f1 : 1 - f1)) * (o[2] ? f2 : 1 - f2);
      const c0 = Math.floor(((i0 + o[0]) + 0.5) * 1.0), c1 = Math.floor(((i1 + o[1]) + 0.5) * 1.0), c2 = Math.floor(((i2 + o[2]) + 0.5) * 1.0);
      out = fr(out + w * hashNoise(c0, c1, c2, seed));
    }
    return out;
  }
  const F065 = fr(0.65), F035 = fr(0.35);
  const grain = (p0, p1, p2, W, seed) => fr(fr(F065 * valueNoise(p0, p1, p2, W / 6.0, seed)) + fr(F035 * valueNoise(p0, p1, p2, W / 2.0, seed + 1)));

  // grass_texture(size 256, seed 7): numpy's PCG64 (default_rng(7) state below), bilinear octaves, normalised by the
  // array's mean / std (fixed values: the seed is fixed; checked against numpy by GRASS_SHA)
  const PCG_STATE = 208745520555909116978795849195383758904n, PCG_INC = 261136684632268670825940853076396136793n;
  const PCG_MULT = 0x2360ED051FC65DA44385DF649FCCF645n, M128 = (1n << 128n) - 1n, M64 = (1n << 64n) - 1n;
  const GRASS_MEAN = 0.494350159431553, GRASS_STD = 0.1248775015292277;
  let GRASS_NORM = null;
  function grassNorm() {
    if (GRASS_NORM) return GRASS_NORM;
    let s = PCG_STATE;
    const rnd = () => {
      s = (s * PCG_MULT + PCG_INC) & M128;
      const x = ((s >> 64n) ^ s) & M64, r = Number(s >> 122n);
      const v = ((x >> BigInt(r)) | (x << BigInt((64 - r) & 63))) & M64;
      return Number(v >> 11n) * (1.0 / 9007199254740992.0);
    };
    const size = 256, out = new Float64Array(size * size);
    for (const [cells, wgt] of [[8, 0.45], [32, 0.30]]) {
      const C = cells + 1, c = new Float64Array(C * C);
      for (let y = 0; y < cells; y++) for (let x = 0; x < cells; x++) c[y * C + x] = rnd();
      for (let x = 0; x < cells; x++) c[cells * C + x] = c[x];            // c = concat([c, c[:1]], 0)
      for (let y = 0; y < C; y++) c[y * C + cells] = c[y * C];            // c = concat([c, c[:, :1]], 1)
      const step = cells / size, ti = new Int32Array(size), tf = new Float64Array(size);
      for (let k = 0; k < size; k++) { const t = k * step; ti[k] = Math.trunc(t); tf[k] = t - ti[k]; }
      const row = new Float64Array(size * C);
      for (let a = 0; a < size; a++) for (let x = 0; x < C; x++) row[a * C + x] = c[ti[a] * C + x] * (1 - tf[a]) + c[(ti[a] + 1) * C + x] * tf[a];
      for (let a = 0; a < size; a++) for (let b = 0; b < size; b++)
        out[a * size + b] += wgt * (row[a * C + ti[b]] * (1 - tf[b]) + row[a * C + ti[b] + 1] * tf[b]);
    }
    for (let k = 0; k < size * size; k++) out[k] += 0.25 * rnd();
    const den = GRASS_STD + 1e-9;
    for (let k = 0; k < size * size; k++) out[k] = (out[k] - GRASS_MEAN) / den;
    GRASS_NORM = out;
    return out;
  }
  function grassTexture(base = [0.34, 0.46, 0.27], amp = 0.07) {
    const n = grassNorm(), d = new Float32Array(n.length * 3);
    for (let k = 0; k < n.length; k++) for (let c = 0; c < 3; c++) {
      let v = base[c] + n[k] * amp * (c === 2 ? 0.7 : 1.0);
      v = v < 0 ? 0 : v > 1 ? 1 : v;
      d[3 * k + c] = v;
    }
    return { w: 256, h: 256, d };
  }
  const GRASS_TEXELS_PER_CELL = 90.0;
  function grassArgs(st, z) {
    const g = st.grass;
    if (!g) return null;
    const ks = Object.keys(g).map(Number), c = g[Math.min(z, Math.max(...ks))];
    const lit = st.ambient + (st.light === 'axis' ? st.top : st.diffuse * Math.max(SUN[2], 0));
    return { base: c.map(x => Math.min(x / 255.0 / lit, 1.0)), amp: st.grass_amp !== undefined ? st.grass_amp : 0.07 };
  }
  const LUMA = [fr(0.299), fr(0.587), fr(0.114)];

  function renderFrame(mesh, n, z, r, ss, ground, shadows, groundTex, st) {
    mesh = slotMesh(mesh, r);
    const W = 8 << z;
    const [dx, dy, gtab] = CALIB[z];
    const gpx = pz(gtab, n);
    const g = gpx / (W / 2.0);
    const nm = mesh.n, nt = nm + (ground ? 2 : 0);
    const t0 = new Float64Array(nt * 9);
    t0.set(mesh.tri);
    if (ground) {
      const a = -g, b = n + g, e = -1e-4;
      t0.set([a, a, e, b, a, e, b, b, e, a, a, e, b, b, e, a, b, e], nm * 9);
    }
    const t = rotPts(t0, n, r);
    // screen
    const NP = nt * 3, X = new Float64Array(NP), Y = new Float64Array(NP), dep = new Float64Array(NP);
    let ymin = Infinity;
    for (let k = 0; k < NP; k++) {
      const u = t[3 * k], v = t[3 * k + 1], h = t[3 * k + 2];
      X[k] = (u + v) * W / 2.0; Y[k] = (v - u) * W / 4.0 - h * W * VSCALE;
      dep[k] = v * F[0] + u * F[1] + h * F[2];
      if (Y[k] < ymin || ymin !== ymin) ymin = Y[k];
    }
    const B = Math.floor(n * W / 4) + 1;
    const top = Math.max(Math.ceil(-ymin + 1), Math.floor(n * W / 4));
    const Hh = top + B, Ww = n * W, SW = Ww * ss, SH = Hh * ss;
    const sx = new Float64Array(NP), sy = new Float64Array(NP);
    for (let k = 0; k < NP; k++) { sx[k] = (X[k] + dx) * ss; sy[k] = (Y[k] + top + dy) * ss; }
    const { ib, bb, zb } = rasterize(sx, sy, dep, nt, SW, SH, true);
    // task sc4web (bldrender task sc4conv): a sample whose texel is transparent (alpha < 0.5) takes the next
    // surface behind it, up to PEEL_LAYERS times
    const alphaMats = mesh.mats.filter(m => m.alpha).length;
    for (let layer = 0; layer < (alphaMats ? PEEL_LAYERS : 0); layer++) {
      const hole = new Uint8Array(ib.length); let any = false;
      for (let q = 0; q < ib.length; q++) {
        const id = ib[q];
        if (id < 0 || id >= nm) continue;
        const al = mesh.mats[mesh.mat[id]].alpha;
        if (!al || !mesh.has_uv[id]) continue;
        const o = 6 * id, b0 = bb[3 * q], b1 = bb[3 * q + 1], b2 = bb[3 * q + 2];
        const uu = (mesh.uv[o] * b0 + mesh.uv[o + 2] * b1) + mesh.uv[o + 4] * b2;
        const vv = (mesh.uv[o + 1] * b0 + mesh.uv[o + 3] * b1) + mesh.uv[o + 5] * b2;
        if (al.d[texIndex(al, uu, vv)] < 0.5) { hole[q] = 1; any = true; }
      }
      if (!any) break;
      const zmin = new Float64Array(ib.length).fill(Infinity);
      for (let q = 0; q < ib.length; q++) if (hole[q]) zmin[q] = zb[q];
      const p2 = rasterize(sx, sy, dep, nt, SW, SH, true, zmin);
      for (let q = 0; q < ib.length; q++) if (hole[q]) {
        ib[q] = p2.ib[q]; zb[q] = p2.zb[q];
        bb[3 * q] = p2.bb[3 * q]; bb[3 * q + 1] = p2.bb[3 * q + 1]; bb[3 * q + 2] = p2.bb[3 * q + 2];
      }
    }
    // covered samples in row-major order
    let M = 0; for (let q = 0; q < ib.length; q++) if (ib[q] >= 0) M++;
    const rgb = new Float32Array(SW * SH * 3);
    if (M) {
      const nrmT = faceNormals(t, nt), nrm0T = faceNormals(t0, nt);
      // the 'sun' light with diffuse 0 (the baked styles) is the ambient alone, so no shadow map is needed (light =
      // ambient + 0 * nl with nl >= 0 is the value bldrender gets with its map)
      const sm = shadows && nm > 0 && !(st.light !== 'axis' && st.diffuse === 0) ? shadowMap(t.subarray(0, nm * 9), nm) : null;
      const shadowSun = SUN;
      const sel = new Int32Array(M);
      { let m = 0; for (let q = 0; q < ib.length; q++) if (ib[q] >= 0) sel[m++] = q; }
      const pts = new Float64Array(M * 3), nrm = new Float64Array(M * 3), nrm0 = new Float64Array(M * 3);
      const light = new Float64Array(M), alb = new Float32Array(M * 3), isG = new Uint8Array(M);
      let nModel = 0;
      for (let m = 0; m < M; m++) {
        const q = sel[m], id = ib[q], b0 = bb[3 * q], b1 = bb[3 * q + 1], b2 = bb[3 * q + 2], o = 9 * id;
        for (let c = 0; c < 3; c++) pts[3 * m + c] = (t[o + c] * b0 + t[o + 3 + c] * b1) + t[o + 6 + c] * b2;
        let n0 = nrmT[3 * id], n1 = nrmT[3 * id + 1], n2 = nrmT[3 * id + 2];
        let m0 = nrm0T[3 * id], m1 = nrm0T[3 * id + 1], m2 = nrm0T[3 * id + 2];
        if (mm3(n0, n1, n2, F) > 0) { n0 *= -1; n1 *= -1; n2 *= -1; m0 *= -1; m1 *= -1; m2 *= -1; }
        nrm[3 * m] = n0; nrm[3 * m + 1] = n1; nrm[3 * m + 2] = n2; nrm0[3 * m] = m0; nrm0[3 * m + 1] = m1; nrm0[3 * m + 2] = m2;
        isG[m] = id >= nm ? 1 : 0;
        if (!isG[m]) nModel++;
        let sh = false;
        if (sm) {
          sh = inShadow(pts[3 * m], pts[3 * m + 1], pts[3 * m + 2], sm, 0.02);
          if (st.light === 'axis') sh = sh && mm3(n0, n1, n2, shadowSun) > 0.05;
        }
        if (st.light === 'axis') {
          let direct = st.top * (m2 > 0 ? m2 : (m2 === 0 ? m2 : 0)) + st.ku * Math.abs(m1) + st.kv * Math.abs(m0);
          if (sh) direct = direct * (1 - pz(st.shadow_keep, z));
          light[m] = st.ambient + direct;
        } else {
          let nl = mm3(n0, n1, n2, SUN); nl = nl > 0 ? nl : (nl === 0 ? nl : 0);
          if (sh) nl = nl * (1 - pz(st.shadow_keep, z));
          light[m] = st.ambient + st.diffuse * nl;
        }
      }
      const rim = st.rim;
      let nG = M - nModel;
      if (rim && nG && pz(rim.dark, z)) {
        const dark = pz(rim.dark, z);
        for (let m = 0; m < M; m++) {
          if (!isG[m]) continue;
          const u = pts[3 * m], v = pts[3 * m + 1];
          const d = Math.min(u, n - v);                       // np.minimum(pg[:, 0], n - pg[:, 1])
          let fall = 1.0 - d / rim.width; fall = fall < 0 ? 0 : fall > 1 ? 1 : fall; fall = Math.pow(fall, 1.5);
          const p0 = rotPts(pts.subarray(3 * m, 3 * m + 3), n, (4 - r) % 4);
          let patch = fr(fr(0.55) + fr(fr(0.6) * valueNoise(p0[0], p0[1], p0[2], 4.0, 11)));
          patch = patch < 0 ? 0 : patch > 1 ? 1 : patch;
          light[m] = light[m] * (1.0 - dark * fall * patch);
        }
      }
      if (nG) {
        const kuv = GRASS_TEXELS_PER_CELL / groundTex.h;
        for (let m = 0; m < M; m++) {
          if (!isG[m]) continue;
          const p0 = rotPts(pts.subarray(3 * m, 3 * m + 3), n, (4 - r) % 4);
          const ti = texIndex(groundTex, p0[0] * kuv, p0[1] * kuv);
          alb[3 * m] = groundTex.d[ti]; alb[3 * m + 1] = groundTex.d[ti + 1]; alb[3 * m + 2] = groundTex.d[ti + 2];
        }
      }
      if (nModel) {
        const one = nModel === 1;
        const sat = pz(st.sat, z), gr = pz(st.grain, z);
        const satK = fr(sat - 1.0), grK = fr(gr);
        const tone = st.tone && st.tone.length ? [fr(st.tone[0]), fr(st.tone[1])] : null, lo4 = fr(1e-4);
        for (let m = 0; m < M; m++) {
          if (isG[m]) continue;
          const q = sel[m], id = ib[q], b0 = bb[3 * q], b1 = bb[3 * q + 1], b2 = bb[3 * q + 2];
          const mat = mesh.mats[mesh.mat[id]];
          let a0 = fr(mat.kd[0]), a1 = fr(mat.kd[1]), a2 = fr(mat.kd[2]);
          if (mat.tex && mesh.has_uv[id]) {
            const o = 6 * id;
            const uu = (mesh.uv[o] * b0 + mesh.uv[o + 2] * b1) + mesh.uv[o + 4] * b2;
            const vv = (mesh.uv[o + 1] * b0 + mesh.uv[o + 3] * b1) + mesh.uv[o + 5] * b2;
            const ti = texIndex(mat.tex, uu, vv);
            a0 = mat.tex.d[ti]; a1 = mat.tex.d[ti + 1]; a2 = mat.tex.d[ti + 2];
          }
          if (tone) {                       // task sc4web (bldrender task sc4conv): luminance tone of pre-lit art, float32
            const y = mm3f(a0, a1, a2, LUMA, one);
            let y2 = fr(tone[1] * powf(y > 0 ? y : 0, tone[0])); y2 = y2 < 0 ? 0 : y2 > 1 ? 1 : y2;
            const ratio = fr(y2 / Math.max(y, lo4));
            const cl = x => x < 0 ? 0 : x > 1 ? 1 : x;
            a0 = cl(fr(a0 * ratio)); a1 = cl(fr(a1 * ratio)); a2 = cl(fr(a2 * ratio));
          }
          if (sat !== 1.0) {
            const y = mm3f(a0, a1, a2, LUMA, one);
            const mx = Math.max(a0, a1, a2), mn = Math.min(a0, a1, a2);
            const s0 = fr(fr(mx - mn) / Math.max(mx, fr(1e-6)));
            const k = fr(1.0 + fr(satK * fr(1.0 - s0)));
            const cl = x => x < 0 ? 0 : x > 1 ? 1 : x;
            a0 = cl(fr(y + fr(fr(a0 - y) * k))); a1 = cl(fr(y + fr(fr(a1 - y) * k))); a2 = cl(fr(y + fr(fr(a2 - y) * k)));
          }
          if (gr) {
            const p0 = rotPts(pts.subarray(3 * m, 3 * m + 3), n, (4 - r) % 4);
            const nz = grain(p0[0], p0[1], p0[2], W, 0);
            const f = fr(1.0 + fr(grK * nz));
            const cl = x => x < 0 ? 0 : x > 1 ? 1 : x;
            a0 = cl(fr(a0 * f)); a1 = cl(fr(a1 * f)); a2 = cl(fr(a2 * f));
          }
          alb[3 * m] = a0; alb[3 * m + 1] = a1; alb[3 * m + 2] = a2;
        }
      }
      if (pz(st.edge, z)) throw new BldError('edge light is not part of any style (bldrender.STYLES) and not ported');
      for (let m = 0; m < M; m++) {
        const q = sel[m];
        for (let c = 0; c < 3; c++) { let v = alb[3 * m + c] * light[m]; v = v < 0 ? 0 : v > 1 ? 1 : v; rgb[3 * q + c] = v; }
      }
      const con = pz(st.contrast, z);
      if (con !== 1.0 && nModel) {
        const one = nModel === 1, piv = fr(st.pivot), cf = fr(con), lo = fr(1e-4);
        const cl = x => x < 0 ? 0 : x > 1 ? 1 : x;
        for (let m = 0; m < M; m++) {
          if (isG[m]) continue;
          const q = sel[m], r0 = rgb[3 * q], r1 = rgb[3 * q + 1], r2 = rgb[3 * q + 2];
          const y = mm3f(r0, r1, r2, LUMA, one);
          const y2 = cl(fr(piv + fr(fr(y - piv) * cf)));
          const ratio = fr(y2 / Math.max(y, lo));
          rgb[3 * q] = cl(fr(r0 * ratio)); rgb[3 * q + 1] = cl(fr(r1 * ratio)); rgb[3 * q + 2] = cl(fr(r2 * ratio));
        }
      }
    }
    // box filter ss x ss
    let img = newImg(Ww, Hh);
    const s3 = new Float32Array(3), area = fr(ss * ss);
    for (let y = 0; y < Hh; y++) for (let x = 0; x < Ww; x++) {
      let c = 0; s3[0] = s3[1] = s3[2] = 0;
      for (let a = 0; a < ss; a++) {
        const row = (y * ss + a) * SW + x * ss;
        for (let b = 0; b < ss; b++) {
          const q = row + b;
          if (ib[q] < 0) continue;
          c++;
          s3[0] = s3[0] + rgb[3 * q]; s3[1] = s3[1] + rgb[3 * q + 1]; s3[2] = s3[2] + rgb[3 * q + 2];
        }
      }
      const o = (y * Ww + x) * 4;
      if (c > 0) {
        for (let k = 0; k < 3; k++) { let v = rint(fr(fr(s3[k] / c) * 255)); img.d[o + k] = v < 0 ? 0 : v > 255 ? 255 : v; }
      }
      img.d[o + 3] = fr(c / area) >= 0.5 ? 255 : 0;
    }
    // trim empty rows above the content, never below the lot's top vertex row
    let first = -1;
    for (let y = 0; y < Hh && first < 0; y++) for (let x = 0; x < Ww; x++) if (img.d[(y * Ww + x) * 4 + 3]) { first = y; break; }
    const cut = first >= 0 ? Math.min(first, top) : 0;
    if (cut) img = { w: Ww, h: Hh - cut, d: img.d.slice(cut * Ww * 4) };
    if (st.palette) img = paletteCut(img, st.palette);
    return [quantize565(img), [0, top - cut]];
  }

  // render_model -> Map "z,r" -> [image, [L, T]]
  function renderModel(meshTile, n, opts) {
    const { ground = 'grass', shadows = true, style = null, envStyle = null, progress = null, ss = 4 } = opts || {};
    const [, st] = styleOf(style, envStyle);
    const zooms = [0, 1, 2, 3, 4];
    const need = [...new Set(zooms.concat(st.zoom4 === 'double' ? [3] : []))].sort();
    const out = new Map(), gts = new Map();
    for (const z of need) {
      if (z === 4 && st.zoom4 === 'double') {
        for (let r = 0; r < ROTS; r++) { const [im, [L, T]] = out.get('3,' + r); out.set('4,' + r, [imgNearest2x(im), [2 * L, 2 * T]]); }
        continue;
      }
      const ga = grassArgs(st, z), key = JSON.stringify(ga);
      if (!gts.has(key)) gts.set(key, ga ? grassTexture(ga.base, ga.amp) : grassTexture());
      for (let r = 0; r < ROTS; r++) {
        out.set(z + ',' + r, renderFrame(meshTile, n, z, r, z >= 2 ? ss : 8, ground, shadows, gts.get(key), st));
        if (progress) progress(z * 4 + r + 1, 20);
      }
    }
    return out;
  }

  // ================================================================================================ QFS + sprites
  function qfsDecompress(buf, pos = 0, limit = null) {
    const end = limit === null ? buf.length : Math.min(buf.length, pos + limit);
    let p = pos + ((buf[pos] & 1) ? 5 : 2);
    const declared = (buf[p] << 16) | (buf[p + 1] << 8) | buf[p + 2]; p += 3;
    const out = []; let o = 0;
    const lit = n => { if (p + n > end) throw new BldError('literal run overruns the stream'); for (let k = 0; k < n; k++) out.push(buf[p + k]); p += n; };
    const back = (off, ln) => { if (off > out.length) throw new BldError('back-reference out of range'); let src = out.length - off; for (let k = 0; k < ln; k++) out.push(out[src++]); };
    for (;;) {
      if (p >= end) throw new BldError('stream ended without a terminator control byte');
      const b0 = buf[p];
      if (!(b0 & 0x80)) { const b1 = buf[p + 1]; p += 2; lit(b0 & 3); back(((b0 & 0x60) << 3) + b1 + 1, ((b0 >> 2) & 7) + 3); }
      else if (!(b0 & 0x40)) { const b1 = buf[p + 1], b2 = buf[p + 2]; p += 3; lit(b1 >> 6); back(((b1 & 0x3F) << 8) + b2 + 1, (b0 & 0x3F) + 4); }
      else if (!(b0 & 0x20)) { const b1 = buf[p + 1], b2 = buf[p + 2], b3 = buf[p + 3]; p += 4; lit(b0 & 3); back(((b0 & 0x10) << 12) + (b1 << 8) + b2 + 1, ((b0 & 0x0C) << 6) + b3 + 5); }
      else { const n = (b0 & 0x1F) * 4 + 4; p += 1; if (n > 0x70) { lit(b0 & 3); break; } lit(n); }
    }
    void o;
    return { out: Uint8Array.from(out), consumed: p - pos, declared };
  }
  // qfs_encode.compress (GZResourceD FUN_1001694d), quick = 1
  function qfsCompress(src) {
    const n = src.length;
    const pad = new Uint8Array(n + 2); pad.set(src);
    const hashtab = new Int32Array(0x10000).fill(-1), chain = new Int32Array(0x20000).fill(-1);
    const out = []; let pos = 0, litStart = 0, pending = 0, remaining = n;
    const flushRuns = () => {
      while (pending > 3) {
        let k = pending & 0xFFFFFFFC; if (k > 0x70) k = 0x70;
        pending -= k; out.push(((k >> 2) - 0x21) & 0xFF);
        for (let q = 0; q < k; q++) out.push(src[litStart + q]);
        litStart += k;
      }
    };
    while (remaining > 0) {
      let bestOffM1 = 0, bestCost = 2, bestLen = 2;
      const cap = Math.min(0x404, remaining);
      const hv = (pad[pos + 1] << 4) ^ ((pad[pos] << 8) | pad[pos + 2]);
      let lo = pos - 0x1FFFF; if (lo < 1) lo = 0;
      let cand = hashtab[hv];
      if (cand >= lo) {
        for (;;) {
          if (pad[pos + bestLen] === pad[cand + bestLen]) {
            let m = 0;
            while (m < cap && src[pos + m] === src[cand + m]) m++;
            if (m > bestLen) {
              const offM1 = pos - cand - 1;
              let cost;
              if (offM1 < 0x400 && m < 0xB) cost = 2; else if (offM1 > 0x3FFF) cost = 4; else cost = m > 0x43 ? 4 : 3;
              if (bestLen - bestCost < m - cost) { bestCost = cost; bestOffM1 = offM1; bestLen = m; if (m > 0x403) break; }
            }
          }
          cand = chain[cand & 0x1FFFF];
          if (cand < lo) break;
        }
      }
      if (bestLen <= bestCost) {
        pending++; remaining--; chain[pos & 0x1FFFF] = hashtab[hv]; hashtab[hv] = pos; pos++; continue;
      }
      flushRuns();
      if (bestCost === 2) { out.push((((bestOffM1 >> 3) & 0xE0) + ((bestLen + 0x3D) * 4) + pending) & 0xFF); out.push(bestOffM1 & 0xFF); }
      else if (bestCost === 3) { out.push((bestLen + 0x7C) & 0xFF); out.push(((bestOffM1 >> 8) + pending * 0x40) & 0xFF); out.push(bestOffM1 & 0xFF); }
      else {
        out.push(((((bestLen - 5) >> 6) & 0xFC) + ((bestOffM1 >> 12) & 0xF0) + pending - 0x40) & 0xFF);
        out.push((bestOffM1 >> 8) & 0xFF); out.push(bestOffM1 & 0xFF); out.push((bestLen - 5) & 0xFF);
      }
      if (pending) { for (let q = 0; q < pending; q++) out.push(src[litStart + q]); pending = 0; }
      chain[pos & 0x1FFFF] = hashtab[hv]; hashtab[hv] = pos; pos += bestLen;
      remaining -= bestLen; litStart = pos;
    }
    flushRuns();
    out.push((pending - 4) & 0xFF);
    if (pending) for (let q = 0; q < pending; q++) out.push(src[litStart + q]);
    const hdr = Uint8Array.from([0x10, 0xFB, (n >>> 16) & 255, (n >>> 8) & 255, n & 255]);
    return u8cat([hdr, Uint8Array.from(out)]);
  }
  function recordHeader(p) {
    if (p.length < 0x14) throw new BldError('payload shorter than the 0x14-byte header');
    const d0 = rdU32(p, 0), d1 = rdU32(p, 4);
    return { d0, d1, d2: rdU32(p, 8), d3: rdU32(p, 12), d4: rdU32(p, 16), format: (d0 >>> 8) & 0xFF };
  }
  function decodeRecord(p) {             // -> [kind, block, info]
    const h = recordHeader(p);
    let start = null;
    if (h.format === 1 && (h.d1 & 0x8000) === 0 && (h.d1 & 0x80000) !== 0) start = 0x14;
    if (h.format === 0 && (h.d1 & 0x10000000) !== 0 && (h.d1 & 0x8000) === 0 && (h.d1 & 0x80000) !== 0) start = 0x14;
    if (start === null) return ['raw', null, h];
    const st = p.subarray(start);
    if (st.length < 2 || ((st[0] << 8) | st[1]) !== 0x10FB) return ['error', null, h];
    const r = qfsDecompress(st);
    if (r.out.length !== r.declared) return ['error', r.out, h];
    return ['qfs', r.out, h];
  }
  function parseSpan(block) {
    const w = rdU16(block, 4), h = rdU16(block, 6), a = rdU16(block, 8), b = rdU16(block, 10), key = rdU16(block, 12);
    const rows = [];
    for (let i = 0; i < h; i++) { const o = 16 + i * 8; rows.push([rdU32(block, o), rdU16(block, o + 4), rdU16(block, o + 6) & 0x7FFF]); }
    return { w, h, a, b, key, rows, ds: 16 + h * 8 };
  }
  function spanToImage(block) {          // sprite_render.span_to_image
    const m = parseSpan(block), im = newImg(m.w, m.h), k555 = m.key === 0x7C1F;
    m.rows.forEach(([off, x, n], y) => {
      const base = m.ds + off * 2;
      for (let i = 0; i < n; i++) {
        const v = rdU16(block, base + i * 2);
        if (v === m.key) continue;
        const o = (y * m.w + x + i) * 4;
        if (k555) { im.d[o] = Math.floor(((v >> 10) & 31) * 255 / 31); im.d[o + 1] = Math.floor(((v >> 5) & 31) * 255 / 31); }
        else { im.d[o] = Math.floor(((v >> 11) & 31) * 255 / 31); im.d[o + 1] = Math.floor(((v >> 5) & 63) * 255 / 63); }
        im.d[o + 2] = Math.floor((v & 31) * 255 / 31); im.d[o + 3] = 255;
      }
    });
    return im;
  }
  function spriteEncode(surf, w, h, key, fmtId, tag) {
    const rows = new Uint8Array(h * 8); const pix = []; let running = 0;
    for (let y = 0; y < h; y++) {
      const ro = y * w; let lead = 0;
      while (lead < w && surf[ro + lead] === key) lead++;
      let span, opaque, x;
      if (w === 0 || lead >= w) { span = 0; opaque = 1; x = lead; }
      else {
        let trail = 0, i = w - 1; while (surf[ro + i] === key) { trail++; i--; }
        span = w - lead - trail; x = lead; opaque = 1;
        for (let j = lead; j < lead + span; j++) if (surf[ro + j] === key) { opaque = 0; break; }
      }
      wrU32(rows, y * 8, running); wrU16(rows, y * 8 + 4, x); wrU16(rows, y * 8 + 6, (opaque ? 0x8000 : 0) | span);
      for (let j = x; j < x + span; j++) pix.push(surf[ro + j]);
      running += span;
    }
    const out = new Uint8Array(16 + rows.length + pix.length * 2);
    wrU32(out, 0, out.length); wrU16(out, 4, w); wrU16(out, 6, h); wrU16(out, 8, tag); wrU16(out, 10, fmtId); wrU16(out, 12, key);
    out.set(rows, 16);
    for (let k = 0; k < pix.length; k++) wrU16(out, 16 + rows.length + 2 * k, pix[k]);
    return out;
  }
  function recordFromImage(tmpl, im) {   // sprite_patch.record_from_image, alpha threshold 128
    const [kind, block, inf] = decodeRecord(tmpl);
    if (kind !== 'qfs' || inf.format !== 1) throw new BldError('template is not a format-1 sprite record');
    const m = parseSpan(block), w = im.w, h = im.h;
    if (!(1 <= w && w <= 0x7FFF && 1 <= h && h <= 0xFFFF)) throw new BldError('sprite size out of range');
    const surf = new Uint16Array(w * h).fill(m.key); let nudged = 0;
    const k555 = m.key === 0x7C1F;
    for (let i = 0; i < w * h; i++) {
      const r = im.d[4 * i], g = im.d[4 * i + 1], b = im.d[4 * i + 2], a = im.d[4 * i + 3];
      if (a < 128) continue;
      let v = k555 ? (((r >> 3) << 10) | ((g >> 3) << 5) | (b >> 3)) : (((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3));
      if (v === m.key) { v = m.key ^ 1; nudged++; }
      surf[i] = v;
    }
    const nb = spriteEncode(surf, w, h, m.key, m.b, m.a);
    const stream = qfsCompress(nb);
    const out = new Uint8Array(20 + stream.length);
    wrU32(out, 0, inf.d0); wrU32(out, 4, inf.d1); wrU32(out, 8, w); wrU32(out, 12, h); wrU32(out, 16, stream.length + 4);
    out.set(stream, 20);
    return [out, [w, h], nudged];
  }
  function anchorPayload(L, T, w, h) {
    for (const v of [L, T, w - L, h - T]) if (v < -32768 || v > 32767) throw new BldError('anchor value does not fit a signed i16');
    const b = new Uint8Array(8); wrU16(b, 0, L & 0xFFFF); wrU16(b, 2, T & 0xFFFF); wrU16(b, 4, (w - L) & 0xFFFF); wrU16(b, 6, (h - T) & 0xFFFF);
    return b;
  }

  // ================================================================================================ IXF + TKB1 (batgrow)
  const MAGIC = 0x80C381D7, REC = 20, FIRST_PAYLOAD = 0x5004, BLOCK = 0x5000;
  const FREE = 0xFFFFFFFF;
  const keyOf = (g, i, t) => g + ':' + i + ':' + t;
  function slots(d) {
    if (d.length < 4 || rdU32(d, 0) !== MAGIC) throw new BldError('not an IXF container');
    const out = []; let n = 0;
    while (4 + (n + 1) * REC <= d.length) {
      const o = 4 + n * REC, s = [rdU32(d, o), rdU32(d, o + 4), rdU32(d, o + 8), rdU32(d, o + 12), rdU32(d, o + 16)];
      out.push(s); n++;
      if (s[0] === 0 && s[1] === 0 && s[2] === 0) break;
    }
    if (!out.length || !(out[out.length - 1][0] === 0 && out[out.length - 1][1] === 0 && out[out.length - 1][2] === 0)) throw new BldError('IXF index has no terminator');
    return out;
  }
  function records(d) {                  // -> { idx: Map key -> payload, order: [[g, i, t]] }, first wins
    const idx = new Map(), order = [];
    const sl = slots(d);
    for (let k = 0; k < sl.length - 1; k++) {
      const [g, i, t, o, n] = sl[k];
      if (t === FREE || o === FREE || n === FREE) continue;
      const kk = keyOf(g, i, t);
      if (!idx.has(kk)) { idx.set(kk, d.subarray(o, o + n)); order.push([g, i, t]); }
    }
    return { idx, order };
  }
  function newContainer(recs) {
    const n = recs.length;
    const first = 4 + (n + 1) * REC <= FIRST_PAYLOAD ? FIRST_PAYLOAD : 4 + (n + 1) * REC;
    let tot = first; for (const r of recs) tot += r[3].length;
    const out = new Uint8Array(tot); wrU32(out, 0, MAGIC);
    let off = first, o = 4;
    for (const [g, i, t, p] of recs) { wrU32(out, o, g); wrU32(out, o + 4, i); wrU32(out, o + 8, t); wrU32(out, o + 12, off); wrU32(out, o + 16, p.length); o += REC; off += p.length; }
    off = first; for (const r of recs) { out.set(r[3], off); off += r[3].length; }
    return out;
  }
  function ixfAppend(d, recs) {
    let sl = slots(d);
    const termAt = 4 + (sl.length - 1) * REC;
    const live = sl.slice(0, -1).filter(s => s[3] !== FREE && s[4] !== FREE);
    const first = live.length ? Math.min(...live.map(s => s[3])) : d.length;
    const needEnd = termAt + (recs.length + 1) * REC;
    if (needEnd > first) {
      for (let k = termAt; k < first; k++) if (d[k]) throw new BldError('bytes between the index terminator and the first payload are not zero');
      const delta = BLOCK * Math.ceil((needEnd - first) / BLOCK);
      const g = new Uint8Array(d.length + delta); g.set(d.subarray(0, first)); g.set(d.subarray(first), first + delta);
      sl.slice(0, -1).forEach((s, k) => { if (s[3] !== FREE) wrU32(g, 4 + k * REC + 12, s[3] + delta); });
      d = g; sl = slots(d);
    }
    const keys = new Set(sl.slice(0, -1).map(s => keyOf(s[0], s[1], s[2])));
    let tot = d.length; for (const r of recs) tot += r[3].length;
    const out = new Uint8Array(tot); out.set(d);
    let off = d.length;
    const blob = new Uint8Array((recs.length + 1) * REC);
    recs.forEach(([g, i, t, p], k) => {
      const kk = keyOf(g, i, t);
      if (keys.has(kk)) throw new BldError('key already present');
      keys.add(kk);
      wrU32(blob, k * REC, g); wrU32(blob, k * REC + 4, i); wrU32(blob, k * REC + 8, t); wrU32(blob, k * REC + 12, off); wrU32(blob, k * REC + 16, p.length);
      off += p.length;
    });
    for (let k = termAt; k < termAt + blob.length; k++) if (out[k]) throw new BldError('bytes after the index terminator are not zero');
    out.set(blob, termAt);
    off = d.length; for (const r of recs) { out.set(r[3], off); off += r[3].length; }
    return out;
  }
  function ixfReplace(d, recs) {
    const pos = new Map();
    slots(d).forEach((s, k) => { if (!(s[0] === 0 && s[1] === 0 && s[2] === 0)) pos.set(keyOf(s[0], s[1], s[2]), 4 + k * REC); });
    let tot = d.length; for (const r of recs) tot += r[3].length;
    const out = new Uint8Array(tot); out.set(d); let off = d.length;
    for (const [g, i, t, p] of recs) {
      const at = pos.get(keyOf(g, i, t));
      if (at === undefined) throw new BldError('record not in the container');
      out.set(p, off); wrU32(out, at + 12, off); wrU32(out, at + 16, p.length); off += p.length;
    }
    return out;
  }
  function upsert(d, recs) {
    const have = new Set(slots(d).slice(0, -1).map(s => keyOf(s[0], s[1], s[2])));
    const old = recs.filter(r => have.has(keyOf(r[0], r[1], r[2]))), nw = recs.filter(r => !have.has(keyOf(r[0], r[1], r[2])));
    if (old.length) d = ixfReplace(d, old);
    if (nw.length) d = ixfAppend(d, nw);
    return d;
  }
  function tkb1Props(buf) {
    if (!(buf[0] === 0x54 && buf[1] === 0x4B && buf[2] === 0x42 && buf[3] === 0x31)) throw new BldError('not a TKB1 record');
    const out = []; let o = 4;
    while (o + 8 <= buf.length) {
      const prop = rdU32(buf, o), t = rdU16(buf, o + 4), n = rdU16(buf, o + 6); o += 8;
      let ln;
      if (t === 7) ln = rdU32(buf, o) + 4; else if (t === 3) ln = 4 * n; else if (t === 8) ln = 12 * n; else if (t === 1) ln = n;
      else throw new BldError('TKB1 prop 0x' + prop.toString(16) + ' has unknown type ' + t);
      out.push([prop, t, n, o, ln]); o += ln;
    }
    if (o !== buf.length) throw new BldError('TKB1 walk ended early');
    return out;
  }
  function tkb1Get(buf, prop) {
    for (const [p, t, n, off, ln] of tkb1Props(buf)) {
      if (p !== prop) continue;
      if (t === 3) return Array.from({ length: n }, (_, k) => rdU32(buf, off + 4 * k));
      if (t === 8) return Array.from({ length: 3 * n }, (_, k) => rdU32(buf, off + 4 * k));
      if (t === 7) return buf.subarray(off + 4, off + ln);
      return buf.subarray(off, off + ln);
    }
    return null;
  }
  function tkb1SetKey(buf, prop, key) {
    const b = new Uint8Array(buf);
    for (const [p, t, n, off] of tkb1Props(buf)) {
      if (p !== prop) continue;
      if (t !== 8 || n !== 1) throw new BldError('prop is not one key');
      key.forEach((v, k) => wrU32(b, off + 4 * k, v)); return b;
    }
    throw new BldError('prop 0x' + prop.toString(16) + ' not present');
  }
  function tkb1SetText(buf, prop, raw) {
    for (const [p, t, , off, ln] of tkb1Props(buf)) {
      if (p !== prop) continue;
      if (t !== 7) throw new BldError('prop is not text');
      return u8cat([buf.subarray(0, off), packU32s(raw.length), raw, buf.subarray(off + ln)]);
    }
    throw new BldError('prop not present');
  }
  const arrEq = (a, b) => !!a && a.length === b.length && b.every((v, k) => a[k] === v);

  // ================================================================================================ game data (batgrow)
  const BAT_REL = 'Apps/BARender/BAT.DAT';
  const BAT_GROUP = 0xBA1DBF1E, OVR_TYPE = 0x856CD19A, CS_TYPE = 0x6300;
  const BLD_TYPE = 0x207EDC0E, BLD_GROUP = 0x57E;
  const FAM_TYPE = 0x81F53D09, FAM_GROUP = 0x01F58D3D;
  const TEXT_TYPE = 0x2026960B, TEXT_GROUP = 0xA1096A4F;
  const OVL = 'mods/netmod/overlay/';
  const OCC_KOREA = 'Apps/Res/Occupant/OccupantAttribs_Korea.IXF', CS_KOREA = 'Apps/Res/Sprites/CSAttrib_Korea.IXF';
  const BUILDFAM = 'Apps/Res/BUILDFAM.IXF', NAMES = 'SC3StringsNetpack.IXF';
  const DEFAULT_CLASS = { R: { 1: 3300, 2: 3900, 3: 4500, 4: 4500 }, C: { 1: 5100, 2: 5700, 3: 6300, 4: 6700 }, I: { 1: 8700, 2: 8700, 3: 8900, 4: 9100 } };
  const CLASS_LABEL = {
    3100: 'Residential light, low wealth', 3300: 'Residential light, mid wealth', 3500: 'Residential light, high wealth',
    3700: 'Residential medium, low wealth', 3900: 'Residential medium, mid wealth', 4100: 'Residential medium, high wealth',
    4300: 'Residential dense, low wealth', 4500: 'Residential dense, mid wealth', 4700: 'Residential dense, high wealth',
    5100: 'Commercial light, low wealth', 5500: 'Commercial light, high wealth', 5700: 'Commercial medium, low wealth',
    6100: 'Commercial medium, high wealth', 6300: 'Commercial dense, low wealth', 6700: 'Commercial dense, high wealth',
    8100: 'Industrial dirty, light', 8300: 'Industrial dirty, medium', 8500: 'Industrial dirty, dense',
    8700: 'Industrial clean, light', 8900: 'Industrial clean, medium', 9100: 'Industrial clean, dense', 9300: 'Farm' };
  const EXCLUDE_FAMILIES = new Set([1]);
  // task airsea: bldimport.PORTS (kind -> the [ZoneDeveloperRules] rule whose families an entry joins)
  const PORTS = {
    airport: { rule: 0x2207D9EE, landuse: 12310, sizes: [1], filler: null, copies: true, label: 'Airport (airpark filler)' },
    seaport: { rule: 0xE2D3FD92, landuse: 12330, sizes: [1, 2], filler: false, copies: false, label: 'Seaport (dockyard)' },
  };
  const PORT_MAX_COPIES = 20;
  const portOf = kind => (typeof kind === 'string' && Object.prototype.hasOwnProperty.call(PORTS, kind)) ? PORTS[kind] : null;
  const reAll = (re, s) => { const out = []; re.lastIndex = 0; let m; while ((m = re.exec(s))) { out.push(m); if (m[0] === '') re.lastIndex++; } return out; };
  const KEY_RE = /Key:\s*(\d+),(\d+),(\d+),(\d+)/g;     // on latin1 strings of the payload bytes
  const familyLanduse = s => { const m = /LandUse:\s*(\d+)/.exec(s); return m ? parseInt(m[1], 10) : null; };

  async function stockBuildings(game) {
    if (game._stock) return game._stock;
    const out = new Map();
    for (const n of await game.listdir('Apps/Res/Occupant')) {
      if (!n.toLowerCase().endsWith('.ixf')) continue;
      const { idx, order } = records(await game.read('Apps/Res/Occupant/' + n));
      for (const [g, i, t] of order) if (t === BLD_TYPE && g === BLD_GROUP && !out.has(i)) out.set(i, [n, idx.get(keyOf(g, i, t))]);
    }
    game._stock = out;
    return out;
  }
  function familyRecords(d) {
    const { idx, order } = records(d), out = new Map();
    for (const [g, i, t] of order) if (t === FAM_TYPE && g === FAM_GROUP) out.set(i, idx.get(keyOf(g, i, t)));
    return out;
  }
  function syspakMember(pak, wanted) {   // syspak_parse.parse: the lines of one member (case-insensitive), exactly one
    let off = 0; const names = [];
    while (off + 8 <= pak.length) {
      const nl = rdU32(pak, off + 4);
      if (nl === 0 || nl > 128) break;
      const nm = pak.subarray(off + 8, off + 8 + nl);
      if (!nm.every(c => c >= 32 && c < 127)) break;
      names.push(latin1(nm)); off += 8 + nl;
    }
    let o = off + 4; const recs = [];
    for (let k = 0; k < names.length; k++) {
      const lc = rdU32(pak, o); o += 4; const lines = [];
      for (let q = 0; q < lc; q++) { const ln = rdU32(pak, o); o += 4; lines.push(latin1(pak.subarray(o, o + ln))); o += ln; }
      recs.push(lines);
    }
    if (o !== pak.length) throw new BldError('SYS.PAK record walk did not end at the end of the file');
    const hits = names.map((n, k) => [n, k]).filter(([n]) => n.toLowerCase() === wanted);
    if (hits.length !== 1) throw new BldError('SYS.PAK has ' + hits.length + ' ' + wanted + ' members');
    return recs[hits[0][1]];
  }
  function ruleFirstFamilies(pak, fams) {
    const lines = syspakMember(pak, 'sc3zonelayer.ini'), out = new Map(); let sec = null;
    for (const ln of lines) {
      const s = pyStrip(ln);
      if (s.startsWith('[')) { sec = s.toLowerCase(); continue; }
      if (sec !== '[zonedeveloperrules]' || !s.includes('=') || s.startsWith(';')) continue;
      const seen = new Set();
      for (const m of reAll(/0x81f53d09\s*,\s*0x01f58d3d\s*,\s*(\d+)/gi, s.slice(s.indexOf('=') + 1))) {
        const f = parseInt(m[1], 10);
        const lu = fams.has(f) ? familyLanduse(latin1(fams.get(f))) : null;
        if (lu === null || seen.has(lu)) continue;
        seen.add(lu);
        if (!out.has(lu)) out.set(lu, []);
        if (!out.get(lu).includes(f)) out.get(lu).push(f);
      }
    }
    return out;
  }
  function ruleFamilies(pak, fams) {     // bldimport.rule_families: rule CLSID -> [family] over [ZoneDeveloperRules]
    void fams;
    const lines = syspakMember(pak, 'sc3zonelayer.ini'), out = new Map(); let sec = null;
    for (const ln of lines) {
      const s = pyStrip(ln);
      if (s.startsWith('[')) { sec = s.toLowerCase(); continue; }
      if (sec !== '[zonedeveloperrules]' || !s.includes('=') || s.startsWith(';')) continue;
      const eq = s.indexOf('='), left = s.slice(0, eq), right = s.slice(eq + 1);
      const m = /^\s*\d+\s*,\s*0x([0-9a-f]+)\s*$/i.exec(left);
      if (!m) continue;
      const rule = parseInt(m[1], 16);
      if (!out.has(rule)) out.set(rule, []);
      const lst = out.get(rule);
      for (const mm of reAll(/0x81f53d09\s*,\s*0x01f58d3d\s*,\s*(\d+)/gi, right)) { const f = parseInt(mm[1], 10); if (!lst.includes(f)) lst.push(f); }
    }
    return out;
  }
  async function portTable(game) {      // bldimport.port_table
    if (game._ports) return game._ports;
    const fams = familyRecords(await game.read(BUILDFAM));
    const rules = ruleFamilies(await game.read('Apps/Sys/SYS.PAK'), fams);
    const bld = await stockBuildings(game);
    const out = new Map();
    for (const [kind, pt] of Object.entries(PORTS)) {
      const fl = (rules.get(pt.rule) || []).filter(f => fams.has(f) && familyLanduse(latin1(fams.get(f))) === pt.landuse);
      if (!fl.length) throw new BldError(kind + ': rule 0x' + hex8(pt.rule) + ' has no family with LandUse ' + pt.landuse);
      const bases = new Map();
      for (const f of fl) {
        for (const m of reAll(KEY_RE, latin1(fams.get(f)))) {
          if (parseInt(m[1], 10) !== BLD_GROUP || parseInt(m[2], 10) !== BLD_TYPE) continue;
          const bid = parseInt(m[3], 10);
          if (!bld.has(bid)) continue;
          const p = bld.get(bid)[1];
          const fp = tkb1Get(p, 0x66), cs = tkb1Get(p, 0x67), fl_ = tkb1Get(p, 0xCA);
          if (!pyTrue(fp && fp.length ? fp : null) || fp[0] !== fp[2] || !pt.sizes.includes(fp[0]) || bases.has(fp[0])) continue;
          const flag = !!(fl_ && fl_.length && (fl_[0] & 0x100));
          if (!(cs && cs.length) || cs[0] !== CS_TYPE || (pt.filler !== null && flag !== pt.filler)) continue;
          if (!arrEq(tkb1Get(p, 0x65), [pt.landuse]) || tkb1Get(p, 0x6D) === null) continue;
          bases.set(fp[0], [bid, bld.get(bid)[0]]);
        }
      }
      const miss = pt.sizes.filter(n => !bases.has(n));
      if (miss.length) throw new BldError(kind + ': no stock base building for lot ' + miss.map(n => n + 'x' + n).join(', ') + ' in families [' + fl.join(', ') + ']');
      out.set(kind, { families: fl, bases: new Map([...bases].sort((a, b) => a[0] - b[0])), landuse: pt.landuse, copies: pt.copies, label: pt.label });
    }
    game._ports = out;
    return out;
  }
  const targetOf = e => (portOf(e.kind) ? e.kind : e.class);   // bldimport.target_of
  async function classTable(game) {
    if (game._table) return game._table;
    const fams = familyRecords(await game.read(BUILDFAM));
    const firsts = ruleFirstFamilies(await game.read('Apps/Sys/SYS.PAK'), fams);
    const bld = await stockBuildings(game);
    const out = new Map();
    for (const lu of Object.keys(CLASS_LABEL).map(Number).sort((a, b) => a - b)) {
      const fl = (firsts.get(lu) || []).filter(f => !EXCLUDE_FAMILIES.has(f));
      if (!fl.length) throw new BldError('class ' + lu + ': no rule uses a family with that LandUse');
      const bases = new Map();
      for (const f of fl) {
        for (const m of reAll(KEY_RE, latin1(fams.get(f)))) {
          if (parseInt(m[1], 10) !== BLD_GROUP || parseInt(m[2], 10) !== BLD_TYPE) continue;
          const bid = parseInt(m[3], 10);
          if (!bld.has(bid)) continue;
          const p = bld.get(bid)[1];
          const fp = tkb1Get(p, 0x66), cs = tkb1Get(p, 0x67), fl_ = tkb1Get(p, 0xCA);
          if (!pyTrue(fp && fp.length ? fp : null) || fp[0] !== fp[2] || !(1 <= fp[0] && fp[0] <= 4) || bases.has(fp[0])) continue;
          if (!(cs && cs.length) || cs[0] !== CS_TYPE || (fl_ && fl_.length && (fl_[0] & 0x100))) continue;
          if (!arrEq(tkb1Get(p, 0x65), [lu]) || tkb1Get(p, 0x6D) === null) continue;
          bases.set(fp[0], [bid, bld.get(bid)[0]]);
        }
      }
      out.set(lu, { families: fl, bases: new Map([...bases].sort((a, b) => a[0] - b[0])) });
    }
    for (const z of Object.keys(DEFAULT_CLASS)) for (const [size, lu] of Object.entries(DEFAULT_CLASS[z]))
      if (!out.get(lu).bases.has(+size)) throw new BldError('default class ' + lu + ' for zone ' + z + ' has no ' + size + 'x' + size + ' base');
    game._table = out;
    return out;
  }
  async function baseExemplar(game, bid, fname) {
    const { idx } = records(await game.read('Apps/Res/Occupant/' + fname));
    const p = idx.get(keyOf(BLD_GROUP, bid, BLD_TYPE));
    if (!p) throw new BldError('stock building ' + bid + ' not found in Apps/Res/Occupant/' + fname);
    return p;
  }
  async function batBuildings(game) {
    if (game._bats) return game._bats;
    game._bats = batParse(records(await game.read(BAT_REL)), BAT_GROUP);
    return game._bats;
  }
  // batgrow.bat_buildings over one group of an IXF's records (BAT.DAT: group 0xBA1DBF1E)
  function batParse(rec, group) {
    const { idx, order } = rec, out = [];
    for (const [g, i, t] of order) {
      if (t !== OVR_TYPE || g !== group) continue;
      const p = idx.get(keyOf(g, i, t));
      const b = { inst: i, size: p[0], problem: null };
      if (p.length < 17) { b.name = new Uint8Array(0); b.problem = 'override record too short'; out.push(b); continue; }
      const key = [rdU32(p, 1), rdU32(p, 5), rdU32(p, 9)];
      const nl = rdU32(p, 13);
      if (p.length < 17 + nl + 4) { b.name = new Uint8Array(0); b.problem = 'override record too short'; out.push(b); continue; }
      b.name = p.subarray(17, 17 + nl);
      const tab = idx.get(keyOf(key[1], key[2], key[0]));
      if (key[0] !== CS_TYPE || !tab || tab.length < 0x18 || !(tab[0] === 0x42 && tab[1] === 0x49 && tab[2] === 0x4E && tab[3] === 0x0D) || (tab.length - 0x18) % 15) b.problem = 'frame table missing';
      else if (!(1 <= b.size && b.size <= 4)) b.problem = 'lot size ' + b.size;
      else {
        const ents = []; for (let k = 0; k < (tab.length - 0x18) / 15; k++) ents.push([rdU32(tab, 0x18 + 15 * k + 2), rdU32(tab, 0x18 + 15 * k + 6)]);
        const pix = [];
        for (const e of ents) if (!pix.some(q => q[0] === e[0] && q[1] === e[1])) pix.push(e);
        if (pix.some(([pg, pi]) => !idx.has(keyOf(pg, pi, 0)) || !idx.has(keyOf(pg, pi, 1))) || pix.length > 0xFFFF) b.problem = 'frame table names a pixel record BAT.DAT does not hold';
        else Object.assign(b, { table: tab, entries: ents, pix_keys: pix, pixels: pix.map(([pg, pi]) => [idx.get(keyOf(pg, pi, 0)), idx.get(keyOf(pg, pi, 1))]) });
      }
      out.push(b);
    }
    return out;
  }
  // bldfile.ixf_buildings: every group of a BA-rendered IXF, groups in the order of their first override record
  function ixfBuildings(d) {
    const rec = records(d), groups = [];
    for (const [g, , t] of rec.order) if (t === OVR_TYPE && !groups.includes(g)) groups.push(g);
    const out = [];
    for (const g of groups) for (const b of batParse(rec, g)) { b.group = g; out.push(b); }
    return out;
  }
  // bldfile.side_match: by the .bld id first (an IXF re-keyed by bldfile.py render), then by name and lot in the
  // IXF's order, each building once. -> [[bld, building or null], ...]
  function sideMatch(d, blds) {
    const blt = ixfBuildings(d).filter(b => !b.problem), used = new Set();
    const out = blds.map(bld => {
      const k = blt.findIndex((b, j) => !used.has(j) && b.inst === bld.ident && b.size === bld.lot && b.group === BAT_GROUP);
      return [bld, k < 0 ? null : k];
    });
    for (const r of out) if (r[1] !== null) used.add(r[1]);
    for (const r of out) {
      if (r[1] !== null) continue;
      const nm = cp1252Encode(r[0].name, true);
      const k = blt.findIndex((b, j) => !used.has(j) && bytesEq(b.name, nm) && b.size === r[0].lot);
      if (k >= 0) { r[1] = k; used.add(k); }
    }
    return out.map(([bld, k]) => [bld, k === null ? null : blt[k]]);
  }
  // stock_table_and_template: the base's 0x6300 table and one of its pixel records, from the game's own files.
  // Lazy: an IXF index is at the head of the file, so only the head and the one payload are read.
  async function findRecordLazy(game, rel, g, i, t) {
    const head = await game.readRange(rel, 0, 4);
    if (head.length < 4 || rdU32(head, 0) !== MAGIC) throw new BldError('not an IXF container');
    let n = 0, chunk = new Uint8Array(0), chunkAt = 4, found = null;
    const size = await game.size(rel);
    for (;;) {
      const o = 4 + n * REC;
      if (o + REC > size) throw new BldError('IXF index has no terminator');
      if (o + REC > chunkAt + chunk.length) { chunk = await game.readRange(rel, o, Math.min(size - o, 1 << 16)); chunkAt = o; }
      const c = o - chunkAt;
      const s = [rdU32(chunk, c), rdU32(chunk, c + 4), rdU32(chunk, c + 8), rdU32(chunk, c + 12), rdU32(chunk, c + 16)];
      n++;
      if (s[0] === 0 && s[1] === 0 && s[2] === 0) break;
      if (found === null && s[0] === g && s[1] === i && s[2] === t && s[2] !== FREE && s[3] !== FREE && s[4] !== FREE) found = s;
    }
    if (!found) return null;
    return game.readRange(rel, found[3], found[4]);
  }
  async function stockTableAndTemplate(game, ex) {
    const key = tkb1Get(ex, 0x67);
    if (!key || key[0] !== CS_TYPE) throw new BldError('base exemplar prop 0x67 is not a 0x6300 frame table key');
    game._tt = game._tt || new Map();
    const ck = key.join(':');
    if (game._tt.has(ck)) return game._tt.get(ck);
    let tab = null;
    for (const n of await game.listdir('Apps/Res/Sprites')) {
      if (n.toLowerCase().startsWith('csattrib') && n.toLowerCase().endsWith('.ixf')) {
        const { idx } = records(await game.read('Apps/Res/Sprites/' + n));
        tab = idx.get(keyOf(key[1], key[2], key[0])) || null;
        if (tab && tab.length) break;
        tab = null;
      }
    }
    if (!tab) throw new BldError('frame table not found in Apps\\Res\\Sprites\\CSATTRIB*.IXF');
    const g = rdU32(tab, 0x18 + 2), i = rdU32(tab, 0x18 + 6);
    for (const n of await game.listdir('Apps/Res/Sprites')) {
      if (!n.toLowerCase().endsWith('.dat')) continue;
      let p;
      try { p = await findRecordLazy(game, 'Apps/Res/Sprites/' + n, g, i, 0); } catch (e) { if (e instanceof BldError) continue; throw e; }
      if (p && p.length) { game._tt.set(ck, [tab, p]); return [tab, p]; }
    }
    throw new BldError('pixel record of the base frame table not found');
  }

  // ================================================================================================ .bld (bldfile)
  const B_GROUP = 0xC3F8D4A9;
  const T_MODEL = 0xE3F87B0C, T_PREVIEW = 0xE3F87B0E, T_INFO = 0xE3F87B0F, T_TEX = 0xE3F87B10, T_CATEGORY = 0x644D7179;
  const I_MODEL = 0xA3F8D615, I_INFO = 0x63FBE1CC, I_PREVIEW = 0xE3F8D655, I_CATEGORY = 0xA44D71AB;
  const CATEGORY_ZONE = { 0x208: 'R', 0x209: 'C', 0x20A: 'I' };
  function bldRecords(b) {
    if (b.length < 24 || rdU32(b, 0) !== MAGIC) throw new BldError('not an IXF container (no 0x80C381D7 magic)');
    const out = new Map(); let o = 4;
    while (o + 20 <= b.length) {
      const g = rdU32(b, o), i = rdU32(b, o + 4), t = rdU32(b, o + 8), off = rdU32(b, o + 12), sz = rdU32(b, o + 16); o += 20;
      if (g === 0 && i === 0 && t === 0) return out;
      if (t === FREE || off === FREE || sz === FREE) continue;
      if (off + sz > b.length) throw new BldError('record runs past the end of the file');
      const k = keyOf(g, i, t); if (!out.has(k)) out.set(k, b.subarray(off, off + sz));
    }
    throw new BldError('IXF index has no terminator');
  }
  // model version 8 = SC3U Building Architect, 7 = the 1999 SC3 Building Architect (same byte layout, BLD_FORMAT.md 6)
  function parseModel(p) {
    const ver = p[0], n = p[2], lot = p[3], sep = p[4], height = rdU16(p, 5);
    const nn = rdU32(p, 0x1D);
    if ((ver !== 7 && ver !== 8) || sep !== 0xEA || nn !== n * n * 4) throw new BldError('model record header is not version 7 or 8 (got ' + ver + ')');
    let o = 0x21 + nn;
    if (rdU32(p, o) !== 0xEAEAEAEA) throw new BldError('model record: no separator after the column table');
    const blob = rdU32(p, o + 4);
    qfsDecompress(p, o + 12, blob - 4);
    o += 8 + blob;
    if (rdU32(p, o) !== 0xEAEAEAEA) throw new BldError('model record: no separator after the cell data');
    const cnt = rdU32(p, o + 4); o += 8;
    for (let k = 0; k < cnt; k++) { const ln = rdU32(p, o); o += 8 + ln; }
    if (rdU32(p, o) !== 0xEAEAEAEA || o + 4 !== p.length) throw new BldError('model record: texture list does not end the record');
    return { version: ver, grid: n, lot, height, textures: cnt };
  }
  function readBld(buf, file) {
    const b = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
    const r = bldRecords(b);
    const rec = (i, t, need = true) => { const p = r.get(keyOf(B_GROUP, i, t)); if (!p && need) throw new BldError('record missing'); return p || null; };
    const info = rec(I_INFO, T_INFO);
    const lot = info[0];
    let o = 1; const nl = info[o]; const nameRaw = info.subarray(o + 1, o + 1 + nl); o += 1 + nl;
    const al = info[o]; const arch = info.subarray(o + 1, o + 1 + al); o += 1 + al;
    let ident, identFrom;
    if (o === info.length) { ident = (crc32(b) ^ 0xFFFFFFFF) >>> 0; identFrom = 'crc32'; }   // 1999 .bld: no id (bldfile.derived_ident)
    else {
      if (o + 8 > info.length) throw new BldError('info record too short');
      const sl = rdU32(info, o);
      if (o + 8 + sl !== info.length) throw new BldError('info record: ' + (info.length - o - 4 - sl) + ' bytes after the owner string, 4 expected');
      ident = rdU32(info, o + 4 + sl); identFrom = 'file';
    }
    const cat = rec(I_CATEGORY, T_CATEGORY, false);
    const model = parseModel(rec(I_MODEL, T_MODEL));
    const pv = rec(I_PREVIEW, T_PREVIEW);
    const w = rdU16(pv, 2), h = rdU16(pv, 4), pn = rdU32(pv, 6);
    const raw = qfsDecompress(pv, 10, pn).out;
    if (raw.length !== w * h * 2) throw new BldError('preview is not ' + w + 'x' + h + ' RGB565');
    const prev = newImg(w, h);
    for (let k = 0; k < w * h; k++) {
      const v = raw[2 * k] | (raw[2 * k + 1] << 8);
      prev.d[4 * k] = Math.floor(((v >> 11) & 31) * 255 / 31); prev.d[4 * k + 1] = Math.floor(((v >> 5) & 63) * 255 / 63);
      prev.d[4 * k + 2] = Math.floor((v & 31) * 255 / 31); prev.d[4 * k + 3] = v === 0xF81F ? 0 : 255;
    }
    const out = { file, lot, name: cp1252Decode(nameRaw), nameRaw, architect: cp1252Decode(arch), ident, ident_from: identFrom,
      category: cat && cat.length >= 4 ? rdU32(cat, 0) : null, model, preview: prev,
      custom_textures: [...r.keys()].filter(k => +k.split(':')[2] === T_TEX).length };
    if (!(1 <= lot && lot <= 4)) throw new BldError('lot size ' + lot + ' (growables are 1x1 to 4x4)');
    if (model.grid !== 8 * lot) throw new BldError('model grid is not 8 x lot');
    return out;
  }
  const suggestClass = b => { const z = CATEGORY_ZONE[b.category]; return z ? DEFAULT_CLASS[z][b.lot] : null; };
  function artBox(prev) {
    let x0 = Infinity, y0 = Infinity, x1 = -1, y1 = -1;
    for (let y = 0; y < prev.h; y++) for (let x = 0; x < prev.w; x++) if (prev.d[(y * prev.w + x) * 4 + 3] > 0) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
    if (x1 < 0) throw new BldError('the preview is empty');
    return [x0, y0, x1, y1];
  }
  function fitPreview(prev, n, z) {
    const W = 8 << z, [x0, y0, x1, y1] = artBox(prev);
    const crop = imgCrop(prev, x0, y0, x1 + 1, y1 + 1);
    const w = n * W, s = w / crop.w, h = Math.max(1, rint(crop.h * s));
    const im = pilResize(crop, w, h, s < 1 ? 'LANCZOS' : 'BICUBIC');
    for (let k = 0; k < w * h; k++) {
      im.d[4 * k + 3] = im.d[4 * k + 3] >= 128 ? 255 : 0;
      if (!im.d[4 * k + 3]) im.d[4 * k] = im.d[4 * k + 1] = im.d[4 * k + 2] = 0;
    }
    return [im, [0, h - Math.floor(n * W / 4)]];
  }
  function previewFrames(bld, style) {
    const st = style ? styleOf(style)[1] : BA_LOOK;
    const prev = bld.preview, n = bld.lot, [x0, , x1] = artBox(prev);
    const out = new Map();
    for (let z = 0; z < ZOOMS; z++) {
      let im, LT;
      if (z === 4 && (st.zoom4 === 'double' || (x1 - x0 + 1) < n * 128)) {
        const [im3, [, T3]] = out.get('3,0'); im = imgNearest2x(im3); LT = [0, T3 * 2];
      } else {
        [im, LT] = fitPreview(prev, n, z);
        if (st.palette) im = paletteCut(im, st.palette);
      }
      im = quantize565(im);
      const mir = imgMirror(im);
      for (let r = 0; r < ROTS; r++) out.set(z + ',' + r, [r % 2 ? mir : im, LT]);
    }
    return out;
  }
  async function batMatch(game, bld) {
    if (!(await game.exists(BAT_REL))) return null;
    const bats = (await batBuildings(game)).filter(b => !b.problem);
    for (const b of bats) if (b.inst === bld.ident && b.size === bld.lot) return b;
    if (bld.ident_from === 'crc32') return null;   // 1999 .bld: a same-named entry is another file's render (bldfile.bat_match)
    const nm = cp1252Encode(bld.name, true);
    for (const b of bats) if (bytesEq(b.name, nm) && b.size === bld.lot) return b;
    return null;
  }
  function batFrames(b) {
    const out = new Map();
    for (let k = 0; k < 16; k++) {
      const key = b.entries[k], pi = b.pix_keys.findIndex(q => q[0] === key[0] && q[1] === key[1]);
      const [px, an] = b.pixels[pi];
      const [, block] = decodeRecord(px);
      out.set((k >> 2) + ',' + (k % 4), [spanToImage(block), [rdI16(an, 0), rdI16(an, 2)]]);
    }
    for (let r = 0; r < ROTS; r++) { const [im, [L, T]] = out.get('3,' + r); out.set('4,' + r, [imgNearest2x(im), [L * 2, T * 2]]); }
    return out;
  }
  // side: the bytes of bld_frames.ixf beside the .bld (render_bld.ps1, the player's own BA render) or null
  const SIDE_NAME = 'bld_frames.ixf';
  async function bldFrames(bld, game, art, style, side) {
    if (!['auto', 'bat', 'preview'].includes(art)) throw new BldError('art ' + JSON.stringify(art) + ': use auto, bat or preview');
    if (art !== 'preview') {
      if (side) { const m = sideMatch(side, [bld])[0][1]; if (m) return [batFrames(m), 'bat', SIDE_NAME]; }
      const b = game ? await batMatch(game, bld) : null;
      if (b) return [batFrames(b), 'bat', 'BAT.DAT'];
      if (art === 'bat') throw new BldError(bld.file + ': neither ' + SIDE_NAME + ' beside it nor BAT.DAT holds this building');
    }
    return [previewFrames(bld, style), 'preview', 'the .bld'];
  }
  async function sideOf(folder, file) {
    const rel = joinRel(dirOf(String(file)), SIDE_NAME);
    folder._side = folder._side || new Map();
    if (!folder._side.has(rel)) folder._side.set(rel, rel === null ? null : await folder.get(rel));
    return folder._side.get(rel);
  }

  // ================================================================================================ bldimport
  const GROUP = 0xB1D10001, ID_FIRST = 38000, ID_LAST = 38999;
  const PIX_DAT = 'Apps/Res/Sprites/B1D10001_bldimport.DAT', STATE_DIR = 'mods/netmod/bldimport', BUILD_DIR = 'sc3build';
  const CELL_M = 16.0, FRAMES = 20;
  const isBld = f => String(f).toLowerCase().endsWith('.bld');
  const splitext0 = f => { const b = f.lastIndexOf('/') + 1, d = f.lastIndexOf('.'); return d > b && f.slice(b, d).replace(/\./g, '') !== '' ? f.slice(0, d) : f; };

  async function bldEntry(folder, f) {
    let b;
    try { b = readBld(await folder.get(f), f); }
    catch (e) { return { file: f, kind: 'growable', enabled: false, x_bld: { error: String(e.message || e) } }; }
    const cls = suggestClass(b);
    const cat = b.category !== null ? '0x' + b.category.toString(16).toUpperCase() : null;
    const e = { file: f, name: b.name, kind: 'growable', lot: [b.lot, b.lot], weight: 1, enabled: cls !== null, x_bld: { art: 'auto', architect: b.architect, category: cat } };
    if (cls !== null) e.class = cls;
    return e;
  }
  async function readModels(folder) {
    const blds = (await folder.list()).filter(isBld).sort();
    const j0 = await folder.get('models.json');
    if (!j0) {
      if (blds.length) { const out = []; for (const f of blds) out.push(await bldEntry(folder, f)); return out; }
      throw new BldError('the folder has no models.json (make one with the classifier page)');
    }
    const j = JSON.parse(utf8Dec().decode(j0).replace(/^﻿/, ''));
    if (j.sc3models !== 1) throw new BldError('models.json: sc3models is ' + JSON.stringify(j.sc3models) + ', this tool reads version 1');
    const models = j.models || [];
    const have = new Set(models.map(m => m.file));
    const out = models.slice();
    for (const f of blds) if (!have.has(f)) out.push(await bldEntry(folder, f));
    return out;
  }
  async function idsFor(folder, models) {
    const p = BUILD_DIR + '/ids.json';
    const raw = await folder.get(p);
    const ids = raw ? JSON.parse(utf8Dec().decode(raw)) : {};
    const used = new Set(Object.values(ids));
    let changed = false;
    for (const m of models) {
      const f = m.file;
      if (pyTrue(f) && !Object.prototype.hasOwnProperty.call(ids, f)) {
        let nid = null; for (let k = ID_FIRST; k <= ID_LAST; k++) if (!used.has(k)) { nid = k; break; }
        if (nid === null) throw new BldError('no free id left in ' + ID_FIRST + '-' + ID_LAST);
        ids[f] = nid; used.add(nid); changed = true;
      }
    }
    if (changed) await folder.put(p, new TextEncoder().encode(pyJson(ids, 1, true)));
    return ids;
  }
  function lotOf(m) {
    const lot = 'lot' in m ? m.lot : [1, 1];
    if (!(Array.isArray(lot) && lot.length === 2 && lot.every(x => Number.isInteger(x) || typeof x === 'boolean'))) return [null, 'lot ' + JSON.stringify(lot) + ' is not [n, n]'];
    const a = +lot[0], b = +lot[1];
    if (a !== b) return [null, 'lot ' + a + 'x' + b + ': only square lots grow (every stock base is n x n)'];
    if (!(1 <= a && a <= 4)) return [null, 'lot ' + a + 'x' + b + ': growables are 1x1 to 4x4'];
    return [a, null];
  }
  const xr = m => (m.x_bldrender && typeof m.x_bldrender === 'object' && pyTrue(m.x_bldrender)) ? m.x_bldrender : {};
  function optsOf(m, env) {
    const x = xr(m);
    return { shadow: pyTrue('shadow' in x ? x.shadow : true), ground: 'ground' in x ? x.ground : 'grass',
      cell_m: 'cell_m' in x ? Number(x.cell_m) : CELL_M, style: styleOf(x.style || null, env)[0] };
  }
  const bldStyle = m => { const s = xr(m).style; return pyTrue(s) ? styleOf(s)[0] : null; };
  const bldArt = m => (m.x_bld && typeof m.x_bld === 'object' && pyTrue(m.x_bld) && 'art' in m.x_bld) ? m.x_bld.art : 'auto';

  async function plan(folder, game) {
    const models = await readModels(folder);
    const ids = await idsFor(folder, models);
    const table = game ? await classTable(game) : null;
    const ports = game ? await portTable(game) : null;
    const out = [], rep = [];
    for (const m of models) {
      const f = 'file' in m ? m.file : '?';
      const nid = Object.prototype.hasOwnProperty.call(ids, f) ? ids[f] : null;
      const name = pyStrip(pyTrue(m.name) ? String(m.name) : splitext0(String(f)));
      let why = null;
      let [n, lotErr] = lotOf(m);
      const exists = typeof f === 'string' && !!(await folder.exists(f));
      if (isBld(f) && exists && !lotErr) {
        try { const bl = readBld(await folder.get(f), f).lot; if ('lot' in m && n !== bl) lotErr = 'lot ' + n + 'x' + n + ' in models.json, the .bld file is ' + bl + 'x' + bl; n = bl; }
        catch (e) { lotErr = 'not a readable .bld file (' + (e.message || e) + ')'; }
      }
      let cls = 'class' in m ? m.class : null;
      const w = 'weight' in m ? m.weight : 1;
      const kind = 'kind' in m ? m.kind : 'growable', port = portOf(kind);
      if (!pyTrue('enabled' in m ? m.enabled : true)) why = 'enabled is false';
      else if (kind !== 'growable' && port === null) why = 'kind ' + JSON.stringify(kind) + ': only growable, airport and seaport buildings';
      else if (!exists) why = 'file not in the folder';
      else if (!(String(f).toLowerCase().endsWith('.obj') || isBld(f))) why = 'only .obj models and .bld files';
      else if (cls === null && isBld(f) && port === null) why = 'no class: its category (' + ((m.x_bld || {}).category) + ') is not a house, shop or factory, set one in models.json';
      else if (lotErr) why = lotErr;
      else if (!Number.isInteger(w) || !(1 <= w && w <= 1000)) why = 'weight ' + JSON.stringify(w) + ' is not a whole number from 1 to 1000';
      else if (port !== null && port.copies && w > PORT_MAX_COPIES) why = 'weight ' + w + ': an ' + kind + "'s weight is the number of copies in the airpark's list (the rule ignores Key weights), at most " + PORT_MAX_COPIES;
      else if (port !== null && !port.sizes.includes(n)) why = kind + ' lot ' + n + 'x' + n + ': the ' + port.label.toLowerCase() + ' grows ' + port.sizes.map(s_ => s_ + 'x' + s_).join(' and ');
      else if (port === null && table && !(Number.isInteger(cls) && table.has(cls))) why = 'class ' + JSON.stringify(cls) + ' is not a growable class (' + [...table.keys()].join(', ') + ')';
      else if (port === null && table && !table.get(cls).bases.has(n)) why = 'class ' + cls + ' has no ' + n + 'x' + n + ' lot (it has ' + [...table.get(cls).bases.keys()].map(s => s + 'x' + s).join(', ') + ')';
      else if (cp1252Encode(name) === null) why = 'name ' + JSON.stringify(name) + " has characters the game's text files cannot hold (cp1252)";
      if (why) { rep.push('skip  [' + nid + '] ' + f + ': ' + why); continue; }
      if (port !== null) cls = port.landuse;          // the base's LandUse; models.json "class" is not used
      out.push({ id: nid, file: f, name, lot: n, class: cls, weight: w, model: m, kind: port !== null ? kind : 'growable' });
    }
    let tg = table;
    if (table) { tg = new Map(table); for (const [k, v] of ports) tg.set(k, v); }
    return [out, rep, tg];
  }

  // The render of one entry -> { frames, info }. renderer: optional async (job) => frames for a Web Worker.
  async function renderOne(folder, m, n, game, opt) {
    opt = opt || {};
    if (isBld(m.file)) {
      const b = readBld(await folder.get(m.file), m.file);
      const [fr_, src, where] = await bldFrames(b, game, bldArt(m), bldStyle(m), await sideOf(folder, m.file));
      return { frames: fr_, info: { bld: true, art: src, from: where, style: bldStyle(m) || 'ba', lot: b.lot, architect: b.architect, ident: hex8(b.ident), grid: b.model.grid, height: b.model.height } };
    }
    const o = optsOf(m, opt.envStyle);
    const job = { file: m.file, n, cell_m: o.cell_m, scale: Number('scale' in m ? m.scale : 1.0), rotate_deg: Number('rotate_deg' in m ? m.rotate_deg : 0),
      ground: o.ground === 'none' ? null : o.ground, shadows: o.shadow, style: o.style };
    const res = opt.renderer ? await opt.renderer(job, folder) : await renderJob(job, folder, opt.progress);
    const info = res.info;
    const hm = m.height_m;
    if (typeof hm === 'number' && hm > 0 && Math.abs(info.size_m[1] - hm) > 0.1 * hm && opt.log)
      opt.log('  note: ' + m.file + ' is ' + info.size_m[1].toFixed(1) + ' m tall after scale, models.json says height_m ' + hm.toFixed(1) + ' (scale wins)');
    if (!info.fits && opt.log)
      opt.log('  note: ' + m.file + ' is ' + info.size_m[0].toFixed(1) + ' x ' + info.size_m[2].toFixed(1) + ' m, larger than its ' + n + 'x' + n + ' lot: it will overhang the neighbours');
    info.style = o.style;
    return { frames: res.frames, info };
  }
  // the worker-side job: OBJ -> 20 frames
  async function renderJob(job, folder, progress) {
    const mesh = await loadObj(folder, job.file);
    const [mt, info] = place(mesh, job.n, job.cell_m, job.scale, job.rotate_deg);
    info.triangles = mesh.n;
    const frames = renderModel(mt, job.n, { ground: job.ground, shadows: job.shadows, style: job.style, progress });
    return { frames, info };
  }

  function frameTable(baseTab, nid) {
    if (!(baseTab[0] === 0x42 && baseTab[1] === 0x49 && baseTab[2] === 0x4E && baseTab[3] === 0x0D) || baseTab.length < 0x18) throw new BldError('base frame table is not a BIN\\r table');
    const out = new Uint8Array(0x18 + 15 * FRAMES);
    out.set(baseTab.subarray(0, 0x18)); wrU16(out, 0x16, FRAMES);
    for (let k = 0; k < FRAMES; k++) { const o = 0x18 + 15 * k; wrU16(out, o, k); wrU32(out, o + 2, GROUP); wrU32(out, o + 6, (nid * 65536 + k) >>> 0); }
    return out;
  }
  const KEY_LINE = /Key:\s*1406,545184782,(\d+),\d+[^\r\n]*\r?\n/g;
  function buildfamLines(bf, lines) {
    const fams = familyRecords(bf), neu = [];
    for (const [f, payload] of fams) {
      let text = latin1(payload);
      const drop = reAll(KEY_LINE, text).filter(mm => ID_FIRST <= +mm[1] && +mm[1] <= ID_LAST);
      const add = lines.get(f) || [];
      if (!drop.length && !add.length) continue;
      for (const mm of drop.reverse()) text = text.slice(0, mm.index) + text.slice(mm.index + mm[0].length);
      const mc = /BuildingCount:\s*(\d+)[^\r\n]*\r?\n/.exec(text);
      if (!mc) throw new BldError('BUILDFAM family ' + f + ' has no BuildingCount line');
      const cnt = parseInt(mc[1], 10) - drop.length + add.length;
      text = text.slice(0, mc.index) + 'BuildingCount: ' + cnt + '\r\n' + add.join('') + text.slice(mc.index + mc[0].length);
      neu.push([FAM_GROUP, f, FAM_TYPE, ascii(text)]);
    }
    return neu.length ? ixfReplace(bf, neu) : bf;
  }
  function describe(info) {
    if (info.bld) return info.art + ' art from ' + (info.from || 'the .bld') + ' (id ' + info.ident + ', by ' + info.architect + ')' + (info.art === 'preview' ? ', style ' + (info.style || 'ba') : '');
    return info.triangles + ' tris, ' + info.size_m[0].toFixed(1) + ' x ' + info.size_m[2].toFixed(1) + ' x ' + info.size_m[1].toFixed(1) + ' m, style ' + (info.style || '?');
  }
  async function buildFiles(folder, game, src, opt) {
    opt = opt || {};
    const log = opt.log || (() => {});
    const cur = async rel => (src.has(rel) ? src.get(rel) : (await game.exists(rel) ? await game.read(rel) : null));
    for (const rel of [OVL + OCC_KOREA, OVL + CS_KOREA]) if ((await cur(rel)) === null) throw new BldError(rel + ' not found: the road mod (sc3netmod, mods\\netmod) must be installed');
    const langs = [];
    for (const n of await game.listdir(OVL + 'Apps/Res/Text')) { const c = await cur(OVL + 'Apps/Res/Text/' + n + '/' + NAMES); if (c && c.length) langs.push(n); }
    if (!langs.length) throw new BldError('no mods\\netmod\\overlay\\Apps\\Res\\Text\\<language>\\' + NAMES + ' found');
    const [entries, rep, table] = await plan(folder, game);
    const occ = [], cs = [], pix = [], names = [], lines = new Map();
    const bld = await stockBuildings(game);
    let k0 = 0;
    for (const e of entries) {
      k0++;
      const nid = e.id, n = e.lot, lu = e.class, tg = table.get(targetOf(e));
      if (bld.has(nid)) throw new BldError('id ' + nid + ' already has a stock building exemplar');
      if (opt.onModel) opt.onModel(k0, entries.length, e);
      const { frames, info } = await renderOne(folder, e.model, n, game, Object.assign({}, opt, { log }));
      const [base, bfile] = tg.bases.get(n);
      let ex = await baseExemplar(game, base, bfile);
      const [tab, tmpl] = await stockTableAndTemplate(game, ex);
      const nm = cp1252Encode(e.name);
      ex = tkb1SetKey(ex, 0x67, [CS_TYPE, GROUP, nid]);
      ex = tkb1SetKey(ex, 0x6D, [TEXT_TYPE, TEXT_GROUP, nid]);
      ex = tkb1SetText(ex, 0x64, nm);
      tkb1Props(ex);
      occ.push([BLD_GROUP, nid, BLD_TYPE, ex]);
      cs.push([GROUP, nid, CS_TYPE, frameTable(tab, nid)]);
      let nudged = 0;
      for (let k = 0; k < FRAMES; k++) {
        const z = Math.floor((k % 20) / 4), r = k % 4;
        const [im, [L, T]] = frames.get(z + ',' + r);
        const [p0, [w, h], nd] = recordFromImage(tmpl, im);
        nudged += nd;
        pix.push([GROUP, (nid * 65536 + k) >>> 0, 0, p0]);
        pix.push([GROUP, (nid * 65536 + k) >>> 0, 1, anchorPayload(L, T, w, h)]);
      }
      names.push([TEXT_GROUP, nid, TEXT_TYPE, u8cat([packU32s(nm.length), nm])]);
      const copies = !!tg.copies;
      for (const f of tg.families) {
        if (!lines.has(f)) lines.set(f, []);
        if (copies) for (let q = 0; q < e.weight; q++) lines.get(f).push('Key: 1406,545184782,' + nid + ',1   ' + latin1(nm) + '\r\n');   // airpark: one line per copy
        else lines.get(f).push('Key: 1406,545184782,' + nid + ',' + e.weight + '   ' + latin1(nm) + '\r\n');
      }
      const what = copies ? tg.label + ', ' + n + 'x' + n + ', ' + e.weight + (e.weight === 1 ? ' copy' : ' copies')
        : (portOf(e.kind) ? tg.label : 'class ' + lu + ' (' + CLASS_LABEL[lu] + ')') + ', ' + n + 'x' + n + ', weight ' + e.weight;
      rep.push('grow  [' + nid + '] ' + e.file + ': "' + e.name + '", ' + what +
        ', stats of stock ' + base + ', families ' + tg.families.join(',') + ', ' + describe(info) + (nudged ? ', ' + nudged + ' magenta px nudged' : ''));
      if (opt.onFrames) opt.onFrames(e, frames, info);
    }
    const files = new Map();
    const keep = entries.map(e => e.id);
    if (entries.length || src.size) {
      files.set(OVL + OCC_KOREA, occ.length ? upsert(await cur(OVL + OCC_KOREA), occ) : await cur(OVL + OCC_KOREA));
      files.set(OVL + CS_KOREA, cs.length ? upsert(await cur(OVL + CS_KOREA), cs) : await cur(OVL + CS_KOREA));
      if (pix.length) files.set(OVL + PIX_DAT, newContainer(pix));
      for (const lang of langs) { const rel = OVL + 'Apps/Res/Text/' + lang + '/' + NAMES; files.set(rel, names.length ? upsert(await cur(rel), names) : await cur(rel)); }
      let bf = await cur(OVL + BUILDFAM);
      if (bf === null) bf = await game.read(BUILDFAM);
      files.set(OVL + BUILDFAM, buildfamLines(bf, lines));
    }
    rep.push(keep.length + ' building(s) to install: ' + (keep.slice().sort((a, b) => a - b).join(', ') || 'none'));
    return [files, rep];
  }

  // install / restore (batgrow's scheme)
  async function sources(game) {
    const stPath = STATE_DIR + '/state.json';
    const state = (await game.exists(stPath)) ? JSON.parse(utf8Dec().decode(await game.read(stPath))) : { files: {} };
    const src = new Map();
    for (const [rel, ent] of Object.entries(state.files)) {
      const c = (await game.exists(rel)) ? await game.read(rel) : null;
      if (c !== null && sha256(c) === ent.written) src.set(rel, ent.existed ? await game.read(STATE_DIR + '/backup/' + rel) : null);
      else src.set(rel, c);
    }
    return [src, state];
  }
  async function applyFiles(game, files, src, state, log) {
    log = log || (() => {});
    const newState = { files: {} };
    for (const rel of Object.keys(state.files)) {
      const orig = src.has(rel) ? src.get(rel) : null;
      if (orig === null) { if ((await game.exists(rel)) && !files.has(rel)) { await game.remove(rel); log('removed ' + rel); } }
      else if (!files.has(rel)) { await game.writeNew(rel, orig); log('put back ' + rel); }
    }
    const rels = [...files.keys()].sort((a, b) => a < b ? -1 : a > b ? 1 : 0);
    for (const rel of rels) {
      const b = files.get(rel);
      if (b === null) continue;
      const orig = src.has(rel) ? src.get(rel) : ((await game.exists(rel)) ? await game.read(rel) : null);
      const now = (await game.exists(rel)) ? await game.read(rel) : null;
      if (bytesEq(orig, b)) { if (!bytesEq(now, b)) await game.writeNew(rel, b); continue; }
      if (orig !== null) await game.writeNew(STATE_DIR + '/backup/' + rel, orig);
      if (!bytesEq(now, b)) await game.writeNew(rel, b);
      newState.files[rel] = { existed: orig !== null, written: sha256(b) };
      log('installed ' + rel);
    }
    await game.writeNew(STATE_DIR + '/state.json', ascii(pyJson(newState, 1, true)));
    return newState;
  }
  async function install(folder, game, opt) {
    if (!(await game.exists('Apps/Sys/SYS.PAK'))) throw new BldError('this folder has no Apps\\Sys\\SYS.PAK: pick the game folder (the one with Apps, Cities and Buildings)');
    const [src, state] = await sources(game);
    const [files, rep] = await buildFiles(folder, game, src, opt);
    if (opt && opt.dryRun) return { files, rep, state: null };
    const st = await applyFiles(game, files, src, state, opt && opt.log);
    return { files, rep, state: st };
  }
  async function restore(game, log) {
    const [src, state] = await sources(game);
    await applyFiles(game, new Map(), src, state, log);
    return Object.keys(state.files).length;
  }

  // ================================================================================================ folders
  // Folder over a FileSystemDirectoryHandle (File System Access API; node's test adapter has the same surface).
  // Paths are '/' separated and resolved case-insensitively, as on Windows.
  function handleFS(root) {
    const dirCache = new Map();
    async function dir(parts, create) {
      let h = root, path = '';
      for (const p of parts) {
        path += '/' + p.toLowerCase();
        if (dirCache.has(path)) { h = dirCache.get(path); continue; }
        let next = null;
        try { next = await h.getDirectoryHandle(p, { create: !!create }); }
        catch (e) {
          if (create) throw e;
          for await (const [nm, ch] of h.entries()) if (ch.kind === 'directory' && nm.toLowerCase() === p.toLowerCase()) { next = ch; break; }
          if (!next) return null;
        }
        dirCache.set(path, next); h = next;
      }
      return h;
    }
    async function fileHandle(rel) {
      const parts = rel.split('/').filter(Boolean), name = parts.pop();
      const d = await dir(parts, false); if (!d) return null;
      try { return await d.getFileHandle(name); }
      catch (e) {
        for await (const [nm, ch] of d.entries()) if (ch.kind === 'file' && nm.toLowerCase() === name.toLowerCase()) return ch;
        return null;
      }
    }
    const fileOf = async rel => { const h = await fileHandle(rel); return h ? h.getFile() : null; };
    return {
      root,
      async exists(rel) { return !!(await fileHandle(rel)); },
      async read(rel) { const f = await fileOf(rel); if (!f) throw new BldError(rel + ': not found'); return new Uint8Array(await f.arrayBuffer()); },
      async readRange(rel, a, n) { const f = await fileOf(rel); if (!f) throw new BldError(rel + ': not found'); return new Uint8Array(await f.slice(a, a + n).arrayBuffer()); },
      async size(rel) { const f = await fileOf(rel); return f ? f.size : 0; },
      async listdir(rel) {
        const d = await dir(rel.split('/').filter(Boolean), false); if (!d) return [];
        const names = []; for await (const [nm] of d.entries()) names.push(nm);
        return lowerSort(names);
      },
      async writeNew(rel, data) {
        // never through a hard link and never half a file over the old one: remove the old entry, then write a
        // new file (test trees are hard-linked; bldimport.py writes temp + rename)
        const parts = rel.split('/').filter(Boolean), name = parts.pop();
        const d = await dir(parts, true);
        const tmp = name + '.bldimport-tmp';
        const th = await d.getFileHandle(tmp, { create: true });
        const w = await th.createWritable(); await w.write(data); await w.close();
        const old = await fileHandle(rel);
        if (old) await d.removeEntry(old.name);
        if (typeof th.move === 'function') { try { await th.move(name); return; } catch (e) { /* fall through */ } }
        const nh = await d.getFileHandle(name, { create: true });
        const w2 = await nh.createWritable(); await w2.write(data); await w2.close();
        await d.removeEntry(tmp);
      },
      async remove(rel) {
        const parts = rel.split('/').filter(Boolean), name = parts.pop();
        const d = await dir(parts, false); const h = await fileHandle(rel);
        if (d && h) await d.removeEntry(h.name);
      },
      // models-folder view
      async get(rel) { const f = await fileOf(rel); return f ? new Uint8Array(await f.arrayBuffer()) : null; },
      async put(rel, data) { return this.writeNew(rel, data); },
      async list() { return this.listdir(''); },
    };
  }
  // Folder over a list of File objects (input webkitdirectory, or files posted to a worker): read only.
  function filesFS(files) {               // files: Map lowercased relative path -> File|Blob|Uint8Array, plus names
    const get = async rel => {
      const f = files.get(String(rel).toLowerCase());
      if (!f) return null;
      if (f instanceof Uint8Array) return f;
      return new Uint8Array(await f.arrayBuffer());
    };
    const put = new Map();
    return {
      get: async rel => put.has(rel.toLowerCase()) ? put.get(rel.toLowerCase()) : get(rel),
      exists: async rel => files.has(String(rel).toLowerCase()) || put.has(String(rel).toLowerCase()),
      async put(rel, data) { put.set(rel.toLowerCase(), data); if (this.onPut) await this.onPut(rel, data); },
      async list() { return [...(files._names || [])].filter(n => !n.includes('/')); },
      written: put,
    };
  }

  // A game folder read from a file list (input webkitdirectory: any browser, any folder) with the writes kept in
  // memory: install / restore run unchanged, then zipOf(writes) is what the player unpacks into the game folder.
  function listFS(fileList) {
    const files = new Map(), dirs = new Map();
    for (const f of fileList) {
      const parts = String(f.webkitRelativePath || f.name).split('/'); if (parts.length > 1) parts.shift();
      const rel = parts.join('/'); files.set(rel.toLowerCase(), f);
      for (let k = 0; k < parts.length; k++) {
        const d = parts.slice(0, k).join('/').toLowerCase();
        if (!dirs.has(d)) dirs.set(d, new Map());
        dirs.get(d).set(parts[k].toLowerCase(), parts[k]);
      }
    }
    const writes = new Map(), removed = new Map();          // lower key -> [rel as named, ...]; removed: key -> rel
    const key = rel => rel.split('/').filter(Boolean).join('/').toLowerCase();
    const live = rel => { const k = key(rel); if (writes.has(k)) return writes.get(k)[1]; if (removed.has(k)) return null; return files.get(k) || null; };
    const bytesOf = async f => f instanceof Uint8Array ? f : new Uint8Array(await f.arrayBuffer());
    return {
      async exists(rel) { return !!live(rel); },
      async read(rel) { const f = live(rel); if (!f) throw new BldError(rel + ': not found'); return bytesOf(f); },
      async readRange(rel, a, n) { const f = live(rel); if (!f) throw new BldError(rel + ': not found'); return f instanceof Uint8Array ? f.slice(a, a + n) : new Uint8Array(await f.slice(a, a + n).arrayBuffer()); },
      async size(rel) { const f = live(rel); return f ? (f instanceof Uint8Array ? f.length : f.size) : 0; },
      async listdir(rel) {
        const d = dirs.get(key(rel)); const names = d ? [...d.values()] : [];
        for (const [k, [r]] of writes) { const dd = k.includes('/') ? k.slice(0, k.lastIndexOf('/')) : ''; if (dd === key(rel)) { const nm = r.split('/').pop(); if (!names.some(x => x.toLowerCase() === nm.toLowerCase())) names.push(nm); } }
        return lowerSort(names.filter(nm => { const k = (key(rel) ? key(rel) + '/' : '') + nm.toLowerCase(); return !removed.has(k) || writes.has(k); }));
      },
      async writeNew(rel, data) { const k = key(rel); removed.delete(k); writes.set(k, [rel, data]); },
      async remove(rel) { const k = key(rel); writes.delete(k); if (files.has(k)) { const f = files.get(k); const p = String(f.webkitRelativePath || f.name).split('/'); if (p.length > 1) p.shift(); removed.set(k, p.join('/')); } },
      writes, removed, files,
    };
  }
  function zipOf(entries) {              // [[path, Uint8Array]] -> Uint8Array, stored (no compression)
    const parts = [], central = []; let off = 0;
    for (const [name, data] of entries) {
      const nm = new TextEncoder().encode(name), crc = (crc32(data) ^ 0xFFFFFFFF) >>> 0;
      const h = new Uint8Array(30 + nm.length);
      wrU32(h, 0, 0x04034b50); wrU16(h, 4, 20); wrU16(h, 6, 0x0800); wrU16(h, 8, 0); wrU32(h, 14, crc); wrU32(h, 18, data.length); wrU32(h, 22, data.length); wrU16(h, 26, nm.length); h.set(nm, 30);
      const c = new Uint8Array(46 + nm.length);
      wrU32(c, 0, 0x02014b50); wrU16(c, 4, 20); wrU16(c, 6, 20); wrU16(c, 8, 0x0800); wrU32(c, 16, crc); wrU32(c, 20, data.length); wrU32(c, 24, data.length); wrU16(c, 28, nm.length); wrU32(c, 42, off); c.set(nm, 46);
      parts.push(h, data); central.push(c); off += h.length + data.length;
    }
    const cd = u8cat(central), end = new Uint8Array(22);
    wrU32(end, 0, 0x06054b50); wrU16(end, 8, entries.length); wrU16(end, 10, entries.length); wrU32(end, 12, cd.length); wrU32(end, 16, off);
    return u8cat([...parts, cd, end]);
  }

  // ================================================================================================ Web Worker
  // The worker gets this library from BLDWEB_LIB's own source, so the page works opened from disk (no fetch).
  function workerMain() {
    const B = self.BLDWEB;
    self.onmessage = async ev => {
      const { id, job, files, names } = ev.data;
      try {
        const map = new Map(Object.entries(files)); map._names = names;
        const fs = B.filesFS(map);
        const res = await B.renderJob(job, fs, (k, n) => self.postMessage({ id, progress: [k, n] }));
        const frames = [], tr = [];
        for (const [k, [im, LT]] of res.frames) { frames.push([k, im.w, im.h, im.d, LT]); tr.push(im.d.buffer); }
        self.postMessage({ id, frames, info: res.info }, tr);
      } catch (e) { self.postMessage({ id, error: String(e && e.message || e) }); }
    };
  }
  function makeWorkerRenderer(onProgress) {
    const src = '"use strict";\nself.BLDWEB = (' + BLDWEB_LIB.toString() + ')();\n(' + workerMain.toString() + ')();\n';
    let url = null, worker = null, mode = 'inline', broken = false;
    try { url = URL.createObjectURL(new Blob([src], { type: 'text/javascript' })); worker = new Worker(url); mode = 'worker (blob)'; }
    catch (e) {
      try { worker = new Worker('data:text/javascript;charset=utf-8,' + encodeURIComponent(src)); mode = 'worker (data)'; }
      catch (e2) { worker = null; }
    }
    api_.lastWorkerMode = mode;
    let seq = 0; const pending = new Map();
    if (worker) {
      worker.onmessage = ev => {
        const m = ev.data, p = pending.get(m.id); if (!p) return;
        if (m.progress) { if (onProgress) onProgress(p.job, m.progress[0], m.progress[1]); return; }
        pending.delete(m.id);
        if (m.error) p.reject(new BldError(m.error));
        else { const fr_ = new Map(); for (const [k, w, h, d, LT] of m.frames) fr_.set(k, [{ w, h, d: new Uint8Array(d) }, LT]); p.resolve({ frames: fr_, info: m.info }); }
      };
      // a worker that cannot start (some browsers refuse blob workers on file:// pages) -> render on the page
      worker.onerror = ev => { broken = true; api_.lastWorkerMode = 'inline (worker failed: ' + (ev.message || 'error') + ')'; for (const p of pending.values()) p.fallback(); pending.clear(); };
    }
    // the models folder's files that one OBJ needs: the OBJ, its MTL files and their textures
    async function filesFor(job, folder) {
      const out = {}, names = [];
      const add = async rel => { if (rel === null) return null; const b = await folder.get(rel); if (b) { out[rel.toLowerCase()] = b; names.push(rel); } return b; };
      const obj = await add(job.file); if (!obj) throw new BldError(job.file + ': not found');
      const base = dirOf(job.file);
      for (const ln of pyLines(utf8Dec().decode(obj))) {
        const p = pySplit(ln);
        if (p[0] !== 'mtllib') continue;
        for (const nm of p.slice(1)) {
          const mrel = joinRel(base, nm), mb = await add(mrel); if (!mb) continue;
          for (const l2 of pyLines(utf8Dec().decode(mb))) {
            const q = pySplit(l2);
            if (q.length > 1 && q[0].toLowerCase() === 'map_kd') await add(joinRel(dirOf(mrel), q[q.length - 1]));
          }
        }
      }
      return { files: out, names };
    }
    const inline = (job, folder) => renderJob(job, folder, (k, n) => { if (onProgress) onProgress(job, k, n); });
    const render = async (job, folder) => {
      if (!worker || broken) return inline(job, folder);
      const { files, names } = await filesFor(job, folder);
      const id = ++seq;
      return new Promise((resolve, reject) => {
        pending.set(id, { resolve, reject, job, fallback: () => inline(job, folder).then(resolve, reject) });
        worker.postMessage({ id, job, files, names });
      });
    };
    render.terminate = () => { if (worker) worker.terminate(); if (url) URL.revokeObjectURL(url); };
    render.mode = () => api_.lastWorkerMode;
    return render;
  }

  const api_ = {
    BldError, version: '2026-11-18d',
    // pieces (exported for the tests)
    fma, sha256, pyJson, pyJsonStr, cp1252Encode, rint, decodePNG, slotMesh, powf, encodePNG, decodeImage, pilMedianCut, paletteCut, pilResize, qfsCompress, qfsDecompress,
    loadObj, place, renderModel, joinRel, dirOf, renderFrame, grassNorm, readBld, previewFrames, batFrames, sideMatch, ixfBuildings, bldFrames, recordFromImage, spanToImage,
    records, slots, classTable, portTable, ruleFamilies, stockBuildings, styleOf, STYLES, PORTS, PORT_MAX_COPIES,
    // the tool
    readModels, idsFor, plan, renderOne, renderJob, buildFiles, sources, applyFiles, install, restore, describe,
    handleFS, filesFS, listFS, zipOf, makeWorkerRenderer, suggestClass, CLASS_LABEL, DEFAULT_CLASS, OVL, STATE_DIR, PIX_DAT, BUILD_DIR, GROUP,
    ID_FIRST, ID_LAST, lastWorkerMode: null,
  };
  return api_;
}

globalThis.BLDWEB = BLDWEB_LIB();
globalThis.BLDWEB_LIB = BLDWEB_LIB;
if (typeof module === 'object' && module.exports) module.exports = globalThis.BLDWEB;
