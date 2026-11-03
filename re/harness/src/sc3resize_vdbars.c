/* ======================================================================================================== VDBARS
 * (child graphs2 2026-11-02, owner: "the Cuadros radio buttons become tabs too / Education tab: horizontal bar chart of
 * capacity vs current students, schools and universities separately; what exists for libraries and museums / Health
 * tab: patients vs hospital capacity, same style / water sources and water processing in one tab / transportation
 * methods used"). #included by sc3resize.c after sc3resize_graphs.c. Evidence and the full value list:
 * re/analysis/GRAPH_SERIES.md section 9.
 *
 * CUADROS TABS (with VDTABS). The Cuadros page director (vtable SIMUI 0x100a4080) builds the page in FUN_1001f3df:
 * bar chart child 2 (FUN_10020615, (14, 10) 356 x 189), panel child 4 (FUN_1002095a, same rect), pie chart child 3,
 * text labels 0xb (10, 200) / 0xc (10, 216), legend labels 0xd..0x1c, radio group child 5 (FUN_10020a4c, (150, 260)..
 * (270, 410), radios 6 Educacion, 7 Electricidad, 8 Basura, 9 Salud, 10 Poblacion). The fill FUN_100245c7(director,
 * page) draws the chart of the group's selection; the control handler FUN_1001f30d (this = director + 4, ret 0x14) runs
 * it on a radio pick (message 3, p3 3) and the refresh handler FUN_1001f3b3 (this = director + 0xc, message
 * 0xC2A3FD82) on a data refresh; the close FUN_10020ffd keeps the selection in the game prefs [CONFIRMED @ SIMUI
 * 0x1001f3df, 0x100245c7, 0x1001f30d, 0x1001f3b3, 0x10020ffd]. Here: the four vtable slots (build +0xc at 0x100a408c,
 * close +0x10 at 0x100a4090, control +0xc at 0x100a4014, refresh +0xc at 0x100a3ff4) are patched, not the code, so
 * sc3dataview's prologue detour on 0x100245c7 keeps working (we call the fill by its address, through that detour).
 * After the build: the radio group is parked (hidden, moved to y 4000, still read by the fill), labels 0xb / 0xc move
 * 22 px down, and a VDTABS strip hangs under panel 4: Educacion, Salud, Poblacion, Electricidad, Basura (the 5 stock
 * charts, a click selects the stock radio and runs the fill), Agua, Transporte (ours: the stock chart children 2, 3 and
 * labels 0xb..0x1c hide, our bars draw on panel 4). The tab is kept in sc3resize.ini [cuadros] tab.
 *
 * BARS (VDBARS). Labels + filled rects of the page, built on every fill / refresh:
 *  - Educacion (under the stock chart, in place of sc3dataview's text column, which is hidden while ours shows):
 *    residential layer city+0xe4 (vtable SIMRCI 0x1004c99c), written by the residential pass FUN_10024347:
 *    school pupils +0x66c vs places +0x670, college +0x674 / +0x678, library places +0x67c, museum places +0x680,
 *    teachers +0x684, professors +0x688, strike bytes +0x650 / +0x651 [CONFIRMED @ SIMRCI 0x10024347: 0x10024b46,
 *    0x10024614, 0x10024b74, 0x10024637, 0x1002464c, 0x10024661, 0x10024606, 0x10024629]. Pupils / students are every
 *    resident of the age band (6..18, 19..24), not an enrolment: no min(demand, places) anywhere. Places = one constant
 *    per building (SC3Tune.INI OptimalDeskCount 3000 school, 7500 college, PopServed 41000 library, 83000 museum, globals
 *    SIMRCI 0x10057474 / 0x100572f4 / 0x1005741c / 0x1005745c), so buildings = places / constant, exact. Libraries and
 *    museums keep NO user count: their seats go into the per-age EQ arrays mixed with schools. What the sim compares
 *    their seats with is the residents of each age they serve (seats * eff / max(seats, residents at age)); the bar
 *    shows that population: res vt+0x78 (population) x res vt+0x80(lo, hi) (age cohort share, SIMRCI 0x100251b5), band
 *    from the INI bytes SIMRCI 0x10057420 / 0x10057421 (library), 0x10057460 / 0x10057461 (museum), clamped to 89 like
 *    the pass does.
 *  - Salud: patients +0x664 vs hospital capacity (beds) +0x668, doctors +0x68c, strike +0x652 [CONFIRMED @ SIMRCI
 *    0x10024833, 0x1002485d, 0x10024572]. Patients = population x pollution-based rate, not tied to beds.
 *  - Agua: plumbing layer P = city vt+0x154 (vtable SIMUTIL 0x10022944), monthly FUN_1000e8c4: supply int64 +0xb0,
 *    delivered int64 +0xb8, consumer buildings left dry +0xc4 (and +0xc0 = consumer count while some are dry, else 100)
 *    [CONFIRMED @ SIMUTIL 0x1000e8c4]. Per source: the facility list *(*(P+0x74)) (MSVC list, node +0x08 data: +0x18
 *    base capacity u16, +0x1a output this month u16, +0x20 type u16: 2 tower, 3 pump, 5 desalination) [CONFIRMED @
 *    SIMUTIL 0x1000e0b5, 0x1000f771], walked under the layer's lock *(P+0x14) vt+4 / vt+8. Treatment: SIMECO po = city
 *    vt+0x16c: water pollution produced last month po+0xe8, treated po+0xec (rollover 0x10007a9e copies them from the
 *    month sums the block pass 0x10008249 adds up), plants = the list po+0x98 (item = iface 0x4337354e of a building
 *    0x3214 WaterTreatment, item vt+0x34 = its capacity per period, x 30 = the month budget the pass spends), aging
 *    plants po+0xb8, all under the lock *(po+0x74); average water pollution po vt+0x7c of vt+0x88 [CONFIRMED @ SIMECO
 *    0x1000a032, 0x10008249, 0x10007a9e; SIMUTIL 0x10002563, 0x100015ac]. Not stored anywhere: unmet water demand,
 *    water held by towers, sewage volume.
 *  - Transporte: share of arrived trips that used each network. The game counts no trip per mode (only route calls
 *    T+0xb0, failures T+0xb4, last month's failure ratio float T+0xb8, T = SimTransit 0x1001fdb8 [CONFIRMED @
 *    SimTransit 0x100070d0, 0x100093e9]), so TRIPMODES counts them: route_trip pops its path destination first, one
 *    32-byte node per pop, the origin lot (type 0x80) last; the pop `call 0x10009eed` at SimTransit 0x100072f8 becomes a
 *    call to tm_stub (sc3cartrips' recipe, 14-byte signature at 0x100072f3, one locked 8-byte write), which ORs the
 *    node's network into a per-thread mask and, on the origin pop of a trip whose deposit flag [ebp+0x14] is set (the
 *    flag the game uses for congestion and fares, so growth probes are left out), adds the trip to each network it used
 *    [CONFIRMED @ SimTransit 0x100072b6..0x10007554]. Node types: road 1, 3 (ramp road); highway 2; bus 0x41, 0x42,
 *    0x43, 0x50; rail 4, 0x14; subway 8, 0x18. Counted on every routing thread (sc3perf traffic_mt workers too), kept
 *    per month: the budget's monthly record (GRAPHNEW gn_month) closes a month. sc3cartrips (a dev tool, not shipped)
 *    patches the same call: whichever comes second refuses and logs it.
 * SC3RESIZE_VDBARS=0: no bars (Agua / Transporte tabs show nothing, sc3dataview's text stays). SC3RESIZE_TRIPMODES=0:
 * no SimTransit patch (and no TRIPCELLS). SC3RESIZE_TRIPCELLS=0: no per-cell counts (sc3dataview's transit map stays empty).
 * SC3RESIZE_VDTABS=0: Cuadros keeps its stock radios and gets no bars (they would sit on the radios). */
static int g_vdbars = 1, g_tripmodes = 1;

/* ---------------------------------------------------------------------------------------------- bar primitives */
#define VB_LBL0 0x7A3C0500u     /* + 0 .. 0xff */
#define VB_SHP0 0x7A3C0600u     /* + 0 .. 0xff */
typedef struct { void *fac, *win; int nl, ns; } VB;
static int g_vb_nl, g_vb_ns;    /* used by the last draw on g_cq.win */
static WORD g_vb_ink, g_vb_sub, g_vb_track, g_vb_a, g_vb_b, g_vb_warn, g_vb_ok;
static int g_vb_redbars = 1;   /* SC3RESIZE_VDREDBARS=0: the old blue demand bars (red only on the % text) */

