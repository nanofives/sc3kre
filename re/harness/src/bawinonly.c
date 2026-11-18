/* bawinonly.c - task bldbat (2026-11-18): Building Architect (Baapp.exe) windowed, with no display-mode switch possible.
 *
 * Dev tool, never shipped. Loaded by an import that re/tools/bldbat/ba_patch.py adds to a COPY of Baapp.exe in a dev
 * tree (BaappW.exe). Does nothing in any other process (SC3U.exe maps every Apps DLL, FUN_0040b00f).
 *
 * Why it is safe (static, re/analysis/BLD_FORMAT.md section 5, verify/bldbat/RESULTS.md step 1):
 *   - In the Baapp process only GZGraphicD.dll imports DirectDrawCreate; no module imports or names
 *     ChangeDisplaySettings*. GZGraphicD holds ONE IDirectDraw::SetDisplayMode call (vt+0x54, in
 *     sc3_gfx_set_display_mode 0x10011f73) and ONE DDSCL_EXCLUSIVE|FULLSCREEN request (0x11 in FUN_1001250d, param 1).
 *   - Both run only through sc3_gfx_set_display_mode(1): from Init (0x100119a5) when the fullscreen flag this+0x48 is
 *     set, or through its vtable slot (cIGZSystemService 0x1001ee0c + 0x34 = 0x1001ee40).
 *   - this+0x48 is written by Init from the windowed byte (0x10011547, sete) and re-forced to 1 at 0x100117d6 when the
 *     desktop format or size differs from the request; elsewhere only by the constructor (0x10010e0c, before Init) and
 *     by set_display_mode itself (0x10012090).
 * Patches (all checked byte for byte first; any mismatch = TerminateProcess before GZGraphicD's DllMain runs):
 *   GZGraphicD+0x6cdac = 1                     the windowed byte Init reads (Baapp -w sets it too, FUN_00411637)
 *   GZGraphicD+0x117d6 c6 43 48 01 -> nop      the fullscreen re-force
 *   GZGraphicD+0x11f73 entry guard             set_display_mode(param != 0) returns at once (ret 4), counted
 *   GZGraphicD+0x1250d entry guard             cooperative level: param forced to 0 (DDSCL_NORMAL)
 *   GZGraphicD+0x19349 FIX16                   sc3resize's 16 bpp 5-6-5 surface format branch (windowed on 32 bpp)
 *   per-monitor v2 DPI awareness               as sc3resize / sc3winonly
 * STRTOKFIX (stability, stock Baapp bug): FUN_00419d88 (0x419e04, prop .met files) and FUN_0041a3b3 (0x41a429) read a
 *   whole file into operator new(filesize) with no terminating zero and run strtok over it (0x419e2b, 0x41a44e), so
 *   strtok reads past the block and writes '\0' at any delimiter there: heap corruption, crash at a later free
 *   (BaappW_stkdmp.txt: free <- 0x41889e / 0x419faa). Both calls (E8 -> thunk 0x479692 = jmp [0x4801f8] MSVCRT
 *   operator new) are pointed at bw_new_z(size): the same operator new for size+1, zero filled. BAWIN_STRTOK=0 skips.
 * A/B switches (environment): BAWIN_FIX16=0, BAWIN_DPI=0 skip those two parts (the mode-switch guards always apply).
 * Log: bawinonly.log beside the DLL. Export bawinonly_state() -> pointer to {u32 patched, u32 refused_fullscreen,
 * u32 coop_forced, u32 gz_base} for Frida checks. */
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <stdarg.h>

typedef struct { DWORD patched, refused_fullscreen, coop_forced, gz_base; } BW_STATE;
static BW_STATE g_state;
static volatile LONG g_done;
static PVOID g_cookie;
static char g_logpath[MAX_PATH];

__declspec(dllexport) BW_STATE *__cdecl bawinonly_state(void) { return &g_state; }

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

static void die(const char *why) {
    wlogf("[pid %lu] FAIL-CLOSED: %s. Terminating before any display init.", GetCurrentProcessId(), why);
    TerminateProcess(GetCurrentProcess(), 0xBA0F);
}

