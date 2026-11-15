/* sc3netmod_dbv.c - the DBV block of sc3netmod.dll (task diagbv, 2026-10-18): automatic diagonal boulevards.
 * #included by sc3netmod.c after the BV block; shares RBT's retile-pass and city-load hooks, where it runs BEFORE
 * DAV and BV: the cells of every boulevard it accepts go into a claims set that DAV and BV read (dbv_claimed), so the
 * diagonal avenue past a narrowing and the straight boulevard past a bend start where DBV stops. Offline twin, art
 * and lanes: re/tools/netmod/diagbv.py (bands(), plan_pieces), diagbv_paint.py; evidence verify/diagbv/.
 *
 * Three diagonal road drags joined side by side (each one cell over) make rows of four cells, d0..d3 (staircases A =
 * d0,d1, B = d1,d2, C = d2,d3; stock tiles them as a ladder 11203 / 43 / 43 / 11203). A and C become the
 * carriageways, B their extra lanes and a tree median. Canonical frame (= diagbv.py's): axis 0 = the down-right
 * diagonal as is; axis 1 = the real map turned back one state (canonical (x, z) is real (-z - 1, x), pieces + 1).
 *  chain     rows (z, a) with ROAD at (a..a+3, z), each the next row's left - 1; anchored by DBV_MIN_CLEAN rows with
 *            nothing beside them besides junction and end rows
 *  ends      the rows past the first / last row (the top end turned half a circle): a bend into three straight roads
 *            (along x: the last three rows run on to the right; along z: three columns go on below), a narrowing to
 *            the diagonal avenue, a taper to one of the three roads, a band ending on a row road, or a cap (all three
 *            stop); each end but the bends writes its stamp (dbvs lines), the bends write band pieces only.
 *            A cap needs only the rows its stamp writes plus one empty row (task avrbtfix: a road further away no
 *            longer refuses the band; one that touches still does). Any other end shape (a drag one row longer
 *            than the others, ...) is RAGGED (task avrbtfix): the band converts, the end's rows past it stay with the
 *            stock tiler (owner 2026-10-21: an end that does not convert is fine, the whole band turning into the
 *            stock ladder is not). Still refused: a narrowing whose avenue will not convert, a road beside the end row
 *  junctions a straight single road along x on a band row (both sides = crossing, one side = T) or along z through
 *            four rows (entering at a row's d3 from above, leaving at a row's d0 below); arms = two road cells -> 29
 *  pieces    band by d: d0 outer state 2, d1 inner state 2, d2 inner, d3 outer; then the stamps (a stamp's cells are
 *            relative to a row's left cell, 'row' family, or to the cell where a column road is that row's d0, 'col';
 *            turned: row (dx, dz) -> (3 - dx, -dz), col -> (-dx, -3 - dz), state + 2); overlapping stamps refused
 *  isolated  every other road 8-touching the band or its stamps is an arm, the road an end goes on into, or the
 *            straight roads past a bend
 * Write = FUN_10008919 per cell. Revert = rect retile of a DBV piece no band kept (the variants are not Protected).
 * Save: every piece saves as its base (outer 35, inner / junction / two-road end cells 43). Off: SC3NETMOD_DBV=0.
 * Table lines (netpack manifest "auto_diagonal_boulevards"): `dbvb <outer> <inner>`, `dbvs <kind> <dx> <dz> <piece>
 * <state>` with kind 1 jrow-both, 2 jrow-A, 3 jrow-stem, 4 jcol-both, 5 jcol-A, 6 narrow-C, 7 narrow-A, 8..10
 * taper-0..2, 11 cap-square, 12 cap-part, 13..15 taper-0s..2s, 16 cap-x4z3, 17 cap-x4z4.
 */

#define DBV_MIN_CLEAN 3
#define DBV_KINDS 26                         /* task diagfix: 18 BEND135, 19 BEND135M, 20 BENDAV, 21 BENDAVM, 22 BENDBV,
                                                23 JBVX, 24 JBVE, 25 JBVEO */
#define DBV_MAX_STAMP 40
#define DBV_MAX_USES 64
#define DBV_MAX_ROWS 1024
#define DBV_CLAIM 32768                      /* claims hash slots (power of two) */
#define DBV_MAX_BAD 64                       /* task dbvtouch */
#define DBV_MAX_FOR 128
#define DBV_TOUCH_TRIES 8

enum { DK_NONE = 0, DK_JROW_BOTH = 1, DK_JROW_A, DK_JROW_STEM, DK_JCOL_BOTH, DK_JCOL_A, DK_NARROW_C, DK_NARROW_A,
       DK_TAPER0, DK_TAPER1, DK_TAPER2, DK_CAP_SQ, DK_CAP_PART, DK_TAPER0S, DK_TAPER1S, DK_TAPER2S, DK_CAP_X4Z3,
       DK_CAP_X4Z4, DK_BEND135, DK_BEND135M, DK_BENDAV, DK_BENDAVM, DK_BENDBV, DK_JBVX, DK_JBVE, DK_JBVEO, DK_BEND_X = 100, DK_BEND_Z, DK_STEM, DK_RAGGED, DK_BEND_ZT };     /* DK_RAGGED: task avrbtfix */
static int dbv_b135_on(void);                /* task diagfix: DBVBEND135 (defined before dbv_band) */
static int dbv_bbv_on(void);                 /* task diagfix: DBVBBEND */

/* task avends F2a (2026-11-09, round brief ROUND_2026-11-09_avends.md, twin diagbv.classify_end "bend-z-tee"): a bend
   into three straight columns whose second and third rows past the end also carry an avenue arm on ONE side (two rows,
   the arm's first cells beside the columns; none on rows 1 and 4). The stock tiler leaves it; DBV called it ragged.
   The three columns and the arm are BV's (a boulevard narrowing into an avenue with an avenue T on its last two
   columns, sc3netmod_bv.c AVENDS F2b / F3); DBV writes the band as for a plain bend-z. Owner's Big One (583..585,
   107..109). Off: SC3NETMOD_DBVBENDT=0 (the end is ragged again). */
static int g_dbvt = -1;
static int dbvt_on(void) {
    if (g_dbvt < 0) {
        g_dbvt = !env_off("SC3NETMOD_DBVBENDT");
        logf("dbv: bend into a narrowing with an avenue T (avends F2a) %s", g_dbvt ? "on" : "off (SC3NETMOD_DBVBENDT=0)");
    }
    return g_dbvt;
}

typedef struct { signed char dx, dz; WORD piece; BYTE state; } DbvStamp;
static DbvStamp g_dbv_st[DBV_KINDS][DBV_MAX_STAMP];
static int g_dbv_nst[DBV_KINDS];
static WORD g_dbv_inn;                       /* g_dbv_out (declared in sc3netmod_rbt.c) != 0: DBV declared */
static DWORD *g_dbv_claim;                    /* claims of the current pass: (x << 12 | z) + 1, open addressing */
static int g_dbv_nclaim;
static volatile LONG g_dbv_n_bands, g_dbv_n_cells, g_dbv_n_rev;

/* task diagfix (round 2026-11-15, families c / d: xsect 49 50 52 53 54 55): DBVX, crossing templates. A diagonal
   boulevard meeting a diagonal avenue or another diagonal boulevard (crossing, T, corner) is a paved junction box, the
   owner's sheet_cd look. Templates are generated offline from that scene over the layout's symmetries, in DBV's
   canonical frame (verify/diagfix/dbvx_build.py): `dbvx <id> <x0> <z0> <w> <h>` + `dbvxg <id> <row> <cells>` (window
   from a band row's left cell: r road, . no road, - any) + `dbvxw <id> <dx> <dz> <piece> <state>` (cells to write,
   canonical state). A band row with road beside it (or a chain end) whose window matches gets the writes; DBV claims
   them, the diagonal avenue's cells too (DAV yields claimed cells and ends its band there). Off: SC3NETMOD_DBVX=0. */
#define DBVX_MAX 192
#define DBVX_MAX_GRID 1024
#define DBVX_MAX_W 4096
typedef struct { WORD id, w0, nw; signed char x0, z0; BYTE w, h, got; char grid[DBVX_MAX_GRID]; } DbvX;
typedef struct { signed char dx, dz; WORD piece; BYTE state; } DbvXW;
static DbvX g_dbvx[DBVX_MAX];
static int g_dbvx_n;
static DbvXW g_dbvxw[DBVX_MAX_W];
static int g_dbvxw_n;
static int g_dbvx_on = -1;
static volatile LONG g_dbvx_hits;
static int dbvx_on(void) {
    if (g_dbvx_on < 0) {
        g_dbvx_on = !env_off("SC3NETMOD_DBVX");
        logf("dbv: DBVX %s (%d crossing template(s): diagonal x diagonal junction boxes, SC3NETMOD_DBVX)",
             g_dbvx_on ? "on" : "off", g_dbvx_n);
    }
    return g_dbvx_on;
}

static void dbvx_line(const char *path, const char *line) {
    unsigned long id, w, h, row, pc, st;
    long x0, z0, dx, dz;
    char s[256];
    int k;
    if (!strncmp(line, "dbvxg ", 6)) {
        if (sscanf(line + 6, "%lu %lu %255s", &id, &row, s) == 3)
            for (k = g_dbvx_n - 1; k >= 0; k--)
                if (g_dbvx[k].id == id) {
                    if (row == g_dbvx[k].got && row < g_dbvx[k].h && strlen(s) == g_dbvx[k].w) {
                        memcpy(g_dbvx[k].grid + row * g_dbvx[k].w, s, g_dbvx[k].w);
                        g_dbvx[k].got++;
                        return;
                    }
                    break;
                }
        logf("### dbv: %s: bad crossing grid line '%s'", path, line);
        return;
    }
    if (!strncmp(line, "dbvxw ", 6)) {
        if (sscanf(line + 6, "%lu %ld %ld %lu %lu", &id, &dx, &dz, &pc, &st) == 5 && g_dbvx_n &&
            g_dbvx[g_dbvx_n - 1].id == id && dx >= -100 && dx <= 100 && dz >= -100 && dz <= 100 && pc && pc <= 0xffff &&
            st <= 3 && (pc == 29 || pc == 35 || g_base[pc]) && g_dbvxw_n < DBVX_MAX_W) {
            DbvXW *q = &g_dbvxw[g_dbvxw_n++];
            q->dx = (signed char)dx; q->dz = (signed char)dz; q->piece = (WORD)pc; q->state = (BYTE)st;
            g_dbvx[g_dbvx_n - 1].nw++;
            return;
        }
        logf("### dbv: %s: bad crossing write line '%s'", path, line);
        return;
    }
    if (sscanf(line + 5, "%lu %ld %ld %lu %lu", &id, &x0, &z0, &w, &h) != 5 || id > 0xffff || w < 1 || h < 1 ||
        w > 200 || w * h > DBVX_MAX_GRID || x0 < -100 || x0 > 100 || z0 < -100 || z0 > 100) {
        logf("### dbv: %s: bad crossing line '%s'", path, line);
        return;
    }
    if (g_dbvx_n >= DBVX_MAX) { logf("### dbv: %s: too many crossing templates - ignored", path); return; }
    {
        DbvX *t = &g_dbvx[g_dbvx_n++];
        t->id = (WORD)id; t->x0 = (signed char)x0; t->z0 = (signed char)z0; t->w = (BYTE)w; t->h = (BYTE)h;
        t->got = 0; t->w0 = (WORD)g_dbvxw_n; t->nw = 0;
    }
}

