/* sc3cartrips.c - the trip tap (task cartrips2, milestone M1 of re/analysis/CAR_TRIPS.md 4.5). No visible change.
 *
 * SimTransit route_trip FUN_100070d0 pops its final path destination first, one 32-byte node per iteration of the
 * loop 0x100072d8..0x10007554: back() FUN_10009e8e, `rep movsd` of the node into *ebx, then the deque pop
 * `call 0x10009eed` at 0x100072f8, then the deposit switch on the node type [CONFIRMED @ SimTransit 0x100072b6..
 * 0x10007554]. The origin lot (type 0x80) is always the last pop (verify/cartrips PRE prediction 7). Node: +0
 * occupant, +4/+8/+0xc/+0x10 cell rect x0 z0 x1 z1, +0x14 type, +0x15 previous type, +0x18 cost, +0x1c entry side.
 *
 * CAPTURE: the 5-byte call at 0x100072f8 becomes a call to pop_stub (written with one locked 8-byte exchange: the
 * call sits inside one aligned qword). pop_stub saves every register, appends the node copy in ebx to a per-thread
 * buffer, and jumps to 0x10009eed, which returns to 0x100072fd as before. It runs on whichever thread routes: the sim
 * thread and sc3perf's traffic_mt workers. On the origin pop the trip is complete: counters are added, and a trip
 * with any node meeting the street sim's sim rect (layer +0xb0..+0xbc, the cars' rect) is copied into a lock-free
 * MPSC ring (bounded, Vyukov sequence slots; full -> counted drop). Nothing in a ring entry points into game memory.
 *
 * DRAIN: the STRTSIM layer's animation tick FUN_10012e46 calls the car producer tick `call 0x1001f44a` at
 * 0x10012e8a (game thread, esi = layer + 8) [CONFIRMED @ STRTSIM 0x10012e46]. That call becomes tick_stub: it
 * publishes the sim rect for the routing threads (a virtual 33 x 28 rect at the view centre when the rect is empty,
 * as verify/cartrips PRE addendum 2), drains the ring into a bounded queue of the newest viewport trips (M3's input),
 * then jumps to 0x1001f44a.
 *
 * VERIFY (verify=1, measurement only): the five deposit calls `call 0x10006edd` of the pop loop (0x100073b2,
 * 0x100073f8, 0x10007463, 0x100074be, 0x10007500; thiscall, stack x, z, amount, mask) also go through a stub that
 * records each deposit cell against the node popped last on that thread. Per trip the deposits are checked against
 * the captured nodes: every deposit inside the last popped node's rect, every depositing node covered cell for cell.
 *
 * TIME (time_route=1, measurement only): route_trip's entry `mov eax, 0x100189b4` (5 bytes) becomes a jmp to a
 * wrapper that reads the TSC around the call; per-thread cycles and calls feed the in-game A/B (tools ctm_alt.py).
 * sc3cartrips_set(0|1) writes the shipped call / our call back at 0x100072f8, so one game alternates capture off/on.
 *
 * Config cartrips.ini beside the DLL, [cartrips]: mode=capture|off  verify=0|1  time_route=0|1  dump=0|1
 * log_s=10. Log sc3cartrips.log beside the DLL (env SC3CARTRIPS_LOG overrides). dump=1 writes every drained trip to
 * cartrips_trips.bin (format: tools re/tools/ctm_read.py).
 * Build: pwsh re/scripts/build_mod.ps1 -Mod sc3cartrips -Src re/harness/src -Out <dir>. Ships via mods_launch.exe.
 */

#include <windows.h>
#include <tlhelp32.h>
#include <intrin.h>
#include <stdio.h>
#include <string.h>

/* ============================================================ logging */

static CRITICAL_SECTION g_lock;
static HANDLE g_log = INVALID_HANDLE_VALUE;
static LARGE_INTEGER g_freq, g_t0;
static HMODULE g_self;

