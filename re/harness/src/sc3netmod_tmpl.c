/* sc3netmod_tmpl.c - the TMPL block of sc3netmod.dll (task multitile, 2026-10-13). #included by sc3netmod.c after
 * the NETRAMP block, so it shares the variant table (g_base), the patch helpers and the log. Evidence and the
 * owner guide: re/analysis/MULTITILE.md, verify/multitile/.
 *
 * TEMPLATES (SC3NETMOD_TMPL=0 turns it off). A template is a fixed block of network pieces that the player places in
 * one click (netpack manifest section `templates`, compiled by netpack_templates.py into `tmpl` lines of
 * <root>\mods\netmod\tables\<package>.txt). The game's own highway On-ramp TOOL is borrowed while template mode is on:
 *   - hover: the selection object's hover (vtable 0x1002c1b0 slot 3 = 0x1002c1bc, FUN_10009d20) is wrapped. In
 *     template mode it clears the selection and its highlights the way FUN_10009d20 starts (highlighter +0x50
 *     vt+0x40(0), point vector erase FUN_100041e4), adds every template cell with the game's add-point FUN_10004754
 *     (which also highlights the cell, highlighter vt+0x2c), redraws the union of the old and new boxes
 *     (highlighter vt+0x58) and sends the selection's change message 0x62c0838e, as FUN_10009d20 ends.
 *   - cost preview: manager vt+0x90 (FUN_100145aa) is wrapped: in template mode the cost is the template's.
 *   - click: manager vt+0xac (FUN_1000abde, the On-ramp build) is wrapped: in template mode the template is
 *     checked (in map, flat, not water, each cell empty, flora, or a non-Protected piece of the cell's network:
 *     the rule of FUN_10009613), the funds checked (manager +0x38 vt+0x10), every cell written with the game's own
 *     piece writer FUN_10008919 (the On-ramp build's, which removes the old occupant, sets the height, inserts the
 *     piece and the side table), the money spent (+0x38 vt+0x14(cost), as FUN_1000abde does at 0x1000bcd2), and the
 *     footprint re-tiled with the rectangle retile FUN_100151f1 (manager vt+0xb0, the handler of GZ message
 *     0x637c0dab) so the neighbours connect. The template pieces are in their network's Protected list (netpack), so
 *     that retile and every later one keep them (FUN_1001547b, TILER_SIM.md 3).
 * Keys (game window subclass): T cycles the templates (off -> 1 -> 2 -> .. -> off) and selects the On-ramp tool
 * (menu command 0x10004302) when a template is chosen; R turns it a quarter. Both only without Ctrl / Alt.
 * Removal: netpack puts the template pieces of a package in one Collapse.txt group; g_tmpl_keep stops the INHERIT
 * block from mapping those ids to their base in the Collapse walk (sc3netmod_bridge.c), so the walk sees the group.
 */

#define TM_MAXT    32
#define TM_MAXCELL 256
#define TM_MAXEDGE 64

typedef struct { short x, z; BYTE net, st; WORD id; } TmCell;
typedef struct { short x, z; BYTE dir, net, need; } TmEdge;
typedef struct { int w, h, nc, ne; TmCell c[TM_MAXCELL]; TmEdge e[TM_MAXEDGE]; } TmOri;
typedef struct { char name[64]; int nori, cost, flags, bad; TmOri o[4]; } Tmpl;

static Tmpl *g_tm;
static int g_ntm;
static volatile LONG g_tm_sel = -1, g_tm_rot;
static BYTE *g_tm_m;                                  /* SIMNTWRK base */
static DWORD g_tm_orig_hover, g_tm_orig_cost, g_tm_orig_build;
static int g_tm_hx = 0x7fffffff, g_tm_hz;             /* anchor of the last template hover */
static volatile LONG g_tm_n_hover, g_tm_n_place, g_tm_n_refused;
static HWND g_tm_hwnd;
static WNDPROC g_tm_oldproc;

