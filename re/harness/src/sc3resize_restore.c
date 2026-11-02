/* ======================================================================================================== RESTORE
 * (child restore 2026-11-02, re/analysis/RESTORE.md). #included by sc3resize.c after the LANDFILL block.
 * Owner: "en el menu de informacion de un edificio deberia haber un boton para restaurar (con costo acorde) el edificio
 * en cuestion si tiene vida util, luego agregar otro menu dentro de la seccion de reunirse (boton al lado de la cruz)".
 *
 * The mechanism lives in sc3restore.dll (age through IBuildingMortal 0x43680ca9, cost = price x fraction of life used,
 * SetBirthdate through the building interface, the city list). This block is the UI only, like LANDFILL:
 *  1. Query (?) dialog of a building the game ages: "Restaurar $N" (the font draws $ as the simoleon sign). The game's
 *     own "Edad (max)" line already shows age and life. The click restores it, then the dialog is closed and opened again
 *     on the same building (the game builds its text when the dialog opens) with "Restaurado ($N)" on the button; a
 *     refusal ("Sin fondos ($N)") leaves the dialog as it is.
 *  2. Reunirse list page: a "Vida util" button left of the close box (detour on the page's message handler SIMUI
 *     FUN_100042f7, __thiscall(this, win, msg, p3, p4, p5), ret 0x14: msg 0xa2bf8ace builds the page through FUN_10004405,
 *     msg 3 p3 1 is a button click with the id in p4 [CONFIRMED @ SIMUI 0x100042f7]). The click turns the same window
 *     into a list page, the MODSPAGE way: the game's children below the title bar are hidden, ours are shown. Two-line
 *     rows (name and cell / age and life left) with "Restaurar $N" each, 7 rows a page, "Restaurar todos ($total)" and
 *     "Volver". The window keeps its size (the game sizes it from the advisor count, FUN_10004405).
 * Without sc3restore.dll nothing is added. SC3RESIZE_RESTORE=0: nothing added either. */


#define RS_LBL 0x5E570002
static void *g_rs_win;                /* the last query dialog given a restore button (test message 2) */
#define RS_BW  150

typedef struct {                      /* = SC3R_INFO in sc3restore.c */
    DWORD size, type;
    LONG  age, max_age, decline, aging, defunct, price, cost, x0, z0, x1, z1, birth_y, birth_m;
    char  name[64];
} RS_INFO;
typedef int  (__cdecl *PFN_rs_info)(void *, RS_INFO *);
typedef int  (__cdecl *PFN_rs_apply)(void *, int, char *, int);
typedef LONG (__cdecl *PFN_rs_funds)(void);

static FARPROC rs_fn(const char *name) {
    HMODULE m = GetModuleHandleA("sc3restore.dll");
    return m ? GetProcAddress(m, name) : NULL;
}

static void rs_money(char *out, int cap, LONG v) {    /* 1234567 -> "1,234,567" (the game's font draws $ as the simoleon sign) */
    char t[32];
    int n, i, j = 0;
    _snprintf(t, sizeof(t), "%ld", v < 0 ? -v : v);
    n = (int)strlen(t);
    if (v < 0 && j < cap - 1) out[j++] = '-';
    for (i = 0; i < n && j < cap - 1; i++) {
        out[j++] = t[i];
        if ((n - 1 - i) % 3 == 0 && i < n - 1 && j < cap - 1) out[j++] = ',';
    }
    out[j] = 0;
}

/* "12a 4m" / "12y 4m" from months */
static void rs_age(char *out, int cap, LONG months, int es) {
    if (months < 0) months = 0;
    if (months % 12) _snprintf(out, cap, es ? "%lda %ldm" : "%ldy %ldm", months / 12, months % 12);
    else _snprintf(out, cap, es ? "%lda" : "%ldy", months / 12);
    out[cap - 1] = 0;
}

static void rs_line(const RS_INFO *i, int es, char *out, int cap) {
    char a[24], m[24], l[24];
    rs_age(a, sizeof(a), i->age, es);
    rs_age(m, sizeof(m), i->max_age, es);
    rs_age(l, sizeof(l), i->max_age - i->age, es);
    _snprintf(out, cap, es ? "Edad %s de %s, le quedan %s%s" : "Age %s of %s, %s left%s", a, m, l,
              i->aging ? (es ? " (decayendo)" : " (declining)") : "");
    out[cap - 1] = 0;
}