static void logf(const char *fmt, ...) {
    char buf[2048], line[2176];
    va_list ap;
    LARGE_INTEGER now;
    DWORD wrote;
    int n;
    va_start(ap, fmt);
    _vsnprintf(buf, sizeof(buf) - 1, fmt, ap);
    buf[sizeof(buf) - 1] = 0;
    va_end(ap);
    QueryPerformanceCounter(&now);
    n = _snprintf(line, sizeof(line) - 1, "[%10.3f s][tid %04lx] %s\r\n",
                  (double)(now.QuadPart - g_t0.QuadPart) / (double)g_freq.QuadPart, GetCurrentThreadId(), buf);
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

static unsigned __int64 epoch_ms(void) {
    FILETIME ft;
    GetSystemTimeAsFileTime(&ft);
    return (((unsigned __int64)ft.dwHighDateTime << 32 | ft.dwLowDateTime) / 10000) - 11644473600000ULL;
}

/* ============================================================ config */

static int g_mode = 2;                           /* 0 off, 1 capture, 2 replace (default), 3 filler */
static int g_verify, g_time, g_dump, g_choice, g_log_s = 10;
static int g_solve, g_time_agents;
static int g_rect_ovr, g_ovr[4];                 /* [cartrips] rect=x0,z0,x1,z1: measurement region instead of the sim rect */
static volatile LONG g_fix = 1;                  /* [cartrips] scroll_fill=1: route cars hold their count while the camera moves */
static int g_margin = 4;                         /* [cartrips] margin=4: cells added around the sim rect for capture (scroll_fill) */

static void ini_read(void) {
    char path[MAX_PATH], v[32];
    self_path(path, sizeof(path), "cartrips.ini");
    if (!path[0]) return;
    GetPrivateProfileStringA("cartrips", "mode", "replace", v, sizeof(v), path);
    g_mode = (!lstrcmpiA(v, "off") || !lstrcmpiA(v, "0")) ? 0 : !lstrcmpiA(v, "capture") ? 1 :
             !lstrcmpiA(v, "filler") ? 3 : 2;
    g_verify = GetPrivateProfileIntA("cartrips", "verify", 0, path) ? 1 : 0;
    g_time = GetPrivateProfileIntA("cartrips", "time_route", 0, path) ? 1 : 0;
    g_dump = GetPrivateProfileIntA("cartrips", "dump", 0, path) ? 1 : 0;
    g_choice = GetPrivateProfileIntA("cartrips", "choice", 0, path) ? 1 : 0;
    g_solve = GetPrivateProfileIntA("cartrips", "solve", 0, path) ? 1 : 0;
    if (g_mode >= 2) g_solve = 1;                 /* route cars need the solver */
    g_time_agents = GetPrivateProfileIntA("cartrips", "time_agents", 0, path) ? 1 : 0;
    GetPrivateProfileStringA("cartrips", "rect", "", v, sizeof(v), path);
    if (v[0] && sscanf(v, "%d,%d,%d,%d", &g_ovr[0], &g_ovr[1], &g_ovr[2], &g_ovr[3]) == 4) g_rect_ovr = 1;
    g_log_s = GetPrivateProfileIntA("cartrips", "log_s", 10, path);
    g_fix = GetPrivateProfileIntA("cartrips", "scroll_fill", 1, path) ? 1 : 0;
    g_margin = GetPrivateProfileIntA("cartrips", "margin", 4, path);
    if (g_margin < 0) g_margin = 0;
    if (g_margin > 32) g_margin = 32;
    if (g_log_s < 1) g_log_s = 1;
}

/* ============================================================ records */

#pragma pack(push, 1)
typedef struct { short x0, z0, x1, z1; BYTE type, prev, side, retry; } Node;          /* 12 bytes */
#define MAXSTORE 256
typedef struct {
    DWORD seq;                    /* commit order (global) */
    DWORD tid;                    /* routing thread */
    DWORD c1, c2;                 /* return address into route_trip's caller, and into that caller's caller */
    DWORD qpc_lo, qpc_hi;         /* commit time */
    short rect[4];                /* sim rect used for the in-view test (x0 z0 x1 z1) */
    BYTE flag, dkind, m5, m6, m7, trunc, vrect, pad;
    WORD n;                       /* nodes in the whole path */
    WORD first;                   /* index (pop order) of nodes[0] */
    WORD nstore;                  /* nodes stored */
    WORD nin;                     /* nodes meeting the rect */
    WORD lo, hi;                  /* first / last index (pop order) of a node meeting the rect */
    DWORD types;                  /* bit per node class (tclass) */
    Node dest, origin;            /* first and last pop */
    Node nodes[MAXSTORE];         /* pop order (destination first): indices first .. first + nstore - 1 */
} TripRec;
#pragma pack(pop)

static int tclass(int ty) {
    switch (ty & 0xff) {
        case 0x80: return 0; case 1: return 1; case 2: return 2; case 3: return 3; case 4: return 4; case 8: return 5;
        case 0x14: return 6; case 0x18: return 7; case 0x30: return 8; case 0x41: return 9; case 0x42: return 10;
        case 0x43: return 11; case 0x50: return 12; default: return 13;
    }
}

/* ============================================================ per-thread state */

#define MAXP 8192
#define NCALLER 48
typedef struct { DWORD c1, c2; BYTE dk, m5, m6, m7; DWORD trips, flagged, vp, vpflag, nodes, roadonly, dep_nodes; } Caller;

typedef struct TS {
    struct TS *next;
    DWORD tid;
    LONG epoch;
    /* the trip being popped */
    int n, nin, lo, hi;
    DWORD types;
    BYTE flag, dkind, m5, m6, m7;
    DWORD c1, c2;
    short rect[4];
    BYTE vrect;
    Node origin;
    Node p[MAXP];
    WORD dep[MAXP];               /* verify: deposit calls attributed to node i */
    DWORD dep_out;                /* verify: deposits outside the node popped last (this trip) */
    /* statistics: written by the owner thread only, read by the logger */
    volatile DWORD paths, nodes, flagged, vp, vpnodes, vpflag, roadonly, vproadonly, transit, mixed, trunc;
    volatile DWORD commits, drops, wraps;
    volatile DWORD typecnt[14];
    volatile DWORD rt_calls, rt_cyc_lo, rt_cyc_hi, rt_seq;   /* rt_seq odd while the pair is written */
    /* verify totals */
    volatile DWORD v_trips, v_flag_trips, v_exact, v_dep_calls, v_dep_out, v_nodes_full, v_nodes_gated, v_nodes_bad,
                   v_unflag_dep, v_flag_nodep, v_trips_bad;
    Caller ct[NCALLER];
    volatile DWORD ct_over;
    /* choice (open question: which neighbour the ring scan keeps) */
    int pend, pend_x, pend_z, pend_bx, pend_bz;
    BYTE pend_road[4], pend_byte[4];
    volatile DWORD ch_steps, ch_max, ch_min, ch_mid, ch_alleq, ch_single, ch_b_not_cand, ch_fault;
} TS;

static DWORD g_tls = TLS_OUT_OF_INDEXES;
static TS *volatile g_threads;
static volatile LONG g_nthreads;
static volatile LONG g_epoch;

static TS *ts_new(void) {
    TS *t = (TS *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, sizeof(TS));
    TS *head;
    if (!t) return NULL;
    t->tid = GetCurrentThreadId();
    t->epoch = g_epoch;
    TlsSetValue(g_tls, t);
    do { head = g_threads; t->next = head; }
    while (InterlockedCompareExchangePointer((PVOID volatile *)&g_threads, t, head) != head);
    InterlockedIncrement(&g_nthreads);
    return t;
}

/* TlsGetValue clears the last error; the TEB slot read does not touch it (index < 64: TEB+0xE10). */
static __forceinline TS *ts_get(void) {
    TS *t;
    if (g_tls < 64) t = (TS *)__readfsdword(0xE10 + g_tls * 4);
    else { DWORD e = GetLastError(); t = (TS *)TlsGetValue(g_tls); SetLastError(e); }
    if (!t) { DWORD e = GetLastError(); t = ts_new(); SetLastError(e); }
    return t;
}

/* ============================================================ the sim rect, written by the game thread */

static volatile LONG g_rect_xz0 = 0x7fff7fff, g_rect_xz1 = 0;   /* (x << 16 | z): empty until the first tick */
static volatile LONG g_sim_xz0 = 0x7fff7fff, g_sim_xz1 = 0;     /* the sim rect itself (g_rect_xz* add the capture margin) */
static LONG g_box[4];                                           /* view box, cells (layer +0x27b0..+0x27bc), game thread */
static LONG g_box_prev[4];                                      /* the view box before the latest sim-rect change */
static DWORD g_last_move_ms;                                    /* last tick the sim rect changed (game thread) */
static void strips_add(int ox0, int oz0, int ox1, int oz1, int nx0, int nz0, int nx1, int nz1);   /* sc3cartrips_cars.c */
static volatile LONG g_rect_virtual;

/* ============================================================ the ring (MPSC) */

#define RN 1024
typedef struct { volatile LONG seq; DWORD pad[3]; TripRec r; } RSlot;
static RSlot *g_ring;
static volatile LONG g_wpos;
static LONG g_rpos;                              /* game thread only */
static volatile LONG g_seq;

static void commit(TS *t) {
    LONG pos = g_wpos, dif;
    RSlot *s;
    TripRec *r;
    int first, last, i, m;
    LARGE_INTEGER q;
    for (;;) {
        s = &g_ring[pos & (RN - 1)];
        dif = s->seq - pos;
        if (dif == 0) {
            if (InterlockedCompareExchange(&g_wpos, pos + 1, pos) == pos) break;
            pos = g_wpos;
        } else if (dif < 0) { t->drops++; return; }
        else pos = g_wpos;
    }
    r = &s->r;
    r->seq = (DWORD)InterlockedIncrement(&g_seq);
    r->tid = t->tid; r->c1 = t->c1; r->c2 = t->c2;
    QueryPerformanceCounter(&q);
    r->qpc_lo = q.LowPart; r->qpc_hi = (DWORD)q.HighPart;
    memcpy(r->rect, t->rect, sizeof(r->rect));
    r->flag = t->flag; r->dkind = t->dkind; r->m5 = t->m5; r->m6 = t->m6; r->m7 = t->m7; r->vrect = t->vrect;
    r->n = (WORD)(t->n > 0xffff ? 0xffff : t->n);
    r->nin = (WORD)(t->nin > 0xffff ? 0xffff : t->nin);
    r->lo = (WORD)t->lo; r->hi = (WORD)t->hi;
    r->types = t->types;
    m = t->n < MAXP ? t->n : MAXP;
    r->dest = t->p[0];
    r->origin = t->origin;
    /* the in-view window and one node either side */
    first = t->lo > 0 ? t->lo - 1 : 0;
    last = t->hi + 1 < m ? t->hi + 1 : m - 1;
    r->trunc = (BYTE)((t->n > MAXP ? 1 : 0) | (last - first + 1 > MAXSTORE ? 2 : 0));
    if (last - first + 1 > MAXSTORE) last = first + MAXSTORE - 1;
    r->first = (WORD)first;
    r->nstore = (WORD)(last - first + 1);
    for (i = first; i <= last; i++) r->nodes[i - first] = t->p[i];
    MemoryBarrier();
    s->seq = pos + 1;
    t->commits++;
}

/* ============================================================ capture */

static DWORD g_pop_target, g_dep_target, g_tick_target;     /* runtime addresses of 0x10009eed, 0x10006edd, 0x1001f44a */
static DWORD g_time_lo, g_time_hi;                          /* time_wrap code range */
static volatile LONG g_cap_on;

static Caller *caller_of(TS *t) {
    int i;
    for (i = 0; i < NCALLER; i++) {
        Caller *c = &t->ct[i];
        if (c->trips && c->c1 == t->c1 && c->c2 == t->c2 && c->dk == t->dkind && c->m5 == t->m5 && c->m6 == t->m6 &&
            c->m7 == t->m7) return c;
        if (!c->trips) {
            c->c1 = t->c1; c->c2 = t->c2; c->dk = t->dkind; c->m5 = t->m5; c->m6 = t->m6; c->m7 = t->m7;
            return c;
        }
    }
    t->ct_over++;
    return NULL;
}

static int dep_expect(int type, int area) {       /* deposit calls the switch makes for a node (flag set, gate true) */
    switch (type) {
        case 1: case 2: case 4: case 8: case 0x14: case 0x50: return area;
        case 0x18: case 0x30: return 2 * area;      /* 0x15 then 8 (falls into LAB_100074ce) */
        default: return 0;                          /* 0x80, 3, 0x41..0x43: no deposit */
    }
}

static void verify_trip(TS *t) {
    int i, m = t->n < MAXP ? t->n : MAXP, bad = 0, any = 0;
    t->v_trips++;
    if (t->flag) t->v_flag_trips++;
    t->v_dep_out += t->dep_out;
    if (t->dep_out) bad = 1;
    for (i = 0; i < m; i++) {
        Node *nd = &t->p[i];
        int area = (nd->x1 - nd->x0 + 1) * (nd->z1 - nd->z0 + 1);
        int want = t->flag ? dep_expect(nd->type, area) : 0, got = t->dep[i];
        if (got) any = 1;
        if (got == want && want) t->v_nodes_full++;
        else if (got == 0 && want) t->v_nodes_gated++;          /* FUN_10008c5b(occupant) false: no deposit */
        else if (got != want) { t->v_nodes_bad++; bad = 1; }
        t->dep[i] = 0;
    }
    if (!t->flag && any) { t->v_unflag_dep++; bad = 1; }
    if (t->flag && !any) t->v_flag_nodep++;
    if (bad) t->v_trips_bad++; else t->v_exact++;
}

static void finish_trip(TS *t) {
    Caller *c;
    int roadonly = (t->types & ~0xfu) == 0, road = (t->types & 0xe) != 0, other = (t->types & ~0xfu) != 0;
    t->paths++;
    t->nodes += t->n;
    if (t->n > MAXP) t->trunc++;
    if (t->flag) t->flagged++;
    if (roadonly) t->roadonly++;
    else if (road) t->mixed++;
    else if (other) t->transit++;
    if (t->nin > 0) {
        t->vp++; t->vpnodes += t->nin;
        if (t->flag) t->vpflag++;
        if (roadonly) t->vproadonly++;
    }
    c = caller_of(t);
    if (c) {
        c->trips++; c->nodes += t->n;
        if (t->flag) c->flagged++;
        if (roadonly) c->roadonly++;
        if (t->nin > 0) { c->vp++; if (t->flag) c->vpflag++; }
    }
    if (g_verify) {
        int i, m = t->n < MAXP ? t->n : MAXP, k = 0;
        for (i = 0; i < m; i++) k += t->dep[i] != 0;
        if (c) c->dep_nodes += k;
        verify_trip(t);
    }
    if (t->nin > 0 && g_ring) commit(t);
    t->n = 0;
}

/* CHOICE (choice=1, measurement): which road neighbour did the router keep? SimTransit FUN_1000755e's ring scan
   for a road node (type 1) takes a neighbour cell when its flags (+0x5c, u16) have bit 1 and not 0x10, and compares
   the congestion bytes (+0x6c) of the candidates below DAT_1001f0c0; the static read (LANE_DENSITY 1 table) says the
   kept one is replaced unless the new byte is LOWER, i.e. the most congested is kept. Tested on trips without the
   deposit flag (their own deposits never touch the grid): at the pop of a road node a whose successor b (the node
   popped just before) is a road cell beside it, the four neighbours' flags and bytes are read; at the next pop (a's
   predecessor p, which is visited) the step is scored among a's road neighbours other than p and a, under the cap.
   Visited cells cannot be seen here, so a few steps score "mid" for that reason alone. */
static const int NB[4][2] = { { -1, 0 }, { 0, -1 }, { 1, 0 }, { 0, 1 } };
static BYTE g_cap = 150;

static int choice_read(TS *t, BYTE *fp, int x, int z) {
    BYTE *layer = *(BYTE **)(fp - 0x14);
    int k, w;
    __try {
        BYTE **rows6c = *(BYTE ***)(*(BYTE **)(layer + 0x6c) + 0xc);
        WORD **rows5c = *(WORD ***)(*(BYTE **)(layer + 0x5c) + 0xc);
        w = *(int *)(layer + 0x14);
        for (k = 0; k < 4; k++) {
            int nx = x + NB[k][0], nz = z + NB[k][1];
            WORD f;
            if (nx < 0 || nz < 0 || nx >= w || nz >= w) { t->pend_road[k] = 0; continue; }
            f = rows5c[nx][nz];
            t->pend_road[k] = (BYTE)((f & 1) && !(f & 0x10));
            t->pend_byte[k] = rows6c[nx][nz];
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) { t->ch_fault++; return 0; }
    return 1;
}

static void choice_score(TS *t, int px, int pz) {
    int k, n = 0, bk = -1, mx = -1, mn = 256;
    for (k = 0; k < 4; k++) {
        int nx = t->pend_x + NB[k][0], nz = t->pend_z + NB[k][1];
        if (nx == px && nz == pz) continue;                      /* the predecessor: visited */
        if (!t->pend_road[k] || t->pend_byte[k] >= g_cap) {
            if (nx == t->pend_bx && nz == t->pend_bz) { t->ch_b_not_cand++; return; }
            continue;
        }
        n++;
        if (nx == t->pend_bx && nz == t->pend_bz) bk = k;
        if (t->pend_byte[k] > mx) mx = t->pend_byte[k];
        if (t->pend_byte[k] < mn) mn = t->pend_byte[k];
    }
    if (bk < 0) { t->ch_b_not_cand++; return; }
    t->ch_steps++;
    if (n == 1) { t->ch_single++; return; }
    if (mx == mn) { t->ch_alleq++; return; }
    if (t->pend_byte[bk] == mx) t->ch_max++;
    else if (t->pend_byte[bk] == mn) t->ch_min++;
    else t->ch_mid++;
}

static void choice_step(TS *t, BYTE *fp, int i, int x0, int z0, int x1, int z1, int ty) {
    if (t->pend) { t->pend = 0; choice_score(t, x0, z0); }
    if (t->flag || ty != 1 || x0 != x1 || z0 != z1 || i == 0 || i > MAXP) return;
    {   Node *b = &t->p[i - 1];
        int dx = b->x0 - x0, dz = b->z0 - z0;
        if (b->type != 1 || b->x0 != b->x1 || b->z0 != b->z1 || (dx * dx + dz * dz) != 1) return;
        if (!choice_read(t, fp, x0, z0)) return;
        t->pend = 1; t->pend_x = x0; t->pend_z = z0; t->pend_bx = b->x0; t->pend_bz = b->z0;
    }
}

/* pop_stub's C half: node = the 32-byte node copy (ebx), fp = route_trip's frame (ebp) */
static void __cdecl on_pop(BYTE *node, BYTE *fp) {
    TS *t = ts_get();
    int i, x0, z0, x1, z1, ty;
    if (!t) return;
    if (t->epoch != g_epoch) {                    /* capture was switched: drop a half trip */
        int k, m = t->n < MAXP ? t->n : MAXP;
        for (k = 0; k < m; k++) t->dep[k] = 0;
        t->epoch = g_epoch; t->n = 0;
    }
    x0 = *(int *)(node + 4); z0 = *(int *)(node + 8); x1 = *(int *)(node + 0xc); z1 = *(int *)(node + 0x10);
    ty = node[0x14];
    if (t->n == 0) {
        LONG a = g_rect_xz0, b = g_rect_xz1;
        DWORD c1 = *(DWORD *)(fp + 4), up = *(DWORD *)fp;
        DWORD sb = __readfsdword(4), sl = __readfsdword(8);             /* this thread's stack base / limit */
        /* args read at the first pop, before the deposit loops reuse [ebp+0x20] (SimTransit 0x10007393) */
        t->flag = fp[0x14]; t->dkind = fp[0xc]; t->m5 = fp[0x18]; t->m6 = fp[0x1c]; t->m7 = fp[0x20];
        /* the frame chain is followed only inside this thread's stack: a caller built without a frame pointer
           (sc3perf's hooks, /O2) leaves ebp holding anything */
        if (c1 >= g_time_lo && c1 < g_time_hi) {     /* time_wrap between route_trip and its caller */
            if (up >= sl && up + 8 <= sb) { c1 = *(DWORD *)(up + 4); up = *(DWORD *)up; }
            else { c1 = 0; up = 0; }
        }
        t->c1 = c1;
        t->c2 = (up >= sl && up + 8 <= sb) ? *(DWORD *)(up + 4) : 0;
        t->rect[0] = (short)(a >> 16); t->rect[1] = (short)a; t->rect[2] = (short)(b >> 16); t->rect[3] = (short)b;
        t->vrect = (BYTE)g_rect_virtual;
        t->nin = 0; t->lo = -1; t->hi = -1; t->types = 0; t->dep_out = 0; t->pend = 0;
    }
    if (g_choice) choice_step(t, fp, t->n, x0, z0, x1, z1, ty);
    i = t->n;
    if (i < MAXP) {
        Node *d = &t->p[i];
        d->x0 = (short)x0; d->z0 = (short)z0; d->x1 = (short)x1; d->z1 = (short)z1;
        d->type = (BYTE)ty; d->prev = node[0x15]; d->side = node[0x1c]; d->retry = node[0x1d];
        if (x1 >= t->rect[0] && x0 <= t->rect[2] && z1 >= t->rect[1] && z0 <= t->rect[3]) {
            t->nin++;
            if (t->lo < 0) t->lo = i;
            t->hi = i;
        }
    }
    t->n = i + 1;
    {   int k = tclass(ty);
        t->typecnt[k]++;
        t->types |= 1u << k;
    }
    if (ty == 0x80) {
        Node *o = &t->origin;
        o->x0 = (short)x0; o->z0 = (short)z0; o->x1 = (short)x1; o->z1 = (short)z1;
        o->type = (BYTE)ty; o->prev = node[0x15]; o->side = node[0x1c]; o->retry = node[0x1d];
        finish_trip(t);
    }
}

static __declspec(naked) void pop_stub(void) {
    __asm {
        pushad
        pushfd
        push ebp
        push ebx
        call on_pop
        add esp, 8
        popfd
        popad
        jmp dword ptr [g_pop_target]
    }
}

/* verify: deposit call inside the pop loop; [esp+4] x, [esp+8] z, [esp+0xc] amount, [esp+0x10] mask */
static void __cdecl on_dep(int x, int z) {
    TS *t = ts_get();
    int i;
    if (!t || t->n == 0) return;
    i = t->n - 1;
    if (i >= MAXP) return;
    t->v_dep_calls++;
    if (x < t->p[i].x0 || x > t->p[i].x1 || z < t->p[i].z0 || z > t->p[i].z1) t->dep_out++;
    else if (t->dep[i] < 0xffff) t->dep[i]++;
}

static __declspec(naked) void dep_stub(void) {
    __asm {
        pushad
        pushfd
        push dword ptr [esp + 0x2c]          /* z: pushfd 4 + pushad 0x20 + ret 4 -> x at +0x28, z at +0x2c */
        push dword ptr [esp + 0x2c]          /* x (one push later) */
        call on_dep
        add esp, 8
        popfd
        popad
        jmp dword ptr [g_dep_target]
    }
}

/* time_route: per-thread TSC cycles inside route_trip */
static void __cdecl time_add(DWORD lo, DWORD hi) {
    TS *t = ts_get();
    unsigned __int64 v;
    if (!t) return;
    t->rt_seq++;
    v = ((unsigned __int64)t->rt_cyc_hi << 32 | t->rt_cyc_lo) + ((unsigned __int64)hi << 32 | lo);
    t->rt_cyc_lo = (DWORD)v; t->rt_cyc_hi = (DWORD)(v >> 32);
    t->rt_calls++;
    t->rt_seq++;
}

static BYTE *g_tramp;                                     /* mov eax, imm32 (relocated) ; jmp route_trip + 5 */

static __declspec(naked) void time_wrap(void) {
    __asm {
        push ebp
        mov ebp, esp
        push ecx                         ; [ebp-4] this
        rdtsc
        push edx                         ; [ebp-8]
        push eax                         ; [ebp-0xc]
        mov ecx, [ebp - 4]
        push dword ptr [ebp + 0x20]
        push dword ptr [ebp + 0x1c]
        push dword ptr [ebp + 0x18]
        push dword ptr [ebp + 0x14]
        push dword ptr [ebp + 0x10]
        push dword ptr [ebp + 0x0c]
        push dword ptr [ebp + 0x08]
        call dword ptr [g_tramp]         ; route_trip: thiscall, ret 0x1c
        push eax
        rdtsc
        sub eax, [ebp - 0xc]
        sbb edx, [ebp - 8]
        push edx
        push eax
        call time_add
        add esp, 8
        pop eax
        mov esp, ebp
        pop ebp
        ret 0x1c
    }
}

/* ============================================================ game-thread drain */

#define QN 256
static TripRec *g_queue;                         /* newest viewport trips (M3's input), game thread only */
static int g_qhead, g_qlen;
static volatile DWORD g_drained, g_ticks, g_game_tid, g_lat_max_us, g_lat_sum_us;
static CRITICAL_SECTION g_dlock;                 /* dump buffer */
static BYTE *g_dbuf;
static int g_dlen;
#define DCAP (512 * 1024)
static volatile DWORD g_dump_drop;

#include "sc3cartrips_lanes.c"
static int write_q(BYTE *at, const BYTE *bytes, int len);
static void call_bytes(BYTE *out, BYTE *at, void *to);
#include "sc3cartrips_cars.c"

/* trips drained but not solved yet (M3: carried to the next tick instead of dropped past the budget) */
static DWORD g_q_total, g_q_done;

static void __cdecl on_tick(BYTE *layer8) {
    BYTE *L = layer8 - 8;
    int x0, z0, x1, z1, virt = 0;
    LARGE_INTEGER now;
    LONGLONG budget_end;
    g_ticks++;
    g_game_tid = GetCurrentThreadId();
    __try {
        x0 = *(int *)(L + 0xb0); z0 = *(int *)(L + 0xb4); x1 = *(int *)(L + 0xb8); z1 = *(int *)(L + 0xbc);
        if (!(x1 > x0 && z1 > z0)) {             /* cars off (zoomed out): Berlin's 33 x 28 rect at the view centre */
            int cx = (*(int *)(L + 0x90) + *(int *)(L + 0x98)) >> 1, cz = (*(int *)(L + 0x94) + *(int *)(L + 0x9c)) >> 1;
            x0 = cx - 16; z0 = cz - 13; x1 = cx + 16; z1 = cz + 14;
            virt = 1;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) { return; }
    if (g_rect_ovr) { x0 = g_ovr[0]; z0 = g_ovr[1]; x1 = g_ovr[2]; z1 = g_ovr[3]; virt = 2; }
    {   LONG s0 = (LONG)((x0 & 0xffff) << 16 | (z0 & 0xffff)), s1 = (LONG)((x1 & 0xffff) << 16 | (z1 & 0xffff));
        if (s0 != g_sim_xz0 || s1 != g_sim_xz1) {
            LONG a = g_sim_xz0, b = g_sim_xz1;
            g_last_move_ms = GetTickCount();
            memcpy(g_box_prev, g_box, sizeof(g_box_prev));      /* g_box still holds the box shown before this step */
            if (b) strips_add((short)(a >> 16), (short)a, (short)(b >> 16), (short)b, x0, z0, x1, z1);
        }
        g_sim_xz0 = s0; g_sim_xz1 = s1;
    }
    __try {
        g_box[0] = *(int *)(L + 0x27b0); g_box[1] = *(int *)(L + 0x27b4); g_box[2] = *(int *)(L + 0x27b8); g_box[3] = *(int *)(L + 0x27bc);
    } __except (EXCEPTION_EXECUTE_HANDLER) { }
    if (g_fix && g_margin && g_mode_now >= MODE_REPLACE && !virt) {
        /* scroll_fill: capture and solve over the sim rect plus a margin, so routes reach past the view edge */
        int mx = *(int *)(g_strt_base + 0x33204), mz = *(int *)(g_strt_base + 0x33114);
        if (mx <= 0 || mx > 4096) mx = 1024;
        if (mz <= 0 || mz > 4096) mz = 1024;
        x0 -= g_margin; z0 -= g_margin; x1 += g_margin; z1 += g_margin;
        if (x0 < 0) x0 = 0;
        if (z0 < 0) z0 = 0;
        if (x1 > mx - 1) x1 = mx - 1;
        if (z1 > mz - 1) z1 = mz - 1;
    }
    g_rect_xz0 = (LONG)((x0 & 0xffff) << 16 | (z0 & 0xffff));
    g_rect_xz1 = (LONG)((x1 & 0xffff) << 16 | (z1 & 0xffff));
    g_rect_virtual = virt;
    if (!g_ring) return;
    QueryPerformanceCounter(&now);
    budget_end = now.QuadPart + g_freq.QuadPart * 4 / 1000;            /* M2 solving: 4 ms per tick at most */
    for (;;) {
        RSlot *s = &g_ring[g_rpos & (RN - 1)];
        TripRec *q;
        LONGLONG c;
        DWORD us;
        if (s->seq != g_rpos + 1) break;
        MemoryBarrier();
        q = &g_queue[g_qhead];
        memcpy(q, &s->r, sizeof(TripRec));
        g_qhead = (g_qhead + 1) % QN;
        if (g_qlen < QN) g_qlen++;
        c = ((LONGLONG)s->r.qpc_hi << 32) | s->r.qpc_lo;
        us = (DWORD)((now.QuadPart - c) * 1000000 / g_freq.QuadPart);
        if (us > g_lat_max_us) g_lat_max_us = us;
        g_lat_sum_us += us;
        MemoryBarrier();
        s->seq = g_rpos + RN;
        g_rpos++;
        g_drained++;
        g_q_total++;
        if (g_dump) {
            int sz = (int)(sizeof(TripRec) - (MAXSTORE - q->nstore) * sizeof(Node));
            EnterCriticalSection(&g_dlock);
            if (g_dlen + sz <= DCAP) { memcpy(g_dbuf + g_dlen, q, sz); g_dlen += sz; }
            else g_dump_drop++;
            LeaveCriticalSection(&g_dlock);
        }
    }
    if (g_solve && g_strt_base) {
        if (g_q_total - g_q_done > QN) { g_c3[C3_TRIPS_DROPPED] += g_q_total - g_q_done - QN; g_q_done = g_q_total - QN; }
        while (g_q_done < g_q_total) {
            LARGE_INTEGER t;
            TripRec *q = &g_queue[(g_qhead + QN - (g_q_total - g_q_done)) % QN];
            QueryPerformanceCounter(&t);
            if (t.QuadPart > budget_end) { g_c3[C3_TRIPS_CARRIED]++; break; }
            g_q_done++;
            if (q->c1 == g_pop_target - 0x9eed + 0x70b3) { g_c3[C3_ZONE_EXCLUDED]++; continue; }   /* D5: zone probes */
            solve_trip(q, &budget_end);
        }
    }
    {   BYTE *prod = *(BYTE **)(layer8 + 0xf8);
        spawn_tick(prod);
        g_skip_tick = g_mode_now == MODE_REPLACE;
    }
}
static __declspec(naked) void tick_stub(void) {
    __asm {
        pushad
        pushfd
        push esi
        call on_tick
        add esp, 4
        popfd
        popad
        cmp dword ptr [g_skip_tick], 0
        jne skip
        jmp dword ptr [g_tick_target]
    skip:
        ret 4                                    /* replace mode: no random cars (FUN_1001f44a, ret 4) */
    }
}

/* ============================================================ patching */

/* replace len bytes at `at` (inside one aligned qword) with one locked 8-byte exchange; page left RWX
   (PERFORMANCE.md "mods patching the same page must not restore its protection") */
static int write_q(BYTE *at, const BYTE *bytes, int len) {
    BYTE *q = (BYTE *)((DWORD)at & ~7u);
    int off = (int)(at - q);
    DWORD old;
    LONGLONG cur, nw;
    if (off + len > 8) return 0;
    if (!VirtualProtect(q, 8, PAGE_EXECUTE_READWRITE, &old)) return 0;
    do {
        cur = *(volatile LONGLONG *)q;
        nw = cur;
        memcpy((BYTE *)&nw + off, bytes, len);
    } while (InterlockedCompareExchange64((volatile LONGLONG *)q, nw, cur) != cur);
    FlushInstructionCache(GetCurrentProcess(), q, 8);
    return 1;
}

/* a 5-byte write that does not fit one aligned qword: every other thread suspended, retried until none of them
   is inside the bytes (the sc3netmod_ld_set pattern). Used only at arm time, before a city routes. */
static int write_suspended(BYTE *at, const BYTE *bytes, int len) {
    HANDLE th[256], snap;
    THREADENTRY32 te;
    DWORD me = GetCurrentThreadId(), pid = GetCurrentProcessId(), old;
    int n = 0, k, tries, busy = 1;
    snap = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
    te.dwSize = sizeof(te);
    if (snap != INVALID_HANDLE_VALUE && Thread32First(snap, &te)) do {
        if (te.th32OwnerProcessID == pid && te.th32ThreadID != me && n < 256) {
            HANDLE h = OpenThread(THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT, FALSE, te.th32ThreadID);
            if (h) th[n++] = h;
        }
        te.dwSize = sizeof(te);
    } while (Thread32Next(snap, &te));
    if (snap != INVALID_HANDLE_VALUE) CloseHandle(snap);
    if (!VirtualProtect(at, len, PAGE_EXECUTE_READWRITE, &old)) busy = 2;
    for (tries = 0; tries < 200 && busy == 1; tries++) {
        busy = 0;
        for (k = 0; k < n; k++) SuspendThread(th[k]);
        for (k = 0; k < n && !busy; k++) {
            CONTEXT c;
            c.ContextFlags = CONTEXT_CONTROL;
            if (GetThreadContext(th[k], &c) && c.Eip > (DWORD)at && c.Eip < (DWORD)at + len) busy = 1;
        }
        if (!busy) { memcpy(at, bytes, len); FlushInstructionCache(GetCurrentProcess(), at, len); }
        for (k = 0; k < n; k++) ResumeThread(th[k]);
        if (busy) Sleep(1);
    }
    for (k = 0; k < n; k++) CloseHandle(th[k]);
    return busy == 0;
}

static BYTE *g_pop_site;
static BYTE g_pop_orig[5], g_pop_new[5];

static void call_bytes(BYTE *out, BYTE *at, void *to) {
    out[0] = 0xE8;
    *(DWORD *)(out + 1) = (DWORD)to - (DWORD)(at + 5);
}

static int site_ok(BYTE *at, const BYTE *expect, int n) {
    return !IsBadReadPtr(at, n) && !memcmp(at, expect, n);
}

static volatile LONG g_toggles;

__declspec(dllexport) int __cdecl sc3cartrips_set(int on) {
    int prev = g_cap_on;
    if (!g_pop_site) return -1;
    on = on ? 1 : 0;
    if (prev == on) return prev;
    InterlockedIncrement(&g_epoch);
    if (!write_q(g_pop_site, on ? g_pop_new : g_pop_orig, 5)) return -1;
    g_cap_on = on;
    g_toggles++;
    return prev;
}

/* cumulative counters summed over the routing threads, for ctm_alt.py:
   [0] paths [1] nodes [2] vp [3] vpflag [4] commits [5] drops [6] drained [7] rt_calls [8] rt_cyc lo [9] rt_cyc hi
   [10] capture on [11] threads [12] flagged [13] roadonly [14] ticks [15] toggles. Returns the count written. */
__declspec(dllexport) int __cdecl sc3cartrips_stats(DWORD *out, int n) {
    DWORD v[16];
    unsigned __int64 cyc = 0;
    TS *t;
    int i;
    memset(v, 0, sizeof(v));
    for (t = g_threads; t; t = t->next) {
        DWORD s1, lo, hi, calls;
        v[0] += t->paths; v[1] += t->nodes; v[2] += t->vp; v[3] += t->vpflag; v[4] += t->commits; v[5] += t->drops;
        v[12] += t->flagged; v[13] += t->roadonly;
        do { s1 = t->rt_seq; lo = t->rt_cyc_lo; hi = t->rt_cyc_hi; calls = t->rt_calls; } while ((s1 & 1) || s1 != t->rt_seq);
        v[7] += calls;
        cyc += (unsigned __int64)hi << 32 | lo;
    }
    v[6] = g_drained; v[8] = (DWORD)cyc; v[9] = (DWORD)(cyc >> 32); v[10] = g_cap_on; v[11] = g_nthreads;
    v[14] = g_ticks; v[15] = g_toggles;
    for (i = 0; i < n && i < 16; i++) out[i] = v[i];
    return i;
}

static int arm_capture(HMODULE st) {
    static const BYTE e_pop[] = { 0xf3, 0xa5, 0x8d, 0x4d, 0x80, 0xe8, 0xf0, 0x2b, 0x00, 0x00, 0x80, 0x7d, 0x14, 0x00 };
    BYTE *p = (BYTE *)st + 0x72f3;
    if (!site_ok(p, e_pop, sizeof(e_pop))) { logf("### CAPTURE: SimTransit+0x72f3 differs from shipped - not armed"); return 0; }
    g_pop_site = p + 5;
    g_pop_target = (DWORD)st + 0x9eed;
    memcpy(g_pop_orig, g_pop_site, 5);
    call_bytes(g_pop_new, g_pop_site, pop_stub);
    return sc3cartrips_set(1) == 0;
}

static int arm_verify(HMODULE st) {
    static const DWORD sites[5] = { 0x73b2, 0x73f8, 0x7463, 0x74be, 0x7500 };
    int i, ok = 0;
    g_dep_target = (DWORD)st + 0x6edd;
    for (i = 0; i < 5; i++) {
        BYTE *p = (BYTE *)st + sites[i], b[5];
        if (p[0] != 0xE8 || (DWORD)(p + 5) + *(DWORD *)(p + 1) != g_dep_target) {
            logf("### VERIFY: SimTransit+0x%04lX is not call 0x10006edd - not armed", sites[i]);
            continue;
        }
        call_bytes(b, p, dep_stub);
        ok += ((DWORD)p & 7) <= 3 ? write_q(p, b, 5) : write_suspended(p, b, 5);
    }
    return ok;
}

static int arm_time(HMODULE st) {
    BYTE *p = (BYTE *)st + 0x70d0, b[5];
    DWORD want = (DWORD)st + 0x189b4;
    if (p[0] != 0xB8 || *(DWORD *)(p + 1) != want || p[5] != 0xE8) {
        logf("### TIME: SimTransit+0x70d0 differs from shipped - not armed");
        return 0;
    }
    g_tramp = (BYTE *)VirtualAlloc(NULL, 16, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!g_tramp) return 0;
    memcpy(g_tramp, p, 5);                                /* mov eax, 0x100189b4 (already relocated) */
    g_tramp[5] = 0xE9;
    *(DWORD *)(g_tramp + 6) = (DWORD)(p + 5) - (DWORD)(g_tramp + 10);
    g_time_lo = (DWORD)time_wrap; g_time_hi = g_time_lo + 0x80;   /* the wrapper is ~0x50 bytes */
    b[0] = 0xE9;
    *(DWORD *)(b + 1) = (DWORD)time_wrap - (DWORD)(p + 5);
    return write_q(p, b, 5);
}

static int arm_tick(HMODULE strt) {
    static const BYTE e_tick[] = { 0xff, 0x75, 0x08, 0xe8, 0xbb, 0xc5, 0x00, 0x00, 0x53 };
    BYTE *p = (BYTE *)strt + 0x12e87, b[5];
    if (!site_ok(p, e_tick, sizeof(e_tick))) { logf("### DRAIN: STRTSIM+0x12e87 differs from shipped - not armed"); return 0; }
    g_tick_target = (DWORD)strt + 0x1f44a;
    call_bytes(b, p + 3, tick_stub);
    return write_q(p + 3, b, 5);
}

/* ============================================================ logger */

static void mod_rva(DWORD a, char *out, int cap) {
    HMODULE m = NULL;
    char name[MAX_PATH] = "?", *b;
    if (!a) { lstrcpynA(out, "0", cap); return; }
    GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT, (LPCSTR)a, &m);
    if (m) GetModuleFileNameA(m, name, sizeof(name));
    b = strrchr(name, '\\');
    if (m) _snprintf(out, cap, "%s+0x%lX", b ? b + 1 : name, a - (DWORD)m);
    else _snprintf(out, cap, "0x%08lX", a);
    out[cap - 1] = 0;
}

typedef struct { DWORD v[24]; DWORD ty[14]; DWORD ch[8]; } Sum;
static void sum_threads(Sum *s) {
    TS *t;
    int k;
    memset(s, 0, sizeof(*s));
    for (t = g_threads; t; t = t->next) {
        s->v[0] += t->paths; s->v[1] += t->nodes; s->v[2] += t->flagged; s->v[3] += t->roadonly; s->v[4] += t->mixed;
        s->v[5] += t->transit; s->v[6] += t->vp; s->v[7] += t->vpflag; s->v[8] += t->vproadonly; s->v[9] += t->vpnodes;
        s->v[10] += t->commits; s->v[11] += t->drops; s->v[12] += t->trunc;
        s->v[13] += t->v_trips; s->v[14] += t->v_flag_trips; s->v[15] += t->v_exact; s->v[16] += t->v_dep_calls;
        s->v[17] += t->v_dep_out; s->v[18] += t->v_nodes_full; s->v[19] += t->v_nodes_gated; s->v[20] += t->v_nodes_bad;
        s->v[21] += t->v_unflag_dep; s->v[22] += t->v_flag_nodep; s->v[23] += t->v_trips_bad;
        for (k = 0; k < 14; k++) s->ty[k] += t->typecnt[k];
        s->ch[0] += t->ch_steps; s->ch[1] += t->ch_max; s->ch[2] += t->ch_min; s->ch[3] += t->ch_mid;
        s->ch[4] += t->ch_alleq; s->ch[5] += t->ch_single; s->ch[6] += t->ch_b_not_cand; s->ch[7] += t->ch_fault;
    }
}

static void log_callers(void) {
    /* merge the per-thread tables by key */
    static Caller all[256];
    int n = 0, i, j;
    DWORD over = 0;
    TS *t;
    for (t = g_threads; t; t = t->next) {
        over += t->ct_over;
        for (i = 0; i < NCALLER && t->ct[i].trips; i++) {
            Caller *c = &t->ct[i];
            for (j = 0; j < n; j++)
                if (all[j].c1 == c->c1 && all[j].c2 == c->c2 && all[j].dk == c->dk && all[j].m5 == c->m5 &&
                    all[j].m6 == c->m6 && all[j].m7 == c->m7) break;
            if (j == n) { if (n == 256) continue; all[n] = *c; all[n].trips = all[n].flagged = all[n].vp = all[n].vpflag = 0;
                          all[n].nodes = all[n].roadonly = all[n].dep_nodes = 0; n++; }
            all[j].trips += c->trips; all[j].flagged += c->flagged; all[j].vp += c->vp; all[j].vpflag += c->vpflag;
            all[j].nodes += c->nodes; all[j].roadonly += c->roadonly; all[j].dep_nodes += c->dep_nodes;
        }
    }
    for (j = 0; j < n; j++) {
        char a[96], b[96];
        mod_rva(all[j].c1, a, sizeof(a));
        mod_rva(all[j].c2, b, sizeof(b));
        logf("CALLER> c1=%s c2=%s dkind=%u m=%u,%u,%u trips=%lu flagged=%lu roadonly=%lu vp=%lu vpflag=%lu nodes=%lu depnodes=%lu",
             a, b, all[j].dk, all[j].m5, all[j].m6, all[j].m7, all[j].trips, all[j].flagged, all[j].roadonly, all[j].vp,
             all[j].vpflag, all[j].nodes, all[j].dep_nodes);
    }
    if (over) logf("CALLER> table overflow: %lu trips not keyed", over);
}

static DWORD WINAPI logger(LPVOID param) {
    HMODULE st, strt;
    Sum prev, cur;
    LARGE_INTEGER q0, q1;
    unsigned __int64 tsc0, tsc1;
    DWORD dr0 = 0, k = 0;
    char path[MAX_PATH];
    HANDLE dump = INVALID_HANDLE_VALUE;
    (void)param;
    while (!(st = GetModuleHandleA("SimTransit.dll"))) Sleep(5);
    while (!(strt = GetModuleHandleA("STRTSIM.DLL"))) Sleep(5);
    g_strt_base = (BYTE *)strt;
    g_cap = *((BYTE *)st + 0x1f0c0);                       /* DAT_1001f0c0, the ring scan's congestion cap */
    {
        int c = arm_capture(st), v = g_verify ? arm_verify(st) : 0, tm = g_time ? arm_time(st) : 0, d = arm_tick(strt);
        logf("### ARMED: capture=%d verify=%d/5 time_route=%d drain=%d (SimTransit 0x%08lX, STRTSIM 0x%08lX) dump=%d choice=%d cap=%u",
             c, v, tm, d, (DWORD)st, (DWORD)strt, g_dump, g_choice, g_cap);
        int cars = g_mode >= MODE_REPLACE ? arm_cars(strt) : 0, ag = g_time_agents ? arm_agtimer() : 0;
        g_mode_now = g_mode >= MODE_REPLACE ? (cars ? g_mode : MODE_CAPTURE) : MODE_CAPTURE;
        logf("### CARS: mode=%s armed=%d (route cars %s) time_agents=%d scroll_fill=%ld margin=%d", g_mode == 3 ? "filler" :
             g_mode == 2 ? "replace" : "capture", cars, g_mode_now >= MODE_REPLACE ? "on" : "off", ag, g_fix, g_margin);
    }
    if (g_dump) {
        static const DWORD hdr[4] = { 0x31544354 /* "TCT1" */, sizeof(TripRec), sizeof(Node), MAXSTORE };
        DWORD w;
        self_path(path, sizeof(path), "cartrips_trips.bin");
        dump = CreateFileA(path, GENERIC_WRITE, FILE_SHARE_READ, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        if (dump != INVALID_HANDLE_VALUE) WriteFile(dump, hdr, sizeof(hdr), &w, NULL);
    }
    if (g_solve && g_dump) {
        static const DWORD hg[2] = { 0x31474354 /* "TCG1" */, 1 }, hr[2] = { 0x31524354 /* "TCR1" */, 1 };
        DWORD w;
        Out *os[2] = { &g_og, &g_or };
        const char *names[2] = { "cartrips_graphs.bin", "cartrips_routes.bin" };
        int i;
        g_cellseen = (BYTE *)VirtualAlloc(NULL, 1024 * 1024 / 8, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        for (i = 0; i < 2; i++) {
            InitializeCriticalSection(&os[i]->cs);
            os[i]->cap = 4 * 1024 * 1024;
            os[i]->buf = (BYTE *)VirtualAlloc(NULL, os[i]->cap, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
            self_path(path, sizeof(path), names[i]);
            os[i]->f = CreateFileA(path, GENERIC_WRITE, FILE_SHARE_READ, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
            if (os[i]->f != INVALID_HANDLE_VALUE) WriteFile(os[i]->f, i ? hr : hg, 8, &w, NULL);
        }
        if (!g_cellseen) g_og.buf = g_or.buf = NULL;
    }
    sum_threads(&prev);
    QueryPerformanceCounter(&q0);
    logf("CLOCK> qpc=%I64d freq=%I64d epoch=%I64u", q0.QuadPart, g_freq.QuadPart, epoch_ms());
    tsc0 = __rdtsc();
    for (;;) {
        int s;
        for (s = 0; s < g_log_s * 4; s++) {
            Sleep(250);
            out_flush(&g_og);
            out_flush(&g_or);
            if (dump != INVALID_HANDLE_VALUE && g_dlen) {
                DWORD w;
                EnterCriticalSection(&g_dlock);
                WriteFile(dump, g_dbuf, (DWORD)g_dlen, &w, NULL);
                g_dlen = 0;
                LeaveCriticalSection(&g_dlock);
            }
        }
        sum_threads(&cur);
        QueryPerformanceCounter(&q1);
        tsc1 = __rdtsc();
        {
            double dt = (double)(q1.QuadPart - q0.QuadPart) / (double)g_freq.QuadPart;
            DWORD dr = g_drained, lat = g_lat_max_us;
            DWORD stats[16];
            g_lat_max_us = 0;
#define D(i) (cur.v[i] - prev.v[i])
            logf("STAT> epoch=%I64u dt=%.2f cap=%ld paths=%lu nodes=%lu flagged=%lu roadonly=%lu mixed=%lu transit=%lu vp=%lu vpflag=%lu "
                 "vproad=%lu vpnodes=%lu commits=%lu drops=%lu drained=%lu qlen=%d lat_max_ms=%.1f trunc=%lu threads=%ld "
                 "rect=%d,%d,%d,%d%s tsc_mhz=%.1f ticks=%lu dumpdrop=%lu",
                 epoch_ms(), dt, g_cap_on, D(0), D(1), D(2), D(3), D(4), D(5), D(6), D(7), D(8), D(9), D(10), D(11), dr - dr0, g_qlen,
                 lat / 1000.0, D(12), g_nthreads, (short)(g_rect_xz0 >> 16), (short)g_rect_xz0, (short)(g_rect_xz1 >> 16),
                 (short)g_rect_xz1, g_rect_virtual == 2 ? " (ini)" : g_rect_virtual ? " (virtual)" : "", (double)(tsc1 - tsc0) / dt / 1e6, g_ticks, g_dump_drop);
            logf("TYPES> 0x80=%lu 1=%lu 2=%lu 3=%lu 4=%lu 8=%lu 0x14=%lu 0x18=%lu 0x30=%lu 0x41=%lu 0x42=%lu 0x43=%lu 0x50=%lu other=%lu",
                 cur.ty[0], cur.ty[1], cur.ty[2], cur.ty[3], cur.ty[4], cur.ty[5], cur.ty[6], cur.ty[7], cur.ty[8], cur.ty[9],
                 cur.ty[10], cur.ty[11], cur.ty[12], cur.ty[13]);
            if (g_verify)
                logf("VERIFY> trips=%lu flagged=%lu exact=%lu bad=%lu dep_calls=%lu dep_outside=%lu nodes_full=%lu nodes_gated=%lu "
                     "nodes_bad=%lu unflagged_with_dep=%lu flagged_no_dep=%lu", cur.v[13], cur.v[14], cur.v[15], cur.v[23],
                     cur.v[16], cur.v[17], cur.v[18], cur.v[19], cur.v[20], cur.v[21], cur.v[22]);
            if (g_choice)
                logf("CHOICE> cap=%u steps=%lu max=%lu min=%lu mid=%lu all_equal=%lu single=%lu b_not_candidate=%lu faults=%lu",
                     g_cap, cur.ch[0], cur.ch[1], cur.ch[2], cur.ch[3], cur.ch[4], cur.ch[5], cur.ch[6], cur.ch[7]);
            if (g_solve)
                logf("M2> trips=%lu routes=%lu one_cell=%lu exact_w0=%lu solved_w1=%lu full_w1=%lu cov90_w1=%lu fail_nopath=%lu "
                     "fail_start=%lu fail_limit=%lu budget_skipped=%lu solve_us_total=%lu max_us=%lu graphs: ok=%lu offmap=%lu "
                     "noocc=%lu notroad=%lu noqi=%lu nograph=%lu fault=%lu dumpdrop=%lu/%lu",
                     g_m2[12], g_m2[0], g_m2[11], g_m2[1], g_m2[2], g_m2[3], g_m2[4], g_m2[5], g_m2[6], g_m2[7], g_m2[8],
                     g_m2[9], g_m2[10], g_gs[GS_OK], g_gs[GS_OFFMAP], g_gs[GS_NOOCC], g_gs[GS_NOTROAD], g_gs[GS_NOQI],
                     g_gs[GS_NOGRAPH], g_gs[GS_FAULT], g_og.drop, g_or.drop);
            if (g_mode >= MODE_REPLACE) {
                BYTE *L = *(BYTE **)(g_strt_base + 0x33208), *prod = L ? *(BYTE **)(L + 0x100) : NULL;
                DWORD alive = 0, target = 0;
                __try { if (prod) { alive = *(DWORD *)(prod + 0xc); target = *(DWORD *)(prod + 0x10); } }
                __except (EXCEPTION_EXECUTE_HANDLER) { alive = target = 0; }
                logf("CARS> epoch=%I64u mode=%ld alive=%lu target=%lu route_cars=%d queued_routes=%d routes_in=%lu routes_old=%lu "
                     "spawn_try=%lu spawn_ok=%lu initfail=%lu placefail=%lu noocc=%lu noedge=%lu outrect=%lu paused_ticks=%lu "
                     "end_arrived=%lu end_lost=%lu end_other=%lu end_other_edge=%lu decisions=%lu followed=%lu cross_followed=%lu "
                     "lost_events=%lu need_route=%lu need_true=%lu steps_covered=%lu steps_total=%lu zone_excluded=%lu "
                     "carried=%lu dropped=%lu spawn_fault=%lu decisions_after_end=%lu retry_ok=%lu cyc=%I64u ag_calls=%lu ag_cyc=%I64u "
                     "fix=%ld fresh_routes=%d fill_try=%lu fill_ok=%lu free=%lu free_gone=%lu still=%d take_skip=%lu inbox=%ld "
                     "strips=%lu strip_quota=%lu strip_try=%lu strip_ok=%lu strip_noroute=%lu",
                     epoch_ms(), g_mode_now, alive, target, g_ncars, g_rq_len, g_c3[C3_ROUTES_QUEUED], g_c3[C3_ROUTES_DROPPED_OLD],
                     g_c3[C3_SPAWN_TRY], g_c3[C3_SPAWN_OK], g_c3[C3_SPAWN_INITFAIL], g_c3[C3_SPAWN_PLACEFAIL], g_c3[C3_SPAWN_NOOCC],
                     g_c3[C3_SPAWN_NOEDGE], g_c3[C3_SPAWN_OUTRECT], g_c3[C3_PAUSED_TICKS], g_c3[C3_END_ARRIVED], g_c3[C3_END_LOST],
                     g_c3[C3_END_OTHER], g_c3[C3_END_OTHER_EDGE], g_c3[C3_DECISIONS], g_c3[C3_FOLLOWED], g_c3[C3_CROSS_FOLLOWED],
                     g_c3[C3_LOST_EVENTS], g_c3[C3_NEED_CALLS_ROUTE], g_c3[C3_NEED_TRUE_ROUTE], g_c3[C3_STEPS_COVERED],
                     g_c3[C3_STEPS_TOTAL], g_c3[C3_ZONE_EXCLUDED], g_c3[C3_TRIPS_CARRIED], g_c3[C3_TRIPS_DROPPED], g_c3[C3_SPAWN_FAULT], g_c3[C3_DECISIONS_AFTER], g_c3[C3_SPAWN_RETRY_OK],
                     (unsigned __int64)g_c3_cyc_hi << 32 | g_c3_cyc_lo, g_ag_calls, (unsigned __int64)g_ag_cyc_hi << 32 | g_ag_cyc_lo,
                     g_fix, routes_fresh(), g_c3[C3_FILL_TRY], g_c3[C3_FILL_OK], g_c3[C3_FREE], g_c3[C3_FREE_GONE],
                     (int)(g_still + 0.5), g_c3[C3_TAKE_SKIP], g_inbox, g_c3[C3_STRIPS], g_c3[C3_STRIP_QUOTA],
                     g_c3[C3_STRIP_TRY], g_c3[C3_STRIP_OK], g_c3[C3_STRIP_NOROUTE]);
            }
            if (g_time) {
                sc3cartrips_stats(stats, 16);
                logf("TIME> calls=%lu cycles=%I64u", stats[7], (unsigned __int64)stats[9] << 32 | stats[8]);
            }
#undef D
            prev = cur; q0 = q1; tsc0 = tsc1; dr0 = dr;
        }
        if (++k % 6 == 0) log_callers();
    }
    return 0;
}

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        char path[MAX_PATH];
        g_self = (HMODULE)inst;
        DisableThreadLibraryCalls(inst);
        InitializeCriticalSection(&g_lock);
        InitializeCriticalSection(&g_dlock);
        QueryPerformanceFrequency(&g_freq);
        QueryPerformanceCounter(&g_t0);
        ini_read();
        if (!GetEnvironmentVariableA("SC3CARTRIPS_LOG", path, sizeof(path))) self_path(path, sizeof(path), "sc3cartrips.log");
        g_log = CreateFileA(path, GENERIC_WRITE, FILE_SHARE_READ, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        logf("### sc3cartrips loaded: mode=%s verify=%d time_route=%d dump=%d choice=%d solve=%d log_s=%d rect=%s", g_mode ? "capture" : "off",
             g_verify, g_time, g_dump, g_choice, g_solve, g_log_s, g_rect_ovr ? "ini" : "sim rect");
        if (g_mode) {
            int i;
            g_tls = TlsAlloc();
            g_ring = (RSlot *)VirtualAlloc(NULL, sizeof(RSlot) * RN, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
            g_queue = (TripRec *)VirtualAlloc(NULL, sizeof(TripRec) * QN, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
            if (g_dump) g_dbuf = (BYTE *)VirtualAlloc(NULL, DCAP, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
            if (g_tls == TLS_OUT_OF_INDEXES || !g_ring || !g_queue || (g_dump && !g_dbuf)) {
                logf("### allocation failed - not armed");
                return TRUE;
            }
            for (i = 0; i < RN; i++) g_ring[i].seq = i;
            CreateThread(NULL, 0, logger, NULL, 0, NULL);
        }
    }
    return TRUE;
}
