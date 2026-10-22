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
 *  accepted  at least BV_MIN_COLS clean columns besides the end regions, no junction in or next to an end region
 *            (task avx32: a refusal about one end - incl. a bad arm, img16 - leaves that end stock, bv_run_fb;
 *            a Protected ROAD piece - level crossing, bridge, tunnel mouth - is never a boulevard cell, bv_prot;
 *            a bad arm the end cuts cannot reach splits the run there into two boulevards, bv_parts)
 *            (task avx32: a road / avenue crossing may stand next to a cap; a run ending ON a single road makes its
 *            last column a 1-column BVX box),
 *            no other ROAD 8-touching the run (junction arms and the road a taper goes on into excepted)
 *  pieces    canonical (boulevard along +x, rows 0 / 1 / 2): outer rows OUTER (row 0 state 2, row 2 state 0, = the
 *            states stock 11204 has there), middle MIDDLE / NOSE (median nose at +x, state 2 at -x) / NOSE2 (both)
 *            next to a junction or an end region; junction column JN / JM / JF; cap CAP[row]; taper TAPER[keep][col*3+row].
 *            The -x end is the +x end turned half a circle (rows 2 - row, state + 2, kept row 2 - keep).
 * Shapes refused (other streams own them): a diagonal touching the run, 3x3 blocks (any run shorter than
 * BV_MIN_RUN = 4 columns, whatever its arms: bigrbt's), the two OUTER rows going on at an end (two separate roads).
 * Avenue and boulevard junctions (2- or 3-wide spans, and a run ending on one): sc3netmod_bvx.c (task bvx), without
 * its `bvxb` lines refused as not a straight single road.
 * Write = FUN_10008919 per cell (as RBT / DAV). Revert = rect retile of a boulevard piece no run kept, done BEFORE
 * the writes (task avx32: a revert's retile reaches the run's own cells). Save: every
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
static WORD g_bv_jt[2];                        /* task bvlanes: a T's entry row / middle row (`bvj`), 0 = jn / jm */
static volatile LONG g_bv_n_runs, g_bv_n_cells, g_bv_n_rev;

enum { BV_OUTER, BV_MIDDLE, BV_NOSE, BV_NOSE2, BV_JN, BV_JM, BV_JF };
static int bv_post_avl(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who, int *rbox);   /* task bvlanes */
static int avl_post_set(int slot, int (*f)(BYTE *, int, int, int, int, const char *, int *));    /* task bvlanes */

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
        avl_post_set(1 /* AVL_POST_BV */, bv_post_avl);                           /* task bvlanes */
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
    } else if (!strncmp(line, "bvj ", 4)) {                                        /* task bvlanes */
        if (sscanf(line + 4, "%lu %lu", &v[0], &v[1]) != 2 || !bv_variant(v[0]) || !bv_variant(v[1])) {
            logf("### bv: %s: bad T junction line '%s'", path, line);
            return;
        }
        g_bv_jt[0] = (WORD)v[0];
        g_bv_jt[1] = (WORD)v[1];
        logf("bv: %s: T junction pieces entry %u, middle %u", path, g_bv_jt[0], g_bv_jt[1]);
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

static int bvx_is_piece(WORD id);                                        /* task bvx: sc3netmod_bvx.c */
/* task bvlanes: the post-AVL phase (AVENUE_LANES.md 5, slot AVL_POST_BV = 1 in sc3netmod_avl.c). After each avl_run:
   (1) the box of every cell BV wrote or reverted since the last call goes back to AVL as a re-run box, so the avenue
   a narrowing / avenue arm meets is re-decided with the boulevard as it now stands; (2) every recorded attachment
   (boulevard end cell, avenue cell beyond it) whose avenue AVL left two-way (avl_dir -1) while the boulevard piece is
   still there gets its run re-decided (avl_band_ok then refuses it -> stock, program rule), e.g. after a T drawn far
   down the avenue, outside BV's own pass box. */
static int avl_dir(int x, int z);
#define BV_ATT_MAX 512
static int g_bv_att[BV_ATT_MAX][5], g_bv_natt;   /* boulevard end x z, avenue cell x z, side toward the avenue */
static int g_bv_dirty[4] = { 0x7fffffff, 0x7fffffff, -1, -1 };
static void bv_dirty(int x, int z) {
    if (x - 2 < g_bv_dirty[0]) g_bv_dirty[0] = x - 2;
    if (z - 2 < g_bv_dirty[1]) g_bv_dirty[1] = z - 2;
    if (x + 2 > g_bv_dirty[2]) g_bv_dirty[2] = x + 2;
    if (z + 2 > g_bv_dirty[3]) g_bv_dirty[3] = z + 2;
}
static void bv_run(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who);
static void bv_att_add(const int *a) {
    int k;
    for (k = 0; k < g_bv_natt; k++)
        if (g_bv_att[k][0] == a[0] && g_bv_att[k][1] == a[1] && g_bv_att[k][2] == a[2] && g_bv_att[k][3] == a[3]) return;
    if (g_bv_natt < BV_ATT_MAX) { memcpy(g_bv_att[g_bv_natt], a, sizeof g_bv_att[0]); g_bv_natt++; }
}
static int avl_band_ok(int x, int z, int away);                          /* task bvlanes: sc3netmod_avl.c */
/* task avx32: bv_takes() runs bv_run1 as a dry run on the geometry only, with the AVL band checks taken as passed */
static int g_bv_dry;
#define BV_BAND_OK(x, z, away) (g_bv_dry || avl_band_ok((x), (z), (away)))
/* task bvlanes: the real side (0 N 1 E 2 S 3 W) of axis-space direction +s (dir 1) / -s (-1) / +w (2) / -w (-2) */
static int bv_side(int axis, int dir) {
    if (dir == 1) return axis ? 2 : 1;
    if (dir == -1) return axis ? 0 : 3;
    if (dir == 2) return axis ? 3 : 2;
    return axis ? 1 : 0;
}
static int bv_is_piece(WORD id) {
    int k, j;
    if (!id || !g_bv_p[0]) return 0;
    for (k = 0; k < 7; k++) if (g_bv_p[k] == id) return 1;
    for (k = 0; k < 3; k++) if (g_bv_cap[k] == id) return 1;
    if (g_bv_jt[0] == id || g_bv_jt[1] == id) return 1;                    /* task bvlanes */
    for (k = 0; k < 3; k++) for (j = 0; j < 9; j++) if (g_bv_tap[k][j] == id) return 1;
    for (k = 0; k < 2; k++) for (j = 0; j < 9; j++) if (g_bv_av[k][j] == id) return 1;
    if (bvx_is_piece(id)) return 1;                       /* task bvx */
    return 0;
}

typedef struct { int x, z; DWORD want; } BvCell;

typedef struct {
    RbBuf b;
    int axis;
    BvCell *cell;
    int n;
    int natt, att[8][5];        /* task bvlanes: (boulevard end cell, attached avenue cell, side) of the run decided */
    int bja, bjb;               /* task avx32 (img16 split): columns of the bad arm bv_run1 refused, -1 none */
} BvPass;
static int bvx_spans(BvPass *p, int sa, int sb, int w0, BYTE *kind, const char **why, int *bad_e);  /* task bvx */
static int bvx_boxes(BvPass *p, int sa, int sb, int w0, const BYTE *kind, int lo_tee, int hi_tee, int lo_av,
                     int hi_av);                                                       /* task bvx, avx32 */
static int bvx_cells_on(void);                                     /* task avx32: bvxc box cells declared */

/* axis space -> real */
static int bv_rx(int axis, int s, int w) { return axis ? -w : s; }
static int bv_rz(int axis, int s, int w) { return axis ? s : w; }
static int bv_road(BvPass *p, int s, int w) { return rb_at(&p->b, bv_rx(p->axis, s, w), bv_rz(p->axis, s, w)) != 0; }
static int bv_cl(BvPass *p, int s, int w) { return dbv_claimed(bv_rx(p->axis, s, w), bv_rz(p->axis, s, w)); } /* task diagbv */
/* task avx32 (img16): a ROAD piece the game keeps out of re-tiling (ROAD_GRND_Protected: level crossings 67 / 69,
   road x highway 11258, tunnel mouths 63 / 64, bridges 81.. / 11265..; netpack variants inherit their base's
   membership, templates are added) is never a boulevard cell: BV would overwrite it. FUN_1001a7f7(net 1 = ROAD, id),
   answers cached per id (0 not asked, 1 no, 2 yes) */
static BYTE g_bv_pk[65536];
static int bv_prot(BvPass *p, int s, int w) {
    DWORD v = rb_at(&p->b, bv_rx(p->axis, s, w), bv_rz(p->axis, s, w)), id = v & 0xffff;
    if (!v) return 0;
    if (!g_bv_pk[id]) g_bv_pk[id] = ((PFN_Prot)(g_rb_m + 0x1a7f7))(1, id) ? 2 : 1;
    return g_bv_pk[id] == 2;
}
static int bv_full(BvPass *p, int s, int w) {
    return bv_road(p, s, w) && bv_road(p, s, w + 1) && bv_road(p, s, w + 2) &&
           !bv_cl(p, s, w) && !bv_cl(p, s, w + 1) && !bv_cl(p, s, w + 2) &&   /* task diagbv: a diagonal boulevard's */
           !bv_prot(p, s, w) && !bv_prot(p, s, w + 1) && !bv_prot(p, s, w + 2);              /* task avx32 (img16) */
}

static void bv_put(BvPass *p, int s, int w, WORD piece, int st) {
    if (p->n >= DAV_MAX_CELLS) return;
    p->cell[p->n].x = bv_rx(p->axis, s, w);
    p->cell[p->n].z = bv_rz(p->axis, s, w);
    p->cell[p->n].want = ((DWORD)piece << 8) | (DWORD)((st + p->axis) & 3);
    p->n++;
}

/* one run starting at column sa, rows w0..w0+2. -> 1 accepted (cells in p->cell), 0 refused (*why; *bad_e = the end
   the refusal is about, 0 +s / 1 -s, or -1). Task avx32: cut_hi / cut_lo > 0 = a RAGGED end: that many columns at the
   +s / -s end stay with the stock tiler and the run ends on a plain column there, its median in a nose (end type 7) */
static int bv_run1(BvPass *p, int sa, int w0, int *psb, const char **why, BYTE *kind, int cut_hi, int cut_lo,
                   int *bad_e) {
    int sb = sa, s, k, e, n, ncl = 0, endtyp[2], endkeep[2], endlo, endhi, normlo, normhi, teew[2] = { 0, 0 };
    *why = "";
    *bad_e = -1;
    p->bja = p->bjb = -1;                                                /* task avx32 (img16 split) */
    p->natt = 0;                                                         /* task bvlanes */
    while (bv_full(p, sb + 1, w0) && sb - sa < BV_MAX_RUN - 1) sb++;
    *psb = sb;
    sa += cut_lo;                                                        /* task avx32 */
    sb -= cut_hi;
    n = sb - sa + 1;
    if (n < BV_MIN_COLS) return 0;
    if (n < BV_MIN_RUN) { *why = "3-column run: a 3x3 block (bigrbt's)"; return 0; }
    /* task avx32 (img16): a ragged end on a column with road beside it is refused before the spans, so bv_run_fb
       keeps cutting that end (a span further in must not be read as the other end's refusal first) */
    for (e = 0; e < 2; e++) {
        int se = e ? sa : sb;
        if ((e ? cut_lo : cut_hi) && (bv_road(p, se, w0 - 1) || bv_road(p, se, w0 + 3)))
            { *why = "ragged end on a junction column"; *bad_e = e; return 0; }
    }
    /* kind: 0 clean, 1 arm N, 2 arm S, 3 both; | 4 = a wide span column (task bvx: an avenue / boulevard arm) */
    if (!bvx_spans(p, sa, sb, w0, kind, why, bad_e)) return 0;  /* task bvx; avx32: a bad arm names its end */
    for (s = sa; s <= sb; s++) {
        int no = bv_road(p, s, w0 - 1), so = bv_road(p, s, w0 + 3);
        if (kind[s - sa] & 4) continue;                  /* task bvx */
        kind[s - sa] = (BYTE)(no | (so << 1));
        /* task avx32 (owner img16, a 1x1 stub): about the run end nearer to the column (bv_run_fb may leave it stock) */
        if (no && !(bv_road(p, s, w0 - 2) && !bv_road(p, s - 1, w0 - 1) && !bv_road(p, s + 1, w0 - 1)))
            { *why = "road beside the boulevard is not a straight single road"; *bad_e = s - sa <= sb - s;
              p->bja = p->bjb = s; return 0; }
        if (so && !(bv_road(p, s, w0 + 4) && !bv_road(p, s - 1, w0 + 3) && !bv_road(p, s + 1, w0 + 3)))
            { *why = "road beside the boulevard is not a straight single road"; *bad_e = s - sa <= sb - s;
              p->bja = p->bjb = s; return 0; }
    }
    /* ends: e 0 = the +s end (column sb), e 1 = the -s end (column sa) */
    for (e = 0; e < 2; e++) {
        int se = e ? sa : sb, st = e ? -1 : 1, got = 0, row = -1, first = -1, nclm = 0;
        for (k = 0; k < 3; k++) if (bv_road(p, se + st, w0 + k)) { got++; row = k; if (first < 0) first = k; }
        for (k = 0; k < 3; k++) nclm += bv_road(p, se + st, w0 + k) && bv_cl(p, se + st, w0 + k);   /* task diagbv */
        if (e ? cut_lo : cut_hi) {                                        /* task avx32: ragged end */
            if (kind[se - sa]) { *why = "ragged end on a junction column"; *bad_e = e; return 0; }
            endtyp[e] = 7; endkeep[e] = -1;
            continue;
        }
        if (got && nclm == got) { endtyp[e] = 5; endkeep[e] = -1; continue; }   /* task diagbv: 5 = bends into a DBV */
        if (!got && (kind[se - sa] & 4)) {                 /* task bvx: the run ends on an avenue / boulevard (T) */
            if ((kind[se - sa] & 3) != 3) { *why = "an end on a corner (road on one side only)"; *bad_e = e; return 0; }
            for (k = 0; k < 3 && se - st * k >= sa && se - st * k <= sb && (kind[se - st * k - sa] & 4); k++) ;
            endtyp[e] = 4; endkeep[e] = -9; teew[e] = k;
        }
        else if (got == 2 && row == first + 1 && (kind[se - sa] & 4) && bv_road(p, se + 2 * st, w0 + first) &&
                 bv_road(p, se + 2 * st, w0 + row)) {
            /* task avx32: the run ends in a box and an avenue goes on past it (the crossing road is a boulevard on one
               side, an avenue on the other: owner img7); the box side is 'L' / 'H'. Its noses come from the run that
               has this avenue beside it (bvx_boxes, side arm) */
            if ((kind[se - sa] & 3) != 3) { *why = "an end on a corner (road on one side only)"; *bad_e = e; return 0; }
            for (k = 0; k < 3 && se - st * k >= sa && se - st * k <= sb && (kind[se - st * k - sa] & 4); k++) ;
            endtyp[e] = 6; endkeep[e] = first; teew[e] = k;
            if (!BV_BAND_OK(bv_rx(p->axis, se + 2 * st, w0 + first), bv_rz(p->axis, se + 2 * st, w0 + first),
                             bv_side(p->axis, st)))
                { *why = "the avenue past the box would stay two-way"; return 0; }
            if (p->natt < 8) {
                p->att[p->natt][0] = bv_rx(p->axis, se + st, w0 + first); p->att[p->natt][1] = bv_rz(p->axis, se + st, w0 + first);
                p->att[p->natt][2] = bv_rx(p->axis, se + 2 * st, w0 + first);
                p->att[p->natt][3] = bv_rz(p->axis, se + 2 * st, w0 + first);
                p->att[p->natt][4] = bv_side(p->axis, st);
                p->natt++;
            }
            continue;
        }
        else if (!got && kind[se - sa] == 3 && bvx_cells_on()) {
            /* task avx32 (owner img12): the run ends ON a single road crossing its last column (a T, the boulevard
               the stem): that column is a 1-column box, its far side closed (bvx_boxes, hi_tee / lo_tee) */
            kind[se - sa] |= 4;
            endtyp[e] = 4; endkeep[e] = -9; teew[e] = 1;
        }
        else if (!got) { endtyp[e] = 1; endkeep[e] = -1; }
        else if (got == 1 && bv_road(p, se + 2 * st, w0 + row)) { endtyp[e] = 2; endkeep[e] = row; }
        else if (got == 2 && row == first + 1 && bv_road(p, se + 2 * st, w0 + first) && bv_road(p, se + 2 * st, w0 + row))
            { endtyp[e] = 3; endkeep[e] = first; }          /* task boulevard: two rows go on = the avenue */
        else { *why = "an end where the roads going on are not one road or an avenue"; *bad_e = e; return 0; }
        if (endtyp[e] == 1 && !g_bv_cap[0]) { *why = "no cap pieces declared"; *bad_e = e; return 0; }
        if (endtyp[e] == 2 && !g_bv_tap[e ? 2 - row : row][0])
            { *why = "no taper pieces declared"; *bad_e = e; return 0; }
        if (endtyp[e] == 3 && !g_bv_av[e ? 1 - first : first][0])
            { *why = "no avenue-narrowing pieces declared"; *bad_e = e; return 0; }
        /* task bvlanes (AVENUE_LANES.md program rule): the narrowing is one-way, so the avenue it goes on into must
           convert; else the whole run stays stock */
        if (endtyp[e] == 3 && !BV_BAND_OK(bv_rx(p->axis, se + st, w0 + first), bv_rz(p->axis, se + st, w0 + first),
                                           bv_side(p->axis, st)))
            { *why = "the avenue it narrows into would stay two-way"; return 0; }
        if (endtyp[e] == 3 && p->natt < 8) {
            p->att[p->natt][0] = bv_rx(p->axis, se, w0 + first); p->att[p->natt][1] = bv_rz(p->axis, se, w0 + first);
            p->att[p->natt][2] = bv_rx(p->axis, se + st, w0 + first); p->att[p->natt][3] = bv_rz(p->axis, se + st, w0 + first);
            p->att[p->natt][4] = bv_side(p->axis, st);
            p->natt++;
        }
    }
    /* bvx: 4 = T, diagbv: 5 = DBV, avx32: 6 = box + avenue, 7 = ragged */
    endhi = endtyp[0] == 1 ? 1 : endtyp[0] == 4 || endtyp[0] == 6 ? teew[0] : endtyp[0] >= 5 ? 0 : BV_TAPER;
    endlo = endtyp[1] == 1 ? 1 : endtyp[1] == 4 || endtyp[1] == 6 ? teew[1] : endtyp[1] >= 5 ? 0 : BV_TAPER;
    normlo = sa + endlo;
    normhi = sb - endhi;
    if (normhi < normlo) { *why = "run too short for its ends"; return 0; }
    for (s = normlo; s <= normhi; s++) ncl += kind[s - sa] == 0;
    if (ncl < BV_MIN_COLS) { *why = "fewer than 3 boulevard columns"; return 0; }
    for (s = sa; s < normlo; s++)
        if (kind[s - sa] && endtyp[1] != 4 && endtyp[1] != 6)
            { *why = "a junction inside an end region"; *bad_e = 1; return 0; }
    for (s = normhi + 1; s <= sb; s++)
        if (kind[s - sa] && endtyp[0] != 4 && endtyp[0] != 6)
            { *why = "a junction inside an end region"; *bad_e = 0; return 0; }
    /* task avx32: a road or an avenue crossing may stand next to a cap (the boulevard crosses it and stops one column
       on). Not a boulevard (3 wide): its own run reads the one-column stub as an arm shorter than 2 */
    for (e = 0; e < 2; e++) {
        int s0 = e ? normlo : normhi, st = e ? 1 : -1, wd = 0;
        if (!kind[s0 - sa]) continue;
        if (kind[s0 - sa] & 4)
            for (; s0 + st * wd >= sa && s0 + st * wd <= sb && (kind[s0 + st * wd - sa] & 4); wd++) ;
        if (endtyp[e] != 1 || wd > 2) { *why = "a junction next to an end region"; *bad_e = e; return 0; }
    }
    /* isolated: every ROAD cell 8-touching the run is the run, a junction arm or the road a taper goes on into */
    for (s = sa - 1; s <= sb + 1; s++)
        for (k = -1; k <= 3; k++) {
            int in = s >= sa && s <= sb && k >= 0 && k <= 2, ok;
            if (in || !bv_road(p, s, w0 + k)) continue;
            ok = (s >= sa && s <= sb && k == -1 && (kind[s - sa] & 1)) || (s >= sa && s <= sb && k == 3 && (kind[s - sa] & 2)) ||
                 (s == sb + 1 && endtyp[0] >= 2 && (k == endkeep[0] || ((endtyp[0] == 3 || endtyp[0] == 6) && k == endkeep[0] + 1))) ||
                 (s == sa - 1 && endtyp[1] >= 2 && (k == endkeep[1] || ((endtyp[1] == 3 || endtyp[1] == 6) && k == endkeep[1] + 1))) ||
                 bv_cl(p, s, w0 + k) ||                              /* task diagbv */
                 (s == sb + 1 && endtyp[0] == 7) || (s == sa - 1 && endtyp[1] == 7);   /* task avx32: the stock rest */
            if (!ok) { *why = "touches road"; return 0; }
        }
    /* pieces */
    p->n = 0;
    for (e = 0; e < 2; e++) {
        int col, row;
        if (endtyp[e] >= 4) continue;  /* task bvx: the T's box comes with bvx_boxes; diagbv: DBV; avx32: box + avenue */
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
            int hi = (s == normhi && endtyp[0] != 3 && endtyp[0] != 5) || (s < sb && kind[s + 1 - sa]),
                lo = (s == normlo && endtyp[1] != 3 && endtyp[1] != 5) || (s > sa && kind[s - 1 - sa]);   /* task diagbv */
            bv_put(p, s, w0, g_bv_p[BV_OUTER], 2);
            bv_put(p, s, w0 + 2, g_bv_p[BV_OUTER], 0);
            bv_put(p, s, w0 + 1, g_bv_p[hi && lo ? BV_NOSE2 : hi || lo ? BV_NOSE : BV_MIDDLE], lo && !hi ? 2 : 0);
        } else if (kd & 4) {                                /* task bvx: the box, below */
        } else {
            /* task bvlanes: a T's entry and middle rows carry their own one-way lanes; the T from +w is the T from -w
               turned half a circle */
            WORD jn = kd == 3 || !g_bv_jt[0] ? g_bv_p[BV_JN] : g_bv_jt[0];
            WORD jm = kd == 3 || !g_bv_jt[1] ? g_bv_p[BV_JM] : g_bv_jt[1];
            bv_put(p, s, w0 + 1, jm, kd == 2 && g_bv_jt[1] ? 2 : 0);
            if (kd == 1) { bv_put(p, s, w0, jn, 0); bv_put(p, s, w0 + 2, g_bv_p[BV_JF], 0); }
            else if (kd == 2) { bv_put(p, s, w0, g_bv_p[BV_JF], 2); bv_put(p, s, w0 + 2, jn, 2); }
            else { bv_put(p, s, w0, jn, 0); bv_put(p, s, w0 + 2, jn, 2); }
        }
    }
    if (!bvx_boxes(p, sa, sb, w0, kind, endtyp[1] == 4, endtyp[0] == 4, endtyp[1] == 6 ? 1 + endkeep[1] : 0,
                   endtyp[0] == 6 ? 1 + endkeep[0] : 0))                  /* task bvx, avx32 */
        { *why = "a box cell with no declared piece"; return 0; }
    return 1;
}

