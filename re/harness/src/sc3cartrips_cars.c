/* sc3cartrips_cars.c - M3 of re/analysis/CAR_TRIPS.md: route cars (game thread). #included by sc3cartrips.c after
 * sc3cartrips_lanes.c. Owner decisions 2026-10-16: D1 replace (filler behind ini mode), D2 pause = FREEZE, D3 stock
 * count formula, D4 road part of mixed trips, D5 all building trips (no zone probes), D6 corridor 1 cell.
 *
 * Decoded for this (STRTSIM unless named) [CONFIRMED @ the addresses]:
 *  - FUN_1001f112 PutVehiclesOnRoadTile makes a car: FUN_1001ed36(producer, (z>>5) * DAT_10033280 + (x>>5), &inst)
 *    (roster pick, thiscall, ret 8; x, z from occ->vt+0xbc(&x, &z)), new(0x15c) (MSVCRT ??2), ctor FUN_10019750,
 *    vt+4 AddRef, vt+0x13c Init({0xc25c2bf7, 0x025c2c45, inst}), producer +0xc += 1, vt+0x140 SetProducer,
 *    PlaceOnTransitTile = (car+0x18)->vt+0x10(occ) (FUN_1001bc70), vt+8 Release.
 *  - FUN_1001bc70 takes the car's first path from car vt+0x154 = FUN_1001c510 SelectPath(occ): QI 0x41658d28 -> piece,
 *    holder = piece->vt+0x54(), occ->vt+0xbc(&x, &z), rot = occ->vt+0xc0() - [[holder+4] + r*4 + 0x14] with r from
 *    occ->vt+0xa0()->vt+0x1c(&r), a random node + internal edge (FUN_1002034d), path = FUN_10018630(holder, x, rot, z,
 *    edge) (stdcall, ret 0x14), piece Released. A route car gets the same with the edge of its solved lane path.
 *  - car vt+0x158 = FUN_1001c290 SelectAnEdge(node, x, z), thiscall, ret 0xc: every lane decision (SelectNextPath and
 *    the crossing FUN_1001c750 at 0x1001c878, whose caller reads [edge+4] so it must never get NULL).
 *  - producer vtable 0x1002d1d0: +0x10 VehicleDisappears FUN_1001f610 (arg car+0x18, ret 4), +0x14 NeedVehicleDisappear
 *    FUN_1001eec4 (car+0x18, &counter; ret 8).
 *  - random cars: producer tick FUN_1001f44a (call at 0x10012e8a, ret 4) and PutVehiclesInRect FUN_1001f040 (calls at
 *    0x100154a0 and 0x10015573 in FUN_10015415, thiscall, ret 4). Replace mode skips both.
 */

enum { MODE_OFF = 0, MODE_CAPTURE = 1, MODE_REPLACE = 2, MODE_FILLER = 3 };

#define MAXLP 2048
#define RQN 256                                  /* solved routes, newest kept: a history (scroll_fill reuses them) */
#define RQN_OLD 64                               /* scroll_fill off: only the 64 newest, each used once (as before) */
#define ROUTE_USES 8                             /* scroll_fill: cars per route at most (strips and top-up) */
#define ROUTE_AGE_S 120.0                        /* scroll_fill: routes older than this are not reused */
#define STRIP_PER_TICK 24                        /* scroll_fill: strip placements per tick at most */
#define MOVE_TAIL_MS 8000                        /* scroll_fill: the top-up keeps going this long after the camera stops */
#define MAXCARS 256

typedef struct { short x, z; BYTE *node, *g; } LStep;
typedef struct { DWORD seq; int n; LARGE_INTEGER t; int used, cut; short bx0, bz0, bx1, bz1; LStep s[MAXLP]; } Route;
typedef struct {
    BYTE *car;                                   /* 0 = free */
    int n, idx, ended, lost, followed, crossings, spawned_tick, placing;
    int cut, roam;                               /* path cut by the capture rect; roaming past its end (scroll_fill) */
    DWORD seq;
    LStep s[MAXLP];
} RCar;

static Route *g_rq;                              /* ring, newest at g_rq_head - 1 */
static int g_rq_head, g_rq_len;
static RCar *g_cars;
static int g_ncars;
static BYTE *g_spawn_car, *g_spawn_edge;

/* counters for CARS> */
static volatile DWORD g_c3[48];
enum { C3_ROUTES_QUEUED, C3_ROUTES_DROPPED_OLD, C3_SPAWN_TRY, C3_SPAWN_OK, C3_SPAWN_INITFAIL, C3_SPAWN_PLACEFAIL,
       C3_SPAWN_NOOCC, C3_SPAWN_NOEDGE, C3_SPAWN_OUTRECT, C3_END_ARRIVED, C3_END_LOST, C3_END_OTHER, C3_END_OTHER_EDGE,
       C3_DECISIONS, C3_FOLLOWED, C3_CROSS_FOLLOWED, C3_LOST_EVENTS, C3_NEED_CALLS_ROUTE, C3_NEED_TRUE_ROUTE,
       C3_ZONE_EXCLUDED, C3_PAUSED_TICKS, C3_STEPS_COVERED, C3_STEPS_TOTAL, C3_SPAWN_PAUSED, C3_RQ_STALE,
       C3_TRIPS_CARRIED, C3_TRIPS_DROPPED, C3_SPAWN_FAULT, C3_DECISIONS_AFTER, C3_SPAWN_RETRY_OK,
       C3_FILL_TRY, C3_FILL_OK, C3_FREE, C3_FREE_GONE, C3_TAKE_SKIP,
       C3_STRIPS, C3_STRIP_QUOTA, C3_STRIP_TRY, C3_STRIP_OK, C3_STRIP_NOROUTE };
