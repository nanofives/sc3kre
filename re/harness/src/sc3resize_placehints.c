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
 * Round 2 (placehints2, owner after trying it: "the extra information when placing a zone should be visible when pressing
 * shift, the zone impact should be in a shade of green, light blue is the same as the zone it's being placed"):
 *  - SHIFT: the hint TEXT is added to the cost label only while Shift is held. Since placehints4 the plop halo (green /
 *    red land value cells and the green sprite tint, which follows the cells) also shows only while Shift is held
 *    (ph_halo_redo). The airport / seaport red no-transport cells stay always on: they say where the zone being dragged
 *    cannot grow, like the stock red refusal, not an area the building affects.
 *    Stock Shift role (re/analysis/PLACEHINTS.md D): only at button release. GZGraphicD 0x10017b90 maps MK_SHIFT to GZ
 *    mouse flag 1, and the left-up slots commit only when (flags & 1) == 0 (zone SIMRCI 0x1003f7ca, building SIMGEOM
 *    0x1002165e): releasing with Shift held cancels the drag / plop (measured: airport drag, no zone, no cost). Down and
 *    move ignore the flags. This block leaves that as it is. The state comes from the WM_KEYDOWN / WM_KEYUP VK_SHIFT the game
 *    window receives (rz_wndproc -> ph_shiftmsg), and a change re-posts the label with its last arguments, so it updates
 *    without a mouse move. SC3RESIZE_PLACEHINTS_SHIFT=force / never: test override (a modifier cannot be posted).
 *  - GREEN: where a plop raises land value the halo is green, not the tool's light blue. The highlighter holds 3 states
 *    per cell (low nibble 1 = tool code, 0xf = 0x24, 0 = none), the getter vt+0x30 0x1004adcd maps them, and two
 *    readers turn the code into a colour:
 *      terrain:  SIMSPR 0x1001a4c8 -> DirtBag vt+0x70 SIMDIRT 0x10005d20 -> cell cursor 0x10016b11 (+9 = code | 0x80),
 *                drawn by 0x1001576a as palette[style].row[code][shade] (palette table DAT_10025bac +0xc, 9 entries of
 *                {loaded, rows - 1 (short +2), row array +4}, built from palBasic.bmp .. palEdgeD.bmp, 0x10016cce /
 *                0x10012342), decoded by the cdecl DAT_10025bb4(pixel, &c0, &c1, &c2);
 *      sprites:  SIMSPR 0x10018081 (called only at 0x10019903) returns +0xdc (light blue, RGB 0 0x8a 0xb4) for any
 *                highlighted cell under the sprite or +0xde (red, RGB 0xdf 0x2c 0x2c) when one is 0x24, both made
 *                once by the converter FUN_1004feba() vt+0x88(&out, r, g, b) at 0x10016eba.
 *    The block adds nibble 2 -> code PH_GCODE: a green row appended to the palette of the highlighter's style
 *    (the tool's light-blue row 0x23 recoloured, same shading), the getter slot returns PH_GCODE for nibble 2, and the
 *    0x10019903 call returns a green tint when the sprite stands only on green cells. SC3RESIZE_PLACEHINTS_GREEN=0: the
 *    halo goes back to the tool colour.
 *
 * SC3RESIZE_PLACEHINTS=0: nothing. _ZONE=0 / _PLOP=0: one of the two. _LOG=1: one line per hint change. */
static int  g_ph = 1, g_ph_zone = 1, g_ph_plop = 1, g_ph_log, g_ph_green = 1;
static int  g_ph_shiftmode;         /* 0 = the Shift key, 1 = force (always shown), 2 = never */
static volatile LONG g_ph_shiftdown;/* Shift held, from the game window's key messages */
static void *g_ph_lview;            /* last cost label call: view, show, cost, nofunds (for the re-post on Shift) */
static DWORD g_ph_lshow, g_ph_lcost, g_ph_lnf;
static int ph_shift(void) { return g_ph_shiftmode == 1 ? 1 : g_ph_shiftmode == 2 ? 0 : g_ph_shiftdown != 0; }
static BYTE *g_ph_rci, *g_ph_geom, *g_ph_spr;
static DWORD g_ph_zprev_orig, g_ph_bprev_orig[4], g_ph_lbl_orig;
static int   g_ph_shiftplace = 1;   /* SHIFTPLACE: Shift + button release places like a plain release, hint tools only */
static DWORD g_ph_zup_orig, g_ph_bup_orig[4];
static BYTE *g_ph_hinttool;         /* the tool whose preview made the current hint (game thread) */
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
    g_ph_lview = view; g_ph_lshow = show & 0xff; g_ph_lcost = (DWORD)cost; g_ph_lnf = nofunds;   /* for a Shift edge */
    __try {
        BYTE *s = view + 0x134;
        if (g_ph && g_ph_hint[0] && (show & 0xff) && ph_shift()) {
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
    if (t[0]) g_ph_hinttool = tool; else if (g_ph_hinttool == tool) g_ph_hinttool = NULL;
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

/* placehints4 (owner 2026-11-03: "without shift it should hide the area affecting a ploppable building"): the land value
   halo is drawn only while Shift is held, so a Shift edge runs the building tool's preview again. The stock fill under it
   (highlighter vt+0x4c = SIMSPR 0x1004af93) clears every live cell (0x1004b653), fills the footprint and pushes the
   rect plus the dirty rect (vt+0x58), so the old halo goes and ph_bprev draws it again only when Shift is down. Called
   with the same arguments as the move handler SIMGEOM 0x10021764 (tool+0x40 = the cell it last previewed, out rect6),
   only when the hint tool is a building tool AND the city view's current tool (view +0x228, the picker's measurement),
   so a tool that was switched away or freed is never called. */
static void ph_halo_redo(void) {
    static const DWORD bvt[4] = { 0x29504, 0x295e4, 0x2968c, 0x29734 };
    BYTE *t = g_ph_hinttool, *vw = (BYTE *)g_ph_lview;
    LONG out[6];
    int i, ok = 0;
    if (!t || !vw || !g_ph_plop || IsBadReadPtr(vw, 0x22c) || *(DWORD *)vw != (DWORD)g_ph_spr + 0x67894) return;
    if (*(BYTE **)(vw + 0x228) != t || IsBadReadPtr(t, 0x120)) return;
    for (i = 0; i < 4; i++) if (*(DWORD *)t == (DWORD)g_ph_geom + bvt[i]) ok = 1;
    if (!ok || t[0x30]) return;
    ho_v(t, 0x54, 2, (DWORD)(t + 0x40), (DWORD)out, 0, 0, 0);
    if (g_ph_log) logf("PLACEHINTS> halo %s", ph_shift() ? "drawn (Shift down)" : "cleared (Shift up)");
}

/* rz_wndproc, game window thread (the same thread the tools post the label from): WM_KEYDOWN / WM_KEYUP VK_SHIFT and
   WM_KILLFOCUS (a key-up then goes to another window). On a change, the label is posted again with the arguments of
   its last post, when that post showed it and a hint is waiting, so Shift alone adds or drops the text. */
static void ph_shiftmsg(UINT m, WPARAM wp) {
    LONG down;
    if (!g_ph) return;
    if (m == WM_KILLFOCUS) down = 0;
    else if ((m == WM_KEYDOWN || m == WM_KEYUP) && wp == VK_SHIFT) down = m == WM_KEYDOWN;
    else return;
    if (InterlockedExchange(&g_ph_shiftdown, down) == down || g_ph_shiftmode) return;
    if (g_ph_log) logf("PLACEHINTS> Shift %s%s", down ? "down" : "up", g_ph_hint[0] && g_ph_lshow ? ": label re-posted" : "");
    if (!g_ph_hint[0] || !g_ph_lshow || !g_ph_lview) return;
    __try {
        ph_halo_redo();
        g_ph_inrepost = 1;
        ho_v(g_ph_lview, 0x50, 3, 1, g_ph_lcost, g_ph_lnf, 0, 0);
    } __except (EXCEPTION_EXECUTE_HANDLER) { }
    g_ph_inrepost = 0;
}

/* ------------------------------------------------------------------------------------------ SHIFTPLACE */
/* Stock: the left-up slots commit only when (flags & 1) == 0, flag 1 = MK_SHIFT (zone SIMRCI 0x1003f7ca, building SIMGEOM
   0x1002165e, both (x, z, byte flags), ret 0xc). While the tool is the one whose preview made the current hint (airport /
   seaport zone drag, plop with a land value row) the flag is dropped, so Shift + release places like a plain release.
   Other tools, other zone types, plops without a hint and every other use of Shift are not touched. */
static DWORD ph_up(BYTE *tool, DWORD orig, DWORD x, DWORD z, DWORD flags) {
    DWORD a[3];
    if (g_ph && g_ph_shiftplace && (flags & 1) && tool == g_ph_hinttool && g_ph_hint[0]) {
        if (g_ph_log) logf("PLACEHINTS> Shift + release on the hint tool: placed as a plain release");
        flags &= ~1u;
    }
    a[0] = x; a[1] = z; a[2] = flags;
    return rz_thiscall_ret(tool, (void *)orig, a, 3);
}
static DWORD __fastcall ph_zup(BYTE *t, void *e, DWORD x, DWORD z, DWORD f) { (void)e; return ph_up(t, g_ph_zup_orig, x, z, f); }
static DWORD __fastcall ph_bup0(BYTE *t, void *e, DWORD x, DWORD z, DWORD f) { (void)e; return ph_up(t, g_ph_bup_orig[0], x, z, f); }
static DWORD __fastcall ph_bup1(BYTE *t, void *e, DWORD x, DWORD z, DWORD f) { (void)e; return ph_up(t, g_ph_bup_orig[1], x, z, f); }
static DWORD __fastcall ph_bup2(BYTE *t, void *e, DWORD x, DWORD z, DWORD f) { (void)e; return ph_up(t, g_ph_bup_orig[2], x, z, f); }
static DWORD __fastcall ph_bup3(BYTE *t, void *e, DWORD x, DWORD z, DWORD f) { (void)e; return ph_up(t, g_ph_bup_orig[3], x, z, f); }

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

/* ------------------------------------------------------------------------------------------------- green */
static BYTE  *g_ph_dirt;
static DWORD  g_ph_gcode;            /* the green code, the index of the row this block appends (0 = none yet) */
static void  *g_ph_garr[9];          /* per palette style: the row array this block installed */
static DWORD  g_ph_get_orig, g_ph_tint_orig;
static WORD   g_ph_g16, g_ph_g16_for;/* sprite tint, made for this value of the stock tint (+0xdc) */
typedef void   (__cdecl *PH_DEC)(DWORD px, BYTE *c0, BYTE *c1, BYTE *c2);
typedef void  *(__cdecl *PH_MALLOC)(size_t);
typedef size_t (__cdecl *PH_MSIZE)(void *);
#define PH_GR(l) ((l) / 4)           /* the green from the light blue's brightness l: (l/4, l, l*3/10) */
#define PH_GB(l) ((l) * 3 / 10)

/* the display colour of r g b (SIMSPR converter FUN_1004feba() vt+0x88(&out, r, g, b), as 0x10016eba makes +0xdc) */
static WORD ph_enc(DWORD r, DWORD g, DWORD b) {
    DWORD o = 0;
    void *cv = ((PH_FN0)(g_ph_spr + 0x4feba))();
    if (cv) ho_v(cv, 0x88, 4, (DWORD)&o, r, g, b, 0);
    return (WORD)o;
}

/* make sure the palette of `style` has the green row at g_ph_gcode. The row array is the game's (msvcrt heap, freed
   entry by entry by SIMDIRT 0x100121a9 with msvcrt free), so the new array and row come from msvcrt malloc; the rows
   between the old end and the green one (only when styles differ in height) stay NULL, which that free loop skips. */
static int ph_green_ready(void *hl) {
    static PH_MALLOC mal; static PH_MSIZE msz;
    BYTE *bag, *pal, *e;
    WORD **arr, **na, *src, *row;
    DWORD style, rows, need, i, w, s;
    PH_DEC dec;
    if (!g_ph_dirt) g_ph_dirt = (BYTE *)GetModuleHandleA("SIMDIRT.DLL");
    if (!g_ph_green || !g_ph_dirt || !hl) return 0;
    style = *(DWORD *)((BYTE *)hl + 0x28) & 0x3f;
    if (style > 8) return 0;
    bag = *(BYTE **)(g_ph_dirt + 0x25bac);
    dec = *(PH_DEC *)(g_ph_dirt + 0x25bb4);
    if (!bag || !dec || IsBadReadPtr(bag, 0x20)) return 0;
    pal = *(BYTE **)(bag + 0xc);
    if (!pal || IsBadReadPtr(pal, 9 * 8)) return 0;
    e = pal + style * 8;
    if (!e[0]) return 0;
    arr = *(WORD ***)(e + 4);
    rows = (DWORD)*(WORD *)(e + 2) + 1;
    if (arr && arr == g_ph_garr[style] && g_ph_gcode && rows == g_ph_gcode + 1) return 1;
    if (!arr || rows <= 0x23 || IsBadReadPtr(arr, rows * 4) || !(src = arr[0x23])) return 0;
    if (!mal) {
        HMODULE crt = GetModuleHandleA("msvcrt.dll");
        if (crt) { mal = (PH_MALLOC)GetProcAddress(crt, "malloc"); msz = (PH_MSIZE)GetProcAddress(crt, "_msize"); }
        if (!mal || !msz) { logf("PLACEHINTS> msvcrt malloc/_msize not found: green halo off"); g_ph_green = 0; return 0; }
    }
    if (!g_ph_gcode) g_ph_gcode = rows;            /* one code for every style: the first height seen */
    if (rows > g_ph_gcode || g_ph_gcode > 0x7f) {  /* a taller style: its row at our code is a stock colour */
        logf("PLACEHINTS> palette style %lu has %lu rows, green code 0x%lX: green halo off", style, rows, g_ph_gcode);
        g_ph_green = 0; return 0;
    }
    s = (DWORD)msz(src);
    w = s / 2;
    if (!s || s == (DWORD)-1 || w < 2 || w > 4096) return 0;
    need = g_ph_gcode + 1;
    na = (WORD **)mal(need * 4);
    row = (WORD *)mal(w * 2);
    if (!na || !row) return 0;
    for (i = 0; i < need; i++) na[i] = i < rows ? arr[i] : NULL;
    for (i = 0; i < w; i++) {                       /* same shading as the light blue: brightness = max channel */
        BYTE c[3] = { 0, 0, 0 }, l;
        dec((DWORD)src[i], &c[0], &c[1], &c[2]);
        l = c[0] > c[1] ? c[0] : c[1]; if (c[2] > l) l = c[2];
        row[i] = ph_enc(PH_GR(l), l, PH_GB(l));
    }
    na[g_ph_gcode] = row;
    *(WORD ***)(e + 4) = na;                        /* the old array is left allocated: a reader may hold it */
    *(WORD *)(e + 2) = (WORD)(need - 1);
    g_ph_garr[style] = na;
    {   BYTE c[3] = { 0, 0, 0 }, g[3] = { 0, 0, 0 };
        dec((DWORD)src[w / 2], &c[0], &c[1], &c[2]); dec((DWORD)row[w / 2], &g[0], &g[1], &g[2]);
        logf("PLACEHINTS> green row 0x%lX added to palette style %lu (%lu rows, %lu shades): mid shade light blue "
             "%u %u %u -> green %u %u %u", g_ph_gcode, style, rows, w, c[0], c[1], c[2], g[0], g[1], g[2]); }
    return 1;
}

/* highlighter getter vt+0x30 (0x1004adcd, void(pos*, code*), ret 8): nibble 2 = the green code */
static void __fastcall ph_hlget(BYTE *hl, void *edx, LONG *pos, DWORD *out) {
    DWORD a[2];
    (void)edx;
    a[0] = (DWORD)pos; a[1] = (DWORD)out;
    rz_thiscall_ret(hl, (void *)g_ph_get_orig, a, 2);
    if (g_ph_gcode && g_ph_green && pos && out && !*out) {
        __try {
            void *g = *(void **)(hl + 0x6c);
            BYTE b = 0;
            if (g) { ho_v(g, 0x34, 3, (DWORD)(pos[0] >> 8), (DWORD)(pos[1] >> 8), (DWORD)&b, 0, 0); if ((b & 0xf) == 2) *out = g_ph_gcode; }
        } __except (EXCEPTION_EXECUTE_HANDLER) { }
    }
}

/* SIMSPR 0x10018081 (sprite manager, this+0x1c highlighter; (x0, z0, x1, z1, colour*), ret 0x14), called at 0x10019903:
   a sprite standing only on green cells (no tool-coloured or red cell) gets the green tint */
static DWORD __fastcall ph_tint(BYTE *mgr, void *edx, DWORD x0, DWORD z0, DWORD x1, DWORD z1, DWORD *out) {
    DWORD a[5], r;
    (void)edx;
    a[0] = x0; a[1] = z0; a[2] = x1; a[3] = z1; a[4] = (DWORD)out;
    r = rz_thiscall_ret(mgr, (void *)g_ph_tint_orig, a, 5);
    if (!(r & 0xff) || !g_ph_gcode || !g_ph_green || !out) return r;
    __try {
        WORD blue = *(WORD *)(mgr + 0xdc);
        void *hl = *(void **)(mgr + 0x1c);
        DWORD x, z, code;
        int green = 0, other = 0;
        if (*out != blue || !hl || x1 < x0 || z1 < z0 || x1 - x0 > 63 || z1 - z0 > 63) return r;
        for (x = x0; x <= x1 && !other; x++) for (z = z0; z <= z1 && !other; z++) {
            LONG p[3];
            p[0] = (LONG)(x << 8); p[1] = (LONG)(z << 8); p[2] = 0; code = 0;
            ho_v(hl, 0x30, 2, (DWORD)p, (DWORD)&code, 0, 0, 0);
            if (code == g_ph_gcode) green = 1; else if (code) other = 1;
        }
        if (green && !other) {
            if (g_ph_g16_for != blue || !g_ph_g16) { g_ph_g16 = ph_enc(0x2c, 0xb4, 0x36); g_ph_g16_for = blue; }
            *out = g_ph_g16;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) { }
    return r;
}

/* a halo cell going up: the tool's own code through the stock setter (dirty rect, push bookkeeping), then nibble 2 */
static void ph_mark_up(void *hl, LONG x, LONG z) {
    void *g;
    BYTE b = 0;
    ph_mark(hl, x, z, *(DWORD *)((BYTE *)hl + 0x2c));
    if (!ph_green_ready(hl) || !(g = *(void **)((BYTE *)hl + 0x6c))) return;
    ho_v(g, 0x34, 3, (DWORD)x, (DWORD)z, (DWORD)&b, 0, 0);
    if ((b & 0xf) != 1) return;
    b = (BYTE)((b & 0xf0) | 2);
    ho_v(g, 0x3c, 3, (DWORD)x, (DWORD)z, (DWORD)&b, 0, 0);
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
            /* modlang: one format per language from the tables, the inline pair is the fallback */
            wsprintfA(t, SC3TR(es, "placehints.port_hint",
                               "%s %ld celdas, %ld sin transporte (rojo)  |  cap. %s +%ld, uso %ld%% a %ld%%  |  "
                               "techo %s %ld a %ld  |  %snecesita energia y agua",
                               "%s %ld cells, %ld without transport (red)  |  cap. %s +%ld, use %ld%% to %ld%%  |  "
                               "%s ceiling %ld to %ld  |  %sneeds power and water"),
                      air ? SC3TR(es, "placehints.airport", "Aeropuerto", "Airport") : SC3TR(es, "placehints.seaport", "Puerto", "Seaport"),
                      n, bad, air ? "C" : "I", add, cap, capn,
                      air ? "C" : "I", vmax - vmax * cap / 100, vmax - vmax * capn / 100,
                      air ? (tiny ? SC3TR(es, "placehints.runway", "pista: 3x5 o mas, ", "runway: 3x5 or more, ") : "")
                          : SC3TR(es, "placehints.piers", "muelles: 5 de borde con agua, ", "piers: 5 edge cells on water, "));
        }
        ph_sethint(tool, t);
    } __except (EXCEPTION_EXECUTE_HANDLER) { }
    return r;
}


/* ------------------------------------------------------------------------------------------ STATION (placehints4) */
/* Owner 2026-11-03: "is it possible to add public transport to the shift visualization?". While a bus stop, train
 * station, subway station or rail-to-subway station is being placed:
 *  - Shift: the cells whose lots would walk to it, and of those the ones whose trips already use transit in green.
 *    The rule [CONFIRMED @ SimTransit 0x1000755e, start node type 0x80]: a trip's start scans its lot rect grown by r,
 *    corners skipped, r = layer+0xc5 Res / +0xc6 Com / +0xc7 Ind / +0xc8 other (STTraffic TripMaxDistanceToRoad 4 / 3 /
 *    5 / 5, +1 with the shuttle ordinance 0x100087fd). A cell with flag 0x10 in the layer+0x5c grid is a station
 *    candidate, and one below DAT_1001f0c0 sets the keep value to 0xff, so it beats every road. The drawn area uses the
 *    Res reach (exact for 1-cell lots; a bigger lot reaches when any of its cells is inside); the label names all three.
 *    Trips: TRIPCELLS (sc3resize_vdbars.c), per origin cell, all / bus-rail-subway, months faded by 1/8.
 *  - always (like the stock red refusal): footprint red when no neighbour can take the trip on, ph_station_links.
 * Station agent type ids: measured in the lab (plop tool type log), SC3RESIZE_PLACEHINTS_STATIONS=bus,rail,subway,railsub
 * overrides. SC3RESIZE_PLACEHINTS_STATION=0: stations get no hint (stock preview). */
#define PH_ST_LAYER 0x1fdb8           /* SimTransit traffic layer singleton (sc3dataview ST_LAYER) */
static int    g_ph_station = 1;
static BYTE  *g_ph_st;
static DWORD  g_ph_stype[4] = { 12210, 12230, 12360, 12361 };   /* bus stop, train station, subway station, rail to
   subway: agent type ids measured 2026-11-03, plop tool type log after menu commands 0x10004004 / 0x10004102 / 0x10004202 /
   0x10004009 (MenuItem.INI names), building tool vtables SIMGEOM 0x10029504 (bus, train) and 0x1002968c (both subway) */

static BYTE *ph_tlayer(void) {
    BYTE *tl;
    if (!g_ph_st) g_ph_st = (BYTE *)GetModuleHandleA("SimTransit.dll");
    if (!g_ph_st) return NULL;
    tl = *(BYTE **)(g_ph_st + PH_ST_LAYER);
    if (!tl || IsBadReadPtr(tl, 0xd0) || *(int *)(tl + 0x14) <= 0 || *(int *)(tl + 0x18) <= 0 ||
        *(int *)(tl + 0x14) > 4096 || *(int *)(tl + 0x18) > 4096 || !*(BYTE **)(tl + 0x5c)) return NULL;
    return tl;
}
static WORD ph_tflags(BYTE *tl, LONG x, LONG z) {
    return *(WORD *)(*(BYTE **)(*(BYTE **)(*(BYTE **)(tl + 0x5c) + 0xc) + x * 4) + z * 2);
}

/* THE SHARED STATION RULE (child stationwarn uses the same one for built stations). Number of cells through which a
 * station of `kind` on the cell rect x0..x1, z0..z1 can pass a trip on; 0 = a dead station. The route step from a
 * station node looks at the rect grown by 1, corners skipped (the station's own cells carry 0x10 and never qualify),
 * and steps to a cell that LACKS 0x10 and has: bus stop 0x50 -> 1 road (node 0x41), train station 0x14 -> 4 rail,
 * subway station 0x18 -> 8 tunnel, rail-subway 0x30 -> 4 or 8 [CONFIRMED @ SimTransit 0x1000755e]. Measured for rail:
 * a 1-cell gap gave 0 arrivals in 800 days (verify/railgap/RESULTS.md). kind: 0 bus, 1 rail, 2 subway, 3 rail-subway. */
static int ph_station_links(BYTE *tl, int kind, LONG x0, LONG z0, LONG x1, LONG z1) {
    static const WORD need[4] = { 1, 4, 8, 4 | 8 };
    LONG W = *(int *)(tl + 0x14), H = *(int *)(tl + 0x18), x, z;
    int n = 0;
    if (kind < 0 || kind > 3) return 0;
    for (x = x0 - 1; x <= x1 + 1; x++) for (z = z0 - 1; z <= z1 + 1; z++) {
        WORD f;
        if ((x == x0 - 1 || x == x1 + 1) && (z == z0 - 1 || z == z1 + 1)) continue;   /* corners */
        if (x >= x0 && x <= x1 && z >= z0 && z <= z1) continue;                        /* the station itself */
        if (x < 0 || z < 0 || x >= W || z >= H) continue;
        f = ph_tflags(tl, x, z);
        if (!(f & 0x10) && (f & need[kind])) n++;
    }
    return n;
}

static int ph_station_kind(DWORD type) {
    int i;
    if (!g_ph_station || !type) return -1;
    for (i = 0; i < 4; i++) if (g_ph_stype[i] == type) return i;
    return -1;
}

/* the station preview, called from ph_bprev after the stock footprint fill. Footprint cells fx0..fx1, fz0..fz1. */
static void ph_station(BYTE *tool, void *hl, int kind, LONG fx0, LONG fz0, LONG fx1, LONG fz1) {
    BYTE *tl = ph_tlayer();
    char t[400], tr[160], lk[96];
    int es = ho_spanish(), draw = ph_shift(), links, r, rc, ri;
    LONG W, H, x, z, hx0, hz0, hx1, hz1, cells = 0, tcells = 0;
    double sn = 0, st = 0, cn = 0, ct = 0;
    if (!tl) { ph_sethint(tool, ""); return; }
    W = *(int *)(tl + 0x14); H = *(int *)(tl + 0x18);
    r = tl[0xc5]; rc = tl[0xc6]; ri = tl[0xc7];
    if (r < 1 || r > 16) r = 4;
    links = ph_station_links(tl, kind, fx0, fz0, fx1, fz1);
    if (!links && !tool[0x38] && !tool[0x39] && !tool[0x3a]) {   /* dead here: footprint red, Shift or not */
        for (x = fx0; x <= fx1; x++) for (z = fz0; z <= fz1; z++) ph_mark(hl, x, z, 0x24);
        ph_push(hl, fx0, fz0, fx1, fz1);
    }
    hx0 = fx0 - r < 0 ? 0 : fx0 - r; hz0 = fz0 - r < 0 ? 0 : fz0 - r;
    hx1 = fx1 + r > W - 1 ? W - 1 : fx1 + r; hz1 = fz1 + r > H - 1 ? H - 1 : fz1 + r;
    for (x = hx0; x <= hx1; x++) for (z = hz0; z <= hz1; z++) {
        LONG dx = x < fx0 ? fx0 - x : x > fx1 ? x - fx1 : 0, dz = z < fz0 ? fz0 - z : z > fz1 ? z - fz1 : 0;
        int tused = 0;
        if (!dx && !dz) continue;                                  /* footprint: the stock preview */
        if (dx > r || dz > r || (dx == r && dz == r)) continue;    /* outside the reach, or a skipped corner */
        cells++;
        if (g_tc_hist && g_tc_cur && x < TC_S && z < TC_S) {
            DWORD h = g_tc_hist[x * TC_S + z], c = g_tc_cur[x * TC_S + z];
            sn += h & 0xffff; st += h >> 16; cn += c & 0xffff; ct += c >> 16;
            tused = (h >> 16) || (c >> 16);
        }
        if (tused) tcells++;
        if (draw) { if (tused) ph_mark_up(hl, x, z); else ph_mark(hl, x, z, *(DWORD *)((BYTE *)hl + 0x2c)); }
    }
    if (draw && cells) ph_push(hl, hx0, hz0, hx1, hz1);
    /* trips a month: hist holds each closed month x16, older ones faded by 1/8, so after k months the weights sum to
       128 (1 - (7/8)^k). TRIPCELLS closes a month only from GRAPHNEW's budget hook, which runs once the Graficas page
       has been opened (sc3resize_graphs.c gn_month, g_gn_if[0]); until then it holds only the count since the load. */
    if (!g_tc_cur)
        lstrcpyA(tr, SC3TR(es, "placehints.st_notrips", "sin datos de viajes (TRIPCELLS apagado)", "no trip data (TRIPCELLS off)"));
    else if (g_tc_months > 0) {
        double w, f = 1;
        LONG k;
        for (k = 0; k < g_tc_months && k < 64; k++) f *= 0.875;
        w = 128.0 * (1.0 - f);
        wsprintfA(tr, SC3TR(es, "placehints.st_trips", "%ld viajes al mes salen de aqu\xed, %ld en transporte (verde)",
                            "%ld trips a month start here, %ld by transit (green)"), (LONG)(sn / w + 0.5), (LONG)(st / w + 0.5));
    } else
        wsprintfA(tr, SC3TR(es, "placehints.st_trips_load", "%ld viajes desde la carga salen de aqu\xed, %ld en transporte (verde)",
                            "%ld trips since the city loaded start here, %ld by transit (green)"), (LONG)cn, (LONG)ct);
    if (links)
        wsprintfA(lk, SC3TR(es, "placehints.st_links", "conecta por %d celdas", "connects through %d cells"), links);
    else if (kind == 0)
        lstrcpyA(lk, SC3TR(es, "placehints.st_dead_bus", "no toca ninguna calle: 0 viajes (rojo)", "touches no road: 0 trips (red)"));
    else if (kind == 2)
        lstrcpyA(lk, SC3TR(es, "placehints.st_dead_subway", "no toca el t\xfanel: 0 viajes (rojo)", "touches no subway: 0 trips (red)"));
    else if (kind == 3)
        lstrcpyA(lk, SC3TR(es, "placehints.st_dead_railsub", "no toca v\355a ni t\xfanel: 0 viajes (rojo)", "touches no rail or subway: 0 trips (red)"));
    else
        lstrcpyA(lk, SC3TR(es, "placehints.st_dead_rail", "no toca la v\355a: 0 viajes (rojo)", "touches no rail: 0 trips (red)"));
    wsprintfA(t, SC3TR(es, "placehints.station", "%s: a pie R %d C %d I %d celdas  |  %s  |  %s",
                       "%s: walk R %d C %d I %d cells  |  %s  |  %s"),
              kind == 0 ? SC3TR(es, "placehints.st_bus", "Parada de bus", "Bus stop")
              : kind == 1 ? SC3TR(es, "placehints.st_rail", "Estaci\xf3n de tren", "Train station")
              : kind == 2 ? SC3TR(es, "placehints.st_subway", "Estaci\xf3n de metro", "Subway station")
                          : SC3TR(es, "placehints.st_railsub", "Tren a metro", "Rail to subway"),
              r, rc, ri, tr, lk);
    if (g_ph_log && lstrcmpA(g_ph_hint, t))
        logf("PLACEHINTS> station kind %d footprint [%ld %ld %ld %ld] links %d, reach %d: %ld cells, %ld with transit trips",
             kind, fx0, fz0, fx1, fz1, links, r, cells, tcells);
    ph_sethint(tool, t);
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
        int draw = ph_shift();     /* placehints4: the halo is drawn only while Shift is held (the text too, ph_label) */
        static const char cls[3] = { 'R', 'C', 'I' };
        if (!pos || !hl || !db || tool[0x30]) { ph_sethint(tool, ""); return r; }
        if (!(ho_v(db, 0x24, 3, (DWORD)(tool + 0x108), 0xe075ef51, (DWORD)&attr, 0, 0) & 0xff) || !attr) {
            ph_sethint(tool, ""); return r; }
        type = ho_v(attr, 0x50, 0, 0, 0, 0, 0, 0);
        ho_v(attr, 0x08, 0, 0, 0, 0, 0, 0);
        {   static DWORD lastt = 0xffffffff;
            if (g_ph_log && type != lastt) {
                logf("PLACEHINTS> plop tool type %lu (tool vtable SIMGEOM+0x%lX)", type, *(DWORD *)tool - (DWORD)g_ph_geom);
                lastt = type; } }
        if ((k = ph_station_kind(type)) >= 0) {   /* placehints4: bus stop / train / subway / rail-to-subway station */
            fx0 = pos[0] >> 8; fz0 = pos[1] >> 8;
            ph_station(tool, hl, (int)k, fx0, fz0, fx0 + tool[0x116], fz0 + tool[0x117]);
            return r;
        }
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
                    if (draw) { if (v > 0) ph_mark_up(hl, cx, cz); else ph_mark(hl, cx, cz, 0x24); }   /* up green, down red */
                    d = cx < fx0 ? fx0 - cx : cx > fx1 ? cx - fx1 : 0;
                    if (cz < fz0 && fz0 - cz > d) d = fz0 - cz;
                    if (cz > fz1 && cz - fz1 > d) d = cz - fz1;
                    if (d > reach) reach = d;
                    if (cx < hx0) hx0 = cx; if (cz < hz0) hz0 = cz; if (cx > hx1) hx1 = cx; if (cz > hz1) hz1 = cz;
                }
            }
            if (draw && hx1 >= 0) ph_push(hl, hx0, hz0, hx1, hz1);
        }
        if (best < 0) { ph_sethint(tool, ""); return r; }
        {
            char part[3][24];
            for (k = 0; k < 3; k++) wsprintfA(part[k], "%c %s%ld%%", cls[k], peak[k] > 0 ? "+" : "", peak[k]);
            wsprintfA(t, SC3TR(ho_spanish(), "placehints.land_value", "Valor del suelo %s  %s  %s  |  %s %c %s%ld%% o mas hasta %ld celdas",
                               "Land value %s  %s  %s  |  %s %c %s%ld%% or more up to %ld cells"), part[0], part[1], part[2],
                      peak[best] > 0 ? (g_ph_green && g_ph_gcode ? SC3TR(ho_spanish(), "placehints.in_green", "en verde", "green")
                                                                 : SC3TR(ho_spanish(), "placehints.marked", "marcado", "marked")) : SC3TR(ho_spanish(), "placehints.in_red", "en rojo", "red"),
                      cls[best], peak[best] > 0 ? "+" : "-", thr, reach);
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
    if (GetEnvironmentVariableA("SC3RESIZE_PLACEHINTS_GREEN", v, sizeof(v))) g_ph_green = atoi(v);
    if (GetEnvironmentVariableA("SC3RESIZE_PLACEHINTS_SHIFTPLACE", v, sizeof(v))) g_ph_shiftplace = atoi(v);
    if (GetEnvironmentVariableA("SC3RESIZE_PLACEHINTS_STATION", v, sizeof(v))) g_ph_station = atoi(v);
    {   char sv[64];
        if (GetEnvironmentVariableA("SC3RESIZE_PLACEHINTS_STATIONS", sv, sizeof(sv))) {
            char *q = sv; int i;
            for (i = 0; i < 4 && *q; i++) { g_ph_stype[i] = strtoul(q, &q, 0); while (*q == ',' || *q == ' ') q++; }
        } }
    if (GetEnvironmentVariableA("SC3RESIZE_PLACEHINTS_SHIFT", v, sizeof(v)))
        g_ph_shiftmode = !lstrcmpiA(v, "force") ? 1 : !lstrcmpiA(v, "never") ? 2 : 0;
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
    if (g_ph_zone && g_ph_shiftplace) {
        slot = (DWORD *)(g_ph_rci + 0x4c06c + 0x28);
        if (*slot == (DWORD)g_ph_rci + 0x3f7ca) rl_patch_slot(slot, (void *)ph_zup, &g_ph_zup_orig);
        else logf("PLACEHINTS> zone tool up slot is 0x%08lX, not shipped: SHIFTPLACE off for zones", *slot);
    }
    if (g_ph_plop) {
        for (i = 0; i < 4; i++) {
            slot = (DWORD *)(g_ph_geom + bvt[i] + 0x54);
            if (*slot == (DWORD)g_ph_geom + 0x968b) { rl_patch_slot(slot, bfn[i], &g_ph_bprev_orig[i]); nb++; }
            slot = (DWORD *)(g_ph_geom + bvt[i] + 0x28);
            if (g_ph_shiftplace && *slot == (DWORD)g_ph_geom + 0x2165e) {
                static void *const bup[4] = { (void *)ph_bup0, (void *)ph_bup1, (void *)ph_bup2, (void *)ph_bup3 };
                rl_patch_slot(slot, bup[i], &g_ph_bup_orig[i]);
            }
        }
        if (!nb) { logf("PLACEHINTS> no building tool preview slot is shipped: plop hint off"); g_ph_plop = 0; }
    }
    if (g_ph_plop && g_ph_green) {   /* GREEN: palette row (SIMDIRT), getter slot, sprite tint call (SIMSPR) */
        BYTE *call = g_ph_spr + 0x19903;
        DWORD old;
        slot = (DWORD *)(g_ph_spr + 0x67a5c + 0x30);
        if (*slot != (DWORD)g_ph_spr + 0x4adcd || call[0] != 0xe8 ||
                 (DWORD)(call + 5 + *(LONG *)(call + 1)) != (DWORD)g_ph_spr + 0x18081) {
            logf("PLACEHINTS> highlighter getter 0x%08lX / tint call %02X not shipped: green halo off", *slot, call[0]);
            g_ph_green = 0;
        } else if (VirtualProtect(call + 1, 4, PAGE_EXECUTE_READWRITE, &old)) {
            rl_patch_slot(slot, (void *)ph_hlget, &g_ph_get_orig);
            g_ph_tint_orig = (DWORD)g_ph_spr + 0x18081;
            InterlockedExchange((LONG volatile *)(call + 1), (LONG)((DWORD)ph_tint - (DWORD)(call + 5)));
            FlushInstructionCache(GetCurrentProcess(), call, 5);
        } else { logf("PLACEHINTS> tint call not writable: green halo off"); g_ph_green = 0; }
    }
    logf("PLACEHINTS> on: cost label (SIMSPR view +0x50)%s%s%s, hint text %s", g_ph_zone ? ", airport/seaport zone drag (SIMRCI +0x54)" : "",
         g_ph_plop ? ", land value halo for plopped buildings (SIMGEOM +0x54)" : "", g_ph_plop && g_ph_green ? " in green" : "",
         g_ph_shiftmode == 1 ? "always (SHIFT=force)" : g_ph_shiftmode == 2 ? "never (SHIFT=never)" : "while Shift is held");
}
static DWORD WINAPI ph_thread(LPVOID p) { (void)p; ph_install(); return 0; }
