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
 * Env: SC3NETMOD_LOG=<path> (default sc3netmod.log beside the DLL), SC3NETMOD_TABLE=<path> (variant table).
 */

#include <windows.h>
#include <stdio.h>
#include <string.h>

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
static int  g_nvariants;

static void table_load(void) {
    char path[MAX_PATH], line[256], *slash;
    FILE *f;
    if (!GetEnvironmentVariableA("SC3NETMOD_TABLE", path, sizeof(path))) {
        /* Apps\SC3U.exe -> Apps\Res\netmod_variants.txt (installed with the variant's data files) */
        if (!GetModuleFileNameA(NULL, path, sizeof(path))) return;
        slash = strrchr(path, '\\');
        if (!slash) return;
        slash[1] = 0;
        lstrcatA(path, "Res\\netmod_variants.txt");
    }
    f = fopen(path, "r");
    if (!f) { logf("table: %s not found, no variants", path); return; }
    while (fgets(line, sizeof(line), f)) {
        unsigned long v, b;
        char *p = line;
        while (*p == ' ' || *p == '\t') p++;
        if (*p == '#' || *p == ';' || *p == '\r' || *p == '\n' || !*p) continue;
        if (sscanf(p, "%lu %lu", &v, &b) != 2 || v == 0 || v > 0xffff || b == 0 || b > 0xffff || v == b) {
            logf("table: bad line '%s'", p);
            continue;
        }
        if (!g_base[v]) g_nvariants++;
        g_base[v] = (WORD)b;
        logf("table: variant %lu -> base %lu", v, b);
    }
    fclose(f);
    logf("table: %s, %d variant(s)", path, g_nvariants);
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

/* record = the 8-byte tile record object; +4 word0 (coord, state), +8 word1 (id, props) */
static void __stdcall save_rec(BYTE *rec) {
    DWORD w1 = *(DWORD *)(rec + 8), id = w1 & 0xffff;
    if (!g_base[id]) return;
    *(DWORD *)(rec + 8) = (w1 & 0xffff0000) | g_base[id];
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

/* ============================================================ arming */

static DWORD WINAPI watcher(LPVOID param) {
    BYTE *m;
    int cross = !env_off("SC3NETMOD_CROSS"), nc = 0, sv = 0, ld = 0;
    (void)param;
    g_savebase = !env_off("SC3NETMOD_SAVEBASE");
    while (!(m = (BYTE *)GetModuleHandleA("SIMNTWRK.DLL"))) Sleep(1);
    table_load();
    if (!g_nvariants) { logf("### READY: no variants in the table, nothing patched"); return 0; }
    g_wopen = (PFN_WOpen)(m + 0x26129);
    g_ropen = (PFN_ROpen)(m + 0x25f0d);
    g_stream = (PFN_Stream)(m + 0x262a3);
    g_close = (PFN_Close)(m + 0x26264);
    g_fail = (PFN_Fail)(m + 0x262b2);
    if (cross) nc = patch_cross(m);
    if (g_savebase) sv = patch_save(m);
    ld = patch_load(m);
    logf("### READY: SIMNTWRK at 0x%08lX, variants=%d, cross=%d (%d site(s)), savebase=%d (%s), load=%s",
         (DWORD)m, g_nvariants, cross, nc, g_savebase, sv ? "patched" : "off", ld ? "patched" : "FAILED");
    for (;;) {
        Sleep(10000);
        if (g_n_cross_map || g_n_pred_map || g_n_saved_base)
            logf("stats: crossing-switch lookups mapped=%ld, predicate id reads mapped=%ld, tiles saved as base (last save)=%ld",
                 g_n_cross_map, g_n_pred_map, g_n_saved_base);
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
        CreateThread(NULL, 0, watcher, NULL, 0, NULL);
    }
    return TRUE;
}
