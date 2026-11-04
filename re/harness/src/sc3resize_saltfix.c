/* ================= SALTFIX (child/saltfix 2026-11-04): sea water is salt, rivers and lakes stay fresh
 * Owner: "what's the logic between salt water and regular water on big island maps? i see regular water in between
 * salt water, can we fix that?" Owner calls (2026-11-04): water linked to the sea turns salt only where it is wide;
 * channels 1-2 cells wide (rivers) and lakes not linked to the sea stay fresh. New terrain gets the rule by itself,
 * an existing city only when the player asks ("Recalcular agua salada", mods page C, applied on OK).
 *
 * Stock rule (SIMDIRT FUN_100181d6, called by the generator FUN_10017c2d): no flood fill. For each map edge in the
 * generator's 4-bit sea mask, every row / column casts a straight ray inward and marks every vertex on it salt
 * (FUN_100183eb into the bitmap at gen+0x20), land included, until (param & 0xff) * N >> 8 cells or 5 cells where
 * water < height - 1. Water behind a headland, an island or a shoal, or past the ray length, stays fresh.
 *
 * Data path [static reads, cited]:
 *   generator vtable SIMDIRT 0x10020be8: +0x1c Generate (0x10017c2d), +0x28 Apply-to-terrain (0x10017683). Apply
 *     copies height gen+0x14 -> terrain vt+0x84, then water gen+0x18 + the salt bit -> terrain vt+0x8c
 *     (0x10006220, SetWaterTable). Grids: +4 rows, +8 cols, +0xc row pointers (bytes). Salt bitmap: +4 rows,
 *     +0xc words per row, +0x10 row pointers (DWORD, bit y & 31 of word y >> 5).
 *   SetWaterTable: a salt vertex marks its 4 cells salt (at once, or through the pending bitmap terrain+0x48 that
 *     vt+0x2c 0x10005230 flushes: cell salt if any of its 4 corners is salt). A fresh vertex writes nothing; the
 *     generate message handler 0x10005500 clears every cell before it calls Apply.
 *   terrain vtable SIMDIRT 0x1002046c: +0x30 height grid (vt+0x4c), +0x38 water grid (vt+0x50), vt+0xb0/+0xb4 =
 *     vertex rows / cols. A vertex is under water when height <= water (tile test vt+0x54 = 0x100065f0).
 *   salt flag: city vt+0x16c -> SIMECO interface, vt+0x50 IsSaltWater(x, y) 0x10008d90, vt+0x90 SetIsSaltWater
 *     0x10008ecd = bit 0x40000000 of the pollution grid, one bit per 2x2 cells (shift 1, ctor 0x10004379 +0x14).
 *
 * The rule (sf_rule, one function for both paths; only new terrain also knows where its rivers were carved), R =
 * ceil(0.6 * sqrt(map side)) = 10 / 14 / 20 cells at 256 / 512 / 1024, L = 2R:
 *   water cell = any corner under water (height <= water).
 *   wide water = inside a (2R+1) x (2R+1) square that is all water and no river (off the map counts as water).
 *   sea        = flood from the map edge (wide water on the edge, or an edge run of 2R+1 water cells) through water,
 *                crossing at most L cells of narrow water in a row (wide water resets the count).
 *   salt       = the sea, through the game's own corner expansion over wet corners. Land is never salt.
 * So the open sea, its bays, the straits between islands and lochs behind a short neck are salt. Lakes are never
 * reached. A big lake that touches the map edge on 2R+1 cells counts as sea.
 * Rivers: a generated river is carved sqrt(N) * (water + 64) / 128 deep below the sea (SIMDIRT 0x100187da, banks
 * rising 2 per vertex, 0x10018b57): 13-16 cells wide at 256, and it flares into an estuary as wide as the sea floor is
 * deep where it meets the sea (30-40 cells measured at 256). On NEW terrain the carve itself is recorded (Generate's
 * call at 0x10018151 wrapped: land vertices it put under water), those cells never count as wide, so every generated
 * river, estuary included, only turns salt L cells from the sea. A saved city has no such record: the button sees
 * only shapes, so a river narrower than 2R+1 behaves the same, and an estuary wider than that is salt like a bay.
 * New terrain: the Apply slot (+0x28) recomputes gen+0x20 with the rule from the generator's final grids (the end
 * of Generate only rounds heights above sea + 2, which never changes what is under water), then runs the stock Apply.
 * A city: salt_recalc() reads the terrain's grids and writes the salt flag block by block.
 * SC3RESIZE_SALTFIX=0: nothing installed (stock rays, no button). SC3RESIZE_SALTFIX_DUMP=1: a BMP of the salt layer
 * before and after each pass, beside sc3resize.log (saltfix_<n>_<before|after>.bmp). */