static double g_still;                           /* route cars with the camera still (scroll_fill's goal), game thread */
static double g_still_area = 1.0;                /* sim rect area (cells) while g_still was measured */

/* scroll_fill strips: ground the sim rect has just taken in, each with a car quota at the still-camera density */
#define NSTRIP 16
typedef struct { int x0, z0, x1, z1, quota; } Strip;
static Strip g_strip[NSTRIP];
static int g_nstrip;

static void strips_add(int ox0, int oz0, int ox1, int oz1, int nx0, int nz0, int nx1, int nz1) {
    int r[4][4], n = 0, k;
    double dens;
    if (!g_fix || g_still < 1.0) return;
    if (nx1 < ox0 || nx0 > ox1 || nz1 < oz0 || nz0 > oz1) { r[n][0] = nx0; r[n][1] = nz0; r[n][2] = nx1; r[n][3] = nz1; n++; }
    else {                                          /* new minus old, as STRTSIM FUN_10014d85 cuts it */
        int cx0 = nx0, cx1 = nx1;
        if (nx0 < ox0) { r[n][0] = nx0; r[n][1] = nz0; r[n][2] = ox0 - 1; r[n][3] = nz1; n++; cx0 = ox0; }
        if (nx1 > ox1) { r[n][0] = ox1 + 1; r[n][1] = nz0; r[n][2] = nx1; r[n][3] = nz1; n++; cx1 = ox1; }
        if (nz0 < oz0) { r[n][0] = cx0; r[n][1] = nz0; r[n][2] = cx1; r[n][3] = oz0 - 1; n++; }
        if (nz1 > oz1) { r[n][0] = cx0; r[n][1] = oz1 + 1; r[n][2] = cx1; r[n][3] = nz1; n++; }
    }
    dens = g_still / g_still_area;
    for (k = 0; k < n; k++) {
        int area = (r[k][2] - r[k][0] + 1) * (r[k][3] - r[k][1] + 1), q;
        if (area <= 0) continue;
        q = (int)(dens * area + 0.5);
        if (q < 1) continue;
        if (q > 40) q = 40;
        if (g_nstrip == NSTRIP) { memmove(&g_strip[0], &g_strip[1], sizeof(Strip) * (NSTRIP - 1)); g_nstrip--; }
        g_strip[g_nstrip].x0 = r[k][0]; g_strip[g_nstrip].z0 = r[k][1]; g_strip[g_nstrip].x1 = r[k][2]; g_strip[g_nstrip].z1 = r[k][3];
        g_strip[g_nstrip].quota = q;
        g_nstrip++;
        g_c3[C3_STRIPS]++; g_c3[C3_STRIP_QUOTA] += q;
    }
}
static volatile LONG g_inbox;                    /* route cars whose cell is inside the view box (sampled every 250 ms) */
static volatile DWORD g_c3_cyc_lo, g_c3_cyc_hi;  /* rdtsc spent in this file's hooks + spawning (game thread) */

static void cyc_add(unsigned __int64 c) {
    unsigned __int64 v = ((unsigned __int64)g_c3_cyc_hi << 32 | g_c3_cyc_lo) + c;
    g_c3_cyc_lo = (DWORD)v; g_c3_cyc_hi = (DWORD)(v >> 32);
}

static RCar *car_find(BYTE *car) {
    int i;
    if (!g_cars || !car) return NULL;
    for (i = 0; i < MAXCARS; i++) if (g_cars[i].car == car) return &g_cars[i];
    return NULL;
}

/* ------------------------------------------------------------ routes from the solver */

static void route_push(DWORD seq, int npath, int cut) {
    Route *r;
    int q;
    if (!g_rq || npath < 2) return;
    r = &g_rq[g_rq_head];
    g_rq_head = (g_rq_head + 1) % RQN;
    if (g_rq_len < RQN) g_rq_len++; else g_c3[C3_ROUTES_DROPPED_OLD]++;
    r->seq = seq;
    r->used = 0; r->cut = cut;
    r->bx0 = r->bz0 = 0x7fff; r->bx1 = r->bz1 = -1;
    QueryPerformanceCounter(&r->t);
    r->n = npath > MAXLP ? MAXLP : npath;
    for (q = 0; q < r->n; q++) {
        int ci = cell_find(g_path[q][0], g_path[q][1]);
        BYTE *g = ci >= 0 ? g_c[ci].g : NULL;
        r->s[q].x = g_path[q][0]; r->s[q].z = g_path[q][1];
        r->s[q].g = g;
        r->s[q].node = g ? GNODE(g, g_pathn[q]) : NULL;
        if (r->s[q].x < r->bx0) r->bx0 = r->s[q].x;
        if (r->s[q].x > r->bx1) r->bx1 = r->s[q].x;
        if (r->s[q].z < r->bz0) r->bz0 = r->s[q].z;
        if (r->s[q].z > r->bz1) r->bz1 = r->s[q].z;
    }
    g_c3[C3_ROUTES_QUEUED]++;
}

