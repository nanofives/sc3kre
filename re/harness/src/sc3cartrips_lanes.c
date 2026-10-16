/* sc3cartrips_lanes.c - M2 of re/analysis/CAR_TRIPS.md: the corridor lane-route solver, in game (game thread).
 * #included by sc3cartrips.c. The offline twin is re/tools/ctm_lanes.py (same rules, same tie-break order); the match
 * test compares both on the graphs this file dumps.
 *
 * Lane graph of a cell, read the way STRTSIM's car crossing FUN_1001c750 reads it [CONFIRMED @ STRTSIM
 * 0x1001c7c2..0x1001c84b]: occupant = DAT_100331e0[class]->vt+0x7c(x, z, &occ); road predicate DAT_10033108[class](occ)
 * (class 0: 0x1001ac90, occupant flags & 0x8000 or & 0x10000); occ->QI(0x41658d28, &piece); piece->vt+0x54() ->
 * holder; graph = [[holder + 4] + 0x28]; both Released. Map bounds DAT_10033204 / DAT_10033114 (unsigned compare).
 * Graph layout (link-up FUN_100201d8): +4 / +8 node vector (0x1c each: +0 class, +4 x, +8 y, +0xc z, +0x10 / +0x14
 * edge vector), edge 0x38: +4 target node (0 for an exit), +0x16 heading code (an exit's code); +0x10 + b * 0xc the
 * 16 position buckets, b = bz + bx * 4. Arrival node: FUN_10020108 [CONFIRMED @ STRTSIM 0x10020108].
 * Search: ctm_lanes.solve (docstring) - state (cell, node, j), corridor = Chebyshev `width` around route cells inside
 * the trip's rect, progress by proximity, skip cost, Dijkstra with (cost, push order) priority.
 */

/* ------------------------------------------------------------ graph access */

static BYTE *g_strt_base;
typedef char (__fastcall *PFN_OccAt)(void *self, void *edx, int x, int z, void **occ);
typedef char (__cdecl *PFN_Pred)(void *occ);
typedef char (__fastcall *PFN_QI)(void *self, void *edx, DWORD iid, void **out);
typedef BYTE *(__fastcall *PFN_Holder)(void *self, void *edx);
typedef DWORD (__fastcall *PFN_Rel)(void *self, void *edx);

enum { GS_OK = 0, GS_OFFMAP, GS_NOLAYER, GS_NOOCC, GS_NOTROAD, GS_NOQI, GS_NOGRAPH, GS_FAULT, GS_N };
static volatile DWORD g_gs[GS_N];

static BYTE *graph_at(int x, int z, int *status) {
    BYTE *S = g_strt_base, *g = NULL;
    void *obj, *occ = NULL, *piece = NULL;
    *status = GS_FAULT;
    __try {
        if ((DWORD)x > *(DWORD *)(S + 0x33204) || (DWORD)z > *(DWORD *)(S + 0x33114)) { *status = GS_OFFMAP; return NULL; }
        obj = *(void **)(S + 0x331e0);
        if (!obj) { *status = GS_NOLAYER; return NULL; }
        if (!((PFN_OccAt)(*(DWORD **)obj)[0x7c / 4])(obj, NULL, x, z, &occ) || !occ) { *status = GS_NOOCC; return NULL; }
        if (!(*(PFN_Pred *)(S + 0x33108))(occ)) {
            ((PFN_Rel)(*(DWORD **)occ)[2])(occ, NULL);
            *status = GS_NOTROAD; return NULL;
        }
        if (!((PFN_QI)(*(DWORD **)occ)[0])(occ, NULL, 0x41658d28, &piece) || !piece) {
            ((PFN_Rel)(*(DWORD **)occ)[2])(occ, NULL);
            *status = GS_NOQI; return NULL;
        }
        {   BYTE *holder = ((PFN_Holder)(*(DWORD **)piece)[0x54 / 4])(piece, NULL);
            BYTE *attr = holder ? *(BYTE **)(holder + 4) : NULL;
            g = attr ? *(BYTE **)(attr + 0x28) : NULL;
        }
        ((PFN_Rel)(*(DWORD **)piece)[2])(piece, NULL);
        ((PFN_Rel)(*(DWORD **)occ)[2])(occ, NULL);
        *status = g ? GS_OK : GS_NOGRAPH;
    } __except (EXCEPTION_EXECUTE_HANDLER) { *status = GS_FAULT; return NULL; }
    return g;
}