/* task avx32 (orchestrator 2026-10-21): an end the rule cannot build does not take the whole run stock. Its columns stay
   with the stock tiler (cut 1, 2, ... from that end until the run converts), the rest converts, middle boxes included.
   Refusals not about one end (touching road, road 4+ wide, the AVL program rule) still refuse the run; a bad arm (task
   avx32, owner img16: a 2x1 or 1x1 stub beside the run) is about the end nearer to it. -> as bv_run1;
   base[] = the columns already left stock at the +s / -s end (a piece of a split run, bv_parts), cut[] = base + the
   ragged cuts, *why = the first refusal when an end was cut, *sja / *sjb = the bad arm of the first refusal (-1 none).
   Twin: boulevard.runs() fb() */
#define BV_RAG_MAX 12
static int bv_run_fb(BvPass *p, int sa, int w0, int *psb, const char **why, BYTE *kind, const int *base, int *cut,
                     int *sja, int *sjb) {
    int bad, r, round, e, c, sb2, b2;
    const char *why0, *w2;
    cut[0] = base[0]; cut[1] = base[1];
    r = bv_run1(p, sa, w0, psb, why, kind, base[0], base[1], &bad);
    why0 = *why;
    *sja = p->bja; *sjb = p->bjb;
    for (round = 0; round < 4 && !r && bad >= 0; round++) {           /* task avx32 (img16): 4 rounds, cuts grow */
        int cc[2], next = 0;
        e = bad;
        for (c = cut[e] + 1; c <= base[e] + BV_RAG_MAX; c++) {
            cc[0] = cut[0]; cc[1] = cut[1]; cc[e] = c;
            if (*psb - sa + 1 - cc[0] - cc[1] < BV_MIN_RUN) break;
            r = bv_run1(p, sa, w0, &sb2, &w2, kind, cc[0], cc[1], &b2);
            if (r || (b2 >= 0 && b2 != e)) { cut[0] = cc[0]; cut[1] = cc[1]; bad = b2; next = 1; break; }
        }
        if (!next) { r = 0; break; }
    }
    if (!r) { cut[0] = base[0]; cut[1] = base[1]; *why = why0; return 0; }
    *why = (cut[0] != base[0] || cut[1] != base[1]) ? why0 : "";
    return 1;
}

