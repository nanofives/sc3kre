/* sc3simrun.c - keep the SimCity 3000 Unlimited simulation running while the camera moves.
 *
 * Stock behaviour (measured 2026-10-06, verify/simrun/): the view's scroll step SIMSPR FUN_10043daf
 * sets a "held for camera" flag (view outer +0x174 = inner +0x170) and calls the city-simulator
 * coordinator's vt+0x21c (FUN_100058ac: +0x144 += 1, clock Pause, clock +0x54 += 1). The view tick
 * FUN_10042a95 calls vt+0x220 (release) only once every camera-busy flag (+0x1dd..+0x1e2) is clear.
 * So right-drag, a held right button and arrow/edge scrolling all freeze the sim clock until the
 * camera stops. Every camera hold in a scripted drag/held/arrows run came from that one call site.
 *
 * The fix is one byte: SIMSPR 0x1004401a `jne +0x12` -> `jmp +0x12`, so the scroll step never sets the
 * flag and never holds. The tick then never sees the flag and never releases, so the coordinator's
 * counts stay balanced. Zoom/rotate (FUN_10042d8a, FUN_10042f27, ...) keep their own momentary
 * hold/release brackets, untouched.
 *
 * FREEZE (owner 2026-10-15, task cartrips P1 + extension): the street animation keeps running while the game is
 * paused, because its tick is real time (STRTSIM.md 8): cars keep driving and being deleted by the density
 * despawn (CAR_TRIPS.md 1.4: ~35 visible deletions a minute paused in Berlin), trains, subway cars, people, boats
 * and aircraft keep moving. The SC3U.exe agent loop FUN_00425a10 ticks every animated agent through one
 * instruction, `call [edx+0x100]` at 0x00425a99 (ecx = agent, edx = its vtable, one stack arg the callee pops).
 * That instruction is replaced by a call to freeze_thunk: while the user pause depth city +0x140 is non-zero and
 * the agent is in the frozen set, it returns at once (ret 4); otherwise it jumps to the agent's own Tick. Nothing
 * of a frozen agent runs (no move, no animation frame, no despawn test, no wait timer); on resume it continues
 * where it stopped. Frozen set, ini [sim] freeze_on_pause:
 *   street (default) = every agent whose class (vtable) lives in STRTSIM.DLL: cars, trains, subway, people,
 *                      boats, aircraft, other street vehicles. SIMSPR's animated sprites keep running.
 *   cars             = only the street sim's cars (vtable STRTSIM 0x1002cd20, the class FUN_10019750 builds).
 *   0                = stock.
 * The camera hold already freezes all of them (SIMSPR view tick). City = *(SC3U.exe+0xfa86c) +0x48, as sc3perf /
 * sc3resize read it. Measured: verify/cartrips/RESULTS.md addenda 3 and 4.
 *
 * ANIMATE (owner 2026-10-16, task carscroll): with the hold gone the street agents still froze while the camera moved.
 * The heartbeat that ticks them (SC3U FUN_00426140, STRTSIM.md 8) is called from the render view's frame FUN_1001cab9
 * (SIMSPR vtable 0x10063390 slot +0x20) only while its byte +0x2b is set, and +0x2b = (rate >= 0.1) is written by
 * slot +0x7c FUN_1001d65d(&rate) `[CONFIRMED @ SIMSPR 0x1001cab9, 0x1001d65d, 0x10063504 = 0.1f]`. The idle view tick
 * FUN_10042a95 passes 60.0 before every frame; the scroll step FUN_10043daf passes 0.0 (`fldz; fstp [ebp-8]` at
 * 0x10043de7, 0x10043f60 and 0x10044003, one per branch) before its own frame, so every scroll frame renders without
 * the heartbeat. Zoom and rotate
 * (FUN_10042d8a, ...) pass 0.0 and 60.0 inside one call, with no frame between: nothing to change there.
 * The 5 bytes at each of the three sites become a call to anim_stub, which writes g_scroll_rate (60.0, the idle tick's value)
 * into [ebp-8]. Needs run_while_scrolling=1: the stock camera hold suspends the heartbeat itself (+0xb0).
 * FREEZE still wins: it skips frozen agents inside the heartbeat's agent loop whatever drives the heartbeat.
 * STRIPS (same switch): once the agents tick during a move, the camera's car churn shows. UpdateVehicleView STRTSIM
 * FUN_10015415 queues the cars on the strips that left the sim rect for removal (AnimOccMan vt+0x58, carried out in
 * their next tick, so today, with frozen agents, nothing is removed until the camera stops) and then refills by calling
 * PutVehiclesInRect FUN_1001f040 on the WHOLE new rect once per new strip (loop at 0x1001556c..0x1001557c: edi = index,
 * strips at [ebp-0x44], count at [ebp-4]); the refill scans the rect row by row from its first corner and places cars
 * until alive > target `[CONFIRMED @ STRTSIM 0x10015415, 0x10014d85, 0x1001f040]`. Measured (carscroll K0d): arrow
 * scrolling then placed ~50 cars/s, 26% of them popping in on screen. While animating, the refill from that loop
 * (return address 0x10015578) gets strip number edi instead of the whole rect, so new cars appear only on the ground
 * the camera has just revealed. Hooked at FUN_1001f040's entry: sc3cartrips patches (and checks) the call site and, in
 * filler / off, jumps to the function with the return address intact.
 * TICKSTRIP (same switch): the strip cars leave in their own tick, so the stock producer tick FUN_1001f44a sees
 * alive < target during a move and places cars with PutAVehicleInRect FUN_1001ef25 at random cells of the producer's
 * rect +0x24..+0x30 `[CONFIRMED @ STRTSIM 0x1001f44a, 0x1001ef25]`. Measured (carscroll S1, drag): on-screen pop-ins
 * 219 a minute against 98 with the camera still, all from that tick. While the camera is moving (a scroll frame in the
 * last 300 ms) the tick runs with the producer's rect set to the strip most recently revealed (if it still lies in the
 * rect), and the rect is put back as soon as it returns; with no such strip the tick is skipped (carscroll S1c: every
 * remaining on-screen pop-in during a drag came from ticks run on the full rect between strips). Once the camera has
 * been still for 300 ms the tick runs as stock.
 * CARMARGIN (same switch, ini [sim] car_margin, default 5; 2 = stock): ProcessViewChange STRTSIM FUN_10013e66 grows the
 * view's cell box by 2 cells into the street agents' sim rect (`push 2` at 0x10013fc9, FUN_100120b7(box, +0x90, 2))
 * `[CONFIRMED @ STRTSIM 0x10013fc9, 0x100120b7]`. Every camera step deletes the agents on the strips that leave that rect,
 * so a back-and-forth drag keeps deleting the cars just off screen and the ground they leave is empty when the camera
 * comes back (carscroll R0). A wider margin keeps them while the camera moves less than the margin, and fills new ground
 * before the camera reaches it. The byte is written once at arming; sc3simrun_carmargin(n) changes it at run time. Hooked at FUN_1001f44a's entry (reached in stock and filler modes; replace mode never calls it).
 *
 * Config: simrun.ini beside the DLL:  [sim] run_while_scrolling=1   (0 = stock, the A/B control)
 *                                     [sim] freeze_on_pause=street  (cars = cars only, 0 = stock)
 *                                     [sim] animate_while_scrolling=1 (0 = agents freeze during camera moves, stock)
 *                                     [churn] anarchy_res|com|ind=0, upgrade_X and density_X=-1 (game value),
 *                                     enabled=1 (0 = stock rolls; env SC3SIMRUN_CHURN=0 too)
 *                                     [sirens] enabled=1 per_vehicle=1 chance_pct=20 cooldown_s=30 (SIRENS block;
 *                                     env SC3SIMRUN_SIRENS=0 = stock, SC3SIMRUN_SIREN_PERVEH / _PCT / _COOL per part)
 *                                     [lvwrap] mode=1 (LVWRAP block: cap the city land value average at 255;
 *                                     0 = stock, 2 = observe; env SC3SIMRUN_LVWRAP=0/1/2)
 *                                     [sandbox] enabled=0 (SANDBOX block: 1 = no zone-evaluator abandonment;
 *                                     env SC3SIMRUN_SANDBOX=1/0)
 *                                     [gentle] enabled=0 share_pct=25 (GENTLE block: negative-demand abandonment only
 *                                     under that share of the valve range; env SC3SIMRUN_GENTLE=1/0, _GENTLE_SHARE)
 *                                     [hwyspeed] enabled=1 factor_pct=150 threshold=66000 (HWYSPEED block: animated
 *                                     cars on highway and ramp lanes x factor; env SC3SIMRUN_HWYSPEED=1/0, _HWYSPEED_PCT)
 * Exports (measurement): sc3simrun_animate(on) switches the scroll-frame rate at run time (returns the old state),
 *         sc3simrun_sirens(DWORD out[4]) = siren states recorded, cooldown blocks, siren-actor updates, removals.
 *         sc3simrun_lvwrap(DWORD out[4]) = average stores, stores over 255, last true average, last cell count.
 *         sc3simrun_abandon(DWORD out[42]) = abandonment counts (layout at the function).
 *         sc3simrun_stats(DWORD out[6]) = scroll frames seen by the stub, agent ticks, frozen agent ticks, strip refills, producer ticks run on the revealed strip, producer ticks skipped.
 * Env:    SC3SIMRUN_LOG=<abs path>  SC3SIMRUN_TRACE=1 (20 Hz sampler + hold/pause caller log)
 *         SC3SIMRUN_RESUME=1 (test only: post 0xc2a35d80 once per unit of +0x140 after load)
 * Build:  re/harness/build_simrun.ps1. Ships via mods_launch.exe.
 */

#include <windows.h>
#include "sc3mods_guard.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

/* ============================================================ logging */

static CRITICAL_SECTION g_lock;
static HANDLE g_log = INVALID_HANDLE_VALUE;
static LARGE_INTEGER g_freq, g_t0;
static HMODULE g_self;

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
}

static void self_path(char *out, int cap, const char *leaf) {
    char *slash;
    if (!GetModuleFileNameA(g_self, out, cap)) { out[0] = 0; return; }
    slash = strrchr(out, '\\');
    if (slash) slash[1] = 0; else out[0] = 0;
    lstrcatA(out, leaf);
}

static void log_open(void) {
    char path[MAX_PATH];
    if (!GetEnvironmentVariableA("SC3SIMRUN_LOG", path, sizeof(path)))
        self_path(path, sizeof(path), "sc3simrun.log");
    g_log = CreateFileA(path, GENERIC_WRITE, FILE_SHARE_READ, NULL,
                        CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
}

static unsigned __int64 epoch_ms(void) {
    FILETIME ft;
    unsigned __int64 t;
    GetSystemTimeAsFileTime(&ft);
    t = ((unsigned __int64)ft.dwHighDateTime << 32) | ft.dwLowDateTime;
    return t / 10000 - 11644473600000ULL;
}

/* ============================================================ coordinator capture */

/* SIMCITY vtable 0x10013260 slot 3 (+0x0c) = FUN_10002fa6, the coordinator's message dispatcher,
   __thiscall. Swap that one pointer to capture ecx. Same technique as sc3probe.c coord_arm. */
static volatile DWORD g_coord;
static volatile LONG  g_coord_msgs;
static void *g_coord_orig;
static DWORD g_simcity;

static __declspec(naked) void coord_thunk(void) {
    __asm mov g_coord, ecx
    __asm lock inc dword ptr [g_coord_msgs]
    __asm jmp dword ptr [g_coord_orig]
}

static int coord_arm(HMODULE simcity) {
    DWORD *slot = (DWORD *)((BYTE *)simcity + 0x1326c);
    DWORD want = (DWORD)((BYTE *)simcity + 0x2fa6), old;
    if (IsBadReadPtr(slot, 4) || *slot != want) {
        logf("### COORD: slot +0x1326c holds 0x%08lX, expected 0x%08lX - not armed", *slot, want);
        return 0;
    }
    if (!VirtualProtect(slot, 4, PAGE_EXECUTE_READWRITE, &old)) return 0;
    g_coord_orig = (void *)*slot;
    *slot = (DWORD)coord_thunk;
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    return 1;
}


/* ============================================================ clock Pause/Resume callers */

/* Clock vtable SIMCITY 0x10013988: +0x2c = FUN_1000a0ec Pause (inc +0x54), +0x30 = FUN_1000a145
   Resume (dec +0x54). Both __fastcall(this), no stack args. Swap the two slots and log callers. */
#pragma intrinsic(_ReturnAddress)
void *_ReturnAddress(void);
typedef char (__fastcall *PFN_Clk)(void *);
static PFN_Clk g_clk_pause, g_clk_resume;

static void who(const char *what, void *self, void *ret) {
    HMODULE m = NULL;
    char name[MAX_PATH] = "?", *b;
    GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                       (LPCSTR)ret, &m);
    if (m) GetModuleFileNameA(m, name, sizeof(name));
    b = strrchr(name, '\\');
    logf("C %s t=%I64u clk=%08lX depth(before)=%lu ret=%s+0x%lX (0x%08lX)", what, epoch_ms(), (DWORD)self,
         *(DWORD *)((BYTE *)self + 0x54), b ? b + 1 : name, (DWORD)ret - (DWORD)m, 0x10000000 + (DWORD)ret - (DWORD)m);
}
static char __fastcall clk_pause(void *self) { who("PAUSE ", self, _ReturnAddress()); return g_clk_pause(self); }
static char __fastcall clk_resume(void *self) { who("RESUME", self, _ReturnAddress()); return g_clk_resume(self); }

