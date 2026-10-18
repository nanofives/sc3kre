/* sc3netmod_bridge.c - the netbridge block of sc3netmod.dll (task netbridge, 2026-10-13). #included by sc3netmod.c
 * just above its "arming" section, so it shares the variant table (g_base, read only here) and the patch helpers
 * (write_code, retarget_call, bytes_are). Nothing outside this file changes except the include and one call in
 * watcher(). Evidence: re/analysis/NETBRIDGE.md, verify/netbridge/.
 *
 * 1. INHERIT (SC3NETMOD_INHERIT=0 turns it off). SIMNTWRK code that decides by piece id, beyond the crossing switch
 *    and the 15 predicates of the CROSS block, sees the BASE id of a variant:
 *    a. highway diagonals and onramps: FUN_10009bc7 (cell -> piece id) is called only from FUN_10009d20 (19 sites)
 *       and FUN_1000aaba only from FUN_1000abde (10 sites); both compare the result with 0x49 / 0x2bfa / 0x3acb /
 *       0x3afa / 0x3b07..0x3b0a. Every call site goes through a thunk that maps the result.
 *    b. removal of multi-tile pieces (bridges, highway diagonals): manager vt+0x104 = FUN_1001da5f looks the removed
 *       id up in the Collapse.txt groups and walks the neighbours whose id (FUN_1001a93d, 5 sites) is in the group.
 *       The vtable slot gets a wrapper that maps the id argument, and the 5 sites map the neighbour ids. The two
 *       cell removers it calls also compare ids: vt+0xfc FUN_1001e2ea (site 0x1001e377, exact id + state, for
 *       0x3acc / 0x2bd7) and vt+0xf4 FUN_1001e3cc (site 0x1001e454, the 16-id list at 0x10031f94).
 *    So a variant of a bridge or highway piece collapses, joins diagonals and is removed exactly as its base. Not
 *    mapped on purpose: FUN_1000de17 (road wear decorations, see the CROSS block) and FUN_1001d761's ramp partner
 *    site 0x1001d96d (ramps belong to the sibling block netramp).
 *
 * 2. XCROSS (SC3NETMOD_XCROSS=0 turns it off). Crossing art for variants. FUN_100167d4 turns the existing piece and
 *    the new network into a crossing tile through the 6x6 matrix at 0x100318ac and decodes the value with
 *    FUN_1002207c(value, &id, &state) at 0x10016953; the existing occupant is [ebp-8] of that frame. The call goes
 *    through a thunk: when the existing piece's RAW id is a variant that a table names for this crossing piece, the
 *    value becomes (replacement << 8) | state. Tables: every <root>\mods\netmod\cross\*.txt (netpack writes one per
 *    package), lines "<variant> <crossing piece> <replacement piece>". The replacement is itself a variant of the
 *    crossing piece (base = crossing piece), so saves store the stock crossing (SAVEBASE) and the id lists see it
 *    as the stock crossing. Only the EXISTING piece can select the art: the new network enters the matrix as its
 *    netType, not as a piece id.
 */

/* ---------------------------------------------------------------- 1. INHERIT */

static DWORD g_nb_a93d, g_nb_bc7, g_nb_aaba, g_nb_orig104;
static volatile LONG g_nb_n_hway, g_nb_n_remove, g_nb_n_collapse_arg;

static DWORD __stdcall nb_map(DWORD id) {
    if (id < 65536 && g_base[id]) return g_base[id];
    return id;
}

static DWORD __stdcall nb_map_count(DWORD id, volatile LONG *n) {
    if (id < 65536 && n == &g_nb_n_remove && g_tmpl_keep[id]) return id;   /* task multitile: own Collapse group */
    if (id < 65536 && g_base[id]) { InterlockedIncrement(n); return g_base[id]; }
    return id;
}

/* call FUN_1001a93d(occ) (one stack arg, ret 4, ecx unused) at a removal site: same contract, base id out */
static __declspec(naked) void nb_a93d_thunk(void) {
    __asm {
        push dword ptr [esp + 4]
        call dword ptr [g_nb_a93d]
        push offset g_nb_n_remove
        push eax
        call nb_map_count
        ret 4
    }
}

/* FUN_10009bc7 / FUN_1000aaba: __thiscall (x, z), ret 8 -> piece id at the cell (0 if none) */
static __declspec(naked) void nb_bc7_thunk(void) {
    __asm {
        push dword ptr [esp + 8]
        push dword ptr [esp + 8]
        call dword ptr [g_nb_bc7]
        push offset g_nb_n_hway
        push eax
        call nb_map_count
        ret 8
    }
}

static __declspec(naked) void nb_aaba_thunk(void) {
    __asm {
        push dword ptr [esp + 8]
        push dword ptr [esp + 8]
        call dword ptr [g_nb_aaba]
        push offset g_nb_n_hway
        push eax
        call nb_map_count
        ret 8
    }
}

/* manager vt+0x104 = FUN_1001da5f(layer, x, z, y, WORD id, ...) __thiscall: the id is the 5th stack argument
   ([esp+0x14] at entry, read as a ushort by the function). Map it, then run the original with every register and
   argument as they were. */