static void dbv_line(const char *path, const char *line) {
    unsigned long k, p, st, o, i;
    long dx, dz;
    if (!strncmp(line, "dbvx", 4)) { dbvx_line(path, line); return; }   /* task diagfix: DBVX */
    if (!strncmp(line, "dbvb ", 5)) {
        if (sscanf(line + 5, "%lu %lu", &o, &i) != 2 || !o || o > 0xffff || !i || i > 0xffff || !g_base[o] ||
            !g_base[i]) {
            logf("### dbv: %s: bad band line '%s'", path, line);
            return;
        }
        if (g_dbv_out) { logf("### dbv: %s: a second diagonal boulevard set - ignored", path); return; }
        g_dbv_out = (WORD)o; g_dbv_inn = (WORD)i;
        logf("dbv: %s: diagonal boulevard band pieces outer %lu, inner %lu", path, o, i);
        return;
    }
    if (sscanf(line + 5, "%lu %ld %ld %lu %lu", &k, &dx, &dz, &p, &st) != 5 || k < 1 || k >= DBV_KINDS ||
        dx < -12 || dx > 12 || dz < -12 || dz > 12 || !p || p > 0xffff || st > 3 || (p != 29 && p != 35 && !g_base[p])) {
        logf("### dbv: %s: bad stamp line '%s'", path, line);
        return;
    }
    if (g_dbv_nst[k] >= DBV_MAX_STAMP) { logf("### dbv: %s: too many cells for kind %lu - ignored", path, k); return; }
    g_dbv_st[k][g_dbv_nst[k]].dx = (signed char)dx; g_dbv_st[k][g_dbv_nst[k]].dz = (signed char)dz;
    g_dbv_st[k][g_dbv_nst[k]].piece = (WORD)p; g_dbv_st[k][g_dbv_nst[k]].state = (BYTE)st;
    g_dbv_nst[k]++;
}

static int dbv_is_piece(WORD id) {
    int k, j;
    if (!id || !g_dbv_out) return 0;
    if (id == g_dbv_out || id == g_dbv_inn) return 1;
    for (k = 1; k < DBV_KINDS; k++)
        for (j = 0; j < g_dbv_nst[k]; j++)
            if (g_dbv_st[k][j].piece == id && id != 29 && id != 35) return 1;
    for (k = 0; k < g_dbvxw_n; k++)                                      /* task diagfix: DBVX */
        if (g_dbvxw[k].piece == id && id != 29 && id != 35) return 1;
    return 0;
}

/* ---------------------------------------------------------------- claims (read by DAV and BV) */
static DWORD dbv_hash(int x, int z) { return (((DWORD)x * 2654435761UL) ^ ((DWORD)z * 40503UL)) & (DBV_CLAIM - 1); }

static void dbv_claim(int x, int z) {
    DWORD key = ((DWORD)(x & 0xfff) << 12 | (DWORD)(z & 0xfff)) + 1, h = dbv_hash(x, z);
    if (!g_dbv_claim || g_dbv_nclaim >= DBV_CLAIM / 2) return;
    while (g_dbv_claim[h] && g_dbv_claim[h] != key) h = (h + 1) & (DBV_CLAIM - 1);
    if (!g_dbv_claim[h]) { g_dbv_claim[h] = key; g_dbv_nclaim++; }
}

static int dbv_claimed(int x, int z) {
    DWORD key, h;
    if (hwave_claimed(x, z)) return 1;                                   /* task hwave: diagonal transitions */
    if (!g_dbv_claim || !g_dbv_nclaim || x < 0 || z < 0) return 0;
    key = ((DWORD)(x & 0xfff) << 12 | (DWORD)(z & 0xfff)) + 1;
    h = dbv_hash(x, z);
    while (g_dbv_claim[h]) {
        if (g_dbv_claim[h] == key) return 1;
        h = (h + 1) & (DBV_CLAIM - 1);
    }
    return 0;
}

/* ---------------------------------------------------------------- one pass */
typedef struct { int x, z; DWORD want; } DbvCell;
typedef struct { int kind, rx, rz, turned; } DbvUse;
typedef struct {
    RbBuf b;
    int axis;
    BYTE *mark;                 /* [real cell]: 1 band, 2 path, 4 arm, 8 stamped, 16 not band (bend), 32 written */
    BYTE *owner;                /* [real cell]: use index + 1 of the stamp that wrote it */
    DbvCell *cell;
    int n;
    int ragged;                 /* task avrbtfix: ends of the last accepted band left to the stock tiler */
    int nbad, badx[DBV_MAX_BAD], badz[DBV_MAX_BAD];       /* task dbvtouch: this try's touching cells (real) */
    int nfor, forx[DBV_MAX_FOR], forz[DBV_MAX_FOR];       /* task dbvtouch: cells masked out of the read buffer */
    DWORD forv[DBV_MAX_FOR];
    int nstub;                  /* task dbvtouch: one-cell stub arms of the last accepted band */
    int xout;                   /* task diagfix DBVX: a template could match but its window leaves the read buffer */
    int xdbg, xbest, xbid, xbx, xbz, xba, xbzz;   /* task diagfix DBVX: SC3NETMOD_DBVXDBG nearest miss */
} DbvPass;

#define DBV_RX(p, cx, cz) ((p)->axis ? -(cz) - 1 : (cx))
#define DBV_RZ(p, cx, cz) ((p)->axis ? (cx) : (cz))

static int dbv_rd(DbvPass *p, int cx, int cz) { return rb_at(&p->b, DBV_RX(p, cx, cz), DBV_RZ(p, cx, cz)) != 0; }

/* task dbvtouch (owner 2026-10-31: "A road touching a diagonal avenue should keep the avenue"; the owner's "3-lane
   avenue" is this boulevard). A road touching a band in a shape the rules have no junction or end for (a stub, a road
   beside an end row, a column road that is not a straight single road) refused the band and the revert loop
   stock-retiled all of it. Now the band is judged again with the touching road's cells masked out of the read buffer
   (read as no road), up to DBV_TOUCH_TRIES times: the band converts, the touching road keeps its stock pieces. A
   one-cell stub beside a band row is a row junction instead (its arm = the stock dead end 11225 facing the band). The
   mask lives only while its band is judged and written (dbv_unmask). Off: SC3NETMOD_DBVTOUCH=0. */
static int g_dbv_touch = -1;
static volatile LONG g_dbv_n_touch, g_dbv_n_stub;

static void dbv_bad(DbvPass *p, int cx, int cz) {                        /* canonical cell */
    if (g_dbv_touch > 0 && p->nbad < DBV_MAX_BAD && dbv_rd(p, cx, cz)) {
        p->badx[p->nbad] = DBV_RX(p, cx, cz); p->badz[p->nbad] = DBV_RZ(p, cx, cz); p->nbad++;
    }
}

static int dbv_mask(DbvPass *p) {                                         /* -> cells newly masked */
    int k, n = 0;
    for (k = 0; k < p->nbad && p->nfor < DBV_MAX_FOR; k++) {
        int x = p->badx[k] - p->b.x0, z = p->badz[k] - p->b.z0;
        DWORD *c;
        if (x < 0 || z < 0 || x >= p->b.w || z >= p->b.h) continue;
        c = &p->b.c[z * p->b.w + x];
        if (!*c) continue;
        p->forx[p->nfor] = p->badx[k]; p->forz[p->nfor] = p->badz[k]; p->forv[p->nfor] = *c; p->nfor++;
        *c = 0;
        n++;
    }
    p->nbad = 0;
    return n;
}

static void dbv_unmask(DbvPass *p) {
    while (p->nfor > 0) {
        p->nfor--;
        p->b.c[(p->forz[p->nfor] - p->b.z0) * p->b.w + (p->forx[p->nfor] - p->b.x0)] = p->forv[p->nfor];
    }
    p->nbad = 0;
}

static BYTE *dbv_mk(DbvPass *p, BYTE *buf, int cx, int cz) {
    static BYTE dummy;
    int x = DBV_RX(p, cx, cz) - p->b.x0, z = DBV_RZ(p, cx, cz) - p->b.z0;
    if (x < 0 || z < 0 || x >= p->b.w || z >= p->b.h) { dummy = 0; return &dummy; }
    return &buf[z * p->b.w + x];
}

static int dbv_full(DbvPass *p, int a, int z) {
    return dbv_rd(p, a, z) && dbv_rd(p, a + 1, z) && dbv_rd(p, a + 2, z) && dbv_rd(p, a + 3, z);
}

/* row j (1..6) past an end as a mask of d -2..6 (bit d + 2); e 1 bottom, 0 top (turned) */
#define DBV_CELLX(dx, dz) (e ? a_e + (dx) : a_e + 3 - (dx))
#define DBV_CELLZ(dx, dz) (e ? z_e + (dz) : z_e - (dz))
#define DBV_RDE(dx, dz) dbv_rd(p, DBV_CELLX(dx, dz), DBV_CELLZ(dx, dz))
#define DM(a) (1u << ((a) + 2))

/* task bvlanes (AVENUE_LANES.md program rule): the narrowing's lanes are one-way, so the diagonal avenue it goes on
   into must convert; else the whole band stays stock. Asks avdiag's dry-run dav_band_ok with a cell of the avenue's
   first full row past the claim (narrow-C claims 2 rows, narrow-A none). Built only once DAV has the predicate
   (DAV_HAS_BAND_OK, set in sc3netmod_dav.c next to dav_band_ok); before that a narrowing converts unchecked. */
static int dbv_narrow_ok(DbvPass *p, int z_e, int a_e, int e, int kind) {
#ifdef DAV_HAS_BAND_OK
    int j = kind == DK_NARROW_C ? 3 : 1, d = kind == DK_NARROW_C ? 0 : 1;
    int cx = DBV_CELLX(j + d, j), cz = DBV_CELLZ(j + d, j);
    return dav_band_ok(DBV_RX(p, cx, cz), DBV_RZ(p, cx, cz));
#else
    (void)p; (void)z_e; (void)a_e; (void)e; (void)kind;
    return 1;
#endif
}

