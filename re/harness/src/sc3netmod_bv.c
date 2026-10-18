/* sc3netmod_bv.c - the BV block of sc3netmod.dll (task boulevard, 2026-10-17): automatic boulevards.
 * #included by sc3netmod.c after the DAV block; shares RBT's retile-pass and city-load hooks (rb_pass / rb_load call
 * bv_run when `bvp` lines were read). Offline twin, art and lanes: re/tools/netmod/boulevard.py (runs()),
 * boulevard_paint.py; evidence verify/boulevard/.
 *
 * Three parallel straight roads drawn side by side (stock: 11204 / 29 / 11204) become one boulevard: the outer roads
 * are the carriageways, the middle road an extra lane for each plus a wide tree median. Axis space: (s along, w
 * across); axis 0 = along x (real (s, w)), axis 1 = along z (real (-w, s): the canonical frame turned one state, so
 * every piece's state is its canonical state + 1).
 *  column    s with ROAD at (s, w0..w0+2). Clean: no ROAD at (s, w0-1), (s, w0+3). Junction: a straight single road
 *            arm at (s, w0-1) and / or (s, w0+3) (its next cell road, the cells beside the arm cell not)
 *  run       maximal consecutive columns, at least BV_MIN_COLS long. Each end: nothing beyond -> cap (the last
 *            column closes the boulevard), exactly one row going on straight (two cells) -> taper to that row over
 *            the last BV_TAPER columns, two adjacent rows going on -> narrowing to that avenue over the last
 *            BV_TAPER columns (task boulevard, 20750..), anything else -> the run is left to the stock tiler
 *  accepted  at least BV_MIN_COLS clean columns besides the end regions, no junction in or next to an end region,
 *            no other ROAD 8-touching the run (junction arms and the road a taper goes on into excepted)
 *  pieces    canonical (boulevard along +x, rows 0 / 1 / 2): outer rows OUTER (row 0 state 2, row 2 state 0, = the
 *            states stock 11204 has there), middle MIDDLE / NOSE (median nose at +x, state 2 at -x) / NOSE2 (both)
 *            next to a junction or an end region; junction column JN / JM / JF; cap CAP[row]; taper TAPER[keep][col*3+row].
 *            The -x end is the +x end turned half a circle (rows 2 - row, state + 2, kept row 2 - keep).
 * Shapes refused (other streams own them): a diagonal touching the run, 3x3 blocks (any run shorter than
 * BV_MIN_RUN = 4 columns, whatever its arms: bigrbt's), an avenue or a boulevard crossing (its arm is not a single
 * road: wave 2), the two OUTER rows going on at an end (two separate roads).
 * Write = FUN_10008919 per cell (as RBT / DAV). Revert = rect retile of a boulevard piece no run kept. Save: every
 * piece saves as its base (OUTER 11204 and MIDDLE 29 in the stock states, junction / end pieces 43), so a game without
 * the mod keeps the roads joined. Off: SC3NETMOD_BV=0.
 * Table lines: `bvp <outer> <middle> <nose> <nose2> <jn> <jm> <jf>`, `bvc <row0> <row1> <row2>`,
 * `bvt <keep> <9 pieces, column-major>`, `bva <first kept row 0|1> <9 pieces>` (netpack manifest "auto_boulevards").
 */

#define BV_MIN_COLS 3
#define BV_TAPER 3
#define BV_MIN_RUN 4             /* orchestrator ruling 2026-10-17: an exactly-3x3 full road block is bigrbt's */
#define BV_MAX_RUN 1024

/* g_bv_p[7] (declared in sc3netmod_rbt.c): outer middle nose nose2 jn jm jf; g_bv_p[0] != 0: BV declared */
static WORD g_bv_cap[3];
static WORD g_bv_tap[3][9];
static WORD g_bv_av[2][9];                     /* narrowing to the avenue on rows k, k+1 (k 0 / 1), column-major */
static volatile LONG g_bv_n_runs, g_bv_n_cells, g_bv_n_rev;

enum { BV_OUTER, BV_MIDDLE, BV_NOSE, BV_NOSE2, BV_JN, BV_JM, BV_JF };

static int bv_variant(unsigned long v) { return v && v <= 0xffff && g_base[v]; }