static int routes_fresh(void) {                  /* unused routes (logger: a racy statistic) */
    int k, n = 0;
    if (!g_rq) return 0;
    for (k = 0; k < g_rq_len; k++) n += !g_rq[(g_rq_head + RQN - 1 - k) % RQN].used;
    return n;
}

static int box_has(int x, int z) { return x >= g_box[0] && x <= g_box[2] && z >= g_box[1] && z <= g_box[3]; }

static double route_age_s(Route *r) {
    LARGE_INTEGER now;
    QueryPerformanceCounter(&now);
    return (double)(now.QuadPart - r->t.QuadPart) / (double)g_freq.QuadPart;
}

/* first path step inside the producer's rect (the car enters the route there), -1 if none */
static int route_entry(Route *r, BYTE *prod) {
    int px0 = *(int *)(prod + 0x24), pz0 = *(int *)(prod + 0x28), px1 = *(int *)(prod + 0x2c), pz1 = *(int *)(prod + 0x30), s;
    if (r->bx1 < px0 || r->bx0 > px1 || r->bz1 < pz0 || r->bz0 > pz1) return -1;     /* path box misses the rect */
    for (s = 0; s + 1 < r->n; s++)
        if (r->s[s].x >= px0 && r->s[s].x <= px1 && r->s[s].z >= pz0 && r->s[s].z <= pz1) return s;
    return -1;
}

/* the route for the next stock-rate spawn. scroll_fill off: the newest unused route, used once whatever happens (the
   M3 behaviour; spawn_at refuses a start outside the rect). On: the newest unused route of the last 30 s with a step
   inside the rect, entered there; routes with no step inside stay for later. */
static Route *route_take(BYTE *prod, int *entry) {
    int k, lim = g_fix ? g_rq_len : (g_rq_len < RQN_OLD ? g_rq_len : RQN_OLD);
    *entry = 0;
    for (k = 0; k < lim; k++) {
        Route *r = &g_rq[(g_rq_head + RQN - 1 - k) % RQN];
        int e;
        if (r->used) continue;
        if (!g_fix) { r->used = 1; return r; }
        if (route_age_s(r) > 30.0) break;
        e = route_entry(r, prod);
        if (e < 0) { g_c3[C3_TAKE_SKIP]++; continue; }
        r->used = 1; *entry = e;
        return r;
    }
    return NULL;
}

/* scroll_fill strip: a recent route (60 s, at most 3 cars per route) with a step inside the strip and off screen (outside the
   view box): the car enters the route there, mid-path; newest routes first */
static Route *route_strip(Strip *st, int *entry) {
    int k, s;
    for (k = 0; k < g_rq_len; k++) {
        Route *r = &g_rq[(g_rq_head + RQN - 1 - k) % RQN];
        if (r->used >= ROUTE_USES) continue;
        if (route_age_s(r) > ROUTE_AGE_S) break;
        if (r->bx1 < st->x0 || r->bx0 > st->x1 || r->bz1 < st->z0 || r->bz0 > st->z1) continue;   /* misses the strip */
        for (s = 0; s + 1 < r->n; s++) {
            int x = r->s[s].x, z = r->s[s].z;
            if (x >= st->x0 && x <= st->x1 && z >= st->z0 && z <= st->z1 && !box_has(x, z)) {
                r->used++; *entry = s;
                return r;
            }
        }
    }
    return NULL;
}

/* scroll_fill: a recent route (60 s, at most 3 cars per route) whose first step inside the rect is off screen (outside the
   view box, which contains the screen): the car enters there and drives in, nothing appears on screen */
static int g_fill_cur;
static Route *route_fill(BYTE *prod, int *entry) {
    int k;
    for (k = 0; k < g_rq_len; k++) {
        int j = (g_fill_cur + k) % g_rq_len, e;
        Route *r = &g_rq[(g_rq_head + RQN - 1 - j) % RQN];
        if (r->used >= ROUTE_USES || route_age_s(r) > ROUTE_AGE_S) continue;
        e = route_entry(r, prod);
        if (e < 0 || box_has(r->s[e].x, r->s[e].z)) continue;
        g_fill_cur = (j + 1) % g_rq_len;
        r->used++; *entry = e;
        return r;
    }
    return NULL;
}

/* ------------------------------------------------------------ edge choice along a lane path */

