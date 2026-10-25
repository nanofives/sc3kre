"""Build the ladder batch TSV from the 2026-10-23..25 evidence. Run from the worktree root.
Rules: never lower a level, never replace an existing name/subsystem, notes always appended."""
import json, sys, csv, io, collections
sys.path.insert(0, 're/scripts')
import tracker
SP = sys.argv[1]
t = tracker.Tracker('functions.csv')
MODS = {m.upper(): m for m in t.modules()}
ORD = tracker.ORDER
TAG = '[ladder 2026-10-25]'
AB = {'AUDIO.DLL': 'audio', 'GIMEX.DLL': 'gimex', 'GZGRAPHICD.DLL': 'gzgfx', 'GZRESOURCED.DLL': 'gzres',
      'GZSERVICED.DLL': 'gzsvc', 'GZSOUNDD.DLL': 'gzsound', 'GZTOOLSD.DLL': 'gztools', 'GZWIND.DLL': 'gzwin',
      'GZWWWD.DLL': 'gzwww', 'MAXISADDON.DLL': 'maxisaddon', 'SCENARIO.DLL': 'scenario', 'SIMADV.DLL': 'simadv',
      'SIMBABLD.DLL': 'simbabld', 'SIMCITY.DLL': 'simcity', 'SIMDIRT.DLL': 'dirt', 'SIMDSTR.DLL': 'dstr',
      'SIMECO.DLL': 'simeco', 'SIMGEOM.DLL': 'simgeom', 'SIMINIT.DLL': 'siminit', 'SIMMISC.DLL': 'simmisc',
      'SIMNTWRK.DLL': 'ntwrk', 'SIMRCI.DLL': 'simrci', 'SIMSERV.DLL': 'simserv', 'SIMSPR.DLL': 'spr',
      'SIMTRANSIT.DLL': 'transit', 'SIMUI.DLL': 'ui', 'SIMUTIL.DLL': 'simutil', 'SIMVARIABLES.DLL': 'simvar',
      'STRTSIM.DLL': 'strtsim'}
RC = 'gzcom-refcount'
PL = 'verify/reload1024/plain_refcount_vtables.txt'
PLE = 'verify/reload1024/plain_refcount_vtables_ecx.txt'
LE1 = 'verify/refaudit/le1_refcount_vtables.txt'