/* SIMNTWRK calls, __thiscall emulated with __fastcall (ecx = this, edx unused) */
typedef void (__fastcall *PFN_AddPt)(void *sel, void *edx, int *pt, int dedupe);                 /* FUN_10004754 ret 8 */
typedef void *(__fastcall *PFN_Erase)(void *vec, void *edx, void *first, void *last);            /* FUN_100041e4 ret 8 */
typedef void (__fastcall *PFN_Put)(void *mgr, void *edx, void *layer, int *pos, DWORD idst, int h, int p5, int p6);
                                                                                                 /* FUN_10008919 ret 0x18 */
typedef void (__fastcall *PFN_Retile)(void *mgr, void *edx, int *rect, DWORD mask);              /* FUN_100151f1 ret 8 */
typedef char (__fastcall *PFN_Pos)(void *mgr, void *edx, int *pos);                              /* FUN_10016ccd / 6d69 ret 4 */
typedef char (__stdcall *PFN_Prot)(DWORD net, DWORD id);                                         /* FUN_1001a7f7 ret 8 */
typedef DWORD (__stdcall *PFN_Id)(void *occ);                                                    /* FUN_1001a93d ret 4 */
typedef char (__fastcall *PFN_Hover)(void *sel, void *edx, DWORD a1, int *cell, DWORD a3, DWORD a4);
typedef char (__fastcall *PFN_Cost)(void *mgr, void *edx, void *sel, DWORD *cost);
typedef char (__fastcall *PFN_Build)(void *mgr, void *edx, void *sel, DWORD *cost, DWORD a3, DWORD a4);
typedef void (__fastcall *PFN_Box)(int *box);                                                 /* FUN_10005f83, ecx only */
typedef void (__fastcall *PFN_V1)(void *obj, void *edx, DWORD a);
typedef void (__fastcall *PFN_V2)(void *obj, void *edx, DWORD a, DWORD b);
typedef char (__fastcall *PFN_Get)(void *obj, void *edx, int *pos, void **out);
typedef char (__fastcall *PFN_B0)(void *obj);
typedef char (__fastcall *PFN_Pred)(void *obj, void *edx, DWORD net, void *occ);
typedef unsigned __int64 (__fastcall *PFN_Funds)(void *obj);

#define VT(o, off) (*(DWORD *)(*(BYTE **)(o) + (off)))

