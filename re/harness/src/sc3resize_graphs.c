/* ======================================================================================================== GRAPHNEW
 * (child graphaxis 2026-10-30, owner pick: income vs expenses, power and water supply vs demand, R/C/I demand, air vs
 * water pollution; child graphtabs 2026-11-02, owner: "Demand graphs are not working, they show nothing, shows flat /
 * energy demand/offer either / put tabs to show different types of graphs, add more graphs according to available
 * data"). #included by sc3resize.c right after the GRAPHAXIS block. Plan and evidence: re/analysis/GRAPH_SERIES.md.
 *
 * 14 new graphs on the Graficas page, one checkbox each, 31 lines. Every line is a series object of the game's own class
 * (SIMMISC ctor 0x10033556, 0xf0 bytes, interface at +8, vtable 0x10041b78 [CONFIRMED]), so the page draws, labels and
 * scales it like its own 16:
 *  - enumeration: the page broadcasts {0x02DC6D7F, 0x605} and each layer answers sink->+0xc(series) = FUN_1002f8c7, which
 *    appends {BYTE on; series *} to page+0x68 [CONFIRMED @ SIMUI 0x1002f8fd, 0x1002f8c7]. A detour on 0x1002f8fd appends
 *    our 31 after the original.
 *  - tabs (graphtabs): a row of 5 radio buttons under the chart (the range group's recipe, SIMUI 0x1002e6cb). Every
 *    checkbox of the page belongs to one tab (k_tab, by checkbox id); only the current tab's checkboxes are shown, from
 *    page (20, 230), 3 per row, pitch 120 x 24, and only the current tab's checked graphs are drawn. A click on a radio
 *    reaches the page handler SIMUI 0x1002df5b as message 3, p3 3, which re-renders [CONFIRMED @ SIMUI 0x1002df5b]; the
 *    tab is read back before every render. A series that must not be drawn gets an id no window has (series vt+0x54):
 *    the renderer's by-id checkbox lookup (0x1002ed75) misses and leaves the on byte we set before it runs. Stock series
 *    get their real id back before the page closes (and on the next enumeration), so the game prefs keep their state.
 *  - close: FUN_1002eb59 writes every entry's on byte to the game prefs keyed by checkbox id, then releases the series
 *    [CONFIRMED @ SIMUI 0x1002eb59]. A detour takes our entries out of the list first (their on state goes to
 *    sc3resize.ini [graphs] instead), so the game prefs never hold our ids.
 *  - recording: SIMMISC FUN_10007d88 (budget, monthly, __fastcall) reads the date (budget+0x14 vt+0x1e4), takes the month
 *    that just closed (month 1 -> December of year - 1, else month - 2), pushes Funds, and on a closed December pushes the
 *    12-month average to the yearly ring and, when (year + 1) % 10 == 0, the 10-year average to the decade ring
 *    [CONFIRMED @ SIMMISC 0x10007d88]. A detour runs after it and does the same for our lines.
 *  - scale: the class clamps a push to its scale in fixed mode (slot +0x64(0), +0x60 scale) [CONFIRMED @ SIMMISC
 *    0x10033baa]. Lines of one graph share one scale (1.1 x the group's largest kept value, rounded up), so they compare
 *    and share one axis column. Values are unsigned in the class, so R/C/I demand is stored + an offset (gn_off).
 *  - history: the class rings live only in memory, so 10 years / 100 years are kept in "<city>.sc3.graphs" next to the
 *    city file, written after a successful city save (SIMCITY 0x1000429d = city vt+0x20); sc3autosave gets its own copy
 *    per autosave through the export sc3resize_graphs_write. It is read the first time the
 *    graphs look at a city in a session and whenever the date jumps (another city or an older save was loaded: the
 *    closed month is neither the last one pushed nor the next), from the city's file or one of its 3 autosaves, and
 *    used only when its date is the city's date. A city
 *    vt+0x1c (0x10003b8b) detour never fired on a load (measured 2026-10-30), so no load hook. The .sc3 itself is not
 *    touched: the stock game ignores the file.
 *  - seeding (graphtabs): a line with no history file used to start as 12 months of its fill value (0, or "no demand"),
 *    which is what the owner saw as "flat, shows nothing" (owner log 2026-11-01: "history starts empty", graphs opened
 *    before a month closed). Now the 12 months come from rings the game itself saves, where one exists:
 *      income / expenses: the budget rings (slots > the closed month hold last year's months, the year-end fold only
 *        zeroes the yearly accumulators) [CONFIRMED @ SIMMISC 0x10007d88, saved by 0x10007519];
 *      power used: the 12 x 10 ring of power used per plant type, power base+0xcc, newest row base+0x2ac
 *        [CONFIRMED @ SIMUTIL 0x10004c1f, saved by 0x100045ec]; power supply from it and the stock Energia % series
 *        (spare % = (S - D) * 100 / S, [CONFIRMED @ SIMUTIL 0x100051b8]): S = D * 100 / (100 - spare) when spare > 0;
 *      garbage: the 7 SIMECO month rings, index = closed month [CONFIRMED @ SIMECO 0x10007b5d, saved by 0x10006abb].
 *    Every other line (no ring in the game) and the 10 / 100 year views are filled with the value of now (the mean of
 *    the seeded 12 months for a seeded line), so a line starts at its real level and moves from the next month.
 * SC3RESIZE_GRAPHNEW=0: none of this is installed (the 16 stock graphs, as before). SC3RESIZE_GRAPHNEW_LOG=1 logs every
 * monthly push. SC3RESIZE_GRAPHTABS=0: no tabs, every checkbox in one grid (the 10-30 page, rows run past the radios). */
static int   g_graphnew = 1, g_gn_log, g_graphtabs = 1;
#define GN_LINES 31
#define GN_GROUPS 14
#define GN_ID0   0x7A3C0100u           /* line i: checkbox id GN_ID0 + i, label id GN_ID0 + 0x40 + i, dummy GN_ID0 + 0x80 + i */
#define GN_STKDUMMY 0x7A3C0200u        /* + k: a stock series kept off the chart (other tab) */
#define GN_TABGRP   0x7A3C0300u        /* the tab radio group; its buttons + 1 + t */
#define GN_TABS  5
#define GT_ID0   0x7A3C0320u           /* VDTABS strip of the Graficas page (ids +1 .. +0x51, sc3resize_vdtabs.c) */
static TB g_gt_tb;
typedef struct { const char *key, *es, *en; int grp; DWORD rgb; } GN_LINE;   /* key: modlang table id */
/* line index = id - GN_ID0 = record id in the history file: lines 0..10 keep their 10-30 meaning (old files stay valid) */
static const GN_LINE k_gn[GN_LINES] = {
    { SC3KEY("graphs.income"), "Ingresos", "Income", 0, 0x209020 },
    { SC3KEY("graphs.expenses"), "Gastos", "Expenses", 0, 0xD02020 },
    { SC3KEY("graphs.power_supply"), "Energ\xed""a oferta", "Power supply", 1, 0xE09000 },
    { SC3KEY("graphs.power_demand"), "Energ\xed""a demanda", "Power demand", 1, 0x7040C0 },
    { SC3KEY("graphs.water_supply"), "Agua oferta", "Water supply", 2, 0x1878E0 },
    { SC3KEY("graphs.water_delivered"), "Agua entregada", "Water delivered", 2, 0x7040C0 },
    { SC3KEY("graphs.r_demand"), "Demanda R", "R demand", 3, 0x00A000 },
    { SC3KEY("graphs.c_demand"), "Demanda C", "C demand", 3, 0x2040E0 },
    { SC3KEY("graphs.i_demand"), "Demanda I", "I demand", 3, 0xD0A000 },
    { SC3KEY("graphs.air_pollution"), "Contam. aire", "Air pollution", 4, 0x707070 },
    { SC3KEY("graphs.water_pollution"), "Contam. agua", "Water pollution", 4, 0x2060C0 },
    /* graphtabs 2026-11-02 */
    { SC3KEY("graphs.power_used"), "Energ\xed""a consumo", "Power used", 1, 0x20A0A0 },
    { SC3KEY("graphs.r_tax"), "Impuesto R", "R tax", 5, 0x00A000 },
    { SC3KEY("graphs.c_tax"), "Impuesto C", "C tax", 5, 0x2040E0 },
    { SC3KEY("graphs.i_tax"), "Impuesto I", "I tax", 5, 0xD0A000 },
    { SC3KEY("graphs.debt"), "Deuda", "Debt", 6, 0xC03030 },
    { SC3KEY("graphs.jobs"), "Empleos", "Jobs", 7, 0x2060C0 },
    { SC3KEY("graphs.workers"), "Trabajadores", "Workers", 7, 0xC07020 },
    { SC3KEY("graphs.school_pupils"), "Escuela alumnos", "School pupils", 8, 0x2060C0 },
    { SC3KEY("graphs.school_capacity"), "Escuela capacidad", "School capacity", 8, 0x909090 },
    { SC3KEY("graphs.college_students"), "Univ. alumnos", "College students", 9, 0x7040C0 },
    { SC3KEY("graphs.college_capacity"), "Univ. capacidad", "College capacity", 9, 0x909090 },
    { SC3KEY("graphs.patients"), "Pacientes", "Patients", 10, 0xD02020 },
    { SC3KEY("graphs.hospital_capacity"), "Hosp. capacidad", "Hospital capacity", 10, 0x909090 },
    { SC3KEY("graphs.garbage_made"), "Basura producida", "Garbage made", 11, 0x806020 },
    { SC3KEY("graphs.to_landfill"), "Al vertedero", "To landfill", 11, 0xC07020 },
    { SC3KEY("graphs.recycled"), "Reciclada", "Recycled", 11, 0x20A040 },
    { SC3KEY("graphs.incinerated"), "Incinerada", "Incinerated", 11, 0xD02020 },
    { SC3KEY("graphs.exported"), "Exportada", "Exported", 11, 0x2060C0 },
    { SC3KEY("graphs.unpowered"), "Sin energ\xed""a", "Unpowered", 12, 0xE09000 },
    { SC3KEY("graphs.abandoned"), "Abandonados", "Abandoned", 13, 0x806040 } };
