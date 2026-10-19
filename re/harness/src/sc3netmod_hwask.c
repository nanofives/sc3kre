/* sc3netmod_hwask.c - the HWASK helper of sc3netmod.dll (task hwask, owner decision 2026-10-19: "Dialog: default
 * bridge, the game asks whether to build the interchange"). #included by sc3netmod.c after sc3netmod_hwcap.c, before
 * the four highway shape blocks, which call hwask_ok() right before they would build a FULL interchange.
 *
 * The question is the game's own confirm dialog, the one the stock tunnel builders open: manager vt+0x140 =
 * FUN_10006018(msg, cost) (manager vtable 0x1002c7bc, read from the PE; ret 8 @ 0x1000631e) `[CONFIRMED @ 0x10006018]`:
 * pause message 0x4372cf29, the cost formatted as money (FUN_1001f015 vt+0x94 -> vt+0x3c), the body = string
 * {0x2026960B, 0x029541F4, msg} used as a printf format with that money string (FUN_1001ef1c -> _vsnprintf), the title
 * = string 0x252 of the same group ("Engineer's Report"), dialog type 1 when cost >= 1 (2 when cost < 1), run modally
 * by FUN_10006321 (returns 0x12340001 for the accept button), resume message 0xa372cf2d; returns 1 = accept. The
 * tunnel builders call it as `this vt+0x140(0x253, cost)` (0x253 = "Do you want to construct a tunnel for %s?")
 * `[CONFIRMED @ 0x1001c102, 0x1001ca1a]`. Our texts are two new instances of group 0x029541F4 in a netpack text
 * container (package highway_ask, manifest key "texts"), listed in SYS.PAK Default.ini [DBSegments] under key
 * 0x029541f4 the way the shipped list repeats a key for its Holidays containers. re/analysis/HWY_ASK.md.
 *
 *   hwask_ok(hp, kind, x, z, r, trig, ncells) -> 1 build the full interchange, 0 build the default (the bridge; a T
 *                         stays stock). Asks only on an edit pass, on the game window's thread. On accept it charges
 *                         ncells x price(0x4332 = 17202 OffRamp, what the stock On-ramp tool charges per ramp cell,
 *                         `[CONFIRMED @ 0x10014678]`) through budget (manager +0x38) vt+0x14, as the tunnel builders
 *                         charge; with less money than that it does not ask (the default is built). A load pass never
 *                         asks: it gets the default. Off (SC3NETMOD_HWASK=0, or no `hwask` table line) -> always 1,
 *                         the automatic behaviour from before this task.
 *   A declined T stays stock, so the same T would be found again by every later retile: its decline is remembered
 *   (trigger cell, turn, trigger id) and saved in sc3netmod's variant section 0x4E56 as entries an older DLL skips
 *   (id word 0; sc3netmod.c load_begin), so a reload does not ask again. hwask_prune drops a decline once its trigger
 *   cell holds something else. X and diagonal crossings need no record: the bridge pieces written on "no" are not the
 *   stock aftermath the blocks start a new interchange from.
 *
 * Table line (netpack manifest "highway_lines", package highway_ask): hwask <crossing text id> <T text id>
 * Off: SC3NETMOD_HWASK=0.
 */

#define HWASK_MAXD 256
#define HWASK_W1TAG 0x4B53UL                /* saved decline: id word 0, w1 = tag << 16 | trigger id */
#define HWASK_PRICE 0x4332UL                /* 17202 OffRamp: the On-ramp tool's price per ramp cell */
enum { HWASK_X = 1, HWASK_T, HWASK_DX, HWASK_DD };

typedef char (__fastcall *PFN_HwaskDlg)(void *mgr, void *edx, DWORD msg, int cost);    /* vt+0x140 FUN_10006018 ret 8 */
typedef int (__fastcall *PFN_HwaskPrice)(void *bud, void *edx, DWORD type);            /* budget vt+0x54 */

static DWORD g_hwask_txt[2];                /* text instances: [0] crossing, [1] T */
static int g_hwask_on = -1;
static struct { short x, z; BYTE r, kind; WORD trig; } g_hwask_d[HWASK_MAXD];
static int g_hwask_nd;
static volatile LONG g_hwask_n_ask, g_hwask_n_yes, g_hwask_n_no, g_hwask_n_def;

