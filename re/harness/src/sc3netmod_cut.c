/*
 * sc3netmod_cut.c - CUT guard for DAV's revert loop (task avdiagbreak, 2026-10-30; BV / DBV have the same pattern and
 * are task avslow's). Included by
 * sc3netmod.c after sc3netmod_rbt.c (RbBuf, rb_read, PFN_Put). SC3NETMOD_CUTGUARD=0 turns it off (old behaviour).
 *
 * Owner report 2026-10-30: "Diagonal sections of 3-lane road sometimes break when placing roads elsewhere."
 * An edit pass reads a window (the retile pass's work box + 24). A band the window's edge cuts is judged on the part
 * inside it; that part fails the band rules (too few rows, a junction outside), so the pass never set its border flag
 * (no whole-map pass) and the revert loop read its pieces as "no longer in a band". The revert is a stock retile of
 * one cell (manager vt+0xb0, mask 3), and the game's retile goes over the whole connected run, past the window: in the
 * lab, an unconnected road 22 cells away reverted 3 cells and 21 cells of the band went back to the stock ladder.
 *
 * The guard: (1) before reverting, every stale piece's 8-connected component of block pieces (not kept by this pass) is
 * walked; one that reaches the window's border ring means the window cut a band, so nothing is reverted and the caller's
 * whole-map pass decides. (2) When the whole-map pass is coming anyway, the windowed pass reverts nothing. (3) After
 * any revert, the cells this pass wrote and the run-wide retile changed get their pieces back.
 */
typedef struct {
    int on, x0, z0, x1, z1, W, H, w, h, full, nreput;
    DWORD *want;                        /* [cell]: piece << 8 | state this pass wrote (or found right), 0 none */
    BYTE *seen;                         /* [cell]: 0 not walked, 1 component inside the window, 2 reaches its border */
    int *q;                             /* the walk's queue */
} CutGuard;

static int g_cut_on = -1;
static volatile LONG g_cut_n_cut, g_cut_n_reput;

static void cut_begin(CutGuard *g, int x0, int z0, int x1, int z1, int W, int H) {
    if (g_cut_on < 0) {
        g_cut_on = !env_off("SC3NETMOD_CUTGUARD");
        logf("cut: revert guard %s (SC3NETMOD_CUTGUARD)", g_cut_on ? "on" : "off");
    }
    ZeroMemory(g, sizeof(*g));
    g->on = g_cut_on;
    g->x0 = x0; g->z0 = z0; g->x1 = x1; g->z1 = z1; g->W = W; g->H = H; g->w = x1 - x0 + 1; g->h = z1 - z0 + 1;
    g->full = x0 == 0 && z0 == 0 && x1 == W - 1 && z1 == H - 1;
    if (g->on) g->want = (DWORD *)VirtualAlloc(NULL, (SIZE_T)g->w * g->h * 4, MEM_COMMIT, PAGE_READWRITE);
}

static void cut_end(CutGuard *g) {
    if (g->want) VirtualFree(g->want, 0, MEM_RELEASE);
    if (g->seen) VirtualFree(g->seen, 0, MEM_RELEASE);
    if (g->q) VirtualFree(g->q, 0, MEM_RELEASE);
    g->want = NULL; g->seen = NULL; g->q = NULL;
}

/* a cell this pass put (or found already right) as part of a kept band */
static void cut_wrote(CutGuard *g, int x, int z, DWORD want) {
    if (!g->want || x < g->x0 || z < g->z0 || x > g->x1 || z > g->z1) return;
    g->want[(z - g->z0) * g->w + (x - g->x0)] = want;
}

static int cut_at_border(CutGuard *g, int x, int z) {
    return (x <= g->x0 + 1 && g->x0 > 0) || (z <= g->z0 + 1 && g->z0 > 0) || (x >= g->x1 - 1 && g->x1 < g->W - 1) ||
           (z >= g->z1 - 1 && g->z1 < g->H - 1);
}

