/* ===================================================================================================== STATIONWARN
 * (child stationwarn 2026-11-03, owner: "add an indicator when a station of any kind can't receive passengers because
 * it's poorly connected"). #included by sc3resize.c after RESTORE. Evidence: re/analysis/STATION_RULE.md,
 * verify/stationwarn/RESULTS.md.
 *
 * The rule is the trip router's own (SimTransit, T = *(SimTransit+0x1fdb8)), read, not measured beyond railgap:
 *  - Station kinds: the cell flag builder FUN_10005983 tags only four occupant type ids (vt+0x88) as stations, over the
 *    whole occupant rect: 0x2fb2 bus stop (flags | 0x11), 0x2fc6 rail station (| 0x14), 0x3048 subway station (| 0x18),
 *    0x3049 rail-subway (| 0x3c) [CONFIRMED @ SimTransit 0x10005983]. Ports and airports are no trip nodes.
 *  - A node's neighbours (ring scan 0x10007a63) are the cells of its rect grown by one, corners excluded. A station node
 *    is the whole occupant rect (manager *(T+0x94) vt+0x7c(x, z, &occ), occ vt+0xcc rect) [CONFIRMED @ 0x1000755e].
 *  - IN: a road node (type 1, cell flag 1 without 0x40) offers a neighbouring 0x10 cell as a station (bus stop with bus
 *    mode, else 0x30 / 0x14 / 0x18 by flags), scored 0xff so it wins over any road; the trip's start node (0x80) does the
 *    same over the lot grown by TripMaxDistanceToRoad (T+0xc5/c6/c7) [CONFIRMED @ 0x1000755e, 0x80 branch]. The cells
 *    within that reach of R / C / I lots are the grids T+0x84 / +0x88 / +0x8c, filled by FUN_1000559e around the
 *    classes FUN_1000532c maps to 0 / 1 / 2 [CONFIRMED @ 0x1000559e, 0x1000532c].
 *  - OUT: a rail station (0x14) steps only to a neighbour with flag 4 and no 0x10, a subway station (0x18) to flag 8,
 *    a rail-subway (0x30) to either by the trip's mode, and none of them back to track when it came from track (parent
 *    type test); from any station a trip can also take a neighbouring bus stop [CONFIRMED @ 0x1000755e: 0x10007f87,
 *    0x10007fe9]. railgap measured it: one cell off the track = 0 trips (verify/railgap/RESULTS.md).
 *  - WHERE TO: a rail (4) or subway (8) node arrives only on map-edge connection cells 0x1000 / 0x2000 (FUN_10008a94);
 *    otherwise it has to step into another station cell (rail: 0x10 with 4; subway: 0x10 with 0x20, or with 8 and
 *    without 1 / 4) whose rect lies in the destination grid [CONFIRMED @ 0x10008a94, 0x1000755e types 4 / 8]. Track
 *    nodes spread over 4-neighbour cells of their own bit.
 *  - Bus stop: in from a neighbouring road (bus mode), out only to a neighbouring road cell as a bus-road node (0x41),
 *    which arrives like a road [CONFIRMED @ 0x1000755e type 0x50, 0x10008a94 type 0x41].
 *  - Not read by the router: power, funding, strikes. Not checked here: the trip budget (1,024 cost units, about 500
 *    rail cells) and which buildings may use transit (building bytes +0xc..+0xe, writer unknown).
 * So a station is flagged when: it touches no track of its own kind (SW_NOTRACK), no road cell and no lot reach grid
 * touches it (SW_NOACCESS), or its track reaches no map edge and no other station with lots in reach (SW_NODEST); a bus
 * stop when no road cell touches it (SW_NOROAD).
 *
 * Shown: a red row in the station's "?" dialog per reason, "Estaciones sin conexion: N" on the Cuadros Transporte tab,
 * and an in-world marker (SWMARK below). SC3RESIZE_STATIONWARN=0: none of it. _LOG=1: one line per flagged station per scan. */
static int g_sw = 1, g_sw_log;