/* ---------------------------------------------------------------- table lines */
static void tm_line(const char *path, char *p) {
    Tmpl *t = g_ntm ? &g_tm[g_ntm - 1] : NULL;
    TmOri *o;
    int a[6];
    if (!strncmp(p, "tmpl ", 5)) {
        char name[64];
        if (g_ntm >= TM_MAXT) { logf("### tmpl: %s: more than %d templates - rest ignored", path, TM_MAXT); return; }
        t = &g_tm[g_ntm];
        ZeroMemory(t, sizeof(*t));
        if (sscanf(p, "tmpl %63s %d %d %d", name, &a[0], &a[1], &a[2]) != 4 || a[0] < 1 || a[0] > 4 || a[1] < 0) {
            logf("### tmpl: %s: bad line '%s'", path, p); return;
        }
        lstrcpynA(t->name, name, sizeof(t->name));
        t->cost = a[1]; t->flags = a[2]; t->nori = 0;
        g_ntm++;
        return;
    }
    if (!t) return;
    if (!strncmp(p, "tori ", 5)) {
        if (sscanf(p, "tori %d %d %d", &a[0], &a[1], &a[2]) != 3 || a[0] != t->nori || a[0] > 3 || a[1] < 1 ||
            a[1] > 16 || a[2] < 1 || a[2] > 16) { logf("### tmpl: %s: bad line '%s'", path, p); t->bad = 1; return; }
        o = &t->o[t->nori++];
        o->w = a[1]; o->h = a[2]; o->nc = o->ne = 0;
        return;
    }
    if (!t->nori) { t->bad = 1; return; }
    o = &t->o[t->nori - 1];
    if (!strncmp(p, "tcel ", 5)) {
        if (sscanf(p, "tcel %d %d %d %d %d", &a[0], &a[1], &a[2], &a[3], &a[4]) != 5 || a[0] < 0 || a[0] >= o->w ||
            a[1] < 0 || a[1] >= o->h || a[2] < 1 || a[2] > 6 || a[3] < 1 || a[3] > 0xffff || a[4] < 0 || a[4] > 3 ||
            o->nc >= TM_MAXCELL) { logf("### tmpl: %s: bad line '%s'", path, p); t->bad = 1; return; }
        o->c[o->nc].x = (short)a[0]; o->c[o->nc].z = (short)a[1]; o->c[o->nc].net = (BYTE)a[2];
        o->c[o->nc].id = (WORD)a[3]; o->c[o->nc].st = (BYTE)a[4];
        o->nc++;
        g_tmpl_keep[a[3]] = 1;
    } else if (!strncmp(p, "tedg ", 5)) {
        if (sscanf(p, "tedg %d %d %d %d %d", &a[0], &a[1], &a[2], &a[3], &a[4]) != 5 || o->ne >= TM_MAXEDGE) {
            logf("### tmpl: %s: bad line '%s'", path, p); t->bad = 1; return;
        }
        o->e[o->ne].x = (short)a[0]; o->e[o->ne].z = (short)a[1]; o->e[o->ne].dir = (BYTE)a[2];
        o->e[o->ne].net = (BYTE)a[3]; o->e[o->ne].need = (BYTE)a[4];
        o->ne++;
    } else if (!strncmp(p, "tend", 4)) {
        if (t->bad || !t->nori || !t->o[0].nc) {
            logf("### tmpl: %s: template %s dropped (bad lines)", path, t->name);
            g_ntm--;
            return;
        }
        logf("tmpl: %s: template %s, %d orientation(s), %d cell(s), cost %d, flags %d", path, t->name, t->nori,
             t->o[0].nc, t->cost, t->flags);
    }
}

static void tm_file(const char *path) {
    char line[256];
    FILE *f = fopen(path, "r");
    if (!f) return;
    while (fgets(line, sizeof(line), f)) {
        char *e = line + strlen(line), *p = line;
        while (e > line && (e[-1] == '\r' || e[-1] == '\n')) *--e = 0;
        while (*p == ' ' || *p == '\t') p++;
        if (p[0] == 't' && (!strncmp(p, "tmpl ", 5) || !strncmp(p, "tori ", 5) || !strncmp(p, "tcel ", 5) ||
                            !strncmp(p, "tedg ", 5) || !strncmp(p, "tend", 4)))
            tm_line(path, p);
    }
    fclose(f);
}

/* ---------------------------------------------------------------- the game's objects */
static int tm_active(void) {
    return g_tm_sel >= 0 && g_tm_sel < g_ntm;
}

static TmOri *tm_ori(Tmpl **pt) {
    Tmpl *t = &g_tm[g_tm_sel];
    if (pt) *pt = t;
    return &t->o[g_tm_rot % t->nori];
}

static void *tm_layer(BYTE *mgr, int net) {          /* FUN_10012609: +0x3c surface (ROAD RAIL POWR HWAY), +0x40 PIPE, +0x44 SUBW */
    return *(void **)(mgr + (net == 5 ? 0x40 : net == 6 ? 0x44 : 0x3c));
}

static const DWORD g_tm_mask[7] = { 0, 3, 4, 0x20, 3, 8, 0x10 };   /* FUN_100151f1 mask per netType (TILER_SIM.md 1) */

