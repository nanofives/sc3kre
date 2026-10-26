/* sc3netmod_avx.c - the AVX block of sc3netmod.dll: junction boxes on straight avenues (task avx, 2026-10-17),
 * reworked for one-way avenues (task avjunc, 2026-10-19). #included by sc3netmod.c after the DAV block; runs on RBT's
 * retile-pass and city-load hooks: avx_run before avcore's AVL block, avx_post in avcore's post-AVL phase (slot
 * AVL_POST_AVX: once, after the last avl_run and every other stream's put-back). Offline twin:
 * re/tools/netmod/avjunc_rule.py (the rule), avjunc.py (lanes), avjunc_build.py (package); plan verify/avjunc/PLAN.md;
 * conventions re/analysis/AVENUE_LANES.md (avcore).
 *
 * Table lines (package avenue_junctions, netpack key avenue_junction_lines):
 *   avxm <piece> <outline> <modes>   a box cell piece at state 0, per side N E S W: outline I (another box cell),
 *                                    A (an arm), C (closed); modes I (2 lanes in), O (2 out), T (two-way), C
 *   avxn <piece> <ends> <oneway> [<link>]  a half cell next to a box (base 11204, at the half's 11204 state): ends =
 *                                    4 digits N E S W at state 0, 1 where the median nose is; oneway 1 = avcore's
 *                                    one-way lanes; link 1 = written on a LINK cell of a segment (a stock T / X joining
 *                                    the halves): kept apart so a reloaded layout segments as the stock one did (a nose
 *                                    on a straight pair stays a band row, a link nose stays a link)
 *   avxk <piece> <outline> <modes>   corner junctions (2026-10-19): the OUTER cell of an avenue corner (avcore's inner
 *                                    bend diagonal to it, the two halves beside it) that is a stock T 39 / X 43 with
 *                                    plain roads (29) leaving its outside: the avenue turns through it on both lanes,
 *                                    the road keeps two-way lanes (twin avjunc_rule.corner_at). Written one-way;
 *                                    avx_post puts the stock T / X back when avcore leaves the bands two-way
 * The rule (twin avjunc_rule.find), sides N E S W, "road" = a ROAD cell:
 *   straight pair  the two halves side by side, each 11204 / avcore's straight / our nose piece, in its half state
 *                  (along x: (x, z) state 2 + (x, z + 1) state 0; along z: (x, z) state 1 + (x + 1, z) state 3)
 *   segment        the positions along a band from a straight pair to the next one (at most AVX_MAXSEG), both cells
 *                  road; a foreign variant (another block's) refuses it
 *   box            a run (1..AVX_MAXRUN) of positions where a half connects (both cells' arms) to a road cell on its
 *                  outside, both halves; two such arms at consecutive positions on one side whose cells, up to 3 cells
 *                  out over links / crossings, are a straight pair of the other axis = a crossing avenue span
 *   noses          the straight pairs beside a box, and the plain link positions (29 / 39 / 43) chained to it
 *   modes          along edge inside the box: the row flow (the half's direction); outside the box: the band arm
 *                  (one-way by the half's direction), a road (T) or C; outside edge: a span (one-way by the crossing
 *                  half's direction), a road (T) or C; median edge: the span column's flow, else T (the opening)
 *   validation     a box whose edges do not meet its neighbours' (every band one-way) is left stock; repeat
 *   pieces         every combination of the box's avenue arms one-way / two-way must have a declared piece, else
 *                  the box is left stock (avcore then keeps those bands two-way: their end is a stock piece)
 * avx_run writes every box with all its avenue arms one-way and declared one-way noses (AVENUE_LANES.md 5: the
 * letters avcore reads to end a band on them). avcore decides the bands. avx_post then reads avl_dir() past each arm
 * (over our noses): an arm whose band is not one-way turns two-way (its edges T, the row / column flow kept while another
 * arm of that row / column is one-way), its noses two-way (link noses back to stock), and it rewrites every box and nose
 * cell (a revert retile in avcore's pass can reach them). Without the AVL block every arm is two-way at once.
 * Write = FUN_10008919 per cell; reverts = the rect retile FUN_100151f1 before the writes. Save = each piece's base at
 * its own state (43 / 39 / 11203 / 29, noses 11204). Off: SC3NETMOD_AVX=0.
 */

#define AVX_MAXM 128
#define AVX_MAXSEG 6
#define AVX_MAXRUN 4
#define AVX_ROUNDS 6

typedef struct { WORD piece; char ol[4], md[4]; } AvxM;
static AvxM g_avx_m[AVX_MAXM];
static AvxM g_avx_k[8];                                  /* corner junction pieces (avxk) */
static int g_avx_nk;
static WORD g_avx_now[16], g_avx_ntw[16];               /* noses by ends mask (bit N 1, E 2, S 4, W 8) at state 0 */
static WORD g_avx_nowl[16], g_avx_ntwl[16];             /* link noses */
static volatile LONG g_avx_n_j, g_avx_n_cells, g_avx_n_rev, g_avx_n_dem, g_avx_n_drop;
static const signed char AVX_DIR[4][2] = { { 0, -1 }, { 1, 0 }, { 0, 1 }, { -1, 0 } };     /* N E S W */
static int avl_own(WORD id);                             /* task avjunc: sc3netmod_avl.c (avcore) */
static int avl_dir(int x, int z);
static int avl_post_set(int slot, int (*f)(BYTE *, int, int, int, int, const char *, int *));
#define AVX_AVL_POST_SLOT 2                               /* AVL_POST_AVX: once, after avcore's last avl_run */
static int avx_post_hook(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who, int *rbox);

static void avx_line(const char *path, const char *line) {
    unsigned long v, ow, lk = 0;
    char o[8], m[8], e[8];
    int k;
    if (!strncmp(line, "avxn ", 5)) {
        int mk = 0;
        if (sscanf(line + 5, "%lu %4s %lu %lu", &v, e, &ow, &lk) < 3 || !v || v > 0xffff || strlen(e) != 4 || ow > 1 ||
            lk > 1 || g_base[v] != 11204) {
            logf("### avx: %s: bad nose line or piece not a variant of 11204: '%s'", path, line);
            return;
        }
        for (k = 0; k < 4; k++) if (e[k] == '1') mk |= 1 << k;
        if (lk) { if (ow) g_avx_nowl[mk] = (WORD)v; else g_avx_ntwl[mk] = (WORD)v; }
        else if (ow) g_avx_now[mk] = (WORD)v; else g_avx_ntw[mk] = (WORD)v;
        logf("avx: %s: %s%s nose piece %lu, nose ends N E S W %.4s at state 0", path, ow ? "one-way" : "two-way",
             lk ? " link" : "", v, e);
        return;
    }
    if (!strncmp(line, "avxk ", 5)) {
        if (sscanf(line + 5, "%lu %4s %4s", &v, o, m) != 3 || !v || v > 0xffff || strlen(o) != 4 || strlen(m) != 4 ||
            !g_base[v] || g_avx_nk >= 8) {
            logf("### avx: %s: bad corner line, piece not a variant, or too many: '%s'", path, line);
            return;
        }
        g_avx_k[g_avx_nk].piece = (WORD)v;
        memcpy(g_avx_k[g_avx_nk].ol, o, 4);
        memcpy(g_avx_k[g_avx_nk].md, m, 4);
        g_avx_nk++;
        logf("avx: %s: corner junction piece %lu, outline %.4s modes %.4s at state 0", path, v, o, m);
        return;
    }
    if (strncmp(line, "avxm ", 5)) {
        if (!strncmp(line, "avxb ", 5) || !strncmp(line, "avxa ", 5))
            logf("### avx: %s: old AVX line (before task avjunc) ignored: '%s'", path, line);
        return;
    }
    if (sscanf(line + 5, "%lu %4s %4s", &v, o, m) != 3 || !v || v > 0xffff || strlen(o) != 4 || strlen(m) != 4 ||
        !g_base[v]) {
        logf("### avx: %s: bad box line or piece not a variant: '%s'", path, line);
        return;
    }
    for (k = 0; k < 4; k++)
        if (!strchr("IAC", o[k]) || !strchr("IOTC", m[k])) { logf("### avx: %s: bad letters: '%s'", path, line); return; }
    if (g_avx_nbox >= AVX_MAXM) { logf("### avx: %s: too many box pieces - ignored", path); return; }
    if (!g_avx_nbox) avl_post_set(AVX_AVL_POST_SLOT, avx_post_hook);   /* avx_post in avcore's post-AVL phase */
    g_avx_m[g_avx_nbox].piece = (WORD)v;
    memcpy(g_avx_m[g_avx_nbox].ol, o, 4);
    memcpy(g_avx_m[g_avx_nbox].md, m, 4);
    g_avx_nbox++;
}

