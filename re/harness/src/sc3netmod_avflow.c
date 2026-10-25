/* sc3netmod_avflow.c - the AVFLOW blocks of sc3netmod.dll (task avflow, 2026-10-24): AVFIRST + AVDEPOSIT.
 * #included by sc3netmod_lanes.c after sc3netmod_rampfirst.c; rides on LANEDENSITY's entry detour of SimTransit
 * FUN_1000755e and uses its helpers (ld_flags, ld_mark, ld_close). Evidence and measurements: verify/avflow/RESULTS.md.
 *
 * Owner 2026-10-24: "make a 2-road avenue and 3-road avenue (boulevard) increase traffic flow"; chosen: avenue-first
 * routing together with lighter traffic per trip on avenue / boulevard cells.
 *
 * Stock: a road (type 1) or bus (0x41) node's ring scan (SimTransit 0x10007a63) keeps the busiest road candidate below
 * TrafficAnnoyanceLevel (DAT_1001f0c0, keep rule 0x10007db4), whatever the piece. On arrival route_trip 0x100070d0
 * pops the final path and, for every type-1 (and 0x50) node, calls FUN_10006edd(layer, x, z, amount, 0x15) at
 * 0x10007463 [CONFIRMED @ SimTransit 0x10007463]; amount = start-lot area x TripDensityAdder (DAT_1001f0be), as a
 * char [CONFIRMED @ 0x100070d0]. Same rule and amount on every road piece, avenues included.
 *
 *   CLASS grid  one byte per cell, 0 = other, 1 = avenue, 2 = boulevard; filled on the game thread after RBT's edit
 *               pass (rb_pass, box + 3) and load pass (rb_load_pass, whole map), from the piece in each cell:
 *               boulevard = a BV piece that is not a BVX junction box (bv_is_piece, bvx_is_piece), or a DBV piece;
 *               avenue = stock 11204 or a variant of it, stock 11203, an AVL piece (avl_own), a cell an AVL band
 *               claims (avl_claimed), or a DAV avenue piece that is not a junction (dav_is_mid, dav_is_junc).
 *               AVX median noses count as avenue. Junction boxes (AVX boxes and corners, BVX, DAV junctions,
 *               stock 39 / 43) stay class 0.
 *   AVFIRST     when a 1x1 road / bus node has an open avenue / boulevard candidate (road cell, not visited by the
 *               node type, density +0x6c below TrafficAnnoyanceLevel), every other road candidate is closed in the
 *               visited grid for that one call (ld_close; ld_select clears the bits after the call). The stock rule
 *               then picks the busiest open avenue cell below the level. Runs after RAMPFIRST, so an offered on-ramp
 *               still wins. On a later retry the stock order applies (the avenue cells are visited by then).
 *   BVFIRST     (inside AVFIRST, its own switch) when an open boulevard candidate below the level is offered, the open
 *               avenue candidates are closed too, so the boulevard is taken; with only avenue cells open, AVFIRST as
 *               above. Off by default until measured. SC3NETMOD_AVF_BVFIRST=1 on, live sc3netmod_avf_bv_set(0|1).
 *   AVDEPOSIT   the call at 0x10007463 goes through avd_dep: on an avenue cell the amount is scaled by 2/3, on a
 *               boulevard cell by 1/3; the remainder is kept per cell (CAS on a LONG per cell), so the long-run
 *               deposit is exact. The scaled amount goes on to the original target (sc3perf's atomic deposit sits
 *               behind the same entry, TRAFFIC_MT). Only the type-1 road deposit site is touched: stations, highways,
 *               subways and the monthly decrement keep stock amounts.
 *
 *   BVCOST      (task bventry) after a road / bus step onto a 1x1 boulevard cell (or avenue cell, its own scale), the
 *               step's cost (out+0x18 - node+0x18, SimTransit 0x10008468: 4 + density/25 for a road) is scaled by n/d,
 *               rounded up, at least 1. The trip budget (route_trip: DAT_1001f0b0 x param_3, checked first thing in
 *               FUN_1000755e) then lasts longer through boulevards. Two switches: SC3NETMOD_BVCOST=1 (boulevard cells,
 *               scale SC3NETMOD_AVCOST_BV=n/d, default 1/2), SC3NETMOD_AVCOST=1 (avenue cells, scale
 *               SC3NETMOD_AVCOST_AV=n/d, default 1/2); live sc3netmod_avc_set(0|1), sc3netmod_avc_av_set(0|1).
 *               Evidence: verify/bventry/RESULTS.md.
 *   AVSTART     (task bventry) AVFIRST for a trip's START node (type 0x80, the lot). FUN_1000755e's start branch scans
 *               every road cell within r of the lot rect (corners excluded), r = layer+0xc5 / +0xc6 / +0xc7 by the lot's
 *               kind from FUN_100057f6 (thiscall on the layer: (occupant, &kind)), else +0xc8, with the ring scan's keep rule (busiest road
 *               below TrafficAnnoyanceLevel) [CONFIRMED @ SimTransit 0x1000755e]. So a lot beside an empty boulevard
 *               starts its trips on a busier road nearby (measured: 2 of 3 starts with an open boulevard cell in range).
 *               With AVSTART, when an open avenue / boulevard cell below the level is in range, every other open road
 *               cell in the box is closed for that one call (stations stay). SC3NETMOD_AVSTART=1 (avenue and boulevard
 *               cells), =2 (boulevard cells only), =0 off; live sc3netmod_avs_set(0|1|2). Default off (recommended on, RESULTS 3.1).
 *
 * Both on by default (measured, verify/avflow/RESULTS.md). Off switches: SC3NETMOD_AVFIRST=0, SC3NETMOD_AVDEPOSIT=0. Scales:
 * SC3NETMOD_AVDEP_AV=n/d, SC3NETMOD_AVDEP_BV=n/d. Live (measurement): sc3netmod_avf_set(0|1), sc3netmod_avd_set(0|1),
 * sc3netmod_avflow_set(0|1) (both), sc3netmod_avf_bv_set(0|1), sc3netmod_avf_grid(&w, &h) -> the class grid (index z * w + x).
 */

