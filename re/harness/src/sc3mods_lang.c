/* sc3mods_lang.c - included by sc3mods.c. The mods' text language and the per-language string tables (modlang 2026-11-02).
 *
 * WHY HERE. Every mod needs sc3mods.dll (a mod's DllMain stays inert unless this loader is loading it, sc3mods_guard.h),
 * so the loader is the one place that is always there, with or without sc3resize. Mods reach it through
 * GetProcAddress(GetModuleHandleA("sc3mods.dll"), "sc3mods_tr") in sc3lang.h; an old loader without the export, or
 * SC3MODS_LANGTABLES=0, gives NULL and the mod shows its own inline es/en text exactly as before.
 *
 * LANGUAGE = what the game's text really is, not the folder name or the locale number (the dev install's folder
 * ENGLISH holds Spanish and the locale object reads 1 there, sc3resize ho_spanish). Same probe as ho_spanish: SIMUI's
 * resource key FUN_1008ebbd(0x14e, group 0x029541f4) loads the Preferences dialog title from the game's active
 * SC3StringsWindow.IXF, and the title names the language. Titles read from every shipped Res\Text folder 2026-11-02:
 *   ENGLISH "Preferencias" (Spanish text)  English-UK "Preferences"  FRENCH "Pr\xe9" "f\xe9rences"  GERMAN "Einstellungen"
 *   ITALIAN "Preferenze"  DUTCH "Instellingen"  SWEDISH "Egenskaper"
 * Override: sc3resize.ini [hud] lang=<code> (the key ho_spanish already reads, now any code below), or env SC3MODS_LANG.
 * Before SIMUI.DLL is mapped the language is unknown: sc3mods_tr returns NULL (the mod's inline text) and the probe
 * runs again on the next call.
 *
 * TABLES. <mods dir>\sc3lang\<code>.txt, UTF-8, one "key=value" per line, '#' comments. A value in double quotes keeps
 * its leading/trailing spaces; \n \t \" \\ escapes. Converted to the game's code page 1252 at load (the game's own
 * IXF text is 1252: "Pr\xe9" "f\xe9rences" is 0xE9 in FRENCH\SC3StringsWindow.IXF). Lookup: the language's table, then en.txt,
 * then NULL (the mod's inline text). Every printf conversion of a table value must match the mod's own English text
 * (same conversions in the same order, "%%" ignored), else the line is logged once and English is used.
 */

#define LANG_SLOTS 2048                          /* open addressing, power of two; ~250 keys per table today */
typedef struct { char *key; char *val; signed char ok; } LANG_ENT;   /* ok: 0 unchecked, 1 good, -1 bad format */
typedef struct { LANG_ENT e[LANG_SLOTS]; int n; int loaded; } LANG_TAB;

static CRITICAL_SECTION g_lang_cs;
static int  g_lang_cs_ok;
static int  g_lang_state;                       /* 0 not decided yet, 1 decided, -1 tables off */
static char g_lang_code[8];                     /* "es", "en", ... */
static LANG_TAB *g_lang_tab, *g_lang_en;        /* g_lang_tab == g_lang_en when the language is English */
static int  g_lang_tries;

static const struct { const char *title; const char *code; } k_lang_titles[] = {
    { "Preferencias", "es" }, { "Preferences", "en" }, { "Pr\xe9" "f\xe9rences", "fr" }, { "Einstellungen", "de" },
    { "Preferenze", "it" }, { "Instellingen", "nl" }, { "Egenskaper", "sv" } };
static const char *k_lang_codes[] = { "es", "en", "fr", "de", "it", "nl", "sv", "pt", "da", "no", "fi", "pl" };

static unsigned lang_hash(const char *s) {
    unsigned h = 2166136261u;
    while (*s) { h ^= (unsigned char)*s++; h *= 16777619u; }
    return h;
}

