/* sc3netmod_avl.c - the AVL block of sc3netmod.dll (task avcore, 2026-10-19): one-way avenue halves.
 * #included by sc3netmod.c after the other road blocks; runs on RBT's retile-pass and city-load hooks (rb_pass /
 * rb_load_pass call avl_run LAST, after DBV / DAV / AVX / BV / RBT9 / the hwave road pass, so the siblings' pieces are
 * in place when a band end is checked). Contract: re/analysis/AVENUE_LANES.md; plan verify/avlanes/PLAN.md.
 *
 * Owner 2026-10-19: avenues are 2 lanes each way, one direction per half, right-hand traffic; an avenue the mod cannot
 * convert whole stays stock two-way. Stock 11204 state s = the half (its median on world side s, N E S W = 0 1 2 3;
 * 26,752 shipped cells, 100%); a one-way half runs toward side (s + 3) % 4.
 *
 * Table lines (netpack manifest key `avenue_lines`):
 *   avls <piece>                 the one-way straight half (a variant of 11204), written at the cell's 11204 state
 *   avlu <piece>                 the end U-turn quarter (a variant of 11203), written at the cell's 11203 state
 *   avlc <piece> <base> <side>   a one-way variant of a crossing / slope piece; at the base's state 0 its lanes run
 *                                toward world side <side>; at state s toward (side + s) % 4
 *   avlj <piece> <NESW>          a sibling's piece a band may END on: per side at state 0, I = a half's traffic
 *                                enters the piece across it, O = leaves across it, . = none
 * The rule:
 *   band row   along z: (x, z) holds a straight half at state 1 and (x + 1, z) at state 3; along x: (x, z) state 2 and
 *              (x, z + 1) state 0 ("straight" = stock 11204 or our avls piece); or both cells hold the same avlc base
 *              (stock or ours) with its road along the band
 *   band       the maximal run of band rows; it converts only if BOTH ends are acceptable, else it stays stock
 *   end        the row past the run: off the map; or the stock end U pair (11203 or ours: along z to the N x- 11203.3
 *              x+ 11203.0, to the S x- 2 x+ 1; along x to the E z- 0 z+ 1, to the W z- 3 z+ 2, measured on the 15
 *              shipped cities); or two avlj pieces whose letters on the side facing the band say I where the half's
 *              traffic flows into the piece and O where it flows out
 *   guard      every cell written holds a stock id (< 20000) or one of ours; never a cell dbv_claimed / hwave_claimed
 * Write = the game's piece writer FUN_10008919 per cell (as AVX / DAV). Our pieces in a band that no longer converts,
 * and in no band, get the rect retile FUN_100151f1 (not Protected) BEFORE the writes (AVX's order). Save: every piece
 * saves as its base at its own state (g_base, SAVEBASE), so a game without the mod loads the stock avenue.
 * Routing: LANEDENSITY enforces the variants' one-way matrices (default mode). Off: SC3NETMOD_AVL=0.
 */

#define AVL_MAXC 32
#define AVL_MAXJ 64
#define AVL_MAXLEN 4096                                     /* longest band walked, rows */

typedef struct { WORD piece, base; BYTE side; } AvlC;
typedef struct { WORD piece; char e[4]; } AvlJ;
static WORD g_avl_uturn;                                    /* g_avl_straight, g_avl_on: sc3netmod_rbt.c */
static AvlC g_avl_c[AVL_MAXC];
static AvlJ g_avl_j[AVL_MAXJ];
static int g_avl_nc, g_avl_nj;
static BYTE *g_avl_map;                                     /* 1 + travel side of a converted band cell, 0xff = U-turn cell */
static int g_avl_mw, g_avl_mh;
static volatile LONG g_avl_n_bands, g_avl_n_refused, g_avl_n_cells, g_avl_n_rev;
static const signed char AVL_D[4][2] = { { 0, -1 }, { 1, 0 }, { 0, 1 }, { -1, 0 } };      /* N E S W */

