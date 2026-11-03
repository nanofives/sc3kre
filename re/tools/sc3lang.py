#!/usr/bin/env python3
"""sc3lang.py - the mods' per-language string tables (modlang 2026-11-02).

The mods' UI text lives in the source as SC3TR(es, "mod.key", "Spanish", "English") calls and
{ SC3KEY("mod.key"), "Spanish", "English" } table rows (re/harness/src/sc3lang.h). At run time sc3mods.dll
(sc3mods_lang.c) reads <mods dir>\\sc3lang\\<code>.txt for the game's text language, falls back to en.txt, then to the
inline text.

  extract  re/harness/src -> re/harness/lang/es.txt + en.txt, exactly the inline pairs (never edit those two by hand)
  check    every table: missing / unknown keys, printf conversions that differ from the English, characters code page
           1252 cannot hold (the game's text encoding), and the width report when --fonts is given
  widths   caption widths per language against the layout, from the glyph advances SC3RESIZE_FONTDUMP=1 writes
  render   write a translated table from a JSON {key: text} file (machine translations; header marks them for review)
  convert  rewrite inline  es ? "Spanish" : "English"  pairs into SC3TR(es, "mod.key", ...) (dry run unless --apply),
           then list the UI-looking text it cannot convert by itself (if/else blocks, _es[]/_en[] arrays, one-language text)
  merge    add keys to an existing translated table from a JSON {key: text} file, keeping every line already there

Table format: UTF-8, "key=value", '#' comments. A value with leading/trailing spaces is written in double quotes.
Escapes \\n \\t \\\\ (and \\" inside quotes).

  py re/tools/sc3lang.py extract
  py re/tools/sc3lang.py check [--fonts <inst>\\fontwidths.txt]
  py re/tools/sc3lang.py render fr <fr.json>
  py re/tools/sc3lang.py convert [--apply] [files...]      then extract + check (missing keys in fr..sv = English)
  py re/tools/sc3lang.py merge fr <new_keys.json>
"""
import argparse
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..'))
SRC = os.path.join(REPO, 're', 'harness', 'src')
LANG = os.path.join(REPO, 're', 'harness', 'lang')

STR = r'"(?:[^"\\\n]|\\.)*"(?:\s*"(?:[^"\\\n]|\\.)*")*'
RX_TR = re.compile(r'SC3TR\(\s*[^,;]+?,\s*"([\w.]+)"\s*,\s*(' + STR + r')\s*,\s*(' + STR + r')\s*\)')
RX_KEY = re.compile(r'SC3KEY\(\s*"([\w.]+)"\s*\)\s*,\s*(' + STR + r')\s*,\s*(' + STR + r')')

# The installed game languages (Res\Text folders on the GOG install, titles read 2026-11-02) -> table code
LANGS = {'es': 'Espanol (Res\\Text\\ENGLISH on the dev install)', 'en': 'English (Res\\Text\\English-UK)',
         'fr': 'Francais (FRENCH)', 'de': 'Deutsch (GERMAN)', 'it': 'Italiano (ITALIAN)', 'nl': 'Nederlands (DUTCH)',
         'sv': 'Svenska (SWEDISH)'}


def c_bytes(lit):
    """C string literal(s) -> bytes (cp1252 in this source)"""
    out = bytearray()
    for m in re.finditer(r'"((?:[^"\\\n]|\\.)*)"', lit):
        s, i = m.group(1), 0
        while i < len(s):
            c = s[i]
            if c == '\\':
                n = s[i + 1]
                if n == 'x':
                    j = i + 2
                    while j < len(s) and s[j] in '0123456789abcdefABCDEF':
                        j += 1
                    out.append(int(s[i + 2:j], 16) & 0xff)
                    i = j
                    continue
                out += {'n': b'\n', 't': b'\t', '\\': b'\\', '"': b'"', '0': b'\0', 'r': b'\r'}.get(n, n.encode())
                i += 2
                continue
            out += c.encode('latin-1')
            i += 1
    return bytes(out)


