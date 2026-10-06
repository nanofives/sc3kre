/* sc3bigcity.c - "Enorme" city size mod for SimCity 3000 Unlimited.
 *
 * Adds a fifth size option to the New City dialog, plus a slider that picks the map side
 * from 512 to 1024 tiles in steps of 128. The map stays square. Shipped sizes 64/128/192/256
 * are untouched.
 *
 * Everything is applied in memory. No game file is modified. Delivery is the same as the
 * other mods: bigcity_launch.exe starts SC3U.exe suspended and injects this DLL.
 *
 * WHAT IT CHANGES (all evidence in re/analysis/formats/BIGGER_CITIES.md):
 *
 *  1. SIMDIRT terrain vertex buffer (the crash at N > 256). The singleton's +0x2c buffer is a
 *     ushort per vertex, sized and strided for N=256 at 12 immediates. We size it ONCE for the
 *     maximum (1024): size 2*1025*1025, stride 1025, corner disp 2*(1025+1). Every access to the
 *     buffer goes through one of those 12 sites (all 13 DAT_10025bac+0x2c references checked), so
 *     a fixed max layout is correct for every map size, shipped ones included, and removes the
 *     row aliasing that a size-only patch leaves at N > 256.
 *
 *  2. SIMINIT FUN_1000c09c writes N into all three city-descriptor extents, one of which (+0x40)
 *     is the VERTICAL extent. Occupant Z is packed into 8 bits with no mask (SIMGEOM 0x1001d1bf),
 *     so a vertical extent above 256 can spill into the orientation bits. We clamp +0x40 to 256,
 *     which is exactly what every shipped 256 city already gets. N <= 256 is unchanged.
 *
 *  3. SIMUI FUN_1005eb40, the New City OK path. The "else" arm at 0x1005ecf8
 *     (mov [esi+0x174], 0x100) is replaced by a jump to size_hook: if the selected radio is ours,
 *     +0x174 = the slider's size, otherwise 256 as shipped. The saved radio id ([edi+8]) is put
 *     back to the shipped 256 id so the game's own settings never hold an id it does not know.
 *
 *  4. UI: when the size option group (0x2552484e) appears, add our radio to it, and a slider +
 *     size label to the dialog. Polled from the GZGraphicD heartbeat (game thread), like
 *     sc3slider.c. The dialog object is reused across openings; we detect our own radio by id.
 *
 * Helpers (logging, GZ tree walk, widget recipes, detour installer) are copied from
 * sc3slider.c, which copied them from sc3probe.c. See re/analysis/PREFS_UI.md for the widget API.
 *
 * Build: re/harness/build_bigcity.ps1 (32-bit, must match SC3U.exe).
 */

#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ============================================================ logging */

static CRITICAL_SECTION g_lock;
static HANDLE g_log = INVALID_HANDLE_VALUE;
static LARGE_INTEGER g_freq, g_t0;
static HMODULE g_self;

static void logf(const char *fmt, ...) {
    char buf[2048];
    char line[2176];
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

    n = _snprintf(line, sizeof(line) - 1, "[%9.3f ms][tid %04lx] %s\r\n",
                  ms, GetCurrentThreadId(), buf);
    if (n < 0) return;
    line[sizeof(line) - 1] = 0;

    EnterCriticalSection(&g_lock);
    if (g_log != INVALID_HANDLE_VALUE)
        WriteFile(g_log, line, (DWORD)n, &wrote, NULL);
    LeaveCriticalSection(&g_lock);
    OutputDebugStringA(line);
}

/* sibling file of this DLL */
static void self_path(char *out, int cap, const char *leaf) {
    char *slash;
    if (!GetModuleFileNameA(g_self, out, cap)) { out[0] = 0; return; }
    slash = strrchr(out, '\\');
    if (slash) slash[1] = 0; else out[0] = 0;
    lstrcatA(out, leaf);
}