static void avl_line(const char *path, const char *line) {
    unsigned long v, b, s;
    char e[8];
    if (!strncmp(line, "avls ", 5) || !strncmp(line, "avlu ", 5)) {
        int u = line[3] == 'u';
        if (sscanf(line + 5, "%lu", &v) != 1 || !v || v > 0xffff || g_base[v] != (u ? 11203 : 11204)) {
            logf("### avl: %s: bad line or piece not a variant of %s: '%s'", path, u ? "11203" : "11204", line);
            return;
        }
        if (u) g_avl_uturn = (WORD)v; else g_avl_straight = (WORD)v;
        logf("avl: %s: %s piece %lu", path, u ? "end U-turn" : "one-way straight half", v);
        return;
    }
    if (!strncmp(line, "avlc ", 5)) {
        if (sscanf(line + 5, "%lu %lu %lu", &v, &b, &s) != 3 || !v || v > 0xffff || !b || b > 0xffff || s > 3 ||
            g_base[v] != (WORD)b || g_avl_nc >= AVL_MAXC) {
            logf("### avl: %s: bad crossing line (or not a variant of its base, or too many): '%s'", path, line);
            return;
        }
        g_avl_c[g_avl_nc].piece = (WORD)v; g_avl_c[g_avl_nc].base = (WORD)b; g_avl_c[g_avl_nc].side = (BYTE)s;
        g_avl_nc++;
        logf("avl: %s: one-way %lu on base %lu, lanes toward side %lu at state 0", path, v, b, s);
        return;
    }
    if (!strncmp(line, "avlj ", 5)) {
        int k;
        if (sscanf(line + 5, "%lu %4s", &v, e) != 2 || !v || v > 0xffff || strlen(e) != 4 || !g_base[v] ||
            g_avl_nj >= AVL_MAXJ) {
            logf("### avl: %s: bad join line (or piece not a variant, or too many): '%s'", path, line);
            return;
        }
        for (k = 0; k < 4; k++)
            if (e[k] != 'I' && e[k] != 'O' && e[k] != '.') { logf("### avl: %s: letters must be I / O / . : '%s'", path, line); return; }
        g_avl_j[g_avl_nj].piece = (WORD)v;
        memcpy(g_avl_j[g_avl_nj].e, e, 4);
        g_avl_nj++;
        logf("avl: %s: join piece %lu, sides N E S W %.4s at state 0", path, v, e);
    }
}

static int avl_own(WORD id) {
    int k;
    if (!id) return 0;
    if (id == g_avl_straight || id == g_avl_uturn) return 1;
    for (k = 0; k < g_avl_nc; k++) if (g_avl_c[k].piece == id) return 1;
    return 0;
}

/* AVENUE_LANES.md 5: for siblings */
static int avl_dir(int x, int z) {
    BYTE m;
    if (!g_avl_map || x < 0 || z < 0 || x >= g_avl_mw || z >= g_avl_mh) return -1;
    m = g_avl_map[z * g_avl_mw + x];
    return (m && m != 0xff) ? m - 1 : -1;
}

static int avl_claimed(int x, int z) {
    if (!g_avl_map || x < 0 || z < 0 || x >= g_avl_mw || z >= g_avl_mh) return 0;
    return g_avl_map[z * g_avl_mw + x] != 0;
}

/* ---------------------------------------------------------------- lazy cell reads for one pass */
typedef struct { BYTE *mgr; void *lay; int W, H; DWORD *c; BYTE *rd, *seen; } AvlPass;

static DWORD avl_at(AvlPass *p, int x, int z) {
    int i;
    if (x < 0 || z < 0 || x >= p->W || z >= p->H) return 0;
    i = z * p->W + x;
    if (!p->rd[i]) { p->c[i] = rb_read(p->mgr, p->lay, x, z, p->W, p->H); p->rd[i] = 1; }
    return p->c[i];
}

#define AVL_ID(v) ((WORD)((v) & 0xffff))
#define AVL_ST(v) ((int)(((v) >> 16) & 3))