/* the result of the last click, shown on the reopened dialog's button for 4 s (the game's own text, "Edad (max)",
   is built when the dialog opens, so after a restore the dialog is closed and opened again on the same building) */
static struct { DWORD type, tick; LONG x0, z0; char cap[64]; } g_rs_last;

static void rs_caption(const RS_INFO *i, int es, char *out, int cap) {
    char c[32];
    rs_money(c, sizeof(c), i->cost);
    if (g_rs_last.tick && GetTickCount() - g_rs_last.tick < 10000 && g_rs_last.type == i->type && g_rs_last.x0 == i->x0 &&
        g_rs_last.z0 == i->z0) lstrcpynA(out, g_rs_last.cap, cap);
    else if (i->age <= 0) _snprintf(out, cap, es ? "Como nuevo" : "As new");
    else _snprintf(out, cap, es ? "Restaurar $%s" : "Restore $%s", c);
    out[cap - 1] = 0;
}

static void rs_query_cell(LONG x, LONG z);   /* below */
static struct { BYTE *self; void *win; LPARAM cell; } g_rs_close;   /* the dialog to close and reopen (rs_click) */
#define WM_RZ_RESTORE (WM_APP + 0x5F8)

static void rs_add(void *win, BYTE *qo) {
    HMODULE sui = GetModuleHandleA("SIMUI.DLL");
    PFN_rs_info fi = (PFN_rs_info)rs_fn("sc3restore_info");
    void *occ = *(void **)(qo + 0xd8), *fac;
    LONG *l = (LONG *)((BYTE *)win + 0x80), w, h, bx, by, ly;
    RS_INFO i;
    char cap[64], line[160];
    int es = ho_spanish(), okb = 0, okl = 0;
    if (!g_restore || !fi || !sui || !occ || !win || IsBadReadPtr(win, 0xa4)) return;
    if (ho_v(win, 0x78, 1, RS_BTN, 0, 0, 0, 0)) return;
    memset(&i, 0, sizeof(i));
    i.size = sizeof(i);
    if (!fi(occ, &i)) return;
    fac = ((void *(__cdecl *)(void))((BYTE *)sui + 0x85065))();
    if (!fac || IsBadReadPtr(fac, 4)) return;
    w = l[2] - l[0]; h = l[3] - l[1];
    by = h - 0x25 + (32 - QI_BH) / 2;
    bx = w - 0x32 - 8 - RS_BW - (g_queryid ? QI_BW + 8 : 0);
    if (bx < 8 || !rl_rect_free(win, bx, by, bx + RS_BW, by + QI_BH)) { bx = w - 8 - RS_BW; by -= QI_BH + 6; }
    rs_caption(&i, es, cap, sizeof(cap));
    okb = mp_button(fac, win, RS_BTN, cap, bx, by, RS_BW, QI_BH);
    if (okb) g_rs_win = win;
    ly = by - 22;
    rs_line(&i, es, line, sizeof(line));
    if (rl_rect_free(win, 10, ly, w - 10, ly + 18)) {
        int keep = g_ho_lblcol;
        g_ho_lblcol = 1;                       /* navy, as LANDFILL's lines */
        okl = ho_add_label(fac, win, RS_LBL, line, 10, ly, w - 20);
        g_ho_lblcol = keep;
    }
    logf("RESTORE> \"?\" on %s (type %lu) at (%ld, %ld), dialog %ldx%ld: age %ld of %ld months (decline %ld), price %ld, "
         "cost %ld; button %d at (%ld, %ld), line %d | %s", i.name, i.type, i.x0, i.z0, w, h, i.age, i.max_age, i.decline,
         i.price, i.cost, okb, bx, by, okl, line);
}