static void hwask_line(const char *path, const char *line) {
    unsigned long a, b;
    if (sscanf(line + 6, "%lu %lu", &a, &b) != 2 || !a || !b) { logf("### hwask: %s: bad line '%s'", path, line); return; }
    g_hwask_txt[0] = a; g_hwask_txt[1] = b;
}

static int hwask_active(void) {
    if (g_hwask_on < 0) {
        g_hwask_on = g_hwask_txt[0] && !env_off("SC3NETMOD_HWASK");
        logf("hwask: %s", g_hwask_on ? "on: a new interchange is built only when the player accepts the question" :
             g_hwask_txt[0] ? "off (SC3NETMOD_HWASK=0): interchanges are built automatically" :
                              "off (no hwask table line, package highway_ask not installed): interchanges are built automatically");
        if (g_hwask_on) logf("hwask: texts %lu (crossing) %lu (T) of group 0x029541F4", g_hwask_txt[0], g_hwask_txt[1]);
    }
    return g_hwask_on;
}

static int hwask_find(int x, int z, int r, WORD trig) {
    int k;
    for (k = 0; k < g_hwask_nd; k++)
        if (g_hwask_d[k].x == x && g_hwask_d[k].z == z && g_hwask_d[k].r == r && g_hwask_d[k].trig == trig) return k;
    return -1;
}

static void hwask_decline(int kind, int x, int z, int r, WORD trig) {
    if (hwask_find(x, z, r, trig) >= 0) return;
    if (g_hwask_nd >= HWASK_MAXD) { logf("### hwask: %d declines remembered, (%d,%d) not kept", HWASK_MAXD, x, z); return; }
    g_hwask_d[g_hwask_nd].x = (short)x; g_hwask_d[g_hwask_nd].z = (short)z;
    g_hwask_d[g_hwask_nd].r = (BYTE)r; g_hwask_d[g_hwask_nd].kind = (BYTE)kind; g_hwask_d[g_hwask_nd].trig = trig;
    g_hwask_nd++;
}

/* drop the declines whose trigger cell (inside this pass's read box) no longer holds the trigger piece */
static void hwask_prune(HwyPass *hp) {
    int k;
    for (k = g_hwask_nd - 1; k >= 0; k--) {
        int x = g_hwask_d[k].x, z = g_hwask_d[k].z;
        DWORD v;
        if (x < hp->b.x0 || z < hp->b.z0 || x >= hp->b.x0 + hp->b.w || z >= hp->b.z0 + hp->b.h) continue;
        v = hwy_at(hp, x, z);
        if (v && hwy_id(v) == g_hwask_d[k].trig) continue;
        logf("hwask: %s: decline at (%d,%d) turn %d forgotten (the trigger cell changed)", hp->who, x, z, g_hwask_d[k].r);
        g_hwask_d[k] = g_hwask_d[--g_hwask_nd];
    }
}

