/* sc3netmod.c - runtime support for NEW network piece variants (netmod suite, task netvariant 2026-10-13).
 *
 * A variant is a new piece id that clones a stock piece's behaviour with new art (re/analysis/NEW_PIECE.md:
 * id 20029 = blue copy of road straight 29, placed by the ROAD tiler from the Korea DBSegments containers).
 * Pure data gives it everything except what SIMNTWRK decides by comparing the piece id against fixed lists.
 * Each variant declares a BASE id (manifest.json "base", installed as Apps\Res\netmod_variants.txt, one
 * "<variant> <base>" pair per line). This DLL does two things with that table:
 *
 * 1. CROSS (SC3NETMOD_CROSS=0 turns it off). The id checks that decide crossings see the base id, so rail and
 *    power lines cross a variant exactly as they cross its base. The crossing tile becomes the stock crossing
 *    piece (69 rail, 67 power over road 29): the variant look is lost on that one tile, as it is for the base.
 *    Two levers: the crossing switch's id lookup (g_cross_sites) returns the base, and the two piece-id getters
 *    return the base only while one of the 15 predicates in g_preds runs (the "may X cross this cell" id lists
 *    that the path planner and FUN_1001547b ask). Everything else (art, tiler, decorations, save, query) still
 *    sees the variant id. Evidence per site: re/analysis/NETVARIANT.md.
 *
 * 2. SAVEBASE (SC3NETMOD_SAVEBASE=0 turns the save side off). The saved tile words carry the BASE id, so a
 *    stock game (no mod) loads the city with stock pieces instead of dropping the tiles. The variant ids are
 *    kept in one extra network-layer section, key {0x206c6e7c, 0x2147c2dd, instance 0x4E56}, written with the
 *    game's own section writer next to the stock instances 0..3. The stock loader reads instances 0..3 by key
 *    and never asks for 0x4E56 (SIMNTWRK FUN_100130e9). With this DLL the loader reads that section first and
 *    puts each variant id back into the tile word before the piece is created (exact match on word0 + word1).
 *    The load side is always on: it only acts on files that carry the section.
 *
 * Hooks (SIMNTWRK.DLL, all relative to the module base, all checked against the shipped bytes first):
 *   +0x16821  call FUN_1001a93d in FUN_100167d4 (crossing)            -> id_base_thunk     (CROSS)
 *   +0x0c2fc  FUN_1000c2fc piece vt+0x5c getter, +0x0cc83 FUN_1000cc83 vt+0x30 getter -> scoped map (CROSS)
 *   15 predicate vtables, slot +0xc (g_preds)                         -> pred_wrapN        (CROSS)
 *   +0x13082  call FUN_1000d688 in FUN_10012fc3 (write one tile)      -> save_rec_thunk    (SAVEBASE)
 *   +0x12e3e  mov eax,0x2147c2dd in FUN_10012dff (save start)         -> save_begin_hook   (SAVEBASE)
 *   +0x12ee0  push ebx/push 4/sub esp,0xc in FUN_10012dff (3 nets out)-> save_end_hook     (SAVEBASE)
 *   +0x130e9  mov eax,<eh> in FUN_100130e9 (load entry)               -> load_begin_hook
 *   +0x13264/+0x13338/+0x1340b  call FUN_1000d6b3 (read one tile)     -> load_rec_thunk
 *
 * 4. RAMPS (task netramp, SC3NETMOD_RAMPS=0 turns it off): `ramp` lines of the same table files change the hardcoded
 *    on-ramp / tunnel / slope piece tables; variants they place classify as their base. See the NETRAMP block.
 * 3. OVERLAY (task netpack, SC3NETMOD_OVERLAY=0 turns it off). Files under <root>\mods\netmod\overlay\ are served in
 *    place of <root>\<same path> (read-only opens, existence checks, merged directory listings), so netpack packages
 *    install without writing to Apps\. Variant tables come from every <root>\mods\netmod\tables\*.txt (one per pack),
 *    then Apps\Res\netmod_variants.txt. Details at overlay_init and table_load; evidence in re/analysis/NETPACK.md.
 * 4. INHERIT + XCROSS (task netbridge, sc3netmod_bridge.c): highway / removal id reads see the base, and crossing art
 *    for variants from <root>\mods
etmod\cross\*.txt. SC3NETMOD_INHERIT=0 / SC3NETMOD_XCROSS=0 turn them off.
 * 5. RBT (task roundabout3, sc3netmod_rbt.c): automatic 2x2 roundabouts from `rbt` table lines, after every road
 *    retile (FUN_1001547b entry) and after a city load. SC3NETMOD_RBT=0 / SC3NETMOD_RBT_LOAD=0 turn it off.
 * 6. DAV (task diagave, sc3netmod_dav.c): automatic diagonal avenues from `dav` table lines, on RBT's two hooks: two
 *    diagonal drags side by side get a median. SC3NETMOD_DAV=0 turns it off.
 * Env: SC3NETMOD_LOG=<path> (default sc3netmod.log beside the DLL), SC3NETMOD_TABLE=<path> (variant table, only that
 * file), SC3NETMOD_FILELOG=1 (log every hooked file call under Apps\Res).
 */

#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <ctype.h>
#include <intrin.h>
#pragma intrinsic(_ReturnAddress)

/* ============================================================ logging */

static CRITICAL_SECTION g_lock;
static HANDLE g_log = INVALID_HANDLE_VALUE;
static LARGE_INTEGER g_freq, g_t0;
static HMODULE g_self;

