/* sc3landfill.c - independent landfills, and emptying one (task landfill, 2026-10-30, re/analysis/LANDFILL.md).
 *
 * Owner 2026-10-30: "Each landfill should be independent, and it should be possible to empty one." Choice: A2 + E1.
 *
 * STOCK. Every landfill cell already holds its own fill, 0..0x7fff, in the low 15 bits of the pollution layer's garbage
 * cell map (bit 0x8000 = active landfill) [CONFIRMED @ SIMECO 0x10008e3a, 0x10009151, 0x100093ec]. Capacity is one
 * city-wide garbage valve (SIMECO vtable 0x1001bdfc): +0x10 free room, +0x0c garbage accepted but not yet put down,
 * vt+0x30 = room - waiting, vt+0x40 adds to waiting, vt+0x44 adds to room. The router SIMECO FUN_100094a2 (recycling,
 * incinerators, valve, export deal, abduction) checks only that number for every producer in the city. The landfill
 * developer's UpdateCell SIMRCI FUN_10019de1 puts the waiting garbage onto the cells of one city-wide heap list (dev
 * +0x5c, std::list nodes {next, prev, x, z}); findNewDumpPoint FUN_1001a62f keeps a heap inside its own connected
 * landfill, and a new heap is only started (FUN_1001a447) when the list is empty. Measured game-side: available =
 * total - sum of fills on active cells, exactly.
 *
 * INDEPENDENT (A2, landfill.ini [landfill] independent=1, SC3LANDFILL_INDEPENDENT=0 = stock):
 *   - A landfill = one 4-connected group of zone-17 cells (what fillConnectionMap floods), relabelled on load and
 *     whenever the active landfill count (pollution iface +0x468) changes. room = sum of 0x7fff - fill over its active
 *     cells, pending = garbage accepted for it and not yet put down. The valve keeps the city totals.
 *   - The router is replaced by an exact copy (SIMECO 0x100094a2, entry jmp) whose landfill step charges the nearest
 *     landfill with room (distance from the tick's 2x2 block, tick +0x48c/+0x490, to the landfill's bounding box), then
 *     the next nearest. Calls from the import and end-of-pass sites (return 0x10008492 / 0x10008c5c) have no cell: they
 *     go to the landfills with the most free room. max_distance (cells, 0 = off) limits who serves a block.
 *   - UpdateCell is wrapped (entry jmp, trampoline replays `mov eax, imm32`): for a cell of landfill g, the other
 *     landfills' heaps are unlinked from the list, valve +0x0c is set to g's pending, the stock function runs (decay,
 *     activation, deposit into g's heaps, a new heap in g when it has none), then the valve and list are put back and
 *     g's pending drops by what was put down. Same thread for both hooks (measured: the sim thread, not the UI's).
 * EMPTY (E1, [landfill] empty=1, SC3LANDFILL_EMPTY=0 = off): sc3landfill_empty(x, z) empties the landfill holding cell
 *   (x, z) the way decay does at 0: per cell with fill f, SetGarbageValue(1), valve vt+0x44(f - 1) if active, then the
 *   game's own decay FUN_1001a549 takes the last unit, removes the heap occupant (occupant manager RemoveOccupantAtCell)
 *   and the cell's heap entries, and returns that unit to the valve. Fee = tons x fee_per_1000_tons / 1000, tons =
 *   units x 0.1 (GarbageScalingFactor 100 x 0.001, SIMECO 0x100046bb). Default 50 per 1000 t: the game's own price for
 *   getting rid of garbage, the neighbour export deal (GARBAGE_EXPORT_RATE=5 per 1000 units, NeighborDeals.ini,
 *   SIMMISC 0x1001761c cost = q * rate / 1000). Charged through the budget (city vt+0x15c, vt+0x14 Withdraw); refused
 *   when funds are short. Paused: runs on the caller's thread. Running: queued for the sim thread (next UpdateCell).
 * Saves: only stock fields change, so a save loads the same without this mod.
 *
 * Exports (sc3resize's query dialog, LANDFILL block): sc3landfill_text, sc3landfill_empty.
 * Off: SC3LANDFILL=0 (nothing patched). Log: sc3landfill.log beside the DLL. Ini written with defaults if missing.
 */

#include <windows.h>
#include "sc3mods_guard.h"
#include <stdio.h>
#include <string.h>
#include <intrin.h>

#pragma intrinsic(_ReturnAddress)

static CRITICAL_SECTION g_lock;
static HANDLE g_log = INVALID_HANDLE_VALUE;
static LARGE_INTEGER g_freq, g_t0;
static HMODULE g_self;

static void logf(const char *fmt, ...) {
    char buf[1536], line[1664];
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
                  (double)(now.QuadPart - g_t0.QuadPart) * 1000.0 / (double)g_freq.QuadPart, GetCurrentThreadId(), buf);
    if (n < 0) return;
    EnterCriticalSection(&g_lock);
    if (g_log != INVALID_HANDLE_VALUE) WriteFile(g_log, line, (DWORD)n, &wrote, NULL);
    LeaveCriticalSection(&g_lock);
}

static void self_path(char *out, int cap, const char *leaf) {
    char *s;
    if (!GetModuleFileNameA(g_self, out, cap)) { out[0] = 0; return; }
    s = strrchr(out, '\\');
    if (s) s[1] = 0; else out[0] = 0;
    lstrcatA(out, leaf);
}

/* ============================================================ config */

static int g_independent = 1, g_empty = 1, g_fee = 50, g_maxdist = 0, g_verbose = 0, g_on;

static int env_int(const char *name, int *out) {
    char v[16];
    if (!GetEnvironmentVariableA(name, v, sizeof(v))) return 0;
    *out = atoi(v);
    return 1;
}

