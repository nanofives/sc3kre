/* sc3netmod_hwcap.c - carry a highway arm on past its stock end cap (task hwcap, highway program 2026-10-18).
 * #included by sc3netmod.c after sc3netmod_hwy.c and before the shape blocks (hwt, hwx, hwdd, hwdx), which call it.
 *
 * The case (verify/hwcap/RESULTS.md): a highway the player drags ends in a stock end cap ON the drag's last cell at one
 * end and one cell PAST the drag at the other (measured in game 2026-10-18, below). An interchange whose joining cells
 * reach the drag's end then finds the cap (or nothing) where it needs plain highway, and the block dropped that
 * quadrant (hwdx: Seoul quadrant A1) or the whole cloverleaf (hwx, hwdd, hwt). The fix is the stock shape: the block
 * carries the arm on with the stock plain pieces up to its last joining row and puts the arm's own cap (same id and
 * state) one row further, exactly what a drag that much longer leaves. No new pieces: a city saved this way loads in a
 * game without the mod as a stock highway that is a few cells longer.
 *
 * Stock ends (lab, `hw_lab.py cells`, 2026-10-18; sc3netmod loaded, no block touches a lone highway):
 *   straight along x, drag (58,25) -> (66,25): lanes z 24 = 15051.2, z 25 = 15051.0, x 57..66; caps x 57 (one past the
 *     start) 15053.0 / 15054.0 (z 24 / z 25), x 66 (the end cell) 15054.2 / 15053.2
 *   straight along z, drag (70,28) -> (70,38): lanes x 69 = 73.2, x 70 = 73.0; caps z 27 11237.2 / 11235.2 (x 69 / 70),
 *     z 38 11235.0 / 11237.0
 *   diagonal x - z, drag (44,14) -> (52,22): band 11223.2 / 11224.0 / 11223.0 per row; caps on the middle line,
 *     (43,13) 14999.0 with (44,13) 11223.0, (52,22) 14999.2 with (51,22) 11223.2 (the row's outer cell beyond is empty)
 *   diagonal x + z, drag (56,40) -> (64,32): band 15052.2 / 15106.0 / 15052.0; caps (55,40) 15059.2 with (56,40)
 *     15052.0, (64,31) 15059.0 with (63,31) 15052.2
 * So an arm's end is always: the last row, with the cap(s) in it (straight: both lanes; diagonal: the middle cell, the
 * two outer cells between it and the previous middle stay plain, the two beyond it are empty). The cap's (id, state)
 * names the outward direction (g_hwcap_dir).
 *
 * Use (a block's FRESH build only: an interchange already built never grows its arms, so a player who cuts an arm
 * still loses that side as before):
 *   HwcapSet s; s.n = s.nn = 0;
 *   hwcap_need(hp, &s, x, z, sx, sz, tag)   cell (x, z) of an arm whose outward step is (sx, sz) must be whole highway.
 *                 -> 1 it holds highway that is no cap (nothing to do), 2 it will be: its arm ends behind it in a cap and
 *                 every cell the arm needs up to one row past (x, z) takes a highway (hwcap_free), unclaimed and inside the pass
 *                 box (the need is recorded under `tag`), 0 no (g_hwcap_why says why)
 *   hwcap_commit(hp, &s, tags)              write the arms the needs under `tags` (a bit mask) asked for; per arm the
 *                 farthest need wins. Call it before writing the block's own pieces (they go over the plain ones).
 * Off: SC3NETMOD_HWCAP=0 (the blocks then refuse as before).
 */

#define HWCAP_ARMS 8
#define HWCAP_NEEDS 64
#define HWCAP_REACH 16                       /* cells walked back from a needed cell to find its arm's cap */

typedef struct { short x, z; signed char sx, sz, px, pz; BYTE diag; WORD cap0, cap1; BYTE st0, st1; } HwcapArm;
typedef struct { int n, nn; HwcapArm a[HWCAP_ARMS]; struct { BYTE arm; BYTE tag; short rows; } need[HWCAP_NEEDS]; } HwcapSet;

