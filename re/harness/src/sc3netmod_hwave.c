/* sc3netmod_hwave.c - the HWAVE block of sc3netmod.dll (task hwave, highway program wave 2, 2026-10-19): a straight
 * highway that ends right at the end of a straight avenue lowers to the ground and goes on as the avenue.
 * #included by sc3netmod.c after the HWDX block; uses the HWY base (sc3netmod_hwy.c) and hwcap's cap table.
 * Evidence: verify/hwave/RESULTS.md; owner pictures MAIN\verify\hwave\owner_shots\hwave_plan.png / _mockup / _sheet.
 *
 * Stock (lab, in game, 2026-10-19, both drag orders, x and z): a highway dragged to an avenue's end, or an avenue
 * dragged to a highway's end, leaves the highway's cap row (z: 11235 / 11237, x: 15053 / 15054) right against the
 * avenue's U-turn row (11203 x 2), not connected. Neither tool builds onto the other network's cell.
 *
 * The transition (one set of four pieces, painted for state 0 = the avenue at +z; state k turns it k quarter turns,
 * (x, z) -> (-z, x) per turn as hwy_rot): with A = the entry carriageway's cap cell, E = rot_k(1, 0) (entry -> exit
 * carriageway), D = rot_k(0, 1) (highway -> avenue):
 *     A - D, A + E - D       plain highway (73 / 15051, driving toward the avenue in the exit column)     kept stock
 *     A, A + E               the cap row      -> T1 entry / T1 exit (deck H down to H/2)
 *     A + D, A + E + D       the U-turn row   -> T2 entry / T2 exit (H/2 down to the ground)
 *     A + 2D, A + E + 2D     avenue 11204                                                                   kept stock
 * The eight cells flat (FUN_10016ccd) at one height (terrain vt+0x4c, the vertex height FUN_1001a1f3 reads), none
 * claimed by another highway block, none on the map edge. Nothing else qualifies: a single road (its end is 11225), an
 * avenue one column off, a junction in the U-turn row (no longer 11203), a slope piece or interchange behind the cap.
 *
 * Classes (why the bases): a road node steps only onto road cells (flag 1) and a highway cell (flag 2) is entered only
 * from a ramp node (type 3) or a highway node; type 3 = cell flag 0x40 = occupant flag 0x200000 [CONFIRMED @ SimTransit
 * 0x10007a63, 0x100086e7, FUN_10005983], which only the on-ramp classes give (SIMNTWRK FUN_1001a5f2: ids
 * 15130..15141, kind 14 when also in the ROAD set, else kind 15). So T2 are variants of 15141 / 15140 (kind 14, road +
 * highway), T1 of 15137 / 15136 (kind 15), the layout of a stock on-ramp strip, and the package's `hwrc` lines make the
 * NETRAMP class mapping (sc3netmod.c) classify them as their bases. Offline (tiler.py, stock rules) those bases in the
 * two end rows are kept by both retiles, which turn the caps behind into 73 and leave the avenue 11204.
 *
 * When: every highway pass (rb_hwy: edit + load) and every ROAD pass (hwave_road from rb_pass: an avenue drag is a
 * ROAD retile; only this block runs there, nothing of the other blocks is reverted). A built transition whose pattern
 * breaks (a cell bulldozed, the avenue or the highway behind gone) goes back to the stock ends: each remaining piece
 * becomes its stock cap / 11203 (or is removed when its neighbour is gone), then a rect retile. SC3NETMOD_HWAVE=0:
 * every transition found is turned back that way, none is built.
 * Saves: the package's hwys lines save every piece as what stock leaves there (caps + 11203).
 *
 * Table line: hwave <T1 exit> <T1 entry> <T2 exit> <T2 entry>   (each needs its hwyp line; netpack "highway_lines")
 *
 * DIAGONAL (phase 2, owner 2026-10-19 "Keep it automatic and build the diagonal version"): a diagonal highway ending at
 * the end of a diagonal avenue (the DAV block's joined band, sc3netmod_dav.c) on the same middle line. Measured (lab,
 * verify/hwave/RESULTS.md 6): the highway's end = j-2 middle plain, j-1 both outer cells plain, j0 the cap on the
 * middle line, the far j+1 outer cell empty; the avenue's end (DAV pieces) holds road at j+1 (sometimes), j+2, j+3,
 * the plain 20500 from j+4 (j = cells along the band from the cap). One set of six pieces painted for state 0 = the
 * x - z family heading +x +z, turned by k for the four directions (k odd = the x + z family):
 *     offsets from the cap A (state 0, turned by hwy_rot): j-1 high (0,-1) / low (-1,0), j0 (0,0),
 *     j+1 high (1,0) / low (0,1), j+2 (1,1); j+3 high (2,1) / low (1,2) get DAV's plain outer 20505; j+4 (2,2) 20500
 *   roles 0..5 = j-1 high, j-1 low, j0, j+1 high, j+1 low, j+2. Deck H at j0's start, ground at j+3's (2.1 cells).
 *   j+2 is the only cell beside the avenue: a variant of the on-ramp road end (kind 14); the five others kind 15.
 * DAV re-tiles the band on every ROAD pass. It skips cells dbv_claimed() names (writer and revert); that function also
 * asks hwave_claimed() (one marked line in sc3netmod_dbv.c), the set of cells built diagonal transitions hold. In a
 * ROAD pass and the load pass HWAVE runs BEFORE DAV and again AFTER it. The run before only claims the cells of the
 * transitions already built (the stock ROAD retile of that same pass has just re-tiled DAV's cells as the stock
 * ladder, so nothing on the avenue side can be judged yet); the run after (and every highway pass) checks, keeps,
 * reverts and builds.
 * Table line: hwavd <j-1 high> <j-1 low> <j0> <j+1 high> <j+1 low> <j+2>   (hwyp lines first)
 */

