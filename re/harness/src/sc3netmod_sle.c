/* sc3netmod_sle.c - the SLE block of sc3netmod.dll (task slopeend, 2026-10-26): rounded road ends on slopes.
 * #included by sc3netmod.c after the RBT block; runs on RBT's two hooks (rb_pass net 1, rb_load_pass).
 * Notes and evidence: verify/slopeend/RESULTS.md, re/tools/netmod/slopeend.py (offline twin), slopeend_paint.py (art).
 *
 * Stock: a ROAD cell on a legal slope never sees the tiling rules. The retile pass FUN_1001547b moves it to the slope
 * list and FUN_1001a2c0 gives it the ROAD slope table entry (SIMNTWRK 0x1003195C) by corner pattern alone: 11202 state
 * 0 / 2 (slope along x, downhill +x / -x), 11201 0 / 2 (along z, downhill +z / -z), steep 32 / 31 the same. So a road
 * that ends on a slope ends with the straight piece's square cut.
 *
 * A package declares `sle <base> <up> <down> <both> <up> <down> <both>` (netpack manifest "road_end_lines"): ROAD
 * variants of the slope piece <base> with the uphill end, the downhill end or both ends rounded like the flat dead end
 * 11225, the first three written at state 0, the last three at state 2. One set per state because the variants use
 * 11225's sprite class (the slope pieces' class draws no terrain under a ground-bit piece), which anchors the art at
 * the occupant's altitude, and that is a different corner of the plane at the two states (slopeend_paint.py
 * variant_art). After every ROAD retile (over the work box + 1) and once after a city load (whole map), each
 * road cell holding <base> or one of its variants becomes:
 *   a road in a side neighbour (across the slope)  -> <base> (refused: the stock T beside it stays as stock draws it)
 *   road in both axis neighbours                   -> <base>
 *   road in the downhill neighbour only            -> <up>    (the road climbs onto the cell and stops)
 *   road in the uphill neighbour only              -> <down>
 *   no road in either axis neighbour               -> <both>
 * "Road" = rb_read (the manager's ROAD predicate, as RBT). Downhill = from the base's axis and the cell's state (the
 * slope pass placed it from the terrain). Written with the piece writer FUN_10008919, same state, height -1 = from the
 * terrain (vt+0x4c, as the stock commit FUN_100165d8). Saves: the variants save as their base (netvariant), so a game
 * without the mod loads today's square cut. Off: SC3NETMOD_SLE=0.
 */

#define SLE_MAX 8
static WORD g_sle_base[SLE_MAX], g_sle_v[SLE_MAX][2][3];   /* [k][state / 2][0] up, [1] down, [2] both */
/* g_sle_n, g_sle_on: declared in sc3netmod_rbt.c */
static BYTE g_sle_of[65536];                              /* id -> 1 + index of its slope family, 0 none */
static volatile LONG g_sle_n_pass, g_sle_n_put, g_sle_n_refused;

static void sle_line(const char *path, const char *line) {
    unsigned long b, v[6];
    int k, j;
    if (sscanf(line + 4, "%lu %lu %lu %lu %lu %lu %lu", &b, &v[0], &v[1], &v[2], &v[3], &v[4], &v[5]) != 7 ||
        (b != 11202 && b != 11201 && b != 32 && b != 31)) {
        logf("### sle: %s: bad line: '%s'", path, line);
        return;
    }
    for (j = 0; j < 6; j++)
        if (!v[j] || v[j] > 0xffff || g_base[v[j]] != b) {
            logf("### sle: %s: %lu is not a variant of slope piece %lu - line ignored", path, v[j], b);
            return;
        }
    if (g_sle_of[b]) { logf("### sle: %s: slope piece %lu declared twice - ignored", path, b); return; }
    if (g_sle_n >= SLE_MAX) return;
    k = g_sle_n++;
    g_sle_base[k] = (WORD)b;
    g_sle_of[b] = (BYTE)(k + 1);
    for (j = 0; j < 6; j++) {
        g_sle_v[k][j / 3][j % 3] = (WORD)v[j];
        g_sle_of[v[j]] = (BYTE)(k + 1);
    }
    logf("sle: %s: slope piece %lu -> state 0: up %lu, down %lu, both %lu; state 2: up %lu, down %lu, both %lu", path,
         b, v[0], v[1], v[2], v[3], v[4], v[5]);
}