static void rs_click(void *win, BYTE *qo) {
    PFN_rs_info fi = (PFN_rs_info)rs_fn("sc3restore_info");
    PFN_rs_apply fa = (PFN_rs_apply)rs_fn("sc3restore_apply");
    void *occ = *(void **)(qo + 0xd8);
    RS_INFO i;
    char msg[200], cap[64], c[32];
    int es = ho_spanish(), r;
    DWORD a[5];
    if (!fi || !fa || !occ) return;
    memset(&i, 0, sizeof(i));
    i.size = sizeof(i);
    if (!fi(occ, &i)) return;
    if (i.age <= 0) return;                            /* "Como nuevo": nothing to do */
    r = fa(occ, es, msg, sizeof(msg));
    logf("RESTORE> click on %s at (%ld, %ld): %d \"%s\"", i.name, i.x0, i.z0, r, msg);
    rs_money(c, sizeof(c), i.cost);
    if (!r) {                                          /* refused: say so on the button, the dialog stays */
        LONG f = 0;
        PFN_rs_funds ff = (PFN_rs_funds)rs_fn("sc3restore_funds");
        if (ff) f = ff();
        if (f < i.cost) _snprintf(cap, sizeof(cap), es ? "Sin fondos ($%s)" : "No funds ($%s)", c);
        else lstrcpynA(cap, es ? "No se pudo" : "Not done", sizeof(cap));
        cap[sizeof(cap) - 1] = 0;
        lf_caption(win, RS_BTN, cap);
        return;
    }
    g_rs_last.type = i.type; g_rs_last.x0 = i.x0; g_rs_last.z0 = i.z0; g_rs_last.tick = GetTickCount();
    _snprintf(g_rs_last.cap, sizeof(g_rs_last.cap), es ? "Restaurado ($%s)" : "Restored ($%s)", c);
    g_rs_last.cap[sizeof(g_rs_last.cap) - 1] = 0;
    /* Close and reopen from posted messages, so this click is fully handled before its dialog goes. A posted message,
       not a thread timer: the dialog's modal loop dispatched a 150 ms timer 10 s late (measured). */
    (void)a;
    g_rs_close.self = qo + 4; g_rs_close.win = win;
    g_rs_close.cell = (LPARAM)((i.x0 & 0xffff) | ((i.z0 & 0xffff) << 16));
    if (!g_hwnd || !PostMessageA(g_hwnd, WM_RZ_RESTORE, 4, 0)) logf("RESTORE> PostMessage failed: the dialog is not reopened");
}

/* open the query dialog on a cell through the "?" tool's own Apply (SIMGEOM 0x1000b6b4, __thiscall(tool, LONG *coord
   8.8), ret 4; it reads no tool field and sends query command 0x816c8928, whose SIMUI 0x10010c39 opens the dialog
   [CONFIRMED @ SIMGEOM 0x1000b6b4]) */
static void rs_query_cell(LONG x, LONG z) {
    HMODULE g = GetModuleHandleA("SIMGEOM.DLL");
    LONG c[3];
    DWORD a[1], dummy[16];
    c[0] = x << 8; c[1] = z << 8; c[2] = 0;
    memset(dummy, 0, sizeof(dummy));
    a[0] = (DWORD)c;
    if (!g || ((BYTE *)g)[0xb6b4] != 0xb8) { logf("RESTORE> SIMGEOM query Apply not as shipped: no dialog"); return; }
    __try { rz_thiscall_ret(dummy, (BYTE *)g + 0xb6b4, a, 1); }
    __except (EXCEPTION_EXECUTE_HANDLER) { logf("RESTORE> fault opening the query dialog on (%ld, %ld)", x, z); }
}

/* Test message WM_RZ_RESTORE (lab only, nothing on screen asks for it): wParam 1 opens the query dialog on the cell
   lParam = x | z << 16 (rs_query_cell); 4 then 3 are posted by rs_click (close, then reopen); 5 ages the building at
   cell lParam to 60 months before its MaxAge, 6 logs its output (sc3restore test exports); 2 logs the restore button's absolute rect in the last dialog it was added to. */
