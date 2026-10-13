/* mods_launch.exe - one launcher for all the sc3kre game mods.
 *
 * Starts SC3U.exe suspended (cwd = the game's Apps dir), injects EVERY mod DLL from the list
 * below that sits beside the launcher, then resumes. Same injector as bigcity_launch.c /
 * resize_launch.c (copied from sc3launch.c). Each mod finds its own ini and log beside itself.
 *
 *   mods_launch.exe [-delay <ms>] [-kill <seconds>] [-multi] [-exe <name>] [-- <args passed to the game>]
 *   -multi: per-instance mutex name, so several games can run at once (see unique_mutex).
 *
 * Mods are independent: each one checks the game bytes it patches and refuses (logging why)
 * rather than half-patching, so a collision shows up in that mod's log, not as a crash.
 */

#include <windows.h>
#include <stdio.h>

static int inject(HANDLE proc, const char *dll) {
    void *mem;
    HANDLE thread;
    SIZE_T len = lstrlenA(dll) + 1;
    HMODULE k32;
    FARPROC loadlib;
    DWORD exitcode = 0;

    k32 = GetModuleHandleA("kernel32.dll");
    loadlib = GetProcAddress(k32, "LoadLibraryA");
    if (!loadlib) { printf("[!] GetProcAddress(LoadLibraryA) failed\n"); return 0; }

    mem = VirtualAllocEx(proc, NULL, len, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!mem) { printf("[!] VirtualAllocEx failed: %lu\n", GetLastError()); return 0; }

    if (!WriteProcessMemory(proc, mem, dll, len, NULL)) {
        printf("[!] WriteProcessMemory failed: %lu\n", GetLastError());
        return 0;
    }

    thread = CreateRemoteThread(proc, NULL, 0, (LPTHREAD_START_ROUTINE)loadlib, mem, 0, NULL);
    if (!thread) { printf("[!] CreateRemoteThread failed: %lu\n", GetLastError()); return 0; }

    WaitForSingleObject(thread, 10000);
    GetExitCodeThread(thread, &exitcode);
    CloseHandle(thread);
    VirtualFreeEx(proc, mem, 0, MEM_RELEASE);

    if (!exitcode) { printf("[!] LoadLibraryA returned NULL in target\n"); return 0; }
    printf("[+] injected %s (remote HMODULE = 0x%08lX)\n", dll, exitcode);
    return 1;
}

/* -multi (2026-10-11): run several games at once. SC3U.exe refuses a second instance through the named mutex
   "SimCity 3000 Mutex" (FUN_0040496d reads its name through the pointer at 0x004f4b10, string at 0x004f4b24;
   a failed acquire without -restart focuses the other window and exits ~30 ms in, measured 2026-08-21). A named
   mutex is session-wide, so a second install copy does not help. With the process still suspended, write
   "SimCity 3000 Mutex <pid>" into it and point 0x004f4b10 at that copy: each instance owns its own mutex and the
   restart path is never taken. The exe file is not touched. Refuses (returns 0) if the pointer is not the shipped
   one, i.e. a different SC3U.exe build. */
static int unique_mutex(HANDLE proc, DWORD pid) {
    const DWORD slot = 0x004f4b10, shipped = 0x004f4b24;
    DWORD cur = 0, newp, oldprot;
    char name[64];
    SIZE_T got = 0, len;
    void *mem;
    if (!ReadProcessMemory(proc, (void *)slot, &cur, 4, &got) || got != 4 || cur != shipped) {
        printf("[!] -multi: mutex name pointer at 0x%08lX is 0x%08lX, expected 0x%08lX - not patched\n", slot, cur, shipped);
        return 0;
    }
    _snprintf(name, sizeof(name), "SimCity 3000 Mutex %lu", pid);
    len = lstrlenA(name) + 1;
    mem = VirtualAllocEx(proc, NULL, len, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!mem || !WriteProcessMemory(proc, mem, name, len, NULL)) { printf("[!] -multi: cannot write the name\n"); return 0; }
    newp = (DWORD)mem;
    VirtualProtectEx(proc, (void *)slot, 4, PAGE_READWRITE, &oldprot);
    if (!WriteProcessMemory(proc, (void *)slot, &newp, 4, NULL)) { printf("[!] -multi: cannot write the pointer\n"); return 0; }
    VirtualProtectEx(proc, (void *)slot, 4, oldprot, &oldprot);
    printf("[+] -multi: mutex renamed to \"%s\"\n", name);
    return 1;
}