/* task avx32 (owner 2026-10-22, img16 middle split): a run the end cuts cannot save, refused for a bad arm, is split at
   the arm's columns: each side is a run of its own (base cut = the columns from the arm on, so the split ends are
   ragged), tried by bv_run_fb the same way; sides shorter than BV_MIN_RUN stay stock. part() is called for every piece
   that converts, with p->cell / p->n / p->natt holding its cells and cut[] its stock columns at the +s / -s end of the
   whole run sa..*psb; -> the number of pieces. *why = the first refusal (of the whole run). Twin: boulevard.runs() segs */
#define BV_SEG_MAX 16
typedef void (*BvPart)(void *ctx, BvPass *p, int sa, int sb, int w0, const int *cut, const char *why, int split);
static int bv_parts(BvPass *p, int sa, int w0, int *psb, const char **why, BYTE *kind, BvPart part, void *ctx) {
    int seg[BV_SEG_MAX][2], nseg = 1, head = 0, nparts = 0, failed = 0, cut[2], sja, sjb, k;
    const char *w1, *first = "";
    seg[0][0] = seg[0][1] = 0;
    while (head < nseg) {
        int *base = seg[head++];
        if (!bv_run_fb(p, sa, w0, psb, &w1, kind, base, cut, &sja, &sjb)) {
            if (!failed) first = w1;
            failed = 1;
            if (sja < 0) continue;
            for (k = 0; k < 2; k++) {                       /* the -s side (arm and beyond cut at +s), the +s side */
                int nb0 = k ? base[0] : *psb - sja + 1, nb1 = k ? sjb - sa + 1 : base[1];
                if (*psb - sa + 1 - nb0 - nb1 < BV_MIN_RUN || nseg >= BV_SEG_MAX) continue;
                seg[nseg][0] = nb0; seg[nseg][1] = nb1; nseg++;
            }
            continue;
        }
        if (!failed && !nparts) first = w1;
        part(ctx, p, sa, *psb, w0, cut, failed ? first : w1, failed);
        nparts++;
    }
    *why = first;
    return nparts;
}

