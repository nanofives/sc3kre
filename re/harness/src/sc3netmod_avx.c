/* sc3netmod_avx.c - the AVX block of sc3netmod.dll (task avx, 2026-10-17): straight avenue intersections.
 * #included by sc3netmod.c after the DAV block; shares RBT's retile-pass and city-load hooks (rb_pass / rb_load_pass
 * call avx_run when `avxb` lines were read). Offline twin, rule, art and lanes: re/tools/netmod/avx.py; evidence
 * verify/avx/.
 *
 * Stock tiles two crossing avenues (11204, two parallel roads each) as a 2x2 of 43 with T 39 on the arm cells, and a
 * road across an avenue as a column of 43. This block re-pieces those shapes as one paved box. A package declares:
 *  `avxb <piece> <NESW> <save>`  a box cell piece whose edges at state 0 are N E S W, each I (another box cell), A (an
 *                                arm cell) or C (closed); <save> 1 = save it as 11204 (a closed edge on S at state 0:
 *                                the far half of a T, stock keeps the avenue half there)
 *  `avxa <piece> <side>`         the cell of an avenue arm next to the box: 11204 (state 0) with the median nose at
 *                                <side> (1 E, 3 W); placed in the cell's 11204 state
 * The rule, "road" = a ROAD cell (rb_read):
 *  box     w x h road cells, (w, h) = (2, 2), (1, 2) or (2, 1), its four diagonal corner cells hold no road
 *  side    the cells just outside one box side: all road (an arm) or none (closed); else no box
 *  arm     clean and straight for AVX_ARM_LEN cells: the side's run goes on that far with no road flanking it;
 *          2 wide = avenue arm, 1 wide = road arm
 *  kinds   (2, 2): 4 or 3 avenue arms (avenue x avenue, avenue T); (1, 2) / (2, 1): both avenue arms (the avenue goes
 *          through) and 2 or 1 road arms (road x avenue, road T). Anything else stays stock.
 *  guard   every cell to write holds a stock id (< 20000) or one of ours: another block's pieces are never taken.
 * This refuses RBT's 2x2 roundabout (its exits hold one road each), 3x3 blocks (a corner holds road), three parallel
 * roads (an arm flank holds road) and diagonal shapes (no clean straight arm).
 * Write = the game's piece writer FUN_10008919 per cell (as RBT / DAV). Revert: an AVX piece that no junction keeps
 * gets the rect retile FUN_100151f1 (not Protected), BEFORE the writes, so a revert's stock retile cannot undo a
 * neighbouring junction's cells. Save: box pieces as their base 43 or 11204 (`avxb ... 1`), arm pieces as 11204.
 * Off: SC3NETMOD_AVX=0.
 */

#define AVX_ARM_LEN 2
#define AVX_MAX_BOX 16

typedef struct { WORD piece; char e[4]; BYTE save11204; } AvxBox;
static AvxBox g_avx_box[AVX_MAX_BOX];
static WORD g_avx_arm[4];                              /* by the box side at state 0: [1] E, [3] W */
static volatile LONG g_avx_n_j, g_avx_n_cells, g_avx_n_rev;
static const signed char AVX_DIR[4][2] = { { 0, -1 }, { 1, 0 }, { 0, 1 }, { -1, 0 } };     /* N E S W */

static void avx_line(const char *path, const char *line) {
    unsigned long v, s;
    char e[8];
    int k;
    if (!strncmp(line, "avxa ", 5)) {
        if (sscanf(line + 5, "%lu %lu", &v, &s) != 2 || !v || v > 0xffff || (s != 1 && s != 3) || g_base[v] != 11204) {
            logf("### avx: %s: bad arm line or piece not a variant of 11204: '%s'", path, line);
            return;
        }
        g_avx_arm[s] = (WORD)v;
        logf("avx: %s: arm piece %lu = 11204 with the median nose at its %s end", path, v, s == 1 ? "E" : "W");
        return;
    }
    if (strncmp(line, "avxb ", 5)) return;
    if (sscanf(line + 5, "%lu %4s %lu", &v, e, &s) != 3 || !v || v > 0xffff || s > 1 || strlen(e) != 4 || !g_base[v]) {
        logf("### avx: %s: bad box line or piece not a variant: '%s'", path, line);
        return;
    }
    for (k = 0; k < 4; k++)
        if (e[k] != 'I' && e[k] != 'A' && e[k] != 'C') { logf("### avx: %s: edges must be I/A/C: '%s'", path, line); return; }
    if (g_avx_nbox >= AVX_MAX_BOX) { logf("### avx: %s: too many box pieces - ignored", path); return; }
    g_avx_box[g_avx_nbox].piece = (WORD)v;
    memcpy(g_avx_box[g_avx_nbox].e, e, 4);
    g_avx_box[g_avx_nbox].save11204 = (BYTE)s;
    g_avx_nbox++;
    logf("avx: %s: box piece %lu, edges N E S W %.4s at state 0%s", path, v, e, s ? ", saves as 11204" : "");
}

