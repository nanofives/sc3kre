/* task diagxnet (round 2026-11-15b, xsect 68 69 72 73; owner 2026-11-15 "Yes, build them", stop lines "Keep them"):
 * DAVXN, the diagonal level crossing and the diagonal underpass. #included by sc3netmod_dav.c right after dav_xnet().
 *
 * DAVXNET (diagfix) keeps a rail / highway crossing cell under a diagonal avenue or boulevard: no DAV / DBV write
 * touches it, so it showed the stock crossing (69 road x rail, 15098 / 11258 highway over road) with straight 2-lane
 * road art. Now, on such a cell, the band's own piece for that cell (what DAV / DBV would have written there, `want`)
 * picks a variant of the crossing piece from the package's table:
 *
 *   davxn <base> <base state> <band piece> <band state> <variant>
 *
 * The variant is written at the base's own state (69: 0 / 1 by the rail's axis; 15098 / 11258: 0 / 2 by the deck
 * half), so it inherits every Set (the rail / highway is not cut), Protected list, Convert row, the turn matrix (highway
 * trips, prop 310) and saves as the stock crossing. Art = the band's lanes with the rail through / the deck over one
 * band-shaped opening; lanes = the band's car lanes + the base's train / highway lanes (re/tools/netmod/xnet_build.py).
 * A cell holding one of these variants that no line matches any more (band changed, switch off) or that no band keeps
 * (the DAV revert scan) gets its base back at the same state (a stock retile keeps a Protected cell as it is).
 * Off: SC3NETMOD_DAVXNRAIL=0 (rail crossings), SC3NETMOD_DAVXNHWY=0 (underpasses): stock crossing as before. */
#define DAVXN_MAX 256
typedef struct { WORD base, band, piece; BYTE bst, sst; } DavXn;
static DavXn g_davxn[DAVXN_MAX];
static int g_davxn_n, g_davxn_rail = -1, g_davxn_hwy = -1;
static volatile LONG g_davxn_n_put, g_davxn_n_back;

static void davxn_line(const char *path, const char *line) {
    unsigned long b, bs, p, ps, v;
    if (sscanf(line + 6, "%lu %lu %lu %lu %lu", &b, &bs, &p, &ps, &v) != 5 || bs > 3 || ps > 3 || !p || p > 0xffff ||
        !v || v > 0xffff || (b != 69 && b != 15098 && b != 11258) || g_base[v] != (WORD)b) {
        logf("### dav: %s: bad davxn line (or the piece is not a variant of 69 / 15098 / 11258): '%s'", path, line);
        return;
    }
    if (g_davxn_n >= DAVXN_MAX) { logf("### dav: %s: too many davxn lines (%d) - '%s' ignored", path, DAVXN_MAX, line); return; }
    g_davxn[g_davxn_n].base = (WORD)b; g_davxn[g_davxn_n].bst = (BYTE)bs; g_davxn[g_davxn_n].band = (WORD)p;
    g_davxn[g_davxn_n].sst = (BYTE)ps; g_davxn[g_davxn_n].piece = (WORD)v;
    g_davxn_n++;
}

static int davxn_on(WORD base) {
    if (g_davxn_rail < 0) {
        g_davxn_rail = !env_off("SC3NETMOD_DAVXNRAIL");
        g_davxn_hwy = !env_off("SC3NETMOD_DAVXNHWY");
        logf("dav: DAVXN diagonal level crossings %s (SC3NETMOD_DAVXNRAIL), diagonal underpasses %s (SC3NETMOD_DAVXNHWY), "
             "%d davxn line(s)", g_davxn_rail ? "on" : "off", g_davxn_hwy ? "on" : "off", g_davxn_n);
    }
    return base == 69 ? g_davxn_rail : g_davxn_hwy;
}

static int davxn_is(WORD id) {
    int k;
    for (k = 0; id && k < g_davxn_n; k++) if (g_davxn[k].piece == id) return 1;
    return 0;
}

/* the piece (id << 8 | state) for kept crossing cell `cur` under band piece `want` (id << 8 | state), 0 = leave it */
static DWORD davxn_pick(DWORD cur, DWORD want) {
    WORD id = (WORD)(cur & 0xffff), b = g_base[id] ? g_base[id] : id;
    int st = (int)((cur >> 16) & 3), k;
    if (!g_davxn_n) return 0;
    if (davxn_on(b))
        for (k = 0; k < g_davxn_n; k++)
            if (g_davxn[k].base == b && g_davxn[k].bst == st && g_davxn[k].band == (WORD)(want >> 8) &&
                g_davxn[k].sst == (BYTE)(want & 0xff))
                return ((DWORD)g_davxn[k].piece << 8) | (DWORD)st;
    if (davxn_is(id)) return ((DWORD)b << 8) | (DWORD)st;   /* ours, no line for it now: the stock crossing back */
    return 0;
}

