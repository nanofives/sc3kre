/* ===== CHEATFIX (2026-11-06): Extra Cheats' "SimDate <m> <d> <y>" never ran. =====
 * cGZCheatCodeManager::DoesCheatCodeMatch (SC3U 0x0046ac89, thiscall (cIGZString const&, ulong& id), returns 1 for a
 * prefix match, 2 for an exact one) lower-cases the typed text and returns the FIRST registered cheat whose text the
 * input starts with. The stock cheat "sim" (id 0xE352E88F) is registered before the plugin's "SimDate" (0x1F92F286),
 * so "SimDate 5 20 1990" always matched "sim" (measured with a Frida hook on the match and on SendCheatNotifications:
 * id 0xe352e88f; SIMCITY SetDate 0x10005398 never called). "moolah" / "dotcom" have no shorter stock prefix.
 * Fix: after the stock match, text that starts with "simdate" followed by a space or the end is given the SimDate id,
 * only while SC3KExtraCheats.dll is loaded. SC3RESIZE_CHEATFIX=0: nothing installed. */
static int   g_cheatfix = 1;
static void *g_cf_orig;
#define CF_SIM_ID      0xE352E88F
#define CF_SIMDATE_ID  0x1F92F286

static DWORD __fastcall cf_match(void *self, void *edx, void *str, DWORD *id) {
    DWORD a[2], r;
    (void)edx;
    a[0] = (DWORD)str; a[1] = (DWORD)id;
    r = rz_thiscall_ret(self, g_cf_orig, a, 2);
    if ((r & 0xff) && id && *id == CF_SIM_ID && GetModuleHandleA("SC3KExtraCheats.dll")) {
        const char *t = NULL;
        __try { t = (const char *)ho_v(str, 0x18, 0, 0, 0, 0, 0, 0); } __except (EXCEPTION_EXECUTE_HANDLER) { t = NULL; }   /* ToChar */
        if (t && !IsBadReadPtr(t, 8) && !_strnicmp(t, "simdate", 7) && (t[7] == ' ' || t[7] == 0)) {
            *id = CF_SIMDATE_ID;
            logf("CHEATFIX> \"%.40s\" sent to SimDate (the stock \"sim\" cheat matched it first)", t);
            return (r & ~0xffu) | (t[7] == 0 ? 2u : 1u);
        }
    }
    return r;
}

static void cf_install(void) {
    static const BYTE e[5] = { 0xb8, 0x84, 0x7a, 0x4c, 0x00 };   /* mov eax, 0x4c7a84 (EH_prolog setup) */
    if (!g_cheatfix) { logf("CHEATFIX> off (SC3RESIZE_CHEATFIX=0)"); return; }
    if (GetModuleHandleA(NULL) != (HMODULE)0x00400000) return;
    if (ho_hook((HMODULE)0x00400000, 0x6ac89, e, 5, (void *)cf_match, &g_cf_orig, "cheat match 0x0046ac89"))
        logf("CHEATFIX> installed: SimDate reaches Extra Cheats");
}
