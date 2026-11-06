/* ===== FORESTTOOL (owner 2026-11-06: Civic Deals' forestfill as a terrain-tool button). =====
 * A 7th round button in the city's Paisaje flyout (trees, water, lower, raise, level, demolish). A click runs the
 * Civic Deals cheat "forestfill" through the game's own cheat manager, so the author's code decides which cells get
 * trees and shows its own notice. No button when SC3KCivicDeals.dll is not loaded.
 * SC3RESIZE_FORESTTOOL=0: nothing installed.
 *
 * Static read (worker, 2026-11-06):
 *  - The flyout list is data: MenuItem.INI in SYS.PAK, [SC3MenuDescs] 0xD1002000 = 6 items 0x2001..0x2006. The category
 *    button fills it once at init: SIMUI FUN_1004bc7c(list id) calls the button's vt+0x1f8(item id) per item, which makes
 *    the a917c button in the flyout column. We call vt+0x1f8(0x2007) after the stock list.
 *  - Icon and place per id are hard-coded in SIMUI 0x1004cdcd (thiscall, out[10]); an unknown id returns 0 and the button
 *    shuts down. For 0x2007 we fill it like 0x2001 (icon instance [4] = 0x2001, the trees icon) at the 7th slot, y 0xed at
 *    600 and 480, 0x14e above 600 (the 7th-slot values the game uses for 0x400a / 0x9001).
 *  - A click: a917c mouse-up -> FUN_1004c209 (thiscall, no args), which posts 0x25F0A91 for the item's menu record
 *    +0xb0 and does nothing when +0xb0 is NULL (ours). We catch our button there.
 *  - Cheats: cGZFrameWork::FrameWork 0x0045d5ae -> vt+0x7c Application -> QueryInterface(0xfa2) -> vt+0x2c
 *    GetCheatCodeManager -> vt+0x30 DoDefaultCheatCodeProcessing(cIGZString&, ulong&) = match (vt+0x2c) + notify
 *    (vt+0x28), the path the cheat box takes (cSC3CheatCodeEntryDialog::GZOnCommand 0x00428576). */
static WORD pkr_rgb(int r, int g, int b, DWORD code);   /* PICKER, below */
static int    g_foresttool = 1;
static void  *g_ft_orig_list, *g_ft_orig_art, *g_ft_orig_click;
static void  *g_ft_btn;
#define FT_ID     0x2007
#define FT_LIST   0xD1002000

/* the game's cheat manager, or NULL */
static void *ft_cheatmgr(void) {
    static const BYTE fw_b[6] = { 0xa1, 0x74, 0xab, 0x4f, 0x00, 0xc3 };   /* mov eax,[0x4fab74]; ret */
    void *fw, *app, *sc3 = NULL, *mgr = NULL;
    if (memcmp((void *)0x0045d5ae, fw_b, 6)) return NULL;
    __try {
        fw = ((void *(__cdecl *)(void))0x0045d5ae)();
        if (!fw) __leave;
        app = (void *)ho_v(fw, 0x7c, 0, 0, 0, 0, 0, 0);
        if (!app || !(ho_v(app, 0x00, 2, 0xfa2, (DWORD)&sc3, 0, 0, 0) & 0xff) || !sc3) __leave;
        mgr = (void *)ho_v(sc3, 0x2c, 0, 0, 0, 0, 0, 0);
        ho_v(sc3, 0x08, 0, 0, 0, 0, 0, 0);
    } __except (EXCEPTION_EXECUTE_HANDLER) { mgr = NULL; }
    return mgr;
}