static void logf(const char *fmt, ...) {
    char buf[1024];
    char line[1152];
    va_list ap;
    LARGE_INTEGER now;
    double ms;
    DWORD wrote;
    int n;

    va_start(ap, fmt);
    _vsnprintf(buf, sizeof(buf) - 1, fmt, ap);
    buf[sizeof(buf) - 1] = 0;
    va_end(ap);
    QueryPerformanceCounter(&now);
    ms = (double)(now.QuadPart - g_t0.QuadPart) * 1000.0 / (double)g_freq.QuadPart;
    n = _snprintf(line, sizeof(line) - 1, "[%9.3f ms][tid %04lx] %s\r\n", ms, GetCurrentThreadId(), buf);
    if (n < 0) return;
    line[sizeof(line) - 1] = 0;
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

static int env_off(const char *name) {
    char v[8];
    return GetEnvironmentVariableA(name, v, sizeof(v)) && v[0] == '0';
}

/* ============================================================ the variant table */

static WORD g_base[65536];          /* g_base[variant] = base id, 0 = not a variant */
static BYTE g_conflict[65536];      /* two tables gave this variant different bases: dropped */
static int  g_nvariants;

static char g_root[MAX_PATH];       /* game root with a trailing '\' (parent of the folder holding SC3U.exe) */
static int  g_rootlen;

/* <exe dir>\..\ -> g_root. Works for the dev layout and the release layout (both keep SC3U.exe in Apps). */
static void root_init(void) {
    char *s;
    if (!GetModuleFileNameA(NULL, g_root, sizeof(g_root))) { g_root[0] = 0; return; }
    if ((s = strrchr(g_root, '\\')) != NULL) *s = 0;          /* strip SC3U.exe */
    if ((s = strrchr(g_root, '\\')) != NULL) s[1] = 0;        /* strip Apps, keep the slash */
    else g_root[0] = 0;
    g_rootlen = lstrlenA(g_root);
}

/* One table file: "<variant> <base>" per line, '#'/';' comments. A variant declared twice with different bases
   (two packs disagree) is dropped, so neither pack's base is applied by accident. */
static int table_read(const char *path) {
    char line[256];
    int n = 0;
    FILE *f = fopen(path, "r");
    if (!f) return -1;
    while (fgets(line, sizeof(line), f)) {
        unsigned long v, b;
        char *p = line;
        while (*p == ' ' || *p == '\t') p++;
        if (*p == '#' || *p == ';' || *p == '\r' || *p == '\n' || !*p) continue;
        if (!strncmp(p, "ramp ", 5)) continue;                 /* NETRAMP lines, read by netramp_install */
        if (!strncmp(p, "rbt ", 4)) continue;                  /* RBT lines, read by rbt_install */
        if (!strncmp(p, "dav ", 4) || !strncmp(p, "davj ", 5) || !strncmp(p, "davm ", 5) || !strncmp(p, "davs ", 5) ||
            !strncmp(p, "davx", 4))                    /* task diagx: davx / davxg / davxw */
            continue;                                    /* DAV lines, read by rbt_install (task diagave) */
        if (p[0] == 't' && (!strncmp(p, "tmpl ", 5) || !strncmp(p, "tori ", 5) || !strncmp(p, "tcel ", 5) ||
                            !strncmp(p, "tedg ", 5) || !strncmp(p, "tend", 4))) continue;   /* TMPL lines */
        if (sscanf(p, "%lu %lu", &v, &b) != 2 || v == 0 || v > 0xffff || b == 0 || b > 0xffff || v == b) {
            logf("table: %s: bad line '%s'", path, p);
            continue;
        }
        if (g_conflict[v]) continue;
        if (g_base[v] && g_base[v] != (WORD)b) {
            logf("### table: %s: variant %lu -> base %lu, but an earlier table said base %u - variant DROPPED",
                 path, v, b, g_base[v]);
            g_conflict[v] = 1; g_base[v] = 0; g_nvariants--;
            continue;
        }
        if (!g_base[v]) g_nvariants++;
        g_base[v] = (WORD)b;
        n++;
        logf("table: %s: variant %lu -> base %lu", path, v, b);
    }
    fclose(f);
    return n;
}

/* Sources, in order (task netpack 2026-10-13):
   1. SC3NETMOD_TABLE=<path>: that file only (tests).
   2. every <root>\mods\netmod\tables\*.txt, name order: one per installed netpack package (netpack.py install).
   3. Apps\Res\netmod_variants.txt: the single-mod table newpiece.py installs (kept for old installs). */
static void table_load(void) {
    char path[MAX_PATH], pat[MAX_PATH], *slash;
    WIN32_FIND_DATAA fd;
    HANDLE h;
    int n, nfiles = 0;
    if (GetEnvironmentVariableA("SC3NETMOD_TABLE", path, sizeof(path))) {
        n = table_read(path);
        logf("table: SC3NETMOD_TABLE %s: %s", path, n < 0 ? "not found" : "read");
        logf("table: %d variant(s)", g_nvariants);
        return;
    }
    if (g_rootlen) {
        /* FindFirstFileA here is kernel32's own: this module's IAT is never hooked (ov_hook_all skips g_self). */
        _snprintf(pat, sizeof(pat), "%smods\\netmod\\tables\\*.txt", g_root);
        pat[sizeof(pat) - 1] = 0;
        h = FindFirstFileA(pat, &fd);
        if (h != INVALID_HANDLE_VALUE) {
            char names[64][MAX_PATH];
            int k, j, cnt = 0;
            do {
                if (!(fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) && cnt < 64) lstrcpynA(names[cnt++], fd.cFileName, MAX_PATH);
            } while (FindNextFileA(h, &fd));
            FindClose(h);
            for (k = 1; k < cnt; k++)                     /* name order, so the result does not depend on the FS */
                for (j = k; j > 0 && lstrcmpiA(names[j - 1], names[j]) > 0; j--) {
                    char t[MAX_PATH]; lstrcpyA(t, names[j]); lstrcpyA(names[j], names[j - 1]); lstrcpyA(names[j - 1], t);
                }
            for (k = 0; k < cnt; k++) {
                _snprintf(path, sizeof(path), "%smods\\netmod\\tables\\%s", g_root, names[k]);
                path[sizeof(path) - 1] = 0;
                if (table_read(path) >= 0) nfiles++;
            }
        }
    }
    /* Apps\SC3U.exe -> Apps\Res\netmod_variants.txt (newpiece.py's single-mod install) */
    if (GetModuleFileNameA(NULL, path, sizeof(path)) && (slash = strrchr(path, '\\')) != NULL) {
        slash[1] = 0;
        lstrcatA(path, "Res\\netmod_variants.txt");
        if (table_read(path) >= 0) nfiles++;
    }
    logf("table: %d table file(s), %d variant(s)", nfiles, g_nvariants);
}

/* ============================================================ patch helpers */

static int write_code(BYTE *p, const void *src, int n) {
    DWORD old;
    if (!VirtualProtect(p, n, PAGE_EXECUTE_READWRITE, &old)) return 0;
    memcpy(p, src, n);
    VirtualProtect(p, n, old, &old);
    FlushInstructionCache(GetCurrentProcess(), p, n);
    return 1;
}

static int write_rel(BYTE *at, BYTE op, void *to, int len) {
    BYTE b[16];
    int i;
    if (len < 5 || len > 16) return 0;
    b[0] = op;
    *(DWORD *)(b + 1) = (DWORD)to - (DWORD)(at + 5);
    for (i = 5; i < len; i++) b[i] = 0x90;
    return write_code(at, b, len);
}

/* Redirect an existing `call rel32` at m+rva whose target is m+want. Returns the old absolute target. */
static DWORD retarget_call(BYTE *m, DWORD rva, DWORD want, void *to) {
    BYTE *p = m + rva;
    DWORD tgt;
    if (IsBadReadPtr(p, 5) || p[0] != 0xE8) return 0;
    tgt = (DWORD)(p + 5) + *(DWORD *)(p + 1);
    if (tgt != (DWORD)m + want) return 0;
    return write_rel(p, 0xE8, to, 5) ? tgt : 0;
}

static int bytes_are(BYTE *p, const BYTE *want, int n) {
    return !IsBadReadPtr(p, n) && !memcmp(p, want, n);
}

/* ============================================================ 1. CROSS: id lookups see the base */

static DWORD g_a93d;                 /* SIMNTWRK FUN_1001a93d: __stdcall-like (occupant) -> piece id, ret 4 */
static volatile LONG g_n_cross_map;

static DWORD __stdcall id_base(DWORD id) {
    if (id < 65536 && g_base[id]) { InterlockedIncrement(&g_n_cross_map); return g_base[id]; }
    return id;
}

/* Replaces `call FUN_1001a93d` (push occ; call) at a crossing site: same contract, returns the base id. */
static __declspec(naked) void id_base_thunk(void) {
    __asm {
        push dword ptr [esp + 4]
        call dword ptr [g_a93d]
        push eax
        call id_base
        ret 4
    }
}

/* SIMNTWRK call sites of FUN_1001a93d that ask "which piece is this" to decide a crossing or connection.
   Filled from the inventory in re/analysis/NETVARIANT.md; each is verified to be a call to 0x1001a93d. */
static const DWORD g_cross_sites[] = {
    0x16821,        /* FUN_100167d4: crossing switch on {0x49,0xe,0xf,0x1d,0x2c,0x5c,0x2bc4,0x3acb} */
};

/* ---- scoped mapping: the piece-id getters report the base only while a wrapped predicate runs ----
   Every network piece class shares primary vt+0x30 = FUN_1000cc83 (`[this+0x18] & 0xffff`) and primary vt+0x5c =
   FUN_1000c2fc (`[this+0x18] & mask`; the secondary vt+0x5c FUN_1000d6fd is `sub ecx,4; jmp 0x1000c2fc`).
   Both getters are hooked; they map a variant id to its base only when the calling thread is inside one of the
   predicates in g_preds (vtable slot +0xc swapped to a wrapper). Outside that scope they return the raw id. */
static volatile LONG g_scope_any;    /* wrappers active on any thread */
static DWORD g_tls = TLS_OUT_OF_INDEXES;
static volatile LONG g_n_pred_map;

static void __stdcall scope_enter(void) {
    InterlockedIncrement(&g_scope_any);
    TlsSetValue(g_tls, (void *)((DWORD)TlsGetValue(g_tls) + 1));
}

static void __stdcall scope_leave(void) {
    TlsSetValue(g_tls, (void *)((DWORD)TlsGetValue(g_tls) - 1));
    InterlockedDecrement(&g_scope_any);
}

/* r = [piece+0x18] & mask. Maps only a full 16-bit id read inside a scope on this thread. */
static DWORD __stdcall map_masked(DWORD r, DWORD mask) {
    DWORD id;
    if ((mask & 0xffff) != 0xffff || !TlsGetValue(g_tls)) return r;
    id = r & 0xffff;
    if (!g_base[id]) return r;
    InterlockedIncrement(&g_n_pred_map);
    return (r & 0xffff0000) | g_base[id];
}

static __declspec(naked) void get5c_hook(void) {      /* replaces FUN_1000c2fc, ret 4 */
    __asm {
        mov eax, dword ptr [ecx + 0x18]
        and eax, dword ptr [esp + 4]
        cmp dword ptr [g_scope_any], 0
        jne slow
        ret 4
    slow:
        push dword ptr [esp + 4]
        push eax
        call map_masked
        ret 4
    }
}

static __declspec(naked) void get30_hook(void) {      /* replaces FUN_1000cc83, ret */
    __asm {
        mov eax, dword ptr [ecx + 0x18]
        and eax, 0xffff
        cmp dword ptr [g_scope_any], 0
        jne slow
        ret
    slow:
        push 0xffff
        push eax
        call map_masked
        ret
    }
}

/* Predicates: objects with a 5-slot vtable, slot +0xc = test(occupant) -> al, `ret 4` (ecx = predicate object).
   Built by SIMNTWRK FUN_10010dff into DAT_100323c0..; which ones are wrapped and why: re/analysis/NETVARIANT.md. */
typedef struct { DWORD vt, fn; const char *what; } Pred;
static const Pred g_preds[] = {
    /* per-network "may this network cross / take over this cell" id lists (FUN_1001547b passes them to the crossing
       FUN_100167d4, FUN_100165d8 and the rule check FUN_10016327) */
    { 0x2c608, 0x1ab26, "FUN_1001ab26 road  id list (DAT_10032400, idx 0x0a)" },
    { 0x2c5f4, 0x1ac2b, "FUN_1001ac2b rail  id list (DAT_10032404, idx 0x0c)" },
    { 0x2c5cc, 0x1abb2, "FUN_1001abb2 power id list (DAT_10032408, idx 0x0f)" },
    { 0x2c5e0, 0x1acbe, "FUN_1001acbe hway  id list (DAT_1003240c, idx 0x0b)" },
    /* flag-or-{0xe,0xf} tests (idx 0x1c..0x1e) */
    { 0x2c590, 0x1ad60, "FUN_1001ad60 flags 0x8800 or id 0xe/0xf (DAT_10032418)" },
    { 0x2c57c, 0x1ade7, "FUN_1001ade7 flags 0x20800 or id 0xe/0xf (DAT_1003241c)" },
    { 0x2c568, 0x1ae36, "FUN_1001ae36 flags 0x10800 or id 0xe/0xf (DAT_10032424)" },
    /* rotation-aware id lists handed to other DLLs through manager vt+0x54 (idx 0x10..0x1b); the rail drag asks
       FUN_1001af19 for every cell of its path (live trace 2026-10-13) */
    { 0x2c518, 0x1ae85, "FUN_1001ae85 rotation list (DAT_10032430, idx 0x10)" },
    { 0x2c4f0, 0x1afc7, "FUN_1001afc7 rotation list (DAT_1003243c, idx 0x11)" },
    { 0x2c504, 0x1af19, "FUN_1001af19 rotation list (DAT_10032434, idx 0x12)" },
    { 0x2c4dc, 0x1b07c, "FUN_1001b07c rotation list (DAT_10032438, idx 0x15)" },
    { 0x2c4a0, 0x1b10c, "FUN_1001b10c rotation list (DAT_10032448, idx 0x16)" },
    { 0x2c478, 0x1b248, "FUN_1001b248 rotation list (DAT_10032454, idx 0x17)" },
    { 0x2c48c, 0x1b1a1, "FUN_1001b1a1 rotation list (DAT_1003244c, idx 0x18)" },
    { 0x2c464, 0x1b2e0, "FUN_1001b2e0 rotation list (DAT_10032450, idx 0x1b)" },
    /* NOT wrapped: FUN_1001b378 / FUN_1001b3c4 (decoration pick, FUN_1000de17): a variant must not be swapped for
       the base's random decoration pieces 0x3ac0..0x3ac2 */
};
#define NPRED (sizeof(g_preds) / sizeof(g_preds[0]))
static DWORD g_porig[16];

#define PRED_WRAP(i) \
    static __declspec(naked) void pred_wrap##i(void) { \
        __asm push ecx \
        __asm call scope_enter \
        __asm pop ecx \
        __asm push dword ptr [esp + 4] \
        __asm call dword ptr [g_porig + i * 4] \
        __asm push eax \
        __asm call scope_leave \
        __asm pop eax \
        __asm ret 4 \
    }