static int clock_arm(HMODULE simcity) {
    DWORD *slot = (DWORD *)((BYTE *)simcity + 0x139b4), old;
    if (slot[0] != (DWORD)simcity + 0xa0ec || slot[1] != (DWORD)simcity + 0xa145) return 0;
    if (!VirtualProtect(slot, 8, PAGE_EXECUTE_READWRITE, &old)) return 0;
    g_clk_pause = (PFN_Clk)slot[0]; g_clk_resume = (PFN_Clk)slot[1];
    slot[0] = (DWORD)clk_pause; slot[1] = (DWORD)clk_resume;
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    return 1;
}

/* Coordinator vtable SIMCITY 0x10013260: +0x21c = FUN_100058ac (inc +0x144, clock Pause),
   +0x220 = FUN_1000590e (dec +0x144, clock Resume). __fastcall(this). Log their callers too. */
typedef DWORD (__fastcall *PFN_Co)(void *);
static PFN_Co g_co_hold, g_co_release;
static void who2(const char *what, void *self, void *ret) {
    HMODULE m = NULL;
    char name[MAX_PATH] = "?", *b;
    GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                       (LPCSTR)ret, &m);
    if (m) GetModuleFileNameA(m, name, sizeof(name));
    b = strrchr(name, '\\');
    logf("K %s t=%I64u +0x144(before)=%lu ret=%s 0x%08lX", what, epoch_ms(),
         *(DWORD *)((BYTE *)self + 0x144), b ? b + 1 : name, 0x10000000 + (DWORD)ret - (DWORD)m);
}
static DWORD __fastcall co_hold(void *self) { who2("HOLD   ", self, _ReturnAddress()); return g_co_hold(self); }
static DWORD __fastcall co_release(void *self) { who2("RELEASE", self, _ReturnAddress()); return g_co_release(self); }
static int cohold_arm(HMODULE simcity) {
    DWORD *slot = (DWORD *)((BYTE *)simcity + 0x1347c), old;
    if (slot[0] != (DWORD)simcity + 0x58ac || slot[1] != (DWORD)simcity + 0x590e) return 0;
    if (!VirtualProtect(slot, 8, PAGE_EXECUTE_READWRITE, &old)) return 0;
    g_co_hold = (PFN_Co)slot[0]; g_co_release = (PFN_Co)slot[1];
    slot[0] = (DWORD)co_hold; slot[1] = (DWORD)co_release;
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    return 1;
}

/* ============================================================ GZ message post (from sc3probe.c gz_msg) */

typedef int (__fastcall *PFN_GetSvc)(void *, void *, DWORD, DWORD, void *);
typedef int (__fastcall *PFN_MsgPost)(void *, void *, void *, char);

static int gz_post(DWORD msgid, DWORD a0) {
    BYTE *exe = (BYTE *)GetModuleHandleA(NULL);
    HMODULE gzsvc = GetModuleHandleA("GZServiceD.dll");
    void *fw, *srv = NULL;
    DWORD msg[4];
    if (!exe || !gzsvc || IsBadReadPtr(exe + 0xFAB74, 4)) return 0;
    fw = *(void **)(exe + 0xFAB74);
    if (!fw || IsBadReadPtr(fw, 4)) return 0;
    __try {
        ((PFN_GetSvc)(*(DWORD **)fw)[0x10 / 4])(fw, NULL, 0x64063387, 0xC1085722, &srv);
        if (!srv || *(DWORD *)srv != (DWORD)gzsvc + 0x14618) return 0;
        msg[0] = msgid; msg[1] = a0; msg[2] = msg[3] = 0;
        ((PFN_MsgPost)(*(DWORD **)srv)[0x10 / 4])(srv, NULL, msg, 0);
    } __except (EXCEPTION_EXECUTE_HANDLER) { return 0; }
    return 1;
}

/* ============================================================ the patch */

static int g_run = 1;
static int g_freeze = 2;                         /* 0 stock, 1 cars, 2 street */
static int g_anim = 1;                           /* animate street agents while the camera moves */
static int g_car_margin = 5;                     /* sim rect = view box + this many cells (stock 2) */

static void churn_ini(const char *path);
static void sirens_ini(const char *path);
static void lvwrap_ini(const char *path);
static void abandon_ini(const char *path);
static void hwyspeed_ini(const char *path);

static void ini_read(void) {
    char path[MAX_PATH];
    self_path(path, sizeof(path), "simrun.ini");
    if (path[0]) g_run = GetPrivateProfileIntA("sim", "run_while_scrolling", 1, path) ? 1 : 0;
    if (path[0]) g_anim = GetPrivateProfileIntA("sim", "animate_while_scrolling", 1, path) ? 1 : 0;
    if (path[0]) g_car_margin = GetPrivateProfileIntA("sim", "car_margin", 5, path);
    if (g_car_margin < 2) g_car_margin = 2;
    if (g_car_margin > 24) g_car_margin = 24;
    if (path[0]) {
        char v[16];
        GetPrivateProfileStringA("sim", "freeze_on_pause", "street", v, sizeof(v), path);
        g_freeze = !lstrcmpiA(v, "cars") ? 1 : (!lstrcmpiA(v, "0") || !lstrcmpiA(v, "off")) ? 0 : 2;
    }
    churn_ini(path);
    sirens_ini(path);
    lvwrap_ini(path);
    abandon_ini(path);
    hwyspeed_ini(path);
}

/* ============================================================ FREEZE */

static BYTE *g_exe;
static DWORD g_city_vt;                          /* SIMCITY+0x13260, the city / coordinator vtable */
static DWORD g_vt_lo, g_vt_hi;                   /* frozen vtable range: STRTSIM image, or the car vtable alone */
static volatile LONG g_frozen_ticks, g_agent_ticks;
static int g_freeze_armed;

static __inline int user_paused(void) {
    BYTE *app = *(BYTE **)(g_exe + 0xfa86c), *city;
    if (!app) return 0;
    city = *(BYTE **)(app + 0x48);
    if (!city || *(DWORD *)city != g_city_vt) return 0;
    return *(LONG *)(city + 0x140) > 0;
}

/* game thread only (the agent loop); the counters are statistics */
static int __cdecl freeze_skip(DWORD vt) {
    g_agent_ticks++;
    if (vt >= g_vt_lo && vt < g_vt_hi && user_paused()) { g_frozen_ticks++; return 1; }
    return 0;
}

/* replaces `call dword ptr [edx+0x100]` at SC3U.exe 0x00425a99: ecx = agent, edx = vtable, [esp+4] = time delta */
static __declspec(naked) void freeze_thunk(void) {
    __asm {
        push ecx
        push edx
        push edx
        call freeze_skip
        add esp, 4
        pop edx
        pop ecx
        test eax, eax
        jnz skip
        jmp dword ptr [edx + 0x100]
    skip:
        ret 4
    }
}

static int freeze_arm(HMODULE strt, HMODULE simcity) {
    static const BYTE expect[] = { 0x8b, 0x11, 0xff, 0x92, 0x00, 0x01, 0x00, 0x00, 0x8b, 0xc6 };
    BYTE *p, *exe = (BYTE *)GetModuleHandleA(NULL);
    IMAGE_NT_HEADERS *nt;
    DWORD old;
    p = exe + 0x25a97;                           /* mov edx,[ecx] / call [edx+0x100] / mov eax,esi */
    if (IsBadReadPtr(p, sizeof(expect)) || memcmp(p, expect, sizeof(expect))) {
        logf("### FREEZE: SC3U.exe+0x25a97 differs from shipped - NOT armed");
        return 0;
    }
    g_exe = exe;
    g_city_vt = (DWORD)simcity + 0x13260;
    if (g_freeze == 1) {
        g_vt_lo = (DWORD)strt + 0x2cd20; g_vt_hi = g_vt_lo + 1;
    } else {
        nt = (IMAGE_NT_HEADERS *)((BYTE *)strt + ((IMAGE_DOS_HEADER *)strt)->e_lfanew);
        g_vt_lo = (DWORD)strt; g_vt_hi = (DWORD)strt + nt->OptionalHeader.SizeOfImage;
    }
    p += 2;
    if (!VirtualProtect(p, 6, PAGE_EXECUTE_READWRITE, &old)) return 0;
    p[0] = 0xE8;                                 /* call rel32 freeze_thunk */
    *(DWORD *)(p + 1) = (DWORD)freeze_thunk - (DWORD)(p + 5);
    p[5] = 0x90;
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    FlushInstructionCache(GetCurrentProcess(), p, 6);
    g_freeze_armed = 1;
    return 1;
}

/* SIMSPR+0x4400e: cmp [esi+0x174],bl / lea eax,[esi+0x174] / jne +0x12 / mov byte [eax],1 */
static int patch_scroll_hold(HMODULE spr) {
    static const BYTE expect[] = { 0x38, 0x9e, 0x74, 0x01, 0x00, 0x00, 0x8d, 0x86, 0x74, 0x01, 0x00, 0x00,
                                   0x75, 0x12, 0xc6, 0x00, 0x01 };
    BYTE *p = (BYTE *)spr + 0x4400e;
    DWORD old;
    if (IsBadReadPtr(p, sizeof(expect)) || memcmp(p, expect, sizeof(expect))) {
        logf("### PATCH: SIMSPR+0x4400e differs from shipped - NOT patched (sim pauses while scrolling)");
        return 0;
    }
    if (!VirtualProtect(p + 12, 1, PAGE_EXECUTE_READWRITE, &old)) return 0;
    p[12] = 0xEB;
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    FlushInstructionCache(GetCurrentProcess(), p + 12, 1);
    return 1;
}

/* ============================================================ ANIMATE */

#define RATE_ON  0x42700000                      /* 60.0f, what the idle view tick passes */
static volatile DWORD g_scroll_rate = RATE_ON;   /* float bits the scroll step passes to the render view's +0x7c */
static volatile LONG g_scroll_frames;
static int g_anim_armed;

/* replaces `fldz; fstp dword ptr [ebp-8]` at SIMSPR 0x10043de7 / 0x10043f60 / 0x10044003 (ebp = the scroll step's frame); keeps every register.
   The next instructions (mov eax,[ecx] / push edx / call [eax+0x7c]) read no flags. */
static __declspec(naked) void anim_stub(void) {
    __asm {
        push eax
        mov eax, g_scroll_rate
        mov dword ptr [ebp - 8], eax
        pop eax
        lock inc dword ptr [g_scroll_frames]
        ret
    }
}

/* The compiler kept three copies of the rate write, one per branch, each the same 16 bytes
   (mov ecx,[esi+0xb8] / lea edx,[ebp-8] / fldz / fstp [ebp-8] / mov eax,[ecx]) before `call [eax+0x7c]` at 0x1004400b:
   drag / held button 0x10043dde (jmp 0x1004400a), one direction 0x10043f57 (jmp 0x1004400a), two directions
   0x10043ffa (falls through). Ghidra's text shows one. All three are patched, or none. */