/* run (go=1) or only look up (go=0) a cheat code; 1 = registered / processed */
static int ft_cheat(const char *code, int go) {
    static const BYTE ctor_b[5] = { 0xb8, 0x40, 0x08, 0x4c, 0x00 }, dtor_b[6] = { 0xc7, 0x01, 0xc4, 0xf4, 0x4c, 0x00 };
    DWORD str[16], id = 0;
    void *mgr = ft_cheatmgr();
    int r = 0;
    if (!mgr || memcmp((void *)0x00402a40, ctor_b, 5) || memcmp((void *)0x00402a96, dtor_b, 6)) return 0;
    memset(str, 0, sizeof(str));
    __try {
        ((void (__fastcall *)(void *, void *, const char *))0x00402a40)(str, NULL, code);   /* cRZString(char const *) */
        r = (int)(ho_v(mgr, go ? 0x30 : 0x2c, 2, (DWORD)str, (DWORD)&id, 0, 0, 0) & 0xff) != 0;
        ((void (__fastcall *)(void *, void *))0x00402a96)(str, NULL);                     /* ~cRZString */
    } __except (EXCEPTION_EXECUTE_HANDLER) { logf("FORESTTOOL> fault 0x%08lX in the cheat manager", GetExceptionCode()); r = 0; }
    return r;
}

/* ---- the "Bosque" icon: the trees icon's own 4-frame 144x36 strip with its tree replaced by three smaller ones ----
 * The cSC3Buffer at +0xd8 is shared by every button with the same resource key (measured: 0x2001's and ours are the
 * same object), so ours gets a new buffer (the pkr_strip recipe). Tree pixels = blue < 30 inside the face (x 6..25,
 * y 7..24, within 12 px of (17,15)), measured on frame 1 and used for all four frames (0 greyed, 1 normal, 2 pressed,
 * 3 hover). Their place is refilled with the row's mean face colour, then the tree is drawn at 62% at three spots. */
