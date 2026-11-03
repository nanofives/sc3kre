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
    DWORD flags;                      /* RS_DEAD / RS_BADDATE (restorefix 2026-11-02) */
    DWORD key[3];                     /* attrib key, what the building tool places */
    DWORD jdn;
} RS_INFO;
#define RS_DEAD    1u                 /* = SC3R_DEAD: rubble of an expired building (keeps class, type, name, key) */
#define RS_BADDATE 2u                 /* = SC3R_BADDATE: alive, birthdate broken (the 11-02c recycling-center bug) */
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
    if (months % 12) _snprintf(out, cap, SC3TR(es, "lifespan.y_m", "%lda %ldm", "%ldy %ldm"), months / 12, months % 12);
    else _snprintf(out, cap, SC3TR(es, "lifespan.y", "%lda", "%ldy"), months / 12);
    out[cap - 1] = 0;
}

static void rs_line(const RS_INFO *i, int es, char *out, int cap) {
    char a[24], m[24], l[24];
    if (i->flags & RS_DEAD) {
        _snprintf(out, cap, SC3TR(es, "lifespan.end_its_life_can", "Fin de su vida \xfatil: se puede reconstruir", "End of its life: it can be rebuilt"));
        out[cap - 1] = 0; return;
    }
    if (i->flags & RS_BADDATE) {
        _snprintf(out, cap, SC3TR(es, "lifespan.date_damaged_free_repair", "Fecha da\xf1" "ada: reparaci\xf3n gratis", "Date damaged: free repair"));
        out[cap - 1] = 0; return;
    }
    rs_age(a, sizeof(a), i->age, es);
    rs_age(m, sizeof(m), i->max_age, es);
    rs_age(l, sizeof(l), i->max_age - i->age, es);
    _snprintf(out, cap, SC3TR(es, "lifespan.age_left", "Edad %s de %s, le quedan %s%s", "Age %s of %s, %s left%s"), a, m, l,
              i->aging ? (SC3TR(es, "lifespan.declining", " (decayendo)", " (declining)")) : "");
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
    else if ((i->flags & (RS_DEAD | RS_BADDATE)) == (RS_DEAD | RS_BADDATE)) _snprintf(out, cap, SC3TR(es, "lifespan.rebuild_free", "Reconstruir (gratis)", "Rebuild (free)"));
    else if (i->flags & RS_DEAD) { rs_money(c, sizeof(c), i->price); _snprintf(out, cap, SC3TR(es, "lifespan.rebuild", "Reconstruir $%s", "Rebuild $%s"), c); }
    else if (i->flags & RS_BADDATE) _snprintf(out, cap, SC3TR(es, "lifespan.repair_free", "Reparar (gratis)", "Repair (free)"));
    else if (i->age <= 0) _snprintf(out, cap, SC3TR(es, "lifespan.as_new", "Como nuevo", "As new"));
    else _snprintf(out, cap, SC3TR(es, "lifespan.restore", "Restaurar $%s", "Restore $%s"), c);
    out[cap - 1] = 0;
}

/* window vt+0xf4(2, on): flag 2 = enabled (mp_button sets it; a cleared one draws grey and takes no click) */
static void rs_enable(void *win, DWORD id, int on) {
    void *c = (void *)ho_v(win, 0x78, 1, id, 0, 0, 0, 0);
    if (c && !IsBadReadPtr(c, 4)) ho_v(c, 0xf4, 2, 2, on ? 1 : 0, 0, 0, 0);
}

/* ================= SUSTFONT (round restoreui 2026-11-02, owner: "Sustituir must use the same font as the other buttons").
 * The game makes "Sustituir" from a window template {0x75807649, 0x22ba0121} with id 4, caption string 300 of group
 * 0x41f2625, only when qo+0xd6 is set [CONFIRMED @ SIMUI 0x1006260e]; every other button of the dialog is a factory text
 * button (+0x2c), the QUERYID recipe. So the template button is hidden and a factory text button takes its place: same id
 * 4 (the dialog's handler acts on message 3 with p4 4 as before), same parent-local rect, same enabled flag, and the same
 * caption object (a window keeps its caption string at +0x44, GZWIND FUN_1001fa6c called from the SetCaption slot
 * vt+0x10c 0x100088f9). SC3RESIZE_SUSTFONT=0: the game's button stays. */
static void *g_rs_ours[8];              /* the last replacements made (FindChild(4) may hand back ours) */
static int g_rs_oursn;
static void rs_sust(void *win) {
    HMODULE sui = GetModuleHandleA("SIMUI.DLL");
    BYTE *g, *bw;
    void *fac, *btn;
    LONG *r;
    DWORD fl;
    int ok = 0;
    if (!sui || !win || IsBadReadPtr(win, 0xa4)) return;
    g = (BYTE *)ho_v(win, 0x78, 1, 4, 0, 0, 0, 0);
    if (!g || IsBadReadPtr(g, 0x58)) return;
    {   int k;   /* hidden = done already; one of ours = done already */
        if (!(*(DWORD *)(g + 0xa0) & 1)) return;
        for (k = 0; k < 8; k++) if (g_rs_ours[k] == g) return;
    }
    fac = ((void *(__cdecl *)(void))((BYTE *)sui + 0x85065))();
    if (!fac || IsBadReadPtr(fac, 4)) return;
    r = (LONG *)(g + 0x80); fl = *(DWORD *)(g + 0xa0);
    btn = (void *)ho_v(fac, 0x2c, 5, 4, (DWORD)(g + 0x44), 0, 0, 0);
    if (!btn) { logf("SUSTFONT> factory text button failed: the game's button stays"); return; }
    ho_v(btn, 0x24, 2, 4, 1, 0, 0, 0);
    ho_v(btn, 0x24, 2, 0x20, 0, 0, 0, 0);
    bw = (BYTE *)ho_v(btn, 0x1c, 0, 0, 0, 0, 0, 0);
    /* the game's window has the factory text button's class too (measured: same vtable); what differs is what the
       template sets on it (its font), so a fresh factory button is what reads like "Copiar ID" */
    if (bw) { g_rs_ours[g_rs_oursn++ & 7] = bw; if (*(DWORD *)bw == *(DWORD *)g) logf("SUSTFONT> the game's button has the factory text button's class: only its template settings differ"); }
    ho_v(bw, 0x10c, 1, (DWORD)(g + 0x44), 0, 0, 0, 0);
    ho_v(bw, 0xc8, 4, (DWORD)r[0], (DWORD)r[1], (DWORD)r[2], (DWORD)r[3], 0);
    ho_v(bw, 0xf4, 2, 2, (fl & 2) ? 1 : 0, 0, 0, 0);
    ok = (int)(ho_v(win, 0x34, 1, (DWORD)bw, 0, 0, 0, 0) & 0xff);
    if (!ok) ho_v(bw, 0x28, 0, 0, 0, 0, 0, 0);
    ho_v(btn, 0x08, 0, 0, 0, 0, 0, 0);
    if (ok) ho_v(g, 0xf4, 2, 1, 0, 0, 0, 0);                   /* the template one hidden */
    logf("SUSTFONT> \"Sustituir\" (window %s+0x%lX, flags 0x%lX) local [%ld %ld %ld %ld]: %s", "GZWIND",
         *(DWORD *)g - (DWORD)GetModuleHandleA("GZWIND.DLL"), fl, r[0], r[1], r[2], r[3],
         ok ? "redone as a factory text button, id 4" : "FAILED, the game's button stays");
}

static void rs_query_cell(LONG x, LONG z);   /* below */
static struct { BYTE *self; void *win; LPARAM cell; } g_rs_close;   /* the dialog to close and reopen (rs_click) */
#define WM_RZ_RESTORE (WM_APP + 0x5F8)

/* ================= restorefix (round 2026-11-02b), each block with its own off switch SC3RESIZE_<NAME>=0:
 *   REBUILD   "Reconstruir $N" in the "?" of a dead building and on its row of the Vida util list
 *   RSTITLE   the list page's title reads "Vida Util" while the list is up (the game's own title window and font)
 *   RSARROWS  "<" ">" as 24x25 image buttons cut from the close box's art (were 40 px text buttons whose pills overlap)
 *   RSHG2     the hourglass redrawn as pixel art (off = the 11-02c drawing) */
static int g_rs_strip = 1;   /* SC3RESIZE_RSSTRIP=0: no continuous footer band */
static int g_rs_rebuild = 1, g_rs_title = 1, g_rs_arrows = 1, g_rs_hg2 = 1, g_rs_fix_init;
static void rs_fix_init(void) {
    char v[8];
    if (g_rs_fix_init) return;
    g_rs_fix_init = 1;
    if (GetEnvironmentVariableA("SC3RESIZE_REBUILD", v, sizeof(v))) g_rs_rebuild = atoi(v);
    if (GetEnvironmentVariableA("SC3RESIZE_RSTITLE", v, sizeof(v))) g_rs_title = atoi(v);
    if (GetEnvironmentVariableA("SC3RESIZE_RSARROWS", v, sizeof(v))) g_rs_arrows = atoi(v);
    if (GetEnvironmentVariableA("SC3RESIZE_RSSTRIP", v, sizeof(v))) g_rs_strip = atoi(v);
    if (GetEnvironmentVariableA("SC3RESIZE_RSHG2", v, sizeof(v))) g_rs_hg2 = atoi(v);
    logf("RESTOREFIX> REBUILD %d, RSTITLE %d, RSARROWS %d, RSHG2 %d", g_rs_rebuild, g_rs_title, g_rs_arrows, g_rs_hg2);
}

/* the rubble's info (sc3restore_dead): 1 = occ is a dead building with a lifespan */
static int rs_dead(void *occ, RS_INFO *i) {
    PFN_rs_info fd = (PFN_rs_info)rs_fn("sc3restore_dead");
    memset(i, 0, sizeof(*i));
    i->size = sizeof(*i);
    return g_rs_rebuild && fd && occ && fd(occ, i);
}

/* ================= REBUILD (restorefix 2026-11-02b, owner: "i also want a feature to rebuild the same building that got
 * destroyed in that place"). A building with a lifespan that dies leaves rubble of its own class, type, name and attrib key
 * (SIMECO 0x100035f7 makes it through the building layer from the same attrib, state 8, Kill; SIMUTIL 0x1000690c the same
 * for plants), so the rubble says what stood there. The rebuild is the game's own check + place, SIMGEOM 0x10006ba6 through
 * the building layer's (city vt+0x138) CanPlace / Place slots for the tool kind of the key (the factory 0x10007e64 picks the
 * tool by key {0x207edc0e, 0x57e, inst}: inst 1 = kind 1, 0xdc/0xeb/0xf4/0xfa = kind 2, 0x3e8a/0xe9 = kind 3, else kind 0;
 * the four tools call +0x24..+0x30 / +0x38..+0x44 [CONFIRMED @ SIMGEOM 0x1000970f, 0x10009f7f, 0x100099eb, 0x10009d3f]),
 * at the rubble's first cell, coord {x << 8, z << 8, 0} (the min corner: 0x10006ba6 adds (size - 1) * 0x100 for the far one).
 * Not free: the stock check prices it (build price + clearing + levelling) and the stock Place refuses when funds are short
 * and withdraws the cost itself. The rubble itself is a building (GeomFlag 0x104) that the stock site check refuses, so the
 * call runs inside RELOCATE's context with the rubble as "the occupant being moved": the cave at 0x100076b4 accepts it at no
 * price and the commit detour at 0x10007760 removes it (DemolishOccupant, no rubble) just before the stock insert. A refused
 * spot removes nothing. Needs the RELOCATE hooks (in unless SC3RESIZE_RELOCATE=0 and SC3RESIZE_PLOPOVER=0). */