/* task avmisc: avcore's sibling API (sc3netmod_avl.c, #included later; AVENUE_LANES.md 5) */
static int avl_dir(int x, int z);
static int avl_own(WORD id);
static int avl_band_ok(int x, int z, int away);

static WORD g_hwave_s[2];                      /* task avmisc: the straight ground row, 0 exit, 1 entry (one-way avenue) */
static WORD g_hwave_p[4];                      /* 0 T1 exit, 1 T1 entry, 2 T2 exit, 3 T2 entry */
static int g_hwave_off;
static int g_hwave_pre;                        /* the ROAD / load pass run before DAV: claim only */
static volatile LONG g_hwave_n_built, g_hwave_n_rev, g_hwave_n_ref;

typedef char (__fastcall *PFN_HwaveH)(void *ter, void *edx, int x, int z, BYTE *out);   /* terrain vt+0x4c ret 0xc */

static void hwave_line(const char *path, const char *line) {
    unsigned long v[4];
    int k;
    if (sscanf(line + 6, "%lu %lu %lu %lu", &v[0], &v[1], &v[2], &v[3]) != 4) {
        logf("### hwave: %s: bad line '%s'", path, line);
        return;
    }
    for (k = 0; k < 4; k++)
        if (!v[k] || v[k] > 0xffff || hwy_piece((WORD)v[k]) < 0) {
            logf("### hwave: %s: piece %lu has no hwyp line before this one - '%s' ignored", path, v[k], line);
            return;
        }
    for (k = 0; k < 4; k++) g_hwave_p[k] = (WORD)v[k];
    g_hwave_off = env_off("SC3NETMOD_HWAVE");
    logf("hwave: %s: highway <-> avenue transition pieces %u %u %u %u%s", path, g_hwave_p[0], g_hwave_p[1], g_hwave_p[2],
         g_hwave_p[3], g_hwave_off ? " - OFF (SC3NETMOD_HWAVE=0): built ones go back to stock" : "");
}

/* task avmisc: `hwavs <exit ground> <entry ground>` = the ground row for an avenue whose halves are one-way (no lane
   swap, AVENUE_LANES.md): used where avl_band_ok() says the avenue band converts, else the crossover set above */
static void hwavs_line(const char *path, const char *line) {
    unsigned long v[2];
    int k;
    if (sscanf(line + 6, "%lu %lu", &v[0], &v[1]) != 2) { logf("### hwave: %s: bad line '%s'", path, line); return; }
    for (k = 0; k < 2; k++)
        if (!v[k] || v[k] > 0xffff || hwy_piece((WORD)v[k]) < 0) {
            logf("### hwave: %s: piece %lu has no hwyp line before this one - '%s' ignored", path, v[k], line);
            return;
        }
    for (k = 0; k < 2; k++) g_hwave_s[k] = (WORD)v[k];
    logf("hwave: %s: straight ground row pieces %u %u (one-way avenue)", path, g_hwave_s[0], g_hwave_s[1]);
}

/* the stock piece of each pattern cell at turn k, column c (0 entry, 1 exit): measured, see the header */
static void hwave_plain(int k, int c, WORD *id, int *st) { *id = (k & 1) ? 15051 : 73; *st = ((k < 2) == (c == 1)) ? 0 : 2; }
static void hwave_cap(int k, int c, WORD *id, int *st) {
    *id = (k & 1) ? (c ? 15054 : 15053) : (c ? 11237 : 11235);
    *st = k < 2 ? 0 : 2;
}
static int hwave_uturn_st(int k, int c) { return c ? k : (k + 3) & 3; }
static int hwave_ave_st(int k, int c) { return c ? (k + 3) & 3 : (k + 1) & 3; }

static DWORD hwave_road_at(HwyPass *hp, int x, int z) { return rb_read(hp->mgr, hp->lay, x, z, hp->W, hp->H); }

static int hwave_is(DWORD v, WORD id, int st) { return v && hwy_id(v) == id && hwy_st(v) == st; }

/* task avmisc: the stock piece `base` at state st, or avcore's one-way variant of it (a converted avenue: 21700 for 11204,
   the U-turn quarter 21701 for 11203; written at the same state, saved as the base) */
static int hwave_isb(DWORD v, WORD base, int st) {
    return v && hwy_st(v) == st && (hwy_id(v) == base || (avl_own(hwy_id(v)) && g_base[hwy_id(v)] == base));
}

static int hwave_height(HwyPass *hp, int x, int z) {
    void *ter = *(void **)(hp->mgr + 0x30);
    BYTE h = 0;
    if (!ter) return -1;
    ((PFN_HwaveH)VT(ter, 0x4c))(ter, 0, x, z, &h);
    return h;
}

