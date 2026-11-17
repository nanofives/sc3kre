/* sc3winonly.c - TEST CONTROL ONLY (child rotleak, 2026-11-17): the stock game, windowed, nothing else.
 *
 * The stock exe runs exclusive fullscreen: with SC3MODS_OFF=1 (sc3dev run -Stock) it switched LIVING-PC's display to
 * 800x600 and later sat as a topmost 3840x2160 popup (style 0x94000000, ex 0x8), against the always-windowed rule.
 * This DLL makes the two GZGraphicD byte patches sc3resize's patch_windowed does, from a loader notification before
 * GZGraphicD's DllMain, and nothing more: no hooks, no threads, no other module touched.
 *   GZGraphicD+0x6cdac = 1               the windowed flag Init (FUN_100114b8) reads
 *   GZGraphicD+0x117d6 c6 43 48 01 -> nop the fullscreen re-force store
 * Also (same reason, so the control draws and takes posted 800x600 coordinates like the modded game): sc3resize's FIX16
 * surface-format patch and per-monitor v2 DPI awareness. Measured without them: wrong-colour garbage drawn, and the
 * 800x600 client shown as 2000x1500, so posted HUD clicks landed in the city.
 * Use: SC3MODS_DIR=<inst> SC3MODS_LIST=sc3winonly.dll. Log: sc3winonly.log beside the DLL. Never shipped. */
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
#include "sc3mods_guard.h"

static HMODULE g_self;
static volatile LONG g_done;
static PVOID g_cookie;
static char g_logpath[MAX_PATH];

static void wlog(const char *s) {
    HANDLE h = CreateFileA(g_logpath, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_ALWAYS,
                           FILE_ATTRIBUTE_NORMAL, NULL);
    DWORD w;
    if (h == INVALID_HANDLE_VALUE) return;
    WriteFile(h, s, (DWORD)strlen(s), &w, NULL);
    CloseHandle(h);
}

static void wlogf(const char *fmt, ...) {
    char line[512];
    va_list ap;
    va_start(ap, fmt);
    _vsnprintf(line, sizeof(line) - 3, fmt, ap);
    va_end(ap);
    line[sizeof(line) - 3] = 0;
    lstrcatA(line, "\r\n");
    wlog(line);
}

/* copied verbatim from sc3resize.c patch_surfacefmt (FIX16): the 16 bpp 5-6-5 branch at GZGraphicD+0x19349, without it
   a windowed stock game draws in the wrong pixel format */
static void patch_surfacefmt(HMODULE gz) {
    BYTE *site = (BYTE *)gz + 0x19349;
    static const BYTE orig[10] = { 0xF6,0xDB, 0x1B,0xDB, 0x81,0xE3,0xC0,0x0F,0x00,0x00 };
    BYTE *cave;
    DWORD old;
    int n = 0, jne_fixup, block_start;
    if (memcmp(site, orig, sizeof(orig)) != 0) {
        wlogf("--- FIX16: 0x19349 pattern mismatch (%02X %02X %02X %02X), NOT patched",
             site[0], site[1], site[2], site[3]);
        return;
    }
    cave = (BYTE *)VirtualAlloc(NULL, 256, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!cave) { wlogf("--- FIX16: VirtualAlloc failed (%lu)", GetLastError()); return; }
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
        wlogf("--- FIX16: VirtualProtect failed (%lu)", GetLastError()); return;
    }
    site[0] = 0xE9;
    { DWORD rel = (DWORD)cave - (DWORD)(site + 5); memcpy(site + 1, &rel, 4); }
    site[5]=site[6]=site[7]=site[8]=site[9]=0x90;
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    FlushInstructionCache(GetCurrentProcess(), site, 10);
    wlogf("--- FIX16: 16bpp branch injected at 0x19349 -> cave 0x%08lX (5-6-5)", (DWORD)cave);
}

