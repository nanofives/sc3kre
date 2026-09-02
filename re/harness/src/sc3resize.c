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
    if (g_log != INVALID_HANDLE_VALUE)
        WriteFile(g_log, line, (DWORD)n, &wrote, NULL);
    LeaveCriticalSection(&g_lock);
    OutputDebugStringA(line);
}

static void log_open(void) {
    char path[MAX_PATH];
    if (!GetEnvironmentVariableA("SC3RESIZE_LOG", path, sizeof(path)))   /* [RESIZE] own default */
        lstrcpynA(path, "sc3resize.log", sizeof(path));
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
    VirtualProtect(t, (SIZE_T)len, old, &old);
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
#define SIDE_NAT_H   442   /* native side-panel height, measured rect [704 0 800 442] */
#define WIN_MAX      48
#define ANCHOR_EDGE  12
#define NAT_W        800
#define NAT_H        600
static struct { void *w; LONG nat[4]; } g_wins[WIN_MAX];
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
static void rz_side_fit_surface(DWORD liveH);
/* SC3RESIZE_HUDDY - extra downward bias applied to the whole relocated HUD, on top of the
 * (client - native) translate. Owner-tuned to 8 px on 2026-09-02 at 2048x1081: at bias 0 the bar's
 * bottom lands exactly on the client edge and a black strip shows below it; at 8 the bar, RCI,
 * minimap and corner button all sit where the owner wants them.
 * ⚠️ This is a POSITION bias only. HUD art is TOP-ANCHORED in its rect, so a rect taller than the
 * art paints the surplus black - do not implement this by growing rects. Measured: a 72-tall bar
 * (art 56) produced exactly the "black bar below the bottom bar" the owner reported. */
static LONG   g_hud_dy = 8;
/* SC3RESIZE_SIDEDY - lift the side panel's contents (pages, tabs AND the background art) by this
 * many px from the panel bottom. Owner, 2026-09-02: with 0 the group sat "too shifted down" and
 * three buttons fell out of view. ONE knob feeds both the art placement in rz_side_fit_child and
 * the child move in rz_side_children_bottom, so those two can never drift apart - keeping them in
 * lockstep is the whole reason it is a single global. */
static LONG   g_side_dy;
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
        ax = (n[2] >= NAT_W - ANCHOR_EDGE) ? dx : 0;    /* touching the native right edge  */
        ay = (n[3] >= NAT_H - ANCHOR_EDGE) ? dy : 0;    /* touching the native bottom edge */
        if (ax == 0 && ay == 0) continue;               /* left/top anchored - leave it    */
        r = (LONG *)((DWORD)w + 0x90);
        r[0] = n[0] + ax; r[1] = n[1] + ay;
        r[2] = n[2] + ax; r[3] = n[3] + ay;
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
static void rz_cluster_layout(void) {
    RECT cr;
    LONG dx, dy, i, moved = 0;
    if (!g_cluster || !g_hwnd || !GetClientRect(g_hwnd, &cr)) return;
    dx = (cr.right - cr.left) - NAT_W;
    dy = (cr.bottom - cr.top) - NAT_H;
    if (dx <= 0 && dy <= 0) { logf("CLUSTER> window not larger than native - nothing to do"); return; }
    dy += g_hud_dy;   /* owner-tuned bottom bias; see g_hud_dy */

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

    if (g_bar_nat_ok)
        rz_win_setrect(g_hud_top, "bottom bar", g_bar_nat[0] + dx, g_bar_nat[1] + dy,
                       g_bar_nat[2] + dx, g_bar_nat[3] + dy);
    if (g_side_nat_ok)
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
    logf("CLUSTER> translated %ld painter windows by (%ld,%ld); HUD kept at native size",
         moved, dx, dy);
    {   /* Report paint rect vs WINDOW rect for the first few, so a future divergence is visible in
           the log instead of only on screen - this run's clickability bug was invisible in the log. */
        LONG k;
        for (k = 0; k < g_wins_n && k < 6; k++) {
            DWORD *w = (DWORD *)g_wins[k].w;
            LONG *p;
            if (!w || IsBadReadPtr(w, 0xa0)) continue;
            p = (LONG *)((DWORD)w + 0x90);
            logf("CLUSTER>   [%ld] 0x%08lX paint=[%ld %ld %ld %ld] window=[%ld %ld %ld %ld]%s",
                 k, (DWORD)w, p[0], p[1], p[2], p[3],
                 (LONG)w[0x14/4], (LONG)w[0x18/4], (LONG)w[0x1c/4], (LONG)w[0x20/4],
                 (p[0] == (LONG)w[0x14/4] && p[1] == (LONG)w[0x18/4]) ? "" : "   <<< PAINT/WINDOW DIVERGE");
        }
    }
    {   /* THE CLICKABILITY FIX. Widen every ancestor of the relocated windows so the router's
           per-child `vt+0xe4` gate can pass and the recursion that reaches the HUD can start.
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
            logf("PARENT> %s hop %d: 0x%08lX rect [%ld %ld %ld %ld] non-positive - refusing",
                 name, hop, (DWORD)par, r[0], r[1], r[2], r[3]);
            return;
        }
        if (r[2] < cw || r[3] < ch) {
            logf("PARENT> %s hop %d: 0x%08lX [%ld %ld %ld %ld] -> [%ld %ld %ld %ld]",
                 name, hop, (DWORD)par, r[0], r[1], r[2], r[3],
                 r[0], r[1], (r[2] < cw) ? cw : r[2], (r[3] < ch) ? ch : r[3]);
            if (r[2] < cw) r[2] = cw;
            if (r[3] < ch) r[3] = ch;
        } else {
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
 * NOT fixed here, deliberately, and both documented in SESSION.md:
 *   - Edge-scroll bands `+0x178..+0x1c4`: rebuilt by `FUN_10043989` from the same bounds rect and
 *     re-run from `FUN_10044323`, so hand-written bands cannot survive. Widening the source rect
 *     (item 3) is the correct half; the rebuild call is untested and is not made here.
 *     `[CONFIRMED @ SIMSPR 0x10043989, 0x10044323]`
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
            if (vt && !IsBadReadPtr(vt, 0xe8) && vt[0xe4 / 4] == want_e4) return cw;
            {   void *hit = rz_find_view(cw, want_e4, depth + 1, budget);
                if (hit) return hit;   }
        }
        n = *(void **)n;
    }
    return NULL;
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
static void rz_side_children_bottom(void) {
    DWORD *p = (DWORD *)g_side_top;
    void *head, *n;
    LONG panelH, dy;
    int guard = 0, moved = 0;
    /* the caller already gates on g_sideon && !g_cluster (both declared further down the file) */
    if (!p || IsBadReadPtr(p, 0xa0)) { logf("SIDEKIDS> skipped: side panel unreadable"); return; }
    panelH = (LONG)p[0x20 / 4] - (LONG)p[0x18 / 4];
    /* ⚠️ NEVER recompute the delta from the live panel height inside a repeating pass.
     *
     * Measured 2026-09-02, 17 s after a clean layout: the panel's height read 2178 = 2 x 1089 and
     * this routine "pushed 2 side-panel child(ren) down by 1586". Recomputing dy from a height
     * that something else can grow makes the pass feed on its own output - a runaway. The delta is
     * captured ONCE by the resize-time call and reused verbatim afterwards, and a panel taller
     * than the window is refused outright rather than acted on. */
    {   RECT ccr;
        LONG maxH = (g_hwnd && GetClientRect(g_hwnd, &ccr)) ? (ccr.bottom - ccr.top) : 0;
        if (maxH > 0 && panelH > maxH + RZ_SURFACE_SLACK) {
            logf("SIDEKIDS> REFUSED: panel %ld tall exceeds the %ld-px client - not touching it",
                 panelH, maxH);
            return;
        }
    }
    if (g_side_dy_applied > 0) {
        dy = g_side_dy_applied;               /* the delta from the resize-time pass, verbatim */
    } else {
        dy = panelH - SIDE_NAT_H - g_side_dy;
        if (dy > 0) g_side_dy_applied = dy;   /* capture once */
    }
    if (dy <= 0) return;                      /* silent: this runs on a timer */
    head = *(void **)((DWORD)p + 0x34);
    if (!head || IsBadReadPtr(head, 4)) { logf("SIDEKIDS> skipped: no child list"); return; }
    n = *(void **)head;
    while (n && n != head && guard++ < 300) {
        DWORD *c;
        if (IsBadReadPtr(n, 0x0c)) break;
        c = *(DWORD **)((DWORD)n + 8);
        if (c && !IsBadWritePtr(c, 0xa0)) {
            LONG *e = (LONG *)((DWORD)c + 0x80);       /* PARENT-LOCAL rect - what SetRect wants */
            DWORD *vt = *(DWORD **)c;
            /* IDEMPOTENCE, and it is what lets this be re-run.
             *
             * A child already sitting at or below `dy` has been placed by a previous pass; moving
             * it again would push it down by another `dy` every call. Skipping those makes the
             * whole routine safe to call repeatedly, which is required because the game creates
             * windows LATER: the owner opened a tool submenu and it rendered at the top of the
             * strip (2026-09-02), because it did not exist when the resize ran. In the steady state
             * every child fails this test, so a periodic pass issues zero SetRect calls. */
            if (vt && !IsBadReadPtr(vt, 0xcc) && vt[0xc8 / 4] &&
                e[2] - e[0] > 0 && e[3] - e[1] > 0 && e[3] + dy <= panelH && e[1] < dy) {
                DWORD a[4];
                a[0] = (DWORD)e[0]; a[1] = (DWORD)(e[1] + dy);
                a[2] = (DWORD)e[2]; a[3] = (DWORD)(e[3] + dy);
                rz_thiscall(c, (void *)vt[0xc8 / 4], a, 4);
                moved++;
            }
        }
        n = *(void **)n;
    }
    if (moved)   /* silent when there is nothing to place - this runs on a timer */
        logf("SIDEKIDS> pushed %d side-panel child(ren) down by %ld (panel %ld tall, native %d)",
             moved, dy, panelH, SIDE_NAT_H);
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
    if (!view) { logf("GEOM> city view NOT FOUND (vt+0xe4 != SIMSPR+0x4ecd3) - map/camera unfixed"); return; }
    if (IsBadWritePtr(view, 0xe4)) { logf("GEOM> city view 0x%08lX unwritable", (DWORD)view); return; }
    {   LONG *r = (LONG *)((DWORD)view + 0x14);
        LONG *b = (LONG *)((DWORD)view + 0xd4);
        logf("GEOM> city view 0x%08lX hit [%ld %ld %ld %ld] bounds [%ld %ld %ld %ld]",
             (DWORD)view, r[0], r[1], r[2], r[3], b[0], b[1], b[2], b[3]);
        if (r[2] < cw) r[2] = cw;
        if (r[3] < ch) r[3] = ch;
        if (b[2] < cw) b[2] = cw;
        if (b[3] < ch) b[3] = ch;
        logf("GEOM> city view    hit [%ld %ld %ld %ld] bounds [%ld %ld %ld %ld]  (map clicks + camera pan)",
             r[0], r[1], r[2], r[3], b[0], b[1], b[2], b[3]);
    }

    /* 4. native-corner widgets, DIRECT children of the root only. */
    {   void *head = *(void **)((DWORD)root + 0x34);
        void *n;
        int guard = 0, moved = 0;
        if (!head || IsBadReadPtr(head, 4)) return;
        n = *(void **)head;
        while (n && n != head && guard++ < 500) {
            DWORD *c;
            if (IsBadReadPtr(n, 0x0c)) break;
            c = *(DWORD **)((DWORD)n + 8);
            if (c && !IsBadWritePtr(c, 0xa0)) {
                LONG *r = (LONG *)((DWORD)c + 0x14);
                /* fits inside the native screen AND is anchored to its bottom-right corner AND is
                   actually a small widget.
                   ⚠️ The size bound is not cosmetic. Without it a FULL-SCREEN window whose rect is
                   [0 0 800 600] passes both other tests - it "touches" the bottom-right corner - and
                   gets translated off to the right. Measured 2026-09-02 on the dock+span path
                   (`GEOM> corner widget 0x00644140 [0 0] -> [1248 489]`), where cluster mode had
                   masked it because the parent fix widens that window first. The real widget is
                   26x26. */
                int fits = r[0] >= 0 && r[1] >= 0 && r[2] <= NAT_W && r[3] <= NAT_H;
                int corner = r[2] >= NAT_W - 40 && r[3] >= NAT_H - 40;
                int is_small = (r[2] - r[0]) > 0 && (r[2] - r[0]) <= 200 &&
                            (r[3] - r[1]) > 0 && (r[3] - r[1]) <= 200;
                /* ⚠️ exclude the hover label: it parks near the old corner between hovers and its
                   position is recomputed from the cursor anyway, so moving it is noise. Measured
                   2026-09-02 - the first version of this heuristic matched it. */
                int is_label = sc3 && c[0] == sc3 + 0xd3bcc;
                if (fits && corner && is_small && !is_label) {
                    DWORD *vt = *(DWORD **)c;
                    if (vt && !IsBadReadPtr(vt, 0xcc) && vt[0xc8 / 4]) {
                        LONG *e = (LONG *)((DWORD)c + 0x80);
                        LONG ox = r[0], oy = r[1], nx = r[0] + dx, ny = r[1] + dy;
                        int ext_abs = (e[0] == r[0] && e[1] == r[1]);   /* absolute, not parent-local */
                        DWORD a[4];
                        a[0] = (DWORD)nx;        a[1] = (DWORD)ny;
                        a[2] = (DWORD)(r[2]+dx); a[3] = (DWORD)(r[3]+dy);
                        rz_thiscall(c, (void *)vt[0xc8 / 4], a, 4);
                        if (ext_abs) { e[0] = nx; e[1] = ny; e[2] = (LONG)a[2]; e[3] = (LONG)a[3]; }
                        logf("GEOM> corner widget 0x%08lX [%ld %ld] -> [%ld %ld]%s",
                             (DWORD)c, ox, oy, nx, ny, ext_abs ? " (hit rect carried)" : " (hit rect parent-local, left alone)");
                        moved++;
                    }
                }
            }
            n = *(void **)n;
        }
        logf("GEOM> relocated %d native-corner widget(s) by (%ld,%ld)", moved, dx, dy);
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
    if (r[0] == nx && r[1] == ny) { logf("MINI> already docked at [%ld,%ld]", nx, ny); return; }
    {   /* capture the OLD position before overwriting - the hit-origin move verifies against it */
        LONG ox = r[0], oy = r[1];
        logf("MINI> dock [%ld %ld %ld %ld] -> [%ld %ld %ld %ld]",
             r[0], r[1], r[2], r[3], nx, ny, nx + w, ny + h);
        r[0] = nx; r[1] = ny; r[2] = nx + w; r[3] = ny + h;
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

static HRESULT WINAPI rz_blt_hook(void *self, RECT *dr, void *src, RECT *sr, DWORD fl, void *fx) {
    LARGE_INTEGER a, b;
    HRESULT hr;
    __int64 d;
    QueryPerformanceCounter(&a);
    hr = g_orig_blt(self, dr, src, sr, fl, fx);
    QueryPerformanceCounter(&b);
    d = b.QuadPart - a.QuadPart;
    g_ddblt_time += d;
    g_ddblt_calls++;
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
    if (!VirtualProtect(&svt[0x14 / 4], 4, PAGE_READWRITE, &old)) return;
    g_orig_blt = (RZ_BLT)svt[0x14 / 4];
    svt[0x14 / 4] = (DWORD)rz_blt_hook;
    VirtualProtect(&svt[0x14 / 4], 4, old, &old);
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
static void rz_patch_ddblt(void);           /* fwd: install the ddraw Blt timer */

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
        ca[0] = w;
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
    *((BYTE *)obj + 8) = 0;
    rc = rz_thiscall((void *)obj, (void *)vt[0x0c / 4], ca, 8);
    logf("RZ   %s FUN_10009efb -> %d | now +0x24=%lu +0x28=%lu",
         name, rc, ((DWORD *)obj)[0x24 / 4], ((DWORD *)obj)[0x28 / 4]);
    return 1;
}

/* The routine. Runs on the game thread from the per-frame heartbeat. */
static void rz_do_resize(void *iso, DWORD w, DWORD ht) {
    HMODULE ss = GetModuleHandleA("SIMSPR.DLL"), gz = GetModuleHandleA("GZGraphicD.dll");
    DWORD *v = (DWORD *)iso, *b = (DWORD *)g_bridge;
    DWORD gw = 0, gh = 0, a5[5], a2[2], a3[3], fa[5];
    DWORD R, B;

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
    rz_recreate_raster(B, "device-surface iso+0x4ec", w, ht, gz);

    /* 7. the render lever. */
    g_rz_step = 7;
    fa[0] = 0; fa[1] = b[0x78 / 4]; fa[2] = b[0xa8 / 4]; fa[3] = 0; fa[4] = 0;
    logf("RZ   FUN_10018cdf -> %d",
         rz_thiscall(g_bridge, (void *)((DWORD)ss + RVA_BRIDGE_FILL), fa, 5));

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
    {
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
    logf("SRCRECT> tile step [%ld %ld %ld %ld] step=%ld -> right=%ld step=%lu  (FUN_10026841: "
         "~%ld blits/frame -> ~1)",
         sr[0], sr[1], sr[2], sr[3], sr[2] - sr[0], sr[0] + (LONG)liveW, liveW,
         ((LONG)liveW + (sr[2] - sr[0]) - 1) / (sr[2] - sr[0]));
    sr[2] = sr[0] + (LONG)liveW;
}

static void rz_hud_fit_surface(DWORD liveW) {
    rz_hud_fit_child(0x2a, liveW);
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

    if (liveH == oldh) {
        logf("SIDEFIT> +0x%lx already fitted: surface height %lu == live %lu", off, oldh, liveH);
        return;
    }
    if (!ca->art && oldbits && oldpitch && oldh &&
        !IsBadReadPtr((void *)oldbits, oldpitch * oldh)) {
        ca->art = (BYTE *)HeapAlloc(GetProcessHeap(), 0, oldpitch * oldh);
        if (ca->art) {
            memcpy(ca->art, (void *)oldbits, oldpitch * oldh);
            ca->w = oldw; ca->h = oldh; ca->pitch = oldpitch;
            logf("SIDEFIT> +0x%lx cached pristine art %lux%lu pitch=%lu (one-time)",
                 off, oldw, oldh, oldpitch);
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

    logf("SIDEFIT> +0x%lx=0x%08lX -> refitting to %lux%lu (art %lux%lu)",
         off, obj, oldw, liveH, oldw, oldh);
    if (!rz_recreate_raster(obj, "side child surface", oldw, liveH, gz)) {
        logf("SIDEFIT> +0x%lx recreate REFUSED - left as it was", off);
        return;
    }
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
                LONG panelH_ = (g_side_top && !IsBadReadPtr(g_side_top, 0x24))
                             ? (LONG)((DWORD *)g_side_top)[0x20 / 4] -
                               (LONG)((DWORD *)g_side_top)[0x18 / 4]
                             : (LONG)liveH;
                LONG art_at = panelH_ - SIDE_NAT_H - g_side_dy;
                DWORD plain = (oldh > 8) ? oldh - 4 : oldh - 1;
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

static void rz_side_fit_surface(DWORD liveH) {
    DWORD *p = (DWORD *)g_side_top;
    DWORD want = liveH;
    /* Target the BOTTOM CAP's top edge, and subtract the slack rz_recreate_raster pads on, so the
       finished surface is exactly as tall as the dest rect and the blit does not scale. */
    if (p && !IsBadReadPtr(p, 0x120)) {
        LONG capTop = (LONG)((LONG *)((DWORD)p + 0xf0))[1];
        LONG panelH = (LONG)p[0x20 / 4] - (LONG)p[0x18 / 4];
        LONG target = (capTop > 0 && capTop <= panelH) ? capTop : panelH;
        if (target > RZ_SURFACE_SLACK) want = (DWORD)(target - RZ_SURFACE_SLACK);
        logf("SIDEFIT> target height %ld (cap top %ld, panel %ld) -> requesting %lu + %d slack",
             target, capTop, panelH, want, RZ_SURFACE_SLACK);
    }
    rz_side_fit_child(0, 0xc0, want);
    rz_side_fit_child(1, 0xc8, want);

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
            logf("SIDEFIT> dest rect +0xd0 [%ld %ld %ld %ld] left as-is (cap top %ld, panel %ld)",
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
        if (!setrect || panelW <= 0 || panelW >= lw) {
            logf("SIDE> extend skipped: setrect=0x%08lX panelW=%d lw=%d",
                 (DWORD)setrect, panelW, lw);
            return;
        }
        if (x1 == wantX1 && y1 == 0 && x2 == lw && y2 == wantY2) {
            logf("SIDE> already docked at [%d,0,%d,%d]", wantX1, lw, wantY2); return;
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
static void rz_poll(void) {
    void *iso;
    DWORD *v, R, w, ht;
    RECT cr;

    if (!g_bridge || IsBadReadPtr(g_bridge, 0xf4)) return;
    iso = (void *)((DWORD *)g_bridge)[0x18 / 4];
    if (!iso || IsBadReadPtr(iso, 0x4f0)) return;
    if (!g_hwnd || !IsWindow(g_hwnd) || !GetClientRect(g_hwnd, &cr)) return;

    w  = (DWORD)(cr.right - cr.left);
    ht = (DWORD)(cr.bottom - cr.top);
    if (w == 0 || ht == 0) return;

    /* Late-created side-panel windows. A tool submenu opened after the resize renders at its
       native position (owner, 2026-09-02: "when i open a menu it is rendered at the top"), because
       the layout pass ran before that window existed. rz_side_children_bottom is idempotent - it
       skips anything already placed - so re-running it costs nothing in the steady state and
       catches whatever the game has just built. Rate-limited, and placed BEFORE the settled check
       below, which returns early on every frame once the size stops changing. */
    if (g_sideon && !g_cluster) {
        static DWORD rz_side_next_ms;
        DWORD now = GetTickCount();
        if (now >= rz_side_next_ms) { rz_side_next_ms = now + 400; rz_side_children_bottom(); }
    }

    v = (DWORD *)iso;
    R = v[0x74 / 4];
    if (!R || IsBadReadPtr((void *)R, 0x2c)) return;
    /* SETTLED check. The render target is deliberately over-allocated by RZ_SURFACE_SLACK guard rows
       (zoom-blit overrun fix), so its height (+0x28) is ht..ht+SLACK, NOT exactly ht. Comparing
       == ht made the poll see a permanent mismatch and re-resize EVERY FRAME (churn -> black view +
       a zoom-out race crash, 2026-08-30). Treat width-equal and height within [ht, ht+SLACK] as
       settled; a genuine client-size change still fails this and triggers one resize. */
    if (((DWORD *)R)[0x24 / 4] == w &&
        ((DWORD *)R)[0x28 / 4] >= ht && ((DWORD *)R)[0x28 / 4] <= ht + RZ_SURFACE_SLACK)
        return;   /* nothing to do */

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

    if (InterlockedCompareExchange(&g_busy, 1, 0) != 0) return;                /* re-entrancy */
    logf("RZ   size change: client %lux%lu vs render target %lux%lu", w, ht,
         ((DWORD *)R)[0x24 / 4], ((DWORD *)R)[0x28 / 4]);
    /* CRASH HUNT (2026-08-28): SEH around the routine so a fault becomes a DIAGNOSTIC (code +
       address resolved to MODULE+RVA + which of the 9 steps was executing) instead of a silent
       process death. This is how we catch WHERE the v3 crash actually is. */
    g_rz_step = 0;
    g_exc_code = 0;
    __try {
        rz_do_resize(iso, w, ht);
    } __except (rz_filter(GetExceptionInformation())) {
        char who[128];
        rz_modstr(g_exc_addr, who, sizeof(who));
        logf("RZ   *** FAULT CAUGHT *** code=0x%08lX at %s | executing STEP %ld when it faulted "
             "(1=extent 2=griddims 3=dirtygrid 4=gridB 5=RT 6=devsurf 7=FUN_10018cdf 8=rereg 9=present "
             "10=fullrepaint 11=baseview 12=hudreflow)",
             g_exc_code, who, g_rz_step);
        rz_fault_diag(iso);
    }
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

/* Subclass the game window so a real WM_SIZE publishes the REAL client size.
 * GZGraphicD's own handler (FUN_100185f5, reached via vt+0x30) republishes the window object's
 * STORED size and nothing in the engine updates it on a stock resize, so without the
 * rz_set_stored_rect call below the engine never learns the new size and the primary Blt keeps
 * presenting the old rectangle. Doing it here in C is what makes the separate GZGraphicD
 * `wmsize_setrect` patch unnecessary under this mod. */
static LRESULT CALLBACK rz_wndproc(HWND h, UINT m, WPARAM wp, LPARAM lp) {
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
                    if (!seen && r[0] >= -64 && r[1] >= -64 && r[2] <= NAT_W + 64 && r[3] <= NAT_H + 64 &&
                    (w * h) <= (NAT_W * NAT_H * 7) / 10) {
                    g_wins[g_wins_n].w = (void *)ecx;
                    g_wins[g_wins_n].nat[0] = r[0]; g_wins[g_wins_n].nat[1] = r[1];
                    g_wins[g_wins_n].nat[2] = r[2]; g_wins[g_wins_n].nat[3] = r[3];
                    g_wins_n++;
                }
            }

            if (w >= 100 && w <= 400 && h >= 100 && h <= 400 && w < h * 2 && h < w * 2) {

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
static void patch_windowed(HMODULE gz) {
    BYTE *p = (BYTE *)gz + 0x6cdac;         /* the windowed flag Init reads */
    BYTE *q = (BYTE *)gz + 0x117d6;         /* the fullscreen re-force store */
    DWORD old;
    if (VirtualProtect(p, 1, PAGE_READWRITE, &old)) {
        BYTE before = *p; *p = 1; VirtualProtect(p, 1, old, &old);
        logf("--- WINDOWED: GZGraphicD+0x6cdac = %u -> 1", before);
    } else logf("--- WINDOWED: VirtualProtect failed at +0x6cdac (%lu)", GetLastError());
    if (q[0] == 0xC6 && q[1] == 0x43 && q[2] == 0x48 && q[3] == 0x01) {
        DWORD o2;
        if (VirtualProtect(q, 4, PAGE_EXECUTE_READWRITE, &o2)) {
            q[0] = q[1] = q[2] = q[3] = 0x90; VirtualProtect(q, 4, o2, &o2);
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
    VirtualProtect(site, 10, old, &old);
    FlushInstructionCache(GetCurrentProcess(), site, 10);
    logf("--- FIX16: 16bpp branch injected at 0x19349 -> cave 0x%08lX (5-6-5)", (DWORD)cave);
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
    VirtualProtect(site, 2, old, &old);
    FlushInstructionCache(GetCurrentProcess(), site, 2);
    logf("--- EFA1_GUARD: empty-bucket branch 0xefc2 retargeted to the ret (was -> 0xefe3 deref)");
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
        VirtualProtect(cave, c->nbytes, old, &old);
        FlushInstructionCache(GetCurrentProcess(), cave, c->nbytes);
        if (!VirtualProtect(hook, c->stolen, PAGE_EXECUTE_READWRITE, &old)) {
            logf("--- GRIDB_CLAMP %s: VP(hook) failed %lu", c->name, GetLastError()); continue; }
        rel = c->cave - (c->hook + 5);
        hook[0] = 0xe9; memcpy(hook + 1, &rel, 4);
        for (i = 5; i < c->stolen; i++) hook[i] = 0x90;
        VirtualProtect(hook, c->stolen, old, &old);
        FlushInstructionCache(GetCurrentProcess(), hook, c->stolen);
        logf("--- GRIDB_CLAMP %s: index clamped (hook 0x%X -> cave 0x%X, base 0x%08lX)",
             c->name, c->hook, c->cave, (DWORD)ss);
    }
    patch_efa1_emptybucket(ss);
    logf("--- GRIDB_CLAMP: 4 walkers index-clamped (FIX A) + FUN_1000efa1 null-guarded (FIX C)");
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
static void __cdecl rz_hud_reflow(DWORD *arr) {
    static const int x1i[4] = { 1, 5, 9, 13 };
    static const int x2i[4] = { 3, 7, 11, 15 };
    int native_w, live_w, k;
    RECT cr;
    DWORD tag;
    if (!arr || IsBadWritePtr(arr, 0x74)) return;          /* 0x1d ints */
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
    cave = (BYTE *)VirtualAlloc(NULL, 64, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
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
    cave[n++] = 0xFF; cave[n++] = 0x74; cave[n++] = 0x24; cave[n++] = 0x04;
    cave[n++] = 0xE8; *(DWORD *)(cave + n) = (DWORD)tr - (DWORD)(cave + n + 4); n += 4;
    cave[n++] = 0x50;
    cave[n++] = 0xFF; cave[n++] = 0x74; cave[n++] = 0x24; cave[n++] = 0x08;
    cave[n++] = 0xE8; *(DWORD *)(cave + n) = (DWORD)rz_hud_reflow - (DWORD)(cave + n + 4); n += 4;
    cave[n++] = 0x83; cave[n++] = 0xC4; cave[n++] = 0x04;
    cave[n++] = 0x58;
    cave[n++] = 0xC2; cave[n++] = 0x04; cave[n++] = 0x00;

    if (!VirtualProtect(t, (SIZE_T)len, PAGE_EXECUTE_READWRITE, &old)) {
        logf("--- HUD: VirtualProtect failed (%lu)", GetLastError()); return; }
    t[0] = 0xE9; *(DWORD *)(t + 1) = (DWORD)cave - (DWORD)(t + 5);
    { int j; for (j = 5; j < len; j++) t[j] = 0x90; }
    VirtualProtect(t, (SIZE_T)len, old, &old);
    FlushInstructionCache(GetCurrentProcess(), t, (SIZE_T)len);
    logf("--- HUD: FUN_100270e5 wrapped (cave 0x%08lX tr 0x%08lX) - top-strip reflow armed", (DWORD)cave, (DWORD)tr);
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
    patch_surfacefmt(gz);
    patch_gridb_clamp(ss);   /* FIX A: clamp the grid-B bucket index (OOB AV root cause) */


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
          /* Side panel: capture `this` at its constructor so the vertical tiling routine
             FUN_1004e63e (vtable +0x144) has an object to work on. Read-only for now. */
          install_one((DWORD)sui + 0x4e123, sui, 0x4e123, "SIMUI FUN_1004e123 side ctor", 3);
          /* minimap candidates - same +0x144 draw slot, no tile loop */
          install_one((DWORD)sui + 0x1a983, sui, 0x1a983, "SIMUI FUN_1001a983 ctor A", 4);
          install_one((DWORD)sui + 0x60ba9, sui, 0x60ba9, "SIMUI FUN_10060ba9 ctor B", 5);
          /* the generic window painter - where the minimap is identified by its dest rect */
          install_one((DWORD)sui + 0x6d2d0, sui, 0x6d2d0, "SIMUI FUN_1006d2d0 painter", 6);
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
          g_cluster = GetEnvironmentVariableA("SC3RESIZE_CLUSTER", v, sizeof(v)) && atoi(v);
          g_input   = GetEnvironmentVariableA("SC3RESIZE_INPUT",   v, sizeof(v)) && atoi(v);
          g_nohit   = GetEnvironmentVariableA("SC3RESIZE_NOHIT",   v, sizeof(v)) && atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_HUDDY", v, sizeof(v))) g_hud_dy = (LONG)atoi(v);
          if (GetEnvironmentVariableA("SC3RESIZE_SIDEDY", v, sizeof(v))) g_side_dy = (LONG)atoi(v);
          g_noparentfix = GetEnvironmentVariableA("SC3RESIZE_NOPARENTFIX", v, sizeof(v)) && atoi(v);
          /* HUD dock+span ships ON. SC3RESIZE_HUDNATIVE=1 is the opt-out for anyone who prefers the
             native bar - the full-width bar carries a measured GPU-sync FPS cost that is NOT yet
             resolved (verify/resize_hudlab: two causes eliminated, mechanism still open). */
          if (GetEnvironmentVariableA("SC3RESIZE_HUDNATIVE", v, sizeof(v)) && atoi(v)) g_hudfit = 0; }
        logf("### sc3resize loaded - resizable-window mod (minimal Init-free routine, "
             "validated 2026-08-27 over 6 runs)%s%s", g_minzoom ? " [MINZOOM crash-hunt build]" : "",
             g_hudlab ? " [HUD LAB armed: surface census + EIP profiler, verify/resize_hudlab]" : "");
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
             "anchor=%d census=%d minzoom=%d readyms=%lu noparentfix=%d huddy=%ld sidedy=%ld",
             g_cluster, g_input, g_nohit, g_hudfit, g_hudlab, g_sweepon, g_sideon, g_minion,
             g_anchor, g_census, g_minzoom, g_ready_ms, g_noparentfix, g_hud_dy, g_side_dy);
        if (AddVectoredExceptionHandler(1, rz_veh))
            logf("### VEH crash logger installed (logs any hardware fault MODULE+RVA - for the "
                 "zoom-after-resize crash the game swallows)");
        else
            logf("### VEH crash logger FAILED to install");
        CreateThread(NULL, 0, rz_watcher, NULL, 0, NULL);
    }
    return TRUE;
}






































