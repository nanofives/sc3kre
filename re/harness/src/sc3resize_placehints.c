/* ====================================================================================================== PLACEHINTS
 * (child placehints 2026-11-02, owner: "when placing airports and ports would you be able to display the extents of how
 * much will it plop? ... same with the limits of RCI" and "for parks and other ploppable buildings show the impact it has
 * in nearby zones"). #included by sc3resize.c after RCIBARS. Evidence: re/sessions/STATUS_placehints.md,
 * re/analysis/PLACEHINTS.md.
 *
 * Both hints reuse the game's own preview: the drag/footprint highlight grid (SIMSPR highlighter, vtable 0x10067a5c) and
 * the cost label next to the cursor (SIMSPR view vtable 0x10067894, slot +0x50 = FUN_1004a3d7).
 *
 *  - Highlighter [CONFIRMED @ SIMSPR]: one byte per cell, low nibble = live state, high nibble = state last pushed.
 *    Nibble 1 draws the tool's code (+0x2c, 0x23 for every stock tool), 0xf draws code 0x24 (red), 0 nothing
 *    (getter vt+0x30 0x1004adcd). vt+0x2c 0x1004ad51(pos*, code) sets one cell and grows the dirty rect +0x50,
 *    vt+0x58 0x1004b779(rect6*) pushes the cells whose two nibbles differ (dirty rect included) to the view.
 *  - Zone tools (SIMRCI vtable 0x1004c06c, all 13 zone types): slot +0x54 0x1000b9d2(rect6* = tool+0x40, out) fills the
 *    drag rect through highlighter vt+0x4c with tool+0x128, or 0x24 when tool+0x38/+0x39/+0x3a (refused / no funds).
 *    Zone type at tool+0x124, zone layer interface (vtable 0x1004d1e0) at tool+0x11c, highlighter at tool+0x10.
 *  - Building tools (SIMGEOM vtables 0x10029504/0x100295e4/0x1002968c/0x10029734): slot +0x54 0x1000968b(pos3*, out
 *    rect6*) fills the footprint (width tool+0x116, depth tool+0x117) with 0x23, or 0x24 when refused. Key at tool+0x108:
 *    SIMGEOM DAT_1003092c vt+0x24(key, 0xe075ef51, &attrib), attrib vt+0x50 = agent type id [CONFIRMED @ 0x10006bb8].
 *  - The cost label: FUN_1004a3d7(show, cost, nofunds) formats the cost into the string at view+0x134 only when it differs
 *    from view+0x130 (money formatter SIMSPR FUN_1004ff6a() vt+0x94(0) vt+0x3c(lo, hi, string*)), then posts the
 *    tooltip record view+0x168 (+8 = that string). The wrap writes "<cost text>" + hint into the same string and sets
 *    +0x130 = cost first, so the stock body keeps it. Tools call it before their +0x54 preview (SIMRCI 0x1003f5d4 from
 *    0x1003f91e), so the preview wrap posts the label once more with the new hint.
 *
 * Zone hint (zone types 14 airport / 15 seaport), what the code says about growth (re/analysis/PORTS_AIRPORTS.md 2.3):
 *  - transport within 6 cells per cell = zone layer vt+0x6c({x, z}, 6) = SIMRCI 0x100330b7, the very test the airport
 *    and seaport UpdateCell make (0x10004784 / 0x1002ca1f). It searches transport occupants in the box, so it does not
 *    depend on the cell being zoned. Cells that fail it are drawn red: nothing grows there.
 *  - capacity: every developed airport cell adds 500 to valve 5001, every seaport cell 250 to 8001 (SC3ValveLayer.ini,
 *    stamp SIMRCI 0x1002f5af). The label shows capacity in use now = cap byte of 5000 / 8000 and after the whole drag
 *    develops = demand * 100 / (supply + cells * per-cell), as SIMRCI 0x1000ee50 / 0x10016061 compute it, and the C / I
 *    demand ceiling max - max * cap / 100 (SIMRCI 0x10042e89, max = valve +0x24).
 *  - runway (airport): the runway rule 0x1002b04c needs a rect at least 3x3 with a side >= 5.
 *  - power and water are named in the label, not drawn: whether an empty zoned cell conducts power is open
 *    (POWER_GRID.md, the mask writer), so a per-cell answer before zoning would be a guess.
 *
 * Plop hint (any building with an SC3LandValue.ini row or ancestor row, LAND_VALUE.md): the row (R, C, I signed percent)
 * is added once per footprint cell to 4x4-cell blocks, then the layer averages every block with its 3x3 block
 * neighbourhood (in bounds, in place, x outer, short sums, C division), twice (SIMRCI 0x1001d840, 0x1001d3f1). The hint
 * replays exactly that for the building alone, draws the blocks it changes by at least a quarter of the peak (normal
 * colour where the strongest class goes up, red where it goes down, footprint left to the stock preview) and puts the peak per class in the label.
 * Row lookup as 0x1001d840: exact type in the map SIMRCI DAT_10058688 (node +0x10 key, +0x14 R C I A), else the first
 * row whose type IsAncestor of it (app SIMRCI 0x1003ceec() vt+0x40 = agent type tree, vt+0x24(ancestor, type)).
 *
 * SC3RESIZE_PLACEHINTS=0: nothing. _ZONE=0 / _PLOP=0: one of the two. _LOG=1: one line per hint change. */
