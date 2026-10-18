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
 *            stop); each end but the bends writes its stamp (dbvs lines), the bends write band pieces only
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
#define DBV_KINDS 18
#define DBV_MAX_STAMP 40
#define DBV_MAX_USES 64
#define DBV_MAX_ROWS 1024
#define DBV_CLAIM 32768                      /* claims hash slots (power of two) */

enum { DK_NONE = 0, DK_JROW_BOTH = 1, DK_JROW_A, DK_JROW_STEM, DK_JCOL_BOTH, DK_JCOL_A, DK_NARROW_C, DK_NARROW_A,
       DK_TAPER0, DK_TAPER1, DK_TAPER2, DK_CAP_SQ, DK_CAP_PART, DK_TAPER0S, DK_TAPER1S, DK_TAPER2S, DK_CAP_X4Z3,
       DK_CAP_X4Z4, DK_BEND_X = 100, DK_BEND_Z, DK_STEM };

typedef struct { signed char dx, dz; WORD piece; BYTE state; } DbvStamp;
static DbvStamp g_dbv_st[DBV_KINDS][DBV_MAX_STAMP];
static int g_dbv_nst[DBV_KINDS];
static WORD g_dbv_inn;                       /* g_dbv_out (declared in sc3netmod_rbt.c) != 0: DBV declared */
static DWORD *g_dbv_claim;                    /* claims of the current pass: (x << 12 | z) + 1, open addressing */
static int g_dbv_nclaim;
static volatile LONG g_dbv_n_bands, g_dbv_n_cells, g_dbv_n_rev;

static void dbv_line(const char *path, const char *line) {
    unsigned long k, p, st, o, i;
    long dx, dz;
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
} DbvPass;

#define DBV_RX(p, cx, cz) ((p)->axis ? -(cz) - 1 : (cx))
#define DBV_RZ(p, cx, cz) ((p)->axis ? (cx) : (cz))

static int dbv_rd(DbvPass *p, int cx, int cz) { return rb_at(&p->b, DBV_RX(p, cx, cz), DBV_RZ(p, cx, cz)) != 0; }

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