/* task avx32: would BV's run rule put one of its pieces on cell (x, z)? bv_run1 on the cells as they stand, the AVL
   band checks taken as passed (geometry only: whatever a pass wrote into an avenue arm before must not change the
   answer). For AVX, which runs before BV: a box whose crossing roads are a boulevard BV builds is BV's, so AVX and BV
   use one definition of a boulevard. Reads a window of BV_TAKES_R cells round (x, z); a run longer than that is cut
   at the window (an end there reads as a cap). */
#define BV_TAKES_R 48
typedef struct { int x, z, hit; } BvTakes;
static void bv_takes_part(void *ctx, BvPass *p, int sa, int sb, int w0, const int *cut, const char *why, int split) {
    BvTakes *t = (BvTakes *)ctx;
    int k;
    (void)sa; (void)sb; (void)w0; (void)cut; (void)why; (void)split;
    for (k = 0; k < p->n && !t->hit; k++) t->hit = p->cell[k].x == t->x && p->cell[k].z == t->z;
}
static int bv_takes(BYTE *mgr, int x, int z) {
    void *lay = *(void **)(mgr + 0x3c);
    int W = (*(int *)(mgr + 0x5c) >> 8) + 1, H = (*(int *)(mgr + 0x60) >> 8) + 1;
    int x0 = x - BV_TAKES_R, z0 = z - BV_TAKES_R, x1 = x + BV_TAKES_R, z1 = z + BV_TAKES_R, axis, k, hit = 0;
    BvTakes T;
    BvPass P;
    BYTE *mem, *kind;
    SIZE_T nbuf;
    if (!g_bv_p[0] || !mgr || W < 4 || H < 4 || W > 4096 || H > 4096) return 0;
    if (x0 < 0) x0 = 0;
    if (z0 < 0) z0 = 0;
    if (x1 > W - 1) x1 = W - 1;
    if (z1 > H - 1) z1 = H - 1;
    ZeroMemory(&P, sizeof(P));
    P.b.x0 = x0; P.b.z0 = z0; P.b.w = x1 - x0 + 1; P.b.h = z1 - z0 + 1;
    nbuf = (SIZE_T)P.b.w * P.b.h;
    mem = (BYTE *)VirtualAlloc(NULL, nbuf * 4 + DAV_MAX_CELLS * sizeof(BvCell) + BV_MAX_RUN, MEM_COMMIT, PAGE_READWRITE);
    if (!mem) return 0;
    P.b.c = (DWORD *)mem;
    P.cell = (BvCell *)(mem + nbuf * 4);
    kind = (BYTE *)(P.cell + DAV_MAX_CELLS);
    for (k = 0; k < (int)nbuf; k++) P.b.c[k] = rb_read(mgr, lay, x0 + k % P.b.w, z0 + k / P.b.w, W, H);
    g_bv_dry = 1;
    for (axis = 0; axis < 2 && !hit; axis++) {
        int s = axis ? z : x, w = axis ? -x : z, w0;
        P.axis = axis;
        for (w0 = w - 2; w0 <= w && !hit; w0++) {
            const char *why = "";
            int sa = s, sb;
            if (!bv_full(&P, s, w0)) continue;
            while (bv_full(&P, sa - 1, w0) && s - sa < BV_MAX_RUN - 1) sa--;
            T.x = x; T.z = z; T.hit = 0;
            bv_parts(&P, sa, w0, &sb, &why, kind, bv_takes_part, &T);       /* task avx32: + ragged ends, splits */
            hit = T.hit;
        }
    }
    g_bv_dry = 0;
    VirtualFree(mem, 0, MEM_RELEASE);
    return hit;
}