#define GN(g) ((int)((*(BYTE **)((g) + 8) - *(BYTE **)((g) + 4)) / 0x1c))
#define GNODE(g, i) (*(BYTE **)((g) + 4) + (i) * 0x1c)
#define NCLS(n) (*(signed char *)(n))
#define NX(n) (*(int *)((n) + 4))
#define NZ(n) (*(int *)((n) + 0xc))
#define NEB(n) (*(BYTE **)((n) + 0x10))
#define NEN(n) ((int)((*(BYTE **)((n) + 0x14) - NEB(n)) / 0x38))

static int node_index(BYTE *g, BYTE *node) { return (int)((node - *(BYTE **)(g + 4)) / 0x1c); }

/* FUN_10020108: arrival node at (rx, rz) relative to the cell, of class cls; -1 none */
static int g_lookup(BYTE *g, int rx, int rz, int cls) {
    DWORD bx = (DWORD)(rx + 0x10) / 0x48, bz = (DWORD)(rz + 0x10) / 0x48;
    BYTE **b, **e;
    int n, i, best = -1, bd = 10000000;
    if (bx >= 4 || bz >= 4) return -1;
    b = *(BYTE ***)(g + 0x10 + (bz + bx * 4) * 0xc);
    e = *(BYTE ***)(g + 0x14 + (bz + bx * 4) * 0xc);
    n = (int)(e - b);
    if (n == 1) return NCLS(b[0]) == cls ? node_index(g, b[0]) : -1;
    for (i = 0; i < n; i++) {
        BYTE *nd = b[i];
        int d;
        if (NCLS(nd) != cls) continue;
        d = (rz - NZ(nd)) * (rz - NZ(nd)) + (rx - NX(nd)) * (rx - NX(nd));
        if (d < bd) { bd = d; best = i; }
    }
    return best >= 0 ? node_index(g, b[best]) : -1;
}

static int g_has_internal(BYTE *g, int i) {
    BYTE *n = GNODE(g, i), *e = NEB(n);
    int k, m = NEN(n);
    for (k = 0; k < m; k++) if (*(BYTE **)(e + k * 0x38 + 4)) return 1;
    return 0;
}

/* ------------------------------------------------------------ dumps (graphs once per pointer, cells once) */

typedef struct { CRITICAL_SECTION cs; BYTE *buf; int len, cap; HANDLE f; volatile DWORD drop; } Out;
static Out g_og, g_or;                           /* cartrips_graphs.bin, cartrips_routes.bin */
static BYTE *g_cellseen;                         /* 1024 x 1024 bits */
static DWORD g_gseen[8192];                      /* graph pointers dumped (open addressing) */

static void out_put(Out *o, const void *p, int n) {
    if (!o->buf) return;
    EnterCriticalSection(&o->cs);
    if (o->len + n <= o->cap) { memcpy(o->buf + o->len, p, n); o->len += n; } else o->drop++;
    LeaveCriticalSection(&o->cs);
}
static void out_flush(Out *o) {
    DWORD w;
    if (!o->buf || o->f == INVALID_HANDLE_VALUE || !o->len) return;
    EnterCriticalSection(&o->cs);
    WriteFile(o->f, o->buf, (DWORD)o->len, &w, NULL);
    o->len = 0;
    LeaveCriticalSection(&o->cs);
}

