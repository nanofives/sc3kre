/* sc3dataview.c - extra Ver datos map layers for data the game holds and never shows (child dataview, 2026-10-30,
 * plan re/analysis/DATAVIEW_PLAN.md). Owner picks B, A, C, H.
 *
 * HOW A MAP LAYER WORKS [CONFIRMED]. A Ver datos panel's map view (SIMUI vt 0x100a7e68) holds wrappers (vt 0x100a811c,
 * +8 inner layer, +0xc shown) around layer objects (iid 0x5dd). The panel init adds each with the view's layer
 * interface (view+0xa4, vt 0x100a7db8) slot +0x98 AddLayer = SIMUI 0x1004339b: it wraps the inner (the wrapper AddRefs
 * it, SIMUI 0x10043bc4) unless that id is already there. +0x84 ShowLayer(id) / +0x8c HideLayer(id) set the shown byte
 * and the view's dirty byte. The texture render calls each shown inner's per-texel loop (SIMECO copy 0x100186be):
 * for every texel, inner vt+0x48(x, z, &colour) and, when it returns nonzero, paints that colour.
 *
 * WHAT THIS MOD ADDS. One vtable patch: SIMUI 0x100a7db8 +0x98. After the stock AddLayer returns,
 *   - stock id 0x2731 (air pollution, panel Contaminacion) -> also add 0x2735, the layer SIMECO builds and registers
 *     and no panel adds (B). Built with SIMECO's own factory (layer +0x3c owner, owner+0x30 vt+0xc, FUN_1000e0e7).
 *     Its vt+0x48 SIMECO 0x1000e4cc paints one colour (0xff,100,0) where the owner's grid vt+0x54(x, z) is true.
 *     Measured: owner+0x1c is the city's cISC3PollutionLayer and +0x54 is IsRadioactive (SIMECO 0x10008db8, bit 31 of
 *     the cell value), set by SetIsRadioactive (slot 37) from SIMDSTR 0x10007815 / SIMUTIL 0x10009295: a radiation map.
 *   - stock id 0x2715 (traffic, panel Trafico y transporte) -> also add four layers of ours (A, C), each an object
 *     built by SIMECO's layer base ctor 0x1001853b with a copy of the base vtable SIMECO 0x1001cca4 whose +0x48 is ours:
 *       0x2740 trips:    the traffic layer's trip-result bits, +0x7c tried / +0x80 ok, one bit per cell
 *                        (SimTransit FUN_10006965: untried / ok / failed). Green ok, red failed, nothing untried.
 *       0x2741 road, 0x2742 highway, 0x2743 subway: the live congestion grids +0x6c / +0x70 / +0x74 (byte per cell,
 *                        rows at grid+0xc, cap SimTransit+0x1f0bf, sc3perf mt_congestion), drawn only where the cell
 *                        has that network (u16 per cell at layer+0x5c: bit mask 0x15 / 2 / 8, SimTransit
 *                        FUN_10008c7b), coloured with the stock traffic layer's own palette.
 *   All extras start hidden. V (no modifier) on an open panel cycles its extras: Contaminacion stock -> 0x2735;
 *   Trafico stock -> trips -> road -> highway -> subway. Road/highway/subway hide the stock traffic layer while shown.
 *   Our objects keep one reference of ours; refcount 1 = no view holds it any more (the dialog closed), reused later.
 * Measuring 0x2735 (owner: measure before naming): every time it is switched on, the log cross-tabs its mask against
 * zone 17 (landfill zone), the pollution layer's active-landfill flag (vt+0x104) and garbage fill (vt+0x60).
 *
 * A caption label over the map names the extra layer on show (SC3DATAVIEW_CAPTION=0: none).
 * H: the Cuadros page fill SIMUI 0x100245c7 is detoured; on tabs Educacion / Salud a column of labels shows students vs
 * places, patients vs capacity, staff and strikes from the residential layer (block below; SC3DATAVIEW_HNUM=0: none).
 * TRANSIT (child transitmap 2026-11-02): an 11th Ver datos panel under Mapa de zonas, "Mapa de transporte publico",
 * per origin cell the share of trips with no bus / rail / subway (block below; SC3DATAVIEW_TRANSIT=0 / transit=0: none).
 * Off: SC3DATAVIEW=0 (nothing patched). dataview.ini beside the DLL: [dataview] key=86 (VK), pollution=1, traffic=1,
 * measure=1, transit=1. Log sc3dataview.log beside the DLL (SC3DATAVIEW_LOG overrides). Saves are never touched.
 */

#include <windows.h>
#include "sc3mods_guard.h"
#include "sc3lang.h"   /* modlang: SC3TR, mod text from the per-language tables */
#include <stdio.h>
#include <string.h>

static CRITICAL_SECTION g_lock;
static HANDLE g_log = INVALID_HANDLE_VALUE;
static LARGE_INTEGER g_freq, g_t0;
static HMODULE g_self;

static void logf(const char *fmt, ...) {
    char buf[1536], line[1664];
    va_list ap;
    LARGE_INTEGER now;
    DWORD wrote;
    int n;
    va_start(ap, fmt);
    _vsnprintf(buf, sizeof(buf) - 1, fmt, ap);
    buf[sizeof(buf) - 1] = 0;
    va_end(ap);
    QueryPerformanceCounter(&now);
    n = _snprintf(line, sizeof(line) - 1, "[%9.3f ms][tid %04lx] %s\r\n",
                  (double)(now.QuadPart - g_t0.QuadPart) * 1000.0 / (double)g_freq.QuadPart, GetCurrentThreadId(), buf);
    if (n < 0) return;
    EnterCriticalSection(&g_lock);
    if (g_log != INVALID_HANDLE_VALUE) WriteFile(g_log, line, (DWORD)n, &wrote, NULL);
    LeaveCriticalSection(&g_lock);
}

static void self_path(char *out, int cap, const char *leaf) {
    char *s;
    if (!GetModuleFileNameA(g_self, out, cap)) { out[0] = 0; return; }
    s = strrchr(out, '\\');
    if (s) s[1] = 0; else out[0] = 0;
    lstrcatA(out, leaf);
}

/* ============================================================ config */

static int g_key = 'V', g_pollution = 1, g_traffic = 1, g_measure = 1, g_caption = 1, g_hnum = 1, g_transit = 1;

static int env_int(const char *name, int *out) {
    char v[16];
    if (!GetEnvironmentVariableA(name, v, sizeof(v))) return 0;
    *out = atoi(v);
    return 1;
}

static void ini_read(void) {
    char p[MAX_PATH];
    self_path(p, sizeof(p), "dataview.ini");
    if (p[0] && GetFileAttributesA(p) == INVALID_FILE_ATTRIBUTES) {
        WritePrivateProfileStringA("dataview", "key", "86", p);
        WritePrivateProfileStringA("dataview", "pollution", "1", p);
        WritePrivateProfileStringA("dataview", "traffic", "1", p);
        WritePrivateProfileStringA("dataview", "measure", "1", p);
        WritePrivateProfileStringA("dataview", "transit", "1", p);
    }
    if (p[0]) {
        g_key = GetPrivateProfileIntA("dataview", "key", 'V', p);
        g_pollution = GetPrivateProfileIntA("dataview", "pollution", 1, p) ? 1 : 0;
        g_traffic = GetPrivateProfileIntA("dataview", "traffic", 1, p) ? 1 : 0;
        g_measure = GetPrivateProfileIntA("dataview", "measure", 1, p) ? 1 : 0;
        g_transit = GetPrivateProfileIntA("dataview", "transit", 1, p) ? 1 : 0;
    }
    env_int("SC3DATAVIEW_KEY", &g_key);
    env_int("SC3DATAVIEW_POLLUTION", &g_pollution);
    env_int("SC3DATAVIEW_TRAFFIC", &g_traffic);
    env_int("SC3DATAVIEW_MEASURE", &g_measure);
    env_int("SC3DATAVIEW_CAPTION", &g_caption);
    env_int("SC3DATAVIEW_HNUM", &g_hnum);
    env_int("SC3DATAVIEW_TRANSIT", &g_transit);
}

/* ============================================================ game calls */

static DWORD thiscall_n(void *self, void *fn, const DWORD *a, int n) {
    DWORD rv = 0;
    __asm {
        push ebx
        push esi
        push edi
        mov  ebx, esp
        mov  edi, a
        mov  ecx, n
        test ecx, ecx
        jz   tc_ready
    tc_push:
        mov  eax, [edi + ecx*4 - 4]
        push eax
        dec  ecx
        jnz  tc_push
    tc_ready:
        mov  ecx, self
        call [fn]
        mov  esp, ebx
        mov  rv, eax
        pop  edi
        pop  esi
        pop  ebx
    }
    return rv;
}

/* vtable call, slot byte offset, up to 4 args; 0 on a bad object */
static DWORD vc(void *o, DWORD slot, int n, DWORD a0, DWORD a1, DWORD a2, DWORD a3) {
    DWORD *vt, a[4];
    if (!o || IsBadReadPtr(o, 4)) return 0;
    vt = *(DWORD **)o;
    if (!vt || IsBadReadPtr((BYTE *)vt + slot, 4) || !vt[slot / 4]) return 0;
    a[0] = a0; a[1] = a1; a[2] = a2; a[3] = a3;
    return thiscall_n(o, (void *)vt[slot / 4], a, n);
}

