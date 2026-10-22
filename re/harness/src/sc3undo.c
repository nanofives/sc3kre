/* sc3undo.c - undo / redo of the last few actions while the game is PAUSED (owner request 2026-10-20).
 *
 * DEFAULT = OPERATION JOURNAL (instant; "operation journal" section below): while a tool's Apply runs, the game's own
 * occupant Insert / Remove, zone cell and terrain writes are logged, and Undo / Redo replay them in 0-15 ms. Covers
 * zoning, every network tool, building plops and the bulldozer. Evidence: verify/undo_mod/RESULTS.md.
 *
 * Version 1 (undo by a full save / load per click, ~1.3 s per click, ~6 s on a live screen; owner rejected it
 * 2026-10-20) was removed 2026-10-21. Its evidence stays in verify/undo_spike/RESULTS.md and git history.
 * The game's own Save command (game_cmd) is kept for the SC3UNDO_TEST save command.
 *
 * Map click = the engine's own find-window-at-point (root = *(*(*(GZGraphicD+0x6cdb8)+0x30)+0x38), root
 * vt+0x8c(x, y), re/tools/frida_hittest.py) returns the city view window (vtable SIMSPR+0x676AC); the test drag
 * checks it. Tool modes: 2 demolish, 4 a build tool, 1 the query tool / Ctrl.
 *
 * Buttons: Undo / Redo, the minimap's rotate arrows shrunk to 18x20, in the minimap panel's bottom corners (default,
 *          "minimap placement" below) or full size in the bottom bar (placement=bar, "bottom-bar buttons").
 * Config: undo.ini beside the DLL: [undo] enabled=1 steps=10 keys=1 buttons=1 placement=minimap|bar
 *         button_x=-1 button_y=-1 (parent-local, -1 = default) lang=es|en
 * Env:    SC3UNDO_LOG=<abs path>
 *         SC3UNDO_TEST=1: test commands on WM_APP+0x5d0 (wParam 10 = post GZ command lParam, i.e. pick a tool;
 *         11 = log city, name, tool mode, journal; 12 = GZ-event drag from lParam (y << 16 | x); 13 = save the city to
 *         <tmp>	est_<lParam>.sc3) and a log line per paused left click. Driver: re/tools/undo/savecheck.py
 *         SC3UNDO_OPLOG=1: log every op of an entry when it is replayed
 *         SC3UNDO_TFIX=0: a network terrain fix inside an action clears the history again (the pre-2026-10-21 rule)
 * Build:  re/harness/build_undo.ps1. Ships via mods_launch.exe.
 */
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

static CRITICAL_SECTION g_lock;
static HANDLE g_log = INVALID_HANDLE_VALUE;
static LARGE_INTEGER g_freq, g_t0;
static HMODULE g_self;

static void logf(const char *fmt, ...) {
    char buf[1536], line[1700];
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
                  (double)(now.QuadPart - g_t0.QuadPart) * 1000.0 / (double)g_freq.QuadPart,
                  GetCurrentThreadId(), buf);
    if (n < 0) return;
    EnterCriticalSection(&g_lock);
    if (g_log != INVALID_HANDLE_VALUE) WriteFile(g_log, line, (DWORD)n, &wrote, NULL);
    LeaveCriticalSection(&g_lock);
}

static void self_path(char *out, int cap, const char *leaf) {
    char *slash;
    if (!GetModuleFileNameA(g_self, out, cap)) { out[0] = 0; return; }
    slash = strrchr(out, '\\');
    if (slash) slash[1] = 0; else out[0] = 0;
    lstrcatA(out, leaf);
}

/* ------------------------------------------------------------------ config */
#define MAXSTEPS 50
static int g_enabled = 1, g_steps = 10, g_keys = 1, g_test;
static int g_buttons = 1, g_btn_x = -1, g_btn_y = -1, g_lang_es = 1, g_on_bar;

static void ini_read(void) {
    char path[MAX_PATH];
    self_path(path, sizeof(path), "undo.ini");
    if (!path[0]) return;
    g_enabled = GetPrivateProfileIntA("undo", "enabled", 1, path) ? 1 : 0;
    g_steps   = GetPrivateProfileIntA("undo", "steps", 10, path);
    g_keys    = GetPrivateProfileIntA("undo", "keys", 1, path) ? 1 : 0;
    g_buttons = GetPrivateProfileIntA("undo", "buttons", 1, path) ? 1 : 0;
    g_btn_x   = GetPrivateProfileIntA("undo", "button_x", -1, path);
    g_btn_y   = GetPrivateProfileIntA("undo", "button_y", -1, path);
    {   char v[16]; GetPrivateProfileStringA("undo", "placement", "minimap", v, sizeof(v), path); g_on_bar = !lstrcmpiA(v, "bar"); }
    {   char v[8]; GetPrivateProfileStringA("undo", "lang", "es", v, sizeof(v), path); g_lang_es = lstrcmpiA(v, "en") != 0; }
    if (g_steps < 1) g_steps = 1;
    if (g_steps > MAXSTEPS - 1) g_steps = MAXSTEPS - 1;
}

/* ------------------------------------------------------------------ engine access */
static BYTE *g_exe;

static void *vslot(void *obj, unsigned off) {
    void **vt;
    if (!obj || IsBadReadPtr(obj, 4)) return NULL;
    vt = *(void ***)obj;
    if (!vt || IsBadReadPtr(vt, off + 4)) return NULL;
    return vt[off / 4];
}

/* the loaded city (SIMCITY+0x13260 vtable checked), or NULL */
static BYTE *city_get(void) {
    HMODULE simcity = GetModuleHandleA("SIMCITY.DLL");
    BYTE *app, *city;
    if (!simcity) return NULL;
    __try {
        app = *(BYTE **)(g_exe + 0xfa86c);
        if (!app) return NULL;
        city = *(BYTE **)(app + 0x48);
        if (!city || *(DWORD *)city != (DWORD)simcity + 0x13260) return NULL;
        return city;
    } __except (EXCEPTION_EXECUTE_HANDLER) { return NULL; }
}
static int city_paused(BYTE *city) { return city && *(long *)(city + 0x140) > 0; }

typedef void *(__cdecl *PFN_GetWinMgr)(void);
typedef void *(__fastcall *PFN_Get0)(void *, void *);
static void *win_root(void) {
    void *wm = ((PFN_GetWinMgr)(g_exe + 0x703A7))();        /* SC3U 0x004703a7 */
    PFN_Get0 gr = wm ? (PFN_Get0)vslot(wm, 0x0c) : NULL;
    return gr ? gr(wm, NULL) : NULL;
}
static void *find_by_vtable(void *win, DWORD vt, int depth) {
    DWORD *w = (DWORD *)win, sentinel, node;
    int guard = 0;
    if (!win || IsBadReadPtr(win, 0xd8) || depth > 12) return NULL;
    if (w[0] == vt) return win;
    sentinel = w[0x34 / 4];
    if (!sentinel || IsBadReadPtr((void *)sentinel, 0xc)) return NULL;
    for (node = *(DWORD *)sentinel; node && node != sentinel && guard < 200; node = *(DWORD *)node, guard++) {
        void *hit;
        if (IsBadReadPtr((void *)node, 0xc)) break;
        hit = find_by_vtable(*(void **)(node + 8), vt, depth + 1);
        if (hit) return hit;
    }
    return NULL;
}
/* the city view's PRIMARY object (vtable SIMSPR+0x67894), found from its cIGZWin subobject in the tree */
static BYTE *city_view(void) {
    HMODULE spr = GetModuleHandleA("SIMSPR.DLL");
    BYTE *win, *view;
    if (!spr) return NULL;
    __try {
        win = (BYTE *)find_by_vtable(win_root(), (DWORD)spr + 0x676AC, 0);
        if (!win) return NULL;
        view = win - 4;
        if (IsBadReadPtr(view, 0x230) || *(DWORD *)view != (DWORD)spr + 0x67894) return NULL;
        return view;
    } __except (EXCEPTION_EXECUTE_HANDLER) { return NULL; }
}
static long tool_mode(BYTE *view) { return view ? *(long *)(view + 0x220) : 0; }

/* is client point (x, y) on the map? engine hit test, then compare with the city view window */
static int point_on_map(int x, int y) {
    HMODULE gz = GetModuleHandleA("GZGraphicD.dll"), spr = GetModuleHandleA("SIMSPR.DLL");
    typedef void *(__fastcall *PFN_Hit)(void *, void *, int, int);
    BYTE *w, *sink, *root, *hit;
    if (!gz || !spr) return 0;
    __try {
        w = *(BYTE **)((BYTE *)gz + 0x6cdb8);
        if (!w) return 0;
        sink = *(BYTE **)(w + 0x30);
        if (!sink) return 0;
        root = *(BYTE **)(sink + 0x38);
        if (!root || !vslot(root, 0x8c)) return 0;
        hit = (BYTE *)((PFN_Hit)vslot(root, 0x8c))(root, NULL, x, y);
        return hit && *(DWORD *)hit == (DWORD)spr + 0x676AC;
    } __except (EXCEPTION_EXECUTE_HANDLER) { return 0; }
}

/* post {id, a0, 0, 0} through the framework message server (sc3resize rz_city_post) */
static int gz_post(DWORD id, DWORD a0) {
    typedef int (__fastcall *GETSVC)(void *, void *, DWORD, DWORD, void **);
    typedef int (__fastcall *POST)(void *, void *, DWORD *, int);
    HMODULE gzsvc = GetModuleHandleA("GZServiceD.dll");
    void *fw, *srv = NULL;
    DWORD msg[4];
    if (!gzsvc) return 0;
    __try {
        fw = *(void **)(g_exe + 0xFAB74);
        if (!fw) return 0;
        ((GETSVC)vslot(fw, 0x10))(fw, NULL, 0x64063387, 0xC1085722, &srv);
        if (!srv || *(DWORD *)srv != (DWORD)gzsvc + 0x14618) return 0;
        msg[0] = id; msg[1] = a0; msg[2] = msg[3] = 0;
        ((POST)vslot(srv, 0x10))(srv, NULL, msg, 0);
    } __except (EXCEPTION_EXECUTE_HANDLER) { return 0; }
    return 1;
}

/* city file name: copy out of the embedded string, put back through a two-slot fake cIGZString */
static char g_name[MAX_PATH];
static int  g_name_len;
static const char *__fastcall fs_data(void *self) { (void)self; return g_name; }
static DWORD __fastcall fs_len(void *self) { (void)self; return (DWORD)g_name_len; }
static void *g_fs_vt[8];
static void *g_fs_obj = g_fs_vt;
static void name_save(BYTE *city) {
    typedef BYTE *(__fastcall *PFN_GetName)(void *, void *);
    BYTE *s;
    char *b, *e;
    g_name_len = -1;
    __try {
        s = ((PFN_GetName)vslot(city, 0x254))(city, NULL);               /* SIMCITY 0x10007116 -> city+0x15c */
        b = *(char **)(s + 4); e = *(char **)(s + 8);
        if (b && e >= b && e - b < MAX_PATH) { memcpy(g_name, b, e - b); g_name_len = (int)(e - b); g_name[g_name_len] = 0; }
    } __except (EXCEPTION_EXECUTE_HANDLER) { g_name_len = -1; }
}
static void name_restore(BYTE *city) {
    typedef void (__fastcall *PFN_SetName)(void *, void *, void *);
    void *obj = &g_fs_obj;
    if (g_name_len < 0 || !city) return;
    g_fs_vt[6] = (void *)fs_data;                                        /* vt+0x18 */
    g_fs_vt[7] = (void *)fs_len;                                         /* vt+0x1c */
    __try { ((PFN_SetName)vslot(city, 0x258))(city, NULL, obj); }      /* SIMCITY 0x1000713b */
    __except (EXCEPTION_EXECUTE_HANDLER) { logf("name_restore threw 0x%08lX", GetExceptionCode()); }
}