static int g_hwcap_off = -1;
static char g_hwcap_why[112];
static volatile LONG g_hwcap_n_arm, g_hwcap_n_cell;

/* a stock end cap -> its outward step (measured, above); 0 = not a cap or a state never seen */
static int hwcap_dir(DWORD v, int *sx, int *sz) {
    WORD id = hwy_id(v);
    int s = hwy_st(v);
    if (!v || (s & 1)) return 0;
    switch (id) {
    case 14999: *sx = *sz = s ? 1 : -1; return 1;
    case 15059: *sx = s ? -1 : 1; *sz = -*sx; return 1;
    case 15053: case 15054: *sx = s ? 1 : -1; *sz = 0; return 1;
    case 11235: case 11237: *sx = 0; *sz = s ? -1 : 1; return 1;
    }
    return 0;
}

static int hwcap_is(DWORD v) { int a, b; return hwcap_dir(v, &a, &b); }

static DWORD hwcap_rd(HwyPass *hp, int x, int z) {
    if (x >= hp->b.x0 && z >= hp->b.z0 && x < hp->b.x0 + hp->b.w && z < hp->b.z0 + hp->b.h) return hwy_at(hp, x, z);
    return hwy_read(hp->mgr, hp->lay, x, z, hp->W, hp->H);
}

static int hwcap_inbox(HwyPass *hp, int x, int z) { return x > hp->x0 && z > hp->z0 && x < hp->x1 && z < hp->z1; }

/* the plain stock piece of an arm cell: straight lanes (15051 along x / 73 along z, the lower lane state 2), diagonal
 * middle (11224.0 / 15106.0) and outer cells (11223 / 15052, state 0 on the side where x - z, resp. x + z, grows) */
static void hwcap_plain(const HwcapArm *a, int lane, int odx, int odz, WORD *id, int *st) {
    if (!a->diag) {
        int low = (a->px + a->pz > 0) ? lane == 0 : lane == 1;      /* lane 1 = lane 0 + (px, pz) */
        *id = a->sz == 0 ? 15051 : 73;
        *st = low ? 2 : 0;
        return;
    }
    if (a->sx == a->sz) {                                          /* x - z family */
        if (!odx && !odz) { *id = 11224; *st = 0; return; }
        *id = 11223; *st = odx - odz > 0 ? 0 : 2;
    } else {
        if (!odx && !odz) { *id = 15106; *st = 0; return; }
        *id = 15052; *st = odx + odz > 0 ? 0 : 2;
    }
}

/* cells of an arm carried on to `rows` (row 0 = the cap row): calls fn for each cell to write, with its piece */
typedef int (*HwcapFn)(HwyPass *hp, int x, int z, WORD id, int st, int fresh_cell, void *ctx);

static int hwcap_walk(HwyPass *hp, const HwcapArm *a, int rows, HwcapFn fn, void *ctx) {
    int n, ok = 1;
    WORD id;
    int st;
    if (!a->diag) {
        for (n = 0; n <= rows + 1 && ok; n++) {
            int x = a->x + n * a->sx, z = a->z + n * a->sz, lane;
            for (lane = 0; lane < 2 && ok; lane++) {
                int lx = x + lane * a->px, lz = z + lane * a->pz;
                if (n <= rows) hwcap_plain(a, lane, 0, 0, &id, &st);
                else { id = lane ? a->cap1 : a->cap0; st = lane ? a->st1 : a->st0; }
                ok = fn(hp, lx, lz, id, st, n > 0, ctx);
            }
        }
        return ok;
    }
    for (n = 0; n <= rows + 1 && ok; n++) {
        int x = a->x + n * a->sx, z = a->z + n * a->sz;
        if (n <= rows) {
            hwcap_plain(a, 0, 0, 0, &id, &st);
            ok = fn(hp, x, z, id, st, n > 0, ctx);
            hwcap_plain(a, 0, a->sx, 0, &id, &st);                       /* the two outer cells toward the next middle */
            if (ok) ok = fn(hp, x + a->sx, z, id, st, 1, ctx);
            hwcap_plain(a, 0, 0, a->sz, &id, &st);
            if (ok) ok = fn(hp, x, z + a->sz, id, st, 1, ctx);
        } else ok = fn(hp, x, z, a->cap0, a->st0, 1, ctx);
    }
    return ok;
}