static int avl_is_straight(WORD id) { return id == 11204 || (g_avl_straight && id == g_avl_straight); }

/* the crossing table entry for a cell id (stock base or one of our variants), -1 none */
static int avl_cross_of(WORD id) {
    int k;
    for (k = 0; k < g_avl_nc; k++) if (g_avl_c[k].piece == id || g_avl_c[k].base == id) return k;
    return -1;
}

/* the variant of base `b` whose lanes run toward world side `dir` at state `st`, 0 none */
static WORD avl_cross_want(WORD b, int st, int dir) {
    int k;
    for (k = 0; k < g_avl_nc; k++)
        if (g_avl_c[k].base == b && ((g_avl_c[k].side + st) & 3) == dir) return g_avl_c[k].piece;
    return 0;
}

static int avl_free(AvlPass *p, int x, int z, DWORD v) {
    WORD id = AVL_ID(v);
    if (!v) return 0;
    if (id >= 20000 && !avl_own(id)) return 0;
    if (dbv_claimed(x, z) || hwave_claimed(x, z)) return 0;
    (void)p;
    return 1;
}

/* is row k of the band whose first-half cell at row 0 is (ax, az) a band row? axis 0 = along z, 1 = along x */
static int avl_row(AvlPass *p, int axis, int ax, int az, int k) {
    int dx = axis ? 1 : 0, dz = axis ? 0 : 1;
    int x = ax + dx * k, z = az + dz * k, bx = x + (axis ? 0 : 1), bz = z + (axis ? 1 : 0);
    DWORD a = avl_at(p, x, z), b = avl_at(p, bx, bz);
    int sa = axis ? 2 : 1, sb = axis ? 0 : 3, ca, cb;
    if (!avl_free(p, x, z, a) || !avl_free(p, bx, bz, b)) return 0;
    if (avl_is_straight(AVL_ID(a)) && avl_is_straight(AVL_ID(b))) return AVL_ST(a) == sa && AVL_ST(b) == sb;
    ca = avl_cross_of(AVL_ID(a)); cb = avl_cross_of(AVL_ID(b));
    if (ca < 0 || cb < 0 || g_avl_c[ca].base != g_avl_c[cb].base) return 0;
    {   /* the base's road must run along the band at both cells: its lanes toward side (side + st) */
        int ra = (g_avl_c[ca].side + AVL_ST(a)) & 1, rb = (g_avl_c[cb].side + AVL_ST(b)) & 1;
        int along = axis ? 1 : 0;                 /* along z: sides N / S (0 / 2, even); along x: E / W (odd) */
        if (ra != along || rb != along) return 0;
    }
    return 1;
}

/* letter of join piece `id` at state `st` on world side `w`; 0 = not a join piece */
static char avl_letter(WORD id, int st, int w) {
    int k;
    for (k = 0; k < g_avl_nj; k++) if (g_avl_j[k].piece == id) return g_avl_j[k].e[(w - st) & 3];
    return 0;
}