/* cell (x, z) of column c, row r (-1 behind, 0 cap row, 1 U-turn row, 2 avenue) of the transition at anchor A, turn k */
static void hwave_cell(int ax, int az, int k, int c, int r, int *x, int *z) {
    int ex = 1, ez = 0, dx = 0, dz = 1;
    hwy_rot(k, &ex, &ez);
    hwy_rot(k, &dx, &dz);
    *x = ax + c * ex + r * dx;
    *z = az + c * ez + r * dz;
}

/* -> NULL when the transition at (ax, az) turn k qualifies (stock ends or our pieces in the two end rows), else why */
static const char *hwave_check(HwyPass *hp, int ax, int az, int k) {
    int c, r, x, z, st, h0 = -1;
    WORD id;
    for (c = 0; c < 2; c++) {
        hwave_cell(ax, az, k, c, -1, &x, &z);
        hwave_plain(k, c, &id, &st);
        if (!hwave_is(hwy_at(hp, x, z), id, st)) return "no plain highway behind the cap row";
        hwave_cell(ax, az, k, c, 0, &x, &z);
        hwave_cap(k, c, &id, &st);
        if (!hwave_is(hwy_at(hp, x, z), id, st) && !hwave_is(hwy_at(hp, x, z), g_hwave_p[1 - c], k))
            return "cap row";
        hwave_cell(ax, az, k, c, 1, &x, &z);
        if (!hwave_isb(hwave_road_at(hp, x, z), 11203, hwave_uturn_st(k, c)) &&
            !hwave_is(hwy_at(hp, x, z), g_hwave_p[3 - c], k) &&
            !(g_hwave_s[0] && hwave_is(hwy_at(hp, x, z), g_hwave_s[1 - c], k)))      /* task avmisc */
            return "no avenue U-turn row past the cap";
        hwave_cell(ax, az, k, c, 2, &x, &z);
        if (!hwave_isb(hwave_road_at(hp, x, z), 11204, hwave_ave_st(k, c))) return "no straight avenue past the U-turn row";
    }
    for (c = 0; c < 2; c++)
        for (r = -1; r <= 2; r++) {
            int pos[3];
            hwave_cell(ax, az, k, c, r, &x, &z);
            if (x < 1 || z < 1 || x >= hp->W - 1 || z >= hp->H - 1) return "map edge";
            if (hwy_claimed(x, z)) return "a cell is taken by another highway block";
            pos[0] = x << 8; pos[1] = z << 8; pos[2] = 0;
            if (!((PFN_HwyPos)(g_rb_m + 0x16ccd))(hp->mgr, 0, pos)) return "not flat";
            if (h0 < 0) h0 = hwave_height(hp, x, z);
            else if (hwave_height(hp, x, z) != h0) return "height step";
        }
    return NULL;
}

/* write piece.state into any cell (FUN_10008919 replaces the removable occupant, road or highway [CONFIRMED @
   0x10008919]) and refresh the pass buffer; keep = claim + keep it for hwy_end */
static int hwave_write(HwyPass *hp, int x, int z, WORD id, int st, int keep) {
    int pos[3], bx = x - hp->b.x0, bz = z - hp->b.z0;
    DWORD cur = hwy_at(hp, x, z);
    if (keep && hwave_is(cur, id, st)) { hwy_keep(hp, x, z); return 0; }
    pos[0] = x << 8; pos[1] = z << 8; pos[2] = 0;
    ((PFN_Put)(g_rb_m + 0x8919))(hp->mgr, 0, hp->lay, pos, ((DWORD)id << 8) | (DWORD)(st & 3), -1, 8, 0);
    if (bx >= 0 && bz >= 0 && bx < hp->b.w && bz < hp->b.h)
        hp->b.c[bz * hp->b.w + bx] = hwy_read(hp->mgr, hp->lay, x, z, hp->W, hp->H);
    if (keep) hwy_keep(hp, x, z);
    hp->nput++;
    return 1;
}

static void hwave_remove(HwyPass *hp, int x, int z) {
    void *occ = NULL;
    int bx = x - hp->b.x0, bz = z - hp->b.z0;
    if (((PFN_HwyAt)VT(hp->lay, 0x7c))(hp->lay, 0, x, z, &occ) && occ) {
        ((PFN_HwyRemove)VT(hp->mgr, 0xb8))(hp->mgr, 0, hp->lay, occ);
        ((PFN_B0)VT(occ, 8))(occ);
    }
    if (bx >= 0 && bz >= 0 && bx < hp->b.w && bz < hp->b.h) hp->b.c[bz * hp->b.w + bx] = 0;
}

/* back to the stock ends: each of our pieces of the transition at (ax, az) turn k becomes the stock cap / U-turn its
   row had (removed when the highway behind / the avenue past it is gone), then one rect retile over the rows */