static int dbv_end_kind(DbvPass *p, int z_e, int a_e, int e, int nrows) {
    unsigned rr[6];
    int j, d, dz, ok;
    /* task diagfix (xsect 45): DBVBBEND, a straight BOULEVARD's three rows (0, -1, -2 from their d3 + 1 on) into the end
       at 135 degrees: the band's last three rows are the stamp `bendbv` (paved bend box opening into the boulevard).
       Tested before DK_BEND_X, which is the same shape with the overlap left to BV (BV's BVBEND leaves it too) */
    for (d = -2, ok = 1; d <= 7 && ok; d++) ok = !DBV_RDE(d, 1);
    if (ok && !DBV_RDE(-1, 0) && DBV_RDE(4, 0) && DBV_RDE(5, 0) && DBV_RDE(6, 0) && DBV_RDE(3, -1) &&
        DBV_RDE(4, -1) && DBV_RDE(5, -1) && DBV_RDE(2, -2) && DBV_RDE(3, -2) && DBV_RDE(4, -2) && !DBV_RDE(1, -3) &&
        !DBV_RDE(2, -3) && !DBV_RDE(-2, -1) && !DBV_RDE(-3, -2) && g_dbv_nst[DK_BENDBV] && dbv_bbv_on()) {
        int bvx = 0;                     /* BV still holds the overlap (no BVBEND): leave it to DK_BEND_X, as before */
        for (dz = 0; dz >= -2; dz--)
            for (d = dz; d <= dz + 3; d++) {
                int cx = DBV_CELLX(d, dz), cz = DBV_CELLZ(d, dz);
                DWORD v = rb_at(&p->b, DBV_RX(p, cx, cz), DBV_RZ(p, cx, cz));
                if (v && bv_is_piece((WORD)(v & 0xffff))) bvx = 1;
            }
        if (!bvx) return DK_BENDBV;
    }
    ok = nrows >= 3 + DBV_MIN_CLEAN && !DBV_RDE(1, -3);
    for (dz = -2; dz <= 0 && ok; dz++) ok = DBV_RDE(4, dz) && DBV_RDE(5, dz) && !DBV_RDE(dz - 1, dz);
    for (d = -1; d <= 6 && ok; d++) ok = !DBV_RDE(d, 1);
    if (ok) return DK_BEND_X;
    for (j = 1; j <= 6; j++) {
        rr[j - 1] = 0;
        for (d = -2; d <= 6; d++) if (DBV_RDE(j + d, j)) rr[j - 1] |= DM(d);
    }
#define R012 (DM(0) | DM(1) | DM(2))
#define R123 (DM(1) | DM(2) | DM(3))
    if (rr[0] == R012 && rr[1] == (DM(-1) | DM(0) | DM(1))) return DK_BEND_Z;
    if (rr[0] == R012 && dbvt_on()) {                                    /* task avends F2a */
        int east = DBV_RDE(4, 2) && DBV_RDE(4, 3), west = DBV_RDE(0, 2) && DBV_RDE(0, 3), ar = east ? 4 : 0, na = east ? 0 : 4;
        if ((east ^ west) && DBV_RDE(1, 2) && DBV_RDE(2, 2) && DBV_RDE(3, 2) && DBV_RDE(1, 3) && DBV_RDE(2, 3) &&
            DBV_RDE(3, 3) && !DBV_RDE(ar, 1) && !DBV_RDE(ar, 4) && !DBV_RDE(na, 2) && !DBV_RDE(na, 3) &&
            DBV_RDE(east ? 5 : -1, 2) && DBV_RDE(east ? 5 : -1, 3))
            return DK_BEND_ZT;
    }
    for (j = 0, ok = 1; j < 5; j++) ok = ok && rr[j] == R012;
    if (ok) return dbv_narrow_ok(p, z_e, a_e, e, DK_NARROW_C) ? DK_NARROW_C : DK_NONE;              /* task bvlanes */
    if (rr[0] == R123 && rr[1] == R123 && rr[2] == R123)
        return dbv_narrow_ok(p, z_e, a_e, e, DK_NARROW_A) ? DK_NARROW_A : DK_NONE;                  /* task bvlanes */
    for (d = 0; d <= 2; d++) if (rr[0] == (DM(d) | DM(d + 1)) && rr[1] == rr[0]) return DK_TAPER0 + d;
    if (rr[0] == R012 && rr[1] == (DM(0) | DM(1)) && rr[2] == (DM(0) | DM(1))) return DK_TAPER0S;
    if (rr[0] == R012 && rr[1] == (DM(1) | DM(2)) && rr[2] == (DM(1) | DM(2))) return DK_TAPER1S;
    if (rr[0] == R123 && rr[1] == (DM(2) | DM(3)) && rr[2] == (DM(2) | DM(3))) return DK_TAPER2S;
    if (!rr[0] && !rr[1] && !DBV_RDE(-1, 0) && DBV_RDE(4, 0) && DBV_RDE(5, 0) && DBV_RDE(6, 0) && !DBV_RDE(4, -1) &&
        !DBV_RDE(5, -1) && !DBV_RDE(6, -1) && !DBV_RDE(5, 1) && !DBV_RDE(6, 1) && g_dbv_nst[DK_BEND135] && dbv_b135_on())
        return DK_BEND135;                                               /* task diagfix: DBVBEND135 */
    /* the mirror (x <-> z): the drags' flat end seen in the turned frame (cap-x4z4's partial rows) with a straight road
       going on down from its last cell; on the map, a diagonal boulevard on axis 1 with a road along x into its end */
    if (rr[0] == (DM(0) | DM(1) | DM(2)) && rr[1] == (DM(0) | DM(1)) && rr[2] == DM(0) && rr[3] == DM(-1) &&
        rr[4] == DM(-2) && DBV_RDE(3, 6) && !DBV_RDE(2, 5) && !DBV_RDE(4, 5) && !DBV_RDE(2, 6) && !DBV_RDE(4, 6) &&
        !DBV_RDE(-1, 0) && !DBV_RDE(4, 0) && g_dbv_nst[DK_BEND135M] && dbv_b135_on())   /* a straight road, 3+ cells */
        return DK_BEND135M;
    /* task diagfix (xsect 34): a straight AVENUE (rows 0 and -1, 3+ cells each, from d3 + 1 / d3 of row -1 + 1 on)
       into the end at 135 degrees: the boulevard closes into a paved bend box and opens into the avenue (stamp
       `bendav`, verify/diagfix/paint_34.py); the avenue's end column is stamped as avlj pieces so AVL ends it there */
    if (!rr[0] && !DBV_RDE(-1, 0) && DBV_RDE(4, 0) && DBV_RDE(5, 0) && DBV_RDE(6, 0) && DBV_RDE(3, -1) &&
        DBV_RDE(4, -1) && DBV_RDE(5, -1) && !DBV_RDE(2, -2) && !DBV_RDE(3, -2) && !DBV_RDE(4, -2) && !DBV_RDE(5, -2) &&
        g_dbv_nst[DK_BENDAV] && dbv_b135_on())
        return DK_BENDAV;
    /* its x <-> z mirror (an avenue along x into an axis-1 boulevard, seen in the turned frame): cap-x4z4's partial
       rows with the avenue's two columns going on down from them (columns d0 of row 3 and d-1 of row 3 + 1) */
    if (rr[0] == (DM(0) | DM(1) | DM(2)) && rr[1] == (DM(0) | DM(1)) && rr[2] == (DM(-1) | DM(0)) &&
        rr[3] == (DM(-2) | DM(-1)) && DBV_RDE(3, 5) && DBV_RDE(2, 5) && DBV_RDE(3, 6) && DBV_RDE(2, 6) &&
        !DBV_RDE(1, 4) && !DBV_RDE(1, 5) && !DBV_RDE(4, 5) && !DBV_RDE(4, 6) && !DBV_RDE(-1, 0) && !DBV_RDE(4, 0) &&
        g_dbv_nst[DK_BENDAVM] && dbv_b135_on())
        return DK_BENDAVM;
    if (!rr[0] && DBV_RDE(-1, 0) && DBV_RDE(4, 0)) return DK_STEM;
    if (DBV_RDE(-1, 0) || DBV_RDE(4, 0)) return DK_NONE;
    /* task avrbtfix: caps need their stamp rows + one empty row (was: all six rows empty) */
    if (!rr[0]) return DK_CAP_SQ;
    if (rr[0] == R012 && !rr[1]) return DK_CAP_PART;
    if (rr[0] == R012 && rr[1] == (DM(0) | DM(1)) && !rr[2]) return DK_CAP_X4Z3;
    if (rr[0] == R012 && rr[1] == (DM(0) | DM(1)) && rr[2] == DM(0) && !rr[3]) return DK_CAP_X4Z4;
    return DK_RAGGED;                                                    /* task avrbtfix (was DK_NONE) */
#undef R012
#undef R123
}

static void dbv_turn(int fam_col, int *dx, int *dz) {
    if (fam_col) { *dx = -*dx; *dz = -3 - *dz; }
    else { *dx = 3 - *dx; *dz = -*dz; }
}

/* arms of a junction kind (canonical, relative), up to 4 -> count */
static int dbv_arms_of(int kind, int ax[4], int az[4], int *o) {
    int n = 0;
    if (kind == DK_JROW_BOTH || kind == DK_JROW_A || kind == DK_JROW_STEM) {
        *o = 0;
        ax[n] = -1; az[n++] = 0; ax[n] = -2; az[n++] = 0;
        if (kind != DK_JROW_A) { ax[n] = 4; az[n++] = 0; ax[n] = 5; az[n++] = 0; }
    } else {
        *o = 1;
        ax[n] = 0; az[n++] = 1; ax[n] = 0; az[n++] = 2;
        if (kind == DK_JCOL_BOTH) { ax[n] = 0; az[n++] = -4; ax[n] = 0; az[n++] = -5; }
    }
    return n;
}

/* task diagfix (round 2026-11-14b milestone 2, xsect cases 50 52 54 55): DBVCAPCLEAN. The axis-1 frame is the map
   turned one state, so a band's rows there are real COLUMNS. A drag of 7 rows makes 7 full rows on axis 0 but only 4
   on axis 1: the drags' flat ends (along x) are, in the turned frame, the cap-x4z3 / cap-x4z4 ends whose partial rows
   hold the other 3. Each end then takes its row as an end row, and a 7-row diagonal boulevard on axis 1 had 2 clean
   rows left of the 3 the anchor needs ("fewer than 3 clean rows": the stock 43 ladder, drawn as a chain of
   roundabouts, wherever it meets anything). Now the end row of a cap end (square, part, x4z3, x4z4: their shape is
   checked cell by cell) or of a ragged end (the rows past it stay stock; in the xsect sweep case 49's avenue touches
   case 50's boulevard end, so that end is ragged there and a cap alone) counts as clean when nothing is beside it.
   Off: SC3NETMOD_DBVCAPCLEAN=0. */