static BYTE *edge_toward(LStep *a, LStep *b) {
    BYTE *eb = NEB(a->node);
    int k, ne = NEN(a->node);
    if (a->x == b->x && a->z == b->z) {
        for (k = 0; k < ne; k++) if (*(BYTE **)(eb + k * 0x38 + 4) == b->node) return eb + k * 0x38;
        return NULL;
    }
    for (k = 0; k < ne; k++) {
        BYTE *ed = eb + k * 0x38;
        int st;
        if (*(BYTE **)(ed + 4)) continue;
        st = ed[0x16] >> 2;
        if (st & 1) continue;
        if (a->x + STEPX[st] != b->x || a->z + STEPZ[st] != b->z || !b->g) continue;
        if (g_lookup(b->g, NX(a->node) - 256 * STEPX[st], NZ(a->node) - 256 * STEPZ[st], 0) == node_index(b->g, b->node))
            return ed;
    }
    return NULL;
}

/* ------------------------------------------------------------ hooks (car vtable 0x1002cd20, producer vtable 0x1002d1d0) */

typedef BYTE *(__fastcall *PFN_SelPath)(BYTE *car, void *edx, void *occ);
typedef BYTE *(__fastcall *PFN_SelEdge)(BYTE *car, void *edx, BYTE *node, int x, int z);
typedef char (__fastcall *PFN_Need)(BYTE *prod, void *edx, BYTE *car18, WORD *counter);
typedef void (__fastcall *PFN_Gone)(BYTE *prod, void *edx, BYTE *car18);
typedef BYTE *(__stdcall *PFN_Build)(BYTE *holder, int x, DWORD rot, int z, BYTE *edge);   /* ret 0x14 */
typedef void (__fastcall *PFN_XZ)(void *occ, void *edx, int *x, int *z);
typedef BYTE (__fastcall *PFN_B)(void *occ, void *edx);
typedef void *(__fastcall *PFN_P)(void *occ, void *edx);
typedef void (__fastcall *PFN_R1)(void *o, void *edx, int *out);
static PFN_SelPath g_o_selpath;
static PFN_SelEdge g_o_seledge;
static PFN_Need g_o_need;
static PFN_Gone g_o_gone;
static PFN_Build g_build;

/* SelectPath(occupant) for the car being spawned: FUN_1001c510 with the solved path's edge */
static BYTE *__fastcall my_selpath(BYTE *car, void *edx, void *occ) {
    BYTE *piece = NULL, *holder, *attr, *path = NULL;
    int x = 0, z = 0, r = 0;
    BYTE rot;
    if (car != g_spawn_car || !g_spawn_edge) return g_o_selpath(car, edx, occ);
    __try {
        if (!((PFN_QI)(*(DWORD **)occ)[0])(occ, NULL, 0x41658d28, (void **)&piece) || !piece) return NULL;
        holder = ((PFN_Holder)(*(DWORD **)piece)[0x54 / 4])(piece, NULL);
        ((PFN_XZ)(*(DWORD **)occ)[0xbc / 4])(occ, NULL, &x, &z);
        rot = ((PFN_B)(*(DWORD **)occ)[0xc0 / 4])(occ, NULL);
        {   void *sub = ((PFN_P)(*(DWORD **)occ)[0xa0 / 4])(occ, NULL);
            ((PFN_R1)(*(DWORD **)sub)[0x1c / 4])(sub, NULL, &r);
        }
        attr = *(BYTE **)(holder + 4);
        rot = (BYTE)(rot - attr[(r & 0xff) * 4 + 0x14]);
        path = g_build(holder, x, rot, z, g_spawn_edge);
        ((PFN_Rel)(*(DWORD **)piece)[2])(piece, NULL);
    } __except (EXCEPTION_EXECUTE_HANDLER) { return NULL; }
    return path;
}

static BYTE *__fastcall my_seledge(BYTE *car, void *edx, BYTE *node, int x, int z) {
    RCar *c = car_find(car);
    unsigned __int64 t0 = __rdtsc();
    int i, hi;
    BYTE *e;
    if (!c) return g_o_seledge(car, edx, node, x, z);
    if (c->roam) { cyc_add(__rdtsc() - t0); return g_o_seledge(car, edx, node, x, z); }
    if (c->ended || c->lost) { g_c3[C3_DECISIONS_AFTER]++; cyc_add(__rdtsc() - t0); return g_o_seledge(car, edx, node, x, z); }
    g_c3[C3_DECISIONS]++;
    hi = c->idx + 8 < c->n ? c->idx + 8 : c->n - 1;
    for (i = c->idx; i <= hi; i++)
        if (c->s[i].node == node && c->s[i].x == x && c->s[i].z == z) break;
    if (i > hi) {                                    /* off its lane path */
        c->lost = 1;
        g_c3[C3_LOST_EVENTS]++;
        cyc_add(__rdtsc() - t0);
        return g_o_seledge(car, edx, node, x, z);
    }
    if (c->s[i].x != c->s[c->idx].x || c->s[i].z != c->s[c->idx].z) { c->crossings++; c->followed++; g_c3[C3_CROSS_FOLLOWED]++; }
    c->idx = i;
    if (i == c->n - 1) {                             /* destination / view-edge end: one more edge, then removed */
        if (g_fix && c->cut) {                       /* cut by the capture rect: drive on, removed once off screen */
            c->roam = 1; g_c3[C3_FREE]++;
            cyc_add(__rdtsc() - t0);
            return g_o_seledge(car, edx, node, x, z);
        }
        c->ended = 1;
        cyc_add(__rdtsc() - t0);
        return g_o_seledge(car, edx, node, x, z);
    }
    e = edge_toward(&c->s[i], &c->s[i + 1]);
    if (!e) { c->lost = 1; g_c3[C3_LOST_EVENTS]++; cyc_add(__rdtsc() - t0); return g_o_seledge(car, edx, node, x, z); }
    g_c3[C3_FOLLOWED]++;
    cyc_add(__rdtsc() - t0);
    return e;
}

