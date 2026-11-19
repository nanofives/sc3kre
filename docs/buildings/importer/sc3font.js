/* sc3font.js - sc3ui3 (round 2026-11-19b): the game's own UI fonts in the importer page, built at run time.

   Owner call 2026-11-19: the page may draw its text with SimCity 3000's bitmap fonts, but those fonts are never
   published. So nothing here ships a font: when the player chooses their game folder, this file reads the .FBF files
   from that folder (Apps\Res\Text\<language>\), turns each glyph's pixels into a TrueType outline in memory, registers
   the result with the FontFace API and points the page's sc3ui.css type tokens (--ui-type-*) at it. Without a game
   folder the page keeps its free fonts. Nothing is cached or stored: the fonts live as long as the page.

   FBF layout (re/tools/sc3ui/fbf.py, UI_STYLE.md "FBF bitmap fonts"): u32 1, u32 sheet width, u32 sheet height, u32 1;
   width*height bytes of sheet (16 = key, 1..15 = coverage, 1 = full ink); u16[256] RGB565 palette; 256 x 5 u32 glyph
   cells per byte value: left, top, right, bottom (exclusive), advance. Every cell is one line tall and starts at the
   line top. The byte values are the game's Windows-1252 text.

   Outlines: one font pixel = 64 units, 1024 units per em, so font-size 16 px draws one font pixel per CSS px. Full-ink
   pixels become rectangles (row runs, merged down when identical). A partial-coverage pixel (TITLE9, TITLE12,
   SERIF17 are anti-aliased) becomes a full-height bar, centred, whose width is the coverage (in 1/64 steps, picked by
   calibrate() from what the browser really draws). The baseline is the row under the bottom of the font's 'H'.
   Every glyph is also a COLR v1 colour glyph painted in the text colour: Chrome then rasterises it with its own
   FreeType path, whose coverage is exact, instead of DirectWrite's ClearType filter (sc3font_check.py: 0 pixels
   differ on the 1-bit fonts, coverage within 0.012 on the anti-aliased ones). CSS color applies as usual.

   Crisp text needs one font pixel to land on whole device pixels. apply() snaps the font pixel to the nearest whole
   number of device pixels for the page's --ui-scale (mode 'snap', the default): at --ui-scale 1.25 on a 100% screen
   the text is drawn at the game's own size, at 200% it is two device pixels per font pixel. mode 'scale' follows
   --ui-scale exactly (smooth, not crisp).

   Use:
     const info = await SC3Font.useGame(game);    // game: a FileSystemDirectoryHandle, a bldweb FS (exists / read),
                                                  // a File list from <input webkitdirectory>, or a URL string
     SC3Font.reset();                             // back to the free fonts
   useGame never throws: it returns null (and leaves the page as it was) when the folder has no fonts.
*/
(function (root) {
  'use strict';

  const FONTS = {            // FBF -> the sc3ui.css role it takes over (UI_STYLE.md "Which font draws what")
    MAIN9: 'labels, headings, lists, info bar, ticker',
    MAIN10: 'the query dialog building name',
    SYSTEM9: 'dropdown and table rows',
    TITLE9: 'pill buttons',
    TITLE12: 'title bars',
    SERIF17: 'main menu',
  };
  // token -> [FBF, line height in game px] (the sc3ui.css token keeps its own line height)
  const TOKENS = {
    '--ui-type-ui': ['MAIN9', 18], '--ui-type-prose': ['MAIN9', 18], '--ui-type-row': ['SYSTEM9', 18],
    '--ui-type-name': ['MAIN10', 18], '--ui-type-title': ['TITLE12', 28], '--ui-type-btn': ['TITLE9', 19],
  };
  const SPACING = ['--ui-ls-ui', '--ui-ls-row', '--ui-ls-name', '--ui-ls-title', '--ui-ls-btn'];
  const LANGS = ['ENGLISH', 'English-UK', 'GERMAN', 'FRENCH', 'ITALIAN', 'DUTCH', 'SWEDISH'];
  const P = 64, UPM = 1024, KEY = 16;
  const CP1252 = [0x20AC, 0, 0x201A, 0x0192, 0x201E, 0x2026, 0x2020, 0x2021, 0x02C6, 0x2030, 0x0160, 0x2039, 0x0152, 0, 0x017D, 0,
    0, 0x2018, 0x2019, 0x201C, 0x201D, 0x2022, 0x2013, 0x2014, 0x02DC, 0x2122, 0x0161, 0x203A, 0x0153, 0, 0x017E, 0x0178];

  // ------------------------------------------------------------------ FBF
  function parseFBF(bytes) {
    const b = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
    const dv = new DataView(b.buffer, b.byteOffset, b.byteLength);
    const w = dv.getUint32(4, true), h = dv.getUint32(8, true), n = w * h;
    if (dv.getUint32(0, true) !== 1 || w === 0 || h === 0 || 16 + n + 512 + 256 * 20 !== b.length)
      throw new Error('not an FBF font (' + b.length + ' bytes)');
    const sheet = b.subarray(16, 16 + n), tab = 16 + n + 512, cells = [];
    let line = 0;
    for (let i = 0; i < 256; i++) {
      const o = tab + i * 20, c = [0, 4, 8, 12, 16].map(k => dv.getUint32(o + k, true));
      cells.push(c); line = Math.max(line, c[3] - c[1]);
    }
    let levels = new Set();
    for (let i = 0; i < n; i++) if (sheet[i] >= 1 && sheet[i] <= 15) levels.add(sheet[i]);
    const oneBit = levels.size === 1 && levels.has(1);
    if (![...levels].length) throw new Error('FBF has no ink');
    for (let i = 0; i < n; i++) if (sheet[i] > 17) throw new Error('FBF is a colour sheet, not coverage');
    const cov = (i, x, y) => {                       // 0..1 for glyph i, cell pixel (x, y)
      const [l, t] = cells[i], v = sheet[(t + y) * w + l + x];
      if (v < 1 || v > 15) return 0;
      return oneBit ? (v === 1 ? 1 : 0) : (16 - v) / 15;
    };
    // baseline: under the bottom ink row of 'H'
    const H = 72, [hl, ht, hr, hb] = cells[H];
    let base = line;
    for (let y = hb - ht - 1; y >= 0; y--) { let ink = false; for (let x = 0; x < hr - hl; x++) if (cov(H, x, y) > 0.5) ink = true; if (ink) { base = y + 1; break; } }
    return { w, h, line, base, cells, cov, oneBit };
  }

  // ------------------------------------------------------------------ TrueType writer
  function glyphContours(f, i, side) {
    const [l, t, r, b] = f.cells[i], gw = r - l, gh = b - t, rects = [];
    const open = new Map();                          // "x0,x1" -> rect being extended downwards
    for (let y = 0; y < gh; y++) {
      const seen = new Set();
      let x = 0;
      while (x < gw) {
        if (f.cov(i, x, y) >= 1) {
          const s = x; while (x < gw && f.cov(i, x, y) >= 1) x++;
          const k = s + ',' + x, o = open.get(k);
          if (o && o.y1 === y) { o.y1 = y + 1; } else { const nr = { x0: s, x1: x, y0: y, y1: y + 1 }; rects.push(nr); open.set(k, nr); }
          seen.add(k);
        } else x++;
      }
      for (const k of [...open.keys()]) if (!seen.has(k)) open.delete(k);
    }
    const out = [];
    const up = y => (f.base - y) * P;                // cell row -> font units, y up from the baseline
    for (const q of rects) out.push([q.x0 * P, up(q.y1), q.x1 * P, up(q.y0)]);
    if (!f.oneBit) for (let y = 0; y < gh; y++) for (let x = 0; x < gw; x++) {
      const c = f.cov(i, x, y);
      if (c > 0 && c < 1) {
        const s = side(c); if (!s) continue;
        const m = (P - s) >> 1;                       // a full-height bar s units wide, centred in the pixel
        out.push([x * P + m, up(y + 1), x * P + m + s, up(y)]);
      }
    }
    return out;                                      // [x0, y0, x1, y1] boxes, y up
  }

  function u16(a, v) { a.push((v >> 8) & 255, v & 255); }
  function i16(a, v) { u16(a, v & 0xffff); }
  function append(dst, src) { for (let k = 0; k < src.length; k++) dst.push(src[k]); }
  function u32(a, v) { a.push((v >>> 24) & 255, (v >>> 16) & 255, (v >>> 8) & 255, v & 255); }

  // width (font units) of the centred full-height bar that draws coverage c. Default: area = coverage. calibrate()
  // measures what this browser's rasteriser really draws for each width and passes its inverse here.
  const areaSide = c => Math.round(P * c);
  function buildTTF(fbfBytes, family, opts) {
    const f = parseFBF(fbfBytes), side = (opts && opts.side) || areaSide;
    // glyph 0 = .notdef (empty), then every byte value with a cell or an advance
    const gl = [{ byte: -1, adv: 0, boxes: [] }];
    const cmap = [];
    for (let i = 32; i < 256; i++) {
      const [l, , r, , adv] = f.cells[i];
      if (r <= l && !adv) continue;
      const u = i >= 0x80 && i < 0xA0 ? CP1252[i - 0x80] : i;
      if (!u) continue;
      cmap.push([u, gl.length]);
      gl.push({ byte: i, adv: adv * P, boxes: r > l ? glyphContours(f, i, side) : [] });
    }
    return Object.assign(writeTTF(gl, cmap, f.line, f.base, family), { oneBit: f.oneBit });
  }

  function writeTTF(gl, cmap, line, base, family) {
    cmap.sort((a, b) => a[0] - b[0]);
    const asc = base * P, desc = (line - base) * P;
    let xMin = 0, yMin = 0, xMax = 0, yMax = 0, maxPts = 0, maxCont = 0, advMax = 0;
    const glyf = [], loca = [0];
    for (const g of gl) {
      advMax = Math.max(advMax, g.adv);
      if (g.boxes.length) {
        const a = [];
        const bx0 = Math.min(...g.boxes.map(q => q[0])), by0 = Math.min(...g.boxes.map(q => q[1]));
        const bx1 = Math.max(...g.boxes.map(q => q[2])), by1 = Math.max(...g.boxes.map(q => q[3]));
        g.xMin = bx0; xMin = Math.min(xMin, bx0); yMin = Math.min(yMin, by0); xMax = Math.max(xMax, bx1); yMax = Math.max(yMax, by1);
        i16(a, g.boxes.length); i16(a, bx0); i16(a, by0); i16(a, bx1); i16(a, by1);
        g.boxes.forEach((q, k) => u16(a, k * 4 + 3));
        u16(a, 0);                                     // no instructions
        const pts = [];
        for (const [x0, y0, x1, y1] of g.boxes) pts.push([x0, y0], [x0, y1], [x1, y1], [x1, y0]);   // clockwise, y up
        for (let k = 0; k < pts.length; k++) a.push(1); // on-curve, x and y as int16 deltas
        let px = 0; for (const [x] of pts) { i16(a, x - px); px = x; }
        let py = 0; for (const [, y] of pts) { i16(a, y - py); py = y; }
        while (a.length % 4) a.push(0);
        append(glyf, a);
        maxPts = Math.max(maxPts, pts.length); maxCont = Math.max(maxCont, g.boxes.length);
      } else g.xMin = 0;
      loca.push(glyf.length);
    }
    const n = gl.length, T = {};
    let a;
    a = []; u32(a, 0x00010000); u32(a, 0x00010000); u32(a, 0); u32(a, 0x5F0F3CF5); u16(a, 0x000B); u16(a, UPM);
    for (let k = 0; k < 4; k++) u32(a, 0);           // created, modified
    i16(a, xMin); i16(a, yMin); i16(a, xMax); i16(a, yMax); u16(a, 0); u16(a, 8); i16(a, 2); i16(a, 1); i16(a, 0);
    T.head = a;
    a = []; u32(a, 0x00010000); i16(a, asc); i16(a, -desc); i16(a, 0); u16(a, advMax); i16(a, 0); i16(a, 0); i16(a, xMax);
    i16(a, 1); i16(a, 0); i16(a, 0); for (let k = 0; k < 5; k++) i16(a, 0); u16(a, n);
    T.hhea = a;
    a = []; u32(a, 0x00010000); u16(a, n); u16(a, maxPts); u16(a, maxCont); u16(a, 0); u16(a, 0); u16(a, 2);
    for (let k = 0; k < 8; k++) u16(a, 0);
    T.maxp = a;
    a = []; u16(a, 3); i16(a, Math.round(advMax / 2)); u16(a, 400); u16(a, 5); u16(a, 0);
    for (let k = 0; k < 8; k++) i16(a, P * 4); i16(a, P); i16(a, asc / 3 | 0); i16(a, 0);
    for (let k = 0; k < 10; k++) a.push(0);          // panose
    u32(a, 3); u32(a, 0); u32(a, 0); u32(a, 0);        // Basic Latin + Latin-1
    a.push(83, 67, 51, 32);                          // vendor 'SC3 '
    u16(a, 0x40); u16(a, cmap.length ? cmap[0][0] : 32); u16(a, cmap.length ? Math.min(0xffff, cmap[cmap.length - 1][0]) : 32);
    i16(a, asc); i16(a, -desc); i16(a, 0); u16(a, asc); u16(a, desc); u32(a, 1); u32(a, 0);
    i16(a, 7 * P); i16(a, 9 * P); u16(a, 0); u16(a, 32); u16(a, 0);
    T['OS/2'] = a;
    a = []; for (const g of gl) { u16(a, g.adv); i16(a, g.xMin); } T.hmtx = a;
    // cmap format 4: runs of consecutive code points with consecutive glyph ids
    const segs = [];
    for (const [u, g] of cmap) {
      if (u > 0xfffe) continue;
      const s = segs[segs.length - 1];
      if (s && u === s.end + 1 && g === s.g0 + (u - s.start)) s.end = u; else segs.push({ start: u, end: u, g0: g });
    }
    segs.push({ start: 0xffff, end: 0xffff, g0: 1 });  // terminator, delta 1 -> glyph 0
    const sc = segs.length, sr = 2 * Math.pow(2, Math.floor(Math.log2(sc))), sub = [];
    u16(sub, 4); u16(sub, 16 + sc * 8); u16(sub, 0); u16(sub, sc * 2); u16(sub, sr); u16(sub, Math.log2(sr / 2)); u16(sub, sc * 2 - sr);
    segs.forEach(s => u16(sub, s.end)); u16(sub, 0); segs.forEach(s => u16(sub, s.start));
    segs.forEach(s => u16(sub, (s.g0 - s.start) & 0xffff)); segs.forEach(() => u16(sub, 0));
    a = []; u16(a, 0); u16(a, 1); u16(a, 3); u16(a, 1); u32(a, 12); append(a, sub); T.cmap = a;
    a = []; for (const o of loca) u32(a, o); T.loca = a;
    T.glyf = glyf.length ? glyf : [0, 0, 0, 0];
    const names = [family, 'Regular', family + ' (built in the page from the player game files)', family, 'Version 1.0', family.replace(/[^A-Za-z0-9-]/g, '')];
    const nm = [], strs = [];
    let off = 0;
    u16(nm, 0); u16(nm, names.length); u16(nm, 6 + names.length * 12);
    names.forEach((s, k) => {
      const e = []; for (const ch of s) { const c = ch.codePointAt(0); u16(e, c < 0x10000 ? c : 63); }
      u16(nm, 3); u16(nm, 1); u16(nm, 0x409); u16(nm, k + 1); u16(nm, e.length); u16(nm, off); off += e.length; append(strs, e);
    });
    T.name = nm.concat(strs);
    a = []; u32(a, 0x00030000); u32(a, 0); i16(a, -P); i16(a, P); for (let k = 0; k < 5; k++) u32(a, 0); T.post = a;
    // COLR v1 + CPAL: every glyph is one layer of its own outline filled with the text colour (palette index 0xFFFF).
    // Chrome on Windows draws COLRv1 web fonts through its own FreeType rasteriser instead of DirectWrite, whose
    // ClearType-style filter spreads each pixel into its neighbours. FreeType's coverage of a pixel-aligned square is
    // exact, so a font pixel comes out as one screen pixel.
    {
      const inked = gl.map((g, k) => [k, g]).filter(([k, g]) => k && g.boxes.length);
      const bgl = []; u32(bgl, inked.length);
      const paints = [];
      inked.forEach(([k], j) => { u16(bgl, k); u32(bgl, 4 + inked.length * 6 + j * 6); });
      const solidAt = inked.length * 6;
      inked.forEach(([k], j) => { const o = solidAt - j * 6; paints.push(10, (o >> 16) & 255, (o >> 8) & 255, o & 255); u16(paints, k); });
      paints.push(2); u16(paints, 0xffff); u16(paints, 0x4000);          // PaintSolid: foreground, alpha 1.0
      a = []; u16(a, 1); u16(a, 0); u32(a, 0); u32(a, 0); u16(a, 0); u32(a, 34); u32(a, 0); u32(a, 0); u32(a, 0); u32(a, 0);
      append(a, bgl); append(a, paints); T.COLR = a;
      a = []; u16(a, 0); u16(a, 1); u16(a, 1); u16(a, 1); u32(a, 14); u16(a, 0); a.push(0, 0, 0, 255); T.CPAL = a;
    }
    // sfnt directory, tables sorted by tag, 4-byte aligned, checksums
    const tags = Object.keys(T).sort(), nt = tags.length, es = Math.floor(Math.log2(nt)), srch = Math.pow(2, es) * 16;
    const dir = []; u32(dir, 0x00010000); u16(dir, nt); u16(dir, srch); u16(dir, es); u16(dir, nt * 16 - srch);
    let pos = 12 + nt * 16, headPos = 0; const body = [];
    const sum = arr => { let s = 0; for (let k = 0; k < arr.length; k += 4) s = (s + ((arr[k] << 24) | (arr[k + 1] << 16) | (arr[k + 2] << 8) | arr[k + 3])) >>> 0; return s; };
    for (const tg of tags) {
      const d = T[tg].slice(), len = d.length; while (d.length % 4) d.push(0);
      for (const ch of tg.padEnd(4)) dir.push(ch.charCodeAt(0));
      if (tg === 'head') headPos = pos;
      u32(dir, sum(d)); u32(dir, pos); u32(dir, len); append(body, d); pos += d.length;
    }
    const out = new Uint8Array(dir.length + body.length); out.set(dir); out.set(body, dir.length);
    const ho = headPos, adj = (0xB1B0AFBA - sum(Array.from(out))) >>> 0;
    out[ho + 8] = adj >>> 24; out[ho + 9] = (adj >>> 16) & 255; out[ho + 10] = (adj >>> 8) & 255; out[ho + 11] = adj & 255;
    return { buffer: out.buffer, line, base, glyphs: n };
  }

  // ------------------------------------------------------------------ calibration
  // The rasteriser does not draw a square of area c as coverage c: Chrome's FreeType path applies a contrast curve
  // (measured 2026-11-19). So the page draws one bar per width (1..64 units) in a canvas, reads back what came out,
  // and picks for each wanted coverage the width that draws it. A canvas draws
  // text through the same rasteriser as the page (sc3font_check.py checks the page itself). No canvas: area = coverage.
  let calib = null;
  async function calibrate() {
    if (calib) return calib;
    try {
      const gl = [{ adv: 0, boxes: [] }], cmap = [];
      for (let k = 1; k <= 64; k++) { const m = (P - k) >> 1; cmap.push([0x40 + k, gl.length]); gl.push({ adv: 2 * P, boxes: [[m, 0, m + k, P]] }); }
      const t = writeTTF(gl, cmap, 2, 1, 'SC3 calibration');
      const face = new FontFace('SC3 calibration', t.buffer); await face.load(); document.fonts.add(face);
      const cv = document.createElement('canvas'); cv.width = 132; cv.height = 4;
      const cx = cv.getContext('2d', { willReadFrequently: true });
      cx.font = '16px "SC3 calibration"'; cx.textBaseline = 'alphabetic'; cx.fillStyle = '#000';
      cx.fillText(String.fromCharCode(...cmap.map(c => c[0])), 0, 2);
      const px = cx.getImageData(0, 0, 132, 4).data, got = [0];
      for (let k = 1; k <= 64; k++) got.push(px[(1 * 132 + (k - 1) * 2) * 4 + 3] / 255);
      document.fonts.delete(face);
      if (!(got[64] > 0.95 && got[1] < 0.2)) throw new Error('calibration glyphs did not draw');
      calib = { got, side: c => { let best = 0, bd = 9; for (let k = 0; k <= 64; k++) { const d = Math.abs(got[k] - c); if (d < bd) { bd = d; best = k; } } return best; } };
    } catch (e) { calib = { got: null, side: areaSide, why: e.message }; }
    return calib;
  }

  // ------------------------------------------------------------------ reading the game folder
  function sourceOf(src) {
    if (!src) return null;
    if (typeof src === 'string') {                    // URL of the install folder (the test hook)
      const base = src.endsWith('/') ? src : src + '/';
      const read = async rel => { const r = await fetch(base + rel); if (!r.ok) throw new Error(rel + ': ' + r.status); return new Uint8Array(await r.arrayBuffer()); };
      return { read, exists: async rel => { try { await read(rel); return true; } catch (e) { return false; } }, listdir: async () => [] };
    }
    if (typeof src.read === 'function') return src;  // a bldweb FS
    if (typeof src.getDirectoryHandle === 'function') {   // FileSystemDirectoryHandle, case-insensitive walk
      const walk = async rel => {
        let h = src; const parts = rel.split('/').filter(Boolean);
        for (let k = 0; k < parts.length; k++) {
          let next = null;
          for await (const [nm, e] of h.entries()) if (nm.toLowerCase() === parts[k].toLowerCase()) { next = e; break; }
          if (!next) return null; h = next;
        }
        return h;
      };
      return {
        read: async rel => { const h = await walk(rel); if (!h || h.kind !== 'file') throw new Error(rel + ': not found'); return new Uint8Array(await (await h.getFile()).arrayBuffer()); },
        exists: async rel => { const h = await walk(rel); return !!h && h.kind === 'file'; },
        listdir: async rel => { const h = await walk(rel); const out = []; if (h && h.kind === 'directory') for await (const [nm] of h.entries()) out.push(nm); return out; },
      };
    }
    if (typeof src.length === 'number') {             // File list from <input webkitdirectory>
      const map = new Map();
      for (const fl of Array.from(src)) { const p = String(fl.webkitRelativePath || fl.name).split('/'); if (p.length > 1) p.shift(); map.set(p.join('/').toLowerCase(), fl); }
      return {
        read: async rel => { const fl = map.get(rel.toLowerCase()); if (!fl) throw new Error(rel + ': not found'); return new Uint8Array(await fl.arrayBuffer()); },
        exists: async rel => map.has(rel.toLowerCase()),
        listdir: async rel => { const pre = rel.toLowerCase().replace(/\/?$/, '/'); const s = new Set(); for (const k of map.keys()) if (k.startsWith(pre)) s.add(k.slice(pre.length).split('/')[0]); return [...s]; },
      };
    }
    return null;
  }

  async function findFile(fs, dir, name) {
    for (const c of [name + '.FBF', name + '.fbf', name.toLowerCase() + '.fbf']) if (await fs.exists(dir + '/' + c)) return dir + '/' + c;
    let names = []; try { names = await fs.listdir(dir); } catch (e) { /* no listing */ }
    const hit = names.find(x => x.toLowerCase() === name.toLowerCase() + '.fbf');
    return hit ? dir + '/' + hit : null;
  }

  async function load(src, opts) {
    opts = opts || {};
    const fs = sourceOf(src); if (!fs) throw new Error('no game folder');
    let langs = opts.lang ? [opts.lang] : LANGS.slice();
    try { for (const d of await fs.listdir('Apps/Res/Text')) if (!langs.some(x => x.toLowerCase() === d.toLowerCase())) langs.push(d); } catch (e) { /* ok */ }
    for (const lang of langs) {
      const dir = 'Apps/Res/Text/' + lang;
      const main = await findFile(fs, dir, 'MAIN9');
      if (!main) continue;
      const fonts = {};
      for (const nm of Object.keys(FONTS)) {
        const p = nm === 'MAIN9' ? main : await findFile(fs, dir, nm);
        if (!p) continue;
        const family = 'SC3 ' + nm + ' (game)';
        const bytes = await fs.read(p);
        const side = opts.calibrate === false ? areaSide : (await calibrate()).side;
        const t = buildTTF(bytes, family.replace(/[()]/g, '').trim(), { side });
        const face = new FontFace(family, t.buffer, { weight: '1 1000', style: 'normal' });
        await face.load();
        fonts[nm] = { family, line: t.line, base: t.base, glyphs: t.glyphs, face };
      }
      return { lang, fonts };
    }
    throw new Error('no FBF fonts under Apps\\Res\\Text');
  }

  // ------------------------------------------------------------------ switching the page
  let applied = null, mq = null;
  function pixel(mode) {
    const r = document.documentElement, scale = parseFloat(getComputedStyle(r).getPropertyValue('--ui-scale')) || 1;
    if (mode === 'scale') return scale;
    const dpr = root.devicePixelRatio || 1;
    return Math.max(1, Math.round(scale * dpr)) / dpr;
  }
  function apply(info, opts) {
    opts = opts || {};
    if (!info || !info.fonts.MAIN9) return false;
    const r = document.documentElement;
    if (!applied) {
      applied = { prev: {}, info };
      for (const k of [...Object.keys(TOKENS), ...SPACING, '--ui-font', '--ui-title-font', '--ui-gpx', 'font-synthesis'])
        applied.prev[k] = r.style.getPropertyValue(k);
    }
    for (const nm of Object.keys(info.fonts)) if (!document.fonts.has(info.fonts[nm].face)) document.fonts.add(info.fonts[nm].face);
    const px = pixel(opts.mode);
    r.style.setProperty('--ui-gpx', px + 'px');
    const fam = nm => '"' + (info.fonts[nm] || info.fonts.MAIN9).family + '"';
    for (const [k, [nm, lh]] of Object.entries(TOKENS))
      r.style.setProperty(k, '400 calc(16 * var(--ui-gpx)) / calc(' + lh + ' * var(--u)) ' + fam(nm) + ', ' + (nm.startsWith('TITLE') ? 'var(--ui-title-font)' : 'var(--ui-font)'));
    for (const k of SPACING) r.style.setProperty(k, '0px');
    r.style.setProperty('font-synthesis', 'none');
    r.dataset.sc3font = info.lang;
    if (!mq && root.matchMedia && opts.mode !== 'scale') {     // re-snap when the page moves to a screen with another scale
      const re = () => { if (applied) { apply(applied.info, opts); } mq.removeEventListener('change', re); mq = matchMedia('(resolution: ' + root.devicePixelRatio + 'dppx)'); mq.addEventListener('change', re); };
      mq = matchMedia('(resolution: ' + root.devicePixelRatio + 'dppx)'); mq.addEventListener('change', re);
    }
    return true;
  }
  function reset() {
    if (!applied) return;
    const r = document.documentElement;
    for (const [k, v] of Object.entries(applied.prev)) { if (v) r.style.setProperty(k, v); else r.style.removeProperty(k); }
    for (const f of Object.values(applied.info.fonts)) document.fonts.delete(f.face);
    delete r.dataset.sc3font; applied = null;
  }
  async function useGame(src, opts) {
    try { const info = await load(src, opts); apply(info, opts); return info; }
    catch (e) { if (root.console) console.info('sc3font: game fonts not used:', e.message); return null; }
  }

  root.SC3Font = { load, apply, reset, useGame, buildTTF, parseFBF, calibrate, FONTS, TOKENS };
})(typeof window !== 'undefined' ? window : globalThis);