static void hwave_revert(HwyPass *hp, int ax, int az, int k, const char *why) {
    int c, r, x, z, nx, nz, st, n = 0, rect[6], x0 = 1 << 30, z0 = 1 << 30, x1 = -1, z1 = -1;
    WORD id;
    for (c = 0; c < 2; c++)
        for (r = 0; r <= 1; r++) {
            hwave_cell(ax, az, k, c, r, &x, &z);
            if (!hwave_is(hwy_at(hp, x, z), g_hwave_p[r * 2 + (1 - c)], k) &&
                !(r && g_hwave_s[0] && hwave_is(hwy_at(hp, x, z), g_hwave_s[1 - c], k))) continue;     /* task avmisc */
            hwave_cell(ax, az, k, c, r ? 2 : -1, &nx, &nz);
            if (r == 0 && hwy_at(hp, nx, nz)) { hwave_cap(k, c, &id, &st); hwave_write(hp, x, z, id, st, 0); }
            else if (r == 1 && hwave_road_at(hp, nx, nz)) hwave_write(hp, x, z, 11203, hwave_uturn_st(k, c), 0);
            else hwave_remove(hp, x, z);
            hwy_claim(hp, x, z);
            n++;
            if (x < x0) x0 = x;
            if (z < z0) z0 = z;
            if (x > x1) x1 = x;
            if (z > z1) z1 = z;
        }
    if (!n) return;
    rect[0] = (x0 - 1) << 8; rect[1] = (z0 - 1) << 8; rect[2] = 0; rect[3] = (x1 + 1) << 8; rect[4] = (z1 + 1) << 8; rect[5] = 0;
    ((PFN_Retile)VT(hp->mgr, 0xb0))(hp->mgr, 0, rect, 3);
    hp->nrev++;
    InterlockedIncrement(&g_hwave_n_rev);
    logf("hwave: %s: transition at (%d,%d) turn %d %s -> %d piece(s) back to the stock ends", hp->who, ax, az, k, why, n);
}

static int hwave_build(HwyPass *hp, int ax, int az, int k) {
    int c, r, x, z, n = 0, ow = 0, dx, dz;
    if (g_hwave_s[0]) {                           /* task avmisc: a converted avenue band takes the straight ground row */
        hwave_cell(ax, az, k, 1, 2, &x, &z);
        dx = 0; dz = 1;                           /* highway -> avenue step, as avcore's N E S W */
        hwy_rot(k, &dx, &dz);
        ow = avl_band_ok(x, z, dz < 0 ? 0 : dx > 0 ? 1 : dz > 0 ? 2 : 3);
    }
    for (c = 0; c < 2; c++)
        for (r = 0; r <= 1; r++) {
            hwave_cell(ax, az, k, c, r, &x, &z);
            n += hwave_write(hp, x, z, (r && ow) ? g_hwave_s[1 - c] : g_hwave_p[r * 2 + (1 - c)], k, 1);
        }
    for (c = 0; c < 2; c++)                       /* the rows either side stay as they are: claim them for this pass */
        for (r = -1; r <= 2; r += 3) { hwave_cell(ax, az, k, c, r, &x, &z); hwy_claim(hp, x, z); }
    return n;
}

#define HWAVE_MAXA 256

static void hwavd_run(HwyPass *hp);

static void hwave_run(HwyPass *hp) {
    int x, z, k, j, na = 0, ex, ez, dx, dz;
    struct { short x, z; BYTE k; } an[HWAVE_MAXA];
    hwavd_run(hp);                                /* phase 2: the diagonal ones */
    if (!g_hwave_p[0] || g_hwave_pre) return;     /* the straight ones need no claims: nothing to do before DAV */
    /* 1. transitions already built: every piece names its anchor */
    for (z = hp->z0 + 3; z <= hp->z1 - 3; z++)
        for (x = hp->x0 + 3; x <= hp->x1 - 3; x++) {
            DWORD v = hwy_at(hp, x, z);
            int role, ax, az, seen = 0;
            if (!v) continue;
            for (role = 0; role < 4 && hwy_id(v) != g_hwave_p[role]; role++) ;
            if (role == 4 && g_hwave_s[0]) {          /* task avmisc: the straight ground row: roles 2 (exit) / 3 (entry) */
                if (hwy_id(v) == g_hwave_s[0]) role = 2;
                else if (hwy_id(v) == g_hwave_s[1]) role = 3;
            }
            if (role == 4) continue;
            k = hwy_st(v);
            ex = 1; ez = 0; dx = 0; dz = 1;
            hwy_rot(k, &ex, &ez);
            hwy_rot(k, &dx, &dz);
            ax = x - (role == 0 || role == 2 ? ex : 0) - (role >= 2 ? dx : 0);
            az = z - (role == 0 || role == 2 ? ez : 0) - (role >= 2 ? dz : 0);
            for (j = 0; j < na; j++) seen |= an[j].x == ax && an[j].z == az && an[j].k == k;
            if (!seen && na < HWAVE_MAXA) { an[na].x = (short)ax; an[na].z = (short)az; an[na].k = (BYTE)k; na++; }
        }
    for (j = 0; j < na; j++) {
        const char *why = g_hwave_off ? "SC3NETMOD_HWAVE=0" : hwave_check(hp, an[j].x, an[j].z, an[j].k);
        if (why) hwave_revert(hp, an[j].x, an[j].z, an[j].k, why);
        else if (hwave_build(hp, an[j].x, an[j].z, an[j].k) > 0)
            logf("hwave: %s: transition at (%d,%d) turn %d: missing pieces put back", hp->who, an[j].x, an[j].z, an[j].k);
    }
    if (g_hwave_off) return;
    /* 2. new ones: a stock cap in the entry column whose sibling is the exit column's cap */
    for (z = hp->z0 + 3; z <= hp->z1 - 3; z++)
        for (x = hp->x0 + 3; x <= hp->x1 - 3; x++) {
            DWORD v = hwy_at(hp, x, z);
            int sx, sz, st, n;
            WORD id;
            const char *why;
            if (!v || hwy_claimed(x, z) || !hwcap_dir(v, &sx, &sz) || (sx && sz)) continue;
            for (k = 0; k < 4; k++) { dx = 0; dz = 1; hwy_rot(k, &dx, &dz); if (dx == sx && dz == sz) break; }
            if (k == 4) continue;
            hwave_cap(k, 0, &id, &st);
            if (!hwave_is(v, id, st)) continue;           /* only the entry column's cap: it is the anchor */
            hwave_cell(x, z, k, 0, 1, &ex, &ez);
            if (!hwave_road_at(hp, ex, ez)) continue;     /* nothing past the cap: an ordinary highway end, say nothing */
            why = hwave_check(hp, x, z, k);
            if (why) {
                InterlockedIncrement(&g_hwave_n_ref);
                logf("hwave: %s: highway end at (%d,%d) turn %d beside a road: refused (%s)", hp->who, x, z, k, why);
                continue;
            }
            n = hwave_build(hp, x, z, k);
            InterlockedIncrement(&g_hwave_n_built);
            logf("hwave: %s: highway end at (%d,%d) turn %d -> transition to the avenue, %d cell(s) written", hp->who, x, z,
                 k, n);
        }
}