static int g_saltfix = 1;
static int g_sf_dump = 0;
static int g_sf_dumpn = 0;
static HMODULE g_sf_dirt;
static DWORD g_sf_orig_apply;   /* generator vt+0x28 = SIMDIRT 0x10017683 */
static DWORD g_sf_rivers_fn;    /* SIMDIRT 0x100187da _createRivers, called from Generate at 0x10018151 */
static BYTE *g_sf_river;        /* vertex mask of the last carve: 1 = land the river carve put under water */
static void *g_sf_rgen;
static int   g_sf_rvx, g_sf_rvy;

typedef struct { int ok; int vx, vy; BYTE **h, **w; } SF_GRID;

/* a SIMDIRT byte grid: +4 rows, +8 cols, +0xc row pointers */
static int sf_grid(BYTE *g, int *rows, int *cols, BYTE ***rp) {
    if (!g || IsBadReadPtr(g, 0x10)) return 0;
    *rows = *(int *)(g + 4); *cols = *(int *)(g + 8); *rp = *(BYTE ***)(g + 0xc);
    if (*rows < 2 || *cols < 2 || *rows > 4097 || *cols > 4097 || !*rp || IsBadReadPtr(*rp, *rows * 4)) return 0;
    return 1;
}

static int sf_pair(BYTE *hg, BYTE *wg, SF_GRID *o) {
    int r2, c2;
    BYTE **w;
    o->ok = 0;
    if (!sf_grid(hg, &o->vx, &o->vy, &o->h) || !sf_grid(wg, &r2, &c2, &w)) return 0;
    if (r2 != o->vx || c2 != o->vy) return 0;
    o->w = w; o->ok = 1;
    return 1;
}

/* the open-water radius for a map of n cells a side: ceil(0.6 * sqrt(n)) = 10 at 256, 14 at 512, 20 at 1024.
   A generated river is carved sqrt(N) * (water + 64) / 128 deep below the sea (SIMDIRT 0x100187da) with banks rising
   2 per vertex (0x10018b57), so its underwater width grows with sqrt(N): 13-16 cells measured on a 256 map at the
   default water setting. A (2R+1) square does not fit in it at any size. */
static int sf_radius(int n) {
    int r = 1;
    while (r * r * 100 < 36 * n) r++;
    return r;
}

/* count of marked cells in the (2r+1) square around (x, y), from a (cx+1) x (cy+1) prefix-sum table; off the map
   counts 0 */
static int sf_box(const int *ps, int cx, int cy, int x, int y, int r) {
    int x0 = x - r < 0 ? 0 : x - r, y0 = y - r < 0 ? 0 : y - r;
    int x1 = x + r + 1 > cx ? cx : x + r + 1, y1 = y + r + 1 > cy ? cy : y + r + 1, w = cy + 1;
    return ps[x1 * w + y1] - ps[x0 * w + y1] - ps[x1 * w + y0] + ps[x0 * w + y0];
}

/* the in-map cell count of the same square */
static int sf_area(int cx, int cy, int x, int y, int r) {
    int x0 = x - r < 0 ? 0 : x - r, y0 = y - r < 0 ? 0 : y - r;
    int x1 = x + r + 1 > cx ? cx : x + r + 1, y1 = y + r + 1 > cy ? cy : y + r + 1;
    return (x1 - x0) * (y1 - y0);
}