/* does the component of block pieces (is(), not keep[]) through the stale cell (x, z) reach the window's border? */
static int cut_reaches(CutGuard *g, RbBuf *b, int x, int z, int (*is)(WORD), const BYTE *keep) {
    int n = 0, head = 0, hit = 0, k, i = (z - g->z0) * g->w + (x - g->x0);
    if (!g->on || g->full) return 0;
    if (!g->seen) {
        g->seen = (BYTE *)VirtualAlloc(NULL, (SIZE_T)g->w * g->h, MEM_COMMIT, PAGE_READWRITE);
        g->q = (int *)VirtualAlloc(NULL, (SIZE_T)g->w * g->h * 4, MEM_COMMIT, PAGE_READWRITE);
        if (!g->seen || !g->q) return 1;                     /* no memory: the whole-map pass decides */
    }
    if (g->seen[i]) return g->seen[i] == 2;
    g->seen[i] = 1;
    g->q[n++] = i;
    while (head < n) {
        int c = g->q[head++], cx = g->x0 + c % g->w, cz = g->z0 + c / g->w, dx, dz;
        if (cut_at_border(g, cx, cz)) hit = 1;
        for (dz = -1; dz <= 1; dz++)
            for (dx = -1; dx <= 1; dx++) {
                int nx = cx + dx, nz = cz + dz, j;
                DWORD v;
                if ((!dx && !dz) || nx < g->x0 || nz < g->z0 || nx > g->x1 || nz > g->z1) continue;
                j = (nz - g->z0) * g->w + (nx - g->x0);
                if (g->seen[j] || keep[j]) continue;
                v = rb_at(b, nx, nz);
                if (!v || !is((WORD)(v & 0xffff))) continue;
                g->seen[j] = 1;
                g->q[n++] = j;
            }
    }
    for (k = 0; k < n; k++) g->seen[g->q[k]] = (BYTE)(hit ? 2 : 1);
    return hit;
}

/* before the revert loop: -> 1 when the windowed pass must revert nothing (the whole-map pass decides). border = the
   pass's own flag (a kept band reached the border); stale cells are those is() pieces in the inner area not kept. */
static int cut_hold(CutGuard *g, RbBuf *b, int border, int (*is)(WORD), const BYTE *keep, int (*skip)(int, int),
                    const char *who, const char *blk) {
    int x, z;
    if (!g->on || g->full) return 0;
    if (border) return 1;
    for (z = g->z0 + 1; z < g->z1; z++)
        for (x = g->x0 + 1; x < g->x1; x++) {
            DWORD v = rb_at(b, x, z);
            if (!v || !is((WORD)(v & 0xffff)) || keep[(z - g->z0) * g->w + (x - g->x0)] || (skip && skip(x, z))) continue;
            if (cut_reaches(g, b, x, z, is, keep)) {
                InterlockedIncrement(&g_cut_n_cut);
                logf("%s: %s: (%d,%d) piece %lu belongs to a run the read window (%d,%d)-(%d,%d) cuts: not reverted, "
                     "whole-map pass", blk, who, x, z, v & 0xffff, g->x0, g->z0, g->x1, g->z1);
                return 1;
            }
        }
    return 0;
}

/* after the revert loop (nrev > 0): the cells this pass wrote that the reverts' run-wide stock retile changed */
static void cut_reput(CutGuard *g, BYTE *mgr, void *lay, const char *who, const char *blk) {
    int x, z, n = 0;
    if (!g->want) return;
    for (z = g->z0; z <= g->z1; z++)
        for (x = g->x0; x <= g->x1; x++) {
            DWORD want = g->want[(z - g->z0) * g->w + (x - g->x0)], cur;
            int pos[3];
            if (!want) continue;
            cur = rb_read(mgr, lay, x, z, g->W, g->H);
            if (!cur || ((((cur & 0xffff) << 8) | ((cur >> 16) & 3)) == want)) continue;
            pos[0] = x << 8; pos[1] = z << 8; pos[2] = 0;
            ((PFN_Put)(g_rb_m + 0x8919))(mgr, 0, lay, pos, want, -1, 8, 0);
            n++;
        }
    if (n) {
        g->nreput += n;
        InterlockedExchangeAdd(&g_cut_n_reput, n);
        logf("%s: %s: %d written cell(s) changed by the reverts' stock retile, put back", blk, who, n);
    }
}

static void cut_stats(void) {
    static LONG last;
    LONG n = g_cut_n_cut + g_cut_n_reput;
    if (n == last) return;
    last = n;
    logf("stats: cut windows held for the whole-map pass=%ld, cells put back after a revert=%ld", g_cut_n_cut,
         g_cut_n_reput);
}
