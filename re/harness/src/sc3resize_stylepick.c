/* sc3resize_stylepick.c - SPMIX (task stylepick 2026-11-21): the "Mix all three styles" box in City Properties.
 * Included by sc3resize.c after the QUERYID block. The game logic is sc3netmod's STYLEPICK (sc3netmod_stylepick.c):
 * with it on, the building style picked in Options > City Properties (and in the New City dialog, the same window)
 * decides which style NEW buildings grow and standing buildings keep their look. This box adds the fourth choice,
 * all three styles at random (the style mix). The box shows sc3netmod's current state (sc3netmod_stylepick_state) and
 * on OK hands its value over (sc3netmod_stylepick_pending_mix) before the dialog's command calls SetCityScheme
 * (SIMUI 0x10011bc5 calls it after the modal loop returns, so the value is in place). Cancel / Escape send nothing.
 * Dialog messages: SIMUI FUN_1005bb2e (cIGZWinProc slot 0xc of vtable 0x100aa878): 0xa2bf8ace builds the controls
 * (FUN_1005e570), command 3 / 1 with id 0x2552483d is OK [CONFIRMED @ SIMUI 0x1005bb2e, 0x1005e3a1].
 * No box when sc3netmod is not loaded or STYLEPICK is off. SC3RESIZE_SPMIX=0: no detour, no box. */
static int   g_spmix = 1;
static void *g_orig_bb2e;
#define SPX_BOX 0x5C3D5350
#define SPX_OK  0x2552483d
typedef int  (*SPX_STATE)(DWORD *, int *);
typedef void (*SPX_PEND)(int);

static int spx_api(SPX_STATE *st, SPX_PEND *pd) {
    HMODULE m = GetModuleHandleA("sc3netmod.dll");
    *st = m ? (SPX_STATE)GetProcAddress(m, "sc3netmod_stylepick_state") : NULL;
    *pd = m ? (SPX_PEND)GetProcAddress(m, "sc3netmod_stylepick_pending_mix") : NULL;
    return *st && *pd;
}

/* lowest child bottom edge inside [x0, x1) -> where the box goes (layout read from the dialog itself) */
static void spx_add(void *win) {
    HMODULE sui = GetModuleHandleA("SIMUI.DLL");
    SPX_STATE st; SPX_PEND pd;
    DWORD set, col;
    int mix, ok, es = ho_spanish();
    void *fac;
    LONG *l;
    static int dumped;
    if (!win || IsBadReadPtr(win, 0xa4)) return;
    if (!spx_api(&st, &pd) || !st(&set, &mix)) {
        logf("SPMIX> no box: sc3netmod %s", GetModuleHandleA("sc3netmod.dll") ? "has STYLEPICK off" : "is not loaded");
        return;
    }
    if (ho_v(win, 0x78, 1, SPX_BOX, 0, 0, 0, 0)) return;
    fac = ((void *(__cdecl *)(void))((BYTE *)sui + 0x85065))();
    if (!fac || IsBadReadPtr(fac, 4)) { logf("SPMIX> no widget factory"); return; }
    if (!dumped++) qi_dump_children(win);
    col = ho_v(fac, 0x80, 1, 0x62e56a2e, 0, 0, 0, 0);
    l = (LONG *)((BYTE *)win + 0x80);
    ok = mp_checkbox(fac, win, SPX_BOX, SC3TR(es, "resize.sp_mix", "Mezclar los tres estilos", "Mix all three styles"),
                     mix, SPX_X, SPX_Y, 200, col);
    logf("SPMIX> City Properties %ldx%ld: box %s at (%d, %d), mix %d, style %08lX", l[2] - l[0], l[3] - l[1],
         ok ? "added" : "FAILED", SPX_X, SPX_Y, mix, set);
}

static DWORD __fastcall spx_msg(void *self, void *edx, DWORD win, DWORD msg, DWORD p3, DWORD p4, DWORD p5) {
    DWORD a[5], r;
    (void)edx;
    if (msg == 3 && p3 == 1 && p4 == SPX_OK && win) {
        SPX_STATE st; SPX_PEND pd;
        int v = pp_read_box((void *)win, SPX_BOX);
        if (v >= 0 && spx_api(&st, &pd)) { pd(v); logf("SPMIX> OK: mix %d", v); }
    }
    a[0] = win; a[1] = msg; a[2] = p3; a[3] = p4; a[4] = p5;
    r = rz_thiscall_ret(self, g_orig_bb2e, a, 5);
    if (msg == 0xa2bf8ace && (r & 0xff) && win) spx_add((void *)win);
    return r;
}

static void spx_install(HMODULE sui) {
    static const BYTE ebb2e[6] = { 0x55, 0x8b, 0xec, 0x8b, 0x45, 0x0c };   /* push ebp; mov ebp,esp; mov eax,[ebp+0xc] */
    if (!g_spmix) { logf("SPMIX> off (SC3RESIZE_SPMIX=0): no Mix box in City Properties"); return; }
    if (ho_hook(sui, 0x5bb2e, ebb2e, 6, (void *)spx_msg, &g_orig_bb2e, "City Properties messages FUN_1005bb2e"))
        logf("SPMIX> on: \"Mix all three styles\" box in City Properties (needs sc3netmod STYLEPICK)");
}
