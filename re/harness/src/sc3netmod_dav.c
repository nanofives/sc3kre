/* sc3netmod_dav.c - the DAV block of sc3netmod.dll (task diagave, 2026-10-17): automatic diagonal avenues.
 * #included by sc3netmod.c after the RBT block, whose retile-pass and city-load hooks it shares (rb_pass / rb_load
 * call dav_run when `dav` lines were read). Offline twin, rule, art and lanes: re/tools/netmod/diagave.py; evidence
 * verify/diagave/.
 *
 * Two diagonal road drags JOINED side by side (the second one cell over) become one avenue. Stock diagonal 35 draws
 * only the road half of its cell, so in a band of three cells per row the middle cell holds the inner halves of both
 * roads. A package declares its middle pieces, one `dav <piece> <a> <b> <delta>` line each (netpack manifest
 * "auto_diagonal_avenues"): ROAD variants drawn as stock piece <a> (35 / 18004 / 1999) at the cell's state plus stock
 * piece <b> at state + delta, with both pieces' lanes.
 *  band row  (down-right axis) ROAD cells (a..a+2, z), no ROAD at (a-1, z) and (a+3, z); the other axis is the same
 *            with x mirrored
 *  band      a chain of band rows, each the next row's left - 1, at least DAV_MIN_ROWS rows, plus the rows above and
 *            below it that still hold ROAD at d 0..2 (the drags' ends); d = x - row left
 *  split     staircase A = d 0,1 and B = d 1,2 in band rows; in end rows d 0 is A, d 2 is B, d 1 is A, B or both:
 *            the choice with the fewest "both", then the fewest against the end's preference (top A, bottom B), that
 *            keeps every cell of both staircases a lone-staircase mask (g_dav_lone, measured with tiler.py)
 *  isolated  no other ROAD cell touches the band (8 neighbours); junctions are later work
 *  piece     a cell of one staircase gets that lone piece; a cell of both gets the declared middle piece for
 *            (A's piece, B's piece, B state - A state), in A's state. A combination nobody declared: band left alone.
 * Write = the game's piece writer FUN_10008919 per cell (as RBT). Revert: a middle piece that is no longer in a band
 * gets the rect retile FUN_100151f1 (the variants are not Protected), so the stock tiler re-places it.
 * Save: the middle pieces save as 4-way 43 (rb_save_id): stock 35 would show only one of the two roads, 43 keeps the
 * road continuous in a game without the mod (the stock ladder look). Off: SC3NETMOD_DAV=0.
 */

#define DAV_MIN_ROWS 3
#define DAV_MAX_CELLS 8192
#define DAV_MAX_AMB 6
#define DAV_MAX_MID 16

typedef struct { WORD piece, a, b; BYTE delta; } DavMid;
static DavMid g_dav_mid[DAV_MAX_MID];
static int g_dav_nmid;                         /* g_dav_nmid > 0: DAV declared (g_dav_inner[0] mirrors it for rbt.c) */
static DWORD g_dav_lone[256];                 /* own mask -> (piece << 8 | state) + 1, 0 = not a lone mask */
static volatile LONG g_dav_n_bands, g_dav_n_cells, g_dav_n_rev;
static const signed char DAV_DIR[8][2] = { { -1, 0 }, { 0, -1 }, { 1, 0 }, { 0, 1 }, { -1, -1 }, { 1, -1 }, { 1, 1 },
                                           { -1, 1 } };            /* mask bit k, tiler.py:41 */