typedef struct {
    BYTE *mgr; void *lay; int x0, z0, x1, z1, W, H; const char *who; BYTE *keep; int write, border, nruns, nw;
} BvDecide;

/* one converting piece of a run (bv_parts): border check, then keep[] (write 0) or the pieces + log (write 1) */
static void bv_decide_part(void *ctx, BvPass *P, int sa, int sb, int w, const int *cut, const char *why, int split) {
    BvDecide *d = (BvDecide *)ctx;
    int k, nw = 0, axis = P->axis;
    if (cut[0] || cut[1]) {
        /* task avx32: a ragged run whose full extent reaches the read border may be cut by the window, not by its own
           end: the whole-map pass decides it */
        int ec[2], j, hit = 0;
        ec[0] = sa; ec[1] = sb;
        for (j = 0; j < 2 && !hit; j++)
            for (k = 0; k < 3 && !hit; k++) {
                int cx = bv_rx(axis, ec[j], w + k), cz = bv_rz(axis, ec[j], w + k);
                hit = (cx <= d->x0 + 1 && d->x0 > 0) || (cz <= d->z0 + 1 && d->z0 > 0) ||
                      (cx >= d->x1 - 1 && d->x1 < d->W - 1) || (cz >= d->z1 - 1 && d->z1 < d->H - 1);
            }
        if (hit) { d->border = 1; return; }
        if (d->write && split)
            logf("bv: %s: run axis %d from (%d,%d): split at a bad arm, columns %d..%d convert, the rest of %d..%d left to "
                 "the stock tiler: %s", d->who, axis, bv_rx(axis, sa, w), bv_rz(axis, sa, w), sa + cut[1], sb - cut[0],
                 sa, sb, why);
        else if (d->write)
            logf("bv: %s: run axis %d from (%d,%d): ragged end(s), %d column(s) at +s and %d at -s left to the stock "
                 "tiler: %s", d->who, axis, bv_rx(axis, sa, w), bv_rz(axis, sa, w), cut[0], cut[1], why);
    }
    for (k = 0; k < P->n; k++) {                     /* the run or its ring at the read border: seen cut, not written */
        int cx = P->cell[k].x, cz = P->cell[k].z;
        if ((cx <= d->x0 + 1 && d->x0 > 0) || (cz <= d->z0 + 1 && d->z0 > 0) || (cx >= d->x1 - 1 && d->x1 < d->W - 1) ||
            (cz >= d->z1 - 1 && d->z1 < d->H - 1))
            break;
    }
    if (k < P->n) { d->border = 1; return; }
    if (!d->write) {
        if (d->keep)
            for (k = 0; k < P->n; k++) d->keep[(P->cell[k].z - d->z0) * P->b.w + (P->cell[k].x - d->x0)] = 1;
        return;
    }
    d->nruns++;
    for (k = 0; k < P->natt; k++) bv_att_add(P->att[k]);                                /* task bvlanes */
    for (k = 0; k < P->n; k++) {
        int cx = P->cell[k].x, cz = P->cell[k].z, pos[3];
        DWORD cur = rb_at(&P->b, cx, cz);
        if ((((cur & 0xffff) << 8) | ((cur >> 16) & 3)) == P->cell[k].want) continue;
        pos[0] = cx << 8; pos[1] = cz << 8; pos[2] = 0;
        ((PFN_Put)(g_rb_m + 0x8919))(d->mgr, 0, d->lay, pos, P->cell[k].want, -1, 8, 0);
        nw++;
        bv_dirty(cx, cz);                                                               /* task bvlanes */
    }
    if (nw || !strcmp(d->who, "load"))
        logf("bv: %s: boulevard axis %d, columns %d..%d at row %d, %d cell(s), %d written", d->who, axis, sa, sb, w, P->n,
             nw);
    d->nw += nw;
}

