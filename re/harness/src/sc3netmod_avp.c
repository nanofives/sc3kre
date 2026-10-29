/* sc3netmod_avp.c - the AVP block of sc3netmod.dll (task avpaint, 2026-10-28): the avenue LOOK on bands AVL leaves
 * two-way. #included by sc3netmod.c after the AVL block; avl_pass calls avp_run last (after its post hooks), on the same
 * box, so it sees AVL's final band map.
 *
 * Owner 2026-10-28 (LAN build sc3mods-2026-10-27f, img1 slope / img2 corner): an avenue band AVL refuses stays two-way
 * (owner call 2026-10-19, kept), but its corner bends, U-turn ends and slope cells drew the plain road (yellow centre
 * line, no median) while its straights drew avenue_markings' white dashes. AVP gives those cells a LOOK-ONLY twin of the
 * piece AVL would have written there: the same art (white dashes, median trees on slopes), the STOCK base and its
 * stock two-way lanes (no lane spec, trblkatt copy_base), saved as the base at the same state (SAVEBASE).
 *
 * Table line (netpack key `avenue_lines`, parsed by avl_line):
 *   avlp <paint> <piece>   <paint> = the look-only twin of AVL's <piece> (avlu / avlk / an avlc piece): same base
 * Which cells: the band rows, U-turn pairs and corner blocks AVL's own rule finds (avl_row, avl_end's U states,
 * avl_corner_at), of a band that AVL did not convert (no avl_claimed cell) and that holds at least one straight 11204
 * row (two parallel slope roads alone are not an avenue). Each such cell gets the twin of the piece AVL would write there
 * (if that piece has one). A corner + T block is not painted. Never a plain road curve or slope: those are not in a band.
 * Every reader sees the base: rb_read / hwy_read (hwlt_read, sc3netmod_rbt.c) return the base id with the twin's index
 * in bits 20..27 (AVP_IX), so AVL, AVX and every sibling decide on the stock grid and AVL writes over a painted cell
 * as over the stock one. AVP's own writes compare that index. Painted cells that no longer qualify get their base back
 * (the box + 2, as AVL's reverts). Off: SC3NETMOD_AVP=0.
 */

#define AVP_MAX 64
static WORD g_avp_of[AVP_MAX + 1];                          /* index -> the AVL piece it is the twin of */
static int g_avp_n, g_avp_on = -1;
static volatile LONG g_avp_n_cells, g_avp_n_rev, g_avp_n_bands;

static void avp_line(const char *path, const char *line) {
    unsigned long v, a;
    if (sscanf(line + 5, "%lu %lu", &v, &a) != 2 || !v || v > 0xffff || !a || a > 0xffff || v == a || !g_base[v] ||
        g_base[v] != g_base[a] || g_avp_tw[a] || (!g_avp_ix[v] && g_avp_n >= AVP_MAX)) {
        logf("### avp: %s: bad paint line (not a variant of the piece's base, piece named twice, or too many): '%s'", path,
             line);
        return;
    }
    if (!g_avp_ix[v]) { g_avp_n++; g_avp_ix[v] = (BYTE)g_avp_n; g_avp_id[g_avp_n] = (WORD)v; }   /* one twin, several pieces */
    g_avp_of[g_avp_ix[v]] = (WORD)a; g_avp_tw[a] = (WORD)v;
    logf("avp: %s: look-only %lu = the look of %lu on base %u, stock lanes", path, v, a, g_base[v]);
}

static int avp_enabled(void) {
    if (g_avp_on < 0) {
        g_avp_on = !env_off("SC3NETMOD_AVP");
        logf("avp: avenue look on two-way bands %s (%d twin(s))", g_avp_on ? "on" : "off (SC3NETMOD_AVP=0)", g_avp_n);
    }
    return g_avp_on && g_avp_n;
}