/* a cell the arm may be carried into: what the stock Highway tool builds on, not hwy_free. hwy_free adds the On-ramp
 * tool's terrain test (terrain vt+0xd0, FUN_10009c65), and that refuses lake-shore cells the Highway tool takes:
 * measured 2026-10-18 on Seoul, (251,116) (flat, dry, empty, the lake at (251,117)) failed hwy_free, while a stock drag
 * (249,117) -> (249,121) along the same shore built lanes x 248..249 with the lake at x 250. So: inside the map and off
 * its edge row, no highway, flat (FUN_10016ccd), not water (FUN_10016d69), the surface occupant none or trees (type 5,
 * the writer clears them), as in hwy_free. [UNCERTAIN: what else terrain vt+0xd0 refuses is not decoded] */
static int hwcap_free(HwyPass *hp, int x, int z) {
    int pos[3], ok;
    void *occ = NULL;
    if (x < 1 || z < 1 || x >= hp->W - 1 || z >= hp->H - 1 || hwy_at(hp, x, z)) return 0;
    pos[0] = x << 8; pos[1] = z << 8; pos[2] = 0;
    ok = ((PFN_HwyPos)(g_rb_m + 0x16ccd))(hp->mgr, 0, pos) && !((PFN_HwyPos)(g_rb_m + 0x16d69))(hp->mgr, 0, pos);
    if (ok && ((PFN_Get)VT(hp->lay, 0x78))(hp->lay, 0, pos, &occ) && occ) {
        ok = ((PFN_B0)VT(occ, 0x54))(occ) == 5;
        ((PFN_B0)VT(occ, 8))(occ);
    }
    if (ok && !hwy_free(hp, x, z))
        logf("hwcap: %s: (%d,%d) fails the On-ramp free-cell test (hwy_free) but takes a highway", hp->who, x, z);
    return ok;
}

static int hwcap_test_cell(HwyPass *hp, int x, int z, WORD id, int st, int fresh_cell, void *ctx) {
    (void)id; (void)st; (void)ctx;
    if (!hwcap_inbox(hp, x, z)) {
        _snprintf(g_hwcap_why, sizeof(g_hwcap_why), "carrying the arm on reaches (%d,%d), past the pass box", x, z);
        return 0;
    }
    if (hwy_claimed(x, z)) {
        _snprintf(g_hwcap_why, sizeof(g_hwcap_why), "carrying the arm on needs (%d,%d), claimed by another block", x, z);
        return 0;
    }
    if (fresh_cell && !hwcap_free(hp, x, z)) {
        int pos[3], fl, wa, ty = -1;
        void *occ = NULL;
        pos[0] = x << 8; pos[1] = z << 8; pos[2] = 0;
        fl = ((PFN_HwyPos)(g_rb_m + 0x16ccd))(hp->mgr, 0, pos) != 0;
        wa = ((PFN_HwyPos)(g_rb_m + 0x16d69))(hp->mgr, 0, pos) != 0;
        if (((PFN_Get)VT(hp->lay, 0x78))(hp->lay, 0, pos, &occ) && occ) {
            ty = ((PFN_B0)VT(occ, 0x54))(occ);
            ((PFN_B0)VT(occ, 8))(occ);
        }
        logf("hwcap: %s: (%d,%d) refused: highway %u, flat %d, water %d, occupant type %d", hp->who, x, z,
             hwy_id(hwy_at(hp, x, z)), fl, wa, ty);
        _snprintf(g_hwcap_why, sizeof(g_hwcap_why), "carrying the arm on needs (%d,%d), which is not free (%u)", x, z,
                  hwy_id(hwy_at(hp, x, z)));
        return 0;
    }
    return 1;
}