static int patch_scroll_anim(HMODULE spr) {
    static const BYTE expect[] = { 0x8b, 0x8e, 0xb8, 0x00, 0x00, 0x00, 0x8d, 0x55, 0xf8, 0xd9, 0xee, 0xd9, 0x5d, 0xf8,
                                   0x8b, 0x01 };
    static const DWORD sites[3] = { 0x43dde, 0x43f57, 0x43ffa };
    BYTE *q;
    DWORD old;
    int i;
    for (i = 0; i < 3; i++) {
        BYTE *p = (BYTE *)spr + sites[i];
        if (IsBadReadPtr(p, sizeof(expect)) || memcmp(p, expect, sizeof(expect))) {
            logf("### ANIMATE: SIMSPR+0x%lx differs from shipped - NOT patched (agents freeze while scrolling)", sites[i]);
            return 0;
        }
    }
    for (i = 0; i < 3; i++) {
        q = (BYTE *)spr + sites[i] + 9;          /* the fldz */
        if (!VirtualProtect(q, 5, PAGE_EXECUTE_READWRITE, &old)) return 0;
        q[0] = 0xE8;
        *(DWORD *)(q + 1) = (DWORD)anim_stub - (DWORD)(q + 5);
        (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
        FlushInstructionCache(GetCurrentProcess(), q, 5);
    }
    g_anim_armed = 1;
    return 1;
}

/* STRIPS: jmp at STRTSIM FUN_1001f040's entry (push ebp / mov ebp,esp / sub esp,0x18 = 6 bytes). At entry ebp and edi
   are still the caller's. */
static DWORD g_strip_ret, g_strip_cont;          /* STRTSIM+0x15578 (return into the refill loop), +0x1f046 */
static volatile LONG g_strip_calls;
static int g_strip_armed;
static LONG g_last_strip[4];                     /* x0 z0 x1 z1 of the strip revealed last (game thread) */
static DWORD g_last_strip_ms, g_last_scroll_ms, g_scroll_seen;
static volatile LONG g_tick_swaps;

static void __cdecl strip_note(LONG *r) {
    memcpy(g_last_strip, r, sizeof(g_last_strip));
    g_last_strip_ms = GetTickCount();
}

static __declspec(naked) void strip_entry(void) {
    __asm {
        mov eax, [esp]
        cmp eax, g_strip_ret
        jne stock
        cmp dword ptr [g_scroll_rate], 0
        je stock
        mov eax, edi
        shl eax, 4
        lea eax, [ebp + eax - 0x44]              ; &strips[edi]
        mov [esp + 4], eax
        lock inc dword ptr [g_strip_calls]
        pushad
        push eax
        call strip_note
        add esp, 4
        popad
    stock:
        push ebp
        mov ebp, esp
        sub esp, 0x18
        jmp dword ptr [g_strip_cont]
    }
}

static int patch_strips(HMODULE strt) {
    static const BYTE entry[] = { 0x55, 0x8b, 0xec, 0x83, 0xec, 0x18, 0x80, 0x79, 0x35, 0x00 };
    static const BYTE loop[] = { 0x8b, 0x8b, 0x00, 0x01, 0x00, 0x00, 0x56, 0xe8 };   /* 0x1001556c: mov ecx,[ebx+0x100] / push esi / call */
    static const BYTE tail[] = { 0x47, 0x3b, 0x7d, 0xfc, 0x7c, 0xee };               /* 0x10015578: inc edi / cmp edi,[ebp-4] / jl */
    static const BYTE strips[] = { 0x8d, 0x45, 0xbc, 0x50, 0x57, 0x56, 0xe8 };       /* 0x10015541: lea eax,[ebp-0x44] / push eax / push edi / push esi / call FUN_10014d85 */
    BYTE *S = (BYTE *)strt, *p = S + 0x1f040;
    DWORD old;
    if (memcmp(p, entry, sizeof(entry)) || memcmp(S + 0x1556c, loop, sizeof(loop)) || memcmp(S + 0x15578, tail, sizeof(tail))
        || memcmp(S + 0x15541, strips, sizeof(strips))) {
        logf("### STRIPS: STRTSIM differs from shipped - NOT armed (camera moves refill the whole sim rect)");
        return 0;
    }
    g_strip_ret = (DWORD)S + 0x15578;
    g_strip_cont = (DWORD)S + 0x1f046;
    if (!VirtualProtect(p, 6, PAGE_EXECUTE_READWRITE, &old)) return 0;
    p[0] = 0xE9;
    *(DWORD *)(p + 1) = (DWORD)strip_entry - (DWORD)(p + 5);
    p[5] = 0x90;
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    FlushInstructionCache(GetCurrentProcess(), p, 6);
    g_strip_armed = 1;
    return 1;
}

/* TICKSTRIP: jmp at STRTSIM FUN_1001f44a's entry (thiscall, 1 stack arg, ret 4; push ebp / mov ebp,esp / push ecx /
   push ecx / push esi = 6 bytes, moved to g_tick_tramp). */
static BYTE *g_tick_tramp;
static LONG g_tick_saved[4];

static volatile LONG g_tick_skips;

/* 0 = run stock, 1 = run on the strip (rect swapped), 2 = skip this tick */
static int __cdecl tick_swap(BYTE *prod) {
    DWORD now = GetTickCount();
    LONG *r = (LONG *)(prod + 0x24);
    if (g_scroll_frames != (LONG)g_scroll_seen) { g_scroll_seen = (DWORD)g_scroll_frames; g_last_scroll_ms = now; }
    if (now - g_last_scroll_ms > 300) return 0;
    if (!g_last_strip_ms || g_last_strip[2] < g_last_strip[0] || g_last_strip[3] < g_last_strip[1]
        || g_last_strip[0] < r[0] || g_last_strip[1] < r[1] || g_last_strip[2] > r[2] || g_last_strip[3] > r[3]) {
        g_tick_skips++;
        return 2;
    }
    memcpy(g_tick_saved, r, sizeof(g_tick_saved));
    memcpy(r, g_last_strip, sizeof(g_last_strip));
    g_tick_swaps++;
    return 1;
}
static void __cdecl tick_restore(BYTE *prod) { memcpy(prod + 0x24, g_tick_saved, sizeof(g_tick_saved)); }

static __declspec(naked) void tick_entry(void) {
    __asm {
        cmp dword ptr [g_scroll_rate], 0
        je stock
        push ecx
        push ecx
        call tick_swap
        add esp, 4
        pop ecx
        test eax, eax
        je stock
        cmp eax, 2
        je skip
        push ecx                                 ; producer
        push dword ptr [esp + 8]                 ; the caller's stack argument
        call dword ptr [g_tick_tramp]            ; FUN_1001f44a, pops its argument
        pop ecx
        push ecx
        call tick_restore
        add esp, 4
        ret 4
    skip:
        ret 4
    stock:
        jmp dword ptr [g_tick_tramp]
    }
}

static int patch_tickstrip(HMODULE strt) {
    static const BYTE entry[] = { 0x55, 0x8b, 0xec, 0x51, 0x51, 0x56, 0x8b, 0xf1, 0x80, 0x7e, 0x35, 0x00 };
    BYTE *p = (BYTE *)strt + 0x1f44a;
    DWORD old;
    if (memcmp(p, entry, sizeof(entry))) { logf("### TICKSTRIP: STRTSIM+0x1f44a differs from shipped - NOT armed"); return 0; }
    g_tick_tramp = (BYTE *)VirtualAlloc(NULL, 16, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!g_tick_tramp) return 0;
    memcpy(g_tick_tramp, p, 6);
    g_tick_tramp[6] = 0xE9;
    *(DWORD *)(g_tick_tramp + 7) = (DWORD)(p + 6) - (DWORD)(g_tick_tramp + 11);
    if (!VirtualProtect(p, 6, PAGE_EXECUTE_READWRITE, &old)) return 0;
    p[0] = 0xE9;
    *(DWORD *)(p + 1) = (DWORD)tick_entry - (DWORD)(p + 5);
    p[5] = 0x90;
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    FlushInstructionCache(GetCurrentProcess(), p, 6);
    return 1;
}

/* CARMARGIN: the imm8 of `push 2` at STRTSIM 0x10013fc9 */
static BYTE *g_margin_at;

static int set_car_margin(int m) {
    DWORD old;
    int was;
    if (!g_margin_at) return -1;
    if (m < 2) m = 2;
    if (m > 24) m = 24;
    was = g_margin_at[0];
    if (!VirtualProtect(g_margin_at, 1, PAGE_EXECUTE_READWRITE, &old)) return -1;
    g_margin_at[0] = (BYTE)m;
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    FlushInstructionCache(GetCurrentProcess(), g_margin_at, 1);
    return was;
}

static int patch_carmargin(HMODULE strt) {
    static const BYTE expect[] = { 0x8d, 0xbe, 0x90, 0x00, 0x00, 0x00, 0x6a, 0x02, 0xd1, 0xe8 };   /* lea edi,[esi+0x90] / push 2 / shr eax,1 */
    BYTE *p = (BYTE *)strt + 0x13fc3;
    if (memcmp(p, expect, sizeof(expect)) || p[0x20] != 0xe8) {
        logf("### CARMARGIN: STRTSIM+0x13fc3 differs from shipped - NOT armed (sim rect stays view + 2)");
        return 0;
    }
    g_margin_at = p + 7;
    set_car_margin(g_car_margin);
    return 1;
}

__declspec(dllexport) int __cdecl sc3simrun_carmargin(int m) {
    int was = set_car_margin(m);
    logf("CARMARGIN> %d -> %d", was, m);
    return was;
}

__declspec(dllexport) int __cdecl sc3simrun_animate(int on) {
    int was = g_scroll_rate != 0;
    g_scroll_rate = on ? RATE_ON : 0;
    logf("ANIMATE> switched %s (armed=%d)", on ? "on" : "off", g_anim_armed);
    return was;
}

__declspec(dllexport) void __cdecl sc3simrun_stats(DWORD *out) {
    out[0] = (DWORD)g_scroll_frames;
    out[1] = (DWORD)g_agent_ticks;
    out[2] = (DWORD)g_frozen_ticks;
    out[3] = (DWORD)g_strip_calls;
    out[4] = (DWORD)g_tick_swaps;
    out[5] = (DWORD)g_tick_skips;
}

/* ============================================================ CHURN
 * Zone redevelopment rolls (owner 2026-11-01, task churn; re/analysis/ZONE_REDEVELOPMENT.md). The R/C/I per-lot
 * evaluators SIMRCI 0x10028f12 / 0x1000fd53 / 0x10017fc0 run once per lot per ~30 game days and, with demand > 0,
 * redevelop a working building on three rolls, each a `cmp eax, [abs32]` against a SC3Tune.INI global:
 *   upgrade (HigherLandValueRedevelopmentPct, rand(100)), density (HigherDensityRedevelopmentPct, rand(100)),
 *   anarchy (AnarchyFactor, rand(10000): rebuild as the SAME lot class, the churn the owner sees).
 * Each site's 4-byte operand is repointed at a DWORD here, so the roll reads our value. A key at -1 leaves its
 * site untouched (the game's value, SC3Tune or a modded SYS.PAK). Bytes are checked before any write; a site that
 * differs is skipped and logged. LowerLandValueRedevelopmentPct is not offered: its pickers (0x100297fb,
 * 0x10018e45) always return 0, so that roll never decides anything. */

typedef struct { const char *key; DWORD va; DWORD global; } CHURN_SITE;
static const CHURN_SITE g_churn_sites[9] = {
    { "anarchy_res", 0x10029503, 0x1005802c }, { "anarchy_com", 0x1001033b, 0x10057554 },
    { "anarchy_ind", 0x100187cb, 0x100576e4 },
    { "upgrade_res", 0x1002946e, 0x10058020 }, { "upgrade_com", 0x100102a6, 0x10057548 },
    { "upgrade_ind", 0x10018749, 0x100576d8 },
    { "density_res", 0x100294cf, 0x10058028 }, { "density_com", 0x10010307, 0x10057550 },
    { "density_ind", 0x100187a2, 0x100576e0 },
};
static int g_churn_on = 1;
static int g_churn_cfg[9] = { 0, 0, 0, -1, -1, -1, -1, -1, -1 };   /* anarchy off, upgrades as the game has them */
static volatile DWORD g_churn_val[9];

static void churn_ini(const char *path) {
    int i;
    char env[8];
    if (path[0]) {
        g_churn_on = GetPrivateProfileIntA("churn", "enabled", 1, path) ? 1 : 0;
        for (i = 0; i < 9; i++)
            g_churn_cfg[i] = (int)GetPrivateProfileIntA("churn", g_churn_sites[i].key, g_churn_cfg[i], path);
    }
    if (GetEnvironmentVariableA("SC3SIMRUN_CHURN", env, sizeof(env)) && env[0] == '0') g_churn_on = 0;
}

static int churn_arm(HMODULE rci) {
    int i, n = 0;
    DWORD delta = (DWORD)rci - 0x10000000;
    for (i = 0; i < 9; i++) {
        const CHURN_SITE *s = &g_churn_sites[i];
        BYTE *p = (BYTE *)(s->va + delta);
        DWORD old, want = s->global + delta, cur;
        int v = g_churn_cfg[i];
        if (v < 0) continue;
        if (IsBadReadPtr(p, 6) || p[0] != 0x3B || p[1] != 0x05 || memcmp(p + 2, &want, 4)) {
            logf("CHURN> %s: SIMRCI+0x%05lX differs from shipped - NOT patched", s->key, s->va - 0x10000000);
            continue;
        }
        cur = *(DWORD *)want;                    /* the image default (10) until the ctor reads SC3Tune.INI */
        g_churn_val[i] = (DWORD)v;
        if (!VirtualProtect(p + 2, 4, PAGE_EXECUTE_READWRITE, &old)) continue;
        *(DWORD *)(p + 2) = (DWORD)&g_churn_val[i];
        /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
        FlushInstructionCache(GetCurrentProcess(), p + 2, 4);
        logf("CHURN> %s = %d (game global now %lu)", s->key, v, cur);
        n++;
    }
    return n;
}

/* ============================================================ SIRENS
 * Owner 2026-11-02: "avoid looping sirens sounds during gameplay, lower their chances significantly" (task sirens,
 * re/analysis/SIRENS.md, verify/sirens/RESULTS.md).
 * Stock: STRTSIM DecideSirenState 0x100198c0 rolls rand(100) < 0x50 -> 0 (no siren), else 1 / 2, at vehicle placement;
 * FUN_1001b340 re-rolls the same way while the vehicle drives (inline copy, imm8 at 0x1001b44e). The state goes to
 * AUDIO as BoxX event 5. AUDIO keeps one Actor object per [Actor] id (113 fire, 114 police, 130 ambulance; vtable
 * 0x100210ec, ctor 0x10012d97) with ONE state field +0x90: event 5 (slot 14, 0x100138a8) writes it only for the vehicle
 * the actor already tracks (+0x88), the position update (slot 12, 0x100134fb) starts the looped driveby stream on ANY
 * vehicle of that id while +0x90 != 0, nothing clears it on untrack, and the ctor never initializes it (live value
 * 0x444e452c, ",END" heap text). So every on-screen emergency vehicle sounds a siren, one after the other.
 * Fix, three parts with their own switches (A/B), all off with SC3SIMRUN_SIRENS=0 or [sirens] enabled=0:
 *   (b) CHANCE  [sirens] chance_pct (env SC3SIMRUN_SIREN_PCT), 100 = part off. The imm8 0x50 at both roll sites becomes 100 - 20 * chance_pct / 100 (chance_pct = % of the stock chance,
 *           default 20 -> 4 vehicles in 100; 0 = never; 100 = stock; 500 = every vehicle).
 *   (a) PERVEH  [sirens] per_vehicle=1 (env SC3SIMRUN_SIREN_PERVEH), 0 = part off. The four Actor slots that see a vehicle (12 update, 13 / 21 removed, 14 state) are wrapped for actors whose
 *           +0x38 (the [Actor] type field) is 0, the siren type: the state of each vehicle is kept in a table, and
 *           before every position update +0x90 is set to THAT vehicle's state, so only vehicles that rolled a siren
 *           sound one. The stock slots still do all the work.
 *   (c) COOLDOWN [sirens] cooldown_s (env SC3SIMRUN_SIREN_COOL), 0 = part off. After an actor was last audible, a new vehicle may not start it for cooldown_s seconds (default 30).
 * Every byte and vtable slot is checked before it is written; a mismatch leaves that part stock and is logged. */

#define SIR_N 256
typedef struct { BYTE *act; DWORD veh; LONG st; } SIR_ENT;
static SIR_ENT g_sir[SIR_N];
static int g_sir_next;
static CRITICAL_SECTION g_sir_lock;
static BYTE *g_sir_acts[16];                     /* siren actors seen (driveby stream +0x3c), cooldown clock */
static DWORD g_sir_last[16];
static int g_sir_on = 1, g_sir_perveh = 1, g_sir_pct = 20, g_sir_cool = 30;
static volatile LONG g_sir_stat[4];              /* states on recorded, cooldown blocks, updates, removals */
typedef DWORD (__fastcall *PFN_SirUpd)(BYTE *, void *, DWORD, DWORD, DWORD, DWORD);
typedef DWORD (__fastcall *PFN_SirV1)(BYTE *, void *, DWORD);
typedef DWORD (__fastcall *PFN_SirV2)(BYTE *, void *, DWORD, DWORD);
static PFN_SirUpd g_sir_upd;
static PFN_SirV1 g_sir_rm13, g_sir_rm21;
static PFN_SirV2 g_sir_state;

static void sirens_ini(const char *path) {
    char env[16];
    if (path[0]) {
        g_sir_on = GetPrivateProfileIntA("sirens", "enabled", 1, path) ? 1 : 0;
        g_sir_perveh = GetPrivateProfileIntA("sirens", "per_vehicle", 1, path) ? 1 : 0;
        g_sir_pct = (int)GetPrivateProfileIntA("sirens", "chance_pct", 20, path);
        g_sir_cool = (int)GetPrivateProfileIntA("sirens", "cooldown_s", 30, path);
    }
    if (GetEnvironmentVariableA("SC3SIMRUN_SIRENS", env, sizeof(env)) && env[0] == '0') g_sir_on = 0;
    if (GetEnvironmentVariableA("SC3SIMRUN_SIREN_PERVEH", env, sizeof(env))) g_sir_perveh = env[0] != '0';
    if (GetEnvironmentVariableA("SC3SIMRUN_SIREN_PCT", env, sizeof(env))) g_sir_pct = atoi(env);
    if (GetEnvironmentVariableA("SC3SIMRUN_SIREN_COOL", env, sizeof(env))) g_sir_cool = atoi(env);
    if (g_sir_pct < 0) g_sir_pct = 0;
    if (g_sir_pct > 500) g_sir_pct = 500;
    if (g_sir_cool < 0) g_sir_cool = 0;
}

static int sir_find(BYTE *act, DWORD veh) {
    int i;
    for (i = 0; i < SIR_N; i++) if (g_sir[i].veh == veh && g_sir[i].act == act) return i;
    return -1;
}

static void sir_forget(BYTE *act, DWORD veh) {
    int i;
    EnterCriticalSection(&g_sir_lock);
    if ((i = sir_find(act, veh)) >= 0) { g_sir[i].act = NULL; g_sir[i].veh = 0; g_sir[i].st = 0; }
    LeaveCriticalSection(&g_sir_lock);
}

static DWORD *sir_clock(BYTE *act) {
    int i;
    if (!*(DWORD *)(act + 0x3c)) return NULL;     /* no driveby stream: a car honk actor, never a siren */
    for (i = 0; i < 16; i++) {
        if (g_sir_acts[i] == act) return &g_sir_last[i];
        if (!g_sir_acts[i]) { g_sir_acts[i] = act; g_sir_last[i] = 0; return &g_sir_last[i]; }
    }
    return NULL;
}

/* slot 14 0x100138a8 thiscall(veh, state), ret 8 */
static DWORD __fastcall sir_state(BYTE *a, void *edx, DWORD veh, DWORD st) {
    if (g_sir_perveh && *(LONG *)(a + 0x38) == 0 && veh) {
        int i;
        EnterCriticalSection(&g_sir_lock);
        i = sir_find(a, veh);
        if (st) {
            if (i < 0) {
                for (i = 0; i < SIR_N && g_sir[i].veh; i++) {}
                if (i == SIR_N) { i = g_sir_next; g_sir_next = (g_sir_next + 1) % SIR_N; }   /* full: drop the oldest slot */
                g_sir[i].act = a; g_sir[i].veh = veh;
            }
            g_sir[i].st = (LONG)st;
            g_sir_stat[0]++;
        } else if (i >= 0) { g_sir[i].act = NULL; g_sir[i].veh = 0; g_sir[i].st = 0; }
        LeaveCriticalSection(&g_sir_lock);
    }
    return g_sir_state(a, edx, veh, st);
}

/* slot 12 0x100134fb thiscall(veh, x, 0, z), ret 0x10 */
static DWORD __fastcall sir_upd(BYTE *a, void *edx, DWORD veh, DWORD x, DWORD y, DWORD z) {
    LONG saved = 0, blocked = 0;
    DWORD r;
    if (*(LONG *)(a + 0x38) == 0) {
        LONG st;
        DWORD now = GetTickCount(), *last;
        int i;
        saved = *(LONG *)(a + 0x90);
        st = g_sir_perveh ? 0 : saved;           /* per_vehicle=0: the stock shared latch decides */
        EnterCriticalSection(&g_sir_lock);
        if (g_sir_perveh && (i = sir_find(a, veh)) >= 0) st = g_sir[i].st;
        last = g_sir_cool ? sir_clock(a) : NULL;
        LeaveCriticalSection(&g_sir_lock);
        if (last) {
            if (*(DWORD *)(a + 0x88) || *(LONG *)(a + 0xb4) > 0) *last = now;      /* tracking or still audible */
            else if (st && *last && now - *last < (DWORD)g_sir_cool * 1000) { st = 0; blocked = 1; g_sir_stat[1]++; }
        }
        *(LONG *)(a + 0x90) = st;
        g_sir_stat[2]++;
    }
    r = g_sir_upd(a, edx, veh, x, y, z);
    if (blocked && !g_sir_perveh) *(LONG *)(a + 0x90) = saved;   /* keep the stock latch as it was */
    return r;
}

/* slot 13 0x10013873 (event 2) and slot 21 0x10013b5a (event 4): thiscall(veh), ret 4 */
static DWORD __fastcall sir_rm13(BYTE *a, void *edx, DWORD veh) {
    if (g_sir_perveh && *(LONG *)(a + 0x38) == 0 && veh) { sir_forget(a, veh); g_sir_stat[3]++; }
    return g_sir_rm13(a, edx, veh);
}
static DWORD __fastcall sir_rm21(BYTE *a, void *edx, DWORD veh) {
    if (g_sir_perveh && *(LONG *)(a + 0x38) == 0 && veh) { sir_forget(a, veh); g_sir_stat[3]++; }
    return g_sir_rm21(a, edx, veh);
}

static int sir_patch_roll(BYTE *p, const BYTE *tail, int ntail, BYTE thr, const char *what) {
    DWORD old;
    if (IsBadReadPtr(p, 12 + ntail) || p[0] != 0x6a || p[1] != 0x64 || p[2] != 0xb9 || p[7] != 0xe8
        || memcmp(p + 12, tail, ntail)) {
        logf("SIRENS> CHANCE %s differs from shipped - NOT patched", what);
        return 0;
    }
    if (!VirtualProtect(p + 14, 1, PAGE_EXECUTE_READWRITE, &old)) return 0;
    p[14] = thr;
    /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    FlushInstructionCache(GetCurrentProcess(), p + 14, 1);
    return 1;
}

static int sirens_arm(HMODULE strt, HMODULE audio) {
    static const BYTE t1[] = { 0x83, 0xf8, 0x50, 0x73, 0x03, 0x33, 0xc0, 0xc3 };   /* 0x100198cc cmp eax,0x50 / jae / xor / ret */
    static const BYTE t2[] = { 0x83, 0xf8, 0x50, 0x73, 0x04, 0x33, 0xc0, 0xeb };   /* 0x1001b44c cmp eax,0x50 / jae / xor / jmp */
    static const DWORD slot_va[4] = { 0x134fb, 0x13873, 0x138a8, 0x13b5a };
    static const int slot_ix[4] = { 12, 13, 14, 21 };
    BYTE *S = (BYTE *)strt, *U = (BYTE *)audio;
    DWORD *vt = (DWORD *)(U + 0x210ec), old;
    int i, thr = 100 - (20 * g_sir_pct + 50) / 100, n = 0, ok = 1;
    if (thr < 0) thr = 0;
    InitializeCriticalSection(&g_sir_lock);
    if (g_sir_pct != 100) {                      /* (b) CHANCE */
        n += sir_patch_roll(S + 0x198c0, t1, sizeof(t1), (BYTE)thr, "STRTSIM+0x198c0");
        n += sir_patch_roll(S + 0x1b440, t2, sizeof(t2), (BYTE)thr, "STRTSIM+0x1b440");
        logf("SIRENS> (b) CHANCE chance_pct=%d -> rand(100) < %d is no siren (stock 80), %d of 2 sites", g_sir_pct, thr, n);
    } else logf("SIRENS> (b) CHANCE off: chance_pct=100 (stock roll)");
    if (!g_sir_perveh && !g_sir_cool) {
        logf("SIRENS> (a) PERVEH off, (c) COOLDOWN off: AUDIO untouched");
        return n;
    }
    for (i = 0; i < 4; i++)
        if (IsBadReadPtr(vt + slot_ix[i], 4) || vt[slot_ix[i]] != (DWORD)U + slot_va[i]) {
            logf("SIRENS> AUDIO vtable 0x100210ec slot %d holds 0x%08lX, expected 0x%08lX - (a)/(c) NOT armed",
                 slot_ix[i], vt[slot_ix[i]], (DWORD)U + slot_va[i]);
            ok = 0;
        }
    if (!ok) return n;
    if (!VirtualProtect(vt + 12, (21 - 12 + 1) * 4, PAGE_READWRITE, &old)) return n;
    g_sir_upd = (PFN_SirUpd)vt[12]; g_sir_rm13 = (PFN_SirV1)vt[13]; g_sir_state = (PFN_SirV2)vt[14];
    g_sir_rm21 = (PFN_SirV1)vt[21];
    vt[12] = (DWORD)sir_upd; vt[13] = (DWORD)sir_rm13; vt[14] = (DWORD)sir_state; vt[21] = (DWORD)sir_rm21;
    /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    logf("SIRENS> (a) PERVEH %s, (c) COOLDOWN cooldown_s=%d%s (AUDIO slots 12/13/14/21 wrapped)",
         g_sir_perveh ? "on (per-vehicle siren state)" : "off (stock shared latch)", g_sir_cool, g_sir_cool ? "" : " (off)");
    return n + 4;
}

__declspec(dllexport) void __cdecl sc3simrun_sirens(DWORD *out) {
    out[0] = (DWORD)g_sir_stat[0];
    out[1] = (DWORD)g_sir_stat[1];
    out[2] = (DWORD)g_sir_stat[2];
    out[3] = (DWORD)g_sir_stat[3];
}

/* ============================================================ LVWRAP
 * Simtropolis 2026-11-14 ("land value past 255 turns very low"; re/analysis/LAND_VALUE.md, STATUS_lvwrap.md).
 * Stock: SIMRCI 0x1001d616 stores the city land value average as one byte, `div ecx` then `mov [esi+0xc0], al`
 * (0x1001d64c..0x1001d655), with no clamp. The sum (+0xc8) and count (+0xcc) come from 0x1001deca BEFORE the per-cell
 * 1..255 clamp, so a true average of 256 is stored as 0, 300 as 44. GetAverageValue 0x1001b3b7 returns that byte to
 * three readers: property tax SIMMISC 0x100090a7 (income per zone = rate% x valve supply / 100 x max(avg, MinAverageLV)
 * x LVTo{Res,Com,Ind}TaxTransmogrifier/10000; SC3BudgetLayer.INI ships 35 and 35/45/50), the Valor del Terreno graph
 * (0x1001d69b), scenario cmdGetLandValue (SCENARIO 0x10007356). A wrapped byte under 35 pays the floor: measured on
 * Berlin, R tax 1,581 a month at true average 259 (byte 3) against 11,482 with the cap (verify/lvwrap/RESULTS.md). iOS (goLandValueLayer::doDailySim) clamps the same average to
 * 0xff [iOS-HINT].
 * Fix: the 10 bytes become `call lv_stub` + 5 nops; the stub does the same divide, caps the quotient at 255, stores it.
 * [lvwrap] mode=1 (default, cap), 0 = stock bytes, 2 = observe (stub armed, stock wrap kept, the true average logged:
 * the A/B control, since the game zeroes the count right after the store). Env SC3SIMRUN_LVWRAP=0/1/2 wins.
 * Diagnostic (lab only): SC3SIMRUN_LVWRAP_TAX=1 (or _EVERY=1) also calls 0x100090a7 after a logged store and logs
 * R/C/I tax and its inputs; without it a game only divides, caps and writes the LVWRAP average lines.
 * Export sc3simrun_lvwrap(DWORD out[4]) = stores, stores over 255, last true average, last cell count. */

static int g_lv_mode = 1;
static volatile LONG g_lv_calls, g_lv_over;
static volatile DWORD g_lv_raw, g_lv_count;
static int g_lv_logged, g_lv_was_over = -1, g_lv_tell;

/* Property tax per zone, the game's own SIMMISC 0x100090a7 (thiscall(budget, zone) ret 4, __int64), called on the
   game thread right after the store so the log shows what that average pays. The budget pointer from city vt+0x15c
   is accepted only if its +0x14 is the city and its +0x20 the land value interface (the frame 0x100090a7 reads). */
typedef __int64 (__fastcall *PFN_LvTax)(BYTE *budget, void *edx, int zone);
static void lv_tax_log(DWORD stored) {
    BYTE *exe = (BYTE *)GetModuleHandleA(NULL), *app, *city, *b;
    HMODULE misc = GetModuleHandleA("SIMMISC.DLL");
    __int64 tax[3];
    DWORD avg, n[3];
    BYTE *valve;
    int z;
    __try {
        app = *(BYTE **)(exe + 0xfa86c);
        city = app ? *(BYTE **)(app + 0x48) : NULL;
        if (!city || !misc) return;
        b = ((BYTE *(__fastcall *)(BYTE *, void *))(*(DWORD **)city)[0x15c / 4])(city, NULL);
        if (!b || *(BYTE **)(b + 0x14) != city || *(DWORD *)(b + 0x20) != *(DWORD *)(city + 0xf0)) {
            logf("LVWRAP> tax: budget frame not recognised (budget %p) - not read", b);
            return;
        }
        for (z = 0; z < 3; z++) tax[z] = ((PFN_LvTax)((BYTE *)misc + 0x90a7))(b, NULL, z);
        logf("LVWRAP> property tax this month with average byte %lu: R %I64d  C %I64d  I %I64d  (rates %u/%u/%u%%)",
             stored, tax[0], tax[1], tax[2], b[0x8c], b[0x8c + 0x88], b[0x8c + 0x110]);
        /* the inputs 0x100090a7 reads: avg = LandValueLayer vt+0x44, n = valve vt+0x28/+0x2c/+0x30 (+0x40/+0x44/+0x48),
           factor floats SIMMISC 0x1004949c/a0/a4 and floor byte 0x100494a8 as SC3BudgetLayer.INI set them at load */
        avg = ((DWORD (__fastcall *)(BYTE *, void *))(**(DWORD ***)(b + 0x20))[0x44 / 4])(*(BYTE **)(b + 0x20), NULL);
        valve = *(BYTE **)(b + 0x30);
        for (z = 0; z < 3; z++)
            n[z] = ((DWORD (__fastcall *)(BYTE *, void *))(*(DWORD **)valve)[(0x28 + 4 * z) / 4])(valve, NULL);
        {
            float *fac = (float *)((BYTE *)misc + 0x4949c);
            DWORD flo = *((BYTE *)misc + 0x494a8);
            double rc[3];
            for (z = 0; z < 3; z++)
                rc[z] = (double)((b[0x8c + 0x88 * z] * (int)n[z]) / 100 * (int)(n[z] && avg < flo ? flo : avg)) * fac[z];
            logf("LVWRAP> tax inputs: avg %lu, floor %lu (MinAverageLV), factors %.4f/%.4f/%.4f, n R %lu C %lu I %lu;"
                 " (rate*n/100)*max(avg,floor)*factor = %.0f / %.0f / %.0f", avg, flo, fac[0], fac[1], fac[2],
                 n[0], n[1], n[2], rc[0], rc[1], rc[2]);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        logf("LVWRAP> tax: fault reading the budget - not read");
    }
}

static int g_lv_tax = -1;                        /* diagnostic tax line: SC3SIMRUN_LVWRAP_TAX=1 or _EVERY=1 */

static void __cdecl lv_after(BYTE *layer) {
    if (g_lv_tax < 0)
        g_lv_tax = GetEnvironmentVariableA("SC3SIMRUN_LVWRAP_TAX", NULL, 0) || GetEnvironmentVariableA("SC3SIMRUN_LVWRAP_EVERY", NULL, 0);
    if (g_lv_tell && g_lv_tax) lv_tax_log(layer[0xc0]);
    g_lv_tell = 0;
}

static void lvwrap_ini(const char *path) {
    char env[8];
    if (path[0]) g_lv_mode = (int)GetPrivateProfileIntA("lvwrap", "mode", 1, path);
    if (GetEnvironmentVariableA("SC3SIMRUN_LVWRAP", env, sizeof(env)) && env[0] >= '0' && env[0] <= '2')
        g_lv_mode = env[0] - '0';
    if (g_lv_mode < 0 || g_lv_mode > 2) g_lv_mode = 1;
}

/* game thread, once per land value cycle: log the first 3 stores and every crossing of 255 */
static void __cdecl lv_note(DWORD raw, DWORD count) {
    int over = raw > 0xff;
    g_lv_raw = raw; g_lv_count = count;
    InterlockedIncrement(&g_lv_calls);
    if (over) InterlockedIncrement(&g_lv_over);
    if (g_lv_logged < 3 || over != g_lv_was_over) {
        logf("LVWRAP> average %lu over %lu cells -> stored %lu (%s)", raw, count,
             over ? (g_lv_mode == 1 ? 255UL : raw & 0xff) : raw,
             !over ? "under 256, same as stock" : g_lv_mode == 1 ? "capped, stock would store the low byte" : "observe: stock wrap kept");
        g_lv_logged++;
        g_lv_was_over = over;
        g_lv_tell = 1;
    }
    if (GetEnvironmentVariableA("SC3SIMRUN_LVWRAP_EVERY", NULL, 0)) g_lv_tell = 1;   /* lab: tax line every cycle */
}

/* replaces `xor edx,edx / div ecx / mov [esi+0xc0],al` at SIMRCI 0x1001d64c; eax = sum, ecx = count (non-zero),
   esi = land value layer. Leaves eax = stored value, edx = remainder, as stock does (both dead after 0x1001d656). */
static __declspec(naked) void lv_stub(void) {
    __asm {
        xor edx, edx
        div ecx
        push eax
        push ecx
        push edx
        push ecx
        push eax
        call lv_note
        add esp, 8
        pop edx
        pop ecx
        pop eax
        cmp g_lv_mode, 1
        jne store
        cmp eax, 0xff
        jbe store
        mov eax, 0xff
    store:
        mov byte ptr [esi + 0xc0], al
        push eax
        push ecx
        push edx
        push esi
        call lv_after
        add esp, 4
        pop edx
        pop ecx
        pop eax
        ret
    }
}

static int lvwrap_arm(HMODULE rci) {
    static const BYTE want[] = { 0x8b, 0x86, 0xc8, 0x00, 0x00, 0x00,     /* 0x1001d646 mov eax,[esi+0xc8] */
                                 0x33, 0xd2, 0xf7, 0xf1,                 /* 0x1001d64c xor edx,edx / div ecx */
                                 0x88, 0x86, 0xc0, 0x00, 0x00, 0x00,     /* 0x1001d650 mov [esi+0xc0],al */
                                 0xeb, 0x07 };                           /* 0x1001d656 jmp 0x1001d65f */
    BYTE *p = (BYTE *)rci + 0x1d646, *site = p + 6;
    DWORD old;
    if (IsBadReadPtr(p, sizeof(want)) || memcmp(p, want, sizeof(want))) {
        logf("LVWRAP> SIMRCI+0x1d646 differs from shipped - NOT patched");
        return 0;
    }
    if (!VirtualProtect(site, 10, PAGE_EXECUTE_READWRITE, &old)) return 0;
    memset(site + 5, 0x90, 5);
    *(DWORD *)(site + 1) = (DWORD)lv_stub - (DWORD)(site + 5);
    site[0] = 0xe8;
    /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    FlushInstructionCache(GetCurrentProcess(), site, 10);
    return 1;
}

__declspec(dllexport) void __cdecl sc3simrun_lvwrap(DWORD *out) {
    out[0] = (DWORD)g_lv_calls;
    out[1] = (DWORD)g_lv_over;
    out[2] = g_lv_raw;
    out[3] = g_lv_count;
}

/* ============================================================ SANDBOX + GENTLE (abandonment)
 * GitHub issue #3 (2026-11-14), owner decisions 2026-11-15, task abandon (re/analysis/ZONE_REDEVELOPMENT.md section 5).
 * The R/C/I evaluators (SIMRCI 0x10028f12 / 0x1000fd53 / 0x10017fc0) look at each lot once per ~30 game days. A standing
 * building (state 1) is abandoned (re-placed as the same attrib in state 2, sc3_resdev_post_state_change 0x10029a38 /
 * ind 0x100191fe with flag 2) by:
 *   (a) radioactive cell, no roll;
 *   (b) unpowered / not near transport / trip failed / no water at density > 1: rand(100) < NoServicePercentage / x;
 *   (c) raw demand < 0: rand(-valve min) < -(net demand / x);
 *   (d) land value under half the lot class minimum, no roll;
 *   (p) industrial lot class 0x2454 over the ag air / water pollution limits, no roll.
 * Industrial farms are removed (BuildingLayer vt+0x5c) instead in (a), (p), (d). x = the lot width in cells.
 *
 * SANDBOX ([sandbox] enabled=0 default; env SC3SIMRUN_SANDBOX=1/0 wins): no standing R/C/I building is abandoned or
 *   removed by (a)-(d) and (p). The (b) and (c) rolls are made to miss (the game then carries on as after a miss);
 *   the (a), (d), (p) posts and the three farm removals are skipped. Where the game would then re-post the building
 *   for a changed garbage bit (bVar1), the skip makes that same re-post (state 1). Abandoned buildings already in the
 *   city recover as stock. Disasters (SIMDSTR) are not touched.
 * GENTLE ([gentle] enabled=0 default, share_pct=25; env SC3SIMRUN_GENTLE=1/0, SC3SIMRUN_GENTLE_SHARE=<pct>): the (c)
 *   roll may fire only while the raw valve value (what the RCI bar shows) is below min + (max - min) * share_pct / 100.
 *   At or above that line the roll misses; below it the stock roll runs unchanged. Valves read -2000..2000, so
 *   share_pct 25 = value under -1000 = the bar under half of its negative side; 50 = stock; 0 = never.
 * Every patched site is a `call rel32` (or the 14-byte farm removal) checked byte for byte before it is written; a
 * site that differs is left stock and logged. Env SC3SIMRUN_ABANDON_LOG=1 logs every decision. */

static int g_sbx_on = 0, g_gnt_on = 0, g_gnt_share = 25, g_ab_log = 0;
static DWORD g_ab_delta;                          /* SIMRCI base - 0x10000000 */
static volatile LONG g_ab_would[3][6], g_ab_block[3][6], g_ab_held[3];   /* zone R/C/I x branch a b c d p farm */
static DWORD g_ab_last_sum;
static const char *const k_ab_zone[3] = { "res", "com", "ind" };
static const char *const k_ab_br[6] = { "(a) radioactive", "(b) no service", "(c) negative demand", "(d) low land value",
                                        "(p) ag pollution", "farm removal" };

static void abandon_ini(const char *path) {
    char env[16];
    if (path[0]) {
        g_sbx_on = GetPrivateProfileIntA("sandbox", "enabled", 0, path) ? 1 : 0;
        g_gnt_on = GetPrivateProfileIntA("gentle", "enabled", 0, path) ? 1 : 0;
        g_gnt_share = (int)GetPrivateProfileIntA("gentle", "share_pct", 25, path);
    }
    if (GetEnvironmentVariableA("SC3SIMRUN_SANDBOX", env, sizeof(env))) g_sbx_on = env[0] == '1';
    if (GetEnvironmentVariableA("SC3SIMRUN_GENTLE", env, sizeof(env))) g_gnt_on = env[0] == '1';
    if (GetEnvironmentVariableA("SC3SIMRUN_GENTLE_SHARE", env, sizeof(env))) g_gnt_share = atoi(env);
    if (GetEnvironmentVariableA("SC3SIMRUN_ABANDON_LOG", env, sizeof(env))) g_ab_log = env[0] == '1';
    if (g_gnt_share < 0) g_gnt_share = 0;
    if (g_gnt_share > 100) g_gnt_share = 100;
}

static void ab_summary(void) {                    /* at most once a minute, from the game thread */
    DWORD t = GetTickCount();
    int z;
    if (t - g_ab_last_sum < 60000) return;
    g_ab_last_sum = t;
    for (z = 0; z < 3; z++)
        logf("ABANDON> %s: would abandon a/b/c/d/p/farm %ld/%ld/%ld/%ld/%ld/%ld, sandbox blocked %ld/%ld/%ld/%ld/%ld/%ld, "
             "gentle held (c) %ld", k_ab_zone[z], g_ab_would[z][0], g_ab_would[z][1], g_ab_would[z][2], g_ab_would[z][3],
             g_ab_would[z][4], g_ab_would[z][5], g_ab_block[z][0], g_ab_block[z][1], g_ab_block[z][2], g_ab_block[z][3],
             g_ab_block[z][4], g_ab_block[z][5], g_ab_held[z]);
}

/* the (b) and (c) roll call sites: cRZRandom::RandomUint32Uniform 0x10039a9a, frame read at the evaluator's ebp */
typedef DWORD (__fastcall *PFN_AbRand)(void *rng, void *edx, DWORD range);
typedef struct { DWORD call; BYTE zone, br; signed char net, dem, mn, mx, x; DWORD nosvc; BYTE pre[6], post[8]; } AB_ROLL;
static const AB_ROLL g_ab_roll[6] = {      /* x 0 = ebx, else [ebp+x]; br 1 = (b), 2 = (c) */
    { 0x1002951b, 0, 1, 0, 0, 0, 0, 0, 0x10058014, { 0xff,0x6a,0x64,0x8d,0x4e,0x48 }, { 0x8b,0xc8,0xa1,0x14,0x80,0x05,0x10,0x33 } },
    { 0x10010353, 1, 1, 0, 0, 0, 0, 0, 0x1005753c, { 0xff,0x6a,0x64,0x8d,0x4e,0x48 }, { 0x8b,0xc8,0xa1,0x3c,0x75,0x05,0x10,0x33 } },
    { 0x10018557, 2, 1, 0, 0, 0, 0, -0x40, 0x100576cc, { 0x69,0x6a,0x64,0x8d,0x4e,0x78 }, { 0x8b,0xc8,0xa1,0xcc,0x76,0x05,0x10,0x33 } },
    { 0x1002939d, 0, 2, -0x38, -0x18, -0x50, -0x54, 0, 0, { 0x8d,0x4e,0x48,0xf7,0xd8,0x50 }, { 0x8b,0xc8,0x8b,0x45,0xc8,0x99,0xf7,0xfb } },
    { 0x100101d5, 1, 2, -0x34, -0x18, -0x50, -0x54, 0, 0, { 0x8d,0x4e,0x48,0xf7,0xd8,0x50 }, { 0x8b,0xc8,0x8b,0x45,0xcc,0x99,0xf7,0xfb } },
    { 0x10018630, 2, 2, -0x38, -0x24, -0x64, -0x68, -0x40, 0, { 0x8d,0x4e,0x78,0xf7,0xd8,0x50 }, { 0x8b,0xc8,0x8b,0x45,0xc8,0x99,0xf7,0x7d } },
};
static PFN_AbRand g_ab_rand;

static DWORD __cdecl ab_roll(int i, void *rng, DWORD range, BYTE *bp, DWORD ebx) {
    const AB_ROLL *s = &g_ab_roll[i];
    DWORD v = g_ab_rand(rng, NULL, range), x = 1, ret = v;
    LONG net = 0, dem = 0, mn = 0, mx = 0, thr = 0;
    int fire, z = s->zone, what = 0;              /* what: 1 sandbox, 2 gentle held */
    __try {
        x = s->x ? *(DWORD *)(bp + s->x) : ebx;
        if (!x) return v;                         /* the game would divide by it next: leave it to the game */
        if (s->br == 1) fire = v < *(DWORD *)(s->nosvc + g_ab_delta) / x;
        else {
            net = *(LONG *)(bp + s->net); dem = *(LONG *)(bp + s->dem);
            mn = *(LONG *)(bp + s->mn); mx = *(LONG *)(bp + s->mx);
            fire = (LONG)v < -(net / (LONG)x);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) { return v; }
    if (!fire) return v;
    InterlockedIncrement(&g_ab_would[z][s->br]);
    if (g_sbx_on) {
        InterlockedIncrement(&g_ab_block[z][s->br]);
        ret = s->br == 1 ? 0xffffffff : 0x7fffffff;   /* (b) `jae` unsigned, (c) `jge` signed: both now miss */
        what = 1;
    } else if (s->br == 2 && g_gnt_on) {
        thr = mn + (LONG)((__int64)(mx - mn) * g_gnt_share / 100);
        if (dem >= thr) { InterlockedIncrement(&g_ab_held[z]); ret = 0x7fffffff; what = 2; }
    }
    if (g_ab_log)
        logf("ABANDON> %s %s: roll %lu x %lu -> %s", k_ab_zone[z], k_ab_br[s->br], v, x,
             what == 1 ? "blocked (sandbox)" : what == 2 ? "held (gentle)" : "fires");
    if (g_ab_log && s->br == 2) {
        if (g_gnt_on) logf("ABANDON>   demand %ld, net %ld, valve %ld..%ld, gentle line %ld", dem, net, mn, mx, thr);
        else logf("ABANDON>   demand %ld, net %ld, valve %ld..%ld", dem, net, mn, mx);
    }
    ab_summary();
    return ret;
}

#define AB_RSTUB(n) static __declspec(naked) void ab_rstub_##n(void) { __asm push ebx __asm push ebp \
    __asm push dword ptr [esp + 12] __asm push ecx __asm push n __asm call ab_roll __asm add esp, 20 __asm ret 4 }
AB_RSTUB(0) AB_RSTUB(1) AB_RSTUB(2) AB_RSTUB(3) AB_RSTUB(4) AB_RSTUB(5)
static void (*const g_ab_rstub[6])(void) = { ab_rstub_0, ab_rstub_1, ab_rstub_2, ab_rstub_3, ab_rstub_4, ab_rstub_5 };

/* the (a) / (d) / (p) post call sites: post_state_change(bldg, coords*, flags | 2), thiscall, ret 0xc */
typedef BYTE (__fastcall *PFN_AbPost)(void *dev, void *edx, void *bldg, void *coords, DWORD flags);
typedef struct { DWORD call, target; BYTE zone, br; signed char bvar; BYTE pre[6], post[8]; } AB_POST;
static const AB_POST g_ab_post[7] = {      /* bvar = the evaluator's "re-post" byte when the game checks it next, else 0 */
    { 0x1002934f, 0x10029a38, 0, 0, 0,    { 0x02,0x50,0x57,0xff,0x75,0xf0 }, { 0xc7,0x45,0xd4,0x01,0x00,0x00,0x00,0xe9 } },
    { 0x1002942a, 0x10029a38, 0, 3, 0x0b, { 0xc3,0x50,0x57,0xff,0x75,0xf0 }, { 0x80,0x65,0x0b,0x00,0x89,0x5d,0xd4,0xe9 } },
    { 0x10010187, 0x10029a38, 1, 0, 0,    { 0x02,0x50,0x57,0xff,0x75,0xf0 }, { 0xc7,0x45,0xd4,0x01,0x00,0x00,0x00,0xe9 } },
    { 0x10010262, 0x10029a38, 1, 3, 0x0b, { 0xc3,0x50,0x57,0xff,0x75,0xf0 }, { 0x80,0x65,0x0b,0x00,0x89,0x5d,0xd4,0xe9 } },
    { 0x10018523, 0x100191fe, 2, 0, -1,   { 0x02,0x50,0x57,0xff,0x75,0xf0 }, { 0x80,0x65,0xff,0x00,0xeb,0xdd,0x80,0x7d } },
    { 0x10018616, 0x100191fe, 2, 4, -1,   { 0x02,0x50,0x57,0xff,0x75,0xf0 }, { 0x80,0x65,0xff,0x00,0xeb,0xdd,0x83,0x7d } },
    { 0x10018705, 0x100191fe, 2, 3, -1,   { 0xc3,0x50,0x57,0xff,0x75,0xf0 }, { 0x80,0x65,0xff,0x00,0x89,0x5d,0xe4,0xe9 } },
};
static PFN_AbPost g_ab_postfn[7];

static BYTE __cdecl ab_post(int i, void *dev, void *bldg, void *coords, DWORD flags, BYTE *bp) {
    const AB_POST *s = &g_ab_post[i];
    int z = s->zone;
    InterlockedIncrement(&g_ab_would[z][s->br]);
    if (!g_sbx_on) return g_ab_postfn[i](dev, NULL, bldg, coords, flags);
    InterlockedIncrement(&g_ab_block[z][s->br]);
    if (g_ab_log) logf("ABANDON> %s %s: blocked (sandbox) at %lu,%lu", k_ab_zone[z], k_ab_br[s->br],
                       ((DWORD *)coords)[0], ((DWORD *)coords)[1]);
    ab_summary();
    /* the game clears its re-post byte right after this call: make the re-post it would have made (state 1) */
    if (s->bvar && bp[s->bvar]) return g_ab_postfn[i](dev, NULL, bldg, coords, (flags & ~3u) | 1);
    return 0;
}

#define AB_PSTUB(n) static __declspec(naked) void ab_pstub_##n(void) { __asm push ebp \
    __asm push dword ptr [esp + 16] __asm push dword ptr [esp + 16] __asm push dword ptr [esp + 16] __asm push ecx \
    __asm push n __asm call ab_post __asm add esp, 24 __asm ret 12 }
AB_PSTUB(0) AB_PSTUB(1) AB_PSTUB(2) AB_PSTUB(3) AB_PSTUB(4) AB_PSTUB(5) AB_PSTUB(6)
static void (*const g_ab_pstub[7])(void) = { ab_pstub_0, ab_pstub_1, ab_pstub_2, ab_pstub_3, ab_pstub_4, ab_pstub_5, ab_pstub_6 };

/* the industrial farm removals: mov ecx,[esi+0x9c] / push [ebp-0x10] / mov eax,[ecx] / call [eax+0x5c] (14 bytes)
   become push [ebp-0x10] / call ab_fstub_n / 6 x nop. esi = the industrial developer. */
typedef DWORD (__fastcall *PFN_AbRm)(void *layer, void *edx, void *bldg);
static const DWORD g_ab_farm[3] = { 0x100184fd, 0x100185f0, 0x100186dc };
static const BYTE k_ab_farm_bytes[14] = { 0x8b,0x8e,0x9c,0x00,0x00,0x00,0xff,0x75,0xf0,0x8b,0x01,0xff,0x50,0x5c };
static const BYTE k_ab_farm_br[3] = { 0, 4, 3 };

static void __cdecl ab_farm(int i, void *bldg, BYTE *dev) {
    void *layer = *(void **)(dev + 0x9c);
    InterlockedIncrement(&g_ab_would[2][5]);
    if (!g_sbx_on) { ((PFN_AbRm)(*(void ***)layer)[0x5c / 4])(layer, NULL, bldg); return; }
    InterlockedIncrement(&g_ab_block[2][5]);
    if (g_ab_log) logf("ABANDON> ind farm removal in %s: blocked (sandbox)", k_ab_br[k_ab_farm_br[i]]);
    ab_summary();
}

#define AB_FSTUB(n) static __declspec(naked) void ab_fstub_##n(void) { __asm push esi \
    __asm push dword ptr [esp + 8] __asm push n __asm call ab_farm __asm add esp, 12 __asm ret 4 }