/* every run of the read window, decided; write = 0: only mark keep[] and find the border; write = 1: put the pieces
   (and log). -> 1 when an accepted run reached the read border (the caller re-runs over the whole map) */
static int bv_decide(BvPass *P, BYTE *mgr, void *lay, int x0, int z0, int x1, int z1, int W, int H, const char *who,
                     BYTE *keep, BYTE *kind, int write, int *pnruns, int *pnw) {
    int axis;
    BvDecide d;
    d.mgr = mgr; d.lay = lay; d.x0 = x0; d.z0 = z0; d.x1 = x1; d.z1 = z1; d.W = W; d.H = H; d.who = who; d.keep = keep;
    d.write = write; d.border = 0; d.nruns = 0; d.nw = 0;
    for (axis = 0; axis < 2; axis++) {
        int s0 = axis ? z0 : x0, s1 = axis ? z1 : x1, wl = axis ? -x1 : z0, wh = axis ? -x0 : z1, s, w;
        P->axis = axis;
        for (w = wl; w <= wh; w++)
            for (s = s0; s <= s1; s++) {
                const char *why = "";
                int sb;
                if (!bv_full(P, s, w) || bv_full(P, s - 1, w)) continue;
                if (!bv_parts(P, s, w, &sb, &why, kind, bv_decide_part, &d)) {   /* task avx32: + ragged ends, splits */
                    if (write && *why && sb - s + 1 >= 2 * BV_MIN_COLS)
                        logf("bv: %s: run axis %d from (%d,%d), %d column(s) left to the stock tiler: %s", who, axis,
                             bv_rx(axis, s, w), bv_rz(axis, s, w), sb - s + 1, why);
                }
            }
    }
    *pnruns += d.nruns;
    *pnw += d.nw;
    return d.border;
}

