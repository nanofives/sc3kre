/* sc3modldr.c -> version.dll : loads the sc3kre mods into SC3U.exe, Defender-clean (rewritten 2026-10-25, loader2).
 *
 * WHY THE REWRITE. The previous build was flagged by Windows Defender as `Program:Win32/Contebrew.A!ml` (cloud ML,
 * real-time on-access; signatures 1.461.192.0, 2026-10-25) so the file was quarantined and no mods loaded. The flag
 * scores the DLL-sideloading-loader *shape*: a version.dll beside the exe forwarding all 17 exports AND patching the
 * host entry point (0xE9 into .text) under PAGE_EXECUTE_READWRITE AND LoadLibrary'ing a list from env vars. Triage
 * (verify/loader2/RESULTS.md) built three variants and tested them the way Defender caught the original (RTP
 * on-access, MpCmdRun is blind to this detection). Finding: removing the entry-point inline patch and the RWX
 * VirtualProtect clears the strong signals; mods load fine straight from DllMain (fast once the DLLs have reputation,
 * ~24 s only on the very first load of freshly-built DLLs while Defender scans each new hash), and this is EARLY
 * enough - it runs during process init, before the CRT and WinMain, before GZGraphicD's dynamic load, which is the
 * window sc3resize's EARLY loader-notification and DPI-awareness need (confirmed in the logs: every mod loads with
 * "GZGraphicD loaded now? no", DPI set PER_MONITOR_AWARE_V2 before any window, EARLY notification registered).
 *
 * WHAT CHANGED vs the 2026-10-21 build:
 *   - GONE: the entry-point inline patch (no 0xE9 written into the exe), the PAGE_EXECUTE_READWRITE VirtualProtect on
 *     the host .text, the ep_hook / startup trampoline, TerminateProcess on failure.
 *   - The mods are LoadLibrary'd directly from DllMain (DLL_PROCESS_ATTACH of this static-import version.dll).
 *   - NEW: a built-in default mod list, so starting Apps\SC3U.exe normally loads the mods with no launcher at all
 *     (mods_launch.exe is no longer required; it is also ASR-flagged, so the release .bat now starts SC3U.exe
 *     directly). "Stock" = rename/remove version.dll, or set SC3MODS_OFF=1.
 *   - KEPT: the 17 version.dll forwarders (SC3U.exe and AcGenral.dll both import version APIs), the env overrides for
 *     the test harness, and the -multi single-instance mutex rename (env-gated, a single DWORD write to .data).
 *
 * LOAD DECISION (DllMain):
 *   SC3MODS_OFF=1                 -> load nothing (quick stock, no rename).
 *   SC3MODS_DIR set (launcher/.bat/test): dir = it, list = SC3MODS_LIST or the built-in default. Loads for any host.
 *   SC3MODS_DIR unset (normal start):     load the built-in default list from this DLL's own folder, but ONLY when
 *                                         the host exe is SC3U.exe (so Baapp.exe, which also pulls version.dll in via
 *                                         the AppCompat shim DLLs, stays a pure forwarder).
 *   SC3MODS_MULTI=1               -> rename the single-instance mutex per pid (parallel test instances).
 * Log: <dir>\sc3modldr.log, appended, "[pid N t=tick]" prefix. A mod that fails to load is logged and skipped.
 */
#include <windows.h>
#include <stdio.h>
#include <string.h>

/* this SC3U.exe build (anchor 49DD55E1...), image-relative - only used by the -multi mutex rename */
#define SLOT_RVA    0x000f4b10             /* pointer to the mutex name, FUN_0040496d reads it */
#define NAME_RVA    0x000f4b24             /* "SimCity 3000 Mutex" */

/* The shipped mods, load order (sc3resize first: it registers the GZGraphicD loader notification the others rely on). */
static const char k_default_list[] =
    "sc3resize.dll;sc3bigcity.dll;sc3overscroll.dll;sc3simrun.dll;sc3perf.dll;sc3netmod.dll;sc3undo.dll";

/* =====================================================================================================
 * Forwarders: the 17 exports of the system version.dll.
 * ===================================================================================================== */
static const char *const k_names[17] = {
    "GetFileVersionInfoA", "GetFileVersionInfoByHandle", "GetFileVersionInfoExA", "GetFileVersionInfoExW",
    "GetFileVersionInfoSizeA", "GetFileVersionInfoSizeExA", "GetFileVersionInfoSizeExW", "GetFileVersionInfoSizeW",
    "GetFileVersionInfoW", "VerFindFileA", "VerFindFileW", "VerInstallFileA", "VerInstallFileW",
    "VerLanguageNameA", "VerLanguageNameW", "VerQueryValueA", "VerQueryValueW"
};
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
    if (!f) { SetLastError(ERROR_PROC_NOT_FOUND); f = fail_stub(k_argbytes[i]); }
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