static __declspec(naked) void nb_collapse_wrap(void) {
    __asm {
        push eax
        movzx eax, word ptr [esp + 0x18]
        cmp byte ptr [g_tmpl_keep + eax], 0      ; task multitile: a template piece keeps its own Collapse group
        jnz keep
        movzx eax, word ptr [g_base + eax * 2]
        test eax, eax
        jz keep
        mov word ptr [esp + 0x18], ax
        lock inc dword ptr [g_nb_n_collapse_arg]
    keep:
        pop eax
        jmp dword ptr [g_nb_orig104]
    }
}

static const DWORD g_nb_hway_bc7[] = {      /* calls of FUN_10009bc7, all inside FUN_10009d20 (PE call scan) */
    0x0a098, 0x0a0a8, 0x0a0b7, 0x0a1af, 0x0a1bf, 0x0a1ce, 0x0a229, 0x0a24b, 0x0a281, 0x0a2a3,
    0x0a52b, 0x0a546, 0x0a60b, 0x0a626, 0x0a6c1, 0x0a6dc, 0x0a772, 0x0a78d, 0x0a7a8,
};
static const DWORD g_nb_hway_aaba[] = {     /* calls of FUN_1000aaba, all inside FUN_1000abde */
    0x0b080, 0x0b0a7, 0x0b0c5, 0x0b382, 0x0b3a0, 0x0b3ca, 0x0b4b8, 0x0b4db, 0x0b547, 0x0b56a,
};
static const DWORD g_nb_remove_sites[] = {  /* calls of FUN_1001a93d in the removal code */
    0x1dcf4, 0x1debf, 0x1dffb, 0x1e0c4, 0x1e1e5,     /* FUN_1001da5f, Collapse group walk */
    0x1e377,                                         /* FUN_1001e2ea, exact id + state */
    0x1e454,                                         /* FUN_1001e3cc, list 0x10031f94 */
};
#define NB_N(a) ((int)(sizeof(a) / sizeof((a)[0])))

static int nb_retarget_all(BYTE *m, const DWORD *sites, int n, DWORD want, void *to, DWORD *orig, const char *what) {
    int i, ok = 0;
    for (i = 0; i < n; i++) {
        DWORD old = retarget_call(m, sites[i], want, to);
        if (old) { *orig = old; ok++; }
        else logf("### INHERIT: %s site +0x%05lX is not `call +0x%05lX` - skipped", what, sites[i], want);
    }
    return ok;
}

static int nb_patch_inherit(BYTE *m) {
    DWORD *slot = (DWORD *)(m + 0x2c7bc + 0x104), nv = (DWORD)nb_collapse_wrap;
    int nh, nr, nw = 0;
    g_nb_a93d = (DWORD)m + 0x1a93d;
    g_nb_bc7 = (DWORD)m + 0x9bc7;
    g_nb_aaba = (DWORD)m + 0xaaba;
    nh = nb_retarget_all(m, g_nb_hway_bc7, NB_N(g_nb_hway_bc7), 0x9bc7, (void *)nb_bc7_thunk, &g_nb_bc7, "FUN_10009bc7")
       + nb_retarget_all(m, g_nb_hway_aaba, NB_N(g_nb_hway_aaba), 0xaaba, (void *)nb_aaba_thunk, &g_nb_aaba, "FUN_1000aaba");
    nr = nb_retarget_all(m, g_nb_remove_sites, NB_N(g_nb_remove_sites), 0x1a93d, (void *)nb_a93d_thunk, &g_nb_a93d,
                         "FUN_1001a93d");
    if (!IsBadReadPtr(slot, 4) && *slot == (DWORD)m + 0x1da5f) {
        g_nb_orig104 = *slot;
        nw = write_code((BYTE *)slot, &nv, 4);
    } else logf("### INHERIT: manager vtable +0x104 != FUN_1001da5f - collapse id not mapped");
    logf("INHERIT: highway id sites %d/%d, removal id sites %d/%d, collapse arg %s", nh,
         NB_N(g_nb_hway_bc7) + NB_N(g_nb_hway_aaba), nr, NB_N(g_nb_remove_sites), nw ? "wrapped" : "NOT wrapped");
    return nh + nr + nw;
}

/* ---------------------------------------------------------------- 2. XCROSS */

typedef struct { WORD over, cross, piece; } NbCross;
static NbCross g_nb_cross[256];
static int g_nb_ncross;
static DWORD g_nb_207c;
static volatile LONG g_nb_n_xcross;