static int dbv_end_kind(DbvPass *p, int z_e, int a_e, int e, int nrows) {
    unsigned rr[6];
    int j, d, dz, ok;
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
    for (j = 0, ok = 1; j < 5; j++) ok = ok && rr[j] == R012;
    if (ok) return DK_NARROW_C;
    if (rr[0] == R123 && rr[1] == R123 && rr[2] == R123) return DK_NARROW_A;
    for (d = 0; d <= 2; d++) if (rr[0] == (DM(d) | DM(d + 1)) && rr[1] == rr[0]) return DK_TAPER0 + d;
    if (rr[0] == R012 && rr[1] == (DM(0) | DM(1)) && rr[2] == (DM(0) | DM(1))) return DK_TAPER0S;
    if (rr[0] == R012 && rr[1] == (DM(1) | DM(2)) && rr[2] == (DM(1) | DM(2))) return DK_TAPER1S;
    if (rr[0] == R123 && rr[1] == (DM(2) | DM(3)) && rr[2] == (DM(2) | DM(3))) return DK_TAPER2S;
    if (!rr[0] && DBV_RDE(-1, 0) && DBV_RDE(4, 0)) return DK_STEM;
    if (DBV_RDE(-1, 0) || DBV_RDE(4, 0)) return DK_NONE;
    if (!rr[0] && !rr[1] && !rr[2] && !rr[3] && !rr[4] && !rr[5]) return DK_CAP_SQ;
    if (rr[0] == R012 && !rr[1] && !rr[2] && !rr[3] && !rr[4] && !rr[5]) return DK_CAP_PART;
    if (rr[0] == R012 && rr[1] == (DM(0) | DM(1)) && !rr[2] && !rr[3] && !rr[4] && !rr[5]) return DK_CAP_X4Z3;
    if (rr[0] == R012 && rr[1] == (DM(0) | DM(1)) && rr[2] == DM(0) && !rr[3] && !rr[4] && !rr[5]) return DK_CAP_X4Z4;
    return DK_NONE;
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

/* the rule on one anchored chain (x0, z0, n rows), canonical; -> 1 accepted (cells in p->cell), 0 refused */
static int dbv_band(DbvPass *p, int x0, int z0, int n, const char **why) {
    DbvUse use[DBV_MAX_USES];
    BYTE endrow[DBV_MAX_ROWS];
    int nu = 0, e, k, j, i, cx, cz, nclean = 0, armx[256], armz[256], armo[256], na = 0;
    *why = "";
    p->n = 0;
    memset(endrow, 0, n);
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
    /* ---- ends */
    for (e = 1; e >= 0; e--) {
        int z_e = e ? z0 + n - 1 : z0, a_e = LEFT(z_e), kind = dbv_end_kind(p, z_e, a_e, e, n), sgn = e ? 1 : -1, dx, dz;
        if (kind == DK_NONE) { *why = e ? "bottom end: the roads past the band are not an end this package knows"
                                        : "top end: the roads past the band are not an end this package knows"; return 0; }
        if (kind == DK_BEND_X) {
            for (dz = -2; dz <= 0; dz++) {
                int zr = z_e + sgn * dz;
                endrow[zr - z0] = 1;
                for (dx = 1; dx <= dz + 3; dx++) MARK(DBV_CELLX(dx, dz), DBV_CELLZ(dx, dz)) |= 16;
                for (dx = 1; dx < 512 && DBV_RDE(dx, dz); dx++) MARK(DBV_CELLX(dx, dz), DBV_CELLZ(dx, dz)) |= 2;
            }
        } else if (kind == DK_BEND_Z) {
            for (j = 1; j < 512; j++) {
                int got = 0;
                for (dx = 1; dx <= 3; dx++)
                    if (DBV_RDE(dx, j)) { MARK(DBV_CELLX(dx, j), DBV_CELLZ(dx, j)) |= 2; got = 1; }
                if (!got) break;
            }
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
        }
    }
    /* ---- row roads (W / E arms) */
    for (k = 0; k < n; k++) {
        int z = z0 + k, a = LEFT(z), w, ea, rw, re;
        if (endrow[k]) continue;
        w = dbv_rd(p, a - 1, z); ea = dbv_rd(p, a + 4, z);
        rw = w && dbv_rd(p, a - 2, z) && !OUTSIDE(a - 1, z + 1) && !OUTSIDE(a - 2, z + 1) && !OUTSIDE(a - 2, z - 1);
        re = ea && dbv_rd(p, a + 5, z) && !OUTSIDE(a + 4, z - 1) && !OUTSIDE(a + 5, z - 1) && !OUTSIDE(a + 5, z + 1);
        if ((w && !rw) || (ea && !re) || !(w || ea)) continue;
        if (w && ea) { ADDUSE(DK_JROW_BOTH, a, z, 0); ADDARMS(DK_JROW_BOTH, a, z, 0); }
        else { ADDUSE(DK_JROW_A, a, z, ea); ADDARMS(DK_JROW_A, a, z, ea); }
    }
    /* ---- column roads: N arm above a row's d3, S arm below the row three down (its d0) */
    for (k = 0; k < n; k++) {
        int z = z0 + k, xc = LEFT(z) + 3, zl = z + 3, south, t, bad = 0;
        if (endrow[k] || !dbv_rd(p, xc, z - 1) || (MARK(xc, z - 1) & 6)) continue;
        if (!(dbv_rd(p, xc, z - 2) && !OUTSIDE(xc + 1, z - 1) && !OUTSIDE(xc + 1, z - 2) && !OUTSIDE(xc - 1, z - 2)))
            { *why = "road above the band is not a straight single road"; return 0; }
        south = IN_CHAIN(zl) && LEFT(zl) == xc && dbv_rd(p, xc, zl + 1) && dbv_rd(p, xc, zl + 2) &&
                !OUTSIDE(xc - 1, zl + 1) && !OUTSIDE(xc - 1, zl + 2) && !OUTSIDE(xc + 1, zl + 2);
        for (t = z; t < z + 4; t++) if (!IN_CHAIN(t) || endrow[t - z0]) bad = 1;
        if (bad) { *why = "a column road inside an end"; return 0; }
        if (south) { ADDUSE(DK_JCOL_BOTH, xc, zl, 0); ADDARMS(DK_JCOL_BOTH, xc, zl, 0); }
        else { ADDUSE(DK_JCOL_A, xc, zl, 1); ADDARMS(DK_JCOL_A, xc, zl, 1); }
    }
    for (k = 0; k < n; k++) {
        int z = z0 + k, xc = LEFT(z), t, bad = 0, dup = 0;
        if (endrow[k] || !dbv_rd(p, xc, z + 1) || (MARK(xc, z + 1) & 6)) continue;
        for (i = 0; i < nu; i++) if (use[i].rx == xc && use[i].rz == z) dup = 1;
        if (dup) continue;
        if (!(dbv_rd(p, xc, z + 2) && !OUTSIDE(xc - 1, z + 1) && !OUTSIDE(xc - 1, z + 2) && !OUTSIDE(xc + 1, z + 2)))
            { *why = "road below the band is not a straight single road"; return 0; }
        for (t = z - 3; t <= z; t++) if (!IN_CHAIN(t) || endrow[t - z0]) bad = 1;
        if (bad) { *why = "a column road inside an end"; return 0; }
        ADDUSE(DK_JCOL_A, xc, z, 0); ADDARMS(DK_JCOL_A, xc, z, 0);
    }
    /* ---- clean rows besides junction and end rows */
    for (k = 0; k < n; k++) {
        int z = z0 + k, a = LEFT(z), jr = endrow[k];
        for (i = 0; i < nu && !jr; i++) {
            if (use[i].kind == DK_JROW_BOTH || use[i].kind == DK_JROW_A) jr = use[i].rz == z;
            if (use[i].kind == DK_JCOL_BOTH || use[i].kind == DK_JCOL_A) jr = z >= use[i].rz - 3 && z <= use[i].rz;
        }
        if (!jr && !dbv_rd(p, a - 1, z) && !dbv_rd(p, a + 4, z)) nclean++;
    }
    if (nclean < DBV_MIN_CLEAN) { *why = "fewer than 3 clean rows"; return 0; }
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
            p->cell[p->n].x = armx[i]; p->cell[p->n].z = armz[i]; p->cell[p->n].want = ((DWORD)29 << 8) | armo[i];
            p->n++;
        }
    }
    /* ---- isolated */
    for (k = 0; k < p->n; k++) {
        int dx, dz, c0x = p->cell[k].x, c0z = p->cell[k].z;
        if ((p->cell[k].want >> 8) == 29 && (MARK(c0x, c0z) & 4)) continue;
        for (dx = -1; dx <= 1; dx++)
            for (dz = -1; dz <= 1; dz++) {
                int qx = c0x + dx, qz = c0z + dz;
                if (dbv_rd(p, qx, qz) && !(MARK(qx, qz) & (32 | 2 | 4))) { *why = "touches road"; return 0; }
            }
    }
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