def scan(src=SRC):
    """{key: (es, en, [locations])}; exits on a key with two different texts"""
    keys, bad = {}, []
    for f in sorted(glob.glob(os.path.join(src, '*.c'))):
        text = open(f, encoding='latin-1').read()
        for rx in (RX_TR, RX_KEY):
            for m in rx.finditer(text):
                k = m.group(1)
                es = c_bytes(m.group(2)).decode('cp1252')
                en = c_bytes(m.group(3)).decode('cp1252')
                loc = '%s:%d' % (os.path.basename(f), text.count('\n', 0, m.start()) + 1)
                if k in keys:
                    if keys[k][:2] != (es, en):
                        bad.append('%s: %s has %r / %r, %s has %r / %r' % (k, keys[k][2][0], keys[k][0], keys[k][1], loc, es, en))
                    keys[k][2].append(loc)
                else:
                    keys[k] = (es, en, [loc])
    if bad:
        sys.exit('same key, different text:\n  ' + '\n  '.join(bad))
    return keys


def esc(v):
    e = v.replace('\\', '\\\\').replace('\n', '\\n').replace('\t', '\\t')
    if not v or v != v.strip() or v.startswith('"'):
        e = '"' + e.replace('"', '\\"') + '"'
    return e


def unesc(v):
    q = len(v) >= 2 and v[0] == '"' and v[-1] == '"'
    v = v[1:-1] if q else v.strip()
    out, i = [], 0
    while i < len(v):
        if v[i] == '\\' and i + 1 < len(v):
            out.append({'n': '\n', 't': '\t'}.get(v[i + 1], v[i + 1]))
            i += 2
        else:
            out.append(v[i])
            i += 1
    return ''.join(out)


def read_table(path):
    t = {}
    for ln in open(path, encoding='utf-8-sig'):
        ln = ln.rstrip('\r\n')
        s = ln.lstrip()
        if not s or s[0] in '#;' or '=' not in s:
            continue
        k, v = s.split('=', 1)
        t[k.strip()] = unesc(v)
    return t


def write_table(path, code, rows, header):
    """rows: [(key, value, comment-or-None)]"""
    with open(path, 'w', encoding='utf-8', newline='\r\n') as f:
        for h in header:
            f.write('# ' + h + '\n' if h else '#\n')
        f.write('\n')
        last = None
        for k, v, c in rows:
            mod = k.split('.')[0]
            if mod != last:
                f.write('\n# ---- %s\n' % mod)
                last = mod
            if c:
                f.write('# %s\n' % c)
            f.write('%s=%s\n' % (k, esc(v)))


def fmt_sig(s):
    """the loader's lang_sig: length modifier + conversion per argument, '*' kept, '%%' skipped"""
    out = []
    for m in re.finditer(r'%([-+ #0]*)([\d*]*)(?:\.([\d*]*))?([hlLIwq]*)([a-zA-Z%])', s):
        if m.group(5) == '%':
            continue
        stars = ('*' * (m.group(2) or '').count('*')) + ('*' * (m.group(3) or '').count('*'))
        out.append(stars + m.group(4) + m.group(5))
    return ','.join(out)


def cmd_extract(a):
    keys = scan(a.src)
    os.makedirs(a.lang, exist_ok=True)
    for code, idx in (('es', 0), ('en', 1)):
        rows = [(k, keys[k][idx], ', '.join(sorted({l.split(':')[0] for l in keys[k][2]})) if code == 'en' else None)
                for k in sorted(keys)]
        write_table(os.path.join(a.lang, code + '.txt'), code, rows, [
            'sc3lang %s - %s' % (code, LANGS[code]),
            'GENERATED from the inline %s text in re/harness/src by re/tools/sc3lang.py extract. Do not edit:' % (
                'Spanish' if code == 'es' else 'English'),
            'change the SC3TR(...) / SC3KEY(...) text in the source and run extract again.',
            'Format: UTF-8, key=value, "quoted" when the value has leading or trailing spaces, \\n escapes.'])
    print('extract: %d keys -> %s\\es.txt, en.txt' % (len(keys), a.lang))


def load_fonts(path):
    fonts = {}
    for ln in open(path):
        p = ln.split()
        if len(p) == 258 and p[0] == 'font':
            fonts[int(p[1], 16)] = [int(x) for x in p[2:]]
    return fonts


def text_w(font, s):
    b = s.encode('cp1252', 'replace')
    return sum(font[c] for c in b)


