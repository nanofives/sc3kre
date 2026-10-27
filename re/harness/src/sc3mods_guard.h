/* sc3mods_guard.h - a mod DLL does nothing unless the sc3kre mod loader is the one loading it (2026-10-27, lateguard).
 *
 * WHY. SC3U.exe maps every *.dll in its own folder as a GZCOM component: FUN_0040b00f lists "*.dll" (skipping the four
 * SafeDisc DLLs CLCD16/CLCD32/DPLAYERX/DRVMGT) and FUN_0048a575 does LoadLibraryA(path) then
 * GetProcAddress("GZDllGetGZCOMDirector"); a DLL without that export is FreeLibrary'd again by FUN_0048a675
 * [CONFIRMED @ 0x0040b00f, 0x0048a575, 0x0048a675]. With an unpatched exe (no sc3mods.dll import) that scan was the
 * only thing loading the mods: each one ran its full DllMain late (hooks, patches, threads) and was then unmapped
 * under its own hooks. The game died before any window, c0000005 @ SC3U+0x143a (MARIANO-PC 2026-10-27). With a
 * patched exe the scan only bumps the refcount of the already-loaded mods, so DllMain does not run a second time.
 *
 * RULE. A mod initialises only if
 *   - the loader's export sc3mods_loading() returns nonzero: sc3mods.dll (the exe import) or a rebuilt version.dll
 *     proxy (sc3modldr.c) set it on their own thread for the length of their LoadLibrary loop, or
 *   - SC3MODS_ANYLOAD=1 is in the environment: explicit opt-in for test paths that load a mod some other way
 *     (mods_launch.exe sets it for old version.dll binaries without the export, Frida Module.load, old injectors).
 * Otherwise DllMain returns TRUE having done nothing but write one line to <mod>.log beside the DLL.
 *
 * Only kernel32 calls already resolved by the loader: safe under the loader lock, no LoadLibrary. */
#ifndef SC3MODS_GUARD_H
#define SC3MODS_GUARD_H

#include <windows.h>
#include <stdio.h>
#include <string.h>

typedef int (__stdcall *PFN_sc3mods_loading)(void);

static int sc3mods_guard_loader_says(const char *module) {
    HMODULE m = GetModuleHandleA(module);
    PFN_sc3mods_loading f;
    if (!m) return 0;
    f = (PFN_sc3mods_loading)GetProcAddress(m, "sc3mods_loading");
    return f && f();
}

/* 1 = initialise the mod, 0 = stay inert (one line logged to <dir of self>\<name>.log). */
static int sc3mods_guard(HINSTANCE self, const char *name) {
    char v[8], path[MAX_PATH], line[512], *b;
    HANDLE h;
    DWORD w;
    int n;
    if (sc3mods_guard_loader_says("sc3mods.dll") || sc3mods_guard_loader_says("version.dll")) return 1;
    if (GetEnvironmentVariableA("SC3MODS_ANYLOAD", v, sizeof(v)) && v[0] == '1') return 1;
    if (!GetModuleFileNameA(self, path, sizeof(path))) return 0;
    b = strrchr(path, '\\');
    if (!b || (int)(b - path) + 1 + lstrlenA(name) + 5 >= (int)sizeof(path)) return 0;
    _snprintf(b + 1, sizeof(path) - (b + 1 - path), "%s.log", name);
    n = _snprintf(line, sizeof(line) - 1,
                  "[pid %lu] %s not loaded by sc3mods, inert (SC3U.exe is not patched or this DLL was loaded another "
                  "way). Run sc3mods_patch.ps1 in the game folder to use the mods.\r\n", GetCurrentProcessId(), name);
    if (n < 0) n = (int)sizeof(line) - 1;
    h = CreateFileA(path, GENERIC_WRITE, FILE_SHARE_READ, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h != INVALID_HANDLE_VALUE) { WriteFile(h, line, n, &w, NULL); CloseHandle(h); }
    return 0;
}

#endif