static void bv_line(const char *path, const char *line) {
    unsigned long v[10];
    int k;
    if (!strncmp(line, "bvp ", 4)) {
        if (sscanf(line + 4, "%lu %lu %lu %lu %lu %lu %lu", &v[0], &v[1], &v[2], &v[3], &v[4], &v[5], &v[6]) != 7) {
            logf("### bv: %s: bad line '%s'", path, line);
            return;
        }
        for (k = 0; k < 7; k++)
            if (!bv_variant(v[k])) { logf("### bv: %s: piece %lu is not a variant: '%s'", path, v[k], line); return; }
        if (g_bv_p[0]) { logf("### bv: %s: a second boulevard set - ignored", path); return; }
        for (k = 0; k < 7; k++) g_bv_p[k] = (WORD)v[k];
        logf("bv: %s: boulevard pieces outer %u, middle %u, nose %u / %u, junction %u %u %u", path, g_bv_p[0], g_bv_p[1],
             g_bv_p[2], g_bv_p[3], g_bv_p[4], g_bv_p[5], g_bv_p[6]);
    } else if (!strncmp(line, "bvc ", 4)) {
        if (sscanf(line + 4, "%lu %lu %lu", &v[0], &v[1], &v[2]) != 3 || !bv_variant(v[0]) || !bv_variant(v[1]) ||
            !bv_variant(v[2])) {
            logf("### bv: %s: bad cap line '%s'", path, line);
            return;
        }
        for (k = 0; k < 3; k++) g_bv_cap[k] = (WORD)v[k];
        logf("bv: %s: end cap pieces %u %u %u", path, g_bv_cap[0], g_bv_cap[1], g_bv_cap[2]);
    } else if (!strncmp(line, "bvt ", 4)) {
        if (sscanf(line + 4, "%lu %lu %lu %lu %lu %lu %lu %lu %lu %lu", &v[0], &v[1], &v[2], &v[3], &v[4], &v[5], &v[6],
                   &v[7], &v[8], &v[9]) != 10 || v[0] > 2) {
            logf("### bv: %s: bad taper line '%s'", path, line);
            return;
        }
        for (k = 1; k < 10; k++)
            if (!bv_variant(v[k])) { logf("### bv: %s: taper piece %lu is not a variant", path, v[k]); return; }
        for (k = 0; k < 9; k++) g_bv_tap[v[0]][k] = (WORD)v[k + 1];
        logf("bv: %s: taper to row %lu = pieces %lu..%lu", path, v[0], v[1], v[9]);
    } else if (!strncmp(line, "bva ", 4)) {
        if (sscanf(line + 4, "%lu %lu %lu %lu %lu %lu %lu %lu %lu %lu", &v[0], &v[1], &v[2], &v[3], &v[4], &v[5], &v[6],
                   &v[7], &v[8], &v[9]) != 10 || v[0] > 1) {
            logf("### bv: %s: bad avenue-narrowing line '%s'", path, line);
            return;
        }
        for (k = 1; k < 10; k++)
            if (!bv_variant(v[k])) { logf("### bv: %s: narrowing piece %lu is not a variant", path, v[k]); return; }
        for (k = 0; k < 9; k++) g_bv_av[v[0]][k] = (WORD)v[k + 1];
        logf("bv: %s: narrowing to the avenue on rows %lu, %lu = pieces %lu..%lu", path, v[0], v[0] + 1, v[1], v[9]);
    }
}

static int bv_is_piece(WORD id) {
    int k, j;
    if (!id || !g_bv_p[0]) return 0;
    for (k = 0; k < 7; k++) if (g_bv_p[k] == id) return 1;
    for (k = 0; k < 3; k++) if (g_bv_cap[k] == id) return 1;
    for (k = 0; k < 3; k++) for (j = 0; j < 9; j++) if (g_bv_tap[k][j] == id) return 1;
    for (k = 0; k < 2; k++) for (j = 0; j < 9; j++) if (g_bv_av[k][j] == id) return 1;
    return 0;
}

typedef struct { int x, z; DWORD want; } BvCell;

typedef struct {
    RbBuf b;
    int axis;
    BvCell *cell;
    int n;
} BvPass;

/* axis space -> real */
static int bv_rx(int axis, int s, int w) { return axis ? -w : s; }
static int bv_rz(int axis, int s, int w) { return axis ? s : w; }
static int bv_road(BvPass *p, int s, int w) { return rb_at(&p->b, bv_rx(p->axis, s, w), bv_rz(p->axis, s, w)) != 0; }
static int bv_full(BvPass *p, int s, int w) { return bv_road(p, s, w) && bv_road(p, s, w + 1) && bv_road(p, s, w + 2); }

static void bv_put(BvPass *p, int s, int w, WORD piece, int st) {
    if (p->n >= DAV_MAX_CELLS) return;
    p->cell[p->n].x = bv_rx(p->axis, s, w);
    p->cell[p->n].z = bv_rz(p->axis, s, w);
    p->cell[p->n].want = ((DWORD)piece << 8) | (DWORD)((st + p->axis) & 3);
    p->n++;
}

