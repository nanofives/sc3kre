/* mods_launch.exe - one launcher for all the sc3kre game mods.
 *
 * No injection (2026-10-21). Windows Defender blocked the old launcher (start suspended + VirtualAllocEx +
 * WriteProcessMemory + CreateRemoteThread(LoadLibraryA)) as "Behavior:Win32/DefenseEvasion.A!ml". Now the mods are
 * loaded from INSIDE the game by version.dll (sc3modldr.c), which sits beside SC3U.exe in Apps and which the Windows
 * loader maps because SC3U.exe imports VERSION.dll. This launcher only starts SC3U.exe normally (cwd = the game's
 * Apps dir) with the mod list in its environment, waits for the loader's "mods loaded" event and prints the loader's
 * log lines. It never opens the game process for writing. Each mod still finds its own ini and log beside itself.
 *
 *   mods_launch.exe [-delay <ms>] [-kill <seconds>] [-multi] [-exe <name>] [-nolease] [-- <args passed to the game>]
 *   -multi: per-instance mutex name, so several games can run at once (the loader renames it, see sc3modldr.c).
 *   -nolease: skip the dev-PC game-lease gate (see lease_gate; exit 7 = refused).
 *   -delay: the loader loads the mods from a thread <ms> after the game started (test option).
 *
 * Exit codes: 2 = no SC3U.exe / no mod, 3 = CreateProcess failed, 4 = a mod failed to load (the loader ended the
 * game), 6 = version.dll (the loader) missing or not ours beside SC3U.exe, 7 = lease refused.
 *
 * Mods are independent: each one checks the game bytes it patches and refuses (logging why) rather than
 * half-patching, so a collision shows up in that mod's log, not as a crash.
 */

#include <windows.h>
#include <stdio.h>
#include <string.h>

#define SC3MODS_EXIT_LOADFAIL 0x5C30004u   /* sc3modldr.c ends the game with this when a mod does not load */

#include "lease_gate.h"

/* Copy `dir` = everything up to (not including) the last backslash of `full`. */
static void dirname_of(const char *full, char *dir, int cb) {
    const char *slash = NULL, *p;
    int n;
    for (p = full; *p; p++) if (*p == '\\') slash = p;
    n = slash ? (int)(slash - full) : 0;
    if (n >= cb) n = cb - 1;
    lstrcpynA(dir, full, n + 1);
    dir[n] = 0;
}

/* 1 if `path` exists and contains the marker string sc3modldr.c carries (the system version.dll does not). */
static int is_our_loader(const char *path) {
    HANDLE f = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    static char buf[256 * 1024];
    DWORD got = 0, i;
    const char *mark = "sc3modldr ";
    int ml = lstrlenA(mark), found = 0;
    if (f == INVALID_HANDLE_VALUE) return 0;
    ReadFile(f, buf, sizeof(buf), &got, NULL);
    CloseHandle(f);
    for (i = 0; i + ml <= got && !found; i++) if (!memcmp(buf + i, mark, ml)) found = 1;
    return found;
}

/* Print the loader log lines that belong to `pid` (sc3modldr.log in the mod folder, "[pid N] " prefix). */
static void print_loader_log(const char *dir, DWORD pid) {
    char path[MAX_PATH], tag[32], *buf, *p, *e;
    HANDLE f;
    DWORD size, got = 0;
    int tl;
    _snprintf(path, sizeof(path), "%s\\sc3modldr.log", dir);
    _snprintf(tag, sizeof(tag), "[pid %lu] ", pid);
    tl = lstrlenA(tag);
    f = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, 0, NULL);
    if (f == INVALID_HANDLE_VALUE) { printf("[!] no loader log at %s\n", path); return; }
    size = GetFileSize(f, NULL);
    if (size > 4u << 20) { SetFilePointer(f, (LONG)(size - (4u << 20)), NULL, FILE_BEGIN); size = 4u << 20; }
    buf = (char *)HeapAlloc(GetProcessHeap(), 0, size + 1);
    if (!buf) { CloseHandle(f); return; }
    ReadFile(f, buf, size, &got, NULL);
    CloseHandle(f);
    buf[got] = 0;
    for (p = buf; *p; p = e) {
        e = strchr(p, '\n');
        if (e) *e++ = 0; else e = p + lstrlenA(p);
        if (!strncmp(p, tag, tl)) {
            char *cr = strchr(p, '\r');
            if (cr) *cr = 0;
            printf("    loader: %s\n", p + tl);
        }
    }
    HeapFree(GetProcessHeap(), 0, buf);
}