#define AVF_DEFAULT_FIRST   1        /* on: measured in verify/avflow/RESULTS.md (Seoul, one game, off / F / FD) */
#define AVF_DEFAULT_DEPOSIT 1
#define AVF_DEFAULT_BVFIRST 0        /* task avflow BVFIRST: set from verify/avflow/RESULTS.md section 2.7 */
#define AVF_DEFAULT_BVCOST  0        /* task bventry: set from verify/bventry/RESULTS.md */
#define AVF_DEFAULT_AVCOST  0        /* task bventry: the avenue half of BVCOST, its own switch */
#define AVF_DEFAULT_AVSTART 0        /* task bventry: AVFIRST at the trip start; measured better (verify/bventry/RESULTS.md 3.1), off until the orchestrator / owner turn it on */
#define AVS_MAX 1024                 /* cells AVSTART may close in one call (a 6x6 lot at r 8: 22 x 22 = 484) */

static volatile LONG g_avf_on, g_avd_on, g_avf_bv;
static volatile LONG g_avf_n_bvoffer, g_avf_n_bvclosed;   /* BVFIRST: offers with an open boulevard cell, avenue cells closed */
static volatile LONG g_avf_n_offer, g_avf_n_closed, g_avd_n_dep[3], g_avd_n_in[3], g_avd_n_out[3], g_avf_n_fault;
static BYTE *volatile g_avf_cls;                 /* class grid, z * g_avf_w + x */
static LONG *volatile g_avd_carry;               /* remainder per cell, same index */
static volatile LONG g_avf_w, g_avf_h;
static LONG g_avd_num[3] = {1, 2, 1}, g_avd_den[3] = {1, 3, 3};
static DWORD g_avd_orig;                         /* SimTransit FUN_10006edd */
static DWORD g_avf_st;
static volatile LONG g_avf_ncls[3];
static volatile LONG g_avf_sweep_row = -1;       /* next row of the background sweep, -1 idle */
static BYTE *g_avf_sweep_mgr;
static volatile LONG g_avc_on, g_avc_av_on, g_avc_n[3], g_avc_saved[3];   /* task bventry: BVCOST boulevard / avenue switch,
                                                                            steps scaled, cost taken off */