static BYTE *g_sui, *g_eco, *g_st;   /* SIMUI.DLL, SIMECO.DLL, SimTransit.dll bases */

/* the loaded city: *(SC3U.exe + 0xfa86c) + 0x48, vtable SIMCITY + 0x13260 (sc3simrun / sc3undo / sc3landfill) */
static BYTE *city_get(void) {
    BYTE *exe = (BYTE *)GetModuleHandleA(NULL), *app, *c;
    HMODULE sc = GetModuleHandleA("SIMCITY.DLL");
    if (!sc) return NULL;
    __try {
        app = *(BYTE **)(exe + 0xfa86c);
        if (!app) return NULL;
        c = *(BYTE **)(app + 0x48);
        if (!c || *(DWORD *)c != (DWORD)sc + 0x13260) return NULL;
        return c;
    } __except (EXCEPTION_EXECUTE_HANDLER) { return NULL; }
}

/* a text box has the keyboard (sc3undo text_focus) */
static int text_focus(void) {
    DWORD gz = (DWORD)GetModuleHandleA("GZGraphicD.dll"), gw = (DWORD)GetModuleHandleA("GZWIND.DLL");
    DWORD si = (DWORD)GetModuleHandleA("SIMINIT.DLL"), su = (DWORD)GetModuleHandleA("SIMUI.DLL");
    BYTE *win, *sink, *f;
    DWORD vt;
    if (!gz) return 0;
    __try {
        win = *(BYTE **)(gz + 0x6cdb8);
        if (!win || *(DWORD *)win != gz + 0x1f740) return 0;
        sink = *(BYTE **)(win + 0x30);
        if (!sink || !gw || *(DWORD *)sink != gw + 0x2db80) return 0;
        f = *(BYTE **)(sink + 0x2c);
        if (!f) return 0;
        vt = *(DWORD *)f;
        if (vt == gw + 0x2bf10) return 1;
        if (vt == gw + 0x2a8cc || (si && vt == si + 0x30890) || (su && (vt == su + 0xa5f7c || vt == su + 0xadca0)))
            return f[0x111] != 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) { return 0; }
    return 0;
}

/* ============================================================ our layer objects */

#define ID_AIR     0x2731
#define ID_TRAFFIC 0x2715
#define ID_B       0x2735
#define ID_TRIPS   0x2740
#define ID_ROAD    0x2741
#define ID_HWY     0x2742
#define ID_SUB     0x2743
#define ID_TRANSIT 0x2750   /* Mapa de transporte publico (block TRANSIT below); no stock layer uses 0x2744..0x27ff in SIMUI */

#define ECO_BASE_VT   0x1cca4    /* SIMECO layer base vtable */
#define ECO_BASE_CTOR 0x1853b    /* __fastcall(obj) */
#define ECO_RGB       0x187de    /* __stdcall(r, g, b) -> 16-bit colour, the one 0x2735 uses */
#define ECO_FACTORY   0xe0e7     /* SIMECO pollution map-layer factory, owner+0x30 vt+0xc */
#define ST_LAYER      0x1fdb8    /* SimTransit traffic layer singleton */
#define ST_CAP        0x1f0bf    /* congestion cap byte */
#define SUI_ADD       0x4339b    /* SIMUI AddLayer */
#define SUI_IFACE_VT  0xa7db8
#define SUI_VIEW_VT   0xa7e68
#define NSLOTS 32
#define OBJ_SIZE 0x48            /* base fields end before +0x3c; +0x3c kind id, +0x40 traffic layer */

static DWORD g_vt[NSLOTS];
static int   g_vt_ready;
static void *g_orig_add;
static DWORD g_col_ok, g_col_fail;
static int   g_col_ready;
typedef DWORD (__cdecl *TCELLFN)(int, int);
static TCELLFN g_tcell;      /* sc3resize TRIPCELLS: packed trips (low 16) / transit trips (high 16) per origin cell */

typedef WORD (__stdcall *RGBFN)(DWORD, DWORD, DWORD);

static void colours_init(void) {
    RGBFN f = (RGBFN)(g_eco + ECO_RGB);
    if (g_col_ready) return;
    g_col_ok = f(40, 200, 40);
    g_col_fail = f(230, 30, 30);
    g_col_ready = 1;
}

static int trip_at(BYTE *tl, int x, int z) {   /* 2 untried, 0 ok, 1 failed (SimTransit FUN_10006965) */
    DWORD bit = 1u << (z & 31), w = (DWORD)(z >> 5) * 4;
    DWORD tried = *(DWORD *)(*(BYTE **)(*(BYTE **)(*(BYTE **)(tl + 0x7c) + 0x10) + x * 4) + w);
    DWORD ok = *(DWORD *)(*(BYTE **)(*(BYTE **)(*(BYTE **)(tl + 0x80) + 0x10) + x * 4) + w);
    if (!(tried & bit)) return 2;
    return (ok & bit) ? 0 : 1;
}
static WORD net_at(BYTE *tl, int x, int z) {
    return *(WORD *)(*(BYTE **)(*(BYTE **)(*(BYTE **)(tl + 0x5c) + 0xc) + x * 4) + z * 2);
}
static BYTE cong_at(BYTE *tl, DWORD off, int x, int z) {
    return *(*(BYTE **)(*(BYTE **)(*(BYTE **)(tl + off) + 0xc) + x * 4) + z);
}

