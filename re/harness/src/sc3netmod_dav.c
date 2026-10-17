/* sc3netmod_dav.c - the DAV block of sc3netmod.dll (task diagave, 2026-10-17): automatic diagonal avenues.
 * #included by sc3netmod.c after the RBT block, whose retile-pass and city-load hooks it shares (rb_pass / rb_load
 * call dav_run when a `dav` line was read). Offline twin, rule and art: re/tools/netmod/diagave.py; evidence
 * verify/diagave/.
 *
 * A package declares `dav <inner35> <inner18004> <inner1999>` (netpack manifest "auto_diagonal_avenues"): ROAD
 * variants of diagonal road 35, of its start cap 18004 and of its end cap 1999, each drawn as the stock piece's road
 * half plus a median half. Two diagonal road drags laid side by side become an avenue with that median:
 *  band row  (down-right axis) ROAD cells (a..a+3, z), no ROAD at (a-1, z) and (a+4, z); the other axis is the same
 *            with x mirrored
 *  band      a chain of band rows, each the next row's left - 1, at least DAV_MIN_ROWS rows, plus the rows above and
 *            below it that still hold ROAD at one of their four d positions (the drags' ends)
 *  isolated  no other ROAD cell touches the band (8 neighbours); junctions at the ends are later work
 *  piece     d = x - row left; staircase A = d 0,1, B = d 2,3. Each cell gets the piece the stock tiler gives a lone
 *            staircase, from its mask inside its own staircase (g_dav_lone, measured with tiler.py); a cell at d 1 or 2
 *            with the other staircase in its row or a row next to it takes the inner variant.
 * Write = the game's piece writer FUN_10008919 per cell (as RBT). Revert: an inner-variant cell that is no longer in a
 * band gets the rect retile FUN_100151f1 (the variants are not Protected), so the stock tiler re-places it.
 * Save: the variants save as their base (35 / 18004 / 1999) through SAVEBASE, so a stock game sees two diagonals.
 * Off: SC3NETMOD_DAV=0.
 */

#define DAV_MIN_ROWS 3
#define DAV_MAX_CELLS 8192

/* g_dav_inner[3] (inner variants of 35, 18004, 1999; [0] == 0: not declared) and g_dav_on live in sc3netmod_rbt.c */

static DWORD g_dav_lone[256];                 /* own mask -> (piece << 8 | state) + 1, 0 = not a lone mask */
static volatile LONG g_dav_n_bands, g_dav_n_cells, g_dav_n_rev;
static const signed char DAV_DIR[8][2] = { { -1, 0 }, { 0, -1 }, { 1, 0 }, { 0, 1 }, { -1, -1 }, { 1, -1 }, { 1, 1 },
                                           { -1, 1 } };            /* mask bit k, tiler.py:41 */

