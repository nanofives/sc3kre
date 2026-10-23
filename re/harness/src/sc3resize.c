        /* ⛔ DO NOT stretch the dest rect PAST the panel to kill the blit scaling.
         * That was the first attempt and it backfired: with the dest bottom at the surface's real
         * 1089 rows, a layout pass grew the PANEL itself to 2178 = 2 x 1089 a couple of seconds
         * later (measured 2026-09-02, caught by the SIDEKIDS runaway guard). The scaling is instead
         * removed by making the SURFACE match this rect - see the liveH passed to
         * rz_side_fit_child below, which subtracts RZ_SURFACE_SLACK so the padded surface comes out
         * exactly `bottom` tall and the blit is 1:1. */
/* sc3resize.c - standalone resizable-window mod for SimCity 3000 Unlimited.
 *
 * A slim, shippable carve of the validated minimal Init-FREE resize routine out of
 * re/harness/src/sc3probe.c (`rz_minimal_resize`). It makes the in-city isometric view
 * re-render correctly after the window is resized - the defect tracked as U-068 - with NONE
 * of the harness machinery (no capture, no census, no gzlog, no verb dispatcher).
 *
 * WHY A DLL AND NOT A CODE CAVE. Costed in re/analysis/RESIZE_DELIVERY_COST.md: the routine
 * is 8 thiscall invocations plus ~10 field writes, roughly 4x the largest cave this project
 * has shipped (close_button_quit, 77 bytes), for no capability the DLL route lacks. The
 * routine already exists as C validated over six game runs, so shipping it is a carve rather
 * than a hand-assembly job. Delivery vehicle: launcher EXE (CreateProcess SUSPENDED +
 * CreateRemoteThread(LoadLibraryA)), the same one sc3launch.c and slider_launch.c use.
 * DEFERRED.md D-001's foreclosure was proxy-specific, not all injection.
 *
 * PROVENANCE. The logging and detour-installer blocks below are copied VERBATIM from
 * re/harness/src/sc3slider.c (which took them verbatim from sc3probe.c), so the hard-won,
 * address-anchored, position-independent code is not re-derived. Ranges cited per block.
 * The resize routine itself is a faithful carve of sc3probe.c's `rz_minimal_resize` and
 * `rz_recreate_raster` as they stood when run 6 PASSED (verify/resize_minimal/RESULTS.md).
 *
 * THE SEQUENCE (validated 2026-08-27, 6 runs; Init FUN_10005b42 is NEVER called, so its
 * vt+0x10 teardown and iso+0x24 realloc are both avoided):
 *   1. extent  iso+0x5c = iso+0x54 + w, iso+0x60 = iso+0x58 + h, mirror to iso+0x64..0x70
 *      !! WORLD PIXEL space with a MOVING ORIGIN - left/top are routinely NEGATIVE (measured
 *         -848, 2924). Writing w/h absolutely produced a negative height and a BLACK frame.
 *   2. FUN_100059fb(w, h, &gw, &gh, 0)   - the game's own dirty-grid table (40x64 at 1280x1024)
 *   3. FUN_1000e2c0(iso, gw, gh)         - realloc dirty grid + recompute cell sizes
 *   4. FUN_1000ee29(iso, 8, 8, 0)        - grid B is 8x8 at EVERY resolution (FUN_100059fb
 *                                          mode 1 returns 8,8 unconditionally). OMITTING THIS
 *                                          HUNG THE GAME inside FUN_10018cdf.
 *   5. FUN_10009efb replay on iso+0x74   - render target, +0x08 guard cleared, ORIGINAL tuple
 *   6. FUN_10009efb replay on iso+0x4ec  - device surface. MEASURED NECESSARY: the engine does
 *                                          not re-Init it on a stock resize.
 *   7. FUN_10018cdf(bridge, 0, b+0x78, b+0xa8, 0, 0) - tile-cache refill + repaint (~47 ms)
 *      (2026-10-11: skipped by default, with step 11 - SKIPREFRESH, about 1 s each on a 1024 map)
 *   8. FUN_1000fa36(iso, 1, 0)           - re-register drawables from the PERSISTENT container
 *                                          iso+0x3a4. Omitting this renders TERRAIN ONLY
 *                                          (32 distinct colours against a good frame's 463).
 *   9. present rect iso+0x4d0            - supplied by the separate `resize_rectfix` patch.
 *
 * THE STORED-RECT PROBLEM. GZGraphicD's WM_SIZE handler FUN_100185f5 republishes the WINDOW
 * OBJECT'S STORED size (vt+0x68 = *(win+0x40)-*(win+0x38)), not lParam and not GetClientRect,
 * and nothing updates that stored size on a stock resize - measured: the OS client went to
 * 1280x1024 while every engine field stayed at 800x600.
 *
 * ^ CORRECTED 2026-08-29. This comment used to end "This DLL fixes it in C by subclassing the
 * game window (see rz_subclass), which is why the separate GZGraphicD `wmsize_setrect` patch is
 * OPTIONAL". THAT WAS FALSE: rz_wndproc called the original proc and logged lParam, and wrote
 * NOTHING. The claim propagated into RESIZABLE_WINDOW.md section 3 and cost a failed D-004
 * hand-test, where the city drew 800x600 in the top-left because FUN_100185f5 kept publishing the
 * stale rect and FUN_10018c58 (IDirectDrawSurface::Blt) kept presenting at that size.
 * rz_set_stored_rect (below) is the actual fix, added the same day. See verify/resize_storedrect/
 * and RESIZABLE_WINDOW.md sections 8/8b.
 *
 * POSITION INDEPENDENCE (BOARD standing rule). SIMSPR and GZGraphicD both prefer base
 * 0x10000000 and one is relocated per run. Every address is resolved from a live module handle
 * + offset (GetModuleHandleA), never an absolute.
 *
 * EXPECT-OR-REFUSE. Every dereference is IsBadReadPtr-gated and every vtable is COMPARED
 * against a known MODULE+RVA, never dispatched through to identify it - the mistake that
 * crashed an earlier surface dump. A refusal is a LOGGED RESULT, not a crash.
 *
 * SCOPE, HONESTLY (verify/resize_minimal/RESULTS.md): validated upward only (800x600 ->
 * 1280x1024), one city, one zoom, in a headless harness. Downward resize (U-069) is UNTESTED.
 * No claim about the DirectDraw primary (D-004).
 *
 * Build: 32-bit x86 (must match SC3U.exe, PE32). re/harness/build_resize.ps1.
 */
#include <windows.h>
#include <intrin.h>   /* _ReturnAddress - exact Blt caller, replaces the failed stack scans */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ============================================================ logging (sc3probe.c:28-66) */

static CRITICAL_SECTION g_lock;
static HANDLE g_log = INVALID_HANDLE_VALUE;
static LARGE_INTEGER g_freq, g_t0;
static HMODULE g_self;                          /* [SLIDER] this DLL, for locating slider.ini */
static DWORD g_logcap, g_logbytes;              /* default-log cap, see log_open */

static void logf(const char *fmt, ...) {
    char buf[2048];
    char line[2176];
    va_list ap;
    LARGE_INTEGER now;
    double ms;
    DWORD wrote;
    int n;

    va_start(ap, fmt);
    _vsnprintf(buf, sizeof(buf) - 1, fmt, ap);
    buf[sizeof(buf) - 1] = 0;
    va_end(ap);

    QueryPerformanceCounter(&now);
    ms = (double)(now.QuadPart - g_t0.QuadPart) * 1000.0 / (double)g_freq.QuadPart;

    n = _snprintf(line, sizeof(line) - 1, "[%9.3f ms][tid %04lx] %s\r\n",
                  ms, GetCurrentThreadId(), buf);
    if (n < 0) return;
    line[sizeof(line) - 1] = 0;

    EnterCriticalSection(&g_lock);
    if (g_log != INVALID_HANDLE_VALUE) {
        if (g_logcap && g_logbytes + (DWORD)n > g_logcap) {
            static const char stop[] = "### log cap reached (8 MB) - further lines dropped. "
                                       "Set SC3RESIZE_LOG=<path> for an uncapped log.\r\n";
            WriteFile(g_log, stop, sizeof(stop) - 1, &wrote, NULL);
            CloseHandle(g_log);
            g_log = INVALID_HANDLE_VALUE;
        } else {
            WriteFile(g_log, line, (DWORD)n, &wrote, NULL);
            g_logbytes += (DWORD)n;
        }
    }
    LeaveCriticalSection(&g_lock);
    OutputDebugStringA(line);
}

/* The default log (no SC3RESIZE_LOG) is capped so a long play session cannot grow it without bound:
 * an owner session with many resizes wrote ~1.6 MB (verify/handtest_1006). An explicit SC3RESIZE_LOG
 * path (dev and verify runs) stays uncapped. */
static void log_open(void) {
    char path[MAX_PATH];
    if (!GetEnvironmentVariableA("SC3RESIZE_LOG", path, sizeof(path))) {  /* [RESIZE] own default */
        /* Beside the DLL, not the process CWD: the game runs with CWD = Apps\, a game folder, so a
         * bare relative name wrote the log into the install (2026-10-09). */
        char *sl;
        if (g_self && GetModuleFileNameA(g_self, path, sizeof(path) - 16) && (sl = strrchr(path, '\\')) != NULL)
            lstrcpyA(sl + 1, "sc3resize.log");
        else
            lstrcpynA(path, "sc3resize.log", sizeof(path));
        g_logcap = 8u * 1024u * 1024u;
    }
    g_log = CreateFileA(path, GENERIC_WRITE, FILE_SHARE_READ, NULL,
                        CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
}

/* ============================== detour installer (sc3probe.c:8144-8229, 8730-8789) VERBATIM.
 * Self-contained: closure is modrm_len/insn_len/steal_len/pool_alloc + the FNLOG struct.
 * It emits a stub that jmps to fnlog_enter (resolved by address at install time), so the
 * minimal fnlog_enter below satisfies it. */

static int modrm_len(const BYTE *p) {
    BYTE m = p[0];
    int mod = m >> 6, rm = m & 7, n = 1;
    if (mod == 3) return n;
    if (rm == 4) {                       /* SIB */
        BYTE sib = p[1];
        n++;
        if (mod == 0 && (sib & 7) == 5) n += 4;
    } else if (mod == 0 && rm == 5) {
        n += 4;                          /* disp32 */
    }
    if (mod == 1) n += 1;
    else if (mod == 2) n += 4;
    return n;
}

static int insn_len(const BYTE *p, int *is_rel32) {
    BYTE op = p[0];
    *is_rel32 = 0;
    if (op == 0x66 || op == 0xF2 || op == 0xF3) {
        int r, l = insn_len(p + 1, &r);
        *is_rel32 = 0;
        return l ? l + 1 : 0;
    }
    if (op >= 0x50 && op <= 0x5F) return 1;              /* push/pop reg */
    if (op == 0x90 || op == 0xC3 || op == 0xC9) return 1;
    if (op == 0x6A) return 2;                            /* push imm8 */
    if (op == 0x68) return 5;                            /* push imm32 */
    if (op >= 0xB8 && op <= 0xBF) return 5;              /* mov reg, imm32 */
    if (op >= 0xA0 && op <= 0xA3) return 5;              /* mov AL/eAX <-> moffs32 (absolute) */
    if (op == 0xE8 || op == 0xE9) { *is_rel32 = 1; return 5; }
    if (op == 0xEB) return 2;
    if (op == 0xC2) return 3;                            /* ret imm16 */
    if (op == 0x83 || op == 0x80) return 1 + modrm_len(p + 1) + 1;
    if (op == 0x81) return 1 + modrm_len(p + 1) + 4;
    if (op == 0xC6) return 1 + modrm_len(p + 1) + 1;
    if (op == 0xC7) return 1 + modrm_len(p + 1) + 4;
    switch (op) {
    case 0x00: case 0x01: case 0x02: case 0x03:
    case 0x08: case 0x09: case 0x0A: case 0x0B:
    case 0x20: case 0x21: case 0x22: case 0x23:
    case 0x28: case 0x29: case 0x2A: case 0x2B:
    case 0x30: case 0x31: case 0x32: case 0x33:
    case 0x38: case 0x39: case 0x3A: case 0x3B:
    case 0x84: case 0x85: case 0x88: case 0x89:
    case 0x8A: case 0x8B: case 0x8D: case 0x8F:
    case 0xFF:
        return 1 + modrm_len(p + 1);
    }
    return 0;
}

#define MAX_REL 4
static int steal_len(const BYTE *p, int *relofs, int *nrel) {
    int total = 0;
    *nrel = 0;
    while (total < 5) {
        int r, l = insn_len(p + total, &r);
        if (!l || total + l > 24) return 0;
        if (r && *nrel < MAX_REL) relofs[(*nrel)++] = total;
        total += l;
    }
    return total;
}

#define MAX_FNLOG 8                      /* [SLIDER] only ever the one heartbeat entry */

typedef struct {
    DWORD  va;
    char   name[64];
    BYTE  *target;
    BYTE  *tramp;
    volatile LONG hits;
    int    logret;
} FNLOG;

static FNLOG g_fn[MAX_FNLOG];
static int   g_nfn;
static BYTE *g_codepool;
static DWORD g_codeused;

static BYTE *pool_alloc(DWORD n) {
    BYTE *p;
    if (!g_codepool) {
        g_codepool = (BYTE *)VirtualAlloc(NULL, 64 * 1024, MEM_COMMIT | MEM_RESERVE,
                                          PAGE_EXECUTE_READWRITE);
        g_codeused = 0;
        if (!g_codepool) return NULL;
    }
    if (g_codeused + n > 64 * 1024) return NULL;
    p = g_codepool + g_codeused;
    g_codeused += (n + 15) & ~15u;
    return p;
}

/* forward decl: the stub emitted below jmps here by address */
static void __stdcall fnlog_enter(int idx, DWORD *f);

static int fnlog_install_one(FNLOG *e, int idx) {
    BYTE *t = e->target;
    int relofs[MAX_REL], nrel = 0, k;
    int len = steal_len(t, relofs, &nrel);
    BYTE *tr, *stub;
    DWORD old;

    if (!len) {
        logf("FN  %-34s @0x%08lX  UNDECODABLE prologue %02X %02X %02X %02X %02X - skipped",
             e->name, (DWORD)t, t[0], t[1], t[2], t[3], t[4]);
        return 0;
    }
    tr   = pool_alloc(len + 5);
    stub = pool_alloc(24);
    if (!tr || !stub) { logf("FN  code pool exhausted"); return 0; }

    memcpy(tr, t, len);
    /* Relocate any rel32 that moved with the stolen bytes. */
    for (k = 0; k < nrel; k++) {
        int o = relofs[k];
        DWORD abs_target = (DWORD)(t + o + 5) + *(DWORD *)(t + o + 1);
        *(DWORD *)(tr + o + 1) = abs_target - (DWORD)(tr + o + 5);
        logf("FN  %s: relocated rel32 at +%d -> 0x%08lX", e->name, o, abs_target);
    }
    tr[len] = 0xE9;
    *(DWORD *)(tr + len + 1) = (DWORD)(t + len) - (DWORD)(tr + len + 5);

    stub[0] = 0x60; stub[1] = 0x9C; stub[2] = 0x8B; stub[3] = 0xC4; stub[4] = 0x50;
    stub[5] = 0x68; *(DWORD *)(stub + 6) = (DWORD)idx;
    stub[10] = 0xE8; *(DWORD *)(stub + 11) = (DWORD)fnlog_enter - (DWORD)(stub + 15);
    stub[15] = 0x9D; stub[16] = 0x61;
    stub[17] = 0xE9; *(DWORD *)(stub + 18) = (DWORD)tr - (DWORD)(stub + 22);

    if (!VirtualProtect(t, (SIZE_T)len, PAGE_EXECUTE_READWRITE, &old)) {
        logf("FN  %s: VirtualProtect failed (%lu)", e->name, GetLastError());
        return 0;
    }
    t[0] = 0xE9;
    *(DWORD *)(t + 1) = (DWORD)stub - (DWORD)(t + 5);
    { int j; for (j = 5; j < len; j++) t[j] = 0x90; }
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    FlushInstructionCache(GetCurrentProcess(), t, (SIZE_T)len);

    e->tramp = tr;
    return 1;
}

/* ==================================================================== [RESIZE] the mod itself */

/* SIMSPR RVAs. All resolved against the LIVE base at call time. */
#define RVA_BRIDGE_INIT   0x16eba   /* FUN_10016eba: ECX = the occupant bridge (thiscall) */
#define RVA_BRIDGE_FILL   0x18cdf   /* FUN_10018cdf: whole-map tile-cache refill + repaint */
#define RVA_GRIDDIMS      0x59fb    /* FUN_100059fb: dimension table (cdecl, 5 args) */
#define RVA_DIRTYGRID     0xe2c0    /* FUN_1000e2c0: realloc dirty grid, recompute cell sizes */
#define RVA_GRIDB         0xee29    /* FUN_1000ee29: size + zero grid B */
#define RVA_REREGISTER    0xfa36    /* FUN_1000fa36: re-register drawables from iso+0x3a4 (LEAF - see below) */
#define RVA_DRAWKEY       0xc8f9    /* FUN_1000c8f9: __thiscall(iso) recompute every object draw key wrapper+0x24 */
#define RVA_OBJREREG      0xc9bd    /* FUN_1000c9bd: __thiscall(iso, RECT* sentinel, uint* iso+0x54, char recompute)
                                       the REAL object re-register: clears fine grid iso+0x380 (FUN_1000edd9),
                                       tag-2 region pickup (FUN_1000cedb), then FUN_1000fa36 (tag-1). Convention
                                       + args disassembled from the engine's own call at 0x10006bc0. */
#define RVA_CELL_HIDE     0x6c67    /* FUN_10006c67: __thiscall(iso, int* drawable, int zoom, u32 rot, u32 row, int col)
                                       per-cell HIDE - clears set sublayer bits, issues drawable vtable +0x38 */
#define RVA_CELL_SHOW     0x6efc    /* FUN_10006efc: __thiscall(iso, int* drawable, int zoom, u32 rot, int row, u32 col)
                                       per-cell SHOW - issues drawable vtable +0x34, re-sets sublayer bits */
#define RVA_FULLREPAINT   0xdb86    /* FUN_1000db86 = iso vtable+0x144 (verified from PE at 0x10062650):
                                       __fastcall(ecx=iso) - FUN_1000e248 teardown then tessellate the whole
                                       extent iso+0x54..0x60 into 64 dirty rects (+0x130) and set iso+0x32c=1.
                                       This is the whole-view repaint the data-view toggle runs (FUN_1001818c
                                       :53-55) and the resize omitted - the surface is recreated but never
                                       marked dirty, so the per-frame composite FUN_1000dc17 has nothing to draw. */
#define RVA_LIST_ERASE    0x1084b   /* FUN_1001084b: __thiscall(list, first, last) - erase */
#define RVA_LIST_PUSH     0x10586   /* FUN_10010586: __thiscall(list, &rect) - push_back */
#define RVA_ISO_VT        0x6250c   /* the iso view's vtable, for the identity gate */
/* SIMUI RVAs (HUD reflow, top-strip proof 2026-08-30). */
#define SUI_RVA_PRODUCER  0x270e5   /* FUN_100270e5: __thiscall(this=HUD win, int* outTable) ret 4 -
                                       fills the top-strip anchor table (preset by mode W). We wrap it. */
#define SUI_RVA_BUILD     0x24a96   /* FUN_10024a96: __fastcall(this) - builds/registers the top-strip HUD */
#define SUI_RVA_DESTRUCT  0x266c1   /* FUN_100266c1: __fastcall(this) - contents teardown (guarded, keeps this) */
/* GZGraphicD RVAs. */
#define GZ_RVA_RASTER_CREATE 0x9efb  /* FUN_10009efb, vtable slot +0x0c on both raster classes */
#define GZ_RVA_VT_RASTER     0x1E894 /* raster class vtable */
#define GZ_RVA_VT_BLITDEST   0x1F328 /* blit-dest subclass (iso+0x4ec) */
#define GZ_RVA_VT_SURFACE    0x1F0AC /* the SUB-OBJECT (DirectDraw surface) vtable, installed by
                                        FUN_1001420d as PTR_FUN_1001f0ac. Slots read from the PE:
                                        +0x0c FUN_10018a82 Lock, +0x10 FUN_10018b53 Unlock,
                                        +0x40 FUN_10019273 Create. Lock is what writes sub+0xf0
                                        (bits) and sub+0xf4 (pitch); Create never does. */
#define RZ_SURFACE_SLACK     8       /* guard rows below the visible height: FUN_1000239d's 2x/4x
                                        zoom blit companion-writes up to ~3 scanlines past the last
                                        row and has no surface-height clamp. Never presented (step 9
                                        present rect is {0,0,w,ht}). See verify/resize_zoomcrash/. */
#define GZ_RVA_HEARTBEAT     0x18c58 /* per-frame, game thread, mid-paint - the poll site */

/* DEFECT 3 FIX (2026-08-28). The validation run MEASURED the costing's open [UNCERTAIN]: the tuple
 * read back from a raster's own fields gave p3 = 7 where the harness's RECORDED create tuple for the
 * same object was p3 = 4. So field read-back does NOT reproduce the create arguments, and the
 * costing's "no recording hook needed" conclusion is WRONG. We now record real tuples by hooking
 * FUN_10009efb, exactly as the harness does, and only fall back to field read-back when an object
 * has no recorded create - logging loudly which path was taken. */
#define MAX_RC 256
static struct { DWORD obj; DWORD a[8]; } g_rc[MAX_RC];
static volatile LONG g_nrc;
static volatile LONG g_rc_full;

static void *g_bridge;                 /* captured at FUN_10016eba; iso = bridge+0x18 */
static volatile LONG g_rz_step;        /* breadcrumb: which of the 9 steps is executing, for the
                                          SEH fault catcher (2026-08-28 crash hunt) */
static int   g_minzoom;                /* SC3RESIZE_MINZOOM: force zoom 0 before resizing (worst case) */
static DWORD g_bridge_ms;              /* GetTickCount when the bridge was first captured */
static DWORD g_ready_ms = 3000;        /* load-readiness gate: ignore resizes for this long after
                                          bridge capture (SC3RESIZE_READYMS overrides). The v3 crash
                                          (non-reproducing) fired ~5s after capture during load; this
                                          is preventive hygiene - do not touch the view mid-init. */
static int   g_defer_logged;
static volatile LONG g_bridge_fresh;
#define RZ_HOLD_MAX_MS 6000
static int    g_hold = 1;            /* SC3RESIZE_HOLD=0: no present hold, dialogs on the 100 ms timer only */
static int    g_hold_logged;
static LONG   g_hold_frames;   /* a new city view not yet laid out by rz_do_resize (see the SETTLED check) */
static int   g_census;                 /* SC3RESIZE_CENSUS: census the resized frame content */
static DWORD g_census_ms;              /* when to run the post-resize census (0 = not scheduled) */

/* Census one raster's backing RAW (never call vf1c - the standing rule: reading sub+0xf0/f4 out of
 * band via the lock tears the backing down). Reports total non-zero %, the content bounding box, and
 * crucially the non-zero count in the AREA BEYOND the old 800x600 - which is what distinguishes a
 * full-window frame from one clipped to the top-left. 16bpp (fix16). */
static void rz_census_one(DWORD R, const char *name) {
    DWORD sub, bits, pitch, w, h, bpp;
    long total = 0, nz = 0, beyond = 0;
    int minr = 1 << 30, maxr = -1, minc = 1 << 30, maxc = -1, r, c;
    if (!R || IsBadReadPtr((void *)R, 0x2c)) { logf("CENSUS> %s: R unreadable", name); return; }
    w = ((DWORD *)R)[0x24 / 4]; h = ((DWORD *)R)[0x28 / 4]; bpp = ((DWORD *)R)[0x10 / 4];
    sub = ((DWORD *)R)[0x44 / 4];
    if (!sub || IsBadReadPtr((void *)sub, 0xf8)) { logf("CENSUS> %s: sub unreadable", name); return; }
    bits = ((DWORD *)sub)[0xf0 / 4]; pitch = ((DWORD *)sub)[0xf4 / 4];
    if (!bits || !pitch || w == 0 || h == 0 || IsBadReadPtr((void *)bits, pitch * h)) {
        logf("CENSUS> %s: no readable backing (bits=0x%08lX pitch=%lu %lux%lu bpp=%lu)",
             name, bits, pitch, w, h, bpp);
        return;
    }
    for (r = 0; r < (int)h; r++) {
        BYTE *row = (BYTE *)bits + (DWORD)r * pitch;
        for (c = 0; c < (int)w; c++) {
            WORD px = *(WORD *)(row + c * 2);   /* 16bpp */
            total++;
            if (px) {
                nz++;
                if (r < minr) minr = r; if (r > maxr) maxr = r;
                if (c < minc) minc = c; if (c > maxc) maxc = c;
                if (c >= 800 || r >= 600) beyond++;   /* content in the NEW area */
            }
        }
    }
    logf("CENSUS> %s: %lux%lu bpp=%lu pitch=%lu | non-zero %ld/%ld (%.1f%%) | bbox r%d..%d c%d..%d "
         "(%dx%d) | beyond-800x600 non-zero=%ld  << %s", name, w, h, bpp, pitch, nz, total,
         total ? 100.0 * nz / total : 0.0, minr, maxr, minc, maxc,
         maxc >= minc ? maxc - minc + 1 : 0, maxr >= minr ? maxr - minr + 1 : 0, beyond,
         beyond > 0 ? "FILLS BEYOND THE OLD EXTENT (not clipped to 800x600)"
                    : "NO content beyond 800x600 (clipped, or a small zoomed-out scene)");
}
static void rz_census(void) {
    void *iso;
    if (!g_bridge || IsBadReadPtr(g_bridge, 0x1c)) return;
    iso = (void *)((DWORD *)g_bridge)[0x18 / 4];
    if (!iso || IsBadReadPtr(iso, 0x4f0)) { logf("CENSUS> iso unreadable"); return; }
    logf("CENSUS> ---- post-resize content census (RAW, no vf1c) ----");
    rz_census_one(((DWORD *)iso)[0x74 / 4],  "render-target iso+0x74");
    rz_census_one(((DWORD *)iso)[0x4ec / 4], "blit-dest   iso+0x4ec");
}
/* ==================================================================================================
 * HUD LAB (2026-08-31, verify/resize_hudlab/PRE.md) - two READ-ONLY instruments behind
 * SC3RESIZE_HUDLAB=1. Unset, none of this arms and the mod is the shipped viewport build.
 *
 * WHY: the HUD workstream closed on two UNMEASURED claims. (1) "the full-width bar's FPS cost is
 * intrinsic to per-frame compositing" was reached by ELIMINATION (three hypotheses falsified) - frame
 * time was never profiled. (2) the 6 children g_hud_top[0x2a..0x2f] were written up as an unknown
 * class, but their vtable GZGraphicD+0x1E894 is the RASTER SURFACE base class this project already
 * mapped (LAUNCH_CONTROL.md:4048, RESIZE_DELIVERY_COST.md:47) and which rz_census_one above already
 * reads. Both instruments exist to replace inference with measurement.
 * ================================================================================================== */
static void  rz_modstr(DWORD addr, char *out, int n);   /* fwd: defined below, resolves EIP->MODULE+RVA */
static int   rz_win_alive(void *want);                  /* fwd: is this window still in the live tree */
static int   g_hudlab;                 /* SC3RESIZE_HUDLAB: arm the HUD lab */
static int   g_hudfit = 1;             /* dock+span the HUD bar (SHIP DEFAULT ON; SC3RESIZE_HUDNATIVE=1
                                          turns it off and leaves the HUD exactly native) */
static BYTE *g_hud_art;                /* one-time cache of the PRISTINE native bar art */
static DWORD g_hud_artw, g_hud_arth, g_hud_artpitch;
static HWND  g_hwnd;                   /* the game window (declared here: the HUD lab reads it for
                                          the live client size) */
/* The SIDE PANEL window `this`, captured in its constructor SIMUI FUN_1004e123 (run 21).
 *
 * That constructor installs `*this = &PTR_FUN_100a9834`, the vtable whose slot **+0x144** is
 * FUN_1004e63e - the vertical tiling paint routine. (+0x144 is this framework's draw slot; the iso
 * view's whole-view repaint sits at the same offset.) Found by parsing SIMUI's static .rdata for
 * the function pointer, then locating the .text site that writes that vtable base as an immediate
 * (0x4e183, inside FUN_1004e123) - the same PE-parsing route used for the GZGraphicD window vtable,
 * no Ghidra lock needed.
 *
 * CROSS-CONFIRMED, not assumed: the constructor zeroes dword fields [0x30..0x33] and [0x45], which
 * are byte offsets +0xc0/+0xc4/+0xc8/+0xcc and +0x114 - EXACTLY the five child pointers
 * FUN_1004e63e blits, with [0x33] (+0xcc) being the tiled one. Constructor and paint routine agree
 * on the layout. [CONFIRMED @ SIMUI 0x1004e123, 0x1004e63e] */
static void *g_side_top;

/* MINIMAP HUNT (run 23). The owner reports the minimap did not move with the side panel, so it is a
 * separate window. Two more SIMUI classes have a paint routine at the same draw slot **+0x144** and
 * NO tile loop (so, per the model, cheap to move):
 *   FUN_1001ad52  vtable RVA 0xa3d08 +0x144, installed at .text 0x1a9dd -> ctor FUN_1001a983
 *   FUN_10060f59  vtable RVA 0xaab14 +0x144, installed at .text 0x60c07 -> ctor FUN_10060ba9
 * (The side panel's own is FUN_1004e63e / vtable 0xa9834 / ctor FUN_1004e123 - same shape, which is
 * what makes +0x144 a reliable handle on "this framework's window classes".)
 *
 * Both classes may be instantiated more than once, so capture SEVERAL instances of each rather than
 * assuming the first is the interesting one - the rect at diag time is what identifies the minimap
 * (roughly square, near a screen edge), not construction order. */
#define CAPT_MAX 8
static void *g_capt[2][CAPT_MAX];
static LONG  g_capt_n[2];

/* ---- UI TREE WALK (run 24) --------------------------------------------------------------------
 * The minimap is a third window class and guessing candidates cost run 23. The obvious instrument -
 * a surface->owner registry via a create hook on FUN_10009efb - is exactly the hook this mod DROPPED
 * after the v2 crash, where the failure "isolates to the create recorder by construction" and the
 * leading suspect was detouring a hot function during device bring-up (verify/resize_ship).
 * Re-enabling it would repeat the experiment that killed the game.
 *
 * There is a read-only alternative. The window BASE constructor builds a circular doubly-linked list
 * head at `this[0x2d]` (= +0xb4): `n = alloc(0xc); n->next = n; n->prev = n`
 * `[CONFIRMED @ SIMUI 0x1004d9be]`. So every window of this framework carries a 12-byte-node list,
 * and walking it from a window we already hold enumerates the tree - no new hook, nothing written,
 * nothing detoured.
 *
 * Bounded and defensive: node count capped, every dereference guarded, and the walk stops when it
 * returns to the head (or fails to). A payload is only reported as a window if it has a readable
 * vtable AND a plausible rect. */
static void rz_walk_windows(const char *tag, void *w, int depth) {
    DWORD *win = (DWORD *)w;
    DWORD head, node;
    int n = 0;
    if (!win || IsBadReadPtr(win, 0xb8) || depth > 2) return;
    head = win[0xb4 / 4];
    if (!head || IsBadReadPtr((void *)head, 12)) {
        logf("TREE> %s 0x%08lX: no child list at +0xb4 (0x%08lX)", tag, (DWORD)win, head);
        return;
    }
    node = *(DWORD *)head;                       /* first real node, or head itself if empty */
    while (node && node != head && n++ < 64 && !IsBadReadPtr((void *)node, 12)) {
        DWORD payload = ((DWORD *)node)[2];
        if (payload && !IsBadReadPtr((void *)payload, 0x24)) {
            DWORD *p = (DWORD *)payload;
            LONG x1 = (LONG)p[0x14/4], y1 = (LONG)p[0x18/4];
            LONG x2 = (LONG)p[0x1c/4], y2 = (LONG)p[0x20/4];
            LONG cw = x2 - x1, ch = y2 - y1;
            int plausible = (cw > 0 && ch > 0 && cw < 8192 && ch < 8192);
            logf("TREE> %s child[%d] 0x%08lX vt=0x%08lX rect=[%ld %ld %ld %ld] %ldx%ld%s%s",
                 tag, n - 1, payload, p[0], x1, y1, x2, y2, cw, ch,
                 plausible ? "" : "  (rect implausible - may not be a window)",
                 (plausible && cw < ch * 2 && ch < cw * 2 && cw > 40)
                     ? "   <<< SQUARE-ISH" : "");
            if (plausible) rz_walk_windows(tag, (void *)payload, depth + 1);
        }
        node = *(DWORD *)node;                   /* ->next */
    }
    if (n == 0) logf("TREE> %s 0x%08lX: child list EMPTY", tag, (DWORD)win);
}
static void *g_hud_top;                /* the HUD bottom-bar window `this`, captured in the FUN_100270e5
                                          wrap. Declared here (not down with the other window globals)
                                          because rz_hud_surfaces below reads it. The 2026-08-31
                                          diagnostic proved this is the BOTTOM toolbar, not the top
                                          strip - ownrect [0,544,599,600]. */

/* ---- I1: HUD child surface census -------------------------------------------------------------
 * Read one child as a +0x1E894-family raster: dims +0x24/+0x28, bpp +0x10, sub +0x44, and the
 * backing RAW at sub+0xf0 / sub+0xf4. STANDING RULE, learned the hard way (BOARD.md): read
 * sub+0xf0/f4 RAW and NEVER call vf1c out of band - the out-of-band lock tears the backing down and
 * the instrument destroys what it measures. Reports whether pitch is coherent with width*2 (fix16),
 * which is the check that decides "coherent raster" vs "we are misreading the object". */
static void rz_hud_surface(DWORD c, const char *tag, int idx) {
    DWORD gz = (DWORD)GetModuleHandleA("GZGraphicD.dll");
    DWORD *cv, sub, bits, pitch, w, h, bpp;
    const char *fam;
    if (!c || IsBadReadPtr((void *)c, 0x48)) {
        logf("HUDSURF> %s child[0x%x]=0x%08lX unreadable", tag, idx, c); return;
    }
    cv = *(DWORD **)c;
    fam = (gz && (DWORD)cv == gz + 0x1E894) ? "RASTER gz+0x1E894"
        : (gz && (DWORD)cv == gz + 0x1F328) ? "BLITDEST gz+0x1F328"
        : "UNKNOWN-CLASS";
    w = ((DWORD *)c)[0x24 / 4]; h = ((DWORD *)c)[0x28 / 4]; bpp = ((DWORD *)c)[0x10 / 4];
    sub = ((DWORD *)c)[0x44 / 4];
    if (!sub || IsBadReadPtr((void *)sub, 0xf8)) {
        logf("HUDSURF> %s child[0x%x]=0x%08lX vt=0x%08lX %s dims=%lux%lu bpp=%lu sub=0x%08lX UNREADABLE",
             tag, idx, c, (DWORD)cv, fam, w, h, bpp, sub);
        return;
    }
    bits = ((DWORD *)sub)[0xf0 / 4]; pitch = ((DWORD *)sub)[0xf4 / 4];
    {
        long nz = 0, total = 0;
        int coherent = (pitch != 0 && w != 0 && pitch >= w * 2 && pitch <= w * 2 + 64);
        if (bits && pitch && w && h && !IsBadReadPtr((void *)bits, pitch * h)) {
            DWORD r, cc;
            for (r = 0; r < h; r++) {
                BYTE *row = (BYTE *)bits + r * pitch;
                for (cc = 0; cc < w; cc++) { total++; if (*(WORD *)(row + cc * 2)) nz++; }
            }
        }
        logf("HUDSURF> %s child[0x%x]=0x%08lX vt=0x%08lX %s | dims=%lux%lu bpp=%lu | sub=0x%08lX "
             "bits=0x%08lX pitch=%lu (%s vs w*2=%lu) | non-zero %ld/%ld",
             tag, idx, c, (DWORD)cv, fam, w, h, bpp, sub, bits, pitch,
             coherent ? "COHERENT" : "INCOHERENT", w * 2, nz, total);
    }
}
/* Census all 6 children plus the HUD window's own rect. Called before AND after the SetRect widen -
 * the comparison is the point: do the child surface EXTENTS track the window, or are they fixed at
 * construction? Fixed extents identify exactly what a real reflow would have to resize. */
static void rz_hud_surfaces(const char *tag) {
    DWORD *h = (DWORD *)g_hud_top;
    int i;
    if (!h || IsBadReadPtr(h, 0xc0)) { logf("HUDSURF> %s: g_hud_top unreadable", tag); return; }
    logf("HUDSURF> ---- %s ---- hud=0x%08lX vt=0x%08lX ownrect=[%ld %ld %ld %ld]",
         tag, (DWORD)h, h[0], (LONG)h[0x14/4], (LONG)h[0x18/4], (LONG)h[0x1c/4], (LONG)h[0x20/4]);
    for (i = 0x2a; i <= 0x2f; i++) rz_hud_surface(h[i], tag, i);
}

/* ---- I2: EIP sampling profiler ----------------------------------------------------------------
 * Suspend the game render thread, read Eip, resume, bucket by eip>>6 (64-byte granularity) in an
 * open-addressed table. NOTHING is logged or allocated while the thread is suspended, and the resume
 * is unconditional in the same iteration. The render thread id is captured in the heartbeat hook,
 * which already runs on it. Buckets resolve to MODULE+0xRVA at dump time via rz_modstr. */
#define PROF_BUCKETS 8192
static DWORD          g_prof_key[PROF_BUCKETS];   /* (eip>>6)+1, 0 = empty slot */
static DWORD          g_prof_cnt[PROF_BUCKETS];
static volatile LONG  g_prof_on;
static DWORD          g_game_tid;                 /* the render thread, from the heartbeat hook */
static DWORD          g_prof_n, g_prof_fail;

/* ---- I2b: WAIT ATTRIBUTION (2026-08-31) -------------------------------------------------------
 * Runs 3-5 established WHERE the render thread stalls (`NtGdiDdDDIWaitForSynchronizationObject`,
 * doubling with bar width) but not WHO leads it there, and the two obvious causes are eliminated
 * (surface content, surface size). EIP alone cannot answer that - every sample lands in the same
 * system stub regardless of caller.
 *
 * So at each sample we also copy the top of the suspended thread's stack and, after resuming, scan
 * it for the first address lying inside a GAME module. That is the nearest game-side return address
 * - "who called into the wait". Bucketed on the EXACT address (not a range) so it names precise call
 * sites, which is the whole point.
 *
 * This is a stack SCAN, not a frame walk: /O2 code omits frame pointers, so an Ebp chain would lie.
 * A scan can also pick up stale values left on the stack - it is a heuristic, and a single hit means
 * little. What makes it decidable is the SAME A/B differential the EIP profiler uses: a call site
 * that appears overwhelmingly in phase B and not in phase A is attributable to the bar width.
 * `[UNCERTAIN]` by construction - treat the ranking as a lead, not a proof. */
#define STK_BYTES 1024
#define MAX_EXEC 32
static DWORD g_modbase[8], g_modsize[8];
static DWORD g_exbase[MAX_EXEC], g_exend[MAX_EXEC];
static int   g_nmod, g_nex;
static DWORD g_stk_key[PROF_BUCKETS], g_stk_cnt[PROF_BUCKETS];
static DWORD g_stk_n, g_stk_miss;

static void rz_prof_modinit(void) {
    static const char *mods[] = { "SIMSPR.DLL", "GZGraphicD.dll", "SIMCITY.DLL", "SIMUI.DLL",
                                  "GZWIN.DLL", "SC3U.exe", 0 };
    int i;
    g_nmod = 0; g_nex = 0;
    for (i = 0; mods[i] && g_nmod < 8; i++) {
        DWORD h = (DWORD)GetModuleHandleA(mods[i]), e;
        if (!h || IsBadReadPtr((void *)h, 0x40)) continue;
        e = *(DWORD *)(h + 0x3c);
        if (IsBadReadPtr((void *)(h + e + 0x50), 4)) continue;
        g_modbase[g_nmod] = h;
        g_modsize[g_nmod] = *(DWORD *)(h + e + 0x50);   /* SizeOfImage */
        g_nmod++;
        /* Record this module's EXECUTABLE sections. PE32: FileHeader at e+4, NumberOfSections at
           e+6, SizeOfOptionalHeader at e+0x14; section table follows the optional header. Each
           IMAGE_SECTION_HEADER is 40 bytes: VirtualSize +0x08, VirtualAddress +0x0c,
           Characteristics +0x24 (IMAGE_SCN_MEM_EXECUTE = 0x20000000). */
        {   WORD ns = *(WORD *)(h + e + 6), opt = *(WORD *)(h + e + 0x14), s;
            DWORD sec = h + e + 0x18 + opt;
            for (s = 0; s < ns && g_nex < MAX_EXEC; s++) {
                DWORD sh = sec + (DWORD)s * 40;
                if (IsBadReadPtr((void *)sh, 40)) break;
                if (*(DWORD *)(sh + 0x24) & 0x20000000) {
                    g_exbase[g_nex] = h + *(DWORD *)(sh + 0x0c);
                    g_exend[g_nex]  = g_exbase[g_nex] + *(DWORD *)(sh + 0x08);
                    g_nex++;
                }
            }
        }
    }
    logf("PROF> module ranges: %d modules, %d executable sections", g_nmod, g_nex);
}
static int rz_in_game_module(DWORD a) {
    int i;
    for (i = 0; i < g_nmod; i++)
        if (a >= g_modbase[i] && a < g_modbase[i] + g_modsize[i]) return 1;
    return 0;
}
static int rz_in_exec(DWORD a) {
    int i;
    for (i = 0; i < g_nex; i++) if (a >= g_exbase[i] && a < g_exend[i]) return 1;
    return 0;
}
/* Is `a` a plausible RETURN ADDRESS? Run 7 failed because the scan accepted any in-module value:
 * its ranking contained SC3U.exe+0x9 (inside the DOS header) and page-aligned SC3U.exe+0x41000 /
 * +0x80000. A return address points at the instruction AFTER a call, so require:
 *   (1) `a` lies in an EXECUTABLE section (kills page-aligned data pointers and header offsets), and
 *   (2) a call instruction ends EXACTLY at `a`.
 * Encodings accepted: E8 rel32 (5), and the FF /2 family - reg field of the modrm must be 2.
 * Lengths cover mod 00/01/10/11 with and without SIB. Far call 9A is not accepted (not emitted by
 * this toolchain and would add false positives). */
static int rz_is_retaddr(DWORD a) {
    const BYTE *p = (const BYTE *)a;
    BYTE m;
    if (!rz_in_exec(a)) return 0;
    if (IsBadReadPtr((void *)(a - 7), 7)) return 0;
    if (p[-5] == 0xE8) return 1;                                  /* call rel32           len 5 */
    /* FF /2 forms, indexed by total instruction length */
    m = p[-1];                                                    /* len 2: FF <modrm> */
    if (p[-2] == 0xFF && ((m >> 3) & 7) == 2 &&
        ((m >= 0xD0 && m <= 0xD7) ||                              /*   mod 11 call reg    */
         ((m >= 0x10 && m <= 0x17) && m != 0x14 && m != 0x15)))   /*   mod 00 call [reg]  */
        return 1;
    m = p[-2];                                                    /* len 3 */
    if (p[-3] == 0xFF && ((m >> 3) & 7) == 2 &&
        (((m >= 0x50 && m <= 0x57) && m != 0x54) ||               /*   mod 01 disp8       */
         m == 0x14))                                              /*   mod 00 SIB         */
        return 1;
    m = p[-3];                                                    /* len 4: mod 01 SIB disp8 */
    if (p[-4] == 0xFF && m == 0x54) return 1;
    m = p[-5];                                                    /* len 6 */
    if (p[-6] == 0xFF &&
        (m == 0x15 ||                                             /*   call [disp32]      */
         ((m >= 0x90 && m <= 0x97) && m != 0x94)))                /*   mod 10 disp32      */
        return 1;
    m = p[-6];                                                    /* len 7: mod 10 SIB disp32 */
    if (p[-7] == 0xFF && m == 0x94) return 1;
    return 0;
}
static void rz_stk_hit(DWORD a) {
    DWORD i = (a * 2654435761u) >> 19 & (PROF_BUCKETS - 1), tries = 0;
    while (tries++ < 64) {
        if (g_stk_key[i] == a) { g_stk_cnt[i]++; g_stk_n++; return; }
        if (g_stk_key[i] == 0) { g_stk_key[i] = a; g_stk_cnt[i] = 1; g_stk_n++; return; }
        i = (i + 1) & (PROF_BUCKETS - 1);
    }
}
static void rz_stk_dump(const char *tag) {
    DWORD i, rank;
    static DWORD taken[24];
    logf("STK> ---- %s ---- attributed=%lu no-game-frame=%lu", tag, g_stk_n, g_stk_miss);
    for (rank = 0; rank < 20; rank++) {
        DWORD best = 0xFFFFFFFF, bestc = 0, j;
        for (i = 0; i < PROF_BUCKETS; i++) {
            int already = 0;
            if (!g_stk_key[i]) continue;
            for (j = 0; j < rank; j++) if (taken[j] == i) { already = 1; break; }
            if (already) continue;
            if (g_stk_cnt[i] > bestc) { bestc = g_stk_cnt[i]; best = i; }
        }
        if (best == 0xFFFFFFFF) break;
        taken[rank] = best;
        {   char who[160];
            rz_modstr(g_stk_key[best], who, sizeof(who));
            logf("STK> %s #%02lu %6lu (%5.2f%%) %s", tag, rank + 1, bestc,
                 g_stk_n ? 100.0 * bestc / g_stk_n : 0.0, who);
        }
    }
}

/* ---- I3: BLIT TIMING (2026-08-31) -------------------------------------------------------------
 * Stack attribution failed twice (run 7 contamination, run 8 selection bias). Rather than build a
 * third scan variant, measure the thing directly.
 *
 * `FUN_10018c58` is the engine's IDirectDrawSurface::Blt wrapper and the mod ALREADY hooks it as the
 * per-frame heartbeat, so the measurement point costs nothing new. At each entry we take a QPC
 * timestamp and attribute the interval since the PREVIOUS entry to the PREVIOUS call's `this`. That
 * interval is that blit's duration plus whatever ran before the next one - which is exactly the
 * quantity that grows when a blit blocks on the GPU.
 *
 * This answers the actual question - WHICH blit got slower when the bar went full-width - without
 * any inference about stacks or callers. If the bar's blit is the stall, it appears here as a
 * specific object whose average time jumps between phase A and phase B.
 *
 * Outliers (> 50 ms) are counted separately, not averaged in: the heartbeat also drives rz_poll,
 * and a frame that ran the whole resize routine would otherwise swamp one bucket. */
#define BLT_BUCKETS 256
#define BLT_OUTLIER_MS 50
/* Declared here (ahead of rz_blt_dump, which reports them); the ddraw Blt hook that fills them is
   defined below. g_blt_slot == (DWORD*)-1 means "refused, do not retry". */
static DWORD  *g_blt_slot;
static __int64 g_ddblt_time;
static DWORD   g_ddblt_calls;
/* Blt argument aggregates, filled by the ddraw hook below, reported by rz_blt_dump. */
#define BFL_BUCKETS 32
static DWORD   g_bfl_key[BFL_BUCKETS], g_bfl_cnt[BFL_BUCKETS];
static __int64 g_bfl_time[BFL_BUCKETS];
static __int64 g_blt_area;
static DWORD   g_blt_areacnt, g_blt_nullrect, g_blt_nullsrc;
static LONG    g_blt_maxw, g_blt_maxh;
/* SOURCE-side attribution (run 15). Blt is a method on the DESTINATION surface, so bucketing by
 * `self` groups every blit into iso+0x4ec together - including the HUD bar's own blit into it.
 * Run 9's "the bar's own blit never appears as a hot object" was therefore unsupported: by
 * construction it could not appear separately. Bucketing by SOURCE separates the scene's tile blits
 * from the bar's, inside the same destination. At dump time the known sources are labelled by
 * comparing against the bar's and the render target's own IDirectDrawSurface* (sub+0x04). */
#define SRC_BUCKETS 64
static DWORD   g_src_key[SRC_BUCKETS], g_src_cnt[SRC_BUCKETS];
static __int64 g_src_time[SRC_BUCKETS];
/* Per-source DEST RECT (run 25). Finding the minimap by owner-object was a dead end: 883 SIMUI
   vtables have a window-shaped draw slot, and walking child lists is invalid because the list-head
   offset is per-class (FUN_1004d9be uses [0x2d], FUN_1006e2e9 uses [0x7d]). But the identity we
   actually want is GEOMETRY, and the hook already receives the dest rect on every call and discards
   it. Where a source lands on screen, and how big, identifies it without needing its owner at all -
   and without dispatching any COM method on a pointer we did not create. */
static LONG    g_src_rect[SRC_BUCKETS][4];
/* MINIMAP CALLER (run 26). Run 25 identified the minimap by GEOMETRY: a per-frame blit to a
   160x164 dest. Lock the filter on that shape rather than on a pointer, because the surface
   pointer changes every run. Only the minimap falls in a 100..400 px square-ish band - the iso
   target is 2048x1081, the side panel 96x442, the ticker 473x14, the small controls 26x26/32x32.
   Record BOTH frames: L1 = g_wrapper_caller (f[9], exact) and L2 = the frame-pointer walk
   (UNCERTAIN - valid only if that frame uses ebp, and the minimap chain may not match the bar's). */
#define MM_BUCKETS 12
static DWORD   g_mm_src, g_mm_w, g_mm_h;
static DWORD   g_mm_l1[MM_BUCKETS], g_mm_l1c[MM_BUCKETS];
static DWORD   g_mm_l2[MM_BUCKETS], g_mm_l2c[MM_BUCKETS];
/* The minimap WINDOW, captured in the generic painter FUN_1006d2d0 (run 27).
 * Runs 23-26 hunted a bespoke class and a +0x144 override; the minimap has NEITHER - it is drawn by
 * the framework painter, which blits this[0x16] (+0x58) into the dest rect at this+0x90
 * [CONFIRMED @ SIMUI 0x1006d2d0]. So identify it by that rect, not by its class: hook the painter,
 * and whichever `this` presents a 160x164 dest IS the minimap. */
static void  *g_mini;
static LONG   g_mini_rect[4];
static int    g_minion;        /* SC3RESIZE_MINI: dock the minimap to the bottom-right */

/* ---- GENERIC EDGE ANCHORING (SC3RESIZE_ANCHOR=1) ----------------------------------------------
 * The owner reports the RCI indicator and the net icon staying put, just as the minimap did. They
 * are more windows positioned in NATIVE 800x600 coordinates. Rather than hunt each one, generalise:
 * EVERY window passes through FUN_1006d2d0 with its dest rect at `this+0x90`
 * [CONFIRMED @ SIMUI 0x1006d2d0], so record each one's native rect on first sight and re-anchor it
 * to the live client size.
 *
 * Anchor rule: a window touching the native RIGHT edge (x2 >= 800-EDGE) moves by (liveW - 800); one
 * touching the native BOTTOM (y2 >= 600-EDGE) moves by (liveH - 600). Left/top-anchored windows stay
 * put. That is the standard reflow for fixed-resolution UI, and it needs no per-element knowledge.
 *
 * The native rect is captured ONCE per window, before any resize, so repeated resizes re-anchor from
 * the original rather than compounding - the same lesson as the bar's art cache.
 *
 * ⚠️ Skips windows covering most of the native screen (the main view is not a HUD element to move),
 * and skips the bar and side panel, which have their own proper SetRect paths. */
#define SIDE_CAP_H   25    /* native bottom-cap height; the panel clamps its own height UP to
                                   the SUM of its art heights (417 + 25 = 442) - see rz_side_fit_surface */
#define SIDE_NAT_H   442   /* native side-panel height, measured rect [704 0 800 442] */
#define WIN_MAX      48
#define ANCHOR_EDGE  12
#define NAT_W        800
#define NAT_H        600
/* Per painter window: the native PAINT rect (+0x90), the native WINDOW rect (+0x14..0x20), and
 * whether the two disagree.
 *
 * ⭐ Why `child` exists. `+0x90` is PARENT-RELATIVE for a child window, while `+0x14..0x20` is
 * absolute - so for a root the two match and for a child they differ by the parent's origin.
 * Measured at native 2026-09-07 (verify/resize_clicklab/live_resizeio/run.log:388-393):
 *     [1] 0x0D3680B8 paint=[704 0 800 442] window=[704 0 800 442]   <- root, delta (0,0)
 *     [4] 0x0E2D6F80 paint=[0 0 36 442]    window=[704 0 740 442]   <- child, delta (704,0)
 *                                                                      = the side panel's origin
 *     [3] 0x0D42D110 paint=[138 72 147 87] window=[778 508 787 523] <- child, delta (640,436)
 *                                                                      = the MINIMAP's origin
 * A child must NOT be translated: its parent's SetRect already carries it. Translating it anyway
 * double-counts the delta, which is the whole "PAINT/WINDOW DIVERGE + missing side panel" bug.
 * At maximize (dx,dy)=(1120,409) the mod fed SetRect the absolute [1120 409 1156 851] and the
 * engine added the panel's NEW origin (1824,409), landing item [4] at [2944 818 2980 1260] - off
 * a 1920x1009 client, taking every visible side-panel child with it. */
static struct { void *w; LONG nat[4]; LONG natwin[4]; int child; } g_wins[WIN_MAX];
static LONG   g_wins_n;
static int    g_anchor;

/* ---- CLUSTER MODE (SC3RESIZE_CLUSTER=1) -------------------------------------------------------
 * Owner's design, and it is better than stretching: keep every HUD element at its NATIVE size and
 * translate the whole native 800x600 layout into the bottom-right corner, leaving the rest of the
 * bigger window blank.
 *
 * Three things fall out of it:
 *   - **No tiling, so no FPS cost.** The bar is never widened, so SIMUI FUN_10026841's tile loop
 *     never runs long - that loop is the entire measured cost (~46 blits/frame at 2048).
 *   - **No blank stretched regions.** The side panel's black band below its last icon exists because
 *     its 96x417 art does not stretch to a taller window; at native height there is nothing to fill.
 *   - **Relative layout preserved.** A single translation keeps every element's position relative to
 *     the others, so the HUD still reads as one piece.
 *
 * Translation is (liveW - 800, liveH - 600) applied to the cached NATIVE rect every time, so
 * repeated resizes never compound. */
static int    g_input;
/* SC3RESIZE_NOHIT=1 - disable EVERY write to the window +0x80..0x8c rect (all three call sites of
 * rz_win_move_hit). The A arm of the 2026-09-01 experiment in verify/resize_flaggate/.
 *
 * Why this is a real experiment and not a revert: `FUN_1006ddbd` reads +0x80..0x8c ONLY as a width
 * and a height (`param_1 >= [+0x88]-[+0x80]`, `param_2 >= [+0x8c]-[+0x84]`), so translating that
 * rect while preserving its size CANNOT change its verdict [CONFIRMED @ SIMUI 0x1006ddbd]. The write
 * is therefore a no-op for containment - but +0x80/+0x84 are ALSO read by vt+0x98/vt+0x9c and summed
 * up the parent chain by vt+0xdc = FUN_1006dd44 to build the screen->local origin. Writing absolute
 * screen coordinates into a link of a parent-relative sum can DOUBLE-COUNT the offset, which would
 * make the mod's own "fix" the thing that misses. [UNCERTAIN] - that is what this measures. */
static int    g_nohit;
/* SC3RESIZE_NOPARENTFIX=1 - control arm: skip the ancestor-rect widening. */
static int    g_noparentfix;
/* fwd: defined below rz_mini_dock, called from the cluster routine above it */
static void rz_fix_hud_parents(void *leaf, const char *name, LONG cw, LONG ch);
/* fwd: the 2026-09-02 input-geometry fixes, called at the end of the cluster routine */
static void rz_input_geometry(LONG cw, LONG ch, LONG dx, LONG dy);
static void rz_side_children_bottom(void);
static void rz_bar_children_right(void);
static void rz_make_resizable(void);
static int g_fs_on;   /* FULLSCREEN: borderless fullscreen is on (rz_fs_enter) */
/* NATIVE geometry of the bar's contents, captured once before anything moves.
 * The first version SHIFTED children incrementally, which works exactly once: dx
 * depends on the client size, so after a resize the already-moved children failed the
 * "not yet moved" guard and stayed at coordinates that fall outside the smaller bar -
 * owner: "after re-resizing the bottom bar looks broken, no teleprompter, no clickable
 * buttons". Absolute placement from a cached native rect is idempotent by construction
 * and correct at every size. */
#define BARKID_MAX 12
static void  *g_barkid[BARKID_MAX];
static LONG   g_barkid_nat[BARKID_MAX][4];
static int    g_barkid_n;
/* Native positions of the side-panel ITEMS (tool buttons), cached by pointer the first time each is
 * seen at its native y. The item WINDOW (+0x80) and its group-overlay (+0xf4, where the icon draws)
 * must be placed ABSOLUTELY (native + dy), not incrementally: the old `pe[1] += dy` with a `pe[1]<dy`
 * guard re-added the offset whenever dy grew between passes, drifting the icons/hits away from the
 * background-art icons (owner: the hover highlight showed the wrong icon). */
#define SIDEITEM_MAX 48
static struct { void *w; LONG naty; LONG natovl; int has_ovl; } g_sideitem[SIDEITEM_MAX];
/* Flyout sub-tool buttons (SIMUI+0xa917c, inside the full-height page columns): native LOCAL y and the
 * y we last placed, so placement is ABSOLUTE (native + dy) and a recreated or game-moved button is
 * re-cached instead of being pushed twice. */
#define SUBBTN_MAX 160
static struct { void *w; LONG naty; LONG placed; } g_subbtn[SUBBTN_MAX];
static int g_subbtn_n;
static int    g_sideitem_n;
static LONG   g_bar_art_nat[4], g_bar_fill_nat[4], g_bar_info_nat[4][4];
static int    g_bar_art_ok;
/* Native rects of the bottom-right corner widgets (the minimize/restore button and friends), cached
 * by pointer the first time each is seen still at its native position. Relocation must be ABSOLUTE
 * (native+dx), not incremental: the discovery heuristic only matches a widget while it is inside the
 * native bounds, so an incremental move fired once and then the widget was never matched again -
 * stranded at native+dx1 while the window kept growing (owner: "the minimize button is not
 * following"). */
#define CORNER_MAX 12
static struct { void *w; LONG nat[4]; } g_corner[CORNER_MAX];
static int    g_corner_n;
static LONG   g_rci_nat[4];   /* RCI indicator native rect, cached once for absolute y placement */
static int    g_rci_nat_ok;
static void *rz_find_by_vt(void *w, DWORD wantvt, int depth, int *budget);
static void rz_side_fit_surface(DWORD liveH);
static void rz_hud_setrect_w(DWORD wantW);   /* dock the bar, spanning to wantW (0 = full client) */
static void rz_hud_fit_surface(DWORD liveW); /* widen the bar bg+filler source surfaces to liveW */
/* SC3RESIZE_HUDDY - extra downward bias applied to the whole relocated HUD, on top of the
 * (client - native) translate. Owner-tuned to 8 px on 2026-09-02 at 2048x1081: at bias 0 the bar's
 * bottom lands exactly on the client edge and a black strip shows below it; at 8 the bar, RCI,
 * minimap and corner button all sit where the owner wants them.
 * ⚠️ This is a POSITION bias only. HUD art is TOP-ANCHORED in its rect, so a rect taller than the
 * art paints the surplus black - do not implement this by growing rects. Measured: a 72-tall bar
 * (art 56) produced exactly the "black bar below the bottom bar" the owner reported. */
static LONG   g_hud_dy = 0;   /* was 8 to overhang the bar below the client and hide a "black strip"
                                 below it; the present source clamp (PRESENTFIX) removes that strip, so
                                 the +8 only pushed the bar/minimap/RCI/corner bottoms 8px past the
                                 client edge where they clipped. 0 sits them flush (measured clean,
                                 2026-09-03). SC3RESIZE_HUDDY overrides. */
/* SC3RESIZE_SIDEDY - lift the side panel's contents (pages, tabs AND the background art) by this
 * many px from the panel bottom. Owner, 2026-09-02: with 0 the group sat "too shifted down" and
 * three buttons fell out of view. ONE knob feeds both the art placement in rz_side_fit_child and
 * the child move in rz_side_children_bottom, so those two can never drift apart - keeping them in
 * lockstep is the whole reason it is a single global. */
static LONG   g_side_dy;
static int    g_dump_pending;        /* set by the trigger, consumed at the present */
static void  *g_dump_iso;            /* iso captured by the poll for the dumper */
static int    g_minmax_logged;
static int    g_hit_logged;
static int    g_wsnap_logged;
static int    g_reassert_quiet;   /* set during the periodic bar-span re-assert so the idempotent
                                     "already docked / already fitted" skips do not spam the log */
static int    g_thickframe = 1;   /* SC3RESIZE_THICKFRAME=0 leaves the fixed frame */
static int    g_dpiaware = 1;     /* DPIAWARE block: sc3resize.ini [display] dpiaware=0 / SC3RESIZE_DPIAWARE=0 = unaware */
static LONG   g_rt_p3 = -1;       /* SC3RESIZE_RTP3: pin FUN_10009efb arg p3. -1 = field read-back.
                                     Tested 4: did NOT cure the shear, so p3 is not the pitch control;
                                     left as an A/B hook, default off. */
static int    g_sysmem;           /* SC3RESIZE_SYSMEM: zero obj+0x8c before recreate to force a
                                     system-memory surface (tight width*2 pitch, no shear). */
static LONG   g_rt_p7 = -1;       /* SC3RESIZE_RTP7: pin FUN_10009efb arg p7 (obj+0x3c) = the memory
                                     POOL selector. Worker RE 2026-09-03 (FUN_10019273): param_4==0
                                     -> DDSCAPS_SYSTEMMEMORY (tight pitch = width*2 for even widths),
                                     nonzero -> VIDEOMEMORY (driver pads the pitch = shear). Read back
                                     p7=0 on the render target (clean, pitch 2000 at w=1000) and p7=3
                                     on the composite surface (sheared) - the {0,3} pool domain the
                                     worker found. Pinning p7=0 forces system memory => no shear at any
                                     even width, so the 32-snap can drop to a 2px even constraint.
                                     -1 = field read-back (old behaviour). */
static LONG   g_walign = 0;       /* SC3RESIZE_WALIGN: round the recreated surface WIDTH up to this
                                     multiple. TESTED 32: made it WORSE - padding +0x24 to 1024 left
                                     the city BLACK (renderer keys off +0x24) and the composite still
                                     sheared. The real fix snaps the WINDOW client width to a 32-
                                     multiple during the drag (WM_SIZING, g_wsnap), so the surface is
                                     created at an aligned width natively. Default off. */
static LONG   g_wsnap = 0;        /* SC3RESIZE_WSNAP: during a drag, snap the CLIENT width to this
                                     multiple. DEFAULT OFF (0): the "shear at unaligned widths" this was
                                     built to avoid was a bug in the SCREENSHOT tool (screen_grab.py read
                                     the DIB back with a packed stride while GetDIBits pads rows to 4
                                     bytes), NOT in the game - DirectDraw presents each surface with its
                                     own pitch, so the on-screen frame never shears. The snap only added
                                     the "never reaches the cursor" lag. Set >1 to re-enable (A/B). */
/* SC3RESIZE_KIDFIX=0 - A/B control arm: restore the pre-2026-09-07 behaviour of translating
 * CHILD painter windows too, which double-counts the delta (see the g_wins comment). Default
 * ON because the double-translate is a plain arithmetic error, not a trade-off. */
static int    g_kidfix = 1;
/* SC3RESIZE_ARTGUARD=0 - A/B control arm for the fix below. Default ON. */
static int    g_artguard = 1;
/* SC3RESIZE_EDGEFIX=0 - A/B control arm for the edge-scroll band fix in rz_input_geometry (2026-10-05,
 * verify/resize_edgescroll). Default ON. =0 restores the widen-only bounds write with no band rebuild. */
static int    g_edgefix = 1;
static LONG   g_view_nat[4];      /* city view bounds (+0xd4..+0xe0 on the window sub-object) as the
                                     engine set them at native size, cached on first sight */
static int    g_view_nat_ok;
/* SC3RESIZE_EDGESCROLL=1 keeps the game's mouse edge-scroll bands. Default 0: the owner does not want
 * edge scrolling in windowed mode (2026-10-05), and this mod is always windowed. */
static int    g_edgescroll = 0;
static void   rz_edge_off(void);  /* fwd: neutralise the edge bands, defined after rz_find_view */
static int    g_side_span = 1;   /* SC3RESIZE_SIDESPAN (default 1, owner 2026-10-05; =0 opts out): in cluster mode, dock+extend the side panel to
                                     the full client height (background filled down, buttons at the
                                     bottom) instead of translating it at native height. */
static void   rz_side_extend(void);  /* fwd: dock+extend the side panel to full height */
static int    g_bar_span = 1;     /* SC3RESIZE_BARSPAN (default 1, owner 2026-10-05; =0 opts out): in cluster mode, dock+span the bottom bar to
                                     the full client width (filler source widened so the per-frame
                                     tile count does not grow -> the intended FPS fix) instead of
                                     translating the native-width bar. Was default off until measured;
                                     the FPS fix was owner-confirmed in cc687b8. */
static int    g_bltbeat;          /* SC3RESIZE_BLTBEAT: log ddraw Blt calls/sec so the full-width
                                     bar's FPS cost can be read as a number, not inferred. */
static int    g_presentfix = 1;   /* SC3RESIZE_PRESENTFIX=0 disables the present source clamp */
static int    g_presentfix_logged;
static int    g_submove = -1;      /* SC3RESIZE_SUBMOVE: move flyout sub-tool buttons with the panel's dy.
                                     -1 (default) = follow SIDESPAN. 0 / 1 force it (A/B). */
static int    g_rcifix = 1;        /* SC3RESIZE_RCIFIX=0 disables the present-time RCI re-composite */
static int    g_rcifix_logged;
static void  *g_rci_cached;        /* the RCI window, cached across frames (a root child) */
static DWORD  rz_thiscall_ret(void *self, void *fn, const DWORD *a, int n); /* fwd: full EAX return */
static void   rz_repaint_rci(void);                                          /* fwd: present-hook re-blit */
static int    g_presentlog;       /* SC3RESIZE_PRESENTLOG: log the present src/dst rects */
static char   g_dumpdir[MAX_PATH];   /* SC3RESIZE_DUMPDIR: where the surface dumps go */
static int    g_srcrect = 1;      /* SC3RESIZE_SRCRECT=0 disables the tile-step FPS fix (A/B) */
static int    g_side_poll;         /* SC3RESIZE_SIDEPOLL: re-enable the periodic popup correction */
static LONG   g_side_dy_applied;   /* the delta actually used, captured once - see rz_side_children_bottom */
static int    g_sink_logged;  /* one-shot: the sink does not change */   /* resolve the UI event sink once, on the first click */         /* SC3RESIZE_INPUT: log the mouse clamp bounds per click */
static int    g_cluster;
static LONG   g_bar_nat[4], g_side_nat[4];
static int    g_bar_nat_ok, g_side_nat_ok;

/* Dock the minimap by rewriting the dest rect the generic painter reads.
 * FUN_1006d2d0 blits this[0x16] into the rect at this+0x90 [CONFIRMED @ SIMUI 0x1006d2d0], and run
 * 25 measured that rect as [640 436 800 600] - unchanged at 2048x1081, which is exactly why the
 * minimap floats mid-screen when maximized. Move it to the live bottom-right corner, preserving its
 * own size.
 * `[UNCERTAIN]`: whether the painter HONOURS a rewritten +0x90 or recomputes it from a layout parent
 * each frame. If it recomputes, this is a no-op and the log will show the rect reverting - which is
 * a clean falsifier, not an ambiguous result. Unlike the bar and side panel there is no vt+0xc8
 * SetRect in evidence for this class, so the field write is the available lever. */
/* Re-anchor every recorded window from its NATIVE rect to the live client size.
 * Right-edge-anchored windows shift by (liveW - 800); bottom-anchored by (liveH - 600). Computed
 * from the stored native rect every time, so repeated resizes never compound.
 * Skips the bar and the side panel: both have proper framework SetRect paths and moving them here
 * as well would fight those. */
static void rz_anchor_all(void) {
    RECT cr;
    LONG dx, dy, i, moved = 0;
    if (!g_anchor || !g_hwnd || !GetClientRect(g_hwnd, &cr)) return;
    dx = (cr.right - cr.left) - NAT_W;
    dy = (cr.bottom - cr.top) - NAT_H + g_hud_dy;   /* same bottom bias as the bar and the cluster */
    if (dx == 0 && dy == 0) return;
    for (i = 0; i < g_wins_n; i++) {
        void *w = g_wins[i].w;
        LONG *r, *n = g_wins[i].nat;
        LONG ax, ay;
        if (!w || w == g_hud_top || w == g_side_top || IsBadReadPtr(w, 0xa0)) continue;
        if (!rz_win_alive(w)) { g_wins[i].w = NULL; continue; }   /* freed: see rz_win_alive */
        if (g_kidfix && g_wins[i].child) continue;   /* parent-relative: carried by the parent */
        ax = (n[2] >= NAT_W - ANCHOR_EDGE) ? dx : 0;    /* touching the native right edge  */
        ay = (n[3] >= NAT_H - ANCHOR_EDGE) ? dy : 0;    /* touching the native bottom edge */
        if (ax == 0 && ay == 0) continue;               /* left/top anchored - leave it    */
        r = (LONG *)((DWORD)w + 0x90);
        r[0] = n[0] + ax; r[1] = n[1] + ay;
        r[2] = n[2] + ax; r[3] = n[3] + ay;
        /* AND THE AUTHORITATIVE LOCAL RECT, or the cascade undoes this.
         *
         * +0x90 is DERIVED (FUN_1006d8b4 rebuilds it from the local rect), so writing it alone
         * survives only until something cascades - and this mod now cascades deliberately on every
         * resize. Caught by dumping the composited frame: the RCI indicator was sitting at its
         * NATIVE [599 520 640 608] in the middle of the city view, because the cascade had faithfully
         * recomputed its blit dest from a local rect nobody had moved. Same defect I had already
         * fixed for the minimap and missed here. */
        {   LONG *lr = (LONG *)((DWORD)w + 0x80);
            if (!IsBadWritePtr(lr, 0x10) && lr[2] - lr[0] > 0 && lr[3] - lr[1] > 0) {
                lr[0] = n[0] + ax; lr[1] = n[1] + ay;
                lr[2] = n[2] + ax; lr[3] = n[3] + ay;
            }
        }
        moved++;
    }
    logf("ANCHOR> re-anchored %ld of %ld windows (dx=%ld dy=%ld)", moved, g_wins_n, dx, dy);
}

static int rz_thiscall(void *self, void *fn, const DWORD *a, int n);  /* fwd: defined further down */

/* Move one framework window to an absolute rect via its own vt+0xc8 SetRect - the method already
 * proven on both the bar and the side panel. Live-vtable dispatch, guarded, logs what it did. */
/* Move a window's HIT-TEST origin.
 *
 * ⭐ This is the field that made the relocated HUD unclickable. The chain, all confirmed statically:
 *   GZWIND FUN_10020818 -> (sink+0x38)->vt[0x8c] = FUN_1001e748  find-window-at-point
 *     -> child/self vt+0xe4 = SIMUI FUN_1004efcd  point-in-window
 *        -> vt+0xd8 = FUN_1006dd8c   screen->local: subtracts the origin from (x,y)
 *           -> vt+0xdc = FUN_1006dd44  origin = sum of vt+0x98 / vt+0x9c up the parent chain
 *              -> vt+0x98 = `mov eax,[ecx+0x80]`   vt+0x9c = `mov eax,[ecx+0x84]`
 * `[CONFIRMED @ GZWIND 0x10020818, 0x1001e748; SIMUI 0x1004efcd, 0x1006dd8c, 0x1006dd44,
 *   0x1006db74, 0x1006db7b]`
 *
 * So a window carries THREE position representations:
 *   `+0x14..0x20`  the window rect  (what vt+0xc8 SetRect maintains)
 *   `+0x90`        the paint dest   (what the generic painter blits into)
 *   `+0x80/+0x84`  the HIT-TEST origin
 * Moving the first two moves the pixels and leaves input behind - exactly the reported symptom.
 *
 * Self-verifying: only rewrite when the field still holds the OLD position, so if these offsets
 * ever mean something else on some class we refuse rather than corrupt it. */
static void rz_win_move_hit(void *w, const char *name, LONG oldx, LONG oldy, LONG nx, LONG ny) {
    LONG *p;
    if (!w || IsBadReadPtr(w, 0x88)) return;
    if (g_nohit) {   /* arm A: leave +0x80..0x8c exactly as the engine built it */
        p = (LONG *)((DWORD)w + 0x80);
        logf("NOHIT> %s: LEAVING +0x80..0x8c at [%ld %ld %ld %ld] (would have moved origin to %ld,%ld)",
             name, p[0], p[1], p[2], p[3], nx, ny);
        (void)oldx; (void)oldy;
        return;
    }
    /* ⭐ The hit area is a FULL RECT at +0x80(l) +0x84(t) +0x88(r) +0x8c(b), not just an origin.
     * FUN_1006ddbd compares:
     *     height = [+0x8c] - [+0x84];   if (y >= height) miss
     *     width  = [+0x88] - [+0x80];   if (x >= width)  miss
     * `[CONFIRMED @ SIMUI 0x1006ddbd]`
     * Moving left/top ALONE leaves right/bottom at their old values, so width and height come out
     * NEGATIVE and every click misses - which is precisely what "still not clickable" was, after
     * the position fields all read correct. Translate the whole rect, preserving its size. */
    p = (LONG *)((DWORD)w + 0x80);
    {
        LONG cw = p[2] - p[0], ch = p[3] - p[1];
        logf("HIT> %s: rect +0x80..0x8c = [%ld %ld %ld %ld] (%ldx%ld)  want origin (%ld,%ld)",
             name, p[0], p[1], p[2], p[3], cw, ch, nx, ny);
        if (p[0] == nx && p[1] == ny && cw > 0 && ch > 0) return;   /* already correct */
        if (cw <= 0 || ch <= 0) {
            /* Non-positive extent means left/top were moved without right/bottom - the exact bug
               this function now fixes. Refuse rather than invent a size: within one run the first
               move always sees a clean rect, so this can only mean the offsets are not what we
               think on this class. */
            logf("HIT> %s: extent %ldx%ld is non-positive - refusing to guess a size", name, cw, ch);
            return;
        }
        p[0] = nx;      p[1] = ny;
        p[2] = nx + cw; p[3] = ny + ch;
        logf("HIT> %s: hit rect -> [%ld %ld %ld %ld]", name, p[0], p[1], p[2], p[3]);
    }
}

static void rz_win_setrect(void *w, const char *name, LONG x1, LONG y1, LONG x2, LONG y2) {
    DWORD *win = (DWORD *)w, *vt;
    DWORD a[4];
    if (!win || IsBadReadPtr(win, 0xcc)) { logf("CLUSTER> %s: unreadable", name); return; }
    vt = *(DWORD **)win;
    if (!vt || IsBadReadPtr(vt, 0xcc) || !vt[0xc8/4]) {
        logf("CLUSTER> %s: no vt+0xc8", name); return;
    }
    logf("CLUSTER> %s [%ld %ld %ld %ld] -> [%ld %ld %ld %ld]", name,
         (LONG)win[0x14/4], (LONG)win[0x18/4], (LONG)win[0x1c/4], (LONG)win[0x20/4], x1, y1, x2, y2);
    {   LONG ox = (LONG)win[0x14/4], oy = (LONG)win[0x18/4];
        a[0] = (DWORD)x1; a[1] = (DWORD)y1; a[2] = (DWORD)x2; a[3] = (DWORD)y2;
        rz_thiscall(w, (void *)vt[0xc8/4], a, 4);
        rz_win_move_hit(w, name, ox, oy, x1, y1);   /* SetRect does not touch +0x80/+0x84 */
    }
}

/* Translate the whole native HUD into the bottom-right corner, at native size. */
/* The height the extended side panel should fill: the client height, but clamped to the MINIMAP's
 * top so the panel stops above it instead of hiding the lower buttons behind it. */
static LONG rz_side_target_h(void) {
    RECT cr;
    LONG h;
    if (!g_hwnd || !GetClientRect(g_hwnd, &cr)) return 0;
    h = cr.bottom - cr.top;
    if (g_mini && !IsBadReadPtr(g_mini, 0x90)) {
        LONG mtop = ((LONG *)((DWORD)g_mini + 0x80))[1];
        LONG mbot = ((LONG *)((DWORD)g_mini + 0x80))[3];
        /* Only follow the minimap once it is DOCKED at the client bottom. While it still sits at its native spot
           (436..600 in a larger client) this gave the native height, the panel surface was rebuilt at 442 and
           again at full height ~2 ms later, and the panel's paint read a null surface between the two (owner crash
           2026-10-08, GZGraphicD+0x18C7A from SIMUI+0x4E6B0). */
        if (mbot != h) return h;
        /* +6: natively the 442-tall panel overlaps the minimap (top 436) by 6 px, which is what joins the two
           frames. Stopping exactly at the minimap top left a visible seam (owner 2026-10-07). */
        if (mtop > 0 && mtop < h) h = mtop + 6 <= h ? mtop + 6 : h;
    }
    return h;
}

static void rz_cluster_layout(void) {
    RECT cr;
    LONG dx, dy, i, moved = 0, skipped_kids = 0;
    if (!g_cluster || !g_hwnd || !GetClientRect(g_hwnd, &cr)) return;
    dx = (cr.right - cr.left) - NAT_W;
    dy = (cr.bottom - cr.top) - NAT_H;
    /* CLAMP, do not early-return. Shrinking back toward native must RE-APPLY native positions:
     * the HUD was translated by the last (larger) offset, so bailing here on dx<=0&&dy<=0 leaves the
     * side panel stuck at that offset - pushed off the bottom - which is the "bar breaks / panel
     * disappears after re-resizing" the owner reported (measured 2026-09-03: 960x720 -> 800x600 left
     * the side panel translated 120px down, off-screen). Never translate the native HUD to a NEGATIVE
     * offset (it would go smaller than native and clip); at exactly native, offset 0 restores it. */
    if (dx < 0) dx = 0;
    if (dy < 0) dy = 0;
    if (dy > 0) dy += g_hud_dy;   /* owner-tuned bottom bias, only when enlarged; native restores clean */

    /* Cache each framework window's native rect the first time we see it, before anything moves. */
    if (!g_bar_nat_ok && g_hud_top && !IsBadReadPtr(g_hud_top, 0x24)) {
        DWORD *h = (DWORD *)g_hud_top;
        g_bar_nat[0] = (LONG)h[0x14/4]; g_bar_nat[1] = (LONG)h[0x18/4];
        g_bar_nat[2] = (LONG)h[0x1c/4]; g_bar_nat[3] = (LONG)h[0x20/4];
        g_bar_nat_ok = 1;
        logf("CLUSTER> cached bar native [%ld %ld %ld %ld]",
             g_bar_nat[0], g_bar_nat[1], g_bar_nat[2], g_bar_nat[3]);
    }
    if (!g_side_nat_ok && g_side_top && !IsBadReadPtr(g_side_top, 0x24)) {
        DWORD *s = (DWORD *)g_side_top;
        g_side_nat[0] = (LONG)s[0x14/4]; g_side_nat[1] = (LONG)s[0x18/4];
        g_side_nat[2] = (LONG)s[0x1c/4]; g_side_nat[3] = (LONG)s[0x20/4];
        g_side_nat_ok = 1;
        logf("CLUSTER> cached side native [%ld %ld %ld %ld]",
             g_side_nat[0], g_side_nat[1], g_side_nat[2], g_side_nat[3]);
    }

    if (g_bar_span) {
        /* FULL-WIDTH BAR in cluster mode: dock+span the bar object to the whole client width, widen
         * its background+filler SOURCE surfaces (so the engine's per-frame tile count does not grow
         * with the width - the FPS fix), then slide the console/RCI/info to the right end. This is
         * the same sequence the non-cluster ship path uses; here it replaces the native-width
         * translate so the bottom-left gap is filled. */
        RECT bcr;
        rz_hud_setrect_w(0);
        if (g_hwnd && GetClientRect(g_hwnd, &bcr))
            rz_hud_fit_surface((DWORD)(bcr.right - bcr.left));
        rz_bar_children_right();
    } else if (g_bar_nat_ok)
        rz_win_setrect(g_hud_top, "bottom bar", g_bar_nat[0] + dx, g_bar_nat[1] + dy,
                       g_bar_nat[2] + dx, g_bar_nat[3] + dy);
    if (g_side_span) {
        /* FULL-HEIGHT SIDE PANEL in cluster mode: dock+extend the panel to the whole client height,
         * fill its background surface down the new height, then push the buttons to the bottom. Same
         * sequence the non-cluster ship path uses; replaces the native-height translate so the
         * vertical bar is filled instead of floating at native size. */
        LONG sideH;
        rz_side_extend();
        sideH = rz_side_target_h();
        if (sideH > 0) rz_side_fit_surface((DWORD)sideH);
        rz_side_children_bottom();
    } else if (g_side_nat_ok)
        rz_win_setrect(g_side_top, "side panel", g_side_nat[0] + dx, g_side_nat[1] + dy,
                       g_side_nat[2] + dx, g_side_nat[3] + dy);

    /* Everything else the generic painter draws.
     *
     * ⚠️ Writing ONLY `+0x90` moves the PAINT and leaves HIT-TESTING behind - owner-reported:
     * "the clickable area is not scaling either". `+0x90` is the blit destination; the window's own
     * rect lives at `this+0x14..0x20`, which is what `vt+0xc8` SetRect maintains and what input
     * picking reads. The bar and side panel were always clickable because they went through SetRect.
     *
     * So prefer SetRect here too, and fall back to the raw `+0x90` write only when the class has no
     * `vt+0xc8`. Belt and braces: after SetRect, also translate `+0x90` if SetRect did not move it,
     * since these classes are not all guaranteed to keep the two in sync. */
    for (i = 0; i < g_wins_n; i++) {
        void *w = g_wins[i].w;
        LONG *r, *n = g_wins[i].nat;
        DWORD *vt;
        if (!w || w == g_hud_top || w == g_side_top || IsBadReadPtr(w, 0xa0)) continue;
        if (!rz_win_alive(w)) {   /* freed (a closed dialog): calling SetRect on it faulted, see rz_win_alive */
            logf("CLUSTER>   [%ld] 0x%08lX no longer in the window tree - dropped", i, (DWORD)w);
            g_wins[i].w = NULL;
            continue;
        }
        /* ⭐ CHILD WINDOWS ARE CARRIED BY THEIR PARENT - do not translate them.
         *
         * Their `+0x90` is parent-relative, so `vt+0xc8` SetRect adds the parent's origin. Feeding
         * it an absolutely-translated rect applies the delta TWICE. That is what put the side
         * panel's contents at x=2944 on a 1920-wide client and made the panel look absent (the
         * container moved fine; everything visible inside it left the screen).
         * `SC3RESIZE_KIDFIX=0` is the A/B control arm - it restores the old double-translate. */
        if (g_kidfix && g_wins[i].child) {
            logf("CLUSTER>   [%ld] 0x%08lX CHILD of a parent at (%ld,%ld) - left at its "
                 "parent-relative [%ld %ld %ld %ld], parent's move carries it",
                 i, (DWORD)w, g_wins[i].natwin[0] - n[0], g_wins[i].natwin[1] - n[1],
                 n[0], n[1], n[2], n[3]);
            skipped_kids++;
            continue;
        }
        vt = *(DWORD **)w;
        if (vt && !IsBadReadPtr(vt, 0xcc) && vt[0xc8/4]) {
            DWORD a[4];
            a[0] = (DWORD)(n[0] + dx); a[1] = (DWORD)(n[1] + dy);
            a[2] = (DWORD)(n[2] + dx); a[3] = (DWORD)(n[3] + dy);
            rz_thiscall(w, (void *)vt[0xc8/4], a, 4);
        }
        r = (LONG *)((DWORD)w + 0x90);
        if (r[0] != n[0] + dx || r[1] != n[1] + dy) {   /* SetRect did not carry the draw rect */
            r[0] = n[0] + dx; r[1] = n[1] + dy;
            r[2] = n[2] + dx; r[3] = n[3] + dy;
        }
        rz_win_move_hit(w, "painter window", n[0], n[1], n[0] + dx, n[1] + dy);
        moved++;
    }
    logf("CLUSTER> translated %ld painter windows by (%ld,%ld), left %ld child window(s) to their parents%s; HUD kept at native size",
         moved, dx, dy, skipped_kids, g_kidfix ? "" : " [KIDFIX OFF - control arm]");
    {   /* Report paint rect vs WINDOW rect for the first few, so a future divergence is visible in
           the log instead of only on screen - this run's clickability bug was invisible in the log. */
        LONG k;
        for (k = 0; k < g_wins_n; k++) {   /* ALL of them: capping at 6 hid the windows the side-panel buttons live in */
            DWORD *w = (DWORD *)g_wins[k].w;
            LONG *p;
            if (!w || IsBadReadPtr(w, 0xa0)) continue;
            p = (LONG *)((DWORD)w + 0x90);
            logf("CLUSTER>   [%ld] 0x%08lX paint=[%ld %ld %ld %ld] window=[%ld %ld %ld %ld]%s",
                 k, (DWORD)w, p[0], p[1], p[2], p[3],
                 (LONG)w[0x14/4], (LONG)w[0x18/4], (LONG)w[0x1c/4], (LONG)w[0x20/4],
                 /* A CHILD's +0x90 is parent-relative, so paint != window is its CORRECT state -
                    flagging it as a divergence was noise that hid the real ones. Only an
                    unexplained mismatch on a ROOT is a defect now. */
                 (p[0] == (LONG)w[0x14/4] && p[1] == (LONG)w[0x18/4]) ? ""
                     : (g_wins[k].child ? "   (child: parent-relative, expected)"
                                        : "   <<< PAINT/WINDOW DIVERGE"));
        }
    }
    {   /* THE CLICKABILITY FIX. Widen every ancestor of the relocated windows so the router's
           per-child `vt+0xe4` gate can pass.

           ⚠️ CORRECTION 2026-09-07: this comment used to add "and the recursion that reaches the
           HUD can start". That is FALSE and it mattered - it is why widening was applied to art
           windows too, which broke the side panel. `vt+0xe4` (`FUN_1006de62`) is a HIT-TEST against
           the object's own +0x14..0x20 [CONFIRMED @ SIMUI 0x1006de62], called only from the INPUT
           walks `FUN_1006ccda` / `FUN_1006d1af` [CONFIRMED @ SIMUI 0x1006ccda, 0x1006d1af]. The
           PAINT walk (`FUN_1006d2d0`) iterates this+0x34 and calls every child's vt+0x148
           unconditionally - no gate, no clip, no early exit [CONFIRMED @ SIMUI 0x1006d2d0]. A
           window outside its parent's rect still PAINTS; it just gets no mouse input. So this walk
           is an INPUT fix only, and must never grow a window that owns a surface.
           `SC3RESIZE_NOPARENTFIX=1` is the A/B control arm. */
        LONG k, cw = cr.right - cr.left, chh = cr.bottom - cr.top;
        if (g_noparentfix) {
            logf("PARENT> SKIPPED (SC3RESIZE_NOPARENTFIX=1) - control arm");
        } else {
            for (k = 0; k < g_wins_n && k < 8; k++)
                rz_fix_hud_parents(g_wins[k].w, "win", cw, chh);
            if (g_mini) rz_fix_hud_parents(g_mini, "minimap", cw, chh);
        }
    }
}

/* ⭐⭐⭐ THE CLICKABILITY FIX — widen the HUD's ANCESTOR containers.
 *
 * Root cause, measured 2026-09-01 (verify/resize_flaggate/ROOTCAUSE_RESULTS.md + parent.json):
 * the relocated HUD windows hang off a container whose OWN rect is still the pre-resize
 * `[0 0 800 600]`. The event router normal clicks take is `FUN_1001ec22` (= base vt+0x130,
 * reached because `sink+0x28`/`sink+0x30` are both NULL in normal play), and it recurses into a
 * child ONLY if that child passes `vt+0xe4`, a point-in-its-OWN-rect test:
 *
 *     if ((*child->vt[0x100])() && (*child->vt[0xe4])(ev[1], ev[2]))
 *         return (*child->vt[0x130])(ev);
 *     `[CONFIRMED @ GZWIND 0x1001ec22]`
 *
 * So a click outside the old 800x600 box fails at the CONTAINER and the recursion that would
 * reach the HUD never starts - no matter how correct the HUD's own rect is. That is why every
 * previous fix failed, and why `FUN_1001e748` (the vt+0x8c walk) found the bar perfectly: that
 * walk gates only on `vt+0xf0(1)` and does NO parent rect test `[CONFIRMED @ GZWIND 0x1001e748]`.
 *
 * Parent is `win+0x3c`, byte-proven: base `vt+0x2c` is `8b 41 3c c3` = `mov eax,[ecx+0x3c]; ret`
 * `[CONFIRMED @ GZWIND 0x1001e210]`. Measured chain:
 *     minimap [1888 917 2048 1081] -> 0x602960 [0 0 800 600] -> root [0 0 800 600] -> 0
 *
 * Why a DIRECT field write and not `vt+0xc8` SetRect: only `+0x14..0x20` gates the routing
 * (`vt+0xe4` = `FUN_1001f8ef` compares exactly those). SetRect on a CONTAINER may relayout or
 * repaint its children and could undo the cluster placement; this touches the four fields the
 * router reads and nothing else. Expect-or-refuse: widen only, never shrink, and only when the
 * rect is actually too small.
 *
 * The root itself (parent == NULL) is deliberately NOT touched: `FUN_10020818` calls
 * `root->vt[0x130]` directly with no geometry test, so the root's rect does not gate anything. */
static void rz_fix_hud_parents(void *leaf, const char *name, LONG cw, LONG ch) {
    void *cur = leaf;
    int hop;
    if (!leaf || cw <= 0 || ch <= 0) return;
    for (hop = 0; hop < 12; hop++) {
        void *par;
        LONG *r;
        if (!cur || IsBadReadPtr(cur, 0x40)) return;
        par = *(void **)((DWORD)cur + 0x3c);
        if (!par) return;                       /* reached the root - leave it alone */
        if (IsBadReadPtr(par, 0x24)) return;
        r = (LONG *)((DWORD)par + 0x14);
        if (r[2] - r[0] <= 0 || r[3] - r[1] <= 0) {
            if (!g_reassert_quiet)
                logf("PARENT> %s hop %d: 0x%08lX rect [%ld %ld %ld %ld] non-positive - refusing",
                     name, hop, (DWORD)par, r[0], r[1], r[2], r[3]);
            return;
        }
        /* ⭐ NEVER WIDEN A WINDOW THAT BLITS ART (2026-09-07, verify/resize_sidekidfix).
         *
         * This walk exists to let the router's per-child `vt+0xe4` gate pass, and for a layout
         * CONTAINER growing the rect is free. For a window that blits a fixed-size surface it is
         * destructive: the blit destination stops matching the source and the window paints
         * NOTHING.
         *
         * That is the whole "side panel missing when maximized" bug, and it is in this log:
         *   PARENT> win hop 0: 0x0D34F698 ABS [1952 481 2048 923] LOCAL [1952 481 2048 923]
         *                                                                     -> 2048x1081
         * The cluster step had just placed the panel correctly at [1952 481 2048 923], matching
         * its 96x442 surface; this walk then stretched it to 96x600 and the panel vanished.
         * Proven by poking the rect back to [1952 481 2048 923] on the live object - the panel,
         * its background art and its buttons all reappeared with no other change.
         *
         * Why it needed a tool-button CLICK first: the panel only becomes an ANCESTOR once its
         * page children exist, and those are created by clicking a tool button. Before that the
         * panel is never on this walk, which is exactly why maximizing on a fresh load looked fine.
         *
         * Discriminator: a non-NULL surface at `+0x58` - the field FUN_1006d2d0 blits
         * `[CONFIRMED @ SIMUI 0x1006d2d0]`. Measured in the native dump: the panel had
         * surf=0xf6aaca8; both layout ancestors (0x00640BA8, 0x005A6040) had NULL. The mod's own
         * managed HUD windows are named explicitly as belt-and-braces.
         *
         * CONTINUE up the chain rather than returning - the containers above still need widening
         * or the gate fix regresses. */
        if (g_artguard) {
            void *surf = NULL;
            if (!IsBadReadPtr((void *)((DWORD)par + 0x5c), 4))
                surf = *(void **)((DWORD)par + 0x58);
            if (surf || par == g_side_top || par == g_hud_top || par == g_mini) {
                if (!g_reassert_quiet)
                    logf("PARENT> %s hop %d: 0x%08lX SKIPPED - blits art (surface 0x%08lX%s); "
                         "widening it to %ldx%ld would break its blit. rect left [%ld %ld %ld %ld]",
                         name, hop, (DWORD)par, (DWORD)surf,
                         par == g_side_top ? ", the SIDE PANEL" :
                         par == g_hud_top ? ", the BOTTOM BAR" :
                         par == g_mini ? ", the MINIMAP" : "",
                         cw, ch, r[0], r[1], r[2], r[3]);
                cur = par;
                continue;
            }
        }
        if (r[2] < cw || r[3] < ch) {
            /* ⭐ WIDEN THE AUTHORITATIVE LOCAL RECT TOO (+0x80..+0x8c), not only the derived
             * absolute one at +0x14.
             *
             * Measured 2026-09-02 with a 20 ms sampler: an ancestor read LOCAL [0 0 800 600]
             * against the ABS [0 0 2048 1081] this code had poked. The framework treats +0x80 as
             * the only storage and rebuilds +0x14 from it (`FUN_1006c61b`), so the poke survives
             * only until the next cascade - and every absolute rect downstream is computed from
             * the stale local one. The tool flyout anchors on an item's ABSOLUTE rect
             * `[CONFIRMED @ SIMUI 0x1004ec95]`, which is why popups landed wrong.
             * Widen-only in both fields; the +0x14 write stays so nothing regresses if a given
             * ancestor class does not implement the cascade slot. */
            LONG *lr = (LONG *)((DWORD)par + 0x80);
            if (!g_reassert_quiet)
                logf("PARENT> %s hop %d: 0x%08lX ABS [%ld %ld %ld %ld] LOCAL [%ld %ld %ld %ld] -> %ldx%ld",
                     name, hop, (DWORD)par, r[0], r[1], r[2], r[3],
                     lr[0], lr[1], lr[2], lr[3], cw, ch);
            if (r[2] < cw) r[2] = cw;
            if (r[3] < ch) r[3] = ch;
            if (!IsBadWritePtr(lr, 0x10)) {
                if (lr[2] - lr[0] > 0 && lr[3] - lr[1] > 0) {   /* only a sane rect */
                    if (lr[2] < cw) lr[2] = cw;
                    if (lr[3] < ch) lr[3] = ch;
                }
            }
        } else if (!g_reassert_quiet) {
            logf("PARENT> %s hop %d: 0x%08lX [%ld %ld %ld %ld] already covers %ldx%ld",
                 name, hop, (DWORD)par, r[0], r[1], r[2], r[3], cw, ch);
        }
        cur = par;
    }
}

/* ⭐⭐⭐ INPUT GEOMETRY — the four stale rects that survived the HUD work, 2026-09-01/02.
 *
 * All four were found the same way: the mod widened the rects it knew about, the owner played the
 * game, and each remaining rect announced itself as a dead input path. All four are owner-verified
 * fixed in a running game. Full record: verify/resize_clicklab/SESSION.md.
 *
 * There is no single "window size" in this engine. A window carries four independent position
 * representations and the city view carries two more, each read by different code:
 *
 *   1. ROOT `+0x88/+0x8c`   the hover label is placed at the cursor and then CLAMPED into the root
 *      window's extent, read through `vt+0xa0`/`vt+0xa4`. Stale, it pins the label to
 *      right = 798 (= 800-2) and top <= 582 (= 600-2-16, label height 16). Measured across 51
 *      samples before the fix and again after: right edge 798 -> 2000, top 582 -> 1036.
 *      `[CONFIRMED @ SC3U 0x00443331, 0x00441d3e, 0x00441d45]`
 *      Note rz_fix_hud_parents deliberately stops one hop short of the root, so nothing had ever
 *      written these two.
 *
 *   2. VIEW `+0x1c/+0x20`   the view's hit test rejects any point outside `this+0x14..+0x20`, so a
 *      stale rect makes the MAP DEAD outside the old viewport - no zoning, no picking.
 *      `[CONFIRMED @ SIMSPR 0x1004ecd3]`  Traced per click: inside -> `vt+0xe4` ret=1 and the
 *      handler runs; outside -> ret=0 and the handler is never entered.
 *
 *   3. VIEW `+0xd4..+0xe0`  a DIFFERENT rect, and the one that killed the camera. `FUN_1004947d`
 *      tests every mouse-move against it and calls `FUN_1004a37e` -> `FUN_10042cfe(this,0,0,0)`
 *      when the point is outside, which zeroes the right-drag anchor `+0x1ec/+0x1ee` and both
 *      velocities `+0x1f4/+0x1f8`. So every drag-move outside the old viewport DISARMED the pan.
 *      Measured stale at [0 0 704 544] = native minus the side panel and the bar.
 *      `[CONFIRMED @ SIMSPR 0x1004947d, 0x1004a37e, 0x10042cfe]`
 *
 *   4. NATIVE-CORNER WIDGETS hanging off the ROOT rather than off the HUD tree the cluster routine
 *      walks - which is why they were never relocated (owner: "a minimize button on the old
 *      viewport position"). Moved through the framework's own `vt+0xc8` SetRect.
 *
 * Two mistakes from that day, both encoded here:
 *   ⚠️ Poking `+0x14..+0x20` on a widget moves the HIT TEST and leaves the PIXELS behind (owner:
 *      "the functionality moved, visually the button is still on the original position"). Use
 *      SetRect for anything that has to be seen.
 *   ⚠️ SetRect on a container PROPAGATES to its children. Calling it again on the child
 *      double-moves it - a 26x26 button landed at [4044 2110]. Parents only, which is why this
 *      walks the root's DIRECT children and does not recurse.
 *
 * Edge-scroll bands `+0x178..+0x1c4`: now rebuilt here (2026-10-05, SC3RESIZE_EDGEFIX), see the
 * EDGE-SCROLL BAND comment in rz_input_geometry. Item 3's bounds are set from the native rect + delta
 * rather than widened to the client, because the same field is the bands' source.
 *
 * NOT fixed here, deliberately, documented in SESSION.md:
 *   - The ghost strip on the incremental scroll path, which is a PRESENT asymmetry inside
 *     `FUN_10006226`, not a geometry problem. `[CONFIRMED @ SIMSPR 0x10006226, 0x1000e058,
 *     0x1000e206]`
 */
static void *rz_find_view(void *w, DWORD want_e4, int depth, int *budget) {
    void *head, *n;
    int guard = 0;
    if (!w || depth > 8 || *budget <= 0 || IsBadReadPtr(w, 0x40)) return NULL;
    head = *(void **)((DWORD)w + 0x34);
    if (!head || IsBadReadPtr(head, 4)) return NULL;
    n = *(void **)head;
    while (n && n != head && guard++ < 500 && *budget > 0) {
        void *cw;
        if (IsBadReadPtr(n, 0x0c)) break;
        cw = *(void **)((DWORD)n + 8);
        (*budget)--;
        if (cw && !IsBadReadPtr(cw, 0xe4)) {
            DWORD *vt = *(DWORD **)cw;
            /* vt+0xe4 alone is NOT unique: on 2026-10-05, with the water-structure picker open, this
             * matched an object whose outer vtable was 0x94003A00 (verify/resize_maxcrash/run.log,
             * "REFUSED band rebuild") - likely the dialog's building preview. Also require the CITY VIEW
             * outer vtable SIMSPR+0x67894 at cw-4 (constructor at SIMSPR RVA 0x486d2 installs it there).
             * want_e4 is SIMSPR+0x4ecd3, so the module base is want_e4 - 0x4ecd3. */
            if (vt && !IsBadReadPtr(vt, 0xe8) && vt[0xe4 / 4] == want_e4 &&
                !IsBadReadPtr((void *)((DWORD)cw - 4), 4) &&
                *(DWORD *)((DWORD)cw - 4) == want_e4 - 0x4ecd3 + 0x67894) return cw;
            {   void *hit = rz_find_view(cw, want_e4, depth + 1, budget);
                if (hit) return hit;   }
        }
        n = *(void **)n;
    }
    return NULL;
}

/* ⭐ NO EDGE SCROLLING IN WINDOWED MODE (owner, 2026-10-05). SC3RESIZE_EDGESCROLL=1 keeps it.
 *
 * The band test `SIMSPR FUN_10043a38` (outer vt+0x40) clears all four edge flags and sets nothing when
 * the point is INSIDE the inner rect `outer+0x178..+0x184` `[CONFIRMED @ SIMSPR 0x10043a38]`. So an
 * inner rect that covers every possible coordinate makes the bands inert. The other branch of the same
 * function (taken while `+0x1e6` is set) is the right-drag pan, and it never reads these fields, so
 * panning is untouched. Arrow-key scrolling reads the keyboard, not the bands, so it is untouched too.
 * The engine rewrites the inner rect from `FUN_10043989` (load, event 0x624a8241, and our EDGEFIX
 * rebuild), so this is re-asserted from rz_poll rather than written once. Writes only on a mismatch. */
/* The city view window sub-object (outer = view - 4), cached and revalidated by BOTH vtables on every
 * call, so a freed or reused pointer is never written through. NULL if not present. */
static void *rz_city_view(void) {
    static void *view;
    DWORD ss = (DWORD)GetModuleHandleA("SIMSPR.DLL");
    if (!ss) return NULL;
    if (view) {
        DWORD *vt = IsBadReadPtr(view, 4) ? NULL : *(DWORD **)view;
        if (!vt || IsBadReadPtr(vt, 0xe8) || vt[0xe4 / 4] != ss + 0x4ecd3 ||
            IsBadReadPtr((void *)((DWORD)view - 4), 4) ||
            *(DWORD *)((DWORD)view - 4) != ss + 0x67894) view = NULL;
    }
    if (!view) {
        DWORD gz = (DWORD)GetModuleHandleA("GZGraphicD.dll");
        DWORD *win, *sink, *root;
        int budget = 3000;
        if (!gz || IsBadReadPtr((void *)(gz + 0x6cdb8), 4)) return NULL;
        win = *(DWORD **)(gz + 0x6cdb8);
        if (!win || IsBadReadPtr(win, 0x48) || win[0] != gz + 0x1f740) return NULL;
        sink = (DWORD *)win[0x30 / 4];
        if (!sink || IsBadReadPtr(sink, 0x3c)) return NULL;
        root = (DWORD *)sink[0x38 / 4];
        if (!root || IsBadReadPtr(root, 0x40)) return NULL;
        view = rz_find_view(root, ss + 0x4ecd3, 0, &budget);   /* checks both vtables */
    }
    return view;
}

static void rz_edge_off(void) {
    void *view;
    LONG *in;
    if (g_edgescroll) return;
    view = rz_city_view();
    if (!view) return;
    {   void *outer = (void *)((DWORD)view - 4);
        if (IsBadWritePtr(outer, 0x1c8)) return;
        in = (LONG *)((DWORD)outer + 0x178);
        if (in[0] != -0x7fff || in[1] != -0x7fff || in[2] != 0x7fff || in[3] != 0x7fff) {
            /* Direction flags +0x1e1..+0x1e4 are NOT cleared here: the arrow keys drive the same flags,
               and the band test clears them itself on the next mouse move. */
            static int writes;
            if (writes++ < 8)
                logf("EDGE> edge scrolling OFF (windowed): inner [%ld %ld %ld %ld] -> covers all",
                     in[0], in[1], in[2], in[3]);
            in[0] = -0x7fff; in[1] = -0x7fff; in[2] = 0x7fff; in[3] = 0x7fff;
        }
    }
}

/* ⭐ MAP INPUT PAST 800x600 (2026-10-05, verify/resize_mapinput). SC3RESIZE_VIEWFIX=0 = old behaviour.
 *
 * The city view's hit test `vt+0xe4` = `SIMSPR FUN_1004ecd3` rejects any point outside its DERIVED rect
 * `+0x14..+0x20` `[CONFIRMED @ SIMSPR 0x1004ecd3]`. The mod widened that rect, but the cascade (root
 * vt+0x14c, run after rz_input_geometry and again from rz_side_children_bottom) rebuilds every derived
 * rect from the LOCAL rect `+0x80..+0x8c` `[CONFIRMED @ SIMUI 0x1006c61b]`, and the view's local rect
 * stayed [0 0 800 600]. Measured live at 1920x1009: hit = local = [0 0 800 600]; posted moves at
 * (1792,336) reached the view 0 times, and 3 times after a poke of the hit rect
 * (verify/resize_edgescroll/T/poke.txt). So both rects are written, EXACT to the client in both
 * directions. Direct field writes, not SetRect: the view owns no SIMUI paint surface (paint rect +0x90
 * reads [0 0 0 0]) and a SetRect would provoke the relayout that clobbers the view bounds. Re-asserted
 * from rz_poll so an engine relayout cannot win. */
static int g_viewfix = 1;
static void rz_view_rect_assert(LONG cw, LONG ch) {
    void *view;
    LONG *loc, *hit;
    static int writes;
    if (!g_viewfix || cw <= 0 || ch <= 0) return;
    view = rz_city_view();
    if (!view || IsBadWritePtr(view, 0x90)) return;
    loc = (LONG *)((DWORD)view + 0x80);
    hit = (LONG *)((DWORD)view + 0x14);
    if (loc[0] != 0 || loc[1] != 0 || loc[2] != cw || loc[3] != ch ||
        hit[0] != 0 || hit[1] != 0 || hit[2] != cw || hit[3] != ch) {
        if (writes++ < 12)
            logf("VIEW> city view 0x%08lX local [%ld %ld %ld %ld] hit [%ld %ld %ld %ld] -> [0 0 %ld %ld]",
                 (DWORD)view, loc[0], loc[1], loc[2], loc[3], hit[0], hit[1], hit[2], hit[3], cw, ch);
        loc[0] = 0; loc[1] = 0; loc[2] = cw; loc[3] = ch;
        hit[0] = 0; hit[1] = 0; hit[2] = cw; hit[3] = ch;
    }
}

static int rz_cascade_derived(void);   /* fwd: defined below */

/* The GZWIND root window (the top of the SIMUI/GZWIND tree), or NULL. */
static void *rz_ui_root(void) {
    DWORD gz = (DWORD)GetModuleHandleA("GZGraphicD.dll");
    DWORD *win, *sink, *root;
    if (!gz || IsBadReadPtr((void *)(gz + 0x6cdb8), 4)) return NULL;
    win = *(DWORD **)(gz + 0x6cdb8);
    if (!win || IsBadReadPtr(win, 0x48) || win[0] != gz + 0x1f740) return NULL;
    sink = (DWORD *)win[0x30 / 4];
    if (!sink || IsBadReadPtr(sink, 0x3c)) return NULL;
    root = (DWORD *)sink[0x38 / 4];
    if (!root || IsBadReadPtr(root, 0x40)) return NULL;
    return root;
}

/* Is `want` still a window in the live tree? Walks children from `w` (child list +0x34, node +0 next,
 * +8 child). Needed because IsBadReadPtr cannot tell a FREED window from a live one: freed heap is
 * still readable. Owner hand test 2026-10-05: after a dialog was closed, rz_cluster_layout called
 * SetRect on its freed object and faulted in GZWIND+0x1EF7A reading 0xDFDB3AD3
 * (verify/handtest_1005/run.log:10597). */
static int rz_tree_has(void *w, void *want, int depth, int *budget) {
    void *head, *n;
    int guard = 0;
    if (!w || depth > 6 || *budget <= 0 || IsBadReadPtr(w, 0x40)) return 0;
    head = *(void **)((DWORD)w + 0x34);
    if (!head || IsBadReadPtr(head, 4)) return 0;
    n = *(void **)head;
    while (n && n != head && guard++ < 500 && *budget > 0) {
        void *c;
        if (IsBadReadPtr(n, 0x0c)) break;
        c = *(void **)((DWORD)n + 8);
        (*budget)--;
        if (c == want) return 1;
        if (c && rz_tree_has(c, want, depth + 1, budget)) return 1;
        n = *(void **)n;
    }
    return 0;
}
static int rz_win_alive(void *want) {
    void *root = rz_ui_root();
    int budget = 6000;
    if (!want || !root) return 0;
    if (want == root) return 1;
    return rz_tree_has(root, want, 0, &budget);
}

/* ⭐ DIALOGS FOLLOW THE WINDOW (owner hand test 2026-10-05, verify/resize_dialogs).
 *
 * Measured: dialogs are SIMUI+0xa4d64 windows, either direct children of the root (Reunirse
 * [8 8 391 362], budget [102 32 602 512], at the SAME fixed spots at 800x600 and at 1680x979) or children
 * of the full-client HUD container SC3U.exe+0xd32d0 (snapshots, centered at creation). Each is created
 * ONCE and never re-placed: snapshots opened maximized and re-opened at 800x600 sat at
 * [584 309 1096 669], its buttons outside the client. Owner: windows should open centered and adjust
 * when the window is resized.
 *
 * Policy: at exactly 800x600 the stock placement is left alone (and remembered). At any other size a
 * dialog that becomes visible is centered in the map area (client minus the side panel and bar). On a
 * resize, a dialog still where we (or the stock layout) put it is re-placed: stock rect at 800x600,
 * centered otherwise. A dialog the player dragged is only clamped back inside the client.
 * SC3RESIZE_DIALOGS=0 disables it. Moves go through the dialog's own vt+0xc8 SetRect (same size, so
 * FUN_1006d56c keeps its surface), then one cascade rebuilds the derived hit rects. */
static int g_dialogs = 1;
/* DLGKEEP (2026-10-11): a dialog that opens already centred on the CLIENT is left there. The "Cargando..."
 * box is created centred on the client (measured maximized 1680x979: stale copy at [712 412], centre of
 * the client for 256x154) and painted once before the 100 ms poll sees it. Moving it to the map-area centre
 * [664 384] left that first copy on screen for the whole load, because nothing under it repaints until the
 * new city presents (Load City and in-city New City, both maximized). SC3RESIZE_DLGKEEP=0 moves it as before.
 * DLGAREA (2026-10-11): the map area is read from the live side panel and bar, which the first poll after a
 * size change still sees at the OLD size. Measured: maximize put a 308x280 dialog at [348 232], the centre of
 * the 1100x800 map area. For 3 s after a size change, a change of the map area alone re-centres a dialog
 * still where we put it. SC3RESIZE_DLGAREA=0 re-centres on the size change only. */
static int g_dlgkeep = 1, g_dlgarea = 1;
/* DLGSTAY (child reunirse 2026-10-12, verify/reunirse): owner, "cuando mueva una ventana en el menú 'reunirse' que
 * al abrir un ítem la ventana se mantenga en la misma posición". Measured: opening an advisor rebuilds the SAME
 * window as the detail page (383 -> 384 wide) and the game moves it to the detail page's own stored spot, then this
 * poll took the size change for a new window and centred it. Two parts, both off with SC3RESIZE_DLGSTAY=0:
 * (1) rz_meet_hook: the two Reunirse pages share one stored position (game side, below).
 * (2) here: a dialog that becomes visible where the game put it back is kept there (clamped), not centred:
 *     a Reunirse page the game built at the spot where the last page closed, at the same client size (the pages
 *     are often NEW window objects, measured 0x0FACB560 -> 0x0FACADE0), or any dialog reappearing at the
 *     top-left where this poll last saw it, at the same client size. */
static int g_dlgstay = 1;
static void *g_meet_dlg;                 /* the window the last Reunirse page builder ran on */
static LONG g_meet_x = -1, g_meet_y = -1, g_meet_cw, g_meet_ch;   /* where the last page closed, client size then */
static int g_meet_dragged;               /* the last visible Reunirse page was not where we placed it */
/* MEETALL (child reunirse2 2026-10-12, verify/reunirse2): owner, "si muevo la ventana cuando voy a otro cartel la
 * ventana no sigue". Reunirse has FIVE pages with a stored spot each, not two (rz_meet_hook). Measured on round/1012:
 * advisor dragged to [140 115], the topic text page opened at its own slot [640 296] and the poll centred it; topic
 * dragged to [280 195], its back arrow reopened the advisor at [140 115]. Any page's spot now goes to all five slots,
 * and the petitioner answer popup (centred by the game on the page it came from) is kept where the game put it.
 * SC3RESIZE_MEETALL=0 keeps DLGSTAY's list <-> advisor sharing only. */
static int g_meetall = 1;
static void *g_meet_pop;                 /* the last petitioner answer popup the game built */
static void rz_meet_pre(void *nw);       /* fwd: MEETALL, below */
static LONG g_meet_pop_cw, g_meet_pop_ch;
static LONG g_dlg_cw, g_dlg_ch;          /* client size at the last poll */
#define DLG_MAX 24
static struct { void *w; LONG placed[4]; LONG stock[4]; LONG rect[4]; int has_stock, vis, seen, rdock; LONG rdock_y, ew, eh;
                int has_rect; LONG rcw, rch; } g_dlg[DLG_MAX];
static int g_dlg_n;

static int rz_dlg_place(void *w, const LONG *t) {
    DWORD *vt = IsBadReadPtr(w, 4) ? NULL : *(DWORD **)w;
    DWORD a[4];
    if (!vt || IsBadReadPtr(vt, 0xcc) || !vt[0xc8 / 4]) return 0;
    a[0] = (DWORD)t[0]; a[1] = (DWORD)t[1]; a[2] = (DWORD)t[2]; a[3] = (DWORD)t[3];
    rz_thiscall(w, (void *)vt[0xc8 / 4], a, 4);   /* parents sit at (0,0): local == absolute */
    return 1;
}

static void rz_dialogs_poll(LONG cw, LONG ch) {
    static LONG lcw, lch, lax1, lay1;
    static DWORD area_until;
    DWORD sui = (DWORD)GetModuleHandleA("SIMUI.DLL");
    DWORD exe = (DWORD)GetModuleHandleA(NULL);
    void *root = rz_ui_root();
    void *lists[2];
    int nl = 0, li, k, moved = 0, sizechg, native;
    LONG ax1 = cw, ay1 = ch;
    if (!g_dialogs || !sui || !root || cw <= 0 || ch <= 0) return;
    sizechg = (cw != lcw || ch != lch);
    lcw = cw; lch = ch;
    g_dlg_cw = cw; g_dlg_ch = ch;
    native = (cw == NAT_W && ch == NAT_H);
    /* the map area: left of a right-docked side panel, above a bottom-docked bar */
    if (g_side_top && !IsBadReadPtr(g_side_top, 0x24)) {
        LONG sx = ((LONG *)((DWORD)g_side_top + 0x14))[0];
        if (sx > cw / 2 && sx < cw) ax1 = sx;
    }
    if (g_hud_top && !IsBadReadPtr(g_hud_top, 0x24)) {
        LONG by = ((LONG *)((DWORD)g_hud_top + 0x14))[1];
        if (by > ch / 2 && by < ch) ay1 = by;
    }
    if (sizechg) area_until = GetTickCount() + 3000;
    else if (g_dlgarea && (ax1 != lax1 || ay1 != lay1) && (LONG)(GetTickCount() - area_until) < 0) sizechg = 1;
    lax1 = ax1; lay1 = ay1;
    lists[nl++] = root;
    {   /* the HUD container: a root child of class SC3U.exe+0xd32d0 */
        void *head = *(void **)((DWORD)root + 0x34), *n;
        int g = 0;
        if (head && !IsBadReadPtr(head, 4)) {
            n = *(void **)head;
            while (n && n != head && g++ < 200) {
                void *c;
                if (IsBadReadPtr(n, 0x0c)) break;
                c = *(void **)((DWORD)n + 8);
                if (c && !IsBadReadPtr(c, 4) && *(DWORD *)c == exe + 0xd32d0) { lists[nl++] = c; break; }
                n = *(void **)n;
            }
        }
    }
    for (k = 0; k < g_dlg_n; k++) g_dlg[k].seen = 0;
    for (li = 0; li < nl; li++) {
        void *head = *(void **)((DWORD)lists[li] + 0x34), *n;
        int g = 0;
        if (!head || IsBadReadPtr(head, 4)) continue;
        n = *(void **)head;
        while (n && n != head && g++ < 200) {
            void *c;
            LONG *r;
            int e = -1, had_stock;
            if (IsBadReadPtr(n, 0x0c)) break;
            c = *(void **)((DWORD)n + 8);
            n = *(void **)n;
            if (!c || IsBadReadPtr(c, 0xa4) || *(DWORD *)c != sui + 0xa4d64) continue;
            r = (LONG *)((DWORD)c + 0x14);
            if (r[2] - r[0] < 120 || r[3] - r[1] < 80) continue;          /* not the corner widget */
            for (k = 0; k < g_dlg_n; k++) if (g_dlg[k].w == c) { e = k; break; }
            if (!(*(DWORD *)((DWORD)c + 0xa0) & 1)) { if (e >= 0) { g_dlg[e].vis = 0; g_dlg[e].seen = 1; } continue; }
            had_stock = e >= 0 && g_dlg[e].has_stock;      /* DLGSTAY: the size reset below clears it */
            /* A tracked address that comes back with another size is ANOTHER window (dialogs are freed and the
               heap hands the address to the next one): forget what we knew. Owner 2026-10-08: on a second New City
               the terrain panel inherited a plain dialog's entry and was centred instead of docked. */
            if (e >= 0 && (g_dlg[e].ew != r[2] - r[0] || g_dlg[e].eh != r[3] - r[1])) {
                g_dlg[e].vis = 0; g_dlg[e].has_stock = 0; g_dlg[e].rdock = 0;
                g_dlg[e].ew = r[2] - r[0]; g_dlg[e].eh = r[3] - r[1];
                if (r[2] == NAT_W && r[0] >= NAT_W / 2) { g_dlg[e].rdock = 1; g_dlg[e].rdock_y = r[1]; }
                if (r[2] - r[0] == 172 && r[3] - r[1] >= 400) { g_dlg[e].rdock = 1; g_dlg[e].rdock_y = 60; }
            }
            /* and the terrain panel is recognised by size on every (re)open, not only at first sight */
            if (e >= 0 && !g_dlg[e].vis && r[2] - r[0] == 172 && r[3] - r[1] >= 400) { g_dlg[e].rdock = 1; g_dlg[e].rdock_y = 60; }
            if (e < 0) {
                if (g_dlg_n >= DLG_MAX) continue;
                e = g_dlg_n++;
                g_dlg[e].ew = r[2] - r[0]; g_dlg[e].eh = r[3] - r[1];
                g_dlg[e].w = c; g_dlg[e].vis = 0; g_dlg[e].has_stock = 0; g_dlg[e].rdock = 0; g_dlg[e].has_rect = 0;
                /* RIGHT-DOCKED panels (owner 2026-10-07: "Editar Terreno" during New City, stock
                   [628 60 800 540]): dialogs are created at their 800x600 stock spot, so one whose
                   right edge is exactly NAT_W, in the right half, is a tool panel docked to the right
                   edge. It stays docked there at its stock y instead of being centered. */
                if (r[2] == NAT_W && r[0] >= NAT_W / 2) { g_dlg[e].rdock = 1; g_dlg[e].rdock_y = r[1]; }
                /* ...or recognised by its size: the terrain editor panel is 172 wide and 480 tall. On a later
                   New City (after a city was loaded) the game can create it somewhere else, and the edge test
                   alone then sent it to the centring rule (owner 2026-10-07). */
                if (r[2] - r[0] == 172 && r[3] - r[1] >= 400) { g_dlg[e].rdock = 1; g_dlg[e].rdock_y = 60; }
            }
            g_dlg[e].seen = 1;
            /* DLGSTAY: a Reunirse page is never the right-docked terrain panel. Measured: a detail page kept at
               [416 246 800 600] (clamped at 800x600) and reopened maximized matched the "right edge == NAT_W" test and
               was docked to [1296 312]. */
            if (g_dlgstay && (c == g_meet_dlg || (g_meetall && c == g_meet_pop))) g_dlg[e].rdock = 0;
            {   LONG w = r[2] - r[0], h = r[3] - r[1], t[4], was[4];
                int place = 0, drag_clamp = 0;
                LONG cx = (ax1 - w) / 2, cy = (ay1 - h) / 2;
                if (cx < 0) cx = 0;
                if (cy < 0) cy = 0;
                if (g_dlg[e].rdock) {                       /* docked: right edge, centred vertically (owner) */
                    cx = cw - w;
                    cy = (ch - h) / 2;
                    if (cy + h > ch) cy = ch - h;
                    if (cx < 0) cx = 0;
                    if (cy < 0) cy = 0;
                }
                if (g_dlg[e].rdock && g_dlg[e].vis) {
                    /* Docked panels are held at the dock on EVERY poll, not only on our own resize:
                       the terrain editor re-lays out its own panel when the window changes size
                       (measured at y 1222 in an 1135-tall client), which the "player moved it" rule
                       below would only clamp to the bottom. Trade-off: dragging it does not stick. */
                    t[0] = native && g_dlg[e].has_stock ? g_dlg[e].stock[0] : cx;
                    t[1] = native && g_dlg[e].has_stock ? g_dlg[e].stock[1] : cy;
                    t[2] = t[0] + w; t[3] = t[1] + h;
                    place = 1;
                } else if (!g_dlg[e].vis) {                             /* just opened */
                    /* At 800x600 a dialog fully inside the client is at its stock spot: keep it. One that
                       is not was positioned at another size (dialogs are created once and reused, e.g.
                       snapshots re-opened at [584 309 1096 669]) and is centered like at any other size. */
                    int inside = r[0] >= 0 && r[1] >= 0 && r[2] <= cw && r[3] <= ch;
                    int ccent = g_dlgkeep && !native && labs(r[0] - (cw - w) / 2) <= 1 && labs(r[1] - (ch - h) / 2) <= 1;
                    int meet = c == g_meet_dlg && g_meet_cw == cw && g_meet_ch == ch && r[0] == g_meet_x && r[1] == g_meet_y;
                    /* MEETALL: the answer popup, built at this client size, sits where the game centred it on its page */
                    int pop = g_meetall && c == g_meet_pop && g_meet_pop_cw == cw && g_meet_pop_ch == ch;
                    /* MEETALL: a Reunirse page whose spot was noted at another client size is centred at 800x600 too.
                       Measured (F3): closed maximized at (210,125), restored to 800x600, reopened -> kept at [210 125]. */
                    int resized = g_meetall && c == g_meet_dlg && g_meet_cw && (g_meet_cw != cw || g_meet_ch != ch);
                    int stay = g_dlgstay && !g_dlg[e].rdock && (meet || pop || (g_dlg[e].has_rect && g_dlg[e].rcw == cw
                               && g_dlg[e].rch == ch && r[0] == g_dlg[e].rect[0] && r[1] == g_dlg[e].rect[1]));
                    if (stay) {                         /* DLGSTAY: back where it was, keep it there */
                        LONG x = r[0], y = r[1];
                        int ours = meet ? !g_meet_dragged                                  /* not dragged since */
                                        : pop || (g_dlg[e].placed[0] == x && g_dlg[e].placed[1] == y);
                        if (x + w > cw) x = cw - w;
                        if (y + h > ch) y = ch - h;
                        if (x < 0) x = 0;
                        if (y < 0) y = 0;
                        t[0] = x; t[1] = y; t[2] = x + w; t[3] = y + h;
                        logf("DLGSTAY> dialog 0x%08lX [%ld %ld %ld %ld] %s (%s) - kept at [%ld %ld]", (DWORD)c, r[0], r[1],
                             r[2], r[3], meet ? "Reunirse page where the last one closed"
                                         : pop ? "Reunirse answer popup on its page" : "reappeared where it was",
                             ours ? "our spot" : "dragged", x, y);
                        if (!ours && meet) memset(g_dlg[e].placed, 0, sizeof(g_dlg[e].placed));   /* counts as dragged */
                        if (ours) {
                            place = 1;                  /* placed = t: a resize may re-place it as ours */
                            if (had_stock) { memcpy(g_dlg[e].stock, t, sizeof(t)); g_dlg[e].has_stock = 1; }
                        } else if ((x != r[0] || y != r[1]) && rz_dlg_place(c, t)) {
                            moved++;                    /* clamped; placed is left alone, so it still counts as dragged */
                        }
                    } else if (native && inside && !resized) {
                        memcpy(g_dlg[e].stock, r, sizeof(LONG) * 4); g_dlg[e].has_stock = 1;
                        memcpy(g_dlg[e].placed, r, sizeof(LONG) * 4);
                    } else if (ccent) {                 /* DLGKEEP: the game centred it on the client, leave it */
                        memcpy(g_dlg[e].placed, r, sizeof(LONG) * 4);
                        logf("DLG> dialog 0x%08lX [%ld %ld %ld %ld] opened centred on the client %ldx%ld - kept",
                             (DWORD)c, r[0], r[1], r[2], r[3], cw, ch);
                    } else { t[0] = cx; t[1] = cy; t[2] = cx + w; t[3] = cy + h; place = 1; }
                    g_dlg[e].vis = 1;
                } else if (sizechg) {
                    int untouched = !memcmp(r, g_dlg[e].placed, sizeof(LONG) * 4);
                    if (untouched) {
                        if (native && g_dlg[e].has_stock) { memcpy(t, g_dlg[e].stock, sizeof(t)); place = 1; }
                        else if (native) { t[0] = cx; t[1] = cy; t[2] = cx + w; t[3] = cy + h; place = 1; }  /* owner: re-centre on de-maximize */
                        else { t[0] = cx; t[1] = cy; t[2] = cx + w; t[3] = cy + h; place = 1; }
                    } else {                                            /* the player moved it: clamp */
                        LONG x = r[0], y = r[1];
                        if (x + w > cw) x = cw - w;
                        if (y + h > ch) y = ch - h;
                        if (x < 0) x = 0;
                        if (y < 0) y = 0;
                        if (x != r[0] || y != r[1]) { t[0] = x; t[1] = y; t[2] = x + w; t[3] = y + h; place = 1; drag_clamp = g_dlgstay; }
                        else if (!g_dlgstay) memcpy(g_dlg[e].placed, r, sizeof(LONG) * 4);   /* DLGSTAY: stays "dragged" */
                    }
                }
                memcpy(was, r, sizeof(was));   /* r is the live rect: SetRect rewrites it */
                if (place && memcmp(t, r, sizeof(t)) && rz_dlg_place(c, t)) {
                    logf("DLG> dialog 0x%08lX [%ld %ld %ld %ld] -> [%ld %ld %ld %ld] (client %ldx%ld, map area %ldx%ld)",
                         (DWORD)c, was[0], was[1], was[2], was[3], t[0], t[1], t[2], t[3], cw, ch, ax1, ay1);
                    moved++;
                }
                if (place) memcpy(g_dlg[e].placed, t, sizeof(t));
                /* DLGSTAY: a dragged dialog clamped on a resize stays "dragged". Measured: recorded as ours, DLGAREA then
                   re-centred it 33 ms later ([1350 959] -> [417 246] -> [160 95] on restore to 800x600). */
                if (drag_clamp) memset(g_dlg[e].placed, 0, sizeof(g_dlg[e].placed));
                memcpy(g_dlg[e].rect, r, sizeof(LONG) * 4);
                g_dlg[e].has_rect = 1; g_dlg[e].rcw = cw; g_dlg[e].rch = ch;
                if (c == g_meet_dlg) g_meet_dragged = memcmp(r, g_dlg[e].placed, sizeof(LONG) * 4) != 0;
            }
        }
    }
    for (k = 0; k < g_dlg_n; k++) if (!g_dlg[k].seen) g_dlg[k].vis = 0;   /* gone: never dereferenced again until re-seen */
    if (moved) {
        DWORD *rvt = *(DWORD **)root;
        rz_cascade_derived();
        /* repaint what was under the dialog's old spot: during a load nothing redraws there, so the old copy
           stayed (owner: two "Cargando..." boxes). vt+0x154 = invalidate. */
        if (rvt && !IsBadReadPtr(rvt, 0x158) && rvt[0x154 / 4]) rz_thiscall(root, (void *)rvt[0x154 / 4], NULL, 0);
    }
}

/* Does any visible dialog overlap this absolute rect? Uses the rect copies, never the pointers. */
static int rz_dialog_over(const LONG *q) {
    int k;
    for (k = 0; k < g_dlg_n; k++) {
        const LONG *r = g_dlg[k].rect;
        if (g_dlg[k].vis && r[0] < q[2] && q[0] < r[2] && r[1] < q[3] && q[1] < r[3]) return 1;
    }
    return 0;
}

/* DLGSTAY game side: ONE stored position for both Reunirse pages (verify/reunirse/PRE.md).
 * [CONFIRMED @ SIMUI 0x10004405] the list page builder moves the dialog to (8,8) when byte 0 of the struct from
 * FUN_1008e998()->vt+0x5c is 0, else to (s+4, s+8). [CONFIRMED @ 0x10005602] the detail page builder uses (8,8)
 * or (s+0xc, s+0x10). The page closers store the dialog's local left/top (vt+0x98 = +0x80, vt+0x9c = +0x84):
 * FUN_10004cda into s+4/s+8, FUN_10005fb4 into s+0xc/s+0x10, both set byte 0 = 1. So stock keeps one spot PER
 * PAGE and opening an advisor jumps to wherever the detail page was last. After either closer runs we copy the
 * slot it wrote into the other one: the next page opens where the last one was. */
static void *g_orig_4cda, *g_orig_5fb4;
/* MEETALL: the five pages' slot offsets (in LONGs): list +4, advisor +0xc, topic +0x18, petitioner +0x20,
 * page 0x62be6000 +0x28 [CONFIRMED @ SIMUI 0x10004cda, 0x10005fb4, 0x1000a1a2, 0x10007b8c, 0x1000ae3e]. */
static const int g_meet_slot[5] = { 1, 3, 6, 8, 10 };
static void rz_meet_share(int from) {
    BYTE *sui = (BYTE *)GetModuleHandleA("SIMUI.DLL");
    void *o;
    DWORD *vt;
    LONG *s;
    if (!sui) return;
    o = ((void *(__cdecl *)(void))(sui + 0x8e998))();
    if (!o || IsBadReadPtr(o, 4)) return;
    vt = *(DWORD **)o;
    if (!vt || IsBadReadPtr(vt, 0x60) || !vt[0x5c / 4]) return;
    s = (LONG *)rz_thiscall_ret(o, (void *)vt[0x5c / 4], NULL, 0);
    if (!s || IsBadReadPtr(s, 0x30)) return;
    {   int k, n = g_meetall ? 5 : 2;   /* without MEETALL only list <-> advisor, as DLGSTAY shipped */
        LONG x = from > 0 ? s[from] : g_meet_x, y = from > 0 ? s[from + 1] : g_meet_y;   /* from 0: rz_meet_pre */
        for (k = 0; k < n; k++) { s[g_meet_slot[k]] = x; s[g_meet_slot[k] + 1] = y; }
        g_meet_x = x; g_meet_y = y; g_meet_cw = g_dlg_cw; g_meet_ch = g_dlg_ch;
        logf("DLGSTAY> Reunirse %s page %s at (%ld,%ld), client %ldx%ld: %s pages will open there",
             from == 0 ? "previous" : from == 1 ? "list" : from == 3 ? "detail" : from == 6 ? "topic"
             : from == 8 ? "petitioner" : "0x62be6000", from == 0 ? "still open" : "closed",
             x, y, g_dlg_cw, g_dlg_ch, g_meetall ? "all five" : "both");
    }
}
/* The page builders FUN_10004405 / FUN_10005602 are __thiscall(this, dialog window): note which window is the
 * current Reunirse page. Both start with `mov eax, <SIMUI EH handler>` (5 bytes, relocated imm32). */
static void *g_orig_4405, *g_orig_5602;
static DWORD __fastcall rz_4405_detour(void *self, void *edx, DWORD p1) {
    DWORD a[1];
    (void)edx;
    a[0] = p1; rz_meet_pre((void *)p1); g_meet_dlg = (void *)p1;
    return rz_thiscall_ret(self, g_orig_4405, a, 1);
}
static DWORD __fastcall rz_5602_detour(void *self, void *edx, DWORD p1) {
    DWORD a[1];
    (void)edx;
    a[0] = p1; rz_meet_pre((void *)p1); g_meet_dlg = (void *)p1;
    return rz_thiscall_ret(self, g_orig_5602, a, 1);
}
static void *rz_detour_movimm(HMODULE mod, DWORD rva, DWORD imm_rva, void *det, const char *name) {
    BYTE *fn = (BYTE *)mod + rva, *tr;
    DWORD old;
    if (IsBadReadPtr(fn, 5) || fn[0] != 0xB8 || *(DWORD *)(fn + 1) != (DWORD)mod + imm_rva) {
        logf("DLGSTAY> %s prologue mismatch - NOT hooking", name); return NULL;
    }
    tr = (BYTE *)VirtualAlloc(NULL, 16, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!tr) return NULL;
    memcpy(tr, fn, 5); tr[5] = 0xE9;                   /* mov eax, imm32 (already relocated) ; jmp fn+5 */
    *(DWORD *)(tr + 6) = (DWORD)(fn + 5) - (DWORD)(tr + 10);
    FlushInstructionCache(GetCurrentProcess(), tr, 16);
    if (!VirtualProtect(fn, 5, PAGE_EXECUTE_READWRITE, &old)) { VirtualFree(tr, 0, MEM_RELEASE); return NULL; }
    fn[0] = 0xE9; *(DWORD *)(fn + 1) = (DWORD)det - (DWORD)(fn + 5);
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    FlushInstructionCache(GetCurrentProcess(), fn, 5);
    logf("DLGSTAY> detour installed at %s", name);
    return tr;
}
static DWORD __fastcall rz_4cda_detour(void *self, void *edx, DWORD p1) {
    DWORD a[1], r;
    (void)edx;
    a[0] = p1;
    r = rz_thiscall_ret(self, g_orig_4cda, a, 1);
    rz_meet_share(1);
    if (g_meetall && g_meet_dlg == (void *)p1) g_meet_dlg = NULL;   /* MEETALL: freed next */
    return r;
}
static DWORD __fastcall rz_5fb4_detour(void *self, void *edx, DWORD p1) {
    DWORD a[1], r;
    (void)edx;
    a[0] = p1;
    r = rz_thiscall_ret(self, g_orig_5fb4, a, 1);
    rz_meet_share(3);
    if (g_meetall && g_meet_dlg == (void *)p1) g_meet_dlg = NULL;   /* MEETALL: freed next */
    return r;
}
/* 6-byte entry detour (both prologues are push ebx/ebp/esi/edi + a 2-byte mov), all-or-nothing on the bytes */
static void *rz_detour6(HMODULE mod, DWORD rva, const BYTE *expect, void *det, const char *name) {
    BYTE *fn = (BYTE *)mod + rva, *tr;
    DWORD old;
    if (IsBadReadPtr(fn, 6) || memcmp(fn, expect, 6) != 0) { logf("DLGSTAY> %s prologue mismatch - NOT hooking", name); return NULL; }
    tr = (BYTE *)VirtualAlloc(NULL, 16, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!tr) return NULL;
    memcpy(tr, expect, 6); tr[6] = 0xE9;
    *(DWORD *)(tr + 7) = (DWORD)(fn + 6) - (DWORD)(tr + 11);
    FlushInstructionCache(GetCurrentProcess(), tr, 16);
    if (!VirtualProtect(fn, 6, PAGE_EXECUTE_READWRITE, &old)) { VirtualFree(tr, 0, MEM_RELEASE); return NULL; }
    fn[0] = 0xE9; *(DWORD *)(fn + 1) = (DWORD)det - (DWORD)(fn + 5); fn[5] = 0x90;
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    FlushInstructionCache(GetCurrentProcess(), fn, 6);
    logf("DLGSTAY> detour installed at %s", name);
    return tr;
}
/* MEETALL game side: the other three Reunirse pages and the petitioner answer popup. Same calling convention and
 * prologues as the four DLGSTAY detours (bytes checked in SIMUI.DLL sha1 165301ae, MAIN = stock):
 *   topic text page   0x62be5000  build FUN_10008d40 (mov eax, SIMUI+0x98eaa)  close FUN_1000a1a2 (slot +0x18/+0x1c)
 *   petitioner page   0x62be5f00  build FUN_1000690a (mov eax, SIMUI+0x98d59)  close FUN_10007b8c (slot +0x20/+0x24)
 *   page 0x62be6000               build FUN_1000a5ec (mov eax, SIMUI+0x98eff)  close FUN_1000ae3e (slot +0x28/+0x2c)
 * Dispatcher [CONFIRMED @ SIMUI 0x100032ea]: msgs 0x724a82d2/d4/d5 open the topic page (from the advisor page),
 * d6 the petitioner page (list button 0x62be5dd6), d7 page 0x62be6000 (topic page button 0x62be5009). Every open first
 * closes the open page (FUN_100037f0), so its closer has already shared the spot when the next builder reads it.
 * Answer popup: the petitioner page's answer buttons (0x62be5f0c/0x62be5f0d, FUN_10007c7a) build a 337x254 window with
 * FUN_1000823d (mov eax, SIMUI+0x98daf), which the game centres on the page's rect [CONFIRMED @ 0x1000823d]. */
static void *g_orig_8d40, *g_orig_690a, *g_orig_a5ec, *g_orig_823d, *g_orig_a1a2, *g_orig_7b8c, *g_orig_ae3e;
/* A page builder that runs while the previous page is STILL OPEN: share that page's spot before the builder reads its
 * slot. Measured (F1, 800x600): the topic page's back arrow built the advisor page at its old slot [140 115] and the
 * topic page's closer ran 6 ms LATER with the dragged spot (260,195): that close is deferred (FUN_10008c67 hands it to
 * the window manager, vt+0x44(0xd)). Only a live, visible SIMUI+0xa4d64 page of at least 300x300 is read. */
static void rz_meet_pre(void *nw) {
    void *o = g_meet_dlg;
    DWORD sui = (DWORD)GetModuleHandleA("SIMUI.DLL");
    LONG *lr;
    if (!g_meetall || !o || o == nw || !sui || !rz_win_alive(o) || IsBadReadPtr(o, 0xa4)) return;
    if (*(DWORD *)o != sui + 0xa4d64 || !(*(DWORD *)((DWORD)o + 0xa0) & 1)) return;
    lr = (LONG *)((DWORD)o + 0x80);
    if (lr[2] - lr[0] < 300 || lr[3] - lr[1] < 300) return;
    g_meet_x = lr[0]; g_meet_y = lr[1];
    rz_meet_share(0);
}
static DWORD __fastcall rz_8d40_detour(void *self, void *edx, DWORD p1) {
    DWORD a[1]; (void)edx; a[0] = p1; rz_meet_pre((void *)p1); g_meet_dlg = (void *)p1;
    return rz_thiscall_ret(self, g_orig_8d40, a, 1);
}
static DWORD __fastcall rz_690a_detour(void *self, void *edx, DWORD p1) {
    DWORD a[1]; (void)edx; a[0] = p1; rz_meet_pre((void *)p1); g_meet_dlg = (void *)p1;
    return rz_thiscall_ret(self, g_orig_690a, a, 1);
}
static DWORD __fastcall rz_a5ec_detour(void *self, void *edx, DWORD p1) {
    DWORD a[1]; (void)edx; a[0] = p1; rz_meet_pre((void *)p1); g_meet_dlg = (void *)p1;
    return rz_thiscall_ret(self, g_orig_a5ec, a, 1);
}
static DWORD __fastcall rz_823d_detour(void *self, void *edx, DWORD p1) {
    DWORD a[1]; (void)edx; a[0] = p1;
    g_meet_pop = (void *)p1; g_meet_pop_cw = g_dlg_cw; g_meet_pop_ch = g_dlg_ch;
    return rz_thiscall_ret(self, g_orig_823d, a, 1);
}
static DWORD __fastcall rz_a1a2_detour(void *self, void *edx, DWORD p1) {
    DWORD a[1], r; (void)edx; a[0] = p1;
    r = rz_thiscall_ret(self, g_orig_a1a2, a, 1);
    rz_meet_share(6);
    if (g_meetall && g_meet_dlg == (void *)p1) g_meet_dlg = NULL;   /* MEETALL: freed next */
    return r;
}
static DWORD __fastcall rz_7b8c_detour(void *self, void *edx, DWORD p1) {
    DWORD a[1], r; (void)edx; a[0] = p1;
    r = rz_thiscall_ret(self, g_orig_7b8c, a, 1);
    rz_meet_share(8);
    if (g_meetall && g_meet_dlg == (void *)p1) g_meet_dlg = NULL;   /* MEETALL: freed next */
    return r;
}
static DWORD __fastcall rz_ae3e_detour(void *self, void *edx, DWORD p1) {
    DWORD a[1], r; (void)edx; a[0] = p1;
    r = rz_thiscall_ret(self, g_orig_ae3e, a, 1);
    rz_meet_share(10);
    if (g_meetall && g_meet_dlg == (void *)p1) g_meet_dlg = NULL;   /* MEETALL: freed next */
    return r;
}
static void rz_meetall_hook(HMODULE sui) {
    static const BYTE ed9[6] = { 0x53, 0x55, 0x56, 0x57, 0x8b, 0xd9 };   /* push ebx/ebp/esi/edi ; mov ebx, ecx */
    static const BYTE ef1[6] = { 0x53, 0x55, 0x56, 0x57, 0x8b, 0xf1 };   /* ... ; mov esi, ecx */
    if (!g_orig_4cda || !g_orig_5fb4) return;   /* the DLGSTAY closers are the base: without them, nothing to extend */
    g_orig_a1a2 = rz_detour6(sui, 0xa1a2, ed9, (void *)rz_a1a2_detour, "SIMUI+0xa1a2 (Reunirse topic close)");
    g_orig_7b8c = rz_detour6(sui, 0x7b8c, ef1, (void *)rz_7b8c_detour, "SIMUI+0x7b8c (Reunirse petitioner close)");
    g_orig_ae3e = rz_detour6(sui, 0xae3e, ed9, (void *)rz_ae3e_detour, "SIMUI+0xae3e (Reunirse page 0x62be6000 close)");
    g_orig_8d40 = rz_detour_movimm(sui, 0x8d40, 0x98eaa, (void *)rz_8d40_detour, "SIMUI+0x8d40 (Reunirse topic build)");
    g_orig_690a = rz_detour_movimm(sui, 0x690a, 0x98d59, (void *)rz_690a_detour, "SIMUI+0x690a (Reunirse petitioner build)");
    g_orig_a5ec = rz_detour_movimm(sui, 0xa5ec, 0x98eff, (void *)rz_a5ec_detour, "SIMUI+0xa5ec (Reunirse page 0x62be6000 build)");
    g_orig_823d = rz_detour_movimm(sui, 0x823d, 0x98daf, (void *)rz_823d_detour, "SIMUI+0x823d (Reunirse answer popup build)");
}
static void rz_meet_hook(HMODULE sui) {
    static const BYTE e4cda[6] = { 0x53, 0x55, 0x56, 0x57, 0x8b, 0xd9 };
    static const BYTE e5fb4[6] = { 0x53, 0x55, 0x56, 0x57, 0x8b, 0xf1 };
    if (!g_dlgstay || g_orig_4cda) return;
    g_orig_4cda = rz_detour6(sui, 0x4cda, e4cda, (void *)rz_4cda_detour, "SIMUI+0x4cda (Reunirse list close)");
    if (g_orig_4cda)
        g_orig_5fb4 = rz_detour6(sui, 0x5fb4, e5fb4, (void *)rz_5fb4_detour, "SIMUI+0x5fb4 (Reunirse detail close)");
    g_orig_4405 = rz_detour_movimm(sui, 0x4405, 0x98bf1, (void *)rz_4405_detour, "SIMUI+0x4405 (Reunirse list build)");
    g_orig_5602 = rz_detour_movimm(sui, 0x5602, 0x98c5d, (void *)rz_5602_detour, "SIMUI+0x5602 (Reunirse detail build)");
    if (g_meetall) rz_meetall_hook(sui);
}

/* ⭐ SIDE PANEL CONTENTS — push the pages and tabs to the BOTTOM of the extended panel.
 *
 * `rz_side_extend` makes the panel span the full right edge, but its contents do not follow: the
 * pages are 96x442 windows anchored at the panel's top, so the panel grows and the buttons stay up
 * top with dead space below. Owner's ask (2026-09-02): buttons near the minimap, empty space above.
 *
 * Two things this gets right that a live experiment got wrong, both measured the hard way:
 *
 *   ⚠️ **`vt+0xc8` SetRect on a CHILD takes PARENT-LOCAL coordinates**, not absolute. Feeding it the
 *      child's absolute `+0x14` rect adds the parent origin a second time - a tab at absolute
 *      x 1985 landed at 3937 = 1985 + 1952. The parent-local rect is `+0x80..+0x8c`, so that is what
 *      gets translated. Invisible on the corner button, whose parent is the root at (0,0) where
 *      local and absolute coincide.
 *
 *   ⚠️ **This must run BEFORE rz_input_geometry.** SetRect churn on HUD windows makes SIMUI relayout
 *      and rebroadcast, which clobbers BOTH the view bounds AND the ancestor widening - measured
 *      live: the root's rect reverted to [0 0 800 600] and the whole HUD went unclickable, with the
 *      camera clamped back to the original viewport. Doing it here, with geometry applied last,
 *      is the whole reason this lives in the mod instead of a script.
 *
 * Grandchildren (the 36x36 buttons inside each page) are NOT touched: SetRect propagates to them and
 * their parent-local hit rects stay valid because their page moved as a unit. */
/* Rebuild every DERIVED rect (+0x14..+0x20) from the LOCAL rects (+0x84..) tree-wide, by calling the
 * root window's vt+0x168 (src + blit-dest) and vt+0x14c (absolute rects). These recurse into every
 * child `[CONFIRMED @ SIMUI 0x1006c61b, 0x1006d4eb]`. Hit-testing (vt+0xe4 = FUN_1006de62) compares
 * the DERIVED +0x14 rect, so after moving a window's LOCAL rect this MUST run or the moved window
 * stays clickable only at its old (native) position - the side-panel "hover hits a button off from
 * the icon" defect (2026-09-05). Returns 1 if it ran. */
static int rz_cascade_derived(void) {
    DWORD gzb = (DWORD)GetModuleHandleA("GZGraphicD.dll");
    DWORD *w2 = (gzb && !IsBadReadPtr((void *)(gzb + 0x6cdb8), 4))
              ? *(DWORD **)(gzb + 0x6cdb8) : NULL;
    DWORD *snk = (w2 && !IsBadReadPtr(w2, 0x34)) ? (DWORD *)w2[0x30 / 4] : NULL;
    DWORD *rt  = (snk && !IsBadReadPtr(snk, 0x3c)) ? (DWORD *)snk[0x38 / 4] : NULL;
    DWORD *rvt = (rt && !IsBadReadPtr(rt, 4)) ? *(DWORD **)rt : NULL;
    if (rvt && !IsBadReadPtr(rvt, 0x16c) && rvt[0x14c / 4] && rvt[0x168 / 4]) {
        rz_thiscall(rt, (void *)rvt[0x168 / 4], NULL, 0);   /* src + blit dest */
        rz_thiscall(rt, (void *)rvt[0x14c / 4], NULL, 0);   /* absolute rects */
        return 1;
    }
    return 0;
}

static void rz_side_children_bottom(void) {
    DWORD *p = (DWORD *)g_side_top;
    void *head, *n;
    LONG panelH, dy;
    int guard = 0, moved = 0, changed = 0;
    if (!p || IsBadReadPtr(p, 0xa0)) { logf("SIDEKIDS> skipped: side panel unreadable"); return; }
    panelH = (LONG)((LONG *)((DWORD)p + 0x80))[3] - (LONG)((LONG *)((DWORD)p + 0x80))[1];

    /* Read the LOCAL rect (+0x80..+0x8c), never the derived +0x14 one.
     * `+0x14` is local plus the sum of every ancestor origin, rebuilt by FUN_1006c61b
     * `[CONFIRMED @ SIMUI 0x1006c61b]`, and this mod widens those ancestors - so +0x14 conflates
     * "the panel changed" with "an ancestor moved". Reading it is what made me report a doubling
     * as an ancestor artefact when it was real. */
    {   RECT ccr;
        LONG maxH = (g_hwnd && GetClientRect(g_hwnd, &ccr)) ? (ccr.bottom - ccr.top) : 0;
        if (maxH > 0 && panelH > maxH + RZ_SURFACE_SLACK) {
            logf("SIDEKIDS> REFUSED: panel local height %ld exceeds the %ld-px client",
                 panelH, maxH);
            return;
        }
    }
    dy = panelH - SIDE_NAT_H - g_side_dy;
    /* ⛔ dy == 0 IS the native layout, not "nothing to do" (2026-10-05, verify/resize_spandefault).
     * At an 800x600 client the panel is first stretched to 600 (buttons pushed +158), then a later
     * pass shrinks it to 436 above the minimap. The old `if (dy <= 0) return;` left the buttons at
     * +158, under the minimap. Same bug class as the bar's dx <= 0 early return fixed in db1fd42.
     * Clamp instead, so every cached item goes back to native + 0. */
    if (dy < 0) dy = 0;
    if (dy == 0 && g_sideitem_n == 0) return;  /* nothing was ever moved: silent, runs on a timer */

    /* ⭐ MOVE THE BUTTONS, NOT THE PAGES.
     *
     * Measured 2026-09-02 with a submenu open: once the panel is stable at the client height, its
     * page children (class SIMUI+0xa9a80) are 36-wide FULL-HEIGHT columns - LOCAL [0 0 36 1081] -
     * not the 96x442 blocks they are natively, and their buttons sit at local y 21, 57, 93...
     * So pushing the pages down is meaningless (they already span the panel) and my old guard
     * skipped them forever once they had grown. What needs moving is the BUTTONS INSIDE each page.
     *
     * This also explains the "submenu renders at the top": the flyout was measured at
     * [1827 164 1953 200], exactly beside the button at local 165..201. It was never misplaced -
     * it correctly follows a button that was at the top.
     *
     * Buttons carry PARENT-LOCAL rects at +0x80..+0x8c and vt+0xc8 SetRect takes parent-local
     * coordinates, so the local rect is both the input and the thing to keep consistent. Skipping
     * anything already at or below `dy` keeps this idempotent, which is what lets the timer re-run
     * it and catch buttons the game creates later. */
    head = *(void **)((DWORD)p + 0x34);
    if (!head || IsBadReadPtr(head, 4)) { logf("SIDEKIDS> skipped: no child list"); return; }
    n = *(void **)head;
    while (n && n != head && guard++ < 300) {
        DWORD *page;
        if (IsBadReadPtr(n, 0x0c)) break;
        page = *(DWORD **)((DWORD)n + 8);
        if (page && !IsBadReadPtr(page, 0xa0)) {
            /* ⭐ MOVE THE SMALL DIRECT CHILDREN TOO — the ITEM windows.
             *
             * These are class SIMUI+0xa8f60 (56x32, LOCAL x 33..89), direct children of the panel,
             * and they are the items that OWN THE FLYOUTS: `vt+0x1f0` news up this class for kind
             * tag 0x0287C760 and caches the popup at the item's `+0xbc`, and the positioner reads
             * the OWNING ITEM's absolute rect `[CONFIRMED @ SIMUI 0x1004dc89, 0x1004b8c5,
             * 0x1004ec95]`.
             *
             * I moved them in the first version of this routine, then switched to moving the
             * buttons inside the page columns and STOPPED moving these - my own regression. A
             * visible-window enumeration found exactly nine of them still at LOCAL y 3..395 while
             * everything else was at the bottom, which is precisely why toasts and submenus kept
             * anchoring to the top. Both sets have to move.
             *
             * The page COLUMNS (class SIMUI+0xa9a80) are full-height and must NOT be translated -
             * they already span the panel - so height is what separates the two cases. */
            LONG *pe = (LONG *)((DWORD)page + 0x80);
            LONG ph = pe[3] - pe[1];
            if (ph > 0 && ph < panelH / 2) {          /* a small item, not a full-height column */
                DWORD *pvt2 = *(DWORD **)page;
                /* Cache this item's NATIVE y the first time it is seen (before we move it), then place
                 * it ABSOLUTELY at native+dy every pass - idempotent, no drift when dy changes. */
                int si = -1, sk;
                for (sk = 0; sk < g_sideitem_n; sk++)
                    if (g_sideitem[sk].w == (void *)page) { si = sk; break; }
                /* Cache on FIRST SIGHT for EVERY native-positioned item, not just those above dy.
                 * The old `pe[1] < dy` excluded any item whose NATIVE y already sits below dy - i.e.
                 * the alert button and everything under it (native y ~200..395 vs a dy of 175) - so
                 * they were never tracked and never pushed. That is the "top 5 ok, alert and below all
                 * wrong" report: only the handful of items above dy moved. The real intent is "cache it
                 * once, while it is still at a native (unmoved) position"; the native band is bounded by
                 * the native panel height (SIDE_NAT_H = 442), NOT by dy. Items we already moved are
                 * found via the pointer loop above (si >= 0) and never re-cached. (2026-09-05) */
                if (si < 0 && g_sideitem_n < SIDEITEM_MAX &&
                    pe[2] - pe[0] > 0 && pe[1] < SIDE_NAT_H) {   /* still in the native band */
                    DWORD sui2 = (DWORD)GetModuleHandleA("SIMUI.DLL");
                    si = g_sideitem_n++;
                    g_sideitem[si].w = (void *)page;
                    g_sideitem[si].naty = pe[1];
                    g_sideitem[si].has_ovl = 0;
                    if (sui2 && (DWORD)pvt2 == sui2 + 0xa8f60 &&
                        !IsBadWritePtr((void *)((DWORD)page + 0xf8), 4) &&
                        *(DWORD *)((DWORD)page + 0xe8)) {
                        g_sideitem[si].has_ovl = 1;
                        g_sideitem[si].natovl = *(LONG *)((DWORD)page + 0xf4);
                    }
                }
                if (si >= 0 && pvt2 && !IsBadReadPtr(pvt2, 0xcc) && pvt2[0xc8 / 4] &&
                    pe[2] - pe[0] > 0) {
                    LONG wy = g_sideitem[si].naty + dy, ih = pe[3] - pe[1];
                    if (pe[1] != wy) {
                    DWORD a2[4];
                    changed++;
                    a2[0] = (DWORD)pe[0]; a2[1] = (DWORD)wy;
                    a2[2] = (DWORD)pe[2]; a2[3] = (DWORD)(wy + ih);
                    rz_thiscall(page, (void *)pvt2[0xc8 / 4], a2, 4);
                    }
                    /* GROUP-OVERLAY Y at +0xf4 - the duplicate cluster drawn at the top.
                     *
                     * The item does not draw its +0xe8 raster. `vt+0x1f0 = FUN_1004c373` pushes
                     * `(raster, +0xf0, +0xf4)` to the panel (`vt+0x22c = FUN_1004e81c`), which
                     * stores them at +0x114/+0x128/+0x12c, and the panel's SetRect builds the dest
                     * as `(x + panel+0x24, y + panel+0x28)`; a panel owning its own surface has
                     * +0x24/+0x28 = 0, so the overlay lands at exactly `(+0xf0, +0xf4)`
                     * `[CONFIRMED @ SIMUI 0x1004c373, 0x1004e81c, 0x1004e20b, 0x1006d438]`.
                     * Verified live: after clicking a group item the panel read
                     * `overlay=0xf0305d8, x=0, y=0, dest=[0 0 96 247]` - drawn at the very top
                     * while its item sat at y 508.
                     *
                     * +0xf4 is a resolution-keyed constant from the table in FUN_1004c3e9, written
                     * only by Init, so nothing derives it from the item's rect and vt+0xc8 can
                     * never move it. Bump it by the same delta.
                     *
                     * ⚠️ The guard is `< dy`, NOT `> 0 && < dy`. My first version required a
                     * positive value and therefore skipped every item whose overlay y is ZERO -
                     * two of the nine, and one of those is the item that produced the measured
                     * duplicate. An item legitimately anchored at the top is exactly the case that
                     * needs moving most. */
                    /* The group overlay (where the icon actually draws) placed ABSOLUTELY at its
                     * cached native + dy, so it stays locked to the item window and the background
                     * art. The old `*oy += dy` re-added the offset when dy grew and drifted the icon
                     * off its button (owner: the hover highlight showed the wrong icon). */
                    if (g_sideitem[si].has_ovl) {
                        /* The group overlay (+0xe8 raster) draws at (+0xf0,+0xf4). It should sit ON its
                         * OWN item button, not at the shared native +0xf4 constant - otherwise every
                         * active group's icon stacks at one spot and shows as a DUPLICATE button in the
                         * middle of the panel (owner). Anchor it to this item's own window y. */
                        /* ⛔ CORRECTED 2026-10-05: NOT the item's own y. The overlay raster is the whole
                         * highlighted GROUP (measured natively: dest [0 0 96 247] = the top group of
                         * buttons), so anchoring it at the clicked item's y drew a second copy of the
                         * group starting at that item - a duplicate landscape button and a covered slot
                         * (verify/resize_spandefault, panel_triptych.png). It belongs at its native y
                         * plus the same dy as the buttons. Absolute, so it cannot drift when dy changes. */
                        LONG *oy = (LONG *)((DWORD)page + 0xf4);
                        LONG want = g_sideitem[si].natovl + dy;
                        if (*oy != want) {
                            if (!g_reassert_quiet)
                                logf("SIDEKIDS> item 0x%08lX group-overlay y %ld -> %ld (native %ld + dy %ld)",
                                     (DWORD)page, *oy, want, g_sideitem[si].natovl, dy);
                            *oy = want;
                            changed++;
                        }
                    }
                    moved++;
                }
            }
            {
            void *bhead = *(void **)((DWORD)page + 0x34);
            if (bhead && !IsBadReadPtr(bhead, 4)) {
                void *bn = *(void **)bhead;
                int bguard = 0;
                while (bn && bn != bhead && bguard++ < 200) {
                    DWORD *b;
                    if (IsBadReadPtr(bn, 0x0c)) break;
                    b = *(DWORD **)((DWORD)bn + 8);
                    if (b && !IsBadWritePtr(b, 0xa0)) {
                        LONG *e = (LONG *)((DWORD)b + 0x80);
                        DWORD *bvt = *(DWORD **)b;
                        /* ⛔ DO NOT MOVE FLYOUT SUB-TOOL BUTTONS (2026-09-05). These grandchildren are
                         * the tool-submenu buttons (class a917c) inside the page columns. Moving them
                         * by +dy displaced their HIT-RECTS away from the ICONS - the game draws the
                         * flyout icons at its own anchor (next to the owning category button), so the
                         * shifted hit-rects diverged from the icons, growing toward the bottom (owner:
                         * "menu open ... top a little, more and more misaligned"). It also stranded live
                         * hit-rects in the empty area over the minimap while the flyout was closed. The
                         * game already positions these correctly; leave them alone. Gated so it can be
                         * re-enabled for an A/B (SC3RESIZE_SUBMOVE=1). */
                        /* ✅ REVISED 2026-10-05 (verify/resize_spandefault/v2): with SIDESPAN on, the
                         * icons follow their category item (+dy) but these windows stayed at native y,
                         * so a click on the drawn tree icon resolved to the 4th sub-tool
                         * (hit_test.txt). A live poke proved these windows do NOT draw the icons
                         * (moving one left its icon in place, poke_pair.png), so moving them moves only
                         * the click target - onto the icon. The 09-05 drift came from the INCREMENTAL
                         * `e[1] + dy` with an `e[1] < dy` guard. This is absolute: native + dy. */
                        int sm = (g_submove >= 0) ? g_submove : g_side_span;
                        if (sm && bvt && !IsBadReadPtr(bvt, 0xcc) && bvt[0xc8 / 4] &&
                            e[2] - e[0] > 0 && e[3] - e[1] > 0) {
                            int bi = -1, bk;
                            for (bk = 0; bk < g_subbtn_n; bk++)
                                if (g_subbtn[bk].w == (void *)b) { bi = bk; break; }
                            if (bi >= 0 && e[1] != g_subbtn[bi].placed) {
                                g_subbtn[bi].naty = e[1];     /* recreated / moved by the game: re-cache */
                                g_subbtn[bi].placed = e[1];
                            }
                            if (bi < 0 && g_subbtn_n < SUBBTN_MAX) {
                                bi = g_subbtn_n++;
                                g_subbtn[bi].w = (void *)b;
                                g_subbtn[bi].naty = e[1];
                                g_subbtn[bi].placed = e[1];
                            }
                            if (bi >= 0 && e[1] != g_subbtn[bi].naty + dy) {
                                DWORD a[4];
                                LONG ny = g_subbtn[bi].naty + dy, bh = e[3] - e[1];
                                a[0] = (DWORD)e[0]; a[1] = (DWORD)ny;
                                a[2] = (DWORD)e[2]; a[3] = (DWORD)(ny + bh);
                                rz_thiscall(b, (void *)bvt[0xc8 / 4], a, 4);
                                g_subbtn[bi].placed = ny;
                                moved++;
                                changed++;
                            }
                        }
                    }
                    bn = *(void **)bn;
                }
                /* Mark the COLUMN dirty as well, not just the panel.
                 *
                 * FUN_1006d2d0 gates each window paint on that window own dirty byte at +0x60
                 * [CONFIRMED @ SIMUI 0x1006d2d0], and every full-height column carries its OWN
                 * back surface (measured: +0x58 = 36x1081). Invalidating only the panel therefore
                 * left each column composite holding the pixels from when its buttons were at the
                 * top - the owner: "buttons are all in their place, some textures are rendering at
                 * the top". vt+0x154 sets the byte and propagates upward
                 * [CONFIRMED @ SIMUI 0x1006e06b, 0x1006c784]. */
                {   DWORD *cvt2 = *(DWORD **)page;
                    if (cvt2 && !IsBadReadPtr(cvt2, 0x158) && cvt2[0x154 / 4])
                        rz_thiscall(page, (void *)cvt2[0x154 / 4], NULL, 0);
                }
            }
            }
        }
        n = *(void **)n;
    }
    if (moved && (dy > 0 || changed)) {   /* at dy 0, only when a restore actually changed something */
        /* ⭐ INVALIDATE AFTER MOVING, or the cached composite keeps the old pixels.
         *
         * The window geometry was already provably right - a live dump with a submenu open showed
         * every button at LOCAL/ABS y 510..870 and nothing anywhere near the top - yet the owner
         * saw clicked buttons and submenus drawn at the top, and toast labels appear high then
         * jump down. That is stale paint, not stale geometry: rz_side_fit_surface invalidates and
         * THEN this routine moves 54 buttons, so the moves themselves were never invalidated and
         * only regions the engine happened to re-dirty got corrected.
         *
         * vt+0x154 = FUN_1006e06b: set the dirty byte at +0x60 and propagate to every ancestor
         * `[CONFIRMED @ SIMUI 0x1006e06b, 0x1006c784]`. Call it on the PANEL so the whole strip
         * repaints, not on each button. */
        DWORD *pvt = *(DWORD **)p;
        if (pvt && !IsBadReadPtr(pvt, 0x158) && pvt[0x154 / 4])
            rz_thiscall(p, (void *)pvt[0x154 / 4], NULL, 0);
        /* ⭐ REBUILD DERIVED RECTS after moving the item LOCAL rects. vt+0xc8 SetRect writes only the
         * LOCAL rect (+0x84); hit-testing compares the DERIVED rect (+0x14), which the framework
         * rebuilds from local only when the cascade runs. During rz_do_resize the cascade runs after
         * this routine, but on the per-frame poll (where the game re-creates the items later) nothing
         * re-ran it - so the moved items stayed clickable at their OLD native y while their icons drew
         * at the pushed y. That is the "top 5 ok, alert and below all wrong" bug: the divergence grows
         * downward because only the bottom items are pushed far. Rebuild now. */
        {   int did = rz_cascade_derived();
            logf("SIDEKIDS> pushed %d side-panel BUTTON(s) down by %ld (panel %ld tall local, native "
                 "%d) + invalidated the panel%s", moved, dy, panelH, SIDE_NAT_H,
                 did ? " + rebuilt derived rects (hit-test follows the icons)"
                     : " + CASCADE REFUSED (derived rects may lag)");
        }
    }

    /* ⭐ ROOT-LEVEL FLYOUTS. The tool submenu (the column of round icons) is a DIRECT CHILD OF THE
     * ROOT, not of the panel - measured with one open: 0xE194150, class SIMUI+0xa9cc8, depth 0,
     * parent == the root window. So the walk above can never see it, which is why it stayed at the
     * top while everything else moved.
     *
     * Note what is NOT broken: the dropdown list ("Parque pequeno...") already appears beside its
     * moved button, so those popups do follow. Only the ones laid out from a stale anchor near the
     * panel's top need shifting, and `top < dy` is exactly that test - a popup already down at the
     * buttons fails it and is left alone.
     *
     * Deliberately narrow: right edge inside the panel's x-band, and shorter than the panel, so
     * this cannot grab a dialog or the full-screen containers (the corner-widget heuristic already
     * taught me what an unbounded rect test picks up). */
    {   LONG bandL = (LONG)((LONG *)((DWORD)p + 0x80))[0] - 160;   /* panel left, minus a margin */
        void *rhead;
        void *root = NULL;
        DWORD gz = (DWORD)GetModuleHandleA("GZGraphicD.dll");
        int fmoved = 0;
        if (gz && !IsBadReadPtr((void *)(gz + 0x6cdb8), 4)) {
            DWORD *win = *(DWORD **)(gz + 0x6cdb8);
            if (win && !IsBadReadPtr(win, 0x34)) {
                DWORD *sink = (DWORD *)win[0x30 / 4];
                if (sink && !IsBadReadPtr(sink, 0x3c)) root = (void *)sink[0x38 / 4];
            }
        }
        if (root && !IsBadReadPtr(root, 0x38) &&
            (rhead = *(void **)((DWORD)root + 0x34)) != NULL && !IsBadReadPtr(rhead, 4)) {
            void *rn = *(void **)rhead;
            int rguard = 0;
            while (rn && rn != rhead && rguard++ < 300) {
                DWORD *c;
                if (IsBadReadPtr(rn, 0x0c)) break;
                c = *(DWORD **)((DWORD)rn + 8);
                if (c && !IsBadWritePtr(c, 0xa0)) {
                    LONG *e = (LONG *)((DWORD)c + 0x80);
                    LONG h = e[3] - e[1];
                    DWORD *cvt = *(DWORD **)c;
                    /* NOT dialogs (SIMUI+0xa4d64): rz_dialogs_poll owns them. The terrain editor panel
                       (172x480 at the right edge) passed this test and was pushed down by dy here while
                       the dialog dock pulled it back, every poll (owner 2026-10-07: "moves constantly"). */
                    DWORD suif = (DWORD)GetModuleHandleA("SIMUI.DLL");
                    if (cvt && !IsBadReadPtr(cvt, 0xcc) && cvt[0xc8 / 4] &&
                        !(suif && (DWORD)cvt == suif + 0xa4d64) &&
                        e[2] - e[0] > 0 && h > 0 && h < panelH / 2 &&
                        e[2] > bandL && e[1] < dy) {
                        DWORD a[4];
                        a[0] = (DWORD)e[0]; a[1] = (DWORD)(e[1] + dy);
                        a[2] = (DWORD)e[2]; a[3] = (DWORD)(e[3] + dy);
                        rz_thiscall(c, (void *)cvt[0xc8 / 4], a, 4);
                        fmoved++;
                    }
                }
                rn = *(void **)rn;
            }
        }
        if (fmoved) {
            DWORD *pvt2 = *(DWORD **)p;
            if (pvt2 && !IsBadReadPtr(pvt2, 0x158) && pvt2[0x154 / 4])
                rz_thiscall(p, (void *)pvt2[0x154 / 4], NULL, 0);
            logf("SIDEKIDS> pushed %d root-level flyout(s) down by %ld (band x>%ld) + invalidated",
                 fmoved, dy, bandL);
        }
    }
}


/* ⭐ BAR CONTENTS — slide the controls to the right end, beside the minimap.
 *
 * The bar docks and spans the full client width, but its children keep their NATIVE offsets, so the
 * status text, speed buttons, help and RCI stay clustered in the leftmost 599 px with a vast empty
 * stretch to their right. Owner's ask (2026-09-02): bring them next to the minimap.
 *
 * The shift is DERIVED, not hardcoded: the minimap occupies the bottom-right corner and overlaps
 * the bar's own y range, so the target is the minimap's LEFT edge minus the bar's native width -
 * put the block immediately left of the minimap rather than flush to the window edge, where it
 * would slide underneath. Falls back to (clientW - nativeW) when the minimap is not docked.
 *
 * Children are moved with their PARENT-LOCAL rect through vt+0xc8, the same discipline the side
 * panel needed: SetRect on a child takes parent-local coordinates, and feeding it absolute ones
 * adds the parent origin twice. Idempotent (skips anything already shifted), so the periodic pass
 * can re-run it and catch controls the game creates later. */
static void rz_bar_children_right(void) {
    DWORD *bar = (DWORD *)g_hud_top;
    void *head, *n;
    LONG barW, dx, target;
    int guard = 0, moved = 0;
    if (!bar || IsBadReadPtr(bar, 0xa0)) return;
    if (!g_bar_nat_ok) return;
    barW = (LONG)((LONG *)((DWORD)bar + 0x80))[2] - (LONG)((LONG *)((DWORD)bar + 0x80))[0];
    {   LONG natW = g_bar_nat[2] - g_bar_nat[0];
        LONG mmLeft = 0, rciW = 0;
        DWORD sui0 = (DWORD)GetModuleHandleA("SIMUI.DLL");
        DWORD gz0 = (DWORD)GetModuleHandleA("GZGraphicD.dll");
        void *r0 = NULL;
        if (g_mini && !IsBadReadPtr(g_mini, 0x90))
            mmLeft = (LONG)((LONG *)((DWORD)g_mini + 0x80))[0];
        /* ⭐ THE NATIVE LAYOUT, read from the game at 800x600 rather than guessed:
         *     bar     [0   544 599 600]   ends at 599
         *     RCI     [599 520 640 608]   sits BETWEEN the two
         *     minimap [640 436 800 600]   starts at 640
         * So the order is console | RCI | minimap, and the console must stop where the RCI starts,
         * not at the minimap's edge. My first version parked the RCI to the LEFT of the console -
         * the wrong side entirely. Reserve the RCI's width here. */
        if (sui0 && gz0 && !IsBadReadPtr((void *)(gz0 + 0x6cdb8), 4)) {
            DWORD *w0 = *(DWORD **)(gz0 + 0x6cdb8);
            DWORD *s0 = (w0 && !IsBadReadPtr(w0, 0x34)) ? (DWORD *)w0[0x30 / 4] : NULL;
            if (s0 && !IsBadReadPtr(s0, 0x3c)) r0 = (void *)s0[0x38 / 4];
        }
        if (r0 && sui0) {
            int budget = 3000;
            void *rci0 = rz_find_by_vt(r0, sui0 + 0xab274, 0, &budget);
            if (rci0 && !IsBadReadPtr(rci0, 0x90)) {
                LONG *e0 = (LONG *)((DWORD)rci0 + 0x80);
                if (e0[2] - e0[0] > 0) rciW = e0[2] - e0[0];
            }
        }
        target = (mmLeft > natW) ? mmLeft - rciW : barW;
        dx = target - natW;
        /* dx == 0 is the NATIVE layout, not "nothing to do".
         * Bailing on it stranded the bar's children at their wide-window coordinates whenever the
         * window came back to ~800x600: measured at client 800x600 with the art correctly back at
         * [0 552 600 608] while the children still sat at 1256/1795/1737 - a bar with no reachable
         * buttons and no ticker, exactly as the owner reported. Only a NEGATIVE dx is meaningless. */
        if (natW <= 0 || dx < 0) return;
    }
    head = *(void **)((DWORD)bar + 0x34);
    if (!head || IsBadReadPtr(head, 4)) return;
    n = *(void **)head;
    while (n && n != head && guard++ < 200) {
        DWORD *c;
        if (IsBadReadPtr(n, 0x0c)) break;
        c = *(DWORD **)((DWORD)n + 8);
        if (c && !IsBadWritePtr(c, 0xa0)) {
            LONG *e = (LONG *)((DWORD)c + 0x80);
            DWORD *cvt = *(DWORD **)c;
            if (cvt && !IsBadReadPtr(cvt, 0xcc) && cvt[0xc8 / 4] &&
                e[2] - e[0] > 0 && e[3] - e[1] > 0) {
                LONG *nat = NULL;
                int k;
                for (k = 0; k < g_barkid_n; k++)
                    if (g_barkid[k] == (void *)c) { nat = g_barkid_nat[k]; break; }
                if (!nat && g_barkid_n < BARKID_MAX) {      /* first sight: remember it as native */
                    g_barkid[g_barkid_n] = (void *)c;
                    g_barkid_nat[g_barkid_n][0] = e[0]; g_barkid_nat[g_barkid_n][1] = e[1];
                    g_barkid_nat[g_barkid_n][2] = e[2]; g_barkid_nat[g_barkid_n][3] = e[3];
                    nat = g_barkid_nat[g_barkid_n];
                    g_barkid_n++;
                }
                if (nat && (e[0] != nat[0] + dx || e[1] != nat[1])) {
                    DWORD a[4];
                    a[0] = (DWORD)(nat[0] + dx); a[1] = (DWORD)nat[1];
                    a[2] = (DWORD)(nat[2] + dx); a[3] = (DWORD)nat[3];
                    rz_thiscall(c, (void *)cvt[0xc8 / 4], a, 4);
                    moved++;
                }
            }
        }
        n = *(void **)n;
    }
    /* ⭐ AND THE BAR'S OWN ART RECTS. Moving the window children is only half of it: the bar paints
     * child surfaces [0x2a..0x2f] ITSELF into absolute rects stored on the object, so the console
     * art and the four info fields (city name, population, money, date) stay at the left while the
     * controls move right - which is exactly the "second set of controls at the left" the owner
     * sees. Field map, read live from the bar object:
     *     +0x120..+0x12c   where the 600-wide console art is drawn  [0 1033 600 1089]
     *     +0x130..+0x13c   the region the filler is tiled across    [600 1033 2048 1089]
     *     +0x140/+0x150/+0x160/+0x170   the four info-field dests, all at x 8..500
     * Shift every x by the same dx, and flip the two regions so the filler covers what the console
     * vacates. Idempotent: only acts while the console art is still left of dx. */
    {   LONG *art = (LONG *)((DWORD)bar + 0x120);
        LONG *fill = (LONG *)((DWORD)bar + 0x130);
        if (!IsBadWritePtr(art, 0x60) && art[2] - art[0] > 0) {
            int f;
            if (!g_bar_art_ok) {           /* capture the native art geometry once */
                for (f = 0; f < 4; f++) {
                    g_bar_art_nat[f]  = art[f];
                    g_bar_fill_nat[f] = fill[f];
                }
                for (f = 0; f < 4; f++) {
                    LONG *r = (LONG *)((DWORD)bar + 0x140 + f * 0x10);
                    g_bar_info_nat[f][0] = r[0]; g_bar_info_nat[f][1] = r[1];
                    g_bar_info_nat[f][2] = r[2]; g_bar_info_nat[f][3] = r[3];
                }
                g_bar_art_ok = 1;
                logf("BARKIDS> cached native art [%ld %ld %ld %ld] filler [%ld %ld %ld %ld]",
                     art[0], art[1], art[2], art[3], fill[0], fill[1], fill[2], fill[3]);
            }
            /* ABSOLUTE placement from the cached native values, every time - never incremental.
               The bar's own y comes from the CURRENT rect, since the bar re-docks on each resize. */
            {   LONG *br = (LONG *)((DWORD)bar + 0x80);
                LONG dy2 = br[1] - g_bar_art_nat[1];
                if (art[0] != g_bar_art_nat[0] + dx || art[1] != g_bar_art_nat[1] + dy2) {
                    art[0] = g_bar_art_nat[0] + dx;  art[1] = g_bar_art_nat[1] + dy2;
                    art[2] = g_bar_art_nat[2] + dx;  art[3] = g_bar_art_nat[3] + dy2;
                    fill[0] = 0;              fill[1] = g_bar_fill_nat[1] + dy2;
                    fill[2] = art[0];         fill[3] = g_bar_fill_nat[3] + dy2;
                    for (f = 0; f < 4; f++) {
                        LONG *r = (LONG *)((DWORD)bar + 0x140 + f * 0x10);
                        if (g_bar_info_nat[f][2] - g_bar_info_nat[f][0] > 0) {
                            r[0] = g_bar_info_nat[f][0] + dx; r[1] = g_bar_info_nat[f][1] + dy2;
                            r[2] = g_bar_info_nat[f][2] + dx; r[3] = g_bar_info_nat[f][3] + dy2;
                        }
                    }
                    logf("BARKIDS> art -> [%ld %ld %ld %ld], filler -> [%ld %ld %ld %ld] (dx %ld dy %ld)",
                         art[0], art[1], art[2], art[3], fill[0], fill[1], fill[2], fill[3], dx, dy2);
                    moved++;
                }
            }
        }
    }

    /* The RCI indicator travels with the console. It is a separate window (SIMUI+0xab274), not a
     * bar child, and natively sits immediately RIGHT of the 600-wide console at [599 520 640 608].
     * With the console moved to the right end, its native side is where the minimap now lives, so
     * park it against the console's LEFT edge instead - visually adjacent, no overlap. */
    {   DWORD sui3 = (DWORD)GetModuleHandleA("SIMUI.DLL");
        LONG *art = (LONG *)((DWORD)bar + 0x120);
        void *rroot = NULL;
        DWORD gz3 = (DWORD)GetModuleHandleA("GZGraphicD.dll");
        if (sui3 && gz3 && !IsBadReadPtr((void *)(gz3 + 0x6cdb8), 4)) {
            DWORD *w3 = *(DWORD **)(gz3 + 0x6cdb8);
            DWORD *sk3 = (w3 && !IsBadReadPtr(w3, 0x34)) ? (DWORD *)w3[0x30 / 4] : NULL;
            if (sk3 && !IsBadReadPtr(sk3, 0x3c)) rroot = (void *)sk3[0x38 / 4];
        }
        if (rroot && !IsBadReadPtr(art, 0x10)) {
            int budget = 3000;
            void *rci = rz_find_by_vt(rroot, sui3 + 0xab274, 0, &budget);
            if (rci && !IsBadWritePtr(rci, 0xa0)) {
                LONG *e = (LONG *)((DWORD)rci + 0x80);
                LONG w = e[2] - e[0], want = art[2] - 1;   /* right of the console with the native 1-px overlap (599 vs art 600) */
                DWORD *rvt = *(DWORD **)rci;
                /* Cache the RCI's NATIVE rect once (still at native the first time we see it), then
                 * place it at native_y + the bar's vertical shift, so it docks DOWN with the bar
                 * instead of floating at native y and getting clipped (owner: "the lower part of the
                 * RCI is shorter"). The bar's shift is bar_top - native_art_top. */
                if (!g_rci_nat_ok && e[3] - e[1] > 0) {
                    g_rci_nat[0] = e[0]; g_rci_nat[1] = e[1]; g_rci_nat[2] = e[2]; g_rci_nat[3] = e[3];
                    g_rci_nat_ok = 1;
                }
                {   /* Align the RCI's BOTTOM with the bar's bottom. The RCI is 88 px tall vs the bar's
                     * 56, and its native rect hangs 8 px below the bar's, so shifting it by the global
                     * dy pushed its bottom past the client edge and clipped it (owner: "still cutting
                     * off the bottom part of the RCI"). Pinning its bottom to the bar bottom keeps it
                     * fully on-screen; the extra height sticks UP above the bar, which is its native
                     * look. */
                    LONG barBottom = ((LONG *)((DWORD)bar + 0x80))[3];
                    LONG rh = g_rci_nat_ok ? (g_rci_nat[3] - g_rci_nat[1]) : (e[3] - e[1]);
                    /* NATIVE relation (owner 2026-10-08, "there's a gap on the RCI indicator"): natively the RCI top is
                       24 px above the bar top (520 vs 544) and its bottom 8 px hang past the client edge and are cut
                       off. Bottom-aligning it (an earlier request to see the whole RCI) put it 8 px higher than the
                       original and opened a visible step against the bar. Use the native offset. */
                    LONG ny = ((LONG *)((DWORD)bar + 0x80))[1] - 24;
                    if (w > 0 && want > 0 && (e[0] != want || e[1] != ny) &&
                        rvt && !IsBadReadPtr(rvt, 0xcc) && rvt[0xc8 / 4]) {
                        DWORD a[4];
                        a[0] = (DWORD)want;     a[1] = (DWORD)ny;
                        a[2] = (DWORD)(want+w); a[3] = (DWORD)(ny + rh);
                        logf("BARKIDS> RCI [%ld %ld %ld %ld] -> [%ld %ld %ld %ld] (native: top 24 px above the bar top; bar bottom %ld)",
                             e[0], e[1], e[2], e[3], a[0], a[1], a[2], a[3], barBottom);
                        rz_thiscall(rci, (void *)rvt[0xc8 / 4], a, 4);
                        moved++;
                    }
                }
            }
        }
    }

    if (moved) {
        DWORD *bvt = *(DWORD **)bar;
        if (bvt && !IsBadReadPtr(bvt, 0x158) && bvt[0x154 / 4])
            rz_thiscall(bar, (void *)bvt[0x154 / 4], NULL, 0);
        logf("BARKIDS> slid %d bar element(s) right by %ld (bar %ld wide, target x %ld) + invalidated",
             moved, dx, barW, target);
    }
}

/* Re-assert the cached corner widgets' positions absolutely (native+dx/dy). Same as rz_input_geometry
 * item 4a, but standalone so the per-frame poll can call it: after a resize a framework relayout can
 * clobber the corner widget's rect, leaving the minimize button visually right but UNCLICKABLE until
 * the next resize (owner, 2026-09-03). Re-running this a few times a second re-sets both the visual
 * (SetRect) and the hit rect (+0x80) and self-heals that within a frame or two. Idempotent: SetRect
 * only when the position actually differs. */
static void rz_corner_reanchor(void) {
    RECT cr;
    LONG dx, dy, cw, ch;
    int i;
    if (!g_hwnd || !GetClientRect(g_hwnd, &cr)) return;
    cw = cr.right - cr.left; ch = cr.bottom - cr.top;
    dx = cw - NAT_W;
    dy = ch - NAT_H + g_hud_dy;
    if (dx < 0) dx = 0;
    if (dy < 0) dy = 0;
    for (i = 0; i < g_corner_n; i++) {
        void *c = g_corner[i].w;
        LONG *nat = g_corner[i].nat;
        DWORD *vt;
        if (!c || IsBadWritePtr(c, 0xa0)) continue;
        vt = *(DWORD **)c;
        if (!vt || IsBadReadPtr(vt, 0xcc) || !vt[0xc8 / 4]) continue;
        {   LONG *cur = (LONG *)((DWORD)c + 0x14);
            LONG *e = (LONG *)((DWORD)c + 0x80);
            LONG nx = nat[0] + dx, ny = nat[1] + dy;
            int ext_abs = (e[0] == cur[0] && e[1] == cur[1]);
            if (cur[0] != nx || cur[1] != ny) {
                DWORD a[4];
                a[0] = (DWORD)nx;          a[1] = (DWORD)ny;
                a[2] = (DWORD)(nat[2]+dx); a[3] = (DWORD)(nat[3]+dy);
                rz_thiscall(c, (void *)vt[0xc8 / 4], a, 4);
                if (ext_abs) { e[0] = nx; e[1] = ny; e[2] = (LONG)a[2]; e[3] = (LONG)a[3]; }
            }
        }
        /* ⭐ AND widen its ANCESTOR containers. A corner widget's own rect being correct is not enough:
         * the dispatch router (FUN_1001ec22) recurses into a child only if the child's ancestor passes
         * a point-in-rect gate, and an ancestor's LOCAL rect gets re-shrunk to [0 0 800 600] by a
         * relayout after the resize - so a click below the native bottom fails at the container and the
         * button was dead until the NEXT resize re-widened it (owner: "still dead until I resize
         * again"). Re-widening here every ~120ms self-heals it. */
        rz_fix_hud_parents(c, "corner", cw, ch);
    }
}

static void rz_input_geometry(LONG cw, LONG ch, LONG dx, LONG dy) {
    DWORD gz = (DWORD)GetModuleHandleA("GZGraphicD.dll");
    DWORD ss = (DWORD)GetModuleHandleA("SIMSPR.DLL");
    DWORD sc3 = (DWORD)GetModuleHandleA(NULL);
    DWORD *win, *sink, *root;
    void *view;

    if (!gz || !ss) { logf("GEOM> REFUSED: GZGraphicD or SIMSPR not loaded"); return; }
    if (IsBadReadPtr((void *)(gz + 0x6cdb8), 4)) {
        logf("GEOM> REFUSED: gz+0x6cdb8 unreadable"); return;
    }
    win = *(DWORD **)(gz + 0x6cdb8);
    if (!win || IsBadReadPtr(win, 0x48) || win[0] != gz + 0x1f740) {
        logf("GEOM> REFUSED: window object 0x%08lX vftable mismatch", (DWORD)win); return;
    }
    sink = (DWORD *)win[0x30 / 4];
    if (!sink || IsBadReadPtr(sink, 0x3c)) { logf("GEOM> REFUSED: sink unreadable"); return; }
    root = (DWORD *)sink[0x38 / 4];
    if (!root || IsBadWritePtr(root, 0x90)) { logf("GEOM> REFUSED: root unreadable"); return; }

    /* 1. root extent - the hover-label clamp. Widen only, never shrink. */
    {   LONG *e = (LONG *)((DWORD)root + 0x80);
        if (e[2] < cw || e[3] < ch) {
            logf("GEOM> root 0x%08lX ext [%ld %ld %ld %ld] -> [%ld %ld %ld %ld]  (hover label clamp)",
                 (DWORD)root, e[0], e[1], e[2], e[3], e[0], e[1],
                 e[2] < cw ? cw : e[2], e[3] < ch ? ch : e[3]);
            if (e[2] < cw) e[2] = cw;
            if (e[3] < ch) e[3] = ch;
        } else {
            logf("GEOM> root ext already [%ld %ld %ld %ld]", e[0], e[1], e[2], e[3]);
        }
    }

    /* 2+3. the city view, found by IDENTITY (its vt+0xe4 is SIMSPR FUN_1004ecd3), never by a
           remembered pointer - the object is at a different address every launch. */
    {   int budget = 3000;
        view = rz_find_view(root, ss + 0x4ecd3, 0, &budget);
    }
    if (!view) { logf("GEOM> city view NOT FOUND (vt+0xe4 SIMSPR+0x4ecd3 + outer vt SIMSPR+0x67894) - map/camera unfixed"); return; }
    if (IsBadWritePtr(view, 0xe4)) { logf("GEOM> city view 0x%08lX unwritable", (DWORD)view); return; }
    {   LONG *r = (LONG *)((DWORD)view + 0x14);
        LONG *b = (LONG *)((DWORD)view + 0xd4);
        logf("GEOM> city view 0x%08lX hit [%ld %ld %ld %ld] bounds [%ld %ld %ld %ld]",
             (DWORD)view, r[0], r[1], r[2], r[3], b[0], b[1], b[2], b[3]);
        /* Cache the engine's NATIVE bounds the first time we see them. Measured on every logged run:
         * the first call sees [0 0 704 544] = 800x600 minus the 96-wide side panel and the 56-tall bar,
         * because nothing but this function ever writes the field after load. Accept only a rect that
         * fits the native client, so a pointer that was already widened can never be cached. */
        if (!g_view_nat_ok && b[0] == 0 && b[1] == 0 && b[2] > 0 && b[3] > 0 &&
            b[2] <= NAT_W && b[3] <= NAT_H) {
            g_view_nat[0] = b[0]; g_view_nat[1] = b[1]; g_view_nat[2] = b[2]; g_view_nat[3] = b[3];
            g_view_nat_ok = 1;
            logf("EDGE> native view bounds cached [%ld %ld %ld %ld]", b[0], b[1], b[2], b[3]);
        }
        if (g_viewfix) rz_view_rect_assert(cw, ch);   /* local + hit, exact; survives the cascade */
        else {
            if (r[2] < cw) r[2] = cw;
            if (r[3] < ch) r[3] = ch;
        }
        if (g_edgefix && g_view_nat_ok) {
            /* ⭐ EDGE-SCROLL BAND (2026-10-05, verify/resize_edgescroll).
             *
             * These bounds feed TWO readers. `FUN_1004947d` disarms the right-drag pan for a point
             * outside them (item 3 above). And `FUN_10043989(outer)` builds the four edge-scroll bands
             * `outer+0x178..+0x1c4` from them as base +-64 (x) / +-48 (y) `[CONFIRMED @ SIMSPR
             * 0x10043989]`, which the mouse-move test `FUN_10043a38` (outer vt+0x40, reached from sub
             * vt+0x1cc `FUN_1004947d` -> outer vt+0x7c `FUN_10049a6e`; vtables read from the PE)
             * compares every move against `[CONFIRMED @ SIMSPR 0x10043a38, 0x10049a6e]`.
             * The engine rebuilds the bands only on load (`FUN_10044323`, outer vt+0xa8) and on
             * event 0x624a8241 (`FUN_10048d7a`), neither of which fires on a resize. So the old
             * widen-only write left the bands at their native positions: at 2048 wide the "right
             * edge" fired around x=640..704, mid-window, and the real edges never fired.
             *
             * Bounds = native + (dx, dy) on the right/bottom, EXACT in both directions (the old write
             * never shrank, so after a restore-down the rect stayed at the maximized size). This keeps
             * the native relationship: the bands end at the side panel and the bar, where the mouse can
             * reach them, instead of under the HUD. Then the game's own builder recomputes the bands. */
            DWORD *ovt;
            void  *outer = (void *)((DWORD)view - 4);
            b[0] = g_view_nat[0];      b[1] = g_view_nat[1];
            b[2] = g_view_nat[2] + dx; b[3] = g_view_nat[3] + dy;
            if (b[2] <= b[0]) b[2] = b[0] + 1;
            if (b[3] <= b[1]) b[3] = b[1] + 1;
            ovt = IsBadReadPtr(outer, 0x1c8) ? NULL : *(DWORD **)outer;
            if (ovt == (DWORD *)(ss + 0x67894)) {   /* expect-or-refuse: the city view outer vtable */
                LONG *bd = (LONG *)((DWORD)outer + 0x178);
                rz_thiscall(outer, (void *)(ss + 0x43989), NULL, 0);
                logf("EDGE> bands rebuilt from bounds [%ld %ld %ld %ld]: inner [%ld %ld %ld %ld] "
                     "L [%ld %ld %ld %ld] T [%ld %ld %ld %ld] R [%ld %ld %ld %ld] B [%ld %ld %ld %ld] enabled=%d",
                     b[0], b[1], b[2], b[3], bd[0], bd[1], bd[2], bd[3],
                     bd[4], bd[5], bd[6], bd[7],          /* +0x188 left   -> flag +0x1e4 */
                     bd[8], bd[9], bd[10], bd[11],        /* +0x198 top    -> flag +0x1e1 */
                     bd[12], bd[13], bd[14], bd[15],      /* +0x1a8 right  -> flag +0x1e3 */
                     bd[16], bd[17], bd[18], bd[19],      /* +0x1b8 bottom -> flag +0x1e2 */
                     *(BYTE *)((DWORD)outer + 0x177));
                rz_edge_off();   /* windowed default: no edge scrolling, re-neutralise at once */
            } else {
                logf("EDGE> REFUSED band rebuild: outer 0x%08lX vtable 0x%08lX != SIMSPR+0x67894",
                     (DWORD)outer, (DWORD)ovt);
            }
        } else {
            if (b[2] < cw) b[2] = cw;
            if (b[3] < ch) b[3] = ch;
            if (!g_edgefix) logf("EDGE> EDGEFIX OFF - control arm, bands left as built");
            else logf("EDGE> no native bounds cached - bands left as built");
        }
        logf("GEOM> city view    hit [%ld %ld %ld %ld] bounds [%ld %ld %ld %ld]  (map clicks + camera pan)",
             r[0], r[1], r[2], r[3], b[0], b[1], b[2], b[3]);
    }

    /* 4. native-corner widgets, DIRECT children of the root only.
     *
     * ABSOLUTE from a cached native rect, not incremental. The discovery heuristic below only matches
     * a widget while it is still inside the NATIVE bounds; once moved it fails `fits` and is never
     * matched again, so an incremental `r[0]+dx` fired exactly once and the widget then stayed put
     * while the window kept growing (owner: "the minimize button is not following"). So: first move
     * every ALREADY-CACHED widget to native+dx (idempotent), THEN discover any still-native widget,
     * cache its native rect, and place it. */
    {   void *head;
        void *n;
        int guard = 0, moved = 0, i;

        /* 4a. reposition cached corner widgets absolutely. */
        for (i = 0; i < g_corner_n; i++) {
            void *c = g_corner[i].w;
            LONG *nat = g_corner[i].nat;
            DWORD *vt;
            if (!c || IsBadWritePtr(c, 0xa0)) continue;
            vt = *(DWORD **)c;
            if (!vt || IsBadReadPtr(vt, 0xcc) || !vt[0xc8 / 4]) continue;
            {   LONG *cur = (LONG *)((DWORD)c + 0x14);
                LONG *e = (LONG *)((DWORD)c + 0x80);
                LONG nx = nat[0] + dx, ny = nat[1] + dy;
                int ext_abs = (e[0] == cur[0] && e[1] == cur[1]);   /* absolute, not parent-local */
                if (cur[0] != nx || cur[1] != ny) {
                    DWORD a[4];
                    a[0] = (DWORD)nx;          a[1] = (DWORD)ny;
                    a[2] = (DWORD)(nat[2]+dx); a[3] = (DWORD)(nat[3]+dy);
                    rz_thiscall(c, (void *)vt[0xc8 / 4], a, 4);
                    if (ext_abs) { e[0] = nx; e[1] = ny; e[2] = (LONG)a[2]; e[3] = (LONG)a[3]; }
                    moved++;
                }
            }
        }

        /* 4b. discover NEW corner widgets still at their native position and cache them. */
        head = *(void **)((DWORD)root + 0x34);
        if (!head || IsBadReadPtr(head, 4)) return;
        n = *(void **)head;
        while (n && n != head && guard++ < 500) {
            DWORD *c;
            if (IsBadReadPtr(n, 0x0c)) break;
            c = *(DWORD **)((DWORD)n + 8);
            if (c && !IsBadWritePtr(c, 0xa0) && g_corner_n < CORNER_MAX) {
                LONG *r = (LONG *)((DWORD)c + 0x14);
                int already = 0, k;
                for (k = 0; k < g_corner_n; k++) if (g_corner[k].w == (void *)c) { already = 1; break; }
                /* fits inside the native screen AND anchored to its bottom-right corner AND small.
                   ⚠️ The size bound is not cosmetic: without it a FULL-SCREEN [0 0 800 600] window
                   passes the corner test and gets flung off-screen. The real widget is 26x26. */
                if (!already) {
                    int fits = r[0] >= 0 && r[1] >= 0 && r[2] <= NAT_W && r[3] <= NAT_H;
                    int corner = r[2] >= NAT_W - 40 && r[3] >= NAT_H - 40;
                    int is_small = (r[2] - r[0]) > 0 && (r[2] - r[0]) <= 200 &&
                                (r[3] - r[1]) > 0 && (r[3] - r[1]) <= 200;
                    int is_label = sc3 && c[0] == sc3 + 0xd3bcc;   /* the hover label, excluded */
                    if (fits && corner && is_small && !is_label) {
                        DWORD *vt = *(DWORD **)c;
                        if (vt && !IsBadReadPtr(vt, 0xcc) && vt[0xc8 / 4]) {
                            LONG *e = (LONG *)((DWORD)c + 0x80);
                            LONG nx = r[0] + dx, ny = r[1] + dy;
                            int ext_abs = (e[0] == r[0] && e[1] == r[1]);
                            DWORD a[4];
                            g_corner[g_corner_n].w = (void *)c;
                            g_corner[g_corner_n].nat[0] = r[0]; g_corner[g_corner_n].nat[1] = r[1];
                            g_corner[g_corner_n].nat[2] = r[2]; g_corner[g_corner_n].nat[3] = r[3];
                            g_corner_n++;
                            a[0] = (DWORD)nx;        a[1] = (DWORD)ny;
                            a[2] = (DWORD)(r[2]+dx); a[3] = (DWORD)(r[3]+dy);
                            rz_thiscall(c, (void *)vt[0xc8 / 4], a, 4);
                            if (ext_abs) { e[0] = nx; e[1] = ny; e[2] = (LONG)a[2]; e[3] = (LONG)a[3]; }
                            logf("GEOM> corner widget 0x%08lX cached native [%ld %ld %ld %ld] -> [%ld %ld]%s",
                                 (DWORD)c, r[0], r[1], r[2], r[3], nx, ny,
                                 ext_abs ? " (hit rect carried)" : " (hit rect parent-local)");
                            moved++;
                        }
                    }
                }
            }
            n = *(void **)n;
        }
        if (moved)
            logf("GEOM> relocated %d corner widget(s) by (%ld,%ld) [%d cached]", moved, dx, dy, g_corner_n);
    }
}

static void rz_mini_dock(void) {
    LONG *r;
    RECT cr;
    LONG w, h, nx, ny;
    if (!g_minion || !g_mini || IsBadReadPtr(g_mini, 0xa0)) return;
    if (!g_hwnd || !GetClientRect(g_hwnd, &cr)) return;
    r = (LONG *)((DWORD)g_mini + 0x90);
    w = r[2] - r[0]; h = r[3] - r[1];
    if (w <= 0 || h <= 0) { logf("MINI> dock skipped: rect %ldx%ld", w, h); return; }
    nx = (cr.right - cr.left) - w;
    ny = (cr.bottom - cr.top) - h + g_hud_dy;   /* same bottom bias as the bar and the cluster */
    if (nx < 0 || ny < 0) { logf("MINI> dock skipped: window smaller than the minimap"); return; }
    if (r[0] == nx && r[1] == ny) { if (!g_reassert_quiet) logf("MINI> already docked at [%ld,%ld]", nx, ny); return; }
    {   /* capture the OLD position before overwriting - the hit-origin move verifies against it */
        LONG ox = r[0], oy = r[1];
        logf("MINI> dock [%ld %ld %ld %ld] -> [%ld %ld %ld %ld]",
             r[0], r[1], r[2], r[3], nx, ny, nx + w, ny + h);
        r[0] = nx; r[1] = ny; r[2] = nx + w; r[3] = ny + h;
        /* ⭐ AND THE AUTHORITATIVE LOCAL RECT. Writing only +0x90 (the blit dest) moved the pixels
         * and left the minimap's ABS rect at its native [640 436 ...] - measured live, with its
         * children deriving their absolute rects from that stale origin (640+138, 436+72). +0x90
         * is itself derived (`FUN_1006d8b4`), so the local rect is what has to change. */
        {   LONG *lr = (LONG *)((DWORD)g_mini + 0x80);
            if (!IsBadWritePtr(lr, 0x10) && lr[2] - lr[0] > 0 && lr[3] - lr[1] > 0) {
                logf("MINI> local [%ld %ld %ld %ld] -> [%ld %ld %ld %ld]",
                     lr[0], lr[1], lr[2], lr[3], nx, ny, nx + w, ny + h);
                lr[0] = nx; lr[1] = ny; lr[2] = nx + w; lr[3] = ny + h;
            }
        }
        rz_win_move_hit(g_mini, "minimap", ox, oy, nx, ny);
    }
}
/* The bar's IDirectDrawSurface*, captured AT REFIT TIME (run 16). Run 15 read it at dump time, but
 * the pointer changes on every recreate, so the dump described the surface at the END of the window
 * rather than the one blitting during it. Both the new and the replaced surface are kept: the old
 * DD surface is not necessarily destroyed - FUN_1001420d overwrites `param_1[0x11]` without freeing
 * the previous sub-object [CONFIRMED @ GZGraphicD 0x1001420d] - so a stale surface may still be
 * blitted by something holding a reference. */
static DWORD   g_bar_surf, g_bar_surf_prev;
/* Per-child surfaces (run 18). g_bar_surf is set by whichever child refits LAST, so after run 17 it
 * meant child[0x2b] while the log still said "THE HUD BAR" - correct attribution, misleading label.
 * These are indexed [0x2a + i] and let both the resolver and the caller filter name the right one. */
static DWORD   g_child_surf[6], g_child_surf_prev[6];

/* ---- CALLER CAPTURE (run 18) ------------------------------------------------------------------
 * Run 17 proved the tile COUNT is engine-side, not surface geometry. Naming the loop that issues
 * those blits is what runs 7-8 tried to do by SCANNING the stack, and failed at twice (junk
 * addresses, then selection bias against the very samples of interest).
 *
 * That is unnecessary now. The COM vtable hook means we hold the Blt call inside a C function, so
 * `_ReturnAddress()` gives the EXACT caller - a compiler intrinsic, no scanning, no heuristics, no
 * validation. Bucketed only for blits whose SOURCE is the tiled child, so the table stays clean. */
#define RET_BUCKETS 32
static DWORD   g_ret_key[RET_BUCKETS], g_ret_cnt[RET_BUCKETS];
static __int64 g_ret_time[RET_BUCKETS];
static DWORD   g_ret_filter;         /* the source surface whose callers we are recording */
/* Run 18 captured GZGraphicD+0x18C89 = FUN_10018c58+0x31 - INSIDE the engine's own Blt wrapper, one
 * frame too shallow. The tiling loop is that wrapper's CALLER. The wrapper is already hooked
 * (fnlog_enter idx 1) and the stub's frame layout gives f[9] = the return address into its caller
 * (sc3resize.c: "f[9]=return address, f[10..]=stack args", verbatim from sc3probe.c:8650-8658), so
 * the heartbeat stashes it here immediately before the Blt and the ddraw hook buckets it. */
static DWORD   g_wrapper_caller;
/* Two frames further up (run 20). FUN_10014894 establishes a frame pointer (`push ebp; mov ebp,esp`
 * at 0x14894, disassembled in run 19) and it is still live at FUN_10018c58 entry, so from the stub's
 * pushad layout (edi,esi,ebp,esp,ebx,edx,ecx,eax => f[3] = EBP):
 *   L2 = *(ebp + 4)      -> the return into FUN_10014894's CALLER = the tiling loop
 *   L3 = *(*(ebp) + 4)   -> one further, IF that frame also uses ebp
 * L2 rests on a frame pointer proven in the disassembly. L3 is opportunistic: /O2 omits frame
 * pointers freely, so it is a HINT, not a result - the exact hazard that made runs 7-8 useless. */
static DWORD   g_caller_l2, g_caller_l3;
#define L_BUCKETS 24
static DWORD   g_l2_key[L_BUCKETS], g_l2_cnt[L_BUCKETS];
static DWORD   g_l3_key[L_BUCKETS], g_l3_cnt[L_BUCKETS];

/* Name a source IDirectDrawSurface* by searching the objects we can reach for one whose sub-object
 * holds it at sub+0x04. Identity by POINTER against a reachable owner, never by dims or by heap
 * proximity - run 15 could only offer region adjacency, which is not evidence. */
static void rz_name_surface(DWORD surf, char *out, int n) {
    DWORD iso = 0;
    int i;
    out[0] = 0;
    if (!surf) { lstrcpynA(out, "  <NULL: colour fill>", n); return; }
    for (i = 0; i < 6; i++) {
        if (g_child_surf[i] && surf == g_child_surf[i]) {
            _snprintf(out, n, "  <<< HUD child[0x%x] surface (captured at its refit)", 0x2a + i);
            return;
        }
        if (g_child_surf_prev[i] && surf == g_child_surf_prev[i]) {
            _snprintf(out, n, "  <<< HUD child[0x%x] PREVIOUS surface (replaced, not freed)", 0x2a + i);
            return;
        }
    }
    if (g_bridge && !IsBadReadPtr(g_bridge, 0x1c)) iso = ((DWORD *)g_bridge)[0x18 / 4];
    if (iso && !IsBadReadPtr((void *)iso, 0x4f0)) {
        static const struct { DWORD off; const char *nm; } isos[] = {
            { 0x74,  "iso render target" }, { 0x4ec, "iso device/blit-dest surface" } };
        for (i = 0; i < 2; i++) {
            DWORD R = ((DWORD *)iso)[isos[i].off / 4], s;
            if (!R || IsBadReadPtr((void *)R, 0x48)) continue;
            s = ((DWORD *)R)[0x44 / 4];
            if (s && !IsBadReadPtr((void *)s, 8) && ((DWORD *)s)[0x04 / 4] == surf) {
                _snprintf(out, n, "  <<< %s (%lux%lu)", isos[i].nm,
                          ((DWORD *)R)[0x24 / 4], ((DWORD *)R)[0x28 / 4]);
                return;
            }
        }
    }
    if (g_hud_top && !IsBadReadPtr(g_hud_top, 0xc0)) {
        for (i = 0x2a; i <= 0x2f; i++) {
            DWORD c = ((DWORD *)g_hud_top)[i], s;
            if (!c || IsBadReadPtr((void *)c, 0x48)) continue;
            s = ((DWORD *)c)[0x44 / 4];
            if (s && !IsBadReadPtr((void *)s, 8) && ((DWORD *)s)[0x04 / 4] == surf) {
                _snprintf(out, n, "  <<< HUD child[0x%x] (%lux%lu)", i,
                          ((DWORD *)c)[0x24 / 4], ((DWORD *)c)[0x28 / 4]);
                return;
            }
        }
    }
    lstrcpynA(out, "  (not reachable from iso or the HUD children)", n);
}
static double  g_win_ms = 10000.0;   /* length of the current measurement window, for the %-of-window
                                        figure. Run 13 printed percentages against a hardcoded 10 s
                                        while sweep windows were 8 s - all understated. */
static DWORD   g_blt_key[BLT_BUCKETS], g_blt_cnt[BLT_BUCKETS];
static __int64 g_blt_time[BLT_BUCKETS];
static __int64 g_blt_last;
static DWORD   g_blt_lastkey, g_blt_outliers, g_blt_total;

static void rz_blt_sample(DWORD key) {
    LARGE_INTEGER now;
    QueryPerformanceCounter(&now);
    if (g_blt_last && g_blt_lastkey) {
        __int64 d = now.QuadPart - g_blt_last;
        double ms = g_freq.QuadPart ? (1000.0 * (double)d / (double)g_freq.QuadPart) : 0.0;
        if (ms > BLT_OUTLIER_MS) {
            g_blt_outliers++;                      /* a resize frame, not a blit - do not average */
        } else {
            DWORD k = g_blt_lastkey;
            DWORD i = (k * 2654435761u) >> 24 & (BLT_BUCKETS - 1), tries = 0;
            while (tries++ < 32) {
                if (g_blt_key[i] == k || g_blt_key[i] == 0) {
                    g_blt_key[i] = k; g_blt_cnt[i]++; g_blt_time[i] += d; g_blt_total++;
                    break;
                }
                i = (i + 1) & (BLT_BUCKETS - 1);
            }
        }
    }
    g_blt_last = now.QuadPart;
    g_blt_lastkey = key;
}
static void rz_blt_reset(void) {
    g_ddblt_time = 0; g_ddblt_calls = 0;

    memset(g_bfl_key, 0, sizeof(g_bfl_key)); memset((void *)g_bfl_cnt, 0, sizeof(g_bfl_cnt));

    memset(g_bfl_time, 0, sizeof(g_bfl_time));

    g_blt_area = 0; g_blt_areacnt = 0; g_blt_nullrect = 0; g_blt_nullsrc = 0;

    g_blt_maxw = 0; g_blt_maxh = 0;


    memset(g_l2_key, 0, sizeof(g_l2_key)); memset((void *)g_l2_cnt, 0, sizeof(g_l2_cnt));



    memset(g_l3_key, 0, sizeof(g_l3_key)); memset((void *)g_l3_cnt, 0, sizeof(g_l3_cnt));



    memset(g_ret_key, 0, sizeof(g_ret_key)); memset((void *)g_ret_cnt, 0, sizeof(g_ret_cnt));



    memset(g_ret_time, 0, sizeof(g_ret_time));



    memset(g_mm_l1, 0, sizeof(g_mm_l1)); memset((void *)g_mm_l1c, 0, sizeof(g_mm_l1c));




    memset(g_mm_l2, 0, sizeof(g_mm_l2)); memset((void *)g_mm_l2c, 0, sizeof(g_mm_l2c));




    g_mm_src = 0; g_mm_w = 0; g_mm_h = 0;




    memset(g_src_rect, 0, sizeof(g_src_rect));




    memset(g_src_key, 0, sizeof(g_src_key)); memset((void *)g_src_cnt, 0, sizeof(g_src_cnt));


    memset(g_src_time, 0, sizeof(g_src_time));
    memset(g_blt_key, 0, sizeof(g_blt_key));
    memset((void *)g_blt_cnt, 0, sizeof(g_blt_cnt));
    memset(g_blt_time, 0, sizeof(g_blt_time));
    g_blt_last = 0; g_blt_lastkey = 0; g_blt_outliers = 0; g_blt_total = 0;
}
/* Dump each blitting object with its call count and average interval. Where the object is a raster
 * of a class we know, print its dims too - that is what lets "the 2048x56 bar" be told apart from
 * "the 2048x1081 iso view" without guessing. */
static void rz_blt_dump(const char *tag) {
    DWORD gz = (DWORD)GetModuleHandleA("GZGraphicD.dll");
    DWORD i, rank;
    static DWORD taken[16];
    {   /* EXACT time inside IDirectDrawSurface::Blt, measured by the COM slot hook. Compared against
           the heartbeat intervals below, this splits "the blit itself got slower" from "something
           between blits got slower" - the question run 9 could not answer. */
        double dd = g_freq.QuadPart ? (1000.0 * (double)g_ddblt_time / (double)g_freq.QuadPart) : 0.0;
        if (g_blt_slot && g_blt_slot != (DWORD *)-1)
            logf("BLT> ---- %s ---- INSIDE ddraw Blt: %lu calls, %.1f ms total, %.4f ms avg "
                 "(%.1f%% of the measurement window)", tag, g_ddblt_calls, dd,
                 g_ddblt_calls ? dd / g_ddblt_calls : 0.0, dd / (g_win_ms / 100.0));
        else
            logf("BLT> ---- %s ---- INSIDE ddraw Blt: NOT HOOKED (no split available)", tag);
    }
    if (g_blt_slot && g_blt_slot != (DWORD *)-1) {
        DWORD i;
        logf("BLT> %s ARGS: dest rects=%lu avg-area=%.0f px max=%ldx%ld | NULL-dest=%lu NULL-src=%lu",
             tag, g_blt_areacnt,
             g_blt_areacnt ? (double)g_blt_area / g_blt_areacnt : 0.0,
             g_blt_maxw, g_blt_maxh, g_blt_nullrect, g_blt_nullsrc);
        {   /* SOURCE attribution. Each source is resolved by rz_name_surface, which searches the
               objects we can reach for one whose sub-object holds it at sub+0x04
               [CONFIRMED @ GZGraphicD 0x10018a82]. Identity by POINTER against a reachable owner -
               run 15 could only offer heap-region adjacency, which is not evidence. */
            DWORD rank;
            static DWORD taken[24];
            logf("BLT> %s SOURCES (bar surface at refit=0x%08lX, previous=0x%08lX)",
                 tag, g_bar_surf, g_bar_surf_prev);
            for (rank = 0; rank < 8; rank++) {
                DWORD best = 0xFFFFFFFF, j; __int64 bestt = -1;
                for (i = 0; i < SRC_BUCKETS; i++) {
                    int already = 0;
                    if (!g_src_cnt[i]) continue;
                    for (j = 0; j < rank; j++) if (taken[j] == i) { already = 1; break; }
                    if (already) continue;
                    if (g_src_time[i] > bestt) { bestt = g_src_time[i]; best = i; }
                }
                if (best == 0xFFFFFFFF) break;
                taken[rank] = best;
                {   double ms = g_freq.QuadPart
                                ? (1000.0 * (double)g_src_time[best] / (double)g_freq.QuadPart) : 0.0;
                    DWORD k = g_src_key[best];
                    char nm[160];
                    rz_name_surface(k, nm, sizeof(nm));
                    {   LONG rl = g_src_rect[best][0], rt = g_src_rect[best][1];
                        LONG rr = g_src_rect[best][2], rb2 = g_src_rect[best][3];
                        LONG rw = rr - rl, rh = rb2 - rt;
                        logf("BLT> %s SRC #%lu 0x%08lX calls=%lu total=%.1f ms avg=%.4f ms "
                             "dest=[%ld %ld %ld %ld] %ldx%ld%s%s",
                             tag, rank + 1, k, g_src_cnt[best], ms,
                             g_src_cnt[best] ? ms / g_src_cnt[best] : 0.0,
                             rl, rt, rr, rb2, rw, rh,
                             (rw > 40 && rh > 40 && rw < rh * 2 && rh < rw * 2)
                                 ? "  <<< SQUARE-ISH" : "", nm);
                    }
                }
            }
        }
        {   /* EXACT callers of the tiled child's blits - the engine loop we are hunting. This is
               what runs 7-8 failed to obtain by stack scanning; `_ReturnAddress()` needs no
               validation because it is the return address, not a candidate for one. */
            DWORD i2, any = 0;
            for (i2 = 0; i2 < RET_BUCKETS && g_ret_cnt[i2]; i2++) {
                char who[160];
                double ms = g_freq.QuadPart
                            ? (1000.0 * (double)g_ret_time[i2] / (double)g_freq.QuadPart) : 0.0;
                rz_modstr(g_ret_key[i2], who, sizeof(who));
                logf("BLT> %s CALLER %s calls=%lu total=%.1f ms  (FUN_10018c58's caller = the tiling loop)",
                     tag, who, g_ret_cnt[i2], ms);
                any = 1;
            }
            if (!any)
                logf("BLT> %s CALLER: no blits from child[0x2b] this window (filter=0x%08lX)",
                     tag, g_ret_filter);
            {   /* MINIMAP callers, geometry-locked (run 26). */

                DWORD m;

                logf("BLT> %s MINIMAP src=0x%08lX %lux%lu", tag, g_mm_src, g_mm_w, g_mm_h);

                for (m = 0; m < MM_BUCKETS && g_mm_l1c[m]; m++) {

                    char who[160]; rz_modstr(g_mm_l1[m], who, sizeof(who));

                    logf("BLT> %s MINIMAP L1 %s calls=%lu  (exact, f[9])", tag, who, g_mm_l1c[m]);

                }

                for (m = 0; m < MM_BUCKETS && g_mm_l2c[m]; m++) {

                    char who[160]; rz_modstr(g_mm_l2[m], who, sizeof(who));

                    logf("BLT> %s MINIMAP L2 %s calls=%lu  [UNCERTAIN - frame-pointer walk]",

                         tag, who, g_mm_l2c[m]);

                }

            }

            /* L2: FUN_10014894's caller = THE TILING LOOP. Rests on a frame pointer proven in the
               run-19 disassembly, so this is a result, not a guess. */
            for (i2 = 0; i2 < L_BUCKETS && g_l2_cnt[i2]; i2++) {
                char who[160];
                rz_modstr(g_l2_key[i2], who, sizeof(who));
                logf("BLT> %s LOOP(L2) %s calls=%lu  <- FUN_10014894's caller", tag, who, g_l2_cnt[i2]);
            }
            /* L3: one further up. OPPORTUNISTIC - valid only if that frame also uses ebp, which /O2
               does not guarantee. Report as a HINT; do not build on it without confirmation. */
            for (i2 = 0; i2 < L_BUCKETS && g_l3_cnt[i2]; i2++) {
                char who[160];
                rz_modstr(g_l3_key[i2], who, sizeof(who));
                logf("BLT> %s hint(L3) %s calls=%lu  [UNCERTAIN - frame-pointer walk]",
                     tag, who, g_l3_cnt[i2]);
            }
        }
        for (i = 0; i < BFL_BUCKETS && g_bfl_cnt[i]; i++) {
            double ms = g_freq.QuadPart ? (1000.0 * (double)g_bfl_time[i] / (double)g_freq.QuadPart) : 0.0;
            logf("BLT> %s FLAGS 0x%08lX calls=%lu total=%.1f ms avg=%.4f ms%s%s%s%s",
                 tag, g_bfl_key[i], g_bfl_cnt[i], ms, g_bfl_cnt[i] ? ms / g_bfl_cnt[i] : 0.0,
                 (g_bfl_key[i] & 0x01000000) ? " WAIT"    : "",   /* DDBLT_WAIT        */
                 (g_bfl_key[i] & 0x00000080) ? " KEYSRC"  : "",   /* DDBLT_KEYSRC      */
                 (g_bfl_key[i] & 0x00000400) ? " ROP"     : "",   /* DDBLT_ROP         */
                 (g_bfl_key[i] & 0x10000000) ? " ASYNC"   : "");  /* DDBLT_ASYNC       */
        }
    }
    logf("BLT> ---- %s ---- intervals=%lu outliers(>%dms)=%lu",
         tag, g_blt_total, BLT_OUTLIER_MS, g_blt_outliers);
    for (rank = 0; rank < 12; rank++) {
        DWORD best = 0xFFFFFFFF, j; __int64 bestt = -1;
        for (i = 0; i < BLT_BUCKETS; i++) {
            int already = 0;
            if (!g_blt_key[i]) continue;
            for (j = 0; j < rank; j++) if (taken[j] == i) { already = 1; break; }
            if (already) continue;
            if (g_blt_time[i] > bestt) { bestt = g_blt_time[i]; best = i; }
        }
        if (best == 0xFFFFFFFF) break;
        taken[rank] = best;
        {
            DWORD o = g_blt_key[best];
            double tot = g_freq.QuadPart ? (1000.0 * (double)g_blt_time[best] / (double)g_freq.QuadPart) : 0.0;
            char dims[320];
            dims[0] = 0;
            /* IDENTITY: vtable -> MODULE+RVA always. For the surface SUB-OBJECT class
               (GZGraphicD+0x1F0AC, run 10) also decode:
                 sub+0xe8 = the OWNING raster  [CONFIRMED @ GZGraphicD 0x100142a2:41]
                 sub+0x74 = DDSCAPS.dwCaps - the DDSURFACEDESC sits at sub+0x0c and ddsCaps is at
                            DDSD+0x68, which is the exact field FUN_10019273 writes when it picks
                            video vs system memory  [CONFIRMED @ GZGraphicD 0x10019273]
               This tests, rather than assumes, whether widening the bar moves a surface between
               video and system memory. */
            if (o && !IsBadReadPtr((void *)o, 0x2c)) {
                DWORD *vt = *(DWORD **)o;
                if (!IsBadReadPtr(vt, 4)) {
                    char who[120];
                    rz_modstr((DWORD)vt, who, sizeof(who));
                    if (gz && (DWORD)vt == gz + GZ_RVA_VT_SURFACE &&
                        !IsBadReadPtr((void *)o, 0xf0)) {
                        DWORD caps  = ((DWORD *)o)[0x74 / 4];
                        DWORD owner = ((DWORD *)o)[0xe8 / 4];
                        DWORD ow = 0, oh = 0;
                        if (owner && !IsBadReadPtr((void *)owner, 0x2c)) {
                            ow = ((DWORD *)owner)[0x24 / 4];
                            oh = ((DWORD *)owner)[0x28 / 4];
                        }
                        _snprintf(dims, sizeof(dims),
                                  " SURFACE caps=0x%08lX[%s%s%s%s%s] owner=0x%08lX %lux%lu",
                                  caps,
                                  (caps & 0x4000)     ? "VIDMEM "   : "",
                                  (caps & 0x800)      ? "SYSMEM "   : "",
                                  (caps & 0x200)      ? "PRIMARY "  : "",
                                  (caps & 0x40)       ? "OFFSCR "   : "",
                                  (caps & 0x20000000) ? "NONLOCAL " : "",
                                  owner, ow, oh);
                    } else if (gz && ((DWORD)vt == gz + GZ_RVA_VT_RASTER ||
                                      (DWORD)vt == gz + GZ_RVA_VT_BLITDEST)) {
                        _snprintf(dims, sizeof(dims), " vt=%s raster %lux%lu", who,
                                  ((DWORD *)o)[0x24 / 4], ((DWORD *)o)[0x28 / 4]);
                    } else {
                        _snprintf(dims, sizeof(dims), " vt=%s", who);
                    }
                }
            }
            logf("BLT> %s #%02lu obj=0x%08lX%s calls=%lu total=%.1f ms avg=%.3f ms (%.1f%% of window)",
                 tag, rank + 1, o, dims, g_blt_cnt[best], tot,
                 g_blt_cnt[best] ? tot / g_blt_cnt[best] : 0.0,
                 tot / 100.0);   /* the phase window is 10 s = 10000 ms, so ms/100 is a percent */
        }
    }
}

/* ---- I3b: EXACT time INSIDE IDirectDrawSurface::Blt (2026-08-31) ------------------------------
 * Run 9 localized the regression to one object but could only measure the INTERVAL between
 * heartbeat entries - it cannot say whether the cost is inside the Blt or after it.
 *
 * Getting entry+exit on `FUN_10018c58` would mean prologue-wrapping or return-address patching a
 * function that runs ~2000x/s on the render thread. That is a real crash risk for a measurement.
 *
 * Instead, patch the COM vtable slot of IDirectDrawSurface::Blt itself (+0x14; index 5 after
 * QueryInterface/AddRef/Release/AddAttachedSurface/AddOverlayDirtyRect). This is strictly safer:
 * a plain __stdcall C function with the documented signature, no code generation, no stolen
 * prologue, no rel32 relocation. And it is MORE precise - it times the actual DirectDraw call,
 * which is exactly where a GPU synchronization wait would live.
 *
 * The surface pointer is reached the same way the engine reaches it: a raster's sub-object holds
 * IDirectDrawSurface* at sub+0x04 (FUN_10018a82 calls `(*(int**)param_1[1] + 100)` = surface
 * vt+0x64 = Lock) [CONFIRMED @ GZGraphicD 0x10018a82]. All DD surfaces share one vtable, so a
 * single slot patch covers every blit.
 *
 * EXPECT-OR-REFUSE: the current slot target must lie inside ddraw.dll. If it does not, we are not
 * looking at the vtable we think and the patch is refused rather than forced. */
typedef HRESULT (WINAPI *RZ_BLT)(void *, RECT *, void *, RECT *, DWORD, void *);
static RZ_BLT  g_orig_blt;   /* g_blt_slot / g_ddblt_* are declared up with the BLT block above */

/* Argument aggregation (run 12). The hook already receives every Blt parameter and run 11 discarded
 * them. Run 11 excluded the destination (same surface, same VIDMEM residency, same dims), so what
 * is left on-path is the CALL ITSELF: its flags, its rectangles, its source. Bucket time by
 * `dwFlags` (colour-key / ROP / DDBLT_WAIT / async differ wildly in cost), and track destination
 * rectangle area plus the largest rect seen. Cheap: a 32-entry linear scan at ~2600 calls/s. */
/* (aggregate globals are declared up with the BLT block above) */

/* fwd: the surface dumper. Declared here because the Blt hook below is its first caller -
 * the capture rides the final present so the frame is fully composited. */
static void rz_dump_all(void *iso);

/* ⭐ RE-COMPOSITE THE RCI, LAST, AT PRESENT TIME.
 *
 * The RCI indicator (root child, class SIMUI+0xab274) is 88px tall and overhangs ~32px ABOVE the
 * 56px bottom bar. Worker RE (2026-09-05) + runtime probes established: the RCI blits its FULL 88px
 * surface to its dest +0x90 every frame via FUN_1006d2d0 (blit is unconditional), yet the overhang
 * shows the city. The reason is FRAME ORDER - the resize grows the viewport present to the full
 * client (iso+0x4d0 = {0,0,w,h}), and the SIMSPR viewport device-batch composites the city over the
 * overhang band AFTER the SIMUI HUD blit. Native never hits this because the shipped mod leaves the
 * viewport native-height. Neither a one-time nor a per-frame HUD invalidate wins the race.
 *
 * The fix that always wins: re-run the RCI's OWN blit (the exact FUN_1006d2d0:36-52 path -
 * target = parent->vt[0x158](); target->vt[0x1c](0x10) begin; target->vt[0x118](src=+0x58,
 * srcRect=+0x24, destRect=+0x90, 0); target->vt[0x20](0x10) end) from INSIDE the final-present hook,
 * just before the composite is blitted to the screen. Being the last write to the composite, the
 * overhang shows the RCI gauge, not the city. Uses the game's own blit so the magenta colour-key
 * transparency is handled exactly as the game handles it. `[CONFIRMED @ SIMUI 0x1006d2d0:36-52]` */
static int g_in_rci_repaint;
static void rz_repaint_rci(void) {
    DWORD sui = (DWORD)GetModuleHandleA("SIMUI.DLL");
    DWORD gz  = (DWORD)GetModuleHandleA("GZGraphicD.dll");
    void *rci = g_rci_cached, *par, *tgt;
    DWORD *pvt, *tvt, src58;
    if (!g_rcifix || !sui || !gz || g_in_rci_repaint) return;
    /* find + cache the RCI once; re-find if the cached pointer went stale */
    if (!rci || IsBadReadPtr(rci, 0x94) || *(DWORD *)rci != sui + 0xab274) {
        DWORD *w = (!IsBadReadPtr((void *)(gz + 0x6cdb8), 4)) ? *(DWORD **)(gz + 0x6cdb8) : NULL;
        DWORD *sk = (w && !IsBadReadPtr(w, 0x34)) ? (DWORD *)w[0x30 / 4] : NULL;
        void *rt = (sk && !IsBadReadPtr(sk, 0x3c)) ? (void *)sk[0x38 / 4] : NULL;
        int budget = 3000;
        rci = rt ? rz_find_by_vt(rt, sui + 0xab274, 0, &budget) : NULL;
        g_rci_cached = rci;
    }
    if (!rci || IsBadReadPtr(rci, 0x94)) return;
    src58 = ((DWORD *)rci)[0x58 / 4];
    if (!src58 || IsBadReadPtr((void *)src58, 4)) return;
    /* A dialog over the RCI must cover it: the re-composite runs after everything, so without this the
       RCI drew on top of a dragged window (owner hand test 2026-10-05). */
    if (rz_dialog_over((LONG *)((DWORD)rci + 0x14))) return;
    /* Only bother when it actually overhangs above the bar (dest top < the bar's top). */
    if (g_hud_top && !IsBadReadPtr(g_hud_top, 0x90)) {
        LONG barTop = ((LONG *)((DWORD)g_hud_top + 0x80))[1];
        LONG rciTop = ((LONG *)((DWORD)rci + 0x90))[1];
        if (rciTop >= barTop) return;   /* no overhang -> the normal HUD blit already covers it */
    }
    par = *(void **)((DWORD)rci + 0x3c);
    if (!par || IsBadReadPtr(par, 4)) return;
    pvt = *(DWORD **)par;
    if (IsBadReadPtr(pvt, 0x15c) || !pvt[0x158 / 4]) return;
    tgt = (void *)rz_thiscall_ret(par, (void *)pvt[0x158 / 4], NULL, 0);   /* FUN_1006d2d0:46 */
    if (!tgt || IsBadReadPtr(tgt, 0x11c)) return;
    tvt = *(DWORD **)tgt;
    if (IsBadReadPtr(tvt, 0x11c) || !tvt[0x1c / 4] || !tvt[0x118 / 4] || !tvt[0x20 / 4]) return;
    /* ⛔ Both rasters must have a live DirectDraw sub-surface at +0x44. The blit lands in GZGraphicD
     * FUN_10014894, which does `mov ecx,[dest+0x44]; mov eax,[ecx]` and pushes `[src+0x44]` with no
     * null check `[CONFIRMED @ GZGraphicD 0x100148fa]`. Right after a resize a raster can sit with
     * +0x44 = NULL between release and re-create: owner maximize crash 2026-10-05, AV READ 0 at
     * GZGraphicD+0x14904 with dest ebx=0x0054BC40 (verify/resize_panelshots/run_edgeon.log:467). */
    if (IsBadReadPtr((void *)((DWORD)tgt + 0x44), 4) || !*(DWORD *)((DWORD)tgt + 0x44)) return;
    if (IsBadReadPtr((void *)(src58 + 0x44), 4) || !*(DWORD *)(src58 + 0x44)) return;
    g_in_rci_repaint = 1;
    {   DWORD one = 0x10;
        if (rz_thiscall(tgt, (void *)tvt[0x1c / 4], &one, 1) & 0xff) {   /* begin/lock */
            DWORD a4[4];
            a4[0] = src58;                     /* the RCI's surface        */
            a4[1] = (DWORD)((DWORD)rci + 0x24);/* source rect  +0x24       */
            a4[2] = (DWORD)((DWORD)rci + 0x90);/* dest rect    +0x90       */
            a4[3] = 0;
            rz_thiscall(tgt, (void *)tvt[0x118 / 4], a4, 4);            /* the blit */
            rz_thiscall(tgt, (void *)tvt[0x20 / 4], &one, 1);          /* end/unlock */
            if (!g_rcifix_logged) {
                g_rcifix_logged = 1;
                logf("RCIFIX> re-composited the RCI at present time (dest +0x90 = [%ld %ld %ld %ld]) "
                     "so its overhang draws over the viewport",
                     ((LONG *)((DWORD)rci + 0x90))[0], ((LONG *)((DWORD)rci + 0x90))[1],
                     ((LONG *)((DWORD)rci + 0x90))[2], ((LONG *)((DWORD)rci + 0x90))[3]);
            }
        }
    }
    g_in_rci_repaint = 0;
}

/* MENU BACKGROUND (owner 2026-10-07): at the main menu the game still draws an 800x600 frame and the
 * final present stretched it to the window, buttons included - and input was never remapped, so a click
 * where a stretched button showed missed it (measured: "Nueva Ciudad" opened only at its 800x600 spot).
 * Now, for a present whose SOURCE is exactly 800x600 into a larger client:
 *   - menu_bg.bmp (beside the DLL, any size, 24-bit) is stretched to the client and drawn in the margins,
 *   - the 800x600 frame is presented 1:1 in the centre, so the buttons keep their native size,
 *   - inside that frame, every pixel still equal to the stock background (800x600 RGB565, MAIN.IXF
 *     0x22729921, decoded at runtime from the game's own data by rz_mb_stock_from_ixf) is replaced by the
 *     matching centre of the stretched picture. The stock background is blitted unchanged and the buttons
 *     use a hard magenta key, so an exact 565 match is the background and nothing else,
 *   - mouse messages are shifted by the centring offset while this is active.
 * No menu_bg.bmp (2026-10-11): the stock background itself is the picture, stretched the same way, so the
 * buttons keep native size and clicks land where they are drawn. SC3RESIZE_MENUBGSTOCK=0 keeps MENUBG off
 * without a menu_bg.bmp instead (the 2026-10-11 release behaviour: whole frame stretched, clicks off).
 * SC3RESIZE_MENUBG=0 disables it. MAIN.IXF unreadable: stock behaviour.
 * Owner calls 2026-10-14 (task menucrop): a menu_bg.bmp that is present but unusable (not a BMP, not
 * uncompressed 24-bit, truncated) falls back to the stock picture like a missing one, instead of turning MENUBG
 * off. The picture is scaled to COVER the client keeping its proportions, the overflow cropped evenly on both
 * sides (no distortion on a wide client). SC3RESIZE_MENUBGFIT=0 restores the plain stretch. */
#pragma comment(lib, "gdi32.lib")   /* MENUBG uses GDI for the stretched margins */
static int    g_menubg = 1;
static int    g_menubg_stock = 1;         /* no (or unusable) menu_bg.bmp: use the stock background */
static int    g_menubg_fit = 1;           /* 1 cover + centre crop (keeps proportions), 0 plain stretch */
static int    g_mb_state;                 /* 0 untried, 1 loaded, -1 failed */
static BYTE  *g_mb_img;                   /* menu_bg.bmp pixel data */
static BITMAPINFO g_mb_bi;
static WORD  *g_mb_orig;                  /* 800x600 stock background, RGB565 */
static LONG   g_mb_cw, g_mb_ch;           /* size the caches below were built for */
static HDC    g_mb_dc;
static HBITMAP g_mb_bmp, g_mb_oldbmp;
static DWORD *g_mb_bits;                  /* stretched picture, 32-bit top-down, g_mb_cw x g_mb_ch */
static WORD  *g_mb_center;                /* its centre 800x600 in RGB565 */
static LONG g_mb_m_orig, g_mb_m_last, g_mb_m_none;
static int  g_mb_dbg_left = 0;
static WORD *g_mb_native;                 /* the picture at 800x600 (what native frames got), RGB565 */
static WORD  *g_mb_last;                  /* what was last written at each frame pixel (init = stock) */
static volatile LONG g_mb_offx, g_mb_offy;
static volatile DWORD g_mb_tick;          /* GetTickCount of the last centred present */
static volatile LONG g_mb_dx0, g_mb_dy0;  /* dest origin of the last full present (client origin in dest space) */
static volatile LONG g_mb_active;         /* 1 from a centred present until a full-window present of any other frame */
static int    g_ms_valid;                 /* MENUSCALE: g_ms_f32 / g_ms_bg hold a whole frame and g_ms_out is composed from it */

static void rz_mb_path(char *out, int cap, const char *leaf) {
    char *sl;
    if (!GetModuleFileNameA(g_self, out, cap)) { out[0] = 0; return; }
    sl = strrchr(out, '\\'); if (sl) sl[1] = 0; else out[0] = 0;
    lstrcatA(out, leaf);
}

static BYTE *rz_mb_readfile(const char *path, DWORD *len) {
    HANDLE f = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    DWORD sz, got = 0;
    BYTE *b;
    if (f == INVALID_HANDLE_VALUE) return NULL;
    sz = GetFileSize(f, NULL);
    b = (BYTE *)malloc(sz ? sz : 1);
    if (b && !ReadFile(f, b, sz, &got, NULL)) got = 0;
    CloseHandle(f);
    if (!b || got != sz) { free(b); return NULL; }
    *len = sz;
    return b;
}

/* QFS decompress, transcribed from re/tools/qfs.py (itself from SIMSPR sc3_qfs_decompress 0x10050d09).
   Every read and write is bounds-checked; returns the bytes written, or -1 on a malformed stream. */
static LONG rz_qfs_decode(const BYTE *in, DWORD inlen, BYTE *out, DWORD cap) {
    DWORD p, o = 0, lit, off, n, k;
    if (inlen < 5) return -1;
    p = (in[0] & 1) ? 5 : 2;
    if (in[1] != 0xFB || p + 3 > inlen) return -1;
    p += 3;
    for (;;) {
        BYTE b0;
        if (p >= inlen) return -1;
        b0 = in[p];
        if (!(b0 & 0x80)) {                       /* 2-byte form */
            if (p + 2 > inlen) return -1;
            lit = b0 & 3; off = ((b0 & 0x60) << 3) + in[p + 1] + 1; n = ((b0 >> 2) & 7) + 3; p += 2;
        } else if (!(b0 & 0x40)) {                /* 3-byte form */
            if (p + 3 > inlen) return -1;
            lit = in[p + 1] >> 6; off = ((in[p + 1] & 0x3F) << 8) + in[p + 2] + 1; n = (b0 & 0x3F) + 4; p += 3;
        } else if (!(b0 & 0x20)) {                /* 4-byte form */
            if (p + 4 > inlen) return -1;
            lit = b0 & 3; off = ((b0 & 0x10) << 12) + (in[p + 1] << 8) + in[p + 2] + 1;
            n = ((b0 & 0x0C) << 6) + in[p + 3] + 5; p += 4;
        } else {                                  /* literal run, or the terminator */
            lit = (b0 & 0x1F) * 4 + 4;
            if (lit > 0x70) {
                lit = b0 & 3; p++;
                if (p + lit > inlen || o + lit > cap) return -1;
                memcpy(out + o, in + p, lit); o += lit;
                return (LONG)o;
            }
            p++;
            if (p + lit > inlen || o + lit > cap) return -1;
            memcpy(out + o, in + p, lit); o += lit; p += lit;
            continue;
        }
        if (p + lit > inlen || o + lit > cap) return -1;
        memcpy(out + o, in + p, lit); o += lit; p += lit;
        if (off > o || o + n > cap) return -1;
        for (k = 0; k < n; k++, o++) out[o] = out[o - off];   /* byte by byte: off < n repeats the tail */
    }
}

/* The stock menu background, read from the game's own data instead of a shipped copy (game art cannot ship).
   SC3U FUN_0043e05b @ 0x0043e05b loads the backdrop by {group 0x82b9b75c, instance 0x22729921} unless the
   registry value WINSC3BMP overrides it (FUN_0043e28b). The record lives in <exe dir>\Res\UI\Shared\MAIN.IXF:
   index records are { group, instance, type, offset, size } after the 0x80c381d7 magic, end = zero triple,
   0xFFFFFFFF slots skipped (re/analysis/formats/IXF_segment.md). Payload = 6 dwords
   [2][size-0x14][800][600][7][..] then a QFS stream that inflates to 800x600 RGB565, top-down.
   Measured 2026-10-11: the decode is byte-identical to the menu_orig.raw the dev build used. */
static WORD *rz_mb_stock_from_ixf(void) {
    char path[MAX_PATH], *sl;
    HANDLE h;
    DWORD rec[5], got, magic = 0, n = 0, off = 0, size = 0;
    BYTE *pay = NULL;
    WORD *px = NULL;
    LONG dec;
    if (!GetModuleFileNameA(NULL, path, sizeof(path))) return NULL;
    sl = strrchr(path, '\\'); if (sl) sl[1] = 0; else path[0] = 0;
    lstrcatA(path, "Res\\UI\\Shared\\MAIN.IXF");
    h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    if (h == INVALID_HANDLE_VALUE) { logf("MENUBG> cannot open %s", path); return NULL; }
    if (!ReadFile(h, &magic, 4, &got, NULL) || got != 4 || magic != 0x80c381d7) {
        logf("MENUBG> %s: bad magic 0x%08lX", path, magic); CloseHandle(h); return NULL;
    }
    while (n++ < 100000 && ReadFile(h, rec, 20, &got, NULL) && got == 20) {
        if (!rec[0] && !rec[1] && !rec[2]) break;
        if (rec[3] == 0xFFFFFFFF || rec[4] == 0xFFFFFFFF) continue;
        if (rec[0] == 0x82b9b75c && rec[1] == 0x22729921 && rec[2] == 0x62b9da24) { off = rec[3]; size = rec[4]; break; }
    }
    if (!size || size < 0x20 || size > 0x200000) { logf("MENUBG> %s: record 0x22729921 not found (size %lu)", path, size); CloseHandle(h); return NULL; }
    pay = (BYTE *)malloc(size);
    if (!pay || SetFilePointer(h, (LONG)off, NULL, FILE_BEGIN) != off || !ReadFile(h, pay, size, &got, NULL) || got != size) {
        logf("MENUBG> %s: cannot read record at 0x%08lX", path, off); free(pay); CloseHandle(h); return NULL;
    }
    CloseHandle(h);
    if (((DWORD *)pay)[2] != NAT_W || ((DWORD *)pay)[3] != NAT_H || ((DWORD *)pay)[4] != 7) {
        logf("MENUBG> record header [%lu %lu %lu %lu %lu] is not 800x600 format 7", ((DWORD *)pay)[0],
             ((DWORD *)pay)[1], ((DWORD *)pay)[2], ((DWORD *)pay)[3], ((DWORD *)pay)[4]);
        free(pay); return NULL;
    }
    px = (WORD *)malloc(NAT_W * NAT_H * 2);
    dec = px ? rz_qfs_decode(pay + 0x18, size - 0x18, (BYTE *)px, NAT_W * NAT_H * 2) : -1;
    free(pay);
    if (dec != NAT_W * NAT_H * 2) { logf("MENUBG> QFS decode gave %ld bytes, want %d", dec, NAT_W * NAT_H * 2); free(px); return NULL; }
    logf("MENUBG> stock background decoded from %s (record at 0x%08lX, %lu bytes)", path, off, size);
    return px;
}

/* The stock background as the picture: 565 to 24-bit, top-down (header comment above). */
static int rz_mb_use_stock(void) {
    BYTE *rgb = (BYTE *)malloc(NAT_W * NAT_H * 3);
    LONG i;
    if (!rgb) return 0;
    for (i = 0; i < NAT_W * NAT_H; i++) {
        WORD q = g_mb_orig[i];
        BYTE r = (BYTE)(q >> 11), g = (BYTE)((q >> 5) & 0x3F), b = (BYTE)(q & 0x1F);
        rgb[i * 3 + 0] = (BYTE)((b << 3) | (b >> 2));
        rgb[i * 3 + 1] = (BYTE)((g << 2) | (g >> 4));
        rgb[i * 3 + 2] = (BYTE)((r << 3) | (r >> 2));
    }
    g_mb_img = rgb;
    memset(&g_mb_bi, 0, sizeof(g_mb_bi));
    g_mb_bi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    g_mb_bi.bmiHeader.biWidth = NAT_W; g_mb_bi.bmiHeader.biHeight = -NAT_H;   /* top-down */
    g_mb_bi.bmiHeader.biPlanes = 1; g_mb_bi.bmiHeader.biBitCount = 24; g_mb_bi.bmiHeader.biCompression = BI_RGB;
    g_mb_state = 1;
    return 1;
}

static int rz_mb_load(void) {
    char path[MAX_PATH];
    BYTE *f;
    DWORD len = 0;
    const char *why = NULL;
    if (g_mb_state) return g_mb_state > 0;
    g_mb_state = -1;
    g_mb_orig = rz_mb_stock_from_ixf();
    if (!g_mb_orig) { logf("MENUBG> no stock background - off"); return 0; }
    g_mb_last = (WORD *)malloc(NAT_W * NAT_H * 2);
    if (!g_mb_last) return 0;
    memcpy(g_mb_last, g_mb_orig, NAT_W * NAT_H * 2);
    rz_mb_path(path, sizeof(path), "menu_bg.bmp");
    f = rz_mb_readfile(path, &len);
    if (!f) why = "missing";
    else if (len < 54 || f[0] != 'B' || f[1] != 'M') why = "not a BMP";
    else {
        BITMAPINFOHEADER *bh = (BITMAPINFOHEADER *)(f + 14);
        DWORD off = *(DWORD *)(f + 10);
        LONG w = bh->biWidth, h = bh->biHeight < 0 ? -bh->biHeight : bh->biHeight;
        DWORD stride = ((DWORD)w * 3 + 3) & ~3u;
        if (bh->biBitCount != 24 || bh->biCompression != BI_RGB || w <= 0 || h <= 0 || w > 0x4000 || h > 0x4000
            || off > len || stride * h > len - off)
            why = "not an uncompressed 24-bit BMP";
        else {
            g_mb_img = f + off;
            memset(&g_mb_bi, 0, sizeof(g_mb_bi));
            g_mb_bi.bmiHeader = *bh;
            logf("MENUBG> loaded menu_bg.bmp %ldx%ld and the stock background", w, h);
            g_mb_state = 1;
            return 1;
        }
    }
    free(f);
    if (!g_menubg_stock) { logf("MENUBG> %s %s - off (SC3RESIZE_MENUBGSTOCK=0)", path, why); return 0; }
    /* No usable picture of the player's own: the stock background itself, so the buttons still stay at native
       size, centred, and clickable where they are drawn. */
    if (!rz_mb_use_stock()) return 0;
    logf("MENUBG> %s %s - using the stock background", path, why);
    return 1;
}

/* Stretch the picture to cw x ch once per size, keep its centre 800x600 as RGB565. */
static int rz_mb_prepare(LONG cw, LONG ch) {
    BITMAPINFO bi;
    HDC sdc;
    LONG x, y, ox = (cw - NAT_W) / 2, oy = (ch - NAT_H) / 2;
    if (g_mb_cw == cw && g_mb_ch == ch && g_mb_bits) return 1;
    if (g_mb_dc) { SelectObject(g_mb_dc, g_mb_oldbmp); DeleteObject(g_mb_bmp); DeleteDC(g_mb_dc); g_mb_dc = NULL; }
    free(g_mb_center); g_mb_center = NULL; g_mb_bits = NULL;
    memset(&bi, 0, sizeof(bi));
    bi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    bi.bmiHeader.biWidth = cw; bi.bmiHeader.biHeight = -ch;
    bi.bmiHeader.biPlanes = 1; bi.bmiHeader.biBitCount = 32; bi.bmiHeader.biCompression = BI_RGB;
    sdc = GetDC(NULL);
    g_mb_dc = CreateCompatibleDC(sdc);
    g_mb_bmp = CreateDIBSection(sdc, &bi, DIB_RGB_COLORS, (void **)&g_mb_bits, NULL, 0);
    ReleaseDC(NULL, sdc);
    if (!g_mb_dc || !g_mb_bmp || !g_mb_bits) { logf("MENUBG> DIB %ldx%ld failed", cw, ch); g_mb_bits = NULL; return 0; }
    g_mb_oldbmp = (HBITMAP)SelectObject(g_mb_dc, g_mb_bmp);
    SetStretchBltMode(g_mb_dc, HALFTONE);
    SetBrushOrgEx(g_mb_dc, 0, 0, NULL);
    {   LONG iw = g_mb_bi.bmiHeader.biWidth;
        LONG ih = g_mb_bi.bmiHeader.biHeight < 0 ? -g_mb_bi.bmiHeader.biHeight : g_mb_bi.bmiHeader.biHeight;
        LONG sx0 = 0, sy0 = 0, sw = iw, sh = ih;
        /* Cover: the source rect with the client's proportions, as large as fits, centred. The overflow is split
           evenly, so a bottom-up BMP (whose source y counts from the bottom) crops the same way, within 1 px. */
        if (g_menubg_fit) {
            if ((__int64)iw * ch > (__int64)ih * cw) { sw = (LONG)((__int64)ih * cw / ch); sx0 = (iw - sw) / 2; }
            else                                     { sh = (LONG)((__int64)iw * ch / cw); sy0 = (ih - sh) / 2; }
            if (sw < 1) sw = 1;
            if (sh < 1) sh = 1;
        }
        StretchDIBits(g_mb_dc, 0, 0, cw, ch, sx0, sy0, sw, sh, g_mb_img, &g_mb_bi, DIB_RGB_COLORS, SRCCOPY);
        logf("MENUBG> %s source [%ld %ld %ld %ld] of %ldx%ld", g_menubg_fit ? "cover" : "stretch",
             sx0, sy0, sx0 + sw, sy0 + sh, iw, ih);
    }
    GdiFlush();
    g_mb_center = (WORD *)malloc(NAT_W * NAT_H * 2);
    if (!g_mb_center) return 0;
    for (y = 0; y < NAT_H; y++)
        for (x = 0; x < NAT_W; x++) {
            LONG sx = ox + x, sy = oy + y;
            DWORD q = (sx >= 0 && sy >= 0 && sx < cw && sy < ch) ? g_mb_bits[sy * cw + sx] : 0;
            g_mb_center[y * NAT_W + x] = (WORD)(((q >> 8) & 0xF800) | ((q >> 5) & 0x07E0) | ((q >> 3) & 0x001F));
        }
    g_mb_cw = cw; g_mb_ch = ch;
    g_mb_dbg_left = 3;
    /* The menu keeps a copy of its composed frame and redraws from it after a size change; a copy taken at
       native size holds the native-size picture, so that version must count as background too (measured: after
       maximizing, 462,335 frame pixels matched neither stock nor our last write). */
    if (cw == NAT_W && ch == NAT_H && !g_mb_native && (g_mb_native = (WORD *)malloc(NAT_W * NAT_H * 2)) != NULL)
        memcpy(g_mb_native, g_mb_center, NAT_W * NAT_H * 2);
    logf("MENUBG> picture stretched to %ldx%ld, menu frame centred at (%ld,%ld)", cw, ch, ox, oy);
    return 1;
}

/* Replace stock-background pixels in the 800x600 source frame. IDirectDrawSurface Lock = vt+0x64,
   Unlock = vt+0x80; lPitch at desc+0x10 and lpSurface at desc+0x24 in both DDSURFACEDESC sizes. */
typedef HRESULT (WINAPI *RZ_LOCK)(void *, RECT *, void *, DWORD, HANDLE);
typedef HRESULT (WINAPI *RZ_UNLOCK)(void *, void *);
static void rz_mb_patch_src(void *src, const RECT *sr, LONG fx0, LONG fy0, LONG fw, LONG fh) {
    DWORD *vt = *(DWORD **)src;
    BYTE desc[124];
    HRESULT hr;
    LONG x, y, pitch;
    BYTE *bits;
    static int logged;
    memset(desc, 0, sizeof(desc)); *(DWORD *)desc = 124;
    hr = ((RZ_LOCK)vt[0x64 / 4])(src, NULL, desc, 1 /* DDLOCK_WAIT */, NULL);
    if (hr) { memset(desc, 0, sizeof(desc)); *(DWORD *)desc = 108; hr = ((RZ_LOCK)vt[0x64 / 4])(src, NULL, desc, 1, NULL); }
    if (hr) { if (!logged++) logf("MENUBG> Lock failed 0x%08lX", (DWORD)hr); return; }
    pitch = *(LONG *)(desc + 0x10);
    bits = *(BYTE **)(desc + 0x24);
    /* sr = the region of the source surface; (fx0, fy0) = where it sits in the 800x600 frame */
    if (bits && pitch >= (sr->left + fw) * 2) {
        for (y = 0; y < fh; y++) {
            WORD *row = (WORD *)(bits + (sr->top + y) * pitch) + sr->left;
            const WORD *o = g_mb_orig + (fy0 + y) * NAT_W + fx0, *n = g_mb_center + (fy0 + y) * NAT_W + fx0;
            WORD *l = g_mb_last + (fy0 + y) * NAT_W + fx0;
            /* background = still the stock pixel, OR still what we wrote last time. The game does not redraw the
               static menu background every frame, so after a size change the frame holds our previous picture
               (owner: the native-size picture stayed inside the maximized frame - two images). */
            for (x = 0; x < fw; x++) {
                if (row[x] == o[x]) { g_mb_m_orig++; row[x] = n[x]; l[x] = n[x]; }
                else if (row[x] == l[x]) { g_mb_m_last++; row[x] = n[x]; l[x] = n[x]; }
                else if (g_mb_native && row[x] == g_mb_native[(fy0 + y) * NAT_W + fx0 + x]) { g_mb_m_last++; row[x] = n[x]; l[x] = n[x]; }
                else g_mb_m_none++;
            }
        }
        g_ms_valid = 0;   /* MENUSCALE: g_mb_last may have changed, so a cached class may be stale */
        if (g_mb_dbg_left > 0) {
            g_mb_dbg_left--;
            logf("MENUBG> swap %ldx%ld at (%ld,%ld) surf 0x%08lX: stock %ld, last %ld, other %ld (cache %ldx%ld)",
                 fw, fh, fx0, fy0, (DWORD)src, g_mb_m_orig, g_mb_m_last, g_mb_m_none, g_mb_cw, g_mb_ch);
        }
        g_mb_m_orig = g_mb_m_last = g_mb_m_none = 0;
    } else if (!logged++) logf("MENUBG> unexpected surface: bits 0x%08lX pitch %ld", (DWORD)bits, pitch);
    ((RZ_UNLOCK)vt[0x80 / 4])(src, NULL);
}

static void rz_mb_margins(LONG cw, LONG ch, LONG ox, LONG oy) {
    HDC dc = GetDC(g_hwnd);
    if (!dc) return;
    if (oy > 0) BitBlt(dc, 0, 0, cw, oy, g_mb_dc, 0, 0, SRCCOPY);
    if (ch - oy - NAT_H > 0) BitBlt(dc, 0, oy + NAT_H, cw, ch - oy - NAT_H, g_mb_dc, 0, oy + NAT_H, SRCCOPY);
    if (ox > 0) BitBlt(dc, 0, oy, ox, NAT_H, g_mb_dc, 0, oy, SRCCOPY);
    if (cw - ox - NAT_W > 0) BitBlt(dc, ox + NAT_W, oy, cw - ox - NAT_W, NAT_H, g_mb_dc, ox + NAT_W, oy, SRCCOPY);
    ReleaseDC(g_hwnd, dc);
}

/* Is the main menu up? Its button container is a root child of class SC3U.exe+0xd2c20 (measured at
   [80 60 720 540], 15 children). Early city frames are 800x600 too and must not get the menu treatment
   (owner: New City briefly showed the city frame centred inside the menu picture). */
static int rz_menu_visible(void) {
    /* "Menu" = no city view yet: the full-client HUD container (root child, class SC3U.exe+0xd32d0) holds the
       city view (class SIMSPR+0x676ac) once a city exists, and is empty at the main menu and its dialogs.
       (First try keyed on the menu button container SC3U.exe+0xd2c20, which disappears while the New City
       dialog is open - the dialog then went out stretched and clicks missed.) */
    DWORD exe = (DWORD)GetModuleHandleA(NULL), spr = (DWORD)GetModuleHandleA("SIMSPR.DLL");
    void *root = rz_ui_root(), *head, *n;
    int g = 0;
    if (!root || IsBadReadPtr((BYTE *)root + 0x34, 4)) return 0;
    head = *(void **)((DWORD)root + 0x34);
    if (!head || IsBadReadPtr(head, 4)) return 0;
    for (n = *(void **)head; n && n != head && g++ < 200; n = *(void **)n) {
        DWORD *c;
        if (IsBadReadPtr(n, 0x0c)) break;
        c = *(DWORD **)((DWORD)n + 8);
        if (c && !IsBadReadPtr(c, 0x38) && c[0] == exe + 0xd32d0) {
            void *h2 = *(void **)((DWORD)c + 0x34), *m;
            int g2 = 0;
            if (!h2 || IsBadReadPtr(h2, 4)) return 1;
            for (m = *(void **)h2; m && m != h2 && g2++ < 100; m = *(void **)m) {
                DWORD *k;
                if (IsBadReadPtr(m, 0x0c)) break;
                k = *(DWORD **)((DWORD)m + 8);
                if (k && !IsBadReadPtr(k, 4) && spr && k[0] == spr + 0x676ac) return 0;   /* a city view */
            }
            return 1;
        }
    }
    return 0;
}

/* MENUSCALE (task menuscale 2026-10-14, owner: "the main menu has to scale on the viewable 4:3 area, despite textures
 * not scaling"). On a client larger than 800x600 the menu frame is no longer presented 1:1: it is scaled to the largest
 * 4:3 rectangle that fits the client, centred (old art simply upscaled, accepted by the owner). Per present:
 *   - the 800x600 source frame is READ (never written, unlike the 1:1 path) and every pixel classified as background
 *     with the same test as rz_mb_patch_src: equal to the stock background, to what the 1:1 / native path last wrote,
 *     or to the picture at 800x600 (g_mb_native);
 *   - the rect is composed into a 32-bit DIB: each dest pixel resamples the frame (bilinear, or nearest with
 *     SC3RESIZE_MENUSCALE_FILTER=0), and a tap on a background pixel takes the picture AT THE DEST PIXEL instead, so
 *     the picture shows at client resolution behind the buttons and their edges blend into it;
 *   - only the dest region fed by frame pixels that changed since the last present is recomposed;
 *   - the rect and the margins (the cover picture, as before) go to the window through GDI. The ddraw present of the
 *     frame is not called, so the window holds exactly what was composed;
 *   - mouse messages from the queue map client -> frame through the same rect: frame = floor((2(c - r0) + 1) * 800 /
 *     (2 rw)), the source pixel the nearest filter draws at that client pixel.
 * Exactly 800x600: unchanged (the native path above). SC3RESIZE_MENUSCALE=0: the 1:1 centred frame.
 * SC3RESIZE_MENUSCALE_DUMP=<abs prefix>: when <prefix>req exists, the next scaled present writes <prefix>NNN_client.bmp
 * (what was sent to the window) and <prefix>NNN_frame.bmp (the source frame as read), then deletes the request. */
static int    g_menuscale = 1;
static int    g_ms_filter = 1;            /* 1 bilinear, 0 nearest */
static int    g_ms_repost = 1;            /* SC3RESIZE_MENUSCALE_REPOST=0: map a queued move at our last output too */
static volatile LONG g_ms_on;             /* the last full menu present was scaled: the wndproc maps through g_ms_r* */
static volatile LONG g_ms_rx, g_ms_ry, g_ms_rw, g_ms_rh;   /* the 4:3 rect, client coords */
static DWORD *g_ms_lut;                   /* RGB565 -> XRGB */
static DWORD *g_ms_f32;                   /* the frame as last read, 800x600 XRGB */
static BYTE  *g_ms_bg;                    /* 1 = that frame pixel is background */
static int    g_ms_ismenu = -1;           /* the frame shows the menu background (>= 1/10 of it); else (the intro logo,
                                              owner 2026-10-23) the margins are black, not the menu picture */
static WORD  *g_ms_raw;                   /* the frame as last read, RGB565: an unchanged row is skipped */
static HDC    g_ms_dc;
static HBITMAP g_ms_bmp, g_ms_oldbmp;
static DWORD *g_ms_out;                   /* the composed rect, rw x rh, 32-bit top-down */
static LONG   g_ms_cw, g_ms_ch, g_ms_tfilter = -1;
static LONG  *g_ms_xs, *g_ms_xf, *g_ms_ys, *g_ms_yf;   /* per rect column / row: source index, weight 0..256 */
static char   g_ms_dump[MAX_PATH];
static int    g_ms_dumpn;
static __int64 g_ms_t[3], g_ms_tmax;       /* read, compose, blit; worst present */
static DWORD  g_ms_n, g_ms_np, g_ms_beat, g_ms_area;
static int    g_ms_depth, g_ms_nestlog, g_ms_mlog, g_ms_replog;
static LPARAM g_ms_last_out;
static DWORD  g_ms_last_t;
static int    g_ms_last_ok;
static int    g_ms_fullblit;             /* SC3RESIZE_MENUSCALE_FULLBLIT=1: whole client on every present */
static volatile LONG g_ms_full_req;      /* the wndproc saw a paint / size / activation message */
static DWORD  g_ms_full_t, g_ms_nfull;
static int    g_ms_refresh;              /* SC3RESIZE_MENUSCALE_REFRESH=<ms>: periodic whole-client blit, 0 = off */

static void rz_ms_rect(LONG cw, LONG ch, LONG *rx, LONG *ry, LONG *rw, LONG *rh) {
    if ((__int64)cw * NAT_H >= (__int64)ch * NAT_W) { *rh = ch; *rw = (LONG)((__int64)ch * NAT_W / NAT_H); }
    else                                            { *rw = cw; *rh = (LONG)((__int64)cw * NAT_H / NAT_W); }
    *rx = (cw - *rw) / 2; *ry = (ch - *rh) / 2;
}

/* client coordinate -> frame coordinate (floor division, so the margins map below 0 / past the frame) */
static LONG rz_ms_map(LONG c, LONG r0, LONG rl, LONG nat) {
    __int64 num = (__int64)(2 * (c - r0) + 1) * nat, den = 2 * (__int64)rl;
    return (LONG)(num >= 0 ? num / den : -((-num + den - 1) / den));
}

/* Per-column / per-row source taps for a rect side of rl dest pixels over nat source pixels. */
static void rz_ms_axis(LONG *s, LONG *f, LONG rl, LONG nat, int filter) {
    LONG i;
    for (i = 0; i < rl; i++) {
        if (filter) {   /* pixel centres: u = (i + 0.5) * nat / rl - 0.5, 8 fraction bits */
            __int64 u = (__int64)(2 * i + 1) * nat * 256 / (2 * (__int64)rl) - 128;
            if (u < 0) u = 0;
            s[i] = (LONG)(u >> 8); f[i] = (LONG)(u & 255);
            if (s[i] >= nat - 1) { s[i] = nat - 1; f[i] = 0; }
        } else { s[i] = (LONG)((__int64)(2 * i + 1) * nat / (2 * (__int64)rl)); f[i] = 0; }
    }
}

static int rz_ms_prepare(LONG cw, LONG ch) {
    BITMAPINFO bi;
    HDC sdc;
    LONG rx, ry, rw, rh, i;
    if (g_ms_cw == cw && g_ms_ch == ch && g_ms_out && g_ms_tfilter == g_ms_filter) return 1;
    if (!g_ms_lut) {
        g_ms_lut = (DWORD *)malloc(65536 * 4);
        if (!g_ms_lut) return 0;
        for (i = 0; i < 65536; i++) {
            DWORD r = (i >> 11) & 31, g = (i >> 5) & 63, b = i & 31;
            g_ms_lut[i] = (((r << 3) | (r >> 2)) << 16) | (((g << 2) | (g >> 4)) << 8) | ((b << 3) | (b >> 2));
        }
    }
    if (!g_ms_f32) g_ms_f32 = (DWORD *)malloc(NAT_W * NAT_H * 4);
    if (!g_ms_bg) g_ms_bg = (BYTE *)malloc(NAT_W * NAT_H);
    if (!g_ms_raw) g_ms_raw = (WORD *)malloc(NAT_W * NAT_H * 2);
    if (!g_ms_f32 || !g_ms_bg || !g_ms_raw) return 0;
    if (g_ms_dc) { SelectObject(g_ms_dc, g_ms_oldbmp); DeleteObject(g_ms_bmp); DeleteDC(g_ms_dc); g_ms_dc = NULL; }
    g_ms_out = NULL;
    free(g_ms_xs); free(g_ms_xf); free(g_ms_ys); free(g_ms_yf);
    rz_ms_rect(cw, ch, &rx, &ry, &rw, &rh);
    g_ms_xs = (LONG *)malloc(rw * 4); g_ms_xf = (LONG *)malloc(rw * 4);
    g_ms_ys = (LONG *)malloc(rh * 4); g_ms_yf = (LONG *)malloc(rh * 4);
    if (!g_ms_xs || !g_ms_xf || !g_ms_ys || !g_ms_yf) return 0;
    rz_ms_axis(g_ms_xs, g_ms_xf, rw, NAT_W, g_ms_filter);
    rz_ms_axis(g_ms_ys, g_ms_yf, rh, NAT_H, g_ms_filter);
    memset(&bi, 0, sizeof(bi));
    bi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    bi.bmiHeader.biWidth = rw; bi.bmiHeader.biHeight = -rh;
    bi.bmiHeader.biPlanes = 1; bi.bmiHeader.biBitCount = 32; bi.bmiHeader.biCompression = BI_RGB;
    sdc = GetDC(NULL);
    g_ms_dc = CreateCompatibleDC(sdc);
    g_ms_bmp = CreateDIBSection(sdc, &bi, DIB_RGB_COLORS, (void **)&g_ms_out, NULL, 0);
    ReleaseDC(NULL, sdc);
    if (!g_ms_dc || !g_ms_bmp || !g_ms_out) { logf("MENUSCALE> DIB %ldx%ld failed", rw, rh); g_ms_out = NULL; return 0; }
    g_ms_oldbmp = (HBITMAP)SelectObject(g_ms_dc, g_ms_bmp);
    g_ms_cw = cw; g_ms_ch = ch; g_ms_tfilter = g_ms_filter; g_ms_valid = 0; g_ms_full_req = 1;
    g_ms_rx = rx; g_ms_ry = ry; g_ms_rw = rw; g_ms_rh = rh;
    logf("MENUSCALE> client %ldx%ld: menu frame scaled to [%ld %ld %ld %ld] = %ldx%ld (x%.4f, %s)", cw, ch, rx, ry,
         rx + rw, ry + rh, rw, rh, (double)rh / NAT_H, g_ms_filter ? "bilinear" : "nearest");
    return 1;
}

/* Read the frame region [fx0,fx0+fw) x [fy0,fy0+fh) from the source (its sr->left/top = the region's surface origin),
   classify, and widen *bb (x0 y0 x1 y1, frame coords) by every pixel whose value or class changed. Never writes. */
static int rz_ms_read(void *src, const RECT *sr, LONG fx0, LONG fy0, LONG fw, LONG fh, LONG *bb) {
    DWORD *vt = *(DWORD **)src;
    BYTE desc[124];
    HRESULT hr;
    LONG x, y, pitch;
    BYTE *bits;
    static int logged;
    memset(desc, 0, sizeof(desc)); *(DWORD *)desc = 124;
    hr = ((RZ_LOCK)vt[0x64 / 4])(src, NULL, desc, 1 /* DDLOCK_WAIT */, NULL);
    if (hr) { memset(desc, 0, sizeof(desc)); *(DWORD *)desc = 108; hr = ((RZ_LOCK)vt[0x64 / 4])(src, NULL, desc, 1, NULL); }
    if (hr) { if (!logged++) logf("MENUSCALE> Lock failed 0x%08lX", (DWORD)hr); return 0; }
    pitch = *(LONG *)(desc + 0x10);
    bits = *(BYTE **)(desc + 0x24);
    if (!bits || pitch < (sr->left + fw) * 2) {
        if (!logged++) logf("MENUSCALE> unexpected surface: bits 0x%08lX pitch %ld", (DWORD)bits, pitch);
        ((RZ_UNLOCK)vt[0x80 / 4])(src, NULL);
        return 0;
    }
    for (y = 0; y < fh; y++) {
        const WORD *row = (const WORD *)(bits + (sr->top + y) * pitch) + sr->left;
        LONG i0 = (fy0 + y) * NAT_W + fx0;
        const WORD *o = g_mb_orig + i0, *l = g_mb_last + i0, *nv = g_mb_native ? g_mb_native + i0 : NULL;
        DWORD *f = g_ms_f32 + i0;
        BYTE *b = g_ms_bg + i0;
        LONG cx0 = -1, cx1 = -1;
        if (g_ms_valid && !memcmp(g_ms_raw + i0, row, fw * 2)) continue;   /* same pixels, same classes */
        memcpy(g_ms_raw + i0, row, fw * 2);
        for (x = 0; x < fw; x++) {
            WORD p = row[x];
            BYTE isbg;
            DWORD q = g_ms_lut[p];
            if (p == o[x]) { isbg = 1; g_mb_m_orig++; }
            else if (p == l[x] || (nv && p == nv[x])) { isbg = 1; g_mb_m_last++; }
            else { isbg = 0; g_mb_m_none++; }
            if (q != f[x] || isbg != b[x]) { f[x] = q; b[x] = isbg; if (cx0 < 0) cx0 = x; cx1 = x; }
        }
        if (cx0 >= 0) {
            if (bb[0] > fx0 + cx0) bb[0] = fx0 + cx0;
            if (bb[2] < fx0 + cx1 + 1) bb[2] = fx0 + cx1 + 1;
            if (bb[1] > fy0 + y) bb[1] = fy0 + y;
            if (bb[3] < fy0 + y + 1) bb[3] = fy0 + y + 1;
        }
    }
    ((RZ_UNLOCK)vt[0x80 / 4])(src, NULL);
    if (g_mb_dbg_left > 0) {
        g_mb_dbg_left--;
        logf("MENUSCALE> read %ldx%ld at (%ld,%ld) surf 0x%08lX: stock %ld, last %ld, other %ld", fw, fh, fx0, fy0,
             (DWORD)src, g_mb_m_orig, g_mb_m_last, g_mb_m_none);
    }
    g_mb_m_orig = g_mb_m_last = g_mb_m_none = 0;
    return 1;
}

static __inline DWORD rz_ms_lerp(DWORD a, DWORD b, LONG f) {   /* f 0..256 toward b */
    DWORD w = 256 - (DWORD)f;
    return ((((a & 0xFF00FF) * w + (b & 0xFF00FF) * (DWORD)f) >> 8) & 0xFF00FF) |
           ((((a & 0x00FF00) * w + (b & 0x00FF00) * (DWORD)f) >> 8) & 0x00FF00);
}

/* Compose rect pixels [dx0,dx1) x [dy0,dy1) (rect coords) from the frame cache and the cover picture. */
static void rz_ms_compose(LONG dx0, LONG dy0, LONG dx1, LONG dy1) {
    LONG x, y, rw = g_ms_rw, cw = g_ms_cw, rx = g_ms_rx, ry = g_ms_ry;
    for (y = dy0; y < dy1; y++) {
        LONG sy0 = g_ms_ys[y], fy = g_ms_yf[y], sy1 = sy0 < NAT_H - 1 ? sy0 + 1 : sy0;
        const DWORD *f0 = g_ms_f32 + sy0 * NAT_W, *f1 = g_ms_f32 + sy1 * NAT_W;
        const BYTE *b0 = g_ms_bg + sy0 * NAT_W, *b1 = g_ms_bg + sy1 * NAT_W;
        const DWORD *p = g_mb_bits + (ry + y) * cw + rx;
        DWORD *o = g_ms_out + y * rw;
        if (!g_ms_filter) {
            for (x = dx0; x < dx1; x++) { LONG sx = g_ms_xs[x]; o[x] = b0[sx] ? p[x] : f0[sx]; }
            continue;
        }
        for (x = dx0; x < dx1; x++) {
            LONG sx0 = g_ms_xs[x], fx = g_ms_xf[x], sx1 = sx0 < NAT_W - 1 ? sx0 + 1 : sx0;
            BYTE ba = b0[sx0], bb = b0[sx1], bc = b1[sx0], bd = b1[sx1];
            DWORD pa, pb, pc, pd;
            if (ba & bb & bc & bd) { o[x] = p[x]; continue; }
            pa = ba ? p[x] : f0[sx0]; pb = bb ? p[x] : f0[sx1];
            pc = bc ? p[x] : f1[sx0]; pd = bd ? p[x] : f1[sx1];
            o[x] = rz_ms_lerp(rz_ms_lerp(pa, pb, fx), rz_ms_lerp(pc, pd, fx), fy);
        }
    }
}

/* Frame box (x0 y0 x1 y1) -> the rect pixels whose taps can read it (rect coords), clamped. */
static void rz_ms_dest_box(const LONG *bb, LONG *d) {
    d[0] = (LONG)((__int64)(bb[0] - 1) * g_ms_rw / NAT_W) - 1;
    d[1] = (LONG)((__int64)(bb[1] - 1) * g_ms_rh / NAT_H) - 1;
    d[2] = (LONG)((__int64)(bb[2] + 1) * g_ms_rw / NAT_W) + 2;
    d[3] = (LONG)((__int64)(bb[3] + 1) * g_ms_rh / NAT_H) + 2;
    if (d[0] < 0) d[0] = 0;
    if (d[1] < 0) d[1] = 0;
    if (d[2] > g_ms_rw) d[2] = g_ms_rw;
    if (d[3] > g_ms_rh) d[3] = g_ms_rh;
}

static void rz_ms_write_bmp(const char *path, const DWORD *px, LONG w, LONG h) {
    BITMAPFILEHEADER fh;
    BITMAPINFOHEADER ih;
    DWORD wr;
    HANDLE f = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
    if (f == INVALID_HANDLE_VALUE) { logf("MENUSCALE> cannot write %s", path); return; }
    memset(&fh, 0, sizeof(fh)); memset(&ih, 0, sizeof(ih));
    fh.bfType = 0x4D42; fh.bfOffBits = sizeof(fh) + sizeof(ih); fh.bfSize = fh.bfOffBits + (DWORD)w * h * 4;
    ih.biSize = sizeof(ih); ih.biWidth = w; ih.biHeight = -h; ih.biPlanes = 1; ih.biBitCount = 32; ih.biCompression = BI_RGB;
    WriteFile(f, &fh, sizeof(fh), &wr, NULL);
    WriteFile(f, &ih, sizeof(ih), &wr, NULL);
    WriteFile(f, px, (DWORD)w * h * 4, &wr, NULL);
    CloseHandle(f);
}

/* SC3RESIZE_MENUSCALE_DUMP: the whole client as sent to the window (margins from the picture, rect from the
   composed DIB), the source frame as read, the cover picture and the background mask (for offline checks). */
static void rz_ms_dump_if_asked(void) {
    char req[MAX_PATH], p[MAX_PATH];
    DWORD *cl;
    LONG y, cw = g_ms_cw, ch = g_ms_ch;
    if (!g_ms_dump[0]) return;
    wsprintfA(req, "%sreq", g_ms_dump);
    if (GetFileAttributesA(req) == INVALID_FILE_ATTRIBUTES) return;
    DeleteFileA(req);
    cl = (DWORD *)malloc((size_t)cw * ch * 4);
    if (!cl) return;
    memcpy(cl, g_mb_bits, (size_t)cw * ch * 4);
    for (y = 0; y < g_ms_rh; y++)
        memcpy(cl + (g_ms_ry + y) * cw + g_ms_rx, g_ms_out + y * g_ms_rw, g_ms_rw * 4);
    g_ms_dumpn++;
    wsprintfA(p, "%s%03d_client.bmp", g_ms_dump, g_ms_dumpn); rz_ms_write_bmp(p, cl, cw, ch);
    wsprintfA(p, "%s%03d_frame.bmp", g_ms_dump, g_ms_dumpn); rz_ms_write_bmp(p, g_ms_f32, NAT_W, NAT_H);
    wsprintfA(p, "%s%03d_picture.bmp", g_ms_dump, g_ms_dumpn); rz_ms_write_bmp(p, g_mb_bits, cw, ch);
    for (y = 0; y < NAT_W * NAT_H; y++) cl[y] = g_ms_bg[y] ? 0xFFFFFF : 0;   /* background mask, white = background */
    wsprintfA(p, "%s%03d_mask.bmp", g_ms_dump, g_ms_dumpn); rz_ms_write_bmp(p, cl, NAT_W, NAT_H);
    free(cl);
    logf("MENUSCALE> dump %03d: client %ldx%ld, rect [%ld %ld %ld %ld]", g_ms_dumpn, cw, ch, g_ms_rx, g_ms_ry,
         g_ms_rx + g_ms_rw, g_ms_ry + g_ms_rh);
}

static void rz_ms_account(int part, LARGE_INTEGER *t) {   /* t[0..3] = start, read, compose, blit */
    __int64 tot = t[3].QuadPart - t[0].QuadPart;
    DWORD now = GetTickCount();
    g_ms_t[0] += t[1].QuadPart - t[0].QuadPart;
    g_ms_t[1] += t[2].QuadPart - t[1].QuadPart;
    g_ms_t[2] += t[3].QuadPart - t[2].QuadPart;
    if (tot > g_ms_tmax) g_ms_tmax = tot;
    if (part) g_ms_np++; else g_ms_n++;
    if (!g_ms_beat) g_ms_beat = now;
    if (now - g_ms_beat >= 2000 && g_freq.QuadPart) {
        double k = 1000.0 / (double)g_freq.QuadPart, n = (double)(g_ms_n + g_ms_np);
        logf("MENUSCALE> %lu full + %lu partial presents in %lu ms: avg read %.3f compose %.3f blit %.3f ms, worst %.3f ms,"
             " %lu rect px recomposed, %lu whole-client blits", g_ms_n, g_ms_np, now - g_ms_beat, k * g_ms_t[0] / n,
             k * g_ms_t[1] / n, k * g_ms_t[2] / n, k * (double)g_ms_tmax, g_ms_area, g_ms_nfull);
        g_ms_n = g_ms_np = g_ms_area = g_ms_nfull = 0; g_ms_t[0] = g_ms_t[1] = g_ms_t[2] = g_ms_tmax = 0; g_ms_beat = now;
    }
}

/* The full menu present, scaled. cw x ch = the dest size (rz_mb_prepare already built the cover picture for it). */
static int rz_ms_full(void *src, const RECT *sr, LONG cw, LONG ch) {
    LONG bb[4] = { NAT_W, NAT_H, 0, 0 }, d[4];
    LARGE_INTEGER t[4];
    HDC dc;
    QueryPerformanceCounter(&t[0]);
    if (!rz_ms_prepare(cw, ch)) return 0;
    if (!rz_ms_read(src, sr, 0, 0, NAT_W, NAT_H, bb)) return 0;
    if (!g_ms_valid) { bb[0] = 0; bb[1] = 0; bb[2] = NAT_W; bb[3] = NAT_H; }
    QueryPerformanceCounter(&t[1]);
    if (bb[2] > bb[0]) {   /* pixels changed: is it still (or now) the menu? */
        LONG i, nbg = 0;
        int m;
        for (i = 0; i < NAT_W * NAT_H; i++) nbg += g_ms_bg[i];
        m = nbg >= NAT_W * NAT_H / 10;
        if (m != g_ms_ismenu) {
            logf("MENUSCALE> frame %s (%ld background px): margins %s", m ? "is the menu" : "is not the menu", nbg,
                 m ? "show the menu picture" : "black");
            g_ms_ismenu = m; g_ms_full_req = 1;
        }
    }
    if (bb[2] > bb[0]) {
        rz_ms_dest_box(bb, d);
        if (!g_ms_valid) { d[0] = 0; d[1] = 0; d[2] = g_ms_rw; d[3] = g_ms_rh; }
        rz_ms_compose(d[0], d[1], d[2], d[3]);
        g_ms_area += (DWORD)((d[2] - d[0]) * (d[3] - d[1]));
    }
    g_ms_valid = 1;
    GdiFlush();
    QueryPerformanceCounter(&t[2]);
    /* The window keeps what was drawn (measured: a desktop grab equals the dump except the live FPS text), so a
       static present sends only the recomposed box. The whole client goes out on a new size, on the first scaled
       present, and after a paint / size / activation message (g_ms_full_req). SC3RESIZE_MENUSCALE_REFRESH=<ms> also
       sends it every <ms> (off by default: at 3840x1984 that blit is the 14-17 ms worst present, measured with 1000).
       SC3RESIZE_MENUSCALE_FULLBLIT=1 sends the whole client on every present (measured at 3840x1984: 11-16 ms). */
    if (g_ms_fullblit || g_ms_full_req || !g_ms_on || (g_ms_refresh > 0 && GetTickCount() - g_ms_full_t >= (DWORD)g_ms_refresh)) {
        dc = GetDC(g_hwnd);
        if (dc) {
            LONG rx = g_ms_rx, ry = g_ms_ry, rw = g_ms_rw, rh = g_ms_rh;
            DWORD rop = g_ms_ismenu ? SRCCOPY : BLACKNESS;
            BitBlt(dc, rx, ry, rw, rh, g_ms_dc, 0, 0, SRCCOPY);
            if (ry > 0) BitBlt(dc, 0, 0, cw, ry, g_mb_dc, 0, 0, rop);
            if (ch - ry - rh > 0) BitBlt(dc, 0, ry + rh, cw, ch - ry - rh, g_mb_dc, 0, ry + rh, rop);
            if (rx > 0) BitBlt(dc, 0, ry, rx, rh, g_mb_dc, 0, ry, rop);
            if (cw - rx - rw > 0) BitBlt(dc, rx + rw, ry, cw - rx - rw, rh, g_mb_dc, rx + rw, ry, rop);
            ReleaseDC(g_hwnd, dc);
            g_ms_full_req = 0; g_ms_full_t = GetTickCount(); g_ms_nfull++;
        }
    } else if (bb[2] > bb[0] && (dc = GetDC(g_hwnd)) != NULL) {
        BitBlt(dc, g_ms_rx + d[0], g_ms_ry + d[1], d[2] - d[0], d[3] - d[1], g_ms_dc, d[0], d[1], SRCCOPY);
        ReleaseDC(g_hwnd, dc);
    }
    QueryPerformanceCounter(&t[3]);
    rz_ms_account(0, t);
    rz_ms_dump_if_asked();
    return 1;
}

/* A partial present of the menu frame: frame sub-rect sr (surface origin = frame origin, as in the 1:1 path). */
static int rz_ms_partial(void *src, const RECT *sr) {
    LONG bb[4] = { NAT_W, NAT_H, 0, 0 }, d[4];
    LARGE_INTEGER t[4];
    HDC dc;
    if (!g_ms_valid || !g_ms_out) return 0;
    QueryPerformanceCounter(&t[0]);
    if (!rz_ms_read(src, sr, sr->left, sr->top, sr->right - sr->left, sr->bottom - sr->top, bb)) return 0;
    QueryPerformanceCounter(&t[1]);
    if (bb[2] > bb[0]) {
        rz_ms_dest_box(bb, d);
        rz_ms_compose(d[0], d[1], d[2], d[3]);
        g_ms_area += (DWORD)((d[2] - d[0]) * (d[3] - d[1]));
        GdiFlush();
        QueryPerformanceCounter(&t[2]);
        dc = GetDC(g_hwnd);
        if (dc) {
            BitBlt(dc, g_ms_rx + d[0], g_ms_ry + d[1], d[2] - d[0], d[3] - d[1], g_ms_dc, d[0], d[1], SRCCOPY);
            ReleaseDC(g_hwnd, dc);
        }
    } else t[2] = t[1];
    QueryPerformanceCounter(&t[3]);
    rz_ms_account(1, t);
    return 1;
}

/* Returns 1 and sets *hr when it presented the frame itself. */
static int rz_mb_present(void *self, RECT *dr, void *src, RECT *sr, DWORD fl, void *fx, HRESULT *hr) {
    RECT cr, c;
    LONG dw, dh, ox, oy;
    static int logged, logged_part;
    if (!g_menubg || !g_hwnd || !dr || !sr || !src || IsBadReadPtr(dr, sizeof(RECT)) || IsBadReadPtr(sr, sizeof(RECT))) return 0;
    if (g_mb_active && g_mb_bits && (sr->right - sr->left != NAT_W || sr->bottom - sr->top != NAT_H)) {
        /* A PARTIAL present of the menu frame (only the changed part): the game stretched the sub-rect by
           client/800. Recognise that mapping, present it 1:1 at its centred spot instead. The source
           surface's frame origin is the full present's source origin, assumed (0,0) as measured. */
        LONG sw = sr->right - sr->left, sh = sr->bottom - sr->top;
        LONG ex = g_mb_dx0 + sr->left * g_mb_cw / NAT_W, ey = g_mb_dy0 + sr->top * g_mb_ch / NAT_H;
        if (sw > 0 && sh > 0 && sr->left >= 0 && sr->top >= 0 && sr->right <= NAT_W && sr->bottom <= NAT_H &&
            labs(dr->left - ex) <= 2 && labs(dr->top - ey) <= 2) {
            if (g_ms_on) {   /* MENUSCALE: recompose the part of the rect it feeds; dropped if nothing is cached yet */
                static int logged_ms;
                int ok = rz_ms_partial(src, sr);
                if (logged_ms < 3) { logged_ms++; logf("MENUSCALE> partial present [%ld %ld %ld %ld] %s", sr->left, sr->top,
                                                       sr->right, sr->bottom, ok ? "recomposed" : "dropped (no frame cached)"); }
                *hr = 0;
                return 1;
            }
            rz_mb_patch_src(src, sr, sr->left, sr->top, sw, sh);
            c.left = g_mb_dx0 + g_mb_offx + sr->left; c.top = g_mb_dy0 + g_mb_offy + sr->top;
            c.right = c.left + sw; c.bottom = c.top + sh;
            *hr = g_orig_blt(self, &c, src, sr, fl, fx);
            if (!logged_part++) logf("MENUBG> partial present [%ld %ld %ld %ld] -> [%ld %ld %ld %ld]",
                                      sr->left, sr->top, sr->right, sr->bottom, c.left, c.top, c.right, c.bottom);
            return 1;
        }
        return 0;
    }
    if (sr->right - sr->left != NAT_W || sr->bottom - sr->top != NAT_H) return 0;
    dw = dr->right - dr->left; dh = dr->bottom - dr->top;
    if (dw < NAT_W || dh < NAT_H) return 0;
    /* only the FINAL present (dest covers the client); intermediate 800x600 blits are not ours */
    if (!GetClientRect(g_hwnd, &cr) || dw < cr.right - cr.left || dh < cr.bottom - cr.top) return 0;
    if (!rz_menu_visible()) {
        if (g_ms_on) logf("MENUSCALE> 800x600 present with a city view up: not the menu, mapping off");
        g_mb_active = 0; g_ms_on = 0; return 0;
    }
    if (cr.right - cr.left == NAT_W && cr.bottom - cr.top == NAT_H) {
        /* native window: no margins, but the same picture (owner: the 800x600 menu still showed the old one) */
        if (rz_mb_load() && rz_mb_prepare(NAT_W, NAT_H)) rz_mb_patch_src(src, sr, 0, 0, NAT_W, NAT_H);
        g_mb_active = 0;
        return 0;   /* the caller presents it normally */
    }
    if (!GetClientRect(g_hwnd, &cr) || dw < cr.right - cr.left || dh < cr.bottom - cr.top) return 0;
    if (!rz_mb_load() || !rz_mb_prepare(dw, dh)) return 0;
    if (g_menuscale && rz_ms_full(src, sr, dw, dh)) {
        static int logged_ms;
        g_ms_on = 1; g_mb_active = 1; g_mb_tick = GetTickCount();
        g_mb_offx = g_ms_rx; g_mb_offy = g_ms_ry; g_mb_dx0 = dr->left; g_mb_dy0 = dr->top;
        if (!logged_ms++) logf("MENUSCALE> first scaled present: dest [%ld %ld %ld %ld] -> frame at [%ld %ld %ld %ld]",
                               dr->left, dr->top, dr->right, dr->bottom, g_ms_rx, g_ms_ry, g_ms_rx + g_ms_rw, g_ms_ry + g_ms_rh);
        *hr = 0;
        return 1;
    }
    g_ms_on = 0;
    ox = (dw - NAT_W) / 2; oy = (dh - NAT_H) / 2;
    rz_mb_patch_src(src, sr, 0, 0, NAT_W, NAT_H);
    c.left = dr->left + ox; c.top = dr->top + oy; c.right = c.left + NAT_W; c.bottom = c.top + NAT_H;
    *hr = g_orig_blt(self, &c, src, sr, fl, fx);
    rz_mb_margins(dw, dh, ox, oy);
    g_mb_offx = ox; g_mb_offy = oy; g_mb_tick = GetTickCount(); g_mb_active = 1;
    g_mb_dx0 = dr->left; g_mb_dy0 = dr->top;
    if (!logged++) logf("MENUBG> first centred present: dest [%ld %ld %ld %ld] -> frame at [%ld %ld %ld %ld]",
                        dr->left, dr->top, dr->right, dr->bottom, c.left, c.top, c.right, c.bottom);
    return 1;
}

/* HUDSCALE (prototype, task hudscale 2026-10-11, re/analysis/HUD_SCALE.md option A). OFF unless
 * SC3RESIZE_HUDSCALE is set: 1 = factor min(cw/800, ch/600), n >= 100 = n/100 capped at that.
 * SC3RESIZE_HUDSCALE_FILTER=1 resamples bilinear instead of nearest.
 *
 * The layout stays exactly as the cluster code builds it (full-width bar, full-height panel, minimap and RCI
 * docked bottom-right). At the final present every visible HUD window that touches the right or bottom client
 * edge is drawn again enlarged about the bottom-right corner C: dest = C + s * (rect - C). Each such window,
 * and so their union, is closed under "move towards C", so the enlarged union covers every native copy. All
 * windows share the one map, so each dest pixel reads source pixel C + (d - C) / s and overlap order does not
 * matter. The frame is snapshotted first and restored right after the present: the game reuses it.
 * The city-only target iso+0x74 is the see-through mask (SC3RESIZE_HUDSCALE_KEY=0 disables): a HUD-rect pixel
 * equal to the city layer is the city showing through, so the dest gets the city under it instead (without it,
 * the minimap's transparent corner showed a magnified piece of city). Small floating windows (tooltips) are
 * enlarged too, and their native copy is overwritten with the city layer, but only when the game's cursor was on the
 * enlarged HUD as the window appeared (COSTLABEL, owner 2026-10-22: "the price marking is offset a lot"). The game
 * puts a floating window next to the cursor it was told about: after a mapped (HUD) message that is the native point,
 * after an unmapped (city) one it is the real cursor. The road/highway cost label (vt exe+0xd3bcc) dragged in the
 * lower right of the city lay inside the native HUD box, so it was enlarged too and drawn at C + s * (p - C), at
 * 3.307x 374 px left of and 1066 px above the drag end. The decision is latched per window and rect, so a HUD tooltip
 * keeps its place when the cursor leaves the HUD before it hides. The class cannot tell them apart: every HUD tooltip
 * measured (side panel, bottom bar, minimap buttons) is the same exe+0xd3bcc window, moved. So a second test: the
 * floating rect must also touch a native HUD window (8 px margin, last frame's rects). Every HUD tooltip measured
 * overlaps one, and it stops a stray message from enlarging a city label: with the real mouse parked on the HUD of
 * a maximized window, Windows sends a move at its position when a press captures the mouse, so the flag read "HUD"
 * for the label of a drag that started in the open city (measured 2026-10-22 at 3840x1984).
 * SC3RESIZE_HUDSCALE_FLOATALL=1 = the old rule.
 * Mouse messages on an enlarged rect (or during a press that started on one) get the inverse map.
 * Measured 2026-10-11 at 1200x900 and 1600x960: re/analysis/HUD_SCALE.md, verify/hudscale/. */
static int    g_hudscale;               /* 0 off, 1 auto, >= 100 percent */
static int    g_hs_filter;              /* 0 nearest, 1 bilinear */
#define HS_MAX 32
static LONG   g_hs_src[HS_MAX][4], g_hs_dst[HS_MAX][4];
static int    g_hs_float[HS_MAX];          /* 1 = not edge-anchored (a tooltip): its native copy is erased */
static volatile LONG g_hs_n;            /* dest rects in use (0 = inactive): read by the wndproc */
static volatile LONG g_hs_cw, g_hs_ch;
static double g_hs_s = 1.0;
static LONG   g_hs_dlg[16][4];          /* dialogs kept native this frame (DLGSCALE off, or no room to enlarge) */
static int    g_hs_ndlg;
/* DLGSCALE (owner 2026-10-20: "the Reunirse popup is not scaled, neither any other menu"; design call the same day:
 * scale dialogs with the HUD factor, capped to fit). Supersedes the 2026-10-14 "dialogs stay native" call. Each visible
 * dialog (SIMUI+0xa4d64 root child >= 120x80) is enlarged about its own centre by min(HUD factor, cw / w, ch / h),
 * then shifted inside the client. The enlarged image is cached per dialog window and only the dest box fed by the
 * source pixels that changed since the last frame is recomputed, so a still dialog costs one copy per frame and a drag
 * costs nothing (the cache is keyed by size, not position). Mouse messages inside an enlarged dialog map back to its
 * native rect at any depth (the query dialog's modal loop runs at depth 1). SC3RESIZE_DLGSCALE=0 keeps them native. */
#define HD_MAX 8
typedef struct {
    void *win; DWORD used;
    LONG nat[4], dst[4], w, h, dw, dh;
    LONG kw, kh, kdw, kdh, kf;          /* geometry the cache below was built for */
    WORD *cur, *prev, *out;             /* native w*h this frame / last frame, enlarged dw*dh */
    LONG capn, capo, capt;
    LONG *xs, *ys;                      /* per dest column/row: source index << 9 | weight of the next one (0..256) */
    int valid;
    int lbl;                            /* task uiscale: the city cost label, placed at the cursor, takes no mouse */
} HD_SLOT;
static int     g_dlgscale = 1;
static HD_SLOT g_hd[HD_MAX];
static int     g_hd_list[HD_MAX], g_hd_nc;      /* this pass: slots collected */
static volatile LONG g_hd_n;                    /* published with g_hs_n: dialogs drawn enlarged, read by the wndproc */
static LONG    g_hd_pdst[HD_MAX][4], g_hd_pnat[HD_MAX][4];
static int     g_hd_pslot[HD_MAX];
static int     g_hd_capture = -1;               /* slot pressed on, until the release */
static int     g_hd_cap_drag;                   /* that dialog moved since the press: map the cursor 1:1 from it */
static LONG    g_hd_cap_q[2], g_hd_cap_p[2], g_hd_cap_nat[2];
static DWORD   g_hd_stamp, g_hd_px, g_hd_full, g_hd_frames;
static int     rz_hd_add(void *win, const LONG *r, LONG cw, LONG ch, double s);   /* fwd */
/* task uiscale (owner 2026-10-22, img17: "price tag is hiding under the cursor and it's not scaling with the rest of the
 * screen"). The city cost label (the game's tooltip window, vt exe+0xd3bcc, placed by SIMSPR 0x1004a3d7 from the view's
 * mouse point) stayed native since COSTLABEL: a few px tall at 3.3x, under a pointer drawn 64 to 80 px. Now, when the
 * COSTLABEL rule keeps a floating window of that class native (cursor in the city), it is drawn enlarged by the HUD
 * factor through a DLGSCALE slot instead, placed from the cursor point the TIPCURSOR stubs record (g_tip_mx/my): centred
 * under the pointer box, its top g_tip_clr + gap below the hotspot, or above the hotspot when that runs past the bottom,
 * shifted inside the client. Its native copy is erased with the city layer (the DLGSCALE rule). It takes no mouse
 * mapping (rz_hd_mouse skips it). HUD tooltips are untouched (the COSTLABEL "enlarged" branch). Without a TIPCURSOR
 * record the cursor is derived from the stock layout (box 0x2c, label 2 px below). SC3RESIZE_COSTLABEL_SCALE=0: native. */
static int     g_costscale = 1;
static int     g_hd_plbl[HD_MAX];
static volatile LONG g_tip_mx, g_tip_my, g_tip_flip, g_tip_seen;   /* written by tip_stub1/2: the anchor of the last label */
static LONG    g_tip_clr = 32;                  /* drawn pointer size in game px, for the clearance (tip_update) */
static int     g_hl_logs;
static int     rz_hl_add(void *win, const LONG *r, LONG cw, LONG ch, double s);   /* fwd */
static int    g_hs_capture, g_hs_depth, g_hs_nestlog;
static int    g_hs_mouse_hud;           /* COSTLABEL: the last queued mouse message was mapped (cursor on the enlarged HUD) */
static int    g_hs_floatall;            /* SC3RESIZE_HUDSCALE_FLOATALL=1: enlarge every floating window in the box (old rule) */
#define HS_FL_MAX 8
static struct { void *win; LONG r[4]; int hud; DWORD stamp; } g_hs_fl[HS_FL_MAX];   /* COSTLABEL latch */
static DWORD  g_hs_fl_stamp;
static LONG   g_hs_hudr[HS_MAX][4];     /* COSTLABEL: native rects of the edge-anchored HUD windows, last pass */
static LONG   g_hs_hudd[HS_MAX][4];     /* task uiscale: their enlarged rects, last pass (the cost label keeps off them) */
static int    g_hs_nhudr;
static int    g_hs_fl_logs;
static int    g_hs_repost = 1, g_hs_repost_log, g_hs_last_ok;   /* SC3RESIZE_HUDSCALE_REPOST=0 disables the guard */
static LPARAM g_hs_last_out;
static DWORD  g_hs_last_t;
static int    g_hs_mlog, g_hs_mlog_n;     /* SC3RESIZE_HUDSCALE_MLOG=1: log every mouse message the HUDSCALE path sees (diag) */
static WORD  *g_hs_snap;
static LONG   g_hs_snapcap;
static LONG  *g_hs_xs, *g_hs_ys, *g_hs_xf, *g_hs_yf;   /* per column/row: source index, bilinear base + weight */
static LONG   g_hs_tcw, g_hs_tch;
static double g_hs_ts;
static DWORD  g_hs_sig;
static int    g_hs_logs;
static void  *g_hs_primary, *g_hs_lastsrc;
static int    g_hs_key = 1;             /* SC3RESIZE_HUDSCALE_KEY=0: no city mask (transparent HUD edges carry city) */
static __int64 g_hs_time; static DWORD g_hs_frames, g_hs_beat;
static int    g_hs_diag;                /* SC3RESIZE_HUDSCALE_DIAG=1: per-second present census (task hudfix) */
/* HUDFIX (task hudfix 2026-10-11, re/analysis/HUD_SCALE.md "Defects after the hand test"). SC3RESIZE_HUDFIX=0 = the
 * hudopt behaviour (equality mask, taps read the snapshot, a pass on every client-sized Blt).
 * - The enlarge pass runs only on the Blt whose dest is the primary surface. The game also Blts its city layer into
 *   the composite with a client-sized dest every frame; that is not a present.
 * - See-through is decided from what the game actually drew into the composite this frame: every Blt onto the
 *   composite after the frame's city Blt is recorded (dest, source, flags, colour key). A HUD-rect pixel covered by
 *   an opaque Blt, or by a keyed Blt whose source pixel is not the key, is HUD whatever its colour. The equality test
 *   (pixel == city layer) is only the fallback for pixels no recorded Blt covers. Before, any opaque HUD pixel that
 *   happened to equal the city pixel under it showed the city instead, which flickers while the camera moves.
 * - Every resampling tap that is not HUD (see-through, or outside every HUD rect) takes the city at the DEST pixel,
 *   so enlarged edges are composited over the city they sit on. Before, edge taps read the city next to the native
 *   rect, a different spot of the map, which moved during a scroll.
 * - The minimap picture is plain pixel data (no anti-aliasing), so bilinear alone keeps its stair steps. In smooth
 *   mode its source is first doubled with Scale2x (EPX), softened with one [1 2 1] tent in 2x space (HUD pixels only),
 *   and the bilinear tap reads that (filters compared offline: verify/hudfix/minimap_filters_x2.png).
 *   SC3RESIZE_HUDSCALE_MINISMOOTH=0 turns that step off. */
static int    g_hudfix = 1;
static int    g_hs_minismooth = 1;
static DWORD  g_hs_vt[HS_MAX];
typedef struct { LONG d[4], s[4]; void *src; DWORD fl, klo, khi; int kind; } HS_REC;   /* kind 0 opaque, 1 keyed, 2 key unknown */
#define HS_REC_MAX 256
static HS_REC g_hs_rec[HS_REC_MAX];
static LONG   g_hs_nrec, g_hs_recover;
static void  *g_hs_comp;
static BYTE  *g_hs_cov;
static LONG   g_hs_covcap;
static WORD  *g_hs_x2;
static LONG   g_hs_x2cap;
static LONG  *g_hs_c2b, *g_hs_c2f, g_hs_c2cap;
static DWORD  g_hsd_recs, g_hsd_fallback;
static __int64 g_hst[6];   /* HUDFIX stage times: snapshot, coverage, resolve, epx, resample, total */
static void rz_hs_tick(int k, LARGE_INTEGER *t) { LARGE_INTEGER u; QueryPerformanceCounter(&u); g_hst[k] += u.QuadPart - t->QuadPart; *t = u; }
static char   g_hs_dump[MAX_PATH];      /* SC3RESIZE_HUDSCALE_DUMP=<abs prefix>: raw dumps of one frame (diag) */
static int    g_hs_why;                 /* last rz_hs_pre exit: 0 enlarged, else the refusing check */
static DWORD  g_hsd_beat, g_hsd_full, g_hsd_did, g_hsd_why[12], g_hsd_part, g_hsd_partc, g_hsd_null, g_hsd_logn;

/* CITYZOOM (task cityzoom, owner 2026-10-22: "as we scale up, can you also scale the zoom levels? because on 4K
 * screens the game looks too zoomed out on the highest zoom level"). Zooming in at the stock closest zoom (4) adds
 * steps x2 and x3: the iso view is resized to ceil(client / f) by the Init-free resize routine (rz_poll ->
 * rz_do_resize, the path a window resize takes), the game's one city layer -> composite Blt is replaced by a stretch
 * of that view to the client (cz_stretch: nearest, or a linear blend when [hud] smooth is on), and city mouse messages
 * get q / f. Zoom 0..4 are untouched. Steps: integer f up to floor(min(cw / 800, ch / 600)), at most 3 (x2 and x3 at
 * 3840x1984, x2 at 2560x1351 and 1600x1200, none at 1920x1080). Owner calls 2026-10-22: x2 and x3, Auto default,
 * filter follows the HUD smooth setting. sc3resize.ini [view] zoomextra = 0 off | 1 auto (missing = 1) | 2 at most x2;
 * SC3RESIZE_CITYZOOM overrides. Plan and measurements: re/analysis/CITY_ZOOM.md. */
static int  g_cz_mode = 1;
static volatile LONG g_cz_req = 1;     /* factor the zoom keys asked for (game thread writes, the poll applies it) */
static volatile LONG g_cz_f = 1;       /* factor the view is drawn at now (read by the Blt hook and the wndproc) */
static LONG g_cz_vw, g_cz_vh;          /* view size at that factor */
static int  g_cz_draganchor = 1;       /* SC3RESIZE_CITYZOOM_DRAGANCHOR=0: leave a right-drag's anchor alone at a step */
static LONG g_cz_rpx = -100000, g_cz_rpy, g_cz_rpf = 1;   /* the last right press as the game got it, and the factor then */
static void *g_cz_surf;                /* the render target iso+0x74 as an IDirectDrawSurface: src of the city Blt */
static void *g_cz_devsurf;             /* the device surface iso+0x4ec: the frame (city + HUD), kept client-sized */
static LONG g_cz_dev_w, g_cz_dev_h;    /* size rz_do_resize gives iso+0x4ec (0 = the view size, stock) */
static int  g_cz_inblt;                /* inside the rewritten city Blt: rz_blt_hook_inner stretches instead */
static WORD *g_cz_buf;                 /* client-sized stretched city, filled only where HUDSCALE reads it */
static LONG g_cz_bufcap;
static LONG *g_cz_xs, g_cz_xcap, g_cz_xf, g_cz_xw;   /* per dest column: view column | weight << 16, for f / width */
static DWORD g_cz_nstretch; static __int64 g_cz_tstretch; /* 10-s stats */
/* SKIP (owner 2026-10-22, "skip pixels the HUD covers"): dest pixels the last HUD pass composed from HUD taps only
   (HUDPERF cached runs, t == 1) never read the city, so the stretch and the HUD-city copy leave them out. Native HUD
   rects are never skipped (the equality fallback reads the city there). Rebuilt after every HUD pass, used only by the
   next frame's stretch, dropped when a pass does not run. SC3RESIZE_CITYZOOM_SKIP=0 stretches everything. */
static int   g_cz_skipon = 1, g_cz_skok;
static LONG *g_cz_sk, g_cz_skcap;          /* spans x0, x1 pairs, per row from g_cz_sko[y] to g_cz_sko[y + 1] */
static LONG *g_cz_sko, g_cz_skocap;
static LONG  g_cz_skw, g_cz_skh, g_cz_skf;
static DWORD g_czd_skippx;
/* MOVENEAREST (owner 2026-10-22, "nearest filter while the camera moves, smooth once it stops"): while the view origin
   changed within the last 120 ms the stretch is nearest, else it follows [hud] smooth. The HUD keeps its own filter.
   SC3RESIZE_CITYZOOM_MOVENEAREST=0 keeps smooth while moving. */
static int   g_cz_movenear = 1, g_cz_filt;
static DWORD g_cz_movet;
static LONG  g_cz_lox = 0x7fffffff, g_cz_loy;
/* the output spans of dest row y inside [x0, x1): the row minus its SKIP spans. Returns the count (pairs in sg). */
#define CZ_MAXSEG 12
static int cz_segs(LONG y, LONG x0, LONG x1, LONG *sg) {
    LONG a = x0, k, e;
    int n = 0;
    if (!g_cz_skok || y < 0 || y >= g_cz_skh) { sg[0] = x0; sg[1] = x1; return 1; }
    for (k = g_cz_sko[y], e = g_cz_sko[y + 1]; k < e && n < CZ_MAXSEG - 1; k += 2) {
        LONG s0 = g_cz_sk[k] > x0 ? g_cz_sk[k] : x0, s1 = g_cz_sk[k + 1] < x1 ? g_cz_sk[k + 1] : x1;
        if (s1 <= s0) continue;
        if (s0 > a) { sg[2 * n] = a; sg[2 * n + 1] = s0; n++; }
        if (s1 > a) a = s1;
    }
    if (a < x1) { sg[2 * n] = a; sg[2 * n + 1] = x1; n++; }
    return n;
}
static DWORD g_cz_nother, g_cz_npart, g_cz_nfull[2];      /* view Blts: not onto the frame, partial (left alone), full by height */
static DWORD g_cz_nrw, g_cz_nnest;                         /* rewritten city Blts; stretches entered inside another */
static int   g_cz_instretch;
/* SC3RESIZE_CITYZOOM_DIAG=1: one line per second with the frame split (task cityzoom, owner 2026-10-22: "some minor FPS
   drop when moving around"): presents, camera moved or still, interval avg / max, and ms per frame in the stretch, the
   HUD-city fill, the whole HUD pass, the present Blt. */
static int    g_cz_diag;
static __int64 g_czd_fill, g_czd_hs, g_czd_pres, g_czd_str;
static DWORD  g_czd_n, g_czd_t0, g_czd_last, g_czd_maxiv, g_czd_moved, g_czd_fillpx;
static LONG   g_czd_ox, g_czd_oy;
static RECT  g_cz_lastpart;

static void rz_lcenter_area(LONG cw, LONG ch, LONG w0, LONG h0, LONG *w, LONG *h);   /* fwd: LCENTER block */
static int g_zoomcenter_on(void);   /* fwd: ZOOMCENTER block (the zoom steps ride on its wrappers) */

static LONG cz_max(LONG cw, LONG ch) {   /* largest step this client allows */
    LONG k = cw / NAT_W < ch / NAT_H ? cw / NAT_W : ch / NAT_H;
    if (!g_cz_mode) return 1;
    if (k > 3) k = 3;
    if (g_cz_mode == 2 && k > 2) k = 2;
    return k < 1 ? 1 : k;
}

/* The view image: the render target iso+0x74 (+0x24 w, +0x28 h, +0x44 sub, sub+0xf0 bits, sub+0xf4 pitch). Measured
   2026-10-22: per frame the game Blts iso+0x74 [0 0 vw vh] into the device surface iso+0x4ec, draws the HUD into
   iso+0x4ec, and presents iso+0x4ec to the screen. So iso+0x4ec is the frame (HUDSCALE's composite): it keeps the
   client size (g_cz_dev_w/h in rz_do_resize step 6) and the city Blt into it is the one that stretches. */
static BYTE *cz_view_bits(LONG *pitch, LONG *w, LONG *h, DWORD *sub_locked) {
    DWORD iso, obj, sub, bits, pt, *svt;
    HMODULE gz = GetModuleHandleA("GZGraphicD.dll");
    *sub_locked = 0;
    if (!g_bridge || IsBadReadPtr(g_bridge, 0x1c) || !gz) return NULL;
    iso = ((DWORD *)g_bridge)[0x18 / 4];
    if (!iso || IsBadReadPtr((void *)iso, 0x78)) return NULL;
    obj = ((DWORD *)iso)[0x74 / 4];
    if (!obj || IsBadReadPtr((void *)obj, 0x48)) return NULL;
    sub = ((DWORD *)obj)[0x44 / 4];
    if (!sub || IsBadReadPtr((void *)sub, 0xf8)) return NULL;
    bits = ((DWORD *)sub)[0xf0 / 4]; pt = ((DWORD *)sub)[0xf4 / 4];
    if (!bits || !pt) {
        svt = *(DWORD **)sub;
        if (!svt || IsBadReadPtr(svt, 0x14) || (DWORD)svt != (DWORD)gz + GZ_RVA_VT_SURFACE || !svt[0x0c / 4]) return NULL;
        if (!(rz_thiscall((void *)sub, (void *)svt[0x0c / 4], NULL, 0) & 0xff)) return NULL;
        *sub_locked = sub;
        bits = ((DWORD *)sub)[0xf0 / 4]; pt = ((DWORD *)sub)[0xf4 / 4];
    }
    *w = (LONG)((DWORD *)obj)[0x24 / 4]; *h = (LONG)((DWORD *)obj)[0x28 / 4];
    if (*h > g_cz_vh && g_cz_vh > 0) *h = g_cz_vh;   /* the slack rows are not part of the picture */
    *pitch = (LONG)pt;
    if (!bits && *sub_locked) {
        svt = *(DWORD **)sub; rz_thiscall((void *)sub, (void *)svt[0x10 / 4], NULL, 0); *sub_locked = 0;
    }
    return (BYTE *)bits;
}
static void cz_view_unlock(DWORD sub) {
    DWORD *svt;
    if (!sub) return;
    svt = *(DWORD **)sub;
    if (svt && !IsBadReadPtr(svt, 0x14) && svt[0x10 / 4]) rz_thiscall((void *)sub, (void *)svt[0x10 / 4], NULL, 0);
}

/* Dest rect [x0,x1) x [y0,y1) of a client-sized 16-bpp image from the view image at factor f. Dest pixel (x, y) shows
 * view pixel (x / f, y / f); smooth blends toward the next view pixel by (x % f) / f in each axis, on the same grid,
 * so both filters show the city at the same place (and the mouse map q / f matches either). 565 or 555 by gmask.
 * Rects of 100,000 px and more are split in row bands over worker threads (measured at 3840x1984 smooth: ~10 ms on one
 * thread, 3.5 to 4.6 on four). */
typedef struct { DWORD *h0, *h1; LONG cap; } CZ_ROWS;
static void cz_tables(LONG f, LONG sw, LONG x1) {   /* per dest column: view column | weight << 16 */
    LONG x;
    if (g_cz_xcap >= x1 && g_cz_xf == f && g_cz_xw == sw) return;
    if (x1 > g_cz_xcap) { free(g_cz_xs); g_cz_xs = (LONG *)malloc((x1 + 64) * sizeof(LONG)); g_cz_xcap = g_cz_xs ? x1 + 64 : 0; }
    if (!g_cz_xs) return;
    for (x = 0; x < g_cz_xcap; x++) {
        LONG i = x / f;
        if (i > sw - 1) i = sw - 1;
        g_cz_xs[x] = i | (((x % f) * 32 / f) << 16);
    }
    g_cz_xf = f; g_cz_xw = sw;
}
static void cz_stretch_rows(CZ_ROWS *rw, BYTE *dst, LONG dpitch, const BYTE *src, LONG spitch, LONG sw, LONG sh, LONG f,
                            int smooth, DWORD gmask, LONG x0, LONG y0, LONG x1, LONG y1) {
    const DWORD lane = gmask == 0x07E0 ? 0x07E0F81Fu : 0x03E07C1Fu;
    LONG x, y, n = x1 - x0, ra = -1, rb = -1;
    int prevwhole = 0;
    DWORD *h0, *h1;
    if (smooth && rw->cap < n) {
        free(rw->h0); free(rw->h1);
        rw->h0 = (DWORD *)malloc(n * 4); rw->h1 = (DWORD *)malloc(n * 4);
        rw->cap = rw->h0 && rw->h1 ? n : 0;
        if (!rw->cap) smooth = 0;
    }
    h0 = rw->h0; h1 = rw->h1;
    for (y = y0; y < y1; y++) {
        LONG sy = y / f, sg[2 * CZ_MAXSEG], q;
        int ns = cz_segs(y, x0, x1, sg), whole = ns == 1 && sg[0] == x0 && sg[1] == x1;
        WORD *d = (WORD *)(dst + y * dpitch) + x0;
        if (sy > sh - 1) sy = sh - 1;
        if (!whole) {   /* SKIP: count what is left out */
            LONG kept = 0;
            for (q = 0; q < ns; q++) kept += sg[2 * q + 1] - sg[2 * q];
            g_czd_skippx += (DWORD)(n - kept);
        }
        if (ns < 1) { prevwhole = 0; continue; }
        if (!smooth) {
            const WORD *s;
            if (whole && prevwhole && y > y0 && (y - 1) / f == y / f) { memcpy(d, (WORD *)(dst + (y - 1) * dpitch) + x0, n * 2); continue; }
            prevwhole = whole;
            s = (const WORD *)(src + sy * spitch);
            for (q = 0; q < ns; q++) {
                LONG a = sg[2 * q], b = sg[2 * q + 1], na = b - a;
                WORD *dd = (WORD *)(dst + y * dpitch) + a;
                if (f == 2 && !(a & 1)) {
                    DWORD *d2 = (DWORD *)dd;
                    const WORD *s2 = s + a / 2;
                    LONG k, m = na / 2;
                    for (k = 0; k < m; k++) { DWORD p = s2[k]; d2[k] = p | (p << 16); }
                    if (na & 1) dd[na - 1] = s[g_cz_xs[b - 1] & 0xffff];
                } else
                    for (x = a; x < b; x++) dd[x - a] = s[g_cz_xs[x] & 0xffff];
            }
        } else if (f == 2 && !(x0 & 1) && !(n & 1)) {
            /* x2 smooth, two pixels per DWORD: dest (2i, 2i+1) = (s[i], avg(s[i], s[i+1])), odd rows average the two
               view rows. avg = ((a ^ b) & ~lowbits) >> 1 + (a & b) per channel, the same floor((a + b) / 2) the generic
               lane blend gives at weight 16 of 32, so the result is bit-identical. */
            const DWORD m2 = gmask == 0x07E0 ? 0xF7DEF7DEu : 0x7BDE7BDEu;
            LONG sb = sy + 1 < sh ? sy + 1 : sy, r, i0 = x0 / 2, m = n / 2, k;
            DWORD *d2 = (DWORD *)d;
            if (sy == rb && sy != ra) { DWORD *t = h0; h0 = h1; h1 = t; ra = rb; rb = -1; }
            for (r = 0; r < 2; r++) {
                LONG want = r ? sb : sy;
                DWORD *hrow = r ? h1 : h0;
                const WORD *sp;
                if (r ? want == rb : want == ra) continue;
                sp = (const WORD *)(src + want * spitch);
                for (k = 0; k < m; k++) {
                    LONG i = i0 + k, j = i + 1 < sw ? i + 1 : i;
                    DWORD a = sp[i < sw ? i : sw - 1], b = sp[j < sw ? j : sw - 1];
                    DWORD av = (((a ^ b) & (m2 & 0xffff)) >> 1) + (a & b);
                    hrow[k] = a | (av << 16);
                }
                if (r) rb = want; else ra = want;
            }
            for (q = 0; q < ns; q++) {   /* output spans, in whole pixel pairs (a span edge may get one extra px) */
                LONG ka = (sg[2 * q] - x0) / 2, kb = (sg[2 * q + 1] - x0 + 1) / 2;
                if (kb > m) kb = m;
                if (!(y & 1)) memcpy(d2 + ka, h0 + ka, (kb - ka) * 4);
                else for (k = ka; k < kb; k++) { DWORD a = h0[k], b = h1[k]; d2[k] = (((a ^ b) & m2) >> 1) + (a & b); }
            }
        } else {
            LONG wy = (y % f) * 32 / f, sb = sy + 1 < sh ? sy + 1 : sy, r;
            if (sy == rb && sy != ra) { DWORD *t = h0; h0 = h1; h1 = t; ra = rb; rb = -1; }   /* one view row down */
            for (r = 0; r < 2; r++) {   /* horizontal pass for view rows sy (h0) and sb (h1), kept while in use */
                LONG want = r ? sb : sy;
                DWORD *hrow = r ? h1 : h0;
                const WORD *s;
                if (r ? want == rb : want == ra) continue;
                s = (const WORD *)(src + want * spitch);
                for (x = 0; x < n; x++) {
                    LONG e = g_cz_xs[x0 + x], i = e & 0xffff, w = e >> 16, j = i + 1 < sw ? i + 1 : i;
                    DWORD p = s[i], P = (p | (p << 16)) & lane;
                    if (w) { DWORD q = s[j], Q = (q | (q << 16)) & lane; P = ((P * (32 - w) + Q * w) >> 5) & lane; }
                    hrow[x] = P;
                }
                if (r) rb = want; else ra = want;
            }
            for (q = 0; q < ns; q++) {
                LONG a = sg[2 * q] - x0, b = sg[2 * q + 1] - x0;
                if (!wy) for (x = a; x < b; x++) { DWORD v = h0[x]; d[x] = (WORD)(v | (v >> 16)); }
                else for (x = a; x < b; x++) {
                    DWORD v = ((h0[x] * (32 - wy) + h1[x] * wy) >> 5) & lane;
                    d[x] = (WORD)(v | (v >> 16));
                }
            }
        }
    }
}
#define CZ_THREADS 4   /* measured 2026-10-22: 6 lost to the sim's 8 traffic workers while it runs */
static struct { BYTE *dst; LONG dpitch; const BYTE *src; LONG spitch, sw, sh, f; int smooth; DWORD gmask; LONG x0, x1;
                LONG y[CZ_THREADS + 1]; void (*gfn)(void *); void *garg[CZ_THREADS]; } g_czj;   /* gfn set: a generic job */
static HANDLE  g_czw_go[CZ_THREADS], g_czw_done[CZ_THREADS];
static CZ_ROWS g_czw_rows[CZ_THREADS];
static int     g_czw_n = -1;               /* workers running (-1 = not started, 0 = none: single thread) */
static DWORD WINAPI cz_worker(LPVOID p) {
    int k = (int)(INT_PTR)p;
    for (;;) {
        if (WaitForSingleObject(g_czw_go[k], INFINITE) != WAIT_OBJECT_0) return 0;
        if (g_czj.gfn) g_czj.gfn(g_czj.garg[k + 1]);
        else cz_stretch_rows(&g_czw_rows[k], g_czj.dst, g_czj.dpitch, g_czj.src, g_czj.spitch, g_czj.sw, g_czj.sh, g_czj.f,
                             g_czj.smooth, g_czj.gmask, g_czj.x0, g_czj.y[k + 1], g_czj.x1, g_czj.y[k + 2]);
        SetEvent(g_czw_done[k]);
    }
}
static void cz_pool_start(void) {
    int k;
    if (g_czw_n < 0) {   /* start the workers once: CZ_THREADS - 1 of them, the caller takes a band too */
        SYSTEM_INFO si;
        GetSystemInfo(&si);
        g_czw_n = 0;
        for (k = 0; k < CZ_THREADS - 1 && (DWORD)k + 1 < si.dwNumberOfProcessors; k++) {
            g_czw_go[k] = CreateEventA(NULL, FALSE, FALSE, NULL);
            g_czw_done[k] = CreateEventA(NULL, FALSE, FALSE, NULL);
            if (!g_czw_go[k] || !g_czw_done[k] || !CreateThread(NULL, 0, cz_worker, (LPVOID)(INT_PTR)k, 0, NULL)) break;
            g_czw_n++;
        }
        logf("CITYZOOM> stretch on %d thread(s)", g_czw_n + 1);
    }
}
static int cz_pool_size(void) { cz_pool_start(); return g_czw_n + 1; }
/* run fn(args[0..n-1]) with args[0] on the caller and the rest on the workers; n <= cz_pool_size() */
static void cz_pool_run(void (*fn)(void *), void **args, int n) {
    int k;
    if (n > g_czw_n + 1) n = g_czw_n + 1;
    if (n <= 1) { fn(args[0]); return; }
    g_czj.gfn = fn;
    for (k = 0; k < n; k++) g_czj.garg[k] = args[k];
    for (k = 0; k < n - 1; k++) SetEvent(g_czw_go[k]);
    fn(args[0]);
    WaitForMultipleObjects(n - 1, g_czw_done, TRUE, INFINITE);
    g_czj.gfn = NULL;
}
static void cz_stretch(BYTE *dst, LONG dpitch, const BYTE *src, LONG spitch, LONG sw, LONG sh, LONG f, int smooth,
                       DWORD gmask, LONG x0, LONG y0, LONG x1, LONG y1) {
    static CZ_ROWS main_rows;
    int k, nb;
    if (x1 <= x0 || y1 <= y0 || f < 1 || sw <= 0 || sh <= 0) return;
    cz_tables(f, sw, x1);
    if (!g_cz_xs) return;
    cz_pool_start();
    nb = (x1 - x0) * (y1 - y0) >= 100000 ? g_czw_n + 1 : 1;
    if (nb <= 1) { cz_stretch_rows(&main_rows, dst, dpitch, src, spitch, sw, sh, f, smooth, gmask, x0, y0, x1, y1); return; }
    g_czj.dst = dst; g_czj.dpitch = dpitch; g_czj.src = src; g_czj.spitch = spitch; g_czj.sw = sw; g_czj.sh = sh;
    g_czj.f = f; g_czj.smooth = smooth; g_czj.gmask = gmask; g_czj.x0 = x0; g_czj.x1 = x1; g_czj.gfn = NULL;
    for (k = 0; k <= nb; k++) {   /* band edges on view-row boundaries, so no band starts inside a repeated row */
        LONG e = y0 + (LONG)((__int64)(y1 - y0) * k / nb);
        if (k > 0 && k < nb) { e = (e / f) * f; if (e < y0) e = y0; }
        g_czj.y[k] = k == nb ? y1 : e;
    }
    for (k = 0; k < nb - 1; k++) SetEvent(g_czw_go[k]);
    cz_stretch_rows(&main_rows, dst, dpitch, src, spitch, sw, sh, f, smooth, gmask, x0, g_czj.y[0], x1, g_czj.y[1]);
    WaitForMultipleObjects(nb - 1, g_czw_done, TRUE, INFINITE);
}

/* HUDSCALE reads "the city" at client coordinates (see-through mask, the city at the dest pixel, erased native copies).
 * With a factor that is the stretched view, so fill the client-sized buffer with it on every rect this pass reads:
 * each window's source and dest rect, each dialog's native and dest rect, +-2 px for the bilinear taps. */
static LONG g_cz_done[64][4]; static int g_cz_ndone;   /* rects this pass has (filled or copied) */
static LONG g_cz_want[64][4]; static int g_cz_nwant;   /* last pass's rects: copied from the frame by the city Blt */
static LONG g_cz_wcw, g_cz_wch;                        /* client size those rects were for */
static int  g_cz_npre;                                 /* rects of g_cz_want copied this frame (0 = none) */
static DWORD g_czd_copypx;
static void cz_fill_rect(const BYTE *v, LONG vp, LONG vw, LONG vh, LONG cw, LONG ch, DWORD gmask, const LONG *r) {
    LONG x0 = r[0] - 2, y0 = r[1] - 2, x1 = r[2] + 2, y1 = r[3] + 2;
    int k;
    if (x0 < 0) x0 = 0;
    if (y0 < 0) y0 = 0;
    if (x1 > cw) x1 = cw;
    if (y1 > ch) y1 = ch;
    if (x1 <= x0 || y1 <= y0) return;
    for (k = 0; k < g_cz_ndone; k++)   /* a native rect inside its enlarged rect: already there */
        if (x0 >= g_cz_done[k][0] && y0 >= g_cz_done[k][1] && x1 <= g_cz_done[k][2] && y1 <= g_cz_done[k][3]) return;
    if (g_cz_ndone < 64) { g_cz_done[g_cz_ndone][0] = x0; g_cz_done[g_cz_ndone][1] = y0;
                           g_cz_done[g_cz_ndone][2] = x1; g_cz_done[g_cz_ndone][3] = y1; g_cz_ndone++; }
    for (k = 0; k < g_cz_npre; k++)    /* copied from this frame's stretch by cz_stretch_blt */
        if (x0 >= g_cz_want[k][0] && y0 >= g_cz_want[k][1] && x1 <= g_cz_want[k][2] && y1 <= g_cz_want[k][3]) return;
    g_czd_fillpx += (DWORD)((x1 - x0) * (y1 - y0));
    cz_stretch((BYTE *)g_cz_buf, cw * 2, v, vp, vw, vh, g_cz_f, g_cz_filt, gmask, x0, y0, x1, y1);
}

static void cz_fill_hs(int n, LONG cw, LONG ch, DWORD gmask) {
    LONG vp, vw, vh;
    DWORD sub;
    const BYTE *v;
    int i, k;
    if (g_cz_f <= 1 || !g_cz_buf) return;
    LARGE_INTEGER t0, t1;
    QueryPerformanceCounter(&t0);
    v = cz_view_bits(&vp, &vw, &vh, &sub);
    if (!v) return;
    g_cz_ndone = 0;
    for (i = 0; i < n; i++) cz_fill_rect(v, vp, vw, vh, cw, ch, gmask, g_hs_dst[i]);   /* the big ones first */
    for (i = 0; i < n; i++) cz_fill_rect(v, vp, vw, vh, cw, ch, gmask, g_hs_src[i]);
    for (k = 0; k < g_hd_nc; k++) {
        cz_fill_rect(v, vp, vw, vh, cw, ch, gmask, g_hd[g_hd_list[k]].nat);
        cz_fill_rect(v, vp, vw, vh, cw, ch, gmask, g_hd[g_hd_list[k]].dst);
    }
    for (k = 0; k < g_hs_ndlg; k++) cz_fill_rect(v, vp, vw, vh, cw, ch, gmask, g_hs_dlg[k]);
    cz_view_unlock(sub);
    memcpy(g_cz_want, g_cz_done, sizeof(LONG) * 4 * g_cz_ndone);   /* the next city Blt copies these */
    g_cz_nwant = g_cz_ndone; g_cz_wcw = cw; g_cz_wch = ch; g_cz_npre = 0;
    QueryPerformanceCounter(&t1);
    g_czd_fill += t1.QuadPart - t0.QuadPart;
}

/* The city Blt itself: the whole client from the view, into the composite. 0 = done (DD_OK). */
static HRESULT cz_stretch_now(void *self) {
    LONG pitch, sw, sh, vp, vw, vh, cw, ch;
    DWORD bpp, gmask, sub;
    BYTE *bits;
    const BYTE *v;
    RECT rc;
    LARGE_INTEGER a, b;
    if (!g_hwnd || !GetClientRect(g_hwnd, &rc)) return -1;
    cw = rc.right; ch = rc.bottom;
    if (g_cz_instretch) { g_cz_nnest++; return -1; }
    QueryPerformanceCounter(&a);
    {   /* MOVENEAREST: did the view origin move since the last stretch? */
        DWORD now = GetTickCount(), iso = g_bridge && !IsBadReadPtr(g_bridge, 0x1c) ? ((DWORD *)g_bridge)[0x18 / 4] : 0;
        if (iso && !IsBadReadPtr((void *)iso, 0x60)) {
            LONG ox = ((LONG *)iso)[0x54 / 4], oy = ((LONG *)iso)[0x58 / 4];
            if (ox != g_cz_lox || oy != g_cz_loy) { if (g_cz_lox != 0x7fffffff) g_cz_movet = now; g_cz_lox = ox; g_cz_loy = oy; }
        }
        g_cz_filt = g_hs_filter && !(g_cz_movenear && g_cz_movet && now - g_cz_movet < 120);
    }
    if (!(g_cz_skok && g_cz_skw == cw && g_cz_skh == ch && g_cz_skf == g_cz_f)) g_cz_skok = 0;   /* SKIP: same geometry only */
    v = cz_view_bits(&vp, &vw, &vh, &sub);
    if (!v) return -1;
    g_cz_instretch = 1;
    {   DWORD *vt = *(DWORD **)self;
        BYTE desc[124];
        memset(desc, 0, sizeof(desc)); *(DWORD *)desc = 124;
        if (((RZ_LOCK)vt[0x64 / 4])(self, NULL, desc, 1 /* DDLOCK_WAIT */, NULL)) { g_cz_instretch = 0; cz_view_unlock(sub); return -1; }
        pitch = *(LONG *)(desc + 0x10); sh = *(LONG *)(desc + 0x08); sw = *(LONG *)(desc + 0x0c);
        bpp = *(DWORD *)(desc + 0x54); gmask = *(DWORD *)(desc + 0x5c); bits = *(BYTE **)(desc + 0x24);
    }
    g_cz_npre = 0;
    if (bits && bpp == 16 && sw >= cw && sh >= ch) {
        int k;
        cz_stretch(bits, pitch, v, vp, vw, vh, g_cz_f, g_cz_filt, gmask, 0, 0, cw, ch);
        /* HUDSCALE needs the stretched city under the HUD; it is in the frame now, before the HUD is drawn over it */
        if (g_hudscale && g_hs_n > 0 && g_cz_nwant > 0 && g_cz_wcw == cw && g_cz_wch == ch && g_cz_buf && g_cz_bufcap >= cw * ch) {
            for (k = 0; k < g_cz_nwant; k++) {
                const LONG *r = g_cz_want[k];
                LONG y;
                for (y = r[1]; y < r[3]; y++) {
                    LONG sg[2 * CZ_MAXSEG];
                    int ns = cz_segs(y, r[0], r[2], sg), q;
                    for (q = 0; q < ns; q++) {
                        memcpy(g_cz_buf + y * cw + sg[2 * q], (WORD *)(bits + y * pitch) + sg[2 * q], (sg[2 * q + 1] - sg[2 * q]) * 2);
                        g_czd_copypx += (DWORD)(sg[2 * q + 1] - sg[2 * q]);
                    }
                }
            }
            g_cz_npre = g_cz_nwant;
        }
    }
    ((RZ_UNLOCK)(*(DWORD **)self)[0x80 / 4])(self, NULL);
    cz_view_unlock(sub);
    g_cz_instretch = 0;
    QueryPerformanceCounter(&b);
    g_cz_tstretch += b.QuadPart - a.QuadPart; g_cz_nstretch++; g_czd_str += b.QuadPart - a.QuadPart;
    {   static DWORD t0;
        DWORD now = GetTickCount();
        if (!t0) t0 = now;
        if (now - t0 >= 10000) {
            logf("CITYZOOM> x%ld %s: %lu stretches in %lu ms, %.2f ms each (view %ldx%ld -> client %ldx%ld); view Blts: "
                 "full %lu + %lu with slack rows, partial %lu (last [%ld %ld %ld %ld]), not onto the frame %lu; rewritten %lu, nested %lu", g_cz_f,
                 g_hs_filter ? "smooth" : "nearest", g_cz_nstretch, now - t0,
                 g_cz_nstretch ? 1000.0 * (double)g_cz_tstretch / (double)g_freq.QuadPart / g_cz_nstretch : 0.0,
                 g_cz_vw, g_cz_vh, cw, ch, g_cz_nfull[0], g_cz_nfull[1], g_cz_npart, g_cz_lastpart.left, g_cz_lastpart.top,
                 g_cz_lastpart.right, g_cz_lastpart.bottom, g_cz_nother, g_cz_nrw, g_cz_nnest);
            g_cz_nrw = g_cz_nnest = 0;
            t0 = now; g_cz_nstretch = 0; g_cz_tstretch = 0; g_cz_nother = g_cz_npart = g_cz_nfull[0] = g_cz_nfull[1] = 0;
        }
    }
    if (!bits || bpp != 16 || sw < cw || sh < ch) {
        static int logged;
        if (logged++ < 3) logf("CITYZOOM> composite %ldx%ld bpp %lu refused for client %ldx%ld", sw, sh, bpp, cw, ch);
        return -1;
    }
    return 0;
}

/* DEFER (owner hand test 2026-10-22: "some minor FPS drop when moving around"). Measured: while the camera moves the
 * game Blts the view into the frame twice per frame (the scroll handler's own repaint, then the frame's), with only the
 * RCI corner Blt between them, so every moving frame paid two 4K stretches. A city Blt now only marks the frame as owed;
 * the next city Blt drops an owed one; anything else that reads or draws the frame pays it first (any Blt from it, a Lock,
 * GetDC or BltFast of it, a Blt onto it that is not small). Up to two small Blts onto it (the RCI) are passed through and
 * replayed after a late stretch. Only once HUDPERF's Lock/GetDC/BltFast hooks are in (they see every other access).
 * SC3RESIZE_CITYZOOM_DEFER=0: stretch on every city Blt. */
static int  g_cz_defer = 1;
static int  g_hp_lzinst;              /* fwd: HUDPERF lazy-restore hooks installed (> 0) */
static void *g_czp_frame;
static volatile LONG g_czp_on;
typedef struct { void *self, *src; RECT dr, sr; int hd, hs, hfx; DWORD fl; BYTE fx[128]; } CZ_QBLT;
static CZ_QBLT g_czq[2];
static int  g_czq_n;
static DWORD g_czd_drop, g_czd_pay[4];   /* 10-s / 1-s diag: dropped stretches; paid by 0 Blt onto, 1 Blt from, 2 Lock/GetDC/BltFast, 3 overflow */
static int  g_czp_kind;                /* 0 a stretch is owed, 1 the game's own 1:1 city Blt is owed (stock zoom, DEFER1) */
static RECT g_czp1_dr, g_czp1_sr;
static int  g_czp1_hs, g_czp1_hfx;
static DWORD g_czp1_fl;
static BYTE g_czp1_fx[128];
/* DEFER1 (owner 2026-10-22, "also skip the redundant copy at stock zoom"): the same rule at x1, where the owed Blt is the
   game's own 1:1 copy of the view into the frame (about 10 ms at 3840x1984). SC3RESIZE_CITYZOOM_DEFER1=0 turns it off. */
static int  g_cz_defer1 = 1;
static void cz_pay(int why);   /* below */
static HRESULT cz_stretch_blt(void *self) {
    if (g_cz_defer && g_hp_lzinst > 0 && self == g_cz_devsurf) {
        if (g_czp_on) g_czd_drop++;
        g_czp_frame = self; g_czq_n = 0; g_czp_kind = 0;
        InterlockedExchange(&g_czp_on, 1);
        return 0;
    }
    return cz_stretch_now(self);
}
/* x1: 1 = this Blt is the view -> frame copy and is now owed (the caller returns DD_OK without doing it) */
static int cz_defer1(void *self, const RECT *dr, void *src, const RECT *sr, DWORD fl, void *fx) {
    RECT cr;
    static int why_n;
    if (g_cz_diag && why_n < 6 && src && src == g_cz_surf && src != self) {   /* why a view Blt was not owed */
        why_n++;
        logf("CZDIAG> x1 view Blt: defer %d defer1 %d f %ld lzinst %d frame %d fx %d fl %08lX dr [%ld %ld %ld %ld]",
             g_cz_defer, g_cz_defer1, g_cz_f, g_hp_lzinst, self == g_cz_devsurf, fx != NULL, fl,
             dr ? dr->left : -1, dr ? dr->top : -1, dr ? dr->right : -1, dr ? dr->bottom : -1);
    }
    DWORD fsz = 0;
    /* measured 2026-10-22: at x1 the game copies the view into the map area only ([0 0 3744 1928] at 3840x1984, the
       native HUD strips are the HUD's) and passes a DDBLTFX with DDBLT_WAIT */
    if (!g_cz_defer || !g_cz_defer1 || g_cz_f != 1 || g_hp_lzinst <= 0 || !src || src == self || src != g_cz_surf ||
        self != g_cz_devsurf || (fl & ~0x01000000) || !dr || IsBadReadPtr(dr, sizeof(RECT)) || !g_hwnd ||
        !GetClientRect(g_hwnd, &cr) || dr->left > 0 || dr->top > 0 ||
        (dr->right - dr->left) * (dr->bottom - dr->top) < cr.right * cr.bottom / 2) return 0;
    if (fx) {
        if (IsBadReadPtr(fx, 4) || (fsz = *(DWORD *)fx) < 4 || fsz > sizeof(g_czp1_fx) || IsBadReadPtr(fx, fsz)) return 0;
    }
    if (g_czp_on && (g_czp_kind != 1 || dr->left > g_czp1_dr.left || dr->top > g_czp1_dr.top ||
                     dr->right < g_czp1_dr.right || dr->bottom < g_czp1_dr.bottom)) cz_pay(0);   /* does not cover the owed one */
    else if (g_czp_on) g_czd_drop++;
    g_czp1_dr = *dr; g_czp1_hs = sr && !IsBadReadPtr(sr, sizeof(RECT)); if (g_czp1_hs) g_czp1_sr = *sr;
    g_czp1_fl = fl; g_czp1_hfx = fx != NULL; if (fx) memcpy(g_czp1_fx, fx, fsz);
    g_czp_frame = self; g_czq_n = 0; g_czp_kind = 1;
    InterlockedExchange(&g_czp_on, 1);
    return 1;
}
static void cz_pay(int why) {
    int k, n = g_czq_n;
    void *f = g_czp_frame;
    if (!InterlockedExchange(&g_czp_on, 0)) return;
    g_czq_n = 0;
    if (why >= 0 && why < 4) g_czd_pay[why]++;
    if (g_czp_kind == 1) {   /* DEFER1: the game's own copy, as it asked for it */
        if (g_orig_blt) g_orig_blt(f, &g_czp1_dr, g_cz_surf, g_czp1_hs ? &g_czp1_sr : NULL, g_czp1_fl, g_czp1_hfx ? g_czp1_fx : NULL);
    } else if (cz_stretch_now(f) && g_orig_blt) {   /* the stretch failed: the game's own (ddraw) stretch, as without DEFER */
        RECT cd, cs;
        if (g_hwnd && GetClientRect(g_hwnd, &cd)) {
            cs.left = 0; cs.top = 0; cs.right = cd.right / g_cz_f; cs.bottom = cd.bottom / g_cz_f;
            g_orig_blt(f, &cd, g_cz_surf, &cs, 0x01000000, NULL);
        }
    }
    for (k = 0; k < n && g_orig_blt; k++) {
        CZ_QBLT *q = &g_czq[k];
        g_orig_blt(q->self, q->hd ? &q->dr : NULL, q->src, q->hs ? &q->sr : NULL, q->fl, q->hfx ? q->fx : NULL);
    }
}
/* A Blt that touches the owed frame: queue it (small, onto it) or pay first. 1 = queued (the caller still does it). */
static int cz_touch(void *self, RECT *dr, void *src, RECT *sr, DWORD fl, void *fx) {
    if (!g_czp_on || (self != g_czp_frame && src != g_czp_frame)) return 0;
    if (self == g_czp_frame && src != self && dr && !IsBadReadPtr(dr, sizeof(RECT)) && g_czq_n < 2 &&
        (dr->right - dr->left) * (dr->bottom - dr->top) <= 20000) {
        CZ_QBLT *q = &g_czq[g_czq_n];
        DWORD sz = 0;
        q->self = self; q->src = src; q->dr = *dr; q->hd = 1; q->fl = fl;
        q->hs = sr && !IsBadReadPtr(sr, sizeof(RECT)); if (q->hs) q->sr = *sr;
        q->hfx = 0;
        if (fx && !IsBadReadPtr(fx, 4)) { sz = *(DWORD *)fx; if (sz >= 4 && sz <= sizeof(q->fx) && !IsBadReadPtr(fx, sz)) { memcpy(q->fx, fx, sz); q->hfx = 1; } }
        if (fx && !q->hfx) { cz_pay(3); return 0; }
        g_czq_n++;
        return 1;
    }
    cz_pay(src == g_czp_frame ? 1 : (g_czq_n >= 2 ? 3 : 0));
    return 0;
}

/* A view raster's IDirectDrawSurface, as rz_patch_ddblt finds iso+0x74's: *(*(iso+off)+0x44)+0x04. */
static void *cz_find_surf_at(DWORD off) {
    DWORD iso, R, sub;
    if (!g_bridge || IsBadReadPtr(g_bridge, 0x1c)) return NULL;
    iso = ((DWORD *)g_bridge)[0x18 / 4];
    if (!iso || IsBadReadPtr((void *)iso, 0x4f0)) return NULL;
    R = ((DWORD *)iso)[off / 4];
    if (!R || IsBadReadPtr((void *)R, 0x48)) return NULL;
    sub = ((DWORD *)R)[0x44 / 4];
    if (!sub || IsBadReadPtr((void *)sub, 0x08)) return NULL;
    return (void *)((DWORD *)sub)[0x04 / 4];
}

/* The city-only render target iso+0x74 (raster: +0x44 sub, sub+0xf0 bits, sub+0xf4 pitch, mapped by a
   balanced sub vt+0x0c / vt+0x10 lock as the surface dumper does). Used as the mask: a HUD-rect pixel that
   equals the city layer is the city showing through, not HUD. Returns bits or NULL; *sub_locked to unlock. */
static BYTE *rz_hs_city(LONG cw, LONG ch, LONG *pitch, DWORD *sub_locked) {
    DWORD iso, obj, sub, bits, pt, *svt;
    HMODULE gz = GetModuleHandleA("GZGraphicD.dll");
    static int logged;
    *sub_locked = 0;
    if (g_cz_f > 1) {   /* task cityzoom: the stretched view, filled by cz_fill_hs once the frame format is known */
        if (g_cz_bufcap < cw * ch) {
            free(g_cz_buf);
            g_cz_buf = (WORD *)malloc((size_t)cw * ch * 2);
            g_cz_bufcap = g_cz_buf ? cw * ch : 0;
        }
        if (!g_cz_buf) return NULL;
        *pitch = cw * 2;
        return (BYTE *)g_cz_buf;
    }
    if (!g_bridge || IsBadReadPtr(g_bridge, 0x1c) || !gz) return NULL;
    iso = ((DWORD *)g_bridge)[0x18 / 4];
    if (!iso || IsBadReadPtr((void *)iso, 0x78)) return NULL;
    obj = ((DWORD *)iso)[0x74 / 4];
    if (!obj || IsBadReadPtr((void *)obj, 0x48)) return NULL;
    if ((LONG)((DWORD *)obj)[0x24 / 4] < cw || (LONG)((DWORD *)obj)[0x28 / 4] < ch) {
        if (!logged++) logf("HUDSCALE> city layer %lux%lu smaller than the client %ldx%ld - no mask",
                            ((DWORD *)obj)[0x24 / 4], ((DWORD *)obj)[0x28 / 4], cw, ch);
        return NULL;
    }
    sub = ((DWORD *)obj)[0x44 / 4];
    if (!sub || IsBadReadPtr((void *)sub, 0xf8)) return NULL;
    bits = ((DWORD *)sub)[0xf0 / 4]; pt = ((DWORD *)sub)[0xf4 / 4];
    if (!bits || !pt) {
        svt = *(DWORD **)sub;
        if (!svt || IsBadReadPtr(svt, 0x14) || (DWORD)svt != (DWORD)gz + GZ_RVA_VT_SURFACE || !svt[0x0c / 4]) return NULL;
        if (!(rz_thiscall((void *)sub, (void *)svt[0x0c / 4], NULL, 0) & 0xff)) return NULL;
        *sub_locked = sub;
        bits = ((DWORD *)sub)[0xf0 / 4]; pt = ((DWORD *)sub)[0xf4 / 4];
    }
    if (!bits || (LONG)pt < cw * 2) {
        if (*sub_locked) { svt = *(DWORD **)sub; rz_thiscall((void *)sub, (void *)svt[0x10 / 4], NULL, 0); *sub_locked = 0; }
        return NULL;
    }
    if (!logged++) logf("HUDSCALE> city mask: iso+0x74 %lux%lu pitch %lu%s", ((DWORD *)obj)[0x24 / 4],
                        ((DWORD *)obj)[0x28 / 4], pt, *sub_locked ? " (locked)" : " (mapped)");
    *pitch = (LONG)pt;
    return (BYTE *)bits;
}
static void rz_hs_city_unlock(DWORD sub) {
    DWORD *svt;
    if (!sub) return;
    svt = *(DWORD **)sub;
    if (svt && !IsBadReadPtr(svt, 0x14) && svt[0x10 / 4]) rz_thiscall((void *)sub, (void *)svt[0x10 / 4], NULL, 0);
}

static LONG rz_hs_src_coord(LONG d, LONG c, double s) {   /* nearest source pixel of dest pixel d */
    double u = (double)c + ((double)d + 0.5 - (double)c) / s;
    LONG v = (LONG)u;
    if ((double)v > u) v--;   /* floor for negatives */
    return v;
}
static LONG rz_hs_dst_lo(LONG a, LONG c, double s) {      /* smallest d whose source >= a */
    double t = (double)c + s * ((double)a - (double)c) - 0.5;
    LONG v = (LONG)t;
    if ((double)v < t) v++;   /* ceil */
    while (rz_hs_src_coord(v, c, s) < a) v++;
    while (rz_hs_src_coord(v - 1, c, s) >= a) v--;
    return v;
}
static int rz_hs_tables(LONG cw, LONG ch, double s) {
    LONG i;
    if (g_hs_xs && g_hs_tcw == cw && g_hs_tch == ch && g_hs_ts == s) return 1;
    free(g_hs_xs); free(g_hs_ys); free(g_hs_xf); free(g_hs_yf);
    g_hs_xs = (LONG *)malloc(cw * sizeof(LONG)); g_hs_xf = (LONG *)malloc(cw * sizeof(LONG));
    g_hs_ys = (LONG *)malloc(ch * sizeof(LONG)); g_hs_yf = (LONG *)malloc(ch * sizeof(LONG));
    if (!g_hs_xs || !g_hs_ys || !g_hs_xf || !g_hs_yf) { g_hs_xs = NULL; return 0; }
    for (i = 0; i < cw; i++) {
        double u = (double)cw + ((double)i + 0.5 - (double)cw) / s - 0.5;
        LONG b = (LONG)u; if ((double)b > u) b--;
        g_hs_xs[i] = rz_hs_src_coord(i, cw, s);
        g_hs_xf[i] = (b < 0 ? 0 : b) | ((LONG)((u - (double)b) * 256.0) << 20);   /* base | weight<<20 */
    }
    for (i = 0; i < ch; i++) {
        double u = (double)ch + ((double)i + 0.5 - (double)ch) / s - 0.5;
        LONG b = (LONG)u; if ((double)b > u) b--;
        g_hs_ys[i] = rz_hs_src_coord(i, ch, s);
        g_hs_yf[i] = (b < 0 ? 0 : b) | ((LONG)((u - (double)b) * 256.0) << 20);
    }
    g_hs_tcw = cw; g_hs_tch = ch; g_hs_ts = s;
    logf("HUDSCALE> tables for %ldx%ld at %.3fx (native HUD box [%ld %ld %ld %ld] fills the client)", cw, ch, s,
         cw - (LONG)((double)cw / s), ch - (LONG)((double)ch / s), cw, ch);
    return 1;
}

/* COSTLABEL: was the game's cursor on the enlarged HUD when this floating window took this rect, and does the rect
   touch a native HUD window? Latched per window and rect (a new rect = the game moved it, so decide again). */
static int rz_hs_float_hud(void *win, const LONG *r, DWORD vt) {
    int i, k = -1, old = 0, touch = 0;
    DWORD exe = (DWORD)GetModuleHandleA(NULL);
    g_hs_fl_stamp++;
    for (i = 0; i < HS_FL_MAX; i++) if (g_hs_fl[i].win == win) { k = i; break; }
    if (k >= 0 && !memcmp(g_hs_fl[k].r, r, sizeof(g_hs_fl[k].r))) { g_hs_fl[k].stamp = g_hs_fl_stamp; return g_hs_fl[k].hud; }
    if (k >= 0) old = 1;
    else {
        for (i = 0, k = 0; i < HS_FL_MAX; i++) if (g_hs_fl[i].stamp < g_hs_fl[k].stamp) k = i;   /* oldest slot */
    }
    for (i = 0; i < g_hs_nhudr && !touch; i++)
        touch = r[0] < g_hs_hudr[i][2] + 8 && r[2] > g_hs_hudr[i][0] - 8 && r[1] < g_hs_hudr[i][3] + 8 && r[3] > g_hs_hudr[i][1] - 8;
    g_hs_fl[k].win = win; memcpy(g_hs_fl[k].r, r, sizeof(g_hs_fl[k].r));
    g_hs_fl[k].hud = g_hs_mouse_hud && touch; g_hs_fl[k].stamp = g_hs_fl_stamp;
    if (g_hs_fl_logs < 100) {
        g_hs_fl_logs++;
        logf("COSTLABEL> floating %08lX [%ld %ld %ld %ld] %s: cursor %s, %s a HUD window -> %s",
             vt - (exe && vt > exe && vt < exe + 0x200000 ? exe : 0), r[0], r[1], r[2], r[3], old ? "moved" : "shown",
             g_hs_mouse_hud ? "on the HUD" : "in the city", touch ? "touches" : "clear of", g_hs_fl[k].hud ? "enlarged" : "native");
    }
    return g_hs_fl[k].hud;
}

/* HSCENSUS (owner 2026-10-23: "are there other elements that need rescaling?"): one log line per distinct
   (class, size, decision) of a visible root / HUD-container window while HUD scale is enlarging, so a normal play
   session lists every UI window and what HUDSCALE did with it. SC3RESIZE_HSCENSUS=0 turns it off. */
static int g_hs_census = 1;
static void rz_hs_census(DWORD vt, const LONG *r, const char *what) {
    static DWORD seen[512];
    static int nseen;
    DWORD sui = (DWORD)GetModuleHandleA("SIMUI.DLL"), exe = (DWORD)GetModuleHandleA(NULL), spr = (DWORD)GetModuleHandleA("SIMSPR.DLL");
    DWORD key = (vt * 2654435761u) ^ (DWORD)((r[2] - r[0]) * 7919 + (r[3] - r[1]) * 104729) ^ (DWORD)what[0] * 31 ^ (DWORD)what[1];
    int i;
    const char *mod = "?";
    DWORD rel = vt;
    if (!g_hs_census) return;
    for (i = 0; i < nseen; i++) if (seen[i] == key) return;
    if (nseen >= 512) return;
    seen[nseen++] = key;
    if (sui && vt > sui && vt < sui + 0x200000) { mod = "SIMUI"; rel = vt - sui; }
    else if (exe && vt > exe && vt < exe + 0x200000) { mod = "SC3U"; rel = vt - exe; }
    else if (spr && vt > spr && vt < spr + 0x200000) { mod = "SIMSPR"; rel = vt - spr; }
    logf("HSCENSUS> %s+0x%05lX %ldx%ld at [%ld %ld %ld %ld]: %s", mod, rel, r[2] - r[0], r[3] - r[1], r[0], r[1], r[2], r[3], what);
}

/* Collect visible HUD windows (root children, and children of the full-client HUD container). Returns count. */
static int rz_hs_collect(LONG cw, LONG ch, double s, int can_erase) {
    DWORD exe = (DWORD)GetModuleHandleA(NULL), spr = (DWORD)GetModuleHandleA("SIMSPR.DLL");
    DWORD sui = (DWORD)GetModuleHandleA("SIMUI.DLL");
    void *lvl[2], *root = rz_ui_root();
    int nl = 1, li, n = 0;
    DWORD sig = 2166136261u;
    char skipped[400];
    int sk = 0;
    g_hs_ndlg = 0;
    g_hd_nc = 0; g_hd_stamp++;
    skipped[0] = 0;
    if (!root) return 0;
    lvl[0] = root;
    for (li = 0; li < nl; li++) {
        void *head = *(void **)((DWORD)lvl[li] + 0x34), *nd;
        int g = 0;
        if (!head || IsBadReadPtr(head, 4)) continue;
        for (nd = *(void **)head; nd && nd != head && g++ < 300; nd = *(void **)nd) {
            DWORD *c, vt;
            LONG r[4], w, h;
            if (IsBadReadPtr(nd, 0x0c)) break;
            c = *(DWORD **)((DWORD)nd + 8);
            if (!c || IsBadReadPtr(c, 0xa4)) continue;
            vt = c[0];
            if (exe && vt == exe + 0xd32d0) { if (nl < 2) lvl[nl++] = c; continue; }   /* HUD container */
            if (!(c[0xa0 / 4] & 1)) continue;                                         /* hidden */
            if (spr && vt == spr + 0x676ac) continue;                                 /* city view */
            r[0] = (LONG)c[0x14 / 4]; r[1] = (LONG)c[0x18 / 4]; r[2] = (LONG)c[0x1c / 4]; r[3] = (LONG)c[0x20 / 4];
            w = r[2] - r[0]; h = r[3] - r[1];
            if (sui && vt == sui + 0xa4d64 && w >= 120 && h >= 80) {                  /* dialog */
                if (!rz_hd_add(c, r, cw, ch, s)) { rz_hs_census(vt, r, "dialog KEPT NATIVE"); if (g_hs_ndlg < 16) { memcpy(g_hs_dlg[g_hs_ndlg], r, sizeof(r)); g_hs_ndlg++; } }
                else rz_hs_census(vt, r, "dialog enlarged");
                sig = (sig ^ (DWORD)(r[0] * 7 + r[1] * 131 + r[2] * 8191 + r[3] * 524287) ^ 0xd1a1) * 16777619u;
                continue;
            }
            if (r[0] < 0) r[0] = 0;
            if (r[1] < 0) r[1] = 0;
            if (r[2] > cw) r[2] = cw;
            if (r[3] > ch) r[3] = ch;
            if (r[2] <= r[0] || r[3] <= r[1]) continue;
            if ((r[2] - r[0]) * (r[3] - r[1]) > cw * ch / 2) { rz_hs_census(vt, r, "full-client layer, NOT SCALED"); continue; }
            if (r[2] < cw - 2 && r[3] < ch - 2) {   /* floating (tooltips): enlarged only if it fits and can be erased */
                LONG fx0 = rz_hs_dst_lo(r[0], cw, s), fy0 = rz_hs_dst_lo(r[1], ch, s);
                int hud = g_hs_floatall || rz_hs_float_hud(c, r, vt);
                if (hud && can_erase && n < HS_MAX && fx0 >= 0 && fy0 >= 0 && (r[2] - r[0]) * (r[3] - r[1]) <= cw * ch / 16) {
                    memcpy(g_hs_src[n], r, sizeof(r));
                    g_hs_dst[n][0] = fx0; g_hs_dst[n][1] = fy0;
                    g_hs_dst[n][2] = rz_hs_dst_lo(r[2], cw, s); g_hs_dst[n][3] = rz_hs_dst_lo(r[3], ch, s);
                    g_hs_float[n] = 1; g_hs_vt[n] = vt;
                    rz_hs_census(vt, r, "floating, enlarged");
                    sig = (sig ^ (DWORD)vt ^ 0x5a5a) * 16777619u;
                    sig = (sig ^ (DWORD)(r[0] * 7 + r[1] * 131 + r[2] * 8191 + r[3] * 524287)) * 16777619u;
                    n++;
                    continue;
                }
                if (!hud && exe && vt == exe + 0xd3bcc && can_erase && rz_hl_add(c, r, cw, ch, s)) { rz_hs_census(vt, r, "cost label, enlarged"); continue; }   /* task uiscale */
                if (can_erase) rz_hs_census(vt, r, hud ? "floating HUD, NOT SCALED (no room)" : "floating, NOT SCALED");
                if (sk < 6) {
                    char t[64];
                    wsprintfA(t, " %08lX[%ld %ld %ld %ld]", vt - (sui && vt > sui && vt < sui + 0x200000 ? sui : 0),
                              r[0], r[1], r[2], r[3]);
                    lstrcatA(skipped, t); sk++;
                }
                continue;
            }
            if (n >= HS_MAX) continue;
            memcpy(g_hs_src[n], r, sizeof(r));
            g_hs_dst[n][0] = rz_hs_dst_lo(r[0], cw, s); g_hs_dst[n][1] = rz_hs_dst_lo(r[1], ch, s);
            g_hs_dst[n][2] = rz_hs_dst_lo(r[2], cw, s); g_hs_dst[n][3] = rz_hs_dst_lo(r[3], ch, s);
            if (g_hs_dst[n][0] < 0) g_hs_dst[n][0] = 0;
            if (g_hs_dst[n][1] < 0) g_hs_dst[n][1] = 0;
            if (g_hs_dst[n][2] > cw) g_hs_dst[n][2] = cw;
            if (g_hs_dst[n][3] > ch) g_hs_dst[n][3] = ch;
            g_hs_float[n] = 0; g_hs_vt[n] = vt;
            rz_hs_census(vt, r, "edge-anchored, enlarged");
            sig = (sig ^ (DWORD)vt) * 16777619u;
            sig = (sig ^ (DWORD)(r[0] * 7 + r[1] * 131 + r[2] * 8191 + r[3] * 524287)) * 16777619u;
            n++;
        }
    }
    sig ^= (DWORD)g_hs_ndlg * 0x9e3779b9u;
    {   /* COSTLABEL: keep this pass's edge-anchored rects for the next pass's floating test */
        int i;
        for (i = 0, g_hs_nhudr = 0; i < n; i++)
            if (!g_hs_float[i]) {
                memcpy(g_hs_hudd[g_hs_nhudr], g_hs_dst[i], sizeof(g_hs_hudd[0]));   /* task uiscale */
                memcpy(g_hs_hudr[g_hs_nhudr++], g_hs_src[i], sizeof(g_hs_hudr[0]));
            }
    }
    if (sig != g_hs_sig && g_hs_logs < 60) {
        int i;
        g_hs_sig = sig; g_hs_logs++;
        logf("HUDSCALE> %d window(s) enlarged %.3fx about (%ld,%ld), %d dialog(s) kept native, %d enlarged%s%s",
             n, s, cw, ch, g_hs_ndlg, g_hd_nc, sk ? "; not scaled (floating):" : "", skipped);
        for (i = 0; i < g_hd_nc; i++) {
            const HD_SLOT *d = &g_hd[g_hd_list[i]];
            logf("DLGSCALE>   dialog [%ld %ld %ld %ld] -> [%ld %ld %ld %ld] %.3fx", d->nat[0], d->nat[1], d->nat[2], d->nat[3],
                 d->dst[0], d->dst[1], d->dst[2], d->dst[3], (double)d->dw / d->w);
        }
        for (i = 0; i < n; i++)
            logf("HUDSCALE>   [%ld %ld %ld %ld] -> [%ld %ld %ld %ld]%s %08lX", g_hs_src[i][0], g_hs_src[i][1], g_hs_src[i][2],
                 g_hs_src[i][3], g_hs_dst[i][0], g_hs_dst[i][1], g_hs_dst[i][2], g_hs_dst[i][3],
                 g_hs_float[i] ? " (floating: native copy erased)" : "", g_hs_vt[i] -
                 (exe && g_hs_vt[i] > exe && g_hs_vt[i] < exe + 0x200000 ? exe : sui && g_hs_vt[i] > sui && g_hs_vt[i] < sui + 0x200000 ? sui : 0));
    }
    return n;
}

static void rz_hs_copy(BYTE *bits, LONG pitch, LONG ox, LONG oy, LONG cw, const LONG *r, int to_snap) {
    LONG y, x0 = r[0] < 0 ? 0 : r[0], x1 = r[2] > cw ? cw : r[2], y0 = r[1] < 0 ? 0 : r[1], y1 = r[3];
    if (x1 <= x0) return;
    for (y = y0; y < y1; y++) {
        WORD *f = (WORD *)(bits + (oy + y) * pitch) + ox + x0, *s = g_hs_snap + y * cw + x0;
        if (to_snap) memcpy(s, f, (x1 - x0) * 2); else memcpy(f, s, (x1 - x0) * 2);
    }
}

static BYTE *rz_hs_lock(void *src, LONG *pitch, DWORD *bpp, DWORD *gmask, LONG *sw, LONG *sh) {
    DWORD *vt = *(DWORD **)src;
    BYTE desc[124];
    HRESULT hr;
    memset(desc, 0, sizeof(desc)); *(DWORD *)desc = 124;
    hr = ((RZ_LOCK)vt[0x64 / 4])(src, NULL, desc, 1 /* DDLOCK_WAIT */, NULL);
    if (hr) { memset(desc, 0, sizeof(desc)); *(DWORD *)desc = 108; hr = ((RZ_LOCK)vt[0x64 / 4])(src, NULL, desc, 1, NULL); }
    if (hr) return NULL;
    *pitch = *(LONG *)(desc + 0x10);
    *sh = *(LONG *)(desc + 0x08); *sw = *(LONG *)(desc + 0x0c);
    *bpp = *(DWORD *)(desc + 0x54); *gmask = *(DWORD *)(desc + 0x5c);
    return *(BYTE **)(desc + 0x24);
}

static WORD rz_hs_lerp(WORD a, WORD b, LONG f, int g6) {   /* f 0..256 toward b */
    LONG ra = a >> 11, rb = b >> 11, ga, gb, ba = a & 31, bb = b & 31;
    if (g6) { ga = (a >> 5) & 63; gb = (b >> 5) & 63; }
    else    { ra = (a >> 10) & 31; rb = (b >> 10) & 31; ga = (a >> 5) & 31; gb = (b >> 5) & 31; }
    ra += ((rb - ra) * f) >> 8; ga += ((gb - ga) * f) >> 8; ba += ((bb - ba) * f) >> 8;
    return g6 ? (WORD)((ra << 11) | (ga << 5) | ba) : (WORD)((ra << 10) | (ga << 5) | ba);
}

/* DLGSCALE: take a dialog into this pass's enlarged list. 0 = keep it native (off, no room, off the client, list full). */
static int rz_hd_add(void *win, const LONG *r, LONG cw, LONG ch, double s) {
    LONG w = r[2] - r[0], h = r[3] - r[1], dw, dh, x0, y0;
    double sd = s;
    int i, k = -1;
    HD_SLOT *d;
    if (!g_dlgscale || g_hd_nc >= HD_MAX || r[0] < 0 || r[1] < 0 || r[2] > cw || r[3] > ch) return 0;
    if (sd > (double)cw / w) sd = (double)cw / w;
    if (sd > (double)ch / h) sd = (double)ch / h;
    if (sd < 1.01) return 0;
    dw = (LONG)(w * sd); dh = (LONG)(h * sd);
    if (dw > cw) dw = cw;
    if (dh > ch) dh = ch;
    x0 = (LONG)((r[0] + r[2] - dw) / 2.0 + 0.5); y0 = (LONG)((r[1] + r[3] - dh) / 2.0 + 0.5);
    if (x0 + dw > cw) x0 = cw - dw;
    if (y0 + dh > ch) y0 = ch - dh;
    if (x0 < 0) x0 = 0;
    if (y0 < 0) y0 = 0;
    for (i = 0; i < HD_MAX; i++) if (g_hd[i].win == win) { k = i; break; }
    if (k < 0)   /* reuse the slot unused for longest (never one already in this pass) */
        for (i = 0; i < HD_MAX; i++) {
            if (g_hd[i].used == g_hd_stamp) continue;
            if (k < 0 || g_hd[i].used < g_hd[k].used) k = i;
        }
    if (k < 0 || g_hd[k].used == g_hd_stamp) return 0;
    d = &g_hd[k];
    if (d->win != win) { d->win = win; d->valid = 0; }
    d->used = g_hd_stamp; d->lbl = 0;
    memcpy(d->nat, r, sizeof(d->nat));
    d->dst[0] = x0; d->dst[1] = y0; d->dst[2] = x0 + dw; d->dst[3] = y0 + dh;
    d->w = w; d->h = h; d->dw = dw; d->dh = dh;
    g_hd_list[g_hd_nc++] = k;
    return 1;
}

/* task uiscale: the city cost label, enlarged by the HUD factor at the cursor. 0 = keep it native. */
static int rz_hl_add(void *win, const LONG *r, LONG cw, LONG ch, double s) {
    LONG w = r[2] - r[0], h = r[3] - r[1], dw, dh, x0, y0, mx, my, P, gap;
    int i, k = -1, derived = 0;
    HD_SLOT *d;
    if (!g_costscale || g_hd_nc >= HD_MAX || w <= 0 || h <= 0 || s < 1.01) return 0;
    dw = (LONG)(w * s + 0.5); dh = (LONG)(h * s + 0.5);
    if (dw > cw / 2 || dh > ch / 4) return 0;   /* not a label */
    if (g_tip_seen) { mx = g_tip_mx; my = g_tip_my; P = g_tip_clr; }
    else { mx = (r[0] + r[2]) / 2 - 0x2c / 2; my = r[1] - 0x2c - 2; P = 32; derived = 1; }   /* stock layout */
    if (g_cz_f > 1) { mx *= g_cz_f; my *= g_cz_f; }   /* task cityzoom: the game placed it at the view point q / f */
    if (P < 32) P = 32;
    gap = 2 + (LONG)(2.0 * s + 0.5);
    {   /* below the pointer, else above the hotspot (the pointer hangs below-right of it); each inside the client and off
           the enlarged HUD (last pass's rects): shifted left of a window it would cover, if that still fits. The first
           candidate that is clear wins; if none is, below when it fits the client, else above. */
        LONG cy[2], cx = mx + P / 2 - dw / 2, bx = 0, by = 0;
        int c, j, pass, ok = 0;
        cy[0] = my + P + gap; cy[1] = my - gap - dh;
        for (c = 0; c < 2 && !ok; c++) {
            LONG x = cx, y = cy[c];
            if (y < 0 || y + dh > ch) continue;
            if (x + dw > cw) x = cw - dw;
            if (x < 0) x = 0;
            for (pass = 0; pass < 3; pass++) {
                int hit = -1;
                for (j = 0; j < g_hs_nhudr && hit < 0; j++)
                    if (x < g_hs_hudd[j][2] && x + dw > g_hs_hudd[j][0] && y < g_hs_hudd[j][3] && y + dh > g_hs_hudd[j][1]) hit = j;
                if (hit < 0) { ok = 1; break; }
                if (g_hs_hudd[hit][0] - dw < 0 || g_hs_hudd[hit][0] - dw >= x) break;   /* cannot shift left of it */
                x = g_hs_hudd[hit][0] - dw;
            }
            if (ok) { bx = x; by = y; }
        }
        if (!ok) {
            by = cy[0] + dh <= ch ? cy[0] : cy[1];
            bx = cx;
            if (bx + dw > cw) bx = cw - dw;
            if (by + dh > ch) by = ch - dh;
            if (bx < 0) bx = 0;
            if (by < 0) by = 0;
        }
        x0 = bx; y0 = by;
    }
    for (i = 0; i < HD_MAX; i++) if (g_hd[i].win == win) { k = i; break; }
    if (k < 0)
        for (i = 0; i < HD_MAX; i++) {
            if (g_hd[i].used == g_hd_stamp) continue;
            if (k < 0 || g_hd[i].used < g_hd[k].used) k = i;
        }
    if (k < 0 || g_hd[k].used == g_hd_stamp) return 0;
    d = &g_hd[k];
    if (d->win != win) { d->win = win; d->valid = 0; }
    d->used = g_hd_stamp; d->lbl = 1;
    memcpy(d->nat, r, sizeof(d->nat));
    d->dst[0] = x0; d->dst[1] = y0; d->dst[2] = x0 + dw; d->dst[3] = y0 + dh;
    d->w = w; d->h = h; d->dw = dw; d->dh = dh;
    g_hd_list[g_hd_nc++] = k;
    {   static LONG lr[4], lmx = -99999, lmy;
        if (g_hl_logs < 300 && (memcmp(lr, r, sizeof(lr)) || lmx != mx || lmy != my)) {
            g_hl_logs++; memcpy(lr, r, sizeof(lr)); lmx = mx; lmy = my;
            logf("COSTLABEL> city label [%ld %ld %ld %ld] -> [%ld %ld %ld %ld] %.3fx, cursor (%ld,%ld)%s%s, pointer %ld px, %s",
                 r[0], r[1], r[2], r[3], x0, y0, x0 + dw, y0 + dh, s, mx, my, derived ? " derived from the label" : "",
                 g_tip_flip ? " (game flipped it)" : "", P, y0 >= my + P ? "below the pointer" : y0 + dh <= my ? "above the hotspot" : "SHIFTED onto the pointer rows");
        }
    }
    return 1;
}

/* DLGSCALE: make sure the slot's buffers and tables fit its geometry; 0 on allocation failure. */
static int rz_hd_ready(HD_SLOT *d) {
    LONG i;
    if (d->valid && d->kw == d->w && d->kh == d->h && d->kdw == d->dw && d->kdh == d->dh && d->kf == g_hs_filter) return 1;
    d->valid = 0;
    if (d->capn < d->w * d->h) {
        free(d->cur); free(d->prev);
        d->cur = (WORD *)malloc((size_t)d->w * d->h * 2); d->prev = (WORD *)malloc((size_t)d->w * d->h * 2);
        d->capn = d->cur && d->prev ? d->w * d->h : 0;
    }
    if (d->capo < d->dw * d->dh) {
        free(d->out);
        d->out = (WORD *)malloc((size_t)d->dw * d->dh * 2);
        d->capo = d->out ? d->dw * d->dh : 0;
    }
    if (d->capt < d->dw + d->dh) {
        free(d->xs);
        d->xs = (LONG *)malloc((size_t)(d->dw + d->dh) * sizeof(LONG));
        d->capt = d->xs ? d->dw + d->dh : 0;
    }
    if (!d->capn || !d->capo || !d->capt) { d->capn = d->capo = d->capt = 0; return 0; }
    d->ys = d->xs + d->dw;
    for (i = 0; i < d->dw + d->dh; i++) {   /* source of dest pixel j: (j + 0.5) * n / dn - 0.5 */
        int isx = i < d->dw;
        LONG n = isx ? d->w : d->h, dn = isx ? d->dw : d->dh, j = isx ? i : i - d->dw, bb, f;
        double u = (j + 0.5) * n / dn - 0.5;
        if (!g_hs_filter) { bb = (LONG)((j + 0.5) * n / dn); if (bb > n - 1) bb = n - 1; f = 0; }
        else {
            if (u < 0) u = 0;
            bb = (LONG)u; f = (LONG)((u - bb) * 256.0 + 0.5);
            if (bb >= n - 1) { bb = n - 1; f = 0; }
        }
        d->xs[i] = (bb << 9) | f;   /* f is 0..256: 9 bits */
    }
    d->kw = d->w; d->kh = d->h; d->kdw = d->dw; d->kdh = d->dh; d->kf = g_hs_filter;
    return 1;
}

/* DLGSCALE: enlarge one dialog from its native pixels (d->cur) into the frame. Only the dest box fed by the source
   pixels that differ from the last frame is recomputed into the cache; the whole cache is then copied to the frame. */
static void rz_hd_draw(HD_SLOT *d, BYTE *bits, LONG pitch, LONG ox, LONG oy, int g6) {
    LONG x0 = d->w, x1 = -1, y0 = d->h, y1 = -1, x, y, dx0, dx1, dy0, dy1;
    WORD *t;
    if (!d->valid) { x0 = 0; y0 = 0; x1 = d->w - 1; y1 = d->h - 1; g_hd_full++; }
    else
        for (y = 0; y < d->h; y++) {
            const WORD *a = d->cur + y * d->w, *p = d->prev + y * d->w;
            LONG l = 0, rr = d->w - 1;
            if (!memcmp(a, p, d->w * 2)) continue;
            while (a[l] == p[l]) l++;
            while (a[rr] == p[rr]) rr--;
            if (l < x0) x0 = l;
            if (rr > x1) x1 = rr;
            if (y < y0) y0 = y;
            y1 = y;
        }
    if (x1 >= x0) {   /* dest pixels whose taps (b, b + 1) can reach source [x0, x1] x [y0, y1] */
        dx0 = (LONG)((double)(x0 - 1) * d->dw / d->w) - 1; dx1 = (LONG)((double)(x1 + 2) * d->dw / d->w) + 2;
        dy0 = (LONG)((double)(y0 - 1) * d->dh / d->h) - 1; dy1 = (LONG)((double)(y1 + 2) * d->dh / d->h) + 2;
        if (dx0 < 0) dx0 = 0;
        if (dy0 < 0) dy0 = 0;
        if (dx1 > d->dw) dx1 = d->dw;
        if (dy1 > d->dh) dy1 = d->dh;
        for (y = dy0; y < dy1; y++) {
            LONG yb = d->ys[y] >> 9, fy = d->ys[y] & 511, yb1 = yb + 1 < d->h ? yb + 1 : yb;
            const WORD *r0 = d->cur + yb * d->w, *r1 = d->cur + yb1 * d->w;
            WORD *o = d->out + y * d->dw;
            if (!g_hs_filter) for (x = dx0; x < dx1; x++) o[x] = r0[d->xs[x] >> 9];
            else
                for (x = dx0; x < dx1; x++) {
                    LONG xb = d->xs[x] >> 9, fx = d->xs[x] & 511, xb1 = xb + 1 < d->w ? xb + 1 : xb;
                    WORD a = fx ? rz_hs_lerp(r0[xb], r0[xb1], fx, g6) : r0[xb];
                    WORD c = fx ? rz_hs_lerp(r1[xb], r1[xb1], fx, g6) : r1[xb];
                    o[x] = fy ? rz_hs_lerp(a, c, fy, g6) : a;
                }
        }
        g_hd_px += (DWORD)((dx1 - dx0) * (dy1 - dy0));
    }
    d->valid = 1;
    t = d->prev; d->prev = d->cur; d->cur = t;   /* this frame's pixels are the next frame's "last" */
    for (y = 0; y < d->dh; y++)
        memcpy((WORD *)(bits + (oy + d->dst[1] + y) * pitch) + ox + d->dst[0], d->out + y * d->dw, d->dw * 2);
}

/* Is this ddraw surface the primary (DDSCAPS_PRIMARYSURFACE 0x200, GetCaps = vt+0x38)? Per frame the game Blts the
 * city layer into its composite with a client-sized dest too (measured 2026-10-11, HSSEQ in verify/hudfix/), and only
 * the composite -> primary Blt is the present. Cached per pointer. -1 = GetCaps failed. */
static int rz_hs_is_screen(void *self) {
    static void *last; static int last_r;
    DWORD caps[4] = {0, 0, 0, 0};
    if (self == last) return last_r;
    if (!self || IsBadReadPtr(self, 4) || IsBadReadPtr(*(DWORD **)self, 0x3c)) return -1;
    if (((HRESULT (WINAPI *)(void *, DWORD *))(*(DWORD **)self)[0x38 / 4])(self, caps)) return -1;
    last = self; last_r = (caps[0] & 0x200) ? 1 : 0;
    return last_r;
}

/* Diag (SC3RESIZE_HUDSCALE_DUMP): write cw x ch 16-bit rows of a surface to <prefix><tag>.raw. */
static void rz_hs_dumpraw(const char *tag, const BYTE *bits, LONG pitch, LONG ox, LONG oy, LONG cw, LONG ch) {
    char path[MAX_PATH + 32];
    HANDLE h;
    LONG y;
    DWORD wr;
    wsprintfA(path, "%s%s_%ldx%ld.raw", g_hs_dump, tag, cw, ch);
    h = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
    if (h == INVALID_HANDLE_VALUE) return;
    for (y = 0; y < ch; y++) WriteFile(h, bits + (oy + y) * pitch + ox * 2, (DWORD)cw * 2, &wr, NULL);
    CloseHandle(h);
    logf("HUDSCALE> dumped %s", path);
}

/* HUDFIX: record a Blt onto the composite (called from rz_blt_hook for every Blt while HUDSCALE is on). The frame's
 * client-sized Blt onto the composite (the city layer) starts a new list. */
static void rz_hs_record(void *self, const RECT *dr, void *src, const RECT *sr, DWORD fl, const void *fx, LONG cw, LONG ch) {
    HS_REC *r;
    if (!g_hudfix || !g_hs_comp || self != g_hs_comp || !dr || IsBadReadPtr(dr, sizeof(RECT))) return;
    if (dr->left <= 0 && dr->top <= 0 && dr->right >= cw && dr->bottom >= ch) { g_hs_nrec = 0; g_hs_recover = 0; return; }
    if (g_hs_nrec >= HS_REC_MAX) { g_hs_recover = 1; return; }
    r = &g_hs_rec[g_hs_nrec];
    r->d[0] = dr->left; r->d[1] = dr->top; r->d[2] = dr->right; r->d[3] = dr->bottom;
    r->src = src; r->fl = fl; r->klo = r->khi = 0;
    if (sr && !IsBadReadPtr(sr, sizeof(RECT))) { r->s[0] = sr->left; r->s[1] = sr->top; r->s[2] = sr->right; r->s[3] = sr->bottom; }
    else { r->s[0] = 0; r->s[1] = 0; r->s[2] = dr->right - dr->left; r->s[3] = dr->bottom - dr->top; }
    if (fl & 0x400) r->kind = 0;                                        /* DDBLT_COLORFILL: solid */
    else if (fl & 0x10000) {                                            /* DDBLT_KEYSRCOVERRIDE: key in DDBLTFX+0x5c */
        if (fx && !IsBadReadPtr(fx, 0x64)) { r->klo = ((const DWORD *)fx)[0x5c / 4]; r->khi = ((const DWORD *)fx)[0x60 / 4]; r->kind = 1; }
        else r->kind = 2;
    } else if (fl & 0x8000) {                                           /* DDBLT_KEYSRC: the source surface's key */
        DWORD ck[2] = {0, 0};
        r->kind = 2;
        if (src && !IsBadReadPtr(src, 4) && !IsBadReadPtr(*(DWORD **)src, 0x44) &&
            !((HRESULT (WINAPI *)(void *, DWORD, DWORD *))(*(DWORD **)src)[0x40 / 4])(src, 8 /* DDCKEY_SRCBLT */, ck)) {
            r->klo = ck[0]; r->khi = ck[1]; r->kind = 1;
        }
    } else r->kind = 0;
    if (!src && !(fl & 0x400)) r->kind = 2;
    g_hs_nrec++;
}

/* HUDFIX: g_hs_cov over the HUD rects (+1 margin): 0 = not HUD (margin), 1 = HUD rect, no recorded Blt covers it
 * (equality fallback), 2 = covered by a recorded Blt (HUD). */
static void rz_hs_coverage(int n, LONG cw, LONG ch, int recs_ok) {
    int i, k;
    LONG y, x;
    for (i = 0; i < n; i++) {
        LONG x0 = max(g_hs_src[i][0] - 1, 0), x1 = min(g_hs_src[i][2] + 1, cw), y0 = max(g_hs_src[i][1] - 1, 0), y1 = min(g_hs_src[i][3] + 1, ch);
        if (x1 > x0) for (y = y0; y < y1; y++) memset(g_hs_cov + y * cw + x0, 0, x1 - x0);
    }
    for (i = 0; i < n; i++) {
        LONG x0 = max(g_hs_src[i][0], 0), x1 = min(g_hs_src[i][2], cw), y0 = max(g_hs_src[i][1], 0), y1 = min(g_hs_src[i][3], ch);
        if (x1 > x0) for (y = y0; y < y1; y++) memset(g_hs_cov + y * cw + x0, 1, x1 - x0);
    }
    if (!recs_ok) { g_hsd_fallback++; return; }
    for (k = 0; k < g_hs_nrec; k++) {
        const HS_REC *r = &g_hs_rec[k];
        LONG x0 = max(r->d[0], 0), x1 = min(r->d[2], cw), y0 = max(r->d[1], 0), y1 = min(r->d[3], ch);
        LONG dw = r->d[2] - r->d[0], dh = r->d[3] - r->d[1], sw2 = r->s[2] - r->s[0], sh2 = r->s[3] - r->s[1];
        int hit = 0;
        if (x1 <= x0 || y1 <= y0 || dw <= 0 || dh <= 0 || r->kind == 2) continue;
        for (i = 0; i < n && !hit; i++)
            hit = x0 < g_hs_src[i][2] && x1 > g_hs_src[i][0] && y0 < g_hs_src[i][3] && y1 > g_hs_src[i][1];
        if (!hit) continue;
        g_hsd_recs++;
        if (r->kind == 0) {
            for (y = y0; y < y1; y++) { BYTE *c = g_hs_cov + y * cw; for (x = x0; x < x1; x++) if (c[x]) c[x] = 2; }
        } else {
            LONG pt, ssw, ssh; DWORD bpp, gm;
            BYTE *sb;
            if (!r->src || r->src == g_hs_comp || sw2 <= 0 || sh2 <= 0) continue;
            sb = rz_hs_lock(r->src, &pt, &bpp, &gm, &ssw, &ssh);
            if (!sb) continue;
            if (bpp == 16 && r->s[0] >= 0 && r->s[1] >= 0 && r->s[2] <= ssw && r->s[3] <= ssh)
                for (y = y0; y < y1; y++) {
                    BYTE *c = g_hs_cov + y * cw;
                    const WORD *srow = (const WORD *)(sb + (r->s[1] + (y - r->d[1]) * sh2 / dh) * pt);
                    for (x = x0; x < x1; x++) {
                        DWORD v;
                        if (!c[x]) continue;
                        v = srow[r->s[0] + (x - r->d[0]) * sw2 / dw];
                        if (v < r->klo || v > r->khi) c[x] = 2;
                    }
                }
            ((RZ_UNLOCK)(*(DWORD **)r->src)[0x80 / 4])(r->src, NULL);
        }
    }
}

/* HUDFIX: is native pixel (px,py) HUD? */
/* HUDFIX: settle the fallback pixels once per frame (cov 1 -> 2 if the pixel differs from the city layer, else 0), so
 * the per-tap test below is one byte read. */
static void rz_hs_resolve(int n, LONG cw, LONG ch, const BYTE *city, LONG cpitch) {
    int i;
    LONG x, y;
    for (i = 0; i < n; i++) {
        LONG x0 = max(g_hs_src[i][0] - 1, 0), x1 = min(g_hs_src[i][2] + 1, cw), y0 = max(g_hs_src[i][1] - 1, 0), y1 = min(g_hs_src[i][3] + 1, ch);
        for (y = y0; y < y1; y++) {
            BYTE *c = g_hs_cov + y * cw;
            const WORD *sn = g_hs_snap + y * cw, *ct = (const WORD *)(city + y * cpitch);
            for (x = x0; x < x1; x++) if (c[x] == 1) c[x] = sn[x] != ct[x] ? 2 : 0;
        }
    }
}

/* HUDFIX: is native pixel (px,py) HUD? (after rz_hs_resolve) */
static __inline int rz_hs_hud(LONG px, LONG py, LONG cw, const BYTE *city, LONG cpitch) {
    (void)city; (void)cpitch;
    return g_hs_cov[py * cw + px] == 2;
}

static WORD rz_hs_tent3(WORD a, WORD b, WORD c, int g6) {   /* (a + 2b + c) / 4 per channel */
    LONG r, g, bl;
    if (g6) {
        r = ((a >> 11) + 2 * (b >> 11) + (c >> 11) + 2) >> 2;
        g = (((a >> 5) & 63) + 2 * ((b >> 5) & 63) + ((c >> 5) & 63) + 2) >> 2;
        bl = ((a & 31) + 2 * (b & 31) + (c & 31) + 2) >> 2;
        return (WORD)((r << 11) | (g << 5) | bl);
    }
    r = (((a >> 10) & 31) + 2 * ((b >> 10) & 31) + ((c >> 10) & 31) + 2) >> 2;
    g = (((a >> 5) & 31) + 2 * ((b >> 5) & 31) + ((c >> 5) & 31) + 2) >> 2;
    bl = ((a & 31) + 2 * (b & 31) + (c & 31) + 2) >> 2;
    return (WORD)((r << 10) | (g << 5) | bl);
}
static WORD *g_hs_x2t;
static LONG  g_hs_x2tcap;

/* HUDFIX: Scale2x (EPX) of the snapshot region r (native, clipped) into g_hs_x2 (2w x 2h). */
static WORD *g_hs_epxkey;        /* the snapshot region the 2x buffer was built from (skip the rebuild when unchanged) */
static BYTE *g_hs_epxcov;
static LONG  g_hs_epxr[4], g_hs_epxcap;
static int   g_hs_epxg6 = -1;
static int g_hp_mask;   /* fwd: HUDPERF MASK (defined with rz_hp_rowdiff) */
static int rz_hp_rowdiff(const WORD *old, const WORD *now, LONG y, LONG x0, LONG n, LONG cw, LONG ch, LONG *lo, LONG *hi);
/* The minimap 2x buffer for native rows [y0, y1] of r (relative), as the full build does it: Scale2x of each row (reads
   rows -1..+1), the horizontal tent on those 2x rows, the vertical tent on the 2x rows one wider (reads 2x rows -1..+1).
   INCREMENTAL (task cityzoom, owner 2026-10-22: FPS while moving): the minimap's view box moves every frame while the
   camera does, and every change rebuilt the whole buffer (1.3 ms at 3.3x); now the changed rows +-2 are rebuilt. */
static void rz_hs_epx_rows(const LONG *r, LONG cw, int g6, LONG y0, LONG y1) {
    LONG w = r[2] - r[0], h = r[3] - r[1], x, y, W = 2 * w, H = 2 * h, a0, a1;
    if (y0 < 0) y0 = 0;
    if (y1 > h - 1) y1 = h - 1;
    for (y = y0; y <= y1; y++) {
        const WORD *row = g_hs_snap + (r[1] + y) * cw + r[0];
        const WORD *up = y > 0 ? row - cw : row, *dn = y < h - 1 ? row + cw : row;
        WORD *o0 = g_hs_x2 + (2 * y) * (2 * w), *o1 = o0 + 2 * w;
        for (x = 0; x < w; x++) {
            WORD P = row[x], A = up[x], D = dn[x], C = x > 0 ? row[x - 1] : P, B = x < w - 1 ? row[x + 1] : P;
            o0[2 * x]     = (C == A && C != D && A != B) ? A : P;
            o0[2 * x + 1] = (A == B && A != C && B != D) ? B : P;
            o1[2 * x]     = (D == C && D != B && C != A) ? C : P;
            o1[2 * x + 1] = (B == D && B != A && D != C) ? D : P;
        }
    }
    /* then one [1 2 1] tent in 2x space (about half a native pixel of blur), horizontal then vertical, taking only HUD
       neighbours (a non-HUD neighbour counts as the centre), so no city is mixed into the picture */
    if (g_hs_x2tcap < 4 * w * h) {
        free(g_hs_x2t);
        g_hs_x2t = (WORD *)malloc((size_t)4 * w * h * 2);
        g_hs_x2tcap = g_hs_x2t ? 4 * w * h : 0;
        if (g_hs_x2t) { y0 = 0; y1 = h - 1; }   /* a fresh tent buffer: everything */
    }
    if (g_hs_x2t) {
        a0 = 2 * y0; a1 = 2 * y1 + 1;
        for (y = a0; y <= a1; y++) {
            const BYTE *cv = g_hs_cov + (r[1] + y / 2) * cw + r[0];
            const WORD *in = g_hs_x2 + y * W;
            WORD *o = g_hs_x2t + y * W;
            for (x = 0; x < W; x++) {
                WORD c = in[x], l, rr;
                if (cv[x / 2] != 2) { o[x] = c; continue; }
                l = x > 0 && cv[(x - 1) / 2] == 2 ? in[x - 1] : c;
                rr = x < W - 1 && cv[(x + 1) / 2] == 2 ? in[x + 1] : c;
                o[x] = rz_hs_tent3(l, c, rr, g6);
            }
        }
        a0 = a0 > 0 ? a0 - 1 : 0; a1 = a1 < H - 1 ? a1 + 1 : H - 1;
        for (y = a0; y <= a1; y++) {
            const BYTE *cv = g_hs_cov + (r[1] + y / 2) * cw + r[0];
            const BYTE *cu = y > 0 ? g_hs_cov + (r[1] + (y - 1) / 2) * cw + r[0] : NULL;
            const BYTE *cdn = y < H - 1 ? g_hs_cov + (r[1] + (y + 1) / 2) * cw + r[0] : NULL;
            const WORD *in = g_hs_x2t + y * W;
            WORD *o = g_hs_x2 + y * W;
            for (x = 0; x < W; x++) {
                WORD c = in[x], u, dn;
                if (cv[x / 2] != 2) { o[x] = c; continue; }
                u = cu && cu[x / 2] == 2 ? in[x - W] : c;
                dn = cdn && cdn[x / 2] == 2 ? in[x + W] : c;
                o[x] = rz_hs_tent3(u, c, dn, g6);
            }
        }
    }
}
static int g_hs_epxinc = 1;   /* SC3RESIZE_HUDSCALE_EPXINC=0: rebuild the whole minimap 2x buffer on any change */
static DWORD g_hpd_epxrows;
static int g_hs_epxcheck;     /* SC3RESIZE_HUDSCALE_EPXCHECK=1: after each incremental rebuild, a full one, compared */
static DWORD g_hpd_epxchk, g_hpd_epxdiff;
static int rz_hs_epx(const LONG *r, LONG cw, int g6) {
    LONG w = r[2] - r[0], h = r[3] - r[1], y, clo = -1, chi = -1;
    int geo;
    if (w <= 0 || h <= 0) return 0;
    if (g_hs_epxcap < w * h) {
        free(g_hs_epxkey); free(g_hs_epxcov);
        g_hs_epxkey = (WORD *)malloc((size_t)w * h * 2); g_hs_epxcov = (BYTE *)malloc((size_t)w * h);
        g_hs_epxcap = g_hs_epxkey && g_hs_epxcov ? w * h : 0;
        g_hs_epxr[2] = -1;
    }
    geo = g_hs_epxcap >= w * h && g_hs_x2 && g_hs_x2cap >= 4 * w * h && g6 == g_hs_epxg6 && !memcmp(g_hs_epxr, r, sizeof(g_hs_epxr));
    if (geo) {   /* the native rows that changed (MASK: snapshot changes only where a 2x pixel can read them) */
        for (y = 0; y < h; y++) {
            WORD *kr = g_hs_epxkey + y * w;
            BYTE *kc = g_hs_epxcov + y * w;
            const WORD *sr = g_hs_snap + (r[1] + y) * cw + r[0];
            const BYTE *cr = g_hs_cov + (r[1] + y) * cw + r[0];
            LONG lo, hi;
            int ch_ = memcmp(kc, cr, w) != 0;
            if (!ch_ && memcmp(kr, sr, w * 2))
                ch_ = !g_hp_mask || rz_hp_rowdiff(kr, sr, r[1] + y, r[0], w, cw, g_hs_covcap / cw, &lo, &hi);
            memcpy(kr, sr, w * 2); memcpy(kc, cr, w);
            if (ch_) { if (clo < 0) clo = y; chi = y; }
        }
        if (clo < 0) return 1;
        if (g_hs_epxinc) {
            rz_hs_epx_rows(r, cw, g6, clo - 2, chi + 2); g_hpd_epxrows += (DWORD)(chi - clo + 5);
            if (g_hs_epxcheck) {
                static WORD *cp; static LONG cpcap;
                LONG k, n4 = 4 * w * h, d = 0;
                if (cpcap < n4) { free(cp); cp = (WORD *)malloc((size_t)n4 * 2); cpcap = cp ? n4 : 0; }
                if (cp) {
                    memcpy(cp, g_hs_x2, (size_t)n4 * 2);
                    rz_hs_epx_rows(r, cw, g6, 0, h - 1);
                    for (k = 0; k < n4; k++) {   /* only 2x pixels a reader can see: their native pixel is HUD (cov 2) */
                        LONG X = k % (2 * w), Y = k / (2 * w);
                        if (cp[k] != g_hs_x2[k] && g_hs_cov[(r[1] + Y / 2) * cw + r[0] + X / 2] == 2) d++;
                    }
                    g_hpd_epxchk++; g_hpd_epxdiff += (DWORD)d;
                    if (d && g_hpd_epxdiff == (DWORD)d) logf("EPXCHECK> first difference: %ld px (rows %ld..%ld changed)", d, clo, chi);
                    if ((g_hpd_epxchk & 255) == 0) logf("EPXCHECK> %lu incremental rebuilds checked, %lu px differed", g_hpd_epxchk, g_hpd_epxdiff);
                }
            }
            return 1;
        }
    } else if (g_hs_epxcap >= w * h) {
        for (y = 0; y < h; y++) {
            memcpy(g_hs_epxkey + y * w, g_hs_snap + (r[1] + y) * cw + r[0], w * 2);
            memcpy(g_hs_epxcov + y * w, g_hs_cov + (r[1] + y) * cw + r[0], w);
        }
        memcpy(g_hs_epxr, r, sizeof(g_hs_epxr)); g_hs_epxg6 = g6;
    }
    if (g_hs_x2cap < 4 * w * h) {
        free(g_hs_x2);
        g_hs_x2 = (WORD *)malloc((size_t)4 * w * h * 2);
        g_hs_x2cap = g_hs_x2 ? 4 * w * h : 0;
        if (!g_hs_x2) return 0;
    }
    rz_hs_epx_rows(r, cw, g6, 0, h - 1);
    g_hpd_epxrows += (DWORD)h;
    return 1;
}

/* HUDFIX: bilinear of four 16-bit taps in one pass (fx, fy 0..256). */
static __inline WORD rz_hs_blend4(WORD a, WORD b, WORD c, WORD d, LONG fx, LONG fy, int g6) {
    LONG w0 = (256 - fx) * (256 - fy), w1 = fx * (256 - fy), w2 = (256 - fx) * fy, w3 = fx * fy, r, g, bl;
    if (g6) {
        r  = ((a >> 11) * w0 + (b >> 11) * w1 + (c >> 11) * w2 + (d >> 11) * w3 + 32768) >> 16;
        g  = (((a >> 5) & 63) * w0 + ((b >> 5) & 63) * w1 + ((c >> 5) & 63) * w2 + ((d >> 5) & 63) * w3 + 32768) >> 16;
        bl = ((a & 31) * w0 + (b & 31) * w1 + (c & 31) * w2 + (d & 31) * w3 + 32768) >> 16;
        return (WORD)((r << 11) | (g << 5) | bl);
    }
    r  = (((a >> 10) & 31) * w0 + ((b >> 10) & 31) * w1 + ((c >> 10) & 31) * w2 + ((d >> 10) & 31) * w3 + 32768) >> 16;
    g  = (((a >> 5) & 31) * w0 + ((b >> 5) & 31) * w1 + ((c >> 5) & 31) * w2 + ((d >> 5) & 31) * w3 + 32768) >> 16;
    bl = ((a & 31) * w0 + (b & 31) * w1 + (c & 31) * w2 + (d & 31) * w3 + 32768) >> 16;
    return (WORD)((r << 10) | (g << 5) | bl);
}

/* HUDFIX resample of every enlarged rect (the per-frame loop of task hudfix, moved here unchanged by task hudperf so
 * SC3RESIZE_HUDPERF=0 and the HUDPERF self-check run exactly this). Reads only the snapshot, coverage, 2x buffer and
 * city layer, never the frame, and writes every pixel of every dest rect. */
static void rz_hs_resample_fix(int n, BYTE *bits, LONG pitch, LONG ox, LONG oy, LONG cw, LONG ch, const BYTE *city,
                               LONG cpitch, int g6, double s, DWORD sui_base) {
    int i, city_fix = 1;
    for (i = 0; i < n && city && city_fix; i++) {   /* HUDFIX resample: non-HUD taps take the city at the dest */
        const LONG *d = g_hs_dst[i];
        LONG x, y, er[4], w2 = 0, h2 = 0;
        int epx = 0;
        if (g_hs_filter && g_hs_minismooth && sui_base && g_hs_vt[i] == sui_base + 0xaa180 && g_hs_c2cap >= cw + ch) {
            er[0] = max(g_hs_src[i][0] - 1, 0); er[1] = max(g_hs_src[i][1] - 1, 0);
            er[2] = min(g_hs_src[i][2] + 1, cw); er[3] = min(g_hs_src[i][3] + 1, ch);
            { LARGE_INTEGER te; QueryPerformanceCounter(&te); epx = rz_hs_epx(er, cw, g6); rz_hs_tick(3, &te); }
            w2 = 2 * (er[2] - er[0]); h2 = 2 * (er[3] - er[1]);
            if (epx) {   /* per dest column / row: base tap in the 2x buffer and weight */
                for (x = d[0]; x < d[2]; x++) {
                    double u = (double)cw + ((double)x + 0.5 - (double)cw) / s - 0.5, u2 = 2.0 * (u - (double)er[0]) + 0.5;
                    LONG b = (LONG)u2; if ((double)b > u2) b--;
                    g_hs_c2f[x] = (LONG)((u2 - (double)b) * 256.0);
                    if (b < 0) { b = 0; g_hs_c2f[x] = 0; }
                    if (b > w2 - 1) { b = w2 - 1; g_hs_c2f[x] = 0; }
                    g_hs_c2b[x] = b;
                }
                for (y = d[1]; y < d[3]; y++) {
                    double u = (double)ch + ((double)y + 0.5 - (double)ch) / s - 0.5, u2 = 2.0 * (u - (double)er[1]) + 0.5;
                    LONG b = (LONG)u2; if ((double)b > u2) b--;
                    g_hs_c2f[cw + y] = (LONG)((u2 - (double)b) * 256.0);
                    if (b < 0) { b = 0; g_hs_c2f[cw + y] = 0; }
                    if (b > h2 - 1) { b = h2 - 1; g_hs_c2f[cw + y] = 0; }
                    g_hs_c2b[cw + y] = b;
                }
            }
        }
        for (y = d[1]; y < d[3]; y++) {
            WORD *f = (WORD *)(bits + (oy + y) * pitch) + ox;
            const WORD *cd = (const WORD *)(city + y * cpitch);
            if (!g_hs_filter) {
                LONG sy = g_hs_ys[y];
                const WORD *srow = g_hs_snap + sy * cw;
                for (x = d[0]; x < d[2]; x++) { LONG sx = g_hs_xs[x]; f[x] = rz_hs_hud(sx, sy, cw, city, cpitch) ? srow[sx] : cd[x]; }
            } else if (epx) {
                LONG b0 = g_hs_c2b[cw + y], b1 = b0 + 1 < h2 ? b0 + 1 : b0, fy = g_hs_c2f[cw + y];
                const BYTE *c0 = g_hs_cov + (er[1] + b0 / 2) * cw + er[0], *c1 = g_hs_cov + (er[1] + b1 / 2) * cw + er[0];
                const WORD *r0 = g_hs_x2 + b0 * w2, *r1 = g_hs_x2 + b1 * w2;
                for (x = d[0]; x < d[2]; x++) {
                    LONG a0 = g_hs_c2b[x], a1 = a0 + 1 < w2 ? a0 + 1 : a0, fx = g_hs_c2f[x];
                    int h00 = c0[a0 >> 1] == 2, h01 = c0[a1 >> 1] == 2, h10 = c1[a0 >> 1] == 2, h11 = c1[a1 >> 1] == 2;
                    WORD c = cd[x];
                    if (h00 & h01 & h10 & h11) f[x] = rz_hs_blend4(r0[a0], r0[a1], r1[a0], r1[a1], fx, fy, g6);
                    else if (!(h00 | h01 | h10 | h11)) f[x] = c;
                    else f[x] = rz_hs_blend4(h00 ? r0[a0] : c, h01 ? r0[a1] : c, h10 ? r1[a0] : c, h11 ? r1[a1] : c, fx, fy, g6);
                }
            } else {
                LONG yb = g_hs_yf[y] & 0xfffff, fy = (g_hs_yf[y] >> 20) & 0x1ff, yb1 = yb + 1 < ch ? yb + 1 : yb;
                const WORD *r0 = g_hs_snap + yb * cw, *r1 = g_hs_snap + yb1 * cw;
                const BYTE *c0 = g_hs_cov + yb * cw, *c1 = g_hs_cov + yb1 * cw;
                for (x = d[0]; x < d[2]; x++) {
                    LONG xb = g_hs_xf[x] & 0xfffff, fx = (g_hs_xf[x] >> 20) & 0x1ff, xb1 = xb + 1 < cw ? xb + 1 : xb;
                    int h00 = c0[xb] == 2, h01 = c0[xb1] == 2, h10 = c1[xb] == 2, h11 = c1[xb1] == 2;
                    WORD c = cd[x];
                    if (h00 & h01 & h10 & h11) f[x] = rz_hs_blend4(r0[xb], r0[xb1], r1[xb], r1[xb1], fx, fy, g6);
                    else if (!(h00 | h01 | h10 | h11)) f[x] = c;
                    else f[x] = rz_hs_blend4(h00 ? r0[xb] : c, h01 ? r0[xb1] : c, h10 ? r1[xb] : c, h11 ? r1[xb1] : c, fx, fy, g6);
                }
            }
        }
    }
}

/* HUDPERF (task hudperf 2026-10-12, re/analysis/HUD_SCALE.md "Cost of the enlarged HUD"). SC3RESIZE_HUDPERF=0 = the
 * hudfix pass above, every pixel resampled every frame.
 * Every dest pixel of the HUDFIX resample is one of three kinds, decided only by the coverage of its source taps:
 *   all taps HUD  -> a value from the snapshot (or the minimap 2x buffer) alone,
 *   no tap HUD    -> the city layer at the dest pixel,
 *   some taps HUD -> a blend of the two (edges of see-through parts).
 * The first kind does not depend on the city, so it is kept per window in a dest-sized cache, and recomputed only
 * where the window's snapshot or coverage changed since the frame it was built from (each window keeps its own copy
 * of both over its source rect + 1 px, so a changed native pixel marks only the dest pixels whose taps can reach it,
 * +-4 native px around it). Per frame each dest row is a run list: cached runs and city runs are memcpy'd, mixed
 * pixels are recomputed with the same arithmetic as the hudfix pass (rz_hp_px), so the frame is bit-identical.
 * SC3RESIZE_HUDPERF_CHECK=1 runs both every frame and logs any pixel that differs (the old result is what shows). */
static int    g_hudperf = 1, g_hp_check;
typedef struct { LONG x0, x1, t; } HP_RUN;              /* t: 0 city at the dest, 1 cached, 2 mixed (recomputed) */
typedef struct {
    int     live, valid, mode, flt;                     /* mode 0 nearest, 1 bilinear, 2 minimap 2x + bilinear */
    DWORD   vt, last;
    LONG    src[4], dst[4], er[4];
    WORD   *ksnap; BYTE *kcov; LONG kcap, kccap;        /* snapshot + coverage over er when the cache was last built */
    WORD   *img;   BYTE *cls;  LONG icap, clcap;        /* dest-sized: cached values and the kind of each pixel */
    HP_RUN **rrow; LONG *rn, *rcap, rowcap;             /* per dest row: runs (x0, x1 relative to the dest rect's left) */
} HP_SLOT;
typedef struct { int mode, g6; LONG cw, ch, w2, h2; const LONG *er; } HP_CTX;
static HP_SLOT g_hp[HS_MAX];
static LONG    g_hp_gk[3]; static double g_hp_gs;
static DWORD   g_hp_frame;
static WORD   *g_hp_chk; static LONG g_hp_chkcap;
static DWORD   g_hpd_masked;   /* rows whose only snapshot changes no cached value reads (MASK) */
static DWORD   g_hpd_px, g_hpd_mixed, g_hpd_full, g_hpd_part, g_hpd_frames, g_hpd_chkf, g_hpd_diff, g_hpd_diffpx, g_hpd_fail, g_hpd_diflog;
static __int64 g_hpd_comp, g_hpd_post, g_hpd_postlock, g_hpd_chkt, g_hpd_prelock, g_hpd_cityblt;
static DWORD   g_hpd_citybn;
static ULONG64 g_hpd_cyc, g_hpd_cycpost;   /* thread cycles in the pass / the restore (not inflated by preemption) */
/* is the copy rect m (as rz_hs_copy clips it) inside d? Then copying d alone copies it too. */
static int rz_hp_inside(const LONG *m, const LONG *d, LONG cw) {
    LONG x0 = m[0] < 0 ? 0 : m[0], x1 = m[2] > cw ? cw : m[2];
    if (x1 <= x0 || m[3] <= m[1]) return 1;
    return x0 >= d[0] && x1 <= d[2] && m[1] >= d[1] && m[3] <= d[3];
}
static void rz_hp_cyc(ULONG64 *c) {   /* QueryThreadCycleTime (Vista+, resolved at run time: the build targets 0x0501) */
    static BOOL (WINAPI *q)(HANDLE, ULONG64 *);
    static int tried;
    if (!tried) { tried = 1; q = (BOOL (WINAPI *)(HANDLE, ULONG64 *))GetProcAddress(GetModuleHandleA("kernel32.dll"), "QueryThreadCycleTime"); }
    *c = 0;
    if (q) q(GetCurrentThread(), c);
}
static DWORD   g_hpd_lzskip, g_hpd_lzlate[5], g_hpd_lzdrop;   /* LAZYRESTORE counters (block after rz_hs_post) */

/* One dest pixel of the hudfix resample, same arithmetic as rz_hs_resample_fix. c = the city at the dest pixel.
 * *cl: 1 = every tap is HUD (c unused), 0 = no tap is HUD (returns c), 2 = mixed. */
static __inline WORD rz_hp_px(const HP_CTX *k, LONG x, LONG y, WORD c, int *cl) {
    LONG cw = k->cw;
    int h00, h01, h10, h11;
    if (k->mode == 0) {
        LONG sx = g_hs_xs[x], sy = g_hs_ys[y];
        if (g_hs_cov[sy * cw + sx] == 2) { *cl = 1; return g_hs_snap[sy * cw + sx]; }
        *cl = 0; return c;
    }
    if (k->mode == 2) {
        LONG b0 = g_hs_c2b[cw + y], b1 = b0 + 1 < k->h2 ? b0 + 1 : b0, fy = g_hs_c2f[cw + y], w2 = k->w2;
        const BYTE *c0 = g_hs_cov + (k->er[1] + b0 / 2) * cw + k->er[0], *c1 = g_hs_cov + (k->er[1] + b1 / 2) * cw + k->er[0];
        const WORD *r0 = g_hs_x2 + b0 * w2, *r1 = g_hs_x2 + b1 * w2;
        LONG a0 = g_hs_c2b[x], a1 = a0 + 1 < w2 ? a0 + 1 : a0, fx = g_hs_c2f[x];
        h00 = c0[a0 >> 1] == 2; h01 = c0[a1 >> 1] == 2; h10 = c1[a0 >> 1] == 2; h11 = c1[a1 >> 1] == 2;
        if (h00 & h01 & h10 & h11) { *cl = 1; return rz_hs_blend4(r0[a0], r0[a1], r1[a0], r1[a1], fx, fy, k->g6); }
        if (!(h00 | h01 | h10 | h11)) { *cl = 0; return c; }
        *cl = 2;
        return rz_hs_blend4(h00 ? r0[a0] : c, h01 ? r0[a1] : c, h10 ? r1[a0] : c, h11 ? r1[a1] : c, fx, fy, k->g6);
    } else {
        LONG yb = g_hs_yf[y] & 0xfffff, fy = (g_hs_yf[y] >> 20) & 0x1ff, yb1 = yb + 1 < k->ch ? yb + 1 : yb;
        const WORD *r0 = g_hs_snap + yb * cw, *r1 = g_hs_snap + yb1 * cw;
        const BYTE *c0 = g_hs_cov + yb * cw, *c1 = g_hs_cov + yb1 * cw;
        LONG xb = g_hs_xf[x] & 0xfffff, fx = (g_hs_xf[x] >> 20) & 0x1ff, xb1 = xb + 1 < cw ? xb + 1 : xb;
        h00 = c0[xb] == 2; h01 = c0[xb1] == 2; h10 = c1[xb] == 2; h11 = c1[xb1] == 2;
        if (h00 & h01 & h10 & h11) { *cl = 1; return rz_hs_blend4(r0[xb], r0[xb1], r1[xb], r1[xb1], fx, fy, k->g6); }
        if (!(h00 | h01 | h10 | h11)) { *cl = 0; return c; }
        *cl = 2;
        return rz_hs_blend4(h00 ? r0[xb] : c, h01 ? r0[xb1] : c, h10 ? r1[xb] : c, h11 ? r1[xb1] : c, fx, fy, k->g6);
    }
}

/* HUDPERF MASK (task cityzoom, owner 2026-10-22: FPS while moving). A snapshot pixel is read only where its coverage is
   2 (HUD) - rz_hp_px in all three modes - and the minimap's 2x path also reads its 4 neighbours (rz_hs_epx). So a changed
   snapshot pixel that is neither HUD nor next to one (the city showing through a see-through HUD part, changing every
   frame while the camera moves) cannot change any cached value: it no longer triggers a rebuild. Bit-identical.
   Returns 1 and the first/last relevant column (relative to x0) when something relevant changed on native row y.
   SC3RESIZE_HUDPERF_MASK=0 compares every pixel as before. */
static int g_hp_mask = 1;
static int rz_hp_rowdiff(const WORD *old, const WORD *now, LONG y, LONG x0, LONG n, LONG cw, LONG ch, LONG *lo, LONG *hi) {
    const BYTE *c = g_hs_cov + y * cw, *cu = y > 0 ? c - cw : c, *cd = y < ch - 1 ? c + cw : c;
    LONG x, a = -1, b = -1;
    for (x = 0; x < n; x++) {
        LONG gx = x0 + x;
        if (old[x] == now[x]) continue;
        if (c[gx] == 2 || cu[gx] == 2 || cd[gx] == 2 || (gx > 0 && c[gx - 1] == 2) || (gx < cw - 1 && c[gx + 1] == 2)) {
            if (a < 0) a = x;
            b = x;
        }
    }
    if (a < 0) return 0;
    *lo = a; *hi = b;
    return 1;
}

/* grow *p to hold n elements of sz bytes; 0 on failure (the old block is kept) */
static int rz_hp_grow(void **p, LONG *cap, LONG n, size_t sz) {
    void *q;
    if (*cap >= n) return 1;
    q = realloc(*p, (size_t)n * sz);
    if (!q) return 0;
    *p = q; *cap = n;
    return 1;
}

/* per-slot run lists, one array per dest row (so a change re-scans only its own rows) */
static int rz_hp_rows(HP_SLOT *p, LONG dh) {
    HP_RUN **a;
    LONG *b, *c;
    if (p->rowcap >= dh) return 1;
    a = (HP_RUN **)realloc(p->rrow, (size_t)dh * sizeof(HP_RUN *));
    if (!a) return 0;
    p->rrow = a;
    b = (LONG *)realloc(p->rn, (size_t)dh * sizeof(LONG));
    if (!b) return 0;
    p->rn = b;
    c = (LONG *)realloc(p->rcap, (size_t)dh * sizeof(LONG));
    if (!c) return 0;
    p->rcap = c;
    memset(p->rrow + p->rowcap, 0, (size_t)(dh - p->rowcap) * sizeof(HP_RUN *));
    memset(p->rn + p->rowcap, 0, (size_t)(dh - p->rowcap) * sizeof(LONG));
    memset(p->rcap + p->rowcap, 0, (size_t)(dh - p->rowcap) * sizeof(LONG));
    p->rowcap = dh;
    return 1;
}
static int rz_hp_runs(HP_SLOT *p, LONG r, LONG dw) {
    const BYTE *cl = p->cls + r * dw;
    LONG x = 0, nr = 0;
    while (x < dw) {
        LONG x1 = x + 1;
        BYTE t = cl[x];
        while (x1 < dw && cl[x1] == t) x1++;
        if (nr >= p->rcap[r]) {
            LONG nc = p->rcap[r] ? p->rcap[r] * 2 : 8;
            HP_RUN *q = (HP_RUN *)realloc(p->rrow[r], (size_t)nc * sizeof(HP_RUN));
            if (!q) return 0;
            p->rrow[r] = q; p->rcap[r] = nc;
        }
        p->rrow[r][nr].x0 = x; p->rrow[r][nr].x1 = x1; p->rrow[r][nr].t = t;
        nr++;
        x = x1;
    }
    p->rn[r] = nr;
    return 1;
}
static LONG *g_hp_dlo, *g_hp_dhi, g_hp_dlocap, g_hp_dhicap;
/* HUDPERF MT (task cityzoom, owner 2026-10-22: FPS while moving): the dest pixels to rebuild in one window, rows split in
   bands over the CITYZOOM worker threads when there are 20,000 or more (each row is independent: rz_hp_px only reads,
   rz_hp_runs only touches its own row). SC3RESIZE_HUDPERF_MT=0 rebuilds on the game thread. */
static int g_hp_mt = 1;
typedef struct { HP_SLOT *p; const HP_CTX *k; const LONG *d; LONG dw, y0, y1; DWORD px; int fail; } HP_BAND;
static void rz_hp_band(void *arg) {
    HP_BAND *b = (HP_BAND *)arg;
    LONG x, y;
    for (y = b->y0; y < b->y1; y++) {
        LONG a = g_hp_dlo[y], e = g_hp_dhi[y];
        WORD *im;
        BYTE *cl;
        if (e <= a) continue;
        im = b->p->img + (y - b->d[1]) * b->dw;
        cl = b->p->cls + (y - b->d[1]) * b->dw;
        for (x = a; x < e; x++) { int c; im[x - b->d[0]] = rz_hp_px(b->k, x, y, 0, &c); cl[x - b->d[0]] = (BYTE)c; }
        b->px += (DWORD)(e - a);
        if (!rz_hp_runs(b->p, y - b->d[1], b->dw)) b->fail = 1;
    }
}

/* The HUDFIX resample through the per-window caches. Returns 0 if a buffer could not be allocated: the caller then runs
 * rz_hs_resample_fix, which rewrites every dest pixel without reading the frame, so a half-done pass does no harm. */
static int rz_hp_compose(int n, BYTE *bits, LONG pitch, LONG ox, LONG oy, LONG cw, LONG ch, const BYTE *city,
                         LONG cpitch, int g6, double s, DWORD sui_base) {
    int i, j;
    LONG gk[3];
    gk[0] = cw; gk[1] = ch; gk[2] = g6 | (g_hs_filter ? 2 : 0) | (g_hs_minismooth ? 4 : 0);
    if (memcmp(gk, g_hp_gk, sizeof(gk)) || s != g_hp_gs) {
        for (j = 0; j < HS_MAX; j++) g_hp[j].valid = 0;
        memcpy(g_hp_gk, gk, sizeof(gk)); g_hp_gs = s;
    }
    if (!rz_hp_grow((void **)&g_hp_dlo, &g_hp_dlocap, ch, sizeof(LONG)) || !rz_hp_grow((void **)&g_hp_dhi, &g_hp_dhicap, ch, sizeof(LONG)))
        return 0;
    g_hp_frame++;
    for (j = 0; j < HS_MAX; j++) g_hp[j].live = 0;
    for (i = 0; i < n; i++) {
        HP_SLOT *p = NULL;
        HP_CTX k;
        const LONG *d = g_hs_dst[i];
        LONG er[4], x, y, w2 = 0, h2 = 0, dw = d[2] - d[0], dh = d[3] - d[1], kw, kh;
        int mode, epx = 0, full, any;
        /* this window's slot from the last frame (same class and rects), else the least recently used one */
        for (j = 0; j < HS_MAX && !p; j++)
            if (!g_hp[j].live && g_hp[j].valid && g_hp[j].vt == g_hs_vt[i] && g_hp[j].flt == g_hs_float[i] &&
                !memcmp(g_hp[j].src, g_hs_src[i], sizeof(g_hp[j].src)) && !memcmp(g_hp[j].dst, d, sizeof(g_hp[j].dst)))
                p = &g_hp[j];
        if (!p) {
            for (j = 0; j < HS_MAX; j++) if (!g_hp[j].live && (!p || g_hp[j].last < p->last)) p = &g_hp[j];
            p->valid = 0; p->vt = g_hs_vt[i]; p->flt = g_hs_float[i];
            memcpy(p->src, g_hs_src[i], sizeof(p->src)); memcpy(p->dst, d, sizeof(p->dst));
        }
        p->live = 1; p->last = g_hp_frame;
        if (dw <= 0 || dh <= 0) continue;
        er[0] = max(g_hs_src[i][0] - 1, 0); er[1] = max(g_hs_src[i][1] - 1, 0);
        er[2] = min(g_hs_src[i][2] + 1, cw); er[3] = min(g_hs_src[i][3] + 1, ch);
        mode = g_hs_filter ? 1 : 0;
        if (g_hs_filter && g_hs_minismooth && sui_base && g_hs_vt[i] == sui_base + 0xaa180 && g_hs_c2cap >= cw + ch) {
            { LARGE_INTEGER te; QueryPerformanceCounter(&te); epx = rz_hs_epx(er, cw, g6); rz_hs_tick(3, &te); }
            w2 = 2 * (er[2] - er[0]); h2 = 2 * (er[3] - er[1]);
            if (epx) {   /* per dest column / row: base tap in the 2x buffer and weight (as rz_hs_resample_fix) */
                mode = 2;
                for (x = d[0]; x < d[2]; x++) {
                    double u = (double)cw + ((double)x + 0.5 - (double)cw) / s - 0.5, u2 = 2.0 * (u - (double)er[0]) + 0.5;
                    LONG b = (LONG)u2; if ((double)b > u2) b--;
                    g_hs_c2f[x] = (LONG)((u2 - (double)b) * 256.0);
                    if (b < 0) { b = 0; g_hs_c2f[x] = 0; }
                    if (b > w2 - 1) { b = w2 - 1; g_hs_c2f[x] = 0; }
                    g_hs_c2b[x] = b;
                }
                for (y = d[1]; y < d[3]; y++) {
                    double u = (double)ch + ((double)y + 0.5 - (double)ch) / s - 0.5, u2 = 2.0 * (u - (double)er[1]) + 0.5;
                    LONG b = (LONG)u2; if ((double)b > u2) b--;
                    g_hs_c2f[cw + y] = (LONG)((u2 - (double)b) * 256.0);
                    if (b < 0) { b = 0; g_hs_c2f[cw + y] = 0; }
                    if (b > h2 - 1) { b = h2 - 1; g_hs_c2f[cw + y] = 0; }
                    g_hs_c2b[cw + y] = b;
                }
            }
        }
        if (p->mode != mode || memcmp(p->er, er, sizeof(er))) p->valid = 0;
        p->mode = mode; memcpy(p->er, er, sizeof(er));
        kw = er[2] - er[0]; kh = er[3] - er[1];
        if (kw <= 0 || kh <= 0) { p->valid = 0; return 0; }
        if (p->kcap < kw * kh || p->kccap < kw * kh || p->icap < dw * dh || p->clcap < dw * dh || p->rowcap < dh) p->valid = 0;
        if (!rz_hp_grow((void **)&p->ksnap, &p->kcap, kw * kh, 2) || !rz_hp_grow((void **)&p->kcov, &p->kccap, kw * kh, 1) ||
            !rz_hp_grow((void **)&p->img, &p->icap, dw * dh, 2) || !rz_hp_grow((void **)&p->cls, &p->clcap, dw * dh, 1) ||
            !rz_hp_rows(p, dh)) { p->valid = 0; return 0; }
        full = !p->valid;
        any = full;
        for (y = d[1]; y < d[3]; y++) { g_hp_dlo[y] = full ? d[0] : 0x7fffffff; g_hp_dhi[y] = full ? d[2] : -1; }
        /* what changed in this window's source taps since its cache was built: per changed native row, the dest
           pixels whose taps (bilinear +-1, 2x path +-2 native) can reach it, with room (+-4) */
        for (y = er[1]; y < er[3]; y++) {
            WORD *ks = p->ksnap + (y - er[1]) * kw;
            BYTE *kc = p->kcov + (y - er[1]) * kw;
            const WORD *sn = g_hs_snap + y * cw + er[0];
            const BYTE *cv = g_hs_cov + y * cw + er[0];
            if (!full) {
                LONG lo, hi, ry0, ry1, rx0, rx1, r;
                int covsame = !memcmp(kc, cv, kw);
                if (covsame && !memcmp(ks, sn, kw * 2)) continue;
                if (covsame && g_hp_mask) {   /* MASK: only changes a cached value can see */
                    if (!rz_hp_rowdiff(ks, sn, y, er[0], kw, cw, ch, &lo, &hi)) { memcpy(ks, sn, kw * 2); g_hpd_masked++; continue; }
                } else {
                    for (lo = 0; lo < kw && ks[lo] == sn[lo] && kc[lo] == cv[lo]; lo++) ;
                    for (hi = kw - 1; hi > lo && ks[hi] == sn[hi] && kc[hi] == cv[hi]; hi--) ;
                }
                ry0 = max(rz_hs_dst_lo(y - 4, ch, s), d[1]); ry1 = min(rz_hs_dst_lo(y + 5, ch, s), d[3]);
                rx0 = max(rz_hs_dst_lo(er[0] + lo - 4, cw, s), d[0]); rx1 = min(rz_hs_dst_lo(er[0] + hi + 5, cw, s), d[2]);
                for (r = ry0; r < ry1; r++) {
                    if (rx0 < g_hp_dlo[r]) g_hp_dlo[r] = rx0;
                    if (rx1 > g_hp_dhi[r]) g_hp_dhi[r] = rx1;
                }
                any = 1;
            }
            memcpy(ks, sn, kw * 2); memcpy(kc, cv, kw);
        }
        k.mode = mode; k.g6 = g6; k.cw = cw; k.ch = ch; k.w2 = w2; k.h2 = h2; k.er = p->er;
        if (any) {
            HP_BAND bd[CZ_THREADS];
            LONG tot = 0, nb, q;
            if (full) g_hpd_full++; else g_hpd_part++;
            for (y = d[1]; y < d[3]; y++) if (g_hp_dhi[y] > g_hp_dlo[y]) tot += g_hp_dhi[y] - g_hp_dlo[y];
            nb = g_hp_mt && tot >= 20000 ? cz_pool_size() : 1;
            for (q = 0; q < nb; q++) {   /* bands of about equal pixel counts */
                bd[q].p = p; bd[q].k = &k; bd[q].d = d; bd[q].dw = dw; bd[q].px = 0; bd[q].fail = 0;
            }
            if (nb <= 1) { bd[0].y0 = d[1]; bd[0].y1 = d[3]; rz_hp_band(&bd[0]); }
            else {
                LONG acc = 0, cut = 1;
                void *args[CZ_THREADS];
                bd[0].y0 = d[1];
                for (y = d[1]; y < d[3] && cut < nb; y++) {
                    if (g_hp_dhi[y] > g_hp_dlo[y]) acc += g_hp_dhi[y] - g_hp_dlo[y];
                    if (acc >= tot * cut / nb) { bd[cut - 1].y1 = y + 1; bd[cut].y0 = y + 1; cut++; }
                }
                for (; cut < nb; cut++) { bd[cut - 1].y1 = d[3]; bd[cut].y0 = d[3]; }
                bd[nb - 1].y1 = d[3];
                for (q = 0; q < nb; q++) args[q] = &bd[q];
                cz_pool_run(rz_hp_band, args, (int)nb);
            }
            for (q = 0; q < nb; q++) { g_hpd_px += bd[q].px; if (bd[q].fail) { p->valid = 0; return 0; } }
        }
        p->valid = 1;
        for (y = d[1]; y < d[3]; y++) {   /* the frame: cached runs, city runs, mixed pixels */
            WORD *f = (WORD *)(bits + (oy + y) * pitch) + ox + d[0];
            const WORD *cd = (const WORD *)(city + y * cpitch) + d[0];
            const WORD *im = p->img + (y - d[1]) * dw;
            const HP_RUN *r = p->rrow[y - d[1]], *re = r + p->rn[y - d[1]];
            for (; r < re; r++) {
                if (r->t == 1) memcpy(f + r->x0, im + r->x0, (r->x1 - r->x0) * 2);
                else if (r->t == 0) memcpy(f + r->x0, cd + r->x0, (r->x1 - r->x0) * 2);
                else { int c; for (x = r->x0; x < r->x1; x++) f[x] = rz_hp_px(&k, d[0] + x, y, cd[x], &c); g_hpd_mixed += r->x1 - r->x0; }
            }
        }
    }
    return 1;
}

/* HUDPERF: rz_hs_coverage with the same result inside every HUD rect + 1 px (the only part anything reads). An opaque
 * Blt sets 2 on its intersection with each HUD rect (inside a HUD rect the old "if nonzero" test is always true), a
 * keyed Blt reads its source 1:1 without a divide per pixel when it is not stretched. */
static void rz_hp_coverage(int n, LONG cw, LONG ch, int recs_ok) {
    int i, k;
    LONG y, x;
    for (i = 0; i < n; i++) {
        LONG x0 = max(g_hs_src[i][0] - 1, 0), x1 = min(g_hs_src[i][2] + 1, cw), y0 = max(g_hs_src[i][1] - 1, 0), y1 = min(g_hs_src[i][3] + 1, ch);
        if (x1 > x0) for (y = y0; y < y1; y++) memset(g_hs_cov + y * cw + x0, 0, x1 - x0);
    }
    for (i = 0; i < n; i++) {
        LONG x0 = max(g_hs_src[i][0], 0), x1 = min(g_hs_src[i][2], cw), y0 = max(g_hs_src[i][1], 0), y1 = min(g_hs_src[i][3], ch);
        if (x1 > x0) for (y = y0; y < y1; y++) memset(g_hs_cov + y * cw + x0, 1, x1 - x0);
    }
    if (!recs_ok) { g_hsd_fallback++; return; }
    for (k = 0; k < g_hs_nrec; k++) {
        const HS_REC *r = &g_hs_rec[k];
        LONG x0 = max(r->d[0], 0), x1 = min(r->d[2], cw), y0 = max(r->d[1], 0), y1 = min(r->d[3], ch);
        LONG dw = r->d[2] - r->d[0], dh = r->d[3] - r->d[1], sw2 = r->s[2] - r->s[0], sh2 = r->s[3] - r->s[1];
        int hit = 0;
        if (x1 <= x0 || y1 <= y0 || dw <= 0 || dh <= 0 || r->kind == 2) continue;
        for (i = 0; i < n && !hit; i++)
            hit = x0 < g_hs_src[i][2] && x1 > g_hs_src[i][0] && y0 < g_hs_src[i][3] && y1 > g_hs_src[i][1];
        if (!hit) continue;
        g_hsd_recs++;
        if (r->kind == 0) {
            for (i = 0; i < n; i++) {
                LONG a0 = max(x0, max(g_hs_src[i][0], 0)), a1 = min(x1, min(g_hs_src[i][2], cw));
                LONG b0 = max(y0, max(g_hs_src[i][1], 0)), b1 = min(y1, min(g_hs_src[i][3], ch));
                if (a1 > a0) for (y = b0; y < b1; y++) memset(g_hs_cov + y * cw + a0, 2, a1 - a0);
            }
        } else {
            LONG pt, ssw, ssh; DWORD bpp, gm;
            BYTE *sb;
            if (!r->src || r->src == g_hs_comp || sw2 <= 0 || sh2 <= 0) continue;
            sb = rz_hs_lock(r->src, &pt, &bpp, &gm, &ssw, &ssh);
            if (!sb) continue;
            if (bpp == 16 && r->s[0] >= 0 && r->s[1] >= 0 && r->s[2] <= ssw && r->s[3] <= ssh)
                for (i = 0; i < n; i++) {
                    LONG a0 = max(x0, max(g_hs_src[i][0], 0)), a1 = min(x1, min(g_hs_src[i][2], cw));
                    LONG b0 = max(y0, max(g_hs_src[i][1], 0)), b1 = min(y1, min(g_hs_src[i][3], ch));
                    if (a1 <= a0) continue;
                    for (y = b0; y < b1; y++) {
                        BYTE *c = g_hs_cov + y * cw;
                        const WORD *srow = (const WORD *)(sb + (r->s[1] + (y - r->d[1]) * sh2 / dh) * pt);
                        if (sw2 == dw) {
                            const WORD *sp = srow + r->s[0] - r->d[0];
                            for (x = a0; x < a1; x++) { DWORD v = sp[x]; if (v < r->klo || v > r->khi) c[x] = 2; }
                        } else
                            for (x = a0; x < a1; x++) { DWORD v = srow[r->s[0] + (x - r->d[0]) * sw2 / dw]; if (v < r->klo || v > r->khi) c[x] = 2; }
                    }
                }
            ((RZ_UNLOCK)(*(DWORD **)r->src)[0x80 / 4])(r->src, NULL);
        }
    }
}

/* HUDPERF: rz_hs_resolve, skipping to the fallback pixels (cov 1) with memchr. */
static void rz_hp_resolve(int n, LONG cw, LONG ch, const BYTE *city, LONG cpitch) {
    int i;
    LONG y;
    for (i = 0; i < n; i++) {
        LONG x0 = max(g_hs_src[i][0] - 1, 0), x1 = min(g_hs_src[i][2] + 1, cw), y0 = max(g_hs_src[i][1] - 1, 0), y1 = min(g_hs_src[i][3] + 1, ch);
        if (x1 <= x0) continue;
        for (y = y0; y < y1; y++) {
            BYTE *c = g_hs_cov + y * cw, *q;
            const WORD *sn = g_hs_snap + y * cw, *ct = (const WORD *)(city + y * cpitch);
            LONG x = x0;
            while (x < x1 && (q = (BYTE *)memchr(c + x, 1, x1 - x)) != NULL) {
                x = (LONG)(q - c);
                c[x] = sn[x] != ct[x] ? 2 : 0;
                x++;
            }
        }
    }
}

/* HUDPERF_CHECK: the coverage the old functions give, compared inside every HUD rect + 1 px. */
static BYTE  *g_hp_chkcov;
static LONG   g_hp_chkcovcap;
static DWORD  g_hpd_covdiff, g_hpd_covdifff;
static void rz_hp_check_cov(int n, LONG cw, LONG ch, int recs_ok, const BYTE *city, LONG cpitch) {
    int i;
    LONG y, x, diff = 0;
    DWORD sr = g_hsd_recs, sf = g_hsd_fallback;
    if (!rz_hp_grow((void **)&g_hp_chkcov, &g_hp_chkcovcap, cw * ch, 1)) return;
    for (i = 0; i < n; i++) {
        LONG x0 = max(g_hs_src[i][0] - 1, 0), x1 = min(g_hs_src[i][2] + 1, cw), y0 = max(g_hs_src[i][1] - 1, 0), y1 = min(g_hs_src[i][3] + 1, ch);
        if (x1 > x0) for (y = y0; y < y1; y++) memcpy(g_hp_chkcov + y * cw + x0, g_hs_cov + y * cw + x0, x1 - x0);
    }
    rz_hs_coverage(n, cw, ch, recs_ok);
    rz_hs_resolve(n, cw, ch, city, cpitch);
    g_hsd_recs = sr; g_hsd_fallback = sf;
    for (i = 0; i < n; i++) {
        LONG x0 = max(g_hs_src[i][0] - 1, 0), x1 = min(g_hs_src[i][2] + 1, cw), y0 = max(g_hs_src[i][1] - 1, 0), y1 = min(g_hs_src[i][3] + 1, ch);
        for (y = y0; y < y1; y++)
            for (x = x0; x < x1; x++)
                if (g_hp_chkcov[y * cw + x] != g_hs_cov[y * cw + x]) diff++;
    }
    if (diff) { g_hpd_covdifff++; g_hpd_covdiff += diff; }
}

/* HUDPERF_CHECK: keep the composed dest rects, run the hudfix pass over them, count the pixels that differ. */
static void rz_hp_check(int n, BYTE *bits, LONG pitch, LONG ox, LONG oy, LONG cw, LONG ch, const BYTE *city,
                        LONG cpitch, int g6, double s, DWORD sui_base) {
    int i;
    LONG x, y, diff = 0;
    if (!rz_hp_grow((void **)&g_hp_chk, &g_hp_chkcap, cw * ch, 2)) return;
    for (i = 0; i < n; i++)
        for (y = g_hs_dst[i][1]; y < g_hs_dst[i][3]; y++)
            memcpy(g_hp_chk + y * cw + g_hs_dst[i][0], (WORD *)(bits + (oy + y) * pitch) + ox + g_hs_dst[i][0],
                   (g_hs_dst[i][2] - g_hs_dst[i][0]) * 2);
    rz_hs_resample_fix(n, bits, pitch, ox, oy, cw, ch, city, cpitch, g6, s, sui_base);
    for (i = 0; i < n; i++)
        for (y = g_hs_dst[i][1]; y < g_hs_dst[i][3]; y++) {
            const WORD *f = (const WORD *)(bits + (oy + y) * pitch) + ox, *c = g_hp_chk + y * cw;
            for (x = g_hs_dst[i][0]; x < g_hs_dst[i][2]; x++)
                if (f[x] != c[x]) {
                    if (g_hpd_diflog < 20) { g_hpd_diflog++; logf("HUDPERF> CHECK differs at (%ld,%ld) in [%ld %ld %ld %ld]: cached 0x%04X, hudfix 0x%04X",
                                                                    x, y, g_hs_dst[i][0], g_hs_dst[i][1], g_hs_dst[i][2], g_hs_dst[i][3], c[x], f[x]); }
                    diff++;
                }
        }
    g_hpd_chkf++;
    if (diff) { g_hpd_diff++; g_hpd_diffpx += diff; }
}

/* task cityzoom SKIP: per dest row, the HUD-only (cached, t == 1) runs of the live HUDPERF slots, merged, minus the
   native HUD rects (+-2 px). Called after a HUD pass that composed through HUDPERF. */
static void cz_build_skip(int n, LONG cw, LONG ch) {
    LONG y, tmp[128], nt, k, i, j, tot = 0;
    g_cz_skok = 0;
    if (!g_cz_skipon || g_cz_f <= 1 || !g_hudperf || cw <= 0 || ch <= 0) return;
    if (g_cz_skocap < ch + 1) {
        free(g_cz_sko); g_cz_sko = (LONG *)malloc((ch + 1) * sizeof(LONG)); g_cz_skocap = g_cz_sko ? ch + 1 : 0;
        if (!g_cz_sko) return;
    }
    for (y = 0; y < ch; y++) {
        g_cz_sko[y] = tot;
        nt = 0;
        for (j = 0; j < HS_MAX; j++) {
            const HP_SLOT *p = &g_hp[j];
            const HP_RUN *r, *re;
            if (!p->live || !p->valid || p->flt || y < p->dst[1] || y >= p->dst[3] || !p->rrow || !p->rn) continue;
            r = p->rrow[y - p->dst[1]]; re = r + p->rn[y - p->dst[1]];
            for (; r < re && nt < 126; r++)
                if (r->t == 1 && r->x1 > r->x0) { tmp[nt++] = p->dst[0] + r->x0; tmp[nt++] = p->dst[0] + r->x1; }
        }
        for (i = 0; i < n; i++) {   /* never skip inside a native HUD rect: split the spans around it */
            const LONG *q = g_hs_src[i];
            LONG a = q[0] - 2, b = q[2] + 2, m;
            if (g_hs_float[i] || y < q[1] - 2 || y >= q[3] + 2) continue;
            for (m = 0; m < nt; m += 2) {
                if (tmp[m + 1] <= a || tmp[m] >= b) continue;
                if (tmp[m] < a && tmp[m + 1] > b && nt < 126) { tmp[nt++] = b; tmp[nt++] = tmp[m + 1]; tmp[m + 1] = a; }
                else if (tmp[m] < a) tmp[m + 1] = a;
                else if (tmp[m + 1] > b) tmp[m] = b;
                else tmp[m + 1] = tmp[m];   /* inside: empty */
            }
        }
        for (i = 2; i < nt; i += 2) {   /* insertion sort by x0 */
            LONG a = tmp[i], b = tmp[i + 1];
            for (k = i - 2; k >= 0 && tmp[k] > a; k -= 2) { tmp[k + 2] = tmp[k]; tmp[k + 3] = tmp[k + 1]; }
            tmp[k + 2] = a; tmp[k + 3] = b;
        }
        if (g_cz_skcap < tot + nt + 2) {
            LONG cap = (tot + nt + 2) * 2 + 4096, *nb = (LONG *)realloc(g_cz_sk, cap * sizeof(LONG));
            if (!nb) return;
            g_cz_sk = nb; g_cz_skcap = cap;
        }
        for (i = 0; i < nt; i += 2) {   /* merge into the row's list, drop empty spans and short ones */
            if (tmp[i + 1] - tmp[i] < 8) continue;
            if (tot > g_cz_sko[y] && tmp[i] <= g_cz_sk[tot - 1]) { if (tmp[i + 1] > g_cz_sk[tot - 1]) g_cz_sk[tot - 1] = tmp[i + 1]; }
            else { g_cz_sk[tot++] = tmp[i]; g_cz_sk[tot++] = tmp[i + 1]; }
        }
    }
    g_cz_sko[ch] = tot;
    g_cz_skw = cw; g_cz_skh = ch; g_cz_skf = g_cz_f; g_cz_skok = 1;
}

/* Before the final present: enlarge the HUD into the frame. Returns 1 when the frame must be restored after. */
static int rz_hs_pre(void *src, const RECT *sr, LONG cw, LONG ch, int self_is_screen) {
    double s, smax;
    int n, i, k, g6, dump, city_fix = 1;
    LONG pitch, sw, sh, ox, oy;
    DWORD bpp, gmask, csub = 0;
    BYTE *bits, *city = NULL;
    LONG cpitch = 0;
    LARGE_INTEGER t0, t1;
    ULONG64 cy0;
    DWORD sui_base = (DWORD)GetModuleHandleA("SIMUI.DLL");
    static int logged_fmt;
    g_hs_n = 0; g_hd_n = 0; g_hs_why = 1;
    g_cz_skok = 0;   /* task cityzoom SKIP: rebuilt below only when this pass composes */
    if (!g_hudscale || g_mb_active || cw <= 0 || ch <= 0) return 0;
    g_hs_why = 2;
    if (sr->right - sr->left != cw || sr->bottom - sr->top != ch) return 0;   /* only a 1:1 present */
    g_hs_why = 3;
    smax = (double)cw / NAT_W < (double)ch / NAT_H ? (double)cw / NAT_W : (double)ch / NAT_H;
    s = g_hudscale >= 100 ? (double)g_hudscale / 100.0 : smax;
    if (s > smax) s = smax;
    {   static LONG lcw, lch; static int lmode = -1;   /* task uiscale: the factor the mode gives at this size */
        if ((cw != lcw || ch != lch || g_hudscale != lmode) && !rz_menu_visible()) {
            lcw = cw; lch = ch; lmode = g_hudscale;
            logf("HUDSCALE> %s: client %ldx%ld -> factor %.3f%s", g_hudscale == 1 ? "Auto" : "fixed percent", cw, ch, s,
                 s < 1.01 ? " (native size)" : "");
        }
    }
    if (s < 1.01) return 0;
    g_hs_why = 4;
    if (rz_menu_visible()) return 0;
    g_hs_why = 5;
    if (!rz_hs_tables(cw, ch, s)) return 0;
    QueryPerformanceCounter(&t0);
    rz_hp_cyc(&cy0);
    if (g_hs_key) city = rz_hs_city(cw, ch, &cpitch, &csub);
    n = rz_hs_collect(cw, ch, s, city != NULL);
    g_hs_why = 6;
    if (n <= 0) { rz_hs_city_unlock(csub); return 0; }
    g_hs_why = 7;
    if (g_hs_snapcap < cw * ch) {
        free(g_hs_snap);
        g_hs_snap = (WORD *)malloc((size_t)cw * ch * 2);
        g_hs_snapcap = g_hs_snap ? cw * ch : 0;
        if (!g_hs_snap) { rz_hs_city_unlock(csub); return 0; }
    }
    { LARGE_INTEGER tl0, tl1; QueryPerformanceCounter(&tl0);
      bits = rz_hs_lock(src, &pitch, &bpp, &gmask, &sw, &sh);
      QueryPerformanceCounter(&tl1); g_hpd_prelock += tl1.QuadPart - tl0.QuadPart; }
    g_hs_why = 8;
    if (!bits) { rz_hs_city_unlock(csub); return 0; }
    g_hs_why = 9;
    ox = sr->left; oy = sr->top;
    if (bpp != 16 || sw < ox + cw || sh < oy + ch || pitch < (ox + cw) * 2) {
        if (!logged_fmt++) logf("HUDSCALE> refused: frame %ldx%ld pitch %ld bpp %lu for client %ldx%ld", sw, sh, pitch, bpp, cw, ch);
        ((RZ_UNLOCK)(*(DWORD **)src)[0x80 / 4])(src, NULL);
        rz_hs_city_unlock(csub);
        return 0;
    }
    g6 = gmask == 0x07E0;
    if (city && g_cz_f > 1) cz_fill_hs(n, cw, ch, gmask);   /* task cityzoom: the stretched city where this pass reads it */
    dump = g_hs_dump[0] && g_hs_frames >= 200 && self_is_screen;
    if (dump) {
        rz_hs_dumpraw("frame_before", bits, pitch, ox, oy, cw, ch);
        if (city) rz_hs_dumpraw("city", city, cpitch, 0, 0, cw, ch);
    }
    for (i = 0; i < n; i++) {   /* snapshot sources (1 px margin for the bilinear taps) and dests */
        LONG m[4];
        m[0] = g_hs_src[i][0] - 1; m[1] = g_hs_src[i][1] - 1; m[2] = g_hs_src[i][2] + 1; m[3] = g_hs_src[i][3] + 1;
        if (m[1] < 0) m[1] = 0;
        if (m[3] > ch) m[3] = ch;
        if (!(g_hudperf && rz_hp_inside(m, g_hs_dst[i], cw))) rz_hs_copy(bits, pitch, ox, oy, cw, m, 1);   /* HUDPERF: not twice */
        rz_hs_copy(bits, pitch, ox, oy, cw, g_hs_dst[i], 1);
    }
    for (k = 0; k < g_hd_nc; k++) {   /* DLGSCALE: the dest is restored after the present; keep the native pixels */
        HD_SLOT *d = &g_hd[g_hd_list[k]];
        LONG y;
        if (!rz_hd_ready(d)) { d->dw = 0; continue; }
        rz_hs_copy(bits, pitch, ox, oy, cw, d->dst, 1);
        for (y = 0; y < d->h; y++)
            memcpy(d->cur + y * d->w, (WORD *)(bits + (oy + d->nat[1] + y) * pitch) + ox + d->nat[0], d->w * 2);
    }
    { LARGE_INTEGER tq = t0; rz_hs_tick(0, &tq); }
    if (city && g_hudfix) {   /* HUDFIX: what the game drew into the composite this frame */
        LARGE_INTEGER tq; QueryPerformanceCounter(&tq);
        if (g_hs_covcap < cw * ch) {
            free(g_hs_cov);
            g_hs_cov = (BYTE *)malloc((size_t)cw * ch);
            g_hs_covcap = g_hs_cov ? cw * ch : 0;
        }
        if (!g_hs_cov) city_fix = 0;
        else if (g_hudperf) {   /* HUDPERF: same coverage, cheaper (CHECK compares it with the functions below) */
            int recs_ok = src == g_hs_comp && !g_hs_recover && g_hs_nrec > 0;
            rz_hp_coverage(n, cw, ch, recs_ok); rz_hs_tick(1, &tq); rz_hp_resolve(n, cw, ch, city, cpitch); rz_hs_tick(2, &tq);
            if (g_hp_check) rz_hp_check_cov(n, cw, ch, recs_ok, city, cpitch);
        }
        else { rz_hs_coverage(n, cw, ch, src == g_hs_comp && !g_hs_recover && g_hs_nrec > 0); rz_hs_tick(1, &tq); rz_hs_resolve(n, cw, ch, city, cpitch); rz_hs_tick(2, &tq); }
        if (g_hs_c2cap < cw + ch) {
            free(g_hs_c2b); free(g_hs_c2f);
            g_hs_c2b = (LONG *)malloc((size_t)(cw + ch) * sizeof(LONG)); g_hs_c2f = (LONG *)malloc((size_t)(cw + ch) * sizeof(LONG));
            g_hs_c2cap = g_hs_c2b && g_hs_c2f ? cw + ch : 0;
        }
    } else city_fix = 0;
    if (city)   /* erase floating windows' native copies with the city underneath (the enlarged pass below may cover parts) */
        for (i = 0; i < n; i++) {
            LONG x, y;
            if (!g_hs_float[i]) continue;
            for (y = g_hs_src[i][1]; y < g_hs_src[i][3]; y++) {
                WORD *f = (WORD *)(bits + (oy + y) * pitch) + ox;
                const WORD *cd = (const WORD *)(city + y * cpitch);
                for (x = g_hs_src[i][0]; x < g_hs_src[i][2]; x++) f[x] = cd[x];
            }
        }
    if (city)   /* DLGSCALE: a dialog shifted to fit can leave part of its native copy outside the enlarged one */
        for (k = 0; k < g_hd_nc; k++) {
            const HD_SLOT *d = &g_hd[g_hd_list[k]];
            LONG x, y;
            if (!d->dw) continue;
            for (y = d->nat[1]; y < d->nat[3]; y++) {
                WORD *f = (WORD *)(bits + (oy + y) * pitch) + ox;
                const WORD *cd = (const WORD *)(city + y * cpitch);
                int iny = y >= d->dst[1] && y < d->dst[3];
                for (x = d->nat[0]; x < d->nat[2]; x++)
                    if (!iny || x < d->dst[0] || x >= d->dst[2]) f[x] = cd[x];
            }
        }
    if (city && city_fix) {   /* HUDFIX resample (HUDPERF: through the per-window caches) */
        LARGE_INTEGER tc;
        QueryPerformanceCounter(&tc);
        if (!g_hudperf || !rz_hp_compose(n, bits, pitch, ox, oy, cw, ch, city, cpitch, g6, s, sui_base)) {
            if (g_hudperf) g_hpd_fail++;
            rz_hs_resample_fix(n, bits, pitch, ox, oy, cw, ch, city, cpitch, g6, s, sui_base);
        } else if (g_cz_f > 1 && !g_hp_check) cz_build_skip(n, cw, ch);   /* task cityzoom SKIP */
        else if (g_hp_check) {
            LARGE_INTEGER tk;
            QueryPerformanceCounter(&tk); g_hpd_comp += tk.QuadPart - tc.QuadPart; tc = tk;
            rz_hp_check(n, bits, pitch, ox, oy, cw, ch, city, cpitch, g6, s, sui_base);
            QueryPerformanceCounter(&tk); g_hpd_chkt += tk.QuadPart - tc.QuadPart; tc = tk;
        }
        if (!g_hp_check || !g_hudperf) { LARGE_INTEGER tk; QueryPerformanceCounter(&tk); g_hpd_comp += tk.QuadPart - tc.QuadPart; }
        g_hpd_frames++;
    }
    for (i = 0; i < n && !(city && city_fix); i++) {
        const LONG *d = g_hs_dst[i];
        LONG x, y;
        for (y = d[1]; y < d[3]; y++) {
            WORD *f = (WORD *)(bits + (oy + y) * pitch) + ox;
            if (city) {   /* masked: a source pixel equal to the city layer is see-through -> the city at the dest */
                const WORD *srow = g_hs_snap + g_hs_ys[y] * cw;
                const WORD *crow = (const WORD *)(city + g_hs_ys[y] * cpitch), *cd = (const WORD *)(city + y * cpitch);
                if (!g_hs_filter) {
                    for (x = d[0]; x < d[2]; x++) { LONG sx = g_hs_xs[x]; f[x] = srow[sx] == crow[sx] ? cd[x] : srow[sx]; }
                } else {
                    LONG yb = g_hs_yf[y] & 0xfffff, fy = (g_hs_yf[y] >> 20) & 0x1ff, yb1 = yb + 1 < ch ? yb + 1 : yb;
                    const WORD *r0 = g_hs_snap + yb * cw, *r1 = g_hs_snap + yb1 * cw;
                    for (x = d[0]; x < d[2]; x++) {
                        LONG sx = g_hs_xs[x], xb, fx, xb1;
                        if (srow[sx] == crow[sx]) { f[x] = cd[x]; continue; }
                        xb = g_hs_xf[x] & 0xfffff; fx = (g_hs_xf[x] >> 20) & 0x1ff; xb1 = xb + 1 < cw ? xb + 1 : xb;
                        f[x] = rz_hs_lerp(rz_hs_lerp(r0[xb], r0[xb1], fx, g6), rz_hs_lerp(r1[xb], r1[xb1], fx, g6), fy, g6);
                    }
                }
            } else if (!g_hs_filter) {
                const WORD *srow = g_hs_snap + g_hs_ys[y] * cw;
                for (x = d[0]; x < d[2]; x++) f[x] = srow[g_hs_xs[x]];
            } else {
                LONG yb = g_hs_yf[y] & 0xfffff, fy = (g_hs_yf[y] >> 20) & 0x1ff, yb1 = yb + 1 < ch ? yb + 1 : yb;
                const WORD *r0 = g_hs_snap + yb * cw, *r1 = g_hs_snap + yb1 * cw;
                for (x = d[0]; x < d[2]; x++) {
                    LONG xb = g_hs_xf[x] & 0xfffff, fx = (g_hs_xf[x] >> 20) & 0x1ff, xb1 = xb + 1 < cw ? xb + 1 : xb;
                    f[x] = rz_hs_lerp(rz_hs_lerp(r0[xb], r0[xb1], fx, g6), rz_hs_lerp(r1[xb], r1[xb1], fx, g6), fy, g6);
                }
            }
        }
    }
    for (k = 0; k < g_hs_ndlg; k++)   /* dialogs stay native and on top */
        for (i = 0; i < n; i++) {
            LONG q[4];
            q[0] = max(g_hs_dlg[k][0], g_hs_dst[i][0]); q[1] = max(g_hs_dlg[k][1], g_hs_dst[i][1]);
            q[2] = min(g_hs_dlg[k][2], g_hs_dst[i][2]); q[3] = min(g_hs_dlg[k][3], g_hs_dst[i][3]);
            if (q[2] > q[0] && q[3] > q[1]) rz_hs_copy(bits, pitch, ox, oy, cw, q, 0);
        }
    {   int nd = 0, pass;   /* DLGSCALE: enlarged dialogs on top of everything. The root's child list is FRONT-first (owner
                               2026-10-23: Reunirse, opened first, was drawn over Preferencias, opened later; the log listed
                               Preferencias first), so dialogs are drawn from the back of the list; the floating cost label
                               (lbl) stays last, in list order. The mouse picks the last drawn match, so it follows. */
        for (pass = 0; pass < 2; pass++)
        for (k = 0; k < g_hd_nc; k++) {
            HD_SLOT *d = &g_hd[g_hd_list[pass ? k : g_hd_nc - 1 - k]];
            if (!d->dw || (int)(d->lbl != 0) != pass) continue;
            rz_hd_draw(d, bits, pitch, ox, oy, g6);
            memcpy(g_hd_pdst[nd], d->dst, sizeof(d->dst)); memcpy(g_hd_pnat[nd], d->nat, sizeof(d->nat));
            g_hd_plbl[nd] = d->lbl;   /* task uiscale */
            g_hd_pslot[nd] = (int)(d - g_hd); nd++;
        }
        g_hd_n = nd;
        if (nd) g_hd_frames++;
    }
    if (dump) { rz_hs_dumpraw("frame_after", bits, pitch, ox, oy, cw, ch); g_hs_dump[0] = 0; }
    ((RZ_UNLOCK)(*(DWORD **)src)[0x80 / 4])(src, NULL);
    rz_hs_city_unlock(csub);
    g_hs_cw = cw; g_hs_ch = ch; g_hs_s = s;
    g_hs_n = n; g_hs_why = 0;
    QueryPerformanceCounter(&t1);
    g_hs_time += t1.QuadPart - t0.QuadPart; g_hs_frames++;
    { ULONG64 cy1; rz_hp_cyc(&cy1); g_hpd_cyc += cy1 - cy0; }
    if (!g_hs_beat) g_hs_beat = GetTickCount();
    if (GetTickCount() - g_hs_beat >= 10000 && g_hs_frames) {
        if (g_hudfix && g_hs_diag && g_freq.QuadPart)
            logf("HUDSCALE> stages ms/frame: lock+snapshot %.2f coverage %.2f resolve %.2f minimap2x %.2f",
                 1000.0 * g_hst[0] / g_freq.QuadPart / g_hs_frames, 1000.0 * g_hst[1] / g_freq.QuadPart / g_hs_frames,
                 1000.0 * g_hst[2] / g_freq.QuadPart / g_hs_frames, 1000.0 * g_hst[3] / g_freq.QuadPart / g_hs_frames);
        memset(g_hst, 0, sizeof(g_hst));
        logf("HUDSCALE> %lu enlarged frames in %lu ms, %.2f ms per frame in the pre-present pass%s; HUDFIX: %lu recorded HUD Blts used, %lu frame(s) on the equality fallback",
             g_hs_frames, GetTickCount() - g_hs_beat,
             g_freq.QuadPart ? 1000.0 * (double)g_hs_time / (double)g_freq.QuadPart / g_hs_frames : 0.0, city ? " (masked)" : "",
             g_hsd_recs, g_hsd_fallback);
        if (g_hpd_frames && g_freq.QuadPart) {   /* HUDPERF: the resample share of the pass, the restore after the present */
            logf("HUDPERF> %s: frame lock %.2f, resample %.2f ms/frame, restore %.2f ms/frame (lock %.2f); rebuilt %lu px/frame (%lu full, %lu partial window rebuilds), mixed %lu px/frame%s",
                 g_hudperf ? "on" : "off (SC3RESIZE_HUDPERF=0)", 1000.0 * (double)g_hpd_prelock / (double)g_freq.QuadPart / g_hpd_frames,
                 1000.0 * (double)g_hpd_comp / (double)g_freq.QuadPart / g_hpd_frames,
                 1000.0 * (double)g_hpd_post / (double)g_freq.QuadPart / g_hpd_frames,
                 1000.0 * (double)g_hpd_postlock / (double)g_freq.QuadPart / g_hpd_frames, g_hpd_px / g_hpd_frames, g_hpd_full, g_hpd_part,
                 g_hpd_mixed / g_hpd_frames, g_hpd_fail ? "; FELL BACK to the hudfix pass on some frames" : "");
            logf("HUDPERF> thread cycles per frame: pass %.2f M, restore %.2f M (%lu frames)", (double)g_hpd_cyc / 1e6 / g_hs_frames,
                 (double)g_hpd_cycpost / 1e6 / g_hs_frames, g_hs_frames);
            g_hpd_cyc = g_hpd_cycpost = 0;
            logf("HUDPERF> city layer -> composite Blt: %lu per 10 s, %.2f ms each; restores owed and cancelled by it %lu, paid late %lu %lu %lu %lu %lu (Blt onto, Blt from, BltFast, Lock, GetDC), dropped %lu",
                 g_hpd_citybn, g_hpd_citybn ? 1000.0 * (double)g_hpd_cityblt / (double)g_freq.QuadPart / g_hpd_citybn : 0.0,
                 g_hpd_lzskip, g_hpd_lzlate[0], g_hpd_lzlate[1], g_hpd_lzlate[2], g_hpd_lzlate[3], g_hpd_lzlate[4], g_hpd_lzdrop);
            g_hpd_lzskip = g_hpd_lzdrop = 0; memset(g_hpd_lzlate, 0, sizeof(g_hpd_lzlate));
            if (g_hp_check)
                logf("HUDPERF> CHECK: %lu frames compared, %lu with a difference, %lu px differ in total (hudfix pass %.2f ms/frame); coverage: %lu frames with a difference, %lu px",
                     g_hpd_chkf, g_hpd_diff, g_hpd_diffpx, 1000.0 * (double)g_hpd_chkt / (double)g_freq.QuadPart / g_hpd_frames,
                     g_hpd_covdifff, g_hpd_covdiff);
        }
        g_hpd_px = g_hpd_mixed = g_hpd_full = g_hpd_part = g_hpd_frames = g_hpd_chkf = g_hpd_diff = g_hpd_diffpx = g_hpd_fail = 0;
        g_hpd_covdiff = g_hpd_covdifff = 0;
        g_hpd_comp = g_hpd_post = g_hpd_postlock = g_hpd_chkt = g_hpd_prelock = g_hpd_cityblt = 0; g_hpd_citybn = 0;
        g_hsd_recs = 0; g_hsd_fallback = 0;
        g_hs_beat = GetTickCount(); g_hs_frames = 0; g_hs_time = 0;
    }
    return 1;
}

/* After the present: give the game its frame back. */
static void rz_hs_post(void *src, const RECT *sr) {
    LONG pitch, sw, sh, i, n = g_hs_n;
    DWORD bpp, gmask;
    LARGE_INTEGER t0, t1;
    ULONG64 cy0, cy1;
    BYTE *bits;
    QueryPerformanceCounter(&t0);
    rz_hp_cyc(&cy0);
    bits = rz_hs_lock(src, &pitch, &bpp, &gmask, &sw, &sh);
    if (!bits) { logf("HUDSCALE> restore lock failed"); return; }
    { LARGE_INTEGER tl; QueryPerformanceCounter(&tl); g_hpd_postlock += tl.QuadPart - t0.QuadPart; }
    if (bpp != 16 || sw < sr->left + g_hs_cw || sh < sr->top + g_hs_ch) {   /* HUDPERF: a late restore must fit the surface */
        static int logged;
        if (!logged++) logf("HUDPERF> restore refused: surface %ldx%ld bpp %lu, frame %ldx%ld at (%ld,%ld)", sw, sh, bpp, g_hs_cw, g_hs_ch, sr->left, sr->top);
        ((RZ_UNLOCK)(*(DWORD **)src)[0x80 / 4])(src, NULL);
        return;
    }
    for (i = n - 1; i >= 0; i--) {
        LONG mm[4];
        mm[0] = g_hs_src[i][0] - 1; mm[1] = g_hs_src[i][1] - 1; mm[2] = g_hs_src[i][2] + 1; mm[3] = g_hs_src[i][3] + 1;
        if (mm[1] < 0) mm[1] = 0;
        if (mm[3] > g_hs_ch) mm[3] = g_hs_ch;
        if (!(g_hudperf && rz_hp_inside(mm, g_hs_dst[i], g_hs_cw))) rz_hs_copy(bits, pitch, sr->left, sr->top, g_hs_cw, mm, 0);
        rz_hs_copy(bits, pitch, sr->left, sr->top, g_hs_cw, g_hs_dst[i], 0);
    }
    for (i = 0; i < g_hd_n; i++) rz_hs_copy(bits, pitch, sr->left, sr->top, g_hs_cw, g_hd_pdst[i], 0);   /* DLGSCALE */
    ((RZ_UNLOCK)(*(DWORD **)src)[0x80 / 4])(src, NULL);
    QueryPerformanceCounter(&t1); g_hpd_post += t1.QuadPart - t0.QuadPart;
    rz_hp_cyc(&cy1); g_hpd_cycpost += cy1 - cy0;
}

/* HUDPERF LAZYRESTORE (task hudperf 2026-10-12). rz_hs_post gives the game its frame back right after the present, and
 * that copy cost 1.7 to 4.3 ms per frame maximized at 225%, with no lock wait (verify/hudperf). But every frame the game
 * first Blts its city layer over the whole composite (measured: one client-sized Blt onto it per present, 313 of 313,
 * 543 of 543, 771 of 771 frames), which overwrites everything the restore would put back. So the restore is owed, not
 * paid: it is paid only if something touches that surface first, i.e. any other Blt or BltFast onto or from it, a Lock
 * or a GetDC of it, or the next present. A full opaque Blt onto it cancels the debt (paid anyway if that Blt fails).
 * The Lock/GetDC/BltFast hooks go on top of whatever is in the shared ddraw vtable, after sc3perf's: sc3perf calls its
 * saved Lock directly for the FPS overlay, which only puts back the overlay pixels it saved before the present, so it
 * must not trigger the restore every frame. SC3RESIZE_HUDPERF_LAZY=0 = restore right after the present, as before. */
static int    g_hp_lazy = 1, g_hp_lzinst, g_hp_lzwait;
static void * volatile g_hp_pend;
static RECT   g_hp_pendsr;
typedef HRESULT (WINAPI *RZ_BLTFAST)(void *, DWORD, DWORD, void *, RECT *, DWORD);
typedef HRESULT (WINAPI *RZ_GETDC)(void *, HDC *);
static RZ_LOCK g_hp_next_lock;
static RZ_BLTFAST g_hp_next_bltfast;
static RZ_GETDC g_hp_next_getdc;

/* pay the owed restore before surf is used (why: 0 Blt onto, 1 Blt from, 2 BltFast, 3 Lock, 4 GetDC) */
static void rz_hp_settle(void *surf, int why) {
    void *p = g_hp_pend;
    if (!p || p != surf) return;
    if (InterlockedCompareExchangePointer((PVOID volatile *)&g_hp_pend, NULL, p) != p) return;
    if (why >= 0 && why < 5) g_hpd_lzlate[why]++;
    rz_hs_post(p, &g_hp_pendsr);
}
static HRESULT WINAPI rz_hp_lock_hook(void *self, RECT *r, void *desc, DWORD fl, HANDLE ev) {
    if (g_czp_on && self == g_czp_frame && !g_cz_instretch) cz_pay(2);   /* task cityzoom DEFER */
    if (g_hp_pend && self == g_hp_pend) rz_hp_settle(self, 3);
    return g_hp_next_lock(self, r, desc, fl, ev);
}
static HRESULT WINAPI rz_hp_bltfast_hook(void *self, DWORD x, DWORD y, void *src, RECT *sr, DWORD t) {
    void *p = g_hp_pend;
    if (g_czp_on && (self == g_czp_frame || src == g_czp_frame)) cz_pay(2);   /* task cityzoom DEFER */
    if (p && (self == p || src == p)) rz_hp_settle(p, 2);
    return g_hp_next_bltfast(self, x, y, src, sr, t);
}
static HRESULT WINAPI rz_hp_getdc_hook(void *self, HDC *dc) {
    if (g_czp_on && self == g_czp_frame) cz_pay(2);   /* task cityzoom DEFER */
    if (g_hp_pend && self == g_hp_pend) rz_hp_settle(self, 4);
    return g_hp_next_getdc(self, dc);
}
/* 1 once the hooks are in. Waits (eager restores meanwhile) until sc3perf, when loaded, has hooked Lock. */
static int rz_hp_lazy_ready(void *surf) {
    DWORD *vt, old, perf = (DWORD)GetModuleHandleA("sc3perf.dll");
    if (g_hp_lzinst) return g_hp_lzinst > 0;
    if (!surf || IsBadReadPtr(surf, 4)) return 0;
    vt = *(DWORD **)surf;
    if (!vt || IsBadReadPtr(vt, 0x84)) return 0;
    if (perf) {
        DWORD e = *(DWORD *)(perf + 0x3c), sz = *(DWORD *)(perf + e + 0x50);
        if (vt[0x64 / 4] < perf || vt[0x64 / 4] >= perf + sz) {
            if (++g_hp_lzwait < 3000) return 0;
            g_hp_lzinst = -1;
            logf("HUDPERF> lazy restore OFF: sc3perf is loaded but its Lock hook never showed up (slot 0x%08lX)", vt[0x64 / 4]);
            return 0;
        }
    }
    if (!VirtualProtect(&vt[0x1c / 4], 0x64 - 0x1c + 4, PAGE_EXECUTE_READWRITE, &old)) { g_hp_lzinst = -1; return 0; }
    g_hp_next_bltfast = (RZ_BLTFAST)vt[0x1c / 4]; vt[0x1c / 4] = (DWORD)rz_hp_bltfast_hook;
    g_hp_next_getdc = (RZ_GETDC)vt[0x44 / 4];     vt[0x44 / 4] = (DWORD)rz_hp_getdc_hook;
    g_hp_next_lock = (RZ_LOCK)vt[0x64 / 4];       vt[0x64 / 4] = (DWORD)rz_hp_lock_hook;
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    g_hp_lzinst = 1;
    logf("HUDPERF> lazy restore on: BltFast/GetDC/Lock hooked on vtable 0x%08lX over 0x%08lX 0x%08lX 0x%08lX%s", (DWORD)vt,
         (DWORD)g_hp_next_bltfast, (DWORD)g_hp_next_getdc, (DWORD)g_hp_next_lock, perf ? " (after sc3perf)" : "");
    return 1;
}
/* does this Blt onto the owed surface overwrite every pixel the restore would put back? */
static int rz_hp_covers(const RECT *dr, DWORD fl) {
    LONG x0 = g_hp_pendsr.left, y0 = g_hp_pendsr.top;
    if (fl & ~(0x01000000 | 0x08000000 | 0x00000200 | 0x00000400)) return 0;   /* only WAIT / DONOTWAIT / ASYNC / COLORFILL */
    if (!dr) return 1;
    if (IsBadReadPtr(dr, sizeof(RECT))) return 0;
    return dr->left <= x0 && dr->top <= y0 && dr->right >= x0 + g_hs_cw && dr->bottom >= y0 + g_hs_ch;
}

/* Map a client mouse point through the inverse of the enlargement. Returns 1 if it changed lp. */
static int rz_hs_mouse(UINT m, LPARAM *lp) {
    LONG qx = (LONG)(short)LOWORD(*lp), qy = (LONG)(short)HIWORD(*lp), n = g_hs_n, i, px, py;
    int inside = 0, down = (m == WM_LBUTTONDOWN || m == WM_RBUTTONDOWN || m == WM_MBUTTONDOWN),
        up = (m == WM_LBUTTONUP || m == WM_RBUTTONUP || m == WM_MBUTTONUP);
    static int logged;
    for (i = 0; i < n && !inside; i++)
        inside = qx >= g_hs_dst[i][0] && qx < g_hs_dst[i][2] && qy >= g_hs_dst[i][1] && qy < g_hs_dst[i][3];
    if (inside)   /* a dialog drawn on top of the enlarged HUD keeps its native input */
        for (i = 0; i < g_hs_ndlg; i++)
            if (qx >= g_hs_dlg[i][0] && qx < g_hs_dlg[i][2] && qy >= g_hs_dlg[i][1] && qy < g_hs_dlg[i][3]) { inside = 0; break; }
    if (!inside && !g_hs_capture) return 0;
    if (down) g_hs_capture = 1;
    if (up) g_hs_capture = 0;
    px = rz_hs_src_coord(qx, g_hs_cw, g_hs_s);
    py = rz_hs_src_coord(qy, g_hs_ch, g_hs_s);
    if ((down || up) && logged < 40) { logged++; logf("HUDSCALE> %s (%ld,%ld) -> native (%ld,%ld)", down ? "down" : "up", qx, qy, px, py); }
    *lp = MAKELPARAM((WORD)(short)px, (WORD)(short)py);
    return 1;
}

/* UISCALE export (owner hand test 2026-10-20: "the profiling indicator/FPS should scale with interface too"): the HUD
   factor of the last enlarged present in percent, 100 when HUD scale is off or nothing was enlarged. sc3perf reads it
   (GetProcAddress) to draw its FPS line and busy lines at the same size. */
__declspec(dllexport) int sc3resize_ui_scale(void) {
    return g_hs_n > 0 && g_hs_s > 1.0 ? (int)(g_hs_s * 100.0 + 0.5) : 100;
}

/* CITYZOOM export (task cityzoom): the factor the city view is drawn at (1 = stock). sc3overscroll reads it
   (GetProcAddress) to judge camera steps at the visible centre in view pixels. */
__declspec(dllexport) int sc3resize_view_factor(void) {
    return (int)g_cz_f;
}

/* UISCALE export: while the main menu frame is presented scaled (MENUSCALE), its 4:3 rect in client coordinates;
   0 otherwise. sc3perf then draws its text on the window at the top-left instead of into the frame (owner 2026-10-20:
   "top-left of the window on the menu too"), because the frame does not reach the window corner. */
__declspec(dllexport) int sc3resize_menu_rect(LONG *r) {
    if (!g_ms_on || g_ms_rw <= 0 || !r) return 0;
    r[0] = g_ms_rx; r[1] = g_ms_ry; r[2] = g_ms_rx + g_ms_rw; r[3] = g_ms_ry + g_ms_rh;
    return 1;
}

/* DLGSCALE: map a mouse point on an enlarged dialog to its native rect. 1 = lp changed, 2 = already native (the
   game's repost of our last point, or a message it sends while handling ours), 0 = not on a dialog. */
static int rz_hd_mouse(UINT m, LPARAM *lp) {
    LONG qx = (LONG)(short)LOWORD(*lp), qy = (LONG)(short)HIWORD(*lp), n = g_hd_n, i, k = -1, px, py, w, h;
    int down = (m == WM_LBUTTONDOWN || m == WM_RBUTTONDOWN || m == WM_MBUTTONDOWN),
        up = (m == WM_LBUTTONUP || m == WM_RBUTTONUP || m == WM_MBUTTONUP);
    static int logged, dlogged;
    for (i = 0; i < n && g_hd_plbl[i]; i++) ;   /* task uiscale: the cost label takes no mouse */
    if (n <= 0 || i >= n) { g_hd_capture = -1; return 0; }
    if (g_hs_last_ok && *lp == g_hs_last_out && GetTickCount() - g_hs_last_t < 500 && (m == WM_MOUSEMOVE || g_hs_depth > 0))
        return 2;
    if (g_hd_capture >= 0)   /* a press on a dialog keeps the release (and the drag between) on that dialog */
        for (i = 0; i < n; i++) if (g_hd_pslot[i] == g_hd_capture) { k = i; break; }
    if (k < 0) {
        g_hd_capture = -1;
        for (i = n - 1; i >= 0 && k < 0; i--)
            if (!g_hd_plbl[i] && qx >= g_hd_pdst[i][0] && qx < g_hd_pdst[i][2] && qy >= g_hd_pdst[i][1] && qy < g_hd_pdst[i][3]) k = i;
    }
    if (k < 0) return 0;
    if (g_hd_capture >= 0 && !down && !g_hd_cap_drag &&
        (g_hd_pnat[k][0] != g_hd_cap_nat[0] || g_hd_pnat[k][1] != g_hd_cap_nat[1])) {
        g_hd_cap_drag = 1;   /* the game moves a dialog by the native distance from the press: give it the cursor's */
        if (dlogged++ < 10) logf("DLGSCALE> dialog moved during the press: cursor mapped 1:1 from the press point");
    }
    if (g_hd_capture >= 0 && !down && g_hd_cap_drag) {
        px = g_hd_cap_p[0] + (qx - g_hd_cap_q[0]);
        py = g_hd_cap_p[1] + (qy - g_hd_cap_q[1]);
    } else {
        w = g_hd_pnat[k][2] - g_hd_pnat[k][0]; h = g_hd_pnat[k][3] - g_hd_pnat[k][1];
        px = g_hd_pnat[k][0] + (LONG)floor((qx - g_hd_pdst[k][0] + 0.5) * w / (g_hd_pdst[k][2] - g_hd_pdst[k][0]));
        py = g_hd_pnat[k][1] + (LONG)floor((qy - g_hd_pdst[k][1] + 0.5) * h / (g_hd_pdst[k][3] - g_hd_pdst[k][1]));
    }
    if (down) {
        g_hd_capture = g_hd_pslot[k]; g_hd_cap_drag = 0;
        g_hd_cap_q[0] = qx; g_hd_cap_q[1] = qy; g_hd_cap_p[0] = px; g_hd_cap_p[1] = py;
        g_hd_cap_nat[0] = g_hd_pnat[k][0]; g_hd_cap_nat[1] = g_hd_pnat[k][1];
    }
    if (up) g_hd_capture = -1;
    if ((down || up) && logged < 40) {
        logged++;
        logf("DLGSCALE> %s (%ld,%ld) -> native (%ld,%ld) depth %d", down ? "down" : "up", qx, qy, px, py, g_hs_depth);
    }
    *lp = MAKELPARAM((WORD)(short)px, (WORD)(short)py);
    g_hs_last_out = *lp; g_hs_last_ok = 1; g_hs_last_t = GetTickCount();
    return 1;
}

/* HUDOPT (task hudopt 2026-10-11, re/analysis/OPTIONS_DIALOG.md): the HUD scale choice lives in the game's own
 * Preferences dialog ("Preferencias"), so the player picks it there instead of an env var.
 *
 * The dialog is built in CODE by SIMUI FUN_100564d9 (480x472, ids 0x02F95AD5..0x02F95B11), reached through its
 * controller's message handler FUN_10055e07 (message 0xa2bf8ace). It closes through FUN_100562b1(win, id):
 * id 0x02F95AD8 = OK (the check button AND the Enter key), 0x02F95AD6 = cancel (Esc, the close box)
 * [CONFIRMED @ SIMUI 0x10055e07, 0x10058f14]. Two entry detours, no other code change:
 *   - after FUN_10055e07 handles 0xa2bf8ace, add a label, a 5-option group and a checkbox to the window, with the
 *     game's own widget factory (FUN_10085065) and the same calls its builder uses for its own option groups
 *     (FUN_10059ccf) and checkboxes (FUN_10058d67). They sit in the empty right half of "Opciones generales".
 *   - before FUN_100562b1 runs, read them back (GetChildAs vt+0x80 with the option-group IID 0xa1336cc0 and the
 *     checkbox IID 0x8810, exactly as the game's OK handler FUN_100593ac does) and, on OK only, apply them to
 *     g_hudscale / g_hs_filter and write sc3resize.ini beside the DLL. Cancel applies nothing.
 * Our ids (0x02F95B40..47) fall outside every range the dialog's command handler acts on, so a click on them only
 * runs the widget's own behaviour (radio exclusivity, check toggle).
 * Persistence: sc3resize.ini [hud] scale = 0 off | 1 fit | 100..400 percent, smooth = 0 | 1 (missing = 1, owner
 * 2026-10-11). task uiscale (owner 2026-10-22: "auto-apply scaling according to the resolution of the computer, always
 * leave it by default auto adjust on the options"): scale 1 is shown as "Auto", listed first, and is the default when
 * the ini or its scale key is missing. The factor is the existing fit rule min(cw/800, ch/600), recomputed on every
 * present, so it follows the window from the start and on every resize (1.0 = native at 800x600). An ini written
 * before this build (no [hud] ver key) that holds scale=0 is read as Auto once: 0 was the old default and OK wrote it
 * back unchanged, so it does not tell a choice from a default. Every save writes ver=2, so a Normal picked from now
 * on persists. The env vars
 * SC3RESIZE_HUDSCALE / SC3RESIZE_HUDSCALE_FILTER still override the ini at startup. SC3RESIZE_HUDOPT=0 turns this
 * whole block off (no detours, ini not read): exactly the earlier env-only behaviour. */
static int  g_hudopt = 1;
static int  g_ho_env;                     /* bit 0 scale came from env, bit 1 smooth came from env */
static void *g_orig_5e07, *g_orig_62b1;   /* trampolines */
#define HO_GROUP   0x02F95B40
#define HO_OFF     0x02F95B41
#define HO_FIT     0x02F95B42
#define HO_P125    0x02F95B43
#define HO_P150    0x02F95B44
#define HO_P200    0x02F95B45
#define HO_LABEL   0x02F95B46
#define HO_SMOOTH  0x02F95B47
#define HO_X       250                    /* right half of the "Opciones generales" frame [6 346 474 422] */
#define HO_Y_LABEL 346
#define HO_Y_GROUP 364
#define HO_Y_CHECK 400
#define HO_W       218

static void ho_ini_path(char *out, int cap) { rz_mb_path(out, cap, "sc3resize.ini"); }

static int ho_valid_scale(int v) { return v == 0 || v == 1 || (v >= 100 && v <= 400); }

static void ho_load_ini(void) {
    char p[MAX_PATH];
    int s, f, ver;
    ho_ini_path(p, sizeof(p));
    s = (int)GetPrivateProfileIntA("hud", "scale", 1, p);    /* task uiscale: missing = Auto */
    f = (int)GetPrivateProfileIntA("hud", "smooth", 1, p);   /* hudfix: smooth ON unless the ini says smooth=0 */
    ver = (int)GetPrivateProfileIntA("hud", "ver", 0, p);
    if (s == 0 && ver < 2) { s = 1; logf("HUDOPT> ini scale=0 from a build before Auto (no ver=2): read as Auto"); }   /* task uiscale */
    g_hudscale = ho_valid_scale(s) ? s : 1;
    g_hs_filter = f ? 1 : 0;
}

static void ho_save_ini(void) {
    char p[MAX_PATH], v[16];
    ho_ini_path(p, sizeof(p));
    wsprintfA(v, "%d", g_hudscale);
    WritePrivateProfileStringA("hud", "scale", v, p);
    WritePrivateProfileStringA("hud", "smooth", g_hs_filter ? "1" : "0", p);
    WritePrivateProfileStringA("hud", "ver", "2", p);   /* task uiscale: scale=0 from here on is the player's Normal */
}

/* vtable call on a GZ object: __thiscall, slot byte offset, up to 5 dword args. 0 on a bad object. */
static DWORD ho_v(void *o, DWORD slot, int n, DWORD a0, DWORD a1, DWORD a2, DWORD a3, DWORD a4) {
    DWORD *vt, a[5];
    if (!o || IsBadReadPtr(o, 4)) return 0;
    vt = *(DWORD **)o;
    if (!vt || IsBadReadPtr((BYTE *)vt + slot, 4) || !vt[slot / 4]) return 0;
    a[0] = a0; a[1] = a1; a[2] = a2; a[3] = a3; a[4] = a4;
    return rz_thiscall_ret(o, (void *)vt[slot / 4], a, n);
}

/* SIMUI's GZ string class (ctor FUN_10005eb6, dtor FUN_10006057, vt+0x10 = assign from char*), re/analysis/PREFS_UI.md */
typedef void (__fastcall *HO_STRFN)(void *);
static void ho_str(BYTE *buf, const char *text) {
    HMODULE sui = GetModuleHandleA("SIMUI.DLL");
    memset(buf, 0, 0x20);
    ((HO_STRFN)((BYTE *)sui + 0x5eb6))(buf);
    if (text) ho_v(buf, 0x10, 1, (DWORD)text, 0, 0, 0, 0);
}
static void ho_str_free(BYTE *buf) { ((HO_STRFN)((BYTE *)GetModuleHandleA("SIMUI.DLL") + 0x6057))(buf); }

/* Language of our text: load the dialog's own title string (resource 0x14e in group 0x029541f4, the key the
   builder FUN_100564d9 opens with) through SIMUI's resource key FUN_1008ebbd / FUN_1008ebea, and look at its
   text: "Preferencias" -> Spanish, anything else -> English. The game's locale id (SC3U FUN_004845fe vt+0x74)
   reads 1 on the Spanish install, so it cannot tell the text language. sc3resize.ini [hud] lang=es|en overrides. */
static int ho_spanish(void) {
    static int done, es;
    char p[MAX_PATH], v[8];
    HMODULE sui = GetModuleHandleA("SIMUI.DLL");
    DWORD key[8], a[2], fn;
    const char *t = NULL;
    int i;
    if (done) return es;
    done = 1;
    ho_ini_path(p, sizeof(p));
    GetPrivateProfileStringA("hud", "lang", "", v, sizeof(v), p);
    if (v[0]) { es = (v[0] == 'e' || v[0] == 'E') && (v[1] == 's' || v[1] == 'S'); logf("HUDOPT> text language from ini: %s", es ? "es" : "en"); return es; }
    memset(key, 0, sizeof(key));
    a[0] = 0x14e; a[1] = 0x29541f4;
    rz_thiscall_ret(key, (BYTE *)sui + 0x8ebbd, a, 2);
    fn = key[1];                                         /* the loaded string object, NULL if the key missed */
    for (i = 1; fn && !IsBadReadPtr((void *)fn, 0x14) && !t && i < 5; i++) {   /* its char* is in one of its first dwords */
        const char *c = ((const char **)fn)[i];
        if (c && !IsBadReadPtr(c, 12) && c[0] == 'P' && c[1] == 'r') t = c;
    }
    es = t && memcmp(t, "Preferencias", 12) == 0;
    logf("HUDOPT> dialog title resource: \"%.20s\" -> %s text", t ? t : "(not found)", es ? "Spanish" : "English");
    rz_thiscall_ret(key, (BYTE *)sui + 0x8ebea, NULL, 0);
    return es;
}

/* Label, mirrored from SIMUI FUN_1005844a (the dialog's section labels), caption set from our own string. */
static int ho_add_label(void *fac, void *win, DWORD id, const char *text, int x, int y, int w) {
    HMODULE sui = GetModuleHandleA("SIMUI.DLL");
    BYTE s[0x20];
    void *lbl, *lw, *cs;
    int ok = 0;
    ho_str(s, text);
    lbl = (void *)ho_v(fac, 0x44, 2, id, (DWORD)s, 0, 0, 0);                         /* CreateLabel */
    if (lbl) {
        ho_v(lbl, 0x40, 1, ho_v(fac, 0x14, 1, 0xf, 0, 0, 0, 0), 0, 0, 0, 0);          /* font 0xf */
        cs = ((void *(__cdecl *)(void))((BYTE *)sui + 0x85039))();                   /* colour service */
        if (cs) ho_v(lbl, 0x24, 1, ho_v(cs, 0x84, 3, 0x79, 0x7d, 0xb5, 0, 0) & 0xffff, 0, 0, 0, 0);
        lw = (void *)ho_v(lbl, 0x0c, 0, 0, 0, 0, 0, 0);
        ho_v(lw, 0x10c, 1, (DWORD)s, 0, 0, 0, 0);                                     /* caption */
        ho_v(lw, 0xb8, 1, (DWORD)w, 0, 0, 0, 0);
        ho_v(lbl, 0x44, 1, 1, 0, 0, 0, 0);
        ho_v(lw, 0xcc, 2, (DWORD)x, (DWORD)y, 0, 0, 0);
        ok = (int)(ho_v(win, 0x34, 1, (DWORD)lw, 0, 0, 0, 0) & 0xff);                  /* AddChild */
        if (!ok) ho_v(lw, 0x28, 0, 0, 0, 0, 0, 0);
        ho_v(lbl, 0x08, 0, 0, 0, 0, 0, 0);
    }
    ho_str_free(s);
    return ok;
}

static DWORD ho_sel_id(int scale) {
    switch (scale) {
    case 0: return HO_OFF;
    case 1: return HO_FIT;
    case 125: return HO_P125;
    case 150: return HO_P150;
    case 200: return HO_P200;
    }
    return 0;   /* a custom env/ini percent: no option selected, OK keeps it unless the player picks one */
}

static void ho_log_child(void *win, DWORD id, const char *tag) {
    void *c = (void *)ho_v(win, 0x78, 1, id, 0, 0, 0, 0);
    if (c && !IsBadReadPtr(c, 0x90)) {
        LONG *l = (LONG *)((BYTE *)c + 0x80), *d = (LONG *)((BYTE *)c + 0x14);
        logf("HUDOPT>   %s 0x%08lX local [%ld %ld %ld %ld] abs [%ld %ld %ld %ld]", tag, id, l[0], l[1], l[2], l[3],
             d[0], d[1], d[2], d[3]);
    } else logf("HUDOPT>   %s 0x%08lX not found by vt+0x78", tag, id);
}

static void ho_add_controls(void *win) {
    HMODULE sui = GetModuleHandleA("SIMUI.DLL");
    void *fac, *grp, *gw, *cb, *cw;
    DWORD col, font, sel;
    BYTE s[0x20];
    LONG r[4];
    int es = ho_spanish(), okl, okg = 0, okc = 0, i;
    static const DWORD ids[5] = { HO_FIT, HO_OFF, HO_P125, HO_P150, HO_P200 };   /* task uiscale: Auto first */
    /* trailing spaces widen the auto-sized options: the group spaces its columns by the widest option so far
       (GZWIND FUN_1000337d), and without them the next column's radio touches the text before it */
    const char *txt_es[5] = { "Auto   ", "Normal   ", "125%   ", "150%   ", "200%" };
    const char *txt_en[5] = { "Auto   ", "Normal   ", "125%   ", "150%   ", "200%" };
    if (!sui || !win || IsBadReadPtr(win, 0x90)) return;
    if (ho_v(win, 0x78, 1, HO_GROUP, 0, 0, 0, 0)) { logf("HUDOPT> controls already in this window"); return; }
    fac = ((void *(__cdecl *)(void))((BYTE *)sui + 0x85065))();
    if (!fac || IsBadReadPtr(fac, 4)) { logf("HUDOPT> no widget factory"); return; }
    col = ho_v(fac, 0x80, 1, 0x62e56a2e, 0, 0, 0, 0);
    okl = ho_add_label(fac, win, HO_LABEL, es ? "Escala de la interfaz:" : "Interface scale:", HO_X, HO_Y_LABEL, 0xb4);

    /* option group, FUN_10059ccf + the builder's AddOption/Select/SetXY/AddChild sequence */
    ho_str(s, NULL);
    grp = (void *)ho_v(fac, 0x48, 3, HO_GROUP, (DWORD)s, 0, 0, 0);
    ho_str_free(s);
    if (grp) {
        font = ho_v(fac, 0x14, 1, 0xf, 0, 0, 0, 0);
        ho_v(grp, 0x24, 1, font, 0, 0, 0, 0);
        ho_v(grp, 0x28, 2, 2, col, 0, 0, 0);
        ho_v(grp, 0x28, 2, 3, col, 0, 0, 0);
        ho_v(grp, 0x28, 2, 4, col, 0, 0, 0);
        ho_v(grp, 0x14, 2, 1, 0, 0, 0, 0);
        ho_v(grp, 0x14, 2, 8, 0, 0, 0, 0);
        ho_v(grp, 0x18, 2, 0, 0, 0, 0, 0);
        r[0] = HO_X; r[1] = HO_Y_GROUP; r[2] = HO_X + HO_W; r[3] = HO_Y_GROUP + 36;   /* 2 rows of 18, as the game sizes them */
        gw = (void *)ho_v(grp, 0x0c, 0, 0, 0, 0, 0, 0);
        ho_v(gw, 0xc4, 1, (DWORD)r, 0, 0, 0, 0);
        for (i = 0; i < 5; i++) {
            ho_str(s, es ? txt_es[i] : txt_en[i]);
            ho_v(grp, 0x38, 5, ids[i], (DWORD)s, 0, 0, 0);
            ho_str_free(s);
        }
        sel = ho_sel_id(g_hudscale);
        if (sel) ho_v(grp, 0x34, 1, sel, 0, 0, 0, 0);
        gw = (void *)ho_v(grp, 0x0c, 0, 0, 0, 0, 0, 0);
        ho_v(gw, 0xcc, 2, HO_X, HO_Y_GROUP, 0, 0, 0);
        gw = (void *)ho_v(grp, 0x0c, 0, 0, 0, 0, 0, 0);
        okg = (int)(ho_v(win, 0x34, 1, (DWORD)gw, 0, 0, 0, 0) & 0xff);
        if (!okg) ho_v(gw, 0x28, 0, 0, 0, 0, 0, 0);
        else {
            /* measured: once its options are in, the group's rect is 170 wide while its third column ends at 185,
               so the tail of the last option took no clicks. Give it the full width back, parent-local (vt+0xc8). */
            LONG *lr = (LONG *)((BYTE *)gw + 0x80);
            logf("HUDOPT>   group rect before widening [%ld %ld %ld %ld]", lr[0], lr[1], lr[2], lr[3]);
            ho_v(gw, 0xc8, 4, HO_X, HO_Y_GROUP, HO_X + HO_W, lr[3], 0);
        }
        ho_v(grp, 0x08, 0, 0, 0, 0, 0, 0);
    }

    /* checkbox, FUN_10058d67 */
    ho_str(s, es ? "Suavizado" : "Smooth");
    cb = (void *)ho_v(fac, 0x3c, 5, HO_SMOOTH, (DWORD)s, 0, 0, 0);
    ho_str_free(s);
    if (cb) {
        ho_v(cb, 0x34, 1, g_hs_filter ? 1 : 0, 0, 0, 0, 0);
        ho_v(cb, 0x74, 4, 3, 1, 2, 2, 0);
        ho_v(cb, 0x60, 1, ho_v(fac, 0x14, 1, 0xf, 0, 0, 0, 0), 0, 0, 0, 0);
        ho_v(cb, 0x64, 2, 0, col, 0, 0, 0);
        ho_v(cb, 0x64, 2, 2, col, 0, 0, 0);
        ho_v(cb, 0x64, 2, 4, col, 0, 0, 0);
        cw = (void *)ho_v(cb, 0x1c, 0, 0, 0, 0, 0, 0);
        ho_v(cw, 0xb8, 1, 0x78, 0, 0, 0, 0);
        cw = (void *)ho_v(cb, 0x1c, 0, 0, 0, 0, 0, 0);
        ho_v(cw, 0xcc, 2, HO_X, HO_Y_CHECK, 0, 0, 0);
        cw = (void *)ho_v(cb, 0x1c, 0, 0, 0, 0, 0, 0);
        okc = (int)(ho_v(win, 0x34, 1, (DWORD)cw, 0, 0, 0, 0) & 0xff);
        if (!okc) ho_v(cw, 0x28, 0, 0, 0, 0, 0, 0);
        ho_v(cb, 0x08, 0, 0, 0, 0, 0, 0);
    }
    logf("HUDOPT> Preferences 0x%08lX: label %s, scale group %s (selected 0x%08lX for scale %d), smooth checkbox %s (%d)",
         (DWORD)win, okl ? "added" : "FAILED", okg ? "added" : "FAILED", ho_sel_id(g_hudscale), g_hudscale,
         okc ? "added" : "FAILED", g_hs_filter);
    {   static int dumped;
        if (dumped++ < 2) {
            ho_log_child(win, HO_LABEL, "label");
            ho_log_child(win, HO_GROUP, "group");
            {   void *g = (void *)ho_v(win, 0x78, 1, HO_GROUP, 0, 0, 0, 0), *head, *n;   /* the options are the group's children */
                int guard = 0;
                head = (g && !IsBadReadPtr(g, 0x40)) ? *(void **)((BYTE *)g + 0x34) : NULL;
                n = (head && !IsBadReadPtr(head, 4)) ? *(void **)head : NULL;
                while (n && n != head && guard++ < 16 && !IsBadReadPtr(n, 0x0c)) {
                    BYTE *c = *(BYTE **)((BYTE *)n + 8);
                    if (c && !IsBadReadPtr(c, 0x90)) {
                        LONG *l = (LONG *)(c + 0x80), *d = (LONG *)(c + 0x14);
                        logf("HUDOPT>   option local [%ld %ld %ld %ld] abs [%ld %ld %ld %ld]", l[0], l[1], l[2], l[3], d[0], d[1], d[2], d[3]);
                    }
                    n = *(void **)n;
                }
            }
            ho_log_child(win, HO_SMOOTH, "smooth");
            ho_log_child(win, 0x02F95AF8, "game checkbox");
            ho_log_child(win, 0x02F95AD8, "game OK");
        }
    }
}

/* Read the controls back. Returns 1 and fills scale/smooth when both were found. */
static int ho_read(void *win, int *scale, int *smooth) {
    void *o = NULL;
    DWORD id;
    int got = 0;
    *scale = g_hudscale; *smooth = g_hs_filter;
    if ((ho_v(win, 0x80, 3, HO_GROUP, 0xa1336cc0, (DWORD)&o, 0, 0) & 0xff) && o) {
        id = ho_v(o, 0x30, 0, 0, 0, 0, 0, 0);
        ho_v(o, 0x08, 0, 0, 0, 0, 0, 0);
        switch (id) {
        case HO_OFF: *scale = 0; break;
        case HO_FIT: *scale = 1; break;
        case HO_P125: *scale = 125; break;
        case HO_P150: *scale = 150; break;
        case HO_P200: *scale = 200; break;
        }
        got |= 1;
    }
    o = NULL;
    if ((ho_v(win, 0x80, 3, HO_SMOOTH, 0x8810, (DWORD)&o, 0, 0) & 0xff) && o) {
        *smooth = (ho_v(o, 0x38, 0, 0, 0, 0, 0, 0) & 0xff) ? 1 : 0;
        ho_v(o, 0x08, 0, 0, 0, 0, 0, 0);
        got |= 2;
    }
    return got == 3;
}

/* PERFPREFS (task perfprefs 2026-10-12, owner: "quiero un toggle en preferencias para desactivar el FPS counter y el
 * profiler"). Two more checkboxes in the same dialog, on the free row under the game's "Ir a los desastres" (game
 * checkbox 0x02F95AF8 at local [18 381 212 398], measured): "Ver FPS" and "Ver perfilador", worded like the game's
 * own "Ver consejos al iniciar". They drive sc3perf's on-screen text: the FPS line and the red SIM BUSY / DATE
 * STOPPED lines. sc3perf owns that state and its file: we call its exports sc3perf_show_get / sc3perf_show_set
 * (bits 1 FPS, 2 busy lines, 4 busy detector running, 0x100 valid), resolved when the dialog is built. The setter
 * takes effect on the next present and writes perf.ini (overlay=, busy_show=), so a hand edit of perf.ini and the
 * SC3PERF_OVERLAY / SC3PERF_BUSY_SHOW env vars keep working. No sc3perf.dll, or one without the exports: no boxes.
 * OK applies, every other close keeps the old values (same rule as HUDOPT). Ids 0x02F95B48/49 are above 0x02F95B11,
 * so the dialog's command handler only returns for them [CONFIRMED @ SIMUI 0x10058f14].
 * SC3RESIZE_PERFPREFS=0: no boxes. Rides on the HUDOPT detours, so SC3RESIZE_HUDOPT=0 removes them too. */
static int g_perfprefs = 1;
#define PP_FPS     0x02F95B48
#define PP_BUSY    0x02F95B49
#define PP_Y       400
#define PP_X_FPS   18
#define PP_X_BUSY  120
typedef int (*PP_GET)(void);
typedef int (*PP_SET)(int);

static int pp_api(PP_GET *get, PP_SET *set) {
    HMODULE pm = GetModuleHandleA("sc3perf.dll");
    *get = pm ? (PP_GET)GetProcAddress(pm, "sc3perf_show_get") : NULL;
    *set = pm ? (PP_SET)GetProcAddress(pm, "sc3perf_show_set") : NULL;
    return *get && *set;
}

/* one checkbox, the same calls as HUDOPT's "Suavizado" (the game's FUN_10058d67) */
static int pp_add_checkbox(void *fac, void *win, DWORD id, const char *text, int on, int x, int w, DWORD col) {
    BYTE s[0x20];
    void *cb, *cw;
    int ok = 0;
    ho_str(s, text);
    cb = (void *)ho_v(fac, 0x3c, 5, id, (DWORD)s, 0, 0, 0);
    ho_str_free(s);
    if (!cb) return 0;
    ho_v(cb, 0x34, 1, on ? 1 : 0, 0, 0, 0, 0);
    ho_v(cb, 0x74, 4, 3, 1, 2, 2, 0);
    ho_v(cb, 0x60, 1, ho_v(fac, 0x14, 1, 0xf, 0, 0, 0, 0), 0, 0, 0, 0);
    ho_v(cb, 0x64, 2, 0, col, 0, 0, 0);
    ho_v(cb, 0x64, 2, 2, col, 0, 0, 0);
    ho_v(cb, 0x64, 2, 4, col, 0, 0, 0);
    cw = (void *)ho_v(cb, 0x1c, 0, 0, 0, 0, 0, 0);
    ho_v(cw, 0xb8, 1, (DWORD)w, 0, 0, 0, 0);
    cw = (void *)ho_v(cb, 0x1c, 0, 0, 0, 0, 0, 0);
    ho_v(cw, 0xcc, 2, (DWORD)x, PP_Y, 0, 0, 0);
    cw = (void *)ho_v(cb, 0x1c, 0, 0, 0, 0, 0, 0);
    ok = (int)(ho_v(win, 0x34, 1, (DWORD)cw, 0, 0, 0, 0) & 0xff);
    if (!ok) ho_v(cw, 0x28, 0, 0, 0, 0, 0, 0);
    ho_v(cb, 0x08, 0, 0, 0, 0, 0, 0);
    return ok;
}

static void pp_add_controls(void *win) {
    HMODULE sui = GetModuleHandleA("SIMUI.DLL");
    PP_GET get;
    PP_SET set;
    void *fac;
    DWORD col;
    int bits, es, okf, okb;
    if (!g_perfprefs || !sui || !win || IsBadReadPtr(win, 0x90)) return;
    if (!pp_api(&get, &set)) { logf("PERFPREFS> sc3perf.dll %s - no FPS/profiler boxes",
                                    GetModuleHandleA("sc3perf.dll") ? "has no sc3perf_show_get/set exports" : "not loaded"); return; }
    if (ho_v(win, 0x78, 1, PP_FPS, 0, 0, 0, 0)) return;
    fac = ((void *(__cdecl *)(void))((BYTE *)sui + 0x85065))();
    if (!fac || IsBadReadPtr(fac, 4)) return;
    col = ho_v(fac, 0x80, 1, 0x62e56a2e, 0, 0, 0, 0);
    bits = get();
    es = ho_spanish();
    okf = pp_add_checkbox(fac, win, PP_FPS, es ? "Ver FPS" : "Show FPS", bits & 1, PP_X_FPS, 96, col);
    okb = pp_add_checkbox(fac, win, PP_BUSY, es ? "Ver perfilador" : "Show profiler", bits & 2, PP_X_BUSY, 120, col);
    logf("PERFPREFS> Preferences 0x%08lX: FPS box %s (%d), profiler box %s (%d), sc3perf bits 0x%x",
         (DWORD)win, okf ? "added" : "FAILED", bits & 1, okb ? "added" : "FAILED", (bits >> 1) & 1, bits);
    {   static int dumped;
        if (dumped++ < 2) { ho_log_child(win, PP_FPS, "fps box"); ho_log_child(win, PP_BUSY, "profiler box"); }
    }
}

/* -1 = box not found, else 0/1 */
static int pp_read_box(void *win, DWORD id) {
    void *o = NULL;
    int v;
    if (!(ho_v(win, 0x80, 3, id, 0x8810, (DWORD)&o, 0, 0) & 0xff) || !o) return -1;
    v = (ho_v(o, 0x38, 0, 0, 0, 0, 0, 0) & 0xff) ? 1 : 0;
    ho_v(o, 0x08, 0, 0, 0, 0, 0, 0);
    return v;
}

static void pp_close(void *win, DWORD id) {
    PP_GET get;
    PP_SET set;
    int f, b, cur;
    if (!g_perfprefs || !pp_api(&get, &set)) return;
    f = pp_read_box(win, PP_FPS);
    b = pp_read_box(win, PP_BUSY);
    if (f < 0 || b < 0) return;   /* not our dialog build (boxes never added) */
    cur = get();
    if (id == 0x02F95AD8) {
        int now = set((f ? 1 : 0) | (b ? 2 : 0));
        logf("PERFPREFS> OK: FPS %d, profiler %d%s (sc3perf bits 0x%x)", f, b,
             f == (cur & 1) && b == ((cur >> 1) & 1) ? " (unchanged)" : "", now);
    } else {
        logf("PERFPREFS> closed with 0x%08lX (cancel): dialog showed FPS %d profiler %d, kept %d %d", id, f, b,
             cur & 1, (cur >> 1) & 1);
    }
}

/* task cityzoom: "Zoom extra" checkbox on the same row, right of HUDOPT's "Suavizado" ([250 400 327 417]), inside
   "Opciones generales" ([6 346 474 422]). On = zoomextra Auto (or the ini's 2 kept), off = 0. OK applies and writes
   sc3resize.ini [view] zoomextra; every other close keeps the old value. Id above 0x02F95B11 like PERFPREFS'. */
#define CZ_BOX   0x02F95B4A
#define CZ_BOX_X 345
static void cz_add_box(void *win) {
    HMODULE sui = GetModuleHandleA("SIMUI.DLL");
    void *fac;
    DWORD col;
    int ok;
    if (!sui || !win || IsBadReadPtr(win, 0x90) || !g_zoomcenter_on()) return;
    if (ho_v(win, 0x78, 1, CZ_BOX, 0, 0, 0, 0)) return;
    fac = ((void *(__cdecl *)(void))((BYTE *)sui + 0x85065))();
    if (!fac || IsBadReadPtr(fac, 4)) return;
    col = ho_v(fac, 0x80, 1, 0x62e56a2e, 0, 0, 0, 0);
    ok = pp_add_checkbox(fac, win, CZ_BOX, ho_spanish() ? "Zoom extra" : "Extra zoom", g_cz_mode != 0, CZ_BOX_X, 120, col);
    logf("CITYZOOM> Preferences 0x%08lX: zoom extra box %s (%d)", (DWORD)win, ok ? "added" : "FAILED", g_cz_mode != 0);
}
static void cz_close_box(void *win, DWORD id) {
    char ip[MAX_PATH], v[8];
    int b = pp_read_box(win, CZ_BOX), was = g_cz_mode;
    if (b < 0) return;
    if (id != 0x02F95AD8) { logf("CITYZOOM> Preferences closed with 0x%08lX (cancel): zoom extra kept %d", id, was); return; }
    g_cz_mode = b ? (was ? was : 1) : 0;
    if (!g_cz_mode) InterlockedExchange(&g_cz_req, 1);
    ho_ini_path(ip, sizeof(ip));
    wsprintfA(v, "%d", g_cz_mode);
    WritePrivateProfileStringA("view", "zoomextra", v, ip);
    logf("CITYZOOM> Preferences OK: zoomextra %d%s, saved to sc3resize.ini", g_cz_mode, g_cz_mode == was ? " (unchanged)" : "");
}

/* RESROW (owner 2026-10-20): the resolution follows the window, so the "Resolucion de pantalla" label 0x02F95AE3 and its
   dropdown 0x02F95AEA (built by FUN_10058631 [CONFIRMED @ SIMUI 0x10058631]) are hidden, leaving a gap (owner call).
   GZWIND vt+0xf4 SetFlags(1 = visible, 0), the call CLOSEFLY uses. Hidden, the dropdown is never picked, so its index
   stays put and the OK handler FUN_10058f14 never asks to restart. SC3RESIZE_RESROW=1 shows it again. */
static int g_resrow = 0;
static void ho_hide_resrow(void *win) {
    static const DWORD ids[2] = { 0x02F95AE3, 0x02F95AEA };
    int i, hid = 0;
    if (g_resrow) return;
    for (i = 0; i < 2; i++) {
        void *c = (void *)ho_v(win, 0x78, 1, ids[i], 0, 0, 0, 0);
        if (c && !IsBadReadPtr(c, 0xa4)) { ho_v(c, 0xf4, 2, 1, 0, 0, 0, 0); hid += !(*(DWORD *)((BYTE *)c + 0xa0) & 1); }
        else logf("RESROW> 0x%08lX not found in Preferences", ids[i]);
    }
    logf("RESROW> resolution row: %d of 2 hidden", hid);
}

static DWORD __fastcall ho_prefs_msg(void *self, void *edx, DWORD win, DWORD msg, DWORD p3, DWORD p4, DWORD p5) {
    DWORD a[5], r;
    (void)edx;
    a[0] = win; a[1] = msg; a[2] = p3; a[3] = p4; a[4] = p5;
    r = rz_thiscall_ret(self, g_orig_5e07, a, 5);
    if (msg == 0xa2bf8ace && (r & 0xff) && win) { ho_add_controls((void *)win); pp_add_controls((void *)win); cz_add_box((void *)win); ho_hide_resrow((void *)win); }
    return r;
}

static DWORD __fastcall ho_prefs_close(void *self, void *edx, DWORD win, DWORD id) {
    DWORD a[2];
    int sc, sm;
    (void)edx;
    if (win && !IsBadReadPtr((void *)win, 4)) {
        int got = ho_read((void *)win, &sc, &sm);
        if (id == 0x02F95AD8 && got) {
            int changed = sc != g_hudscale || sm != g_hs_filter;
            g_hudscale = sc; g_hs_filter = sm;
            g_hs_capture = 0;
            ho_save_ini();
            logf("HUDOPT> OK: scale %d, smooth %d%s, saved to sc3resize.ini%s", sc, sm, changed ? "" : " (unchanged)",
                 g_ho_env ? " (an env var overrides it at the next start)" : "");
        } else if (id == 0x02F95AD8) {
            logf("HUDOPT> OK but our controls were not found (read %d) - nothing applied", got);
        } else {
            logf("HUDOPT> closed with 0x%08lX (cancel): dialog showed scale %d smooth %d, kept scale %d smooth %d",
                 id, sc, sm, g_hudscale, g_hs_filter);
        }
        pp_close((void *)win, id);   /* PERFPREFS */
        cz_close_box((void *)win, id);   /* task cityzoom */
    }
    a[0] = win; a[1] = id;
    return rz_thiscall_ret(self, g_orig_62b1, a, 2);
}

/* 5- or 6-byte prologue steal, same shape as rz_hook_cdcd. */
static int ho_hook(HMODULE sui, DWORD rva, const BYTE *expect, int len, void *detour, void **orig, const char *name) {
    BYTE *fn = (BYTE *)sui + rva, *tr;
    DWORD old;
    int i;
    if (*orig) return 1;
    if (IsBadReadPtr(fn, len) || memcmp(fn, expect, len) != 0) {
        logf("HUDOPT> SIMUI+0x%lx (%s) prologue mismatch - NOT hooking, no HUD option in Preferences", rva, name);
        return 0;
    }
    tr = (BYTE *)VirtualAlloc(NULL, 16, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!tr) return 0;
    memcpy(tr, expect, len);
    tr[len] = 0xE9;
    *(DWORD *)(tr + len + 1) = (DWORD)(fn + len) - (DWORD)(tr + len + 5);
    FlushInstructionCache(GetCurrentProcess(), tr, 16);
    if (!VirtualProtect(fn, len, PAGE_EXECUTE_READWRITE, &old)) return 0;
    *orig = tr;
    fn[0] = 0xE9;
    *(DWORD *)(fn + 1) = (DWORD)detour - (DWORD)(fn + 5);
    for (i = 5; i < len; i++) fn[i] = 0x90;
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    FlushInstructionCache(GetCurrentProcess(), fn, len);
    logf("HUDOPT> detour on SIMUI+0x%lx (%s)", rva, name);
    return 1;
}

static void ho_install(HMODULE sui) {
    static const BYTE e5e07[6] = { 0x55, 0x8b, 0xec, 0x83, 0xec, 0x18 };   /* push ebp; mov ebp,esp; sub esp,0x18 */
    static const BYTE e62b1[5] = { 0x55, 0x8b, 0xec, 0x51, 0x51 };         /* push ebp; mov ebp,esp; push ecx; push ecx */
    if (!g_hudopt) return;
    /* both or neither: controls that could never be applied would be a lie */
    if (memcmp((BYTE *)sui + 0x55e07, e5e07, 6) != 0 || memcmp((BYTE *)sui + 0x562b1, e62b1, 5) != 0) {
        logf("HUDOPT> SIMUI prologues differ from the anchor - HUD option NOT added to Preferences");
        return;
    }
    ho_hook(sui, 0x562b1, e62b1, 5, (void *)ho_prefs_close, &g_orig_62b1, "Preferences close FUN_100562b1");
    if (g_orig_62b1)
        ho_hook(sui, 0x55e07, e5e07, 6, (void *)ho_prefs_msg, &g_orig_5e07, "Preferences messages FUN_10055e07");
}

/* QUERYID (task queryid 2026-10-12, re/analysis/QUERY_ID.md). Owner: "me gustaria senalar con ID el elemento que quiero
 * trabajar, podemos implementar un boton en el menu de '?' para que copie el ID de lo seleccionado?"
 * The query dialog is one SIMUI class (ctor FUN_10061f53, vtables 0x100aadc8 and 0x100aadb8 at +4). Its message
 * handler FUN_1006338f is slot 3 of the +4 vtable, the only reference to it in the image [CONFIRMED @ SIMUI 0x100aadc4].
 * Message 0xa2bf8ace builds the content (FUN_100634a6), message 3 with p3 1 carries a button id in p4 (0, 4 and the
 * close box 0x42b7c353 are the game's) [CONFIRMED @ SIMUI 0x1006338f]. One entry detour: after the build we add a text
 * button made by the game's widget factory (+0x30, the text-only path of SIMUI 0x1000114e); on its click we read the
 * queried object and put a labelled text block on the clipboard. Object fields (query object, handler this - 4):
 * +0x14 dialog mode, +0xd8 occupant or NULL, +0xdc/+0xe0/+0xe4 coord with cell = +0xdc >> 8, +0xe0 >> 8
 * [CONFIRMED @ SIMUI 0x10062cee, 0x10062cba, 0x1006255a]. SC3RESIZE_QUERYID=0: no detour, no button. */
static int   g_queryid = 1;
static void *g_orig_338f;
#define QI_BTN 0x02F95B50

static const char *qi_mod_of(DWORD a, DWORD *rva) {
    static char name[64];
    HMODULE m = NULL;
    char p[MAX_PATH], *s;
    *rva = 0;
    if (!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                            (LPCSTR)a, &m) || !m) return "?";
    *rva = a - (DWORD)m;
    if (!GetModuleFileNameA(m, p, sizeof(p))) return "?";
    s = strrchr(p, '\\');
    lstrcpynA(name, s ? s + 1 : p, sizeof(name));
    return name;
}

/* The 22 SIMNTWRK network-piece classes, cISC3Occupant subobject vtable (piece + 4), from the factory FUN_1000bdcd
   [CONFIRMED @ SIMNTWRK 0x1000bdcd] (re/analysis/NETWORK_RULE_ENGINE.md section 11.2). */
static const DWORD qi_piece_vt2[22] = {
    0x2b5dc, 0x2b284, 0x2b0d8, 0x2af2c, 0x2abd4, 0x2aa28, 0x2a87c, 0x2a6d0, 0x2ad80, 0x2b430, 0x2a524,
    0x2a378, 0x2a1cc, 0x2a020, 0x29e74, 0x29cc8, 0x29b1c, 0x29970, 0x297c4, 0x29618, 0x2946c, 0x292c0 };

/* Is piece id in one of SIMNTWRK's per-network id lists? Each global is a pointer to {begin, end} of 12-byte keys
   {0xe223741f, 0xa317745f, id}, filled from TilingRules\<NET>_GRND_Set.txt [CONFIRMED @ SIMNTWRK 0x1001726e..0x10017312,
   0x1001746e]; the six membership predicates scan them [CONFIRMED @ SIMNTWRK 0x1001a719..0x1001a7d2]. */
static int qi_in_list(HMODULE nt, DWORD rva, DWORD id) {
    DWORD *v = *(DWORD **)((BYTE *)nt + rva), b, e, n = 0;
    if (!v || IsBadReadPtr(v, 8)) return -1;
    b = v[0]; e = v[1];
    if (!b || e < b || IsBadReadPtr((void *)b, e - b)) return -1;
    for (; b < e && n < 100000; b += 12, n++) if (((DWORD *)b)[2] == id) return 1;
    return 0;
}

static int qi_cat(char *out, int cap, int len, const char *fmt, ...) {
    va_list ap;
    int n;
    if (len >= cap - 1) return len;
    va_start(ap, fmt);
    n = _vsnprintf(out + len, cap - 1 - len, fmt, ap);
    va_end(ap);
    if (n < 0) { out[cap - 1] = 0; return cap - 1; }
    return len + n;
}

static const char *qi_zone_name(DWORD z) {   /* zone bytes from the 13 zone tools, LAUNCH_CONTROL.md (C4 for 6) */
    switch (z) {
    case 0: return "none";
    case 1: return "residential light"; case 2: return "residential medium"; case 3: return "residential dense";
    case 5: return "commercial light"; case 6: return "commercial medium"; case 7: return "commercial dense";
    case 9: return "industrial light"; case 10: return "industrial medium"; case 11: return "industrial dense";
    case 14: return "airport"; case 15: return "seaport"; case 17: return "landfill";
    }
    return NULL;
}

/* Build the text for the query object `qo`. Field meanings and their evidence: re/analysis/QUERY_ID.md.
   Every virtual call is guarded: an unexpected object costs a line, not the game. */
static int qi_build(BYTE *qo, char *t, int cap) {
    HMODULE sui = GetModuleHandleA("SIMUI.DLL"), nt = GetModuleHandleA("SIMNTWRK.DLL");
    int L = 0, i;
    LONG cx, cz;
    DWORD *c = (DWORD *)(qo + 0xdc), mode = *(DWORD *)(qo + 0x14), rva;
    void *occ = *(void **)(qo + 0xd8), *city = NULL;
    L = qi_cat(t, cap, L, "SC3 query id v1\r\n");
    cx = (LONG)c[0] >> 8; cz = (LONG)c[1] >> 8;
    L = qi_cat(t, cap, L, "cell: x=%ld z=%ld alt=%ld\r\n", cx, cz, (LONG)c[2] >> 8);
    __try { city = ((void *(__cdecl *)(void))((BYTE *)sui + 0x8e7da))(); } __except (EXCEPTION_EXECUTE_HANDLER) { city = NULL; }
    if (city) {
        void *dirt = NULL, *zl = NULL;
        BYTE zb = 0xff, alt[4];
        __try {
            dirt = (void *)ho_v(city, 0x13c, 0, 0, 0, 0, 0, 0);
            zl = (void *)ho_v(city, 0x14c, 0, 0, 0, 0, 0, 0);
            if (zl) {
                const char *zn;
                ho_v(zl, 0x34, 3, (DWORD)cx, (DWORD)cz, (DWORD)&zb, 0, 0);
                zn = qi_zone_name(zb);
                L = qi_cat(t, cap, L, "zone: %u%s%s%s\r\n", zb, zn ? " (" : "", zn ? zn : "", zn ? ")" : "");
            }
            if (dirt) {
                L = qi_cat(t, cap, L, "terrain.water: %lu\r\n", ho_v(dirt, 0x54, 2, (DWORD)cx, (DWORD)cz, 0, 0, 0) & 0xff);
                memset(alt, 0, sizeof(alt));
                ho_v(dirt, 0x48, 3, (DWORD)cx, (DWORD)cz, (DWORD)&alt[0], 0, 0);
                ho_v(dirt, 0x48, 3, (DWORD)cx + 1, (DWORD)cz, (DWORD)&alt[1], 0, 0);
                ho_v(dirt, 0x48, 3, (DWORD)cx, (DWORD)cz + 1, (DWORD)&alt[2], 0, 0);
                ho_v(dirt, 0x48, 3, (DWORD)cx + 1, (DWORD)cz + 1, (DWORD)&alt[3], 0, 0);
                L = qi_cat(t, cap, L, "terrain.corner_alt: %u %u %u %u\r\n", alt[0], alt[1], alt[2], alt[3]);
                memset(alt, 0, sizeof(alt));
                ho_v(dirt, 0x4c, 3, (DWORD)cx, (DWORD)cz, (DWORD)&alt[0], 0, 0);
                ho_v(dirt, 0x4c, 3, (DWORD)cx + 1, (DWORD)cz, (DWORD)&alt[1], 0, 0);
                ho_v(dirt, 0x4c, 3, (DWORD)cx, (DWORD)cz + 1, (DWORD)&alt[2], 0, 0);
                ho_v(dirt, 0x4c, 3, (DWORD)cx + 1, (DWORD)cz + 1, (DWORD)&alt[3], 0, 0);
                L = qi_cat(t, cap, L, "terrain.ground_alt: %u %u %u %u\r\n", alt[0], alt[1], alt[2], alt[3]);
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) { L = qi_cat(t, cap, L, "terrain: (fault)\r\n"); }
    }
    if (!occ) { L = qi_cat(t, cap, L, "object: none\r\n"); goto tail; }
    __try {
        DWORD vt = *(DWORD *)occ, *o = (DWORD *)occ, ox = 0, oz = 0, sx, sz, sy, rot = 0, clsid = 0, *k = NULL;
        void *attr;
        BYTE nm[0x20];
        const char *mn = qi_mod_of(vt, &rva), *nmt;
        ho_str(nm, NULL);
        ho_v(occ, 0x7c, 1, (DWORD)nm, 0, 0, 0, 0);
        nmt = (const char *)ho_v(nm, 0x14, 0, 0, 0, 0, 0, 0);
        if (nmt && !IsBadStringPtrA(nmt, 128) && nmt[0]) L = qi_cat(t, cap, L, "object.name: %.80s\r\n", nmt);
        ho_str_free(nm);
        L = qi_cat(t, cap, L, "object.type_id: %lu\r\n", ho_v(occ, 0x88, 0, 0, 0, 0, 0, 0));
        attr = (void *)ho_v(occ, 0x80, 0, 0, 0, 0, 0, 0);
        if (attr) {
            k = (DWORD *)ho_v(attr, 0x14, 0, 0, 0, 0, 0, 0);
            if (k && IsBadReadPtr(k, 12)) k = NULL;
        }
        /* the occupant's own key: its first field points 0x10 past a key block (measured on SIMGEOM buildings, equal
           to the save record's +12 key, also for an abandoned one whose attrib in use is the abandoned look) */
        if (k && o[1] > 0x10000 && !IsBadReadPtr((void *)(o[1] - 0x10), 12)) {
            DWORD *ok = (DWORD *)(o[1] - 0x10);
            if (ok[0] == k[0] && ok[1] == k[1])
                L = qi_cat(t, cap, L, "object.key: 0x%08lX 0x%08lX 0x%08lX\r\n", ok[0], ok[1], ok[2]);
        }
        if (k) L = qi_cat(t, cap, L, "object.attrib_key: 0x%08lX 0x%08lX 0x%08lX\r\n", k[0], k[1], k[2]);
        if (attr) L = qi_cat(t, cap, L, "attrib.type_id: %lu\r\n", ho_v(attr, 0x50, 0, 0, 0, 0, 0, 0));
        ho_v(occ, 0xbc, 2, (DWORD)&ox, (DWORD)&oz, 0, 0, 0);
        L = qi_cat(t, cap, L, "object.cell: x=%lu z=%lu alt=%lu\r\n", ox, oz, ho_v(occ, 0xc0, 0, 0, 0, 0, 0, 0) & 0xff);
        sx = ho_v(occ, 0xd4, 0, 0, 0, 0, 0, 0); sz = ho_v(occ, 0xd8, 0, 0, 0, 0, 0, 0); sy = ho_v(occ, 0xdc, 0, 0, 0, 0, 0, 0);
        L = qi_cat(t, cap, L, "object.size: %lux%lu height=%lu\r\n", sx, sz, sy);
        ho_v(occ, 0xb4, 1, (DWORD)&rot, 0, 0, 0, 0);
        L = qi_cat(t, cap, L, "object.rotation: %lu\r\n", rot);
        L = qi_cat(t, cap, L, "object.class: %s+0x%lX\r\n", mn, rva);
        L = qi_cat(t, cap, L, "object.packed: 0x%08lX\r\n", o[4]);
        if (attr) {
            ho_v(attr, 0x0c, 1, (DWORD)&clsid, 0, 0, 0, 0);
            L = qi_cat(t, cap, L, "attrib.clsid?: 0x%08lX\r\n", clsid);
        }
        if (nt && vt >= (DWORD)nt) {
            for (i = 0; i < 22; i++) if (vt == (DWORD)nt + qi_piece_vt2[i]) break;
            if (i < 22) {
                BYTE *pc = (BYTE *)occ - 4;
                DWORD w0 = *(DWORD *)(pc + 0x14), w1 = *(DWORD *)(pc + 0x18), id = w1 & 0xffff, st = w0 >> 30;
                static const char *nets[6] = { "ROAD", "HWAY", "RAIL", "SUBW", "PIPE", "POWR" };
                static const DWORD lists[6] = { 0x32348, 0x3234c, 0x32350, 0x32354, 0x32358, 0x3235c };
                int j, any = 0;
                L = qi_cat(t, cap, L, "network.piece_id: %lu\r\n", id);
                L = qi_cat(t, cap, L, "network.sets:");
                for (j = 0; j < 6; j++) if (qi_in_list(nt, lists[j], id) == 1) { L = qi_cat(t, cap, L, " %s", nets[j]); any = 1; }
                L = qi_cat(t, cap, L, "%s\r\n", any ? "" : " none");
                L = qi_cat(t, cap, L, "network.state: %lu\r\n", st);
                L = qi_cat(t, cap, L, "network.tile: x=%lu y=%lu z=%lu\r\n", w0 & 0x7ff, (w0 >> 11) & 0x7ff, (w0 >> 22) & 0xff);
                L = qi_cat(t, cap, L, "network.trblkatt_key: 0x625C6226 0x825C6289 0x%08lX\r\n", id * 0x100 + st);
                L = qi_cat(t, cap, L, "network.words: 0x%08lX 0x%08lX\r\n", w0, w1);
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) { L = qi_cat(t, cap, L, "object: (fault while reading)\r\n"); }
tail:
    L = qi_cat(t, cap, L, "query.mode: %lu\r\n", mode);
    L = qi_cat(t, cap, L, "query.coord: 0x%08lX 0x%08lX 0x%08lX\r\n", c[0], c[1], c[2]);
    return L;
}

static void qi_copy(BYTE *qo) {
    static char t[4096];
    int n;
    HGLOBAL h;
    t[0] = 0;
    n = qi_build(qo, t, sizeof(t));
    t[sizeof(t) - 1] = 0;
    logf("QUERYID> copied %d bytes:\n%s", n, t);
    if (!OpenClipboard(g_hwnd)) { logf("QUERYID> OpenClipboard failed (%lu)", GetLastError()); return; }
    EmptyClipboard();
    h = GlobalAlloc(GMEM_MOVEABLE, (SIZE_T)n + 1);
    if (h) {
        char *p = (char *)GlobalLock(h);
        if (p) { memcpy(p, t, (size_t)n + 1); GlobalUnlock(h); }
        if (!SetClipboardData(CF_TEXT, h)) { GlobalFree(h); logf("QUERYID> SetClipboardData failed (%lu)", GetLastError()); }
    }
    /* the game's text is Windows-1252 (the Spanish names log as single bytes, e.g. 0xF3); give the Unicode form too,
       so a paste does not depend on the system code page */
    h = GlobalAlloc(GMEM_MOVEABLE, ((SIZE_T)n + 1) * sizeof(WCHAR));
    if (h) {
        WCHAR *w = (WCHAR *)GlobalLock(h);
        if (w) { MultiByteToWideChar(1252, 0, t, n + 1, w, n + 1); GlobalUnlock(h); }
        if (!SetClipboardData(CF_UNICODETEXT, h)) GlobalFree(h);
    }
    CloseClipboard();
}

static void qi_dump_children(void *win) {
    BYTE *w = (BYTE *)win;
    void *head = *(void **)(w + 0x34), *n;
    int guard = 0;
    LONG *l = (LONG *)(w + 0x80);
    logf("QUERYID>   dialog local [%ld %ld %ld %ld]", l[0], l[1], l[2], l[3]);
    n = (head && !IsBadReadPtr(head, 4)) ? *(void **)head : NULL;
    while (n && n != head && guard++ < 40 && !IsBadReadPtr(n, 0x0c)) {
        BYTE *ch = *(BYTE **)((BYTE *)n + 8);
        if (ch && !IsBadReadPtr(ch, 0xa4)) {
            DWORD rva;
            const char *mn = qi_mod_of(*(DWORD *)ch, &rva);
            LONG *cl = (LONG *)(ch + 0x80);
            logf("QUERYID>   child %s+0x%lX local [%ld %ld %ld %ld] flags 0x%lX", mn, rva, cl[0], cl[1], cl[2], cl[3], *(DWORD *)(ch + 0xa0));
        }
        n = *(void **)n;
    }
}

/* A text button made the way the game makes its own (SIMUI FUN_1003f16b, FUN_1003f900, FUN_1003a303):
   factory +0x2c(id, str, 0, 0, 0), button +0x24(4, 1) and +0x24(0x20, 0), caption = window vt+0x10c(str),
   parent-local rect = window vt+0xc8(l, t, r, b), window vt+0xf4(2, 1), then parent AddChild [CONFIRMED @ SIMUI
   0x1003f16b]. (Factory +0x30 is the image button: without an image it drew an empty pill, measured.)
   Placed on the bottom row, right-aligned against the game's OK button, which the dialog puts at (w - 0x32, h - 0x25),
   32 tall (SIMUI 0x1006260e; measured [258 358 300 390] in a 308x395 dialog). */
#define QI_BW 92
#define QI_BH 33
static void qi_add_button(void *win, BYTE *qo) {
    HMODULE sui = GetModuleHandleA("SIMUI.DLL");
    void *fac, *btn, *bw = NULL;
    BYTE s[0x20];
    LONG *l = (LONG *)((BYTE *)win + 0x80), w, h, bx, by;
    int ok = 0;
    if (!sui || !win || IsBadReadPtr(win, 0xa4)) return;
    if (ho_v(win, 0x78, 1, QI_BTN, 0, 0, 0, 0)) return;
    fac = ((void *(__cdecl *)(void))((BYTE *)sui + 0x85065))();
    if (!fac || IsBadReadPtr(fac, 4)) { logf("QUERYID> no widget factory"); return; }
    w = l[2] - l[0]; h = l[3] - l[1];
    {   static DWORD modes;   /* the layout of the first dialog of each mode, for checking the button against it */
        DWORD md = *(DWORD *)(qo + 0x14) & 31;
        if (!(modes & (1u << md))) {
            modes |= 1u << md;
            logf("QUERYID>   first dialog of mode %lu, children before the button:", md);
            qi_dump_children(win);
        }
    }
    bx = w - 0x32 - 8 - QI_BW;
    by = h - 0x25 + (32 - QI_BH) / 2;
    ho_str(s, ho_spanish() ? "Copiar ID" : "Copy ID");
    btn = (void *)ho_v(fac, 0x2c, 5, QI_BTN, (DWORD)s, 0, 0, 0);
    if (btn) {
        ho_v(btn, 0x24, 2, 4, 1, 0, 0, 0);
        ho_v(btn, 0x24, 2, 0x20, 0, 0, 0, 0);
        bw = (void *)ho_v(btn, 0x1c, 0, 0, 0, 0, 0, 0);
        ho_v(bw, 0x10c, 1, (DWORD)s, 0, 0, 0, 0);
        ho_v(bw, 0xc8, 4, (DWORD)bx, (DWORD)by, (DWORD)(bx + QI_BW), (DWORD)(by + QI_BH), 0);
        ho_v(bw, 0xf4, 2, 2, 1, 0, 0, 0);
        ok = (int)(ho_v(win, 0x34, 1, (DWORD)bw, 0, 0, 0, 0) & 0xff);
        if (!ok) ho_v(bw, 0x28, 0, 0, 0, 0, 0, 0);
        ho_v(btn, 0x08, 0, 0, 0, 0, 0, 0);
    }
    ho_str_free(s);
    logf("QUERYID> dialog 0x%08lX %ldx%ld mode %lu: button %s", (DWORD)win, w, h, *(DWORD *)(qo + 0x14), ok ? "added" : "FAILED");
    if (ok) {
        LONG *bl = (LONG *)((BYTE *)bw + 0x80);
        logf("QUERYID>   button local [%ld %ld %ld %ld]", bl[0], bl[1], bl[2], bl[3]);
    }
}

static DWORD __fastcall qi_msg(void *self, void *edx, DWORD win, DWORD msg, DWORD p3, DWORD p4, DWORD p5) {
    DWORD a[5], r;
    (void)edx;
    if (msg == 3 && p4 == QI_BTN) {
        logf("QUERYID> click (p3 %lu)", p3);
        if (p3 == 1) { qi_copy((BYTE *)self - 4); return 1; }
    }
    a[0] = win; a[1] = msg; a[2] = p3; a[3] = p4; a[4] = p5;
    r = rz_thiscall_ret(self, g_orig_338f, a, 5);
    if (msg == 0xa2bf8ace && (r & 0xff) && win) qi_add_button((void *)win, (BYTE *)self - 4);
    return r;
}

/* PANCURSOR (owner 2026-10-23: "moving camera with right click makes the cursor smaller"). Measured with GetCursorInfo
   during a right-drag: at the press the game sets a centred cursor (hotspot at the middle, the 21x21 centre / four-way
   art), then while dragging it sets the stock PAN ... ARROW.cur cursors, whose art is 15x8 to 17x9 inside the 32x32
   canvas, against the 17x29 pointer. Owner call: keep the four-way cursor for the whole drag. user32!SetCursor is
   redirected in every loaded module's import table; while the right button is held, the first centred cursor set
   after the press is kept and every later SetCursor of that hold gets it instead. SC3RESIZE_PANCURSOR=0 turns it off.
   Import-table pages are left writable (never restore VirtualProtect: mods race on shared pages). */
static int g_pancursor = 1;
typedef HCURSOR (WINAPI *PFN_SETCURSOR)(HCURSOR);
static PFN_SETCURSOR g_orig_setcursor;
static HCURSOR g_pan_keep;
static LONG g_pan_subs;
static int rz_cursor_centred(HCURSOR h) {
    ICONINFO ii;
    BITMAP bm;
    LONG w, hh;
    int ok = 0;
    if (!h || !GetIconInfo(h, &ii)) return 0;
    if (GetObjectA(ii.hbmMask, sizeof(bm), &bm)) {
        w = bm.bmWidth; hh = ii.hbmColor ? bm.bmHeight : bm.bmHeight / 2;
        ok = w > 0 && hh > 0 && labs((LONG)ii.xHotspot * 2 - w) <= w / 32 && labs((LONG)ii.yHotspot * 2 - hh) <= hh / 32;   /* (16,16) of 32, +-1: the pan arrows sit at (14..17, 9..15) */
    }
    if (ii.hbmMask) DeleteObject(ii.hbmMask);
    if (ii.hbmColor) DeleteObject(ii.hbmColor);
    return ok;
}
static HCURSOR g_pan_last;   /* the last cursor this hook let through outside a right-button hold */
static HCURSOR WINAPI rz_setcursor_hook(HCURSOR h) {
    static int dbg;
    HCURSOR in = h;
    int held = (GetAsyncKeyState(VK_RBUTTON) & 0x8000) != 0;
    if (g_pancursor && held && !g_pan_keep && !rz_cursor_centred(h) && g_pan_last && rz_cursor_centred(g_pan_last)) {
        g_pan_keep = g_pan_last;   /* the hover cursor the press kept (no SetCursor at the press) */
    }
    if (g_pancursor && held) {
        if (!g_pan_keep) {
            /* the centred cursor is often already up from hovering the city (no new SetCursor at the press; owner
               recording 2026-10-23: 0xee056b before and through the press, then an arrow 30 ms later) */
            HCURSOR cur = GetCursor();
            if (rz_cursor_centred(h)) g_pan_keep = h;
            else if (cur && cur != h && rz_cursor_centred(cur)) { g_pan_keep = cur; h = cur;
                if (g_pan_subs++ < 3) logf("PANCURSOR> drag cursor replaced by the cursor up at the press"); }
        }
        else if (h != g_pan_keep) { h = g_pan_keep; if (g_pan_subs++ < 3) logf("PANCURSOR> drag cursor replaced by the press cursor"); }
    } else { g_pan_keep = NULL; g_pan_last = h; }
    if (g_pancursor && dbg < 400 && (held || in != h || dbg < 40)) {
        DWORD ra = (DWORD)_ReturnAddress();
        HMODULE m = NULL;
        char mn[32] = "?";
        if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT, (LPCSTR)ra, &m) && m) {
            char full[MAX_PATH], *b; GetModuleFileNameA(m, full, MAX_PATH); b = strrchr(full, 92); lstrcpynA(mn, b ? b + 1 : full, sizeof(mn)); }
        dbg++;
        logf("PANCURSOR> #%d held=%d in=%p centred=%d -> %p keep=%p cur=%p from %s+0x%lX tid %lu", dbg, held, in,
             rz_cursor_centred(in), h, g_pan_keep, GetCursor(), mn, ra - (DWORD)m, GetCurrentThreadId());
    }
    return g_orig_setcursor(h);
}
static int rz_iat_patch(HMODULE m, const char *dll, const char *fn, void *repl, void **orig) {
    BYTE *b = (BYTE *)m;
    IMAGE_DOS_HEADER *dh = (IMAGE_DOS_HEADER *)b;
    IMAGE_NT_HEADERS *nh;
    IMAGE_IMPORT_DESCRIPTOR *id;
    DWORD rva;
    int n = 0;
    if (!b || dh->e_magic != IMAGE_DOS_SIGNATURE) return 0;
    nh = (IMAGE_NT_HEADERS *)(b + dh->e_lfanew);
    rva = nh->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress;
    if (!rva) return 0;
    for (id = (IMAGE_IMPORT_DESCRIPTOR *)(b + rva); id->Name; id++) {
        IMAGE_THUNK_DATA *ot, *ft;
        if (lstrcmpiA((const char *)(b + id->Name), dll)) continue;
        ot = (IMAGE_THUNK_DATA *)(b + (id->OriginalFirstThunk ? id->OriginalFirstThunk : id->FirstThunk));
        ft = (IMAGE_THUNK_DATA *)(b + id->FirstThunk);
        for (; ot->u1.AddressOfData; ot++, ft++) {
            DWORD old;
            if (IMAGE_SNAP_BY_ORDINAL(ot->u1.Ordinal)) continue;
            if (lstrcmpA((const char *)((IMAGE_IMPORT_BY_NAME *)(b + ot->u1.AddressOfData))->Name, fn)) continue;
            if ((void *)ft->u1.Function == repl) continue;
            if (!*orig) *orig = (void *)ft->u1.Function;
            if (VirtualProtect(&ft->u1.Function, sizeof(DWORD), PAGE_READWRITE, &old)) { ft->u1.Function = (DWORD)repl; n++; }
        }
    }
    return n;
}
static void pk_install(void) {
    static const char *mods[] = { NULL, "SIMSPR.DLL", "GZWIND.DLL", "GZGraphicD.dll", "SIMUI.DLL", "SIMCITY.DLL" };
    int i, n = 0;
    if (!g_pancursor) { logf("PANCURSOR> off (SC3RESIZE_PANCURSOR=0)"); return; }
    for (i = 0; i < (int)(sizeof(mods) / sizeof(mods[0])); i++) {
        HMODULE m = mods[i] ? GetModuleHandleA(mods[i]) : GetModuleHandleA(NULL);
        if (m) n += rz_iat_patch(m, "USER32.dll", "SetCursor", (void *)rz_setcursor_hook, (void **)&g_orig_setcursor);
    }
    if (!g_orig_setcursor) g_orig_setcursor = (PFN_SETCURSOR)GetProcAddress(GetModuleHandleA("user32.dll"), "SetCursor");
    logf("PANCURSOR> SetCursor redirected in %d import slot(s): a right-drag keeps the cursor set at the press", n);
}

static void qi_install(HMODULE sui) {
    static const BYTE e338f[6] = { 0x55, 0x8b, 0xec, 0x56, 0x8b, 0xf1 };   /* push ebp; mov ebp,esp; push esi; mov esi,ecx */
    if (!g_queryid) { logf("QUERYID> off (SC3RESIZE_QUERYID=0): no button in the query dialog"); return; }
    if (ho_hook(sui, 0x6338f, e338f, 6, (void *)qi_msg, &g_orig_338f, "query dialog messages FUN_1006338f"))
        logf("QUERYID> on: \"Copiar ID\" button in the query (?) dialog");
}

/* FRAMEDUMP (diag, task hudclick 2026-10-15). SC3RESIZE_FRAMEDUMP=<abs prefix>: when the file <prefix>req exists, the
 * next client-sized Blt onto the primary writes its source rect (the frame exactly as presented, after any HUDSCALE
 * pass) to <prefix><tag>.bmp, tag = the first line of req (else a counter), and deletes req. A smaller Blt onto the
 * primary writes its source surface's client area from (0,0) instead (some dialogs present only their own rect; that
 * area then holds the HUD at native size). Desktop grabs cannot be used while the game window is not in the
 * foreground: the game then presents white/black (verify/menucrop). */
static char  g_fd_prefix[MAX_PATH];
static DWORD g_fd_t, g_fd_n;
static void rz_fd_maybe(void *self, const RECT *dr, void *src, const RECT *sr) {
    char req[MAX_PATH + 8], tag[64], path[MAX_PATH + 80];
    HANDLE f;
    DWORD rd = 0, bpp, gmask, wr;
    LONG pitch, sw, sh, w, h, x, y, rowb;
    RECT cr, all;
    int part;
    BYTE *bits, *row;
    BITMAPFILEHEADER bf;
    BITMAPINFOHEADER bi;
    if (rz_hs_is_screen(self) != 1 || GetTickCount() - g_fd_t < 50) return;   /* only Blts onto the primary count */
    g_fd_t = GetTickCount();
    wsprintfA(req, "%sreq", g_fd_prefix);
    if (GetFileAttributesA(req) == INVALID_FILE_ATTRIBUTES || !GetClientRect(g_hwnd, &cr)) return;
    part = dr->right - dr->left < cr.right || dr->bottom - dr->top < cr.bottom;
    tag[0] = 0;
    f = CreateFileA(req, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, NULL, OPEN_EXISTING, 0, NULL);
    if (f != INVALID_HANDLE_VALUE) {
        if (ReadFile(f, tag, sizeof(tag) - 1, &rd, NULL)) tag[rd] = 0;
        CloseHandle(f);
    }
    for (x = 0; tag[x]; x++) if (tag[x] == '\r' || tag[x] == '\n') { tag[x] = 0; break; }
    if (!tag[0]) wsprintfA(tag, "%03lu", g_fd_n);
    g_fd_n++;
    DeleteFileA(req);
    bits = rz_hs_lock(src, &pitch, &bpp, &gmask, &sw, &sh);
    if (bits && part) {   /* a partial present: the source surface's client-sized area from (0,0), HUD as drawn natively */
        if (sw < cr.right || sh < cr.bottom) { logf("FRAMEDUMP> %s: partial present from a %ldx%ld surface, not dumped", tag, sw, sh);
            ((RZ_UNLOCK)(*(DWORD **)src)[0x80 / 4])(src, NULL); return; }
        all.left = 0; all.top = 0; all.right = cr.right; all.bottom = cr.bottom; sr = &all;
    }
    w = sr->right - sr->left; h = sr->bottom - sr->top;
    if (!bits) { logf("FRAMEDUMP> %s: lock failed", tag); return; }
    if (bpp != 16 || w <= 0 || h <= 0 || sr->left < 0 || sr->top < 0 || sr->right > sw || sr->bottom > sh) {
        logf("FRAMEDUMP> %s: refused (bpp %lu, src [%ld %ld %ld %ld] of %ldx%ld)", tag, bpp, sr->left, sr->top, sr->right, sr->bottom, sw, sh);
        ((RZ_UNLOCK)(*(DWORD **)src)[0x80 / 4])(src, NULL);
        return;
    }
    rowb = (w * 3 + 3) & ~3;
    row = (BYTE *)malloc(rowb);
    wsprintfA(path, "%s%s.bmp", g_fd_prefix, tag);
    f = row ? CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL) : INVALID_HANDLE_VALUE;
    if (f != INVALID_HANDLE_VALUE) {
        memset(&bf, 0, sizeof(bf)); memset(&bi, 0, sizeof(bi));
        bf.bfType = 0x4d42; bf.bfOffBits = sizeof(bf) + sizeof(bi); bf.bfSize = bf.bfOffBits + rowb * h;
        bi.biSize = sizeof(bi); bi.biWidth = w; bi.biHeight = h; bi.biPlanes = 1; bi.biBitCount = 24;
        WriteFile(f, &bf, sizeof(bf), &wr, NULL); WriteFile(f, &bi, sizeof(bi), &wr, NULL);
        memset(row, 0, rowb);
        for (y = h - 1; y >= 0; y--) {
            const WORD *p = (const WORD *)(bits + (sr->top + y) * pitch) + sr->left;
            for (x = 0; x < w; x++) {
                WORD v = p[x];
                BYTE r, g, b;
                if (gmask == 0x07E0) { r = (BYTE)((v >> 11) << 3); g = (BYTE)(((v >> 5) & 63) << 2); }
                else { r = (BYTE)(((v >> 10) & 31) << 3); g = (BYTE)(((v >> 5) & 31) << 3); }
                b = (BYTE)((v & 31) << 3);
                row[x * 3] = b; row[x * 3 + 1] = g; row[x * 3 + 2] = r;
            }
            WriteFile(f, row, rowb, &wr, NULL);
        }
        CloseHandle(f);
        logf("FRAMEDUMP> %s: %ldx%ld frame written to %s%s", tag, w, h, path, part ? " (partial present: source surface from (0,0), HUD native)" : "");
    } else logf("FRAMEDUMP> %s: cannot write %s", tag, path);
    free(row);
    ((RZ_UNLOCK)(*(DWORD **)src)[0x80 / 4])(src, NULL);
}

static HRESULT WINAPI rz_blt_hook_inner(void *self, RECT *dr, void *src, RECT *sr, DWORD fl, void *fx) {
    LARGE_INTEGER a, b;
    HRESULT hr;
    int hs_did;
    __int64 d;
    RECT sfix;
    if (rz_mb_present(self, dr, src, sr, fl, fx, &hr)) return hr;
    /* EVENT-STYLE LAYOUT (owner 2026-10-07: "reposition of the elements looks buggy while it loads").
       On the FINAL present (dest covers the client):
         - HOLD: while a fresh city view / newly shown HUD is waiting for its layout pass, skip the
           present so the half-built native layout is never shown; the previous frame stays up.
           Capped at RZ_HOLD_MAX_MS after the trigger so a layout that never runs cannot black out.
         - DIALOGS: place dialogs right before the frame goes out, not on a 100 ms timer, so a dialog
           never shows a frame at its old spot. SC3RESIZE_HOLD=0 disables both. */
    if (g_hold && dr && g_hwnd && !IsBadReadPtr(dr, sizeof(RECT))) {
        RECT crh;
        if (GetClientRect(g_hwnd, &crh) && dr->right - dr->left >= crh.right - crh.left &&
            dr->bottom - dr->top >= crh.bottom - crh.top) {
            LONG cw = crh.right - crh.left, ch = crh.bottom - crh.top;
            if (g_bridge_fresh && !(cw == NAT_W && ch == NAT_H) && GetTickCount() - g_bridge_ms < RZ_HOLD_MAX_MS) {
                if (!g_hold_logged) { g_hold_logged = 1; logf("HOLD> presents held until the layout pass runs"); }
                g_hold_frames++;
                return 0;   /* DD_OK: nothing drawn, previous frame stays on screen */
            }
            if (g_hold_logged) {
                logf("HOLD> released after %ld held present(s)", g_hold_frames);
                g_hold_logged = 0; g_hold_frames = 0;
            }
            if (g_dialogs) rz_dialogs_poll(cw, ch);
        }
    }
    if (g_mb_active && dr && g_hwnd && !IsBadReadPtr(dr, sizeof(RECT))) {   /* another full-window frame: menu over */
        RECT crm;
        if (GetClientRect(g_hwnd, &crm) && dr->right - dr->left >= crm.right - crm.left &&
            dr->bottom - dr->top >= crm.bottom - crm.top) {
            if (g_ms_on) logf("MENUSCALE> menu over: full-window present of another frame (src %ldx%ld), mapping off",
                              sr && !IsBadReadPtr(sr, sizeof(RECT)) ? sr->right - sr->left : -1,
                              sr && !IsBadReadPtr(sr, sizeof(RECT)) ? sr->bottom - sr->top : -1);
            g_mb_active = 0; g_ms_on = 0;
        }
    }
    /* ⭐⭐ THE BOTTOM STRIP: the present squashes the frame by the slack rows.
     *
     * Measured 2026-09-02 with the present logger:
     *     dst [0 23 2048 1104] = 2048x1081      src [0 0 2048 1089] = 2048x1089
     * The render target is deliberately over-allocated by RZ_SURFACE_SLACK guard rows (the
     * zoom-blit overrun fix), and the present blits the WHOLE surface into the client-sized
     * destination - so every frame is compressed vertically by 8 rows AND the surface's bottom 8
     * rows are squeezed into view. Those rows are the part of the bar that hangs below the client
     * (the bar sits at 1033..1089 with the 8px bias), which is exactly the owner's report: "part of
     * the bottom is not rendering the game, it stays the color of the bottom bar".
     *
     * Fix: for the final present only - destination at least the client size - clamp the SOURCE to
     * the destination's height so the mapping is 1:1 and the slack rows are never shown. A COPY of
     * the caller's rect is passed; the caller's own structure is never modified.
     * SC3RESIZE_PRESENTFIX=0 disables it for an A/B. */
    if (g_presentfix && dr && sr && !IsBadReadPtr(dr, sizeof(RECT)) && !IsBadReadPtr(sr, sizeof(RECT))) {
        RECT cr3;
        if (g_hwnd && GetClientRect(g_hwnd, &cr3)) {
            LONG dw = dr->right - dr->left, dh = dr->bottom - dr->top;
            LONG sw = sr->right - sr->left, sh = sr->bottom - sr->top;
            if (dw >= cr3.right - cr3.left && dh >= cr3.bottom - cr3.top && sh > dh && sw == dw) {
                sfix = *sr;
                sfix.bottom = sfix.top + dh;
                if (!g_presentfix_logged) {
                    g_presentfix_logged = 1;
                    logf("PRESENTFIX> src %ldx%ld -> %ldx%ld to match the %ldx%ld dest "
                         "(was squashing the frame and showing %ld slack row(s))",
                         sw, sh, sw, dh, dw, dh, sh - dh);
                }
                sr = &sfix;
            }
        }
    }
    /* ⭐ RCI OVERHANG FIX: this Blt is the FINAL present (composite -> screen) when the dest is at
     * least the client size. Just before it fires, re-composite the RCI onto the composite so its
     * overhang draws over the viewport (see rz_repaint_rci). Only in cluster+bar_span, where the RCI
     * was moved and the viewport spans the full client. */
    if (g_rcifix && g_cluster && g_bar_span && dr && !IsBadReadPtr(dr, sizeof(RECT))) {
        RECT crx;
        if (g_hwnd && GetClientRect(g_hwnd, &crx) &&
            dr->right - dr->left >= crx.right - crx.left &&
            dr->bottom - dr->top >= crx.bottom - crx.top) {
            rz_repaint_rci();
        }
    }
    hs_did = 0;
    if (g_hudscale && g_hudfix && g_hs_comp && g_hwnd) {   /* HUDFIX: record what is drawn into the composite */
        RECT crr;
        if (GetClientRect(g_hwnd, &crr)) rz_hs_record(self, dr, src, sr, fl, fx, crr.right, crr.bottom);
    }
    if (g_hs_diag >= 2 && dr && !IsBadReadPtr(dr, sizeof(RECT))) {   /* sequence dump: every Blt for 40 calls every 3 s */
        static DWORD seq_t, seq_n;
        DWORD caps[4] = {0, 0, 0, 0}, scaps[4] = {0, 0, 0, 0};
        if (!seq_t) seq_t = GetTickCount();
        if (GetTickCount() - seq_t >= 3000) { seq_t = GetTickCount(); seq_n = 40; logf("HSSEQ> ---- 40 Blts ----"); }
        if (seq_n) {
            seq_n--;
            ((HRESULT (WINAPI *)(void *, DWORD *))(*(DWORD **)self)[0x38 / 4])(self, caps);
            if (src && !IsBadReadPtr(src, 4)) ((HRESULT (WINAPI *)(void *, DWORD *))(*(DWORD **)src)[0x38 / 4])(src, scaps);
            logf("HSSEQ> dst 0x%08lX caps %08lX [%ld %ld %ld %ld] <- src 0x%08lX caps %08lX %s fl %08lX", (DWORD)self, caps[0],
                 dr->left, dr->top, dr->right, dr->bottom, (DWORD)src, scaps[0],
                 sr && !IsBadReadPtr(sr, sizeof(RECT)) ? "sr" : "-", fl);
        }
    }
    if (g_hs_diag && g_hudscale && g_hwnd) {   /* census: what reaches the screen, and what the enlarge pass skipped */
        RECT crd;
        int full = 0;
        if (GetClientRect(g_hwnd, &crd)) {
            if (!dr || IsBadReadPtr(dr, sizeof(RECT))) { if (self == g_hs_primary) g_hsd_null++; }
            else if (dr->right - dr->left >= crd.right && dr->bottom - dr->top >= crd.bottom) full = 1;
            else if (self == g_hs_primary) {
                g_hsd_part++;
                if (src == g_hs_lastsrc) g_hsd_partc++;
                if (g_hsd_logn < 60) { g_hsd_logn++;
                    logf("HSDIAG> partial blit on the presented surface: dest [%ld %ld %ld %ld] src 0x%08lX%s sr %s",
                         dr->left, dr->top, dr->right, dr->bottom, (DWORD)src, src == g_hs_lastsrc ? " (the composite)" : "",
                         sr && !IsBadReadPtr(sr, sizeof(RECT)) ? "set" : "NULL"); }
            }
        }
        if (full) g_hsd_full++;
        if (!g_hsd_beat) g_hsd_beat = GetTickCount();
        if (GetTickCount() - g_hsd_beat >= 1000) {
            logf("HSDIAG> 1s: full presents %lu, enlarged %lu, skipped by check 1..9: %lu %lu %lu %lu %lu %lu %lu %lu %lu; partial on presented %lu (from composite %lu), null-rect %lu",
                 g_hsd_full, g_hsd_did, g_hsd_why[1], g_hsd_why[2], g_hsd_why[3], g_hsd_why[4], g_hsd_why[5], g_hsd_why[6],
                 g_hsd_why[7], g_hsd_why[8], g_hsd_why[9], g_hsd_part, g_hsd_partc, g_hsd_null);
            g_hsd_beat = GetTickCount(); g_hsd_full = g_hsd_did = g_hsd_part = g_hsd_partc = g_hsd_null = 0;
            memset(g_hsd_why, 0, sizeof(g_hsd_why));
        }
    }
    if (g_hudscale && dr && sr && src && g_hwnd && !IsBadReadPtr(dr, sizeof(RECT)) && !IsBadReadPtr(sr, sizeof(RECT))) {
        RECT crh2;
        if (GetClientRect(g_hwnd, &crh2) && dr->right - dr->left >= crh2.right - crh2.left &&
            dr->bottom - dr->top >= crh2.bottom - crh2.top) {
            int scr = rz_hs_is_screen(self);
            {   LARGE_INTEGER h0, h1;
                QueryPerformanceCounter(&h0);
                hs_did = (g_hudfix && scr == 0) ? 0
                       : rz_hs_pre(src, sr, crh2.right - crh2.left, crh2.bottom - crh2.top, scr != 0);
                QueryPerformanceCounter(&h1);
                if (scr != 0) g_czd_hs += h1.QuadPart - h0.QuadPart;
            }
            if (g_hudfix && scr != 0 && src != g_hs_comp) { g_hs_comp = src; g_hs_nrec = 0; g_hs_recover = 1; }
            if (g_hs_diag) { if (hs_did) g_hsd_did++; else if (g_hs_why > 0 && g_hs_why < 12) g_hsd_why[g_hs_why]++; }
            if (hs_did) { g_hs_primary = self; g_hs_lastsrc = src; }
        } else if (g_hs_n > 0 && self == g_hs_primary) {
            static int hs_part;
            if (hs_part++ < 10)
                logf("HUDSCALE> blit onto the presented surface 0x%08lX while active: dest [%ld %ld %ld %ld] src 0x%08lX (last full present src 0x%08lX)",
                     (DWORD)self, dr->left, dr->top, dr->right, dr->bottom, (DWORD)src, (DWORD)g_hs_lastsrc);
        }
    }
    if (g_fd_prefix[0] && dr && sr && src && g_hwnd && !IsBadReadPtr(dr, sizeof(RECT)) && !IsBadReadPtr(sr, sizeof(RECT)))
        rz_fd_maybe(self, dr, src, sr);   /* FRAMEDUMP diag: the frame as it goes to the screen */
    QueryPerformanceCounter(&a);
    hr = -1;
    if (g_cz_inblt && src == g_cz_surf) { g_cz_inblt = 0; hr = cz_stretch_blt(self); }   /* task cityzoom: stretched */
    else if (cz_defer1(self, dr, src, sr, fl, fx)) hr = 0;                                 /* task cityzoom: x1 owed */
    if (hr) hr = g_orig_blt(self, dr, src, sr, fl, fx);
    QueryPerformanceCounter(&b);
    if (g_cz_diag && dr && g_hwnd && !IsBadReadPtr(dr, sizeof(RECT)) && rz_hs_is_screen(self) == 1) {
        RECT cq;
        if (GetClientRect(g_hwnd, &cq) && dr->right - dr->left >= cq.right && dr->bottom - dr->top >= cq.bottom) {
            DWORD now = GetTickCount();
            LONG ox = 0, oy = 0;
            g_czd_pres += b.QuadPart - a.QuadPart; g_czd_n++;
            if (g_czd_last && now - g_czd_last > g_czd_maxiv) g_czd_maxiv = now - g_czd_last;
            g_czd_last = now;
            if (g_bridge && !IsBadReadPtr(g_bridge, 0x1c)) {
                DWORD iso = ((DWORD *)g_bridge)[0x18 / 4];
                if (iso && !IsBadReadPtr((void *)iso, 0x60)) { ox = ((LONG *)iso)[0x54 / 4]; oy = ((LONG *)iso)[0x58 / 4]; }
            }
            g_czd_moved += (DWORD)(labs(ox - g_czd_ox) + labs(oy - g_czd_oy)); g_czd_ox = ox; g_czd_oy = oy;
            if (!g_czd_t0) g_czd_t0 = now;
            if (now - g_czd_t0 >= 1000 && g_czd_n) {
                double q = 1000.0 / (double)g_freq.QuadPart / g_czd_n;
                static DWORD lpx; static __int64 lcomp, lepx;   /* HUDPERF counters reset every 10 s: deltas, guarded */
                DWORD dpx = g_hpd_px >= lpx ? g_hpd_px - lpx : g_hpd_px;
                __int64 dcomp = g_hpd_comp >= lcomp ? g_hpd_comp - lcomp : g_hpd_comp, depx = g_hst[3] >= lepx ? g_hst[3] - lepx : g_hst[3];
                lpx = g_hpd_px; lcomp = g_hpd_comp; lepx = g_hst[3];
                {   static DWORD lmk; DWORD dmk = g_hpd_masked >= lmk ? g_hpd_masked - lmk : g_hpd_masked; lmk = g_hpd_masked;
                    {   BYTE *cv = (BYTE *)rz_city_view();   /* the right-drag state (DRAGANCHOR) */
                    if (cv && !IsBadReadPtr(cv - 4, 0x200)) {
                        BYTE *b = cv - 4;
                        logf("CZDIAG> drag: vt %08lX +1e1..1e7 %02X %02X %02X %02X %02X %02X %02X anchor (%d,%d) vel %ld %ld (%08lX %08lX)",
                             *(DWORD *)b - (DWORD)GetModuleHandleA("SIMSPR.DLL"), b[0x1e1], b[0x1e2], b[0x1e3], b[0x1e4], b[0x1e5],
                             b[0x1e6], b[0x1e7], *(short *)(b + 0x1ec), *(short *)(b + 0x1ee), *(LONG *)(b + 0x1f4),
                             *(LONG *)(b + 0x1f8), *(DWORD *)(b + 0x1f4), *(DWORD *)(b + 0x1f8));
                    }
                }
                logf("CZDIAG> hud: rebuilt %lu px/frame, compose %.2f ms, minimap 2x %.2f ms, masked rows %lu/frame", dpx / g_czd_n,
                         dcomp * q, depx * q, dmk / g_czd_n); }
                logf("CZDIAG> x%ld %s: %lu presents in %lu ms, %s (%lu view px), interval avg %.1f max %lu ms; per frame: "
                     "stretch %.2f (copied %lu px), hud-city fill %.2f (%lu px), hud pass %.2f (incl. fill), present %.2f ms; "
                     "defer: dropped %lu, paid by Blt onto %lu / Blt from %lu / Lock %lu / overflow %lu; skipped %lu px", g_cz_f,
                     g_cz_filt ? "smooth" : "nearest", g_czd_n, now - g_czd_t0, g_czd_moved ? "MOVING" : "still",
                     g_czd_moved, (double)(now - g_czd_t0) / g_czd_n, g_czd_maxiv, g_czd_str * q, g_czd_copypx / g_czd_n, g_czd_fill * q,
                     g_czd_fillpx / g_czd_n, g_czd_hs * q, g_czd_pres * q, g_czd_drop, g_czd_pay[0], g_czd_pay[1], g_czd_pay[2],
                     g_czd_pay[3], g_czd_skippx / g_czd_n);
                g_czd_drop = 0; memset(g_czd_pay, 0, sizeof(g_czd_pay)); g_czd_skippx = 0;
                g_czd_t0 = now; g_czd_n = 0; g_czd_maxiv = 0; g_czd_moved = 0;
                g_czd_fill = g_czd_hs = g_czd_pres = g_czd_str = 0; g_czd_fillpx = 0; g_czd_copypx = 0;
            }
        }
    }
    if (hs_did) {
        if (g_hudperf && g_hudfix && g_hp_lazy && rz_hp_lazy_ready(src)) {   /* HUDPERF: owe the restore */
            if (g_hp_pend) g_hpd_lzdrop++;
            g_hp_pendsr = *sr;
            g_hp_pend = src;
        } else rz_hs_post(src, sr);
    }
    d = b.QuadPart - a.QuadPart;
    if (g_hudscale && self == g_hs_comp && dr && g_hwnd && !IsBadReadPtr(dr, sizeof(RECT))) {   /* HUDPERF diag: the frame's city -> composite Blt */
        RECT crc;
        if (GetClientRect(g_hwnd, &crc) && dr->left <= 0 && dr->top <= 0 && dr->right >= crc.right && dr->bottom >= crc.bottom) { g_hpd_cityblt += d; g_hpd_citybn++; }
    }
    g_ddblt_time += d;
    g_ddblt_calls++;
    /* BLT HEARTBEAT (SC3RESIZE_BLTBEAT): report Blt calls/sec and ms-in-Blt/sec, so the full-width
     * bar's per-frame cost is a measured number. Frame rate itself is not counted, but a present is
     * one Blt/frame, so calls/sec upper-bounds FPS and calls-per-present exposes the tiling growth. */
    if (g_bltbeat) {
        static DWORD beat_ms, beat_calls; static __int64 beat_time;
        DWORD now3 = GetTickCount();
        if (!beat_ms) beat_ms = now3;
        if (now3 - beat_ms >= 1000) {
            double ms = g_freq.QuadPart ? (1000.0 * (double)beat_time / (double)g_freq.QuadPart) : 0.0;
            logf("BLTBEAT> %lu Blt/sec, %.2f ms/sec inside Blt (%.3f ms avg)",
                 beat_calls, ms, beat_calls ? ms / beat_calls : 0.0);
            beat_ms = now3; beat_calls = 0; beat_time = 0;
        }
        beat_calls++; beat_time += d;
    }
    /* PRESENT GEOMETRY LOG. The composited surface is provably correct across a minimize (row-by-row
     * identical), yet the owner still sees a strip at the bottom of the WINDOW - so the defect is
     * downstream of the composite, in the present itself. A present is a Blt with a SOURCE rect and
     * a DEST rect; if those disagree in height the image is scaled or clipped and a band at the
     * bottom shows something else. Logging both costs nothing and needs no COM call on the primary
     * (this project has been burned locking surfaces out of band). Rate-limited to one line/sec. */
    if (g_presentlog && dr && !IsBadReadPtr(dr, sizeof(RECT))) {
        RECT cr2;
        if (g_hwnd && GetClientRect(g_hwnd, &cr2) &&
            dr->right - dr->left >= cr2.right - cr2.left &&
            dr->bottom - dr->top >= cr2.bottom - cr2.top) {
            static DWORD next_present_ms;
            DWORD now2 = GetTickCount();
            if (now2 >= next_present_ms) {
                next_present_ms = now2 + 1000;
                if (sr && !IsBadReadPtr(sr, sizeof(RECT)))
                    logf("PRESENT> dst [%ld %ld %ld %ld] %ldx%ld  src [%ld %ld %ld %ld] %ldx%ld  "
                         "client %ldx%ld  surf=0x%08lX",
                         dr->left, dr->top, dr->right, dr->bottom,
                         dr->right - dr->left, dr->bottom - dr->top,
                         sr->left, sr->top, sr->right, sr->bottom,
                         sr->right - sr->left, sr->bottom - sr->top,
                         cr2.right - cr2.left, cr2.bottom - cr2.top, (DWORD)src);
                else
                    logf("PRESENT> dst [%ld %ld %ld %ld] %ldx%ld  src NULL (whole surface)  "
                         "client %ldx%ld  surf=0x%08lX",
                         dr->left, dr->top, dr->right, dr->bottom,
                         dr->right - dr->left, dr->bottom - dr->top,
                         cr2.right - cr2.left, cr2.bottom - cr2.top, (DWORD)src);
            }
        }
    }

    /* THE FULL-FRAME CAPTURE POINT. The final present blits the whole composited frame to the
       window (measured: dest [0 23 2048 1104] via GZGraphicD+0x16C3D, i.e. client-sized and offset
       by the title bar). Capturing right after it guarantees the HUD is already composited. */
    if (g_dump_pending && dr && !IsBadReadPtr(dr, sizeof(RECT))) {
        RECT cr;
        if (g_hwnd && GetClientRect(g_hwnd, &cr) &&
            dr->right - dr->left >= cr.right - cr.left &&
            dr->bottom - dr->top >= cr.bottom - cr.top) {
            g_dump_pending = 0;
            logf("DUMP> present seen (dest [%ld %ld %ld %ld]) - capturing the composited frame",
                 dr->left, dr->top, dr->right, dr->bottom);
            rz_dump_all(g_dump_iso);
        }
    }
    {   /* time by flags */
        DWORD i;
        for (i = 0; i < BFL_BUCKETS; i++) {
            if (g_bfl_cnt[i] == 0) { g_bfl_key[i] = fl; g_bfl_cnt[i] = 1; g_bfl_time[i] = d; break; }
            if (g_bfl_key[i] == fl) { g_bfl_cnt[i]++; g_bfl_time[i] += d; break; }
        }
    }
    if (src && (DWORD)src == g_ret_filter) {
        /* EXACT caller of this Blt - the engine code driving the tile loop. */
        DWORD ra = g_wrapper_caller ? g_wrapper_caller : (DWORD)_ReturnAddress(), i;
        {   DWORD j;

            for (j = 0; j < L_BUCKETS; j++) {

                if (g_l2_cnt[j] == 0) { g_l2_key[j] = g_caller_l2; g_l2_cnt[j] = 1; break; }

                if (g_l2_key[j] == g_caller_l2) { g_l2_cnt[j]++; break; }

            }

            for (j = 0; j < L_BUCKETS; j++) {

                if (g_l3_cnt[j] == 0) { g_l3_key[j] = g_caller_l3; g_l3_cnt[j] = 1; break; }

                if (g_l3_key[j] == g_caller_l3) { g_l3_cnt[j]++; break; }

            }

        }
        for (i = 0; i < RET_BUCKETS; i++) {
            if (g_ret_cnt[i] == 0) { g_ret_key[i] = ra; g_ret_cnt[i] = 1; g_ret_time[i] = d; break; }
            if (g_ret_key[i] == ra) { g_ret_cnt[i]++; g_ret_time[i] += d; break; }
        }
    }
    {   /* time by SOURCE surface - separates the bar's blit from the scene's within one dest */
        DWORD k = (DWORD)src, i;
        for (i = 0; i < SRC_BUCKETS; i++) {
            if (g_src_cnt[i] == 0 || g_src_key[i] == k) {

                if (g_src_cnt[i] == 0) { g_src_key[i] = k; g_src_cnt[i] = 0; g_src_time[i] = 0; }

                g_src_cnt[i]++; g_src_time[i] += d;

                if (dr && !IsBadReadPtr(dr, sizeof(RECT))) {

                    g_src_rect[i][0] = dr->left;  g_src_rect[i][1] = dr->top;

                    g_src_rect[i][2] = dr->right; g_src_rect[i][3] = dr->bottom;

                }

                break;

            }
        }
    }
    if (dr && !IsBadReadPtr(dr, sizeof(RECT))) {

        LONG w = dr->right - dr->left, h = dr->bottom - dr->top;

        if (w >= 100 && w <= 400 && h >= 100 && h <= 400 && w < h * 2 && h < w * 2) {

            DWORD j;

            g_mm_src = (DWORD)src; g_mm_w = (DWORD)w; g_mm_h = (DWORD)h;

            for (j = 0; j < MM_BUCKETS; j++) {

                if (g_mm_l1c[j] == 0 || g_mm_l1[j] == g_wrapper_caller) {

                    g_mm_l1[j] = g_wrapper_caller; g_mm_l1c[j]++; break; }

            }

            for (j = 0; j < MM_BUCKETS; j++) {

                if (g_mm_l2c[j] == 0 || g_mm_l2[j] == g_caller_l2) {

                    g_mm_l2[j] = g_caller_l2; g_mm_l2c[j]++; break; }

            }

        }

    }

    if (!src) g_blt_nullsrc++;
    if (!dr) {
        g_blt_nullrect++;                      /* NULL dest rect = whole surface */
    } else if (!IsBadReadPtr(dr, sizeof(RECT))) {
        LONG w = dr->right - dr->left, h = dr->bottom - dr->top;
        if (w > 0 && h > 0) {
            g_blt_area += (__int64)w * h;
            g_blt_areacnt++;
            if (w > g_blt_maxw) g_blt_maxw = w;
            if (h > g_blt_maxh) g_blt_maxh = h;
        }
    }
    return hr;
}
/* HUDPERF LAZYRESTORE: settle or cancel an owed restore before the Blt touches that surface. */
static HRESULT WINAPI rz_blt_hook_debt(void *self, RECT *dr, void *src, RECT *sr, DWORD fl, void *fx) {
    void *p = g_hp_pend;
    if (p && (self == p || src == p)) {
        if (self == p && src != p && rz_hp_covers(dr, fl) &&
            InterlockedCompareExchangePointer((PVOID volatile *)&g_hp_pend, NULL, p) == p) {
            HRESULT hr = rz_blt_hook_inner(self, dr, src, sr, fl, fx);
            if (hr == 0) g_hpd_lzskip++;
            else { g_hpd_lzlate[0]++; rz_hs_post(p, &g_hp_pendsr); }
            return hr;
        }
        if (self == p && src != p && dr && !IsBadReadPtr(dr, sizeof(RECT))) {
            static int logged;
            if (logged < 5 && dr->left <= 0 && dr->top <= 0) {
                logged++;
                logf("HUDPERF> owed restore paid: Blt onto the frame [%ld %ld %ld %ld] flags 0x%08lX", dr->left, dr->top,
                     dr->right, dr->bottom, fl);
            }
        }
        rz_hp_settle(p, self == p ? 0 : 1);
    }
    return rz_blt_hook_inner(self, dr, src, sr, fl, fx);
}

/* task cityzoom: with a factor, the game's Blt of the view (cw/f x ch/f) into the composite becomes a client-sized Blt
   from the view's [0 0 cw/f ch/f], which rz_blt_hook_inner then does with cz_stretch. Everything downstream (HUDFIX
   records, the lazy restore, the RCI fix, HUDPERF stats) sees the client-sized city Blt it sees without a factor. */
static HRESULT WINAPI rz_blt_hook(void *self, RECT *dr, void *src, RECT *sr, DWORD fl, void *fx) {
    HRESULT hr;
    RECT cd, cs;
    static LONG diag_f;
    static int diag_n;
    if (g_cz_f != diag_f) { diag_f = g_cz_f; diag_n = 0; }
    if (g_cz_f > 1 && src && src != self && g_hwnd && (src == g_cz_surf || src == g_cz_devsurf) && diag_n < 8) {
        diag_n++;
        logf("CITYZOOM> Blt %s: dst 0x%08lX [%ld %ld %ld %ld] <- src 0x%08lX [%ld %ld %ld %ld] fl %08lX",
             src == g_cz_surf ? "view -> frame" : "frame -> screen", (DWORD)self,
             dr && !IsBadReadPtr(dr, sizeof(RECT)) ? dr->left : -1, dr && !IsBadReadPtr(dr, sizeof(RECT)) ? dr->top : -1,
             dr && !IsBadReadPtr(dr, sizeof(RECT)) ? dr->right : -1, dr && !IsBadReadPtr(dr, sizeof(RECT)) ? dr->bottom : -1,
             (DWORD)src, sr && !IsBadReadPtr(sr, sizeof(RECT)) ? sr->left : -1, sr && !IsBadReadPtr(sr, sizeof(RECT)) ? sr->top : -1,
             sr && !IsBadReadPtr(sr, sizeof(RECT)) ? sr->right : -1, sr && !IsBadReadPtr(sr, sizeof(RECT)) ? sr->bottom : -1, fl);
    }
    if (g_cz_f > 1 && src && src != self && src == g_cz_surf) {   /* census for the 10-s line */
        if (self != g_cz_devsurf) g_cz_nother++;
        else if (dr && !IsBadReadPtr(dr, sizeof(RECT)) && (dr->left > 0 || dr->top > 0 || dr->right < g_cz_vw - 1 ||
                 dr->bottom < g_cz_vh - 1)) { g_cz_npart++; g_cz_lastpart = *dr; }
        else g_cz_nfull[dr && !IsBadReadPtr(dr, sizeof(RECT)) && dr->bottom > g_cz_vh ? 1 : 0]++;
    }
    if (g_czp_on && !(src && src == g_cz_surf && self == g_czp_frame)) cz_touch(self, dr, src, sr, fl, fx);   /* DEFER */
    if (g_cz_f > 1 && src && src != self && src == g_cz_surf && g_hwnd && GetClientRect(g_hwnd, &cd) &&
        (!dr || (!IsBadReadPtr(dr, sizeof(RECT)) && dr->left <= 0 && dr->top <= 0 &&
                 dr->right >= g_cz_vw - 1 && dr->bottom >= g_cz_vh - 1))) {
        cs.left = 0; cs.top = 0; cs.right = cd.right / g_cz_f; cs.bottom = cd.bottom / g_cz_f;   /* ddraw fallback */
        g_cz_inblt = 1; g_cz_nrw++;
        hr = rz_blt_hook_debt(self, &cd, src, &cs, fl, fx);
        g_cz_inblt = 0;
        return hr;
    }
    return rz_blt_hook_debt(self, dr, src, sr, fl, fx);
}

/* Install the same Blt hook from any IDirectDrawSurface (the menu has no city view to find one through):
   the GZGraphicD blit wrapper FUN_10018c58 holds its destination surface at this+4. */
static void rz_patch_ddblt_surf(DWORD surf) {
    DWORD ddbase = (DWORD)GetModuleHandleA("ddraw.dll"), ddsize, e, *svt, old;
    if (g_blt_slot || !ddbase || !surf || IsBadReadPtr((void *)surf, 4)) return;
    e = *(DWORD *)(ddbase + 0x3c);
    if (IsBadReadPtr((void *)(ddbase + e + 0x50), 4)) return;
    ddsize = *(DWORD *)(ddbase + e + 0x50);
    svt = *(DWORD **)surf;
    if (!svt || IsBadReadPtr(svt, 0x84)) return;
    if (svt[0x14 / 4] < ddbase || svt[0x14 / 4] >= ddbase + ddsize) return;
    if (!VirtualProtect(&svt[0x14 / 4], 4, PAGE_EXECUTE_READWRITE, &old)) return;
    g_orig_blt = (RZ_BLT)svt[0x14 / 4];
    svt[0x14 / 4] = (DWORD)rz_blt_hook;
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    g_blt_slot = &svt[0x14 / 4];
    logf("BLT> ddraw Blt hooked from the blit wrapper's surface (menu): slot 0x%08lX, original 0x%08lX",
         (DWORD)g_blt_slot, (DWORD)g_orig_blt);
}

static void rz_patch_ddblt(void) {
    DWORD ddbase = (DWORD)GetModuleHandleA("ddraw.dll"), ddsize = 0, e;
    void *iso, *R; DWORD sub, surf, *svt, old;
    if (g_blt_slot) return;                                  /* already installed */
    if (!ddbase || !g_bridge || IsBadReadPtr(g_bridge, 0x1c)) return;
    e = *(DWORD *)(ddbase + 0x3c);
    if (IsBadReadPtr((void *)(ddbase + e + 0x50), 4)) return;
    ddsize = *(DWORD *)(ddbase + e + 0x50);
    iso = (void *)((DWORD *)g_bridge)[0x18 / 4];
    if (!iso || IsBadReadPtr(iso, 0x78)) return;
    R = (void *)((DWORD *)iso)[0x74 / 4];
    if (!R || IsBadReadPtr(R, 0x48)) return;
    sub = ((DWORD *)R)[0x44 / 4];
    if (!sub || IsBadReadPtr((void *)sub, 8)) return;
    surf = ((DWORD *)sub)[0x04 / 4];                         /* IDirectDrawSurface* */
    if (!surf || IsBadReadPtr((void *)surf, 4)) return;
    svt = *(DWORD **)surf;
    if (!svt || IsBadReadPtr(svt, 0x18)) return;
    if (svt[0x14 / 4] < ddbase || svt[0x14 / 4] >= ddbase + ddsize) {
        logf("BLT> REFUSE ddraw hook: vt+0x14 = 0x%08lX is outside ddraw.dll "
             "(0x%08lX..0x%08lX) - not the vtable we think", svt[0x14 / 4], ddbase, ddbase + ddsize);
        g_blt_slot = (DWORD *)-1;                            /* do not retry every frame */
        return;
    }
    if (!VirtualProtect(&svt[0x14 / 4], 4, PAGE_EXECUTE_READWRITE, &old)) return;
    g_orig_blt = (RZ_BLT)svt[0x14 / 4];
    svt[0x14 / 4] = (DWORD)rz_blt_hook;
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    g_blt_slot = &svt[0x14 / 4];
    logf("BLT> ddraw Blt hooked: vt+0x14 slot at 0x%08lX, original 0x%08lX (ddraw+0x%lX)",
         (DWORD)g_blt_slot, (DWORD)g_orig_blt, (DWORD)g_orig_blt - ddbase);
}

static void rz_prof_hit(DWORD eip) {
    DWORD k = (eip >> 6) + 1;
    DWORD i = (k * 2654435761u) >> 19 & (PROF_BUCKETS - 1);
    DWORD tries = 0;
    while (tries++ < 64) {
        if (g_prof_key[i] == k) { g_prof_cnt[i]++; g_prof_n++; return; }
        if (g_prof_key[i] == 0) { g_prof_key[i] = k; g_prof_cnt[i] = 1; g_prof_n++; return; }
        i = (i + 1) & (PROF_BUCKETS - 1);
    }
    g_prof_fail++;
}
static void rz_prof_reset(void) {
    memset((void *)g_prof_key, 0, sizeof(g_prof_key));
    memset((void *)g_prof_cnt, 0, sizeof(g_prof_cnt));
    memset((void *)g_stk_key, 0, sizeof(g_stk_key));
    memset((void *)g_stk_cnt, 0, sizeof(g_stk_cnt));
    g_prof_n = 0; g_prof_fail = 0; g_stk_n = 0; g_stk_miss = 0;
    rz_prof_modinit();   /* refresh module ranges; DLLs may have loaded since the last phase */
}
/* Dump the top 30 buckets, each resolved to MODULE+RVA. Selection-scan rather than a sort: 30 passes
 * over 8192 slots is trivial and needs no scratch allocation. */
static void rz_prof_dump(const char *tag) {
    DWORD used = 0, i, rank;
    static DWORD taken[32];
    for (i = 0; i < PROF_BUCKETS; i++) if (g_prof_key[i]) used++;
    logf("PROF> ---- %s ---- samples=%lu distinct-buckets=%lu probe-fail=%lu tid=%lu",
         tag, g_prof_n, used, g_prof_fail, g_game_tid);
    if (g_prof_n < 200)
        logf("PROF> %s: FEWER THAN 200 SAMPLES - pre-registered VOID, do not interpret", tag);
    for (rank = 0; rank < 30; rank++) {
        DWORD best = 0xFFFFFFFF, bestc = 0, j;
        for (i = 0; i < PROF_BUCKETS; i++) {
            int already = 0;
            if (!g_prof_key[i]) continue;
            for (j = 0; j < rank; j++) if (taken[j] == i) { already = 1; break; }
            if (already) continue;
            if (g_prof_cnt[i] > bestc) { bestc = g_prof_cnt[i]; best = i; }
        }
        if (best == 0xFFFFFFFF) break;
        taken[rank] = best;
        {
            char who[160];
            DWORD eip = (g_prof_key[best] - 1) << 6;
            rz_modstr(eip, who, sizeof(who));
            logf("PROF> %s #%02lu %6lu (%5.2f%%) %s", tag, rank + 1, bestc,
                 g_prof_n ? 100.0 * bestc / g_prof_n : 0.0, who);
        }
    }
}
static DWORD WINAPI rz_prof_thread(LPVOID p) {
    HANDLE th = NULL;
    DWORD tid = 0;
    (void)p;
    /* 1 ms timer resolution, resolved dynamically so the build needs no winmm.lib */
    {   HMODULE wm = LoadLibraryA("winmm.dll");
        if (wm) { UINT (WINAPI *tbp)(UINT) = (UINT (WINAPI *)(UINT))GetProcAddress(wm, "timeBeginPeriod");
                  if (tbp) tbp(1); } }
    for (;;) {
        if (!g_prof_on || !g_game_tid) { Sleep(5); continue; }
        if (tid != g_game_tid) {
            if (th) CloseHandle(th);
            tid = g_game_tid;
            th = OpenThread(THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT, FALSE, tid);
            if (!th) { g_prof_fail++; Sleep(50); continue; }
        }
        {
            CONTEXT ctx;
            DWORD eip = 0;
            static BYTE stk[STK_BYTES];
            int got_stk = 0;
            ctx.ContextFlags = CONTEXT_CONTROL;      /* gives Eip, Esp, Ebp */
            if (SuspendThread(th) != (DWORD)-1) {
                if (GetThreadContext(th, &ctx)) {
                    eip = ctx.Eip;
                    /* Copy the stack top while suspended; SCAN it after the resume so we hold the
                       thread for as little as possible and never log or allocate under suspension. */
                    if (ctx.Esp && !IsBadReadPtr((void *)ctx.Esp, STK_BYTES)) {
                        memcpy(stk, (void *)ctx.Esp, STK_BYTES);
                        got_stk = 1;
                    }
                }
                ResumeThread(th);                    /* unconditional, same iteration */
            }
            if (eip) rz_prof_hit(eip); else g_prof_fail++;   /* bucketed AFTER the resume */
            if (got_stk) {   /* nearest VALIDATED game-side return address (run 7 fix) */
                int k, found = 0;
                for (k = 0; k < STK_BYTES / 4; k++) {
                    DWORD v = ((DWORD *)stk)[k];
                    if (v && rz_in_game_module(v) && rz_is_retaddr(v)) {
                        rz_stk_hit(v); found = 1; break;
                    }
                }
                if (!found) g_stk_miss++;
            }
        }
        Sleep(1);
    }
}

/* ---- the A/B phase machine ---------------------------------------------------------------------
 * Ticks in the per-frame poll (game thread) so the SetRect stays on the thread that already ran it
 * safely. Step 12 only ARMS it. Phase A profiles the bar at its native width; phase B profiles it
 * docked full-width. Same process, city, window size and zoom - the fixture is its own control. */
static int   g_hudphase;               /* 0 idle, 1 settle, 2 profiling A, 3 profiling B, 4 done */
static DWORD g_phase_ms;
static void rz_hud_setrect_w(DWORD wantW);  /* fwd: dock the bar, spanning to wantW */
static void rz_side_extend(void);           /* fwd: dock+extend the side panel, defined below */
static int  g_sideon;                       /* SC3RESIZE_SIDE: phase B extends the SIDE PANEL only */
static void rz_hud_fit_surface(DWORD liveW);/* fwd: the bar background surface refit, defined below */
static void rz_patch_ddblt(void);
           /* fwd: install the ddraw Blt timer */

/* WIDTH SWEEP (run 13). The A/B design answers "does a full-width bar cost more". It cannot say
 * HOW the cost grows with width, and that shape is diagnostic: a THRESHOLD implies a resource limit
 * (a surface no longer fitting somewhere), while SMOOTH scaling implies per-pixel driver work.
 * Same within-run control as A/B - one process, one city, one window size, only the bar width moves. */
/* RUN 14 control: 600(engine surface) -> 2048(ours) -> 600(ours).
 * Run 13 confounded width with surface ownership: rz_hud_fit_surface skips when liveW == oldw, and
 * the bar is natively 600, so its 600 baseline kept the ENGINE's surface while every wider step ran
 * on one we created - and that first step carried nearly all the cost.
 * Step 3 returns to 600 but now on OUR surface (oldw is 2048 by then, so the refit does happen),
 * which separates the two explanations:
 *   cost back at baseline in step 3 -> WIDTH is the driver;
 *   cost still high in step 3       -> OUR RECREATED SURFACE is the driver = a mod bug, not an
 *                                      engine property, and a far more fixable one. */
static const DWORD g_sweep[] = { 600, 2048, 600 };
#define SWEEP_N (int)(sizeof(g_sweep) / sizeof(g_sweep[0]))
#define SWEEP_MS 8000
static int g_sweepon, g_sweep_i;

/* Apply one sweep step: dock the bar to `w` and refit its background surface to the same width, so
 * window and surface always agree (run 5 showed a surface-less widen is a third state that scores
 * nothing). Then start a fresh measurement window. */
static void rz_sweep_apply(DWORD w) {
    static char tag[32];
    rz_hud_setrect_w(w);
    rz_hud_fit_surface(w);
    _snprintf(tag, sizeof(tag), "S%d_W%lu", g_sweep_i + 1, w);
    g_win_ms = (double)SWEEP_MS;
    rz_prof_reset(); rz_blt_reset();
    InterlockedExchange(&g_prof_on, 1);
    logf("SWEEP> === width %lu === measuring %d ms", w, SWEEP_MS);
    g_phase_ms = GetTickCount() + SWEEP_MS;
}
static void rz_sweep_dump(DWORD w) {
    char tag[32];
    _snprintf(tag, sizeof(tag), "S%d_W%lu", g_sweep_i + 1, w);
    InterlockedExchange(&g_prof_on, 0);
    rz_blt_dump(tag);
}

static void rz_hudlab_tick(void) {
    if (!g_hudphase || GetTickCount() < g_phase_ms) return;

    if (g_sweepon) {
        if (g_hudphase == 1) {                /* settled -> install the timer, start at width[0] */
            rz_patch_ddblt();
            g_sweep_i = 0;
            logf("SWEEP> starting %d-point sweep, %d ms each",
                 SWEEP_N, SWEEP_MS);
            rz_sweep_apply(g_sweep[0]);
            g_hudphase = 2;
            return;
        }
        if (g_hudphase == 2) {
            rz_sweep_dump(g_sweep[g_sweep_i]);
            g_sweep_i++;
            if (g_sweep_i >= SWEEP_N) {
                logf("SWEEP> ---- DONE. Compare avg inside-Blt across widths: a THRESHOLD implies a "
                     "resource limit, SMOOTH scaling implies per-pixel driver work. ----");
                g_hudphase = 4;
                return;
            }
            rz_sweep_apply(g_sweep[g_sweep_i]);
            return;
        }
        return;
    }
    if (g_hudphase == 1) {                       /* settled -> start profiling the NATIVE bar */
        rz_patch_ddblt();   /* install the ddraw Blt timer before the first measurement window */

        logf("HUDLAB> phase A START (bar NATIVE width) - profiling 10 s");
        rz_prof_reset(); rz_blt_reset();
        InterlockedExchange(&g_prof_on, 1);
        g_hudphase = 2; g_phase_ms = GetTickCount() + 10000;
        return;
    }
    if (g_hudphase == 2) {                       /* end A, widen, start B */
        InterlockedExchange(&g_prof_on, 0);
        rz_prof_dump("A-native"); rz_stk_dump("A-native"); rz_blt_dump("A-native");
        if (g_sideon) {
            /* ISOLATED side-panel test (run 22): extend the PANEL only and leave the bar NATIVE, so
               phase B differs from phase A in exactly one thing. The bar/panel confound is the kind
               of thing that cost runs 13-14 a whole extra control, so it is designed out here. */
            logf("HUDLAB> extending the SIDE PANEL only (bar left native), then phase B");
            rz_side_extend();
        } else {
            logf("HUDLAB> applying the SetRect widen, then phase B");
            rz_hud_setrect_w(0);
            /* With SC3RESIZE_HUDFIT=1, also widen the bar's BACKGROUND SURFACE - the 600x56 raster
               run 2 identified as the thing that actually stops the bar spanning the screen.
               Ordered after the window SetRect so the surface fits the window the bar now occupies. */
            {   RECT cr;
                if (g_hudfit && g_hwnd && GetClientRect(g_hwnd, &cr))
                    rz_hud_fit_surface((DWORD)(cr.right - cr.left)); }
        }
        rz_hud_surfaces("AFTER-setrect");
        rz_prof_reset(); rz_blt_reset();
        InterlockedExchange(&g_prof_on, 1);
        logf("HUDLAB> phase B START (bar FULL-WIDTH) - profiling 10 s");
        g_hudphase = 3; g_phase_ms = GetTickCount() + 10000;
        return;
    }
    if (g_hudphase == 3) {
        InterlockedExchange(&g_prof_on, 0);
        rz_prof_dump("B-fullwidth"); rz_stk_dump("B-fullwidth"); rz_blt_dump("B-fullwidth");
        logf("HUDLAB> ---- DONE. Diff B against A; score against verify/resize_hudlab/PRE.md ----");
        g_hudphase = 4;
    }
}

static int   g_zoomed;                 /* min-zoom applied once */
static DWORD g_exc_code, g_exc_addr;   /* captured by the SEH filter */
static DWORD g_exc_eax, g_exc_ecx, g_exc_edx, g_exc_ebx, g_exc_esi, g_exc_edi;  /* fault-time regs */

/* Resolve a code address to "MODULE+0xRVA" so a caught fault names its function. */
/* Resolve an address by walking the PEB loader list, so EVERY loaded module is covered.
 *
 * ⚠️ This replaces a hardcoded six-name list that contained **"GZWIN.DLL"** while the real file is
 * **GZWIND.DLL**. `GetModuleHandleA` returned NULL for it on every call, so the windowing framework
 * was invisible to every MODULE+RVA resolution in this session - and it is exactly where the UI
 * event sink turned out to live. A typo in a lookup table silently degraded every "no known module"
 * result for 37 runs.
 *
 * PEB walk (x86): fs:[0x30] = PEB, PEB+0x0C = Ldr, Ldr+0x14 = InMemoryOrderModuleList.
 * Each LDR_DATA_TABLE_ENTRY is (link - 8): DllBase +0x18, SizeOfImage +0x20,
 * BaseDllName UNICODE_STRING +0x2C (Length, MaximumLength, Buffer at +0x30). */
static void rz_modstr(DWORD addr, char *out, int n) {
    DWORD peb, ldr, head, cur, guard = 0;
    if (IsBadReadPtr(out, 1)) return;
    __asm { mov eax, fs:[0x30]
            mov peb, eax }
    if (!peb || IsBadReadPtr((void *)(peb + 0x0c), 4)) goto unknown;
    ldr = *(DWORD *)(peb + 0x0c);
    if (!ldr || IsBadReadPtr((void *)(ldr + 0x14), 4)) goto unknown;
    head = ldr + 0x14;
    cur  = *(DWORD *)head;
    while (cur && cur != head && guard++ < 256 && !IsBadReadPtr((void *)cur, 0x30)) {
        DWORD ent  = cur - 8;                       /* InMemoryOrderLinks is at entry+0x08 */
        DWORD base, size;
        if (IsBadReadPtr((void *)(ent + 0x18), 0x1c)) break;
        base = *(DWORD *)(ent + 0x18);
        size = *(DWORD *)(ent + 0x20);
        if (base && size && addr >= base && addr < base + size) {
            WORD  len = *(WORD *)(ent + 0x2c);
            WCHAR *w  = *(WCHAR **)(ent + 0x30);
            char name[64];
            int  k = 0;
            if (w && !IsBadReadPtr(w, len)) {
                int chars = len / 2;
                if (chars > (int)sizeof(name) - 1) chars = sizeof(name) - 1;
                for (k = 0; k < chars; k++) name[k] = (char)w[k];   /* module names are ASCII */
            }
            name[k] = 0;
            _snprintf(out, n, "%s+0x%lX (base 0x%08lX)", k ? name : "?", addr - base, base);
            return;
        }
        cur = *(DWORD *)cur;                        /* Flink */
    }
unknown:
    _snprintf(out, n, "0x%08lX (no module)", addr);
}
static int rz_filter(EXCEPTION_POINTERS *ep) {
    g_exc_code = ep->ExceptionRecord->ExceptionCode;
    g_exc_addr = (DWORD)ep->ExceptionRecord->ExceptionAddress;
    g_exc_eax = ep->ContextRecord->Eax; g_exc_ecx = ep->ContextRecord->Ecx;
    g_exc_edx = ep->ContextRecord->Edx; g_exc_ebx = ep->ContextRecord->Ebx;
    g_exc_esi = ep->ContextRecord->Esi; g_exc_edi = ep->ContextRecord->Edi;
    return EXCEPTION_EXECUTE_HANDLER;
}

/* Process-wide crash logger. The zoom-after-resize crash happens on the GAME's own thread/path, which
 * our resize __try/__except never wraps, and SC3U's top-level handler swallows the fault (no WER), so
 * only a vectored handler can capture it. Logs any hardware fault with faulting MODULE+RVA, access
 * address, registers and the top-of-stack return address, then CONTINUE_SEARCH so the game's own
 * handling is unchanged. Filtered to hardware/AV codes to avoid first-chance C++/debug noise. */
static LONG CALLBACK rz_veh(EXCEPTION_POINTERS *ep) {
    DWORD code = ep->ExceptionRecord->ExceptionCode;
    if (code == 0xC0000005 /* access violation */ || code == 0xC000001D /* illegal instruction */ ||
        code == 0xC0000094 /* integer div by zero */ || code == 0xC0000096 /* privileged instr */ ||
        code == 0xC00000FD /* stack overflow */ || code == 0xC0000006 /* in-page error */) {
        CONTEXT *c = ep->ContextRecord;
        char who[160];
        rz_modstr((DWORD)ep->ExceptionRecord->ExceptionAddress, who, sizeof(who));
        logf("RZ   *** VEH FAULT *** code=0x%08lX at %s  (resize step at fault=%d)",
             code, who, g_rz_step);
        if (code == 0xC0000005 && ep->ExceptionRecord->NumberParameters >= 2) {
            DWORD acc = (DWORD)ep->ExceptionRecord->ExceptionInformation[0];
            DWORD ea  = (DWORD)ep->ExceptionRecord->ExceptionInformation[1];
            logf("RZ   VEH access=%s addr=0x%08lX",
                 acc == 0 ? "READ" : acc == 1 ? "WRITE" : acc == 8 ? "EXEC" : "?", ea);
        }
        logf("RZ   VEH regs eax=%08lX ecx=%08lX edx=%08lX ebx=%08lX esi=%08lX edi=%08lX ebp=%08lX esp=%08lX",
             c->Eax, c->Ecx, c->Edx, c->Ebx, c->Esi, c->Edi, c->Ebp, c->Esp);
        if (!IsBadReadPtr((void *)c->Esp, 4)) {
            char ret[160];
            rz_modstr(*(DWORD *)c->Esp, ret, sizeof(ret));
            logf("RZ   VEH [esp]=0x%08lX -> %s", *(DWORD *)c->Esp, ret);
        }
        /* Who called? The single [esp] word above could not name the caller of the 2026-10-05
         * maximize crash. Scan the stack for words that land inside a loaded module (candidate return
         * addresses - a heuristic, not an unwind: stale words are possible) and say whether the mod's
         * own present-time RCI blit was on the stack. */
        logf("RZ   VEH in_rci_repaint=%d", g_in_rci_repaint);
        {   DWORD *sp = (DWORD *)c->Esp;
            int k, shown = 0;
            for (k = 0; k < 512 && shown < 14; k++) {
                char m[160];
                DWORD wv;
                if (IsBadReadPtr(sp + k, 4)) break;
                wv = sp[k];
                if (wv < 0x00400000) continue;
                rz_modstr(wv, m, sizeof(m));
                if (strstr(m, "no module")) continue;
                logf("RZ   VEH stack[esp+0x%03X] = %s", k * 4, m);
                shown++;
            }
        }
    }
    return EXCEPTION_CONTINUE_SEARCH;   /* do not alter the game's own fault handling */
}

/* Fault-time diagnosis for the FUN_1000cedb+0x12a AV (dangling grid-B node). At +0x12a =
 * `cmp [eax],edx`: EAX is the node the walk faulted on, EDI is (near) the bucket slot address. This
 * decides OOB-bucket-index vs freed-node by comparing EDI to the 8x8 grid array range, and scans all
 * 64 buckets to find and count bad node pointers. Called only from the __except handler. */
static void rz_fault_diag(void *iso) {
    DWORD gbase, dimW, dimH, stride, i, badbuckets = 0, badnodes = 0, totnodes = 0;
    char who[128];
    rz_modstr(g_exc_addr, who, sizeof(who));
    logf("RZ   FAULT regs: eip=%s code=0x%08lX | eax=0x%08lX ecx=0x%08lX edx=0x%08lX "
         "ebx=0x%08lX esi=0x%08lX edi=0x%08lX", who, g_exc_code,
         g_exc_eax, g_exc_ecx, g_exc_edx, g_exc_ebx, g_exc_esi, g_exc_edi);
    logf("RZ   FAULT eax (the node cmp'd) readable=%d", !IsBadReadPtr((void *)g_exc_eax, 8));
    if (!iso || IsBadReadPtr(iso, 0x3a0)) { logf("RZ   FAULT: iso unreadable for grid dump"); return; }
    gbase  = ((DWORD *)iso)[0x380 / 4];
    dimW   = ((DWORD *)iso)[0x384 / 4];
    dimH   = ((DWORD *)iso)[0x388 / 4];
    stride = ((DWORD *)iso)[0x38c / 4];
    logf("RZ   FAULT grid: base=0x%08lX dims=%lux%lu stride=%lu (64 buckets = base..base+0x100) | "
         "edi in-grid=%d (edi-base=%ld, /4=%ld) | extent=(%ld,%ld,%ld,%ld) scale39c=%.6f 3a0=%.6f",
         gbase, dimW, dimH, stride,
         (gbase && g_exc_edi >= gbase && g_exc_edi < gbase + 0x100),
         gbase ? (long)(g_exc_edi - gbase) : 0, gbase ? (long)((g_exc_edi - gbase) / 4) : 0,
         (long)((DWORD *)iso)[0x54/4], (long)((DWORD *)iso)[0x58/4],
         (long)((DWORD *)iso)[0x5c/4], (long)((DWORD *)iso)[0x60/4],
         *(float *)((BYTE *)iso + 0x39c), *(float *)((BYTE *)iso + 0x3a0));
    if (gbase && !IsBadReadPtr((void *)gbase, 64 * 4)) {
        for (i = 0; i < 64; i++) {
            DWORD node = ((DWORD *)gbase)[i]; int g = 0;
            if (node && IsBadReadPtr((void *)node, 8)) { badbuckets++;
                logf("RZ   FAULT bucket[%lu] head=0x%08lX is UNREADABLE (dangling head)", i, node); }
            while (node && !IsBadReadPtr((void *)node, 8) && g < 20000) {
                totnodes++; g++;
                { DWORD nx = ((DWORD *)node)[1];
                  if (nx && IsBadReadPtr((void *)nx, 8)) { badnodes++;
                      logf("RZ   FAULT bucket[%lu] node 0x%08lX ->next 0x%08lX UNREADABLE (dangling "
                           "next)", i, node, nx); }
                  node = nx; }
            }
        }
        logf("RZ   FAULT grid scan: %lu total nodes, %lu dangling heads, %lu dangling next-ptrs "
             "(matches eax=0x%08lX?)", totnodes, badbuckets, badnodes, g_exc_eax);
    }
}
static volatile LONG g_busy;           /* re-entrancy guard for the per-frame poll */
/* SIMLOCK (2026-10-10): the map-wide refresh (step 7/11, SIMSPR FUN_10018cdf) ends by walking EVERY cell's occupant
   chain (bridge+0x18 vt+0xa0, occupant vt+0x60 / vt+0x4c) holding only the view's data lock, while the sim thread's
   zone development replaces buildings under the city's TICK lock L1 (city+0x1a8, lock object: vt+4 lock, vt+8 unlock;
   SIMCITY FUN_10002ef3 / FUN_10003178). On the 1024 city it met a building half destroyed (SIMSPR+0x5AFDA: the
   forwarder FUN_1005afd3 read a null inner object; also +0x2D102). The pass now holds L1 from the start, so the sim
   tick waits for it: same order as the sim (L1 -> data lock -> view), and L1 is re-entrant for its owner, so the
   refresh's own L1 take inside FUN_100184d9 still works. The pass runs from rz_wndproc with no locks held
   (DEFERRESIZE). SC3RESIZE_SIMLOCK=0 turns it off. Call with NULL to take; pass the result back to release. */
static int g_simlock = 1;
/* SKIPREFRESH (2026-10-11): no map-wide refresh in the resize pass. Steps 7 and 11 both called SIMSPR FUN_10018cdf,
   and each call ends with a walk over all bridge+0xec x bridge+0xf0 cells (1,048,576 on a 1024 map: iso vt+0xa0,
   FUN_1001924c, FUN_1001a291) plus the whole-view repaint iso vt+0x144 [CONFIRMED @ SIMSPR 0x10018cdf]. Step 7 passed
   layer 0: it unregistered every occupant of the active layer (FUN_1001879e), nulled bridge+0x28 and walked; step 11
   passed the BASE layer and BASE renderer back: re-register (FUN_100184d9) + walk again. That was 1.4-3.3 s of the
   maximize freeze on the 1024 city (2.2 s median with the sim running), and step 11 also threw the view out of any
   open data or underground view (pipes, land value: the city view came back while the UI stayed in the data view).
   A resize never invalidates what the refresh rebuilds: Init is not called, so the tile grid iso+0x24, the occupant
   registrations and the layer attachment all survive; step 8c re-shows the tiles and step 10 repaints the view.
   Measured 2026-10-11 on the 1024 city, 1680x979 <-> 800x600: frames identical to the stock pair in 10 paused states,
   36+16 sim-running cycles with no new fault, pass 107 ms paused / ~150 ms running instead of 1.8 s / 2.2 s.
   1 = skip both (default), 2 = one refresh (step 11 alone when the base layer is active, the same-layer forced
   refresh the game's own SetDataView FUN_100182ba runs), 0 = the stock pair, as before. */
static int g_skiprefresh = 1;
static BYTE *rz_sim_lock(BYTE *held) {
    typedef void (__fastcall *LK_FN)(BYTE *self, void *edx);
    BYTE *app, *city, *lk;
    if (held) { ((LK_FN)(*(DWORD **)held)[2])(held, NULL); return NULL; }
    if (!g_simlock) return NULL;
    app = *(BYTE **)((BYTE *)GetModuleHandleA(NULL) + 0xfa86c);
    if (!app || IsBadReadPtr(app + 0x48, 4)) return NULL;
    city = *(BYTE **)(app + 0x48);
    if (!city || IsBadReadPtr(city + 0x1a8, 4)) return NULL;
    lk = city + 0x1a8;
    if (IsBadReadPtr(*(DWORD **)lk, 12)) return NULL;
    ((LK_FN)(*(DWORD **)lk)[1])(lk, NULL);
    return lk;
}
/* DEFERRESIZE (2026-10-08): the resize pass must not run from the blit heartbeat. That heartbeat fires
   inside the city view's Plot (SIMSPR 0x1001cab9 -> dirty-rect blits), where the game thread already holds
   the city-data lock; step 7/11 (SIMSPR FUN_10018cdf -> FUN_100184d9) then takes the lock the sim thread
   holds for its whole timer pass, while the sim thread (SIMCITY timer -> SIMRCI -> SIMGEOM -> GZServiceD)
   waits for the data lock. Measured deadlock with cdb, sc3perf run moscowB0, 2026-10-08: game thread held
   CS 0x0d76a220 and waited on 0x0d76a1fc, sim thread the reverse. The game itself calls FUN_10018cdf from
   UI handlers, i.e. from message dispatch with no drawing locks held, so the poll now only POSTS
   WM_RZ_DORESIZE and the pass runs from rz_wndproc. SC3RESIZE_DEFERRESIZE=0 restores the old path. */
#define WM_RZ_DORESIZE (WM_APP + 0x5C3)
/* ZOOMKEYS (owner 2026-10-09): the main-keyboard + and - keys also zoom. The hotkey table
   (Apps\Res\Hotkeys\<LANG>.IXF, group 0xa2e3d56d, text lines "ctrl shift alt VK = 583838163 cmd 0 0") binds zoom in
   (cmd 41) to VK 107 (numpad +) and zoom out (cmd 42) to VK 109 (numpad -) only. Rather than edit game files, the
   window procedure hands the game VK_ADD / VK_SUBTRACT when it sees VK_OEM_PLUS (0xBB) / VK_OEM_MINUS (0xBD), which
   are the unshifted + and - keys on a Spanish layout. The numpad keys keep working. SC3RESIZE_ZOOMKEYS=0 disables. */
static int g_zoomkeys = 1;
/* PAUSEKEY (owner 2026-10-10): P toggles the pause, like the bottom bar's pause / play buttons. The hotkey table binds
   plain P (VK 80) to cmd 24, which neither pauses nor resumes (posted live on a running city, 2026-10-10). The city
   subscribes to 0xc2a35d7e (vt+0x20c, user pause depth city+0x140 += 1) and 0xc2a35d80 (vt+0x210, -= 1)
   [CONFIRMED @ SIMCITY 0x10002fa6]; posted through the message service (sc3simrun gz_post) the bar's pause button lights
   and unlights with them. Key down without Ctrl/Alt/Shift and not auto-repeat: depth 0 -> pause, else resume one level.
   The P key message is swallowed so cmd 24 does not also run. SC3RESIZE_PAUSEKEY=0 disables. */
static int g_pausekey = 1;
static int g_miniclass = 1;
/* SPEEDKEYS (owner 2026-10-11): 1-4 (top row and numpad) set the sim speed. The hotkey table binds 1-5 to cmds 84..76,
   which change nothing (posted live: the clock speed stayed put). 0xc2684065 with arg N sets the clock: 1 = 10080
   game-min/day (8571 ms per day), 2 = 43200 (2000 ms), 3 = 129600 (666 ms), 4 = 525600 (164 ms), measured at clock
   +0x50/+0x60 after each post; it does not touch the pause depth, so a paused sim stays paused (owner call 2026-10-11:
   speed keys must not unpause, P does that). SC3RESIZE_SPEEDKEYS=0 disables. */
static int g_speedkeys = 1;
/* KEYFOCUS (2026-10-11): P and 1-4 are left to the game while a text field has keyboard focus, so a city or file name
   can contain them. The GZGraphicD WndProc hands every key to the window manager (GZGraphicD+0x6cdb8 -> +0x30, vtable
   GZWIND+0x2db80) at vt+0x68 [CONFIRMED @ GZGraphicD 0x10017e2f], which passes it to the in-game focus window at
   +0x2c through its vt+0xc [CONFIRMED @ GZWIND 0x10020947]; the window's char handler is vt+0x1a8 [CONFIRMED @ SIMINIT
   0x100181a1, event type 4]. Text fields are the classes whose char handler inserts text: single-line edits GZWIND
   0x1002a8cc, SIMINIT 0x10030890, SIMUI 0x100a5f7c / 0x100adca0 (handler gated on byte +0x111 [CONFIRMED @ SIMINIT
   0x1001d706, GZWIND 0x100053a9, SIMUI 0x1007cb69]) and the GZWIND multi-line text area 0x1002bf10. Measured live: the
   save dialog's three name fields put a SIMINIT+0x30890 object at +0x2c, its file list a SIMINIT+0x3050c one, the city
   view a SIMSPR+0x676ac one. SC3RESIZE_KEYFOCUS=0 disables (P and 1-4 then fire everywhere, as before). */
static int g_keyfocus = 1;
static int rz_text_focus(void) {
    DWORD gz = (DWORD)GetModuleHandleA("GZGraphicD.dll"), gw = (DWORD)GetModuleHandleA("GZWIND.DLL");
    DWORD si = (DWORD)GetModuleHandleA("SIMINIT.DLL"), su = (DWORD)GetModuleHandleA("SIMUI.DLL");
    BYTE *win, *sink, *f;
    DWORD vt;
    if (!g_keyfocus || !gz) return 0;
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
/* Post a GZ message to the loaded city through the message service (sc3simrun gz_post). Returns the city, NULL if
   no city is loaded or the service is not the expected one. */
static BYTE *rz_city_post(DWORD id, DWORD arg) {
    typedef int (__fastcall *GETSVC)(void *self, void *edx, DWORD a, DWORD b, void **out);
    typedef int (__fastcall *POST)(void *self, void *edx, DWORD *msg, int now);
    BYTE *exe = (BYTE *)GetModuleHandleA(NULL), *app, *city;
    HMODULE simcity = GetModuleHandleA("SIMCITY.DLL"), gzsvc = GetModuleHandleA("GZServiceD.dll");
    void *fw, *srv = NULL;
    DWORD msg[4];
    if (!simcity || !gzsvc) return NULL;
    __try {
        app = *(BYTE **)(exe + 0xfa86c);
        if (!app) return NULL;
        city = *(BYTE **)(app + 0x48);
        if (!city || *(DWORD *)city != (DWORD)simcity + 0x13260) return NULL;    /* no city loaded */
        fw = *(void **)(exe + 0xFAB74);
        if (!fw) return NULL;
        ((GETSVC)(*(DWORD **)fw)[0x10 / 4])(fw, NULL, 0x64063387, 0xC1085722, &srv);
        if (!srv || *(DWORD *)srv != (DWORD)gzsvc + 0x14618) return NULL;
        if (!id) return city;
        msg[0] = id; msg[1] = arg; msg[2] = msg[3] = 0;
        ((POST)(*(DWORD **)srv)[0x10 / 4])(srv, NULL, msg, 0);
    } __except (EXCEPTION_EXECUTE_HANDLER) { return NULL; }
    return city;
}
static int rz_pause_toggle(void) {
    BYTE *city = rz_city_post(0, 0);
    DWORD depth;
    if (!city) return 0;
    depth = *(DWORD *)(city + 0x140);
    rz_city_post(depth ? 0xc2a35d80 : 0xc2a35d7e, 0);
    logf("PAUSEKEY> depth %lu -> %s", depth, depth ? "resume" : "pause");
    return 1;
}
static int rz_speed_key(int n) {
    if (!rz_city_post(0xc2684065, (DWORD)n)) return 0;
    logf("SPEEDKEYS> speed %d", n);
    return 1;
}
/* CLOSEX (owner 2026-10-12, "no funcionó la X para cerrar"): the window X, the system-menu Close and Alt+F4 open the
   game's own quit dialog. Stock GZGraphicD FUN_10017e2f returns 0 on WM_CLOSE without DefWindowProc (the je at
   0x10017eab) and sends WM_SYSKEYDOWN to its key path, so on a stock install none of the three does anything
   [CONFIRMED @ GZGraphicD 0x10017e2f]. Only MAIN's on-disk pe_patch recipe close_button_quit made the X work, and it
   quits at once (PostQuitMessage). Here the X does what the game's own "Salir" button does in the current screen:
   - main menu (root child with vtable SC3U+0xd2c20): the menu's button handler vt+0x1e0 = FUN_0043b51d(1, 0x712bf5c4),
     the exact call a click on its "Salir" tile reaches [CONFIRMED @ SC3U 0x0043b51d; id 0x712BF5C4 = Exit,
     LAUNCH_CONTROL.md section 31]. Measured: the Quit command below does nothing at the menu.
   - city: the menu bar's Quit command, {0x025F0A91, 0x10009005, 0, 0} through the message service, the message
     SIMUI FUN_1004c209 posts for a click on that item [CONFIRMED @ SIMUI 0x1004c209; id from MenuItem.INI].
   - the intro screen (vtable SC3U+0xd1784): PostQuitMessage(0), what the recipe did. Nothing to save there.
   - any other screen (loading, terrain editor, ...): nothing, as on stock, so work there is never lost to a stray X.
   Both game paths ask before quitting, so an unsaved city is not lost on a stray click. CLOSEX takes WM_CLOSE before
   the game's WndProc, so on a GZGraphicD that carries the recipe cave the cave never runs. SC3RESIZE_CLOSEX=0 passes
   WM_CLOSE and Alt+F4 to the game as before. */
static int g_closex = 1;
static void *rz_closex_screen(DWORD vtoff) {   /* the visible root child with vtable SC3U+vtoff, or NULL */
    DWORD vt = (DWORD)GetModuleHandleA(NULL) + vtoff;
    BYTE *root = (BYTE *)rz_ui_root(), *head, *n, *c;
    int guard = 0;
    if (!root) return NULL;
    head = *(BYTE **)(root + 0x34);
    if (!head) return NULL;
    for (n = *(BYTE **)head; n && n != head && guard++ < 200; n = *(BYTE **)n) {
        c = *(BYTE **)(n + 8);
        if (c && *(DWORD *)c == vt && (*(DWORD *)(c + 0xa0) & 1)) return c;
    }
    return NULL;
}
static void rz_closex(const char *why) {
    typedef int (__fastcall *GETSVC)(void *self, void *edx, DWORD a, DWORD b, void **out);
    typedef int (__fastcall *POST)(void *self, void *edx, DWORD *msg, int now);
    typedef int (__fastcall *MENUBTN)(void *self, void *edx, int ev, DWORD id);
    BYTE *exe = (BYTE *)GetModuleHandleA(NULL);
    void *menu = NULL, *intro = NULL, *fw = NULL, *srv = NULL;
    DWORD msg[4] = { 0x025f0a91, 0x10009005, 0, 0 };
    int how = 0;
    __try {
        /* A modal dialog is already up (the quit question itself, or any other): do nothing. The modal loop GZWIND
           FUN_10020971 (vtable GZWIND+0x2db80 slot 0xa0) counts its depth in sink+0x194 and dispatches messages
           itself, so a second X arrived inside the first quit dialog and stacked a second one (measured: two dialogs,
           depth 2). The main menu and the intro screen (vtable SC3U+0xd1784, up for ~40 s at start) each run in one modal
           loop (measured: depth 1 there, 0 in a city), so those two screens allow depth 1
           [CONFIRMED @ GZWIND 0x10020971, 0x1002174d]. */
        DWORD gz = (DWORD)GetModuleHandleA("GZGraphicD.dll"), gw = (DWORD)GetModuleHandleA("GZWIND.DLL");
        BYTE *win = gz ? *(BYTE **)(gz + 0x6cdb8) : NULL, *sink = win ? *(BYTE **)(win + 0x30) : NULL;
        menu = rz_closex_screen(0xd2c20);
        intro = menu ? NULL : rz_closex_screen(0xd1784);
        if (sink && gw && *(DWORD *)sink == gw + 0x2db80 && *(LONG *)(sink + 0x194) > ((menu || intro) ? 1 : 0)) {
            logf("CLOSEX> %s: a modal dialog is open (depth %ld%s) - ignored", why, *(LONG *)(sink + 0x194),
                 menu ? ", main menu" : intro ? ", intro" : "");
            return;
        }
        if (menu) {
            ((MENUBTN)(*(DWORD **)menu)[0x1e0 / 4])(menu, NULL, 1, 0x712bf5c4);
            how = 1;
        } else if (rz_city_post(0, 0)) {
            HMODULE gzsvc = GetModuleHandleA("GZServiceD.dll");
            fw = *(void **)(exe + 0xFAB74);
            if (fw) ((GETSVC)(*(DWORD **)fw)[0x10 / 4])(fw, NULL, 0x64063387, 0xC1085722, &srv);
            if (gzsvc && srv && *(DWORD *)srv == (DWORD)gzsvc + 0x14618) {
                ((POST)(*(DWORD **)srv)[0x10 / 4])(srv, NULL, msg, 0);
                how = 2;
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        logf("CLOSEX> %s: fault 0x%08lX in the game's quit path (menu %p)", why, (DWORD)GetExceptionCode(), menu);
        return;
    }
    if (how == 1) { logf("CLOSEX> %s: main menu 0x%08lX -> its Salir button 0x712BF5C4", why, (DWORD)menu); return; }
    if (how == 2) { logf("CLOSEX> %s: city -> posted the Quit command 0x10009005", why); return; }
    if (!intro) { logf("CLOSEX> %s: no menu, no city, no intro - ignored", why); return; }
    logf("CLOSEX> %s: intro screen - PostQuitMessage(0)", why);
    PostQuitMessage(0);
}
static int           g_deferresize = 1;
static volatile LONG g_in_wndproc_pass, g_resize_posted;
static int   g_wm_fixed;               /* the window has been subclassed */
static WNDPROC g_oldproc;
/* g_hwnd and g_hud_top are declared up with the HUD lab block (both are read by it). */

/* Indirect __thiscall with n stack args. ESP is saved and restored around the call, so a wrong
 * argument count shows up as a bad return value rather than as a crash three frames later.
 * VERBATIM from sc3probe.c rz_thiscall. Also used for the one cdecl callee (FUN_100059fb),
 * which simply ignores ECX - the esp restore makes that safe. */
static int rz_thiscall(void *self, void *fn, const DWORD *a, int n) {
    int rv = 0;
    __asm {
        push ebx
        push esi
        push edi
        mov  ebx, esp
        mov  edi, a
        mov  ecx, n
        test ecx, ecx
        jz   rz_ready
    rz_push:
        mov  eax, [edi + ecx*4 - 4]
        push eax
        dec  ecx
        jnz  rz_push
    rz_ready:
        mov  ecx, self
        call [fn]
        mov  esp, ebx
        movzx eax, al
        mov  rv, eax
        pop  edi
        pop  esi
        pop  ebx
    }
    return rv;
}

/* Same __thiscall shim as rz_thiscall but returns the FULL EAX (not the low byte) - needed for
 * methods that return a pointer, e.g. the window's target-surface getter vt+0x158. */
static DWORD rz_thiscall_ret(void *self, void *fn, const DWORD *a, int n) {
    DWORD rv = 0;
    __asm {
        push ebx
        push esi
        push edi
        mov  ebx, esp
        mov  edi, a
        mov  ecx, n
        test ecx, ecx
        jz   rzr_ready
    rzr_push:
        mov  eax, [edi + ecx*4 - 4]
        push eax
        dec  ecx
        jnz  rzr_push
    rzr_ready:
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

/* Replay FUN_10009efb at a new size on one raster-class object.
 * The ORIGINAL 8-arg tuple matters: a 2-arg call writes stack garbage into the raster. The
 * tuple is recovered from the object's OWN fields, which is sound because FUN_10009efb writes
 * p3..p8 to +0x0c/+0x10/+0x14/+0x18/+0x3c/+0x40 [CONFIRMED @ 0x10009efb] and nothing
 * downstream overwrites them: vt+0x1dc (FUN_1001420d) writes only this+0x44, and vt+0x1e0
 * (FUN_100142a2) writes none of them [CONFIRMED @ 0x1001420d, 0x100142a2].
 * The +0x08 surfaces-created guard must be cleared first or FUN_10009efb refuses. */
static int rz_recreate_raster(DWORD obj, const char *name, DWORD w, DWORD ht, HMODULE gz) {
    DWORD *vt, ca[8];
    DWORD want_r = (DWORD)gz + GZ_RVA_VT_RASTER, want_b = (DWORD)gz + GZ_RVA_VT_BLITDEST;
    int rc;

    if (!obj || IsBadReadPtr((void *)obj, 0x44)) {
        logf("RZ   REFUSE %s: 0x%08lX unreadable", name, obj);
        return 0;
    }
    vt = *(DWORD **)obj;
    if (IsBadReadPtr(vt, 0x1e0)) { logf("RZ   REFUSE %s: vtable unreadable", name); return 0; }
    if ((DWORD)vt != want_r && (DWORD)vt != want_b) {
        logf("RZ   REFUSE %s 0x%08lX: vtable 0x%08lX is neither GZGraphicD+0x1E894 (0x%08lX) "
             "nor +0x1F328 (0x%08lX) - not the class we think, refusing to call it",
             name, obj, (DWORD)vt, want_r, want_b);
        return 0;
    }
    if (vt[0x0c / 4] != (DWORD)gz + GZ_RVA_RASTER_CREATE) {
        logf("RZ   REFUSE %s 0x%08lX: vt+0x0c = 0x%08lX != FUN_10009efb (0x%08lX)",
             name, obj, vt[0x0c / 4], (DWORD)gz + GZ_RVA_RASTER_CREATE);
        return 0;
    }
    {   /* Prefer the RECORDED create tuple; fall back to field read-back and say so. */
        int i, found = -1;
        for (i = 0; i < (int)g_nrc && i < MAX_RC; i++)
            if (g_rc[i].obj == obj) { found = i; break; }
        if (found >= 0) {
            for (i = 0; i < 8; i++) ca[i] = g_rc[found].a[i];
            logf("RZ   %s 0x%08lX tuple from its RECORDED create "
                 "[%lu %lu %lu %lu %lu %lu %lu %lu]", name, obj,
                 ca[0], ca[1], ca[2], ca[3], ca[4], ca[5], ca[6], ca[7]);
        } else {
            ca[2] = ((DWORD *)obj)[0x0c / 4];
            ca[3] = ((DWORD *)obj)[0x10 / 4];
            ca[4] = ((DWORD *)obj)[0x14 / 4];
            ca[5] = ((DWORD *)obj)[0x18 / 4];
            ca[6] = ((DWORD *)obj)[0x3c / 4];
            ca[7] = (DWORD)*((BYTE *)obj + 0x40);
            logf("RZ   %s 0x%08lX NO RECORDED CREATE (%ld known%s) - FALLING BACK to field "
                 "read-back [_ _ %lu %lu %lu %lu %lu %lu]. Field read-back is NOT proven "
                 "equivalent: p3 measured 7 vs a recorded 4 on 2026-08-28.",
                 name, obj, g_nrc, g_rc_full ? ", TABLE FULL - miss unreliable" : "",
                 ca[2], ca[3], ca[4], ca[5], ca[6], ca[7]);
        }
        /* PITCH-SHEAR FIX (2026-09-03): pin p3 to the recorded-good value. Field read-back yields 7,
           which places some widths in a pool whose pitch rounds up (1000 -> 2048) while the present
           reads width*2 -> the whole frame shears diagonally and goes grey. The recorded create used
           4. Applied to BOTH the render target and the device surface (same routine). Only when a
           recorded tuple was NOT found (a real recording is authoritative and already correct). */
        if (found < 0 && g_rt_p3 >= 0) {
            logf("RZ   %s p3 pinned %lu -> %ld (pitch-shear fix)", name, ca[2], g_rt_p3);
            ca[2] = (DWORD)g_rt_p3;
        }
        if (found < 0 && g_rt_p7 >= 0 && ca[6] != (DWORD)g_rt_p7) {
            logf("RZ   %s p7 pinned %lu -> %ld (force system memory, tight pitch)", name, ca[6], g_rt_p7);
            ca[6] = (DWORD)g_rt_p7;
        }
        ca[0] = w;
        /* PITCH-SHEAR FIX (2026-09-03): round surface width up so width*2 is 64-byte aligned. See
           g_walign. Keeps the client width intact (present pushes the client rect); only the backing
           allocation is wider. */
        if (g_walign > 1) {
            DWORD aw = (w + (DWORD)g_walign - 1) & ~((DWORD)g_walign - 1);
            if (aw != w) {
                logf("RZ   %s width padded %lu -> %lu (walign %ld, pitch-shear fix)",
                     name, w, aw, g_walign);
                ca[0] = aw;
            }
        }
        /* ZOOM-CRASH FIX (2026-08-30): allocate GUARD ROWS below the visible height.
           The zoom-scaled 16bpp blitter FUN_1000239d (GZGraphicD) has NO vertical clamp to the
           surface height - it bounds its row loop only by the caller's dest rect, and its 2x/4x
           branches issue COMPANION writes one-to-four scanlines BELOW the current row (the vertical
           up-scaling). When a bottom-edge tile at higher zoom reaches the surface's last row, that
           companion write spills one page past the buffer -> 0xC0000005 WRITE at edx+pitch (captured:
           GZGraphicD FUN_1000239d+0x1a1, addr = base+0x1000, one 2048px scanline). The surface is
           correctly WIDTH-resized (pitch witnessed 0x1000 = 2048px); it is one row too SHORT for the
           scaled write. Padding the height gives the companion writes mapped space. The 4x branch
           spills up to ~3 rows, so 8 is a safe guard. These rows are never presented: step 9 pushes
           the present rect {0,0,w,ht}, so only the top ht rows reach the screen.
           Root cause + evidence: verify/resize_zoomcrash/RESULTS.md. */
        ca[1] = ht + RZ_SURFACE_SLACK;
        logf("RZ   %s replay at %lux%lu (+%d guard rows -> alloc h=%lu, zoom-blit overrun fix)",
             name, w, ht, RZ_SURFACE_SLACK, ca[1]);
    }
    /* FORCE SYSTEM MEMORY (SC3RESIZE_SYSMEM). Worker RE 2026-09-03: the surface pool is derived in
     * the create path from obj+0x8c (param_1[0x23]) as `-(param_1[0x23]!=0) & 3` - nonzero picks
     * VIDEOMEMORY (driver pads the pitch -> the composite shears at widths whose width*2 is not
     * 64-byte aligned), zero picks SYSTEMMEMORY (tight pitch = width*2 for even widths). This field is
     * NOT in the replayed p3..p8 tuple, so zero it directly before the create. Testing whether this
     * kills the shear at arbitrary even widths and lets the 32-snap drop to a 2px even constraint. */
    if (g_sysmem) {
        DWORD *o = (DWORD *)obj;
        if (!IsBadWritePtr(o, 0x90) && o[0x8c / 4] != 0) {
            logf("RZ   %s obj+0x8c %lu -> 0 (force system memory)", name, o[0x8c / 4]);
            o[0x8c / 4] = 0;
        }
    }
    *((BYTE *)obj + 8) = 0;
    rc = rz_thiscall((void *)obj, (void *)vt[0x0c / 4], ca, 8);
    logf("RZ   %s FUN_10009efb -> %d | now +0x24=%lu +0x28=%lu",
         name, rc, ((DWORD *)obj)[0x24 / 4], ((DWORD *)obj)[0x28 / 4]);
    {   /* CREATEFAIL (task cityzoom, 2026-10-22): one run had both creates return 0 at a zoom step (the surface object +0x44
           left NULL, the next draw read through it: GZGraphicD FUN_10014649+0x14). The same NULL +0x44 the monitor-change
           crash leaves (project-test-display-environment). Retry a few times before giving up. */
        int tries;
        for (tries = 0; !(rc & 0xff) && tries < 6; tries++) {
            Sleep(50 * (tries + 1));
            *((BYTE *)obj + 8) = 0;
            rc = rz_thiscall((void *)obj, (void *)vt[0x0c / 4], ca, 8);
            logf("RZ   %s CREATEFAIL retry %d -> %d (+0x44 = 0x%08lX)", name, tries + 1, rc, ((DWORD *)obj)[0x44 / 4]);
        }
    }
    return (rc & 0xff) ? 1 : 0;
}

static void rz_cellfix(void *iso);   /* DIRTCLIP + CELLFIX block */
/* The routine. Runs on the game thread from the per-frame heartbeat. */
static void rz_do_resize(void *iso, DWORD w, DWORD ht) {
    HMODULE ss = GetModuleHandleA("SIMSPR.DLL"), gz = GetModuleHandleA("GZGraphicD.dll");
    DWORD *v = (DWORD *)iso, *b = (DWORD *)g_bridge;
    DWORD gw = 0, gh = 0, a5[5], a2[2], a3[3], fa[5];
    DWORD R, B;
    LARGE_INTEGER tq[7];   /* SKIPREFRESH timing: [0]/[1] step 7, [2]/[3] step 8c, [4]/[5] step 11, [6] pass start */
    int skip7;

    QueryPerformanceCounter(&tq[6]);

    if (!ss || !gz) { logf("RZ   ABORT: SIMSPR/GZGraphicD not loaded"); return; }

    /* CRASH HUNT (2026-08-28): force MIN zoom before resizing. The headroom census ran at zoom 3 and
       found >7x margin at 2048x1081, contradicting the 16384-overflow story; min zoom (whole map
       visible) is the untested worst case. vt+0x38 = setzoom = SIMSPR+0x6752 [from sc3probe]. */
    if (g_minzoom && !g_zoomed) {
        DWORD *vt = *(DWORD **)iso, setz;
        if (!IsBadReadPtr(vt, 0x3c) && (setz = vt[0x38 / 4]) == (DWORD)ss + 0x6752) {
            DWORD za[1]; za[0] = 0;
            logf("RZ   MINZOOM: forcing zoom %lu -> 0 before resize", v[0x28 / 4]);
            rz_thiscall(iso, (void *)setz, za, 1);
            logf("RZ   MINZOOM: zoom now %lu", v[0x28 / 4]);
        } else {
            logf("RZ   MINZOOM: setzoom slot mismatch, NOT forcing (vt+0x38=0x%08lX want 0x%08lX)",
                 IsBadReadPtr(vt, 0x3c) ? 0 : vt[0x38 / 4], (DWORD)ss + 0x6752);
        }
        g_zoomed = 1;
    }

    R = v[0x74 / 4];
    B = v[0x4ec / 4];
    logf("RZ   ---- resize to %lux%lu ---- iso=0x%08lX R=0x%08lX B=0x%08lX bridge=0x%08lX",
         w, ht, (DWORD)iso, R, B, (DWORD)g_bridge);

    /* 1. extent. WORLD space, moving origin: right/bottom are left/top PLUS the size. */
    logf("RZ   extent BEFORE: (%ld,%ld,%ld,%ld) -> %ldx%ld  dirtygrid=%lux%lu cell=%ldx%ld",
         (LONG)v[0x54 / 4], (LONG)v[0x58 / 4], (LONG)v[0x5c / 4], (LONG)v[0x60 / 4],
         (LONG)v[0x5c / 4] - (LONG)v[0x54 / 4], (LONG)v[0x60 / 4] - (LONG)v[0x58 / 4],
         v[0x364 / 4], v[0x368 / 4], (LONG)v[0x374 / 4], (LONG)v[0x378 / 4]);
    g_rz_step = 1;
    v[0x5c / 4] = v[0x54 / 4] + w;
    v[0x60 / 4] = v[0x58 / 4] + ht;
    v[0x64 / 4] = v[0x54 / 4];
    v[0x68 / 4] = v[0x58 / 4];
    v[0x6c / 4] = v[0x5c / 4];
    v[0x70 / 4] = v[0x60 / 4];

    /* 2. the game's own dirty-grid dimension table (mode 0 = resolution-dependent). */
    g_rz_step = 2;
    a5[0] = w; a5[1] = ht; a5[2] = (DWORD)&gw; a5[3] = (DWORD)&gh; a5[4] = 0;
    rz_thiscall(NULL, (void *)((DWORD)ss + RVA_GRIDDIMS), a5, 5);
    if (gw == 0 || gh == 0) {
        logf("RZ   REFUSE: FUN_100059fb returned %lux%lu - refusing to call FUN_1000e2c0 with a "
             "zero dimension (it would new[] a 0-byte grid)", gw, gh);
        return;
    }

    /* 3. dirty grid. 4. grid B - Init's very next step; omitting it HANGS FUN_10018cdf. */
    g_rz_step = 3;
    a2[0] = gw; a2[1] = gh;
    rz_thiscall(iso, (void *)((DWORD)ss + RVA_DIRTYGRID), a2, 2);
    rz_cellfix(iso);   /* round the cell size up: no row/column may map past the grid (DIRTCLIP block) */
    g_rz_step = 4;
    a3[0] = 8; a3[1] = 8; a3[2] = 0;
    rz_thiscall(iso, (void *)((DWORD)ss + RVA_GRIDB), a3, 3);
    logf("RZ   extent AFTER: (%ld,%ld,%ld,%ld) -> %ldx%ld  dirtygrid=%lux%lu cell=%ldx%ld  %s",
         (LONG)v[0x54 / 4], (LONG)v[0x58 / 4], (LONG)v[0x5c / 4], (LONG)v[0x60 / 4],
         (LONG)v[0x5c / 4] - (LONG)v[0x54 / 4], (LONG)v[0x60 / 4] - (LONG)v[0x58 / 4],
         v[0x364 / 4], v[0x368 / 4], (LONG)v[0x374 / 4], (LONG)v[0x378 / 4],
         ((LONG)v[0x374 / 4] > 0 && (LONG)v[0x374 / 4] < 4096 &&
          (LONG)v[0x378 / 4] > 0 && (LONG)v[0x378 / 4] < 4096)
             ? "(cell sizes plausible)" : "<< CELL SIZES IMPLAUSIBLE - rect arithmetic is wrong");

    /* 5-6. the two surfaces. */
    g_rz_step = 5;
    rz_recreate_raster(R, "render-target iso+0x74",  w, ht, gz);
    g_rz_step = 6;
    rz_recreate_raster(B, "device-surface iso+0x4ec", g_cz_dev_w > 0 ? (DWORD)g_cz_dev_w : w,   /* task cityzoom */
                       g_cz_dev_h > 0 ? (DWORD)g_cz_dev_h : ht, gz);

    /* 7. the render lever. SKIPREFRESH: skipped by default (see g_skiprefresh). With SKIPREFRESH=2 it is skipped only
       when the active layer is the base layer, so step 11 runs once; with a non-base layer the original pair runs. */
    g_rz_step = 7;
    QueryPerformanceCounter(&tq[0]);
    skip7 = g_skiprefresh == 1 || (g_skiprefresh == 2 && b[0x28 / 4] && b[0x28 / 4] == b[0x2c / 4]);
    if (skip7) {
        logf("RZ   [step 7] SKIPREFRESH=%d: skipped (active layer bridge+0x28 = 0x%08lX, base layer 0x%08lX)",
             g_skiprefresh, b[0x28 / 4], b[0x2c / 4]);
    } else {
        fa[0] = 0; fa[1] = b[0x78 / 4]; fa[2] = b[0xa8 / 4]; fa[3] = 0; fa[4] = 0;
        logf("RZ   FUN_10018cdf -> %d",
             rz_thiscall(g_bridge, (void *)((DWORD)ss + RVA_BRIDGE_FILL), fa, 5));
    }
    QueryPerformanceCounter(&tq[1]);

    /* 8. re-register the object drawables (buildings, roads).
       DEFECT B FIX (2026-08-29): step 8 used to call the LEAF FUN_1000fa36(iso,1,0) directly. That
       only re-stamps the iso+0x3a4 object set into the fine grid iso+0x380 as tag-1 nodes; it does
       NOT clear the grid first, does NOT do the tag-2 region pickup, and does NOT recompute each
       object's DRAW KEY (wrapper+0x24). Result on a real display: after a resize, buildings and
       roads vanished at every camera position (terrain/zones self-heal on scroll via System B, the
       object grid does not). Root cause + evidence: RESIZABLE_WINDOW.md §9, verify/resize_storedrect/.

       The engine's real object re-register is FUN_1000c9bd (FUN_1000fa36's SOLE caller), and its
       caller FUN_10006a55 recomputes draw keys via FUN_1000c8f9 first. So we now run, exactly as
       FUN_10006a55 does at 0x10006a55:
         8a. FUN_1000c8f9(iso)                       - recompute every object's draw key
         8b. FUN_1000c9bd(iso, &sentinel, iso+0x54, 1) - clear grid + tag-2 pickup + FUN_1000fa36
       FUN_1000c9bd calls FUN_1000fa36 internally, so the bare leaf call is REMOVED, not kept.
       Both internal taggers (FUN_1000cedb tag-2, FUN_1000ef50 tag-1) are grid-B-clamp-hooked, so
       this path is crash-protected. Convention + args are disassembled from the engine's own call
       at 0x10006bc0 (ecx=iso; push &rect{0x80000001 x4}; push iso+0x54; push 1; ret 0xC). */
    g_rz_step = 8;
    logf("RZ   [step 8a] FUN_1000c8f9(iso) - recompute object draw keys");
    rz_thiscall(iso, (void *)((DWORD)ss + RVA_DRAWKEY), NULL, 0);
    {
        /* the sentinel RECT the engine passes as param_1: four dwords of 0x80000001 */
        LONG sentinel[4];
        DWORD c9[3];
        sentinel[0] = (LONG)0x80000001; sentinel[1] = (LONG)0x80000001;
        sentinel[2] = (LONG)0x80000001; sentinel[3] = (LONG)0x80000001;
        c9[0] = (DWORD)&sentinel[0];   /* param_1: &sentinel RECT */
        c9[1] = (DWORD)iso + 0x54;     /* param_2: scroll origin iso+0x54 */
        c9[2] = 1;                     /* param_3: recompute (passed through to FUN_1000fa36) */
        logf("RZ   [step 8b] FUN_1000c9bd(iso, &sentinel, iso+0x54, 1) - clear grid + region pickup "
             "+ re-register (the real object re-register, not the leaf FUN_1000fa36)");
        rz_thiscall(iso, (void *)((DWORD)ss + RVA_OBJREREG), c9, 3);
        logf("RZ   [step 8b] FUN_1000c9bd returned");
    }

    /* 8c. DEFECT A+B FIX (2026-08-29): re-issue HIDE-then-SHOW over every occupied cell of the
       System-B tile grid iso+0x24, so terrain, zones, BUILDINGS and ROADS re-register into the
       freshly rebuilt draw buffer. 8a/8b handle the sprite/object grid (iso+0x380); they left the
       System-B tile drawables untouched, which is why after a resize the new area was black until a
       scroll (terrain/zones) and buildings/roads never returned at all. The engine only re-registers
       these on a view TRANSITION, via FUN_100071a3's inner loop - and FUN_100071a3 is reached only
       from the rotate/zoom handlers, never from a resize. A data-layer toggle repaired the screen by
       hand precisely because it drove that transition.

       This is that inner loop, extracted NET-ZERO (no zoom/rotation change, invisible): per occupied
       cell, FUN_10006c67 clears the current-zoom sublayer bits (+0x38) and FUN_10006efc re-sets and
       re-issues them (+0x34). Both key off the same zoom/scale, so bits end where they started.
       Cell layout confirmed from FUN_10005b42; call args from FUN_100071a3:61-64. iso+0x28 = ZOOM,
       iso+0x2c = ROTATION (corrected 2026-08-29). The sublayer primitives self-lock via iso+0x46c
       when async (iso+0x3c9), so no outer render lock is added here. EXPECT-OR-REFUSE: every pointer
       is IsBadReadPtr-gated and the grid dims are sanity-bounded; a bad cell is skipped, not chased. */
    QueryPerformanceCounter(&tq[2]);
    {
        int zoom = (int)((DWORD *)iso)[0x28 / 4];
        int rot  = (int)((DWORD *)iso)[0x2c / 4];
        int rows = (int)((DWORD *)iso)[0x14 / 4];
        int cols = (int)((DWORD *)iso)[0x18 / 4];
        DWORD *grid = (DWORD *)((DWORD *)iso)[0x24 / 4];
        g_rz_step = 8;
        if (rows < 1 || rows > 4096 || cols < 1 || cols > 4096 || !grid ||
            IsBadReadPtr(grid, (UINT)rows * 4)) {
            logf("RZ   [step 8c] REFUSE grid re-show: rows=%d cols=%d grid=0x%08lX zoom=%d rot=%d",
                 rows, cols, (DWORD)grid, zoom, rot);
        } else {
            DWORD ha[5], sa[5];
            int r, c, occ = 0, shown = 0, badcell = 0;
            for (r = 0; r < rows; r++) {
                DWORD rowp = grid[r];
                if (!rowp || IsBadReadPtr((void *)rowp, (UINT)cols * 0x14)) { badcell++; continue; }
                for (c = 0; c < cols; c++) {
                    DWORD cell = rowp + (DWORD)c * 0x14;
                    DWORD drawable;
                    if ((*(BYTE *)(cell + 0x11) & 0x40) == 0) continue;   /* not occupied */
                    occ++;
                    drawable = *(DWORD *)cell;                            /* cell+0 = drawable */
                    if (!drawable || IsBadReadPtr((void *)drawable, 4)) { badcell++; continue; }
                    /* HIDE then SHOW: args (drawable, zoom, rot, row, col), ecx = iso */
                    ha[0] = drawable; ha[1] = (DWORD)zoom; ha[2] = (DWORD)rot;
                    ha[3] = (DWORD)r; ha[4] = (DWORD)c;
                    rz_thiscall(iso, (void *)((DWORD)ss + RVA_CELL_HIDE), ha, 5);
                    sa[0] = drawable; sa[1] = (DWORD)zoom; sa[2] = (DWORD)rot;
                    sa[3] = (DWORD)r; sa[4] = (DWORD)c;
                    rz_thiscall(iso, (void *)((DWORD)ss + RVA_CELL_SHOW), sa, 5);
                    shown++;
                }
            }
            logf("RZ   [step 8c] grid re-show %dx%d: %d occupied, %d re-shown, %d bad "
                 "(hide+show +0x38/+0x34 per cell)", rows, cols, occ, shown, badcell);
        }
    }

    QueryPerformanceCounter(&tq[3]);

    /* 9. THE PRESENT RECT - DEFECT 1 FIX (2026-08-28), and my error was in the design, not the code.
       I documented step 9 as "already ships as resize_rectfix". It does NOT: that cave hooks INIT
       (BOARD.md:668, "resize_rectfix is inert unless the iso Init runs") and this routine never
       calls Init - they are mutually exclusive. The validation run presented a correctly-rendered
       1280x1024 target through a stale {0,0,800,600} rect, clipped top-left.

       So push it here. Init's own order is erase-then-push:
         FUN_1001084b(iso+0x4d0, *(iso+0x4d0), *(iso+0x4d4))   erase(begin, end)
         FUN_10010586(iso+0x4d0, &rect)                        push_back
       The erase matters MORE for us than for the cave: iso+0x4d0 is append-only with Init and the
       dtor as its only emptiers, so without it every resize would append another rect.
       !! rect is {0,0,w,h} in SCREEN space. Do NOT push iso+0x5c/0x60 the way the cave does - those
       are the WORLD-space right/bottom here (measured 745, 2970), correct only at Init time. */
    {
        DWORD list = (DWORD)iso + 0x4d0;
        g_rz_step = 9;
        DWORD ea[2], pa[1];
        LONG rect[4];
        ea[0] = *(DWORD *)list;
        ea[1] = *(DWORD *)(list + 4);
        logf("RZ   [step 9] present list iso+0x4d0: begin=0x%08lX end=0x%08lX (%ld rect(s)) - "
             "erase then push {0,0,%lu,%lu}", ea[0], ea[1],
             ea[0] ? (LONG)((ea[1] - ea[0]) / 16) : 0L, w, ht);
        rz_thiscall((void *)list, (void *)((DWORD)ss + RVA_LIST_ERASE), ea, 2);
        rect[0] = 0; rect[1] = 0; rect[2] = (LONG)w; rect[3] = (LONG)ht;
        /* (2026-08-31) The "stop the iso present above the bar" FPS hypothesis was FALSIFIED by hand-test
           (iso->1025, bar at 1025-1081, no overlap, FPS still dropped). Reverted to full-height present;
           the bar's per-frame cost is its own redraw, not the iso overlap. See verify/resize_hud. */
        pa[0] = (DWORD)&rect[0];
        rz_thiscall((void *)list, (void *)((DWORD)ss + RVA_LIST_PUSH), pa, 1);
        logf("RZ   [step 9] after: begin=0x%08lX end=0x%08lX (%ld rect(s))",
             *(DWORD *)list, *(DWORD *)(list + 4),
             *(DWORD *)list ? (LONG)((*(DWORD *)(list + 4) - *(DWORD *)list) / 16) : 0L);
    }

    /* 10. THE WHOLE-VIEW REPAINT - DEFECT A+B FIX (2026-08-30). Steps 1-9 recreate the render target
       iso+0x74 but never mark the view dirty, so the per-frame composite FUN_1000dc17 (which only
       processes the incremental dirty-rect lists, empty after a surface recreate) draws nothing into
       the fresh surface. That is why buildings/roads and the newly exposed area stayed blank until a
       manual data-layer toggle - the toggle runs the iso-view whole-view repaint (iso vtable+0x144 =
       FUN_1000db86), bracketed by the device batch, at FUN_1001818c:53-55.
         Root cause + evidence: RESIZABLE_WINDOW.md §9, verify/resize_pipeline/.
       Drawable RE-REGISTRATION (steps 8a/8b/8c) was proven NOT to be the fix (65536/65536 cells
       re-shown, no visual change) - the missing work is this full re-rasterization, not registration.

       FUN_1000db86 does FUN_1000e248 (clear draw lists + dirty grid) then tessellates the whole extent
       into 64 dirty rects and sets iso+0x32c=1, so the very next composite redraws the entire view -
       terrain, zones, buildings, roads and sprites alike. We call it directly by RVA (verified iso
       vtable+0x144 -> FUN_1000db86 from the PE); it is __fastcall(ecx=iso), no args. The device begin/
       end batch the toggle wraps it in is for a synchronous present; the game composites every frame,
       so marking dirty here suffices and avoids dispatching unverified device vtable slots. */
    g_rz_step = 10;
    {
        /* The DATA-VIEW TOGGLE's exact bracket, FUN_1001818c:53-55 (cMapView = g_bridge):
             (*(device)+0x240)()   device begin batch - binds the recreated surface
             (*(iso)+0x144)()      iso whole-view repaint = FUN_1000db86
             (*(device)+0x244)()   device end batch - PRESENTS to the recreated surface
           Step-10-alone (repaint without the batch) was hand-tested and did NOT present; rotating the
           view (which repaints but never runs this device batch) also does not fix it, while switching
           to a data/utility overlay and back DOES. So the device present batch is the operative part.
           device = *(cMapView+0x14) = *(g_bridge+0x14), a GZGraphicD device; its +0x240/+0x244 are
           called through the LIVE vtable (as the engine does), IsBadReadPtr-gated. FUN_1000db86 is
           called by RVA (== iso vt+0x144, PE-verified). Evidence: verify/resize_pipeline/RESULTS.md. */
        DWORD dev = ((DWORD *)g_bridge)[0x14 / 4];
        DWORD *dvt = (dev && !IsBadReadPtr((void *)dev, 4)) ? *(DWORD **)dev : NULL;
        int have_batch = (dvt && !IsBadReadPtr(dvt, 0x248));
        if (have_batch) {
            logf("RZ   [step 10] device batch begin: dev=0x%08lX +0x240", dev);
            rz_thiscall((void *)dev, (void *)dvt[0x240 / 4], NULL, 0);
        } else {
            logf("RZ   [step 10] device batch REFUSED (dev=0x%08lX dvt=0x%08lX) - repaint only",
                 dev, (DWORD)dvt);
        }
        logf("RZ   [step 10] FUN_1000db86(iso) - whole-view repaint (iso vt+0x144)");
        rz_thiscall(iso, (void *)((DWORD)ss + RVA_FULLREPAINT), NULL, 0);
        if (have_batch) {
            rz_thiscall((void *)dev, (void *)dvt[0x244 / 4], NULL, 0);
            logf("RZ   [step 10] device batch end +0x244 - presented; iso+0x32c=%d",
                 *(BYTE *)((DWORD)iso + 0x32c));
        } else {
            logf("RZ   [step 10] FUN_1000db86 returned - iso+0x32c=%d (no batch)",
                 *(BYTE *)((DWORD)iso + 0x32c));
        }
    }

    /* 11. RESTORE THE BASE VIEW WITH A FORCED REFRESH - DEFECT A+B FIX (2026-08-30).
       Reading FUN_10018cdf + FUN_100182ba (SetDataView) exposed that step 7 calls FUN_10018cdf with the
       WRONG args: FUN_10018cdf(bridge, 0, *(bridge+0x78), *(bridge+0xa8), 0, 0) - it passes layer=0,
       which NULLS the active layer (bridge+0x28), and force=0, so the full-grid refresh (gated on
       bVar7||force) runs only if the layer changed. The data-view toggle's "return to base view",
       SetDataView(0), instead calls FUN_10018cdf(bridge, *(bridge+0x2c), *(bridge+0x80), *(bridge+0x80),
       0, 1) - the BASE layer (not null), the BASE renderer, and force=1. So the resize left the active
       layer null with no forced repaint; the toggle restored it. That is why re-registering drawables,
       repainting, and the device batch all failed - none restored the active layer.

       This step reproduces SetDataView(0)'s core (bypassing its mode-guard so it runs even though mode is
       already 0), with force=1. The base renderer bridge+0x80 is always valid (unlike overlay
       renderers), so this is the safe half of the toggle. Since step 7 nulled bridge+0x28, bVar7 here is
       true -> FUN_100184d9 re-register + the forced grid refresh both run.
       [CONFIRMED arg difference @ SIMSPR 0x10018cdf, 0x100182ba]; [UNCERTAIN] that it repairs the screen. */
    g_rz_step = 11;
    QueryPerformanceCounter(&tq[4]);
    if (g_skiprefresh == 1) {
        logf("RZ   [step 11] SKIPREFRESH=1: skipped (no map-wide refresh, active layer stays 0x%08lX)",
             ((DWORD *)g_bridge)[0x28 / 4]);
    } else {
        DWORD layer = ((DWORD *)g_bridge)[0x2c / 4];   /* base layer  = *(bridge+0x2c) */
        DWORD rend  = ((DWORD *)g_bridge)[0x80 / 4];   /* base render = *(bridge+0x80) */
        if (!layer || IsBadReadPtr((void *)layer, 4) || !rend || IsBadReadPtr((void *)rend, 4)) {
            logf("RZ   [step 11] REFUSE base-view refresh: layer=0x%08lX rend=0x%08lX", layer, rend);
        } else {
            DWORD da[5];
            da[0] = layer; da[1] = rend; da[2] = rend; da[3] = 0; da[4] = 1;  /* force = 1 */
            logf("RZ   [step 11] FUN_10018cdf(bridge, base layer 0x%08lX, base rend 0x%08lX, force=1) "
                 "- SetDataView(0) core, restore active layer + forced refresh", layer, rend);
            rz_thiscall(g_bridge, (void *)((DWORD)ss + RVA_BRIDGE_FILL), da, 5);
            logf("RZ   [step 11] returned - active layer bridge+0x28 = 0x%08lX",
                 ((DWORD *)g_bridge)[0x28 / 4]);
        }
    }
    QueryPerformanceCounter(&tq[5]);
    {
#define RZ_MS(a, z) ((double)(tq[z].QuadPart - tq[a].QuadPart) * 1000.0 / (double)g_freq.QuadPart)
        logf("RZ   TIMING skiprefresh=%d step7=%.1f ms%s step8c=%.1f ms step11=%.1f ms steps1-11=%.1f ms",
             g_skiprefresh, RZ_MS(0, 1), skip7 ? " (skipped)" : "", RZ_MS(2, 3), RZ_MS(4, 5), RZ_MS(6, 5));
#undef RZ_MS
    }

    /* 12. HUD REFLOW - top-strip PROOF (2026-08-30). The HUD lays out once at construction and never
       re-runs on a window resize, so reflowing its anchor table (the FUN_100270e5 wrap) only takes
       effect if we DRIVE a re-layout. Do the guarded destruct+rebuild of the captured top-strip HUD
       window: FUN_100266c1(this) tears down its contents (guarded by the built-flag vt+0xf0(0x4000);
       does NOT free `this` or detach it), then FUN_10024a96(this) rebuilds - re-running the wrapped
       producer, which reflows the anchors for the live width. Both __fastcall(this). g_hud_top was
       captured by the producer wrap at construction. SIMUI. Only the top strip in this proof; the
       height-keyed side/panel tables (FUN_1004c3e9/FUN_1004cdcd) are a later increment. */
    /* 12. HUD LAB (2026-08-31, verify/resize_hudlab/PRE.md). Only with SC3RESIZE_HUDLAB=1; otherwise
       the HUD is left NATIVE and this whole step is skipped (the shipped viewport build).

       This step does NOT widen the bar inline. It censuses the child surfaces at their native extent
       and ARMS the A/B phase machine, which ticks in the per-frame poll: phase A profiles the bar at
       native width, then the widen is applied and phase B profiles it full-width. Same process, city,
       window size and zoom across both phases - the run supplies its own control, which is what makes
       the FPS delta attributable to bar width and nothing else. */
    if (g_hud_top && !IsBadReadPtr(g_hud_top, 0xc0)) {
        g_rz_step = 12;

        /* Repositioning that applies on BOTH the ship path and the lab path. Wiring this inside the

           g_hudlab branch was a real bug: run 30 took the ship path and the minimap never docked,

           while run 29 (lab armed) had worked. A shipping feature must not live in a diagnostic branch. */

        if (g_cluster) {


            /* Cluster mode replaces both: nothing is widened, everything is translated at native size. */


            rz_mini_dock();


            rz_cluster_layout();


        } else {


            rz_mini_dock();


            rz_anchor_all();


        }

        if (g_hudlab) {
            /* DIAGNOSTIC path: census now, then let the A/B phase machine drive the dock+fit so the
               profiler gets a native-width control phase first. */

            rz_hud_surfaces("BEFORE-setrect");
            /* SIDE PANEL (run 21) - READ-ONLY. Confirm FUN_1004e63e's object really is the in-city
               side panel: a tall narrow rect at a screen edge. Children at +0xc0/+0xc4/+0xc8/+0xcc
               /+0x114, only +0xcc tiled; span for the tile loop = *(+0x10c) - *(+0x104). Moves
               nothing - this run only decides whether the identification holds. */
            if (g_side_top && !IsBadReadPtr(g_side_top, 0x120)) {
                DWORD *s = (DWORD *)g_side_top;
                static const int so[5] = { 0xc0, 0xc4, 0xc8, 0xcc, 0x114 };
                int k;
                logf("SIDE> panel=0x%08lX vt=0x%08lX rect this+0x14..0x20=[%ld %ld %ld %ld] "
                     "tilespan=*(+0x10c)-*(+0x104)=%ld-%ld=%ld",
                     (DWORD)s, s[0], (LONG)s[0x14/4], (LONG)s[0x18/4], (LONG)s[0x1c/4],
                     (LONG)s[0x20/4], (LONG)s[0x10c/4], (LONG)s[0x104/4],
                     (LONG)s[0x10c/4] - (LONG)s[0x104/4]);
                for (k = 0; k < 5; k++) {
                    DWORD ch = s[so[k]/4];
                    if (!ch || IsBadReadPtr((void *)ch, 0x2c)) {
                        logf("SIDE> child +0x%x = 0x%08lX (null/unreadable)", so[k], ch); continue;
                    }
                    logf("SIDE> child +0x%x = 0x%08lX dims=%lux%lu%s", so[k], ch,
                         ((DWORD *)ch)[0x24/4], ((DWORD *)ch)[0x28/4],
                         so[k] == 0xcc ? "   <<< THE TILED ONE (step = its HEIGHT, vt+0x3c)" : "");
                }
            } else {
                logf("SIDE> panel NOT captured (ctor hook did not fire) - identification untested");
            }
            {   /* every captured candidate window, with its rect - the minimap is the roughly
                   SQUARE one. Identification by geometry, decided after the fact from the log. */
                int cs, ci2;
                for (cs = 0; cs < 2; cs++) {
                    logf("CAPT> class %c (%s): %ld instance(s)", 'A' + cs,
                         cs == 0 ? "FUN_1001a983/paint FUN_1001ad52" : "FUN_10060ba9/paint FUN_10060f59",
                         g_capt_n[cs]);
                    for (ci2 = 0; ci2 < g_capt_n[cs]; ci2++) {
                        DWORD *w = (DWORD *)g_capt[cs][ci2];
                        LONG x1, y1, x2, y2;
                        if (!w || IsBadReadPtr(w, 0x24)) {
                            logf("CAPT>   [%d] unreadable", ci2); continue;
                        }
                        x1 = (LONG)w[0x14/4]; y1 = (LONG)w[0x18/4];
                        x2 = (LONG)w[0x1c/4]; y2 = (LONG)w[0x20/4];
                        logf("CAPT>   [%d] 0x%08lX vt=0x%08lX rect=[%ld %ld %ld %ld] %ldx%ld%s",
                             ci2, (DWORD)w, w[0], x1, y1, x2, y2, x2 - x1, y2 - y1,
                             (x2-x1) > 0 && (y2-y1) > 0 &&
                             (x2-x1) < (y2-y1)*2 && (y2-y1) < (x2-x1)*2 ? "   <<< SQUARE-ISH" : "");
                    }
                }
                /* UI TREE WALK - read-only enumeration from the two windows we already hold.
                   Chosen over a surface->owner create recorder because that would mean re-enabling
                   the FUN_10009efb hook the v2 crash isolated to. No new hook, nothing detoured. */
                /* run 24's tree walk is DISABLED: it produced 21 access violations because node[2] was a guess

                   and the list-head offset turned out to be per-class ([0x2d] in FUN_1004d9be, [0x7d] in

                   FUN_1006e2e9). It must not run again until the node layout is established statically. */

                (void)rz_walk_windows;
            }
            g_hudphase = 1;
            g_phase_ms = GetTickCount() + 3000;
            logf("HUDLAB> armed - phase A (native bar) begins in 3 s, then widen, then phase B");
        } else if (g_hudfit) {
            /* SHIP path: dock the bar to the resized window and refit its background surface, here
               and now on the render thread. Same two calls the lab drives, no phases, no census.
               Both are self-gating and log a refusal rather than forcing anything. */
            RECT cr;

            if (!g_cluster) {
            rz_hud_setrect_w(0);
            if (g_hwnd && GetClientRect(g_hwnd, &cr))
                    rz_hud_fit_surface((DWORD)(cr.right - cr.left));
            rz_bar_children_right();   /* slide the controls beside the minimap */

            }
            /* SC3RESIZE_SIDE on the SHIP path. Placed here deliberately: the first attempt put it
               next to the lab's copy of the same fit block (rz_hudlab_tick phase 2), which is the
               identical wiring mistake that made run 30's minimap dock silently not run. Two
               near-identical blocks exist; this is the one step 12 reaches when the lab is off. */
            if (g_sideon && !g_cluster) {
                RECT sr;
                rz_side_extend();
                if (g_hwnd && GetClientRect(g_hwnd, &sr))
                    rz_side_fit_surface((DWORD)(sr.bottom - sr.top));   /* fill the new height */
                rz_side_children_bottom();                              /* then place the buttons */
            }
        }

        /* ⭐ INPUT GEOMETRY - MUST BE LAST, AND MUST RUN IN EVERY HUD MODE.
         *
         * Last, because SIMUI recomputes the view bounds from the HUD panel edges
         * (FUN_10014a5d broadcasts 0x624a8241, FUN_10048d7a unpacks it). Measured 2026-09-02: after
         * the HUD moved, the rect had been rewritten to [0 0 1952 1025] = client minus the side
         * panel's 96 and the bar's 56. A bounds write done before the moves is simply lost.
         *
         * Every mode, because the first version of this call sat inside rz_cluster_layout, which
         * returns early when cluster mode is off - so switching to dock+span would have silently
         * dropped all four fixes (dead map, dead camera pan, clamped hover label, stranded corner
         * widget) with nothing in the log to say so. Exactly the "wired behind the wrong flag" class
         * this file has been bitten by three times. */
        {   RECT gr;
            if (g_hwnd && GetClientRect(g_hwnd, &gr)) {
                LONG gw = gr.right - gr.left, gh = gr.bottom - gr.top;
                /* ⭐ ANCESTOR WIDENING, IN EVERY MODE.
                 *
                 * This was called only from rz_cluster_layout, so on the dock+span path the HUD's
                 * parent containers kept their [0 0 800 600] rects and the router's per-child
                 * `vt+0xe4` gate rejected every click before the recursion could reach the HUD
                 * `[CONFIRMED @ GZWIND 0x1001ec22]` - the identical defect that made the CLUSTER
                 * HUD unclickable until it was fixed there. Owner-reported "still not clickable"
                 * on dock+span, 2026-09-02, with cluster mode working fine at the same time.
                 *
                 * Runs before rz_input_geometry for the same reason everything else does: the
                 * SIMUI relayout these SetRects provoke clobbers the view bounds, so geometry is
                 * last. */
                if (!g_noparentfix) {
                    LONG k;
                    rz_fix_hud_parents(g_hud_top,  "bar",     gw, gh);
                    rz_fix_hud_parents(g_side_top, "side",    gw, gh);
                    if (g_mini) rz_fix_hud_parents(g_mini, "minimap", gw, gh);
                    for (k = 0; k < g_wins_n && k < 8; k++)
                        rz_fix_hud_parents(g_wins[k].w, "win", gw, gh);
                }
                rz_input_geometry(gw, gh, gw - NAT_W, gh - NAT_H + g_hud_dy);
                if (g_thickframe) rz_make_resizable();
                if (g_presentlog || g_presentfix) {
                    rz_patch_ddblt();
                    logf("PRESENT> hook installed (log=%d fix=%d)", g_presentlog, g_presentfix);
                }

                /* ⭐⭐ THE CASCADE — rebuild every DERIVED rect from the local ones, once, last.
                 *
                 * `vt+0x14c` recomputes this window's +0x14..+0x20 as local + the sum of ancestor
                 * origins and then RECURSES into every child `[CONFIRMED @ SIMUI 0x1006c61b]`, and
                 * `vt+0x168` does the same for the +0x24 source and +0x90 blit-dest rects
                 * `[CONFIRMED @ SIMUI 0x1006d4eb, 0x1006d438, 0x1006d8b4]`. Called on the ROOT it
                 * fixes the whole tree in one pass.
                 *
                 * Why this matters beyond tidiness: the engine positions popups from ABSOLUTE
                 * rects - the tool flyout reads its owning item's +0x14
                 * `[CONFIRMED @ SIMUI 0x1004ec95, 0x1004b8c5]` - so while the derived rects were
                 * stale, every toast and submenu inherited a wrong anchor and had to be corrected
                 * after the fact by a timer.
                 *
                 * `[UNCERTAIN]`: the ancestors are GZWIND / SC3U.exe classes and this slot is only
                 * byte-verified on the SIMUI window base. Guarded, and a refusal is logged rather
                 * than forced. */
                {   DWORD gzb = (DWORD)GetModuleHandleA("GZGraphicD.dll");
                    DWORD *w2 = (gzb && !IsBadReadPtr((void *)(gzb + 0x6cdb8), 4))
                              ? *(DWORD **)(gzb + 0x6cdb8) : NULL;
                    DWORD *snk = (w2 && !IsBadReadPtr(w2, 0x34)) ? (DWORD *)w2[0x30 / 4] : NULL;
                    DWORD *rt  = (snk && !IsBadReadPtr(snk, 0x3c)) ? (DWORD *)snk[0x38 / 4] : NULL;
                    DWORD *rvt = (rt && !IsBadReadPtr(rt, 4)) ? *(DWORD **)rt : NULL;
                    if (rvt && !IsBadReadPtr(rvt, 0x16c) && rvt[0x14c / 4] && rvt[0x168 / 4]) {
                        rz_thiscall(rt, (void *)rvt[0x168 / 4], NULL, 0);   /* src + blit dest */
                        rz_thiscall(rt, (void *)rvt[0x14c / 4], NULL, 0);   /* absolute rects */
                        logf("CASCADE> root 0x%08lX vt+0x168 + vt+0x14c - derived rects rebuilt "
                             "tree-wide from the LOCAL rects", (DWORD)rt);
                    } else {
                        logf("CASCADE> REFUSED: root 0x%08lX vtable has no vt+0x14c/vt+0x168",
                             (DWORD)rt);
                    }
                }
            } else {
                logf("GEOM> SKIPPED: no client rect");
            }
        }
    }

    logf("RZ   ---- done (viewport: steps 1-11%s) ----",
         g_hudlab ? "; step 12 HUD LAB armed" : "; step 12 HUD reflow not shipped, native");
    if (g_census) g_census_ms = GetTickCount() + 2000;   /* census once, after frames have run */
}

/* The HUD widen (ATTEMPT 3, proven safe 2026-08-31: docked + spanned, no crash, no VEH fault).
 *
 * Move+widen the HUD WINDOW itself via its real SetRect (vt+0xc8, 4 int coords; window rect at
 * this+0x14..0x20, GetRect = vt+0xc0). The framework's own window-geometry method - no destruct, no
 * child-class assumptions. The runtime slot is SIMUI FUN_10026776, which sets the rect and repositions
 * 5 internal parts by POSITION only, not size [CONFIRMED @ SIMUI 0x10026776]. Dispatched through the
 * LIVE vtable, so it is correct regardless of the static base.
 *
 * Docks to the CURRENT client size (tracks bigger AND smaller, so a lower-res monitor re-fits instead
 * of leaving the bar off-screen). barH is the bar's own height, preserved.
 *
 * Called by the phase machine at the A->B boundary, on the game thread - the same thread that ran it
 * safely before. */
static void rz_hud_setrect_w(DWORD wantW) {
    DWORD *h = (DWORD *)g_hud_top;
    RECT cr;
    LONG x1, y1, x2, y2;
    int barH;
    DWORD *hvt;
    if (!h || IsBadReadPtr(h, 0xc0)) { logf("HUDLAB> SetRect skipped: g_hud_top unreadable"); return; }
    x1 = (LONG)h[0x14/4]; y1 = (LONG)h[0x18/4]; x2 = (LONG)h[0x1c/4]; y2 = (LONG)h[0x20/4];
    barH = (int)(y2 - y1);
    /* Cache the bar's NATIVE rect here too, not only in the cluster routine.
     * rz_bar_children_right needs the native width to know how far to slide the controls, and the
     * cluster routine (the only other place that cached it) returns early on the dock+span path -
     * so on the path that actually spans the bar the cache was never filled and the slide silently
     * did nothing. Cached BEFORE the SetRect below, while the rect is still native. */
    if (!g_bar_nat_ok && x2 - x1 > 0 && y2 - y1 > 0) {
        g_bar_nat[0] = x1; g_bar_nat[1] = y1; g_bar_nat[2] = x2; g_bar_nat[3] = y2;
        g_bar_nat_ok = 1;
        logf("HUDLAB> cached bar native [%ld %ld %ld %ld] (%ld wide)", x1, y1, x2, y2, x2 - x1);
    }
    hvt = *(DWORD **)h;
    if (!g_hwnd || !GetClientRect(g_hwnd, &cr) || !hvt || IsBadReadPtr(hvt, 0xcc)) {
        logf("HUDLAB> SetRect skipped: no window or vtable unreadable"); return;
    }
    {
        int lw = (int)(cr.right - cr.left), lh = (int)(cr.bottom - cr.top);
        void *setrect = (void *)hvt[0xc8/4];
        /* wantW == 0 means "span the whole client" (the ship path). The sweep passes explicit
           widths, clamped to the client so a sweep step can never exceed the window. */
        int wantX2 = (wantW == 0 || (int)wantW > lw) ? lw : (int)wantW;
        /* g_hud_dy pushes the docked bar below the client edge by the owner-tuned bias, the same
           bias the cluster translate uses. At bias 0 the bar's bottom lands exactly on the client
           edge and the owner reports a black strip below it; the native RCI overhangs its own
           screen bottom by 8 for the same reason. Measured and tuned 2026-09-02. */
        int wantY1 = lh - barH + g_hud_dy, wantY2 = lh + g_hud_dy;
        if (!setrect || barH <= 0 || barH >= lh) {
            logf("HUDLAB> SetRect skipped: setrect=0x%08lX barH=%d lh=%d", (DWORD)setrect, barH, lh);
            return;
        }
        if (x1 == 0 && y1 == wantY1 && x2 == wantX2 && y2 == wantY2) {
            if (!g_reassert_quiet)
                logf("HUDLAB> SetRect skipped: bar already docked at [0,%d,%d,%d]", wantY1, wantX2, wantY2);
            return;
        }
        {
            DWORD a[4];
            a[0] = 0; a[1] = (DWORD)wantY1; a[2] = (DWORD)wantX2; a[3] = (DWORD)wantY2;
            logf("HUDLAB> HUD SetRect vt+0xc8=0x%08lX  [%ld,%ld,%ld,%ld] -> [0,%d,%d,%d]",
                 (DWORD)setrect, x1, y1, x2, y2, wantY1, wantX2, wantY2);
            rz_thiscall(g_hud_top, setrect, a, 4);
            logf("HUDLAB> HUD SetRect returned; rect now [%ld,%ld,%ld,%ld]",
                 (LONG)h[0x14/4], (LONG)h[0x18/4], (LONG)h[0x1c/4], (LONG)h[0x20/4]);
        }
    }
}

/* ---- HUD FIT: widen the bar's BACKGROUND SURFACE (2026-08-31, SC3RESIZE_HUDFIT=1) ---------------
 *
 * Run 2's census named the blocker: the bar background is child `g_hud_top[0x2a]`, a FIXED 600x56
 * raster of class GZGraphicD+0x1E894, pitch 1200 = width*2 (fix16), holding real art (25525/33600
 * non-zero). The window SetRect can move and widen the WINDOW, but the bar cannot actually span the
 * screen while its backing surface is 600 px wide.
 *
 * That class is one the mod already resizes twice per resize: rz_recreate_raster drives Init
 * FUN_10009efb through vt+0x0c on iso+0x74 and iso+0x4ec, with an expect-or-refuse vtable check.
 * The HUD child passes the same gate, so this is the SAME proven primitive on a new object - not a
 * new mechanism.
 *
 * ⚠️ Recreating a surface DISCARDS its pixels, and the bar's art lives in exactly those pixels. If
 * the engine only blits a cached bar surface rather than repainting it, a bare recreate yields a
 * BLANK bar. So this snapshots the old image first and, after the recreate, TILES it horizontally
 * across the wider surface. Tiling is a deliberate choice over stretching: no filtering, no new art,
 * and the bar's background is a repeating texture, so tiling is the artefact-free option.
 *
 * `[UNCERTAIN]` until hand-tested: whether the engine repaints over our tiled content each frame
 * (in which case the tiling is harmless and redundant) or preserves it (in which case the tiling is
 * what makes the bar look right). Either way the surface is the correct width, which is the point.
 *
 * Self-gated: no g_hud_top, no capture, or a refused vtable -> does nothing and says so. */
/* Refit ONE HUD child surface to `liveW`, preserving its own native height and tiling its own
 * pristine art across the new width.
 *
 * Generalised from the [0x2a]-only version after run 16: the dominant per-frame cost is NOT the
 * 600x56 background but **child[0x2b], a 16x64 filler strip the engine tiles across the bar's
 * width - 6892 blits in 8 s at 2048 against 24 at 600, ~46 DirectDraw calls PER FRAME.** If the
 * engine's tile count is the region width divided by the SOURCE width, widening [0x2b] collapses
 * that count. Same primitive, different child - so each child needs its OWN art cache and its OWN
 * native height (a shared cache would tile [0x2a]'s 56-row art into [0x2b]'s 64-row surface).
 *
 * `[UNCERTAIN]`, with a clean falsifier: that the tile count follows source width. If [0x2b]'s blit
 * count is unchanged after widening it, the hypothesis is dead and the fix does nothing. */
typedef struct { BYTE *art; DWORD w, h, pitch; } HUDART;
static HUDART g_hud_cache[6];        /* index i => child [0x2a + i] */

static void rz_hud_fit_child(int ci, DWORD liveW) {
    DWORD *h = (DWORD *)g_hud_top;
    HMODULE gz = GetModuleHandleA("GZGraphicD.dll");
    DWORD obj, sub, oldbits, oldpitch, oldw, oldh;
    HUDART *ca = &g_hud_cache[ci - 0x2a];
    BYTE *snap = NULL;

    if (!g_hudfit) return;
    if (ci < 0x2a || ci > 0x2f) return;
    if (!h || IsBadReadPtr(h, 0xc0) || !gz) { logf("HUDFIT> skipped: no HUD window or GZGraphicD"); return; }
    obj = h[ci];
    if (!obj || IsBadReadPtr((void *)obj, 0x48)) { logf("HUDFIT> skipped: child[0x%x] unreadable", ci); return; }

    oldw = ((DWORD *)obj)[0x24 / 4]; oldh = ((DWORD *)obj)[0x28 / 4];
    sub  = ((DWORD *)obj)[0x44 / 4];
    if (!sub || IsBadReadPtr((void *)sub, 0xf8)) { logf("HUDFIT> skipped: sub unreadable"); return; }
    oldbits = ((DWORD *)sub)[0xf0 / 4]; oldpitch = ((DWORD *)sub)[0xf4 / 4];
    /* Remember the surface we are about to replace - FUN_1001420d overwrites the sub-object pointer
       without freeing the old one, so the previous DD surface may still be blitted by a holder. */
    if (!IsBadReadPtr((void *)sub, 8)) {
        g_bar_surf_prev = ((DWORD *)sub)[0x04 / 4];
        g_child_surf_prev[ci - 0x2a] = g_bar_surf_prev;
    }
    /* Re-fit on ANY width change, not just a widen - a later resize to a SMALLER window must bring
       the bar back down, or it stays wider than the window it lives in. */
    if (liveW == oldw) {
        if (!g_reassert_quiet)
            logf("HUDFIT> already fitted: surface width %lu == live width %lu", oldw, liveW);
        return;
    }

    /* ONE-TIME snapshot of the PRISTINE native art, cached for the life of the process.
       Two bugs this avoids, both of which only appear on the SECOND resize:
       (1) re-snapshotting would capture already-TILED content and re-tile it at a new width,
           producing misaligned seams that compound every resize;
       (2) `oldh` after a recreate is 56+RZ_SURFACE_SLACK = 64, so recreating at `oldh` would grow
           the bar by 8 px every single resize. The cached NATIVE height is the fix.
       Read RAW - the standing rule. The surface has bits here because the engine locked and drew it
       at construction (the BEFORE-setrect census reads them fine). */
    if (!ca->art && oldbits && oldpitch && oldh &&
        !IsBadReadPtr((void *)oldbits, oldpitch * oldh)) {
        ca->art = (BYTE *)HeapAlloc(GetProcessHeap(), 0, oldpitch * oldh);
        if (ca->art) {
            memcpy(ca->art, (void *)oldbits, oldpitch * oldh);
            ca->w = oldw; ca->h = oldh; ca->pitch = oldpitch;
            logf("HUDFIT> child[0x%x]: cached pristine art %lux%lu pitch=%lu (one-time)",
                 ci, oldw, oldh, oldpitch);
        }
    }
    if (!ca->art) {
        logf("HUDFIT> child[0x%x] WARNING: no cached art (bits=0x%08lX pitch=%lu) - may come back blank",
             ci, oldbits, oldpitch);
    }
    snap     = ca->art;
    oldw     = ca->w     ? ca->w     : oldw;
    oldpitch = ca->pitch ? ca->pitch : oldpitch;
    oldh     = ca->h     ? ca->h     : oldh;   /* THIS child's NATIVE height - never the padded one */

    logf("HUDFIT> child[0x%x]=0x%08lX -> refitting to %lux%lu (art %lux%lu)",
         ci, obj, liveW, oldh, oldw, oldh);

    if (!rz_recreate_raster(obj, "HUD child surface", liveW, oldh, gz)) {
        logf("HUDFIT> child[0x%x] recreate REFUSED - left as it was", ci);
        return;
    }

    /* Tile the snapshot across the new surface - UNDER A BALANCED LOCK.
     *
     * Run 4 read bits=0 here and I first read that as a failed allocation. It was not. The static
     * read (RESULTS.md) proves `sub+0xf0`/`+0xf4` are written ONLY by the lock:
     *   create  sub->vt[0x40] = FUN_10019273 - builds the DD surface, sets sub+0xe0/+0xec,
     *                                          NEVER writes bits/pitch  [CONFIRMED @ 0x10019273]
     *   lock    sub->vt[0x0c] = FUN_10018a82 - refcounts sub+0xe4; on 0->1 calls IDDS::Lock and
     *                                          copies DDSD lpSurface (sub+0x30) -> sub+0xf0 and
     *                                          DDSD lPitch (sub+0x1c) -> sub+0xf4
     *                                                                   [CONFIRMED @ 0x10018a82]
     *   unlock  sub->vt[0x10] = FUN_10018b53 - refcounts down; on ->0 calls IDDS::Unlock
     *                                                                   [CONFIRMED @ 0x10018b53]
     * So bits==0 straight after a recreate is the CORRECT state for every surface of this class.
     * Waiting for it to become non-zero would likely wait forever: the bar is built once, and
     * per-frame compositing blits FROM the surface without ever taking a CPU lock.
     *
     * The lock is refcounted, so a BALANCED pair nests safely with engine usage. That refcount is
     * also exactly why the standing rule forbids an out-of-band unlock - dropping the depth to 0
     * invalidates a pointer the engine may be mid-use of. We only ever add and remove our own level.
     *
     * EXPECT-OR-REFUSE on the sub-object vtable before dispatching through it - the same discipline
     * that turned the old GetSurfaceDesc crash into a logged refusal: identify by COMPARING the
     * vtable against a known MODULE+RVA, never by calling through the pointer being identified.
     *
     * `[UNCERTAIN]`: nothing proves this surface is lockable at an arbitrary moment on the render
     * thread. A refusal or a failed lock is a LOGGED RESULT, never a forced write. */
    if (snap) {
        DWORD nsub = ((DWORD *)obj)[0x44 / 4];
        DWORD nw = ((DWORD *)obj)[0x24 / 4], nh = ((DWORD *)obj)[0x28 / 4];
        DWORD *svt = NULL, want = (DWORD)gz + GZ_RVA_VT_SURFACE;

        if (!nsub || IsBadReadPtr((void *)nsub, 0xf8)) {
            logf("HUDFIT> sub 0x%08lX unreadable after recreate - not tiling", nsub);
        } else if ((svt = *(DWORD **)nsub) == NULL || IsBadReadPtr(svt, 0x14) ||
                   (DWORD)svt != want) {
            logf("HUDFIT> REFUSE lock: sub vtable 0x%08lX != GZGraphicD+0x%X (0x%08lX) - not the "
                 "class we think, refusing to dispatch through it", (DWORD)svt, GZ_RVA_VT_SURFACE, want);
        } else {
            int lk;
            /* capture the NEW surface here, at refit time - not at dump time (run 15's error) */
            g_bar_surf = IsBadReadPtr((void *)nsub, 8) ? 0 : ((DWORD *)nsub)[0x04 / 4];
            g_child_surf[ci - 0x2a] = g_bar_surf;
            if (ci == 0x2b) g_ret_filter = g_bar_surf;   /* record callers of the TILED child */
            logf("HUDFIT> bar IDirectDrawSurface* now 0x%08lX (was 0x%08lX)",
                 g_bar_surf, g_bar_surf_prev);
            lk = rz_thiscall((void *)nsub, (void *)svt[0x0c / 4], NULL, 0);
            DWORD nbits = ((DWORD *)nsub)[0xf0 / 4], npitch = ((DWORD *)nsub)[0xf4 / 4];
            logf("HUDFIT> lock vt+0x0c=0x%08lX -> %d | depth=%lu bits=0x%08lX pitch=%lu",
                 svt[0x0c / 4], lk & 0xff, ((DWORD *)nsub)[0xe4 / 4], nbits, npitch);
            if (!(lk & 0xff) || !nbits || !npitch || IsBadReadPtr((void *)nbits, npitch * nh)) {
                logf("HUDFIT> lock did not yield a usable backing - not tiling");
            } else {
                DWORD r, c, copied = 0;
                for (r = 0; r < nh && r < oldh; r++) {
                    BYTE *dst = (BYTE *)nbits + r * npitch;
                    BYTE *src = snap + r * oldpitch;
                    for (c = 0; c < nw; c += oldw) {
                        DWORD run = (nw - c < oldw) ? (nw - c) : oldw;
                        memcpy(dst + c * 2, src, run * 2);
                        copied += run;
                    }
                }
                logf("HUDFIT> tiled the %lux%lu art across %lux%lu (pitch %lu, %lu px written)",
                     oldw, oldh, nw, nh, npitch, copied);
            }
            if (lk & 0xff) {   /* unlock ONLY the level we took - never below our own */
                int ul = rz_thiscall((void *)nsub, (void *)svt[0x10 / 4], NULL, 0);
                logf("HUDFIT> unlock vt+0x10 -> %d | depth now %lu", ul & 0xff,
                     ((DWORD *)nsub)[0xe4 / 4]);
            }
        }
        /* ca->art is a process-lifetime per-child cache - deliberately NOT freed here. */
    }
}

/* Refit the HUD child surfaces that scale with the bar's width.
 *   [0x2a] the 600x56 background - what "the bar looks right" depends on;
 *   [0x2b] the 16x64 filler strip - what the FPS cost actually IS (run 16: 6892 blits in 8 s at
 *          2048 = 93% of all DirectDraw Blt time and ~46 calls per frame, against 24 at 600).
 * The other four ([0x2c..0x2f], 104-148 x 18) are discrete widgets, not tiled fill, and are left
 * alone deliberately: widening those would stretch content without removing any blits. */
/* ⭐ THE FPS FIX for the full-width bar — widen the TILE STEP, 2026-09-02.
 *
 * `FUN_10026841` fills the bar by blitting the `[0x2b]` filler once per step and walking the dest
 * leftwards, and the step is NOT the surface width:
 *
 *     iVar4 = *(int *)(param_1 + 0xd8) - *(int *)(param_1 + 0xd0);   // STEP = SOURCE RECT width
 *     ... vt[0x118](*(param_1 + 0xac), param_1 + 0xd0, &local_14, 0);
 *     `[CONFIRMED @ SIMUI 0x10026841]`
 *
 * With a 16-px source rect that is ~46 DirectDraw blits per frame at 2048 = 93% of all Blt time,
 * the measured cost of the full-width bar (`verify/resize_hudlab`, 20 runs). Run 17 already proved
 * widening the SURFACE alone changes nothing, which is what identified the source rect as the real
 * step. `rz_hud_fit_child(0x2b)` has just refit that surface to liveW, so a source rect of liveW
 * has real pixels behind it.
 *
 * `[UNCERTAIN]`, and this is the falsifiable part: that `+0xd0..+0xd8` is a plain source RECT the
 * blit path honours at any width. If the blit clamps it to the surface's original 16, the step stays
 * 16 and the FPS cost survives - a clean negative, visible as an unchanged frame rate.
 *
 * Widen only, never shrink, and only when the surface can actually back it. */
static void rz_hud_srcrect(DWORD liveW) {
    LONG *sr;
    if (!g_hud_top || IsBadWritePtr(g_hud_top, 0xe0)) {
        logf("SRCRECT> skipped: g_hud_top unreadable"); return;
    }
    sr = (LONG *)((DWORD)g_hud_top + 0xd0);
    if (sr[2] - sr[0] <= 0 || sr[3] - sr[1] <= 0) {
        logf("SRCRECT> REFUSED: +0xd0 is not a positive rect [%ld %ld %ld %ld]",
             sr[0], sr[1], sr[2], sr[3]);
        return;
    }
    if (sr[2] - sr[0] >= (LONG)liveW) {
        logf("SRCRECT> already wide: [%ld %ld %ld %ld] step=%ld >= %lu",
             sr[0], sr[1], sr[2], sr[3], sr[2] - sr[0], liveW);
        return;
    }
    if (!g_srcrect) {
        logf("SRCRECT> DISABLED (SC3RESIZE_SRCRECT=0) - leaving the %ld-px tile step, "
             "so the full-width bar keeps its ~%ld blits/frame",
             sr[2] - sr[0], ((LONG)liveW + (sr[2] - sr[0]) - 1) / (sr[2] - sr[0]));
        return;
    }
    logf("SRCRECT> tile step [%ld %ld %ld %ld] step=%ld -> right=%ld step=%lu  (FUN_10026841: "
         "~%ld blits/frame -> ~1)",
         sr[0], sr[1], sr[2], sr[3], sr[2] - sr[0], sr[0] + (LONG)liveW, liveW,
         ((LONG)liveW + (sr[2] - sr[0]) - 1) / (sr[2] - sr[0]));
    sr[2] = sr[0] + (LONG)liveW;
    /* ⚠️ Clamp the source rect to the SURFACE it samples. The widening only ever touched the right
     * edge, leaving the bottom at 64 while child[0x2a]'s refit surface is 2048x56 - a source rect 8
     * rows taller than its own surface, which is the shape that makes a blit read past the end.
     * Suspected in the "some textures are rendering at the top" report; clamped here so the source
     * can never exceed the surface regardless. */
    {   DWORD obj = ((DWORD *)g_hud_top)[0x2a];
        if (obj && !IsBadReadPtr((void *)obj, 0x2c)) {
            LONG sw = (LONG)((DWORD *)obj)[0x24 / 4], sh = (LONG)((DWORD *)obj)[0x28 / 4];
            if (sw > 0 && sr[2] - sr[0] > sw) sr[2] = sr[0] + sw;
            if (sh > 0 && sr[3] - sr[1] > sh) {
                logf("SRCRECT> clamped bottom %ld -> %ld (surface is %ldx%ld)",
                     sr[3], sr[1] + sh, sw, sh);
                sr[3] = sr[1] + sh;
            }
        }
    }
}

static void rz_hud_fit_surface(DWORD liveW) {
    /* ONLY the filler [0x2b] gets widened. [0x2a] is the console BACKGROUND - a unique 600x56 image
     * (ticker well + info-field wells + control-button wells), NOT a repeating texture. Tiling it to
     * liveW duplicated its baked-in button graphics across the surface, which showed up as ghost
     * controls (a blue button + speed squares) painted over the money field (owner, 2026-09-03). The
     * console is painted into a fixed 600-wide rect (+0x120), so it never needs widening; leaving it
     * at native 600 is correct. Only the 16-px filler [0x2b] is a repeating texture and the one whose
     * per-frame tile count the widening was meant to collapse. */
    rz_hud_fit_child(0x2b, liveW);
    rz_hud_srcrect(liveW);   /* after the refit: the surface must back the wider source rect */
}

/* ⭐ SIDE PANEL BACKGROUND — refit its art surfaces to the panel's new HEIGHT, 2026-09-02.
 *
 * `rz_side_extend` makes the panel span the full right edge and the owner reports "a black section
 * on the vertical bar": the panel's art surfaces are the native 96x442, so everything below 442 has
 * nothing drawn in it. This is NOT the bar's problem in a different place - the bar is filled by a
 * TILE LOOP with a 16-px source rect, while the panel simply blits its children, and its tiled child
 * `+0xcc` is NULL (measured live, along with `+0xc4` and `+0x114`). So there is no filler to widen;
 * the background surface itself has to get taller.
 *
 * Same primitive as `rz_hud_fit_child` with the axis swapped: keep the 96 width, grow the height,
 * and tile the cached native art DOWNWARDS (destination row r takes art row r % nativeH).
 *
 * The two live children are at `+0xc0` and `+0xc8` (`FUN_1004e63e` blits five slots: `+0xc0`,
 * `+0xc4`, `+0xc8`, `+0xcc`, `+0x114`; only the first and third are non-NULL here).
 *
 * Every hazard `rz_hud_fit_child` documents applies unchanged and is honoured the same way: a
 * one-time PRISTINE art snapshot (re-snapshotting would capture already-tiled content and compound
 * seams on the second resize), expect-or-refuse on the sub-object vtable before dispatching through
 * it, a balanced lock/unlock of only our own level, and a logged refusal rather than a forced write.
 *
 * `[UNCERTAIN]`: that a taller background surface is what the panel's paint routine actually reads
 * for the full height. If the panel blits a fixed 442-tall destination rect regardless, the extra
 * rows will never appear and the black section survives - a clean negative, visible on screen. */
static HUDART g_side_cache[2];       /* [0] => child +0xc0, [1] => child +0xc8 */
static DWORD  g_side_plainrow[2];    /* the flattest art row (min horizontal variation) - the fill
                                        source, chosen adaptively so the extended area is not streaky */
static LONG   g_side_intended_h;     /* the panel height rz_side_fit_surface is about to SetRect (see art_at) */
static DWORD  g_side_failh[2];       /* the liveH a recreate last FAILED at (per slot). The fit runs
                                        every poll; without this memo a height whose CreateSurface fails
                                        is retried forever, and each failed create churns the video pool
                                        until the game blits a null surface and dies (2026-09-05). */

static void rz_side_fit_child(int slot, DWORD off, DWORD liveH) {
    DWORD *p = (DWORD *)g_side_top;
    HMODULE gz = GetModuleHandleA("GZGraphicD.dll");
    DWORD obj, sub, oldbits, oldpitch, oldw, oldh;
    HUDART *ca = &g_side_cache[slot];
    BYTE *snap;

    if (!p || IsBadReadPtr(p, 0x120) || !gz) { logf("SIDEFIT> skipped: no side panel"); return; }
    obj = p[off / 4];
    if (!obj || IsBadReadPtr((void *)obj, 0x48)) {
        logf("SIDEFIT> child +0x%lx is NULL/unreadable (0x%08lX) - nothing to refit", off, obj);
        return;
    }
    oldw = ((DWORD *)obj)[0x24 / 4]; oldh = ((DWORD *)obj)[0x28 / 4];
    sub  = ((DWORD *)obj)[0x44 / 4];
    if (!sub || IsBadReadPtr((void *)sub, 0xf8)) { logf("SIDEFIT> +0x%lx sub unreadable", off); return; }
    oldbits = ((DWORD *)sub)[0xf0 / 4]; oldpitch = ((DWORD *)sub)[0xf4 / 4];

    /* rz_recreate_raster pads every surface by RZ_SURFACE_SLACK rows, so a surface WE made at liveH
     * reads back as liveH + slack. Comparing against liveH alone never matched, and the re-assert
     * pass (every poll) re-created the background each time. Each re-create leaked the previous
     * 80 KB system-memory surface inside DDRAW: +40 MB/min, game dead at ~1.6 GB after 36 min with
     * the year-end budget dialog open (2026-10-09, Frida: 80x CreateSurface 96x417 per 10 s from
     * this path). The native 96x417 at a 409 request is also "fitted" by the same rule. */
    if (liveH == oldh || liveH + RZ_SURFACE_SLACK == oldh) {
        if (!g_reassert_quiet)
            logf("SIDEFIT> +0x%lx already fitted: surface height %lu for live %lu", off, oldh, liveH);
        return;
    }
    if (!ca->art && oldbits && oldpitch && oldh &&
        !IsBadReadPtr((void *)oldbits, oldpitch * oldh)) {
        ca->art = (BYTE *)HeapAlloc(GetProcessHeap(), 0, oldpitch * oldh);
        if (ca->art) {
            memcpy(ca->art, (void *)oldbits, oldpitch * oldh);
            ca->w = oldw; ca->h = oldh; ca->pitch = oldpitch;
            /* Pick the FLATTEST row (least horizontal RGB565 variation) as the fill source, so the
             * extended background is a clean panel-fill and not a streaky one. Buttons and the top
             * cap have high variation; the plain gap between button clusters is the minimum. */
            {   DWORD rr, best = oldh / 2; DWORD bestv = 0xFFFFFFFF;
                for (rr = 0; rr < oldh; rr++) {
                    const WORD *row = (const WORD *)(ca->art + rr * oldpitch);
                    DWORD x, v = 0;
                    for (x = 1; x < oldw; x++) {
                        int d = (int)row[x] - (int)row[x - 1];
                        v += (DWORD)(d < 0 ? -d : d);
                    }
                    if (v < bestv) { bestv = v; best = rr; }
                }
                g_side_plainrow[slot] = best;
            }
            logf("SIDEFIT> +0x%lx cached pristine art %lux%lu pitch=%lu, flattest fill row %lu",
                 off, oldw, oldh, oldpitch, g_side_plainrow[slot]);
        }
    }
    if (!ca->art) {
        logf("SIDEFIT> +0x%lx WARNING: no cached art (bits=0x%08lX pitch=%lu) - may come back blank",
             off, oldbits, oldpitch);
    }
    snap     = ca->art;
    oldw     = ca->w     ? ca->w     : oldw;
    oldh     = ca->h     ? ca->h     : oldh;
    oldpitch = ca->pitch ? ca->pitch : oldpitch;

    /* Don't re-attempt a height that already failed - the fit runs every poll and each failed
     * video-memory create leaks/churns the pool until the game blits a null surface and crashes. */
    if (g_side_failh[slot] == liveH) return;

    /* ⭐ FORCE SYSTEM MEMORY for the side-panel background (2026-09-05). The stock surface is VIDEO
     * memory (obj+0x8c != 0 -> DDSCAPS_VIDEOMEMORY), and at tall heights, after many resizes, the
     * driver's video CreateSurface starts returning NO surface - EVERY poll - so the fit churned the
     * video pool and the game eventually blitted a null +0x44 (esi=0 READ +0xDC, GZGraphicD+0x18C74).
     * Zeroing obj+0x8c selects the SYSTEMMEMORY branch of FUN_10009efb (worker RE: pool =
     * -(param_1[0x23]!=0) & 3), whose software allocator does not fail like the video pool and hands
     * back a tight width*2 pitch. This surface is tiny (96 x <1000 x 2 = <200KB) and only blitted, so
     * system memory costs nothing visible. Done once; the field then stays zero across recreates. */
    if (!IsBadWritePtr((void *)(obj + 0x8c), 4) && ((DWORD *)obj)[0x8c / 4] != 0) {
        logf("SIDEFIT> +0x%lx obj+0x8c %lu -> 0 (force SYSTEM memory, video pool was failing)",
             off, ((DWORD *)obj)[0x8c / 4]);
        ((DWORD *)obj)[0x8c / 4] = 0;
    }

    logf("SIDEFIT> +0x%lx=0x%08lX -> refitting to %lux%lu (art %lux%lu)",
         off, obj, oldw, liveH, oldw, oldh);
    if (!rz_recreate_raster(obj, "side child surface", oldw, liveH, gz)) {
        logf("SIDEFIT> +0x%lx recreate REFUSED - left as it was", off);
        return;
    }
    /* ⛔ CRASH GUARD (2026-09-05): if the recreate still handed back a NULL DirectDraw surface at
     * +0x44, the game's per-frame Blt wrapper FUN_10018c58 dereferences it (esi=0 READ +0xDC, fault
     * at GZGraphicD+0x18C74) and the process dies. Make it TRANSACTIONAL: re-create at the known-good
     * native size so the object always holds a valid surface, and MEMO this height so we never retry
     * it (the retry loop is what churned the pool into the crash). */
    {   DWORD chk = ((DWORD *)obj)[0x44 / 4];
        if (!chk || IsBadReadPtr((void *)chk, 0xf8)) {
            g_side_failh[slot] = liveH;
            logf("SIDEFIT> +0x%lx recreate yielded NULL surface at h=%lu - rolling back to native "
                 "%lux%lu and MEMOing the height (no more retries at this size)", off, liveH, oldw, oldh);
            rz_recreate_raster(obj, "side child ROLLBACK", oldw, oldh, gz);
            return;
        }
    }
    g_side_failh[slot] = 0;   /* success clears any earlier memo */
    if (snap) {
        DWORD nsub = ((DWORD *)obj)[0x44 / 4];
        DWORD nw = ((DWORD *)obj)[0x24 / 4], nh = ((DWORD *)obj)[0x28 / 4];
        DWORD *svt = NULL, want = (DWORD)gz + GZ_RVA_VT_SURFACE;
        if (!nsub || IsBadReadPtr((void *)nsub, 0xf8)) {
            logf("SIDEFIT> sub 0x%08lX unreadable after recreate - not tiling", nsub);
        } else if ((svt = *(DWORD **)nsub) == NULL || IsBadReadPtr(svt, 0x14) ||
                   (DWORD)svt != want) {
            logf("SIDEFIT> REFUSE lock: sub vtable 0x%08lX != GZGraphicD+0x%X - not the class we think",
                 (DWORD)svt, GZ_RVA_VT_SURFACE);
        } else {
            int lk = rz_thiscall((void *)nsub, (void *)svt[0x0c / 4], NULL, 0);
            DWORD nbits = ((DWORD *)nsub)[0xf0 / 4], npitch = ((DWORD *)nsub)[0xf4 / 4];
            logf("SIDEFIT> lock -> %d | bits=0x%08lX pitch=%lu new %lux%lu",
                 lk & 0xff, nbits, npitch, nw, nh);
            if (!(lk & 0xff) || !nbits || !npitch || IsBadReadPtr((void *)nbits, npitch * nh)) {
                logf("SIDEFIT> lock did not yield a usable backing - not tiling");
            } else {
                /* ⛔ DO NOT TILE THIS ART. Owner, 2026-09-02: "you have repeated the same texture
                   with the 5 buttons over and over." The 96x417 surface is not a filler strip - it
                   is the whole PAGE, button frames included - which is also why the panel's tiled
                   slot `+0xcc` is NULL: this panel was never meant to be tiled.
                   So: place the art ONCE, aligned with where rz_side_children_bottom is about to
                   put the pages, and fill the space above with a single PLAIN row taken from below
                   the last button (the buttons occupy art rows ~21..381 of 417). */
                DWORD r, run = (nw < oldw) ? nw : oldw;
                /* Anchor the art to the page's TOP - the same row the child windows get.
                 *
                 * The art's button frames sit at art rows 21.. and the real button windows at
                 * page-local 21.., so top-anchoring is what makes them coincide. I briefly
                 * bottom-anchored this (art bottom == page bottom) because the art is 417 tall
                 * against a 442-tall page; that put every frame 25 px low, which the owner then
                 * measured as a uniform offset once the real defect was fixed.
                 *
                 * The real defect was SCALING, not the anchor: the dest rect was 33 rows shorter
                 * than the surface, so the blit compressed everything and the error grew down the
                 * strip ("misaligned in one way at the top, differently at the bottom"). With the
                 * dest matched 1:1 below, top-anchoring is correct and the 25-row remainder is
                 * simply plain filler behind the cap. */
                /* Derive the row from the PANEL's height, not from `liveH` - liveH is now the
                   surface REQUEST (cap top minus slack), so using it would offset the art from the
                   child windows by exactly that slack. The children move by
                   panelH - SIDE_NAT_H - g_side_dy, and surface row r maps to panel y r, so the art
                   must use the same expression. */
                /* Use the panel's LOCAL height (+0x80..+0x8c), the SAME field rz_side_children_bottom
                 * reads to place the button windows. Reading the derived +0x14 ABS rect here (which
                 * this mod leaves at its stale native 442 while the local rect is the extended height)
                 * put the icon art at a different offset than the button windows - so the hover
                 * highlight sat a button off from the icon (owner: "the alignment is still off"). */
                /* ⭐ The height the panel is ABOUT TO HAVE, not the one it has now (2026-10-09). The fit
                 * runs before rz_side_fit_surface's re-SetRect, and while the art is still the old,
                 * taller size SetRect clamps the panel UP, so the local rect still reads the old
                 * height here: placed at 1081 - 442 = 639 while the panel then settled at 923 above
                 * the minimap and the buttons went to 923 - 442 = 481, so every icon sat 158 px
                 * below its button (owner screenshot). This used to self-heal only because the
                 * leaking refit re-ran every poll; with the leak fixed it has to be right first time. */
                LONG panelH_ = g_side_intended_h > 0 ? g_side_intended_h
                             : (g_side_top && !IsBadReadPtr(g_side_top, 0x90))
                             ? (LONG)((DWORD *)g_side_top)[0x8c / 4] -
                               (LONG)((DWORD *)g_side_top)[0x84 / 4]
                             : (LONG)liveH;
                LONG art_at = panelH_ - SIDE_NAT_H - g_side_dy;
                DWORD plain = g_side_plainrow[slot] < oldh ? g_side_plainrow[slot]
                            : ((oldh > 8) ? oldh - 4 : oldh - 1);
                if (art_at < 0) art_at = 0;
                for (r = 0; r < nh; r++) {
                    LONG src = (LONG)r - art_at;
                    BYTE *from = (src >= 0 && src < (LONG)oldh)
                               ? snap + (DWORD)src * oldpitch      /* the real art, once */
                               : snap + plain * oldpitch;          /* plain background elsewhere */
                    memcpy((BYTE *)nbits + r * npitch, from, run * 2);
                }
                logf("SIDEFIT> placed the %lux%lu art ONCE at row %ld of %lu and filled the rest "
                     "from plain art row %lu (no tiling)", oldw, oldh, art_at, nh, plain);
            }
            if (lk & 0xff) rz_thiscall((void *)nsub, (void *)svt[0x10 / 4], NULL, 0);
        }
    }
}

/* Patch the panel bottom-cap's transparency COLOR-KEY (RGB565 magenta 0xF81F, the rounded-corner
 * outside pixels) to the panel blue. Native rendering hides these behind the minimap; the extended
 * panel exposes them and the paint blits them as solid magenta (owner: the magenta line at the panel
 * bottom). The cap is never recreated, so patch its surface once. */
static int g_cap_patched;
static void rz_side_patch_cap(void) {
    DWORD *p = (DWORD *)g_side_top;
    HMODULE gz = GetModuleHandleA("GZGraphicD.dll");
    DWORD cap, sub, bits, pitch, w, h;
    DWORD *svt, want;
    int lk;
    if (g_cap_patched || !p || IsBadReadPtr(p, 0x120) || !gz) return;
    cap = p[0xc8 / 4];
    if (!cap || IsBadReadPtr((void *)cap, 0x48)) return;
    w = ((DWORD *)cap)[0x24 / 4]; h = ((DWORD *)cap)[0x28 / 4];
    sub = ((DWORD *)cap)[0x44 / 4];
    if (!sub || IsBadReadPtr((void *)sub, 0xf8)) return;
    svt = *(DWORD **)sub; want = (DWORD)gz + GZ_RVA_VT_SURFACE;
    if (!svt || IsBadReadPtr(svt, 0x14) || (DWORD)svt != want) return;
    lk = rz_thiscall((void *)sub, (void *)svt[0x0c / 4], NULL, 0);
    bits = ((DWORD *)sub)[0xf0 / 4]; pitch = ((DWORD *)sub)[0xf4 / 4];
    if ((lk & 0xff) && bits && pitch && w && h && !IsBadWritePtr((void *)bits, pitch * h)) {
        DWORD r, x, patched = 0;
        for (r = 0; r < h; r++) {
            WORD *row = (WORD *)(bits + r * pitch);
            for (x = 0; x < w; x++)
                if (row[x] == 0xF81F) { row[x] = 0x9D3F; patched++; }   /* magenta key -> panel blue */
        }
        g_cap_patched = 1;
        logf("SIDEFIT> cap: patched %lu magenta color-key px -> panel blue (once)", patched);
    }
    if (lk & 0xff) rz_thiscall((void *)sub, (void *)svt[0x10 / 4], NULL, 0);
}

static void rz_side_fit_surface(DWORD clientH) {
    DWORD *p = (DWORD *)g_side_top;
    DWORD capH = 0, target, want, liveH;
    if (!p || IsBadReadPtr(p, 0x120)) { logf("SIDEFIT> skipped: no side panel"); return; }

    /* ⭐⭐ THE PANEL SIZES ITSELF TO THE SUM OF ITS ART. This is the whole story.
     *
     * `FUN_1004e20b` (the panel's own vt+0xc8 SetRect) does:
     *     minH = c0->height + c4->height + c8->height     // ART SURFACE heights, vt+0x3c
     *     h    = max(requested, minH)                     // clamp UP only
     *     w    = c0->width                                // width is not ours to set
     *   `[CONFIRMED @ SIMUI 0x1004e20b]`, and 417 + 25 == 442 == the native panel height exactly.
     *
     * So refitting BOTH surfaces to the full height made minH the SUM of two full heights and the
     * panel duly resized itself to 2x: measured 1056 + 1056 -> 2112, and 1089 + 1089 -> 2178, in
     * its LOCAL rect (+0x80), not merely the derived +0x14 one. The engine was doing exactly what
     * it is written to do; the bug was mine.
     *
     * Therefore: grow ONLY the background (+0xc0), to `clientH - capHeight`, and leave the bottom
     * cap (+0xc8) at its native 25 rows. minH then lands on exactly the height we want and the
     * panel is stable.
     *
     * Also do NOT write the child dest rects (+0xd0 / +0xf0): SetRect recomputes them from each
     * surface's own pixel size and then translates them, so a hand-written value is overwritten on
     * the next pass and its only other consumer (+0x104, the tile span) is dead while +0xcc is
     * NULL. `[CONFIRMED @ SIMUI 0x1004e20b, 0x1004e63e]` */
    if (p[0xc8 / 4] && !IsBadReadPtr((void *)p[0xc8 / 4], 0x2c))
        capH = ((DWORD *)p[0xc8 / 4])[0x28 / 4];
    if (capH == 0 || capH > clientH) capH = SIDE_CAP_H;
    target = clientH - capH;   /* the background gets everything above the cap */
    liveH = target;            /* what the re-SetRect below asks for, plus capH */
    want = (target > RZ_SURFACE_SLACK) ? target - RZ_SURFACE_SLACK : target;
    if (!g_reassert_quiet)
    logf("SIDEFIT> background target %lu (client %lu - cap %lu) -> requesting %lu + %d slack; "
         "cap left at native so minH = %lu + %lu = %lu",
         target, clientH, capH, want, RZ_SURFACE_SLACK, target, capH, target + capH);
    g_side_intended_h = (LONG)(target + capH);
    rz_side_fit_child(0, 0xc0, want);
    g_side_intended_h = 0;
    rz_side_patch_cap();   /* kill the magenta color-key line at the exposed panel bottom */

    /* Re-run the panel's own SetRect so it recomputes the child dest rects from the new art size,
       then mark it dirty the way the framework does (vt+0x154 = dirty + propagate to ancestors,
       `[CONFIRMED @ SIMUI 0x1006e06b, 0x1006c784]`) rather than hoping a layout pass notices. */
    {   DWORD *vt = *(DWORD **)p;
        LONG *loc = (LONG *)((DWORD)p + 0x80);
        if (vt && !IsBadReadPtr(vt, 0x158) && vt[0xc8 / 4]) {
            DWORD a[4];
            /* ⭐ RE-SETRECT WITH THE DESIRED HEIGHT, NOT THE CURRENT ONE. This is what let the panel
             * grow but never SHRINK.
             *
             * FUN_1004e20b clamps the panel height UP to the sum of its art heights, so on a shrink
             * the first SetRect is legitimately refused: requested 861, returned 1081, because the
             * art was still 1056 tall. The art is refit just above, so by here the clamp would allow
             * the smaller height - but replaying `loc` re-applies the REFUSED value and the panel
             * stays tall forever. Measured 2026-09-02 at 1384x861: bar, minimap and RCI all tracked
             * the client; only the panel stayed 1081.
             * Ask for `top + liveH + capH` - the art we just installed plus the cap - which is
             * exactly what minH will now be. */
            LONG wantBottom = loc[1] + (LONG)liveH + (LONG)capH;
            a[0] = (DWORD)loc[0]; a[1] = (DWORD)loc[1];
            a[2] = (DWORD)loc[2]; a[3] = (DWORD)wantBottom;
            rz_thiscall(p, (void *)vt[0xc8 / 4], a, 4);
            if (!g_reassert_quiet)
            logf("SIDEFIT> re-SetRect [%ld %ld %ld %ld] -> local now [%ld %ld %ld %ld]",
                 (LONG)a[0], (LONG)a[1], (LONG)a[2], (LONG)a[3],
                 loc[0], loc[1], loc[2], loc[3]);
            if (vt[0x154 / 4]) rz_thiscall(p, (void *)vt[0x154 / 4], NULL, 0);
        }
    }


    /* ⭐ AND THE DESTINATION RECT — the half that makes the taller surface visible at all.
     *
     * `FUN_1004e63e` blits each child surface into its OWN dest rect stored in the panel:
     * `+0xc0 -> +0xd0`, `+0xc4 -> +0xe0`, `+0xc8 -> +0xf0`, `+0x114 -> +0x118`, and the tiled
     * `+0xcc` walks `+0x100..+0x10c` `[CONFIRMED @ SIMUI 0x1004e63e]`.
     *
     * Measured live 2026-09-02 on the extended panel: `+0xd0` was still the native
     * `[0 0 96 417]` while `+0xf0` (the 25-px bottom cap) had moved itself to `[0 1056 96 1081]`.
     * So the panel painted y 0..417 and y 1056..1081 and NOTHING BETWEEN - the owner's "black
     * section on the vertical bar", exactly, and the reason three earlier attempts at filling the
     * SURFACE could not have worked no matter how it was filled. Stretching this one rect to the
     * bottom cap is what made the fill appear.
     *
     * Bottom edge comes from the cap's own top when it looks sane, so the cap is never overdrawn. */
    if (p && !IsBadWritePtr(p, 0x120)) {
        LONG *d0 = (LONG *)((DWORD)p + 0xd0);
        LONG *f0 = (LONG *)((DWORD)p + 0xf0);
        LONG panelH = (LONG)p[0x20 / 4] - (LONG)p[0x18 / 4];
        LONG bottom = (f0[1] > 0 && f0[1] <= panelH) ? f0[1] : panelH;
        /* ⚠️ MATCH THE DEST HEIGHT TO THE SURFACE, or the blit SCALES.
         *
         * `rz_recreate_raster` pads every surface by RZ_SURFACE_SLACK guard rows, so a surface
         * requested at 1081 is really 1089 tall. Blitting that into a 1056-tall dest compresses it
         * by ~3.1%: no drift at the top, ~33 px by the bottom. Owner, 2026-09-02, on two
         * screenshots: "the one at the top is misaligned in one way, the one at the bottom is
         * misaligned differently" - which is scaling, not an offset, and is why moving the art
         * could not fix it. Extend the dest to the surface's REAL height so the mapping is 1:1.
         * The extra rows land under the bottom cap, which paints after this one and covers them. */
        {   DWORD bg = p[0xc0 / 4];
            if (bg && !IsBadReadPtr((void *)bg, 0x2c)) {
                LONG surfH = (LONG)((DWORD *)bg)[0x28 / 4];
                if (surfH > bottom) {
                    logf("SIDEFIT> dest bottom %ld -> %ld to match the %ld-row surface 1:1 "
                         "(no scaling; the cap repaints the overlap)", bottom, surfH, surfH);
                    bottom = surfH;
                }
            }
        }
        if (d0[2] - d0[0] > 0 && d0[3] - d0[1] > 0 && d0[3] < bottom) {
            logf("SIDEFIT> dest rect +0xd0 [%ld %ld %ld %ld] -> [%ld %ld %ld %ld]  (cap top %ld, "
                 "panel %ld) - the black band between 0x%lx and the cap was UNPAINTED",
                 d0[0], d0[1], d0[2], d0[3], d0[0], d0[1], d0[2], bottom, f0[1], panelH,
                 (DWORD)d0[3]);
            d0[3] = bottom;
        } else {
            if (!g_reassert_quiet) logf("SIDEFIT> dest rect +0xd0 [%ld %ld %ld %ld] left as-is (cap top %ld, panel %ld)",
                 d0[0], d0[1], d0[2], d0[3], f0[1], panelH);
        }
    }
}


/* Dock the SIDE PANEL to the right edge and extend it to full height, via its own framework
 * SetRect (`vt+0xc8`) - the identical method already proven on the bottom bar.
 *
 * Native rect measured in run 21: [704, 0, 800, 442] = 96 wide, 442 tall, at the right edge of the
 * native 800-wide screen. Docked target: [liveW - 96, 0, liveW, liveH].
 *
 * PREDICTION under test: unlike the bar, this should cost nothing per frame. The panel's tiled child
 * `+0xcc` is NULL, so `FUN_1004e63e`'s tile loop is skipped entirely and extending the panel cannot
 * multiply blits the way widening the bar does.
 *
 * `[UNCERTAIN]` on appearance: the two real children are 96x417 and 96x25 and will NOT stretch, so a
 * taller panel very likely shows a blank region below them. That is expected and is not the thing
 * being measured here - this run is about frame cost, not looks. */
static void rz_side_extend(void) {
    DWORD *s = (DWORD *)g_side_top;
    RECT cr;
    LONG x1, y1, x2, y2;
    int panelW;
    DWORD *svt;
    if (!s || IsBadReadPtr(s, 0x120)) { logf("SIDE> extend skipped: panel not captured"); return; }
    x1 = (LONG)s[0x14/4]; y1 = (LONG)s[0x18/4]; x2 = (LONG)s[0x1c/4]; y2 = (LONG)s[0x20/4];
    panelW = (int)(x2 - x1);
    svt = *(DWORD **)s;
    if (!g_hwnd || !GetClientRect(g_hwnd, &cr) || !svt || IsBadReadPtr(svt, 0xcc)) {
        logf("SIDE> extend skipped: no window or vtable unreadable"); return;
    }
    {
        int lw = (int)(cr.right - cr.left), lh = (int)(cr.bottom - cr.top);
        void *setrect = (void *)svt[0xc8/4];
        int wantX1 = lw - panelW, wantY2 = lh;
        /* Stop the panel at the MINIMAP's top, not the client bottom. The minimap docks in the
         * bottom-right corner and is wider than the panel; extending the panel over it hid the lower
         * button cluster BEHIND the minimap (owner: "side bar buttons are wrong"). The minimap docks
         * before this runs (rz_mini_dock precedes rz_cluster_layout), so its top is current. */
        {   LONG th = rz_side_target_h();
            if (th > 0 && th < lh) wantY2 = (int)th;
        }
        if (!setrect || panelW <= 0 || panelW >= lw) {
            logf("SIDE> extend skipped: setrect=0x%08lX panelW=%d lw=%d",
                 (DWORD)setrect, panelW, lw);
            return;
        }
        if (x1 == wantX1 && y1 == 0 && x2 == lw && y2 == wantY2) {
            if (!g_reassert_quiet) logf("SIDE> already docked at [%d,0,%d,%d]", wantX1, lw, wantY2);
            return;
        }
        {
            DWORD a[4];
            a[0] = (DWORD)wantX1; a[1] = 0; a[2] = (DWORD)lw; a[3] = (DWORD)wantY2;
            logf("SIDE> SetRect vt+0xc8=0x%08lX  [%ld,%ld,%ld,%ld] -> [%d,0,%d,%d]",
                 (DWORD)setrect, x1, y1, x2, y2, wantX1, lw, wantY2);
            rz_thiscall(g_side_top, setrect, a, 4);
            logf("SIDE> SetRect returned; rect now [%ld,%ld,%ld,%ld] (tiled child +0xcc=0x%08lX)",
                 (LONG)s[0x14/4], (LONG)s[0x18/4], (LONG)s[0x1c/4], (LONG)s[0x20/4], s[0xcc/4]);
        }
    }
}

/* The per-frame poll. Compares the live client size against the render target's size and only
 * acts on a genuine mismatch - so a stray frame cannot churn the render target. */

/* ============================ ON-DEMAND SURFACE DUMPER ============================
 *
 * Why this exists: this session burned hours diagnosing HUD paint defects blind. External screen
 * capture CANNOT see the HUD layer (measured: five GDI captures read as "the HUD is not on screen"
 * while the owner was looking straight at it), so every visual question had to go through a human
 * describing pixels. Four consecutive wrong models came out of that loop.
 *
 * The engine's composited frame is reachable in-process: `iso+0x4ec` is the blit destination the
 * DirectDraw present reads, and it contains the HUD. `iso+0x74` is the iso render target (city
 * only). Both are raster objects with the same shape:
 *     obj+0x24 width, obj+0x28 height, obj+0x44 -> sub, sub+0xf0 bits, sub+0xf4 pitch
 * Pixels are read RAW from sub+0xf0/+0xf4 and NEVER through the out-of-band lock: calling `vf1c`
 * here tore the backing down and destroyed the thing being measured (2026-08-25).
 *
 * Trigger: drop any file named DUMP next to the log (or set SC3RESIZE_DUMPDIR). The poll notices
 * it, deletes it, and writes the BMPs - so the owner can put the game in the exact state that
 * misbehaves (a submenu open, a tool clicked) and the capture is of THAT frame.
 * 16bpp RGB565 in, 24bpp BMP out, top-down via a negative height. */
static int rz_bmp_write(const char *path, const BYTE *bits, LONG w, LONG h, LONG pitch) {
    HANDLE f;
    DWORD wrote, rowbytes = (DWORD)(w * 3), pad = (4 - (rowbytes & 3)) & 3;
    BYTE hdr[54];
    BYTE *row;
    LONG y, x;
    DWORD fsz = 54 + (rowbytes + pad) * (DWORD)h;
    if (!bits || w <= 0 || h <= 0 || pitch <= 0) return 0;
    f = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (f == INVALID_HANDLE_VALUE) return 0;
    memset(hdr, 0, sizeof(hdr));
    hdr[0] = 'B'; hdr[1] = 'M';
    *(DWORD *)(hdr + 2) = fsz;
    *(DWORD *)(hdr + 10) = 54;
    *(DWORD *)(hdr + 14) = 40;
    *(LONG  *)(hdr + 18) = w;
    *(LONG  *)(hdr + 22) = -h;            /* negative = top-down rows */
    *(WORD  *)(hdr + 26) = 1;
    *(WORD  *)(hdr + 28) = 24;
    *(DWORD *)(hdr + 34) = (rowbytes + pad) * (DWORD)h;
    WriteFile(f, hdr, 54, &wrote, NULL);
    row = (BYTE *)HeapAlloc(GetProcessHeap(), 0, rowbytes + 4);
    if (!row) { CloseHandle(f); return 0; }
    for (y = 0; y < h; y++) {
        const WORD *src = (const WORD *)(bits + (DWORD)y * (DWORD)pitch);
        if (IsBadReadPtr(src, (UINT)(w * 2))) break;
        for (x = 0; x < w; x++) {
            WORD v = src[x];                       /* RGB565 */
            row[x * 3 + 0] = (BYTE)(( v        & 0x1f) << 3);   /* B */
            row[x * 3 + 1] = (BYTE)(((v >> 5)  & 0x3f) << 2);   /* G */
            row[x * 3 + 2] = (BYTE)(((v >> 11) & 0x1f) << 3);   /* R */
        }
        memset(row + rowbytes, 0, pad);
        WriteFile(f, row, rowbytes + pad, &wrote, NULL);
    }
    HeapFree(GetProcessHeap(), 0, row);
    CloseHandle(f);
    return 1;
}

static void rz_dump_raster(void *obj, const char *tag, int seq) {
    char path[MAX_PATH];
    DWORD sub, bits, pitch, w, h;
    int locked = 0;
    if (!obj || IsBadReadPtr(obj, 0x48)) { logf("DUMP> %s: unreadable object", tag); return; }
    w = ((DWORD *)obj)[0x24 / 4]; h = ((DWORD *)obj)[0x28 / 4];
    sub = ((DWORD *)obj)[0x44 / 4];
    if (!sub || IsBadReadPtr((void *)sub, 0xf8)) { logf("DUMP> %s: no sub-object", tag); return; }
    bits = ((DWORD *)sub)[0xf0 / 4]; pitch = ((DWORD *)sub)[0xf4 / 4];
    /* A VIDEO-memory surface (the composite is recreated as one after a resize) has no persistent CPU
     * mapping - bits/pitch are 0 until it is LOCKED. Take a BALANCED lock (add and remove our own
     * refcount level, the exact primitive rz_hud_fit_child uses) to map it for the read, so the HUD
     * composite can be captured post-resize instead of coming back "nothing mapped". Expect-or-refuse
     * on the sub vtable before dispatching through it. */
    if ((!bits || !pitch)) {
        HMODULE gz = GetModuleHandleA("GZGraphicD.dll");
        DWORD *svt = *(DWORD **)sub, wantvt = gz ? (DWORD)gz + GZ_RVA_VT_SURFACE : 0;
        if (gz && svt && !IsBadReadPtr(svt, 0x14) && (DWORD)svt == wantvt && svt[0x0c / 4]) {
            int lk = rz_thiscall((void *)sub, (void *)svt[0x0c / 4], NULL, 0);
            if (lk & 0xff) {
                locked = 1;
                bits = ((DWORD *)sub)[0xf0 / 4]; pitch = ((DWORD *)sub)[0xf4 / 4];
                logf("DUMP> %s: locked video surface -> bits=0x%08lX pitch=%lu", tag, bits, pitch);
            }
        }
    }
    if (!bits || !pitch) {
        logf("DUMP> %s: %lux%lu but bits=0x%08lX pitch=%lu - nothing mapped", tag, w, h, bits, pitch);
        if (locked) { DWORD *svt = *(DWORD **)sub; if (svt && svt[0x10/4]) rz_thiscall((void *)sub, (void *)svt[0x10/4], NULL, 0); }
        return;
    }
    _snprintf(path, sizeof(path), "%s\\dump%02d_%s_%lux%lu.bmp", g_dumpdir, seq, tag, w, h);
    if (!IsBadReadPtr((void *)bits, pitch * h) && rz_bmp_write(path, (const BYTE *)bits, (LONG)w, (LONG)h, (LONG)pitch))
        logf("DUMP> %s -> %s (%lux%lu pitch %lu)", tag, path, w, h, pitch);
    else
        logf("DUMP> %s: BMP write FAILED (%lux%lu pitch %lu)", tag, w, h, pitch);
    if (locked) { DWORD *svt = *(DWORD **)sub; if (svt && svt[0x10/4]) rz_thiscall((void *)sub, (void *)svt[0x10/4], NULL, 0); }
}

/* Find a window by its vftable, anywhere in the tree from the event sink's root. */
static void *rz_find_by_vt(void *w, DWORD wantvt, int depth, int *budget) {
    void *head, *n;
    int guard = 0;
    if (!w || depth > 8 || *budget <= 0 || IsBadReadPtr(w, 0x40)) return NULL;
    head = *(void **)((DWORD)w + 0x34);
    if (!head || IsBadReadPtr(head, 4)) return NULL;
    n = *(void **)head;
    while (n && n != head && guard++ < 400 && *budget > 0) {
        void *cw;
        if (IsBadReadPtr(n, 0x0c)) break;
        cw = *(void **)((DWORD)n + 8);
        (*budget)--;
        if (cw && !IsBadReadPtr(cw, 4)) {
            if (*(DWORD *)cw == wantvt) return cw;
            {   void *hit = rz_find_by_vt(cw, wantvt, depth + 1, budget);
                if (hit) return hit;   }
        }
        n = *(void **)n;
    }
    return NULL;
}

static void rz_dump_all(void *iso) {
    static int seq;
    DWORD gz = (DWORD)GetModuleHandleA("GZGraphicD.dll");
    DWORD sui = (DWORD)GetModuleHandleA("SIMUI.DLL");
    seq++;
    logf("DUMP> ---- capture %02d ----", seq);
    if (iso && !IsBadReadPtr(iso, 0x4f0)) {
        rz_dump_raster((void *)((DWORD *)iso)[0x4ec / 4], "frame_with_hud", seq);
        rz_dump_raster((void *)((DWORD *)iso)[0x74 / 4],  "iso_target", seq);
    }
    if (gz && sui && !IsBadReadPtr((void *)(gz + 0x6cdb8), 4)) {
        DWORD *win = *(DWORD **)(gz + 0x6cdb8);
        DWORD *sink = (win && !IsBadReadPtr(win, 0x34)) ? (DWORD *)win[0x30 / 4] : NULL;
        void *root = (sink && !IsBadReadPtr(sink, 0x3c)) ? (void *)sink[0x38 / 4] : NULL;
        if (root) {
            int budget = 3000;
            void *panel = rz_find_by_vt(root, sui + 0xa9834, 0, &budget);
            if (panel && !IsBadReadPtr(panel, 0xd0)) {
                rz_dump_raster((void *)((DWORD *)panel)[0x58 / 4], "panel_composite", seq);
                rz_dump_raster((void *)((DWORD *)panel)[0xc0 / 4], "panel_bg_art", seq);
            } else {
                logf("DUMP> side panel not found");
            }
            budget = 3000;
            {   void *bar = g_hud_top;
                if (bar && !IsBadReadPtr(bar, 0xd0))
                    rz_dump_raster((void *)((DWORD *)bar)[0x58 / 4], "bar_composite", seq);
            }
        }
    }
    logf("DUMP> ---- capture %02d done ----", seq);
}


/* CLOSE OPEN FLYOUTS ON A RESIZE (owner 2026-10-08: "if a menu of the vertical bar is open when resizing you
   have to close it after resize"). Hide it with GZWIND vt+0xf4 SetFlags(1 = visible, 0), the same call sc3bigcity
   uses, then invalidate the panel (vt+0x154) so it repaints. SC3RESIZE_CLOSEFLY=0 disables. */
static int g_closefly = 1;
/* Returns 1 and the abs rect of the first open flyout (a visible a9a80 child of the side panel narrower than a page). */
static int rz_open_flyout(LONG *out) {
    DWORD sui = (DWORD)GetModuleHandleA("SIMUI.DLL");
    void *p = g_side_top, *head, *n;
    int g = 0;
    if (!sui || !p || IsBadReadPtr((BYTE *)p + 0x34, 4)) return 0;
    head = *(void **)((DWORD)p + 0x34);
    if (!head || IsBadReadPtr(head, 4)) return 0;
    for (n = *(void **)head; n && n != head && g++ < 300; n = *(void **)n) {
        DWORD *c;
        LONG *r;
        if (IsBadReadPtr(n, 0x0c)) break;
        c = *(DWORD **)((DWORD)n + 8);
        if (!c || IsBadReadPtr(c, 0xa4) || c[0] != sui + 0xa9a80 || !(c[0xa0 / 4] & 1)) continue;
        r = (LONG *)((DWORD)c + 0x80);
        if (r[2] - r[0] >= 96) continue;
        if (out) memcpy(out, (BYTE *)c + 0x14, 16);
        return 1;
    }
    return 0;
}

/* The last left click on a side-panel CATEGORY button (inside the panel, outside any open flyout), in client
   coordinates. The game toggles a flyout only through that button (Escape does not close it, measured), and hiding
   the flyout from outside left the game thinking it was open, so reopening took two clicks (measured). */
static LPARAM g_fly_lp;
static int    g_fly_have;
static void rz_note_panel_click(LPARAM lp) {
    LONG x = (short)LOWORD(lp), y = (short)HIWORD(lp), f[4];
    LONG *pr;
    if (!g_side_top || IsBadReadPtr((BYTE *)g_side_top + 0x14, 16)) return;
    pr = (LONG *)((BYTE *)g_side_top + 0x14);
    if (x < pr[0] || x >= pr[2] || y < pr[1] || y >= pr[3]) return;
    if (rz_open_flyout(f) && x >= f[0] && x < f[2] && y >= f[1] && y < f[3]) return;   /* a click inside the flyout */
    g_fly_lp = lp; g_fly_have = 1;
}

/* Called from the poll on a size change, before any layout moves the button: replay the click on the
   button that opened the flyout, so the game closes it through its own toggle and its state stays consistent. */
static void rz_close_flyout_by_click(HWND h) {
    if (!g_closefly || !rz_open_flyout(NULL)) return;
    if (!g_fly_have) { logf("CLOSEFLY> a flyout is open but no category click was recorded - falling back to hiding it"); return; }
    CallWindowProcA(g_oldproc, h, WM_LBUTTONDOWN, MK_LBUTTON, g_fly_lp);
    CallWindowProcA(g_oldproc, h, WM_LBUTTONUP, 0, g_fly_lp);
    logf("CLOSEFLY> replayed the category click at (%d,%d) to close the open flyout before the resize",
         (int)(short)LOWORD(g_fly_lp), (int)(short)HIWORD(g_fly_lp));
}

static void rz_close_flyouts(void) {
    /* Measured with a flyout open (Europolis, landscape button): the flyout is a 36-px column of class
       SIMUI+0xa9a80 inside the side panel ([704 0 740 442], visible); the panel's pages are the same class but
       96 wide and hidden. Hide visible a9a80 children of the panel narrower than a page. */
    DWORD sui = (DWORD)GetModuleHandleA("SIMUI.DLL");
    void *p = g_side_top, *head, *n;
    int g = 0, closed = 0;
    if (!g_closefly || !sui || !p || IsBadReadPtr((BYTE *)p + 0x34, 4)) return;
    head = *(void **)((DWORD)p + 0x34);
    if (!head || IsBadReadPtr(head, 4)) return;
    for (n = *(void **)head; n && n != head && g++ < 300; n = *(void **)n) {
        DWORD *c, *vt;
        LONG *r;
        if (IsBadReadPtr(n, 0x0c)) break;
        c = *(DWORD **)((DWORD)n + 8);
        if (!c || IsBadReadPtr(c, 0xa4) || c[0] != sui + 0xa9a80 || !(c[0xa0 / 4] & 1)) continue;
        r = (LONG *)((DWORD)c + 0x80);
        if (r[2] - r[0] >= 96) continue;                 /* a full page, not a flyout */
        vt = (DWORD *)c[0];
        if (vt && !IsBadReadPtr(vt, 0xf8) && vt[0xf4 / 4]) {
            DWORD a[2]; a[0] = 1; a[1] = 0;
            rz_thiscall(c, (void *)vt[0xf4 / 4], a, 2);
            closed++;
        }
    }
    if (closed) {
        DWORD *pvt = *(DWORD **)p;
        if (pvt && !IsBadReadPtr(pvt, 0x158) && pvt[0x154 / 4]) rz_thiscall(p, (void *)pvt[0x154 / 4], NULL, 0);
        logf("CLOSEFLY> closed %d open side-panel flyout(s) after a resize", closed);
    }
}

static void rz_poll(void) {
    void *iso;
    DWORD *v, R, w, ht;
    RECT cr;
    BYTE *lk;
    LARGE_INTEGER tp0, tp1, tp2;   /* SKIPREFRESH timing: sim-lock wait and the pass */
    LONG cz_f = 1, cz_cw = 0, cz_ch = 0, cz_px = 0, cz_py = 0, cz_tx = 0, cz_ty = 0;   /* task cityzoom */
    int cz_move = 0;

    if (!g_bridge || IsBadReadPtr(g_bridge, 0xf4)) return;
    iso = (void *)((DWORD *)g_bridge)[0x18 / 4];
    if (!iso || IsBadReadPtr(iso, 0x4f0)) return;
    if (!g_hwnd || !IsWindow(g_hwnd) || !GetClientRect(g_hwnd, &cr)) return;

    w  = (DWORD)(cr.right - cr.left);
    ht = (DWORD)(cr.bottom - cr.top);
    if (w == 0 || ht == 0) return;

    /* HUD REBUILT -> LAY OUT AGAIN (owner 2026-10-07). New City builds a terrain-mode HUD, then on
       "accept terrain" the game builds the city HUD (new bottom bar / side panel objects). With the
       window already maximized there is no size change, so nothing laid the new objects out: minimap
       mid-screen, side buttons twice, bar contents at the left. A de-maximize/maximize fixed it because
       the size change runs the full routine. Treat a new bar or panel object like a new city view:
       wait the readiness gate, then run the routine once. */
    {   static void *s_hud, *s_side;
        if ((g_hud_top && g_hud_top != s_hud) || (g_side_top && g_side_top != s_side)) {
            if (s_hud || s_side) {
                g_bridge_fresh = 1; g_bridge_ms = GetTickCount(); g_defer_logged = 0;
                logf("RZ   HUD rebuilt (bar 0x%08lX side 0x%08lX) - layout will run again once ready",
                     (DWORD)g_hud_top, (DWORD)g_side_top);
            }
            s_hud = g_hud_top; s_side = g_side_top;
        }
    }
    /* ...and when the city HUD becomes VISIBLE. Measured: "accept terrain" reuses the same bar and panel
       objects (no rebuild logged) but shows them after the terrain editor, where the first pass ran
       with them hidden - the result was the same broken HUD. Side panel +0xa0 bit 0 going 0 -> 1. */
    {   static int s_vis = -1;
        int vis = (g_side_top && !IsBadReadPtr(g_side_top, 0xa4)) ? (int)(*(DWORD *)((DWORD)g_side_top + 0xa0) & 1) : -1;
        if (vis == 1 && s_vis == 0) {
            g_bridge_fresh = 1; g_bridge_ms = GetTickCount(); g_defer_logged = 0;
            logf("RZ   city HUD became visible - layout will run again once ready");
        }
        s_vis = vis;
    }

    /* No edge scrolling in windowed mode (owner, 2026-10-05) - see rz_edge_off. 250 ms cadence. */
    if (!g_edgescroll) {
        static DWORD rz_edge_next_ms;
        DWORD nowe = GetTickCount();
        if (nowe >= rz_edge_next_ms) { rz_edge_next_ms = nowe + 250; rz_edge_off(); }
    }
    /* Dialogs follow the window - see rz_dialogs_poll. 100 ms. */
    if (g_dialogs) {
        static DWORD rz_dlg_next_ms;
        DWORD nowd = GetTickCount();
        if (nowd >= rz_dlg_next_ms) { rz_dlg_next_ms = nowd + 100; rz_dialogs_poll((LONG)w, (LONG)ht); }
    }
    /* Map input past 800x600 - see rz_view_rect_assert. Same 250 ms cadence. */
    if (g_viewfix) {
        static DWORD rz_view_next_ms;
        DWORD nowv = GetTickCount();
        if (nowv >= rz_view_next_ms) { rz_view_next_ms = nowv + 250; rz_view_rect_assert((LONG)w, (LONG)ht); }
    }

    /* Late-created side-panel windows. A tool submenu opened after the resize renders at its
       native position (owner, 2026-09-02: "when i open a menu it is rendered at the top"), because
       the layout pass ran before that window existed. rz_side_children_bottom is idempotent - it
       skips anything already placed - so re-running it costs nothing in the steady state and
       catches whatever the game has just built. Rate-limited, and placed BEFORE the settled check
       below, which returns early on every frame once the size stops changing. */
    if (g_sideon && !g_cluster) {
        static DWORD rz_side_next_ms;
        DWORD now = GetTickCount();
        /* 80 ms, not 400. The pass corrects popups the game creates at a stale anchor, and at
           400 ms the owner could SEE the correction happen: "toast labels appear briefly at the
           top and then they move to the bottom" (2026-09-02). Tightening the interval makes the
           correction land within a frame or two instead of a fifth of a second.
           ⚠️ Be clear about what this is: it HIDES the latency of a correction, it does not fix
           the anchor those popups are positioned from. The real fix is to find that anchor - the
           tool flyout's own positioner (FUN_1004ec95) reads the owning item's absolute rect and is
           already correct, so whatever creates these labels uses something else. Cost is bounded:
           the walk only touches the root's direct children and issues SetRect only on a match, of
           which there are none in the idle state (measured: 0 matches over 6 s idle). */
        /* DISABLED for the cascade A/B, per CASCADE_PRE.md: if the refactor is the real fix,
           popups land correctly with no timer at all, and leaving the timer on would make the two
           indistinguishable. SC3RESIZE_SIDEPOLL=1 turns it back on. */
        if (g_side_poll && now >= rz_side_next_ms) {
            rz_side_next_ms = now + 80;
            rz_side_children_bottom();
            if (!g_cluster) rz_bar_children_right();
        }
    }

    /* CLUSTER RE-ANCHOR. The full layout runs only on a size CHANGE, and the settle check below
     * returns early once the render target matches the client - so if a hand-drag stops on a frame
     * where the minimap re-docked AFTER the bar read its position, the bar's controls stay anchored
     * to a stale minimap and drift away from it (owner, 2026-09-03: "the bar is not stuck near the
     * minimap"). Re-assert the LIGHTWEIGHT anchoring here: rz_mini_dock and rz_bar_children_right are
     * both idempotent (skip when already correct) and do NO surface recreate, so re-running them a
     * few times a second is free in the steady state and self-heals any staleness within a frame or
     * two. The expensive dock+span+fit stays on the size-change path only. */
    if (g_cluster) {
        static DWORD rz_cbar_next_ms;
        DWORD now2 = GetTickCount();
        /* EVERY FRAME: re-assert the corner widgets' ancestor rects. The game's own per-frame layout
         * re-shrinks that ancestor's rect back toward [0 0 800 600], so at a 120 ms cadence the widen
         * only wins ~1 frame in 7 and the minimize button is dead most of the time (owner: "it worked
         * a few times and it died"). rz_corner_reanchor is idempotent and cheap (widen-only, SetRect
         * skipped when the position matches), so running it every poll - after the game's cascade -
         * keeps the router's gate open whenever a click arrives. */
        g_reassert_quiet = 1;
        rz_corner_reanchor();
        g_reassert_quiet = 0;
        if (now2 >= rz_cbar_next_ms) {
            rz_cbar_next_ms = now2 + 120;
            g_reassert_quiet = 1;
            rz_mini_dock();
            g_reassert_quiet = 0;
            if (g_bar_span) {
                /* Re-assert the WHOLE bar-span, not just the children. Each step is idempotent and
                 * cheap when nothing changed (SetRect skips when already docked, fit_surface skips
                 * when the surface width already matches), so this is free in the steady state and
                 * self-heals a stale filler / stale dock left by a resize the size-change path did not
                 * fully service - owner: "the fill bar is not triggering ... elements get buried". */
                RECT pcr;
                g_reassert_quiet = 1;
                rz_hud_setrect_w(0);
                if (g_hwnd && GetClientRect(g_hwnd, &pcr))
                    rz_hud_fit_surface((DWORD)(pcr.right - pcr.left));
                rz_bar_children_right();
                g_reassert_quiet = 0;
            }
            if (g_side_span) {
                /* Re-assert the full-height side panel, same idempotent sequence as the size-change
                 * path, so the fill and the button placement persist after a resize. */
                LONG sideH;
                g_reassert_quiet = 1;
                rz_side_extend();
                sideH = rz_side_target_h();
                if (sideH > 0) rz_side_fit_surface((DWORD)sideH);
                rz_side_children_bottom();
                g_reassert_quiet = 0;
            }
        }
    }

    {   /* MINIMIZE -> RESTORE: force the HUD to repaint.
         *
         * Owner: after minimizing, part of the bottom keeps the bar's colour instead of the city.
         * Reproduced programmatically (ShowWindow SW_MINIMIZE then SW_RESTORE, then a capture):
         * the restored frame has NO HUD in it at all - no bar, no side panel, no minimap - because
         * the engine repaints the city on restore while every HUD window keeps a clear dirty byte
         * at +0x60, and FUN_1006d2d0 paints only dirty windows `[CONFIRMED @ SIMUI 0x1006d2d0]`.
         * Whatever those pixels held survives, which is what the owner sees.
         *
         * vt+0x154 sets the byte and propagates to ancestors `[CONFIRMED @ 0x1006e06b, 0x1006c784]`,
         * but it does NOT descend - so each HUD root has to be marked itself. */
        static int was_iconic;
        int now_iconic = g_hwnd ? (IsIconic(g_hwnd) ? 1 : 0) : 0;
        if (was_iconic && !now_iconic) {
            void *wins[3];
            int i, n = 0;
            wins[n++] = g_hud_top;
            wins[n++] = g_side_top;
            wins[n++] = g_mini;
            for (i = 0; i < n; i++) {
                DWORD *w = (DWORD *)wins[i];
                if (w && !IsBadReadPtr(w, 0x158)) {
                    DWORD *vt = *(DWORD **)w;
                    if (vt && !IsBadReadPtr(vt, 0x158) && vt[0x154 / 4])
                        rz_thiscall(w, (void *)vt[0x154 / 4], NULL, 0);
                }
            }
            logf("RESTORE> window un-minimized - invalidated %d HUD root(s) so they repaint", n);
        }
        was_iconic = now_iconic;
    }

    {   /* DUMP TRIGGER: a file named DUMP in the dump dir. Deleted once seen, so the owner can
           set the game up, drop the file, and get a capture of exactly that frame. */
        static DWORD next_check;
        DWORD now = GetTickCount();
        if (now >= next_check) {
            char trig[MAX_PATH];
            next_check = now + 200;
            _snprintf(trig, sizeof(trig), "%s\\DUMP", g_dumpdir);
            if (GetFileAttributesA(trig) != INVALID_FILE_ATTRIBUTES) {
                DeleteFileA(trig);
                /* Do NOT dump here. The poll runs mid-frame, so a capture taken from it can land
                   between the city blit and the HUD blits - measured: a dump with NO HUD at all
                   (no bar, no panel, no minimap), which looks exactly like a catastrophic defect
                   and is purely an artefact of sampling a half-composited frame. Instead arm a
                   flag and let the Blt hook capture immediately after the FINAL PRESENT, when the
                   frame is whole. Sampling a partial composite is the same nondiagnostic-proxy
                   mistake this project has already paid for three times. */
                g_dump_pending = 1;
                g_dump_iso = iso;
                rz_patch_ddblt();      /* the capture rides the Blt hook */
                logf("DUMP> armed - will capture right after the next full-frame present");
            }
        }
    }

    v = (DWORD *)iso;
    R = v[0x74 / 4];
    if (!R || IsBadReadPtr((void *)R, 0x2c)) return;
    {   /* task cityzoom: the view is drawn at client / factor. A new city, a zoom away from 4 (any path) or a client
           too small for the step drops the factor; the zoom keys raise and lower it (cz_zoom). */
        static void *s_czb;
        LONG mx = cz_max((LONG)w, (LONG)ht), want;
        if (g_bridge != s_czb) { s_czb = g_bridge; InterlockedExchange(&g_cz_req, 1); }
        if (v[0x28 / 4] != 4 && g_cz_req > 1) InterlockedExchange(&g_cz_req, 1);
        if (g_cz_req > mx) InterlockedExchange(&g_cz_req, mx);
        want = g_cz_req;
        cz_f = want;
        cz_cw = (LONG)w; cz_ch = (LONG)ht;
        if (want > 1) { w = (w + want - 1) / want; ht = (ht + want - 1) / want; }
    }
    /* SETTLED check. The render target is deliberately over-allocated by RZ_SURFACE_SLACK guard rows
       (zoom-blit overrun fix), so its height (+0x28) is ht..ht+SLACK, NOT exactly ht. Comparing
       == ht made the poll see a permanent mismatch and re-resize EVERY FRAME (churn -> black view +
       a zoom-out race crash, 2026-08-30). Treat width-equal and height within [ht, ht+SLACK] as
       settled; a genuine client-size change still fails this and triggers one resize. */
    if (((DWORD *)R)[0x24 / 4] == w &&
        ((DWORD *)R)[0x28 / 4] >= ht && ((DWORD *)R)[0x28 / 4] <= ht + RZ_SURFACE_SLACK) {
        /* FRESH CITY AT THE CURRENT SIZE (owner 2026-10-07): when the window was already maximized
           before New City / Load City, the game creates the new view's render target at the stored
           client size itself, so this check said "settled" and the rest of the routine (root window,
           HUD layout, input geometry) never ran - the terrain editor fought the dock every 100 ms
           and the city needed a de-maximize/maximize. Run the full routine once per new bridge. */
        if (g_cz_f != cz_f || g_cz_vw != (LONG)w || g_cz_vh != (LONG)ht) {
            g_cz_vw = (LONG)w; g_cz_vh = (LONG)ht; g_cz_f = cz_f; g_cz_surf = cz_find_surf_at(0x74); g_cz_devsurf = cz_find_surf_at(0x4ec);
        }
        if (!g_bridge_fresh || (cz_cw == NAT_W && cz_ch == NAT_H)) { g_bridge_fresh = 0; return; }
        if (!g_defer_logged) logf("RZ   fresh city view already at %lux%lu - running the layout once", w, ht);
    }

    /* LOAD-READINESS GATE (2026-08-28, cheap hygiene). Do not touch the view until the renderer is
       actually up: (a) >= g_ready_ms since bridge capture, AND (b) the render target holds a real
       backing surface (sub = *(R+0x44); sub+0xf0 bits nonzero) - i.e. the game has drawn at least
       one frame. Both cheap reads. Deferring is a no-op that retries on the next poll, so the resize
       still lands once the city is ready. */
    if (g_bridge_ms && GetTickCount() - g_bridge_ms < g_ready_ms) {
        if (!g_defer_logged) {
            logf("RZ   DEFER: resize to %lux%lu held - only %lu ms since bridge capture (< %lu). "
                 "Will retry once the city is ready.", w, ht, GetTickCount() - g_bridge_ms, g_ready_ms);
            g_defer_logged = 1;
        }
        return;
    }
    {   /* render target must have a real backing (one frame drawn) before we recreate it */
        DWORD sub = ((DWORD *)R)[0x44 / 4];
        if (!sub || IsBadReadPtr((void *)sub, 0xf8) || ((DWORD *)sub)[0xf0 / 4] == 0) {
            if (!g_defer_logged) {
                logf("RZ   DEFER: resize to %lux%lu held - render target has no backing yet "
                     "(sub=0x%08lX) - renderer not up. Will retry.", w, ht, sub);
                g_defer_logged = 1;
            }
            return;
        }
    }

    if (g_deferresize && g_hwnd && !g_in_wndproc_pass) {   /* DEFERRESIZE: run it from message dispatch */
        if (!InterlockedExchange(&g_resize_posted, 1)) PostMessageA(g_hwnd, WM_RZ_DORESIZE, 0, 0);
        return;
    }
    if (InterlockedCompareExchange(&g_busy, 1, 0) != 0) return;                /* re-entrancy */
    if (!g_bridge_fresh) {   /* a real resize, not the first layout of a new city */
        /* The poll sees the new client size ~140 ms before WM_SIZE is delivered (measured), so close here, on the
           game thread, before the layout moves the button: replay the category click first (the game's own toggle),
           and hide only if that did not close it. */
        if (g_hwnd) rz_close_flyout_by_click(g_hwnd);
        rz_close_flyouts();
    }
    logf("RZ   size change: client %lux%lu vs render target %lux%lu", w, ht,
         ((DWORD *)R)[0x24 / 4], ((DWORD *)R)[0x28 / 4]);
    if (cz_f > 1 || g_cz_f > 1)
        logf("CITYZOOM> view %lux%lu = client %ldx%ld at x%ld (was x%ld)", w, ht, cz_cw, cz_ch, cz_f, g_cz_f);
    if (cz_f != g_cz_f) {   /* keep the world point at the map-area centre where it is on screen */
        LONG aw, ah;
        rz_lcenter_area(cz_cw, cz_ch, NAT_W - 96, NAT_H - 56, &aw, &ah);
        cz_px = (LONG)v[0x54 / 4] + aw / 2 / g_cz_f; cz_py = (LONG)v[0x58 / 4] + ah / 2 / g_cz_f;
        cz_tx = cz_px - aw / 2 / cz_f; cz_ty = cz_py - ah / 2 / cz_f;
        cz_move = 1;
    }
    /* CRASH HUNT (2026-08-28): SEH around the routine so a fault becomes a DIAGNOSTIC (code +
       address resolved to MODULE+RVA + which of the 9 steps was executing) instead of a silent
       process death. This is how we catch WHERE the v3 crash actually is. */
    g_rz_step = 0;
    g_exc_code = 0;
    QueryPerformanceCounter(&tp0);
    lk = rz_sim_lock(NULL);
    QueryPerformanceCounter(&tp1);
    g_cz_dev_w = cz_f > 1 ? cz_cw : 0; g_cz_dev_h = cz_f > 1 ? cz_ch : 0;   /* task cityzoom: the frame stays client-sized */
    InterlockedExchange(&g_czp_on, 0); g_czq_n = 0;   /* DEFER: the frame is recreated below */
    __try {
        rz_do_resize(iso, w, ht);
        g_bridge_fresh = 0;
        if (cz_move && g_cz_draganchor) {   /* DRAGANCHOR (owner 2026-10-23: right-drag + '+' flew the camera away) */
            BYTE *cv = (BYTE *)rz_city_view();
            /* The right-drag scroll is a velocity from the mouse to the anchor set at the press, in view pixels [SIMSPR
               FUN_10043daf: drag on +0x1e6, anchor +0x1ec/+0x1ee (shorts, written by SetDragMode FUN_10042cfe, city view
               vt 0x10067894 +0x3c), velocity +0x1f4/+0x1f8]. After a step the moves arrive at the new q / f: put the
               anchor where it is on screen at the new factor and stop the old velocity until the next move. */
            if (cv && !IsBadWritePtr(cv - 4, 0x200)) {
                BYTE *b = cv - 4;
                if (b[0x1e6]) {
                    short ax = *(short *)(b + 0x1ec), ay = *(short *)(b + 0x1ee);
                    *(short *)(b + 0x1ec) = (short)((LONG)ax * g_cz_f / cz_f);
                    *(short *)(b + 0x1ee) = (short)((LONG)ay * g_cz_f / cz_f);
                    *(LONG *)(b + 0x1f4) = 0; *(LONG *)(b + 0x1f8) = 0;
                    logf("DRAGANCHOR> right-drag active across x%ld -> x%ld: anchor (%d,%d) -> (%d,%d), velocity reset",
                         g_cz_f, cz_f, ax, ay, *(short *)(b + 0x1ec), *(short *)(b + 0x1ee));
                }
            }
        }
        g_cz_vw = (LONG)w; g_cz_vh = (LONG)ht; g_cz_f = cz_f; g_cz_surf = cz_find_surf_at(0x74); g_cz_devsurf = cz_find_surf_at(0x4ec);   /* task cityzoom */
        if (cz_move && (!((DWORD *)v[0x74 / 4]) || !((DWORD *)v[0x74 / 4])[0x44 / 4])) {
            logf("CITYZOOM> x%ld: render target has no surface after the resize (create failed) - no ScrollTo", cz_f);
            cz_move = 0;
        }
        if (cz_move) {
            DWORD *ivt = *(DWORD **)iso, a3[3];
            a3[0] = (DWORD)cz_tx; a3[1] = (DWORD)cz_ty; a3[2] = 1;
            if (ivt && !IsBadReadPtr(ivt, 0x34) && ivt[0x30 / 4]) rz_thiscall(iso, (void *)ivt[0x30 / 4], a3, 3);   /* ScrollTo */
            logf("CITYZOOM> x%ld: centre (%ld,%ld) kept, origin -> (%ld,%ld) now (%ld,%ld)", cz_f, cz_px, cz_py, cz_tx, cz_ty,
                 (LONG)v[0x54 / 4], (LONG)v[0x58 / 4]);
        }
    } __except (rz_filter(GetExceptionInformation())) {
        char who[128];
        rz_modstr(g_exc_addr, who, sizeof(who));
        logf("RZ   *** FAULT CAUGHT *** code=0x%08lX at %s | executing STEP %ld when it faulted "
             "(1=extent 2=griddims 3=dirtygrid 4=gridB 5=RT 6=devsurf 7=FUN_10018cdf 8=rereg 9=present "
             "10=fullrepaint 11=baseview 12=hudreflow)",
             g_exc_code, who, g_rz_step);
        rz_fault_diag(iso);
    }
    rz_sim_lock(lk);
    QueryPerformanceCounter(&tp2);
    logf("RZ   TIMING pass %lux%lu: simlock wait %.1f ms, pass %.1f ms (lock to unlock)", w, ht,
         (double)(tp1.QuadPart - tp0.QuadPart) * 1000.0 / (double)g_freq.QuadPart,
         (double)(tp2.QuadPart - tp1.QuadPart) * 1000.0 / (double)g_freq.QuadPart);
    InterlockedExchange(&g_busy, 0);
}

/* Write the new client size into the GZGraphicD WINDOW OBJECT's stored RECT.
 *
 * THIS IS THE D-004 FIX (2026-08-29). Until now this subclass only OBSERVED WM_SIZE - it called
 * the original proc and logged lParam, and the comments here and at the top of this file wrongly
 * claimed it published the true client size. It did not, and that is why the hand-test failed with
 * the city drawn 800x600 in the top-left: FUN_100185f5 builds the on-screen dest rect from this
 * stored RECT (vt+0x68 = [win+0x40]-[win+0x38], vt+0x6c = [win+0x44]-[win+0x3c]) and publishes it,
 * and FUN_10018c58 (IDirectDrawSurface::Blt) presents at that size. Resizing the SIMSPR surfaces
 * alone can never help. Full evidence: re/analysis/RESIZABLE_WINDOW.md sections 8 and 8b.
 *
 * The object comes from the same global the game's own WndProc thunk uses (RVA 0x17e11 does
 * `mov ecx,[0x1006cdb8]` before calling FUN_10017e2f), so we are reading the engine's own pointer,
 * not one we inferred.
 *
 * EXPECT-OR-REFUSE: identity-check the primary vftable (gz+0x1f740, installed as [this+0] at
 * 0x17bf7 / 0x17c6e) before writing. A refusal is a LOGGED RESULT, never a forced write. */
/* DPIAWARE block (child windowed, 2026-10-12): per-DPI metrics for the frame handlers. Under per-monitor
   awareness GetSystemMetrics / AdjustWindowRectEx answer for the SYSTEM dpi (fixed at logon), not the monitor the
   window is on; the ForDpi variants (Win10 1607+) take the window's dpi. Unaware or older Windows: plain calls. */
typedef UINT (WINAPI *RZ_DPIWIN)(HWND);
typedef int  (WINAPI *RZ_SMFORDPI)(int, UINT);
typedef BOOL (WINAPI *RZ_AWRFORDPI)(LPRECT, DWORD, BOOL, DWORD, UINT);
static int rz_metric(HWND h, int idx) {
    HMODULE u = GetModuleHandleA("user32.dll");
    RZ_DPIWIN dw = (RZ_DPIWIN)GetProcAddress(u, "GetDpiForWindow");
    RZ_SMFORDPI sm = (RZ_SMFORDPI)GetProcAddress(u, "GetSystemMetricsForDpi");
    UINT dpi = dw ? dw(h) : 0;
    return (sm && dpi) ? sm(idx, dpi) : GetSystemMetrics(idx);
}
static BOOL rz_adjust_rect(HWND h, RECT *r, DWORD style, DWORD ex) {
    HMODULE u = GetModuleHandleA("user32.dll");
    RZ_DPIWIN dw = (RZ_DPIWIN)GetProcAddress(u, "GetDpiForWindow");
    RZ_AWRFORDPI aw = (RZ_AWRFORDPI)GetProcAddress(u, "AdjustWindowRectExForDpi");
    UINT dpi = dw ? dw(h) : 0;
    return (aw && dpi) ? aw(r, style, FALSE, ex, dpi) : AdjustWindowRectEx(r, style, FALSE, ex);
}

/* ⭐ MAKE THE WINDOW ACTUALLY RESIZABLE.
 *
 * The game creates a fixed-frame window: it can be maximized but not dragged to an arbitrary size
 * (owner, 2026-09-02: "i want to make the window resizeable, i just can maximize today"). The mod
 * already handles any client size - the HUD tracks it in both directions - so the only thing
 * missing is the frame style itself.
 *
 * Adds WS_THICKFRAME (the sizing border) and WS_MAXIMIZEBOX, then SWP_FRAMECHANGED so the
 * non-client area is recomputed. Done once, guarded, and logged either way. The resulting drag
 * produces ordinary WM_SIZE messages, which is the path the mod already services.
 *
 * SC3RESIZE_THICKFRAME=0 opts out. */
static void rz_make_resizable(void) {
    LONG st, want;
    if (!g_hwnd || !IsWindow(g_hwnd) || g_fs_on) return;   /* FULLSCREEN: the frame stays off until Alt+Enter */
    st = GetWindowLongA(g_hwnd, GWL_STYLE);
    want = st | WS_THICKFRAME | WS_MAXIMIZEBOX;
    if (st == want) {
        logf("FRAME> already resizable (style 0x%08lX)", st);
        return;
    }
    SetWindowLongA(g_hwnd, GWL_STYLE, want);
    SetWindowPos(g_hwnd, NULL, 0, 0, 0, 0,
                 SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED);
    logf("FRAME> style 0x%08lX -> 0x%08lX (added WS_THICKFRAME|WS_MAXIMIZEBOX) - drag-resize enabled",
         st, GetWindowLongA(g_hwnd, GWL_STYLE));
}

static void rz_set_stored_rect(DWORD w, DWORD h) {
    DWORD gz = (DWORD)GetModuleHandleA("GZGraphicD.dll");
    DWORD *win, want;
    LONG l, t;
    if (!gz) { logf("RZ   STOREDRECT REFUSED: GZGraphicD not loaded"); return; }
    if (IsBadReadPtr((void *)(gz + 0x6cdb8), 4)) {
        logf("RZ   STOREDRECT REFUSED: global gz+0x6cdb8 unreadable"); return;
    }
    win = *(DWORD **)(gz + 0x6cdb8);
    if (!win || IsBadWritePtr(win, 0x48)) {
        logf("RZ   STOREDRECT REFUSED: window object 0x%08lX unreadable/unwritable", (DWORD)win);
        return;
    }
    want = gz + 0x1f740;
    if (win[0] != want) {
        logf("RZ   STOREDRECT REFUSED: vftable mismatch - win[0]=0x%08lX expected 0x%08lX "
             "(gz base 0x%08lX + 0x1f740)", win[0], want, gz);
        return;
    }
    l = (LONG)win[0x38 / 4];
    t = (LONG)win[0x3c / 4];
    logf("RZ   STOREDRECT win=0x%08lX rect BEFORE {%ld,%ld,%ld,%ld} = %ldx%ld",
         (DWORD)win, l, t, (LONG)win[0x40 / 4], (LONG)win[0x44 / 4],
         (LONG)win[0x40 / 4] - l, (LONG)win[0x44 / 4] - t);
    /* right/bottom relative to the EXISTING left/top - FUN_100185f5 maps the rect through
       ClientToScreen, so left/top may carry a position and must not be zeroed. */
    win[0x40 / 4] = (DWORD)(l + (LONG)w);
    win[0x44 / 4] = (DWORD)(t + (LONG)h);
    logf("RZ   STOREDRECT rect AFTER  {%ld,%ld,%ld,%ld} = %lux%lu - right/bottom updated",
         l, t, (LONG)win[0x40 / 4], (LONG)win[0x44 / 4], w, h);
}

/* FULLSCREEN + WINMEM (owner 2026-10-20: "remove the screen resolution dropdown selector, resolution is driven by
 * size of the window and alt + enter should enter fullscreen and keep current refresh rate"; design calls the same
 * day: borderless, remember size and fullscreen like the HUD scale, leave a gap where the dropdown was).
 *   - Alt+Enter toggles BORDERLESS fullscreen: the frame styles come off and the window covers the whole monitor it
 *     is on. The display mode is never changed (the game stays DDSCL_NORMAL), so the desktop resolution and refresh
 *     rate are kept by construction. The game's own fullscreen is exclusive mode through DD1 SetDisplayMode(w,h,bpp),
 *     which has no refresh-rate argument [GZGraphicD FUN_10011f73], and is not used. To the game this is an ordinary
 *     WM_SIZE, the path the resize mod already services. Alt+Enter again restores the frame and the placement.
 *   - sc3resize.ini [window]: left/top/right/bottom (the normal, restored rect), maximized, fullscreen. Written on
 *     every change (end of a drag, maximize/restore, toggle), read at the subclass and applied once.
 * The stock game has no Alt+Enter: its WndProc FUN_10017e2f turns WM_SYSKEYDOWN into its own key path and never calls
 * DefWindowProc for it [CONFIRMED @ GZGraphicD 0x10017e2f]. SC3RESIZE_FSKEY=0 / SC3RESIZE_WINMEM=0 turn each off. */
static int g_fskey = 1, g_winmem = 1;
static DWORD g_wm_usert;   /* last player window command (WM_SYSCOMMAND / title double-click), task cityzoom */
static int g_wm_restoring, g_wm_applied;   /* g_fs_on is declared beside rz_make_resizable's forward decl */
static LONG g_fs_style, g_fs_exstyle;
static WINDOWPLACEMENT g_fs_wp;

static void wm_save(void) {
    char p[MAX_PATH], v[16];
    WINDOWPLACEMENT wp;
    RECT *r;
    if (!g_winmem || !g_wm_applied || g_wm_restoring || !g_hwnd) return;
    if (g_fs_on) wp = g_fs_wp;   /* the placement to come back to, not the monitor-sized popup */
    else {
        wp.length = sizeof(wp);
        if (!GetWindowPlacement(g_hwnd, &wp) || wp.showCmd == SW_SHOWMINIMIZED || IsIconic(g_hwnd)) return;
    }
    r = &wp.rcNormalPosition;
    if (r->right - r->left < NAT_W || r->bottom - r->top < NAT_H) return;
    ho_ini_path(p, sizeof(p));
    wsprintfA(v, "%ld", r->left);   WritePrivateProfileStringA("window", "left", v, p);
    wsprintfA(v, "%ld", r->top);    WritePrivateProfileStringA("window", "top", v, p);
    wsprintfA(v, "%ld", r->right);  WritePrivateProfileStringA("window", "right", v, p);
    wsprintfA(v, "%ld", r->bottom); WritePrivateProfileStringA("window", "bottom", v, p);
    WritePrivateProfileStringA("window", "maximized", (wp.showCmd == SW_SHOWMAXIMIZED || (wp.flags & WPF_RESTORETOMAXIMIZED)) ? "1" : "0", p);
    WritePrivateProfileStringA("window", "fullscreen", g_fs_on ? "1" : "0", p);
}

static void rz_fs_enter(HWND h) {
    MONITORINFO mi;
    LONG st;
    if (g_fs_on) return;
    g_fs_wp.length = sizeof(g_fs_wp);
    if (!GetWindowPlacement(h, &g_fs_wp)) return;
    mi.cbSize = sizeof(mi);
    if (!GetMonitorInfoA(MonitorFromWindow(h, MONITOR_DEFAULTTONEAREST), &mi)) return;
    g_fs_style = GetWindowLongA(h, GWL_STYLE);
    g_fs_exstyle = GetWindowLongA(h, GWL_EXSTYLE);
    if (IsZoomed(h)) g_fs_wp.flags |= WPF_RESTORETOMAXIMIZED;
    g_fs_on = 1;
    st = (g_fs_style & ~(WS_CAPTION | WS_THICKFRAME | WS_SYSMENU | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_MAXIMIZE)) | WS_POPUP;
    SetWindowLongA(h, GWL_STYLE, st);
    SetWindowLongA(h, GWL_EXSTYLE, g_fs_exstyle & ~(WS_EX_WINDOWEDGE | WS_EX_CLIENTEDGE | WS_EX_DLGMODALFRAME));
    SetWindowPos(h, HWND_TOP, mi.rcMonitor.left, mi.rcMonitor.top, mi.rcMonitor.right - mi.rcMonitor.left,
                 mi.rcMonitor.bottom - mi.rcMonitor.top, SWP_NOOWNERZORDER | SWP_FRAMECHANGED | SWP_SHOWWINDOW);
    logf("FULLSCREEN> on: style 0x%08lX -> 0x%08lX, monitor [%ld %ld %ld %ld], display mode untouched", g_fs_style,
         GetWindowLongA(h, GWL_STYLE), mi.rcMonitor.left, mi.rcMonitor.top, mi.rcMonitor.right, mi.rcMonitor.bottom);
    wm_save();
}

static void rz_fs_leave(HWND h) {
    RECT cr;
    if (!g_fs_on) return;
    g_fs_on = 0;
    SetWindowLongA(h, GWL_STYLE, g_fs_style & ~WS_MAXIMIZE);
    SetWindowLongA(h, GWL_EXSTYLE, g_fs_exstyle);
    SetWindowPos(h, NULL, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOOWNERZORDER | SWP_FRAMECHANGED);
    g_fs_wp.showCmd = (g_fs_wp.flags & WPF_RESTORETOMAXIMIZED) ? SW_SHOWMAXIMIZED : SW_SHOWNORMAL;
    SetWindowPlacement(h, &g_fs_wp);
    GetClientRect(h, &cr);
    logf("FULLSCREEN> off: style 0x%08lX, client %ldx%ld%s", GetWindowLongA(h, GWL_STYLE), cr.right, cr.bottom,
         g_fs_wp.showCmd == SW_SHOWMAXIMIZED ? " (maximized)" : "");
    wm_save();
}

/* Once, from the subclass: put the window back where the last session left it. */
static void wm_restore(HWND h) {
    char p[MAX_PATH];
    WINDOWPLACEMENT wp;
    RECT r;
    int mx, fs;
    if (g_wm_applied) return;
    g_wm_applied = 1;
    if (!g_winmem) return;
    ho_ini_path(p, sizeof(p));
    r.left   = (LONG)GetPrivateProfileIntA("window", "left", 0x7fffffff, p);
    r.top    = (LONG)GetPrivateProfileIntA("window", "top", 0x7fffffff, p);
    r.right  = (LONG)GetPrivateProfileIntA("window", "right", 0x7fffffff, p);
    r.bottom = (LONG)GetPrivateProfileIntA("window", "bottom", 0x7fffffff, p);
    mx = (int)GetPrivateProfileIntA("window", "maximized", 0, p);
    fs = (int)GetPrivateProfileIntA("window", "fullscreen", 0, p);
    if (r.left == 0x7fffffff || r.top == 0x7fffffff || r.right == 0x7fffffff || r.bottom == 0x7fffffff ||
        r.right - r.left < NAT_W || r.bottom - r.top < NAT_H) {
        logf("WINMEM> no saved window in sc3resize.ini - game default");
        if (fs && g_fskey) rz_fs_enter(h);
        return;
    }
    wp.length = sizeof(wp);
    if (!GetWindowPlacement(h, &wp)) return;
    g_wm_restoring = 1;
    wp.rcNormalPosition = r;   /* SetWindowPlacement moves it onto a monitor if the saved one is gone */
    wp.showCmd = mx ? SW_SHOWMAXIMIZED : SW_SHOWNORMAL;
    wp.flags = 0;
    SetWindowPlacement(h, &wp);
    g_wm_restoring = 0;
    logf("WINMEM> restored [%ld %ld %ld %ld]%s%s", r.left, r.top, r.right, r.bottom, mx ? " maximized" : "",
         fs && g_fskey ? ", fullscreen" : "");
    if (fs && g_fskey) rz_fs_enter(h);
}

/* Subclass the game window so a real WM_SIZE publishes the REAL client size.
 * GZGraphicD's own handler (FUN_100185f5, reached via vt+0x30) republishes the window object's
 * STORED size and nothing in the engine updates it on a stock resize, so without the
 * rz_set_stored_rect call below the engine never learns the new size and the primary Blt keeps
 * presenting the old rectangle. Doing it here in C is what makes the separate GZGraphicD
 * `wmsize_setrect` patch unnecessary under this mod. */
/* task cityzoom: a client point on a visible UI window (HUD, dialog, flyout) rather than the city view. */
static int cz_on_ui(LONG x, LONG y) {
    DWORD exe = (DWORD)GetModuleHandleA(NULL), spr = (DWORD)GetModuleHandleA("SIMSPR.DLL");
    void *lvl[2], *root = rz_ui_root();
    int nl = 1, li;
    if (!root) return 0;
    lvl[0] = root;
    for (li = 0; li < nl; li++) {
        void *head = *(void **)((DWORD)lvl[li] + 0x34), *nd;
        int g = 0;
        if (!head || IsBadReadPtr(head, 4)) continue;
        for (nd = *(void **)head; nd && nd != head && g++ < 300; nd = *(void **)nd) {
            DWORD *c, vt;
            if (IsBadReadPtr(nd, 0x0c)) break;
            c = *(DWORD **)((DWORD)nd + 8);
            if (!c || IsBadReadPtr(c, 0xa4)) continue;
            vt = c[0];
            if (exe && vt == exe + 0xd32d0) { if (nl < 2) lvl[nl++] = c; continue; }   /* HUD container */
            if (!(c[0xa0 / 4] & 1)) continue;                                         /* hidden */
            if (spr && vt == spr + 0x676ac) continue;                                 /* the city view */
            if (exe && vt == exe + 0xd3bcc) continue;                                 /* the tooltip / cost label */
            if (x >= (LONG)c[0x14 / 4] && x < (LONG)c[0x1c / 4] && y >= (LONG)c[0x18 / 4] && y < (LONG)c[0x20 / 4]) return 1;
        }
    }
    return 0;
}

/* task cityzoom: a queued mouse message on the city goes to view point q / f. A press there keeps the map until its
   release (a drag that ends on the HUD stays in the city). The game reposts a move at the point we produced ~15 ms later
   (HUDSCALE's REPOST): such a move is left as is. 1 = mapped. */
static LPARAM g_cz_last_out;
static int    g_cz_last_ok, g_cz_cap, g_cz_depth, g_cz_mlog;
static DWORD  g_cz_last_t;
static LONG cz_div(LONG v, LONG f) { return v >= 0 ? v / f : -((-v + f - 1) / f); }
static int cz_mouse(UINT m, LPARAM *lp) {
    LONG f = g_cz_f, x, y, nx, ny;
    if (f <= 1) { g_cz_cap = 0; return 0; }
    if (m == WM_MOUSEMOVE && g_cz_last_ok && *lp == g_cz_last_out && GetTickCount() - g_cz_last_t < 500) return 0;
    x = (LONG)(short)LOWORD(*lp); y = (LONG)(short)HIWORD(*lp);
    if (!g_cz_cap && cz_on_ui(x, y)) return 0;
    nx = cz_div(x, f); ny = cz_div(y, f);
    if (m == WM_LBUTTONDOWN || m == WM_RBUTTONDOWN || m == WM_MBUTTONDOWN ||
        m == WM_LBUTTONDBLCLK || m == WM_RBUTTONDBLCLK || m == WM_MBUTTONDBLCLK) g_cz_cap = 1;
    else if (m == WM_LBUTTONUP || m == WM_RBUTTONUP || m == WM_MBUTTONUP) g_cz_cap = 0;
    *lp = MAKELPARAM((WORD)(short)nx, (WORD)(short)ny);
    g_cz_last_out = *lp; g_cz_last_ok = 1; g_cz_last_t = GetTickCount();
    if (m != WM_MOUSEMOVE && g_cz_mlog < 40) {
        g_cz_mlog++;
        logf("CITYZOOM> msg 0x%04X client (%ld,%ld) -> view (%ld,%ld) at x%ld%s", m, x, y, nx, ny, f,
             cz_on_ui(nx, ny) ? " (lands on a UI window)" : "");
    }
    return 1;
}

static LRESULT CALLBACK rz_wndproc(HWND h, UINT m, WPARAM wp, LPARAM lp) {
    if (m == WM_RBUTTONDOWN) { g_cz_rpx = (short)LOWORD(lp); g_cz_rpy = (short)HIWORD(lp); g_cz_rpf = 1; }   /* raw; a mapping block below overwrites it */
    if (m == WM_PAINT || m == WM_ERASEBKGND || m == WM_SIZE || m == WM_ACTIVATE || m == WM_ACTIVATEAPP ||
        m == WM_WINDOWPOSCHANGED || m == WM_DISPLAYCHANGE || m == WM_NCPAINT) g_ms_full_req = 1;   /* MENUSCALE */
    if (g_pausekey && wp == 'P' && (m == WM_KEYDOWN || m == WM_KEYUP) && GetKeyState(VK_CONTROL) >= 0 &&
        GetKeyState(VK_MENU) >= 0 && GetKeyState(VK_SHIFT) >= 0 && !rz_text_focus()) {        /* PAUSEKEY */
        if (m == WM_KEYUP || (lp & 0x40000000) || rz_pause_toggle()) return 0;
    }
    if (g_speedkeys && (m == WM_KEYDOWN || m == WM_KEYUP) && GetKeyState(VK_CONTROL) >= 0 &&
        GetKeyState(VK_MENU) >= 0 && GetKeyState(VK_SHIFT) >= 0 &&
        ((wp >= '1' && wp <= '4') || (wp >= VK_NUMPAD1 && wp <= VK_NUMPAD4)) && !rz_text_focus()) {   /* SPEEDKEYS */
        int n = (wp >= VK_NUMPAD1) ? (int)(wp - VK_NUMPAD1) + 1 : (int)(wp - '1') + 1;
        if (m == WM_KEYUP || (lp & 0x40000000) || rz_speed_key(n)) return 0;
    }
    if (g_closex && m == WM_CLOSE) { rz_closex("WM_CLOSE"); return 0; }   /* CLOSEX */
    if (g_closex && wp == VK_F4 && (m == WM_SYSKEYDOWN || m == WM_SYSKEYUP) && (lp & 0x20000000)) {
        if (m == WM_SYSKEYDOWN && !(lp & 0x40000000)) rz_closex("Alt+F4");
        return 0;
    }
    if (g_fskey && wp == VK_RETURN && (m == WM_SYSKEYDOWN || m == WM_SYSKEYUP) && (lp & 0x20000000)) {   /* FULLSCREEN */
        if (m == WM_SYSKEYDOWN && !(lp & 0x40000000)) { if (g_fs_on) rz_fs_leave(h); else rz_fs_enter(h); }
        return 0;
    }
    if (g_fskey && m == WM_SYSCHAR && wp == '\r') return 0;   /* the Alt+Enter char: no beep, not a game key */
    if (g_fs_on && m == WM_SYSCOMMAND) {   /* no frame to drag or maximize while fullscreen (Win+Up, the Alt+Space menu) */
        UINT sc = (UINT)(wp & 0xfff0);
        if (sc == SC_MAXIMIZE || sc == SC_SIZE || sc == SC_MOVE || sc == SC_RESTORE) return 0;
    }
    if (m == WM_EXITSIZEMOVE) wm_save();   /* WINMEM: end of a drag */
    if (m == WM_SYSCOMMAND || m == WM_NCLBUTTONDBLCLK) g_wm_usert = GetTickCount();
    if (g_zoomkeys && (m == WM_KEYDOWN || m == WM_KEYUP)) {   /* ZOOMKEYS */
        if (wp == VK_OEM_PLUS) wp = VK_ADD;
        else if (wp == VK_OEM_MINUS) wp = VK_SUBTRACT;
    }
    if (m == WM_MOUSEWHEEL && g_cz_f > 1 && !g_mb_active) {   /* task cityzoom: GZGraphicD FUN_100178a6 takes its point */
        POINT pt;
        pt.x = (LONG)(short)LOWORD(lp); pt.y = (LONG)(short)HIWORD(lp);
        if (ScreenToClient(h, &pt) && !cz_on_ui(pt.x, pt.y)) {
            pt.x = cz_div(pt.x, g_cz_f); pt.y = cz_div(pt.y, g_cz_f);
            if (ClientToScreen(h, &pt)) lp = MAKELPARAM((WORD)(short)pt.x, (WORD)(short)pt.y);
        }
    }
    if (m == WM_RZ_DORESIZE) {   /* DEFERRESIZE: the resize pass, outside any drawing lock */
        InterlockedExchange(&g_resize_posted, 0);
        g_in_wndproc_pass = 1;
        rz_poll();
        g_in_wndproc_pass = 0;
        return 0;
    }
    /* MENUSCALE: while the menu frame is presented scaled, map client mouse coordinates into it through the same rect.
       Nesting depth does NOT tell queue messages apart at the menu: "Preferencias" runs a modal loop inside the button
       handler, so every later click arrives at depth 1 from the queue, in client coordinates (measured: the close box
       missed while depth-1 messages were left alone). What is left alone is a message carrying exactly the frame
       point we produced last, within 500 ms: a WM_MOUSEMOVE at any depth (the game's queued repost, measured at the
       menu after every click), or a button message at depth > 0 (one the game sends itself while handling ours). */
    if (g_menubg && g_mb_active && g_ms_on && m >= WM_MOUSEMOVE && m <= WM_MBUTTONDBLCLK) {
        LRESULT r;
        if (g_ms_repost && g_ms_last_ok && lp == g_ms_last_out && GetTickCount() - g_ms_last_t < 500 &&
            (m == WM_MOUSEMOVE || g_ms_depth > 0)) {
            if (g_ms_replog < 10) { g_ms_replog++;
                logf("MENUSCALE> msg 0x%04X at our last frame point (%d,%d), depth %d, left unmapped", m,
                     (int)(short)LOWORD(lp), (int)(short)HIWORD(lp), g_ms_depth); }
        } else {
            LONG cx = (LONG)(short)LOWORD(lp), cy = (LONG)(short)HIWORD(lp);
            LONG fx = rz_ms_map(cx, g_ms_rx, g_ms_rw, NAT_W), fy = rz_ms_map(cy, g_ms_ry, g_ms_rh, NAT_H);
            lp = MAKELPARAM((WORD)(short)fx, (WORD)(short)fy);
            g_ms_last_out = lp; g_ms_last_ok = 1; g_ms_last_t = GetTickCount();
            if (m != WM_MOUSEMOVE && g_ms_mlog < 60) { g_ms_mlog++;
                logf("MENUSCALE> msg 0x%04X client (%ld,%ld) -> frame (%ld,%ld), depth %d", m, cx, cy, fx, fy, g_ms_depth); }
        }
        g_ms_depth++;
        r = CallWindowProcA(g_oldproc, h, m, wp, lp);
        g_ms_depth--;
        return r;
    }
    /* MENUBG: while the 800x600 menu frame is presented centred, shift client mouse coordinates into it. */
    if (g_menubg && g_mb_active && m >= WM_MOUSEMOVE && m <= WM_MBUTTONDBLCLK) {
        int mx = (int)(short)LOWORD(lp) - (int)g_mb_offx, my = (int)(short)HIWORD(lp) - (int)g_mb_offy;
        lp = MAKELPARAM((WORD)(short)mx, (WORD)(short)my);
    }
    /* HUDSCALE: a mouse message on the enlarged HUD goes to the native widget under it. Only messages that come
       from the queue are mapped: a mouse message the game sends to itself while handling one (nested) already
       carries native coordinates, and mapping it again moved a flyout-item click onto the emergency button. */
    if (g_hudscale && !g_mb_active && m >= WM_MOUSEMOVE && m <= WM_MBUTTONDBLCLK) {
        LRESULT r;
        if (g_hs_mlog && g_hs_mlog_n < 400) {
            g_hs_mlog_n++;
            logf("HSMLOG> in  msg 0x%04X (%d,%d) wp 0x%lx depth %d n %ld t %lu", m, (int)(short)LOWORD(lp),
                 (int)(short)HIWORD(lp), (DWORD)wp, g_hs_depth, g_hs_n, GetMessageTime());
        }
        if (g_hd_n > 0 && rz_hd_mouse(m, &lp)) {
            /* DLGSCALE: on an enlarged dialog (mapped, or already native): the HUD map below is not for it */
        } else if (g_hs_depth == 0 && g_hs_n > 0) {
            /* REPOST (task hudopt 2026-10-11): a WM_MOUSEMOVE carrying exactly the native point we produced for the
               previous message comes back through the queue ~15 ms later (measured: in (1100,332) -> native
               (1120,446), then a queued move at (1120,446); the physical cursor never moved). Mapping it again
               put the hover two flyout items lower ("Guardar como" over "Preferencias") and the click opened
               nothing. Such a move already holds native coordinates: pass it through. =0 maps it like any other. */
            if (g_hs_repost && m == WM_MOUSEMOVE && g_hs_last_ok && lp == g_hs_last_out &&
                GetTickCount() - g_hs_last_t < 500) {
                if (g_hs_repost_log < 10) { g_hs_repost_log++;
                    logf("HUDSCALE> queued move at our last native point (%d,%d) left unmapped",
                         (int)(short)LOWORD(lp), (int)(short)HIWORD(lp)); }
            } else if (rz_hs_mouse(m, &lp)) {
                g_hs_last_out = lp; g_hs_last_ok = 1; g_hs_last_t = GetTickCount();
                g_hs_mouse_hud = 1;
            } else { g_hs_mouse_hud = 0; cz_mouse(m, &lp); }   /* task cityzoom: the city at a factor */
        }
        else if (g_hs_depth == 0) cz_mouse(m, &lp);   /* task cityzoom: HUD not enlarged this frame */
        else if (m != WM_MOUSEMOVE && g_hs_nestlog < 20) {
            g_hs_nestlog++;
            logf("HUDSCALE> nested mouse msg 0x%04X at (%d,%d) left as is (sent by the game while handling one)",
                 m, (int)(short)LOWORD(lp), (int)(short)HIWORD(lp));
        }
        if (m == WM_LBUTTONDOWN) rz_note_panel_click(lp);
        if (m == WM_RBUTTONDOWN && g_hs_depth == 0) { g_cz_rpx = (short)LOWORD(lp); g_cz_rpy = (short)HIWORD(lp); g_cz_rpf = g_cz_f; }
        g_hs_depth++;
        r = CallWindowProcA(g_oldproc, h, m, wp, lp);
        g_hs_depth--;
        return r;
    }
    /* task cityzoom: the same map with HUD scale off (HUDSCALE's block above handles it when on) */
    if (g_cz_f > 1 && !g_mb_active && m >= WM_MOUSEMOVE && m <= WM_MBUTTONDBLCLK) {
        LRESULT r;
        if (g_cz_depth == 0) cz_mouse(m, &lp);
        if (m == WM_RBUTTONDOWN && g_cz_depth == 0) { g_cz_rpx = (short)LOWORD(lp); g_cz_rpy = (short)HIWORD(lp); g_cz_rpf = g_cz_f; }
        g_cz_depth++;
        r = CallWindowProcA(g_oldproc, h, m, wp, lp);
        g_cz_depth--;
        return r;
    }
    /* ⭐ LET THE USER DRAG THE WINDOW TO ANY SIZE.
     *
     * The window already carries WS_THICKFRAME|WS_MAXIMIZEBOX (measured: style 0x95CF0000), so the
     * sizing border exists - yet the owner can only maximize. The remaining lever is
     * WM_GETMINMAXINFO: whatever the game answers there caps the drag. Let the game's handler run
     * first, then widen the track limits. Min is kept sane (the HUD is 800x600 native and the
     * layout code needs room); max is the virtual screen, so multi-monitor still works.
     * SC3RESIZE_THICKFRAME=0 leaves the game's own limits alone. */
    /* ⭐ THE SIZING BORDER HAS TO ANSWER THE HIT TEST.
     *
     * The window carries WS_THICKFRAME and WM_GETMINMAXINFO is widened, yet the owner still cannot
     * drag an edge - and SetWindowPos resizes the window fine, so nothing rejects the SIZE, only
     * the DRAG. That points at WM_NCHITTEST: if the game answers HTCLIENT over the frame, Windows
     * never starts a sizing loop. Let the game answer first, and only when it says HTCLIENT and the
     * cursor is within the border margin of the window edge, substitute the proper edge code. */
    if (m == WM_NCHITTEST && g_thickframe && !g_fs_on) {   /* FULLSCREEN: no sizing edges on the borderless window */
        LRESULT r = CallWindowProcA(g_oldproc, h, m, wp, lp);
        if (r == HTCLIENT) {
            RECT wr;
            int mx = (int)(short)LOWORD(lp), my = (int)(short)HIWORD(lp);
            int bw = rz_metric(h, SM_CXSIZEFRAME) + 4;
            if (GetWindowRect(h, &wr)) {
                int left = mx < wr.left + bw, right = mx >= wr.right - bw;
                int top = my < wr.top + bw, bottom = my >= wr.bottom - bw;
                if (!g_hit_logged && (left || right || top || bottom)) {
                    g_hit_logged = 1;
                    logf("FRAME> WM_NCHITTEST returned HTCLIENT over the frame - substituting edge "
                         "codes so the sizing border works (margin %d)", bw);
                }
                if (top && left)      return HTTOPLEFT;
                if (top && right)     return HTTOPRIGHT;
                if (bottom && left)   return HTBOTTOMLEFT;
                if (bottom && right)  return HTBOTTOMRIGHT;
                if (left)             return HTLEFT;
                if (right)            return HTRIGHT;
                if (top)              return HTTOP;
                if (bottom)           return HTBOTTOM;
            }
        }
        return r;
    }
    /* Show the SIZING CURSOR over the frame.
     *
     * The drag itself works once WM_NCHITTEST answers edge codes (verified by driving the real
     * mouse: client 1684x961 -> 1836x961 on a right-edge drag). But the game paints its own cursor
     * and answers WM_SETCURSOR, so the user never sees a resize arrow and cannot tell the border is
     * grabbable - which is indistinguishable from "cannot drag". Set the system sizing cursor
     * whenever the hit code in the low word is a border code, and claim the message. */
    if (m == WM_SETCURSOR && g_thickframe) {
        WORD hit = LOWORD(lp);
        LPCSTR id = NULL;
        switch (hit) {
            case HTLEFT: case HTRIGHT:              id = IDC_SIZEWE;   break;
            case HTTOP:  case HTBOTTOM:             id = IDC_SIZENS;   break;
            case HTTOPLEFT: case HTBOTTOMRIGHT:     id = IDC_SIZENWSE; break;
            case HTTOPRIGHT: case HTBOTTOMLEFT:     id = IDC_SIZENESW; break;
            default: break;
        }
        if (id) {
            SetCursor(LoadCursorA(NULL, id));
            return TRUE;
        }
    }
    /* SNAP the client WIDTH to a 32-multiple while dragging. At widths whose width*2 is not 64-byte
     * aligned (e.g. client 1000 -> pitch 2000) the device/composite surface pads its pitch to 2048
     * and the compositor's width*2 stride no longer matches, shearing the whole frame diagonally and
     * greying it (measured 2026-09-03: 800/960 clean, 1000 sheared). Constraining the drag rect so
     * the CLIENT width is always a multiple of 32 keeps every size on a self-consistent pitch. The
     * edge being dragged is in wp (WMSZ_*); adjust the moving edge so the fixed edge stays put. */
    if (m == WM_SIZING && g_thickframe && g_wsnap > 1 && lp) {
        RECT *wr = (RECT *)lp, cr, cwr;
        if (GetClientRect(h, &cr) && GetWindowRect(h, &cwr)) {
            LONG frame = (cwr.right - cwr.left) - (cr.right - cr.left);   /* constant non-client width */
            LONG cw = (wr->right - wr->left) - frame;                     /* PROPOSED client width */
            /* Round to the NEAREST multiple (not floor) so the dragged edge meets or just passes the
             * cursor (±g_wsnap/2) instead of always trailing it by up to g_wsnap-1 (owner: "it never
             * reaches the end position of my cursor"). The multiple itself is required: width*2 must
             * be 64-byte aligned or the composite surface shears. */
            LONG snapped = ((cw + g_wsnap / 2) / g_wsnap) * g_wsnap;
            if (snapped < g_wsnap) snapped = g_wsnap;
            if (snapped != cw) {
                LONG neww = snapped + frame;
                if (!g_wsnap_logged) {
                    g_wsnap_logged = 1;
                    logf("FRAME> WM_SIZING wp=%lu wr=[%ld %ld %ld %ld] client cur=%ld frame=%ld "
                         "proposed cw=%ld -> snap %ld (neww=%ld)", (DWORD)wp, wr->left, wr->top,
                         wr->right, wr->bottom, cr.right - cr.left, frame, cw, snapped, neww);
                }
                switch (wp) {
                    case WMSZ_LEFT: case WMSZ_TOPLEFT: case WMSZ_BOTTOMLEFT:
                        wr->left = wr->right - neww; break;
                    default:  /* right/top/bottom edges move the right side */
                        wr->right = wr->left + neww; break;
                }
            }
        }
        return CallWindowProcA(g_oldproc, h, m, wp, lp);
    }
    if (m == WM_GETMINMAXINFO && g_thickframe && lp) {
        LRESULT r = CallWindowProcA(g_oldproc, h, m, wp, lp);
        MINMAXINFO *mmi = (MINMAXINFO *)lp;
        if (!IsBadWritePtr(mmi, sizeof(MINMAXINFO))) {
            int vx = GetSystemMetrics(SM_CXVIRTUALSCREEN), vy = GetSystemMetrics(SM_CYVIRTUALSCREEN);
            /* MIN = native. The HUD is authored for an 800x600 client and stays native-size (dx/dy
             * clamp at 0); below that the window is narrower than the HUD and the right panel clips
             * off-screen (measured 2026-09-03 at 704x600). Floor the window at the size that yields an
             * 800x600 CLIENT, computed from THIS window's own frame so it is correct for the style. */
            RECT nc = { 0, 0, NAT_W, NAT_H };
            LONG minw = NAT_W + 16, minh = NAT_H + 39;   /* fallback if AdjustWindowRect fails */
            LONG style = GetWindowLongA(h, GWL_STYLE), ex = GetWindowLongA(h, GWL_EXSTYLE);
            if (rz_adjust_rect(h, &nc, (DWORD)style, (DWORD)ex)) {
                minw = nc.right - nc.left;
                minh = nc.bottom - nc.top;
            }
            if (vx < minw) vx = minw;
            if (vy < minh) vy = minh;
            mmi->ptMinTrackSize.x = minw;
            mmi->ptMinTrackSize.y = minh;
            mmi->ptMaxTrackSize.x = vx;
            mmi->ptMaxTrackSize.y = vy;
            if (!g_minmax_logged) {
                g_minmax_logged = 1;
                logf("FRAME> WM_GETMINMAXINFO widened: track %ld..%ld x %ld..%ld (virtual screen)",
                     mmi->ptMinTrackSize.x, mmi->ptMaxTrackSize.x,
                     mmi->ptMinTrackSize.y, mmi->ptMaxTrackSize.y);
            }
        }
        return r;
    }
    if (m == WM_LBUTTONDOWN && !g_mb_active) rz_note_panel_click(lp);
    if (m == WM_SIZE && wp != SIZE_MINIMIZED) {
        LRESULT r;
        DWORD w = (DWORD)LOWORD(lp), hh = (DWORD)HIWORD(lp);
        /* Update the stored RECT BEFORE the game's handler runs, so the republish it performs
           on this same message already carries the new size. */
        if (w && hh) rz_set_stored_rect(w, hh);
        /* Then let the game's handler run, and let the per-frame poll do the surface work on the
           render thread - never resize from the message thread. */
        r = CallWindowProcA(g_oldproc, h, m, wp, lp);
        logf("RZ   WM_SIZE %lux%lu - poll will pick it up on the next frame", w, hh);
        if (wp == SIZE_MAXIMIZED || wp == SIZE_RESTORED) {   /* WINMEM: a maximize or restore (a drag saves at its end) */
            static WPARAM last = (WPARAM)-1;
            /* task cityzoom (owner's quits, 2026-10-22): at quit the game itself restores the window to 800x600 (WM_SIZE
               SIZE_RESTORED 800x600 ~0.6 s after the quit dialog, no player command), which saved maximized=0 and the next
               start came up small. A restore to exactly 800x600 counts only after a player window command. */
            if (wp == SIZE_RESTORED && w == NAT_W && hh == NAT_H && GetTickCount() - g_wm_usert > 2000) {
                logf("WINMEM> restore to 800x600 without a player command (the game's own, at quit) - not saved");
                last = wp;
            } else if (wp != last) { last = wp; wm_save(); }
        }
        return r;
    }
    /* ---- INPUT CLAMP PROBE (SC3RESIZE_INPUT=1) -------------------------------------------------
     * Owner: the relocated HUD is not clickable. Located statically: EVERY mouse coordinate is
     * clamped before the UI sees it, in FUN_100178a6 at LAB_10017aaa -
     *     x < 0        -> 0
     *     x >= vt+0x68 -> vt+0x68 - 1        (vt+0x68 = [win+0x40] - [win+0x38] = WIDTH)
     * and identically for y with vt+0x6c (HEIGHT)  [CONFIRMED @ GZGraphicD 0x100178a6, 0x10017c1e].
     *
     * Those getters read the STORED RECT at win+0x38..0x44 - the exact field the mod's D-004 fix
     * writes on WM_SIZE. So either the rect is stale when a click arrives (clamp to 800x600, and the
     * corner HUD is unreachable by construction), or it is correct and the clamp is innocent and the
     * blocker is further up in SIMUI's hit-testing.
     *
     * This logs, per click, the raw coordinates and the LIVE clamp bounds read from the window
     * object. One line per click, read-only, no dispatch through anything. It distinguishes the two
     * cases outright rather than by inference. */
    if (g_input && (m == WM_LBUTTONDOWN || m == WM_RBUTTONDOWN)) {
        DWORD gz = (DWORD)GetModuleHandleA("GZGraphicD.dll");
        LONG x = (LONG)(SHORT)LOWORD(lp), y = (LONG)(SHORT)HIWORD(lp);
        if (gz && !IsBadReadPtr((void *)(gz + 0x6cdb8), 4)) {
            DWORD *win = *(DWORD **)(gz + 0x6cdb8);
            if (win && !IsBadReadPtr(win, 0x48)) {
                LONG l = (LONG)win[0x38/4], t = (LONG)win[0x3c/4];
                LONG r2 = (LONG)win[0x40/4], b = (LONG)win[0x44/4];
                LONG cw = r2 - l, ch = b - t;
                logf("INPUT> click raw=(%ld,%ld) clamp bounds=%ldx%ld (stored rect [%ld %ld %ld %ld])"
                     "%s", x, y, cw, ch, l, t, r2, b,
                     (x >= cw || y >= ch)
                       ? "   <<< OUTSIDE THE CLAMP - this click is being pulled back inside" : "");
                /* Per-click state of every captured HUD window, using ONLY confirmed offsets.
                 *   +0x14..0x20  window rect - what vt+0xe4 = SIMUI FUN_1006de62 actually compares,
                 *                and FUN_1006de62 is the hit test FUN_1001e748 calls on fallthrough
                 *                [CONFIRMED @ GZWIND 0x1001e748; SIMUI 0x1006de62]
                 *   +0x80..0x8c  read as EXTENTS by FUN_1006ddbd (vt+0x1a0), and as the origin link
                 *                by vt+0x98/0x9c summed in FUN_1006dd44 [CONFIRMED @ SIMUI 0x1006dd44]
                 *   +0xa0        flags; bit 0x1 = shown, gates the child walk in FUN_1001e748
                 *                [CONFIRMED @ GZWIND 0x1001dd9a, SIMUI 0x1006c2f7]
                 * No guessed offsets and no dispatch - run 24 threw 21 AVs from invented offsets
                 * after being described as bounded and defensive. Marks whether the click is inside
                 * the window rect: run 36 established that "nothing responded" is not evidence
                 * unless the click is shown to have landed on the target. */
                {
                    LONG i;
                    for (i = 0; i < g_wins_n; i++) {
                        DWORD *ww = (DWORD *)g_wins[i].w;
                        LONG *wr, *hr; DWORD fl;
                        if (!ww || IsBadReadPtr(ww, 0xa4)) continue;
                        wr = (LONG *)((DWORD)ww + 0x14);
                        hr = (LONG *)((DWORD)ww + 0x80);
                        fl = ww[0xa0/4];
                        logf("WINSTATE> [%ld] %p vt=%p  rect+0x14=[%ld %ld %ld %ld]  "
                             "ext+0x80=[%ld %ld %ld %ld] (%ldx%ld)  flags+0xa0=0x%08lX shown=%d%s",
                             i, (void *)ww, (void *)*(DWORD **)ww,
                             wr[0], wr[1], wr[2], wr[3],
                             hr[0], hr[1], hr[2], hr[3], hr[2] - hr[0], hr[3] - hr[1],
                             fl, (int)(fl & 1),
                             (x >= wr[0] && x < wr[2] && y >= wr[1] && y < wr[3])
                               ? "   <<< CLICK IS INSIDE THIS WINDOW RECT" : "");
                    }
                }
                /* Run 36 proved the clamp innocent, so the blocker is the UI event sink. FUN_10017e2f
                   dispatches through (*(window+0x30))->vt[0x64] (`+ 100` in the decompilation), and
                   window+0x30 is written by the plain setter FUN_10017c3c
                   [CONFIRMED @ GZGraphicD 0x10017e2f, 0x10017c3c]. Resolve the sink's class and that
                   slot ONCE - it is the door the hit-test lives behind, and the board has carried
                   "the real hit-test dispatcher was not located" since the HUD reflow work. */
                if (!g_sink_logged) {
                    DWORD sink = win[0x30/4];
                    g_sink_logged = 1;
                    if (sink && !IsBadReadPtr((void *)sink, 4)) {
                        DWORD *svt = *(DWORD **)sink;
                        char who[160], slot[160];
                        rz_modstr((DWORD)svt, who, sizeof(who));
                        if (svt && !IsBadReadPtr(svt, 0x68)) {
                            rz_modstr(svt[0x64/4], slot, sizeof(slot));
                            logf("INPUT> event sink window+0x30 = 0x%08lX  vtable %s",
                                 sink, who);
                            logf("INPUT> sink vt+0x64 (the mouse-event entry) = %s", slot);
                            /* GZWIND FUN_10020818 consumes the coordinates in two places
                               [CONFIRMED @ GZWIND 0x10020818]:
                                 (sink+0x30)->vt[0xe4](x,y)  - hit-test the focused window
                                 (sink+0x38)->vt[0x8c](x,y)  - find WHICH window contains the point
                               The second is the dispatcher the board records as never located.
                               Resolve both objects and both slots. */
                            {   static const struct { int off, sl; const char *what; } q[] = {
                                    { 0x28, 0x104, "captured widget" },
                                    { 0x30, 0x0e4, "focused window HIT-TEST(x,y)" },
                                    { 0x38, 0x08c, "FIND-WINDOW-AT-POINT(x,y)" } };
                                int qi;
                                for (qi = 0; qi < 3; qi++) {
                                    DWORD o = ((DWORD *)sink)[q[qi].off / 4];
                                    char ow[160], os[160];
                                    if (!o || IsBadReadPtr((void *)o, 4)) {
                                        logf("INPUT>   sink+0x%02x (%s) = 0x%08lX (null)",
                                             q[qi].off, q[qi].what, o);
                                        continue;
                                    }
                                    {   DWORD *ovt = *(DWORD **)o;
                                        rz_modstr((DWORD)ovt, ow, sizeof(ow));
                                        if (ovt && !IsBadReadPtr(ovt, q[qi].sl + 4)) {
                                            rz_modstr(ovt[q[qi].sl / 4], os, sizeof(os));
                                            logf("INPUT>   sink+0x%02x = 0x%08lX vtable %s",
                                                 q[qi].off, o, ow);
                                            logf("INPUT>     vt+0x%03x %s = %s",
                                                 q[qi].sl, q[qi].what, os);
                                        } else {
                                            logf("INPUT>   sink+0x%02x = 0x%08lX vtable %s (slot unreadable)",
                                                 q[qi].off, o, ow);
                                        }
                                    }
                                }
                            }
                        } else {
                            logf("INPUT> event sink 0x%08lX vtable %s unreadable", sink, who);
                        }
                    } else {
                        logf("INPUT> event sink window+0x30 is NULL/unreadable (0x%08lX)", sink);
                    }
                }
            }
        }
    }
    return CallWindowProcA(g_oldproc, h, m, wp, lp);
}

static BOOL CALLBACK rz_enum(HWND h, LPARAM p) {
    DWORD pid = 0;
    char cls[64];
    GetWindowThreadProcessId(h, &pid);
    if (pid != GetCurrentProcessId()) return TRUE;
    if (!GetClassNameA(h, cls, sizeof(cls))) return TRUE;
    if (!IsWindowVisible(h)) return TRUE;
    *(HWND *)p = h;
    return FALSE;
}

static void rz_subclass(void) {
    HWND h = NULL;
    EnumWindows(rz_enum, (LPARAM)&h);
    if (!h) return;
    g_hwnd = h;
    g_oldproc = (WNDPROC)SetWindowLongA(h, GWL_WNDPROC, (LONG)rz_wndproc);
    g_wm_fixed = 1;
    logf("### RESIZE: window 0x%08lX subclassed (old proc 0x%08lX) - WM_SIZE observed, "
         "resize performed on the render thread", (DWORD)h, (DWORD)g_oldproc);
    /* WINDOWED-EARLY block: if the style bytes could not be patched, the frame is still fixed here and the
       resize step that would add it never runs (no resize is possible). Add it now. */
    if (g_thickframe) rz_make_resizable();
    wm_restore(h);   /* WINMEM: last session's size, maximize and fullscreen */
    /* One line that answers "what did this machine do" from a player's log: frame style, client size,
       DPI of the window and its monitor, and the process DPI awareness (0 = unaware: Windows scales the
       window bitmap on a >100% screen). Resolved dynamically, every call is Win10 1607+. */
    {   typedef UINT (WINAPI *DPIWIN)(HWND);
        typedef HANDLE (WINAPI *GETCTX)(void);
        typedef int (WINAPI *AWARE)(HANDLE);
        typedef LONG (WINAPI *MONDPI)(HMONITOR, int, UINT *, UINT *);
        HMODULE u = GetModuleHandleA("user32.dll"), sh = LoadLibraryA("shcore.dll");
        DPIWIN dw = (DPIWIN)GetProcAddress(u, "GetDpiForWindow");
        GETCTX gc = (GETCTX)GetProcAddress(u, "GetThreadDpiAwarenessContext");
        AWARE aw = (AWARE)GetProcAddress(u, "GetAwarenessFromDpiAwarenessContext");
        MONDPI md = sh ? (MONDPI)GetProcAddress(sh, "GetDpiForMonitor") : NULL;
        HMONITOR mon = MonitorFromWindow(h, MONITOR_DEFAULTTONEAREST);
        MONITORINFO mi;
        RECT cr;
        UINT mx = 0, my = 0;
        mi.cbSize = sizeof(mi);
        GetMonitorInfoA(mon, &mi);
        GetClientRect(h, &cr);
        if (md) md(mon, 0, &mx, &my);
        typedef HANDLE (WINAPI *WINCTX)(HWND);
        typedef BOOL (WINAPI *CTXEQ)(HANDLE, HANDLE);
        WINCTX wc = (WINCTX)GetProcAddress(u, "GetWindowDpiAwarenessContext");
        CTXEQ eq = (CTXEQ)GetProcAddress(u, "AreDpiAwarenessContextsEqual");
        HANDLE ctx = wc ? wc(h) : NULL;
        logf("DISPLAY> style 0x%08lX client %ldx%ld, window dpi %u, monitor dpi %u (effective), monitor [%ld %ld %ld %ld], "
             "thread awareness %d, WINDOW awareness %d%s (0 unaware = Windows stretches it, 1 system, 2 per-monitor), "
             "dpiaware setting %d", (DWORD)GetWindowLongA(h, GWL_STYLE),
             cr.right - cr.left, cr.bottom - cr.top, dw ? dw(h) : 0, mx, mi.rcMonitor.left, mi.rcMonitor.top,
             mi.rcMonitor.right, mi.rcMonitor.bottom, (gc && aw) ? aw(gc()) : -1, (ctx && aw) ? aw(ctx) : -1,
             (ctx && eq && eq(ctx, (HANDLE)(LONG_PTR)-4)) ? " (per-monitor v2)" : "", g_dpiaware);
    }
    {   /* CLOSEX: say whether this GZGraphicD carries the on-disk close_button_quit cave (WM_CLOSE je rel32 at
           0x10017ead = 0x00005959 instead of stock 0x00000316). Diagnostic only. */
        BYTE *gz = (BYTE *)GetModuleHandleA("GZGraphicD.dll");
        DWORD rel = 0;
        if (gz) { __try { rel = *(DWORD *)(gz + 0x17ead); } __except (EXCEPTION_EXECUTE_HANDLER) { rel = 0; } }
        logf("CLOSEX> %s; GZGraphicD WM_CLOSE branch rel32 0x%08lX (%s)", g_closex ? "on" : "off (SC3RESIZE_CLOSEX=0)",
             rel, rel == 0x5959 ? "on-disk close_button_quit cave present" : rel == 0x316 ? "stock" : "unknown");
    }
}

/* Minimal replacement for the probe's multi-branch fnlog_enter. Same __stdcall(idx, f)
 * contract the installed stub expects. idx 0 = the bridge capture, idx 1 = the heartbeat. */
static void __stdcall fnlog_enter(int idx, DWORD *f) {
    if (idx == 0) {
        /* FUN_10016eba is __thiscall: ECX is the bridge.
           Frame layout is the stub's `pushad; pushfd; mov eax,esp; push eax`, so from the
           pointer: f[0]=eflags, f[1..8]=edi,esi,ebp,esp,ebx,edx,ecx,eax, f[9]=return address,
           f[10..]=stack args. **f[7] = ECX** - taken from sc3probe.c:8650-8658, which documents
           and uses exactly this layout, NOT re-derived here. */
        DWORD ecx = f[7];
        if (ecx && !IsBadReadPtr((void *)ecx, 0xf4) && g_bridge != (void *)ecx) {
            g_bridge = (void *)ecx;
            g_bridge_ms = GetTickCount();
            g_defer_logged = 0;
            g_bridge_fresh = 1;
            logf("### RESIZE: bridge captured 0x%08lX (iso view = bridge+0x18 = 0x%08lX); "
                 "readiness gate = %lu ms", ecx, ((DWORD *)ecx)[0x18 / 4], g_ready_ms);
        }
        return;
    }
    if (idx == 1) {
        /* This hook IS the render thread, so it is where the profiler learns which thread to sample.
           Cheap and idempotent; no call when it has not changed. */
        if (g_hudlab) { rz_blt_sample(f[7]); }
        g_wrapper_caller = f[9];   /* -> FUN_10014894+0x76, proven run 19 */

        {   /* f[3] = EBP = FUN_10014894's live frame pointer (it does push ebp; mov ebp,esp) */

            DWORD fp = f[3], fp2;

            g_caller_l2 = g_caller_l3 = 0;

            if (fp && !IsBadReadPtr((void *)fp, 8)) {

                g_caller_l2 = *(DWORD *)(fp + 4);          /* the tiling loop */

                fp2 = *(DWORD *)fp;

                if (fp2 && fp2 > fp && !IsBadReadPtr((void *)fp2, 8))

                    g_caller_l3 = *(DWORD *)(fp2 + 4);     /* opportunistic - HINT only */

            }

        }
        if (g_hudlab) {
            DWORD me = GetCurrentThreadId();
            if (g_game_tid != me) g_game_tid = me;
        }
        if (!g_wm_fixed) rz_subclass();
        if (g_menubg && !g_blt_slot && f[7] && !IsBadReadPtr((void *)(f[7] + 4), 4))
            rz_patch_ddblt_surf(*(DWORD *)(f[7] + 4));
        rz_poll();
        if (g_census_ms && GetTickCount() >= g_census_ms) { g_census_ms = 0; rz_census(); }
        if (g_hudlab) rz_hudlab_tick();
        return;
    }
    if (idx == 6) {

        /* FUN_1006d2d0(this): ECX = f[7]. The dest rect lives at this+0x90. Identify the minimap by

           geometry - the same 100..400 square-ish band that isolated it in run 25 - because it has no

           class of its own to match on. Read-only. */

        DWORD ecx = f[7];

        if (ecx && !IsBadReadPtr((void *)ecx, 0xa0)) {

            LONG *r = (LONG *)(ecx + 0x90);
            LONG w = r[2] - r[0], h = r[3] - r[1];
            /* Gated on BOTH consumers. Recording it only under g_anchor meant cluster mode had an empty
                   table and silently translated nothing - the third time this session a feature was
                   wired behind the wrong flag (lab-vs-ship twice, now anchor-vs-cluster). The fault
                   each time was gating the PRODUCER on one consumer instead of on all of them. */
                if ((g_anchor || g_cluster) && w > 0 && h > 0 && g_wins_n < WIN_MAX) {
                /* Record each window's NATIVE rect ONCE, before any resize moves it, so repeated
                   resizes re-anchor from the original instead of compounding - the same lesson the
                   bar's art cache taught. Bounded by the native screen, and the main view is
                   excluded by area so we never move the thing the HUD sits on top of. */
                LONG q; int seen = 0;
                for (q = 0; q < g_wins_n; q++) if (g_wins[q].w == (void *)ecx) { seen = 1; break; }
                /* Bounds relaxed +64: the RCI indicator sits at [599 520 640 608] and a strict `<= 600`
                       rejected it, which is why it never moved. Overhang is normal for native UI. */
                    /* Not dialogs: SIMUI+0xa4d64 windows of at least 120x80 are managed by rz_dialogs_poll.
                       Capturing them here translated them like HUD pieces and kept their pointers after
                       they were freed (owner hand test 2026-10-05). */
                    DWORD suic = (DWORD)GetModuleHandleA("SIMUI.DLL");
                    int is_dlg = suic && *(DWORD *)ecx == suic + 0xa4d64 && w >= 120 && h >= 80;
                    if (!seen && !is_dlg && r[0] >= -64 && r[1] >= -64 && r[2] <= NAT_W + 64 && r[3] <= NAT_H + 64 &&
                    (w * h) <= (NAT_W * NAT_H * 7) / 10) {
                    LONG *wr = (LONG *)(ecx + 0x14);   /* the window's own (absolute) rect */
                    g_wins[g_wins_n].w = (void *)ecx;
                    g_wins[g_wins_n].nat[0] = r[0]; g_wins[g_wins_n].nat[1] = r[1];
                    g_wins[g_wins_n].nat[2] = r[2]; g_wins[g_wins_n].nat[3] = r[3];
                    /* Classify root vs child ONCE, at native, before anything moves - the same
                       reason `nat` is captured once. Comparing the ORIGINS is enough and is what
                       the existing DIVERGE log line already computes; sizes can legitimately
                       differ without implying parentage. */
                    g_wins[g_wins_n].natwin[0] = wr[0]; g_wins[g_wins_n].natwin[1] = wr[1];
                    g_wins[g_wins_n].natwin[2] = wr[2]; g_wins[g_wins_n].natwin[3] = wr[3];
                    g_wins[g_wins_n].child = (wr[0] != r[0] || wr[1] != r[1]);
                    logf("WINCAP> [%ld] 0x%08lX paint=[%ld %ld %ld %ld] window=[%ld %ld %ld %ld] "
                         "-> %s (parent origin delta %ld,%ld)",
                         g_wins_n, ecx, r[0], r[1], r[2], r[3], wr[0], wr[1], wr[2], wr[3],
                         g_wins[g_wins_n].child ? "CHILD (will NOT be translated)" : "root",
                         wr[0] - r[0], wr[1] - r[1]);
                    g_wins_n++;
                }
            }

            /* MINICLASS (2026-10-10): geometry alone also matched DIALOGS. The Ordinances window
               (374x226) passed the band, so every repaint of it while the sim ran (its costs update)
               re-captured it as the minimap, alternating with the real one. The side panel's target
               height and the bar's anchor follow g_mini, so both flipped (panel local 923 <-> 1081,
               every button +-158 px, the bar's controls slid right) - owner: "the bottom bar moves
               when a panel like ordinances is open, only while the simulation runs". Measured live:
               captures of 0x22CA7298 [789 394 1163 620] interleaved with the minimap 0x0EB2C498.
               The minimap does have a class: SIMUI+0xaa180, set by its ctor FUN_1004f90f
               [CONFIRMED @ SIMUI 0x1004f90f] and the only window of it in a live tree walk.
               SC3RESIZE_MINICLASS=0 restores the geometry-only match. */
            DWORD suim = (DWORD)GetModuleHandleA("SIMUI.DLL");
            if (w >= 100 && w <= 400 && h >= 100 && h <= 400 && w < h * 2 && h < w * 2 &&
                (!g_miniclass || !suim || *(DWORD *)ecx == suim + 0xaa180)) {

                if (g_mini != (void *)ecx) {

                    g_mini = (void *)ecx;

                    g_mini_rect[0] = r[0]; g_mini_rect[1] = r[1];

                    g_mini_rect[2] = r[2]; g_mini_rect[3] = r[3];

                    logf("### MINI: window captured 0x%08lX vt=0x%08lX dest(this+0x90)=[%ld %ld %ld %ld] %ldx%ld",

                         ecx, *(DWORD *)ecx, r[0], r[1], r[2], r[3], w, h);

                }

            }

        }

        return;

    }

    if (idx == 4 || idx == 5) {
        /* Minimap hunt: capture up to CAPT_MAX instances of each candidate window class. ECX = f[7]
           per the stub's documented pushad layout. Rects are read later, at diag time. */
        int slot = idx - 4;
        DWORD ecx = f[7];
        LONG n = g_capt_n[slot], k;
        if (ecx && !IsBadReadPtr((void *)ecx, 0x24) && n < CAPT_MAX) {
            for (k = 0; k < n; k++) if (g_capt[slot][k] == (void *)ecx) return;
            g_capt[slot][n] = (void *)ecx;
            g_capt_n[slot] = n + 1;
            logf("### CAPT[%d] #%ld = 0x%08lX", slot, n, ecx);
        }
        return;
    }
    if (idx == 3) {
        /* SIMUI FUN_1004e123, the side panel ctor: __fastcall(this), so ECX = f[7] per the stub's
           documented pushad layout. Captured at construction, exactly as the bar's `this` is. */
        DWORD ecx = f[7];
        if (ecx && !IsBadReadPtr((void *)ecx, 0x120) && g_side_top != (void *)ecx) {
            g_side_top = (void *)ecx;
            logf("### SIDE: panel window captured 0x%08lX (SIMUI FUN_1004e123 ctor)", ecx);
        }
        return;
    }
    if (idx == 2) {
        /* FUN_10009efb create: record the REAL 8-arg tuple per object, so a later replay uses the
           create arguments rather than field read-back (which is measurably not the same thing).
           Frame layout per sc3probe.c:8650-8658: f[7]=ecx (the raster), f[10..]=stack args. */
        DWORD obj = f[7];
        int i, n;
        if (!obj) return;
        n = (int)g_nrc;
        for (i = 0; i < n && i < MAX_RC; i++) {
            if (g_rc[i].obj == obj) {                    /* refresh in place */
                int k; for (k = 0; k < 8; k++) g_rc[i].a[k] = f[10 + k];
                return;
            }
        }
        if (n >= MAX_RC) { InterlockedExchange(&g_rc_full, 1); return; }
        g_rc[n].obj = obj;
        for (i = 0; i < 8; i++) g_rc[n].a[i] = f[10 + i];
        InterlockedIncrement(&g_nrc);
    }
}

static int install_one(DWORD va, void *base, DWORD rva, const char *name, int idx) {
    FNLOG *e;
    if (g_nfn >= MAX_FNLOG) return 0;
    e = &g_fn[g_nfn];
    memset(e, 0, sizeof(*e));
    e->va     = va;
    e->target = (BYTE *)base + rva;
    e->logret = 0;
    lstrcpynA(e->name, name, sizeof(e->name));
    if (!fnlog_install_one(e, idx)) {
        logf("### RESIZE: FAILED to install %s", name);
        return 0;
    }
    g_nfn++;
    return 1;
}

/* DISPLAY-MODE CONTROL (2026-08-28). The routine was validated only under the harness's
 * -windowed -fix16 patches, and the first two DLL runs launched in the game's DEFAULT mode - a
 * confound the owner caught. Both patches are carved VERBATIM from sc3probe.c (patch_windowed,
 * patch_surfacefmt) so the byte operations are not re-derived, resolved from the live GZGraphicD
 * base. Applied at watcher start, before the fnlog hooks and before the city loads. */
/* STARTRES (owner 2026-10-20): with the Preferences dropdown gone, the game must not come up at a resolution saved
   by an earlier pick of it. Every run of this mod was measured from an 800x600 start, and the HUD layout group is
   picked from the root width (640 / 800 / >= 801, SIMUI FUN_100270e5). So SetResolution GZGraphicD FUN_10010ed1 (the
   gfx vt+0xDC that SC3U FUN_0040586a calls with the saved prefs, stdcall, copies 7 dwords to +0x6cd90) is replaced
   by the same copy with W/H forced to 800x600. The window then sizes the view. SC3RESIZE_STARTRES=0 keeps the
   game's request. Fail-closed on the prologue, as sc3startsize.c (which hooks the same function, and loses). */
static int   g_startres = 1;
static DWORD g_sr_gz;
static void __stdcall rz_startres_hook(DWORD *blk) {
    DWORD *dst = (DWORD *)(g_sr_gz + 0x6cd90);
    int i;
    for (i = 0; i < 7; i++) dst[i] = blk[i];
    logf("STARTRES> game asked %lux%lux%lu -> %dx%d", blk[0], blk[1], blk[2], NAT_W, NAT_H);
    dst[0] = NAT_W;
    dst[1] = NAT_H;
}
static void patch_startres(HMODULE gz) {
    static const BYTE expect[] = { 0x56, 0x8b, 0x74, 0x24, 0x08, 0x57, 0x6a, 0x07, 0x59, 0xbf };
    BYTE *t = (BYTE *)gz + 0x10ed1;
    DWORD old;
    if (!g_startres || g_sr_gz) return;
    if (memcmp(t, expect, sizeof(expect)) || *(DWORD *)(t + 10) != (DWORD)gz + 0x6cd90) {
        logf("STARTRES> FUN_10010ed1 differs from the anchor (another hook?) - NOT hooked"); return;
    }
    if (!VirtualProtect(t, 5, PAGE_EXECUTE_READWRITE, &old)) return;
    g_sr_gz = (DWORD)gz;
    t[0] = 0xE9; *(DWORD *)(t + 1) = (DWORD)rz_startres_hook - (DWORD)(t + 5);
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    FlushInstructionCache(GetCurrentProcess(), t, 5);
    logf("STARTRES> FUN_10010ed1 hooked: the game starts at %dx%d", NAT_W, NAT_H);
}

static void patch_windowed(HMODULE gz) {
    BYTE *p = (BYTE *)gz + 0x6cdac;         /* the windowed flag Init reads */
    BYTE *q = (BYTE *)gz + 0x117d6;         /* the fullscreen re-force store */
    DWORD old;
    if (VirtualProtect(p, 1, PAGE_EXECUTE_READWRITE, &old)) {
        BYTE before = *p; *p = 1; (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
        logf("--- WINDOWED: GZGraphicD+0x6cdac = %u -> 1", before);
    } else logf("--- WINDOWED: VirtualProtect failed at +0x6cdac (%lu)", GetLastError());
    if (q[0] == 0xC6 && q[1] == 0x43 && q[2] == 0x48 && q[3] == 0x01) {
        DWORD o2;
        if (VirtualProtect(q, 4, PAGE_EXECUTE_READWRITE, &o2)) {
            q[0] = q[1] = q[2] = q[3] = 0x90; (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
            FlushInstructionCache(GetCurrentProcess(), q, 4);
            logf("--- WINDOWED: GZGraphicD+0x117D6 'mov [ebx+0x48],1' -> nop x4");
        }
    } else {
        logf("--- WINDOWED: 0x117D6 pattern mismatch (%02X %02X %02X %02X)", q[0], q[1], q[2], q[3]);
    }
}

static void patch_surfacefmt(HMODULE gz) {
    BYTE *site = (BYTE *)gz + 0x19349;
    static const BYTE orig[10] = { 0xF6,0xDB, 0x1B,0xDB, 0x81,0xE3,0xC0,0x0F,0x00,0x00 };
    BYTE *cave;
    DWORD old;
    int n = 0, jne_fixup, block_start;
    if (memcmp(site, orig, sizeof(orig)) != 0) {
        logf("--- FIX16: 0x19349 pattern mismatch (%02X %02X %02X %02X), NOT patched",
             site[0], site[1], site[2], site[3]);
        return;
    }
    cave = (BYTE *)VirtualAlloc(NULL, 256, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!cave) { logf("--- FIX16: VirtualAlloc failed (%lu)", GetLastError()); return; }
    cave[n++] = 0x50;
    cave[n++]=0x83;cave[n++]=0xBE;cave[n++]=0x10;cave[n++]=0;cave[n++]=0;cave[n++]=0;cave[n++]=0x07;
    cave[n++] = 0x75; jne_fixup = n; cave[n++] = 0x00;
    block_start = n;
    #define MOV_D(off,imm) do{ cave[n++]=0xC7;cave[n++]=0x86; \
        cave[n++]=(BYTE)(off);cave[n++]=(BYTE)((off)>>8);cave[n++]=0;cave[n++]=0; \
        cave[n++]=(BYTE)(imm);cave[n++]=(BYTE)((imm)>>8);cave[n++]=(BYTE)((imm)>>16);cave[n++]=(BYTE)((imm)>>24);}while(0)
    MOV_D(0x10, 0x1007);
    MOV_D(0x54, 0x20);
    cave[n++]=0x83;cave[n++]=0x8E;cave[n++]=0x58;cave[n++]=0;cave[n++]=0;cave[n++]=0;cave[n++]=0x40;
    MOV_D(0x60, 0x10);
    MOV_D(0x64, 0xF800);
    MOV_D(0x68, 0x07E0);
    MOV_D(0x6C, 0x001F);
    #undef MOV_D
    cave[jne_fixup] = (BYTE)(n - block_start);
    cave[n++] = 0x58;
    memcpy(cave + n, orig, sizeof(orig)); n += sizeof(orig);
    cave[n++] = 0xE9;
    { DWORD tgt = (DWORD)((BYTE *)gz + 0x19353);
      DWORD rel = tgt - (DWORD)(cave + n + 4); memcpy(cave + n, &rel, 4); n += 4; }
    FlushInstructionCache(GetCurrentProcess(), cave, n);
    if (!VirtualProtect(site, 10, PAGE_EXECUTE_READWRITE, &old)) {
        logf("--- FIX16: VirtualProtect failed (%lu)", GetLastError()); return;
    }
    site[0] = 0xE9;
    { DWORD rel = (DWORD)cave - (DWORD)(site + 5); memcpy(site + 1, &rel, 4); }
    site[5]=site[6]=site[7]=site[8]=site[9]=0x90;
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    FlushInstructionCache(GetCurrentProcess(), site, 10);
    logf("--- FIX16: 16bpp branch injected at 0x19349 -> cave 0x%08lX (5-6-5)", (DWORD)cave);
}

/* ⭐ WINDOWED-EARLY + FRAME (child windowed, 2026-10-12, verify/windowed/).
 *
 * Owner report from a STOCK install + release sc3mods-2026-10-12: no windowed, no "escalado". Measured on
 * Simcity_stock: the window comes up windowed but with the stock FIXED frame, style 0x94CA0000 (no
 * WS_THICKFRAME, no WS_MAXIMIZEBOX), so it can be neither dragged nor maximized. rz_make_resizable only runs
 * inside the resize step, which only runs after a resize: on stock it never runs. Every owner test so far ran
 * on MAIN\Apps, whose GZGraphicD carries pe_patch.py `resizable_frame` on disk (style 0x94CF0000 from creation).
 *
 * This applies that recipe's three same-length imm bytes in memory, plus the windowed and 16-bit patches,
 * from a loader notification (LdrRegisterDllNotification, LOADED), i.e. after GZGraphicD is mapped and
 * relocated and before its DllMain or any of its code runs. The watcher's 100 ms poll (and the 1 ms polls in
 * sc3bigcity / sc3overscroll) only win the race against GZGraphicD Init by load order; this removes the race.
 *   0x10017ca1  c7 43 10 1b 00 00 00   mov [ebx+0x10],0x1b   -> 0x3b  create mask: MAXIMIZEBOX branch on
 *   0x10018220  0d 00 00 01 00         or eax,0x10000        -> 0x50000 fold WS_THICKFRAME in beside it
 *   0x1001856d  68 00 00 c8 90         push 0x90C80000       -> 0x90CD0000 live windowed style (SetWindowLongA)
 * [CONFIRMED @ GZGraphicD 0x100181d0, 0x1001854a], none of the bytes is under a base relocation.
 * All-or-nothing; already-patched bytes (MAIN's on-disk build) are logged and left alone.
 * SC3RESIZE_EARLY=0 goes back to the watcher-only path. SC3RESIZE_THICKFRAME=0 skips the frame bytes. */
static int g_early = 1;
static PVOID g_ldr_cookie;
static volatile LONG g_gz_early;

static void patch_frame_style(HMODULE gz) {
    static const struct { DWORD rva; BYTE stock[7]; int len; int at; BYTE want; } s[3] = {
        { 0x17ca1, { 0xC7,0x43,0x10,0x1B,0x00,0x00,0x00 }, 7, 3, 0x3B },
        { 0x18220, { 0x0D,0x00,0x00,0x01,0x00 },           5, 3, 0x05 },
        { 0x1856d, { 0x68,0x00,0x00,0xC8,0x90 },           5, 3, 0xCD },
    };
    int i, stock = 0, done = 0;
    for (i = 0; i < 3; i++) {
        BYTE *p = (BYTE *)gz + s[i].rva;
        if (!memcmp(p, s[i].stock, s[i].len)) stock++;
        else if (!memcmp(p, s[i].stock, s[i].at) && p[s[i].at] == s[i].want &&
                 !memcmp(p + s[i].at + 1, s[i].stock + s[i].at + 1, s[i].len - s[i].at - 1)) done++;
    }
    if (done == 3) { logf("--- FRAME: GZGraphicD style bytes already resizable (on-disk resizable_frame or applied earlier)"); return; }
    if (stock != 3) { logf("--- FRAME: GZGraphicD style bytes differ from shipped (%d stock, %d patched) - NOT patched", stock, done); return; }
    for (i = 0; i < 3; i++) {
        BYTE *p = (BYTE *)gz + s[i].rva + s[i].at;
        DWORD old;
        if (!VirtualProtect(p, 1, PAGE_EXECUTE_READWRITE, &old)) {
            logf("--- FRAME: VirtualProtect failed at +0x%lX (%lu)", s[i].rva + s[i].at, GetLastError()); return; }
        *p = s[i].want;
        (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
        FlushInstructionCache(GetCurrentProcess(), p, 1);
    }
    logf("--- FRAME: GZGraphicD create mask 0x1b->0x3b, or 0x10000->0x50000, live style 0x90C80000->0x90CD0000 "
         "(WS_THICKFRAME|WS_MAXIMIZEBOX, same bytes as pe_patch resizable_frame)");
}

typedef struct { USHORT Length, MaximumLength; PWSTR Buffer; } RZ_USTR;
typedef struct { ULONG Flags; const RZ_USTR *FullDllName; const RZ_USTR *BaseDllName; PVOID DllBase; ULONG SizeOfImage; } RZ_LDR_DATA;
typedef VOID (CALLBACK *RZ_LDR_FN)(ULONG, const RZ_LDR_DATA *, PVOID);
typedef LONG (NTAPI *RZ_LDR_REG)(ULONG, RZ_LDR_FN, PVOID, PVOID *);

/* Loader-lock context: only byte patches, VirtualAlloc/Protect and logf (whose lock is never held across a
   loader call). No LoadLibrary, no thread waits. */
static VOID CALLBACK rz_ldr_notify(ULONG reason, const RZ_LDR_DATA *d, PVOID ctx) {
    static const WCHAR want[] = L"gzgraphicd.dll";
    int i, n;
    (void)ctx;
    if (reason != 1 || !d || !d->BaseDllName || !d->BaseDllName->Buffer || g_gz_early) return;
    n = d->BaseDllName->Length / 2;
    if (n != (int)(sizeof(want) / 2 - 1)) return;
    for (i = 0; i < n; i++) {
        WCHAR c = d->BaseDllName->Buffer[i];
        if (c >= L'A' && c <= L'Z') c = (WCHAR)(c + 32);
        if (c != want[i]) return;
    }
    if (InterlockedExchange(&g_gz_early, 1)) return;
    logf("--- EARLY: GZGraphicD mapped at 0x%08lX, patching before its DllMain (loader notification)", (DWORD)d->DllBase);
    patch_windowed((HMODULE)d->DllBase);
    patch_startres((HMODULE)d->DllBase);
    patch_surfacefmt((HMODULE)d->DllBase);
    if (g_thickframe) patch_frame_style((HMODULE)d->DllBase);
}

/* ⭐ DPIAWARE (child windowed, 2026-10-12). Owner design call: on a >100% screen the game is drawn sharp at its
 * real pixel size, not stretched by Windows (SC3U has no manifest, so it ran DPI-unaware, measured awareness 0).
 * Set here, in DllMain: mods_launch injects sc3resize first while the game's main thread is still suspended, so
 * this runs before the game creates any window. Awareness is per process and settable once.
 * Per-monitor v2 first: the game draws its whole client itself (no child controls), so v2 only adds what we want:
 * the caption/frame scaled for the monitor the window is on, and no bitmap stretch on a monitor whose dpi differs
 * from the system dpi (system-aware would stretch there, the thing the owner rejected). WM_DPICHANGED is not
 * handled: moving to another monitor keeps the client's pixel size, which the resize mod handles like any size.
 * Fallbacks: per-monitor v1 context, then system-aware (SetProcessDPIAware). Read back and logged, so an AppCompat layer that
 * forces awareness (DPIUNAWARE / GDIDPISCALING) shows up as "requested 2, in effect 0".
 * sc3resize.ini [display] dpiaware=0 or SC3RESIZE_DPIAWARE=0 keeps the old unaware behaviour (g_dpiaware). */

static void rz_dpi_aware(void) {
    typedef BOOL (WINAPI *SETCTX)(HANDLE);
    typedef HANDLE (WINAPI *GETCTX)(void);
    typedef int (WINAPI *AWARE)(HANDLE);
    HMODULE u = GetModuleHandleA("user32.dll");
    SETCTX sc = (SETCTX)GetProcAddress(u, "SetProcessDpiAwarenessContext");
    GETCTX gc = (GETCTX)GetProcAddress(u, "GetThreadDpiAwarenessContext");
    AWARE aw = (AWARE)GetProcAddress(u, "GetAwarenessFromDpiAwarenessContext");
    const char *how = "none";
    DWORD err = 0;
    int before = (gc && aw) ? aw(gc()) : -1;
    if (sc && sc((HANDLE)(LONG_PTR)-4)) how = "SetProcessDpiAwarenessContext(PER_MONITOR_AWARE_V2)";
    else {
        err = GetLastError();
        if (sc && sc((HANDLE)(LONG_PTR)-3)) how = "SetProcessDpiAwarenessContext(PER_MONITOR_AWARE)";
        else { typedef BOOL (WINAPI *SETAW)(void); SETAW sa = (SETAW)GetProcAddress(u, "SetProcessDPIAware");
               if (sa && sa()) how = "SetProcessDPIAware (system)"; }   /* no LoadLibrary under the loader lock */
    }
    logf("DPI> awareness before %d, last call that returned TRUE: %s (first call error %lu), in effect now %d "
         "(0 unaware, 1 system, 2 per-monitor; the DISPLAY> line has the window's own)%s",
         before, how, err, (gc && aw) ? aw(gc()) : -1,
         err == ERROR_ACCESS_DENIED ? " - ALREADY FIXED BEFORE THE MOD: an AppCompat layer (Properties > Compatibility >"
         " high DPI override) or a manifest decides it. Measured: System / System (Enhanced) keep it at 0" : "");
}

static void rz_early_register(void) {
    RZ_LDR_REG reg = (RZ_LDR_REG)GetProcAddress(GetModuleHandleA("ntdll.dll"), "LdrRegisterDllNotification");
    LONG st;
    if (GetModuleHandleA("GZGraphicD.dll")) {
        logf("--- EARLY: GZGraphicD already loaded at mod load - the watcher patches it (late injection)");
        return;
    }
    if (!reg) { logf("--- EARLY: LdrRegisterDllNotification not found - watcher path only"); return; }
    st = reg(0, rz_ldr_notify, NULL, &g_ldr_cookie);
    logf("--- EARLY: loader notification %s (status 0x%08lX)", st >= 0 ? "registered" : "FAILED", (DWORD)st);
}

/* FIX A (2026-08-28): clamp the grid-B bucket index in FUN_1000cedb.
 * Root cause (verify/resize_rootcause): the far-edge cell maps to bucket index == grid dim (8 on the
 * 8x8 grid), one past the 64-bucket array; `lea edi,[base+index*4]` then reads OOB and the walk
 * dereferences a garbage "node" -> AV (heap-layout-dependent, hence intermittent). This cave replays
 * the index computation with row clamped to [esi+0x388]-1 (gh-1) and col to [esi+0x384]-1 (gw-1).
 * SIMSPR-internal, so the two rel32s are constant regardless of load base - written in memory (the mod
 * patches nothing on disk). Fail-closed: verified against the shipped bytes before writing.
 * ⚠️ SCOPE: fixes FUN_1000cedb ONLY. FUN_1000d0f5 / FUN_1000be25 / FUN_1000ef50 share the same latent
 * OOB index math; if one of them faults on a later run, it needs the same clamp (or fix B). */
/* Each entry clamps one function's grid-B bucket index. All four inline the same OOB index math and
 * share no helper, so each needs its own cave (verify/resize_fix_a). The caves are SIMSPR-internal
 * (hook rel32 + one jmp-back rel32, both constant regardless of load base). Cave bytes assembled +
 * capstone-verified; each ends `jmp <back>` with the rel pre-baked for the shipped layout, so the
 * recipe is anchored implicitly - a mismatched hook byte aborts that entry (fail-closed). */
typedef struct { DWORD hook, cave, stolen; const BYTE *bytes; DWORD nbytes;
                 BYTE expect[5]; const char *name; } CLAMP;
static const BYTE CLAMP_CEDB[] = { /* 59, jmp 0x1000cfc3 */
 0x8b,0x45,0xfc,0x8b,0x8e,0x88,0x03,0x00,0x00,0x49,0x3b,0xc1,0x7e,0x02,0x8b,0xc1,0x8b,0x8e,0x8c,0x03,
 0x00,0x00,0xd3,0xe0,0x52,0x8b,0x55,0x0c,0x8b,0x8e,0x84,0x03,0x00,0x00,0x49,0x3b,0xd1,0x7e,0x02,0x8b,
 0xd1,0x03,0xc2,0x5a,0x8b,0x8e,0x80,0x03,0x00,0x00,0x80,0x7d,0x10,0x00,0xe9,0xa8,0xba,0xfa,0xff };
static const BYTE CLAMP_D0F5[] = { /* 52, jmp 0x1000d292 */
 0x8b,0x8e,0x88,0x03,0x00,0x00,0x49,0x3b,0xc1,0x7e,0x02,0x8b,0xc1,0x8b,0x8e,0x8c,0x03,0x00,0x00,0xd3,
 0xe0,0x52,0x8b,0x55,0xe4,0x8b,0x8e,0x84,0x03,0x00,0x00,0x49,0x3b,0xd1,0x7e,0x02,0x8b,0xd1,0x03,0xc2,
 0x5a,0x8b,0x8e,0x80,0x03,0x00,0x00,0xe9,0x3e,0xbd,0xfa,0xff };
static const BYTE CLAMP_BE25[] = { /* 55, jmp 0x1000c426 */
 0x8b,0x45,0xec,0x8b,0x8e,0x88,0x03,0x00,0x00,0x49,0x3b,0xc1,0x7e,0x02,0x8b,0xc1,0x8b,0x8e,0x8c,0x03,
 0x00,0x00,0xd3,0xe0,0x52,0x8b,0x55,0xe8,0x8b,0x8e,0x84,0x03,0x00,0x00,0x49,0x3b,0xd1,0x7e,0x02,0x8b,
 0xd1,0x03,0xc2,0x5a,0x8b,0x8e,0x80,0x03,0x00,0x00,0xe9,0x8f,0xae,0xfa,0xff };
/* ef50 is the odd one: this/base alias eax and a `push esi` shifts the args, so instead of
 * reimplementing through its ABSOLUTE `cmp [0x10072670]` (which would not survive relocation), the
 * cave clamps the two incoming params IN PLACE on the stack at entry (this=ecx live), then re-execs
 * the 3 stolen instrs and lets the original code (incl. its own relocated cmp) run. 46, jmp 0x1000ef57. */
static const BYTE CLAMP_EF50[] = {
 0x8b,0x81,0x88,0x03,0x00,0x00,0x48,0x39,0x44,0x24,0x08,0x7e,0x04,0x89,0x44,0x24,0x08,0x8b,0x81,0x84,
 0x03,0x00,0x00,0x48,0x39,0x44,0x24,0x04,0x7e,0x04,0x89,0x44,0x24,0x04,0x8b,0x54,0x24,0x08,0x8b,0xc1,
 0x56,0xe9,0x89,0xd9,0xfa,0xff };
/* FIX C (2026-08-31, verify/resize_hudlab): FUN_1000efa1, the grid-B node REMOVE, dereferences the
 * NULL list terminator. Caught in-game: 0xC0000005 READ at 0x00000004, eax=0, at BOTH unlink sites.
 *
 *   0efc0  test eax,eax / je 0x1000efe3     ; EMPTY BUCKET -> jumps straight into the deref
 *   0efd4  jne 0x1000efc5                   ; walk exits with eax == 0 when NOT FOUND
 *   0efdb  mov ecx,[eax+4]                  ; <<< faulted (not found, prev != 0)
 *   0efe3  mov edx,[eax+4]                  ; <<< faulted (empty bucket, or not found w/ no prev)
 *   0efe8  test eax,eax                     ; the author DOES null-check eax - one site too late
 *
 * The resize exposes it because the caller FUN_1000f122 computes the bucket from the LIVE extent
 * origin (this+0x54/+0x58) and scale (this+0x39c/+0x3a0) - the exact fields step 1 rewrites - so
 * nodes inserted under the OLD geometry hash to DIFFERENT buckets. Remove then searches a list the
 * node is not in and walks off its end. Measured that run: 86 live nodes, 0 dangling - the list is
 * intact, the lookup is in the wrong list. Same class as FIX A: a latent missing guard, harmless at
 * a fixed extent, exposed the moment the view geometry changes.
 * [CONFIRMED @ SIMSPR 0x1000efa1, caller 0x1000f122]
 *
 * Skipping the unlink when the node is absent is the CORRECT SEMANTIC, not crash suppression: there
 * is nothing in that bucket to remove. Two parts, both SIMSPR-internal and base-invariant:
 *   (1) this cave, hooked at 0xefd6, adds the missing `test eax,eax` before the unlink;
 *   (2) patch_efa1_emptybucket below retargets the empty-bucket branch (2 bytes, in place).
 * Cave assembled + capstone-verified at its load address; all three targets checked. */
static const BYTE GUARD_EFA1[] = {   /* 22, pop esi / test eax,eax / je 0xeff9 / test edx,edx /
                                        je 0xefe3 / jmp 0xefdb */
 0x5e,0x85,0xc0,0x0f,0x84,0x10,0xda,0xfa,0xff,0x85,
 0xd2,0x0f,0x84,0xf2,0xd9,0xfa,0xff,0xe9,0xe5,0xd9,
 0xfa,0xff };
static const CLAMP g_clamps[] = {
 { 0xcfab, 0x614e0, 24, CLAMP_CEDB, sizeof(CLAMP_CEDB), {0x8b,0x45,0xfc,0x8b,0x8e}, "FUN_1000cedb" },
 { 0xd281, 0x61520, 17, CLAMP_D0F5, sizeof(CLAMP_D0F5), {0x8b,0x8e,0x8c,0x03,0x00}, "FUN_1000d0f5" },
 { 0xc412, 0x61560, 20, CLAMP_BE25, sizeof(CLAMP_BE25), {0x8b,0x45,0xec,0x8b,0x8e}, "FUN_1000be25" },
 { 0xef50, 0x615a0,  7, CLAMP_EF50, sizeof(CLAMP_EF50), {0x8b,0x54,0x24,0x08,0x8b}, "FUN_1000ef50" },
 { 0xefd6, 0x615e0,  5, GUARD_EFA1, sizeof(GUARD_EFA1), {0x85,0xd2,0x5e,0x74,0x08}, "FUN_1000efa1" },
};

/* FIX C part 2: the empty-bucket branch at 0xefc2 (`je 0x1000efe3`) jumps directly into the NULL
 * deref. Retarget it to the function's ret at 0x1000eff9 - an empty bucket has nothing to unlink.
 * Two bytes, same instruction length, in place, no cave: rel8 = 0xeff9 - 0xefc4 = 0x35. The
 * empty-bucket path never executed `push esi` (that is at 0xefc4, after the branch), and the
 * original reached 0xeff9 without a pop either, so the stack is balanced. Fail-closed on the
 * shipped bytes. */
static void patch_efa1_emptybucket(HMODULE ss) {
    BYTE *site = (BYTE *)ss + 0xefc2;
    DWORD old;
    if (IsBadReadPtr(site, 2) || site[0] != 0x74 || site[1] != 0x1f) {
        logf("--- EFA1_GUARD: empty-bucket site 0xefc2 mismatch (%02X %02X) - NOT patching",
             IsBadReadPtr(site, 2) ? 0 : site[0], IsBadReadPtr(site, 2) ? 0 : site[1]);
        return;
    }
    if (!VirtualProtect(site, 2, PAGE_EXECUTE_READWRITE, &old)) {
        logf("--- EFA1_GUARD: VirtualProtect failed (%lu)", GetLastError()); return;
    }
    site[1] = 0x35;                      /* je 0x1000efe3 -> je 0x1000eff9 */
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    FlushInstructionCache(GetCurrentProcess(), site, 2);
    logf("--- EFA1_GUARD: empty-bucket branch 0xefc2 retargeted to the ret (was -> 0xefe3 deref)");
}

/* ================= DIRTGUARD (2026-10-09)
 * SIMDIRT FUN_10013556 (sc3_dirt_render_gouraudpoly_flat, cdecl, 10 args) fills terrain polygons into the
 * surface it is handed, through the pixel pointer from surface vt+0x1a8, stored at 0x10013A8F
 * (`mov word ptr [ecx], ax`). That store faulted on the Europolis 1024 city one second after a maximize
 * (owner, ECX=0x18604496, Apps\SC3U_stkdmp.txt 2026-10-09 15:17) and at the same address on 2026-08-21,
 * when the cause was the surface lock not taken (LAUNCH_CONTROL.md 33.2 defect 5). 29 maximize/restore
 * cycles with the sim running and a per-store bounds probe (6.4M stores) found no out-of-surface store, so
 * the trigger is a rare timing case not yet isolated.
 * Guard: the entry (`mov eax, imm32`, the EH_prolog frame address) is replaced by a JMP to dirt_guard, which
 * runs the original through a trampoline inside __try. An access violation drops that one polygon instead
 * of killing the game: the faulting store did not happen, so nothing was overwritten. The function holds a
 * lock (global 0x100249f0) through a guard object in its own EH frame; SEH unwinding runs that frame's
 * handler, which releases it (checked with a forced fault). The first 20 faults are logged with the
 * surface, its pixel pointer and the rectangles, for the root cause. SC3RESIZE_DIRTGUARD=0 disables.
 * Root cause found 2026-10-11 and fixed by CELLFIX + DIRTCLIP below (dirty-grid cells past the view); this guard
 * stays on as the fallback. */
static int g_dirtguard = 1;
static BYTE *g_dirt_tramp;
static volatile LONG g_dirt_faults;
typedef void (__cdecl *DIRT_RAST)(void *, int *, int *, DWORD, short *, int, int, int, DWORD, int);

static int dirt_filter(EXCEPTION_POINTERS *ep, void *srf, int *r2, int *r3, short *v) {
    LONG n;
    if (ep->ExceptionRecord->ExceptionCode != EXCEPTION_ACCESS_VIOLATION) return EXCEPTION_CONTINUE_SEARCH;
    n = InterlockedIncrement(&g_dirt_faults);
    if (n <= 20) {
        DWORD addr = ep->ExceptionRecord->NumberParameters > 1 ? (DWORD)ep->ExceptionRecord->ExceptionInformation[1] : 0;
        LONG R[4] = {0, 0, 0, 0}, C[4] = {-1, -1, -1, -1}, w = -1, h = -1;
        DWORD bits = 0, pitch = 0;
        if (r2 && !IsBadReadPtr(r2, 16)) memcpy(R, r2, 16);
        if (r3 && !IsBadReadPtr(r3, 16)) memcpy(C, r3, 16);
        if (srf && !IsBadReadPtr(srf, 0x2c)) {
            DWORD *vt = *(DWORD **)srf;
            w = ((LONG *)srf)[0x24 / 4]; h = ((LONG *)srf)[0x28 / 4];
            if (vt && !IsBadReadPtr(vt, 0x1b0)) {
                bits = rz_thiscall_ret(srf, (void *)vt[0x1a8 / 4], NULL, 0);
                pitch = rz_thiscall_ret(srf, (void *)vt[0x1ac / 4], NULL, 0);
            }
        }
        logf("DIRTGUARD> fault #%ld at 0x%08lX writing 0x%08lX: surface 0x%08lX %ldx%ld bits 0x%08lX pitch %lu "
             "rect [%ld %ld %ld %ld] clip [%ld %ld %ld %ld] v0 (%d,%d) - polygon dropped",
             n, (DWORD)ep->ExceptionRecord->ExceptionAddress, addr, (DWORD)srf, w, h, bits, pitch,
             R[0], R[1], R[2], R[3], C[0], C[1], C[2], C[3],
             v && !IsBadReadPtr(v, 4) ? v[0] : 0, v && !IsBadReadPtr(v, 4) ? v[1] : 0);
    }
    return EXCEPTION_EXECUTE_HANDLER;
}

static void __cdecl dirt_guard(void *srf, int *r2, int *r3, DWORD shape, short *v, int a6, int a7, int a8, DWORD a9, int a10) {
    __try {
        ((DIRT_RAST)(void *)g_dirt_tramp)(srf, r2, r3, shape, v, a6, a7, a8, a9, a10);
    } __except (dirt_filter(GetExceptionInformation(), srf, r2, r3, v)) {
    }
}

/* Second level: the per-tile terrain draw FUN_10012cb7 (sc3_dirt_draw_dispatch, thiscall, 6 args, ret 0x18;
 * vtable slot +0x40 shared by all six terrain classes, called per tile from SIMSPR FUN_1000dc17). A forced
 * fault (surface pixel pointer replaced with a read-only page) landed in the depth-tested sibling rasterizer
 * FUN_100148d7, outside the first guard; the August crash log also has SIMDIRT 0x11EAB/0x12EC2/0x4AE1. Guarding
 * the dispatch covers every rasterizer: a fault skips that tile for that frame. */
static BYTE *g_dirt_tramp2;
static volatile LONG g_dirt_faults2;
typedef void (__fastcall *DIRT_DISPATCH)(void *self, void *edx, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD);

static int dirt_filter2(EXCEPTION_POINTERS *ep, DWORD x, DWORD y) {
    LONG n;
    if (ep->ExceptionRecord->ExceptionCode != EXCEPTION_ACCESS_VIOLATION) return EXCEPTION_CONTINUE_SEARCH;
    n = InterlockedIncrement(&g_dirt_faults2);
    if (n <= 20)
        logf("DIRTGUARD> tile fault #%ld at 0x%08lX writing 0x%08lX (tile args %lu,%lu) - tile skipped this frame", n,
             (DWORD)ep->ExceptionRecord->ExceptionAddress,
             ep->ExceptionRecord->NumberParameters > 1 ? (DWORD)ep->ExceptionRecord->ExceptionInformation[1] : 0, x, y);
    return EXCEPTION_EXECUTE_HANDLER;
}

static void __fastcall dirt_dispatch_guard(void *self, void *edx, DWORD a1, DWORD a2, DWORD a3, DWORD a4, DWORD a5, DWORD a6) {
    (void)edx;
    __try {
        ((DIRT_DISPATCH)(void *)g_dirt_tramp2)(self, NULL, a1, a2, a3, a4, a5, a6);
    } __except (dirt_filter2(GetExceptionInformation(), a2, a3)) {
    }
}

static void patch_dirtguard(HMODULE dm) {
    BYTE *f = (BYTE *)dm + 0x13556;
    DWORD old;
    if (!g_dirtguard) { logf("--- DIRTGUARD: disabled (SC3RESIZE_DIRTGUARD=0)"); return; }
    /* b8 <imm32 = SIMDIRT+0x1ecf3, relocated>  e8 <rel32 -> SIMDIRT+0x1e280 (__EH_prolog)> */
    if (f[0] != 0xb8 || *(DWORD *)(f + 1) != (DWORD)dm + 0x1ecf3 || f[5] != 0xe8 ||
        (DWORD)(f + 10) + *(DWORD *)(f + 6) != (DWORD)dm + 0x1e280) {
        logf("--- DIRTGUARD: SIMDIRT+0x13556 differs from shipped - not installed");
        return;
    }
    g_dirt_tramp = (BYTE *)VirtualAlloc(NULL, 16, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!g_dirt_tramp) return;
    memcpy(g_dirt_tramp, f, 5);                                            /* mov eax, imm32 (already relocated) */
    g_dirt_tramp[5] = 0xE9; *(DWORD *)(g_dirt_tramp + 6) = (DWORD)(f + 5) - (DWORD)(g_dirt_tramp + 10);
    if (!VirtualProtect(f, 5, PAGE_EXECUTE_READWRITE, &old)) return;
    f[0] = 0xE9; *(DWORD *)(f + 1) = (DWORD)dirt_guard - (DWORD)(f + 5);
    FlushInstructionCache(GetCurrentProcess(), f, 5);
    logf("--- DIRTGUARD: terrain polygon fill (SIMDIRT+0x13556) runs under an access-violation guard");
    {   static const BYTE pro[] = { 0x55, 0x8b, 0xec, 0x83, 0xec, 0x10 };   /* push ebp / mov ebp,esp / sub esp,0x10 */
        BYTE *d = (BYTE *)dm + 0x12cb7;
        if (memcmp(d, pro, sizeof(pro))) { logf("--- DIRTGUARD: SIMDIRT+0x12cb7 differs from shipped - tile guard not installed"); return; }
        g_dirt_tramp2 = (BYTE *)VirtualAlloc(NULL, 16, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
        if (!g_dirt_tramp2) return;
        memcpy(g_dirt_tramp2, d, 6);
        g_dirt_tramp2[6] = 0xE9; *(DWORD *)(g_dirt_tramp2 + 7) = (DWORD)(d + 6) - (DWORD)(g_dirt_tramp2 + 11);
        if (!VirtualProtect(d, 6, PAGE_EXECUTE_READWRITE, &old)) return;
        d[0] = 0xE9; *(DWORD *)(d + 1) = (DWORD)dirt_dispatch_guard - (DWORD)(d + 5); d[5] = 0x90;
        FlushInstructionCache(GetCurrentProcess(), d, 6);
        logf("--- DIRTGUARD: per-tile terrain draw (SIMDIRT+0x12cb7) runs under an access-violation guard");
    }
}

static DWORD WINAPI dirtguard_watcher(LPVOID p) {
    HMODULE dm = NULL;
    int ms = 0;
    (void)p;
    while (!(dm = GetModuleHandleA("SIMDIRT.DLL")) && ms++ < 3000) Sleep(100);
    if (dm) patch_dirtguard(dm); else logf("--- DIRTGUARD: SIMDIRT.DLL never loaded");
    return 0;
}

/* ================= DIRTCLIP + CELLFIX (2026-10-11): the root cause behind DIRTGUARD
 * Reproduced with DIRTGUARD off on the Europolis 1024 city, sim running, 7th maximize (re/tools/dirtprobe.py,
 * re/analysis/DIRTCRASH.md): the faulting terrain tile drew with clip [1672 984 1680 988] into the render
 * target iso+0x74 allocated 1680x987 (979 + RZ_SURFACE_SLACK), lock depth 1, and the write landed on row 987,
 * the first row past the allocation. Mechanism, all SIMSPR:
 *   - FUN_100059fb picks the dirty-grid cell COUNT: a table for 640/800/1024/1152/1280 widths and
 *     480/600/768/864/1024 heights, otherwise the first even count 12..24 that divides the size, else 8.
 *     979 is odd, so the count is 8.  [CONFIRMED @ 0x100059fb]
 *   - FUN_1000e2c0 sets the cell SIZE = extent / count, truncated: 979 / 8 = 122, so the grid covers 976 rows.
 *     [CONFIRMED @ 0x1000e2c0, iso+0x374 / +0x378]
 *   - FUN_1000d725 (iso vt+0x130, dirty-rect intake) maps rows 976..978 to cell row (978 / 122) = 8 of an
 *     8-row grid: it sets the grid byte one row past the gw*gh allocation (iso+0x360) and passes the cell rect
 *     rows 976..1098 to FUN_1000d0c5, which builds display items as (object rect) AND (cell rect), never
 *     clipped to the view.  [CONFIRMED @ 0x1000d9a2..0x1000d9f1]
 *   - FUN_1000dc17 draws those items with the item rect as the rasterizer clip, so a terrain polygon below the
 *     view writes past the surface end. It faults only when the write crosses into an unmapped page, which is
 *     why it is rare. The shipped game never meets this: its window sizes are all table sizes.
 * CELLFIX: after the resize's FUN_1000e2c0 call, round the cell size UP, so (size - 1) / cell < count and no
 * index leaves the grid. DIRTCLIP: at FUN_1000d0c5 entry, clamp the cell rect to the view rect iso+0x64 (the
 * rect FUN_1000d725 already intersects every incoming rect with) and skip an empty one, so nothing is drawn
 * outside the view whatever the cell math. SC3RESIZE_CELLFIX=0 / SC3RESIZE_DIRTCLIP=0 turn them off. */
static int g_cellfix = 1, g_dirtclip = 1;
static DWORD g_d0c5_ret;                 /* SIMSPR+0xd0cb, after the 6 stolen prologue bytes */
static volatile LONG g_dirtclip_n, g_dirtclip_skip;

static int __cdecl dirtclip_rect(DWORD iso, LONG *r) {
    const LONG *v = (const LONG *)(iso + 0x64);
    LONG n;
    if (v[2] <= v[0] || v[3] <= v[1]) return 1;   /* no view rect yet: leave the call alone */
    if (r[0] >= v[0] && r[1] >= v[1] && r[2] <= v[2] && r[3] <= v[3]) return 1;
    n = InterlockedIncrement(&g_dirtclip_n);
    if (n <= 10 || (n & 0x3ff) == 0)
        logf("DIRTCLIP> #%ld cell rect [%ld %ld %ld %ld] outside view [%ld %ld %ld %ld] (cell %lux%lu, grid %lux%lu) - clamped",
             n, r[0], r[1], r[2], r[3], v[0], v[1], v[2], v[3],
             *(DWORD *)(iso + 0x374), *(DWORD *)(iso + 0x378), *(DWORD *)(iso + 0x364), *(DWORD *)(iso + 0x368));
    if (r[0] < v[0]) r[0] = v[0];
    if (r[1] < v[1]) r[1] = v[1];
    if (r[2] > v[2]) r[2] = v[2];
    if (r[3] > v[3]) r[3] = v[3];
    if (r[2] <= r[0] || r[3] <= r[1]) { InterlockedIncrement(&g_dirtclip_skip); return 0; }
    return 1;
}

/* FUN_1000d0c5 is __thiscall(iso, RECT *cell, int), ret 8. Both callers (0x1000d97e, 0x1000d9f1) pass a local
 * rect they rebuild before every call, so clamping it in place is safe. */
static __declspec(naked) void dirtclip_stub(void) {
    __asm {
        pushad
        push dword ptr [esp + 32 + 4]   /* RECT* */
        push ecx                        /* iso */
        call dirtclip_rect
        add  esp, 8
        test eax, eax
        popad                           /* POPAD leaves the flags alone */
        jz   dc_skip
        push ebp                        /* the 6 stolen bytes: push ebp / mov ebp,esp / push esi / mov esi,ecx */
        mov  ebp, esp
        push esi
        mov  esi, ecx
        jmp  dword ptr [g_d0c5_ret]
    dc_skip:
        ret  8
    }
}

static void patch_dirtclip(HMODULE ss) {
    static const BYTE pro[] = { 0x55, 0x8b, 0xec, 0x56, 0x8b, 0xf1 };
    BYTE *f = (BYTE *)ss + 0xd0c5;
    DWORD old;
    if (!g_dirtclip) { logf("--- DIRTCLIP: disabled (SC3RESIZE_DIRTCLIP=0)"); return; }
    if (memcmp(f, pro, sizeof(pro))) { logf("--- DIRTCLIP: SIMSPR+0xd0c5 differs from shipped - not installed"); return; }
    g_d0c5_ret = (DWORD)f + sizeof(pro);
    if (!VirtualProtect(f, sizeof(pro), PAGE_EXECUTE_READWRITE, &old)) return;
    f[0] = 0xE9; *(DWORD *)(f + 1) = (DWORD)dirtclip_stub - (DWORD)(f + 5); f[5] = 0x90;
    FlushInstructionCache(GetCurrentProcess(), f, sizeof(pro));
    logf("--- DIRTCLIP: dirty-cell rects clamped to the view at SIMSPR+0xd0c5 (terrain never drawn past the surface)");
}

/* LCENTER (task leftclick, owner 2026-10-12: "el click izquierdo en el mapa para desplazarse no se adapta a la ventana").
 * A left click on the map (default tool, SIMSPR FUN_10043540), a left-drag (one call on the press) and a minimap click
 * (SIMUI+0x5090c) all call cISC3CityViewIso vt+0x54 = SIMSPR FUN_1001d039 CenterOnTile(tx, ty, flag). It puts the tile at
 * world - (+0x20 >> 1, +0x24 >> 1) [CONFIRMED @ SIMSPR 0x1001d09c], and +0x20/+0x24 is the stored 704x544 that the
 * resize never changes, so at any size the tile lands at view point (352, 272): maximized at 1680x979 a click on the
 * map-area centre moved the camera (+448, +192) (verify/leftclick/PRE.md). The stub subtracts half the VISIBLE map area
 * instead: right = the docked side panel's left edge, bottom = the bar's top, else stored size + (client - 800x600)
 * (sc3overscroll true_center's rule); with HUDSCALE on, the edges the enlarged HUD covers. At 800x600 it is stock.
 * SC3RESIZE_LCENTER=0 leaves the function alone. */
static int g_lcenter = 1;
static DWORD g_d09c_ret;                 /* SIMSPR+0x1d0b5, after the 25 stolen bytes */
static volatile LONG g_lcenter_n;

static void rz_lcenter_area(LONG cw, LONG ch, LONG w0, LONG h0, LONG *w, LONG *h) {
    LONG ax1 = -1, ay1 = -1;
    *w = w0; *h = h0;
    if (cw <= 0 || ch <= 0 || (cw == NAT_W && ch == NAT_H)) return;
    if (g_side_top && !IsBadReadPtr(g_side_top, 0x24)) {
        LONG sx = ((LONG *)((DWORD)g_side_top + 0x14))[0];
        if (sx > cw / 2 && sx < cw) ax1 = sx;
    }
    if (g_hud_top && !IsBadReadPtr(g_hud_top, 0x24)) {
        LONG by = ((LONG *)((DWORD)g_hud_top + 0x14))[1];
        if (by > ch / 2 && by < ch) ay1 = by;
    }
    if (ax1 < 0) ax1 = w0 + (cw - NAT_W);
    if (ay1 < 0) ay1 = h0 + (ch - NAT_H);
    if (g_hudscale && g_hs_n > 0 && g_hs_s > 1.0 && g_hs_cw == cw && g_hs_ch == ch) {   /* enlarged about the corner */
        ax1 = cw - (LONG)(g_hs_s * (double)(cw - ax1) + 0.5);
        ay1 = ch - (LONG)(g_hs_s * (double)(ch - ay1) + 0.5);
    }
    if (ax1 < 64 || ay1 < 64) return;
    *w = ax1; *h = ay1;
}

static void __stdcall lcenter_sub(BYTE *view, LONG *wx, LONG *wy) {
    LONG w0 = *(LONG *)(view + 0x20), h0 = *(LONG *)(view + 0x24), w, h, cw = 0, ch = 0, n;
    RECT rc;
    if (g_hwnd && GetClientRect(g_hwnd, &rc)) { cw = rc.right - rc.left; ch = rc.bottom - rc.top; }
    rz_lcenter_area(cw, ch, w0, h0, &w, &h);
    if (g_cz_f > 1) { w /= g_cz_f; h /= g_cz_f; }   /* task cityzoom: in view pixels */
    *wx -= (LONG)((DWORD)w >> 1);
    *wy -= (LONG)((DWORD)h >> 1);
    n = InterlockedIncrement(&g_lcenter_n);
    if (n <= 12 || (n & 0x3f) == 0)
        logf("LCENTER> #%ld tile (%ld,%ld) centred on the map area %ldx%ld (stored %ldx%ld, client %ldx%ld)",
             n, *(LONG *)(view + 0xb0), *(LONG *)(view + 0xb4), w, h, w0, h0, cw, ch);
}

/* Replaces SIMSPR 0x1001d09c..0x1001d0b4: mov eax,[esi+20h] / push [ebp+10h] / shr eax,1 / sub [ebp-8],eax /
 * mov eax,[esi+24h] / mov ecx,[esi+158h] / shr eax,1 / sub [ebp-4],eax. esi = the view, [ebp-8]/[ebp-4] = the tile's
 * world position. The code after it reloads eax from [ecx], so eax is free. */
static __declspec(naked) void lcenter_stub(void) {
    __asm {
        pushad
        lea  eax, [ebp-4]
        push eax
        lea  eax, [ebp-8]
        push eax
        push esi
        call lcenter_sub
        popad
        push dword ptr [ebp+10h]
        mov  ecx, [esi+158h]
        jmp  dword ptr [g_d09c_ret]
    }
}

static void patch_lcenter(HMODULE ss) {
    static const BYTE orig[25] = { 0x8b, 0x46, 0x20, 0xff, 0x75, 0x10, 0xd1, 0xe8, 0x29, 0x45, 0xf8, 0x8b, 0x46,
                                   0x24, 0x8b, 0x8e, 0x58, 0x01, 0x00, 0x00, 0xd1, 0xe8, 0x29, 0x45, 0xfc };
    BYTE *f = (BYTE *)ss + 0x1d09c;
    DWORD old;
    int i;
    if (!g_lcenter) { logf("--- LCENTER: disabled (SC3RESIZE_LCENTER=0) - clicks centre on the stored 704x544"); return; }
    if (memcmp(f, orig, sizeof(orig))) { logf("--- LCENTER: SIMSPR+0x1d09c differs from shipped - not installed"); return; }
    g_d09c_ret = (DWORD)f + sizeof(orig);
    if (!VirtualProtect(f, sizeof(orig), PAGE_EXECUTE_READWRITE, &old)) return;
    f[0] = 0xE9; *(DWORD *)(f + 1) = (DWORD)lcenter_stub - (DWORD)(f + 5);
    for (i = 5; i < (int)sizeof(orig); i++) f[i] = 0x90;
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    FlushInstructionCache(GetCurrentProcess(), f, sizeof(orig));
    logf("--- LCENTER: lcenter=1, CenterOnTile centres on the visible map area (SIMSPR+0x1d09c)");
}

/* TIPCURSOR (task toolicon, owner 2026-10-12: "el ícono de la herramienta seleccionada está renderizando sobre el valor
 * de lo que estoy construyendo"). The cost label next to the cursor is the game's tooltip window (SC3U class 0x4d3bcc),
 * placed centred 2 px below an anchor box. The city view builds that box as [mx, my, mx+0x2c, my+0x2c] from the mouse
 * point (view +0x204/+0x208), or [mx-0x2c, my-0x20, mx, my] when the box leaves the view [CONFIRMED @ SIMSPR
 * 0x1004a3d7, the immediates at 0x1004a47b/0x1004a486/0x1004a4d5/0x1004a4e0], and posts it with message 0x22c010d0
 * [CONFIRMED @ SC3U 0x00443952 -> 0x00443aba -> 0x004430f3]. 0x2c = a 32 px cursor + 12. The tool cursors are 32x32
 * .cur files with the hotspot at (0,0), but Windows draws them at the accessibility pointer size: on the owner's PC
 * (CursorBaseSize 80, pointer size 4, 125%) the road cursor is drawn 80x80 physical, measured with DXGI desktop
 * duplication both DPI-aware and unaware, so the label at +46 sits inside the icon (verify/toolicon/RESULTS.md). That is
 * stock behaviour at that pointer size; per-monitor DPI awareness only moves the label 11 px closer (46 vs 57.5).
 * Fix: the same box sized from the drawn pointer, B = pointer / (physical px per game px) + 12; when the box leaves the
 * view, the label goes above-left of the cursor instead of onto its hotspot. At the default pointer size B = 44 and the
 * flip is the shipped one, so the stock layout is unchanged.
 * Pointer size = max(HKCU\Control Panel\Cursors CursorBaseSize, SM_CYCURSOR at the monitor dpi). Measured only at dpi
 * 120 with base 80 (drawn 80); other dpi/size pairs are [UNCERTAIN] (UNCERTAINTIES.md), SC3RESIZE_TIPCURSOR_PX=<n> sets
 * the pointer size by hand. SC3RESIZE_TIPCURSOR=0 leaves the game code alone. */
static int g_tipcursor = 1, g_tipcursor_px;
static DWORD g_tip_ret1, g_tip_ret2;     /* SIMSPR+0x4a495, +0x4a4ef */
static LONG g_tip_box = 0x2c, g_tip_uptop = 0x20, g_tip_upbot = 0;   /* shipped values until the first update */
static DWORD g_tip_tick;
static LONG g_tip_logged = -1;

static void __stdcall tip_update(void) {
    typedef LONG (WINAPI *REGGET)(HKEY, LPCSTR, LPCSTR, DWORD, LPDWORD, PVOID, LPDWORD);
    typedef LONG (WINAPI *MONDPI)(HMONITOR, int, UINT *, UINT *);
    typedef HANDLE (WINAPI *SETCTX)(HANDLE);
    static REGGET rg; static MONDPI md; static SETCTX sc; static RZ_DPIWIN dw; static RZ_SMFORDPI sm; static int init;
    DWORD now = GetTickCount(), base = 32, cb = sizeof(base);
    UINT mdx = 96, mdy = 96, wdpi = 96;
    LONG ptr, box;
    double scale;
    if (g_tip_tick && now - g_tip_tick < 1000) return;   /* settings can change while playing: re-read once a second */
    g_tip_tick = now ? now : 1;
    if (!init) {
        HMODULE u = GetModuleHandleA("user32.dll"), a = LoadLibraryA("advapi32.dll"), sh = LoadLibraryA("shcore.dll");
        init = 1;
        rg = a ? (REGGET)GetProcAddress(a, "RegGetValueA") : NULL;
        md = sh ? (MONDPI)GetProcAddress(sh, "GetDpiForMonitor") : NULL;
        sc = (SETCTX)GetProcAddress(u, "SetThreadDpiAwarenessContext");
        dw = (RZ_DPIWIN)GetProcAddress(u, "GetDpiForWindow");
        sm = (RZ_SMFORDPI)GetProcAddress(u, "GetSystemMetricsForDpi");
    }
    if (rg && rg(HKEY_CURRENT_USER, "Control Panel\\Cursors", "CursorBaseSize", 0x18 /* RRF_RT_REG_DWORD */, NULL,
                 &base, &cb) != ERROR_SUCCESS) base = 32;
    if (g_hwnd) {
        HANDLE prev = sc ? sc((HANDLE)(LONG_PTR)-4) : NULL;   /* per-monitor v2 for this query: an unaware thread reads 96 */
        if (md) md(MonitorFromWindow(g_hwnd, MONITOR_DEFAULTTONEAREST), 0, &mdx, &mdy);
        if (prev) sc(prev);
        if (dw) wdpi = dw(g_hwnd);   /* 96 for an unaware window (game px are logical), the monitor dpi when aware */
    }
    if (!mdy) mdy = 96;
    if (!wdpi) wdpi = 96;
    ptr = (LONG)base;
    if (sm && (LONG)sm(SM_CYCURSOR, mdy) > ptr) ptr = sm(SM_CYCURSOR, mdy);
    if (g_tipcursor_px > 0) ptr = g_tipcursor_px;
    scale = (double)mdy / (double)wdpi;                    /* physical px per game px */
    if (scale < 1.0) scale = 1.0;
    box = (LONG)((double)ptr / scale + 0.999) + 12;
    {   /* task uiscale: clearance for the enlarged label. The drawn size is measured only at (base 80, dpi 120): take
           the larger of the pointer above and the base size scaled to the monitor dpi, so the label errs clear. */
        LONG big = (LONG)((double)base * mdy / 96.0 + 0.5);
        g_tip_clr = (LONG)((double)(big > ptr ? big : ptr) / scale + 0.999);
    }
    if (box <= 0x2c) { g_tip_box = 0x2c; g_tip_uptop = 0x20; g_tip_upbot = 0; }          /* shipped */
    else             { g_tip_box = box;  g_tip_uptop = 36;   g_tip_upbot = 20; }          /* label above-left */
    if (g_tip_logged != g_tip_box) {
        g_tip_logged = g_tip_box;
        logf("TIPCURSOR> pointer %ld px (CursorBaseSize %lu%s), monitor dpi %u, window dpi %u -> anchor box %ld game px%s, enlarged label clearance %ld game px",
             ptr, base, g_tipcursor_px > 0 ? ", SC3RESIZE_TIPCURSOR_PX" : "", mdy, wdpi, g_tip_box,
             g_tip_box == 0x2c ? " (shipped)" : "", g_tip_clr);
    }
}

/* Replaces SIMSPR 0x1004a475..0x1004a494 (mov ecx,[ebx+208h] / lea edx,[eax+2Ch] / mov [esi],eax / mov [ebx+14Ch],ecx /
 * lea edi,[ecx+2Ch] / mov [ebx+150h],edx / mov [ebx+154h],edi). eax = mx, ebx = the view, esi = ebx+148h. */
static __declspec(naked) void tip_stub1(void) {
    __asm {
        pushad
        call tip_update
        popad
        mov  ecx, [ebx+208h]
        mov  [g_tip_mx], eax          /* task uiscale: the label's cursor point */
        mov  [g_tip_my], ecx
        mov  dword ptr [g_tip_flip], 0
        mov  dword ptr [g_tip_seen], 1
        imul eax, dword ptr [g_cz_f]  /* task cityzoom: the box in client pixels (the view point is q / f); the flip */
        imul ecx, dword ptr [g_cz_f]  /* test and tip_stub2 read these registers next. g_tip_mx/my stay view pixels */
        mov  edx, eax
        add  edx, [g_tip_box]
        mov  [esi], eax
        mov  [ebx+14Ch], ecx
        mov  edi, ecx
        add  edi, [g_tip_box]
        mov  [ebx+150h], edx
        mov  [ebx+154h], edi
        jmp  dword ptr [g_tip_ret1]
    }
}

/* Replaces SIMSPR 0x1004a4d5..0x1004a4ee, the flip (lea edx,[eax-2Ch] / mov [ebx+150h],eax / mov [esi],edx /
 * lea edx,[ecx-20h] / mov [ebx+14Ch],edx / mov [ebx+154h],ecx). eax = mx, ecx = my; edx is dead after it. */
static __declspec(naked) void tip_stub2(void) {
    __asm {
        mov  dword ptr [g_tip_flip], 1   /* task uiscale */
        mov  [ebx+150h], eax
        mov  edx, eax
        sub  edx, [g_tip_box]
        mov  [esi], edx
        mov  edx, ecx
        sub  edx, [g_tip_uptop]
        mov  [ebx+14Ch], edx
        mov  edx, ecx
        sub  edx, [g_tip_upbot]
        mov  [ebx+154h], edx
        jmp  dword ptr [g_tip_ret2]
    }
}

static void patch_tipcursor(HMODULE ss) {
    static const BYTE o1[32] = { 0x8b, 0x8b, 0x08, 0x02, 0x00, 0x00, 0x8d, 0x50, 0x2c, 0x89, 0x06, 0x89, 0x8b, 0x4c, 0x01,
                                 0x00, 0x00, 0x8d, 0x79, 0x2c, 0x89, 0x93, 0x50, 0x01, 0x00, 0x00, 0x89, 0xbb, 0x54, 0x01,
                                 0x00, 0x00 };
    static const BYTE o2[26] = { 0x8d, 0x50, 0xd4, 0x89, 0x83, 0x50, 0x01, 0x00, 0x00, 0x89, 0x16, 0x8d, 0x51, 0xe0, 0x89,
                                 0x93, 0x4c, 0x01, 0x00, 0x00, 0x89, 0x8b, 0x54, 0x01, 0x00, 0x00 };
    BYTE *f1 = (BYTE *)ss + 0x4a475, *f2 = (BYTE *)ss + 0x4a4d5;
    DWORD old;
    int i;
    if (!g_tipcursor) { logf("--- TIPCURSOR: disabled (SC3RESIZE_TIPCURSOR=0) - cost label 46 px below the cursor point"); return; }
    if (memcmp(f1, o1, sizeof(o1)) || memcmp(f2, o2, sizeof(o2))) {
        logf("--- TIPCURSOR: SIMSPR+0x4a475/+0x4a4d5 differ from shipped - not installed"); return;
    }
    g_tip_ret1 = (DWORD)f1 + sizeof(o1);
    g_tip_ret2 = (DWORD)f2 + sizeof(o2);
    if (!VirtualProtect(f1, 0x4a4ef - 0x4a475, PAGE_EXECUTE_READWRITE, &old)) return;
    f1[0] = 0xE9; *(DWORD *)(f1 + 1) = (DWORD)tip_stub1 - (DWORD)(f1 + 5);
    for (i = 5; i < (int)sizeof(o1); i++) f1[i] = 0x90;
    f2[0] = 0xE9; *(DWORD *)(f2 + 1) = (DWORD)tip_stub2 - (DWORD)(f2 + 5);
    for (i = 5; i < (int)sizeof(o2); i++) f2[i] = 0x90;
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    FlushInstructionCache(GetCurrentProcess(), f1, 0x4a4ef - 0x4a475);
    logf("--- TIPCURSOR: tipcursor=1, the cost label's anchor box follows the drawn pointer size (SIMSPR+0x4a475, +0x4a4d5)");
}

/* ZOOMCENTER (task leftclick, owner design call 2026-10-12: zoom centres on the map area like the left click).
 * The zoom keys and the rotate keys call the iso view's zoom in / zoom out / rotate methods (vtable 0x10063390 slots
 * +0x60 FUN_1001d2d6, +0x64 FUN_1001d365, +0x70 FUN_1001d3f3, +0x74 FUN_1001d47b); the generic set (+0x6c FUN_1001d1d9)
 * runs at city load. All pass the stored centre tile +0xb0/+0xb4 to the camera, which ends in FUN_10006752 (zoom) /
 * FUN_10006a55 (rotate). Both put that tile at world - (camera rect +0x64..+0x70) / 2 [CONFIRMED @ SIMSPR 0x1000688d,
 * 0x10006b0f], and that rect is the WHOLE client (800x600 stock, 1680x979 read live maximized), while the view's own
 * centre (CenterOnTile, Translate's pick) is the map area's: (352,272) at 800x600. Two changes: the two half-rect sites
 * use half the map area (rz_lcenter_area), and the four user methods are wrapped (vtable slots) so the stored tile is
 * first refreshed with the game's own pick (FUN_1000902f, mode 0 then 1, as Translate does) at the map-area centre: the
 * tile was stale after a window resize (measured). A failed pick (centre past the map edge) keeps the stored tile. The
 * load-time set is NOT refreshed: its tile is the saved city centre (refreshing it moved the loaded view, measured).
 * SC3RESIZE_ZOOMCENTER=0 stock; 1 (default) at every size; 2 only when the client is not 800x600. */
static int g_zoomcenter = 1;
static int g_zoomcenter_on(void) { return g_zoomcenter; }
static DWORD g_688d_ret, g_6b0f_ret, g_zc_orig[4];   /* original vt+0x60, +0x64, +0x70, +0x74 */
typedef int (__fastcall *PFN_RzPick)(void *, void *, int, int, DWORD *, DWORD *, int, int *, int);
static PFN_RzPick g_rz_pick;
static volatile LONG g_zc_n;

static int rz_zc_area(LONG *w, LONG *h) {   /* 0 = leave this call stock */
    RECT rc;
    LONG cw, ch;
    if (!g_zoomcenter || !g_hwnd || !GetClientRect(g_hwnd, &rc)) return 0;
    cw = rc.right - rc.left; ch = rc.bottom - rc.top;
    if (cw <= 0 || ch <= 0 || (g_zoomcenter == 2 && cw == NAT_W && ch == NAT_H)) return 0;
    rz_lcenter_area(cw, ch, NAT_W - 96, NAT_H - 56, w, h);   /* 704x544 = the view's stored size, read live */
    if (g_cz_f > 1) { *w /= g_cz_f; *h /= g_cz_f; }   /* task cityzoom: in view pixels */
    return 1;
}

/* task cityzoom: zoom in at zoom 4 goes to the next step (up to cz_max), zoom out above x1 to the step below. The
   poll applies it on the next frame. 1 = handled, the game's own zoom method is skipped (at zoom 4 it would do nothing). */
static int __stdcall cz_zoom(BYTE *view, int dir) {
    DWORD *cam;
    RECT rc;
    LONG mx, cur, was;
    if (!g_cz_mode || IsBadReadPtr(view, 0x160)) return 0;
    cam = *(DWORD **)(view + 0x158);
    if (!cam || IsBadReadPtr(cam, 0x30) || cam[0x28 / 4] != 4 || !g_hwnd || !GetClientRect(g_hwnd, &rc)) return 0;
    mx = cz_max(rc.right, rc.bottom);
    was = cur = g_cz_req;
    if (dir == 0) { if (cur >= mx) return 0; cur++; }
    else { if (cur <= 1) return 0; cur--; }
    InterlockedExchange(&g_cz_req, cur);
    logf("CITYZOOM> zoom %s at zoom 4: step x%ld -> x%ld (client %ldx%ld allows x%ld)", dir ? "out" : "in", was, cur,
         rc.right, rc.bottom, mx);
    return 1;
}

static int __stdcall zc_delta(DWORD *cam, LONG *xslot) {   /* returns the y delta, adds the x delta */
    LONG w, h;
    if (!rz_zc_area(&w, &h)) { w = (LONG)cam[0x6c / 4] - (LONG)cam[0x64 / 4]; h = (LONG)cam[0x70 / 4] - (LONG)cam[0x68 / 4]; }
    *xslot += w / -2;
    return h / -2;
}

static void __stdcall zc_refresh_tile(BYTE *view) {
    void *cam = IsBadReadPtr(view, 0x160) ? NULL : *(void **)(view + 0x158);
    LONG w, h, n;
    DWORD tx = 0, ty = 0, ox = *(DWORD *)(view + 0xb0), oy = *(DWORD *)(view + 0xb4);
    int ok;
    if (!cam || !g_rz_pick || !rz_zc_area(&w, &h)) return;
    ok = g_rz_pick(cam, NULL, w / 2, h / 2, &tx, &ty, 0, NULL, 0) & 0xff;
    if (!ok) ok = g_rz_pick(cam, NULL, w / 2, h / 2, &tx, &ty, 1, NULL, 0) & 0xff;
    if (ok) { *(DWORD *)(view + 0xb0) = tx; *(DWORD *)(view + 0xb4) = ty; }
    n = InterlockedIncrement(&g_zc_n);
    if (n <= 12 || (n & 0x3f) == 0)
        logf("ZOOMCENTER> #%ld zoom/rotate: map area %ldx%ld, centre tile %s (%lu,%lu) (stored was %lu,%lu)",
             n, w, h, ok ? "picked" : "not on the map, kept", ok ? tx : ox, ok ? ty : oy, ox, oy);
}

/* SIMSPR 0x1000688d..0x100068a4 (zoom) and 0x10006b0f..0x10006b26 (rotate): mov eax,[esi+6ch] / push -2 / sub eax,
 * [esi+64h] / pop ecx / cdq / idiv ecx / add [x],eax / mov eax,[esi+70h] / sub eax,[esi+68h] / cdq / idiv ecx. esi = the
 * camera, x = [ebp+8] (zoom) or [ebp+14h] (rotate). The code after it needs eax = the y delta; ecx/edx are reloaded. */
static __declspec(naked) void zc_zoom_stub(void) {
    __asm {
        pushad
        lea  eax, [ebp+8]
        push eax
        push esi
        call zc_delta
        mov  [esp+28], eax
        popad
        jmp  dword ptr [g_688d_ret]
    }
}
static __declspec(naked) void zc_rot_stub(void) {
    __asm {
        pushad
        lea  eax, [ebp+14h]
        push eax
        push esi
        call zc_delta
        mov  [esp+28], eax
        popad
        jmp  dword ptr [g_6b0f_ret]
    }
}
/* Wrappers for iso view vt+0x60/+0x64/+0x70/+0x74 (thiscall, no stack args; the originals read ebx, kept by pushad). */
#define ZC_WRAP(k) static __declspec(naked) void zc_wrap##k(void) { __asm { pushad } __asm { push ecx }     __asm { call zc_refresh_tile } __asm { popad } __asm { jmp dword ptr [g_zc_orig + 4 * k] } }
/* zoom in / out: task cityzoom first (cz_zoom), then the ZOOMCENTER wrapper */
static __declspec(naked) void zc_wrap0(void) {
    __asm {
        pushad
        push 0
        push ecx
        call cz_zoom
        test eax, eax
        jnz  zin_done
        popad
        pushad
        push ecx
        call zc_refresh_tile
        popad
        jmp  dword ptr [g_zc_orig + 0]
    zin_done:
        popad
        ret
    }
}
static __declspec(naked) void zc_wrap1(void) {
    __asm {
        pushad
        push 1
        push ecx
        call cz_zoom
        test eax, eax
        jnz  zout_done
        popad
        pushad
        push ecx
        call zc_refresh_tile
        popad
        jmp  dword ptr [g_zc_orig + 4]
    zout_done:
        popad
        ret
    }
}
ZC_WRAP(2)
ZC_WRAP(3)

static void rz_jmp_patch(BYTE *f, int len, void *to) {
    DWORD old;
    int i;
    if (!VirtualProtect(f, len, PAGE_EXECUTE_READWRITE, &old)) return;
    f[0] = 0xE9; *(DWORD *)(f + 1) = (DWORD)to - (DWORD)(f + 5);
    for (i = 5; i < len; i++) f[i] = 0x90;
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    FlushInstructionCache(GetCurrentProcess(), f, len);
}

/* DRAGANCHOR, part 2. A zoom ends the right-drag (SetDragMode off, measured: +0x1e6 0 right after it); with the button
   still held the game turns it on again with the PRESS point it kept (the owner's camera flew the other way after '+'
   during a right-drag). That point is in the view pixels of the factor at the press: when it comes back after a step,
   put it in the current factor's. Any other anchor passes as is. City view vtable 0x10067894 slot +0x3c = FUN_10042cfe
   (thiscall x, y, on). */
typedef void (__fastcall *CZ_SETDRAG)(void *, void *, int, int, int);
static CZ_SETDRAG g_cz_setdrag_orig;
static void __fastcall cz_setdrag(void *self, void *edx, int x, int y, int on) {
    (void)edx;
    if (on && g_cz_draganchor && g_cz_rpf > 0 && g_cz_rpf != g_cz_f && (short)x == (short)g_cz_rpx && (short)y == (short)g_cz_rpy) {
        int nx = (int)((LONG)(short)x * g_cz_rpf / g_cz_f), ny = (int)((LONG)(short)y * g_cz_rpf / g_cz_f);
        logf("DRAGANCHOR> drag restarted at the press point (%d,%d) taken at x%ld, now x%ld -> (%d,%d)", (short)x, (short)y,
             g_cz_rpf, g_cz_f, nx, ny);
        x = nx; y = ny;
    }
    g_cz_setdrag_orig(self, NULL, x, y, on);
}
static void patch_setdrag(HMODULE ss) {
    DWORD *slot = (DWORD *)((BYTE *)ss + 0x678d0), old;
    if (!g_cz_mode || !g_cz_draganchor) return;
    if (IsBadReadPtr(slot, 4) || *slot != (DWORD)ss + 0x42cfe) { logf("--- DRAGANCHOR: city view vt+0x3c is not FUN_10042cfe - not installed"); return; }
    if (!VirtualProtect(slot, 4, PAGE_EXECUTE_READWRITE, &old)) return;
    g_cz_setdrag_orig = (CZ_SETDRAG)*slot;
    *slot = (DWORD)cz_setdrag;
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    logf("--- DRAGANCHOR: city view SetDragMode (SIMSPR+0x42cfe, vt 0x10067894 +0x3c) wrapped: a right-drag keeps its anchor across zoom steps");
}

static void patch_zoomcenter(HMODULE ss) {
    static const BYTE zoom[24] = { 0x8b, 0x46, 0x6c, 0x6a, 0xfe, 0x2b, 0x46, 0x64, 0x59, 0x99, 0xf7, 0xf9,
                                   0x01, 0x45, 0x08, 0x8b, 0x46, 0x70, 0x2b, 0x46, 0x68, 0x99, 0xf7, 0xf9 };
    static const BYTE rot[24]  = { 0x8b, 0x46, 0x6c, 0x6a, 0xfe, 0x2b, 0x46, 0x64, 0x59, 0x99, 0xf7, 0xf9,
                                   0x01, 0x45, 0x14, 0x8b, 0x46, 0x70, 0x2b, 0x46, 0x68, 0x99, 0xf7, 0xf9 };
    static const DWORD slot[4] = { 0x633f0, 0x633f4, 0x63400, 0x63404 }, fn[4] = { 0x1d2d6, 0x1d365, 0x1d3f3, 0x1d47b };
    void (*wrap[4])(void) = { zc_wrap0, zc_wrap1, zc_wrap2, zc_wrap3 };
    BYTE *fz = (BYTE *)ss + 0x688d, *fr = (BYTE *)ss + 0x6b0f;
    DWORD old, *vt = (DWORD *)((BYTE *)ss + 0x633f0);
    int k;
    if (!g_zoomcenter) { logf("--- ZOOMCENTER: disabled (SC3RESIZE_ZOOMCENTER=0) - zoom/rotate centre on the whole window"); return; }
    for (k = 0; k < 4; k++)
        if (*(DWORD *)((BYTE *)ss + slot[k]) != (DWORD)ss + fn[k]) break;
    if (k < 4 || memcmp(fz, zoom, sizeof(zoom)) || memcmp(fr, rot, sizeof(rot))) {
        logf("--- ZOOMCENTER: SIMSPR+0x688d/+0x6b0f or iso vtable +0x60..+0x74 differ from shipped - not installed"); return;
    }
    g_rz_pick = (PFN_RzPick)((BYTE *)ss + 0x902f);
    g_688d_ret = (DWORD)fz + sizeof(zoom);
    g_6b0f_ret = (DWORD)fr + sizeof(rot);
    for (k = 0; k < 4; k++) g_zc_orig[k] = (DWORD)ss + fn[k];
    rz_jmp_patch(fz, sizeof(zoom), zc_zoom_stub);
    rz_jmp_patch(fr, sizeof(rot), zc_rot_stub);
    if (VirtualProtect(vt, 0x18, PAGE_EXECUTE_READWRITE, &old)) {
        for (k = 0; k < 4; k++) *(DWORD *)((BYTE *)ss + slot[k]) = (DWORD)wrap[k];
        (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    }
    logf("--- ZOOMCENTER: zoomcenter=%d, zoom/rotate keep the map-area centre tile (SIMSPR+0x688d, +0x6b0f, iso vt+0x60/64/70/74)%s",
         g_zoomcenter, g_zoomcenter == 2 ? ", stock at 800x600" : "");
}

/* CELLFIX: called by rz_do_resize right after FUN_1000e2c0. */
static void rz_cellfix(void *iso) {
    DWORD *v = (DWORD *)iso;
    LONG w = (LONG)v[0x5c / 4] - (LONG)v[0x54 / 4], h = (LONG)v[0x60 / 4] - (LONG)v[0x58 / 4];
    DWORD gw = v[0x364 / 4], gh = v[0x368 / 4], cw, ch;
    if (!g_cellfix || w <= 0 || h <= 0 || !gw || !gh) return;
    cw = ((DWORD)w + gw - 1) / gw;
    ch = ((DWORD)h + gh - 1) / gh;
    if (cw != v[0x374 / 4] || ch != v[0x378 / 4])
        logf("RZ   CELLFIX: dirty cell %lux%lu -> %lux%lu (%ldx%ld over a %lux%lu grid; truncated cells left %ld cols / %ld rows "
             "outside the grid)", v[0x374 / 4], v[0x378 / 4], cw, ch, w, h, gw, gh,
             w - (LONG)(gw * v[0x374 / 4]), h - (LONG)(gh * v[0x378 / 4]));
    v[0x374 / 4] = cw;
    v[0x378 / 4] = ch;
}

static void patch_gridb_clamp(HMODULE ss) {
    int k;
    for (k = 0; k < (int)(sizeof(g_clamps) / sizeof(g_clamps[0])); k++) {
        const CLAMP *c = &g_clamps[k];
        BYTE *hook = (BYTE *)ss + c->hook, *cave = (BYTE *)ss + c->cave;
        DWORD old, rel; DWORD i; int slackok = 1;
        /* the hook's first 5 stolen bytes == the cave's first 5 (the cave re-executes them) */
        if (IsBadReadPtr(hook, c->stolen) || memcmp(hook, c->expect, 5) != 0) {
            logf("--- GRIDB_CLAMP %s: hook 0x%X mismatch (%02X %02X %02X %02X %02X) - NOT patching",
                 c->name, c->hook, hook[0], hook[1], hook[2], hook[3], hook[4]);
            continue;
        }
        for (i = 0; i < c->nbytes; i++) if (cave[i] != 0) { slackok = 0; break; }
        if (!slackok) {
            logf("--- GRIDB_CLAMP %s: slack 0x%X not zero at +%lu - NOT patching", c->name, c->cave, i);
            continue;
        }
        if (!VirtualProtect(cave, c->nbytes, PAGE_EXECUTE_READWRITE, &old)) {
            logf("--- GRIDB_CLAMP %s: VP(cave) failed %lu", c->name, GetLastError()); continue; }
        memcpy(cave, c->bytes, c->nbytes);
        (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
        FlushInstructionCache(GetCurrentProcess(), cave, c->nbytes);
        if (!VirtualProtect(hook, c->stolen, PAGE_EXECUTE_READWRITE, &old)) {
            logf("--- GRIDB_CLAMP %s: VP(hook) failed %lu", c->name, GetLastError()); continue; }
        rel = c->cave - (c->hook + 5);
        hook[0] = 0xe9; memcpy(hook + 1, &rel, 4);
        for (i = 5; i < c->stolen; i++) hook[i] = 0x90;
        (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
        FlushInstructionCache(GetCurrentProcess(), hook, c->stolen);
        logf("--- GRIDB_CLAMP %s: index clamped (hook 0x%X -> cave 0x%X, base 0x%08lX)",
             c->name, c->hook, c->cave, (DWORD)ss);
    }
    patch_efa1_emptybucket(ss);
    logf("--- GRIDB_CLAMP: 4 walkers index-clamped (FIX A) + FUN_1000efa1 null-guarded (FIX C)");
}

/* ===================== FLYOUT LAYOUT DETOUR (2026-09-06) =====================
 * FUN_1004cdcd (SIMUI) is the resolution-keyed layout table for the tool-submenu 36x36 icons: it
 * reads the view height (this->vt[0x20]()->vt[0x94]()) and a resolution code (vt[0xe8]()) and picks
 * per-resolution icon offsets. When side-span makes the panel taller than native, it selects a
 * "tall" table entry that spaces the icons wider than the fixed 36px click-targets -> the flyout
 * icons drift below their targets, growing down the column (owner: "menu open, top a little, more
 * and more misaligned"). External frida instrumentation of this crashes the game during resize, so
 * this is a MOD-SIDE wrapping detour: run the original, then log its inputs/outputs to the mod log.
 * Prologue at SIMUI+0x4cdcd = `53 8b d9 56 57` (push ebx;mov ebx,ecx;push esi;push edi) - a clean
 * 5-byte boundary, so we steal 5 and trampoline. When SC3RESIZE_CDCDCLAMP is set, we also force the
 * NATIVE (600) layout by remembering the native output and re-applying it. */
static void *g_orig_cdcd;             /* trampoline: stolen prologue + jmp back to SIMUI+0x4cdcd+5 */
static int   g_cdcdlog = 0;          /* SC3RESIZE_CDCDLOG=1: install the flyout diag detours + log.
                                        Default OFF - they are diagnostic (ruled out FUN_1004cdcd and
                                        FUN_1004e81c as the flyout-icon scale source, 2026-09-06). */
static int   g_cdcdlogn;

static DWORD __fastcall rz_cdcd_detour(void *self, void *edx, void *param_1) {
    DWORD r, arg = (DWORD)param_1;
    (void)edx;
    r = rz_thiscall_ret(self, g_orig_cdcd, &arg, 1);   /* run the original via the trampoline */
    if (g_cdcdlog && g_cdcdlogn < 60 && param_1 && !IsBadReadPtr(param_1, 0x28)) {
        LONG *p = (LONG *)param_1;
        RECT cr; LONG ch = (g_hwnd && GetClientRect(g_hwnd, &cr)) ? cr.bottom - cr.top : -1;
        logf("CDCD> clientH=%ld self=0x%08lX out: p0=0x%lx p2=0x%lx cellW(p6)=%ld cellH(p7)=%ld "
             "p8=%ld p9=%ld", ch, (DWORD)self, (DWORD)p[0], (DWORD)p[2], p[6], p[7], p[8], p[9]);
        g_cdcdlogn++;
    }
    return r;
}

static void rz_hook_cdcd(HMODULE sui) {
    BYTE *fn = (BYTE *)sui + 0x4cdcd, *tr;
    static const BYTE expect[5] = { 0x53, 0x8b, 0xd9, 0x56, 0x57 };
    DWORD old;
    if (g_orig_cdcd) return;                          /* once */
    if (IsBadReadPtr(fn, 5) || memcmp(fn, expect, 5) != 0) {
        logf("CDCD> SIMUI+0x4cdcd prologue mismatch (%02X %02X %02X %02X %02X) - NOT hooking",
             fn[0], fn[1], fn[2], fn[3], fn[4]);
        return;
    }
    tr = (BYTE *)VirtualAlloc(NULL, 16, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!tr) { logf("CDCD> VirtualAlloc failed"); return; }
    memcpy(tr, expect, 5);                             /* stolen prologue */
    tr[5] = 0xE9;                                      /* jmp fn+5 */
    *(DWORD *)(tr + 6) = (DWORD)(fn + 5) - (DWORD)(tr + 10);
    FlushInstructionCache(GetCurrentProcess(), tr, 16);
    g_orig_cdcd = (void *)tr;
    if (!VirtualProtect(fn, 5, PAGE_EXECUTE_READWRITE, &old)) {
        logf("CDCD> VP failed %lu", GetLastError()); g_orig_cdcd = NULL; return;
    }
    fn[0] = 0xE9;                                      /* jmp rz_cdcd_detour */
    *(DWORD *)(fn + 1) = (DWORD)rz_cdcd_detour - (DWORD)(fn + 5);
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    FlushInstructionCache(GetCurrentProcess(), fn, 5);
    logf("CDCD> logging detour installed at SIMUI+0x4cdcd (trampoline 0x%08lX)", (DWORD)tr);
}

/* ===================== ICON-DRAW DETOUR (2026-09-06) =====================
 * FUN_1004e81c (SIMUI, panel vt+0x22c) is the panel/column draw that RECEIVES an item's final dest:
 * __thiscall(this, param_2=raster, param_3, param_4=x, param_5=y) - it stores them at +0xac/+0x114/
 * +0x128/+0x12c and blits. FUN_1004cdcd was ruled out (it lays icons at native 36px); the stretch is
 * HERE, in the render, where the native icon y gets scaled by the extended panel height. This detour
 * logs (x,y) per draw so we can see the scale. Prologue at SIMUI+0x4e81c = `8b 44 24 04 56` - clean
 * 5-byte boundary. */
static void *g_orig_e81c;
static int   g_e81cn;
static DWORD __fastcall rz_e81c_detour(void *self, void *edx, DWORD p2, DWORD p3, DWORD p4, DWORD p5) {
    DWORD args[4], r;
    (void)edx;
    args[0] = p2; args[1] = p3; args[2] = p4; args[3] = p5;
    r = rz_thiscall_ret(self, g_orig_e81c, args, 4);
    if (g_cdcdlog) {                    /* burst up to 40 draws per 500ms window (the recent log = a
                                           near-complete frame while the flyout is open) */
        static DWORD win_start; static int win_n;
        DWORD now = GetTickCount();
        if (now - win_start >= 500) { win_start = now; win_n = 0; }
        if (win_n < 40) {
            logf("E81C> self=0x%08lX raster=0x%lx x=%ld y=%ld", (DWORD)self, p2, (LONG)p4, (LONG)p5);
            win_n++;
        }
    }
    (void)g_e81cn; (void)p3;
    return r;
}
static void rz_hook_e81c(HMODULE sui) {
    BYTE *fn = (BYTE *)sui + 0x4e81c, *tr;
    static const BYTE expect[5] = { 0x8b, 0x44, 0x24, 0x04, 0x56 };
    DWORD old;
    if (g_orig_e81c) return;
    if (IsBadReadPtr(fn, 5) || memcmp(fn, expect, 5) != 0) {
        logf("E81C> SIMUI+0x4e81c prologue mismatch - NOT hooking"); return;
    }
    tr = (BYTE *)VirtualAlloc(NULL, 16, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!tr) return;
    memcpy(tr, expect, 5); tr[5] = 0xE9;
    *(DWORD *)(tr + 6) = (DWORD)(fn + 5) - (DWORD)(tr + 10);
    FlushInstructionCache(GetCurrentProcess(), tr, 16);
    g_orig_e81c = (void *)tr;
    if (!VirtualProtect(fn, 5, PAGE_EXECUTE_READWRITE, &old)) { g_orig_e81c = NULL; return; }
    fn[0] = 0xE9; *(DWORD *)(fn + 1) = (DWORD)rz_e81c_detour - (DWORD)(fn + 5);
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    FlushInstructionCache(GetCurrentProcess(), fn, 5);
    logf("E81C> icon-draw logging detour installed at SIMUI+0x4e81c");
}

/* ===================== a917c ICON PAINT DETOUR (2026-09-06) =====================
 * FUN_1004cac8 is the flyout sub-tool (class a917c) OWN paint (vtable +0x144). It blits sprite
 * param_1[0x36] with SOURCE rect [0,0,vt0x90(),vt0x94()] (native icon dims) into DEST rect =
 * param_1+0x24, via param_1[0x17]->vt[0x118] (FUN_10014894, which STRETCHES if src!=dst height).
 * So the flyout icon's size/position is param_1+0x24. This detour logs that dest rect (burst per
 * 500ms) so we can see whether it is stretched (size) or spread (spacing) vs the native 36px.
 * Prologue at SIMUI+0x4cac8 = `55 8b ec 83 ec 10` (push ebp;mov ebp,esp;sub esp,0x10) - 6-byte
 * clean boundary; steal 6 (5-byte jmp + 1 nop). __thiscall(this) - this in ecx, no stack args. */
static void *g_orig_cac8;
static DWORD __fastcall rz_cac8_detour(void *self, void *edx) {
    DWORD r;
    (void)edx;
    r = rz_thiscall_ret(self, g_orig_cac8, NULL, 0);   /* run the original icon paint */
    if (g_cdcdlog && self && !IsBadReadPtr(self, 0x34)) {
        static DWORD win_start; static int win_n;
        DWORD now = GetTickCount();
        LONG *d = (LONG *)((DWORD)self + 0x24);        /* the dest rect the icon blits into */
        if (now - win_start >= 500) { win_start = now; win_n = 0; }
        if (win_n < 40) {
            /* Walk to the a917c's PARENT (the column window, a9a80) and read ITS composite blit:
             * FUN_1006d2d0 blits column +0x58 surface with src=+0x24 -> dest=+0x90. If those heights
             * differ, the column-surface->screen blit stretches the icons. Also its derived +0x14. */
            DWORD col = ((DWORD *)((DWORD)self))[0x3c / 4];
            LONG cs[4]={0,0,0,0}, cd[4]={0,0,0,0}, cab[4]={0,0,0,0}, clo[4]={0,0,0,0};
            if (col && !IsBadReadPtr((void *)col, 0x94)) {
                LONG *a=(LONG*)(col+0x24),*b=(LONG*)(col+0x90),*c=(LONG*)(col+0x14),*e=(LONG*)(col+0x80);
                cs[0]=a[0];cs[1]=a[1];cs[2]=a[2];cs[3]=a[3];
                cd[0]=b[0];cd[1]=b[1];cd[2]=b[2];cd[3]=b[3];
                cab[0]=c[0];cab[1]=c[1];cab[2]=c[2];cab[3]=c[3];
                clo[0]=e[0];clo[1]=e[1];clo[2]=e[2];clo[3]=e[3];
            }
            logf("CAC8> iconY=%ld..%ld | COL 0x%08lX src24=[%ld %ld %ld %ld](h=%ld) dst90=[%ld %ld %ld %ld](h=%ld) "
                 "local80=[%ld %ld %ld %ld] abs14=[%ld %ld %ld %ld]",
                 d[1], d[3], col, cs[0],cs[1],cs[2],cs[3], cs[3]-cs[1], cd[0],cd[1],cd[2],cd[3], cd[3]-cd[1],
                 clo[0],clo[1],clo[2],clo[3], cab[0],cab[1],cab[2],cab[3]);
            win_n++;
        }
    }
    return r;
}
static void rz_hook_cac8(HMODULE sui) {
    BYTE *fn = (BYTE *)sui + 0x4cac8, *tr;
    static const BYTE expect[6] = { 0x55, 0x8b, 0xec, 0x83, 0xec, 0x10 };
    DWORD old;
    if (g_orig_cac8) return;
    if (IsBadReadPtr(fn, 6) || memcmp(fn, expect, 6) != 0) {
        logf("CAC8> SIMUI+0x4cac8 prologue mismatch - NOT hooking"); return;
    }
    tr = (BYTE *)VirtualAlloc(NULL, 16, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!tr) return;
    memcpy(tr, expect, 6); tr[6] = 0xE9;
    *(DWORD *)(tr + 7) = (DWORD)(fn + 6) - (DWORD)(tr + 11);
    FlushInstructionCache(GetCurrentProcess(), tr, 16);
    g_orig_cac8 = (void *)tr;
    if (!VirtualProtect(fn, 6, PAGE_EXECUTE_READWRITE, &old)) { g_orig_cac8 = NULL; return; }
    fn[0] = 0xE9; *(DWORD *)(fn + 1) = (DWORD)rz_cac8_detour - (DWORD)(fn + 5); fn[5] = 0x90;
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    FlushInstructionCache(GetCurrentProcess(), fn, 6);
    logf("CAC8> a917c icon-paint logging detour installed at SIMUI+0x4cac8");
}

/* ===================== HUD REFLOW - top-strip PROOF (2026-08-30) =====================
 * The HUD lays out ONCE at window construction and never re-runs on a window resize (SIMUI has no
 * runtime re-layout trigger - worker dig, verify/resize_ui/). Two parts:
 *   (1) rz_hud_reflow rewrites the top-strip anchor TABLE for the live width (extend, keep size);
 *   (2) patch_hud_reflow WRAPS FUN_100270e5 (the table producer) to capture the HUD `this` (=ecx) and
 *       call rz_hud_reflow on its output;
 *   (3) resize step 12 drives the guarded destruct+rebuild (FUN_100266c1 then FUN_10024a96) so the
 *       producer re-runs at the live width. All SIMUI. Only the top strip for this proof. */

/* Rewrite the top-strip anchor table for the live client width. The table's 4 widgets are 4-field
 * boxes (X1,Y1,X2,Y2) at idx 1-4/5-8/9-12/13-16; idx0 is a resolution tag whose hex digits spell the
 * NATIVE resolution (0x1024768=1024x768, 0x800600=800x600, 0x640480=640x480). "Extend, keep size":
 * origin-scale each widget's X by live/native and preserve its width. Y (top strip band) unchanged.
 * Only widens (live > native); at native or smaller it is a no-op, so construction is untouched.
 * The label group (idx17-28) is left alone in this proof. __cdecl: the wrap cleans the arg. */
static int g_hudreflow = 0;
static void __cdecl rz_hud_reflow(DWORD *arr) {
    static const int x1i[4] = { 1, 5, 9, 13 };
    static const int x2i[4] = { 3, 7, 11, 15 };
    int native_w, live_w, k;
    RECT cr;
    DWORD tag;
    if (!arr || IsBadWritePtr(arr, 0x74)) return;          /* 0x1d ints */
    /* OFF BY DEFAULT (owner 2026-10-07). This proof origin-scales the bar's four info-field boxes by live/native.
       When the HUD is built in an already-maximized window (New City while maximized) that scaled the fields by
       2.56x and the bar-span code then shifted them by dx again: date field at x 2261..2365 in a 2048 client,
       population and money out of place. The bar-span code places the fields itself, so this is not needed.
       SC3RESIZE_HUDREFLOW=1 restores it. */
    if (!g_hudreflow) return;
    tag = arr[0];
    if      (tag == 0x1024768) native_w = 1024;
    else if (tag == 0x800600)  native_w = 800;
    else if (tag == 0x640480)  native_w = 640;
    else { logf("RZ   HUD reflow: unknown tag 0x%08lX - skip", tag); return; }
    if (!g_hwnd || !GetClientRect(g_hwnd, &cr)) return;
    live_w = (int)(cr.right - cr.left);
    if (live_w <= native_w) return;                         /* only extend when wider than native */
    for (k = 0; k < 4; k++) {
        int x1 = (int)arr[x1i[k]], x2 = (int)arr[x2i[k]], w = x2 - x1;
        int nx1 = (int)(((__int64)x1 * live_w) / native_w);
        arr[x1i[k]] = (DWORD)nx1;
        arr[x2i[k]] = (DWORD)(nx1 + w);                     /* keep width */
    }
    logf("RZ   HUD reflow: tag native %d -> live %d, top-strip 4 widgets origin-scaled (keep width)",
         native_w, live_w);
}

/* Wrap FUN_100270e5: capture ecx (HUD `this`) into g_hud_top, run the original (fills the table), then
 * rz_hud_reflow(table). Custom cave because we post-process the OUTPUT (an entry hook cannot). The
 * function is __thiscall(this, outTable) ending `ret 4` (verified from the PE), so the wrapper calls it
 * as a subroutine with param_1 re-pushed and lets its own ret 4 unwind. Fail-closed: verifies the
 * prologue bytes before hooking. */
/* BAR800 (owner 2026-10-07): SIMUI FUN_100270e5 picks the bar layout group from the ROOT WIDTH (640 / 800 /
   >= 801 -> 1024x768 group; worker report re/harness/simrun/opt2_result.txt). Maximized BEFORE New City, the
   game built the 1024 group's field positions on top of the 800 group's 600-wide art (live read: date field
   at x 2070..2174 in a 1920 client, population out of place), while this mod lays the bar out from the 800
   layout. Present an 800-wide root to that one call so both flows build the same bar. SC3RESIZE_BAR800=0. */
static int  g_bar800 = 1;
static LONG g_bar800_saved = 0x7fffffff;
static LONG *g_bar800_win;
static DWORD rz_thiscall_ret(void *self, void *fn, const DWORD *a, int n);   /* fwd */
/* cdecl, arg = the HUD `this` (the cave pushes ecx). Resolve the window the selector itself reads -
   this->vt[0x10]()->vt[0x0c](), width = vt[0x90] = +0x88 - +0x80 - and present it 800 wide. */
static void __cdecl rz_bar800_begin(void *self) {
    DWORD *vt, w1, *vt1, w2;
    LONG *r;
    g_bar800_saved = 0x7fffffff; g_bar800_win = NULL;
    if (!g_bar800 || !self || IsBadReadPtr(self, 4)) return;
    vt = *(DWORD **)self;
    if (!vt || IsBadReadPtr(vt, 0x14) || !vt[0x10 / 4]) return;
    w1 = rz_thiscall_ret(self, (void *)vt[0x10 / 4], NULL, 0);
    if (!w1 || IsBadReadPtr((void *)w1, 4)) return;
    vt1 = *(DWORD **)w1;
    if (!vt1 || IsBadReadPtr(vt1, 0x10) || !vt1[0x0c / 4]) return;
    w2 = rz_thiscall_ret((void *)w1, (void *)vt1[0x0c / 4], NULL, 0);
    if (!w2 || IsBadWritePtr((BYTE *)w2 + 0x80, 16)) return;
    r = (LONG *)w2;
    if (r[0x88 / 4] - r[0x80 / 4] > NAT_W) {
        g_bar800_win = r; g_bar800_saved = r[0x88 / 4];
        r[0x88 / 4] = r[0x80 / 4] + NAT_W;
        logf("BAR800> layout window 0x%08lX width %ld presented as %d to the bar layout selector",
             w2, g_bar800_saved - r[0x80 / 4], NAT_W);
    }
}
static void __cdecl rz_bar800_end(void) {
    if (g_bar800_win && g_bar800_saved != 0x7fffffff && !IsBadWritePtr((BYTE *)g_bar800_win + 0x80, 16))
        g_bar800_win[0x88 / 4] = g_bar800_saved;
    g_bar800_saved = 0x7fffffff; g_bar800_win = NULL;
}

static void patch_hud_reflow(HMODULE sui) {
    static const BYTE expect[6] = { 0x8B, 0x01, 0x56, 0xFF, 0x50, 0x10 };
    BYTE *t = (BYTE *)sui + SUI_RVA_PRODUCER;
    int relofs[MAX_REL], nrel = 0, k, len;
    BYTE *tr, *cave;
    DWORD old, n = 0;

    if (IsBadReadPtr(t, 6) || memcmp(t, expect, 6) != 0) {
        logf("--- HUD: FUN_100270e5 prologue mismatch (%02X %02X %02X %02X %02X %02X) - NOT hooking",
             t[0], t[1], t[2], t[3], t[4], t[5]);
        return;
    }
    len = steal_len(t, relofs, &nrel);
    if (len < 5) { logf("--- HUD: FUN_100270e5 undecodable prologue - skip"); return; }
    tr   = pool_alloc(len + 5);
    cave = (BYTE *)VirtualAlloc(NULL, 96, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!tr || !cave) { logf("--- HUD: alloc failed"); return; }

    memcpy(tr, t, len);
    for (k = 0; k < nrel; k++) {
        int o = relofs[k];
        DWORD abs_t = (DWORD)(t + o + 5) + *(DWORD *)(t + o + 1);
        *(DWORD *)(tr + o + 1) = abs_t - (DWORD)(tr + o + 5);
    }
    tr[len] = 0xE9; *(DWORD *)(tr + len + 1) = (DWORD)(t + len) - (DWORD)(tr + len + 5);

    /* cave: mov [g_hud_top],ecx ; push [esp+4] ; call tr ; push eax ; push [esp+8] ; call reflow ;
             add esp,4 ; pop eax ; ret 4 */
    cave[n++] = 0x89; cave[n++] = 0x0D; *(DWORD *)(cave + n) = (DWORD)&g_hud_top; n += 4;
    cave[n++] = 0x51;                                                                   /* push ecx */
    cave[n++] = 0xE8; *(DWORD *)(cave + n) = (DWORD)rz_bar800_begin - (DWORD)(cave + n + 4); n += 4;
    cave[n++] = 0x59;                                                                   /* pop ecx */
    cave[n++] = 0xFF; cave[n++] = 0x74; cave[n++] = 0x24; cave[n++] = 0x04;
    cave[n++] = 0xE8; *(DWORD *)(cave + n) = (DWORD)tr - (DWORD)(cave + n + 4); n += 4;
    cave[n++] = 0x50;
    cave[n++] = 0xE8; *(DWORD *)(cave + n) = (DWORD)rz_bar800_end - (DWORD)(cave + n + 4); n += 4;
    cave[n++] = 0xFF; cave[n++] = 0x74; cave[n++] = 0x24; cave[n++] = 0x08;
    cave[n++] = 0xE8; *(DWORD *)(cave + n) = (DWORD)rz_hud_reflow - (DWORD)(cave + n + 4); n += 4;
    cave[n++] = 0x83; cave[n++] = 0xC4; cave[n++] = 0x04;
    cave[n++] = 0x58;
    cave[n++] = 0xC2; cave[n++] = 0x04; cave[n++] = 0x00;

    if (!VirtualProtect(t, (SIZE_T)len, PAGE_EXECUTE_READWRITE, &old)) {
        logf("--- HUD: VirtualProtect failed (%lu)", GetLastError()); return; }
    t[0] = 0xE9; *(DWORD *)(t + 1) = (DWORD)cave - (DWORD)(t + 5);
    { int j; for (j = 5; j < len; j++) t[j] = 0x90; }
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    FlushInstructionCache(GetCurrentProcess(), t, (SIZE_T)len);
    logf("--- HUD: FUN_100270e5 wrapped (cave 0x%08lX tr 0x%08lX) - top-strip reflow armed", (DWORD)cave, (DWORD)tr);
}

/* FIELDBG (2026-10-07, verify/simrun/RESULTS.md follow-up): the bottom bar's four info fields (city,
 * population, money, date) erase their old text by copying a patch of the bar background raster
 * (+0xa8, 600x56) into the field raster. SIMUI FUN_10026a09 computes that patch as the field's DEST
 * rect (+0x120 + idx*0x10) minus the BAR origin (+0x24, +0x28) [CONFIRMED @ 0x10026a5c]. The bar span
 * above moves the art (+0x120) and the field dests by dx but the bar origin stays put, so once
 * dest - origin passes x=600 the erase reads outside the art and new text lands on the old text: the
 * owner's "dates piling over each other" at 2560 wide (measured 2026-10-07, both simrun arms).
 * Fix: subtract the ART origin instead (where the background raster is actually drawn). At native size
 * the two are equal, so this is stock there. Falls back to the stock read if the art rect is empty.
 * Patch site 0x10026a5c: mov ecx,[edx+24] / mov eax,[edx+28] / movsd (7 bytes) -> jmp cave. */
static int g_fieldbg = 1;          /* SC3RESIZE_FIELDBG=0 = control arm */
static void patch_fieldbg(HMODULE sui) {
    static const BYTE expect[] = { 0x8B, 0x4A, 0x24, 0x8B, 0x42, 0x28, 0xA5, 0x8B, 0x75, 0x08 };
    BYTE *t = (BYTE *)sui + 0x26a5c, *cave;
    DWORD old, n = 0;
    if (!g_fieldbg) { logf("--- FIELDBG: off (SC3RESIZE_FIELDBG=0) - stock field erase"); return; }
    if (IsBadReadPtr(t, sizeof(expect)) || memcmp(t, expect, sizeof(expect))) {
        logf("--- FIELDBG: SIMUI+0x26a5c differs from shipped - NOT patched"); return; }
    cave = (BYTE *)VirtualAlloc(NULL, 64, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!cave) { logf("--- FIELDBG: VirtualAlloc failed"); return; }
    /* mov ecx,[edx+0x128] ; sub ecx,[edx+0x120] ; jz stock */
    cave[n++] = 0x8B; cave[n++] = 0x8A; *(DWORD *)(cave + n) = 0x128; n += 4;
    cave[n++] = 0x2B; cave[n++] = 0x8A; *(DWORD *)(cave + n) = 0x120; n += 4;
    cave[n++] = 0x74; cave[n++] = 0x0E;                                      /* jz +14 -> stock */
    /* art: mov ecx,[edx+0x120] ; mov eax,[edx+0x124] ; movsd ; jmp back */
    cave[n++] = 0x8B; cave[n++] = 0x8A; *(DWORD *)(cave + n) = 0x120; n += 4;
    cave[n++] = 0x8B; cave[n++] = 0x82; *(DWORD *)(cave + n) = 0x124; n += 4;
    cave[n++] = 0xEB; cave[n++] = 0x06;                                      /* jmp +6 -> tail */
    /* stock: mov ecx,[edx+0x24] ; mov eax,[edx+0x28] */
    cave[n++] = 0x8B; cave[n++] = 0x4A; cave[n++] = 0x24;
    cave[n++] = 0x8B; cave[n++] = 0x42; cave[n++] = 0x28;
    /* tail: movsd ; jmp t+7 */
    cave[n++] = 0xA5;
    cave[n++] = 0xE9; *(DWORD *)(cave + n) = (DWORD)(t + 7) - (DWORD)(cave + n + 4); n += 4;
    FlushInstructionCache(GetCurrentProcess(), cave, n);
    if (!VirtualProtect(t, 7, PAGE_EXECUTE_READWRITE, &old)) { logf("--- FIELDBG: VirtualProtect failed"); return; }
    t[0] = 0xE9; *(DWORD *)(t + 1) = (DWORD)cave - (DWORD)(t + 5);
    t[5] = 0x90; t[6] = 0x90;
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    FlushInstructionCache(GetCurrentProcess(), t, 7);
    logf("--- FIELDBG: SIMUI FUN_10026a09 field erase reads the ART origin (cave 0x%08lX)", (DWORD)cave);
}

/* ---- INTRO: the intro movie whole and centred in the window (task intro, 2026-10-12) ----------
 * Owner report: "la intro se ve cortada". Mechanism, all in re/analysis/INTRO_MOVIE.md:
 * SC3U FUN_00429f95 plays Res/UI/Shared/Movies/Intro.tgq through UV.DLL in "direct" mode (ctx flag 0x400):
 * the codec Locks the whole PRIMARY and writes pixels itself. The movie is 320x480 and flag 0x40 asks for
 * double width. The doubling writer (UV FUN_10006900, case 3 FUN_100065a0) writes one DWORD per source pixel
 * at dst = bits + x*4 + y*pitch: on a 16bpp primary that DWORD is two pixels (640 wide), and the game
 * passes x/2 to match (FUN_00429f95: vt+0x40 gets (x & 0xffff) >> 1). On a 32bpp primary (our windowed
 * desktop) the same DWORD is ONE pixel: the picture comes out 320x480 at half the intended screen x, which
 * for a centred 800x600 window starts left of the client. Only its right part lands inside the window.
 * Fix: the two writer calls in UV FUN_10005c40 are re-targeted here. On a 32bpp primary the codec decodes
 * into a private buffer and this code scales it into the client, centred, aspect kept, black bars.
 * Default (1): integer scale, 1x in the 800x600 window like stock fullscreen, 2x when it fits. 2: fit to the
 * window at any scale. 0 (SC3RESIZE_INTRO=0): stock. A 16bpp primary is left to the codec (it doubles). */
static int g_intro = 1;
typedef void (__cdecl *uv_writer_t)(int *, void *, BYTE *, void *, unsigned);
static uv_writer_t g_uv_w6900, g_uv_w65a0;
static DWORD *g_intro_buf;
static unsigned g_intro_bw, g_intro_bh;      /* buffer size in pixels (16-aligned, the writers work in 16x16 blocks) */
static int g_intro_bpp = -1;                 /* primary bpp from GetSurfaceDesc, -1 = not read yet */
static LONG g_intro_sw, g_intro_sh, g_intro_sp; /* primary width, height, pitch */
static unsigned g_intro_frames, g_intro_pass;
static RECT g_intro_last;                    /* last client rect on the primary, for change logging */
static HWND g_intro_hwnd;

static BOOL CALLBACK intro_enum(HWND h, LPARAM p) {
    DWORD pid = 0;
    GetWindowThreadProcessId(h, &pid);
    if (pid != GetCurrentProcessId() || !IsWindowVisible(h)) return TRUE;
    *(HWND *)p = h;
    return FALSE;
}

/* Primary surface desc (IDirectDrawSurface vt+0x58 GetSurfaceDesc, DDSURFACEDESC v1 = 0x6c bytes). */
static int intro_read_desc(void *surf) {
    DWORD d[0x7c / 4];
    typedef HRESULT (__stdcall *gsd_t)(void *, DWORD *);
    HRESULT hr;
    if (!surf) return 0;
    memset(d, 0, sizeof(d)); d[0] = 0x6c;
    hr = ((gsd_t)(*(DWORD **)surf)[0x58 / 4])(surf, d);
    if (hr != 0) { logf("INTRO> GetSurfaceDesc failed 0x%08lX - stock path", (DWORD)hr); return 0; }
    g_intro_sh = (LONG)d[2]; g_intro_sw = (LONG)d[3]; g_intro_sp = (LONG)d[4];
    g_intro_bpp = (int)d[(0x48 + 0xc) / 4];
    logf("INTRO> primary %ldx%ld pitch %ld bpp %d", g_intro_sw, g_intro_sh, g_intro_sp, g_intro_bpp);
    return 1;
}

static void intro_frame(uv_writer_t orig, const char *which, int *p1, void *src, BYTE *dst, void *p4, unsigned pitch) {
    BYTE *ctx, *base;
    DWORD flags;
    unsigned sw, sh, need;
    LONG x, y, cw, ch, sw2, tw, th, tx, ty, r, c, r0, r1, c0, c1, k, scrw, scrh;
    RECT cr;
    POINT org = {0, 0};
    void *surf;

    ctx = (BYTE *)p1[0];
    flags = *(DWORD *)(ctx + 4);
    /* Only the case measured: mode 1 (p1[0x13]), direct-to-primary (0x400), double width (0x40). */
    if (!g_intro || p1[0x13] != 1 || !(flags & 0x400) || !(flags & 0x40)) { orig(p1, src, dst, p4, pitch); return; }
    surf = *(void **)(ctx + ((flags & 0x8000000) ? 0x18 : 0x14));
    if (g_intro_bpp < 0 && !intro_read_desc(surf)) g_intro_bpp = 0;
    sw = *(unsigned *)(ctx + 100); sh = *(unsigned *)(ctx + 0x60);
    if (g_intro_bpp != 32 || (LONG)pitch != g_intro_sp || !sw || !sh || sw > 4096 || sh > 4096) {
        if (!g_intro_pass++) logf("INTRO> %s: stock path (bpp %d, pitch %u vs %ld, movie %ux%u)",
                                  which, g_intro_bpp, pitch, g_intro_sp, sw, sh);
        orig(p1, src, dst, p4, pitch); return;
    }
    x = p1[5]; y = p1[6];
    base = dst - x * 4 - y * (LONG)pitch;    /* the codec's own address: bits + x*4 + y*pitch (UV 0x10005ef9) */

    need = ((sw + 15) & ~15u) * ((sh + 15) & ~15u);
    if (!g_intro_buf || g_intro_bw * g_intro_bh < need) {
        if (g_intro_buf) HeapFree(GetProcessHeap(), 0, g_intro_buf);
        g_intro_bw = (sw + 15) & ~15u; g_intro_bh = (sh + 15) & ~15u;
        g_intro_buf = (DWORD *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, g_intro_bw * g_intro_bh * 4);
        if (!g_intro_buf) { logf("INTRO> buffer alloc failed - stock path"); g_intro = 0; orig(p1, src, dst, p4, pitch); return; }
    }
    orig(p1, src, (BYTE *)g_intro_buf, p4, g_intro_bw * 4);

    if (!g_intro_hwnd || !IsWindow(g_intro_hwnd)) {
        g_intro_hwnd = g_hwnd;
        if (!g_intro_hwnd) EnumWindows(intro_enum, (LPARAM)&g_intro_hwnd);
    }
    if (!g_intro_hwnd || !GetClientRect(g_intro_hwnd, &cr) || !ClientToScreen(g_intro_hwnd, &org)) return;
    cw = cr.right - cr.left; ch = cr.bottom - cr.top;
    /* Client rect in primary pixels. Same space when the primary is the size Windows reports for the screen
       (measured here, 100% scaling). Otherwise scale by surface/screen [UNVERIFIED on a scaled display]. */
    scrw = GetSystemMetrics(SM_CXSCREEN); scrh = GetSystemMetrics(SM_CYSCREEN);
    if (scrw > 0 && scrh > 0 && (scrw != g_intro_sw || scrh != g_intro_sh)) {
        org.x = MulDiv(org.x, g_intro_sw, scrw); org.y = MulDiv(org.y, g_intro_sh, scrh);
        cw = MulDiv(cw, g_intro_sw, scrw); ch = MulDiv(ch, g_intro_sh, scrh);
    }
    if (cw <= 0 || ch <= 0) return;

    sw2 = (LONG)sw * 2;                      /* the picture as designed: double width */
    k = (cw / sw2 < ch / (LONG)sh) ? cw / sw2 : ch / (LONG)sh;
    if (g_intro == 1 && k >= 1) { tw = sw2 * k; th = (LONG)sh * k; }
    else if ((__int64)cw * sh <= (__int64)ch * sw2) { tw = cw; th = (LONG)((__int64)cw * sh / sw2); }
    else { th = ch; tw = (LONG)((__int64)ch * sw2 / sh); }
    if (tw <= 0 || th <= 0) return;
    tx = org.x + (cw - tw) / 2; ty = org.y + (ch - th) / 2;

    g_intro_frames++;
    if (g_intro_frames == 1 || cr.right != g_intro_last.right || cr.bottom != g_intro_last.bottom ||
        org.x != g_intro_last.left || org.y != g_intro_last.top) {
        logf("INTRO> %s frame %u: codec x,y %ld,%ld (stock dest), client %ldx%ld at %ld,%ld on the primary, "
             "movie %ux%u shown %ldx%ld at %ld,%ld", which, g_intro_frames, x, y, cw, ch, org.x, org.y,
             sw, sh, tw, th, tx, ty);
        g_intro_last.left = org.x; g_intro_last.top = org.y; g_intro_last.right = cr.right; g_intro_last.bottom = cr.bottom;
    }

    __try {
        /* Every write is clipped to client AND primary bounds. */
        r0 = org.y > 0 ? org.y : 0; r1 = org.y + ch < g_intro_sh ? org.y + ch : g_intro_sh;
        c0 = org.x > 0 ? org.x : 0; c1 = org.x + cw < g_intro_sw ? org.x + cw : g_intro_sw;
        for (r = r0; r < r1; r++) {
            DWORD *row = (DWORD *)(base + r * (LONG)pitch);
            if (r < ty || r >= ty + th) { for (c = c0; c < c1; c++) row[c] = 0; continue; }
            {
                const DWORD *srow = g_intro_buf + (unsigned)((__int64)(r - ty) * sh / th) * g_intro_bw;
                LONG a = tx > c0 ? tx : c0, b = tx + tw < c1 ? tx + tw : c1;
                DWORD step = (DWORD)(((unsigned __int64)sw << 16) / (unsigned)tw);
                DWORD acc = (DWORD)(a - tx) * step;
                for (c = c0; c < a; c++) row[c] = 0;
                for (c = a; c < b; c++, acc += step) row[c] = srow[acc >> 16];
                for (c = b; c < c1; c++) row[c] = 0;
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        logf("INTRO> fault while drawing (primary %ldx%ld pitch %u) - INTRO off", g_intro_sw, g_intro_sh, pitch);
        g_intro = 0;
    }
}

static void __cdecl intro_w6900(int *p1, void *src, BYTE *dst, void *p4, unsigned pitch) {
    intro_frame(g_uv_w6900, "FUN_10006900", p1, src, dst, p4, pitch);
}
static void __cdecl intro_w65a0(int *p1, void *src, BYTE *dst, void *p4, unsigned pitch) {
    intro_frame(g_uv_w65a0, "FUN_100065a0", p1, src, dst, p4, pitch);
}

/* Re-target the two doubling-writer calls in UV FUN_10005c40 (E8 rel32 at +0x5ef9 -> +0x6900, +0x5e2a -> +0x65a0).
   Both sites are checked before either is written. UV.DLL is identical in the dev and stock installs
   (SHA-256 e81ade5b...bef4). */
static DWORD WINAPI intro_watcher(LPVOID param) {
    static const DWORD site[2] = {0x5ef9, 0x5e2a}, target[2] = {0x6900, 0x65a0};
    BYTE *uv = NULL;
    DWORD old;
    int i, tries = 0;
    (void)param;
    { char v[8]; if (GetEnvironmentVariableA("SC3RESIZE_INTRO", v, sizeof(v))) g_intro = atoi(v); }
    if (!g_intro) { logf("--- INTRO: off (SC3RESIZE_INTRO=0) - stock intro"); return 0; }
    while (tries++ < 30000 && !(uv = (BYTE *)GetModuleHandleA("UV.DLL"))) Sleep(1);
    if (!uv) { logf("--- INTRO: UV.DLL never loaded - not armed"); return 0; }
    for (i = 0; i < 2; i++) {
        BYTE *s = uv + site[i];
        if (IsBadReadPtr(s, 5) || s[0] != 0xE8 || (DWORD)(s + 5 + *(LONG *)(s + 1)) != (DWORD)(uv + target[i])) {
            logf("--- INTRO: UV+0x%lX is not the expected call - not armed", site[i]);
            return 0;
        }
    }
    g_uv_w6900 = (uv_writer_t)(uv + target[0]);
    g_uv_w65a0 = (uv_writer_t)(uv + target[1]);
    for (i = 0; i < 2; i++) {
        BYTE *s = uv + site[i];
        DWORD fn = i == 0 ? (DWORD)intro_w6900 : (DWORD)intro_w65a0;
        if (!VirtualProtect(s, 5, PAGE_EXECUTE_READWRITE, &old)) { logf("--- INTRO: VirtualProtect failed"); return 0; }
        *(LONG *)(s + 1) = (LONG)(fn - (DWORD)(s + 5));
        (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
        FlushInstructionCache(GetCurrentProcess(), s, 5);
    }
    logf("--- INTRO: armed (mode %d) - UV.DLL base 0x%08lX, writer calls at +0x5ef9/+0x5e2a re-targeted",
         g_intro, (DWORD)uv);
    return 0;
}

static DWORD WINAPI rz_watcher(LPVOID param) {
    HMODULE ss = NULL, gz = NULL;
    int tries = 0;
    (void)param;
    /* Both modules load after DllMain, so wait for them rather than assuming. */
    while (tries++ < 600 && (!ss || !gz)) {
        ss = GetModuleHandleA("SIMSPR.DLL");
        gz = GetModuleHandleA("GZGraphicD.dll");
        if (ss && gz) break;
        Sleep(100);
    }
    if (!ss || !gz) {
        logf("### RESIZE: SIMSPR/GZGraphicD never loaded after %d tries - mod inactive", tries);
        return 0;
    }
    logf("### RESIZE: SIMSPR base 0x%08lX (relocated: %s)  GZGraphicD base 0x%08lX (%s)",
         (DWORD)ss, (DWORD)ss == 0x10000000 ? "NO" : "YES",
         (DWORD)gz, (DWORD)gz == 0x10000000 ? "NO" : "YES");

    /* idx 0 must be the bridge capture: without it there is no iso view and no lever. */
    /* Display-mode control FIRST, before any hook and before the surfaces/city are created -
       replicates the -windowed and -fix16 the routine was validated under. */
    patch_windowed(gz);
    patch_startres(gz);   /* no-op when the loader notification ran */
    patch_surfacefmt(gz);
    if (g_thickframe) patch_frame_style(gz);   /* WINDOWED-EARLY block: no-op when the loader notification ran */
    patch_gridb_clamp(ss);   /* FIX A: clamp the grid-B bucket index (OOB AV root cause) */
    {   char v[8];
        if (GetEnvironmentVariableA("SC3RESIZE_CELLFIX", v, sizeof(v))) g_cellfix = atoi(v);
        if (GetEnvironmentVariableA("SC3RESIZE_DIRTCLIP", v, sizeof(v))) g_dirtclip = atoi(v); }
    patch_dirtclip(ss);      /* the SIMDIRT 0x10013A8F crash: dirty cells past the view (DIRTCLIP block) */
    {   char v[8];
        if (GetEnvironmentVariableA("SC3RESIZE_LCENTER", v, sizeof(v))) g_lcenter = atoi(v); }
    patch_lcenter(ss);       /* left click / minimap centre on the visible map area (LCENTER block) */
    {   char v[8];
        if (GetEnvironmentVariableA("SC3RESIZE_ZOOMCENTER", v, sizeof(v))) g_zoomcenter = atoi(v); }
    patch_zoomcenter(ss);    /* zoom / rotate keep the map-area centre tile (ZOOMCENTER block) */
    patch_setdrag(ss);       /* task cityzoom DRAGANCHOR: a right-drag keeps its anchor across zoom steps */
    {   char v[8];
        if (GetEnvironmentVariableA("SC3RESIZE_TIPCURSOR", v, sizeof(v))) g_tipcursor = atoi(v);
        if (GetEnvironmentVariableA("SC3RESIZE_TIPCURSOR_PX", v, sizeof(v))) g_tipcursor_px = atoi(v); }
    patch_tipcursor(ss);     /* cost label clear of a large pointer (TIPCURSOR block) */
    {   char v[8];
        if (GetEnvironmentVariableA("SC3RESIZE_DIRTGUARD", v, sizeof(v))) g_dirtguard = atoi(v); }
    CreateThread(NULL, 0, dirtguard_watcher, NULL, 0, NULL);


    /* v3: the create-recorder hook (idx 2) is DROPPED - it crashed the game at startup in v2
       (verify/resize_ship RUN 2). Reverts to the known-good two-hook set. The tuple therefore comes
       from field read-back, which rendered the visible region correctly in run 1 (8019 colours); the
       replay logs loudly that it used read-back so the p3 7-vs-4 caveat stays on the record. */
    if (!install_one(0x10016eba, ss, RVA_BRIDGE_INIT, "bridge_capture", 0)) return 0;
    if (!install_one(0x10018c58, gz, GZ_RVA_HEARTBEAT, "frame_heartbeat", 1)) return 0;
    logf("### RESIZE: armed - windowed+fix16 applied, bridge capture at SIMSPR+0x%X, "
         "per-frame poll at GZGraphicD+0x%X (create recorder DROPPED after v2 crash)",
         RVA_BRIDGE_INIT, GZ_RVA_HEARTBEAT);

    /* HUD: NATIVE by default (the shipped viewport build). The bottom bar can be docked + spanned
       full-width via its own SetRect (attempt 3), but full-width carries a per-frame cost that scales
       with width, and true per-widget reflow hit engine class/offset mismatches. Full history:
       verify/resize_hud/RESULTS.md.

       WITH SC3RESIZE_HUDLAB=1 the lab arms instead (verify/resize_hudlab/PRE.md): install the producer
       wrap to capture g_hud_top, start the EIP sampler thread, and let step 12 run the A/B phases. The
       two claims that closed this workstream - "intrinsic per-frame composite cost" and "the children
       are an unknown class" - were both reached by inference, and this measures them.

       The wrap MUST be installed before the HUD constructs (the producer runs at construction; we do
       NOT drive a rebuild - that approach is falsified and stays disabled). SIMUI loads LATER than
       SIMSPR/GZGraphicD, so a one-shot check missed it (2026-08-31, "capture NOT armed"). WAIT for
       SIMUI here (up to ~30 s) - still well before the city/HUD build. */
    if (!g_hudfit && !g_hudlab) {
        logf("### RESIZE: HUD stays NATIVE (SC3RESIZE_HUDNATIVE=1) - viewport only");
        (void)patch_hud_reflow;   /* referenced to avoid an unused-function warning; not installed */
        return 0;
    }
    { int st = 0; HMODULE sui = NULL;
      while (st++ < 300 && !(sui = GetModuleHandleA("SIMUI.DLL"))) Sleep(100);
      if (sui) {
          patch_hud_reflow(sui);
          patch_fieldbg(sui);
          /* Side panel: capture `this` at its constructor so the vertical tiling routine
             FUN_1004e63e (vtable +0x144) has an object to work on. Read-only for now. */
          install_one((DWORD)sui + 0x4e123, sui, 0x4e123, "SIMUI FUN_1004e123 side ctor", 3);
          /* minimap candidates - same +0x144 draw slot, no tile loop */
          install_one((DWORD)sui + 0x1a983, sui, 0x1a983, "SIMUI FUN_1001a983 ctor A", 4);
          install_one((DWORD)sui + 0x60ba9, sui, 0x60ba9, "SIMUI FUN_10060ba9 ctor B", 5);
          /* the generic window painter - where the minimap is identified by its dest rect */
          install_one((DWORD)sui + 0x6d2d0, sui, 0x6d2d0, "SIMUI FUN_1006d2d0 painter", 6);
          if (g_cdcdlog) { rz_hook_cdcd(sui); rz_hook_e81c(sui); rz_hook_cac8(sui); }  /* flyout diag detours */
          ho_install(sui);   /* HUDOPT: HUD scale controls in the Preferences dialog */
          rz_meet_hook(sui); /* DLGSTAY: the Reunirse pages share one stored position */
          qi_install(sui);   /* QUERYID: "Copiar ID" button in the query (?) dialog */
          pk_install();      /* PANCURSOR: right-drag keeps the four-way cursor */
      }
      else logf("--- HUD: SIMUI.DLL never loaded after %d tries - capture NOT armed, HUD stays native", st); }
    if (g_hudlab) {
        DWORD tid;
        HANDLE ph = CreateThread(NULL, 0, rz_prof_thread, NULL, 0, &tid);
        if (ph) { CloseHandle(ph); logf("### HUDLAB: EIP sampler thread started (tid %lu)", tid); }
        else     logf("### HUDLAB: FAILED to start the sampler thread (%lu)", GetLastError());
    }
    return 0;
}

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        g_self = (HMODULE)inst;
        DisableThreadLibraryCalls(inst);
        InitializeCriticalSection(&g_lock);
        QueryPerformanceFrequency(&g_freq);
        QueryPerformanceCounter(&g_t0);
        log_open();
        { char v[16];
          g_minzoom = GetEnvironmentVariableA("SC3RESIZE_MINZOOM", v, sizeof(v)) && atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_READYMS", v, sizeof(v)) && atoi(v) >= 0)
              g_ready_ms = (DWORD)atoi(v);
          g_census = GetEnvironmentVariableA("SC3RESIZE_CENSUS", v, sizeof(v)) && atoi(v);
          g_hudlab = GetEnvironmentVariableA("SC3RESIZE_HUDLAB", v, sizeof(v)) && atoi(v);
          g_sweepon = GetEnvironmentVariableA("SC3RESIZE_SWEEP", v, sizeof(v)) && atoi(v);
          g_sideon  = GetEnvironmentVariableA("SC3RESIZE_SIDE",  v, sizeof(v)) && atoi(v);
          g_minion  = GetEnvironmentVariableA("SC3RESIZE_MINI",  v, sizeof(v)) && atoi(v);
          g_anchor  = GetEnvironmentVariableA("SC3RESIZE_ANCHOR", v, sizeof(v)) && atoi(v);
          /* Cluster mode (the HUD follows the window) ships ON - owner pass 2026-10-06. =0 opts out. */
          g_cluster = 1;
          if (GetEnvironmentVariableA("SC3RESIZE_CLUSTER", v, sizeof(v))) g_cluster = atoi(v);
          g_input   = GetEnvironmentVariableA("SC3RESIZE_INPUT",   v, sizeof(v)) && atoi(v);
          g_nohit   = GetEnvironmentVariableA("SC3RESIZE_NOHIT",   v, sizeof(v)) && atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_HUDDY", v, sizeof(v))) g_hud_dy = (LONG)atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_SIDEDY", v, sizeof(v))) g_side_dy = (LONG)atoi(v);
          g_side_poll = GetEnvironmentVariableA("SC3RESIZE_SIDEPOLL", v, sizeof(v)) && atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_SRCRECT", v, sizeof(v))) g_srcrect = atoi(v);
          g_presentlog = GetEnvironmentVariableA("SC3RESIZE_PRESENTLOG", v, sizeof(v)) && atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_PRESENTFIX", v, sizeof(v))) g_presentfix = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_RCIFIX", v, sizeof(v))) g_rcifix = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_SUBMOVE", v, sizeof(v))) g_submove = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_CDCDLOG", v, sizeof(v))) g_cdcdlog = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_RTP3", v, sizeof(v))) g_rt_p3 = (LONG)atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_RTP7", v, sizeof(v))) g_rt_p7 = (LONG)atoi(v);
          g_sysmem = GetEnvironmentVariableA("SC3RESIZE_SYSMEM", v, sizeof(v)) && atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_WALIGN", v, sizeof(v))) g_walign = (LONG)atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_WSNAP", v, sizeof(v))) g_wsnap = (LONG)atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_BARSPAN", v, sizeof(v))) g_bar_span = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_SIDESPAN", v, sizeof(v))) g_side_span = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_KIDFIX", v, sizeof(v))) g_kidfix = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_ARTGUARD", v, sizeof(v))) g_artguard = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_FIELDBG", v, sizeof(v))) g_fieldbg = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_MENUBG", v, sizeof(v))) g_menubg = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_HUDOPT", v, sizeof(v))) g_hudopt = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_PERFPREFS", v, sizeof(v))) g_perfprefs = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_QUERYID", v, sizeof(v))) g_queryid = atoi(v);
          if (g_hudopt) ho_load_ini();   /* HUDOPT: the Preferences choice, env vars below still override */
          if (GetEnvironmentVariableA("SC3RESIZE_HUDSCALE", v, sizeof(v))) { g_hudscale = atoi(v); g_ho_env |= 1; }
          if (GetEnvironmentVariableA("SC3RESIZE_HUDSCALE_FILTER", v, sizeof(v))) { g_hs_filter = atoi(v); g_ho_env |= 2; }
          if (GetEnvironmentVariableA("SC3RESIZE_HUDSCALE_KEY", v, sizeof(v))) g_hs_key = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_HUDSCALE_MLOG", v, sizeof(v))) g_hs_mlog = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_HUDSCALE_DIAG", v, sizeof(v))) g_hs_diag = atoi(v);
          GetEnvironmentVariableA("SC3RESIZE_HUDSCALE_DUMP", g_hs_dump, sizeof(g_hs_dump));
          GetEnvironmentVariableA("SC3RESIZE_FRAMEDUMP", g_fd_prefix, sizeof(g_fd_prefix));
          {   char ip[MAX_PATH];   /* task cityzoom: sc3resize.ini [view] zoomextra, env wins */
              ho_ini_path(ip, sizeof(ip));
              g_cz_mode = GetPrivateProfileIntA("view", "zoomextra", 1, ip);
              if (GetEnvironmentVariableA("SC3RESIZE_CITYZOOM", v, sizeof(v))) g_cz_mode = atoi(v);
              if (GetEnvironmentVariableA("SC3RESIZE_CITYZOOM_DIAG", v, sizeof(v))) g_cz_diag = atoi(v);
              if (GetEnvironmentVariableA("SC3RESIZE_CITYZOOM_DEFER", v, sizeof(v))) g_cz_defer = atoi(v);
              if (GetEnvironmentVariableA("SC3RESIZE_CITYZOOM_SKIP", v, sizeof(v))) g_cz_skipon = atoi(v);
              if (GetEnvironmentVariableA("SC3RESIZE_CITYZOOM_DEFER1", v, sizeof(v))) g_cz_defer1 = atoi(v);
              if (GetEnvironmentVariableA("SC3RESIZE_CITYZOOM_DRAGANCHOR", v, sizeof(v))) g_cz_draganchor = atoi(v);
              if (GetEnvironmentVariableA("SC3RESIZE_HUDPERF_MASK", v, sizeof(v))) g_hp_mask = atoi(v);
              if (GetEnvironmentVariableA("SC3RESIZE_HUDPERF_MT", v, sizeof(v))) g_hp_mt = atoi(v);
              if (GetEnvironmentVariableA("SC3RESIZE_HUDSCALE_EPXINC", v, sizeof(v))) g_hs_epxinc = atoi(v);
              if (GetEnvironmentVariableA("SC3RESIZE_HUDSCALE_EPXCHECK", v, sizeof(v))) g_hs_epxcheck = atoi(v);
              if (GetEnvironmentVariableA("SC3RESIZE_CITYZOOM_MOVENEAREST", v, sizeof(v))) g_cz_movenear = atoi(v);
              logf("CITYZOOM> zoomextra=%d (%s): zoom past the closest level adds %s%s", g_cz_mode,
                   g_cz_mode ? "on" : "off", g_cz_mode == 2 ? "x2" : "x2 and x3, as the window allows",
                   g_zoomcenter ? "" : " - NOT AVAILABLE, it rides on ZOOMCENTER (SC3RESIZE_ZOOMCENTER=0)");
          }
          if (GetEnvironmentVariableA("SC3RESIZE_HUDFIX", v, sizeof(v))) g_hudfix = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_HUDSCALE_MINISMOOTH", v, sizeof(v))) g_hs_minismooth = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_HUDPERF", v, sizeof(v))) g_hudperf = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_HUDPERF_CHECK", v, sizeof(v))) g_hp_check = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_HUDPERF_LAZY", v, sizeof(v))) g_hp_lazy = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_HUDSCALE_REPOST", v, sizeof(v))) g_hs_repost = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_HUDSCALE_FLOATALL", v, sizeof(v))) g_hs_floatall = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_MENUBGSTOCK", v, sizeof(v))) g_menubg_stock = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_MENUBGFIT", v, sizeof(v))) g_menubg_fit = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_MENUSCALE", v, sizeof(v))) g_menuscale = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_HSCENSUS", v, sizeof(v))) g_hs_census = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_PANCURSOR", v, sizeof(v))) g_pancursor = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_MENUSCALE_FILTER", v, sizeof(v))) g_ms_filter = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_MENUSCALE_REPOST", v, sizeof(v))) g_ms_repost = atoi(v);
          GetEnvironmentVariableA("SC3RESIZE_MENUSCALE_DUMP", g_ms_dump, sizeof(g_ms_dump));
          if (GetEnvironmentVariableA("SC3RESIZE_MENUSCALE_FULLBLIT", v, sizeof(v))) g_ms_fullblit = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_MENUSCALE_REFRESH", v, sizeof(v))) g_ms_refresh = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_HOLD", v, sizeof(v))) g_hold = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_DEFERRESIZE", v, sizeof(v))) g_deferresize = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_SIMLOCK", v, sizeof(v))) g_simlock = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_SKIPREFRESH", v, sizeof(v))) g_skiprefresh = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_ZOOMKEYS", v, sizeof(v))) g_zoomkeys = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_PAUSEKEY", v, sizeof(v))) g_pausekey = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_SPEEDKEYS", v, sizeof(v))) g_speedkeys = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_CLOSEX", v, sizeof(v))) g_closex = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_KEYFOCUS", v, sizeof(v))) g_keyfocus = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_MINICLASS", v, sizeof(v))) g_miniclass = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_DLGKEEP", v, sizeof(v))) g_dlgkeep = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_DLGAREA", v, sizeof(v))) g_dlgarea = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_DLGSTAY", v, sizeof(v))) g_dlgstay = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_MEETALL", v, sizeof(v))) g_meetall = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_BAR800", v, sizeof(v))) g_bar800 = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_HUDREFLOW", v, sizeof(v))) g_hudreflow = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_CLOSEFLY", v, sizeof(v))) g_closefly = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_EDGEFIX", v, sizeof(v))) g_edgefix = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_EDGESCROLL", v, sizeof(v))) g_edgescroll = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_VIEWFIX", v, sizeof(v))) g_viewfix = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_DIALOGS", v, sizeof(v))) g_dialogs = atoi(v);
          g_bltbeat = GetEnvironmentVariableA("SC3RESIZE_BLTBEAT", v, sizeof(v)) && atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_THICKFRAME", v, sizeof(v))) g_thickframe = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_FSKEY", v, sizeof(v))) g_fskey = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_DLGSCALE", v, sizeof(v))) g_dlgscale = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_COSTLABEL_SCALE", v, sizeof(v))) g_costscale = atoi(v);   /* task uiscale */
          if (GetEnvironmentVariableA("SC3RESIZE_WINMEM", v, sizeof(v))) g_winmem = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_RESROW", v, sizeof(v))) g_resrow = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_STARTRES", v, sizeof(v))) g_startres = atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_EARLY", v, sizeof(v))) g_early = atoi(v);
          if (!GetEnvironmentVariableA("SC3RESIZE_DUMPDIR", g_dumpdir, sizeof(g_dumpdir)))
              lstrcpynA(g_dumpdir, ".", sizeof(g_dumpdir));
          g_noparentfix = GetEnvironmentVariableA("SC3RESIZE_NOPARENTFIX", v, sizeof(v)) && atoi(v);
          /* HUD dock+span ships ON. SC3RESIZE_HUDNATIVE=1 is the opt-out for anyone who prefers the
             native bar - the full-width bar carries a measured GPU-sync FPS cost that is NOT yet
             resolved (verify/resize_hudlab: two causes eliminated, mechanism still open). */
          if (GetEnvironmentVariableA("SC3RESIZE_HUDNATIVE", v, sizeof(v)) && atoi(v)) g_hudfit = 0; }
        logf("### sc3resize loaded - resizable-window mod (minimal Init-free routine, "
             "validated 2026-08-27 over 6 runs)%s%s", g_minzoom ? " [MINZOOM crash-hunt build]" : "",
             g_hudlab ? " [HUD LAB armed: surface census + EIP profiler, verify/resize_hudlab]" : "");
        if (g_hudopt)
            logf("HUDOPT> on: scale %d smooth %d (sc3resize.ini [hud]%s%s)", g_hudscale, g_hs_filter,
                 (g_ho_env & 1) ? ", scale from SC3RESIZE_HUDSCALE" : "", (g_ho_env & 2) ? ", smooth from SC3RESIZE_HUDSCALE_FILTER" : "");
        logf("PERFPREFS> %s", !g_hudopt ? "off (rides on HUDOPT, which is off)" : g_perfprefs ? "on: FPS/profiler boxes in Preferences when sc3perf.dll exports them"
             : "off (SC3RESIZE_PERFPREFS=0)");
        if (g_hudscale)
            logf("HUDSCALE> ON (prototype): %s, filter %s, HUDFIX %d (minimap Scale2x %d)", g_hudscale >= 100 ? "fixed percent, capped at min(cw/800, ch/600)"
                 : "factor min(cw/800, ch/600)", g_hs_filter ? "bilinear" : "nearest", g_hudfix, g_hs_minismooth);
        if (g_hudscale && g_hudfix)
            logf("HUDPERF> %s%s", g_hudperf ? "on: cached enlarged HUD, only changed parts resampled" : "off (SC3RESIZE_HUDPERF=0): every pixel resampled every frame",
                 g_hudperf && g_hp_check ? ", CHECK on: the hudfix pass also runs and every differing pixel is counted" : "");
        /* ⭐ Echo EVERY parsed flag, unconditionally, at init.
         *
         * Attempt 1 of the NOHIT experiment (2026-09-01) was VOID because none of three env vars
         * reached the DLL - auto.ps1 was invoked with `-EnvVars` under `pwsh -File`, the exact form
         * HANDOFF.md warns embeds quotes. The log looked completely healthy: city loaded, resize
         * fired, HUD refitted, zero faults. Nothing said "your flags are off", and the previous
         * session lost three features the same way ("wired behind the wrong flag", each invisible in
         * a self-consistent log). One line makes the whole class loud instead of silent.
         * verify/resize_flaggate/NOHIT_RESULTS.md */
        logf("### FLAGS> cluster=%d input=%d nohit=%d hudfit=%d hudlab=%d sweep=%d side=%d mini=%d "
             "anchor=%d census=%d minzoom=%d readyms=%lu noparentfix=%d huddy=%ld sidedy=%ld presentlog=%d kidfix=%d artguard=%d edgefix=%d edgescroll=%d barspan=%d sidespan=%d viewfix=%d dialogs=%d menubg=%d menubgstock=%d menubgfit=%d",
             g_cluster, g_input, g_nohit, g_hudfit, g_hudlab, g_sweepon, g_sideon, g_minion,
             g_anchor, g_census, g_minzoom, g_ready_ms, g_noparentfix, g_hud_dy, g_side_dy, g_presentlog,
             g_kidfix, g_artguard, g_edgefix, g_edgescroll, g_bar_span, g_side_span, g_viewfix, g_dialogs, g_menubg, g_menubg_stock, g_menubg_fit);
        logf("### FLAGS> dlgstay=%d (Reunirse keeps its position, verify/reunirse) meetall=%d (all five pages, verify/reunirse2)",
             g_dlgstay, g_meetall);
        logf("### FLAGS> menuscale=%d filter=%s repost=%d fullblit=%d refresh=%d dump=%s", g_menuscale,
             g_ms_filter ? "bilinear" : "nearest", g_ms_repost, g_ms_fullblit, g_ms_refresh, g_ms_dump[0] ? g_ms_dump : "-");
        if (AddVectoredExceptionHandler(1, rz_veh))
            logf("### VEH crash logger installed (logs any hardware fault MODULE+RVA - for the "
                 "zoom-after-resize crash the game swallows)");
        else
            logf("### VEH crash logger FAILED to install");
        {   char ip[MAX_PATH], v[8];
            rz_mb_path(ip, sizeof(ip), "sc3resize.ini");
            if (ip[0]) g_dpiaware = GetPrivateProfileIntA("display", "dpiaware", 1, ip) ? 1 : 0;
            if (GetEnvironmentVariableA("SC3RESIZE_DPIAWARE", v, sizeof(v))) g_dpiaware = atoi(v) ? 1 : 0; }
        logf("### FLAGS> early=%d thickframe=%d dpiaware=%d", g_early, g_thickframe, g_dpiaware);
        if (g_dpiaware) rz_dpi_aware();
        if (g_early) rz_early_register();
        CreateThread(NULL, 0, intro_watcher, NULL, 0, NULL);   /* INTRO block: UV.DLL writer re-target
                                                                   (UV.DLL loads early, own thread) */
        CreateThread(NULL, 0, rz_watcher, NULL, 0, NULL);
    }
    return TRUE;
}






































