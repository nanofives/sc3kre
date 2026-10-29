/* sc3netmod_hwsc.c - the HWSC block of sc3netmod.dll (task hwyscurve, owner request 2026-10-29: "i need this S curve
 * for highways"): two parallel straight highways one cell apart that overlap by 2..4 columns become an S-curve.
 * Built on hwcore's HWY base (sc3netmod_hwy.c); #included by sc3netmod.c after the HWAVE block; runs as `hwsc_run(hp);`
 * in rb_hwy (sc3netmod_rbt.c), on every highway retile and on the city-load pass.
 *
 * Stock (measured in game 2026-10-29, verify/hwyscurve/RESULTS.md): band 1 on rows z 89 / 90 up to x 104, band 2 on
 * rows z 90 / 91 from x 103 -> the overlap cells (104,89), (103,90), (104,90), (103,91) are 15149.0. The shared row
 * would carry band 1's -x carriageway and band 2's +x one in the same cells; no HWAY Simple / Complex rule matches
 * those neighbour masks (0xdf, 0x7f, 0x36, 0xc9), so HWAY_GRND_final.txt #6 / #9 / #15 write 15149 (offline
 * `netrules explain`, agrees with the save). Overlap 1 is a stock one-column diagonal (11223 / 11224): left alone.
 *
 * Canonical frame (art, lanes and the table from re/tools/netmod/hwsc_build.py): axis a, cross c, cell (a, c).
 * Hand 0 (S): band 1 rows c 0 / 1 for a <= L - 1, band 2 rows c 1 / 2 for a >= 0; hand 1 (Z): band 1 rows 1 / 2,
 * band 2 rows 0 / 1. Footprint = a 0..L-1 x c 0..2, one piece per cell. Turned k states about the anchor vertex
 * (X0, Z0): world cell = (X0, Z0) + T^k(a, c), T(a, c) = (-c - 1, a) (hwpaint.turn_cell), piece state k. The S is
 * point-symmetric, so k 0 / 1 cover every layout (k 2 / 3 are the same S read from the other end); the lit twin goes
 * in at k 1 (hwy_put, hwyl lines).
 *
 * Rule (every pass, the load pass included: the S only rewrites cells the player built, so an old city's staircase is
 * healed on load). Seeds: a cell holding 15149 or an HWSC piece, not claimed. For every (k, hand, L) and footprint
 * cell the seed could be, the anchor must give:
 *   footprint  every cell highway (15149, the axis straight 15051 / 73, or an HWSC piece), unclaimed, flat ground
 *              (FUN_10016ccd, the test hwy_free uses);
 *   lead-ins   a = -1 on band 1's rows and a = L on band 2's: the plain stock straight of the axis (15051 for k 0,
 *              73 for k 1) at the stock states (the lower row drives +a), unclaimed;
 *   empty      no highway at a = -1 / a = L on the third row, nor on rows c -1 and c 3 for a -1..L (else it is
 *              another shape: two bands touching side by side, a T, three bands).
 * Then every footprint cell gets its piece at state k (hwy_put: written, or kept when already there). A built S whose
 * layout no longer holds is not kept, and hwy_end re-tiles its cells in place (stock: 15149 again). Pieces save as
 * 15149.0 (hwys lines), so a game without the mod loads the city as stock shows it; the variant section restores them.
 * Slopes, ramps or interchanges on the footprint or the lead-ins, overlaps of 5 or more: stock (15149) stays.
 *
 * Table lines (netpack manifest "highway_lines", written by hwsc_build.py manifest):
 *   hwsc <hand 0|1> <L 2..4> <a> <c> <piece>
 * Off: SC3NETMOD_HWSC=0.
 */

#define HWSC_MINL 2
#define HWSC_MAXL 4

static WORD g_hwsc_tab[2][HWSC_MAXL + 1][HWSC_MAXL][3];      /* hand, L, a, c -> piece (0 = none) */
static WORD g_hwsc_lo = 0xffff, g_hwsc_hi;
static int g_hwsc_n;
static volatile LONG g_hwsc_n_new, g_hwsc_n_kept, g_hwsc_n_refused;