/* ================================================================ diagonal (phase 2) */
static WORD g_hwavd_p[6];                      /* j-1 high, j-1 low, j0, j+1 high, j+1 low, j+2 */
static const signed char HWAVD_OFF[6][2] = { { 0, -1 }, { -1, 0 }, { 0, 0 }, { 1, 0 }, { 0, 1 }, { 1, 1 } };
static volatile LONG g_hwavd_n_built, g_hwavd_n_rev;

/* the cells built diagonal transitions hold, kept across passes (DAV asks hwave_claimed through dbv_claimed) */
#define HWAVE_CL 4096
static DWORD g_hwave_cl[HWAVE_CL];
static int g_hwave_ncl;

static DWORD hwave_key(int x, int z) { return ((DWORD)(x & 0xfff) << 12 | (DWORD)(z & 0xfff)) + 1; }
static DWORD hwave_hash(int x, int z) { return (((DWORD)x * 2654435761UL) ^ ((DWORD)z * 40503UL)) & (HWAVE_CL - 1); }

static int hwave_claimed(int x, int z) {
    DWORD k = hwave_key(x, z), h = hwave_hash(x, z);
    if (!g_hwave_ncl || x < 0 || z < 0) return 0;
    while (g_hwave_cl[h]) {
        if (g_hwave_cl[h] == k) return 1;
        h = (h + 1) & (HWAVE_CL - 1);
    }
    return 0;
}

static void hwave_cl_set(int x, int z, int on) {
    DWORD k = hwave_key(x, z), h = hwave_hash(x, z), j;
    if (x < 0 || z < 0) return;
    while (g_hwave_cl[h] && g_hwave_cl[h] != k) h = (h + 1) & (HWAVE_CL - 1);
    if (on) {
        if (!g_hwave_cl[h] && g_hwave_ncl < HWAVE_CL / 2) { g_hwave_cl[h] = k; g_hwave_ncl++; }
        return;
    }
    if (!g_hwave_cl[h]) return;
    g_hwave_cl[h] = 0;                          /* delete, then re-insert the probe run after it (linear probing) */
    g_hwave_ncl--;
    for (j = (h + 1) & (HWAVE_CL - 1); g_hwave_cl[j]; j = (j + 1) & (HWAVE_CL - 1)) {
        DWORD v = g_hwave_cl[j];
        g_hwave_cl[j] = 0;
        g_hwave_ncl--;
        hwave_cl_set((int)((v - 1) >> 12), (int)((v - 1) & 0xfff), 1);
    }
}

static void hwavd_line(const char *path, const char *line) {
    unsigned long v[6];
    int k;
    if (sscanf(line + 6, "%lu %lu %lu %lu %lu %lu", &v[0], &v[1], &v[2], &v[3], &v[4], &v[5]) != 6) {
        logf("### hwave: %s: bad diagonal line '%s'", path, line);
        return;
    }
    for (k = 0; k < 6; k++)
        if (!v[k] || v[k] > 0xffff || hwy_piece((WORD)v[k]) < 0) {
            logf("### hwave: %s: piece %lu has no hwyp line before this one - '%s' ignored", path, v[k], line);
            return;
        }
    for (k = 0; k < 6; k++) g_hwavd_p[k] = (WORD)v[k];
    g_hwave_off = env_off("SC3NETMOD_HWAVE");
    logf("hwave: %s: diagonal transition pieces %u %u %u %u %u %u", path, g_hwavd_p[0], g_hwavd_p[1], g_hwavd_p[2],
         g_hwavd_p[3], g_hwavd_p[4], g_hwavd_p[5]);
}