#define SW_NST   4096
#define SW_S     1024
#define SW_MAXCP 32768
enum { SW_BUS, SW_RAIL, SW_SUB, SW_RS };
#define SW_NOTRACK  1
#define SW_NOACCESS 2
#define SW_NODEST   4
#define SW_NOROAD   8
typedef struct { short x0, z0, x1, z1; BYTE kind, bad, reach, road, trail, tsub, drail, dsub; LONG pax; } SW_ST;   /* pax: the game's own
   station rows read: transit layer vt+0x60(x, z, &byte, 0x10), the station-cell density that arrived trips deposit (the
   per-cell rows FUN_1000b2c2, call at SimTransit 0x1000b472 with this = T), -1 unknown. Diagnostic only (log). */
typedef struct { WORD a, b; BYTE edge; } SW_CP;   /* a track component: up to two stations (index + 1) it delivers to */

static SW_ST  g_sw_a[SW_NST], g_sw_b[SW_NST], *g_sw_st = g_sw_a;   /* published list (UI), the other one is built */
static volatile LONG g_sw_n, g_sw_nbad, g_sw_nst, g_sw_busy, g_sw_gen;
static DWORD  g_sw_tick;
static BYTE  *g_sw_T;
static int    g_sw_W, g_sw_H;
static WORD  *g_sw_map;        /* station index + 1 per cell, 0xffff = a station cell with no known occupant */
static DWORD *g_sw_comp, *g_sw_q;
static SW_CP *g_sw_cp;