static void ini_read(void) {
    char p[MAX_PATH];
    self_path(p, sizeof(p), "landfill.ini");
    if (p[0] && GetFileAttributesA(p) == INVALID_FILE_ATTRIBUTES) {
        WritePrivateProfileStringA("landfill", "independent", "1", p);
        WritePrivateProfileStringA("landfill", "max_distance", "0", p);
        WritePrivateProfileStringA("landfill", "empty", "1", p);
        WritePrivateProfileStringA("landfill", "fee_per_1000_tons", "50", p);
    }
    if (p[0]) {
        g_independent = GetPrivateProfileIntA("landfill", "independent", 1, p) ? 1 : 0;
        g_maxdist = GetPrivateProfileIntA("landfill", "max_distance", 0, p);
        g_empty = GetPrivateProfileIntA("landfill", "empty", 1, p) ? 1 : 0;
        g_fee = GetPrivateProfileIntA("landfill", "fee_per_1000_tons", 50, p);
        g_verbose = GetPrivateProfileIntA("landfill", "verbose", 0, p);
    }
    env_int("SC3LANDFILL_INDEPENDENT", &g_independent);
    env_int("SC3LANDFILL_EMPTY", &g_empty);
    env_int("SC3LANDFILL_FEE", &g_fee);
    env_int("SC3LANDFILL_MAXDIST", &g_maxdist);
    env_int("SC3LANDFILL_VERBOSE", &g_verbose);
    if (g_fee < 0) g_fee = 0;
    if (g_maxdist < 0) g_maxdist = 0;
}

/* ============================================================ game calls */

static DWORD thiscall_n(void *self, void *fn, const DWORD *a, int n) {
    DWORD rv = 0;
    __asm {
        push ebx
        push esi
        push edi
        mov  ebx, esp
        mov  edi, a
        mov  ecx, n
        test ecx, ecx
        jz   tc_ready
    tc_push:
        mov  eax, [edi + ecx*4 - 4]
        push eax
        dec  ecx
        jnz  tc_push
    tc_ready:
        mov  ecx, self
        call [fn]
        mov  esp, ebx
        mov  rv, eax
        pop  edi
        pop  esi
        pop  ebx
    }
    return rv;
}

/* vtable call, slot byte offset, up to 4 args; 0 on a bad object */
static DWORD vc(void *o, DWORD slot, int n, DWORD a0, DWORD a1, DWORD a2, DWORD a3) {
    DWORD *vt, a[4];
    if (!o || IsBadReadPtr(o, 4)) return 0;
    vt = *(DWORD **)o;
    if (!vt || IsBadReadPtr((BYTE *)vt + slot, 4) || !vt[slot / 4]) return 0;
    a[0] = a0; a[1] = a1; a[2] = a2; a[3] = a3;
    return thiscall_n(o, (void *)vt[slot / 4], a, n);
}

static BYTE *g_eco, *g_rci;          /* SIMECO.DLL, SIMRCI.DLL bases */
static BYTE *volatile g_dev;         /* the landfill developer (UpdateCell's this), vtable SIMRCI 0x1004c558 */

/* the loaded city: *(SC3U.exe + 0xfa86c) + 0x48, vtable SIMCITY + 0x13260 (sc3simrun / sc3undo) */
static BYTE *city_get(void) {
    BYTE *exe = (BYTE *)GetModuleHandleA(NULL), *app, *c;
    HMODULE sc = GetModuleHandleA("SIMCITY.DLL");
    if (!sc) return NULL;
    __try {
        app = *(BYTE **)(exe + 0xfa86c);
        if (!app) return NULL;
        c = *(BYTE **)(app + 0x48);
        if (!c || *(DWORD *)c != (DWORD)sc + 0x13260) return NULL;
        return c;
    } __except (EXCEPTION_EXECUTE_HANDLER) { return NULL; }
}
/* sim stopped: user pause depth +0x140, or a hold +0x144 (coordinator vt+0x21c, sc3simrun notes). An open query dialog
   holds the sim with +0x144 = 2 and +0x140 = 0 (measured), so the click runs directly then. */
static int city_paused(BYTE *c) { return c && (*(LONG *)(c + 0x140) > 0 || *(LONG *)(c + 0x144) > 0); }

/* layers through the city (any thread): ZoneLayer vt+0x14c, PollutionLayer vt+0x16c, SurfaceOccupantManager vt+0x11c */
typedef struct { void *zl, *pl, *om; int nx, nz; } Layers;
static int layers_get(Layers *L) {
    BYTE *c = city_get();
    memset(L, 0, sizeof(*L));
    if (!c) return 0;
    L->zl = (void *)vc(c, 0x14c, 0, 0, 0, 0, 0);
    L->pl = (void *)vc(c, 0x16c, 0, 0, 0, 0, 0);
    L->om = (void *)vc(c, 0x11c, 0, 0, 0, 0, 0);
    if (!L->zl || !L->pl || !L->om) return 0;
    L->nx = (int)vc(L->om, 0x14, 0, 0, 0, 0, 0);      /* GetCellsInX */
    L->nz = (int)vc(L->om, 0x18, 0, 0, 0, 0, 0);      /* GetCellsInZ */
    return L->nx > 0 && L->nz > 0 && L->nx <= 4096 && L->nz <= 4096;
}
static int zone_at(void *zl, int x, int z) { BYTE b = 0xff; vc(zl, 0x34, 3, (DWORD)x, (DWORD)z, (DWORD)&b, 0); return b; }
static DWORD fill_at(void *pl, int x, int z) { DWORD v = 0; vc(pl, 0x60, 3, (DWORD)x, (DWORD)z, (DWORD)&v, 0); return v; }
static int active_at(void *pl, int x, int z) { return (int)(vc(pl, 0x104, 2, (DWORD)x, (DWORD)z, 0, 0) & 0xff); }
static void fill_set(void *pl, int x, int z, DWORD v) { vc(pl, 0xa0, 3, (DWORD)x, (DWORD)z, v, 0); }