static LANG_ENT *lang_slot(LANG_TAB *t, const char *key) {
    unsigned i = lang_hash(key) & (LANG_SLOTS - 1), k;
    for (k = 0; k < LANG_SLOTS; k++, i = (i + 1) & (LANG_SLOTS - 1))
        if (!t->e[i].key || !strcmp(t->e[i].key, key)) return &t->e[i];
    return NULL;
}

/* UTF-8 -> code page 1252, malloc'd. Characters 1252 lacks become '?' (WideCharToMultiByte default). */
static char *lang_to1252(const char *u, int n) {
    int wn = MultiByteToWideChar(CP_UTF8, 0, u, n, NULL, 0), an;
    WCHAR *w;
    char *a;
    if (wn <= 0) { a = (char *)malloc(1); if (a) a[0] = 0; return a; }
    w = (WCHAR *)malloc((wn + 1) * sizeof(WCHAR));
    if (!w) return NULL;
    MultiByteToWideChar(CP_UTF8, 0, u, n, w, wn);
    an = WideCharToMultiByte(1252, 0, w, wn, NULL, 0, NULL, NULL);
    a = (char *)malloc(an + 1);
    if (a) { WideCharToMultiByte(1252, 0, w, wn, a, an, NULL, NULL); a[an] = 0; }
    free(w);
    return a;
}

/* "key=value" -> unescaped UTF-8 value in place. Returns the value length, -1 for a line without a key. */
static int lang_parse_line(char *ln, char **key, char **val) {
    char *eq, *v, *o, *k;
    int q = 0;
    while (*ln == ' ' || *ln == '\t') ln++;
    if (!*ln || *ln == '#' || *ln == ';') return -1;
    eq = strchr(ln, '=');
    if (!eq || eq == ln) return -1;
    k = eq;
    while (k > ln && (k[-1] == ' ' || k[-1] == '\t')) k--;
    *k = 0;
    *key = ln;
    v = eq + 1;
    if (*v == '"') {
        size_t L = strlen(v);
        if (L >= 2 && v[L - 1] == '"') { v[L - 1] = 0; v++; q = 1; }
    }
    if (!q) {   /* unquoted: trim both ends */
        size_t L;
        while (*v == ' ' || *v == '\t') v++;
        L = strlen(v);
        while (L && (v[L - 1] == ' ' || v[L - 1] == '\t')) v[--L] = 0;
    }
    for (o = v, *val = v; *v; v++) {
        if (*v == '\\' && v[1]) {
            v++;
            *o++ = *v == 'n' ? '\n' : *v == 't' ? '\t' : *v;   /* \" \\ and anything else: the char itself */
        } else *o++ = *v;
    }
    *o = 0;
    return (int)(o - *val);
}

static LANG_TAB *lang_load(const char *code) {
    char path[MAX_PATH];
    HANDLE f;
    DWORD sz, got = 0;
    char *b, *p, *nl;
    LANG_TAB *t;
    int lines = 0, dup = 0;
    _snprintf(path, sizeof(path), "%s\\sc3lang\\%s.txt", g_dir, code);
    path[sizeof(path) - 1] = 0;
    f = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    if (f == INVALID_HANDLE_VALUE) { logf("LANG> no table %s (GetLastError %lu)", path, GetLastError()); return NULL; }
    sz = GetFileSize(f, NULL);
    b = (char *)malloc(sz + 1);
    if (b && !ReadFile(f, b, sz, &got, NULL)) got = 0;
    CloseHandle(f);
    if (!b) return NULL;
    b[got] = 0;
    t = (LANG_TAB *)calloc(1, sizeof(LANG_TAB));
    if (!t) { free(b); return NULL; }
    p = b;
    if ((BYTE)p[0] == 0xEF && (BYTE)p[1] == 0xBB && (BYTE)p[2] == 0xBF) p += 3;   /* UTF-8 BOM */
    for (; p && *p; p = nl) {
        char *key, *val;
        int vn;
        LANG_ENT *e;
        nl = strchr(p, '\n');
        if (nl) { *nl++ = 0; }
        if (*p && p[strlen(p) - 1] == '\r') p[strlen(p) - 1] = 0;
        vn = lang_parse_line(p, &key, &val);
        if (vn < 0) continue;
        lines++;
        if (t->n >= LANG_SLOTS / 2 || !(e = lang_slot(t, key))) { logf("LANG> %s: table full at %s", code, key); break; }
        if (e->key) { dup++; free(e->val); } else { e->key = _strdup(key); t->n++; }
        e->val = lang_to1252(val, vn);
    }
    free(b);
    t->loaded = 1;
    logf("LANG> loaded %s: %d keys%s", path, t->n, dup ? " (duplicate keys: the last one wins)" : "");
    return t;
}

