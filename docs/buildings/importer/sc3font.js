/* sc3font.js - sc3ui3 (round 2026-11-19b): the game's own UI fonts in the importer page, built at run time.

   gamefont (round 2026-11-19d): the owner then chose to publish web fonts built from the FBF files (docs/assets/fonts/,
   re/tools/sc3ui/build_fonts.mjs runs buildTTF below in node), so pages carry them through sc3ui.css. In the page this
   file is now the fallback: useGame() builds only when those faces did not load (publishedLoaded()).

   Owner call 2026-11-19 (sc3ui3): the page may draw its text with SimCity 3000's bitmap fonts. When the player
   chooses their game folder, this file reads the .FBF files
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
  // smoothfont (round 2026-11-20f): fonts the run-time builder traces as smooth outlines (the same switch as SMOOTH in
  // re/tools/sc3ui/build_fonts.mjs, keep the two lists equal). Empty = pixel squares. opts.smooth (a list) overrides.
  const SMOOTH = ['TITLE9', 'TITLE12'];   // owner 2026-11-20: "Smooth" (same list as build_fonts.mjs)
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

  // ------------------------------------------------------------------ smooth outlines (smoothfont, round 2026-11-20f)
  // Owner 2026-11-20: "can you make the comic sans font less pixelated?". Instead of one square per font pixel, the
  // glyph's coverage (15 levels on TITLE9 / TITLE12 / SERIF17) is read as samples of a smooth shape: upsampled S x S
  // with a Catmull-Rom kernel, cut at one iso level, the contour simplified (Douglas-Peucker) and drawn as a TrueType
  // quadratic B-spline (vertices become off-curve points, sharp corners stay on-curve). Advances, line height and
  // baseline are the same as the pixel build, so layout does not move. The iso level is picked per font so that the
  // outline's area equals the font's total coverage (ink mass kept): smoothFont() below.
  const SM = { S: 8, pad: 2, tol: 0.07, corner: 0.55 };   // samples per px, padding px, simplify px, corner cos limit
  function crKernel(t) {                                   // Catmull-Rom, a = -0.5
    t = Math.abs(t);
    if (t < 1) return 1.5 * t * t * t - 2.5 * t * t + 1;
    if (t < 2) return -0.5 * t * t * t + 2.5 * t * t - 4 * t + 2;
    return 0;
  }
  // coverage of glyph i upsampled: field[(gy * W) + gx], sample (gx, gy) at pixel position ((gx + 0.5) / S - pad, ...)
  function glyphField(f, i, opt) {
    const [l, t, r, b] = f.cells[i], gw = r - l, gh = b - t, S = opt.S, pad = opt.pad;
    const W = (gw + 2 * pad) * S, H = (gh + 2 * pad) * S;
    const cov = new Float64Array(gw * gh);
    for (let y = 0; y < gh; y++) for (let x = 0; x < gw; x++) cov[y * gw + x] = f.cov(i, x, y);
    const pos = k => (k + 0.5) / S - pad - 0.5;            // sample k -> continuous pixel-centre coordinate
    const wts = (n, m) => {                                // per sample: [first pixel, 4 weights]
      const out = [];
      for (let k = 0; k < n; k++) { const p = pos(k), p0 = Math.floor(p) - 1, w = []; for (let j = 0; j < 4; j++) w.push(crKernel(p - (p0 + j))); out.push([p0, w]); }
      return out;
    };
    const wx = wts(W, gw), wy = wts(H, gh), tmp = new Float64Array(W * gh), fld = new Float64Array(W * H);
    for (let y = 0; y < gh; y++) for (let gx = 0; gx < W; gx++) {
      const [p0, w] = wx[gx]; let s = 0;
      for (let j = 0; j < 4; j++) { const x = p0 + j; if (x >= 0 && x < gw) s += w[j] * cov[y * gw + x]; }
      tmp[y * W + gx] = s;
    }
    for (let gy = 0; gy < H; gy++) { const [p0, w] = wy[gy]; for (let gx = 0; gx < W; gx++) {
      let s = 0; for (let j = 0; j < 4; j++) { const y = p0 + j; if (y >= 0 && y < gh) s += w[j] * tmp[y * W + gx]; }
      fld[gy * W + gx] = s;
    } }
    let mass = 0; for (const c of cov) mass += c;
    return { fld, W, H, gw, gh, mass };
  }
  function fieldArea(F, T) { let n = 0; for (const v of F.fld) if (v >= T) n++; return n / (F.S2 || 1); }
  // marching squares on the field at level T: closed loops in pixel coordinates (x right, y down), each oriented so the
  // inside is on the right in y-up font space (TrueType's clockwise outer contours)
  function isoLoops(F, T, opt) {
    const { fld, W, H } = F, S = opt.S, pad = opt.pad;
    const v = (x, y) => (x < 0 || y < 0 || x >= W || y >= H) ? 0 : fld[y * W + x];
    const px = gx => (gx + 0.5) / S - pad, py = gy => (gy + 0.5) / S - pad;
    // crossing point on an edge: 'h' edge from (x,y) to (x+1,y), 'v' edge from (x,y) to (x,y+1)
    const pt = (kind, x, y) => {
      const a = v(x, y), b = kind === 'h' ? v(x + 1, y) : v(x, y + 1), t = (T - a) / (b - a);
      return kind === 'h' ? [px(x + t), py(y)] : [px(x), py(y + t)];
    };
    const next = new Map(), pos = new Map();
    for (let y = -1; y < H; y++) for (let x = -1; x < W; x++) {
      const a = v(x, y) >= T, b = v(x + 1, y) >= T, c = v(x + 1, y + 1) >= T, d = v(x, y + 1) >= T;
      const code = (a ? 8 : 0) | (b ? 4 : 0) | (c ? 2 : 0) | (d ? 1 : 0);
      if (code === 0 || code === 15) continue;
      const eT = 'h' + x + ',' + y, eR = 'v' + (x + 1) + ',' + y, eB = 'h' + x + ',' + (y + 1), eL = 'v' + x + ',' + y;
      const P = { [eT]: ['h', x, y], [eR]: ['v', x + 1, y], [eB]: ['h', x, y + 1], [eL]: ['v', x, y] };
      // segments as [from, to], inside on the right in y-up = on the left walking in y-down image coordinates.
      // Walking a square clockwise on screen (T, R, B, L), an inside corner sits on the walker's right in y-down, so
      // each segment runs from the edge where the walk leaves the inside to the edge where it enters it.
      const segs = [];
      const centre = (v(x, y) + v(x + 1, y) + v(x + 1, y + 1) + v(x, y + 1)) / 4 >= T;
      switch (code) {
        case 8: segs.push([eL, eT]); break;          // a only
        case 4: segs.push([eT, eR]); break;          // b
        case 2: segs.push([eR, eB]); break;          // c
        case 1: segs.push([eB, eL]); break;          // d
        case 12: segs.push([eL, eR]); break;         // a b
        case 6: segs.push([eT, eB]); break;          // b c
        case 3: segs.push([eR, eL]); break;          // c d
        case 9: segs.push([eB, eT]); break;          // d a
        case 14: segs.push([eL, eB]); break;         // not d
        case 13: segs.push([eB, eR]); break;         // not c
        case 11: segs.push([eR, eT]); break;         // not b
        case 7: segs.push([eT, eL]); break;          // not a
        case 10: if (centre) segs.push([eL, eB], [eR, eT]); else segs.push([eL, eT], [eR, eB]); break;   // a c
        case 5: if (centre) segs.push([eT, eL], [eB, eR]); else segs.push([eT, eR], [eB, eL]); break;    // b d
      }
      for (const [s, e] of segs) { next.set(s, e); if (!pos.has(s)) pos.set(s, pt(...P[s])); if (!pos.has(e)) pos.set(e, pt(...P[e])); }
    }
    const loops = [], done = new Set();
    for (const k0 of next.keys()) {
      if (done.has(k0)) continue;
      const loop = []; let k = k0;
      while (!done.has(k)) { done.add(k); loop.push(pos.get(k)); k = next.get(k); if (k === undefined) break; }
      if (loop.length >= 3) loops.push(loop);
    }
    return loops;
  }
  function simplify(pts, tol) {                            // Douglas-Peucker on a closed loop
    if (pts.length < 4) return pts;
    // split at the two points farthest apart so both halves are open polylines
    let i0 = 0, i1 = 0, best = -1;
    for (let k = 0; k < pts.length; k++) { const d = (pts[k][0] - pts[0][0]) ** 2 + (pts[k][1] - pts[0][1]) ** 2; if (d > best) { best = d; i1 = k; } }
    best = -1; for (let k = 0; k < pts.length; k++) { const d = (pts[k][0] - pts[i1][0]) ** 2 + (pts[k][1] - pts[i1][1]) ** 2; if (d > best) { best = d; i0 = k; } }
    const keep = new Uint8Array(pts.length); keep[i0] = keep[i1] = 1;
    const n = pts.length, idx = (a, b) => { const o = []; for (let k = a; ; k = (k + 1) % n) { o.push(k); if (k === b) break; } return o; };
    const dp = ids => {
      if (ids.length < 3) return;
      const A = pts[ids[0]], B = pts[ids[ids.length - 1]], dx = B[0] - A[0], dy = B[1] - A[1], L = Math.hypot(dx, dy) || 1e-9;
      let far = 0, fk = -1;
      for (let k = 1; k < ids.length - 1; k++) { const P = pts[ids[k]], d = Math.abs((P[0] - A[0]) * dy - (P[1] - A[1]) * dx) / L; if (d > far) { far = d; fk = k; } }
      if (far > tol) { keep[ids[fk]] = 1; dp(ids.slice(0, fk + 1)); dp(ids.slice(fk)); }
    };
    dp(idx(i0, i1)); dp(idx(i1, i0));
    return pts.filter((p, k) => keep[k]);
  }
  const loopArea = L => { let a = 0; for (let k = 0; k < L.length; k++) { const p = L[k], q = L[(k + 1) % L.length]; a += p[0] * q[1] - q[0] * p[1]; } return a / 2; };
  // one glyph as TrueType contours: [[x, y, onCurve], ...] in font units, y up from the baseline
  function smoothContours(f, i, T, opt) {
    const F = glyphField(f, i, opt), out = [];
    for (let L of isoLoops(F, T, opt)) {
      if (Math.abs(loopArea(L)) < 0.04) continue;          // specks under 1/25 px
      L = simplify(L, opt.tol);
      if (L.length < 3) continue;
      const n = L.length, pts = [];
      for (let k = 0; k < n; k++) {
        const a = L[(k + n - 1) % n], p = L[k], b = L[(k + 1) % n];
        const ux = p[0] - a[0], uy = p[1] - a[1], vx = b[0] - p[0], vy = b[1] - p[1];
        const cos = (ux * vx + uy * vy) / ((Math.hypot(ux, uy) * Math.hypot(vx, vy)) || 1e-9);
        pts.push([Math.round(p[0] * P), Math.round((f.base - p[1]) * P), cos < opt.corner ? 1 : 0]);
      }
      // drop repeats left by rounding
      const c = pts.filter((p, k) => { const q = pts[(k + 1) % pts.length]; return p[0] !== q[0] || p[1] !== q[1]; });
      if (c.length >= 3) out.push(c);
    }
    return out;
  }
  // the iso level whose outlines hold the font's ink mass (area of every glyph = sum of its coverage)
  function smoothLevel(f, glyphs, opt) {
    const F = glyphs.map(i => { const g = glyphField(f, i, opt); g.S2 = opt.S * opt.S; return g; });
    const mass = F.reduce((s, g) => s + g.mass, 0);
    let lo = 0.15, hi = 0.85;
    for (let it = 0; it < 30; it++) { const m = (lo + hi) / 2, a = F.reduce((s, g) => s + fieldArea(g, m), 0); if (a > mass) lo = m; else hi = m; }
    return (lo + hi) / 2;
  }

  function u16(a, v) { a.push((v >> 8) & 255, v & 255); }
  function i16(a, v) { u16(a, v & 0xffff); }
  function append(dst, src) { for (let k = 0; k < src.length; k++) dst.push(src[k]); }
  function u32(a, v) { a.push((v >>> 24) & 255, (v >>> 16) & 255, (v >>> 8) & 255, v & 255); }

  // width (font units) of the centred full-height bar that draws coverage c. Default: area = coverage. calibrate()
  // measures what this browser's rasteriser really draws for each width and passes its inverse here.
  const areaSide = c => Math.round(P * c);
  function buildTTF(fbfBytes, family, opts) {
    opts = opts || {};
    const f = parseFBF(fbfBytes), side = opts.side || areaSide;
    // smooth: true = traced outlines for an anti-aliased font (ignored for 1-bit ones unless smooth1bit),
    // or an object overriding SM (S, pad, tol, corner, level)
    const sm = (opts.smooth && (!f.oneBit || opts.smooth1bit)) ? Object.assign({}, SM, typeof opts.smooth === 'object' ? opts.smooth : {}) : null;
    let level = null;
    if (sm) {
      const ids = []; for (let i = 32; i < 256; i++) { const [l, , r] = f.cells[i]; if (r > l) ids.push(i); }
      level = sm.level || smoothLevel(f, ids, sm);
    }
    // glyph 0 = .notdef (empty), then every byte value with a cell or an advance
    const gl = [{ byte: -1, adv: 0, boxes: [] }];
    const cmap = [];
    for (let i = 32; i < 256; i++) {
      const [l, , r, , adv] = f.cells[i];
      if (r <= l && !adv) continue;
      const u = i >= 0x80 && i < 0xA0 ? CP1252[i - 0x80] : i;
      if (!u) continue;
      cmap.push([u, gl.length]);
      if (sm) gl.push({ byte: i, adv: adv * P, boxes: [], contours: r > l ? smoothContours(f, i, level, sm) : [] });
      else gl.push({ byte: i, adv: adv * P, boxes: r > l ? glyphContours(f, i, side) : [] });
    }
    return Object.assign(writeTTF(gl, cmap, f.line, f.base, family, { colr: opts.colr }), { oneBit: f.oneBit, smooth: !!sm, level });
  }

  // a contour whose first point is off-curve starts at the implied on-curve midpoint instead (some rasterisers want one)
  function startOnCurve(c) {
    const k = c.findIndex(p => p[2]);
    if (k > 0) return c.slice(k).concat(c.slice(0, k));
    if (k === 0) return c;
    const a = c[c.length - 1], b = c[0];
    return [[Math.round((a[0] + b[0]) / 2), Math.round((a[1] + b[1]) / 2), 1]].concat(c);
  }
  function writeTTF(gl, cmap, line, base, family, opts) {
    const colr = !(opts && opts.colr === false);
    cmap.sort((a, b) => a[0] - b[0]);
    const asc = base * P, desc = (line - base) * P;
    let xMin = 0, yMin = 0, xMax = 0, yMax = 0, maxPts = 0, maxCont = 0, advMax = 0;
    const glyf = [], loca = [0];
    for (const g of gl) {
      advMax = Math.max(advMax, g.adv);
      // contours: boxes (the pixel build, 4 on-curve points each, clockwise) or smooth outlines ([x, y, on] lists)
      const cs = g.contours ? g.contours.map(startOnCurve)
        : g.boxes.map(([x0, y0, x1, y1]) => [[x0, y0, 1], [x0, y1, 1], [x1, y1, 1], [x1, y0, 1]]);   // clockwise, y up
      if (cs.length) {
        const a = [], pts = [].concat(...cs);
        const bx0 = Math.min(...pts.map(q => q[0])), by0 = Math.min(...pts.map(q => q[1]));
        const bx1 = Math.max(...pts.map(q => q[0])), by1 = Math.max(...pts.map(q => q[1]));
        g.xMin = bx0; xMin = Math.min(xMin, bx0); yMin = Math.min(yMin, by0); xMax = Math.max(xMax, bx1); yMax = Math.max(yMax, by1);
        i16(a, cs.length); i16(a, bx0); i16(a, by0); i16(a, bx1); i16(a, by1);
        let end = -1; for (const c of cs) { end += c.length; u16(a, end); }
        u16(a, 0);                                     // no instructions
        for (const p of pts) a.push(p[2] ? 1 : 0);     // on / off curve, x and y as int16 deltas
        let px = 0; for (const [x] of pts) { i16(a, x - px); px = x; }
        let py = 0; for (const [, y] of pts) { i16(a, y - py); py = y; }
        while (a.length % 4) a.push(0);
        append(glyf, a);
        maxPts = Math.max(maxPts, pts.length); maxCont = Math.max(maxCont, cs.length);
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
    if (colr) {
      const inked = gl.map((g, k) => [k, g]).filter(([k, g]) => k && (g.contours ? g.contours.length : g.boxes.length));
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
  // the inverse of a measured table: for a wanted coverage c, the bar width (0..64 units) that draws closest to it.
  // Also used by re/tools/sc3ui/build_fonts.mjs with the table it measured in Chrome (font_calibration.json).
  function sideFrom(got) {
    return c => { let best = 0, bd = 9; for (let k = 0; k <= 64; k++) { const d = Math.abs(got[k] - c); if (d < bd) { bd = d; best = k; } } return best; };
  }
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
      calib = { got, side: sideFrom(got) };
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
        const sm = (opts.smooth || SMOOTH).includes(nm);
        const t = buildTTF(bytes, family.replace(/[()]/g, '').trim(), sm ? { side, smooth: true, smooth1bit: true } : { side });
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
  // gamefont (round 2026-11-19d): sc3ui.css now carries the game fonts as published web fonts (docs/assets/fonts/,
  // inlined in the importer by sync_css.py). This run-time builder is the fallback: it only builds from the player's
  // game folder when those faces did not load. opts.force builds anyway (sc3font_test.html).
  async function publishedLoaded() {
    if (typeof document === 'undefined' || !document.fonts) return false;
    try { const f = await document.fonts.load('400 12.5px "SC3 Main"', 'Aa'); return f.length > 0 && f.every(x => x.status === 'loaded'); }
    catch (e) { return false; }
  }
  async function useGame(src, opts) {
    opts = opts || {};
    if (!opts.force && await publishedLoaded()) { if (root.console) console.info('sc3font: the published game fonts are in use'); return null; }
    if (!src) return null;
    try { const info = await load(src, opts); apply(info, opts); return info; }
    catch (e) { if (root.console) console.info('sc3font: game fonts not used:', e.message); return null; }
  }

  root.SC3Font = { load, apply, reset, useGame, publishedLoaded, buildTTF, parseFBF, calibrate, sideFrom, FONTS, TOKENS, SMOOTH };
})(typeof window !== 'undefined' ? window : globalThis);
