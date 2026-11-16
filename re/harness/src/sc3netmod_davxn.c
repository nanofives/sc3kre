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