/* one run starting at column sa, rows w0..w0+2. -> 1 accepted (cells in p->cell), 0 refused (*why) */
static int bv_run1(BvPass *p, int sa, int w0, int *psb, const char **why, BYTE *kind) {
    int sb = sa, s, k, e, n, ncl = 0, endtyp[2], endkeep[2], endlo, endhi, normlo, normhi;
    *why = "";
    while (bv_full(p, sb + 1, w0) && sb - sa < BV_MAX_RUN - 1) sb++;
    *psb = sb;
    n = sb - sa + 1;
    if (n < BV_MIN_COLS) return 0;
    if (n < BV_MIN_RUN) { *why = "3-column run: a 3x3 block (bigrbt's)"; return 0; }
    /* kind: 0 clean, 1 arm N, 2 arm S, 3 both */
    for (s = sa; s <= sb; s++) {
        int no = bv_road(p, s, w0 - 1), so = bv_road(p, s, w0 + 3);
        kind[s - sa] = (BYTE)(no | (so << 1));
        if (no && !(bv_road(p, s, w0 - 2) && !bv_road(p, s - 1, w0 - 1) && !bv_road(p, s + 1, w0 - 1)))
            { *why = "road beside the boulevard is not a straight single road"; return 0; }
        if (so && !(bv_road(p, s, w0 + 4) && !bv_road(p, s - 1, w0 + 3) && !bv_road(p, s + 1, w0 + 3)))
            { *why = "road beside the boulevard is not a straight single road"; return 0; }
    }
    /* ends: e 0 = the +s end (column sb), e 1 = the -s end (column sa) */
    for (e = 0; e < 2; e++) {
        int se = e ? sa : sb, st = e ? -1 : 1, got = 0, row = -1, first = -1;
        for (k = 0; k < 3; k++) if (bv_road(p, se + st, w0 + k)) { got++; row = k; if (first < 0) first = k; }
        if (!got) { endtyp[e] = 1; endkeep[e] = -1; }
        else if (got == 1 && bv_road(p, se + 2 * st, w0 + row)) { endtyp[e] = 2; endkeep[e] = row; }
        else if (got == 2 && row == first + 1 && bv_road(p, se + 2 * st, w0 + first) && bv_road(p, se + 2 * st, w0 + row))
            { endtyp[e] = 3; endkeep[e] = first; }          /* task boulevard: two rows go on = the avenue */
        else { *why = "an end where the roads going on are not one road or an avenue"; return 0; }
        if (endtyp[e] == 1 && !g_bv_cap[0]) { *why = "no cap pieces declared"; return 0; }
        if (endtyp[e] == 2 && !g_bv_tap[e ? 2 - row : row][0]) { *why = "no taper pieces declared"; return 0; }
        if (endtyp[e] == 3 && !g_bv_av[e ? 1 - first : first][0]) { *why = "no avenue-narrowing pieces declared"; return 0; }
    }
    endhi = endtyp[0] == 1 ? 1 : BV_TAPER;                 /* end-region widths */
    endlo = endtyp[1] == 1 ? 1 : BV_TAPER;
    normlo = sa + endlo;
    normhi = sb - endhi;
    if (normhi < normlo) { *why = "run too short for its ends"; return 0; }
    for (s = normlo; s <= normhi; s++) ncl += kind[s - sa] == 0;
    if (ncl < BV_MIN_COLS) { *why = "fewer than 3 boulevard columns"; return 0; }
    for (s = sa; s < normlo; s++) if (kind[s - sa]) { *why = "a junction inside an end region"; return 0; }
    for (s = normhi + 1; s <= sb; s++) if (kind[s - sa]) { *why = "a junction inside an end region"; return 0; }
    if (kind[normlo - sa] || kind[normhi - sa]) { *why = "a junction next to an end region"; return 0; }
    /* isolated: every ROAD cell 8-touching the run is the run, a junction arm or the road a taper goes on into */
    for (s = sa - 1; s <= sb + 1; s++)
        for (k = -1; k <= 3; k++) {
            int in = s >= sa && s <= sb && k >= 0 && k <= 2, ok;
            if (in || !bv_road(p, s, w0 + k)) continue;
            ok = (s >= sa && s <= sb && k == -1 && (kind[s - sa] & 1)) || (s >= sa && s <= sb && k == 3 && (kind[s - sa] & 2)) ||
                 (s == sb + 1 && endtyp[0] >= 2 && (k == endkeep[0] || (endtyp[0] == 3 && k == endkeep[0] + 1))) ||
                 (s == sa - 1 && endtyp[1] >= 2 && (k == endkeep[1] || (endtyp[1] == 3 && k == endkeep[1] + 1)));
            if (!ok) { *why = "touches road"; return 0; }
        }
    /* pieces */
    p->n = 0;
    for (e = 0; e < 2; e++) {
        int col, row;
        if (endtyp[e] == 1) {
            for (row = 0; row < 3; row++)
                bv_put(p, e ? sa : sb, w0 + (e ? 2 - row : row), g_bv_cap[row], e ? 2 : 0);
        } else {
            /* taper (2): canonical kept row 2 - row at the -s end; avenue (3): canonical first row 1 - first */
            WORD *set = endtyp[e] == 2 ? g_bv_tap[e ? 2 - endkeep[e] : endkeep[e]] : g_bv_av[e ? 1 - endkeep[e] : endkeep[e]];
            for (col = 0; col < BV_TAPER; col++)
                for (row = 0; row < 3; row++)
                    bv_put(p, e ? sa + BV_TAPER - 1 - col : sb - BV_TAPER + 1 + col, w0 + (e ? 2 - row : row),
                           set[3 * col + row], e ? 2 : 0);
        }
    }
    for (s = normlo; s <= normhi; s++) {
        int kd = kind[s - sa];
        if (!kd) {
            /* the median ends in a nose next to a junction, a cap or a taper; it goes on into an avenue narrowing */
            int hi = (s == normhi && endtyp[0] != 3) || kind[s + 1 - sa], lo = (s == normlo && endtyp[1] != 3) || kind[s - 1 - sa];
            bv_put(p, s, w0, g_bv_p[BV_OUTER], 2);
            bv_put(p, s, w0 + 2, g_bv_p[BV_OUTER], 0);
            bv_put(p, s, w0 + 1, g_bv_p[hi && lo ? BV_NOSE2 : hi || lo ? BV_NOSE : BV_MIDDLE], lo && !hi ? 2 : 0);
        } else {
            bv_put(p, s, w0 + 1, g_bv_p[BV_JM], 0);
            if (kd == 1) { bv_put(p, s, w0, g_bv_p[BV_JN], 0); bv_put(p, s, w0 + 2, g_bv_p[BV_JF], 0); }
            else if (kd == 2) { bv_put(p, s, w0, g_bv_p[BV_JF], 2); bv_put(p, s, w0 + 2, g_bv_p[BV_JN], 2); }
            else { bv_put(p, s, w0, g_bv_p[BV_JN], 0); bv_put(p, s, w0 + 2, g_bv_p[BV_JN], 2); }
        }
    }
    return 1;
}