/* the window manager's focused window (window +4 = manager, manager +0x2c = focus, GZWIND FUN_10020108), for the log */
static void rs_focus_log(const char *when) {
    void *root = NULL, *wm, *f;
    __try {
        root = rz_ui_root();
        if (!root || IsBadReadPtr(root, 8)) { logf("RESTORE> focus (%s): no UI root", when); return; }
        wm = *(void **)((BYTE *)root + 4);
        f = wm ? *(void **)((BYTE *)wm + 0x2c) : NULL;
        logf("RESTORE> focus (%s): manager 0x%08lX focus 0x%08lX%s", when, (DWORD)wm, (DWORD)f,
             f ? (rz_win_alive(f) ? " (live)" : " (NOT in the live tree)") : "");
    } __except (EXCEPTION_EXECUTE_HANDLER) { logf("RESTORE> focus (%s): fault", when); }
}
static void rs_test(WPARAM wp, LPARAM lp) {
    if (wp == 1) {
        rs_query_cell((LONG)(short)LOWORD(lp), (LONG)(short)HIWORD(lp));
        logf("RESTORE> test: query dialog requested on cell (%d, %d)", (short)LOWORD(lp), (short)HIWORD(lp));
    } else if (wp == 3) {   /* the reopen after a restore (rs_click) */
        DWORD t = GetTickCount() - g_rs_last.tick;
        logf("RESTORE> reopening the dialog on (%d, %d), %lu ms after the click", (short)LOWORD(lp), (short)HIWORD(lp), t);
        rs_query_cell((LONG)(short)LOWORD(lp), (LONG)(short)HIWORD(lp));
    } else if (wp == 4) {   /* rs_click, step 1: close the dialog the way its close box does (RELOCATE's rl_click) */
        DWORD a[5];
        void *win = g_rs_close.win;
        BYTE *self = g_rs_close.self;
        g_rs_close.win = NULL; g_rs_close.self = NULL;
        rs_focus_log("before close");
        if (!win || !self || !rz_win_alive(win)) { logf("RESTORE> the dialog is gone already: not reopened"); return; }
        a[0] = (DWORD)win; a[1] = 3; a[2] = 1; a[3] = 0x42b7c353; a[4] = 0;
        rz_thiscall_ret(self, g_orig_338f, a, 5);
        rs_focus_log("after close");
        if (!PostMessageA(g_hwnd, WM_RZ_RESTORE, 3, g_rs_close.cell)) logf("RESTORE> PostMessage failed: the dialog is not reopened");
    } else if (wp == 5 || wp == 6) {   /* TEST ONLY: 5 age the building at cell lp to 60 months before its MaxAge, 6 log its output */
        typedef int (__cdecl *PFN_tl)(LONG, LONG, LONG);
        typedef int (__cdecl *PFN_to)(LONG, LONG);
        LONG x = (LONG)(short)LOWORD(lp), z = (LONG)(short)HIWORD(lp);
        if (wp == 5) { PFN_tl f = (PFN_tl)rs_fn("sc3restore_test_left"); logf("RESTORE> test: age (%ld, %ld) -> %d", x, z, f ? f(x, z, 60) : -1); }
        else { PFN_to f = (PFN_to)rs_fn("sc3restore_test_output"); if (f) f(x, z); }
    } else if (wp == 2) {
        void *b = g_rs_win && rz_win_alive(g_rs_win) ? (void *)ho_v(g_rs_win, 0x78, 1, RS_BTN, 0, 0, 0, 0) : NULL;
        LONG *r = b ? (LONG *)((BYTE *)b + 0x14) : NULL;
        if (r) logf("RESTORE> test: button absolute [%ld %ld %ld %ld]", r[0], r[1], r[2], r[3]);
        else logf("RESTORE> test: no restore button on screen");
        rs_focus_log("test");
    }
}

