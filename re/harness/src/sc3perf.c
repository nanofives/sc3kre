/* sc3perf.c - performance instruments and experiments for SC3U (2026-10-08).
 *
 * 1. FRAME STATS + OVERLAY. Chains the IDirectDrawSurface Blt slot (vt+0x14) AFTER sc3resize has
 *    installed its own hook (sc3resize refuses to hook a slot that no longer points into ddraw.dll, so
 *    we must never go first while it is loaded). A frame = one FINAL present (Blt whose destination
 *    covers the client, the same test sc3resize uses). Also chains BltFast (vt+0x1c) and Lock (vt+0x64)
 *    to count calls and time spent inside DirectDraw. Once a second a CSV row goes to the log; the
 *    overlay (GDI on the window DC after each final present) shows the last second.
 *
 * 2. SAMPLING PROFILER. Suspends the game thread (owner of the "Gonzo" window) about once per ms,
 *    reads Eip and copies the top of its stack, resumes, then buckets the exact Eip (exclusive) and
 *    every validated return address found on the stack copy, once per sample (inclusive). Method is
 *    the I2/I2b profiler of sc3resize (re/analysis/RESIZABLE_WINDOW.md): stack SCAN, not a frame walk,
 *    so inclusive counts are a heuristic (stale return addresses can appear). Raw addresses plus the
 *    module table go to sc3perf_prof_<tag>.txt; re/tools/perf_report.py maps them onto functions.csv.
 *    Control: write "reset" or "dump <tag>" into sc3perf.cmd beside the DLL (polled every 250 ms).
 *
 * 3. SYSMEM EXPERIMENT (off by default). GZGraphicD FUN_10019273 puts a surface in video memory only
 *    while the byte GZGraphicD+0x6cbcd is 0; otherwise it asks for DDSCAPS_SYSTEMMEMORY (0x800). The
 *    byte is written once, at 0x100140fe (`mov [0x1006cbcd], al` after a device query in
 *    FUN_10014078), and read at 0x10015d50, 0x10018f2d and 0x10019370. sysmem=1 presets the byte to 1
 *    and redirects that one store to a dummy, so the game's own system-memory path is taken.
 *
 * 4. SIMCLOCK (2026-10-09). The game clock (SIMCITY vtable 0x10013988, built by FUN_10009b35) is driven
 *    by one periodic timer callback, LAB_1000a854, registered by the clock's Start FUN_10009d5a with a
 *    period of 1000 ms (`push 0x3e8` at 0x10009d98). The callback adds the real time since its last
 *    run to +0x5c and then fires every whole day (+0x60 = ms per game day) that fits, in a loop. At the
 *    fastest speed (SetSpeed 525600, from FUN_10005ada: 0x80520) a day is 164 ms, so the date and every
 *    daily sim pass arrive in bursts of 5-6 days once a second. clock_ms=N registers the timer at N ms
 *    instead. The accumulator logic is untouched, so game time per real second is identical; only the
 *    burst size shrinks. Default 50 = the game's own floor for its hour/minute periods (DAT_10017278).
 *    clock_ms=0 leaves the shipped 1000. Takes effect at the next clock Start (city load / new city).
 *
 * 5. SPRITES (2026-10-09). Buildings draw as light-blue footprint boxes until a background loader thread
 *    (SIMSPR FUN_10008a81, started by FUN_10008156, priority 2) "realizes" their sprite for the current
 *    zoom. Per wake it works until a cost sum reaches the float at iso+0x3d4 (5.0 live; realize costs 1.0,
 *    release 0.3, empty tile 0.03: SIMSPR .rdata 0x100628ec/f4/f0), then SleepEx(20) (`push 0x4e20` at
 *    0x10008cd5, FUN_10054c5e takes microseconds). That is about 5 buildings per 20 ms whatever the CPU,
 *    while the game reads this PC as a 2048 MB machine (app+0xfe) and so queues WHOLE-MAP realize passes
 *    for several zoom levels (SIMSPR FUN_100071a3 tiers 20/29/36/46 MB). On 1024 maps that is 16x the tiles
 *    at the same trickle. spr_budget=N replaces the compare operand (`d8 9e d4 03 00 00` fcomp [esi+0x3d4]
 *    at 0x10008aaf -> `d8 1d <&g_spr_budget>`, same length) and spr_sleep_us=N the sleep immediate.
 *    The loader holds the view lock (iso+0x46c) for one budget, so the budget bounds the game thread's
 *    worst wait on that lock. spr_budget=0 leaves both shipped values.
 *
 * 6. SPR_FOLLOW (2026-10-09). The loader walks each job's region in a spiral from the camera centre AT THE
 *    TIME THE JOB STARTED (FUN_10008835: centre = mid of the camera tile rect iso+0x340..0x34c, then
 *    FUN_10005666(iso+0x3e8, cx, cy)). Scrolling does not restart it - only zoom/rotation re-queue jobs - so on
 *    a 1024 map the spiral can be hundreds of tiles away from where the player is looking (owner: "scrolling,
 *    buildings don't load, but zooming loads them at once"). spr_follow=1 redirects the loader's sleep call
 *    (SIMSPR 0x10008cda, cdecl, esi = iso) through a stub that, under the loader lock (iso+0x46c, vt+4/+8),
 *    re-seeds the spiral at the camera centre when it moved >= 8 tiles, clamped into the spiral's bounds
 *    (+0x10..+0x1c; an out-of-bounds seed would mark the job finished), then sets the current cell with
 *    FUN_1000868b. The job still covers its whole region from the new centre; tiles already realized cost
 *    0.03 each to pass over again.
 *
 * 7. TRANSIT_CLEAR (2026-10-09). SimTransit's trip router (FUN_100070d0) starts EVERY trip by clearing its
 *    whole visited-marker grid (layer+0x78, a byte grid rows x width, class vtable 0x1001a5d8, each row its
 *    own operator new) with FUN_1000a5cb: one memset per row, 1 MB per trip on a 1024 map (64 KB on 256).
 *    On the Europolis 1024 city that memset was the largest single cost on the sim thread. A trip only marks
 *    cells near its path, so transit_clear=1 moves the grid's rows into ONE MEM_WRITE_WATCH buffer the first
 *    time a trip clears it, then each clear asks GetWriteWatch which 4 KB pages were written since the last
 *    one and clears only those, whoever wrote them. Call site SIMTRANSIT 0x10007158 (call FUN_1000a5cb,
 *    thiscall grid, byte* value). The grid's destructor FUN_1000ab16 is replaced by a C copy that puts the
 *    original row pointers back before freeing them. Any mismatch falls back to the full clear.
 *
 * 8. FAST_FTOL (2026-10-09). The game's VC6 code converts float to int through msvcrt!_ftol, imported by
 *    SC3U.exe and every sim/graphics DLL. The Windows 10/11 msvcrt _ftol saves the x87 control word, sets
 *    round-toward-zero with fldcw, stores, and restores it with another fldcw (via an internal _controlfp-
 *    like helper); fldcw serialises the FPU. On the 1024 sim thread that helper alone was ~17% of samples
 *    (msvcrt+0xa9024/+0xa9028, inside SimTransit route search). fast_ftol=1 puts a JMP at msvcrt!_ftol's
 *    entry to a three-instruction version using SSE3 FISTTP, which truncates without touching the control
 *    word: same contract (pops ST0, int64 in edx:eax, NaN/overflow -> 0x8000000000000000). Requires SSE3.
 *
 * 9. SIM BUSY INDICATOR (2026-10-09, owner: "a visual cue when a day is not moving"). The day fire SIMCITY
 *    FUN_1000aa4d (fastcall, ecx = clock; bumps the day count +0x4c and runs the day listeners) gets a 10-byte
 *    entry hook that records the clock and counts days. Clock fields [CONFIRMED @ 0x1000a066, 0x1000a0ec]:
 *    +0x50 game minutes per real day (speed; 120 = the paused speed), +0x54 clock pause count, +0x60 ms per
 *    day. A watcher thread compares the time since the last day with +0x60. When the date is more than 1 s
 *    late, the speed is not the paused one, and the city is neither user-paused (city+0x140) nor camera-held
 *    (city+0x144), the overlay shows a red line: how late the day is, the CPU use of the SIMCITY-class sim
 *    threads, and which sim modules their samples fall in (EIP, or the first return address outside the
 *    system DLLs). Sim threads idle while the date is late mean the clock is held by something else (a
 *    dialog), and the line says so. Drawn even with overlay=0. busy=0 turns it off. busy_show=0 (PERFPREFS,
 *    "Ver perfilador" in Preferencias) keeps the detector and its log and only stops the drawing.
 *    Below it, the two most frequent CALL CHAINS of the stall so far: the function the sim thread is in and the
 *    next two game functions under it on the stack (stack scan, so a stale return address can appear), named
 *    from sc3perf_names.txt beside the DLL (re/tools/perf_names.py, from functions.csv). When the date moves
 *    again, the stall's top 8 chains go to the log.
 *
 * 10. LIST_COUNT (2026-10-09). SIMCITY keeps per-category registries of sim objects (std::list heads at
 *    this+0x44+4*i, i < 6). Add FUN_10001bec pushes, then calls FUN_10001db0 - which COUNTS the list by walking
 *    every node - only to test `== 1` (list became non-empty); remove FUN_10001c63 finds the node, erases it, and
 *    counts again only to test `== 0`. FUN_10001db0 has no other caller. On the Europolis 1024 city (~369k
 *    buildings) the count was 72% of the sim thread's busy samples and the date stood still for minutes.
 *    list_count=1 jumps FUN_10001db0 to a constant-time version returning min(count, 2), exact for both tests.
 *    list_find=1: the remove's own search (0x10001c80..0x10001c96, walks from the front comparing node+8) is
 *    replaced by a hash index (list head, object) -> node (VC6 std::list node: +0 next, +4 prev, +8 value).
 *    Measured on that city: category 3 holds every building (~348k nodes), 2,450 removes a minute, the removed
 *    node on average 303k from the front (a both-ends walk only gained 8%). The lists change in three places,
 *    all hooked: add FUN_10001bec -> push_back FUN_10001dc0 (call at 0x10001c15: the new node is head->prev),
 *    remove FUN_10001c63 (the search), and range erase FUN_10002120 (teardown; wipes the whole index). A list
 *    is indexed on its first search by one walk; a duplicate object or any hit whose links do not check out
 *    (node+8 == object, next->prev == node, prev->next == node) drops the index and falls back to the walk.
 *
 * Config: perf.ini beside the DLL, [perf] overlay=1 profile=0 sysmem=0 clock_ms=50 spr_budget=40
 * spr_sleep_us=1000 spr_follow=1 transit_clear=1 fast_ftol=1 busy=1 busy_show=1; overlay and busy_show are also
 * written by the Preferences checkboxes (PERFPREFS, sc3perf_show_set). Env SC3PERF_<KEY> overrides any key at
 * startup (SC3PERF_OVERLAY, SC3PERF_BUSY_SHOW, SC3PERF_PROFILE, ...); SC3PERF_LOG=<path> (default sc3perf.log beside the DLL).
 */
#include <windows.h>
#include "sc3mods_guard.h"
#include <tlhelp32.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <intrin.h>
#pragma intrinsic(_ReturnAddress)

static HMODULE g_self;
static char    g_dir[MAX_PATH];
static HANDLE  g_log = INVALID_HANDLE_VALUE;
static CRITICAL_SECTION g_logcs;
static int     g_overlay = 1, g_profile = 0, g_sysmem = 0, g_clock_ms = 50, g_spr_sleep_us = 1000;
static float   g_spr_budget = 40.0f;
static int     g_spr_follow = 1;
static DWORD   g_spr_base, g_sleep_orig;
static LONG    g_seed_x = -100000, g_seed_y = -100000;
static volatile LONG g_reseeds;
static int     g_fastceil = 1, g_sprref = 1, g_layerref = 1, g_strtref = 1, g_reloadshadow = 1;
static int     g_trclear = 1, g_fastftol = 1, g_busy = 1, g_listcount = 1, g_listfind = 1;
static volatile int g_busy_show = 1;   /* PERFPREFS: draw the busy lines (busy= keeps the detector itself) */
static LARGE_INTEGER g_qf, g_t0;

static double now_ms(void) {
    LARGE_INTEGER t;
    QueryPerformanceCounter(&t);
    return (double)(t.QuadPart - g_t0.QuadPart) * 1000.0 / (double)g_qf.QuadPart;
}

static void logf(const char *fmt, ...) {
    char buf[1024];
    DWORD wrote;
    int n, h;
    va_list ap;
    if (g_log == INVALID_HANDLE_VALUE) return;
    h = _snprintf(buf, 40, "[%10.3f ms] ", now_ms());
    if (h < 0) h = 0;
    va_start(ap, fmt);
    n = _vsnprintf(buf + h, sizeof(buf) - h - 3, fmt, ap);
    va_end(ap);
    if (n < 0) n = (int)strlen(buf + h);
    n += h;
    buf[n++] = '\r'; buf[n++] = '\n';
    EnterCriticalSection(&g_logcs);
    WriteFile(g_log, buf, n, &wrote, NULL);
    LeaveCriticalSection(&g_logcs);
}

/* Bytes readable from p, up to want, by VirtualQuery: unlike IsBadReadPtr it never faults (each fault there
   was a first-chance AV that sc3resize's crash logger dumped with a stack walk - 88k lines in 3 minutes of
   sim-thread sampling, 2026-10-09). Committed, readable, not a guard page. */
static DWORD readable(const void *p, DWORD want) {
    MEMORY_BASIC_INFORMATION mbi;
    const BYTE *a = (const BYTE *)p, *end = a + want;
    while (a < end) {
        if (!VirtualQuery(a, &mbi, sizeof(mbi)) || mbi.State != MEM_COMMIT ||
            (mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD)) || !(mbi.Protect & 0xEE)) break;
        a = (const BYTE *)mbi.BaseAddress + mbi.RegionSize;
    }
    if (a > end) a = end;
    return (DWORD)(a - (const BYTE *)p);
}

/* ---------------------------------------------------------------- module ranges */
static DWORD mod_size(DWORD h) {
    DWORD e;
    if (!h || IsBadReadPtr((void *)h, 0x40)) return 0;
    e = *(DWORD *)(h + 0x3c);
    if (IsBadReadPtr((void *)(h + e + 0x50), 4)) return 0;
    return *(DWORD *)(h + e + 0x50);
}
static int in_mod(DWORD a, const char *name) {
    DWORD h = (DWORD)GetModuleHandleA(name);
    return h && a >= h && a < h + mod_size(h);
}

/* ---------------------------------------------------------------- game window */
static HWND g_hwnd;
static DWORD g_game_tid;
static LONG g_cw, g_ch;   /* client size, refreshed by the stats thread */

static BOOL CALLBACK find_wnd(HWND h, LPARAM lp) {
    DWORD pid = 0;
    char cls[32];
    (void)lp;
    GetWindowThreadProcessId(h, &pid);
    if (pid != GetCurrentProcessId()) return TRUE;
    if (!GetClassNameA(h, cls, sizeof(cls)) || strcmp(cls, "Gonzo")) return TRUE;
    g_hwnd = h;
    return FALSE;
}

/* ---------------------------------------------------------------- DirectDraw hooks */
typedef HRESULT (WINAPI *BLT_FN)(void *, RECT *, void *, RECT *, DWORD, void *);
typedef HRESULT (WINAPI *BLTFAST_FN)(void *, DWORD, DWORD, void *, RECT *, DWORD);
typedef HRESULT (WINAPI *LOCK_FN)(void *, RECT *, void *, DWORD, HANDLE);
static BLT_FN     g_next_blt;
static BLTFAST_FN g_next_bltfast;
static LOCK_FN    g_next_lock;
static DWORD     *g_vt;

/* per-second accumulators (written on the game thread, read/reset by the stats thread) */
static volatile LONG g_frames, g_blt_n, g_bltfast_n, g_lock_n;
static volatile double g_blt_ms, g_bltfast_ms, g_lock_ms, g_present_ms, g_frame_max;
static volatile double g_wait_ms;
static double g_last_present;
static char g_text[160] = "sc3perf";
static LONG g_va_used, g_va_priv, g_va_free;
static volatile LONG g_days;          /* days fired since load (SIM BUSY day hook) */   /* MB, refreshed once a second by the stats thread */
static volatile LONG g_in_present;

/* Draw the counter INTO the frame (the present's source surface) right before it goes out, so the next
   present cannot cover it. IDirectDrawSurface GetDC vt+0x44, ReleaseDC vt+0x68. */
/* OVERLAY SAVE/RESTORE (owner hand test 2026-10-08: the counter left a trail down the screen while
   scrolling, and tore the city under it). The game scrolls by shifting the pixels already in its back
   buffer and redrawing only the strip that came into view, so anything drawn into that buffer is carried
   along. So: copy the pixels under the counter out of the source surface, draw, present, copy them back.
   The game never sees a changed back buffer. DDSURFACEDESC v1: height +0x08, width +0x0c, pitch +0x10,
   bits +0x24, pixel format +0x48 (RGB bit count at +0x54). Lock = the real (next) Lock, Unlock vt+0x80. */
#define OV_W 800
#define OV_H 92
/* UISCALE (owner hand test 2026-10-20: "the profiling indicator/FPS should scale with interface too"): with sc3resize's
   HUD scale on, the text is drawn with the stock font's face at the HUD factor (sc3resize_ui_scale, percent) and the
   saved area grows with it. At 100 the stock font and the 800x92 area are used, as before. */
static BYTE *g_ov_save;
static LONG  g_ov_cap;
static int   g_ov_saved;
static LONG  g_ov_x, g_ov_y, g_ov_w, g_ov_h, g_ov_bpp, g_ov_aw = OV_W, g_ov_ah = OV_H;
static int ov_scale(void) {   /* percent, 100 = native */
    static int (*f)(void);
    static int tried;
    int s;
    if (!tried) {
        HMODULE rz = GetModuleHandleA("sc3resize.dll");
        if (rz) { f = (int (*)(void))GetProcAddress(rz, "sc3resize_ui_scale"); tried = 1; }
    }
    s = f ? f() : 100;
    return s < 100 ? 100 : s > 800 ? 800 : s;
}

static int ov_copy(void *src, int restore) {
    DWORD d[0x6c / 4], *vt = *(DWORD **)src;
    BYTE *bits;
    LONG pitch, y, rowbytes;
    memset(d, 0, sizeof(d));
    d[0] = 0x6c;
    if (g_next_lock(src, NULL, d, 1 /* DDLOCK_WAIT */, NULL) != 0) return 0;
    bits = (BYTE *)d[0x24 / 4];
    pitch = (LONG)d[0x10 / 4];
    if (!restore) {
        LONG sw = (LONG)d[0x0c / 4], sh = (LONG)d[0x08 / 4];
        g_ov_bpp = (LONG)d[0x54 / 4] / 8;
        if (g_ov_bpp < 1 || g_ov_bpp > 4) g_ov_bpp = 0;
        g_ov_w = g_ov_x + g_ov_aw <= sw ? g_ov_aw : sw - g_ov_x;
        g_ov_h = g_ov_y + g_ov_ah <= sh ? g_ov_ah : sh - g_ov_y;
    }
    rowbytes = g_ov_w * g_ov_bpp;
    if (bits && g_ov_bpp && g_ov_w > 0 && g_ov_h > 0)
        for (y = 0; y < g_ov_h; y++) {
            BYTE *row = bits + (g_ov_y + y) * pitch + g_ov_x * g_ov_bpp, *buf = g_ov_save + y * g_ov_aw * 4;
            if (restore) memcpy(row, buf, rowbytes); else memcpy(buf, row, rowbytes);
        }
    ((HRESULT (WINAPI *)(void *, void *))vt[0x80 / 4])(src, NULL);
    return bits && g_ov_bpp && g_ov_w > 0 && g_ov_h > 0;
}

static char g_busy_text[512];
static CRITICAL_SECTION g_busycs;

/* UISCALE: the overlay font at s percent (NULL = the stock font, at 100). The stock font is a raster font that Windows
   can only widen, which looked stretched (owner hand test 2026-10-20), so a TrueType monospace at the scaled cell
   height keeps the proportions. Cached for the last s. */
static HFONT ov_font(int s) {
    static HFONT big;
    static int big_s;
    if (s == big_s) return big;
    if (big) DeleteObject(big);
    big = NULL; big_s = s;
    if (s > 100) {
        LOGFONTA lf;
        TEXTMETRICA tm;
        HDC sdc = GetDC(NULL);
        HGDIOBJ o = SelectObject(sdc, GetStockObject(ANSI_FIXED_FONT));
        LONG ch = GetTextMetricsA(sdc, &tm) ? tm.tmHeight : 13;
        SelectObject(sdc, o); ReleaseDC(NULL, sdc);
        memset(&lf, 0, sizeof(lf));
        lf.lfHeight = -(ch * s / 100);   /* character height, natural width */
        lf.lfWeight = FW_BOLD;
        lf.lfCharSet = ANSI_CHARSET;
        lf.lfQuality = ANTIALIASED_QUALITY;
        lf.lfPitchAndFamily = FIXED_PITCH | FF_MODERN;
        lstrcpyA(lf.lfFaceName, "Consolas");
        big = CreateFontIndirectA(&lf);
        logf("UISCALE> overlay text at %d%% (%s)", s, big ? "scaled font" : "font FAILED, stock size");
    }
    return big;
}

/* the FPS line and the busy lines at (x0, y0), s percent */
static void ov_paint(HDC dc, int x0, int y0, int s, const char *busy) {
    HFONT f = ov_font(s);
    int step = f ? 16 * s / 100 : 16;
    HGDIOBJ of = SelectObject(dc, f ? (HGDIOBJ)f : GetStockObject(ANSI_FIXED_FONT));
    SetBkMode(dc, OPAQUE);
    if (g_overlay) {
        SetBkColor(dc, RGB(0, 0, 0));
        SetTextColor(dc, RGB(255, 255, 0));
        TextOutA(dc, x0, y0, g_text, (int)strlen(g_text));
        y0 += step;
    }
    if (busy[0]) {
        const char *ln = busy, *nl;
        int first = 1;
        SetTextColor(dc, RGB(255, 255, 255));
        while (ln && *ln) {
            nl = strchr(ln, '\n');
            SetBkColor(dc, first ? RGB(160, 0, 0) : RGB(90, 0, 0));
            TextOutA(dc, x0, y0, ln, nl ? (int)(nl - ln) : (int)strlen(ln));
            y0 += step;
            first = 0;
            ln = nl ? nl + 1 : NULL;
        }
    }
    SelectObject(dc, of);
}

static int ov_text(char *busy) {   /* 1 = something to draw */
    EnterCriticalSection(&g_busycs);
    memcpy(busy, g_busy_text, 512);
    LeaveCriticalSection(&g_busycs);
    busy[511] = 0;
    if (!g_busy_show) busy[0] = 0;
    return g_overlay || busy[0];
}

/* UISCALE: the main menu's scaled 4:3 rect from sc3resize, or 0 (not the menu, or no sc3resize) */
static int ov_menu_rect(LONG *r) {
    static int (*f)(LONG *);
    static int tried;
    if (!tried) {
        HMODULE rz = GetModuleHandleA("sc3resize.dll");
        if (rz) { f = (int (*)(LONG *))GetProcAddress(rz, "sc3resize_menu_rect"); tried = 1; }
    }
    return f ? f(r) : 0;
}
static int g_ov_menu;   /* this present is the scaled main menu: draw on the window after it, not into the frame */

static void draw_overlay(void *src, RECT *sr) {
    HDC dc = NULL;
    DWORD *vt;
    char busy[512];
    int s, x0, y0;
    LONG mr[4];
    g_ov_menu = 0;
    if (!ov_text(busy)) return;
    if (!src || IsBadReadPtr(src, 4)) return;
    if (ov_menu_rect(mr)) { g_ov_menu = 1; return; }
    vt = *(DWORD **)src;
    s = ov_scale();
    {   /* UISCALE: the area the scaled text can cover */
        LONG aw = OV_W * s / 100, ah = OV_H * s / 100;
        if (g_ov_cap < aw * ah * 4) {
            BYTE *nb = (BYTE *)malloc((size_t)aw * ah * 4);
            if (!nb) return;
            free(g_ov_save); g_ov_save = nb; g_ov_cap = aw * ah * 4;
        }
        g_ov_aw = aw; g_ov_ah = ah;
    }
    x0 = (sr ? sr->left : 0) + 4 * s / 100; y0 = (sr ? sr->top : 0) + 4 * s / 100;
    g_ov_x = sr ? sr->left : 0; g_ov_y = sr ? sr->top : 0;
    g_ov_saved = ov_copy(src, 0);
    if (!g_ov_saved) return;   /* never draw what we cannot take back */
    if (((HRESULT (WINAPI *)(void *, HDC *))vt[0x44 / 4])(src, &dc) != 0 || !dc) { g_ov_saved = 0; return; }
    ov_paint(dc, x0, y0, s, busy);
    ((HRESULT (WINAPI *)(void *, HDC))vt[0x68 / 4])(src, dc);
}

/* UISCALE, main menu: after the present, on the window itself, at its top-left, at the menu's scale (rect width / 800).
   MENUSCALE only sends changed parts of the frame, so the text stays until the next present draws it again. */
static void draw_overlay_menu(void) {
    char busy[512];
    LONG mr[4];
    HDC dc;
    int s;
    if (!g_hwnd || !ov_text(busy) || !ov_menu_rect(mr)) return;
    s = (int)((mr[2] - mr[0]) * 100 / 800);
    if (s < 100) s = 100;
    if (!(dc = GetDC(g_hwnd))) return;
    ov_paint(dc, 4 * s / 100, 4 * s / 100, s, busy);
    ReleaseDC(g_hwnd, dc);
}

/* FRAME CAP: hold each final present until 1000/cap ms after the previous one. Sleep for all but the
   last ~1.5 ms (1 ms timer resolution is set by the profiler thread), then spin. g_wait_ms keeps the
   time spent waiting so the CSV can show the frame's real work time. */
static int g_cap;                    /* setting: 0 off, -1 = the window's monitor refresh rate, N = N fps */
static volatile LONG g_cap_eff;
static volatile LONG g_iconic;       /* window minimized: no final present exists to pace on */
static double g_iconic_t;      /* the cap in force, refreshed once a second by the stats thread */
static double g_next_due;
static void cap_wait(void) {
    double t = now_ms(), period, w0 = t;
    if (g_cap_eff <= 0) return;
    period = 1000.0 / g_cap_eff;
    if (g_next_due <= 0 || t - g_next_due > period) g_next_due = t;   /* first frame, or fell behind */
    {   /* a high-resolution waitable timer (Win10 1803+) wakes within ~0.5 ms, so almost no spinning is
           left; without it, Sleep to ~1 ms short and spin (that spin measured ~16% of a core at 165 fps) */
        static HANDLE hrt;
        static int tried;
        if (!tried) {
            typedef HANDLE (WINAPI *CWTEX)(void *, LPCWSTR, DWORD, DWORD);
            CWTEX f = (CWTEX)GetProcAddress(GetModuleHandleA("kernel32.dll"), "CreateWaitableTimerExW");
            tried = 1;
            if (f) hrt = f(NULL, NULL, 0x2 /* CREATE_WAITABLE_TIMER_HIGH_RESOLUTION */, 0x1F0003 /* TIMER_ALL_ACCESS */);
            logf("CAP> high-resolution timer %s", hrt ? "available" : "NOT available - sleep and spin");
        }
        while ((t = now_ms()) < g_next_due) {
            double left = g_next_due - t;
            if (hrt && left > 0.6) {
                LARGE_INTEGER due;
                due.QuadPart = -(LONGLONG)((left - 0.5) * 10000.0);   /* relative, 100 ns units */
                if (SetWaitableTimer(hrt, &due, 0, NULL, NULL, FALSE)) { WaitForSingleObject(hrt, 100); continue; }
            }
            if (!hrt && left > 1.5) Sleep((DWORD)(left - 1.0)); else YieldProcessor();
        }
    }
    g_next_due += period;
    g_wait_ms += now_ms() - w0;
}