/* Straight rows (task cartrees, 2026-10-29): with a twin of AVL's straight half declared (`avlp 21742 21700`), both
 * cells of every straight row of a two-way band get it, so the band draws 21700's look: its layer 1 holds both halves'
 * median trees in the far half's slots (avenue_markings.py --trees), which stock 11204 cannot do because 6.9% of its
 * halves face a road T across the median, not the mirrored half. A band row is always the mirrored pair (avl_row).
 * Off: SC3NETMOD_AVPSTRAIGHT=0 (straights stay stock 11204, as before). */
static int g_avp_str_on = -1;

static int avp_straight_on(void) {
    if (g_avp_str_on < 0) {
        g_avp_str_on = !env_off("SC3NETMOD_AVPSTRAIGHT");
        logf("avp: straight rows %s (twin %u)", g_avp_str_on ? "painted" : "stock (SC3NETMOD_AVPSTRAIGHT=0)",
             g_avl_straight ? g_avp_tw[g_avl_straight] : 0);
    }
    return g_avp_str_on && g_avl_straight && g_avp_tw[g_avl_straight];
}

typedef struct { int x, z; DWORD want; } AvpW;              /* want = paint << 8 | state */

static void avp_add(AvlPass *p, BYTE *mark, AvpW *w, int *nw, int cap, int x, int z, WORD piece) {
    DWORD v = avl_at(p, x, z);
    WORD tw = piece ? g_avp_tw[piece] : 0;
    if (!v || !tw || x < 0 || z < 0 || x >= p->W || z >= p->H || mark[z * p->W + x]) return;
    if (*nw >= cap) return;
    mark[z * p->W + x] = 1;
    w[*nw].x = x; w[*nw].z = z; w[*nw].want = ((DWORD)tw << 8) | AVL_ST(v); (*nw)++;
}

/* the U-turn pair / plain corner past the row at offset k: its cells' AVL pieces -> twins */
static void avp_end(AvlPass *p, BYTE *mark, AvpW *w, int *nw, int cap, int axis, int ax, int az, int k, int end) {
    static const int USTATE[2][2][2] = { { { 3, 0 }, { 2, 1 } }, { { 3, 2 }, { 0, 1 } } };   /* = avl_end's */
    int dx = axis ? 1 : 0, dz = axis ? 0 : 1, fwd = end > 0, c, oaxis, ox, oz, oass;
    int x = ax + dx * k, z = az + dz * k, bx = x + (axis ? 0 : 1), bz = z + (axis ? 1 : 0);
    DWORD a = avl_at(p, x, z), b = avl_at(p, bx, bz);
    AvlCT ct;
    if (!a || !b) return;
    if (AVL_ID(a) == 11203 && AVL_ID(b) == 11203 && AVL_ST(a) == USTATE[axis][fwd][0] && AVL_ST(b) == USTATE[axis][fwd][1] &&
        avl_free(p, x, z, a) && avl_free(p, bx, bz, b)) {
        avp_add(p, mark, w, nw, cap, x, z, g_avl_uturn);
        avp_add(p, mark, w, nw, cap, bx, bz, g_avl_uturn);
        return;
    }
    if ((c = avl_corner_at(p, axis, ax, az, k, end, &oaxis, &ox, &oz, &oass, NULL, &ct)) != 0 && !ct.n) {
        int ib = c == 2, x2 = x + dx * end, z2 = z + dz * end, bx2 = bx + dx * end, bz2 = bz + dz * end;
        int ix = ib ? bx : x, iz = ib ? bz : z, ox2 = ib ? x2 : bx2, oz2 = ib ? z2 : bz2;
        avp_add(p, mark, w, nw, cap, ix, iz, g_avl_corner);
        if (AVL_ID(avl_at(p, ox2, oz2)) == 11203) avp_add(p, mark, w, nw, cap, ox2, oz2, g_avl_uturn);
    }
}

