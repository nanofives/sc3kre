/* sc3modldr.c -> version.dll : loads the sc3kre mods into SC3U.exe without injection (2026-10-21).
 *
 * WHY. mods_launch.exe used to start SC3U.exe suspended and inject every mod with VirtualAllocEx +
 * WriteProcessMemory + CreateRemoteThread(LoadLibraryA). Windows Defender now blocks that launcher as
 * "Behavior:Win32/DefenseEvasion.A!ml" (ML behaviour detection), on the dev PCs and on the LAN release. Owner
 * decision: load the mods with no injection at all. This DLL is the replacement: the Windows loader itself maps it,
 * because SC3U.exe imports VERSION.dll and VERSION.dll is not a KnownDLL, so the copy beside the exe (Apps\) wins.
 *
 * WHY THE EARLIER PROXIES NEVER RAN (proxy_version.c, proxy_winmm.c, re/analysis/PREFS_UI.md). Both were "mapped but
 * never entered". Cause, settled 2026-10-21: their export tables were incomplete, so process init failed with an
 * entry-point-not-found hard error before any DllMain ran (the process sits with no window, one thread in LpcReply).
 *   - winmm: SC3U.exe imports only timeGetTime, but UV.DLL (a static import of SC3U.exe) imports mmioSetBuffer,
 *     mmioOpenA, mmioSeek, mmioRead, mmioClose.
 *   - version: SC3U.exe imports the 3 A functions, but AcGenral.dll (the AppCompat shim DLL, loaded because shims
 *     apply to SC3U.exe) imports GetFileVersionInfoW / SizeW / ExW and VerQueryValueW.
 * So this proxy exports ALL 17 names of the system version.dll, same ordinals (sc3modldr.def), each one a jmp to
 * the real function. Any module in the process may import any of them.
 *
 * WHAT IT DOES. Nothing at all unless mods_launch.exe started the game: it reads SC3MODS_DIR / SC3MODS_LIST
 * (set by the launcher). Without them, or in a process that is not this SC3U.exe build (Baapp.exe also picks this
 * DLL up through the shim DLLs), it is a pure forwarder. With them:
 *   DllMain (loader lock held): checks the 5 entry-point bytes and the mutex-name slot, then overwrites the exe's
 *   entry point with a jmp to ep_hook. No LoadLibrary here.
 *   ep_hook (main thread, all static DLLs initialised, no loader lock, before the CRT and WinMain): puts the 5 bytes
 *   back, renames the single-instance mutex for -multi (same patch as mods_launch's old unique_mutex, now done from
 *   inside the process), LoadLibrary's every listed mod in order, signals the launcher, jumps to the real entry.
 * This is the same moment the injected mods used to load (the remote thread ran process init, then LoadLibraryA,
 * and the main thread started only after it), so startup hooks (sc3resize's loader notification and STARTRES,
 * sc3undo, sc3netmod) see the same state.
 *
 * Environment (all set by mods_launch.exe):
 *   SC3MODS_DIR    folder holding the mod DLLs (release: Apps; dev: the instance folder)
 *   SC3MODS_LIST   mod file names in load order, ';'-separated
 *   SC3MODS_MULTI  1 = per-instance mutex "SimCity 3000 Mutex <pid>"
 *   SC3MODS_EVENT  named event the launcher waits on; set once the mods are loaded (or failed)
 *   SC3MODS_DELAY  ms: load the mods from a thread after this delay instead (old mods_launch -delay test option)
 * Log: <SC3MODS_DIR>\sc3modldr.log, appended, one "[pid N]" prefix per line.
 * A mod that fails to load ends the game with exit code SC3MODS_EXIT_LOADFAIL (mods_launch reports it, exit 4),
 * the same all-or-nothing rule the injector had.
 */
#include <windows.h>
#include <stdio.h>
#include <string.h>

#define SC3MODS_EXIT_LOADFAIL 0x5C30004u   /* mods_launch.c knows this value */