/* the template at anchor (X, Z): 0 = ok, else a reason (logged) */
static const char *tm_check(BYTE *mgr, Tmpl *t, TmOri *o, int X, int Z, int *cx, int *cz) {
    int k, W = (*(int *)(mgr + 0x5c) >> 8) + 1, H = (*(int *)(mgr + 0x60) >> 8) + 1;
    for (k = 0; k < o->nc; k++) {
        int pos[3], x = X + o->c[k].x, z = Z + o->c[k].z;
        void *lay, *occ = NULL;
        *cx = x; *cz = z;
        if (x < 0 || z < 0 || x >= W || z >= H) return "off the map";
        pos[0] = x << 8; pos[1] = z << 8; pos[2] = 0;
        if ((t->flags & 1) && !((PFN_Pos)(g_tm_m + 0x16ccd))(mgr, 0, pos)) return "not flat";
        if ((t->flags & 2) && ((PFN_Pos)(g_tm_m + 0x16d69))(mgr, 0, pos)) return "water";
        lay = tm_layer(mgr, o->c[k].net);
        if (((PFN_Get)VT(lay, 0x78))(lay, 0, pos, &occ) && occ) {
            /* FUN_10009613: an occupant of major type 5 (vt+0x54), or one the manager's network test vt+0x14c
               accepts that is not Protected (FUN_1001a7f7) */
            char ok = ((PFN_B0)VT(occ, 0x54))(occ) == 5;
            if (!ok && ((PFN_Pred)VT(mgr, 0x14c))(mgr, 0, o->c[k].net, occ))
                ok = !((PFN_Prot)(g_tm_m + 0x1a7f7))(o->c[k].net, ((PFN_Id)(g_tm_m + 0x1a93d))(occ) & 0xffff);
            ((PFN_B0)VT(occ, 8))(occ);
            if (!ok) return "occupied (building, other network or protected piece)";
        }
    }
    for (k = 0; k < o->ne; k++) {                      /* required exits: the cell outside holds that network */
        static const int dx[4] = { -1, 0, 1, 0 }, dz[4] = { 0, -1, 0, 1 };
        int pos[3], x, z;
        void *lay, *occ = NULL;
        char ok = 0;
        if (!o->e[k].need) continue;
        x = X + o->e[k].x + dx[o->e[k].dir & 3]; z = Z + o->e[k].z + dz[o->e[k].dir & 3];
        *cx = x; *cz = z;
        if (x < 0 || z < 0 || x >= W || z >= H) return "required exit off the map";
        pos[0] = x << 8; pos[1] = z << 8; pos[2] = 0;
        lay = tm_layer(mgr, o->e[k].net);
        if (((PFN_Get)VT(lay, 0x78))(lay, 0, pos, &occ) && occ) {
            ok = ((PFN_Pred)VT(mgr, 0x14c))(mgr, 0, o->e[k].net, occ);
            ((PFN_B0)VT(occ, 8))(occ);
        }
        if (!ok) return "required exit has no network to connect to";
    }
    return NULL;
}

/* ---------------------------------------------------------------- hover (selection vtable slot) */
static char __fastcall tm_hover(BYTE *sel, void *edx, DWORD a1, int *cell, DWORD a3, DWORD a4) {
    Tmpl *t;
    TmOri *o;
    int k, X, Z, box[6], un[6], *old = (int *)(sel + 0x78);
    void *hl;
    if (!tm_active() || !cell) return ((PFN_Hover)g_tm_orig_hover)(sel, edx, a1, cell, a3, a4);
    o = tm_ori(&t);
    X = (cell[0] >> 8) - (o->w - 1) / 2;
    Z = (cell[1] >> 8) - (o->h - 1) / 2;
    hl = *(void **)(sel + 0x50);
    ((PFN_Box)(g_tm_m + 0x5f83))(old);                            /* FUN_10005f83: normalise the old box */
    ((PFN_V1)VT(hl, 0x40))(hl, 0, 0);
    ((PFN_Erase)(g_tm_m + 0x41e4))(sel + 8, 0, *(void **)(sel + 8), *(void **)(sel + 0xc));
    *(DWORD *)(g_tm_m + 0x322a4) = 0;                             /* DAT_100322a4, the add-point cap (NET_RAMPS 1.2) */
    for (k = 0; k < o->nc; k++) {
        int pt[3];
        pt[0] = (X + o->c[k].x) << 8; pt[1] = (Z + o->c[k].z) << 8; pt[2] = cell[2];
        ((PFN_AddPt)(g_tm_m + 0x4754))(sel, 0, pt, 0);      /* dedupe 0 = colour 0x23, as FUN_10009d20's found cells */
    }
    box[0] = X << 8; box[1] = Z << 8; box[2] = 0x7fffffff;
    box[3] = (X + o->w - 1) << 8; box[4] = (Z + o->h - 1) << 8; box[5] = 0x7fffffff;
    un[0] = min(old[0], box[0]); un[1] = min(old[1], box[1]); un[2] = 0x7fffffff;
    un[3] = max(old[3], box[3]); un[4] = max(old[4], box[4]); un[5] = 0x7fffffff;
    ((PFN_V1)VT(hl, 0x58))(hl, 0, (DWORD)un);
    CopyMemory(old, box, sizeof(box));
    ((PFN_V2)VT(sel, 0))(sel, 0, 0x62c0838e, a3);
    if (X != g_tm_hx || Z != g_tm_hz) {
        g_tm_hx = X; g_tm_hz = Z;
        InterlockedIncrement(&g_tm_n_hover);
    }
    return 1;
}