static void ft_rgb(WORD v, DWORD code, int *o) {
    if (code == 7) { o[0] = (v >> 11) << 3; o[1] = ((v >> 5) & 63) << 2; o[2] = (v & 31) << 3; }
    else           { o[0] = ((v >> 10) & 31) << 3; o[1] = ((v >> 5) & 31) << 3; o[2] = (v & 31) << 3; }
}
static int ft_make_art(void *btn) {
    BYTE *sui = (BYTE *)GetModuleHandleA("SIMUI.DLL");
    void *src = *(void **)((BYTE *)btn + 0xd8), *com, *dst = NULL;
    DWORD fmt[2] = { 0, 0 }, a[8];
    static BYTE mask[36][36];
    static WORD pix[36][144];
    BYTE *sb, *db;
    LONG sp, dp, x, y, f, k, cx2 = 0, cy2 = 0, n = 0;
    int ok = 0, locked = 0;
    static const double PL[3][2] = { { -5.5, -2.5 }, { 5.5, -2.5 }, { 0.0, 3.0 } };
    if (!src || IsBadReadPtr(src, 4)) return 0;
    __try {
        ho_v(src, 0x4c, 1, (DWORD)fmt, 0, 0, 0, 0);
        if (fmt[1] != 16 || (fmt[0] != 7 && fmt[0] != 5)) { logf("FORESTTOOL> icon format {%lu,%lu}: trees icon kept", fmt[0], fmt[1]); __leave; }
        if (ho_v(src, 0x38, 0, 0, 0, 0, 0, 0) != 144 || ho_v(src, 0x3c, 0, 0, 0, 0, 0, 0) != 36) { logf("FORESTTOOL> icon not 144x36: trees icon kept"); __leave; }
        if (!(ho_v(src, 0x1c, 1, 0x40, 0, 0, 0, 0) & 0xff)) __leave;
        locked = 1;
        sb = (BYTE *)ho_v(src, 0x1a8, 0, 0, 0, 0, 0, 0); sp = (LONG)ho_v(src, 0x1ac, 0, 0, 0, 0, 0, 0);
        if (!sb || sp < 288) __leave;
        for (y = 0; y < 36; y++) memcpy(pix[y], sb + y * sp, 288);
        ho_v(src, 0x20, 1, 0x40, 0, 0, 0, 0); locked = 0;
        for (y = 0; y < 36; y++)
            for (x = 0; x < 36; x++) {
                int c[3];
                ft_rgb(pix[y][36 + x], fmt[0], c);
                mask[y][x] = (BYTE)(x >= 6 && x <= 25 && y >= 7 && y <= 24 && c[2] < 30 && (x - 17) * (x - 17) + (y - 15) * (y - 15) <= 144);
                if (mask[y][x]) { cx2 += 2 * x; cy2 += 2 * y; n++; }
            }
        if (n < 40) { logf("FORESTTOOL> trees icon: only %ld tree pixels, trees icon kept", n); __leave; }
        {   /* the glyph box centre, as the prototype: (min+max)/2 */
            LONG x0 = 36, x1 = -1, y0 = 36, y1 = -1;
            for (y = 0; y < 36; y++) for (x = 0; x < 36; x++) if (mask[y][x]) {
                if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
            cx2 = x0 + x1; cy2 = y0 + y1;   /* doubled */
        }
        com = ((void *(__cdecl *)(void))(sui + 0x8489d))();
        if (!com || !(ho_v(com, 0x0c, 3, 0xc470d325, 0x20732180, (DWORD)&dst, 0, 0) & 0xff) || !dst) __leave;
        a[0] = 144; a[1] = 36; a[2] = fmt[0]; a[3] = fmt[1]; a[4] = a[5] = a[6] = a[7] = 0;
        if (!(rz_thiscall_ret(dst, (void *)(*(DWORD **)dst)[0x0c / 4], a, 8) & 0xff)) __leave;
        if (!(ho_v(dst, 0x1c, 1, 0x40, 0, 0, 0, 0) & 0xff)) __leave;
        db = (BYTE *)ho_v(dst, 0x1a8, 0, 0, 0, 0, 0, 0); dp = (LONG)ho_v(dst, 0x1ac, 0, 0, 0, 0, 0, 0);
        if (db && dp >= 288) {
            static WORD o[36][144];
            memcpy(o, pix, sizeof(o));
            for (f = 0; f < 4; f++) {
                LONG ox = f * 36;
                for (y = 0; y < 36; y++) {   /* refill the tree with the row's mean face colour */
                    int sum[3] = { 0, 0, 0 }, m = 0, c[3];
                    for (x = 0; x < 36; x++)
                        if (!mask[y][x] && (x - 18) * (x - 18) + (y - 16) * (y - 16) <= 81) { ft_rgb(pix[y][ox + x], fmt[0], c); sum[0] += c[0]; sum[1] += c[1]; sum[2] += c[2]; m++; }
                    if (!m) continue;
                    for (x = 0; x < 36; x++) if (mask[y][x]) o[y][ox + x] = pkr_rgb(sum[0] / m, sum[1] / m, sum[2] / m, fmt[0]);
                }
                for (k = 0; k < 3; k++)
                    for (y = 0; y < 36; y++)
                        for (x = 0; x < 36; x++) {
                            double sx = cx2 / 2.0 + (x + 0.5 - (cx2 / 2.0 + 0.5 + PL[k][0])) / 0.62;
                            double sy = cy2 / 2.0 + (y + 0.5 - (cy2 / 2.0 + 0.5 + PL[k][1])) / 0.62;
                            LONG ix = (LONG)sx, iy = (LONG)sy;
                            if (sx >= 0 && sy >= 0 && ix < 36 && iy < 36 && mask[iy][ix]) o[y][ox + x] = pix[iy][ox + ix];
                        }
            }
            for (y = 0; y < 36; y++) memcpy(db + y * dp, o[y], 288);
        }
        ho_v(dst, 0x20, 1, 0x40, 0, 0, 0, 0);
        ho_v(dst, 0xc8, 1, ho_v(dst, 0x18c, 3, 0xff, 0, 0xff, 0, 0), 0, 0, 0, 0);   /* magenta = transparent */
        if (db) {
            *(void **)((BYTE *)btn + 0xd8) = dst;   /* ours now; the shared one keeps its count (not known to be ours) */
            ok = 1;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) { logf("FORESTTOOL> icon fault 0x%08lX", GetExceptionCode()); ok = 0; }
    if (locked) ho_v(src, 0x20, 1, 0x40, 0, 0, 0, 0);
    if (!ok && dst) ho_v(dst, 0x08, 0, 0, 0, 0, 0, 0);
    logf("FORESTTOOL> icon: %s", ok ? "three trees drawn from the trees icon" : "trees icon kept");
    return ok;
}

/* per-frame poll: the 7th button is not painted when the flyout opens (measured: it showed only after a click), so
   invalidate it each time its column turns visible */
static int g_ft_colvis;
static void ft_tick(void) {
    BYTE *b = (BYTE *)g_ft_btn, *col;
    int vis;
    if (!b || IsBadReadPtr(b, 0xdc)) return;
    col = *(BYTE **)(b + 0xb8);
    if (!col || IsBadReadPtr(col, 0xa4)) return;
    vis = (*(DWORD *)(col + 0xa0) & 1) != 0;
    if (vis && !g_ft_colvis) { __try { ho_v(b, 0x154, 0, 0, 0, 0, 0, 0); } __except (EXCEPTION_EXECUTE_HANDLER) { } }
    g_ft_colvis = vis;
}

/* FUN_1004bc7c: the category button's list fill; after the landscape list, one more item */
static DWORD __fastcall ft_list(void *self, void *edx, DWORD list) {
    DWORD a[1], r;
    (void)edx;
    a[0] = list;
    r = rz_thiscall_ret(self, g_ft_orig_list, a, 1);
    if (list == FT_LIST) {
        /* the cheat manager does not list "forestfill" yet while the side panel is built (measured), so the test is the DLL */
        if (!GetModuleHandleA("SC3KCivicDeals.dll")) logf("FORESTTOOL> SC3KCivicDeals.dll not loaded: no button");
        else {
            DWORD ok = 0;
            __try { ok = ho_v(self, 0x1f8, 1, FT_ID, 0, 0, 0, 0) & 0xff; } __except (EXCEPTION_EXECUTE_HANDLER) { ok = 0; }
            logf("FORESTTOOL> Paisaje flyout: item 0x%x %s", FT_ID, ok ? "added" : "NOT added");
            if (ok && g_ft_btn) ft_make_art(g_ft_btn);
        }
    }
    return r;
}

/* SIMUI 0x1004cdcd: icon + place; ours borrows the trees icon at the 7th slot */
static DWORD __fastcall ft_art(void *self, void *edx, DWORD *out) {
    DWORD a[1], id = 0;
    (void)edx;
    __try { id = ho_v(self, 0xe8, 0, 0, 0, 0, 0, 0); } __except (EXCEPTION_EXECUTE_HANDLER) { id = 0; }
    if (id == FT_ID && out) {
        LONG h = 600;
        __try { void *w = (void *)ho_v(self, 0x20, 0, 0, 0, 0, 0, 0); if (w) h = (LONG)ho_v(w, 0x94, 0, 0, 0, 0, 0, 0); }
        __except (EXCEPTION_EXECUTE_HANDLER) { h = 600; }
        out[0] = 0x20; out[1] = 0x4287c742;
        out[2] = h == 0x1e0 ? 0x640480 : 0x2f78c6d;
        out[4] = 0x2001;
        *(BYTE *)(out + 5) = 1;
        out[6] = out[7] = 0x24;
        out[8] = 0;
        out[9] = h > 600 ? 0x14e : 0xed;
        g_ft_btn = self;
        logf("FORESTTOOL> button 0x%08lX art: trees icon, y %lu (window height %ld)", (DWORD)self, out[9], h);
        return 1;
    }
    a[0] = (DWORD)out;
    return rz_thiscall_ret(self, g_ft_orig_art, a, 1);
}

/* FUN_1004c209: a flyout button was clicked */
static DWORD __fastcall ft_click(void *self, void *edx) {
    (void)edx;
    if (self && self == g_ft_btn) {
        int r = ft_cheat("forestfill", 1);
        logf("FORESTTOOL> clicked: forestfill %s", r ? "sent" : "NOT processed");
        return 1;
    }
    return rz_thiscall_ret(self, g_ft_orig_click, NULL, 0);
}

/* a917c GZPaint (vtable slot 0x144 = 0x1004cac8): the stock buttons paint only hovered / pressed frames, their normal
   icons are part of the flyout's own art (measured: ours showed only under the pointer). For our button at rest,
   frame 1 is drawn the way the stock code draws the others: surface +0x5c, vt+0x1c(0x10) begin,
   vt+0x118(buffer +0xd8, src rect, dest rect +0x24, 0), vt+0x20(0x10) end. */
static DWORD g_ft_orig_paint;
static DWORD __fastcall ft_paint(void *self, void *edx) {
    (void)edx;
    if (self && self == g_ft_btn) {
        __try {
            /* measured: vt+0xf0(2) is 1 and +0xa4 is 0xa0 at rest; stock then draws nothing (+0xa4 bit 2 = frame 2,
               bit 4 = frame 3) */
            if ((ho_v(self, 0xf0, 1, 2, 0, 0, 0, 0) & 0xff) && !(*(DWORD *)((BYTE *)self + 0xa4) & 6)) {
                void *sf = *(void **)((BYTE *)self + 0x5c);
                LONG w = (LONG)ho_v(self, 0x90, 0, 0, 0, 0, 0, 0), h = (LONG)ho_v(self, 0x94, 0, 0, 0, 0, 0, 0);
                LONG r[4];
                if (sf && (ho_v(sf, 0x1c, 1, 0x10, 0, 0, 0, 0) & 0xff)) {
                    r[0] = w; r[1] = 0; r[2] = 2 * w; r[3] = h;
                    ho_v(sf, 0x118, 4, *(DWORD *)((BYTE *)self + 0xd8), (DWORD)r, (DWORD)((BYTE *)self + 0x24), 0, 0);
                    ho_v(sf, 0x20, 1, 0x10, 0, 0, 0, 0);
                }
                return 1;
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) { }
    }
    return rz_thiscall_ret(self, (void *)g_ft_orig_paint, NULL, 0);
}

static void ft_install(HMODULE sui) {
    static const BYTE e_list[5] = { 0x55, 0x8b, 0xec, 0x51, 0x51 };        /* push ebp; mov ebp,esp; push ecx; push ecx */
    static const BYTE e_art[5]  = { 0x53, 0x8b, 0xd9, 0x56, 0x57 };        /* push ebx; mov ebx,ecx; push esi; push edi */
    static const BYTE e_clk[6]  = { 0x55, 0x8b, 0xec, 0x83, 0xec, 0x10 };  /* push ebp; mov ebp,esp; sub esp,0x10 */
    if (!g_foresttool) { logf("FORESTTOOL> off (SC3RESIZE_FORESTTOOL=0)"); return; }
    if (GetModuleHandleA(NULL) != (HMODULE)0x00400000) { logf("FORESTTOOL> exe not at 0x400000: off"); return; }
    if (!ho_hook(sui, 0x4cdcd, e_art, 5, (void *)ft_art, &g_ft_orig_art, "flyout art FUN_1004cdcd")) return;
    if (!ho_hook(sui, 0x4c209, e_clk, 6, (void *)ft_click, &g_ft_orig_click, "flyout click FUN_1004c209")) return;
    if (!ho_hook(sui, 0x4bc7c, e_list, 5, (void *)ft_list, &g_ft_orig_list, "flyout list FUN_1004bc7c")) return;
    {   DWORD *slot = (DWORD *)((BYTE *)sui + 0xa917c + 0x144), old;
        if (*slot == (DWORD)sui + 0x4cac8 && VirtualProtect(slot, 4, PAGE_READWRITE, &old)) { g_ft_orig_paint = *slot; *slot = (DWORD)ft_paint; }
        else logf("FORESTTOOL> a917c GZPaint slot differs: the button shows only under the pointer"); }
    logf("FORESTTOOL> installed: \"Bosque\" button in the Paisaje flyout when Civic Deals is present");
}