int main(int argc, char **argv) {
    const char *exename = "SC3U.exe";
    char self[MAX_PATH], owndir[MAX_PATH], root[MAX_PATH], appsdir[MAX_PATH];
    char exe[MAX_PATH], workdir[MAX_PATH], dll[MAX_PATH], loader[MAX_PATH];
    static const char *mods[] = { "sc3resize.dll", "sc3bigcity.dll", "sc3overscroll.dll", "sc3simrun.dll", "sc3startsize.dll", "sc3perf.dll", "sc3netmod.dll", "sc3cartrips.dll", "sc3undo.dll", "sc3autosave.dll" };
    int nmods = 0, m;
    char cmdline[2048];
    char gameargs[1024];
    char list[1024], evname[64], num[16];
    STARTUPINFOA si;
    PROCESS_INFORMATION pi;
    HANDLE ev;
    int delayms = 0;
    int killsec = 0;
    int multi = 0;
    int nolease = 0;
    int i;
    char *p;

    /* Unbuffered: piped to a script, a buffered stdout held the "pid = N" line until the game exited (2026-10-11). */
    setvbuf(stdout, NULL, _IONBF, 0);
    gameargs[0] = 0;
    list[0] = 0;

    /* Where we are: the mod DLLs sit beside us. */
    GetModuleFileNameA(NULL, self, sizeof(self));
    dirname_of(self, owndir, sizeof(owndir));

    for (i = 1; i < argc; i++) {
        if (!lstrcmpiA(argv[i], "-delay") && i + 1 < argc) {
            delayms = atoi(argv[++i]);
        } else if (!lstrcmpiA(argv[i], "-exe") && i + 1 < argc) {
            exename = argv[++i];   /* test option: launch a renamed copy (compat layers are keyed by path) */
        } else if (!lstrcmpiA(argv[i], "-multi")) {
            multi = 1;
        } else if (!lstrcmpiA(argv[i], "-nolease")) {
            nolease = 1;
        } else if (!lstrcmpiA(argv[i], "-kill") && i + 1 < argc) {
            killsec = atoi(argv[++i]);
        } else if (!lstrcmpA(argv[i], "--")) {
            /* Re-quote any passthrough arg containing a space (sc3launch.c learned this the hard
               way: an unquoted "Cities\Berlin, Germany.sc3" loaded on one run and errored on the
               next). */
            for (i++; i < argc; i++) {
                const char *a = argv[i];
                int needq = 0, k;
                for (k = 0; a[k]; k++) { if (a[k] == ' ' || a[k] == '\t') { needq = 1; break; } }
                if (a[0] == '"') needq = 0;
                if (gameargs[0]) lstrcatA(gameargs, " ");
                if (needq) { lstrcatA(gameargs, "\""); lstrcatA(gameargs, a); lstrcatA(gameargs, "\""); }
                else       { lstrcatA(gameargs, a); }
            }
            break;
        }
    }

    /* SC3U.exe: ship layout is next to us (launcher in Apps); dev layout is <root>\Apps\SC3U.exe reached by
       walking up 4 levels from re\harness\<bin or inst_x>\mods_launch.exe. */
    _snprintf(exe, sizeof(exe), "%s\\%s", owndir, exename);
    if (GetFileAttributesA(exe) != INVALID_FILE_ATTRIBUTES) {
        lstrcpynA(workdir, owndir, sizeof(workdir));
    } else {
        lstrcpynA(root, self, sizeof(root));
        for (i = 0; i < 4; i++) { p = strrchr(root, '\\'); if (p) *p = 0; }
        _snprintf(exe, sizeof(exe), "%s\\Apps\\%s", root, exename);
        _snprintf(workdir, sizeof(workdir), "%s\\Apps", root);
    }

    if (GetFileAttributesA(exe) == INVALID_FILE_ATTRIBUTES) {
        printf("[!] SC3U.exe not found next to the loader or at <root>\\Apps\\SC3U.exe\n");
        printf("    looked last at: %s\n", exe);
        return 2;
    }
    if (!nolease) {
        char gameroot[MAX_PATH];
        dirname_of(workdir, gameroot, sizeof(gameroot));                 /* <root>\Apps -> <root> */
        if (!lease_gate(gameroot)) return 7;
    }
    for (m = 0; m < (int)(sizeof(mods) / sizeof(mods[0])); m++) {
        _snprintf(dll, sizeof(dll), "%s\\%s", owndir, mods[m]);
        if (GetFileAttributesA(dll) != INVALID_FILE_ATTRIBUTES) {
            printf("[*] mod : %s\n", mods[m]);
            if (list[0]) lstrcatA(list, ";");
            lstrcatA(list, mods[m]);
            nmods++;
        }
    }
    if (!nmods) {
        printf("[!] no mod DLL beside the launcher (sc3resize.dll, sc3bigcity.dll, ...)\n");
        return 2;
    }

    /* The loader must be beside the exe that runs (the Windows loader looks for VERSION.dll there first). */
    dirname_of(exe, appsdir, sizeof(appsdir));
    _snprintf(loader, sizeof(loader), "%s\\version.dll", appsdir);
    if (!is_our_loader(loader)) {
        printf("[!] %s is %s.\n", loader, GetFileAttributesA(loader) == INVALID_FILE_ATTRIBUTES ? "missing" : "not the sc3kre mod loader");
        printf("    The mods load through it (no injection since 2026-10-21). Put the version.dll built from\n");
        printf("    re/harness/src/sc3modldr.c there (build_mod.ps1 -Mod sc3modldr -Out <that folder>).\n");
        return 6;
    }

    /* Hand the work to the loader through the environment (inherited by the game only). */
    _snprintf(evname, sizeof(evname), "Local\\sc3mods_ready_%lu", GetCurrentProcessId());
    ev = CreateEventA(NULL, TRUE, FALSE, evname);
    SetEnvironmentVariableA("SC3MODS_DIR", owndir);
    SetEnvironmentVariableA("SC3MODS_LIST", list);
    SetEnvironmentVariableA("SC3MODS_EVENT", evname);
    SetEnvironmentVariableA("SC3MODS_MULTI", multi ? "1" : NULL);
    /* The mods start only when their loader says so (sc3mods_guard.h, 2026-10-27). A version.dll built before that has
       no sc3mods_loading export, so this launcher opts the whole game process in. */
    SetEnvironmentVariableA("SC3MODS_ANYLOAD", "1");
    _snprintf(num, sizeof(num), "%d", delayms);
    SetEnvironmentVariableA("SC3MODS_DELAY", delayms > 0 ? num : NULL);

    _snprintf(cmdline, sizeof(cmdline), "\"%s\" %s", exe, gameargs);
    printf("[*] exe : %s\n", exe);
    printf("[*] mods: %s (loaded by %s)\n", owndir, loader);
    printf("[*] args: %s\n", gameargs[0] ? gameargs : "(none)");

    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(si);
    ZeroMemory(&pi, sizeof(pi));

    if (!CreateProcessA(NULL, cmdline, NULL, NULL, FALSE, 0, NULL, workdir, &si, &pi)) {
        printf("[!] CreateProcess failed: %lu\n", GetLastError());
        return 3;
    }
    printf("[+] created, pid = %lu\n", pi.dwProcessId);

    /* Wait for the loader's event (mods loaded or refused) or the game's end, whichever first. */
    {
        HANDLE w[2];
        DWORD r;
        w[0] = ev; w[1] = pi.hProcess;
        r = WaitForMultipleObjects(ev ? 2 : 1, ev ? w : &pi.hProcess, FALSE, 30000 + (delayms > 0 ? delayms : 0));
        if (ev && r == WAIT_OBJECT_0) printf("[+] loader done\n");
        else if (r == WAIT_TIMEOUT) printf("[!] loader did not report in 30 s\n");
        print_loader_log(owndir, pi.dwProcessId);
    }

    if (killsec > 0) {
        DWORD w = WaitForSingleObject(pi.hProcess, killsec * 1000);
        if (w == WAIT_TIMEOUT) {
            printf("[*] %d s elapsed, terminating\n", killsec);
            TerminateProcess(pi.hProcess, 0);
        } else {
            DWORD code = 0;
            GetExitCodeProcess(pi.hProcess, &code);
            printf("[*] game exited on its own, code = %lu\n", code);
            if (code == SC3MODS_EXIT_LOADFAIL) { printf("[!] a mod failed to load (see loader lines above)\n"); return 4; }
        }
    } else {
        /* Exit code + lifetime (2026-10-21): the intermittent ~0.3 s startup deaths printed only "game exited",
           which cannot tell the single-instance exit (0xFFFFFFFF) from an NTSTATUS or a clean quit. */
        DWORD code = 0, t0 = GetTickCount();
        WaitForSingleObject(pi.hProcess, INFINITE);
        GetExitCodeProcess(pi.hProcess, &code);
        printf("[*] game exited, code = 0x%08lX after %lu ms\n", code, GetTickCount() - t0);
        if (code == SC3MODS_EXIT_LOADFAIL) { printf("[!] a mod failed to load (see loader lines above)\n"); return 4; }
    }
    if (ev) CloseHandle(ev);
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    return 0;
}
