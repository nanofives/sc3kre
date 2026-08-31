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
                 "(%.1f%% of the 10 s window)", tag, g_ddblt_calls, dd,
                 g_ddblt_calls ? dd / g_ddblt_calls : 0.0, dd / 100.0);
        else
            logf("BLT> ---- %s ---- INSIDE ddraw Blt: NOT HOOKED (no split available)", tag);
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
            char dims[160];
            dims[0] = 0;
            /* IDENTITY (run 9 left this UNCERTAIN): always report the object's vtable resolved to
               MODULE+RVA, and its dims when the class is one we know. Run 9's dominant object
               printed nothing because it is neither known raster class, which left it unidentified.*/
            if (o && !IsBadReadPtr((void *)o, 0x2c)) {
                DWORD *vt = *(DWORD **)o;
                if (!IsBadReadPtr(vt, 4)) {
                    char who[120];
                    rz_modstr((DWORD)vt, who, sizeof(who));
                    if (gz && ((DWORD)vt == gz + GZ_RVA_VT_RASTER ||
                               (DWORD)vt == gz + GZ_RVA_VT_BLITDEST))
                        _snprintf(dims, sizeof(dims), " vt=%s raster %lux%lu", who,
                                  ((DWORD *)o)[0x24 / 4], ((DWORD *)o)[0x28 / 4]);
                    else
                        _snprintf(dims, sizeof(dims), " vt=%s", who);
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

static HRESULT WINAPI rz_blt_hook(void *self, RECT *dr, void *src, RECT *sr, DWORD fl, void *fx) {
    LARGE_INTEGER a, b;
    HRESULT hr;
    QueryPerformanceCounter(&a);
    hr = g_orig_blt(self, dr, src, sr, fl, fx);
    QueryPerformanceCounter(&b);
    g_ddblt_time += b.QuadPart - a.QuadPart;
    g_ddblt_calls++;
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
static void rz_hud_setrect(void);           /* fwd: the window widen, defined below */
static void rz_hud_fit_surface(DWORD liveW);/* fwd: the bar background surface widen, defined below */

static void rz_hudlab_tick(void) {
    if (!g_hudphase || GetTickCount() < g_phase_ms) return;
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
        logf("HUDLAB> applying the SetRect widen, then phase B");
        rz_hud_setrect();
        /* With SC3RESIZE_HUDFIT=1, also widen the bar's BACKGROUND SURFACE - the 600x56 raster run 2
           identified as the thing that actually stops the bar spanning the screen. Ordered after the
           window SetRect so the surface is fitted to the window the bar now occupies. */
        {   RECT cr;
            if (g_hudfit && g_hwnd && GetClientRect(g_hwnd, &cr))
                rz_hud_fit_surface((DWORD)(cr.right - cr.left)); }
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
static void rz_modstr(DWORD addr, char *out, int n) {
    static const char *mods[] = { "SIMSPR.DLL", "GZGraphicD.dll", "SIMCITY.DLL", "SIMUI.DLL",
                                  "GZWIN.DLL", "SC3U.exe", 0 };
    int i;
    for (i = 0; mods[i]; i++) {
        DWORD h = (DWORD)GetModuleHandleA(mods[i]), e, size;
        if (!h || IsBadReadPtr((void *)h, 0x40)) continue;
        e = *(DWORD *)(h + 0x3c);                       /* e_lfanew */
        if (IsBadReadPtr((void *)(h + e + 0x50), 4)) continue;
        size = *(DWORD *)(h + e + 0x50);                /* OptionalHeader.SizeOfImage (PE32) */
        if (addr >= h && addr < h + size) {
            _snprintf(out, n, "%s+0x%lX (base 0x%08lX)", mods[i], addr - h, h);
            return;
        }
    }
    _snprintf(out, n, "0x%08lX (no known module)", addr);
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
        if (g_hudlab) {
            /* DIAGNOSTIC path: census now, then let the A/B phase machine drive the dock+fit so the
               profiler gets a native-width control phase first. */
            rz_hud_surfaces("BEFORE-setrect");
            g_hudphase = 1;
            g_phase_ms = GetTickCount() + 3000;
            logf("HUDLAB> armed - phase A (native bar) begins in 3 s, then widen, then phase B");
        } else if (g_hudfit) {
            /* SHIP path: dock the bar to the resized window and refit its background surface, here
               and now on the render thread. Same two calls the lab drives, no phases, no census.
               Both are self-gating and log a refusal rather than forcing anything. */
            RECT cr;
            rz_hud_setrect();
            if (g_hwnd && GetClientRect(g_hwnd, &cr))
                rz_hud_fit_surface((DWORD)(cr.right - cr.left));
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
static void rz_hud_setrect(void) {
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
        int wantY1 = lh - barH, wantX2 = lw, wantY2 = lh;
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
static void rz_hud_fit_surface(DWORD liveW) {
    DWORD *h = (DWORD *)g_hud_top;
    HMODULE gz = GetModuleHandleA("GZGraphicD.dll");
    DWORD obj, sub, oldbits, oldpitch, oldw, oldh;
    BYTE *snap = NULL;

    if (!g_hudfit) return;
    if (!h || IsBadReadPtr(h, 0xc0) || !gz) { logf("HUDFIT> skipped: no HUD window or GZGraphicD"); return; }
    obj = h[0x2a];
    if (!obj || IsBadReadPtr((void *)obj, 0x48)) { logf("HUDFIT> skipped: child[0x2a] unreadable"); return; }

    oldw = ((DWORD *)obj)[0x24 / 4]; oldh = ((DWORD *)obj)[0x28 / 4];
    sub  = ((DWORD *)obj)[0x44 / 4];
    if (!sub || IsBadReadPtr((void *)sub, 0xf8)) { logf("HUDFIT> skipped: sub unreadable"); return; }
    oldbits = ((DWORD *)sub)[0xf0 / 4]; oldpitch = ((DWORD *)sub)[0xf4 / 4];
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
    if (!g_hud_art && oldbits && oldpitch && oldh &&
        !IsBadReadPtr((void *)oldbits, oldpitch * oldh)) {
        g_hud_art = (BYTE *)HeapAlloc(GetProcessHeap(), 0, oldpitch * oldh);
        if (g_hud_art) {
            memcpy(g_hud_art, (void *)oldbits, oldpitch * oldh);
            g_hud_artw = oldw; g_hud_arth = oldh; g_hud_artpitch = oldpitch;
            logf("HUDFIT> cached the pristine native art %lux%lu pitch=%lu (one-time)",
                 oldw, oldh, oldpitch);
        }
    }
    if (!g_hud_art) {
        logf("HUDFIT> WARNING: no cached art (bits=0x%08lX pitch=%lu) - the bar may come back blank",
             oldbits, oldpitch);
    }
    snap    = g_hud_art;
    oldw    = g_hud_artw    ? g_hud_artw    : oldw;
    oldpitch= g_hud_artpitch ? g_hud_artpitch : oldpitch;
    oldh    = g_hud_arth    ? g_hud_arth    : oldh;   /* NATIVE height - never the padded one */

    logf("HUDFIT> bar background child[0x2a]=0x%08lX -> refitting to %lux%lu (art %lux%lu)",
         obj, liveW, oldh, oldw, oldh);

    if (!rz_recreate_raster(obj, "HUD bar background", liveW, oldh, gz)) {
        logf("HUDFIT> recreate REFUSED - bar left as it was");
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
            int lk = rz_thiscall((void *)nsub, (void *)svt[0x0c / 4], NULL, 0);
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
        /* g_hud_art is the process-lifetime cache - deliberately NOT freed here. */
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
      if (sui) patch_hud_reflow(sui);
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
          /* HUD dock+span ships ON. SC3RESIZE_HUDNATIVE=1 is the opt-out for anyone who prefers the
             native bar - the full-width bar carries a measured GPU-sync FPS cost that is NOT yet
             resolved (verify/resize_hudlab: two causes eliminated, mechanism still open). */
          if (GetEnvironmentVariableA("SC3RESIZE_HUDNATIVE", v, sizeof(v)) && atoi(v)) g_hudfit = 0; }
        logf("### sc3resize loaded - resizable-window mod (minimal Init-free routine, "
             "validated 2026-08-27 over 6 runs)%s%s", g_minzoom ? " [MINZOOM crash-hunt build]" : "",
             g_hudlab ? " [HUD LAB armed: surface census + EIP profiler, verify/resize_hudlab]" : "");
        if (AddVectoredExceptionHandler(1, rz_veh))
            logf("### VEH crash logger installed (logs any hardware fault MODULE+RVA - for the "
                 "zoom-after-resize crash the game swallows)");
        else
            logf("### VEH crash logger FAILED to install");
        CreateThread(NULL, 0, rz_watcher, NULL, 0, NULL);
    }
    return TRUE;
}