/* -> 1 when an accepted band reached the read border (the caller re-runs it over the whole map) */
static int dbv_pass(BYTE *mgr, int x0, int z0, int x1, int z1, int W, int H, const char *who, BYTE *keep) {
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
    for (z = 0; z < P.b.h; z++)
        for (x = 0; x < P.b.w; x++) P.b.c[z * P.b.w + x] = rb_read(mgr, lay, x0 + x, z0 + z, W, H);
    for (axis = 0; axis < 2; axis++) {
        /* canonical box of the read box: axis 1 real (x, z) = canonical (z, -x - 1) */
        int cx0 = axis ? z0 : x0, cx1 = axis ? z1 : x1, cz0 = axis ? -x1 - 1 : z0, cz1 = axis ? -x0 - 1 : z1, cx, cz;
        P.axis = axis;
        for (cz = cz0; cz <= cz1; cz++)
            for (cx = cx0; cx <= cx1; cx++) {
                const char *why = "";
                int n = 0, clean = 0, nw = 0;
                if (!dbv_full(&P, cx, cz) || dbv_full(&P, cx - 1, cz - 1)) continue;
                while (dbv_full(&P, cx + n, cz + n) && n < DBV_MAX_ROWS) n++;
                for (k = 0; k < n; k++)
                    clean += !dbv_rd(&P, cx + k - 1, cz + k) && !dbv_rd(&P, cx + k + 4, cz + k);
                if (clean < DBV_MIN_CLEAN) continue;
                if (!dbv_band(&P, cx, cz, n, &why)) {
                    logf("dbv: %s: band axis %d from canonical (%d,%d), %d row(s) left to the stock tiler: %s", who, axis,
                         cx, cz, n, why);
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
                    if ((((cur & 0xffff) << 8) | ((cur >> 16) & 3)) == want) continue;
                    pos[0] = rx << 8; pos[1] = rz << 8; pos[2] = 0;
                    ((PFN_Put)(g_rb_m + 0x8919))(mgr, 0, lay, pos, want, -1, 8, 0);
                    nw++;
                }
                if (nw || !strcmp(who, "load"))
                    logf("dbv: %s: diagonal boulevard axis %d, %d row(s) from canonical (%d,%d), %d cell(s), %d written",
                         who, axis, n, cx, cz, P.n, nw);
                nwall += nw;
                dbv_clear(&P);
            }
    }
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

static void dbv_run(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who) {
    int W = (*(int *)(mgr + 0x5c) >> 8) + 1, H = (*(int *)(mgr + 0x60) >> 8) + 1, M = 24, full;
    BYTE *keep;
    if (!g_dbv_claim) g_dbv_claim = (DWORD *)VirtualAlloc(NULL, DBV_CLAIM * sizeof(DWORD), MEM_COMMIT, PAGE_READWRITE);
    if (g_dbv_claim) { ZeroMemory(g_dbv_claim, DBV_CLAIM * sizeof(DWORD)); g_dbv_nclaim = 0; }
    if (!g_dbv_on || W < 4 || H < 4 || W > 4096 || H > 4096) return;
    x0 -= M; z0 -= M; x1 += M; z1 += M;
    if (x0 < 0) x0 = 0;
    if (z0 < 0) z0 = 0;
    if (x1 > W - 1) x1 = W - 1;
    if (z1 > H - 1) z1 = H - 1;
    full = x0 == 0 && z0 == 0 && x1 == W - 1 && z1 == H - 1;
    keep = (BYTE *)VirtualAlloc(NULL, (SIZE_T)(x1 - x0 + 1) * (z1 - z0 + 1), MEM_COMMIT, PAGE_READWRITE);
    if (!keep) return;
    if (dbv_pass(mgr, x0, z0, x1, z1, W, H, who, keep) && !full) {
        VirtualFree(keep, 0, MEM_RELEASE);
        logf("dbv: %s: a diagonal boulevard reached the read border - whole-map pass", who);
        keep = (BYTE *)VirtualAlloc(NULL, (SIZE_T)W * H, MEM_COMMIT, PAGE_READWRITE);
        if (!keep) return;
        dbv_pass(mgr, 0, 0, W - 1, H - 1, W, H, who, keep);
    }
    VirtualFree(keep, 0, MEM_RELEASE);
}

static void dbv_stats(void) {
    static LONG last;
    LONG n = g_dbv_n_bands + g_dbv_n_cells + g_dbv_n_rev;
    if (!g_dbv_on || n == last) return;
    last = n;
    logf("stats: dbv bands seen=%ld, cells written=%ld, cells reverted=%ld", g_dbv_n_bands, g_dbv_n_cells, g_dbv_n_rev);
}