static void dump_graph(BYTE *g) {
    DWORD h = ((DWORD)g >> 4) * 2654435761u, i;
    BYTE tmp[16384];
    int o = 0, n, k, m;
    for (i = 0; i < 8192; i++) {
        DWORD *s = &g_gseen[(h + i) & 8191];
        if (*s == (DWORD)g) return;
        if (!*s) { *s = (DWORD)g; break; }
    }
    if (i == 8192) return;
    n = GN(g);
    tmp[o++] = 1;
    *(DWORD *)(tmp + o) = (DWORD)g; o += 4;
    *(WORD *)(tmp + o) = (WORD)n; o += 2;
    for (k = 0; k < n && o < (int)sizeof(tmp) - 64; k++) {
        BYTE *nd = GNODE(g, k), *e = NEB(nd);
        int q;
        m = NEN(nd);
        tmp[o++] = (BYTE)NCLS(nd);
        *(int *)(tmp + o) = NX(nd); o += 4;
        *(int *)(tmp + o) = NZ(nd); o += 4;
        tmp[o++] = (BYTE)m;
        for (q = 0; q < m && o < (int)sizeof(tmp) - 8; q++) {
            BYTE *ed = e + q * 0x38, *t = *(BYTE **)(ed + 4);
            *(short *)(tmp + o) = (short)(t ? node_index(g, t) : -1); o += 2;
            tmp[o++] = ed[0x16];
        }
    }
    out_put(&g_og, tmp, o);
}

static void dump_cell(int x, int z, int status, BYTE *g) {
    BYTE tmp[10];
    if (x < 0 || z < 0 || x >= 1024 || z >= 1024) return;
    if (g_cellseen[(x * 1024 + z) >> 3] & (1 << ((x * 1024 + z) & 7))) return;
    g_cellseen[(x * 1024 + z) >> 3] |= (BYTE)(1 << ((x * 1024 + z) & 7));
    tmp[0] = 2;
    *(short *)(tmp + 1) = (short)x; *(short *)(tmp + 3) = (short)z;
    tmp[5] = (BYTE)status;
    *(DWORD *)(tmp + 6) = (DWORD)g;
    out_put(&g_og, tmp, 10);
    if (g) dump_graph(g);
}

/* ------------------------------------------------------------ the search */

#define MAXR 256                                 /* route cells (MAXSTORE bounds it) */
#define MAXC 4096                                /* corridor cells */
#define MAXS 65536                               /* states */
#define HS 131072                                /* state hash */
#define LIMIT 200000
#define LIMIT_FIX 40000                          /* scroll_fill (wider capture): no single solve may stall a frame (R2: 260 ms) */
#define SKIPC 3
#define OFFC 1
#define BACK 2

typedef struct { short x, z; BYTE *g; int status; WORD m0, mn; BYTE route; } Cell;    /* M(n) = mlist[m0 .. m0+mn) */
typedef struct { int cell, node, j; DWORD cost; int prev; } State;
typedef struct { DWORD cost, seq; int s; } HeapE;

static Cell g_c[MAXC];
static int g_nc;
static WORD g_ml[MAXC * 9];
static int g_chash[8192];                        /* cell (x, z) -> index + 1 */
static State g_s[MAXS];
static int g_ns;
static int g_shash[HS];                          /* state -> index + 1 */
static HeapE g_heap[MAXS * 4];
static int g_nh;

static int cell_find(int x, int z) {
    DWORD h = ((DWORD)(x * 4099 + z) * 2654435761u) >> 19, i;
    for (i = 0; i < 8192; i++) {
        int v = g_chash[(h + i) & 8191];
        if (!v) return -1;
        if (g_c[v - 1].x == x && g_c[v - 1].z == z) return v - 1;
    }
    return -1;
}
static int cell_add(int x, int z) {
    DWORD h = ((DWORD)(x * 4099 + z) * 2654435761u) >> 19, i;
    for (i = 0; i < 8192; i++) {
        int *v = &g_chash[(h + i) & 8191];
        if (!*v) {
            if (g_nc >= MAXC) return -1;
            g_c[g_nc].x = (short)x; g_c[g_nc].z = (short)z; g_c[g_nc].g = NULL; g_c[g_nc].status = -1;
            g_c[g_nc].mn = 0; g_c[g_nc].route = 0;
            *v = ++g_nc;
            return g_nc - 1;
        }
        if (g_c[*v - 1].x == x && g_c[*v - 1].z == z) return *v - 1;
    }
    return -1;
}
static BYTE *cell_graph(int ci) {
    Cell *c = &g_c[ci];
    if (c->status < 0) {
        c->g = graph_at(c->x, c->z, &c->status);
        g_gs[c->status]++;
        if (g_dump) dump_cell(c->x, c->z, c->status, c->g);
    }
    return c->g;
}