static const SC3TXT k_gn_grp[GN_GROUPS] = {
    { SC3KEY("graphs.grp_income_expenses"), "Ingresos/Gastos", "Income/Expenses" },
    { SC3KEY("graphs.grp_power_sup_dem"), "Energ\xed""a of./dem.", "Power sup./dem." },
    { SC3KEY("graphs.grp_water_sup_deliv"), "Agua of./entreg.", "Water sup./deliv." },
    { SC3KEY("graphs.grp_rci_demand"), "Demanda RCI", "RCI demand" },
    { SC3KEY("graphs.grp_air_water_pollut"), "Contam. aire/agua", "Air/water pollut." },
    { SC3KEY("graphs.grp_tax_rates"), "Impuestos", "Tax rates" },
    { SC3KEY("graphs.grp_debt_bonds"), "Deuda (bonos)", "Debt (bonds)" },
    { SC3KEY("graphs.grp_jobs_workers"), "Empleos/Trab.", "Jobs/Workers" },
    { SC3KEY("graphs.grp_schools"), "Escuelas", "Schools" },
    { SC3KEY("graphs.grp_colleges"), "Universidades", "Colleges" },
    { SC3KEY("graphs.grp_hospitals"), "Hospitales", "Hospitals" },
    { SC3KEY("graphs.grp_garbage"), "Basura", "Garbage" },
    { SC3KEY("graphs.grp_unpowered"), "Sin energ\xed""a", "Unpowered" },
    { SC3KEY("graphs.grp_abandoned"), "Abandonados", "Abandoned" } };
static const int   k_gn_lead[GN_GROUPS] = { 0, 2, 4, 6, 9, 12, 15, 16, 18, 20, 22, 24, 29, 30 };

/* the tabs, by checkbox id: stock ids measured 2026-11-02 (GRAPHNEW entry log, Berlin), ours = the group's lead line.
   A stock id that is in no tab (none known) goes to the last tab. */
static const SC3TXT k_tabtx[GN_TABS] = {
    { SC3KEY("graphs.tab_city"), "Ciudad", "City" }, { SC3KEY("graphs.tab_economy"), "Econom\xed""a", "Economy" },
    { SC3KEY("graphs.tab_services"), "Servicios", "Services" },
    { SC3KEY("graphs.tab_utilities"), "Redes", "Utilities" },
    { SC3KEY("graphs.tab_environment"), "Ambiente", "Environment" } };
static const DWORD k_tab[GN_TABS][12] = {
    { 0x4308EADB /* Tamano */, 0x0349A4CB /* Poblacion */, 0x0303E40D /* Residentes */, 0x8308EC75 /* Comercio */,
      0xA308EC84 /* Industria */, 0xA308EC96 /* Desempleo */, GN_ID0 + 16 /* Empleos */, GN_ID0 + 6 /* Demanda RCI */,
      GN_ID0 + 30 /* Abandonados */, 0 },
    { 0x630536CB /* Fondos */, GN_ID0 + 0 /* Ingresos/Gastos */, GN_ID0 + 12 /* Impuestos */, GN_ID0 + 15 /* Deuda */,
      0xC3080BED /* Valor del Terreno */, 0 },
    { 0x4303E4E7 /* Educacion */, 0x6303E4F7 /* Salud */, GN_ID0 + 18 /* Escuelas */, GN_ID0 + 20 /* Universidades */,
      GN_ID0 + 22 /* Hospitales */, 0x43092C78 /* Crimen */, 0x0259C03F /* Aprobacion */, 0 },
    { 0xE0AFDF68 /* Energia % */, GN_ID0 + 2 /* Energia of./dem. */, GN_ID0 + 29 /* Sin energia */, 0x02BF0033 /* Agua % */,
      GN_ID0 + 4 /* Agua of./entreg. */, 0x029CA804 /* Trafico */, 0 },
    { 0xE3079EF9 /* Polucion */, GN_ID0 + 9 /* Contam. aire/agua */, GN_ID0 + 24 /* Basura */, 0 } };

static DWORD g_gn_off[GN_GROUPS];      /* stored = real + off (R/C/I demand can be negative), set in gn_make */
static BYTE *g_gn_if[GN_LINES];        /* interface (object + 8), one reference held for the session */
static int   g_gn_on[GN_GROUPS];       /* group checkbox state, sc3resize.ini [graphs] */
static int   g_gn_tab;                 /* current tab, sc3resize.ini [graphs] tab */
static int   g_gn_last = -1;           /* year * 12 + closed month index of the last push */
static int   g_gn_synced;
static int   g_gn_es = 1;
static void *g_orig_f8fd, *g_orig_e012, *g_orig_eb59, *g_orig_7d88, *g_orig_save, *g_orig_df5b;
typedef struct { void *p; DWORD id; } GN_STK;
static GN_STK g_gn_stk[48];            /* stock series -> its real checkbox id */
static int    g_gn_nstk;

static void gn_sync(void *cal);   /* below */
static void tm_install(void); static void tm_month(int key);   /* VDBARS (sc3resize_vdbars.c) */
static void gn_fmt_real(char *o, double v);
static int gn_line_of(const void *p) { int i; for (i = 0; i < GN_LINES; i++) if (g_gn_if[i] && (void *)g_gn_if[i] == p) return i; return -1; }

/* GRAPHAXIS asks: is this series one of ours? group key and real = stored * mul + add */
static int gn_xform(const void *p, DWORD *key, double *mul, double *add) {
    int i = gn_line_of(p);
    if (i < 0) return 0;
    *key = GN_ID0 + 0x100 + k_gn[i].grp; *mul = 1.0; *add = -(double)g_gn_off[k_gn[i].grp];
    return 1;
}

/* a two-slot cIGZString for the class's string setters (they read vt+0x18 data and vt+0x1c length [CONFIRMED @ SIMMISC
   0x1000c53a]) */
typedef struct { void **vt; const char *p; DWORD n; } GN_STR;
static const char *__fastcall gn_s_data(GN_STR *s) { return s->p; }
static DWORD __fastcall gn_s_len(GN_STR *s) { return s->n; }
static void *g_gn_svt[8];
static GN_STR *gn_str(GN_STR *s, const char *t) {
    g_gn_svt[6] = (void *)gn_s_data; g_gn_svt[7] = (void *)gn_s_len;
    s->vt = g_gn_svt; s->p = t; s->n = (DWORD)lstrlenA(t);
    return s;
}

static void gn_ini(int save) {
    char p[MAX_PATH], k[16], v[8];
    int g;
    ho_ini_path(p, sizeof(p));
    for (g = 0; g < GN_GROUPS; g++) {
        wsprintfA(k, "on%d", g);
        if (save) { wsprintfA(v, "%d", g_gn_on[g] ? 1 : 0); WritePrivateProfileStringA("graphs", k, v, p); }
        else g_gn_on[g] = GetPrivateProfileIntA("graphs", k, 0, p) ? 1 : 0;
    }
    if (save) { wsprintfA(v, "%d", g_gn_tab); WritePrivateProfileStringA("graphs", "tab", v, p); }
    else { g_gn_tab = (int)GetPrivateProfileIntA("graphs", "tab", 0, p); if (g_gn_tab < 0 || g_gn_tab >= GN_TABS) g_gn_tab = 0; }
}

/* every ring of line i to the fill value (offset), scale back to the start value */
static void gn_reset_line(int i) {
    DWORD a[12], f = g_gn_off[k_gn[i].grp];
    int k;
    for (k = 0; k < 12; k++) a[k] = f;
    ho_v(g_gn_if[i], 0x60, 1, f ? 2 * f : 10, 0, 0, 0, 0);
    ho_v(g_gn_if[i], 0x70, 1, (DWORD)a, 0, 0, 0, 0);
    ho_v(g_gn_if[i], 0x78, 1, (DWORD)a, 0, 0, 0, 0);
    ho_v(g_gn_if[i], 0x80, 1, (DWORD)a, 0, 0, 0, 0);
}

static void gn_label(int i, const char *val) {
    GN_STR s;
    char t[96];
    int m;
    wsprintfA(t, "%s\n%s", sc3lang_tr(g_gn_es, k_gn[i].key, k_gn[i].es, k_gn[i].en), val);
    for (m = 0; m < 3; m++) ho_v(g_gn_if[i], 0x50, 2, (DWORD)m, (DWORD)gn_str(&s, t), 0, 0, 0);
}

static int gn_make(void) {
    static int done;
    HMODULE mi = GetModuleHandleA("SIMMISC.DLL");
    GN_STR s;
    DWORD a[1], id;
    int i, g;
    if (done) return done > 0;
    done = -1;
    if (!mi) return 0;
    g_gn_es = ho_spanish();
    g_gn_off[3] = 1000;                         /* R/C/I demand -1000..1000 (the HUD bar), stored + 1000 */
    for (i = 0; i < GN_LINES; i++) {
        BYTE *mem = (BYTE *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, 0x100);   /* never freed: we keep a reference */
        if (!mem) return 0;
        g = k_gn[i].grp;
        a[0] = g_gn_off[g];
        rz_thiscall_ret(mem, (BYTE *)mi + 0x33556, a, 1);
        g_gn_if[i] = mem + 8;
        ho_v(g_gn_if[i], 0x04, 0, 0, 0, 0, 0, 0);                                        /* AddRef, kept */
        ho_v(g_gn_if[i], 0x4c, 1, (DWORD)gn_str(&s, k_gn_lead[g] == i ? sc3lang_txt(g_gn_es, &k_gn_grp[g])
                                                     : (sc3lang_tr(g_gn_es, k_gn[i].key, k_gn[i].es, k_gn[i].en))), 0, 0, 0, 0);
        id = GN_ID0 + i;          ho_v(g_gn_if[i], 0x54, 1, (DWORD)&id, 0, 0, 0, 0);
        id = GN_ID0 + 0x40 + i;   ho_v(g_gn_if[i], 0x58, 1, (DWORD)&id, 0, 0, 0, 0);
        ho_v(g_gn_if[i], 0x5c, 1, k_gn[i].rgb, 0, 0, 0, 0);
        ho_v(g_gn_if[i], 0x64, 1, 0, 0, 0, 0, 0);                                        /* fixed scale, set by us */
        gn_reset_line(i);
        gn_label(i, "-");
    }
    gn_ini(0);
    done = 1;
    logf("GRAPHNEW> %d series made (SIMMISC class), %d graphs, tab %d", GN_LINES, GN_GROUPS, g_gn_tab);
    return 1;
}

