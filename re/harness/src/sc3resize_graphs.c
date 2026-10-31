/* ======================================================================================================== GRAPHNEW
 * (child graphaxis 2026-10-30, owner pick: income vs expenses, power and water supply vs demand, R/C/I demand, air vs
 * water pollution). #included by sc3resize.c right after the GRAPHAXIS block. Plan and evidence: re/analysis/GRAPH_SERIES.md.
 *
 * Five new graphs on the Graficas page, one checkbox each, 2 or 3 lines each (11 lines). Every line is a series object of
 * the game's own class (SIMMISC ctor 0x10033556, 0xf0 bytes, interface at +8, vtable 0x10041b78 [CONFIRMED]), so the page
 * draws, labels and scales it like its own 16:
 *  - enumeration: the page broadcasts {0x02DC6D7F, 0x605} and each layer answers sink->+0xc(series) = FUN_1002f8c7, which
 *    appends {BYTE on; series *} to page+0x68 [CONFIRMED @ SIMUI 0x1002f8fd, 0x1002f8c7]. A detour on 0x1002f8fd appends
 *    our 11 after the original.
 *  - layout: FUN_1002e012 makes one checkbox per entry, 3 per row from page (20, 210), pitch 120 x 24 [CONFIRMED @ SIMUI
 *    0x1002e012, 0x1002e380]. Its automatic place for entry 17 lands on the 1 / 10 / 100 years radios, so after it runs the
 *    five group checkboxes are moved to free cells of columns 0 and 1 (rows 5..7) and the other 6 lines' checkboxes are
 *    hidden. A hidden line follows its group's checkbox: its own id is swapped for one no window has, so the renderer's
 *    by-id lookup (0x1002ed75) misses and leaves the on byte we set before it runs.
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
 *    city file, written after a successful city save (SIMCITY 0x1000429d = city vt+0x20). It is read the first time the
 *    graphs look at a city in a session and whenever the date jumps (another city or an older save was loaded: the
 *    closed month is neither the last one pushed nor the next), and used only when its date is the city's date. A city
 *    vt+0x1c (0x10003b8b) detour never fired on a load (measured 2026-10-30), so no load hook. The .sc3 itself is not
 *    touched: the stock game ignores the file.
 * SC3RESIZE_GRAPHNEW=0: none of this is installed (the 16 stock graphs, as before). SC3RESIZE_GRAPHNEW_LOG=1 logs every
 * monthly push. */
static int   g_graphnew = 1, g_gn_log;
#define GN_LINES 11
#define GN_GROUPS 5
#define GN_ID0   0x7A3C0100u           /* line i: checkbox id GN_ID0 + i, label id GN_ID0 + 0x40 + i, dummy GN_ID0 + 0x80 + i */
typedef struct { const char *es, *en; int grp; DWORD rgb; } GN_LINE;
static const GN_LINE k_gn[GN_LINES] = {
    { "Ingresos", "Income", 0, 0x209020 },          { "Gastos", "Expenses", 0, 0xD02020 },
    { "Energ\xed""a oferta", "Power supply", 1, 0xE09000 }, { "Energ\xed""a demanda", "Power demand", 1, 0x7040C0 },
    { "Agua oferta", "Water supply", 2, 0x1878E0 },  { "Agua demanda", "Water demand", 2, 0x7040C0 },
    { "Demanda R", "R demand", 3, 0x00A000 },       { "Demanda C", "C demand", 3, 0x2040E0 },
    { "Demanda I", "I demand", 3, 0xD0A000 },
    { "Contam. aire", "Air pollution", 4, 0x707070 }, { "Contam. agua", "Water pollution", 4, 0x2060C0 } };
static const char *k_gn_grp_es[GN_GROUPS] = { "Ingresos/Gastos", "Energ\xed""a of./dem.", "Agua of./dem.", "Demanda RCI", "Contam. aire/agua" };
static const char *k_gn_grp_en[GN_GROUPS] = { "Income/Expenses", "Power sup./dem.", "Water sup./dem.", "RCI demand", "Air/water pollut." };
static const int   k_gn_lead[GN_GROUPS] = { 0, 2, 4, 6, 9 };
static const int   k_gn_cell[GN_GROUPS][2] = { { 1, 5 }, { 0, 6 }, { 1, 6 }, { 0, 7 }, { 1, 7 } };   /* col, row (Agua % takes 0, 5) */
static DWORD g_gn_off[GN_GROUPS];      /* stored = real + off (R/C/I demand can be negative), set in gn_make */
static BYTE *g_gn_if[GN_LINES];        /* interface (object + 8), one reference held for the session */
static int   g_gn_on[GN_GROUPS];       /* group checkbox state, sc3resize.ini [graphs] */
static int   g_gn_last = -1;           /* year * 12 + closed month index of the last push */
static int   g_gn_synced;
static int   g_gn_es = 1;
static void *g_orig_f8fd, *g_orig_e012, *g_orig_eb59, *g_orig_7d88, *g_orig_save;