static BYTE *cave_alloc(void) {
    return (BYTE *)VirtualAlloc(NULL, 4096, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
}

static int env_off(const char *name) {
    char v[8];
    return GetEnvironmentVariableA(name, v, sizeof(v)) && v[0] == '0';
}

static int writable(BYTE *p, SIZE_T n) {
    DWORD old;
    return VirtualProtect(p, n, PAGE_EXECUTE_READWRITE, &old) != 0;
}

static void put_jmp(BYTE *at, BYTE *to) {
    DWORD rel = (DWORD)to - (DWORD)(at + 5);
    at[0] = 0xE9;
    memcpy(at + 1, &rel, 4);
}

/* sc3resize patch_surfacefmt (FIX16), same bytes as sc3winonly.c */
static int build_fix16(BYTE *gz, BYTE *cave) {
    BYTE *site = gz + 0x19349;
    static const BYTE orig[10] = { 0xF6,0xDB, 0x1B,0xDB, 0x81,0xE3,0xC0,0x0F,0x00,0x00 };
    int n = 0, jne_fixup, block_start;
    if (memcmp(site, orig, sizeof(orig)) != 0) return 0;
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
    put_jmp(cave + n, gz + 0x19353); n += 5;
    return n;
}

typedef void *(__cdecl *BW_NEW)(size_t);
static BW_NEW g_opnew;

static void *__cdecl bw_new_z(size_t n) {
    BYTE *p = (BYTE *)g_opnew(n + 1);
    if (p) memset(p, 0, n + 1);
    return p;
}

/* stock Baapp.exe: two 'call 0x479692' (operator new) feeding strtok; exe has no relocations (base 0x400000) */
static void patch_strtok(void) {
    static const DWORD sites[2] = { 0x419e04, 0x41a429 };
    int i, done = 0;
    BYTE *thunk = (BYTE *)0x479692;
    HMODULE crt = GetModuleHandleA("MSVCRT.dll");
    if (env_off("BAWIN_STRTOK")) { wlog("STRTOKFIX off (BAWIN_STRTOK=0)\r\n"); return; }
    if (GetModuleHandleA(NULL) != (HMODULE)0x400000 || !crt) { wlog("STRTOKFIX: unexpected base or no MSVCRT, NOT applied\r\n"); return; }
    g_opnew = (BW_NEW)GetProcAddress(crt, "??2@YAPAXI@Z");
    if (!g_opnew || thunk[0] != 0xFF || thunk[1] != 0x25 || *(DWORD *)(thunk + 2) != 0x4801f8) {
        wlog("STRTOKFIX: operator new thunk differs, NOT applied\r\n"); return;
    }
    for (i = 0; i < 2; i++) {
        BYTE *c = (BYTE *)sites[i];
        DWORD rel, old;
        memcpy(&rel, c + 1, 4);
        if (c[0] != 0xE8 || (DWORD)(c + 5) + rel != 0x479692) { wlogf("STRTOKFIX: 0x%08lX differs, skipped", sites[i]); continue; }
        if (!VirtualProtect(c, 5, PAGE_EXECUTE_READWRITE, &old)) continue;
        rel = (DWORD)bw_new_z - (DWORD)(c + 5);
        memcpy(c + 1, &rel, 4);
        FlushInstructionCache(GetCurrentProcess(), c, 5);
        done++;
    }
    wlogf("STRTOKFIX: %d of 2 file buffers get a terminating zero (0x419e04, 0x41a429)", done);
}

typedef struct { USHORT Length, MaximumLength; PWSTR Buffer; } BW_USTR;
typedef struct { ULONG Flags; const BW_USTR *FullDllName, *BaseDllName; PVOID DllBase; ULONG SizeOfImage; } BW_LDR_DATA;
typedef VOID (CALLBACK *BW_LDR_FN)(ULONG, const BW_LDR_DATA *, PVOID);
typedef LONG (NTAPI *BW_LDR_REG)(ULONG, BW_LDR_FN, PVOID, PVOID *);

static void patch(BYTE *gz) {
    static const BYTE nop4[4] = { 0xC6, 0x43, 0x48, 0x01 };
    BYTE *flag = gz + 0x6cdac, *force = gz + 0x117d6, *sdm = gz + 0x11f73, *coop = gz + 0x1250d;
    DWORD delta = (DWORD)gz - 0x10000000, imm_sdm, imm_coop;
    BYTE *cave;
    int n = 0, nf;
    g_state.gz_base = (DWORD)gz;
    /* entry bytes: mov eax, <EH handler> ; call EH_prolog. The imm32 carries a base relocation (+1), so a relocated
       image must already hold the relocated value, else the loader would later add the delta into our jmp. */
    memcpy(&imm_sdm, sdm + 1, 4);
    memcpy(&imm_coop, coop + 1, 4);
    if (sdm[0] != 0xB8 || sdm[5] != 0xE8 || imm_sdm != 0x1001d034 + delta) die("set_display_mode entry bytes differ");
    if (coop[0] != 0xB8 || coop[5] != 0xE8 || imm_coop != 0x1001d0f8 + delta) die("coop level entry bytes differ");
    if (memcmp(force, nop4, 4) != 0) die("0x117d6 is not c6 43 48 01");
    if (flag[0] > 1) die("windowed byte is neither 0 nor 1");
    cave = cave_alloc();
    if (!cave) die("VirtualAlloc for the code caves failed");
    if (!writable(flag, 1) || !writable(force, 4) || !writable(sdm, 5) || !writable(coop, 5) || !writable(gz + 0x19349, 10))
        die("VirtualProtect failed");

    /* cave A: set_display_mode guard */
    {
        BYTE *a = cave + n;
        DWORD p = (DWORD)&g_state.refused_fullscreen;
        a[0]=0x80; a[1]=0x7C; a[2]=0x24; a[3]=0x04; a[4]=0x00;      /* cmp byte [esp+4],0 */
        a[5]=0x74; a[6]=0x09;                                       /* je  original       */
        a[7]=0xFF; a[8]=0x05; memcpy(a + 9, &p, 4);                 /* inc dword [refused] */
        a[13]=0xC2; a[14]=0x04; a[15]=0x00;                         /* ret 4              */
        a[16]=0xB8; memcpy(a + 17, &imm_sdm, 4);                    /* mov eax, handler   */
        put_jmp(a + 21, sdm + 5);                                   /* jmp call EH_prolog */
        n += 26;
    }
    /* cave B (at +32): cooperative level always DDSCL_NORMAL */
    n = 32;
    {
        BYTE *b = cave + n;
        DWORD p = (DWORD)&g_state.coop_forced;
        b[0]=0x80; b[1]=0x7C; b[2]=0x24; b[3]=0x04; b[4]=0x00;      /* cmp byte [esp+4],0 */
        b[5]=0x74; b[6]=0x0B;                                       /* je  original       */
        b[7]=0xFF; b[8]=0x05; memcpy(b + 9, &p, 4);                 /* inc dword [forced] */
        b[13]=0xC6; b[14]=0x44; b[15]=0x24; b[16]=0x04; b[17]=0x00; /* mov byte [esp+4],0 */
        b[18]=0xB8; memcpy(b + 19, &imm_coop, 4);                   /* mov eax, handler   */
        put_jmp(b + 23, coop + 5);
        n += 28;
    }
    n = (n + 15) & ~15;
    nf = build_fix16(gz, cave + n);
    if (!nf) die("FIX16 pattern at 0x19349 differs");
    if (env_off("BAWIN_FIX16")) nf = 0;          /* A/B switch: BAWIN_FIX16=0 leaves the surface format alone */
    FlushInstructionCache(GetCurrentProcess(), cave, 4096);

    flag[0] = 1;
    force[0] = force[1] = force[2] = force[3] = 0x90;
    put_jmp(sdm, cave);
    put_jmp(coop, cave + 32);
    if (nf) {
        BYTE *site = gz + 0x19349;
        put_jmp(site, cave + n);
        site[5] = site[6] = site[7] = site[8] = site[9] = 0x90;
    }
    FlushInstructionCache(GetCurrentProcess(), gz, 0x20000);
    g_state.patched = 1;
    wlogf("[pid %lu] GZGraphicD at 0x%08lX: windowed byte 1, 0x117d6 nop, set_display_mode guard, coop guard, FIX16 "
          "(caves at 0x%08lX)%s. All patterns matched.", GetCurrentProcessId(), (DWORD)gz, (DWORD)cave,
          nf ? "" : " [FIX16 OFF by BAWIN_FIX16=0]");
}

static VOID CALLBACK notify(ULONG reason, const BW_LDR_DATA *d, PVOID ctx) {
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
}

static int is_baapp(void) {
    char exe[MAX_PATH], *b;
    if (!GetModuleFileNameA(NULL, exe, sizeof(exe))) return 0;
    b = strrchr(exe, '\\');
    b = b ? b + 1 : exe;
    return _strnicmp(b, "baapp", 5) == 0;
}

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID res) {
    (void)res;
    if (reason == DLL_PROCESS_ATTACH) {
        char *b;
        BW_LDR_REG reg;
        DisableThreadLibraryCalls(inst);
        if (!is_baapp()) return TRUE;           /* SC3U's Apps scan maps it too: stay inert there */
        GetModuleFileNameA(inst, g_logpath, sizeof(g_logpath));
        b = strrchr(g_logpath, '\\');
        if (b) lstrcpyA(b + 1, "bawinonly.log");
        {
            typedef BOOL (WINAPI *SETCTX)(HANDLE);
            SETCTX sc = (SETCTX)GetProcAddress(GetModuleHandleA("user32.dll"), "SetProcessDpiAwarenessContext");
            if (env_off("BAWIN_DPI")) wlogf("[pid %lu] bawinonly in Baapp; dpi untouched (BAWIN_DPI=0)", GetCurrentProcessId());
            else wlogf("[pid %lu] bawinonly in Baapp; dpi per-monitor v2: %s", GetCurrentProcessId(),
                       sc && sc((HANDLE)(LONG_PTR)-4) ? "set" : "FAILED");
        }
        patch_strtok();
        if (GetModuleHandleA("GZGraphicD.dll")) die("GZGraphicD already loaded, cannot prove the patch precedes Init");
        reg = (BW_LDR_REG)GetProcAddress(GetModuleHandleA("ntdll.dll"), "LdrRegisterDllNotification");
        if (!reg || reg(0, notify, NULL, &g_cookie) < 0) die("LdrRegisterDllNotification failed");
        wlog("waiting for GZGraphicD.dll\r\n");
    }
    return TRUE;
}
