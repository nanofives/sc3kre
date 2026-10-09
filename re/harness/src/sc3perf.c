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
 * Config: perf.ini beside the DLL, [perf] overlay=1 profile=0 sysmem=0 clock_ms=50 spr_budget=40
 * spr_sleep_us=1000 spr_follow=1 transit_clear=1 fast_ftol=1; env SC3PERF_OVERLAY /
 * SC3PERF_PROFILE / SC3PERF_SYSMEM / SC3PERF_CLOCK_MS override; SC3PERF_LOG=<path> (default sc3perf.log beside the DLL).
 */
#include <windows.h>
#include <tlhelp32.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

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
static int     g_trclear = 1, g_fastftol = 1;
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
static volatile LONG g_in_present;

/* Draw the counter INTO the frame (the present's source surface) right before it goes out, so the next
   present cannot cover it. IDirectDrawSurface GetDC vt+0x44, ReleaseDC vt+0x68. */
/* OVERLAY SAVE/RESTORE (owner hand test 2026-10-08: the counter left a trail down the screen while
   scrolling, and tore the city under it). The game scrolls by shifting the pixels already in its back
   buffer and redrawing only the strip that came into view, so anything drawn into that buffer is carried
   along. So: copy the pixels under the counter out of the source surface, draw, present, copy them back.
   The game never sees a changed back buffer. DDSURFACEDESC v1: height +0x08, width +0x0c, pitch +0x10,
   bits +0x24, pixel format +0x48 (RGB bit count at +0x54). Lock = the real (next) Lock, Unlock vt+0x80. */
#define OV_W 400
#define OV_H 18
static BYTE  g_ov_save[OV_W * 4 * OV_H];
static int   g_ov_saved;
static LONG  g_ov_x, g_ov_y, g_ov_w, g_ov_h, g_ov_bpp;

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
        g_ov_w = g_ov_x + OV_W <= sw ? OV_W : sw - g_ov_x;
        g_ov_h = g_ov_y + OV_H <= sh ? OV_H : sh - g_ov_y;
    }
    rowbytes = g_ov_w * g_ov_bpp;
    if (bits && g_ov_bpp && g_ov_w > 0 && g_ov_h > 0)
        for (y = 0; y < g_ov_h; y++) {
            BYTE *row = bits + (g_ov_y + y) * pitch + g_ov_x * g_ov_bpp, *buf = g_ov_save + y * OV_W * 4;
            if (restore) memcpy(row, buf, rowbytes); else memcpy(buf, row, rowbytes);
        }
    ((HRESULT (WINAPI *)(void *, void *))vt[0x80 / 4])(src, NULL);
    return bits && g_ov_bpp && g_ov_w > 0 && g_ov_h > 0;
}