static char __fastcall tm_cost(BYTE *mgr, void *edx, void *sel, DWORD *cost) {
    Tmpl *t;
    char r = ((PFN_Cost)g_tm_orig_cost)(mgr, edx, sel, cost);   /* stock first (points x price), so tools that
                                                                     watch FUN_100145aa still see the selection */
    if (!tm_active()) return r;
    tm_ori(&t);
    if (cost) *cost = (DWORD)t->cost;
    return 1;
}

/* the click: FUN_1000abde's slot. sel's first point is the template's first cell. */
static char __fastcall tm_build(BYTE *mgr, void *edx, BYTE *sel, DWORD *cost, DWORD a3, DWORD a4) {
    Tmpl *t;
    TmOri *o;
    int k, X, Z, cx = 0, cz = 0, rect[6];
    DWORD mask = 0;
    const char *why;
    void *bud;
    unsigned __int64 funds;
    if (!tm_active()) return ((PFN_Build)g_tm_orig_build)(mgr, edx, sel, cost, a3, a4);
    o = tm_ori(&t);
    if (g_tm_hx == 0x7fffffff) { logf("tmpl: click before any template hover - nothing placed"); return 0; }
    /* the anchor of the selection the hover generator just made: the tool's mouse-up (FUN_10025b3c) runs vt+0x54
       (FUN_1000f760 -> selection vt+0xc = tm_hover) and then the build (vt+0x48 -> FUN_1000f9b7 -> here). `sel` is
       the point-list interface (object + 4, QI 0x62c0838e), not the object tm_hover receives. */
    X = g_tm_hx; Z = g_tm_hz;
    (void)sel;
    if (cost) *cost = 0;
    why = tm_check(mgr, t, o, X, Z, &cx, &cz);
    if (why) {
        InterlockedIncrement(&g_tm_n_refused);
        logf("tmpl: %s rot %ld at (%d,%d) REFUSED: cell (%d,%d) %s", t->name, g_tm_rot % t->nori, X, Z, cx, cz, why);
        return 0;
    }
    bud = *(void **)(mgr + 0x38);
    funds = ((PFN_Funds)VT(bud, 0x10))(bud);
    if ((__int64)funds < 0x100000000LL && ((__int64)funds < 0 || (DWORD)funds < (DWORD)t->cost)) {
                                                       /* the test FUN_1000abde makes at 0x1000ad3e..ad4d */
        InterlockedIncrement(&g_tm_n_refused);
        logf("tmpl: %s at (%d,%d) REFUSED: funds %lu < cost %d", t->name, X, Z, (DWORD)funds, t->cost);
        return 0;
    }
    for (k = 0; k < o->nc; k++) {
        int pos[3];
        pos[0] = (X + o->c[k].x) << 8; pos[1] = (Z + o->c[k].z) << 8; pos[2] = 0;
        ((PFN_Put)(g_tm_m + 0x8919))(mgr, 0, tm_layer(mgr, o->c[k].net), pos, ((DWORD)o->c[k].id << 8) | o->c[k].st,
                                     -1, 8, 0);
        mask |= g_tm_mask[o->c[k].net];
    }
    ((PFN_V1)VT(bud, 0x14))(bud, 0, (DWORD)t->cost);
    if (cost) *cost = (DWORD)t->cost;
    rect[0] = X << 8; rect[1] = Z << 8; rect[2] = 0;
    rect[3] = (X + o->w - 1) << 8; rect[4] = (Z + o->h - 1) << 8; rect[5] = 0;
    if (!env_off("SC3NETMOD_TMPL_RETILE")) ((PFN_Retile)VT(mgr, 0xb0))(mgr, 0, rect, mask);
    InterlockedIncrement(&g_tm_n_place);
    logf("tmpl: %s rot %ld PLACED at (%d,%d) %dx%d, %d cell(s), cost %d, funds %lu -> %lu, retile mask 0x%lx", t->name,
         g_tm_rot % t->nori, X, Z, o->w, o->h, o->nc, t->cost, (DWORD)funds, (DWORD)((PFN_Funds)VT(bud, 0x10))(bud), mask);
    return 1;
}