/* the row past the run at offset k (end = -1 the back end, +1 the forward end): acceptable? *u = 1 when it is the U */
static int avl_end(AvlPass *p, int axis, int ax, int az, int k, int end, int *u) {
    static const int USTATE[2][2][2] = { { { 3, 0 }, { 2, 1 } }, { { 3, 2 }, { 0, 1 } } };   /* [axis][fwd][A/B] */
    int dx = axis ? 1 : 0, dz = axis ? 0 : 1;
    int x = ax + dx * k, z = az + dz * k, bx = x + (axis ? 0 : 1), bz = z + (axis ? 1 : 0);
    int fwd = end > 0, da = axis ? 1 : 0, db = axis ? 3 : 2;     /* travel: along z A runs N, B runs S; along x A E, B W */
    int face = axis ? (fwd ? 3 : 1) : (fwd ? 0 : 2);             /* the end piece's side facing the band */
    int toward = axis ? (fwd ? 1 : 3) : (fwd ? 2 : 0);           /* travel side that points into this end */
    DWORD a, b;
    char la, lb;
    *u = 0;
    if (x < 0 || z < 0 || bx < 0 || bz < 0 || x >= p->W || z >= p->H || bx >= p->W || bz >= p->H) return 1;   /* map edge */
    a = avl_at(p, x, z); b = avl_at(p, bx, bz);
    if (!a && !b) return 0;
    if ((AVL_ID(a) == 11203 || (g_avl_uturn && AVL_ID(a) == g_avl_uturn)) &&
        (AVL_ID(b) == 11203 || (g_avl_uturn && AVL_ID(b) == g_avl_uturn)) &&
        AVL_ST(a) == USTATE[axis][fwd][0] && AVL_ST(b) == USTATE[axis][fwd][1] &&
        avl_free(p, x, z, a) && avl_free(p, bx, bz, b)) {
        *u = g_avl_uturn != 0;
        return g_avl_uturn != 0;
    }
    la = avl_letter(AVL_ID(a), AVL_ST(a), face);
    lb = avl_letter(AVL_ID(b), AVL_ST(b), face);
    if (!la || !lb) return 0;
    return la == (da == toward ? 'I' : 'O') && lb == (db == toward ? 'I' : 'O');
}

typedef struct { int x, z; DWORD want; } AvlW;

/* one band from the seed (ax, az): walk, decide, collect writes (accepted) or reverts (refused) */
static void avl_band(AvlPass *p, int axis, int ax, int az, AvlW *w, int *nw, int cap, int *rv, int *nrv, int rcap,
                     const char *who) {
    int dx = axis ? 1 : 0, dz = axis ? 0 : 1, k0 = 0, k1 = 0, k, ub = 0, uf = 0, ok;
    while (k0 > -AVL_MAXLEN && avl_row(p, axis, ax, az, k0 - 1)) k0--;
    while (k1 < AVL_MAXLEN && avl_row(p, axis, ax, az, k1 + 1)) k1++;
    for (k = k0; k <= k1; k++) {                                  /* mark every row seen: one walk per band per pass */
        int x = ax + dx * k, z = az + dz * k;
        p->seen[z * p->W + x] = 1;
    }
    ok = avl_end(p, axis, ax, az, k0 - 1, -1, &ub) && avl_end(p, axis, ax, az, k1 + 1, 1, &uf);
    for (k = k0; ok && k <= k1; k++) {                             /* every crossing row needs a variant per direction */
        int c;
        for (c = 0; c < 2 && ok; c++) {
            int cx = ax + dx * k + (c && !axis ? 1 : 0), cz = az + dz * k + (c && axis ? 1 : 0);
            DWORD v = avl_at(p, cx, cz);
            int ci = avl_cross_of(AVL_ID(v)), dir = axis ? (c ? 3 : 1) : (c ? 2 : 0);
            if (!avl_is_straight(AVL_ID(v)) && (ci < 0 || !avl_cross_want(g_avl_c[ci].base, AVL_ST(v), dir))) ok = 0;
        }
    }
    for (k = k0 - 1; k <= k1 + 1; k++) {
        int x = ax + dx * k, z = az + dz * k, c;
        int end = k < k0 || k > k1, isu = (k < k0 && ub) || (k > k1 && uf);
        if (end && !isu) continue;                                /* a sibling's piece or the map edge: not ours */
        for (c = 0; c < 2; c++) {
            int cx = x + (c && !axis ? 1 : 0), cz = z + (c && axis ? 1 : 0);
            DWORD v = avl_at(p, cx, cz), want;
            WORD id = AVL_ID(v);
            int st = AVL_ST(v), dir = axis ? (c ? 3 : 1) : (c ? 2 : 0);
            if (!v) continue;
            if (ok) {
                if (isu) want = ((DWORD)g_avl_uturn << 8) | st;
                else if (avl_is_straight(id)) want = ((DWORD)g_avl_straight << 8) | st;
                else want = ((DWORD)avl_cross_want(g_avl_c[avl_cross_of(id)].base, st, dir) << 8) | st;
                if (*nw < cap) { w[*nw].x = cx; w[*nw].z = cz; w[*nw].want = want; (*nw)++; }
                if (g_avl_map && cx < g_avl_mw && cz < g_avl_mh) g_avl_map[cz * g_avl_mw + cx] = isu ? 0xff : (BYTE)(1 + dir);
            } else {
                if (avl_own(id) && *nrv < rcap) { rv[2 * *nrv] = cx; rv[2 * *nrv + 1] = cz; (*nrv)++; }
                if (g_avl_map && cx < g_avl_mw && cz < g_avl_mh) g_avl_map[cz * g_avl_mw + cx] = 0;
            }
        }
    }
    if (ok) InterlockedIncrement(&g_avl_n_bands); else InterlockedIncrement(&g_avl_n_refused);
    if (ok && k1 - k0 + 1 >= 1) {
        static volatile LONG nlog;
        if (InterlockedIncrement(&nlog) <= 200 || strcmp(who, "load"))
            logf("avl: %s: band along %s from (%d,%d) rows %d..%d -> one-way (ends: %s / %s)", who, axis ? "x" : "z",
                 ax, az, k0, k1, ub ? "U-turn" : "join or edge", uf ? "U-turn" : "join or edge");
    }
}