PRED_WRAP(0) PRED_WRAP(1) PRED_WRAP(2) PRED_WRAP(3) PRED_WRAP(4) PRED_WRAP(5) PRED_WRAP(6) PRED_WRAP(7)
PRED_WRAP(8) PRED_WRAP(9) PRED_WRAP(10) PRED_WRAP(11) PRED_WRAP(12) PRED_WRAP(13) PRED_WRAP(14) PRED_WRAP(15)
static void *g_pwrap[16] = { pred_wrap0, pred_wrap1, pred_wrap2, pred_wrap3, pred_wrap4, pred_wrap5, pred_wrap6,
    pred_wrap7, pred_wrap8, pred_wrap9, pred_wrap10, pred_wrap11, pred_wrap12, pred_wrap13, pred_wrap14, pred_wrap15 };

static int patch_getters(BYTE *m) {
    static const BYTE g5c[] = { 0x8b, 0x41, 0x18, 0x23, 0x44, 0x24, 0x04, 0xc2, 0x04, 0x00 };
    static const BYTE g30[] = { 0x8b, 0x41, 0x18, 0x25, 0xff, 0xff, 0x00, 0x00, 0xc3 };
    if (!bytes_are(m + 0xc2fc, g5c, sizeof(g5c)) || !bytes_are(m + 0xcc83, g30, sizeof(g30))) {
        logf("### CROSS: id getters differ from shipped - predicates NOT wrapped");
        return 0;
    }
    return write_rel(m + 0xc2fc, 0xE9, (void *)get5c_hook, 5) && write_rel(m + 0xcc83, 0xE9, (void *)get30_hook, 5);
}

static int patch_preds(BYTE *m) {
    int i, ok = 0;
    for (i = 0; i < (int)NPRED && i < 16; i++) {
        DWORD *slot = (DWORD *)(m + g_preds[i].vt + 0xc), want = (DWORD)m + g_preds[i].fn, nv = (DWORD)g_pwrap[i];
        if (IsBadReadPtr(slot, 4) || *slot != want) {
            logf("### CROSS: predicate vtable +0x%05lX slot +0xc != FUN at +0x%05lX - skipped", g_preds[i].vt, g_preds[i].fn);
            continue;
        }
        g_porig[i] = want;
        if (write_code((BYTE *)slot, &nv, 4)) { ok++; logf("CROSS: wrapped %s", g_preds[i].what); }
    }
    return ok;
}

static int patch_cross(BYTE *m) {
    int i, ok = 0;
    for (i = 0; i < (int)(sizeof(g_cross_sites) / sizeof(g_cross_sites[0])); i++) {
        DWORD old = retarget_call(m, g_cross_sites[i], 0x1a93d, (void *)id_base_thunk);
        if (old) { g_a93d = old; ok++; }
        else logf("### CROSS: site +0x%05lX is not `call FUN_1001a93d` - skipped", g_cross_sites[i]);
    }
    g_tls = TlsAlloc();
    if (g_tls != TLS_OUT_OF_INDEXES && patch_getters(m)) ok += patch_preds(m);
    return ok;
}

/* ============================================================ 2. SAVEBASE: save words carry the base */

#define NV_TYPE   0x206c6e7cUL       /* the network layer's section type */
#define NV_GROUP  0x2147c2ddUL       /* the network layer's section group (SIMNTWRK FUN_10012dff) */
#define NV_INST   0x4E56UL           /* ours; stock uses instances 0..3 */
#define NV_MAGIC  0x3152564EUL       /* "NVR1" */

typedef struct { DWORD w0, w1, id; } NvRec;   /* w1 = the word as saved (base id), id = the variant id */

static NvRec *g_sv;                  /* collected during one save */
static int g_nsv, g_capsv;
static NvRec *g_ld;                  /* read at load entry, open-addressed on w0 */
static int g_capld, g_nld, g_nld_hit;
static int g_savebase = 1;
static volatile LONG g_n_saved_base;

/* SIMNTWRK framework helpers (the same frame/section objects FUN_10012dff and FUN_100130e9 use) */
typedef void *(__fastcall *PFN_WOpen)(void *frame, void *edx, void *p1, void *p2, DWORD t, DWORD g, DWORD i,
                                      DWORD ver, DWORD flags);           /* FUN_10026129, ret 0x1c */
typedef void *(__fastcall *PFN_ROpen)(void *frame, void *edx, void *p1, void *p2, DWORD t, DWORD g, DWORD i);
                                                                         /* FUN_10025f0d, ret 0x14 */
typedef void *(__fastcall *PFN_Stream)(void *frame);                     /* FUN_100262a3 */
typedef void  (__fastcall *PFN_Close)(void *frame);                      /* FUN_10026264 */
typedef void  (__fastcall *PFN_Fail)(void *frame);                       /* FUN_100262b2 */
typedef char  (__fastcall *PFN_W32)(void *stream, void *edx, DWORD v);   /* stream vt+0x88 */
typedef char  (__fastcall *PFN_R32)(void *stream, void *edx, DWORD *v);  /* stream vt+0x38 */

static PFN_WOpen g_wopen;
static PFN_ROpen g_ropen;
static PFN_Stream g_stream;
static PFN_Close g_close;
static PFN_Fail g_fail;
static DWORD g_d688, g_d6b3;         /* FUN_1000d688 write tile, FUN_1000d6b3 read tile */
static DWORD g_ret_save_begin, g_ret_save_end, g_ret_load, g_eh_load;

static void sv_add(DWORD w0, DWORD w1, DWORD id) {
    if (g_nsv == g_capsv) {
        int cap = g_capsv ? g_capsv * 2 : 256;
        NvRec *n = (NvRec *)realloc(g_sv, cap * sizeof(NvRec));
        if (!n) return;
        g_sv = n; g_capsv = cap;
    }
    g_sv[g_nsv].w0 = w0; g_sv[g_nsv].w1 = w1; g_sv[g_nsv].id = id;
    g_nsv++;
}

static WORD rb_save_id(DWORD w0, WORD id);       /* RBT block (sc3netmod_rbt.c): stock id of a roundabout cell */

/* record = the 8-byte tile record object; +4 word0 (coord, state), +8 word1 (id, props) */
static void __stdcall save_rec(BYTE *rec) {
    DWORD w1 = *(DWORD *)(rec + 8), id = w1 & 0xffff;
    WORD rb;
    if (!g_base[id]) return;
    rb = rb_save_id(*(DWORD *)(rec + 4), (WORD)id);
    *(DWORD *)(rec + 8) = (w1 & 0xffff0000) | (rb ? rb : g_base[id]);
    sv_add(*(DWORD *)(rec + 4), *(DWORD *)(rec + 8), id);
    InterlockedIncrement(&g_n_saved_base);
}

static __declspec(naked) void save_rec_thunk(void) {
    __asm {
        pushad
        push ecx
        call save_rec
        popad
        jmp dword ptr [g_d688]
    }
}

static void __stdcall save_begin(void) {
    if (g_nsv) logf("save: dropping %d stale entries", g_nsv);
    g_nsv = 0;
    g_n_saved_base = 0;
}

static __declspec(naked) void save_begin_hook(void) {
    __asm {
        pushad
        call save_begin
        popad
        mov eax, 0x2147c2dd
        jmp dword ptr [g_ret_save_begin]
    }
}

/* Called after the three networks were written, with FUN_10012dff's (param_1, param_2). */
static void __stdcall save_end(void *p1, void *p2) {
    BYTE frame[0x40];
    void *s;
    int i, ok;
    if (!g_nsv) { logf("save: no variant tiles, no section"); return; }
    memset(frame, 0, sizeof(frame));
    __try {
        g_wopen(frame, NULL, p1, p2, NV_TYPE, NV_GROUP, NV_INST, 1, 0);
        s = frame[0x10] ? g_stream(frame) : NULL;
        ok = s != NULL;
        if (ok) ok = ((PFN_W32)(*(DWORD **)s)[0x88 / 4])(s, NULL, NV_MAGIC);
        if (ok) ok = ((PFN_W32)(*(DWORD **)s)[0x88 / 4])(s, NULL, (DWORD)g_nsv);
        for (i = 0; ok && i < g_nsv; i++) {
            ok = ((PFN_W32)(*(DWORD **)s)[0x88 / 4])(s, NULL, g_sv[i].w0)
              && ((PFN_W32)(*(DWORD **)s)[0x88 / 4])(s, NULL, g_sv[i].w1)
              && ((PFN_W32)(*(DWORD **)s)[0x88 / 4])(s, NULL, g_sv[i].id);
        }
        if (!ok) g_fail(frame);
        g_close(frame);
        logf("save: %d variant tile(s) written as base, section 0x%lX %s", g_nsv, NV_INST, ok ? "written" : "FAILED");
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        logf("### save: exception 0x%08lX writing the variant section", GetExceptionCode());
    }
    g_nsv = 0;
}