static LONG g_avc_num[3] = {1, 1, 1}, g_avc_den[3] = {1, 2, 2};
static volatile LONG g_avs_on, g_avs_n_start, g_avs_n_offer, g_avs_n_closed, g_avs_n_big;   /* task bventry: AVSTART */
typedef DWORD (__fastcall *AVS_KIND)(BYTE *layer, void *edx, void *occ, BYTE *kind);   /* __thiscall on the layer:
                                                                   0x100057f6 is mov edi, ecx ... ret 8 */
typedef struct { BYTE *a[AVS_MAX]; BYTE b[AVS_MAX]; } AvsBuf;      /* per thread, heap: not on ld_select's stack */
static DWORD g_avs_tls = TLS_OUT_OF_INDEXES;
static AvsBuf *avs_buf(void) {
    AvsBuf *p;
    if (g_avs_tls == TLS_OUT_OF_INDEXES) return NULL;
    p = (AvsBuf *)TlsGetValue(g_avs_tls);
    if (!p) { p = (AvsBuf *)HeapAlloc(GetProcessHeap(), 0, sizeof(AvsBuf)); TlsSetValue(g_avs_tls, p); }
    return p;
}

typedef void (__fastcall *AVD_DEP)(BYTE *layer, void *edx, int x, int z, DWORD amount, DWORD mask);

static int avf_env(const char *name, int def) {
    char v[8];
    DWORD got = GetEnvironmentVariableA(name, v, sizeof(v));
    if (!got) return def;
    return v[0] != '0';
}

static void avf_frac(const char *name, int k) {
    char v[32];
    long n, d;
    if (!GetEnvironmentVariableA(name, v, sizeof(v))) return;
    if (sscanf(v, "%ld/%ld", &n, &d) == 2 && n >= 0 && d > 0 && n <= d && d <= 1000) { g_avd_num[k] = n; g_avd_den[k] = d; }
    else logf("### avflow: %s='%s' not n/d with 0 <= n <= d <= 1000 - default kept", name, v);
}

static void avc_frac(const char *name, int k) {                    /* task bventry: BVCOST scale, 0 < n <= d */
    char v[32];
    long n, d;
    if (!GetEnvironmentVariableA(name, v, sizeof(v))) return;
    if (sscanf(v, "%ld/%ld", &n, &d) == 2 && n > 0 && d > 0 && n <= d && d <= 1000) { g_avc_num[k] = n; g_avc_den[k] = d; }
    else logf("### avflow: %s='%s' not n/d with 0 < n <= d <= 1000 - default kept", name, v);
}

static void avf_init(void) {
    g_avf_on = avf_env("SC3NETMOD_AVFIRST", AVF_DEFAULT_FIRST);
    g_avd_on = avf_env("SC3NETMOD_AVDEPOSIT", AVF_DEFAULT_DEPOSIT);
    g_avf_bv = avf_env("SC3NETMOD_AVF_BVFIRST", AVF_DEFAULT_BVFIRST);
    avf_frac("SC3NETMOD_AVDEP_AV", 1);
    avf_frac("SC3NETMOD_AVDEP_BV", 2);
    g_avc_on = avf_env("SC3NETMOD_BVCOST", AVF_DEFAULT_BVCOST);       /* task bventry */
    g_avc_av_on = avf_env("SC3NETMOD_AVCOST", AVF_DEFAULT_AVCOST);
    {
        char v[8];
        g_avs_on = AVF_DEFAULT_AVSTART;
        if (GetEnvironmentVariableA("SC3NETMOD_AVSTART", v, sizeof(v))) g_avs_on = v[0] == '2' ? 2 : v[0] != '0';
    }
    g_avs_tls = TlsAlloc();
    logf("avflow: avstart %s", g_avs_on == 2 ? "on (boulevard cells only)" : g_avs_on ? "on (avenue and boulevard cells)" : "off");
    avc_frac("SC3NETMOD_AVCOST_AV", 1);
    avc_frac("SC3NETMOD_AVCOST_BV", 2);
    logf("avflow: bvcost %s (step cost on boulevard cells x %ld/%ld), avcost %s (avenue cells x %ld/%ld)", g_avc_on ? "on" : "off",
         g_avc_num[2], g_avc_den[2], g_avc_av_on ? "on" : "off", g_avc_num[1], g_avc_den[1]);
    logf("avflow: avfirst %s (bvfirst %s), avdeposit %s (avenue %ld/%ld, boulevard %ld/%ld of the adder)", g_avf_on ? "on" : "off",
         g_avf_bv ? "on" : "off", g_avd_on ? "on" : "off", g_avd_num[1], g_avd_den[1], g_avd_num[2], g_avd_den[2]);
}