static int avx_is_box(WORD id) {
    int k;
    if (!id) return 0;
    for (k = 0; k < g_avx_nbox; k++) if (g_avx_m[k].piece == id) return k + 1;
    return 0;
}

static int avx_is_nose(WORD id) {
    int k;
    if (!id) return 0;
    for (k = 0; k < 16; k++) if (g_avx_now[k] == id || g_avx_ntw[k] == id) return 1;
    for (k = 0; k < 16; k++) if (g_avx_nowl[k] == id || g_avx_ntwl[k] == id) return 2;   /* link nose */
    return 0;
}

static int avx_is_corner(WORD id) {
    int k;
    if (!id) return 0;
    for (k = 0; k < g_avx_nk; k++) if (g_avx_k[k].piece == id) return k + 1;
    return 0;
}

static int avx_own(WORD id) { return avx_is_box(id) || avx_is_nose(id) || avx_is_corner(id); }

static WORD avx_save_id(WORD id) { (void)id; return 0; }  /* every piece saves as its base (task avjunc) */

/* ---------------------------------------------------------------- piece facts */
/* stock road pieces' props 310 (SIMNTWRK dir order x- z- x+ z+), verify/avlanes/data/stock_lanes.txt */
static const struct { WORD id; DWORD m; } AVX_STOCK[] = {
    { 29, 0x01040104 }, { 39, 0x309a309a }, { 43, 0x7bde7bde }, { 11203, 0x10081008 }, { 11204, 0x01040104 },
    { 69, 0x01040104 }, { 67, 0x01040104 }, { 11258, 0x21040184 }, { 15098, 0x20842180 }, { 31, 0x20802080 },
    { 32, 0x01040104 }, { 11201, 0x20802080 }, { 11202, 0x01040104 } };

static int avx_stock_arms(WORD b) {                       /* -> arm sides N E S W at state 0 (bits), -1 unknown */
    int k, d, out = 0;
    for (k = 0; k < (int)(sizeof(AVX_STOCK) / sizeof(AVX_STOCK[0])); k++)
        if (AVX_STOCK[k].id == b) {
            for (d = 0; d < 4; d++)
                if ((AVX_STOCK[k].m >> (4 * d)) & 0xf || (AVX_STOCK[k].m >> (16 + 4 * d)) & 0xf) out |= 1 << ((d + 3) & 3);
            return out;
        }
    return -1;
}

static int avx_rotm(int m, int st) { return ((m << st) | (m >> (4 - st))) & 0xf; }

static WORD avx_stock_of(WORD id) {                       /* stock base of a stock piece or of avcore's variant */
    if (id < 20000) return id;
    if (avl_own(id)) return g_base[id];
    return 0;
}

static int avx_avcore_band(WORD id) {
    WORD b = avx_stock_of(id);
    return b == 69 || b == 67 || b == 11258 || b == 15098 || b == 31 || b == 32 || b == 11201 || b == 11202;
}

static int avx_plain(WORD id) { return id == 29 || id == 39 || id == 43 || id == 11204; }

static int avx_foreign(WORD id) { return id >= 20000 && !avx_own(id) && !avl_own(id); }

/* arm sides of a cell value (rb_read), -1 foreign / unknown, 0 none */
static int avx_arms(DWORD v) {
    WORD id = (WORD)(v & 0xffff);
    int st = (int)((v >> 16) & 3), k, a, e;
    if (!v) return 0;
    if ((k = avx_is_box(id)) != 0) {
        for (a = 0, e = 0; e < 4; e++) if (g_avx_m[k - 1].ol[e] != 'C') a |= 1 << e;
        return avx_rotm(a, st);
    }
    if (avx_is_nose(id)) return avx_rotm(0x2 | 0x8, st);  /* E and W at state 0 */
    if ((k = avx_is_corner(id)) != 0) {
        for (a = 0, e = 0; e < 4; e++) if (g_avx_k[k - 1].ol[e] != 'C') a |= 1 << e;
        return avx_rotm(a, st);
    }
    if (!avx_stock_of(id)) return -1;
    a = avx_stock_arms(avx_stock_of(id));
    return a < 0 ? -1 : avx_rotm(a, st);
}

static int avx_is_half(WORD id) { return id == 11204 || (g_avl_straight && id == g_avl_straight) || avx_is_nose(id); }
/* a band row cell: stock 11204, avcore's straight, a nose on a straight pair (NOT a link nose) */
static int avx_is_row(WORD id) { return id == 11204 || (g_avl_straight && id == g_avl_straight) || avx_is_nose(id) == 1; }

/* ---------------------------------------------------------------- one pass */
typedef struct {
    BYTE axis, L, dead, narm;
    int x[AVX_MAXRUN][2], z[AVX_MAXRUN][2];
    char ek[AVX_MAXRUN][2][4];                          /* edge kind: C, R row, K median, B band arm, D road arm, S span */
    signed char span[AVX_MAXRUN][2];                    /* -1 none, 0 first, 1 second half of a crossing span */
    BYTE ak[8], ah[8], ae[8];                            /* arms: kind B (h, side) / S (h, first position) */
    BYTE dem;                                            /* demoted arms (bits) */
} AvxBox;

typedef struct { int x, z, hx, hz, ox, oz; DWORD want, orig; } AvxCorner;   /* corner cell and its two halves */

typedef struct {
    BYTE *mgr; void *lay; int W, H;
    RbBuf b;
    int *own;                                            /* box index + 1 per buffer cell */
    BYTE *link, *nose, *segm;                            /* link: 1 + axis * 2 + h; nose: 1 + axis; segm: seen bits */
    signed char *nst;                                    /* nose state */
    AvxBox *bx; int nb, cap;
    int rx0, rz0, rx1, rz1;                              /* cells a revert may touch: the edit box + 2 (whole map on load) */
    BYTE *kmap;                                          /* 1: a corner junction cell this pass keeps */
    BYTE *virt;                                          /* task avx32: 0x10 | arm sides re-read by avx_caps, 0 none */
    AvxCorner *kc; int nk, kcap;
} AvxPass;

static AvxPass g_avx_p;                                   /* the last avx_run's result, for avx_post */
static int g_avx_have;

static int avx_ix(AvxPass *p, int x, int z) {
    x -= p->b.x0; z -= p->b.z0;
    if (x < 0 || z < 0 || x >= p->b.w || z >= p->b.h) return -1;
    return z * p->b.w + x;
}

static DWORD avx_at(AvxPass *p, int x, int z) { return rb_at(&p->b, x, z); }

/* band geometry: axis 0 = along x, 1 = along z; [axis][h]: h 0 = the x- / z- half, 1 = the other */
static const int AVX_STEP[2][2] = { { 1, 0 }, { 0, 1 } }, AVX_ACROSS[2][2] = { { 0, 1 }, { 1, 0 } };
static const int AVX_OUT[2][2] = { { 0, 2 }, { 3, 1 } }, AVX_HDIR[2][2] = { { 1, 3 }, { 0, 2 } };
static const int AVX_HST[2][2] = { { 2, 0 }, { 1, 3 } }, AVX_PDIR[2][2] = { { 0, 2 }, { 1, 3 } };
static const int AVX_ALONG[2][2] = { { 3, 1 }, { 0, 2 } };