static __declspec(naked) void save_end_hook(void) {
    __asm {
        pushad
        push edi                       /* param_2 (the archive), FUN_10012dff keeps it in edi */
        push dword ptr [ebp + 8]       /* param_1 */
        call save_end
        popad
        push ebx
        push 4
        sub esp, 0xc
        jmp dword ptr [g_ret_save_end]
    }
}

/* ---- load side ---- */

static int ld_slot(DWORD w0) {
    return (int)((w0 * 2654435761UL) >> 7) & (g_capld - 1);
}

static void ld_put(DWORD w0, DWORD w1, DWORD id) {
    int i = ld_slot(w0);
    while (g_ld[i].id) i = (i + 1) & (g_capld - 1);
    g_ld[i].w0 = w0; g_ld[i].w1 = w1; g_ld[i].id = id;
}

static DWORD ld_get(DWORD w0, DWORD w1) {
    int i = ld_slot(w0);
    while (g_ld[i].id) {
        if (g_ld[i].w0 == w0 && g_ld[i].w1 == w1) return g_ld[i].id;
        i = (i + 1) & (g_capld - 1);
    }
    return 0;
}

static void __stdcall load_begin(void *p1, void *p2) {
    BYTE frame[0x40];
    void *s;
    DWORD magic = 0, n = 0, i, w0, w1, id;
    int ok, unknown = 0;
    free(g_ld); g_ld = NULL; g_capld = g_nld = g_nld_hit = 0;
    memset(frame, 0, sizeof(frame));
    __try {
        g_ropen(frame, NULL, p1, p2, NV_TYPE, NV_GROUP, NV_INST);
        s = frame[0x10] ? g_stream(frame) : NULL;
        if (!s) { g_close(frame); logf("load: no variant section"); return; }
        ok = ((PFN_R32)(*(DWORD **)s)[0x38 / 4])(s, NULL, &magic)
          && ((PFN_R32)(*(DWORD **)s)[0x38 / 4])(s, NULL, &n);
        if (!ok || magic != NV_MAGIC || n > 4 * 1024 * 1024) {
            logf("### load: variant section unreadable (ok=%d magic=0x%08lX n=%lu) - ignored", ok, magic, n);
            g_close(frame);
            return;
        }
        for (g_capld = 64; g_capld < (int)n * 2; g_capld <<= 1) ;
        g_ld = (NvRec *)calloc(g_capld, sizeof(NvRec));
        for (i = 0; g_ld && i < n; i++) {
            ok = ((PFN_R32)(*(DWORD **)s)[0x38 / 4])(s, NULL, &w0)
              && ((PFN_R32)(*(DWORD **)s)[0x38 / 4])(s, NULL, &w1)
              && ((PFN_R32)(*(DWORD **)s)[0x38 / 4])(s, NULL, &id);
            if (!ok) { logf("### load: variant section short at %lu of %lu", i, n); break; }
            if (id == 0 || id > 0xffff) continue;
            if (!g_base[id]) { unknown++; continue; }   /* variant not installed: keep the base tile */
            ld_put(w0, w1, id);
            g_nld++;
        }
        g_close(frame);
        logf("load: variant section %lu entries, %d to restore, %d not installed (stay base)", n, g_nld, unknown);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        logf("### load: exception 0x%08lX reading the variant section", GetExceptionCode());
    }
}

static __declspec(naked) void load_begin_hook(void) {
    __asm {
        pushad
        push dword ptr [esp + 0x28]    /* param_2: 0x20 pushad + 4 ret + 4 param_1 */
        push dword ptr [esp + 0x28]    /* param_1 (shifted by the push above) */
        call load_begin
        popad
        mov eax, dword ptr [g_eh_load]
        jmp dword ptr [g_ret_load]
    }
}

static void __stdcall load_rec(BYTE *rec, DWORD ok) {
    DWORD id;
    if (!(ok & 0xff) || !g_nld) return;
    id = ld_get(*(DWORD *)(rec + 4), *(DWORD *)(rec + 8));
    if (!id) return;
    *(DWORD *)(rec + 8) = (*(DWORD *)(rec + 8) & 0xffff0000) | id;
    if (++g_nld_hit == g_nld) logf("load: all %d variant tiles restored", g_nld);
}

static __declspec(naked) void load_rec_thunk(void) {
    __asm {
        push ecx
        push dword ptr [esp + 0x10]
        push dword ptr [esp + 0x10]
        push dword ptr [esp + 0x10]
        call dword ptr [g_d6b3]
        pop ecx
        pushad
        push eax
        push ecx
        call load_rec
        popad
        ret 0xc
    }
}

static int patch_save(BYTE *m) {
    static const BYTE begin[] = { 0xb8, 0xdd, 0xc2, 0x47, 0x21, 0xb9, 0x7c, 0x6e, 0x6c, 0x20 };
    static const BYTE end[] = { 0x53, 0x6a, 0x04, 0x83, 0xec, 0x0c, 0x8d, 0x45, 0xb8 };
    if (!bytes_are(m + 0x12e3e, begin, sizeof(begin)) || !bytes_are(m + 0x12ee0, end, sizeof(end))) {
        logf("### SAVEBASE: FUN_10012dff differs from shipped - save side NOT patched");
        return 0;
    }
    g_d688 = retarget_call(m, 0x13082, 0xd688, (void *)save_rec_thunk);
    if (!g_d688) { logf("### SAVEBASE: +0x13082 is not `call FUN_1000d688`"); return 0; }
    g_ret_save_begin = (DWORD)m + 0x12e43;
    g_ret_save_end = (DWORD)m + 0x12ee6;
    return write_rel(m + 0x12e3e, 0xE9, (void *)save_begin_hook, 5)
        && write_rel(m + 0x12ee0, 0xE9, (void *)save_end_hook, 6);
}

static int patch_load(BYTE *m) {
    static const DWORD sites[] = { 0x13264, 0x13338, 0x1340b };
    BYTE *p = m + 0x130e9;
    int i;
    if (IsBadReadPtr(p, 10) || p[0] != 0xb8 || *(DWORD *)(p + 1) != (DWORD)m + 0x27924 || p[5] != 0xe8) {
        logf("### LOAD: FUN_100130e9 entry differs from shipped - load side NOT patched");
        return 0;
    }
    for (i = 0; i < 3; i++) {
        BYTE *c = m + sites[i];
        if (IsBadReadPtr(c, 5) || c[0] != 0xE8 || (DWORD)(c + 5) + *(DWORD *)(c + 1) != (DWORD)m + 0xd6b3) {
            logf("### LOAD: +0x%05lX is not `call FUN_1000d6b3` - load side NOT patched", sites[i]);
            return 0;
        }
    }
    g_d6b3 = (DWORD)m + 0xd6b3;
    for (i = 0; i < 3; i++) retarget_call(m, sites[i], 0xd6b3, (void *)load_rec_thunk);
    g_eh_load = (DWORD)m + 0x27924;
    g_ret_load = (DWORD)m + 0x130ee;
    return write_rel(p, 0xE9, (void *)load_begin_hook, 5);
}

/* ============================================================ 3. OVERLAY: mods\netmod\overlay serves game files */

/* Task netpack (2026-10-13, re/analysis/NETPACK.md). `netpack.py install` (overlay mode) writes every built file to
 * <root>\mods\netmod\overlay\<path relative to root> and never writes under Apps\. This block makes the game read
 * them: a read-only open of <root>\X is served from overlay\X when that file exists, and a directory listing of a
 * folder the overlay mirrors is merged (stock entries first, then overlay-only names), so a new Res\Sprites\*.DAT is
 * enumerated like a shipped one. Without this DLL the game sees the stock install only.
 *
 * Every game module imports CreateFileA / GetFileAttributesA / FindFirstFileA / FindNextFileA / FindClose from
 * KERNEL32.dll by name, ANSI only; fopen/_sopen reach CreateFileA through the shipped MSVCRT.DLL's own import (import
 * tables read with pefile, 2026-10-13). So the hooks are IAT slots in every loaded module, re-armed after every
 * LoadLibraryA/ExA returns (the sim DLLs load after injection). Writes are never redirected.
 * Off: SC3NETMOD_OVERLAY=0, or no <root>\mods\netmod\overlay folder (then nothing is hooked).
 * SC3NETMOD_FILELOG=1 logs every hooked call on a path under <root>\Apps\Res, with the calling module. */

typedef HANDLE (WINAPI *PFN_CreateFileA)(LPCSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);
typedef DWORD  (WINAPI *PFN_GetFileAttributesA)(LPCSTR);
typedef HANDLE (WINAPI *PFN_FindFirstFileA)(LPCSTR, LPWIN32_FIND_DATAA);
typedef BOOL   (WINAPI *PFN_FindNextFileA)(HANDLE, LPWIN32_FIND_DATAA);
typedef BOOL   (WINAPI *PFN_FindClose)(HANDLE);
typedef HMODULE (WINAPI *PFN_LoadLibraryA)(LPCSTR);
typedef HMODULE (WINAPI *PFN_LoadLibraryExA)(LPCSTR, HANDLE, DWORD);

static PFN_CreateFileA o_CreateFileA;
static PFN_GetFileAttributesA o_GetFileAttributesA;
static PFN_FindFirstFileA o_FindFirstFileA;
static PFN_FindNextFileA o_FindNextFileA;
static PFN_FindClose o_FindClose;
static PFN_LoadLibraryA o_LoadLibraryA;
static PFN_LoadLibraryExA o_LoadLibraryExA;

static int g_ov_on, g_filelog;
static char g_ovdir[MAX_PATH];       /* <root>\mods\netmod\overlay\ */
static int g_ovdirlen;
static char **g_ovfiles;             /* overlay files, path relative to the overlay = relative to root */
static int g_novfiles;
static CRITICAL_SECTION g_ovlock;
static volatile LONG g_n_redirect;

static void ov_add(const char *rel) {
    char **n;
    if (g_novfiles % 64 == 0) {
        n = (char **)realloc(g_ovfiles, (g_novfiles + 64) * sizeof(char *));
        if (!n) return;
        g_ovfiles = n;
    }
    g_ovfiles[g_novfiles] = _strdup(rel);
    if (g_ovfiles[g_novfiles]) g_novfiles++;
}