static int avx_own(WORD id) {
    int k;
    if (!id) return 0;
    for (k = 0; k < g_avx_nbox; k++) if (g_avx_box[k].piece == id) return 1;
    return id == g_avx_arm[1] || id == g_avx_arm[3];
}

static WORD avx_save_id(WORD id) {
    int k;
    for (k = 0; k < g_avx_nbox; k++) if (g_avx_box[k].piece == id) return g_avx_box[k].save11204 ? 11204 : 0;
    return 0;
}

/* edge pattern (N E S W) -> piece << 8 | state, 0 = none: the declared pattern turned by `state` (N -> E per state) */
static DWORD avx_box_of(const char *d) {
    int k, j, e;
    for (k = 0; k < 4; k++)
        for (j = 0; j < g_avx_nbox; j++) {
            for (e = 0; e < 4 && g_avx_box[j].e[e] == d[(e + k) % 4]; e++) ;
            if (e == 4) return ((DWORD)g_avx_box[j].piece << 8) | (DWORD)k;
        }
    return 0;
}

#define AVX_MAX_W 12                                    /* cells one junction writes: 4 box + 4 arms x 2 */
typedef struct { int n, x[AVX_MAX_W], z[AVX_MAX_W]; DWORD want[AVX_MAX_W]; const char *kind; } AvxJ;

static int avx_side(int X, int Z, int w, int h, int e, int i, int *cx, int *cz) {
    int n = (e % 2 == 0) ? w : h;
    if (i >= n) return 0;
    if (e == 0) { *cx = X + i; *cz = Z - 1; }
    else if (e == 2) { *cx = X + i; *cz = Z + h; }
    else if (e == 1) { *cx = X + w; *cz = Z + i; }
    else { *cx = X - 1; *cz = Z + i; }
    return 1;
}