/* hwy_put without its hwy_free test (it refuses the shore cells hwcap_free takes): the same piece writer, buffer
 * re-read and keep */
static int hwcap_put_cell(HwyPass *hp, int x, int z, WORD id, int st, int fresh_cell, void *ctx) {
    DWORD cur = hwy_at(hp, x, z);
    int pos[3], bx = x - hp->b.x0, bz = z - hp->b.z0;
    (void)fresh_cell;
    if (cur && hwy_id(cur) == id && hwy_st(cur) == (st & 3)) { hwy_keep(hp, x, z); return 1; }
    if (!cur && !hwcap_free(hp, x, z)) {
        logf("### hwcap: %s: (%d,%d) is no longer free - stock piece %u.%d not written", hp->who, x, z, id, st);
        return 1;
    }
    pos[0] = x << 8; pos[1] = z << 8; pos[2] = 0;
    ((PFN_Put)(g_rb_m + 0x8919))(hp->mgr, 0, hp->lay, pos, ((DWORD)id << 8) | (DWORD)(st & 3), -1, 8, 0);
    if (bx >= 0 && bz >= 0 && bx < hp->b.w && bz < hp->b.h)
        hp->b.c[bz * hp->b.w + bx] = hwy_read(hp->mgr, hp->lay, x, z, hp->W, hp->H);
    hwy_keep(hp, x, z);
    hp->nput++;
    (*(int *)ctx)++;
    return 1;
}