# ---- refcount bodies: class tag per (module, body); framework copies default by offset
B = json.load(open(f'{SP}/bodies.json'))
TAGS = {
 ('AUDIO.DLL', '0x10011277'): 'audioinfo', ('AUDIO.DLL', '0x1001127e'): 'audioinfo',
 ('GZRESOURCED.DLL', '0x100039f1'): 'tokenrecord', ('GZRESOURCED.DLL', '0x10015b03'): 'resource',
 ('GZRESOURCED.DLL', '0x1000b7c0'): 'resource', ('GZRESOURCED.DLL', '0x10015b0a'): 'resourcemgr',
 ('SCENARIO.DLL', '0x100012ae'): 'functor', ('SCENARIO.DLL', '0x100012b5'): 'occfilter',
 ('SCENARIO.DLL', '0x1000c9a7'): 'layeralgo', ('SCENARIO.DLL', '0x10005b6f'): 'layer', ('SCENARIO.DLL', '0x100099a1'): 'layer',
 ('SIMADV.DLL', '0x100064fd'): 'msgrecord', ('SIMADV.DLL', '0x10006504'): 'msgrecord',
 ('SIMADV.DLL', '0x1000b606'): 'record50', ('SIMADV.DLL', '0x1000b60d'): 'record50',
 ('SIMADV.DLL', '0x10011702'): 'record5c', ('SIMADV.DLL', '0x10011709'): 'record5c',
 ('SIMADV.DLL', '0x1001c97a'): 'record58', ('SIMADV.DLL', '0x1001c981'): 'record58',
 ('SIMDIRT.DLL', '0x1001b9bf'): 'dataadapter', ('SIMDIRT.DLL', '0x1001daa9'): 'dataadapter',
 ('SIMDSTR.DLL', '0x10005674'): 'firefunctor', ('SIMDSTR.DLL', '0x1000567b'): 'firefunctor',
 ('SIMDSTR.DLL', '0x1000652f'): 'fireinstance', ('SIMDSTR.DLL', '0x100066f0'): 'fireinstance',
 ('SIMDSTR.DLL', '0x10007661'): 'layer', ('SIMDSTR.DLL', '0x10008dc8'): 'layer',
 ('SIMDSTR.DLL', '0x10009884'): 'layeralgo', ('SIMDSTR.DLL', '0x100098c1'): 'layeralgo',
 ('SIMDSTR.DLL', '0x1000e087'): 'instance', ('SIMDSTR.DLL', '0x1000e4eb'): 'riotinstance',
 ('SIMDSTR.DLL', '0x100214f6'): 'paradeinstance', ('SIMDSTR.DLL', '0x10013a81'): 'tornadoinstance',
 ('SIMDSTR.DLL', '0x10014090'): 'tornadoinstance', ('SIMDSTR.DLL', '0x10016a93'): 'toxiccloud',
 ('SIMDSTR.DLL', '0x1001715c'): 'toxiccloud',
 ('SIMECO.DLL', '0x100185c7'): 'dataadapter', ('SIMECO.DLL', '0x100185ce'): 'dataadapter',
 ('SIMGEOM.DLL', '0x10003567'): 'functor', ('SIMGEOM.DLL', '0x1000356e'): 'functor',
 ('SIMGEOM.DLL', '0x1001474e'): 'demolishtest', ('SIMGEOM.DLL', '0x10004dab'): 'demolishtest',
 ('SIMGEOM.DLL', '0x10023e54'): 'comptrlist', ('SIMGEOM.DLL', '0x10014a99'): 'fwobject',
 ('SIMBABLD.DLL', '0x12059e64'): 'resource', ('SIMBABLD.DLL', '0x12050943'): 'resource', ('SIMBABLD.DLL', '0x12059e6b'): 'resourcemgr',
 ('SIMINIT.DLL', '0x10004e3b'): 'schememgr', ('SIMINIT.DLL', '0x100062ad'): 'schememgr',
 ('SIMINIT.DLL', '0x1000c175'): 'gfxprobe', ('SIMINIT.DLL', '0x1000c605'): 'attribcache',
 ('SIMINIT.DLL', '0x1000d3b3'): 'attribcache', ('SIMINIT.DLL', '0x1000cd67'): 'functor',
 ('SIMINIT.DLL', '0x1000cd6e'): 'functor', ('SIMINIT.DLL', '0x1000d68d'): 'iterator', ('SIMINIT.DLL', '0x1000d694'): 'iterator',
 ('SIMMISC.DLL', '0x10019b3e'): 'ordinancelayer', ('SIMMISC.DLL', '0x10019b45'): 'ordinancelayer',
 ('SIMMISC.DLL', '0x1002e3f0'): 'dataadapter', ('SIMMISC.DLL', '0x10034523'): 'dataadapter',
 ('SIMRCI.DLL', '0x100318c1'): 'functor', ('SIMRCI.DLL', '0x100318c8'): 'functor',
 ('SIMRCI.DLL', '0x1004288d'): 'dataadapter', ('SIMRCI.DLL', '0x10042894'): 'dataadapter',
 ('SIMSERV.DLL', '0x1001a9e6'): 'dataadapter', ('SIMSERV.DLL', '0x100192ad'): 'dataadapter',
 ('SIMSPR.DLL', '0x1005982a'): 'resource', ('SIMSPR.DLL', '0x10059831'): 'resource', ('SIMSPR.DLL', '0x10041564'): 'comclass',
 ('SIMTRANSIT.DLL', '0x1001499a'): 'dataadapter', ('SIMTRANSIT.DLL', '0x100149a1'): 'dataadapter',
 ('SIMUI.DLL', '0x100139b6'): 'object', ('SIMUI.DLL', '0x10043ba9'): 'wrapper', ('SIMUI.DLL', '0x10090d1c'): 'uiadapter',
 ('SIMUTIL.DLL', '0x1001cc1c'): 'object', ('SIMUTIL.DLL', '0x100053ae'): 'poweralgo', ('SIMUTIL.DLL', '0x1001cc23'): 'dataadapter',
 ('STRTSIM.DLL', '0x10003310'): 'object08', ('STRTSIM.DLL', '0x10015599'): 'object04', ('STRTSIM.DLL', '0x10021980'): 'object10',
 ('STRTSIM.DLL', '0x10010569'): 'crowdproducer', ('STRTSIM.DLL', '0x100110fc'): 'crowdproducer',
 ('STRTSIM.DLL', '0x100076a8'): 'layerobj104', ('STRTSIM.DLL', '0x1001607d'): 'occupant',
 ('STRTSIM.DLL', '0x1001e004'): 'setupobj', ('STRTSIM.DLL', '0x1001e1de'): 'setupobj', ('STRTSIM.DLL', '0x1001e2c3'): 'setupobj2',
}
C4 = {
 ('STRTSIM.DLL', '0x10010569'): 'C4: made atomic by sc3perf STRTSIM_REFCOUNT; owner second-load crash 5 of 18 loads before, 0 of 24 after; the strtsim_refcount=0 arm crashed (verify/reload1024/RESULTS.md s1-2).',
 ('STRTSIM.DLL', '0x100110fc'): 'C4: a lost update destroyed the producer twice (pool double free). Made atomic by sc3perf STRTSIM_REFCOUNT; owner second-load crash 5 of 18 loads before, 0 of 24 after; the strtsim_refcount=0 arm crashed (verify/reload1024/RESULTS.md s1-2).',
}
FIXED = {
 ('STRTSIM.DLL', '0x100076a8'): 'Class at vtable 0x1002b0fc = the STRTSIM layer +0x104 object. Made atomic by sc3perf STRTSIM_REFCOUNT; lifetrace showed it destroyed once (ruled out as the crash) (verify/reload1024/RESULTS.md s2, s5).',
 ('STRTSIM.DLL', '0x1001607d'): 'RACE-PRONE rank 3: cSSStrtSimOccupant family [LINUX-HINT], derived vtables 0x1002AF90/0x1002C9BC/0x1002B7AC share it. Made atomic by sc3perf RES_REFCOUNT strtsim_refcount_ecx; final soak 6 loads, 0 faults (verify/refaudit/RESULTS.md).',
 ('SIMSPR.DLL', '0x1005982a'): 'RACE-PRONE rank 1 resource object (ctor 0x10058a42): census v1 1,601 objs, 80 on 2+ threads incl. the sprite loader, up to 11 switches. Made atomic by sc3perf RES_REFCOUNT res_refcount_simspr; final soak 0 faults (verify/refaudit/RESULTS.md).',
 ('SIMSPR.DLL', '0x10059831'): 'RACE-PRONE rank 1 resource object, reached via thunks 0x100589c6 -> 0x100598fc. Made atomic by sc3perf RES_REFCOUNT res_refcount_simspr; final soak 0 faults (verify/refaudit/RESULTS.md).',
 ('GZRESOURCED.DLL', '0x10015b03'): 'RACE-PRONE rank 2 resource object (ctor 0x1000dc13), body shared with cSLTokenRecord [LINUX-HINT]. Made atomic by sc3perf RES_REFCOUNT res_refcount_gzres; final soak 0 faults (verify/refaudit/RESULTS.md).',
 ('GZRESOURCED.DLL', '0x1000b7c0'): 'RACE-PRONE rank 2 resource object, reached via thunks 0x1000ffdb -> 0x1000b8be. Made atomic by sc3perf RES_REFCOUNT res_refcount_gzres; final soak 0 faults (verify/refaudit/RESULTS.md).',
 ('SCENARIO.DLL', '0x10005b6f'): 'RACE-PRONE rank 4 cSCNScenarioLayer [LINUX-HINT], game + sim, rare. Made atomic by sc3perf RES_REFCOUNT scenario_refcount (verify/refaudit/RESULTS.md).',
 ('SCENARIO.DLL', '0x100099a1'): 'RACE-PRONE rank 4 cSCNScenarioLayer [LINUX-HINT]; at 0 calls dtor 0x100067f0 + delete. Made atomic by sc3perf RES_REFCOUNT scenario_refcount (verify/refaudit/RESULTS.md).',
 ('SIMUI.DLL', '0x100139b6'): 'Shared by several SIMUI classes incl. the RACE-PRONE rank 5 wrapper 0x100A8164. Made atomic by sc3perf RES_REFCOUNT le1_refcount_simui (verify/refaudit/RESULTS.md).',
 ('SIMUI.DLL', '0x10043ba9'): 'RACE-PRONE rank 5 wrapper 0x100A8164 (ctor 0x10043d52): all 9 objects went game -> sim -> game. Made atomic by sc3perf RES_REFCOUNT le1_refcount_simui (verify/refaudit/RESULTS.md).',
}
rows = []  # (module, rva, conf, sub, name, note)
for k, d in B.items():
    m, b = k.split('|')
    role = 'AddRef' if d['role'] == ['AddRef'] else 'Release'
    vts = sorted(set(d['vts']))
    off = '/'.join(d['off'])
    tmpl = [x for x in d['tmpl'] if x != 'inc']
    tmpl = tmpl[0] if tmpl else 'inc'
    if role == 'AddRef':
        mech = f'AddRef `inc [ecx+{off}]` (plain, not atomic)'
    else:
        mech = {'le1': f'Release `if n<=1: vt+S(1) else n--` on [ecx+{off}] (plain)',
                'ecx': f'Release `if n: n--; if !n vt+S(1)` on [ecx+{off}] (plain, ecx form)',
                'esi': f'Release `if n: n--; if !n destroy` on [ecx+{off}] (plain, esi form)'}[tmpl]
    src = ', '.join(d['srcs'])
    tag = TAGS.get((m, b))
    fw = d['srcs'] == [LE1]
    if not tag:
        if not fw: tag = 'vt' + vts[0][-5:]
        elif off == '0x10': tag = 'fwobject'
        elif off == '0x20': tag = 'comdirector' if role == 'AddRef' else 'fwobject20'
        else: tag = 'vt' + vts[0][-5:]
    name = f'sc3_{AB[m]}_{role.lower()}_{tag}'
    hit = d['hit']
    if (m, b) == ('STRTSIM.DLL', '0x1001607d'):
        hit = [['0x1002af90', {'calls': 5156, 'objs': 25, 'xobj': 17, 'maxsw': 3, 'threads': 'main+sim'}]]
    hs = ''
    if hit:
        v, h = max(hit, key=lambda x: x[1]['calls'])
        hs = (f" Census (verify/refaudit): live on vtable {v}, {h['calls']:,} calls, {h['objs']} objs, "
              f"{h['xobj']} on 2+ threads, max {h['maxsw']} switches, {h['threads']}.")
    more = f' +{len(vts) - 6} more' if len(vts) > 6 else ''
    note = f"{TAG} {mech}, vtables {', '.join(vts[:6])}{more} ({src}).{hs}"
    if tag == 'comdirector':
        note += ' Body shared with the per-DLL cRZCOMDllDirector AddRef, whose Release only decrements (benign).'
    conf = 'C3' if hit else 'C2'
    if (m, b) in C4:
        conf = 'C4'; note += ' ' + C4[(m, b)]
    elif (m, b) in FIXED:
        conf = 'C3'; note += ' ' + FIXED[(m, b)]
    rows.append((m, b, conf, RC, name, note))