static HRESULT WINAPI perf_blt(void *self, RECT *dr, void *src, RECT *sr, DWORD fl, void *fx) {
    double a, b;
    HRESULT hr;
    int final = dr && g_cw > 0 && !IsBadReadPtr(dr, sizeof(RECT)) &&
                dr->right - dr->left >= g_cw && dr->bottom - dr->top >= g_ch;
    if (!final && g_iconic && g_cap) {
        /* MINIMIZED: the game keeps rendering (measured: ~12,000 blits/s, 96% of a core, 0 final presents
           because the client is 0x0). Sleep 90 ms out of every ~100 so it idles instead (40 of 50 still left 50% of a core, measured). */
        double t = now_ms();
        if (t - g_iconic_t > 10) { Sleep(90); g_iconic_t = now_ms(); }
    }
    if (final) {
        cap_wait();
        draw_overlay(src, sr && !IsBadReadPtr(sr, sizeof(RECT)) ? sr : NULL);
    }
    a = now_ms();
    hr = g_next_blt(self, dr, src, sr, fl, fx);
    if (final && g_ov_saved) { ov_copy(src, 1); g_ov_saved = 0; }   /* give the game its pixels back */
    if (final && g_ov_menu) { draw_overlay_menu(); g_ov_menu = 0; }   /* UISCALE: the menu's text, on the window */
    b = now_ms();
    if (final) {   /* a frame ends here */
        double ft = g_last_present > 0 ? b - g_last_present : 0;
        g_last_present = b;
        g_frames++;
        g_present_ms += b - a;
        if (ft > g_frame_max) g_frame_max = ft;
    } else {
        g_blt_n++;
        g_blt_ms += b - a;
    }
    return hr;
}
static HRESULT WINAPI perf_bltfast(void *self, DWORD x, DWORD y, void *src, RECT *sr, DWORD t) {
    double a = now_ms();
    HRESULT hr = g_next_bltfast(self, x, y, src, sr, t);
    g_bltfast_n++;
    g_bltfast_ms += now_ms() - a;
    return hr;
}
/* LOCKLOG (task locks 2026-10-20, verify/dlgscale): SC3PERF_LOCKLOG=1 records who calls Lock - the return address and
   two more frames (RtlCaptureStackBackTrace, EBP chain, 0 when it stops) - and every 10 s the stats thread logs the
   top callers as module+offset with their share and lock time. The Reunirse dialog adds ~3,300 Locks per second
   (verify/dlgscale/RESULTS.md); this names the code. Off by default: no cost then. */
#define LL_N 512
typedef struct { DWORD ra[3]; LONG n; double ms; } LL_ENT;
static int    g_locklog;
static LL_ENT g_ll[LL_N];
static volatile LONG g_ll_lost;
static CRITICAL_SECTION g_llcs;
static void ll_note(const DWORD *ra, double ms) {
    DWORD h = (ra[0] ^ (ra[1] * 31) ^ (ra[2] * 131)) * 2654435761u;
    int i, k;
    EnterCriticalSection(&g_llcs);
    for (i = 0; i < 16; i++) {
        k = (int)((h >> 23) + i) & (LL_N - 1);
        if (!g_ll[k].n) { memcpy(g_ll[k].ra, ra, 12); }
        if (!memcmp(g_ll[k].ra, ra, 12)) { g_ll[k].n++; g_ll[k].ms += ms; LeaveCriticalSection(&g_llcs); return; }
    }
    g_ll_lost++;
    LeaveCriticalSection(&g_llcs);
}
static void ll_name(DWORD a, char *out, int cap) {
    HMODULE m = NULL;
    char path[MAX_PATH], *sl;
    if (!a) { lstrcpynA(out, "-", cap); return; }
    if (!GetModuleHandleExA(0x4 | 0x2 /* FROM_ADDRESS | UNCHANGED_REFCOUNT */, (LPCSTR)a, &m) || !m ||
        !GetModuleFileNameA(m, path, sizeof(path))) { _snprintf(out, cap, "0x%08lX", a); out[cap - 1] = 0; return; }
    sl = strrchr(path, '\\');
    _snprintf(out, cap, "%s+0x%lX", sl ? sl + 1 : path, a - (DWORD)m);
    out[cap - 1] = 0;
}
static void ll_dump(void) {
    static LL_ENT snap[LL_N];
    LONG total = 0, lost;
    int i, j, shown = 0;
    EnterCriticalSection(&g_llcs);
    memcpy(snap, g_ll, sizeof(snap)); memset(g_ll, 0, sizeof(g_ll)); lost = g_ll_lost; g_ll_lost = 0;
    LeaveCriticalSection(&g_llcs);
    for (i = 0; i < LL_N; i++) total += snap[i].n;
    if (!total) return;
    logf("LOCKLOG> %ld Locks in 10 s (%ld not recorded: table full)", total, lost);
    while (shown < 12) {
        int best = -1;
        char a0[96], a1[96], a2[96];
        for (j = 0; j < LL_N; j++) if (snap[j].n && (best < 0 || snap[j].n > snap[best].n)) best = j;
        if (best < 0) break;
        ll_name(snap[best].ra[0], a0, sizeof(a0)); ll_name(snap[best].ra[1], a1, sizeof(a1)); ll_name(snap[best].ra[2], a2, sizeof(a2));
        logf("LOCKLOG>   %6ld (%4.1f%%) %7.1f ms  %s <- %s <- %s", snap[best].n, 100.0 * snap[best].n / total, snap[best].ms, a0, a1, a2);
        snap[best].n = 0; shown++;
    }
}

static HRESULT WINAPI perf_lock(void *self, RECT *r, void *desc, DWORD fl, HANDLE ev) {
    double a = now_ms(), d;
    HRESULT hr = g_next_lock(self, r, desc, fl, ev);
    g_lock_n++;
    d = now_ms() - a;
    g_lock_ms += d;
    if (g_locklog) {
        typedef USHORT (WINAPI *CSBT)(ULONG, ULONG, PVOID *, PULONG);
        static CSBT cs;
        PVOID fr[3] = { 0, 0, 0 };
        DWORD ra[3];
        if (!cs) cs = (CSBT)GetProcAddress(GetModuleHandleA("kernel32.dll"), "RtlCaptureStackBackTrace");
        ra[0] = (DWORD)_ReturnAddress();
        if (cs) cs(1, 3, fr, NULL);   /* frame 0 of that is our caller's return as seen from the EBP chain */
        ra[1] = (DWORD)fr[1]; ra[2] = (DWORD)fr[2];
        ll_note(ra, d);
    }
    return hr;
}

static void swap_slot(DWORD *vt, int off, void *mine, void **next) {
    DWORD old;
    if (!VirtualProtect(&vt[off / 4], 4, PAGE_READWRITE, &old)) return;
    *next = (void *)vt[off / 4];
    vt[off / 4] = (DWORD)mine;
    (void)0; /* VirtualProtect(&vt[off / 4], 4, old, &old); left RWX: sc3resize hooks the same vtable */
}

/* The IDirectDrawSurface (v1) vtable is static in ddraw.dll and shared by every v1 surface, so a
   throwaway 1x1 system-memory surface on our OWN DirectDraw object (DDSCL_NORMAL, no window) yields
   the same vtable the game's surfaces use. Verified at runtime: once sc3resize has hooked, our
   slot +0x14 points into sc3resize.dll. */
static DWORD *surface_vtable(void) {
    typedef HRESULT (WINAPI *DDC)(GUID *, void **, void *);
    HMODULE dd = GetModuleHandleA("ddraw.dll");
    DDC ddc = dd ? (DDC)GetProcAddress(dd, "DirectDrawCreate") : NULL;
    void *ddo = NULL, *surf = NULL;
    DWORD desc[0x6c / 4], *vt = NULL;
    if (!ddc || ddc(NULL, &ddo, NULL) != 0 || !ddo) return NULL;
    /* IDirectDraw: SetCooperativeLevel vt+0x50, CreateSurface vt+0x18, Release vt+0x08 */
    if (((HRESULT (WINAPI *)(void *, HWND, DWORD))(*(DWORD **)ddo)[0x50 / 4])(ddo, NULL, 8 /*DDSCL_NORMAL*/) == 0) {
        memset(desc, 0, sizeof(desc));
        desc[0] = 0x6c;              /* dwSize */
        desc[1] = 1 | 2 | 4;         /* DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH */
        desc[2] = 1; desc[3] = 1;    /* height, width */
        desc[0x68 / 4] = 0x40 | 0x800;   /* OFFSCREENPLAIN | SYSTEMMEMORY */
        if (((HRESULT (WINAPI *)(void *, void *, void **, void *))(*(DWORD **)ddo)[0x18 / 4])(ddo, desc, &surf, NULL) == 0 && surf) {
            vt = *(DWORD **)surf;
            ((ULONG (WINAPI *)(void *))vt[0x08 / 4])(surf);
        } else logf("VTABLE> CreateSurface on our probe object failed");
    } else logf("VTABLE> SetCooperativeLevel on our probe object failed");
    ((ULONG (WINAPI *)(void *))(*(DWORD **)ddo)[0x08 / 4])(ddo);
    return vt;
}

static void install_dd_hooks(void) {
    DWORD ddb = (DWORD)GetModuleHandleA("ddraw.dll"), dds = mod_size(ddb);
    int ms;
    DWORD *vt = surface_vtable();
    if (!vt) { logf("DD> no surface vtable - frame stats off"); return; }
    /* sc3resize goes first when it is loaded: wait for its Blt hook (max 120 s) */
    if (GetModuleHandleA("sc3resize.dll")) {
        for (ms = 0; ms < 120000 && vt[0x14 / 4] >= ddb && vt[0x14 / 4] < ddb + dds; ms += 50) Sleep(50);
        logf("DD> Blt slot after waiting for sc3resize: 0x%08lX (%s)", vt[0x14 / 4],
             in_mod(vt[0x14 / 4], "sc3resize.dll") ? "sc3resize hook - chaining after it" :
             "still ddraw - sc3resize did not hook in 120 s");
    }
    g_vt = vt;
    swap_slot(vt, 0x14, (void *)perf_blt, (void **)&g_next_blt);
    swap_slot(vt, 0x1c, (void *)perf_bltfast, (void **)&g_next_bltfast);
    swap_slot(vt, 0x64, (void *)perf_lock, (void **)&g_next_lock);
    logf("DD> hooked Blt/BltFast/Lock on vtable 0x%08lX (next 0x%08lX 0x%08lX 0x%08lX)",
         (DWORD)vt, (DWORD)g_next_blt, (DWORD)g_next_bltfast, (DWORD)g_next_lock);
}

/* ---------------------------------------------------------------- SYSMEM experiment */
static BYTE g_dummy_flag;
static void patch_sysmem(DWORD gz) {
    /* `mov [imm32], al` - the imm32 is relocated with the module, so expect gz + 0x6cbcd */
    BYTE *p = (BYTE *)gz + 0x140fe, *flag = (BYTE *)gz + 0x6cbcd, *inited = (BYTE *)gz + 0x6cbcc;
    DWORD old;
    if (p[0] != 0xa2 || *(DWORD *)(p + 1) != gz + 0x6cbcd) {
        logf("SYSMEM> GZGraphicD+0x140fe differs from shipped (%02X %08lX) - not patched", p[0], *(DWORD *)(p + 1));
        return;
    }
    if (!VirtualProtect(p, 5, PAGE_EXECUTE_READWRITE, &old)) return;
    *(DWORD *)(p + 1) = (DWORD)&g_dummy_flag;
    (void)0; /* protection left RWX on purpose: several mods patch the same pages from their own threads at module load, and a restore landing mid-write in another mod faulted the game (sc3bigcity+0x5B89 memcpy, 2026-10-09) */ /* VirtualProtect(p, 5, old, &old); */
    FlushInstructionCache(GetCurrentProcess(), p, 5);
    if (VirtualProtect(flag, 1, PAGE_READWRITE, &old)) { *flag = 1; (void)0; /* VirtualProtect(flag, 1, old, &old); */ }
    logf("SYSMEM> forced: flag 0x1006cbcd = 1, store at 0x100140fe redirected (graphics init %s)",
         *inited ? "ALREADY RAN - surfaces made before now stay where they are" : "not yet run - in time");
}

/* ---------------------------------------------------------------- SIMCLOCK */
static void patch_clock(DWORD sc) {
    /* FUN_10009d5a: 6a 00 (push 0) / 68 e8 03 00 00 (push 1000) / 8b cb / ff 50 14 (timer vt+0x14) */
    static const BYTE want[] = {0x6a, 0x00, 0x68, 0xe8, 0x03, 0x00, 0x00, 0x8b, 0xcb, 0xff, 0x50, 0x14};
    BYTE *p = (BYTE *)sc + 0x9d96;
    DWORD old;
    if (memcmp(p, want, sizeof(want))) {
        logf("SIMCLOCK> SIMCITY+0x9d96 differs from shipped - not patched");
        return;
    }
    if (!VirtualProtect(p + 3, 4, PAGE_EXECUTE_READWRITE, &old)) return;
    *(DWORD *)(p + 3) = (DWORD)g_clock_ms;
    (void)0; /* VirtualProtect(p + 3, 4, old, &old); */
    FlushInstructionCache(GetCurrentProcess(), p + 3, 4);
    logf("SIMCLOCK> clock timer period 1000 -> %d ms", g_clock_ms);
}

static void patch_sprites(DWORD spr) {
    static const BYTE want_cmp[] = {0xd8, 0x9e, 0xd4, 0x03, 0x00, 0x00};
    static const BYTE want_slp[] = {0x68, 0x20, 0x4e, 0x00, 0x00, 0xe8};
    BYTE *c = (BYTE *)spr + 0x8aaf, *z = (BYTE *)spr + 0x8cd5;
    DWORD old;
    if (memcmp(c, want_cmp, sizeof(want_cmp)) || memcmp(z, want_slp, sizeof(want_slp))) {
        logf("SPRITES> SIMSPR+0x8aaf / +0x8cd5 differ from shipped - not patched");
        return;
    }
    if (!VirtualProtect(c, 0x230, PAGE_EXECUTE_READWRITE, &old)) return;
    c[1] = 0x1d;                                   /* fcomp dword ptr [abs32] */
    *(DWORD *)(c + 2) = (DWORD)&g_spr_budget;
    *(DWORD *)(z + 1) = (DWORD)g_spr_sleep_us;
    (void)0; /* VirtualProtect(c, 0x230, old, &old); */
    FlushInstructionCache(GetCurrentProcess(), c, 0x230);
    logf("SPRITES> loader budget 5.0 -> %.1f per wake, sleep 20000 -> %d us", g_spr_budget, g_spr_sleep_us);
}

typedef void (__fastcall *SPIRAL_SEED)(void *spiral, void *edx, int cx, int cy);   /* thiscall, ret 8 */
typedef void (__fastcall *THIS0)(void *self, void *edx);                            /* thiscall, no args */

static void __cdecl spr_follow_check(BYTE *iso) {
    BYTE *spiral, *lockobj;
    DWORD *q, *front, *lvt;
    LONG cx, cy, kind;
    if (!iso || IsBadReadPtr(iso, 0x470)) return;
    spiral = iso + 0x3e8;
    lockobj = iso + 0x46c;
    lvt = *(DWORD **)lockobj;
    if (!lvt || IsBadReadPtr(lvt, 0xc)) return;
    ((THIS0)lvt[1])(lockobj, NULL);                                  /* lock */
    q = *(DWORD **)(iso + 0x444);
    front = q ? (DWORD *)q[0] : NULL;
    kind = (front && front != q) ? (LONG)front[2] : -1;
    if (kind >= 1 && kind <= 4 && spiral[0x2c] != 2) {
        LONG *cam = (LONG *)(iso + 0x340), *b = (LONG *)(spiral + 0x10);
        cx = (cam[0] + cam[2]) / 2; cy = (cam[1] + cam[3]) / 2;
        if (cx < b[0]) cx = b[0]; if (cx > b[2]) cx = b[2];
        if (cy < b[1]) cy = b[1]; if (cy > b[3]) cy = b[3];
        if (labs(cx - g_seed_x) + labs(cy - g_seed_y) >= 8) {
            ((SPIRAL_SEED)(g_spr_base + 0x5666))(spiral, NULL, cx, cy);
            ((THIS0)(g_spr_base + 0x868b))(iso, NULL);
            g_seed_x = cx; g_seed_y = cy;
            InterlockedIncrement(&g_reseeds);
        }
    } else if (kind < 1) {
        g_seed_x = g_seed_y = -100000;                                 /* idle: next job seeds itself */
    }
    ((THIS0)lvt[2])(lockobj, NULL);                                  /* unlock */
}

/* Entered by `call` from 0x10008cda with [esp] = return, [esp+4] = sleep microseconds, esi = iso. */
static __declspec(naked) void spr_sleep_stub(void) {
    __asm {
        pushad
        push esi
        call spr_follow_check
        add esp, 4
        popad
        jmp dword ptr [g_sleep_orig]
    }
}

static void patch_follow(DWORD spr) {
    BYTE *c = (BYTE *)spr + 0x8cda;
    DWORD old, tgt;
    if (c[0] != 0xe8) { logf("SPR_FOLLOW> SIMSPR+0x8cda is not a call - not patched"); return; }
    tgt = (DWORD)(c + 5) + *(DWORD *)(c + 1);
    if (tgt != spr + 0x54c5e) { logf("SPR_FOLLOW> call target 0x%08lX != SIMSPR+0x54c5e - not patched", tgt); return; }
    g_spr_base = spr; g_sleep_orig = tgt;
    if (!VirtualProtect(c, 5, PAGE_EXECUTE_READWRITE, &old)) return;
    *(DWORD *)(c + 1) = (DWORD)spr_sleep_stub - (DWORD)(c + 5);
    (void)0; /* VirtualProtect(c, 5, old, &old); */
    FlushInstructionCache(GetCurrentProcess(), c, 5);
    logf("SPR_FOLLOW> loader re-seeds its spiral at the camera when it moves >= 8 tiles");
}

/* ---------------------------------------------------------------- FAST_FTOL */
static __declspec(naked) void ftol_fast(void) {
    __asm {
        sub esp, 8
        fisttp qword ptr [esp]
        mov eax, dword ptr [esp]
        mov edx, dword ptr [esp + 4]
        add esp, 8
        ret
    }
}

static void patch_ftol(void) {
    HMODULE crt = GetModuleHandleA("msvcrt.dll");
    BYTE *f = crt ? (BYTE *)GetProcAddress(crt, "_ftol") : NULL;
    DWORD old;
    if (!IsProcessorFeaturePresent(13 /* PF_SSE3_INSTRUCTIONS_AVAILABLE */)) { logf("FAST_FTOL> no SSE3 - not patched"); return; }
    if (!f) { logf("FAST_FTOL> msvcrt!_ftol not found"); return; }
    if (!VirtualProtect(f, 5, PAGE_EXECUTE_READWRITE, &old)) return;
    f[0] = 0xE9; *(DWORD *)(f + 1) = (DWORD)ftol_fast - (DWORD)(f + 5);
    FlushInstructionCache(GetCurrentProcess(), f, 5);
    logf("FAST_FTOL> msvcrt!_ftol (0x%08lX) -> FISTTP version", (DWORD)f);
}

/* ---------------------------------------------------------------- TRANSIT_CLEAR */
static DWORD  g_tr_base;
static BYTE  *g_tr_grid, *g_tr_buf, **g_tr_orig;
static DWORD  g_tr_rows, g_tr_w, g_tr_size;
static int    g_tr_val = -1;
static PVOID  g_tr_addrs[2048];
static volatile LONG g_tr_full, g_tr_part, g_tr_pages;

static void tr_full(void) {
    memset(g_tr_buf, g_tr_val, g_tr_size);
    ResetWriteWatch(g_tr_buf, g_tr_size);
    InterlockedIncrement(&g_tr_full);
}

static int tr_install(BYTE *grid) {
    DWORD rows = *(DWORD *)(grid + 4), w = *(DWORD *)(grid + 8), y;
    BYTE **tab = *(BYTE ***)(grid + 0xc), *buf;
    if (!rows || !w || rows > 4096 || w > 4096 || !tab || IsBadReadPtr(tab, rows * 4)) return 0;
    buf = (BYTE *)VirtualAlloc(NULL, rows * w, MEM_RESERVE | MEM_COMMIT | MEM_WRITE_WATCH, PAGE_READWRITE);
    if (!buf) { logf("TRANSIT_CLEAR> VirtualAlloc(write-watch) failed %lu - full clears", GetLastError()); return 0; }
    g_tr_orig = (BYTE **)HeapAlloc(GetProcessHeap(), 0, rows * sizeof(BYTE *));
    if (!g_tr_orig) { VirtualFree(buf, 0, MEM_RELEASE); return 0; }
    for (y = 0; y < rows; y++) {
        g_tr_orig[y] = tab[y];
        memcpy(buf + y * w, tab[y], w);
        tab[y] = buf + y * w;
    }
    g_tr_grid = grid; g_tr_buf = buf; g_tr_rows = rows; g_tr_w = w; g_tr_size = rows * w;
    logf("TRANSIT_CLEAR> marker grid 0x%08lX (%lux%lu) moved into a write-watch buffer", (DWORD)grid, w, rows);
    return 1;
}

/* Extra marker grids made by TRAFFIC_MT (one per worker), each in its own write-watch buffer. */
#define TRX_MAX 16
typedef struct { BYTE *grid, *buf; DWORD size; int val; PVOID addrs[2048]; } TRX;
static TRX  g_trx[TRX_MAX];
static volatile LONG g_ntrx;
static void tr_register(BYTE *grid, BYTE *buf, DWORD size) {
    LONG k = g_ntrx;
    if (k >= TRX_MAX) return;
    g_trx[k].grid = grid; g_trx[k].buf = buf; g_trx[k].size = size; g_trx[k].val = -1;
    InterlockedIncrement(&g_ntrx);
}
static void trx_clear(TRX *t, int v) {
    ULONG_PTR n = 2048, i;
    DWORD gran = 0;
    if (v != t->val || GetWriteWatch(0, t->buf, t->size, t->addrs, &n, &gran) != 0 || !gran || n >= 2048) {
        memset(t->buf, v, t->size);
        t->val = v;
    } else {
        for (i = 0; i < n; i++) {
            BYTE *pg = (BYTE *)t->addrs[i];
            DWORD len = gran;
            if (pg + len > t->buf + t->size) len = (DWORD)(t->buf + t->size - pg);
            memset(pg, v, len);
        }
    }
    ResetWriteWatch(t->buf, t->size);
}

/* Replaces the call to FUN_1000a5cb in the trip router: thiscall(grid), one stack arg (byte *value), ret 4. */
static void __fastcall tr_clear(BYTE *grid, void *edx, BYTE *val) {
    ULONG_PTR n = sizeof(g_tr_addrs) / sizeof(g_tr_addrs[0]), i;
    DWORD gran = 0;
    LONG k;
    (void)edx;
    for (k = 0; k < g_ntrx; k++) if (g_trx[k].grid == grid) { trx_clear(&g_trx[k], *val); return; }
    if (grid != g_tr_grid) {
        if (g_tr_grid || !tr_install(grid)) {          /* a second grid: leave it to the original */
            DWORD y, rows = *(DWORD *)(grid + 4), w = *(DWORD *)(grid + 8);
            BYTE **tab = *(BYTE ***)(grid + 0xc);
            for (y = 0; y < rows; y++) memset(tab[y], *val, w);
            return;
        }
        g_tr_val = *val;
        tr_full();
        return;
    }
    if ((int)*val != g_tr_val) { g_tr_val = *val; tr_full(); return; }
    if (GetWriteWatch(0, g_tr_buf, g_tr_size, g_tr_addrs, &n, &gran) != 0 || !gran ||
        n >= sizeof(g_tr_addrs) / sizeof(g_tr_addrs[0])) {
        tr_full();
        return;
    }
    for (i = 0; i < n; i++) {
        BYTE *pg = (BYTE *)g_tr_addrs[i];
        DWORD len = gran;
        if (pg + len > g_tr_buf + g_tr_size) len = (DWORD)(g_tr_buf + g_tr_size - pg);
        memset(pg, g_tr_val, len);
    }
    ResetWriteWatch(g_tr_buf, g_tr_size);
    InterlockedIncrement(&g_tr_part);
    InterlockedExchangeAdd(&g_tr_pages, (LONG)n);
}

typedef void (__cdecl *TR_DELETE)(void *);
/* Replaces FUN_1000ab16, the byte grid's destructor body (fastcall, grid in ecx), reached by a JMP. */
static void smooth_on_grid_dtor(void);
static void __fastcall tr_dtor(DWORD *g, void *edx) {
    TR_DELETE del = (TR_DELETE)(g_tr_base + 0x1806f);
    int i;
    (void)edx;
    if ((BYTE *)g == g_tr_grid) smooth_on_grid_dtor();   /* city teardown: no worker may route past this point */
    g[0] = g_tr_base + 0x1a5d8;
    if (!g[3]) return;
    if ((BYTE *)g == g_tr_grid) {
        DWORD y;
        for (y = 0; y < g_tr_rows; y++) ((BYTE **)g[3])[y] = g_tr_orig[y];
        HeapFree(GetProcessHeap(), 0, g_tr_orig); g_tr_orig = NULL;
        VirtualFree(g_tr_buf, 0, MEM_RELEASE); g_tr_buf = NULL;
        logf("TRANSIT_CLEAR> grid destroyed: %ld full clears, %ld partial (avg %.1f pages)", g_tr_full, g_tr_part,
             g_tr_part ? (double)g_tr_pages / g_tr_part : 0.0);
        g_tr_grid = NULL;
    }
    for (i = (int)g[1] - 1; i >= 0; i--) del(((void **)g[3])[i]);
    del((void *)g[3]);
}