static void avp_band(AvlPass *p, BYTE *mark, AvpW *w, int *nw, int cap, int axis, int ax, int az) {
    int dx = axis ? 1 : 0, dz = axis ? 0 : 1, k0 = 0, k1 = 0, k, c, straight = 0, conv = 0, n0 = *nw;
    while (k0 > -AVL_MAXLEN && avl_row(p, axis, ax, az, k0 - 1)) k0--;
    while (k1 < AVL_MAXLEN && avl_row(p, axis, ax, az, k1 + 1)) k1++;
    for (k = k0; k <= k1; k++) {                                   /* mark the band walked (p->seen), find a straight */
        int x = ax + dx * k, z = az + dz * k, bx = x + (axis ? 0 : 1), bz = z + (axis ? 1 : 0);
        p->seen[z * p->W + x] = 1; p->seen[bz * p->W + bx] = 1;
        if (avl_is_straight(AVL_ID(avl_at(p, x, z)))) straight = 1;
        if (avl_claimed(x, z) || avl_claimed(bx, bz)) conv = 1;
    }
    if (!straight || conv) return;                                 /* not an avenue, or AVL's */
    for (k = k0; k <= k1; k++)                                     /* crossing / slope rows: the twin of AVL's variant */
        for (c = 0; c < 2; c++) {
            int cx = ax + dx * k + (c && !axis ? 1 : 0), cz = az + dz * k + (c && axis ? 1 : 0);
            int dir = axis ? (c ? 3 : 1) : (c ? 2 : 0), ci;
            DWORD v = avl_at(p, cx, cz);
            if (v && avl_is_straight(AVL_ID(v)) && avp_straight_on()) {   /* straight row: both halves are 11204 */
                avp_add(p, mark, w, nw, cap, cx, cz, g_avl_straight);
                continue;
            }
            if (!v || avl_is_straight(AVL_ID(v)) || (ci = avl_cross_of(AVL_ID(v))) < 0) continue;
            avp_add(p, mark, w, nw, cap, cx, cz, avl_cross_want(g_avl_c[ci].base, AVL_ST(v), dir));
        }
    avp_end(p, mark, w, nw, cap, axis, ax, az, k0 - 1, -1);
    avp_end(p, mark, w, nw, cap, axis, ax, az, k1 + 1, 1);
    if (*nw > n0) InterlockedIncrement(&g_avp_n_bands);
}