/* valve (SIMECO vtable 0x1001bdfc): +0x0c waiting, +0x10 room */
#define VALVE_VT 0x1bdfc
static int valve_ok(BYTE *v) { return v && !IsBadReadPtr(v, 0x30) && *(DWORD *)v == (DWORD)g_eco + VALVE_VT; }

/* ============================================================ landfill groups (sim thread) */

#define MAXG 1024
typedef struct { int x0, z0, x1, z1, n, off, nact; LONG room, fill, pending; } Grp;
static Grp g_grp[MAXG + 1];          /* 1..g_ng */
static int g_ng, g_lab_nx, g_lab_nz, g_labelled;
static WORD *g_lab;                  /* nx * nz group ids, 0 = not a landfill cell */
static DWORD *g_cells;               /* packed x | z << 16, grouped by off/n */
static int g_cells_cap;
static DWORD g_last_count = 0xffffffff;
static DWORD g_relabels;

static int lab_at(int x, int z) {
    if (!g_lab || x < 0 || z < 0 || x >= g_lab_nx || z >= g_lab_nz) return 0;
    return g_lab[z * g_lab_nx + x];
}

static void grp_room(Grp *g, void *pl) {
    int i;
    LONG room = 0, fill = 0, nact = 0;
    for (i = 0; i < g->n; i++) {
        DWORD c = g_cells[g->off + i], f;
        int x = (int)(c & 0xffff), z = (int)(c >> 16);
        f = fill_at(pl, x, z);
        fill += (LONG)f;
        if (active_at(pl, x, z)) { nact++; room += (LONG)(f < 0x7fff ? 0x7fff - f : 0); }
    }
    g->room = room; g->fill = fill; g->nact = nact;
}

/* flood every zone-17 cell into 4-connected groups. Pending is kept by matching each new group to the old group that
   held most of its cells' first cell (a cheap proxy: the old label of the new group's first cell). */
