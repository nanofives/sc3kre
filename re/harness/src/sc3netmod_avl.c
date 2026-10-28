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
 *   avlu <piece>                 the end U-turn quarter (a variant of 11203), written at the cell's 11203 state; also
 *                                the OUTER bend of a corner (the same left turn)
 *   avlk <piece>                 the INNER bend of an avenue corner (a variant of 11203, a right turn), written at the
 *                                cell's 11203 state
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
 *              ; or a corner block (avl_corner_at): acceptable when the band beyond the corner converts (decided with
 *              it, recursively; a loop of bands closes on itself), so bands joined by corners convert all or nothing
 *   guard      every cell written holds a stock id (< 20000) or one of ours; never a cell dbv_claimed / hwave_claimed
 * Write = the game's piece writer FUN_10008919 per cell (as AVX / DAV). Our pieces in a band that no longer converts,
 * and in no band, get their base back at the same state BEFORE the writes (the stock piece they replaced; a rect
 * retile would keep a Protected base such as rail crossing 69, measured in the lab). Save: every piece
 * saves as its base at its own state (g_base, SAVEBASE), so a game without the mod loads the stock avenue.
 * Routing: LANEDENSITY enforces the variants' one-way matrices (default mode). Off: SC3NETMOD_AVL=0.
 */

#define AVL_MAXC 32
#define AVL_MAXJ 4096                                       /* every package's avlj lines together */
#define AVL_MAXLEN 4096                                     /* longest band walked, rows */

typedef struct { WORD piece, base; BYTE side; } AvlC;
typedef struct { WORD piece; char e[4]; } AvlJ;
static WORD g_avl_uturn, g_avl_corner;                      /* g_avl_straight, g_avl_on: sc3netmod_rbt.c */
static AvlC g_avl_c[AVL_MAXC];
static AvlJ g_avl_j[AVL_MAXJ];
static int g_avl_nc, g_avl_nj;
static BYTE *g_avl_map;                                     /* 1 + travel side of a converted band cell, 0xff = U-turn cell */
static int g_avl_mw, g_avl_mh;
static volatile LONG g_avl_n_bands, g_avl_n_refused, g_avl_n_cells, g_avl_n_rev;
static const signed char AVL_D[4][2] = { { 0, -1 }, { 1, 0 }, { 0, 1 }, { -1, 0 } };      /* N E S W */

static void avl_t_line(const char *path, const char *line);   /* task avpaint: avlt */
static void avp_line(const char *path, const char *line);     /* task avpaint: avlp (AVP block) */