/* the rule at box (X, Z, w, h) -> 1 and the cells to write in *j, 0 = no junction */
static int avx_check(RbBuf *b, int X, int Z, int w, int h, AvxJ *j) {
    int arms[4], e, i, k, x, z, nav = 0, nrd = 0, cx, cz;
    for (z = Z; z < Z + h; z++)
        for (x = X; x < X + w; x++) if (!rb_at(b, x, z)) return 0;
    if (rb_at(b, X - 1, Z - 1) || rb_at(b, X + w, Z - 1) || rb_at(b, X - 1, Z + h) || rb_at(b, X + w, Z + h)) return 0;
    for (e = 0; e < 4; e++) {
        int n = (e % 2 == 0) ? w : h, got = 0, dx = AVX_DIR[e][0], dz = AVX_DIR[e][1], pdx = dz ? 1 : 0, pdz = dx ? 1 : 0;
        int fx, fz, lx, lz;
        for (i = 0; avx_side(X, Z, w, h, e, i, &cx, &cz); i++) got += rb_at(b, cx, cz) != 0;
        arms[e] = 0;
        if (!got) continue;
        if (got != n) return 0;
        avx_side(X, Z, w, h, e, 0, &fx, &fz);
        avx_side(X, Z, w, h, e, n - 1, &lx, &lz);
        for (k = 0; k < AVX_ARM_LEN; k++) {
            for (i = 0; avx_side(X, Z, w, h, e, i, &cx, &cz); i++)
                if (!rb_at(b, cx + dx * k, cz + dz * k)) return 0;
            if (rb_at(b, fx + dx * k - pdx, fz + dz * k - pdz) || rb_at(b, lx + dx * k + pdx, lz + dz * k + pdz)) return 0;
        }
        arms[e] = n == 2 ? 2 : 1;                       /* 2 avenue, 1 road */
        if (n == 2) nav++; else nrd++;
    }
    if (w == 2 && h == 2) {
        if (nav < 3) return 0;
        j->kind = nav == 4 ? "avenue x avenue" : "avenue T";
    } else {
        int t0 = w == 1 ? 1 : 0;                        /* the through avenue's sides: E / W for a 1 x 2 box */
        if (arms[t0] != 2 || arms[t0 + 2] != 2 || !nrd) return 0;
        j->kind = nrd == 2 ? "road x avenue" : "road T";
    }
    j->n = 0;
    for (z = Z; z < Z + h; z++)
        for (x = X; x < X + w; x++) {
            char d[4];
            DWORD v;
            for (e = 0; e < 4; e++) {
                int nx = x + AVX_DIR[e][0], nz = z + AVX_DIR[e][1];
                if (nx >= X && nx < X + w && nz >= Z && nz < Z + h) d[e] = 'I';
                else d[e] = arms[e] ? 'A' : 'C';        /* a cell's outside edge on side e faces that side's arm */
            }
            if (!(v = avx_box_of(d))) return 0;
            j->x[j->n] = x; j->z[j->n] = z; j->want[j->n] = v; j->n++;
        }
    for (e = 0; e < 4; e++) {
        if (arms[e] != 2) continue;
        for (i = 0; i < 2; i++) {
            int s = (e == 1 || e == 3) ? (i == 0 ? 2 : 0) : (i == 0 ? 1 : 3);   /* 11204's states (avx.py half_state) */
            int d0 = (((e + 2) % 4) - s + 4) % 4;
            if (!g_avx_arm[d0]) return 0;
            avx_side(X, Z, w, h, e, i, &cx, &cz);
            j->x[j->n] = cx; j->z[j->n] = cz; j->want[j->n] = ((DWORD)g_avx_arm[d0] << 8) | (DWORD)s; j->n++;
        }
    }
    for (k = 0; k < j->n; k++) {                         /* never take another block's piece */
        WORD id = (WORD)(rb_at(b, j->x[k], j->z[k]) & 0xffff);
        if (id >= 20000 && !avx_own(id)) return 0;
    }
    return 1;
}

static void avx_read(BYTE *mgr, RbBuf *b, int W, int H) {
    void *lay = *(void **)(mgr + 0x3c);
    int x, z;
    for (z = 0; z < b->h; z++)
        for (x = 0; x < b->w; x++) b->c[z * b->w + x] = rb_read(mgr, lay, b->x0 + x, b->z0 + z, W, H);
}

