/* sc3autosave.c - save the city to a separate autosave file every few minutes (owner request 2026-10-27).
 *
 * The save is the game's own Save command, the same one the File menu runs, pointed at an autosave path:
 *   - command CLSID 0x410438DD, one string argument = the path (recipe of SC3U 0x004108f3, first used by sc3undo's
 *     snapshot mode, verify/undo_spike/RESULTS.md).
 *   - The menu save brackets the command with city vt+0x21c / vt+0x220 (SIMCITY 0x100058ac / 0x1000590e: lock
 *     counter city+0x144 up / down, sim sub-object +0x130 vt+0x2c / +0x30) [CONFIRMED @ 0x004108f3]. This mod does
 *     the same, so the sim holds still while it writes.
 *   - The command re-points the city's file name at the path it saved to. The mod reads the name first (city vt+0x254
 *     = SIMCITY 0x10007116 -> string at city+0x15c) and puts it back after (vt+0x258 = 0x1000713b), so the player's
 *     own Save still goes to their own file.
 *   - The menu save then calls thunk_FUN_0045d5ae()->vt+0x40(0) when it succeeds. The autosave does NOT, so the
 *     game still treats the city as unsaved and asks "save changes?" on quit as before. [UNCERTAIN: what vt+0x40(0)
 *     clears is not read; the mod just leaves it alone.]
 *
 * Where: next to the city's own file, "<city>.autosave<N>.sc3", N = 1..keep (oldest overwritten). A city that was
 * never saved goes to <game>\Cities\Untitled.autosaveN.sc3. Each save goes to "<city>.autosave<N>.tmp.sc3" first (the
 * command appends ".sc3" to any path that does not end in it, measured 2026-10-27) and is renamed
 * over the target only when the game says it succeeded, so a failed or interrupted save never destroys the previous
 * autosave. A save byte-identical to the newest autosave (a paused city saves identically) is dropped.
 *
 * When: a watcher thread checks every second and posts WM_AUTOSAVE to the game window, so the save runs on the game
 * thread. The save is put off (retried next second) while a mouse button is held or captured (a drag is in
 * progress), while a text field has focus, while the city object is new (< 20 s since it appeared) or the city's own
 * lock counter is nonzero (the game is already saving), or while another autosave is running. A due save also waits
 * for idle_seconds without mouse or keyboard input ("idle wait" below).
 *
 * Cost: the game freezes for one save. With the game's "Guardando..." box replaced by the corner indicator ("corner
 * indicator" below) that is ~0.3 s on Frankfurt (690 KB), against 1.6 - 2.7 s with the box.
 *
 * autosave.ini beside the DLL:
 *   [autosave] enabled=1 minutes=5 keep=2 dir= idle_seconds=3 indicator=1   (dir empty = next to the city file)
 * Test overrides: SC3AUTOSAVE_SECONDS=<n> (interval in seconds), SC3AUTOSAVE_LOG=<path>, SC3AUTOSAVE_HOLD=<ms> (hold the
 * game thread after the save with the indicator up), SC3AUTOSAVE_INDFORCE=1 (show the indicator even when the game is
 * not in front).
 * Log: sc3autosave.log beside the DLL.
 */
#include <windows.h>
#include "sc3mods_guard.h"
#pragma comment(lib, "gdi32.lib")     /* the corner indicator */
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
#define MAXKEEP 9
static int   g_enabled = 1, g_keep = 2;
static DWORD g_interval_ms = 5 * 60 * 1000;
static char  g_cfg_dir[MAX_PATH];
static DWORD g_idle_ms = 3000;      /* idle wait, see "idle wait" below */
static int   g_indicator = 1;       /* corner indicator instead of the progress box */