static void dav_line(const char *path, const char *line) {
    unsigned long v, a, b, d;
    int k;
    if (sscanf(line + 4, "%lu %lu %lu %lu", &v, &a, &b, &d) != 4 || !v || v > 0xffff || d > 3 ||
        (a != 35 && a != 18004 && a != 1999) || (b != 35 && b != 18004 && b != 1999) || g_base[v] != (WORD)a) {
        logf("### dav: %s: bad line or piece not a variant of its first stock piece: '%s'", path, line);
        return;
    }
    for (k = 0; k < g_dav_nmid; k++)
        if (g_dav_mid[k].a == a && g_dav_mid[k].b == b && g_dav_mid[k].delta == d) {
            logf("### dav: %s: middle (%lu,%lu,%lu) already declared as %u - ignored", path, a, b, d, g_dav_mid[k].piece);
            return;
        }
    if (g_dav_nmid >= DAV_MAX_MID) { logf("### dav: %s: too many middle pieces - ignored", path); return; }
    g_dav_mid[g_dav_nmid].piece = (WORD)v; g_dav_mid[g_dav_nmid].a = (WORD)a; g_dav_mid[g_dav_nmid].b = (WORD)b;
    g_dav_mid[g_dav_nmid].delta = (BYTE)d;
    g_dav_nmid++;
    g_dav_inner[0] = g_dav_mid[0].piece;
    logf("dav: %s: middle piece %lu = %lu + %lu (state + %lu)", path, v, a, b, d);
}

static void dav_init_table(void) {
    /* lone staircase of 3+ steps, stock rules (verify/diagave/RESULTS.md, diagave.py LONE) */
    static const WORD t[20][3] = {
        { 17, 18004, 2 }, { 18, 1999, 2 }, { 22, 35, 2 }, { 25, 35, 0 }, { 34, 18004, 3 }, { 35, 35, 1 },
        { 36, 1999, 3 }, { 44, 35, 3 }, { 68, 18004, 0 }, { 70, 35, 2 }, { 72, 1999, 0 }, { 73, 35, 0 },
        { 86, 35, 2 }, { 89, 35, 0 }, { 129, 1999, 1 }, { 131, 35, 1 }, { 136, 18004, 1 }, { 140, 35, 3 },
        { 163, 35, 1 }, { 172, 35, 3 } };
    int k;
    for (k = 0; k < 20; k++) g_dav_lone[t[k][0]] = (((DWORD)t[k][1] << 8) | t[k][2]) + 1;
}

static int dav_is_mid(WORD id) {
    int k;
    for (k = 0; k < g_dav_nmid; k++) if (g_dav_mid[k].piece == id) return 1;
    return 0;
}

static WORD dav_mid_of(WORD a, WORD b, int delta) {
    int k;
    for (k = 0; k < g_dav_nmid; k++)
        if (g_dav_mid[k].a == a && g_dav_mid[k].b == b && g_dav_mid[k].delta == delta) return g_dav_mid[k].piece;
    return 0;
}

/* road test in axis space: axis 1 mirrors x */
static int dav_road(RbBuf *b, int axis, int x, int z) { return rb_at(b, axis ? -x : x, z) != 0; }

static int dav_band_row(RbBuf *b, int axis, int a, int z) {
    return !dav_road(b, axis, a - 1, z) && dav_road(b, axis, a, z) && dav_road(b, axis, a + 1, z) &&
           dav_road(b, axis, a + 2, z) && !dav_road(b, axis, a + 3, z);
}

typedef struct { int x, z; BYTE pref; } DavCell;    /* x in real space; pref: ambiguous end cell, 1 = A, 2 = B */

typedef struct {                                      /* one pass: the read buffer and per-band scratch */
    RbBuf b;
    BYTE *mark;                                       /* [cell]: bit 0 staircase A, bit 1 B, bit 2 in the band */
    DavCell *cell;
    DWORD *want;
} DavPass;

static int dav_mark(DavPass *p, int x, int z) {
    x -= p->b.x0; z -= p->b.z0;
    if (x < 0 || z < 0 || x >= p->b.w || z >= p->b.h) return 0;
    return p->mark[z * p->b.w + x];
}

static BYTE *dav_markp(DavPass *p, int x, int z) { return &p->mark[(z - p->b.z0) * p->b.w + (x - p->b.x0)]; }

