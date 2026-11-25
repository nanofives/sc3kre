/* ======================================================================================================== ROTPLACE
 * (child rotplace 2026-11-25, owner: "while placing a plopped building, TAB cycles its rotation 0 -> 1 -> 2 -> 3 -> 0 and
 * the building is placed with that rotation, so its front can face the street"). #included by sc3resize.c after
 * PLACEHINTS. Evidence: re/analysis/BUILDING_ROTATION.md section 6, verify/rotplace/RESULTS.md.
 *
 * Why it works (BUILDING_ROTATION.md 1-2): the occupant's rotation is bits 30-31 of +0x10, saved as is, and its sprite
 * draws frame zoom*4 + ((state + view) & 3) where the state is read from +0x10 when the sprite chain is attached
 * (SIMGEOM 0x1001ce12). cISC3Occupant::SetRotationFlag = vt+0x10c (SIMGEOM 0x1001d23e for building occupants) writes the
 * bits and rebuilds the chain; GetRotationFlag = vt+0xb4 (CodeView cv_vtables.tsv, cISC3Occupant). Set on a placed
 * occupant it does not redraw (section 4), so it must run before the occupant is inserted.
 *
 * Where: the building tools' Place goes through sc3_geom_place_footprint_region SIMGEOM 0x10006ba6, which makes the
 * occupant (this vt+0x20, into a vector), positions it (QI 0xc14f8955 vt+0xec(bounds)) and then calls
 * sc3_geom_commit_occupants_region 0x10007760(bounds, &vector, ...), whose insert is this vt+0x58 per occupant
 * [CONFIRMED @ SIMGEOM 0x10006cf8..0x10006d4e, 0x10007ab8]. RELOCATE already detours the commit entry and wraps the
 * 8 layer slots that tell a building tool's call from any other (key pointer - 0x108 has a tool vtable). This block
 * rides on both: rl_commit_pre hands it the vector, and rp_commit calls vt+0x10c(rot) on each new occupant there,
 * before the stock insert. Scripts and every other caller of the layer stay stock (no tool context).
 *
 * Key: TAB (no Ctrl / Alt) while the city view's current tool (view +0x228) is a building tool (SIMGEOM vtables
 * 0x10029504 / 0x100295e4 / 0x1002968c / 0x10029734) with a square footprint (width - 1 = tool+0x116 equals depth - 1 =
 * tool+0x117) and no text field has focus: rotation + 1 (Shift+TAB: - 1), the key is swallowed. Anything else passes
 * TAB to the game, which binds nothing to it (no VK 9 row in any Apps\Res\Hotkeys\*.IXF, checked 2026-11-25).
 * The rotation belongs to the tool object (pointer + key) while it is the city view's current tool: a new tool starts
 * at 0, so choosing another building, Esc, or a one-shot tool ending after its placement resets it (rp_poll), and a tool
 * that stays (parks, not one-shot) keeps it between placements. The Mover's tool starts at the moved
 * building's own rotation (read at the "Mover" click, vt+0xb4), so a move keeps it unless TAB changes it.
 * Label: one line "Giro N grados (TAB)" in the cost label of a square building tool (PLACEHINTS label wrapper; with
 * SC3RESIZE_PLACEHINTS=0 the rotation still works, the line is not shown).
 * Non-square footprints never turn (the footprint getters ignore rotation, LOT_SHAPES.md 1): TAB passes, no line, and
 * the commit refuses to set a rotation on an occupant whose cell rect is not square.
 * Switch: sc3resize.ini [buildings] rotate=0 or SC3RESIZE_ROTPLACE=0: stock (no key, no line, no SetRotationFlag). */
static BYTE  *g_rp_tool;            /* the tool the rotation was picked in */
static DWORD  g_rp_key[3];          /* and its key, so a new tool at a reused address starts at 0 */
static int    g_rp_rot;             /* 0..3 */
static int    g_rp_swallow;         /* the TAB down was ours: eat its WM_CHAR and key-up too */

static int rp_btool(BYTE *t) {
    static const DWORD bvt[4] = { 0x29504, 0x295e4, 0x2968c, 0x29734 };
    int i;
    if (!t || !g_rl_geom || IsBadReadPtr(t, 0x120)) return 0;
    for (i = 0; i < 4; i++) if (*(DWORD *)t == (DWORD)g_rl_geom + bvt[i]) return 1;
    return 0;
}