/* ================= part 2: the Reunirse list page */
#define RM_BTN    0x5E570010              /* "Vida util" on the Reunirse list page */
#define RM_HEAD   0x5E570100
#define RM_ALL    0x5E570101
#define RM_PREV   0x5E570102
#define RM_NEXT   0x5E570103
#define RM_BACK   0x5E570105
#define RM_L1     0x5E570200              /* + row */
#define RM_L2     0x5E570220
#define RM_RB     0x5E570240
#define RM_ROWS   7
#define RM_MAXB   256
typedef int (__cdecl *PFN_rs_list)(RS_INFO *, int, LONG *);
typedef int (__cdecl *PFN_rs_apply_at)(LONG, LONG, DWORD, LONG, int, char *, int);
typedef int (__cdecl *PFN_rs_apply_all)(LONG, int, char *, int);
static void *g_orig_42f7;
static struct {
    void *win;                            /* the list page showing our list, NULL when not */
    void *hidden[128]; int nhidden;       /* the game's windows we hid (children and their children) */
    void *ours[32]; int nours;            /* our widgets on that window, never hidden by the pass */
    RS_INFO rows[RM_MAXB]; int n, page; LONG total;
    char msg[160]; DWORD msg_tick;     /* the last action's result, shown in the header for 8 s */
} g_rm;

static void rm_show(void *win, DWORD id, int on) {
    void *c = (void *)ho_v(win, 0x78, 1, id, 0, 0, 0, 0);
    if (c && !IsBadReadPtr(c, 4)) ho_v(c, 0xf4, 2, 1, on ? 1 : 0, 0, 0, 0);
}

static void rm_reload(void) {
    PFN_rs_list fl = (PFN_rs_list)rs_fn("sc3restore_list");
    g_rm.n = 0; g_rm.total = 0;
    if (!fl) return;
    g_rm.rows[0].size = sizeof(RS_INFO);
    g_rm.n = fl(g_rm.rows, RM_MAXB, &g_rm.total);
    if (g_rm.page * RM_ROWS >= g_rm.n) g_rm.page = g_rm.n ? (g_rm.n - 1) / RM_ROWS : 0;
}

/* write every caption of the page from g_rm (the widgets exist, rm_open made them) */
static void rm_fill(void *win) {
    int es = ho_spanish(), k, pages = g_rm.n ? (g_rm.n + RM_ROWS - 1) / RM_ROWS : 1;
    char t[200], a[24], b[24], c[32];
    PFN_rs_funds ff = (PFN_rs_funds)rs_fn("sc3restore_funds");
    LONG funds = ff ? ff() : 0;
    if (g_rm.msg[0]) lstrcpynA(t, g_rm.msg, sizeof(t));
    else {
        int k2 = 0;
        rs_money(c, sizeof(c), funds);
        k2 = _snprintf(t, sizeof(t), es ? "%d con vida \xfatil. Fondos $%s" : "%d that age. Funds $%s", g_rm.n, c);
        if (pages > 1 && k2 > 0) _snprintf(t + k2, sizeof(t) - k2, es ? ". P\xe1g. %d/%d" : ". Page %d/%d", g_rm.page + 1, pages);
    }
    t[sizeof(t) - 1] = 0;
    lf_caption(win, RM_HEAD, t);
    for (k = 0; k < RM_ROWS; k++) {
        int i = g_rm.page * RM_ROWS + k, on = i < g_rm.n;
        rm_show(win, RM_L1 + k, on); rm_show(win, RM_L2 + k, on); rm_show(win, RM_RB + k, on);
        if (!on) continue;
        _snprintf(t, sizeof(t), "%.40s (%ld, %ld)", g_rm.rows[i].name, g_rm.rows[i].x0, g_rm.rows[i].z0);
        t[sizeof(t) - 1] = 0;
        lf_caption(win, RM_L1 + k, t);
        rs_age(a, sizeof(a), g_rm.rows[i].age, es);
        rs_age(b, sizeof(b), g_rm.rows[i].max_age - g_rm.rows[i].age, es);
        _snprintf(t, sizeof(t), es ? "Edad %s, quedan %s%s" : "Age %s, %s left%s", a, b,
                  g_rm.rows[i].aging ? (es ? " (decae)" : " (declining)") : "");
        t[sizeof(t) - 1] = 0;
        lf_caption(win, RM_L2 + k, t);
        rs_money(c, sizeof(c), g_rm.rows[i].cost);
        if (g_rm.rows[i].age <= 0) lstrcpynA(t, es ? "Como nuevo" : "As new", sizeof(t));
        else _snprintf(t, sizeof(t), es ? "Restaurar $%s" : "Restore $%s", c);
        t[sizeof(t) - 1] = 0;
        lf_caption(win, RM_RB + k, t);
    }
    rs_money(c, sizeof(c), g_rm.total);
    _snprintf(t, sizeof(t), es ? "Restaurar todos ($%s)" : "Restore all ($%s)", c);
    t[sizeof(t) - 1] = 0;
    lf_caption(win, RM_ALL, t);
    rm_show(win, RM_PREV, pages > 1); rm_show(win, RM_NEXT, pages > 1);
    ho_v(win, 0x154, 0, 0, 0, 0, 0, 0);   /* invalidate */
}

