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
 * Config: simrun.ini beside the DLL:  [sim] run_while_scrolling=1   (0 = stock, the A/B control)
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

static void ini_read(void) {
    char path[MAX_PATH];
    self_path(path, sizeof(path), "simrun.ini");
    if (path[0]) g_run = GetPrivateProfileIntA("sim", "run_while_scrolling", 1, path) ? 1 : 0;
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
        int ok = 0;
        while (!(spr = GetModuleHandleA("SIMSPR.DLL"))) Sleep(1);
        if (g_run) ok = patch_scroll_hold(spr);
        logf("### READY: run_while_scrolling=%d patched=%d trace=%d", g_run, ok, trace);
    }
    if (!trace && !resume) return 0;

    while (!(simcity = GetModuleHandleA("SIMCITY.DLL"))) Sleep(5);
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