/* task avx32: a cell avx_caps re-reads (its arm sides), 0 none */
static int avx_virt(AvxPass *p, int x, int z) {
    int ix = avx_ix(p, x, z);
    return (ix >= 0 && p->virt && p->virt[ix]) ? p->virt[ix] : 0;
}

static int avx_pair(AvxPass *p, int ax, int az, int axis) {
    DWORD a = avx_at(p, ax, az), b = avx_at(p, ax + AVX_ACROSS[axis][0], az + AVX_ACROSS[axis][1]);
    if (!a || !b || !avx_is_row((WORD)(a & 0xffff)) || !avx_is_row((WORD)(b & 0xffff))) return 0;
    if (avx_virt(p, ax, az) || avx_virt(p, ax + AVX_ACROSS[axis][0], az + AVX_ACROSS[axis][1])) return 0;  /* avx32 */
    return (int)((a >> 16) & 3) == AVX_HST[axis][0] && (int)((b >> 16) & 3) == AVX_HST[axis][1];
}

static int avx_conn(AvxPass *p, int x, int z, int side) {
    int va = avx_virt(p, x, z), vb = avx_virt(p, x + AVX_DIR[side][0], z + AVX_DIR[side][1]);   /* task avx32 */
    int A = va ? (va & 0xf) : avx_arms(avx_at(p, x, z)), B;
    if (A <= 0 || !(A & (1 << side))) return 0;
    B = vb ? (vb & 0xf) : avx_arms(avx_at(p, x + AVX_DIR[side][0], z + AVX_DIR[side][1]));
    return B > 0 && (B & (1 << ((side + 2) & 3)));
}

/* task avx32 (owner hand test 2026-10-21, img8; twin avjunc_rule.cap_links): an avenue crossing an avenue that goes on
   past it as a single road on one column only. The stock tiler caps the other half at the crossing (11203) and joins
   the going-on half with a T 39, so the avenue does not reach the box. Pattern: a straight pair of the crossing avenue,
   then the row {11203, 39} (the T joining back and forward), then the two rows of the through avenue (the cell past
   the cap a half), then road past it in the T's column only. Re-read
   for this pass: the cap and the T as a plain link row (arms back and forward), the cell past the cap with an extra
   arm toward it (and no longer a straight pair). The box then forms as for an avenue x avenue, the going-on road an
   arm (T) on its side. */
static void avx_caps(AvxPass *p, int ox0, int oz0, int ox1, int oz1) {
    int x, z, axis, sg;
    for (z = oz0; z <= oz1; z++)
        for (x = ox0; x <= ox1; x++)
            for (axis = 0; axis < 2; axis++) {
                if (!avx_pair(p, x, z, axis)) continue;
                for (sg = -1; sg <= 1; sg += 2) {
                    int dx = sg * AVX_STEP[axis][0], dz = sg * AVX_STEP[axis][1], fwd, back, ta, a2;
                    int ax = x + dx, az = z + dz, bx = ax + AVX_ACROSS[axis][0], bz = az + AVX_ACROSS[axis][1];
                    int cx, cz, tx, tz, ic, it, i2;
                    DWORD va = avx_at(p, ax, az), vb = avx_at(p, bx, bz), vt, v2;
                    WORD ia = (WORD)(va & 0xffff), ib = (WORD)(vb & 0xffff);
                    if (!va || !vb || !((ia == 11203 && ib == 39) || (ia == 39 && ib == 11203))) continue;
                    if (ia == 11203) { cx = ax; cz = az; tx = bx; tz = bz; vt = vb; }
                    else { cx = bx; cz = bz; tx = ax; tz = az; vt = va; }
                    for (fwd = 0; fwd < 4 && !(AVX_DIR[fwd][0] == dx && AVX_DIR[fwd][1] == dz); fwd++) ;
                    if (fwd == 4) continue;
                    back = (fwd + 2) & 3;
                    ta = avx_arms(vt);
                    if (ta <= 0 || !(ta & (1 << fwd)) || !(ta & (1 << back))) continue;
                    v2 = avx_at(p, cx + dx, cz + dz);
                    if (!v2 || !avx_at(p, tx + dx, tz + dz) || !avx_is_half((WORD)(v2 & 0xffff))) continue;
                    /* past the through avenue (two rows) the road goes on in the T's column only; both columns or
                       none is another shape (an avenue ending on an avenue with a road beside it) */
                    if (!avx_at(p, cx + 2 * dx, cz + 2 * dz) || !avx_at(p, tx + 2 * dx, tz + 2 * dz) ||
                        !avx_at(p, tx + 3 * dx, tz + 3 * dz) || avx_at(p, cx + 3 * dx, cz + 3 * dz)) continue;
                    if ((a2 = avx_arms(v2)) <= 0) continue;
                    ic = avx_ix(p, cx, cz); it = avx_ix(p, tx, tz); i2 = avx_ix(p, cx + dx, cz + dz);
                    if (ic < 0 || it < 0 || i2 < 0) continue;
                    p->virt[ic] = (BYTE)(0x10 | (1 << fwd) | (1 << back));
                    p->virt[it] = (BYTE)(0x10 | (1 << fwd) | (1 << back));
                    p->virt[i2] = (BYTE)(0x10 | a2 | (1 << back));
                }
            }
}

/* task avxroad (owner hand test 2026-10-26, img1; twin avjunc_rule.dropped_tees): two roads meeting an avenue from
   opposite sides one position apart. The stock tiler drops BOTH T's (measured with no netmod loaded: the second road
   turns the first T 39 back to 11204 and never makes its own), so the roads stop at the curbs with an arm pointing into
   a straight half that has none back, no box forms and AVL converts the stretch as plain band. Re-read for this pass:
   a straight half (11204 / avcore's straight) whose outside neighbour is a plain road piece (29 / 39 / 43 / 11203) with
   an arm toward it gets that arm. The two positions then form one box with a road arm on each side (existing box pieces). Off:
   SC3NETMOD_AVXDROP=0. */
static int g_avx_drop = -1;
static volatile LONG g_avx_n_tee;

static void avx_drops(AvxPass *p, int ox0, int oz0, int ox1, int oz1, const char *who) {
    int x, z, n = 0;
    if (g_avx_drop < 0) {
        g_avx_drop = !env_off("SC3NETMOD_AVXDROP");
        logf("avx: dropped-T re-read %s", g_avx_drop ? "on" : "off (SC3NETMOD_AVXDROP=0)");
    }
    if (!g_avx_drop) return;
    for (z = oz0; z <= oz1; z++)
        for (x = ox0; x <= ox1; x++) {
            DWORD v = avx_at(p, x, z), q;
            WORD id = (WORD)(v & 0xffff), qid;
            int st = (int)((v >> 16) & 3), out = (st + 2) & 3, ix = avx_ix(p, x, z), A, B;
            if (!v || ix < 0 || !(id == 11204 || (g_avl_straight && id == g_avl_straight))) continue;
            q = avx_at(p, x + AVX_DIR[out][0], z + AVX_DIR[out][1]);
            qid = (WORD)(q & 0xffff);
            /* plain single-road pieces only: another avenue's half, a rail crossing or a slope abutting the side is
               another shape (shipped cities: 64 of 227 dangling arms, left alone) */
            if (!q || !(qid == 29 || qid == 39 || qid == 43 || qid == 11203)) continue;
            A = p->virt[ix] ? (p->virt[ix] & 0xf) : avx_arms(v);
            B = avx_arms(q);
            if (A <= 0 || (A & (1 << out)) || B <= 0 || !(B & (1 << st))) continue;
            p->virt[ix] = (BYTE)(0x10 | A | (1 << out));
            if (n < 8) logf("avx: %s: (%d,%d) road %u.%d has an arm into the straight half (stock dropped the T) -> read as a T",
                            who, x, z, qid, (int)((q >> 16) & 3));
            n++;
        }
    if (n) InterlockedExchangeAdd(&g_avx_n_tee, n);
}

static int avx_road(AvxPass *p, int x, int z) { return avx_at(p, x, z) != 0; }