static void sf_prefix(int *ps, const BYTE *m, BYTE want, int cx, int cy) {
    int x, y, w = cy + 1;
    for (y = 0; y <= cy; y++) ps[y] = 0;
    for (x = 0; x < cx; x++) {
        int run = 0;
        ps[(x + 1) * w] = 0;
        for (y = 0; y < cy; y++) { run += m[x * cy + y] == want; ps[(x + 1) * w + y + 1] = ps[x * w + y + 1] + run; }
    }
}

/* mark the border water cells that lie in a run of >= len water cells along that edge (the sea along an edge, not a
   river crossing it). idx(k) = the cell index of the k-th cell along the edge, n = edge length. */
static void sf_edge_runs(const BYTE *wat, BYTE *lab, int *q, int *qt, int n, int base, int step, int len) {
    int k = 0, j;
    while (k < n) {
        if (wat[base + k * step] != 1) { k++; continue; }
        j = k;
        while (j < n && wat[base + j * step] == 1) j++;
        if (j - k >= len) for (; k < j; k++) if (lab[base + k * step]) { lab[base + k * step] = 0; q[(*qt)++] = base + k * step; }
        k = j;
    }
}

/* out: vx*vy bytes, 1 = salt vertex. *salt_cells / *radius for the log. Returns the wide-water cell count, -1 = no memory.
     water cell  = any corner wet (height <= water), the game's own tile test (SIMDIRT 0x100065f0)
     river cell  = (new terrain only) a water cell whose wet corners were all made wet by the generator's river carve
     open water  = a water cell whose (2R+1) square is all non-river water, off the map counting as water
     wide water  = every cell of those squares (all water by construction)
     seeds       = open water on the map edge, and edge water in a run of >= 2R+1 cells along the edge (a thin sea
                   strip along an edge counts, a river crossing the edge does not)
     salt        = water reached 4-way from the seeds where no stretch of narrow (not wide) water on the way is longer
                   than L = 2R cells: the count goes back to 0 on wide water. So straits and narrow necks into wide
                   bays and lochs are crossed, a river (narrow for its whole length) only turns salt L cells from the
                   sea, lakes are never reached.
     salt vertex = a wet corner of a salt cell (the game marks a cell salt when any corner is: one more ring of water,
                   never a land cell, unlike the stock rays) */
