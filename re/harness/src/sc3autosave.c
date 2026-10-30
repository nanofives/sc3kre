/* sc3autosave.c - save the city to a separate autosave file every few minutes (owner request 2026-10-27).
 *
 * The save is the game's own Save command, the same one the File menu runs, pointed at an autosave path:
 *   - command CLSID 0x410438DD, one string argument = the path (recipe of SC3U 0x004108f3, first used by sc3undo's
 *     snapshot mode, verify/undo_spike/RESULTS.md).
 *   - The menu save brackets the command with city vt+0x21c / vt+0x220 (SIMCITY 0x100058ac / 0x1000590e: lock
 *     counter city+0x144 up / down, sim sub-object +0x130 vt+0x2c / +0x30) [CONFIRMED @ 0x004108f3]. This mod does
 *     the same, so the sim holds still while it writes.
 *   - The command re-points the city's file name at the path it saved to. The mod reads the name first (city vt+0x254
 *     = SIMCITY 0x10007116 -> string at city+0x15c) and puts it back after (vt+0x258 = 0x1000713b), so the player's
 *     own Save still goes to their own file.
 *   - The menu save then calls thunk_FUN_0045d5ae()->vt+0x40(0) when it succeeds. The autosave does NOT, so the
 *     game still treats the city as unsaved and asks "save changes?" on quit as before. [UNCERTAIN: what vt+0x40(0)
 *     clears is not read; the mod just leaves it alone.]
 *
 * Where: next to the city's own file, three files "<city> (auto 5 min).sc3", "(auto 10 min)", "(auto 1 h)" (2026-10-28,
 * "three files" below; builds before that wrote "<city>.autosave1/2.sc3", which are left alone). A city that was never
 * saved goes to <game>\Cities\Untitled (auto ...).sc3. Each save goes to "<city> (auto).tmp.sc3" first (the command
 * appends ".sc3" to any path that does not end in it, measured 2026-10-27) and is renamed over the target only when the
 * game says it succeeded, so a failed or interrupted save never destroys the previous autosave. A save byte-identical
 * to the newest autosave (a paused city saves identically) is dropped.
 *
 * When: a watcher thread checks every second and posts WM_AUTOSAVE to the game window, so the save runs on the game
 * thread. The save is put off (retried next second) while a mouse button is held or captured (a drag is in
 * progress), while a text field has focus, while the city object is new (< 20 s since it appeared, or since the game
 * thread came back from a load, "one WM_AUTOSAVE in flight" below) or the city's own lock counter is nonzero (the game
 * is saving, or a dialog such as Load City is open: lock 3 measured 2026-10-28), or while another autosave is running.
 * A due save also waits for idle_seconds without mouse or keyboard input ("idle wait" below).
 *
 * Cost: the game freezes for one save. With the game's "Guardando..." box replaced by the corner indicator ("corner
 * indicator" below) that is ~0.3 s on Frankfurt (690 KB), against 1.6 - 2.7 s with the box.
 *
 * autosave.ini beside the DLL:
 *   [autosave] enabled=1 minutes=5 dir= idle_seconds=3 indicator=1   (dir empty = next to the city file; keep= is gone)
 * Test overrides: SC3AUTOSAVE_SECONDS=<n> (interval in seconds), SC3AUTOSAVE_TIERS=<b>,<c> (the 10 min / 1 h ages in
 * seconds), SC3AUTOSAVE_LOG=<path>, SC3AUTOSAVE_HOLD=<ms> (hold the game thread after the save with the indicator up),
 * SC3AUTOSAVE_INDFORCE=1 (show the indicator even when the game is not in front), SC3AUTOSAVE_DIAG=1 (log the stack of
 * every WM_AUTOSAVE dispatch).
 * Log: sc3autosave.log beside the DLL.
 */
#include <windows.h>
#include "sc3mods_guard.h"
#pragma comment(lib, "gdi32.lib")     /* the corner indicator */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

static CRITICAL_SECTION g_lock;
static HANDLE g_log = INVALID_HANDLE_VALUE;
static LARGE_INTEGER g_freq, g_t0;
static HMODULE g_self;

static void logf(const char *fmt, ...) {
    char buf[1536], line[1700];
    va_list ap;
    LARGE_INTEGER now;
    DWORD wrote;
    int n;
    va_start(ap, fmt);
    _vsnprintf(buf, sizeof(buf) - 1, fmt, ap);
    buf[sizeof(buf) - 1] = 0;
    va_end(ap);
    QueryPerformanceCounter(&now);
    n = _snprintf(line, sizeof(line) - 1, "[%9.3f ms][tid %04lx] %s\r\n",
                  (double)(now.QuadPart - g_t0.QuadPart) * 1000.0 / (double)g_freq.QuadPart,
                  GetCurrentThreadId(), buf);
    if (n < 0) return;
    EnterCriticalSection(&g_lock);
    if (g_log != INVALID_HANDLE_VALUE) WriteFile(g_log, line, (DWORD)n, &wrote, NULL);
    LeaveCriticalSection(&g_lock);
}

static void self_path(char *out, int cap, const char *leaf) {
    char *slash;
    if (!GetModuleFileNameA(g_self, out, cap)) { out[0] = 0; return; }
    slash = strrchr(out, '\\');
    if (slash) slash[1] = 0; else out[0] = 0;
    lstrcatA(out, leaf);
}

/* ------------------------------------------------------------------ config */
static int   g_enabled = 1;
static DWORD g_tier_b = 10 * 60, g_tier_c = 60 * 60;   /* seconds, see "three files" below */
static DWORD g_interval_ms = 5 * 60 * 1000;
static char  g_cfg_dir[MAX_PATH];
static DWORD g_idle_ms = 3000;      /* idle wait, see "idle wait" below */
static int   g_indicator = 1;       /* corner indicator instead of the progress box */
static int   g_unauto = 1;          /* UNAUTO below; autosave.ini [autosave] unauto=, SC3AUTOSAVE_UNAUTO overrides */
static int   g_faultfix = 1;       /* FAULTFIX below; SC3AUTOSAVE_FAULTFIX=0 = off */
static DWORD g_min_free_mb = 64;   /* MINFREE below; autosave.ini [autosave] min_free_mb=, SC3AUTOSAVE_MINFREE, 0 = off */