static int st_get(int cell, int node, int j, int make) {
    DWORD h = (((DWORD)cell * 73856093u) ^ ((DWORD)node * 19349663u) ^ ((DWORD)j * 83492791u)) & (HS - 1), i;
    for (i = 0; i < HS; i++) {
        int *v = &g_shash[(h + i) & (HS - 1)];
        if (!*v) {
            if (!make || g_ns >= MAXS) return -1;
            g_s[g_ns].cell = cell; g_s[g_ns].node = node; g_s[g_ns].j = j; g_s[g_ns].cost = 0xffffffff; g_s[g_ns].prev = -1;
            *v = ++g_ns;
            return g_ns - 1;
        }
        if (g_s[*v - 1].cell == cell && g_s[*v - 1].node == node && g_s[*v - 1].j == j) return *v - 1;
    }
    return -1;
}

static int heap_less(HeapE *a, HeapE *b) { return a->cost < b->cost || (a->cost == b->cost && a->seq < b->seq); }
static void heap_push(DWORD cost, DWORD seq, int s) {
    int i = g_nh++;
    HeapE e; e.cost = cost; e.seq = seq; e.s = s;
    while (i > 0) {
        int p = (i - 1) / 2;
        if (!heap_less(&e, &g_heap[p])) break;
        g_heap[i] = g_heap[p]; i = p;
    }
    g_heap[i] = e;
}
static HeapE heap_pop(void) {
    HeapE top = g_heap[0], last = g_heap[--g_nh];
    int i = 0;
    for (;;) {
        int l = 2 * i + 1, r = l + 1, m = i;
        HeapE *pm = &last;
        if (l < g_nh && heap_less(&g_heap[l], pm)) { m = l; pm = &g_heap[l]; }
        if (r < g_nh && heap_less(&g_heap[r], pm)) { m = r; pm = &g_heap[r]; }
        if (m == i) break;
        g_heap[i] = g_heap[m]; i = m;
    }
    if (g_nh) g_heap[i] = last;
    return top;
}

enum { SR_OK = 0, SR_START_NO_GRAPH, SR_START_NO_NODE, SR_NO_PATH, SR_LIMIT, SR_TOO_BIG };
typedef struct { int ok, reason, jmax, skipped, offroute, npath; DWORD cost, expanded; } SolveRes;
static short g_path[MAXS][2];
static BYTE g_pathn[MAXS];

static const int STEPX[8] = { -1, -1, 0, 1, 1, 1, 0, -1 }, STEPZ[8] = { 0, -1, -1, -1, 0, 1, 1, 1 };