static void dav_line(const char *path, const char *line) {
    unsigned long a, b, c;
    if (sscanf(line + 4, "%lu %lu %lu", &a, &b, &c) != 3 || !a || !b || !c || a > 0xffff || b > 0xffff || c > 0xffff ||
        g_base[a] != 35 || g_base[b] != 18004 || g_base[c] != 1999) {
        logf("### dav: %s: bad line or pieces not variants of 35 / 18004 / 1999: '%s'", path, line);
        return;
    }
    if (g_dav_inner[0] && g_dav_inner[0] != (WORD)a) {
        logf("### dav: %s: a second diagonal avenue set %lu (already %u) - ignored", path, a, g_dav_inner[0]);
        return;
    }
    g_dav_inner[0] = (WORD)a; g_dav_inner[1] = (WORD)b; g_dav_inner[2] = (WORD)c;
    logf("dav: %s: automatic diagonal avenues, inner pieces %lu (35) %lu (18004) %lu (1999)", path, a, b, c);
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

static WORD dav_inner_of(WORD pid) {
    return pid == 35 ? g_dav_inner[0] : pid == 18004 ? g_dav_inner[1] : pid == 1999 ? g_dav_inner[2] : 0;
}

static int dav_is_inner(WORD id) {
    return id && (id == g_dav_inner[0] || id == g_dav_inner[1] || id == g_dav_inner[2]);
}

/* road test in axis space: axis 1 mirrors x */
static int dav_road(RbBuf *b, int axis, int x, int z) { return rb_at(b, axis ? -x : x, z) != 0; }

static int dav_band_row(RbBuf *b, int axis, int a, int z) {
    return !dav_road(b, axis, a - 1, z) && dav_road(b, axis, a, z) && dav_road(b, axis, a + 1, z) &&
           dav_road(b, axis, a + 2, z) && dav_road(b, axis, a + 3, z) && !dav_road(b, axis, a + 4, z);
}

typedef struct { int x, z; BYTE st, d; } DavCell;     /* x in real space; st 1 = A, 2 = B */

typedef struct {                                      /* one pass: the read buffer and per-band scratch */
    RbBuf b;
    BYTE *mark;                                       /* [cell]: staircase (1 A, 2 B) of the band being built, 0 */
    BYTE *rowA, *rowB;                                /* [z - z0]: the band's staircase A / B has a cell in row z */
    DavCell *cell;
    DWORD *want;
} DavPass;

static int dav_mark(DavPass *p, int x, int z) {
    x -= p->b.x0; z -= p->b.z0;
    if (x < 0 || z < 0 || x >= p->b.w || z >= p->b.h) return 0;
    return p->mark[z * p->b.w + x];
}

static void dav_add(DavPass *p, int *n, int axis, int ax, int z, int d) {
    int x = axis ? -ax : ax, i = (z - p->b.z0) * p->b.w + (x - p->b.x0);
    if (*n >= DAV_MAX_CELLS || p->mark[i]) return;
    p->cell[*n].x = x; p->cell[*n].z = z; p->cell[*n].st = (BYTE)(d < 2 ? 1 : 2); p->cell[*n].d = (BYTE)d;
    p->mark[i] = (BYTE)(d < 2 ? 1 : 2);
    if (d < 2) p->rowA[z - p->b.z0] = 1; else p->rowB[z - p->b.z0] = 1;
    (*n)++;
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
    mem = (BYTE *)VirtualAlloc(NULL, nbuf * 5 + 2 * (SIZE_T)P.b.h + DAV_MAX_CELLS * (sizeof(DavCell) + 4), MEM_COMMIT,
                               PAGE_READWRITE);
    if (!mem) return 0;
    P.b.c = (DWORD *)mem;
    P.cell = (DavCell *)(mem + nbuf * 4);
    P.want = (DWORD *)(P.cell + DAV_MAX_CELLS);
    P.mark = (BYTE *)(P.want + DAV_MAX_CELLS);
    P.rowA = P.mark + nbuf;
    P.rowB = P.rowA + P.b.h;
    for (z = 0; z < P.b.h; z++)
        for (x = 0; x < P.b.w; x++) P.b.c[z * P.b.w + x] = rb_read(mgr, lay, x0 + x, z0 + z, W, H);
    for (axis = 0; axis < 2; axis++) {
        int ax0 = axis ? -x1 : x0, ax1 = axis ? -x0 : x1;
        for (z = z0; z <= z1; z++)
            for (x = ax0; x <= ax1; x++) {
                int rows = 0, zz, aa, ok = 1, step, nw = 0;
                if (!dav_band_row(&P.b, axis, x, z) || dav_band_row(&P.b, axis, x - 1, z - 1)) continue;
                for (zz = z, aa = x; dav_band_row(&P.b, axis, aa, zz); zz++, aa++) rows++;
                if (rows < DAV_MIN_ROWS) continue;
                n = 0;
                for (k = 0; k < rows; k++)
                    for (j = 0; j < 4; j++) dav_add(&P, &n, axis, x + k + j, z + k, j);
                for (step = -1; step <= 1; step += 2) {           /* the drags' ends above and below the full rows */
                    int zr = step < 0 ? z : z + rows - 1, ar = step < 0 ? x : x + rows - 1;
                    for (k = 1;; k++) {
                        int got = 0;
                        for (j = 0; j < 4; j++)
                            if (dav_road(&P.b, axis, ar + step * k + j, zr + step * k)) {
                                dav_add(&P, &n, axis, ar + step * k + j, zr + step * k, j);
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
                }
                for (k = 0; k < n && ok; k++) {                    /* own masks -> lone pieces, inner variants */
                    int m = 0, inner = 0, cz = P.cell[k].z - z0;
                    DWORD v;
                    for (j = 0; j < 8; j++)
                        if (dav_mark(&P, P.cell[k].x + DAV_DIR[j][0], P.cell[k].z + DAV_DIR[j][1]) == P.cell[k].st)
                            m |= 1 << j;
                    if (!g_dav_lone[m]) { ok = 0; break; }
                    v = g_dav_lone[m] - 1;
                    if (P.cell[k].d == 1 || P.cell[k].d == 2) {
                        BYTE *other = P.cell[k].st == 1 ? P.rowB : P.rowA;
                        inner = other[cz] || (cz > 0 && other[cz - 1]) || (cz + 1 < P.b.h && other[cz + 1]);
                    }
                    P.want[k] = inner ? (((DWORD)dav_inner_of((WORD)(v >> 8)) << 8) | (v & 0xff)) : v;
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
                for (k = 0; k < n; k++) {                          /* clear this band's scratch */
                    P.mark[(P.cell[k].z - z0) * P.b.w + (P.cell[k].x - x0)] = 0;
                    P.rowA[P.cell[k].z - z0] = P.rowB[P.cell[k].z - z0] = 0;
                }
            }
    }
    /* inner-variant cells in the area (one cell in from the read border) that no band kept: back to the stock tiles */
    if (keep)
        for (z = z0 + 1; z < z1; z++)
            for (x = x0 + 1; x < x1; x++) {
                DWORD v = rb_at(&P.b, x, z);
                int rect[6];
                if (!v || !dav_is_inner((WORD)(v & 0xffff)) || keep[(z - z0) * P.b.w + (x - x0)]) continue;
                rect[0] = x << 8; rect[1] = z << 8; rect[2] = 0; rect[3] = x << 8; rect[4] = z << 8; rect[5] = 0;
                ((PFN_Retile)VT(mgr, 0xb0))(mgr, 0, rect, 3);
                nrev++;
                logf("dav: %s: (%d,%d) inner piece %lu no longer in a band -> stock retile", who, x, z, v & 0xffff);
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
    logf("stats: dav bands seen=%ld, cells written=%ld, inner cells reverted=%ld", g_dav_n_bands, g_dav_n_cells,
         g_dav_n_rev);
}
