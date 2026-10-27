/* sc3netmod_bvs.c - boulevards on slopes, for the BV block (task avslope, 2026-10-26).
 * #included by sc3netmod.c right before sc3netmod_bv.c; BV calls bvs_line (its `bvs` table lines), bvs_is_piece
 * (bv_is_piece) and bvs_map (on every cell it writes). Notes and evidence: verify/avslope/RESULTS.md.
 *
 * Stock: a ROAD cell on a legal slope gets the ROAD slope table piece by its corner pattern alone (FUN_1001a2c0, table
 * SIMNTWRK 0x1003195C: rows 0..3 = 11202 / 11201 / 11202 / 11201 at states 0 / 0 / 2 / 2, rows 4..7 = 32 / 31 the same;
 * verify/slopeend/RESULTS.md 1). BV counts every ROAD cell as a boulevard column, so before this block it wrote the
 * FLAT 20700 / 20701 onto sloped cells (in game: a terrain hole and a step; the save held 11204 / 29 there).
 *
 * A package declares (netpack manifest "boulevard_slope_lines"):
 *   bvs o <piece> <slope piece> <side>   the sloped OUTER carriageway: a ROAD variant of the slope piece whose lanes run
 *                                        toward world side <side> at state 0 (at state s toward (side + s) % 4)
 *   bvs m <piece> <slope piece>          the sloped MIDDLE (two-way, the wide tree median)
 * bvs_map, on a cell BV writes: the cell's slope is read from the TERRAIN (FUN_1001a1f3, the corner pattern the slope
 * pass uses, so a flat boulevard piece an older build left on a slope is put right too). Not a legal slope -> BV's
 * piece. A slope: OUTER -> the sloped outer whose lanes run where BV's outer runs (11204 convention: state s runs
 * toward (s + 3) % 4), at the slope's state; MIDDLE / NOSE / NOSE2 -> the sloped middle at the slope's state; any other
 * piece (cap, taper, junction) -> the stock slope piece (as stock draws it). The sloped pieces save as the slope piece.
 * Off: SC3NETMOD_BVS=0 (BV then writes flat pieces on slopes, as before).
 */

typedef char (__fastcall *PFN_Corners)(void *mgr, void *edx, int *pos, signed char *out);   /* FUN_1001a1f3 */

static WORD g_bvs_o[4][4], g_bvs_m[4];               /* [slope index][side], [slope index] */
static const WORD BVS_BASE[4] = { 11202, 11201, 32, 31 };
static BYTE g_bvs_ours[65536];
static int g_bvs_n, g_bvs_on;
static volatile LONG g_bvs_n_slope, g_bvs_n_stock;

static int bvs_k(WORD b) {
    int k;
    for (k = 0; k < 4; k++) if (BVS_BASE[k] == b) return k;
    return -1;
}

static void bvs_line(const char *path, const char *line) {
    char role;
    unsigned long v, b, s = 0;
    int n = sscanf(line + 4, "%c %lu %lu %lu", &role, &v, &b, &s), k = bvs_k((WORD)b);
    if (!((role == 'o' && n == 4 && s < 4) || (role == 'm' && n >= 3)) || k < 0 || !v || v > 0xffff ||
        g_base[v] != (WORD)b) {
        logf("### bvs: %s: bad line (or not a variant of slope piece 11202 / 11201 / 32 / 31): '%s'", path, line);
        return;
    }
    if (role == 'o') g_bvs_o[k][s] = (WORD)v; else g_bvs_m[k] = (WORD)v;
    g_bvs_ours[v] = 1;
    g_bvs_n++;
    logf("bvs: %s: sloped boulevard %s %lu on slope piece %lu%s", path, role == 'o' ? "outer" : "middle", v, b,
         role == 'o' ? (s == 0 ? ", lanes toward N at state 0" : s == 1 ? ", lanes toward E at state 0" :
                        s == 2 ? ", lanes toward S at state 0" : ", lanes toward W at state 0") : "");
}

static int bvs_is_piece(WORD id) { return g_bvs_on && g_bvs_ours[id]; }

/* the legal slope at (x, z) from the terrain: -> slope index 0..3 and *st, or -1 (flat or not a legal slope) */
static int bvs_slope_at(BYTE *mgr, int x, int z, int *st) {
    static const signed char ROWS[8][4] = { { 0, -1, -1, 0 }, { 0, 0, -1, -1 }, { 0, 1, 1, 0 }, { 0, 0, 1, 1 },
                                            { 0, -2, -2, 0 }, { 0, 0, -2, -2 }, { 0, 2, 2, 0 }, { 0, 0, 2, 2 } };
    static const BYTE PIECE_K[8] = { 0, 1, 0, 1, 2, 3, 2, 3 }, STATE[8] = { 0, 0, 2, 2, 0, 0, 2, 2 };
    signed char c[4];
    int pos[3], r;
    pos[0] = x << 8; pos[1] = z << 8; pos[2] = 0;
    if (!((PFN_Corners)(g_rb_m + 0x1a1f3))(mgr, 0, pos, c)) return -1;
    for (r = 0; r < 8; r++)
        if (c[1] == ROWS[r][1] && c[2] == ROWS[r][2] && c[3] == ROWS[r][3]) { *st = STATE[r]; return PIECE_K[r]; }
    return -1;
}

/* BV is about to write `want` (piece << 8 | state) at (x, z): -> what to write instead on a slope */
static DWORD bvs_map(BYTE *mgr, int x, int z, DWORD want, const WORD *bvp) {
    WORD wp = (WORD)(want >> 8), piece;
    int ws = (int)(want & 3), st, k, side;
    if (!g_bvs_on || (k = bvs_slope_at(mgr, x, z, &st)) < 0) return want;
    if (wp == bvp[0]) {                                           /* OUTER: one-way toward (ws + 3) % 4 */
        side = ((ws + 3) - st + 8) & 3;
        piece = g_bvs_o[k][side];
    } else if (wp == bvp[1] || wp == bvp[2] || wp == bvp[3]) {    /* MIDDLE, NOSE, NOSE2 */
        piece = g_bvs_m[k];
    } else piece = 0;
    if (!piece) {
        InterlockedIncrement(&g_bvs_n_stock);
        return ((DWORD)BVS_BASE[k] << 8) | (DWORD)st;
    }
    InterlockedIncrement(&g_bvs_n_slope);
    return ((DWORD)piece << 8) | (DWORD)st;
}

static void bvs_install(void) {
    int k, s;
    if (g_bvs_n && env_off("SC3NETMOD_BVS")) { logf("bvs: off (SC3NETMOD_BVS=0)"); return; }
    if (!g_bvs_n) return;
    for (k = 0; k < 4; k++) {
        for (s = 0; s < 4; s++)
            if (!g_bvs_o[k][s] && (s & 1) == (k == 0 || k == 2))     /* 11202 / 32 run along x (E / W), 11201 / 31 z */
                logf("### bvs: slope piece %u has no sloped outer toward side %d: those cells get the stock slope piece",
                     BVS_BASE[k], s);
        if (!g_bvs_m[k]) logf("### bvs: slope piece %u has no sloped middle", BVS_BASE[k]);
    }
    g_bvs_on = 1;
    logf("bvs: boulevards on slopes on, %d sloped piece(s)", g_bvs_n);
}

static void bvs_stats(void) {
    static LONG last;
    LONG n = g_bvs_n_slope + g_bvs_n_stock;
    if (!g_bvs_on || n == last) return;
    last = n;
    logf("stats: bvs boulevard cells on a slope: %ld sloped piece(s), %ld left the stock slope piece", g_bvs_n_slope,
         g_bvs_n_stock);
}