static void nb_cross_read(const char *path) {
    char line[256];
    FILE *f = fopen(path, "r");
    if (!f) return;
    while (fgets(line, sizeof(line), f)) {
        unsigned long o, c, p;
        char *s = line;
        while (*s == ' ' || *s == '\t') s++;
        if (*s == '#' || *s == ';' || *s == '\r' || *s == '\n' || !*s) continue;
        if (sscanf(s, "%lu %lu %lu", &o, &c, &p) != 3 || !o || o > 0xffff || !c || c > 0xffff || !p || p > 0xffff) {
            logf("xcross: %s: bad line '%s'", path, s);
            continue;
        }
        if (!g_base[o] || g_base[p] != (WORD)c) {
            logf("### xcross: %s: %lu is not a variant, or %lu is not a variant of %lu - line skipped", path, o, p, c);
            continue;
        }
        if (g_nb_ncross < (int)(sizeof(g_nb_cross) / sizeof(g_nb_cross[0]))) {
            g_nb_cross[g_nb_ncross].over = (WORD)o; g_nb_cross[g_nb_ncross].cross = (WORD)c;
            g_nb_cross[g_nb_ncross].piece = (WORD)p; g_nb_ncross++;
            logf("xcross: %s: over %lu, crossing %lu -> %lu", path, o, c, p);
        }
    }
    fclose(f);
}

static void nb_cross_load(void) {
    char pat[MAX_PATH], path[MAX_PATH];
    WIN32_FIND_DATAA fd;
    HANDLE h;
    if (!g_rootlen) return;
    _snprintf(pat, sizeof(pat), "%smods\\netmod\\cross\\*.txt", g_root);
    pat[sizeof(pat) - 1] = 0;
    h = FindFirstFileA(pat, &fd);
    if (h == INVALID_HANDLE_VALUE) return;
    do {
        if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) continue;
        _snprintf(path, sizeof(path), "%smods\\netmod\\cross\\%s", g_root, fd.cFileName);
        path[sizeof(path) - 1] = 0;
        nb_cross_read(path);
    } while (FindNextFileA(h, &fd));
    FindClose(h);
}

/* value = matrix cell (id << 8 | state); occ = the existing occupant at the crossing cell */
static DWORD __stdcall nb_xcross_map(DWORD value, void *occ) {
    DWORD raw;
    int i;
    if (!occ || !g_nb_ncross) return value;
    raw = ((DWORD (__stdcall *)(void *))g_nb_a93d)(occ);
    if (raw >= 65536 || !g_base[raw]) return value;
    for (i = 0; i < g_nb_ncross; i++)
        if (g_nb_cross[i].over == raw && g_nb_cross[i].cross == (value >> 8)) {
            InterlockedIncrement(&g_nb_n_xcross);
            return ((DWORD)g_nb_cross[i].piece << 8) | (value & 0xff);
        }
    return value;
}

/* replaces `call FUN_1002207c` (cdecl: value, &id, &state) at 0x10016953; ebp is FUN_100167d4's frame */
static __declspec(naked) void nb_xcross_thunk(void) {
    __asm {
        push dword ptr [ebp - 8]
        push dword ptr [esp + 8]
        call nb_xcross_map
        mov dword ptr [esp + 4], eax
        jmp dword ptr [g_nb_207c]
    }
}

static int nb_patch_xcross(BYTE *m) {
    /* FUN_100167d4 must still be the shipped frame: push ebp / mov ebp,esp / sub esp,0x18, and the occupant pointer at
       [ebp-8] fed to FUN_1001a93d at 0x1001681e (push dword [ebp-8]) */
    static const BYTE pro[] = { 0x55, 0x8b, 0xec, 0x83, 0xec, 0x18 };
    static const BYTE occ[] = { 0xff, 0x75, 0xf8 };
    DWORD old;
    nb_cross_load();
    if (!g_nb_ncross) { logf("XCROSS: no crossing table entries, not patched"); return 0; }
    if (!bytes_are(m + 0x167d4, pro, sizeof(pro)) || !bytes_are(m + 0x1681e, occ, sizeof(occ))) {
        logf("### XCROSS: FUN_100167d4 differs from shipped - not patched");
        return 0;
    }
    if (!g_nb_a93d) g_nb_a93d = (DWORD)m + 0x1a93d;
    old = retarget_call(m, 0x16953, 0x2207c, (void *)nb_xcross_thunk);
    if (!old) { logf("### XCROSS: +0x16953 is not `call FUN_1002207c` - not patched"); return 0; }
    g_nb_207c = old;
    logf("XCROSS: %d crossing entr%s, FUN_100167d4 decode at +0x16953 hooked", g_nb_ncross, g_nb_ncross == 1 ? "y" : "ies");
    return 1;
}

/* ---------------------------------------------------------------- arming (called from watcher) */

static int bridge_patch(BYTE *m) {
    int n = 0;
    if (!env_off("SC3NETMOD_INHERIT")) n += nb_patch_inherit(m);
    else logf("INHERIT: off (SC3NETMOD_INHERIT=0)");
    if (!env_off("SC3NETMOD_XCROSS")) n += nb_patch_xcross(m);
    else logf("XCROSS: off (SC3NETMOD_XCROSS=0)");
    return n;
}

static void bridge_stats(void) {
    if (g_nb_n_hway || g_nb_n_remove || g_nb_n_collapse_arg || g_nb_n_xcross)
        logf("stats(netbridge): highway id reads mapped=%ld, removal id reads mapped=%ld, collapse ids mapped=%ld, "
             "variant crossings=%ld", g_nb_n_hway, g_nb_n_remove, g_nb_n_collapse_arg, g_nb_n_xcross);
}