static void avp_run(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who) {
    AvlPass P;
    AvpW *w;
    BYTE *mark;
    int x, z, k, nw = 0, n = 0, nrv = 0, cap;
    if (!avp_enabled()) return;
    P.mgr = mgr; P.lay = *(void **)(mgr + 0x3c);
    P.W = (*(int *)(mgr + 0x5c) >> 8) + 1; P.H = (*(int *)(mgr + 0x60) >> 8) + 1;
    if (P.W < 4 || P.H < 4 || P.W > 4096 || P.H > 4096) return;
    if (x0 < 0) x0 = 0;
    if (z0 < 0) z0 = 0;
    if (x1 > P.W - 1) x1 = P.W - 1;
    if (z1 > P.H - 1) z1 = P.H - 1;
    x0 -= 2; z0 -= 2; x1 += 2; z1 += 2;
    cap = strcmp(who, "load") ? 1 << 14 : 1 << 18;
    P.c = (DWORD *)VirtualAlloc(NULL, (SIZE_T)P.W * P.H * 7 + (SIZE_T)cap * sizeof(AvpW), MEM_COMMIT, PAGE_READWRITE);
    if (!P.c) return;
    P.rd = (BYTE *)(P.c + P.W * P.H);
    P.seen = P.rd + P.W * P.H;
    mark = P.seen + P.W * P.H;
    w = (AvpW *)(mark + P.W * P.H);
    for (z = z0 < 0 ? 0 : z0; z <= z1 && z < P.H; z++)             /* seeds: as avl_run */
        for (x = x0 < 0 ? 0 : x0; x <= x1 && x < P.W; x++) {
            DWORD v = avl_at(&P, x, z);
            WORD id = AVL_ID(v);
            int st = AVL_ST(v);
            if (!v || P.seen[z * P.W + x]) continue;
            if (avl_is_straight(id)) {
                if (st == 1 && avl_row(&P, 0, x, z, 0)) avp_band(&P, mark, w, &nw, cap, 0, x, z);
                else if (st == 2 && avl_row(&P, 1, x, z, 0)) avp_band(&P, mark, w, &nw, cap, 1, x, z);
                else if (st == 3 && avl_row(&P, 0, x - 1, z, 0)) avp_band(&P, mark, w, &nw, cap, 0, x - 1, z);
                else if (st == 0 && avl_row(&P, 1, x, z - 1, 0)) avp_band(&P, mark, w, &nw, cap, 1, x, z - 1);
            } else if (avl_cross_of(id) >= 0) {
                if (avl_row(&P, 0, x, z, 0)) avp_band(&P, mark, w, &nw, cap, 0, x, z);
                else if (avl_row(&P, 0, x - 1, z, 0)) avp_band(&P, mark, w, &nw, cap, 0, x - 1, z);
                else if (avl_row(&P, 1, x, z, 0)) avp_band(&P, mark, w, &nw, cap, 1, x, z);
                else if (avl_row(&P, 1, x, z - 1, 0)) avp_band(&P, mark, w, &nw, cap, 1, x, z - 1);
            }
        }
    /* painted cells in the box that no band keeps: their base back (read value = base id + AVP_IX) */
    for (z = z0 < 0 ? 0 : z0; z <= z1 && z < P.H; z++)
        for (x = x0 < 0 ? 0 : x0; x <= x1 && x < P.W; x++) {
            DWORD v = avl_at(&P, x, z);
            int pos[3];
            if (!v || !(v & AVP_IX) || mark[z * P.W + x]) continue;
            pos[0] = x << 8; pos[1] = z << 8; pos[2] = 0;
            ((PFN_Put)(g_rb_m + 0x8919))(mgr, 0, P.lay, pos, ((DWORD)AVL_ID(v) << 8) | AVL_ST(v), -1, 8, 0);
            nrv++;
        }
    if (nrv) ZeroMemory(P.rd, (SIZE_T)P.W * P.H);                 /* read again, as avl_run */
    for (k = 0; k < nw; k++) {
        DWORD cur = avl_at(&P, w[k].x, w[k].z);
        int pos[3], ix = (int)((cur & AVP_IX) >> 20);
        if (ix && ((DWORD)g_avp_id[ix] << 8 | AVL_ST(cur)) == w[k].want) continue;
        pos[0] = w[k].x << 8; pos[1] = w[k].z << 8; pos[2] = 0;
        ((PFN_Put)(g_rb_m + 0x8919))(mgr, 0, P.lay, pos, w[k].want, -1, 8, 0);
        n++;
    }
    if (n || nrv || !strcmp(who, "load"))
        logf("avp: %s pass over (%d,%d)-(%d,%d): %d cell(s) painted, %d given back%s", who, x0, z0, x1, z1, n, nrv,
             nw >= cap ? " (LIST FULL)" : "");
    VirtualFree(P.c, 0, MEM_RELEASE);
    InterlockedExchangeAdd(&g_avp_n_cells, n);
    InterlockedExchangeAdd(&g_avp_n_rev, nrv);
}

static void avp_stats(void) {
    static LONG last;
    LONG n = g_avp_n_cells + g_avp_n_rev + g_avp_n_bands;
    if (g_avp_on != 1 || n == last) return;
    last = n;
    logf("stats: avp two-way bands painted=%ld, cells painted=%ld, given back=%ld", g_avp_n_bands, g_avp_n_cells,
         g_avp_n_rev);
}