static void avx_make(AvxPass *p, int axis, int pos[][2][2], int np, int i0, int i1, AvxBox *bx) {
    int i, h, e, k;
    ZeroMemory(bx, sizeof(*bx));
    bx->axis = (BYTE)axis; bx->L = (BYTE)(i1 - i0 + 1);
    for (i = 0; i < bx->L; i++)
        for (h = 0; h < 2; h++) { bx->x[i][h] = pos[i0 + i][h][0]; bx->z[i][h] = pos[i0 + i][h][1]; bx->span[i][h] = -1; }
    for (h = 0; h < 2; h++) {                             /* crossing avenue spans on each side */
        int side = AVX_OUT[axis][h];
        i = 0;
        while (i < bx->L - 1) {
            int ca[2], cb[2], found = 0;
            ca[0] = bx->x[i][h]; ca[1] = bx->z[i][h]; cb[0] = bx->x[i + 1][h]; cb[1] = bx->z[i + 1][h];
            if (avx_conn(p, ca[0], ca[1], side) && avx_conn(p, cb[0], cb[1], side)) {
                for (k = 1; k <= 3; k++) {
                    int oax = ca[0] + AVX_DIR[side][0] * k, oaz = ca[1] + AVX_DIR[side][1] * k;
                    int obx = cb[0] + AVX_DIR[side][0] * k, obz = cb[1] + AVX_DIR[side][1] * k;
                    DWORD qa, qb;
                    WORD ia, ib;
                    if (avx_pair(p, oax, oaz, axis ^ 1)) { found = 1; break; }
                    qa = avx_at(p, oax, oaz); qb = avx_at(p, obx, obz);
                    ia = (WORD)(qa & 0xffff); ib = (WORD)(qb & 0xffff);
                    if (!qa || !qb || !((avx_plain(ia) || avx_own(ia) || avx_avcore_band(ia) || avx_virt(p, oax, oaz)) &&
                                        (avx_plain(ib) || avx_own(ib) || avx_avcore_band(ib) || avx_virt(p, obx, obz))))
                        break;                                                                           /* avx32 */
                }
            }
            if (found) { bx->span[i][h] = 0; bx->span[i + 1][h] = 1; i += 2; } else i++;
        }
    }
    for (i = 0; i < bx->L; i++)
        for (h = 0; h < 2; h++) {
            int x = bx->x[i][h], z = bx->z[i][h], eo = AVX_OUT[axis][h];
            for (e = 0; e < 4; e++) {
                int nx = x + AVX_DIR[e][0], nz = z + AVX_DIR[e][1];
                char *ek = &bx->ek[i][h][e];
                if (e == AVX_ALONG[axis][0] || e == AVX_ALONG[axis][1]) {
                    int j = e == AVX_ALONG[axis][0] ? i - 1 : i + 1;
                    DWORD q = avx_at(p, nx, nz);
                    if (j >= 0 && j < bx->L) *ek = 'R';
                    else if (!q || !avx_conn(p, x, z, e)) *ek = 'C';
                    else if ((i0 + j >= 0 && i0 + j < np) || avx_is_half((WORD)(q & 0xffff)) ||
                             avx_avcore_band((WORD)(q & 0xffff))) *ek = 'B';
                    else *ek = 'D';
                } else if (e == eo) {
                    if (bx->span[i][h] >= 0) *ek = 'S';
                    else if (avx_conn(p, x, z, e)) *ek = 'D';
                    else *ek = 'C';
                } else *ek = 'K';
            }
        }
    for (i = 0; i < bx->L; i++)                           /* arms: band (h, side), span (h, first position) */
        for (h = 0; h < 2; h++)
            for (e = 0; e < 4; e++) {
                if (bx->ek[i][h][e] == 'B') {
                    for (k = 0; k < bx->narm; k++) if (bx->ak[k] == 'B' && bx->ah[k] == h && bx->ae[k] == e) break;
                    if (k == bx->narm && bx->narm < 8) { bx->ak[k] = 'B'; bx->ah[k] = (BYTE)h; bx->ae[k] = (BYTE)e; bx->narm++; }
                } else if (bx->ek[i][h][e] == 'S' && bx->span[i][h] == 0 && bx->narm < 8) {
                    bx->ak[bx->narm] = 'S'; bx->ah[bx->narm] = (BYTE)h; bx->ae[bx->narm] = (BYTE)i; bx->narm++;
                }
            }
}

/* modes of box cell (i, h) under demotion bits `dem` -> outline + modes N E S W (twin avjunc_rule.box_modes) */
static void avx_modes(AvxBox *bx, BYTE dem, int i, int h, char *ol, char *md) {
    int e, k, axis = bx->axis, row_tw = 1, has_band = 0, col_tw, spi = -1, sph = -1, sides = 0, demd = 0, hh;
    for (k = 0; k < bx->narm; k++)
        if (bx->ak[k] == 'B' && bx->ah[k] == h) { has_band = 1; if (!(dem & (1 << k))) row_tw = 0; }
    if (!has_band) row_tw = 0;
    for (hh = 0; hh < 2; hh++)                            /* the span column: two-way when every span side is demoted */
        if (bx->span[i][hh] >= 0) {
            int first = bx->span[i][hh] == 0 ? i : i - 1;
            sides++;
            if (spi < 0) { spi = i; sph = hh; }
            for (k = 0; k < bx->narm; k++)
                if (bx->ak[k] == 'S' && bx->ah[k] == hh && bx->ae[k] == first && (dem & (1 << k))) demd++;
        }
    col_tw = sides && demd == sides;
    for (e = 0; e < 4; e++) {
        char kd = bx->ek[i][h][e];
        int d, first;
        ol[e] = kd == 'C' ? 'C' : (kd == 'R' || kd == 'K') ? 'I' : 'A';
        switch (kd) {
        case 'C': md[e] = 'C'; break;
        case 'D': md[e] = 'T'; break;
        case 'B':
            for (k = 0; k < bx->narm; k++) if (bx->ak[k] == 'B' && bx->ah[k] == h && bx->ae[k] == e) break;
            if (k < bx->narm && (dem & (1 << k))) { md[e] = 'T'; break; }
            d = AVX_HDIR[axis][h]; md[e] = e == d ? 'O' : 'I'; break;
        case 'S':
            first = bx->span[i][h] == 0 ? i : i - 1;
            for (k = 0; k < bx->narm; k++) if (bx->ak[k] == 'S' && bx->ah[k] == h && bx->ae[k] == first) break;
            if (k < bx->narm && (dem & (1 << k))) { md[e] = 'T'; break; }
            d = AVX_PDIR[axis][bx->span[i][h]]; md[e] = e == d ? 'O' : 'I'; break;
        case 'R':
            if (row_tw) { md[e] = 'T'; break; }
            d = AVX_HDIR[axis][h]; md[e] = e == d ? 'O' : 'I'; break;
        default:                                          /* K: the median edge */
            if (spi < 0 || col_tw) { md[e] = 'T'; break; }
            d = AVX_PDIR[axis][bx->span[spi][sph]]; md[e] = e == d ? 'O' : 'I'; break;
        }
    }
}

/* declared piece and state for an outline + modes (world sides), 0 = none */
static DWORD avx_piece(const char *ol, const char *md) {
    int j, k, e;
    for (j = 0; j < g_avx_nbox; j++)
        for (k = 0; k < 4; k++) {
            for (e = 0; e < 4 && g_avx_m[j].ol[e] == ol[(e + k) & 3] && g_avx_m[j].md[e] == md[(e + k) & 3]; e++) ;
            if (e == 4) return ((DWORD)g_avx_m[j].piece << 8) | (DWORD)k;
        }
    return 0;
}

static int avx_all_pieces(AvxBox *bx) {
    int c, i, h;
    char ol[4], md[4];
    for (c = 0; c < (1 << bx->narm); c++)
        for (i = 0; i < bx->L; i++)
            for (h = 0; h < 2; h++) {
                avx_modes(bx, (BYTE)c, i, h, ol, md);
                if (!avx_piece(ol, md)) return 0;
            }
    return 1;
}