static void ov_walk(const char *rel) {          /* rel = "" or "Apps\Res\" (ends with '\') */
    char pat[MAX_PATH], sub[MAX_PATH];
    WIN32_FIND_DATAA fd;
    HANDLE h;
    _snprintf(pat, sizeof(pat), "%s%s*", g_ovdir, rel);
    pat[sizeof(pat) - 1] = 0;
    h = FindFirstFileA(pat, &fd);
    if (h == INVALID_HANDLE_VALUE) return;
    do {
        if (!lstrcmpA(fd.cFileName, ".") || !lstrcmpA(fd.cFileName, "..")) continue;
        _snprintf(sub, sizeof(sub), "%s%s", rel, fd.cFileName);
        sub[sizeof(sub) - 1] = 0;
        if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            lstrcatA(sub, "\\");
            ov_walk(sub);
        } else {
            ov_add(sub);
        }
    } while (FindNextFileA(h, &fd));
    FindClose(h);
}

/* full path of `in` under the root -> pointer to its root-relative part inside `full`, else NULL */
static const char *ov_rel(LPCSTR in, char *full) {
    DWORD n;
    if (!in || !g_rootlen) return NULL;
    n = GetFullPathNameA(in, MAX_PATH, full, NULL);
    if (!n || n >= MAX_PATH) return NULL;
    if (_strnicmp(full, g_root, g_rootlen)) return NULL;
    return full + g_rootlen;
}

/* `in` names a file the overlay holds -> overlay path in `out`, 1 */
static int ov_map(LPCSTR in, char *out) {
    char full[MAX_PATH];
    const char *rel = ov_rel(in, full);
    int i;
    if (!rel) return 0;
    for (i = 0; i < g_novfiles; i++) {
        if (!lstrcmpiA(g_ovfiles[i], rel)) {
            _snprintf(out, MAX_PATH, "%s%s", g_ovdir, g_ovfiles[i]);
            out[MAX_PATH - 1] = 0;
            return 1;
        }
    }
    return 0;
}

static int is_res(LPCSTR in) {
    char full[MAX_PATH];
    const char *rel = ov_rel(in, full);
    return rel && !_strnicmp(rel, "Apps\\Res\\", 9);
}

static const char *caller_mod(void *ret, char *buf, int cap) {
    HMODULE m = NULL;
    char *s;
    buf[0] = 0;
    if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                           (LPCSTR)ret, &m) && GetModuleFileNameA(m, buf, cap)) {
        s = strrchr(buf, '\\');
        return s ? s + 1 : buf;
    }
    return "?";
}

#define WANTS_WRITE(acc) ((acc) & (GENERIC_WRITE | GENERIC_ALL | FILE_WRITE_DATA | FILE_APPEND_DATA | DELETE))

static HANDLE WINAPI h_CreateFileA(LPCSTR name, DWORD acc, DWORD share, LPSECURITY_ATTRIBUTES sa, DWORD disp,
                                   DWORD flags, HANDLE tmpl) {
    char alt[MAX_PATH], who[MAX_PATH];
    HANDLE r;
    if (!WANTS_WRITE(acc) && (disp == OPEN_EXISTING || disp == OPEN_ALWAYS) && ov_map(name, alt)) {
        r = o_CreateFileA(alt, acc, share, sa, OPEN_EXISTING, flags, tmpl);
        InterlockedIncrement(&g_n_redirect);
        logf("overlay: CreateFileA \"%s\" -> \"%s\" %s (%s)", name, alt, r == INVALID_HANDLE_VALUE ? "FAIL" : "ok",
             caller_mod(_ReturnAddress(), who, sizeof(who)));
        return r;
    }
    r = o_CreateFileA(name, acc, share, sa, disp, flags, tmpl);
    if (g_filelog && is_res(name))
        logf("filelog: CreateFileA \"%s\" acc 0x%lX disp %lu -> %s (%s)%s", name, acc, disp,
             r == INVALID_HANDLE_VALUE ? "FAIL" : "ok", caller_mod(_ReturnAddress(), who, sizeof(who)),
             WANTS_WRITE(acc) && ov_map(name, alt) ? " ### WRITE to an overlaid path, not redirected" : "");
    return r;
}

static DWORD WINAPI h_GetFileAttributesA(LPCSTR name) {
    char alt[MAX_PATH], who[MAX_PATH];
    DWORD r;
    if (ov_map(name, alt)) {
        r = o_GetFileAttributesA(alt);
        logf("overlay: GetFileAttributesA \"%s\" -> overlay %s (%s)", name,
             r == INVALID_FILE_ATTRIBUTES ? "MISSING" : "exists", caller_mod(_ReturnAddress(), who, sizeof(who)));
        return r;
    }
    r = o_GetFileAttributesA(name);
    if (g_filelog && is_res(name))
        logf("filelog: GetFileAttributesA \"%s\" -> %s (%s)", name, r == INVALID_FILE_ATTRIBUTES ? "MISSING" : "exists",
             caller_mod(_ReturnAddress(), who, sizeof(who)));
    return r;
}

/* ---- merged directory listings: our handles are FindCtx pointers kept in g_finds ---- */
typedef struct { WIN32_FIND_DATAA *e; int n, pos; } FindCtx;
static FindCtx *g_finds[64];

static int wild(const char *p, const char *s) {           /* '*' and '?', case-insensitive */
    for (; *p; p++, s++) {
        if (*p == '*') {
            while (p[1] == '*') p++;
            if (!p[1]) return 1;
            for (; *s; s++) if (wild(p + 1, s)) return 1;
            return 0;
        }
        if (!*s) return 0;
        if (*p != '?' && toupper((unsigned char)*p) != toupper((unsigned char)*s)) return 0;
    }
    return !*s;
}

static void fc_push(FindCtx *c, const WIN32_FIND_DATAA *d) {
    int i;
    for (i = 0; i < c->n; i++)
        if (!lstrcmpiA(c->e[i].cFileName, d->cFileName)) { c->e[i] = *d; return; }   /* overlay replaces stock */
    if (c->n % 32 == 0) {
        WIN32_FIND_DATAA *n = (WIN32_FIND_DATAA *)realloc(c->e, (c->n + 32) * sizeof(*n));
        if (!n) return;
        c->e = n;
    }
    c->e[c->n++] = *d;
}

static int fc_ours(HANDLE h) {
    int i;
    for (i = 0; i < 64; i++) if (g_finds[i] && (HANDLE)g_finds[i] == h) return i;
    return -1;
}

static HANDLE WINAPI h_FindFirstFileA(LPCSTR pat, LPWIN32_FIND_DATAA d) {
    char full[MAX_PATH], dir[MAX_PATH], opat[MAX_PATH], who[MAX_PATH];
    const char *rel = ov_rel(pat, full), *spec;
    char *slash;
    int i, dlen, slot, extra = 0;
    FindCtx *c;
    WIN32_FIND_DATAA fd;
    HANDLE h;
    if (rel) {
        lstrcpynA(dir, rel, sizeof(dir));
        slash = strrchr(dir, '\\');
        if (slash) { slash[1] = 0; spec = rel + (slash + 1 - dir); } else { dir[0] = 0; spec = rel; }
        dlen = lstrlenA(dir);
        for (i = 0; i < g_novfiles; i++)
            if (!_strnicmp(g_ovfiles[i], dir, dlen) && !strchr(g_ovfiles[i] + dlen, '\\') && wild(spec, g_ovfiles[i] + dlen))
                extra++;
        if (extra) {
            c = (FindCtx *)calloc(1, sizeof(FindCtx));
            if (!c) goto plain;
            h = o_FindFirstFileA(pat, &fd);
            if (h != INVALID_HANDLE_VALUE) {
                do fc_push(c, &fd); while (o_FindNextFileA(h, &fd));
                o_FindClose(h);
            }
            for (i = 0; i < g_novfiles; i++) {
                if (_strnicmp(g_ovfiles[i], dir, dlen) || strchr(g_ovfiles[i] + dlen, '\\') || !wild(spec, g_ovfiles[i] + dlen))
                    continue;
                _snprintf(opat, sizeof(opat), "%s%s", g_ovdir, g_ovfiles[i]);
                opat[sizeof(opat) - 1] = 0;
                h = o_FindFirstFileA(opat, &fd);
                if (h != INVALID_HANDLE_VALUE) { fc_push(c, &fd); o_FindClose(h); }
            }
            EnterCriticalSection(&g_ovlock);
            for (slot = 0; slot < 64 && g_finds[slot]; slot++) ;
            if (slot < 64) g_finds[slot] = c;
            LeaveCriticalSection(&g_ovlock);
            logf("overlay: FindFirstFileA \"%s\" -> merged listing, %d entries incl. %d from the overlay (%s)", pat, c->n,
                 extra, caller_mod(_ReturnAddress(), who, sizeof(who)));
            if (slot == 64 || !c->n) {
                free(c->e); free(c);
                if (slot < 64) { EnterCriticalSection(&g_ovlock); g_finds[slot] = NULL; LeaveCriticalSection(&g_ovlock); }
                if (slot == 64) { logf("### overlay: 64 merged listings open, plain listing"); goto plain; }
                SetLastError(ERROR_FILE_NOT_FOUND);
                return INVALID_HANDLE_VALUE;
            }
            *d = c->e[0];
            c->pos = 1;
            return (HANDLE)c;
        }
    }
plain:
    h = o_FindFirstFileA(pat, d);
    if (g_filelog && is_res(pat))
        logf("filelog: FindFirstFileA \"%s\" -> %s (%s)", pat, h == INVALID_HANDLE_VALUE ? "none" : d->cFileName,
             caller_mod(_ReturnAddress(), who, sizeof(who)));
    return h;
}

