/* sc3netmod_hwdx.c - the HWDX block of sc3netmod.dll (task hwdx, highway program 2026-10-18): a diagonal highway that
 * crosses a straight highway at 45 degrees becomes a skewed cloverleaf (the straight bridges over the diagonal, four
 * loops for the left turns, four outer ramps for the right turns). #included by sc3netmod.c after sc3netmod_hwy.c; runs
 * in rb_hwy() as `hwdx_run(hp);` on hwcore's helpers (sc3netmod_hwy.c header).
 *
 * Geometry, tables, rule and offline twin: re/tools/netmod/hwdx_plan.py, hwdx.py (verify/hwdx/README.md). The tables
 * are generated: sc3netmod_hwdx_tab.h (`py -3.12 -m netmod.hwdx ctab ...`).
 *
 * Frames. A crossing is (O, case, r): O the cell corner where the medians cross, case A (x-z diagonal over a straight
 * along x) or B (x+z diagonal), r quarter turns. World cell = case cell (i, j) turned r times about O with
 * (i, j) -> (-j - 1, i) per step; a piece's state = case state + r + the class's flavour offset (flavour = r & 1: a
 * straight along z uses 73 / the other diagonal family as base, hwdx.base_of). The design is point-symmetric about
 * O, so r and r + 2 place the same pieces: r is kept in {0, 1}.
 *
 * Rule, per highway pass:
 *  - find crossings from the read box: the stock aftermath (two 15149 pairs, band middles, straight cells; measured in
 *    game and by the offline tiler) = FRESH; or any HWDX piece whose (id, state) puts O where the 16 core cells hold
 *    the HWDX core pieces = EXISTING (the box may hold only part of the 20 x 14 interchange: cells outside the box are
 *    read with hwy_read);
 *  - FRESH: the core is written; each quadrant whose joining cells hold the plain stock highway and whose ramp cells
 *    are hwy_free and unclaimed (all inside the read box) is written too. Quadrants are independent: each joins only
 *    its own two carriageways. Where the player's drag ends ON a quadrant's last joining cell of an arm (diagonal or
 *    straight), that cell holds the stock end cap and gets the CAPPED JOIN (g_hwdx_cap: the join with the stock end
 *    face, base = the stock cap, written at the cap's own state; tasks hwcap / hwcap2). An arm that ends earlier
 *    leaves a joining cell empty: that quadrant drops. Nothing is added past the player's drag (owner 2026-10-18,
 *    "never extend": task hwcap's carry-on is gone);
 *  - EXISTING: the core is kept; a quadrant is kept while every one of its ramp cells holds its piece (its joining
 *    cells are re-written if a stock retile put the plain highway back). A player who bulldozes a ramp cell loses
 *    that quadrant (hwy_end reverts the rest); quadrants are only added on a fresh build.
 *  - A stock retile over part of the core may put 15149 / plain pieces back: the core still counts when at least half
 *    of its cells hold our pieces and the rest hold highway.
 * Task hwtdel: cells past the read box are kept (hwy_put past the box keeps a right cell instead of refusing it with a
 * ### line per cell), and a dropped quadrant's cells on the border row / past the box are taken back (hwy_unput).
 * Off: SC3NETMOD_HWDX=0.
 */
#include "sc3netmod_hwdx_tab.h"

#define HWDX_MAXF 32

typedef struct { int ox, oz, cs, r, fresh; } HwdxFound;

static int g_hwdx_off = -1, g_hwdx_capon = 1;
static WORD g_hwdx_lo = 0xffff, g_hwdx_hi;
static volatile LONG g_hwdx_n_new, g_hwdx_n_keep, g_hwdx_n_q, g_hwdx_n_drop;

static void hwdx_cell(int i, int j, int r, int *x, int *z) {
    while (r-- > 0) { int t = i; i = -j - 1; j = t; }
    *x = i; *z = j;
}

static DWORD hwdx_rd(HwyPass *hp, int x, int z) { return hwy_rd(hp, x, z); }       /* task hwtdel: the shared read */

static int hwdx_inbox(HwyPass *hp, int x, int z) {
    return x > hp->x0 && z > hp->z0 && x < hp->x1 && z < hp->z1;
}

static const HwdxCell *hwdx_tab(int cs, int *n) {
    *n = cs ? HWDX_NB : HWDX_NA;
    return cs ? g_hwdx_B : g_hwdx_A;
}

/* expected piece of table cell c at (case, r): id, state; base id (plain stock) */
static WORD hwdx_want(const HwdxCell *c, int r, int *st, WORD *base) {
    int f = r & 1;
    WORD id = g_hwdx_id[c->cls][f];
    if (!id) f = 0, id = g_hwdx_id[c->cls][0];          /* ramp classes: one flavour */
    *st = (c->cs + r + g_hwdx_soff[c->cls][f]) & 3;
    if (base) *base = g_hwdx_base[c->cls][f];
    return id;
}