static void log_open(void) {
    char path[MAX_PATH];
    /* The game's cwd is Apps\, so a relative default would land there. Default beside the DLL. */
    if (!GetEnvironmentVariableA("SC3BIGCITY_LOG", path, sizeof(path)))
        self_path(path, sizeof(path), "sc3bigcity.log");
    g_log = CreateFileA(path, GENERIC_WRITE, FILE_SHARE_READ, NULL,
                        CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
}

/* ============================================================ config (bigcity.ini) */

#define BIG_MIN   512
#define BIG_MAX   1024
#define BIG_STEP  128

static volatile LONG g_big_n = BIG_MIN;      /* current slider size */
static int  g_last_big;                     /* the last New City used our option */
static char g_caption[64] = "Enorme";
static int  g_fix_vertical = 1;
static int  g_windowed = 1;

static int snap_size(int v) {
    int n = BIG_MIN + ((v - BIG_MIN + BIG_STEP / 2) / BIG_STEP) * BIG_STEP;
    if (n < BIG_MIN) n = BIG_MIN;
    if (n > BIG_MAX) n = BIG_MAX;
    return n;
}

static void ini_read(void) {
    char path[MAX_PATH];
    self_path(path, sizeof(path), "bigcity.ini");
    if (!path[0]) return;
    g_big_n = snap_size(GetPrivateProfileIntA("city", "size", BIG_MIN, path));
    g_last_big = GetPrivateProfileIntA("city", "selected", 0, path) ? 1 : 0;
    GetPrivateProfileStringA("city", "caption", "Enorme", g_caption, sizeof(g_caption), path);
    g_fix_vertical = GetPrivateProfileIntA("fixes", "clamp_vertical", 1, path) ? 1 : 0;
    g_windowed = GetPrivateProfileIntA("display", "windowed", 1, path) ? 1 : 0;
}

static void ini_write(int n, int selected) {
    char path[MAX_PATH], buf[16];
    self_path(path, sizeof(path), "bigcity.ini");
    if (!path[0]) return;
    _snprintf(buf, sizeof(buf) - 1, "%d", n); buf[sizeof(buf) - 1] = 0;
    WritePrivateProfileStringA("city", "size", buf, path);
    WritePrivateProfileStringA("city", "selected", selected ? "1" : "0", path);
}

/* ============================================================ in-memory code patching */

static int write_code(BYTE *p, const void *src, int n) {
    DWORD old;
    if (!VirtualProtect(p, n, PAGE_EXECUTE_READWRITE, &old)) return 0;
    memcpy(p, src, n);
    VirtualProtect(p, n, old, &old);
    FlushInstructionCache(GetCurrentProcess(), p, n);
    return 1;
}

static int write_jmp(BYTE *at, void *to, int len) {
    BYTE b[16];
    int i;
    if (len < 5 || len > 16) return 0;
    b[0] = 0xE9;
    *(DWORD *)(b + 1) = (DWORD)to - (DWORD)(at + 5);
    for (i = 5; i < len; i++) b[i] = 0x90;
    return write_code(at, b, len);
}

/* ---- 1. SIMDIRT terrain buffer, fixed max layout */

#define DIRT_STRIDE   (BIG_MAX + 1)                          /* 1025 */
#define DIRT_SIZE     (2 * DIRT_STRIDE * DIRT_STRIDE)        /* 0x201002 */
#define DIRT_CORNER   (2 * (DIRT_STRIDE + 1))                /* 0x804 */

typedef struct { DWORD rva; BYTE prefix[4]; int plen; DWORD shipped; DWORD value; } SITE;

static const SITE g_dirt_sites[] = {
    /* SIZE: push imm32 */
    { 0x166E0, {0x68}, 1, 0x20402, DIRT_SIZE },
    { 0x132C3, {0x68}, 1, 0x20402, DIRT_SIZE },
    { 0x14159, {0x68}, 1, 0x20402, DIRT_SIZE },
    { 0x1469F, {0x68}, 1, 0x20402, DIRT_SIZE },
    /* STRIDE: imul r, r, imm32 */
    { 0x12D0F, {0x69, 0xc9}, 2, 0x101, DIRT_STRIDE },
    { 0x12D2D, {0x69, 0xc9}, 2, 0x101, DIRT_STRIDE },
    { 0x12D4E, {0x69, 0xc9}, 2, 0x101, DIRT_STRIDE },
    { 0x12D6C, {0x69, 0xc9}, 2, 0x101, DIRT_STRIDE },
    { 0x130B0, {0x69, 0xd2}, 2, 0x101, DIRT_STRIDE },
    { 0x13FC0, {0x69, 0xc9}, 2, 0x101, DIRT_STRIDE },
    { 0x14512, {0x69, 0xd2}, 2, 0x101, DIRT_STRIDE },
    /* CORNER: mov word [edx+ecx*2+disp32], ax */
    { 0x12D3E, {0x66, 0x89, 0x84, 0x4a}, 4, 0x204, DIRT_CORNER },
};

/* Terrain generator subdivision depth. FUN_10017c2d calls the midpoint subdivision
 * FUN_100177b7(this,0,0,W-1,H-1,min(W-1,H-1),8) at 0x10017f3b; the `push 8` is at 0x10017f2f.
 * Depth 8 = 9 rounds = every vertex only while N <= 512. Above that, 3/4 of the vertices are
 * never written and stay at height 0: a pit on every tile (the "spikes", owner 2026-10-06).
 * The 10 bytes 0x10017f2f..0x10017f38 (push 8; push [eax]; push ecx; push edx; push 0; push 0)
 * are replaced by a jump to depth_hook, which pushes 9 when N > 512 and the stock 8 otherwise,
 * so every shipped size (and the dialog's regenerate buttons) generate exactly as before. */
static DWORD g_depth_ret;            /* SIMDIRT+0x17f39 (mov ecx, esi; call) */

/* River density. FUN_100187da carves the river at a fixed 1024 Bezier samples
 * (alloc push 0x2000 @0x10018831, count push 0x400 @0x10018a51, loop cmp 0x400 @0x10018b37,
 * height ramp shr 10 @0x10018aab). Each sample carves a short cross, so on a 1024 map the
 * samples land more than a tile apart and the river breaks into dashes (owner screenshot
 * 2026-10-06). The sampler divides by its count (FUN_10018c30: fdivr by the count arg), so a
 * larger count is safe. 4096 samples when N > 512, stock 1024 otherwise. Rivers are carved after
 * the subdivision, inside the same generator call, so depth_hook sets it for the current map. */
typedef struct { DWORD rva; int off; DWORD stock; DWORD big; int width; } RIVERSITE;
static const RIVERSITE g_river[] = {
    { 0x18831, 1, 0x2000, 0x8000, 4 },   /* push imm32: buffer bytes (8 per sample) */
    { 0x18a51, 1, 0x400,  0x1000, 4 },   /* push imm32: sample count */
    { 0x18b37, 3, 0x400,  0x1000, 4 },   /* cmp [ebp+8], imm32: loop bound */
    { 0x18aab, 2, 10,     12,     1 },   /* shr ebx, imm8: ramp over the samples */
};
static BYTE *g_dirt_base;
static int   g_river_big = -1;

static void __stdcall set_river(DWORD n) {
    int big = n > 0x200, i;
    if (!g_dirt_base || big == g_river_big) return;
    for (i = 0; i < 4; i++) {
        BYTE *p = g_dirt_base + g_river[i].rva + g_river[i].off;
        DWORD v = big ? g_river[i].big : g_river[i].stock;
        write_code(p, &v, g_river[i].width);
    }
    g_river_big = big;
    logf("### DIRT: N=%lu -> depth %d, river samples %d", n, big ? 9 : 8, big ? 4096 : 1024);
}

static int check_river(BYTE *b) {
    static const BYTE pre[4][3] = { {0x68}, {0x68}, {0x81, 0x7d, 0x08}, {0xc1, 0xeb} };
    static const int plen[4] = { 1, 1, 3, 2 };
    int i;
    for (i = 0; i < 4; i++) {
        BYTE *p = b + g_river[i].rva;
        DWORD v = 0;
        memcpy(&v, p + g_river[i].off, g_river[i].width);
        if (memcmp(p, pre[i], plen[i]) != 0 || v != g_river[i].stock) {
            logf("### DIRT: river site +0x%05lX unexpected - river density not changed", g_river[i].rva);
            return 0;
        }
    }
    g_dirt_base = b;
    return 1;
}

__declspec(naked) static void depth_hook(void) {
    __asm {
        pushad
        push dword ptr [eax]
        call set_river
        popad
        cmp dword ptr [eax], 0x200
        ja deep
        push 8
        jmp args
    deep:
        push 9
    args:
        push dword ptr [eax]
        push ecx
        push edx
        push 0
        push 0
        jmp dword ptr [g_depth_ret]
    }
}

static int patch_depth(BYTE *b) {
    static const BYTE expect[] = { 0x6a, 0x08, 0xff, 0x30, 0x51, 0x52, 0x6a, 0x00, 0x6a, 0x00 };
    BYTE *p = b + 0x17f2f;
    if (memcmp(p, expect, sizeof(expect)) != 0) { logf("### DIRT: depth site unexpected"); return 0; }
    check_river(b);
    g_depth_ret = (DWORD)b + 0x17f39;
    if (!write_jmp(p, (void *)depth_hook, 10)) return 0;
    logf("### DIRT: terrain subdivision depth 8 -> 9 when N > 512 (SIMDIRT+0x17f2f)");
    return 1;
}

static int patch_simdirt(HMODULE m) {
    int i, n = sizeof(g_dirt_sites) / sizeof(g_dirt_sites[0]);
    BYTE *b = (BYTE *)m;
    /* verify all first: never half-patch */
    for (i = 0; i < n; i++) {
        const SITE *s = &g_dirt_sites[i];
        DWORD cur = *(DWORD *)(b + s->rva + s->plen);
        if (memcmp(b + s->rva, s->prefix, s->plen) != 0 || (cur != s->shipped && cur != s->value)) {
            logf("### DIRT: site +0x%05lX unexpected (val 0x%lX) - NOT patching SIMDIRT", s->rva, cur);
            return 0;
        }
    }
    for (i = 0; i < n; i++) {
        const SITE *s = &g_dirt_sites[i];
        DWORD v = s->value;
        if (!write_code(b + s->rva + s->plen, &v, 4)) { logf("### DIRT: write failed"); return 0; }
    }
    if (!patch_depth(b)) return 0;
    logf("### DIRT: 12 sites -> size 0x%X stride %d corner 0x%X (max map %d)",
         DIRT_SIZE, DIRT_STRIDE, DIRT_CORNER, BIG_MAX);
    return 1;
}

/* ---- 2. SIMINIT vertical extent clamp */

__declspec(naked) static void dims_hook(void) {
    __asm {
        mov eax, [esp + 4]
        mov [ecx + 0x3c], eax
        mov [ecx + 0x44], eax
        cmp eax, 0x100
        jbe keep
        mov eax, 0x100
    keep:
        mov [ecx + 0x40], eax
        ret 4
    }
}

static int patch_siminit(HMODULE m) {
    static const BYTE expect[] = { 0x8b, 0x44, 0x24, 0x04, 0x89, 0x41, 0x3c, 0x89, 0x41, 0x40,
                                   0x89, 0x41, 0x44, 0xc2, 0x04, 0x00 };
    BYTE *p = (BYTE *)m + 0xc09c;
    if (memcmp(p, expect, sizeof(expect)) != 0) {
        logf("### DIMS: SIMINIT+0xc09c unexpected bytes - vertical clamp not installed");
        return 0;
    }
    if (!write_jmp(p, (void *)dims_hook, 5)) return 0;
    logf("### DIMS: SIMINIT+0xc09c -> vertical extent clamped to 256");
    return 1;
}

/* ---- 3. SIMUI New City size arm */

#define RADIO_256_ID   0x25524852
#define SIZE_GROUP_ID  0x2552484e
#define BIG_RADIO_ID   0x2552485b
#define BIG_SLIDER_ID  0x2552485c
#define IID_OPTGROUP   0xa1336cc0
#define IID_SLIDER     0x21325207

static DWORD g_simui_ret;            /* SIMUI+0x5ed26, where every size arm rejoins */
static volatile LONG g_last_created; /* size handed to the generator by the last OK */

typedef int (__fastcall *PFN_GetChildAs)(void *, void *, DWORD, DWORD, void **);
typedef int (__fastcall *PFN_GetVal)(void *, void *);
typedef int (__fastcall *PFN_Rel)(void *, void *);

static void *gz_vslot(void *obj, unsigned off);

/* Called from size_hook on the game thread with the dialog object. Reads the slider directly so
   a drag immediately before OK is never lost to the 10 Hz poll. */
static int __stdcall big_resolve(void *dlg) {
    PFN_GetChildAs get = (PFN_GetChildAs)gz_vslot(dlg, 0x80);
    void *s = NULL;
    int n = g_big_n;
    if (get && get(dlg, NULL, BIG_SLIDER_ID, IID_SLIDER, &s) && s && !IsBadReadPtr(s, 4)) {
        PFN_GetVal gv = (PFN_GetVal)gz_vslot(s, 0x10);
        PFN_Rel   rl = (PFN_Rel)gz_vslot(s, 0x08);
        if (gv) n = snap_size(gv(s, NULL));
        if (rl) rl(s, NULL);
    }
    g_big_n = n;
    g_last_created = n;
    ini_write(n, 1);
    logf("### SIZE: New City OK with \"%s\" -> %d x %d", g_caption, n, n);
    return n;
}

static void __stdcall big_not_ours(void) {
    g_last_created = 256;
    if (g_last_big) { g_last_big = 0; ini_write(g_big_n, 0); }
}

/* At entry: eax = selected radio id - 0x25524852, esi = dialog, edi = settings struct. */
__declspec(naked) static void size_hook(void) {
    __asm {
        cmp eax, (BIG_RADIO_ID - RADIO_256_ID)
        jne shipped
        pushad
        push esi
        call big_resolve
        mov [esp + 28], eax                  /* into the saved EAX slot */
        popad
        mov dword ptr [esi + 0x174], eax
        mov dword ptr [edi + 8], RADIO_256_ID
        jmp dword ptr [g_simui_ret]
    shipped:
        pushad
        call big_not_ours
        popad
        mov dword ptr [esi + 0x174], 0x100
        jmp dword ptr [g_simui_ret]
    }
}

static int patch_simui(HMODULE m) {
    static const BYTE expect[] = { 0xc7, 0x86, 0x74, 0x01, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00 };
    BYTE *p = (BYTE *)m + 0x5ecf8;
    if (memcmp(p, expect, sizeof(expect)) != 0) {
        logf("### SIZE: SIMUI+0x5ecf8 unexpected bytes (patched on disk?) - option disabled");
        return 0;
    }
    g_simui_ret = (DWORD)m + 0x5ed26;
    if (!write_jmp(p, (void *)size_hook, 10)) return 0;
    logf("### SIZE: SIMUI+0x5ecf8 hooked (radio 0x%08X -> slider size)", BIG_RADIO_ID);
    return 1;
}

/* ---- 5. SIMSPR 16-bit cell anchors (camera refusing every step, zoom 3/4 blank at N > 256).
 * Every 0x14-byte cell record keeps its anchor as BYTES (+8 X, +9 Y); record bytes +0x12/+0x13
 * are unused and now hold the high bytes. 8 writes + 48 reads, all in SIMSPR, are detoured.
 * The table and the reasoning are generated by re/tools/gen_anchor16.py. All-or-nothing: if any
 * site differs from the shipped bytes (another mod, a patched DLL), nothing is installed. */
#include "anchor16_sites.h"

static int patch_anchor16(HMODULE m) {
    BYTE *b = (BYTE *)m, *pool, *c;
    int i, n = sizeof(g_anchor_sites) / sizeof(g_anchor_sites[0]), total = 0;
    for (i = 0; i < n; i++) {
        const ANCHORSITE *s = &g_anchor_sites[i];
        if (memcmp(b + s->rva, s->orig, s->origlen) != 0) {
            logf("### ANCHOR: SIMSPR+0x%05lX differs from shipped - 16-bit anchors NOT installed", s->rva);
            return 0;
        }
        total += s->cavelen + 5 + 15;
    }
    pool = (BYTE *)VirtualAlloc(NULL, total, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!pool) { logf("### ANCHOR: VirtualAlloc failed"); return 0; }
    c = pool;
    for (i = 0; i < n; i++) {
        const ANCHORSITE *s = &g_anchor_sites[i];
        int k;
        memcpy(c, s->cave, s->cavelen);
        for (k = 0; k < s->nrel; k++) {
            BYTE *at = c + s->relofs[k];
            *(DWORD *)at = (DWORD)(b + s->reltgt[k]) - (DWORD)(at + 4);
        }
        c[s->cavelen] = 0xE9;
        *(DWORD *)(c + s->cavelen + 1) = (DWORD)(b + s->rva + s->len) - (DWORD)(c + s->cavelen + 5);
        if (!write_jmp(b + s->rva, c, s->len)) { logf("### ANCHOR: write failed at +0x%05lX", s->rva); return 0; }
        c += (s->cavelen + 5 + 15) & ~15;
    }
    FlushInstructionCache(GetCurrentProcess(), pool, total);
    logf("### ANCHOR: %d SIMSPR sites detoured - cell anchors are 16-bit (+0x12/+0x13 high bytes)", n);
    return 1;
}

/* ============================================ GZ window-tree helpers (from sc3slider.c) */

typedef void * (__cdecl    *PFN_GetWinMgr)(void);
typedef void * (__fastcall *PFN_WM_Get)(void *);

static void *g_gz_found;

static void *gz_winmgr(void) {
    static void *cached;
    PFN_GetWinMgr get;
    if (cached) return cached;
    get = (PFN_GetWinMgr)((BYTE *)GetModuleHandleA(NULL) + 0x703A7);
    if (IsBadCodePtr((FARPROC)get)) return NULL;
    cached = get();
    if (cached && IsBadReadPtr(cached, 4)) cached = NULL;
    return cached;
}

static void *gz_vslot(void *obj, unsigned off) {
    void **vt;
    if (!obj || IsBadReadPtr(obj, 4)) return NULL;
    vt = *(void ***)obj;
    if (!vt || IsBadReadPtr(vt, off + 4)) return NULL;
    return vt[off / 4];
}

static int gz_find_by_id_quiet(void *win, DWORD id, int depth) {
    DWORD *w = (DWORD *)win;
    DWORD sentinel, node;
    int guard = 0;
    if (!win || IsBadReadPtr(win, 0xd8) || depth > 12) return 0;
    if (w[0x10 / 4] == id) { g_gz_found = win; return 1; }
    sentinel = w[0x34 / 4];
    if (!sentinel || IsBadReadPtr((void *)sentinel, 0xc)) return 0;
    for (node = *(DWORD *)sentinel;
         node && node != sentinel && guard < 400;
         node = *(DWORD *)node, guard++) {
        if (IsBadReadPtr((void *)node, 0xc)) break;
        if (gz_find_by_id_quiet(*(void **)(node + 8), id, depth + 1)) return 1;
    }
    return 0;
}

static void *gz_root(void) {
    void *wm = gz_winmgr();
    PFN_WM_Get getroot = wm ? (PFN_WM_Get)gz_vslot(wm, 0x0c) : NULL;
    return getroot ? getroot(wm) : NULL;
}

static void *find_id(void *from, DWORD id) {
    g_gz_found = NULL;
    if (!from || !gz_find_by_id_quiet(from, id, 0)) return NULL;
    return g_gz_found;
}

static int win_visible(void *w) {
    return w && !IsBadReadPtr(w, 0xa4) && (*(DWORD *)((BYTE *)w + 0xa0) & 1);
}

static void log_rect(const char *tag, void *w) {
    int *l;
    if (!w || IsBadReadPtr(w, 0x90)) return;
    l = (int *)((BYTE *)w + 0x80);
    logf("### UI: %-8s id 0x%08lX local %d,%d,%d,%d  abs %d,%d,%d,%d", tag,
         *(DWORD *)((BYTE *)w + 0x10), l[0], l[1], l[2], l[3],
         ((int *)((BYTE *)w + 0x14))[0], ((int *)((BYTE *)w + 0x14))[1],
         ((int *)((BYTE *)w + 0x14))[2], ((int *)((BYTE *)w + 0x14))[3]);
}

static void log_children(const char *tag, void *win) {
    DWORD sentinel, node;
    int guard = 0;
    if (!win || IsBadReadPtr(win, 0xd8)) return;
    log_rect(tag, win);
    sentinel = *(DWORD *)((BYTE *)win + 0x34);
    if (!sentinel || IsBadReadPtr((void *)sentinel, 0xc)) return;
    for (node = *(DWORD *)sentinel; node && node != sentinel && guard < 100;
         node = *(DWORD *)node, guard++) {
        if (IsBadReadPtr((void *)node, 0xc)) break;
        log_rect("  child", *(void **)(node + 8));
    }
}

/* ============================================ widgets (recipes from PREFS_UI.md) */

#define SIMUI_WIDGET_FACTORY_RVA 0x85065
#define SIMUI_STR_CTOR_RVA       0x5eb6
#define SIMUI_STR_DTOR_RVA       0x6057
#define SIMUI_COLOUR_SVC_RVA     0x85039

typedef void *(__cdecl    *PFN_Factory)(void);
typedef void *(__fastcall *PFN_CreateSlider)(void *, void *, DWORD, int, int, int, int);
typedef void *(__fastcall *PFN_GetWin)(void *, void *);
typedef int   (__fastcall *PFN_SetInt)(void *, void *, int);
typedef int   (__fastcall *PFN_SetXY)(void *, void *, int, int);
typedef int   (__fastcall *PFN_AddChild)(void *, void *, void *);
typedef void *(__fastcall *PFN_StrCtor)(void *);
typedef void  (__fastcall *PFN_StrDtor)(void *);
typedef void  (__fastcall *PFN_StrSetChar)(void *, void *, const char *);
typedef void *(__fastcall *PFN_CreateLabel)(void *, void *, DWORD, void *);
typedef void *(__fastcall *PFN_GetFont)(void *, void *, int);
typedef WORD  (__fastcall *PFN_MakeColour)(void *, void *, int, int, int);
typedef void  (__fastcall *PFN_SetPtr)(void *, void *, void *);
typedef void  (__fastcall *PFN_SetWord)(void *, void *, WORD);
typedef int   (__fastcall *PFN_QI)(void *, void *, DWORD, void **);
typedef int   (__fastcall *PFN_AddOption)(void *, void *, DWORD, void *, int, int, int);
typedef int   (__fastcall *PFN_Select)(void *, void *, DWORD);
typedef int   (__fastcall *PFN_Void)(void *, void *);

/* A GZ string object (SIMUI PTR_FUN_100a2410 class, 5 dwords). */
typedef struct { BYTE b[0x20]; } GZSTR;

static int gzstr_init(GZSTR *s, const char *text) {
    HMODULE simui = GetModuleHandleA("SIMUI.DLL");
    PFN_StrCtor ctor;
    PFN_StrSetChar set;
    if (!simui) return 0;
    ctor = (PFN_StrCtor)((BYTE *)simui + SIMUI_STR_CTOR_RVA);
    memset(s, 0, sizeof(*s));
    ctor(s);
    set = (PFN_StrSetChar)gz_vslot(s, 0x10);
    if (!set) return 0;
    set(s, NULL, text);
    return 1;
}

static void gzstr_free(GZSTR *s) {
    HMODULE simui = GetModuleHandleA("SIMUI.DLL");
    if (simui) ((PFN_StrDtor)((BYTE *)simui + SIMUI_STR_DTOR_RVA))(s);
}

static void *factory(void) {
    HMODULE simui = GetModuleHandleA("SIMUI.DLL");
    return simui ? ((PFN_Factory)((BYTE *)simui + SIMUI_WIDGET_FACTORY_RVA))() : NULL;
}

/* place a created widget (factory interface) into parent at (x,y) with width w; releases it */
static int place_widget(void *parent, void *widget, int x, int y, int w) {
    PFN_GetWin getwin = (PFN_GetWin)gz_vslot(widget, 0x0c);
    void *win;
    int ok = 0;
    if (getwin) {
        PFN_SetInt setw;
        PFN_SetXY setxy;
        PFN_AddChild add;
        win = getwin(widget, NULL);
        setw = win ? (PFN_SetInt)gz_vslot(win, 0xb8) : NULL;
        if (setw && w > 0) setw(win, NULL, w);
        setxy = win ? (PFN_SetXY)gz_vslot(win, 0xcc) : NULL;
        if (setxy) setxy(win, NULL, x, y);
        add = (PFN_AddChild)gz_vslot(parent, 0x34);
        if (add && win) ok = add(parent, NULL, win);
        if (!ok && win) {
            PFN_Rel destroy = (PFN_Rel)gz_vslot(win, 0x28);
            if (destroy) destroy(win, NULL);
        }
    }
    { PFN_Rel rel = (PFN_Rel)gz_vslot(widget, 0x08); if (rel) rel(widget, NULL); }
    return ok;
}

static int add_slider(void *parent, int x, int y, int w) {
    void *fac = factory(), *sl;
    PFN_CreateSlider create = fac ? (PFN_CreateSlider)gz_vslot(fac, 0x50) : NULL;
    if (!create) return 0;
    sl = create(fac, NULL, BIG_SLIDER_ID, 1, BIG_MIN, BIG_MAX, g_big_n);
    if (!sl || IsBadReadPtr(sl, 4)) return 0;
    return place_widget(parent, sl, x, y, w);
}

static void label_text(void *labelwin, const char *text) {
    GZSTR s;
    PFN_SetPtr setcap = (PFN_SetPtr)gz_vslot(labelwin, 0x10c);
    if (!setcap || !gzstr_init(&s, text)) return;
    setcap(labelwin, NULL, &s);
    gzstr_free(&s);
}

/* ============================================ the dialog augmentation */

static int   g_ui_on;
static DWORD g_next_poll;
static int   g_shown_n = -1;
static int   g_aug_fail;

static void *group_iface(void *gwin) {
    PFN_QI qi = (PFN_QI)gz_vslot(gwin, 0x00);
    void *g = NULL;
    if (!qi || !qi(gwin, NULL, IID_OPTGROUP, &g) || !g || IsBadReadPtr(g, 4)) return NULL;
    return g;
}

static int group_selected(void *gwin) {
    void *g = group_iface(gwin);
    int id = 0;
    if (!g) return 0;
    { PFN_GetVal gv = (PFN_GetVal)gz_vslot(g, 0x30); if (gv) id = gv(g, NULL); }
    { PFN_Rel rl = (PFN_Rel)gz_vslot(g, 0x08); if (rl) rl(g, NULL); }
    return id;
}

static void group_select(void *gwin, DWORD id) {
    void *g = group_iface(gwin);
    if (!g) return;
    { PFN_Select sel = (PFN_Select)gz_vslot(g, 0x34); if (sel) sel(g, NULL, id); }
    { PFN_Rel rl = (PFN_Rel)gz_vslot(g, 0x08); if (rl) rl(g, NULL); }
}

/* Layout, from the measured New City dialog (639x365, run 1 log, verify/bigcity_option):
 *   size group 0x2552484E local 100,186,177,276; radios at x 8, rows 18 px from y 18
 *   checkboxes 0x25524854 (17,294) 0x25524855 (17,311); bottom bar 0x2552483C (4,330,635,364),
 *   OK 0x2552483D (589,331); column dividers 0x2552483A/B (y 39..326); right column x >= 232.
 * The left column has no free row, so the dialog grows by GROW px: the slider takes a new row
 * under the size group, and the two checkboxes + bottom bar + OK move down by GROW. */
#define DLG_W        639
#define DLG_H        365
#define GROW         24
#define RADIO_X      8
#define RADIO_Y      90          /* under "Grande" (0x25524852 at 72) */
#define RADIO_W      100
#define GROUP_W      112         /* 100 + 112 = 212 < the divider at 218 */
#define GROUP_H      108         /* 90 + 18 */
#define SLIDER_X     108
#define SLIDER_Y     298
#define SLIDER_W     100
#define SLIDER_H     20
#define PANEL_PAD    4

typedef int (__fastcall *PFN_SetWH)(void *, void *, int, int);

static int *lrect(void *w) { return (int *)((BYTE *)w + 0x80); }

static void win_move(void *w, int x, int y) {
    PFN_SetXY f = (PFN_SetXY)gz_vslot(w, 0xcc);
    if (f) f(w, NULL, x, y);
}

static void win_size(void *w, int cx, int cy) {
    PFN_SetWH f = (PFN_SetWH)gz_vslot(w, 0xc0);
    if (f) f(w, NULL, cx, cy);
}

/* move a dialog child to an absolute local y (idempotent: the dialog is reused across openings) */
static void child_to_y(void *dlg, DWORD id, int y) {
    void *w = find_id(dlg, id);
    if (w) win_move(w, lrect(w)[0], y);
}

static void child_height(void *dlg, DWORD id, int h) {
    void *w = find_id(dlg, id);
    if (w) win_size(w, lrect(w)[2] - lrect(w)[0], h);
}

static void radio_caption(void *gwin, int n) {
    void *r = find_id(gwin, BIG_RADIO_ID);
    char txt[48];
    if (!r) return;
    _snprintf(txt, sizeof(txt) - 1, "%s %d", g_caption, n); txt[sizeof(txt) - 1] = 0;
    label_text(r, txt);
}

static void relayout(void *dlg, void *gwin) {
    int *d = lrect(dlg);
    void *r = find_id(gwin, BIG_RADIO_ID);
    if (r) { win_move(r, RADIO_X, RADIO_Y); win_size(r, RADIO_W, 18); }
    win_size(gwin, GROUP_W, GROUP_H);
    child_to_y(dlg, 0x25524854, 294 + GROW);
    child_to_y(dlg, 0x25524855, 311 + GROW);
    child_to_y(dlg, 0x2552483C, 330 + GROW);
    child_to_y(dlg, 0x2552483D, 331 + GROW);
    child_height(dlg, 0x2552483A, 326 - 39 + GROW);
    child_height(dlg, 0x2552483B, 326 - 39 + GROW);
    if (d[3] - d[1] < DLG_H + GROW) {          /* grow once, keep it centred */
        win_size(dlg, DLG_W, DLG_H + GROW);
        win_move(dlg, d[0], d[1] - GROW / 2);
    }
    logf("### UI: dialog surface +0x58 = 0x%08lX", *(DWORD *)((BYTE *)dlg + 0x58));
}

/* An inset frame behind the slider. The New City dialog builds its own frames (the column
 * dividers 0x2552483A/B, the bottom bar 0x2552483C) through its +0xa4 subobject's vt+0x54 =
 * SIMUI FUN_1002d3c4(id, mode, sides, rect*): GZCOM frame window (CLSID 0xc2afa76e), the inset
 * box image 0x62e56a2c (the same one the Preferences audio sliders sit in), SetRect, AddChild.
 * We call that method on the live dialog, with the dividers' own (0, 0xf).
 * (A first attempt mirrored the Preferences recipe FUN_10058c80; in this context its GZCOM
 * create handed back a different object and the first call faulted - caught, see run7/run8.) */
#define BIG_PANEL_ID      0x2552485d
#define NEWCITY_DLG_VT    0xaa8e8          /* SIMUI primary vtable of the New City dialog */
typedef int (__fastcall *PFN_AddFrame)(void *, void *, DWORD, int, int, int *);

static int add_panel_raw(void *dlg, int x, int y, int w, int h) {
    HMODULE simui = GetModuleHandleA("SIMUI.DLL");
    BYTE *sub;
    PFN_AddFrame addframe;
    int r[4], ok;
    DWORD vt = *(DWORD *)dlg - (DWORD)simui;
    if (vt != NEWCITY_DLG_VT) { logf("### PANEL: dialog vtable SIMUI+0x%lX, expected 0x%X - no frame", vt, NEWCITY_DLG_VT); return 0; }
    sub = (BYTE *)dlg + 0xa4;
    addframe = (PFN_AddFrame)gz_vslot(sub, 0x54);
    if ((DWORD)addframe != (DWORD)simui + 0x2d3c4) { logf("### PANEL: +0xa4 vt+0x54 is not FUN_1002d3c4 - no frame"); return 0; }
    r[0] = x; r[1] = y; r[2] = x + w; r[3] = y + h;
    ok = addframe(sub, NULL, BIG_PANEL_ID, 0, 0xf, r);
    logf("### PANEL: frame %d,%d,%d,%d -> %d", r[0], r[1], r[2], r[3], ok);
    return ok;
}

static int add_panel(void *parent, int x, int y, int w, int h) {
    __try {
        return add_panel_raw(parent, x, y, w, h);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        logf("### PANEL: FAULT 0x%08lX while building the frame - skipped", GetExceptionCode());
        return 0;
    }
}

static int augment(void *gwin) {
    void *dlg = *(void **)((BYTE *)gwin + 0x3c);
    void *g = group_iface(gwin);
    GZSTR cap;
    int ok = 0;

    if (!g || !dlg || IsBadReadPtr(dlg, 0xd8)) { logf("### UI: no option group interface"); return 0; }
    log_children("dialog", dlg);
    log_children("group", gwin);

    if (gzstr_init(&cap, g_caption)) {
        PFN_AddOption addopt = (PFN_AddOption)gz_vslot(g, 0x38);
        if (addopt) ok = addopt(g, NULL, BIG_RADIO_ID, &cap, 0, 0, 0);
        gzstr_free(&cap);
    }
    { PFN_Rel rl = (PFN_Rel)gz_vslot(g, 0x08); if (rl) rl(g, NULL); }
    logf("### UI: add radio 0x%08X \"%s\" -> %s", BIG_RADIO_ID, g_caption, ok ? "OK" : "FAILED");
    if (!ok) return 0;

    if (!find_id(dlg, BIG_SLIDER_ID)) {
        int p1 = find_id(dlg, BIG_PANEL_ID) ? 1 :      /* frame first: children paint in order */
                 add_panel(dlg, SLIDER_X - PANEL_PAD, SLIDER_Y - PANEL_PAD,
                           SLIDER_W + 2 * PANEL_PAD, SLIDER_H + 2 * PANEL_PAD);
        int s1 = add_slider(dlg, SLIDER_X, SLIDER_Y, SLIDER_W);
        logf("### UI: slider frame -> %s", p1 ? "OK" : "FAILED");
        logf("### UI: slider at (%d,%d) w %d -> %s", SLIDER_X, SLIDER_Y, SLIDER_W, s1 ? "OK" : "FAILED");
    }
    relayout(dlg, gwin);
    radio_caption(gwin, g_big_n);
    log_children("dialog+", dlg);
    log_children("group+", gwin);
    if (g_last_big) group_select(gwin, BIG_RADIO_ID);
    g_shown_n = g_big_n;
    return 1;
}

static int read_slider(void *dlg, int *out) {
    PFN_GetChildAs get = (PFN_GetChildAs)gz_vslot(dlg, 0x80);
    void *s = NULL;
    if (!get || !get(dlg, NULL, BIG_SLIDER_ID, IID_SLIDER, &s) || !s || IsBadReadPtr(s, 4)) return 0;
    { PFN_GetVal gv = (PFN_GetVal)gz_vslot(s, 0x10); if (gv) *out = gv(s, NULL); }
    { PFN_Rel rl = (PFN_Rel)gz_vslot(s, 0x08); if (rl) rl(s, NULL); }
    return 1;
}

/* GZWIND window vt+0xf4 = SetFlags(flag, on) (GZWIND FUN_1001dfa7); flag 1 = visible.
   Called only on a change, so the window is not re-flagged 10 times a second. */
typedef int (__fastcall *PFN_SetFlag)(void *, void *, DWORD, int);

static void show_child(void *dlg, DWORD id, int show) {
    void *w = find_id(dlg, id);
    PFN_SetFlag f;
    if (!w || win_visible(w) == (show != 0)) return;
    f = (PFN_SetFlag)gz_vslot(w, 0xf4);
    if (f) f(w, NULL, 1, show ? 1 : 0);
    {   /* hiding does not repaint by itself (measured: the slider stayed drawn until the mouse
           moved), so invalidate the dialog, vt+0x154, as the resize mod does after a move */
        PFN_Void inval = (PFN_Void)gz_vslot(dlg, 0x154);
        if (inval) inval(dlg, NULL);
    }
}

static void ui_tick(void) {
    void *root, *gwin, *dlg;
    DWORD now = GetTickCount();
    int v = 0, n;
    if ((int)(now - g_next_poll) < 0) return;
    g_next_poll = now + 100;

    root = gz_root();
    gwin = find_id(root, SIZE_GROUP_ID);
    if (!gwin || !win_visible(gwin)) return;
    dlg = *(void **)((BYTE *)gwin + 0x3c);
    if (!dlg || IsBadReadPtr(dlg, 0xd8)) return;

    {
        void *r = find_id(gwin, BIG_RADIO_ID);
        if (!r) {                       /* first opening, or the game rebuilt the dialog */
            if (g_aug_fail < 3 && !augment(gwin)) g_aug_fail++;
            return;
        }
        if (lrect(r)[1] != RADIO_Y) {   /* the game re-laid the dialog out on reopening */
            logf("### UI: layout reset by the game (radio y %d), re-applying", lrect(r)[1]);
            relayout(dlg, gwin);
        }
    }
    {   /* the slider and its frame only show while "Enorme" is the chosen size (owner) */
        int show = group_selected(gwin) == BIG_RADIO_ID;
        show_child(dlg, BIG_PANEL_ID, show);
        show_child(dlg, BIG_SLIDER_ID, show);
    }
    if (!read_slider(dlg, &v)) return;
    n = snap_size(v);
    if (n != g_shown_n) {
        char txt[32];
        int first = (g_shown_n < 0);
        g_shown_n = n;
        g_big_n = n;
        _snprintf(txt, sizeof(txt) - 1, "%d x %d", n, n); txt[sizeof(txt) - 1] = 0;
        radio_caption(gwin, n);
        if (!first && group_selected(gwin) != BIG_RADIO_ID) group_select(gwin, BIG_RADIO_ID);
        logf("### UI: slider %d -> %s", v, txt);
    }
}

/* ============================== detour installer (from sc3slider.c, heartbeat only) */

static int modrm_len(const BYTE *p) {
    BYTE m = p[0];
    int mod = m >> 6, rm = m & 7, n = 1;
    if (mod == 3) return n;
    if (rm == 4) {
        BYTE sib = p[1];
        n++;
        if (mod == 0 && (sib & 7) == 5) n += 4;
    } else if (mod == 0 && rm == 5) {
        n += 4;
    }
    if (mod == 1) n += 1;
    else if (mod == 2) n += 4;
    return n;
}

static int insn_len(const BYTE *p, int *is_rel32) {
    BYTE op = p[0];
    *is_rel32 = 0;
    if (op == 0x66 || op == 0xF2 || op == 0xF3) {
        int r, l = insn_len(p + 1, &r);
        *is_rel32 = 0;
        return l ? l + 1 : 0;
    }
    if (op >= 0x50 && op <= 0x5F) return 1;
    if (op == 0x90 || op == 0xC3 || op == 0xC9) return 1;
    if (op == 0x6A) return 2;
    if (op == 0x68) return 5;
    if (op >= 0xB8 && op <= 0xBF) return 5;
    if (op >= 0xA0 && op <= 0xA3) return 5;
    if (op == 0xE8 || op == 0xE9) { *is_rel32 = 1; return 5; }
    if (op == 0xEB) return 2;
    if (op == 0xC2) return 3;
    if (op == 0x83 || op == 0x80) return 1 + modrm_len(p + 1) + 1;
    if (op == 0x81) return 1 + modrm_len(p + 1) + 4;
    if (op == 0xC6) return 1 + modrm_len(p + 1) + 1;
    if (op == 0xC7) return 1 + modrm_len(p + 1) + 4;
    switch (op) {
    case 0x00: case 0x01: case 0x02: case 0x03:
    case 0x08: case 0x09: case 0x0A: case 0x0B:
    case 0x20: case 0x21: case 0x22: case 0x23:
    case 0x28: case 0x29: case 0x2A: case 0x2B:
    case 0x30: case 0x31: case 0x32: case 0x33:
    case 0x38: case 0x39: case 0x3A: case 0x3B:
    case 0x84: case 0x85: case 0x88: case 0x89:
    case 0x8A: case 0x8B: case 0x8D: case 0x8F:
    case 0xFF:
        return 1 + modrm_len(p + 1);
    }
    return 0;
}

#define MAX_REL 4
static int steal_len(const BYTE *p, int *relofs, int *nrel) {
    int total = 0;
    *nrel = 0;
    while (total < 5) {
        int r, l = insn_len(p + total, &r);
        if (!l || total + l > 24) return 0;
        if (r && *nrel < MAX_REL) relofs[(*nrel)++] = total;
        total += l;
    }
    return total;
}

static BYTE *g_codepool;
static DWORD g_codeused;

static BYTE *pool_alloc(DWORD n) {
    BYTE *p;
    if (!g_codepool) {
        g_codepool = (BYTE *)VirtualAlloc(NULL, 4096, MEM_COMMIT | MEM_RESERVE,
                                          PAGE_EXECUTE_READWRITE);
        g_codeused = 0;
        if (!g_codepool) return NULL;
    }
    if (g_codeused + n > 4096) return NULL;
    p = g_codepool + g_codeused;
    g_codeused += (n + 15) & ~15u;
    return p;
}

static void __stdcall heartbeat(int idx, DWORD *f) {
    (void)idx; (void)f;
    if (g_ui_on) ui_tick();
}

static int install_heartbeat(BYTE *t) {
    int relofs[MAX_REL], nrel = 0, k;
    int len = steal_len(t, relofs, &nrel);
    BYTE *tr, *stub;
    if (!len) return 0;
    tr   = pool_alloc(len + 5);
    stub = pool_alloc(24);
    if (!tr || !stub) return 0;
    memcpy(tr, t, len);
    for (k = 0; k < nrel; k++) {
        int o = relofs[k];
        DWORD abs_target = (DWORD)(t + o + 5) + *(DWORD *)(t + o + 1);
        *(DWORD *)(tr + o + 1) = abs_target - (DWORD)(tr + o + 5);
    }
    tr[len] = 0xE9;
    *(DWORD *)(tr + len + 1) = (DWORD)(t + len) - (DWORD)(tr + len + 5);

    stub[0] = 0x60; stub[1] = 0x9C; stub[2] = 0x8B; stub[3] = 0xC4; stub[4] = 0x50;
    stub[5] = 0x68; *(DWORD *)(stub + 6) = 0;
    stub[10] = 0xE8; *(DWORD *)(stub + 11) = (DWORD)heartbeat - (DWORD)(stub + 15);
    stub[15] = 0x9D; stub[16] = 0x61;
    stub[17] = 0xE9; *(DWORD *)(stub + 18) = (DWORD)tr - (DWORD)(stub + 22);

    return write_jmp(t, stub, len);
}

/* ---- 0. windowed mode (owner rule: tests and play are windowed). Carved VERBATIM from
 * sc3resize.c (which carved them from sc3probe.c): the windowed flag + the fullscreen re-force
 * nop, and the 16bpp surface-format branch the windowed path needs. If sc3resize.dll is injected
 * too, the second application finds the patterns already changed and logs a mismatch, harmless. */
static void patch_windowed(HMODULE gz) {
    BYTE *p = (BYTE *)gz + 0x6cdac;         /* the windowed flag Init reads */
    BYTE *q = (BYTE *)gz + 0x117d6;         /* the fullscreen re-force store */
    DWORD old;
    if (VirtualProtect(p, 1, PAGE_READWRITE, &old)) {
        BYTE before = *p; *p = 1; VirtualProtect(p, 1, old, &old);
        logf("--- WINDOWED: GZGraphicD+0x6cdac = %u -> 1", before);
    } else logf("--- WINDOWED: VirtualProtect failed at +0x6cdac (%lu)", GetLastError());
    if (q[0] == 0xC6 && q[1] == 0x43 && q[2] == 0x48 && q[3] == 0x01) {
        DWORD o2;
        if (VirtualProtect(q, 4, PAGE_EXECUTE_READWRITE, &o2)) {
            q[0] = q[1] = q[2] = q[3] = 0x90; VirtualProtect(q, 4, o2, &o2);
            FlushInstructionCache(GetCurrentProcess(), q, 4);
            logf("--- WINDOWED: GZGraphicD+0x117D6 'mov [ebx+0x48],1' -> nop x4");
        }
    } else {
        logf("--- WINDOWED: 0x117D6 pattern mismatch (%02X %02X %02X %02X)", q[0], q[1], q[2], q[3]);
    }
}

static void patch_surfacefmt(HMODULE gz) {
    BYTE *site = (BYTE *)gz + 0x19349;
    static const BYTE orig[10] = { 0xF6,0xDB, 0x1B,0xDB, 0x81,0xE3,0xC0,0x0F,0x00,0x00 };
    BYTE *cave;
    DWORD old;
    int n = 0, jne_fixup, block_start;
    if (memcmp(site, orig, sizeof(orig)) != 0) {
        logf("--- FIX16: 0x19349 pattern mismatch (%02X %02X %02X %02X), NOT patched",
             site[0], site[1], site[2], site[3]);
        return;
    }
    cave = (BYTE *)VirtualAlloc(NULL, 256, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!cave) { logf("--- FIX16: VirtualAlloc failed (%lu)", GetLastError()); return; }
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
        logf("--- FIX16: VirtualProtect failed (%lu)", GetLastError()); return;
    }
    site[0] = 0xE9;
    { DWORD rel = (DWORD)cave - (DWORD)(site + 5); memcpy(site + 1, &rel, 4); }
    site[5]=site[6]=site[7]=site[8]=site[9]=0x90;
    VirtualProtect(site, 10, old, &old);
    FlushInstructionCache(GetCurrentProcess(), site, 10);
    logf("--- FIX16: 16bpp branch injected at 0x19349 -> cave 0x%08lX (5-6-5)", (DWORD)cave);
}