/* DAV / DBV write loops: a kept crossing cell (dav_xnet) -> its variant, written when it differs. -> 1 written */
static int davxn_write(BYTE *mgr, void *lay, int x, int z, DWORD cur, DWORD want) {
    DWORD w = davxn_pick(cur, want);
    int pos[3];
    if (!w || (((cur & 0xffff) << 8) | ((cur >> 16) & 3)) == w) return 0;
    pos[0] = x << 8; pos[1] = z << 8; pos[2] = 0;
    ((PFN_Put)(g_rb_m + 0x8919))(mgr, 0, lay, pos, w, -1, 8, 0);
    InterlockedIncrement(davxn_is((WORD)(w >> 8)) ? &g_davxn_n_put : &g_davxn_n_back);
    return 1;
}

/* DAV's revert scan: one of our variants that no band kept in this window -> its base at the same state. -> 1 reverted */
static int davxn_back(BYTE *mgr, void *lay, DWORD v, int x, int z, int kept, const char *who) {
    WORD id = (WORD)(v & 0xffff);
    int pos[3];
    if (!v || kept || !davxn_is(id)) return 0;
    pos[0] = x << 8; pos[1] = z << 8; pos[2] = 0;
    ((PFN_Put)(g_rb_m + 0x8919))(mgr, 0, lay, pos, ((DWORD)g_base[id] << 8) | ((v >> 16) & 3), -1, 8, 0);
    InterlockedIncrement(&g_davxn_n_back);
    logf("dav: %s: (%d,%d) crossing piece %u no longer under a band -> stock %u (DAVXN)", who, x, z, id, g_base[id]);
    return 1;
}

/* task diagxnet (owner 2026-11-16 "Fix it"): DAVXHEAL, rail or a highway drawn ACROSS an existing diagonal road / avenue /
 * boulevard. The drag skips the diagonal's cells: the crossing builder FUN_100167d4 [CONFIRMED @ SIMNTWRK 0x100167d4]
 * only knows straight road (0x1d, 0x2bc4) as the existing piece, so 35 and every DAV / DBV piece (bases 35, 43, 18004)
 * get no crossing, and the run is placed on both sides with the diagonal left in between: the line was cut (stock does
 * the same with a plain diagonal road). After every rail (net 2) and highway (net 4) pass, a straight run of that network
 * interrupted by 1..DAVXH_GAP diagonal-road cells, with two run cells on each side, gets the stock crossing piece on the
 * gap cells: 69 at state 1 (rail along x) / 0 (along z), the same pieces drawing the rail first gives (xsect 68 / 69 / 74);
 * 15098 next to 15051, 11258 next to 73, at the neighbour's state (the deck half). Then DBV and DAV run over the box,
 * so a diagonal avenue / boulevard's kept crossing cells take their DAVXN variants. Off: SC3NETMOD_DAVXHEAL=0. */
#define DAVXH_GAP 4
static void dbv_run(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who);   /* sc3netmod_dbv.c */
static void dav_run(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who);   /* sc3netmod_dav.c */
static int g_davxh = -1;
static volatile LONG g_davxh_n_runs, g_davxh_n_cells;

/* the surface occupant at (x, z) if the manager's network test vt+0x14c accepts it for network `net`: id | state << 16 */
static DWORD davxh_read(BYTE *mgr, void *lay, int x, int z, int W, int H, int net) {
    void *occ = NULL;
    DWORD r = 0, vt;
    if (x < 0 || z < 0 || x >= W || z >= H) return 0;
    if (!((PFN_At)VT(lay, 0x7c))(lay, 0, x, z, &occ) || !occ) return 0;
    vt = *(DWORD *)occ;
    if (vt >= (DWORD)g_rb_m && vt < (DWORD)g_rb_m + g_rb_msize && ((PFN_Pred)VT(mgr, 0x14c))(mgr, 0, net, occ))
        r = 0x80000000UL | ((*(DWORD *)((BYTE *)occ + 0x10) >> 30) << 16) | (*(DWORD *)((BYTE *)occ + 0x14) & 0xffff);
    ((PFN_B0)VT(occ, 8))(occ);
    return r;
}