static void ini_read(void) {
    char path[MAX_PATH], v[32];
    int minutes;
    self_path(path, sizeof(path), "autosave.ini");
    if (path[0]) {
        g_enabled = GetPrivateProfileIntA("autosave", "enabled", 1, path) ? 1 : 0;
        minutes   = GetPrivateProfileIntA("autosave", "minutes", 5, path);
        g_keep    = GetPrivateProfileIntA("autosave", "keep", 2, path);
        GetPrivateProfileStringA("autosave", "dir", "", g_cfg_dir, sizeof(g_cfg_dir), path);
        g_idle_ms   = (DWORD)GetPrivateProfileIntA("autosave", "idle_seconds", 3, path) * 1000;
        g_indicator = GetPrivateProfileIntA("autosave", "indicator", 1, path) ? 1 : 0;
        if (minutes < 1) minutes = 1;
        if (minutes > 240) minutes = 240;
        g_interval_ms = (DWORD)minutes * 60 * 1000;
    }
    if (GetEnvironmentVariableA("SC3AUTOSAVE_SECONDS", v, sizeof(v)) && atoi(v) > 0) g_interval_ms = (DWORD)atoi(v) * 1000;
    if (g_keep < 1) g_keep = 1;
    if (g_keep > MAXKEEP) g_keep = MAXKEEP;
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
static long city_lock(BYTE *city) {
    __try { return *(long *)(city + 0x144); } __except (EXCEPTION_EXECUTE_HANDLER) { return -1; }
}

/* a text field has keyboard focus (sc3resize KEYFOCUS, same check as sc3undo) */
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
    g_name[0] = 0;
    __try {
        s = ((PFN_GetName)vslot(city, 0x254))(city, NULL);               /* SIMCITY 0x10007116 -> city+0x15c */
        b = *(char **)(s + 4); e = *(char **)(s + 8);
        if (!b && !e) g_name_len = 0;                                   /* empty string: never saved */
        else if (b && e >= b && e - b < MAX_PATH) { memcpy(g_name, b, e - b); g_name_len = (int)(e - b); g_name[g_name_len] = 0; }
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

/* the game's own Save command (CLSID 0x410438DD), game thread only. Returns the command's own success byte. */
typedef void *(__cdecl    *PFN_GNew)(unsigned);
typedef void *(__cdecl    *PFN_GDir)(void);
typedef DWORD (__fastcall *PFN_GCreate)(void *, void *, DWORD, DWORD, void **);
typedef DWORD (__fastcall *PFN_GV0)(void *, void *);
typedef DWORD (__fastcall *PFN_GV1)(void *, void *, void *);
typedef void  (__fastcall *PFN_GVarCtor)(void *);
typedef void  (__fastcall *PFN_GVarS)(void *, void *, const char *, DWORD);
static int game_save(BYTE *city, const char *path) {
    PFN_GNew gnew = (PFN_GNew)(g_exe + 0xB4890);                       /* operator_new, the game heap */
    PFN_GDir gdir = (PFN_GDir)(g_exe + 0x84573);                       /* COM director, SC3U 0x00484573 */
    PFN_GV0 lock_up = (PFN_GV0)vslot(city, 0x21c), lock_dn = (PFN_GV0)vslot(city, 0x220);
    void *dir, *cmd = NULL, *v;
    DWORD ok = 0;
    int locked = 0;
    __try {
        dir = gdir();
        if (!dir) return 0;
        if (!(((PFN_GCreate)vslot(dir, 0x0c))(dir, NULL, 0x410438DD, 0x006856F7, &cmd) & 0xff) || !cmd)
            return 0;
        if (lock_up) { lock_up(city, NULL); locked = 1; }                /* as the menu save: SIMCITY 0x100058ac */
        v = gnew(0x28);
        ((PFN_GVarCtor)(g_exe + 0x6ECC0))(v);
        ((PFN_GVarS)(g_exe + 0x6F896))(v, NULL, path, (DWORD)strlen(path));
        ((PFN_GV0)vslot(v, 0x04))(v, NULL);
        ((PFN_GV1)vslot(cmd, 0x0c))(cmd, NULL, v);
        ((PFN_GV0)vslot(v, 0x08))(v, NULL);
        ok = ((PFN_GV0)vslot(cmd, 0x2c))(cmd, NULL) & 0xff;
        ((PFN_GV0)vslot(cmd, 0x08))(cmd, NULL);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        logf("SAVE threw 0x%08lX", GetExceptionCode());
        ok = 0;
    }
    if (locked) {
        __try { lock_dn(city, NULL); }                                  /* SIMCITY 0x1000590e */
        __except (EXCEPTION_EXECUTE_HANDLER) { logf("unlock threw 0x%08lX", GetExceptionCode()); }
    }
    return (int)ok;
}

/* ------------------------------------------------------------------ files */
static int file_hash(const char *path, unsigned __int64 *h, DWORD *size) {
    HANDLE f = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    static BYTE buf[65536];
    DWORD got, i;
    unsigned __int64 x = 1469598103934665603ULL;
    if (f == INVALID_HANDLE_VALUE) return 0;
    *size = 0;
    while (ReadFile(f, buf, sizeof(buf), &got, NULL) && got) {
        for (i = 0; i < got; i++) { x ^= buf[i]; x *= 1099511628211ULL; }
        *size += got;
    }
    CloseHandle(f);
    *h = x;
    return 1;
}

/* "<dir>\<base>.autosave" from the city file name (or <game>\Cities\Untitled when it has none) */
static void target_stem(char *out, int cap) {
    char dir[MAX_PATH], base[MAX_PATH], *s, *dot;
    if (g_name_len > 0) {
        lstrcpynA(dir, g_name, sizeof(dir));
        s = strrchr(dir, '\\');
        if (!s) s = strrchr(dir, '/');
        if (s) { lstrcpynA(base, s + 1, sizeof(base)); s[0] = 0; }
        else { lstrcpynA(base, dir, sizeof(base)); dir[0] = 0; }
        dot = strrchr(base, '.');
        if (dot) *dot = 0;
        /* an autosave the player loaded saves as itself, not as "x.autosave1.autosave1" */
        if ((dot = strstr(base, ".autosave")) != NULL) *dot = 0;
    } else {
        lstrcpyA(base, "Untitled");
        dir[0] = 0;
    }
    if (g_cfg_dir[0]) lstrcpynA(dir, g_cfg_dir, sizeof(dir));
    if (!dir[0]) {                                                     /* <exe dir>\..\Cities */
        GetModuleFileNameA(NULL, dir, sizeof(dir));
        if ((s = strrchr(dir, '\\')) != NULL) *s = 0;
        if ((s = strrchr(dir, '\\')) != NULL) *s = 0;
        lstrcatA(dir, "\\Cities");
    }
    if (!base[0]) lstrcpyA(base, "Untitled");
    _snprintf(out, cap, "%s\\%s.autosave", dir, base);
    out[cap - 1] = 0;
}

/* slot to write = the first missing one, else the oldest by write time; *newest = the newest existing one (0 = none) */
static int pick_slot(const char *stem, int *newest) {
    char p[MAX_PATH];
    int i, missing = 0, oldest = 0;
    FILETIME t_old, t_new;
    WIN32_FILE_ATTRIBUTE_DATA a;
    *newest = 0;
    for (i = 1; i <= g_keep; i++) {
        _snprintf(p, sizeof(p), "%s%d.sc3", stem, i); p[sizeof(p) - 1] = 0;
        if (!GetFileAttributesExA(p, GetFileExInfoStandard, &a)) { if (!missing) missing = i; continue; }
        if (!*newest || CompareFileTime(&a.ftLastWriteTime, &t_new) > 0) { *newest = i; t_new = a.ftLastWriteTime; }
        if (!oldest || CompareFileTime(&a.ftLastWriteTime, &t_old) < 0) { oldest = i; t_old = a.ftLastWriteTime; }
    }
    if (missing) return missing;                      /* fill empty slots before overwriting any */
    return oldest ? oldest : 1;
}

/* ------------------------------------------------------------------ the autosave */
#define WM_AUTOSAVE (WM_APP + 0x5E0)
static HWND    g_hwnd;
static WNDPROC g_oldproc;
static volatile LONG g_busy;
static BYTE   *g_seen_city;
static DWORD   g_seen_at, g_last_save;
static int     g_saves, g_skips_logged;

/* ------------------------------------------------------------------ idle wait
 * The interval only makes a save DUE. A due save waits until the player has not touched mouse or keyboard over the
 * game window for idle_seconds (default 3), so the freeze does not land in the middle of building something. After
 * one more full interval without such a pause it saves anyway (at the next moment no button is held). */
static DWORD g_last_input;

/* ------------------------------------------------------------------ corner indicator instead of the progress box
 * The city save opens the game's progress box itself: SIMCITY 0x1000429d (city Save, the handler of message
 * 0x111fdae5 that the Save command posts) builds FUN_10002678(steps, string 0x2dd "Guardando...") at city+0x1a4, which
 * calls the progress service FUN_1000edff(): vt+0x88(total, title) open, vt+0x8c(step) advance (redraws the box),
 * vt+0x90() close (FUN_100026a8) [CONFIRMED @ SIMCITY 0x10002678, 0x100026e4, 0x100026a8]. Those three slots are
 * wrapped: during an autosave they feed a small "Autoguardando..." indicator instead of opening the box; at any other
 * time they call the game's own methods, so the player's Save and Load look exactly as before.
 * The indicator is its own small window over the game's top-left corner, run by its own thread: GDI drawn on the game
 * window itself never reached the screen (2026-10-27, desktop grab during a held save showed the frozen frame and no
 * box: the DirectDraw presentation covers it). The window never activates (WS_EX_NOACTIVATE), lets clicks through
 * (WS_EX_TRANSPARENT | WS_EX_LAYERED), shows "Autoguardando..." with a bar while the save runs, then "Autoguardado
 * HH:MM" for 2 s. */
typedef void (__fastcall *PFN_PgOpen)(void *, void *, DWORD, void *);
typedef void (__fastcall *PFN_PgStep)(void *, void *, DWORD);
typedef void (__fastcall *PFN_PgClose)(void *, void *);
static PFN_PgOpen  g_pg_open;
static PFN_PgStep  g_pg_step;
static PFN_PgClose g_pg_close;
static int   g_autosaving, g_pg_hooked;
static DWORD g_pg_total, g_pg_cur;

#define IND_W 176
#define IND_H 36
#define WM_IND_SHOW (WM_APP + 1)
#define WM_IND_DONE (WM_APP + 2)
static HWND  g_ind;                    /* the indicator window (owned by the indicator thread) */
static volatile LONG g_ind_state;      /* 0 hidden, 1 saving, 2 done */
static char  g_ind_done_text[32];

static void ind_paint(HWND w) {
    PAINTSTRUCT ps;
    HDC dc = BeginPaint(w, &ps);
    HFONT f, of;
    HBRUSH bg = CreateSolidBrush(RGB(0x7a, 0x8c, 0xf0)), trough = CreateSolidBrush(RGB(0xe0, 0xe4, 0xf8)),
           bar = CreateSolidBrush(RGB(0xe8, 0x60, 0x48));          /* the game's dialog blue / progress orange */
    RECT rc = { 0, 0, IND_W, IND_H }, r, b;
    DWORD tot = g_pg_total, cur = g_pg_cur;
    int fill;
    FillRect(dc, &rc, bg);
    FrameRect(dc, &rc, trough);
    f = CreateFontA(-13, 0, 0, 0, FW_BOLD, 0, 0, 0, DEFAULT_CHARSET, 0, 0, ANTIALIASED_QUALITY, 0, "Tahoma");
    of = (HFONT)SelectObject(dc, f);
    SetBkMode(dc, TRANSPARENT);
    SetTextColor(dc, RGB(0xff, 0xff, 0xff));
    SetRect(&r, 8, 3, IND_W - 8, 20);
    DrawTextA(dc, g_ind_state == 2 ? g_ind_done_text : "Autoguardando...", -1, &r, DT_LEFT | DT_SINGLELINE | DT_VCENTER);
    SetRect(&b, 8, 23, IND_W - 8, 29);
    FillRect(dc, &b, trough);
    if (g_ind_state == 2) cur = tot = 1;
    fill = tot ? (int)((b.right - b.left) * (cur > tot ? tot : cur) / tot) : 0;
    b.right = b.left + fill;
    if (fill > 0) FillRect(dc, &b, bar);
    SelectObject(dc, of);
    DeleteObject(f); DeleteObject(bg); DeleteObject(bar); DeleteObject(trough);
    EndPaint(w, &ps);
}

static LRESULT CALLBACK ind_proc(HWND w, UINT m, WPARAM wp, LPARAM lp) {
    switch (m) {
    case WM_PAINT: ind_paint(w); return 0;
    case WM_IND_SHOW: {                                  /* place over the game's client top-left, show, no activation */
        POINT pt = { 8, 26 };
        KillTimer(w, 1);
        if (!g_hwnd || IsIconic(g_hwnd)) return 0;
        ClientToScreen(g_hwnd, &pt);
        /* above the game and nothing else: the game window can be WS_EX_TOPMOST (ex-style 0x108 measured
           2026-10-27, a plain HWND_TOP indicator stayed behind it); when it is not, show only while the game is
           the foreground window, so the indicator never floats over another program */
        if (GetWindowLongA(g_hwnd, GWL_EXSTYLE) & WS_EX_TOPMOST)
            SetWindowPos(w, HWND_TOPMOST, pt.x, pt.y, IND_W, IND_H, SWP_NOACTIVATE | SWP_SHOWWINDOW);
        else if (GetForegroundWindow() == g_hwnd || GetEnvironmentVariableA("SC3AUTOSAVE_INDFORCE", NULL, 0)) {
            /* SC3AUTOSAVE_INDFORCE (test only): show even when the game is not in front, for a PrintWindow check */
            SetWindowPos(w, HWND_NOTOPMOST, pt.x, pt.y, IND_W, IND_H, SWP_NOACTIVATE);
            SetWindowPos(w, HWND_TOP, pt.x, pt.y, IND_W, IND_H, SWP_NOACTIVATE | SWP_SHOWWINDOW);
        } else return 0;
        InvalidateRect(w, NULL, FALSE);
        UpdateWindow(w);
        {   RECT wr; GetWindowRect(w, &wr);
            logf("IND> shown at (%ld,%ld)-(%ld,%ld) visible=%d", wr.left, wr.top, wr.right, wr.bottom, IsWindowVisible(w)); }
        return 0;
    }
    case WM_IND_DONE: InvalidateRect(w, NULL, FALSE); SetTimer(w, 1, 2000, NULL); return 0;
    case WM_TIMER: KillTimer(w, 1); g_ind_state = 0; ShowWindow(w, SW_HIDE); return 0;
    case WM_MOUSEACTIVATE: return MA_NOACTIVATE;
    case WM_NCHITTEST: return HTTRANSPARENT;
    }
    return DefWindowProcA(w, m, wp, lp);
}

static DWORD WINAPI ind_thread(LPVOID unused) {
    WNDCLASSA wc;
    MSG msg;
    (void)unused;
    memset(&wc, 0, sizeof(wc));
    wc.lpfnWndProc = ind_proc;
    wc.hInstance = (HINSTANCE)g_self;
    wc.lpszClassName = "sc3autosave_ind";
    wc.hCursor = LoadCursorA(NULL, (LPCSTR)IDC_ARROW);
    RegisterClassA(&wc);
    g_ind = CreateWindowExA(WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_LAYERED | WS_EX_TRANSPARENT, wc.lpszClassName, "",
                            WS_POPUP, 0, 0, IND_W, IND_H, NULL, NULL, wc.hInstance, NULL);
    if (!g_ind) { logf("IND> window not created (%lu)", GetLastError()); return 0; }
    SetLayeredWindowAttributes(g_ind, 0, 235, LWA_ALPHA);
    logf("IND> window 0x%08lX ready", (DWORD)g_ind);
    while (GetMessageA(&msg, NULL, 0, 0) > 0) { TranslateMessage(&msg); DispatchMessageA(&msg); }
    return 0;
}

/* called from the game thread by the progress wrappers and the autosave */
static void ind_show(void)   { if (g_indicator && g_ind) { g_ind_state = 1; PostMessageA(g_ind, WM_IND_SHOW, 0, 0); } }
static void ind_update(void) { if (g_indicator && g_ind && g_ind_state == 1) InvalidateRect(g_ind, NULL, FALSE); }
static void ind_done(int ok) {
    SYSTEMTIME t;
    if (!g_indicator || !g_ind || !g_ind_state) return;
    GetLocalTime(&t);
    if (ok) _snprintf(g_ind_done_text, sizeof(g_ind_done_text), "Autoguardado %02d:%02d", t.wHour, t.wMinute);
    else lstrcpyA(g_ind_done_text, "Autoguardado fallido");
    g_ind_done_text[sizeof(g_ind_done_text) - 1] = 0;
    g_ind_state = 2;
    PostMessageA(g_ind, WM_IND_DONE, 0, 0);
}

static void __fastcall pg_open(void *self, void *edx, DWORD total, void *title) {
    if (g_autosaving) { g_pg_total = total; g_pg_cur = 0; ind_show(); return; }
    g_pg_open(self, edx, total, title);
}
static void __fastcall pg_step(void *self, void *edx, DWORD step) {
    if (g_autosaving) { g_pg_cur = step; ind_update(); return; }
    g_pg_step(self, edx, step);
}
static void __fastcall pg_close(void *self, void *edx) {
    if (g_autosaving) return;
    g_pg_close(self, edx);
}

/* wrap the three slots once, on the game thread (FUN_1000edff builds the service on first use) */
static void pg_hook(void) {
    typedef void *(__cdecl *PFN_Get)(void);
    BYTE *sc = (BYTE *)GetModuleHandleA("SIMCITY.DLL"), *svc;
    DWORD *vt, old;
    if (g_pg_hooked || !sc) return;
    g_pg_hooked = 1;
    __try {
        svc = (BYTE *)((PFN_Get)(sc + 0xedff))();
        if (!svc || IsBadReadPtr(svc, 4)) { logf("PROGRESS> no progress service, box stays"); return; }
        vt = *(DWORD **)svc;
        if (IsBadReadPtr(vt, 0x94) || !VirtualProtect(&vt[0x88 / 4], 12, PAGE_READWRITE, &old)) {
            logf("PROGRESS> vtable 0x%08lX not writable, box stays", (DWORD)vt); return;
        }
        g_pg_open  = (PFN_PgOpen)vt[0x88 / 4];
        g_pg_step  = (PFN_PgStep)vt[0x8c / 4];
        g_pg_close = (PFN_PgClose)vt[0x90 / 4];
        vt[0x88 / 4] = (DWORD)pg_open;
        vt[0x8c / 4] = (DWORD)pg_step;
        vt[0x90 / 4] = (DWORD)pg_close;
        logf("PROGRESS> service 0x%08lX vtable 0x%08lX: open/step/close wrapped (were 0x%08lX 0x%08lX 0x%08lX)",
             (DWORD)svc, (DWORD)vt, (DWORD)g_pg_open, (DWORD)g_pg_step, (DWORD)g_pg_close);
    } __except (EXCEPTION_EXECUTE_HANDLER) { logf("PROGRESS> hook threw 0x%08lX, box stays", GetExceptionCode()); }
}

/* returns NULL if the save can run now, else the reason it is put off */
static const char *why_not(BYTE *city) {
    if (!city) return "no city";
    if (GetTickCount() - g_seen_at < 20000) return "city just loaded";
    if (city_lock(city) != 0) return "city locked (the game is saving)";
    if (GetCapture()) return "mouse captured";
    if (GetAsyncKeyState(VK_LBUTTON) < 0 || GetAsyncKeyState(VK_RBUTTON) < 0 || GetAsyncKeyState(VK_MBUTTON) < 0)
        return "mouse button held";
    if (text_focus()) return "text field has focus";
    return NULL;
}

static void autosave_now(void) {
    BYTE *city = city_get();
    const char *why = why_not(city);
    char stem[MAX_PATH], target[MAX_PATH], tmp[MAX_PATH], prev[MAX_PATH];
    unsigned __int64 h, hp;
    DWORD sz, szp, t0 = GetTickCount();
    int slot, newest, ok;
    if (why) {
        if (!g_skips_logged++) logf("SAVE> put off: %s", why);
        return;
    }
    name_save(city);
    if (g_name_len < 0) { logf("SAVE> city name unreadable, skipped"); g_last_save = GetTickCount(); return; }
    target_stem(stem, sizeof(stem));
    slot = pick_slot(stem, &newest);
    _snprintf(target, sizeof(target), "%s%d.sc3", stem, slot); target[sizeof(target) - 1] = 0;
    /* the Save command appends ".sc3" to a path that does not end in it, so the temp name ends in .sc3 too */
    _snprintf(tmp, sizeof(tmp), "%s%d.tmp.sc3", stem, slot); tmp[sizeof(tmp) - 1] = 0;
    DeleteFileA(tmp);
    pg_hook();
    g_pg_total = g_pg_cur = 0;
    ind_show();
    g_autosaving = 1;
    ok = game_save(city, tmp);
    g_autosaving = 0;
    {   /* test only: SC3AUTOSAVE_HOLD=<ms> holds the game thread with the indicator up, so a screen grab can catch it */
        char v[16];
        if (GetEnvironmentVariableA("SC3AUTOSAVE_HOLD", v, sizeof(v)) && atoi(v) > 0) Sleep((DWORD)atoi(v));
    }
    ind_done(ok);
    name_restore(city);
    {   /* check the restore: the city must still point at the player's own file */
        char want[MAX_PATH];
        int wl = g_name_len;
        lstrcpynA(want, g_name, sizeof(want));
        name_save(city);
        if (g_name_len != wl || strcmp(g_name, want)) logf("SAVE> city name NOT restored: '%s' (wanted '%s')", g_name, want);
        g_name_len = wl;
        lstrcpynA(g_name, want, sizeof(g_name));
    }
    g_last_save = GetTickCount();
    g_skips_logged = 0;
    if (!ok || !file_hash(tmp, &h, &sz) || !sz) {
        logf("SAVE> FAILED (command %d) to %s, %lu ms", ok, tmp, GetTickCount() - t0);
        DeleteFileA(tmp);
        return;
    }
    if (newest) {
        _snprintf(prev, sizeof(prev), "%s%d.sc3", stem, newest); prev[sizeof(prev) - 1] = 0;
        if (file_hash(prev, &hp, &szp) && hp == h && szp == sz) {
            DeleteFileA(tmp);
            logf("SAVE> unchanged since %s, dropped (%lu B, %lu ms)", prev, sz, GetTickCount() - t0);
            return;
        }
    }
    if (!MoveFileExA(tmp, target, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        logf("SAVE> rename %s -> %s failed (%lu)", tmp, target, GetLastError());
        DeleteFileA(tmp);
        return;
    }
    g_saves++;
    logf("SAVE> #%d %s, %lu B, %lu ms (city name kept: '%s')", g_saves, target, sz, GetTickCount() - t0,
         g_name_len > 0 ? g_name : "");
}

static LRESULT CALLBACK as_wndproc(HWND h, UINT m, WPARAM wp, LPARAM lp) {
    if (m == WM_AUTOSAVE) {
        if (InterlockedExchange(&g_busy, 1)) return 0;     /* a nested message loop inside a save: never re-enter */
        autosave_now();
        InterlockedExchange(&g_busy, 0);
        return 0;
    }
    if ((m >= WM_MOUSEFIRST && m <= WM_MOUSELAST) || (m >= WM_KEYFIRST && m <= WM_KEYLAST)) g_last_input = GetTickCount();
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
    while (!h) { Sleep(50); EnumWindows(find_game_window, (LPARAM)&h); }
    Sleep(500);                                       /* let the other mods subclass first; chaining works either way */
    g_hwnd = h;
    /* the old proc must be known BEFORE the swap (sc3undo: a message can arrive between the two calls) */
    g_oldproc = (WNDPROC)GetWindowLongA(h, GWL_WNDPROC);
    {   WNDPROC prev = (WNDPROC)SetWindowLongA(h, GWL_WNDPROC, (LONG)as_wndproc);
        if (prev && prev != g_oldproc) g_oldproc = prev; }
    CloseHandle(CreateThread(NULL, 0, ind_thread, NULL, 0, NULL));   /* always: the indicator can be turned on later */
    logf("### window 0x%08lX subclassed, every %lu s, keep %d%s%s", (DWORD)h, g_interval_ms / 1000, g_keep,
         g_cfg_dir[0] ? ", dir " : "", g_cfg_dir);
    for (;;) {
        BYTE *city;
        Sleep(1000);
        {   /* MODSPAGE (sc3resize Preferencias -> Opciones de mods) writes autosave.ini: re-read it when it changes */
            static FILETIME seen;            /* zero = no file */
            static int first = 1;
            char ip[MAX_PATH];
            WIN32_FILE_ATTRIBUTE_DATA a;
            self_path(ip, sizeof(ip), "autosave.ini");
            if (GetFileAttributesExA(ip, GetFileExInfoStandard, &a) && CompareFileTime(&a.ftLastWriteTime, &seen)) {
                int was_first = first;
                seen = a.ftLastWriteTime;
                first = 0;
                if (!was_first) {   /* the first look only records the time: DllMain already read the file */
                    ini_read();
                    g_skips_logged = 0;
                    logf("INI> autosave.ini changed: enabled=%d every %lu s, keep %d, indicator %d", g_enabled,
                         g_interval_ms / 1000, g_keep, g_indicator);
                }
            }
            first = 0;   /* no file at the first look: one created later is a change */
        }
        if (!IsWindow(h)) return 0;
        city = city_get();
        if (city != g_seen_city) {                    /* new / loaded / closed city: the interval starts again */
            g_seen_city = city;
            g_seen_at = g_last_save = GetTickCount();
            g_skips_logged = 0;
            logf("CITY> %s 0x%08lX", city ? "city" : "no city", (DWORD)city);
            continue;
        }
        if (!city || g_busy || !g_enabled) continue;
        {   DWORD now = GetTickCount(), since = now - g_last_save;
            if (since < g_interval_ms) continue;
            /* due: wait for idle_seconds without input, or save anyway one more interval later */
            if (now - g_last_input < g_idle_ms && since < 2 * g_interval_ms) {
                if (!g_skips_logged++) logf("SAVE> due, waiting for %lu s without input", g_idle_ms / 1000);
                continue;
            }
            PostMessageA(h, WM_AUTOSAVE, 0, 0);
        }
    }
}

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        char path[MAX_PATH];
        if (!sc3mods_guard(inst, "sc3autosave")) return TRUE;   /* not our loader: stay inert (sc3mods_guard.h) */
        g_self = (HMODULE)inst;
        DisableThreadLibraryCalls(inst);
        InitializeCriticalSection(&g_lock);
        QueryPerformanceFrequency(&g_freq);
        QueryPerformanceCounter(&g_t0);
        g_exe = (BYTE *)GetModuleHandleA(NULL);
        if (!GetEnvironmentVariableA("SC3AUTOSAVE_LOG", path, sizeof(path))) self_path(path, sizeof(path), "sc3autosave.log");
        g_log = CreateFileA(path, GENERIC_WRITE, FILE_SHARE_READ, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        ini_read();
        logf("### sc3autosave loaded, enabled=%d", g_enabled);
        /* enabled=0 still starts the watcher: Preferencias can turn autosave on without a restart */
        CreateThread(NULL, 0, watcher, NULL, 0, NULL);
    }
    return TRUE;
}