static int  g_ph = 1, g_ph_zone = 1, g_ph_plop = 1, g_ph_log;
static BYTE *g_ph_rci, *g_ph_geom, *g_ph_spr;
static DWORD g_ph_zprev_orig, g_ph_bprev_orig[4], g_ph_lbl_orig;
static char  g_ph_hint[400];        /* text appended to the cost label, "" = none (game thread only) */
static int   g_ph_inrepost;         /* ph_repost is calling the label (game thread) */
static int   g_ph_lbl_dirty;      /* the label string holds a hint: force a stock re-format once it is gone */
static char  g_ph_lastlog[400];
static DWORD *g_ph_tipw;            /* SC3U 0x0044314a: the 0x100 px width limit FUN_004430f3 passes to FUN_004431e1 */
#define PH_TIPW 0x300               /* while a hint is shown: one line up to 768 px instead of "..." at 256 */
static void ph_tipw(DWORD w) { if (g_ph_tipw && *g_ph_tipw != w) InterlockedExchange((LONG volatile *)g_ph_tipw, (LONG)w); }

/* ---------------------------------------------------------------------------------------------------- label */
typedef void *(__cdecl *PH_FN0)(void);
static DWORD __fastcall ph_label(BYTE *view, void *edx, DWORD show, LONG cost, DWORD nofunds) {
    DWORD a[3], ra = (DWORD)_ReturnAddress();
    (void)edx;
    /* only the label posts of the two hinted tool families keep a hint: SIMRCI 0x1003f5d4 (zone tools) and SIMGEOM
       0x1002146b (building tools), 77 bytes each, or ph_repost. Any other tool (road, query...) drops it. */
    if (!g_ph_inrepost && !(ra - (DWORD)g_ph_rci - 0x3f5d4 < 0x4d) && !(ra - (DWORD)g_ph_geom - 0x2146b < 0x4d))
        g_ph_hint[0] = 0;
    __try {
        BYTE *s = view + 0x134;
        if (g_ph && g_ph_hint[0] && (show & 0xff)) {
            void *f = ((PH_FN0)(g_ph_spr + 0x4ff6a))();
            char buf[600];
            const char *d;
            DWORD n;
            f = f ? (void *)ho_v(f, 0x94, 1, 0, 0, 0, 0, 0) : NULL;
            if (f) {
                ho_v(f, 0x3c, 3, (DWORD)cost, (DWORD)(cost >> 31), (DWORD)s, 0, 0);
                d = (const char *)ho_v(s, 0x18, 0, 0, 0, 0, 0, 0);
                n = ho_v(s, 0x1c, 0, 0, 0, 0, 0, 0);
                if (!d || n > 100 || IsBadReadPtr(d, n)) n = 0;
                if (n) memcpy(buf, d, n);
                buf[n] = 0;
                lstrcatA(buf, n ? "  |  " : "");
                lstrcpynA(buf + lstrlenA(buf), g_ph_hint, (int)(sizeof(buf) - lstrlenA(buf)));
                ho_v(s, 0x10, 1, (DWORD)buf, 0, 0, 0, 0);
                *(LONG *)(view + 0x130) = cost;
                g_ph_lbl_dirty = 1;
                ph_tipw(PH_TIPW);
            }
        } else if (g_ph_lbl_dirty) {
            *(LONG *)(view + 0x130) = cost + 1;   /* differs: the stock body formats the plain cost again */
            g_ph_lbl_dirty = 0;
            ph_tipw(0x100);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) { }
    a[0] = show; a[1] = (DWORD)cost; a[2] = nofunds;
    return rz_thiscall_ret(view, (void *)g_ph_lbl_orig, a, 3);
}

/* post the label again (after a hint change), with the tool's own cost / no-funds state, as SIMRCI 0x1003f5d4 does */
static void ph_repost(BYTE *tool) {
    void *view = *(void **)(tool + 8);
    if (!view || tool[0x30]) return;
    g_ph_inrepost = 1;
    ho_v(view, 0x50, 3, 1, *(DWORD *)(tool + 0x34), tool[0x39] ? 1 : 0, 0, 0);
    g_ph_inrepost = 0;
}

static void ph_sethint(BYTE *tool, const char *t) {
    if (!lstrcmpA(g_ph_hint, t)) return;
    lstrcpynA(g_ph_hint, t, sizeof(g_ph_hint));
    if (g_ph_log && lstrcmpA(g_ph_lastlog, t)) {
        char one[400];
        int i;
        lstrcpynA(one, t, sizeof(one));
        for (i = 0; one[i]; i++) if (one[i] == '\n') one[i] = '|';
        logf("PLACEHINTS> %s", one[0] ? one : "(no hint)");
        lstrcpynA(g_ph_lastlog, t, sizeof(g_ph_lastlog));
    }
    ph_repost(tool);
}

/* --------------------------------------------------------------------------------------------- highlighter */
static void ph_mark(void *hl, LONG x, LONG z, DWORD code) {
    LONG p[3];
    p[0] = x << 8; p[1] = z << 8; p[2] = 0;
    ho_v(hl, 0x2c, 2, (DWORD)p, code, 0, 0, 0);
}
static void ph_push(void *hl, LONG x0, LONG z0, LONG x1, LONG z1) {
    LONG b[6];
    b[0] = x0 << 8; b[1] = z0 << 8; b[2] = 0; b[3] = x1 << 8; b[4] = z1 << 8; b[5] = 0;
    ho_v(hl, 0x58, 1, (DWORD)b, 0, 0, 0, 0);
}

/* city size in cells: SIMRCI app vt+0x18 = city, vt+0xcc / vt+0xd0 (the base tool ctor 0x1003f48e reads the same) */
static int ph_citysize(LONG *w, LONG *h) {
    void *app = ((PH_FN0)(g_ph_rci + 0x3ceec))(), *city;
    if (!app) return 0;
    city = (void *)ho_v(app, 0x18, 0, 0, 0, 0, 0, 0);
    if (!city) return 0;
    *w = (LONG)ho_v(city, 0xcc, 0, 0, 0, 0, 0, 0);
    *h = (LONG)ho_v(city, 0xd0, 0, 0, 0, 0, 0, 0);
    return *w > 0 && *h > 0 && *w <= 4096 && *h <= 4096;
}

/* ---------------------------------------------------------------------------------------------------- zone */
/* valve vid: cap byte (vt+0x70), max (vt+0x50 getter is the max/min pair: read +0x24 directly) and supply/demand of vid+1 */
static int ph_valves(DWORD vid, LONG *cap, LONG *vmax, LONG *sup, LONG *dem) {
    BYTE *city = rl_city();
    void *L, *vl = NULL, *va = NULL, *vs = NULL;
    int ok = 0;
    if (!city) return 0;
    L = (void *)ho_v(city, 0x1b8, 1, 0x80f1e6d3, 0, 0, 0, 0);
    if (!L) return 0;
    if (!(ho_v(L, 0x00, 2, 0x40a42f1c, (DWORD)&vl, 0, 0, 0) & 0xff)) vl = NULL;
    if (!vl) return 0;
    if ((ho_v(vl, 0x14, 3, vid, 0xf1ec30, (DWORD)&va, 0, 0) & 0xff) && va) {
        *cap = (LONG)(ho_v(va, 0x70, 0, 0, 0, 0, 0, 0) & 0xff);
        *vmax = *(LONG *)((BYTE *)va + 0x24);
        ho_v(va, 0x08, 0, 0, 0, 0, 0, 0);
        ok++;
    }
    if ((ho_v(vl, 0x14, 3, vid + 1, 0xf1ec30, (DWORD)&vs, 0, 0) & 0xff) && vs) {
        *sup = (LONG)ho_v(vs, 0x28, 0, 0, 0, 0, 0, 0);
        *dem = (LONG)ho_v(vs, 0x2c, 0, 0, 0, 0, 0, 0);
        ho_v(vs, 0x08, 0, 0, 0, 0, 0, 0);
        ok++;
    }
    ho_v(vl, 0x08, 0, 0, 0, 0, 0, 0);
    return ok == 2;
}
static LONG ph_cappct(LONG sup, LONG dem) {   /* SIMRCI 0x1000ee50 / 0x10016061 */
    if (dem == 0) return 0;
    if (sup < dem) return 100;
    return (LONG)((__int64)dem * 100 / sup);
}

static DWORD __fastcall ph_zprev(BYTE *tool, void *edx, LONG *rect, DWORD out) {
    DWORD a[2], r;
    (void)edx;
    a[0] = (DWORD)rect; a[1] = out;
    r = rz_thiscall_ret(tool, (void *)g_ph_zprev_orig, a, 2);
    if (!g_ph || !g_ph_zone) return r;
    __try {
        DWORD zt = *(DWORD *)(tool + 0x124);
        void *zl = *(void **)(tool + 0x11c), *hl = *(void **)(tool + 0x10);
        char t[400];
        int es = ho_spanish(), air = zt == 14;
        LONG x0, z0, x1, z1, x, z, w, h, n = 0, bad = 0, cap = 0, vmax = 0, sup = 0, dem = 0, per, add, capn;
        if ((zt != 14 && zt != 15) || !rect || !zl || !hl || tool[0x30]) { ph_sethint(tool, ""); return r; }
        x0 = rect[0] >> 8; z0 = rect[1] >> 8; x1 = rect[3] >> 8; z1 = rect[4] >> 8;
        if (x0 > x1) { x = x0; x0 = x1; x1 = x; }
        if (z0 > z1) { z = z0; z0 = z1; z1 = z; }
        if (!ph_citysize(&w, &h)) return r;
        if (x0 < 0) x0 = 0; if (z0 < 0) z0 = 0; if (x1 > w - 1) x1 = w - 1; if (z1 > h - 1) z1 = h - 1;
        if (x1 < x0 || z1 < z0 || (x1 - x0 + 1) * (z1 - z0 + 1) > 65536) return r;
        {   /* cells the zone tool takes (CanZone 0x1003559f: no occupant, or flora 0x400, or a power line 0x400000 + 0x800),
               and of those the ones with no transport within 6. Red only over a stock preview that is not red already. */
            BYTE *city = rl_city();
            void *om = city ? (void *)ho_v(city, 0x11c, 0, 0, 0, 0, 0, 0) : NULL;
            int mark = !tool[0x38] && !tool[0x39] && !tool[0x3a];
            for (x = x0; x <= x1; x++) for (z = z0; z <= z1; z++) {
                DWORD c[2];
                void *occ = NULL;
                if (om && (ho_v(om, 0x7c, 3, (DWORD)x, (DWORD)z, (DWORD)&occ, 0, 0) & 0xff) && occ) {
                    int take = (ho_v(occ, 0x3c, 1, 0x400, 0, 0, 0, 0) & 0xff) ||
                               ((ho_v(occ, 0x3c, 1, 0x400000, 0, 0, 0, 0) & 0xff) && (ho_v(occ, 0x3c, 1, 0x800, 0, 0, 0, 0) & 0xff));
                    ho_v(occ, 0x08, 0, 0, 0, 0, 0, 0);
                    if (!take) continue;
                }
                c[0] = (DWORD)x; c[1] = (DWORD)z;
                n++;
                if (!(ho_v(zl, 0x6c, 2, (DWORD)c, 6, 0, 0, 0) & 0xff)) { if (mark) ph_mark(hl, x, z, 0x24); bad++; }
            }
            if (bad && mark) ph_push(hl, x0, z0, x1, z1);
        }
        per = air ? 500 : 250;
        add = (n - bad) * per;
        if (!ph_valves(air ? 5000 : 8000, &cap, &vmax, &sup, &dem)) { sup = dem = 0; cap = 0; vmax = 2000; }
        capn = ph_cappct(sup + add, dem);
        {
            int tiny = air && (x1 - x0 + 1 < 3 || z1 - z0 + 1 < 3 || (x1 - x0 + 1 < 5 && z1 - z0 + 1 < 5));
            if (es)
                wsprintfA(t, "%s %ld celdas, %ld sin transporte (rojo)  |  cap. %s +%ld, uso %ld%% a %ld%%  |  "
                             "techo %s %ld a %ld  |  %snecesita energia y agua",
                          air ? "Aeropuerto" : "Puerto", n, bad, air ? "C" : "I", add, cap, capn,
                          air ? "C" : "I", vmax - vmax * cap / 100, vmax - vmax * capn / 100,
                          air ? (tiny ? "pista: 3x5 o mas, " : "") : "muelles: 5 de borde con agua, ");
            else
                wsprintfA(t, "%s %ld cells, %ld without transport (red)  |  cap. %s +%ld, use %ld%% to %ld%%  |  "
                             "%s ceiling %ld to %ld  |  %sneeds power and water",
                          air ? "Airport" : "Seaport", n, bad, air ? "C" : "I", add, cap, capn,
                          air ? "C" : "I", vmax - vmax * cap / 100, vmax - vmax * capn / 100,
                          air ? (tiny ? "runway: 3x5 or more, " : "") : "piers: 5 edge cells on water, ");
        }
        ph_sethint(tool, t);
    } __except (EXCEPTION_EXECUTE_HANDLER) { }
    return r;
}

/* ---------------------------------------------------------------------------------------------------- plop */
typedef struct { DWORD key; signed char v[4]; int found; } PH_ROW;
static void ph_walk(BYTE *node, BYTE *head, void *tree, DWORD type, PH_ROW *best, int depth) {
    if (!node || node == head || depth > 64 || best->found || IsBadReadPtr(node, 0x18)) return;
    if ((ho_v(tree, 0x24, 2, *(DWORD *)(node + 0x10), type, 0, 0, 0) & 0xff)) {
        best->key = *(DWORD *)(node + 0x10); memcpy(best->v, node + 0x14, 4); best->found = 1; return;
    }
    ph_walk(*(BYTE **)(node + 8), head, tree, type, best, depth + 1);
    ph_walk(*(BYTE **)(node + 0xc), head, tree, type, best, depth + 1);
}
static int ph_lvrow(DWORD type, PH_ROW *row) {
    static DWORD ctype = 0xffffffff; static PH_ROW crow;   /* the preview runs every mouse move: one lookup per type */
    BYTE *head = *(BYTE **)(g_ph_rci + 0x58688), *n;
    void *app, *tree;
    if (type == ctype) { *row = crow; return row->found; }
    memset(row, 0, sizeof(*row));
    if (!head || IsBadReadPtr(head, 0x10)) return 0;
    ctype = type;   /* filled below; a row added later for this type would need a new city, as in the game's cache */
    for (n = *(BYTE **)(head + 4); n && n != head && !IsBadReadPtr(n, 0x18); ) {   /* exact key, 0x10029c40 */
        DWORD k = *(DWORD *)(n + 0x10);
        if (k == type) { row->key = k; memcpy(row->v, n + 0x14, 4); row->found = 1; crow = *row; return 1; }
        n = *(BYTE **)(n + (k < type ? 0xc : 8));
    }
    app = ((PH_FN0)(g_ph_rci + 0x3ceec))();
    tree = app ? (void *)ho_v(app, 0x40, 0, 0, 0, 0, 0, 0) : NULL;
    if (!tree) return 0;
    ph_walk(*(BYTE **)(head + 4), head, tree, type, row, 0);
    crow = *row;
    return row->found;
}

#define PH_WB 24   /* replay window in blocks (footprint blocks + 3 each side fits for footprints up to 64 cells) */
static DWORD __fastcall ph_bprev(BYTE *tool, void *edx, LONG *pos, LONG *out, int vi) {
    DWORD a[2], r;
    a[0] = (DWORD)pos; a[1] = (DWORD)out;
    r = rz_thiscall_ret(tool, (void *)g_ph_bprev_orig[vi], a, 2);
    (void)edx;
    if (!g_ph || !g_ph_plop) return r;
    __try {
        static short m[3][PH_WB][PH_WB];
        void *hl = *(void **)(tool + 0x10), *attr = NULL, *db = *(void **)(g_ph_geom + 0x3092c);
        DWORD type;
        PH_ROW row;
        char t[400];
        LONG w, h, fx0, fz0, fx1, fz1, bx0, bz0, nbx, nbz, bw, bh, i, j, k, x, z, pass, peak[3], best = -1, bestabs = 0;
        LONG reach = 0, thr = 1;   /* marked blocks: at least a quarter of the peak of the strongest class */
        static const char cls[3] = { 'R', 'C', 'I' };
        if (!pos || !hl || !db || tool[0x30]) { ph_sethint(tool, ""); return r; }
        if (!(ho_v(db, 0x24, 3, (DWORD)(tool + 0x108), 0xe075ef51, (DWORD)&attr, 0, 0) & 0xff) || !attr) {
            ph_sethint(tool, ""); return r; }
        type = ho_v(attr, 0x50, 0, 0, 0, 0, 0, 0);
        ho_v(attr, 0x08, 0, 0, 0, 0, 0, 0);
        if (!ph_lvrow(type, &row) || (!row.v[0] && !row.v[1] && !row.v[2]) || !ph_citysize(&w, &h)) {
            ph_sethint(tool, ""); return r; }
        fx0 = pos[0] >> 8; fz0 = pos[1] >> 8;
        fx1 = fx0 + tool[0x116]; fz1 = fz0 + tool[0x117];   /* width - 1 / depth - 1: rect end = start + w * 0x100, inclusive (0x1000968b) */
        bw = w >> 2; bh = h >> 2;
        bx0 = (fx0 >> 2) - 3; bz0 = (fz0 >> 2) - 3;
        nbx = (fx1 >> 2) + 3 - bx0 + 1; nbz = (fz1 >> 2) + 3 - bz0 + 1;
        if (nbx > PH_WB || nbz > PH_WB) { ph_sethint(tool, ""); return r; }
        memset(m, 0, sizeof(m));
        for (x = fx0; x <= fx1; x++) for (z = fz0; z <= fz1; z++)   /* the stamp, once per footprint cell */
            for (k = 0; k < 3; k++) m[k][(x >> 2) - bx0][(z >> 2) - bz0] += row.v[k];
        for (pass = 0; pass < 2; pass++)                             /* two in-place 3x3 block averages, x outer */
            for (i = 0; i < nbx; i++) for (j = 0; j < nbz; j++) {
                LONG gx = bx0 + i, gz = bz0 + j, s[3] = { 0, 0, 0 }, c = 0, di, dj;
                if (gx < 0 || gz < 0 || gx >= bw || gz >= bh) continue;
                for (di = -1; di <= 1; di++) for (dj = -1; dj <= 1; dj++) {
                    LONG ux = gx + di, uz = gz + dj;
                    if (ux < 0 || uz < 0 || ux >= bw || uz >= bh) continue;
                    c++;
                    if (i + di < 0 || j + dj < 0 || i + di >= nbx || j + dj >= nbz) continue;   /* outside: 0 delta */
                    for (k = 0; k < 3; k++) s[k] += m[k][i + di][j + dj];
                }
                for (k = 0; k < 3; k++) m[k][i][j] = (short)((short)s[k] / (short)c);
            }
        for (k = 0; k < 3; k++) {
            peak[k] = 0;
            for (i = 0; i < nbx; i++) for (j = 0; j < nbz; j++) {
                LONG v = m[k][i][j];
                if ((v < 0 ? -v : v) > (peak[k] < 0 ? -peak[k] : peak[k])) peak[k] = v;
            }
            if ((peak[k] < 0 ? -peak[k] : peak[k]) > bestabs) { bestabs = peak[k] < 0 ? -peak[k] : peak[k]; best = k; }
        }
        if (best >= 0) {   /* halo: the blocks of the strongest class changed by at least a quarter of its peak */
            LONG hx0 = 0x7fffffff, hz0 = 0x7fffffff, hx1 = -1, hz1 = -1;
            thr = (bestabs + 3) / 4; if (thr < 1) thr = 1;
            for (i = 0; i < nbx; i++) for (j = 0; j < nbz; j++) {
                LONG v = m[best][i][j], gx = bx0 + i, gz = bz0 + j, cx, cz;
                if ((v < 0 ? -v : v) < thr || gx < 0 || gz < 0 || gx >= bw || gz >= bh) continue;
                for (cx = gx * 4; cx < gx * 4 + 4; cx++) for (cz = gz * 4; cz < gz * 4 + 4; cz++) {
                    LONG d;
                    if (cx >= fx0 && cx <= fx1 && cz >= fz0 && cz <= fz1) continue;   /* footprint: the stock preview */
                    ph_mark(hl, cx, cz, v > 0 ? 0x23 : 0x24);
                    d = cx < fx0 ? fx0 - cx : cx > fx1 ? cx - fx1 : 0;
                    if (cz < fz0 && fz0 - cz > d) d = fz0 - cz;
                    if (cz > fz1 && cz - fz1 > d) d = cz - fz1;
                    if (d > reach) reach = d;
                    if (cx < hx0) hx0 = cx; if (cz < hz0) hz0 = cz; if (cx > hx1) hx1 = cx; if (cz > hz1) hz1 = cz;
                }
            }
            if (hx1 >= 0) ph_push(hl, hx0, hz0, hx1, hz1);
        }
        if (best < 0) { ph_sethint(tool, ""); return r; }
        {
            char part[3][24];
            for (k = 0; k < 3; k++) wsprintfA(part[k], "%c %s%ld%%", cls[k], peak[k] > 0 ? "+" : "", peak[k]);
            if (ho_spanish())
                wsprintfA(t, "Valor del suelo %s  %s  %s  |  %s %c %s%ld%% o mas hasta %ld celdas", part[0], part[1], part[2],
                          peak[best] > 0 ? "marcado" : "en rojo", cls[best], peak[best] > 0 ? "+" : "-", thr, reach);
            else
                wsprintfA(t, "Land value %s  %s  %s  |  %s %c %s%ld%% or more up to %ld cells", part[0], part[1], part[2],
                          peak[best] > 0 ? "marked" : "red", cls[best], peak[best] > 0 ? "+" : "-", thr, reach);
        }
        if (g_ph_log && lstrcmpA(g_ph_hint, t))
            logf("PLACEHINTS> plop type %lu row %lu (R %d C %d I %d) footprint %ldx%ld", type, row.key, row.v[0],
                 row.v[1], row.v[2], fx1 - fx0 + 1, fz1 - fz0 + 1);
        ph_sethint(tool, t);
    } __except (EXCEPTION_EXECUTE_HANDLER) { }
    return r;
}
static DWORD __fastcall ph_bprev0(BYTE *t, void *e, LONG *p, LONG *o) { return ph_bprev(t, e, p, o, 0); }
static DWORD __fastcall ph_bprev1(BYTE *t, void *e, LONG *p, LONG *o) { return ph_bprev(t, e, p, o, 1); }
static DWORD __fastcall ph_bprev2(BYTE *t, void *e, LONG *p, LONG *o) { return ph_bprev(t, e, p, o, 2); }
static DWORD __fastcall ph_bprev3(BYTE *t, void *e, LONG *p, LONG *o) { return ph_bprev(t, e, p, o, 3); }

/* ------------------------------------------------------------------------------------------------- install */
static void ph_install(void) {
    static const DWORD bvt[4] = { 0x29504, 0x295e4, 0x2968c, 0x29734 };
    static void *const bfn[4] = { (void *)ph_bprev0, (void *)ph_bprev1, (void *)ph_bprev2, (void *)ph_bprev3 };
    char v[8];
    HMODULE rci = NULL, geom = NULL, spr = NULL;
    DWORD *slot;
    int st = 0, i, nb = 0;
    if (GetEnvironmentVariableA("SC3RESIZE_PLACEHINTS", v, sizeof(v))) g_ph = atoi(v);
    if (GetEnvironmentVariableA("SC3RESIZE_PLACEHINTS_ZONE", v, sizeof(v))) g_ph_zone = atoi(v);
    if (GetEnvironmentVariableA("SC3RESIZE_PLACEHINTS_PLOP", v, sizeof(v))) g_ph_plop = atoi(v);
    if (GetEnvironmentVariableA("SC3RESIZE_PLACEHINTS_LOG", v, sizeof(v))) g_ph_log = atoi(v);
    if (!g_ph) { logf("PLACEHINTS> off (SC3RESIZE_PLACEHINTS=0)"); return; }
    while (st++ < 300 && !((rci = GetModuleHandleA("SIMRCI.DLL")) && (geom = GetModuleHandleA("SIMGEOM.DLL")) &&
                           (spr = GetModuleHandleA("SIMSPR.DLL")))) Sleep(100);
    if (!rci || !geom || !spr) { logf("PLACEHINTS> SIMRCI / SIMGEOM / SIMSPR not loaded: off"); g_ph = 0; return; }
    g_ph_rci = (BYTE *)rci; g_ph_geom = (BYTE *)geom; g_ph_spr = (BYTE *)spr;
    slot = (DWORD *)(g_ph_spr + 0x67894 + 0x50);
    if (*slot != (DWORD)g_ph_spr + 0x4a3d7) { logf("PLACEHINTS> view label slot is 0x%08lX, not shipped: off", *slot); g_ph = 0; return; }
    rl_patch_slot(slot, (void *)ph_label, &g_ph_lbl_orig);
    {   BYTE *exe = (BYTE *)GetModuleHandleA(NULL), *push = exe + 0x43149;   /* push 0x100 before call FUN_004431e1 */
        DWORD old;
        if (push[0] == 0x68 && *(DWORD *)(push + 1) == 0x100 && VirtualProtect(push + 1, 4, PAGE_EXECUTE_READWRITE, &old))
            g_ph_tipw = (DWORD *)(push + 1);
        else logf("PLACEHINTS> tooltip width push at SC3U 0x00443149 not shipped: hints stay cut at 256 px");
        /* the tooltip raster is made 0x100 px wide (SC3U FUN_00442e88, push 0x100 at 0x00442f16, raster vt+0xc(w, h)):
           room for PH_TIPW. The window still sizes itself to the text, so stock labels look the same. */
        push = exe + 0x42f16;
        if (push[0] == 0x68 && *(DWORD *)(push + 1) == 0x100 && VirtualProtect(push + 1, 4, PAGE_EXECUTE_READWRITE, &old))
            *(DWORD *)(push + 1) = PH_TIPW;
        else logf("PLACEHINTS> tooltip raster push at SC3U 0x00442f16 not shipped: hints stay cut at 256 px"); }
    if (g_ph_zone) {
        slot = (DWORD *)(g_ph_rci + 0x4c06c + 0x54);
        if (*slot == (DWORD)g_ph_rci + 0xb9d2) rl_patch_slot(slot, (void *)ph_zprev, &g_ph_zprev_orig);
        else { logf("PLACEHINTS> zone tool preview slot is 0x%08lX, not shipped: zone hint off", *slot); g_ph_zone = 0; }
    }
    if (g_ph_plop) {
        for (i = 0; i < 4; i++) {
            slot = (DWORD *)(g_ph_geom + bvt[i] + 0x54);
            if (*slot == (DWORD)g_ph_geom + 0x968b) { rl_patch_slot(slot, bfn[i], &g_ph_bprev_orig[i]); nb++; }
        }
        if (!nb) { logf("PLACEHINTS> no building tool preview slot is shipped: plop hint off"); g_ph_plop = 0; }
    }
    logf("PLACEHINTS> on: cost label (SIMSPR view +0x50)%s%s", g_ph_zone ? ", airport/seaport zone drag (SIMRCI +0x54)" : "",
         g_ph_plop ? ", land value halo for plopped buildings (SIMGEOM +0x54)" : "");
}
static DWORD WINAPI ph_thread(LPVOID p) { (void)p; ph_install(); return 0; }
