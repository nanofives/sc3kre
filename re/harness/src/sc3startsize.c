/* sc3startsize.c - EXPERIMENT (2026-10-07): make the game create its window, device and UI at a chosen size
 * from the start, instead of 800x600 and resizing afterwards.
 *
 * GZGraphicD keeps the requested display mode in a 7-dword block at +0x6cd90 (W, H, bpp, ...), defaults
 * 640x480x16 (FUN_1001586f). The game sets it wholesale through FUN_10010ed1(block) (stdcall, ret 4):
 * push esi / mov esi,[esp+8] / push edi / push 7 / pop ecx / mov edi,0x1006cd90 / rep movsd / pop edi /
 * pop esi / ret 4. The device rect, the Win32 window (FUN_10018228) and the SIMUI root (FUN_10018691 ->
 * vt+0xc8) all follow from it, and SIMUI FUN_100270e5 picks the HUD layout from the root width
 * (640 / 800 / >= 801 -> the 1024x768 group). This hooks FUN_10010ed1: copy the game's block, then put
 * our W and H in. Worker report: re/harness/simrun/opt2_result.txt.
 *
 * Env: SC3START_W, SC3START_H (default 1024x768), SC3START_LOG=<abs path>.
 */
#include <windows.h>
#include <stdio.h>
#include <string.h>

static HMODULE g_self;
static HANDLE g_log = INVALID_HANDLE_VALUE;
static DWORD g_w = 1024, g_h = 768, g_gz;

static void logf(const char *fmt, ...) {
    char buf[1024];
    DWORD wrote;
    int n;
    va_list ap;
    va_start(ap, fmt);
    n = _vsnprintf(buf, sizeof(buf) - 3, fmt, ap);
    va_end(ap);
    if (n < 0) n = (int)strlen(buf);
    buf[n++] = '\r'; buf[n++] = '\n';
    if (g_log != INVALID_HANDLE_VALUE) WriteFile(g_log, buf, n, &wrote, NULL);
}

static void __stdcall setmode_hook(DWORD *blk) {
    DWORD *dst = (DWORD *)(g_gz + 0x6cd90);
    int i;
    for (i = 0; i < 7; i++) dst[i] = blk[i];
    logf("SETMODE: game asked %lux%lux%lu [%lu %lu %lu %lu] -> using %lux%lu",
         blk[0], blk[1], blk[2], blk[3], blk[4], blk[5], blk[6], g_w, g_h);
    dst[0] = g_w;
    dst[1] = g_h;
}

static DWORD WINAPI watcher(LPVOID p) {
    static const BYTE expect[] = { 0x56, 0x8b, 0x74, 0x24, 0x08, 0x57, 0x6a, 0x07, 0x59, 0xbf };
    HMODULE gz = NULL;
    BYTE *t;
    DWORD old;
    int ms = 0;
    (void)p;
    while (!(gz = GetModuleHandleA("GZGraphicD.dll")) && ms++ < 300000) Sleep(1);
    if (!gz) { logf("GZGraphicD never loaded"); return 0; }
    g_gz = (DWORD)gz;
    t = (BYTE *)gz + 0x10ed1;
    if (memcmp(t, expect, sizeof(expect)) || *(DWORD *)(t + 10) != g_gz + 0x6cd90) {
        logf("FUN_10010ed1 differs from shipped - NOT hooked"); return 0;
    }
    /* already set before we got here? (would mean we are too late) */
    logf("mode block at hook time: %lux%lux%lu", ((DWORD *)(g_gz + 0x6cd90))[0], ((DWORD *)(g_gz + 0x6cd90))[1], ((DWORD *)(g_gz + 0x6cd90))[2]);
    if (!VirtualProtect(t, 5, PAGE_EXECUTE_READWRITE, &old)) return 0;
    t[0] = 0xE9; *(DWORD *)(t + 1) = (DWORD)setmode_hook - (DWORD)(t + 5);
    VirtualProtect(t, 5, old, &old);
    FlushInstructionCache(GetCurrentProcess(), t, 5);
    logf("READY: FUN_10010ed1 hooked, start size %lux%lu", g_w, g_h);
    return 0;
}

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID r) {
    (void)r;
    if (reason == DLL_PROCESS_ATTACH) {
        char v[MAX_PATH], path[MAX_PATH], *sl;
        g_self = inst;
        DisableThreadLibraryCalls(inst);
        if (GetEnvironmentVariableA("SC3START_W", v, sizeof(v))) g_w = (DWORD)atoi(v);
        if (GetEnvironmentVariableA("SC3START_H", v, sizeof(v))) g_h = (DWORD)atoi(v);
        if (!GetEnvironmentVariableA("SC3START_LOG", path, sizeof(path))) {
            GetModuleFileNameA(inst, path, sizeof(path));
            sl = strrchr(path, '\\'); if (sl) sl[1] = 0;
            lstrcatA(path, "sc3startsize.log");
        }
        g_log = CreateFileA(path, GENERIC_WRITE, FILE_SHARE_READ, NULL, CREATE_ALWAYS, 0, NULL);
        logf("sc3startsize loaded");
        CreateThread(NULL, 0, watcher, NULL, 0, NULL);
    }
    return TRUE;
}