static void avl_line(const char *path, const char *line) {
    unsigned long v, b, s;
    char e[8];
    if (!strncmp(line, "avlt ", 5)) { avl_t_line(path, line); return; }
    if (!strncmp(line, "avlp ", 5)) { avp_line(path, line); return; }
    if (!strncmp(line, "avls ", 5) || !strncmp(line, "avlu ", 5) || !strncmp(line, "avlk ", 5)) {
        int u = line[3] == 'u', kc = line[3] == 'k';
        if (sscanf(line + 5, "%lu", &v) != 1 || !v || v > 0xffff || g_base[v] != (u || kc ? 11203 : 11204)) {
            logf("### avl: %s: bad line or piece not a variant of %s: '%s'", path, u || kc ? "11203" : "11204", line);
            return;
        }
        if (u) g_avl_uturn = (WORD)v; else if (kc) g_avl_corner = (WORD)v; else g_avl_straight = (WORD)v;
        logf("avl: %s: %s piece %lu", path, u ? "end U-turn" : kc ? "corner inner bend" : "one-way straight half", v);
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

static int avl_is_t(WORD id);                               /* task avpaint: corner + T pieces */

static int avl_own(WORD id) {
    int k;
    if (!id) return 0;
    if (id == g_avl_straight || id == g_avl_uturn || (g_avl_corner && id == g_avl_corner)) return 1;
    for (k = 0; k < g_avl_nc; k++) if (g_avl_c[k].piece == id) return 1;
    return avl_is_t(id);
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
    if (!p->rd) return rb_read(p->mgr, p->lay, x, z, p->W, p->H);   /* avl_band_ok: no cache */
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

/* Corners (task avcore, 2026-10-19): a stock avenue corner is a 2 x 2 block past a band's last row. The end row holds
   the INNER bend (11203) and a half of the other axis (11204); the next row holds that half's partner (11204) and the
   OUTER bend (11203), diagonal to the inner one and at the SAME 11203 state (169 corner ends over the 15 shipped cities,
   8 patterns). Beside the block, on the inner bend's side, the other axis's band begins. One-way: the inner bend becomes
   the corner piece (avlk, a right turn whose median lane takes the wide arc), the outer bend the U-turn quarter (avlu,
   the same left turn), the two halves avls. The two bands join into one: both convert or neither does.
   A T / X on the outer cell (a road leaving the corner; avjunc's box pieces, orchestrator 2026-10-19): the outer cell
   may instead hold a piece declared with avlj whose letters say I on the side the incoming half flows in from and O on
   the side the outgoing half leaves by (the halves' travel decides which is which). That cell is the declaring
   stream's: avcore neither writes nor claims it, and joins the two bands through it as through a bend. */
/* [axis][fwd][inner on B] = 11203 / 11204 states of A, B (end row) and A2, B2 (next row, A2 beside A) */
static const signed char AVL_CST[2][2][2][4] = {
    { { { 0, 3, 2, 0 }, { 1, 3, 3, 2 } }, { { 1, 3, 0, 1 }, { 1, 2, 2, 0 } } },
    { { { 2, 0, 1, 2 }, { 2, 3, 3, 1 } }, { { 1, 0, 3, 1 }, { 2, 0, 0, 3 } } } };

typedef struct { int axis, x, z, n; } AvlSeed;                   /* a band being decided: first-half cell of row k0, rows */
#define AVL_DEPTH 64
typedef struct { AvlSeed s[AVL_DEPTH]; int n; char why[320]; } AvlStack;

/* task avpaint (2026-10-28): why a band stays two-way = the FIRST check that failed in its decision (through a corner
   the band beyond names itself). Logged by avl_band for every refused band, capped like the accepted-band lines. */
static const char AVL_SIDE[4] = { 'N', 'E', 'S', 'W' };
static void avl_why(AvlStack *stk, const char *fmt, ...) {
    va_list ap;
    if (!stk || stk->why[0]) return;
    va_start(ap, fmt);
    _vsnprintf(stk->why, sizeof(stk->why) - 1, fmt, ap);
    stk->why[sizeof(stk->why) - 1] = 0;
    va_end(ap);
}

static int avl_decide_r(AvlPass *p, int axis, int ax, int az, int *pk0, int *pk1, int *pub, int *puf, int assume,
                        AvlStack *stk);

static int avl_is_bend(WORD id, WORD ours) { return id == 11203 || (ours && id == ours); }

/* avl_corner_ok's dry run: the outer cell at (x, z) counts as a fitting avlj piece whatever stands there now */
static int g_avl_oas_x = -1, g_avl_oas_z = -1, g_avl_oas_hit;

/* is the outer cell `o` at (ox2, oz2) a declared avlj piece that fits the turn between its two block neighbours, the
   end-row half (mx, mz) and the next-row half (m2x, m2z)? A neighbour whose travel points into the outer cell flows in
   (letter I on that side), the other flows out (O). */
static int avl_outer_join(AvlPass *p, DWORD o, int ox2, int oz2, int mx, int mz, int m2x, int m2z) {
    int n;
    if (ox2 == g_avl_oas_x && oz2 == g_avl_oas_z) { g_avl_oas_hit = 1; return 1; }
    for (n = 0; n < 2; n++) {
        int nx = n ? m2x : mx, nz = n ? m2z : mz, t, w;
        DWORD v = avl_at(p, nx, nz);
        char l;
        if (!v) return 0;
        t = (AVL_ST(v) + 3) & 3;                                  /* the half's travel side */
        for (w = 0; w < 4; w++) if (ox2 + AVL_D[w][0] == nx && oz2 + AVL_D[w][1] == nz) break;
        if (w == 4) return 0;
        l = avl_letter(AVL_ID(o), AVL_ST(o), w);
        if (!l) return 0;
        if (l != ((nx + AVL_D[t][0] == ox2 && nz + AVL_D[t][1] == oz2) ? 'I' : 'O')) return 0;
    }
    return 1;
}

/* the corner block past the row at offset k: 0 none, 1 inner bend on A, 2 inner bend on B; *ox *oz = the other band's
   first-half cell beside the block, *oaxis its axis, *oass the end of it that faces the corner */
/* task avpaint: *stage (may be NULL) = the furthest check either inner-bend choice passed, AVL_CSTAGE */
static const char *AVL_CSTAGE[8] = { "no 11203 inner bend in the end row", "the cells beside the inner bend are not 11204 halves",
    "the 11203 / 11204 states are not a corner", "the outer cell is neither a bend nor a fitting avlj piece",
    "a block cell is claimed or a foreign variant", "the other band's first row is not a band row",
    "corner + T: the T row beside the block is not a road crossing the other band", "corner + T: no avlt piece fits a cell" };

/* task avpaint, CORNER + T (owner save 2026-10-27, "Big One" (567..569, 31..32)): a plain road meeting the other band's
   first row right beside a corner block. The stock tiler puts a T 39 / X 43 on that row (the "T row") and, when the road
   is on the outer side, links the inner bend and the other band's half beside it through their shared edge (both
   become T 39: inner bend + that edge, half + that edge). The block is then 3 rows deep from the other band's side.
   One-way: the corner cells as usual (the outer bend avlu, the halves avls, an unlinked inner bend avlk), every linked
   cell and both T row cells an `avlt` box-cell piece found by its outline / modes per side (the AVX box-cell letters,
   avjunc_build.py: one 2 x 2 paved box with the inner band's half as an arm, the outer bend as an arm, the other band
   as an arm, the road as a two-way arm). The other band begins one row further out. Bands joined through it convert
   all or nothing, as through a corner. Off: SC3NETMOD_AVLCT=0 (then the block is refused, as before). */
typedef struct { WORD piece; char ol[4], md[4]; } AvlT;
#define AVL_MAXT 16
static AvlT g_avl_t[AVL_MAXT];
static int g_avl_nt, g_avl_ct = -1;
typedef struct { int n, link_in, link_m2; int x[4], z[4]; DWORD want[4]; BYTE mapv[4]; } AvlCT;

static int avl_ct_on(void) {
    if (g_avl_ct < 0) {
        g_avl_ct = !env_off("SC3NETMOD_AVLCT");
        logf("avl: corner + T %s (%d avlt piece(s))", g_avl_ct ? "on" : "off (SC3NETMOD_AVLCT=0)", g_avl_nt);
    }
    return g_avl_ct && g_avl_nt;
}

static int avl_is_t(WORD id) {
    int k;
    for (k = 0; id && k < g_avl_nt; k++) if (g_avl_t[k].piece == id) return 1;
    return 0;
}

static void avl_t_line(const char *path, const char *line) {
    unsigned long v;
    char o[8], m[8];
    int k;
    if (sscanf(line + 5, "%lu %4s %4s", &v, o, m) != 3 || !v || v > 0xffff || strlen(o) != 4 || strlen(m) != 4 ||
        !g_base[v] || g_avl_nt >= AVL_MAXT) {
        logf("### avl: %s: bad corner + T line (piece not a variant, or too many): '%s'", path, line);
        return;
    }
    for (k = 0; k < 4; k++)
        if (!strchr("IAC", o[k]) || !strchr("IOTC", m[k])) { logf("### avl: %s: bad letters: '%s'", path, line); return; }
    g_avl_t[g_avl_nt].piece = (WORD)v;
    memcpy(g_avl_t[g_avl_nt].ol, o, 4);
    memcpy(g_avl_t[g_avl_nt].md, m, 4);
    g_avl_nt++;
    logf("avl: %s: corner + T piece %lu on base %u, outline %.4s modes %.4s at state 0", path, v, g_base[v], o, m);
}

static int avl_arms(DWORD v) { return v ? avx_arms(v) : 0; }      /* N E S W bits, -1 unknown (sc3netmod_avx.c) */

/* the avlt piece (id << 8 | state) with outline `ol` and modes `md` (world sides N E S W) on cell value v, 0 none: same
   base as the cell, written at a state with the cell's own connections (the cell's state first) */
static DWORD avl_ct_find(DWORD v, const char *ol, const char *md) {
    WORD base = avx_stock_of(AVL_ID(v));
    int arms = base ? avx_stock_arms(base) : -1, cst = AVL_ST(v), k, i, w;
    if (arms < 0) return 0;
    for (k = 0; k < g_avl_nt; k++) {
        if (g_base[g_avl_t[k].piece] != base) continue;
        for (i = 0; i < 4; i++) {
            int st = (cst + i) & 3;
            if (avx_rotm(arms, st) != avx_rotm(arms, cst)) continue;
            for (w = 0; w < 4; w++)
                if (g_avl_t[k].ol[(w - st) & 3] != ol[w] || g_avl_t[k].md[(w - st) & 3] != md[w]) break;
            if (w == 4) return ((DWORD)g_avl_t[k].piece << 8) | (DWORD)st;
        }
    }
    return 0;
}

static int avl_ct_cell(AvlCT *ct, int x, int z, DWORD v, const char *ol, const char *md, BYTE mapv) {
    DWORD w = avl_ct_find(v, ol, md);
    if (!w || ct->n >= 4) return 0;
    ct->x[ct->n] = x; ct->z[ct->n] = z; ct->want[ct->n] = w; ct->mapv[ct->n] = mapv; ct->n++;
    return 1;
}

static int avl_corner_at(AvlPass *p, int axis, int ax, int az, int k, int end, int *oaxis, int *ox, int *oz, int *oass,
                         int *stage, AvlCT *ct) {
    int dx = axis ? 1 : 0, dz = axis ? 0 : 1, fwd = end > 0, ib;
    int x = ax + dx * k, z = az + dz * k, bx = x + (axis ? 0 : 1), bz = z + (axis ? 1 : 0);
    int x2 = x + dx * end, z2 = z + dz * end, bx2 = bx + dx * end, bz2 = bz + dz * end;
    DWORD a = avl_at(p, x, z), b = avl_at(p, bx, bz), a2 = avl_at(p, x2, z2), b2 = avl_at(p, bx2, bz2);
    int dummy = 0, cton = avl_ct_on();
    int sL = axis ? (fwd ? 1 : 3) : (fwd ? 2 : 0);                 /* from the end row to the next row */
    AvlCT ct0;
    if (!stage) stage = &dummy;
    if (!ct) ct = &ct0;
    *stage = 0;
    ct->n = ct->link_in = ct->link_m2 = 0;
    if (!a || !b || !a2 || !b2) return 0;
    for (ib = 0; ib < 2; ib++) {
        const signed char *S = AVL_CST[axis][fwd][ib];
        DWORD in = ib ? b : a, mid = ib ? a : b, mid2 = ib ? b2 : a2, out = ib ? a2 : b2;
        int ox2 = ib ? x2 : bx2, oz2 = ib ? z2 : bz2, mx = ib ? x : bx, mz = ib ? z : bz;
        int m2x = ib ? bx2 : x2, m2z = ib ? bz2 : z2, bend, k2, lin = 0, lm2 = 0;
        int sT = axis ? (ib ? 2 : 0) : (ib ? 1 : 3);               /* from the inner bend toward the other band */
        const int ST[4] = { AVL_ST(a), AVL_ST(b), AVL_ST(a2), AVL_ST(b2) };
        const int iin = ib ? 1 : 0, im2 = ib ? 3 : 2;
        if (!avl_is_bend(AVL_ID(in), g_avl_corner)) {              /* corner + T: a linked inner bend (39 / ours) */
            if (!cton || !(AVL_ID(in) == 39 || avl_is_t(AVL_ID(in))) ||
                avl_arms(in) != (avx_rotm(avx_stock_arms(11203), S[iin]) | (1 << sL))) continue;
            lin = 1;
        }
        if (*stage < 1) *stage = 1;
        if (!avl_is_straight(AVL_ID(mid))) continue;
        if (!avl_is_straight(AVL_ID(mid2))) {                      /* corner + T: a linked half */
            if (!cton || !(AVL_ID(mid2) == 39 || avl_is_t(AVL_ID(mid2))) ||
                avl_arms(mid2) != (avx_rotm(avx_stock_arms(11204), S[im2]) | (1 << ((sL + 2) & 3)))) continue;
            lm2 = 1;
        }
        if (*stage < 2) *stage = 2;
        bend = avl_is_bend(AVL_ID(out), g_avl_uturn);
        for (k2 = 0; k2 < 4; k2++)                                 /* a declared outer piece: its own state */
            if (ST[k2] != S[k2] && (bend || k2 != (ib ? 2 : 3)) && !(lin && k2 == iin) && !(lm2 && k2 == im2)) break;
        if (k2 < 4) continue;
        if (*stage < 3) *stage = 3;
        if (!bend && !avl_outer_join(p, out, ox2, oz2, mx, mz, m2x, m2z)) continue;
        if (*stage < 4) *stage = 4;
        if (!avl_free(p, x, z, a) || !avl_free(p, bx, bz, b) || !avl_free(p, x2, z2, a2) || !avl_free(p, bx2, bz2, b2)) {
            if (bend || !avl_free(p, ib ? bx : x, ib ? bz : z, in) || !avl_free(p, mx, mz, mid) ||
                !avl_free(p, m2x, m2z, mid2))
                return 0;                                          /* (a declared outer cell is not ours: not checked) */
        }
        *stage = 5;
        *oaxis = 1 - axis;
        if (axis == 0) { *ox = ib ? bx + 1 : x - 1; *oz = min(z, z2); *oass = ib ? -1 : 1; }   /* along x: W / E */
        else { *ox = min(x, x2); *oz = ib ? bz + 1 : z - 1; *oass = ib ? -1 : 1; }            /* along z: N / S */
        if (!lin && !lm2 && avl_row(p, *oaxis, *ox, *oz, 0)) return ib + 1;
        if (!cton) return 0;
        {   /* corner + T: the T row at (ox, oz), the other band one row further out */
            int ix = ib ? bx : x, iz = ib ? bz : z;                /* the inner bend */
            int tax = ix + AVL_D[sT][0], taz = iz + AVL_D[sT][1], tbx = m2x + AVL_D[sT][0], tbz = m2z + AVL_D[sT][1];
            DWORD ta = avl_at(p, tax, taz), tb = avl_at(p, tbx, tbz);
            int oT = (sT + 2) & 3, oL = (sL + 2) & 3, A, B, ra, rb, fin;
            char ol[4], md[4];
            *stage = 6;
            if (!ta || !tb || !avl_free(p, tax, taz, ta) || !avl_free(p, tbx, tbz, tb)) return 0;
            if (!(AVL_ID(ta) == 39 || AVL_ID(ta) == 43 || avl_is_t(AVL_ID(ta))) ||
                !(AVL_ID(tb) == 39 || AVL_ID(tb) == 43 || avl_is_t(AVL_ID(tb)))) return 0;
            A = avl_arms(ta); B = avl_arms(tb);
            if (A < 0 || B < 0) return 0;
            ra = (A >> oL) & 1; rb = (B >> sL) & 1;                /* a road on the outside of each */
            if ((A & ~(1 << oL)) != ((1 << oT) | (1 << sT) | (1 << sL))) return 0;
            if ((B & ~(1 << sL)) != ((1 << oT) | (1 << sT) | (1 << oL))) return 0;
            if (!ra && !rb) return 0;
            if (ra && !(avl_arms(avl_at(p, tax + AVL_D[oL][0], taz + AVL_D[oL][1])) > 0 &&
                        (avl_arms(avl_at(p, tax + AVL_D[oL][0], taz + AVL_D[oL][1])) & (1 << sL)))) return 0;
            if (rb && !(avl_arms(avl_at(p, tbx + AVL_D[sL][0], tbz + AVL_D[sL][1])) > 0 &&
                        (avl_arms(avl_at(p, tbx + AVL_D[sL][0], tbz + AVL_D[sL][1])) & (1 << oL)))) return 0;
            if (axis == 0) *ox += ib ? 1 : -1; else *oz += ib ? 1 : -1;
            if (!avl_row(p, *oaxis, *ox, *oz, 0)) { *stage = 5; return 0; }
            *stage = 7;
            /* flow: the band's half at the inner bend runs into the block when the other half (mid) runs away from it */
            fin = ((S[ib ? 0 : 1] + 3) & 3) == oL;
            ct->link_in = lin; ct->link_m2 = lm2;
            if (lin) {
                memset(ol, 'C', 4); memset(md, 'C', 4);
                ol[oL] = 'A'; md[oL] = fin ? 'I' : 'O';
                ol[sT] = 'I'; md[sT] = fin ? 'O' : 'I';
                ol[sL] = 'I';
                if (!avl_ct_cell(ct, ix, iz, in, ol, md, 0xff)) return 0;
            }
            if (lm2) {
                memset(ol, 'C', 4); memset(md, 'C', 4);
                ol[sT] = 'I'; md[sT] = fin ? 'I' : 'O';
                ol[oT] = 'A'; md[oT] = fin ? 'O' : 'I';
                ol[oL] = 'I';
                if (!avl_ct_cell(ct, m2x, m2z, mid2, ol, md, (BYTE)(1 + (fin ? oT : sT)))) return 0;
            }
            memset(ol, 'C', 4); memset(md, 'C', 4);                /* T row cell beside the inner bend */
            ol[oT] = lin ? 'I' : 'A'; md[oT] = fin ? 'I' : 'O';
            ol[sT] = 'A'; md[sT] = fin ? 'O' : 'I';
            ol[sL] = 'I'; md[sL] = 'T';
            if (ra) { ol[oL] = 'A'; md[oL] = 'T'; }
            if (!avl_ct_cell(ct, tax, taz, ta, ol, md, 0xff)) return 0;
            memset(ol, 'C', 4); memset(md, 'C', 4);                /* T row cell beside the other half */
            ol[oT] = lm2 ? 'I' : 'A'; md[oT] = fin ? 'O' : 'I';
            ol[sT] = 'A'; md[sT] = fin ? 'I' : 'O';
            ol[oL] = 'I'; md[oL] = 'T';
            if (rb) { ol[sL] = 'A'; md[sL] = 'T'; }
            if (!avl_ct_cell(ct, tbx, tbz, tb, ol, md, 0xff)) return 0;
            return ib + 1;
        }
    }
    return 0;
}

static int avl_on_stack(AvlStack *stk, int axis, int x, int z) {
    int i;
    for (i = 0; i < stk->n; i++) {
        AvlSeed *s = &stk->s[i];
        if (s->axis != axis) continue;
        if (axis == 0 ? (x == s->x && z >= s->z && z < s->z + s->n) : (z == s->z && x >= s->x && x < s->x + s->n)) return 1;
    }
    return 0;
}

/* task avpaint: is the row at offset k (past the run, toward `end`) the T row of a corner + T whose corner band is the
   other axis? -> 1 with that band's first-half cell (*sx, *sz) and its end facing the corner (*se) */
static int avl_ct_side(AvlPass *p, int axis, int ax, int az, int k, int end, int *sx, int *sz, int *se) {
    int dx = axis ? 1 : 0, dz = axis ? 0 : 1, c;
    if (!avl_ct_on()) return 0;
    for (c = 0; c < 2; c++) {
        int ax1, az1, k1 = c ? -1 : 1, e1 = c ? -1 : 1, oa, ox, oz, os;
        AvlCT ct;
        if (axis == 1) { ax1 = min(ax + dx * (k + end), ax + dx * (k + 2 * end)); az1 = c ? az + 2 : az - 1; }
        else { az1 = min(az + dz * (k + end), az + dz * (k + 2 * end)); ax1 = c ? ax + 2 : ax - 1; }
        if (!avl_row(p, 1 - axis, ax1, az1, 0)) continue;
        if (!avl_corner_at(p, 1 - axis, ax1, az1, k1, e1, &oa, &ox, &oz, &os, NULL, &ct) || !ct.n) continue;
        if (oa != axis || ox != ax + dx * (k - end) || oz != az + dz * (k - end)) continue;
        *sx = ax1; *sz = az1; *se = e1;
        return 1;
    }
    return 0;
}

/* the row past the run at offset k (end = -1 the back end, +1 the forward end): acceptable? *u = 1 U-turn, 2 / 3 a
   corner (inner bend on A / B). assume == end: the caller's end, accepted whatever stands on it (avl_band_ok, and the
   band beyond a corner, which is being decided by the caller) */
static int avl_end(AvlPass *p, int axis, int ax, int az, int k, int end, int *u, int assume, AvlStack *stk) {
    static const int USTATE[2][2][2] = { { { 3, 0 }, { 2, 1 } }, { { 3, 2 }, { 0, 1 } } };   /* [axis][fwd][A/B] */
    int dx = axis ? 1 : 0, dz = axis ? 0 : 1;
    int x = ax + dx * k, z = az + dz * k, bx = x + (axis ? 0 : 1), bz = z + (axis ? 1 : 0);
    int fwd = end > 0, da = axis ? 1 : 0, db = axis ? 3 : 2;     /* travel: along z A runs N, B runs S; along x A E, B W */
    int face = axis ? (fwd ? 3 : 1) : (fwd ? 0 : 2);             /* the end piece's side facing the band */
    int toward = axis ? (fwd ? 1 : 3) : (fwd ? 2 : 0);           /* travel side that points into this end */
    int c, oaxis, ox, oz, oass, hw, cst = 0;
    AvlCT ct;
    DWORD a, b;
    char la, lb;
    const char *en = fwd ? "forward" : "back";
    *u = 0;
    if (x < 0 || z < 0 || bx < 0 || bz < 0 || x >= p->W || z >= p->H || bx >= p->W || bz >= p->H) return 1;   /* map edge */
    a = avl_at(p, x, z); b = avl_at(p, bx, bz);
    if (!a && !b) {
        avl_why(stk, "band along %s at (%d,%d): %s end (%d,%d)/(%d,%d) has no road (a dead end, not a U-turn pair)",
                axis ? "x" : "z", ax, az, en, x, z, bx, bz);
        return 0;
    }
    if (assume && assume == end) return 1;
    if ((AVL_ID(a) == 11203 || (g_avl_uturn && AVL_ID(a) == g_avl_uturn)) &&
        (AVL_ID(b) == 11203 || (g_avl_uturn && AVL_ID(b) == g_avl_uturn)) &&
        AVL_ST(a) == USTATE[axis][fwd][0] && AVL_ST(b) == USTATE[axis][fwd][1] &&
        avl_free(p, x, z, a) && avl_free(p, bx, bz, b)) {
        *u = g_avl_uturn != 0;
        if (!g_avl_uturn) avl_why(stk, "band along %s at (%d,%d): %s end is a U-turn pair but no avlu piece is loaded",
                                  axis ? "x" : "z", ax, az, en);
        return g_avl_uturn != 0;
    }
    if (g_avl_corner && g_avl_uturn && (c = avl_corner_at(p, axis, ax, az, k, end, &oaxis, &ox, &oz, &oass, &cst, &ct))) {
        int k0, k1, ub, uf;
        *u = ct.n ? 4 + c : 1 + c;                               /* 2 / 3 corner, 5 / 6 corner + T */
        if (avl_on_stack(stk, oaxis, ox, oz)) return 1;          /* a loop of bands: that band is being decided above */
        if (stk->n >= AVL_DEPTH) {
            avl_why(stk, "band along %s at (%d,%d): %s end corner chain deeper than %d bands", axis ? "x" : "z", ax, az,
                    en, AVL_DEPTH);
            return 0;
        }
        return avl_decide_r(p, oaxis, ox, oz, &k0, &k1, &ub, &uf, oass, stk);   /* (its own reason if refused) */
    }
    if (g_avl_corner && g_avl_uturn && avl_ct_side(p, axis, ax, az, k, end, &ox, &oz, &oass)) {
        int k0, k1, ub, uf;                                       /* task avpaint: the T row of a corner + T */
        *u = 7;
        if (avl_on_stack(stk, 1 - axis, ox, oz)) return 1;
        if (stk->n >= AVL_DEPTH) {
            avl_why(stk, "band along %s at (%d,%d): %s end corner chain deeper than %d bands", axis ? "x" : "z", ax, az,
                    en, AVL_DEPTH);
            return 0;
        }
        return avl_decide_r(p, 1 - axis, ox, oz, &k0, &k1, &ub, &uf, oass, stk);
    }
    /* task avx32 (owner img10): a highway transition's ground row (hwave: the one-way hwavs pair, or the two-way T2
       pair it holds while the avenue stays two-way) is read as the one-way pair (T2 exit -> hwavs exit, T2 entry ->
       hwavs entry, same state) and is the band's to choose (*u = 4): avl_band writes the hwavs pair when the band
       converts and the T2 pair when it does not, as hwave_build would. Else the box at an avenue's far end and the
       ground row each wait on the other (both ask avl_band_ok) and neither converts once one went back to two-way,
       and a band decided outside hwave's pass box keeps a ground row of the other kind */
    /* orchestrator 2026-10-21: only a transition hwave_check accepts (hwave_row_ok, the same conditions), so a
       transition hwave refuses leaves the band, and the box that asks about it, stock */
    hw = g_hwave_s[0] && g_hwave_p[2] && hwave_row_ok(p->mgr, x, z, a) && hwave_row_ok(p->mgr, bx, bz, b);
    if (hw) {
        if (AVL_ID(a) == g_hwave_p[2] || AVL_ID(a) == g_hwave_p[3])
            a = (a & ~0xffffUL) | g_hwave_s[AVL_ID(a) == g_hwave_p[2] ? 0 : 1];
        if (AVL_ID(b) == g_hwave_p[2] || AVL_ID(b) == g_hwave_p[3])
            b = (b & ~0xffffUL) | g_hwave_s[AVL_ID(b) == g_hwave_p[2] ? 0 : 1];
    }
    la = avl_letter(AVL_ID(a), AVL_ST(a), face);
    lb = avl_letter(AVL_ID(b), AVL_ST(b), face);
    if (!la || !lb) {
        avl_why(stk, "band along %s at (%d,%d): %s end (%d,%d) %u.%d%s + (%d,%d) %u.%d%s is not a U-turn pair, corner or "
                "avlj join (%s; corner check: %s)", axis ? "x" : "z", ax, az, en, x, z, AVL_ID(a), AVL_ST(a),
                avl_free(p, x, z, a) ? "" : " [claimed]", bx, bz, AVL_ID(b), AVL_ST(b), avl_free(p, bx, bz, b) ? "" : " [claimed]",
                !la && !lb ? "neither cell an avlj piece" : !la ? "first cell not an avlj piece" : "second cell not an avlj piece",
                AVL_CSTAGE[cst]);
        return 0;
    }
    if (la != (da == toward ? 'I' : 'O') || lb != (db == toward ? 'I' : 'O')) {
        avl_why(stk, "band along %s at (%d,%d): %s end join (%d,%d) %u.%d / (%d,%d) %u.%d letters %c%c on side %c, want %c%c",
                axis ? "x" : "z", ax, az, en, x, z, AVL_ID(a), AVL_ST(a), bx, bz, AVL_ID(b), AVL_ST(b), la, lb,
                AVL_SIDE[face], da == toward ? 'I' : 'O', db == toward ? 'I' : 'O');
        return 0;
    }
    if (hw) *u = 4;
    return 1;
}

typedef struct { int x, z; DWORD want; } AvlW;

/* the decision for the band through first-half cell (ax, az): rows k0..k1, end kinds ub / uf (avl_end's *u); nothing
   written. Through a corner the band beyond is decided too (recursively, its corner end assumed): all or nothing. */
static int avl_decide_r(AvlPass *p, int axis, int ax, int az, int *pk0, int *pk1, int *pub, int *puf, int assume,
                        AvlStack *stk) {
    int dx = axis ? 1 : 0, dz = axis ? 0 : 1, k0 = 0, k1 = 0, k, ok;
    while (k0 > -AVL_MAXLEN && avl_row(p, axis, ax, az, k0 - 1)) k0--;
    while (k1 < AVL_MAXLEN && avl_row(p, axis, ax, az, k1 + 1)) k1++;
    stk->s[stk->n].axis = axis; stk->s[stk->n].x = ax + dx * k0; stk->s[stk->n].z = az + dz * k0;
    stk->s[stk->n].n = k1 - k0 + 1;
    stk->n++;
    {   /* both ends always: a refused band must also give back its U-turn / corner cells */
        int okb = avl_end(p, axis, ax, az, k0 - 1, -1, pub, assume, stk);
        int okf = avl_end(p, axis, ax, az, k1 + 1, 1, puf, assume, stk);
        ok = okb && okf;
    }
    for (k = k0; ok && k <= k1; k++) {                             /* every crossing row needs a variant per direction */
        int c;
        for (c = 0; c < 2 && ok; c++) {
            int cx = ax + dx * k + (c && !axis ? 1 : 0), cz = az + dz * k + (c && axis ? 1 : 0);
            DWORD v = avl_at(p, cx, cz);
            int ci = avl_cross_of(AVL_ID(v)), dir = axis ? (c ? 3 : 1) : (c ? 2 : 0);
            if (!avl_is_straight(AVL_ID(v)) && (ci < 0 || !avl_cross_want(g_avl_c[ci].base, AVL_ST(v), dir))) {
                ok = 0;
                avl_why(stk, "band along %s at (%d,%d): row %d (%d,%d) holds %u.%d, no one-way variant toward %c",
                        axis ? "x" : "z", ax, az, k, cx, cz, AVL_ID(v), AVL_ST(v), AVL_SIDE[dir]);
            }
        }
    }
    stk->n--;
    *pk0 = k0; *pk1 = k1;
    return ok;
}

/* why (may be NULL, 320 bytes): the refusal reason (task avpaint) */
static int avl_decide(AvlPass *p, int axis, int ax, int az, int *pk0, int *pk1, int *pub, int *puf, int assume,
                      char *why) {
    AvlStack *stk = (AvlStack *)HeapAlloc(GetProcessHeap(), 0, sizeof(AvlStack));
    int ok;
    if (why) why[0] = 0;
    if (!stk) return 0;
    stk->n = 0; stk->why[0] = 0;
    ok = avl_decide_r(p, axis, ax, az, pk0, pk1, pub, puf, assume, stk);
    if (why && !ok) {
        memcpy(why, stk->why[0] ? stk->why : "(no reason recorded)", sizeof(stk->why));
        why[sizeof(stk->why) - 1] = 0;
    }
    HeapFree(GetProcessHeap(), 0, stk);
    return ok;
}

static void avl_band(AvlPass *p, int axis, int ax, int az, AvlW *w, int *nw, int cap, int *rv, int *nrv, int rcap,
                     const char *who);

/* one cell of an accepted band's write list, or (refused) of the revert list */
static void avl_cellw(AvlPass *p, int ok, int cx, int cz, DWORD want, int mapv, AvlW *w, int *nw, int cap, int *rv,
                      int *nrv, int rcap) {                      /* want = id << 8 | state; 0 = piece at the cell's state */
    DWORD v = avl_at(p, cx, cz);
    if (!v) return;
    if (ok) {
        if (*nw < cap) { w[*nw].x = cx; w[*nw].z = cz; w[*nw].want = want; (*nw)++; }
        if (g_avl_map && cx < g_avl_mw && cz < g_avl_mh) g_avl_map[cz * g_avl_mw + cx] = (BYTE)mapv;
    } else {
        if (avl_own(AVL_ID(v)) && *nrv < rcap) { rv[2 * *nrv] = cx; rv[2 * *nrv + 1] = cz; (*nrv)++; }
        if (g_avl_map && cx < g_avl_mw && cz < g_avl_mh) g_avl_map[cz * g_avl_mw + cx] = 0;
    }
}

static void avl_cell(AvlPass *p, int ok, int cx, int cz, WORD piece, int mapv, AvlW *w, int *nw, int cap, int *rv,
                     int *nrv, int rcap) {
    avl_cellw(p, ok, cx, cz, ((DWORD)piece << 8) | AVL_ST(avl_at(p, cx, cz)), mapv, w, nw, cap, rv, nrv, rcap);
}

/* one band from the seed (ax, az): walk, decide, collect writes (accepted) or reverts (refused); through a corner the
   band beyond is processed in the same run (it may lie outside the pass box) */
static void avl_band(AvlPass *p, int axis, int ax, int az, AvlW *w, int *nw, int cap, int *rv, int *nrv, int rcap,
                     const char *who) {
    int dx = axis ? 1 : 0, dz = axis ? 0 : 1, k0, k1, k, ub = 0, uf = 0, ok, e;
    int next[2][3], nnext = 0;
    char why[320];
    ok = avl_decide(p, axis, ax, az, &k0, &k1, &ub, &uf, 0, why);
    for (k = k0; k <= k1; k++) {                                  /* mark both cells of every row: one walk per band */
        int x = ax + dx * k, z = az + dz * k;
        p->seen[z * p->W + x] = 1;
        p->seen[(z + (axis ? 1 : 0)) * p->W + x + (axis ? 0 : 1)] = 1;
    }
    for (k = k0; k <= k1; k++) {                                  /* the rows */
        int x = ax + dx * k, z = az + dz * k, c;
        for (c = 0; c < 2; c++) {
            int cx = x + (c && !axis ? 1 : 0), cz = z + (c && axis ? 1 : 0), dir = axis ? (c ? 3 : 1) : (c ? 2 : 0);
            DWORD v = avl_at(p, cx, cz);
            WORD id = AVL_ID(v), piece;
            if (!v) continue;
            piece = avl_is_straight(id) ? g_avl_straight : ok ? avl_cross_want(g_avl_c[avl_cross_of(id)].base, AVL_ST(v), dir) : 0;
            avl_cell(p, ok, cx, cz, piece, 1 + dir, w, nw, cap, rv, nrv, rcap);
        }
    }
    for (e = 0; e < 2; e++) {                                     /* the ends that are ours: U-turn pair, corner block */
        int end = e ? 1 : -1, kind = e ? uf : ub, kk = e ? k1 + 1 : k0 - 1;
        int x = ax + dx * kk, z = az + dz * kk, bx = x + (axis ? 0 : 1), bz = z + (axis ? 1 : 0);
        if (kind == 1) {
            avl_cell(p, ok, x, z, g_avl_uturn, 0xff, w, nw, cap, rv, nrv, rcap);
            avl_cell(p, ok, bx, bz, g_avl_uturn, 0xff, w, nw, cap, rv, nrv, rcap);
        } else if (kind == 2 || kind == 3 || kind == 5 || kind == 6) {
            int ib = kind == 3 || kind == 6, x2 = x + dx * end, z2 = z + dz * end, bx2 = bx + dx * end, bz2 = bz + dz * end;
            int oaxis, ox, oz, oass, i, cok;
            AvlCT ct;
            /* inner bend, its partner half, the other half, the outer bend */
            int ix = ib ? bx : x, iz = ib ? bz : z, mx = ib ? x : bx, mz = ib ? z : bz;
            int m2x = ib ? bx2 : x2, m2z = ib ? bz2 : z2, ox2 = ib ? x2 : bx2, oz2 = ib ? z2 : bz2;
            cok = avl_corner_at(p, axis, ax, az, kk, end, &oaxis, &ox, &oz, &oass, NULL, &ct);
            if (!cok) ct.n = ct.link_in = ct.link_m2 = 0;
            if (!ct.link_in) avl_cell(p, ok, ix, iz, g_avl_corner, 0xff, w, nw, cap, rv, nrv, rcap);
            avl_cell(p, ok, mx, mz, g_avl_straight, 1 + ((AVL_ST(avl_at(p, mx, mz)) + 3) & 3), w, nw, cap, rv, nrv, rcap);
            if (!ct.link_m2)
                avl_cell(p, ok, m2x, m2z, g_avl_straight, 1 + ((AVL_ST(avl_at(p, m2x, m2z)) + 3) & 3), w, nw, cap, rv, nrv, rcap);
            if (avl_is_bend(AVL_ID(avl_at(p, ox2, oz2)), g_avl_uturn))  /* a declared avlj outer cell is not ours */
                avl_cell(p, ok, ox2, oz2, g_avl_uturn, 0xff, w, nw, cap, rv, nrv, rcap);
            for (i = 0; i < ct.n; i++)                             /* task avpaint: corner + T cells */
                avl_cellw(p, ok, ct.x[i], ct.z[i], ct.want[i], ct.mapv[i], w, nw, cap, rv, nrv, rcap);
            if (cok && !p->seen[oz * p->W + ox] && nnext < 2) {
                next[nnext][0] = oaxis; next[nnext][1] = ox; next[nnext][2] = oz; nnext++;
            }
        } else if (kind == 7) {                                    /* task avpaint: a corner + T's T row: the corner band */
            int sx, sz, se;                                        /* writes the block, in this run */
            if (avl_ct_side(p, axis, ax, az, kk, end, &sx, &sz, &se) && !p->seen[sz * p->W + sx] && nnext < 2) {
                next[nnext][0] = 1 - axis; next[nnext][1] = sx; next[nnext][2] = sz; nnext++;
            }
        } else if (kind == 4) {                                    /* task avx32: the ground row of a highway transition */
            int c;
            for (c = 0; c < 2; c++) {
                int cx = c ? bx : x, cz = c ? bz : z;
                DWORD v = avl_at(p, cx, cz);
                WORD id = AVL_ID(v), ex = id == g_hwave_s[0] || id == g_hwave_p[2];
                WORD want = ok ? g_hwave_s[ex ? 0 : 1] : g_hwave_p[ex ? 2 : 3];
                if (v && *nw < cap) { w[*nw].x = cx; w[*nw].z = cz; w[*nw].want = ((DWORD)want << 8) | AVL_ST(v); (*nw)++; }
            }
        }
    }
    if (ok) InterlockedIncrement(&g_avl_n_bands); else InterlockedIncrement(&g_avl_n_refused);
    if (ok && k1 - k0 + 1 >= 1) {
        static volatile LONG nlog;
        static const char *KIND[8] = { "join or edge", "U-turn", "corner", "corner", "highway ground row", "corner + T",
                                       "corner + T", "T row of a corner + T" };
        if (InterlockedIncrement(&nlog) <= 200 || strcmp(who, "load"))
            logf("avl: %s: band along %s from (%d,%d) rows %d..%d -> one-way (ends: %s / %s)", who, axis ? "x" : "z",
                 ax, az, k0, k1, KIND[ub & 7], KIND[uf & 7]);
    }
    if (!ok) {                                                    /* task avpaint: the refusal reason */
        static volatile LONG nlogr;
        if (InterlockedIncrement(&nlogr) <= 200 || strcmp(who, "load"))
            logf("avl: %s: band along %s from (%d,%d) rows %d..%d stays two-way: %s", who, axis ? "x" : "z", ax, az, k0,
                 k1, why);
    }
    for (e = 0; e < nnext; e++)                                   /* the band beyond each corner, same run */
        if (!p->seen[next[e][2] * p->W + next[e][1]])
            avl_band(p, next[e][0], next[e][1], next[e][2], w, nw, cap, rv, nrv, rcap, who);
}

/* AVENUE_LANES.md 5: would the avenue band through (x, z) (any cell of it, either half, stock or ours), running away from
   the caller toward world side `away` (0 N 1 E 2 S 3 W), convert if the end on the caller's side counted as a declared
   join? Evaluated on the current road grid with the pass rules; nothing written, no cache. 0 when AVL is off, when
   (x, z) is not a band cell, or when `away` does not run along the band. The same answer whatever stands at the
   caller's end. */
static int avl_band_ok(int x, int z, int away) {
    AvlPass P;
    BYTE *mgr = (BYTE *)g_rb_mgr;
    int k0, k1, ub = 0, uf = 0, ok = 0, t;
    static const int TRY[4][3] = { { 0, 0, 0 }, { 0, -1, 0 }, { 1, 0, 0 }, { 1, 0, -1 } };   /* axis, dx, dz */
    if (!g_avl_on || !mgr || away < 0 || away > 3) return 0;
    P.mgr = mgr; P.lay = *(void **)(mgr + 0x3c);
    P.W = (*(int *)(mgr + 0x5c) >> 8) + 1; P.H = (*(int *)(mgr + 0x60) >> 8) + 1;
    P.c = NULL; P.rd = NULL; P.seen = NULL;
    if (!avl_at(&P, x, z)) return 0;
    for (t = 0; t < 4; t++) {                                      /* the cell as either half of either axis */
        int axis = TRY[t][0], ax = x + TRY[t][1], az = z + TRY[t][2];
        if (!avl_row(&P, axis, ax, az, 0)) continue;
        /* along z the forward step is S (2), along x it is E (1); away from the caller = toward that end */
        if (axis == 0 && away != 0 && away != 2) return 0;
        if (axis == 1 && away != 1 && away != 3) return 0;
        ok = avl_decide(&P, axis, ax, az, &k0, &k1, &ub, &uf, (away == (axis ? 1 : 2)) ? -1 : 1, NULL);
        break;
    }
    return ok;
}

/* AVENUE_LANES.md 5, for the stream that declares corner outer pieces (avjunc): would the corner group through the
   OUTER cell (x, z) of a stock corner block convert if that cell held a fitting avlj piece? Evaluated on the current
   grid with the pass rules, whatever stands on (x, z) now (stock T 39 / X 43, or the declared piece); nothing written,
   no cache. 0 when AVL is off or (x, z) is not the outer cell of a corner block next to a band. */
static int avl_corner_ok(int x, int z) {
    AvlPass P;
    BYTE *mgr = (BYTE *)g_rb_mgr;
    int dx, dz, axis, ok = 0;
    if (!g_avl_on || !g_avl_corner || !mgr) return 0;
    P.mgr = mgr; P.lay = *(void **)(mgr + 0x3c);
    P.W = (*(int *)(mgr + 0x5c) >> 8) + 1; P.H = (*(int *)(mgr + 0x60) >> 8) + 1;
    P.c = NULL; P.rd = NULL; P.seen = NULL;
    g_avl_oas_x = x; g_avl_oas_z = z;
    for (axis = 0; axis < 2 && !ok; axis++)                        /* a band row 2 or 3 cells away along its axis */
        for (dz = -3; dz <= 3 && !ok; dz++)
            for (dx = -3; dx <= 3 && !ok; dx++) {
                int k0, k1, ub = 0, uf = 0, r;
                if (!avl_row(&P, axis, x + dx, z + dz, 0)) continue;
                g_avl_oas_hit = 0;
                r = avl_decide(&P, axis, x + dx, z + dz, &k0, &k1, &ub, &uf, 0, NULL);
                if (g_avl_oas_hit) ok = r;
            }
    g_avl_oas_x = g_avl_oas_z = -1;
    return ok;
}

/* post-AVL phase (AVENUE_LANES.md 5), fixed slots:
     AVL_POST_DAV  avdiag's diagonal put-back: runs after every avl_run of the pass; may ask for a re-run
     AVL_POST_BV   bvlanes (if it needs one): same
     AVL_POST_AVX  avjunc's avx_post: runs ONCE, after the last avl_run, on avl's final band map; returns 0
   A hook asking for a re-run returns 1 with rbox = x0 z0 x1 z1: avl_run then re-decides the union of the asked boxes
   and the re-run hooks run again, at most AVL_ROUNDS times per pass (program rule: all-or-nothing per connected group).
   A sibling sets its slot once with avl_post_set(slot, fn), e.g. from its table-line handler. */
typedef int (*AvlPostFn)(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who, int *rbox);
enum { AVL_POST_DAV, AVL_POST_BV, AVL_POST_AVX, AVL_NPOST };
#define AVL_ROUNDS 4
static AvlPostFn g_avl_post[AVL_NPOST];

static int avl_post_set(int slot, AvlPostFn f) {
    if (slot < 0 || slot >= AVL_NPOST) return 0;
    g_avl_post[slot] = f;
    return 1;
}

static void avl_run(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who);
static void avp_run(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who);   /* task avpaint (sc3netmod_avp.c) */
static void avp_stats(void);

/* what rb_pass / rb_load_pass call: avl_run, then the post hooks, re-runs as they ask */
static void avl_pass(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who) {
    int round, k, want, rb[4], u[4] = { 0, 0, 0, 0 };
    avl_run(mgr, x0, z0, x1, z1, who);
    for (round = 0; round <= AVL_ROUNDS; round++) {
        want = 0;
        for (k = 0; k < AVL_POST_AVX; k++) {                       /* the re-run hooks */
            if (!g_avl_post[k]) continue;
            rb[0] = rb[1] = 0x7fffffff; rb[2] = rb[3] = -1;
            if (g_avl_post[k](mgr, x0, z0, x1, z1, who, rb) && rb[2] >= rb[0] && rb[3] >= rb[1]) {
                if (!want) { u[0] = rb[0]; u[1] = rb[1]; u[2] = rb[2]; u[3] = rb[3]; }
                else { u[0] = min(u[0], rb[0]); u[1] = min(u[1], rb[1]); u[2] = max(u[2], rb[2]); u[3] = max(u[3], rb[3]); }
                want = 1;
            }
        }
        if (!want) break;
        if (round == AVL_ROUNDS) { logf("### avl: %s: post hooks still asking after %d re-runs - stopped", who, AVL_ROUNDS); break; }
        avl_run(mgr, u[0], u[1], u[2], u[3], who);
    }
    if (g_avl_post[AVL_POST_AVX]) {                                /* last, on the final band map */
        rb[0] = rb[1] = 0x7fffffff; rb[2] = rb[3] = -1;
        g_avl_post[AVL_POST_AVX](mgr, x0, z0, x1, z1, who, rb);
    }
    avp_run(mgr, x0, z0, x1, z1, who);                             /* task avpaint: last, on AVL's final band map */
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
    for (k = 0; k < nrv; k++) {                                   /* back to the base at the same state: what stock had */
        DWORD v = avl_at(&P, rv[2 * k], rv[2 * k + 1]);           /* (a rect retile keeps a Protected base, e.g. 69) */
        int pos[3];
        if (!v || !avl_own(AVL_ID(v))) continue;
        pos[0] = rv[2 * k] << 8; pos[1] = rv[2 * k + 1] << 8; pos[2] = 0;
        ((PFN_Put)(g_rb_m + 0x8919))(mgr, 0, P.lay, pos, ((DWORD)g_base[AVL_ID(v)] << 8) | AVL_ST(v), -1, 8, 0);
    }
    if (nrv) ZeroMemory(P.rd, (SIZE_T)P.W * P.H);                 /* a retile may have changed neighbours: read again */
    for (k = 0; k < nw; k++) {
        DWORD cur = avl_at(&P, w[k].x, w[k].z);
        int pos[3];
        if (((DWORD)AVL_ID(cur) << 8 | AVL_ST(cur)) == w[k].want && !(cur & HWLT_LIT)) continue;
        pos[0] = w[k].x << 8; pos[1] = w[k].z << 8; pos[2] = 0;
        ((PFN_Put)(g_rb_m + 0x8919))(mgr, 0, P.lay, pos, hwlt_want(w[k].want), -1, 8, 0);   /* task hwlight */
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
    avp_stats();                                                   /* task avpaint */
    LONG n = g_avl_n_bands + g_avl_n_refused + g_avl_n_cells + g_avl_n_rev;
    if (!g_avl_on || n == last) return;
    last = n;
    logf("stats: avl bands converted=%ld, refused=%ld, cells written=%ld, reverted=%ld", g_avl_n_bands, g_avl_n_refused,
         g_avl_n_cells, g_avl_n_rev);
}