/* the list page's own windows: hide everything below the title bar, children and their children, and keep a list to
   show them again. The petition rows the game adds while our list is up come up visible and painted over our rows
   (measured): rm_42f7 runs this again after every message to the page. */
static void rm_hide_tree(void *win, int depth) {
    BYTE *w = (BYTE *)win;
    void *head = *(void **)(w + 0x34), *n;
    int guard = 0;
    if (depth > 4) return;
    n = (head && !IsBadReadPtr(head, 4)) ? *(void **)head : NULL;
    while (n && n != head && guard++ < 80 && !IsBadReadPtr(n, 0x0c)) {
        BYTE *ch = *(BYTE **)((BYTE *)n + 8);
        if (ch && !IsBadReadPtr(ch, 0xa4)) {
            LONG *cl = (LONG *)(ch + 0x80);
            int k, mine = 0;
            for (k = 0; k < g_rm.nours; k++) if (g_rm.ours[k] == ch) { mine = 1; break; }
            if (!mine && (depth > 0 || cl[1] >= 36)) {
                rm_hide_tree(ch, depth + 1);
                if ((*(DWORD *)(ch + 0xa0) & 1) && g_rm.nhidden < 128) {
                    g_rm.hidden[g_rm.nhidden++] = ch;
                    ho_v(ch, 0xf4, 2, 1, 0, 0, 0, 0);
                }
            }
        }
        n = *(void **)n;
    }
}
static void rm_hide_game(void *win) { g_rm.nhidden = 0; rm_hide_tree(win, 0); }
/* our widgets on the window, by id (vt+0x78 FindChild) */
static void rm_collect_ours(void *win) {
    DWORD ids[32];
    int n = 0, k;
    ids[n++] = RM_BTN; ids[n++] = RM_HEAD; ids[n++] = RM_ALL; ids[n++] = RM_PREV; ids[n++] = RM_NEXT; ids[n++] = RM_BACK;
    for (k = 0; k < RM_ROWS; k++) { ids[n++] = RM_L1 + k; ids[n++] = RM_L2 + k; ids[n++] = RM_RB + k; }
    g_rm.nours = 0;
    for (k = 0; k < n && g_rm.nours < 32; k++) {
        void *c = (void *)ho_v(win, 0x78, 1, ids[k], 0, 0, 0, 0);
        if (c) g_rm.ours[g_rm.nours++] = c;
    }
}

static void rm_open(void *win) {
    HMODULE sui = GetModuleHandleA("SIMUI.DLL");
    void *fac;
    LONG *l = (LONG *)((BYTE *)win + 0x80), w, h, bw, y;
    int es = ho_spanish(), k, ok = 0, keep = g_ho_lblcol;
    if (!sui) return;
    fac = ((void *(__cdecl *)(void))((BYTE *)sui + 0x85065))();
    if (!fac || IsBadReadPtr(fac, 4)) return;
    w = l[2] - l[0]; h = l[3] - l[1];
    g_rm.page = 0; g_rm.msg[0] = 0;
    rm_reload();
    rm_collect_ours(win);
    rm_hide_game(win);
    rm_show(win, RM_BTN, 0);
    if (!ho_v(win, 0x78, 1, RM_HEAD, 0, 0, 0, 0)) {   /* first time on this window: make the widgets */
        bw = 132;
        g_ho_lblcol = 1;
        ok += ho_add_label(fac, win, RM_HEAD, " ", 14, 42, w - 28);
        for (k = 0; k < RM_ROWS; k++) {
            y = 64 + k * 34;
            ok += ho_add_label(fac, win, RM_L1 + k, " ", 14, y, w - 28 - bw - 6);
            ok += ho_add_label(fac, win, RM_L2 + k, " ", 14, y + 15, w - 28 - bw - 6);
            ok += mp_button(fac, win, RM_RB + k, " ", w - 14 - bw, y + 2, bw, 26);
        }
        g_ho_lblcol = keep;
        y = h - 42;
        ok += mp_button(fac, win, RM_ALL, " ", 8, y, 196, QI_BH);
        ok += mp_button(fac, win, RM_PREV, "<", 210, y, 36, QI_BH);
        ok += mp_button(fac, win, RM_NEXT, ">", 250, y, 36, QI_BH);
        ok += mp_button(fac, win, RM_BACK, es ? "Volver" : "Back", w - 8 - 76, y, 76, QI_BH);
        logf("RESTORE> Reunirse page %ldx%ld: %d widgets made", w, h, ok);
    } else {
        rm_show(win, RM_HEAD, 1); rm_show(win, RM_ALL, 1); rm_show(win, RM_BACK, 1);
    }
    g_rm.win = win;
    rm_collect_ours(win);
    rm_fill(win);
    logf("RESTORE> Reunirse list on: %d building(s), total %ld, %d game children hidden", g_rm.n, g_rm.total, g_rm.nhidden);
}