# Layout spec (2026-11-02, from the sc3resize source): (key or tab strip, font id, room in px, kind).
# kind: label = text box width, check = checkbox width (the box takes ~18 px), button = button width (~10 px padding),
# graph = Graficas checkbox (font 0x11, 14 px box). Room = the width the code passes, or (marked) the room seen in the
# French pictures of 2026-11-02. Calibration: an item 1-4 px over sits on its neighbour or the edge but stays readable
# (Spanish "Botones de deshacer" 144/140 is the owner's look); clipping showed from about 6 px over.
LAYOUT = [
    ('resize.interface_scale', 0xf, 180, 'label'), ('resize.show_fps', 0xf, 96, 'check'),
    ('resize.show_profiler', 0xf, 120, 'check'), ('resize.extra_zoom', 0xf, 120, 'check'),
    ('resize.arrow_speed', 0xf, 96, 'label'), ('resize.drag_speed', 0xf, 96, 'label'),
    ('resize.mod_options', 0xf, 150, 'button'), ('resize.mod_options_2', 0xf, 300, 'label'),
    ('resize.interface', 0xf, 200, 'label'), ('resize.performance', 0xf, 200, 'label'),
    ('resize.buildings', 0xf, 190, 'label'), ('resize.move_button', 0xf, 170, 'check'),
    ('resize.build_over_zones', 0xf, 176, 'check'), ('resize.fps_limit', 0xf, 90, 'label'),
    ('resize.autosave', 0xf, 200, 'label'), ('resize.autosave_2', 0xf, 120, 'check'),
    ('resize.show_notice', 0xf, 112, 'check'), ('resize.every', 0xf, 50, 'label'), ('resize.camera', 0xf, 180, 'label'),
    ('resize.past_map_edge', 0xf, 124, 'label'), ('resize.push_camera_when_building', 0xf, 234, 'check'),
    ('resize.after_restarting_game', 0xf, 300, 'label'), ('resize.edge_scroll', 0xf, 140, 'check'),
    ('resize.undo', 0xf, 140, 'check'), ('resize.undo_buttons', 0xf, 140, 'check'), ('resize.back', 0xf, 110, 'button'),
    ('resize.copy_id', 0xf, 92, 'button'), ('resize.move', 0xf, 80, 'button'), ('resize.empty', 0xf, 80, 'button'),
    ('lifespan.lifespan', 0xf, 84, 'button'), ('lifespan.back', 0xf, 76, 'button'),
    ('lifespan.as_new', 0xf, 92, 'button'), ('lifespan.new', 0xf, 92, 'button'), ('lifespan.restore_2', 0xf, 92, 'button'),
    ('lifespan.restore', 0xf, 150, 'button', '$1,246'), ('lifespan.restore_all', 0xf, 196, 'button', '$12,345'),
    ('resize.no_limit', 0xf, 60, 'label'),   # FPS radio at the dialog edge: "Sin limite" (56) fits, "Sans limite" (66) clipped
    # round 2026-11-02b keys. A tuple = printf arguments (sample values, '@key' = that key's text in the same language).
    # room None = no width in the code: compared with Spanish (shown in game), flagged when 8+ px wider than Spanish.
    ('lifespan.rebuild_2', 0xf, 92, 'button'), ('lifespan.repair', 0xf, 92, 'button'),          # Vida util rows (QI_BW)
    ('lifespan.rebuild_free', 0xf, 150, 'button'), ('lifespan.rebuild', 0xf, 150, 'button', '$1,246'),   # query (RS_BW)
    ('lifespan.repair_free', 0xf, 150, 'button'),
    ('lifespan.that_age_dead', 0xf, 355, 'label', (41, 3, '1,234,567')),
    ('lifespan.dead_rebuild', 0xf, 263, 'label', ('12,345',)), ('lifespan.dead_date_damaged_free', 0xf, 263, 'label'),
    ('dataview.red_trips_with_no', 0xf, 316, 'label'),                                             # transit map caption
    ('dataview.transit_share', 0xf, 316, 'label', ('@dataview.this_month_so_far', 12, 3, '1.473')),
    ('dataview.no_trip_data_sc3resize', 0xf, 316, 'label'), ('dataview.no_trips_counted_yet', 0xf, 316, 'label'),
    ('dataview.use_transit', 0xf, None, 'label'), ('dataview.no_transit', 0xf, None, 'label'),   # legend (stock label)
    ('dataview.public_transit_map', 0xf, 380, 'label'),
    ('cuadros.red_capacity_short_green', 0xf, 370, 'label'),                                      # Cuadros legend line
    # placement tooltip: no line break, cut at 768 px while a hint shows (PLACEHINTS.md), "$12,345  " cost text first
    ('placehints.port_hint', 0x11, None, 'label', ('$12,345  @placehints.airport', 40, 3, 'C', 20000, 45, 78, 'C', 1100, 440,
                                                 '@placehints.runway')),
    ('placehints.port_hint', 0x11, None, 'label', ('$12,345  @placehints.seaport', 40, 3, 'I', 10000, 45, 78, 'I', 1100, 440,
                                                 '@placehints.piers')),
    ('placehints.land_value', 0x11, 768, 'label', ('$12,345  R +12%', 'C +8%', 'I -5%', '@placehints.marked', 'R', '+', 10, 6)),
] + [(k, 0xf, 133, 'label') for k in (   # query dialog rows, label column: "Cout de construction :" (133) met the values
    'lifespan.build_cost', 'lifespan.declines_from', 'lifespan.life_left', 'lifespan.output', 'lifespan.months_overworked',
    'lifespan.beds_this_one', 'lifespan.doctors_this_one', 'lifespan.teachers_this_one', 'lifespan.professors_this_one')
] + [(k, 0x11, 120, 'graph') for k in (   # Graficas checkbox columns 120 px apart, font 0x11, box 14 (fr picture 2026-11-02)
    'graphs.grp_income_expenses', 'graphs.grp_power_sup_dem', 'graphs.grp_water_sup_deliv', 'graphs.grp_rci_demand',
    'graphs.grp_air_water_pollut', 'graphs.grp_tax_rates', 'graphs.grp_debt_bonds', 'graphs.grp_jobs_workers',
    'graphs.grp_schools', 'graphs.grp_colleges', 'graphs.grp_hospitals', 'graphs.grp_garbage', 'graphs.grp_unpowered',
    'graphs.grp_abandoned')]