static void gn_sync(void *cal);   /* below */
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
    wsprintfA(t, "%s\n%s", g_gn_es ? k_gn[i].es : k_gn[i].en, val);
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
        ho_v(g_gn_if[i], 0x4c, 1, (DWORD)gn_str(&s, k_gn_lead[g] == i ? (g_gn_es ? k_gn_grp_es[g] : k_gn_grp_en[g])
                                                     : (g_gn_es ? k_gn[i].es : k_gn[i].en)), 0, 0, 0, 0);
        id = GN_ID0 + i;          ho_v(g_gn_if[i], 0x54, 1, (DWORD)&id, 0, 0, 0, 0);
        id = GN_ID0 + 0x40 + i;   ho_v(g_gn_if[i], 0x58, 1, (DWORD)&id, 0, 0, 0, 0);
        ho_v(g_gn_if[i], 0x5c, 1, k_gn[i].rgb, 0, 0, 0, 0);
        ho_v(g_gn_if[i], 0x64, 1, 0, 0, 0, 0, 0);                                        /* fixed scale, set by us */
        gn_reset_line(i);
        gn_label(i, "-");
    }
    gn_ini(0);
    done = 1;
    logf("GRAPHNEW> %d series made (SIMMISC class), groups on %d%d%d%d%d", GN_LINES, g_gn_on[0], g_gn_on[1], g_gn_on[2], g_gn_on[3], g_gn_on[4]);
    return 1;
}

/* ---------------------------------------------------------------------------------------------- the page */
typedef DWORD (__fastcall *GN_PAGEFN)(void *self, void *edx, DWORD a);

typedef DWORD (__fastcall *GN_PAGEFN2)(void *self, void *edx, DWORD a, DWORD b);
static DWORD __fastcall gn_enum(BYTE *page, void *edx, DWORD city, DWORD a2) {   /* page vt+0x20, ret 8: 2 args */
    HMODULE sui = GetModuleHandleA("SIMUI.DLL");
    DWORD r = ((GN_PAGEFN2)g_orig_f8fd)(page, edx, city, a2), a[1];
    BYTE *e, *v0, *v1;
    int i, n = 0;
    if (!gn_make()) return r;
    __try { gn_sync(((void *(__cdecl *)(void))((BYTE *)sui + 0x8e7da))()); }   /* a load since the last look: read its history now */
    __except (EXCEPTION_EXECUTE_HANDLER) { logf("GRAPHNEW> history check threw 0x%08lX", GetExceptionCode()); }
    for (i = 0; i < GN_LINES; i++) {
        int have = 0;
        v0 = *(BYTE **)(page + 0x68); v1 = *(BYTE **)(page + 0x6c);
        for (e = v0; e && e < v1; e += 8) if (*(BYTE **)(e + 4) == g_gn_if[i]) have = 1;
        if (have) continue;
        { DWORD id = GN_ID0 + i; ho_v(g_gn_if[i], 0x54, 1, (DWORD)&id, 0, 0, 0, 0); }   /* real id back for the layout */
        a[0] = (DWORD)g_gn_if[i];
        rz_thiscall_ret(page + 0x64, (BYTE *)sui + 0x2f8c7, a, 1);
        n++;
    }
    logf("GRAPHNEW> page 0x%08lX: %d series added to the list (%d entries)", (DWORD)page, n,
         (int)((*(BYTE **)(page + 0x6c) - *(BYTE **)(page + 0x68)) / 8));
    return r;
}

static void *gn_cbox(void *win, DWORD id) {   /* the checkbox interface (IID 0x8810), released by the caller */
    void *cb = NULL;
    if (!(ho_v(win, 0x80, 3, id, 0x8810, (DWORD)&cb, 0, 0) & 0xff)) return NULL;
    return cb;
}