/* cells [x0..x1] x [z0..z1] were edited (the retile pass's work box) or the whole map (load) */
static void avx_run(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who) {
    static const int WH[3][2] = { { 2, 2 }, { 1, 2 }, { 2, 1 } };
    void *lay = *(void **)(mgr + 0x3c);
    int W = (*(int *)(mgr + 0x5c) >> 8) + 1, H = (*(int *)(mgr + 0x60) >> 8) + 1;
    int ox0, oz0, ox1, oz1, rx0, rz0, rx1, rz1, x, z, k, t, nj = 0, nw = 0, nrev = 0, cap = 64;
    RbBuf b;
    BYTE *keep;
    AvxJ *js;
    if (!g_avx_on || W < 4 || H < 4 || W > 4096 || H > 4096) return;
    if (x1 > W - 1) x1 = W - 1;
    if (z1 > H - 1) z1 = H - 1;
    ox0 = x0 - 6; oz0 = z0 - 6; ox1 = x1 + 6; oz1 = z1 + 6;           /* box origins scanned */
    rx0 = ox0 + 2; rz0 = oz0 + 2; rx1 = ox1 - 1; rz1 = oz1 - 1;       /* cells whose every owner origin is scanned */
    b.x0 = ox0 - 3; b.z0 = oz0 - 3; b.w = ox1 - ox0 + 9; b.h = oz1 - oz0 + 9;
    if (b.x0 < 0) { b.w += b.x0; b.x0 = 0; }
    if (b.z0 < 0) { b.h += b.z0; b.z0 = 0; }
    if (b.x0 + b.w > W) b.w = W - b.x0;
    if (b.z0 + b.h > H) b.h = H - b.z0;
    if (ox0 < 0) ox0 = 0;
    if (oz0 < 0) oz0 = 0;
    if (ox1 > W - 1) ox1 = W - 1;
    if (oz1 > H - 1) oz1 = H - 1;
    if (b.w <= 0 || b.h <= 0) return;
    if (!strcmp(who, "load")) cap = 4096;
    b.c = (DWORD *)VirtualAlloc(NULL, (SIZE_T)b.w * b.h * 5 + (SIZE_T)cap * sizeof(AvxJ), MEM_COMMIT, PAGE_READWRITE);
    if (!b.c) return;
    keep = (BYTE *)(b.c + b.w * b.h);
    js = (AvxJ *)(keep + b.w * b.h);
    avx_read(mgr, &b, W, H);
    for (z = oz0; z <= oz1; z++)
        for (x = ox0; x <= ox1; x++) {
            if (!rb_at(&b, x, z)) continue;
            for (t = 0; t < 3 && nj < cap; t++) {
                if (!avx_check(&b, x, z, WH[t][0], WH[t][1], &js[nj])) continue;
                for (k = 0; k < js[nj].n; k++) keep[(js[nj].z[k] - b.z0) * b.w + (js[nj].x[k] - b.x0)] = 1;
                nj++;
            }
        }
    /* AVX pieces no junction keeps: back to stock, before the writes (a revert's retile reaches the neighbours) */
    for (z = rz0 < b.z0 ? b.z0 : rz0; z <= rz1 && z < b.z0 + b.h; z++)
        for (x = rx0 < b.x0 ? b.x0 : rx0; x <= rx1 && x < b.x0 + b.w; x++) {
            DWORD v = rb_at(&b, x, z);
            int rect[6];
            if (!v || !avx_own((WORD)(v & 0xffff)) || keep[(z - b.z0) * b.w + (x - b.x0)]) continue;
            rect[0] = x << 8; rect[1] = z << 8; rect[2] = 0; rect[3] = x << 8; rect[4] = z << 8; rect[5] = 0;
            ((PFN_Retile)VT(mgr, 0xb0))(mgr, 0, rect, 3);
            nrev++;
            logf("avx: %s: (%d,%d) piece %lu no longer in a junction -> stock retile", who, x, z, v & 0xffff);
        }
    if (nrev) avx_read(mgr, &b, W, H);
    for (t = 0; t < nj; t++) {
        int n = 0;
        for (k = 0; k < js[t].n; k++) {
            DWORD cur = rb_at(&b, js[t].x[k], js[t].z[k]);
            int pos[3];
            if ((((cur & 0xffff) << 8) | ((cur >> 16) & 3)) == js[t].want[k]) continue;
            pos[0] = js[t].x[k] << 8; pos[1] = js[t].z[k] << 8; pos[2] = 0;
            ((PFN_Put)(g_rb_m + 0x8919))(mgr, 0, lay, pos, js[t].want[k], -1, 8, 0);
            n++;
        }
        if (n)
            logf("avx: %s: %s, box from (%d,%d), %d cell(s), %d written: %lu.%lu %lu.%lu %lu.%lu %lu.%lu", who, js[t].kind,
                 js[t].x[0], js[t].z[0], js[t].n, n, js[t].want[0] >> 8, js[t].want[0] & 3, js[t].want[1] >> 8,
                 js[t].want[1] & 3, js[t].n > 2 ? js[t].want[2] >> 8 : 0, js[t].n > 2 ? js[t].want[2] & 3 : 0,
                 js[t].n > 3 ? js[t].want[3] >> 8 : 0, js[t].n > 3 ? js[t].want[3] & 3 : 0);
        nw += n;
    }
    if (nw || nrev || !strcmp(who, "load"))
        logf("avx: %s pass over origins (%d,%d)-(%d,%d): %d junction(s), %d cell(s) written, %d reverted", who, ox0, oz0,
             ox1, oz1, nj, nw, nrev);
    VirtualFree(b.c, 0, MEM_RELEASE);
    InterlockedExchangeAdd(&g_avx_n_j, nj);
    InterlockedExchangeAdd(&g_avx_n_cells, nw);
    InterlockedExchangeAdd(&g_avx_n_rev, nrev);
}

static void avx_stats(void) {
    static LONG last;
    LONG n = g_avx_n_j + g_avx_n_cells + g_avx_n_rev;
    if (!g_avx_on || n == last) return;
    last = n;
    logf("stats: avx junctions seen=%ld, cells written=%ld, cells reverted=%ld", g_avx_n_j, g_avx_n_cells, g_avx_n_rev);
}