static BOOL WINAPI h_FindNextFileA(HANDLE h, LPWIN32_FIND_DATAA d) {
    int i = fc_ours(h);
    FindCtx *c;
    if (i < 0) return o_FindNextFileA(h, d);
    c = g_finds[i];
    if (c->pos >= c->n) { SetLastError(ERROR_NO_MORE_FILES); return FALSE; }
    *d = c->e[c->pos++];
    return TRUE;
}

static BOOL WINAPI h_FindClose(HANDLE h) {
    int i;
    FindCtx *c;
    EnterCriticalSection(&g_ovlock);
    i = fc_ours(h);
    c = i >= 0 ? g_finds[i] : NULL;
    if (c) g_finds[i] = NULL;
    LeaveCriticalSection(&g_ovlock);
    if (!c) return o_FindClose(h);
    free(c->e);
    free(c);
    return TRUE;
}

static void ov_hook_all(void);

static HMODULE WINAPI h_LoadLibraryA(LPCSTR name) {
    HMODULE r = o_LoadLibraryA(name);
    if (r) ov_hook_all();
    return r;
}

static HMODULE WINAPI h_LoadLibraryExA(LPCSTR name, HANDLE f, DWORD flags) {
    HMODULE r = o_LoadLibraryExA(name, f, flags);
    if (r && !(flags & (LOAD_LIBRARY_AS_DATAFILE | 0x40 /* AS_IMAGE_RESOURCE */))) ov_hook_all();
    return r;
}

/* Patch module m's KERNEL32.dll import of `fn` (looked up by name in the import name table) to `to`. */
static int iat_patch(BYTE *m, const char *fn, void *to) {
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)m;
    IMAGE_NT_HEADERS *nt;
    IMAGE_IMPORT_DESCRIPTOR *imp;
    DWORD rva;
    int hits = 0;
    if (IsBadReadPtr(dos, sizeof(*dos)) || dos->e_magic != IMAGE_DOS_SIGNATURE) return 0;
    nt = (IMAGE_NT_HEADERS *)(m + dos->e_lfanew);
    if (IsBadReadPtr(nt, sizeof(*nt)) || nt->Signature != IMAGE_NT_SIGNATURE) return 0;
    rva = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress;
    if (!rva) return 0;
    for (imp = (IMAGE_IMPORT_DESCRIPTOR *)(m + rva); imp->Name; imp++) {
        IMAGE_THUNK_DATA *names, *slots;
        if (lstrcmpiA((const char *)(m + imp->Name), "KERNEL32.dll") || !imp->OriginalFirstThunk) continue;
        names = (IMAGE_THUNK_DATA *)(m + imp->OriginalFirstThunk);
        slots = (IMAGE_THUNK_DATA *)(m + imp->FirstThunk);
        for (; names->u1.AddressOfData; names++, slots++) {
            IMAGE_IMPORT_BY_NAME *ibn;
            if (IMAGE_SNAP_BY_ORDINAL(names->u1.Ordinal)) continue;
            ibn = (IMAGE_IMPORT_BY_NAME *)(m + names->u1.AddressOfData);
            if (lstrcmpA((const char *)ibn->Name, fn)) continue;
            if (slots->u1.Function != (DWORD)to && write_code((BYTE *)&slots->u1.Function, &to, 4)) hits++;
        }
    }
    return hits;
}

static void ov_hook_all(void) {
    typedef BOOL (WINAPI *PFN_EPM)(HANDLE, HMODULE *, DWORD, LPDWORD);
    static PFN_EPM epm;
    HMODULE mods[512];
    DWORD needed = 0, i;
    int hits = 0;
    if (!epm) epm = (PFN_EPM)GetProcAddress(GetModuleHandleA("KERNEL32.dll"), "K32EnumProcessModules");
    if (!epm || !epm(GetCurrentProcess(), mods, sizeof(mods), &needed)) return;
    EnterCriticalSection(&g_ovlock);
    for (i = 0; i < needed / sizeof(HMODULE) && i < 512; i++) {
        BYTE *m = (BYTE *)mods[i];
        if (mods[i] == g_self) continue;                 /* our own reads stay on kernel32 */
        hits += iat_patch(m, "CreateFileA", (void *)h_CreateFileA);
        hits += iat_patch(m, "GetFileAttributesA", (void *)h_GetFileAttributesA);
        hits += iat_patch(m, "FindFirstFileA", (void *)h_FindFirstFileA);
        hits += iat_patch(m, "FindNextFileA", (void *)h_FindNextFileA);
        hits += iat_patch(m, "FindClose", (void *)h_FindClose);
        hits += iat_patch(m, "LoadLibraryA", (void *)h_LoadLibraryA);
        hits += iat_patch(m, "LoadLibraryExA", (void *)h_LoadLibraryExA);
    }
    LeaveCriticalSection(&g_ovlock);
    if (hits) logf("overlay: %d import slot(s) hooked over %lu module(s)", hits, needed / sizeof(HMODULE));
}

/* Runs in DllMain: mods_launch injects while the game's main thread is still suspended, so the hooks are in place
   before the game opens any resource. Only kernel32 calls here (loader lock). */
static void overlay_init(void) {
    char v[8];
    HMODULE k = GetModuleHandleA("KERNEL32.dll");
    InitializeCriticalSection(&g_ovlock);
    g_filelog = GetEnvironmentVariableA("SC3NETMOD_FILELOG", v, sizeof(v)) && v[0] == '1';
    if (env_off("SC3NETMOD_OVERLAY")) { logf("overlay: off (SC3NETMOD_OVERLAY=0)"); if (!g_filelog) return; }
    else if (g_rootlen) {
        _snprintf(g_ovdir, sizeof(g_ovdir), "%smods\\netmod\\overlay\\", g_root);
        g_ovdir[sizeof(g_ovdir) - 1] = 0;
        g_ovdirlen = lstrlenA(g_ovdir);
        if (GetFileAttributesA(g_ovdir) != INVALID_FILE_ATTRIBUTES) ov_walk("");
        logf("overlay: %s, %d file(s)", g_ovdir, g_novfiles);
    }
    if (!g_novfiles && !g_filelog) return;
    o_CreateFileA = (PFN_CreateFileA)GetProcAddress(k, "CreateFileA");
    o_GetFileAttributesA = (PFN_GetFileAttributesA)GetProcAddress(k, "GetFileAttributesA");
    o_FindFirstFileA = (PFN_FindFirstFileA)GetProcAddress(k, "FindFirstFileA");
    o_FindNextFileA = (PFN_FindNextFileA)GetProcAddress(k, "FindNextFileA");
    o_FindClose = (PFN_FindClose)GetProcAddress(k, "FindClose");
    o_LoadLibraryA = (PFN_LoadLibraryA)GetProcAddress(k, "LoadLibraryA");
    o_LoadLibraryExA = (PFN_LoadLibraryExA)GetProcAddress(k, "LoadLibraryExA");
    if (!o_CreateFileA || !o_GetFileAttributesA || !o_FindFirstFileA || !o_FindNextFileA || !o_FindClose
        || !o_LoadLibraryA || !o_LoadLibraryExA) {
        logf("### overlay: kernel32 originals not bound, overlay OFF");
        g_novfiles = 0;
        return;
    }
    g_ov_on = 1;
    ov_hook_all();
    logf("overlay: ON (%d file(s)%s)", g_novfiles, g_filelog ? ", file log on" : "");
}

static BYTE g_tmpl_keep[65536];   /* task multitile: template piece ids, kept out of the INHERIT collapse mapping */
#include "sc3netmod_bridge.c"     /* task netbridge: INHERIT + XCROSS (SC3NETMOD_INHERIT / SC3NETMOD_XCROSS) */
/* ==== NETRAMP begin (task netramp, 2026-10-13) ==========================================================
 * 4. RAMPS (SC3NETMOD_RAMPS=0 turns it off). SIMNTWRK picks on-ramp, tunnel and slope pieces from hardcoded tables,
 *    not from TilingRules (re/analysis/NET_RAMPS.md):
 *      onramp / onramp_corner  imm32 operands of `mov [ebp+d8], imm32` in FUN_1000abde (On-ramp tool, netmgr vt+0xac)
 *      slope.<NET>             u32[8] in .data, read only by FUN_1001a2c0
 *      tunnel.<NET>            u32[4] in .data, read by FUN_1001c102 / FUN_1001ca1a (build) and FUN_1001d761 (removal)
 *    netpack.py writes `ramp <table> <slot> <from> <to>` lines into the package's mods\netmod\tables\<package>.txt.
 *    Each line is applied in place when SIMNTWRK maps, only if (table, slot) is in g_rslots below, `from` is that
 *    slot's stock value and memory still holds it. Patching the table itself keeps the builder and the removal path
 *    (FUN_1001d761 compares ids against the same tunnel tables) consistent.
 *    A variant placed by a table gets its BASE's piece class: the two calls of the classifier FUN_1001a5f2 (in
 *    FUN_1001363a and FUN_1001369f) go through ramp_class_thunk, which hands the classifier the base id. The class
 *    decides the occupant flags: the on-ramp classes (kind 14/15, ids 15130..15141 only) add 0x200000 [CONFIRMED @
 *    0x1000c5f6, 0x1000c62e], which SIMTRANSIT FUN_10005983 tests. Only ids listed as a ramp `to` AND as a variant
 *    are mapped; every other id classifies exactly as stock.
 *  Hooks: +0x13643, +0x136ce call FUN_1001a5f2 -> ramp_class_thunk; table slots as listed. Log lines "ramp: ...". */