static int hwcap_need(HwyPass *hp, HwcapSet *s, int x, int z, int sx, int sz, int tag) {
    DWORD v = hwcap_rd(hp, x, z);
    int c, k, diag = sx && sz, cx = 0, cz = 0, found = 0, rows, ai;
    HwcapArm arm;
    g_hwcap_why[0] = 0;
    if (v && !hwcap_is(v)) return 1;
    if (g_hwcap_off < 0) {
        g_hwcap_off = env_off("SC3NETMOD_HWCAP");
        logf("hwcap: %s", g_hwcap_off ? "off (SC3NETMOD_HWCAP=0)" : "on");
    }
    if (g_hwcap_off) { _snprintf(g_hwcap_why, sizeof(g_hwcap_why), "(%d,%d) holds %s (hwcap off)", x, z, v ? "an end cap" : "no highway"); return 0; }
    /* the arm's cap: walk back toward the interchange along the middle line (diagonal: from the cell or from the middle
     * cell before it) or the lane; only empty cells may lie between */
    for (c = 0; c < (diag ? 3 : 1) && !found; c++) {
        int bx = x - (c == 1 ? sx : 0), bz = z - (c == 2 ? sz : 0);
        for (k = 0; k <= HWCAP_REACH; k++) {
            int qx = bx - k * sx, qz = bz - k * sz, dx, dz;
            DWORD w = hwcap_rd(hp, qx, qz);
            if (!w) continue;
            if (hwcap_dir(w, &dx, &dz) && dx == sx && dz == sz) {
                int across = (x - qx) * sx - (z - qz) * sz;          /* diagonal: the cell lies in the cap's band */
                if (!diag || (across >= -1 && across <= 1)) { cx = qx; cz = qz; found = 1; }
            }
            break;
        }
    }
    if (!found) {
        _snprintf(g_hwcap_why, sizeof(g_hwcap_why), "(%d,%d) holds %s and no end cap of its arm lies behind it", x, z,
                  v ? "an end cap of another arm" : "no highway");
        return 0;
    }
    memset(&arm, 0, sizeof(arm));
    arm.x = (short)cx; arm.z = (short)cz; arm.sx = (signed char)sx; arm.sz = (signed char)sz; arm.diag = (BYTE)diag;
    v = hwcap_rd(hp, cx, cz);
    arm.cap0 = hwy_id(v); arm.st0 = (BYTE)hwy_st(v);
    if (!diag) {                                                     /* the other lane's cap, beside it */
        int j, dx, dz;
        for (j = -1; j <= 1; j += 2) {
            int ox = sz ? j : 0, oz = sx ? j : 0;
            DWORD w = hwcap_rd(hp, cx + ox, cz + oz);
            if (hwcap_dir(w, &dx, &dz) && dx == sx && dz == sz) {
                arm.px = (signed char)ox; arm.pz = (signed char)oz; arm.cap1 = hwy_id(w); arm.st1 = (BYTE)hwy_st(w);
                break;
            }
        }
        if (!arm.cap1) {
            _snprintf(g_hwcap_why, sizeof(g_hwcap_why), "end cap (%d,%d) has no second lane cap beside it", cx, cz);
            return 0;
        }
        if (arm.px + arm.pz < 0) {                                   /* key the arm on its lower lane: one per arm */
            WORD t = arm.cap0;
            BYTE u = arm.st0;
            arm.x = (short)(cx + arm.px); arm.z = (short)(cz + arm.pz);
            arm.px = (signed char)-arm.px; arm.pz = (signed char)-arm.pz;
            arm.cap0 = arm.cap1; arm.st0 = arm.st1; arm.cap1 = t; arm.st1 = u;
        }
        rows = (x - cx) * sx + (z - cz) * sz;
    } else rows = ((x - cx) * sx + (z - cz) * sz) / 2;                  /* middle k: 2k along; outer: 2k + 1 */
    if (!hwcap_walk(hp, &arm, rows, hwcap_test_cell, NULL)) return 0;
    for (ai = 0; ai < s->n; ai++) if (s->a[ai].x == arm.x && s->a[ai].z == arm.z) break;
    if (ai == s->n) {
        if (s->n >= HWCAP_ARMS) { _snprintf(g_hwcap_why, sizeof(g_hwcap_why), "too many arms to carry on"); return 0; }
        s->a[s->n++] = arm;
    }
    for (k = 0; k < s->nn; k++)
        if (s->need[k].arm == ai && s->need[k].tag == tag) { if (rows > s->need[k].rows) s->need[k].rows = (short)rows; return 2; }
    if (s->nn >= HWCAP_NEEDS) { _snprintf(g_hwcap_why, sizeof(g_hwcap_why), "too many cells to carry on"); return 0; }
    s->need[s->nn].arm = (BYTE)ai; s->need[s->nn].tag = (BYTE)tag; s->need[s->nn].rows = (short)rows;
    s->nn++;
    return 2;
}

/* -> arms carried on */
static int hwcap_commit(HwyPass *hp, HwcapSet *s, unsigned tags) {
    int ai, k, done = 0;
    for (ai = 0; ai < s->n; ai++) {
        int rows = -1, n = 0;
        const HwcapArm *a = &s->a[ai];
        for (k = 0; k < s->nn; k++)
            if (s->need[k].arm == ai && (tags & (1u << s->need[k].tag)) && s->need[k].rows > rows) rows = s->need[k].rows;
        if (rows < 0) continue;
        hwcap_walk(hp, a, rows, hwcap_put_cell, &n);
        done++;
        InterlockedIncrement(&g_hwcap_n_arm);
        InterlockedExchangeAdd(&g_hwcap_n_cell, n);
        logf("hwcap: %s: arm end %u.%d at (%d,%d) carried on %d row(s): cap now at (%d,%d), %d cells written", hp->who,
             a->cap0, a->st0, a->x, a->z, rows + 1, a->x + (rows + 1) * a->sx, a->z + (rows + 1) * a->sz, n);
    }
    return done;
}

static void hwcap_stats(void) {
    static LONG last;
    if (g_hwcap_n_arm == last) return;
    last = g_hwcap_n_arm;
    logf("stats: hwcap arms carried on=%ld, cells written=%ld", g_hwcap_n_arm, g_hwcap_n_cell);
}