AB_FSTUB(0) AB_FSTUB(1) AB_FSTUB(2)
static void (*const g_ab_fstub[3])(void) = { ab_fstub_0, ab_fstub_1, ab_fstub_2 };

/* abs32: the post bytes 3..6 are `mov eax, [abs32]`, which the loader relocates: compare it with the rebased global */
static int ab_call_ok(BYTE *p, DWORD target, const BYTE *pre, const BYTE *post, DWORD abs32) {
    if (IsBadReadPtr(p - 6, 19) || memcmp(p - 6, pre, 6) || p[0] != 0xe8) return 0;
    if (abs32 ? memcmp(p + 5, post, 3) || *(DWORD *)(p + 8) != abs32 + g_ab_delta || p[12] != post[7]
              : memcmp(p + 5, post, 8)) return 0;
    return (DWORD)(p + 5) + *(DWORD *)(p + 1) == target + g_ab_delta;
}

static int ab_set_call(BYTE *p, void (*to)(void)) {
    DWORD old;
    if (!VirtualProtect(p + 1, 4, PAGE_EXECUTE_READWRITE, &old)) return 0;
    *(DWORD *)(p + 1) = (DWORD)to - (DWORD)(p + 5);
    /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    FlushInstructionCache(GetCurrentProcess(), p + 1, 4);
    return 1;
}