# Tab strips: (name, keys in order, font, room = rule x1 - x0 - 4 from the VDTABS> strip log, 2026-11-02 at 2560x1351:
# Graficas rule 6..362, Cuadros rule 6..380). tb_layout fits when sum + n * (4 px min padding + 2 px gap) <= room.
STRIPS = [
    ('Graficas tabs', ['graphs.tab_city', 'graphs.tab_economy', 'graphs.tab_services', 'graphs.tab_utilities',
                       'graphs.tab_environment'], 0xf, 352),
    ('Cuadros tabs', ['cuadros.tab_education', 'cuadros.tab_health', 'cuadros.tab_population', 'cuadros.tab_power',
                      'cuadros.tab_garbage', 'cuadros.tab_water', 'cuadros.tab_transport'], 0x11, 370),
]
PAD = {'label': 0, 'check': 18, 'button': 10, 'graph': 14}


def width_report(tables, fonts, strip_room):
    """lines of the report and the number of overflows"""
    out, over = [], 0
    codes = [c for c in LANGS if c in tables]
    out.append('| item | font | room | ' + ' | '.join(codes) + ' |')
    out.append('|---|---|---|' + '---|' * len(codes))
    for name, keys, fid, _ in STRIPS:
        room = strip_room.get(name, _)
        if fid not in fonts:
            continue
        cells = []
        for c in codes:
            ws = [text_w(fonts[fid], tables[c].get(k, tables['en'].get(k, ''))) for k in keys]
            need = sum(ws) + 6 * len(ws)   # tb_layout: 4 px minimum padding + 2 px gap per tab (ROUND), x1 test
            bad = room is not None and need > room
            over += bad
            cells.append(('**%d OVER**' if bad else '%d') % need)
        out.append('| %s (%d tabs, min padding) | 0x%x | %s | %s |' % (name, len(keys), fid, room if room else '?',
                                                                       ' | '.join(cells)))
    for it in LAYOUT:
        k, fid, room, kind = it[:4]
        arg = it[4] if len(it) > 4 else None
        if fid not in fonts:
            continue
        cells, ws = [], {}
        for c in codes:
            tab = tables[c]
            t = tab.get(k, tables['en'].get(k, ''))
            if isinstance(arg, tuple):   # printf with sample arguments; '@key' inside a string = that key's text
                def sub(v):
                    if not isinstance(v, str):
                        return v
                    return re.sub(r'@([\w.]+)', lambda m: tab.get(m.group(1), tables['en'].get(m.group(1), '')), v)
                if isinstance(arg[0], str) and arg[0].startswith('$') and '%s' in t:   # cost text before the hint
                    lead, rest = sub(arg[0]).split('  ', 1)
                    vals = tuple(sub(v) for v in (rest,) + arg[1:])
                    t = lead + '  ' + re.sub(r'%l([dc])', r'%\1', t) % vals
                else:
                    t = re.sub(r'%l([dc])', r'%\1', t) % tuple(sub(v) for v in arg)
            elif arg:
                t = t.replace('%s', arg)
            ws[c] = text_w(fonts[fid], t) + PAD[kind]
        r = room if room is not None else ws.get('es', 0) + 8
        for c in codes:
            bad = ws[c] > r
            over += bad
            cells.append(('**%d OVER**' if bad else '%d') % ws[c])
        out.append('| %s (%s) | 0x%x | %s | %s |' % (k, kind, fid, room if room is not None else 'es+8',
                                                     ' | '.join(cells)))
    return out, over


