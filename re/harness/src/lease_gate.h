/* lease_gate.h - dev-PC game-lease gate shared by mods_launch.c and sc3launch.c. Needs windows.h, stdio.h, string.h. */
#ifndef LEASE_GATE_H
#define LEASE_GATE_H

/* Dev-PC lease gate (2026-10-21). On 2026-10-20 a session's script launched the game over a lease another session
   held (re/harness/game_lock.ps1). The lease is advisory and only the PowerShell helpers checked it, so every
   launcher that called mods_launch.exe directly ignored it. The check now lives here, where every launch passes.
   Only in the repo layout (<root>\re\harness\game_lock.ps1 exists): a released install has no such file and is
   never gated. A LIVE lease (expiresUtc in the future, same TTL rule as game_lock.ps1) whose owner is not
   %SC3_SESSION% refuses the launch with exit 7. No lease = allowed with a warning (parallel -multi children run
   without one). -nolease skips the gate on purpose. */
static int json_str(const char *json, const char *key, char *out, int cb) {
    char pat[64];
    const char *p, *e;
    int n;
    out[0] = 0;
    _snprintf(pat, sizeof(pat), "\"%s\"", key);
    p = strstr(json, pat);
    if (!p) return 0;
    p = strchr(p + lstrlenA(pat), ':');
    if (!p) return 0;
    p = strchr(p, '"');
    if (!p) return 0;
    e = strchr(++p, '"');
    if (!e) return 0;
    n = (int)(e - p);
    if (n >= cb) n = cb - 1;
    lstrcpynA(out, p, n + 1);
    return 1;
}

/* returns 1 = may launch, 0 = refused */
static int lease_gate(const char *root) {
    char path[MAX_PATH], buf[4096], owner[128], expires[64], session[128];
    HANDLE f;
    DWORD got = 0;
    SYSTEMTIME st, now;
    FILETIME ft, fnow;
    _snprintf(path, sizeof(path), "%s\\re\\harness\\game_lock.ps1", root);
    if (GetFileAttributesA(path) == INVALID_FILE_ATTRIBUTES) return 1;          /* not the dev repo */
    if (!GetEnvironmentVariableA("SC3_SESSION", session, sizeof(session))) session[0] = 0;
    _snprintf(path, sizeof(path), "%s\\re\\harness\\GAME_LOCK.json", root);
    f = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, NULL, OPEN_EXISTING, 0, NULL);
    if (f == INVALID_HANDLE_VALUE) {
        printf("[!] lease: no game lease held (re\\harness\\game_lock.ps1 -Acquire -Owner <you>), launching anyway\n");
        return 1;
    }
    ReadFile(f, buf, sizeof(buf) - 1, &got, NULL);
    CloseHandle(f);
    buf[got] = 0;
    if (!json_str(buf, "owner", owner, sizeof(owner)) || !json_str(buf, "expiresUtc", expires, sizeof(expires))) {
        printf("[!] lease: REFUSED - %s is unreadable; check it with game_lock.ps1 -Status (or pass -nolease)\n", path);
        return 0;
    }
    ZeroMemory(&st, sizeof(st));
    if (sscanf(expires, "%hu-%hu-%huT%hu:%hu:%hu", &st.wYear, &st.wMonth, &st.wDay, &st.wHour, &st.wMinute, &st.wSecond) != 6
        || !SystemTimeToFileTime(&st, &ft)) {
        printf("[!] lease: REFUSED - cannot read expiresUtc \"%s\" (pass -nolease to override)\n", expires);
        return 0;
    }
    GetSystemTime(&now);
    SystemTimeToFileTime(&now, &fnow);
    if (CompareFileTime(&ft, &fnow) <= 0) {
        printf("[!] lease: stale lease of '%s' (expired %s), launching\n", owner, expires);
        return 1;
    }
    if (lstrcmpiA(owner, session) != 0) {
        printf("\n[!] ==================================================================\n");
        printf("[!] lease: REFUSED - the game lease is held by '%s' until %s,\n", owner, expires);
        printf("[!]        and SC3_SESSION is '%s'. Another session is using the game.\n", session[0] ? session : "(unset)");
        printf("[!]        Queue with: pwsh re/harness/game_lock.ps1 -Acquire -Wait -Owner <you>\n");
        printf("[!]        then set SC3_SESSION=<you>. Do not kill that session's game.\n");
        printf("[!] ==================================================================\n\n");
        return 0;
    }
    printf("[+] lease: held by '%s' (this session) until %s\n", owner, expires);
    return 1;
}

#endif