/* ---------------------------------------------------------------------------------------------- the page */
typedef DWORD (__fastcall *GN_PAGEFN)(void *self, void *edx, DWORD a);
typedef DWORD (__fastcall *GN_PAGEFN2)(void *self, void *edx, DWORD a, DWORD b);

static DWORD gn_series_id(void *p) {
    DWORD *idp = (DWORD *)ho_v(p, 0x14, 0, 0, 0, 0, 0, 0);
    return idp && !IsBadReadPtr(idp, 4) ? *idp : 0;
}
static void gn_set_id(void *p, DWORD id) { ho_v(p, 0x54, 1, (DWORD)&id, 0, 0, 0, 0); }
static int gn_stk_of(const void *p) { int k; for (k = 0; k < g_gn_nstk; k++) if (g_gn_stk[k].p == p) return k; return -1; }

/* tab of a checkbox id; a stock id in no tab goes to the last tab */
static int gn_tab_of(DWORD cbid) {
    int t, j;
    for (t = 0; t < GN_TABS; t++) for (j = 0; j < 12 && k_tab[t][j]; j++) if (k_tab[t][j] == cbid) return t;
    return GN_TABS - 1;
}
static int gn_tab_of_entry(void *p) {
    int i = gn_line_of(p), k;
    if (i >= 0) return gn_tab_of(GN_ID0 + k_gn_lead[k_gn[i].grp]);
    k = gn_stk_of(p);
    return gn_tab_of(k >= 0 ? g_gn_stk[k].id : gn_series_id(p));
}

static DWORD __fastcall gn_enum(BYTE *page, void *edx, DWORD city, DWORD a2) {   /* page vt+0x20, ret 8: 2 args */
    HMODULE sui = GetModuleHandleA("SIMUI.DLL");
    DWORD r = ((GN_PAGEFN2)g_orig_f8fd)(page, edx, city, a2), a[1];
    BYTE *e, *v0, *v1;
    int i, n = 0, k;
    if (!gn_make()) return r;
    __try { gn_sync(((void *(__cdecl *)(void))((BYTE *)sui + 0x8e7da))()); }   /* a load since the last look: read its history now */
    __except (EXCEPTION_EXECUTE_HANDLER) { logf("GRAPHNEW> history check threw 0x%08lX", GetExceptionCode()); }
    /* stock series: remember the real id (or give it back, if a page went away without our close) */
    v0 = *(BYTE **)(page + 0x68); v1 = *(BYTE **)(page + 0x6c);
    for (e = v0; e && e < v1; e += 8) {
        void *p = *(void **)(e + 4);
        if (gn_line_of(p) >= 0) continue;
        if ((k = gn_stk_of(p)) >= 0) { if (gn_series_id(p) != g_gn_stk[k].id) gn_set_id(p, g_gn_stk[k].id); }
        else if (g_gn_nstk < 48) { g_gn_stk[g_gn_nstk].p = p; g_gn_stk[g_gn_nstk].id = gn_series_id(p); g_gn_nstk++; }
    }
    for (i = 0; i < GN_LINES; i++) {
        int have = 0;
        v0 = *(BYTE **)(page + 0x68); v1 = *(BYTE **)(page + 0x6c);
        for (e = v0; e && e < v1; e += 8) if (*(BYTE **)(e + 4) == g_gn_if[i]) have = 1;
        if (have) continue;
        gn_set_id(g_gn_if[i], GN_ID0 + i);   /* real id back for the layout */
        a[0] = (DWORD)g_gn_if[i];
        rz_thiscall_ret(page + 0x64, (BYTE *)sui + 0x2f8c7, a, 1);
        n++;
    }
    logf("GRAPHNEW> page 0x%08lX: %d series added to the list (%d entries, %d stock)", (DWORD)page, n,
         (int)((*(BYTE **)(page + 0x6c) - *(BYTE **)(page + 0x68)) / 8), g_gn_nstk);
    return r;
}

static void *gn_cbox(void *win, DWORD id) {   /* the checkbox interface (IID 0x8810), released by the caller */
    void *cb = NULL;
    if (!(ho_v(win, 0x80, 3, id, 0x8810, (DWORD)&cb, 0, 0) & 0xff)) return NULL;
    return cb;
}
static int gn_cb_state(void *win, DWORD id) {   /* -1 = no such checkbox */
    void *cb = gn_cbox(win, id);
    int on;
    if (!cb) return -1;
    on = (ho_v(cb, 0x38, 0, 0, 0, 0, 0, 0) & 0xff) ? 1 : 0;
    ho_v(cb, 0x08, 0, 0, 0, 0, 0, 0);
    return on;
}

/* a checkbox off the current tab: hidden AND moved far below the page. Hidden alone still took clicks: measured
   2026-11-02, a click on the Redes tab's first-row cell toggled Salud, hidden there from the Servicios tab. */
static void gn_park(BYTE *w) {
    gx_show(w, 0);
    ho_v(w, 0xcc, 2, 20, 4000, 0, 0, 0);
}

/* show the checkboxes of tab t at their cells, hide every other one (ours and stock) */
static void gn_place_tab(BYTE *page, void *win, int t) {
    BYTE *e, *v0, *v1, *w;
    int j, n = 0, extra = 0;
    DWORD cb;
    v0 = *(BYTE **)(page + 0x68); v1 = *(BYTE **)(page + 0x6c);
    for (e = v0; e && e < v1 && !IsBadReadPtr(e, 8); e += 8) {   /* hide all */
        void *p = *(void **)(e + 4);
        int i = gn_line_of(p), k = gn_stk_of(p);
        cb = i >= 0 ? GN_ID0 + i : k >= 0 ? g_gn_stk[k].id : gn_series_id(p);
        if ((w = (BYTE *)mp_child(win, cb))) gn_park(w);
    }
    for (j = 0; j < 12 && k_tab[t][j]; j++) {
        if (!(w = (BYTE *)mp_child(win, k_tab[t][j]))) continue;
        ho_v(w, 0xcc, 2, (DWORD)(20 + 120 * (n % 3)), (DWORD)(230 + 24 * (n / 3)), 0, 0, 0);
        gx_show(w, 1);
        n++;
    }
    if (t == GN_TABS - 1)                                         /* stock ids in no tab */
        for (j = 0; j < g_gn_nstk && n < 12; j++) {
            int tt, jj, known = 0;
            for (tt = 0; tt < GN_TABS && !known; tt++) for (jj = 0; jj < 12 && k_tab[tt][jj]; jj++) if (k_tab[tt][jj] == g_gn_stk[j].id) known = 1;
            if (known || !(w = (BYTE *)mp_child(win, g_gn_stk[j].id))) continue;
            ho_v(w, 0xcc, 2, (DWORD)(20 + 120 * (n % 3)), (DWORD)(230 + 24 * (n / 3)), 0, 0, 0);
            gx_show(w, 1);
            n++; extra++;
        }
    /* vt+0xcc writes only the LOCAL rect; hit-testing uses the derived rect +0x14, rebuilt by vt+0x168 / vt+0x14c (this
       window and every child) [CONFIRMED @ SIMUI 0x1006c61b, 0x1006d4eb]. Without this the first click after a tab
       switch went to the old place of the checkbox (measured 2026-11-02: lost), then vt+0x154 marks the page dirty. */
    ho_v(win, 0x168, 0, 0, 0, 0, 0, 0);
    ho_v(win, 0x14c, 0, 0, 0, 0, 0, 0);
    ho_v(win, 0x154, 0, 0, 0, 0, 0, 0);
    logf("GRAPHNEW> page 0x%08lX tab %d: %d checkboxes shown%s", (DWORD)page, t, n, extra ? " (some not in any tab)" : "");
}

static int g_gn_placed = -1;   /* tab whose checkboxes are placed on the current page window */
static void *g_gn_placed_win;

