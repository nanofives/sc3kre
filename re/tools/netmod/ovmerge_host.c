/* ovmerge_host.c - runs sc3netmod's OVMERGE block (re/harness/src/sc3netmod_ovmerge.c, the same source the DLL
 * compiles) outside the game, for ovmerge_test.py (task overlaymerge 2026-11-21).
 *
 *   ovmerge_host.exe <game root>      -> log lines on stdout, then one "SERVED <rel> <path>" line per merged file and
 *                                        "STATUS <n> <names>" (what sc3netmod_ovmerge_status returns)
 * Env SC3NETMOD_OVMERGE=0 is honoured as in the DLL. Built by ovmerge_test.py with the VC tools (cl /O2). */
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

static void logf(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    vprintf(fmt, ap);
    va_end(ap);
    printf("\n");
}
static int env_off(const char *name) {
    char v[8];
    return GetEnvironmentVariableA(name, v, sizeof(v)) && v[0] == '0';
}

static char g_root[MAX_PATH];
static int g_rootlen;
static char g_ovdir[MAX_PATH];
static char **g_ovfiles;
static int g_novfiles;

static void ov_add(const char *rel) {
    g_ovfiles = (char **)realloc(g_ovfiles, (g_novfiles + 1) * sizeof(char *));
    g_ovfiles[g_novfiles++] = _strdup(rel);
}
static void ov_walk(const char *rel) {
    char pat[MAX_PATH], sub[MAX_PATH];
    WIN32_FIND_DATAA fd;
    HANDLE h;
    _snprintf(pat, sizeof(pat), "%s%s*", g_ovdir, rel);
    h = FindFirstFileA(pat, &fd);
    if (h == INVALID_HANDLE_VALUE) return;
    do {
        if (!strcmp(fd.cFileName, ".") || !strcmp(fd.cFileName, "..")) continue;
        _snprintf(sub, sizeof(sub), "%s%s", rel, fd.cFileName);
        if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) { strcat(sub, "\\"); ov_walk(sub); }
        else ov_add(sub);
    } while (FindNextFileA(h, &fd));
    FindClose(h);
}

#include "../../harness/src/sc3netmod_ovmerge.c"

int main(int argc, char **argv) {
    char names[256];
    int i, n;
    if (argc < 2) { fprintf(stderr, "usage: ovmerge_host <game root>\n"); return 2; }
    GetFullPathNameA(argv[1], MAX_PATH, g_root, NULL);
    if (g_root[strlen(g_root) - 1] != '\\') strcat(g_root, "\\");
    g_rootlen = (int)strlen(g_root);
    _snprintf(g_ovdir, sizeof(g_ovdir), "%smods\\netmod\\overlay\\", g_root);
    ov_walk("");
    ovmerge_init();
    for (i = 0; i < g_novfiles; i++) if (g_ovalt && g_ovalt[i]) printf("SERVED %s %s\n", g_ovfiles[i], g_ovalt[i]);
    n = sc3netmod_ovmerge_status(names, sizeof(names));
    printf("STATUS %d %s\n", n, names);
    return 0;
}