static void avx_half_modes(int st, int oneway, char *md) {
    int d = (st + 3) & 3, e;
    for (e = 0; e < 4; e++) md[e] = 'C';
    md[d] = oneway ? 'O' : 'T'; md[(d + 2) & 3] = oneway ? 'I' : 'T';
}

/* modes, on side e, of a non-box cell: our nose / a half (one-way: validation assumes every band converts),
   avcore's crossing ('?': skipped), a stock piece (T on its arms), nothing (C) */
static char avx_nb_mode(AvxPass *p, int x, int z, int e) {
    DWORD v = avx_at(p, x, z);
    int ix = avx_ix(p, x, z), a;
    char md[4];
    if (!v) return 'C';
    if ((ix >= 0 && p->nose[ix]) || avx_is_half((WORD)(v & 0xffff))) {
        avx_half_modes(ix >= 0 && p->nose[ix] ? p->nst[ix] : (int)((v >> 16) & 3), 1, md);
        return md[e];
    }
    if (avx_avcore_band((WORD)(v & 0xffff))) return '?';
    a = avx_arms(v);
    if (a < 0) return 'X';                                /* unknown connections (a diagonal road piece, ...): refuse */
    return (a & (1 << e)) ? 'T' : 'C';
}

/* noses from the live boxes: straight halves beside a box and the link cells chained to it */
static void avx_noses(AvxPass *p) {
    int t, i, h, s, n = p->b.w * p->b.h;
    ZeroMemory(p->nose, n);
    for (t = 0; t < p->nb; t++) {
        AvxBox *bx = &p->bx[t];
        if (bx->dead) continue;
        for (i = 0; i < bx->L; i++)
            for (h = 0; h < 2; h++)
                for (s = 0; s < 2; s++) {
                    int e = AVX_ALONG[bx->axis][s], x = bx->x[i][h], z = bx->z[i][h], ix;
                    if (bx->ek[i][h][e] != 'B') continue;
                    x += AVX_DIR[e][0]; z += AVX_DIR[e][1];
                    while ((ix = avx_ix(p, x, z)) >= 0 && !p->nose[ix] && !p->own[ix] &&
                           (p->link[ix] || avx_is_nose((WORD)(avx_at(p, x, z) & 0xffff)) == 2)) {
                        /* links and our link noses (nose 3 + axis) */
                        if (p->link[ix]) {
                            p->nose[ix] = (BYTE)(3 + ((p->link[ix] - 1) >> 1));
                            p->nst[ix] = (signed char)AVX_HST[(p->link[ix] - 1) >> 1][(p->link[ix] - 1) & 1];
                        } else {
                            p->nose[ix] = (BYTE)(3 + bx->axis);
                            p->nst[ix] = (signed char)((avx_at(p, x, z) >> 16) & 3);
                        }
                        x += AVX_DIR[e][0]; z += AVX_DIR[e][1];
                    }
                    ix = avx_ix(p, x, z);
                    if (ix >= 0 && !p->own[ix] && !p->nose[ix] && avx_is_row((WORD)(avx_at(p, x, z) & 0xffff))) {
                        p->nose[ix] = (BYTE)(1 + bx->axis);
                        p->nst[ix] = (signed char)((avx_at(p, x, z) >> 16) & 3);
                    }
                }
        for (i = 0; i < bx->L; i++)                       /* the crossing avenue's side: its links and first halves */
            for (h = 0; h < 2; h++) {
                int e = AVX_OUT[bx->axis][h], x = bx->x[i][h], z = bx->z[i][h], ix;
                if (bx->span[i][h] < 0) continue;
                x += AVX_DIR[e][0]; z += AVX_DIR[e][1];
                while ((ix = avx_ix(p, x, z)) >= 0 && !p->nose[ix] && !p->own[ix] &&
                       (p->link[ix] || avx_is_nose((WORD)(avx_at(p, x, z) & 0xffff)) == 2)) {
                    if (p->link[ix]) {
                        p->nose[ix] = (BYTE)(3 + ((p->link[ix] - 1) >> 1));
                        p->nst[ix] = (signed char)AVX_HST[(p->link[ix] - 1) >> 1][(p->link[ix] - 1) & 1];
                    } else {
                        p->nose[ix] = (BYTE)(3 + (bx->axis ^ 1));
                        p->nst[ix] = (signed char)((avx_at(p, x, z) >> 16) & 3);
                    }
                    x += AVX_DIR[e][0]; z += AVX_DIR[e][1];
                }
                ix = avx_ix(p, x, z);
                if (ix >= 0 && !p->own[ix] && !p->nose[ix] && avx_is_row((WORD)(avx_at(p, x, z) & 0xffff))) {
                    p->nose[ix] = (BYTE)(1 + (bx->axis ^ 1));
                    p->nst[ix] = (signed char)((avx_at(p, x, z) >> 16) & 3);
                }
            }
    }
}

static void avx_kill(AvxPass *p, int t) {
    AvxBox *bx = &p->bx[t];
    int i, h, ix;
    bx->dead = 1;
    for (i = 0; i < bx->L; i++)
        for (h = 0; h < 2; h++)
            if ((ix = avx_ix(p, bx->x[i][h], bx->z[i][h])) >= 0 && p->own[ix] == t + 1) p->own[ix] = 0;
}

/* task avx32: a run of 3 positions that BV's own run rule takes as part of a boulevard (bv_takes: bv_run1 as a dry run,
   so AVX and BV share one definition of a boulevard). BV runs after AVX and builds that junction itself (BVX); boxing
   it here first put our nose pieces into the avenue arm, which made BVX refuse the whole boulevard (owner hand test
   2026-10-21, img6). Twin: avjunc_rule.bv_box (boulevard.runs). */
static int bv_takes(BYTE *mgr, int x, int z);                 /* task avx32: sc3netmod_bv.c */
static int avx_bv_box(AvxPass *p, int axis, int pos[][2][2], int i0, int i1) {
    (void)axis;
    if (i1 - i0 + 1 != 3) return 0;
    return bv_takes(p->mgr, pos[i0 + 1][0][0], pos[i0 + 1][0][1]);
}