def cmd_check(a):
    keys = scan(a.src)
    tables = {}
    problems = 0
    for p in sorted(glob.glob(os.path.join(a.lang, '*.txt'))):
        code = os.path.splitext(os.path.basename(p))[0]
        t = read_table(p)
        tables[code] = t
        miss = [k for k in keys if k not in t]
        extra = [k for k in t if k not in keys]
        sig = [k for k in t if k in keys and fmt_sig(t[k]) != fmt_sig(keys[k][1])]
        enc = []
        for k, v in t.items():
            try:
                v.encode('cp1252')
            except UnicodeEncodeError:
                enc.append(k)
        same = []
        if code in ('es', 'en'):
            idx = 0 if code == 'es' else 1
            same = [k for k in keys if k in t and t[k] != keys[k][idx]]
        print('%s.txt: %d keys, %d missing, %d unknown, %d format mismatches, %d not in cp1252%s' % (
            code, len(t), len(miss), len(extra), len(sig), len(enc),
            (', %d differ from the source (run extract)' % len(same)) if code in ('es', 'en') else ''))
        for k in miss[:15]:
            print('   missing  %s' % k)
        for k in extra[:15]:
            print('   unknown  %s' % k)
        for k in sig:
            print('   format   %s: %r vs English %r' % (k, fmt_sig(t[k]), fmt_sig(keys[k][1])))
        for k in enc:
            print('   cp1252   %s: %r' % (k, t[k]))
        for k in same[:15]:
            print('   stale    %s' % k)
        problems += len(sig) + len(enc) + len(same) + (len(miss) if code in ('es', 'en') else 0)
    if a.fonts:
        rows, over = width_report(tables, load_fonts(a.fonts), dict(a.strip or []))
        print()
        print('\n'.join(rows))
        print('\n%d item(s) over their room (estimate: glyph advances + padding guess)' % over)
    sys.exit(1 if problems else 0)


def cmd_render(a):
    keys = scan(a.src)
    tr = json.load(open(a.json, encoding='utf-8'))
    rows, todo = [], 0
    for k in sorted(keys):
        v = tr.get(k)
        if v is None:
            todo += 1
            continue
        rows.append((k, v, 'en: ' + esc(keys[k][1])))
    write_table(os.path.join(a.lang, a.code + '.txt'), a.code, rows, [
        'sc3lang %s - %s' % (a.code, LANGS.get(a.code, a.code)),
        'MACHINE TRANSLATION, NEEDS NATIVE REVIEW (modlang 2026-11-02). Each line is preceded by the English it',
        'translates. Keep every %d / %s / %ld / %.40s / %% exactly as in the English, in the same order: a line',
        'whose conversions differ is ignored at run time and the English shows instead (logged in sc3mods.log).',
        'A missing key shows the English. Format: UTF-8, key=value, "quoted" for leading/trailing spaces.'])
    print('render: %s.txt %d keys, %d left to English' % (a.code, len(rows), todo))