static void ini_read(void) {
    char path[MAX_PATH], v[32];
    int minutes;
    self_path(path, sizeof(path), "autosave.ini");
    if (path[0]) {
        g_enabled = GetPrivateProfileIntA("autosave", "enabled", 1, path) ? 1 : 0;
        minutes   = GetPrivateProfileIntA("autosave", "minutes", 5, path);
        GetPrivateProfileStringA("autosave", "dir", "", g_cfg_dir, sizeof(g_cfg_dir), path);
        g_idle_ms   = (DWORD)GetPrivateProfileIntA("autosave", "idle_seconds", 3, path) * 1000;
        g_indicator = GetPrivateProfileIntA("autosave", "indicator", 1, path) ? 1 : 0;
        g_unauto    = GetPrivateProfileIntA("autosave", "unauto", 1, path) ? 1 : 0;
        g_min_free_mb = (DWORD)GetPrivateProfileIntA("autosave", "min_free_mb", 64, path);
        if (minutes < 1) minutes = 1;
        if (minutes > 240) minutes = 240;
        g_interval_ms = (DWORD)minutes * 60 * 1000;
    }
    if (GetEnvironmentVariableA("SC3AUTOSAVE_UNAUTO", v, sizeof(v))) g_unauto = atoi(v) != 0;
    if (GetEnvironmentVariableA("SC3AUTOSAVE_MINFREE", v, sizeof(v))) g_min_free_mb = (DWORD)atoi(v);
    if (GetEnvironmentVariableA("SC3AUTOSAVE_FAULTFIX", v, sizeof(v))) g_faultfix = atoi(v) != 0;
    if (GetEnvironmentVariableA("SC3AUTOSAVE_SECONDS", v, sizeof(v)) && atoi(v) > 0) g_interval_ms = (DWORD)atoi(v) * 1000;
    /* test only: SC3AUTOSAVE_TIERS=<b>,<c> = the 10 min / 1 h ages in seconds */
    if (GetEnvironmentVariableA("SC3AUTOSAVE_TIERS", v, sizeof(v)) && atoi(v) > 0 && strchr(v, ',')) {
        g_tier_b = (DWORD)atoi(v);
        g_tier_c = (DWORD)atoi(strchr(v, ',') + 1);
    }
}

/* ------------------------------------------------------------------ engine access */
static BYTE *g_exe;

static void *vslot(void *obj, unsigned off) {
    void **vt;
    if (!obj || IsBadReadPtr(obj, 4)) return NULL;
    vt = *(void ***)obj;
    if (!vt || IsBadReadPtr(vt, off + 4)) return NULL;
    return vt[off / 4];
}

/* the loaded city (SIMCITY+0x13260 vtable checked), or NULL */
static BYTE *city_get(void) {
    HMODULE simcity = GetModuleHandleA("SIMCITY.DLL");
    BYTE *app, *city;
    if (!simcity) return NULL;
    __try {
        app = *(BYTE **)(g_exe + 0xfa86c);
        if (!app) return NULL;
        city = *(BYTE **)(app + 0x48);
        if (!city || *(DWORD *)city != (DWORD)simcity + 0x13260) return NULL;
        return city;
    } __except (EXCEPTION_EXECUTE_HANDLER) { return NULL; }
}
static long city_lock(BYTE *city) {
    __try { return *(long *)(city + 0x144); } __except (EXCEPTION_EXECUTE_HANDLER) { return -1; }
}

/* a text field has keyboard focus (sc3resize KEYFOCUS, same check as sc3undo) */
static int text_focus(void) {
    DWORD gz = (DWORD)GetModuleHandleA("GZGraphicD.dll"), gw = (DWORD)GetModuleHandleA("GZWIND.DLL");
    DWORD si = (DWORD)GetModuleHandleA("SIMINIT.DLL"), su = (DWORD)GetModuleHandleA("SIMUI.DLL");
    BYTE *win, *sink, *f;
    DWORD vt;
    if (!gz) return 0;
    __try {
        win = *(BYTE **)(gz + 0x6cdb8);
        if (!win || *(DWORD *)win != gz + 0x1f740) return 0;
        sink = *(BYTE **)(win + 0x30);
        if (!sink || !gw || *(DWORD *)sink != gw + 0x2db80) return 0;
        f = *(BYTE **)(sink + 0x2c);
        if (!f) return 0;
        vt = *(DWORD *)f;
        if (vt == gw + 0x2bf10) return 1;
        if (vt == gw + 0x2a8cc || (si && vt == si + 0x30890) || (su && (vt == su + 0xa5f7c || vt == su + 0xadca0)))
            return f[0x111] != 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) { return 0; }
    return 0;
}

/* city file name: copy out of the embedded string, put back through a two-slot fake cIGZString */
static char g_name[MAX_PATH];
static int  g_name_len;
static const char *__fastcall fs_data(void *self) { (void)self; return g_name; }
static DWORD __fastcall fs_len(void *self) { (void)self; return (DWORD)g_name_len; }
static void *g_fs_vt[8];
static void *g_fs_obj = g_fs_vt;
static void name_save(BYTE *city) {
    typedef BYTE *(__fastcall *PFN_GetName)(void *, void *);
    BYTE *s;
    char *b, *e;
    g_name_len = -1;
    g_name[0] = 0;
    __try {
        s = ((PFN_GetName)vslot(city, 0x254))(city, NULL);               /* SIMCITY 0x10007116 -> city+0x15c */
        b = *(char **)(s + 4); e = *(char **)(s + 8);
        if (!b && !e) g_name_len = 0;                                   /* empty string: never saved */
        else if (b && e >= b && e - b < MAX_PATH) { memcpy(g_name, b, e - b); g_name_len = (int)(e - b); g_name[g_name_len] = 0; }
    } __except (EXCEPTION_EXECUTE_HANDLER) { g_name_len = -1; }
}
static void name_restore(BYTE *city) {
    typedef void (__fastcall *PFN_SetName)(void *, void *, void *);
    void *obj = &g_fs_obj;
    if (g_name_len < 0 || !city) return;
    g_fs_vt[6] = (void *)fs_data;                                        /* vt+0x18 */
    g_fs_vt[7] = (void *)fs_len;                                         /* vt+0x1c */
    __try { ((PFN_SetName)vslot(city, 0x258))(city, NULL, obj); }      /* SIMCITY 0x1000713b */
    __except (EXCEPTION_EXECUTE_HANDLER) { logf("name_restore threw 0x%08lX", GetExceptionCode()); }
}