static char __fastcall my_need(BYTE *prod, void *edx, BYTE *car18, WORD *counter) {
    RCar *c = car18 ? car_find(car18 - 0x18) : NULL;
    if (!c) return g_o_need(prod, edx, car18, counter);
    g_c3[C3_NEED_CALLS_ROUTE]++;
    if (c->ended || c->lost) { g_c3[C3_NEED_TRUE_ROUTE]++; return 1; }
    if (c->roam) {                                   /* never the density despawn; leaves once it is off screen */
        BYTE *car = c->car;
        if (!box_has(*(int *)(car + 0xc) >> 8, *(int *)(car + 0x14) >> 8)) { g_c3[C3_NEED_TRUE_ROUTE]++; return 1; }
        return 0;
    }
    return 0;                                        /* never the density despawn */
}

static void __fastcall my_gone(BYTE *prod, void *edx, BYTE *car18) {
    RCar *c = car18 ? car_find(car18 - 0x18) : NULL;
    if (c) {
        BYTE *car = c->car;
        int cx = *(int *)(car + 0xc) >> 8, cz = *(int *)(car + 0x14) >> 8;
        if (c->roam) g_c3[C3_FREE_GONE]++;
        else if (c->ended) g_c3[C3_END_ARRIVED]++;
        else if (c->lost) g_c3[C3_END_LOST]++;
        else if (c->placing) ;                     /* placement failed: counted at the spawn */
        else {
            g_c3[C3_END_OTHER]++;
            {   LONG a = g_sim_xz0, b = g_sim_xz1;
                int x0 = (short)(a >> 16), z0 = (short)a, x1 = (short)(b >> 16), z1 = (short)b;
                if (cx <= x0 || cx >= x1 || cz <= z0 || cz >= z1) g_c3[C3_END_OTHER_EDGE]++;
            }
        }
        if (!c->placing) { g_c3[C3_STEPS_COVERED] += c->idx + 1; g_c3[C3_STEPS_TOTAL] += c->n; }
        c->car = NULL;
        g_ncars--;
    }
    g_o_gone(prod, edx, car18);
}

/* ------------------------------------------------------------ spawning (game thread, producer tick) */

typedef void *(__cdecl *PFN_New)(size_t);
typedef BYTE *(__fastcall *PFN_Ctor)(BYTE *car, void *edx);
typedef char (__fastcall *PFN_Roster)(BYTE *prod, void *edx, int idx, DWORD *inst);
typedef char (__fastcall *PFN_Init)(BYTE *car, void *edx, DWORD *key);
typedef void (__fastcall *PFN_SetProd)(BYTE *car, void *edx, BYTE *prod);
typedef char (__fastcall *PFN_Place)(BYTE *car18, void *edx, void *occ);
static PFN_New g_new;

static int user_paused_city(void) {
    BYTE *exe = (BYTE *)GetModuleHandleA(NULL), *app, *city;
    __try {
        app = *(BYTE **)(exe + 0xfa86c);
        if (!app) return 0;
        city = *(BYTE **)(app + 0x48);
        if (!city) return 0;
        return *(LONG *)(city + 0x140) > 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) { return 0; }
}