/* ---------------------------------------------------------------- keys */
static void tm_post_cmd(DWORD cmd) {       /* GZ message {0x025F0A91, cmd, 0, 0} to the msg server (np_drive.py) */
    BYTE *exe = (BYTE *)GetModuleHandleA(NULL);
    void *fw, *srv = NULL;
    DWORD msg[4];
    __try {
        fw = *(void **)(exe + 0xFAB74);
        if (!fw) return;
        ((char (__fastcall *)(void *, void *, DWORD, DWORD, void **))VT(fw, 0x10))(fw, 0, 0x64063387, 0xC1085722, &srv);
        if (!srv) return;
        msg[0] = 0x025F0A91; msg[1] = cmd; msg[2] = 0; msg[3] = 0;
        ((char (__fastcall *)(void *, void *, DWORD *, int))VT(srv, 0x10))(srv, 0, msg, 0);
    } __except (EXCEPTION_EXECUTE_HANDLER) { logf("### tmpl: menu command 0x%08lX faulted", cmd); }
}

static LRESULT CALLBACK tm_wndproc(HWND h, UINT m, WPARAM wp, LPARAM lp) {
    if ((m == WM_KEYDOWN || m == WM_KEYUP) && (wp == 'T' || (wp == 'R' && tm_active())) &&
        GetKeyState(VK_CONTROL) >= 0 && GetKeyState(VK_MENU) >= 0) {
        if (m == WM_KEYDOWN && !(lp & 0x40000000)) {
            if (wp == 'T') {
                LONG s = g_tm_sel + 1;
                if (s >= g_ntm) s = -1;
                InterlockedExchange(&g_tm_sel, s);
                InterlockedExchange(&g_tm_rot, 0);
                g_tm_hx = 0x7fffffff;
                if (s >= 0) {
                    logf("tmpl: key T -> template %ld %s (On-ramp tool selected)", s, g_tm[s].name);
                    tm_post_cmd(0x10004302);
                } else logf("tmpl: key T -> template mode OFF (On-ramp tool is stock again)");
            } else {
                InterlockedExchange(&g_tm_rot, (g_tm_rot + 1) % g_tm[g_tm_sel].nori);
                logf("tmpl: key R -> %s orientation %ld", g_tm[g_tm_sel].name, g_tm_rot);
            }
        }
        return 0;
    }
    return CallWindowProcA(g_tm_oldproc, h, m, wp, lp);
}

static BOOL CALLBACK tm_enum(HWND h, LPARAM p) {
    DWORD pid = 0;
    char cls[64];
    GetWindowThreadProcessId(h, &pid);
    if (pid != GetCurrentProcessId() || !IsWindowVisible(h) || !GetClassNameA(h, cls, sizeof(cls))) return TRUE;
    if (GetWindow(h, GW_OWNER)) return TRUE;
    *(HWND *)p = h;
    return FALSE;
}