static void relabel(void) {
    Layers L;
    static WORD *old;
    static LONG oldp[MAXG + 1];
    int x, z, i, total = 0, oldn = g_ng, onx = g_lab_nx;
    DWORD *stack;
    if (!layers_get(&L)) return;
    if (g_lab && onx == L.nx && g_lab_nz == L.nz) {
        if (!old) old = (WORD *)VirtualAlloc(NULL, (SIZE_T)L.nx * L.nz * 2, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        if (old) memcpy(old, g_lab, (size_t)L.nx * L.nz * 2);
        for (i = 1; i <= oldn; i++) oldp[i] = g_grp[i].pending;
    } else oldn = 0;
    if (!g_lab || g_lab_nx != L.nx || g_lab_nz != L.nz) {
        if (g_lab) VirtualFree(g_lab, 0, MEM_RELEASE);
        if (old) { VirtualFree(old, 0, MEM_RELEASE); old = NULL; }
        g_lab = (WORD *)VirtualAlloc(NULL, (SIZE_T)L.nx * L.nz * 2, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        g_lab_nx = L.nx; g_lab_nz = L.nz;
        if (!g_lab) { g_ng = 0; return; }
    }
    memset(g_lab, 0, (size_t)L.nx * L.nz * 2);
    for (z = 0; z < L.nz; z++) for (x = 0; x < L.nx; x++) if (zone_at(L.zl, x, z) == 17) { g_lab[z * L.nx + x] = 0xffff; total++; }
    if (total > g_cells_cap) {
        if (g_cells) VirtualFree(g_cells, 0, MEM_RELEASE);
        g_cells_cap = total + 4096;
        g_cells = (DWORD *)VirtualAlloc(NULL, (SIZE_T)g_cells_cap * 4, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        if (!g_cells) { g_cells_cap = 0; g_ng = 0; return; }
    }
    stack = (DWORD *)VirtualAlloc(NULL, (SIZE_T)(total + 1) * 4, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!stack) { g_ng = 0; return; }
    g_ng = 0;
    {   int used = 0;
        for (z = 0; z < L.nz; z++) for (x = 0; x < L.nx; x++) {
            int sp = 0, id;
            Grp *g;
            if (g_lab[z * L.nx + x] != 0xffff) continue;
            if (g_ng >= MAXG) { g_lab[z * L.nx + x] = 0; continue; }   /* past MAXG: those cells stay stock-less (no group) */
            id = ++g_ng;
            g = &g_grp[id];
            memset(g, 0, sizeof(*g));
            g->x0 = g->x1 = x; g->z0 = g->z1 = z; g->off = used;
            g_lab[z * L.nx + x] = (WORD)id;
            stack[sp++] = (DWORD)x | ((DWORD)z << 16);
            while (sp) {
                DWORD c = stack[--sp];
                int cx = (int)(c & 0xffff), cz = (int)(c >> 16), d;
                static const int dx[4] = { 1, -1, 0, 0 }, dz[4] = { 0, 0, 1, -1 };
                g_cells[used++] = c; g->n++;
                if (cx < g->x0) g->x0 = cx;
                if (cx > g->x1) g->x1 = cx;
                if (cz < g->z0) g->z0 = cz;
                if (cz > g->z1) g->z1 = cz;
                for (d = 0; d < 4; d++) {
                    int nx = cx + dx[d], nz = cz + dz[d];
                    if (nx < 0 || nz < 0 || nx >= L.nx || nz >= L.nz || g_lab[nz * L.nx + nx] != 0xffff) continue;
                    g_lab[nz * L.nx + nx] = (WORD)id;
                    stack[sp++] = (DWORD)nx | ((DWORD)nz << 16);
                }
            }
            if (oldn && old) {   /* carry the old group's pending over (once) */
                DWORD c0 = g_cells[g->off];
                int o = old[(c0 >> 16) * L.nx + (c0 & 0xffff)];
                if (o > 0 && o <= oldn && oldp[o] > 0) { g->pending = oldp[o]; oldp[o] = 0; }
            }
            grp_room(g, L.pl);
        }
    }
    VirtualFree(stack, 0, MEM_RELEASE);
    g_labelled = 1;
    g_relabels++;
    logf("GROUPS> relabel %lu: %d landfill(s), %d cell(s), map %dx%d", g_relabels, g_ng, total, L.nx, L.nz);
    for (i = 1; i <= g_ng && i <= 12; i++)
        logf("GROUPS>   #%d cells %d active %d box [%d %d %d %d] fill %ld room %ld pending %ld", i, g_grp[i].n,
             g_grp[i].nact, g_grp[i].x0, g_grp[i].z0, g_grp[i].x1, g_grp[i].z1, g_grp[i].fill, g_grp[i].room,
             g_grp[i].pending);
}

/* the active landfill count (pollution iface +0x468, GetTotalLandfillCapacity = it x 0x7fff, SIMECO 0x1000a719) */
static void labels_check(void *pl) {
    DWORD n;
    if (!pl || IsBadReadPtr((BYTE *)pl + 0x468, 4)) return;
    n = *(DWORD *)((BYTE *)pl + 0x468);
    if (n != g_last_count || !g_labelled) { g_last_count = n; relabel(); }
}

static LONG grp_free(int i) { LONG f = g_grp[i].room - g_grp[i].pending; return f > 0 ? f : 0; }

/* keep sum(pending) == valve waiting: surplus to `prefer` (or the freest), shortfall off the largest pendings */
static void reconcile(BYTE *valve, int prefer) {
    LONG P = *(LONG *)(valve + 0x0c), sum = 0, d;
    int i, best;
    for (i = 1; i <= g_ng; i++) sum += g_grp[i].pending;
    d = P - sum;
    if (!d || !g_ng) return;
    if (d > 0) {
        best = prefer;
        if (best < 1 || best > g_ng) {
            best = 1;
            for (i = 2; i <= g_ng; i++) if (grp_free(i) > grp_free(best)) best = i;
        }
        g_grp[best].pending += d;
        if (g_verbose) logf("PENDING> +%ld unassigned waiting garbage -> landfill #%d", d, best);
        return;
    }
    d = -d;
    while (d > 0) {
        best = 0;
        for (i = 1; i <= g_ng; i++) if (g_grp[i].pending > 0 && (!best || g_grp[i].pending > g_grp[best].pending)) best = i;
        if (!best) break;
        if (g_grp[best].pending >= d) { g_grp[best].pending -= d; d = 0; }
        else { d -= g_grp[best].pending; g_grp[best].pending = 0; }
    }
}

/* ============================================================ the router (SIMECO FUN_100094a2, replaced) */

static DWORD g_ret_cell;                      /* SIMECO 0x10008877: the per-cell call in the tick */
static volatile LONG g_routed, g_routed_cell, g_short;   /* statistics */

static void add64(BYTE *p, LONG v) { *(__int64 *)p += (__int64)v; }

typedef DWORD (__fastcall *PFN_vt0)(void *self, void *edx);
static DWORD vt0(void *o, DWORD slot) { return vc(o, slot, 0, 0, 0, 0, 0); }

/* take up to `want` units from the landfills' own free room, nearest first from (bx, bz), or freest first (bx < 0) */
static LONG grp_take(LONG want, int bx, int bz) {
    static char tried[MAXG + 1];
    LONG got = 0;
    int k;
    if (!g_ng) return want;      /* no landfill zone at all: whatever the valve says (stock) */
    memset(tried, 0, (size_t)g_ng + 1);
    for (k = 0; k < g_ng && got < want; k++) {
        int i, best = 0;
        double bd = 0;
        for (i = 1; i <= g_ng; i++) {
            double d;
            if (tried[i] || grp_free(i) <= 0) continue;
            if (bx >= 0) {
                int X = bx + 1, Z = bz + 1, dx = 0, dz = 0;
                if (X < g_grp[i].x0) dx = g_grp[i].x0 - X; else if (X > g_grp[i].x1) dx = X - g_grp[i].x1;
                if (Z < g_grp[i].z0) dz = g_grp[i].z0 - Z; else if (Z > g_grp[i].z1) dz = Z - g_grp[i].z1;
                d = (double)dx * dx + (double)dz * dz;
                if (g_maxdist > 0 && d > (double)g_maxdist * g_maxdist) continue;
            } else d = -(double)grp_free(i);
            if (!best || d < bd) { best = i; bd = d; }
        }
        if (!best) break;
        tried[best] = 1;
        {   LONG t = want - got, f = grp_free(best);
            if (t > f) t = f;
            g_grp[best].pending += t;
            got += t;
        }
    }
    return got;
}

static DWORD __fastcall lf_router(BYTE *self, void *edx, int amt, DWORD *incin, DWORD *recyc) {
    DWORD ra = (DWORD)_ReturnAddress();
    LONG ret = 0, rem, t;
    BYTE *valve, *deal;
    (void)edx;
    if (amt < 1) return 0;
    rem = amt;
    if (*recyc != 0) {                                   /* 1. recycling reserve, ledger +0x470 */
        LONG r = (LONG)*recyc;
        if (r < rem) { t = r; rem -= r; *recyc = 0; } else { *recyc = (DWORD)(r - rem); t = rem; rem = 0; }
        add64(self + 0x470, t);
        ret = t;
    }
    if (rem <= 0) return (DWORD)ret;
    if (*incin != 0) {                                   /* 2. incinerator reserve, ledger +0x468 */
        LONG r = (LONG)*incin;
        if (r < rem) { t = r; rem -= r; *incin = 0; } else { *incin = (DWORD)(r - rem); t = rem; rem = 0; }
        add64(self + 0x468, t);
        ret += t;
    }
    if (rem <= 0) return (DWORD)ret;
    valve = *(BYTE **)(self + 0x158);                    /* 3. the garbage valve: per landfill */
    {   LONG av = (LONG)vt0(valve, 0x30), got;
        if (av > 0) {
            LONG want = rem < av ? rem : av;
            InterlockedIncrement(&g_routed);
            if (valve_ok(valve)) {
                labels_check((void *)(self + 0x1c));          /* the cISC3PollutionLayer subobject (QI 0x80a814ac) */
                if (ra == g_ret_cell) {
                    InterlockedIncrement(&g_routed_cell);
                    got = grp_take(want, *(int *)(self + 0x48c), *(int *)(self + 0x490));
                } else got = grp_take(want, -1, 0);
            } else got = want;
            if (got < rem && got < av) InterlockedIncrement(&g_short);
            if (got > 0) { vc(valve, 0x40, 1, (DWORD)got, 0, 0, 0); rem -= got; ret += got; }
        }
    }
    if (rem <= 0) return (DWORD)ret;
    deal = *(BYTE **)(self + 0x4c);                      /* 4. neighbour export deal (4), ledger +0x458 */
    {   BYTE buf[0x40];
        if ((BYTE)vc(deal, 0x8c, 2, 4, (DWORD)buf, 0, 0)) { add64(self + 0x458, rem); return (DWORD)(ret + rem); }
    }
    {   LONG cap = *(LONG *)(g_eco + 0x20270) - *(LONG *)(self + 0x480), c = 0;   /* 5. GarbageAbductionAmount */
        if (cap > 0) { c = rem < cap ? rem : cap; *(LONG *)(self + 0x480) += c; }
        ret += c;
    }
    return (DWORD)ret;
}

/* ============================================================ UpdateCell wrapper (SIMRCI FUN_10019de1) */

static DWORD g_uc_imm, g_uc_cont;               /* the relocated `mov eax, imm32` operand, FUN_10019de1 + 5 */
static __declspec(naked) void uc_tramp(void) {
    __asm {
        mov eax, g_uc_imm
        jmp dword ptr [g_uc_cont]
    }
}
static DWORD uc_orig(BYTE *dev, DWORD *cell) { DWORD a[1]; a[0] = (DWORD)cell; return thiscall_n(dev, (void *)uc_tramp, a, 1); }

static volatile LONG g_req;                     /* 0 idle, 1 asked, 2 done */
static volatile LONG g_req_x, g_req_z;
static char g_req_msg[256];
static int g_req_es;
static int do_empty(int x, int z, int es, char *msg, int cap);

#define MAXHIDE 8192
static DWORD *g_hide[MAXHIDE];

static DWORD __fastcall lf_update(BYTE *dev, void *edx, DWORD *cell) {
    BYTE *valve, *head;
    void *pl;
    DWORD r, *n;
    int g, nh = 0, i;
    LONG P, Pg, after, D;
    (void)edx;
    if (!g_dev) {
        if (*(DWORD *)dev != (DWORD)g_rci + 0x4c558) { logf("### UpdateCell this 0x%08lX vtable 0x%08lX not the developer's", (DWORD)dev, *(DWORD *)dev); return uc_orig(dev, cell); }
        g_dev = dev;
        logf("DEV> landfill developer 0x%08lX (valve 0x%08lX, pollution 0x%08lX)", (DWORD)dev, *(DWORD *)(dev + 0x3c), *(DWORD *)(dev + 0x4c));
    }
    if (g_req == 1 && dev == g_dev) {            /* an empty request from the UI thread, game running */
        do_empty(g_req_x, g_req_z, g_req_es, g_req_msg, sizeof(g_req_msg));
        InterlockedExchange(&g_req, 2);
    }
    valve = *(BYTE **)(dev + 0x3c);
    pl = *(void **)(dev + 0x4c);
    if (!g_independent || dev != g_dev || !valve_ok(valve)) return uc_orig(dev, cell);
    labels_check(pl);
    g = lab_at((int)cell[0], (int)cell[1]);
    reconcile(valve, g);
    head = *(BYTE **)(dev + 0x5c);
    for (n = *(DWORD **)head; n && (BYTE *)n != head && nh < MAXHIDE; ) {   /* other landfills' heaps out of the list */
        DWORD *next = (DWORD *)n[0];
        if (!g || lab_at((int)n[2], (int)n[3]) != g) {
            ((DWORD *)n[1])[0] = n[0];
            ((DWORD *)n[0])[1] = n[1];
            g_hide[nh++] = n;
        }
        n = next;
    }
    P = *(LONG *)(valve + 0x0c);
    Pg = g ? g_grp[g].pending : 0;
    if (Pg > P) Pg = P;
    if (Pg < 0) Pg = 0;
    *(LONG *)(valve + 0x0c) = Pg;
    r = uc_orig(dev, cell);
    after = *(LONG *)(valve + 0x0c);
    D = Pg - after;
    *(LONG *)(valve + 0x0c) = P - D;
    if (g) g_grp[g].pending = after > 0 ? after : 0;
    head = *(BYTE **)(dev + 0x5c);
    for (i = 0; i < nh; i++) {                   /* back in, at the tail */
        n = g_hide[i];
        n[0] = (DWORD)head;
        n[1] = ((DWORD *)head)[1];
        ((DWORD *)n[1])[0] = (DWORD)n;
        ((DWORD *)head)[1] = (DWORD)n;
    }
    if (*(DWORD *)((BYTE *)pl + 0x468) != g_last_count) labels_check(pl);
    else if (g) grp_room(&g_grp[g], pl);
    if (g_verbose && D > 0) logf("DEPOSIT> cell (%lu, %lu) landfill #%d: put down %ld, its pending %ld, room %ld; hidden heaps %d",
                                 cell[0], cell[1], g, D, g_grp[g].pending, g_grp[g].room, nh);
    return r;
}

/* ============================================================ emptying + text (any thread) */

static int flood(Layers *L, int x, int z, DWORD **out) {     /* the zone-17 group holding (x, z), its own copy */
    BYTE *seen;
    DWORD *list, *st;
    int n = 0, sp = 0, cap = 1 << 16;
    *out = NULL;
    if (x < 0 || z < 0 || x >= L->nx || z >= L->nz || zone_at(L->zl, x, z) != 17) return 0;
    seen = (BYTE *)VirtualAlloc(NULL, (SIZE_T)L->nx * L->nz, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    list = (DWORD *)VirtualAlloc(NULL, (SIZE_T)cap * 4, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    st = (DWORD *)VirtualAlloc(NULL, (SIZE_T)cap * 4, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!seen || !list || !st) {
        if (seen) VirtualFree(seen, 0, MEM_RELEASE);
        if (list) VirtualFree(list, 0, MEM_RELEASE);
        if (st) VirtualFree(st, 0, MEM_RELEASE);
        return 0;
    }
    seen[z * L->nx + x] = 1;
    st[sp++] = (DWORD)x | ((DWORD)z << 16);
    while (sp && n < cap) {
        DWORD c = st[--sp];
        int cx = (int)(c & 0xffff), cz = (int)(c >> 16), d;
        static const int dx[4] = { 1, -1, 0, 0 }, dz[4] = { 0, 0, 1, -1 };
        list[n++] = c;
        for (d = 0; d < 4; d++) {
            int nx = cx + dx[d], nz = cz + dz[d];
            if (nx < 0 || nz < 0 || nx >= L->nx || nz >= L->nz || seen[nz * L->nx + nx]) continue;
            seen[nz * L->nx + nx] = 1;
            if (zone_at(L->zl, nx, nz) != 17 || sp >= cap) continue;
            st[sp++] = (DWORD)nx | ((DWORD)nz << 16);
        }
    }
    VirtualFree(seen, 0, MEM_RELEASE);
    VirtualFree(st, 0, MEM_RELEASE);
    *out = list;
    return n;
}

static LONG fee_of(LONG units) {   /* tons = units / 10, fee per 1000 t */
    __int64 c = ((__int64)units * g_fee + 9999) / 10000;
    return (LONG)c;
}

static void thousands(char *out, int cap, LONG v, int es) {
    char t[32];
    int n, i, j = 0, lead;
    if (v < 0) { out[j++] = '-'; v = -v; }
    n = _snprintf(t, sizeof(t), "%ld", v);
    lead = n % 3;
    for (i = 0; i < n && j < cap - 2; i++) {
        if (i && (i - lead) % 3 == 0) out[j++] = ',';   /* the game's own panels write 376,821 on the Spanish install too */
        (void)es;
        out[j++] = t[i];
    }
    out[j] = 0;
}

typedef struct { int cells, nact; LONG fill, cap, room; } Totals;
static void totals(Layers *L, DWORD *list, int n, Totals *t) {
    int i;
    memset(t, 0, sizeof(*t));
    t->cells = n;
    for (i = 0; i < n; i++) {
        int x = (int)(list[i] & 0xffff), z = (int)(list[i] >> 16);
        DWORD f = fill_at(L->pl, x, z);
        t->fill += (LONG)f;
        if (active_at(L->pl, x, z)) { t->nact++; t->cap += 0x7fff; t->room += (LONG)(f < 0x7fff ? 0x7fff - f : 0); }
    }
}

/* three lines for the query dialog (l3 empty when emptying is off). 1 = (x, z) is a landfill cell. */
__declspec(dllexport) int __cdecl sc3landfill_text(int x, int z, int es, char *l1, char *l2, char *l3, int cap) {
    Layers L;
    DWORD *list;
    Totals t;
    int n, pct, k;
    char a[32], b[32], c[32], d[32];
    l1[0] = l2[0] = l3[0] = 0;
    if (!g_on) return 0;
    __try {
        if (!layers_get(&L)) return 0;
        n = flood(&L, x, z, &list);
        if (!n) return 0;
        totals(&L, list, n, &t);
        VirtualFree(list, 0, MEM_RELEASE);
    } __except (EXCEPTION_EXECUTE_HANDLER) { return 0; }
    pct = t.cap ? (int)((__int64)(t.cap - t.room) * 100 / t.cap) : 0;
    thousands(a, sizeof(a), (t.cap - t.room) / 10, es);
    thousands(b, sizeof(b), t.cap / 10, es);
    thousands(c, sizeof(c), t.room / 10, es);
    thousands(d, sizeof(d), fee_of(t.fill), es);
    k = _snprintf(l1, cap, es ? "Este vertedero: %d%% completo" : "This landfill: %d%% full", pct);
    if (k > 0 && t.nact < t.cells)    /* cells without road access hold nothing */
        _snprintf(l1 + k, cap - k, es ? " (%d sin acceso)" : " (%d not connected)", t.cells - t.nact);
    _snprintf(l2, cap, es ? "%s de %s ton. (libre %s)" : "%s of %s tons (%s free)", a, b, c);
    if (g_empty) _snprintf(l3, cap, es ? "Vaciarlo cuesta $%s" : "Emptying it costs $%s", d);
    l1[cap - 1] = l2[cap - 1] = l3[cap - 1] = 0;
    return 1;
}

static void *budget_get(void) {
    BYTE *c = city_get();
    HMODULE misc = GetModuleHandleA("SIMMISC.DLL");
    void *bu;
    if (!c || !misc) return NULL;
    bu = (void *)vc(c, 0x15c, 0, 0, 0, 0, 0);
    return bu && *(DWORD *)bu == (DWORD)misc + 0x3c550 ? bu : NULL;
}

/* empty the landfill holding (x, z). Needs the developer (seen once UpdateCell has run). */
static int do_empty(int x, int z, int es, char *msg, int cap) {
    Layers L;
    DWORD *list = NULL;
    BYTE *dev = g_dev, *valve;
    void *bu;
    int n, i, emptied = 0;
    LONG total = 0, cost, funds, f1;
    char a[32], b[32];
    __try {
        if (!layers_get(&L) || !dev) { _snprintf(msg, cap, es ? "No disponible todav\xed" "a: reanud\xe1 la simulaci\xf3n un momento" : "Not ready yet: let the game run for a moment"); return 0; }
        valve = *(BYTE **)(dev + 0x3c);
        if (!valve_ok(valve) || *(void **)(dev + 0x4c) != L.pl) { _snprintf(msg, cap, "landfill: unexpected layers"); logf("### EMPTY: layers do not match (dev pl 0x%08lX, city pl 0x%08lX)", *(DWORD *)(dev + 0x4c), (DWORD)L.pl); return 0; }
        n = flood(&L, x, z, &list);
        if (!n) { _snprintf(msg, cap, es ? "No es un vertedero" : "Not a landfill"); return 0; }
        for (i = 0; i < n; i++) total += (LONG)fill_at(L.pl, (int)(list[i] & 0xffff), (int)(list[i] >> 16));
        if (!total) { VirtualFree(list, 0, MEM_RELEASE); _snprintf(msg, cap, es ? "Ya est\xe1 vac\xedo" : "Already empty"); return 0; }
        cost = fee_of(total);
        bu = budget_get();
        funds = bu ? (LONG)vc(bu, 0x10, 0, 0, 0, 0, 0) : 0;
        if (!bu || funds < cost) {
            VirtualFree(list, 0, MEM_RELEASE);
            thousands(a, sizeof(a), cost, es);
            _snprintf(msg, cap, es ? "Fondos insuficientes: cuesta $%s" : "Not enough funds: it costs $%s", a);
            logf("EMPTY> landfill at (%d, %d): %d cells, %ld units, refused: funds %ld < %ld", x, z, n, total, funds, cost);
            return 0;
        }
        for (i = 0; i < n; i++) {
            int cx = (int)(list[i] & 0xffff), cz = (int)(list[i] >> 16);
            DWORD f = fill_at(L.pl, cx, cz), cxz[2];
            if (!f) continue;
            if (f > 1) {
                fill_set(L.pl, cx, cz, 1);
                if (active_at(L.pl, cx, cz)) vc(valve, 0x44, 1, f - 1, 0, 0, 0);
            }
            cxz[0] = (DWORD)cx; cxz[1] = (DWORD)cz;
            {   DWORD a[1];
                a[0] = (DWORD)cxz;
                thiscall_n(dev, g_rci + 0x1a549, a, 1);   /* decay: 1 -> 0, heap occupant + entries removed */
            }
            emptied++;
        }
        VirtualFree(list, 0, MEM_RELEASE);
        if (cost > 0) vc(bu, 0x14, 1, (DWORD)cost, 0, 0, 0);
        f1 = (LONG)vc(bu, 0x10, 0, 0, 0, 0, 0);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        if (list) VirtualFree(list, 0, MEM_RELEASE);
        _snprintf(msg, cap, "landfill: fault");
        logf("### EMPTY: fault 0x%08lX", GetExceptionCode());
        return 0;
    }
    if (g_independent && g_labelled) { int g = lab_at(x, z); if (g) grp_room(&g_grp[g], L.pl); }
    thousands(a, sizeof(a), total / 10, es);
    thousands(b, sizeof(b), cost, es);
    _snprintf(msg, cap, es ? "Vaciado: %s ton. por $%s" : "Emptied: %s tons for $%s", a, b);
    logf("EMPTY> landfill at (%d, %d): %d cells, %d emptied, %ld units (%ld t), fee $%ld, funds %ld -> %ld", x, z, n,
         emptied, total, total / 10, cost, funds, f1);
    return 1;
}

/* 1 done, 2 queued (game running, the sim thread had not picked it up within 3 s), 0 refused (msg says why) */
__declspec(dllexport) int __cdecl sc3landfill_empty(int x, int z, int es, char *msg, int cap) {
    BYTE *c = city_get();
    int i;
    msg[0] = 0;
    if (!g_on) return 0;
    if (!g_empty) { _snprintf(msg, cap, es ? "Vaciar est\xe1 apagado (landfill.ini)" : "Emptying is off (landfill.ini)"); return 0; }
    if (!c) return 0;
    if (city_paused(c)) return do_empty(x, z, es, msg, cap);
    if (!g_dev) { _snprintf(msg, cap, es ? "No disponible todav\xed" "a: reanud\xe1 la simulaci\xf3n un momento" : "Not ready yet: let the game run for a moment"); return 0; }
    if (g_req == 1) { _snprintf(msg, cap, es ? "Ya hay un vaciado en curso" : "Already emptying one"); return 0; }
    g_req_x = x; g_req_z = z; g_req_es = es; g_req_msg[0] = 0;
    InterlockedExchange(&g_req, 1);
    for (i = 0; i < 300 && g_req == 1; i++) Sleep(10);
    if (g_req == 2) {
        lstrcpynA(msg, g_req_msg, cap);
        InterlockedExchange(&g_req, 0);
        return strncmp(g_req_msg, es ? "Vaciado" : "Emptied", 7) == 0 ? 1 : 0;
    }
    _snprintf(msg, cap, es ? "Se vac\xed" "a en unos segundos" : "Emptying in a few seconds");
    return 2;
}

/* ============================================================ install */

static int jmp_patch(BYTE *at, void *to) {
    DWORD old;
    if (!VirtualProtect(at, 5, PAGE_EXECUTE_READWRITE, &old)) return 0;
    at[0] = 0xE9;
    *(DWORD *)(at + 1) = (DWORD)to - (DWORD)(at + 5);
    (void)0; /* no restore: a restore can land mid-write in another mod on the same page (memory mod-startup-races) */
    FlushInstructionCache(GetCurrentProcess(), at, 5);
    return 1;
}

static DWORD WINAPI init_thread(LPVOID p) {
    static const BYTE router_head[] = { 0x55, 0x8b, 0xec, 0x83, 0xec, 0x30, 0x56, 0x57, 0x8b, 0x7d, 0x08 };
    static const BYTE uc_head[] = { 0xb8 };
    static const BYTE decay_head[] = { 0x55, 0x8b, 0xec, 0x83, 0xec, 0x10, 0x53, 0x56 };
    BYTE *r, *u, *d, *call;
    int i, calls = 0, ok_r = 0, ok_u = 0;
    (void)p;
    while (!(g_eco = (BYTE *)GetModuleHandleA("SIMECO.DLL")) || !(g_rci = (BYTE *)GetModuleHandleA("SIMRCI.DLL"))) Sleep(20);
    r = g_eco + 0x94a2; u = g_rci + 0x19de1; d = g_rci + 0x1a549;
    if (memcmp(u, uc_head, 1) || u[5] != 0xe8 || memcmp(d, decay_head, sizeof(decay_head))) {
        logf("### SIMRCI differs from shipped at UpdateCell/decay: NOT installed (stock game)");
        return 0;
    }
    /* the tick's three router calls: the per-cell one is the second (ret 0x10008877) */
    for (call = g_eco + 0x8249; call < g_eco + 0x8249 + 0xb3b - 5; call++)
        if (call[0] == 0xe8 && (DWORD)call + 5 + *(LONG *)(call + 1) == (DWORD)r) { if (++calls == 2) g_ret_cell = (DWORD)call + 5; }
    if (g_independent && (memcmp(r, router_head, sizeof(router_head)) || calls != 3 || g_ret_cell != (DWORD)g_eco + 0x8877)) {
        logf("### SIMECO differs from shipped (router head / %d calls): independent landfills OFF", calls);
        g_independent = 0;
    }
    g_uc_imm = *(DWORD *)(u + 1);
    g_uc_cont = (DWORD)u + 5;
    ok_u = jmp_patch(u, (void *)lf_update);
    if (g_independent) ok_r = jmp_patch(r, (void *)lf_router);
    g_on = ok_u;
    logf("### READY: independent=%d (router %s, max_distance %d), empty=%d (fee %d per 1000 t), UpdateCell hook %s",
         g_independent, ok_r ? "replaced" : "stock", g_maxdist, g_empty, g_fee, ok_u ? "on" : "FAILED");
    for (i = 0;; i++) {          /* a line a minute while the game runs: how routing went */
        Sleep(60000);
        if (g_independent && g_ng) {
            int k;
            logf("STATS> routed %ld (per cell %ld), short of local room %ld; %d landfill(s):", g_routed, g_routed_cell, g_short, g_ng);
            for (k = 1; k <= g_ng && k <= 12; k++)
                logf("STATS>   #%d cells %d active %d fill %ld room %ld pending %ld", k, g_grp[k].n, g_grp[k].nact,
                     g_grp[k].fill, g_grp[k].room, g_grp[k].pending);
        }
    }
}

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID reserved) {
    char v[8];
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        if (!sc3mods_guard(inst, "sc3landfill")) return TRUE;
        g_self = (HMODULE)inst;
        DisableThreadLibraryCalls(inst);
        InitializeCriticalSection(&g_lock);
        QueryPerformanceFrequency(&g_freq);
        QueryPerformanceCounter(&g_t0);
        {   char path[MAX_PATH];
            self_path(path, sizeof(path), "sc3landfill.log");
            g_log = CreateFileA(path, GENERIC_WRITE, FILE_SHARE_READ, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        }
        if (GetEnvironmentVariableA("SC3LANDFILL", v, sizeof(v)) && v[0] == '0') {
            g_independent = g_empty = 0;
            logf("### sc3landfill off (SC3LANDFILL=0): nothing patched");
            return TRUE;
        }
        ini_read();
        logf("### sc3landfill loaded");
        CreateThread(NULL, 0, init_thread, NULL, 0, NULL);
    }
    return TRUE;
}