static int hwdx_after(HwyPass *hp, int ox, int oz, int cs, int r) {
    int k;
    for (k = 0; k < 10; k++) {
        int i = g_hwdx_after[k][0], j = g_hwdx_after[k][1], x, z;
        WORD id;
        if (cs) j = -1 - j;
        hwdx_cell(i, j, r, &x, &z);
        id = hwy_id(hwdx_rd(hp, ox + x, oz + z));
        switch (g_hwdx_after[k][2]) {
            case 0: if (id != 15149) return 0; break;
            case 1: if (id != 11224 && id != 15106) return 0; break;
            default: if (id != 15051 && id != 73) return 0;
        }
    }
    return 1;
}

static int hwdx_hwid(WORD id) {
    return id == 15149 || id == 15051 || id == 73 || id == 11223 || id == 11224 || id == 15052 || id == 15106;
}

/* the core found from one of our pieces: each core cell holds its piece, or any plain / stock-crossing highway piece
 * (a stock retile may have put some cells back), and at least half of them are ours */
static int hwdx_core_ours(HwyPass *hp, int ox, int oz, int cs, int r) {
    int n, k, st, ours = 0, tot = 0;
    const HwdxCell *t = hwdx_tab(cs, &n);
    for (k = 0; k < n && t[k].kind == 0; k++) {
        int x, z;
        DWORD v;
        WORD id = hwdx_want(&t[k], r, &st, NULL);
        hwdx_cell(t[k].i, t[k].j, r, &x, &z);
        v = hwdx_rd(hp, ox + x, oz + z);
        tot++;
        if (hwy_id(v) == id && hwy_st(v) == st) ours++;
        else if (!v || !hwdx_hwid(hwy_id(v))) return 0;
    }
    return ours * 2 >= tot;
}

static void hwdx_add(HwdxFound *f, int *nf, int ox, int oz, int cs, int r, int fresh) {
    int k;
    r &= 1;
    for (k = 0; k < *nf; k++)
        if (f[k].ox == ox && f[k].oz == oz && f[k].cs == cs && f[k].r == r) return;
    if (*nf >= HWDX_MAXF) return;
    f[*nf].ox = ox; f[*nf].oz = oz; f[*nf].cs = cs; f[*nf].r = r; f[*nf].fresh = fresh;
    (*nf)++;
}

/* outward step of the arm a table cell lies on (case frame turned r times): the straight's rows j -1 / 0 run along x,
 * the band is (k + d, k) in case A and (k + d, -1 - k) in case B (task hwcap) */
static void hwdx_arm_step(const HwdxCell *c, const HwdxFound *F, int *sx, int *sz) {
    if (c->j == -1 || c->j == 0) { *sx = c->i >= 0 ? 1 : -1; *sz = 0; }
    else if (!F->cs) *sx = *sz = c->j > 0 ? 1 : -1;
    else { *sx = c->j < 0 ? 1 : -1; *sz = -*sx; }
    hwy_rot(F->r, sx, sz);
}

/* task hwcap: the capped join of a table cell (0 = none), and whether v is the stock cap it stands for: the arm's own
 * end (outward step = the arm's) with the capped join's base id */
static WORD hwdx_capid(const HwdxCell *c, const HwdxFound *F) {
    return g_hwdx_capon ? g_hwdx_cap[c->cls][F->r & 1][0] : 0;
}

static int hwdx_capok(const HwdxCell *c, const HwdxFound *F, DWORD v) {
    int sx, sz, dx, dz;
    if (!hwdx_capid(c, F) || !hwcap_dir(v, &dx, &dz) || hwy_id(v) != g_hwdx_cap[c->cls][F->r & 1][1]) return 0;
    hwdx_arm_step(c, F, &sx, &sz);
    return dx == sx && dz == sz;
}

/* one quadrant: 2 = keep / write it (every ramp cell holds its piece, every joining cell holds its piece, its capped
 * join or the plain stock highway), 1 = buildable on a fresh crossing (ramp cells hold their piece or are free; a
 * joining cell holding the arm's own end cap counts when its class has a capped join), 0 = neither */