/* arms the sites each part needs; returns how many were patched, *want = how many it tried */
static int abandon_arm(HMODULE rci, int *want) {
    int i, n = 0;
    g_ab_delta = (DWORD)rci - 0x10000000;
    g_ab_rand = (PFN_AbRand)(0x10039a9a + g_ab_delta);
    *want = 0;
    for (i = 0; i < 6; i++) {
        const AB_ROLL *s = &g_ab_roll[i];
        BYTE *p = (BYTE *)(s->call + g_ab_delta);
        if (!(g_sbx_on || (g_gnt_on && s->br == 2))) continue;
        ++*want;
        if (!ab_call_ok(p, 0x10039a9a, s->pre, s->post, s->br == 1 ? s->nosvc : 0)) {
            logf("ABANDON> %s %s roll: SIMRCI+0x%05lX differs from shipped - NOT patched", k_ab_zone[s->zone], k_ab_br[s->br],
                 s->call - 0x10000000);
            continue;
        }
        n += ab_set_call(p, g_ab_rstub[i]);
    }
    if (!g_sbx_on) return n;
    for (i = 0; i < 7; i++) {
        const AB_POST *s = &g_ab_post[i];
        BYTE *p = (BYTE *)(s->call + g_ab_delta);
        ++*want;
        if (!ab_call_ok(p, s->target, s->pre, s->post, 0)) {
            logf("ABANDON> %s %s post: SIMRCI+0x%05lX differs from shipped - NOT patched", k_ab_zone[s->zone], k_ab_br[s->br],
                 s->call - 0x10000000);
            continue;
        }
        g_ab_postfn[i] = (PFN_AbPost)(s->target + g_ab_delta);
        n += ab_set_call(p, g_ab_pstub[i]);
    }
    for (i = 0; i < 3; i++) {
        BYTE *p = (BYTE *)(g_ab_farm[i] + g_ab_delta);
        DWORD old;
        ++*want;
        if (IsBadReadPtr(p, 14) || memcmp(p, k_ab_farm_bytes, 14)) {
            logf("ABANDON> ind farm removal %s: SIMRCI+0x%05lX differs from shipped - NOT patched", k_ab_br[k_ab_farm_br[i]],
                 g_ab_farm[i] - 0x10000000);
            continue;
        }
        if (!VirtualProtect(p, 14, PAGE_EXECUTE_READWRITE, &old)) continue;
        p[0] = 0xff; p[1] = 0x75; p[2] = 0xf0;                 /* push dword ptr [ebp-0x10] */
        p[3] = 0xe8; *(DWORD *)(p + 4) = (DWORD)g_ab_fstub[i] - (DWORD)(p + 8);
        memset(p + 8, 0x90, 6);
        FlushInstructionCache(GetCurrentProcess(), p, 14);    /* no restore (task onramp) */
        n++;
    }
    return n;
}