/* ---------------------------------------------------------------- the class grid (game thread, after RBT's passes) */
static BYTE g_avf_idc[65536];                    /* per piece id: 0 = not computed, else 1 + class (tables are fixed) */

static int avf_id_class(WORD id) {
    int c = 0;
    if (g_avf_idc[id]) return g_avf_idc[id] - 1;
    if ((g_bv_p[0] && bv_is_piece(id) && !bvx_is_piece(id)) || dbv_is_piece(id)) c = 2;
    else if (avx_is_box(id) || avx_is_corner(id)) c = 0;          /* junction boxes (some have base 11204) */
    else if (id == 11204 || id == 11203 || g_base[id] == 11204 || avl_own(id)) c = 1;
    else if (g_dav_on && dav_is_mid(id) && !dav_is_junc(id)) c = 1;
    else c = 3;                                                    /* not ours: avl_claimed decides per cell */
    g_avf_idc[id] = (BYTE)(c + 1);
    return c;
}

static int avf_class_of(WORD id, int x, int z) {
    int c;
    if (!id) return 0;
    c = avf_id_class(id);
    if (c == 3) return avl_claimed(x, z) ? 1 : 0;
    return c;
}

static void avf_classify(BYTE *mgr, int x0, int z0, int x1, int z1, int load) {
    void *lay = *(void **)(mgr + 0x3c);
    int W = (*(int *)(mgr + 0x5c) >> 8) + 1, H = (*(int *)(mgr + 0x60) >> 8) + 1, x, z;
    BYTE *g = g_avf_cls;
    if (W < 4 || H < 4 || W > 4096 || H > 4096) return;
    if (!g || g_avf_w != W || g_avf_h != H) {                     /* a new city size: new grids (the old ones are kept:
                                                                     a worker may still read them; once per size change) */
        BYTE *ng = (BYTE *)VirtualAlloc(NULL, (SIZE_T)W * H, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        LONG *nc = (LONG *)VirtualAlloc(NULL, (SIZE_T)W * H * sizeof(LONG), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        if (!ng || !nc) { logf("### avflow: no memory for the class grid"); return; }
        g_avf_cls = NULL; MemoryBarrier();
        g_avf_w = W; g_avf_h = H; g_avd_carry = nc; MemoryBarrier();
        g_avf_cls = g = ng;
        g_avf_ncls[1] = g_avf_ncls[2] = 0;
        x0 = 0; z0 = 0; x1 = W - 1; z1 = H - 1;
    } else if (load) {                                             /* a load: start from nothing */
        ZeroMemory(g, (SIZE_T)W * H);
        ZeroMemory(g_avd_carry, (SIZE_T)W * H * sizeof(LONG));
        g_avf_ncls[1] = g_avf_ncls[2] = 0;
    }
    if (x0 < 0) x0 = 0;
    if (z0 < 0) z0 = 0;
    if (x1 > W - 1) x1 = W - 1;
    if (z1 > H - 1) z1 = H - 1;
    for (z = z0; z <= z1; z++)
        for (x = x0; x <= x1; x++) {
            DWORD v = rb_read(mgr, lay, x, z, W, H);
            BYTE c = (BYTE)avf_class_of((WORD)(v & 0xffff), x, z), o = g[z * W + x];
            if (c == o) continue;
            g[z * W + x] = c;
            if (o) InterlockedDecrement(&g_avf_ncls[o]);
            if (c) InterlockedIncrement(&g_avf_ncls[c]);
        }
}

/* called by rb_pass (box + 3, "edit") and rb_load_pass (whole map, "load"), after every other road block */
static void avf_pass(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who) {
    LONG a0 = g_avf_ncls[1], b0 = g_avf_ncls[2];
    int load = !strcmp(who, "load");
    __try {
        avf_classify(mgr, x0, z0, x1, z1, load);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        InterlockedIncrement(&g_avf_n_fault);
        logf("### avflow: exception 0x%08lX in the class pass", GetExceptionCode());
    }
    if (load || g_avf_ncls[1] != a0 || g_avf_ncls[2] != b0)
        logf("avflow: %s class pass: avenue cells %ld, boulevard cells %ld (grid %ldx%ld)", who, g_avf_ncls[1],
             g_avf_ncls[2], g_avf_w, g_avf_h);
    if (!load && g_rb_hwnd) {                                      /* the sweep below, (re)started from row 0 */
        g_avf_sweep_mgr = mgr;
        if (InterlockedExchange(&g_avf_sweep_row, 0) < 0) PostMessageA(g_rb_hwnd, RB_WM + 1, 0, 0);
    }
}

/* SWEEP: blocks write outside the edit box (BV and DAV re-run over the whole map when a run reaches the read border,
   an AVL band is written to its far end), so after every edit pass the whole grid is re-read on the game thread,
   AVF_SWEEP_ROWS rows per window message (a 1024 map in 64 messages, no long stall). A new edit restarts it. */
#define AVF_SWEEP_ROWS 16
static void avf_sweep_step(void) {
    LONG a0 = g_avf_ncls[1], b0 = g_avf_ncls[2], r = g_avf_sweep_row;
    BYTE *mgr = g_avf_sweep_mgr;
    if (r < 0 || !mgr) return;
    __try {
        avf_classify(mgr, 0, r, 0x7fffff, r + AVF_SWEEP_ROWS - 1, 0);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        InterlockedIncrement(&g_avf_n_fault);
        logf("### avflow: exception 0x%08lX in the sweep", GetExceptionCode());
        InterlockedExchange(&g_avf_sweep_row, -1);
        return;
    }
    if (g_avf_ncls[1] != a0 || g_avf_ncls[2] != b0)
        logf("avflow: sweep rows %ld..%ld: avenue cells %ld, boulevard cells %ld", r, r + AVF_SWEEP_ROWS - 1,
             g_avf_ncls[1], g_avf_ncls[2]);
    if (InterlockedCompareExchange(&g_avf_sweep_row, r + AVF_SWEEP_ROWS, r) != r) {   /* restarted meanwhile */
        PostMessageA(g_rb_hwnd, RB_WM + 1, 0, 0);
        return;
    }
    if (r + AVF_SWEEP_ROWS >= g_avf_h) InterlockedCompareExchange(&g_avf_sweep_row, -1, r + AVF_SWEEP_ROWS);
    if (g_avf_sweep_row >= 0) PostMessageA(g_rb_hwnd, RB_WM + 1, 0, 0);
}

static int avf_class(DWORD x, DWORD z) {
    BYTE *g = g_avf_cls;
    if (!g || x >= (DWORD)g_avf_w || z >= (DWORD)g_avf_h) return 0;
    return g[z * g_avf_w + x];
}

/* ---------------------------------------------------------------- AVFIRST (inside ld_select, after rf_close) */
static void avf_close(BYTE *layer, BYTE *node, BYTE **added, BYTE *addb, int *nadd) {
    BYTE t = node[0x14], lvl;
    DWORD x, z, w, h, cx[5], cz[5];
    int k, av = 0, bv = 0, close_below, kind[5];
    if (!g_avf_on || !g_avf_cls || (t != 1 && t != 0x41)) return;
    x = *(DWORD *)(node + 4); z = *(DWORD *)(node + 8);
    if (x != *(DWORD *)(node + 0xc) || z != *(DWORD *)(node + 0x10)) return;
    w = *(DWORD *)(layer + 0x14); h = *(DWORD *)(layer + 0x18);
    lvl = *(BYTE *)(g_avf_st + 0x1f0c0);                           /* TrafficAnnoyanceLevel, read live */
    for (k = 0; k < 5; k++) {
        WORD f;
        kind[k] = 0;
        cx[k] = x + g_rf_dx[k]; cz[k] = z + g_rf_dz[k];
        if (cx[k] >= w || cz[k] >= h) continue;                     /* unsigned: also catches -1 */
        f = ld_flags(layer, cx[k], cz[k]);
        if ((f & 0x11) != 0x01) continue;                            /* road cell, not a station */
        if ((*ld_mark(layer, cx[k], cz[k]) & t) == t) continue;      /* visited by this node type (or closed above) */
        kind[k] = 1;
        if (*(*(BYTE **)(*(BYTE **)(*(BYTE **)(layer + 0x6c) + 0xc) + cx[k] * 4) + cz[k]) < lvl)
            switch (avf_class(cx[k], cz[k])) {
            case 1: kind[k] = 2; av = 1; break;
            case 2: kind[k] = 3; av = 1; bv = 1; break;
            }
    }
    if (!av) return;
    InterlockedIncrement(&g_avf_n_offer);
    close_below = 2;                                               /* close plain road candidates (kind 1) */
    if (bv && g_avf_bv) { close_below = 3; InterlockedIncrement(&g_avf_n_bvoffer); }   /* BVFIRST: avenue cells too */
    for (k = 0; k < 5; k++)
        if (kind[k] && kind[k] < close_below) {
            int before = *nadd;
            ld_close(layer, cx[k], cz[k], t, added, addb, nadd);
            if (*nadd > before) InterlockedIncrement(kind[k] == 2 ? &g_avf_n_bvclosed : &g_avf_n_closed);
        }
}

/* ---------------------------------------------------------------- BVCOST (task bventry: ld_select, after the step) */
static void avc_adjust(BYTE *node, BYTE *out, BYTE r) {
    DWORD x, z, base, oc, step, ns;
    BYTE t;
    int c;
    if ((!g_avc_on && !g_avc_av_on) || !r || !g_avf_cls) return;
    t = out[0x14];
    if (t != 1 && t != 0x41) return;
    x = *(DWORD *)(out + 4); z = *(DWORD *)(out + 8);
    if (x != *(DWORD *)(out + 0xc) || z != *(DWORD *)(out + 0x10)) return;
    c = avf_class(x, z);
    if (!c || (c == 2 ? !g_avc_on : !g_avc_av_on) || g_avc_num[c] == g_avc_den[c]) return;
    base = *(DWORD *)(node + 0x18); oc = *(DWORD *)(out + 0x18);
    if (oc <= base) return;
    step = oc - base;
    ns = (step * (DWORD)g_avc_num[c] + (DWORD)g_avc_den[c] - 1) / (DWORD)g_avc_den[c];
    if (!ns) ns = 1;
    if (ns >= step) return;
    *(DWORD *)(out + 0x18) = base + ns;
    InterlockedIncrement(&g_avc_n[c]);
    InterlockedExchangeAdd(&g_avc_saved[c], (LONG)(step - ns));
}

/* ---------------------------------------------------------------- AVSTART (task bventry: ld_select, start nodes) */
static void avs_close(BYTE *layer, BYTE *node, BYTE **added, BYTE *addb, int *nadd) {
    BYTE t = node[0x14], lvl, k = 0xee;
    void *occ = *(void **)node;
    int mode = (int)g_avs_on, r, bx0, bz0, bx1, bz1, x0, z0, x1, z1, x, z, found = 0, n0 = *nadd;
    if (!mode || !g_avf_cls || !g_avf_st || t != 0x80) return;
    if (!occ) r = layer[0xc8];
    else {
        if (!(((AVS_KIND)(g_avf_st + 0x57f6))(layer, NULL, occ, &k) & 0xff)) return;   /* the game's own kind call; failed: stock */
        r = k == 0 ? layer[0xc5] : k == 1 ? layer[0xc6] : k == 2 ? layer[0xc7] : layer[0xc8];
    }
    InterlockedIncrement(&g_avs_n_start);
    lvl = *(BYTE *)(g_avf_st + 0x1f0c0);
    bx0 = *(int *)(node + 4) - r; bz0 = *(int *)(node + 8) - r; bx1 = *(int *)(node + 0xc) + r; bz1 = *(int *)(node + 0x10) + r;
    x0 = bx0 < 0 ? 0 : bx0; z0 = bz0 < 0 ? 0 : bz0;
    x1 = bx1 > *(int *)(layer + 0x14) - 1 ? *(int *)(layer + 0x14) - 1 : bx1;
    z1 = bz1 > *(int *)(layer + 0x18) - 1 ? *(int *)(layer + 0x18) - 1 : bz1;
    for (x = x0; x <= x1 && !found; x++)
        for (z = z0; z <= z1; z++) {
            int c;
            if ((x == bx0 || x == bx1) && (z == bz0 || z == bz1)) continue;          /* the scan skips the corners */
            c = avf_class((DWORD)x, (DWORD)z);
            if (!c || (mode == 2 && c != 2)) continue;
            if ((ld_flags(layer, x, z) & 0x11) != 0x01) continue;
            if ((*ld_mark(layer, x, z) & t) == t) continue;
            if (*(*(BYTE **)(*(BYTE **)(*(BYTE **)(layer + 0x6c) + 0xc) + x * 4) + z) >= lvl) continue;
            found = 1;
            break;
        }
    if (!found) return;
    InterlockedIncrement(&g_avs_n_offer);
    for (x = x0; x <= x1; x++)
        for (z = z0; z <= z1; z++) {
            int c = avf_class((DWORD)x, (DWORD)z);
            if (c && (mode != 2 || c == 2)) continue;
            if (*nadd >= AVS_MAX) {                                  /* too many: undo, stock */
                int k2;
                for (k2 = n0; k2 < *nadd; k2++) *added[k2] &= (BYTE)~addb[k2];
                *nadd = n0;
                InterlockedIncrement(&g_avs_n_big);
                return;
            }
            ld_close(layer, (DWORD)x, (DWORD)z, t, added, addb, nadd);
        }
    InterlockedExchangeAdd(&g_avs_n_closed, *nadd - n0);
}

/* ---------------------------------------------------------------- AVDEPOSIT (call site SimTransit 0x10007463) */
static void __fastcall avd_dep(BYTE *layer, void *edx, int x, int z, DWORD amount, DWORD mask) {
    int a = (signed char)(amount & 0xff), c;
    (void)edx;
    if (g_avd_on && a > 0 && (c = avf_class((DWORD)x, (DWORD)z)) != 0) {
        LONG *cell = g_avd_carry, num = g_avd_num[c], den = g_avd_den[c], o, n, out;
        if (cell) {
            cell += (DWORD)z * g_avf_w + (DWORD)x;
            for (;;) {
                o = *cell;
                n = o + a * num;
                out = n / den;
                if (InterlockedCompareExchange(cell, n - out * den, o) == o) break;
            }
            InterlockedIncrement(&g_avd_n_dep[c]);
            InterlockedExchangeAdd(&g_avd_n_in[c], a);
            InterlockedExchangeAdd(&g_avd_n_out[c], out);
            if (!out) return;
            amount = (amount & ~0xffu) | (DWORD)(out & 0xff);
        }
    }
    ((AVD_DEP)g_avd_orig)(layer, NULL, x, z, amount, mask);
}

static void avd_install(BYTE *st) {
    g_avf_st = (DWORD)st;
    g_avd_orig = retarget_call(st, 0x7463, 0x6edd, (void *)avd_dep);
    if (!g_avd_orig) { logf("### avflow: SimTransit+0x7463 is not call 0x10006edd - AVDEPOSIT not installed"); g_avd_on = 0; return; }
    logf("avflow: AVDEPOSIT installed at SimTransit+0x7463 (road deposit of the final path)");
}

/* ---------------------------------------------------------------- live switches + stats */
__declspec(dllexport) int __cdecl sc3netmod_avf_set(int on) {
    LONG prev;
    if (!g_ld_st || !g_ld_mode) return -1;
    prev = InterlockedExchange(&g_avf_on, on ? 1 : 0);
    logf("avflow: avfirst live switch %s (was %s)", on ? "ON" : "OFF", prev ? "on" : "off");
    return (int)prev;
}

__declspec(dllexport) int __cdecl sc3netmod_avf_bv_set(int on) {
    LONG prev;
    if (!g_ld_st || !g_ld_mode) return -1;
    prev = InterlockedExchange(&g_avf_bv, on ? 1 : 0);
    logf("avflow: bvfirst live switch %s (was %s)", on ? "ON" : "OFF", prev ? "on" : "off");
    return (int)prev;
}

__declspec(dllexport) int __cdecl sc3netmod_avc_set(int on) {      /* task bventry */
    LONG prev;
    if (!g_ld_st || !g_ld_mode) return -1;
    prev = InterlockedExchange(&g_avc_on, on ? 1 : 0);
    logf("avflow: bvcost live switch %s (was %s)", on ? "ON" : "OFF", prev ? "on" : "off");
    return (int)prev;
}

__declspec(dllexport) int __cdecl sc3netmod_avc_av_set(int on) {   /* task bventry: avenue half */
    LONG prev;
    if (!g_ld_st || !g_ld_mode) return -1;
    prev = InterlockedExchange(&g_avc_av_on, on ? 1 : 0);
    logf("avflow: avcost live switch %s (was %s)", on ? "ON" : "OFF", prev ? "on" : "off");
    return (int)prev;
}

__declspec(dllexport) int __cdecl sc3netmod_avs_set(int on) {      /* task bventry: AVSTART, 0 off, 1 on, 2 boulevard only */
    LONG prev;
    if (!g_ld_st || !g_ld_mode) return -1;
    prev = InterlockedExchange(&g_avs_on, on == 2 ? 2 : on ? 1 : 0);
    logf("avflow: avstart live switch %d (was %ld)", on, prev);
    return (int)prev;
}

__declspec(dllexport) int __cdecl sc3netmod_avd_set(int on) {
    LONG prev;
    if (!g_avd_orig) return -1;
    prev = InterlockedExchange(&g_avd_on, on ? 1 : 0);
    logf("avflow: avdeposit live switch %s (was %s)", on ? "ON" : "OFF", prev ? "on" : "off");
    return (int)prev;
}

__declspec(dllexport) int __cdecl sc3netmod_avflow_set(int on) {
    int a = sc3netmod_avf_set(on), b = sc3netmod_avd_set(on);
    if (a < 0 || b < 0) return -1;
    return a && b;
}

__declspec(dllexport) BYTE *__cdecl sc3netmod_avf_grid(int *w, int *h) {
    if (w) *w = g_avf_w;
    if (h) *h = g_avf_h;
    return g_avf_cls;
}

static void avflow_stats(void) {
    logf("avflow: avfirst %s, avenue offers=%ld, other road candidates closed=%ld, bvfirst %s offers=%ld avenue cells closed=%ld | avdeposit %s, avenue deposits=%ld in=%ld out=%ld, boulevard deposits=%ld in=%ld out=%ld | cells avenue=%ld boulevard=%ld",
         g_avf_on ? "on" : "off", g_avf_n_offer, g_avf_n_closed, g_avf_bv ? "on" : "off", g_avf_n_bvoffer, g_avf_n_bvclosed, g_avd_on ? "on" : "off", g_avd_n_dep[1], g_avd_n_in[1],
         g_avd_n_out[1], g_avd_n_dep[2], g_avd_n_in[2], g_avd_n_out[2], g_avf_ncls[1], g_avf_ncls[2]);
    logf("avflow: bvcost %s, boulevard steps scaled=%ld cost off=%ld | avcost %s, avenue steps scaled=%ld cost off=%ld",
         g_avc_on ? "on" : "off", g_avc_n[2], g_avc_saved[2], g_avc_av_on ? "on" : "off", g_avc_n[1], g_avc_saved[1]);
    logf("avflow: avstart %ld, starts=%ld with an open avenue/boulevard cell=%ld, cells closed=%ld, too big=%ld", g_avs_on,
         g_avs_n_start, g_avs_n_offer, g_avs_n_closed, g_avs_n_big);   /* task bventry */
}