static void draw_overlay(void *src, RECT *sr) {
    HDC dc = NULL;
    HGDIOBJ of;
    DWORD *vt;
    if (!src || IsBadReadPtr(src, 4)) return;
    vt = *(DWORD **)src;
    g_ov_x = sr ? sr->left : 0; g_ov_y = sr ? sr->top : 0;
    g_ov_saved = ov_copy(src, 0);
    if (!g_ov_saved) return;   /* never draw what we cannot take back */
    if (((HRESULT (WINAPI *)(void *, HDC *))vt[0x44 / 4])(src, &dc) != 0 || !dc) { g_ov_saved = 0; return; }
    of = SelectObject(dc, GetStockObject(ANSI_FIXED_FONT));
    SetBkMode(dc, OPAQUE);
    SetBkColor(dc, RGB(0, 0, 0));
    SetTextColor(dc, RGB(255, 255, 0));
    TextOutA(dc, (sr ? sr->left : 0) + 4, (sr ? sr->top : 0) + 4, g_text, (int)strlen(g_text));
    SelectObject(dc, of);
    ((HRESULT (WINAPI *)(void *, HDC))vt[0x68 / 4])(src, dc);
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
        if (g_overlay) draw_overlay(src, sr && !IsBadReadPtr(sr, sizeof(RECT)) ? sr : NULL);
    }
    a = now_ms();
    hr = g_next_blt(self, dr, src, sr, fl, fx);
    if (final && g_ov_saved) { ov_copy(src, 1); g_ov_saved = 0; }   /* give the game its pixels back */
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
static HRESULT WINAPI perf_lock(void *self, RECT *r, void *desc, DWORD fl, HANDLE ev) {
    double a = now_ms();
    HRESULT hr = g_next_lock(self, r, desc, fl, ev);
    g_lock_n++;
    g_lock_ms += now_ms() - a;
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

/* Replaces the call to FUN_1000a5cb in the trip router: thiscall(grid), one stack arg (byte *value), ret 4. */
static void __fastcall tr_clear(BYTE *grid, void *edx, BYTE *val) {
    ULONG_PTR n = sizeof(g_tr_addrs) / sizeof(g_tr_addrs[0]), i;
    DWORD gran = 0;
    (void)edx;
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
static void __fastcall tr_dtor(DWORD *g, void *edx) {
    TR_DELETE del = (TR_DELETE)(g_tr_base + 0x1806f);
    int i;
    (void)edx;
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

static DWORD WINAPI tr_watcher(LPVOID p) {
    DWORD st = 0;
    int ms = 0;
    (void)p;
    while (!(st = (DWORD)GetModuleHandleA("SimTransit.dll")) && ms++ < 300000) Sleep(1);
    if (st) patch_trclear(st); else logf("TRANSIT_CLEAR> SimTransit.dll never loaded");
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
    return 0;
}

static DWORD WINAPI clock_watcher(LPVOID p) {
    DWORD sc = 0;
    int ms = 0;
    (void)p;
    while (!(sc = (DWORD)GetModuleHandleA("SIMCITY.DLL")) && ms++ < 300000) Sleep(1);
    if (sc) patch_clock(sc); else logf("SIMCLOCK> SIMCITY.DLL never loaded");
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
static DWORD g_sim_tid[8];
static HANDLE g_sim_th[8];
static volatile LONG g_nsim;
static DWORD g_exb[64], g_exe[64];
static int   g_nex;

static void exec_ranges(void) {
    HANDLE s = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, GetCurrentProcessId());
    MODULEENTRY32 me;
    g_nex = 0;
    if (s == INVALID_HANDLE_VALUE) return;
    me.dwSize = sizeof(me);
    if (Module32First(s, &me)) do {
        DWORD h = (DWORD)me.modBaseAddr, e = *(DWORD *)(h + 0x3c);
        WORD ns = *(WORD *)(h + e + 6), opt = *(WORD *)(h + e + 0x14), k;
        DWORD sec = h + e + 0x18 + opt;
        for (k = 0; k < ns && g_nex < 64; k++) {
            DWORD sh = sec + (DWORD)k * 40;
            if (*(DWORD *)(sh + 0x24) & 0x20000000) {
                g_exb[g_nex] = h + *(DWORD *)(sh + 0x0c);
                g_exe[g_nex] = g_exb[g_nex] + *(DWORD *)(sh + 0x08);
                g_nex++;
            }
        }
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
    g_samples = 0; g_samples2 = 0; g_overflow = 0;
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
    fprintf(f, "# sc3perf profile tag=%s samples=%lu overflow=%lu tid=%lu samples2=%lu simthreads=%ld\n",
            tag, g_samples, g_overflow, g_game_tid, g_samples2, g_nsim);
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
        if (esp && !IsBadReadPtr((void *)esp, STK_BYTES)) { memcpy(stk, (void *)esp, STK_BYTES); got = 1; }
        else if (esp && !IsBadReadPtr((void *)esp, 512)) { memset(stk, 0, STK_BYTES); memcpy(stk, (void *)esp, 512); got = 1; }
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
static void find_sim_threads(void) {
    DWORD sc = (DWORD)GetModuleHandleA("SIMCITY.DLL"), want, me = GetCurrentProcessId();
    HANDLE snap;
    THREADENTRY32 te;
    static DWORD buf[4096];
    if (!sc) return;
    want = sc + 0xd0a5;
    snap = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
    if (snap == INVALID_HANDLE_VALUE) return;
    te.dwSize = sizeof(te);
    if (Thread32First(snap, &te)) do {
        HANDLE th;
        CONTEXT ctx;
        DWORD esp = 0, k, len = 0, known = 0, i;
        if (te.th32OwnerProcessID != me || te.th32ThreadID == g_game_tid || te.th32ThreadID == GetCurrentThreadId()) continue;
        for (i = 0; i < (DWORD)g_nsim; i++) if (g_sim_tid[i] == te.th32ThreadID) known = 1;
        if (known || g_nsim >= 8) continue;
        th = OpenThread(THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT, FALSE, te.th32ThreadID);
        if (!th) continue;
        ctx.ContextFlags = CONTEXT_CONTROL;
        if (SuspendThread(th) != (DWORD)-1) {
            if (GetThreadContext(th, &ctx)) esp = ctx.Esp;
            for (len = sizeof(buf); len >= 512 && esp && IsBadReadPtr((void *)esp, len); len /= 2) ;
            if (esp && len >= 512) memcpy(buf, (void *)esp, len); else len = 0;
            ResumeThread(th);
        }
        for (k = 0; k < len / 4; k++) if (buf[k] == want) break;
        if (len && k < len / 4) {
            g_sim_tid[g_nsim] = te.th32ThreadID;
            g_sim_th[g_nsim] = th;
            InterlockedIncrement(&g_nsim);
            logf("SIMTHREAD> thread %lu is a SIMCITY-class thread (SIMCITY+0xd0a5 on its stack)", te.th32ThreadID);
        } else CloseHandle(th);
    } while (Thread32Next(snap, &te));
    CloseHandle(snap);
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
            if (it++ % 2000 == 0 && g_nsim < 2) find_sim_threads();   /* every ~2 s until found */
            sample_one(th, g_ex_key, g_ex_cnt, g_in_key, g_in_cnt, &g_samples);
            for (i = 0; i < g_nsim; i++)
                sample_one(g_sim_th[i], g_ex2_key, g_ex2_cnt, g_in2_key, g_in2_cnt, &g_samples2);
        }
        Sleep(1);
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
    else logf("CMD> unknown '%s'", buf);
}

static DWORD WINAPI stats_thread(LPVOID p) {
    double t_last = now_ms();
    int tick = 0;
    (void)p;
    logf("CSV,t_s,fps,frame_ms_avg,frame_ms_max,present_ms,blt_n,blt_ms,bltfast_n,bltfast_ms,lock_n,lock_ms,client_w,client_h,wait_ms,cap");
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
            logf("CSV,%.1f,%.1f,%.1f,%.1f,%.1f,%ld,%.1f,%ld,%.1f,%ld,%.1f,%ld,%ld,%.1f,%d",
                 t / 1000.0, fps, fr ? dt / fr : 0.0, mx, pm, bn, bm, fn, fm, ln, lm, g_cw, g_ch, wm, (int)g_cap_eff);
            _snprintf(g_text, sizeof(g_text),
                      " %3.0f fps   %4.1f ms/frame   worst %3.0f ms ",
                      fps, fr ? (dt - wm) / fr : 0.0, mx);
            g_text[sizeof(g_text) - 1] = 0;
        }
    }
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
        logf("sc3perf loaded: overlay=%d profile=%d sysmem=%d fps_cap=%d clock_ms=%d spr_budget=%.0f spr_sleep_us=%d", g_overlay,
             g_profile, g_sysmem, g_cap, g_clock_ms, g_spr_budget, g_spr_sleep_us);
        CreateThread(NULL, 0, watcher, NULL, 0, NULL);
        if (g_clock_ms) CreateThread(NULL, 0, clock_watcher, NULL, 0, NULL);
        if (g_spr_budget > 0 || g_spr_follow) CreateThread(NULL, 0, spr_watcher, NULL, 0, NULL);
        if (g_trclear) CreateThread(NULL, 0, tr_watcher, NULL, 0, NULL);
        if (g_fastftol) patch_ftol();      /* msvcrt is loaded before any mod; patch before the game converts a float */
    }
    return TRUE;
}