/* add a band cell; st: 1 A, 2 B, 3 both, 0 ambiguous (pref 1 / 2) */
static void dav_add(DavPass *p, int *n, int axis, int ax, int z, int st, int pref) {
    int x = axis ? -ax : ax;
    BYTE *m = dav_markp(p, x, z);
    if (*n >= DAV_MAX_CELLS || *m) return;
    p->cell[*n].x = x; p->cell[*n].z = z; p->cell[*n].pref = (BYTE)(st ? 0 : pref);
    *m = (BYTE)(4 | st);
    (*n)++;
}

static int dav_own_mask(DavPass *p, int x, int z, int bit) {
    int j, m = 0;
    for (j = 0; j < 8; j++) if (dav_mark(p, x + DAV_DIR[j][0], z + DAV_DIR[j][1]) & bit) m |= 1 << j;
    return m;
}

/* every cell of both staircases a lone mask? */
static int dav_valid(DavPass *p, int n) {
    int k;
    for (k = 0; k < n; k++) {
        int m = dav_mark(p, p->cell[k].x, p->cell[k].z);
        if ((m & 1) && !g_dav_lone[dav_own_mask(p, p->cell[k].x, p->cell[k].z, 1)]) return 0;
        if ((m & 2) && !g_dav_lone[dav_own_mask(p, p->cell[k].x, p->cell[k].z, 2)]) return 0;
    }
    return 1;
}

/* one pass over the cells in [x0..x1] x [z0..z1]; -> 1 when a band reached the read border (the caller re-runs it
   over the whole map). keep[cell] = 1 for every cell of a converted band (the revert skips them). */