static int hwask_ok(HwyPass *hp, int kind, int x, int z, int r, WORD trig, int ncells) {
    static const char *nm[5] = {"", "X cloverleaf", "T", "diagonal x straight interchange", "diagonal x diagonal cloverleaf"};
    void *bud;
    unsigned __int64 funds;
    int price, cost;
    char yes;
    if (!hwask_active()) return 1;
    if (hp->who && !strcmp(hp->who, "load")) {
        InterlockedIncrement(&g_hwask_n_def);
        logf("hwask: load: %s at (%d,%d) not asked on a load pass: the default (%s)", nm[kind], x, z,
             kind == HWASK_T ? "stays stock" : "bridge");
        return 0;
    }
    if (kind == HWASK_T && hwask_find(x, z, r, trig) >= 0) {             /* declined before: stays stock */
        logf("hwask: %s: T at (%d,%d) turn %d declined before: stays stock, not asked", hp->who, x, z, r);
        return 0;
    }
    if (!g_rb_hwnd || GetWindowThreadProcessId(g_rb_hwnd, NULL) != GetCurrentThreadId()) {
        InterlockedIncrement(&g_hwask_n_def);
        logf("hwask: %s: %s at (%d,%d) not asked: not on the game window's thread [tid %04lx]: the default", hp->who,
             nm[kind], x, z, GetCurrentThreadId());
        return 0;
    }
    bud = *(void **)(hp->mgr + 0x38);
    price = ((PFN_HwaskPrice)VT(bud, 0x54))(bud, 0, HWASK_PRICE);
    cost = ncells * price;
    if (cost < 1) cost = 1;                                               /* cost < 1 opens the OK-only dialog */
    funds = ((PFN_Funds)VT(bud, 0x10))(bud);
    if ((__int64)funds < 0 || ((__int64)funds < 0x100000000LL && (DWORD)funds < (DWORD)cost)) {   /* the tunnel test */
        InterlockedIncrement(&g_hwask_n_def);
        logf("hwask: %s: %s at (%d,%d) not asked: funds %lu < cost %d (%d ramp cells x %d): the default", hp->who,
             nm[kind], x, z, (DWORD)funds, cost, ncells, price);
        return 0;
    }
    InterlockedIncrement(&g_hwask_n_ask);
    logf("hwask: %s: asking for the %s at (%d,%d) turn %d: %d ramp cells x %d = %d", hp->who, nm[kind], x, z, r,
         ncells, price, cost);
    yes = ((PFN_HwaskDlg)VT(hp->mgr, 0x140))(hp->mgr, 0, g_hwask_txt[kind == HWASK_T], cost);
    if (yes) {
        ((PFN_V1)VT(bud, 0x14))(bud, 0, (DWORD)cost);
        InterlockedIncrement(&g_hwask_n_yes);
        logf("hwask: %s: yes: %s at (%d,%d) built, %d charged, funds %lu -> %lu", hp->who, nm[kind], x, z, cost,
             (DWORD)funds, (DWORD)((PFN_Funds)VT(bud, 0x10))(bud));
        return 1;
    }
    InterlockedIncrement(&g_hwask_n_no);
    if (kind == HWASK_T) hwask_decline(kind, x, z, r, trig);
    logf("hwask: %s: no: %s at (%d,%d) %s", hp->who, nm[kind], x, z,
         kind == HWASK_T ? "stays stock (decline remembered, saved with the city)" : "gets the bridge");
    return 0;
}

/* save / load (sc3netmod.c save_end / load_begin): one variant-section entry per remembered decline */
static int hwask_nsave(void) { return g_hwask_nd; }

static void hwask_save_rec(int k, DWORD *w0, DWORD *w1, DWORD *id) {
    *w0 = ((DWORD)g_hwask_d[k].x & 0xfff) | (((DWORD)g_hwask_d[k].z & 0xfff) << 12) | ((DWORD)(g_hwask_d[k].r & 3) << 24) |
          ((DWORD)(g_hwask_d[k].kind & 15) << 28);
    *w1 = (HWASK_W1TAG << 16) | g_hwask_d[k].trig;
    *id = 0;                                                              /* an older DLL skips id word 0 */
}

static int hwask_load_rec(DWORD w0, DWORD w1, DWORD id) {               /* -> 1 it was ours */
    if (id != 0 || (w1 >> 16) != HWASK_W1TAG) return 0;
    hwask_decline((int)(w0 >> 28), (int)(w0 & 0xfff), (int)((w0 >> 12) & 0xfff), (int)((w0 >> 24) & 3), (WORD)w1);
    logf("hwask: load: T decline at (%d,%d) turn %d (trigger %u) restored", (int)(w0 & 0xfff), (int)((w0 >> 12) & 0xfff),
         (int)((w0 >> 24) & 3), (WORD)w1);
    return 1;
}

static void hwask_reset(void) { g_hwask_nd = 0; }

static void hwask_stats(void) {
    static LONG last;
    LONG n = g_hwask_n_ask + g_hwask_n_def;
    if (n == last) return;
    last = n;
    logf("stats: hwask asked=%ld (yes %ld, no %ld), default without asking=%ld, T declines remembered=%d", g_hwask_n_ask,
         g_hwask_n_yes, g_hwask_n_no, g_hwask_n_def, g_hwask_nd);
}