static int spawn_at(BYTE *prod, Route *r, int s0, int *next) {
    BYTE *S = g_strt_base, *car, *edge = NULL;
    void *obj, *occ = NULL;
    int s, x = 0, z = 0, ok = 0;
    *next = -1;
    RCar *c = NULL;
    DWORD key[3], inst = 0;
    g_c3[C3_SPAWN_TRY]++;
    for (s = s0; s + 1 < r->n; s++)
        if (r->s[s].node && r->s[s].x == r->s[s + 1].x && r->s[s].z == r->s[s + 1].z &&
            (edge = edge_toward(&r->s[s], &r->s[s + 1])) != NULL) break;
    if (!edge) { g_c3[C3_SPAWN_NOEDGE]++; return 0; }
    {   int q = s + 1;                               /* a retry starts in a later cell */
        while (q < r->n && r->s[q].x == r->s[s].x && r->s[q].z == r->s[s].z) q++;
        *next = q < r->n - 1 ? q : -1;
    }
    {   int px0 = *(int *)(prod + 0x24), pz0 = *(int *)(prod + 0x28), px1 = *(int *)(prod + 0x2c), pz1 = *(int *)(prod + 0x30);
        if (r->s[s].x < px0 || r->s[s].x > px1 || r->s[s].z < pz0 || r->s[s].z > pz1) { g_c3[C3_SPAWN_OUTRECT]++; return 0; }
    }
    {   int i;
        for (i = 0; i < MAXCARS; i++) if (!g_cars[i].car) { c = &g_cars[i]; break; }
        if (!c) return 0;
    }
    __try {
        obj = *(void **)(S + 0x331e0);
        if (!obj || !((PFN_OccAt)(*(DWORD **)obj)[0x7c / 4])(obj, NULL, r->s[s].x, r->s[s].z, &occ) || !occ) {
            g_c3[C3_SPAWN_NOOCC]++; return 0;
        }
        ((PFN_XZ)(*(DWORD **)occ)[0xbc / 4])(occ, NULL, &x, &z);
        if (!((PFN_Roster)(S + 0x1ed36))(prod, NULL, (z >> 5) * *(int *)(S + 0x33280) + (x >> 5), &inst)) {
            ((PFN_Rel)(*(DWORD **)occ)[2])(occ, NULL);
            g_c3[C3_SPAWN_INITFAIL]++; return 0;
        }
        car = (BYTE *)g_new(0x15c);
        if (!car) { ((PFN_Rel)(*(DWORD **)occ)[2])(occ, NULL); return 0; }
        car = ((PFN_Ctor)(S + 0x19750))(car, NULL);
        ((PFN_Rel)(*(DWORD **)car)[1])(car, NULL);                      /* vt+4 AddRef */
        key[0] = 0xc25c2bf7; key[1] = 0x025c2c45; key[2] = inst;
        if (((PFN_Init)(*(DWORD **)car)[0x13c / 4])(car, NULL, key)) {
            int q;
            *(DWORD *)(prod + 0xc) += 1;
            ((PFN_SetProd)(*(DWORD **)car)[0x140 / 4])(car, NULL, prod);
            c->car = car; c->n = r->n - s; c->idx = 0; c->ended = c->lost = 0; c->followed = c->crossings = 0;
            c->cut = r->cut; c->roam = 0;
            c->seq = r->seq; c->spawned_tick = g_ticks; c->placing = 1;
            for (q = 0; q < c->n; q++) c->s[q] = r->s[s + q];
            g_ncars++;
            g_spawn_car = car; g_spawn_edge = edge;
            ok = ((PFN_Place)(*(DWORD **)(car + 0x18))[0x10 / 4])(car + 0x18, NULL, occ);
            g_spawn_car = NULL; g_spawn_edge = NULL;
            if (!ok) g_c3[C3_SPAWN_PLACEFAIL]++;
            else { g_c3[C3_SPAWN_OK]++; c->placing = 0; }
        } else g_c3[C3_SPAWN_INITFAIL]++;
        ((PFN_Rel)(*(DWORD **)car)[2])(car, NULL);                      /* vt+8 Release: a failed car dies here */
        ((PFN_Rel)(*(DWORD **)occ)[2])(occ, NULL);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        g_spawn_car = NULL; g_spawn_edge = NULL;
        if (c && c->car) { c->car = NULL; g_ncars--; }
        g_c3[C3_SPAWN_FAULT]++;
        return 0;
    }
    return ok;
}

/* a placement fails when the start lane is taken (FUN_1001bc70's path test): try up to 3 starts along the path */
static int spawn_one(BYTE *prod, Route *r, int s0) {
    int k, next;
    for (k = 0; k < 3 && s0 >= 0; k++) {
        int before = g_c3[C3_SPAWN_PLACEFAIL];
        if (spawn_at(prod, r, s0, &next)) { if (k) g_c3[C3_SPAWN_RETRY_OK]++; return 1; }
        if ((int)g_c3[C3_SPAWN_PLACEFAIL] == before) return 0;   /* failed for another reason: no retry */
        s0 = next;
    }
    return 0;
}

