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

static int dav_is_x(WORD id);

/* task avdiag (avenue lane rework, verify/avdiag/PLAN.md): one-way lane roles. Every DAV piece carries one-way lanes
   (right-hand, two lanes per carriageway); the writer places three role variants on top of the band's pieces:
     `davu <a> <b>`  the middle piece 20500 as the LAST middle cell of a free end carries the two-lane U-turn: piece a
                     at the end toward -t, b toward +t (axis 0; axis 1 swapped: the corner the U-turn wraps, in 20500's
                     own frame); both save as 43
     `davn <p> <v>`  a lone / outer piece p in a cell past that U-turn: v (no lanes, p's art, saved as p's base)
     `davt <p> <v>`  junction piece p whose road arrives from one side only (a T touching one carriageway): v
   And a diagonal avenue that bends into, or crosses, a straight avenue converts only when avcore's AVL would convert
   that straight band (avl_band_ok, before writing; avl_dir in the post-AVL put-back, AVENUE_LANES.md 5). */
#define DAV_MAX_ROLE 16
static WORD g_dav_u[2];
static WORD g_dav_n[DAV_MAX_ROLE][2], g_dav_t[DAV_MAX_ROLE][2];
static int g_dav_nn, g_dav_nt;
static int g_dav_post;                          /* 1 while the post-AVL put-back pass runs: avl_dir, not avl_band_ok */
static volatile LONG g_dav_n_avl;               /* bands left to the stock tiler: the straight avenue stays two-way */
static int avl_band_ok(int x, int z, int away);                     /* sc3netmod_avl.c (included after this file) */
static int avl_dir(int x, int z);
static int avl_post_set(int slot, int (*f)(BYTE *, int, int, int, int, const char *, int *));
static int dav_post(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who, int *rbox);
static int g_dav_probe, g_dav_pq[2], g_dav_pr;   /* dav_band_ok: a dry pass, the band through cell pq, its verdict */

static void dav_oline(const char *path, const char *line) {      /* davu / davn / davt */
    unsigned long a, b;
    char k = line[3];
    if (sscanf(line + 5, "%lu %lu", &a, &b) != 2 || !a || !b || a > 0xffff || b > 0xffff) {
        logf("### dav: %s: bad one-way role line '%s'", path, line);
        return;
    }
    if (k == 'u') { g_dav_u[0] = (WORD)a; g_dav_u[1] = (WORD)b; }
    else if (k == 'n' && g_dav_nn < DAV_MAX_ROLE) { g_dav_n[g_dav_nn][0] = (WORD)a; g_dav_n[g_dav_nn][1] = (WORD)b; g_dav_nn++; }
    else if (k == 't' && g_dav_nt < DAV_MAX_ROLE) { g_dav_t[g_dav_nt][0] = (WORD)a; g_dav_t[g_dav_nt][1] = (WORD)b; g_dav_nt++; }
    else { logf("### dav: %s: too many role lines - '%s' ignored", path, line); return; }
    avl_post_set(0 /* AVL_POST_DAV */, dav_post);
    logf("dav: %s: one-way role %c %lu -> %lu", path, k, a, b);
}

static WORD dav_role(WORD (*t)[2], int n, WORD p) {
    int k;
    for (k = 0; k < n; k++) if (t[k][0] == p) return t[k][1];
    return 0;
}

static int dav_is_role(WORD id) {
    int k;
    if (id && (id == g_dav_u[0] || id == g_dav_u[1])) return 1;
    for (k = 0; k < g_dav_nn; k++) if (g_dav_n[k][1] == id) return 1;
    for (k = 0; k < g_dav_nt; k++) if (g_dav_t[k][1] == id) return 1;
    return 0;
}

static int dav_is_mid(WORD id) {                 /* any avenue piece: middle, outer, junction, merge or crossing */
    int k;
    for (k = 0; k < g_dav_nmid; k++) if (g_dav_mid[k].piece == id) return 1;
    return dav_is_junc(id) || dav_is_mrg(id) || dav_is_x(id) || dav_is_role(id);     /* task avdiag: roles */
}

/* save as 43: a cell holding both roads (stock 35 draws one); the OUTER piece (b == 0) saves as its base 35; merge
   pieces as their `davs` lines say */