/* -> 1 when an accepted run reached the read border (the caller re-runs over the whole map) */
static int bv_pass(BYTE *mgr, int x0, int z0, int x1, int z1, int W, int H, const char *who, BYTE *keep) {
    void *lay = *(void **)(mgr + 0x3c);
    BvPass P;
    BYTE *mem, kind[BV_MAX_RUN];
    SIZE_T nbuf;
    int axis, x, z, k, border = 0, nruns = 0, nwall = 0, nrev = 0;
    P.b.x0 = x0; P.b.z0 = z0; P.b.w = x1 - x0 + 1; P.b.h = z1 - z0 + 1;
    nbuf = (SIZE_T)P.b.w * P.b.h;
    mem = (BYTE *)VirtualAlloc(NULL, nbuf * 4 + DAV_MAX_CELLS * sizeof(BvCell), MEM_COMMIT, PAGE_READWRITE);
    if (!mem) return 0;
    P.b.c = (DWORD *)mem;
    P.cell = (BvCell *)(mem + nbuf * 4);
    for (z = 0; z < P.b.h; z++)
        for (x = 0; x < P.b.w; x++) P.b.c[z * P.b.w + x] = rb_read(mgr, lay, x0 + x, z0 + z, W, H);
    for (axis = 0; axis < 2; axis++) {
        int s0 = axis ? z0 : x0, s1 = axis ? z1 : x1, wl = axis ? -x1 : z0, wh = axis ? -x0 : z1, s, w;
        P.axis = axis;
        for (w = wl; w <= wh; w++)
            for (s = s0; s <= s1; s++) {
                const char *why = "";
                int sb, nw = 0;
                if (!bv_full(&P, s, w) || bv_full(&P, s - 1, w)) continue;
                if (!bv_run1(&P, s, w, &sb, &why, kind)) {
                    if (*why && sb - s + 1 >= 2 * BV_MIN_COLS)
                        logf("bv: %s: run axis %d from (%d,%d), %d column(s) left to the stock tiler: %s", who, axis,
                             bv_rx(axis, s, w), bv_rz(axis, s, w), sb - s + 1, why);
                    continue;
                }
                for (k = 0; k < P.n; k++) {          /* the run or its ring at the read border: seen cut, not written */
                    int cx = P.cell[k].x, cz = P.cell[k].z;
                    if ((cx <= x0 + 1 && x0 > 0) || (cz <= z0 + 1 && z0 > 0) || (cx >= x1 - 1 && x1 < W - 1) ||
                        (cz >= z1 - 1 && z1 < H - 1))
                        break;
                }
                if (k < P.n) { border = 1; continue; }
                nruns++;
                for (k = 0; k < P.n; k++) {
                    int cx = P.cell[k].x, cz = P.cell[k].z, pos[3];
                    DWORD cur = rb_at(&P.b, cx, cz);
                    if (keep) keep[(cz - z0) * P.b.w + (cx - x0)] = 1;
                    if ((((cur & 0xffff) << 8) | ((cur >> 16) & 3)) == P.cell[k].want) continue;
                    pos[0] = cx << 8; pos[1] = cz << 8; pos[2] = 0;
                    ((PFN_Put)(g_rb_m + 0x8919))(mgr, 0, lay, pos, P.cell[k].want, -1, 8, 0);
                    nw++;
                }
                if (nw || !strcmp(who, "load"))
                    logf("bv: %s: boulevard axis %d, columns %d..%d at row %d, %d cell(s), %d written", who, axis, s, sb,
                         w, P.n, nw);
                nwall += nw;
            }
    }
    /* boulevard pieces (one cell in from the read border) that no run kept: back to stock */
    if (keep)
        for (z = z0 + 1; z < z1; z++)
            for (x = x0 + 1; x < x1; x++) {
                DWORD v = rb_at(&P.b, x, z);
                int rect[6];
                if (!v || !bv_is_piece((WORD)(v & 0xffff)) || keep[(z - z0) * P.b.w + (x - x0)]) continue;
                rect[0] = x << 8; rect[1] = z << 8; rect[2] = 0; rect[3] = x << 8; rect[4] = z << 8; rect[5] = 0;
                ((PFN_Retile)VT(mgr, 0xb0))(mgr, 0, rect, 3);
                nrev++;
                logf("bv: %s: (%d,%d) boulevard piece %lu no longer in a run -> stock retile", who, x, z, v & 0xffff);
            }
    VirtualFree(mem, 0, MEM_RELEASE);
    InterlockedExchangeAdd(&g_bv_n_runs, nruns);
    InterlockedExchangeAdd(&g_bv_n_cells, nwall);
    InterlockedExchangeAdd(&g_bv_n_rev, nrev);
    return border;
}