static int sf_rule(const SF_GRID *g, const BYTE *rv, BYTE *out, int *salt_cells, int *radius) {
    int vx = g->vx, vy = g->vy, cx = vx - 1, cy = vy - 1, nc = cx * cy, x, y, i, n = 0, qh = 0, qt = 0, qn = 0, R, L, ns = 0, nr = 0;
    BYTE *wat = NULL, *st = NULL, *lab = NULL;   /* st bit 1 open, 2 wide, 4 queued */
    int *ps = NULL, *q = NULL;
    static const int dx[4] = { 1, -1, 0, 0 }, dy[4] = { 0, 0, 1, -1 };
    R = sf_radius(cx > cy ? cx : cy);
    if (R > 120) R = 120;
    L = 2 * R;
    *radius = R; *salt_cells = 0;
    wat = (BYTE *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, nc);
    st = (BYTE *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, nc);
    lab = (BYTE *)HeapAlloc(GetProcessHeap(), 0, nc);
    ps = (int *)HeapAlloc(GetProcessHeap(), 0, (SIZE_T)(cx + 1) * (cy + 1) * sizeof(int));
    q = (int *)HeapAlloc(GetProcessHeap(), 0, (SIZE_T)nc * sizeof(int));
    if (!wat || !st || !lab || !ps || !q) { n = -1; goto done; }
    memset(out, 0, vx * vy);
    memset(lab, 255, nc);
    for (x = 0; x < cx; x++) {
        const BYTE *h0 = g->h[x], *w0 = g->w[x], *h1 = g->h[x + 1], *w1 = g->w[x + 1];
        for (y = 0; y < cy; y++) {
            int w00 = h0[y] <= w0[y], w10 = h1[y] <= w1[y], w01 = h0[y + 1] <= w0[y + 1], w11 = h1[y + 1] <= w1[y + 1];
            BYTE v = (BYTE)(w00 || w10 || w01 || w11);
            /* river cell (2): every wet corner was made wet by the river carve (rv, new terrain only) */
            if (v && rv && (!w00 || rv[x * vy + y]) && (!w10 || rv[(x + 1) * vy + y]) &&
                (!w01 || rv[x * vy + y + 1]) && (!w11 || rv[(x + 1) * vy + y + 1])) { v = 2; nr++; }
            wat[x * cy + y] = v;
        }
    }
    sf_prefix(ps, wat, 1, cx, cy);   /* sea-type water cells: a river cell or land in the square stops it being open */
    for (x = 0; x < cx; x++) for (y = 0; y < cy; y++)
        if (wat[x * cy + y] == 1 && sf_box(ps, cx, cy, x, y, R) == sf_area(cx, cy, x, y, R)) st[x * cy + y] = 1;
    sf_prefix(ps, st, 1, cx, cy);    /* open cells */
    for (x = 0; x < cx; x++) for (y = 0; y < cy; y++)
        if (wat[x * cy + y] && sf_box(ps, cx, cy, x, y, R)) { st[x * cy + y] |= 2; n++; }
    /* seeds (lab 0) */
    for (x = 0; x < cx; x++) for (y = 0; y < cy; y++)
        if ((st[x * cy + y] & 1) && (x == 0 || y == 0 || x == cx - 1 || y == cy - 1)) { lab[x * cy + y] = 0; q[qt++] = x * cy + y; }
    sf_edge_runs(wat, lab, q, &qt, cy, 0, 1, 2 * R + 1);                 /* x = 0 */
    sf_edge_runs(wat, lab, q, &qt, cy, (cx - 1) * cy, 1, 2 * R + 1);     /* x = cx-1 */
    sf_edge_runs(wat, lab, q, &qt, cx, 0, cy, 2 * R + 1);                /* y = 0 */
    sf_edge_runs(wat, lab, q, &qt, cx, cy - 1, cy, 2 * R + 1);           /* y = cy-1 */
    for (i = 0; i < qt; i++) st[q[i]] |= 4;
    qn = qt;   /* ring buffer of nc: a cell is in it at most once (bit 4) */
    qt %= nc;
    while (qn > 0) {
        int c = q[qh], ccx = c / cy, ccy = c % cy, l;
        qh = (qh + 1) % nc; qn--;
        st[c] &= ~4;
        l = lab[c];
        for (i = 0; i < 4; i++) {
            int ax = ccx + dx[i], ay = ccy + dy[i], a2, nl;
            if (ax < 0 || ay < 0 || ax >= cx || ay >= cy) continue;
            a2 = ax * cy + ay;
            if (!wat[a2]) continue;
            nl = (st[a2] & 2) ? 0 : l + 1;
            if (nl > L || nl >= lab[a2]) continue;
            lab[a2] = (BYTE)nl;
            if (!(st[a2] & 4)) { st[a2] |= 4; q[qt] = a2; qt = (qt + 1) % nc; qn++; }
        }
    }
    for (x = 0; x < cx; x++) for (y = 0; y < cy; y++) if (lab[x * cy + y] != 255) {   /* wet corners only: land stays clear */
        int i2, j2;
        ns++;
        for (i2 = x; i2 <= x + 1; i2++) for (j2 = y; j2 <= y + 1; j2++)
            if (g->h[i2][j2] <= g->w[i2][j2]) out[i2 * vy + j2] = 1;
    }
    *salt_cells = ns;
    if (rv) logf("SALTFIX> river cells from the generator's carve: %d (never wide, salt at most %d cells from the sea)", nr, L);
done:
    if (wat) HeapFree(GetProcessHeap(), 0, wat);
    if (st) HeapFree(GetProcessHeap(), 0, st);
    if (lab) HeapFree(GetProcessHeap(), 0, lab);
    if (ps) HeapFree(GetProcessHeap(), 0, ps);
    if (q) HeapFree(GetProcessHeap(), 0, q);
    return n;
}