static void solve(const short (*cells)[2], int ncell, const short *rect, int width, SolveRes *R) {
    int k = ncell - 1, i, dx, dz, free = width >= 1 ? 2 : 1, goal = -1, c0, n0;
    DWORD seq = 0;
    memset(R, 0, sizeof(*R));
    g_nc = 0; g_ns = 0; g_nh = 0;
    memset(g_chash, 0, sizeof(g_chash));
    memset(g_shash, 0, sizeof(g_shash));
    /* corridor: M(n) lists, ascending route index, as ctm_lanes builds them */
    {
        static WORD tmp_m[MAXC][32];
        static BYTE tmp_n[MAXC];
        int used = 0;
        for (i = 0; i <= k; i++)
            for (dx = -width; dx <= width; dx++)
                for (dz = -width; dz <= width; dz++) {
                    int x = cells[i][0] + dx, z = cells[i][1] + dz, ci;
                    if (x < rect[0] || x > rect[2] || z < rect[1] || z > rect[3]) continue;
                    ci = cell_add(x, z);
                    if (ci < 0) { R->reason = SR_TOO_BIG; return; }
                    if (ci >= used) { tmp_n[ci] = 0; used = ci + 1; }
                    if ((!tmp_n[ci] || tmp_m[ci][tmp_n[ci] - 1] != i) && tmp_n[ci] < 32) tmp_m[ci][tmp_n[ci]++] = (WORD)i;
                }
        for (i = 0, used = 0; i < g_nc; i++) {
            int q;
            g_c[i].m0 = (WORD)used; g_c[i].mn = tmp_n[i];
            for (q = 0; q < tmp_n[i]; q++) g_ml[used++] = tmp_m[i][q];
        }
        for (i = 0; i <= k; i++) { int ci = cell_find(cells[i][0], cells[i][1]); if (ci >= 0) g_c[ci].route = 1; }
    }
    /* start cells: r0, then (w >= 1) the corridor cells around r0 in dx, dz order, cost OFFC each (ctm_lanes WIDE_START) */
    c0 = cell_find(cells[0][0], cells[0][1]);
    n0 = 0;
    for (dx = -1 - width; dx <= width; dx++)
        for (dz = (dx < -width ? 0 : -width); dz <= (dx < -width ? 0 : width); dz++) {
            int ci, s;
            DWORD d0;
            BYTE *gs;
            if (dx < -width) ci = c0;                                     /* first pass: r0 itself */
            else {
                if (!width || (!dx && !dz)) continue;
                ci = cell_find(cells[0][0] + dx, cells[0][1] + dz);
                if (ci < 0 || !g_c[ci].mn) continue;
            }
            if (ci < 0 || !(gs = cell_graph(ci))) continue;
            d0 = ci == c0 ? 0 : OFFC;
            for (i = 0; i < GN(gs); i++) {
                if (NCLS(GNODE(gs, i)) != 0) continue;
                s = st_get(ci, i, 0, 1);
                if (s < 0) { R->reason = SR_TOO_BIG; return; }
                if (d0 < g_s[s].cost) { g_s[s].cost = d0; heap_push(d0, seq++, s); n0++; }
            }
        }
    if (!n0) { R->reason = (c0 < 0 || !g_c[c0].g) ? SR_START_NO_GRAPH : SR_START_NO_NODE; return; }
    while (g_nh) {
        HeapE e = heap_pop();
        State *s = &g_s[e.s];
        BYTE *g, *nd, *eb;
        int ne, q, cell = s->cell, n = s->node, j = s->j;
        if (s->cost < e.cost) continue;
        if (++R->expanded > (DWORD)(g_fix ? LIMIT_FIX : LIMIT)) { R->reason = SR_LIMIT; break; }
        if (j > R->jmax) R->jmax = j;
        if (j == k) { goal = e.s; break; }
        g = g_c[cell].g;
        nd = GNODE(g, n); eb = NEB(nd); ne = NEN(nd);
        for (q = 0; q < ne; q++) {
            BYTE *ed = eb + q * 0x38, *t = *(BYTE **)(ed + 4), *g2;
            int ns, nj, nc, an, x, z, st, mlo, mn, a;
            DWORD nd2;
            if (t) {
                ns = st_get(cell, node_index(g, t), j, 1);
                nd2 = e.cost + 1;
            } else {
                st = ed[0x16] >> 2;
                if (st & 1) continue;                    /* vehicle exits are side * 8: steps 0, 2, 4, 6 */
                x = g_c[cell].x + STEPX[st]; z = g_c[cell].z + STEPZ[st];
                nc = cell_find(x, z);
                if (nc < 0 || !g_c[nc].mn) continue;       /* off the corridor / out of the rect */
                mlo = g_c[nc].m0; mn = g_c[nc].mn;
                if ((int)g_ml[mlo + mn - 1] < j - BACK) continue;
                nj = -1;
                for (a = 0; a < mn; a++) if (g_ml[mlo + a] > j && g_ml[mlo + a] <= j + free) nj = g_ml[mlo + a];
                if (nj < 0) {
                    if (width == 0) {
                        if (!g_c[nc].route || (int)g_ml[mlo + mn - 1] > j) continue;
                        nj = j;
                    } else {
                        nj = j;
                        for (a = 0; a < mn; a++) if (g_ml[mlo + a] > j) { nj = g_ml[mlo + a]; break; }
                    }
                }
                g2 = cell_graph(nc);
                if (!g2) continue;
                an = g_lookup(g2, NX(nd) - 256 * STEPX[st], NZ(nd) - 256 * STEPZ[st], 0);
                if (an < 0 || !g_has_internal(g2, an)) continue;
                ns = st_get(nc, an, nj, 1);
                nd2 = e.cost + 1 + (g_c[nc].route ? 0 : OFFC) + SKIPC * (nj - j - free > 0 ? nj - j - free : 0);
            }
            if (ns < 0) { R->reason = SR_TOO_BIG; goto done; }
            if (nd2 < g_s[ns].cost) {
                g_s[ns].cost = nd2;
                g_s[ns].prev = e.s;
                if (g_nh >= MAXS * 4) { R->reason = SR_TOO_BIG; goto done; }
                heap_push(nd2, seq++, ns);
            }
        }
    }
done:
    if (goal < 0) { if (R->reason == SR_OK) R->reason = SR_NO_PATH; return; }
    R->ok = 1; R->reason = SR_OK; R->jmax = k; R->cost = g_s[goal].cost;
    {   /* walk back: path, skipped route cells, cells off the route */
        static int chain[MAXS];
        int nch = 0, s = goal, lastj = 0, lastc = -1;
        while (s >= 0 && nch < MAXS) { chain[nch++] = s; s = g_s[s].prev; }
        for (i = nch - 1; i >= 0; i--) {
            State *p = &g_s[chain[i]];
            if (R->npath < MAXS) {
                g_path[R->npath][0] = g_c[p->cell].x; g_path[R->npath][1] = g_c[p->cell].z;
                g_pathn[R->npath] = (BYTE)p->node; R->npath++;
            }
            if (p->j - lastj - free > 0) R->skipped += p->j - lastj - free;
            lastj = p->j;
            if (p->cell != lastc) { if (!g_c[p->cell].route) R->offroute++; lastc = p->cell; }
        }
    }
}