static void bv_run(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who) {
    int W = (*(int *)(mgr + 0x5c) >> 8) + 1, H = (*(int *)(mgr + 0x60) >> 8) + 1, M = 24, full;
    BYTE *keep;
    if (!g_bv_p[0] || W < 4 || H < 4 || W > 4096 || H > 4096) return;
    x0 -= M; z0 -= M; x1 += M; z1 += M;
    if (x0 < 0) x0 = 0;
    if (z0 < 0) z0 = 0;
    if (x1 > W - 1) x1 = W - 1;
    if (z1 > H - 1) z1 = H - 1;
    full = x0 == 0 && z0 == 0 && x1 == W - 1 && z1 == H - 1;
    keep = (BYTE *)VirtualAlloc(NULL, (SIZE_T)(x1 - x0 + 1) * (z1 - z0 + 1), MEM_COMMIT, PAGE_READWRITE);
    if (!keep) return;
    if (bv_pass(mgr, x0, z0, x1, z1, W, H, who, keep) && !full) {
        VirtualFree(keep, 0, MEM_RELEASE);
        logf("bv: %s: a boulevard reached the read border - whole-map pass", who);
        keep = (BYTE *)VirtualAlloc(NULL, (SIZE_T)W * H, MEM_COMMIT, PAGE_READWRITE);
        if (!keep) return;
        bv_pass(mgr, 0, 0, W - 1, H - 1, W, H, who, keep);
    }
    VirtualFree(keep, 0, MEM_RELEASE);
}

static void bv_stats(void) {
    static LONG last;
    LONG n = g_bv_n_runs + g_bv_n_cells + g_bv_n_rev;
    if (!g_bv_p[0] || n == last) return;
    last = n;
    logf("stats: bv runs seen=%ld, cells written=%ld, cells reverted=%ld", g_bv_n_runs, g_bv_n_cells, g_bv_n_rev);
}