/* the city view's current tool (SIMGEOM FUN_1001be16 -> view, SIMSPR vtable +0x67894, tool +0x228; pkr_cur_tool) */
static BYTE *rp_cur_tool(BYTE **view) {
    HMODULE spr = GetModuleHandleA("SIMSPR.DLL");
    BYTE *vw;
    if (view) *view = NULL;
    if (!g_rl_geom || !spr) return NULL;
    __try {
        vw = ((BYTE *(__cdecl *)(void))((BYTE *)g_rl_geom + 0x1be16))();
        if (!vw || IsBadReadPtr(vw, 0x22c) || *(DWORD *)vw != (DWORD)spr + 0x67894) return NULL;
        if (view) *view = vw;
        return *(BYTE **)(vw + 0x228);
    } __except (EXCEPTION_EXECUTE_HANDLER) { return NULL; }
}

/* the rotation a placement by this tool gets: the picked one, else the moved building's own (Mover), else 0 */
static int rp_rot_of(BYTE *t, int *mine_out) {
    int mine = 0;
    if (t && rp_btool(t)) rl_tool((DWORD)(t + 0x108), &mine);
    if (mine_out) *mine_out = mine;
    if (t && t == g_rp_tool && !memcmp(t + 0x108, g_rp_key, 12)) return g_rp_rot;
    return mine ? g_rl_rot0 : 0;
}

static int rp_square(BYTE *t) { return t[0x116] == t[0x117]; }

/* the picked rotation ends with its tool: once the city view's current tool is another one (Esc, a menu pick, the
   one-shot tool ending after its placement), so a new tool made at the freed tool's address starts at 0 again
   (measured: two arms of the Mayor's House in a row got the same address). Game thread: mouse moves, keys, labels. */
static void rp_poll(void) {
    if (g_rp_tool && rp_cur_tool(NULL) != g_rp_tool) {
        logf("ROTPLACE> tool 0x%08lX no longer current: rotation %d dropped", (DWORD)g_rp_tool, g_rp_rot);
        g_rp_tool = NULL; g_rp_rot = 0;
    }
}

/* PLACEHINTS label wrapper: the line for the current tool, 0 = none */
static int rp_label(BYTE *view, char *out, int cap) {
    BYTE *t;
    out[0] = 0;
    if (!g_rp || !g_rl_geom || !view) return 0;
    __try {
        if (IsBadReadPtr(view, 0x22c)) return 0;
        t = *(BYTE **)(view + 0x228);
        if (g_rp_tool && t != g_rp_tool) { g_rp_tool = NULL; g_rp_rot = 0; }
        if (!rp_btool(t) || !rp_square(t)) return 0;
        wsprintfA(out, SC3TR(ho_spanish(), "resize.rotplace_label", "Giro %d grados (TAB)", "Rotation %d degrees (TAB)"),
                  rp_rot_of(t, NULL) * 90);
    } __except (EXCEPTION_EXECUTE_HANDLER) { out[0] = 0; return 0; }
    (void)cap;
    return out[0] != 0;
}

