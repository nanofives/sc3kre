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
 * TEXT: sc3mods_lang() / sc3mods_tr() give every mod the game's text language and the <dir>\sc3lang\<code>.txt tables
 *   (sc3mods_lang.c; SC3MODS_LANGTABLES=0 = each mod's old inline es/en text).
 * Log: <dir>\sc3mods.log, appended, "[pid N t=tick]" prefix. A mod that fails to load is logged and skipped.
 */
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <ctype.h>

/* this SC3U.exe build (anchor 49DD55E1...), image-relative - only used by the -multi mutex rename */
#define SLOT_RVA    0x000f4b10             /* pointer to the mutex name, FUN_0040496d reads it */
#define NAME_RVA    0x000f4b24             /* "SimCity 3000 Mutex" */

/* The shipped mods, load order (sc3resize first: it registers the GZGraphicD loader notification the others rely on). */
static const char k_default_list[] =
    "sc3resize.dll;sc3bigcity.dll;sc3overscroll.dll;sc3simrun.dll;sc3perf.dll;sc3netmod.dll;sc3undo.dll;sc3autosave.dll;sc3landfill.dll;sc3dataview.dll;sc3restore.dll";

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

#include "sc3mods_lang.c"   /* modlang 2026-11-02: sc3mods_lang / sc3mods_tr, the mods' language and string tables */

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

/* MODTOGGLE (owner 2026-11-03: "on the mods options add a feature to disable mod features"). The page that writes this
 * is sc3resize's "Activar mods" page (MODSPAGE). <dir>\sc3mods.ini, read once here before any mod loads:
 *   [mods]  <dll>=0    the DLL is not loaded (sc3resize.dll cannot be turned off: it hosts the page)
 *   [env]   NAME=val   set in the process environment before the mods load, unless NAME is already set (a test
 *                      harness or the user's own env wins). Every mod already reads its own NAME=0 off-switch.
 * SC3MODS_INI=0 ignores the file. */
static char g_ini[MAX_PATH];

static int ini_on(void) {
    char v[8];
    if (GetEnvironmentVariableA("SC3MODS_INI", v, sizeof(v)) && v[0] == '0') return 0;
    _snprintf(g_ini, sizeof(g_ini), "%s\\sc3mods.ini", g_dir);
    g_ini[sizeof(g_ini) - 1] = 0;
    return GetFileAttributesA(g_ini) != INVALID_FILE_ATTRIBUTES;
}

static void ini_env(void) {
    char sec[4096], cur[8], *k;
    DWORD n = GetPrivateProfileSectionA("env", sec, sizeof(sec), g_ini);
    int set = 0;
    for (k = sec; n && k < sec + n && *k; k += lstrlenA(k) + 1) {
        char *eq = strchr(k, '=');
        if (!eq || eq == k) continue;
        *eq = 0;
        if (GetEnvironmentVariableA(k, cur, sizeof(cur)) || GetLastError() != ERROR_ENVVAR_NOT_FOUND)
            logf("    [env] %s left as the environment has it", k);
        else if (SetEnvironmentVariableA(k, eq + 1)) { logf("    [env] %s=%s (sc3mods.ini)", k, eq + 1); set++; }
        *eq = '=';
    }
    if (set) logf("[+] sc3mods.ini: %d feature switch(es) set", set);
}

static int ini_mod_off(const char *dll) {
    return g_ini[0] && lstrcmpiA(dll, "sc3resize.dll") && GetPrivateProfileIntA("mods", dll, 1, g_ini) == 0;
}

/* Loaded straight from DllMain (loader lock held), on the thread that runs process init (the game's main thread). */
static void load_mods(LPVOID res) {
    char list[1024], path[MAX_PATH];
    char *p, *next;
    int n = 0, off = 0;
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
    if (ini_on()) ini_env(); else g_ini[0] = 0;
    g_loading_tid = GetCurrentThreadId();
    for (p = list; p && *p; p = next) {
        HMODULE m;
        next = strchr(p, ';');
        if (next) *next++ = 0;
        if (!*p) continue;
        if (ini_mod_off(p)) { logf("[-] %s turned off in sc3mods.ini [mods]: not loaded", p); off++; continue; }
        _snprintf(path, sizeof(path), "%s\\%s", g_dir, p);
        m = LoadLibraryA(path);
        if (!m) { logf("[!] LoadLibrary %s failed, GetLastError=%lu", path, GetLastError()); continue; }
        logf("[+] loaded %s (HMODULE 0x%08lX)", p, (DWORD)m);
        n++;
    }
    g_loading_tid = 0;
    logf("[+] %d mod(s) loaded%s", n, off ? ", some turned off in sc3mods.ini" : "");
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

/* ===== REWARD TYPES (child civmod 2026-11-19, owner call "Loader declares"; re/analysis/CIVIC_REWARD.md 5.2).
 * A building whose type id is not declared like a CitySim.ini [AgentTypes] row has no agent type object: placing it
 * faults the City Planner (SIMADV 0x1000b392) and a city holding one stops the game while it loads. bldimport's new
 * rewards have their own type ids, listed in <PlugIn root>\PlugIn\bldimport_rewards\bldimport_types.ini in the
 * CitySim.ini format ([AgentTypes] <type>=<name>:<text key>, [AgentTypeHierarchy] <type>=<parent>). The declaration lives
 * here, not in a mod, so it is made whenever the loader runs: every mod off on the mods page, sc3resize off, or
 * SC3MODS_OFF=1. cSC3App::LoadRegistry (SC3U 0x0040b761, app init, after this DllMain) reads CitySim.ini with
 * cSC3CompressibleINIFile::EnumEntries (0x00486f55) at 0x0040bc80 ([AgentTypes], callback RegisterAgentTypeCallback
 * 0x0040cb70) and 0x0040bccb ([AgentTypeHierarchy], RegisterAgentRelationCallback 0x0040cc08). The two calls' rel32 go to
 * at_types / at_hier, which run the stock EnumEntries and then hand our rows to the same callback as exe cRZString
 * (char* ctor 0x00402a40, dtor 0x00402a96). The registry categories they fill build the agent type tree (SIMINIT
 * 0x10002eb1). No file: nothing patched. sc3mods_reward_types() tells sc3resize which types were declared (it unlocks
 * only those). SC3MODS_DECLARE=0 (test only) skips it, to reproduce what the bare stock exe sees. */
#define AT_MAX 64
static DWORD g_at_type[AT_MAX];
static int   g_at_n;
static DWORD g_at_enum;
static char  g_at_path[MAX_PATH];

static DWORD at_call(void *self, DWORD fn, DWORD a0, DWORD a1, DWORD a2, int n) {   /* __thiscall with 0..3 args */
    DWORD rv;
    __asm {
        mov  eax, n
        cmp  eax, 3
        jl   at_l2
        push a2
    at_l2:
        cmp  eax, 2
        jl   at_l1
        push a1
    at_l1:
        cmp  eax, 1
        jl   at_l0
        push a0
    at_l0:
        mov  ecx, self
        call fn
        mov  rv, eax
    }
    return rv;
}

typedef void (__cdecl *AT_CB)(void *key, void *value, void *ctx);
static void at_feed(const char *sec, AT_CB cb, void *ctx) {
    DWORD exe = (DWORD)GetModuleHandleA(NULL);
    unsigned char ks[0x20], vs[0x20];
    char buf[8192], k[16], *e, *eq;
    int rel = !lstrcmpA(sec, "AgentTypeHierarchy"), i;
    if (!GetPrivateProfileSectionA(sec, buf, sizeof(buf), g_at_path)) return;
    for (e = buf; *e; e += lstrlenA(e) + 1) {
        DWORD t = strtoul(e, NULL, 0);
        eq = strchr(e, '=');
        if (*e == ';' || !eq || eq - e >= (int)sizeof(k)) continue;
        if (t < 38000 || t > 38999) { logf("[!] reward types: [%s] %s outside 38000..38999, not declared", sec, e); continue; }
        for (i = 0; i < g_at_n && g_at_type[i] != t; i++) ;
        if (rel ? i == g_at_n : (i < g_at_n || g_at_n >= AT_MAX)) continue;   /* parents only for declared types */
        memcpy(k, e, eq - e); k[eq - e] = 0;
        memset(ks, 0, sizeof(ks)); memset(vs, 0, sizeof(vs));
        at_call(ks, exe + 0x2a40, (DWORD)k, 0, 0, 1);          /* cRZString(char const *) */
        at_call(vs, exe + 0x2a40, (DWORD)(eq + 1), 0, 0, 1);
        cb(ks, vs, ctx);
        at_call(ks, exe + 0x2a96, 0, 0, 0, 0);                 /* ~cRZString */
        at_call(vs, exe + 0x2a96, 0, 0, 0, 0);
        if (!rel) g_at_type[g_at_n++] = t;
        logf("[+] reward types: declared [%s] %s", sec, e);
    }
}
static unsigned char __fastcall at_types(void *ini, void *edx, void *sec, AT_CB cb, void *ctx) {
    unsigned char r = (unsigned char)at_call(ini, g_at_enum, (DWORD)sec, (DWORD)cb, (DWORD)ctx, 3);
    (void)edx;
    at_feed("AgentTypes", cb, ctx);
    return r;
}
static unsigned char __fastcall at_hier(void *ini, void *edx, void *sec, AT_CB cb, void *ctx) {
    unsigned char r = (unsigned char)at_call(ini, g_at_enum, (DWORD)sec, (DWORD)cb, (DWORD)ctx, 3);
    (void)edx;
    at_feed("AgentTypeHierarchy", cb, ctx);
    return r;
}
/* the types declared (the game's registry has them before the agent type tree is built) */
int __stdcall sc3mods_reward_types(DWORD *out, int cap) {
    int i;
    for (i = 0; out && i < g_at_n && i < cap; i++) out[i] = g_at_type[i];
    return g_at_n;
}

/* <PlugIn root>\PlugIn\bldimport_rewards\bldimport_types.ini; root = Apps\SC3U.ini [Directories] PlugIn=, else Apps\
   (cGZFileSystem::PlugInDirectory, SC3U 0x00482532) */
static void at_install(void) {
    unsigned char *exe = (unsigned char *)GetModuleHandleA(NULL), *c1 = exe + 0xbc80, *c2 = exe + 0xbccb;
    char dir[MAX_PATH], ini[MAX_PATH], root[MAX_PATH], v[8], *b;
    DWORD old;
    if (GetEnvironmentVariableA("SC3MODS_DECLARE", v, sizeof(v)) && v[0] == '0') { logf("[-] reward types: SC3MODS_DECLARE=0, not declared (test)"); return; }
    if (!GetModuleFileNameA(NULL, dir, sizeof(dir)) || !(b = strrchr(dir, '\\'))) return;
    b[1] = 0;
    _snprintf(ini, sizeof(ini), "%sSC3U.ini", dir); ini[sizeof(ini) - 1] = 0;
    GetPrivateProfileStringA("Directories", "PlugIn", "", root, sizeof(root), ini);
    if (!root[0]) lstrcpynA(root, dir, sizeof(root));
    else if (root[lstrlenA(root) - 1] != '\\') lstrcatA(root, "\\");
    _snprintf(g_at_path, sizeof(g_at_path), "%sPlugIn\\bldimport_rewards\\bldimport_types.ini", root);
    g_at_path[sizeof(g_at_path) - 1] = 0;
    if (GetFileAttributesA(g_at_path) == INVALID_FILE_ATTRIBUTES) return;   /* no reward types: CitySim.ini alone */
    if (c1[-6] != 0x68 || *(DWORD *)(c1 - 5) != (DWORD)exe + 0xcb70 || c1[0] != 0xe8 ||
        c2[-6] != 0x68 || *(DWORD *)(c2 - 5) != (DWORD)exe + 0xcc08 || c2[0] != 0xe8 ||
        (DWORD)(c1 + 5 + *(LONG *)(c1 + 1)) != (DWORD)exe + 0x86f55 || (DWORD)(c2 + 5 + *(LONG *)(c2 + 1)) != (DWORD)exe + 0x86f55) {
        logf("[!] reward types: SC3U LoadRegistry differs from shipped, %s not declared", g_at_path); return; }
    if (!VirtualProtect(c1, 0x50, PAGE_EXECUTE_READWRITE, &old)) { logf("[!] reward types: VirtualProtect failed %lu", GetLastError()); return; }
    g_at_enum = (DWORD)exe + 0x86f55;
    *(LONG *)(c1 + 1) = (LONG)((DWORD)at_types - (DWORD)(c1 + 5));
    *(LONG *)(c2 + 1) = (LONG)((DWORD)at_hier - (DWORD)(c2 + 5));
    /* protection left writable on purpose: a restore can land mid-write in a mod patching the same page (task onramp) */
    FlushInstructionCache(GetCurrentProcess(), c1, 0x50);
    logf("[+] reward types of %s go after CitySim.ini's (SC3U 0x0040bc80 / 0x0040bccb)", g_at_path);
}

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID res) {
    char v[8];
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(inst);
        lang_init();
        if (decide(inst)) {
            _snprintf(g_log, sizeof(g_log), "%s\\sc3mods.log", g_dir);
            if (GetEnvironmentVariableA("SC3MODS_MULTI", v, sizeof(v)) && v[0] == '1') unique_mutex();
            load_mods(res);
        }
        /* REWARD TYPES: whenever the patched exe maps the loader as a static import, mods on or off. A late dynamic
           load (unpatched exe) loads no mods and that game runs stock: nothing declared there. */
        if (res && host_is_sc3u()) {
            if (!g_log[0]) {   /* SC3MODS_OFF=1: the log beside this DLL */
                char self[MAX_PATH], *s;
                if (GetModuleFileNameA(inst, self, sizeof(self)) && (s = strrchr(self, '\\'))) { *s = 0; _snprintf(g_log, sizeof(g_log), "%s\\sc3mods.log", self); }
            }
            at_install();
        }
    }
    return TRUE;
}
