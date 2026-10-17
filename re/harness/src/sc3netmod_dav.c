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
 * Ends of a band (2026-10-17):
 *  merge     one staircase's two cells go on alone for two rows: its next DAV_MERGE_ROWS rows join the band, the row
 *            after is path (in the masks, not written), and the `davm` case table puts the taper pieces in
 *  bend      the band goes on as two parallel straight roads (stock avenue 11204), along x or along z: the straight
 *            cells are path, two virtual rows of both staircases past the end make the end cells middle-of-band
 *            pieces. The carriageways' edges meet the straight avenue's on one cell line, so no new art is needed.
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
    /* b == 0: the OUTER piece (a = 35, delta 0), placed on a one-road 35 cell with the other road beside it */
    if (sscanf(line + 4, "%lu %lu %lu %lu", &v, &a, &b, &d) != 4 || !v || v > 0xffff || d > 3 ||
        (a != 35 && a != 18004 && a != 1999) || (b != 0 && b != 35 && b != 18004 && b != 1999) ||
        (b == 0 && (a != 35 || d != 0)) || g_base[v] != (WORD)a) {
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

static int dav_is_junc(WORD id);
static int dav_is_mrg(WORD id);
static int dav_is_s43(WORD id);

static int dav_is_mid(WORD id) {                 /* any avenue piece: middle, outer, junction or merge */
    int k;
    for (k = 0; k < g_dav_nmid; k++) if (g_dav_mid[k].piece == id) return 1;
    return dav_is_junc(id) || dav_is_mrg(id);
}

/* save as 43: a cell holding both roads (stock 35 draws one); the OUTER piece (b == 0) saves as its base 35; merge
   pieces as their `davs` lines say */
static int dav_save_43(WORD id) {
    int k;
    for (k = 0; k < g_dav_nmid; k++) if (g_dav_mid[k].piece == id) return g_dav_mid[k].b != 0;
    return dav_is_s43(id);
}

static WORD dav_mid_of(WORD a, WORD b, int delta) {
    int k;
    for (k = 0; k < g_dav_nmid; k++)
        if (g_dav_mid[k].a == a && g_dav_mid[k].b == b && g_dav_mid[k].delta == delta) return g_dav_mid[k].piece;
    return 0;
}

/* road test in axis space: axis 1 mirrors x */
static int dav_road(RbBuf *b, int axis, int x, int z) { return rb_at(b, axis ? -x : x, z) != 0; }

static int dav_full(RbBuf *b, int axis, int a, int z) {
    return dav_road(b, axis, a, z) && dav_road(b, axis, a + 1, z) && dav_road(b, axis, a + 2, z);
}

static int dav_clean(RbBuf *b, int axis, int a, int z) {
    return !dav_road(b, axis, a - 1, z) && !dav_road(b, axis, a + 3, z);
}

/* junction pieces: `davj <piece> <n> <s1> <s2> <road> <far>` = the piece at state 0 draws road 29 in orientation
   <road> (0 along x, 1 along z) with the avenue's 35 halves at states s1 (and s2 when n == 2) over it as asphalt, and
   keeps its far curb <far> (0 N, 1 E, 2 S, 3 W; 255 none) for a stem. */
#define DAV_MAX_JUNC 32
typedef struct { WORD piece; BYTE n, s1, s2, o, e; } DavJunc;
static DavJunc g_dav_junc[DAV_MAX_JUNC];
static int g_dav_njunc;

static void dav_jline(const char *path, const char *line) {
    unsigned long v, n, s1, s2, o, e;
    if (sscanf(line + 5, "%lu %lu %lu %lu %lu %lu", &v, &n, &s1, &s2, &o, &e) != 6 || !v || v > 0xffff || n < 1 ||
        n > 2 || s1 > 3 || (n == 2 && s2 > 3) || o > 1 || (e > 3 && e != 255) || !g_base[v]) {
        logf("### dav: %s: bad junction line or piece not a variant: '%s'", path, line);
        return;
    }
    if (g_dav_njunc >= DAV_MAX_JUNC) { logf("### dav: %s: too many junction pieces - ignored", path); return; }
    if (n == 2 && s2 < s1) { unsigned long t = s1; s1 = s2; s2 = t; }
    g_dav_junc[g_dav_njunc].piece = (WORD)v; g_dav_junc[g_dav_njunc].n = (BYTE)n;
    g_dav_junc[g_dav_njunc].s1 = (BYTE)s1; g_dav_junc[g_dav_njunc].s2 = (BYTE)(n == 2 ? s2 : 0);
    g_dav_junc[g_dav_njunc].o = (BYTE)o; g_dav_junc[g_dav_njunc].e = (BYTE)e;
    g_dav_njunc++;
    logf("dav: %s: junction piece %lu = road %lu + 35 at %lu%s%lu, far curb %lu", path, v, o, s1, n == 2 ? "," : " ",
         n == 2 ? s2 : 0UL, e);
}

static int dav_is_junc(WORD id) {
    int k;
    for (k = 0; k < g_dav_njunc; k++) if (g_dav_junc[k].piece == id) return 1;
    return 0;
}

/* a cell's junction descriptor -> (piece << 8 | state), 0 = none declared. The table holds each piece's state-0
   descriptor; turning it by k states (35 states + k, road + k mod 2, far curb + k) gives state k. Smallest k first. */
static DWORD dav_junc_of(int n, int s1, int s2, int o, int e) {
    int k, j;
    for (k = 0; k < 4; k++) {
        int r = (4 - k) % 4, a = (s1 + r) % 4, b = (s2 + r) % 4, oo = (o + r) % 2, ee = e == 255 ? 255 : (e + r) % 4;
        if (n == 2 && b < a) { int t = a; a = b; b = t; }
        for (j = 0; j < g_dav_njunc; j++) {
            DavJunc *q = &g_dav_junc[j];
            if (q->n == n && q->s1 == a && (n == 1 || q->s2 == b) && q->o == oo && q->e == ee)
                return ((DWORD)q->piece << 8) | (DWORD)k;
        }
    }
    return 0;
}

/* merges: one carriageway ends and the other goes on as a single road. `davm <axis> <end> <cont> <dx> <dz> <piece>
   <state>` = in that case (end 0: the band's last row going on down, 1: its first row going on up; cont 1 A / 2 B, the
   staircase that goes on) the cell (dx, dz) from the end row's left cell, in axis space, gets the piece at the state.
   `davs <piece>`: the piece saves as 43 (it holds both roads, stock 35 would draw one). */
#define DAV_MERGE_ROWS 3                              /* single-road rows past the end row that the avenue writes */
#define DAV_MAX_MRG 64
#define DAV_MAX_S43 32
typedef struct { BYTE axis, end, cont; signed char dx, dz; WORD piece; BYTE state; } DavMrg;
static DavMrg g_dav_mrg[DAV_MAX_MRG];
static int g_dav_nmrg;
static WORD g_dav_s43[DAV_MAX_S43];
static int g_dav_ns43;

static void dav_mline(const char *path, const char *line) {
    unsigned long ax, end, cont, v, st;
    long dx, dz;
    if (sscanf(line + 5, "%lu %lu %lu %ld %ld %lu %lu", &ax, &end, &cont, &dx, &dz, &v, &st) != 7 || ax > 1 || end > 1 ||
        cont < 1 || cont > 2 || dx < -4 || dx > 4 || dz < -4 || dz > 4 || !v || v > 0xffff || st > 3 || !g_base[v]) {
        logf("### dav: %s: bad merge line or piece not a variant: '%s'", path, line);
        return;
    }
    if (g_dav_nmrg >= DAV_MAX_MRG) { logf("### dav: %s: too many merge cells - ignored", path); return; }
    g_dav_mrg[g_dav_nmrg].axis = (BYTE)ax; g_dav_mrg[g_dav_nmrg].end = (BYTE)end; g_dav_mrg[g_dav_nmrg].cont = (BYTE)cont;
    g_dav_mrg[g_dav_nmrg].dx = (signed char)dx; g_dav_mrg[g_dav_nmrg].dz = (signed char)dz;
    g_dav_mrg[g_dav_nmrg].piece = (WORD)v; g_dav_mrg[g_dav_nmrg].state = (BYTE)st;
    g_dav_nmrg++;
}

static void dav_sline(const char *path, const char *line) {
    unsigned long v;
    if (sscanf(line + 5, "%lu", &v) != 1 || !v || v > 0xffff || !g_base[v]) {
        logf("### dav: %s: bad save line or piece not a variant: '%s'", path, line);
        return;
    }
    if (g_dav_ns43 < DAV_MAX_S43) g_dav_s43[g_dav_ns43++] = (WORD)v;
}

static int dav_is_mrg(WORD id) {
    int k;
    for (k = 0; k < g_dav_nmrg; k++) if (g_dav_mrg[k].piece == id) return 1;
    return 0;
}

static int dav_is_s43(WORD id) {
    int k;
    for (k = 0; k < g_dav_ns43; k++) if (g_dav_s43[k] == id) return 1;
    return 0;
}

typedef struct { int x, z; BYTE pref; } DavCell;    /* x in real space; pref: ambiguous end cell, 1 = A, 2 = B */
typedef struct { int x, z; BYTE o; } DavArm;         /* a straight road cell beside the avenue -> 29 in state o */
typedef struct { int x, z; BYTE n, s1, s2, o, e; } DavJ;   /* a junction cell and its descriptor */

#define DAV_MAX_ARMS 256
#define DAV_MAX_COLS 64

typedef struct {                                      /* one pass: the read buffer and per-band scratch */
    RbBuf b;
    BYTE *mark;                         /* [cell]: 1 A, 2 B, 4 band, 8 arm, 16 junction, 32 path, 64 merge */
    DavCell *cell;
    DWORD *want;
    DavArm *arm;
    DavJ *junc;
} DavPass;

static int dav_mark(DavPass *p, int x, int z) {
    x -= p->b.x0; z -= p->b.z0;
    if (x < 0 || z < 0 || x >= p->b.w || z >= p->b.h) return 0;
    return p->mark[z * p->b.w + x];
}

static BYTE *dav_markp(DavPass *p, int x, int z) {
    static BYTE dummy;
    x -= p->b.x0; z -= p->b.z0;
    if (x < 0 || z < 0 || x >= p->b.w || z >= p->b.h) { dummy = 0; return &dummy; }
    return &p->mark[z * p->b.w + x];
}

/* add a band cell; st: 1 A, 2 B, 3 both, 0 ambiguous (pref 1 / 2) */
static void dav_add(DavPass *p, int *n, int axis, int ax, int z, int st, int pref) {
    int x = axis ? -ax : ax;
    BYTE *m = dav_markp(p, x, z);
    if (*n >= DAV_MAX_CELLS || (*m & 4)) return;
    p->cell[*n].x = x; p->cell[*n].z = z; p->cell[*n].pref = (BYTE)(st ? 0 : pref);
    *m = (BYTE)((*m & 8) | 4 | st);
    (*n)++;
}

static void dav_add_arm(DavPass *p, int *na, int axis, int ax, int z, int o) {
    int x = axis ? -ax : ax;
    BYTE *m = dav_markp(p, x, z);
    if (*na >= DAV_MAX_ARMS || (*m & 8)) return;
    p->arm[*na].x = x; p->arm[*na].z = z; p->arm[*na].o = (BYTE)o;
    *m |= 8;
    (*na)++;
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

/* 35's state in each band position, staircase A at d 0 / 1 and B at d 1 / 2 (diagave.py AXIS_STATES) */
static const BYTE DAV_AX_ST[2][4] = { { 2, 0, 2, 0 }, { 1, 3, 1, 3 } };     /* A0, A1, B1, B2 */

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
    mem = (BYTE *)VirtualAlloc(NULL, nbuf * 5 + DAV_MAX_CELLS * (sizeof(DavCell) + 4 + sizeof(DavJ)) +
                               DAV_MAX_ARMS * sizeof(DavArm), MEM_COMMIT, PAGE_READWRITE);
    if (!mem) return 0;
    P.b.c = (DWORD *)mem;
    P.cell = (DavCell *)(mem + nbuf * 4);
    P.want = (DWORD *)(P.cell + DAV_MAX_CELLS);
    P.junc = (DavJ *)(P.want + DAV_MAX_CELLS);
    P.arm = (DavArm *)(P.junc + DAV_MAX_CELLS);
    P.mark = (BYTE *)(P.arm + DAV_MAX_ARMS);
    for (z = 0; z < P.b.h; z++)
        for (x = 0; x < P.b.w; x++) P.b.c[z * P.b.w + x] = rb_read(mgr, lay, x0 + x, z0 + z, W, H);
    for (axis = 0; axis < 2; axis++) {
        int ax0 = axis ? -x1 : x0, ax1 = axis ? -x0 : x1;
#define RD(a, zq) dav_road(&P.b, axis, (a), (zq))
#define MK(a, zq) dav_mark(&P, axis ? -(a) : (a), (zq))
#define DOUT(a, zq) (RD(a, zq) && !(MK(a, zq) & 4))
        for (z = z0; z <= z1; z++)
            for (x = ax0; x <= ax1; x++) {
                int rows = 0, ok = 1, step, nw = 0, namb = 0, amb[DAV_MAX_AMB], combo, ncombo, best = -1, run, brun;
                int bestcost = 0x7fffffff, na = 0, nj = 0, ncn = 0, ncs = 0, colN[DAV_MAX_COLS][2], colS[DAV_MAX_COLS][2];
                int nmg = 0, mg[2][4], npath = 0, path[16][2], nmc = 0, mcx[16], mcz[16], bend[2], e;
                DWORD mcw[16];
                BYTE side[1024];
                const char *why = "";
                if (!dav_full(&P.b, axis, x, z) || dav_full(&P.b, axis, x - 1, z - 1)) continue;
                while (dav_full(&P.b, axis, x + rows, z + rows)) rows++;
                for (k = 0, run = brun = 0; k < rows; k++)        /* anchored by MIN_ROWS clean rows (no road beside) */
                    brun += dav_clean(&P.b, axis, x + k, z + k);
                if (brun < DAV_MIN_ROWS || rows > 1024) continue;
                /* bends: the avenue goes on as two parallel straight roads (stock avenue 11204). (u, v) = cell u right of
                   the end row's left cell, v rows past it (the top end turned half a circle: u -> 2 - u, v up). 1: along
                   x, rows v -1 and 0 go on past their d2; 2: along z, columns u 1 and 2 go on below. The carriageways'
                   edges meet the straight ones on one cell line, so the diagonal cells keep their middle-of-band pieces
                   and the straight cells stay stock. */
#define BX(u) (e ? x + rows - 1 + (u) : x + 2 - (u))
#define BZ(v) (e ? z + rows - 1 + (v) : z - (v))
                for (e = 0; e < 2; e++) {
                    bend[e] = 0;
                    if (rows >= 3 && RD(BX(3), BZ(0)) && RD(BX(2), BZ(-1)) && RD(BX(3), BZ(-1)) && !RD(BX(1), BZ(1)) &&
                        !RD(BX(2), BZ(1)) && !RD(BX(3), BZ(1)))
                        bend[e] = 1;
                    else if (RD(BX(1), BZ(1)) && RD(BX(2), BZ(1)) && RD(BX(1), BZ(2)) && RD(BX(2), BZ(2)) &&
                             !RD(BX(0), BZ(1)) && !RD(BX(3), BZ(1)))
                        bend[e] = 2;
                }
                n = 0;
                for (k = 0; k < rows; k++) {                     /* along x: the straight cells of the last two rows */
                    int tb = k == 0 ? 0 : k == 1 ? 1 : 9, bb = k == rows - 1 ? 0 : k == rows - 2 ? 1 : 9;
                    if (!(bend[0] == 1 && tb <= 1))
                        dav_add(&P, &n, axis, x + k, z + k, 1, 0);
                    if (!(bend[0] == 1 && tb == 0) && !(bend[1] == 1 && bb == 0))
                        dav_add(&P, &n, axis, x + k + 1, z + k, 3, 0);
                    if (!(bend[1] == 1 && bb <= 1))
                        dav_add(&P, &n, axis, x + k + 2, z + k, 2, 0);
                }
                /* side cells: straight road arms along the row (W / E) or along a column (N / S) */
                for (k = 0; k < rows && ok; k++) {
                    int aa = x + k, zz = z + k;
                    side[k] = 0;
                    if (bend[0] == 1 && k <= 1 && RD(aa - 1, zz)) side[k] |= 4;     /* the straight avenue, not an arm */
                    else if (RD(aa - 1, zz)) {
                        if (RD(aa - 2, zz) && !DOUT(aa - 1, zz + 1) && !DOUT(aa - 2, zz + 1) && !DOUT(aa - 2, zz - 1)) {
                            side[k] |= 1;
                            dav_add_arm(&P, &na, axis, aa - 1, zz, 0); dav_add_arm(&P, &na, axis, aa - 2, zz, 0);
                        } else if (RD(aa - 1, zz + 1) && !DOUT(aa - 2, zz) && !DOUT(aa, zz + 1) && !DOUT(aa - 2, zz + 1) &&
                                   ncs < DAV_MAX_COLS) {
                            colS[ncs][0] = aa - 1; colS[ncs][1] = zz; ncs++;
                            dav_add_arm(&P, &na, axis, aa - 1, zz, 1); dav_add_arm(&P, &na, axis, aa - 1, zz + 1, 1);
                        } else { ok = 0; why = "road beside the avenue is not a straight arm"; }
                    }
                    if (bend[1] == 1 && k >= rows - 2 && RD(aa + 3, zz)) side[k] |= 4;
                    else if (ok && RD(aa + 3, zz)) {
                        if (RD(aa + 4, zz) && !DOUT(aa + 3, zz - 1) && !DOUT(aa + 4, zz + 1) && !DOUT(aa + 4, zz - 1)) {
                            side[k] |= 2;
                            dav_add_arm(&P, &na, axis, aa + 3, zz, 0); dav_add_arm(&P, &na, axis, aa + 4, zz, 0);
                        } else if (RD(aa + 3, zz - 1) && !DOUT(aa + 4, zz) && !DOUT(aa + 2, zz - 1) && !DOUT(aa + 4, zz - 1) &&
                                   ncn < DAV_MAX_COLS) {
                            colN[ncn][0] = aa + 3; colN[ncn][1] = zz; ncn++;
                            dav_add_arm(&P, &na, axis, aa + 3, zz, 1); dav_add_arm(&P, &na, axis, aa + 3, zz - 1, 1);
                        } else { ok = 0; why = "road beside the avenue is not a straight arm"; }
                    }
                }
                /* junction cells (axis-space d, then real descriptor) */
#define JADD(AX, ZQ, D, O, E) do { if (nj < DAV_MAX_CELLS) { int d_ = (D); \
                    P.junc[nj].x = axis ? -(AX) : (AX); P.junc[nj].z = (ZQ); P.junc[nj].o = (BYTE)(O); P.junc[nj].e = (BYTE)(E); \
                    if (d_ == 1) { P.junc[nj].n = 2; P.junc[nj].s1 = DAV_AX_ST[axis][1]; P.junc[nj].s2 = DAV_AX_ST[axis][2]; } \
                    else { P.junc[nj].n = 1; P.junc[nj].s1 = DAV_AX_ST[axis][d_ == 0 ? 0 : 3]; P.junc[nj].s2 = 0; } \
                    if (P.junc[nj].n == 2 && P.junc[nj].s2 < P.junc[nj].s1) { BYTE t_ = P.junc[nj].s1; \
                        P.junc[nj].s1 = P.junc[nj].s2; P.junc[nj].s2 = t_; } \
                    nj++; } } while (0)
                for (k = 0; k < rows && ok; k++) {
                    int aa = x + k, zz = z + k, e = 255;
                    if (!side[k]) continue;
                    if (side[k] == 3 && (k == 0 || k == rows - 1)) e = k == 0 ? 0 : 2;   /* stem: the far curb */
                    if (side[k] & 1) JADD(aa, zz, 0, 0, e);
                    if (side[k] == 3) JADD(aa + 1, zz, 1, 0, e);
                    if (side[k] & 2) JADD(aa + 2, zz, 2, 0, e);
                }
                for (k = 0; k < ncn && ok; k++) {                    /* a column enters at (x0, zz+1), its d2 cell */
                    int x0c = colN[k][0], zz = colN[k][1], cross = 0, t;
                    for (j = 0; j < ncs; j++) if (colS[j][0] == x0c && colS[j][1] == zz + 4) cross = 1;
                    for (t = 1; t <= (cross ? 3 : 1); t++) {
                        int zr = zz + t, kr = zr - z;
                        if (kr < 0 || kr >= rows) { ok = 0; why = "column road leaves the avenue's rows"; break; }
                        JADD(x0c, zr, x0c - (x + kr), 1, 255);
                    }
                }
                for (k = 0; k < ncs && ok; k++) {                    /* a column leaves from (x0, zz-1), its d0 cell */
                    int x0c = colS[k][0], zz = colS[k][1], crossed = 0, kr = zz - 1 - z;
                    for (j = 0; j < ncn; j++) if (colN[j][0] == x0c && colN[j][1] == zz - 4) crossed = 1;
                    if (crossed) continue;
                    if (kr < 0 || kr >= rows) { ok = 0; why = "column road leaves the avenue's rows"; break; }
                    JADD(x0c, zz - 1, 0, 1, 255);
                }
#undef JADD
                for (k = 0; k < nj; k++) *dav_markp(&P, P.junc[k].x, P.junc[k].z) |= 16;
                /* the drags' ends beyond the full rows; not past a junction row. A merge when only one staircase's two
                   cells go on for two rows: that staircase's next DAV_MERGE_ROWS rows join the band, the row after is
                   path (in its staircase's mask, not written: the stock tiler joins the single road on) */
                for (step = -1; step <= 1 && ok; step += 2) {
                    int zr = step < 0 ? z : z + rows - 1, ar = step < 0 ? x : x + rows - 1, pat[2] = { 0, 0 }, cont = 0;
                    e = step > 0;
                    if (bend[e]) {                       /* the straight cells: path; two virtual rows of both staircases */
                        int u, v;                        /* past the end hold the masks of a band that goes on */
                        for (v = -1; v <= 2; v++)
                            for (u = v; u <= v + 3; u++) {
                                int d = u - v, bits = 0, real = 0, cx = axis ? -BX(u) : BX(u), cz = BZ(v);
                                if (v >= 1 && d <= 2) bits = d == 0 ? 1 : d == 1 ? 3 : 2;
                                if (bend[e] == 1 && ((v == -1 && (u == 1 || u == 2)) || (v == 0 && (u == 1 || u == 2))))
                                    real = 1, bits = v == -1 ? (u == 1 ? 2 : 0) : (u == 1 ? 3 : 2);
                                if (bend[e] == 2 && v == 1 && (u == 1 || u == 2)) real = 1;
                                if (!e) bits = ((bits & 1) << 1) | ((bits & 2) >> 1);   /* turned: d 0 is B's side */
                                if ((!bits && !real) || npath >= 16) continue;
                                path[npath][0] = cx; path[npath][1] = cz; npath++;
                                *dav_markp(&P, cx, cz) |= (BYTE)((real ? 32 : 0) | bits);
                            }
                        continue;
                    }
                    if (side[step < 0 ? 0 : rows - 1] & 3) continue;
                    for (k = 1; k <= 2; k++)
                        for (j = 0; j < 3; j++) {
                            int axj = ar + step * k + j, zj = zr + step * k;
                            if (RD(axj, zj) && !(MK(axj, zj) & 8)) pat[k - 1] |= 1 << j;
                        }
                    if (pat[0] == 3 && pat[1] == 3) cont = 1;
                    if (pat[0] == 6 && pat[1] == 6) cont = 2;
                    if (cont && nmg < 2) {
                        mg[nmg][0] = step > 0 ? 0 : 1; mg[nmg][1] = cont; mg[nmg][2] = zr; mg[nmg][3] = ar; nmg++;
                        for (k = 1; k <= DAV_MERGE_ROWS + 1; k++)
                            for (j = cont - 1; j <= cont; j++) {
                                int axj = ar + step * k + j, zj = zr + step * k;
                                if (!RD(axj, zj)) continue;
                                if (k <= DAV_MERGE_ROWS) dav_add(&P, &n, axis, axj, zj, cont, 0);
                                else if (npath < 8) {
                                    path[npath][0] = axis ? -axj : axj; path[npath][1] = zj; npath++;
                                    *dav_markp(&P, axis ? -axj : axj, zj) |= (BYTE)(32 | cont);
                                }
                            }
                        continue;
                    }
                    for (k = 1;; k++) {
                        int got = 0;
                        for (j = 0; j < 3; j++) {
                            int axj = ar + step * k + j, zj = zr + step * k;
                            if (RD(axj, zj) && !(MK(axj, zj) & 8)) {
                                dav_add(&P, &n, axis, axj, zj, j == 0 ? 1 : j == 2 ? 2 : 0, step < 0 ? 1 : 2);
                                got = 1;
                            }
                        }
                        if (!got) break;
                    }
                }
#undef RD
#undef MK
#undef DOUT
#undef BX
#undef BZ
                for (k = 0; k < n && ok; k++) {
                    int cx = P.cell[k].x, cz = P.cell[k].z;
                    if ((cx <= x0 && x0 > 0) || (cz <= z0 && z0 > 0) || (cx >= x1 && x1 < W - 1) || (cz >= z1 && z1 < H - 1))
                        border = 1;
                    for (j = 0; j < 8 && ok; j++) {                /* isolated: no other road touches the band */
                        int qx = cx + DAV_DIR[j][0], qz = cz + DAV_DIR[j][1];
                        if (rb_at(&P.b, qx, qz) && !(dav_mark(&P, qx, qz) & 44)) { ok = 0; why = "touches road"; }
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
                        BYTE *m = dav_markp(&P, P.cell[amb[k]].x, P.cell[amb[k]].z);
                        *m = (BYTE)((*m & 0xf8) | 4 | (ch == 2 ? 3 : ch == 0 ? pref : 3 - pref));
                        cost += ch == 2 ? 100 : ch;
                    }
                    if (cost < bestcost && dav_valid(&P, n)) { best = combo; bestcost = cost; }
                }
                if (ok && best < 0) { ok = 0; why = "no split into two lone staircases"; }
                if (ok) {
                    int c = best;
                    for (k = 0; k < namb; k++, c /= 3) {
                        int ch = c % 3, pref = P.cell[amb[k]].pref;
                        BYTE *m = dav_markp(&P, P.cell[amb[k]].x, P.cell[amb[k]].z);
                        *m = (BYTE)((*m & 0xf8) | 4 | (ch == 2 ? 3 : ch == 0 ? pref : 3 - pref));
                    }
                }
                for (k = 0; k < nmg && ok; k++) {                  /* merge cells: (piece, state) from the case table */
                    for (j = 0; j < g_dav_nmrg && ok; j++) {
                        DavMrg *q = &g_dav_mrg[j];
                        int ax = mg[k][3] + q->dx, cz = mg[k][2] + q->dz, cx = axis ? -ax : ax;
                        if (q->axis != axis || q->end != mg[k][0] || q->cont != mg[k][1]) continue;
                        if (!(dav_mark(&P, cx, cz) & 4) || nmc >= 16) { ok = 0; why = "merge cell is not band road"; break; }
                        *dav_markp(&P, cx, cz) |= 64;
                        mcx[nmc] = cx; mcz[nmc] = cz; mcw[nmc] = ((DWORD)q->piece << 8) | q->state; nmc++;
                    }
                }
                for (k = 0; k < n && ok; k++) {                    /* pieces */
                    int cx = P.cell[k].x, cz = P.cell[k].z, m = dav_mark(&P, cx, cz);
                    DWORD va, vb;
                    if (m & 64) {
                        for (j = 0; j < nmc; j++) if (mcx[j] == cx && mcz[j] == cz) P.want[k] = mcw[j];
                        continue;
                    }
                    if (m & 16) {
                        for (j = 0; j < nj; j++)
                            if (P.junc[j].x == cx && P.junc[j].z == cz) {
                                P.want[k] = dav_junc_of(P.junc[j].n, P.junc[j].s1, P.junc[j].s2, P.junc[j].o, P.junc[j].e);
                                break;
                            }
                        if (j == nj || !P.want[k]) { ok = 0; why = "no junction piece declared"; }
                        continue;
                    }
                    va = (m & 1) ? g_dav_lone[dav_own_mask(&P, cx, cz, 1)] : 0;
                    vb = (m & 2) ? g_dav_lone[dav_own_mask(&P, cx, cz, 2)] : 0;
                    if (va && vb) {
                        WORD mid;
                        va--; vb--;
                        mid = dav_mid_of((WORD)(va >> 8), (WORD)(vb >> 8), (int)((vb - va) & 3));
                        if (!mid) { ok = 0; why = "no middle piece declared"; break; }
                        P.want[k] = ((DWORD)mid << 8) | (va & 0xff);
                    } else if (va || vb) {
                        DWORD v = (va ? va : vb) - 1;
                        int other = va ? 2 : 1, beside = 0, dx;
                        WORD outer = (v >> 8) == 35 ? dav_mid_of(35, 0, 0) : 0;
                        for (dx = -2; dx <= 2 && outer && !beside; dx++)  /* the other road beside it in its row */
                            if (dx) beside = (dav_mark(&P, cx + dx, cz) & other) != 0;
                        P.want[k] = beside ? (((DWORD)outer << 8) | (v & 0xff)) : v;
                    } else { ok = 0; break; }
                }
                if (ok) {
                    nb++;
                    for (k = 0; k < n + na; k++) {
                        int cx = k < n ? P.cell[k].x : P.arm[k - n].x, cz = k < n ? P.cell[k].z : P.arm[k - n].z;
                        DWORD want = k < n ? P.want[k] : ((DWORD)29 << 8) | P.arm[k - n].o;
                        DWORD cur = rb_at(&P.b, cx, cz);
                        int pos[3];
                        if (keep && k < n) keep[(cz - z0) * P.b.w + (cx - x0)] = 1;
                        if ((((cur & 0xffff) << 8) | ((cur >> 16) & 3)) == want) continue;
                        pos[0] = cx << 8; pos[1] = cz << 8; pos[2] = 0;
                        ((PFN_Put)(g_rb_m + 0x8919))(mgr, 0, lay, pos, want, -1, 8, 0);
                        nw++;
                    }
                    if (nw || !strcmp(who, "load"))
                        logf("dav: %s: band axis %d, %d row(s) from (%d,%d), %d cell(s), %d junction cell(s), %d arm "
                             "cell(s), %d merge(s), bends %d/%d, %d written", who, axis, rows, axis ? -x : x, z, n, nj, na,
                             nmg, bend[0], bend[1], nw);
                    nwall += nw;
                } else if (nj || na) {
                    logf("dav: %s: band axis %d from (%d,%d) with %d junction cell(s) left to the stock tiler: %s", who,
                         axis, axis ? -x : x, z, nj, why);
                }
                for (k = 0; k < n; k++) *dav_markp(&P, P.cell[k].x, P.cell[k].z) = 0;   /* clear this band's scratch */
                for (k = 0; k < na; k++) *dav_markp(&P, P.arm[k].x, P.arm[k].z) = 0;
                for (k = 0; k < npath; k++) *dav_markp(&P, path[k][0], path[k][1]) = 0;
            }
    }
    /* middle and junction pieces in the area (one cell in from the read border) that no band kept: back to stock */
    if (keep)
        for (z = z0 + 1; z < z1; z++)
            for (x = x0 + 1; x < x1; x++) {
                DWORD v = rb_at(&P.b, x, z);
                int rect[6];
                if (!v || !dav_is_mid((WORD)(v & 0xffff)) || keep[(z - z0) * P.b.w + (x - x0)]) continue;
                rect[0] = x << 8; rect[1] = z << 8; rect[2] = 0; rect[3] = x << 8; rect[4] = z << 8; rect[5] = 0;
                ((PFN_Retile)VT(mgr, 0xb0))(mgr, 0, rect, 3);
                nrev++;
                logf("dav: %s: (%d,%d) avenue piece %lu no longer in a band -> stock retile", who, x, z, v & 0xffff);
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
