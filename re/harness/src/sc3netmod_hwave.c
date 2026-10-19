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
 */

static WORD g_hwave_p[4];                      /* 0 T1 exit, 1 T1 entry, 2 T2 exit, 3 T2 entry */
static int g_hwave_off;
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
        if (!hwave_is(hwave_road_at(hp, x, z), 11203, hwave_uturn_st(k, c)) &&
            !hwave_is(hwy_at(hp, x, z), g_hwave_p[3 - c], k))
            return "no avenue U-turn row past the cap";
        hwave_cell(ax, az, k, c, 2, &x, &z);
        if (!hwave_is(hwave_road_at(hp, x, z), 11204, hwave_ave_st(k, c))) return "no straight avenue past the U-turn row";
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
            if (!hwave_is(hwy_at(hp, x, z), g_hwave_p[r * 2 + (1 - c)], k)) continue;
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
    int c, r, x, z, n = 0;
    for (c = 0; c < 2; c++)
        for (r = 0; r <= 1; r++) {
            hwave_cell(ax, az, k, c, r, &x, &z);
            n += hwave_write(hp, x, z, g_hwave_p[r * 2 + (1 - c)], k, 1);
        }
    for (c = 0; c < 2; c++)                       /* the rows either side stay as they are: claim them for this pass */
        for (r = -1; r <= 2; r += 3) { hwave_cell(ax, az, k, c, r, &x, &z); hwy_claim(hp, x, z); }
    return n;
}

#define HWAVE_MAXA 256

static void hwave_run(HwyPass *hp) {
    int x, z, k, j, na = 0, ex, ez, dx, dz;
    struct { short x, z; BYTE k; } an[HWAVE_MAXA];
    if (!g_hwave_p[0]) return;
    /* 1. transitions already built: every piece names its anchor */
    for (z = hp->z0 + 3; z <= hp->z1 - 3; z++)
        for (x = hp->x0 + 3; x <= hp->x1 - 3; x++) {
            DWORD v = hwy_at(hp, x, z);
            int role, ax, az, seen = 0;
            if (!v) continue;
            for (role = 0; role < 4 && hwy_id(v) != g_hwave_p[role]; role++) ;
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

/* a ROAD pass (an avenue drag or edit): this block alone, on the HWY base's buffer, without hwy_end (whose reverts
   are for highway passes, where every highway block has run) */
static void hwave_road(BYTE *mgr, int x0, int z0, int x1, int z1) {
    HwyPass *hp;
    if (!g_hwave_p[0]) return;
    hp = hwy_begin(mgr, x0, z0, x1, z1, "road");
    if (!hp) return;
    hwave_run(hp);
    if (hp->nput || hp->nrev)
        logf("hwave: road pass over (%d,%d)-(%d,%d): %d written, %d reverted", hp->x0, hp->z0, hp->x1, hp->z1, hp->nput,
             hp->nrev);
    VirtualFree(hp->b.c, 0, MEM_RELEASE);
    hp->b.c = NULL;
}

static void hwave_stats(void) {
    static LONG last;
    LONG n = g_hwave_n_built + g_hwave_n_rev + g_hwave_n_ref;
    if (!g_hwave_p[0] || n == last) return;
    last = n;
    logf("stats: hwave transitions built=%ld, reverted=%ld, refused=%ld", g_hwave_n_built, g_hwave_n_rev, g_hwave_n_ref);
}