typedef struct { const char *table; int slot; DWORD va; int imm; DWORD stock; } RampSlot;
static const RampSlot g_rslots[] = {
    {"onramp", 0, 0x1000B5D0, 1, 0x3B2500},
    {"onramp", 1, 0x1000B5D7, 1, 0x3B2100},
    {"onramp", 2, 0x1000B5DE, 1, 0x3B1D00},
    {"onramp", 3, 0x1000B5EB, 1, 0x3B1C02},
    {"onramp", 4, 0x1000B5F2, 1, 0x3B2002},
    {"onramp", 5, 0x1000B5F9, 1, 0x3B2402},
    {"onramp", 6, 0x1000B60C, 1, 0x3B1D02},
    {"onramp", 7, 0x1000B613, 1, 0x3B2102},
    {"onramp", 8, 0x1000B61A, 1, 0x3B2502},
    {"onramp", 9, 0x1000B627, 1, 0x3B2400},
    {"onramp", 10, 0x1000B62E, 1, 0x3B2000},
    {"onramp", 11, 0x1000B635, 1, 0x3B1C00},
    {"onramp", 12, 0x1000B64E, 1, 0x3B2302},
    {"onramp", 13, 0x1000B655, 1, 0x3B1F02},
    {"onramp", 14, 0x1000B65C, 1, 0x3B1B02},
    {"onramp", 15, 0x1000B669, 1, 0x3B1A00},
    {"onramp", 16, 0x1000B670, 1, 0x3B1E00},
    {"onramp", 17, 0x1000B677, 1, 0x3B2200},
    {"onramp", 18, 0x1000B68A, 1, 0x3B2202},
    {"onramp", 19, 0x1000B691, 1, 0x3B1E02},
    {"onramp", 20, 0x1000B698, 1, 0x3B1A02},
    {"onramp", 21, 0x1000B6A5, 1, 0x3B1B00},
    {"onramp", 22, 0x1000B6AC, 1, 0x3B1F00},
    {"onramp", 23, 0x1000B6B3, 1, 0x3B2300},
    {"onramp_corner", 0, 0x1000B8C0, 1, 0x3B1700},
    {"onramp_corner", 1, 0x1000B8C7, 1, 0x3B1600},
    {"onramp_corner", 2, 0x1000B8CE, 1, 0x3B1300},
    {"onramp_corner", 3, 0x1000B8D7, 1, 0x3B1800},
    {"onramp_corner", 4, 0x1000B8DE, 1, 0x3B1500},
    {"onramp_corner", 5, 0x1000B8E5, 1, 0x3B1402},
    {"onramp_corner", 6, 0x1000B8FE, 1, 0x3B1802},
    {"onramp_corner", 7, 0x1000B905, 1, 0x3B1502},
    {"onramp_corner", 8, 0x1000B90C, 1, 0x3B1400},
    {"onramp_corner", 9, 0x1000B915, 1, 0x3B1702},
    {"onramp_corner", 10, 0x1000B91C, 1, 0x3B1602},
    {"onramp_corner", 11, 0x1000B923, 1, 0x3B1302},
    {"slope.ROAD", 0, 0x1003195C, 0, 0x2BC200},
    {"slope.ROAD", 1, 0x10031960, 0, 0x2BC100},
    {"slope.ROAD", 2, 0x10031964, 0, 0x2BC202},
    {"slope.ROAD", 3, 0x10031968, 0, 0x2BC102},
    {"slope.ROAD", 4, 0x1003196C, 0, 0x002000},
    {"slope.ROAD", 5, 0x10031970, 0, 0x001F00},
    {"slope.ROAD", 6, 0x10031974, 0, 0x002002},
    {"slope.ROAD", 7, 0x10031978, 0, 0x001F02},
    {"slope.RAIL", 0, 0x1003197C, 0, 0x3E8800},
    {"slope.RAIL", 1, 0x10031980, 0, 0x3E8900},
    {"slope.RAIL", 2, 0x10031984, 0, 0x3E8802},
    {"slope.RAIL", 3, 0x10031988, 0, 0x3E8902},
    {"slope.RAIL", 4, 0x1003198C, 0, 0x002E00},
    {"slope.RAIL", 5, 0x10031990, 0, 0x002F00},
    {"slope.RAIL", 6, 0x10031994, 0, 0x002E02},
    {"slope.RAIL", 7, 0x10031998, 0, 0x002F02},
    {"slope.SUBW", 0, 0x1003199C, 0, 0x2D6000},
    {"slope.SUBW", 1, 0x100319A0, 0, 0x2D6100},
    {"slope.SUBW", 2, 0x100319A4, 0, 0x2D6002},
    {"slope.SUBW", 3, 0x100319A8, 0, 0x2D6102},
    {"slope.SUBW", 4, 0x100319AC, 0, 0x2D5E00},
    {"slope.SUBW", 5, 0x100319B0, 0, 0x2D5F00},
    {"slope.SUBW", 6, 0x100319B4, 0, 0x2D5E02},
    {"slope.SUBW", 7, 0x100319B8, 0, 0x2D5F02},
    {"slope.PIPE", 0, 0x100319BC, 0, 0x2D8200},
    {"slope.PIPE", 1, 0x100319C0, 0, 0x2D8100},
    {"slope.PIPE", 2, 0x100319C4, 0, 0x2D8202},
    {"slope.PIPE", 3, 0x100319C8, 0, 0x2D8102},
    {"slope.PIPE", 4, 0x100319CC, 0, 0x2D8000},
    {"slope.PIPE", 5, 0x100319D0, 0, 0x2D7F00},
    {"slope.PIPE", 6, 0x100319D4, 0, 0x2D8002},
    {"slope.PIPE", 7, 0x100319D8, 0, 0x2D7F02},
    {"slope.POWR_line", 0, 0x100319DC, 0, 0x2BFE00},
    {"slope.POWR_line", 1, 0x100319E0, 0, 0x2BFE01},
    {"slope.POWR_line", 2, 0x100319E4, 0, 0x2BFE02},
    {"slope.POWR_line", 3, 0x100319E8, 0, 0x2BFE03},
    {"slope.POWR_line", 4, 0x100319EC, 0, 0x2BFF00},
    {"slope.POWR_line", 5, 0x100319F0, 0, 0x2BFF01},
    {"slope.POWR_line", 6, 0x100319F4, 0, 0x2BFF02},
    {"slope.POWR_line", 7, 0x100319F8, 0, 0x2BFF03},
    {"slope.POWR_pole", 0, 0x100319FC, 0, 0x46A100},
    {"slope.POWR_pole", 1, 0x10031A00, 0, 0x46A000},
    {"slope.POWR_pole", 2, 0x10031A04, 0, 0x46A102},
    {"slope.POWR_pole", 3, 0x10031A08, 0, 0x46A002},
    {"slope.POWR_pole", 4, 0x10031A0C, 0, 0x46A300},
    {"slope.POWR_pole", 5, 0x10031A10, 0, 0x46A200},
    {"slope.POWR_pole", 6, 0x10031A14, 0, 0x46A302},
    {"slope.POWR_pole", 7, 0x10031A18, 0, 0x46A202},
    {"slope.HWAY_absent", 0, 0x10031A1C, 0, 0x3B0000},
    {"slope.HWAY_absent", 1, 0x10031A20, 0, 0x3AFF00},
    {"slope.HWAY_absent", 2, 0x10031A24, 0, 0x3AFE02},
    {"slope.HWAY_absent", 3, 0x10031A28, 0, 0x3B0102},
    {"slope.HWAY_absent", 4, 0x10031A2C, 0, 0x3AFC00},
    {"slope.HWAY_absent", 5, 0x10031A30, 0, 0x3AFB00},
    {"slope.HWAY_absent", 6, 0x10031A34, 0, 0x370E02},
    {"slope.HWAY_absent", 7, 0x10031A38, 0, 0x3AFD02},
    {"slope.HWAY_present", 0, 0x10031A3C, 0, 0x3AFE00},
    {"slope.HWAY_present", 1, 0x10031A40, 0, 0x3B0100},
    {"slope.HWAY_present", 2, 0x10031A44, 0, 0x3B0002},
    {"slope.HWAY_present", 3, 0x10031A48, 0, 0x3AFF02},
    {"slope.HWAY_present", 4, 0x10031A4C, 0, 0x370E00},
    {"slope.HWAY_present", 5, 0x10031A50, 0, 0x3AFD00},
    {"slope.HWAY_present", 6, 0x10031A54, 0, 0x3AFC02},
    {"slope.HWAY_present", 7, 0x10031A58, 0, 0x3AFB02},
    {"tunnel.ROAD", 0, 0x10031FD8, 0, 0x004000},
    {"tunnel.ROAD", 1, 0x10031FDC, 0, 0x003F00},
    {"tunnel.ROAD", 2, 0x10031FE0, 0, 0x004002},
    {"tunnel.ROAD", 3, 0x10031FE4, 0, 0x003F02},
    {"tunnel.RAIL", 0, 0x10031FE8, 0, 0x466800},
    {"tunnel.RAIL", 1, 0x10031FEC, 0, 0x466300},
    {"tunnel.RAIL", 2, 0x10031FF0, 0, 0x466802},
    {"tunnel.RAIL", 3, 0x10031FF4, 0, 0x466302},
    {"tunnel.HWAY_a", 0, 0x10031FF8, 0, 0x466E00},
    {"tunnel.HWAY_a", 1, 0x10031FFC, 0, 0x466D00},
    {"tunnel.HWAY_a", 2, 0x10032000, 0, 0x466E02},
    {"tunnel.HWAY_a", 3, 0x10032004, 0, 0x466D02},
    {"tunnel.HWAY_b", 0, 0x10032008, 0, 0x466C00},
    {"tunnel.HWAY_b", 1, 0x1003200C, 0, 0x466B00},
    {"tunnel.HWAY_b", 2, 0x10032010, 0, 0x466C02},
    {"tunnel.HWAY_b", 3, 0x10032014, 0, 0x466B02},
    {"tunnel.HWAY_c", 0, 0x10032018, 0, 0x46AB00},
    {"tunnel.HWAY_c", 1, 0x1003201C, 0, 0x46AA00},
    {"tunnel.HWAY_c", 2, 0x10032020, 0, 0x46AB02},
    {"tunnel.HWAY_c", 3, 0x10032024, 0, 0x46AA02},
    {"tunnel.HWAY_d", 0, 0x10032028, 0, 0x46A900},
    {"tunnel.HWAY_d", 1, 0x1003202C, 0, 0x46A800},
    {"tunnel.HWAY_d", 2, 0x10032030, 0, 0x46A902},
    {"tunnel.HWAY_d", 3, 0x10032034, 0, 0x46A802},
};
#define NRSLOTS (sizeof(g_rslots) / sizeof(g_rslots[0]))