/* measurement: out[0..17] would-abandon counts, zone-major (res a b c d p farm, com ..., ind ...), out[18..35] the same
   for sandbox blocks, out[36..38] gentle holds per zone, out[39] sandbox on, out[40] gentle on, out[41] share_pct */
__declspec(dllexport) void __cdecl sc3simrun_abandon(DWORD *out) {
    int z, b;
    for (z = 0; z < 3; z++) for (b = 0; b < 6; b++) {
        out[z * 6 + b] = (DWORD)g_ab_would[z][b];
        out[18 + z * 6 + b] = (DWORD)g_ab_block[z][b];
    }
    for (z = 0; z < 3; z++) out[36 + z] = (DWORD)g_ab_held[z];
    out[39] = (DWORD)g_sbx_on; out[40] = (DWORD)g_gnt_on; out[41] = (DWORD)g_gnt_share;
}

/* ============================================================ HWYSPEED
 * Simtropolis 2026-11-18 (Spamoidutout: "vehicles going faster on highways"; re/analysis/VEHICLE_SPEED.md,
 * verify/hwyspeed/RESULTS.md). LOOKS ONLY: the animated cars. Trips, traffic density and routing never read this.
 * Stock: a car moves dt * [veh+0x10c] per frame (STRTSIM 0x1001b940, dt = real-time microseconds). +0x10c is set from
 * the current lane path's speed getter, vtable slot +0x3c = 0x1001ddc8 (`fld [ecx+0x24]; ret`), by MoveAlongPath
 * 0x1001b110, 0x10019d50 and appear-on-path 0x1001bc70 `[CONFIRMED]`. path+0x24 = the TrBlkAtt lane edge's
 * e3 * 2.22222e-09 (0x1002066a, constant 0x1002d264). The getter sits in exactly two vtables: forward path 0x1002cf40
 * (slot at 0x1002cf7c) and backward path 0x1002cfa8 (slot at 0x1002cfe4). The car class max speed is read only by boats.
 * Stock lane speeds (e3): road / avenue / rail / subway <= 65,000; highway lanes 94,000-110,000, ramps 74,999-79,999,
 * highway grade changes 70,000. Every lane above 66,000 in the stock and netmod tables (14 TrBlkAtt files) is a
 * highway, highway-crossing or ramp lane, and none is a train or subway lane (verify/hwyspeed/data/sweep66.txt).
 * Fix: both slots point at hws_speed, which returns path+0x24 * factor when it is above threshold e3 * 2.22222e-09.
 * Highway curves and junction pieces stored at 64,000 (stock 14020.., 15001..) are not scaled.
 * Config: [hwyspeed] enabled=1 factor_pct=150 threshold=66000; env SC3SIMRUN_HWYSPEED=0/1, SC3SIMRUN_HWYSPEED_PCT=n.
 * ON by default (owner 2026-11-18, x1.5), mods page row "Faster highway cars" (sc3resize MODTOGGLE writes
 * [env] SC3SIMRUN_HWYSPEED=0 when unchecked). Off leaves the vtables untouched. Export sc3simrun_hwyspeed(pct) sets the factor at run time (A/B in one game;
 * a car picks it up at its next lane path), returns the old one; pct < 0 only reads. */