static void rm_close(void *win) {
    int k;
    static const DWORD ids[] = { RM_HEAD, RM_ALL, RM_PREV, RM_NEXT, RM_BACK };
    for (k = 0; k < (int)(sizeof(ids) / sizeof(ids[0])); k++) rm_show(win, ids[k], 0);
    for (k = 0; k < RM_ROWS; k++) { rm_show(win, RM_L1 + k, 0); rm_show(win, RM_L2 + k, 0); rm_show(win, RM_RB + k, 0); }
    for (k = g_rm.nhidden - 1; k >= 0; k--) if (rz_win_alive(g_rm.hidden[k])) ho_v(g_rm.hidden[k], 0xf4, 2, 1, 1, 0, 0, 0);
    g_rm.nhidden = 0;
    rm_show(win, RM_BTN, 1);
    g_rm.win = NULL;
    ho_v(win, 0x154, 0, 0, 0, 0, 0, 0);
    logf("RESTORE> Reunirse list off (Volver)");
}

/* 1 = the click was ours */
static int rm_click(void *win, DWORD id) {
    int es = ho_spanish();
    char msg[200];
    if (id == RM_BTN) { rm_open(win); return 1; }
    if (g_rm.win != win) return 0;
    if (id == RM_BACK) { rm_close(win); return 1; }
    if (id == RM_PREV || id == RM_NEXT) {
        int pages = g_rm.n ? (g_rm.n + RM_ROWS - 1) / RM_ROWS : 1;
        g_rm.page = (g_rm.page + (id == RM_NEXT ? 1 : pages - 1)) % pages;
        g_rm.msg[0] = 0;
        rm_fill(win);
        return 1;
    }
    if (id == RM_ALL) {
        PFN_rs_apply_all fa = (PFN_rs_apply_all)rs_fn("sc3restore_apply_all");
        int r = fa ? fa(g_rm.total, es, msg, sizeof(msg)) : 0;
        logf("RESTORE> Reunirse: restore all -> %d \"%s\"", r, msg);
        rm_reload();
        lstrcpynA(g_rm.msg, msg, sizeof(g_rm.msg));
        g_rm.msg_tick = GetTickCount();
        rm_fill(win);
        return 1;
    }
    if (id >= RM_RB && id < RM_RB + RM_ROWS) {
        PFN_rs_apply_at fa = (PFN_rs_apply_at)rs_fn("sc3restore_apply_at");
        int i = g_rm.page * RM_ROWS + (int)(id - RM_RB), r;
        char nm[64];
        if (i >= g_rm.n || !fa) return 1;
        if (g_rm.rows[i].age <= 0) return 1;
        lstrcpynA(nm, g_rm.rows[i].name, sizeof(nm));
        r = fa(g_rm.rows[i].x0, g_rm.rows[i].z0, g_rm.rows[i].type, g_rm.rows[i].cost, es, msg, sizeof(msg));
        logf("RESTORE> Reunirse: row %d %s at (%ld, %ld) -> %d \"%s\"", i, nm, g_rm.rows[i].x0, g_rm.rows[i].z0, r, msg);
        rm_reload();
        _snprintf(g_rm.msg, sizeof(g_rm.msg), "%.40s: %s", nm, msg);
        g_rm.msg[sizeof(g_rm.msg) - 1] = 0;
        g_rm.msg_tick = GetTickCount();
        rm_fill(win);
        return 1;
    }
    return 0;
}