/* ---- this SC3U.exe build (anchor 49DD55E1...), image-relative ---- */
#define EP_RVA      0x000b4b54             /* AddressOfEntryPoint */
#define SLOT_RVA    0x000f4b10             /* pointer to the mutex name, FUN_0040496d reads it */
#define NAME_RVA    0x000f4b24             /* "SimCity 3000 Mutex" */
static const unsigned char k_ep_bytes[5] = { 0x55, 0x8b, 0xec, 0x6a, 0xff };   /* push ebp; mov ebp,esp; push -1 */

/* =====================================================================================================
 * Forwarders: the 17 exports of the system version.dll.
 * ===================================================================================================== */
static const char *const k_names[17] = {
    "GetFileVersionInfoA", "GetFileVersionInfoByHandle", "GetFileVersionInfoExA", "GetFileVersionInfoExW",
    "GetFileVersionInfoSizeA", "GetFileVersionInfoSizeExA", "GetFileVersionInfoSizeExW", "GetFileVersionInfoSizeW",
    "GetFileVersionInfoW", "VerFindFileA", "VerFindFileW", "VerInstallFileA", "VerInstallFileW",
    "VerLanguageNameA", "VerLanguageNameW", "VerQueryValueA", "VerQueryValueW"
};
/* stdcall argument bytes, only for the "function missing on this Windows" stub */
static const unsigned char k_argbytes[17] = { 16, 16, 20, 20, 8, 12, 12, 8, 16, 32, 32, 32, 32, 12, 12, 16, 16 };
static FARPROC g_fn[17];
static HMODULE g_real;

static __declspec(naked) void fail_0(void)  { __asm { xor eax, eax } __asm { ret } }
static __declspec(naked) void fail_8(void)  { __asm { xor eax, eax } __asm { ret 8 } }
static __declspec(naked) void fail_12(void) { __asm { xor eax, eax } __asm { ret 12 } }
static __declspec(naked) void fail_16(void) { __asm { xor eax, eax } __asm { ret 16 } }
static __declspec(naked) void fail_20(void) { __asm { xor eax, eax } __asm { ret 20 } }
static __declspec(naked) void fail_32(void) { __asm { xor eax, eax } __asm { ret 32 } }

static FARPROC fail_stub(int bytes) {
    switch (bytes) {
    case 8: return (FARPROC)fail_8;   case 12: return (FARPROC)fail_12; case 16: return (FARPROC)fail_16;
    case 20: return (FARPROC)fail_20; case 32: return (FARPROC)fail_32; default: return (FARPROC)fail_0;
    }
}

static void load_real(void) {
    char p[MAX_PATH];
    UINT n;
    if (g_real) return;
    n = GetSystemDirectoryA(p, MAX_PATH - 16);      /* WOW64: System32 is redirected to SysWOW64 */
    if (!n || n >= MAX_PATH - 16) return;
    lstrcpyA(p + n, "\\version.dll");
    g_real = LoadLibraryA(p);
}

/* cdecl, called from fwd_common with the export index; returns the target (never NULL). */
static FARPROC __cdecl resolve(int i) {
    FARPROC f = g_fn[i];
    if (f) return f;
    load_real();
    if (g_real) f = GetProcAddress(g_real, k_names[i]);
    if (!f) {
        SetLastError(ERROR_PROC_NOT_FOUND);
        f = fail_stub(k_argbytes[i]);
    }
    g_fn[i] = f;
    return f;
}

/* The stack is untouched between the caller's call and the final jmp, so every stdcall signature works. eax/ecx/edx
   are caller-saved in stdcall, resolve() keeps the rest. */
static __declspec(naked) void fwd_common(void) {
    __asm {
        push eax
        call resolve
        add  esp, 4
        jmp  eax
    }
}
#define FWD(i, name) __declspec(naked) void x_##name(void) { __asm { mov eax, i } __asm { jmp fwd_common } }
FWD(0,  GetFileVersionInfoA)
FWD(1,  GetFileVersionInfoByHandle)
FWD(2,  GetFileVersionInfoExA)
FWD(3,  GetFileVersionInfoExW)
FWD(4,  GetFileVersionInfoSizeA)
FWD(5,  GetFileVersionInfoSizeExA)
FWD(6,  GetFileVersionInfoSizeExW)
FWD(7,  GetFileVersionInfoSizeW)
FWD(8,  GetFileVersionInfoW)
FWD(9,  VerFindFileA)
FWD(10, VerFindFileW)
FWD(11, VerInstallFileA)
FWD(12, VerInstallFileW)
FWD(13, VerLanguageNameA)
FWD(14, VerLanguageNameW)
FWD(15, VerQueryValueA)
FWD(16, VerQueryValueW)