static BYTE g_rampcls[65536];        /* variant ids a ramp line places: classify as the base */
static DWORD g_a5f2;
static volatile LONG g_n_rampcls;
static int g_n_ramp_ok, g_n_ramp_bad;

static DWORD __stdcall ramp_class_id(DWORD id) {
    if (id <= 0xffff && g_rampcls[id] && g_base[id]) { InterlockedIncrement(&g_n_rampcls); return g_base[id]; }
    return id;
}

/* __thiscall FUN_1001a5f2(this, uint id), ret 4: replace the id argument, keep ecx, tail-jump to the original. */
static __declspec(naked) void ramp_class_thunk(void) {
    __asm {
        push ecx
        push dword ptr [esp + 8]
        call ramp_class_id
        pop ecx
        mov [esp + 4], eax
        jmp dword ptr [g_a5f2]
    }
}

static void ramp_line(BYTE *m, const char *path, const char *line) {
    char tab[64];
    int slot, k;
    unsigned long from, to;
    if (sscanf(line, "ramp %63s %d %lx %lx", tab, &slot, &from, &to) != 4) {
        logf("### ramp: %s: bad line '%s'", path, line); g_n_ramp_bad++; return;
    }
    for (k = 0; k < (int)NRSLOTS; k++) {
        const RampSlot *r = &g_rslots[k];
        DWORD *p, cur;
        if (lstrcmpA(r->table, tab) || r->slot != slot) continue;
        if (from != r->stock) {
            logf("### ramp: %s slot %d: line says stock 0x%lx, this DLL knows 0x%lx - skipped", tab, slot, from, r->stock);
            g_n_ramp_bad++; return;
        }
        p = (DWORD *)(m + (r->va - 0x10000000));
        cur = *p;
        if (cur == to) { logf("ramp: %s slot %d already 0x%lx (another line set it) - kept", tab, slot, to); return; }
        if (cur != r->stock) {
            logf("### ramp: %s slot %d holds 0x%lx, not the stock 0x%lx - skipped", tab, slot, cur, r->stock);
            g_n_ramp_bad++; return;
        }
        if (!write_code((BYTE *)p, &to, 4)) { logf("### ramp: %s slot %d: write failed", tab, slot); g_n_ramp_bad++; return; }
        if ((to >> 8) <= 0xffff && g_base[to >> 8]) g_rampcls[to >> 8] = 1;
        logf("ramp: %s slot %d  %lu.%lu -> %lu.%lu%s", tab, slot, from >> 8, from & 0xff, to >> 8, to & 0xff,
             g_base[to >> 8] ? " (variant)" : "");
        g_n_ramp_ok++;
        return;
    }
    logf("### ramp: %s: unknown table/slot '%s %d' - skipped", path, tab, slot);
    g_n_ramp_bad++;
}

static void ramp_file(BYTE *m, const char *path) {
    char line[256];
    FILE *f = fopen(path, "r");
    if (!f) return;
    while (fgets(line, sizeof(line), f)) {
        char *e = line + strlen(line);
        while (e > line && (e[-1] == '\r' || e[-1] == '\n')) *--e = 0;
        if (!strncmp(line, "ramp ", 5)) ramp_line(m, path, line);
    }
    fclose(f);
}

/* Same sources as table_load: SC3NETMOD_TABLE alone, else every mods\netmod\tables\*.txt in name order. */
static int netramp_install(BYTE *m) {
    char path[MAX_PATH], pat[MAX_PATH];
    WIN32_FIND_DATAA fd;
    HANDLE h;
    int k, j, cnt = 0, ncls = 0;
    static char names[64][MAX_PATH];
    if (env_off("SC3NETMOD_RAMPS")) { logf("ramp: off (SC3NETMOD_RAMPS=0)"); return 0; }
    if (GetEnvironmentVariableA("SC3NETMOD_TABLE", path, sizeof(path))) ramp_file(m, path);
    else if (g_rootlen) {
        _snprintf(pat, sizeof(pat), "%smods\\netmod\\tables\\*.txt", g_root);
        pat[sizeof(pat) - 1] = 0;
        h = FindFirstFileA(pat, &fd);
        if (h != INVALID_HANDLE_VALUE) {
            do {
                if (!(fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) && cnt < 64) lstrcpynA(names[cnt++], fd.cFileName, MAX_PATH);
            } while (FindNextFileA(h, &fd));
            FindClose(h);
        }
        for (k = 1; k < cnt; k++)
            for (j = k; j > 0 && lstrcmpiA(names[j - 1], names[j]) > 0; j--) {
                char t[MAX_PATH]; lstrcpyA(t, names[j]); lstrcpyA(names[j], names[j - 1]); lstrcpyA(names[j - 1], t);
            }
        for (k = 0; k < cnt; k++) {
            _snprintf(path, sizeof(path), "%smods\\netmod\\tables\\%s", g_root, names[k]);
            path[sizeof(path) - 1] = 0;
            ramp_file(m, path);
        }
    }
    for (k = 0; k < 65536; k++) ncls += g_rampcls[k];
    if (ncls) {
        DWORD a, b;
        g_a5f2 = (DWORD)m + 0x1a5f2;                                 /* set before any call can reach the thunk */
        a = retarget_call(m, 0x13643, 0x1a5f2, (void *)ramp_class_thunk);
        b = a ? retarget_call(m, 0x136ce, 0x1a5f2, (void *)ramp_class_thunk) : 0;
        if (!(a && b)) {
            if (a) write_rel(m + 0x13643, 0xE8, (void *)a, 5);      /* undo the first: all or nothing */
            logf("### ramp: classifier call sites do not match the shipped bytes - class mapping OFF");
            ncls = 0;
        }
    }
    logf("ramp: %d slot(s) changed, %d line(s) refused, %d variant id(s) classified as their base", g_n_ramp_ok,
         g_n_ramp_bad, ncls);
    return g_n_ramp_ok;
}
/* ==== NETRAMP end ======================================================================================= */
#include "sc3netmod_tmpl.c"         /* task multitile: TMPL, multi-cell templates (SC3NETMOD_TMPL=0) */
#include "sc3netmod_rbt.c"          /* task roundabout3: RBT, automatic 2x2 roundabouts (SC3NETMOD_RBT=0) */
#include "sc3netmod_dav.c"          /* task diagave: DAV, automatic diagonal avenues on RBT's hooks (SC3NETMOD_DAV=0) */
#include "sc3netmod_lanes.c"        /* task lanedensity: road density honours turn matrices (SC3NETMOD_LANEDENSITY) */

/* ============================================================ arming */

static DWORD WINAPI watcher(LPVOID param) {
    BYTE *m;
    int cross = !env_off("SC3NETMOD_CROSS"), nc = 0, sv = 0, ld = 0, k;
    (void)param;
    g_savebase = !env_off("SC3NETMOD_SAVEBASE");
    while (!(m = (BYTE *)GetModuleHandleA("SIMNTWRK.DLL"))) Sleep(1);
    table_load();
    netramp_install(m);                                          /* NETRAMP: table slots + classifier (section 4) */
    tmpl_install(m);                                             /* TMPL: multi-cell templates (task multitile) */
    CreateThread(NULL, 0, lanedensity_thread, NULL, 0, NULL);   /* LANEDENSITY (task lanedensity) */
    if (!g_nvariants) { logf("### READY: no variants in the table, nothing patched"); return 0; }
    rbt_install(m);                                              /* RBT: automatic 2x2 roundabouts (task roundabout3) */
    g_wopen = (PFN_WOpen)(m + 0x26129);
    g_ropen = (PFN_ROpen)(m + 0x25f0d);
    g_stream = (PFN_Stream)(m + 0x262a3);
    g_close = (PFN_Close)(m + 0x26264);
    g_fail = (PFN_Fail)(m + 0x262b2);
    if (cross) nc = patch_cross(m);
    if (g_savebase) sv = patch_save(m);
    ld = patch_load(m);
    bridge_patch(m);                 /* task netbridge, sc3netmod_bridge.c */
    logf("### READY: SIMNTWRK at 0x%08lX, variants=%d, cross=%d (%d site(s)), savebase=%d (%s), load=%s",
         (DWORD)m, g_nvariants, cross, nc, g_savebase, sv ? "patched" : "off", ld ? "patched" : "FAILED");
    for (k = 0;; k++) {
        Sleep(500);
        tmpl_keys();                     /* task multitile: subclass the game window once it exists */
        rbt_window();                    /* task roundabout3: the window that runs the load pass */
        if (k % 20 != 19) continue;
        tmpl_stats();
        rbt_stats();
        dav_stats();                     /* task diagave */
        if (g_n_cross_map || g_n_pred_map || g_n_saved_base)
            logf("stats: crossing-switch lookups mapped=%ld, predicate id reads mapped=%ld, tiles saved as base (last save)=%ld",
                 g_n_cross_map, g_n_pred_map, g_n_saved_base);
        bridge_stats();                  /* task netbridge */
    }
}

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        char path[MAX_PATH];
        g_self = (HMODULE)inst;
        DisableThreadLibraryCalls(inst);
        InitializeCriticalSection(&g_lock);
        QueryPerformanceFrequency(&g_freq);
        QueryPerformanceCounter(&g_t0);
        if (!GetEnvironmentVariableA("SC3NETMOD_LOG", path, sizeof(path)))
            self_path(path, sizeof(path), "sc3netmod.log");
        g_log = CreateFileA(path, GENERIC_WRITE, FILE_SHARE_READ, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        logf("### sc3netmod loaded");
        root_init();
        overlay_init();
        CreateThread(NULL, 0, watcher, NULL, 0, NULL);
    }
    return TRUE;
}
