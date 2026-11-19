/* ================= CIVVAR + NEWREWARD (child civmod, round 2026-11-19j; evidence re/analysis/CIVIC_REWARD.md,
 * verify/civmod/RESULTS.md). #included by sc3resize.c before PLACEHINTS (the cost label shows the civic look).
 * Owner 2026-11-19: civic buildings "cycle looks" on the existing button, new rewards "yes, build it".
 *
 * Data: written by re/tools/bldimport/bldimport.py into the game's own plugin folders under <PlugIn root>\PlugIn\
 * (the root is [Directories] PlugIn= of Apps\SC3U.ini, else Apps\, SC3U.exe cGZFileSystem::PlugInDirectory
 * 0x00482532). The game's plugin scan reads only *.pin and the sprite folder's *.DAT, so these files are inert for the
 * game itself:
 *   bldimport\bldimport_civic.ini  [Variants] <base instance>=<variant>,<variant>,...   base = the instance of the stock
 *                          exemplar the civic command builds ({0x207EDC0E, 0x57E, base}, CIVIC_REWARD.md 1); a variant
 *                          is an instance in group 0xB1D10002 (bldimport's plugin group) or "<group>:<instance>"
 *                          [Names] <variant instance>=<name shown in the cost label>
 *   bldimport_rewards\bldimport_rewards.ini  [REWARD_BUILDINGS] <type>=<name> ;<population>;<year>;0;0, the stock row
 *                          format (Advisor-CityPlanner.ini, parser SIMADV FUN_100089e7). bldimport gives each reward its
 *                          own type id = its id, block RW_TYPE_LO..RW_TYPE_HI (ids.json, 38000..38999). Rewards are a
 *                          plugin of their own so sc3mods_patch -Restore can take them out of PlugIn.
 *   bldimport_rewards\bldimport_types.ini  the reward types in CitySim.ini format: declared by the LOADER (sc3mods.c
 *                          "REWARD TYPES"), not here (owner call 2026-11-19 "Loader declares").
 *
 * CIVVAR [CONFIRMED @ SIMGEOM 0x1000a896, disassembly + game]: the 17 plain civic commands of SIMGEOM's command factory
 * meet at one tool constructor call, 0x1000b1a3 call 0x10009443 (thiscall, ecx = the new tool, args &key, 0, 0), the
 * exemplar key {type, group, instance} at [ebp-0x3c]. Each case pushes its own args (push edi; push edi; lea eax,
 * [ebp-0x3c]) and 16 of them jump to 0x1000b1a2 (push eax); only the last falls through 0x1000b19d, so the window
 * CIVIC_REWARD.md proposed (0x1000b19d) sees one case of 17 (measured: the Police hotkey built the stock tool without
 * passing it). The call's rel32 now points at cv_call, which calls cv_pick(&key) and jumps on to 0x10009443 with the
 * stack untouched. Every press of a civic button (menu or hotkey) is a new GetCommand call (SIMUI 0x10016329, SIMSPR
 * 0x10049a80), so it passes here once: for a base with variants, presses cycle stock, variant 1, ..., stock. Since
 * CIVDLG (round 2026-11-19k, below) a press opens the list window instead and cv_pick builds the look picked there;
 * the cycle is what SC3RESIZE_CIVDLG=0 gives back.
 * The variant exemplar is a copy of the base (same type id, coverage, price), so the stock tool, site check, price and
 * commit run unchanged. Installed only when the file lists at least one variant: no file = stock code.
 *
 * NEWREWARD [CONFIRMED @ SIMADV 0x10007989, 0x1000a324, disassembly]:
 *  - rows: the only call of the City Planner ini loader, SIMADV 0x10006f80 call 0x10007989 (ecx = the advisor), goes to
 *    rw_load_wrap, which runs the stock loader and then reads our file with the game's own classes: a
 *    cSC3CompressibleINIFile (ctor 0x10029434, dtor 0x100294a8) with only a path (cRZIniFile::SetPath 0x10025a3f), so
 *    InitFileType 0x10029ba7 picks the loose ini (type 1, cRZIniFile::EnumEntries 0x100269f1, which keeps the ';'
 *    columns in the value), and EnumEntries 0x10029828 of [REWARD_BUILDINGS] with the stock row callback 0x100089bf and
 *    the advisor as context, exactly as the stock loader does for its own section. Strings are SIMADV's own cRZString
 *    (char* ctor 0x10003b1d, dtor 0x10026740), so SIMADV's allocator owns them.
 *  - unlock: the "population and year met" exit of the City Planner tick, 0x1000a7fa mov eax, [ebp-0x10]; mov ecx,
 *    [eax+0x10] (6 bytes, node + type), then a sub chain over 7 fixed type ids into 0x1000a832 (unlocked = 1). The jmp
 *    reaches rw_stub: our types go to 0x1000a832, every other type continues at 0x1000a800 as stock. Installed only
 *    when the file has at least one row.
 *  - declare the types (measured 2026-11-19, the research's open point): a type that is not in CitySim.ini
 *    [AgentTypes] has no agent type object, and placing it faults the City Planner's occupant-inserted handler
 *    (SIMADV 0x1000b32a: QI 0xe0faadc7, vt+0x2c returns NULL, read of 0 at 0x1000b392), which aborts the commit after
 *    the insert (building on the map, "placed" never set, tool still armed). The agent type tree (SIMINIT
 *    sc3_agenttype_tree_init 0x10002eb1) is built from the GZ registry categories "sc3agenttype" / "sc3typehierarchy",
 *    which cSC3App::LoadRegistry (SC3U 0x0040b761) fills from CitySim.ini with EnumEntries at 0x0040bc80
 *    (RegisterAgentTypeCallback 0x0040cb70) and 0x0040bccb (RegisterAgentRelationCallback 0x0040cc08). Both calls' rel32
 *    are hooked by sc3mods.dll (the loader), which passes bldimport_types.ini's rows to the same stock callbacks, so the
 *    types are declared whenever the loader runs, mods on or off (a city holding a placed reward of an undeclared type
 *    faulted at 0x1000b392 and the game exited on load, measured). Here only the guard: rw_unlock_test unlocks a type
 *    only when sc3mods_reward_types() lists it as declared, so an undeclared reward can never be placed.
 * Switches: sc3resize.ini [buildings] civicvariants= / newrewards= / civiclist= (default 1), env SC3RESIZE_CIVVAR /
 * SC3RESIZE_NEWREWARD / SC3RESIZE_CIVDLG (the "Activar mods" page writes the first two env ones). Read once at start:
 * the hooks are code patches. */