/* before the renderer: the tab from its radio group, then every entry's id / on byte */
static void gn_pre_render(BYTE *page, void *win) {
    BYTE *e, *v0, *v1;
    int g, i, ch = 0, k;
    if (!g_gn_if[0] || !page || IsBadReadPtr(page, 0x70)) return;
    for (g = 0; g < GN_GROUPS; g++) {
        int on = gn_cb_state(win, GN_ID0 + k_gn_lead[g]);
        if (on >= 0 && on != g_gn_on[g]) { g_gn_on[g] = on; ch = 1; }
    }
    if (g_graphtabs) {
        void *o = NULL;
        if ((ho_v(win, 0x80, 3, GN_TABGRP, 0xa1336cc0, (DWORD)&o, 0, 0) & 0xff) && o) {
            DWORD s = ho_v(o, 0x30, 0, 0, 0, 0, 0, 0);
            ho_v(o, 0x08, 0, 0, 0, 0, 0, 0);
            if (s > GN_TABGRP && s <= GN_TABGRP + GN_TABS && (int)(s - GN_TABGRP - 1) != g_gn_tab) { g_gn_tab = (int)(s - GN_TABGRP - 1); ch = 1; }
        }
        if (g_gn_placed_win == win && g_gn_placed != g_gn_tab) { gn_place_tab(page, win, g_gn_tab); g_gn_placed = g_gn_tab; }
    }
    if (ch) gn_ini(1);   /* kept at once, not only on close */
    if (g_gn_log) {   /* every checkbox's state, logged when it changes */
        static char last[160];
        char st[160];
        int n = 0;
        for (k = 0; k < g_gn_nstk && n < 60; k++) { int s = gn_cb_state(win, g_gn_stk[k].id); st[n++] = s < 0 ? '-' : (char)('0' + s); }
        st[n++] = '|';
        for (g = 0; g < GN_GROUPS; g++) { int s = gn_cb_state(win, GN_ID0 + k_gn_lead[g]); st[n++] = s < 0 ? '-' : (char)('0' + s); }
        wsprintfA(st + n, " tab %d", g_gn_tab);
        if (lstrcmpA(st, last)) { lstrcpyA(last, st); logf("GRAPHNEW> boxes %s", st); }
    }
    v0 = *(BYTE **)(page + 0x68); v1 = *(BYTE **)(page + 0x6c);
    for (e = v0, k = 0; e && e < v1 && !IsBadReadPtr(e, 8); e += 8, k++) {
        void *p = *(void **)(e + 4);
        int here = !g_graphtabs || g_gn_placed_win != win || gn_tab_of_entry(p) == g_gn_tab;
        if ((i = gn_line_of(p)) >= 0) {
            g = k_gn[i].grp;
            if (k_gn_lead[g] != i) e[0] = (BYTE)(g_gn_on[g] && here);           /* id is the dummy since the layout */
            else if (here) gn_set_id(p, GN_ID0 + i);                            /* the renderer reads the checkbox */
            else { gn_set_id(p, GN_ID0 + 0x80 + i); e[0] = 0; }
        } else if (g_graphtabs && (i = gn_stk_of(p)) >= 0) {
            if (here) gn_set_id(p, g_gn_stk[i].id);
            else { gn_set_id(p, GN_STKDUMMY + (DWORD)i); e[0] = 0; }
        }
    }
}

static DWORD __fastcall gn_layout(BYTE *page, void *edx, DWORD win) {
    HMODULE sui = GetModuleHandleA("SIMUI.DLL");
    DWORD r = ((GN_PAGEFN)g_orig_e012)(page, edx, win), ids[GN_TABS];
    const char *tx[GN_TABS];
    int i, g, t, ok = 0;
    if (!g_gn_if[0] || !win) return r;
    for (i = 0; i < GN_LINES; i++) {
        BYTE *w = (BYTE *)mp_child((void *)win, GN_ID0 + i);
        g = k_gn[i].grp;
        if (!w || IsBadReadPtr(w, 0xa4)) { logf("GRAPHNEW> no checkbox for line %d", i); continue; }
        if (k_gn_lead[g] == i) {
            void *cb;
            if ((cb = gn_cbox((void *)win, GN_ID0 + i))) { ho_v(cb, 0x34, 1, (DWORD)g_gn_on[g], 0, 0, 0, 0); ho_v(cb, 0x08, 0, 0, 0, 0, 0, 0); }
        } else {
            gn_park(w);
            gn_set_id(g_gn_if[i], GN_ID0 + 0x80 + i);   /* the renderer's lookup misses */
        }
    }
    if (g_graphtabs && g_vdtabs) {   /* VDTABS: drawn tabs hanging under the chart (child 6), not a radio row */
        void *fac = ((void *(__cdecl *)(void))((BYTE *)sui + 0x85065))();
        BYTE *ch = (BYTE *)mp_child((void *)win, 6);
        int x0 = 6, x1 = 380, y = 198;
        if (ch && !IsBadReadPtr(ch, 0x90) && *(BYTE **)(ch + 0x3c) == (BYTE *)win) {
            x0 = *(LONG *)(ch + 0x80); x1 = *(LONG *)(ch + 0x88); y = *(LONG *)(ch + 0x8c) - 1;
        }
        for (t = 0; t < GN_TABS; t++) tx[t] = sc3lang_txt(g_gn_es, &k_tabtx[t]);
        if (fac && !IsBadReadPtr(fac, 4) && !mp_child((void *)win, GT_ID0 + 1))
            ok = tb_make(fac, (void *)win, &g_gt_tb, GT_ID0, tx, GN_TABS, g_gn_tab, x0, x1, y, 18);
        g_gn_placed_win = (void *)win;
        gn_place_tab(page, (void *)win, g_gn_tab);
        g_gn_placed = g_gn_tab;
        logf("GRAPHNEW> page 0x%08lX laid out: drawn tabs %s (chart bottom %d, x %d..%d), tab %d", (DWORD)page, ok ? "added" : "NOT added", y, x0, x1, g_gn_tab);
    } else if (g_graphtabs) {
        void *fac = ((void *(__cdecl *)(void))((BYTE *)sui + 0x85065))();
        if (fac && !IsBadReadPtr(fac, 4) && !mp_child((void *)win, GN_TABGRP)) {
            DWORD col = ho_v((void *)win, 0x184, 3, 0x31, 0x34, 0x7b, 0, 0);   /* the range group's colour (SIMUI 0x1002e6cb) */
            for (t = 0; t < GN_TABS; t++) { ids[t] = GN_TABGRP + 1 + t; tx[t] = sc3lang_txt(g_gn_es, &k_tabtx[t]); }
            ok = mp_group(fac, (void *)win, GN_TABGRP, ids, tx, GN_TABS, GN_TABGRP + 1 + g_gn_tab, 14, 205, 360, col);
        }
        g_gn_placed_win = (void *)win;
        gn_place_tab(page, (void *)win, g_gn_tab);
        g_gn_placed = g_gn_tab;
        logf("GRAPHNEW> page 0x%08lX laid out: tabs %s, tab %d", (DWORD)page, ok ? "added" : "NOT added", g_gn_tab);
    } else {
        /* the 10-30 grid: group checkboxes in free cells of rows 5..9 (columns 0 / 1) */
        for (g = 0; g < GN_GROUPS; g++) {
            BYTE *w = (BYTE *)mp_child((void *)win, GN_ID0 + k_gn_lead[g]);
            int c = (g + 1) % 2, rw = 5 + (g + 1) / 2;
            if (w) ho_v(w, 0xcc, 2, (DWORD)(20 + 120 * c), (DWORD)(210 + 24 * rw), 0, 0, 0);
        }
    }
    gx_render(page, NULL, win);   /* redraw with the group states and the tab (the original drew before) */
    return r;
}

/* the page's control handler (vtable 0x100a4fe8 +0xc, this = page + 4). A radio pick arrives as message 3, p3 3, p4 =
   the group id, and the original re-renders only when that group's selection is 3..5 (the range radios) [CONFIRMED @
   SIMUI 0x1002df5b], so a tab pick changed the radio and nothing else until the next click, which then hit the old
   tab's checkbox (measured 2026-11-02). After the original: our group -> render (pre_render places the tab). */
typedef DWORD (__fastcall *GN_CTLFN)(void *self, void *edx, DWORD win, DWORD msg, DWORD p3, DWORD id, DWORD p5);
static DWORD __fastcall gn_ctl(BYTE *self, void *edx, DWORD win, DWORD msg, DWORD p3, DWORD id, DWORD p5) {
    DWORD r;
    int tt;
    if (msg == 3 && p3 == 1 && g_graphtabs && g_vdtabs && g_gn_if[0] && win && (tt = tb_hit(&g_gt_tb, (void *)win, id)) >= 0) {
        __try {   /* VDTABS: a tab click (button message) -> select, redraw the strip, render (pre_render places the tab) */
            if (tt != g_gn_tab) { g_gn_tab = tt; gn_ini(1); }
            g_gt_tb.sel = tt;
            tb_draw(&g_gt_tb);
            gx_render(self - 4, NULL, win);
        } __except (EXCEPTION_EXECUTE_HANDLER) { logf("GRAPHNEW> tab click threw 0x%08lX", GetExceptionCode()); }
        return 1;
    }
    r = ((GN_CTLFN)g_orig_df5b)(self, edx, win, msg, p3, id, p5);
    if (msg == 3 && (p3 == 1 || p3 == 3) && g_graphtabs && g_gn_if[0] && win &&
        (id == GN_TABGRP || (id > GN_TABGRP && id <= GN_TABGRP + GN_TABS))) {
        __try { gx_render(self - 4, NULL, win); }
        __except (EXCEPTION_EXECUTE_HANDLER) { logf("GRAPHNEW> tab render threw 0x%08lX", GetExceptionCode()); }
        r = (r & ~0xffu) | 1;
    }
    return r;
}

static void __fastcall gn_close(BYTE *page, void *edx, DWORD win) {
    BYTE *v0, *v1, *e, *o;
    int n = 0, k, on;
    if (g_gn_if[0] && page && !IsBadReadPtr(page, 0x70)) {
        gn_pre_render(page, (void *)win);
        gn_ini(1);
        v0 = *(BYTE **)(page + 0x68); v1 = *(BYTE **)(page + 0x6c);
        for (e = o = v0; e && e < v1; e += 8) {
            void *p = *(void **)(e + 4);
            if (gn_line_of(p) >= 0) { ho_v(p, 0x08, 0, 0, 0, 0, 0, 0); n++; continue; }   /* the list's reference */
            if ((k = gn_stk_of(p)) >= 0) {                   /* real id + checkbox state back, for the game prefs */
                gn_set_id(p, g_gn_stk[k].id);
                if ((on = gn_cb_state((void *)win, g_gn_stk[k].id)) >= 0) e[0] = (BYTE)on;
            }
            if (o != e) memcpy(o, e, 8);
            o += 8;
        }
        if (v0) *(BYTE **)(page + 0x6c) = o;
        if (g_gn_placed_win == (void *)win) { g_gn_placed_win = NULL; g_gn_placed = -1; }
        if (g_gt_tb.win == (void *)win) g_gt_tb.win = NULL, g_gt_tb.n = 0;
        logf("GRAPHNEW> page 0x%08lX closing: %d series taken out before the game saves its prefs", (DWORD)page, n);
    }
    ((GN_PAGEFN)g_orig_eb59)(page, edx, win);
}