/* rz_wndproc, game window thread. 1 = the message was ours (swallow it). */
static int rp_key(UINT m, WPARAM wp, LPARAM lp) {
    BYTE *t, *view;
    int mine, back;
    if (!g_rp) return 0;
    if (m == WM_MOUSEMOVE || m == WM_LBUTTONDOWN || m == WM_RBUTTONDOWN) { rp_poll(); return 0; }
    if (wp != VK_TAB) return 0;
    if (m == WM_KEYUP || m == WM_CHAR) { if (g_rp_swallow) { if (m == WM_KEYUP) g_rp_swallow = 0; return 1; } return 0; }
    if (m != WM_KEYDOWN) return 0;
    g_rp_swallow = 0;
    rp_poll();
    if (GetKeyState(VK_CONTROL) < 0 || GetKeyState(VK_MENU) < 0 || rz_text_focus()) return 0;
    t = rp_cur_tool(&view);
    if (!rp_btool(t)) return 0;
    if (!rp_square(t)) {
        static BYTE *said;
        if (said != t) { said = t; logf("ROTPLACE> TAB ignored: footprint %ux%u is not square", t[0x116] + 1, t[0x117] + 1); }
        return 0;
    }
    g_rp_swallow = 1;
    if (lp & 0x40000000) return 1;   /* auto-repeat: one step per press */
    back = GetKeyState(VK_SHIFT) < 0;
    {   int r = rp_rot_of(t, &mine);
        g_rp_tool = t; memcpy(g_rp_key, t + 0x108, 12);
        g_rp_rot = (r + (back ? 3 : 1)) & 3; }
    logf("ROTPLACE> TAB%s: rotation %d (%d degrees), tool 0x%08lX key 0x%08lX 0x%08lX 0x%08lX footprint %ux%u%s",
         back ? " (Shift, back)" : "", g_rp_rot, g_rp_rot * 90, (DWORD)t, g_rp_key[0], g_rp_key[1], g_rp_key[2],
         t[0x116] + 1, t[0x117] + 1, mine ? " (Mover)" : "");
    __try { ph_repost(t); } __except (EXCEPTION_EXECUTE_HANDLER) { }
    return 1;
}

/* rl_commit_pre (SIMGEOM 0x10007760 entry, building tool context only): the new occupants, not inserted yet */
static void rp_commit(DWORD *vec, BYTE *tool, int mine) {
    void **p, **e;
    int rot, n = 0;
    if (!g_rp || !vec || IsBadReadPtr(vec, 8)) return;
    rot = rp_rot_of(tool, NULL);
    if (!rot && !mine) return;   /* stock: the occupant is made with rotation 0 */
    p = (void **)vec[0]; e = (void **)vec[1];
    if (!p || e < p || e - p > 16) return;
    for (; p < e; p++) {
        LONG r[4];
        DWORD got = 0xff, ok;
        void *occ = NULL;
        if (!*p) continue;
        __try {
            /* the vector holds the 0xe0faadc7 interface the layer's create vt+0x20 asked for; cISC3Occupant is
               QueryInterface 0xc14f8955 of it, as 0x10006d63 does before SetLocation (vt+0xec) */
            if (!(ho_v(*p, 0x00, 2, 0xc14f8955, (DWORD)&occ, 0, 0, 0) & 0xff) || !occ) {
                logf("ROTPLACE> new occupant 0x%08lX: no cISC3Occupant interface", (DWORD)*p);
                continue;
            }
            memset(r, 0, sizeof(r));
            ho_v(occ, 0xd0, 1, (DWORD)r, 0, 0, 0, 0);   /* GetBoundingRectInCellCoords, inclusive */
            if (r[2] - r[0] != r[3] - r[1])
                logf("ROTPLACE> occupant 0x%08lX cells [%ld %ld %ld %ld] not square: left at rotation 0", (DWORD)occ, r[0], r[1], r[2], r[3]);
            else {
                ok = ho_v(occ, 0x10c, 1, (DWORD)rot, 0, 0, 0, 0) & 0xff;   /* SetRotationFlag */
                ho_v(occ, 0xb4, 1, (DWORD)&got, 0, 0, 0, 0);                /* GetRotationFlag */
                n++;
                logf("ROTPLACE> placed occupant 0x%08lX type %lu cells [%ld %ld %ld %ld]: SetRotationFlag(%d) %u, now %lu%s",
                     (DWORD)occ, ho_v(occ, 0x88, 0, 0, 0, 0, 0, 0), r[0], r[1], r[2], r[3], rot, ok, got, mine ? " (Mover)" : "");
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) { logf("ROTPLACE> fault setting the rotation of 0x%08lX", (DWORD)occ); }
        if (occ) __try { ho_v(occ, 0x08, 0, 0, 0, 0, 0, 0); } __except (EXCEPTION_EXECUTE_HANDLER) { }   /* the QI's reference */
    }
    if (tool && tool == g_rp_tool && !IsBadReadPtr(tool, 0x118) && tool[0x115]) {   /* one-shot (+0x115): the tool ends now */
        g_rp_tool = NULL; g_rp_rot = 0;
    }
    (void)n;
}