# SIMCITY sim group refcount: live class 0x10013CF0, reached through adjustor thunks
for b, role in (('0x10010d0d', 'addref'), ('0x10010d14', 'release')):
    rows = [r for r in rows if not (r[0] == 'SIMCITY.DLL' and r[1] == b)]
    mech = '`inc [ecx+4]`' if role == 'addref' else '`if n: n--; if !n vt+0x98(1)` (ecx form)'
    rows.append(('SIMCITY.DLL', b, 'C4', RC, f'sc3_simcity_{role}_simgroup',
        f"{TAG} Sim group base {role} {mech}, plain; reached via adjustor thunks 0x1000e787/0x1000e78f; listed vtables "
        f"0x10013D8C/0x10013E44, live class 0x10013CF0 (census 9.1 M calls, max 31,863 switches, main+sim). "
        f"C4: made atomic by sc3perf SIMGROUP_REFCOUNT; play-after-reload crash 8 of 13 runs before, 0 of 8 after; "
        f"the group was freed while still registered (verify/reload1024/RESULTS.md s5)."))
for b in ('0x1000c3df', '0x1000cab6'):
    rows = [r for r in rows if not (r[0] == 'SIMSERV.DLL' and r[1] == b)]
    rows.append(('SIMSERV.DLL', b, 'C3', '', '', f"{TAG} Census reference point: vtable 0x1001F2C8, 8.7 M calls, 5 objs, max 958 switches, main+sim; already atomic (verify/refaudit/RESULTS.md method 3)."))