static int g_dbv_capclean = -1;
static int dbv_capclean_on(void) {
    if (g_dbv_capclean < 0) {
        g_dbv_capclean = !env_off("SC3NETMOD_DBVCAPCLEAN");
        logf("dbv: DBVCAPCLEAN %s (a cap end's row counts as a clean row, SC3NETMOD_DBVCAPCLEAN)",
             g_dbv_capclean ? "on" : "off");
    }
    return g_dbv_capclean;
}
/* task diagfix (round 2026-11-14b family a, xsect 19; owner chose "taper + bend" 2026-11-14): DBVBEND135. A single
   straight road meeting a diagonal boulevard's end row from the side of the carriageway that starts that row (canonical
   bottom end: from +x into d3; top end, turned: from -x into d0), nothing past the end row: the end's rows hold the
   bend stamp (`dbvs 18 ...`, painted by verify/diagfix/paint_19.py: the far side closes, the median ends in a nose, the
   near carriageway turns into the road); the road's cells stay stock. Without it that road touched the end and was
   masked (DBVTOUCH), ending square against the cap. Off: SC3NETMOD_DBVBEND135=0. */
static int g_dbv_b135 = -1;
static int dbv_b135_on(void) {
    if (g_dbv_b135 < 0) {
        g_dbv_b135 = !env_off("SC3NETMOD_DBVBEND135");
        logf("dbv: DBVBEND135 %s (a road into a diagonal boulevard's end at 135 degrees: the end tapers and turns, "
             "SC3NETMOD_DBVBEND135)", g_dbv_b135 ? "on" : "off");
    }
    return g_dbv_b135;
}

/* task diagfix (round 2026-11-14b art family a, xsect 45): DBVBBEND. A straight BOULEVARD (BV, three rows) into a
   diagonal boulevard's end at 135 degrees, from the side of the end row's d3 (canonical bottom end: rows 0, -1, -2 from
   +x, its rows starting at the band's outer edge; on the map case 45, the boulevard from -x into the top end). Before,
   BV took the band's first cells for its run and DBV wrote the rest (the boulevard ended square against the band).
   Now the band's last three rows hold the stamp `bendbv` (a paved bend box with a rounded kerb that opens into the
   boulevard, the median ends in a nose; verify/diagfix/paint_45.py) and BV ends its run before them (orthfix BVBEND,
   end type 8). Off: SC3NETMOD_DBVBBEND=0. */
static int g_dbv_bbv = -1;
static int dbv_bbv_on(void) {
    if (g_dbv_bbv < 0) {
        g_dbv_bbv = !env_off("SC3NETMOD_DBVBBEND");
        logf("dbv: DBVBBEND %s (a boulevard into a diagonal boulevard's end at 135 degrees: the end is a paved bend box, "
             "SC3NETMOD_DBVBBEND)", g_dbv_bbv ? "on" : "off");
    }
    return g_dbv_bbv;
}

/* task diagfix (round 2026-11-15, xsect 42 / 44): DBVJBV. A straight BOULEVARD (BV, three rows) crossing a diagonal
   boulevard (rows beside the band on both sides: stamp `jbv-x`) or ending against it (one side: `jbv-e`, the boulevard
   on the band's +x side; DBV turns it half a circle for -x). Before, DBVBROW kept such rows from being junction arms
   and the band's cells there were plain band pieces / end stamps (the boulevard ran into the band's kerb). Now the
   band's cells in and beside the boulevard's rows are a paved junction box (the 38 / 40 look, orthfix's mockup scene,
   verify/diagfix/dbbox_build.py) and the boulevard's cells are left to BV (orthfix BVDIAG stops BV at the band).
   Off: SC3NETMOD_DBVJBV=0. */
static int g_dbv_jbv = -1;
static int dbv_jbv_on(void) {
    if (g_dbv_jbv < 0) {
        g_dbv_jbv = !env_off("SC3NETMOD_DBVJBV");
        logf("dbv: DBVJBV %s (a boulevard crossing or ending against a diagonal boulevard: a paved junction box, "
             "SC3NETMOD_DBVJBV)", g_dbv_jbv ? "on" : "off");
    }
    return g_dbv_jbv;
}

static int dbv_is_cap(int kind) {
    return kind == DK_CAP_SQ || kind == DK_CAP_PART || kind == DK_CAP_X4Z3 || kind == DK_CAP_X4Z4 || kind == DK_RAGGED;
}

/* task diagfix (round 2026-11-14b, orthfix BOXCELLS.md, xsect 42): DBVBROW. A boulevard (three straight roads side by
   side) crossing a diagonal boulevard has only its outermost row free of road above / below, so DBV made that one row a
   junction arm (29 at (32,88), (33,88)) and claimed it: BV, which stops at the band since BVDIAG, could not give the
   boulevard its end cells there. A row road that is one row of a run of 3+ rows beside the band (road at the same
   side cell in the rows above / below) is not an arm: DBV masks it as a touching road (DBVTOUCH) and does not claim it.
   Off: SC3NETMOD_DBVBROW=0. */
static int g_dbv_brow = -1;
static int dbv_brow_on(void) {
    if (g_dbv_brow < 0) {
        g_dbv_brow = !env_off("SC3NETMOD_DBVBROW");
        logf("dbv: DBVBROW %s (a boulevard's row beside a diagonal boulevard is not a junction arm, SC3NETMOD_DBVBROW)",
             g_dbv_brow ? "on" : "off");
    }
    return g_dbv_brow;
}

static int dbv_rd_any(DbvPass *p, int cx, int cz) {                /* task diagfix: road, or masked by DBVTOUCH */
    int k, rx = DBV_RX(p, cx, cz), rz = DBV_RZ(p, cx, cz);
    if (dbv_rd(p, cx, cz)) return 1;
    for (k = 0; k < p->nfor; k++) if (p->forx[k] == rx && p->forz[k] == rz) return 1;
    return 0;
}

/* the rule on one anchored chain (x0, z0, n rows), canonical; -> 1 accepted (cells in p->cell), 0 refused */
static int dbv_band(DbvPass *p, int x0, int z0, int n, const char **why) {
    DbvUse use[DBV_MAX_USES];
    BYTE endrow[DBV_MAX_ROWS], jbrow[DBV_MAX_ROWS];                      /* task diagfix: DBVJBV rows */
    BYTE jxrow[DBV_MAX_ROWS];                                            /* task diagfix: DBVX rows */
    int nxm = 0, xmt[8], xma[8], xmz[8], m;                              /* task diagfix: DBVX matches */
    int nu = 0, e, k, j, i, cx, cz, nclean = 0, armx[256], armz[256], armo[256], na = 0;
    int sw, se, na0, tbad = 0;                                           /* task dbvtouch */
    int ekind[2] = { DK_NONE, DK_NONE };                                 /* task diagfix: DBVCAPCLEAN */
    *why = "";
    p->n = 0;
    p->ragged = 0;                                                       /* task avrbtfix */
    p->nstub = 0;                                                        /* task dbvtouch */
    p->xout = 0;                                                         /* task diagfix DBVX */
    memset(endrow, 0, n);
    memset(jbrow, 0, n);
    memset(jxrow, 0, n);
#define IN_CHAIN(z) ((z) >= z0 && (z) < z0 + n)
#define LEFT(z) (x0 + (z) - z0)
#define MARK(cx, cz) (*dbv_mk(p, p->mark, (cx), (cz)))
#define ISBAND(cx, cz) (IN_CHAIN(cz) && (cx) - LEFT(cz) >= 0 && (cx) - LEFT(cz) <= 3 && !(MARK(cx, cz) & 16))
#define OUTSIDE(cx, cz) (dbv_rd(p, (cx), (cz)) && !ISBAND((cx), (cz)))
#define ADDUSE(K, RX, RZ, T) do { if (nu < DBV_MAX_USES) { use[nu].kind = (K); use[nu].rx = (RX); use[nu].rz = (RZ); \
        use[nu].turned = (T); nu++; } } while (0)