/* printf conversions of s, '%%' skipped, written as "ld,s,.40s" -> length modifier + conversion (flags, width and
   precision are not part of the argument list... except '*', which takes an int, so it is kept). */
static void lang_sig(const char *s, char *out, int cap) {
    int n = 0;
    out[0] = 0;
    for (; *s; s++) {
        char c[8];
        int k = 0;
        if (*s != '%') continue;
        if (s[1] == '%') { s++; continue; }
        s++;
        while (*s && strchr("-+ #0", *s)) s++;
        while (*s && (isdigit((unsigned char)*s) || *s == '*' || *s == '.')) { if (*s == '*' && k < 6) c[k++] = '*'; s++; }
        while (*s && strchr("hlLIwq", *s)) { if (k < 6) c[k++] = *s; s++; }
        if (!*s) break;
        if (k < 7) c[k++] = *s;
        c[k] = 0;
        if (n + k + 2 >= cap) break;
        if (n) out[n++] = ',';
        memcpy(out + n, c, k + 1);
        n += k;
    }
}

static void lang_decide(void) {
    char p[MAX_PATH], v[16];
    const char *how = NULL;
    int i;
    v[0] = 0;
    if (GetEnvironmentVariableA("SC3MODS_LANGTABLES", v, sizeof(v)) && v[0] == '0') {
        g_lang_state = -1;
        logf("LANG> tables off (SC3MODS_LANGTABLES=0): every mod shows its own inline es/en text");
        return;
    }
    v[0] = 0;
    if (GetEnvironmentVariableA("SC3MODS_LANG", v, sizeof(v)) && v[0]) how = "env SC3MODS_LANG";
    if (!v[0]) {
        _snprintf(p, sizeof(p), "%s\\sc3resize.ini", g_dir); p[sizeof(p) - 1] = 0;
        GetPrivateProfileStringA("hud", "lang", "", v, sizeof(v), p);
        if (v[0]) how = "sc3resize.ini [hud] lang";
    }
    if (v[0]) {
        for (i = 0; v[i]; i++) if (v[i] >= 'A' && v[i] <= 'Z') v[i] += 32;
        for (i = 0; i < (int)(sizeof(k_lang_codes) / sizeof(k_lang_codes[0])); i++)
            if (!strcmp(v, k_lang_codes[i])) break;
        if (i == (int)(sizeof(k_lang_codes) / sizeof(k_lang_codes[0]))) {
            logf("LANG> %s = \"%s\" is not a language code I know: ignored, reading the game's text", how, v);
            v[0] = 0;
        }
    }
    if (!v[0]) {
        HMODULE sui = GetModuleHandleA("SIMUI.DLL");
        DWORD key[8], fn;
        const char *t = NULL, *code = NULL;
        if (!sui) { if (g_lang_tries++ < 3) logf("LANG> asked before SIMUI.DLL is mapped: inline text for now"); return; }   /* asked again next call */
        memset(key, 0, sizeof(key));
        __try {
            typedef void (__fastcall *KEYCTOR)(void *ecx, void *edx, DWORD inst, DWORD group);   /* __thiscall, 2 args */
            typedef void (__fastcall *KEYDTOR)(void *ecx, void *edx);
            ((KEYCTOR)((BYTE *)sui + 0x8ebbd))(key, NULL, 0x14e, 0x29541f4);
            fn = key[1];                                          /* the loaded string object, 0 if the key missed */
            for (i = 1; fn && !IsBadReadPtr((void *)fn, 0x14) && !code && i < 5; i++) {
                const char *c = ((const char **)fn)[i];
                int k;
                if (!c || IsBadReadPtr(c, 10)) continue;
                for (k = 0; k < (int)(sizeof(k_lang_titles) / sizeof(k_lang_titles[0])) && !code; k++) {
                    size_t L = strlen(k_lang_titles[k].title);
                    if (!IsBadReadPtr(c, L) && !memcmp(c, k_lang_titles[k].title, L)) { code = k_lang_titles[k].code; t = c; }
                }
                if (!t) t = c;
            }
            ((KEYDTOR)((BYTE *)sui + 0x8ebea))(key, NULL);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            logf("LANG> fault 0x%08lX reading the Preferences title: English", GetExceptionCode());
            code = NULL;
        }
        if (!code) {
            if (!t) { if (g_lang_tries++ < 3) logf("LANG> Preferences title not loaded yet: inline text for now"); return; }
            logf("LANG> Preferences title \"%.24s\" is no language I know: English", t ? t : "(none)");
            code = "en";
        } else logf("LANG> game text language: \"%.24s\" -> %s", t, code);
        lstrcpynA(v, code, sizeof(v));
    } else logf("LANG> language %s from %s", v, how);
    lstrcpynA(g_lang_code, v, sizeof(g_lang_code));
    g_lang_en = lang_load("en");
    g_lang_tab = strcmp(g_lang_code, "en") ? lang_load(g_lang_code) : g_lang_en;
    g_lang_state = 1;
}