static int hwdx_quad(HwyPass *hp, const HwdxFound *F, int q) {
    int n, k, st, ramp_have = 1, can = 1;
    const HwdxCell *t = hwdx_tab(F->cs, &n);
    for (k = 0; k < n; k++) {
        int x, z, mine;
        DWORD v;
        WORD base, id;
        if (t[k].quad != q) continue;
        id = hwdx_want(&t[k], F->r, &st, &base);
        hwdx_cell(t[k].i, t[k].j, F->r, &x, &z);
        x += F->ox; z += F->oz;
        v = hwdx_rd(hp, x, z);
        mine = hwy_id(v) == id && hwy_st(v) == st;
        if (mine) continue;
        if (t[k].kind == 1 && v && hwy_id(v) == hwdx_capid(&t[k], F)) continue;   /* its capped join (task hwcap) */
        if (!hwdx_inbox(hp, x, z) || hwy_claimed(x, z)) return 0;        /* would have to be written */
        if (t[k].kind == 1) {                            /* joins a highway: the plain stock piece there */
            int sym = base == 11224 || base == 15106;
            if (!v || hwcap_is(v)) {                     /* tasks hwcap / hwcap2: the arm ends here or before */
                if (hwdx_capok(&t[k], F, v)) continue;   /* it ends on this cell: the capped join */
                if (F->fresh) logf("hwdx: %s: crossing O (%d,%d) quadrant %d: the arm ends at (%d,%d) (%s), %s", hp->who,
                                   F->ox, F->oz, q, x, z, v ? "end cap" : "no highway",
                                   v ? "no capped join for that cell" : "before the joining cell");
                return 0;
            }
            if (hwy_id(v) != base || (hwy_st(v) != st && !(sym && ((hwy_st(v) ^ st) & 1) == 0))) return 0;
        } else {                                         /* ramp alone */
            ramp_have = 0;
            if (v || !hwy_free(hp, x, z)) can = 0;
        }
    }
    return ramp_have ? 2 : can ? 1 : 0;
}

static void hwdx_write(HwyPass *hp, const HwdxFound *F, int q) {    /* q = 255: the core */
    int n, k, st;
    const HwdxCell *t = hwdx_tab(F->cs, &n);
    for (k = 0; k < n; k++) {
        int x, z;
        WORD id;
        if (t[k].quad != q) continue;
        id = hwdx_want(&t[k], F->r, &st, NULL);
        hwdx_cell(t[k].i, t[k].j, F->r, &x, &z);
        if (t[k].kind == 1) {                            /* tasks hwcap / hwcap2: the arm ends on it -> its capped join */
            DWORD v = hwdx_rd(hp, F->ox + x, F->oz + z);
            if (v && (hwy_id(v) == hwdx_capid(&t[k], F) || hwdx_capok(&t[k], F, v))) {
                id = hwdx_capid(&t[k], F);
                st = hwy_st(v);
            }
        }
        if (hwy_put(hp, F->ox + x, F->oz + z, id, st) < 0)
            logf("### hwdx: %s: cell (%d,%d) refused piece %u.%d", hp->who, F->ox + x, F->oz + z, id, st);
    }
}