/* segments and boxes from the straight pairs in (ox0, oz0)-(ox1, oz1) (twin avjunc_rule.find) */
static void avx_find(AvxPass *p, int ox0, int oz0, int ox1, int oz1) {
    int x, z, axis, sg;
    for (z = oz0; z <= oz1; z++)
        for (x = ox0; x <= ox1; x++)
            for (axis = 0; axis < 2; axis++) {
                if (!avx_pair(p, x, z, axis)) continue;
                for (sg = -1; sg <= 1; sg += 2) {
                    int pos[AVX_MAXSEG][2][2], np = 0, k = 1, bad = 0, i, h, i0, ix;
                    int feat[AVX_MAXSEG];
                    for (;;) {
                        int ax = x + sg * AVX_STEP[axis][0] * k, az = z + sg * AVX_STEP[axis][1] * k;
                        int bx = ax + AVX_ACROSS[axis][0], bz = az + AVX_ACROSS[axis][1];
                        DWORD a = avx_at(p, ax, az), b = avx_at(p, bx, bz);
                        if (!a || !b || avx_pair(p, ax, az, axis)) break;
                        if (avx_foreign((WORD)(a & 0xffff)) || avx_foreign((WORD)(b & 0xffff))) { bad = 1; break; }
                        if (np == AVX_MAXSEG) { bad = 1; break; }
                        pos[np][0][0] = ax; pos[np][0][1] = az; pos[np][1][0] = bx; pos[np][1][1] = bz; np++;
                        k++;
                    }
                    if (bad || !np) continue;
                    if (sg < 0)                                   /* positions in increasing order */
                        for (i = 0; i < np / 2; i++)
                            for (h = 0; h < 2; h++) {
                                int t0 = pos[i][h][0], t1 = pos[i][h][1];
                                pos[i][h][0] = pos[np - 1 - i][h][0]; pos[i][h][1] = pos[np - 1 - i][h][1];
                                pos[np - 1 - i][h][0] = t0; pos[np - 1 - i][h][1] = t1;
                            }
                    ix = avx_ix(p, pos[0][0][0], pos[0][0][1]);
                    if (ix < 0 || (p->segm[ix] & (1 << axis))) continue;
                    p->segm[ix] |= (BYTE)(1 << axis);
                    for (i = 0; i < np; i++)                      /* every cell plain, ours, or avcore's crossing */
                        for (h = 0; h < 2; h++) {
                            WORD id = (WORD)(avx_at(p, pos[i][h][0], pos[i][h][1]) & 0xffff);
                            if (!avx_plain(id) && !avx_own(id) && !avx_avcore_band(id) &&
                                !avx_virt(p, pos[i][h][0], pos[i][h][1])) bad = 1;                    /* avx32 */
                        }
                    if (bad) continue;
                    for (i = 0; i < np; i++)
                        feat[i] = avx_conn(p, pos[i][0][0], pos[i][0][1], AVX_OUT[axis][0]) ||
                                  avx_conn(p, pos[i][1][0], pos[i][1][1], AVX_OUT[axis][1]);
                    for (i = 0; i < np; ) {                       /* a run longer than AVX_MAXRUN refuses the segment */
                        int j = i;
                        while (j < np && feat[j]) j++;
                        if (j - i > AVX_MAXRUN) bad = 1;
                        i = j + 1;
                    }
                    if (bad) continue;
                    for (i = 0; i < np; i++) {                    /* link candidates: plain positions with no arm */
                        WORD ida = (WORD)(avx_at(p, pos[i][0][0], pos[i][0][1]) & 0xffff);
                        WORD idb = (WORD)(avx_at(p, pos[i][1][0], pos[i][1][1]) & 0xffff);
                        if (feat[i] || !(avx_plain(ida) || avx_own(ida) || avx_virt(p, pos[i][0][0], pos[i][0][1])) ||
                            !(avx_plain(idb) || avx_own(idb) || avx_virt(p, pos[i][1][0], pos[i][1][1]))) continue;   /* avx32 */
                        for (h = 0; h < 2; h++)
                            if ((ix = avx_ix(p, pos[i][h][0], pos[i][h][1])) >= 0) p->link[ix] = (BYTE)(1 + axis * 2 + h);
                    }
                    for (i0 = 0; i0 < np; ) {
                        int i1 = i0, t, clash = 0, mine;
                        AvxBox nb;
                        if (!feat[i0]) { i0++; continue; }
                        while (i1 + 1 < np && feat[i1 + 1]) i1++;
                        for (i = i0; i <= i1; i++)
                            for (h = 0; h < 2; h++) {
                                WORD id = (WORD)(avx_at(p, pos[i][h][0], pos[i][h][1]) & 0xffff);
                                if (!avx_plain(id) && !avx_own(id) && !avx_virt(p, pos[i][h][0], pos[i][h][1]))
                                    clash = -1;                                                          /* avx32 */
                            }
                        if (clash < 0) { i0 = i1 + 1; continue; }
                        if (g_bv_p[0] && avx_bv_box(p, axis, pos, i0, i1)) { i0 = i1 + 1; continue; }   /* task avx32 */
                        avx_make(p, axis, pos, np, i0, i1, &nb);
                        mine = 2 * nb.L;
                        for (i = 0; i < nb.L && clash >= 0; i++)   /* overlap: keep the bigger box */
                            for (h = 0; h < 2 && clash >= 0; h++) {
                                int ix2 = avx_ix(p, nb.x[i][h], nb.z[i][h]);
                                if (ix2 >= 0 && p->own[ix2]) {
                                    t = p->own[ix2] - 1;
                                    if (2 * p->bx[t].L >= mine) clash = -1; else avx_kill(p, t);
                                }
                            }
                        if (clash >= 0 && p->nb < p->cap) {
                            p->bx[p->nb] = nb;
                            for (i = 0; i < nb.L; i++)
                                for (h = 0; h < 2; h++) {
                                    int ix2 = avx_ix(p, nb.x[i][h], nb.z[i][h]);
                                    if (ix2 >= 0) p->own[ix2] = p->nb + 1;
                                }
                            p->nb++;
                        }
                        i0 = i1 + 1;
                    }
                }
            }
}

/* the modes another box gives cell (x, z) on side e (validation) */
static char avx_box_mode(AvxPass *p, int t, int x, int z, int e) {
    AvxBox *ob = &p->bx[t];
    int i, h;
    char ol[4], md[4];
    for (i = 0; i < ob->L; i++)
        for (h = 0; h < 2; h++)
            if (ob->x[i][h] == x && ob->z[i][h] == z) { avx_modes(ob, 0, i, h, ol, md); return md[e]; }
    return '?';
}

/* validation: drop boxes whose edges (every arm one-way) do not meet their neighbours; noses recomputed each round */
static void avx_validate(AvxPass *p) {
    int round, t, i, h, e, ndrop = 0;
    for (round = 0; round < AVX_ROUNDS; round++) {
        int bad = 0;
        avx_noses(p);
        for (t = 0; t < p->nb; t++) {
            AvxBox *bx = &p->bx[t];
            int ok = 1;
            if (bx->dead) continue;
            if (!avx_all_pieces(bx)) { avx_kill(p, t); ndrop++; bad++; continue; }
            for (i = 0; i < bx->L && ok; i++)
                for (h = 0; h < 2 && ok; h++) {
                    char ol[4], md[4];
                    avx_modes(bx, 0, i, h, ol, md);
                    for (e = 0; e < 4 && ok; e++) {
                        int nx = bx->x[i][h] + AVX_DIR[e][0], nz = bx->z[i][h] + AVX_DIR[e][1], ix = avx_ix(p, nx, nz);
                        char a = md[e], b;
                        if (ix >= 0 && p->own[ix]) b = avx_box_mode(p, p->own[ix] - 1, nx, nz, (e + 2) & 3);
                        else {
                            b = avx_nb_mode(p, nx, nz, (e + 2) & 3);
                            if (a == 'C' && b == 'T') continue;            /* a stub that does not connect (stock too) */
                        }
                        if (b == 'X') { ok = 0; continue; }
                        if (b == '?') continue;
                        if (!((a == 'I' && b == 'O') || (a == 'O' && b == 'I') || (a == 'T' && b == 'T') ||
                              (a == 'C' && b == 'C') || (a == 'C' && !avx_road(p, nx, nz)))) ok = 0;
                    }
                }
            if (!ok) { avx_kill(p, t); ndrop++; bad++; }
        }
        if (!bad) break;
    }
    avx_noses(p);
    if (ndrop) InterlockedExchangeAdd(&g_avx_n_drop, ndrop);
}

/* corner junctions (twin avjunc_rule.corner_at): the avenue enters the cell across e_in from a half running into it
   and leaves across e_out = e_in - 1 into a half running away; both halves' medians face the inner bend diagonal to
   the cell; each of the other two sides is a connected plain road (29) or closed, at least one road */