# convert: file -> key prefix. A file not listed takes its name without "sc3" / "sc3resize_" (sc3foo_bar.c -> foo_bar).
PREFIX = {'sc3resize.c': 'resize', 'sc3resize_restore.c': 'lifespan', 'sc3resize_vdbars.c': 'cuadros',
          'sc3resize_graphs.c': 'graphs', 'sc3resize_rcibars.c': 'rcibars', 'sc3resize_vdtabs.c': 'vdtabs',
          'sc3restore.c': 'restore', 'sc3landfill.c': 'landfill', 'sc3undo.c': 'undo', 'sc3dataview.c': 'dataview',
          'sc3autosave.c': 'autosave', 'sc3bigcity.c': 'bigcity'}
# the language tests in use on 2026-11-02 (a new one: add it here)
LANG_CONDS = r'(es|ho_spanish\(\)|g_lang_es|vb_es\(\)|g_gn_es|g_req_es|is_es|g_tp_es|spanish)'
RX_PAIR = re.compile(r'(?<![\w.>])' + LANG_CONDS + r'\s*\?\s*(' + STR + r')\s*:\s*(' + STR + ')')
RX_SPANISH = re.compile(r'\\x[c-f][0-9a-f]|\b(de|del|la|las|los|el|sin|con|por|para|ciudad|edificios?|vaciar|restaurar|'
                        r'mover|volver|ver|guardar|deshacer|rehacer|mapa|tr\\xe1fico|agua|energ|basura|calles?|viajes?|autoguard\w*|enorme)\b',
                        re.I)
RX_SKIPLINE = re.compile(r'logf\(|LOG\(|OutputDebugString|SC3TR\(|SC3KEY\(|GetPrivateProfile|WritePrivateProfile|'
                         r'GetEnvironmentVariable|GetModuleHandle|GetProcAddress|LoadLibrary|CreateFile|_snprintf\(\s*g_log')


def prefix_of(fname):
    if fname in PREFIX:
        return PREFIX[fname]
    b = os.path.splitext(fname)[0]
    for pre in ('sc3resize_', 'sc3netmod_', 'sc3'):
        if b.startswith(pre):
            return b[len(pre):] or b
    return b


def slug(en):
    t = re.sub(r'%[-+ #0]*[\d*]*(?:\.[\d*]+)?[hlL]*[a-zA-Z%]', ' ', en.lower())
    t = re.sub(r'\((ctrl|strg)\+\w\)', ' ', t)
    w = [x for x in re.findall(r'[a-z0-9]+', t) if x not in ('the', 'a', 'of', 'to', 'is', 'it')]
    return '_'.join(w[:4]) or 'text'


def code_lines(text):
    """(line number, code without comments) for every line"""
    in_c = False
    for i, ln in enumerate(text.split('\n'), 1):
        code = ln
        if in_c:
            if '*/' not in code:
                continue
            code, in_c = code.split('*/', 1)[1], False
        code = re.sub(r'/\*.*?\*/', '', code)
        if '/*' in code:
            code, in_c = code.split('/*')[0], True
        yield i, code.split('//')[0]