/* producer tick: route cars first while alive < target (stock rate: max(1, (target - alive) / 10) per tick) */
static void spawn_tick(BYTE *prod) {
    DWORD alive, target;
    int n;
    unsigned __int64 t0 = __rdtsc();
    if (g_mode_now < MODE_REPLACE || !prod || !g_cars) return;
    if (!*(BYTE *)(prod + 0x35)) return;
    {   static DWORD last_box;                    /* measurement: route cars inside the view box */
        DWORD now = GetTickCount();
        if (now - last_box >= 250) {
            int i, n = 0;
            last_box = now;
            for (i = 0; i < MAXCARS; i++) {
                BYTE *car = g_cars[i].car;
                if (car && !g_cars[i].placing && box_has(*(int *)(car + 0xc) >> 8, *(int *)(car + 0x14) >> 8)) n++;
            }
            g_inbox = n;
        }
    }
    if (user_paused_city()) { g_c3[C3_PAUSED_TICKS]++; return; }
    alive = *(DWORD *)(prod + 0xc); target = *(DWORD *)(prod + 0x10);
    if (g_fix) {
        /* scroll_fill: while the camera moves (and 3 s after) keep the route cars at the count they had with the camera
           still, placing at most 2 a tick from recent routes, each entering off screen */
        static DWORD last_ema;
        DWORD now = GetTickCount();
        int moving = now - g_last_move_ms < MOVE_TAIL_MS, k;
        if (now - g_last_move_ms >= MOVE_TAIL_MS && now - last_ema >= 250) {
            int px0 = *(int *)(prod + 0x24), pz0 = *(int *)(prod + 0x28), px1 = *(int *)(prod + 0x2c), pz1 = *(int *)(prod + 0x30);
            double area = (double)(px1 - px0 + 1) * (pz1 - pz0 + 1);
            last_ema = now;
            g_still = g_still * 0.9 + g_ncars * 0.1;
            if (area > 0) g_still_area = g_still_area * 0.9 + area * 0.1;
        }
        {   /* the strips the rect took in: up to 8 placements a tick, each on a route that crosses the strip */
            int placed = 0;
            while (g_nstrip && placed < STRIP_PER_TICK && *(DWORD *)(prod + 0xc) < target && *(DWORD *)(prod + 0xc) < 200 &&
                   g_ncars < (int)(g_still * 1.05 + 0.5)) {   /* never above the still-camera count */
                Strip *st = &g_strip[0];
                int px0 = *(int *)(prod + 0x24), pz0 = *(int *)(prod + 0x28), px1 = *(int *)(prod + 0x2c), pz1 = *(int *)(prod + 0x30), e;
                Route *r;
                if (st->quota <= 0 || st->x1 < px0 || st->x0 > px1 || st->z1 < pz0 || st->z0 > pz1) {   /* done, or left the rect */
                    memmove(&g_strip[0], &g_strip[1], sizeof(Strip) * (g_nstrip - 1)); g_nstrip--; continue;
                }
                r = route_strip(st, &e);
                if (!r) { g_c3[C3_STRIP_NOROUTE]++; st->quota = 0; continue; }
                g_c3[C3_STRIP_TRY]++;
                st->quota--;
                if (spawn_one(prod, r, e)) g_c3[C3_STRIP_OK]++;
                placed++;
            }
        }
        for (k = 0; moving && k < 2 && g_ncars < (int)(g_still + 0.5) && *(DWORD *)(prod + 0xc) < target &&
                    *(DWORD *)(prod + 0xc) < 200; k++) {
            int e;
            Route *r = route_fill(prod, &e);
            if (!r) break;
            g_c3[C3_FILL_TRY]++;
            if (spawn_one(prod, r, e)) g_c3[C3_FILL_OK]++;
        }
        alive = *(DWORD *)(prod + 0xc);
        /* while the camera moves (and 3 s after), stock-rate spawns do not lift the route cars above the still count
           either (R1: arrows ended at 1.3-1.4 x the still-camera count) */
        if (moving && g_ncars >= (int)(g_still * 1.05 + 0.5)) { cyc_add(__rdtsc() - t0); return; }
    }
    if (alive >= target || alive >= 200) return;
    n = (int)((target - alive) / 10);
    if (n < 1) n = 1;
    while (n-- > 0 && *(DWORD *)(prod + 0xc) < target) {
        int e;
        Route *r = route_take(prod, &e);
        if (!r) break;
        spawn_one(prod, r, e);
    }
    cyc_add(__rdtsc() - t0);
}

/* ------------------------------------------------------------ arming */

static int swap_slot(DWORD *slot, DWORD want, void *to, void **orig) {
    DWORD old;
    if (*slot != want) return 0;
    if (!VirtualProtect(slot, 4, PAGE_READWRITE, &old)) return 0;
    *orig = (void *)*slot;
    InterlockedExchange((volatile LONG *)slot, (LONG)to);
    VirtualProtect(slot, 4, old, &old);
    return 1;
}

static DWORD g_view_target;
static volatile LONG g_skip_tick;

static __declspec(naked) void view_stub(void) {    /* replaces call FUN_1001f040 (thiscall, 1 arg, ret 4) */
    __asm {
        cmp dword ptr [g_mode_now], MODE_REPLACE
        je skip
        jmp dword ptr [g_view_target]
    skip:
        ret 4
    }
}