/* ================================================================ boot */

static DWORD WINAPI watcher(LPVOID param) {
    HMODULE gz = NULL, dirtm = NULL, initm = NULL, uim = NULL, sprm = NULL;
    int dirt = 0, dims = 0, ui = 0, anchors = 0, ms = 0;
    (void)param;

    /* Patch each module the moment it maps. Windowed mode must land before GZGraphicD's Init
       (~250 ms); SIMDIRT's buffer singleton is created lazily at first terrain use, much later. */
    while (ms < 300000 && !(gz && dirtm && uim && sprm && (initm || !g_fix_vertical))) {
        if (!sprm && (sprm = GetModuleHandleA("SIMSPR.DLL")) != NULL) anchors = patch_anchor16(sprm);
        if (!gz && (gz = GetModuleHandleA("GZGraphicD.dll")) != NULL && g_windowed) {
            patch_windowed(gz);
            patch_surfacefmt(gz);
        }
        if (!dirtm && (dirtm = GetModuleHandleA("SIMDIRT.DLL")) != NULL) dirt = patch_simdirt(dirtm);
        if (!initm && g_fix_vertical && (initm = GetModuleHandleA("SIMINIT.DLL")) != NULL)
            dims = patch_siminit(initm);
        if (!uim && (uim = GetModuleHandleA("SIMUI.DLL")) != NULL) ui = patch_simui(uim);
        Sleep(1);
        ms++;
    }

    if (gz && ui && dirt && anchors && install_heartbeat((BYTE *)gz + 0x18c58)) {
        g_ui_on = 1;
        logf("### UI: heartbeat installed, New City option armed");
    } else {
        logf("### UI: NOT armed (simdirt %d simui %d simspr %d) - the option will not appear", dirt, ui, anchors);
    }
    logf("### READY: windowed=%d simdirt=%d siminit=%d simui=%d simspr=%d ui=%d size=%d selected=%d",
         g_windowed, dirt, dims, ui, anchors, g_ui_on, g_big_n, g_last_big);
    return 0;
}

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        g_self = (HMODULE)inst;
        DisableThreadLibraryCalls(inst);
        InitializeCriticalSection(&g_lock);
        QueryPerformanceFrequency(&g_freq);
        QueryPerformanceCounter(&g_t0);
        ini_read();
        log_open();
        logf("### sc3bigcity loaded - size %d, caption \"%s\", vertical clamp %d",
             g_big_n, g_caption, g_fix_vertical);
        CreateThread(NULL, 0, watcher, NULL, 0, NULL);
    }
    return TRUE;
}