static void hwavd_cell(int ax, int az, int k, int dx, int dz, int *x, int *z) {
    hwy_rot(k, &dx, &dz);
    *x = ax + dx; *z = az + dz;
}

/* stock pieces at turn k (measured, header): the band's outer cells (high = role 0 side, low = role 1), middle, cap */
static void hwavd_plain(int k, int high, WORD *id, int *st) {
    *id = (k & 1) ? 15052 : 11223;
    *st = ((k < 2) == (high != 0)) ? 0 : 2;
}
static WORD hwavd_mid(int k) { return (k & 1) ? 15106 : 11224; }
static void hwavd_cap(int k, WORD *id, int *st) { *id = (k & 1) ? 15059 : 14999; *st = k < 2 ? 2 : 0; }
static int hwavd_outer_st(int k, int high) { return high ? k : (k + 2) & 3; }    /* DAV 20505 / stock 35 */

/* a DAV band piece (plain or an end combo, not a junction, merge or crossing), or a stock diagonal road / its caps */
static int hwavd_dav_road(WORD id) {
    int k;
    if (id == 35 || id == 18004 || id == 1999) return 1;
    for (k = 0; k < g_dav_nmid; k++) if (g_dav_mid[k].piece == id) return 1;
    return dav_is_role(id);          /* task avdiag: DAV's one-way end pieces (U-turn / no-lane cells) */
}

static WORD g_hwavd_outer, g_hwavd_middle;     /* DAV's plain outer / middle pieces (20505 / 20500 in its package) */

static int hwavd_dav_pieces(void) {
    int k;
    if (g_hwavd_outer && g_hwavd_middle) return 1;
    for (k = 0; k < g_dav_nmid; k++) {
        if (g_dav_mid[k].b == 0 && g_dav_mid[k].a == 35) g_hwavd_outer = g_dav_mid[k].piece;
        if (g_dav_mid[k].a == 35 && g_dav_mid[k].b == 35 && g_dav_mid[k].delta == 2) g_hwavd_middle = g_dav_mid[k].piece;
    }
    return g_hwavd_outer && g_hwavd_middle;
}

static int hwavd_ours(DWORD v, int role, int k) { return hwave_is(v, g_hwavd_p[role], k); }

/* -> NULL when the diagonal transition at cap cell (ax, az) turn k qualifies (stock / DAV ends or our pieces), else why */
static const char *hwavd_check(HwyPass *hp, int ax, int az, int k) {
    int x, z, st, j, h0 = -1, side;
    WORD id;
    DWORD v, rv;
    static const signed char ALL[10][2] = { { -1, -1 }, { 0, -1 }, { -1, 0 }, { 0, 0 }, { 1, 0 }, { 0, 1 }, { 1, 1 },
                                            { 2, 1 }, { 1, 2 }, { 2, 2 } };
    if (!g_dav_on || !hwavd_dav_pieces()) return "no diagonal avenue block (DAV)";
    hwavd_cell(ax, az, k, -1, -1, &x, &z);
    if (!hwave_is(hwy_at(hp, x, z), hwavd_mid(k), 0)) return "no plain highway band behind the cap";
    for (side = 0; side < 2; side++) {                           /* j-1: the plain band (or ours) */
        hwavd_cell(ax, az, k, HWAVD_OFF[side][0], HWAVD_OFF[side][1], &x, &z);
        hwavd_plain(k, side == 0, &id, &st);
        v = hwy_at(hp, x, z);
        if (!hwave_is(v, id, st) && !hwavd_ours(v, side, k)) return "no plain highway band beside the cap";
    }
    hwavd_cap(k, &id, &st);
    v = hwy_at(hp, ax, az);
    if (!hwave_is(v, id, st) && !hwavd_ours(v, 2, k)) return "cap";
    hwavd_cell(ax, az, k, 1, 0, &x, &z);                          /* j+1 high: empty land or ours */
    v = hwy_at(hp, x, z);
    if (v ? !hwavd_ours(v, 3, k) : (hwave_road_at(hp, x, z) || !hwy_free(hp, x, z))) return "the cell past the cap is taken";
    hwavd_cell(ax, az, k, 0, 1, &x, &z);                          /* j+1 low: empty, a DAV end piece, or ours */
    v = hwy_at(hp, x, z);
    rv = hwave_road_at(hp, x, z);
    if (v ? !hwavd_ours(v, 4, k) : (rv ? !hwavd_dav_road(hwy_id(rv)) : !hwy_free(hp, x, z)))
        return "the avenue's end cell beside the cap is taken";
    hwavd_cell(ax, az, k, 1, 1, &x, &z);                          /* j+2: the avenue's end (road) or ours */
    v = hwy_at(hp, x, z);
    rv = hwave_road_at(hp, x, z);
    if (v ? !hwavd_ours(v, 5, k) : (!rv || !hwavd_dav_road(hwy_id(rv)))) return "no avenue end past the cap";
    for (j = 0; j < 2; j++) {                                     /* j+3: road (the build makes it DAV's plain outer) */
        hwavd_cell(ax, az, k, j ? 1 : 2, j ? 2 : 1, &x, &z);
        if (hwy_at(hp, x, z) || !hwave_road_at(hp, x, z)) return "no avenue band two cells past the cap";
    }
    hwavd_cell(ax, az, k, 2, 2, &x, &z);                          /* j+4: the plain middle 20500 */
    if (hwy_id(hwave_road_at(hp, x, z)) != g_hwavd_middle) return "no plain avenue band (DAV middle piece) past the end";
    for (j = 0; j < 10; j++) {
        int pos[3];
        hwavd_cell(ax, az, k, ALL[j][0], ALL[j][1], &x, &z);
        if (x < 1 || z < 1 || x >= hp->W - 1 || z >= hp->H - 1) return "map edge";
        if (j >= 1 && j <= 8 && hwy_claimed(x, z)) return "a cell is taken by another highway block";
        pos[0] = x << 8; pos[1] = z << 8; pos[2] = 0;
        if (!((PFN_HwyPos)(g_rb_m + 0x16ccd))(hp->mgr, 0, pos)) return "not flat";
        if (h0 < 0) h0 = hwave_height(hp, x, z);
        else if (hwave_height(hp, x, z) != h0) return "height step";
    }
    return NULL;
}