/* the game's own Save command (CLSID 0x410438DD), game thread only. Returns the command's own success byte. */
typedef void *(__cdecl    *PFN_GNew)(unsigned);
typedef void *(__cdecl    *PFN_GDir)(void);
typedef DWORD (__fastcall *PFN_GCreate)(void *, void *, DWORD, DWORD, void **);
typedef DWORD (__fastcall *PFN_GV0)(void *, void *);
typedef DWORD (__fastcall *PFN_GV1)(void *, void *, void *);
typedef void  (__fastcall *PFN_GVarCtor)(void *);
typedef void  (__fastcall *PFN_GVarS)(void *, void *, const char *, DWORD);
/* FAULTFIX (child memleak 2026-10-29). Owner crash 10-29 (MARIANO-PC, Big One 1024, 72 min): the address space ran
 * out, a save faulted half way ("SAVE threw 0xC0000005", caught below), and every later save was "put off: city
 * locked" until the game died. The city save SIMCITY 0x1000429d (the handler the Save command reaches) does three
 * things that only its normal exit undoes, and an exception unwinds past all three:
 *   - city+0x1a8 lock object (FUN_1000d283: vtable, CRITICAL_SECTION at +4, depth +0x20; vt+4 = FUN_1000d310 enter +
 *     depth++, vt+8 = FUN_1000d3e0 depth-- + leave) entered at the start, left at the end;
 *   - city vt+0x21c (lock counter city+0x144 up, sim sub-object +0x130 vt+0x2c), vt+0x220 at the end;
 *   - a progress object at city+0x1a4 (FUN_10002678), closed by FUN_100026a8 and freed at the end.
 * [CONFIRMED @ SIMCITY 0x1000429d, 0x1000d283, 0x1000d310, 0x1000d3e0, 0x10002678, 0x100026a8]
 * After a fault the mod puts each back to what it read before the save (leaves the critical section as often as this
 * thread entered it, calls vt+0x220 until city+0x144 is back, closes the progress object through FUN_100026a8 while
 * the progress wrappers still swallow it, and clears city+0x1a4; the 8-byte object is left unfreed), then stops
 * autosaving for the session (g_fault_stop). SC3AUTOSAVE_FAULTFIX=0 = the old behaviour (log only, keep saving). */
static volatile LONG g_fault_stop;

/* MINFREE (child memleak 2026-10-29): the owner's failed save ran with the largest free address block at 62 MB (sc3perf
 * CSV, 10-29); the saves before it, at 78 MB and more, worked. The game is not large-address-aware (2 GB user space), so
 * a save that needs a block the process no longer has faults. Before each autosave the mod walks the address space
 * (VirtualQuery, as sc3perf does) and skips the save when the largest free block is under min_free_mb (default 64,
 * autosave.ini [autosave] min_free_mb=, SC3AUTOSAVE_MINFREE=<MB>, 0 = no check). A skipped save logs a line and is tried
 * again one interval later. */