/* -> 1 when an accepted run reached the read border (the caller re-runs over the whole map).
   task avx32 (img16): decide (keep), revert, re-read, THEN write. Writing first let a revert's stock retile overwrite
   pieces just written (in game: a run cut by a rail crossing, its far side reverted, 4 written columns came back
   stock until the next edit) */
static int bv_pass(BYTE *mgr, int x0, int z0, int x1, int z1, int W, int H, const char *who, BYTE *keep) {
    void *lay = *(void **)(mgr + 0x3c);
    BvPass P;
    BYTE *mem, kind[BV_MAX_RUN];
    SIZE_T nbuf;
    int x, z, border, nruns = 0, nwall = 0, nrev = 0;
    P.b.x0 = x0; P.b.z0 = z0; P.b.w = x1 - x0 + 1; P.b.h = z1 - z0 + 1;
    nbuf = (SIZE_T)P.b.w * P.b.h;
    mem = (BYTE *)VirtualAlloc(NULL, nbuf * 4 + DAV_MAX_CELLS * sizeof(BvCell), MEM_COMMIT, PAGE_READWRITE);
    if (!mem) return 0;
    P.b.c = (DWORD *)mem;
    P.cell = (BvCell *)(mem + nbuf * 4);
    for (z = 0; z < P.b.h; z++)
        for (x = 0; x < P.b.w; x++) P.b.c[z * P.b.w + x] = rb_read(mgr, lay, x0 + x, z0 + z, W, H);
    border = bv_decide(&P, mgr, lay, x0, z0, x1, z1, W, H, who, keep, kind, 0, &nruns, &nwall);
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
                bv_dirty(x, z);                                                         /* task bvlanes */
                logf("bv: %s: (%d,%d) boulevard piece %lu no longer in a run -> stock retile", who, x, z, v & 0xffff);
            }
    if (nrev)                                        /* task avx32: the retiles may have changed cells: read again */
        for (z = 0; z < P.b.h; z++)
            for (x = 0; x < P.b.w; x++) P.b.c[z * P.b.w + x] = rb_read(mgr, lay, x0 + x, z0 + z, W, H);
    bv_decide(&P, mgr, lay, x0, z0, x1, z1, W, H, who, NULL, kind, 1, &nruns, &nwall);
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