static void hwavd_claim_all(int ax, int az, int k, int on) {
    static const signed char C8[8][2] = { { 0, -1 }, { -1, 0 }, { 0, 0 }, { 1, 0 }, { 0, 1 }, { 1, 1 }, { 2, 1 }, { 1, 2 } };
    int j, x, z;
    for (j = 0; j < 8; j++) { hwavd_cell(ax, az, k, C8[j][0], C8[j][1], &x, &z); hwave_cl_set(x, z, on); }
}

static int hwavd_build(HwyPass *hp, int ax, int az, int k) {
    int j, x, z, n = 0;
    for (j = 0; j < 6; j++) {
        hwavd_cell(ax, az, k, HWAVD_OFF[j][0], HWAVD_OFF[j][1], &x, &z);
        n += hwave_write(hp, x, z, g_hwavd_p[j], k, 1);
    }
    for (j = 0; j < 2; j++) {                     /* j+3: DAV's plain outer piece where DAV left an end cap */
        int st = hwavd_outer_st(k, j == 0);
        hwavd_cell(ax, az, k, j ? 1 : 2, j ? 2 : 1, &x, &z);
        if (!hwave_is(hwave_road_at(hp, x, z), g_hwavd_outer, st)) { hwave_write(hp, x, z, g_hwavd_outer, st, 0); n++; }
        hwy_claim(hp, x, z);
    }
    hwavd_cell(ax, az, k, -1, -1, &x, &z);
    hwy_claim(hp, x, z);
    hwavd_claim_all(ax, az, k, 1);
    return n;
}

/* back to the stock ends: j-1 plain band and j0 the cap (when the band behind is still there, else removed), j+1
   removed (stock leaves the far one empty; DAV re-tiles its own end), j+2 a stock diagonal road 35; then a rect retile
   and, with DAV on, DAV over the area so the avenue's end gets its own pieces again */
static void hwavd_revert(HwyPass *hp, int ax, int az, int k, const char *why) {
    int j, x, z, bx, bz, n = 0, rect[6], x0 = 1 << 30, z0 = 1 << 30, x1 = -1, z1 = -1, behind, st;
    WORD id;
    hwavd_cell(ax, az, k, -1, -1, &bx, &bz);
    behind = hwy_at(hp, bx, bz) != 0;
    for (j = 0; j < 6; j++) {
        hwavd_cell(ax, az, k, HWAVD_OFF[j][0], HWAVD_OFF[j][1], &x, &z);
        if (!hwavd_ours(hwy_at(hp, x, z), j, k)) continue;
        if (j <= 1 && behind) { hwavd_plain(k, j == 0, &id, &st); hwave_write(hp, x, z, id, st, 0); }
        else if (j == 2 && behind) { hwavd_cap(k, &id, &st); hwave_write(hp, x, z, id, st, 0); }
        else if (j == 5) hwave_write(hp, x, z, 35, hwavd_outer_st(k, 0), 0);
        else hwave_remove(hp, x, z);
        hwy_claim(hp, x, z);
        n++;
        if (x < x0) x0 = x;
        if (z < z0) z0 = z;
        if (x > x1) x1 = x;
        if (z > z1) z1 = z;
    }
    hwavd_claim_all(ax, az, k, 0);
    if (!n) return;
    rect[0] = (x0 - 1) << 8; rect[1] = (z0 - 1) << 8; rect[2] = 0; rect[3] = (x1 + 1) << 8; rect[4] = (z1 + 1) << 8; rect[5] = 0;
    ((PFN_Retile)VT(hp->mgr, 0xb0))(hp->mgr, 0, rect, 3);
    if (g_dav_on) dav_run(hp->mgr, x0 - 3, z0 - 3, x1 + 3, z1 + 3, "hwave revert");
    hp->nrev++;
    InterlockedIncrement(&g_hwavd_n_rev);
    logf("hwave: %s: diagonal transition at (%d,%d) turn %d %s -> %d piece(s) back to the stock ends", hp->who, ax, az, k,
         why, n);
}