/* The mods' language code ("es", "en", "fr", "de", "it", "nl", "sv"), "" until it is known or with tables off. */
const char * __stdcall sc3mods_lang(void) {
    if (!g_lang_cs_ok) return "";
    EnterCriticalSection(&g_lang_cs);
    if (!g_lang_state) lang_decide();
    LeaveCriticalSection(&g_lang_cs);
    return g_lang_state == 1 ? g_lang_code : "";
}

static const char *lang_get(LANG_TAB *t, const char *code, const char *key, const char *en) {
    LANG_ENT *e;
    if (!t || !(e = lang_slot(t, key)) || !e->key || !e->val) return NULL;
    if (!e->ok) {
        char a[96], b[96];
        lang_sig(e->val, a, sizeof(a));
        lang_sig(en ? en : "", b, sizeof(b));
        e->ok = strcmp(a, b) ? -1 : 1;
        if (e->ok < 0) logf("LANG> %s.txt %s: conversions \"%s\" differ from the mod's \"%s\": English used", code, key, a, b);
    }
    return e->ok > 0 ? e->val : NULL;
}

/* Text for key in the mods' language, `en` = the mod's own English (the format reference). NULL = use your inline text. */
const char * __stdcall sc3mods_tr(const char *key, const char *en) {
    const char *r = NULL;
    if (!g_lang_cs_ok || !key) return NULL;
    EnterCriticalSection(&g_lang_cs);
    if (!g_lang_state) lang_decide();
    if (g_lang_state == 1) {
        r = lang_get(g_lang_tab, g_lang_code, key, en);
        if (!r && g_lang_tab != g_lang_en) r = lang_get(g_lang_en, "en", key, en);
        if (!r) {
            static int miss;
            if (miss++ < 20) logf("LANG> no text for %s in %s.txt or en.txt: the mod's inline text", key, g_lang_code);
        }
    }
    LeaveCriticalSection(&g_lang_cs);
    return r;
}

static void lang_init(void) { InitializeCriticalSection(&g_lang_cs); g_lang_cs_ok = 1; }