static void patch_trclear(DWORD st) {
    BYTE *c = (BYTE *)st + 0x7158, *d = (BYTE *)st + 0xab16;
    static const BYTE dhead[] = { 0x57, 0x8b, 0xf9, 0x83, 0x7f, 0x0c, 0x00, 0xc7, 0x07 };
    DWORD old;
    if (c[0] != 0xe8 || (DWORD)(c + 5) + *(DWORD *)(c + 1) != st + 0xa5cb || memcmp(d, dhead, sizeof(dhead)) ||
        *(DWORD *)(d + 9) != st + 0x1a5d8) {
        logf("TRANSIT_CLEAR> SIMTRANSIT+0x7158/0xab16 differ from shipped - not patched");
        return;
    }
    g_tr_base = st;
    if (!VirtualProtect(c, 5, PAGE_EXECUTE_READWRITE, &old) || !VirtualProtect(d, 5, PAGE_EXECUTE_READWRITE, &old)) return;
    *(DWORD *)(c + 1) = (DWORD)tr_clear - (DWORD)(c + 5);
    d[0] = 0xE9; *(DWORD *)(d + 1) = (DWORD)tr_dtor - (DWORD)(d + 5);
    FlushInstructionCache(GetCurrentProcess(), c, 5);
    FlushInstructionCache(GetCurrentProcess(), d, 5);
    logf("TRANSIT_CLEAR> trip router clears only the written pages of its marker grid");
}

/* ---------------------------------------------------------------- TRAFFIC_MT (2026-10-09, default on: 8 workers)
   Spreads the monthly per-building trips across worker threads. Design and the read/write list of one trip:
   PERFORMANCE.md Finding 20 (from the static study scratchpad worker_transit_mt.md).
   - The per-building issuer SimTransit FUN_100097b9 (iOS BuildingTrafficMonthly::Apply) calls layer vt+0x4c =
     FUN_10006fe3 (trip from an occupant, thiscall, 7 args, ret 0x1c) and discards the result. Those calls are
     QUEUED (occupant AddRef'd) and return 1; every other caller of FUN_10006fe3, and FUN_1000706a (trip from a
     cell) and the stats pass FUN_10009242 first FLUSH the queue, so they see every queued trip applied.
   - A flush hands the queue to N worker threads. Each routes on its own SHADOW of the 0x110-byte layer: same grids
     and settings, but its own visited-marker grid (+0x78, write-watch cleared like transit_clear), its own cell
     iterator (+0x1c..+0x53, vector zeroed) and its own counters (+0xb0, +0xb4, +0x100, added back afterwards).
   - The two shared writers are replaced, for every caller, by atomic versions with the same arithmetic:
     congestion FUN_10006edd (saturating byte add on +0x6c/+0x70/+0x74, clamp [0, TrafficMaxDensity]) and trip
     result bits FUN_10006a72 (+0x7c tried / +0x80 succeeded words, InterlockedOr/And).
   Results differ from serial: trips in one batch route against congestion as the other workers leave it, not in
   a fixed order. traffic_mt=N workers (default 8, capped at logical CPUs - 1; 0 = off), traffic_mt_batch = queue size that forces a flush. */
static void prof_add_thread(HANDLE th, DWORD tid);
static DWORD g_tls_pool_fwd(void);
static DWORD g_tls_worker_fwd(void);
static void geom_hold_fwd(BYTE *l);
static void geom_release_fwd(void);
typedef DWORD (__fastcall *TRIP_FN)(BYTE *layer, void *edx, DWORD occ, DWORD kind, DWORD len, DWORD flag,
                                     DWORD p5, DWORD p6, DWORD p7);
typedef struct { DWORD occ, kind, len, flag, p5, p6, p7; } TJOB;
#define MT_MAXW 16
static int     g_mt = 0, g_mt_batch = 4096, g_mtlocks = 1, g_geomheld = 0;
static DWORD   g_mt_st;                          /* SimTransit base */
static BYTE   *g_mt_tramp_6fe3, *g_mt_tramp_706a;
static TJOB   *g_mtq;
static volatile LONG g_mtq_n, g_mtq_next, g_mt_left;
static double  g_mtq_t0;
static CRITICAL_SECTION g_mtcs;
static HANDLE  g_mt_go[MT_MAXW], g_mt_done;
static BYTE   *g_mt_shadow[MT_MAXW];
static int     g_mt_threads;
static volatile LONG g_mt_batches, g_mt_jobs, g_mt_faults;
static double  g_mt_ms;

static BYTE *mt_layer(void) { return g_mt_st ? *(BYTE **)(g_mt_st + 0x1fdb8) : NULL; }

/* ---- atomic congestion deposit: FUN_10006edd(this, x, y, char amount, mask), thiscall, ret 0x10 */
static void mt_sat_add(BYTE *cell, int amount, int maxv) {
    volatile LONG *w = (volatile LONG *)((DWORD)cell & ~3u);
    int sh = ((DWORD)cell & 3) * 8;
    for (;;) {
        LONG o = *w, n;
        int v = (int)((o >> sh) & 0xff) + amount;
        if (v < 1) v = 0;
        if (v >= maxv) v = maxv;
        n = (o & ~(0xff << sh)) | (v << sh);
        if (n == o || InterlockedCompareExchange(w, n, o) == o) return;
    }
}
static void __fastcall mt_congestion(BYTE *self, void *edx, int x, int y, DWORD amount, DWORD mask) {
    int a = (signed char)(amount & 0xff), maxv = *(BYTE *)(g_mt_st + 0x1f0bf);
    (void)edx;
    if (mask & 0x35) mt_sat_add(*(BYTE **)(*(BYTE **)(*(BYTE **)(self + 0x6c) + 0xc) + x * 4) + y, a, maxv);
    if (mask & 2)    mt_sat_add(*(BYTE **)(*(BYTE **)(*(BYTE **)(self + 0x70) + 0xc) + x * 4) + y, a, maxv);
    if (mask & 8)    mt_sat_add(*(BYTE **)(*(BYTE **)(*(BYTE **)(self + 0x74) + 0xc) + x * 4) + y, a, maxv);
}

/* ---- atomic trip-result bits: FUN_10006a72(this, x0, y0, x1, y1, char mode), thiscall, ret 0x14.
   Bit grid (FUN_10005562): word = *(*(grid+0x10) + x*4) + (y>>5)*4, bit y&31.
   mode 0: tried=1 ok=1; mode 1: tried=1 ok=0; else: tried=0 ok=0. */
static void mt_bits(BYTE *grid, DWORD x0, DWORD y0, DWORD x1, DWORD y1, int set) {
    DWORD x, y;
    for (x = x0; x <= x1; x++)
        for (y = y0; y <= y1; y++) {
            volatile LONG *w = (volatile LONG *)(*(BYTE **)(*(BYTE **)(grid + 0x10) + x * 4) + (y >> 5) * 4);
            LONG b = 1L << (y & 31);
            if (set) InterlockedOr(w, b); else InterlockedAnd(w, ~b);
        }
}
static void __fastcall mt_result(BYTE *self, void *edx, DWORD x0, DWORD y0, DWORD x1, DWORD y1, DWORD mode) {
    int m = (int)(mode & 0xff);
    (void)edx;
    mt_bits(*(BYTE **)(self + 0x7c), x0, y0, x1, y1, m == 0 || m == 1);
    mt_bits(*(BYTE **)(self + 0x80), x0, y0, x1, y1, m == 0);
}