static int dav_pass(BYTE *mgr, int x0, int z0, int x1, int z1, int W, int H, const char *who, BYTE *keep) {
    void *lay = *(void **)(mgr + 0x3c);
    DavPass P;
    BYTE *mem;
    SIZE_T nbuf;
    int axis, x, z, n, k, j, border = 0, nb = 0, nwall = 0, nrev = 0;
    P.b.x0 = x0; P.b.z0 = z0; P.b.w = x1 - x0 + 1; P.b.h = z1 - z0 + 1;
    nbuf = (SIZE_T)P.b.w * P.b.h;
    mem = (BYTE *)VirtualAlloc(NULL, nbuf * 5 + DAV_MAX_CELLS * (sizeof(DavCell) + 4), MEM_COMMIT, PAGE_READWRITE);
    if (!mem) return 0;
    P.b.c = (DWORD *)mem;
    P.cell = (DavCell *)(mem + nbuf * 4);
    P.want = (DWORD *)(P.cell + DAV_MAX_CELLS);
    P.mark = (BYTE *)(P.want + DAV_MAX_CELLS);
    for (z = 0; z < P.b.h; z++)
        for (x = 0; x < P.b.w; x++) P.b.c[z * P.b.w + x] = rb_read(mgr, lay, x0 + x, z0 + z, W, H);
    for (axis = 0; axis < 2; axis++) {
        int ax0 = axis ? -x1 : x0, ax1 = axis ? -x0 : x1;
        for (z = z0; z <= z1; z++)
            for (x = ax0; x <= ax1; x++) {
                int rows = 0, zz, aa, ok = 1, step, nw = 0, namb = 0, amb[DAV_MAX_AMB], combo, ncombo, best = -1;
                int bestcost = 0x7fffffff;
                if (!dav_band_row(&P.b, axis, x, z) || dav_band_row(&P.b, axis, x - 1, z - 1)) continue;
                for (zz = z, aa = x; dav_band_row(&P.b, axis, aa, zz); zz++, aa++) rows++;
                if (rows < DAV_MIN_ROWS) continue;
                n = 0;
                for (k = 0; k < rows; k++) {
                    dav_add(&P, &n, axis, x + k, z + k, 1, 0);
                    dav_add(&P, &n, axis, x + k + 1, z + k, 3, 0);
                    dav_add(&P, &n, axis, x + k + 2, z + k, 2, 0);
                }
                for (step = -1; step <= 1; step += 2) {           /* the drags' ends above and below the full rows */
                    int zr = step < 0 ? z : z + rows - 1, ar = step < 0 ? x : x + rows - 1;
                    for (k = 1;; k++) {
                        int got = 0;
                        for (j = 0; j < 3; j++)
                            if (dav_road(&P.b, axis, ar + step * k + j, zr + step * k)) {
                                dav_add(&P, &n, axis, ar + step * k + j, zr + step * k, j == 0 ? 1 : j == 2 ? 2 : 0,
                                        step < 0 ? 1 : 2);
                                got = 1;
                            }
                        if (!got) break;
                    }
                }
                for (k = 0; k < n && ok; k++) {
                    int cx = P.cell[k].x, cz = P.cell[k].z;
                    if ((cx <= x0 && x0 > 0) || (cz <= z0 && z0 > 0) || (cx >= x1 && x1 < W - 1) || (cz >= z1 && z1 < H - 1))
                        border = 1;
                    for (j = 0; j < 8 && ok; j++) {                /* isolated: no other road touches the band */
                        int qx = cx + DAV_DIR[j][0], qz = cz + DAV_DIR[j][1];
                        if (rb_at(&P.b, qx, qz) && !dav_mark(&P, qx, qz)) ok = 0;
                    }
                    if (P.cell[k].pref) {
                        if (namb < DAV_MAX_AMB) amb[namb++] = k; else ok = 0;
                    }
                }
                /* the split: each ambiguous end cell is its end's staircase (0), the other one (1) or both (2) */
                for (ncombo = 1, k = 0; k < namb; k++) ncombo *= 3;
                for (combo = 0; ok && combo < ncombo; combo++) {
                    int c = combo, cost = 0;
                    for (k = 0; k < namb; k++, c /= 3) {
                        int ch = c % 3, pref = P.cell[amb[k]].pref;
                        *dav_markp(&P, P.cell[amb[k]].x, P.cell[amb[k]].z) = (BYTE)(4 | (ch == 2 ? 3 : ch == 0 ? pref : 3 - pref));
                        cost += ch == 2 ? 100 : ch;
                    }
                    if (cost < bestcost && dav_valid(&P, n)) { best = combo; bestcost = cost; }
                }
                if (ok && best < 0) ok = 0;
                if (ok) {
                    int c = best;
                    for (k = 0; k < namb; k++, c /= 3) {
                        int ch = c % 3, pref = P.cell[amb[k]].pref;
                        *dav_markp(&P, P.cell[amb[k]].x, P.cell[amb[k]].z) = (BYTE)(4 | (ch == 2 ? 3 : ch == 0 ? pref : 3 - pref));
                    }
                }
                for (k = 0; k < n && ok; k++) {                    /* pieces */
                    int cx = P.cell[k].x, cz = P.cell[k].z, m = dav_mark(&P, cx, cz);
                    DWORD va = (m & 1) ? g_dav_lone[dav_own_mask(&P, cx, cz, 1)] : 0;
                    DWORD vb = (m & 2) ? g_dav_lone[dav_own_mask(&P, cx, cz, 2)] : 0;
                    if (va && vb) {
                        WORD mid;
                        va--; vb--;
                        mid = dav_mid_of((WORD)(va >> 8), (WORD)(vb >> 8), (int)((vb - va) & 3));
                        if (!mid) { ok = 0; break; }
                        P.want[k] = ((DWORD)mid << 8) | (va & 0xff);
                    } else if (va || vb) {
                        P.want[k] = (va ? va : vb) - 1;
                    } else { ok = 0; break; }
                }
                if (ok) {
                    nb++;
                    for (k = 0; k < n; k++) {
                        DWORD cur = rb_at(&P.b, P.cell[k].x, P.cell[k].z);
                        int pos[3];
                        if (keep) keep[(P.cell[k].z - z0) * P.b.w + (P.cell[k].x - x0)] = 1;
                        if ((((cur & 0xffff) << 8) | ((cur >> 16) & 3)) == P.want[k]) continue;
                        pos[0] = P.cell[k].x << 8; pos[1] = P.cell[k].z << 8; pos[2] = 0;
                        ((PFN_Put)(g_rb_m + 0x8919))(mgr, 0, lay, pos, P.want[k], -1, 8, 0);
                        nw++;
                    }
                    if (nw || !strcmp(who, "load"))
                        logf("dav: %s: band axis %d, %d full row(s) from (%d,%d), %d cell(s), %d written", who, axis,
                             rows, axis ? -x : x, z, n, nw);
                    nwall += nw;
                }
                for (k = 0; k < n; k++) *dav_markp(&P, P.cell[k].x, P.cell[k].z) = 0;   /* clear this band's scratch */
            }
    }
    /* middle pieces in the area (one cell in from the read border) that no band kept: back to the stock tiles */
    if (keep)
        for (z = z0 + 1; z < z1; z++)
            for (x = x0 + 1; x < x1; x++) {
                DWORD v = rb_at(&P.b, x, z);
                int rect[6];
                if (!v || !dav_is_mid((WORD)(v & 0xffff)) || keep[(z - z0) * P.b.w + (x - x0)]) continue;
                rect[0] = x << 8; rect[1] = z << 8; rect[2] = 0; rect[3] = x << 8; rect[4] = z << 8; rect[5] = 0;
                ((PFN_Retile)VT(mgr, 0xb0))(mgr, 0, rect, 3);
                nrev++;
                logf("dav: %s: (%d,%d) middle piece %lu no longer in a band -> stock retile", who, x, z, v & 0xffff);
            }
    VirtualFree(mem, 0, MEM_RELEASE);
    InterlockedExchangeAdd(&g_dav_n_bands, nb);
    InterlockedExchangeAdd(&g_dav_n_cells, nwall);
    InterlockedExchangeAdd(&g_dav_n_rev, nrev);
    return border;
}

