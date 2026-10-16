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
 *
 * Config: simrun.ini beside the DLL:  [sim] run_while_scrolling=1   (0 = stock, the A/B control)
 *                                     [sim] freeze_on_pause=street  (cars = cars only, 0 = stock)
 *                                     [sim] animate_while_scrolling=1 (0 = agents freeze during camera moves, stock)
 * Exports (measurement): sc3simrun_animate(on) switches the scroll-frame rate at run time (returns the old state),
 *         sc3simrun_stats(DWORD out[4]) = scroll frames seen by the stub, agent ticks, frozen agent ticks, strip refills.
 * Env:    SC3SIMRUN_LOG=<abs path>  SC3SIMRUN_TRACE=1 (20 Hz sampler + hold/pause caller log)
 *         SC3SIMRUN_RESUME=1 (test only: post 0xc2a35d80 once per unit of +0x140 after load)
 * Build:  re/harness/build_simrun.ps1. Ships via mods_launch.exe.
 */

#include <windows.h>
#include <stdio.h>
#include <string.h>

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
    if (!VirtualProtect(slot, 4, PAGE_READWRITE, &old)) return 0;
    g_coord_orig = (void *)*slot;
    *slot = (DWORD)coord_thunk;
    VirtualProtect(slot, 4, old, &old);
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
    if (!VirtualProtect(slot, 8, PAGE_READWRITE, &old)) return 0;
    g_clk_pause = (PFN_Clk)slot[0]; g_clk_resume = (PFN_Clk)slot[1];
    slot[0] = (DWORD)clk_pause; slot[1] = (DWORD)clk_resume;
    VirtualProtect(slot, 8, old, &old);
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
    if (!VirtualProtect(slot, 8, PAGE_READWRITE, &old)) return 0;
    g_co_hold = (PFN_Co)slot[0]; g_co_release = (PFN_Co)slot[1];
    slot[0] = (DWORD)co_hold; slot[1] = (DWORD)co_release;
    VirtualProtect(slot, 8, old, &old);
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

static void ini_read(void) {
    char path[MAX_PATH];
    self_path(path, sizeof(path), "simrun.ini");
    if (path[0]) g_run = GetPrivateProfileIntA("sim", "run_while_scrolling", 1, path) ? 1 : 0;
    if (path[0]) g_anim = GetPrivateProfileIntA("sim", "animate_while_scrolling", 1, path) ? 1 : 0;
    if (path[0]) {
        char v[16];
        GetPrivateProfileStringA("sim", "freeze_on_pause", "street", v, sizeof(v), path);
        g_freeze = !lstrcmpiA(v, "cars") ? 1 : (!lstrcmpiA(v, "0") || !lstrcmpiA(v, "off")) ? 0 : 2;
    }
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
    VirtualProtect(p, 6, old, &old);
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
    VirtualProtect(p + 12, 1, old, &old);
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
        VirtualProtect(q, 5, old, &old);
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
    VirtualProtect(p, 6, old, &old);
    FlushInstructionCache(GetCurrentProcess(), p, 6);
    g_strip_armed = 1;
    return 1;
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
    while (!(simcity = GetModuleHandleA("SIMCITY.DLL"))) Sleep(5);
    if (g_anim_armed) {
        HMODULE strt;
        while (!(strt = GetModuleHandleA("STRTSIM.DLL"))) Sleep(5);
        logf("### STRIPS: armed=%d", patch_strips(strt));
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