static int inject_all(HANDLE proc, const char *dir, const char **mods, int n) {
    char dll[MAX_PATH];
    int m;
    for (m = 0; m < n; m++) {
        _snprintf(dll, sizeof(dll), "%s\\%s", dir, mods[m]);
        if (GetFileAttributesA(dll) == INVALID_FILE_ATTRIBUTES) continue;
        if (!inject(proc, dll)) return 0;
    }
    return 1;
}

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

int main(int argc, char **argv) {
    const char *exename = "SC3U.exe";
    char self[MAX_PATH], owndir[MAX_PATH], root[MAX_PATH];
    char exe[MAX_PATH], workdir[MAX_PATH], dll[MAX_PATH];
    static const char *mods[] = { "sc3resize.dll", "sc3bigcity.dll", "sc3overscroll.dll", "sc3simrun.dll", "sc3startsize.dll", "sc3perf.dll", "sc3netmod.dll" };
    int nmods = 0, m;
    char cmdline[2048];
    char gameargs[1024];
    STARTUPINFOA si;
    PROCESS_INFORMATION pi;
    int delayms = 0;
    int killsec = 0;
    int multi = 0;
    int i;
    char *p;

    /* Unbuffered: piped to a script, a buffered stdout held the "pid = N" line until the game exited (2026-10-11). */
    setvbuf(stdout, NULL, _IONBF, 0);
    gameargs[0] = 0;

    /* Where we are, and the DLL that sits beside us. */
    GetModuleFileNameA(NULL, self, sizeof(self));
    dirname_of(self, owndir, sizeof(owndir));
    _snprintf(dll, sizeof(dll), "%s\\sc3bigcity.dll", owndir);

    for (i = 1; i < argc; i++) {
        if (!lstrcmpiA(argv[i], "-delay") && i + 1 < argc) {
            delayms = atoi(argv[++i]);
        } else if (!lstrcmpiA(argv[i], "-exe") && i + 1 < argc) {
            exename = argv[++i];   /* test option: launch a renamed copy (compat layers are keyed by path) */
        } else if (!lstrcmpiA(argv[i], "-multi")) {
            multi = 1;
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

    /* SC3U.exe: ship layout is next to us (loader dropped in Apps); dev layout is
       <root>\Apps\SC3U.exe reached by walking up 4 levels from bin\bigcity_launch.exe. */
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
    for (m = 0; m < (int)(sizeof(mods) / sizeof(mods[0])); m++) {
        _snprintf(dll, sizeof(dll), "%s\\%s", owndir, mods[m]);
        if (GetFileAttributesA(dll) != INVALID_FILE_ATTRIBUTES) { printf("[*] mod : %s\n", mods[m]); nmods++; }
    }
    if (!nmods) {
        printf("[!] no mod DLL beside the loader (sc3resize.dll, sc3bigcity.dll, sc3overscroll.dll)\n");
        return 2;
    }

    _snprintf(cmdline, sizeof(cmdline), "\"%s\" %s", exe, gameargs);
    printf("[*] exe : %s\n", exe);
    printf("[*] dll : %s\n", dll);
    printf("[*] args: %s\n", gameargs[0] ? gameargs : "(none)");

    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(si);
    ZeroMemory(&pi, sizeof(pi));

    if (!CreateProcessA(NULL, cmdline, NULL, NULL, FALSE,
                        CREATE_SUSPENDED, NULL, workdir, &si, &pi)) {
        printf("[!] CreateProcess failed: %lu\n", GetLastError());
        return 3;
    }
    printf("[+] created suspended, pid = %lu\n", pi.dwProcessId);
    if (multi && !unique_mutex(pi.hProcess, pi.dwProcessId)) { TerminateProcess(pi.hProcess, 1); return 5; }

    if (delayms > 0) {
        /* Inject after the process loader has run, not while still suspended (sc3launch.c note). */
        ResumeThread(pi.hThread);
        printf("[+] resumed first, injecting in %d ms\n", delayms);
        Sleep(delayms);
        if (!inject_all(pi.hProcess, owndir, mods, sizeof(mods) / sizeof(mods[0]))) { TerminateProcess(pi.hProcess, 1); return 4; }
    } else {
        if (!inject_all(pi.hProcess, owndir, mods, sizeof(mods) / sizeof(mods[0]))) { TerminateProcess(pi.hProcess, 1); return 4; }
        ResumeThread(pi.hThread);
        printf("[+] resumed\n");
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
        }
    } else {
        WaitForSingleObject(pi.hProcess, INFINITE);
        printf("[*] game exited\n");
    }
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    return 0;
}