static void avl_run(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who) {
    AvlPass P;
    AvlW *w;
    int *rv, nw = 0, nrv = 0, cap, rcap, x, z, k, n = 0, load = !strcmp(who, "load");
    if (!g_avl_on) return;
    P.mgr = mgr; P.lay = *(void **)(mgr + 0x3c);
    P.W = (*(int *)(mgr + 0x5c) >> 8) + 1; P.H = (*(int *)(mgr + 0x60) >> 8) + 1;
    if (P.W < 4 || P.H < 4 || P.W > 4096 || P.H > 4096) return;
    if (!g_avl_map || g_avl_mw != P.W || g_avl_mh != P.H) {
        if (g_avl_map) VirtualFree(g_avl_map, 0, MEM_RELEASE);
        g_avl_map = (BYTE *)VirtualAlloc(NULL, (SIZE_T)P.W * P.H, MEM_COMMIT, PAGE_READWRITE);
        g_avl_mw = P.W; g_avl_mh = P.H;
    }
    if (load && g_avl_map) ZeroMemory(g_avl_map, (SIZE_T)P.W * P.H);
    if (x0 < 0) x0 = 0;
    if (z0 < 0) z0 = 0;
    if (x1 > P.W - 1) x1 = P.W - 1;
    if (z1 > P.H - 1) z1 = P.H - 1;
    x0 -= 2; z0 -= 2; x1 += 2; z1 += 2;                            /* a pair's other half and the end rows */
    cap = load ? 1 << 20 : 1 << 16; rcap = load ? 1 << 18 : 1 << 14;
    P.c = (DWORD *)VirtualAlloc(NULL, (SIZE_T)P.W * P.H * 6 + (SIZE_T)cap * sizeof(AvlW) + (SIZE_T)rcap * 8,
                                MEM_COMMIT, PAGE_READWRITE);
    if (!P.c) return;
    P.rd = (BYTE *)(P.c + P.W * P.H);
    P.seen = P.rd + P.W * P.H;
    w = (AvlW *)(P.seen + P.W * P.H);
    rv = (int *)(w + cap);
    for (z = z0 < 0 ? 0 : z0; z <= z1 && z < P.H; z++)
        for (x = x0 < 0 ? 0 : x0; x <= x1 && x < P.W; x++) {
            DWORD v = avl_at(&P, x, z);
            WORD id = AVL_ID(v);
            int st = AVL_ST(v), ci;
            if (!v || P.seen[z * P.W + x]) continue;
            if (avl_is_straight(id)) {                            /* seed on the first half (state 1 along z, 2 along x) */
                if (st == 1 && avl_row(&P, 0, x, z, 0)) avl_band(&P, 0, x, z, w, &nw, cap, rv, &nrv, rcap, who);
                else if (st == 2 && avl_row(&P, 1, x, z, 0)) avl_band(&P, 1, x, z, w, &nw, cap, rv, &nrv, rcap, who);
                else if (st == 3 && avl_row(&P, 0, x - 1, z, 0) && !P.seen[z * P.W + x - 1])
                    avl_band(&P, 0, x - 1, z, w, &nw, cap, rv, &nrv, rcap, who);
                else if (st == 0 && avl_row(&P, 1, x, z - 1, 0) && !P.seen[(z - 1) * P.W + x])
                    avl_band(&P, 1, x, z - 1, w, &nw, cap, rv, &nrv, rcap, who);
            } else if ((ci = avl_cross_of(id)) >= 0) {             /* a crossing row: try it as either half of either axis */
                if (avl_row(&P, 0, x, z, 0)) avl_band(&P, 0, x, z, w, &nw, cap, rv, &nrv, rcap, who);
                else if (avl_row(&P, 0, x - 1, z, 0)) avl_band(&P, 0, x - 1, z, w, &nw, cap, rv, &nrv, rcap, who);
                else if (avl_row(&P, 1, x, z, 0)) avl_band(&P, 1, x, z, w, &nw, cap, rv, &nrv, rcap, who);
                else if (avl_row(&P, 1, x, z - 1, 0)) avl_band(&P, 1, x, z - 1, w, &nw, cap, rv, &nrv, rcap, who);
            }
        }
    /* our pieces in the box that no accepted band claims: back to stock */
    for (z = z0 < 0 ? 0 : z0; z <= z1 && z < P.H; z++)
        for (x = x0 < 0 ? 0 : x0; x <= x1 && x < P.W; x++) {
            DWORD v = avl_at(&P, x, z);
            if (v && avl_own(AVL_ID(v)) && !avl_claimed(x, z) && nrv < rcap) { rv[2 * nrv] = x; rv[2 * nrv + 1] = z; nrv++; }
        }
    for (k = 0; k < nrv; k++) {
        int rect[6];
        rect[0] = rv[2 * k] << 8; rect[1] = rv[2 * k + 1] << 8; rect[2] = 0;
        rect[3] = rv[2 * k] << 8; rect[4] = rv[2 * k + 1] << 8; rect[5] = 0;
        ((PFN_Retile)VT(mgr, 0xb0))(mgr, 0, rect, 3);
    }
    if (nrv) ZeroMemory(P.rd, (SIZE_T)P.W * P.H);                 /* a retile may have changed neighbours: read again */
    for (k = 0; k < nw; k++) {
        DWORD cur = avl_at(&P, w[k].x, w[k].z);
        int pos[3];
        if (((DWORD)AVL_ID(cur) << 8 | AVL_ST(cur)) == w[k].want) continue;
        pos[0] = w[k].x << 8; pos[1] = w[k].z << 8; pos[2] = 0;
        ((PFN_Put)(g_rb_m + 0x8919))(mgr, 0, P.lay, pos, w[k].want, -1, 8, 0);
        n++;
    }
    if (n || nrv || load)
        logf("avl: %s pass over (%d,%d)-(%d,%d): %d cell(s) written, %d reverted%s", who, x0, z0, x1, z1, n, nrv,
             nw >= cap ? " (WRITE LIST FULL)" : "");
    VirtualFree(P.c, 0, MEM_RELEASE);
    InterlockedExchangeAdd(&g_avl_n_cells, n);
    InterlockedExchangeAdd(&g_avl_n_rev, nrv);
}

static void avl_stats(void) {
    static LONG last;
    LONG n = g_avl_n_bands + g_avl_n_refused + g_avl_n_cells + g_avl_n_rev;
    if (!g_avl_on || n == last) return;
    last = n;
    logf("stats: avl bands converted=%ld, refused=%ld, cells written=%ld, reverted=%ld", g_avl_n_bands, g_avl_n_refused,
         g_avl_n_cells, g_avl_n_rev);
}