#define ADDARMS(K, RX, RZ, T) do { int ax_[4], az_[4], o_, m_ = dbv_arms_of((K), ax_, az_, &o_), q_; \
        for (q_ = 0; q_ < m_ && na < 256; q_++) { int dx_ = ax_[q_], dz_ = az_[q_]; \
            if (T) dbv_turn((K) == DK_JCOL_BOTH || (K) == DK_JCOL_A, &dx_, &dz_); \
            armx[na] = (RX) + dx_; armz[na] = (RZ) + dz_; armo[na] = o_; na++; \
            MARK((RX) + dx_, (RZ) + dz_) |= 4; } } while (0)
    /* ---- task diagfix DBVX: crossing templates, tried on rows with road beside and on the chain's end rows */
    {
        static int dbg = -1;
        if (dbg < 0) dbg = env_on("SC3NETMOD_DBVXDBG");
        p->xdbg = dbg;
        p->xbest = 1 << 30;
    }
    for (k = 0; k < n && nxm < 8 && g_dbvx_n && dbvx_on(); k++) {
        int z = z0 + k, a = LEFT(z), t2;
        if (k && k != n - 1 && !dbv_rd(p, a - 1, z) && !dbv_rd(p, a + 4, z)) continue;
        for (t2 = 0; t2 < g_dbvx_n && nxm < 8; t2++) {
            const DbvX *q = &g_dbvx[t2];
            int i2, j2, ok = q->got == q->h && q->nw, dup = 0, outside = 0;
            int miss = 0, mx = 0, mz = 0;
            for (j2 = 0; j2 < q->h && (ok || p->xdbg); j2++)
                for (i2 = 0; i2 < q->w && (ok || p->xdbg); i2++) {
                    char g = q->grid[j2 * q->w + i2];
                    int cx2 = a + q->x0 + i2, cz2 = z + q->z0 + j2, rx2 = DBV_RX(p, cx2, cz2), rz2 = DBV_RZ(p, cx2, cz2);
                    if (g == '-') continue;
                    if (rx2 < p->b.x0 || rz2 < p->b.z0 || rx2 >= p->b.x0 + p->b.w || rz2 >= p->b.z0 + p->b.h) {
                        if (g == 'r') outside = 1;               /* not read: a wider pass decides (as DAV's) */
                        continue;
                    }
                    if ((g == 'r') != (dbv_rd(p, cx2, cz2) != 0)) {
                        if (!miss) { mx = rx2; mz = rz2; }
                        ok = 0; miss++;
                    }
                }
            if (p->xdbg && miss && miss < p->xbest) {         /* SC3NETMOD_DBVXDBG: the nearest miss */
                p->xbest = miss; p->xbid = q->id; p->xbx = mx; p->xbz = mz; p->xba = a; p->xbzz = z;
            }
            if (ok && outside) { p->xout = 1; continue; }
            if (!ok) continue;
            for (m = 0; m < nxm; m++) if (xmt[m] == t2) dup = 1;
            if (dup) continue;
            xmt[nxm] = t2; xma[nxm] = a; xmz[nxm] = z; nxm++;
            for (j2 = 0; j2 < q->h; j2++) {
                int zz = z + q->z0 + j2;
                if (IN_CHAIN(zz)) jxrow[zz - z0] = 1;
                for (i2 = 0; i2 < q->w; i2++)
                    if (q->grid[j2 * q->w + i2] == 'r') MARK(a + q->x0 + i2, zz) |= 2;
            }
        }
    }
    if (p->xdbg && !nxm && p->xbest < (1 << 30))
        logf("dbv: DBVXDBG band axis %d from canonical (%d,%d): no template; nearest %d (%d cell(s) off, first at real "
             "(%d,%d)), anchor canonical (%d,%d)", p->axis, x0, z0, p->xbid, p->xbest, p->xbx, p->xbz, p->xba, p->xbzz);
    /* ---- ends */
    for (e = 1; e >= 0; e--) {
        int z_e = e ? z0 + n - 1 : z0, a_e = LEFT(z_e), kind, sgn = e ? 1 : -1, dx, dz;
        if (jxrow[z_e - z0]) continue;                                   /* task diagfix: inside a crossing template */
        kind = dbv_end_kind(p, z_e, a_e, e, n);
        ekind[e] = kind;                                                 /* task diagfix: DBVCAPCLEAN */
        if (kind == DK_NONE) {
            *why = e ? "bottom end: the roads past the band are not an end this package knows"
                     : "top end: the roads past the band are not an end this package knows";
            dbv_bad(p, DBV_CELLX(-1, 0), DBV_CELLZ(-1, 0));                 /* task dbvtouch: a road beside the end row */
            dbv_bad(p, DBV_CELLX(4, 0), DBV_CELLZ(4, 0));
            return 0;
        }
        if (kind == DK_BEND_X) {
            for (dz = -2; dz <= 0; dz++) {
                int zr = z_e + sgn * dz;
                endrow[zr - z0] = 1;
                for (dx = 1; dx <= dz + 3; dx++) MARK(DBV_CELLX(dx, dz), DBV_CELLZ(dx, dz)) |= 16;
                for (dx = 1; dx < 512 && DBV_RDE(dx, dz); dx++) MARK(DBV_CELLX(dx, dz), DBV_CELLZ(dx, dz)) |= 2;
            }
        } else if (kind == DK_BEND_Z || kind == DK_BEND_ZT) {
            if (kind == DK_BEND_ZT) {                                    /* task avends F2a: the arm is BV's */
                int st2 = DBV_RDE(4, 2) ? 1 : -1;
                for (j = 2; j <= 3; j++)
                    for (dx = st2 > 0 ? 4 : 0; dx > -512 && dx < 512 && DBV_RDE(dx, j); dx += st2)
                        MARK(DBV_CELLX(dx, j), DBV_CELLZ(dx, j)) |= 2;
            }
            for (j = 1; j < 512; j++) {
                int got = 0;
                for (dx = 1; dx <= 3; dx++)
                    if (DBV_RDE(dx, j)) { MARK(DBV_CELLX(dx, j), DBV_CELLZ(dx, j)) |= 2; got = 1; }
                if (!got) break;
            }
        } else if (kind == DK_RAGGED) {                                  /* task avrbtfix: rows past it stay stock */
            endrow[z_e - z0] = 1;
            p->ragged++;
            for (j = 1; j <= 2; j++)
                for (dx = -2; dx <= j + 5; dx++)
                    if (DBV_RDE(dx, j)) MARK(DBV_CELLX(dx, j), DBV_CELLZ(dx, j)) |= 2;
        } else if (kind == DK_STEM) {
            endrow[z_e - z0] = 1;
            ADDUSE(DK_JROW_STEM, a_e, z_e, !e);
            ADDARMS(DK_JROW_STEM, a_e, z_e, !e);
        } else {
            int mindz = 0, maxdz = 0;
            if (!g_dbv_nst[kind]) { *why = "no pieces declared for an end of this kind"; return 0; }
            for (i = 0; i < g_dbv_nst[kind]; i++) {
                if (g_dbv_st[kind][i].dz < mindz) mindz = g_dbv_st[kind][i].dz;
                if (g_dbv_st[kind][i].dz > maxdz) maxdz = g_dbv_st[kind][i].dz;
            }
            ADDUSE(kind, a_e, z_e, !e);
            for (k = 0; k < 1 - mindz; k++) if (IN_CHAIN(z_e - sgn * k)) endrow[z_e - sgn * k - z0] = 1;
            for (j = maxdz + 1; j <= maxdz + 2; j++)          /* the avenue / single road going on: path */
                for (dx = j - 1; dx <= j + 4; dx++)
                    if (DBV_RDE(dx, j)) MARK(DBV_CELLX(dx, j), DBV_CELLZ(dx, j)) |= 2;
            for (j = 1; j <= maxdz; j++)                       /* the claimed rows (the stamp writes them) */
                for (dx = j - 1; dx <= j + 4; dx++)
                    if (DBV_RDE(dx, j)) MARK(DBV_CELLX(dx, j), DBV_CELLZ(dx, j)) |= 2;
            if (kind == DK_BEND135 || kind == DK_BENDAV)       /* task diagfix: the road / avenue the bend turns into */
                for (dx = 4; dx < 512 && DBV_RDE(dx, 0); dx++) MARK(DBV_CELLX(dx, 0), DBV_CELLZ(dx, 0)) |= 2;
            if (kind == DK_BENDAV)
                for (dx = 4; dx < 512 && DBV_RDE(dx, -1); dx++) MARK(DBV_CELLX(dx, -1), DBV_CELLZ(dx, -1)) |= 2;
            if (kind == DK_BENDAVM)                            /* task diagfix: the avenue's two columns going on */
                for (j = 4; j < 512 && (DBV_RDE(2, j) || DBV_RDE(3, j)); j++)          /* (m34l: "touches road") */
                    for (dx = 2; dx <= 3; dx++) if (DBV_RDE(dx, j)) MARK(DBV_CELLX(dx, j), DBV_CELLZ(dx, j)) |= 2;
            if (kind == DK_BENDBV)                             /* task diagfix DBVBBEND: the boulevard's rows: path */
                for (j = 0; j < 3; j++)
                    for (dx = 4 - j; dx < 512 && DBV_RDE(dx, -j); dx++) MARK(DBV_CELLX(dx, -j), DBV_CELLZ(dx, -j)) |= 2;
        }
    }
    /* ---- task diagfix DBVJBV: a boulevard's three rows beside the band (one side or both), anchored on the middle row */
    for (k = 1; k + 1 < n && g_dbv_nst[DK_JBVX] + g_dbv_nst[DK_JBVE] && dbv_jbv_on(); k++) {
        int sd[2], s2, t2, kind2;
        if (endrow[k - 1] || endrow[k] || endrow[k + 1]) continue;
        for (s2 = 0; s2 < 2; s2++) {
            int ok3 = 1, za = z0 + k - 2, zb = z0 + k + 2;
            for (t2 = -1; t2 <= 1 && ok3; t2++) {
                int z = z0 + k + t2, a = LEFT(z);
                ok3 = s2 ? dbv_rd(p, a + 4, z) && dbv_rd(p, a + 5, z) : dbv_rd(p, a - 1, z) && dbv_rd(p, a - 2, z);
            }
            if (ok3 && (s2 ? dbv_rd(p, LEFT(za) + 4, za) || dbv_rd(p, LEFT(zb) + 4, zb)       /* exactly three rows */
                           : dbv_rd(p, LEFT(za) - 1, za) || dbv_rd(p, LEFT(zb) - 1, zb)))
                ok3 = 0;
            sd[s2] = ok3;
        }
        if (!sd[0] && !sd[1]) continue;
        kind2 = sd[0] && sd[1] ? DK_JBVX : DK_JBVE;
        if (kind2 == DK_JBVE && g_dbv_nst[DK_JBVEO]) {          /* the drags' one-cell overshoot past the band's far */
            int ax = LEFT(z0 + k) + (sd[1] ? 0 : 3), az = z0 + k + (sd[1] ? 1 : -1);      /* edge (xsect 44): drawn */
            if (dbv_rd(p, ax, az) && !dbv_rd(p, sd[1] ? ax - 1 : ax + 1, az)) kind2 = DK_JBVEO;   /* by the box */
        }
        if (!g_dbv_nst[kind2]) continue;
        ADDUSE(kind2, LEFT(z0 + k), z0 + k, sd[0] && !sd[1]);
        for (t2 = -1; t2 <= 1; t2++) {
            int z = z0 + k + t2, a = LEFT(z), j2;
            jbrow[k + t2] = 1;
            for (s2 = 0; s2 < 2; s2++)                         /* the boulevard's cells: BV's, path */
                for (j2 = 1; j2 <= 3 && sd[s2]; j2++) {
                    int cx2 = s2 ? a + 3 + j2 : a - j2;
                    if (dbv_rd(p, cx2, z)) MARK(cx2, z) |= 2;
                }
        }
        k += 2;
    }
    /* ---- row roads (W / E arms) */
    for (k = 0; k < n; k++) {
        int z = z0 + k, a = LEFT(z), w, ea, rw, re;
        if (endrow[k] || jbrow[k] || jxrow[k]) continue;
        w = dbv_rd(p, a - 1, z); ea = dbv_rd(p, a + 4, z);
        rw = w && dbv_rd(p, a - 2, z) && !OUTSIDE(a - 1, z + 1) && !OUTSIDE(a - 2, z + 1) && !OUTSIDE(a - 2, z - 1);
        re = ea && dbv_rd(p, a + 5, z) && !OUTSIDE(a + 4, z - 1) && !OUTSIDE(a + 5, z - 1) && !OUTSIDE(a + 5, z + 1);
        sw = se = 0;                                                     /* task dbvtouch: one-cell stubs */
        if (g_dbv_touch > 0 && w && !rw && !dbv_rd(p, a - 2, z) && !OUTSIDE(a - 1, z + 1) && !OUTSIDE(a - 2, z + 1) &&
            !OUTSIDE(a - 2, z - 1) && !OUTSIDE(a, z + 1))
            rw = sw = 1;
        if (g_dbv_touch > 0 && ea && !re && !dbv_rd(p, a + 5, z) && !OUTSIDE(a + 4, z - 1) && !OUTSIDE(a + 5, z - 1) &&
            !OUTSIDE(a + 5, z + 1) && !OUTSIDE(a + 3, z - 1))
            re = se = 1;
        if (dbv_brow_on()) {                                             /* task diagfix: DBVBROW */
            int run, t;                     /* rows with road beside the band, following its edge (row z + t's
                                               side cells are a - 1 + t / a + 4 + t), outside the band */
#define BROAD(cx_, cz_) (dbv_rd_any(p, (cx_), (cz_)) && !ISBAND((cx_), (cz_)))  /* masked touches count as road */
            for (run = 1, t = 1; t < 4 && BROAD(a - 1 - t, z - t); t++) run++;
            for (t = 1; t < 4 && BROAD(a - 1 + t, z + t); t++) run++;
            if (w && run >= 3) rw = sw = 0;
            for (run = 1, t = 1; t < 4 && BROAD(a + 4 - t, z - t); t++) run++;
            for (t = 1; t < 4 && BROAD(a + 4 + t, z + t); t++) run++;
            if (ea && run >= 3) re = se = 0;
#undef BROAD
        }
        if ((w && !rw) || (ea && !re) || !(w || ea)) continue;
        na0 = na;
        if (w && ea) { ADDUSE(DK_JROW_BOTH, a, z, 0); ADDARMS(DK_JROW_BOTH, a, z, 0); }
        else { ADDUSE(DK_JROW_A, a, z, ea); ADDARMS(DK_JROW_A, a, z, ea); }
        for (i = na0; i < na && (sw || se); i++) {                       /* task dbvtouch: the stub's arms */
            if (!dbv_rd(p, armx[i], armz[i])) {                          /* the far cell: no road, no arm */
                MARK(armx[i], armz[i]) &= ~4;
                memmove(&armx[i], &armx[i + 1], (na - i - 1) * sizeof(int));
                memmove(&armz[i], &armz[i + 1], (na - i - 1) * sizeof(int));
                memmove(&armo[i], &armo[i + 1], (na - i - 1) * sizeof(int));
                na--; i--;
            } else if ((sw && armx[i] == a - 1 && armz[i] == z) || (se && armx[i] == a + 4 && armz[i] == z))
                armo[i] = 0x100 | (armx[i] == a - 1 ? 3 : 1);            /* 11225 open toward the band (canonical) */
        }
    }
    /* ---- column roads: N arm above a row's d3, S arm below the row three down (its d0) */
    for (k = 0; k < n; k++) {
        int z = z0 + k, xc = LEFT(z) + 3, zl = z + 3, south, t, bad = 0;
        if (endrow[k] || jxrow[k] || !dbv_rd(p, xc, z - 1) || (MARK(xc, z - 1) & 6)) continue;
        if (!(dbv_rd(p, xc, z - 2) && !OUTSIDE(xc + 1, z - 1) && !OUTSIDE(xc + 1, z - 2) && !OUTSIDE(xc - 1, z - 2)))
            { *why = "road above the band is not a straight single road"; dbv_bad(p, xc, z - 1); return 0; }
        south = IN_CHAIN(zl) && LEFT(zl) == xc && dbv_rd(p, xc, zl + 1) && dbv_rd(p, xc, zl + 2) &&
                !OUTSIDE(xc - 1, zl + 1) && !OUTSIDE(xc - 1, zl + 2) && !OUTSIDE(xc + 1, zl + 2);
        for (t = z; t < z + 4; t++) if (!IN_CHAIN(t) || endrow[t - z0]) bad = 1;
        if (bad) { *why = "a column road inside an end"; dbv_bad(p, xc, z - 1); return 0; }      /* dbvtouch */
        if (south) { ADDUSE(DK_JCOL_BOTH, xc, zl, 0); ADDARMS(DK_JCOL_BOTH, xc, zl, 0); }
        else { ADDUSE(DK_JCOL_A, xc, zl, 1); ADDARMS(DK_JCOL_A, xc, zl, 1); }
    }
    for (k = 0; k < n; k++) {
        int z = z0 + k, xc = LEFT(z), t, bad = 0, dup = 0;
        if (endrow[k] || jxrow[k] || !dbv_rd(p, xc, z + 1) || (MARK(xc, z + 1) & 6)) continue;
        for (i = 0; i < nu; i++) if (use[i].rx == xc && use[i].rz == z) dup = 1;
        if (dup) continue;
        if (!(dbv_rd(p, xc, z + 2) && !OUTSIDE(xc - 1, z + 1) && !OUTSIDE(xc - 1, z + 2) && !OUTSIDE(xc + 1, z + 2)))
            { *why = "road below the band is not a straight single road"; dbv_bad(p, xc, z + 1); return 0; }
        for (t = z - 3; t <= z; t++) if (!IN_CHAIN(t) || endrow[t - z0]) bad = 1;
        if (bad) { *why = "a column road inside an end"; dbv_bad(p, xc, z + 1); return 0; }      /* dbvtouch */
        ADDUSE(DK_JCOL_A, xc, z, 0); ADDARMS(DK_JCOL_A, xc, z, 0);
    }
    /* ---- clean rows besides junction and end rows */
    for (k = 0; k < n; k++) {
        int z = z0 + k, a = LEFT(z), jr = endrow[k] || jbrow[k];        /* diagfix: DBVJBV rows */
        if (jxrow[k]) { nclean++; continue; }                            /* a template's row: a known shape */
        for (i = 0; i < nu && !jr; i++) {
            if (use[i].kind == DK_JROW_BOTH || use[i].kind == DK_JROW_A) jr = use[i].rz == z;
            if (use[i].kind == DK_JCOL_BOTH || use[i].kind == DK_JCOL_A) jr = z >= use[i].rz - 3 && z <= use[i].rz;
        }
        if (jr && endrow[k] && n > 1 && ((k == 0 && dbv_is_cap(ekind[0])) || (k == n - 1 && dbv_is_cap(ekind[1]))) &&
            dbv_capclean_on())                                           /* task diagfix: DBVCAPCLEAN */
            for (jr = 0, i = 0; i < nu && !jr; i++) {                    /* still a junction row: not clean */
                if (use[i].kind == DK_JROW_BOTH || use[i].kind == DK_JROW_A) jr = use[i].rz == z;
                if (use[i].kind == DK_JCOL_BOTH || use[i].kind == DK_JCOL_A) jr = z >= use[i].rz - 3 && z <= use[i].rz;
            }
        if (!jr && !dbv_rd(p, a - 1, z) && !dbv_rd(p, a + 4, z)) nclean++;
    }
    if (nclean < DBV_MIN_CLEAN) {                                        /* task diagfix: say what the rule saw */
        static char wb[96];
        _snprintf(wb, sizeof(wb), "fewer than 3 clean rows (%d clean, end kinds top %d bottom %d)", nclean, ekind[0],
                  ekind[1]);
        wb[sizeof(wb) - 1] = 0;
        *why = wb;
        return 0;
    }
    /* ---- pieces: the band by d, the stamps, the arms */
    for (k = 0; k < n; k++) {
        int z = z0 + k, a = LEFT(z), d;
        for (d = 0; d < 4; d++) {
            static const BYTE ST[4] = { 2, 2, 0, 0 };
            if (MARK(a + d, z) & 16 || p->n >= DAV_MAX_CELLS) continue;
            p->cell[p->n].x = a + d; p->cell[p->n].z = z;
            p->cell[p->n].want = ((DWORD)(d == 0 || d == 3 ? g_dbv_out : g_dbv_inn) << 8) | ST[d];
            MARK(a + d, z) |= 1 | 32;
            p->n++;
        }
    }
    {                                                                    /* task diagfix DBVX: the templates' cells, */
        int ord[8], spec[8], t3, u3;                                     /* most specific window first; a template */
        for (m = 0; m < nxm; m++) {                                      /* disagreeing with cells already written */
            const DbvX *q = &g_dbvx[xmt[m]];                             /* is a smaller window inside a bigger */
            ord[m] = m; spec[m] = 0;                                     /* shape (a T's inside an L's): skipped */
            for (j = 0; j < q->w * q->h; j++) if (q->grid[j] != '-') spec[m]++;
        }
        for (t3 = 0; t3 < nxm; t3++)
            for (u3 = t3 + 1; u3 < nxm; u3++)
                if (spec[ord[u3]] > spec[ord[t3]]) { int x3 = ord[t3]; ord[t3] = ord[u3]; ord[u3] = x3; }
        for (t3 = 0; t3 < nxm; t3++) {
            const DbvX *q;
            int clash = 0;
            m = ord[t3];
            q = &g_dbvx[xmt[m]];
            for (j = 0; j < q->nw && !clash; j++) {
                const DbvXW *w = &g_dbvxw[q->w0 + j];
                DWORD want = ((DWORD)w->piece << 8) | w->state;
                cx = xma[m] + w->dx; cz = xmz[m] + w->dz;
                if (!dbv_rd(p, cx, cz)) clash = 2;
                else if (*dbv_mk(p, p->owner, cx, cz) >= 200) {
                    for (k = 0; k < p->n; k++)
                        if (p->cell[k].x == cx && p->cell[k].z == cz) break;
                    if (k < p->n && p->cell[k].want != want) clash = 1;
                }
            }
            if (clash) {
                logf("dbv: crossing template %u at canonical (%d,%d) skipped: %s", q->id, xma[m], xmz[m],
                     clash == 2 ? "a cell is not road" : "a more specific template wrote its cells otherwise");
                continue;
            }
            for (j = 0; j < q->nw; j++) {
                const DbvXW *w = &g_dbvxw[q->w0 + j];
                DWORD want = ((DWORD)w->piece << 8) | w->state;
                BYTE *ow;
                int mk;
                cx = xma[m] + w->dx; cz = xmz[m] + w->dz;
                ow = dbv_mk(p, p->owner, cx, cz);
                mk = MARK(cx, cz);
                if (*ow >= 200) continue;                                /* the same piece, written already */
                *ow = (BYTE)(200 + m);
                if (mk & 32) {
                    for (k = 0; k < p->n; k++)
                        if (p->cell[k].x == cx && p->cell[k].z == cz) { p->cell[k].want = want; break; }
                } else if (p->n < DAV_MAX_CELLS) {
                    p->cell[p->n].x = cx; p->cell[p->n].z = cz; p->cell[p->n].want = want;
                    p->n++;
                }
                MARK(cx, cz) |= 8 | 32;
            }
            InterlockedIncrement(&g_dbvx_hits);
        }
    }
    for (i = 0; i < nu; i++) {
        int kind = use[i].kind, col = kind == DK_JCOL_BOTH || kind == DK_JCOL_A;
        if (!g_dbv_nst[kind]) { *why = "no pieces declared for a junction of this kind"; return 0; }
        for (j = 0; j < g_dbv_nst[kind]; j++) {
            DbvStamp *s = &g_dbv_st[kind][j];
            int dx = s->dx, dz = s->dz, st = s->state, m;
            BYTE *ow;
            if (use[i].turned) { dbv_turn(col, &dx, &dz); st = (st + 2) & 3; }
            cx = use[i].rx + dx; cz = use[i].rz + dz;
            ow = dbv_mk(p, p->owner, cx, cz);
            if (*ow && *ow != i + 1) { *why = "junctions or ends too close together"; return 0; }
            *ow = (BYTE)(i + 1);
            if (!dbv_rd(p, cx, cz)) { *why = "a stamp cell is not road"; return 0; }
            m = MARK(cx, cz);
            if (m & 32) {                                      /* replace the band default */
                for (k = 0; k < p->n; k++)
                    if (p->cell[k].x == cx && p->cell[k].z == cz) { p->cell[k].want = ((DWORD)s->piece << 8) | st; break; }
            } else if (p->n < DAV_MAX_CELLS) {
                p->cell[p->n].x = cx; p->cell[p->n].z = cz; p->cell[p->n].want = ((DWORD)s->piece << 8) | st;
                p->n++;
            }
            MARK(cx, cz) |= 8 | 32;
        }
    }
    for (i = 0; i < na; i++) {
        if (MARK(armx[i], armz[i]) & 33 || *dbv_mk(p, p->owner, armx[i], armz[i])) { *why = "an arm cell inside the band"; return 0; }
        if (p->n < DAV_MAX_CELLS) {
            p->cell[p->n].x = armx[i]; p->cell[p->n].z = armz[i];
            p->cell[p->n].want = armo[i] & 0x100 ? ((DWORD)11225 << 8) | (armo[i] & 3) : ((DWORD)29 << 8) | armo[i];
            if (armo[i] & 0x100) p->nstub++;                             /* task dbvtouch */
            p->n++;
        }
    }
    /* ---- isolated */
    for (k = 0; k < p->n; k++) {
        int dx, dz, c0x = p->cell[k].x, c0z = p->cell[k].z;
        if (((p->cell[k].want >> 8) == 29 || (p->cell[k].want >> 8) == 11225) && (MARK(c0x, c0z) & 4)) continue;
        for (dx = -1; dx <= 1; dx++)
            for (dz = -1; dz <= 1; dz++) {
                int qx = c0x + dx, qz = c0z + dz;
                if (dbv_rd(p, qx, qz) && !(MARK(qx, qz) & (32 | 2 | 4))) {
                    *why = "touches road";
                    if (g_dbv_touch <= 0) return 0;
                    dbv_bad(p, qx, qz); tbad = 1;                        /* task dbvtouch: collect every touch */
                }
            }
    }
    if (tbad) return 0;