static void sle_run(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who) {
    void *lay = *(void **)(mgr + 0x3c);
    int W = (*(int *)(mgr + 0x5c) >> 8) + 1, H = (*(int *)(mgr + 0x60) >> 8) + 1;
    int x, z, nput = 0, nref = 0;
    RbBuf b;
    if (!g_sle_on || W < 2 || H < 2 || W > 4096 || H > 4096) return;
    if (x0 < 0) x0 = 0;
    if (z0 < 0) z0 = 0;
    if (x1 > W - 1) x1 = W - 1;
    if (z1 > H - 1) z1 = H - 1;
    if (x0 > x1 || z0 > z1) return;
    b.x0 = x0 - 1; b.z0 = z0 - 1; b.w = x1 - x0 + 3; b.h = z1 - z0 + 3;
    b.c = (DWORD *)VirtualAlloc(NULL, (SIZE_T)b.w * b.h * 4, MEM_COMMIT, PAGE_READWRITE);
    if (!b.c) return;
    for (z = 0; z < b.h; z++)
        for (x = 0; x < b.w; x++) b.c[z * b.w + x] = rb_read(mgr, lay, b.x0 + x, b.z0 + z, W, H);
    for (z = z0; z <= z1; z++)
        for (x = x0; x <= x1; x++) {
            DWORD v = rb_at(&b, x, z), id = v & 0xffff, st = (v >> 16) & 3;
            int k, dx, dz, up, dn, side;
            WORD want;
            if (!v || !(k = g_sle_of[id])) continue;
            k--;
            if (st & 1) continue;                         /* the slope table only ever writes states 0 / 2 */
            if (g_sle_base[k] == 11202 || g_sle_base[k] == 32) { dx = st ? -1 : 1; dz = 0; }
            else { dx = 0; dz = st ? -1 : 1; }
            up = rb_at(&b, x - dx, z - dz) != 0;
            dn = rb_at(&b, x + dx, z + dz) != 0;
            side = rb_at(&b, x + dz, z + dx) != 0 || rb_at(&b, x - dz, z - dx) != 0;
            if (side || (up && dn)) want = g_sle_base[k];
            else if (dn) want = g_sle_v[k][st >> 1][0];
            else if (up) want = g_sle_v[k][st >> 1][1];
            else want = g_sle_v[k][st >> 1][2];
            if (side && !(up && dn)) nref++;
            if (want == (WORD)id) continue;
            {
                int pos[3];
                pos[0] = x << 8; pos[1] = z << 8; pos[2] = 0;
                ((PFN_Put)(g_rb_m + 0x8919))(mgr, 0, lay, pos, ((DWORD)want << 8) | st, -1, 8, 0);
            }
            nput++;
            if (nput <= 40)
                logf("sle: %s: (%d,%d) %lu/%lu -> %u (road uphill %d, downhill %d, beside %d)", who, x, z, id, st, want,
                     up, dn, side);
        }
    VirtualFree(b.c, 0, MEM_RELEASE);
    InterlockedIncrement(&g_sle_n_pass);
    InterlockedExchangeAdd(&g_sle_n_put, nput);
    InterlockedExchangeAdd(&g_sle_n_refused, nref);
    if (nput || !strcmp(who, "load"))
        logf("sle: %s pass over (%d,%d)-(%d,%d): %d cell(s) written, %d end(s) left stock (road beside)", who, x0, z0,
             x1, z1, nput, nref);
}

static void sle_install(void) {
    if (g_sle_n && env_off("SC3NETMOD_SLE")) { g_sle_n = 0; logf("sle: off (SC3NETMOD_SLE=0)"); }
    if (!g_sle_n) logf("sle: no road slope ends in the tables");
}

static void sle_stats(void) {
    static LONG last;
    LONG n = g_sle_n_pass + g_sle_n_put;
    if (!g_sle_on || n == last) return;
    last = n;
    logf("stats: sle passes=%ld, cells written=%ld, ends left stock (road beside)=%ld", g_sle_n_pass, g_sle_n_put,
         g_sle_n_refused);
}