/* ---- workers */
static BYTE *mt_make_shadow(BYTE *layer) {
    BYTE *s = (BYTE *)VirtualAlloc(NULL, 0x200, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    BYTE *rg = *(BYTE **)(layer + 0x78), *g, *buf, **rows;
    DWORD nrows, w, y;
    if (!s || !rg) return NULL;
    memcpy(s, layer, 0x110);
    memset(s + 0x1c + 0x20, 0, 12);              /* iterator's own vector (list mode), never shared */
    nrows = *(DWORD *)(rg + 4); w = *(DWORD *)(rg + 8);
    g = (BYTE *)VirtualAlloc(NULL, 0x20, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    rows = (BYTE **)VirtualAlloc(NULL, nrows * 4, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    buf = (BYTE *)VirtualAlloc(NULL, nrows * w, MEM_RESERVE | MEM_COMMIT | MEM_WRITE_WATCH, PAGE_READWRITE);
    if (!g || !rows || !buf) return NULL;
    memcpy(g, rg, 0x10);
    for (y = 0; y < nrows; y++) rows[y] = buf + y * w;
    *(BYTE ***)(g + 0xc) = rows;
    tr_register(g, buf, nrows * w);
    *(BYTE **)(s + 0x78) = g;
    *(BYTE **)(s + 0x1f0) = layer;               /* RELOAD: the layer this shadow was shaped for */
    return s;
}
/* RELOAD (task reload1024, owner 2026-10-23: "loaded Europolis 1024 a second time, the game crashed"). The shadows
   are made once, from the first city's traffic layer, and the refresh kept their marker grid (+0x78) and iterator
   (+0x1c..+0x54) for good. Measured after Berlin (256) -> Europolis 1024 in one game: the workers routed 1024 trips
   on a 256-row grid, 39,336 of 87,038 background trips faulted (msvcrt memset in the grid clear, sc3netmod rf_close
   -> ld_mark reading row pointers past the 256 rows) and the game then stopped presenting (0 fps). When the live
   layer or its grid size changes, the shadow now takes the new city's iterator (own vector emptied, as at creation)
   and a marker grid of the new size; the old grid's buffers are released and its write-watch entry follows. */
static int mt_reshape_shadow(BYTE *s, BYTE *layer) {
    BYTE *rg = *(BYTE **)(layer + 0x78), *g = *(BYTE **)(s + 0x78), *buf, **rows, *obuf = NULL, **orows;
    DWORD nrows, w, y;
    LONG k;
    memcpy(s + 0x1c, layer + 0x1c, 0x38);
    memset(s + 0x1c + 0x20, 0, 12);
    *(BYTE **)(s + 0x1f0) = layer;
    if (!rg || !g) return 0;
    nrows = *(DWORD *)(rg + 4); w = *(DWORD *)(rg + 8);
    if (nrows == *(DWORD *)(g + 4) && w == *(DWORD *)(g + 8)) return 1;
    rows = (BYTE **)VirtualAlloc(NULL, nrows * 4, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    buf = (BYTE *)VirtualAlloc(NULL, nrows * w, MEM_RESERVE | MEM_COMMIT | MEM_WRITE_WATCH, PAGE_READWRITE);
    if (!rows || !buf) {
        if (rows) VirtualFree(rows, 0, MEM_RELEASE);
        if (buf) VirtualFree(buf, 0, MEM_RELEASE);
        logf("TRAFFIC_MT> RELOAD: no memory for a %lux%lu worker grid - this worker skips trips", w, nrows);
        return 0;
    }
    for (y = 0; y < nrows; y++) rows[y] = buf + y * w;
    orows = *(BYTE ***)(g + 0xc);
    for (k = 0; k < g_ntrx; k++)
        if (g_trx[k].grid == g) { obuf = g_trx[k].buf; g_trx[k].buf = buf; g_trx[k].size = nrows * w; g_trx[k].val = -1; }
    logf("TRAFFIC_MT> RELOAD: worker grid 0x%08lX %lux%lu -> %lux%lu (layer 0x%08lX)", (DWORD)g,
         *(DWORD *)(g + 8), *(DWORD *)(g + 4), w, nrows, (DWORD)layer);
    memcpy(g, rg, 0x10);
    *(BYTE ***)(g + 0xc) = rows;
    if (orows) VirtualFree(orows, 0, MEM_RELEASE);
    if (obuf) VirtualFree(obuf, 0, MEM_RELEASE);
    return 1;
}
/* returns 0 when the shadow cannot be used for this layer */
static int mt_refresh_shadow(BYTE *s, BYTE *layer) {
    BYTE keep[0x38], *g = *(BYTE **)(s + 0x78), *rg = *(BYTE **)(layer + 0x78);
    if (g_reloadshadow && (*(BYTE **)(s + 0x1f0) != layer || !g || !rg ||
        *(DWORD *)(rg + 4) != *(DWORD *)(g + 4) || *(DWORD *)(rg + 8) != *(DWORD *)(g + 8)))
        if (!mt_reshape_shadow(s, layer)) return 0;
    memcpy(keep, s + 0x1c, 0x38);
    memcpy(s, layer, 0x110);
    memcpy(s + 0x1c, keep, 0x38);
    *(BYTE **)(s + 0x78) = g;
    *(DWORD *)(s + 0xb0) = 0; *(DWORD *)(s + 0xb4) = 0; *(float *)(s + 0x100) = 0.0f;
    return 1;
}
static int mt_run_job(BYTE *s, TJOB *j) {
    __try {
        ((TRIP_FN)g_mt_tramp_6fe3)(s, NULL, j->occ, j->kind, j->len, j->flag, j->p5, j->p6, j->p7);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        InterlockedIncrement(&g_mt_faults);
        return 0;
    }
    return 1;
}
static void *g_mt_pool[MT_MAXW];
typedef void (__fastcall *THIS0F)(DWORD self, void *edx);
static BYTE *make_tramp(BYTE *src, int n);
static void jmp_to(BYTE *at, void *to);
/* ---------------------------------------------------------------- TRAFFIC_SMOOTH (2026-10-10, with TRAFFIC_MT)
   The synchronous batches kept the clock stopped while ~87k trips routed on a traffic day (Finding 23). Here the
   queue is a large ring the workers drain CONTINUOUSLY, in chunks of 32, while the sim thread and the clock carry on:
   - the sim thread enqueues (occupant AddRef'd) and never routes; finished trips' occupants come back through a
     second ring and are Released on the sim thread (a building's last Release must not run its destructor on a
     worker);
   - each chunk runs on the worker's shadow layer refreshed from the live layer; counters (+0xb0 attempts,
     +0xb4 failures, +0x100 float) go into shared accumulators the sim thread adds to the layer;
   - the sim thread WAITS for the queue to drain only before the monthly stats pass FUN_10009242 (it decays and
     publishes the congestion grids), before any other trip call (FUN_1000706a, non-issuer FUN_10006fe3), when the
     ring is full, and before the traffic layer is destroyed: its Release FUN_10005237 (refcount +0xc) is hooked and
     drains first when the count is about to reach 0. Workers also check the live layer pointer before each chunk.
   Trips are the same; their congestion and result bits land later (up to the end of the month). traffic_mt_smooth=0
   restores the synchronous batches. */
#define SQ_CAP (1 << 19)
#define SQ_CHUNK 32
static int     g_smooth = 1;
static TJOB   *g_sq;
static DWORD  *g_sdone;
static volatile LONG g_sq_head, g_sq_tail, g_sq_inflight, g_sd_head, g_sd_tail;
static CRITICAL_SECTION g_sqcs, g_sdcs, g_acccs;
static HANDLE  g_sq_evt;
static BYTE   *g_sq_layer;
static LONG    g_acc_b0, g_acc_b4;
static double  g_acc_100;
static volatile LONG g_sq_jobs, g_sq_drains;
static double  g_sq_drain_ms;
static DWORD   g_dr_ret[16], g_dr_cnt[16];      /* who asked for a drain: caller return address, count */
static void drain_note(DWORD ret) {
    int k;
    for (k = 0; k < 16; k++) {
        if (g_dr_cnt[k] && g_dr_ret[k] == ret) { g_dr_cnt[k]++; return; }
        if (!g_dr_cnt[k]) { g_dr_ret[k] = ret; g_dr_cnt[k] = 1; return; }
    }
}
static BYTE   *g_rel_tramp;

static void smooth_publish(BYTE *s) {
    EnterCriticalSection(&g_acccs);
    g_acc_b0 += *(LONG *)(s + 0xb0); g_acc_b4 += *(LONG *)(s + 0xb4); g_acc_100 += *(float *)(s + 0x100);
    LeaveCriticalSection(&g_acccs);
    *(DWORD *)(s + 0xb0) = 0; *(DWORD *)(s + 0xb4) = 0; *(float *)(s + 0x100) = 0.0f;
}
/* worker loop body for smooth mode; returns when nothing is queued (caller waits on the event) */
static void smooth_work(int me) {
    for (;;) {
        LONG start, n, i;
        BYTE *layer = g_sq_layer, *s = g_mt_shadow[me];
        EnterCriticalSection(&g_sqcs);
        n = g_sq_tail - g_sq_head;
        if (n > SQ_CHUNK) n = SQ_CHUNK;
        start = g_sq_head;
        if (n > 0) { g_sq_head += n; InterlockedExchangeAdd(&g_sq_inflight, n); }
        LeaveCriticalSection(&g_sqcs);
        if (n <= 0) return;
        if (layer && layer == mt_layer() && mt_refresh_shadow(s, layer)) {
            for (i = 0; i < n; i++) mt_run_job(s, &g_sq[(start + i) & (SQ_CAP - 1)]);
            smooth_publish(s);
        }
        EnterCriticalSection(&g_sdcs);                     /* occupants go back to the sim thread for Release */
        for (i = 0; i < n; i++) g_sdone[(g_sd_tail++) & (SQ_CAP - 1)] = g_sq[(start + i) & (SQ_CAP - 1)].occ;
        LeaveCriticalSection(&g_sdcs);
        InterlockedExchangeAdd(&g_sq_inflight, -n);
        InterlockedExchangeAdd(&g_sq_jobs, n);
    }
}
/* sim thread: Release finished trips' occupants, add the workers' counters to the layer */
static void smooth_settle(BYTE *layer) {
    for (;;) {
        DWORD o;
        EnterCriticalSection(&g_sdcs);
        if (g_sd_head == g_sd_tail) { LeaveCriticalSection(&g_sdcs); break; }
        o = g_sdone[(g_sd_head++) & (SQ_CAP - 1)];
        LeaveCriticalSection(&g_sdcs);
        ((THIS0F)(*(DWORD **)o)[2])(o, NULL);
    }
    if (layer) {
        EnterCriticalSection(&g_acccs);
        *(LONG *)(layer + 0xb0) += g_acc_b0; *(LONG *)(layer + 0xb4) += g_acc_b4;
        *(float *)(layer + 0x100) += (float)g_acc_100;
        g_acc_b0 = g_acc_b4 = 0; g_acc_100 = 0;
        LeaveCriticalSection(&g_acccs);
    }
}
/* wait until every queued trip has run; the waiting thread helps by routing on worker 0's shadow? no: it waits */
static void smooth_drain(void) {
    double t0;
    if (!g_sq) return;
    if (g_sq_tail == g_sq_head && !g_sq_inflight && g_sd_head == g_sd_tail) return;
    t0 = now_ms();
    SetEvent(g_sq_evt);
    while (g_sq_tail != g_sq_head || g_sq_inflight) Sleep(0);
    smooth_settle(g_sq_layer);
    g_sq_drain_ms += now_ms() - t0;
    g_sq_drains++;
}
static void smooth_enqueue(BYTE *layer, DWORD occ, DWORD kind, DWORD len, DWORD flag, DWORD p5, DWORD p6, DWORD p7) {
    TJOB *j;
    if (g_sq_layer != layer) { smooth_drain(); g_sq_layer = layer; }
    smooth_settle(layer);
    while (g_sq_tail - g_sq_head >= SQ_CAP - SQ_CHUNK - 1) { SetEvent(g_sq_evt); Sleep(1); smooth_settle(layer); }
    j = &g_sq[g_sq_tail & (SQ_CAP - 1)];
    j->occ = occ; j->kind = kind; j->len = len; j->flag = flag; j->p5 = p5; j->p6 = p6; j->p7 = p7;
    ((THIS0F)(*(DWORD **)occ)[1])(occ, NULL);           /* AddRef: held until the trip has run */
    InterlockedIncrement(&g_sq_tail);
    if (((g_sq_tail - g_sq_head) & 15) == 1) SetEvent(g_sq_evt);
}
/* traffic layer Release FUN_10005237 (fastcall this, ret): drain before the last reference goes */
/* Traffic layer AddRef 0x1000526c / Release 0x10005237 (refcount +0xc, plus SimTransit's stats object FUN_100010a6
   vt+4 / vt+0x28): plain inc / dec, and the layer gets message fan-out from the sim thread and the game thread. A lost
   update freed the layer early: the city teardown (SIMCITY FUN_100066a0 at 0x100069b8) then released it again - index
   19 of city+0x94 (teardown probe) with its vtable already overwritten by text ("dern"). Both are atomic now, with the
   same results; Release also drains the TRAFFIC_SMOOTH queue before the layer can die. */
typedef void (__fastcall *TVOID0)(void *self, void *edx);
typedef BYTE *(__cdecl *TSTATS_FN)(void);
typedef void (__fastcall *VDEL1_FN)(BYTE *self, void *edx, DWORD flags);
static LONG __fastcall tl_addref(BYTE *self) {
    LONG n = InterlockedIncrement((volatile LONG *)(self + 0xc));
    BYTE *st = ((TSTATS_FN)(g_mt_st + 0x10a6))();
    ((TVOID0)(*(DWORD **)st)[1])(st, NULL);
    return n;
}
static LONG __fastcall smooth_layer_release(BYTE *self) {
    volatile LONG *rc = (volatile LONG *)(self + 0xc);
    LONG o, n;
    for (;;) {
        o = *rc;
        if (!o) { n = 0; break; }                    /* the original skips the decrement and destroys */
        if (InterlockedCompareExchange(rc, o - 1, o) == o) {
            BYTE *st = ((TSTATS_FN)(g_mt_st + 0x10a6))();
            ((TVOID0)(*(DWORD **)st)[0x28 / 4])(st, NULL);
            n = o - 1;
            break;
        }
    }
    if (n) return n;
    if (g_smooth && self == g_sq_layer) {
        logf("TRAFFIC_SMOOTH> traffic layer released: draining %ld queued trips first", g_sq_tail - g_sq_head);
        smooth_drain();
        g_sq_layer = NULL;
    }
    ((VDEL1_FN)(*(DWORD **)self)[0xc4 / 4])(self, NULL, 1);
    return 0;
}
/* The traffic layer's destructor body FUN_1000154e (called by the deleting destructor vt+0xc4 = 0x1000152a): a
   shutdown test destroyed the layer WITHOUT passing through Release, so the drain is also hooked here. Its entry is
   `mov eax, <handler>` / `call _EH_prolog`, replayed by the stub as for the day hook. */
static DWORD g_ldt_imm, g_ldt_ehp, g_ldt_cont;
static void __cdecl smooth_on_dtor(BYTE *self) {
    if (g_smooth && self && self == g_sq_layer) {
        logf("TRAFFIC_SMOOTH> traffic layer destroyed: draining %ld queued trips first", g_sq_tail - g_sq_head);
        smooth_drain();
        g_sq_layer = NULL;
    }
}
static __declspec(naked) void smooth_dtor_stub(void) {
    __asm {
        pushad
        push ecx
        call smooth_on_dtor
        add esp, 4
        popad
        mov eax, dword ptr [g_ldt_imm]
        call dword ptr [g_ldt_ehp]
        jmp dword ptr [g_ldt_cont]
    }
}
/* Measured: at exit the traffic layer object is never deleted (its destructor hook never fired in 5 closes) but
   its marker grid is (tr_dtor runs every time), so the grid's destructor is the teardown signal. */
static void smooth_on_grid_dtor(void) {
    if (!g_smooth || !g_sq_layer) return;
    logf("TRAFFIC_SMOOTH> traffic grids being destroyed (caller 0x%08lX): draining %ld queued trips first",
         (DWORD)_ReturnAddress(), g_sq_tail - g_sq_head);
    smooth_drain();
    g_sq_layer = NULL;
}
static int smooth_init(DWORD st) {
    static const BYTE want[] = {0x56, 0x8b, 0xf1, 0x8b, 0x46, 0x0c, 0x85, 0xc0};
    BYTE *r = (BYTE *)st + 0x5237;
    g_sq = (TJOB *)VirtualAlloc(NULL, SQ_CAP * sizeof(TJOB), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    g_sdone = (DWORD *)VirtualAlloc(NULL, SQ_CAP * sizeof(DWORD), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    (void)want;   /* Release 0x10005237 is already replaced by patch_trafficmt's atomic version, which drains */
    if (!g_sq || !g_sdone) {
        logf("TRAFFIC_SMOOTH> no memory - synchronous batches instead");
        return 0;
    }
    InitializeCriticalSection(&g_sqcs); InitializeCriticalSection(&g_sdcs); InitializeCriticalSection(&g_acccs);
    g_sq_evt = CreateEventA(NULL, FALSE, FALSE, NULL);
    (void)r;                                              /* Release is hooked by patch_trafficmt (atomic refcount) */
    {   BYTE *dt = (BYTE *)st + 0x154e;
        if (dt[0] == 0xb8 && *(DWORD *)(dt + 1) == st + 0x183a1 && dt[5] == 0xe8) {
            g_ldt_imm = *(DWORD *)(dt + 1);
            g_ldt_ehp = (DWORD)(dt + 10) + *(DWORD *)(dt + 6);
            g_ldt_cont = (DWORD)(dt + 10);
            jmp_to(dt, (void *)smooth_dtor_stub);
        } else {
            logf("TRAFFIC_SMOOTH> layer destructor differs from shipped - background queue off");
            return 0;
        }
    }
    logf("TRAFFIC_SMOOTH> monthly trips drain in the background (queue %d, chunks of %d)", SQ_CAP, SQ_CHUNK);
    return 1;
}

/* Double buffer: g_mtq fills on the sim thread while g_mtq_fly (the previous batch) routes on the workers. */
static TJOB  *g_mtq_fly;
static LONG   g_fly_n;
static int    g_fly_active, g_mt_async = 0;
static double g_fly_t0, g_mt_wait_ms;
static DWORD WINAPI mt_worker(LPVOID p) {
    int me = (int)(INT_PTR)p;
    if (g_mt_pool[me]) TlsSetValue(g_tls_pool_fwd(), g_mt_pool[me]);
    if (g_tls_worker_fwd() != TLS_OUT_OF_INDEXES) TlsSetValue(g_tls_worker_fwd(), (void *)1);
    if (g_smooth) {                            /* background drain */
        for (;;) {
            smooth_work(me);
            WaitForSingleObject(g_sq_evt, 2);
        }
    }
    for (;;) {
        LONG i;
        WaitForSingleObject(g_mt_go[me], INFINITE);
        while ((i = InterlockedIncrement(&g_mtq_next) - 1) < g_fly_n) mt_run_job(g_mt_shadow[me], &g_mtq_fly[i]);
        if (InterlockedDecrement(&g_mt_left) == 0) SetEvent(g_mt_done);
    }
}
static void mt_ensure_workers(BYTE *layer) {
    int k;
    if (g_mt_threads) return;
    g_mt_done = CreateEventA(NULL, FALSE, FALSE, NULL);
    g_mtq_fly = (TJOB *)VirtualAlloc(NULL, (g_mt_batch + 16) * sizeof(TJOB), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    for (k = 0; g_mtq_fly && k < g_mt && k < MT_MAXW; k++) {
        g_mt_shadow[k] = mt_make_shadow(layer);
        if (!g_mt_shadow[k]) break;
        g_mt_go[k] = CreateEventA(NULL, FALSE, FALSE, NULL);
        if (g_tls_pool_fwd() != TLS_OUT_OF_INDEXES)
            g_mt_pool[k] = HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, 17 * sizeof(void *));
        {   DWORD tid = 0;
            HANDLE th = CreateThread(NULL, 1024 * 1024, mt_worker, (LPVOID)(INT_PTR)k, 0, &tid);
            prof_add_thread(th, tid);
        }
        g_mt_threads++;
    }
    logf("TRAFFIC_MT> %d worker threads, %s", g_mt_threads, g_smooth ? "background queue (TRAFFIC_SMOOTH)" :
         g_mt_async ? "asynchronous batches" : "synchronous batches");
}
/* Wait for the batch in flight, merge its counters, drop its references. g_mtcs held. */
static void mt_finish_locked(void) {
    BYTE *layer = mt_layer();
    LONG i;
    int k;
    double t0 = now_ms();
    if (!g_fly_active) return;
    while (WaitForSingleObject(g_mt_done, 20000) == WAIT_TIMEOUT)
        logf("TRAFFIC_MT> batch of %ld still running after 20 s (left %ld)", g_fly_n, g_mt_left);
    g_mt_wait_ms += now_ms() - t0;
    for (k = 0; k < g_mt_threads && layer; k++) {
        BYTE *s = g_mt_shadow[k];
        *(DWORD *)(layer + 0xb0) += *(DWORD *)(s + 0xb0);
        *(DWORD *)(layer + 0xb4) += *(DWORD *)(s + 0xb4);
        *(float *)(layer + 0x100) += *(float *)(s + 0x100);
    }
    for (i = 0; i < g_fly_n; i++) {
        DWORD o = g_mtq_fly[i].occ;
        ((THIS0F)(*(DWORD **)o)[2])(o, NULL);
    }
    g_mt_batches++;
    g_mt_jobs += g_fly_n;
    g_mt_ms += now_ms() - g_fly_t0;
    g_fly_n = 0;
    g_fly_active = 0;
}
/* Hand the filled queue to the workers. sync = also wait for it. g_mtcs held. */
static void mt_flush_locked(int sync) {
    BYTE *layer = mt_layer();
    TJOB *t;
    LONG i;
    int k;
    if (!layer) return;
    if (!g_mtq_n) { if (sync) mt_finish_locked(); return; }
    mt_ensure_workers(layer);
    if (!g_mt_threads) {                         /* no workers: route serially, here */
        for (i = 0; i < g_mtq_n; i++) mt_run_job(layer, &g_mtq[i]);
        for (i = 0; i < g_mtq_n; i++) { DWORD o = g_mtq[i].occ; ((THIS0F)(*(DWORD **)o)[2])(o, NULL); }
        g_mtq_n = 0;
        return;
    }
    mt_finish_locked();                          /* one batch in flight at a time */
    for (k = 0; k < g_mt_threads; k++)            /* RELOAD: a shadow that cannot take this layer: route here */
        if (!mt_refresh_shadow(g_mt_shadow[k], layer)) {
            for (i = 0; i < g_mtq_n; i++) mt_run_job(layer, &g_mtq[i]);
            for (i = 0; i < g_mtq_n; i++) { DWORD o = g_mtq[i].occ; ((THIS0F)(*(DWORD **)o)[2])(o, NULL); }
            g_mtq_n = 0;
            return;
        }
    t = g_mtq_fly; g_mtq_fly = g_mtq; g_mtq = t;
    g_fly_n = g_mtq_n;
    g_mtq_n = 0;
    g_mtq_next = 0;
    g_mt_left = g_mt_threads;
    g_fly_active = 1;
    g_fly_t0 = now_ms();
    if (sync || !g_mt_async) {               /* synchronous: hold the occupant-manager locks for the batch */
        if (g_geomheld) geom_hold_fwd(layer);
        for (k = 0; k < g_mt_threads; k++) SetEvent(g_mt_go[k]);
        mt_finish_locked();
        if (g_geomheld) geom_release_fwd();
    } else {
        for (k = 0; k < g_mt_threads; k++) SetEvent(g_mt_go[k]);
    }
}
/* Smooth mode: callers that want a trip result now (FUN_1000706a, ~17/s on Europolis 1024 - zone development; other
   callers of FUN_10006fe3, e.g. SIMECO+0x423c) route at once on the sim thread, on the real layer and its own marker
   grid, alongside the workers (shared writes are atomic or lock-free). They see congestion without the still-queued
   trips - the same lag the queued trips have. Draining every backlog for them cost 8,871 waits in 10 minutes. Only the
   monthly stats pass (mt_flush_stats) and the layer's last Release drain. */
static void __cdecl mt_flush(void) {
    if (g_mt && g_smooth) {                    /* no wait; but give finished trips' references back promptly */
        if (g_sq && g_sd_head != g_sd_tail) {
            EnterCriticalSection(&g_mtcs);
            smooth_settle(g_sq_layer);
            LeaveCriticalSection(&g_mtcs);
        }
        return;
    }
    if (!g_mt || (!g_mtq_n && !g_fly_active)) return;
    EnterCriticalSection(&g_mtcs);
    mt_flush_locked(1);
    LeaveCriticalSection(&g_mtcs);
}

/* FUN_10006fe3 replacement (thiscall layer, 7 args, ret 0x1c) */
static DWORD __fastcall mt_trip(BYTE *layer, void *edx, DWORD occ, DWORD kind, DWORD len, DWORD flag,
                                DWORD p5, DWORD p6, DWORD p7) {
    DWORD ret = (DWORD)_ReturnAddress();
    if (g_mt && layer == mt_layer() && !layer[0x11] && ret >= g_mt_st + 0x97b9 && ret < g_mt_st + 0x99f1 && occ) {
        TJOB *j;
        EnterCriticalSection(&g_mtcs);
        if (g_smooth) {
            mt_ensure_workers(layer);
            if (g_mt_threads) {
                smooth_enqueue(layer, occ, kind, len, flag, p5, p6, p7);
                LeaveCriticalSection(&g_mtcs);
                return 1;
            }
        }
        if (!g_mtq_n) g_mtq_t0 = now_ms();
        j = &g_mtq[g_mtq_n++];
        j->occ = occ; j->kind = kind; j->len = len; j->flag = flag; j->p5 = p5; j->p6 = p6; j->p7 = p7;
        ((THIS0F)(*(DWORD **)occ)[1])(occ, NULL);          /* AddRef: held until the trip has run */
        if (g_mtq_n >= g_mt_batch || now_ms() - g_mtq_t0 > 500.0) mt_flush_locked(0);
        LeaveCriticalSection(&g_mtcs);
        return 1;
    }
    if (g_smooth && (g_sq_tail != g_sq_head || g_sq_inflight)) drain_note(ret);
    mt_flush();
    return ((TRIP_FN)g_mt_tramp_6fe3)(layer, edx, occ, kind, len, flag, p5, p6, p7);
}

/* entry stubs: flush first, then the original */
static DWORD g_mt_706a_cont, g_mt_9242_call, g_mt_9242_cont;
static void __cdecl note_706a(void) { if (g_smooth && (g_sq_tail != g_sq_head || g_sq_inflight)) drain_note(0x706a); }
static void __cdecl note_9242(void) { if (g_smooth && (g_sq_tail != g_sq_head || g_sq_inflight)) drain_note(0x9242); }
static void __cdecl mt_flush_stats(void) {
    if (g_mt && g_smooth) {
        EnterCriticalSection(&g_mtcs);
        smooth_drain();
        LeaveCriticalSection(&g_mtcs);
        return;
    }
    mt_flush();
}
static __declspec(naked) void mt_706a_stub(void) {
    __asm {
        pushad
        call note_706a
        call mt_flush
        popad
        push ebp
        mov ebp, esp
        sub esp, 0x20
        jmp dword ptr [g_mt_706a_cont]
    }
}
static __declspec(naked) void mt_9242_stub(void) {
    __asm {
        pushad
        call note_9242
        call mt_flush_stats
        popad
        call dword ptr [g_mt_9242_call]
        jmp dword ptr [g_mt_9242_cont]
    }
}

static BYTE *make_tramp(BYTE *src, int n) {
    BYTE *t = (BYTE *)VirtualAlloc(NULL, 32, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!t) return NULL;
    memcpy(t, src, n);
    t[n] = 0xE9; *(DWORD *)(t + n + 1) = (DWORD)(src + n) - (DWORD)(t + n + 5);
    return t;
}
static void jmp_to(BYTE *at, void *to) {
    DWORD old;
    VirtualProtect(at, 5, PAGE_EXECUTE_READWRITE, &old);
    at[0] = 0xE9; *(DWORD *)(at + 1) = (DWORD)to - (DWORD)(at + 5);
    FlushInstructionCache(GetCurrentProcess(), at, 5);
}
static void patch_trafficmt(DWORD st) {
    static const BYTE w6fe3[] = {0x55, 0x8b, 0xec, 0x83, 0xec, 0x38};
    static const BYTE w706a[] = {0x55, 0x8b, 0xec, 0x83, 0xec, 0x20};
    static const BYTE w6edd[] = {0x55, 0x8b, 0xec, 0xf6, 0x45, 0x14, 0x35};
    static const BYTE w6a72[] = {0x55, 0x8b, 0xec, 0x83, 0xec, 0x0c};
    BYTE *a = (BYTE *)st + 0x6fe3, *b = (BYTE *)st + 0x706a, *c = (BYTE *)st + 0x6edd, *d = (BYTE *)st + 0x6a72,
         *e = (BYTE *)st + 0x9242;
    if (memcmp(a, w6fe3, 6) || memcmp(b, w706a, 6) || memcmp(c, w6edd, 7) || memcmp(d, w6a72, 6) || e[0] != 0xe8 ||
        (DWORD)(e + 5) + *(DWORD *)(e + 1) != st + 0x9776) {
        logf("TRAFFIC_MT> SimTransit differs from shipped - not patched");
        return;
    }
    g_mt_st = st;
    g_mtq = (TJOB *)VirtualAlloc(NULL, (g_mt_batch + 16) * sizeof(TJOB), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    g_mt_tramp_6fe3 = make_tramp(a, 6);
    if (!g_mtq || !g_mt_tramp_6fe3) { logf("TRAFFIC_MT> no memory - not patched"); return; }
    InitializeCriticalSection(&g_mtcs);
    g_mt_706a_cont = st + 0x706a + 6;
    g_mt_9242_call = st + 0x9776; g_mt_9242_cont = st + 0x9247;
    jmp_to(c, (void *)mt_congestion);
    jmp_to(d, (void *)mt_result);
    jmp_to(b, (void *)mt_706a_stub);
    jmp_to(e, (void *)mt_9242_stub);
    jmp_to(a, (void *)mt_trip);
    logf("TRAFFIC_MT> monthly building trips queued and routed on %d workers (batch %d)", g_mt, g_mt_batch);

    if (g_smooth && !g_trclear) { logf("TRAFFIC_SMOOTH> needs transit_clear (its grid destructor is the teardown signal) - off"); g_smooth = 0; }
    if (g_smooth && !smooth_init(st)) g_smooth = 0;
}

/* ---------------------------------------------------------------- MT_LOCKS (2026-10-09, with TRAFFIC_MT)
   The 8 traffic workers spent most of their routing time waiting on two global locks (profile of the workers):
   1. SimTransit's STL node allocator FUN_10009f58 / FUN_1000a08f (SGI __default_alloc_template: 16 free lists at
      DAT_1001fdbc[(n+7)>>3], spinlock DAT_1001fe00 via FUN_10009fcf that backs off with Sleep() up to 128 ms).
      Replaced: worker threads use their OWN free lists (carved from their own chunks); every other thread runs the
      original logic (same lock, same lists, same refill FUN_1000a51c). A block freed on another thread than the
      one that allocated it just joins that thread's list (free-list blocks are never returned to the OS).
   2. SIMNTWRK network-piece AddRef FUN_10023886 / Release FUN_100238cc: refcount = low 16 bits of piece+0xc
      under one global CRITICAL_SECTION (0x100325f8, used by nothing else), plus a global live-reference counter
      (stats object FUN_100010a6() +0x20). Replaced by CAS loops with the same arithmetic; release to 0 still
      calls vt+0x20 then vt+0x144(1) (delete), outside any lock as before. */
typedef struct { void *fl[17]; } TPOOL;
static DWORD g_tls_pool = TLS_OUT_OF_INDEXES;
static DWORD g_ntw;                                  /* SIMNTWRK base */
static volatile LONG g_pool_chunks;
typedef void *(__cdecl *MALLOC_FN)(size_t);
typedef void (__cdecl *FREE_FN)(void *);
typedef void *(__cdecl *REFILL_FN)(DWORD);
typedef void (__fastcall *SPIN_FN)(volatile LONG *);
typedef void (__cdecl *OOM_FN)(DWORD);

static void *pool_tls_alloc(TPOOL *pl, DWORD n) {
    DWORD idx = (n + 7) >> 3, sz, k;
    BYTE *p, *chunk;
    if (!idx) idx = 1;
    p = (BYTE *)pl->fl[idx];
    if (p) { pl->fl[idx] = *(void **)p; return p; }
    sz = idx * 8;
    chunk = (BYTE *)HeapAlloc(GetProcessHeap(), 0, sz * 64);
    if (!chunk) return NULL;
    InterlockedIncrement(&g_pool_chunks);
    for (k = 1; k < 63; k++) *(void **)(chunk + k * sz) = chunk + (k + 1) * sz;
    *(void **)(chunk + 63 * sz) = NULL;
    pl->fl[idx] = chunk + sz;
    return chunk;
}
/* FUN_10009f58 replacement: cdecl allocate(n) */
static void *__cdecl pool_alloc(DWORD n) {
    TPOOL *pl;
    volatile LONG *lock;
    void **head, *p;
    if (n > 0x80) {
        p = (*(MALLOC_FN *)(g_mt_st + 0x1a0b8))(n);
        if (!p) ((OOM_FN)(g_mt_st + 0xaa92))(n);
        return p;
    }
    pl = g_tls_pool != TLS_OUT_OF_INDEXES ? (TPOOL *)TlsGetValue(g_tls_pool) : NULL;
    if (pl) return pool_tls_alloc(pl, n);
    lock = (volatile LONG *)(g_mt_st + 0x1fe00);
    ((SPIN_FN)(g_mt_st + 0x9fcf))(lock);
    head = (void **)(g_mt_st + 0x1fdbc) + ((n + 7) >> 3);
    p = *head;
    if (!p) p = ((REFILL_FN)(g_mt_st + 0xa51c))((n + 7) & ~7u);
    else *head = *(void **)p;
    *lock = 0;
    return p;
}
/* FUN_1000a08f replacement: cdecl deallocate(p, n) */
static void __cdecl pool_free(void *p, DWORD n) {
    TPOOL *pl;
    volatile LONG *lock;
    void **head;
    if (n > 0x80) { (*(FREE_FN *)(g_mt_st + 0x1a0bc))(p); return; }
    pl = g_tls_pool != TLS_OUT_OF_INDEXES ? (TPOOL *)TlsGetValue(g_tls_pool) : NULL;
    if (pl) {
        DWORD idx = (n + 7) >> 3;
        if (!idx) idx = 1;
        *(void **)p = pl->fl[idx]; pl->fl[idx] = p;
        return;
    }
    lock = (volatile LONG *)(g_mt_st + 0x1fe00);
    ((SPIN_FN)(g_mt_st + 0x9fcf))(lock);
    head = (void **)(g_mt_st + 0x1fdbc) + ((n + 7) >> 3);
    *(void **)p = *head; *head = p;
    *lock = 0;
}

typedef BYTE *(__cdecl *STATS_FN)(void);
typedef void (__fastcall *VOID0)(void *self, void *edx);
typedef void (__fastcall *VOID1)(void *self, void *edx, DWORD a);
/* FUN_10023886 replacement: fastcall AddRef(piece) -> new count */
static BYTE *g_ntw_stats;                 /* FUN_100010a6's static object, created once on first use */
static DWORD __fastcall ntw_addref(BYTE *piece) {
    BYTE *st = g_ntw_stats ? g_ntw_stats : (g_ntw_stats = ((STATS_FN)(g_ntw + 0x10a6))());
    volatile LONG *rc = (volatile LONG *)(piece + 0xc);
    LONG o, n;
    InterlockedIncrement((volatile LONG *)(st + 0x20));
    do { o = *rc; n = (o & 0xffff0000) | ((o + 1) & 0xffff); } while (InterlockedCompareExchange(rc, n, o) != o);
    return (DWORD)n & 0xffff;
}
/* FUN_100238cc replacement: fastcall Release(piece) -> remaining count (0 = destroyed) */
static DWORD __fastcall ntw_release(BYTE *piece) {
    volatile LONG *rc = (volatile LONG *)(piece + 0xc);
    LONG o, n;
    for (;;) {
        o = *rc;
        if (!(o & 0xffff)) break;                              /* already 0: the original destroys too */
        n = (o & 0xffff0000) | ((o - 1) & 0xffff);
        if (InterlockedCompareExchange(rc, n, o) == o) {
            volatile LONG *cnt = (volatile LONG *)((g_ntw_stats ? g_ntw_stats : (g_ntw_stats = ((STATS_FN)(g_ntw + 0x10a6))())) + 0x20);
            LONG c;
            do { c = *cnt; } while (c > 0 && InterlockedCompareExchange(cnt, c - 1, c) != c);
            if (n & 0xffff) return (DWORD)n & 0xffff;
            break;
        }
    }
    ((VOID0)(*(DWORD **)piece)[0x20 / 4])(piece, NULL);
    ((VOID1)(*(DWORD **)piece)[0x144 / 4])(piece, NULL, 1);
    return 0;
}

static DWORD g_tls_pool_fwd(void) { return g_tls_pool; }
static void patch_mtlocks(DWORD st) {
    static const BYTE w9f58[] = {0xb8, 0x10, 0x8a, 0x01, 0x10};      /* mov eax, 0x10018a10 (relocated below) */
    static const BYTE wa08f[] = {0x8b, 0x44, 0x24, 0x08, 0x3d, 0x80, 0x00, 0x00, 0x00};
    static const BYTE w3886[] = {0x56, 0x57, 0x8b, 0xf1, 0xe8};
    static const BYTE w38cc[] = {0x53, 0x56, 0x8b, 0xf1, 0xbb};
    BYTE *a = (BYTE *)st + 0x9f58, *b = (BYTE *)st + 0xa08f, *c, *d;
    int ms = 0;
    while (!(g_ntw = (DWORD)GetModuleHandleA("SIMNTWRK.DLL")) && ms++ < 60000) Sleep(1);
    if (a[0] != 0xb8 || *(DWORD *)(a + 1) != st + 0x18a10 || memcmp(b, wa08f, sizeof(wa08f))) {
        logf("MT_LOCKS> SimTransit allocator differs from shipped - not patched");
    } else {
        g_tls_pool = TlsAlloc();
        jmp_to(a, (void *)pool_alloc);
        jmp_to(b, (void *)pool_free);
        logf("MT_LOCKS> SimTransit node allocator: per-worker free lists (TLS %lu)", g_tls_pool);
    }
    (void)w9f58;
    if (!g_ntw) { logf("MT_LOCKS> SIMNTWRK.DLL not loaded - refcount not patched"); return; }
    c = (BYTE *)g_ntw + 0x23886; d = (BYTE *)g_ntw + 0x238cc;
    if (memcmp(c, w3886, sizeof(w3886)) || memcmp(d, w38cc, sizeof(w38cc)) || *(DWORD *)(d + 5) != g_ntw + 0x325f8) {
        logf("MT_LOCKS> SIMNTWRK refcount differs from shipped - not patched");
        return;
    }
    jmp_to(c, (void *)ntw_addref);
    jmp_to(d, (void *)ntw_release);
    logf("MT_LOCKS> SIMNTWRK network-piece AddRef/Release lock-free");
}

/* ---------------------------------------------------------------- GEOM_HELD (2026-10-09, with TRAFFIC_MT)
   Every routing step reads the occupant grids through SIMGEOM GetOccupantAtCell FUN_1000ec60 (thiscall mgr, x, z,
   occupant** out, ret 0xc): bounds check vt+0x6c, lock *(mgr+0x90) (vt+4 = FUN_1001adf5 EnterCriticalSection),
   read grid *(mgr+0x98) (u32 per cell; flag bit 2 in the byte grid *(mgr+0x9c) means "points at the anchor cell
   (v & 0xffff, v >> 16)"), unlock (vt+8), AddRef the occupant (vt+4) [CONFIRMED by disassembly @ 0x1000ec60].
   With 8 workers that lock was the largest remaining wait. For a synchronous batch the SIM THREAD now takes the
   locks of the traffic layer's two managers (layer+0x94 / +0x98) once, before releasing the workers, and drops
   them after the batch: nobody else (UI edits included) can change those grids meanwhile, which is what the
   per-call lock guaranteed, and the lock order is the original one (the sim thread took the same lock while
   routing). Worker threads then read through a copy of the function without the lock calls; every other thread,
   and any manager whose lock is not held for the batch, takes the original path. */
typedef DWORD (__fastcall *GOAC_FN)(BYTE *mgr, void *edx, DWORD x, DWORD z, DWORD *out);
typedef BYTE (__fastcall *INB_FN)(BYTE *mgr, void *edx, DWORD x, DWORD z);
static BYTE  *g_goac_tramp;
static DWORD  g_tls_worker = TLS_OUT_OF_INDEXES;
static BYTE  *g_geom_held[2];
static volatile LONG g_geom_on;
static volatile LONG g_geom_fast;

static DWORD __fastcall geom_get_at_cell(BYTE *mgr, void *edx, DWORD x, DWORD z, DWORD *out) {
    BYTE *lk = *(BYTE **)(mgr + 0x90), fl;
    DWORD v;
    if (!g_geom_on || g_tls_worker == TLS_OUT_OF_INDEXES || !TlsGetValue(g_tls_worker) ||
        (lk != g_geom_held[0] && lk != g_geom_held[1]))
        return ((GOAC_FN)g_goac_tramp)(mgr, edx, x, z, out);
    if (!((INB_FN)(*(DWORD **)mgr)[0x6c / 4])(mgr, NULL, x, z)) { *out = 0; return 0; }
    InterlockedIncrement(&g_geom_fast);
    v = *(DWORD *)(*(BYTE **)(*(BYTE **)(*(BYTE **)(mgr + 0x98) + 0xc) + x * 4) + z * 4);
    fl = *(BYTE *)(*(BYTE **)(*(BYTE **)(*(BYTE **)(mgr + 0x9c) + 0xc) + x * 4) + z);
    if (!out) return fl & 1;
    if (!(fl & 1)) { *out = 0; return 0; }
    if (fl & 2)
        v = *(DWORD *)(*(BYTE **)(*(BYTE **)(*(BYTE **)(mgr + 0x98) + 0xc) + (v & 0xffff) * 4) + (v >> 16) * 4);
    *out = v;
    if (!v) return 0;
    ((VOID0)(*(DWORD **)v)[1])((void *)v, NULL);             /* AddRef, as the original does after unlocking */
    return 1;
}

/* sim thread, before / after a synchronous batch */
static void geom_hold(BYTE *layer) {
    int k;
    if (!g_goac_tramp) return;
    for (k = 0; k < 2; k++) {
        BYTE *mgr = *(BYTE **)(layer + 0x94 + 4 * k), *lk;
        g_geom_held[k] = NULL;
        if (!mgr) continue;
        lk = *(BYTE **)(mgr + 0x90);
        if (!lk || (k == 1 && lk == g_geom_held[0])) continue;
        ((VOID0)(*(DWORD **)lk)[1])(lk, NULL);               /* lock vt+4 */
        g_geom_held[k] = lk;
    }
    g_geom_on = 1;
}
static void geom_release(void) {
    int k;
    if (!g_geom_on) return;
    g_geom_on = 0;
    for (k = 1; k >= 0; k--)
        if (g_geom_held[k]) { ((VOID0)(*(DWORD **)g_geom_held[k])[2])(g_geom_held[k], NULL); g_geom_held[k] = NULL; }
}

static void patch_geomheld(void) {
    static const BYTE want[] = {0x83, 0xec, 0x08, 0x53, 0x8b, 0x5c, 0x24, 0x10, 0x56, 0x57};
    DWORD gm = 0;
    BYTE *f;
    int ms = 0;
    while (!(gm = (DWORD)GetModuleHandleA("SIMGEOM.DLL")) && ms++ < 60000) Sleep(1);
    if (!gm) { logf("GEOM_HELD> SIMGEOM.DLL not loaded"); return; }
    f = (BYTE *)gm + 0xec60;
    if (memcmp(f, want, sizeof(want))) { logf("GEOM_HELD> SIMGEOM+0xec60 differs from shipped - not patched"); return; }
    g_goac_tramp = make_tramp(f, 8);                          /* sub esp,8 / push ebx / mov ebx,[esp+0x10] */
    if (!g_goac_tramp) return;
    jmp_to(f, (void *)geom_get_at_cell);
    logf("GEOM_HELD> GetOccupantAtCell: traffic workers read under the batch's held manager locks");
}

static DWORD g_tls_worker_fwd(void) { return g_tls_worker; }
static void geom_hold_fwd(BYTE *l) { geom_hold(l); }
static void geom_release_fwd(void) { geom_release(); }
/* ---------------------------------------------------------------- FAST_CEIL (2026-10-09, SimTransit only)
   Every routing step (select_next_cell 0x1000755e, its cost tail) ends with `ftol(ceil((double)cost))`. msvcrt's ceil
   switches the x87 rounding mode with fldcw and back (msvcrt+0xa9024, the same serialising helper FAST_FTOL took out
   of _ftol), which was the largest single item left in the workers' routing profile. SimTransit's import of ceil
   (IAT 0x1001a0ac) now points at a version that never touches the control word: truncate with FISTTP (SSE3), add 1
   when the truncated value is below the input. |x| >= 2^31 and NaN go to the real ceil. Every SimTransit call site
   (0x1000755e, 0x10008e63, 0x10008ef5) converts the result to an integer right away, so the one difference from the
   real function, ceil(-0.5) giving +0.0 instead of -0.0, cannot show. */
static DWORD g_real_ceil;
static const double g_two31 = 2147483648.0;
static __declspec(naked) void fast_ceil(void) {
    __asm {
        fld qword ptr [esp + 4]            ; x
        fld st(0)
        fabs
        fcomp qword ptr [g_two31]
        fnstsw ax
        sahf
        jp big                              ; NaN
        jae big                             ; |x| >= 2^31
        sub esp, 8
        fld st(0)
        fisttp qword ptr [esp]              ; truncate toward zero, control word untouched
        fild qword ptr [esp]                ; t, x
        add esp, 8
        fcom st(1)
        fnstsw ax
        sahf
        jae done                            ; t >= x: t is the ceiling
        fld1
        faddp st(1), st
    done:
        fstp st(1)                          ; drop x, keep t
        ret
    big:
        fstp st(0)
        jmp dword ptr [g_real_ceil]
    }
}

static void patch_fastceil(DWORD st) {
    DWORD *iat = (DWORD *)(st + 0x1a0ac), old;
    HMODULE crt = GetModuleHandleA("msvcrt.dll");
    DWORD want = crt ? (DWORD)GetProcAddress(crt, "ceil") : 0;
    if (!IsProcessorFeaturePresent(13 /* SSE3 */)) { logf("FAST_CEIL> no SSE3 - not patched"); return; }
    if (!want || *iat != want) { logf("FAST_CEIL> SimTransit IAT slot 0x1a0ac is not msvcrt!ceil - not patched"); return; }
    g_real_ceil = want;
    if (!VirtualProtect(iat, 4, PAGE_READWRITE, &old)) return;
    *iat = (DWORD)fast_ceil;
    logf("FAST_CEIL> SimTransit ceil -> FISTTP version (no fldcw)");
}

/* ---------------------------------------------------------------- LAYER_REFCOUNT (2026-10-10)
   The engine's GZCOM "layer"-style objects (layers, agents, advisors: the ones that receive message fan-out from the
   sim thread while the game thread also holds them) count references with plain inc/dec plus a per-module stats
   counter. Measured crashes from it: the traffic layer (SIMCITY teardown index 19), SIMADV Release FUN_1002ba93
   (heap corruption at exit: its deleting destructor freed an object twice). These bodies come from four compiler
   templates, matched here BYTE FOR BYTE (only the field offset N, the stats-getter call and the destroy slot S vary;
   the branch distances must match the slot encoding) in every game DLL, and each match is redirected through a
   16-byte stub (mov edx, params / jmp) to one atomic implementation with the same results:
     AddRef  56 8b f1 ff 46 N e8 <stats> 8b 10 8b c8 ff 52 04 8b 46 N 5e c3             count += 1, stats vt+4
     F1      56 8b f1 ff 4e N e8 <stats> 8b 10 8b c8 ff 52 28 8b 46 N 85 c0 TAIL           count -= 1 always
     F2      56 8b f1 83 7e N 00 76 0f e8 <stats> 8b 10 8b c8 ff 52 28 ff 4e N 8b 46 N 85 c0 TAIL   if count: -1
     F3      56 8b f1 8b 46 N 85 c0 (74|76) 10 48 89 46 N e8 <stats> 8b 10 8b c8 ff 52 28 8b 46 N 85 c0 TAIL
     TAIL    75 J 85 f6 74 K 8b 06 6a 01 8b ce (ff 50 S | ff 90 S32) 33 c0 5e c3      count 0: vt+S(1), return 0
   (stats vt+0x28 runs when the count was decremented.) SimTransit is left to TRAFFIC_MT's own atomic version, which
   also drains the trip queue. layer_refcount=0 turns this off. */
typedef struct { int kind, off; DWORD stats, slot; } RCP;    /* kind 0 AddRef, 1 F1, 2 F2/F3 */
typedef BYTE *(__cdecl *RC_STATS)(void);
static volatile LONG g_rc_patched[4];
static BYTE *g_rc_stubs;
static int   g_rc_nstub;

static LONG __fastcall rc_addref(BYTE *self, RCP *p) {
    LONG n = InterlockedIncrement((volatile LONG *)(self + p->off));
    BYTE *st = ((RC_STATS)p->stats)();
    ((TVOID0)(*(DWORD **)st)[1])(st, NULL);
    return n;
}
static LONG __fastcall rc_release(BYTE *self, RCP *p) {
    volatile LONG *rc = (volatile LONG *)(self + p->off);
    LONG n;
    if (p->kind == 1) {
        BYTE *st;
        n = InterlockedDecrement(rc);
        st = ((RC_STATS)p->stats)();
        ((TVOID0)(*(DWORD **)st)[0x28 / 4])(st, NULL);
    } else {
        for (;;) {
            LONG o = *rc;
            if (!o) { n = 0; break; }
            if (InterlockedCompareExchange(rc, o - 1, o) == o) {
                BYTE *st = ((RC_STATS)p->stats)();
                ((TVOID0)(*(DWORD **)st)[0x28 / 4])(st, NULL);
                n = o - 1;
                break;
            }
        }
    }
    if (n) return n;
    ((VDEL1_FN)(*(DWORD **)self)[p->slot / 4])(self, NULL, 1);
    return 0;
}
/* TAIL at q: returns its length (and the slot), 0 if no match */
static int rc_tail(const BYTE *q, DWORD *slot) {
    static const BYTE mid[] = {0x85, 0xf6, 0x74};
    static const BYTE mid2[] = {0x8b, 0x06, 0x6a, 0x01, 0x8b, 0xce};
    if (q[0] != 0x75 || memcmp(q + 2, mid, 3) || memcmp(q + 6, mid2, 6)) return 0;
    if (q[12] == 0xff && q[13] == 0x50 && q[1] == 0x0f && q[5] == 0x09 &&
        q[15] == 0x33 && q[16] == 0xc0 && q[17] == 0x5e && q[18] == 0xc3) { *slot = q[14]; return 19; }
    if (q[12] == 0xff && q[13] == 0x90 && q[1] == 0x12 && q[5] == 0x0c &&
        q[18] == 0x33 && q[19] == 0xc0 && q[20] == 0x5e && q[21] == 0xc3) { *slot = *(DWORD *)(q + 14); return 22; }
    return 0;
}
static const BYTE RC_STATSCALL[] = {0x8b, 0x10, 0x8b, 0xc8, 0xff, 0x52};
/* match at p: fills params, returns 1 */
static int rc_match(const BYTE *p, RCP *r) {
    DWORD slot;
    if (p[0] != 0x56 || p[1] != 0x8b || p[2] != 0xf1) return 0;
    if (p[3] == 0xff && p[4] == 0x46 && p[6] == 0xe8 && !memcmp(p + 11, RC_STATSCALL, 6) && p[17] == 0x04 &&
        p[18] == 0x8b && p[19] == 0x46 && p[20] == p[5] && p[21] == 0x5e && p[22] == 0xc3) {
        r->kind = 0; r->off = p[5]; r->stats = (DWORD)(p + 11) + *(DWORD *)(p + 7); r->slot = 0; return 1;
    }
    if (p[3] == 0xff && p[4] == 0x4e && p[6] == 0xe8 && !memcmp(p + 11, RC_STATSCALL, 6) && p[17] == 0x28 &&
        p[18] == 0x8b && p[19] == 0x46 && p[20] == p[5] && p[21] == 0x85 && p[22] == 0xc0 && rc_tail(p + 23, &slot)) {
        r->kind = 1; r->off = p[5]; r->stats = (DWORD)(p + 11) + *(DWORD *)(p + 7); r->slot = slot; return 1;
    }
    if (p[3] == 0x83 && p[4] == 0x7e && p[6] == 0x00 && p[7] == 0x76 && p[8] == 0x0f && p[9] == 0xe8 &&
        !memcmp(p + 14, RC_STATSCALL, 6) && p[20] == 0x28 && p[21] == 0xff && p[22] == 0x4e && p[23] == p[5] &&
        p[24] == 0x8b && p[25] == 0x46 && p[26] == p[5] && p[27] == 0x85 && p[28] == 0xc0 && rc_tail(p + 29, &slot)) {
        r->kind = 2; r->off = p[5]; r->stats = (DWORD)(p + 14) + *(DWORD *)(p + 10); r->slot = slot; return 1;
    }
    if (p[3] == 0x8b && p[4] == 0x46 && p[6] == 0x85 && p[7] == 0xc0 && (p[8] == 0x74 || p[8] == 0x76) && p[9] == 0x10 &&
        p[10] == 0x48 && p[11] == 0x89 && p[12] == 0x46 && p[13] == p[5] && p[14] == 0xe8 &&
        !memcmp(p + 19, RC_STATSCALL, 6) && p[25] == 0x28 && p[26] == 0x8b && p[27] == 0x46 && p[28] == p[5] &&
        p[29] == 0x85 && p[30] == 0xc0 && rc_tail(p + 31, &slot)) {
        r->kind = 2; r->off = p[5]; r->stats = (DWORD)(p + 19) + *(DWORD *)(p + 15); r->slot = slot; return 1;
    }
    return 0;
}
static void rc_scan_module(DWORD base, const char *name) {
    DWORD e = *(DWORD *)(base + 0x3c), k, i;
    WORD ns = *(WORD *)(base + e + 6), opt = *(WORD *)(base + e + 0x14);
    DWORD sec = base + e + 0x18 + opt;
    int n[4] = {0, 0, 0, 0};
    for (k = 0; k < ns; k++) {
        DWORD sh = sec + k * 40, va = base + *(DWORD *)(sh + 0x0c), vs = *(DWORD *)(sh + 0x08);
        if (!(*(DWORD *)(sh + 0x24) & 0x20000000) || vs < 64) continue;
        for (i = 0; i + 40 < vs; i++) {
            BYTE *p = (BYTE *)va + i, *stub;
            RCP r, *pp;
            if (p[0] != 0x56 || !rc_match(p, &r)) continue;
            if (g_rc_nstub >= 4096) break;
            pp = (RCP *)(g_rc_stubs + 4096 * 16 + g_rc_nstub * sizeof(RCP));
            *pp = r;
            stub = g_rc_stubs + g_rc_nstub * 16;
            g_rc_nstub++;
            stub[0] = 0xBA; *(DWORD *)(stub + 1) = (DWORD)pp;                       /* mov edx, params */
            stub[5] = 0xE9; *(DWORD *)(stub + 6) = (DWORD)(r.kind ? (void *)rc_release : (void *)rc_addref) - (DWORD)(stub + 10);
            jmp_to(p, stub);
            n[r.kind ? (r.kind == 1 ? 1 : 2) : 0]++;
            InterlockedIncrement(&g_rc_patched[r.kind ? (r.kind == 1 ? 1 : 2) : 0]);
        }
    }
    if (n[0] || n[1] || n[2])
        logf("LAYER_REFCOUNT> %s: %d AddRef, %d Release (always-decrement), %d Release (if-nonzero) made atomic", name, n[0], n[1], n[2]);
}
/* every game DLL from the install's Apps folder, once each, as it loads (not our own mods, not SimTransit) */
static DWORD WINAPI rc_watcher(LPVOID p) {
    char apps[MAX_PATH], *sl;
    DWORD done[128];
    int nd = 0, t;
    (void)p;
    GetModuleFileNameA(NULL, apps, sizeof(apps));
    sl = strrchr(apps, '\\'); if (sl) sl[1] = 0;
    g_rc_stubs = (BYTE *)VirtualAlloc(NULL, 4096 * 16 + 4096 * sizeof(RCP), MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!g_rc_stubs) return 0;
    for (t = 0; t < 6000; t++) {                       /* ~5 minutes: every game DLL is loaded long before that */
        HANDLE s = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, GetCurrentProcessId());
        MODULEENTRY32 me;
        me.dwSize = sizeof(me);
        if (s != INVALID_HANDLE_VALUE && Module32First(s, &me)) do {
            DWORD b = (DWORD)me.modBaseAddr;
            HMODULE pin = NULL;
            int j, seen = 0;
            for (j = 0; j < nd; j++) if (done[j] == b) seen = 1;
            if (seen || nd >= 128) continue;
            if (_strnicmp(me.szExePath, apps, strlen(apps)) || !lstrcmpiA(me.szModule, "SimTransit.dll") ||
                !_strnicmp(me.szModule, "sc3", 3) || !lstrcmpiA(me.szModule, "SC3U.exe")) { done[nd++] = b; continue; }
            /* task onramp: a DLL the snapshot listed can be freed before we read it (startup crash, read of
               0x7800003C at rc_scan_module's first load, 3 of 23 launches on 2026-10-22). Hold a reference while
               scanning; a module already gone is skipped and not marked done, so a later load is still scanned. */
            if (!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS, (LPCSTR)b, &pin) || (DWORD)pin != b) {
                if (pin) FreeLibrary(pin);
                logf("LAYER_REFCOUNT> %s at 0x%08lX was freed after the module snapshot - skipped", me.szModule, b);
                continue;
            }
            done[nd++] = b;
            rc_scan_module(b, me.szModule);
            FreeLibrary(pin);
        } while (Module32Next(s, &me));
        if (s != INVALID_HANDLE_VALUE) CloseHandle(s);
        Sleep(50);
    }
    logf("LAYER_REFCOUNT> done: %ld AddRef, %ld + %ld Release patched in total", g_rc_patched[0], g_rc_patched[1], g_rc_patched[2]);
    return 0;
}

static void patch_tlrefcount(DWORD st) {
    if (!g_mt_st) g_mt_st = st;
    {   static const BYTE wadd[] = {0x56, 0x8b, 0xf1, 0xff, 0x46, 0x0c, 0xe8};
        static const BYTE wrel[] = {0x56, 0x8b, 0xf1, 0x8b, 0x46, 0x0c, 0x85, 0xc0};
        BYTE *ad = (BYTE *)st + 0x526c, *rl = (BYTE *)st + 0x5237;
        if (!memcmp(ad, wadd, 7) && !memcmp(rl, wrel, 8)) {
            jmp_to(ad, (void *)tl_addref);
            jmp_to(rl, (void *)smooth_layer_release);
            logf("REFCOUNT> traffic layer AddRef/Release atomic (0x1000526c, 0x10005237)");
        } else logf("REFCOUNT> traffic layer refcount differs from shipped - not patched");
    }
}
static DWORD WINAPI tr_watcher(LPVOID p) {
    DWORD st = 0;
    int ms = 0;
    (void)p;
    while (!(st = (DWORD)GetModuleHandleA("SimTransit.dll")) && ms++ < 300000) Sleep(1);
    if (!st) { logf("TRANSIT_CLEAR> SimTransit.dll never loaded"); return 0; }
    if (g_sprref) patch_tlrefcount(st);              /* traffic layer refcount: an original bug, also without traffic_mt */
    if (g_trclear) patch_trclear(st);
    if (g_fastceil) patch_fastceil(st);
    if (g_mt > 0) patch_trafficmt(st);
    if (g_mt > 0 && g_mtlocks) patch_mtlocks(st);
    if (g_mt > 0 && g_geomheld && !g_smooth) { g_tls_worker = TlsAlloc(); patch_geomheld(); }
    return 0;
}

/* ---------------------------------------------------------------- SPR_REFCOUNT (2026-10-10)
   Crash family seen after maximize on the 1024 city (SIMSPR+0x2D102 / +0x2D112, walking a freed sparse map in
   FUN_100222de) and at exit (+0x40B9F, a destructor run twice). Static read (scratchpad worker_sprmap.md): the owning
   objects - the per-data-view sprite overlays (vtable 0x10064390, three per city view at bridge+0x110/+0x114/+0x118)
   and the per-cell effect manager (vtable 0x10067264 at bridge+0x108) - count references with plain, non-atomic code:
   AddRef `inc [ecx+8]; mov eax,[ecx+8]; ret` (0x10021551, shared by five classes; 0x1003cf95 on +0xc) and Release
   `if count == 1: destructor + delete, return 0; else count -= 1` (0x1002209c; 0x1003cf9c on +0xc). Both objects get
   message fan-out from the SIM thread (GZServiceD MessageSend AddRefs each target under its lock and Releases it after
   dropping the lock, on the sending thread) while the GAME thread references them too, so a lost update leaves the
   count low and a later ordinary Release frees the object while it is still in use. The four bodies are replaced by
   atomic versions with the same results: no lock is added, so this cannot deadlock. spr_refcount=0 keeps the originals. */
typedef void (__fastcall *DTOR_FN)(BYTE *self, void *edx);
typedef void (__cdecl *DEL_FN)(void *);
static DWORD g_sr_base;
static volatile LONG g_sr_frees;

static LONG __fastcall sr_addref8(BYTE *self) { return InterlockedIncrement((volatile LONG *)(self + 8)); }
static LONG __fastcall sr_addrefc(BYTE *self) { return InterlockedIncrement((volatile LONG *)(self + 0xc)); }
static LONG sr_release(BYTE *self, int off, DWORD dtor) {
    volatile LONG *rc = (volatile LONG *)(self + off);
    for (;;) {
        LONG o = *rc;
        if (o == 1) {                            /* the original destroys at 1 without decrementing first */
            if (InterlockedCompareExchange(rc, 0, 1) != 1) continue;
            ((DTOR_FN)(g_sr_base + dtor))(self, NULL);
            ((DEL_FN)(g_sr_base + 0x5ca7a))(self);
            InterlockedIncrement(&g_sr_frees);
            return 0;
        }
        if (InterlockedCompareExchange(rc, o - 1, o) == o) return o - 1;
    }
}
static LONG __fastcall sr_release8(BYTE *self) { return sr_release(self, 8, 0x220c1); }
/* the other four classes whose AddRef is 0x10021551 (vtables 0x10064194, 0x10065f24, 0x10066618, 0x10066a24) */
static LONG __fastcall sr_rel_21558(BYTE *self) { return sr_release(self, 8, 0x2157d); }
static LONG __fastcall sr_rel_35433(BYTE *self) { return sr_release(self, 8, 0x35458); }
typedef void (__fastcall *VDEL_FN)(BYTE *self, void *edx, DWORD flags);
/* release through a virtual deleting destructor: `le1` = destroy at count <= 1 (0x1002e929, vt+0x20), else at == 1
   (0x10037c93, vt+0x28); otherwise decrement */
static LONG sr_release_v(BYTE *self, int slot, int le1) {
    volatile LONG *rc = (volatile LONG *)(self + 8);
    for (;;) {
        LONG o = *rc;
        if (le1 ? o <= 1 : o == 1) {
            if (InterlockedCompareExchange(rc, 0, o) != o) continue;
            ((VDEL_FN)(*(DWORD **)self)[slot / 4])(self, NULL, 1);
            InterlockedIncrement(&g_sr_frees);
            return 0;
        }
        if (InterlockedCompareExchange(rc, o - 1, o) == o) return o - 1;
    }
}
static LONG __fastcall sr_rel_2e929(BYTE *self) { return sr_release_v(self, 0x20, 1); }
static LONG __fastcall sr_rel_37c93(BYTE *self) { return sr_release_v(self, 0x28, 0); }
static LONG __fastcall sr_releasec(BYTE *self) { return sr_release(self, 0xc, 0x3cfce); }

static void patch_sprrefcount(DWORD spr) {
    static const BYTE wadd8[] = {0xff, 0x41, 0x08, 0x8b, 0x41, 0x08, 0xc3};
    static const BYTE waddc[] = {0xff, 0x41, 0x0c, 0x8b, 0x41, 0x0c, 0xc3};
    static const BYTE wrel8[] = {0x56, 0x8b, 0xf1, 0x8b, 0x46, 0x08, 0x83, 0xf8, 0x01, 0x75, 0x14};
    static const BYTE wrelc[] = {0x56, 0x8b, 0xf1, 0x8b, 0x46, 0x0c, 0x83, 0xf8, 0x01, 0x75, 0x14};
    BYTE *a = (BYTE *)spr + 0x21551, *b = (BYTE *)spr + 0x2209c, *c = (BYTE *)spr + 0x3cf95, *d = (BYTE *)spr + 0x3cf9c;
    if (memcmp(a, wadd8, 7) || memcmp(b, wrel8, 11) || memcmp(c, waddc, 7) || memcmp(d, wrelc, 11) ||
        (DWORD)(b + 0x14) + *(DWORD *)(b + 0x10) != spr + 0x220c1 || (DWORD)(d + 0x14) + *(DWORD *)(d + 0x10) != spr + 0x3cfce) {
        logf("SPR_REFCOUNT> SIMSPR refcount functions differ from shipped - not patched");
        return;
    }
    g_sr_base = spr;
    {   static const BYTE w2e929[] = {0x8b, 0x41, 0x08, 0x83, 0xf8, 0x01, 0x76, 0x05, 0x48, 0x89, 0x41, 0x08};
        static const BYTE w37c93[] = {0x8b, 0x41, 0x08, 0x83, 0xf8, 0x01, 0x75, 0x0e, 0x85, 0xc9, 0x74, 0x07};
        BYTE *e = (BYTE *)spr + 0x21558, *f = (BYTE *)spr + 0x35433, *g = (BYTE *)spr + 0x2e929, *h = (BYTE *)spr + 0x37c93;
        if (memcmp(e, wrel8, 11) || memcmp(f, wrel8, 11) || memcmp(g, w2e929, 12) || memcmp(h, w37c93, 12) ||
            (DWORD)(e + 0x14) + *(DWORD *)(e + 0x10) != spr + 0x2157d || (DWORD)(f + 0x14) + *(DWORD *)(f + 0x10) != spr + 0x35458) {
            logf("SPR_REFCOUNT> the other Release functions differ from shipped - not patched");
            return;
        }
        jmp_to(e, (void *)sr_rel_21558);
        jmp_to(f, (void *)sr_rel_35433);
        jmp_to(g, (void *)sr_rel_2e929);
        jmp_to(h, (void *)sr_rel_37c93);
    }
    jmp_to(a, (void *)sr_addref8);
    jmp_to(b, (void *)sr_release8);
    jmp_to(c, (void *)sr_addrefc);
    jmp_to(d, (void *)sr_releasec);
    logf("SPR_REFCOUNT> SIMSPR AddRef 0x10021551 / 0x1003cf95 and the six Releases of their classes are atomic");
}

/* Same bug in SIMSERV (exit crash at SIMSERV+0xCAD3, 1 in 4 closes with traffic_mt on AND off): class vtable
   0x1001f2c8 counts on +0x38 with AddRef `inc [ecx+0x38]` (0x1000c3df) and Release 0x1000cab6 `if (n) n--; if n == 0:
   vt+0x44(1)` - the destroy call landed on an already destroyed object (null vtable). */
static DWORD g_ss_base;
static LONG __fastcall ss_addref(BYTE *self) { return InterlockedIncrement((volatile LONG *)(self + 0x38)); }
static LONG __fastcall ss_release(BYTE *self) {
    volatile LONG *rc = (volatile LONG *)(self + 0x38);
    LONG o, n;
    do { o = *rc; n = o ? o - 1 : 0; } while (o && InterlockedCompareExchange(rc, n, o) != o);
    if (n) return n;
    ((VDEL_FN)(*(DWORD **)self)[0x44 / 4])(self, NULL, 1);
    InterlockedIncrement(&g_sr_frees);
    return 0;
}
static DWORD WINAPI ss_watcher(LPVOID p) {
    static const BYTE wadd[] = {0xff, 0x41, 0x38, 0x8b, 0x41, 0x38, 0xc3};
    static const BYTE wrel[] = {0x8b, 0x41, 0x38, 0x85, 0xc0, 0x76, 0x04, 0x48, 0x89, 0x41, 0x38};
    DWORD ss = 0;
    int ms = 0;
    (void)p;
    while (!(ss = (DWORD)GetModuleHandleA("SIMSERV.DLL")) && ms++ < 300000) Sleep(1);
    if (!ss) return 0;
    if (memcmp((BYTE *)ss + 0xc3df, wadd, 7) || memcmp((BYTE *)ss + 0xcab6, wrel, 11)) {
        logf("SPR_REFCOUNT> SIMSERV refcount differs from shipped - not patched");
        return 0;
    }
    g_ss_base = ss;
    jmp_to((BYTE *)ss + 0xcab6, (void *)ss_release);
    jmp_to((BYTE *)ss + 0xc3df, (void *)ss_addref);
    logf("SPR_REFCOUNT> SIMSERV class 0x1001f2c8 AddRef/Release atomic (0x1000c3df, 0x1000cab6)");
    return 0;
}
/* ---------------------------------------------------------------- STRTSIM_REFCOUNT (task reload1024, 2026-10-23)
   Owner: "I retried to load Europolis 1024 for a second time after I loaded it once and the game crashed" (STRTSIM
   0x10011908, a std::set insert in the strike-crowd producer). Two STRTSIM message listeners, the strike-crowd
   producer (vtable 0x1002c594, Linux cSSStrikeCrowdProducer) and the class at vtable 0x1002b0fc, share AddRef
   0x10010569 `inc [ecx+0xc]` and use if-nonzero Releases 0x100110fc / 0x100076a8 (`if (n) n--; if (!n) destroy`).
   GZServiceD's dispatch AddRefs and Releases every listener around each message (0x1000399b / 0x100039dc), and
   OccupantInserted / OccupantRemoved reach the producer from the sim thread and the game thread, so the plain
   inc/dec lose updates. Measured (Frida, STRTSIM pool + set destructor hooks, 1024 -> 1024 Load City, 5 runs):
   count one too low = the message server's unregister in the layer's Shutdown call (STRTSIM 0x144df -> producer
   Shutdown -> GZServiceD 0x3c4c) released it to 0 and destroyed it, then the layer's own Release (0x144ea) destroyed
   it again: its set header went back to STRTSIM's small-block pool twice (FUN_1001125c, 0x10011283), two later
   allocations shared one block and the next OccupantInserted crashed in the pool or the set rebalance. Count one
   too high = the producer leaked (never destroyed). Both bodies are made atomic with the same results; an
   over-release at 0 still destroys, as the game does. strtsim_refcount=0 turns this off. */
/* STRTSIM_REFCOUNT_ALL (2026-10-24, strtsim_refcount_all=0 off): the same two bodies in 12 more STRTSIM classes
   (vtables 0x1002A558 0x1002A92C 0x1002B550 0x1002C328 0x1002C600 0x1002C7C8 0x1002C840 0x1002C8CC 0x1002CB28
   0x1002CF40 0x1002CFA8 0x1002D1D0): AddRefs 0x10003310 (+8), 0x10015599 (+4), 0x10021980 (+0x10) and every
   if-nonzero Release of the template, its counter offset and destructor read from its own bytes. */
typedef struct { DWORD dtor, del, off; } STRP;
typedef void (__fastcall *STR_DTOR)(BYTE *self);
typedef void (__cdecl *STR_DEL)(void *p);
static int g_strtref_all = 1;
static LONG __fastcall st_addref4(BYTE *self) { return InterlockedIncrement((volatile LONG *)(self + 4)); }
static LONG __fastcall st_addref8(BYTE *self) { return InterlockedIncrement((volatile LONG *)(self + 8)); }
static LONG __fastcall st_addref(BYTE *self) { return InterlockedIncrement((volatile LONG *)(self + 0xc)); }
static LONG __fastcall st_addref10(BYTE *self) { return InterlockedIncrement((volatile LONG *)(self + 0x10)); }
static LONG __fastcall st_release(BYTE *self, STRP *p) {
    volatile LONG *rc = (volatile LONG *)(self + p->off);
    LONG o, n;
    for (;;) {
        o = *rc;
        if (!o) { n = 0; break; }                    /* the original skips the decrement and destroys */
        if (InterlockedCompareExchange(rc, o - 1, o) == o) { n = o - 1; break; }
    }
    if (n) return n;
    ((STR_DTOR)p->dtor)(self);
    ((STR_DEL)p->del)(self);
    return 0;
}
/* the Release template at r (counter offset r[5]): 1 if it matches byte for byte */
static int st_is_release(const BYTE *r) {
    BYTE n = r[5];
    return r[0] == 0x56 && r[1] == 0x8b && r[2] == 0xf1 && r[3] == 0x8b && r[4] == 0x46 &&
           (n == 4 || n == 8 || n == 0xc || n == 0x10) &&
           r[6] == 0x85 && r[7] == 0xc0 && r[8] == 0x76 && r[9] == 0x04 && r[10] == 0x48 && r[11] == 0x89 &&
           r[12] == 0x46 && r[13] == n && r[14] == 0x8b && r[15] == 0x46 && r[16] == n && r[17] == 0x85 &&
           r[18] == 0xc0 && r[19] == 0x75 && r[20] == 0x14 && r[21] == 0x85 && r[22] == 0xf6 && r[23] == 0x74 &&
           r[24] == 0x0e && r[25] == 0x8b && r[26] == 0xce && r[27] == 0xe8 && r[0x20] == 0x56 && r[0x21] == 0xe8 &&
           !memcmp(r + 0x26, "\x59\x33\xc0\x5e\xc3", 5);
}
static DWORD WINAPI st_watcher(LPVOID unused) {
    static const struct { DWORD rva; BYTE off; void *fn; int all; } adds[4] = {
        {0x10569, 0x0c, (void *)st_addref, 0}, {0x3310, 0x08, (void *)st_addref8, 1},
        {0x15599, 0x04, (void *)st_addref4, 1}, {0x21980, 0x10, (void *)st_addref10, 1}};
    BYTE *st = NULL, *stubs;
    STRP *pp;
    DWORD e, k, sec, i, vs, va;
    WORD ns, opt;
    int ms = 0, n = 0, na = 0;
    (void)unused;
    while (!(st = (BYTE *)GetModuleHandleA("STRTSIM.DLL")) && ms++ < 300000) Sleep(1);
    if (!st) return 0;
    for (k = 0; k < 4; k++) {
        BYTE *a = st + adds[k].rva, o = adds[k].off;
        if (a[0] != 0xff || a[1] != 0x41 || a[2] != o || a[3] != 0x8b || a[4] != 0x41 || a[5] != o || a[6] != 0xc3) {
            logf("STRTSIM_REFCOUNT> AddRef STRTSIM+0x%lx differs from shipped - not patched", adds[k].rva); return 0;
        }
    }
    if (!st_is_release(st + 0x110fc) || !st_is_release(st + 0x76a8)) {
        logf("STRTSIM_REFCOUNT> STRTSIM+0x110fc / +0x76a8 differ from shipped - not patched"); return 0;
    }
    stubs = (BYTE *)VirtualAlloc(NULL, 8192, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!stubs) return 0;
    pp = (STRP *)(stubs + 4096);
    e = *(DWORD *)(st + 0x3c); ns = *(WORD *)(st + e + 6); opt = *(WORD *)(st + e + 0x14); sec = (DWORD)st + e + 0x18 + opt;
    for (k = 0; k < ns; k++) {
        DWORD sh = sec + k * 40;
        if (!(*(DWORD *)(sh + 0x24) & 0x20000000)) continue;
        va = (DWORD)st + *(DWORD *)(sh + 0x0c); vs = *(DWORD *)(sh + 0x08);
        for (i = 0; i + 0x30 < vs && n < 64; i++) {
            BYTE *r = (BYTE *)va + i, *stub;
            DWORD rva = (DWORD)(r - st);
            if (r[0] != 0x56 || !st_is_release(r)) continue;
            if (!g_strtref_all && rva != 0x110fc && rva != 0x76a8) continue;
            stub = stubs + n * 16;
            pp[n].dtor = (DWORD)(r + 0x20) + *(DWORD *)(r + 0x1c);          /* call rel32 at +0x1b */
            pp[n].del = (DWORD)(r + 0x26) + *(DWORD *)(r + 0x22);           /* call rel32 at +0x21 */
            pp[n].off = r[5];
            stub[0] = 0xBA; *(DWORD *)(stub + 1) = (DWORD)&pp[n];           /* mov edx, params */
            stub[5] = 0xE9; *(DWORD *)(stub + 6) = (DWORD)st_release - (DWORD)(stub + 10);
            jmp_to(r, stub);
            n++;
        }
    }
    for (k = 0; k < 4; k++)
        if (!adds[k].all || g_strtref_all) { jmp_to(st + adds[k].rva, adds[k].fn); na++; }
    logf("STRTSIM_REFCOUNT> %d AddRef + %d if-nonzero Release bodies atomic (%s)", na, n,
         g_strtref_all ? "all 14 plain-refcount classes" : "strike-crowd producer + vtable 0x1002b0fc only, strtsim_refcount_all=0");
    return 0;
}
/* ---------------------------------------------------------------- SIMGROUP_REFCOUNT (task reload1024, 2026-10-24)
   SIMCITY's sim group (vtable 0x10013d.., Simulate FUN_1000e93f iterates its 6 simulator vectors at +0x94) counts
   references with a plain base AddRef 0x10010d0d `inc [ecx+4]` and if-nonzero Release 0x10010d14 (count 0: vt+0x98(1)),
   reached through the adjustor thunks 0x1000e787 / 0x1000e78f. Same race class as STRTSIM_REFCOUNT, a template the
   LAYER_REFCOUNT scan does not match (no stats call, ecx not esi). Suspect for the crash while playing a city
   reloaded over a 1024 city: the sim registry walk calls a group whose simulator vectors are freed. Both bodies are
   made atomic with the same results. simgroup_refcount=0 turns this off. */
static int g_sgref = 1;
typedef void (__fastcall *SG_DEL)(BYTE *self, void *edx, DWORD flags);
static LONG __fastcall sg_addref(BYTE *self) { return InterlockedIncrement((volatile LONG *)(self + 4)); }
static LONG __fastcall sg_release(BYTE *self) {
    volatile LONG *rc = (volatile LONG *)(self + 4);
    LONG o, n;
    for (;;) {
        o = *rc;
        if (!o) { n = 0; break; }
        if (InterlockedCompareExchange(rc, o - 1, o) == o) { n = o - 1; break; }
    }
    if (n) return n;
    if (self) ((SG_DEL)(*(DWORD **)self)[0x98 / 4])(self, NULL, 1);
    return 0;
}
static DWORD WINAPI sg_watcher(LPVOID unused) {
    static const BYTE wadd[] = {0xff, 0x41, 0x04, 0x8b, 0x41, 0x04, 0xc3};
    static const BYTE wrel[] = {0x8b, 0x41, 0x04, 0x85, 0xc0, 0x76, 0x04, 0x48, 0x89, 0x41, 0x04, 0x8b, 0x41, 0x04,
                                0x85, 0xc0, 0x75, 0x10, 0x85, 0xc9, 0x74, 0x0a, 0x8b, 0x01, 0x6a, 0x01, 0xff, 0x90,
                                0x98, 0x00, 0x00, 0x00, 0x33, 0xc0, 0xc3};
    BYTE *sc = NULL;
    int ms = 0;
    (void)unused;
    while (!(sc = (BYTE *)GetModuleHandleA("SIMCITY.DLL")) && ms++ < 300000) Sleep(1);
    if (!sc) return 0;
    if (memcmp(sc + 0x10d0d, wadd, sizeof(wadd)) || memcmp(sc + 0x10d14, wrel, sizeof(wrel))) {
        logf("SIMGROUP_REFCOUNT> SIMCITY+0x10d0d/0x10d14 differ from shipped - not patched"); return 0;
    }
    jmp_to(sc + 0x10d14, (void *)sg_release);
    jmp_to(sc + 0x10d0d, (void *)sg_addref);
    logf("SIMGROUP_REFCOUNT> SIMCITY sim group AddRef 0x10010d0d / Release 0x10010d14 atomic");
    return 0;
}
/* ---------------------------------------------------------------- RES_REFCOUNT (task refaudit, 2026-10-24)
   The plain-refcount classes the refaudit census (verify/refaudit/RESULTS.md, Frida per-object thread census over two
   1024 games with reloads) saw handed back and forth between live threads, made atomic with the same results:
   - SIMSPR and GZResourceD resource object (the same framework class, a 3-dword resource key at +0xc; vtables
     0x10068950 / 0x1001d410 at +4): AddRef `inc [ecx+4]` (SIMSPR 0x1005982a, GZResourceD 0x10015b03) and Release
     `if (n <= 1) vt+0x14(1), return 0; else n -= 1` (0x10059831 / 0x1000b7c0). Game, sim and sprite-loader threads,
     up to 11 thread switches on one object. Switches res_refcount_simspr, res_refcount_gzres.
   - STRTSIM occupant family (base vtable 0x1002b95c, live 0x1002af90 0x1002c9bc 0x1002b7ac): Release 0x1001607d
     `if (n) n--; if (!n) vt+0x120(1)` on +8, whose AddRef 0x10003310 STRTSIM_REFCOUNT_ALL already made atomic (that
     pass only matches the esi form). Game + sim. Switch strtsim_refcount_ecx.
   - SCENARIO layer (vtable 0x1001a64c, GZ message target at +4): AddRef 0x10005b6f `inc [ecx+0xc]`, Release
     0x100099a1 (the STRTSIM esi template: dtor 0x100067f0 + delete). Game + sim, rare. Switch scenario_refcount.
   - Second census pass over the 86 `<= 1` vtables (verify/refaudit/le1_refcount_vtables.txt): SIMUI wrapper object
     (vtable 0x100a8164, 0x14 bytes, ctor 0x10043d52, made in 0x10043424 and handed to its owner's vt+0x9c): AddRef
     0x100139b6 `inc [ecx+4]` (shared by other SIMUI classes), Release 0x10043ba9 `<= 1` through vt+0x44. Every object
     went game -> sim -> game, rare. Switch le1_refcount_simui.
   All switches default on; each module is byte-checked against the shipped DLL and left alone if it differs. */
static int g_resref_spr = 1, g_resref_gz = 1, g_strtref_ecx = 1, g_scnref = 1, g_le1ref_ui = 1;
static LONG rr_release_le1(BYTE *self, int slot) {
    volatile LONG *rc = (volatile LONG *)(self + 4);
    for (;;) {
        LONG o = *rc;
        if (o <= 1) {                         /* the original destroys at <= 1 without writing the count */
            if (InterlockedCompareExchange(rc, 0, o) != o) continue;
            if (self) ((VDEL_FN)(*(DWORD **)self)[slot / 4])(self, NULL, 1);
            return 0;
        }
        if (InterlockedCompareExchange(rc, o - 1, o) == o) return o - 1;
    }
}
static LONG __fastcall rr_rel_le1_4_14(BYTE *self) { return rr_release_le1(self, 0x14); }
static LONG __fastcall rr_rel_le1_4_44(BYTE *self) { return rr_release_le1(self, 0x44); }
static LONG __fastcall rr_rel_nz_8_120(BYTE *self) {
    volatile LONG *rc = (volatile LONG *)(self + 8);
    LONG o, n;
    for (;;) {
        o = *rc;
        if (!o) { n = 0; break; }
        if (InterlockedCompareExchange(rc, o - 1, o) == o) { n = o - 1; break; }
    }
    if (n) return n;
    if (self) ((VDEL_FN)(*(DWORD **)self)[0x120 / 4])(self, NULL, 1);
    return 0;
}
static STRP g_scn_p;
static LONG __fastcall rr_scn_release(BYTE *self) { return st_release(self, &g_scn_p); }
static const BYTE RR_ADD4[] = {0xff, 0x41, 0x04, 0x8b, 0x41, 0x04, 0xc3};
static const BYTE RR_LE1_4_14[] = {0x8b, 0x41, 0x04, 0x83, 0xf8, 0x01, 0x77, 0x0e, 0x85, 0xc9, 0x74, 0x07, 0x8b, 0x01,
                                   0x6a, 0x01, 0xff, 0x50, 0x14, 0x33, 0xc0, 0xc3, 0x48, 0x89, 0x41, 0x04, 0xc3};
/* AddRef `inc [ecx+4]` at rva_a and Release `<= 1` at rva_r: both or neither. 0 = module not loaded yet */
static int rr_patch_res(const char *name, DWORD rva_a, DWORD rva_r) {
    BYTE *m = (BYTE *)GetModuleHandleA(name);
    if (!m) return 0;
    if (memcmp(m + rva_a, RR_ADD4, sizeof(RR_ADD4)) || memcmp(m + rva_r, RR_LE1_4_14, sizeof(RR_LE1_4_14))) {
        logf("RES_REFCOUNT> %s+0x%lx / +0x%lx differ from shipped - not patched", name, rva_a, rva_r); return 1;
    }
    jmp_to(m + rva_r, (void *)rr_rel_le1_4_14);
    jmp_to(m + rva_a, (void *)st_addref4);
    logf("RES_REFCOUNT> %s resource object AddRef 0x%08lx / Release 0x%08lx atomic", name, 0x10000000 + rva_a, 0x10000000 + rva_r);
    return 1;
}
static int rr_patch_strtsim(void) {
    static const BYTE wrel[] = {0x8b, 0x41, 0x08, 0x85, 0xc0, 0x76, 0x04, 0x48, 0x89, 0x41, 0x08, 0x8b, 0x41, 0x08,
                                0x85, 0xc0, 0x75, 0x10, 0x85, 0xc9, 0x74, 0x0a, 0x8b, 0x01, 0x6a, 0x01, 0xff, 0x90,
                                0x20, 0x01, 0x00, 0x00, 0x33, 0xc0, 0xc3};
    BYTE *m = (BYTE *)GetModuleHandleA("STRTSIM.DLL");
    if (!m) return 0;
    if (memcmp(m + 0x1607d, wrel, sizeof(wrel))) { logf("RES_REFCOUNT> STRTSIM+0x1607d differs from shipped - not patched"); return 1; }
    jmp_to(m + 0x1607d, (void *)rr_rel_nz_8_120);
    logf("RES_REFCOUNT> STRTSIM occupant Release 0x1001607d atomic%s",
         g_strtref && g_strtref_all ? "" : " (strtsim_refcount_all is off: its AddRef 0x10003310 stays plain)");
    return 1;
}
static int rr_patch_scenario(void) {
    static const BYTE wadd[] = {0xff, 0x41, 0x0c, 0x8b, 0x41, 0x0c, 0xc3};
    BYTE *m = (BYTE *)GetModuleHandleA("SCENARIO.DLL"), *r;
    if (!m) return 0;
    r = m + 0x99a1;
    if (memcmp(m + 0x5b6f, wadd, sizeof(wadd)) || !st_is_release(r) || r[5] != 0x0c ||
        (DWORD)(r + 0x20) + *(DWORD *)(r + 0x1c) != (DWORD)m + 0x67f0) {
        logf("RES_REFCOUNT> SCENARIO+0x5b6f / +0x99a1 differ from shipped - not patched"); return 1;
    }
    g_scn_p.dtor = (DWORD)(r + 0x20) + *(DWORD *)(r + 0x1c);          /* call rel32 at +0x1b */
    g_scn_p.del = (DWORD)(r + 0x26) + *(DWORD *)(r + 0x22);           /* call rel32 at +0x21 */
    g_scn_p.off = 0x0c;
    jmp_to(r, (void *)rr_scn_release);
    jmp_to(m + 0x5b6f, (void *)st_addref);
    logf("RES_REFCOUNT> SCENARIO layer AddRef 0x10005b6f / Release 0x100099a1 atomic");
    return 1;
}
/* SIMUI wrapper object: the same `<= 1` template, destroy slot 0x44 */
static int rr_patch_simui(void) {
    BYTE *m = (BYTE *)GetModuleHandleA("SIMUI.DLL");
    BYTE rel[sizeof(RR_LE1_4_14)];
    if (!m) return 0;
    memcpy(rel, RR_LE1_4_14, sizeof(rel)); rel[18] = 0x44;
    if (memcmp(m + 0x139b6, RR_ADD4, sizeof(RR_ADD4)) || memcmp(m + 0x43ba9, rel, sizeof(rel))) {
        logf("RES_REFCOUNT> SIMUI+0x139b6 / +0x43ba9 differ from shipped - not patched"); return 1;
    }
    jmp_to(m + 0x43ba9, (void *)rr_rel_le1_4_44);
    jmp_to(m + 0x139b6, (void *)st_addref4);
    logf("RES_REFCOUNT> SIMUI wrapper object AddRef 0x100139b6 / Release 0x10043ba9 atomic");
    return 1;
}
static DWORD WINAPI rr_watcher(LPVOID unused) {
    int ms, k, all, done[5];
    (void)unused;
    done[0] = !g_resref_spr; done[1] = !g_resref_gz; done[2] = !g_strtref_ecx; done[3] = !g_scnref; done[4] = !g_le1ref_ui;
    for (ms = 0; ms < 300000; ms++) {
        if (!done[0]) done[0] = rr_patch_res("SIMSPR.DLL", 0x5982a, 0x59831);
        if (!done[1]) done[1] = rr_patch_res("GZResourceD.dll", 0x15b03, 0xb7c0);
        if (!done[2]) done[2] = rr_patch_strtsim();
        if (!done[3]) done[3] = rr_patch_scenario();
        if (!done[4]) done[4] = rr_patch_simui();
        for (k = 0, all = 1; k < 5; k++) all &= done[k];
        if (all) break;
        Sleep(1);
    }
    return 0;
}
static DWORD WINAPI spr_watcher(LPVOID p) {
    DWORD spr = 0;
    int ms = 0;
    (void)p;
    while (!(spr = (DWORD)GetModuleHandleA("SIMSPR.DLL")) && ms++ < 300000) Sleep(1);
    if (!spr) { logf("SPRITES> SIMSPR.DLL never loaded"); return 0; }
    if (g_spr_budget > 0) patch_sprites(spr);
    if (g_spr_follow) patch_follow(spr);
    if (g_sprref) patch_sprrefcount(spr);
    return 0;
}

static void patch_dayhook(DWORD sc);

/* FUN_10001db0 replacement (fastcall, ecx = list object, *ecx = sentinel head): 0, 1 or 2 (= two or more) */
static __declspec(naked) void list_count_fast(void) {
    __asm {
        mov ecx, dword ptr [ecx]
        xor eax, eax
        mov edx, dword ptr [ecx]
        cmp edx, ecx
        je done
        inc eax
        mov edx, dword ptr [edx]
        cmp edx, ecx
        je done
        inc eax
    done:
        ret
    }
}

/* ---- registry index for LIST_FIND. All access under g_lfcs (the game's own locks are per registry). */
typedef struct { DWORD head, obj, node; } LFE;
typedef struct { DWORD head; int state; } LFL;      /* state 0 = not indexed, 1 = indexed, 2 = never (duplicates) */
static CRITICAL_SECTION g_lfcs;
static LFE  *g_lft;
static DWORD g_lfcap, g_lfused;                     /* used = live + tombstones (head == 1) */
static LFL   g_lfl[64];
static volatile LONG g_lf_hits, g_lf_walks, g_lf_builds, g_lf_drops;
static DWORD lf_slot(DWORD head, DWORD obj) { return ((obj * 2654435761u) ^ (head * 40503u)) & (g_lfcap - 1); }

static void lf_clear(void) {
    if (g_lft) memset(g_lft, 0, g_lfcap * sizeof(LFE));
    g_lfused = 0;
    memset(g_lfl, 0, sizeof(g_lfl));
}
static LFL *lf_list(DWORD head, int create) {
    int i;
    for (i = 0; i < 64; i++) if (g_lfl[i].head == head) return &g_lfl[i];
    if (!create) return NULL;
    for (i = 0; i < 64; i++) if (!g_lfl[i].head) { g_lfl[i].head = head; g_lfl[i].state = 0; return &g_lfl[i]; }
    return NULL;
}
static LFE *lf_find(DWORD head, DWORD obj) {
    DWORD i, n;
    if (!g_lft) return NULL;
    i = lf_slot(head, obj);
    for (n = 0; n < g_lfcap; n++, i = (i + 1) & (g_lfcap - 1)) {
        if (!g_lft[i].head) return NULL;
        if (g_lft[i].head == head && g_lft[i].obj == obj) return &g_lft[i];
    }
    return NULL;
}
static int lf_grow(void) {
    LFE *old = g_lft;
    DWORD oc = g_lfcap, i, nc = oc ? oc * 2 : (1u << 16);
    LFE *t = (LFE *)VirtualAlloc(NULL, nc * sizeof(LFE), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!t) return 0;
    g_lft = t; g_lfcap = nc; g_lfused = 0;
    for (i = 0; i < oc; i++)
        if (old[i].head > 1) {
            DWORD j = lf_slot(old[i].head, old[i].obj);
            while (g_lft[j].head) j = (j + 1) & (g_lfcap - 1);
            g_lft[j] = old[i]; g_lfused++;
        }
    if (old) VirtualFree(old, 0, MEM_RELEASE);
    return 1;
}
/* 1 = inserted, 0 = duplicate key (or no memory) */
static int lf_insert(DWORD head, DWORD obj, DWORD node) {
    DWORD i;
    if ((!g_lft || (g_lfused + 1) * 10 >= g_lfcap * 6) && !lf_grow()) return 0;
    if (lf_find(head, obj)) return 0;
    i = lf_slot(head, obj);
    while (g_lft[i].head > 1) i = (i + 1) & (g_lfcap - 1);
    if (!g_lft[i].head) g_lfused++;
    g_lft[i].head = head; g_lft[i].obj = obj; g_lft[i].node = node;
    return 1;
}
static void lf_drop(void) { lf_clear(); InterlockedIncrement(&g_lf_drops); }

/* the original search, from both ends (fallback) */
static DWORD lf_walk(DWORD head, DWORD obj) {
    DWORD f = *(DWORD *)head, b = *(DWORD *)(head + 4);
    InterlockedIncrement(&g_lf_walks);
    while (f != head) {
        if (*(DWORD *)(f + 8) == obj) return f;
        if (*(DWORD *)(b + 8) == obj) return b;
        if (f == b) break;
        f = *(DWORD *)f;
        if (f == b) break;
        b = *(DWORD *)(b + 4);
    }
    return 0;
}

static DWORD __cdecl lf_lookup(DWORD *list, DWORD obj) {
    DWORD head = *list, node;
    LFL *l;
    EnterCriticalSection(&g_lfcs);
    l = lf_list(head, 1);
    if (l && l->state == 0) {                        /* index this list: one walk */
        DWORD p;
        int ok = 1;
        for (p = *(DWORD *)head; p != head; p = *(DWORD *)p)
            if (!lf_insert(head, *(DWORD *)(p + 8), p)) { ok = 0; break; }
        if (ok) { l->state = 1; InterlockedIncrement(&g_lf_builds); }
        else { lf_drop(); l = lf_list(head, 1); if (l) l->state = 2; }
    }
    if (l && l->state == 1) {
        LFE *e = lf_find(head, obj);
        if (e) {
            DWORD n = e->node;
            if (*(DWORD *)(n + 8) == obj && *(DWORD *)(*(DWORD *)(n + 4)) == n && *(DWORD *)(*(DWORD *)n + 4) == n) {
                e->head = 1;                         /* tombstone: the caller erases this node now */
                InterlockedIncrement(&g_lf_hits);
                LeaveCriticalSection(&g_lfcs);
                return n;
            }
            lf_drop();                               /* stale: start over */
        } else {
            InterlockedIncrement(&g_lf_hits);        /* indexed and absent = not in the list */
            LeaveCriticalSection(&g_lfcs);
            return 0;
        }
    }
    node = lf_walk(head, obj);
    LeaveCriticalSection(&g_lfcs);
    return node;
}

/* push_back wrapper at SIMCITY 0x10001c15: thiscall FUN_10001dc0(list, &obj), ret 4 */
typedef void (__fastcall *PUSH_FN)(DWORD *list, void *edx, DWORD *pobj);
static PUSH_FN g_lf_push;
static void __fastcall lf_push(DWORD *list, void *edx, DWORD *pobj) {
    DWORD head, obj = *pobj;
    LFL *l;
    g_lf_push(list, edx, pobj);
    head = *list;
    EnterCriticalSection(&g_lfcs);
    l = lf_list(head, 0);
    if (l && l->state == 1 && !lf_insert(head, obj, *(DWORD *)(head + 4))) {
        lf_drop();
        l = lf_list(head, 1);
        if (l) l->state = 2;
    }
    LeaveCriticalSection(&g_lfcs);
}

/* FUN_10002120 (range erase, list teardown): wipe the index, then run the original */
static DWORD g_lf_2120_cont;
static void __cdecl lf_teardown(void) { EnterCriticalSection(&g_lfcs); lf_clear(); LeaveCriticalSection(&g_lfcs); }
static __declspec(naked) void lf_2120_stub(void) {
    __asm {
        pushad
        call lf_teardown
        popad
        push ebp
        mov ebp, esp
        push ecx
        push esi
        jmp dword ptr [g_lf_2120_cont]
    }
}

/* Entered by JMP from SIMCITY 0x10001c80 with ecx = list object, ebp = FUN_10001c63's frame ([ebp+8] = the object
   to remove). Leaves like the original loop: found -> eax = node, edi = object, continue at 0x10001ca7;
   not found -> continue at 0x10001c96. */
static DWORD g_lf_found, g_lf_missing;
static __declspec(naked) void list_find_both_ends(void) {
    __asm {
        mov edi, dword ptr [ebp + 8]
        push edi
        push ecx
        call lf_lookup
        add esp, 8
        test eax, eax
        jz missing
        jmp dword ptr [g_lf_found]
    missing:
        jmp dword ptr [g_lf_missing]
    }
}

static void patch_listfind(DWORD sc) {
    static const BYTE want[] = {0x8b, 0x11, 0x8b, 0x02, 0x3b, 0xc2, 0x74, 0x0e, 0x8b, 0x7d, 0x08, 0x39, 0x78, 0x08,
                                0x74, 0x17, 0x8b, 0x00, 0x3b, 0xc2, 0x75, 0xf5};
    BYTE *p = (BYTE *)sc + 0x1c80;
    DWORD old;
    if (memcmp(p, want, sizeof(want))) { logf("LIST_FIND> SIMCITY+0x1c80 differs from shipped - not patched"); return; }
    BYTE *c = (BYTE *)sc + 0x1c15, *t = (BYTE *)sc + 0x2120;
    static const BYTE want_t[] = {0x55, 0x8b, 0xec, 0x51, 0x56, 0x8b, 0x75, 0x10};
    if (c[0] != 0xe8 || (DWORD)(c + 5) + *(DWORD *)(c + 1) != sc + 0x1dc0 || memcmp(t, want_t, sizeof(want_t))) {
        logf("LIST_FIND> SIMCITY+0x1c15 / +0x2120 differ from shipped - not patched");
        return;
    }
    InitializeCriticalSection(&g_lfcs);
    g_lf_found = sc + 0x1ca7; g_lf_missing = sc + 0x1c96;
    g_lf_push = (PUSH_FN)(sc + 0x1dc0); g_lf_2120_cont = sc + 0x2125;
    if (!VirtualProtect(p, 5, PAGE_EXECUTE_READWRITE, &old) || !VirtualProtect(c, 5, PAGE_EXECUTE_READWRITE, &old) ||
        !VirtualProtect(t, 5, PAGE_EXECUTE_READWRITE, &old)) return;
    t[0] = 0xE9; *(DWORD *)(t + 1) = (DWORD)lf_2120_stub - (DWORD)(t + 5);
    *(DWORD *)(c + 1) = (DWORD)lf_push - (DWORD)(c + 5);
    p[0] = 0xE9; *(DWORD *)(p + 1) = (DWORD)list_find_both_ends - (DWORD)(p + 5);
    FlushInstructionCache(GetCurrentProcess(), (BYTE *)sc + 0x1c00, 0x600);
    logf("LIST_FIND> SIMCITY registry remove uses a hash index (push 0x1c15, search 0x1c80, teardown 0x2120 hooked)");
}

static void patch_listcount(DWORD sc) {
    static const BYTE want[] = {0x8b, 0x09, 0x33, 0xc0, 0x8b, 0x11, 0x3b, 0xd1, 0x74, 0x05, 0x8b, 0x12, 0x40, 0xeb, 0xf7, 0xc3};
    BYTE *p = (BYTE *)sc + 0x1db0;
    DWORD old;
    if (memcmp(p, want, sizeof(want))) { logf("LIST_COUNT> SIMCITY+0x1db0 differs from shipped - not patched"); return; }
    if (!VirtualProtect(p, 5, PAGE_EXECUTE_READWRITE, &old)) return;
    p[0] = 0xE9; *(DWORD *)(p + 1) = (DWORD)list_count_fast - (DWORD)(p + 5);
    FlushInstructionCache(GetCurrentProcess(), p, 5);
    logf("LIST_COUNT> SIMCITY FUN_10001db0 (registry list count, used only for ==0 / ==1) is now constant time");
}
static DWORD WINAPI busy_thread(LPVOID p);
static DWORD WINAPI clock_watcher(LPVOID p) {
    DWORD sc = 0;
    int ms = 0;
    (void)p;
    while (!(sc = (DWORD)GetModuleHandleA("SIMCITY.DLL")) && ms++ < 300000) Sleep(1);
    if (!sc) { logf("SIMCLOCK> SIMCITY.DLL never loaded"); return 0; }
    if (g_clock_ms) patch_clock(sc);
    if (g_listcount) patch_listcount(sc);
    if (g_listfind) patch_listfind(sc);
    if (g_busy) { patch_dayhook(sc); CreateThread(NULL, 0, busy_thread, NULL, 0, NULL); }
    return 0;
}

/* ---------------------------------------------------------------- profiler */
#define PB 65536
#define STK_BYTES 4096
static DWORD g_ex_key[PB], g_ex_cnt[PB], g_in_key[PB], g_in_cnt[PB];
static DWORD g_samples, g_overflow;
/* SIM THREADS: threads started by SIMCITY's thread class (FUN_1000d036 -> _beginthreadex); their stacks hold
   the return address SIMCITY+0xd0a5 (cdb, deadlock dump 2026-10-08: the thread running SIMCITY -> SIMRCI ->
   SIMGEOM). Sampled into a second pair of tables, dumped as E2/I2. */
static DWORD g_ex2_key[PB], g_ex2_cnt[PB], g_in2_key[PB], g_in2_cnt[PB];
static DWORD g_samples2;
/* TRAFFIC_MT workers: a third pair of tables, dumped as E3/I3 (perf_report --thread workers) */
static DWORD g_ex3_key[PB], g_ex3_cnt[PB], g_in3_key[PB], g_in3_cnt[PB];
static DWORD g_samples3;
static BYTE  g_sim_isw[32];
static DWORD g_sim_tid[32];
static HANDLE g_sim_th[32];
static volatile LONG g_nsim, g_nsim_real;   /* all sampled threads; the SIMCITY-class ones among them */
/* TRAFFIC_MT workers are sampled like sim threads (profiler E2/I2 and the busy readout) */
static void prof_add_thread(HANDLE th, DWORD tid) {
    LONG k = g_nsim;
    if (k >= 32 || !th) return;
    g_sim_tid[k] = tid; g_sim_th[k] = th; g_sim_isw[k] = 1;
    InterlockedIncrement(&g_nsim);
}
static DWORD g_exb[512], g_exe[512];   /* was 64: full with ~100 modules, so the later sim DLLs failed is_retaddr (2026-10-09) */
static int   g_nex;

static void exec_ranges(void) {
    HANDLE s = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, GetCurrentProcessId());
    MODULEENTRY32 me;
    g_nex = 0;
    if (s == INVALID_HANDLE_VALUE) return;
    me.dwSize = sizeof(me);
    if (Module32First(s, &me)) do {
        DWORD h = (DWORD)me.modBaseAddr, e, sec;
        WORD ns, opt, k;
        HMODULE pin = NULL;                            /* task onramp: the module may be freed after the snapshot */
        if (!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS, (LPCSTR)h, &pin) || (DWORD)pin != h) {
            if (pin) FreeLibrary(pin);
            continue;
        }
        e = *(DWORD *)(h + 0x3c);
        ns = *(WORD *)(h + e + 6); opt = *(WORD *)(h + e + 0x14);
        sec = h + e + 0x18 + opt;
        for (k = 0; k < ns && g_nex < 512; k++) {
            DWORD sh = sec + (DWORD)k * 40;
            if (*(DWORD *)(sh + 0x24) & 0x20000000) {
                g_exb[g_nex] = h + *(DWORD *)(sh + 0x0c);
                g_exe[g_nex] = g_exb[g_nex] + *(DWORD *)(sh + 0x08);
                g_nex++;
            }
        }
        FreeLibrary(pin);
    } while (Module32Next(s, &me));
    CloseHandle(s);
}
static int in_exec(DWORD a) {
    int i;
    for (i = 0; i < g_nex; i++) if (a >= g_exb[i] && a < g_exe[i]) return 1;
    return 0;
}
/* return address = a CALL ends exactly at `a` (same encodings as sc3resize rz_is_retaddr) */
static int is_retaddr(DWORD a) {
    const BYTE *p = (const BYTE *)a;
    BYTE m;
    if (!in_exec(a) || !in_exec(a - 7)) return 0;
    if (p[-5] == 0xE8) return 1;
    m = p[-1];
    if (p[-2] == 0xFF && ((m >> 3) & 7) == 2 &&
        ((m >= 0xD0 && m <= 0xD7) || ((m >= 0x10 && m <= 0x17) && m != 0x14 && m != 0x15))) return 1;
    m = p[-2];
    if (p[-3] == 0xFF && ((m >> 3) & 7) == 2 && (((m >= 0x50 && m <= 0x57) && m != 0x54) || m == 0x14)) return 1;
    if (p[-4] == 0xFF && p[-3] == 0x54) return 1;
    m = p[-5];
    if (p[-6] == 0xFF && (m == 0x15 || ((m >= 0x90 && m <= 0x97) && m != 0x94))) return 1;
    if (p[-7] == 0xFF && p[-6] == 0x94) return 1;
    return 0;
}
static void hit(DWORD *key, DWORD *cnt, DWORD a) {
    DWORD i = (a * 2654435761u) >> 16 & (PB - 1), t = 0;
    while (t++ < 256) {
        if (key[i] == a) { cnt[i]++; return; }
        if (!key[i]) { key[i] = a; cnt[i] = 1; return; }
        i = (i + 1) & (PB - 1);
    }
    g_overflow++;
}
static void prof_reset(void) {
    memset(g_ex_key, 0, sizeof(g_ex_key)); memset(g_ex_cnt, 0, sizeof(g_ex_cnt));
    memset(g_in_key, 0, sizeof(g_in_key)); memset(g_in_cnt, 0, sizeof(g_in_cnt));
    memset(g_ex2_key, 0, sizeof(g_ex2_key)); memset(g_ex2_cnt, 0, sizeof(g_ex2_cnt));
    memset(g_in2_key, 0, sizeof(g_in2_key)); memset(g_in2_cnt, 0, sizeof(g_in2_cnt));
    memset(g_ex3_key, 0, sizeof(g_ex3_key)); memset(g_ex3_cnt, 0, sizeof(g_ex3_cnt));
    memset(g_in3_key, 0, sizeof(g_in3_key)); memset(g_in3_cnt, 0, sizeof(g_in3_cnt));
    g_samples = 0; g_samples2 = 0; g_samples3 = 0; g_overflow = 0;
    exec_ranges();
}
static void prof_dump(const char *tag) {
    char path[MAX_PATH];
    FILE *f;
    HANDLE s;
    MODULEENTRY32 me;
    DWORD i;
    _snprintf(path, sizeof(path), "%ssc3perf_prof_%s.txt", g_dir, tag);
    f = fopen(path, "w");
    if (!f) { logf("PROF> cannot write %s", path); return; }
    fprintf(f, "# sc3perf profile tag=%s samples=%lu overflow=%lu tid=%lu samples2=%lu simthreads=%ld samples3=%lu workers=%ld\n",
            tag, g_samples, g_overflow, g_game_tid, g_samples2, g_nsim_real, g_samples3, g_nsim - g_nsim_real);
    s = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, GetCurrentProcessId());
    me.dwSize = sizeof(me);
    if (s != INVALID_HANDLE_VALUE && Module32First(s, &me)) do {
        fprintf(f, "M 0x%08lX 0x%08lX %s\n", (DWORD)me.modBaseAddr, me.modBaseSize, me.szModule);
    } while (Module32Next(s, &me));
    if (s != INVALID_HANDLE_VALUE) CloseHandle(s);
    for (i = 0; i < PB; i++) if (g_ex_key[i]) fprintf(f, "E 0x%08lX %lu\n", g_ex_key[i], g_ex_cnt[i]);
    for (i = 0; i < PB; i++) if (g_in_key[i]) fprintf(f, "I 0x%08lX %lu\n", g_in_key[i], g_in_cnt[i]);
    for (i = 0; i < PB; i++) if (g_ex2_key[i]) fprintf(f, "E2 0x%08lX %lu\n", g_ex2_key[i], g_ex2_cnt[i]);
    for (i = 0; i < PB; i++) if (g_in2_key[i]) fprintf(f, "I2 0x%08lX %lu\n", g_in2_key[i], g_in2_cnt[i]);
    for (i = 0; i < PB; i++) if (g_ex3_key[i]) fprintf(f, "E3 0x%08lX %lu\n", g_ex3_key[i], g_ex3_cnt[i]);
    for (i = 0; i < PB; i++) if (g_in3_key[i]) fprintf(f, "I3 0x%08lX %lu\n", g_in3_key[i], g_in3_cnt[i]);
    fclose(f);
    logf("PROF> dumped %lu samples to %s", g_samples, path);
}

/* One sample of thread `th` into the given tables. Nothing is allocated or logged while it is suspended. */
static void sample_one(HANDLE th, DWORD *ek, DWORD *ec, DWORD *ik, DWORD *ic, DWORD *count) {
    static BYTE stk[STK_BYTES];
    static DWORD seen[256];
    CONTEXT ctx;
    DWORD eip = 0, esp = 0, n = 0;
    int got = 0, k, j;
    ctx.ContextFlags = CONTEXT_CONTROL;
    if (SuspendThread(th) == (DWORD)-1) return;
    if (GetThreadContext(th, &ctx)) {
        eip = ctx.Eip; esp = ctx.Esp;
        DWORD r = esp ? readable((void *)esp, STK_BYTES) & ~3u : 0;
        if (r >= 512) {   /* memory past a stack top can be released between VirtualQuery and the copy */
            memset(stk, 0, STK_BYTES);
            __try { memcpy(stk, (void *)esp, r); got = 1; } __except (EXCEPTION_EXECUTE_HANDLER) { got = 0; }
        }
    }
    ResumeThread(th);   /* unconditional */
    if (!eip) return;
    (*count)++;
    hit(ek, ec, eip);
    hit(ik, ic, eip);
    seen[n++] = eip;
    if (got) for (k = 0; k < STK_BYTES / 4 && n < 256; k++) {
        DWORD v = ((DWORD *)stk)[k];
        int dup = 0;
        if (v < 0x10000 || !is_retaddr(v)) continue;
        for (j = 0; j < (int)n; j++) if (seen[j] == v) { dup = 1; break; }
        if (dup) continue;
        seen[n++] = v;
        hit(ik, ic, v);
    }
}

/* Find SIMCITY-class threads: a thread whose stack (top 16 KB) holds SIMCITY+0xd0a5. */
static volatile LONG g_finding;
static void find_sim_threads(void) {
    DWORD sc = (DWORD)GetModuleHandleA("SIMCITY.DLL"), want, me = GetCurrentProcessId();
    HANDLE snap;
    THREADENTRY32 te;
    static DWORD buf[4096];
    if (!sc) return;
    if (InterlockedCompareExchange(&g_finding, 1, 0)) return;   /* the profiler and the busy watcher both call this */
    want = sc + 0xd0a5;
    snap = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
    if (snap == INVALID_HANDLE_VALUE) { InterlockedExchange(&g_finding, 0); return; }
    te.dwSize = sizeof(te);
    if (Thread32First(snap, &te)) do {
        HANDLE th;
        CONTEXT ctx;
        DWORD esp = 0, k, len = 0, known = 0, i;
        if (te.th32OwnerProcessID != me || te.th32ThreadID == g_game_tid || te.th32ThreadID == GetCurrentThreadId()) continue;
        for (i = 0; i < (DWORD)g_nsim; i++) if (g_sim_tid[i] == te.th32ThreadID) known = 1;
        if (known || g_nsim >= 32) continue;
        th = OpenThread(THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT | THREAD_QUERY_INFORMATION, FALSE, te.th32ThreadID);
        if (!th) continue;
        ctx.ContextFlags = CONTEXT_CONTROL;
        if (SuspendThread(th) != (DWORD)-1) {
            if (GetThreadContext(th, &ctx)) esp = ctx.Esp;
            len = esp ? readable((void *)esp, sizeof(buf)) & ~3u : 0;
            if (esp && len >= 512) { __try { memcpy(buf, (void *)esp, len); } __except (EXCEPTION_EXECUTE_HANDLER) { len = 0; } }
            else len = 0;
            ResumeThread(th);
        }
        for (k = 0; k < len / 4; k++) if (buf[k] == want) break;
        if (!len || k >= len / 4) {
            /* deep in work the thread-start frame is far below esp: scan the oldest 16 KB of the stack
               instead, from NT_TIB.StackBase (TEB+4), TEB from NtQueryInformationThread(ThreadBasicInformation) */
            typedef LONG (WINAPI *NQIT)(HANDLE, int, void *, ULONG, ULONG *);
            static NQIT nqit;
            DWORD tbi[7] = {0}, base = 0, lo;
            if (!nqit) nqit = (NQIT)GetProcAddress(GetModuleHandleA("ntdll.dll"), "NtQueryInformationThread");
            if (nqit && nqit(th, 0, tbi, sizeof(tbi), NULL) == 0 && tbi[1] && readable((void *)(tbi[1] + 4), 4) == 4)
                base = *(DWORD *)(tbi[1] + 4);
            for (len = sizeof(buf); base && len >= 512; len /= 2) {
                lo = base - len;
                if (readable((void *)lo, len) == len) {
                    __try { memcpy(buf, (void *)lo, len); } __except (EXCEPTION_EXECUTE_HANDLER) { len = 0; }
                    break;
                }
            }
            if (!base || len < 512) len = 0;
            for (k = 0; k < len / 4; k++) if (buf[k] == want) break;
        }
        if (len && k < len / 4) {
            g_sim_tid[g_nsim] = te.th32ThreadID;
            g_sim_th[g_nsim] = th;
            InterlockedIncrement(&g_nsim); InterlockedIncrement(&g_nsim_real);
            logf("SIMTHREAD> thread %lu is a SIMCITY-class thread (SIMCITY+0xd0a5 on its stack)", te.th32ThreadID);
        } else CloseHandle(th);
    } while (Thread32Next(snap, &te));
    CloseHandle(snap);
    InterlockedExchange(&g_finding, 0);
}

static DWORD WINAPI prof_thread(LPVOID p) {
    HANDLE th;
    int it = 0;
    (void)p;
    while (!g_game_tid) Sleep(100);
    th = OpenThread(THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT, FALSE, g_game_tid);
    if (!th) { logf("PROF> OpenThread failed (%lu)", GetLastError()); return 0; }
    SetThreadPriority(GetCurrentThread(), THREAD_PRIORITY_TIME_CRITICAL);
    {   HMODULE wm = LoadLibraryA("winmm.dll");   /* 1 ms timer so Sleep(1) is ~1 ms, not 15.6 */
        if (wm) { UINT (WINAPI *tbp)(UINT) = (UINT (WINAPI *)(UINT))GetProcAddress(wm, "timeBeginPeriod");
                  if (tbp) tbp(1); } }
    prof_reset();
    logf("PROF> sampling thread %lu, %d executable sections", g_game_tid, g_nex);
    for (;;) {
        if (g_profile) {
            int i;
            if (it++ % 2000 == 0 && g_nsim_real < 2) find_sim_threads();   /* every ~2 s until found */
            sample_one(th, g_ex_key, g_ex_cnt, g_in_key, g_in_cnt, &g_samples);
            for (i = 0; i < g_nsim; i++)
                if (g_sim_isw[i]) sample_one(g_sim_th[i], g_ex3_key, g_ex3_cnt, g_in3_key, g_in3_cnt, &g_samples3);
                else sample_one(g_sim_th[i], g_ex2_key, g_ex2_cnt, g_in2_key, g_in2_cnt, &g_samples2);
        }
        Sleep(1);
    }
}

/* ---------------------------------------------------------------- SIM BUSY indicator */
static volatile DWORD g_clk;          /* the clock last seen by the day hook */
static DWORD g_day_imm, g_day_ehp, g_day_cont;

/* Entry of SIMCITY FUN_1000aa4d: its `mov eax, <handler>` / `call _EH_prolog` are replayed here, then back
   at +10. _EH_prolog builds the frame from its own return address and returns to it, so calling it from
   here leaves the same frame the original would have. */
static __declspec(naked) void day_stub(void) {
    __asm {
        mov dword ptr [g_clk], ecx
        lock inc dword ptr [g_days]
        mov eax, dword ptr [g_day_imm]
        call dword ptr [g_day_ehp]
        jmp dword ptr [g_day_cont]
    }
}

static void patch_dayhook(DWORD sc) {
    BYTE *p = (BYTE *)sc + 0xaa4d;
    DWORD old;
    if (p[0] != 0xb8 || *(DWORD *)(p + 1) != sc + 0x11e90 || p[5] != 0xe8) {
        logf("BUSY> SIMCITY+0xaa4d differs from shipped - no day hook, no indicator");
        return;
    }
    g_day_imm = *(DWORD *)(p + 1);
    g_day_ehp = (DWORD)(p + 10) + *(DWORD *)(p + 6);
    g_day_cont = (DWORD)(p + 10);
    if (!VirtualProtect(p, 10, PAGE_EXECUTE_READWRITE, &old)) return;
    p[5] = 0x90; *(DWORD *)(p + 6) = 0x90909090;
    *(DWORD *)(p + 1) = (DWORD)day_stub - (DWORD)(p + 5);
    p[0] = 0xE9;
    FlushInstructionCache(GetCurrentProcess(), p, 10);
    logf("BUSY> day hook at SIMCITY+0xaa4d (EH_prolog 0x%08lX)", g_day_ehp);
}

/* module table for labelling samples */
typedef struct { DWORD b, e; char name[32]; } MODR;
static MODR g_mods[128];
static int  g_nmods;
static void load_mods(void) {
    HANDLE s = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, GetCurrentProcessId());
    MODULEENTRY32 me;
    g_nmods = 0;
    if (s == INVALID_HANDLE_VALUE) return;
    me.dwSize = sizeof(me);
    if (Module32First(s, &me)) do {
        if (g_nmods >= 128) break;
        g_mods[g_nmods].b = (DWORD)me.modBaseAddr;
        g_mods[g_nmods].e = (DWORD)me.modBaseAddr + me.modBaseSize;
        lstrcpynA(g_mods[g_nmods].name, me.szModule, 32);
        g_nmods++;
    } while (Module32Next(s, &me));
    CloseHandle(s);
}
static int mod_index(DWORD a) {
    int i;
    for (i = 0; i < g_nmods; i++) if (a >= g_mods[i].b && a < g_mods[i].e) return i;
    return -1;
}
static int is_system_mod(int i) {
    static const char *sys[] = { "ntdll.dll", "kernel32.dll", "KERNELBASE.dll", "msvcrt.dll", "ucrtbase.dll",
                                 "win32u.dll", "user32.dll", "gdi32.dll", "gdi32full.dll", "winmm.dll", 0 };
    int k;
    if (i < 0) return 1;
    for (k = 0; sys[k]; k++) if (!lstrcmpiA(g_mods[i].name, sys[k])) return 1;
    return 0;
}
/* what the owner reads; other modules show by name */
static const char *mod_label(const char *m) {
    static const char *map[][2] = {
        {"SimTransit.dll", "traffic"}, {"SIMECO.DLL", "pollution/land"}, {"SIMRCI.DLL", "zone growth"},
        {"SIMGEOM.DLL", "map grid"}, {"SIMNTWRK.DLL", "power/water"}, {"SIMSERV.DLL", "services"},
        {"SIMDSTR.DLL", "disasters"}, {"SIMCITY.DLL", "sim core"}, {"SIMVARIABLES.DLL", "city stats"},
        {"STRTSIM.DLL", "street life"}, {"SIMMISC.DLL", "misc"}, {"SIMUTIL.DLL", "sim util"},
        {"SIMADV.DLL", "advisors"}, {"SIMSPR.DLL", "sprites"}, {"SIMDIRT.DLL", "terrain"},
        {"SIMBABLD.DLL", "buildings"}, {0, 0} };
    int k;
    for (k = 0; map[k][0]; k++) if (!lstrcmpiA(m, map[k][0])) return map[k][1];
    return m;
}

/* ---- function names (sc3perf_names.txt: "MODULE RVA SIZE NAME" sorted by module then rva) */
typedef struct { char mod[32]; int lo, hi; } NMOD;
static DWORD *g_nm_rva, *g_nm_size;
static char **g_nm_name;
static int    g_nm_n, g_nm_nmod;
static NMOD   g_nm_mods[64];
static void load_names(void) {
    char path[MAX_PATH], *buf, *p, *end;
    HANDLE f;
    DWORD sz, got = 0;
    int cap = 0;
    _snprintf(path, sizeof(path), "%ssc3perf_names.txt", g_dir);
    f = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    if (f == INVALID_HANDLE_VALUE) { logf("BUSY> no sc3perf_names.txt - chains show module+offset"); return; }
    sz = GetFileSize(f, NULL);
    buf = (char *)HeapAlloc(GetProcessHeap(), 0, sz + 1);
    if (!buf || !ReadFile(f, buf, sz, &got, NULL)) { CloseHandle(f); return; }
    CloseHandle(f);
    buf[got] = 0;
    for (p = buf; *p; p++) if (*p == '\n') cap++;
    g_nm_rva = (DWORD *)HeapAlloc(GetProcessHeap(), 0, cap * 4 + 4);
    g_nm_size = (DWORD *)HeapAlloc(GetProcessHeap(), 0, cap * 4 + 4);
    g_nm_name = (char **)HeapAlloc(GetProcessHeap(), 0, cap * sizeof(char *) + 4);
    if (!g_nm_rva || !g_nm_size || !g_nm_name) return;
    for (p = buf; *p && g_nm_n < cap; p = end + 1) {
        char *mod = p, *rv, *szs, *nm;
        end = strchr(p, '\n');
        if (!end) break;
        *end = 0;
        rv = strchr(mod, ' '); if (!rv) continue; *rv++ = 0;
        szs = strchr(rv, ' '); if (!szs) continue; *szs++ = 0;
        nm = strchr(szs, ' '); if (!nm) continue; *nm++ = 0;
        if (!g_nm_nmod || lstrcmpiA(g_nm_mods[g_nm_nmod - 1].mod, mod)) {
            if (g_nm_nmod >= 64) break;
            lstrcpynA(g_nm_mods[g_nm_nmod].mod, mod, 32);
            g_nm_mods[g_nm_nmod].lo = g_nm_mods[g_nm_nmod].hi = g_nm_n;
            g_nm_nmod++;
        }
        g_nm_rva[g_nm_n] = strtoul(rv, NULL, 16);
        g_nm_size[g_nm_n] = strtoul(szs, NULL, 16);
        g_nm_name[g_nm_n] = nm;
        g_nm_n++;
        g_nm_mods[g_nm_nmod - 1].hi = g_nm_n;
    }
    logf("BUSY> %d function names for %d modules", g_nm_n, g_nm_nmod);
}
/* runtime address -> function: returns its name (or NULL) and its runtime start in *start; *gh = Ghidra address */
static const char *func_of(DWORD addr, DWORD *start, DWORD *gh) {
    int m = mod_index(addr), i, lo, hi;
    DWORD g;
    *start = addr; *gh = 0;
    if (m < 0) return NULL;
    g = addr - g_mods[m].b + (lstrcmpiA(g_mods[m].name, "SC3U.exe") ? 0x10000000 : 0x00400000);
    *gh = g;
    for (i = 0; i < g_nm_nmod; i++) if (!lstrcmpiA(g_nm_mods[i].mod, g_mods[m].name)) break;
    if (i == g_nm_nmod) return NULL;
    lo = g_nm_mods[i].lo; hi = g_nm_mods[i].hi - 1;
    if (hi < lo || g < g_nm_rva[lo]) return NULL;
    while (lo < hi) { int mid = (lo + hi + 1) / 2; if (g_nm_rva[mid] <= g) lo = mid; else hi = mid - 1; }
    if (g - g_nm_rva[lo] > (g_nm_size[lo] ? g_nm_size[lo] : 0x400)) return NULL;
    *start = addr - (g - g_nm_rva[lo]);
    return g_nm_name[lo];
}
static void frame_text(DWORD start, char *out, int cb) {
    DWORD st, gh;
    const char *nm = func_of(start, &st, &gh);
    int m = mod_index(start);
    if (nm) {
        if (!strncmp(nm, "sc3_", 4)) nm += 4;
        _snprintf(out, cb, "%s", nm);
    } else if (m >= 0) _snprintf(out, cb, "%s+%lx", g_mods[m].name, start - g_mods[m].b);
    else _snprintf(out, cb, "%08lx", start);
    out[cb - 1] = 0;
}

/* ---- call chains: function the thread is in + the next two distinct game functions below it */
#define NCH 2048
typedef struct { DWORD f[3]; DWORD cnt; } CHN;
static CHN   g_chn[NCH];
static DWORD g_chn_total;
static void chain_add(const DWORD *f) {
    DWORD h = ((f[0] * 2654435761u) ^ (f[1] * 40503u) ^ f[2]) & (NCH - 1), n;
    g_chn_total++;
    for (n = 0; n < NCH; n++, h = (h + 1) & (NCH - 1)) {
        if (g_chn[h].cnt && g_chn[h].f[0] == f[0] && g_chn[h].f[1] == f[1] && g_chn[h].f[2] == f[2]) { g_chn[h].cnt++; return; }
        if (!g_chn[h].cnt) { memcpy(g_chn[h].f, f, 12); g_chn[h].cnt = 1; return; }
    }
}
static int chain_top(int *idx, int want) {                  /* indexes of the top `want` chains, by count */
    int k, j, n = 0;
    for (k = 0; k < NCH; k++) {
        if (!g_chn[k].cnt) continue;
        for (j = n; j > 0 && g_chn[idx[j - 1]].cnt < g_chn[k].cnt; j--) if (j < want) idx[j] = idx[j - 1];
        if (j < want) { idx[j] = k; if (n < want) n++; }
    }
    return n;
}
static int chain_text(int k, char *out, int cb) {
    char a[40], b[40], c[40];
    frame_text(g_chn[k].f[0], a, 30);
    if (g_chn[k].f[1]) frame_text(g_chn[k].f[1], b, 30); else b[0] = 0;
    if (g_chn[k].f[2]) frame_text(g_chn[k].f[2], c, 30); else c[0] = 0;
    return _snprintf(out, cb, "%3lu%%  %s%s%s%s%s", g_chn_total ? g_chn[k].cnt * 100 / g_chn_total : 0, a,
                     b[0] ? " < " : "", b, c[0] ? " < " : "", c);
}

#define BUSY_LBL 24
static int   g_bl_mod[BUSY_LBL];
static DWORD g_bl_cnt[BUSY_LBL], g_bl_total, g_bl_idle;

/* One sample of a sim thread: the module of EIP, or of the first return address on its stack outside the
   system DLLs. Nothing found (a thread parked in a kernel wait) counts as idle. */
static void busy_sample(HANDLE th) {
    static DWORD stk[1024];
    CONTEXT ctx;
    DWORD eip = 0, esp = 0, len = 0;
    int m, k;
    ctx.ContextFlags = CONTEXT_CONTROL;
    if (SuspendThread(th) == (DWORD)-1) return;
    if (GetThreadContext(th, &ctx)) {
        eip = ctx.Eip; esp = ctx.Esp;
        len = esp ? readable((void *)esp, sizeof(stk)) & ~3u : 0;
        if (esp && len >= 256) { __try { memcpy(stk, (void *)esp, len); } __except (EXCEPTION_EXECUTE_HANDLER) { len = 0; } }
        else len = 0;
    }
    ResumeThread(th);   /* unconditional */
    if (!eip) return;
    g_bl_total++;
    m = mod_index(eip);
    /* parked in a system call (WOW64 ntdll stub: `call edx` just before EIP): a sleeping or waiting thread,
       not work - kept out of the module shares and the call chains */
    if (is_system_mod(m) && readable((void *)(eip - 2), 2) == 2 && *(WORD *)(eip - 2) == 0xD2FF) { g_bl_idle++; return; }
    if (is_system_mod(m)) {
        /* heap and copies in ntdll/msvcrt are charged to the game module that called them; whether the
           thread is working at all is decided from its CPU time, not from here */
        for (m = -1, k = 0; k < (int)(len / 4); k++) {
            int mi;
            if (stk[k] < 0x10000 || !is_retaddr(stk[k])) continue;
            mi = mod_index(stk[k]);
            if (!is_system_mod(mi)) { m = mi; break; }
        }
    }
    if (m < 0) { g_bl_idle++; return; }
    {   /* call chain: EIP's function if it is game code, then the next distinct game functions on the stack */
        DWORD f[3] = {0, 0, 0}, st, gh;
        int nf = 0, self = mod_index((DWORD)g_self);
        if (!is_system_mod(mod_index(eip)) && mod_index(eip) != self) { func_of(eip, &st, &gh); f[nf++] = st; }
        for (k = 0; k < (int)(len / 4) && nf < 3; k++) {
            int mi;
            if (stk[k] < 0x10000 || !is_retaddr(stk[k])) continue;
            mi = mod_index(stk[k]);
            if (is_system_mod(mi) || mi == self) continue;
            func_of(stk[k], &st, &gh);
            if (nf && f[nf - 1] == st) continue;
            f[nf++] = st;
        }
        if (nf) chain_add(f);
    }
    for (k = 0; k < BUSY_LBL; k++) {
        if (g_bl_cnt[k] && g_bl_mod[k] == m) { g_bl_cnt[k]++; return; }
        if (!g_bl_cnt[k]) { g_bl_mod[k] = m; g_bl_cnt[k] = 1; return; }
    }
}

static unsigned __int64 sim_cpu_100ns(void) {
    unsigned __int64 sum = 0;
    int i;
    for (i = 0; i < g_nsim; i++) {
        FILETIME c, e, k, u;
        if (GetThreadTimes(g_sim_th[i], &c, &e, &k, &u))
            sum += ((unsigned __int64)k.dwHighDateTime << 32 | k.dwLowDateTime) +
                   ((unsigned __int64)u.dwHighDateTime << 32 | u.dwLowDateTime);
    }
    return sum;
}

static void busy_set(const char *s) {
    EnterCriticalSection(&g_busycs);
    lstrcpynA(g_busy_text, s, sizeof(g_busy_text));
    LeaveCriticalSection(&g_busycs);
}

static DWORD WINAPI busy_thread(LPVOID p) {
    LONG seen_days = -1;
    double day_t = now_ms(), last_find = -1e9, stall_t0 = 0, last_text = 0, last_log = 0, cpu_t0 = 0;
    unsigned __int64 cpu0 = 0;
    int stalled = 0;
    DWORD exe = (DWORD)GetModuleHandleA(NULL);
    (void)p;
    load_mods();
    exec_ranges();
    load_names();
    logf("BUSY> watcher running");
    for (;;) {
        double t;
        DWORD clk = g_clk, city = 0, app;
        LONG days = g_days, msday = 0, speed = 0, cpause = 0, upause = 0, hold = 0;
        int eligible;
        Sleep(stalled ? 5 : 50);
        t = now_ms();
        if (days != seen_days) {
            static double dl[1024], dl_last;
            static int ndl;
            static double dl_t0;
            /* own timestamp: day_t is reset while paused or minimized (stall detection), which made days read 50 ms */
            if (seen_days >= 0 && dl_last > 0 && ndl < 1024 && days - seen_days == 1) dl[ndl++] = t - dl_last;
            dl_last = t;
            if (!dl_t0) dl_t0 = t;
            if (t - dl_t0 >= 60000 && ndl) {
                int a, b2;
                double sum = 0;
                for (a = 1; a < ndl; a++) { double v = dl[a]; for (b2 = a; b2 > 0 && dl[b2 - 1] > v; b2--) dl[b2] = dl[b2 - 1]; dl[b2] = v; }
                for (a = 0; a < ndl; a++) sum += dl[a];
                logf("DAYS> %d days in %.0f s: mean %.0f ms, median %.0f, p90 %.0f, max %.0f (nominal %ld ms)", ndl,
                     (t - dl_t0) / 1000.0, sum / ndl, dl[ndl / 2], dl[ndl * 9 / 10], dl[ndl - 1],
                     (clk && readable((void *)(clk + 0x60), 4) == 4) ? *(LONG *)(clk + 0x60) : 0L);
                ndl = 0; dl_t0 = t;
            }
            seen_days = days; day_t = t;
        }
        if (clk && !IsBadReadPtr((void *)clk, 0x70)) {
            speed = *(LONG *)(clk + 0x50); cpause = *(LONG *)(clk + 0x54); msday = *(LONG *)(clk + 0x60);
        }
        app = !IsBadReadPtr((void *)(exe + 0xfa86c), 4) ? *(DWORD *)(exe + 0xfa86c) : 0;
        if (app && !IsBadReadPtr((void *)(app + 0x48), 4)) city = *(DWORD *)(app + 0x48);
        if (city && !IsBadReadPtr((void *)(city + 0x140), 12)) { upause = *(LONG *)(city + 0x140); hold = *(LONG *)(city + 0x144); }
        eligible = clk && city && speed > 120 && msday > 0 && msday < 60000 && !upause && !hold && !g_iconic;
        if (!eligible || t - day_t < msday + 1000.0) {
            if (!eligible) day_t = t;            /* paused on purpose: the date is not expected to move */
            if (stalled) {
                if (eligible) {
                    int top[8], nt = chain_top(top, 8), k;
                    char ct[200];
                    logf("BUSY> date moved again after %.1f s; top call chains (%lu samples):", (t - stall_t0) / 1000.0, g_chn_total);
                    for (k = 0; k < nt; k++) { chain_text(top[k], ct, sizeof(ct)); ct[sizeof(ct) - 1] = 0; logf("BUSY>   %s", ct); }
                }
                stalled = 0;
                busy_set("");
            }
            continue;
        }
        if (!stalled) {
            stalled = 1;
            stall_t0 = day_t;
            memset(g_bl_cnt, 0, sizeof(g_bl_cnt));
            g_bl_total = g_bl_idle = 0;
            memset(g_chn, 0, sizeof(g_chn));
            g_chn_total = 0;
            load_mods();
            exec_ranges();
            cpu0 = sim_cpu_100ns(); cpu_t0 = t;
            last_text = 0;
            last_log = t;
            logf("BUSY> date stopped: %.0f ms since the last day, %ld ms per day, clock pause %ld", t - day_t, msday, cpause);
        }
        if (g_nsim_real == 0 && t - last_find > 2000) { find_sim_threads(); last_find = t; cpu0 = sim_cpu_100ns(); cpu_t0 = t; }
        {   /* sample only a thread that ran since its last look (cycle counter moved): a parked sim thread's
               stack also holds SIMCITY frames and would read as "sim core" */
            typedef BOOL (WINAPI *QTCT)(HANDLE, ULONG64 *);   /* Vista+, resolved at runtime (built for 0x0501) */
            static QTCT qtct;
            static ULONG64 cyc[32];
            int i;
            if (!qtct) qtct = (QTCT)GetProcAddress(GetModuleHandleA("kernel32.dll"), "QueryThreadCycleTime");
            for (i = 0; i < g_nsim && i < 32; i++) {
                ULONG64 c = 0;
                if (!qtct || (qtct(g_sim_th[i], &c) && c != cyc[i])) { cyc[i] = c; busy_sample(g_sim_th[i]); }
            }
        }
        if (t - last_text >= 250) {
            char line[512];
            double late = (t - day_t) / 1000.0, wall = t - cpu_t0;
            double cpu = (wall > 50 && g_nsim) ? (double)(sim_cpu_100ns() - cpu0) / 10000.0 / wall * 100.0 : 0;
            int a = -1, b = -1, k, n;
            DWORD busy_n = g_bl_total - g_bl_idle;
            for (k = 0; k < BUSY_LBL; k++) {
                if (!g_bl_cnt[k]) continue;
                if (a < 0 || g_bl_cnt[k] > g_bl_cnt[a]) { b = a; a = k; }
                else if (b < 0 || g_bl_cnt[k] > g_bl_cnt[b]) b = k;
            }
            last_text = t;
            if (!g_nsim) {
                n = _snprintf(line, sizeof(line), " DATE STOPPED %.1f s  (sim thread not found yet) ", late);
            } else if (wall > 1000 && cpu < 25) {
                n = _snprintf(line, sizeof(line), " DATE STOPPED %.1f s  sim idle, clock held%s ", late,
                              cpause ? " (a dialog open?)" : "");
            } else {
                n = _snprintf(line, sizeof(line), " SIM BUSY %.1f s  CPU %.0f%%", late, cpu > 100 ? 100.0 : cpu);
                if (a >= 0 && busy_n && n > 0)
                    n += _snprintf(line + n, sizeof(line) - n, "  %s %lu%%", mod_label(g_mods[g_bl_mod[a]].name),
                                   g_bl_cnt[a] * 100 / busy_n);
                if (b >= 0 && busy_n && n > 0 && g_bl_cnt[b] * 10 >= busy_n)
                    n += _snprintf(line + n, sizeof(line) - n, "  %s %lu%%", mod_label(g_mods[g_bl_mod[b]].name),
                                   g_bl_cnt[b] * 100 / busy_n);
                if (n > 0 && n < (int)sizeof(line) - 2) { line[n++] = ' '; line[n] = 0; }
                {   int top[2], nt = chain_top(top, 2), k;
                    for (k = 0; k < nt && n > 0 && n < (int)sizeof(line) - 120; k++) {
                        line[n++] = '\n'; line[n++] = ' ';
                        n += chain_text(top[k], line + n, 110);
                        line[n++] = ' '; line[n] = 0;
                    }
                }
            }
            line[sizeof(line) - 1] = 0;
            busy_set(line);
            if (t - last_log >= 5000) {
                char one[512], *q;
                lstrcpynA(one, line, sizeof(one));
                for (q = one; *q; q++) if (*q == '\n') *q = '|';
                logf("BUSY>%s", one);
                last_log = t;
            }
        }
    }
}

/* ---------------------------------------------------------------- stats / control thread */
static void read_cmd(void) {
    char path[MAX_PATH], buf[128];
    FILE *f;
    _snprintf(path, sizeof(path), "%ssc3perf.cmd", g_dir);
    f = fopen(path, "r");
    if (!f) return;
    buf[0] = 0;
    fgets(buf, sizeof(buf), f);
    fclose(f);
    DeleteFileA(path);
    buf[strcspn(buf, "\r\n")] = 0;
    if (!strcmp(buf, "reset")) { prof_reset(); logf("CMD> profile reset"); }
    else if (!strncmp(buf, "dump ", 5)) prof_dump(buf + 5);
    else if (!strcmp(buf, "profile on")) { g_profile = 1; logf("CMD> profiling on"); }
    else if (!strcmp(buf, "profile off")) { g_profile = 0; logf("CMD> profiling off"); }
    else if (!strncmp(buf, "mark ", 5)) logf("MARK> %s", buf + 5);
    else if (!strncmp(buf, "busytest", 8)) {   /* test aid: put text on the busy line ("busytest" alone clears it) */
        busy_set(buf[8] == ' ' ? buf + 9 : "");
        logf("CMD> busy line test text '%s'", buf[8] == ' ' ? buf + 9 : "");
    }
    else logf("CMD> unknown '%s'", buf);
}

static DWORD WINAPI stats_thread(LPVOID p) {
    double t_last = now_ms();
    int tick = 0;
    (void)p;
    logf("CSV,t_s,fps,frame_ms_avg,frame_ms_max,present_ms,blt_n,blt_ms,bltfast_n,bltfast_ms,lock_n,lock_ms,client_w,client_h,wait_ms,cap,va_used_mb,private_mb,largest_free_mb,days");
    for (;;) {
        RECT cr;
        Sleep(250);
        if (g_hwnd && GetClientRect(g_hwnd, &cr)) { g_cw = cr.right; g_ch = cr.bottom; }
        if (g_hwnd) {
            LONG ic = IsIconic(g_hwnd) ? 1 : 0;
            if (ic != g_iconic) { logf("CAP> window %s", ic ? "minimized - idling" : "restored"); InterlockedExchange(&g_iconic, ic); }
        }
        if (tick % 4 == 0) {   /* cap: fixed, or the refresh rate of the monitor the window is on */
            LONG c = g_cap > 0 ? g_cap : 0;
            if (g_cap < 0 && g_hwnd) {
                MONITORINFOEXA mi;
                DEVMODEA dm;
                mi.cbSize = sizeof(mi);
                memset(&dm, 0, sizeof(dm)); dm.dmSize = sizeof(dm);
                if (GetMonitorInfoA(MonitorFromWindow(g_hwnd, MONITOR_DEFAULTTONEAREST), (MONITORINFO *)&mi) &&
                    EnumDisplaySettingsA(mi.szDevice, ENUM_CURRENT_SETTINGS, &dm) && dm.dmDisplayFrequency > 1)
                    c = (LONG)dm.dmDisplayFrequency;
                else c = 60;   /* refresh unknown: a safe default */
            }
            if (c != g_cap_eff) { logf("CAP> frame cap now %ld fps (setting %d)", c, g_cap); InterlockedExchange(&g_cap_eff, c); }
        }
        read_cmd();
        if (g_mt > 0 && g_smooth && tick && tick % 240 == 0 && g_sq)
        {   int k;
            logf("TRAFFIC_SMOOTH> %ld trips routed in the background, queue %ld, %ld drains (sim thread waited %.0f ms), %ld faults",
                 g_sq_jobs, g_sq_tail - g_sq_head, g_sq_drains, g_sq_drain_ms, g_mt_faults);
            for (k = 0; k < 16 && g_dr_cnt[k]; k++) {
                int mi = mod_index(g_dr_ret[k]);
                logf("TRAFFIC_SMOOTH>   drain asked by %s+0x%lx: %lu", mi >= 0 ? g_mods[mi].name : "stub",
                     mi >= 0 ? g_dr_ret[k] - g_mods[mi].b : g_dr_ret[k], g_dr_cnt[k]);
            }
        }
        if (g_mt > 0 && tick && tick % 240 == 0 && g_mt_batches)
            logf("TRAFFIC_MT> %ld batches, %ld trips, %.0f ms routing (%.2f ms per trip), sim thread waited %.0f ms, %ld faults, %ld lock-free grid reads",
                 g_mt_batches, g_mt_jobs, g_mt_ms, g_mt_jobs ? g_mt_ms / g_mt_jobs : 0.0, g_mt_wait_ms, g_mt_faults, g_geom_fast);
        if (g_listfind && tick && tick % 240 == 0)
            logf("LIST_FIND> hits %ld walks %ld builds %ld drops %ld (table %lu slots)", g_lf_hits, g_lf_walks,
                 g_lf_builds, g_lf_drops, g_lfcap);
        if (g_locklog && !(tick % 40)) ll_dump();   /* LOCKLOG: every 10 s (the loop ticks every 250 ms) */
        if (++tick % 4) continue;
        {
            double t = now_ms(), dt = t - t_last;
            LONG fr = g_frames, bn = g_blt_n, fn = g_bltfast_n, ln = g_lock_n;
            double bm = g_blt_ms, fm = g_bltfast_ms, lm = g_lock_ms, pm = g_present_ms, mx = g_frame_max, wm = g_wait_ms;
            double fps = fr * 1000.0 / dt;
            g_frames = 0; g_blt_n = 0; g_bltfast_n = 0; g_lock_n = 0;
            g_blt_ms = 0; g_bltfast_ms = 0; g_lock_ms = 0; g_present_ms = 0; g_frame_max = 0; g_wait_ms = 0;
            t_last = t;
            if (!g_vt) continue;
            {   /* address space: the game is NOT large-address-aware (2 GB user space) */
                MEMORY_BASIC_INFORMATION mbi;
                BYTE *a = (BYTE *)0x10000;
                SIZE_T used = 0, priv = 0, big = 0;
                while (a < (BYTE *)0x7FFF0000 && VirtualQuery(a, &mbi, sizeof(mbi))) {
                    if (mbi.State == MEM_FREE) { if (mbi.RegionSize > big) big = mbi.RegionSize; }
                    else { used += mbi.RegionSize; if (mbi.Type == MEM_PRIVATE && mbi.State == MEM_COMMIT) priv += mbi.RegionSize; }
                    a = (BYTE *)mbi.BaseAddress + mbi.RegionSize;
                }
                g_va_used = (LONG)(used >> 20); g_va_priv = (LONG)(priv >> 20); g_va_free = (LONG)(big >> 20);
            }
            logf("CSV,%.1f,%.1f,%.1f,%.1f,%.1f,%ld,%.1f,%ld,%.1f,%ld,%.1f,%ld,%ld,%.1f,%d,%ld,%ld,%ld,%ld",
                 t / 1000.0, fps, fr ? dt / fr : 0.0, mx, pm, bn, bm, fn, fm, ln, lm, g_cw, g_ch, wm, (int)g_cap_eff,
                 g_va_used, g_va_priv, g_va_free, g_days);
            _snprintf(g_text, sizeof(g_text),
                      " %3.0f fps   %4.1f ms/frame   worst %3.0f ms   mem %ld MB ",
                      fps, fr ? (dt - wm) / fr : 0.0, mx, g_va_used);
            g_text[sizeof(g_text) - 1] = 0;
        }
    }
}

/* ---------------------------------------------------------------- PERFPREFS (2026-10-12)
   The game's Preferences dialog (sc3resize HUDOPT) shows two checkboxes, "Ver FPS" and "Ver perfilador", and
   reaches us through these two exports (GetProcAddress: either DLL works without the other). They only change
   what draw_overlay paints, which it reads on every final present, so a change shows on the next frame. Set
   writes the choice into perf.ini beside this DLL: overlay= (the FPS line, existing key) and busy_show= (the red
   busy lines; busy= stays the switch for the detector itself, its day hook and its log). Bits: 1 FPS line shown,
   2 busy lines shown, 4 busy detector running (read only), 0x100 always set. */
static void perf_ini_put(const char *key, int v) {
    char ini[MAX_PATH], val[16];
    _snprintf(ini, sizeof(ini), "%sperf.ini", g_dir);
    _snprintf(val, sizeof(val), "%d", v);
    WritePrivateProfileStringA("perf", key, val, ini);
}

__declspec(dllexport) int sc3perf_show_get(void) {
    return 0x100 | (g_overlay ? 1 : 0) | (g_busy_show ? 2 : 0) | (g_busy ? 4 : 0);
}

__declspec(dllexport) int sc3perf_show_set(int bits) {
    int fps = (bits & 1) ? 1 : 0, busy = (bits & 2) ? 1 : 0, was = sc3perf_show_get();
    g_overlay = fps;
    g_busy_show = busy;
    perf_ini_put("overlay", fps);
    perf_ini_put("busy_show", busy);
    logf("PERFPREFS> from Preferences: FPS line %d, busy lines %d (was %d/%d), saved to perf.ini%s", fps, busy,
         was & 1, (was >> 1) & 1, g_busy ? "" : " (busy=0: the detector is off, there is nothing to show)");
    return sc3perf_show_get();
}

/* ---------------------------------------------------------------- startup */
static int cfg(const char *key, int def) {
    char ini[MAX_PATH], v[32];
    int r;
    _snprintf(ini, sizeof(ini), "%sperf.ini", g_dir);
    r = GetPrivateProfileIntA("perf", key, def, ini);
    {   char env[64];
        _snprintf(env, sizeof(env), "SC3PERF_%s", key);
        _strupr(env);
        if (GetEnvironmentVariableA(env, v, sizeof(v))) r = atoi(v);
    }
    return r;
}

static DWORD WINAPI watcher(LPVOID p) {
    DWORD gz = 0;
    int ms = 0;
    (void)p;
    while (!(gz = (DWORD)GetModuleHandleA("GZGraphicD.dll")) && ms++ < 300000) Sleep(1);
    if (!gz) { logf("GZGraphicD never loaded"); return 0; }
    if (g_sysmem) patch_sysmem(gz);
    while (!g_hwnd) { EnumWindows(find_wnd, 0); if (!g_hwnd) Sleep(100); }
    g_game_tid = GetWindowThreadProcessId(g_hwnd, NULL);
    logf("WINDOW> 0x%08lX, game thread %lu", (DWORD)g_hwnd, g_game_tid);
    while (!*(DWORD *)(gz + 0x6cd54)) Sleep(50);   /* the game's IDirectDraw exists */
    install_dd_hooks();
    CreateThread(NULL, 0, stats_thread, NULL, 0, NULL);
    CreateThread(NULL, 0, prof_thread, NULL, 0, NULL);
    return 0;
}

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID r) {
    (void)r;
    if (reason == DLL_PROCESS_ATTACH) {
        char path[MAX_PATH], *sl;
        if (!sc3mods_guard(inst, "sc3perf")) return TRUE;   /* not our loader: stay inert (sc3mods_guard.h) */
        g_self = inst;
        DisableThreadLibraryCalls(inst);
        QueryPerformanceFrequency(&g_qf);
        QueryPerformanceCounter(&g_t0);
        InitializeCriticalSection(&g_logcs);
        GetModuleFileNameA(inst, g_dir, sizeof(g_dir));
        sl = strrchr(g_dir, '\\'); if (sl) sl[1] = 0;
        if (!GetEnvironmentVariableA("SC3PERF_LOG", path, sizeof(path)))
            _snprintf(path, sizeof(path), "%ssc3perf.log", g_dir);
        g_log = CreateFileA(path, GENERIC_WRITE, FILE_SHARE_READ, NULL, CREATE_ALWAYS, 0, NULL);
        g_overlay = cfg("overlay", 1);
        g_profile = cfg("profile", 0);
        g_sysmem  = cfg("sysmem", 0);
        g_cap     = cfg("fps_cap", -1);
        g_clock_ms = cfg("clock_ms", 50);
        if (g_clock_ms < 0 || g_clock_ms > 1000) g_clock_ms = 0;
        g_spr_budget = (float)cfg("spr_budget", 40);
        g_spr_sleep_us = cfg("spr_sleep_us", 1000);
        if (g_spr_sleep_us < 0 || g_spr_sleep_us > 20000) g_spr_sleep_us = 1000;
        g_spr_follow = cfg("spr_follow", 1);
        g_trclear = cfg("transit_clear", 1);
        g_fastftol = cfg("fast_ftol", 1);
        g_fastceil = cfg("fast_ceil", 1);
        g_sprref = cfg("spr_refcount", 1);
        g_layerref = cfg("layer_refcount", 1);
        g_strtref = cfg("strtsim_refcount", 1);
        g_strtref_all = cfg("strtsim_refcount_all", 1);
        g_sgref = cfg("simgroup_refcount", 1);
        g_resref_spr = cfg("res_refcount_simspr", 1);
        g_resref_gz = cfg("res_refcount_gzres", 1);
        g_strtref_ecx = cfg("strtsim_refcount_ecx", 1);
        g_scnref = cfg("scenario_refcount", 1);
        g_le1ref_ui = cfg("le1_refcount_simui", 1);
        g_reloadshadow = cfg("reload_shadow", 1);
        g_busy = cfg("busy", 1);
        g_busy_show = cfg("busy_show", 1);
        g_locklog = cfg("locklog", 0);   /* LOCKLOG diag, SC3PERF_LOCKLOG=1 */
        g_listcount = cfg("list_count", 1);
        g_listfind = cfg("list_find", 1);
        {   /* default 8 workers (owner call 2026-10-09), never more than the logical processors minus one */
            SYSTEM_INFO si;
            int cap;
            GetSystemInfo(&si);
            cap = (int)si.dwNumberOfProcessors - 1;
            g_mt = cfg("traffic_mt", 8);
            if (g_mt > cap) g_mt = cap > 0 ? cap : 0;
            if (g_mt > MT_MAXW) g_mt = MT_MAXW;
        }
        g_mt_batch = cfg("traffic_mt_batch", 4096);
        g_mtlocks = cfg("mt_locks", 1);
        g_mt_async = cfg("traffic_mt_async", 0);
        g_smooth = cfg("traffic_mt_smooth", 1);
        g_geomheld = cfg("geom_held", 0);
        if (g_mt_batch < 64) g_mt_batch = 64;
        InitializeCriticalSection(&g_busycs);
        InitializeCriticalSection(&g_llcs);
        logf("sc3perf loaded: overlay=%d profile=%d sysmem=%d fps_cap=%d clock_ms=%d spr_budget=%.0f spr_sleep_us=%d busy=%d busy_show=%d",
             g_overlay, g_profile, g_sysmem, g_cap, g_clock_ms, g_spr_budget, g_spr_sleep_us, g_busy, g_busy_show);
        CreateThread(NULL, 0, watcher, NULL, 0, NULL);
        if (g_clock_ms || g_busy || g_listcount || g_listfind) CreateThread(NULL, 0, clock_watcher, NULL, 0, NULL);
        if (g_spr_budget > 0 || g_spr_follow || g_sprref) CreateThread(NULL, 0, spr_watcher, NULL, 0, NULL);
        if (g_sprref) CreateThread(NULL, 0, ss_watcher, NULL, 0, NULL);
        if (g_layerref) CreateThread(NULL, 0, rc_watcher, NULL, 0, NULL);
        if (g_strtref) CreateThread(NULL, 0, st_watcher, NULL, 0, NULL);
        if (g_sgref) CreateThread(NULL, 0, sg_watcher, NULL, 0, NULL);
        if (g_resref_spr || g_resref_gz || g_strtref_ecx || g_scnref || g_le1ref_ui) CreateThread(NULL, 0, rr_watcher, NULL, 0, NULL);
        if (g_trclear || g_mt > 0 || g_fastceil || g_sprref) CreateThread(NULL, 0, tr_watcher, NULL, 0, NULL);
        if (g_fastftol) patch_ftol();      /* msvcrt is loaded before any mod; patch before the game converts a float */
    }
    return TRUE;
}
