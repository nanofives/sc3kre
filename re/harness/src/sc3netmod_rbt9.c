/* sc3netmod_rbt9.c - the RBT9 block of sc3netmod.dll (task bigrbt, 2026-10-17): automatic 3x3 roundabouts.
 * #included by sc3netmod.c after sc3netmod_dav.c; runs on RBT's two hooks (rb_pass after every road retile,
 * rb_load_pass once after a city load) when `rbt9` table lines were read. Offline twin, pieces, art and lanes:
 * re/tools/netmod/bigrbt.py; evidence verify/bigrbt/.
 *
 * A package declares its pieces, one `rbt9 <role> <k> <piece>` line each (netpack manifest "auto_big_roundabouts"):
 * role c = the centre cell; s k = the side-middle cell at state 0 (the E cell, outer side x+) by its arm k (0 none,
 * 1 road, 2 avenue half with the median toward z-, 3 toward z+); k k = the corner cell at state 0 (the NE cell, outer
 * sides z- and x+), k = 3 * kN + kE by the arm on z- / on x+ (0 none, 1 road, 2 avenue half). A block = the 3x3 of
 * cells with origin (X, Z) = its x-, z- cell. It becomes those pieces when ALL hold:
 *  (a) the 9 cells hold ROAD, each a flat stock road piece (29, 39, 43, 11203, 11204) or one of the RBT9 pieces;
 *  (b) the four diagonal cells (X-1,Z-1) (X+3,Z-1) (X-1,Z+3) (X+3,Z+3) hold no ROAD;
 *  (c) on each side the three arm cells (one step out of the side's three cells) are not all ROAD (three parallel
 *      roads or a bigger block: not a 3x3 roundabout);
 *  (d) two neighbouring arm cells on a side are an avenue: the two cells beyond them hold ROAD too, and both arm cells
 *      are flat stock road pieces (they are written as avenue half 11204, median toward each other, so the median
 *      runs up to the block).
 * Cells of each side: index 0..2 along +z (W, E) or +x (N, S). Cell states by position: side E 0, S 1, W 2, N 3;
 * corner NE 0, SE 1, SW 2, NW 3 (a piece's local side c is world side (c + state) mod 4, NET_LANES.md 1.1).
 * Refused by construction: 2x2 blocks (RBT), avenue x avenue boxes (avx), three-row runs (boulevard: rule c),
 * diagonal avenues (no full 3x3 in a band).
 * Write = the piece writer FUN_10008919 per cell (as RBT, DAV), free. Revert: an RBT9 piece that is not in a
 * qualifying block gets the rect retile FUN_100151f1 (manager vt+0xb0, mask 3) over it and its 8 neighbours (the
 * pieces are not Protected, so the stock tiler re-places the block and the avenue arm cells as road).
 * Save: the bases are the stock pieces a game without the mod should load (centre and cells with arms 43, arm-less
 * side 39, arm-less corner 11203 in the same state: their stock connections), so SAVEBASE needs no override here.
 * Off: SC3NETMOD_RBT9=0.
 */

static WORD g_r9_side[4], g_r9_corner[9];       /* g_r9_centre: declared in sc3netmod_rbt.c */
static volatile LONG g_r9_n_blocks, g_r9_n_cells, g_r9_n_rev;

/* cells by index cx + 3 * cz: 0 centre / 1 side / 2 corner, and the state */
static const BYTE R9_TYPE[9] = { 2, 1, 2, 1, 0, 1, 2, 1, 2 };
static const BYTE R9_STATE[9] = { 3, 3, 0, 2, 0, 0, 2, 1, 1 };
static const signed char R9_OUT[4][2] = { { -1, 0 }, { 0, -1 }, { 1, 0 }, { 0, 1 } };   /* world side -> step out */
static const signed char R9_SIDE[4][3][2] = {                                           /* side cells, index 0..2 */
    { { 0, 0 }, { 0, 1 }, { 0, 2 } }, { { 0, 0 }, { 1, 0 }, { 2, 0 } },
    { { 2, 0 }, { 2, 1 }, { 2, 2 } }, { { 0, 2 }, { 1, 2 }, { 2, 2 } } };