static int davxh_diag(DWORD v) {                 /* a diagonal road / avenue / boulevard cell (never stock 43) */
    WORD id = (WORD)(v & 0xffff), b;
    if (!v) return 0;
    if (id == 35) return 1;
    b = g_base[id];
    return id >= 20000 && (b == 35 || b == 43 || b == 18004);
}

/* a plain run cell of network net: rail 44, highway 15051 / 73 (-> 0 none) */
static WORD davxh_line(DWORD v, int net) {
    WORD id = (WORD)(v & 0xffff);
    if (!v) return 0;
    if (net == 2) return id == 44 ? id : 0;
    return id == 15051 || id == 73 ? id : 0;
}

static void davxn_heal(BYTE *mgr, int net, int bx0, int bz0, int bx1, int bz1, const char *who) {
    void *lay = *(void **)(mgr + 0x3c);
    int W = (*(int *)(mgr + 0x5c) >> 8) + 1, H = (*(int *)(mgr + 0x60) >> 8) + 1, ax, nw = 0;
    int x0 = bx0 - DAVXH_GAP - 3, z0 = bz0 - DAVXH_GAP - 3, x1 = bx1 + DAVXH_GAP + 3, z1 = bz1 + DAVXH_GAP + 3;
    if (g_davxh < 0) {
        g_davxh = !env_off("SC3NETMOD_DAVXHEAL");
        logf("dav: DAVXHEAL %s (rail / highway drawn across an existing diagonal gets its crossing, SC3NETMOD_DAVXHEAL)",
             g_davxh ? "on" : "off");
    }
    if (!g_davxh || (net != 2 && net != 4) || W < 4 || H < 4 || W > 4096 || H > 4096) return;
    if (x0 < 0) x0 = 0;
    if (z0 < 0) z0 = 0;
    if (x1 > W - 1) x1 = W - 1;
    if (z1 > H - 1) z1 = H - 1;
    for (ax = 0; ax < 2; ax++) {                 /* 0: runs along x (rows), 1: along z (columns) */
        int a, s, A0 = ax ? z0 : x0, A1 = ax ? z1 : x1, S0 = ax ? x0 : z0, S1 = ax ? x1 : z1;
        for (s = S0; s <= S1; s++)
            for (a = A0 + 1; a + 2 <= A1; a++) {
#define DXH_AT(aa, nn) davxh_read(mgr, lay, ax ? s : (aa), ax ? (aa) : s, W, H, (nn))
                DWORD L1 = DXH_AT(a, net), L0, R0, R1, d;
                WORD lid = davxh_line(L1, net);
                int g, k, st;
                if (!lid || !davxh_diag(DXH_AT(a + 1, 1))) continue;
                L0 = DXH_AT(a - 1, net);
                if (davxh_line(L0, net) != lid) continue;
                for (g = 1; g <= DAVXH_GAP && davxh_diag(DXH_AT(a + g, 1)); g++) ;
                g--;                             /* cells a+1 .. a+g are diagonal */
                R0 = DXH_AT(a + g + 1, net); R1 = DXH_AT(a + g + 2, net);
                if (davxh_line(R0, net) != lid || davxh_line(R1, net) != lid) continue;
                if (net == 4 && (((L1 >> 16) & 3) != ((R0 >> 16) & 3))) continue;   /* one deck half */
                st = net == 2 ? (ax ? 0 : 1) : (int)((L1 >> 16) & 3);
                for (k = 1; k <= g; k++) {
                    int pos[3], cx = ax ? s : a + k, cz = ax ? a + k : s;
                    d = ((DWORD)(net == 2 ? 69 : lid == 15051 ? 15098 : 11258) << 8) | (DWORD)st;
                    pos[0] = cx << 8; pos[1] = cz << 8; pos[2] = 0;
                    ((PFN_Put)(g_rb_m + 0x8919))(mgr, 0, lay, pos, d, -1, 8, 0);
                    nw++;
                }
                InterlockedIncrement(&g_davxh_n_runs);
                InterlockedExchangeAdd(&g_davxh_n_cells, g);
                logf("dav: %s: %s along %c at %d across a diagonal, cells %d..%d: %d cell(s) -> %u.%d (DAVXHEAL)", who,
                     net == 2 ? "rail" : "highway", ax ? 'z' : 'x', s, a + 1, a + g, g,
                     net == 2 ? 69 : lid == 15051 ? 15098 : 11258, st);
                a += g;
#undef DXH_AT
            }
    }
    if (nw) {                                    /* the band blocks over the box: kept crossings -> DAVXN variants */
        dbv_run(mgr, x0, z0, x1, z1, "heal");
        if (g_dav_on) dav_run(mgr, x0, z0, x1, z1, "heal");
    }
}