/* cell picture: land, fresh water, salt water. salt: 1 byte per cell. Pixel (col x, row y), y = 0 at the top. */
static void sf_dump(const SF_GRID *g, const BYTE *salt, const char *tag, int seq) {
    char p[MAX_PATH], leaf[64];
    int cx = g->vx - 1, cy = g->vy - 1, x, y, row = (cx * 3 + 3) & ~3;
    BYTE *buf;
    BITMAPFILEHEADER fh;
    BITMAPINFOHEADER ih;
    HANDLE f;
    DWORD wr;
    if (!g_sf_dump) return;
    wsprintfA(leaf, "saltfix_%02d_%s.bmp", seq, tag);
    rz_mb_path(p, sizeof(p), leaf);
    buf = (BYTE *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, (SIZE_T)row * cy);
    if (!buf) return;
    for (y = 0; y < cy; y++) for (x = 0; x < cx; x++) {
        BYTE *px = buf + (SIZE_T)(cy - 1 - y) * row + x * 3;   /* bottom-up rows */
        int water = g->h[x][y] <= g->w[x][y] || g->h[x + 1][y] <= g->w[x + 1][y] ||
                    g->h[x][y + 1] <= g->w[x][y + 1] || g->h[x + 1][y + 1] <= g->w[x + 1][y + 1];
        int s = salt[x * cy + y];
        if (water && s)      { px[0] = 140; px[1] = 40;  px[2] = 20;  }   /* salt: navy (BGR) */
        else if (water)      { px[0] = 255; px[1] = 220; px[2] = 110; }   /* fresh: light cyan */
        else if (s)          { px[0] = 0;   px[1] = 0;   px[2] = 230; }   /* salt land: red (stock rays do this) */
        else { BYTE a = g->h[x][y]; px[0] = (BYTE)(40 + a / 4); px[1] = (BYTE)(110 + a / 3); px[2] = (BYTE)(60 + a / 4); }
    }
    memset(&fh, 0, sizeof(fh)); memset(&ih, 0, sizeof(ih));
    fh.bfType = 0x4d42; fh.bfOffBits = sizeof(fh) + sizeof(ih); fh.bfSize = fh.bfOffBits + row * cy;
    ih.biSize = sizeof(ih); ih.biWidth = cx; ih.biHeight = cy; ih.biPlanes = 1; ih.biBitCount = 24; ih.biSizeImage = row * cy;
    f = CreateFileA(p, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
    if (f != INVALID_HANDLE_VALUE) {
        WriteFile(f, &fh, sizeof(fh), &wr, NULL); WriteFile(f, &ih, sizeof(ih), &wr, NULL);
        WriteFile(f, buf, row * cy, &wr, NULL); CloseHandle(f);
        logf("SALTFIX> dump %s (%dx%d cells)", p, cx, cy);
    }
    HeapFree(GetProcessHeap(), 0, buf);
}

/* vertex salt -> cell salt, the game's expansion (0x10005230: any corner) */
static int sf_cells(const SF_GRID *g, const BYTE *vs, BYTE *cs) {
    int cx = g->vx - 1, cy = g->vy - 1, vy = g->vy, x, y, n = 0;
    for (x = 0; x < cx; x++) for (y = 0; y < cy; y++) {
        BYTE s = vs[x * vy + y] || vs[(x + 1) * vy + y] || vs[x * vy + y + 1] || vs[(x + 1) * vy + y + 1];
        cs[x * cy + y] = s; n += s;
    }
    return n;
}

/* the generator's salt bitmap gen+0x20: +4 rows, +0xc words per row, +0x10 row pointers */
static int sf_bits(BYTE *bm, int vx, int vy, DWORD ***rp) {
    if (!bm || IsBadReadPtr(bm, 0x14)) return 0;
    if (*(int *)(bm + 4) < vx || *(int *)(bm + 0xc) * 32 < vy) return 0;
    *rp = *(DWORD ***)(bm + 0x10);
    return *rp && !IsBadReadPtr(*rp, vx * 4);
}

/* Generate's call to _createRivers (thiscall, 2 args). The carve only lowers heights (0x10018b57) and leaves the
   water grid at the sea level the generator filled it with, so a vertex dry before and wet after is river. */
static void __fastcall sf_rivers(BYTE *gen, void *edx, DWORD a1, DWORD a2) {
    DWORD a[2];
    SF_GRID g;
    BYTE *before = NULL;
    int x, y, n = 0;
    (void)edx;
    a[0] = a1; a[1] = a2;
    __try {
        if (g_sf_river) { HeapFree(GetProcessHeap(), 0, g_sf_river); g_sf_river = NULL; g_sf_rgen = NULL; }
        if (g_saltfix && sf_pair(*(BYTE **)(gen + 0x14), *(BYTE **)(gen + 0x18), &g) &&
            (before = (BYTE *)HeapAlloc(GetProcessHeap(), 0, g.vx * g.vy)) != NULL)
            for (x = 0; x < g.vx; x++) for (y = 0; y < g.vy; y++) before[x * g.vy + y] = g.h[x][y] <= g.w[x][y];
    } __except (EXCEPTION_EXECUTE_HANDLER) { if (before) HeapFree(GetProcessHeap(), 0, before); before = NULL; }
    rz_thiscall_ret(gen, (void *)g_sf_rivers_fn, a, 2);
    if (!before) return;
    __try {
        if (sf_pair(*(BYTE **)(gen + 0x14), *(BYTE **)(gen + 0x18), &g) && g.vx * g.vy > 0) {
            for (x = 0; x < g.vx; x++) for (y = 0; y < g.vy; y++) {
                BYTE r = (BYTE)(!before[x * g.vy + y] && g.h[x][y] <= g.w[x][y]);
                before[x * g.vy + y] = r; n += r;
            }
            g_sf_river = before; g_sf_rgen = gen; g_sf_rvx = g.vx; g_sf_rvy = g.vy; before = NULL;
            logf("SALTFIX> river carve: %d vertices of land put under water (flags 0x%02lX, water %lu)", n, a1 & 0xff, a2 & 0xff);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) { }
    if (before) HeapFree(GetProcessHeap(), 0, before);
}

/* generator vt+0x28 (thiscall, 1 arg: the terrain) */
static DWORD __fastcall sf_apply(BYTE *gen, void *edx, DWORD terrain) {
    DWORD a[1];
    (void)edx;
    a[0] = terrain;
    __try {
        SF_GRID g;
        DWORD **bits;
        if (g_saltfix && sf_pair(*(BYTE **)(gen + 0x14), *(BYTE **)(gen + 0x18), &g) &&
            sf_bits(*(BYTE **)(gen + 0x20), g.vx, g.vy, &bits)) {
            int nv = g.vx * g.vy, nc = (g.vx - 1) * (g.vy - 1), x, y, sea, old = 0, now = 0, oc = 0, ncs = 0, rc = 0, R = 0, seq = ++g_sf_dumpn;
            BYTE *vs = (BYTE *)HeapAlloc(GetProcessHeap(), 0, nv), *cs = (BYTE *)HeapAlloc(GetProcessHeap(), 0, nc);
            DWORD t0 = GetTickCount();
            if (vs && cs) {
                for (x = 0; x < g.vx; x++) for (y = 0; y < g.vy; y++) {
                    vs[x * g.vy + y] = (bits[x][y >> 5] >> (y & 31)) & 1; old += vs[x * g.vy + y]; }
                oc = sf_cells(&g, vs, cs);
                sf_dump(&g, cs, "before", seq);
                {   const BYTE *rv = (g_sf_river && g_sf_rgen == gen && g_sf_rvx == g.vx && g_sf_rvy == g.vy) ? g_sf_river : NULL;
                    if (!rv) logf("SALTFIX> new terrain: no river carve recorded for this generator (rivers not told apart)");
                    sea = sf_rule(&g, rv, vs, &rc, &R); }
                if (sea >= 0) {
                    for (x = 0; x < g.vx; x++) for (y = 0; y < g.vy; y++) {
                        DWORD m = 1u << (y & 31);
                        if (vs[x * g.vy + y]) { bits[x][y >> 5] |= m; now++; } else bits[x][y >> 5] &= ~m;
                    }
                    ncs = sf_cells(&g, vs, cs);
                    sf_dump(&g, cs, "after", seq);
                    logf("SALTFIX> new terrain %dx%d cells, R %d: salt vertices %d (stock rays) -> %d, salt cells %d -> %d, "
                         "wide water cells %d, %lu ms", g.vx - 1, g.vy - 1, R, old, now, oc, ncs, sea, GetTickCount() - t0);
                } else logf("SALTFIX> new terrain: out of memory, stock salt kept");
            }
            if (vs) HeapFree(GetProcessHeap(), 0, vs);
            if (cs) HeapFree(GetProcessHeap(), 0, cs);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) { logf("SALTFIX> new terrain: fault in the salt pass, stock salt kept"); }
    return rz_thiscall_ret(gen, (void *)g_sf_orig_apply, a, 1);
}

/* the current city's terrain: city vt+0x13c, its vtable SIMDIRT 0x1002046c, grids +0x30 height / +0x38 water */
static void *sf_city(void) {
    HMODULE sui = GetModuleHandleA("SIMUI.DLL");
    void *c = NULL;
    if (!sui) return NULL;
    __try { c = ((void *(__cdecl *)(void))((BYTE *)sui + 0x8e7da))(); } __except (EXCEPTION_EXECUTE_HANDLER) { c = NULL; }
    return c;
}

static int sf_city_grid(void *city, SF_GRID *g, void **eco) {
    BYTE *t;
    g->ok = 0;
    if (!city || !g_sf_dirt) return 0;
    t = (BYTE *)ho_v(city, 0x13c, 0, 0, 0, 0, 0, 0);
    *eco = (void *)ho_v(city, 0x16c, 0, 0, 0, 0, 0, 0);
    if (!t || !*eco || IsBadReadPtr(t, 0x40) || *(DWORD *)t != (DWORD)g_sf_dirt + 0x2046c) return 0;
    return sf_pair(*(BYTE **)(t + 0x30), *(BYTE **)(t + 0x38), g);
}

/* the SIMECO salt interface (vtable SIMECO 0x1001b984): +0x50 IsSaltWater(x, y), +0x90 SetIsSaltWater(x, y, v).
   Called straight through the vtable: ho_v's per-call pointer checks cost 25 s for the 1M cells of a 1024 map. */
typedef BYTE (__fastcall *SF_ISSALT)(void *self, void *edx, DWORD x, DWORD y);
typedef void (__fastcall *SF_SETSALT)(void *self, void *edx, DWORD x, DWORD y, DWORD v);

/* "Recalcular agua salada": the current city, same rule. Returns the salt cells read back, -1 if not possible.
   The flag is one bit per 2^shift x 2^shift block (shift = iface-8, 1 on SC3U: SIMECO 0x10008d90, ctor 0x10004379),
   so the block value = OR of its cells (what clearing every cell and then setting the salt cells gives, as the stock
   flush 0x10005230 does), and only blocks whose bit changes are written: one SetIsSaltWater message per change. */
static int salt_recalc(void) {
    void *city = sf_city(), *eco = NULL, *o;
    SF_GRID g;
    int r = -1;
    __try {
        HMODULE em = GetModuleHandleA("SIMECO.DLL");
        if (sf_city_grid(city, &g, &eco) && em && *(DWORD *)eco == (DWORD)em + 0x1b984) {
            int cx = g.vx - 1, cy = g.vy - 1, nv = g.vx * g.vy, nc = cx * cy, x, y, i, j, sea, before = 0, after = 0, wrote = 0, rc = 0, R = 0;
            int seq = ++g_sf_dumpn, sh = (int)*(DWORD *)((BYTE *)eco - 8), bs;
            DWORD *vt = *(DWORD **)eco;
            SF_ISSALT is = (SF_ISSALT)vt[0x50 / 4];
            SF_SETSALT set = (SF_SETSALT)vt[0x90 / 4];
            BYTE *vs = (BYTE *)HeapAlloc(GetProcessHeap(), 0, nv), *cs = (BYTE *)HeapAlloc(GetProcessHeap(), 0, nc);
            DWORD t0 = GetTickCount();
            if (sh < 0 || sh > 4) sh = 1;
            bs = 1 << sh;
            if (vs && cs) {
                for (x = 0; x < cx; x++) for (y = 0; y < cy; y++) { cs[x * cy + y] = is(eco, NULL, x, y) & 1; before += cs[x * cy + y]; }
                sf_dump(&g, cs, "before", seq);
                sea = sf_rule(&g, NULL, vs, &rc, &R);   /* a saved city has no record of its rivers */
                if (sea >= 0) {
                    sf_cells(&g, vs, cs);
                    for (x = 0; x < cx; x += bs) for (y = 0; y < cy; y += bs) {
                        BYTE want = 0;
                        for (i = x; i < x + bs && i < cx && !want; i++) for (j = y; j < y + bs && j < cy && !want; j++) want = cs[i * cy + j];
                        if ((is(eco, NULL, x, y) & 1) != want) { set(eco, NULL, x, y, want); wrote++; }
                    }
                    for (x = 0; x < cx; x++) for (y = 0; y < cy; y++) { cs[x * cy + y] = is(eco, NULL, x, y) & 1; after += cs[x * cy + y]; }
                    sf_dump(&g, cs, "after", seq);
                    /* the stock "salt on" cheat (SIMDIRT 0x1000e520) ends with city vt+0x18c -> vt+0x4c: same here */
                    o = (void *)ho_v(city, 0x18c, 0, 0, 0, 0, 0, 0);
                    if (o) ho_v(o, 0x4c, 0, 0, 0, 0, 0, 0);
                    logf("SALTFIX> recalculated this city (%dx%d cells, R %d): salt cells %d -> %d (read back), %d blocks of %dx%d "
                         "changed, wide water cells %d, %lu ms", cx, cy, R, before, after, wrote, bs, bs, sea, GetTickCount() - t0);
                    r = after;
                }
            }
            if (vs) HeapFree(GetProcessHeap(), 0, vs);
            if (cs) HeapFree(GetProcessHeap(), 0, cs);
        } else logf("SALTFIX> recalculate: no city terrain or SIMECO salt interface differs from shipped (city %p)", city);
    } __except (EXCEPTION_EXECUTE_HANDLER) { logf("SALTFIX> recalculate: fault, stopped"); r = -1; }
    return r;
}

static DWORD WINAPI sf_watcher(LPVOID p) {
    HMODULE dm = NULL;
    DWORD *slot, want, old;
    int ms = 0;
    (void)p;
    if (!g_saltfix) { logf("SALTFIX> off (SC3RESIZE_SALTFIX=0): stock salt water"); return 0; }
    while (!(dm = GetModuleHandleA("SIMDIRT.DLL")) && ms++ < 3000) Sleep(100);
    if (!dm) { logf("SALTFIX> SIMDIRT.DLL never loaded: off"); return 0; }
    slot = (DWORD *)((BYTE *)dm + 0x20c10);   /* generator vtable 0x10020be8 + 0x28 */
    want = (DWORD)dm + 0x17683;
    if (*(DWORD *)((BYTE *)dm + 0x20c04) != (DWORD)dm + 0x17c2d || *slot != want ||
        *(DWORD *)((BYTE *)dm + 0x204f8) != (DWORD)dm + 0x6220) {
        logf("SALTFIX> SIMDIRT differs from shipped (generator / terrain vtables): not installed");
        return 0;
    }
    g_sf_dirt = dm;
    {   BYTE *c = (BYTE *)dm + 0x18151;   /* call 0x100187da: e8 84 06 00 00 */
        if (c[0] == 0xE8 && *(LONG *)(c + 1) == 0x684 && VirtualProtect(c, 5, PAGE_EXECUTE_READWRITE, &old)) {
            g_sf_rivers_fn = (DWORD)dm + 0x187da;
            *(LONG *)(c + 1) = (LONG)((DWORD)sf_rivers - (DWORD)(c + 5));
            FlushInstructionCache(GetCurrentProcess(), c, 5);
        } else logf("SALTFIX> SIMDIRT+0x18151 differs from shipped: rivers not told apart on new terrain");
    }
    if (VirtualProtect(slot, 4, PAGE_EXECUTE_READWRITE, &old)) {
        g_sf_orig_apply = *slot;
        *slot = (DWORD)sf_apply;
        logf("SALTFIX> on: new terrain gets salt by flood from the map edge over open water (rivers, lakes fresh)");
    }
    return 0;
}