static void hwsc_line(const char *path, const char *line) {
    long h, L, a, c, p;
    if (sscanf(line + 5, "%ld %ld %ld %ld %ld", &h, &L, &a, &c, &p) != 5 || h < 0 || h > 1 || L < HWSC_MINL ||
        L > HWSC_MAXL || a < 0 || a >= L || c < 0 || c > 2 || p <= 0 || p > 0xffff) {
        logf("### hwsc: %s: bad line '%s'", path, line);
        return;
    }
    if (!g_hwsc_tab[h][L][a][c]) g_hwsc_n++;
    g_hwsc_tab[h][L][a][c] = (WORD)p;
    if (p < g_hwsc_lo) g_hwsc_lo = (WORD)p;
    if (p > g_hwsc_hi) g_hwsc_hi = (WORD)p;
}

static int hwsc_mine(WORD id) {
    int h, L, a, c;
    if (id < g_hwsc_lo || id > g_hwsc_hi) return 0;
    for (h = 0; h < 2; h++)
        for (L = HWSC_MINL; L <= HWSC_MAXL; L++)
            for (a = 0; a < L; a++)
                for (c = 0; c < 3; c++)
                    if (g_hwsc_tab[h][L][a][c] == id) return 1;
    return 0;
}

static void hwsc_at(int X0, int Z0, int k, int a, int c, int *x, int *z) {
    int i, t;
    for (i = 0; i < k; i++) { t = a; a = -c - 1; c = t; }
    *x = X0 + a; *z = Z0 + c;
}

/* band rows of a hand: r1 = band 1's lower row (c), r2 = band 2's lower row */
static void hwsc_rows(int hand, int *r1, int *r2) { *r1 = hand ? 1 : 0; *r2 = hand ? 0 : 1; }

/* 1 = the layout (k, hand, L) at anchor (X0, Z0) holds; *why = what failed (shape tests fail silently: why = NULL) */
static int hwsc_match(HwyPass *hp, int X0, int Z0, int k, int hand, int L, const char **why) {
    int a, c, x, z, r1, r2, j;
    WORD axis = k ? 73 : 15051;
    *why = NULL;
    hwsc_rows(hand, &r1, &r2);
    for (a = 0; a < L; a++)
        for (c = 0; c < 3; c++) {
            DWORD v;
            WORD id;
            if (!g_hwsc_tab[hand][L][a][c]) return 0;
            hwsc_at(X0, Z0, k, a, c, &x, &z);
            v = hwy_rd(hp, x, z);
            if (!v) return 0;
            id = hwy_id(v);
            if (id != 15149 && id != axis && !hwsc_mine(id)) return 0;
        }
    for (j = 0; j < 4; j++) {                              /* lead-ins: the axis straight, lower row drives +a */
        int row = j < 2 ? r1 + j : r2 + (j - 2), st = (j & 1) ? (k ? 2 : 0) : (k ? 0 : 2);
        DWORD v;
        hwsc_at(X0, Z0, k, j < 2 ? -1 : L, row, &x, &z);
        v = hwy_rd(hp, x, z);
        if (!v || hwy_id(v) != axis || hwy_st(v) != st) return 0;
    }
    for (a = -1; a <= L; a++)                              /* nothing else beside it */
        for (c = -1; c <= 3; c++) {
            int empty = c == -1 || c == 3 || (a == -1 && (c < r1 || c > r1 + 1)) || (a == L && (c < r2 || c > r2 + 1));
            if (!empty) continue;
            hwsc_at(X0, Z0, k, a, c, &x, &z);
            if (hwy_rd(hp, x, z)) return 0;
        }
    for (a = -1; a <= L; a++)                              /* the shape holds: now the conditions that refuse it */
        for (c = 0; c < 3; c++) {
            int foot = a >= 0 && a < L, lead = (a == -1 && (c == r1 || c == r1 + 1)) || (a == L && (c == r2 || c == r2 + 1));
            if (!foot && !lead) continue;
            hwsc_at(X0, Z0, k, a, c, &x, &z);
            if (hwy_claimed(x, z)) { *why = "a cell is another block's"; return 0; }
            if (foot) {
                int pos[3];
                pos[0] = x << 8; pos[1] = z << 8; pos[2] = 0;
                if (!((PFN_HwyPos)(g_rb_m + 0x16ccd))(hp->mgr, 0, pos)) { *why = "sloped ground"; return 0; }
            }
        }
    return 1;
}