#undef IN_CHAIN
#undef LEFT
#undef MARK
#undef ISBAND
#undef OUTSIDE
#undef ADDUSE
#undef ADDARMS
    return 1;
}

static void dbv_clear(DbvPass *p) {
    /* every mark of the last chain (its ends reach rows away, a bend's straight runs any distance) */
    ZeroMemory(p->mark, (SIZE_T)p->b.w * p->b.h);
    ZeroMemory(p->owner, (SIZE_T)p->b.w * p->b.h);
}

/* task dbvtouch: dbv_band, judged again with the touching cells it names masked (they stay masked until dbv_unmask,
   so the caller writes the band against the same buffer); *ntry = the masked tries */
static int dbv_band_t(DbvPass *p, int x0, int z0, int n, const char **why, int *ntry) {
    int t = 0, ok;
    p->nbad = 0;
    for (;;) {
        ok = dbv_band(p, x0, z0, n, why);
        if (!ok && p->nbad && g_dbv_touch > 0 && t < DBV_TOUCH_TRIES)   /* task diagfix: why the try was refused */
            logf("dbv: band axis %d from canonical (%d,%d): try %d refused (%s), masking the touching road", p->axis, x0, z0,
                 t + 1, *why);
        if (ok || g_dbv_touch <= 0 || !p->nbad || t >= DBV_TOUCH_TRIES) break;
        dbv_clear(p);
        if (!dbv_mask(p)) break;
        t++;
    }
    p->nbad = 0;
    if (ntry) *ntry = t;
    return ok;
}