static void vb_colours(void) {
    static int done;
    if (done) return;
    done = 1;
    g_vb_ink = gx_col16(0x202870); g_vb_sub = gx_col16(0x505890); g_vb_track = gx_col16(0xC8D0F0);
    g_vb_a = gx_col16(0x2060D0); g_vb_b = gx_col16(0x8890A8); g_vb_warn = gx_col16(0xC02020); g_vb_ok = gx_col16(0x20A040);
}
static void vb_text(VB *b, const char *t, WORD col, int x, int y, int w, int h, int align) {
    if (b->nl < 0x100) vt_label(b->fac, b->win, VB_LBL0 + b->nl++, t, col, x, y, w, h, align);
}
static void vb_box(VB *b, WORD col, int x, int y, int w, int h) {
    if (b->ns < 0x100 && w > 0 && h > 0) vt_rect(b->win, VB_SHP0 + b->ns++, col, x, y, w, h);
}
static void vb_box2(VB *b, WORD fill, WORD line, int x, int y, int w, int h) {
    LONG p[8];
    p[0] = 0; p[1] = 0; p[2] = 0; p[3] = h - 1; p[4] = w - 1; p[5] = h - 1; p[6] = w - 1; p[7] = 0;
    if (b->ns < 0x100 && w > 0 && h > 0) vt_poly2(b->win, VB_SHP0 + b->ns++, fill, line, x, y, w, h, p, 4);
}
static void vb_bar(VB *b, int x, int y, int w, int h, double frac, WORD col) {
    int f;
    if (frac < 0) frac = 0;
    if (frac > 1) frac = 1;
    f = (int)(w * frac + 0.5);
    if (frac > 0 && f < 1) f = 1;
    vb_box(b, g_vb_track, x, y, w, h);
    vb_box(b, col, x, y, f, h);
}
/* hide what the previous draw used beyond this one */
static void vb_end(VB *b) {
    int i;
    for (i = b->nl; i < g_vb_nl; i++) gx_show(mp_child(b->win, VB_LBL0 + i), 0);
    for (i = b->ns; i < g_vb_ns; i++) gx_show(mp_child(b->win, VB_SHP0 + i), 0);
    g_vb_nl = b->nl; g_vb_ns = b->ns;
}

static int vb_es(void) { static int es = -1; if (es < 0) es = ho_spanish(); return es; }

/* decimal separator of the mods' language (a one-character table value) */
static char vb_dec(void) { return SC3TR(vb_es(), "cuadros.decimal_sep", ",", ".")[0]; }

/* 9.500 / 44,5K / 1,2M (Spanish), 9,500 / 44.5K / 1.2M (English) */
static void vb_num(char *o, double v) {
    char dc = vb_dec(), th = SC3TR(vb_es(), "cuadros.thousands_sep", ".", ",")[0];   /* modlang: per language */
    long n;
    if (v < 0) v = 0;
    n = (long)(v + 0.5);
    if (n < 10000) { if (n >= 1000) wsprintfA(o, "%ld%c%03ld", n / 1000, th, n % 1000); else wsprintfA(o, "%ld", n); }
    else if (n < 1000000) { long d = (n + 50) / 100; if (d % 10) wsprintfA(o, "%ld%c%ldK", d / 10, dc, d % 10); else wsprintfA(o, "%ldK", d / 10); }
    else { long d = (long)((v + 50000.0) / 100000.0); if (d % 10) wsprintfA(o, "%ld%c%ldM", d / 10, dc, d % 10); else wsprintfA(o, "%ldM", d / 10); }
}

/* a 26 px row: name (+ pct) / sub line on the left, bar a over bar b (shared scale), the two values on the right.
   dem = which value is the DEMAND measured against the other as capacity: 0 none (plain blue), 1 = a, 2 = b. The demand bar
   and its number are red when demand exceeds capacity (need), green when covered (VDREDBARS). */
static void vb_pair(VB *b, int x0, int x1, int y, const char *name, const char *sub, double a, double c, int pct, int dem) {
    char t[64], va[24], vc[24];
    double mx = a > c ? a : c;
    int bx = x0 + 140, bw = x1 - 58 - bx;
    int rd = g_vb_redbars && dem;
    int short_ = rd && (dem == 1 ? a > c : c > a);
    WORD ca = g_vb_a, cb = g_vb_b;
    if (rd) { WORD d = short_ ? g_vb_warn : g_vb_ok; if (dem == 1) ca = d; else cb = d; }
    if (pct && c > 0) wsprintfA(t, "%s  %ld%%", name, (long)(a * 100.0 / c + 0.5)); else lstrcpynA(t, name, sizeof(t));
    vb_text(b, t, (pct && c > 0 && a > c) || (short_ && !pct) ? g_vb_warn : g_vb_ink, x0, y, 138, 13, 1);
    vb_text(b, sub, g_vb_sub, x0, y + 12, 138, 13, 1);
    vb_bar(b, bx, y + 2, bw, 8, mx > 0 ? a / mx : 0, ca);
    vb_bar(b, bx, y + 14, bw, 8, mx > 0 ? c / mx : 0, cb);
    vb_num(va, a); vb_num(vc, c);
    vb_text(b, va, ca, x1 - 56, y, 56, 13, 7);
    vb_text(b, vc, cb, x1 - 56, y + 12, 56, 13, 7);
}
static void vb_legend(VB *b, int x0, int x1, int y) {
    if (!g_vb_redbars) return;
    vb_text(b, SC3TR(vb_es(), "cuadros.red_capacity_short_green", "rojo = falta capacidad, verde = cubierto", "red = capacity short, green = covered"), g_vb_sub, x0, y, x1 - x0, 14, 1);
}
/* a 16 px row: name, one bar of frac, a value text */
static void vb_one(VB *b, int x0, int x1, int y, const char *name, double frac, const char *val) {
    int bx = x0 + 104, bw = x1 - 62 - bx;
    vb_text(b, name, g_vb_ink, x0, y, 102, 14, 1);
    vb_bar(b, bx, y + 3, bw, 9, frac, g_vb_a);
    vb_text(b, val, g_vb_a, x1 - 58, y, 58, 14, 7);
}
static void vb_pct(char *o, double num, double den) {
    long p10 = den > 0 ? (long)(num * 1000.0 / den + 0.5) : 0;
    wsprintfA(o, "%ld%c%ld%%", p10 / 10, vb_dec(), p10 % 10);
}

/* ---------------------------------------------------------------------------------------------- TRIPMODES */
#define TM_N 8   /* [0] trips counted, [1] road, [2] highway, [3] bus, [4] rail, [5] subway, [6] any of bus/rail/subway, [7] no network */
static volatile LONG g_tm[TM_N];
static LONG  g_tm_last[TM_N], g_tm_lastkey = -1;
static DWORD g_tm_tls = TLS_OUT_OF_INDEXES;
static DWORD g_tm_target;
static int   g_tm_on;

/* TRIPCELLS (child transitmap 2026-11-02, SC3RESIZE_TRIPCELLS=0 off): the same counted trips per ORIGIN cell, for
 * sc3dataview's "Mapa de transporte publico". The game keeps no trip mode anywhere; the origin is the last node
 * route_trip pops (type 0x80, cell rect +4 x0, +8 z0, +0xc x1, +0x10 z1, measured 1 x 1 on Berlin) [CONFIRMED @
 * SimTransit 0x100072b6..0x10007554, sc3cartrips]. Three grids, u32 per cell, stride TC_S, low 16 bits = trips that
 * used a network, high 16 = those that used bus, rail or subway:
 *   cur   this month, raw counts, one locked add per origin cell (routing threads);
 *   hist  the months before, x16 fixed point, each closed month added and the older ones faded by 1/8 (about the last
 *         8 months: Berlin counts about 1,250 trips a month, so one month alone is a sparse dot field);
 *   disp  what the map draws: hist + cur x16 summed over the 5 x 5 cells around each cell (a neighbourhood's share,
 *         not single dots), rebuilt at month close and when the map is switched in (sc3resize_tripcells_build).
 * Trips that used no network (lot next to lot) and failed trips (never popped) are not in it. 3 x 4 MB reserved, the
 * OS commits a page per x row as it is written. */