/* task bvlanes: AVL_POST_BV (see bv_dirty above). -> 1 with rbox = the box AVL must re-decide */
static int bv_post_avl(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who, int *rbox) {
    int W = (*(int *)(mgr + 0x5c) >> 8) + 1, H = (*(int *)(mgr + 0x60) >> 8) + 1, k, n0 = g_bv_natt;
    void *lay = *(void **)(mgr + 0x3c);
    static int redo[BV_ATT_MAX][2];
    int nredo = 0;
    (void)x0; (void)z0; (void)x1; (void)z1;
    if (!g_bv_p[0]) return 0;
    for (k = n0 - 1; k >= 0; k--) {                 /* only the entries there at entry (bv_run below adds new ones) */
        int *a = g_bv_att[k];
        DWORD v = rb_read(mgr, lay, a[0], a[1], W, H);
        if (!v || !bv_is_piece((WORD)(v & 0xffff))) { memcpy(a, g_bv_att[--g_bv_natt], sizeof g_bv_att[0]); continue; }
        if (avl_dir(a[2], a[3]) >= 0) continue;
        if (avl_band_ok(a[2], a[3], a[4])) { bv_dirty(a[2], a[3]); continue; }   /* it would convert: AVL decides it */
        logf("bv: %s: post-avl: the avenue at (%d,%d) would stay two-way - re-deciding the boulevard at (%d,%d)", who,
             a[2], a[3], a[0], a[1]);
        redo[nredo][0] = a[0]; redo[nredo][1] = a[1]; nredo++;
        memcpy(a, g_bv_att[--g_bv_natt], sizeof g_bv_att[0]);
    }
    for (k = 0; k < nredo; k++) bv_run(mgr, redo[k][0], redo[k][1], redo[k][0], redo[k][1], who);   /* -> stock */
    if (g_bv_dirty[2] < g_bv_dirty[0]) return 0;
    memcpy(rbox, g_bv_dirty, sizeof g_bv_dirty);
    g_bv_dirty[0] = g_bv_dirty[1] = 0x7fffffff;
    g_bv_dirty[2] = g_bv_dirty[3] = -1;
    return 1;
}

static void bv_stats(void) {
    static LONG last;
    LONG n = g_bv_n_runs + g_bv_n_cells + g_bv_n_rev;
    if (!g_bv_p[0] || n == last) return;
    last = n;
    logf("stats: bv runs seen=%ld, cells written=%ld, cells reverted=%ld", g_bv_n_runs, g_bv_n_cells, g_bv_n_rev);
}