static void avx_corners(AvxPass *p, int ox0, int oz0, int ox1, int oz1) {
    int x, z, ein, e;
    if (!g_avx_nk) return;
    for (z = oz0; z <= oz1; z++)
        for (x = ox0; x <= ox1; x++) {
            DWORD v = avx_at(p, x, z);
            WORD id = (WORD)(v & 0xffff);
            int st = (int)((v >> 16) & 3), ix = avx_ix(p, x, z);
            if (!v || ix < 0 || !(id == 39 || id == 43 || avx_is_corner(id))) continue;
            for (ein = 0; ein < 4; ein++) {
                int eout = (ein + 3) & 3, hx = x + AVX_DIR[ein][0], hz = z + AVX_DIR[ein][1];
                int ox = x + AVX_DIR[eout][0], oz = z + AVX_DIR[eout][1];
                int nx = hx + AVX_DIR[eout][0], nz = hz + AVX_DIR[eout][1], si, so, nroad = 0, ok = 1, j, k, q;
                DWORD qi = avx_at(p, hx, hz), qo = avx_at(p, ox, oz), qn = avx_at(p, nx, nz), w = 0;
                WORD ii = (WORD)(qi & 0xffff), io = (WORD)(qo & 0xffff), inn = (WORD)(qn & 0xffff);
                char ol[4], md[4];
                if (!qi || !qo || !qn) continue;
                if (!(inn == 11203 || (avl_own(inn) && g_base[inn] == 11203))) continue;
                if (!(ii == 11204 || ii == g_avl_straight) || !(io == 11204 || io == g_avl_straight)) continue;
                si = (int)((qi >> 16) & 3); so = (int)((qo >> 16) & 3);
                if (((si + 3) & 3) != ((ein + 2) & 3) || ((so + 3) & 3) != eout) continue;
                if (hx + AVX_DIR[si][0] != nx || hz + AVX_DIR[si][1] != nz) continue;
                if (ox + AVX_DIR[so][0] != nx || oz + AVX_DIR[so][1] != nz) continue;
                for (e = 0; e < 4; e++) { ol[e] = 'C'; md[e] = 'C'; }
                ol[ein] = 'A'; md[ein] = 'I'; ol[eout] = 'A'; md[eout] = 'O';
                for (e = 0; e < 4; e++) {
                    if (e == ein || e == eout || !avx_conn(p, x, z, e)) continue;
                    if ((WORD)(avx_at(p, x + AVX_DIR[e][0], z + AVX_DIR[e][1]) & 0xffff) != 29) ok = 0;
                    ol[e] = 'A'; md[e] = 'T'; nroad++;
                }
                if (!ok || !nroad) continue;
                for (j = 0; j < g_avx_nk && !w; j++)       /* the declared piece whose pattern turned by k matches */
                    for (k = 0; k < 4 && !w; k++) {
                        for (q = 0; q < 4 && g_avx_k[j].ol[q] == ol[(q + k) & 3] && g_avx_k[j].md[q] == md[(q + k) & 3]; q++) ;
                        if (q == 4) w = ((DWORD)g_avx_k[j].piece << 8) | (DWORD)k;
                    }
                if (!w || p->nk >= p->kcap) break;
                p->kc[p->nk].x = x; p->kc[p->nk].z = z; p->kc[p->nk].hx = hx; p->kc[p->nk].hz = hz;
                p->kc[p->nk].ox = ox; p->kc[p->nk].oz = oz; p->kc[p->nk].want = w;
                p->kc[p->nk].orig = avx_is_corner(id) ? (((DWORD)g_base[id] << 8) | (DWORD)st) : (((DWORD)id << 8) | (DWORD)st);
                p->nk++;
                p->kmap[ix] = 1;
                break;
            }
        }
}

static void avx_free_pass(void) {
    if (g_avx_have && g_avx_p.b.c) VirtualFree(g_avx_p.b.c, 0, MEM_RELEASE);
    ZeroMemory(&g_avx_p, sizeof(g_avx_p));
    g_avx_have = 0;
}

static void avx_read(AvxPass *p) {
    int x, z;
    for (z = 0; z < p->b.h; z++)
        for (x = 0; x < p->b.w; x++) p->b.c[z * p->b.w + x] = rb_read(p->mgr, p->lay, p->b.x0 + x, p->b.z0 + z, p->W, p->H);
}

/* one-way when the first cell past the arm (over our noses) is one of our boxes or a cell of a band avcore converted */
static int avx_arm_oneway(AvxPass *p, AvxBox *bx, int k) {
    int i, h = bx->ah[k], e, x, z, ix, guard = 0;
    if (bx->ak[k] == 'B') {
        e = bx->ae[k];
        for (i = 0; i < bx->L; i++) if (bx->ek[i][h][e] == 'B') break;
        if (i == bx->L) return 0;
        x = bx->x[i][h]; z = bx->z[i][h];
    } else {
        e = AVX_OUT[bx->axis][h];
        x = bx->x[bx->ae[k]][h]; z = bx->z[bx->ae[k]][h];
    }
    x += AVX_DIR[e][0]; z += AVX_DIR[e][1];
    while ((ix = avx_ix(p, x, z)) >= 0 && p->nose[ix] && guard++ < 64) { x += AVX_DIR[e][0]; z += AVX_DIR[e][1]; }
    if (ix >= 0 && p->own[ix]) return 1;
    return avl_dir(x, z) >= 0;
}

static int avx_nose_oneway(AvxPass *p, int x0, int z0) {
    int ix0 = avx_ix(p, x0, z0), axis = (p->nose[ix0] - 1) & 1, s;
    for (s = 0; s < 2; s++) {
        int e = AVX_ALONG[axis][s], x = x0 + AVX_DIR[e][0], z = z0 + AVX_DIR[e][1], ix, guard = 0;
        while ((ix = avx_ix(p, x, z)) >= 0 && p->nose[ix] && guard++ < 64) { x += AVX_DIR[e][0]; z += AVX_DIR[e][1]; }
        if (ix >= 0 && p->own[ix]) continue;
        if (avl_dir(x, z) < 0) return 0;
    }
    return 1;
}

static int avx_nose_ends(AvxPass *p, int x, int z) {
    int ix = avx_ix(p, x, z), axis = (p->nose[ix] - 1) & 1, st = p->nst[ix], s, m = 0;
    for (s = 0; s < 2; s++) {
        int e = AVX_ALONG[axis][s], j = avx_ix(p, x + AVX_DIR[e][0], z + AVX_DIR[e][1]);
        if (j >= 0 && p->own[j]) m |= 1 << ((e - st) & 3);
    }
    return m;
}