static int g_hws_on = 1, g_hws_pct = 150, g_hws_thr = 66000;
static volatile float g_hws_mul = 1.5f, g_hws_lim = 0.0f;
static volatile LONG g_hws_calls, g_hws_scaled;

static void hwyspeed_ini(const char *path) {
    char env[16];
    if (path[0]) {
        g_hws_on = GetPrivateProfileIntA("hwyspeed", "enabled", 1, path) ? 1 : 0;
        g_hws_pct = (int)GetPrivateProfileIntA("hwyspeed", "factor_pct", 150, path);
        g_hws_thr = (int)GetPrivateProfileIntA("hwyspeed", "threshold", 66000, path);
    }
    if (GetEnvironmentVariableA("SC3SIMRUN_HWYSPEED", env, sizeof(env))) g_hws_on = env[0] == '1';
    if (GetEnvironmentVariableA("SC3SIMRUN_HWYSPEED_PCT", env, sizeof(env))) g_hws_pct = atoi(env);
    if (g_hws_pct < 25) g_hws_pct = 25;
    if (g_hws_pct > 400) g_hws_pct = 400;
    if (g_hws_thr < 1) g_hws_thr = 1;
    g_hws_mul = (float)g_hws_pct / 100.0f;
}

/* thiscall getter: ecx = path, no stack arguments, float in st(0) (same contract as 0x1001ddc8) */
static float __fastcall hws_speed(BYTE *path, void *edx) {
    float s = *(float *)(path + 0x24);
    (void)edx;
    InterlockedIncrement(&g_hws_calls);
    if (s > g_hws_lim) {
        InterlockedIncrement(&g_hws_scaled);
        s *= g_hws_mul;
    }
    return s;
}