/* ---------------------------------------------------------------- install */
static int tmpl_install(BYTE *m) {
    char path[MAX_PATH], pat[MAX_PATH];
    WIN32_FIND_DATAA fd;
    HANDLE hf;
    int k, j, cnt = 0, ok = 0;
    static char names[64][MAX_PATH];
    DWORD *s_hover = (DWORD *)(m + 0x2c1bc), *s_cost = (DWORD *)(m + 0x2c7bc + 0x90),
          *s_build = (DWORD *)(m + 0x2c7bc + 0xac), v;
    if (env_off("SC3NETMOD_TMPL")) { logf("tmpl: off (SC3NETMOD_TMPL=0)"); return 0; }
    g_tm = (Tmpl *)VirtualAlloc(NULL, sizeof(Tmpl) * TM_MAXT, MEM_COMMIT, PAGE_READWRITE);
    if (!g_tm) return 0;
    if (GetEnvironmentVariableA("SC3NETMOD_TABLE", path, sizeof(path))) tm_file(path);
    else if (g_rootlen) {
        _snprintf(pat, sizeof(pat), "%smods\\netmod\\tables\\*.txt", g_root);
        pat[sizeof(pat) - 1] = 0;
        hf = FindFirstFileA(pat, &fd);
        if (hf != INVALID_HANDLE_VALUE) {
            do {
                if (!(fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) && cnt < 64) lstrcpynA(names[cnt++], fd.cFileName, MAX_PATH);
            } while (FindNextFileA(hf, &fd));
            FindClose(hf);
        }
        for (k = 1; k < cnt; k++)
            for (j = k; j > 0 && lstrcmpiA(names[j - 1], names[j]) > 0; j--) {
                char t[MAX_PATH]; lstrcpyA(t, names[j]); lstrcpyA(names[j], names[j - 1]); lstrcpyA(names[j - 1], t);
            }
        for (k = 0; k < cnt; k++) {
            _snprintf(path, sizeof(path), "%smods\\netmod\\tables\\%s", g_root, names[k]);
            path[sizeof(path) - 1] = 0;
            tm_file(path);
        }
    }
    if (!g_ntm) { logf("tmpl: no templates in the tables"); return 0; }
    g_tm_m = m;
    if (*s_hover != (DWORD)m + 0x9d20 || *s_cost != (DWORD)m + 0x145aa || *s_build != (DWORD)m + 0xabde) {
        logf("### tmpl: vtable slots 0x1002c1bc / mgr+0x90 / mgr+0xac do not hold the shipped functions - TMPL OFF");
        g_ntm = 0;
        return 0;
    }
    g_tm_orig_hover = *s_hover; g_tm_orig_cost = *s_cost; g_tm_orig_build = *s_build;
    v = (DWORD)tm_hover; ok += write_code((BYTE *)s_hover, &v, 4);
    v = (DWORD)tm_cost;  ok += write_code((BYTE *)s_cost, &v, 4);
    v = (DWORD)tm_build; ok += write_code((BYTE *)s_build, &v, 4);
    logf("tmpl: %d template(s), %d of 3 slots wrapped (hover 0x1002c1bc, cost mgr+0x90, build mgr+0xac); keys: T cycle, "
         "R rotate", g_ntm, ok);
    return g_ntm;
}

/* the game window exists later than SIMNTWRK: called from the watcher loop until it subclasses */
static void tmpl_keys(void) {
    HWND h = NULL;
    if (!g_ntm || g_tm_hwnd || env_off("SC3NETMOD_TMPL_KEYS")) return;
    EnumWindows(tm_enum, (LPARAM)&h);
    if (!h) return;
    g_tm_hwnd = h;
    g_tm_oldproc = (WNDPROC)SetWindowLongA(h, GWL_WNDPROC, (LONG)tm_wndproc);
    logf("tmpl: window 0x%08lX subclassed for the T / R keys", (DWORD)h);
}

static void tmpl_stats(void) {
    if (g_tm_n_hover || g_tm_n_place || g_tm_n_refused)
        logf("stats(tmpl): template hovers=%ld, placed=%ld, refused=%ld", g_tm_n_hover, g_tm_n_place, g_tm_n_refused);
}