static int dav_save_43(WORD id) {
    int k;
    for (k = 0; k < g_dav_nmid; k++) if (g_dav_mid[k].piece == id) return g_dav_mid[k].b != 0;
    if (id && (id == g_dav_u[0] || id == g_dav_u[1])) return 1;                     /* task avdiag: 20500's U-turns */
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
    return dav_road(b, axis, a, z) && dav_road(b, axis, a + 1, z) && dav_road(b, axis, a + 2, z) &&
           !(dbv_claimed(axis ? -a : a, z) && dbv_claimed(axis ? -(a + 1) : a + 1, z) &&
             dbv_claimed(axis ? -(a + 2) : a + 2, z));        /* task diagbv: a row a diagonal boulevard holds */
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

/* crossings (task diagx, 2026-10-17): a diagonal avenue crossing another diagonal avenue or the straight avenue 11204,
   or ending on one (a T). `davx <id> <axis> <pax> <pdx> <pdz> <x0> <z0> <w> <h>` = a template: anchored on a band row
   of an axis-<axis> avenue (axis space, the row's left cell), a window of w x h cells from (x0, z0) relative to it;
   `davxg <id> <row> <w chars>` = one row of the window ('r' ROAD, '.' no ROAD, '-' either; table lines stay under the
   readers' 256 characters). `davxw <id> <dx> <dz> <piece> <state>` = a cell
   the template writes (its own pieces, and stock 11204 on the straight avenue's plain cells). pax 0/1: the window
   holds a band of that axis too, whose row's left cell is (pdx, pdz) from the anchor in this axis space; the crossing
   converts only when that band does (dry rounds until no band changes, then the write round); 255 none. Generated by
   diagave.py xbuild (recipe_crossings.json), offline twin diagave.py bands. A template is tried at every band row with road
   beside it; its window's road cells are not arms, do not count as touching, and a band end inside it has no stub,
   merge or bend. */
#define DAVX_MAX 64
#define DAVX_MAX_W 2048
#define DAVX_MAX_GRID 400
#define DAVX_MAX_M 16                                  /* matched templates per band */
#define DAVX_MAX_CW 512                                /* cells a band's crossings write */
#define DAV_MAX_ST 2048                                /* bands per pass (round status) */
typedef struct { WORD id; BYTE axis, pax; signed char pdx, pdz, x0, z0; BYTE w, h, got; char grid[DAVX_MAX_GRID]; } DavX;
typedef struct { WORD id; signed char dx, dz; WORD piece; BYTE state; } DavXW;
static DavX g_davx[DAVX_MAX];
static int g_davx_n, g_davx_partner;
static DavXW g_davxw[DAVX_MAX_W];
static int g_davxw_n;
static volatile LONG g_dav_n_x;

static void dav_xline(const char *path, const char *line) {
    unsigned long id, ax, pax, w, h;
    long pdx, pdz, x0, z0;
    DavX *t;
    if (sscanf(line + 5, "%lu %lu %lu %ld %ld %ld %ld %lu %lu", &id, &ax, &pax, &pdx, &pdz, &x0, &z0, &w, &h) != 9 ||
        id > 0xffff || ax > 1 || (pax > 1 && pax != 255) || w < 1 || h < 1 || w > 120 || w * h > DAVX_MAX_GRID ||
        pdx < -100 || pdx > 100 || pdz < -100 || pdz > 100 || x0 < -100 || x0 > 100 || z0 < -100 || z0 > 100) {
        logf("### dav: %s: bad crossing line: '%s'", path, line);
        return;
    }
    if (g_davx_n >= DAVX_MAX) { logf("### dav: %s: too many crossing templates - ignored", path); return; }
    t = &g_davx[g_davx_n++];
    t->id = (WORD)id; t->axis = (BYTE)ax; t->pax = (BYTE)pax; t->pdx = (signed char)pdx; t->pdz = (signed char)pdz;
    t->x0 = (signed char)x0; t->z0 = (signed char)z0; t->w = (BYTE)w; t->h = (BYTE)h;
    t->got = 0;                                 /* used only once all its rows came (davxg) */
    if (pax != 255) g_davx_partner = 1;
}

static void dav_xgline(const char *path, const char *line) {
    unsigned long id, row;
    char s[128];
    int k;
    if (sscanf(line + 6, "%lu %lu %127s", &id, &row, s) == 3)
        for (k = g_davx_n - 1; k >= 0; k--)
            if (g_davx[k].id == id) {
                if (row < g_davx[k].h && strlen(s) == g_davx[k].w && row == g_davx[k].got) {
                    memcpy(g_davx[k].grid + row * g_davx[k].w, s, g_davx[k].w);
                    g_davx[k].got++;
                    return;
                }
                break;
            }
    logf("### dav: %s: bad crossing row line: '%s'", path, line);
}


static void dav_xwline(const char *path, const char *line) {
    unsigned long id, v, st;
    long dx, dz;
    if (sscanf(line + 6, "%lu %ld %ld %lu %lu", &id, &dx, &dz, &v, &st) != 5 || id > 0xffff || dx < -100 || dx > 100 ||
        dz < -100 || dz > 100 || !v || v > 0xffff || st > 3) {
        logf("### dav: %s: bad crossing cell line: '%s'", path, line);
        return;
    }
    if (g_davxw_n >= DAVX_MAX_W) { logf("### dav: %s: too many crossing cells - ignored", path); return; }
    g_davxw[g_davxw_n].id = (WORD)id; g_davxw[g_davxw_n].dx = (signed char)dx; g_davxw[g_davxw_n].dz = (signed char)dz;
    g_davxw[g_davxw_n].piece = (WORD)v; g_davxw[g_davxw_n].state = (BYTE)st;
    g_davxw_n++;
}

static int dav_is_x(WORD id) {                       /* a crossing piece (variants only: 11204 is stock) */
    int k;
    if (!g_base[id]) return 0;
    for (k = 0; k < g_davxw_n; k++) if (g_davxw[k].piece == id) return 1;
    return 0;
}

typedef struct { int x, z; BYTE pref; } DavCell;    /* x in real space; pref: ambiguous end cell, 1 = A, 2 = B */
typedef struct { int x, z; BYTE o; } DavArm;         /* a straight road cell beside the avenue -> 29 in state o */
typedef struct { int x, z; BYTE n, s1, s2, o, e; } DavJ;   /* a junction cell and its descriptor */

#define DAV_MAX_ARMS 256
#define DAV_MAX_COLS 64

typedef struct { int x, z; BYTE axis, ok; } DavSt;  /* a band's start row (axis space) and whether it converted */

typedef struct {                                      /* one pass: the read buffer and per-band scratch */
    RbBuf b;
    BYTE *mark;                         /* [cell]: 1 A, 2 B, 4 band, 8 arm, 16 junction, 32 path, 64 merge */
    DavCell *cell;
    DWORD *want;
    DavArm *arm;
    DavJ *junc;
    BYTE *xmark;                        /* [cell] (task diagx): 1 road in a matched crossing window, 2 the crossing writes it */
    int *xwx, *xwz;                     /* the band's crossing writes: cell, want */
    DWORD *xww;
    DavSt *st[2];                       /* band status, previous round / this round */
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

static int dav_xm(DavPass *p, int x, int z) {         /* task diagx: crossing flags of a real cell */
    x -= p->b.x0; z -= p->b.z0;
    if (x < 0 || z < 0 || x >= p->b.w || z >= p->b.h) return 0;
    return p->xmark[z * p->b.w + x];
}

static void dav_xm_set(DavPass *p, int x, int z, int v) {
    x -= p->b.x0; z -= p->b.z0;
    if (x < 0 || z < 0 || x >= p->b.w || z >= p->b.h) return;
    p->xmark[z * p->b.w + x] = (BYTE)v;
}

/* template t anchored at axis-space row (a, z)? *out = 1 when part of its window lies outside the read box (inside
   the map): the caller then re-reads the whole map */
static int davx_match(DavPass *p, int axis, const DavX *t, int a, int z, int W, int H, int *out) {
    int i, j;
    if (t->got != t->h) return 0;

    for (j = 0; j < t->h; j++)
        for (i = 0; i < t->w; i++) {
            char g = t->grid[j * t->w + i];
            int ax = a + t->x0 + i, zq = z + t->z0 + j, rx = axis ? -ax : ax;
            if (g == '-') continue;
            if (rx < p->b.x0 || zq < p->b.z0 || rx >= p->b.x0 + p->b.w || zq >= p->b.z0 + p->b.h) {
                if (rx >= 0 && zq >= 0 && rx < W && zq < H) *out = 1;
                if (g == 'r') return 0;
                continue;
            }
            if ((g == 'r') != (dav_road(&p->b, axis, ax, zq) != 0)) return 0;
        }
    return 1;
}

/* every cell of both staircases a lone mask? (a crossing's own cells excepted) */
static int dav_valid(DavPass *p, int n) {
    int k;
    for (k = 0; k < n; k++) {
        int m = dav_mark(p, p->cell[k].x, p->cell[k].z);
        if (dav_xm(p, p->cell[k].x, p->cell[k].z) & 2) continue;
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
    int axis, x, z, n, k, j, border = 0, nb = 0, nwall = 0, nrev = 0, nxall = 0, round, done, dry, nst[2] = { 0, 0 };
    P.b.x0 = x0; P.b.z0 = z0; P.b.w = x1 - x0 + 1; P.b.h = z1 - z0 + 1;
    nbuf = (SIZE_T)P.b.w * P.b.h;
    mem = (BYTE *)VirtualAlloc(NULL, nbuf * 6 + DAV_MAX_CELLS * (sizeof(DavCell) + 4 + sizeof(DavJ)) +
                               DAV_MAX_ARMS * sizeof(DavArm) + DAVX_MAX_CW * 12 + 2 * DAV_MAX_ST * sizeof(DavSt),
                               MEM_COMMIT, PAGE_READWRITE);
    if (!mem) return 0;
    P.b.c = (DWORD *)mem;
    P.cell = (DavCell *)(mem + nbuf * 4);
    P.want = (DWORD *)(P.cell + DAV_MAX_CELLS);
    P.junc = (DavJ *)(P.want + DAV_MAX_CELLS);
    P.arm = (DavArm *)(P.junc + DAV_MAX_CELLS);
    P.xwx = (int *)(P.arm + DAV_MAX_ARMS);
    P.xwz = P.xwx + DAVX_MAX_CW;
    P.xww = (DWORD *)(P.xwz + DAVX_MAX_CW);
    P.st[0] = (DavSt *)(P.xww + DAVX_MAX_CW);
    P.st[1] = P.st[0] + DAV_MAX_ST;
    P.mark = (BYTE *)(P.st[1] + DAV_MAX_ST);
    P.xmark = P.mark + nbuf;
    for (z = 0; z < P.b.h; z++)
        for (x = 0; x < P.b.w; x++) P.b.c[z * P.b.w + x] = rb_read(mgr, lay, x0 + x, z0 + z, W, H);
    /* task diagx: with crossings of two diagonal avenues, dry rounds (no writes) until no band changes, each band's
       crossing needing the other band converted in the round before (round 0: assumed); then the write round */
    done = !g_davx_partner;
    for (round = 0;; round++) {
    dry = !done;
    nst[1] = 0;
    for (axis = 0; axis < 2; axis++) {
        int ax0 = axis ? -x1 : x0, ax1 = axis ? -x0 : x1;
#define RD(a, zq) dav_road(&P.b, axis, (a), (zq))
#define MK(a, zq) dav_mark(&P, axis ? -(a) : (a), (zq))
#define DCL(a, zq) dbv_claimed(axis ? -(a) : (a), (zq))      /* task diagbv: a diagonal boulevard's cell */
#define DOUT(a, zq) (RD(a, zq) && !(MK(a, zq) & 4) && !DCL(a, zq))
        for (z = z0; z <= z1; z++)
            for (x = ax0; x <= ax1; x++) {
                int rows = 0, ok = 1, step, nw = 0, namb = 0, amb[DAV_MAX_AMB], combo, ncombo, best = -1, run, brun;
                int bestcost = 0x7fffffff, na = 0, nj = 0, ncn = 0, ncs = 0, colN[DAV_MAX_COLS][2], colS[DAV_MAX_COLS][2];
                int nmg = 0, mg[2][4], npath = 0, path[16][2], nmc = 0, mcx[16], mcz[16], bend[2], e;
                int nxm = 0, xmt[DAVX_MAX_M], xma[DAVX_MAX_M], xmz[DAVX_MAX_M], nxw = 0, xend[2], t, xout = 0;
                DWORD mcw[16];
                BYTE side[1024];
                const char *why = "";
                if (!dav_full(&P.b, axis, x, z) || dav_full(&P.b, axis, x - 1, z - 1)) continue;
                while (dav_full(&P.b, axis, x + rows, z + rows)) rows++;
                for (k = 0, run = brun = 0; k < rows; k++)        /* anchored by MIN_ROWS clean rows (no road beside) */
                    brun += dav_clean(&P.b, axis, x + k, z + k);
                if (brun < DAV_MIN_ROWS || rows > 1024) continue;
                /* task diagx: crossing templates at every row with road beside it */
                for (k = 0; k < rows; k++) {
                    if (dav_clean(&P.b, axis, x + k, z + k)) continue;
                    for (t = 0; t < g_davx_n && nxm < DAVX_MAX_M; t++)
                        if (g_davx[t].axis == axis && davx_match(&P, axis, &g_davx[t], x + k, z + k, W, H, &xout)) {
                            xmt[nxm] = t; xma[nxm] = x + k; xmz[nxm] = z + k; nxm++;
                        }
                }
                if (xout) border = 1;
                for (k = 0; k < nxm; k++) {
                    const DavX *q = &g_davx[xmt[k]];
                    int i2, j2;
                    for (j2 = 0; j2 < q->h; j2++)
                        for (i2 = 0; i2 < q->w; i2++)
                            if (q->grid[j2 * q->w + i2] == 'r') {
                                int ax = xma[k] + q->x0 + i2, rx = axis ? -ax : ax, zq = xmz[k] + q->z0 + j2;
                                dav_xm_set(&P, rx, zq, dav_xm(&P, rx, zq) | 1);
                            }
                    for (j2 = 0; j2 < g_davxw_n; j2++) {
                        const DavXW *w = &g_davxw[j2];
                        int ax = xma[k] + w->dx, rx = axis ? -ax : ax, zq = xmz[k] + w->dz, m;
                        DWORD want = ((DWORD)w->piece << 8) | w->state;
                        if (w->id != q->id) continue;
                        for (m = 0; m < nxw; m++) if (P.xwx[m] == rx && P.xwz[m] == zq) break;
                        if (m < nxw) {
                            if (P.xww[m] != want) { ok = 0; why = "two crossings claim one cell"; }
                            continue;
                        }
                        if (nxw >= DAVX_MAX_CW) { ok = 0; why = "too many crossing cells"; continue; }
                        P.xwx[nxw] = rx; P.xwz[nxw] = zq; P.xww[nxw] = want; nxw++;
                        dav_xm_set(&P, rx, zq, dav_xm(&P, rx, zq) | 2);
                    }
                    if (q->pax != 255 && ok) {                 /* the other diagonal band: its start row */
                        int rx = axis ? -(xma[k] + q->pdx) : xma[k] + q->pdx, zp = xmz[k] + q->pdz;
                        int xp = q->pax ? -rx : rx, s, found = 0;
                        while (dav_full(&P.b, q->pax, xp - 1, zp - 1)) { xp--; zp--; }
                        if (round > 0) {
                            for (s = 0; s < nst[0]; s++)
                                if (P.st[0][s].axis == q->pax && P.st[0][s].x == xp && P.st[0][s].z == zp) {
                                    found = P.st[0][s].ok;
                                    break;
                                }
                            if (!found) { ok = 0; why = "the crossing diagonal avenue does not convert"; }
                        }
                    }
                }
#define XC(a, zq) dav_xm(&P, axis ? -(a) : (a), (zq))
                for (e = 0; e < 2; e++) {
                    int ar = e ? x + rows - 1 : x, zr = e ? z + rows - 1 : z;
                    xend[e] = (XC(ar, zr) | XC(ar + 1, zr) | XC(ar + 2, zr)) & 1;
                }
                /* bends: the avenue goes on as two parallel straight roads (stock avenue 11204). (u, v) = cell u right of
                   the end row's left cell, v rows past it (the top end turned half a circle: u -> 2 - u, v up). 1: along
                   x, rows v -1 and 0 go on past their d2; 2: along z, columns u 1 and 2 go on below. The carriageways'
                   edges meet the straight ones on one cell line, so the diagonal cells keep their middle-of-band pieces
                   and the straight cells stay stock. */
#define BX(u) (e ? x + rows - 1 + (u) : x + 2 - (u))
#define BZ(v) (e ? z + rows - 1 + (v) : z - (v))
                for (e = 0; e < 2; e++) {
                    bend[e] = 0;
                    if (xend[e]) continue;                         /* task diagx: the band ends in a crossing */
                    for (j = 0; j < 4 && !bend[e]; j++)          /* task diagbv: the end runs into a diagonal boulevard */
                        if (dbv_claimed(axis ? -BX(j) : BX(j), BZ(1))) bend[e] = 3;
                    if (bend[e]) continue;
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
                    else if (RD(aa - 1, zz) && !(XC(aa - 1, zz) & 1) && !DCL(aa - 1, zz)) {   /* diagx, diagbv */
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
                    else if (ok && RD(aa + 3, zz) && !(XC(aa + 3, zz) & 1) && !DCL(aa + 3, zz)) {
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
                    if ((side[step < 0 ? 0 : rows - 1] & 3) || xend[e]) continue;   /* task diagx: or a crossing */
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
#undef DCL
#undef BX
#undef BZ
#undef XC
                for (k = 0; k < n && ok; k++) {
                    int cx = P.cell[k].x, cz = P.cell[k].z;
                    if ((cx <= x0 && x0 > 0) || (cz <= z0 && z0 > 0) || (cx >= x1 && x1 < W - 1) || (cz >= z1 && z1 < H - 1))
                        border = 1;
                    for (j = 0; j < 8 && ok; j++) {                /* isolated: no other road touches the band */
                        int qx = cx + DAV_DIR[j][0], qz = cz + DAV_DIR[j][1];
                        if (rb_at(&P.b, qx, qz) && !(dav_mark(&P, qx, qz) & 44) && !(dav_xm(&P, qx, qz) & 1) &&
                            !dbv_claimed(qx, qz)) {                  /* task diagx, task diagbv */
                            ok = 0; why = "touches road";
                        }
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
                    if (dav_xm(&P, cx, cz) & 2) {                  /* task diagx: the crossing's piece */
                        for (j = 0; j < nxw; j++) if (P.xwx[j] == cx && P.xwz[j] == cz) P.want[k] = P.xww[j];
                        continue;
                    }
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
                /* task avdiag: a straight avenue the band bends into or crosses must convert to one-way halves too
                   (program rule: else the diagonal stays the stock ladder); before writing, AVL's dry-run predicate;
                   in the post-AVL put-back, AVL's band map */
#define BX(u) (e ? x + rows - 1 + (u) : x + 2 - (u))
#define BZ(v) (e ? z + rows - 1 + (v) : z - (v))
#define STRAIGHT_OK(cx_, cz_, away_) (g_dav_post ? avl_dir((cx_), (cz_)) >= 0 : avl_band_ok((cx_), (cz_), (away_)))
                for (e = 0; e < 2 && ok && (g_dav_u[0] || g_dav_nn || g_dav_nt); e++) {
                    int bx, bz, away;
                    if (bend[e] == 2) {                               /* along z, columns u 1 / 2 go on */
                        bx = BX(1); bz = BZ(1); away = e ? 2 : 0;
                    } else if (bend[e] == 1) {                        /* along x, rows v -1 / 0 go on past d2 */
                        bx = BX(3); bz = BZ(0); away = (e ? 1 : 3) ^ (axis ? 2 : 0);
                    } else continue;
                    if (!STRAIGHT_OK(axis ? -bx : bx, bz, away)) {
                        ok = 0; why = "the straight avenue it bends into stays two-way";
                        InterlockedIncrement(&g_dav_n_avl);
                    }
                }
                if (ok && (g_dav_u[0] || g_dav_nn || g_dav_nt) && nxw) {   /* the crossings' straight avenue cells */
                    int sx_ = 0, sz_ = 0, ns = 0;
                    for (j = 0; j < nxw; j++)
                        if ((P.xww[j] >> 8) != 11204) { sx_ += P.xwx[j]; sz_ += P.xwz[j]; ns++; }
                    for (j = 0; j < nxw && ok && ns; j++) {
                        int st = P.xww[j] & 3, away;
                        if ((P.xww[j] >> 8) != 11204) continue;
                        if (st % 2 == 0) away = P.xwx[j] * ns > sx_ ? 1 : 3;          /* band along x: E / W */
                        else away = P.xwz[j] * ns > sz_ ? 2 : 0;                     /* along z: S / N */
                        if (!STRAIGHT_OK(P.xwx[j], P.xwz[j], away)) {
                            ok = 0; why = "the straight avenue it crosses stays two-way";
                            InterlockedIncrement(&g_dav_n_avl);
                        }
                    }
                }
#undef STRAIGHT_OK
#undef BX
#undef BZ
                /* task avdiag: the one-way roles. A free end (no bend, crossing, junction or merge there): its last middle
                   cell (both carriageways, extreme along the band) holds the U-turn; the band cells past it carry none */
                for (e = 0; e < 2 && ok && g_dav_u[0]; e++) {
                    int merge_here = 0, best_k = -1, bs = 0, s;
                    if (bend[e] || xend[e] || (side[e ? rows - 1 : 0] & 3)) continue;
                    for (j = 0; j < nmg; j++) if (mg[j][0] == (e ? 0 : 1)) merge_here = 1;
                    if (merge_here) continue;
                    for (k = 0; k < n; k++) {
                        int cx = P.cell[k].x, cz = P.cell[k].z;
                        if ((dav_mark(&P, cx, cz) & 3) != 3) continue;
                        s = (axis ? -cx : cx) + cz;
                        if (best_k < 0 || (e ? s > bs : s < bs)) { best_k = k; bs = s; }
                    }
                    if (best_k < 0) continue;
                    if ((P.want[best_k] >> 8) == dav_mid_of(35, 35, 2))         /* 20500: the U-turn variant */
                        P.want[best_k] = ((DWORD)g_dav_u[(e != 0) ^ (axis != 0)] << 8) | (P.want[best_k] & 0xff);
                    for (k = 0; k < n; k++) {
                        int cx = P.cell[k].x, cz = P.cell[k].z;
                        WORD r;
                        s = (axis ? -cx : cx) + cz;
                        if (k == best_k || !(e ? s > bs : s < bs)) continue;
                        r = dav_role(g_dav_n, g_dav_nn, (WORD)(P.want[k] >> 8));
                        if (r) P.want[k] = ((DWORD)r << 8) | (P.want[k] & 0xff);
                    }
                }
                for (k = 0; k < n && ok && g_dav_nt; k++) {        /* a T: the junction's road arrives from one side */
                    int cx = P.cell[k].x, cz = P.cell[k].z, arms = 0, q;
                    WORD r = dav_role(g_dav_t, g_dav_nt, (WORD)(P.want[k] >> 8));
                    if (!r || !(dav_mark(&P, cx, cz) & 16)) continue;
                    for (j = 0; j < nj; j++) if (P.junc[j].x == cx && P.junc[j].z == cz) break;
                    if (j == nj) continue;
                    for (q = -1; q <= 1; q += 2) {
                        int nx = cx + (P.junc[j].o ? 0 : q), nz = cz + (P.junc[j].o ? q : 0), a2;
                        if (dav_mark(&P, nx, nz) & 16) { arms++; continue; }
                        for (a2 = 0; a2 < na; a2++) if (P.arm[a2].x == nx && P.arm[a2].z == nz) { arms++; break; }
                    }
                    if (arms == 1) P.want[k] = ((DWORD)r << 8) | (P.want[k] & 0xff);
                }
                if (nst[1] < DAV_MAX_ST) {                         /* task diagx: this round's status */
                    P.st[1][nst[1]].axis = (BYTE)axis; P.st[1][nst[1]].x = x; P.st[1][nst[1]].z = z;
                    P.st[1][nst[1]].ok = (BYTE)ok; nst[1]++;
                }
                if (g_dav_probe && !dry)                           /* task avdiag: dav_band_ok's question */
                    for (k = 0; k < n; k++)
                        if (P.cell[k].x == g_dav_pq[0] && P.cell[k].z == g_dav_pq[1]) g_dav_pr = ok;
                if (ok && !dry && !g_dav_probe) {
                    nb++;
                    for (k = 0; k < n + na + nxw; k++) {
                        int cx, cz;
                        DWORD want, cur;
                        int pos[3];
                        if (k < n) { cx = P.cell[k].x; cz = P.cell[k].z; want = P.want[k]; }
                        else if (k < n + na) {
                            cx = P.arm[k - n].x; cz = P.arm[k - n].z; want = ((DWORD)29 << 8) | P.arm[k - n].o;
                        } else {                                   /* the crossings' cells outside the band */
                            cx = P.xwx[k - n - na]; cz = P.xwz[k - n - na]; want = P.xww[k - n - na];
                            if (dav_mark(&P, cx, cz) & 4) continue;
                        }
                        cur = rb_at(&P.b, cx, cz);
                        if (keep && (k < n || k >= n + na) && cx >= x0 && cz >= z0 && cx <= x1 && cz <= z1)
                            keep[(cz - z0) * P.b.w + (cx - x0)] = 1;
                        if (dbv_claimed(cx, cz)) continue;          /* task diagbv: DBV writes its own cells */
                        if ((((cur & 0xffff) << 8) | ((cur >> 16) & 3)) == want) continue;
                        pos[0] = cx << 8; pos[1] = cz << 8; pos[2] = 0;
                        ((PFN_Put)(g_rb_m + 0x8919))(mgr, 0, lay, pos, want, -1, 8, 0);
                        nw++;
                    }
                    if (nw || !strcmp(who, "load"))
                        logf("dav: %s: band axis %d, %d row(s) from (%d,%d), %d cell(s), %d junction cell(s), %d arm "
                             "cell(s), %d merge(s), bends %d/%d, %d crossing(s), %d written", who, axis, rows,
                             axis ? -x : x, z, n, nj, na, nmg, bend[0], bend[1], nxm, nw);
                    nwall += nw;
                    nxall += nxm;
                } else if (!dry && !g_dav_probe && (nj || na || nxm)) {
                    logf("dav: %s: band axis %d from (%d,%d) with %d junction cell(s), %d crossing(s) left to the stock "
                         "tiler: %s", who, axis, axis ? -x : x, z, nj, nxm, why);
                }
                for (k = 0; k < n; k++) *dav_markp(&P, P.cell[k].x, P.cell[k].z) = 0;   /* clear this band's scratch */
                for (k = 0; k < na; k++) *dav_markp(&P, P.arm[k].x, P.arm[k].z) = 0;
                for (k = 0; k < npath; k++) *dav_markp(&P, path[k][0], path[k][1]) = 0;
                for (k = 0; k < nxm; k++) {                       /* and its crossings' windows */
                    const DavX *q = &g_davx[xmt[k]];
                    int i2, j2;
                    for (j2 = 0; j2 < q->h; j2++)
                        for (i2 = 0; i2 < q->w; i2++) {
                            int ax = xma[k] + q->x0 + i2;
                            dav_xm_set(&P, axis ? -ax : ax, xmz[k] + q->z0 + j2, 0);
                        }
                }
                for (k = 0; k < nxw; k++) dav_xm_set(&P, P.xwx[k], P.xwz[k], 0);
            }
    }
    if (done) break;
    /* stable when this round's statuses equal the last round's (same bands in the same order) */
    if (round > 0 && nst[0] == nst[1]) {
        for (k = 0; k < nst[1]; k++)
            if (P.st[0][k].ok != P.st[1][k].ok || P.st[0][k].x != P.st[1][k].x || P.st[0][k].z != P.st[1][k].z ||
                P.st[0][k].axis != P.st[1][k].axis) break;
        if (k == nst[1]) done = 1;
    }
    if (round >= 6) done = 1;
    { DavSt *tmp = P.st[0]; P.st[0] = P.st[1]; P.st[1] = tmp; nst[0] = nst[1]; }
    }
    /* middle and junction pieces in the area (one cell in from the read border) that no band kept: back to stock */
    if (keep)
        for (z = z0 + 1; z < z1; z++)
            for (x = x0 + 1; x < x1; x++) {
                DWORD v = rb_at(&P.b, x, z);
                int rect[6];
                if (!v || !dav_is_mid((WORD)(v & 0xffff)) || keep[(z - z0) * P.b.w + (x - x0)] || dbv_claimed(x, z))
                    continue;                                    /* task diagbv: claimed cells are DBV's */
                rect[0] = x << 8; rect[1] = z << 8; rect[2] = 0; rect[3] = x << 8; rect[4] = z << 8; rect[5] = 0;
                ((PFN_Retile)VT(mgr, 0xb0))(mgr, 0, rect, 3);
                nrev++;
                logf("dav: %s: (%d,%d) avenue piece %lu no longer in a band -> stock retile", who, x, z, v & 0xffff);
            }
    VirtualFree(mem, 0, MEM_RELEASE);
    InterlockedExchangeAdd(&g_dav_n_bands, nb);
    InterlockedExchangeAdd(&g_dav_n_cells, nwall);
    InterlockedExchangeAdd(&g_dav_n_rev, nrev);
    InterlockedExchangeAdd(&g_dav_n_x, nxall);
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

/* task avdiag: AVL's post phase (AVL_POST_DAV): after avl_run, a band that bends into or crosses a straight avenue AVL
   left two-way goes back to the stock tiler; then AVL re-decides the box (a straight band ending on it may change) */
static int dav_post(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who, int *rbox) {
    LONG before = g_dav_n_rev;
    if (!g_dav_on || (!g_dav_u[0] && !g_dav_nn && !g_dav_nt)) return 0;
    g_dav_post = 1;
    dav_run(mgr, x0, z0, x1, z1, who);
    g_dav_post = 0;
    if (g_dav_n_rev == before) return 0;
    rbox[0] = x0 - 24; rbox[1] = z0 - 24; rbox[2] = x1 + 24; rbox[3] = z1 + 24;
    if (rbox[0] < 0) rbox[0] = 0;
    if (rbox[1] < 0) rbox[1] = 0;
    logf("dav: %s: put back %ld band cell(s) whose straight avenue stayed two-way - AVL re-decides", who,
         (long)(g_dav_n_rev - before));
    return 1;
}

/* task avdiag (for bvlanes / DBV, AVENUE_LANES.md style): would the diagonal avenue band through cell (x, z) convert
   (to DAV's one-way pieces), on the current road grid with the full rule (junctions, crossings, merges, bends and their
   straight avenues via avl_band_ok)? A dry pass over the cell's surroundings: nothing written or reverted, no state
   kept. 0 when DAV is off or (x, z) is not a cell of a diagonal band. A cell DBV claims is not a band cell (the band
   ends there: bend kind 3), so ask with a cell of the avenue part beyond the claim. */
#define DAV_HAS_BAND_OK 1                 /* task avdiag: sc3netmod_dbv.c (bvlanes) calls dav_band_ok when set */
static int dav_band_ok(int x, int z) {
    BYTE *mgr = (BYTE *)g_rb_mgr;
    int W, H, x0, z0, x1, z1, border;
    if (!g_dav_on || !mgr || g_dav_probe) return 0;
    W = (*(int *)(mgr + 0x5c) >> 8) + 1; H = (*(int *)(mgr + 0x60) >> 8) + 1;
    x0 = x - 40 < 0 ? 0 : x - 40; z0 = z - 40 < 0 ? 0 : z - 40;
    x1 = x + 40 > W - 1 ? W - 1 : x + 40; z1 = z + 40 > H - 1 ? H - 1 : z + 40;
    g_dav_probe = 1; g_dav_pq[0] = x; g_dav_pq[1] = z; g_dav_pr = 0;
    border = dav_pass(mgr, x0, z0, x1, z1, W, H, "probe", NULL);
    if (border && !(x0 == 0 && z0 == 0 && x1 == W - 1 && z1 == H - 1)) {
        g_dav_pr = 0;
        dav_pass(mgr, 0, 0, W - 1, H - 1, W, H, "probe", NULL);
    }
    g_dav_probe = 0;
    return g_dav_pr;
}

static void dav_stats(void) {
    static LONG last;
    LONG n = g_dav_n_bands + g_dav_n_cells + g_dav_n_rev + g_dav_n_x + g_dav_n_avl;
    if (!g_dav_on || n == last) return;
    last = n;
    logf("stats: dav bands seen=%ld, cells written=%ld, middle cells reverted=%ld, crossings=%ld, left two-way for a "
         "straight avenue=%ld", g_dav_n_bands, g_dav_n_cells, g_dav_n_rev, g_dav_n_x, g_dav_n_avl);   /* task avdiag */

}