typedef struct { USHORT Length, MaximumLength; PWSTR Buffer; } WO_USTR;
typedef struct { ULONG Flags; const WO_USTR *FullDllName, *BaseDllName; PVOID DllBase; ULONG SizeOfImage; } WO_LDR_DATA;
typedef VOID (CALLBACK *WO_LDR_FN)(ULONG, const WO_LDR_DATA *, PVOID);
typedef LONG (NTAPI *WO_LDR_REG)(ULONG, WO_LDR_FN, PVOID, PVOID *);

static void patch(BYTE *gz) {
    char line[256];
    BYTE *p = gz + 0x6cdac, *q = gz + 0x117d6, before;
    DWORD old;
    if (!VirtualProtect(p, 1, PAGE_EXECUTE_READWRITE, &old)) { wlog("windowed byte: VirtualProtect failed\r\n"); return; }
    before = *p; *p = 1;
    if (q[0] == 0xC6 && q[1] == 0x43 && q[2] == 0x48 && q[3] == 0x01 && VirtualProtect(q, 4, PAGE_EXECUTE_READWRITE, &old)) {
        q[0] = q[1] = q[2] = q[3] = 0x90;
        FlushInstructionCache(GetCurrentProcess(), q, 4);
    }
    _snprintf(line, sizeof(line) - 1, "[pid %lu] GZGraphicD at 0x%08lX: +0x6cdac %u -> 1, +0x117d6 now %02x %02x %02x %02x\r\n",
              GetCurrentProcessId(), (DWORD)gz, before, q[0], q[1], q[2], q[3]);
    line[sizeof(line) - 1] = 0;
    wlog(line);
}

static VOID CALLBACK notify(ULONG reason, const WO_LDR_DATA *d, PVOID ctx) {
    static const WCHAR want[] = L"gzgraphicd.dll";
    int i, n;
    (void)ctx;
    if (reason != 1 || !d || !d->BaseDllName || !d->BaseDllName->Buffer || g_done) return;
    n = d->BaseDllName->Length / 2;
    if (n != (int)(sizeof(want) / 2 - 1)) return;
    for (i = 0; i < n; i++) {
        WCHAR c = d->BaseDllName->Buffer[i];
        if (c >= L'A' && c <= L'Z') c = (WCHAR)(c + 32);
        if (c != want[i]) return;
    }
    if (InterlockedExchange(&g_done, 1)) return;
    patch((BYTE *)d->DllBase);
    patch_surfacefmt((HMODULE)d->DllBase);
}

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID res) {
    (void)res;
    if (reason == DLL_PROCESS_ATTACH) {
        char *b;
        WO_LDR_REG reg;
        HMODULE gz;
        g_self = inst;
        DisableThreadLibraryCalls(inst);
        if (!sc3mods_guard(inst, "sc3winonly")) return TRUE;
        GetModuleFileNameA(inst, g_logpath, sizeof(g_logpath));
        b = strrchr(g_logpath, '\\');
        if (b) lstrcpyA(b + 1, "sc3winonly.log");
        {   /* sc3resize rz_dpi_aware: sharp at real pixel size, so posted 800x600 coordinates hit the HUD */
            typedef BOOL (WINAPI *SETCTX)(HANDLE);
            SETCTX sc = (SETCTX)GetProcAddress(GetModuleHandleA("user32.dll"), "SetProcessDpiAwarenessContext");
            wlogf("[pid %lu] dpi per-monitor v2: %s", GetCurrentProcessId(), sc && sc((HANDLE)(LONG_PTR)-4) ? "set" : "FAILED");
        }
        gz = GetModuleHandleA("GZGraphicD.dll");
        if (gz) { wlog("GZGraphicD already loaded: patching late\r\n"); patch((BYTE *)gz); return TRUE; }
        reg = (WO_LDR_REG)GetProcAddress(GetModuleHandleA("ntdll.dll"), "LdrRegisterDllNotification");
        if (!reg || reg(0, notify, NULL, &g_cookie) < 0) wlog("LdrRegisterDllNotification failed\r\n");
    }
    return TRUE;
}