def R(m, b, conf, sub, name, note):
    rows.append((m.upper(), b, conf, sub, name, f'{TAG} {note}'))


exec(open(f'{SP}/rows_named.py', encoding='utf-8').read())
NPRIM = len(rows)
exec(open(f'{SP}/rows_secondary.py', encoding='utf-8').read())

# ---- filter against the tracker
out, plan = [], []
for k, (m, b, conf, sub, name, note) in enumerate(rows):
    st = 'primary' if k < NPRIM else 'secondary'
    mod = MODS[m.upper()]
    i = t.lookup(mod, b)
    if i is None:
        plan.append((st, mod, b, 'NO ROW', '', '', '', '', conf, note)); continue
    old = t.as_dict(i)
    oc = old['confidence']
    c = conf if (conf and (oc not in ORD or ORD[conf] > ORD[oc])) else ''
    if conf and oc in ORD and ORD[conf] < ORD[oc]:
        note += f' (this evidence alone supports {conf}; kept {oc})'
    n = name if (name and not old['new_name']) else ''
    s = sub if (sub and n) else ''
    out.append(dict(set=st, module=mod, rva=old['rva'], confidence=c, subsystem=s, new_name=n, notes=note))
    plan.append((st, mod, old['rva'], oc, old['new_name'], c or '=', n or (old['new_name'] and '(kept)'), s, conf, note))
for st, fn in (('primary', 'ladder_batch.tsv'), ('secondary', 'ladder_batch_secondary.tsv'), (None, 'ladder_batch_all.tsv')):
    with io.open(f'{SP}/{fn}', 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, ['module', 'rva', 'confidence', 'subsystem', 'new_name', 'notes'], delimiter='\t',
                           lineterminator='\n', extrasaction='ignore')
        w.writeheader(); w.writerows([o for o in out if st is None or o['set'] == st])
with io.open(f'{SP}/ladder_plan.tsv', 'w', encoding='utf-8', newline='') as fh:
    w = csv.writer(fh, delimiter='\t', lineterminator='\n')
    w.writerow(['set', 'module', 'rva', 'old_conf', 'old_name', 'new_conf', 'new_name', 'subsystem', 'proposed', 'notes'])
    w.writerows(plan)
cnt = collections.Counter((p[0], p[3], p[5]) for p in plan)
print(len(out), 'batch rows')
for k, v in sorted(cnt.items()): print(k, v)