/* Lets mods_launch (and anyone) tell this file from the system version.dll: GetProcAddress-free check is a
   string search for "sc3modldr" in the file. */
const char sc3modldr_id[] = "sc3modldr 1 (2026-10-21)";

/* =====================================================================================================
 * Mod loading.
 * ===================================================================================================== */
static char g_dir[MAX_PATH];
static char g_list[1024];
static char g_event[128];
static char g_log[MAX_PATH];
static int  g_multi;
static int  g_delay;
static unsigned char *g_ep;
static char g_mutex_name[64];

static void logf(const char *fmt, ...) {
    char line[1024];
    int n;
    va_list ap;
    HANDLE h;
    DWORD w;
    if (!g_log[0]) return;
    n = _snprintf(line, sizeof(line) - 2, "[pid %lu] ", GetCurrentProcessId());
    va_start(ap, fmt);
    n += _vsnprintf(line + n, sizeof(line) - 2 - n, fmt, ap);
    va_end(ap);
    if (n < 0 || n > (int)sizeof(line) - 2) n = (int)sizeof(line) - 2;
    line[n++] = '\r'; line[n++] = '\n';
    h = CreateFileA(g_log, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_ALWAYS,
                    FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) return;
    WriteFile(h, line, n, &w, NULL);
    CloseHandle(h);
}

static void signal_launcher(void) {
    HANDLE e;
    if (!g_event[0]) return;
    e = OpenEventA(EVENT_MODIFY_STATE, FALSE, g_event);
    if (e) { SetEvent(e); CloseHandle(e); }
}

/* -multi: same patch mods_launch.c applied with WriteProcessMemory, now from inside. A failed acquire of the shared
   name makes the game focus the other window and exit, so a refusal here is logged and the game runs single. */
static void unique_mutex(unsigned char *base) {
    DWORD *slot = (DWORD *)(base + SLOT_RVA);
    DWORD oldp;
    if (*slot != (DWORD)(base + NAME_RVA)) {
        logf("[!] -multi: mutex name pointer is 0x%08lX, expected 0x%08lX - not renamed", *slot, (DWORD)(base + NAME_RVA));
        return;
    }
    _snprintf(g_mutex_name, sizeof(g_mutex_name), "SimCity 3000 Mutex %lu", GetCurrentProcessId());
    if (!VirtualProtect(slot, 4, PAGE_READWRITE, &oldp)) { logf("[!] -multi: VirtualProtect failed %lu", GetLastError()); return; }
    *slot = (DWORD)g_mutex_name;
    VirtualProtect(slot, 4, oldp, &oldp);
    logf("[+] -multi: mutex renamed to \"%s\"", g_mutex_name);
}

/* Returns 1 when every listed mod loaded. */
static int load_mods(void) {
    char list[1024], path[MAX_PATH];
    char *p, *next;
    int n = 0;
    lstrcpynA(list, g_list, sizeof(list));
    for (p = list; p && *p; p = next) {
        HMODULE m;
        next = strchr(p, ';');
        if (next) *next++ = 0;
        if (!*p) continue;
        _snprintf(path, sizeof(path), "%s\\%s", g_dir, p);
        m = LoadLibraryA(path);
        if (!m) { logf("[!] LoadLibrary %s failed, GetLastError=%lu", path, GetLastError()); return 0; }
        logf("[+] loaded %s (HMODULE = 0x%08lX)", p, (DWORD)m);
        n++;
    }
    logf("[+] %d mod(s) loaded", n);
    return 1;
}

static DWORD WINAPI delayed_load(LPVOID unused) {
    (void)unused;
    Sleep(g_delay);
    if (!load_mods()) { signal_launcher(); TerminateProcess(GetCurrentProcess(), SC3MODS_EXIT_LOADFAIL); }
    signal_launcher();
    return 0;
}

