/* sc3lang.h - mod UI text from the per-language tables (modlang 2026-11-02).
 *
 * SC3TR(es, "key", "Spanish", "English") returns the text for "key" in the game's text language, from
 * <mods dir>\sc3lang\<code>.txt through sc3mods.dll (sc3mods_lang.c: language detection, tables, English fallback,
 * printf-format check). The two inline strings stay in the source: they are what re/tools/sc3lang.py extracts into
 * es.txt / en.txt, and they are the text shown when the loader has no table for the key, has no sc3mods_tr export
 * (an older sc3mods.dll), or runs with SC3MODS_LANGTABLES=0 - then `es` picks between them as before this change.
 *
 * Keys are stable ids "<mod>.<name>": change the inline text freely, never reuse a key for a different meaning.
 * Every key must be a string literal inside SC3TR( or SC3KEY( so the extractor finds it.
 */
#ifndef SC3LANG_H
#define SC3LANG_H
#include <windows.h>

typedef const char *(__stdcall *SC3LANG_TR)(const char *key, const char *en);
typedef const char *(__stdcall *SC3LANG_CODE)(void);

static SC3LANG_TR   g_sc3lang_tr;
static SC3LANG_CODE g_sc3lang_code;
static int          g_sc3lang_bound;

static void sc3lang_bind(void) {
    HMODULE m;
    if (g_sc3lang_bound) return;
    g_sc3lang_bound = 1;
    m = GetModuleHandleA("sc3mods.dll");
    if (!m) return;
    g_sc3lang_tr = (SC3LANG_TR)GetProcAddress(m, "sc3mods_tr");
    g_sc3lang_code = (SC3LANG_CODE)GetProcAddress(m, "sc3mods_lang");
}

static const char *sc3lang_tr(int es, const char *key, const char *s_es, const char *s_en) {
    const char *r;
    sc3lang_bind();
    if (g_sc3lang_tr && (r = g_sc3lang_tr(key, s_en)) != NULL) return r;
    return es ? s_es : s_en;
}

/* the mods' language code ("es", "en", "fr", "de", "it", "nl", "sv"); fallback "es"/"en" from the caller's own test */
static const char *sc3lang_code(int es) {
    const char *c;
    sc3lang_bind();
    if (g_sc3lang_code && (c = g_sc3lang_code()) != NULL && c[0]) return c;
    return es ? "es" : "en";
}

/* a key + its two inline texts, for tables of captions: { SC3KEY("mod.key"), "Spanish", "English" } */
typedef struct { const char *key, *es, *en; } SC3TXT;
static const char *sc3lang_txt(int es, const SC3TXT *t) { return sc3lang_tr(es, t->key, t->es, t->en); }

#define SC3TR(es, key, s_es, s_en) sc3lang_tr((es), key, s_es, s_en)
#define SC3KEY(key) key   /* marks a key literal kept in a table of keys, for the extractor */
#endif