static BYTE *sw_T(void) {
    HMODULE st = GetModuleHandleA("SimTransit.dll");
    BYTE *T = st ? *(BYTE **)((BYTE *)st + 0x1fdb8) : NULL;
    if (!T || IsBadReadPtr(T, 0x100) || *(DWORD *)T != (DWORD)st + 0x1a368) return NULL;
    return T;
}
static int sw_alloc(void) {
    if (g_sw_cp) return 1;
    g_sw_map = (WORD *)VirtualAlloc(NULL, SW_S * SW_S * 2, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    g_sw_comp = g_sw_map ? (DWORD *)VirtualAlloc(NULL, SW_S * SW_S * 4, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE) : NULL;
    g_sw_q = g_sw_comp ? (DWORD *)VirtualAlloc(NULL, SW_S * SW_S * 4, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE) : NULL;
    g_sw_cp = g_sw_q ? (SW_CP *)VirtualAlloc(NULL, SW_MAXCP * sizeof(SW_CP), MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE) : NULL;
    if (!g_sw_cp) logf("STATIONWARN> no memory for the scan grids: off");
    return g_sw_cp != NULL;
}

/* flags grid T+0x5c: object +0xc = row array by x, u16 per z [CONFIRMED @ 0x10008a94] */
#define SW_F(F, x, z) ((F)[(x)][(z)])
static int sw_ingrid(BYTE *T, int off, int x, int z) {
    BYTE *g = *(BYTE **)(T + off);
    DWORD **rows;
    if (!g || IsBadReadPtr(g, 0x14) || !(rows = *(DWORD ***)(g + 0x10))) return 0;
    return (rows[x][z >> 5] >> (z & 31)) & 1;
}
static int sw_reach(BYTE *T, int x, int z) { return sw_ingrid(T, 0x84, x, z) || sw_ingrid(T, 0x88, x, z) || sw_ingrid(T, 0x8c, x, z); }

/* track cell of the network (rail 4 / subway 8): the bit and no station bit */
static int sw_track(WORD f, int net) { return !(f & 0x10) && (f & (net ? 8 : 4)); }
/* a station cell a track node of the network steps into (0x1000755e types 4 / 8) */
static int sw_entry(WORD f, int net) {
    if (!(f & 0x10)) return 0;
    if (!net) return (f & 4) != 0;
    return (f & 0x20) || ((f & 8) && !(f & 5));
}

/* label the track component holding cell (x, z) of the network, collecting the stations it delivers to */
static DWORD sw_flood(WORD **F, int W, int H, int x, int z, int net, DWORD id) {
    SW_CP *c = &g_sw_cp[id];
    DWORD qh = 0, qt = 0;
    WORD edge = net ? 0x2000 : 0x1000;
    c->a = c->b = 0; c->edge = 0;
    g_sw_comp[x * SW_S + z] = id;
    g_sw_q[qt++] = (DWORD)(x * SW_S + z);
    while (qh < qt) {
        DWORD p = g_sw_q[qh++];
        int cx = (int)(p / SW_S), cz = (int)(p % SW_S), k;
        if (SW_F(F, cx, cz) & edge) c->edge = 1;
        for (k = 0; k < 4; k++) {
            int nx = cx + (k == 0 ? -1 : k == 1 ? 1 : 0), nz = cz + (k == 2 ? -1 : k == 3 ? 1 : 0);
            WORD f;
            if (nx < 0 || nz < 0 || nx >= W || nz >= H) continue;
            f = SW_F(F, nx, nz);
            if (sw_track(f, net)) {
                if (!g_sw_comp[nx * SW_S + nz]) { g_sw_comp[nx * SW_S + nz] = id; g_sw_q[qt++] = (DWORD)(nx * SW_S + nz); }
            } else if (sw_entry(f, net)) {
                WORD s = g_sw_map[nx * SW_S + nz];
                if (s && s != 0xffff && g_sw_b[s - 1].reach) {
                    if (!c->a) c->a = s; else if (c->a != s && !c->b) c->b = s;
                }
            }
        }
    }
    return qt;
}

/* the ring of a station rect: grown by one, corners and the rect itself excluded, clamped (0x10007a63) */
#define SW_RING_FOR(s, W, H, x, z) \
    for (x = (s)->x0 - 1; x <= (s)->x1 + 1; x++) for (z = (s)->z0 - 1; z <= (s)->z1 + 1; z++) \
        if (x >= 0 && z >= 0 && x < (W) && z < (H) && \
            !((x == (s)->x0 - 1 || x == (s)->x1 + 1) && (z == (s)->z0 - 1 || z == (s)->z1 + 1)) && \
            !(x >= (s)->x0 && x <= (s)->x1 && z >= (s)->z0 && z <= (s)->z1))

static void sw_scan(void) {
    BYTE *T = sw_T(), *mgr;
    WORD **F;
    int W, H, x, z, n = 0, i, net, nbad = 0, cen[8][2];
    DWORD ncp = 1, t0 = GetTickCount();
    if (!T || !sw_alloc()) { g_sw_T = NULL; InterlockedExchange(&g_sw_n, 0); InterlockedExchange(&g_sw_nbad, 0); return; }
    memset(cen, 0, sizeof(cen));
    W = *(int *)(T + 0x14); H = *(int *)(T + 0x18);
    if (W <= 0 || H <= 0 || W > SW_S || H > SW_S) return;
    F = *(WORD ***)(*(BYTE **)(T + 0x5c) + 0xc);
    mgr = *(BYTE **)(T + 0x94);
    if (!F || !mgr) return;
    for (x = 0; x < W; x++) memset(g_sw_map + x * SW_S, 0, H * 2);
    /* 1. stations: every 0x10 cell, grouped by its occupant */
    for (x = 0; x < W; x++) for (z = 0; z < H; z++) {
        WORD f = SW_F(F, x, z);
        void *o = NULL;
        LONG r[6];
        DWORD ty;
        SW_ST *s;
        int kind, a, b;
        if (!(f & 0x10) || g_sw_map[x * SW_S + z]) continue;
        g_sw_map[x * SW_S + z] = 0xffff;
        if (n >= SW_NST || !(ho_v(mgr, 0x7c, 3, (DWORD)x, (DWORD)z, (DWORD)&o, 0, 0) & 0xff) || !o) continue;
        ty = ho_v(o, 0x88, 0, 0, 0, 0, 0, 0);
        kind = ty == 0x2fb2 ? SW_BUS : ty == 0x2fc6 ? SW_RAIL : ty == 0x3048 ? SW_SUB : ty == 0x3049 ? SW_RS : -1;
        r[0] = r[1] = r[3] = r[4] = 0x7fffffff;
        s = &g_sw_b[n];
        memset(s, 0, sizeof(*s));
        s->pax = -1;
        if (kind >= 0) {
            ho_v(o, 0xcc, 1, (DWORD)r, 0, 0, 0, 0);
            if (g_sw_log && r[0] != 0x7fffffff) { BYTE b = 0; ho_v(T, 0x60, 4, (DWORD)(r[0] >> 8), (DWORD)(r[1] >> 8), (DWORD)&b, 0x10, 0); s->pax = b; }
        }
        ho_v(o, 0x08, 0, 0, 0, 0, 0, 0);
        if (kind < 0 || r[0] == 0x7fffffff) continue;
        s->x0 = (short)(r[0] >> 8); s->z0 = (short)(r[1] >> 8); s->x1 = (short)(r[3] >> 8); s->z1 = (short)(r[4] >> 8);
        if (s->x0 < 0 || s->z0 < 0 || s->x1 >= W || s->z1 >= H || s->x1 < s->x0 || s->z1 < s->z0 || s->x1 - s->x0 > 15 || s->z1 - s->z0 > 15) continue;
        s->kind = (BYTE)kind;
        for (a = s->x0; a <= s->x1; a++) for (b = s->z0; b <= s->z1; b++) {
            g_sw_map[a * SW_S + b] = (WORD)(n + 1);
            if (!s->reach && sw_reach(T, a, b)) s->reach = 1;
        }
        n++;
    }
    /* 2. what touches each station */
    for (i = 0; i < n; i++) {
        SW_ST *s = &g_sw_b[i];
        SW_RING_FOR(s, W, H, x, z) {
            WORD f = SW_F(F, x, z);
            if (!(f & 0x10) && (f & 1) && (s->kind == SW_BUS || !(f & 0x40))) s->road = 1;
            /* a rail / subway station hands trips to a neighbouring bus stop (0x10007fe9, bus mode): that is a way out
               to the streets too (measured: Sacramento rail stations with no road and no lot reach, density 1 and 19) */
            if (s->kind != SW_BUS && (f & 0x11) == 0x11) s->road = 1;
            if (sw_track(f, 0)) s->trail = 1;
            if (sw_track(f, 1)) s->tsub = 1;
        }
    }
    /* 3. where the track goes: one flood per component touched by a station, per network */
    for (net = 0; net < 2; net++) {
        for (x = 0; x < W; x++) memset(g_sw_comp + x * SW_S, 0, H * 4);
        for (i = 0; i < n; i++) {
            SW_ST *s = &g_sw_b[i];
            int want = net ? (s->kind == SW_SUB || s->kind == SW_RS) : (s->kind == SW_RAIL || s->kind == SW_RS);
            BYTE ok = 0;
            if (!want) continue;
            SW_RING_FOR(s, W, H, x, z) {
                DWORD c;
                if (!sw_track(SW_F(F, x, z), net)) continue;
                c = g_sw_comp[x * SW_S + z];
                if (!c && ncp < SW_MAXCP) { c = ncp++; sw_flood(F, W, H, x, z, net, c); }
                if (c && (g_sw_cp[c].edge || (g_sw_cp[c].a && g_sw_cp[c].a != i + 1) || (g_sw_cp[c].b && g_sw_cp[c].b != i + 1))) ok = 1;
            }
            if (net) s->dsub = ok; else s->drail = ok;
        }
    }
    /* 4. the verdict */
    for (i = 0; i < n; i++) {
        SW_ST *s = &g_sw_b[i];
        if (s->kind == SW_BUS) s->bad = s->road ? 0 : SW_NOROAD;
        else {
            int touch = s->kind == SW_RAIL ? s->trail : s->kind == SW_SUB ? s->tsub : (s->trail || s->tsub);
            int dest = s->kind == SW_RAIL ? s->drail : s->kind == SW_SUB ? s->dsub : (s->drail || s->dsub);
            s->bad = 0;
            if (!touch) s->bad |= SW_NOTRACK;
            else if (!dest) s->bad |= SW_NODEST;
            if (!s->road && !s->reach) s->bad |= SW_NOACCESS;
        }
        if (s->bad) {
            nbad++;
            if (g_sw_log) logf("STATIONWARN>   kind %d [%d %d .. %d %d] bad 0x%x (road %d reach %d rail %d/%d subway %d/%d) station density %ld", s->kind,
                               s->x0, s->z0, s->x1, s->z1, s->bad, s->road, s->reach, s->trail, s->drail, s->tsub, s->dsub, s->pax);
        }
        if (s->pax >= 0) { int k = s->kind * 2 + (s->bad ? 1 : 0); cen[k][0]++; if (s->pax > 0) cen[k][1]++; }
        if (g_sw_log && !s->bad && s->pax == 0)
            logf("STATIONWARN>   unused but connected: kind %d [%d %d .. %d %d] (road %d reach %d rail %d/%d subway %d/%d)", s->kind,
                 s->x0, s->z0, s->x1, s->z1, s->road, s->reach, s->trail, s->drail, s->tsub, s->dsub);
    }
    /* publish: built in g_sw_b, readers use g_sw_a (count first down, list, count up) */
    InterlockedExchange(&g_sw_n, 0);
    memcpy(g_sw_a, g_sw_b, n * sizeof(SW_ST));
    g_sw_T = T; g_sw_W = W; g_sw_H = H;
    InterlockedExchange(&g_sw_n, n);
    {   LONG prev = InterlockedExchange(&g_sw_nbad, nbad);
        InterlockedIncrement(&g_sw_gen);
        if (prev != nbad || g_sw_log)
        {
            logf("STATIONWARN> scan %dx%d: %d station(s), %d not connected, %lu track component(s), %lu ms", W, H, n, nbad, ncp - 1, GetTickCount() - t0);
            logf("STATIONWARN>   station density > 0 (ok / flagged): bus %d of %d / %d of %d, rail %d of %d / %d of %d, subway %d of %d / %d of %d, rail-subway %d of %d / %d of %d",
                 cen[0][1], cen[0][0], cen[1][1], cen[1][0], cen[2][1], cen[2][0], cen[3][1], cen[3][0],
                 cen[4][1], cen[4][0], cen[5][1], cen[5][0], cen[6][1], cen[6][0], cen[7][1], cen[7][0]);
        }
    }
}

/* a scan at most every 2 s (UI readers), or now (force) */
static void sw_refresh(int force) {
    DWORD now = GetTickCount();
    if (!g_sw) return;
    if (!force && g_sw_tick && now - g_sw_tick < 2000 && g_sw_T == sw_T()) return;
    if (InterlockedExchange(&g_sw_busy, 1)) return;
    g_sw_tick = now;
    __try { sw_scan(); } __except (EXCEPTION_EXECUTE_HANDLER) { logf("STATIONWARN> scan threw 0x%08lX", GetExceptionCode()); InterlockedExchange(&g_sw_n, 0); }
    InterlockedExchange(&g_sw_busy, 0);
}

/* the published station at cell (x, z), or NULL */
static SW_ST *sw_at(int x, int z) {
    LONG i, n = g_sw_n;
    for (i = 0; i < n; i++) {
        SW_ST *s = &g_sw_st[i];
        if (x >= s->x0 && x <= s->x1 && z >= s->z0 && z <= s->z1) return s;
    }
    return NULL;
}

/* ------------------------------------------------------------------------------------------- "?" dialog rows */
/* The query dialog's row list (QI 0x583) vt+0x4c FUN_100645bf(label, value, flags, red) [CONFIRMED @ SIMUI 0x100645bf],
   the way QROWS adds its rows. Called from rs_qrows (sc3resize_restore.c) before the dialog grows, returns the rows
   added. One row per reason, red; a connected station gets one navy row. */
static int sw_row(void *li, const char *label, const char *value, int red) {
    BYTE a[0x20], b[0x20];
    DWORD r;
    ho_str(a, label); ho_str(b, value);
    r = ho_v(li, 0x4c, 4, (DWORD)a, (DWORD)b, 0x20000u, red ? 1 : 0, 0);
    ho_str_free(a); ho_str_free(b);
    return (int)(r & 0xff);
}
static int sw_qrows(void *li, BYTE *occ) {
    DWORD ty;
    LONG r[6];
    SW_ST *s;
    int es = ho_spanish(), n = 0, kind;
    const char *lb;
    if (!g_sw || !li || !occ) return 0;
    ty = ho_v(occ, 0x88, 0, 0, 0, 0, 0, 0);
    kind = ty == 0x2fb2 ? SW_BUS : ty == 0x2fc6 ? SW_RAIL : ty == 0x3048 ? SW_SUB : ty == 0x3049 ? SW_RS : -1;
    if (kind < 0) return 0;
    r[0] = r[1] = 0x7fffffff;
    ho_v(occ, 0xcc, 1, (DWORD)r, 0, 0, 0, 0);
    if (r[0] == 0x7fffffff) return 0;
    sw_refresh(1);
    if (g_sw_log) {   /* field dump around the station object (diag: which field the stock rows read) */
        char t[400];
        int k, m = 0;
        for (k = -2; k < 24 && m < 380; k++) m += wsprintfA(t + m, " %08lX", IsBadReadPtr(occ + k * 4, 4) ? 0 : *(DWORD *)(occ + k * 4));
        logf("STATIONWARN> query occ 0x%08lX dwords from occ-8:%s", (DWORD)occ, t);
    }
    s = sw_at(r[0] >> 8, r[1] >> 8);
    if (!s) { logf("STATIONWARN> query: station type 0x%lx at (%ld, %ld) not in the scan", ty, r[0] >> 8, r[1] >> 8); return 0; }
    lb = SC3TR(es, "stationwarn.no_passengers", "Sin pasajeros:", "No passengers:");
    if (!s->bad) n += sw_row(li, SC3TR(es, "stationwarn.connection", "Conexi\xf3n:", "Connection:"),
                             SC3TR(es, "stationwarn.connected", "correcta", "connected"), 0);
    if (s->bad & SW_NOROAD) n += sw_row(li, lb, SC3TR(es, "stationwarn.bus_no_street", "sin calle al lado", "no street next to it"), 1);
    if (s->bad & SW_NOTRACK)
        n += sw_row(li, lb, s->kind == SW_RAIL ? SC3TR(es, "stationwarn.rail_no_track", "no toca la v\xed""a", "not on the track") :
                            s->kind == SW_SUB ? SC3TR(es, "stationwarn.subway_no_track", "no toca el metro", "not on the subway line") :
                            SC3TR(es, "stationwarn.rs_no_track", "no toca v\xed""a ni metro", "not on track or subway"), 1);
    if (s->bad & SW_NODEST)
        n += sw_row(li, lb, s->kind == SW_SUB ? SC3TR(es, "stationwarn.subway_no_dest", "metro sin otra estaci\xf3n", "no other station on it") :
                            SC3TR(es, "stationwarn.rail_no_dest", "v\xed""a sin otra estaci\xf3n", "no other station on it"), 1);
    if (s->bad & SW_NOACCESS) n += sw_row(li, lb, SC3TR(es, "stationwarn.no_access", "sin calle ni edificios", "no street or buildings"), 1);
    logf("STATIONWARN> query: station kind %d [%d %d .. %d %d] bad 0x%x, %d row(s)", s->kind, s->x0, s->z0, s->x1, s->z1, s->bad, n);
    return n;
}

/* ------------------------------------------------------------------------------------------- Cuadros line */
/* "Estaciones sin conexion: N de M" for the Transporte tab (vb_transport), "" when off or no station */
static int sw_cuadros_text(char *out, int cap) {
    int es = ho_spanish();
    out[0] = 0;
    if (!g_sw) return 0;
    sw_refresh(0);
    if (g_sw_n <= 0) return 0;
    if (g_sw_nbad > 0) _snprintf(out, cap, SC3TR(es, "stationwarn.cuadros_bad", "Estaciones sin conexi\xf3n: %ld de %ld", "Stations not connected: %ld of %ld"), g_sw_nbad, g_sw_n);
    else _snprintf(out, cap, SC3TR(es, "stationwarn.cuadros_ok", "Estaciones: %ld, todas conectadas", "Stations: %ld, all connected"), g_sw_n);
    out[cap - 1] = 0;
    return g_sw_nbad > 0 ? 2 : 1;
}

/* ------------------------------------------------------------------------------------------- SWMARK: in-world marker */
/* The game has no generic problem icon: its flashing outage icon is the power-only display cSC3PowerOuttageDisplay
 * (SIMSPR 0x1003db3d / 0x1003e486, one image set, names [LINUX-HINT]), so reusing it would read as "no power". The
 * marker is the game's cell highlighter instead, the grid the tools draw their previews and refusals with
 * (re/analysis/PLACEHINTS.md): the city view window (outer, SIMSPR vt 0x67894) holds it at +0xc0 (GetCellCursorMap
 * SIMSPR 0x1004abc0, Linux cSC3WinCityView::GetCellCursorMap +0xb8) [CONFIRMED @ SIMSPR 0x1004abc0, 0x1004abde], vtable
 * SIMSPR 0x10067a5c, cell bytes in the grid object +0x6c (vt+0x34 get, vt+0x3c set (x, z, &byte)): low nibble 0xf =
 * code 0x24, the red the tools use for "refused" (getter 0x1004adcd). The terrain under the cell turns red and a
 * building standing on a red cell gets the red tint (SIMSPR 0x10018081). vt+0x58 0x1004b779(rect6) repaints the cells
 * whose live and pushed nibbles differ. The cells are written straight into the grid, not through vt+0x2c, so they stay
 * out of the dirty rect +0x50 the tools' clear FUN_1004b653 wipes; a tool preview over a station can still wipe them and
 * the next pass puts them back. Blinks like the outage icon (SC3RESIZE_STATIONWARN_BLINK=0: steady). Game thread only
 * (the city view heartbeat). SC3RESIZE_STATIONWARN_MARK=0: no marker. */
static int g_sw_mark = 1, g_sw_blink = 1;
#define SW_MK 512
static struct { short x0, z0, x1, z1; } g_sw_mk[SW_MK];   /* stations marked now */
static int   g_sw_nmk, g_sw_mkon = -1;
static LONG  g_sw_mkgen = -1;
static void *g_sw_mkhl;
static DWORD g_sw_mkt;

static void *sw_hl(void) {
    DWORD ss = (DWORD)GetModuleHandleA("SIMSPR.DLL");
    BYTE *v = (BYTE *)rz_city_view();
    int k;
    if (!v || !ss) return NULL;
    for (k = 0; k < 2; k++) {
        BYTE *o = k ? v : v - 4;
        void *h;
        if (IsBadReadPtr(o + 0xc0, 4)) continue;
        h = *(void **)(o + 0xc0);
        if (h && !IsBadReadPtr(h, 0x70) && *(DWORD *)h == ss + 0x67a5c) return h;
    }
    return NULL;
}
/* one rect's cells to red (on) or back to none (only cells still red); 1 = something changed */
static int sw_paint(void *hl, int x0, int z0, int x1, int z1, int on) {
    void *g = *(void **)((BYTE *)hl + 0x6c);
    int x, z, ch = 0;
    if (!g || IsBadReadPtr(g, 4)) return 0;
    for (x = x0; x <= x1; x++) for (z = z0; z <= z1; z++) {
        BYTE b = 0, nb;
        ho_v(g, 0x34, 3, (DWORD)x, (DWORD)z, (DWORD)&b, 0, 0);
        if (on) nb = (BYTE)((b & 0xf0) | 0x0f);
        else if ((b & 0x0f) == 0x0f) nb = (BYTE)(b & 0xf0);
        else continue;
        if (nb != b) { ho_v(g, 0x3c, 3, (DWORD)x, (DWORD)z, (DWORD)&nb, 0, 0); ch = 1; }
    }
    if (ch) {
        LONG r[6];
        r[0] = x0 << 8; r[1] = z0 << 8; r[2] = 0; r[3] = x1 << 8; r[4] = z1 << 8; r[5] = 0;
        ho_v(hl, 0x58, 1, (DWORD)r, 0, 0, 0, 0);
    }
    return ch;
}
static void sw_unmark_all(void *hl) {
    int i;
    if (hl) for (i = 0; i < g_sw_nmk; i++) sw_paint(hl, g_sw_mk[i].x0, g_sw_mk[i].z0, g_sw_mk[i].x1, g_sw_mk[i].z1, 0);
    g_sw_nmk = 0;
}
/* every frame from the heartbeat (game thread): rescan every 3 s, keep the marks, blink */
static void sw_tick(void) {
    void *hl;
    DWORD now;
    int on, i, ch = 0;
    if (!g_sw || !g_sw_mark) return;
    now = GetTickCount();
    if (now - g_sw_mkt < 100) return;
    g_sw_mkt = now;
    __try {
        hl = sw_hl();
        if (hl != g_sw_mkhl) { g_sw_nmk = 0; g_sw_mkhl = hl; g_sw_mkgen = -1; }   /* a new view: its grid starts empty */
        if (!hl) return;
        if (!g_sw_tick || now - g_sw_tick >= 3000) sw_refresh(1);
        on = g_sw_blink ? (int)((now / 700) & 1) : 1;
        if (g_sw_mkgen != g_sw_gen) {   /* a new scan: drop marks no longer wanted, mark the new set */
            LONG n = g_sw_n;
            sw_unmark_all(hl);
            for (i = 0; i < n && g_sw_nmk < SW_MK; i++) if (g_sw_st[i].bad) {
                g_sw_mk[g_sw_nmk].x0 = g_sw_st[i].x0; g_sw_mk[g_sw_nmk].z0 = g_sw_st[i].z0;
                g_sw_mk[g_sw_nmk].x1 = g_sw_st[i].x1; g_sw_mk[g_sw_nmk].z1 = g_sw_st[i].z1;
                g_sw_nmk++;
            }
            g_sw_mkgen = g_sw_gen; g_sw_mkon = -1;
        }
        /* every pass: the wanted state (restores marks a tool preview wiped; a no-op when nothing differs) */
        for (i = 0; i < g_sw_nmk; i++) ch |= sw_paint(hl, g_sw_mk[i].x0, g_sw_mk[i].z0, g_sw_mk[i].x1, g_sw_mk[i].z1, on);
        if (g_sw_log && on != g_sw_mkon) {
            static int nlog;
            if (nlog++ < 6) logf("STATIONWARN> marker %s on %d station(s) (highlighter 0x%08lX)%s", on ? "on" : "off", g_sw_nmk, (DWORD)hl, ch ? "" : ", nothing to repaint");
        }
        g_sw_mkon = on;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        static int nf;
        if (nf++ < 3) logf("STATIONWARN> marker pass threw 0x%08lX", GetExceptionCode());
    }
}

static void sw_install(void) {
    char v[16];
    if (GetEnvironmentVariableA("SC3RESIZE_STATIONWARN", v, sizeof(v))) g_sw = atoi(v);
    if (GetEnvironmentVariableA("SC3RESIZE_STATIONWARN_MARK", v, sizeof(v))) g_sw_mark = atoi(v);
    if (GetEnvironmentVariableA("SC3RESIZE_STATIONWARN_BLINK", v, sizeof(v))) g_sw_blink = atoi(v);
    if (GetEnvironmentVariableA("SC3RESIZE_STATIONWARN_LOG", v, sizeof(v))) g_sw_log = atoi(v);
    if (!g_sw) { logf("STATIONWARN> off (SC3RESIZE_STATIONWARN=0)"); return; }
    logf("STATIONWARN> on: station rule check, \"?\" rows, Cuadros Transporte line%s%s", g_sw_mark ? ", red marker" : "",
         g_sw_mark && g_sw_blink ? " (blinking)" : "");
}