/* write every live box (with its demotions) and nose; final = 1 in avx_post (decided), 0 in avx_run (optimistic) */
static int avx_write(AvxPass *p, int final, const char *who) {
    int t, i, h, x, z, n = 0, nrev = 0, wcap = p->b.w * p->b.h, nw = 0, live = 0;
    int *wx, *wz;
    DWORD *ww;
    wx = (int *)VirtualAlloc(NULL, (SIZE_T)wcap * 12, MEM_COMMIT, PAGE_READWRITE);
    if (!wx) return 0;
    wz = wx + wcap; ww = (DWORD *)(wz + wcap);
    for (t = 0; t < p->nb; t++) {
        AvxBox *bx = &p->bx[t];
        BYTE dem = 0;
        int k;
        if (bx->dead) continue;
        live++;
        if (!g_avl_on) dem = (BYTE)((1 << bx->narm) - 1);
        else if (final)
            for (k = 0; k < bx->narm; k++) if (!avx_arm_oneway(p, bx, k)) dem |= (BYTE)(1 << k);
        if (dem && final) InterlockedIncrement(&g_avx_n_dem);
        bx->dem = dem;
        for (i = 0; i < bx->L; i++)
            for (h = 0; h < 2; h++) {
                char ol[4], md[4];
                DWORD w;
                avx_modes(bx, dem, i, h, ol, md);
                w = avx_piece(ol, md);
                if (w && nw < wcap) { wx[nw] = bx->x[i][h]; wz[nw] = bx->z[i][h]; ww[nw] = w; nw++; }
            }
    }
    for (z = p->b.z0; z < p->b.z0 + p->b.h; z++)
        for (x = p->b.x0; x < p->b.x0 + p->b.w; x++) {
            int ix = avx_ix(p, x, z), ow, ends;
            WORD pc;
            if (!p->nose[ix]) continue;
            ow = g_avl_on && (!final || avx_nose_oneway(p, x, z));
            ends = avx_nose_ends(p, x, z);
            if (p->nose[ix] >= 3) pc = ow ? g_avx_nowl[ends] : g_avx_ntwl[ends];   /* a link nose */
            else pc = ow ? g_avx_now[ends] : g_avx_ntw[ends];
            if (pc && nw < wcap) { wx[nw] = x; wz[nw] = z; ww[nw] = ((DWORD)pc << 8) | (DWORD)p->nst[ix]; nw++; }
            else p->nose[ix] = 0;                         /* a two-way link with no nose piece: back to stock below */
        }
    for (t = 0; t < p->nk; t++) {                        /* corner junctions: one-way, or the stock T / X back */
        AvxCorner *k = &p->kc[t];
        DWORD w = k->want;
        /* no avl_corner_ok() dry run here: in avx_run the boxes and noses that end the corner group's other bands
           are not written yet (a load pass would refuse every corner); avx_post decides on avl's final map */
        if (!g_avl_on || (final && (avl_dir(k->hx, k->hz) < 0 || avl_dir(k->ox, k->oz) < 0))) w = k->orig;
        if (nw < wcap) { wx[nw] = k->x; wz[nw] = k->z; ww[nw] = w; nw++; }
    }
    /* our pieces no box or nose keeps: back to stock first (a revert's retile reaches the neighbours). Only near the
       edit: a box or nose farther out may belong to a band whose seeds lie outside this pass, and a needless revert's
       retile spreads into avcore's cells, which its own pass box (the edit + 2) does not rewrite */
    for (z = max(p->rz0, p->b.z0); !final && z <= p->rz1 && z < p->b.z0 + p->b.h; z++)   /* post never retiles */
        for (x = max(p->rx0, p->b.x0); x <= p->rx1 && x < p->b.x0 + p->b.w; x++) {
            DWORD v = avx_at(p, x, z);
            int ix = avx_ix(p, x, z), rect[6];
            if (!v || !avx_own((WORD)(v & 0xffff)) || p->own[ix] || p->nose[ix] || p->kmap[ix]) continue;
            rect[0] = x << 8; rect[1] = z << 8; rect[2] = 0; rect[3] = x << 8; rect[4] = z << 8; rect[5] = 0;
            ((PFN_Retile)VT(p->mgr, 0xb0))(p->mgr, 0, rect, 3);
            if (nrev < 8) logf("avx: %s: (%d,%d) piece %lu kept by no box or nose -> stock retile", who, x, z, v & 0xffff);
            nrev++;
        }
    if (nrev) avx_read(p);
    for (t = 0; t < nw; t++) {
        DWORD cur = avx_at(p, wx[t], wz[t]);
        int pos[3];
        if ((((cur & 0xffff) << 8) | ((cur >> 16) & 3)) == ww[t]) continue;
        pos[0] = wx[t] << 8; pos[1] = wz[t] << 8; pos[2] = 0;
        ((PFN_Put)(g_rb_m + 0x8919))(p->mgr, 0, p->lay, pos, ww[t], -1, 8, 0);
        n++;
    }
    if (n || nrev || !strcmp(who, "load"))
        logf("avx: %s %s: %d junction box(es), %d corner junction(s), %d cell(s) written, %d reverted", who,
             final ? "post" : "run", live, p->nk, n, nrev);
    VirtualFree(wx, 0, MEM_RELEASE);
    InterlockedExchangeAdd(&g_avx_n_cells, n);
    InterlockedExchangeAdd(&g_avx_n_rev, nrev);
    return n;
}

/* cells [x0..x1] x [z0..z1] were edited (the retile pass's work box) or the whole map (load) */
static void avx_run(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who) {
    AvxPass *p = &g_avx_p;
    int W = (*(int *)(mgr + 0x5c) >> 8) + 1, H = (*(int *)(mgr + 0x60) >> 8) + 1, n, t, live = 0;
    int ox0, oz0, ox1, oz1, M = AVX_MAXSEG + 6;
    avx_free_pass();
    if (!g_avx_on || W < 4 || H < 4 || W > 4096 || H > 4096) return;
    if (x1 > W - 1) x1 = W - 1;
    if (z1 > H - 1) z1 = H - 1;
    ox0 = x0 - M; oz0 = z0 - M; ox1 = x1 + M; oz1 = z1 + M;             /* straight pairs that seed segments */
    p->mgr = mgr; p->lay = *(void **)(mgr + 0x3c); p->W = W; p->H = H;
    p->rx0 = x0 - 2; p->rz0 = z0 - 2; p->rx1 = x1 + 2; p->rz1 = z1 + 2;
    p->b.x0 = ox0 - M; p->b.z0 = oz0 - M; p->b.w = ox1 - ox0 + 2 * M + 1; p->b.h = oz1 - oz0 + 2 * M + 1;
    if (p->b.x0 < 0) { p->b.w += p->b.x0; p->b.x0 = 0; }
    if (p->b.z0 < 0) { p->b.h += p->b.z0; p->b.z0 = 0; }
    if (p->b.x0 + p->b.w > W) p->b.w = W - p->b.x0;
    if (p->b.z0 + p->b.h > H) p->b.h = H - p->b.z0;
    if (ox0 < 0) ox0 = 0;
    if (oz0 < 0) oz0 = 0;
    if (ox1 > W - 1) ox1 = W - 1;
    if (oz1 > H - 1) oz1 = H - 1;
    if (p->b.w <= 0 || p->b.h <= 0) return;
    n = p->b.w * p->b.h;
    p->cap = strcmp(who, "load") ? 512 : 16384;
    p->kcap = strcmp(who, "load") ? 64 : 4096;
    p->b.c = (DWORD *)VirtualAlloc(NULL, (SIZE_T)n * 14 + 32 + (SIZE_T)p->cap * sizeof(AvxBox) +    /* avx32: +virt */
                                   (SIZE_T)p->kcap * sizeof(AvxCorner), MEM_COMMIT, PAGE_READWRITE);
    if (!p->b.c) return;
    p->own = (int *)(p->b.c + n);
    p->link = (BYTE *)(p->own + n); p->nose = p->link + n; p->segm = p->nose + n; p->nst = (signed char *)(p->segm + n);
    p->kmap = (BYTE *)(p->nst + n);
    p->virt = p->kmap + n;                                                                /* task avx32 */
    p->bx = (AvxBox *)(((ULONG_PTR)(p->virt + n) + 15) & ~(ULONG_PTR)15);
    p->kc = (AvxCorner *)(p->bx + p->cap);
    g_avx_have = 1;
    avx_read(p);
    avx_caps(p, ox0, oz0, ox1, oz1);                      /* task avx32 */
    avx_drops(p, p->b.x0, p->b.z0, p->b.x0 + p->b.w - 1, p->b.z0 + p->b.h - 1, who);   /* task avxroad */
    avx_find(p, ox0, oz0, ox1, oz1);
    avx_validate(p);
    avx_corners(p, ox0, oz0, ox1, oz1);
    for (t = 0; t < p->nb; t++) live += !p->bx[t].dead;
    InterlockedExchangeAdd(&g_avx_n_j, live);
    avx_write(p, !g_avl_on, who);                         /* without avcore every arm is two-way already */
}

/* after avcore's AVL pass: demote the arms whose band it left two-way, rewrite boxes and noses */
static void avx_post(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who) {
    AvxPass *p = &g_avx_p;
    (void)x0; (void)z0; (void)x1; (void)z1;
    if (!g_avx_on || !g_avx_have || p->mgr != mgr) return;
    if (!g_avl_on) { avx_free_pass(); return; }           /* avx_run wrote every arm two-way already */
    avx_read(p);
    avx_write(p, 1, who);
    avx_free_pass();
}

static int avx_post_hook(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who, int *rbox) {
    (void)rbox;
    avx_post(mgr, x0, z0, x1, z1, who);
    return 0;                                             /* never asks for a re-run */
}

static void avx_stats(void) {
    static LONG last;
    LONG n = g_avx_n_j + g_avx_n_cells + g_avx_n_rev + g_avx_n_dem + g_avx_n_drop + g_avx_n_tee;
    if (!g_avx_on || n == last) return;
    last = n;
    logf("stats: avx boxes seen=%ld, cells written=%ld, reverted=%ld, boxes with a two-way arm=%ld, dropped=%ld, "
         "stock-dropped T's re-read=%ld", g_avx_n_j, g_avx_n_cells, g_avx_n_rev, g_avx_n_dem, g_avx_n_drop,
         g_avx_n_tee);                                                                          /* task avxroad */
}