static int rb_kind(const DWORD *k) {
    if (k[0] == 0x207edc0e && k[1] == 0x57e) {
        if (k[2] == 1) return 1;
        if (k[2] == 0x3e8a || k[2] == 0xe9) return 3;
        if (k[2] == 0xdc || k[2] == 0xeb || k[2] == 0xf4 || k[2] == 0xfa) return 2;
        if (k[2] == 0x1f98 || k[2] == 0x1f8b || k[2] == 0x1f5d) return -1;   /* multi-cell / random variants: not here */
    }
    return 0;
}
/* 1 placed, 0 refused (msg says why), *paid = what the game withdrew */
static int rb_rebuild(void *occ, const RS_INFO *i, int es, char *msg, int cap, LONG *paid) {
    BYTE *city = rl_city();
    void *bl, *bud, *o2 = NULL, *om;
    LONG coord[3], bounds[6], funds, f1;
    DWORD cost = 0, a[5], r = 0, t2 = 0;
    int kind, k, placed = 0;
    /* FREE for a building the 11-02c restore bug killed (dead with a birthdate GetAge cannot make sense of, RS_BADDATE;
       the owner already paid for that restore; orchestrator call 2026-11-02): Place with the game's free flag, so the
       stock commit withdraws nothing and does not test funds (SIMGEOM 0x10006ba6). Any other dead building: PAID. */
    int freeb = (i->flags & (RS_DEAD | RS_BADDATE)) == (RS_DEAD | RS_BADDATE);
    char c1[32], c2[32];
    msg[0] = 0; *paid = 0;
    if (!g_rs_rebuild) return 0;
    if (!city || !g_rl_geom || !g_rl_orig[0] || !g_rl_7760_ret) {
        _snprintf(msg, cap, SC3TR(es, "lifespan.not_available_mover_off", "No disponible (Mover desactivado)", "Not available (Mover is off)"));
        logf("REBUILD> refused: the RELOCATE hooks are not in (SC3RESIZE_RELOCATE=0 and SC3RESIZE_PLOPOVER=0?)");
        return 0;
    }
    if (g_rl.on || g_rl_occ) {
        _snprintf(msg, cap, SC3TR(es, "lifespan.move_in_progress", "Hay una mudanza en curso", "A move is in progress"));
        logf("REBUILD> refused: a Mover is pending (occupant 0x%08lX)", (DWORD)g_rl_occ);
        return 0;
    }
    kind = rb_kind(i->key);
    if (!i->key[0] || kind < 0) {
        _snprintf(msg, cap, SC3TR(es, "lifespan.cannot_be_rebuilt", "No se puede reconstruir", "Cannot be rebuilt"));
        logf("REBUILD> refused: key 0x%08lX 0x%08lX 0x%08lX (kind %d)", i->key[0], i->key[1], i->key[2], kind);
        return 0;
    }
    bl = (void *)ho_v(city, 0x138, 0, 0, 0, 0, 0, 0);
    bud = (void *)ho_v(city, 0x15c, 0, 0, 0, 0, 0, 0);
    if (!bl || !bud) return 0;
    funds = (LONG)ho_v(bud, 0x10, 0, 0, 0, 0, 0, 0);
    coord[0] = i->x0 << 8; coord[1] = i->z0 << 8; coord[2] = 0;
    g_rl_occ = occ; g_rl_city = city; g_rl_tool = NULL; g_rl_type = i->type;
    g_rl_cell[0] = i->x0; g_rl_cell[1] = i->z0; g_rl_cell[2] = i->x1; g_rl_cell[3] = i->z1;
    g_rl.on = 1; g_rl.reloc = 1; g_rl.n = 0; g_rl.clr = g_rl.zon = 0; g_rl.tid = GetCurrentThreadId();
    __try {
        for (k = 0; k < 6; k++) bounds[k] = 0x7fffffff;
        a[0] = (DWORD)coord; a[1] = (DWORD)i->key; a[2] = (DWORD)bounds; a[3] = (DWORD)&cost;
        r = rz_thiscall_ret(bl, (void *)g_rl_orig[kind], a, 4) & 0xff;            /* CanPlace, as the tool's Apply */
        if (r && !freeb && (LONG)cost > funds) {
            rs_money(c1, sizeof(c1), (LONG)cost); rs_money(c2, sizeof(c2), funds);
            _snprintf(msg, cap, SC3TR(es, "lifespan.not_enough_funds_costs", "Fondos insuficientes: cuesta $%s, hay $%s", "Not enough funds: costs $%s, you have $%s"), c1, c2);
            r = 2;
        } else if (r) {
            DWORD pcost = 0;
            g_rl.n = 0; g_rl.clr = g_rl.zon = 0;
            for (k = 0; k < 6; k++) bounds[k] = 0x7fffffff;
            a[0] = (DWORD)coord; a[1] = (DWORD)i->key; a[2] = (DWORD)bounds; a[3] = (DWORD)&pcost; a[4] = (DWORD)freeb;   /* free only for the bug's victims */
            placed = (int)(rz_thiscall_ret(bl, (void *)g_rl_orig[4 + kind], a, 5) & 0xff);   /* Place: the stock commit */
            cost = pcost;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) { logf("REBUILD> fault 0x%08lX in the check / place", GetExceptionCode()); placed = 0; }
    g_rl.on = 0; g_rl.reloc = 0; g_rl.n = 0;
    g_rl_occ = NULL; g_rl_city = NULL; g_rl_type = 0;
    f1 = (LONG)ho_v(bud, 0x10, 0, 0, 0, 0, 0, 0);
    om = (void *)ho_v(city, 0x11c, 0, 0, 0, 0, 0, 0);
    if (om && (ho_v(om, 0x7c, 3, (DWORD)i->x0, (DWORD)i->z0, (DWORD)&o2, 0, 0) & 0xff) && o2) {
        t2 = ho_v(o2, 0x88, 0, 0, 0, 0, 0, 0);
        if (o2 == occ) t2 = 0;
        ho_v(o2, 0x08, 0, 0, 0, 0, 0, 0);
    }
    logf("REBUILD> %s (type %lu, key 0x%08lX 0x%08lX 0x%08lX, kind %d) at cells [%ld %ld %ld %ld]: %s; check %s, place %s, "
         "cost %lu, funds %ld -> %ld; now at (%ld, %ld): %s type %lu", i->name, i->type, i->key[0], i->key[1], i->key[2], kind,
         i->x0, i->z0, i->x1, i->z1,
         freeb ? "FREE (died from the 11-02c restore bug: broken birthdate, the owner paid for that restore)"
               : "PAID (died of old age: the build price)",
         r == 1 ? "ok" : r == 2 ? "ok but funds short" : "REFUSED", placed ? "done" : "not done",
         cost, funds, f1, i->x0, i->z0, t2 == i->type ? "the new building" : "NOT the new building", t2);
    if (placed && t2 == i->type) {
        *paid = funds - f1;
        rs_money(c1, sizeof(c1), *paid);
        if (freeb && *paid == 0) _snprintf(msg, cap, SC3TR(es, "lifespan.rebuilt_for_free", "Reconstruido sin costo", "Rebuilt for free"));
        else _snprintf(msg, cap, SC3TR(es, "lifespan.rebuilt_for", "Reconstruido por $%s", "Rebuilt for $%s"), c1);
        return 1;
    }
    if (!msg[0]) _snprintf(msg, cap, SC3TR(es, "lifespan.cannot_build_there", "No se puede construir ah\xed", "Cannot build there"));
    return 0;
}
/* the rubble at (x0, z0) of that type: rebuild it (the list's row button) */
static int rb_rebuild_at(LONG x0, LONG z0, DWORD type, int es, char *msg, int cap) {
    BYTE *city = rl_city();
    void *om = city ? (void *)ho_v(city, 0x11c, 0, 0, 0, 0, 0, 0) : NULL, *o = NULL;
    RS_INFO i;
    LONG paid;
    int r = 0;
    msg[0] = 0;
    if (!om || !(ho_v(om, 0x7c, 3, (DWORD)x0, (DWORD)z0, (DWORD)&o, 0, 0) & 0xff) || !o) {
        _snprintf(msg, cap, SC3TR(es, "lifespan.gone", "Ya no est\xe1", "It is gone")); return 0;
    }
    if (ho_v(o, 0x88, 0, 0, 0, 0, 0, 0) == type && rs_dead(o, &i) && i.x0 == x0 && i.z0 == z0) r = rb_rebuild(o, &i, es, msg, cap, &paid);
    else _snprintf(msg, cap, SC3TR(es, "lifespan.no_longer_rubble", "Ya no est\xe1 en ruinas", "No longer rubble"));
    ho_v(o, 0x08, 0, 0, 0, 0, 0, 0);
    return r;
}

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
    if (!fi(occ, &i) && !rs_dead(occ, &i)) return;   /* REBUILD: a dead one gets "Reconstruir $price" */
    fac = ((void *(__cdecl *)(void))((BYTE *)sui + 0x85065))();
    if (!fac || IsBadReadPtr(fac, 4)) return;
    w = l[2] - l[0]; h = l[3] - l[1];
    by = h - 0x25 + (32 - QI_BH) / 2;
    bx = w - 0x32 - 8 - RS_BW - (g_queryid ? QI_BW + 8 : 0);
    if (bx < 8 || !rl_rect_free(win, bx, by, bx + RS_BW, by + QI_BH)) { bx = w - 8 - RS_BW; by -= QI_BH + 6; }
    rs_caption(&i, es, cap, sizeof(cap));
    okb = mp_button(fac, win, RS_BTN, cap, bx, by, RS_BW, QI_BH);
    if (okb) g_rs_win = win;
    if (okb && g_rs_grey && i.age <= 0 && !(i.flags & (RS_DEAD | RS_BADDATE)))
        rs_enable(win, RS_BTN, 0);   /* RSGREY: "Como nuevo" / "Restaurado" grey, not clickable */
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
    if (!fi(occ, &i)) {
        LONG paid = 0;
        if (!rs_dead(occ, &i)) return;
        /* REBUILD: the rubble's "Reconstruir"; on success the dialog is closed and opened again on the new building */
        r = rb_rebuild(occ, &i, es, msg, sizeof(msg), &paid);
        logf("REBUILD> click on %s at (%ld, %ld): %d \"%s\"", i.name, i.x0, i.z0, r, msg);
        rs_money(c, sizeof(c), r ? paid : i.price);
        if (!r) {
            LONG f = 0;
            PFN_rs_funds ff = (PFN_rs_funds)rs_fn("sc3restore_funds");
            if (ff) f = ff();
            if (!(i.flags & RS_BADDATE) && f < i.price) _snprintf(cap, sizeof(cap), SC3TR(es, "lifespan.no_funds", "Sin fondos ($%s)", "No funds ($%s)"), c);
            else lstrcpynA(cap, SC3TR(es, "lifespan.not_done", "No se pudo", "Not done"), sizeof(cap));
            cap[sizeof(cap) - 1] = 0;
            lf_caption(win, RS_BTN, cap);
            return;
        }
        g_rs_last.type = i.type; g_rs_last.x0 = i.x0; g_rs_last.z0 = i.z0; g_rs_last.tick = GetTickCount();
        _snprintf(g_rs_last.cap, sizeof(g_rs_last.cap), SC3TR(es, "lifespan.rebuilt", "Reconstruido ($%s)", "Rebuilt ($%s)"), c);
        g_rs_last.cap[sizeof(g_rs_last.cap) - 1] = 0;
        g_rs_close.self = qo + 4; g_rs_close.win = win;
        g_rs_close.cell = (LPARAM)((i.x0 & 0xffff) | ((i.z0 & 0xffff) << 16));
        if (!g_hwnd || !PostMessageA(g_hwnd, WM_RZ_RESTORE, 4, 0)) logf("RESTORE> PostMessage failed: the dialog is not reopened");
        return;
    }
    if (i.age <= 0 && !(i.flags & RS_BADDATE)) return; /* "Como nuevo": nothing to do */
    r = fa(occ, es, msg, sizeof(msg));
    logf("RESTORE> click on %s at (%ld, %ld): %d \"%s\"", i.name, i.x0, i.z0, r, msg);
    rs_money(c, sizeof(c), i.cost);
    if (r && (i.flags & RS_BADDATE)) lstrcpynA(c, "0", sizeof(c));
    if (!r) {                                          /* refused: say so on the button, the dialog stays */
        LONG f = 0;
        PFN_rs_funds ff = (PFN_rs_funds)rs_fn("sc3restore_funds");
        if (ff) f = ff();
        if (f < i.cost) _snprintf(cap, sizeof(cap), SC3TR(es, "lifespan.no_funds", "Sin fondos ($%s)", "No funds ($%s)"), c);
        else lstrcpynA(cap, SC3TR(es, "lifespan.not_done", "No se pudo", "Not done"), sizeof(cap));
        cap[sizeof(cap) - 1] = 0;
        lf_caption(win, RS_BTN, cap);
        return;
    }
    g_rs_last.type = i.type; g_rs_last.x0 = i.x0; g_rs_last.z0 = i.z0; g_rs_last.tick = GetTickCount();
    _snprintf(g_rs_last.cap, sizeof(g_rs_last.cap), SC3TR(es, "lifespan.restored", "Restaurado ($%s)", "Restored ($%s)"), c);
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

/* ================= QROWS (round restoreui 2026-11-02, owner: "more data on buildings in the ? dialog").
 * Sources: re/sessions/restoreui_query_rows_research.md. The dialog's rows are a list object at qo+0x100 (factory clsid
 * 0x584, built by FUN_10062bc1); the game fills it when the dialog sends {0x2dc6d7f, 0x2dcc206} to the occupant and the
 * city's layers (FUN_1006330b, dialog vt+0x18), each class adding its rows through the list interface (QI 0x583) vt+0x4c
 * FUN_100645bf(label, value, flags, red): the row is kept when (list+0x28 & flags) != 0, the label is navy
 * (0x30,0x30,0x7f) or red [CONFIRMED @ SIMUI 0x100645bf, 0x1006330b]. Our rows go in the same way, after the game's.
 * Flags 0x20000, the bit the game's plant / hospital / school rows use.
 * Rows (only what the game does not show already, every value read, none computed beyond a sum or a percent):
 *   any building with a build price   "Coste de obra"           budget (city vt+0x15c) vt+0x54(type id)  [SIMGEOM 0x100072f6]
 *   any building with a lifespan      "Decae desde" DeclineAge, "Vida restante" MaxAge - age  (IBuildingMortal 0x43680ca9
 *                                       vt+0x18 / +0x10 / +0x1c, re/analysis/RESTORE.md)
 *   a SIMUTIL power plant             "Rendimiento" output vt+0x3c as a percent of base vt+0x38 (falls from DeclineAge,
 *                                       SIMUTIL 0x100069fb), "Meses en sobrecarga" u16 at mortal+0x10 (breakdown test,
 *                                       SIMUTIL 0x10006c27)
 *   a hospital (SIMRCI vt 0x1004b548)  "Camas (este)" occ+0x24, "Medicos (este)" occ+0x28  [SIMRCI 0x1000790d, 0x10006c12]
 *   a school (SIMRCI vt 0x1004be08)    "Profesores (esta)" occ+0x24                          [SIMRCI 0x1000b726]
 *   a college (SIMRCI vt 0x1004b2a8)   "Profesores (esta)" occ+0x24                        [SIMRCI 0x100063c6]
 * The game's own hospital / school rows are the systemwide figures (city vt+0x17c), so these are the per-building ones.
 * SC3RESIZE_QROWS=0: no rows added. */
#define QR_FLAGS 0x20000u
static int qr_row(void *li, const char *label, const char *value) {
    BYTE a[0x20], b[0x20];
    DWORD r;
    ho_str(a, label); ho_str(b, value);
    r = ho_v(li, 0x4c, 4, (DWORD)a, (DWORD)b, QR_FLAGS, 0, 0);
    ho_str_free(a); ho_str_free(b);
    return (int)(r & 0xff);
}
/* The dialog does not grow for rows added after its build: its size is set once, the row list's window keeps its rect
   (measured: 308x395, list SIMUI+0xAAF64 at local [20 188 300 355]) and the rows past its bottom are not drawn, or sit
   under the restore button. So the dialog grows by the rows (QR_ROWH each, measured on the game's single-line rows) plus,
   when a button goes on the row above the bottom one (RESTORE when the bottom row is full, or RELOCATE's "Mover" already
   moved up), that row: the list window stretches, every child below the list moves down, a child spanning it (the left
   bar) stretches, and the dialog keeps inside the client (moved up when it would pass its bottom). Window vt+0xc8 =
   parent-local SetRect (memory project-simui-window-model). */
#define QR_ROWH 14
static void qr_grow(void *win, BYTE *occ, int nrows) {
    BYTE *w = (BYTE *)win, *list = NULL;
    LONG *l = (LONG *)(w + 0x80), lb = 0, dy, extra = 0, h = l[3] - l[1], top = l[1];
    void *head = *(void **)(w + 0x34), *n;
    DWORD lvt = (DWORD)GetModuleHandleA("SIMUI.DLL") + 0xaaf64;
    int guard = 0, moved = 0;
    RECT cr;
    n = (head && !IsBadReadPtr(head, 4)) ? *(void **)head : NULL;
    while (n && n != head && guard++ < 60 && !IsBadReadPtr(n, 0x0c)) {
        BYTE *ch = *(BYTE **)((BYTE *)n + 8);
        if (ch && !IsBadReadPtr(ch, 0xa4) && *(DWORD *)ch == lvt) { list = ch; lb = ((LONG *)(ch + 0x80))[3]; }
        n = *(void **)n;
    }
    if (!list) { logf("QROWS> no row list window (SIMUI+0xAAF64) among the dialog's children: not grown"); return; }
    {   /* the action row above the bottom row: Mover already up there, or a restore button about to go there */
        BYTE *mv = (BYTE *)ho_v(win, 0x78, 1, RL_BTN, 0, 0, 0, 0);
        PFN_rs_info fi = (PFN_rs_info)rs_fn("sc3restore_info");
        RS_INFO i;
        LONG by = h - 0x25 + (32 - QI_BH) / 2;
        if (mv && !IsBadReadPtr(mv, 0xa4) && ((LONG *)(mv + 0x80))[1] < by - 2) extra = QI_BH + 6;
        memset(&i, 0, sizeof(i)); i.size = sizeof(i);
        if (!extra && g_restore && fi && ((fi(occ, &i) && !i.defunct) || rs_dead(occ, &i))) {
            LONG bx = (l[2] - l[0]) - 0x32 - 8 - RS_BW - (g_queryid ? QI_BW + 8 : 0);
            if (bx < 8 || !rl_rect_free(win, bx, by, bx + RS_BW, by + QI_BH)) extra = QI_BH + 6;
        }
    }
    dy = nrows * QR_ROWH + extra;
    guard = 0;
    n = (head && !IsBadReadPtr(head, 4)) ? *(void **)head : NULL;
    while (n && n != head && guard++ < 60 && !IsBadReadPtr(n, 0x0c)) {
        BYTE *ch = *(BYTE **)((BYTE *)n + 8);
        if (ch && !IsBadReadPtr(ch, 0xa4)) {
            LONG *c = (LONG *)(ch + 0x80);
            if (ch == list) ho_v(ch, 0xc8, 4, (DWORD)c[0], (DWORD)c[1], (DWORD)c[2], (DWORD)(c[3] + nrows * QR_ROWH), 0);
            else if (c[1] >= lb - 2) { ho_v(ch, 0xc8, 4, (DWORD)c[0], (DWORD)(c[1] + dy), (DWORD)c[2], (DWORD)(c[3] + dy), 0); moved++; }
            else if (c[3] > lb) ho_v(ch, 0xc8, 4, (DWORD)c[0], (DWORD)c[1], (DWORD)c[2], (DWORD)(c[3] + dy), 0);
        }
        n = *(void **)n;
    }
    if (g_hwnd && GetClientRect(g_hwnd, &cr) && top + h + dy > cr.bottom) top = cr.bottom - (h + dy) < 0 ? 0 : cr.bottom - (h + dy);
    ho_v(win, 0xc8, 4, (DWORD)l[0], (DWORD)top, (DWORD)l[2], (DWORD)(top + h + dy), 0);
    ho_v(win, 0x154, 0, 0, 0, 0, 0, 0);
    logf("QROWS> dialog grown by %ld (%d row(s) x %d%s): %ldx%ld at top %ld, list bottom %ld -> %ld, %d child(ren) moved down",
         dy, nrows, QR_ROWH, extra ? " + the action row" : "", l[2] - l[0], l[3] - l[1], l[1], lb, lb + nrows * QR_ROWH, moved);
}

static void rs_qrows(void *win, BYTE *qo) {
    BYTE *occ = *(BYTE **)(qo + 0xd8), *city = rl_city(), *list = *(BYTE **)(qo + 0x100);
    HMODULE rci = GetModuleHandleA("SIMRCI.DLL"), util = GetModuleHandleA("SIMUTIL.DLL");
    void *li = NULL, *mo = NULL, *bud;
    DWORD type = 0, rva = 0, ovt;
    char v[96], m1[32], m2[32];
    int es = ho_spanish(), n = 0, tried = 0;
    (void)win;
    if (!occ || !city || !list || IsBadReadPtr(occ, 0x40) || IsBadReadPtr(list, 4)) return;
    __try {
        if (!(ho_v(list, 0x00, 2, 0x583, (DWORD)&li, 0, 0, 0) & 0xff) || !li || IsBadReadPtr(li, 0x2c)) {
            logf("QROWS> the row list at qo+0x100 does not answer 0x583: no rows"); return;
        }
        ovt = *(DWORD *)occ;
        type = ho_v(occ, 0x88, 0, 0, 0, 0, 0, 0);
        {   const char *mn = qi_mod_of(ovt, &rva);
            logf("QROWS> occupant type %lu vtable %s+0x%lX, row mask 0x%08lX", type, mn, rva, *(DWORD *)((BYTE *)li + 0x28)); }
        /* build value */
        bud = (void *)ho_v(city, 0x15c, 0, 0, 0, 0, 0, 0);
        if (bud && type) {
            LONG price = (LONG)ho_v(bud, 0x54, 1, type, 0, 0, 0, 0);
            if (price > 0) {
                rs_money(m1, sizeof(m1), price);
                _snprintf(v, sizeof(v), "$%s", m1); v[sizeof(v) - 1] = 0;
                tried++; n += qr_row(li, SC3TR(es, "lifespan.build_cost", "Coste de obra:", "Build cost:"), v);
            }
        }
        /* lifespan */
        if ((ho_v(occ, 0x00, 2, 0x43680ca9, (DWORD)&mo, 0, 0, 0) & 0xff) && mo && !IsBadReadPtr(mo, 0x14)) {
            LONG mx = (LONG)ho_v(mo, 0x10, 0, 0, 0, 0, 0, 0), dc = (LONG)ho_v(mo, 0x18, 0, 0, 0, 0, 0, 0);
            LONG age = (LONG)ho_v(mo, 0x1c, 0, 0, 0, 0, 0, 0), dead = (LONG)(ho_v(mo, 0x28, 0, 0, 0, 0, 0, 0) & 0xff);
            DWORD *mvt = *(DWORD **)mo;
            if (!dead && mx > 0 && mx < 100000 && dc >= 0 && dc <= mx) {
                rs_age(m1, sizeof(m1), dc, es);
                _snprintf(v, sizeof(v), SC3TR(es, "lifespan.age", "%s de edad%s", "age %s%s"), m1, age >= dc ? (SC3TR(es, "lifespan.declining_now", " (ya decae)", " (declining now)")) : "");
                v[sizeof(v) - 1] = 0;
                tried++; n += qr_row(li, SC3TR(es, "lifespan.declines_from", "Decae desde:", "Declines from:"), v);
                rs_age(m2, sizeof(m2), mx - age, es);
                tried++; n += qr_row(li, SC3TR(es, "lifespan.life_left", "Vida restante:", "Life left:"), m2);
            }
            /* a SIMUTIL plant (the output pair as sc3restore's plant_output checks it) */
            if (!dead && util && mvt[0x3c / 4] == (DWORD)util + 0x2563 && mvt[0x38 / 4] == (DWORD)util + 0x6b67) {
                LONG now = *(LONG *)((BYTE *)mo + 8), base = *(LONG *)((BYTE *)mo + 0xc);
                WORD ow = *(WORD *)((BYTE *)mo + 0x10);
                if (base > 0) {
                    _snprintf(v, sizeof(v), "%ld%%", (LONG)(((__int64)now * 100 + base / 2) / base)); v[sizeof(v) - 1] = 0;
                    tried++; n += qr_row(li, SC3TR(es, "lifespan.output", "Rendimiento:", "Output:"), v);
                }
                _snprintf(v, sizeof(v), "%u", (unsigned)ow); v[sizeof(v) - 1] = 0;
                tried++; n += qr_row(li, SC3TR(es, "lifespan.months_overworked", "Meses en sobrecarga:", "Months overworked:"), v);
            }
            ho_v(mo, 0x08, 0, 0, 0, 0, 0, 0);
            mo = NULL;
        }
        /* per-building health / education staff */
        if (rci && ovt == (DWORD)rci + 0x4b548) {
            _snprintf(v, sizeof(v), "%lu", *(DWORD *)(occ + 0x24)); v[sizeof(v) - 1] = 0;
            tried++; n += qr_row(li, SC3TR(es, "lifespan.beds_this_one", "Camas (este):", "Beds (this one):"), v);
            _snprintf(v, sizeof(v), "%lu", *(DWORD *)(occ + 0x28)); v[sizeof(v) - 1] = 0;
            tried++; n += qr_row(li, SC3TR(es, "lifespan.doctors_this_one", "M\xe9" "dicos (este):", "Doctors (this one):"), v);
        } else if (rci && ovt == (DWORD)rci + 0x4be08) {
            _snprintf(v, sizeof(v), "%lu", *(DWORD *)(occ + 0x24)); v[sizeof(v) - 1] = 0;
            tried++; n += qr_row(li, SC3TR(es, "lifespan.teachers_this_one", "Profesores (esta):", "Teachers (this one):"), v);
        } else if (rci && ovt == (DWORD)rci + 0x4b2a8) {
            _snprintf(v, sizeof(v), "%lu", *(DWORD *)(occ + 0x24)); v[sizeof(v) - 1] = 0;
            tried++; n += qr_row(li, SC3TR(es, "lifespan.professors_this_one", "Profesores (esta):", "Professors (this one):"), v);
        }
        logf("QROWS> %d of %d row(s) added", n, tried);
        if (n > 0) qr_grow(win, occ, n);
    } __except (EXCEPTION_EXECUTE_HANDLER) { logf("QROWS> fault 0x%08lX", GetExceptionCode()); }
    if (mo) ho_v(mo, 0x08, 0, 0, 0, 0, 0, 0);
    if (li) ho_v(li, 0x08, 0, 0, 0, 0, 0, 0);
}

/* TEST (WM_RZ_RESTORE 7): one cell per occupant vtable over the map (SIMRCI / SIMSERV classes), to find a hospital,
   school or station to query. Surface occupant manager city vt+0x11c, GetOccupantAtCell vt+0x7c AddRefs. */
static void rs_scan_classes(void) {
    BYTE *city = rl_city();
    void *om;
    DWORD seen[64], x, z;
    int ns = 0, k;
    if (!city || !(om = (void *)ho_v(city, 0x11c, 0, 0, 0, 0, 0, 0))) { logf("QROWS> scan: no city"); return; }
    for (z = 0; z < 256; z++)
        for (x = 0; x < 256; x++) {
            void *o = NULL;
            DWORD vt, rva = 0;
            const char *mn;
            __try {
                if (!(ho_v(om, 0x7c, 3, x, z, (DWORD)&o, 0, 0) & 0xff) || !o) continue;
                vt = *(DWORD *)o;
                for (k = 0; k < ns; k++) if (seen[k] == vt) break;
                if (k == ns && ns < 64) {
                    seen[ns++] = vt;
                    mn = qi_mod_of(vt, &rva);
                    if (!lstrcmpiA(mn, "SIMRCI.DLL") || !lstrcmpiA(mn, "SIMSERV.DLL") || !lstrcmpiA(mn, "SIMECO.DLL"))
                        logf("QROWS> scan: %s+0x%lX type %lu at (%lu, %lu)", mn, rva, ho_v(o, 0x88, 0, 0, 0, 0, 0, 0), x, z);
                }
                ho_v(o, 0x08, 0, 0, 0, 0, 0, 0);
            } __except (EXCEPTION_EXECUTE_HANDLER) { }
        }
    logf("QROWS> scan done: %d occupant classes", ns);
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
    } else if (wp == 8) {   /* TEST ONLY (restorefix): age the building at cell lp to one month past its MaxAge, so the game kills it */
        typedef int (__cdecl *PFN_tl)(LONG, LONG, LONG);
        PFN_tl f = (PFN_tl)rs_fn("sc3restore_test_left");
        LONG x = (LONG)(short)LOWORD(lp), z = (LONG)(short)HIWORD(lp);
        logf("RESTORE> test: age (%ld, %ld) past its life -> %d", x, z, f ? f(x, z, -1) : -1);
    } else if (wp == 10) {  /* TEST ONLY (restorefix): break the birthdate at cell lp as the 11-02c bug did */
        typedef int (__cdecl *PFN_tb)(LONG, LONG);
        PFN_tb f = (PFN_tb)rs_fn("sc3restore_test_break");
        LONG x = (LONG)(short)LOWORD(lp), z = (LONG)(short)HIWORD(lp);
        logf("RESTORE> test: break the date at (%ld, %ld) -> %d", x, z, f ? f(x, z) : -1);
    } else if (wp == 9) {   /* TEST ONLY (restorefix): one Vida util list scan, for its log (and the type -> key table it learns) */
        typedef int (__cdecl *PFN_ls)(RS_INFO *, int, LONG *);
        static RS_INFO rows[512];
        LONG tot = 0;
        PFN_ls fl = (PFN_ls)rs_fn("sc3restore_list");
        rows[0].size = sizeof(RS_INFO);
        logf("RESTORE> test: list scan -> %d row(s)", fl ? fl(rows, 512, &tot) : -1);
    } else if (wp == 7) {
        rs_scan_classes();
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
#define RM_STRIP  0x5E570110              /* RSSTRIP: flat light-blue shape behind the whole footer row */
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

static int rs_img_btn(void *fac, void *win, DWORD id, int glyph, LONG x, LONG y, const char *tip, LONG *fw_out);   /* RSARROWS, below */
static void rs_title(void *win, int on);                                                                       /* RSTITLE, below */
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
/* RSSTRIP: a flat filled rect from the game's shape window (class 0x4303E5B6 / 0xE303E5AE, style 0x31 via vt_rect),
   colour = the colour service's converted 16-bit value (a raw 0xRRGGBB drew dark red) of the footer boxes' light blue (120, 144, 248, measured on the boxes).
   Disabled so a click falls through to the parent. 1 = added. Page-local (x, y). */
static int rs_flat(void *win, DWORD id, int x, int y, int w, int h) {
    HMODULE sui = GetModuleHandleA("SIMUI.DLL");
    void *cs, *sw;
    if (!sui) return 0;
    cs = ((void *(__cdecl *)(void))((BYTE *)sui + 0x85039))();
    if (!cs) return 0;
    vt_rect(win, id, (WORD)(ho_v(cs, 0x84, 3, 120, 144, 248, 0, 0) & 0xffff), x, y, w, h);   /* VDTABS recipe: style 0x31 = filled (0x11 only strokes) */
    sw = mp_child(win, id);
    if (!sw) return 0;
    ho_v(sw, 0xf4, 2, 2, 0, 0, 0, 0);   /* disabled: a click falls through to the parent */
    return 1;
}

static void rm_fill(void *win) {
    int es = ho_spanish(), k, pages = g_rm.n ? (g_rm.n + RM_ROWS - 1) / RM_ROWS : 1;
    char t[200], a[24], b[24], c[32];
    PFN_rs_funds ff = (PFN_rs_funds)rs_fn("sc3restore_funds");
    LONG funds = ff ? ff() : 0;
    if (g_rm.msg[0]) lstrcpynA(t, g_rm.msg, sizeof(t));
    else {
        int k2 = 0, nd = 0, j;
        for (j = 0; j < g_rm.n; j++) if (g_rm.rows[j].flags & RS_DEAD) nd++;
        rs_money(c, sizeof(c), funds);
        if (nd) k2 = _snprintf(t, sizeof(t), SC3TR(es, "lifespan.that_age_dead", "%d con vida \xfatil, %d en ruinas. $%s", "%d that age, %d dead. $%s"), g_rm.n - nd, nd, c);
        else k2 = _snprintf(t, sizeof(t), SC3TR(es, "lifespan.that_age_funds", "%d con vida \xfatil. Fondos $%s", "%d that age. Funds $%s"), g_rm.n, c);
        if (pages > 1 && k2 > 0) _snprintf(t + k2, sizeof(t) - k2, SC3TR(es, "lifespan.page", ". P\xe1g. %d/%d", ". Page %d/%d"), g_rm.page + 1, pages);
    }
    t[sizeof(t) - 1] = 0;
    lf_caption(win, RM_HEAD, t);
    for (k = 0; k < RM_ROWS; k++) {
        int i = g_rm.page * RM_ROWS + k, on = i < g_rm.n;
        rm_show(win, RM_L1 + k, on); rm_show(win, RM_L2 + k, on); rm_show(win, RM_RB + k, on);
        if (!on) continue;
        if (g_rm.rows[i].flags & (RS_DEAD | RS_BADDATE)) {   /* restorefix: rubble -> Reconstruir, broken date -> Reparar */
            int dead = (g_rm.rows[i].flags & RS_DEAD) != 0;
            /* line 1 as the live rows (a label wraps past about 41 characters and the wrapped part is not drawn, measured:
               "Central Termica de Carbon (59, 164), en ruinas" lost "ruinas"), the state on line 2 */
            _snprintf(t, sizeof(t), "%.40s (%ld, %ld)", g_rm.rows[i].name, g_rm.rows[i].x0, g_rm.rows[i].z0);
            t[sizeof(t) - 1] = 0;
            lf_caption(win, RM_L1 + k, t);
            rs_money(c, sizeof(c), g_rm.rows[i].price);
            if (dead && (g_rm.rows[i].flags & RS_BADDATE))   /* killed by the 11-02c bug: free */
                lstrcpynA(t, SC3TR(es, "lifespan.dead_date_damaged_free", "En ruinas (fecha da\xf1" "ada). Gratis", "Dead (date damaged). Free"), sizeof(t));
            else if (dead) _snprintf(t, sizeof(t), SC3TR(es, "lifespan.dead_rebuild", "En ruinas. Reconstruir: $%s", "Dead. Rebuild: $%s"), c);
            else lstrcpynA(t, SC3TR(es, "lifespan.date_damaged_free_repair", "Fecha da\xf1" "ada: reparaci\xf3n gratis", "Date damaged: free repair"), sizeof(t));
            t[sizeof(t) - 1] = 0;
            lf_caption(win, RM_L2 + k, t);
            lf_caption(win, RM_RB + k, dead ? (SC3TR(es, "lifespan.rebuild_2", "Reconstruir", "Rebuild")) : (SC3TR(es, "lifespan.repair", "Reparar", "Repair")));
            rs_enable(win, RM_RB + k, dead ? g_rs_rebuild : 1);
            continue;
        }
        /* RSLAYOUT: the price moves from the (narrower) button to the second line, "decae" to the first (a label wraps
           past about 41 characters and the wrapped part is not shown, measured: "... (decae). $7,080" lost its price) */
        if (g_rs_layout && g_rm.rows[i].aging)
            _snprintf(t, sizeof(t), SC3TR(es, "lifespan.declining_2", "%.40s (%ld, %ld), decae", "%.40s (%ld, %ld), declining"), g_rm.rows[i].name,
                      g_rm.rows[i].x0, g_rm.rows[i].z0);
        else _snprintf(t, sizeof(t), "%.40s (%ld, %ld)", g_rm.rows[i].name, g_rm.rows[i].x0, g_rm.rows[i].z0);
        t[sizeof(t) - 1] = 0;
        lf_caption(win, RM_L1 + k, t);
        rs_age(a, sizeof(a), g_rm.rows[i].age, es);
        rs_age(b, sizeof(b), g_rm.rows[i].max_age - g_rm.rows[i].age, es);
        rs_money(c, sizeof(c), g_rm.rows[i].cost);
        if (g_rs_layout && g_rm.rows[i].age > 0)
            _snprintf(t, sizeof(t), SC3TR(es, "lifespan.age_left_2", "Edad %s, quedan %s. $%s", "Age %s, %s left. $%s"), a, b, c);
        else if (g_rs_layout)
            _snprintf(t, sizeof(t), SC3TR(es, "lifespan.age_left_3", "Edad %s, quedan %s", "Age %s, %s left"), a, b);
        else
            _snprintf(t, sizeof(t), SC3TR(es, "lifespan.age_left_4", "Edad %s, quedan %s%s", "Age %s, %s left%s"), a, b,
                      g_rm.rows[i].aging ? (SC3TR(es, "lifespan.declining_3", " (decae)", " (declining)")) : "");
        t[sizeof(t) - 1] = 0;
        lf_caption(win, RM_L2 + k, t);
        if (g_rm.rows[i].age <= 0 && g_rs_layout) lstrcpynA(t, SC3TR(es, "lifespan.new", "Nuevo", "New"), sizeof(t));   /* "Como nuevo" is wider than the 92 px pill */
        else if (g_rm.rows[i].age <= 0) lstrcpynA(t, SC3TR(es, "lifespan.as_new", "Como nuevo", "As new"), sizeof(t));
        else if (g_rs_layout) lstrcpynA(t, SC3TR(es, "lifespan.restore_2", "Restaurar", "Restore"), sizeof(t));
        else _snprintf(t, sizeof(t), SC3TR(es, "lifespan.restore", "Restaurar $%s", "Restore $%s"), c);
        t[sizeof(t) - 1] = 0;
        lf_caption(win, RM_RB + k, t);
        if (g_rs_grey) rs_enable(win, RM_RB + k, g_rm.rows[i].age > 0);   /* RSGREY */
    }
    rs_money(c, sizeof(c), g_rm.total);
    _snprintf(t, sizeof(t), SC3TR(es, "lifespan.restore_all", "Restaurar todos ($%s)", "Restore all ($%s)"), c);
    t[sizeof(t) - 1] = 0;
    lf_caption(win, RM_ALL, t);
    if (g_rs_layout) {   /* RSLAYOUT: one page = the arrows grey, not hidden, so the footer strip stays unbroken */
        rm_show(win, RM_PREV, 1); rm_show(win, RM_NEXT, 1);
        rs_enable(win, RM_PREV, pages > 1); rs_enable(win, RM_NEXT, pages > 1);
    } else { rm_show(win, RM_PREV, pages > 1); rm_show(win, RM_NEXT, pages > 1); }
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
    ids[n++] = RM_BTN; ids[n++] = RM_HEAD; ids[n++] = RM_ALL; ids[n++] = RM_PREV; ids[n++] = RM_NEXT; ids[n++] = RM_BACK; ids[n++] = RM_STRIP;
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
    if (!ho_v(win, 0x78, 1, RM_HEAD, 0, 0, 0, 0) && g_rs_layout) {   /* first time on this window: make the widgets */
        /* RSLAYOUT (round restoreui 2026-11-02, owner: "the list buttons are too wide; light blue behind them and in the gaps
           between the footer buttons"). A factory text button fills its whole rect with its background colour (factory
           colour 0xb, set through window vt+0x178 by the factory, GZWIND 0x1000b6b2 / 0x1001fb67) and draws its pill inside;
           its box is QI_BH (33) tall whatever height it is given (measured: rows given 26 drew 33). So the light blue is
           made unbroken by butting the boxes: rows 33 apart (was 34, a 1 px seam), the footer buttons edge to edge from
           x 8 to w - 8 (were 6 and 4 px apart). Row buttons 92 wide (QI_BW, as "Copiar ID"; were 132) read "Restaurar",
           the price moves to the row's second line. */
        LONG yb, xa, wa;
        bw = QI_BW;
        g_ho_lblcol = 1;
        ok += ho_add_label(fac, win, RM_HEAD, " ", 14, 42, w - 28);
        for (k = 0; k < RM_ROWS; k++) {
            y = 64 + k * QI_BH;
            ok += ho_add_label(fac, win, RM_L1 + k, " ", 14, y + 1, w - 8 - bw - 6 - 14);
            ok += ho_add_label(fac, win, RM_L2 + k, " ", 14, y + 16, w - 8 - bw - 6 - 14);
            ok += mp_button(fac, win, RM_RB + k, " ", w - 8 - bw, y, bw, QI_BH);
        }
        g_ho_lblcol = keep;
        yb = h - 42;
        if (g_rs_arrows) {
            /* RSARROWS (restorefix, owner: "'<' '>' smaller, they overlap", shot 1793660447360): a text button's pill is
               wider than 40 px and the next box paints over its right end, so the arrows are 24x25 image buttons cut from
               the close box's art (bevel and state frames as the X), 6 px apart, centred on the footer row */
            LONG aw = 24, gap = 6, ya = yb + (QI_BH - 25) / 2, xp;
            int oa;
            wa = w - 16 - 84 - (3 * gap + 2 * aw);
            xa = 8;
            if (g_rs_strip) ok += rs_flat(win, RM_STRIP, 8, yb, w - 16, QI_BH);   /* RSSTRIP: created first = under every footer button */
            ok += mp_button(fac, win, RM_ALL, " ", xa, yb, wa, QI_BH);                xa += wa;
            xp = xa + gap;
            oa = rs_img_btn(fac, win, RM_PREV, 1, xp, ya, SC3TR(es, "lifespan.previous", "Anterior", "Previous"), &aw);
            oa += rs_img_btn(fac, win, RM_NEXT, 2, xp + aw + gap, ya, SC3TR(es, "lifespan.next", "Siguiente", "Next"), NULL);
            if (oa < 2) {   /* no art: the text buttons in the same strip */
                logf("RSARROWS> image buttons not made (%d of 2): text buttons", oa);
                if (!ho_v(win, 0x78, 1, RM_PREV, 0, 0, 0, 0)) ok += mp_button(fac, win, RM_PREV, "<", xa, yb, gap + aw + gap / 2, QI_BH);
                if (!ho_v(win, 0x78, 1, RM_NEXT, 0, 0, 0, 0)) ok += mp_button(fac, win, RM_NEXT, ">", xa + gap + aw + gap / 2, yb, aw + gap + gap / 2, QI_BH);
            } else ok += oa;
            xa += 3 * gap + 2 * aw;
            ok += mp_button(fac, win, RM_BACK, SC3TR(es, "lifespan.back", "Volver", "Back"), xa, yb, w - 8 - xa, QI_BH);
        } else {
        wa = w - 16 - 40 - 40 - 84;
        xa = 8;
        ok += mp_button(fac, win, RM_ALL, " ", xa, yb, wa, QI_BH);                xa += wa;
        ok += mp_button(fac, win, RM_PREV, "<", xa, yb, 40, QI_BH);               xa += 40;
        ok += mp_button(fac, win, RM_NEXT, ">", xa, yb, 40, QI_BH);               xa += 40;
        ok += mp_button(fac, win, RM_BACK, SC3TR(es, "lifespan.back", "Volver", "Back"), xa, yb, w - 8 - xa, QI_BH);
        }
        logf("RESTORE> Reunirse page %ldx%ld: %d widgets made (RSLAYOUT: rows %d wide, footer edge to edge 8..%ld)", w, h, ok,
             (int)bw, w - 8);
    } else if (!ho_v(win, 0x78, 1, RM_HEAD, 0, 0, 0, 0)) {   /* SC3RESIZE_RSLAYOUT=0: the 11-02 layout */
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
        ok += mp_button(fac, win, RM_BACK, SC3TR(es, "lifespan.back", "Volver", "Back"), w - 8 - 76, y, 76, QI_BH);
        logf("RESTORE> Reunirse page %ldx%ld: %d widgets made", w, h, ok);
    } else {
        rm_show(win, RM_HEAD, 1); rm_show(win, RM_ALL, 1); rm_show(win, RM_BACK, 1); rm_show(win, RM_STRIP, 1);
    }
    g_rm.win = win;
    rm_collect_ours(win);
    rs_title(win, 1);                                    /* RSTITLE */
    rm_fill(win);
    logf("RESTORE> Reunirse list on: %d building(s), total %ld, %d game children hidden", g_rm.n, g_rm.total, g_rm.nhidden);
}

static void rm_close(void *win) {
    int k;
    static const DWORD ids[] = { RM_HEAD, RM_ALL, RM_PREV, RM_NEXT, RM_BACK, RM_STRIP };
    for (k = 0; k < (int)(sizeof(ids) / sizeof(ids[0])); k++) rm_show(win, ids[k], 0);
    for (k = 0; k < RM_ROWS; k++) { rm_show(win, RM_L1 + k, 0); rm_show(win, RM_L2 + k, 0); rm_show(win, RM_RB + k, 0); }
    for (k = g_rm.nhidden - 1; k >= 0; k--) if (rz_win_alive(g_rm.hidden[k])) ho_v(g_rm.hidden[k], 0xf4, 2, 1, 1, 0, 0, 0);
    g_rm.nhidden = 0;
    rm_show(win, RM_BTN, 1);
    rs_title(win, 0);                                    /* RSTITLE: the game's title back */
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
        if (g_rm.rows[i].age <= 0 && !(g_rm.rows[i].flags & (RS_DEAD | RS_BADDATE))) return 1;
        lstrcpynA(nm, g_rm.rows[i].name, sizeof(nm));
        if (g_rm.rows[i].flags & RS_DEAD)    /* REBUILD */
            r = rb_rebuild_at(g_rm.rows[i].x0, g_rm.rows[i].z0, g_rm.rows[i].type, es, msg, sizeof(msg));
        else
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

/* ================= RSICON (round restoreui 2026-11-02, owner: "the Vida util button must be an icon, as tall as the X").
 * The close box is an image button (window vtable GZWIND+0x2b190, ctor 0x1000810d). Its art is kept at window +0x118 and
 * the source rect of its first frame at +0xfc..+0x108 (stored by the image-button slot 0x1000901e that SetImage
 * 0x10008559 calls; SetImage modes 2..5 cut the art into 4 frames side by side, 6..7 into 8) [CONFIRMED @ GZWIND
 * 0x1000901e, 0x10008559]. The art is a 4x4 sheet of 24x25 frames (rows: close, back, minimise, maximise; measured).
 * The icon is the minimise row with its bar replaced by an hourglass: per frame the glyph's outline box is found from its
 * dark pixels, the inside of the box is painted back row by row in the face's own colour (bevel, outline and the greyed /
 * pressed / hover shading stay the stock ones), and the hourglass is drawn inside it in the outline's colour (4x4
 * subsamples), about the size of the cross. The
 * image button is the factory's (+0x30), as sc3resize's picker makes its minimap button. Tooltip "Vida util". */
static char g_fd_prefix[MAX_PATH];            /* (tentative definition: FRAMEDUMP defines it further down) */
static void rs_unpack(WORD v, DWORD code, int *r, int *g, int *b) {
    if (code == 7) { *r = (v >> 11) << 3; *g = ((v >> 5) & 63) << 2; *b = (v & 31) << 3; }
    else           { *r = ((v >> 10) & 31) << 3; *g = ((v >> 5) & 31) << 3; *b = (v & 31) << 3; }
}
static WORD rs_pack(int r, int g, int b, DWORD code) {
    if (r < 0) r = 0; if (g < 0) g = 0; if (b < 0) b = 0; if (r > 255) r = 255; if (g > 255) g = 255; if (b > 255) b = 255;
    return code == 7 ? (WORD)(((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)) : (WORD)(((r >> 3) << 10) | ((g >> 3) << 5) | (b >> 3));
}
static int rs_lum(WORD v, DWORD code) { int r, g, b; rs_unpack(v, code, &r, &g, &b); return (r * 3 + g * 6 + b) / 10; }
static double rs_seg2(double px, double py, double ax, double ay, double bx, double by) {
    double dx = bx - ax, dy = by - ay, t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy);
    if (t < 0) t = 0; if (t > 1) t = 1;
    dx = ax + t * dx - px; dy = ay + t * dy - py;
    return dx * dx + dy * dy;
}
/* the hourglass in the box (x0, y0, w, h), pixel units: two bars, the glass's four sides, sand in the lower bulb */
static int rs_hourglass(double px, double py, double x0, double y0, double w, double h) {
    double u = (px - x0) / w, v = (py - y0) / h, cx = x0 + w / 2, cy = y0 + h / 2, t = w < 10 ? 0.62 : 0.8;
    double ax = x0 + w * 0.2, bx = x0 + w * 0.8, ty = y0 + h * 0.14, by = y0 + h * 0.86, du = u < 0.5 ? 0.5 - u : u - 0.5;
    if (u < -0.02 || u > 1.02 || v < -0.02 || v > 1.02) return 0;
    if ((v <= 0.14 || v >= 0.86) && u >= 0.04 && u <= 0.96) return 1;
    if (rs_seg2(px, py, ax, ty, cx, cy) <= t * t || rs_seg2(px, py, bx, ty, cx, cy) <= t * t) return 1;
    if (rs_seg2(px, py, ax, by, cx, cy) <= t * t || rs_seg2(px, py, bx, by, cx, cy) <= t * t) return 1;
    if (v >= 0.66 && v < 0.86 && du <= (v - 0.5) * 0.85) return 1;   /* sand */
    return 0;
}
static void rs_dump_strip(const char *leaf, const BYTE *b, LONG p, LONG w, LONG hh, DWORD code) {
    char path[MAX_PATH];
    LONG rs = (w * 3 + 3) & ~3, x, y;
    BYTE *out;
    BITMAPFILEHEADER fh; BITMAPINFOHEADER ih; HANDLE f; DWORD wr;
    if (!g_fd_prefix[0] || !(out = (BYTE *)calloc(rs, hh))) return;
    for (y = 0; y < hh; y++) for (x = 0; x < w; x++) {
        int r, g, bb;
        BYTE *o = out + (hh - 1 - y) * rs + x * 3;
        rs_unpack(*(const WORD *)(b + y * p + x * 2), code, &r, &g, &bb);
        o[2] = (BYTE)r; o[1] = (BYTE)g; o[0] = (BYTE)bb;
    }
    memset(&fh, 0, sizeof(fh)); memset(&ih, 0, sizeof(ih));
    fh.bfType = 0x4d42; fh.bfOffBits = sizeof(fh) + sizeof(ih); fh.bfSize = fh.bfOffBits + rs * hh;
    ih.biSize = sizeof(ih); ih.biWidth = w; ih.biHeight = hh; ih.biPlanes = 1; ih.biBitCount = 24;
    wsprintfA(path, "%s%s.bmp", g_fd_prefix, leaf);
    f = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
    if (f != INVALID_HANDLE_VALUE) { WriteFile(f, &fh, sizeof(fh), &wr, NULL); WriteFile(f, &ih, sizeof(ih), &wr, NULL); WriteFile(f, out, rs * hh, &wr, NULL); CloseHandle(f); }
    free(out);
}
/* the close box of a page: the rightmost image-button child (vtable GZWIND+0x2b190) of its title bar, the child at local
   top 4 (measured on the Reunirse page: title bar SIMUI+0xA4B1C local [4 4 379 35], the page's own children hold no image
   button on that row). *ox, *oy = the title bar's local origin, to turn the close box's rect into page coordinates. */
static BYTE *rs_close_box(void *win, LONG *ox, LONG *oy) {
    BYTE *w = (BYTE *)win, *best = NULL;
    void *head = *(void **)(w + 0x34), *n;
    DWORD vt = (DWORD)GetModuleHandleA("GZWIND.DLL") + 0x2b190;
    int guard = 0;
    n = (head && !IsBadReadPtr(head, 4)) ? *(void **)head : NULL;
    while (n && n != head && guard++ < 80 && !IsBadReadPtr(n, 0x0c)) {
        BYTE *tb = *(BYTE **)((BYTE *)n + 8);
        if (tb && !IsBadReadPtr(tb, 0xa4) && ((LONG *)(tb + 0x80))[1] < 12 && ((LONG *)(tb + 0x80))[3] < 48) {
            void *h2 = *(void **)(tb + 0x34), *n2;
            int g2 = 0;
            n2 = (h2 && !IsBadReadPtr(h2, 4)) ? *(void **)h2 : NULL;
            while (n2 && n2 != h2 && g2++ < 40 && !IsBadReadPtr(n2, 0x0c)) {
                BYTE *ch = *(BYTE **)((BYTE *)n2 + 8);
                if (ch && !IsBadReadPtr(ch, 0x11c) && *(DWORD *)ch == vt &&
                    (!best || ((LONG *)(ch + 0x80))[0] > ((LONG *)(best + 0x80))[0])) {
                    best = ch; *ox = ((LONG *)(tb + 0x80))[0]; *oy = ((LONG *)(tb + 0x80))[1];
                }
                n2 = *(void **)n2;
            }
        }
        n = *(void **)n;
    }
    return best;
}
/* RSHG2 / RSARROWS (restorefix 2026-11-02b, owner: the hourglass "looks weird", shot 1793660447359: at 24x25 the 11-02c
   anti-aliased glass read as a dark bow tie with a bar under it). Pixel art instead, one ink pixel per '#', 's' = sand (ink
   at 55% over the face). */
/* The measured sheet (96x100, 24x25 frames; frame order disabled, normal, pressed, hover): each frame's glyph sits in an
   inner square with its outline at x 4..17, y 4..15, one row lower in the pressed frame (f 2), measured from the art
   (verify/restorefix/RESULTS.md). The 11-02c code found that square from dark pixels and took the button's own bevel rows
   (y 2..3, 16) as its edges, so the glass was drawn over the square's top and bottom lines (the bar the owner saw).
     glyph 0 (RSHG2): the minimise row (2) with the whole square painted in the face colour, row by row, and an 11x12
              hourglass drawn there in the square's outline colour (grey in the disabled frame)
     glyph 1 (RSARROWS "<"): the back row (1) as it is, the game's own arrow
     glyph 2 (RSARROWS ">"): the back row with the glyph's dark pixels mirrored inside the square */
static const char *const g_rs_glyph_hg12[12] = {
    "###########",
    " #       # ",
    " #sssssss# ",
    "  #sssss#  ",
    "   #sss#   ",
    "    #s#    ",
    "    #s#    ",
    "   # s #   ",
    "  #  s  #  ",
    " #  sss  # ",
    " #sssssss# ",
    "###########" };
/* the most common colour of row[x0..x1] among the pixels lighter than minlum (the glyph's own pixels left out: on the
   minimise row the bar's 6 dark pixels outnumber the face's 5 and won the vote, measured) */
static WORD rs_row_face(WORD *row, int x0, int x1, WORD dflt, DWORD code, int minlum) {
    int best = 0, i, j;
    WORD fc = dflt;
    for (i = x0; i <= x1; i++) {
        int c = 0;
        if (rs_lum(row[i], code) < minlum) continue;
        for (j = x0; j <= x1; j++) c += row[j] == row[i];
        if (c > best) { best = c; fc = row[i]; }
    }
    return fc;
}
static void rs_frames_v2(BYTE *db, LONG dp, const BYTE *sb, LONG sp, DWORD code, WORD keyc, int glyph) {
    int f, x, y, srow = glyph ? 1 : 2;
    for (f = 0; f < 4; f++) {
        LONG ox = f * 24, t = 4 + (f == 2), b = 15 + (f == 2), l = 4, r = 17;
        WORD ink = ((const WORD *)(sb + (srow * 25 + t) * sp))[f * 24 + 10];   /* the square's top line, mid-way */
        int il = rs_lum(ink, code), ir, ig, ib, pr, pg, pb;
        for (y = 0; y < 25; y++) memcpy(db + y * dp + ox * 2, sb + (srow * 25 + y) * sp + f * 24 * 2, 24 * 2);
        if (glyph == 0) {
            WORD fcs[25];
            for (y = t + 1; y < b; y++) fcs[y] = rs_row_face((WORD *)(db + y * dp) + ox, l + 1, r - 1, ink, code, il + 40);
            fcs[t] = fcs[t + 1]; fcs[b] = fcs[b - 1];
            for (y = t; y <= b; y++) { WORD *row = (WORD *)(db + y * dp) + ox; for (x = l; x <= r; x++) row[x] = fcs[y]; }
            rs_unpack(ink, code, &ir, &ig, &ib);
            for (y = 0; y < 12; y++) {
                WORD *row = (WORD *)(db + (t + y) * dp) + ox;
                for (x = 0; x < 11; x++) {
                    char c = g_rs_glyph_hg12[y][x];
                    int px = l + 1 + x;                      /* columns 5..15 of the 4..17 square */
                    if (c == ' ') continue;
                    if (c == '#') row[px] = ink;
                    else { rs_unpack(row[px], code, &pr, &pg, &pb);
                           row[px] = rs_pack(pr + (ir - pr) * 55 / 100, pg + (ig - pg) * 55 / 100, pb + (ib - pb) * 55 / 100, code); }
                    if (row[px] == keyc) row[px] ^= 1;
                }
            }
        } else if (glyph == 2) {
            for (y = t + 1; y < b; y++) {
                WORD *row = (WORD *)(db + y * dp) + ox, src[24], fc;
                memcpy(src, row, sizeof(src));
                fc = rs_row_face(src, l + 1, r - 1, src[l + 1], code, il + 40);
                for (x = l + 1; x < r; x++) if (rs_lum(src[x], code) < il + 40) row[x] = fc;             /* glyph out */
                for (x = l + 1; x < r; x++) if (rs_lum(src[x], code) < il + 40) row[(l + r) - x] = src[x]; /* mirrored in */
            }
        }
        logf("RSICON> frame %d: %s, square [%ld %ld %ld %ld], ink luminance %d", f,
             glyph == 0 ? "hourglass 11x12 on the bare face (RSHG2)" : glyph == 1 ? "the game's back arrow" : "the back arrow mirrored",
             l, t, r, b, il);
    }
}

/* a 4-frame strip of the close box's frame size with the hourglass; NULL = not made (the caller keeps the text button) */
static void *rs_icon_art_g(BYTE *xb, LONG *fw_out, LONG *fh_out, int glyph);
static void *rs_icon_art(BYTE *xb, LONG *fw_out, LONG *fh_out) { return rs_icon_art_g(xb, fw_out, fh_out, 0); }
static void *rs_icon_art_g(BYTE *xb, LONG *fw_out, LONG *fh_out, int glyph) {
    BYTE *sui = (BYTE *)GetModuleHandleA("SIMUI.DLL"), *sb = NULL, *db = NULL;
    void *src = *(void **)(xb + 0x118), *com, *dst = NULL;
    LONG *fr = (LONG *)(xb + 0xfc), fw = fr[2] - fr[0], fh = fr[3] - fr[1], sw = 0, sh = 0, sp = 0, dp = 0, nf = 0, f, x, y;
    DWORD fmt[2] = { 0, 0 }, a[8];
    WORD keyc = 0;
    int ok = 0, locked = 0;
    *fw_out = fw; *fh_out = fh;
    if (!src || IsBadReadPtr(src, 4) || fw < 8 || fh < 8 || fw > 64 || fh > 64) { logf("RSICON> close box art: none or odd (%ldx%ld)", fw, fh); return NULL; }
    __try {
        ho_v(src, 0x4c, 1, (DWORD)fmt, 0, 0, 0, 0);
        sw = (LONG)ho_v(src, 0x38, 0, 0, 0, 0, 0, 0); sh = (LONG)ho_v(src, 0x3c, 0, 0, 0, 0, 0, 0);
        nf = fw ? sw / fw : 0;
        logf("RSICON> close box art: format {%lu,%lu} %ldx%ld, frame [%ld %ld %ld %ld] (%ldx%ld, %ld frame(s)), mode %lu",
             fmt[0], fmt[1], sw, sh, fr[0], fr[1], fr[2], fr[3], fw, fh, nf, *(DWORD *)(xb + 0xf8));
        /* the close box's sheet is 4x4 frames (measured 96x100, 24x25 frames): rows close, back, minimise, maximise; the
           minimise frames are used, their bar sits in a plain inner face that the hourglass replaces */
        if (fmt[1] != 16 || (fmt[0] != 7 && fmt[0] != 5) || fr[0] != 0 || fr[1] != 0 || nf < 1 || sh < 3 * fh) __leave;
        keyc = fmt[0] == 7 ? 0xF81F : 0x7C1F;
        if (!(ho_v(src, 0x1c, 1, 0x40, 0, 0, 0, 0) & 0xff)) __leave;
        locked = 1;
        sb = (BYTE *)ho_v(src, 0x1a8, 0, 0, 0, 0, 0, 0); sp = (LONG)ho_v(src, 0x1ac, 0, 0, 0, 0, 0, 0);
        if (!sb || sp < sw * 2) __leave;
        rs_dump_strip("rsicon_close_src", sb, sp, sw, sh, fmt[0]);
        com = ((void *(__cdecl *)(void))(sui + 0x8489d))();
        if (!com || !(ho_v(com, 0x0c, 3, 0xc470d325, 0x20732180, (DWORD)&dst, 0, 0) & 0xff) || !dst) __leave;
        a[0] = 4 * fw; a[1] = fh; a[2] = fmt[0]; a[3] = fmt[1]; a[4] = a[5] = a[6] = a[7] = 0;
        if (!(rz_thiscall_ret(dst, (void *)(*(DWORD **)dst)[0x0c / 4], a, 8) & 0xff)) __leave;
        if (!(ho_v(dst, 0x1c, 1, 0x40, 0, 0, 0, 0) & 0xff)) __leave;
        db = (BYTE *)ho_v(dst, 0x1a8, 0, 0, 0, 0, 0, 0); dp = (LONG)ho_v(dst, 0x1ac, 0, 0, 0, 0, 0, 0);
        if (db && dp >= 4 * fw * 2 && (glyph || g_rs_hg2) && fw == 24 && fh == 25 && nf >= 4 && sh >= 3 * fh) {
            rs_frames_v2(db, dp, sb, sp, fmt[0], keyc, glyph);   /* RSHG2 / RSARROWS */
            rs_dump_strip(glyph == 1 ? "rsicon_left" : glyph == 2 ? "rsicon_right" : "rsicon_hourglass", db, dp, 4 * fw, fh, fmt[0]);
            ok = 1;
        } else if (db && dp >= 4 * fw * 2 && glyph) {
            logf("RSARROWS> the close box's art is not the measured 4x4 sheet of 24x25 frames: no arrow art");
        } else if (db && dp >= 4 * fw * 2) {
            for (f = 0; f < 4; f++) {                     /* frame f of the minimise row (row 2 of the sheet) */
                LONG sf = f < nf ? f : nf - 1, ox = f * fw, sy0 = 2 * fh, bx0 = fw, by0 = fh, bx1 = -1, by1 = -1;
                LONG ink_l = 999, sl;
                WORD ink = 0, seed;
                for (y = 0; y < fh; y++) memcpy(db + y * dp + ox * 2, sb + (sy0 + y) * sp + sf * fw * 2, fw * 2);
                /* the glyph's outline box: the dark pixels of the face, the drop shadow (right 6 columns, bottom 8 rows of
                   the 24x25 frame, measured) left out; the face colour is taken above the centre, inside that box */
                seed = *((WORD *)(db + (fh / 2 - 3) * dp) + ox + fw / 2);
                sl = rs_lum(seed, fmt[0]);
                for (y = 2; y < fh - 8; y++) {
                    WORD *row = (WORD *)(db + y * dp) + ox;
                    for (x = 2; x < fw - 6; x++) {
                        int l = rs_lum(row[x], fmt[0]);
                        if (row[x] == keyc || l > sl - 60) continue;
                        if (x < bx0) bx0 = x; if (x > bx1) bx1 = x; if (y < by0) by0 = y; if (y > by1) by1 = y;
                        if (l < ink_l) { ink_l = l; ink = row[x]; }
                    }
                }
                if (bx1 - bx0 < 7 || by1 - by0 < 6) {
                    logf("RSICON> frame %ld: glyph box [%ld %ld %ld %ld] not as expected: no icon", f, bx0, by0, bx1, by1);
                    ok = -1; break;
                }
                for (y = by0 + 1; y < by1; y++) {         /* inside the outline: the face back (each row its most common colour) */
                    WORD *row = (WORD *)(db + y * dp) + ox, fc = seed;
                    int best = 0, i, j;
                    for (i = bx0 + 1; i < bx1; i++) {
                        int c = 0;
                        for (j = bx0 + 1; j < bx1; j++) c += row[j] == row[i];
                        if (c > best) { best = c; fc = row[i]; }
                    }
                    for (x = bx0 + 1; x < bx1; x++) row[x] = fc;
                }
                for (y = by0 + 2; y <= by1 - 2; y++) {    /* the hourglass a pixel inside the outline, in the outline's ink */
                    WORD *row = (WORD *)(db + y * dp) + ox;
                    int ir, ig, ib, pr, pg, pb;
                    rs_unpack(ink, fmt[0], &ir, &ig, &ib);
                    for (x = bx0 + 2; x <= bx1 - 2; x++) {
                        int n = 0, sx, sy;
                        for (sy = 0; sy < 4; sy++) for (sx = 0; sx < 4; sx++)
                            n += rs_hourglass(x + (sx + 0.5) / 4, y + (sy + 0.5) / 4, bx0 + 2, by0 + 2, bx1 - bx0 - 3, by1 - by0 - 3);
                        if (!n) continue;
                        rs_unpack(row[x], fmt[0], &pr, &pg, &pb);
                        row[x] = rs_pack(pr + (ir - pr) * n / 16, pg + (ig - pg) * n / 16, pb + (ib - pb) * n / 16, fmt[0]);
                        if (row[x] == keyc) row[x] ^= 1;
                    }
                }
                logf("RSICON> frame %ld: glyph outline [%ld %ld %ld %ld], ink luminance %ld", f, bx0, by0, bx1, by1, ink_l);
            }
            if (ok < 0) { ok = 0; ho_v(dst, 0x20, 1, 0x40, 0, 0, 0, 0); __leave; }
            rs_dump_strip(glyph == 1 ? "rsicon_left" : glyph == 2 ? "rsicon_right" : "rsicon_hourglass", db, dp, 4 * fw, fh, fmt[0]);
            ok = 1;
        }
        ho_v(dst, 0x20, 1, 0x40, 0, 0, 0, 0);
        ho_v(dst, 0xc8, 1, ho_v(dst, 0x18c, 3, 0xff, 0, 0xff, 0, 0), 0, 0, 0, 0);   /* magenta = transparent */
    } __except (EXCEPTION_EXECUTE_HANDLER) { logf("RSICON> art fault 0x%08lX", GetExceptionCode()); ok = 0; }
    if (locked) ho_v(src, 0x20, 1, 0x40, 0, 0, 0, 0);
    if (!ok && dst) { ho_v(dst, 0x08, 0, 0, 0, 0, 0, 0); dst = NULL; }
    return dst;
}
/* the icon button left of the close box, its top on the close box's top; 1 = added */
static int rm_add_icon(void *fac, void *win) {
    LONG rect[4] = { 0, 0, 0, 0 }, *xr, fw = 0, fh = 0, x = 0, y = 0, ox = 0, oy = 0;
    BYTE *xb = rs_close_box(win, &ox, &oy);
    BYTE cap[0x20], tt[0x20];
    void *img, *btn, *bw;
    int ok = 0;
    if (!xb) { logf("RSICON> no close box found on the page: text button; children:"); qi_dump_children(win); return 0; }
    xr = (LONG *)(xb + 0x80);
    if (!(img = rs_icon_art(xb, &fw, &fh))) return 0;
    ho_v(img, 0x40, 1, (DWORD)rect, 0, 0, 0, 0);
    ho_str(cap, "");
    btn = (void *)ho_v(fac, 0x30, 5, RM_BTN, (DWORD)cap, (DWORD)img, (DWORD)rect, 0);
    if (btn) {
        ho_str(tt, SC3TR(ho_spanish(), "lifespan.lifespan", "Vida \xfatil", "Lifespan"));
        ho_v(btn, 0x8c, 1, (DWORD)tt, 0, 0, 0, 0);
        ho_str_free(tt);
        ho_v(btn, 0x24, 2, 4, 0, 0, 0, 0);
        ho_v(btn, 0x24, 2, 0x100, 1, 0, 0, 0);
        ho_v(btn, 0x98, 1, 0x1000000, 0, 0, 0, 0);
        bw = (void *)ho_v(btn, 0x1c, 0, 0, 0, 0, 0, 0);
        ok = bw && (ho_v(win, 0x34, 1, (DWORD)bw, 0, 0, 0, 0) & 0xff);
        x = ox + xr[0] - 6 - fw; y = oy + xr[1];
        if (ok) { ho_v(bw, 0xcc, 2, (DWORD)x, (DWORD)y, 0, 0, 0); ho_v(bw, 0xf4, 2, 2, 1, 0, 0, 0); }
        else if (bw) ho_v(bw, 0x28, 0, 0, 0, 0, 0, 0);
        ho_v(btn, 0x08, 0, 0, 0, 0, 0, 0);
    }
    logf("RSICON> close box [%ld %ld %ld %ld] in a title bar at (%ld, %ld); hourglass icon %ldx%ld at page (%ld, %ld): %s",
         xr[0], xr[1], xr[2], xr[3], ox, oy, fw, fh, x, y, ok ? "added" : "FAILED");
    ho_str_free(cap);
    ho_v(img, 0x08, 0, 0, 0, 0, 0, 0);
    return ok;
}


/* RSARROWS: an image button with a glyph cut from the close box's art (as rm_add_icon), page-local (x, y); 1 = added */
static int rs_img_btn(void *fac, void *win, DWORD id, int glyph, LONG x, LONG y, const char *tip, LONG *fw_out) {
    LONG rect[4] = { 0, 0, 0, 0 }, fw = 0, fh = 0, ox = 0, oy = 0;
    BYTE *xb = rs_close_box(win, &ox, &oy);
    BYTE cap[0x20], tt[0x20];
    void *img, *btn, *bw;
    int ok = 0;
    if (!xb || !(img = rs_icon_art_g(xb, &fw, &fh, glyph))) return 0;
    if (fw_out) *fw_out = fw;
    ho_v(img, 0x40, 1, (DWORD)rect, 0, 0, 0, 0);
    ho_str(cap, "");
    btn = (void *)ho_v(fac, 0x30, 5, id, (DWORD)cap, (DWORD)img, (DWORD)rect, 0);
    if (btn) {
        ho_str(tt, tip);
        ho_v(btn, 0x8c, 1, (DWORD)tt, 0, 0, 0, 0);
        ho_str_free(tt);
        ho_v(btn, 0x24, 2, 4, 0, 0, 0, 0);
        ho_v(btn, 0x24, 2, 0x100, 1, 0, 0, 0);
        ho_v(btn, 0x98, 1, 0x1000000, 0, 0, 0, 0);
        bw = (void *)ho_v(btn, 0x1c, 0, 0, 0, 0, 0, 0);
        ok = bw && (ho_v(win, 0x34, 1, (DWORD)bw, 0, 0, 0, 0) & 0xff);
        if (ok) { ho_v(bw, 0xcc, 2, (DWORD)x, (DWORD)y, 0, 0, 0); ho_v(bw, 0xf4, 2, 2, 1, 0, 0, 0); }
        else if (bw) ho_v(bw, 0x28, 0, 0, 0, 0, 0, 0);
        ho_v(btn, 0x08, 0, 0, 0, 0, 0, 0);
    }
    ho_str_free(cap);
    ho_v(img, 0x08, 0, 0, 0, 0, 0, 0);
    logf("RSARROWS> %s image button %ldx%ld at page (%ld, %ld): %s", glyph == 1 ? "\"<\"" : "\">\"", fw, fh, x, y, ok ? "added" : "FAILED");
    return ok;
}

/* ================= RSTITLE (restorefix 2026-11-02b, owner: the list must be titled "Vida Util" in the game's title font,
 * the Comic-Sans-like face of the "Reunirse" title). The page's title is the game's own text in its title bar (the child at
 * local top < 12, bottom < 48, as rs_close_box finds it). The window holding the text is found by its caption (window +0x44,
 * the SetCaption slot vt+0x10c stores it there, GZWIND 0x1001fa6c) and given "Vida Util" through vt+0x10c while the list is
 * up, so the game draws it with its own font; Volver and a page close put the old caption back. */
static struct { void *w; char old[64]; } g_rs_title_w;
static const char *rs_win_text(BYTE *w) {
    BYTE *s = w + 0x44;
    const char *t = NULL;
    __try {
        if (IsBadReadPtr(s, 8) || !*(DWORD *)s || IsBadReadPtr(*(void **)s, 0x18)) return NULL;
        t = (const char *)ho_v(s, 0x14, 0, 0, 0, 0, 0, 0);
        if (!t || IsBadStringPtrA(t, 64) || !t[0]) return NULL;
    } __except (EXCEPTION_EXECUTE_HANDLER) { return NULL; }
    return t;
}
static void *rs_title_find(void *win, char *out, int cap) {
    BYTE *w = (BYTE *)win;
    void *head = *(void **)(w + 0x34), *n, *found = NULL;
    int guard = 0;
    n = (head && !IsBadReadPtr(head, 4)) ? *(void **)head : NULL;
    while (n && n != head && guard++ < 80 && !IsBadReadPtr(n, 0x0c) && !found) {
        BYTE *tb = *(BYTE **)((BYTE *)n + 8);
        if (tb && !IsBadReadPtr(tb, 0xa4) && ((LONG *)(tb + 0x80))[1] < 12 && ((LONG *)(tb + 0x80))[3] < 48) {
            const char *t = rs_win_text(tb);
            void *h2 = *(void **)(tb + 0x34), *n2;
            int g2 = 0;
            DWORD rva = 0;
            if (t) { logf("RSTITLE> title bar %s+0x%lX holds \"%s\"", qi_mod_of(*(DWORD *)tb, &rva), rva, t); found = tb; lstrcpynA(out, t, cap); }
            n2 = (h2 && !IsBadReadPtr(h2, 4)) ? *(void **)h2 : NULL;
            while (!found && n2 && n2 != h2 && g2++ < 40 && !IsBadReadPtr(n2, 0x0c)) {
                BYTE *ch = *(BYTE **)((BYTE *)n2 + 8);
                LONG *cl;
                if (ch && !IsBadReadPtr(ch, 0xa4)) {
                    cl = (LONG *)(ch + 0x80);
                    t = rs_win_text(ch);
                    logf("RSTITLE>   title bar child %s+0x%lX local [%ld %ld %ld %ld] text %s%s%s", qi_mod_of(*(DWORD *)ch, &rva), rva,
                         cl[0], cl[1], cl[2], cl[3], t ? "\"" : "", t ? t : "(none)", t ? "\"" : "");
                    if (t) { found = ch; lstrcpynA(out, t, cap); }
                }
                n2 = *(void **)n2;
            }
        }
        n = *(void **)n;
    }
    return found;
}
static void rs_title(void *win, int on) {
    BYTE s[0x20];
    if (!g_rs_title) return;
    if (on) {
        char old[64];
        void *t = rs_title_find(win, old, sizeof(old));
        if (!t) { logf("RSTITLE> no title text found on the page: title unchanged"); return; }
        if (g_rs_title_w.w != t) { g_rs_title_w.w = t; lstrcpynA(g_rs_title_w.old, old, sizeof(g_rs_title_w.old)); }
        ho_str(s, SC3TR(ho_spanish(), "lifespan.lifespan_2", "Vida \xdatil", "Lifespan"));
        ho_v(t, 0x10c, 1, (DWORD)s, 0, 0, 0, 0);
        ho_str_free(s);
        ho_v(t, 0x154, 0, 0, 0, 0, 0, 0);
        logf("RSTITLE> title \"%s\" -> \"%s\"", g_rs_title_w.old, ho_spanish() ? "Vida \xdatil" : "Lifespan");
    } else if (g_rs_title_w.w) {
        if (rz_win_alive(g_rs_title_w.w)) {
            ho_str(s, g_rs_title_w.old);
            ho_v(g_rs_title_w.w, 0x10c, 1, (DWORD)s, 0, 0, 0, 0);
            ho_str_free(s);
            ho_v(g_rs_title_w.w, 0x154, 0, 0, 0, 0, 0, 0);
            logf("RSTITLE> title back to \"%s\"", g_rs_title_w.old);
        }
        g_rs_title_w.w = NULL;
    }
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
    ok = g_rs_icon && rm_add_icon(fac, win);            /* RSICON; SC3RESIZE_RSICON=0 or no art: the text button */
    if (!ok) ok = mp_button(fac, win, RM_BTN, SC3TR(ho_spanish(), "lifespan.lifespan", "Vida \xfatil", "Lifespan"), w - 34 - 84, 8, 84, 24);
    logf("RESTORE> Reunirse list page 0x%08lX %ldx%ld: \"Vida util\" button %s", (DWORD)win, w, l[3] - l[1], ok ? "added" : "FAILED");
}

/* the list page's message handler, SIMUI FUN_100042f7: __thiscall with FIVE stack args, `ret 0x14` at 0x10004402 (Ghidra
   shows four; a 4-arg detour unbalanced the stack and the game died on the next Reunirse open, measured 2026-11-02) */
static DWORD __fastcall rm_42f7(void *self, void *edx, DWORD win, DWORD msg, DWORD p3, DWORD p4, DWORD p5) {
    DWORD a[5], r;
    (void)edx;
    if (g_restore && msg == 3 && p3 == 1 && win && rm_click((void *)win, p4)) return 1;
    if (msg == 0xa2bf8acf && (void *)win == g_rm.win) { g_rm.win = NULL; g_rm.nhidden = 0; g_rs_title_w.w = NULL; }   /* page closing */
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
    rs_fix_init();
    if (ho_hook(sui, 0x42f7, e42f7, 6, (void *)rm_42f7, &g_orig_42f7, "Reunirse list page messages FUN_100042f7"))
        logf("RESTORE> on: \"Restaurar\" in the query dialog, \"Vida util\" on the Reunirse list page");
}