#define TC_S 1024
#define TC_R 2
static int g_tripcells = 1;
static DWORD *g_tc_cur, *g_tc_hist, *g_tc_disp;
static volatile LONG g_tc_maxx = -1, g_tc_maxz = -1, g_tc_seen, g_tc_busy;
static LONG  g_tc_months, g_tc_dx = -1, g_tc_dz = -1;
static void tc_cell_add(const BYTE *node, DWORD add) {
    DWORD *g = g_tc_cur;
    int x0 = *(const int *)(node + 4), z0 = *(const int *)(node + 8), x1 = *(const int *)(node + 0xc), z1 = *(const int *)(node + 0x10), x, z, t;
    if (!g) return;
    if (x1 < x0) { t = x0; x0 = x1; x1 = t; }
    if (z1 < z0) { t = z0; z0 = z1; z1 = t; }
    if (x0 < 0 || z0 < 0 || x1 >= TC_S || z1 >= TC_S || x1 - x0 > 7 || z1 - z0 > 7) return;
    if (InterlockedIncrement(&g_tc_seen) <= 6)
        logf("TRIPCELLS> origin rect [%d %d %d %d] %s", x0, z0, x1, z1, (add >> 16) ? "transit" : "no transit");
    for (x = x0; x <= x1; x++) for (z = z0; z <= z1; z++) InterlockedExchangeAdd((volatile LONG *)&g[x * TC_S + z], (LONG)add);
    if (x1 > g_tc_maxx) InterlockedExchange(&g_tc_maxx, x1);
    if (z1 > g_tc_maxz) InterlockedExchange(&g_tc_maxz, z1);
}
static void tc_alloc(void) {
    char v[8];
    if (GetEnvironmentVariableA("SC3RESIZE_TRIPCELLS", v, sizeof(v))) g_tripcells = atoi(v);
    if (!g_tripcells || g_tc_cur) return;
    g_tc_hist = (DWORD *)VirtualAlloc(NULL, TC_S * TC_S * 4, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    g_tc_disp = g_tc_hist ? (DWORD *)VirtualAlloc(NULL, TC_S * TC_S * 4, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE) : NULL;
    g_tc_cur = g_tc_disp ? (DWORD *)VirtualAlloc(NULL, TC_S * TC_S * 4, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE) : NULL;
    logf("TRIPCELLS> %s", g_tc_cur ? "on: trips counted per origin cell" : "no memory: off");
}
static DWORD tc_sat(DWORD n, DWORD t) {   /* pack, scaled down so n fits 16 bits */
    if (t > n) t = n;
    if (n > 0xffff) { t = (DWORD)((unsigned __int64)t * 0xffff / n); n = 0xffff; }
    return n | (t << 16);
}
/* disp = 5 x 5 sums of (hist + cur x16). One builder at a time (month close on the sim thread, the map on the UI). */
static void tc_build(void) {
    LONG X, Z, x, z, i, j;
    if (!g_tc_cur || InterlockedExchange(&g_tc_busy, 1)) return;
    X = g_tc_maxx + 1 + TC_R; Z = g_tc_maxz + 1 + TC_R;
    if (X > TC_S) X = TC_S;
    if (Z > TC_S) Z = TC_S;
    if (g_tc_maxx >= 0) for (x = 0; x < X; x++) for (z = 0; z < Z; z++) {
        DWORD n = 0, t = 0;
        for (i = x - TC_R; i <= x + TC_R; i++) {
            if (i < 0 || i > g_tc_maxx) continue;
            for (j = z - TC_R; j <= z + TC_R; j++) {
                DWORD h, c;
                if (j < 0 || j >= TC_S) continue;
                h = g_tc_hist[i * TC_S + j]; c = g_tc_cur[i * TC_S + j];
                n += (h & 0xffff) + (c & 0xffff) * 16;
                t += (h >> 16) + (c >> 16) * 16;
            }
        }
        g_tc_disp[x * TC_S + z] = n ? tc_sat(n, t) : 0;
    }
    g_tc_dx = g_tc_maxx >= 0 ? X - 1 : -1; g_tc_dz = Z - 1;
    InterlockedExchange(&g_tc_busy, 0);
}
/* a month closed: fade hist by 1/8 and add the month (x16); fresh = another city: drop everything */
static void tc_month(int fresh) {
    LONG rows = g_tc_maxx + 1, x, z, Z = g_tc_maxz + 1;
    if (!g_tc_cur) return;
    if (fresh) {
        if (rows > 0) {
            memset(g_tc_hist, 0, (size_t)rows * TC_S * 4); memset(g_tc_cur, 0, (size_t)rows * TC_S * 4);
            memset(g_tc_disp, 0, (size_t)(rows + TC_R < TC_S ? rows + TC_R : TC_S) * TC_S * 4);
        }
        g_tc_months = 0;
        logf("TRIPCELLS> month key jumped (city loaded): per-cell history cleared");
        return;
    }
    for (x = 0; x < rows; x++) for (z = 0; z < Z; z++) {
        DWORD *cp = &g_tc_cur[x * TC_S + z], c = *cp, h = g_tc_hist[x * TC_S + z], n, t;
        if (c) c = (DWORD)InterlockedExchange((volatile LONG *)cp, 0);
        if (!c && !h) continue;
        n = (h & 0xffff); t = (h >> 16);
        n -= n >> 3; t -= t >> 3;
        n += (c & 0xffff) * 16; t += (c >> 16) * 16;
        if (n > 0xffff) n = 0xffff;
        if (t > n) t = n;
        g_tc_hist[x * TC_S + z] = n | (t << 16);
    }
    g_tc_months++;
    tc_build();
}

static void __cdecl tm_on_pop(BYTE *node, BYTE *fp) {
    DWORD e = GetLastError(), st = (DWORD)TlsGetValue(g_tm_tls);
    int ty = node[0x14], k;
    if (!(st & 0x80000000u)) st = 0x80000000u | (fp[0x14] ? 0x40000000u : 0);   /* deposit flag, read at the first pop */
    switch (ty) {
        case 1: case 3: st |= 1; break;
        case 2: st |= 2; break;
        case 0x41: case 0x42: case 0x43: case 0x50: st |= 4; break;
        case 4: case 0x14: st |= 8; break;
        case 8: case 0x18: st |= 0x10; break;
    }
    if (ty == 0x80) {                                   /* the origin lot: the trip is complete */
        if (st & 0x40000000u) {
            InterlockedIncrement(&g_tm[0]);
            for (k = 0; k < 5; k++) if (st & (1u << k)) InterlockedIncrement(&g_tm[1 + k]);
            if (st & 0x1c) InterlockedIncrement(&g_tm[6]);
            if (!(st & 0x1f)) InterlockedIncrement(&g_tm[7]);
            else if (g_tc_cur) tc_cell_add(node, 1u | ((st & 0x1c) ? 0x10000u : 0));   /* TRIPCELLS */
        }
        st = 0;
    }
    TlsSetValue(g_tm_tls, (LPVOID)st);
    SetLastError(e);
}
static __declspec(naked) void tm_stub(void) {
    __asm {
        pushad
        pushfd
        push ebp
        push ebx
        call tm_on_pop
        add esp, 8
        popfd
        popad
        jmp dword ptr [g_tm_target]
    }
}
static int tm_write_q(BYTE *at, const BYTE *bytes, int len) {   /* sc3cartrips write_q: one locked 8-byte exchange */
    BYTE *q = (BYTE *)((DWORD)at & ~7u);
    int off = (int)(at - q);
    DWORD old;
    LONGLONG cur, nw;
    if (off + len > 8) return 0;
    if (!VirtualProtect(q, 8, PAGE_EXECUTE_READWRITE, &old)) return 0;   /* left writable: mod startup races */
    do {
        cur = *(volatile LONGLONG *)q;
        nw = cur;
        memcpy((BYTE *)&nw + off, bytes, len);
    } while (InterlockedCompareExchange64((volatile LONGLONG *)q, nw, cur) != cur);
    FlushInstructionCache(GetCurrentProcess(), q, 8);
    return 1;
}
static void tm_install(void) {
    static const BYTE e_pop[] = { 0xf3, 0xa5, 0x8d, 0x4d, 0x80, 0xe8, 0xf0, 0x2b, 0x00, 0x00, 0x80, 0x7d, 0x14, 0x00 };
    static int done;
    HMODULE st;
    BYTE *p, b[5];
    if (done || !g_tripmodes) return;
    if (!(st = GetModuleHandleA("SimTransit.dll"))) return;
    done = 1;
    p = (BYTE *)st + 0x72f3;
    if (IsBadReadPtr(p, sizeof(e_pop)) || memcmp(p, e_pop, sizeof(e_pop))) {
        logf("TRIPMODES> SimTransit+0x72f3 is not the shipped pop call (sc3cartrips loaded?): no trip counting");
        return;
    }
    if ((g_tm_tls = TlsAlloc()) == TLS_OUT_OF_INDEXES) { logf("TRIPMODES> no TLS index: no trip counting"); return; }
    tc_alloc();   /* TRIPCELLS, before the patch goes live */
    g_tm_target = (DWORD)st + 0x9eed;
    b[0] = 0xE8; *(DWORD *)(b + 1) = (DWORD)tm_stub - (DWORD)(p + 5 + 5);
    if (!tm_write_q(p + 5, b, 5)) { logf("TRIPMODES> patch at SimTransit+0x72f8 failed"); return; }
    g_tm_on = 1;
    logf("TRIPMODES> on: route_trip pop call SimTransit+0x72f8 counts trips per network");
}
/* a month closed (GRAPHNEW gn_month, sim thread): keep its counts, start the next */
static void tm_month(int key) {
    int k;
    if (!g_tm_on) return;
    for (k = 0; k < TM_N; k++) g_tm_last[k] = InterlockedExchange(&g_tm[k], 0);
    tc_month(g_tm_lastkey >= 0 && key != g_tm_lastkey + 1);   /* TRIPCELLS: a jump (city load) drops the old city's cells */
    g_tm_lastkey = key;
    logf("TRIPMODES> month %d: %ld trips, road %ld highway %ld bus %ld rail %ld subway %ld transit %ld none %ld", key, g_tm_last[0],
         g_tm_last[1], g_tm_last[2], g_tm_last[3], g_tm_last[4], g_tm_last[5], g_tm_last[6], g_tm_last[7]);
}

/* TRIPCELLS readers (sc3dataview): the drawn grid, packed like the others (5 x 5 neighbourhood, fixed point) */
__declspec(dllexport) DWORD __cdecl sc3resize_tripcell(int x, int z) {
    DWORD *d = g_tc_disp;
    if (!d || x < 0 || z < 0 || x > g_tc_dx || z > g_tc_dz) return 0;
    return d[x * TC_S + z];
}
/* rebuild the drawn grid now (the map was switched in) */
__declspec(dllexport) void __cdecl sc3resize_tripcells_build(void) {
    __try { tc_build(); } __except (EXCEPTION_EXECUTE_HANDLER) { InterlockedExchange(&g_tc_busy, 0); }
}
__declspec(dllexport) int __cdecl sc3resize_tripcells_info(LONG *out) {
    __try { tm_install(); } __except (EXCEPTION_EXECUTE_HANDLER) { }
    if (out) {
        out[0] = vb_es(); out[1] = g_tm_last[0]; out[2] = g_tm_last[6]; out[3] = g_tm_last[7];
        out[4] = g_tc_months; out[5] = g_tm[0]; out[6] = g_tm[6];
    }
    return g_tm_on && g_tc_cur != NULL;
}

/* ---------------------------------------------------------------------------------------------- the data */
static int g_vb_lock = 1;   /* SC3RESIZE_VDBARS_LOCK=0: read the water / treatment lists without the layers' locks */
static void *vb_lock(void *L) { if (L && !IsBadReadPtr(L, 4)) ho_v(L, 0x04, 0, 0, 0, 0, 0, 0); return L; }
static void vb_unlock(void *L) { if (L && !IsBadReadPtr(L, 4)) ho_v(L, 0x08, 0, 0, 0, 0, 0, 0); }

static BYTE *vb_res(void) {
    HMODULE rci = GetModuleHandleA("SIMRCI.DLL");
    BYTE *c = gn_city(), *rl;
    if (!c || !rci) return NULL;
    rl = *(BYTE **)(c + 0xe4);
    if (!rl || IsBadReadPtr(rl, 0x690) || *(DWORD *)rl != (DWORD)rci + 0x4c99c) return NULL;
    return rl;
}
typedef float (__fastcall *VB_PCTFN)(void *self, void *edx, int lo, int hi);

/* residents aged lo..hi (the pass clamps the band to 89): population x cohort share */
static double vb_band(BYTE *rl, int lo, int hi, double *share) {
    double pop = (double)(LONG)ho_v(rl, 0x78, 0, 0, 0, 0, 0, 0);
    float f;
    if (hi > 89) hi = 89;
    if (lo > hi) { *share = 0; return 0; }
    f = ((VB_PCTFN)(*(void ***)rl)[0x80 / 4])(rl, NULL, lo, hi);
    *share = f;
    return pop * f;
}

static void vb_education(VB *b, int x0, int x1, int y) {
    HMODULE rci = GetModuleHandleA("SIMRCI.DLL");
    BYTE *rl = vb_res(), *g = (BYTE *)rci;
    char sub[48], t[96], n1[16], n2[16];
    int es = vb_es();
    LONG libc, musc, libu, musu;
    double rlib, rmus, slib, smus;
    if (!rl) { vb_text(b, SC3TR(es, "cuadros.no_education_data", "Sin datos de educaci\xf3n", "No education data"), g_vb_ink, x0, y, 300, 14, 1); return; }
    libc = *(LONG *)(rl + 0x67c); musc = *(LONG *)(rl + 0x680);
    libu = *(LONG *)(g + 0x5741c); musu = *(LONG *)(g + 0x5745c);
    rlib = vb_band(rl, g[0x57420], g[0x57421], &slib);
    rmus = vb_band(rl, g[0x57460], g[0x57461], &smus);
    vb_pair(b, x0, x1, y, SC3TR(es, "cuadros.schools", "Escuelas", "Schools"), SC3TR(es, "cuadros.pupils_places", "alumnos / plazas", "pupils / places"),
            *(LONG *)(rl + 0x66c), *(LONG *)(rl + 0x670), 1, 1);
    vb_pair(b, x0, x1, y + 26, SC3TR(es, "cuadros.colleges", "Universidades", "Colleges"), SC3TR(es, "cuadros.students_places", "alumnos / plazas", "students / places"),
            *(LONG *)(rl + 0x674), *(LONG *)(rl + 0x678), 1, 1);
    wsprintfA(t, "%s (%ld)", SC3TR(es, "cuadros.libraries", "Bibliotecas", "Libraries"), libu > 0 ? libc / libu : 0);
    /* the [Library] INI section is read by the first library built (ctor FUN_1000793d, guard DAT_100585b4): with none
       built the globals hold the file's defaults (PopServed 60000, ages 6..18, measured on Berlin), so no band then */
    if (libc > 0) wsprintfA(sub, SC3TR(es, "cuadros.aged_places", "%d-%d a\xf1os / plazas", "aged %d-%d / places"), g[0x57420], g[0x57421] > 89 ? 89 : g[0x57421]);
    else { lstrcpyA(sub, SC3TR(es, "cuadros.none_in_city", "ninguna en la ciudad", "none in the city")); rlib = 0; }
    vb_pair(b, x0, x1, y + 52, t, sub, rlib, libc, 0, 1);
    wsprintfA(t, "%s (%ld)", SC3TR(es, "cuadros.museums", "Museos", "Museums"), musu > 0 ? musc / musu : 0);
    if (musc > 0) wsprintfA(sub, SC3TR(es, "cuadros.aged_places", "%d-%d a\xf1os / plazas", "aged %d-%d / places"), g[0x57460], g[0x57461] > 89 ? 89 : g[0x57461]);
    else { lstrcpyA(sub, SC3TR(es, "cuadros.none_in_city_2", "ninguno en la ciudad", "none in the city")); rmus = 0; }
    vb_pair(b, x0, x1, y + 78, t, sub, rmus, musc, 0, 1);
    vb_num(n1, *(LONG *)(rl + 0x684)); vb_num(n2, *(LONG *)(rl + 0x688));
    wsprintfA(t, SC3TR(es, "cuadros.teachers_professors_strike", "Docentes %s   Profesores %s   Huelga: %s", "Teachers %s   Professors %s   Strike: %s"), n1, n2,
              rl[0x650] && rl[0x651] ? (SC3TR(es, "cuadros.schools_and_colleges", "escuela y universidad", "schools and colleges")) :
              rl[0x650] ? (SC3TR(es, "cuadros.schools_2", "escuela", "schools")) : rl[0x651] ? (SC3TR(es, "cuadros.colleges_2", "universidad", "colleges")) : SC3TR(es, "cuadros.no", "no", "no"));
    vb_text(b, t, g_vb_ink, x0, y + 106, x1 - x0, 14, 1);
    vb_legend(b, x0, x1, y + 122);
    if (g_vt_log) {
        static char last[200];
        char lg[200];
        wsprintfA(lg, "school %ld/%ld college %ld/%ld library %ld (unit %ld, band %d-%d share %ld/1e6 -> %ld) museum %ld (unit %ld, band %d-%d share %ld/1e6 -> %ld)",
                  *(LONG *)(rl + 0x66c), *(LONG *)(rl + 0x670), *(LONG *)(rl + 0x674), *(LONG *)(rl + 0x678), libc, libu,
                  g[0x57420], g[0x57421], (long)(slib * 1e6), (long)rlib, musc, musu, g[0x57460], g[0x57461], (long)(smus * 1e6), (long)rmus);
        if (lstrcmpA(lg, last)) { lstrcpyA(last, lg); logf("VDBARS> education: %s", lg); }
    }
}

static void vb_health(VB *b, int x0, int x1, int y) {
    BYTE *rl = vb_res();
    char t[96], n1[16];
    int es = vb_es();
    if (!rl) { vb_text(b, SC3TR(es, "cuadros.no_health_data", "Sin datos de salud", "No health data"), g_vb_ink, x0, y, 300, 14, 1); return; }
    vb_pair(b, x0, x1, y, SC3TR(es, "cuadros.hospitals", "Hospitales", "Hospitals"), SC3TR(es, "cuadros.patients_beds", "pacientes / camas", "patients / beds"),
            *(LONG *)(rl + 0x664), *(LONG *)(rl + 0x668), 1, 1);
    vb_num(n1, *(LONG *)(rl + 0x68c));
    wsprintfA(t, SC3TR(es, "cuadros.doctors_strike", "M\xe9" "dicos %s   Huelga: %s", "Doctors %s   Strike: %s"), n1, rl[0x652] ? (SC3TR(es, "cuadros.yes", "s\xed", "yes")) : SC3TR(es, "cuadros.no", "no", "no"));
    vb_text(b, t, g_vb_ink, x0, y + 28, x1 - x0, 14, 1);
    vb_legend(b, x0, x1, y + 44);
    if (g_vt_log) {
        static LONG last[3] = { -1, -1, -1 };
        if (last[0] != *(LONG *)(rl + 0x664) || last[1] != *(LONG *)(rl + 0x668) || last[2] != *(LONG *)(rl + 0x68c)) {
            last[0] = *(LONG *)(rl + 0x664); last[1] = *(LONG *)(rl + 0x668); last[2] = *(LONG *)(rl + 0x68c);
            logf("VDBARS> health: patients %ld beds %ld doctors %ld strike %d", last[0], last[1], last[2], rl[0x652]);
        }
    }
}

static void vb_water(VB *b, int px0, int px1, int py, int lx0, int lx1, int ly) {
    HMODULE ut = GetModuleHandleA("SIMUTIL.DLL"), eco = GetModuleHandleA("SIMECO.DLL");
    BYTE *city = gn_city(), *P = NULL, *po = NULL;
    double cap[3] = { 0, 0, 0 }, out[3] = { 0, 0, 0 }, pcap = 0;
    LONG cnt[3] = { 0, 0, 0 }, np = 0, aging = 0, prod = 0, treat = 0, wp = 0, wmax = 0, dry = 0, cons = 0;
    __int64 sup = 0, del = 0;
    int es = vb_es(), k, nn = 0;
    char t[96], sub[48];
    static const SC3TXT nm[3] = { { SC3KEY("cuadros.pumps"), "Bombas", "Pumps" },
        { SC3KEY("cuadros.water_towers"), "Torres de agua", "Water towers" },
        { SC3KEY("cuadros.desalination"), "Desalinizadoras", "Desalination" } };
    if (city) {
        BYTE *p = (BYTE *)ho_v(city, 0x154, 0, 0, 0, 0, 0, 0);
        if (p && ut && !IsBadReadPtr(p, 0xd0) && *(DWORD *)p == (DWORD)ut + 0x22944) P = p;
        p = (BYTE *)ho_v(city, 0x16c, 0, 0, 0, 0, 0, 0);
        if (p && eco && !IsBadReadPtr(p, 0xf0) && *(DWORD *)p == (DWORD)eco + 0x1b984) po = p;
    }
    if (g_vt_log) {
        static int once;
        if (!once++) logf("VDBARS> water: P 0x%08lX lock 0x%08lX (vt 0x%08lX), po 0x%08lX lock 0x%08lX (vt 0x%08lX)", (DWORD)P,
                          P ? *(DWORD *)(P + 0x14) : 0, P && *(DWORD *)(P + 0x14) && !IsBadReadPtr(*(void **)(P + 0x14), 4) ? **(DWORD **)(P + 0x14) : 0,
                          (DWORD)po, po ? *(DWORD *)(po + 0x74) : 0, po && *(DWORD *)(po + 0x74) && !IsBadReadPtr(*(void **)(po + 0x74), 4) ? **(DWORD **)(po + 0x74) : 0);
    }
    if (P) {
        void *L = g_vb_lock ? vb_lock(*(void **)(P + 0x14)) : NULL;
        __try {
            BYTE *lst = *(BYTE **)(P + 0x74), *s = lst ? *(BYTE **)lst : NULL, *n;
            sup = *(__int64 *)(P + 0xb0); del = *(__int64 *)(P + 0xb8); cons = *(LONG *)(P + 0xc0); dry = *(LONG *)(P + 0xc4);
            for (n = s ? *(BYTE **)s : NULL; n && n != s && nn < 4096 && !IsBadReadPtr(n, 0x28); n = *(BYTE **)n, nn++) {
                int ty = *(WORD *)(n + 0x20), i = ty == 3 ? 0 : ty == 2 ? 1 : ty == 5 ? 2 : -1;
                if (i < 0) continue;
                cnt[i]++; cap[i] += *(WORD *)(n + 0x18); out[i] += *(WORD *)(n + 0x1a);
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) { logf("VDBARS> water list read threw 0x%08lX", GetExceptionCode()); }
        vb_unlock(L);
    }
    if (po) {
        void *L = g_vb_lock ? vb_lock((void *)(po + 0x74)) : NULL;
        __try {
            BYTE *s = *(BYTE **)(po + 0x98), *n;
            for (n = s ? *(BYTE **)s : NULL; n && n != s && np < 4096 && !IsBadReadPtr(n, 0xc); n = *(BYTE **)n) {
                void *it = *(void **)(n + 8);
                if (it) { pcap += 30.0 * (double)(LONG)ho_v(it, 0x34, 0, 0, 0, 0, 0, 0); np++; }
            }
            prod = *(LONG *)(po + 0xe8); treat = *(LONG *)(po + 0xec); aging = *(LONG *)(po + 0xb8);
        } __except (EXCEPTION_EXECUTE_HANDLER) { logf("VDBARS> treatment list read threw 0x%08lX", GetExceptionCode()); }
        vb_unlock(L);
        wp = (LONG)ho_v(po, 0x7c, 0, 0, 0, 0, 0, 0); wmax = (LONG)ho_v(po, 0x88, 0, 0, 0, 0, 0, 0);
    }
    vb_text(b, SC3TR(es, "cuadros.water_sources_this_month", "Fuentes de agua (este mes)", "Water sources (this month)"), g_vb_ink, px0, py, px1 - px0, 14, 1);
    for (k = 0; k < 3; k++) {
        wsprintfA(t, "%s (%ld)", sc3lang_txt(es, &nm[k]), cnt[k]);
        vb_pair(b, px0, px1, py + 16 + 26 * k, t, SC3TR(es, "cuadros.output_capacity", "produce / capacidad", "output / capacity"), out[k], cap[k], 0, 0);
    }
    vb_pair(b, px0, px1, py + 16 + 78, SC3TR(es, "cuadros.total", "Total", "Total"), SC3TR(es, "cuadros.delivered_supply", "entregada / oferta", "delivered / supply"), (double)del, (double)sup, 1, 1);
    if (!P) lstrcpyA(t, SC3TR(es, "cuadros.no_water_layer", "Sin red de agua", "No water layer"));
    else if (dry > 0) wsprintfA(t, SC3TR(es, "cuadros.buildings_without_water", "Edificios sin agua: %ld de %ld", "Buildings without water: %ld of %ld"), dry, cons);
    else lstrcpyA(t, SC3TR(es, "cuadros.every_building_that_needs", "Todos los edificios que piden agua la reciben", "Every building that needs water gets it"));
    vb_text(b, t, dry > 0 ? g_vb_warn : g_vb_ink, px0, py + 16 + 106, px1 - px0, 14, 1);
    if (po) {
        char v[16];
        vb_pct(v, wp, wmax > 0 ? wmax : 1);
        wsprintfA(t, SC3TR(es, "cuadros.water_pollution", "Contaminaci\xf3n del agua: %s", "Water pollution: %s"), v);
        vb_text(b, t, g_vb_ink, px0, py + 16 + 122, px1 - px0, 14, 1);
    }
    /* below the tabs: treatment */
    vb_text(b, SC3TR(es, "cuadros.water_treatment_last_month", "Tratamiento de aguas (mes pasado)", "Water treatment (last month)"), g_vb_ink, lx0, ly, lx1 - lx0, 14, 1);
    vb_pair(b, lx0, lx1, ly + 16, SC3TR(es, "cuadros.pollution", "Contaminaci\xf3n", "Pollution"), SC3TR(es, "cuadros.treated_produced", "tratada / producida", "treated / produced"), treat, prod, 1, 2);
    wsprintfA(t, SC3TR(es, "cuadros.plants", "Plantas (%ld)", "Plants (%ld)"), np);
    wsprintfA(sub, SC3TR(es, "cuadros.capacity_produced", "capacidad / producida", "capacity / produced"));   /* capacity = sum of item vt+0x34 x 30 */
    vb_pair(b, lx0, lx1, ly + 42, t, sub, pcap, prod, 0, 2);
    if (aging > 0) {
        wsprintfA(t, SC3TR(es, "cuadros.aging_plants_capacity_falls", "Plantas envejecidas: %ld (su capacidad baja)", "Aging plants: %ld (capacity falls)"), aging);
        vb_text(b, t, g_vb_warn, lx0, ly + 70, lx1 - lx0, 14, 1);
    }
    vb_legend(b, lx0, lx1, ly + 86);
    if (g_vt_log) {
        static char last[300];
        char lg[300];
        wsprintfA(lg, "layer %s supply %ld delivered %ld dry %ld of %ld; pumps %ld %ld/%ld towers %ld %ld/%ld desal %ld %ld/%ld (%d nodes); "
                  "treatment %s plants %ld cap*30 %ld produced %ld treated %ld aging %ld; pollution %ld/%ld", P ? "ok" : "MISSING",
                  (long)sup, (long)del, dry, cons, cnt[0], (long)out[0], (long)cap[0], cnt[1], (long)out[1], (long)cap[1], cnt[2],
                  (long)out[2], (long)cap[2], nn, po ? "ok" : "MISSING", np, (long)pcap, prod, treat, aging, wp, wmax);
        if (lstrcmpA(lg, last)) { lstrcpyA(last, lg); logf("VDBARS> water: %s", lg); }
    }
}

static void vb_transport(VB *b, int x0, int x1, int y) {
    HMODULE st = GetModuleHandleA("SimTransit.dll");
    BYTE *T = st ? *(BYTE **)((BYTE *)st + 0x1fdb8) : NULL;
    LONG v[TM_N], key = g_tm_lastkey;
    int es = vb_es(), k, cur = key < 0;
    char t[120], val[24], n1[16];
    static const SC3TXT nm[6] = { { SC3KEY("cuadros.mode_streets"), "Calles", "Streets" },
        { SC3KEY("cuadros.mode_highways"), "Autopistas", "Highways" }, { SC3KEY("cuadros.mode_bus"), "Autob\xfas", "Bus" },
        { SC3KEY("cuadros.mode_rail"), "Tren", "Rail" }, { SC3KEY("cuadros.mode_subway"), "Metro", "Subway" },
        { SC3KEY("cuadros.mode_none"), "Sin usar red", "No network" } };
    static const int slot[6] = { 1, 2, 3, 4, 5, 7 };
    for (k = 0; k < TM_N; k++) v[k] = cur ? g_tm[k] : g_tm_last[k];
    if (!g_tm_on) {
        vb_text(b, SC3TR(es, "cuadros.trip_counting_off_sc3resize", "Conteo de viajes apagado (SC3RESIZE_TRIPMODES=0 o sc3cartrips cargado)", "Trip counting is off (SC3RESIZE_TRIPMODES=0 or sc3cartrips loaded)"), g_vb_ink, x0, y, x1 - x0, 14, 1);
        return;
    }
    vb_num(n1, v[0]);
    wsprintfA(t, SC3TR(es, "cuadros.trips_using_each_network", "Viajes que usan cada medio (%s, %s viajes)", "Trips using each network (%s, %s trips)"),
              cur ? (SC3TR(es, "cuadros.this_month", "este mes", "this month")) : (SC3TR(es, "cuadros.last_month", "mes pasado", "last month")), n1);
    vb_text(b, t, g_vb_ink, x0, y, x1 - x0, 14, 1);
    for (k = 0; k < 6; k++) {
        vb_pct(val, v[slot[k]], v[0]);
        vb_one(b, x0, x1, y + 18 + 17 * k, sc3lang_txt(es, &nm[k]), v[0] > 0 ? (double)v[slot[k]] / v[0] : 0, val);
    }
    vb_text(b, SC3TR(es, "cuadros.one_trip_can_use", "Un viaje puede usar varios medios.", "One trip can use several networks."), g_vb_sub, x0, y + 18 + 102, x1 - x0, 14, 1);
    if (T && !IsBadReadPtr(T, 0xc0) && *(DWORD *)T == (DWORD)st + 0x1a368) {
        float fr = *(float *)(T + 0xb8);
        vb_pct(val, fr * 1000.0, 1000.0);
        wsprintfA(t, SC3TR(es, "cuadros.trips_with_no_destination", "Viajes sin destino (mes pasado): %s", "Trips with no destination (last month): %s"), val);
        vb_text(b, t, g_vb_ink, x0, y + 18 + 118, x1 - x0, 14, 1);
    }
    {   int sw = sw_cuadros_text(t, sizeof(t));   /* STATIONWARN: poorly connected stations */
        if (sw) vb_text(b, t, sw == 2 ? g_vb_warn : g_vb_ink, x0, y + 18 + 134, x1 - x0, 14, 1);
    }
    if (g_vt_log) {
        static LONG last = -2;
        if (last != key) {
            last = key;
            logf("VDBARS> transport (%s): %ld trips road %ld hwy %ld bus %ld rail %ld subway %ld none %ld; T fail ratio %ld/1000",
                 cur ? "this month" : "last month", v[0], v[1], v[2], v[3], v[4], v[5], v[7],
                 T && !IsBadReadPtr(T, 0xc0) ? (long)(*(float *)(T + 0xb8) * 1000.0f) : -1);
        }
    }
}

/* ---------------------------------------------------------------------------------------------- the Cuadros page */
#define CQ_ID0  0x7A3C0400u     /* VDTABS strip (+1 .. +0x51) */
#define CQ_TABS 7
#define CQ_NEW  5               /* tabs from here on are ours */
/* "Electricidad" -> "Energia" on the tab (the Graficas tabs' word): 7 captions fit 374 px with 4 px padding otherwise */
static const SC3TXT k_cq[CQ_TABS] = {
    { SC3KEY("cuadros.tab_education"), "Educaci\xf3n", "Education" }, { SC3KEY("cuadros.tab_health"), "Salud", "Health" },
    { SC3KEY("cuadros.tab_population"), "Poblaci\xf3n", "Population" }, { SC3KEY("cuadros.tab_power"), "Energ\xed""a", "Power" },
    { SC3KEY("cuadros.tab_garbage"), "Basura", "Garbage" }, { SC3KEY("cuadros.tab_water"), "Agua", "Water" },
    { SC3KEY("cuadros.tab_transport"), "Transporte", "Transport" } };
static const DWORD k_cq_stock[CQ_NEW] = { 6, 9, 10, 7, 8 };   /* the radio ids of the stock charts */
static const DWORD k_cq_hide[] = { 2, 3, 0xb, 0xc, 0xd, 0xe, 0xf, 0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1a, 0x1b, 0x1c };
#define CQ_NHIDE (sizeof(k_cq_hide) / sizeof(k_cq_hide[0]))
#define H_ID_DV  0x0DA7A100u    /* sc3dataview's Cuadros text column, ids + 0..8 */
static TB    g_cq_tb;
static struct { BYTE *dir; void *win; int tab, hidden, px0, py0, px1, py1; BYTE vis[CQ_NHIDE]; } g_cq;
static DWORD g_cq_orig_build, g_cq_orig_close, g_cq_orig_ctl, g_cq_orig_msg;

static void cq_ini(int save) {
    char p[MAX_PATH], v[8];
    ho_ini_path(p, sizeof(p));
    if (save) { wsprintfA(v, "%d", g_cq.tab); WritePrivateProfileStringA("cuadros", "tab", v, p); }
    else g_cq.tab = (int)GetPrivateProfileIntA("cuadros", "tab", -1, p);
}

static int cq_stock_sel(void *win) {   /* the stock group's selection (radio id), 0 = unknown */
    void *g = mp_child(win, 5), *o = NULL;
    DWORD s = 0;
    if (g && (ho_v(g, 0x00, 2, 0xa1336cc0, (DWORD)&o, 0, 0, 0) & 0xff) && o) { s = ho_v(o, 0x30, 0, 0, 0, 0, 0, 0); ho_v(o, 0x08, 0, 0, 0, 0, 0, 0); }
    return (int)s;
}
static void cq_set_stock(void *win, DWORD id) {
    void *g = mp_child(win, 5), *o = NULL;
    if (g && (ho_v(g, 0x00, 2, 0xa1336cc0, (DWORD)&o, 0, 0, 0) & 0xff) && o) { ho_v(o, 0x34, 1, id, 0, 0, 0, 0); ho_v(o, 0x08, 0, 0, 0, 0, 0, 0); }
}
static int vb_visible(void *w) { return w && !IsBadReadPtr(w, 0xa4) ? (int)(ho_v(w, 0x100, 0, 0, 0, 0, 0, 0) & 0xff) : 0; }
static void cq_move(void *win, DWORD id, int x, int y) {
    BYTE *w = (BYTE *)mp_child(win, id);
    if (w && !IsBadReadPtr(w, 0x90) && (*(LONG *)(w + 0x80) != x || *(LONG *)(w + 0x84) != y)) ho_v(w, 0xcc, 2, (DWORD)x, (DWORD)y, 0, 0, 0);
}

static void cq_frame(void *win, int on);   /* below */
/* after every fill / refresh / tab pick: the stock children for the tab, then our bars */
static void cq_after(void *win) {
    HMODULE sui = GetModuleHandleA("SIMUI.DLL");
    VB b;
    unsigned k;
    if (!win || win != g_cq.win || IsBadReadPtr(win, 0xa4)) return;
    if (g_vdtabs && g_cq_tb.n) {
        cq_move(win, 0xb, 10, 222);                       /* the two text lines below the tab row */
        cq_move(win, 0xc, 10, 238);
        { BYTE *g = (BYTE *)mp_child(win, 5); if (g && vb_visible(g)) { gx_show(g, 0); ho_v(g, 0xcc, 2, 150, 4000, 0, 0, 0); } }
    }
    if (g_cq.tab >= CQ_NEW) {
        if (!g_cq.hidden) {
            for (k = 0; k < CQ_NHIDE; k++) g_cq.vis[k] = (BYTE)vb_visible(mp_child(win, k_cq_hide[k]));
            g_cq.hidden = 1;
        }
        for (k = 0; k < CQ_NHIDE; k++) gx_show(mp_child(win, k_cq_hide[k]), 0);
    } else if (g_cq.hidden) {
        for (k = 0; k < CQ_NHIDE; k++) if (g_cq.vis[k]) gx_show(mp_child(win, k_cq_hide[k]), 1);
        g_cq.hidden = 0;
    }
    if (g_vdtabs && g_cq_tb.n) cq_frame(win, g_cq.tab >= CQ_NEW && g_vdbars);
    memset(&b, 0, sizeof(b));
    b.win = win;
    b.fac = sui ? ((void *(__cdecl *)(void))((BYTE *)sui + 0x85065))() : NULL;
    if (g_vdbars && b.fac) {
        vb_colours();
        if (g_cq.tab <= 1 || g_cq.tab >= CQ_NEW)
            for (k = 0; k < 9; k++) gx_show(mp_child(win, H_ID_DV + k), 0);   /* sc3dataview's text: ours replaces it */
        __try {
            int ly = g_vdtabs && g_cq_tb.n ? 262 : 240;
            if (g_cq.tab == 0) vb_education(&b, 6, 380, ly);
            else if (g_cq.tab == 1) vb_health(&b, 6, 380, ly);
            else if (g_cq.tab >= CQ_NEW) {
                /* the chart frame for our tabs (the stock one is the chart child itself, hidden here): panel colour,
                   tab border, joined to the tab row like the stock charts */
                if (g_cq.tab == 5) vb_water(&b, g_cq.px0 + 6, g_cq.px1 - 6, g_cq.py0 + 4, 6, 380, 222);
                else vb_transport(&b, g_cq.px0 + 6, g_cq.px1 - 6, g_cq.py0 + 4);
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) { logf("VDBARS> tab %d draw threw 0x%08lX", g_cq.tab, GetExceptionCode()); }
    }
    vb_end(&b);
    ho_v(win, 0x168, 0, 0, 0, 0, 0, 0);
    ho_v(win, 0x14c, 0, 0, 0, 0, 0, 0);
    ho_v(win, 0x154, 0, 0, 0, 0, 0, 0);
}

static void cq_fill(void *win) {
    HMODULE sui = GetModuleHandleA("SIMUI.DLL");
    DWORD a[1];
    a[0] = (DWORD)win;
    if (sui && g_cq.dir) rz_thiscall_ret(g_cq.dir, (BYTE *)sui + 0x245c7, a, 1);   /* through sc3dataview's detour when present */
}

static void cq_select(void *win, int t) {
    HMODULE sui = GetModuleHandleA("SIMUI.DLL");
    g_cq.tab = t;
    cq_ini(1);
    g_cq_tb.sel = t;
    tb_draw(&g_cq_tb);
    __try {   /* the stock click sound (FUN_1001f30d on a radio pick) */
        void *p = ((void *(__cdecl *)(void))((BYTE *)sui + 0x8e77f))();
        if (p && (p = (void *)ho_v(p, 0x34, 0, 0, 0, 0, 0, 0))) ho_v(p, 0x14, 5, 1, 0xd, 0, 0, 0);
    } __except (EXCEPTION_EXECUTE_HANDLER) { }
    if (t < CQ_NEW) {
        if (g_cq.hidden) cq_after(win);                         /* the stock children back first */
        cq_set_stock(win, k_cq_stock[t]);
        cq_fill(win);
    }
    cq_after(win);
    logf("VDTABS> Cuadros tab %d (%s)", t, k_cq[t].es);
}

/* the chart frame of our tabs (the stock frame is drawn by chart child 2, hidden there): fill + left / top / right
   edges, made before the tab strip so it lies under the tabs and every bar; its bottom edge is the strip's rule */
#define CQ_FRAME 0x7A3C0480u
static void cq_frame(void *win, int on) {
    int k, w = g_cq.px1 - g_cq.px0, h = g_cq.py1 - g_cq.py0;
    vt_rect(win, CQ_FRAME + 0, g_vt_c_sel, g_cq.px0, g_cq.py0, w, h);
    vt_rect(win, CQ_FRAME + 1, g_vt_c_border, g_cq.px0, g_cq.py0, 1, h);
    vt_rect(win, CQ_FRAME + 2, g_vt_c_border, g_cq.px0, g_cq.py0, w, 1);
    vt_rect(win, CQ_FRAME + 3, g_vt_c_border, g_cq.px1 - 1, g_cq.py0, 1, h);
    if (!on) for (k = 0; k < 4; k++) gx_show(mp_child(win, CQ_FRAME + k), 0);
}

static void cq_setup(BYTE *dir, void *win) {
    HMODULE sui = GetModuleHandleA("SIMUI.DLL");
    void *fac = sui ? ((void *(__cdecl *)(void))((BYTE *)sui + 0x85065))() : NULL;
    const char *tx[CQ_TABS];
    int k, sel = cq_stock_sel(win), t = 0, x0 = 14, x1 = 370, y = 198;
    BYTE *pn = (BYTE *)mp_child(win, 4);
    g_cq.px0 = 14; g_cq.py0 = 10; g_cq.px1 = 370; g_cq.py1 = 198;
    if (pn && !IsBadReadPtr(pn, 0x90) && *(BYTE **)(pn + 0x3c) == (BYTE *)win) {
        g_cq.px0 = *(LONG *)(pn + 0x80); g_cq.py0 = *(LONG *)(pn + 0x84); g_cq.px1 = *(LONG *)(pn + 0x88); g_cq.py1 = *(LONG *)(pn + 0x8c) - 1;
    }
    tm_install();
    g_cq.dir = dir; g_cq.win = win; g_cq.hidden = 0;
    g_vb_nl = g_vb_ns = 0;
    memset(&g_cq_tb, 0, sizeof(g_cq_tb));
    cq_ini(0);
    for (k = 0; k < CQ_NEW; k++) if ((int)k_cq_stock[k] == sel) t = k;
    if (g_cq.tab < CQ_NEW || g_cq.tab >= CQ_TABS || !g_vdtabs) g_cq.tab = t;   /* a stock tab: the game's own pick */
    if (g_vdtabs && fac) {
        if (pn && !IsBadReadPtr(pn, 0x90) && *(BYTE **)(pn + 0x3c) == (BYTE *)win) {
            x0 = *(LONG *)(pn + 0x80); x1 = *(LONG *)(pn + 0x88); y = *(LONG *)(pn + 0x8c) - 1;
        }
        for (k = 0; k < CQ_TABS; k++) tx[k] = sc3lang_txt(vb_es(), &k_cq[k]);
        vt_colours(fac);
        cq_frame(win, 0);
        g_vt_cur = g_vt_small ? g_vt_small_id : g_vt_font;
        tb_make(fac, win, &g_cq_tb, CQ_ID0, tx, CQ_TABS, g_cq.tab, x0 - 8, x1 + 10, y, 18);
        g_vt_cur = g_vt_font;
    }
    logf("VDTABS> Cuadros page 0x%08lX built: stock radio %d, tab %d, panel bottom %d", (DWORD)win, sel, g_cq.tab, y);
    cq_after(win);
}

typedef DWORD (__fastcall *CQ_FN1)(void *self, void *edx, DWORD a);
typedef DWORD (__fastcall *CQ_FN5)(void *self, void *edx, DWORD a, DWORD b, DWORD c, DWORD d, DWORD e);
static DWORD __fastcall cq_build(BYTE *dir, void *edx, DWORD win) {
    DWORD r = ((CQ_FN1)g_cq_orig_build)(dir, edx, win);
    __try { if (win) cq_setup(dir, (void *)win); } __except (EXCEPTION_EXECUTE_HANDLER) { logf("VDTABS> Cuadros setup threw 0x%08lX", GetExceptionCode()); }
    return r;
}
static DWORD __fastcall cq_close(BYTE *dir, void *edx, DWORD win) {
    if ((void *)win == g_cq.win) {
        __try { cq_ini(1); } __except (EXCEPTION_EXECUTE_HANDLER) { }
        g_cq.win = NULL; g_cq.dir = NULL; g_cq_tb.n = 0; g_cq_tb.win = NULL;
    }
    return ((CQ_FN1)g_cq_orig_close)(dir, edx, win);
}
static DWORD __fastcall cq_ctl(BYTE *self, void *edx, DWORD win, DWORD msg, DWORD p3, DWORD id, DWORD p5) {
    int t;
    DWORD r;
    if (msg == 3 && p3 == 1 && g_cq.win == (void *)win && (t = tb_hit(&g_cq_tb, (void *)win, id)) >= 0) {
        __try { cq_select((void *)win, t); } __except (EXCEPTION_EXECUTE_HANDLER) { logf("VDTABS> Cuadros tab click threw 0x%08lX", GetExceptionCode()); }
        return 1;
    }
    r = ((CQ_FN5)g_cq_orig_ctl)(self, edx, win, msg, p3, id, p5);
    if (msg == 3 && p3 == 3 && g_cq.win == (void *)win)
        __try { cq_after((void *)win); } __except (EXCEPTION_EXECUTE_HANDLER) { }
    return r;
}
static DWORD __fastcall cq_msg(BYTE *self, void *edx, DWORD m) {
    DWORD r = ((CQ_FN1)g_cq_orig_msg)(self, edx, m);
    if (g_cq.win && m && !IsBadReadPtr((void *)m, 4) && *(DWORD *)m == 0xC2A3FD82u && self - 0xc == g_cq.dir)
        __try { cq_after(g_cq.win); } __except (EXCEPTION_EXECUTE_HANDLER) { logf("VDBARS> refresh threw 0x%08lX", GetExceptionCode()); }
    return r;
}

static int cq_slot(HMODULE sui, DWORD slot, DWORD expect, void *detour, DWORD *orig, const char *name) {
    DWORD *p = (DWORD *)((BYTE *)sui + slot), old;
    if (IsBadReadPtr(p, 4) || *p != (DWORD)sui + expect) { logf("VDTABS> SIMUI+0x%lx (%s) is 0x%08lX, not SIMUI+0x%lx: not hooked", slot, name, p ? *p : 0, expect); return 0; }
    if (!VirtualProtect(p, 4, PAGE_READWRITE, &old)) return 0;   /* left writable: mod startup races */
    *orig = *p;
    InterlockedExchange((LONG *)p, (LONG)detour);
    return 1;
}

static void vb_install(HMODULE sui) {
    char v[8];
    int ok;
    if (GetEnvironmentVariableA("SC3RESIZE_VDTABS", v, sizeof(v))) g_vdtabs = atoi(v);
    if (GetEnvironmentVariableA("SC3RESIZE_VDBARS", v, sizeof(v))) g_vdbars = atoi(v);
    if (GetEnvironmentVariableA("SC3RESIZE_VDTABSROUND", v, sizeof(v))) g_vt_round = atoi(v);
    if (GetEnvironmentVariableA("SC3RESIZE_VDTABSSMALL", v, sizeof(v))) g_vt_small = atoi(v);
    if (GetEnvironmentVariableA("SC3RESIZE_VDTABSFONT", v, sizeof(v))) g_vt_small_id = (int)strtol(v, NULL, 0);
    if (GetEnvironmentVariableA("SC3RESIZE_TRIPMODES", v, sizeof(v))) g_tripmodes = atoi(v);
    if (GetEnvironmentVariableA("SC3RESIZE_VDTABS_FONT", v, sizeof(v))) g_vt_font = atoi(v);
    if (GetEnvironmentVariableA("SC3RESIZE_VDTABS_LOG", v, sizeof(v))) g_vt_log = atoi(v);
    if (GetEnvironmentVariableA("SC3RESIZE_VDREDBARS", v, sizeof(v))) g_vb_redbars = atoi(v);
    if (GetEnvironmentVariableA("SC3RESIZE_VDBARS_LOCK", v, sizeof(v))) g_vb_lock = atoi(v);
    if (!g_vdtabs) g_vdbars = 0;   /* the bars sit where the stock radio group is: no tabs, no bars (sc3dataview's text stays) */
    if (!g_vdtabs && !g_vdbars) { logf("VDTABS> off (SC3RESIZE_VDTABS=0, SC3RESIZE_VDBARS=0): stock Cuadros page"); return; }
    ok = cq_slot(sui, 0xa408c, 0x1f3df, (void *)cq_build, &g_cq_orig_build, "Cuadros build FUN_1001f3df") &&
         cq_slot(sui, 0xa4090, 0x20ffd, (void *)cq_close, &g_cq_orig_close, "Cuadros close FUN_10020ffd") &&
         cq_slot(sui, 0xa4014, 0x1f30d, (void *)cq_ctl, &g_cq_orig_ctl, "Cuadros control FUN_1001f30d") &&
         cq_slot(sui, 0xa3ff4, 0x1f3b3, (void *)cq_msg, &g_cq_orig_msg, "Cuadros refresh FUN_1001f3b3");
    tm_install();
    logf("VDTABS> %s: tabs %d, bars %d, trip modes %d (%s)", ok ? "Cuadros hooked" : "Cuadros NOT fully hooked", g_vdtabs, g_vdbars,
         g_tripmodes, g_tm_on ? "counting" : "SimTransit later");
}