static int hwsc_put(HwyPass *hp, int X0, int Z0, int k, int hand, int L, int *written) {
    int a, c, x, z, n = 0, r;
    *written = 0;
    for (a = 0; a < L; a++)
        for (c = 0; c < 3; c++) {
            hwsc_at(X0, Z0, k, a, c, &x, &z);
            r = hwy_put(hp, x, z, g_hwsc_tab[hand][L][a][c], k);
            if (r >= 0) n++;
            if (r > 0) (*written)++;
        }
    return n;
}

static void hwsc_run(HwyPass *hp) {
    static int done[64][3];                        /* anchors handled in this pass: X0, Z0, k */
    int ndone = 0, x, z, k, hand, L, a, c, j;
    if (!g_hwsc_n || env_off("SC3NETMOD_HWSC")) return;
    for (z = hp->z0 + 1; z < hp->z1; z++)
        for (x = hp->x0 + 1; x < hp->x1; x++) {
            DWORD v = hwy_at(hp, x, z);
            WORD id;
            if (!v || hwy_claimed(x, z)) continue;
            id = hwy_id(v);
            if (id != 15149 && !hwsc_mine(id)) continue;
            for (k = 0; k < 2; k++)
                for (hand = 0; hand < 2; hand++)
                    for (L = HWSC_MINL; L <= HWSC_MAXL; L++)
                        for (a = 0; a < L; a++)
                            for (c = 0; c < 3; c++) {
                                int tx, tz, X0, Z0, n, w;
                                const char *why;
                                hwsc_at(0, 0, k, a, c, &tx, &tz);
                                X0 = x - tx; Z0 = z - tz;
                                for (j = 0; j < ndone; j++)
                                    if (done[j][0] == X0 && done[j][1] == Z0 && done[j][2] == k) break;
                                if (j < ndone) continue;
                                if (!hwsc_match(hp, X0, Z0, k, hand, L, &why)) {
                                    if (why) {
                                        InterlockedIncrement(&g_hwsc_n_refused);
                                        logf("hwsc: %s: S-curve %c%d at (%d,%d) turn %d refused: %s", hp->who,
                                             hand ? 'Z' : 'S', L, X0, Z0, k, why);
                                        if (ndone < 64) { done[ndone][0] = X0; done[ndone][1] = Z0; done[ndone][2] = k; ndone++; }
                                    }
                                    continue;
                                }
                                if (ndone < 64) { done[ndone][0] = X0; done[ndone][1] = Z0; done[ndone][2] = k; ndone++; }
                                n = hwsc_put(hp, X0, Z0, k, hand, L, &w);
                                if (w) {
                                    InterlockedIncrement(&g_hwsc_n_new);
                                    logf("hwsc: %s: S-curve %c%d at (%d,%d) turn %d: %d cells written, %d kept", hp->who,
                                         hand ? 'Z' : 'S', L, X0, Z0, k, w, n - w);
                                } else InterlockedIncrement(&g_hwsc_n_kept);
                            }
        }
}

static void hwsc_stats(void) {
    static LONG last;
    LONG n = g_hwsc_n_new + g_hwsc_n_kept + g_hwsc_n_refused;
    if (!g_hwsc_n || n == last) return;
    last = n;
    logf("stats: hwsc S-curves built=%ld, kept=%ld, refused=%ld", g_hwsc_n_new, g_hwsc_n_kept, g_hwsc_n_refused);
}