def cmd_convert(a):
    existing = scan(a.src)                                   # keys already in the source: reuse, never collide
    by_text = {(k.split('.')[0], v[0], v[1]): k for k, v in existing.items()}
    used = set(existing)
    files = [os.path.join(a.src, f) if not os.path.isabs(f) else f for f in a.files] or \
        sorted(glob.glob(os.path.join(a.src, '*.c')))
    total = 0
    for f in files:
        fname = os.path.basename(f)
        if fname in ('sc3mods_lang.c',):
            continue
        pre = prefix_of(fname)
        src = open(f, encoding='latin-1').read()
        out, last, n = [], 0, 0
        for m in RX_PAIR.finditer(src):
            ls = src.rfind('\n', 0, m.start()) + 1
            stmt = src[max(src.rfind(';', 0, m.start()), src.rfind('{', 0, m.start()), src.rfind('}', 0, m.start())):m.start()]
            line = src[ls:m.start()]
            if 'logf(' in stmt or 'logf(' in line or 'SC3TR(' in line[-12:]:
                continue
            es = c_bytes(m.group(2)).decode('cp1252')
            en = c_bytes(m.group(3)).decode('cp1252')
            key = by_text.get((pre, es, en))
            if not key:
                base = pre + '.' + slug(en)
                key, i = base, 2
                while key in used:
                    key, i = '%s_%d' % (base, i), i + 1
                used.add(key)
                by_text[(pre, es, en)] = key
            out.append(src[last:m.start()])
            out.append('SC3TR(%s, "%s", %s, %s)' % (m.group(1), key, m.group(2), m.group(3)))
            last = m.end()
            n += 1
            print('  %s:%d  %s  %r / %r' % (fname, src.count('\n', 0, m.start()) + 1, key, es[:40], en[:40]))
        out.append(src[last:])
        if n and a.apply:
            new = ''.join(out)
            if 'sc3lang.h' not in new and '#include "sc3mods_guard.h"' in new:   # a module root: add the include
                nl = '\r\n' if '#include "sc3mods_guard.h"\r\n' in new else '\n'
                new = new.replace('#include "sc3mods_guard.h"' + nl, '#include "sc3mods_guard.h"' + nl +
                                  '#include "sc3lang.h"   /* modlang: SC3TR, mod text from the per-language tables */' + nl, 1)
            open(f, 'w', encoding='latin-1', newline='').write(new)
        total += n
    print('convert: %d pair(s) %s' % (total, 'rewritten' if a.apply else 'found (dry run, --apply to rewrite)'))
    print('\nby hand (UI-looking text that is not an inline pair; logs, ini and env names skipped):')
    for f in files:
        fname = os.path.basename(f)
        if fname in ('sc3mods_lang.c',):
            continue
        text = open(f, encoding='latin-1').read()
        covered = set()                       # lines inside an SC3TR( / SC3KEY( call that spans several lines
        for rx in (RX_TR, RX_KEY):
            for m in rx.finditer(text):
                a0 = text.count('\n', 0, m.start()) + 1
                covered.update(range(a0, a0 + m.group(0).count('\n') + 1))
        for i, code in code_lines(text):
            if i in covered:
                continue
            if RX_SKIPLINE.search(code) or RX_PAIR.search(code):
                continue
            hits = [t for t in re.findall(STR, code) if len(t) > 4 and RX_SPANISH.search(t)]
            if hits or re.search(r'\b\w+_es\s*\[|if\s*\(\s*' + LANG_CONDS + r'\s*\)', code):
                print('  %s:%d: %s' % (fname, i, code.strip()[:140]))


def cmd_merge(a):
    path = os.path.join(a.lang, a.code + '.txt')
    keys = scan(a.src)
    tr = json.load(open(a.json, encoding='utf-8'))
    have = read_table(path) if os.path.exists(path) else {}
    add = {k: v for k, v in tr.items() if k in keys and k not in have}
    with open(path, 'a', encoding='utf-8', newline='\r\n') as f:
        if add:
            f.write('\n# ---- added by sc3lang.py merge (machine translation, needs native review)\n')
        for k in sorted(add):
            f.write('# en: %s\n%s=%s\n' % (esc(keys[k][1]), k, esc(add[k])))
    print('merge: %s.txt +%d keys (%d in the JSON were already there or unknown)' % (a.code, len(add), len(tr) - len(add)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--src', default=SRC)
    ap.add_argument('--lang', default=LANG)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('extract')
    c = sub.add_parser('check')
    c.add_argument('--fonts')
    c.add_argument('--strip', action='append', type=lambda s: (s.split('=')[0], int(s.split('=')[1])),
                   help='"Graficas tabs=NNN" / "Cuadros tabs=NNN": room in px from the VDTABS> strip log')
    r = sub.add_parser('render')
    r.add_argument('code')
    r.add_argument('json')
    cv = sub.add_parser('convert')
    cv.add_argument('--apply', action='store_true')
    cv.add_argument('files', nargs='*', help='source files (default: every re/harness/src/*.c)')
    mg = sub.add_parser('merge')
    mg.add_argument('code')
    mg.add_argument('json')
    a = ap.parse_args()
    {'extract': cmd_extract, 'check': cmd_check, 'render': cmd_render, 'convert': cmd_convert, 'merge': cmd_merge}[a.cmd](a)


if __name__ == '__main__':
    main()