static char  g_mem_note[64] = "not measured";
static DWORD mem_largest_free_mb(void) {
    MEMORY_BASIC_INFORMATION mbi;
    BYTE *a = (BYTE *)0x10000;
    SIZE_T big = 0;
    while (a < (BYTE *)0x7FFF0000 && VirtualQuery(a, &mbi, sizeof(mbi))) {
        if (mbi.State == MEM_FREE && mbi.RegionSize > big) big = mbi.RegionSize;
        a = (BYTE *)mbi.BaseAddress + mbi.RegionSize;
    }
    return (DWORD)(big >> 20);
}
typedef void (__fastcall *PFN_PgEnd)(void *);
static void save_recover(BYTE *city, long lock0, DWORD depth0, BYTE *prog0, PFN_GV0 lock_dn) {
    BYTE *lk = city + 0x1a8;
    int n = 0, m = 0;
    __try {
        RTL_CRITICAL_SECTION *cs = (RTL_CRITICAL_SECTION *)(lk + 4);
        while ((DWORD)cs->OwningThread == GetCurrentThreadId() && *(DWORD *)(lk + 0x20) > depth0 && n < 16) {
            ((PFN_GV0)vslot(lk, 0x08))(lk, NULL);                        /* FUN_1000d3e0 */
            n++;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) { logf("FAULTFIX> city lock object threw 0x%08lX", GetExceptionCode()); }
    __try {
        while (lock_dn && *(long *)(city + 0x144) > lock0 && m < 16) { lock_dn(city, NULL); m++; }
    } __except (EXCEPTION_EXECUTE_HANDLER) { logf("FAULTFIX> unlock threw 0x%08lX", GetExceptionCode()); }
    __try {
        BYTE *p = *(BYTE **)(city + 0x1a4);
        if (p && p != prog0) {
            ((PFN_PgEnd)((BYTE *)GetModuleHandleA("SIMCITY.DLL") + 0x26a8))(p);   /* FUN_100026a8, swallowed */
            *(BYTE **)(city + 0x1a4) = prog0;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) { logf("FAULTFIX> progress close threw 0x%08lX", GetExceptionCode()); }
    logf("FAULTFIX> after the fault: left the city lock object %d time(s), city lock %d time(s), now lock %ld",
         n, m, city_lock(city));
}

static int game_save(BYTE *city, const char *path) {
    PFN_GNew gnew = (PFN_GNew)(g_exe + 0xB4890);                       /* operator_new, the game heap */
    PFN_GDir gdir = (PFN_GDir)(g_exe + 0x84573);                       /* COM director, SC3U 0x00484573 */
    PFN_GV0 lock_up = (PFN_GV0)vslot(city, 0x21c), lock_dn = (PFN_GV0)vslot(city, 0x220);
    void *dir, *cmd = NULL, *v;
    DWORD ok = 0, depth0 = *(DWORD *)(city + 0x1a8 + 0x20);
    long lock0 = city_lock(city);
    BYTE *prog0 = *(BYTE **)(city + 0x1a4);
    int locked = 0, faulted = 0;
    __try {
        dir = gdir();
        if (!dir) return 0;
        if (!(((PFN_GCreate)vslot(dir, 0x0c))(dir, NULL, 0x410438DD, 0x006856F7, &cmd) & 0xff) || !cmd)
            return 0;
        if (lock_up) { lock_up(city, NULL); locked = 1; }                /* as the menu save: SIMCITY 0x100058ac */
        v = gnew(0x28);
        ((PFN_GVarCtor)(g_exe + 0x6ECC0))(v);
        ((PFN_GVarS)(g_exe + 0x6F896))(v, NULL, path, (DWORD)strlen(path));
        ((PFN_GV0)vslot(v, 0x04))(v, NULL);
        ((PFN_GV1)vslot(cmd, 0x0c))(cmd, NULL, v);
        ((PFN_GV0)vslot(v, 0x08))(v, NULL);
        ok = ((PFN_GV0)vslot(cmd, 0x2c))(cmd, NULL) & 0xff;
        ((PFN_GV0)vslot(cmd, 0x08))(cmd, NULL);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        logf("SAVE threw 0x%08lX", GetExceptionCode());
        ok = 0;
        faulted = 1;
    }
    if (faulted && g_faultfix) {
        save_recover(city, lock0 + locked, depth0, prog0, lock_dn);   /* our own vt+0x21c is undone just below */
        InterlockedExchange(&g_fault_stop, 1);
        logf("SAVE> autosave is OFF for the rest of this session: the game faulted inside its own save (memory %s). "
             "Save by hand under a new name, then restart the game.", g_mem_note);
    }
    if (locked) {
        __try { lock_dn(city, NULL); }                                  /* SIMCITY 0x1000590e */
        __except (EXCEPTION_EXECUTE_HANDLER) { logf("unlock threw 0x%08lX", GetExceptionCode()); }
    }
    return (int)ok;
}

/* ------------------------------------------------------------------ files */
static int file_hash(const char *path, unsigned __int64 *h, DWORD *size) {
    HANDLE f = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    static BYTE buf[65536];
    DWORD got, i;
    unsigned __int64 x = 1469598103934665603ULL;
    if (f == INVALID_HANDLE_VALUE) return 0;
    *size = 0;
    while (ReadFile(f, buf, sizeof(buf), &got, NULL) && got) {
        for (i = 0; i < got; i++) { x ^= buf[i]; x *= 1099511628211ULL; }
        *size += got;
    }
    CloseHandle(f);
    *h = x;
    return 1;
}

/* "<dir>\<base>" from the city file name (or <game>\Cities\Untitled when it has none) */
static void target_stem(char *out, int cap) {
    char dir[MAX_PATH], base[MAX_PATH], *s, *dot;
    if (g_name_len > 0) {
        lstrcpynA(dir, g_name, sizeof(dir));
        s = strrchr(dir, '\\');
        if (!s) s = strrchr(dir, '/');
        if (s) { lstrcpynA(base, s + 1, sizeof(base)); s[0] = 0; }
        else { lstrcpynA(base, dir, sizeof(base)); dir[0] = 0; }
        dot = strrchr(base, '.');
        if (dot) *dot = 0;
        /* an autosave the player loaded saves under its city, not as "x (auto 5 min) (auto 5 min)" */
        if ((dot = strstr(base, " (auto")) != NULL) *dot = 0;
        if ((dot = strstr(base, ".autosave")) != NULL) *dot = 0;     /* names of the builds before 10-28 */
    } else {
        lstrcpyA(base, "Untitled");
        dir[0] = 0;
    }
    if (g_cfg_dir[0]) lstrcpynA(dir, g_cfg_dir, sizeof(dir));
    if (!dir[0]) {                                                     /* <exe dir>\..\Cities */
        GetModuleFileNameA(NULL, dir, sizeof(dir));
        if ((s = strrchr(dir, '\\')) != NULL) *s = 0;
        if ((s = strrchr(dir, '\\')) != NULL) *s = 0;
        lstrcatA(dir, "\\Cities");
    }
    if (!base[0]) lstrcpyA(base, "Untitled");
    _snprintf(out, cap, "%s\\%s", dir, base);
    out[cap - 1] = 0;
}

/* ------------------------------------------------------------------ three files
 * Owner 2026-10-28: "guardar hasta 3 autosave, el de los ultimos 5 minutos, ultimos 10, ultima hora".
 *   A "<city> (auto 5 min).sc3"   the newest autosave
 *   B "<city> (auto 10 min).sc3"
 *   C "<city> (auto 1 h).sc3"
 * Each save is written to "<city> (auto).tmp.sc3". If it differs from A: when A exists and B is missing or its save is
 * at least 10 min old, B first moves to C (when C is missing or its save is at least 60 min old), then A moves to B;
 * last the tmp file becomes A. A file's age is its last-write time (a rename keeps it), i.e. when that save was made.
 * With the 5 min default A is 0-5 min old, B the save before it, C 10-65 min old. */
static const char *const k_slot[3] = { " (auto 5 min).sc3", " (auto 10 min).sc3", " (auto 1 h).sc3" };
static void slot_path(char *out, int cap, const char *stem, int i) {
    _snprintf(out, cap, "%s%s", stem, k_slot[i]);
    out[cap - 1] = 0;
}
/* seconds since the file was last written, or -1 when it does not exist */
static long file_age(const char *path) {
    WIN32_FILE_ATTRIBUTE_DATA a;
    FILETIME now;
    unsigned __int64 n, w;
    if (!GetFileAttributesExA(path, GetFileExInfoStandard, &a)) return -1;
    GetSystemTimeAsFileTime(&now);
    n = ((unsigned __int64)now.dwHighDateTime << 32) | now.dwLowDateTime;
    w = ((unsigned __int64)a.ftLastWriteTime.dwHighDateTime << 32) | a.ftLastWriteTime.dwLowDateTime;
    return n > w ? (long)((n - w) / 10000000) : 0;
}
static int move_over(const char *from, const char *to) {
    if (MoveFileExA(from, to, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) return 1;
    logf("ROT> rename %s -> %s failed (%lu)", from, to, GetLastError());
    return 0;
}
/* make room in A for the new save: A -> B, B -> C by the ages above */
static void rotate(const char *stem) {
    char a[MAX_PATH], b[MAX_PATH], c[MAX_PATH];
    long aa, ab, ac;
    slot_path(a, sizeof(a), stem, 0); slot_path(b, sizeof(b), stem, 1); slot_path(c, sizeof(c), stem, 2);
    aa = file_age(a); ab = file_age(b); ac = file_age(c);
    if (aa < 0) return;                                        /* no A: nothing to keep */
    if (ab >= 0 && ab < (long)g_tier_b) {                      /* B young enough: A is simply replaced */
        logf("ROT> A (%ld s) replaced, B (%ld s) kept", aa, ab);
        return;
    }
    if (ab >= 0 && (ac < 0 || ac >= (long)g_tier_c)) {
        if (move_over(b, c)) logf("ROT> B (%ld s) -> C (was %ld s)", ab, ac);
    }
    if (move_over(a, b)) logf("ROT> A (%ld s) -> B (was %ld s)", aa, ab);
}

/* ------------------------------------------------------------------ the autosave */
#define WM_AUTOSAVE (WM_APP + 0x5E0)
#define WM_AS_HOOK  (WM_APP + 0x5E1)     /* wrap the progress service once a city exists (game thread) */
#define WM_AS_UNAUTO (WM_APP + 0x5E2)    /* a loaded autosave: point the city's file name back at its own file */
static HWND    g_hwnd;
static WNDPROC g_oldproc;
static volatile LONG g_busy;
static BYTE   *g_seen_city;
static DWORD   g_seen_at, g_last_save;
/* One WM_AUTOSAVE in flight (child autosave3 2026-10-28). The watcher used to post one every second while a save was
 * due. During a long load (Europolis 1024: the city pointer changed at 267 s, the game thread came back at ~303 s) they
 * queued up and all ran when the load ended: 6 full saves back to back, 1.5-2.5 s each, and the "just loaded" guard
 * had already run out because it counted from the pointer change. Now the watcher posts only when none is queued,
 * the handler drops a message for another city or one that is no longer due, and a message that waited in the queue
 * for over 5 s (the game thread was stuck, a load) restarts the "just loaded" wait from that moment. */
static volatile LONG g_posted;
static int     g_wait_unlock;          /* new city, its lock counter not yet seen at 0 */
static BYTE   *g_post_city;
static DWORD   g_post_at, g_stall_at;
static int     g_saves, g_skips_logged;

/* ------------------------------------------------------------------ idle wait
 * The interval only makes a save DUE. A due save waits until the player has not touched mouse or keyboard over the
 * game window for idle_seconds (default 3), so the freeze does not land in the middle of building something. After
 * one more full interval without such a pause it saves anyway (at the next moment no button is held). */
static DWORD g_last_input;

/* ------------------------------------------------------------------ corner indicator instead of the progress box
 * The city save opens the game's progress box itself: SIMCITY 0x1000429d (city Save, the handler of message
 * 0x111fdae5 that the Save command posts) builds FUN_10002678(steps, string 0x2dd "Guardando...") at city+0x1a4, which
 * calls the progress service FUN_1000edff(): vt+0x88(total, title) open, vt+0x8c(step) advance (redraws the box),
 * vt+0x90() close (FUN_100026a8) [CONFIRMED @ SIMCITY 0x10002678, 0x100026e4, 0x100026a8]. Those three slots are
 * wrapped: during an autosave they feed a small "Autoguardando..." indicator instead of opening the box; at any other
 * time they call the game's own methods, so the player's Save and Load look exactly as before.
 * The indicator is its own small window over the game's top-left corner, run by its own thread: GDI drawn on the game
 * window itself never reached the screen (2026-10-27, desktop grab during a held save showed the frozen frame and no
 * box: the DirectDraw presentation covers it). The window never activates (WS_EX_NOACTIVATE), lets clicks through
 * (WS_EX_TRANSPARENT | WS_EX_LAYERED), shows "Autoguardando..." with a bar while the save runs, then "Autoguardado
 * HH:MM" for 2 s. */
typedef void (__fastcall *PFN_PgOpen)(void *, void *, DWORD, void *);
typedef void (__fastcall *PFN_PgStep)(void *, void *, DWORD);
typedef void (__fastcall *PFN_PgClose)(void *, void *);
static PFN_PgOpen  g_pg_open;
static PFN_PgStep  g_pg_step;
static PFN_PgClose g_pg_close;
static int   g_autosaving, g_pg_hooked;
static DWORD g_pg_total, g_pg_cur;

#define IND_W 176
#define IND_H 36
#define WM_IND_SHOW (WM_APP + 1)
#define WM_IND_DONE (WM_APP + 2)
static HWND  g_ind;                    /* the indicator window (owned by the indicator thread) */
static volatile LONG g_ind_state;      /* 0 hidden, 1 saving, 2 done */
static char  g_ind_done_text[32];

static void ind_paint(HWND w) {
    PAINTSTRUCT ps;
    HDC dc = BeginPaint(w, &ps);
    HFONT f, of;
    HBRUSH bg = CreateSolidBrush(RGB(0x7a, 0x8c, 0xf0)), trough = CreateSolidBrush(RGB(0xe0, 0xe4, 0xf8)),
           bar = CreateSolidBrush(RGB(0xe8, 0x60, 0x48));          /* the game's dialog blue / progress orange */
    RECT rc = { 0, 0, IND_W, IND_H }, r, b;
    DWORD tot = g_pg_total, cur = g_pg_cur;
    int fill;
    FillRect(dc, &rc, bg);
    FrameRect(dc, &rc, trough);
    f = CreateFontA(-13, 0, 0, 0, FW_BOLD, 0, 0, 0, DEFAULT_CHARSET, 0, 0, ANTIALIASED_QUALITY, 0, "Tahoma");
    of = (HFONT)SelectObject(dc, f);
    SetBkMode(dc, TRANSPARENT);
    SetTextColor(dc, RGB(0xff, 0xff, 0xff));
    SetRect(&r, 8, 3, IND_W - 8, 20);
    DrawTextA(dc, g_ind_state == 2 ? g_ind_done_text : "Autoguardando...", -1, &r, DT_LEFT | DT_SINGLELINE | DT_VCENTER);
    SetRect(&b, 8, 23, IND_W - 8, 29);
    FillRect(dc, &b, trough);
    if (g_ind_state == 2) cur = tot = 1;
    fill = tot ? (int)((b.right - b.left) * (cur > tot ? tot : cur) / tot) : 0;
    b.right = b.left + fill;
    if (fill > 0) FillRect(dc, &b, bar);
    SelectObject(dc, of);
    DeleteObject(f); DeleteObject(bg); DeleteObject(bar); DeleteObject(trough);
    EndPaint(w, &ps);
}

static LRESULT CALLBACK ind_proc(HWND w, UINT m, WPARAM wp, LPARAM lp) {
    switch (m) {
    case WM_PAINT: ind_paint(w); return 0;
    case WM_IND_SHOW: {                                  /* place over the game's client top-left, show, no activation */
        POINT pt = { 8, 26 };
        KillTimer(w, 1);
        if (!g_hwnd || IsIconic(g_hwnd)) return 0;
        ClientToScreen(g_hwnd, &pt);
        /* above the game and nothing else: the game window can be WS_EX_TOPMOST (ex-style 0x108 measured
           2026-10-27, a plain HWND_TOP indicator stayed behind it); when it is not, show only while the game is
           the foreground window, so the indicator never floats over another program */
        if (GetWindowLongA(g_hwnd, GWL_EXSTYLE) & WS_EX_TOPMOST)
            SetWindowPos(w, HWND_TOPMOST, pt.x, pt.y, IND_W, IND_H, SWP_NOACTIVATE | SWP_SHOWWINDOW);
        else if (GetForegroundWindow() == g_hwnd || GetEnvironmentVariableA("SC3AUTOSAVE_INDFORCE", NULL, 0)) {
            /* SC3AUTOSAVE_INDFORCE (test only): show even when the game is not in front, for a PrintWindow check */
            SetWindowPos(w, HWND_NOTOPMOST, pt.x, pt.y, IND_W, IND_H, SWP_NOACTIVATE);
            SetWindowPos(w, HWND_TOP, pt.x, pt.y, IND_W, IND_H, SWP_NOACTIVATE | SWP_SHOWWINDOW);
        } else return 0;
        InvalidateRect(w, NULL, FALSE);
        UpdateWindow(w);
        {   RECT wr; GetWindowRect(w, &wr);
            logf("IND> shown at (%ld,%ld)-(%ld,%ld) visible=%d", wr.left, wr.top, wr.right, wr.bottom, IsWindowVisible(w)); }
        return 0;
    }
    case WM_IND_DONE: InvalidateRect(w, NULL, FALSE); SetTimer(w, 1, 2000, NULL); return 0;
    case WM_TIMER: KillTimer(w, 1); g_ind_state = 0; ShowWindow(w, SW_HIDE); return 0;
    case WM_MOUSEACTIVATE: return MA_NOACTIVATE;
    case WM_NCHITTEST: return HTTRANSPARENT;
    }
    return DefWindowProcA(w, m, wp, lp);
}

static DWORD WINAPI ind_thread(LPVOID unused) {
    WNDCLASSA wc;
    MSG msg;
    (void)unused;
    memset(&wc, 0, sizeof(wc));
    wc.lpfnWndProc = ind_proc;
    wc.hInstance = (HINSTANCE)g_self;
    wc.lpszClassName = "sc3autosave_ind";
    wc.hCursor = LoadCursorA(NULL, (LPCSTR)IDC_ARROW);
    RegisterClassA(&wc);
    g_ind = CreateWindowExA(WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_LAYERED | WS_EX_TRANSPARENT, wc.lpszClassName, "",
                            WS_POPUP, 0, 0, IND_W, IND_H, NULL, NULL, wc.hInstance, NULL);
    if (!g_ind) { logf("IND> window not created (%lu)", GetLastError()); return 0; }
    SetLayeredWindowAttributes(g_ind, 0, 235, LWA_ALPHA);
    logf("IND> window 0x%08lX ready", (DWORD)g_ind);
    while (GetMessageA(&msg, NULL, 0, 0) > 0) { TranslateMessage(&msg); DispatchMessageA(&msg); }
    return 0;
}

/* called from the game thread by the progress wrappers and the autosave */
static void ind_show(void)   { if (g_indicator && g_ind) { g_ind_state = 1; PostMessageA(g_ind, WM_IND_SHOW, 0, 0); } }
static void ind_update(void) { if (g_indicator && g_ind && g_ind_state == 1) InvalidateRect(g_ind, NULL, FALSE); }
static void ind_done(int ok) {
    SYSTEMTIME t;
    if (!g_indicator || !g_ind || !g_ind_state) return;
    GetLocalTime(&t);
    if (ok) _snprintf(g_ind_done_text, sizeof(g_ind_done_text), "Autoguardado %02d:%02d", t.wHour, t.wMinute);
    else lstrcpyA(g_ind_done_text, "Autoguardado fallido");
    g_ind_done_text[sizeof(g_ind_done_text) - 1] = 0;
    g_ind_state = 2;
    PostMessageA(g_ind, WM_IND_DONE, 0, 0);
}

static volatile LONG g_pg_depth;      /* the game's own progress box is open (a load or a save is running) */
static void __fastcall pg_open(void *self, void *edx, DWORD total, void *title) {
    if (g_autosaving) { g_pg_total = total; g_pg_cur = 0; ind_show(); return; }
    InterlockedIncrement(&g_pg_depth);
    g_pg_open(self, edx, total, title);
}
static void __fastcall pg_step(void *self, void *edx, DWORD step) {
    if (g_autosaving) { g_pg_cur = step; ind_update(); return; }
    g_pg_step(self, edx, step);
}
static void __fastcall pg_close(void *self, void *edx) {
    if (g_autosaving) return;
    if (g_pg_depth > 0) InterlockedDecrement(&g_pg_depth);
    g_pg_close(self, edx);
}

/* SC3AUTOSAVE_DIAG=1 (diag, child autosave3 2026-10-28): every WM_AUTOSAVE dispatch logs why it would be put off and the
   game-module return addresses found on the stack, to see which message loop dispatched it */
static int g_diag;
static void diag_stack(const char *tag) {
    char line[1400], mod[MAX_PATH], *leaf;
    DWORD *sp, *top, v, esp_now;
    HMODULE m;
    int n = 0, len;
    __asm { mov esp_now, esp }
    sp = (DWORD *)esp_now;
    top = sp + 0x1800 / 4;
    len = _snprintf(line, sizeof(line), "DIAG> %s stack:", tag);
    for (; sp < top && n < 24 && len < (int)sizeof(line) - 64; sp++) {
        __try { v = *sp; } __except (EXCEPTION_EXECUTE_HANDLER) { break; }
        if (v < 0x00401000) continue;
        if (!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                                (LPCSTR)v, &m) || !m) continue;
        if (m == g_self || !GetModuleFileNameA(m, mod, sizeof(mod))) continue;
        leaf = strrchr(mod, '\\'); leaf = leaf ? leaf + 1 : mod;
        if (!lstrcmpiA(leaf, "SC3U.exe") || !_strnicmp(leaf, "SIM", 3) || !_strnicmp(leaf, "GZ", 2) || !_strnicmp(leaf, "STRT", 4)) {
            BYTE *b = (BYTE *)v;
            int call = 0;
            __try {   /* a return address: the bytes before it are a call (E8 rel32, FF /2 with a 0/1/4-byte operand) */
                call = b[-5] == 0xE8 || (b[-6] == 0xFF && (b[-5] & 0x38) == 0x10) || (b[-2] == 0xFF && (b[-1] & 0x38) == 0x10)
                    || (b[-3] == 0xFF && (b[-2] & 0x38) == 0x10);
            } __except (EXCEPTION_EXECUTE_HANDLER) { call = 0; }
            if (!call) continue;
            len += _snprintf(line + len, sizeof(line) - len, " %s+0x%lX", leaf, v - (DWORD)m);
            n++;
        }
    }
    logf("%s", line);
}

/* wrap the three slots once, on the game thread (FUN_1000edff builds the service on first use) */
static void pg_hook(void) {
    typedef void *(__cdecl *PFN_Get)(void);
    BYTE *sc = (BYTE *)GetModuleHandleA("SIMCITY.DLL"), *svc;
    DWORD *vt, old;
    if (g_pg_hooked || !sc) return;
    g_pg_hooked = 1;
    __try {
        svc = (BYTE *)((PFN_Get)(sc + 0xedff))();
        if (!svc || IsBadReadPtr(svc, 4)) { logf("PROGRESS> no progress service, box stays"); return; }
        vt = *(DWORD **)svc;
        if (IsBadReadPtr(vt, 0x94) || !VirtualProtect(&vt[0x88 / 4], 12, PAGE_READWRITE, &old)) {
            logf("PROGRESS> vtable 0x%08lX not writable, box stays", (DWORD)vt); return;
        }
        g_pg_open  = (PFN_PgOpen)vt[0x88 / 4];
        g_pg_step  = (PFN_PgStep)vt[0x8c / 4];
        g_pg_close = (PFN_PgClose)vt[0x90 / 4];
        vt[0x88 / 4] = (DWORD)pg_open;
        vt[0x8c / 4] = (DWORD)pg_step;
        vt[0x90 / 4] = (DWORD)pg_close;
        logf("PROGRESS> service 0x%08lX vtable 0x%08lX: open/step/close wrapped (were 0x%08lX 0x%08lX 0x%08lX)",
             (DWORD)svc, (DWORD)vt, (DWORD)g_pg_open, (DWORD)g_pg_step, (DWORD)g_pg_close);
    } __except (EXCEPTION_EXECUTE_HANDLER) { logf("PROGRESS> hook threw 0x%08lX, box stays", GetExceptionCode()); }
}

/* returns NULL if the save can run now, else the reason it is put off */
static const char *why_not(BYTE *city) {
    if (!city) return "no city";
    if (GetTickCount() - g_seen_at < 20000) return "city just loaded";
    if (g_stall_at && GetTickCount() - g_stall_at < 20000) return "game thread was busy (a load)";
    if (city_lock(city) != 0) return "city locked (the game is saving)";
    if (GetCapture()) return "mouse captured";
    if (GetAsyncKeyState(VK_LBUTTON) < 0 || GetAsyncKeyState(VK_RBUTTON) < 0 || GetAsyncKeyState(VK_MBUTTON) < 0)
        return "mouse button held";
    if (text_focus()) return "text field has focus";
    return NULL;
}

static void autosave_now(void) {
    BYTE *city = city_get();
    const char *why = why_not(city);
    char stem[MAX_PATH], target[MAX_PATH], tmp[MAX_PATH];
    unsigned __int64 h, hp;
    DWORD sz, szp, t0 = GetTickCount();
    int ok;
    if (city != g_post_city) { logf("SAVE> message was for another city, dropped"); return; }
    if (GetTickCount() - g_last_save < g_interval_ms) return;           /* a save already ran since it was posted */
    if (why) {
        if (!g_skips_logged++) logf("SAVE> put off: %s", why);
        return;
    }
    if (g_fault_stop) return;
    {   DWORD fr = mem_largest_free_mb();
        _snprintf(g_mem_note, sizeof(g_mem_note), "largest free block %lu MB before the save", fr);
        g_mem_note[sizeof(g_mem_note) - 1] = 0;
        if (g_min_free_mb && fr < g_min_free_mb) {
            logf("SAVE> skipped: largest free address block %lu MB < %lu MB (the game is close to running out of "
                 "address space, a save now would fault). Save by hand and restart the game", fr, g_min_free_mb);
            g_last_save = GetTickCount();
            return;
        }
    }
    name_save(city);
    if (g_name_len < 0) { logf("SAVE> city name unreadable, skipped"); g_last_save = GetTickCount(); return; }
    target_stem(stem, sizeof(stem));
    slot_path(target, sizeof(target), stem, 0);
    /* the Save command appends ".sc3" to a path that does not end in it, so the temp name ends in .sc3 too */
    _snprintf(tmp, sizeof(tmp), "%s (auto).tmp.sc3", stem); tmp[sizeof(tmp) - 1] = 0;
    DeleteFileA(tmp);
    pg_hook();
    g_pg_total = g_pg_cur = 0;
    ind_show();
    g_autosaving = 1;
    ok = game_save(city, tmp);
    g_autosaving = 0;
    {   /* test only: SC3AUTOSAVE_HOLD=<ms> holds the game thread with the indicator up, so a screen grab can catch it */
        char v[16];
        if (GetEnvironmentVariableA("SC3AUTOSAVE_HOLD", v, sizeof(v)) && atoi(v) > 0) Sleep((DWORD)atoi(v));
    }
    ind_done(ok);
    name_restore(city);
    {   /* check the restore: the city must still point at the player's own file */
        char want[MAX_PATH];
        int wl = g_name_len;
        lstrcpynA(want, g_name, sizeof(want));
        name_save(city);
        if (g_name_len != wl || strcmp(g_name, want)) logf("SAVE> city name NOT restored: '%s' (wanted '%s')", g_name, want);
        g_name_len = wl;
        lstrcpynA(g_name, want, sizeof(g_name));
    }
    g_last_save = GetTickCount();
    g_skips_logged = 0;
    if (!ok || !file_hash(tmp, &h, &sz) || !sz) {
        logf("SAVE> FAILED (command %d) to %s, %lu ms", ok, tmp, GetTickCount() - t0);
        DeleteFileA(tmp);
        return;
    }
    if (file_hash(target, &hp, &szp) && hp == h && szp == sz) {
        DeleteFileA(tmp);
        logf("SAVE> unchanged since %s, dropped (%lu B, %lu ms)", target, sz, GetTickCount() - t0);
        return;
    }
    rotate(stem);
    if (!move_over(tmp, target)) {
        DeleteFileA(tmp);
        return;
    }
    g_saves++;
    logf("SAVE> #%d %s, %lu B, %lu ms (city name kept: '%s')", g_saves, target, sz, GetTickCount() - t0,
         g_name_len > 0 ? g_name : "");
}

/* UNAUTO (owner 2026-10-28: "if i open an auto save file when i save it at the end of my session it should NOT save
 * with the auto save name"). The game's Save writes to the city's file name, which is the path it was loaded from. When
 * that is an autosave ("<city> (auto 5 min).sc3", or "<city>.autosaveN.sc3" from the builds before 10-28b), the name
 * is set to "<city>.sc3" in the same folder once the load is over (city vt+0x258, as name_restore), so Save goes to
 * the player's own file. Autosaves keep going to the "<city> (auto ...)" files (target_stem strips the suffix anyway).
 * SC3AUTOSAVE_UNAUTO=0 keeps the loaded name; so does autosave.ini [autosave] unauto=0 (the mods page checkbox). */
static void unauto_name(void) {
    BYTE *city = city_get();
    char *slash, *cut, want[MAX_PATH];
    if (!city || city_lock(city) != 0) return;
    name_save(city);
    if (g_name_len <= 0) return;
    slash = strrchr(g_name, '\\');
    if (!slash) slash = strrchr(g_name, '/');
    slash = slash ? slash + 1 : g_name;
    if ((cut = strstr(slash, " (auto ")) == NULL && (cut = strstr(slash, ".autosave")) == NULL) return;
    lstrcpynA(want, g_name, sizeof(want));
    _snprintf(want + (cut - g_name), sizeof(want) - (cut - g_name), ".sc3");
    want[sizeof(want) - 1] = 0;
    logf("UNAUTO> loaded autosave '%s': Save now goes to '%s'", g_name, want);
    lstrcpynA(g_name, want, sizeof(g_name));
    g_name_len = (int)strlen(g_name);
    name_restore(city);
    name_save(city);
    if (strcmp(g_name, want)) logf("UNAUTO> name NOT changed: '%s'", g_name);
}

static LRESULT CALLBACK as_wndproc(HWND h, UINT m, WPARAM wp, LPARAM lp) {
    if (m == WM_AUTOSAVE) {
        DWORD waited = GetTickCount() - g_post_at;
        if (waited > 5000) {                               /* the game thread did not pump messages for > 5 s */
            g_stall_at = GetTickCount();
            logf("SAVE> message waited %lu ms in the queue (game thread busy), waiting 20 s more", waited);
        }
        InterlockedExchange(&g_posted, 0);
        if (g_diag) {
            BYTE *c = city_get();
            const char *w = why_not(c);
            char tag[160];
            _snprintf(tag, sizeof(tag), "WM_AUTOSAVE city 0x%08lX lock %ld pgdepth %ld seen %lu ms ago -> %s", (DWORD)c,
                      c ? city_lock(c) : -1, g_pg_depth, GetTickCount() - g_seen_at, w ? w : "SAVE");
            tag[sizeof(tag) - 1] = 0;
            diag_stack(tag);
        }
        if (InterlockedExchange(&g_busy, 1)) return 0;     /* a nested message loop inside a save: never re-enter */
        autosave_now();
        InterlockedExchange(&g_busy, 0);
        return 0;
    }
    if (m == WM_AS_HOOK) { pg_hook(); return 0; }
    if (m == WM_AS_UNAUTO) { if (!g_busy) unauto_name(); return 0; }
    if ((m >= WM_MOUSEFIRST && m <= WM_MOUSELAST) || (m >= WM_KEYFIRST && m <= WM_KEYLAST)) g_last_input = GetTickCount();
    return CallWindowProcA(g_oldproc, h, m, wp, lp);
}

static BOOL CALLBACK find_game_window(HWND h, LPARAM p) {
    DWORD pid = 0;
    char cls[32];
    GetWindowThreadProcessId(h, &pid);
    if (pid != GetCurrentProcessId()) return TRUE;
    if (!GetClassNameA(h, cls, sizeof(cls)) || lstrcmpA(cls, "Gonzo")) return TRUE;
    *(HWND *)p = h;
    return FALSE;
}

static DWORD WINAPI watcher(LPVOID unused) {
    HWND h = NULL;
    (void)unused;
    while (!h) { Sleep(50); EnumWindows(find_game_window, (LPARAM)&h); }
    Sleep(500);                                       /* let the other mods subclass first; chaining works either way */
    g_hwnd = h;
    /* the old proc must be known BEFORE the swap (sc3undo: a message can arrive between the two calls) */
    g_oldproc = (WNDPROC)GetWindowLongA(h, GWL_WNDPROC);
    {   WNDPROC prev = (WNDPROC)SetWindowLongA(h, GWL_WNDPROC, (LONG)as_wndproc);
        if (prev && prev != g_oldproc) g_oldproc = prev; }
    CloseHandle(CreateThread(NULL, 0, ind_thread, NULL, 0, NULL));   /* always: the indicator can be turned on later */
    logf("### window 0x%08lX subclassed, every %lu s, B/C ages %lu / %lu s%s%s", (DWORD)h, g_interval_ms / 1000,
         g_tier_b, g_tier_c, g_cfg_dir[0] ? ", dir " : "", g_cfg_dir);
    for (;;) {
        BYTE *city;
        Sleep(1000);
        {   /* MODSPAGE (sc3resize Preferencias -> Opciones de mods) writes autosave.ini: re-read it when it changes */
            static FILETIME seen;            /* zero = no file */
            static int first = 1;
            char ip[MAX_PATH];
            WIN32_FILE_ATTRIBUTE_DATA a;
            self_path(ip, sizeof(ip), "autosave.ini");
            if (GetFileAttributesExA(ip, GetFileExInfoStandard, &a) && CompareFileTime(&a.ftLastWriteTime, &seen)) {
                int was_first = first;
                seen = a.ftLastWriteTime;
                first = 0;
                if (!was_first) {   /* the first look only records the time: DllMain already read the file */
                    ini_read();
                    g_skips_logged = 0;
                    logf("INI> autosave.ini changed: enabled=%d every %lu s, indicator %d, unauto %d", g_enabled,
                         g_interval_ms / 1000, g_indicator, g_unauto);
                }
            }
            first = 0;   /* no file at the first look: one created later is a change */
        }
        if (!IsWindow(h)) return 0;
        city = city_get();
        if (city != g_seen_city) {                    /* new / loaded / closed city: the interval starts again */
            g_seen_city = city;
            g_seen_at = g_last_save = GetTickCount();
            g_skips_logged = 0;
            g_post_city = NULL;                       /* a queued message for the old city is dropped by the handler */
            g_wait_unlock = city != NULL;
            logf("CITY> %s 0x%08lX", city ? "city" : "no city", (DWORD)city);
            if (city && !g_pg_hooked) PostMessageA(h, WM_AS_HOOK, 0, 0);
            continue;
        }
        /* the interval of a new city starts when its lock counter is first 0 (the load holds it), not at the pointer */
        if (g_wait_unlock && city) {
            long lk = city_lock(city);
            g_seen_at = g_last_save = GetTickCount();
            if (lk == 0) {
                g_wait_unlock = 0;
                logf("CITY> lock 0, interval starts");
                if (g_unauto) PostMessageA(h, WM_AS_UNAUTO, 0, 0);   /* UNAUTO, on the game thread */
            }
            continue;
        }
        if (!city || g_busy || !g_enabled || g_fault_stop) continue;
        {   DWORD now = GetTickCount(), since = now - g_last_save;
            if (since < g_interval_ms) continue;
            /* due: wait for idle_seconds without input, or save anyway one more interval later */
            if (now - g_last_input < g_idle_ms && since < 2 * g_interval_ms) {
                if (!g_skips_logged++) logf("SAVE> due, waiting for %lu s without input", g_idle_ms / 1000);
                continue;
            }
            if (InterlockedCompareExchange(&g_posted, 1, 0) == 0) {
                g_post_city = city;
                g_post_at = now;
                if (!PostMessageA(h, WM_AUTOSAVE, 0, 0)) InterlockedExchange(&g_posted, 0);
            }
        }
    }
}

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        char path[MAX_PATH];
        if (!sc3mods_guard(inst, "sc3autosave")) return TRUE;   /* not our loader: stay inert (sc3mods_guard.h) */
        g_self = (HMODULE)inst;
        DisableThreadLibraryCalls(inst);
        InitializeCriticalSection(&g_lock);
        QueryPerformanceFrequency(&g_freq);
        QueryPerformanceCounter(&g_t0);
        g_exe = (BYTE *)GetModuleHandleA(NULL);
        if (!GetEnvironmentVariableA("SC3AUTOSAVE_LOG", path, sizeof(path))) self_path(path, sizeof(path), "sc3autosave.log");
        g_log = CreateFileA(path, GENERIC_WRITE, FILE_SHARE_READ, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        ini_read();
        g_diag = GetEnvironmentVariableA("SC3AUTOSAVE_DIAG", NULL, 0) != 0;
        logf("### sc3autosave loaded, enabled=%d", g_enabled);
        /* enabled=0 still starts the watcher: Preferencias can turn autosave on without a restart */
        CreateThread(NULL, 0, watcher, NULL, 0, NULL);
    }
    return TRUE;
}