static const BYTE R9_ALONG[4] = { 3, 2, 3, 2 };                                         /* index grows toward */

static void r9_line(const char *path, const char *line) {
    char role;
    unsigned long k, p;
    if (sscanf(line + 5, " %c %lu %lu", &role, &k, &p) != 3 || !p || p > 0xffff || !g_base[p] ||
        (role == 'c' && k != 0) || (role == 's' && k > 3) || (role == 'k' && k > 8) ||
        (role != 'c' && role != 's' && role != 'k')) {
        logf("### rbt9: %s: bad line or piece not a variant: '%s'", path, line);
        return;
    }
    if (role == 'c') g_r9_centre = (WORD)p;
    else if (role == 's') g_r9_side[k] = (WORD)p;
    else g_r9_corner[k] = (WORD)p;
}

/* all roles declared? (a missing one turns the block off) */
static int r9_complete(void) {
    int k;
    if (!g_r9_centre) return 0;
    for (k = 0; k < 4; k++) if (!g_r9_side[k]) return 0;
    for (k = 0; k < 9; k++) if (!g_r9_corner[k]) return 0;
    return 1;
}

static int r9_is_ours(WORD id) {
    int k;
    if (!id) return 0;
    if (id == g_r9_centre) return 1;
    for (k = 0; k < 4; k++) if (g_r9_side[k] == id) return 1;
    for (k = 0; k < 9; k++) if (g_r9_corner[k] == id) return 1;
    return 0;
}

static int r9_flat(DWORD v) {
    WORD id = (WORD)(v & 0xffff);
    return v && (id == 29 || id == 39 || id == 43 || id == 11203 || id == 11204);
}

/* the rule for origin (X, Z). -> 1 and want[0..8] (piece << 8 | state per cell, index cx + 3 cz), arm[0..7]
   (x, z, 11204 << 8 | state; *narm of them) when it qualifies; else 0 and *why */
static int r9_check(RbBuf *b, int X, int Z, DWORD *want, int *arm, int *narm, const char **why) {
    BYTE kind[9][4];                              /* per block cell and world side: 0 none, 1 road, 2 + partner */
    int cx, cz, s, i, k;
    *narm = 0;
    for (k = 0; k < 9; k++) {
        DWORD v = rb_at(b, X + k % 3, Z + k / 3);
        if (!r9_flat(v) && !(v && r9_is_ours((WORD)(v & 0xffff)))) { *why = "a"; return 0; }
    }
    if (rb_at(b, X - 1, Z - 1) || rb_at(b, X + 3, Z - 1) || rb_at(b, X - 1, Z + 3) || rb_at(b, X + 3, Z + 3)) {
        *why = "b (a diagonal cell holds road)"; return 0;
    }
    memset(kind, 0, sizeof(kind));
    for (s = 0; s < 4; s++) {
        int on[3], dx = R9_OUT[s][0], dz = R9_OUT[s][1];
        for (i = 0; i < 3; i++) on[i] = rb_at(b, X + R9_SIDE[s][i][0] + dx, Z + R9_SIDE[s][i][1] + dz) != 0;
        if (on[0] && on[1] && on[2]) { *why = "c (three arm cells on a side)"; return 0; }
        for (i = 0; i < 3; i++) {
            int j = -1, c = R9_SIDE[s][i][0] + 3 * R9_SIDE[s][i][1];
            if (!on[i]) continue;
            if (i < 2 && on[i + 1]) j = i + 1;
            if (i > 0 && on[i - 1]) j = i - 1;
            if (j < 0) { kind[c][s] = 1; continue; }
            {
                int ax = X + R9_SIDE[s][i][0] + dx, az = Z + R9_SIDE[s][i][1] + dz, partner;
                if (!rb_at(b, ax + dx, az + dz)) { *why = "d (a 2-wide arm that does not go on as an avenue)"; return 0; }
                if (!r9_flat(rb_at(b, ax, az))) { *why = "d (avenue arm cell is not a flat road piece)"; return 0; }
                partner = j > i ? R9_ALONG[s] : (R9_ALONG[s] + 2) & 3;
                kind[c][s] = (BYTE)(2 + partner);
                if (*narm < 8) {
                    arm[*narm * 3] = ax; arm[*narm * 3 + 1] = az;
                    arm[*narm * 3 + 2] = (int)((11204UL << 8) | ((partner + 3) & 3));
                    (*narm)++;
                }
            }
        }
    }
    for (cz = 0; cz < 3; cz++)
        for (cx = 0; cx < 3; cx++) {
            int c = cx + 3 * cz, st = R9_STATE[c];
            WORD p;
            if (R9_TYPE[c] == 0) p = g_r9_centre;
            else if (R9_TYPE[c] == 1) {
                int o = (2 + st) & 3, kd = kind[c][o], code = kd < 2 ? kd : (((kd - 2 - st) & 3) == 1 ? 2 : 3);
                p = g_r9_side[code];
            } else {
                int n = kind[c][(1 + st) & 3], e = kind[c][(2 + st) & 3];
                p = g_r9_corner[3 * (n < 2 ? n : 2) + (e < 2 ? e : 2)];
            }
            want[c] = ((DWORD)p << 8) | (DWORD)st;
        }
    return 1;
}