static void hwavd_run(HwyPass *hp) {
    int x, z, k, j, na = 0;
    struct { short x, z; BYTE k; } an[HWAVE_MAXA];
    if (!g_hwavd_p[0]) return;
    for (z = hp->z0 + 3; z <= hp->z1 - 3; z++)                    /* 1. built ones: each piece names its cap */
        for (x = hp->x0 + 3; x <= hp->x1 - 3; x++) {
            DWORD v = hwy_at(hp, x, z);
            int role, ax, az, dx, dz, seen = 0;
            if (!v) continue;
            for (role = 0; role < 6 && hwy_id(v) != g_hwavd_p[role]; role++) ;
            if (role == 6) continue;
            k = hwy_st(v);
            dx = HWAVD_OFF[role][0]; dz = HWAVD_OFF[role][1];
            hwy_rot(k, &dx, &dz);
            ax = x - dx; az = z - dz;
            for (j = 0; j < na; j++) seen |= an[j].x == ax && an[j].z == az && an[j].k == k;
            if (!seen && na < HWAVE_MAXA) { an[na].x = (short)ax; an[na].z = (short)az; an[na].k = (BYTE)k; na++; }
        }
    for (j = 0; j < na; j++) {
        const char *why;
        if (g_hwave_pre) { hwavd_claim_all(an[j].x, an[j].z, an[j].k, 1); continue; }   /* before DAV: claim only */
        why = g_hwave_off ? "SC3NETMOD_HWAVE=0" : hwavd_check(hp, an[j].x, an[j].z, an[j].k);
        if (why) hwavd_revert(hp, an[j].x, an[j].z, an[j].k, why);
        else if (hwavd_build(hp, an[j].x, an[j].z, an[j].k) > 0)
            logf("hwave: %s: diagonal transition at (%d,%d) turn %d: missing pieces put back", hp->who, an[j].x, an[j].z,
                 an[j].k);
    }
    if (g_hwave_off || g_hwave_pre) return;
    for (z = hp->z0 + 3; z <= hp->z1 - 3; z++)                    /* 2. new ones: a diagonal cap with road past it */
        for (x = hp->x0 + 3; x <= hp->x1 - 3; x++) {
            DWORD v = hwy_at(hp, x, z);
            int sx, sz, n, ex, ez;
            const char *why;
            if (!v || hwy_claimed(x, z) || !hwcap_dir(v, &sx, &sz) || !(sx && sz)) continue;
            for (k = 0; k < 4; k++) { int dx = 1, dz = 1; hwy_rot(k, &dx, &dz); if (dx == sx && dz == sz) break; }
            if (k == 4) continue;
            hwavd_cell(x, z, k, 1, 1, &ex, &ez);
            if (!hwave_road_at(hp, ex, ez)) continue;     /* no road two cells past the cap: an ordinary highway end */
            why = hwavd_check(hp, x, z, k);
            if (why) {
                InterlockedIncrement(&g_hwave_n_ref);
                logf("hwave: %s: diagonal highway end at (%d,%d) turn %d beside a road: refused (%s)", hp->who, x, z, k, why);
                continue;
            }
            n = hwavd_build(hp, x, z, k);
            InterlockedIncrement(&g_hwavd_n_built);
            logf("hwave: %s: diagonal highway end at (%d,%d) turn %d -> transition to the diagonal avenue, %d cell(s) "
                 "written", hp->who, x, z, k, n);
        }
}

/* a ROAD pass (an avenue drag or edit): this block alone, on the HWY base's buffer, without hwy_end (whose reverts
   are for highway passes, where every highway block has run) */
static void hwave_road(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who, int pre) {
    HwyPass *hp;
    if (!g_hwave_p[0] && !g_hwavd_p[0]) return;
    if (!strcmp(who, "load")) { ZeroMemory(g_hwave_cl, sizeof(g_hwave_cl)); g_hwave_ncl = 0; }   /* a new city */
    hp = hwy_begin(mgr, x0, z0, x1, z1, who);
    if (!hp) return;
    g_hwave_pre = pre;
    hwave_run(hp);
    g_hwave_pre = 0;
    if (hp->nput || hp->nrev)
        logf("hwave: %s pass over (%d,%d)-(%d,%d): %d written, %d reverted", who, hp->x0, hp->z0, hp->x1, hp->z1,
             hp->nput, hp->nrev);
    VirtualFree(hp->b.c, 0, MEM_RELEASE);
    hp->b.c = NULL;
}

static void hwave_stats(void) {
    static LONG last;
    LONG n = g_hwave_n_built + g_hwave_n_rev + g_hwave_n_ref + g_hwavd_n_built + g_hwavd_n_rev;
    if ((!g_hwave_p[0] && !g_hwavd_p[0]) || n == last) return;
    last = n;
    logf("stats: hwave transitions built=%ld, reverted=%ld, diagonal built=%ld, reverted=%ld, refused=%ld, cells held=%d",
         g_hwave_n_built, g_hwave_n_rev, g_hwavd_n_built, g_hwavd_n_rev, g_hwave_n_ref, g_hwave_ncl);
}