static void hwdx_run(HwyPass *hp) {
    HwdxFound F[HWDX_MAXF];
    int nf = 0, x, z, k, cs, r, q;
    if (g_hwdx_off < 0) {
        g_hwdx_off = env_off("SC3NETMOD_HWDX");
        for (k = 0; k < HWDX_NCLS; k++) {
            int f;
            for (f = 0; f < 2; f++) {
                WORD id = g_hwdx_id[k][f];
                if (!id) continue;
                if (hwy_piece(id) < 0) { logf("### hwdx: piece %u is not declared (hwyp) - HWDX off", id); g_hwdx_off = 1; }
                if (id < g_hwdx_lo) g_hwdx_lo = id;
                if (id > g_hwdx_hi) g_hwdx_hi = id;
            }
        }
        for (k = 0; k < HWDX_NCLS && g_hwdx_capon; k++)  /* task hwcap: an older package without the capped joins */
            if ((g_hwdx_cap[k][0][0] && hwy_piece(g_hwdx_cap[k][0][0]) < 0) ||
                (g_hwdx_cap[k][1][0] && hwy_piece(g_hwdx_cap[k][1][0]) < 0)) {
                logf("hwdx: capped joins not declared (package older than task hwcap2) - an arm ending on a joining cell "
                     "drops its quadrant");
                g_hwdx_capon = 0;
            }
        logf("hwdx: %s (%d classes, ids %u..%u)", g_hwdx_off ? "off" : "on", HWDX_NCLS, g_hwdx_lo, g_hwdx_hi);
    }
    if (g_hwdx_off) return;
    for (z = hp->z0; z <= hp->z1; z++)
        for (x = hp->x0; x <= hp->x1; x++) {
            DWORD v = hwy_at(hp, x, z);
            WORD id = hwy_id(v);
            if (!v) continue;
            if (id == 15149) {                           /* the stock aftermath: try each 15149 role */
                for (cs = 0; cs < 2; cs++)
                    for (r = 0; r < 4; r++)
                        for (k = 0; k < 10; k++) {
                            int i = g_hwdx_after[k][0], j = g_hwdx_after[k][1], dx, dz;
                            if (g_hwdx_after[k][2]) continue;
                            if (cs) j = -1 - j;
                            hwdx_cell(i, j, r, &dx, &dz);
                            if (hwdx_after(hp, x - dx, z - dz, cs, r)) hwdx_add(F, &nf, x - dx, z - dz, cs, r, 1);
                        }
            } else if (id >= g_hwdx_lo && id <= g_hwdx_hi && !(nf && hwy_claimed(x, z))) {
                for (cs = 0; cs < 2; cs++) {             /* our piece: where would O be? */
                    int n, st;
                    const HwdxCell *t = hwdx_tab(cs, &n);
                    for (k = 0; k < n; k++)
                        for (r = 0; r < 2; r++) {
                            int dx, dz;
                            if (hwdx_want(&t[k], r, &st, NULL) != id || st != hwy_st(v)) continue;
                            hwdx_cell(t[k].i, t[k].j, r, &dx, &dz);
                            if (hwdx_core_ours(hp, x - dx, z - dz, cs, r))
                                hwdx_add(F, &nf, x - dx, z - dz, cs, r, 0);
                        }
                }
            }
        }
    for (k = 0; k < nf; k++) {
        HwdxFound *f = &F[k];
        int st[4], n, j, ok = 1;
        const HwdxCell *t = hwdx_tab(f->cs, &n);
        if (f->fresh)
            for (j = 0; j < n && t[j].kind == 0; j++) {  /* the core: unclaimed */
                int cx, cz;
                hwdx_cell(t[j].i, t[j].j, f->r, &cx, &cz);
                if (hwy_claimed(f->ox + cx, f->oz + cz)) ok = 0;
            }
        if (!ok) continue;
        for (q = 0; q < 4; q++) {
            st[q] = hwdx_quad(hp, f, q);
        }
        if (f->fresh) {                                  /* task hwask: the player decides for every buildable quadrant */
            int nr = 0;
            for (j = 0; j < n; j++) nr += t[j].quad < 4 && st[t[j].quad] == 1 && t[j].kind == 2;
            if (nr && !hwask_ok(hp, HWASK_DX, f->ox, f->oz, f->r, 15149, nr))
                for (q = 0; q < 4; q++) if (st[q] == 1) st[q] = 0;
        }
        hwdx_write(hp, f, 255);
        for (q = 0; q < 4; q++) {
            if (st[q] == 2 || (f->fresh && st[q] == 1)) {
                hwdx_write(hp, f, q);
                InterlockedIncrement(&g_hwdx_n_q);
            } else if (!f->fresh) {
                InterlockedIncrement(&g_hwdx_n_drop);
                for (j = 0; j < n; j++) {                /* task hwtdel: its cells on the border row / past the box too */
                    int cx, cz, cst;
                    WORD cid;
                    if (t[j].quad != q) continue;
                    cid = hwdx_want(&t[j], f->r, &cst, NULL);
                    hwdx_cell(t[j].i, t[j].j, f->r, &cx, &cz);
                    hwy_unput(hp, f->ox + cx, f->oz + cz, cid, cst);
                    if (t[j].kind == 1) {                /* its capped join */
                        DWORD v = hwdx_rd(hp, f->ox + cx, f->oz + cz);
                        if (v && hwy_id(v) == hwdx_capid(&t[j], f)) hwy_unput(hp, f->ox + cx, f->oz + cz, hwy_id(v), hwy_st(v));
                    }
                }
            }
        }
        InterlockedIncrement(f->fresh ? &g_hwdx_n_new : &g_hwdx_n_keep);
        logf("hwdx: %s: %s crossing O (%d,%d) case %c r %d, quadrants %s%s%s%s", hp->who, f->fresh ? "new" : "kept",
             f->ox, f->oz, f->cs ? 'B' : 'A', f->r,
             st[0] == 2 || (f->fresh && st[0] == 1) ? "A1 " : "", st[1] == 2 || (f->fresh && st[1] == 1) ? "A2 " : "",
             st[2] == 2 || (f->fresh && st[2] == 1) ? "O1 " : "", st[3] == 2 || (f->fresh && st[3] == 1) ? "O2" : "");
    }
}

static void hwdx_stats(void) {
    static LONG last;
    LONG n = g_hwdx_n_new + g_hwdx_n_keep + g_hwdx_n_q + g_hwdx_n_drop;
    if (n == last) return;
    last = n;
    logf("stats: hwdx crossings new=%ld, kept=%ld, quadrants written/kept=%ld, dropped=%ld", g_hwdx_n_new,
         g_hwdx_n_keep, g_hwdx_n_q, g_hwdx_n_drop);
}