/* the game's own Save / Load commands, game thread only */
typedef void *(__cdecl    *PFN_GNew)(unsigned);
typedef void *(__cdecl    *PFN_GDir)(void);
typedef DWORD (__fastcall *PFN_GCreate)(void *, void *, DWORD, DWORD, void **);
typedef DWORD (__fastcall *PFN_GV0)(void *, void *);
typedef DWORD (__fastcall *PFN_GV1)(void *, void *, void *);
typedef void  (__fastcall *PFN_GVarCtor)(void *);
typedef void  (__fastcall *PFN_GVarU)(void *, void *, DWORD, DWORD);
typedef void  (__fastcall *PFN_GVarB)(void *, void *, DWORD);
typedef void  (__fastcall *PFN_GVarS)(void *, void *, const char *, DWORD);
static void addarg(void *cmd, void *v) {
    ((PFN_GV0)vslot(v, 0x04))(v, NULL);
    ((PFN_GV1)vslot(cmd, 0x0c))(cmd, NULL, v);
    ((PFN_GV0)vslot(v, 0x08))(v, NULL);
}
static int game_cmd(int is_load, const char *path) {
    PFN_GNew gnew = (PFN_GNew)(g_exe + 0xB4890);                       /* operator_new, the game heap */
    PFN_GDir gdir = (PFN_GDir)(g_exe + 0x84573);                       /* COM director */
    void *dir, *cmd = NULL, *v;
    DWORD ok = 0;
    __try {
        dir = gdir();
        if (!dir) return 0;
        if (!(((PFN_GCreate)vslot(dir, 0x0c))(dir, NULL, is_load ? 0x610438A4 : 0x410438DD, 0x006856F7, &cmd) & 0xff) || !cmd)
            return 0;
        if (is_load) {
            v = gnew(0x28); ((PFN_GVarU)(g_exe + 0x6F260))(v, NULL, 0x83172AD7, 3); addarg(cmd, v);
            v = gnew(0x28); ((PFN_GVarB)(g_exe + 0x6F33F))(v, NULL, 0);            addarg(cmd, v);
        }
        v = gnew(0x28);
        ((PFN_GVarCtor)(g_exe + 0x6ECC0))(v);
        ((PFN_GVarS)(g_exe + 0x6F896))(v, NULL, path, (DWORD)strlen(path));
        addarg(cmd, v);
        ok = ((PFN_GV0)vslot(cmd, 0x2c))(cmd, NULL) & 0xff;
        ((PFN_GV0)vslot(cmd, 0x08))(cmd, NULL);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        logf("%s threw 0x%08lX", is_load ? "LOAD" : "SAVE", GetExceptionCode());
        return 0;
    }
    return (int)ok;
}

/* ------------------------------------------------------------------ test saves folder (%TEMP%\sc3undo_<pid>) */
static char  g_dir[MAX_PATH];
static volatile LONG g_busy;

/* ------------------------------------------------------------------ text focus (sc3resize KEYFOCUS) */
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


/* ------------------------------------------------------------------ bottom-bar buttons
 * The bar is SIMUI class 0x2f95d57, vtable SIMUI 0x100a40ec, built in code (FUN_10013ef3). Two slots are wrapped:
 *   +0x24  Init  FUN_10024a96 __thiscall(this) -> bool: after the stock Init, two image buttons are added.
 *   +0x1e0 child notify FUN_10026973 __thiscall(this, type, id), ret 8: a click arrives as (1, id). Stock handles
 *          only the "?" button (0x52fb5feb) and returns 0 for anything else.
 * Buttons are made the way the minimap makes its rotate buttons (SIMUI 0x1004faec): image {group 0x2f78c6d,
 * instance 0x22f96e30 / 0x22f96e2f} = the rotate anticlockwise / clockwise arrows (a 4-frame strip, 104x29, frame
 * 26x29), magenta key, factory FUN_10085065()->vt+0x30(id, caption, img, &rect, 0), btn vt+0x8c tooltip,
 * vt+0x24(4,0), vt+0x24(0x100,1), vt+0x98(0x1000000), window = btn vt+0x1c, bar vt+0x34 AddChild, window
 * vt+0xcc(x, y) parent-local move, btn vt+0x08 Release. Greyed = window vt+0xf4(2, 0); enabled = (2, 1).
 * A click is POSTED to the window (WM_UNDO_CMD) and run outside the bar's own handler: the load replaces the city
 * and its UI. */
#define BTN_UNDO 0x5D0A0001
#define BTN_REDO 0x5D0A0002
static void *g_bar_init_orig, *g_bar_notify_orig;