/* before the renderer: each hidden line takes its group checkbox state */
static void gn_pre_render(BYTE *page, void *win) {
    BYTE *e, *v0, *v1;
    int g, i, ch = 0;
    if (!g_gn_if[0] || !page || IsBadReadPtr(page, 0x70)) return;
    for (g = 0; g < GN_GROUPS; g++) {
        void *cb = gn_cbox(win, GN_ID0 + k_gn_lead[g]);
        int on;
        if (!cb) continue;
        on = (ho_v(cb, 0x38, 0, 0, 0, 0, 0, 0) & 0xff) ? 1 : 0;
        ho_v(cb, 0x08, 0, 0, 0, 0, 0, 0);
        if (on != g_gn_on[g]) { g_gn_on[g] = on; ch = 1; }
    }
    if (ch) gn_ini(1);   /* kept at once, not only on close */
    v0 = *(BYTE **)(page + 0x68); v1 = *(BYTE **)(page + 0x6c);
    for (e = v0; e && e < v1 && !IsBadReadPtr(e, 8); e += 8)
        if ((i = gn_line_of(*(void **)(e + 4))) >= 0 && k_gn_lead[k_gn[i].grp] != i) e[0] = (BYTE)g_gn_on[k_gn[i].grp];
}

static DWORD __fastcall gn_layout(BYTE *page, void *edx, DWORD win) {
    DWORD r = ((GN_PAGEFN)g_orig_e012)(page, edx, win), id;
    int i, g;
    if (!g_gn_if[0] || !win) return r;
    for (i = 0; i < GN_LINES; i++) {
        BYTE *w = (BYTE *)mp_child((void *)win, GN_ID0 + i);
        g = k_gn[i].grp;
        if (!w || IsBadReadPtr(w, 0xa4)) { logf("GRAPHNEW> no checkbox for line %d", i); continue; }
        if (k_gn_lead[g] == i) {
            void *cb;
            ho_v(w, 0xcc, 2, (DWORD)(20 + 120 * k_gn_cell[g][0]), (DWORD)(210 + 24 * k_gn_cell[g][1]), 0, 0, 0);
            if ((cb = gn_cbox((void *)win, GN_ID0 + i))) { ho_v(cb, 0x34, 1, (DWORD)g_gn_on[g], 0, 0, 0, 0); ho_v(cb, 0x08, 0, 0, 0, 0, 0, 0); }
        } else {
            gx_show(w, 0);
            id = GN_ID0 + 0x80 + i;  ho_v(g_gn_if[i], 0x54, 1, (DWORD)&id, 0, 0, 0, 0);   /* the renderer's lookup misses */
        }
    }
    gx_render(page, NULL, win);   /* redraw with the group states (the original drew before our checkboxes were set) */
    logf("GRAPHNEW> page 0x%08lX laid out: 5 group checkboxes in rows 5..7, 6 line checkboxes hidden", (DWORD)page);
    return r;
}