/* Marker so a file search can tell this from the system version.dll. */
const char sc3modldr_id[] = "sc3modldr 2 (2026-10-25, no-patch dllmain-load)";

/* =====================================================================================================
 * Mod loading.
 * ===================================================================================================== */
static char g_dir[MAX_PATH];
static char g_list[1024];
static char g_log[MAX_PATH];
static char g_mutex_name[64];

static void logf(const char *fmt, ...) {
    char line[1024];
    int n;
    va_list ap;
    HANDLE h;
    DWORD w;
    if (!g_log[0]) return;
    n = _snprintf(line, sizeof(line) - 2, "[pid %lu t=%lu] ", GetCurrentProcessId(), GetTickCount());
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

/* host exe base name == "sc3u.exe" ? */
static int host_is_sc3u(void) {
    char exe[MAX_PATH], *b;
    if (!GetModuleFileNameA(NULL, exe, sizeof(exe))) return 0;
    b = strrchr(exe, '\\');
    b = b ? b + 1 : exe;
    return lstrcmpiA(b, "SC3U.exe") == 0;
}

/* -multi: rename the single-instance mutex per pid, so several instances run for tests. A single DWORD write to the
   game's .data (PAGE_READWRITE, restored), validated against the known slot/name pointer first. */
static void unique_mutex(void) {
    unsigned char *base = (unsigned char *)GetModuleHandleA(NULL);
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

/* Loaded straight from DllMain (loader lock held). No exe patch, no VirtualProtect on .text. */
static void load_mods(void) {
    char list[1024], path[MAX_PATH];
    char *p, *next;
    int n = 0;
    lstrcpynA(list, g_list, sizeof(list));
    logf("mod-load start from %s (GZGraphicD loaded now? %s)", g_dir,
         GetModuleHandleA("GZGraphicD.dll") ? "YES - too late for sc3resize EARLY" : "no");
    for (p = list; p && *p; p = next) {
        HMODULE m;
        next = strchr(p, ';');
        if (next) *next++ = 0;
        if (!*p) continue;
        _snprintf(path, sizeof(path), "%s\\%s", g_dir, p);
        m = LoadLibraryA(path);
        if (!m) { logf("[!] LoadLibrary %s failed, GetLastError=%lu", path, GetLastError()); continue; }
        logf("[+] loaded %s (HMODULE 0x%08lX)", p, (DWORD)m);
        n++;
    }
    logf("[+] %d mod(s) loaded (no exe patch, no VirtualProtect on .text)", n);
}

/* Fill g_dir / g_list from env or the built-in default. Returns 0 if nothing should load. */
static int decide(HINSTANCE self) {
    char v[8];
    int have_dir;
    if (GetEnvironmentVariableA("SC3MODS_OFF", v, sizeof(v)) && v[0] == '1') return 0;   /* explicit stock */

    have_dir = GetEnvironmentVariableA("SC3MODS_DIR", g_dir, sizeof(g_dir)) && g_dir[0];
    if (have_dir) {
        /* launcher / .bat / test harness path - trusted, loads for any host exe */
        if (!GetEnvironmentVariableA("SC3MODS_LIST", g_list, sizeof(g_list)) || !g_list[0])
            lstrcpynA(g_list, k_default_list, sizeof(g_list));
        SetEnvironmentVariableA("SC3MODS_DIR", NULL);   /* a child process must not reload */
        return 1;
    }
    /* normal start: only the game itself, mods from this DLL's own folder (Apps) */
    if (!host_is_sc3u()) return 0;
    {   char self_path[MAX_PATH], *b;
        if (!GetModuleFileNameA(self, self_path, sizeof(self_path))) return 0;
        b = strrchr(self_path, '\\'); if (!b) return 0; *b = 0;
        lstrcpynA(g_dir, self_path, sizeof(g_dir));
    }
    lstrcpynA(g_list, k_default_list, sizeof(g_list));
    return 1;
}

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID res) {
    char v[8];
    (void)res;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(inst);
        load_real();                  /* the system version.dll needs only kernelbase/ntdll, already initialised */
        if (decide(inst)) {
            _snprintf(g_log, sizeof(g_log), "%s\\sc3modldr.log", g_dir);
            if (GetEnvironmentVariableA("SC3MODS_MULTI", v, sizeof(v)) && v[0] == '1') unique_mutex();
            load_mods();
        }
    }
    return TRUE;
}