static int hwyspeed_arm(HMODULE strt) {
    BYTE *S = (BYTE *)strt;
    DWORD *slot[2], want = (DWORD)(S + 0x1ddc8), old;
    float k;
    int i;
    slot[0] = (DWORD *)(S + 0x2cf7c);
    slot[1] = (DWORD *)(S + 0x2cfe4);
    if (IsBadReadPtr(S + 0x2d264, 4) || *(DWORD *)(S + 0x2d264) != 0x3118b5b5u) {
        logf("HWYSPEED> e3 scale at STRTSIM+0x2d264 is not 0x3118b5b5 - NOT armed");
        return 0;
    }
    if (IsBadReadPtr(S + 0x1ddc8, 4) || *(DWORD *)(S + 0x1ddc8) != 0xc32441d9u) {
        logf("HWYSPEED> getter STRTSIM+0x1ddc8 is not `fld [ecx+0x24]; ret` - NOT armed");
        return 0;
    }
    for (i = 0; i < 2; i++)
        if (IsBadReadPtr(slot[i], 4) || *slot[i] != want) {
            logf("HWYSPEED> vtable slot STRTSIM 0x%08lX holds 0x%08lX, expected 0x%08lX - NOT armed",
                 0x10000000UL + (DWORD)((BYTE *)slot[i] - S), slot[i] ? *slot[i] : 0, want);
            return 0;
        }
    k = *(float *)(S + 0x2d264);
    g_hws_lim = (float)g_hws_thr * k;
    for (i = 0; i < 2; i++) {
        if (!VirtualProtect(slot[i], 4, PAGE_READWRITE, &old)) return i;
        *slot[i] = (DWORD)hws_speed;      /* no restore (task onramp): a restore can land mid-write in another mod */
    }
    logf("HWYSPEED> lanes faster than e3 %d (%.6g units/us) x%.2f, slots 0x1002cf7c + 0x1002cfe4 wrapped",
         g_hws_thr, (double)g_hws_lim, (double)g_hws_mul);
    return 2;
}

__declspec(dllexport) int __cdecl sc3simrun_hwyspeed(int pct) {
    int was = (int)(g_hws_mul * 100.0f + 0.5f);
    if (pct >= 0) {
        if (pct < 25) pct = 25;
        if (pct > 400) pct = 400;
        g_hws_mul = (float)pct / 100.0f;
        logf("HWYSPEED> factor %d%% -> %d%% (calls %ld, scaled %ld)", was, pct, g_hws_calls, g_hws_scaled);
    }
    return was;
}

/* ============================================================ sampler */

static DWORD WINAPI sampler(LPVOID param) {
    HMODULE simcity = NULL;
    int resume = 0, resumed = 0, stable = 0, trace = 0;
    DWORD last_susp = 0xffffffff;
    char env[8];
    (void)param;
    if (GetEnvironmentVariableA("SC3SIMRUN_RESUME", env, sizeof(env)) && env[0] == '1') resume = 1;
    if (GetEnvironmentVariableA("SC3SIMRUN_TRACE", env, sizeof(env)) && env[0] == '1') trace = 1;

    {   HMODULE spr;
        int ok = 0, anim = 0;
        while (!(spr = GetModuleHandleA("SIMSPR.DLL"))) Sleep(1);
        if (g_run) ok = patch_scroll_hold(spr);
        if (g_run && g_anim) anim = patch_scroll_anim(spr);
        logf("### READY: run_while_scrolling=%d patched=%d trace=%d", g_run, ok, trace);
        logf("### ANIMATE: animate_while_scrolling=%d armed=%d%s", g_anim, anim,
             g_anim && !g_run ? " (needs run_while_scrolling=1: the stock camera hold suspends the heartbeat)" : "");
    }
    if (g_churn_on) {
        HMODULE rci;
        while (!(rci = GetModuleHandleA("SIMRCI.DLL"))) Sleep(5);
        logf("### CHURN: %d site(s) armed", churn_arm(rci));
    } else logf("### CHURN: off (stock redevelopment rolls)");
    if (g_sir_on) {
        HMODULE strt, au;
        while (!(strt = GetModuleHandleA("STRTSIM.DLL"))) Sleep(5);
        while (!(au = GetModuleHandleA("AUDIO.DLL"))) Sleep(5);
        logf("### SIRENS: %d patch sites armed (2 roll bytes + 4 AUDIO slots when all parts are on)", sirens_arm(strt, au));
    } else logf("### SIRENS: off (stock siren chance and the shared per-id siren state)");
    if (g_hws_on) {
        HMODULE strt;
        while (!(strt = GetModuleHandleA("STRTSIM.DLL"))) Sleep(5);
        logf("### HWYSPEED: on, factor_pct=%d threshold=%d, %d of 2 slots armed", g_hws_pct, g_hws_thr, hwyspeed_arm(strt));
    } else logf("### HWYSPEED: off (stock lane speeds for the animated cars)");
    if (g_lv_mode) {
        HMODULE rci;
        while (!(rci = GetModuleHandleA("SIMRCI.DLL"))) Sleep(5);
        logf("### LVWRAP: mode=%d (%s), armed=%d", g_lv_mode, g_lv_mode == 1 ? "land value average capped at 255"
             : "observe, stock wrap kept", lvwrap_arm(rci));
    } else logf("### LVWRAP: off (stock land value average byte, wraps past 255)");
    {   int n = 0, want = 0;
        if (g_sbx_on || g_gnt_on) {
            HMODULE rci;
            while (!(rci = GetModuleHandleA("SIMRCI.DLL"))) Sleep(5);
            n = abandon_arm(rci, &want);
        }
        if (g_sbx_on) logf("### SANDBOX: on, no R/C/I building abandoned or removed by the zone evaluators; %d of %d sites armed", n, want);
        else logf("### SANDBOX: off (stock abandonment)");
        if (g_gnt_on) logf("### GENTLE: on, share_pct=%d: the negative-demand roll only while the RCI valve is under min + range * %d%%%s",
                           g_gnt_share, g_gnt_share, g_sbx_on ? " (Sandbox is on and wins)" : "");
        else logf("### GENTLE: off (stock negative-demand roll)");
    }
    while (!(simcity = GetModuleHandleA("SIMCITY.DLL"))) Sleep(5);
    if (g_anim_armed) {
        HMODULE strt;
        while (!(strt = GetModuleHandleA("STRTSIM.DLL"))) Sleep(5);
        logf("### STRIPS: armed=%d", patch_strips(strt));
        logf("### TICKSTRIP: armed=%d", patch_tickstrip(strt));
        logf("### CARMARGIN: armed=%d car_margin=%d", patch_carmargin(strt), g_car_margin);
    }
    if (g_freeze) {
        HMODULE strt;
        while (!(strt = GetModuleHandleA("STRTSIM.DLL"))) Sleep(5);
        logf("### FREEZE: freeze_on_pause=%s, armed=%d", g_freeze == 1 ? "cars" : "street", freeze_arm(strt, simcity));
    } else logf("### FREEZE: freeze_on_pause=0 (stock)");
    if (!trace && !resume) {
        int paused, was = -1;
        if (!g_freeze_armed) return 0;
        for (;;) {                                   /* log pause edges with the frozen-tick count */
            Sleep(250);
            __try { paused = user_paused(); } __except (EXCEPTION_EXECUTE_HANDLER) { paused = was; }
            if (paused != was) {
                logf("FREEZE> %s: agent ticks %ld, frozen %ld", paused ? "paused" : "running", g_agent_ticks, g_frozen_ticks);
                was = paused;
            }
        }
    }

    g_simcity = (DWORD)simcity;
    logf("### SIMCITY.DLL at 0x%08lX, coord hook %s, clock hook %s, hold hook %s", (DWORD)simcity,
         coord_arm(simcity) ? "ARMED" : "FAILED", trace && clock_arm(simcity) ? "ARMED" : "off",
         trace && cohold_arm(simcity) ? "ARMED" : "off");

    for (;;) {
        BYTE *c = (BYTE *)g_coord, *clk;
        DWORD pb, susp, cpause, c40, c44, c4c;
        LONG msgs;
        Sleep(50);
        if (!c || IsBadReadPtr(c, 0x218) || *(DWORD *)c != g_simcity + 0x13260) continue;
        clk = *(BYTE **)(c + 0x130);
        if (!clk || IsBadReadPtr(clk, 0x70)) continue;
        pb = *(BYTE *)(c + 0x38) & 1;
        susp = *(DWORD *)(c + 0x140);
        cpause = *(DWORD *)(clk + 0x54);
        c40 = *(DWORD *)(clk + 0x40); c44 = *(DWORD *)(clk + 0x44); c4c = *(DWORD *)(clk + 0x4c);
        msgs = InterlockedExchange((LONG *)&g_coord_msgs, 0);
        if (trace) logf("S t=%I64u coord=%08lX pb=%lu susp=%lu cpause=%lu c40=%lu c44=%lu cur=%lu msgs=%ld",
             epoch_ms(), (DWORD)c, pb, susp, cpause, c40, c44, c4c, msgs);

        if (resume && !resumed) {
            stable = (susp == last_susp) ? stable + 1 : 0;
            last_susp = susp;
            if (stable >= 100) {                       /* 5 s with the same depth: load is done */
                DWORD i;
                for (i = 0; i < susp; i++) gz_post(0xc2a35d80, 0);
                logf("### RESUME: posted 0xc2a35d80 x%lu", susp);
                if (GetEnvironmentVariableA("SC3SIMRUN_SPEED", env, sizeof(env)) && env[0] >= '1' && env[0] <= '9') {
                    gz_post(0xc2684065, (DWORD)(env[0] - '0'));     /* set speed (sc3probe.c msg notes) */
                    logf("### SPEED: posted 0xc2684065,%c", env[0]);
                }
                resumed = 1;
            }
        }
    }
}

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        if (!sc3mods_guard(inst, "sc3simrun")) return TRUE;   /* not our loader: stay inert (sc3mods_guard.h) */
        g_self = (HMODULE)inst;
        DisableThreadLibraryCalls(inst);
        InitializeCriticalSection(&g_lock);
        QueryPerformanceFrequency(&g_freq);
        QueryPerformanceCounter(&g_t0);
        ini_read();
        log_open();
        logf("### sc3simrun loaded");
        CreateThread(NULL, 0, sampler, NULL, 0, NULL);
    }
    return TRUE;
}