/* Called from ep_hook on the main thread. */
static void __cdecl startup(void) {
    DWORD oldp;
    unsigned char *base = (unsigned char *)GetModuleHandleA(NULL);
    VirtualProtect(g_ep, 5, PAGE_EXECUTE_READWRITE, &oldp);
    memcpy(g_ep, k_ep_bytes, 5);
    VirtualProtect(g_ep, 5, oldp, &oldp);
    FlushInstructionCache(GetCurrentProcess(), g_ep, 5);
    logf("entry point reached, base 0x%08lX, mods from %s", (DWORD)base, g_dir);
    if (g_multi) unique_mutex(base);
    if (g_delay > 0) {
        HANDLE t = CreateThread(NULL, 0, delayed_load, NULL, 0, NULL);
        logf("[*] loading in %d ms from a thread", g_delay);
        if (t) CloseHandle(t);
        return;
    }
    if (!load_mods()) {
        signal_launcher();
        TerminateProcess(GetCurrentProcess(), SC3MODS_EXIT_LOADFAIL);
    }
    signal_launcher();
}

static __declspec(naked) void ep_hook(void) {
    __asm {
        pushad
        pushfd
        call startup
        popfd
        popad
        jmp  dword ptr [g_ep]
    }
}

/* DllMain: decide, and arm the entry-point hook. No LoadLibrary of a mod here (loader lock). */
static void arm(void) {
    unsigned char *base = (unsigned char *)GetModuleHandleA(NULL);
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)base;
    IMAGE_NT_HEADERS *nt;
    char v[16];
    DWORD oldp;
    LONG rel;

    if (!GetEnvironmentVariableA("SC3MODS_DIR", g_dir, sizeof(g_dir)) || !g_dir[0]) return;     /* not ours to load */
    if (!GetEnvironmentVariableA("SC3MODS_LIST", g_list, sizeof(g_list))) g_list[0] = 0;
    if (!GetEnvironmentVariableA("SC3MODS_EVENT", g_event, sizeof(g_event))) g_event[0] = 0;
    g_multi = GetEnvironmentVariableA("SC3MODS_MULTI", v, sizeof(v)) && v[0] == '1';
    g_delay = GetEnvironmentVariableA("SC3MODS_DELAY", v, sizeof(v)) ? atoi(v) : 0;
    _snprintf(g_log, sizeof(g_log), "%s\\sc3modldr.log", g_dir);
    /* The env is inherited by anything the game starts; a child process must not load the mods again. */
    SetEnvironmentVariableA("SC3MODS_DIR", NULL);

    nt = (IMAGE_NT_HEADERS *)(base + dos->e_lfanew);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE || nt->Signature != IMAGE_NT_SIGNATURE
        || nt->OptionalHeader.AddressOfEntryPoint != EP_RVA || memcmp(base + EP_RVA, k_ep_bytes, 5) != 0) {
        char exe[MAX_PATH];
        GetModuleFileNameA(NULL, exe, sizeof(exe));
        logf("[!] %s is not the SC3U.exe build this loader knows (entry point) - mods NOT loaded", exe);
        signal_launcher();
        return;
    }
    g_ep = base + EP_RVA;
    rel = (LONG)((unsigned char *)ep_hook - (g_ep + 5));
    if (!VirtualProtect(g_ep, 5, PAGE_EXECUTE_READWRITE, &oldp)) {
        logf("[!] VirtualProtect(entry point) failed %lu - mods NOT loaded", GetLastError());
        signal_launcher();
        return;
    }
    g_ep[0] = 0xE9;
    memcpy(g_ep + 1, &rel, 4);
    VirtualProtect(g_ep, 5, oldp, &oldp);
    FlushInstructionCache(GetCurrentProcess(), g_ep, 5);
    logf("armed: entry point 0x%08lX -> loader, list \"%s\"%s", (DWORD)g_ep, g_list, g_multi ? ", -multi" : "");
}

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID res) {
    (void)res;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(inst);
        load_real();              /* the system version.dll needs only kernelbase/ntdll, already initialised */
        arm();
    }
    return TRUE;
}