/* cells [x0..x1] x [z0..z1] were edited (the retile pass's work box) or the whole map (load) */
static void dav_run(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who) {
    int W = (*(int *)(mgr + 0x5c) >> 8) + 1, H = (*(int *)(mgr + 0x60) >> 8) + 1, M = 24, full;
    BYTE *keep;
    if (!g_dav_on || W < 4 || H < 4 || W > 4096 || H > 4096) return;
    x0 -= M; z0 -= M; x1 += M; z1 += M;
    if (x0 < 0) x0 = 0;
    if (z0 < 0) z0 = 0;
    if (x1 > W - 1) x1 = W - 1;
    if (z1 > H - 1) z1 = H - 1;
    full = x0 == 0 && z0 == 0 && x1 == W - 1 && z1 == H - 1;
    keep = (BYTE *)VirtualAlloc(NULL, (SIZE_T)(x1 - x0 + 1) * (z1 - z0 + 1), MEM_COMMIT, PAGE_READWRITE);
    if (!keep) return;
    if (dav_pass(mgr, x0, z0, x1, z1, W, H, who, keep) && !full) {
        VirtualFree(keep, 0, MEM_RELEASE);
        logf("dav: %s: a band reached the read border - whole-map pass", who);
        keep = (BYTE *)VirtualAlloc(NULL, (SIZE_T)W * H, MEM_COMMIT, PAGE_READWRITE);
        if (!keep) return;
        dav_pass(mgr, 0, 0, W - 1, H - 1, W, H, who, keep);
    }
    VirtualFree(keep, 0, MEM_RELEASE);
}

static void dav_stats(void) {
    static LONG last;
    LONG n = g_dav_n_bands + g_dav_n_cells + g_dav_n_rev;
    if (!g_dav_on || n == last) return;
    last = n;
    logf("stats: dav bands seen=%ld, cells written=%ld, middle cells reverted=%ld", g_dav_n_bands, g_dav_n_cells,
         g_dav_n_rev);
}