static void __fastcall gn_close(BYTE *page, void *edx, DWORD win) {
    BYTE *v0, *v1, *e, *o;
    int n = 0;
    if (g_gn_if[0] && page && !IsBadReadPtr(page, 0x70)) {
        gn_pre_render(page, (void *)win);
        gn_ini(1);
        v0 = *(BYTE **)(page + 0x68); v1 = *(BYTE **)(page + 0x6c);
        for (e = o = v0; e && e < v1; e += 8) {
            if (gn_line_of(*(void **)(e + 4)) >= 0) { ho_v(*(void **)(e + 4), 0x08, 0, 0, 0, 0, 0, 0); n++; continue; }   /* the list's reference */
            if (o != e) memcpy(o, e, 8);
            o += 8;
        }
        if (v0) *(BYTE **)(page + 0x6c) = o;
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

/* after a save: wait until the city's file carries the save's time (the save command may set the name after the city
   save routine returns), then write "<city file>.graphs". A file that did not change (autosave writes a temp copy and
   gives the city its old name back) gets nothing. */
static DWORD WINAPI gn_writer(LPVOID arg) {
    char name[MAX_PATH], side[MAX_PATH + 8];
    WIN32_FILE_ATTRIBUTE_DATA fa;
    ULARGE_INTEGER t0, t1;
    int tries;
    (void)arg;
    t0.LowPart = g_gn_savet.dwLowDateTime; t0.HighPart = g_gn_savet.dwHighDateTime;
    for (tries = 0; tries < 40; tries++) {
        Sleep(250);
        if (!gn_city_name(gn_city(), name, sizeof(name))) continue;
        if (!GetFileAttributesExA(name, GetFileExInfoStandard, &fa)) continue;
        t1.LowPart = fa.ftLastWriteTime.dwLowDateTime; t1.HighPart = fa.ftLastWriteTime.dwHighDateTime;
        if (t1.QuadPart + 20000000ui64 < t0.QuadPart) continue;          /* older than the save (2 s slack) */
        {   HANDLE h;
            GN_HDR hd;
            DWORD w;
            wsprintfA(side, "%s.graphs", name);
            hd.magic = GN_MAGIC; hd.ver = 1; hd.key = (DWORD)g_gn_snapkey; hd.n = GN_LINES;
            h = CreateFileA(side, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
            if (h == INVALID_HANDLE_VALUE) { logf("GRAPHNEW> cannot write %s (%lu)", side, GetLastError()); break; }
            WriteFile(h, &hd, sizeof(hd), &w, NULL);
            WriteFile(h, g_gn_snap, sizeof(g_gn_snap), &w, NULL);
            CloseHandle(h);
            logf("GRAPHNEW> history written: %s (closed month key %d)", side, g_gn_snapkey);
        }
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
    if ((r & 0xff) && g_gn_if[0] && g_gn_last >= 0 && !InterlockedExchange(&g_gn_writer, 1)) {
        HANDLE th;
        gn_snapshot();
        g_gn_savet = t;
        th = CreateThread(NULL, 0, gn_writer, NULL, 0, NULL);
        if (th) CloseHandle(th); else InterlockedExchange(&g_gn_writer, 0);
    }
    return r;
}

/* first look this session, or the dates jumped: start over, from the history file when it matches */
static void gn_sync(void *cal) {
    char name[MAX_PATH], side[MAX_PATH + 8];
    int key = gn_key(cal, NULL, NULL), i, ok = 0, was = g_gn_last;
    if (!g_gn_if[0] || key < 0) return;
    if (g_gn_synced && (key == g_gn_last || key == g_gn_last + 1)) return;
    g_gn_synced = 1;
    for (i = 0; i < GN_LINES; i++) { gn_reset_line(i); gn_label(i, "-"); }
    if (gn_city_name(gn_city(), name, sizeof(name))) {
        HANDLE h;
        GN_HDR hd;
        DWORD rd;
        wsprintfA(side, "%s.graphs", name);
        h = CreateFileA(side, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
        if (h != INVALID_HANDLE_VALUE) {
            if (ReadFile(h, &hd, sizeof(hd), &rd, NULL) && rd == sizeof(hd) && hd.magic == GN_MAGIC && hd.ver == 1 &&
                hd.n == GN_LINES && ReadFile(h, g_gn_snap, sizeof(g_gn_snap), &rd, NULL) && rd == sizeof(g_gn_snap)) {
                if ((int)hd.key == key) {
                    for (i = 0; i < GN_LINES; i++) {
                        ho_v(g_gn_if[i], 0x60, 1, g_gn_snap[i].scale, 0, 0, 0, 0);
                        ho_v(g_gn_if[i], 0x70, 1, (DWORD)g_gn_snap[i].m, 0, 0, 0, 0);
                        ho_v(g_gn_if[i], 0x78, 1, (DWORD)g_gn_snap[i].y, 0, 0, 0, 0);
                        ho_v(g_gn_if[i], 0x80, 1, (DWORD)g_gn_snap[i].d, 0, 0, 0, 0);
                        gn_fmt_real(name, (double)g_gn_snap[i].m[0] - (double)g_gn_off[k_gn[i].grp]);   /* newest month */
                        gn_label(i, name);
                    }
                    ok = 1;
                } else logf("GRAPHNEW> %s is for closed month key %lu, the city is at %d: not used", side, hd.key, key);
            }
            CloseHandle(h);
        }
    }
    g_gn_last = key;
    logf("GRAPHNEW> city at closed month key %d (last push %d): history %s", key, was, ok ? "read from the .graphs file" : "starts empty");
}

/* ---------------------------------------------------------------------------------------------- monthly push */
static int gn_values(BYTE *budget, double *v);   /* below: the 11 real values of the month that closed */

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

static void gn_record(void *cal, BYTE *budget) {
    double v[GN_LINES];
    DWORD s[GN_LINES], a[12];
    int ci, yr, i, g, k;
    gn_sync(cal);
    if (gn_key(cal, &ci, &yr) < 0 || !gn_values(budget, v)) return;
    for (i = 0; i < GN_LINES; i++) {
        double x = v[i] + (double)g_gn_off[k_gn[i].grp];
        s[i] = x <= 0.0 ? 0 : x >= 4294967295.0 ? 0xffffffffu : (DWORD)(x + 0.5);
    }
    for (g = 0; g < GN_GROUPS; g++) {          /* one scale per graph, before the pushes (a push clamps to it) */
        double mx = 0.0;
        DWORD sc;
        if (g_gn_off[g]) sc = 2 * g_gn_off[g];
        else {
            for (i = 0; i < GN_LINES; i++) {
                if (k_gn[i].grp != g) continue;
                if (s[i] > mx) mx = s[i];
                ho_v(g_gn_if[i], 0x28, 1, (DWORD)a, 0, 0, 0, 0); for (k = 0; k < 12; k++) if (a[k] > mx) mx = a[k];
                ho_v(g_gn_if[i], 0x34, 1, (DWORD)a, 0, 0, 0, 0); for (k = 0; k < 10; k++) if (a[k] > mx) mx = a[k];
                ho_v(g_gn_if[i], 0x40, 1, (DWORD)a, 0, 0, 0, 0); for (k = 0; k < 10; k++) if (a[k] > mx) mx = a[k];
            }
            sc = gn_nice(mx * 1.1);
        }
        for (i = 0; i < GN_LINES; i++) if (k_gn[i].grp == g) ho_v(g_gn_if[i], 0x60, 1, sc, 0, 0, 0, 0);
    }
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
        char t[400];
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
    }
    return r;
}

/* ---------------------------------------------------------------------------------------------- install */
static void gn_install(HMODULE sui) {
    HMODULE mi = GetModuleHandleA("SIMMISC.DLL"), sc = GetModuleHandleA("SIMCITY.DLL");
    static const BYTE p6a[6] = { 0x55, 0x8b, 0xec, 0x83, 0xec, 0x10 };    /* push ebp; mov ebp,esp; sub esp,0x10 */
    static const BYTE p6b[6] = { 0x55, 0x8b, 0xec, 0x83, 0xec, 0x3c };    /* ... sub esp,0x3c */
    BYTE e1[5], e3[5];
    if (!g_graphnew) { logf("GRAPHNEW> off (SC3RESIZE_GRAPHNEW=0): the 16 stock graphs only"); return; }
    if (!mi || !sc) { logf("GRAPHNEW> SIMMISC / SIMCITY not loaded: no new graphs"); return; }
    e1[0] = 0xb8; *(DWORD *)(e1 + 1) = (DWORD)sui + 0x9b348;   /* FUN_1002e012: mov eax, <EH handler> */
    e3[0] = 0xb8; *(DWORD *)(e3 + 1) = (DWORD)sc + 0x1186e;    /* FUN_1000429d */
    if (!ho_hook(sui, 0x2f8fd, p6a, 6, (void *)gn_enum, &g_orig_f8fd, "graphs enumeration FUN_1002f8fd") ||
        !ho_hook(sui, 0x2e012, e1, 5, (void *)gn_layout, &g_orig_e012, "graphs layout FUN_1002e012") ||
        !ho_hook(sui, 0x2eb59, p6a, 6, (void *)gn_close, &g_orig_eb59, "graphs close FUN_1002eb59") ||
        !ho_hook(mi, 0x7d88, p6b, 6, (void *)gn_month, &g_orig_7d88, "SIMMISC budget month FUN_10007d88") ||
        !ho_hook(sc, 0x429d, e3, 5, (void *)gn_save, &g_orig_save, "SIMCITY city save FUN_1000429d")) {
        logf("GRAPHNEW> a hook failed (see above): the hooks already in place stay, the new graphs may be partial");
        return;
    }
    logf("GRAPHNEW> on: 5 new graphs (11 lines) on the Graficas page");
}

/* ---------------------------------------------------------------------------------------------- the 11 values
 * Read after FUN_10007d88 returns, for the month that closed (index ci, as the record computes it). Sources (worker pass
 * 2026-10-30 over the exports + PE, re/analysis/GRAPH_SERIES.md section 7):
 *  - income / expenses: budget int64 rings base + off + ci * 8. Income: taxes R/C/I +0x90 / +0x118 / +0x1a0, fares +0x3a0,
 *    ordinances +0x2d0, neighbour deals +0x470, business deals +0x4e8, disaster relief +0x338. Expenses: ordinances +0x268,
 *    neighbour deals +0x408, bonds (dword ring) +0x558 + ci * 4, departments: every node of the map at +0x60 (MSVC6 tree,
 *    successor FUN_10003354), ring node+0x30 + ci * 8. The year-end fold adds the income rings to the treasury and
 *    subtracts the expense rings, and the YTD getters split them the same way [CONFIRMED @ SIMMISC 0x10007d88, 0x10008a3e,
 *    0x10008ced, 0x10008d54].
 *  - power: city vt+0x150 = SIMUTIL power layer + 0x14. Supply = base+0x70 (sum of plant output reached by each grid),
 *    served = base+0x74 [CONFIRMED @ SIMUTIL 0x10004e57]. Demand = sum of the per-tile demand bytes base+0x2dc
 *    (width +0x28, height +0x34 + 1), the bytes the drain subtracts from the supply [CONFIRMED @ 0x10005015..0x100050fa],
 *    so it counts tiles that got no power too.
 *  - water: city vt+0x154 = SIMUTIL plumbing layer. Supply = int64 base+0xb0 (pump capacity), delivered = int64 base+0xb8
 *    [CONFIRMED @ SIMUTIL 0x1000e8c4]. Unmet water demand is not kept anywhere, so the second line is what was delivered.
 *  - R / C / I: city vt+0x1b8(0x80f1e6d3), QI 0x40a42f1c, vt+0x14(3000 / 5000 / 8000, 0xf1ec30, &valve), valve vt+0x30
 *    value, +0x38 max, +0x3c min [CONFIRMED @ SIMUI 0x10026e40, 0x10065303]. Shown as the HUD bar sees it:
 *    v >= 0 ? v * 1000 / max : v * -1000 / min, -1000..1000 [CONFIRMED @ SIMRCI 0x10042e89].
 *  - pollution: city vt+0x16c = SIMECO + 0x1c, vt+0x78 air, vt+0x7c water, vt+0x84 / +0x88 MaxAir / MaxWater for the UI
 *    (SC3Pollution.ini, 11000) [CONFIRMED @ SIMECO 0x10007b5d, 0x10008249]. Shown as a percent of that max, the unit the
 *    stock Polucion graph averages. */
static BYTE *gn_next(BYTE *n) {   /* FUN_10003354: left +8, parent +4, right +0xc, NULL leaves */
    BYTE *r = *(BYTE **)(n + 0xc), *p;
    if (r) { while (*(BYTE **)(r + 8)) r = *(BYTE **)(r + 8); return r; }
    p = *(BYTE **)(n + 4);
    while (p && n == *(BYTE **)(p + 0xc)) { n = p; p = *(BYTE **)(p + 4); }
    if (*(BYTE **)(n + 0xc) != p) n = p;
    return n;
}

static int gn_values(BYTE *b, double *v) {
    static const DWORD inc[8] = { 0x90, 0x118, 0x1a0, 0x3a0, 0x2d0, 0x470, 0x4e8, 0x338 }, exq[2] = { 0x268, 0x408 };
    static const DWORD vid[3] = { 3000, 5000, 8000 };
    HMODULE sui = GetModuleHandleA("SIMUI.DLL"), ut = GetModuleHandleA("SIMUTIL.DLL"), eco = GetModuleHandleA("SIMECO.DLL");
    BYTE *city, *pw, *wa, *head, *n, *rs;
    void *po, *L, *vl = NULL;
    DWORD m = 0, x[4], y = 0;
    int ci, k, g = 0;
    double in = 0, ex = 0, dem = 0;
    char dbg[200];
    if (!sui || !ut || !eco) return 0;
    ho_v(*(void **)(b + 0x14), 0x1e4, 3, (DWORD)&m, (DWORD)x, (DWORD)&y, 0, 0);
    ci = m == 1 ? 11 : (int)m - 2;
    if (ci < 0 || ci > 11) ci = 11;
    for (k = 0; k < 8; k++) in += (double)*(__int64 *)(b + inc[k] + ci * 8);
    for (k = 0; k < 2; k++) ex += (double)*(__int64 *)(b + exq[k] + ci * 8);
    ex += (double)*(LONG *)(b + 0x558 + ci * 4);
    head = *(BYTE **)(b + 0x60);
    if (head) for (n = *(BYTE **)(head + 8); n && n != head && g < 256; g++, n = gn_next(n)) ex += (double)*(__int64 *)(n + 0x30 + ci * 8);
    v[0] = in; v[1] = ex;
    city = (BYTE *)((void *(__cdecl *)(void))((BYTE *)sui + 0x8e7da))();
    for (k = 2; k < GN_LINES; k++) v[k] = 0;
    if (!city) return 1;
    pw = (BYTE *)ho_v(city, 0x150, 0, 0, 0, 0, 0, 0);
    if (pw && !IsBadReadPtr(pw - 0x14, 0x2f0) && *(DWORD *)pw == (DWORD)ut + 0x20550) {
        BYTE *base = pw - 0x14;
        LONG w = *(LONG *)(base + 0x28), h = *(LONG *)(base + 0x34) + 1, i;
        v[2] = *(LONG *)(base + 0x70);
        rs = *(BYTE **)(base + 0x2dc);
        if (rs && w > 0 && h > 0 && w <= 4096 && h <= 4096 && !IsBadReadPtr(rs, (UINT_PTR)w * h))
            for (i = 0; i < w * h; i++) dem += rs[i];
        v[3] = dem;
        wsprintfA(dbg, "power supply %ld served %ld demand bytes %ld (%ldx%ld)", *(LONG *)(base + 0x70), *(LONG *)(base + 0x74), (LONG)dem, w, h);
    } else lstrcpyA(dbg, "power layer not found");
    wa = (BYTE *)ho_v(city, 0x154, 0, 0, 0, 0, 0, 0);
    if (wa && !IsBadReadPtr(wa, 0xc0) && *(DWORD *)wa == (DWORD)ut + 0x22944) {
        v[4] = (double)*(__int64 *)(wa + 0xb0);
        v[5] = (double)*(__int64 *)(wa + 0xb8);
    }
    L = (void *)ho_v(city, 0x1b8, 1, 0x80f1e6d3, 0, 0, 0, 0);
    if (L) {
        if ((ho_v(L, 0x00, 2, 0x40a42f1c, (DWORD)&vl, 0, 0, 0) & 0xff) && vl)
            for (k = 0; k < 3; k++) {
                void *va = NULL;
                LONG val, mx, mn;
                if (!(ho_v(vl, 0x14, 3, vid[k], 0xf1ec30, (DWORD)&va, 0, 0) & 0xff) || !va) continue;
                val = (LONG)ho_v(va, 0x30, 0, 0, 0, 0, 0, 0);
                mx = (LONG)ho_v(va, 0x38, 0, 0, 0, 0, 0, 0);
                mn = (LONG)ho_v(va, 0x3c, 0, 0, 0, 0, 0, 0);
                v[6 + k] = val >= 0 ? (mx > 0 ? val * 1000.0 / mx : 0) : (mn < 0 ? val * -1000.0 / mn : 0);
                if (g_gn_log) logf("GRAPHNEW>   valve %lu value %ld max %ld min %ld -> %ld", vid[k], val, mx, mn, (LONG)v[6 + k]);
                ho_v(va, 0x08, 0, 0, 0, 0, 0, 0);
            }
        ho_v(L, 0x08, 0, 0, 0, 0, 0, 0);
    }
    po = (void *)ho_v(city, 0x16c, 0, 0, 0, 0, 0, 0);
    if (po && !IsBadReadPtr(po, 4) && *(DWORD *)po == (DWORD)eco + 0x1b984) {
        LONG ma = (LONG)ho_v(po, 0x84, 0, 0, 0, 0, 0, 0), mw = (LONG)ho_v(po, 0x88, 0, 0, 0, 0, 0, 0);
        v[9] = (LONG)ho_v(po, 0x78, 0, 0, 0, 0, 0, 0) * 100.0 / (ma > 0 ? ma : 11000);
        v[10] = (LONG)ho_v(po, 0x7c, 0, 0, 0, 0, 0, 0) * 100.0 / (mw > 0 ? mw : 11000);
    }
    if (g_gn_log) logf("GRAPHNEW>   %s, %d department(s), month index %d", dbg, g, ci);
    return 1;
}