#define CV_GROUP    0xB1D10002   /* bldimport's plugin exemplar group (bldimport.py LM_GROUP) */
#define CV_MAXB     17           /* the 17 plain civic commands */
#define CV_MAXV     12
#define RW_TYPE_LO  38000        /* bldimport reward type ids = their ids (bldimport.py ID_FIRST..ID_LAST) */
#define RW_TYPE_HI  38999
#define RW_MAX      64
static int g_civvar = 1, g_newreward = 1;
typedef struct { DWORD base; int n, look; DWORD grp[CV_MAXV], inst[CV_MAXV]; char name[CV_MAXV][64]; } CV_BASE;
static CV_BASE g_cv[CV_MAXB];
static int     g_cv_n;
static BYTE   *g_cv_geom;
static DWORD   g_cv_ctor;                     /* SIMGEOM+0x9443: the plain building tool constructor */
static BYTE   *g_rw_adv;                      /* SIMADV base */
static DWORD   g_rw_hit, g_rw_miss;           /* SIMADV+0xa832 (set unlocked), +0xa800 (the stock sub chain) */
static DWORD   g_rw_type[RW_MAX];
static int     g_rw_n, g_rw_logged[RW_MAX];
static DWORD   g_at_type[RW_MAX];             /* the types the loader declared (sc3mods_reward_types) */
static int     g_at_n = -1;                   /* -1 = not asked yet */

/* <PlugIn root>\PlugIn\<leaf>, leaf = "<plugin folder>\<file>" */
static void cv_path(char *out, int cap, const char *leaf) {
    char exe[MAX_PATH], ini[MAX_PATH], root[MAX_PATH], *s;
    GetModuleFileNameA(NULL, exe, sizeof(exe));
    if ((s = strrchr(exe, '\\'))) s[1] = 0;
    wsprintfA(ini, "%sSC3U.ini", exe);
    GetPrivateProfileStringA("Directories", "PlugIn", "", root, sizeof(root), ini);
    if (!root[0]) lstrcpynA(root, exe, sizeof(root));
    else if (root[lstrlenA(root) - 1] != '\\') lstrcatA(root, "\\");
    wsprintfA(out, "%.200sPlugIn\\%.60s", root, leaf);
    (void)cap;
}

static int cv_exists(const char *p) { DWORD a = GetFileAttributesA(p); return a != INVALID_FILE_ATTRIBUTES && !(a & FILE_ATTRIBUTE_DIRECTORY); }

/* -------------------------------------------------------------------------------------------- CIVVAR data */
static void cv_load(void) {
    char p[MAX_PATH], sec[8192], nm[8192], *e, *q;
    int i;
    cv_path(p, sizeof(p), "bldimport\\bldimport_civic.ini");
    g_cv_n = 0;
    if (!cv_exists(p)) return;
    if (!GetPrivateProfileSectionA("Variants", sec, sizeof(sec), p)) return;
    GetPrivateProfileSectionA("Names", nm, sizeof(nm), p);
    for (e = sec; *e && g_cv_n < CV_MAXB; e += lstrlenA(e) + 1) {
        CV_BASE *b = &g_cv[g_cv_n];
        char *eq = strchr(e, '=');
        if (*e == ';' || !eq) continue;
        memset(b, 0, sizeof(*b));
        b->base = strtoul(e, NULL, 0);
        b->look = -1;                                         /* the first press builds the stock look */
        for (q = eq + 1; *q && b->n < CV_MAXV; ) {
            DWORD a, g = CV_GROUP;
            char *z;
            while (*q == ' ' || *q == ',') q++;
            if (!*q) break;
            a = strtoul(q, &z, 0);
            if (z == q) break;
            if (*z == ':') { g = a; q = z + 1; a = strtoul(q, &z, 0); if (z == q) break; }
            q = z;
            b->grp[b->n] = g; b->inst[b->n] = a;
            {   char *n2;   /* its name from [Names] */
                for (n2 = nm; *n2; n2 += lstrlenA(n2) + 1) {
                    char *eq2 = strchr(n2, '=');
                    if (eq2 && strtoul(n2, NULL, 0) == a) { lstrcpynA(b->name[b->n], eq2 + 1, sizeof(b->name[0])); break; }
                }
                if (!b->name[b->n][0]) wsprintfA(b->name[b->n], "#%lu", a); }
            b->n++;
        }
        if (!b->base || !b->n) continue;
        for (i = 0; i < g_cv_n; i++) if (g_cv[i].base == b->base) break;   /* a repeated base: the first row counts */
        if (i < g_cv_n) continue;
        g_cv_n++;
    }
}

/* CIVDLG (child civdlg, round 2026-11-19k): the look chosen in the list window for the press in progress (cd_getcmd
   sets it around the stock factory call, cv_pick applies it). -1 = no pick: the press cycles (CIVDLG off). */
static int   g_civdlg = 1;
static int   g_cd_force = -1;
static DWORD g_cd_forcebase;