/* ---------------------------------------------------------------------------------------------- city + history file */
static BYTE *gn_city(void) {
    HMODULE sc = GetModuleHandleA("SIMCITY.DLL");
    BYTE *app, *city;
    if (!sc) return NULL;
    __try {
        app = *(BYTE **)((BYTE *)GetModuleHandleA(NULL) + 0xfa86c);   /* sc3autosave city_get */
        city = app ? *(BYTE **)(app + 0x48) : NULL;
        if (!city || *(DWORD *)city != (DWORD)sc + 0x13260) return NULL;
        return city;
    } __except (EXCEPTION_EXECUTE_HANDLER) { return NULL; }
}
static int gn_city_name(BYTE *city, char *out, int cap) {
    BYTE *s;
    char *b, *e;
    out[0] = 0;
    if (!city) return 0;
    __try {
        s = (BYTE *)ho_v(city, 0x254, 0, 0, 0, 0, 0, 0);   /* SIMCITY 0x10007116 -> city+0x15c */
        b = *(char **)(s + 4); e = *(char **)(s + 8);
        if (!b || e <= b || e - b >= cap) return 0;
        memcpy(out, b, e - b); out[e - b] = 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) { out[0] = 0; return 0; }
    return 1;
}
/* closed-month key from a calendar object (vt+0x1e4(&month, &x, &year)), as FUN_10007d88 computes it */
static int gn_key(void *cal, int *ci, int *yr) {
    DWORD m = 0, x[4], y = 0;
    if (!cal) return -1;
    ho_v(cal, 0x1e4, 3, (DWORD)&m, (DWORD)x, (DWORD)&y, 0, 0);
    if (m == 1) { y--; m = 11; } else { m -= 2; if (m > 11) m = 11; }
    if (ci) *ci = (int)m;
    if (yr) *yr = (int)y;
    return (int)y * 12 + (int)m;
}

#define GN_MAGIC 0x47335353   /* "SS3G" */
typedef struct { DWORD magic, ver, key, n; } GN_HDR;
typedef struct { DWORD id, scale, m[12], y[10], d[10]; } GN_REC;
static GN_REC g_gn_snap[GN_LINES];
static int    g_gn_snapkey;
static FILETIME g_gn_savet;
static volatile LONG g_gn_writer;

static void gn_snapshot(void) {
    int i;
    for (i = 0; i < GN_LINES; i++) {
        g_gn_snap[i].id = GN_ID0 + i;
        g_gn_snap[i].scale = ho_v(g_gn_if[i], 0x20, 0, 0, 0, 0, 0, 0);
        ho_v(g_gn_if[i], 0x28, 1, (DWORD)g_gn_snap[i].m, 0, 0, 0, 0);
        ho_v(g_gn_if[i], 0x34, 1, (DWORD)g_gn_snap[i].y, 0, 0, 0, 0);
        ho_v(g_gn_if[i], 0x40, 1, (DWORD)g_gn_snap[i].d, 0, 0, 0, 0);
    }
    g_gn_snapkey = g_gn_last;
}

static DWORD g_gn_snaptick;   /* GetTickCount of the last snapshot (0 = none) */

/* "<sc3>.graphs" from a snapshot (ver 2: GN_LINES records, each with its id; ver 1 had 11) */
static int gn_write_file(const char *sc3, const GN_REC *snap, int key) {
    char side[MAX_PATH + 8];
    HANDLE h;
    GN_HDR hd;
    DWORD w1 = 0, w2 = 0;
    wsprintfA(side, "%s.graphs", sc3);
    hd.magic = GN_MAGIC; hd.ver = 2; hd.key = (DWORD)key; hd.n = GN_LINES;
    h = CreateFileA(side, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) { logf("GRAPHNEW> cannot write %s (%lu)", side, GetLastError()); return 0; }
    WriteFile(h, &hd, sizeof(hd), &w1, NULL);
    WriteFile(h, snap, sizeof(GN_REC) * GN_LINES, &w2, NULL);
    CloseHandle(h);
    logf("GRAPHNEW> history written: %s (closed month key %d)", side, key);
    return w1 == sizeof(hd) && w2 == sizeof(GN_REC) * GN_LINES;
}

/* after a save: wait until the city's file carries the save's time (the save command may set the name after the city
   save routine returns), then write "<city file>.graphs". A file that did not change gets nothing: sc3autosave saves
   to a temp name and gives the city its old name back, and asks for its own copy through sc3resize_graphs_write. */
static DWORD WINAPI gn_writer(LPVOID arg) {
    char name[MAX_PATH];
    WIN32_FILE_ATTRIBUTE_DATA fa;
    ULARGE_INTEGER t0, t1;
    FILETIME seen = { 0, 0 };
    static GN_REC snap[GN_LINES];
    int tries, key;
    (void)arg;
    for (tries = 0; tries < 40; tries++) {
        Sleep(250);
        if (g_gn_savet.dwLowDateTime != seen.dwLowDateTime || g_gn_savet.dwHighDateTime != seen.dwHighDateTime) {
            seen = g_gn_savet; tries = 0;   /* a newer save while we wait: its time, a fresh 10 s */
        }
        t0.LowPart = seen.dwLowDateTime; t0.HighPart = seen.dwHighDateTime;
        if (!gn_city_name(gn_city(), name, sizeof(name))) continue;
        if (!GetFileAttributesExA(name, GetFileExInfoStandard, &fa)) continue;
        t1.LowPart = fa.ftLastWriteTime.dwLowDateTime; t1.HighPart = fa.ftLastWriteTime.dwHighDateTime;
        if (t1.QuadPart + 20000000ui64 < t0.QuadPart) continue;          /* older than the save (2 s slack) */
        memcpy(snap, g_gn_snap, sizeof(snap)); key = g_gn_snapkey;
        gn_write_file(name, snap, key);
        break;
    }
    InterlockedExchange(&g_gn_writer, 0);
    return 0;
}

typedef DWORD (__fastcall *GN_CITYFN)(void *self, void *edx, void *a);
static DWORD __fastcall gn_save(BYTE *city, void *edx, void *db) {
    FILETIME t;
    DWORD r;
    GetSystemTimeAsFileTime(&t);
    r = ((GN_CITYFN)g_orig_save)(city, edx, db);
    if ((r & 0xff) && g_gn_if[0] && g_gn_last >= 0) {
        gn_snapshot();                     /* every save, also while a writer still waits on an earlier one */
        g_gn_snaptick = GetTickCount();
        g_gn_savet = t;
        if (!InterlockedExchange(&g_gn_writer, 1)) {
            HANDLE th = CreateThread(NULL, 0, gn_writer, NULL, 0, NULL);
            if (th) CloseHandle(th); else InterlockedExchange(&g_gn_writer, 0);
        }
    }
    return r;
}

/* For sc3autosave (its GRAPHS block): write the history taken at the save that just ended next to `sc3`, the file that
   save went to. 1 = written. Refuses a snapshot older than 2 min (no save of ours ran just before). */
__declspec(dllexport) int sc3resize_graphs_write(const char *sc3) {
    static GN_REC snap[GN_LINES];
    if (!g_gn_if[0] || !g_gn_snaptick || !sc3 || IsBadStringPtrA(sc3, MAX_PATH)) return 0;
    if (GetTickCount() - g_gn_snaptick > 120000) { logf("GRAPHNEW> history for %s refused: no save in the last 2 min", sc3); return 0; }
    memcpy(snap, g_gn_snap, sizeof(snap));
    return gn_write_file(sc3, snap, g_gn_snapkey);
}

/* "<sc3>.graphs" into out[] by record id when it exists, is ours and was saved at closed month `key`; have[i] = 1 for
   each line found. Returns the number of lines read. */