/* cells [x0..x1] x [z0..z1] were edited (the retile pass's work box) or the whole map (load) */
static void r9_run(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who) {
    void *lay = *(void **)(mgr + 0x3c);
    int W = (*(int *)(mgr + 0x5c) >> 8) + 1, H = (*(int *)(mgr + 0x60) >> 8) + 1;
    int rx0, rz0, rx1, rz1, ox0, oz0, ox1, oz1, x, z, k, nb = 0, nw = 0, nrev = 0;
    RbBuf b;
    BYTE *keep;
    if (!g_r9_centre || W < 5 || H < 5 || W > 4096 || H > 4096) return;
    /* r = the cells of every block whose cells, ring or avenue beyond touch the box (origins x0-4 .. x1+2): the
       revert looks there; o = the origins of every block that has a cell in r, all evaluated so none of them is
       reverted by mistake; the buffer holds what those origins read (X-2 .. X+4) */
    rx0 = max(x0 - 4, 0); rz0 = max(z0 - 4, 0); rx1 = min(x1 + 4, W - 1); rz1 = min(z1 + 4, H - 1);
    ox0 = max(rx0 - 2, 0); oz0 = max(rz0 - 2, 0); ox1 = min(rx1, W - 3); oz1 = min(rz1, H - 3);
    if (ox0 > ox1 || oz0 > oz1) return;
    b.x0 = ox0 - 2; b.z0 = oz0 - 2; b.w = ox1 - ox0 + 7; b.h = oz1 - oz0 + 7;
    b.c = (DWORD *)VirtualAlloc(NULL, (SIZE_T)b.w * b.h * 5, MEM_COMMIT, PAGE_READWRITE);
    if (!b.c) return;
    keep = (BYTE *)(b.c + b.w * b.h);
    for (z = 0; z < b.h; z++)
        for (x = 0; x < b.w; x++) b.c[z * b.w + x] = rb_read(mgr, lay, b.x0 + x, b.z0 + z, W, H);
    for (z = oz0; z <= oz1; z++)
        for (x = ox0; x <= ox1; x++) {
            DWORD want[9];
            int arm[24], narm, n = 0;
            const char *why = "";
            if (!r9_check(&b, x, z, want, arm, &narm, &why)) continue;
            nb++;
            for (k = 0; k < 9 + narm; k++) {
                int cx = k < 9 ? x + k % 3 : arm[(k - 9) * 3], cz = k < 9 ? z + k / 3 : arm[(k - 9) * 3 + 1], pos[3];
                DWORD w = k < 9 ? want[k] : (DWORD)arm[(k - 9) * 3 + 2], cur = rb_at(&b, cx, cz);
                keep[(cz - b.z0) * b.w + (cx - b.x0)] = 1;
                if ((((cur & 0xffff) << 8) | ((cur >> 16) & 3)) == w) continue;
                pos[0] = cx << 8; pos[1] = cz << 8; pos[2] = 0;
                ((PFN_Put)(g_rb_m + 0x8919))(mgr, 0, lay, pos, w, -1, 8, 0);
                n++;
            }
            nw += n;
            if (n || !strcmp(who, "load"))
                logf("rbt9: %s: (%d,%d) -> 3x3 roundabout, %d avenue arm cell(s), %d cell(s) written: %u.%u %u.%u %u.%u / "
                     "%u.%u %u.%u %u.%u / %u.%u %u.%u %u.%u", who, x, z, narm, n, want[0] >> 8, want[0] & 3, want[1] >> 8,
                     want[1] & 3, want[2] >> 8, want[2] & 3, want[3] >> 8, want[3] & 3, want[4] >> 8, want[4] & 3,
                     want[5] >> 8, want[5] & 3, want[6] >> 8, want[6] & 3, want[7] >> 8, want[7] & 3, want[8] >> 8,
                     want[8] & 3);
        }
    /* RBT9 pieces in r that no qualifying block kept: back to the stock tiles */
    for (z = rz0; z <= rz1; z++)
        for (x = rx0; x <= rx1; x++) {
            DWORD v = rb_at(&b, x, z);
            int rect[6], dx, dz;
            if (!v || !r9_is_ours((WORD)(v & 0xffff)) || keep[(z - b.z0) * b.w + (x - b.x0)]) continue;
            rect[0] = (x - 1) << 8; rect[1] = (z - 1) << 8; rect[2] = 0; rect[3] = (x + 1) << 8; rect[4] = (z + 1) << 8;
            rect[5] = 0;
            if (x < 1) rect[0] = 0;
            if (z < 1) rect[1] = 0;
            ((PFN_Retile)VT(mgr, 0xb0))(mgr, 0, rect, 3);
            nrev++;
            logf("rbt9: %s: (%d,%d) piece %lu no longer in a 3x3 roundabout -> stock retile", who, x, z, v & 0xffff);
            for (dz = -1; dz <= 1; dz++)                      /* its neighbours were re-placed by the same retile */
                for (dx = -1; dx <= 1; dx++) {
                    int qx = x + dx - b.x0, qz = z + dz - b.z0;
                    if (qx >= 0 && qz >= 0 && qx < b.w && qz < b.h) keep[qz * b.w + qx] = 1;
                }
        }
    VirtualFree(b.c, 0, MEM_RELEASE);
    InterlockedExchangeAdd(&g_r9_n_blocks, nb);
    InterlockedExchangeAdd(&g_r9_n_cells, nw);
    InterlockedExchangeAdd(&g_r9_n_rev, nrev);
    if (nw || nrev || !strcmp(who, "load"))
        logf("rbt9: %s pass over origins (%d,%d)-(%d,%d) [tid %04lx]: %d qualify, %d cell(s) written, %d reverted", who,
             ox0, oz0, ox1, oz1, GetCurrentThreadId(), nb, nw, nrev);
}

static void r9_stats(void) {
    static LONG last;
    LONG n = g_r9_n_blocks + g_r9_n_cells + g_r9_n_rev;
    if (!g_r9_centre || n == last) return;
    last = n;
    logf("stats: rbt9 blocks seen=%ld, cells written=%ld, reverted=%ld", g_r9_n_blocks, g_r9_n_cells, g_r9_n_rev);
}