/* task avslow: DBVGROW (see dbv_run). The read-window sides (1 x0, 2 z0, 4 x1, 8 z1) a real cell is on or one in
   from, 0 none (the old border test, per side) */
static int g_dbv_grow = -1;
static volatile LONG g_dbv_n_grow, g_dbv_n_full;
static int dbv_bside(const DbvPass *p, int W, int H, int x, int z) {
    int x0 = p->b.x0, z0 = p->b.z0, x1 = p->b.x0 + p->b.w - 1, z1 = p->b.z0 + p->b.h - 1;
    return (x <= x0 + 1 && x0 > 0 ? 1 : 0) | (z <= z0 + 1 && z0 > 0 ? 2 : 0) | (x >= x1 - 1 && x1 < W - 1 ? 4 : 0) |
           (z >= z1 - 1 && z1 < H - 1 ? 8 : 0);
}

/* task avslow: does the window cut a diagonal boulevard? Dry run of dbv_pass's band scan, nothing written: the sides
   reached by (1) an accepted band (the old border test), (2) a chain of 2+ rows holding DBV pieces (the cut part
   of a band can fail them: too few clean rows, an end outside; the old pass then reverted its pieces, the owner's
   "diagonal boulevard torn down by a road placed elsewhere"), (3) any DBV piece on the border ring. */
static int dbv_cut_sides(DbvPass *P, int W, int H) {
    int axis, k, j, sides = 0, x, z;
    int x0 = P->b.x0, z0 = P->b.z0, x1 = P->b.x0 + P->b.w - 1, z1 = P->b.z0 + P->b.h - 1;
    for (axis = 0; axis < 2; axis++) {
        int cx0 = axis ? z0 : x0, cx1 = axis ? z1 : x1, cz0 = axis ? -x1 - 1 : z0, cz1 = axis ? -x0 - 1 : z1, cx, cz;
        P->axis = axis;
        for (cz = cz0; cz <= cz1; cz++)
            for (cx = cx0; cx <= cx1; cx++) {
                const char *why = "";
                int n = 0, clean = 0, sd = 0;
                dbv_unmask(P);                                 /* task dbvtouch: the last band's mask */
                if (!dbv_full(P, cx, cz) || dbv_full(P, cx - 1, cz - 1)) continue;
                while (dbv_full(P, cx + n, cz + n) && n < DBV_MAX_ROWS) n++;
                for (k = 0; k < n; k++)
                    clean += !dbv_rd(P, cx + k - 1, cz + k) && !dbv_rd(P, cx + k + 4, cz + k);
                if (n >= 2) {                                  /* (2) counts only a chain holding our pieces */
                    int ours = 0, cd = 0;
                    for (k = 0; k < n; k++)
                        for (j = 0; j < 4; j++) {
                            int rx = DBV_RX(P, cx + k + j, cz + k), rz = DBV_RZ(P, cx + k + j, cz + k);
                            cd |= dbv_bside(P, W, H, rx, rz);
                            ours |= dbv_is_piece((WORD)(rb_at(&P->b, rx, rz) & 0xffff));
                        }
                    if (ours) sd |= cd;
                }
                if (clean >= DBV_MIN_CLEAN) {
                    if (dbv_band_t(P, cx, cz, n, &why, NULL))   /* task dbvtouch */
                        for (k = 0; k < P->n; k++)
                            sd |= dbv_bside(P, W, H, DBV_RX(P, P->cell[k].x, P->cell[k].z),
                                            DBV_RZ(P, P->cell[k].x, P->cell[k].z));
                    dbv_clear(P);
                }
                sides |= sd;
            }
    }
    dbv_unmask(P);                                                 /* task dbvtouch */
    for (z = z0; z <= z1; z++)                                     /* (3): the ring only */
        for (x = x0; x <= x1; x++) {
            int sd = dbv_bside(P, W, H, x, z);
            if (sd & ~sides) {
                DWORD v = rb_at(&P->b, x, z);
                if (v && dbv_is_piece((WORD)(v & 0xffff))) sides |= sd;
            }
            if (!sd && x1 - 2 > x) x = x1 - 2;                      /* skip the inside of the row */
        }
    return sides;
}

/* -> 1 when an accepted band reached the read border (the caller re-runs it over the whole map); task avslow: with
   psides and DBVGROW on, -> 1 when dbv_cut_sides finds a cut, before any write or revert (*psides = the sides) */