static int arm_cars(HMODULE strt) {
    BYTE *S = (BYTE *)strt;
    DWORD *cv = (DWORD *)(S + 0x2cd20), *pv = (DWORD *)(S + 0x2d1d0);
    int ok = 1;
    HMODULE crt = GetModuleHandleA("MSVCRT.dll");
    g_new = crt ? (PFN_New)GetProcAddress(crt, "??2@YAPAXI@Z") : NULL;
    g_build = (PFN_Build)(S + 0x18630);
    g_rq = (Route *)VirtualAlloc(NULL, sizeof(Route) * RQN, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    g_cars = (RCar *)VirtualAlloc(NULL, sizeof(RCar) * MAXCARS, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!g_new || !g_rq || !g_cars) return 0;
    ok &= swap_slot(cv + 0x154 / 4, (DWORD)S + 0x1c510, my_selpath, (void **)&g_o_selpath);
    ok &= swap_slot(cv + 0x158 / 4, (DWORD)S + 0x1c290, my_seledge, (void **)&g_o_seledge);
    ok &= swap_slot(pv + 0x10 / 4, (DWORD)S + 0x1f610, my_gone, (void **)&g_o_gone);
    ok &= swap_slot(pv + 0x14 / 4, (DWORD)S + 0x1eec4, my_need, (void **)&g_o_need);
    {   static const DWORD sites[2] = { 0x154a0, 0x15573 };
        int i;
        g_view_target = (DWORD)S + 0x1f040;
        for (i = 0; i < 2; i++) {
            BYTE *p = S + sites[i], b[5];
            if (p[0] != 0xE8 || (DWORD)(p + 5) + *(DWORD *)(p + 1) != g_view_target) { ok = 0; continue; }
            call_bytes(b, p, view_stub);
            ok &= write_q(p, b, 5);
        }
    }
    return ok;
}

/* runtime scroll_fill switch (A/B, measurement): 1 on, 0 off; returns the previous state */
__declspec(dllexport) int __cdecl sc3cartrips_fill(int on) {
    return (int)InterlockedExchange(&g_fix, on ? 1 : 0);
}

/* runtime mode switch (A/B): 2 replace, 3 filler, 1 capture only (stock cars); returns the previous mode */
__declspec(dllexport) int __cdecl sc3cartrips_mode(int m) {
    int prev = g_mode_now;
    if (m >= MODE_CAPTURE && m <= MODE_FILLER) InterlockedExchange(&g_mode_now, m);
    return prev;
}

/* ------------------------------------------------------------ agent-loop timer (time_agents=1, measurement) */

static BYTE *g_ag_tramp;
static DWORD g_ag_ret;
static unsigned __int64 g_ag_t0;
static volatile DWORD g_ag_cyc_lo, g_ag_cyc_hi, g_ag_calls;

static void __cdecl ag_done(void) {
    unsigned __int64 v = ((unsigned __int64)g_ag_cyc_hi << 32 | g_ag_cyc_lo) + (__rdtsc() - g_ag_t0);
    g_ag_cyc_lo = (DWORD)v; g_ag_cyc_hi = (DWORD)(v >> 32);
    g_ag_calls++;
}
static __declspec(naked) void ag_exit(void) {
    __asm {
        push eax
        push edx
        push ecx
        call ag_done
        pop ecx
        pop edx
        pop eax
        jmp dword ptr [g_ag_ret]
    }
}
/* entry of SC3U FUN_00425a10 (game thread only, not re-entered): remember the return address, return through ag_exit */
static __declspec(naked) void ag_entry(void) {
    __asm {
        push eax
        push edx
        rdtsc
        mov dword ptr [g_ag_t0], eax
        mov dword ptr [g_ag_t0 + 4], edx
        pop edx
        pop eax
        push eax
        mov eax, [esp + 4]
        mov dword ptr [g_ag_ret], eax
        mov dword ptr [esp + 4], offset ag_exit
        pop eax
        jmp dword ptr [g_ag_tramp]
    }
}
static int arm_agtimer(void) {
    BYTE *p = (BYTE *)GetModuleHandleA(NULL) + 0x25a10, b[5];
    static const BYTE expect[] = { 0x6a, 0xff, 0x68, 0x30, 0x3f, 0x4c, 0x00 };
    if (memcmp(p, expect, sizeof(expect))) return 0;
    g_ag_tramp = (BYTE *)VirtualAlloc(NULL, 16, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!g_ag_tramp) return 0;
    memcpy(g_ag_tramp, p, 7);
    g_ag_tramp[7] = 0xE9;
    *(DWORD *)(g_ag_tramp + 8) = (DWORD)(p + 7) - (DWORD)(g_ag_tramp + 12);
    b[0] = 0xE9;
    *(DWORD *)(b + 1) = (DWORD)ag_entry - (DWORD)(p + 5);
    return write_q(p, b, 5);
}

/* for ctm_modealt.py: [0] mode [1] alive [2] target [3] route cars [4] ag calls [5] ag cycles lo [6] hi
   [7] our game-thread cycles lo [8] hi [9] decisions [10] followed [11] lost events [12] spawn ok [13] end other */
__declspec(dllexport) int __cdecl sc3cartrips_cars(DWORD *out, int n) {
    DWORD v[14];
    BYTE *L, *prod;
    int i;
    memset(v, 0, sizeof(v));
    v[0] = g_mode_now; v[3] = g_ncars;
    __try {
        L = g_strt_base ? *(BYTE **)(g_strt_base + 0x33208) : NULL;
        prod = L ? *(BYTE **)(L + 0x100) : NULL;
        if (prod) { v[1] = *(DWORD *)(prod + 0xc); v[2] = *(DWORD *)(prod + 0x10); }
    } __except (EXCEPTION_EXECUTE_HANDLER) { }
    v[4] = g_ag_calls; v[5] = g_ag_cyc_lo; v[6] = g_ag_cyc_hi; v[7] = g_c3_cyc_lo; v[8] = g_c3_cyc_hi;
    v[9] = g_c3[C3_DECISIONS]; v[10] = g_c3[C3_FOLLOWED]; v[11] = g_c3[C3_LOST_EVENTS]; v[12] = g_c3[C3_SPAWN_OK];
    v[13] = g_c3[C3_END_OTHER];
    for (i = 0; i < n && i < 14; i++) out[i] = v[i];
    return i;
}