/* GetCellColour(x, z, &colour), thiscall ret 0xc */
static char __fastcall dv_cell(BYTE *self, void *edx, int x, int z, DWORD *out) {
    DWORD id = *(DWORD *)(self + 0x3c);
    BYTE *tl = *(BYTE **)(self + 0x40);
    (void)edx;
    if (!tl || x < 0 || z < 0 || x >= *(int *)(self + 0x10) || z >= *(int *)(self + 0x14)) return 0;
    __try {
        if (id == ID_TRANSIT) {   /* share of the cell's trips that used no bus / rail / subway, stock traffic palette */
            DWORD v = g_tcell ? g_tcell(x, z) : 0, n = v & 0xffff, t = v >> 16;
            void *pal;
            int np;
            if (!n) return 0;
            if (t > n) t = n;
            pal = (void *)vc(self, 0x1c, 0, 0, 0, 0, 0);
            if (!pal) return 0;
            np = (int)vc(pal, 0x14, 0, 0, 0, 0, 0);
            if (np < 1) return 0;
            return (char)vc(pal, 0x1c, 2, (DWORD)(((np - 1) * (n - t) * 2 + n) / (2 * n)), (DWORD)out, 0, 0);
        }
        if (id == ID_TRIPS) {
            int r = trip_at(tl, x, z);
            if (r == 2) return 0;
            colours_init();
            *out = r == 0 ? g_col_ok : g_col_fail;
            return 1;
        } else {
            WORD mask = id == ID_ROAD ? 0x15 : id == ID_HWY ? 2 : 8;
            DWORD off = id == ID_ROAD ? 0x6c : id == ID_HWY ? 0x70 : 0x74;
            int cap = *(BYTE *)(g_st + ST_CAP), v, n;
            void *pal;
            if (!(net_at(tl, x, z) & mask)) return 0;
            v = cong_at(tl, off, x, z);
            if (cap < 1) cap = 1;
            if (v > cap) v = cap;
            pal = (void *)vc(self, 0x1c, 0, 0, 0, 0, 0);
            if (!pal) return 0;
            n = (int)vc(pal, 0x14, 0, 0, 0, 0, 0);
            if (n < 1) return 0;
            return (char)vc(pal, 0x1c, 2, (DWORD)((n - 1) * v / cap), (DWORD)out, 0, 0);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) { return 0; }
}

static int vt_init(void) {
    DWORD *src = (DWORD *)(g_eco + ECO_BASE_VT);
    int i;
    if (g_vt_ready) return 1;
    if (IsBadReadPtr(src, NSLOTS * 4)) return 0;
    for (i = 0; i < NSLOTS; i++) g_vt[i] = src[i];
    g_vt[0x48 / 4] = (DWORD)dv_cell;
    g_vt_ready = 1;
    return 1;
}

static BYTE *obj_new(void) {
    BYTE *o = (BYTE *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, OBJ_SIZE);
    void *ctor = g_eco + ECO_BASE_CTOR;
    if (!o) return NULL;
    __asm {
        mov ecx, o
        call [ctor]
    }
    *(DWORD **)o = g_vt;
    vc(o, 0x04, 0, 0, 0, 0, 0);   /* our reference: never released, so the game never deletes our heap block */
    return o;
}

/* ============================================================ native labels (GRAPHAXIS recipe, sc3resize gx_label)
 * factory SIMUI 0x85065() vt+0x44 CreateLabel(id, gzstring*); label vt+0x40 font (factory vt+0x14(0xf)), vt+0x44(1) left;
 * label vt+0x0c = its window: vt+0xec SetId, parent vt+0x34 AddChild, vt+0x78(id) FindChild, vt+0x10c SetText,
 * vt+0xc8 SetRect (parent-local), vt+0xf8 / +0xfc show / hide, window+0xa4 iface vt+0x24 colour (16-bit, colour service
 * SIMUI 0x85039() vt+0x84(r, g, b)). gzstring: SIMUI 0x5eb6 init, vt+0x10 assign, 0x6057 free (sc3resize ho_str). */

typedef void (__fastcall *STRFN)(void *);
static void ui_str(BYTE *buf, const char *t) {
    memset(buf, 0, 0x20);
    ((STRFN)(g_sui + 0x5eb6))(buf);
    if (t) vc(buf, 0x10, 1, (DWORD)t, 0, 0, 0);
}
static void ui_str_free(BYTE *buf) { ((STRFN)(g_sui + 0x6057))(buf); }
static WORD ui_col(int r, int g, int b) {
    void *cs = ((void *(__cdecl *)(void))(g_sui + 0x85039))();
    return cs ? (WORD)(vc(cs, 0x84, 3, (DWORD)r, (DWORD)g, (DWORD)b, 0) & 0xffff) : 0;
}
static void ui_show(void *w, int on) { if (w && !IsBadReadPtr(w, 0xa4)) vc(w, on ? 0xf8 : 0xfc, 0, 0, 0, 0, 0); }
static void *ui_child(void *win, DWORD id) { return (void *)vc(win, 0x78, 1, id, 0, 0, 0); }

/* label `id` of window `win`, made on first use; text, colour and parent-local rect set every time */
static void ui_label(void *win, DWORD id, const char *text, WORD col, int x, int y, int w, int h) {
    BYTE s[0x20];
    BYTE *lw = (BYTE *)ui_child(win, id);
    ui_str(s, text);
    if (!lw) {
        void *fac = ((void *(__cdecl *)(void))(g_sui + 0x85065))(), *lbl;
        lbl = fac ? (void *)vc(fac, 0x44, 2, id, (DWORD)s, 0, 0) : NULL;
        if (lbl) {
            vc(lbl, 0x40, 1, vc(fac, 0x14, 1, 0xf, 0, 0, 0), 0, 0, 0);
            vc(lbl, 0x44, 1, 1, 0, 0, 0);
            lw = (BYTE *)vc(lbl, 0x0c, 0, 0, 0, 0, 0);
            vc(lw, 0xec, 1, id, 0, 0, 0);
            if (!(vc(win, 0x34, 1, (DWORD)lw, 0, 0, 0) & 0xff)) { vc(lw, 0x28, 0, 0, 0, 0, 0); lw = NULL; }
            vc(lbl, 0x08, 0, 0, 0, 0, 0);
        }
    }
    if (lw && !IsBadReadPtr(lw, 0xa8)) {
        vc(lw + 0xa4, 0x24, 1, col, 0, 0, 0);
        vc(lw, 0x10c, 1, (DWORD)s, 0, 0, 0);
        vc(lw, 0xc8, 4, (DWORD)x, (DWORD)y, (DWORD)(x + w), (DWORD)(y + h));
        ui_show(lw, 1);
    }
    ui_str_free(s);
}

/* ============================================================ views */

#define P_POLL 0
#define P_TRAF 1
#define P_TRANS 2   /* our own panel: one layer, always shown, no V cycle */
typedef struct { BYTE *iface; BYTE *obj; DWORD id; int panel, ours; } Ent;
#define MAXE 96
static Ent g_ent[MAXE];
static int g_ne;
static int g_mode[3];                 /* index into the panel's list, 0 = stock */
static const DWORD k_poll[] = { 0, ID_B };
static const DWORD k_traf[] = { 0, ID_TRIPS, ID_ROAD, ID_HWY, ID_SUB };
static const char *k_name_poll[] = { "stock", "0x2735 (built by SIMECO, never shown)" };
static const char *k_name_traf[] = { "stock", "trips (green ok / red failed)", "road congestion", "highway congestion", "subway congestion" };

static int ent_alive(Ent *e) {
    __try { return *(LONG *)(e->obj + 4) > 1; } __except (EXCEPTION_EXECUTE_HANDLER) { return 0; }
}

/* drop dead entries; ours stay pooled (refcount 1, panel -1) for reuse, the game's 0x2735 objects are released */
static void ent_sweep(void) {
    int i, j = 0;
    for (i = 0; i < g_ne; i++) {
        Ent *e = &g_ent[i];
        if (e->iface && !ent_alive(e)) {
            if (!e->ours) { vc(e->obj, 0x08, 0, 0, 0, 0, 0); continue; }
            e->iface = NULL;
        }
        g_ent[j++] = *e;
    }
    g_ne = j;
}

static BYTE *pool_take(void) {
    int i;
    for (i = 0; i < g_ne; i++) if (g_ent[i].ours && !g_ent[i].iface) {
        BYTE *o = g_ent[i].obj;
        g_ent[i] = g_ent[--g_ne];
        return o;
    }
    return obj_new();
}

static int view_visible(BYTE *iface) {
    BYTE *w = iface - 0xa4;
    int i;
    __try {
        if (*(DWORD *)w != (DWORD)g_sui + SUI_VIEW_VT) return 0;
        for (i = 0; i < 16 && w; i++) {
            if (!(*(DWORD *)(w + 0xa0) & 1)) return 0;
            w = *(BYTE **)(w + 0x3c);
        }
        return 1;
    } __except (EXCEPTION_EXECUTE_HANDLER) { return 0; }
}

static void set_shown(BYTE *iface, DWORD id, int on) { vc(iface, on ? 0x84 : 0x8c, 1, id, 0, 0, 0); }

static void apply_entry(Ent *e) {
    DWORD want;
    if (e->panel == P_TRANS) { set_shown(e->iface, e->id, 1); return; }
    want = e->panel == P_POLL ? k_poll[g_mode[P_POLL]] : k_traf[g_mode[P_TRAF]];
    set_shown(e->iface, e->id, want == e->id);
}

static void apply_panel(int panel) {
    int i, hide_stock = panel == P_TRAF && k_traf[g_mode[P_TRAF]] >= ID_ROAD;
    BYTE *done[MAXE];
    int nd = 0, k;
    for (i = 0; i < g_ne; i++) {
        Ent *e = &g_ent[i];
        if (!e->iface || e->panel != panel || !ent_alive(e)) continue;
        apply_entry(e);
        if (panel != P_TRAF) continue;
        for (k = 0; k < nd && done[k] != e->iface; k++) ;
        if (k == nd) { done[nd++] = e->iface; set_shown(e->iface, ID_TRAFFIC, !hide_stock); }
    }
}

/* the caption over a panel's map: which extra layer is on, and the key. Child of the panel (the view's parent), at the
   top of the view's local rect right of the compass. */
#define CAP_ID 0x0DA7A001
/* modlang 2026-11-02: these were Spanish only; the English is new. SC3MODS_LANGTABLES=0 shows the Spanish as before. */
static const SC3TXT k_cap_poll[] = {
    { SC3KEY("dataview.cap_radiation_key"), "V: radiaci\xf3n", "V: radiation" },
    { SC3KEY("dataview.cap_radiation_back"), "Radiaci\xf3n (V: volver)", "Radiation (V: back)" } };
static const SC3TXT k_cap_traf[] = {
    { SC3KEY("dataview.cap_trips_key"), "V: viajes y congesti\xf3n por red", "V: trips and congestion by network" },
    { SC3KEY("dataview.cap_trips"), "Viajes: verde llega, rojo no (V)", "Trips: green arrives, red does not (V)" },
    { SC3KEY("dataview.cap_congestion_roads"), "Congesti\xf3n en calles (V)", "Road congestion (V)" },
    { SC3KEY("dataview.cap_congestion_highways"), "Congesti\xf3n en autopistas (V)", "Highway congestion (V)" },
    { SC3KEY("dataview.cap_congestion_subway"), "Congesti\xf3n en metro (V: volver)", "Subway congestion (V: back)" } };
static void caption_view(BYTE *iface, int panel) {
    BYTE *view = iface - 0xa4, *par;
    LONG l, t;
    static int logged;
    if (!g_caption) return;
    __try {
        if (*(DWORD *)view != (DWORD)g_sui + SUI_VIEW_VT || !(par = *(BYTE **)(view + 0x3c))) return;
        l = *(LONG *)(view + 0x80); t = *(LONG *)(view + 0x84);
        if (logged < 2) {
            logged++;
            logf("CAP> view 0x%08lX local [%ld %ld %ld %ld], parent 0x%08lX local [%ld %ld %ld %ld]", (DWORD)view, l, t,
                 *(LONG *)(view + 0x88), *(LONG *)(view + 0x8c), (DWORD)par, *(LONG *)(par + 0x80), *(LONG *)(par + 0x84),
                 *(LONG *)(par + 0x88), *(LONG *)(par + 0x8c));
        }
        ui_label(par, CAP_ID, sc3lang_txt(1, panel == P_POLL ? &k_cap_poll[g_mode[P_POLL]] : &k_cap_traf[g_mode[P_TRAF]]),
                 ui_col(0x20, 0x28, 0x70), l + 62, t + 4, 250, 14);
    } __except (EXCEPTION_EXECUTE_HANDLER) { logf("CAP> FAULT 0x%08lX", GetExceptionCode()); }
}
static void caption_panel(int panel) {
    int i, k, nd = 0;
    BYTE *done[MAXE];
    for (i = 0; i < g_ne; i++) {
        Ent *e = &g_ent[i];
        if (!e->iface || e->panel != panel || !ent_alive(e)) continue;
        for (k = 0; k < nd && done[k] != e->iface; k++) ;
        if (k == nd) { done[nd++] = e->iface; caption_view(e->iface, panel); }
    }
}

static void add_entry(BYTE *iface, BYTE *obj, DWORD id, int panel, int ours) {
    DWORD a[1];
    BYTE r;
    if (g_ne >= MAXE) ent_sweep();
    if (g_ne >= MAXE) { logf("ADD> table full, id 0x%04lx not added", id); return; }
    a[0] = (DWORD)obj;
    r = (BYTE)thiscall_n(iface, g_orig_add, a, 1);
    g_ent[g_ne].iface = iface; g_ent[g_ne].obj = obj; g_ent[g_ne].id = id;
    g_ent[g_ne].panel = panel; g_ent[g_ne].ours = ours;
    g_ne++;
    logf("ADD> view 0x%08lX: layer 0x%04lx obj 0x%08lX %s, cells %dx%d, add=%d", (DWORD)(iface - 0xa4), id, (DWORD)obj,
         ours ? "ours" : "SIMECO", *(int *)(obj + 0x10), *(int *)(obj + 0x14), r);
    apply_entry(&g_ent[g_ne - 1]);
}

static void add_b(BYTE *iface, BYTE *air) {
    BYTE *owner = *(BYTE **)(air + 0x3c), *fac;
    void *obj = NULL;
    DWORD *vt;
    if (!owner || IsBadReadPtr(owner + 0x30, 4)) { logf("B> 0x2731 layer has no owner"); return; }
    fac = owner + 0x30;
    vt = *(DWORD **)fac;
    if (IsBadReadPtr(vt, 0x10) || vt[0xc / 4] != (DWORD)g_eco + ECO_FACTORY) {
        logf("B> REFUSED: factory slot is 0x%08lX, expected SIMECO+0x%lx", IsBadReadPtr(vt, 0x10) ? 0 : vt[3], ECO_FACTORY);
        return;
    }
    if (!(BYTE)vc(fac, 0x0c, 3, ID_B, 0x5dd, (DWORD)&obj, 0) || !obj) { logf("B> factory refused 0x2735"); return; }
    add_entry(iface, (BYTE *)obj, ID_B, P_POLL, 0);
    caption_view(iface, P_POLL);
}

static void add_traffic(BYTE *iface, BYTE *stock) {
    BYTE *tl = *(BYTE **)(stock + 0x40), *want = *(BYTE **)(g_st + ST_LAYER);
    void *pal = (void *)vc(stock, 0x1c, 0, 0, 0, 0, 0);
    static const DWORD ids[4] = { ID_TRIPS, ID_ROAD, ID_HWY, ID_SUB };
    int i;
    if (!tl || tl != want) { logf("TRAF> stock layer's traffic layer 0x%08lX is not SimTransit's 0x%08lX", (DWORD)tl, (DWORD)want); return; }
    if (!vt_init()) { logf("TRAF> no base vtable"); return; }
    for (i = 0; i < 4; i++) {
        BYTE *o = pool_take();
        if (!o) { logf("TRAF> out of memory"); return; }
        vc(o, 0x14, 1, ids[i], 0, 0, 0);                                   /* SetId */
        vc(o, 0x28, 2, *(DWORD *)(stock + 0x10), *(DWORD *)(stock + 0x14), 0, 0);   /* SetSize */
        if (pal) vc(o, 0x18, 1, (DWORD)pal, 0, 0, 0);                      /* SetPalette */
        *(DWORD *)(o + 0x3c) = ids[i];
        *(BYTE **)(o + 0x40) = tl;
        add_entry(iface, o, ids[i], P_TRAF, 1);
    }
    apply_panel(P_TRAF);
    caption_view(iface, P_TRAF);
}

static volatile LONG g_inhook;

/* SIMUI 0x1004339b AddLayer(inner), thiscall ret 4 */
static BYTE __fastcall dv_add(BYTE *iface, void *edx, BYTE *inner) {
    DWORD a[1];
    BYTE r;
    (void)edx;
    a[0] = (DWORD)inner;
    r = (BYTE)thiscall_n(iface, g_orig_add, a, 1);
    if (!r || !inner || g_inhook) return r;
    g_inhook = 1;
    __try {
        DWORD id = vc(inner, 0x10, 0, 0, 0, 0, 0);
        if (id == ID_AIR || id == ID_TRAFFIC) ent_sweep();
        if (id == ID_AIR && g_pollution) add_b(iface, inner);
        else if (id == ID_TRAFFIC && g_traffic) add_traffic(iface, inner);
    } __except (EXCEPTION_EXECUTE_HANDLER) { logf("ADD> FAULT 0x%08lX in the add hook", GetExceptionCode()); }
    g_inhook = 0;
    return r;
}

/* ============================================================ TRANSIT: "Mapa de transporte publico" (child transitmap 2026-11-02)
 * Owner: "add world map section below mapa de zonas to show places where people are not using public transit".
 * PLACE [CONFIRMED @ SIMUI]. The Ver datos dialog init FUN_10044257 calls FUN_10044430 (call at 0x1004436b), which
 * builds the ten map panels with their factories and adds each with FUN_1004458c(dialog, panel, slot): panel vt+0xc
 * Init(dialog, dialog+0x30, &{4, slot*0x1c+4}) and the panel joins the list dialog+0x78. Slots 0..9 are the maps
 * (9 = Mapa de zonas), Cuadros is 12 and Graficas 13, so slot 10, right under Mapa de zonas, is empty. The panel's icon
 * button takes the panel id (+0x60, vt+0x2c SetId, button made by vt+0x48 from vt+0x44(group, image)), a click switches
 * panels by that id (dialog vt+0x38, FUN_10044aa6: old vt+0x18, new vt+0x1c, dialog title = new vt+0x38 = +0x20 string).
 * Ids in use: 0x5fa..0x603 maps, 0x604 Cuadros (FUN_1001f286), 0x605 Graficas (FUN_1002f8fd). Ours is 0x606.
 * WHAT WE ADD. The call at 0x1004436b goes to tp_panels: FUN_10044430, then one more panel at slot 10, an instance of
 * the traffic panel class (factory FUN_1004ac53, ctor FUN_1004ac88, vtable 0x100a8bd8, 0x26 slots) given a copy of its
 * vtable with three slots ours:
 *   +0x0c Init = the traffic Init FUN_1004acf9 step for step, with our id, title, icon and legend, and our layer in
 *         place of 0x2715: SetId; SetTitle vt+0x3c (gzstring); icon vt+0x44(0x5e5, 0x14) = the unused train strip of
 *         Apps\Res\UI\Shared\000005E5_Maps.ixf (104x26, 4 states, as the other icons); base init FUN_10045d40;
 *         palettes FUN_10046c07(0x830fa4d9 terrain, 0xa30e2116 traffic); legend box FUN_10046a6e + gradient
 *         FUN_10046e6c(0xa30e2116); legend labels FUN_10047524(slot 0 of 4 / slot 3 of 4); layers via the view's AddLayer:
 *         0x2711 terrain with palette 0x830fa4d9, then 0x2750 (ours) with the traffic palette.
 *   +0x1c Activate: stock, then the caption over the map (what red means, last month's citywide transit share).
 *   +0x8c FUN_1004773c maps the panel id to a city view mode with a switch over 0x5fa..0x603 and leaves the mode
 *         uninitialised for any other id: ours runs it as the traffic panel (0x602).
 * Layer 0x2750: per cell, the share of the trips starting there that used no bus, rail or subway, as the traffic
 * palette index (light = all used transit, dark red = none did); no trips = not drawn. Data: sc3resize TRIPCELLS
 * (sc3resize_vdbars.c), this month + last month. Without it the map is empty and the caption says so. */
#define TP_ID       0x606
#define TP_SLOT     10
#define TP_ICON     0x14
#define TP_NSLOTS   0x26
#define SUI_PANELS      0x44430    /* FUN_10044430 */
#define SUI_PANELS_CALL 0x4436b    /* call FUN_10044430 in FUN_10044257 */
#define SUI_TRAF_NEW    0x4ac53
#define SUI_TRAF_VT     0xa8bd8
#define SUI_TRAF_INIT   0x4acf9
#define SUI_PANEL_ADD   0x4458c
#define SUI_BASEINIT    0x45d40
#define SUI_PALETTE     0x46c07
#define SUI_LEGBOX      0x46a6e
#define SUI_LEGGRAD     0x46e6c
#define SUI_LEGLABEL    0x47524
#define SUI_ACTIVATE    0x4603f
#define SUI_USEMAP      0x4773c
#define TP_CAP_ID   0x0DA7A010

typedef int (__cdecl *TINFOFN)(LONG *);
typedef void (__cdecl *TBUILDFN)(void);
static TINFOFN g_tinfo;
static TBUILDFN g_tbuild;
static DWORD g_tpvt[TP_NSLOTS];
static int g_tp_es = 1, g_tp_n;

static DWORD sui_this(DWORD rva, void *self, int n, DWORD a0, DWORD a1, DWORD a2, DWORD a3, DWORD a4) {
    DWORD a[5];
    a[0] = a0; a[1] = a1; a[2] = a2; a[3] = a3; a[4] = a4;
    return thiscall_n(self, g_sui + rva, a, n);
}

static void tp_resolve(void) {
    HMODULE rz = GetModuleHandleA("sc3resize.dll");
    LONG in[8];
    if (rz && !g_tinfo) {
        g_tinfo = (TINFOFN)GetProcAddress(rz, "sc3resize_tripcells_info");
        g_tcell = (TCELLFN)GetProcAddress(rz, "sc3resize_tripcell");
        g_tbuild = (TBUILDFN)GetProcAddress(rz, "sc3resize_tripcells_build");
    }
    memset(in, 0, sizeof(in));
    if (g_tinfo) { g_tinfo(in); g_tp_es = in[0] ? 1 : 0; }
}

static void tp_num(char *o, LONG v) {   /* 45.210 / 45,210 */
    char t[16];
    int n, i, k = 0;
    if (v < 0) v = 0;
    n = wsprintfA(t, "%ld", v);
    for (i = 0; i < n; i++) {
        if (i && (n - i) % 3 == 0) o[k++] = g_tp_es ? '.' : ',';
        o[k++] = t[i];
    }
    o[k] = 0;
}

/* caption lines over the map (children of the panel window, local to it, right of the compass) */
static void tp_caption(BYTE *panel) {
    BYTE *iface = (BYTE *)vc(panel, 0x84, 0, 0, 0, 0, 0), *view, *par;
    LONG in[8], l, t, n, tr;
    char l1[96], l2[128], a[16];
    int on;
    WORD col;
    if (!iface) return;
    view = iface - 0xa4;
    if (*(DWORD *)view != (DWORD)g_sui + SUI_VIEW_VT || !(par = *(BYTE **)(view + 0x3c))) return;
    l = *(LONG *)(view + 0x80); t = *(LONG *)(view + 0x84);
    memset(in, 0, sizeof(in));
    on = g_tinfo ? g_tinfo(in) : 0;
    g_tp_es = in[0] || !g_tinfo ? 1 : 0;
    lstrcpyA(l1, SC3TR(g_tp_es, "dataview.red_trips_with_no", "Rojo: viajes sin bus, tren ni metro", "Red: trips with no bus, rail or subway"));
    if (!on) lstrcpyA(l2, SC3TR(g_tp_es, "dataview.no_trip_data_sc3resize", "Sin datos de viajes (sc3resize TRIPCELLS apagado)", "No trip data (sc3resize TRIPCELLS off)"));
    else {
        int last = in[1] > 0;
        n = last ? in[1] - in[3] : in[5];   /* trips that used a network */
        tr = last ? in[2] : in[6];
        if (n <= 0) lstrcpyA(l2, SC3TR(g_tp_es, "dataview.no_trips_counted_yet", "Todav\xed" "a no hay viajes contados", "No trips counted yet"));
        else {
            long p10 = (long)(tr * 1000.0 / n + 0.5);
            tp_num(a, n);
            if (g_tp_es) wsprintfA(l2, "%s: %ld,%ld%% de %s viajes en transporte", last ? "Mes pasado" : "Este mes",
                                   p10 / 10, p10 % 10, a);
            else wsprintfA(l2, "%s: %ld.%ld%% of %s trips on transit", last ? "Last month" : "This month so far",
                           p10 / 10, p10 % 10, a);
        }
    }
    col = ui_col(0x20, 0x28, 0x70);   /* lines under 50 characters fit the 316 px */
    ui_label(par, TP_CAP_ID, l1, col, l + 62, t + 4, 316, 14);
    ui_label(par, TP_CAP_ID + 1, l2, col, l + 62, t + 19, 316, 14);
    logf("TP> caption: %s | %s (counting %d, last month %ld trips, %ld transit, %ld no network, months %ld, this month %ld / %ld)",
         l1, l2, on, in[1], in[2], in[3], in[4], in[5], in[6]);
}

/* the drawn grid (5 x 5 neighbourhood sums, x16 fixed point) against the traffic layer's trip bits */
static void tp_measure(BYTE *obj) {
    BYTE *tl = *(BYTE **)(obj + 0x40);
    int W = *(int *)(obj + 0x10), H = *(int *)(obj + 0x14), x, z;
    long cells = 0, none = 0, all = 0, tried = 0, sn = 0, st = 0;
    if (!g_tcell || !tl || W <= 0 || H <= 0) return;
    if ((long)W * H > 300000 && g_measure < 2) { logf("TP> measure skipped on %dx%d (SC3DATAVIEW_MEASURE=2 forces)", W, H); return; }
    __try {
        for (x = 0; x < W; x++) for (z = 0; z < H; z++) {
            DWORD v = g_tcell(x, z), n = v & 0xffff, t = v >> 16;
            if (!n) continue;
            cells++; sn += n; st += t;
            if (!t) none++;
            if (t >= n) all++;
            if (trip_at(tl, x, z) != 2) tried++;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) { logf("TP> FAULT measuring"); return; }
    logf("TP> %dx%d: %ld cells drawn (weight %ld, transit %ld): %ld no transit, %ld all transit; "
         "%ld of them have the game's trip bit", W, H, cells, sn, st, none, all, tried);
}

static void add_transit(BYTE *iface, BYTE *traffic, void *pal) {
    BYTE *tl = traffic ? *(BYTE **)(traffic + 0x40) : NULL, *o;
    if (!tl || tl != *(BYTE **)(g_st + ST_LAYER)) { logf("TP> stock 0x2715 layer missing or not SimTransit's: no transit layer"); return; }
    if (!vt_init() || !(o = pool_take())) { logf("TP> no layer object"); return; }
    vc(o, 0x14, 1, ID_TRANSIT, 0, 0, 0);
    vc(o, 0x28, 2, *(DWORD *)(traffic + 0x10), *(DWORD *)(traffic + 0x14), 0, 0);
    if (pal) vc(o, 0x18, 1, (DWORD)pal, 0, 0, 0);
    *(DWORD *)(o + 0x3c) = ID_TRANSIT;
    *(BYTE **)(o + 0x40) = tl;
    add_entry(iface, o, ID_TRANSIT, P_TRANS, 1);
}

/* panel vt+0xc Init(dialog, parent, &pos), thiscall ret 0xc: FUN_1004acf9 with our id, title, icon, legend, layer */
static char __fastcall tp_init(BYTE *self, void *edx, BYTE *p1, BYTE *p2, void *p3) {
    DWORD id = TP_ID;
    BYTE s[0x20], *iface, *base, *tr;
    char ok = 0;
    (void)edx;
    if ((BYTE)vc(self, 0x6c, 0, 0, 0, 0, 0)) return 0;
    __try {
        tp_resolve();
        ok = (BYTE)vc(self, 0x2c, 1, (DWORD)&id, 0, 0, 0) != 0;
        if (ok) {
            ui_str(s, SC3TR(g_tp_es, "dataview.public_transit_map", "Mapa de transporte p\xfa" "blico", "Public transit map"));
            ok = (BYTE)vc(self, 0x3c, 1, (DWORD)s, 0, 0, 0) != 0;
            ui_str_free(s);
        }
        if (ok) ok = (BYTE)vc(self, 0x44, 2, 0x5e5, TP_ICON, 0, 0) != 0;
        if (ok) ok = (BYTE)sui_this(SUI_BASEINIT, self, 3, (DWORD)p1, (DWORD)p2, (DWORD)p3, 0, 0) != 0;
        sui_this(SUI_PALETTE, self, 2, (DWORD)p1, 0x830fa4d9, 0, 0, 0);
        sui_this(SUI_PALETTE, self, 2, (DWORD)p1, 0xa30e2116, 0, 0, 0);
        if (ok) ok = (BYTE)sui_this(SUI_LEGBOX, self, 2, (DWORD)p2, 0, 0, 0, 0) != 0;
        if (ok) ok = (BYTE)sui_this(SUI_LEGGRAD, self, 4, (DWORD)p1, (DWORD)p2, 0xa30e2116, 0, 0) != 0;
        if (ok) {
            ui_str(s, SC3TR(g_tp_es, "dataview.use_transit", "Con transporte", "Use transit"));
            sui_this(SUI_LEGLABEL, self, 5, (DWORD)p2, (DWORD)s, 0, 0, 4);
            ui_str_free(s);
            ui_str(s, SC3TR(g_tp_es, "dataview.no_transit", "Sin transporte", "No transit"));
            sui_this(SUI_LEGLABEL, self, 5, (DWORD)p2, (DWORD)s, 0, 3, 4);
            ui_str_free(s);
        }
        iface = ok ? (BYTE *)vc(self, 0x84, 0, 0, 0, 0, 0) : NULL;
        if (!iface) ok = 0;
        if (ok && (base = (BYTE *)vc(p1, 0x58, 1, 0x2711, 0, 0, 0)) != NULL) {
            ok = (BYTE)vc(base, 0x18, 1, vc(p1, 0x48, 1, 0x830fa4d9, 0, 0, 0), 0, 0, 0) != 0;
            if (ok) ok = (BYTE)vc(iface, 0x98, 1, (DWORD)base, 0, 0, 0) != 0;
        }
        if (ok) {
            tr = (BYTE *)vc(p1, 0x58, 1, ID_TRAFFIC, 0, 0, 0);
            add_transit(iface, tr, (void *)vc(p1, 0x48, 1, 0xa30e2116, 0, 0, 0));
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) { logf("TP> FAULT 0x%08lX in the panel init", GetExceptionCode()); ok = 0; }
    logf("TP> panel 0x%08lX init %s (id 0x%x, slot %d, icon 0x%x, %s)", (DWORD)self, ok ? "ok" : "FAILED", TP_ID, TP_SLOT,
         TP_ICON, g_tcell ? "TRIPCELLS found" : "no sc3resize TRIPCELLS");
    return ok;
}

/* vt+0x1c, called when the panel is switched in */
static void __fastcall tp_activate(BYTE *self) {
    thiscall_n(self, g_sui + SUI_ACTIVATE, NULL, 0);
    __try {
        int i;
        BYTE *iface = (BYTE *)vc(self, 0x84, 0, 0, 0, 0, 0);
        tp_resolve();
        if (g_tbuild) g_tbuild();   /* sc3resize rebuilds the drawn grid from this month + the history */
        tp_caption(self);
        for (i = 0; i < g_ne; i++)
            if (g_ent[i].panel == P_TRANS && g_ent[i].iface == iface && ent_alive(&g_ent[i])) {
                if (g_measure) tp_measure(g_ent[i].obj);
                vc(iface, 0x84, 1, ID_TRANSIT, 0, 0, 0);   /* ShowLayer: also marks the view dirty, new data drawn */
                break;
            }
    } __except (EXCEPTION_EXECUTE_HANDLER) { logf("TP> FAULT 0x%08lX on activate", GetExceptionCode()); }
}

/* vt+0x8c FUN_1004773c (city view mode for the panel id): run as the traffic panel */
static DWORD __fastcall tp_usemap(BYTE *self) {
    DWORD keep = *(DWORD *)(self + 0x60), r;
    *(DWORD *)(self + 0x60) = 0x602;
    r = thiscall_n(self, g_sui + SUI_USEMAP, NULL, 0);
    *(DWORD *)(self + 0x60) = keep;
    return r;
}

/* replaces `call FUN_10044430` at SIMUI 0x1004436b (ecx = the dialog) */
static char __fastcall tp_panels(BYTE *dlg) {
    char r = (char)thiscall_n(dlg, g_sui + SUI_PANELS, NULL, 0);
    BYTE *o;
    DWORD a[2];
    if (!r || !g_transit) return r;
    __try {
        o = ((BYTE *(__cdecl *)(void))(g_sui + SUI_TRAF_NEW))();
        if (!o) { logf("TP> traffic panel factory returned NULL"); return r; }
        *(DWORD **)o = g_tpvt;
        a[0] = (DWORD)o; a[1] = TP_SLOT;
        g_tp_n++;
        logf("TP> dialog 0x%08lX: panel 0x%08lX added at slot %d: %d (dialog #%d)", (DWORD)dlg, (DWORD)o, TP_SLOT,
             (BYTE)thiscall_n(dlg, g_sui + SUI_PANEL_ADD, a, 2), g_tp_n);
    } __except (EXCEPTION_EXECUTE_HANDLER) { logf("TP> FAULT 0x%08lX adding the panel", GetExceptionCode()); }
    return r;
}

static int tp_install(void) {
    DWORD *src = (DWORD *)(g_sui + SUI_TRAF_VT), old;
    BYTE *at = g_sui + SUI_PANELS_CALL;
    static const BYTE k_call[5] = { 0xe8, 0xc0, 0x00, 0x00, 0x00 };
    int i;
    if (memcmp(at, k_call, 5) || src[0xc / 4] != (DWORD)g_sui + SUI_TRAF_INIT || src[0x1c / 4] != (DWORD)g_sui + SUI_ACTIVATE ||
        src[0x8c / 4] != (DWORD)g_sui + SUI_USEMAP) {
        logf("TP> REFUSED: SIMUI is not the anchored build (call at +0x%lx or traffic panel vtable differ)", SUI_PANELS_CALL);
        return 0;
    }
    for (i = 0; i < TP_NSLOTS; i++) g_tpvt[i] = src[i];
    g_tpvt[0xc / 4] = (DWORD)tp_init;
    g_tpvt[0x1c / 4] = (DWORD)tp_activate;
    g_tpvt[0x8c / 4] = (DWORD)tp_usemap;
    if (!VirtualProtect(at, 5, PAGE_EXECUTE_READWRITE, &old)) return 0;   /* left writable: mod startup races */
    *(DWORD *)(at + 1) = (DWORD)tp_panels - (DWORD)(at + 5);
    FlushInstructionCache(GetCurrentProcess(), at, 5);
    return 1;
}

/* ============================================================ measuring */

static int zone_at(void *zl, int x, int z) { BYTE b = 0xff; vc(zl, 0x34, 3, (DWORD)x, (DWORD)z, (DWORD)&b, 0); return b; }
static DWORD fill_at(void *pl, int x, int z) { DWORD v = 0; vc(pl, 0x60, 3, (DWORD)x, (DWORD)z, (DWORD)&v, 0); return v; }
static int active_at(void *pl, int x, int z) { return (int)(vc(pl, 0x104, 2, (DWORD)x, (DWORD)z, 0, 0) & 0xff); }

/* lab only (SC3DATAVIEW_TEST_RAD=x,z): mark a radius-6 disc radioactive with the game's own SetIsRadioactive
   (pollution vt+0x94, slot 37, SIMECO 0x10008f65; the game's setters are SIMDSTR 0x10007815 and SIMUTIL 0x10009295,
   radius 10 plus a random fringe to 20). Changes the running city: never on outside a lab. */
static void test_rad(void) {
    char v[32];
    int cx, cz, x, z, n = 0;
    BYTE *c;
    void *pl;
    static int done;
    if (done || !GetEnvironmentVariableA("SC3DATAVIEW_TEST_RAD", v, sizeof(v)) || sscanf(v, "%d,%d", &cx, &cz) != 2) return;
    if (!(c = city_get()) || !(pl = (void *)vc(c, 0x16c, 0, 0, 0, 0, 0))) return;
    done = 1;
    for (x = cx - 6; x <= cx + 6; x++) for (z = cz - 6; z <= cz + 6; z++)
        if ((x - cx) * (x - cx) + (z - cz) * (z - cz) <= 36 && x >= 0 && z >= 0) { vc(pl, 0x94, 3, (DWORD)x, (DWORD)z, 1, 0); n++; }
    logf("B> TEST: %d cells around (%d,%d) set radioactive (SC3DATAVIEW_TEST_RAD)", n, cx, cz);
}

static void measure_b(BYTE *obj) {
    BYTE *c = city_get();
    void *zl, *pl;
    int W = *(int *)(obj + 0x10), H = *(int *)(obj + 0x14), x, z, shown = 0;
    long n = 0, nm = 0, nz = 0, na = 0, nf = 0, mz = 0, ma = 0, mf = 0, mzt = 0, mnone = 0;
    static long zh[256];
    char line[600];
    int len = 0, i;
    if (!c) return;
    __try {   /* where the mask comes from: 0x1000e4cc reads (*(obj+0x3c))+0x1c -> vt+0x54(x, z) */
        BYTE *own = *(BYTE **)(obj + 0x3c), *sub = own ? *(BYTE **)(own + 0x1c) : NULL;
        DWORD *svt = sub ? *(DWORD **)sub : NULL;
        logf("B> owner 0x%08lX vt SIMECO+0x%lx, owner+0x1c 0x%08lX vt SIMECO+0x%lx, its +0x54 SIMECO+0x%lx +0x58 SIMECO+0x%lx, "
             "city pollution layer 0x%08lX", (DWORD)own, own ? *(DWORD *)own - (DWORD)g_eco : 0, (DWORD)sub,
             svt ? (DWORD)svt - (DWORD)g_eco : 0, svt ? svt[0x54 / 4] - (DWORD)g_eco : 0, svt ? svt[0x58 / 4] - (DWORD)g_eco : 0,
             vc(c, 0x16c, 0, 0, 0, 0, 0));
    } __except (EXCEPTION_EXECUTE_HANDLER) { logf("B> FAULT reading the owner"); }
    zl = (void *)vc(c, 0x14c, 0, 0, 0, 0, 0);
    pl = (void *)vc(c, 0x16c, 0, 0, 0, 0, 0);
    if (!zl || !pl || W <= 0 || H <= 0) return;
    if ((long)W * H > 300000 && g_measure < 2) { logf("B> measure skipped on %dx%d (SC3DATAVIEW_MEASURE=2 forces)", W, H); return; }
    memset(zh, 0, sizeof(zh));
    for (x = 0; x < W; x++) for (z = 0; z < H; z++) {
        DWORD col = 0, f;
        int m = (BYTE)vc(obj, 0x48, 3, (DWORD)x, (DWORD)z, (DWORD)&col, 0) != 0;
        int zn = zone_at(zl, x, z), ac = active_at(pl, x, z), zt = zone_at(zl, z, x);
        f = fill_at(pl, x, z);
        n++;
        if (zn == 17) nz++;
        if (ac) na++;
        if (f & 0x7fff) nf++;
        if (!m) continue;
        nm++;
        zh[zn & 0xff]++;
        if (zn == 17) mz++;
        if (zt == 17) mzt++;
        if (ac) ma++;
        if (f & 0x7fff) mf++;
        if (zn != 17 && !ac && !(f & 0x7fff)) mnone++;
        if (shown < 8) { logf("B>   mask cell (%d,%d): zone %d active %d fill %lu (0x%08lx) colour 0x%04lx", x, z, zn, ac, f, f, col); shown++; }
    }
    logf("B> 0x2735 measured on %dx%d: mask %ld cells | zone17 %ld, active landfill %ld, fill>0 %ld | mask&zone17 %ld, "
         "mask&active %ld, mask&fill>0 %ld, mask&zone17(transposed) %ld, mask with none of the three %ld",
         W, H, nm, nz, na, nf, mz, ma, mf, mzt, mnone);
    for (i = 0; i < 256; i++) if (zh[i]) len += _snprintf(line + len, sizeof(line) - len - 1, " z%d:%ld", i, zh[i]);
    line[len < (int)sizeof(line) ? len : (int)sizeof(line) - 1] = 0;
    logf("B>   zone of mask cells:%s", nm ? line : " (none)");
}

static void measure_trips(BYTE *tl, int W, int H) {
    long t = 0, ok = 0, fail = 0, road = 0, hwy = 0, sub = 0, nz[3] = { 0, 0, 0 };
    int x, z, mx[3] = { 0, 0, 0 }, k;
    static const DWORD offs[3] = { 0x6c, 0x70, 0x74 };
    static const WORD masks[3] = { 0x15, 2, 8 };
    __try {
        for (x = 0; x < W; x++) for (z = 0; z < H; z++) {
            int r = trip_at(tl, x, z);
            WORD nb = net_at(tl, x, z);
            if (r != 2) { t++; if (r == 0) ok++; else fail++; }
            if (nb & 0x15) road++;
            if (nb & 2) hwy++;
            if (nb & 8) sub++;
            for (k = 0; k < 3; k++) if (nb & masks[k]) {
                int v = cong_at(tl, offs[k], x, z);
                if (v) nz[k]++;
                if (v > mx[k]) mx[k] = v;
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) { logf("TRAF> FAULT reading the grids"); return; }
    logf("TRAF> cells with a trip result %ld: ok %ld, failed %ld | network cells road %ld highway %ld subway %ld | cap %d",
         t, ok, fail, road, hwy, sub, *(BYTE *)(g_st + ST_CAP));
    logf("TRAF> congestion on its own network: road %ld cells > 0 (max %d), highway %ld (max %d), subway %ld (max %d)",
         nz[0], mx[0], nz[1], mx[1], nz[2], mx[2]);
}

/* ============================================================ key */

static int visible_panel(void) {
    int i;
    for (i = 0; i < g_ne; i++)
        if (g_ent[i].iface && ent_alive(&g_ent[i]) && view_visible(g_ent[i].iface)) return g_ent[i].panel;
    return -1;
}

static int on_key(void) {
    int p, i;
    ent_sweep();
    p = visible_panel();
    if (p < 0 || p == P_TRANS) return 0;
    if (p == P_POLL) g_mode[p] = (g_mode[p] + 1) % 2;
    else g_mode[p] = (g_mode[p] + 1) % 5;
    logf("KEY> panel %s -> %s", p == P_POLL ? "Contaminacion" : "Trafico",
         p == P_POLL ? k_name_poll[g_mode[p]] : k_name_traf[g_mode[p]]);
    apply_panel(p);
    caption_panel(p);
    for (i = 0; i < g_ne; i++) {
        Ent *e = &g_ent[i];
        if (!e->iface || e->panel != p || !view_visible(e->iface)) continue;
        if (p == P_POLL && g_mode[p] == 1) test_rad();
        if (p == P_POLL && g_mode[p] == 1 && g_measure) { __try { measure_b(e->obj); } __except (EXCEPTION_EXECUTE_HANDLER) { logf("B> FAULT measuring"); } break; }
        if (p == P_TRAF && g_mode[p] >= 1 && e->id == ID_TRIPS) { measure_trips(*(BYTE **)(e->obj + 0x40), *(int *)(e->obj + 0x10), *(int *)(e->obj + 0x14)); break; }
    }
    return 1;
}

/* ============================================================ H: health / education capacity on the Cuadros page
 * The Cuadros page fill SIMUI 0x100245c7 (this, page window) reads the page's tab radios (child 5, iid 0xa1336cc0
 * vt+0x30): 6 Educacion -> 0x100212d4, 7 Electricidad, 8 Basura, 9 Salud -> 0x10022a13, 10 Poblacion [CONFIRMED].
 * After it runs, on tabs 6 and 9 a column of labels goes left of the radios. Data: the residential layer, city +0xe4,
 * vtable SIMRCI 0x1004c99c (GZCOM catalogue s10, field getters): strike flags +0x650 school / +0x651 college /
 * +0x652 health, ratings +0x660 / +0x661 / +0x662, patients +0x664 / health capacity +0x668, school students +0x66c /
 * capacity +0x670, college students +0x674 / capacity +0x678, teachers +0x684, professors +0x688, doctors +0x68c. */
#define H_ID   0x0DA7A100
#define H_N    9
static void *g_tramp_tabs;

static void h_num(char *o, long v) {   /* 9.500, 12,3K, 1,2M */
    if (v < 0) v = 0;
    if (v < 10000) { if (v >= 1000) wsprintfA(o, "%ld.%03ld", v / 1000, v % 1000); else wsprintfA(o, "%ld", v); }
    else if (v < 1000000) { long d = (v + 50) / 100; if (d % 10) wsprintfA(o, "%ld,%ldK", d / 10, d % 10); else wsprintfA(o, "%ldK", d / 10); }
    else { long d = (v + 50000) / 100000; if (d % 10) wsprintfA(o, "%ld,%ldM", d / 10, d % 10); else wsprintfA(o, "%ldM", d / 10); }
}
/* two lines: "<what> 87%" and "   44,5K de 51K" (a 150 px column) */
static void h_pair(char *o1, char *o2, const char *what, long used, long cap) {
    char a[16], b[16];
    h_num(a, used); h_num(b, cap);
    if (cap > 0) wsprintfA(o1, "%s %ld%%", what, (long)((used * 100.0) / cap + 0.5));
    else wsprintfA(o1, SC3TR(1, "dataview.no_places", "%s: sin plazas", "%s: no places"), what);
    wsprintfA(o2, SC3TR(1, "dataview.used_of_cap", "   %s de %s", "   %s of %s"), a, b);
}

static void h_update(BYTE *page, int tab) {
    BYTE *c = city_get(), *rl;
    HMODULE rci = GetModuleHandleA("SIMRCI.DLL");
    char ln[H_N][64];
    int n = 0, i;
    static int last_tab = -1;
    static char last[H_N * 64];
    WORD col;
    memset(ln, 0, sizeof(ln));
    if ((tab == 6 || tab == 9) && c && rci) {
        rl = *(BYTE **)(c + 0xe4);
        if (!rl || IsBadReadPtr(rl, 0x690) || *(DWORD *)rl != (DWORD)rci + 0x4c99c) { logf("H> city +0xe4 is not the residential layer"); rl = NULL; }
        if (rl && tab == 6) {
            char nb[16];
            lstrcpynA(ln[n++], SC3TR(1, "dataview.pupils_places", "Alumnos / plazas", "Pupils / places"), 64);
            h_pair(ln[n], ln[n + 1], SC3TR(1, "dataview.school", "Escuela", "School"), *(LONG *)(rl + 0x66c), *(LONG *)(rl + 0x670)); n += 2;
            h_pair(ln[n], ln[n + 1], SC3TR(1, "dataview.college", "Universidad", "College"), *(LONG *)(rl + 0x674), *(LONG *)(rl + 0x678)); n += 2;
            h_num(nb, *(LONG *)(rl + 0x684)); wsprintfA(ln[n++], SC3TR(1, "dataview.teachers", "Docentes %s", "Teachers %s"), nb);
            h_num(nb, *(LONG *)(rl + 0x688)); wsprintfA(ln[n++], SC3TR(1, "dataview.professors", "Profesores %s", "Professors %s"), nb);
            wsprintfA(ln[n++], SC3TR(1, "dataview.strike", "Huelga: %s", "Strike: %s"),
                      rl[0x650] && rl[0x651] ? SC3TR(1, "dataview.strike_both", "escuela y universidad", "school and college") :
                      rl[0x650] ? SC3TR(1, "dataview.strike_school", "escuela", "school") :
                      rl[0x651] ? SC3TR(1, "dataview.strike_college", "universidad", "college") : SC3TR(1, "dataview.no", "no", "no"));
        } else if (rl) {
            char nb[16];
            lstrcpynA(ln[n++], SC3TR(1, "dataview.patients_capacity", "Pacientes / capacidad", "Patients / capacity"), 64);
            h_pair(ln[n], ln[n + 1], SC3TR(1, "dataview.hospitals", "Hospitales", "Hospitals"), *(LONG *)(rl + 0x664), *(LONG *)(rl + 0x668)); n += 2;
            h_num(nb, *(LONG *)(rl + 0x68c)); wsprintfA(ln[n++], SC3TR(1, "dataview.doctors", "M\xe9" "dicos %s", "Doctors %s"), nb);
            wsprintfA(ln[n++], SC3TR(1, "dataview.strike", "Huelga: %s", "Strike: %s"),
                      rl[0x652] ? SC3TR(1, "dataview.yes", "s\xed", "yes") : SC3TR(1, "dataview.no", "no", "no"));
        }
        if (rl && (tab != last_tab || memcmp(last, ln, sizeof(last)))) {
            logf("H> tab %d: raw school %ld/%ld college %ld/%ld health %ld/%ld teachers %ld profs %ld doctors %ld strikes %d %d %d "
                 "ratings %d %d %d", tab, *(LONG *)(rl + 0x66c), *(LONG *)(rl + 0x670), *(LONG *)(rl + 0x674),
                 *(LONG *)(rl + 0x678), *(LONG *)(rl + 0x664), *(LONG *)(rl + 0x668), *(LONG *)(rl + 0x684),
                 *(LONG *)(rl + 0x688), *(LONG *)(rl + 0x68c), rl[0x650], rl[0x651], rl[0x652], rl[0x660], rl[0x661], rl[0x662]);
            logf("H> page 0x%08lX local [%ld %ld %ld %ld]", (DWORD)page, *(LONG *)(page + 0x80), *(LONG *)(page + 0x84),
                 *(LONG *)(page + 0x88), *(LONG *)(page + 0x8c));
            memcpy(last, ln, sizeof(last));
        }
    }
    last_tab = tab;
    col = ui_col(0x20, 0x28, 0x70);
    for (i = 0; i < H_N; i++) {
        if (i < n) ui_label(page, H_ID + i, ln[i], col, 6, 260 + i * 15, 150, 14);
        else ui_show(ui_child(page, H_ID + i), 0);
    }
}

static int page_tab(BYTE *page) {
    void *g = (void *)vc(page, 0x78, 1, 5, 0, 0, 0), *r = NULL;
    int t;
    if (!g || !(vc(g, 0x00, 2, 0xa1336cc0, (DWORD)&r, 0, 0) & 0xff) || !r) return -1;
    t = (int)vc(r, 0x30, 0, 0, 0, 0, 0);
    vc(r, 0x08, 0, 0, 0, 0, 0);
    return t;
}

/* SIMUI 0x100245c7, thiscall(this, page), ret 4 */
static void __fastcall dv_tabs(BYTE *self, void *edx, BYTE *page) {
    DWORD a[1];
    (void)edx;
    a[0] = (DWORD)page;
    thiscall_n(self, g_tramp_tabs, a, 1);
    __try { h_update(page, page_tab(page)); } __except (EXCEPTION_EXECUTE_HANDLER) { logf("H> FAULT 0x%08lX", GetExceptionCode()); }
}

static int hook_tabs(void) {
    static const BYTE k_pro[7] = { 0x55, 0x8b, 0xec, 0x56, 0x8b, 0x75, 0x08 };
    BYTE *at = g_sui + 0x245c7, *t;
    DWORD old;
    if (memcmp(at, k_pro, 7)) { logf("H> REFUSED: SIMUI+0x245c7 is not the anchored prologue"); return 0; }
    t = (BYTE *)VirtualAlloc(NULL, 16, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!t) return 0;
    memcpy(t, k_pro, 7);
    t[7] = 0xe9; *(DWORD *)(t + 8) = (DWORD)(at + 7) - (DWORD)(t + 12);
    g_tramp_tabs = t;
    if (!VirtualProtect(at, 7, PAGE_EXECUTE_READWRITE, &old)) return 0;   /* left writable: mod startup races */
    at[5] = 0x90; at[6] = 0x90;
    *(DWORD *)(at + 1) = (DWORD)dv_tabs - (DWORD)(at + 5);
    InterlockedExchange((LONG *)at, *(LONG *)at & 0xffffff00 | 0xe9);
    FlushInstructionCache(GetCurrentProcess(), at, 7);
    return 1;
}

static WNDPROC g_oldproc;
static int g_ate_char;

static LRESULT CALLBACK dv_wndproc(HWND h, UINT m, WPARAM wp, LPARAM lp) {
    if (!g_oldproc) return DefWindowProcA(h, m, wp, lp);
    if (m == WM_KEYDOWN && (int)wp == g_key && GetKeyState(VK_CONTROL) >= 0 && GetKeyState(VK_MENU) >= 0 &&
        GetKeyState(VK_SHIFT) >= 0 && !text_focus()) {
        if (lp & 0x40000000) return g_ate_char ? 0 : CallWindowProcA(g_oldproc, h, m, wp, lp);
        g_ate_char = on_key();
        if (g_ate_char) return 0;
    }
    if (m == WM_CHAR && g_ate_char && ((int)wp == g_key || (int)wp == g_key + 0x20)) { g_ate_char = 0; return 0; }
    return CallWindowProcA(g_oldproc, h, m, wp, lp);
}

/* ============================================================ install */

static int patch_slot(DWORD *slot, DWORD v) {
    DWORD old;
    if (!VirtualProtect(slot, 4, PAGE_EXECUTE_READWRITE, &old)) return 0;   /* left writable: mod startup races */
    InterlockedExchange((LONG *)slot, (LONG)v);
    return 1;
}

static BOOL CALLBACK find_game_window(HWND h, LPARAM p) {
    DWORD pid = 0;
    char cls[32];
    GetWindowThreadProcessId(h, &pid);
    if (pid != GetCurrentProcessId()) return TRUE;
    if (!GetClassNameA(h, cls, sizeof(cls)) || lstrcmpA(cls, "Gonzo")) return TRUE;
    *(HWND *)p = h;
    return FALSE;
}

static DWORD WINAPI watcher(LPVOID unused) {
    HWND h = NULL;
    DWORD *vt;
    static const BYTE k_rgb[5] = { 0xe8, 0x2c, 0x99, 0xff, 0xff };
    (void)unused;
    while (!h) { Sleep(20); EnumWindows(find_game_window, (LPARAM)&h); }
    while (!(g_sui = (BYTE *)GetModuleHandleA("SIMUI.DLL")) || !(g_eco = (BYTE *)GetModuleHandleA("SIMECO.DLL")) ||
           !(g_st = (BYTE *)GetModuleHandleA("SimTransit.dll"))) Sleep(20);
    vt = (DWORD *)(g_sui + SUI_IFACE_VT);
    if (vt[0x98 / 4] != (DWORD)g_sui + SUI_ADD) {
        logf("### REFUSED: map view layer interface +0x98 is 0x%08lX, expected SIMUI+0x%lx", vt[0x98 / 4], SUI_ADD);
        return 0;
    }
    if (memcmp(g_eco + ECO_RGB, k_rgb, 5) || *(DWORD *)(g_eco + ECO_BASE_VT + 0x48) != (DWORD)g_eco + 0x18569) {
        logf("### REFUSED: SIMECO is not the anchored build (colour fn / base vtable differ)");
        return 0;
    }
    g_orig_add = (void *)vt[0x98 / 4];
    if (!patch_slot(&vt[0x98 / 4], (DWORD)dv_add)) { logf("### REFUSED: VirtualProtect on SIMUI vtable"); return 0; }
    logf("### AddLayer hooked (SIMUI+0x%lx +0x98), pollution=%d traffic=%d key=%d measure=%d", SUI_IFACE_VT, g_pollution,
         g_traffic, g_key, g_measure);
    if (g_hnum) logf("### Cuadros page numbers %s", hook_tabs() ? "hooked (SIMUI+0x245c7)" : "NOT hooked");
    if (g_transit) logf("### Mapa de transporte publico %s", tp_install() ? "on (Ver datos slot 10, SIMUI+0x4436b)" : "NOT installed");
    Sleep(500);
    g_oldproc = (WNDPROC)GetWindowLongA(h, GWL_WNDPROC);
    {   WNDPROC prev = (WNDPROC)SetWindowLongA(h, GWL_WNDPROC, (LONG)dv_wndproc);
        if (prev && prev != g_oldproc) g_oldproc = prev; }
    logf("### window 0x%08lX subclassed (old proc 0x%08lX)", (DWORD)h, (DWORD)g_oldproc);
    return 0;
}

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        char path[MAX_PATH];
        int on = 1;
        if (!sc3mods_guard(inst, "sc3dataview")) return TRUE;
        g_self = (HMODULE)inst;
        DisableThreadLibraryCalls(inst);
        InitializeCriticalSection(&g_lock);
        QueryPerformanceFrequency(&g_freq);
        QueryPerformanceCounter(&g_t0);
        if (!GetEnvironmentVariableA("SC3DATAVIEW_LOG", path, sizeof(path))) self_path(path, sizeof(path), "sc3dataview.log");
        g_log = CreateFileA(path, GENERIC_WRITE, FILE_SHARE_READ, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        env_int("SC3DATAVIEW", &on);
        ini_read();
        logf("### sc3dataview loaded, enabled=%d", on);
        if (!on) return TRUE;
        CreateThread(NULL, 0, watcher, NULL, 0, NULL);
    }
    return TRUE;
}