static int dbv_pass(BYTE *mgr, int x0, int z0, int x1, int z1, int W, int H, const char *who, BYTE *keep, int *psides) {
    void *lay = *(void **)(mgr + 0x3c);
    DbvPass P;
    BYTE *mem;
    SIZE_T nbuf;
    int axis, x, z, k, border = 0, nb = 0, nwall = 0, nrev = 0;
    P.b.x0 = x0; P.b.z0 = z0; P.b.w = x1 - x0 + 1; P.b.h = z1 - z0 + 1;
    nbuf = (SIZE_T)P.b.w * P.b.h;
    mem = (BYTE *)VirtualAlloc(NULL, nbuf * 6 + DAV_MAX_CELLS * sizeof(DbvCell), MEM_COMMIT, PAGE_READWRITE);
    if (!mem) return 0;
    P.b.c = (DWORD *)mem;
    P.mark = mem + nbuf * 4;
    P.owner = P.mark + nbuf;
    P.cell = (DbvCell *)(P.owner + nbuf);
    P.nbad = P.nfor = 0;                                                     /* task dbvtouch */
    if (g_dbv_touch < 0) {
        g_dbv_touch = !env_off("SC3NETMOD_DBVTOUCH");
        logf("dbv: DBVTOUCH %s (SC3NETMOD_DBVTOUCH)", g_dbv_touch ? "on" : "off");
    }
    for (z = 0; z < P.b.h; z++)
        for (x = 0; x < P.b.w; x++) P.b.c[z * P.b.w + x] = rb_read(mgr, lay, x0 + x, z0 + z, W, H);
    if (psides && g_dbv_grow && (*psides = dbv_cut_sides(&P, W, H)) != 0) {     /* task avslow: cut, decide wider */
        VirtualFree(mem, 0, MEM_RELEASE);
        return 1;
    }
    for (axis = 0; axis < 2; axis++) {
        /* canonical box of the read box: axis 1 real (x, z) = canonical (z, -x - 1) */
        int cx0 = axis ? z0 : x0, cx1 = axis ? z1 : x1, cz0 = axis ? -x1 - 1 : z0, cz1 = axis ? -x0 - 1 : z1, cx, cz;
        P.axis = axis;
        for (cz = cz0; cz <= cz1; cz++)
            for (cx = cx0; cx <= cx1; cx++) {
                const char *why = "";
                int n = 0, clean = 0, nw = 0, ntry = 0, nxk = 0;    /* task diagfix: nxk DAVXNET cells kept */
                int okb;                                       /* task diagfix DBVX */
                dbv_unmask(&P);                                /* task dbvtouch: the last band's mask */
                if (!dbv_full(&P, cx, cz) || dbv_full(&P, cx - 1, cz - 1)) continue;
                while (dbv_full(&P, cx + n, cz + n) && n < DBV_MAX_ROWS) n++;
                for (k = 0; k < n; k++)
                    clean += !dbv_rd(&P, cx + k - 1, cz + k) && !dbv_rd(&P, cx + k + 4, cz + k);
                if (clean < DBV_MIN_CLEAN) continue;
                okb = dbv_band_t(&P, cx, cz, n, &why, &ntry);              /* task dbvtouch */
                if (P.xout) { border = 1; dbv_clear(&P); continue; }      /* task diagfix DBVX: a wider read decides */
                if (!okb) {
                    logf("dbv: %s: band axis %d from canonical (%d,%d), %d row(s) left to the stock tiler: %s%s", who, axis,
                         cx, cz, n, why, ntry ? " (DBVTOUCH: still refused with the touching road masked)" : "");
                    dbv_clear(&P);
                    continue;
                }
                for (k = 0; k < P.n; k++) {            /* a band at the read border: seen cut, not written */
                    int rx = DBV_RX(&P, P.cell[k].x, P.cell[k].z), rz = DBV_RZ(&P, P.cell[k].x, P.cell[k].z);
                    if ((rx <= x0 + 1 && x0 > 0) || (rz <= z0 + 1 && z0 > 0) || (rx >= x1 - 1 && x1 < W - 1) ||
                        (rz >= z1 - 1 && z1 < H - 1))
                        break;
                }
                if (k < P.n) { border = 1; dbv_clear(&P); continue; }
                nb++;
                for (k = 0; k < P.n; k++) {
                    int rx = DBV_RX(&P, P.cell[k].x, P.cell[k].z), rz = DBV_RZ(&P, P.cell[k].x, P.cell[k].z), pos[3];
                    DWORD want = (P.cell[k].want & ~0xffUL) | ((P.cell[k].want + axis) & 3), cur = rb_at(&P.b, rx, rz);
                    dbv_claim(rx, rz);
                    if (keep) keep[(rz - z0) * P.b.w + (rx - x0)] = 1;
                    if (dav_xnet(cur)) { nxk++; continue; }     /* task diagfix: a rail / highway crossing stays */
                    if ((((cur & 0xffff) << 8) | ((cur >> 16) & 3)) == want) continue;
                    pos[0] = rx << 8; pos[1] = rz << 8; pos[2] = 0;
                    ((PFN_Put)(g_rb_m + 0x8919))(mgr, 0, lay, pos, want, -1, 8, 0);
                    nw++;
                }
                if (nxk) {                                                   /* task diagfix: DAVXNET */
                    InterlockedExchangeAdd(&g_dav_n_xnet, nxk);
                    if (nw || !strcmp(who, "load"))
                        logf("dbv: %s: band axis %d from canonical (%d,%d): %d rail / highway crossing cell(s) kept "
                             "(DAVXNET)", who, axis, cx, cz, nxk);
                }
                if (ntry) InterlockedIncrement(&g_dbv_n_touch);              /* task dbvtouch */
                if (P.nstub) InterlockedExchangeAdd(&g_dbv_n_stub, P.nstub);
                if (ntry && (nw || !strcmp(who, "load")))
                    logf("dbv: %s: band axis %d from canonical (%d,%d) kept: %d touching road cell(s) left to the stock tiler "
                         "(DBVTOUCH, %d tries)", who, axis, cx, cz, P.nfor, ntry);
                if (nw || !strcmp(who, "load"))
                    logf("dbv: %s: diagonal boulevard axis %d, %d row(s) from canonical (%d,%d), %d cell(s), %d written%s",
                         who, axis, n, cx, cz, P.n, nw, P.ragged == 2 ? ", both ends left to the stock tiler (shape not known)"
                         : P.ragged ? ", one end left to the stock tiler (shape not known)" : "");   /* task avrbtfix */
                nwall += nw;
                dbv_clear(&P);
            }
    }
    dbv_unmask(&P);                                                          /* task dbvtouch */
    /* DBV pieces (one cell in from the read border) that no band kept: back to stock */
    if (keep)
        for (z = z0 + 1; z < z1; z++)
            for (x = x0 + 1; x < x1; x++) {
                DWORD v = rb_at(&P.b, x, z);
                int rect[6];
                if (!v || !dbv_is_piece((WORD)(v & 0xffff)) || keep[(z - z0) * P.b.w + (x - x0)]) continue;
                rect[0] = x << 8; rect[1] = z << 8; rect[2] = 0; rect[3] = x << 8; rect[4] = z << 8; rect[5] = 0;
                ((PFN_Retile)VT(mgr, 0xb0))(mgr, 0, rect, 3);
                nrev++;
                logf("dbv: %s: (%d,%d) diagonal boulevard piece %lu no longer in a band -> stock retile", who, x, z,
                     v & 0xffff);
            }
    VirtualFree(mem, 0, MEM_RELEASE);
    InterlockedExchangeAdd(&g_dbv_n_bands, nb);
    InterlockedExchangeAdd(&g_dbv_n_cells, nwall);
    InterlockedExchangeAdd(&g_dbv_n_rev, nrev);
    return border;
}

/* task avslow (DBVGROW, owner 2026-10-30): the edit box + M is read. A diagonal boulevard the window cut used to be
   decided on its visible part: accepted, every edit near it reverted its cut cells (stock retile each) and then a
   whole-map pass wrote them back; refused (too few clean rows inside, an end outside), its pieces were reverted and no
   whole-map pass followed, so a road placed ~22-26 cells from a band's end tore the band down. Now a window that cuts
   one (dbv_cut_sides) writes nothing and grows on the cut sides, by 64 cells and then doubling, until nothing is cut
   (the whole map at worst). Off: SC3NETMOD_DBVGROW=0 (old way). */
static void dbv_run(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who) {
    int W = (*(int *)(mgr + 0x5c) >> 8) + 1, H = (*(int *)(mgr + 0x60) >> 8) + 1, M = 24, full, sides = 0, step = 64;
    int round;
    BYTE *keep;
    if (!g_dbv_claim) g_dbv_claim = (DWORD *)VirtualAlloc(NULL, DBV_CLAIM * sizeof(DWORD), MEM_COMMIT, PAGE_READWRITE);
    if (g_dbv_claim) { ZeroMemory(g_dbv_claim, DBV_CLAIM * sizeof(DWORD)); g_dbv_nclaim = 0; }
    if (!g_dbv_on || W < 4 || H < 4 || W > 4096 || H > 4096) {
        g_dbv_win[0] = g_dbv_win[1] = 0; g_dbv_win[2] = g_dbv_win[3] = 0x7fffffff;   /* task diagfix: nothing to claim */
        return;
    }
    if (g_dbv_grow < 0) {
        g_dbv_grow = !env_off("SC3NETMOD_DBVGROW");
        logf("dbv: DBVGROW %s (SC3NETMOD_DBVGROW)", g_dbv_grow ? "on" : "off");
    }
    x0 -= M; z0 -= M; x1 += M; z1 += M;
    if (x0 < 0) x0 = 0;
    if (z0 < 0) z0 = 0;
    if (x1 > W - 1) x1 = W - 1;
    if (z1 > H - 1) z1 = H - 1;
    for (round = 0; ; round++) {
        full = x0 == 0 && z0 == 0 && x1 == W - 1 && z1 == H - 1;
        keep = (BYTE *)VirtualAlloc(NULL, (SIZE_T)(x1 - x0 + 1) * (z1 - z0 + 1), MEM_COMMIT, PAGE_READWRITE);
        if (!keep) return;
        if (!dbv_pass(mgr, x0, z0, x1, z1, W, H, who, keep, full ? NULL : &sides) || full) break;
        VirtualFree(keep, 0, MEM_RELEASE);
        if (!g_dbv_grow) {                                                   /* the old way */
            logf("dbv: %s: a diagonal boulevard reached the read border - whole-map pass", who);
            x0 = 0; z0 = 0; x1 = W - 1; z1 = H - 1;
            continue;
        }
        if (!sides) sides = 15;                                              /* never: a cut names its side */
        if (sides & 1) x0 = max(0, x0 - step);
        if (sides & 2) z0 = max(0, z0 - step);
        if (sides & 4) x1 = min(W - 1, x1 + step);
        if (sides & 8) z1 = min(H - 1, z1 + step);
        step *= 2;
        InterlockedIncrement(&g_dbv_n_grow);
        if (x0 == 0 && z0 == 0 && x1 == W - 1 && z1 == H - 1) InterlockedIncrement(&g_dbv_n_full);
        if (round < 12)
            logf("dbv: %s: the window cuts a diagonal boulevard (side%s%s%s%s) - window grown to (%d,%d)-(%d,%d)", who,
                 sides & 1 ? " x-" : "", sides & 2 ? " z-" : "", sides & 4 ? " x+" : "", sides & 8 ? " z+" : "", x0, z0,
                 x1, z1);
    }
    VirtualFree(keep, 0, MEM_RELEASE);
    g_dbv_win[0] = x0; g_dbv_win[1] = z0; g_dbv_win[2] = x1; g_dbv_win[3] = z1;   /* task diagfix: DAVDBVWIN */
    if (full) { g_dbv_win[0] = g_dbv_win[1] = 0; g_dbv_win[2] = g_dbv_win[3] = 0x7fffffff; }
}

static void dbv_stats(void) {
    static LONG last;
    LONG n = g_dbv_n_bands + g_dbv_n_cells + g_dbv_n_rev + g_dbv_n_grow + g_dbv_n_touch;
    if (!g_dbv_on || n == last) return;
    last = n;
    logf("stats: dbv bands seen=%ld, cells written=%ld, cells reverted=%ld, windows grown=%ld (to the whole map %ld), "
         "kept with touching road=%ld, stub arms=%ld", g_dbv_n_bands, g_dbv_n_cells, g_dbv_n_rev, g_dbv_n_grow,
         g_dbv_n_full, g_dbv_n_touch, g_dbv_n_stub);                        /* task avslow, task dbvtouch */
}