static DWORD tc(void *self, void *fn, const DWORD *a, int n) {
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
static DWORD vc(void *o, DWORD slot, int n, DWORD a0, DWORD a1, DWORD a2, DWORD a3, DWORD a4) {
    DWORD a[5];
    void *fn = vslot(o, slot);
    if (!fn) return 0;
    a[0] = a0; a[1] = a1; a[2] = a2; a[3] = a3; a[4] = a4;
    return tc(o, fn, a, n);
}
/* SIMUI's GZ string (ctor FUN_10005eb6, dtor FUN_10006057, vt+0x10 assign from char*) */
static void ui_str(BYTE *buf, const char *text) {
    BYTE *sui = (BYTE *)GetModuleHandleA("SIMUI.DLL");
    memset(buf, 0, 0x20);
    ((void (__fastcall *)(void *))(sui + 0x5eb6))(buf);
    if (text) vc(buf, 0x10, 1, (DWORD)text, 0, 0, 0, 0);
}
static void ui_str_free(BYTE *buf) { ((void (__fastcall *)(void *))((BYTE *)GetModuleHandleA("SIMUI.DLL") + 0x6057))(buf); }

static void *add_button(void *bar, DWORD id, DWORD art, const char *tip, LONG x, LONG y) {
    BYTE *sui = (BYTE *)GetModuleHandleA("SIMUI.DLL");
    DWORD key[3], img = 0;
    LONG rect[4] = { 0, 0, 0, 0 };
    BYTE cap[0x20], tt[0x20];
    void *fac, *btn, *win = NULL;
    int ok = 0;
    key[0] = 0; key[1] = 0x2f78c6d; key[2] = art;
    if (!((char (__cdecl *)(DWORD *, DWORD *, char))(sui + 0x25489))(key, &img, 1) || !img) {
        logf("BTN> art 0x%08lX not loaded", art); return NULL;
    }
    vc((void *)img, 0x40, 1, (DWORD)rect, 0, 0, 0, 0);
    fac = ((void *(__cdecl *)(void))(sui + 0x85065))();
    ui_str(cap, "");
    btn = fac ? (void *)vc(fac, 0x30, 5, id, (DWORD)cap, img, (DWORD)rect, 0) : NULL;
    if (btn) {
        ui_str(tt, tip);
        vc(btn, 0x8c, 1, (DWORD)tt, 0, 0, 0, 0);
        ui_str_free(tt);
        vc(btn, 0x24, 2, 4, 0, 0, 0, 0);
        vc(btn, 0x24, 2, 0x100, 1, 0, 0, 0);
        vc(btn, 0x98, 1, 0x1000000, 0, 0, 0, 0);
        win = (void *)vc(btn, 0x1c, 0, 0, 0, 0, 0, 0);
        ok = win && (vc(bar, 0x34, 1, (DWORD)win, 0, 0, 0, 0) & 0xff);
        if (ok) vc(win, 0xcc, 2, (DWORD)x, (DWORD)y, 0, 0, 0);
        vc(btn, 0x08, 0, 0, 0, 0, 0, 0);
    }
    ui_str_free(cap);
    vc((void *)img, 0x08, 0, 0, 0, 0, 0, 0);
    logf("BTN> 0x%08lX art 0x%08lX strip %ldx%ld at (%ld,%ld): %s", id, art, rect[2] - rect[0], rect[3] - rect[1], x, y,
         ok ? "added" : "FAILED");
    return ok ? win : NULL;
}

static void log_bar_children(void *bar) {
    BYTE *sui = (BYTE *)GetModuleHandleA("SIMUI.DLL");
    DWORD sentinel, node;
    LONG *r = (LONG *)((BYTE *)bar + 0x80);
    int guard = 0;
    logf("BAR> 0x%08lX local [%ld %ld %ld %ld]", (DWORD)bar, r[0], r[1], r[2], r[3]);
    sentinel = *(DWORD *)((BYTE *)bar + 0x34);
    if (!sentinel || IsBadReadPtr((void *)sentinel, 0xc)) return;
    for (node = *(DWORD *)sentinel; node && node != sentinel && guard < 40; node = *(DWORD *)node, guard++) {
        BYTE *ch = *(BYTE **)(node + 8);
        LONG *c;
        if (!ch || IsBadReadPtr(ch, 0xa4)) continue;
        c = (LONG *)(ch + 0x80);
        logf("BAR>   child vt SIMUI+0x%lX local [%ld %ld %ld %ld]", *(DWORD *)ch - (DWORD)sui, c[0], c[1], c[2], c[3]);
    }
}

static DWORD __fastcall bar_init(void *self, void *edx) {
    DWORD r;
    (void)edx;
    r = tc(self, g_bar_init_orig, NULL, 0);
    if (!(r & 0xff) || !g_buttons) return r;
    __try {
        LONG *br = (LONG *)((BYTE *)self + 0x80);
        LONG x = g_btn_x, y = g_btn_y;
        log_bar_children(self);
        /* default: the right end of the news ticker row. The bar 600x56 has no free 26x29 spot (children: ticker
           [8 6 481 20], pause [488 9 510 31], play [511 9 537 31], speed [489 29 537 52], "?" [547 11 587 50];
           the name / population / funds / date boxes are drawn by the bar itself), so the ticker (id 0x52FB5FEF)
           gives up 60 px and the arrows sit in it, centred on its row, above the date box. Done inside Init, before
           sc3resize BARKIDS records the children's native rects. */
        if (x < 0) {
            void *tk = (void *)vc(self, 0x78, 1, 0x52FB5FEF, 0, 0, 0, 0);
            LONG *tr = tk ? (LONG *)((BYTE *)tk + 0x80) : NULL;
            if (tr && tr[2] - tr[0] > 200) {
                LONG right = tr[2];
                vc(tk, 0xc8, 4, (DWORD)tr[0], (DWORD)tr[1], (DWORD)(right - 60), (DWORD)tr[3], 0);
                x = right - 60 + 3;
                logf("BTN> ticker [%ld %ld %ld %ld] -> right %ld", tr[0], tr[1], right, tr[3], right - 60);
                if (y < 0) y = (tr[1] + tr[3]) / 2 - 29 / 2;
            } else x = (br[2] - br[0]) - 2 * 26 - 4;
        }
        if (y < 0) y = 0;
        add_button(self, BTN_UNDO, 0x22f96e30, g_lang_es ? "Deshacer (Ctrl+Z)" : "Undo (Ctrl+Z)", x, y);
        add_button(self, BTN_REDO, 0x22f96e2f, g_lang_es ? "Rehacer (Ctrl+Y)" : "Redo (Ctrl+Y)", x + 26 + 2, y);
    } __except (EXCEPTION_EXECUTE_HANDLER) { logf("BTN> threw 0x%08lX", GetExceptionCode()); }
    return r;
}

static HWND g_hwnd;
#define WM_UNDO_CMD   (WM_APP + 0x5d0)        /* wParam 1 = undo, 2 = redo, 3 = clear (unpaused), 4 = refresh buttons */
static DWORD __fastcall bar_notify(void *self, void *edx, DWORD type, DWORD id) {
    DWORD a[2];
    (void)edx;
    if (type == 1 && (id == BTN_UNDO || id == BTN_REDO)) {
        logf("BTN> click %s", id == BTN_UNDO ? "undo" : "redo");
        if (g_hwnd) PostMessageA(g_hwnd, WM_UNDO_CMD, id == BTN_UNDO ? 1 : 2, 0);
        return 1;
    }
    a[0] = type; a[1] = id;
    return tc(self, g_bar_notify_orig, a, 2);
}

/* greyed / enabled to match what Undo and Redo can do now (game thread) */
static int g_btn_state = -1;
static void buttons_refresh(int can_undo, int can_redo) {
    BYTE *sui = (BYTE *)GetModuleHandleA("SIMUI.DLL");
    void *bar, *w;
    int st = (can_undo ? 1 : 0) | (can_redo ? 2 : 0);
    if (!sui || !g_buttons) return;
    __try {
        bar = find_by_vtable(win_root(), (DWORD)sui + (g_on_bar ? 0xa40ec : 0xaa180), 0);
        if (!bar) return;
        if ((w = (void *)vc(bar, 0x78, 1, BTN_UNDO, 0, 0, 0, 0)) != NULL) vc(w, 0xf4, 2, 2, can_undo ? 1 : 0, 0, 0, 0);
        if ((w = (void *)vc(bar, 0x78, 1, BTN_REDO, 0, 0, 0, 0)) != NULL) vc(w, 0xf4, 2, 2, can_redo ? 1 : 0, 0, 0, 0);
        if (st != g_btn_state) { logf("BTN> undo %s, redo %s", can_undo ? "on" : "greyed", can_redo ? "on" : "greyed"); g_btn_state = st; }
    } __except (EXCEPTION_EXECUTE_HANDLER) { }
}

static int patch_bar_vtable(HMODULE sui) {
    DWORD *vt = (DWORD *)((BYTE *)sui + 0xa40ec), old;
    if (vt[0x24 / 4] != (DWORD)sui + 0x24a96 || vt[0x1e0 / 4] != (DWORD)sui + 0x26973) {
        logf("BTN> REFUSED: bar vtable slots are 0x%08lX / 0x%08lX, expected SIMUI+0x24a96 / +0x26973",
             vt[0x24 / 4], vt[0x1e0 / 4]);
        return 0;
    }
    g_bar_init_orig = (void *)vt[0x24 / 4];
    g_bar_notify_orig = (void *)vt[0x1e0 / 4];
    /* 4 bytes at a time: a wider protect restored with one 'old' value can hit a neighbouring page in another
       state (measured: patching while SIMUI was still loading killed the game at ~0.4 s) */
    if (!VirtualProtect(&vt[0x24 / 4], 4, PAGE_EXECUTE_READWRITE, &old)) return 0;
    vt[0x24 / 4] = (DWORD)bar_init;
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    if (!VirtualProtect(&vt[0x1e0 / 4], 4, PAGE_EXECUTE_READWRITE, &old)) return 0;
    vt[0x1e0 / 4] = (DWORD)bar_notify;
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    logf("BTN> bar vtable SIMUI+0xa40ec: Init and child-notify wrapped");
    return 1;
}


/* ------------------------------------------------------------------ minimap placement (default, owner 2026-10-20:
 * "smaller buttons on the bottom of the minimap")
 * The minimap panel is SIMUI vtable 0x100aa180 (ctor FUN_1004f90f), 160x164. Init +0x24 = FUN_1004faec (it builds
 * the zoom / rotate / layers buttons), child notify +0x1e0 = FUN_1005093f thiscall(this, type, id) ret 8, which acts
 * only on its own ids. The buttons sit side by side under the map diamond's bottom tip, between the rotate buttons
 * at (34,120) and (100,120), 26x29 (the bottom-right corner holds a small box icon). The game has no arrow art smaller than the 26x29 rotate frames, and the image
 * button blits 1:1 (GZWIND FUN_10008958 -> GZGraphicD vt+0x118), so the strip is shrunk here into a new raster:
 * COM FUN_1008489d()->vt+0xc(0xc470d325, 0x20732180, &r) [as SIMUI FUN_1002ab98], r vt+0xc(w, h, code, bpp, 0,0,0,0)
 * = GZGraphicD FUN_10009efb with the source's {code, bpp} (vt+0x4c), lock vt+0x1c(0x40), bits vt+0x1a8, pitch
 * vt+0x1ac, unlock vt+0x20(0x40), colour key vt+0xc8(vt+0x18c(0xff,0,0xff)). Box filter per frame, magenta kept
 * transparent. */
#define SMALL_W 18
#define SMALL_H 20
static void *g_mm_init_orig, *g_mm_notify_orig;

static DWORD tc8(void *self, void *fn, DWORD a0, DWORD a1, DWORD a2, DWORD a3) {
    DWORD a[8];
    a[0] = a0; a[1] = a1; a[2] = a2; a[3] = a3; a[4] = a[5] = a[6] = a[7] = 0;
    return tc(self, fn, a, 8);
}

/* the rotate strip {0x2f78c6d, art} shrunk to 4 frames of SMALL_W x SMALL_H, or NULL (AddRef'd raster) */
static void *small_strip(DWORD art) {
    BYTE *sui = (BYTE *)GetModuleHandleA("SIMUI.DLL");
    DWORD key[3], src = 0, fmt[2] = { 0, 0 };
    void *com, *dst = NULL;
    BYTE *sb, *db;
    LONG sp, dp, sw, sh, fw, x, y, f;
    WORD key565;
    int locked_s = 0, locked_d = 0, ok = 0;
    key[0] = 0; key[1] = 0x2f78c6d; key[2] = art;
    if (!((char (__cdecl *)(DWORD *, DWORD *, char))(sui + 0x25489))(key, &src, 0) || !src) return NULL;
    __try {
        vc((void *)src, 0x4c, 1, (DWORD)fmt, 0, 0, 0, 0);
        sw = (LONG)vc((void *)src, 0x38, 0, 0, 0, 0, 0, 0);
        sh = (LONG)vc((void *)src, 0x3c, 0, 0, 0, 0, 0, 0);
        if (fmt[1] != 16 || (fmt[0] != 7 && fmt[0] != 5) || sw < 8 || sh < 8) {
            logf("BTN> strip 0x%08lX format {%lu,%lu} %ldx%ld: not shrunk", art, fmt[0], fmt[1], sw, sh);
            __leave;
        }
        key565 = fmt[0] == 7 ? 0xF81F : 0x7C1F;
        fw = sw / 4;
        com = ((void *(__cdecl *)(void))(sui + 0x8489d))();
        if (!com || !(vc(com, 0x0c, 3, 0xc470d325, 0x20732180, (DWORD)&dst, 0, 0) & 0xff) || !dst) __leave;
        if (!(tc8(dst, vslot(dst, 0x0c), 4 * SMALL_W, SMALL_H, fmt[0], fmt[1]) & 0xff)) __leave;
        if (!(vc((void *)src, 0x1c, 1, 0x40, 0, 0, 0, 0) & 0xff)) __leave;
        locked_s = 1;
        if (!(vc(dst, 0x1c, 1, 0x40, 0, 0, 0, 0) & 0xff)) __leave;
        locked_d = 1;
        sb = (BYTE *)vc((void *)src, 0x1a8, 0, 0, 0, 0, 0, 0); sp = (LONG)vc((void *)src, 0x1ac, 0, 0, 0, 0, 0, 0);
        db = (BYTE *)vc(dst, 0x1a8, 0, 0, 0, 0, 0, 0);         dp = (LONG)vc(dst, 0x1ac, 0, 0, 0, 0, 0, 0);
        if (!sb || !db || sp < sw * 2 || dp < 4 * SMALL_W * 2) __leave;
        for (f = 0; f < 4; f++)
            for (y = 0; y < SMALL_H; y++)
                for (x = 0; x < SMALL_W; x++) {
                    LONG x0 = f * fw + x * fw / SMALL_W, x1 = f * fw + ((x + 1) * fw + SMALL_W - 1) / SMALL_W;
                    LONG y0 = y * sh / SMALL_H, y1 = ((y + 1) * sh + SMALL_H - 1) / SMALL_H, xx, yy;
                    DWORD r = 0, g = 0, bl = 0, n = 0, m = 0;
                    WORD out;
                    for (yy = y0; yy < y1 && yy < sh; yy++)
                        for (xx = x0; xx < x1 && xx < (f + 1) * fw; xx++) {
                            WORD v = *(WORD *)(sb + yy * sp + xx * 2);
                            if (v == key565) { m++; continue; }
                            if (fmt[0] == 7) { r += v >> 11; g += (v >> 5) & 63; bl += v & 31; }
                            else             { r += (v >> 10) & 31; g += (v >> 5) & 31; bl += v & 31; }
                            n++;
                        }
                    if (!n || m > n) out = key565;
                    else if (fmt[0] == 7) out = (WORD)(((r / n) << 11) | ((g / n) << 5) | (bl / n));
                    else                  out = (WORD)(((r / n) << 10) | ((g / n) << 5) | (bl / n));
                    if (out == key565 && n && m <= n) out ^= 1;      /* a real colour must not become the key */
                    *(WORD *)(db + y * dp + (f * SMALL_W + x) * 2) = out;
                }
        ok = 1;
    } __except (EXCEPTION_EXECUTE_HANDLER) { logf("BTN> shrink threw 0x%08lX", GetExceptionCode()); ok = 0; }
    if (locked_d) vc(dst, 0x20, 1, 0x40, 0, 0, 0, 0);
    if (locked_s) vc((void *)src, 0x20, 1, 0x40, 0, 0, 0, 0);
    vc((void *)src, 0x08, 0, 0, 0, 0, 0, 0);
    if (!ok) { if (dst) vc(dst, 0x08, 0, 0, 0, 0, 0, 0); return NULL; }
    vc(dst, 0xc8, 1, vc(dst, 0x18c, 3, 0xff, 0, 0xff, 0, 0), 0, 0, 0, 0);
    return dst;
}

/* an image button from a ready raster (the minimap recipe, FUN_1004faec) */
static void *add_button_img(void *parent, DWORD id, void *img, const char *tip, LONG x, LONG y) {
    BYTE *sui = (BYTE *)GetModuleHandleA("SIMUI.DLL");
    LONG rect[4] = { 0, 0, 0, 0 };
    BYTE cap[0x20], tt[0x20];
    void *fac, *btn, *win = NULL;
    int ok = 0;
    vc(img, 0x40, 1, (DWORD)rect, 0, 0, 0, 0);
    fac = ((void *(__cdecl *)(void))(sui + 0x85065))();
    ui_str(cap, "");
    btn = fac ? (void *)vc(fac, 0x30, 5, id, (DWORD)cap, (DWORD)img, (DWORD)rect, 0) : NULL;
    if (btn) {
        ui_str(tt, tip);
        vc(btn, 0x8c, 1, (DWORD)tt, 0, 0, 0, 0);
        ui_str_free(tt);
        vc(btn, 0x24, 2, 4, 0, 0, 0, 0);
        vc(btn, 0x24, 2, 0x100, 1, 0, 0, 0);
        vc(btn, 0x98, 1, 0x1000000, 0, 0, 0, 0);
        win = (void *)vc(btn, 0x1c, 0, 0, 0, 0, 0, 0);
        ok = win && (vc(parent, 0x34, 1, (DWORD)win, 0, 0, 0, 0) & 0xff);
        if (ok) vc(win, 0xcc, 2, (DWORD)x, (DWORD)y, 0, 0, 0);
        vc(btn, 0x08, 0, 0, 0, 0, 0, 0);
    }
    ui_str_free(cap);
    logf("BTN> 0x%08lX strip %ldx%ld at minimap (%ld,%ld): %s", id, rect[2] - rect[0], rect[3] - rect[1], x, y,
         ok ? "added" : "FAILED");
    return ok ? win : NULL;
}

static DWORD __fastcall mm_init(void *self, void *edx) {
    DWORD r;
    (void)edx;
    r = tc(self, g_mm_init_orig, NULL, 0);
    if (!(r & 0xff) || !g_buttons) return r;
    __try {
        static const DWORD art[2] = { 0x22f96e30, 0x22f96e2f };
        static const DWORD ids[2] = { BTN_UNDO, BTN_REDO };
        LONG *pr = (LONG *)((BYTE *)self + 0x80), pw = pr[2] - pr[0], ph = pr[3] - pr[1];
        int i;
        logf("MINIMAP> panel 0x%08lX local [%ld %ld %ld %ld]", (DWORD)self, pr[0], pr[1], pr[2], pr[3]);
        for (i = 0; i < 2; i++) {
            void *img = small_strip(art[i]);
            /* side by side under the bottom tip of the map diamond (~(80,144)), between the rotate buttons
               (x 34..60 and 100..126): owner call 2026-10-20 "closer together near the bottom edge of the map".
               An 18 px gap is left between them (x 70..88): with north at the bottom, SIMUI 0x10050cb3 re-centres the
               "N" compass label at (79,142), and at 2 px apart it was drawn over the Undo button (measured 2026-10-21,
               verify/undo_leftovers/rot). */
            LONG x = i == 0 ? pw / 2 - 10 - SMALL_W : pw / 2 + 8, y = ph - 2 - SMALL_H;
            if (g_btn_x >= 0) x = g_btn_x + i * (SMALL_W + 4);
            if (g_btn_y >= 0) y = g_btn_y;
            if (!img) { DWORD key[3] = { 0, 0x2f78c6d, art[i] }, im = 0;   /* fall back to the full-size strip */
                if (((char (__cdecl *)(DWORD *, DWORD *, char))((BYTE *)GetModuleHandleA("SIMUI.DLL") + 0x25489))(key, &im, 1)) img = (void *)im; }
            if (!img) continue;
            add_button_img(self, ids[i], img, i == 0 ? (g_lang_es ? "Deshacer (Ctrl+Z)" : "Undo (Ctrl+Z)")
                                                     : (g_lang_es ? "Rehacer (Ctrl+Y)" : "Redo (Ctrl+Y)"), x, y);
            vc(img, 0x08, 0, 0, 0, 0, 0, 0);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) { logf("BTN> minimap threw 0x%08lX", GetExceptionCode()); }
    return r;
}

static DWORD __fastcall mm_notify(void *self, void *edx, DWORD type, DWORD id) {
    DWORD a[2];
    (void)edx;
    if (type == 1 && (id == BTN_UNDO || id == BTN_REDO)) {
        logf("BTN> click %s", id == BTN_UNDO ? "undo" : "redo");
        if (g_hwnd) PostMessageA(g_hwnd, WM_UNDO_CMD, id == BTN_UNDO ? 1 : 2, 0);
        return 1;
    }
    a[0] = type; a[1] = id;
    return tc(self, g_mm_notify_orig, a, 2);
}

static int patch_slot(DWORD *slot, DWORD val) {
    DWORD old;
    if (!VirtualProtect(slot, 4, PAGE_EXECUTE_READWRITE, &old)) return 0;
    *slot = val;
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    return 1;
}
static int patch_minimap_vtable(HMODULE sui) {
    DWORD *vt = (DWORD *)((BYTE *)sui + 0xaa180);
    if (vt[0x24 / 4] != (DWORD)sui + 0x4faec || vt[0x1e0 / 4] != (DWORD)sui + 0x5093f) {
        logf("BTN> REFUSED: minimap vtable slots are 0x%08lX / 0x%08lX, expected SIMUI+0x4faec / +0x5093f",
             vt[0x24 / 4], vt[0x1e0 / 4]);
        return 0;
    }
    g_mm_init_orig = (void *)vt[0x24 / 4];
    g_mm_notify_orig = (void *)vt[0x1e0 / 4];
    if (!patch_slot(&vt[0x24 / 4], (DWORD)mm_init) || !patch_slot(&vt[0x1e0 / 4], (DWORD)mm_notify)) return 0;
    logf("BTN> minimap vtable SIMUI+0xaa180: Init and child-notify wrapped");
    return 1;
}


/* ------------------------------------------------------------------ operation journal (default, owner 2026-10-20:
 * "i don't need to save everything, just the change, and it has to be instant"; order zoning, networks, buildings)
 * While a tool's Apply runs (paused only), every change the game makes through these primitives is logged:
 *   occupant Insert / Remove: SIMGEOM occupant manager vtable 0x10029e24 +0x3c 0x1000df50 / +0x48 0x1000e2c0,
 *        __thiscall(mgr, occ), ret 4. Network pieces are occupants, one per cell (SIMNTWRK writer FUN_100165d8);
 *        Insert/Remove notify the registered receivers (OccupantInserted +0xc / Removed +0x10), so power, water and
 *        traffic follow. Logged occupants are AddRef'd (vt+0x4) so a removed one stays alive for undo.
 *   zone cell set: SIMRCI zone layer primary vtable 0x1004d274 +0x3c = 0x10032a96 (what PlaceZone calls) and its
 *        interface at object+0x10, vtable 0x1004d1e0 +0x3c (thunk 0x10034342, what the network writer calls),
 *        __thiscall(grid, x, z, BYTE *in), ret 0xc; old value from the same object's +0x34 getter.
 * Undo replays the log backwards (Insert -> Remove, Remove -> Insert, cell -> old value) inside the city hold
 * bracket (city vt+0x21c / +0x220) and refunds the funds the action took (budget = city vt+0x15c, vtable SIMMISC
 * 0x1003c550, funds int64 at +0x38, Deposit vt+0x18(uint32) / Withdraw vt+0x14(uint32)). Redo replays forwards and
 * charges again. Nothing is saved or loaded.
 * Tools whose Apply opens the scope (all slot +0x48, __thiscall(tool, arg), ret 4):
 *   SIMRCI zone tool 0x1004c06c (0x1000b7d0, every zone type and DeZone);
 *   SIMNTWRK road 0x1002bef8, highway 0x1002bfa0, rail 0x1002c048, subway 0x1002c0f0, pipe 0x1002c328,
 *   power 0x1002c280, on-ramp 0x1002c1d8.
 *   terrain vertex altitude: SIMDIRT DirtBag vtable 0x1002046c +0x84 SetVertexAltitude(x, z, char h) = 0x10005df0,
 *        ret 0xc, and the rect form +0x80 (x0, z0, x1, z1, h) = 0x10005f20, ret 0x14; old value from +0x4c
 *        GetVertexAltitudeDirt(x, z, BYTE *out) = 0x10005ab0. A road commit levels the corner vertices of its pieces
 *        through SIMNTWRK manager +0x13c -> FUN_10009613 -> FUN_1001a581 -> +0x84 (measured: one vertex 0x52 -> 0x54
 *        on a 6-piece road). The setter marks the tiles dirty and re-shades, so replaying through it redraws.
 *   BUILDINGS (owner order: zoning, networks, buildings). The plop tools are SIMGEOM classes with Apply at +0x48 too
 *        (plain 0x10029504, shoreline 0x10029734, plumbing 0x100295e4, subway 0x1002968c, multi 0x100297a4); the
 *        commit (SIMGEOM 0x10006ba6 / 0x10006df6 / 0x10007760) inserts through the occupant manager (+0x3c, logged),
 *        clears the footprint through Remove (logged) and zone +0x3c (logged), levels through DirtBag +0x84 (logged)
 *        and three writes recorded here:
 *          zone rect +0x38 (x0, z0, x1, z1, BYTE *v) = 0x10032afa (memset, value 22 = building footprint), ret 0x14,
 *            on both zone vtables (interface thunk 0x1003433a); restored per cell through +0x3c;
 *          DirtBag +0x88 SetWaterTable rect (x0, z0, x1, z1, BYTE) = 0x100060d0, ret 0x14; old from +0x50
 *            (x, z, BYTE *) = 0x10005ad0; restored per vertex as a 1-vertex rect;
 *          DirtBag +0x15c BlockCell (x, z, bool) = 0x1000e470, ret 0xc (shoreline buildings); old from +0x160
 *            IsCellBlocked (x, z) = 0x1000e4c0, ret 8.
 *        Rects are read inclusive of both ends and only cells that changed are logged, so the bound convention does not
 *        matter.
 * Left alone: SIMSERV FlammabilityLayer 0x61448030 (a re-inserted occupant stamps its value at once; the sim's scan
 * recomputes every cell anyway) and the crime / pollution module-global lookup caches (verify/undo_spike).
 *   TERRAIN TOOLS (raise, lower, level, water, trees): one entry per mouse press, see "TERRAIN TOOLS" below.
 * Terrain levelled by a network drag whose ends are on an illegal slope (network manager vtable 0x1002c7bc +0x118
 * FUN_100086c8, called from +0xf0 FUN_10014a23 when an end is unattached and FUN_10016d00 fails): FUN_100086c8 writes
 * through DirtBag +0x120 FUN_1000c5d0, whose terrain writes are all DirtBag vtable calls, +0x84 per vertex (two sites)
 * and +0x88 water table [CONFIRMED @ SIMDIRT 0x1000c5d0]; both are logged above, so the entry is kept (until
 * 2026-10-21 the history was cleared). Not seen at runtime: 3 runs of roads over raised hills never reached it.
 * SC3UNDO_TFIX=0 brings the old barrier back. */
enum { OP_INS = 1, OP_REM = 2, OP_CELL = 3, OP_ALT = 4, OP_WATER = 5, OP_BLOCK = 6 };
typedef struct { BYTE op, old, neu; short x, z; void *obj, *occ; } JOp;
/* BULLDOZE EXACTNESS (2026-10-21, verify/undo_leftovers bd*): two kinds of write the occupant log does not cover.
 *   RETILE: the network manager's rectangle retile, SIMNTWRK vtable 0x1002c7bc +0xb0 = FUN_100151f1,
 *        __thiscall(mgr, LONG bbox[6], DWORD netMask), ret 8 (capstone). The demolish path (SIMGEOM 0x1001408d) removes
 *        each piece and collects a dirty bbox + mask; the retile then rewrites the neighbours' piece descriptors (save
 *        section 0x2147c2dd: 8-byte {cell, u32 descriptor} records; after undo the neighbours kept the post-bulldoze
 *        descriptors). Each call made inside an action is recorded and run again after the replay, both ways, so the
 *        tiler recomputes the neighbours against the restored pieces.
 *   TRAFFIC: the TrafficSimulator (city+0xac, primary vtable SimTransit 0x1001a368, QI 0x100051fc answers IID
 *        0x29ca805 with itself) zeroes its per-cell grids under a removed piece and a re-insert does not put them back
 *        (save section 0x029ca804, every differing byte KEPT at the bulldozed value). Its save FUN_10004c8d writes the
 *        byte grids at +0x60 +0x64 +0x68 +0x6c +0x70 +0x74 (object: rows +4, row bytes +8, row pointers +0xc) and the
 *        bit grids at +0x7c +0x80 (rows +4, bits +8, row pointers +0x10, rows of ceil(bits/32) dwords). They are copied
 *        when the scope opens; at close the changed bytes are kept per entry and written back after the replay. */
typedef struct { void *mgr; LONG box[6]; DWORD mask; } JRetile;
typedef struct { BYTE *p; BYTE old, neu; } JByte;
typedef struct { BYTE mod; DWORD key; BYTE val[8]; } JCache;   /* a lookup-cache key the action added (caches below) */
typedef struct { int n, cap; JOp *ops; DWORD money; void *budget; const char *tool;
                 int nrt; JRetile *rt; int ntb; JByte *tb; int ncache; JCache *cache; } JEntry;
static JEntry g_j[MAXSTEPS];
static int g_jn, g_jcur;              /* entries 0..g_jn-1; the first g_jcur are applied */
static BYTE *g_jcity;
static JEntry g_rec;                  /* the action being recorded */
static volatile int g_recording, g_rec_barrier, g_replaying;
static int g_oplog;                  /* SC3UNDO_OPLOG=1: log every op of an entry when it is replayed */
static int g_rec_tfix, g_tfix_ok = 1; /* network terrain fixes inside the scope; SC3UNDO_TFIX=0 restores the old barrier */
static int g_pend = -1;              /* entry whose deferred writes are still being collected (tr_finalize) */

static void j_entry_free(JEntry *e) {
    int i;
    for (i = 0; i < e->n; i++) if (e->ops[i].occ) vc(e->ops[i].occ, 0x08, 0, 0, 0, 0, 0, 0);
    if (e->ops) HeapFree(GetProcessHeap(), 0, e->ops);
    if (e->rt) HeapFree(GetProcessHeap(), 0, e->rt);
    if (e->tb) HeapFree(GetProcessHeap(), 0, e->tb);
    if (e->cache) HeapFree(GetProcessHeap(), 0, e->cache);
    memset(e, 0, sizeof(*e));
}
static void j_clear(const char *why) {
    if (g_jn) logf("JOURNAL> cleared (%d entr%s): %s", g_jn, g_jn == 1 ? "y" : "ies", why);
    while (g_jn) j_entry_free(&g_j[--g_jn]);
    g_jcur = 0; g_jcity = NULL; g_pend = -1;
}
/* the entry being written: the open scope, else the PENDING entry (occupant swaps made by the deferred retile) */
static JEntry *rec_target(void) { return g_recording ? &g_rec : g_pend >= 0 && g_pend < g_jn ? &g_j[g_pend] : NULL; }
static void rec_add(BYTE op, void *obj, void *occ, LONG x, LONG z, BYTE old, BYTE neu) {
    JOp *o;
    JEntry *e = rec_target();
    if (!e) return;
    if (e->n == e->cap) {
        int cap = e->cap ? e->cap * 2 : 256;
        JOp *n = e->ops ? (JOp *)HeapReAlloc(GetProcessHeap(), 0, e->ops, cap * sizeof(JOp))
                        : (JOp *)HeapAlloc(GetProcessHeap(), 0, cap * sizeof(JOp));
        if (!n) { if (e == &g_rec) g_rec_barrier = 1; else j_clear("out of memory for a pending entry"); return; }
        e->ops = n; e->cap = cap;
    }
    o = &e->ops[e->n++];
    o->op = op; o->obj = obj; o->occ = occ; o->x = (short)x; o->z = (short)z; o->old = old; o->neu = neu;
    if (occ) vc(occ, 0x04, 0, 0, 0, 0, 0, 0);
}

/* Both writes also land AFTER Apply returns (measured: 0 retiles and 18 of 74 traffic bytes inside the scope), from the
   game's deferred processing on the next frames. While paused only actions change these grids, so the entry stays
   PENDING after its scope closes: retiles keep being recorded into it, and its traffic diff is taken against the copy from
   scope open when the next action opens a scope or an undo / redo runs (tr_finalize). */
static void *g_retile_orig;
static int g_retile_replay;           /* 0: retiles are logged only; the occupant swaps they cause are journaled instead */
static DWORD __fastcall net_retile(void *mgr, void *edx, LONG *box, DWORD mask) {
    DWORD a[2];
    JEntry *e = g_recording ? &g_rec : g_pend >= 0 && g_pend < g_jn ? &g_j[g_pend] : NULL;
    (void)edx;
    if (e && !g_replaying && box && !IsBadReadPtr(box, 24)) {
        int fail = 0;
        if (e->nrt % 16 == 0) {
            JRetile *n = e->rt ? (JRetile *)HeapReAlloc(GetProcessHeap(), 0, e->rt, (e->nrt + 16) * sizeof(JRetile))
                               : (JRetile *)HeapAlloc(GetProcessHeap(), 0, 16 * sizeof(JRetile));
            if (n) e->rt = n; else fail = 1;
        }
        if (!fail) { JRetile *r = &e->rt[e->nrt++]; r->mgr = mgr; memcpy(r->box, box, 24); r->mask = mask; }
    }
    a[0] = (DWORD)box; a[1] = mask;
    return tc(mgr, g_retile_orig, a, 2);
}

/* --- traffic grids (BULLDOZE EXACTNESS above): rows of the TrafficSimulator's grids, copied at scope open */
#define MAXTROWS 16384
static BYTE *g_tr_rowp[MAXTROWS];
static DWORD g_tr_rowlen[MAXTROWS];
static int g_tr_nrows;
static BYTE *g_tr_copy;
static DWORD g_tr_bytes;
static BYTE *traffic_of(BYTE *city) {
    HMODULE st = GetModuleHandleA("SimTransit.dll");
    BYTE *t;
    if (!city || !st) return NULL;
    __try {
        t = *(BYTE **)(city + 0xac);
        return t && *(DWORD *)t == (DWORD)st + 0x1a368 ? t : NULL;
    } __except (EXCEPTION_EXECUTE_HANDLER) { return NULL; }
}
static void tr_snapshot(BYTE *city) {
    static const int bgrid[] = { 0x60, 0x64, 0x68, 0x6c, 0x70, 0x74 }, bitgrid[] = { 0x7c, 0x80 };
    BYTE *t = traffic_of(city), *dst;
    int g, r;
    g_tr_nrows = 0; g_tr_bytes = 0;
    if (!t) return;
    __try {
        for (g = 0; g < 8; g++) {
            BYTE *o = *(BYTE **)(t + (g < 6 ? bgrid[g] : bitgrid[g - 6]));
            LONG rows, len;
            BYTE **rp;
            if (!o) continue;
            rows = *(LONG *)(o + 4);
            len = g < 6 ? *(LONG *)(o + 8) : ((*(LONG *)(o + 8) + 31) / 32) * 4;
            rp = *(BYTE ***)(o + (g < 6 ? 0xc : 0x10));
            if (rows <= 0 || len <= 0 || !rp || g_tr_nrows + rows > MAXTROWS) continue;
            for (r = 0; r < rows; r++) { g_tr_rowp[g_tr_nrows] = rp[r]; g_tr_rowlen[g_tr_nrows++] = (DWORD)len; g_tr_bytes += (DWORD)len; }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) { g_tr_nrows = 0; g_tr_bytes = 0; return; }
    if (g_tr_copy) HeapFree(GetProcessHeap(), 0, g_tr_copy);
    g_tr_copy = (BYTE *)HeapAlloc(GetProcessHeap(), 0, g_tr_bytes ? g_tr_bytes : 1);
    if (!g_tr_copy) { g_tr_nrows = 0; return; }
    for (dst = g_tr_copy, r = 0; r < g_tr_nrows; dst += g_tr_rowlen[r], r++) memcpy(dst, g_tr_rowp[r], g_tr_rowlen[r]);
}
/* the bytes that changed since tr_snapshot, into e->tb */
static void tr_diff(JEntry *e) {
    BYTE *src = g_tr_copy;
    int r, cap = 0;
    DWORD i;
    if (!g_tr_copy || !g_tr_nrows) return;
    for (r = 0; r < g_tr_nrows; src += g_tr_rowlen[r], r++) {
        if (!memcmp(src, g_tr_rowp[r], g_tr_rowlen[r])) continue;
        for (i = 0; i < g_tr_rowlen[r]; i++) {
            if (src[i] == g_tr_rowp[r][i]) continue;
            if (e->ntb == cap) {
                JByte *n;
                cap = cap ? cap * 2 : 256;
                n = e->tb ? (JByte *)HeapReAlloc(GetProcessHeap(), 0, e->tb, cap * sizeof(JByte))
                          : (JByte *)HeapAlloc(GetProcessHeap(), 0, cap * sizeof(JByte));
                if (!n) { g_rec_barrier = 1; return; }
                e->tb = n;
            }
            e->tb[e->ntb].p = &g_tr_rowp[r][i]; e->tb[e->ntb].old = src[i]; e->tb[e->ntb].neu = g_tr_rowp[r][i]; e->ntb++;
        }
    }
}
/* --- module-global lookup caches (2026-10-21, item 6 of the leftovers; verify/undo_spike runs 8-10).
 * SIMSERV crime modifiers DAT_10024968 and SIMECO pollution DAT_10020818 are std::map trees that no Load clears. On a
 * miss for a building id, SIMSERV 0x10007d35 scans every entry for the smallest vt+0x20 distance and copies that
 * entry's modifier bytes into a new entry for the id [CONFIRMED @ SIMSERV 0x10007d35]. A key added by an undone action
 * can therefore become the nearest match of a later id and hand it its modifier, which the city without the action
 * would not have done. So the keys an action added are erased on undo and put back on redo.
 * Tree layout (both): the map global holds the head node; head+4 root, head+8 leftmost; node +8 left, +0xc right (NULL
 * leaves, FUN_1000881b), +0x10 key, value from +0x14: SIMSERV {char modifier, byte radius} (2 bytes), SIMECO {short,
 * short, byte, byte, short} (8 bytes, saver 0x10006abb). Calls, arity by capstone:
 *   SIMSERV erase-by-key FUN_100087b2 __thiscall(map, uint *key) ret 4; operator[] FUN_10007f7e (map, uint *key) ret 4;
 *   SIMECO erase-range FUN_1000a88a __thiscall(map, node first, node last) ret 8 (-> FUN_1000b422 erases [first, last));
 *          operator[] FUN_1000a80b (map, uint *key) ret 4. */
typedef struct { const char *mod; DWORD map, erase, index, vsize; BYTE pro_erase[8], pro_index[8]; } CacheMod;
static const CacheMod g_cmod[2] = {
    { "SIMSERV.DLL", 0x10024968, 0x100087b2, 0x10007f7e, 2, {0x55,0x8b,0xec,0x83,0xec,0x10,0x56,0x8d}, {0x55,0x8b,0xec,0x83,0xec,0x0c,0x56,0x57} },
    { "SIMECO.DLL",  0x10020818, 0x1000a88a, 0x1000a80b, 8, {0x56,0x8b,0xf1,0x51,0x8b,0x4c,0x24,0x10}, {0x55,0x8b,0xec,0x83,0xec,0x14,0x56,0x57} },
};
#define MAXCKEYS 8192
static DWORD g_ckeys[2][MAXCKEYS];
static int g_nckeys[2];
static BYTE *g_cnodes[2][MAXCKEYS];
/* in-order walk of cache m into keys / nodes (sorted); returns the count, -1 if unusable */
static int cache_walk(int m, DWORD *keys, BYTE **nodes) {
    HMODULE h = GetModuleHandleA(g_cmod[m].mod);
    BYTE *head, *stack[64], *n;
    int sp = 0, cnt = 0, guard = 0;
    if (!h) return -1;
    __try {
        head = *(BYTE **)((BYTE *)h + (g_cmod[m].map - 0x10000000));
        if (!head) return -1;
        n = *(BYTE **)(head + 4);
        while ((n && n != head) || sp) {
            if (++guard > 4 * MAXCKEYS) return -1;
            if (n && n != head) { if (sp == 64) return -1; stack[sp++] = n; n = *(BYTE **)(n + 8); continue; }
            n = stack[--sp];
            if (cnt == MAXCKEYS) return -1;
            keys[cnt] = *(DWORD *)(n + 0x10);
            if (nodes) nodes[cnt] = n;
            cnt++;
            n = *(BYTE **)(n + 0xc);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) { return -1; }
    return cnt;
}
static int cache_fn_ok(int m, DWORD va, const BYTE *pro) {
    HMODULE h = GetModuleHandleA(g_cmod[m].mod);
    return h && !memcmp((BYTE *)h + (va - 0x10000000), pro, 8);
}
static void cache_snapshot(void) {
    int m;
    for (m = 0; m < 2; m++) g_nckeys[m] = cache_walk(m, g_ckeys[m], NULL);
}
static int key_in(const DWORD *keys, int n, DWORD k) {
    int lo = 0, hi = n - 1;
    while (lo <= hi) { int mid = (lo + hi) / 2; if (keys[mid] == k) return 1; if (keys[mid] < k) lo = mid + 1; else hi = mid - 1; }
    return 0;
}
static void cache_diff(JEntry *e) {
    static DWORD now[MAXCKEYS];
    int m, i, n;
    for (m = 0; m < 2; m++) {
        if (g_nckeys[m] < 0) continue;
        n = cache_walk(m, now, g_cnodes[m]);
        for (i = 0; i < n; i++) {
            JCache *c;
            if (key_in(g_ckeys[m], g_nckeys[m], now[i])) continue;
            if (e->ncache % 16 == 0) {
                JCache *p = e->cache ? (JCache *)HeapReAlloc(GetProcessHeap(), 0, e->cache, (e->ncache + 16) * sizeof(JCache))
                                     : (JCache *)HeapAlloc(GetProcessHeap(), 0, 16 * sizeof(JCache));
                if (!p) return;
                e->cache = p;
            }
            c = &e->cache[e->ncache++];
            c->mod = (BYTE)m; c->key = now[i];
            memcpy(c->val, g_cnodes[m][i] + 0x14, g_cmod[m].vsize);
        }
    }
}
/* undo: erase the entry's new keys; redo: put them back with the recorded value */
static int cache_apply(JEntry *e, int forward) {
    static DWORD keys[MAXCKEYS];
    int k, done = 0;
    for (k = 0; k < e->ncache; k++) {
        JCache *c = &e->cache[k];
        const CacheMod *cm = &g_cmod[c->mod];
        HMODULE h = GetModuleHandleA(cm->mod);
        BYTE *map = h ? (BYTE *)h + (cm->map - 0x10000000) : NULL;
        int n, i, at = -1;
        if (!map) continue;
        n = cache_walk(c->mod, keys, g_cnodes[c->mod]);
        for (i = 0; i < n; i++) if (keys[i] == c->key) { at = i; break; }
        __try {
            if (!forward && at >= 0 && cache_fn_ok(c->mod, cm->erase, cm->pro_erase)) {
                DWORD a[2];
                if (c->mod == 0) { a[0] = (DWORD)&c->key; tc(map, (BYTE *)h + (cm->erase - 0x10000000), a, 1); }
                else { a[0] = (DWORD)g_cnodes[1][at]; a[1] = at + 1 < n ? (DWORD)g_cnodes[1][at + 1] : *(DWORD *)map;
                       tc(map, (BYTE *)h + (cm->erase - 0x10000000), a, 2); }
                done++;
            } else if (forward && at < 0 && cache_fn_ok(c->mod, cm->index, cm->pro_index)) {
                DWORD a[1];
                BYTE *v;
                a[0] = (DWORD)&c->key;
                v = (BYTE *)tc(map, (BYTE *)h + (cm->index - 0x10000000), a, 1);
                if (v && !IsBadWritePtr(v, cm->vsize)) { memcpy(v, c->val, cm->vsize); done++; }
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) { logf("CACHE> %s key 0x%08lX threw 0x%08lX", cm->mod, c->key, GetExceptionCode()); }
    }
    return done;
}
static void tr_finalize(void) {
    if (g_pend >= 0 && g_pend < g_jn) {
        tr_diff(&g_j[g_pend]);
        cache_diff(&g_j[g_pend]);
        logf("PENDING> entry %d (%s): %d op(s) in all, %d traffic byte(s), %d retile(s), %d new cache key(s)", g_pend + 1,
             g_j[g_pend].tool, g_j[g_pend].n, g_j[g_pend].ntb, g_j[g_pend].nrt, g_j[g_pend].ncache);
    }
    g_pend = -1;
}

/* --- recorder wrappers (pass-through unless an action is being recorded) */
static void *g_occ_ins_orig, *g_occ_rem_orig, *g_zone_set_orig, *g_zone_iset_orig, *g_terrain_fix_orig;
static void *g_alt_set_orig, *g_alt_rect_orig, *g_zone_rect_orig, *g_zone_irect_orig, *g_water_rect_orig, *g_block_orig;
static int g_in_alt_rect;
static DWORD __fastcall occ_insert(void *mgr, void *edx, void *occ) {
    DWORD a[1], r;
    (void)edx;
    a[0] = (DWORD)occ;
    r = tc(mgr, g_occ_ins_orig, a, 1);
    if (rec_target() && !g_replaying && occ && (r & 0xff)) rec_add(OP_INS, mgr, occ, 0, 0, 0, 0);
    return r;
}
static DWORD __fastcall occ_remove(void *mgr, void *edx, void *occ) {
    DWORD a[1], r;
    int rec = rec_target() && !g_replaying && occ;
    (void)edx;
    if (rec) vc(occ, 0x04, 0, 0, 0, 0, 0, 0);            /* keep it alive across the remove */
    a[0] = (DWORD)occ;
    r = tc(mgr, g_occ_rem_orig, a, 1);
    if (rec) {
        if (r & 0xff) rec_add(OP_REM, mgr, occ, 0, 0, 0, 0);
        vc(occ, 0x08, 0, 0, 0, 0, 0, 0);
    }
    return r;
}
static DWORD cell_set_common(void *orig, void *grid, LONG x, LONG z, BYTE *in) {
    DWORD a[3], r;
    BYTE old = 0;
    int rec = rec_target() && !g_replaying && in;
    if (rec) vc(grid, 0x34, 3, (DWORD)x, (DWORD)z, (DWORD)&old, 0, 0);
    a[0] = (DWORD)x; a[1] = (DWORD)z; a[2] = (DWORD)in;
    r = tc(grid, orig, a, 3);
    if (rec && old != *in) rec_add(OP_CELL, grid, NULL, x, z, old, *in);
    return r;
}
static DWORD __fastcall alt_set(void *d, void *edx, LONG x, LONG z, DWORD h) {
    DWORD a[3], r;
    BYTE old = 0;
    int rec = rec_target() && !g_replaying && !g_in_alt_rect;
    (void)edx;
    if (rec) vc(d, 0x4c, 3, (DWORD)x, (DWORD)z, (DWORD)&old, 0, 0);
    a[0] = (DWORD)x; a[1] = (DWORD)z; a[2] = h;
    r = tc(d, g_alt_set_orig, a, 3);
    if (rec) { BYTE now = 0; vc(d, 0x4c, 3, (DWORD)x, (DWORD)z, (DWORD)&now, 0, 0);
               if (now != old) rec_add(OP_ALT, d, NULL, x, z, old, now); }
    return r;
}
static DWORD __fastcall alt_rect(void *d, void *edx, LONG x0, LONG z0, LONG x1, LONG z1, DWORD h) {
    DWORD a[5], r;
    BYTE *old = NULL;
    LONG lx = min(x0, x1), hx = max(x0, x1), lz = min(z0, z1), hz = max(z0, z1), x, z, w = hx - lx + 1, hh = hz - lz + 1;
    int rec = rec_target() && !g_replaying && w > 0 && hh > 0 && w <= 1025 && hh <= 1025;
    (void)edx;
    if (rec && (old = (BYTE *)HeapAlloc(GetProcessHeap(), 0, w * hh)) != NULL)
        for (x = 0; x < w; x++) for (z = 0; z < hh; z++) vc(d, 0x4c, 3, (DWORD)(lx + x), (DWORD)(lz + z), (DWORD)&old[x * hh + z], 0, 0);
    a[0] = (DWORD)x0; a[1] = (DWORD)z0; a[2] = (DWORD)x1; a[3] = (DWORD)z1; a[4] = h;
    g_in_alt_rect++;
    r = tc(d, g_alt_rect_orig, a, 5);
    g_in_alt_rect--;
    if (old) {
        for (x = 0; x < w; x++) for (z = 0; z < hh; z++) {
            BYTE now = 0;
            vc(d, 0x4c, 3, (DWORD)(lx + x), (DWORD)(lz + z), (DWORD)&now, 0, 0);
            if (now != old[x * hh + z]) rec_add(OP_ALT, d, NULL, lx + x, lz + z, old[x * hh + z], now);
        }
        HeapFree(GetProcessHeap(), 0, old);
    }
    return r;
}
/* a rect write recorded as per-cell ops: read old values (getter slot, 3 args (x, z, BYTE *out)), run, compare */
static DWORD rect_common(BYTE op, void *orig, void *obj, DWORD getter, LONG x0, LONG z0, LONG x1, LONG z1, DWORD v) {
    DWORD a[5], r;
    BYTE *old = NULL;
    LONG lx = min(x0, x1), hx = max(x0, x1), lz = min(z0, z1), hz = max(z0, z1), x, z, w = hx - lx + 1, hh = hz - lz + 1;
    int rec = rec_target() && !g_replaying && w > 0 && hh > 0 && w <= 1025 && hh <= 1025 && lx >= 0 && lz >= 0;
    if (rec && (old = (BYTE *)HeapAlloc(GetProcessHeap(), 0, w * hh)) != NULL)
        for (x = 0; x < w; x++) for (z = 0; z < hh; z++) vc(obj, getter, 3, (DWORD)(lx + x), (DWORD)(lz + z), (DWORD)&old[x * hh + z], 0, 0);
    a[0] = (DWORD)x0; a[1] = (DWORD)z0; a[2] = (DWORD)x1; a[3] = (DWORD)z1; a[4] = v;
    r = tc(obj, orig, a, 5);
    if (old) {
        for (x = 0; x < w; x++) for (z = 0; z < hh; z++) {
            BYTE now = 0;
            vc(obj, getter, 3, (DWORD)(lx + x), (DWORD)(lz + z), (DWORD)&now, 0, 0);
            if (now != old[x * hh + z]) rec_add(op, obj, NULL, lx + x, lz + z, old[x * hh + z], now);
        }
        HeapFree(GetProcessHeap(), 0, old);
    }
    return r;
}
static DWORD __fastcall zone_rect(void *g, void *edx, LONG x0, LONG z0, LONG x1, LONG z1, DWORD v) {
    (void)edx; return rect_common(OP_CELL, g_zone_rect_orig, g, 0x34, x0, z0, x1, z1, v); }
static DWORD __fastcall zone_irect(void *g, void *edx, LONG x0, LONG z0, LONG x1, LONG z1, DWORD v) {
    (void)edx; return rect_common(OP_CELL, g_zone_irect_orig, g, 0x34, x0, z0, x1, z1, v); }
static DWORD __fastcall water_rect(void *d, void *edx, LONG x0, LONG z0, LONG x1, LONG z1, DWORD v) {
    (void)edx; return rect_common(OP_WATER, g_water_rect_orig, d, 0x50, x0, z0, x1, z1, v); }
static DWORD __fastcall block_cell(void *d, void *edx, LONG x, LONG z, DWORD on) {
    DWORD a[3], r, b0 = 0;
    int rec = rec_target() && !g_replaying;
    (void)edx;
    if (rec) b0 = vc(d, 0x160, 2, (DWORD)x, (DWORD)z, 0, 0, 0) & 0xff;
    a[0] = (DWORD)x; a[1] = (DWORD)z; a[2] = on;
    r = tc(d, g_block_orig, a, 3);
    if (rec) { DWORD b1 = vc(d, 0x160, 2, (DWORD)x, (DWORD)z, 0, 0, 0) & 0xff;
               if (b1 != b0) rec_add(OP_BLOCK, d, NULL, x, z, (BYTE)b0, (BYTE)b1); }
    return r;
}
static DWORD __fastcall zone_set(void *g, void *edx, LONG x, LONG z, BYTE *in) { (void)edx; return cell_set_common(g_zone_set_orig, g, x, z, in); }
static DWORD __fastcall zone_iset(void *g, void *edx, LONG x, LONG z, BYTE *in) { (void)edx; return cell_set_common(g_zone_iset_orig, g, x, z, in); }

/* network manager +0x118 = SIMNTWRK FUN_100086c8, __thiscall with 8 dword args (ret 0x20, capstone-checked) */
static DWORD __fastcall terrain_fix(void *mgr, void *edx, DWORD a0, DWORD a1, DWORD a2, DWORD a3, DWORD a4, DWORD a5,
                                    DWORD a6, DWORD a7);

/* --- tools whose Apply opens a recording scope */
typedef struct { const char *mod; DWORD vt; DWORD fn; const char *name; void *orig; } ToolHook;
static ToolHook g_tools[] = {
    { "SIMRCI.DLL",  0x1004c06c, 0x1000b7d0, "zone",    NULL },
    { "SIMNTWRK.DLL", 0x1002bef8, 0x1000e72a, "road",    NULL },
    { "SIMNTWRK.DLL", 0x1002bfa0, 0x1000ebe9, "highway", NULL },
    { "SIMNTWRK.DLL", 0x1002c048, 0x1000f041, "rail",    NULL },
    { "SIMNTWRK.DLL", 0x1002c0f0, 0x1000f4ae, "subway",  NULL },
    { "SIMNTWRK.DLL", 0x1002c328, 0x100102a3, "pipe",    NULL },
    { "SIMNTWRK.DLL", 0x1002c280, 0x1000fe36, "power",   NULL },
    { "SIMNTWRK.DLL", 0x1002c1d8, 0x1000f9b7, "on-ramp", NULL },
    { "SIMGEOM.DLL",  0x10029504, 0x1000970f, "building", NULL },
    { "SIMGEOM.DLL",  0x10029734, 0x10009f7f, "shoreline building", NULL },
    { "SIMGEOM.DLL",  0x100295e4, 0x100099eb, "plumbing building", NULL },
    { "SIMGEOM.DLL",  0x1002968c, 0x10009d3f, "subway building", NULL },
    { "SIMGEOM.DLL",  0x100297a4, 0x1000a62a, "multi-cell building", NULL },
    { "SIMGEOM.DLL",  0x10029458, 0x10008ee8, "demolish", NULL },
};
#define NTOOLS (sizeof(g_tools) / sizeof(g_tools[0]))

static void *budget_of(BYTE *city) {
    HMODULE misc = GetModuleHandleA("SIMMISC.DLL");
    void *bu;
    if (!city || !misc) return NULL;
    bu = (void *)vc(city, 0x15c, 0, 0, 0, 0, 0, 0);
    return bu && *(DWORD *)bu == (DWORD)misc + 0x3c550 ? bu : NULL;
}
static __int64 funds_of(void *budget) { return *(__int64 *)((BYTE *)budget + 0x38); }
static void city_hold(int on) {
    BYTE *city = city_get();
    if (city) vc(city, on ? 0x21c : 0x220, 0, 0, 0, 0, 0, 0);
}

static void j_push(JEntry *e) {
    BYTE *city = city_get();
    if (g_jcity && city != g_jcity) j_clear("city changed");
    while (g_jn > g_jcur) j_entry_free(&g_j[--g_jn]);            /* a new action ends the redo branch */
    if (g_jn >= g_steps) { j_entry_free(&g_j[0]); memmove(&g_j[0], &g_j[1], (g_jn - 1) * sizeof(JEntry)); g_jn--; g_jcur--;
                           memset(&g_j[g_jn], 0, sizeof(JEntry)); }
    g_j[g_jn++] = *e;
    g_jcur = g_jn;
    g_jcity = city;
}

/* the recording scope: opened by a tool's Apply, or for the terrain tools by the button press (they commit on every
   mouse move while held, so one press = one entry) */
static void *g_scope_budget;
static __int64 g_scope_f0;
static int scope_open(const char *name) {
    BYTE *city;
    void *bu;
    if (g_recording) return 0;
    city = city_get();
    if (!city_paused(city) || (bu = budget_of(city)) == NULL) return 0;
    tr_finalize();
    memset(&g_rec, 0, sizeof(g_rec));
    g_rec.tool = name;
    g_rec_barrier = 0;
    g_rec_tfix = 0;
    g_scope_budget = bu;
    g_scope_f0 = funds_of(bu);
    tr_snapshot(city);
    cache_snapshot();
    g_recording = 1;
    return 1;
}
static void scope_close(void) {
    __int64 f1;
    if (!g_recording) return;
    f1 = funds_of(g_scope_budget);
    g_recording = 0;
    g_rec.budget = g_scope_budget;
    g_rec.money = g_scope_f0 > f1 ? (DWORD)(g_scope_f0 - f1) : 0;
    if (g_rec_barrier) {
        logf("APPLY> %s: %d op(s) but the action also changed terrain (not journaled): history cleared", g_rec.tool, g_rec.n);
        j_entry_free(&g_rec);
        j_clear("terrain changed by a network drag");
    } else if (g_rec.n) {
        int ins = 0, rem = 0, cell = 0, alt = 0, k;
        for (k = 0; k < g_rec.n; k++) { BYTE op = g_rec.ops[k].op;
            if (op == OP_INS) ins++; else if (op == OP_REM) rem++; else if (op == OP_ALT || op == OP_WATER || op == OP_BLOCK) alt++; else cell++; }
        j_push(&g_rec);
        logf("APPLY> %s: %d inserted, %d removed, %d zone cell(s), %d terrain op(s), %d retile(s) so far, $%lu -> entry %d of %d",
             g_rec.tool, ins, rem, cell, alt, g_j[g_jn - 1].nrt, g_j[g_jn - 1].money, g_jcur, g_jn);
        g_pend = g_jn - 1;
        if (g_rec_tfix) logf("APPLY> %d network terrain fix(es) inside this action, kept in the entry", g_rec_tfix);
        memset(&g_rec, 0, sizeof(g_rec));
    } else {
        if (g_rec.money) logf("APPLY> %s: $%lu charged but no change recorded", g_rec.tool, g_rec.money);
        j_entry_free(&g_rec);
    }
}

static DWORD __fastcall tool_apply(void *tool, void *edx, DWORD arg) {
    DWORD a[1], r, vt = tool ? *(DWORD *)tool : 0;
    ToolHook *t = NULL;
    unsigned i;
    int scope;
    (void)edx;
    for (i = 0; i < NTOOLS; i++) {
        HMODULE m = GetModuleHandleA(g_tools[i].mod);
        if (m && g_tools[i].orig && vt == (DWORD)m + (g_tools[i].vt - 0x10000000)) { t = &g_tools[i]; break; }
    }
    if (!t) { logf("APPLY> unknown tool vtable 0x%08lX", vt); return 0; }
    scope = scope_open(t->name);
    a[0] = arg;
    __try { r = tc(tool, t->orig, a, 1); }
    __except (EXCEPTION_EXECUTE_HANDLER) { logf("APPLY> %s threw 0x%08lX", t->name, GetExceptionCode()); r = 0; }
    if (scope) scope_close();
    return r;
}

/* TERRAIN TOOLS (SIMDIRT raise 0x100200e4, lower 0x1002018c, level 0x10020234, water 0x100202dc; SIMGEOM trees
   0x100298f4): they commit through +0x48 / +0x4c on every mouse move while the button is held and once on release, so
   the scope spans the press: button down +0x20 opens it, button up +0x28 closes it after the stock handler ran. Both
   __thiscall(tool, x, y, flags), ret 0xc (raise / lower / water share 0x1001c334 / 0x1001c40e; level 0x1001c6bf /
   0x1001c752; trees 0x100215a9 / 0x1002165e). Every write they make goes through slots logged above (DirtBag +0x84 /
   +0x88, zone +0x3c, occupant +0x3c / +0x48 via DemolitionLayer +0x5c / +0x58 and FloraLayer SetDensity). */
typedef struct { const char *mod; DWORD vt; DWORD down, up; const char *name; void *odown, *oup; } PressHook;
static PressHook g_press[] = {
    { "SIMDIRT.DLL", 0x100200e4, 0x1001c334, 0x1001c40e, "raise terrain", NULL, NULL },
    { "SIMDIRT.DLL", 0x1002018c, 0x1001c334, 0x1001c40e, "lower terrain", NULL, NULL },
    { "SIMDIRT.DLL", 0x10020234, 0x1001c6bf, 0x1001c752, "level terrain", NULL, NULL },
    { "SIMDIRT.DLL", 0x100202dc, 0x1001c334, 0x1001c40e, "water",         NULL, NULL },
    { "SIMGEOM.DLL", 0x100298f4, 0x100215a9, 0x1002165e, "trees",         NULL, NULL },
};
#define NPRESS (sizeof(g_press) / sizeof(g_press[0]))
static PressHook *press_of(void *tool) {
    DWORD vt = tool ? *(DWORD *)tool : 0;
    unsigned i;
    for (i = 0; i < NPRESS; i++) {
        HMODULE m = GetModuleHandleA(g_press[i].mod);
        if (m && g_press[i].odown && vt == (DWORD)m + (g_press[i].vt - 0x10000000)) return &g_press[i];
    }
    return NULL;
}
static DWORD __fastcall press_down(void *tool, void *edx, DWORD x, DWORD y, DWORD flags) {
    PressHook *ph = press_of(tool);
    DWORD a[3];
    (void)edx;
    if (!ph) { logf("PRESS> unknown tool vtable 0x%08lX", tool ? *(DWORD *)tool : 0); return 0; }
    if (g_recording) scope_close();               /* a press whose release never reached the tool */
    scope_open(ph->name);
    a[0] = x; a[1] = y; a[2] = flags;
    return tc(tool, ph->odown, a, 3);
}
static DWORD __fastcall press_up(void *tool, void *edx, DWORD x, DWORD y, DWORD flags) {
    PressHook *ph = press_of(tool);
    DWORD a[3], r;
    (void)edx;
    if (!ph) { logf("PRESS> unknown tool vtable 0x%08lX", tool ? *(DWORD *)tool : 0); return 0; }
    a[0] = x; a[1] = y; a[2] = flags;
    __try { r = tc(tool, ph->oup, a, 3); }
    __except (EXCEPTION_EXECUTE_HANDLER) { logf("PRESS> %s up threw 0x%08lX", ph->name, GetExceptionCode()); r = 0; }
    scope_close();
    return r;
}

static DWORD __fastcall terrain_fix(void *mgr, void *edx, DWORD a0, DWORD a1, DWORD a2, DWORD a3, DWORD a4, DWORD a5,
                                    DWORD a6, DWORD a7) {
    DWORD a[8];
    (void)edx;
    if (g_recording) { g_rec_tfix++; if (!g_tfix_ok) g_rec_barrier = 1; }
    a[0] = a0; a[1] = a1; a[2] = a2; a[3] = a3; a[4] = a4; a[5] = a5; a[6] = a6; a[7] = a7;
    return tc(mgr, g_terrain_fix_orig, a, 8);
}

static int patch_vt(HMODULE m, DWORD vt_va, DWORD slot, DWORD expect_va, void *hook, void **orig, const char *what) {
    DWORD *vt = (DWORD *)((BYTE *)m + (vt_va - 0x10000000));
    DWORD want = (DWORD)m + (expect_va - 0x10000000);
    if (vt[slot / 4] == (DWORD)hook) { if (!*orig) *orig = (void *)want; return 1; }
    if (vt[slot / 4] != want) { logf("PATCH> REFUSED %s: slot = 0x%08lX, expected 0x%08lX", what, vt[slot / 4], want); return 0; }
    *orig = (void *)vt[slot / 4];
    if (!patch_slot(&vt[slot / 4], (DWORD)hook)) return 0;
    return 1;
}

/* install everything once SIMRCI, SIMNTWRK and SIMGEOM are loaded (a city is up) */
static int g_journal_ready;
static void journal_install(void) {
    HMODULE rci = GetModuleHandleA("SIMRCI.DLL"), nt = GetModuleHandleA("SIMNTWRK.DLL"), geom = GetModuleHandleA("SIMGEOM.DLL");
    unsigned i;
    int ok = 1;
    if (g_journal_ready || !rci || !nt || !geom || !GetModuleHandleA("SIMMISC.DLL")) return;
    g_journal_ready = 1;
    ok &= patch_vt(geom, 0x10029e24, 0x3c, 0x1000df50, (void *)occ_insert, &g_occ_ins_orig, "occupant Insert");
    ok &= patch_vt(geom, 0x10029e24, 0x48, 0x1000e2c0, (void *)occ_remove, &g_occ_rem_orig, "occupant Remove");
    ok &= patch_vt(rci, 0x1004d274, 0x3c, 0x10032a96, (void *)zone_set, &g_zone_set_orig, "zone cell set");
    ok &= patch_vt(rci, 0x1004d1e0, 0x3c, 0x10034342, (void *)zone_iset, &g_zone_iset_orig, "zone cell set (iface)");
    ok &= patch_vt(rci, 0x1004d274, 0x38, 0x10032afa, (void *)zone_rect, &g_zone_rect_orig, "zone rect set");
    ok &= patch_vt(rci, 0x1004d1e0, 0x38, 0x1003433a, (void *)zone_irect, &g_zone_irect_orig, "zone rect set (iface)");
    ok &= patch_vt(nt, 0x1002c7bc, 0x118, 0x100086c8, (void *)terrain_fix, &g_terrain_fix_orig, "network terrain fix");
    ok &= patch_vt(nt, 0x1002c7bc, 0xb0, 0x100151f1, (void *)net_retile, &g_retile_orig, "network retile");
    {   HMODULE dirt = GetModuleHandleA("SIMDIRT.DLL");
        if (!dirt) { logf("PATCH> SIMDIRT.DLL not loaded"); ok = 0; }
        else {
            ok &= patch_vt(dirt, 0x1002046c, 0x84, 0x10005df0, (void *)alt_set, &g_alt_set_orig, "terrain vertex set");
            ok &= patch_vt(dirt, 0x1002046c, 0x80, 0x10005f20, (void *)alt_rect, &g_alt_rect_orig, "terrain rect set");
            ok &= patch_vt(dirt, 0x1002046c, 0x88, 0x100060d0, (void *)water_rect, &g_water_rect_orig, "water table rect");
            ok &= patch_vt(dirt, 0x1002046c, 0x15c, 0x1000e470, (void *)block_cell, &g_block_orig, "block cell");
        } }
    if (!ok) { logf("JOURNAL> a recorder hook is missing: tool Apply NOT wrapped, no undo"); return; }
    for (i = 0; i < NTOOLS; i++) {
        HMODULE m = GetModuleHandleA(g_tools[i].mod);
        if (m && patch_vt(m, g_tools[i].vt, 0x48, g_tools[i].fn, (void *)tool_apply, &g_tools[i].orig, g_tools[i].name)) continue;
        g_tools[i].orig = NULL;
    }
    {   unsigned np = 0;
        for (i = 0; i < NPRESS; i++) {
            HMODULE m = GetModuleHandleA(g_press[i].mod);
            void *od = NULL, *ou = NULL;
            if (!m) continue;
            if (!patch_vt(m, g_press[i].vt, 0x20, g_press[i].down, (void *)press_down, &od, g_press[i].name)) continue;
            g_press[i].odown = od;
            if (!patch_vt(m, g_press[i].vt, 0x28, g_press[i].up, (void *)press_up, &ou, g_press[i].name)) {
                logf("PATCH> %s: down wrapped but up refused", g_press[i].name); continue; }
            g_press[i].oup = ou;
            np++;
        }
        logf("JOURNAL> recorders on (occupant Insert/Remove, zone cells, terrain vertices, terrain-fix barrier), %u tool Apply "
             "slots and %u terrain-tool presses wrapped", (unsigned)NTOOLS, np);
    }
}

/* replay entry i backwards (undo) or forwards (redo) */
static int j_apply(int i, int forward) {
    JEntry *e = &g_j[i];
    int k, bad = 0;
    DWORD t0 = GetTickCount();
    if (forward && e->money && !(vc(e->budget, 0x14, 1, e->money, 0, 0, 0, 0) & 0xff)) {
        logf("REDO> not enough funds for $%lu", e->money);
        return 0;
    }
    g_replaying = 1;
    city_hold(1);
    if (g_oplog) for (k = 0; k < e->n; k++)
        logf("OPLOG> %d op %d obj 0x%08lX occ 0x%08lX (%d,%d) %02X -> %02X", k, e->ops[k].op, (DWORD)e->ops[k].obj,
             (DWORD)e->ops[k].occ, e->ops[k].x, e->ops[k].z, e->ops[k].old, e->ops[k].neu);
    for (k = 0; k < e->n; k++) {
        JOp *o = &e->ops[forward ? k : e->n - 1 - k];
        __try {
            if (o->op == OP_CELL) {
                BYTE v = forward ? o->neu : o->old;
                vc(o->obj, 0x3c, 3, (DWORD)o->x, (DWORD)o->z, (DWORD)&v, 0, 0);
            } else if (o->op == OP_ALT) {
                vc(o->obj, 0x84, 3, (DWORD)o->x, (DWORD)o->z, (DWORD)(forward ? o->neu : o->old), 0, 0);
            } else if (o->op == OP_WATER) {
                vc(o->obj, 0x88, 5, (DWORD)o->x, (DWORD)o->z, (DWORD)o->x, (DWORD)o->z, (DWORD)(forward ? o->neu : o->old));
            } else if (o->op == OP_BLOCK) {
                vc(o->obj, 0x15c, 3, (DWORD)o->x, (DWORD)o->z, (DWORD)(forward ? o->neu : o->old), 0, 0);
            } else {
                int insert = (o->op == OP_INS) == (forward != 0);
                if (insert) {
                    /* a tool's preview tints the sprite of every occupant under it (SIMSPR highlighter 0x10067a5c ->
                       renderer vt+0x58 -> inst vt+0x28(colour)); the stock clear runs after Apply, when removed
                       occupants are no longer in the manager, so a re-inserted one would stay cyan (measured). Clear the
                       tint first: inst = occ vt+0xa0 (SIMGEOM base 0x1001b405 = [occ+8]), inst vt+0x28(0) = SIMSPR
                       0x1005adf5 (or a derived form that also clears the child sprite). */
                    void *inst = (void *)vc(o->occ, 0xa0, 0, 0, 0, 0, 0, 0);
                    if (inst && !IsBadReadPtr(inst, 8)) vc(inst, 0x28, 1, 0, 0, 0, 0, 0);
                }
                if (!(vc(o->obj, insert ? 0x3c : 0x48, 1, (DWORD)o->occ, 0, 0, 0, 0) & 0xff)) bad++;
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) { bad++; }
    }
    /* after every piece is back (or gone again): retile what the action retiled, then the traffic grid bytes */
    for (k = 0; k < e->nrt && g_retile_replay; k++) {
        __try { vc(e->rt[k].mgr, 0xb0, 2, (DWORD)e->rt[k].box, e->rt[k].mask, 0, 0, 0); }
        __except (EXCEPTION_EXECUTE_HANDLER) { bad++; }
    }
    for (k = 0; k < e->ntb; k++) *e->tb[k].p = forward ? e->tb[k].neu : e->tb[k].old;
    if (e->ncache) logf("CACHE> %d of %d lookup-cache key(s) %s", cache_apply(e, forward), e->ncache, forward ? "put back" : "erased");
    city_hold(0);
    g_replaying = 0;
    if (!forward && e->money) vc(e->budget, 0x18, 1, e->money, 0, 0, 0, 0);
    logf("%s> entry %d (%s): %d op(s), %d failed, $%lu %s, %lu ms", forward ? "REDO" : "UNDO", i + 1, e->tool, e->n, bad,
         e->money, forward ? "charged" : "refunded", GetTickCount() - t0);
    return 1;
}
static void j_undo(void) {
    BYTE *city = city_get();
    if (g_recording) scope_close();
    tr_finalize();
    if (!city_paused(city)) { logf("UNDO> ignored: not paused"); return; }
    if (g_jcity && city != g_jcity) j_clear("city changed");
    if (g_jcur <= 0) { logf("UNDO> nothing to undo"); return; }
    if (j_apply(g_jcur - 1, 0)) g_jcur--;
}
static void j_redo(void) {
    BYTE *city = city_get();
    if (g_recording) scope_close();
    tr_finalize();
    if (!city_paused(city)) { logf("REDO> ignored: not paused"); return; }
    if (city != g_jcity || g_jcur >= g_jn) { logf("REDO> nothing to redo"); return; }
    if (j_apply(g_jcur, 1)) g_jcur++;
}

/* ------------------------------------------------------------------ window hook */
static WNDPROC g_oldproc;

/* TEST ONLY (SC3UNDO_TEST=1, wParam 12): the click path, then a GZ-event drag like sc3probe gz_drag_step.
   Posted Win32 mouse input reaches undo_wndproc but does not make a tool act (measured 2026-10-20: posted clicks
   and drags with Demolish did not change the city), so a scripted test injects the engine's own events. */
typedef struct { DWORD type; LONG d1; LONG d2; DWORD d3; } GZEvent;
typedef int (__fastcall *PFN_WM_Event)(void *, void *, GZEvent *);
static int g_td_step = -1, g_td_x, g_td_y;
static void test_drag_step(HWND h) {
    void *wm = ((PFN_GetWinMgr)(g_exe + 0x703A7))();
    PFN_WM_Event pm = wm ? (PFN_WM_Event)vslot(wm, 0x64) : NULL;
    GZEvent ev;
    int st = g_td_step;
    if (!pm) { g_td_step = -1; KillTimer(h, 0x5d1); return; }
    ev.d3 = 0;
    if (st == 0)      { ev.type = 11; ev.d1 = g_td_x; ev.d2 = g_td_y; }
    else if (st == 1) { ev.type = 7;  ev.d1 = g_td_x; ev.d2 = g_td_y; ev.d3 = 0x10; }
    else if (st <= 7) { ev.type = 11; ev.d1 = g_td_x + 150 * (st - 1) / 6; ev.d2 = g_td_y + 100 * (st - 1) / 6; ev.d3 = 0x10; }
    else              { ev.type = 9;  ev.d1 = g_td_x + 150; ev.d2 = g_td_y + 100; }
    __try { pm(wm, NULL, &ev); } __except (EXCEPTION_EXECUTE_HANDLER) { }
    if (st >= 8) { logf("TEST> gz drag done"); g_td_step = -1; KillTimer(h, 0x5d1); }
    else g_td_step++;
}

static LRESULT CALLBACK undo_wndproc(HWND h, UINT m, WPARAM wp, LPARAM lp) {
    if (!g_oldproc) return DefWindowProcA(h, m, wp, lp);
    if (m == WM_TIMER && wp == 0x5d1) { if (g_td_step >= 0) test_drag_step(h); return 0; }
    if (m == WM_UNDO_CMD) {
        InterlockedExchange(&g_busy, 1);
        if (wp == 5) { journal_install(); InterlockedExchange(&g_busy, 0); return 0; }
        if (wp == 1) j_undo();
        else if (wp == 2) j_redo();
        else if (wp == 3) j_clear("unpaused");
        if (wp <= 4) { BYTE *c = city_get(); int p = city_paused(c) && c == g_jcity;
            buttons_refresh(p && g_jcur > 0, p && g_jcur < g_jn); }
        else if (g_test && wp == 12) {
            long mode = tool_mode(city_view());
            g_td_x = (int)(short)LOWORD(lp); g_td_y = (int)(short)HIWORD(lp);
            logf("TEST> gz drag from (%d,%d) mode=%ld on_map=%d", g_td_x, g_td_y, mode, point_on_map(g_td_x, g_td_y));
            g_td_step = 0;
            SetTimer(h, 0x5d1, 120, NULL);
        }
        else if (g_test && wp == 13) { char tp[MAX_PATH]; BYTE *c = city_get();
            _snprintf(tp, MAX_PATH, "%s\\test_%lu.sc3", g_dir, (DWORD)lp); tp[MAX_PATH - 1] = 0; DeleteFileA(tp);
            if (c) name_save(c);
            logf("TEST> save %s: %d", tp, game_cmd(0, tp));
            if (c) name_restore(c); }
        else if (g_test && wp == 10) logf("TEST> post {0x025F0A91, 0x%08lX}: %d", (DWORD)lp, gz_post(0x025F0A91, (DWORD)lp));
        else if (g_test && wp == 11) { BYTE *c = city_get(); BYTE *v = city_view();
            if (c) name_save(c);
            logf("TEST> city 0x%08lX paused=%d name='%s' tool mode=%ld journal %d of %d", (DWORD)c, city_paused(c),
                 c ? g_name : "", tool_mode(v), g_jcur, g_jn); }
        InterlockedExchange(&g_busy, 0);
        return 0;
    }
    if (g_keys && m == WM_KEYDOWN && !(lp & 0x40000000) && GetKeyState(VK_CONTROL) < 0 && GetKeyState(VK_MENU) >= 0 &&
        (wp == 'Z' || wp == 'Y') && !text_focus() && city_get()) {
        int redo = wp == 'Y' || GetKeyState(VK_SHIFT) < 0;
        PostMessageA(h, WM_UNDO_CMD, redo ? 2 : 1, 0);
        return 0;
    }
    if (m == WM_LBUTTONDOWN && g_test && city_paused(city_get()))
        logf("TEST> LBUTTONDOWN (%d,%d) mode=%ld on_map=%d", (int)(short)LOWORD(lp), (int)(short)HIWORD(lp),
             tool_mode(city_view()), point_on_map((int)(short)LOWORD(lp), (int)(short)HIWORD(lp)));
    return CallWindowProcA(g_oldproc, h, m, wp, lp);
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
    (void)unused;
    /* the bar vtable is patched once the window exists: SIMUI is fully loaded by then (patching it as soon as it
       mapped killed the game during startup), and the bar is only built when a city loads */
    while (!h) { Sleep(20); EnumWindows(find_game_window, (LPARAM)&h); }
    if (g_buttons) {
        HMODULE sui;
        while (!(sui = GetModuleHandleA("SIMUI.DLL"))) Sleep(20);
        if (g_on_bar) patch_bar_vtable(sui); else patch_minimap_vtable(sui);
    }
    Sleep(500);                                       /* let the other mods subclass first; chaining works either way */
    g_hwnd = h;
    /* the old proc must be known BEFORE the swap: the game thread can deliver a message to undo_wndproc between
       SetWindowLongA and the assignment (measured: the first build killed the game during the city load) */
    g_oldproc = (WNDPROC)GetWindowLongA(h, GWL_WNDPROC);
    {   WNDPROC prev = (WNDPROC)SetWindowLongA(h, GWL_WNDPROC, (LONG)undo_wndproc);
        if (prev && prev != g_oldproc) g_oldproc = prev; }
    logf("### window 0x%08lX subclassed (old proc 0x%08lX), steps=%d keys=%d", (DWORD)h, (DWORD)g_oldproc, g_steps, g_keys);
    for (;;) {                                        /* the ring lives only while paused */
        BYTE *city;
        Sleep(300);
        if (g_busy) continue;
        city = city_get();
        if (!g_journal_ready && city) PostMessageA(h, WM_UNDO_CMD, 5, 0);   /* install on the game thread */
        if (g_jn && !city_paused(city)) PostMessageA(h, WM_UNDO_CMD, 3, 0);
        else if (city) PostMessageA(h, WM_UNDO_CMD, 4, 0);   /* keep the buttons' greyed state current */
    }
}

/* delete %TEMP%\sc3undo_<pid> folders whose game is gone (a killed or crashed game never runs DLL detach) */
static void dir_sweep(const char *tmp) {
    char pat[MAX_PATH], d[MAX_PATH], f[MAX_PATH];
    WIN32_FIND_DATAA fd, fd2;
    HANDLE h, h2, ph;
    DWORD pid;
    _snprintf(pat, sizeof(pat), "%ssc3undo_*", tmp); pat[sizeof(pat) - 1] = 0;
    if ((h = FindFirstFileA(pat, &fd)) == INVALID_HANDLE_VALUE) return;
    do {
        if (!(fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)) continue;
        pid = strtoul(fd.cFileName + 8, NULL, 10);
        if (!pid || pid == GetCurrentProcessId()) continue;
        if ((ph = OpenProcess(SYNCHRONIZE, FALSE, pid)) != NULL) {
            DWORD alive = WaitForSingleObject(ph, 0) == WAIT_TIMEOUT;
            CloseHandle(ph);
            if (alive) continue;
        }
        _snprintf(d, sizeof(d), "%s%s", tmp, fd.cFileName); d[sizeof(d) - 1] = 0;
        _snprintf(pat, sizeof(pat), "%s\\*.sc3", d); pat[sizeof(pat) - 1] = 0;
        if ((h2 = FindFirstFileA(pat, &fd2)) != INVALID_HANDLE_VALUE) {
            do { _snprintf(f, sizeof(f), "%s\\%s", d, fd2.cFileName); f[sizeof(f) - 1] = 0; DeleteFileA(f); }
            while (FindNextFileA(h2, &fd2));
            FindClose(h2);
        }
        if (RemoveDirectoryA(d)) logf("### removed stale %s", d);
    } while (FindNextFileA(h, &fd));
    FindClose(h);
}

static void dir_init(void) {
    char tmp[MAX_PATH];
    if (!GetTempPathA(sizeof(tmp), tmp)) lstrcpyA(tmp, ".\\");
    dir_sweep(tmp);
    _snprintf(g_dir, sizeof(g_dir), "%ssc3undo_%lu", tmp, GetCurrentProcessId());
    g_dir[sizeof(g_dir) - 1] = 0;
    CreateDirectoryA(g_dir, NULL);
}

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        char path[MAX_PATH];
        g_self = (HMODULE)inst;
        DisableThreadLibraryCalls(inst);
        InitializeCriticalSection(&g_lock);
        QueryPerformanceFrequency(&g_freq);
        QueryPerformanceCounter(&g_t0);
        g_exe = (BYTE *)GetModuleHandleA(NULL);
        if (!GetEnvironmentVariableA("SC3UNDO_LOG", path, sizeof(path))) self_path(path, sizeof(path), "sc3undo.log");
        g_log = CreateFileA(path, GENERIC_WRITE, FILE_SHARE_READ, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        ini_read();
        if (GetEnvironmentVariableA("SC3UNDO_TEST", path, sizeof(path))) g_test = atoi(path);
        if (GetEnvironmentVariableA("SC3UNDO_TFIX", path, sizeof(path))) g_tfix_ok = atoi(path);
        if (GetEnvironmentVariableA("SC3UNDO_OPLOG", path, sizeof(path))) g_oplog = atoi(path);
        logf("### sc3undo loaded, enabled=%d", g_enabled);
        if (!g_enabled) return TRUE;
        dir_init();
        logf("### snapshots in %s", g_dir);
        CreateThread(NULL, 0, watcher, NULL, 0, NULL);
    } else if (reason == DLL_PROCESS_DETACH && g_dir[0]) {
        RemoveDirectoryA(g_dir);                      /* only if empty; dir_sweep removes the rest at the next start */
    }
    return TRUE;
}