/* the "Vida util" button, left of the close box, on the title bar row */
static void rm_add_button(void *win) {
    HMODULE sui = GetModuleHandleA("SIMUI.DLL");
    void *fac;
    LONG *l = (LONG *)((BYTE *)win + 0x80), w;
    int ok;
    if (!sui || !win || IsBadReadPtr(win, 0xa4) || ho_v(win, 0x78, 1, RM_BTN, 0, 0, 0, 0)) return;
    if (!rs_fn("sc3restore_list")) return;
    fac = ((void *(__cdecl *)(void))((BYTE *)sui + 0x85065))();
    if (!fac || IsBadReadPtr(fac, 4)) return;
    w = l[2] - l[0];
    if (g_rm.win == win) { g_rm.win = NULL; g_rm.nhidden = 0; }   /* a new page at a reused address */
    ok = mp_button(fac, win, RM_BTN, ho_spanish() ? "Vida \xfatil" : "Lifespan", w - 34 - 84, 8, 84, 24);
    logf("RESTORE> Reunirse list page 0x%08lX %ldx%ld: \"Vida util\" button %s", (DWORD)win, w, l[3] - l[1], ok ? "added" : "FAILED");
}

/* the list page's message handler, SIMUI FUN_100042f7: __thiscall with FIVE stack args, `ret 0x14` at 0x10004402 (Ghidra
   shows four; a 4-arg detour unbalanced the stack and the game died on the next Reunirse open, measured 2026-11-02) */
static DWORD __fastcall rm_42f7(void *self, void *edx, DWORD win, DWORD msg, DWORD p3, DWORD p4, DWORD p5) {
    DWORD a[5], r;
    (void)edx;
    if (g_restore && msg == 3 && p3 == 1 && win && rm_click((void *)win, p4)) return 1;
    if (msg == 0xa2bf8acf && (void *)win == g_rm.win) { g_rm.win = NULL; g_rm.nhidden = 0; }   /* page closing */
    a[0] = win; a[1] = msg; a[2] = p3; a[3] = p4; a[4] = p5;
    r = rz_thiscall_ret(self, g_orig_42f7, a, 5);
    if (g_restore && msg == 0xa2bf8ace && win) rm_add_button((void *)win);
    if (g_rm.win && msg != 0xa2bf8acf && rz_win_alive(g_rm.win)) {   /* new petition rows come up visible: hide them too */
        int before = g_rm.nhidden;
        rm_hide_tree(g_rm.win, 0);
        if (g_rm.nhidden != before) {
            logf("RESTORE> Reunirse: %d more game window(s) hidden after message 0x%08lX", g_rm.nhidden - before, msg);
            ho_v(g_rm.win, 0x154, 0, 0, 0, 0, 0, 0);
        }
        if (msg == 0x22c05b3f) {   /* the page's periodic refresh (about every 5 s): ages, prices, funds */
            if (g_rm.msg[0] && GetTickCount() - g_rm.msg_tick > 8000) g_rm.msg[0] = 0;
            rm_reload(); rm_fill(g_rm.win);
        }
    }
    return r;
}

static void rm_install(HMODULE sui) {
    static const BYTE e42f7[6] = { 0x55, 0x8b, 0xec, 0x83, 0xec, 0x20 };   /* push ebp; mov ebp,esp; sub esp,0x20 */
    if (!g_restore) { logf("RESTORE> off (SC3RESIZE_RESTORE=0)"); return; }
    if (ho_hook(sui, 0x42f7, e42f7, 6, (void *)rm_42f7, &g_orig_42f7, "Reunirse list page messages FUN_100042f7"))
        logf("RESTORE> on: \"Restaurar\" in the query dialog, \"Vida util\" on the Reunirse list page");
}