/* ------------------------------------------------------------ per drained trip */

static void route_push(DWORD seq, int npath, int cut);
static volatile LONG g_mode_now;

static volatile DWORD g_m2[16];  /* routes, w0 ok, w1 ok, w1 full, w1 cov90, w1 fail no-path, w1 start fails, w1 limit/too big,
                                    routes skipped by the tick budget, solve us total (w1), max us, routes_1cell, trips */

static void solve_trip(TripRec *t, LONGLONG *budget_end) {
    short cells[MAXR][2];
    int nn = t->nstore, i, nc = 0, ridx = 0;
    g_m2[12]++;
    for (i = nn - 1; i >= -1; i--) {                  /* travel order = reversed pop order; i = -1 flushes */
        Node *n = i >= 0 ? &t->nodes[i] : NULL;
        int ok = n && (n->type == 1 || n->type == 2 || n->type == 3) && n->x0 == n->x1 && n->z0 == n->z1 &&
                 n->x0 >= t->rect[0] && n->x0 <= t->rect[2] && n->z0 >= t->rect[1] && n->z0 <= t->rect[3];
        if (ok) {
            if (!nc || cells[nc - 1][0] != n->x0 || cells[nc - 1][1] != n->z0) {
                if (nc < MAXR) { cells[nc][0] = n->x0; cells[nc][1] = n->z0; nc++; }
            }
            continue;
        }
        if (!nc) continue;
        if (nc < 2) { g_m2[11]++; nc = 0; continue; }
        {
            SolveRes r1, r0;
            LARGE_INTEGER a, b;
            DWORD us;
            BYTE hdr[24];
            int o = 0, q;
            QueryPerformanceCounter(&a);
            (void)budget_end;                    /* the budget is checked per trip by the caller (carry-over) */
            g_m2[0]++;
            solve(cells, nc, t->rect, 1, &r1);
            QueryPerformanceCounter(&b);
            us = (DWORD)((b.QuadPart - a.QuadPart) * 1000000 / g_freq.QuadPart);
            g_m2[9] += us;
            if (us > g_m2[10]) g_m2[10] = us;
            if (r1.ok) {
                g_m2[2]++;
                if (!r1.skipped) g_m2[3]++;
                if (r1.skipped * 10 <= nc) g_m2[4]++;
            } else if (r1.reason == SR_NO_PATH) g_m2[5]++;
            else if (r1.reason == SR_START_NO_GRAPH || r1.reason == SR_START_NO_NODE) g_m2[6]++;
            else g_m2[7]++;
            if (g_dump) {   /* the w1 path first: solve(w0) reuses g_path */
                BYTE rec[32];
                *(DWORD *)rec = t->seq; *(WORD *)(rec + 4) = (WORD)ridx; *(WORD *)(rec + 6) = (WORD)nc;
                memcpy(rec + 8, t->rect, 8);
                *(DWORD *)(rec + 16) = us;
                out_put(&g_or, rec, 20);
                out_put(&g_or, cells, nc * 4);
                hdr[0] = (BYTE)r1.ok; hdr[1] = (BYTE)r1.reason; *(WORD *)(hdr + 2) = (WORD)r1.jmax;
                *(DWORD *)(hdr + 4) = r1.cost; *(WORD *)(hdr + 8) = (WORD)r1.skipped; *(WORD *)(hdr + 10) = (WORD)r1.offroute;
                *(DWORD *)(hdr + 12) = r1.expanded; *(WORD *)(hdr + 16) = (WORD)r1.npath;
                out_put(&g_or, hdr, 18);
                for (q = 0; q < r1.npath; q++) {
                    BYTE pe[5];
                    *(short *)pe = g_path[q][0]; *(short *)(pe + 2) = g_path[q][1]; pe[4] = g_pathn[q];
                    out_put(&g_or, pe, 5);
                }
            }
            if (r1.ok && g_mode_now >= 2) {                                   /* M3: a car may drive it */
                /* the route was cut by the capture rect when the trip goes on along a road cell outside it (or past the
                   stored window), rather than ending at its destination or changing to transit */
                int cut = n ? ((n->type == 1 || n->type == 2 || n->type == 3) &&
                               (n->x0 < t->rect[0] || n->x0 > t->rect[2] || n->z0 < t->rect[1] || n->z0 > t->rect[3]))
                            : t->first > 0;
                route_push(t->seq, r1.npath, cut);
            }
            if (!g_dump) { nc = 0; ridx++; continue; }                     /* w0 is a measurement */
            solve(cells, nc, t->rect, 0, &r0);
            if (r0.ok) g_m2[1]++;
            if (g_dump) {
                hdr[0] = (BYTE)r0.ok; hdr[1] = (BYTE)r0.reason; *(WORD *)(hdr + 2) = (WORD)r0.jmax;
                *(DWORD *)(hdr + 4) = r0.cost; *(WORD *)(hdr + 8) = (WORD)r0.skipped; *(WORD *)(hdr + 10) = (WORD)r0.offroute;
                *(DWORD *)(hdr + 12) = r0.expanded; *(WORD *)(hdr + 16) = 0;
                out_put(&g_or, hdr, 18);
            }
            (void)o;
        }
        nc = 0; ridx++;
    }
}