/* the press: the key the factory is about to build. stdcall from cv_stub, game thread. */
static void __stdcall cv_pick(DWORD *key) {
    int i;
    __try {
        if (key[0] != 0x207EDC0E || key[1] != 0x57E) return;
        for (i = 0; i < g_cv_n; i++) {
            CV_BASE *b = &g_cv[i];
            if (b->base != key[2]) continue;
            if (g_cd_force >= 0 && g_cd_forcebase == b->base) b->look = g_cd_force;   /* CIVDLG: the list's pick */
            else if (g_civdlg) b->look = 0;    /* CIVDLG on but no pick (a press inside the open window): stock */
            else b->look = (b->look + 1) % (b->n + 1);
            if (b->look > 0) { key[1] = b->grp[b->look - 1]; key[2] = b->inst[b->look - 1]; }
            logf("CIVVAR> button of base 0x%lX: look %d of %d, %s, key 0x%08lX 0x%08lX 0x%08lX", b->base, b->look + 1,
                 b->n + 1, b->look ? b->name[b->look - 1] : "stock", key[0], key[1], key[2]);
            return;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) { }
}

/* the target of SIMGEOM 0x1000b1a3 call: [esp] = return 0x1000b1a8, [esp+4] = &key, ecx = the tool */
static __declspec(naked) void cv_call(void) {
    __asm {
        pushad
        push dword ptr [esp + 36]
        call cv_pick
        popad
        jmp  dword ptr [g_cv_ctor]
    }
}

/* the cost label's prefix (sc3resize_placehints.c ph_label): the city view's current tool (view +0x228) is a building
   tool (SIMGEOM vtables 0x29504 / 0x295e4 / 0x2968c / 0x29734) whose key (tool +0x108) is a base with variants or one of
   its variants -> "Aspecto 2 de 3: <name>". 0 = no prefix. Game thread. */
static int cv_label(BYTE *view, char *out, int cap) {
    static const DWORD bvt[4] = { 0x29504, 0x295e4, 0x2968c, 0x29734 };
    BYTE *t;
    DWORD *k;
    int i, j, ok = 0, es = ho_spanish();
    out[0] = 0;
    if (!g_cv_geom || !g_cv_n || !view) return 0;
    __try {
        if (IsBadReadPtr(view, 0x22c)) return 0;
        t = *(BYTE **)(view + 0x228);
        if (!t || IsBadReadPtr(t, 0x120)) return 0;
        for (i = 0; i < 4; i++) if (*(DWORD *)t == (DWORD)g_cv_geom + bvt[i]) ok = 1;
        if (!ok) return 0;
        k = (DWORD *)(t + 0x108);
        if (k[0] != 0x207EDC0E) return 0;
        for (i = 0; i < g_cv_n; i++) {
            CV_BASE *b = &g_cv[i];
            if (k[1] == 0x57E && k[2] == b->base) {
                wsprintfA(out, SC3TR(es, "resize.cv_look_stock", "Aspecto %d de %d: original", "Look %d of %d: original"), 1, b->n + 1);
                return 1;
            }
            for (j = 0; j < b->n; j++) if (k[1] == b->grp[j] && k[2] == b->inst[j]) {
                char nm[64];
                lstrcpynA(nm, b->name[j], sizeof(nm));
                wsprintfA(out, SC3TR(es, "resize.cv_look", "Aspecto %d de %d: %s", "Look %d of %d: %s"), j + 2, b->n + 1, nm);
                return 1;
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) { out[0] = 0; }
    (void)cap;
    return 0;
}

/* ================= CIVDLG (child civdlg, round 2026-11-19k; evidence re/analysis/CIVIC_REWARD.md section 6).
 * Owner 2026-11-19: pressing a civic button that has imported looks opens a small list window in the game's own look:
 * the original first, then the looks, each with name, price and picture. Picking one arms the stock tool with that
 * key and closes the window. Esc or close = no tool. A button with no looks stays stock.
 *
 * The window IS the stock catalog dialog (landmarks / rewards / power plants), driven exactly as its own command does
 * [CONFIRMED @ SIMUI 0x10011919, disassembly]: GZCOM create class 0xe3091435 iid 0xa308d9ad (iface = object+0x18),
 * SetMode (iface vt+0xc, object+0x24), Init (vt+0x10: creates the window, whose create message builds the controls,
 * sc3_ui_build_catalog_picker_window 0x10067620, then the list from the object's items, 0x10068603), the window
 * (vt+0x14), cIGZWinMgr::DoModalWin(GetMainWindow(), win) (wm vt+0xc, vt+0x9c), WasOK (vt+0x18), GetSelected(&attrib)
 * (vt+0x1c), DestroyWindow (wm vt+0x28), around a cISC3City::SimHiddenPause / Unpause (vt+0x21c / 0x220).
 * Its items are the object's own list (object vtable 0x100ab514: +0x1c NewItem, +0x18 AddItem in insertion order
 * while the sort property +0x14 is 0), each a property holder (vtable 0x100a27c8: +0x24 SetUint, +0x1c SetString)
 * with the key in 0xba64f91e / 0xfa64f93a / 0xfa64f957, which is how mode 0xa2f7d03a fills it (0x10068603:95-131).
 * The stock modes are filled by the advisors from a city message {0x2dc6d7f, mode} (0x1006950a); an unknown mode gets
 * no advisor items, so ours are added between SetMode and Init and the list shows exactly them. On a selection the
 * dialog (0x10069029) draws the attrib's picture (+0x38), its name (+0x4c) and the item strings 0x2ebe7cb (+0x44),
 * 0x22f291ae (+0x48), 0x2ebe76b (+0x54) the way the advisors' items use them (SIMADV 0x1001c69c). OK, double click,
 * Esc (key 0x1b) and the close box are the dialog's own (winproc 0x1006751b).
 * The dialog is a stock SIMUI dialog window (class 0xa2a79fd0, FUN_1002c647), so DLGSCALE scales it like the rewards
 * list. No SIMUI patch at all.
 *
 * Where: SIMGEOM's command factory, vtable 0x100291f4, slot +0x18 = sc3_geom_dispatch_command_handler 0x1000a896 (the
 * factory's own handler, asked by its GetCommand 0x10015560 after its sub-factories; the only reference to
 * 0x1000a896 in the DLL). The slot now points at cd_getcmd: for one of the 17 plain civic class ids whose base has
 * looks it runs the window first; cancel -> *out = 0, false (both callers test it: SIMUI 0x10016329, SIMSPR
 * 0x10049a80), a pick -> the stock handler runs with g_cd_force set and cv_pick builds that key. The stock catalog
 * also runs modally inside a game command (its Execute, SIMUI vtable 0x100a2b48 +0x2c -> +0x38 = 0x10011919) called
 * from the same two places one call later, so the modal loop runs in the same context as the stock lists.
 * Switch: SC3RESIZE_CIVDLG=0 / sc3resize.ini [buildings] civiclist=0 -> the shipped press-to-cycle. Not a mods page
 * row: the "Activar mods" page's two columns are full (see MODTOGGLE). */
#define CD_MODE 0x3C1D1A10   /* our catalog mode id: not one of the stock six (0x22e92581 0x62e92553 0x62e925a2
                                0xc2f291a9 0xe2e92527 0xa2f7d03a), so no advisor answers it */
static const DWORD k_cd_cls[17][2] = {   /* plain civic command class id -> base instance (CIVIC_REWARD.md section 1) */
    { 0x42ff052f, 0xd2 },   { 0x22ff053f, 0x1f41 }, { 0x22ff054c, 0xd3 },   { 0xe2ff0555, 0xd1 },   { 0xc2ff0563, 0x1f94 },
    { 0xc2ff0571, 0xd6 },   { 0xc2ff057a, 0xf5 },   { 0x62ff0585, 0xd4 },   { 0x02ff05aa, 0xd },    { 0x82ff05b7, 0xd5 },
    { 0x22ff05ca, 0xda },   { 0x62ff05d1, 0xd7 },   { 0xc2ff05e0, 0x234b }, { 0x22ff05ea, 0x234c }, { 0x22ff05f3, 0x234e },
    { 0x02ff04fe, 0x1f96 }, { 0x22ff058f, 0xed } };
static DWORD g_cd_handler;      /* SIMGEOM+0xa896 */
static int   g_cd_busy;

typedef DWORD (__cdecl *CD_F0)(void);

/* "1,234" */
static void cd_money(char *out, LONG v) {
    char t[16];
    int n, i, j = 0;
    if (v < 0) { out[j++] = '-'; v = -v; }
    n = wsprintfA(t, "%ld", v);
    for (i = 0; i < n; i++) { out[j++] = t[i]; if ((n - i - 1) % 3 == 0 && i < n - 1) out[j++] = ','; }
    out[j] = 0;
}

static void cd_setstr(void *item, DWORD prop, const char *text) {
    BYTE s[0x20];
    ho_str(s, text);
    ho_v(item, 0x1c, 2, prop, (DWORD)s, 0, 0, 0);
    ho_str_free(s);
}

/* The entry to select once the dialog has built its controls. They are built by the window's create message
   (sc3_ui_build_catalog_picker_window, list +0x3c, picture +0x38), which arrives inside DoModalWin, not in Init:
   measured, a selection call before DoModalWin read a NULL +0x38 (SIMUI+0x690EF). The builder selects an entry itself
   only from the saved catalog preferences, which our mode has none of. Game thread (the frame heartbeat, which keeps
   running in the modal loop). */
static BYTE *g_cd_sel_obj;
static void *g_cd_sel_win;
static int   g_cd_sel_idx;
static void cd_tick(void) {
    BYTE *obj = g_cd_sel_obj, *S;
    void *lb;
    DWORD a[1];
    if (!obj) return;
    __try {
        lb = *(void **)(obj + 0x3c);
        if (!lb || !*(void **)(obj + 0x38) || !*(void **)(obj + 0x44) || !*(void **)(obj + 0x54) || !*(void **)(obj + 0x64)) return;
        g_cd_sel_obj = NULL;
        if (g_cd_sel_win) {   /* the title: the builder's create message set it to "" for a mode it does not know */
            BYTE s[0x20];
            ho_str(s, SC3TR(ho_spanish(), "resize.cd_title", "Elegir aspecto", "Choose a look"));
            ho_v(g_cd_sel_win, 0x10c, 1, (DWORD)s, 0, 0, 0, 0);                  /* SetCaption */
            ho_str_free(s);
            ho_v(g_cd_sel_win, 0x154, 0, 0, 0, 0, 0, 0);                          /* invalidate */
        }
        ho_v(lb, 0x28, 2, (DWORD)g_cd_sel_idx, 1, 0, 0, 0);                     /* select, as the builder does */
        if (!obj[0x29] || *(int *)(obj + 0x2c) != g_cd_sel_idx) {               /* no notification: fill it directly */
            S = (BYTE *)GetModuleHandleA("SIMUI.DLL");
            a[0] = (DWORD)g_cd_sel_idx; rz_thiscall_ret(obj, S + 0x69029, a, 1);
        }
        logf("CIVDLG> entry %d selected (list %s)", g_cd_sel_idx, obj[0x29] ? "ok" : "NOT selected");
    } __except (EXCEPTION_EXECUTE_HANDLER) { g_cd_sel_obj = NULL; logf("CIVDLG> fault 0x%08lX selecting the entry", GetExceptionCode()); }
}

/* the list window for one base: 0 = original, k = look k, -1 = closed / Esc / failed. Game thread, inside GetCommand. */
static int cd_dialog(CV_BASE *b) {
    BYTE *S = (BYTE *)GetModuleHandleA("SIMUI.DLL"), *obj;
    void *city = NULL, *gz, *cat = NULL, *win = NULL, *wm, *cache, *layer, *bud = NULL, *mw;
    DWORD key[3], *k;
    int i, n = b->n + 1, res = -1, pre, paused = 0, ok = 0, es = ho_spanish();
    char t[200], m[24];
    if (!S) return -1;
    __try {
        city = (void *)((CD_F0)(S + 0x8e7da))();
        if (!city) { logf("CIVDLG> no city: window not opened"); return -1; }
        ho_v(city, 0x21c, 0, 0, 0, 0, 0, 0); paused = 1;                       /* SimHiddenPause, as 0x10011919 */
        gz = (void *)((CD_F0)(S + 0x8489d))();
        if (!gz || !(ho_v(gz, 0xc, 3, 0xe3091435, 0xa308d9ad, (DWORD)&cat, 0, 0) & 0xff) || !cat) {
            logf("CIVDLG> catalog class 0xe3091435 not created"); goto out; }
        obj = (BYTE *)cat - 0x18;
        if (*(DWORD *)obj != (DWORD)S + 0xab514 || *(DWORD *)cat != (DWORD)S + 0xab4f4) {
            logf("CIVDLG> catalog object vtables differ from shipped: window not opened"); goto rel; }
        ho_v(cat, 0xc, 1, CD_MODE, 0, 0, 0, 0);                                 /* SetMode */
        cache = (void *)((CD_F0)(S + 0x8e985))();                              /* occupant attrib cache */
        layer = (void *)ho_v(city, 0x138, 0, 0, 0, 0, 0, 0);                    /* BuildingLayer */
        if (layer && !IsBadReadPtr(layer, 0x34)) bud = *(void **)((BYTE *)layer + 0x30);
        for (i = 0; i < n; i++) {
            void *item, *att = NULL, *ag;
            DWORD type = 0;
            LONG price = -1;
            key[0] = 0x207EDC0E; key[1] = i ? b->grp[i - 1] : 0x57E; key[2] = i ? b->inst[i - 1] : b->base;
            if (cache && (ho_v(cache, 0x18, 2, (DWORD)key, (DWORD)&att, 0, 0, 0) & 0xff) && att) {
                ag = (void *)ho_v(att, 0x4c, 0, 0, 0, 0, 0, 0);                  /* CityAgentType */
                if (ag) type = ho_v(ag, 0x10, 0, 0, 0, 0, 0, 0);
                ho_v(att, 8, 0, 0, 0, 0, 0, 0);
            } else logf("CIVDLG> entry %d key 0x%08lX 0x%08lX: not in the attrib cache (the list shows no name)", i, key[1], key[2]);
            if (bud && type) price = (LONG)ho_v(bud, 0x54, 1, type, 0, 0, 0, 0);   /* the build price by type (site check) */
            item = (void *)ho_v(obj, 0x1c, 0, 0, 0, 0, 0, 0);                    /* NewItem */
            if (!item) continue;
            ho_v(item, 0x24, 2, 0xba64f91e, key[0], 0, 0, 0);
            ho_v(item, 0x24, 2, 0xfa64f93a, key[1], 0, 0, 0);
            ho_v(item, 0x24, 2, 0xfa64f957, key[2], 0, 0, 0);
            if (price >= 0) {
                cd_money(m, price);
                wsprintfA(t, SC3TR(es, "resize.cd_price", "Precio: $%s", "Price: $%s"), m);
                cd_setstr(item, 0x2ebe7cb, t);
            }
            wsprintfA(t, SC3TR(es, "resize.cd_lookn", "Aspecto %d de %d", "Look %d of %d"), i + 1, n);
            cd_setstr(item, 0x22f291ae, t);
            cd_setstr(item, 0x2ebe76b, i ? SC3TR(es, "resize.cd_desc_look", "Aspecto importado. Da el mismo servicio y cuesta lo mismo que el original.",
                                                 "Imported look. Same service and same price as the original.")
                                         : SC3TR(es, "resize.cd_desc_stock", "El edificio original del juego.", "The game's own building."));
            ho_v(obj, 0x18, 1, (DWORD)item, 0, 0, 0, 0);                        /* AddItem */
            logf("CIVDLG> entry %d: key 0x%08lX 0x%08lX type %lu price %ld", i, key[1], key[2], type, price);
        }
        if (!(ho_v(cat, 0x10, 0, 0, 0, 0, 0, 0) & 0xff)) { logf("CIVDLG> catalog Init failed: window not opened"); goto rel; }
        win = (void *)ho_v(cat, 0x14, 0, 0, 0, 0, 0, 0);
        if (!win) { logf("CIVDLG> catalog has no window"); goto rel; }
        ho_v(win, 4, 0, 0, 0, 0, 0, 0);                                          /* AddRef, as 0x10011919 */
        pre = b->look > 0 && b->look < n ? b->look : 0;                          /* the last pick is selected */
        g_cd_sel_win = win; g_cd_sel_idx = pre; g_cd_sel_obj = obj;   /* by cd_tick: the controls exist only once the window is shown */
        wm = (void *)((CD_F0)(S + 0x85091))();
        mw = (void *)ho_v(wm, 0xc, 0, 0, 0, 0, 0, 0);                            /* GetMainWindow */
        logf("CIVDLG> base 0x%lX: list window open, %d entries, entry %d selected", b->base, n, pre);
        ho_v(wm, 0x9c, 2, (DWORD)mw, (DWORD)win, 0, 0, 0);                       /* DoModalWin(main, win) */
        g_cd_sel_obj = NULL;
        ok = ho_v(cat, 0x18, 0, 0, 0, 0, 0, 0) & 0xff;                           /* OK pressed with a selection */
        if (ok) {
            void *att = NULL;
            ho_v(cat, 0x1c, 1, (DWORD)&att, 0, 0, 0, 0);
            if (att) {
                k = (DWORD *)ho_v(att, 0x14, 0, 0, 0, 0, 0, 0);                  /* Key */
                for (i = 0; k && i < n; i++)
                    if (k[1] == (i ? b->grp[i - 1] : 0x57E) && k[2] == (i ? b->inst[i - 1] : b->base)) { res = i; break; }
                ho_v(att, 8, 0, 0, 0, 0, 0, 0);
            }
        }
        if (res >= 0) logf("CIVDLG> base 0x%lX: picked entry %d of %d (%s)", b->base, res + 1, n, res ? b->name[res - 1] : "original");
        else logf("CIVDLG> base 0x%lX: window closed without a pick (%s): no tool", b->base, ok ? "OK with no entry" : "Esc / close");
        ho_v(wm, 0x28, 1, (DWORD)win, 0, 0, 0, 0);                               /* DestroyWindow */
        ho_v(win, 8, 0, 0, 0, 0, 0, 0);
    rel:
        ho_v(cat, 8, 0, 0, 0, 0, 0, 0);
    out:
        ho_v(city, 0x220, 0, 0, 0, 0, 0, 0);                                     /* SimHiddenUnpause */
        paused = 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        g_cd_sel_obj = NULL;
        logf("CIVDLG> fault 0x%08lX in the list window: no tool", GetExceptionCode());
        if (paused && city) __try { ho_v(city, 0x220, 0, 0, 0, 0, 0, 0); } __except (EXCEPTION_EXECUTE_HANDLER) { }
        res = -1;
    }
    return res;
}

/* SIMGEOM factory vtable 0x100291f4 slot +0x18 (thiscall: class id, riid, void **out) */
static BYTE __fastcall cd_getcmd(void *self, void *edx, DWORD cls, DWORD riid, void **out) {
    DWORD a[3], r;
    int i, j, pick;
    (void)edx;
    if (g_civdlg && !g_cd_busy && (!g_hwnd || GetWindowThreadProcessId(g_hwnd, NULL) == GetCurrentThreadId()))
        for (i = 0; i < 17; i++) if (k_cd_cls[i][0] == cls) {
            for (j = 0; j < g_cv_n; j++) if (g_cv[j].base == k_cd_cls[i][1]) break;
            if (j == g_cv_n) break;                       /* no looks: stock */
            g_cd_busy = 1;
            pick = cd_dialog(&g_cv[j]);
            g_cd_busy = 0;
            if (pick < 0) { if (out) *out = NULL; return 0; }
            g_cd_force = pick; g_cd_forcebase = g_cv[j].base;
            break;
        }
    a[0] = cls; a[1] = riid; a[2] = (DWORD)out;
    r = rz_thiscall_ret(self, (void *)g_cd_handler, a, 3);
    g_cd_force = -1;
    return (BYTE)r;
}

static void cd_install(BYTE *geom) {
    DWORD *slot = (DWORD *)(geom + 0x2920c), old;
    if (!g_civdlg) { logf("CIVDLG> off (SC3RESIZE_CIVDLG=0 or sc3resize.ini [buildings] civiclist=0): presses cycle the looks"); return; }
    if (*slot != (DWORD)geom + 0xa896 || *(DWORD *)(geom + 0x29200) != (DWORD)geom + 0x15560) {
        logf("CIVDLG> SIMGEOM factory vtable differs from shipped: off, presses cycle the looks"); g_civdlg = 0; return; }
    g_cd_handler = (DWORD)geom + 0xa896;
    if (!VirtualProtect(slot, 4, PAGE_READWRITE, &old)) { logf("CIVDLG> SIMGEOM+0x2920c not writable: off"); g_civdlg = 0; return; }
    InterlockedExchange((LONG volatile *)slot, (LONG)(DWORD)cd_getcmd);   /* no restore (task onramp) */
    logf("CIVDLG> on: a civic button with looks opens the list window (stock catalog dialog, SIMGEOM+0x2920c)");
}

static void cv_install(void) {
    static const BYTE want[6] = { 0x57, 0x57, 0x8d, 0x45, 0xc4, 0x50 };   /* 0x1000b19d, then the call at +6 */
    HMODULE g = NULL;
    BYTE *s;
    DWORD old;
    int st = 0, i, nv = 0;
    if (!g_civvar) { logf("CIVVAR> off (sc3resize.ini [buildings] civicvariants=0 or SC3RESIZE_CIVVAR=0)"); return; }
    cv_load();
    for (i = 0; i < g_cv_n; i++) nv += g_cv[i].n;
    if (!g_cv_n) {
        char p[MAX_PATH];
        cv_path(p, sizeof(p), "bldimport\\bldimport_civic.ini");
        logf("CIVVAR> no civic variants (%s %s): not installed, the civic buttons are stock", p, cv_exists(p) ? "lists none" : "not found");
        return;
    }
    while (st++ < 300 && !(g = GetModuleHandleA("SIMGEOM.DLL"))) Sleep(100);
    if (!g) { logf("CIVVAR> SIMGEOM.DLL not loaded: off"); g_cv_n = 0; return; }
    s = (BYTE *)g + 0xb1a3;
    if (memcmp(s - 6, want, sizeof(want)) || s[0] != 0xe8 || (DWORD)(s + 5 + *(LONG *)(s + 1)) != (DWORD)g + 0x9443) {
        logf("CIVVAR> SIMGEOM+0xb1a3 differs from shipped: not installed"); g_cv_n = 0; return; }
    g_cv_geom = (BYTE *)g;
    g_cv_ctor = (DWORD)g + 0x9443;
    if (!VirtualProtect(s, 5, PAGE_EXECUTE_READWRITE, &old)) { logf("CIVVAR> SIMGEOM+0xb1a3 not writable: off"); g_cv_n = 0; return; }
    InterlockedExchange((LONG volatile *)(s + 1), (LONG)((DWORD)cv_call - (DWORD)(s + 5)));   /* no restore (task onramp) */
    FlushInstructionCache(GetCurrentProcess(), s, 5);
    for (i = 0; i < g_cv_n; i++) {
        char t[400];
        int j, n = 0;
        n += wsprintfA(t + n, "base 0x%lX:", g_cv[i].base);
        for (j = 0; j < g_cv[i].n && n < 330; j++) n += wsprintfA(t + n, " 0x%lX:0x%lX \"%.24s\"", g_cv[i].grp[j], g_cv[i].inst[j], g_cv[i].name[j]);
        logf("CIVVAR> %s", t);
    }
    logf("CIVVAR> on: %d civic button(s) with %d variant look(s) (SIMGEOM+0xb1a3)", g_cv_n, nv);
    cd_install((BYTE *)g);   /* CIVDLG: the list window instead of the cycle */
}

/* ------------------------------------------------------------------------------------------- NEWREWARD */
/* the reward types sc3mods.dll declared (sc3mods.c "REWARD TYPES"); asked once, at the first city load (after app init,
   so after LoadRegistry). An older loader without the export declares none: then no reward is ever unlocked. */
static void rw_declared(void) {
    HMODULE m = GetModuleHandleA("sc3mods.dll");
    int (__stdcall *f)(DWORD *, int) = m ? (int (__stdcall *)(DWORD *, int))GetProcAddress(m, "sc3mods_reward_types") : NULL;
    int i;
    char t[300];
    if (g_at_n >= 0) return;
    g_at_n = f ? f(g_at_type, RW_MAX) : 0;
    if (g_at_n > RW_MAX) g_at_n = RW_MAX;
    t[0] = 0;
    for (i = 0; i < g_at_n && lstrlenA(t) < 280; i++) wsprintfA(t + lstrlenA(t), " %lu", g_at_type[i]);
    logf("NEWREWARD> %d reward type(s) declared by the loader%s%s", g_at_n, t, f ? "" : " (sc3mods.dll has no sc3mods_reward_types)");
}

static int rw_is_ours(DWORD t) {
    int i;
    for (i = 0; i < g_rw_n; i++) if (g_rw_type[i] == t) return i + 1;
    return 0;
}

/* the reward item of a type, from the advisor's map<type, item*> at +0xb0 (SGI tree: header +4 root, node +8 left,
   +0xc right, +0x10 key, +0x14 value; SIMADV 0x1000a324 walks it from header +8). NULL when not there. */
static BYTE *rw_item(BYTE *adv, DWORD type) {
    BYTE *h, *n;
    int guard = 0;
    __try {
        h = *(BYTE **)(adv + 0xb0);
        if (!h || IsBadReadPtr(h, 0x18)) return NULL;
        n = *(BYTE **)(h + 4);
        while (n && n != h && guard++ < 64 && !IsBadReadPtr(n, 0x18)) {
            DWORD k = *(DWORD *)(n + 0x10);
            if (k == type) return *(BYTE **)(n + 0x14);
            n = *(BYTE **)(n + (type < k ? 8 : 0xc));
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) { }
    return NULL;
}

/* our rows, read with the game's own ini class and row callback; ecx of the stock loader = the advisor */
static void rw_rows(BYTE *adv) {
    BYTE *A = g_rw_adv, ini[0x200], ps[0x20], sec[0x20];
    char p[MAX_PATH];
    DWORD a[3], ok = 0;
    int i, got = 0;
    cv_path(p, sizeof(p), "bldimport_rewards\\bldimport_rewards.ini");
    rw_declared();
    if (!cv_exists(p)) { logf("NEWREWARD> %s not found: no rows added", p); return; }
    memset(ini, 0, sizeof(ini)); memset(ps, 0, sizeof(ps)); memset(sec, 0, sizeof(sec));
    __try {
        rz_thiscall_ret(ini, A + 0x29434, NULL, 0);                 /* cSC3CompressibleINIFile() */
        a[0] = (DWORD)p;                rz_thiscall_ret(ps, A + 0x3b1d, a, 1);    /* cRZString(char const *) */
        a[0] = (DWORD)"REWARD_BUILDINGS"; rz_thiscall_ret(sec, A + 0x3b1d, a, 1);
        a[0] = (DWORD)ps;               rz_thiscall_ret(ini, A + 0x25a3f, a, 1);  /* cRZIniFile::SetPath, no compressed path */
        a[0] = (DWORD)sec; a[1] = (DWORD)(A + 0x89bf); a[2] = (DWORD)adv;
        ok = rz_thiscall_ret(ini, A + 0x29828, a, 3) & 0xff;      /* EnumEntries([REWARD_BUILDINGS], stock row callback) */
        rz_thiscall_ret(sec, A + 0x26740, NULL, 0);                 /* ~cRZString */
        rz_thiscall_ret(ps, A + 0x26740, NULL, 0);
        rz_thiscall_ret(ini, A + 0x294a8, NULL, 0);                 /* ~cSC3CompressibleINIFile */
    } __except (EXCEPTION_EXECUTE_HANDLER) { logf("NEWREWARD> fault 0x%08lX reading %s with the game's ini class", GetExceptionCode(), p); return; }
    for (i = 0; i < g_rw_n; i++) {
        BYTE *it = rw_item(adv, g_rw_type[i]);
        if (it && !IsBadReadPtr(it, 0x60)) {
            got++;
            logf("NEWREWARD> row type %lu: item 0x%08lX population %lu year %lu petition %lu own-rule %u deal %u unlocked %u placed %u",
                 g_rw_type[i], (DWORD)it, *(DWORD *)(it + 0x40), *(DWORD *)(it + 0x44), *(DWORD *)(it + 0x48), it[0x4e], it[0x4f],
                 it[0x4c], it[0x4d]);
        } else logf("NEWREWARD> row type %lu: NO item (the parser dropped it: no exemplar of that type loaded?)", g_rw_type[i]);
        g_rw_logged[i] = 0;
    }
    logf("NEWREWARD> %s read by the game's ini class (EnumEntries %s): %d of %d row(s) are reward items", p,
         ok ? "true" : "FALSE (the class refused the file)", got, g_rw_n);
}

static BYTE __fastcall rw_load_wrap(void *adv, void *edx) {
    DWORD r;
    (void)edx;
    r = rz_thiscall_ret(adv, g_rw_adv + 0x7989, NULL, 0);          /* the stock loader: SYS.PAK Advisor-CityPlanner.ini */
    rw_rows((BYTE *)adv);
    return (BYTE)r;
}

/* the unlock exit: the type passed the population and year test (node in eax) */
static int __stdcall rw_unlock_test(DWORD type, BYTE *node) {
    int i = rw_is_ours(type), j;
    if (!i) return 0;
    rw_declared();
    for (j = 0; j < g_at_n; j++) if (g_at_type[j] == type) break;
    if (j == g_at_n) {   /* not declared: placing it would fault SIMADV 0x1000b392 (see the header), so never unlock it */
        if (g_rw_logged[i - 1] != 2) {
            g_rw_logged[i - 1] = 2;
            logf("NEWREWARD> type %lu passed population and year but is not declared in [AgentTypes]: NOT unlocked", type);
        }
        return 0;
    }
    if (!g_rw_logged[i - 1]) {
        g_rw_logged[i - 1] = 1;
        logf("NEWREWARD> type %lu passed population and year: unlocked (SIMADV+0xa832)", type);
    }
    (void)node;
    return i;
}

/* replaces SIMADV 0x1000a7fa..0x1000a7ff (mov eax, [ebp-0x10]; mov ecx, [eax+0x10]) */
static __declspec(naked) void rw_stub(void) {
    __asm {
        mov  eax, [ebp - 0x10]
        mov  ecx, [eax + 0x10]
        push eax
        push ecx
        push edx
        push eax
        push ecx
        call rw_unlock_test
        test eax, eax
        pop  edx
        pop  ecx
        pop  eax
        jnz  rw_hit
        jmp  dword ptr [g_rw_miss]
    rw_hit:
        jmp  dword ptr [g_rw_hit]
    }
}

static void rw_install(void) {
    static const BYTE unl[12] = { 0x8b, 0x45, 0xf0, 0x8b, 0x48, 0x10, 0x81, 0xe9, 0xea, 0x03, 0x00, 0x00 };
    HMODULE m = NULL;
    BYTE *c, *u, *A;
    char p[MAX_PATH], sec[8192], *e;
    DWORD old;
    int st = 0;
    if (!g_newreward) { logf("NEWREWARD> off (sc3resize.ini [buildings] newrewards=0 or SC3RESIZE_NEWREWARD=0)"); return; }
    cv_path(p, sizeof(p), "bldimport_rewards\\bldimport_rewards.ini");
    g_rw_n = 0;
    if (cv_exists(p) && GetPrivateProfileSectionA("REWARD_BUILDINGS", sec, sizeof(sec), p))
        for (e = sec; *e && g_rw_n < RW_MAX; e += lstrlenA(e) + 1) {
            DWORD t = strtoul(e, NULL, 0);
            if (*e == ';' || !strchr(e, '=')) continue;
            if (t < RW_TYPE_LO || t > RW_TYPE_HI) { logf("NEWREWARD> row \"%.60s\": type outside %d..%d, skipped", e, RW_TYPE_LO, RW_TYPE_HI); continue; }
            if (!rw_is_ours(t)) g_rw_type[g_rw_n++] = t;
        }
    if (!g_rw_n) { logf("NEWREWARD> no reward rows (%s %s): not installed, rewards are stock", p, cv_exists(p) ? "lists none" : "not found"); return; }
    while (st++ < 300 && !(m = GetModuleHandleA("SIMADV.DLL"))) Sleep(100);
    if (!m) { logf("NEWREWARD> SIMADV.DLL not loaded: off"); g_rw_n = 0; return; }
    A = (BYTE *)m; c = A + 0x6f80; u = A + 0xa7fa;
    if (c[0] != 0xe8 || (DWORD)(c + 5 + *(LONG *)(c + 1)) != (DWORD)A + 0x7989 || memcmp(u, unl, sizeof(unl)) ||
        A[0x7989] != 0xb8 || A[0x29434] != 0xb8 || A[0x29828] != 0xb8 || A[0x294a8] != 0xb8 || A[0x3b1d] != 0xb8 ||
        A[0x25a3f] != 0x56 || A[0x26740] != 0xc7 || A[0x89bf] != 0xff) {
        logf("NEWREWARD> SIMADV differs from shipped: not installed"); g_rw_n = 0; return; }
    g_rw_adv = A;
    g_rw_hit = (DWORD)A + 0xa832; g_rw_miss = (DWORD)A + 0xa800;
    if (!VirtualProtect(c, 5, PAGE_EXECUTE_READWRITE, &old) || !VirtualProtect(u, 6, PAGE_EXECUTE_READWRITE, &old)) {
        logf("NEWREWARD> SIMADV not writable: off"); g_rw_n = 0; return; }
    u[0] = 0xE9; *(DWORD *)(u + 1) = (DWORD)rw_stub - (DWORD)(u + 5); u[5] = 0x90;   /* no restore (task onramp) */
    FlushInstructionCache(GetCurrentProcess(), u, 6);
    InterlockedExchange((LONG volatile *)(c + 1), (LONG)((DWORD)rw_load_wrap - (DWORD)(c + 5)));
    FlushInstructionCache(GetCurrentProcess(), c, 5);
    {   char t[400]; int i, n = 0;
        for (i = 0; i < g_rw_n && n < 360; i++) n += wsprintfA(t + n, " %lu", g_rw_type[i]);
        logf("NEWREWARD> on: %d reward row(s) from %s, types%s (rows after SIMADV+0x7989 via +0x6f80, unlock at +0xa7fa)", g_rw_n, p, t); }
}

static DWORD WINAPI cvrw_thread(LPVOID x) { (void)x; cv_install(); rw_install(); return 0; }