static int gn_read_file(const char *sc3, int key, GN_REC *out, int *have, int *found_key) {
    char side[MAX_PATH + 8];
    HANDLE h;
    GN_HDR hd;
    GN_REC r;
    DWORD rd, k;
    int n = 0, i;
    *found_key = -1;
    wsprintfA(side, "%s.graphs", sc3);
    h = CreateFileA(side, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    if (h == INVALID_HANDLE_VALUE) return 0;
    if (ReadFile(h, &hd, sizeof(hd), &rd, NULL) && rd == sizeof(hd) && hd.magic == GN_MAGIC && (hd.ver == 1 || hd.ver == 2) &&
        hd.n >= 1 && hd.n <= 64) {
        *found_key = (int)hd.key;
        if ((int)hd.key == key)
            for (k = 0; k < hd.n; k++) {
                if (!ReadFile(h, &r, sizeof(r), &rd, NULL) || rd != sizeof(r)) break;
                i = (int)(r.id - GN_ID0);
                if (i < 0 || i >= GN_LINES) continue;
                out[i] = r; have[i] = 1; n++;
            }
    }
    CloseHandle(h);
    return n;
}

/* ---------------------------------------------------------------------------------------------- reading the city */
typedef struct {
    BYTE *city, *budget, *pw, *wa, *po, *res, *zone;   /* pw = power iface (base + 0x14), po = SIMECO iface (base + 0x1c) */
    void *vl;                                          /* valve layer, released by gn_ctx_free */
} GN_CTX;

static void gn_ctx(GN_CTX *c, BYTE *budget) {
    HMODULE sui = GetModuleHandleA("SIMUI.DLL"), ut = GetModuleHandleA("SIMUTIL.DLL"), eco = GetModuleHandleA("SIMECO.DLL"),
            mi = GetModuleHandleA("SIMMISC.DLL"), rci = GetModuleHandleA("SIMRCI.DLL");
    BYTE *p;
    void *L;
    memset(c, 0, sizeof(*c));
    if (!sui) return;
    c->city = (BYTE *)((void *(__cdecl *)(void))((BYTE *)sui + 0x8e7da))();
    if (!c->city) return;
    /* budget: the monthly function's own pointer, else city vt+0x15c (vtable SIMMISC 0x1003c550) */
    p = budget ? budget : (BYTE *)ho_v(c->city, 0x15c, 0, 0, 0, 0, 0, 0);
    if (p && mi && !IsBadReadPtr(p, 0x5a0) && *(DWORD *)p == (DWORD)mi + 0x3c550) c->budget = p;
    p = (BYTE *)ho_v(c->city, 0x150, 0, 0, 0, 0, 0, 0);
    if (p && ut && !IsBadReadPtr(p - 0x14, 0x300) && *(DWORD *)p == (DWORD)ut + 0x20550) c->pw = p;
    p = (BYTE *)ho_v(c->city, 0x154, 0, 0, 0, 0, 0, 0);
    if (p && ut && !IsBadReadPtr(p, 0xc0) && *(DWORD *)p == (DWORD)ut + 0x22944) c->wa = p;
    p = (BYTE *)ho_v(c->city, 0x16c, 0, 0, 0, 0, 0, 0);
    if (p && eco && !IsBadReadPtr(p - 0x1c, 0x4a0) && *(DWORD *)p == (DWORD)eco + 0x1b984) c->po = p;
    p = (BYTE *)ho_v(c->city, 0x17c, 0, 0, 0, 0, 0, 0);
    if (p && rci && !IsBadReadPtr(p, 4) && *(DWORD *)p == (DWORD)rci + 0x4c99c) c->res = p;
    p = (BYTE *)ho_v(c->city, 0x14c, 0, 0, 0, 0, 0, 0);
    if (p && rci && !IsBadReadPtr(p, 4) && *(DWORD *)p == (DWORD)rci + 0x4d1e0) c->zone = p;
    /* VALVEREF (2026-11-10, verify/crashguard): city vt+0x1b8 is cISC3City::GetSpecificLayer, a borrowed pointer (no
       AddRef: the RCTRACE run saw no AddRef from it). Only the QI reference is ours. The Release of L that stood here
       took one count off the valve layer per call (once a game month): Europolis 1024 starts at 100, so after ~100
       months the layer was destroyed under the sim thread (sc3_valvelayer_end_of_month, SIMRCI+0x312CC). */
    L = (void *)ho_v(c->city, 0x1b8, 1, 0x80f1e6d3, 0, 0, 0, 0);
    if (L && !(ho_v(L, 0x00, 2, 0x40a42f1c, (DWORD)&c->vl, 0, 0, 0) & 0xff)) c->vl = NULL;
}
static void gn_ctx_free(GN_CTX *c) { if (c->vl) ho_v(c->vl, 0x08, 0, 0, 0, 0, 0, 0); c->vl = NULL; }

static void *gn_valve(GN_CTX *c, DWORD id) {   /* released by the caller */
    void *va = NULL;
    if (!c->vl || !(ho_v(c->vl, 0x14, 3, id, 0xf1ec30, (DWORD)&va, 0, 0) & 0xff)) return NULL;
    return va;
}

typedef float (__fastcall *GN_FLOATFN)(void *self, void *edx);

/* budget income / expenses of closed month ci (ring slot ci) */
static BYTE *gn_next(BYTE *n);
static void gn_budget_month(BYTE *b, int ci, double *in, double *ex) {
    static const DWORD inc[8] = { 0x90, 0x118, 0x1a0, 0x3a0, 0x2d0, 0x470, 0x4e8, 0x338 }, exq[2] = { 0x268, 0x408 };
    BYTE *head, *n;
    int k, g = 0;
    *in = *ex = 0;
    for (k = 0; k < 8; k++) *in += (double)*(__int64 *)(b + inc[k] + ci * 8);
    for (k = 0; k < 2; k++) *ex += (double)*(__int64 *)(b + exq[k] + ci * 8);
    *ex += (double)*(LONG *)(b + 0x558 + ci * 4);
    head = *(BYTE **)(b + 0x60);
    if (head) for (n = *(BYTE **)(head + 8); n && n != head && g < 256; g++, n = gn_next(n)) *ex += (double)*(__int64 *)(n + 0x30 + ci * 8);
}

/* ---------------------------------------------------------------------------------------------- the 31 values
 * Read for the month that closed (index ci, as the record computes it). Sources (re/analysis/GRAPH_SERIES.md sections 7, 8):
 *  - income / expenses: budget int64 rings base + off + ci * 8. Income: taxes R/C/I +0x90 / +0x118 / +0x1a0, fares +0x3a0,
 *    ordinances +0x2d0, neighbour deals +0x470, business deals +0x4e8, disaster relief +0x338. Expenses: ordinances +0x268,
 *    neighbour deals +0x408, bonds (dword ring) +0x558 + ci * 4, departments: every node of the map at +0x60 (MSVC6 tree,
 *    successor FUN_10003354), ring node+0x30 + ci * 8 [CONFIRMED @ SIMMISC 0x10007d88, 0x10008a3e, 0x10008ced, 0x10008d54].
 *  - power: city vt+0x150 = SIMUTIL power iface (base + 0x14, vtable 0x10020550). Supply = base+0x70, served = base+0x74
 *    [CONFIRMED @ SIMUTIL 0x10004e57]. Demand = iface vt+0x5c = base+0x2ec, the running sum of the per-tile demand bytes
 *    [CONFIRMED @ SIMUTIL 0x100041ce, 0x10004340] (10-30 summed the bytes base+0x2dc itself: same number). Used = the
 *    newest row of the 12 x 10 ring base+0xcc (row base+0x2ac) [CONFIRMED @ SIMUTIL 0x10004c1f]. Unpowered tiles = iface
 *    vt+0x60 = max(0, demanding tiles - powered tiles).
 *  - water: city vt+0x154 = SIMUTIL plumbing layer. Supply = int64 base+0xb0 (pump capacity), delivered = int64 base+0xb8
 *    [CONFIRMED @ SIMUTIL 0x1000e8c4]. Unmet water demand is not kept anywhere.
 *  - R / C / I demand: city vt+0x1b8(0x80f1e6d3), QI 0x40a42f1c, vt+0x14(3000 / 5000 / 8000, 0xf1ec30, &valve), valve
 *    vt+0x30 value, +0x38 max, +0x3c min [CONFIRMED @ SIMUI 0x10026e40, 0x10065303], shown as the HUD bar sees it:
 *    v >= 0 ? v * 1000 / max : v * -1000 / min, -1000..1000 [CONFIRMED @ SIMRCI 0x10042e89].
 *  - pollution: city vt+0x16c = SIMECO iface, vt+0x78 air, vt+0x7c water, as % of vt+0x84 / +0x88 [CONFIRMED @ SIMECO
 *    0x10007b5d, 0x10008249].
 *  - taxes: budget vt+0x4c(i) = byte +0x8c + i * 0x88, i = 0..2, the block whose +4 is the tax income ring i
 *    [CONFIRMED @ SIMMISC 0x1000520b]; i = 0/1/2 = R/C/I [UNCERTAIN: order not tied to the budget window yet].
 *  - debt: int64 budget+0x590 (vt+0x60, bonds outstanding) [CONFIRMED @ SIMMISC 0x1000521f].
 *  - jobs / workers: the inputs of Desempleo [CONFIRMED @ SIMMISC 0x100285bb]: jobs = valve 7000 vt+0x2c, workers =
 *    trunc(valve 3000 vt+0x28 * res vt+0x7c (float)).
 *  - schools / colleges / hospitals: city vt+0x17c = SIMRCI residential iface (vtable 0x1004c99c): pupils vt+0x50 vs
 *    capacity vt+0x64, students vt+0x58 vs vt+0x68, patients vt+0x48 vs vt+0x60 (worker read 2026-11-02).
 *  - garbage: SIMECO base (iface - 0x1c) int64 rings, slot ci: made +0x1a8, exported +0x268, incinerated +0x328,
 *    recycled +0x388, to landfill +0x3e8 [CONFIRMED @ SIMECO 0x10007b5d]; names as LANDFILL.md.
 *  - abandoned tiles: city vt+0x14c = SIMRCI zone layer (vtable 0x1004d1e0) vt+0x54 [worker read, UNCERTAIN until the
 *    vtable check passes in a run]. */
static BYTE *gn_next(BYTE *n) {   /* FUN_10003354: left +8, parent +4, right +0xc, NULL leaves */
    BYTE *r = *(BYTE **)(n + 0xc), *p;
    if (r) { while (*(BYTE **)(r + 8)) r = *(BYTE **)(r + 8); return r; }
    p = *(BYTE **)(n + 4);
    while (p && n == *(BYTE **)(p + 0xc)) { n = p; p = *(BYTE **)(p + 4); }
    if (*(BYTE **)(n + 0xc) != p) n = p;
    return n;
}

static const DWORD k_gn_garb[5] = { 0x1a8, 0x3e8, 0x388, 0x328, 0x268 };   /* lines 24..28 */

static void gn_values(GN_CTX *c, int ci, double *v) {
    static const DWORD vid[3] = { 3000, 5000, 8000 };
    int k;
    char dbg[400];
    int n = 0;
    for (k = 0; k < GN_LINES; k++) v[k] = 0;
    dbg[0] = 0;
    if (c->budget) {
        gn_budget_month(c->budget, ci, &v[0], &v[1]);
        for (k = 0; k < 3; k++) v[12 + k] = (double)*(BYTE *)(c->budget + 0x8c + k * 0x88);
        v[15] = (double)*(__int64 *)(c->budget + 0x590);
    }
    if (c->pw) {
        BYTE *base = c->pw - 0x14;
        LONG row = *(LONG *)(base + 0x2ac);
        v[2] = *(LONG *)(base + 0x70);
        v[3] = (double)ho_v(c->pw, 0x5c, 0, 0, 0, 0, 0, 0);
        if (row >= 0 && row < 12) for (k = 0; k < 10; k++) v[11] += *(LONG *)(base + 0xcc + (row * 10 + k) * 4);
        v[29] = (double)ho_v(c->pw, 0x60, 0, 0, 0, 0, 0, 0);
        n += wsprintfA(dbg + n, "power supply %ld served %ld demand %ld used %ld unpowered %ld; ", *(LONG *)(base + 0x70),
                       *(LONG *)(base + 0x74), (LONG)v[3], (LONG)v[11], (LONG)v[29]);
    } else n += wsprintfA(dbg + n, "no power layer; ");
    if (c->wa) { v[4] = (double)*(__int64 *)(c->wa + 0xb0); v[5] = (double)*(__int64 *)(c->wa + 0xb8); }
    for (k = 0; k < 3; k++) {
        void *va = gn_valve(c, vid[k]);
        LONG val, mx, mn;
        if (!va) continue;
        val = (LONG)ho_v(va, 0x30, 0, 0, 0, 0, 0, 0);
        mx = (LONG)ho_v(va, 0x38, 0, 0, 0, 0, 0, 0);
        mn = (LONG)ho_v(va, 0x3c, 0, 0, 0, 0, 0, 0);
        v[6 + k] = val >= 0 ? (mx > 0 ? val * 1000.0 / mx : 0) : (mn < 0 ? val * -1000.0 / mn : 0);
        ho_v(va, 0x08, 0, 0, 0, 0, 0, 0);
    }
    {   void *vj = gn_valve(c, 7000), *vr = gn_valve(c, 3000);
        double rp = 0, f = 0;
        if (vj) { v[16] = (double)ho_v(vj, 0x2c, 0, 0, 0, 0, 0, 0); ho_v(vj, 0x08, 0, 0, 0, 0, 0, 0); }
        if (vr) { rp = (double)ho_v(vr, 0x28, 0, 0, 0, 0, 0, 0); ho_v(vr, 0x08, 0, 0, 0, 0, 0, 0); }
        if (c->res) f = (double)((GN_FLOATFN)(*(void ***)c->res)[0x7c / 4])(c->res, NULL);
        v[17] = rp * f >= 0 ? (double)(__int64)(rp * f) : 0;
        n += wsprintfA(dbg + n, "jobs %ld R pop %ld x workforce %ld/1000; ", (LONG)v[16], (LONG)rp, (LONG)(f * 1000.0));
    }
    if (c->po) {
        BYTE *base = c->po - 0x1c;
        LONG ma = (LONG)ho_v(c->po, 0x84, 0, 0, 0, 0, 0, 0), mw = (LONG)ho_v(c->po, 0x88, 0, 0, 0, 0, 0, 0);
        v[9] = (LONG)ho_v(c->po, 0x78, 0, 0, 0, 0, 0, 0) * 100.0 / (ma > 0 ? ma : 11000);
        v[10] = (LONG)ho_v(c->po, 0x7c, 0, 0, 0, 0, 0, 0) * 100.0 / (mw > 0 ? mw : 11000);
        for (k = 0; k < 5; k++) v[24 + k] = (double)*(__int64 *)(base + k_gn_garb[k] + ci * 8);
    }
    if (c->res) {
        v[18] = (double)ho_v(c->res, 0x50, 0, 0, 0, 0, 0, 0); v[19] = (double)ho_v(c->res, 0x64, 0, 0, 0, 0, 0, 0);
        v[20] = (double)ho_v(c->res, 0x58, 0, 0, 0, 0, 0, 0); v[21] = (double)ho_v(c->res, 0x68, 0, 0, 0, 0, 0, 0);
        v[22] = (double)ho_v(c->res, 0x48, 0, 0, 0, 0, 0, 0); v[23] = (double)ho_v(c->res, 0x60, 0, 0, 0, 0, 0, 0);
    } else n += wsprintfA(dbg + n, "no residential iface; ");
    if (c->zone) v[30] = (double)ho_v(c->zone, 0x54, 0, 0, 0, 0, 0, 0);
    else {
        BYTE *z = c->city ? (BYTE *)ho_v(c->city, 0x14c, 0, 0, 0, 0, 0, 0) : NULL;
        n += wsprintfA(dbg + n, "no zone layer (0x%08lX vt 0x%08lX); ", (DWORD)z, z && !IsBadReadPtr(z, 4) ? *(DWORD *)z : 0);
    }
    for (k = 0; k < GN_LINES; k++) if (v[k] < 0 && k_gn[k].grp != 3) v[k] = 0;   /* the class keeps unsigned values */
    if (g_gn_log) logf("GRAPHNEW>   %smonth index %d", dbg, ci);
}

/* ---------------------------------------------------------------------------------------------- scale + push */
static DWORD gn_nice(double v) {   /* 1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8 x 10^k at or above v, at least 10 */
    static const double st[10] = { 1.0, 1.2, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0 };
    double m = 1.0;
    int k;
    if (v <= 10.0) return 10;
    while (m * 10.0 < v) m *= 10.0;
    for (k = 0; k < 10; k++) if (st[k] * m >= v) return (DWORD)(st[k] * m + 0.5);
    return (DWORD)(10.0 * m + 0.5);
}

static void gn_fmt_real(char *o, double v) {   /* 12,345 / -1,234 */
    char d[24], *p = d;
    int n, i, neg = v < 0;
    __int64 t = (__int64)((neg ? -v : v) + 0.5);
    wsprintfA(d, "%I64d", t);
    n = lstrlenA(d);
    if (neg) *o++ = '-';
    for (i = 0; i < n; i++) { *o++ = *p++; if ((n - 1 - i) % 3 == 0 && i < n - 1) *o++ = ','; }
    *o = 0;
}

static DWORD gn_store(int i, double v) {
    double x = v + (double)g_gn_off[k_gn[i].grp];
    return x <= 0.0 ? 0 : x >= 4294967295.0 ? 0xffffffffu : (DWORD)(x + 0.5);
}

/* one scale per graph from everything it keeps plus `now` (stored units, NULL = none), set before a push (a push clamps) */
static void gn_rescale(const DWORD *now) {
    DWORD a[12], sc;
    int g, i, k;
    for (g = 0; g < GN_GROUPS; g++) {
        double mx = 0.0;
        if (g_gn_off[g]) sc = 2 * g_gn_off[g];
        else {
            for (i = 0; i < GN_LINES; i++) {
                if (k_gn[i].grp != g) continue;
                if (now && now[i] > mx) mx = now[i];
                ho_v(g_gn_if[i], 0x28, 1, (DWORD)a, 0, 0, 0, 0); for (k = 0; k < 12; k++) if (a[k] > mx) mx = a[k];
                ho_v(g_gn_if[i], 0x34, 1, (DWORD)a, 0, 0, 0, 0); for (k = 0; k < 10; k++) if (a[k] > mx) mx = a[k];
                ho_v(g_gn_if[i], 0x40, 1, (DWORD)a, 0, 0, 0, 0); for (k = 0; k < 10; k++) if (a[k] > mx) mx = a[k];
            }
            sc = gn_nice(mx * 1.1);
        }
        for (i = 0; i < GN_LINES; i++) if (k_gn[i].grp == g) ho_v(g_gn_if[i], 0x60, 1, sc, 0, 0, 0, 0);
    }
}

/* lines not read from a history file: 12 months from the game's own rings where it keeps one, the rest at today's value */
static void gn_seed(const int *have) {
    GN_CTX c;
    double v[GN_LINES], m[GN_LINES][12];
    int seeded[GN_LINES], i, k, ci = 11, yr = 0, n = 0;
    DWORD a[12], y[10];
    char t[32];
    HMODULE sui = GetModuleHandleA("SIMUI.DLL");
    memset(seeded, 0, sizeof(seeded));
    gn_ctx(&c, NULL);
    if (!c.city) return;
    if (gn_key(c.city, &ci, &yr) < 0) { gn_ctx_free(&c); return; }
    gn_values(&c, ci, v);
    for (i = 0; i < GN_LINES; i++) for (k = 0; k < 12; k++) m[i][k] = v[i];
    if (c.budget) {
        for (k = 0; k < 12; k++) gn_budget_month(c.budget, (ci - k + 12) % 12, &m[0][k], &m[1][k]);
        seeded[0] = seeded[1] = 1;
    }
    if (c.pw) {
        BYTE *base = c.pw - 0x14, *es;
        LONG row = *(LONG *)(base + 0x2ac), r, t2;
        DWORD p[12];
        int okp = 0;
        if (row >= 0 && row < 12) {
            for (k = 0; k < 12; k++) {
                r = (row - k + 12) % 12; m[11][k] = 0;
                for (t2 = 0; t2 < 10; t2++) m[11][k] += *(LONG *)(base + 0xcc + (r * 10 + t2) * 4);
            }
            seeded[11] = 1;
            es = *(BYTE **)(base + 0x2d8);                /* the stock Energia % series (record 0x100051b8 reads base+0x2d8) */
            if (es && !IsBadReadPtr(es, 4) && sui) { memset(p, 0, sizeof(p)); ho_v(es, 0x28, 1, (DWORD)p, 0, 0, 0, 0); okp = 1; }
            if (okp) {
                for (k = 0; k < 12; k++)
                    m[2][k] = p[k] > 0 && p[k] < 100 ? m[11][k] * 100.0 / (100.0 - p[k]) : m[11][k];
                m[2][0] = v[2];                            /* the newest month is known exactly */
                seeded[2] = 1;
                logf("GRAPHNEW>   seed power: spare %% newest..oldest %lu %lu %lu %lu, used %ld %ld %ld %ld", p[0], p[1], p[2], p[3],
                     (LONG)m[11][0], (LONG)m[11][1], (LONG)m[11][2], (LONG)m[11][3]);
            }
        }
    }
    if (c.po) {
        BYTE *base = c.po - 0x1c;
        for (i = 0; i < 5; i++) for (k = 0; k < 12; k++) m[24 + i][k] = (double)*(__int64 *)(base + k_gn_garb[i] + ((ci - k + 12) % 12) * 8);
        for (i = 0; i < 5; i++) seeded[24 + i] = 1;
    }
    for (i = 0; i < GN_LINES; i++) {
        double mean = 0;
        if (have[i]) continue;
        for (k = 0; k < 12; k++) { a[k] = gn_store(i, m[i][k]); mean += m[i][k] / 12.0; }
        for (k = 0; k < 10; k++) y[k] = gn_store(i, seeded[i] ? mean : v[i]);
        ho_v(g_gn_if[i], 0x60, 1, 0xffffffffu, 0, 0, 0, 0);   /* no clamp while the arrays go in */
        ho_v(g_gn_if[i], 0x70, 1, (DWORD)a, 0, 0, 0, 0);
        ho_v(g_gn_if[i], 0x78, 1, (DWORD)y, 0, 0, 0, 0);
        ho_v(g_gn_if[i], 0x80, 1, (DWORD)y, 0, 0, 0, 0);
        gn_fmt_real(t, m[i][0]);
        gn_label(i, t);
        n++;
    }
    gn_rescale(NULL);
    gn_ctx_free(&c);
    logf("GRAPHNEW> seeded %d line(s) (12 months from the game's rings: %s%s%s%s), the rest at today's value", n,
         seeded[0] ? "budget " : "", seeded[11] ? "power-used " : "", seeded[2] ? "power-supply " : "", seeded[24] ? "garbage" : "");
}

/* first look this session, or the dates jumped: start over, from the history file when it matches, the rest seeded */
static void gn_sync(void *cal) {
    static const char *const slot[3] = { " (auto 5 min).sc3", " (auto 10 min).sc3", " (auto 1 h).sc3" };   /* sc3autosave k_slot */
    char name[MAX_PATH], cand[MAX_PATH + 24], t[32];
    int have[GN_LINES], key = gn_key(cal, NULL, NULL), i, c, n, got = 0, was = g_gn_last, fk;
    if (!g_gn_if[0] || key < 0) return;
    if (g_gn_synced && (key == g_gn_last || key == g_gn_last + 1)) return;
    g_gn_synced = 1;
    memset(have, 0, sizeof(have));
    for (i = 0; i < GN_LINES; i++) { gn_reset_line(i); gn_label(i, "-"); }
    cand[0] = 0;
    if (gn_city_name(gn_city(), name, sizeof(name)))
        /* the city's own file first, then its autosaves: a loaded autosave is renamed "<city>.sc3" right after the load
           (sc3autosave UNAUTO), so its history sits under the autosave's name. Only a file saved at this exact closed
           month is taken. */
        for (c = 0; c < 4 && !got; c++) {
            if (c == 0) lstrcpynA(cand, name, MAX_PATH);
            else {
                n = lstrlenA(name);
                if (n < 4 || lstrcmpiA(name + n - 4, ".sc3")) break;
                lstrcpynA(cand, name, n - 3);
                lstrcatA(cand, slot[c - 1]);
            }
            if ((got = gn_read_file(cand, key, g_gn_snap, have, &fk)) > 0) break;
            if (fk >= 0) logf("GRAPHNEW> %s.graphs is for closed month key %d, the city is at %d: not used", cand, fk, key);
        }
    for (i = 0; i < GN_LINES; i++) {
        if (!have[i]) continue;
        ho_v(g_gn_if[i], 0x60, 1, g_gn_snap[i].scale, 0, 0, 0, 0);
        ho_v(g_gn_if[i], 0x70, 1, (DWORD)g_gn_snap[i].m, 0, 0, 0, 0);
        ho_v(g_gn_if[i], 0x78, 1, (DWORD)g_gn_snap[i].y, 0, 0, 0, 0);
        ho_v(g_gn_if[i], 0x80, 1, (DWORD)g_gn_snap[i].d, 0, 0, 0, 0);
        gn_fmt_real(t, (double)g_gn_snap[i].m[0] - (double)g_gn_off[k_gn[i].grp]);   /* newest month */
        gn_label(i, t);
    }
    g_gn_last = key;
    logf("GRAPHNEW> city at closed month key %d (last push %d): history %s%s (%d line(s))", key, was,
         got ? "read from " : "file none", got ? cand : "", got);
    __try { gn_seed(have); }
    __except (EXCEPTION_EXECUTE_HANDLER) { logf("GRAPHNEW> seeding threw 0x%08lX", GetExceptionCode()); }
}

static void gn_record(void *cal, BYTE *budget) {
    GN_CTX c;
    double v[GN_LINES];
    DWORD s[GN_LINES];
    int ci, yr, i;
    gn_sync(cal);
    if (gn_key(cal, &ci, &yr) < 0) return;
    gn_ctx(&c, budget);
    gn_values(&c, ci, v);
    gn_ctx_free(&c);
    for (i = 0; i < GN_LINES; i++) s[i] = gn_store(i, v[i]);
    gn_rescale(s);
    for (i = 0; i < GN_LINES; i++) {
        char t[32];
        ho_v(g_gn_if[i], 0x6c, 1, s[i], 0, 0, 0, 0);
        if (ci == 11) {
            ho_v(g_gn_if[i], 0x74, 1, ho_v(g_gn_if[i], 0x2c, 0, 0, 0, 0, 0, 0), 0, 0, 0, 0);
            if ((DWORD)(yr + 1) % 10 == 0) ho_v(g_gn_if[i], 0x7c, 1, ho_v(g_gn_if[i], 0x38, 0, 0, 0, 0, 0, 0), 0, 0, 0, 0);
        }
        gn_fmt_real(t, v[i]);
        gn_label(i, t);
    }
    g_gn_last = yr * 12 + ci;
    if (g_gn_log) {
        char t[700];
        int n = wsprintfA(t, "GRAPHNEW> %d-%02d pushed:", yr, ci + 1);
        for (i = 0; i < GN_LINES; i++) n += wsprintfA(t + n, " %ld", (long)(v[i] < 0 ? v[i] - 0.5 : v[i] + 0.5));
        logf("%s", t);
    }
}

typedef DWORD (__fastcall *GN_BUDFN)(void *self);
static DWORD __fastcall gn_month(BYTE *budget) {
    DWORD r = ((GN_BUDFN)g_orig_7d88)(budget);
    if (g_gn_if[0] && budget && !IsBadReadPtr(budget, 0x50)) {
        __try { gn_record(*(void **)(budget + 0x14), budget); }
        __except (EXCEPTION_EXECUTE_HANDLER) { logf("GRAPHNEW> monthly record threw 0x%08lX", GetExceptionCode()); }
        __try { tm_install(); tm_month(g_gn_last); }   /* VDBARS TRIPMODES: a month closed */
        __except (EXCEPTION_EXECUTE_HANDLER) { }
    } else if (budget && !IsBadReadPtr(budget, 0x50)) {
        /* tripmonth 2026-11-03: the series are made only once the Graficas page has been opened (gn_make from gn_enum),
           so before that the month close above never ran and TRIPCELLS / TRIPMODES had no months. The key is the one
           gn_record would store (gn_key on the same calendar), computed here without touching any graph series. */
        __try { int key = gn_key(*(void **)(budget + 0x14), NULL, NULL); if (key >= 0) { tm_install(); tm_month(key); } }
        __except (EXCEPTION_EXECUTE_HANDLER) { }
    }
    return r;
}

/* ---------------------------------------------------------------------------------------------- install */
static void gn_install(HMODULE sui) {
    HMODULE mi = GetModuleHandleA("SIMMISC.DLL"), sc = GetModuleHandleA("SIMCITY.DLL");
    static const BYTE p6a[6] = { 0x55, 0x8b, 0xec, 0x83, 0xec, 0x10 };    /* push ebp; mov ebp,esp; sub esp,0x10 */
    static const BYTE p6b[6] = { 0x55, 0x8b, 0xec, 0x83, 0xec, 0x3c };    /* ... sub esp,0x3c */
    static const BYTE p6c[6] = { 0x55, 0x8b, 0xec, 0x51, 0x53, 0x56 };    /* push ebp; mov ebp,esp; push ecx; push ebx; push esi */
    BYTE e1[5], e3[5];
    char v[8];
    if (!g_graphnew) { logf("GRAPHNEW> off (SC3RESIZE_GRAPHNEW=0): the 16 stock graphs only"); return; }
    if (GetEnvironmentVariableA("SC3RESIZE_GRAPHTABS", v, sizeof(v))) g_graphtabs = atoi(v);
    if (!mi || !sc) { logf("GRAPHNEW> SIMMISC / SIMCITY not loaded: no new graphs"); return; }
    e1[0] = 0xb8; *(DWORD *)(e1 + 1) = (DWORD)sui + 0x9b348;   /* FUN_1002e012: mov eax, <EH handler> */
    e3[0] = 0xb8; *(DWORD *)(e3 + 1) = (DWORD)sc + 0x1186e;    /* FUN_1000429d */
    if (g_graphtabs && !ho_hook(sui, 0x2df5b, p6c, 6, (void *)gn_ctl, &g_orig_df5b, "graphs page control handler FUN_1002df5b"))
        g_graphtabs = 0;   /* no tab clicks without it: the one-grid page */
    if (!ho_hook(sui, 0x2f8fd, p6a, 6, (void *)gn_enum, &g_orig_f8fd, "graphs enumeration FUN_1002f8fd") ||
        !ho_hook(sui, 0x2e012, e1, 5, (void *)gn_layout, &g_orig_e012, "graphs layout FUN_1002e012") ||
        !ho_hook(sui, 0x2eb59, p6a, 6, (void *)gn_close, &g_orig_eb59, "graphs close FUN_1002eb59") ||
        !ho_hook(mi, 0x7d88, p6b, 6, (void *)gn_month, &g_orig_7d88, "SIMMISC budget month FUN_10007d88") ||
        !ho_hook(sc, 0x429d, e3, 5, (void *)gn_save, &g_orig_save, "SIMCITY city save FUN_1000429d")) {
        logf("GRAPHNEW> a hook failed (see above): the hooks already in place stay, the new graphs may be partial");
        return;
    }
    logf("GRAPHNEW> on: %d new graphs (%d lines) on the Graficas page, tabs %s", GN_GROUPS, GN_LINES, g_graphtabs ? "on" : "off");
}
