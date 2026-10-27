/* sc3mods.c -> sc3mods.dll : loads the sc3kre mods into SC3U.exe through an import of the game exe (2026-10-27, importldr).
 *
 * WHY. The previous loader was a version.dll beside SC3U.exe that forwarded the 17 system version.dll exports and
 * LoadLibrary'd the mods from DllMain (sc3modldr.c, 2026-10-25). Defender flagged it as Program:Win32/Contebrew.A!ml twice
 * (10-25 and 10-27) with an unchanged source: a DLL named like a system DLL, beside the exe, forwarding every export, is
 * the DLL-sideloading fingerprint, and a rebuild only changes the hash until the model catches up again.
 *
 * NOW. This DLL has its own name and no forwarders. SC3U.exe loads it because sc3mods_patch.ps1 (run by the player on
 * their own install) adds an import descriptor for sc3mods.dll to Apps\SC3U.exe: the Windows loader maps it as a static
 * import and runs this DllMain during process init, after the game's own static imports and before the CRT, WinMain and
 * the game's dynamic load of GZGraphicD, which is the moment sc3resize's EARLY loader notification and DPI call need.
 * Nothing in the exe's code is changed and nothing is patched at run time.
 *
 * LOAD DECISION (DllMain):
 *   SC3MODS_OFF=1                 -> load nothing (stock game, exe still patched).
 *   SC3MODS_DIR set (test harness): dir = it, list = SC3MODS_LIST or the built-in default.
 *   SC3MODS_DIR unset (normal start): the built-in default list from this DLL's own folder (Apps), host SC3U.exe only.
 *   SC3MODS_MULTI=1               -> rename the single-instance mutex per pid (parallel test instances).
 * Log: <dir>\sc3mods.log, appended, "[pid N t=tick]" prefix. A mod that fails to load is logged and skipped.
 */
#include <windows.h>
#include <stdio.h>
#include <string.h>

/* this SC3U.exe build (anchor 49DD55E1...), image-relative - only used by the -multi mutex rename */
#define SLOT_RVA    0x000f4b10             /* pointer to the mutex name, FUN_0040496d reads it */
#define NAME_RVA    0x000f4b24             /* "SimCity 3000 Mutex" */

/* The shipped mods, load order (sc3resize first: it registers the GZGraphicD loader notification the others rely on). */
static const char k_default_list[] =
    "sc3resize.dll;sc3bigcity.dll;sc3overscroll.dll;sc3simrun.dll;sc3perf.dll;sc3netmod.dll;sc3undo.dll;sc3autosave.dll";

/* Marker so the patcher and file searches can tell the DLL is ours. */
const char sc3mods_id[] = "sc3mods 1 (2026-10-27, exe import)";

/* The one function the patched exe imports. The game never calls it; the import is what makes the loader map this DLL. */
int __stdcall sc3mods_version(void) { return 1; }

/* Nonzero only on the thread inside load_mods' LoadLibrary loop. Each mod's DllMain asks this (sc3mods_guard.h) and
 * stays inert otherwise, so the game's own *.dll component scan cannot start a mod. */
static volatile DWORD g_loading_tid;
int __stdcall sc3mods_loading(void) { return g_loading_tid && g_loading_tid == GetCurrentThreadId(); }

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

/* Loaded straight from DllMain (loader lock held), on the thread that runs process init (the game's main thread). */
static void load_mods(LPVOID res) {
    char list[1024], path[MAX_PATH];
    char *p, *next;
    int n = 0;
    lstrcpynA(list, g_list, sizeof(list));
    logf("mod-load start from %s (%s, tid %lu, GZGraphicD loaded now? %s)", g_dir,
         res ? "static import, process init" : "dynamic load", GetCurrentThreadId(),
         GetModuleHandleA("GZGraphicD.dll") ? "YES - too late for sc3resize EARLY" : "no");
    /* An unpatched SC3U.exe still maps this DLL later (the game loads the DLLs in Apps after GZGraphicD). Loading the
     * mods from there hung the game with no window on MARIANO-PC 2026-10-27 (log stopped at "mod-load start"), so a
     * dynamic load loads nothing: the game runs stock until sc3mods_patch.ps1 is run. */
    if (!res) {
        logf("[!] SC3U.exe is not patched (sc3mods.dll was loaded late, not as an import): no mods loaded, the game runs "
             "stock. Run sc3mods_patch.ps1 in the game folder.");
        return;
    }
    g_loading_tid = GetCurrentThreadId();
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
    g_loading_tid = 0;
    logf("[+] %d mod(s) loaded", n);
}

/* Fill g_dir / g_list from env or the built-in default. Returns 0 if nothing should load. */
static int decide(HINSTANCE self) {
    char v[8];
    if (GetEnvironmentVariableA("SC3MODS_OFF", v, sizeof(v)) && v[0] == '1') return 0;   /* explicit stock */
    if (!host_is_sc3u()) return 0;

    if (GetEnvironmentVariableA("SC3MODS_DIR", g_dir, sizeof(g_dir)) && g_dir[0]) {
        /* test harness: mods from an instance folder */
        if (!GetEnvironmentVariableA("SC3MODS_LIST", g_list, sizeof(g_list)) || !g_list[0])
            lstrcpynA(g_list, k_default_list, sizeof(g_list));
        SetEnvironmentVariableA("SC3MODS_DIR", NULL);   /* a child process must not reload */
        return 1;
    }
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
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(inst);
        if (decide(inst)) {
            _snprintf(g_log, sizeof(g_log), "%s\\sc3mods.log", g_dir);
            if (GetEnvironmentVariableA("SC3MODS_MULTI", v, sizeof(v)) && v[0] == '1') unique_mutex();
            load_mods(res);
        }
    }
    return TRUE;
}
