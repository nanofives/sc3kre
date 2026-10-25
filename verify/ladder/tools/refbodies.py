import re, csv, collections, sys, json
sys.path.insert(0, 're/scripts')
W = '.'
lists = [('verify/reload1024/plain_refcount_vtables.txt', 'esi'),
         ('verify/reload1024/plain_refcount_vtables_ecx.txt', 'ecx'),
         ('verify/refaudit/le1_refcount_vtables.txt', 'le1')]
vt = {}  # (mod, vtable) -> (addref, off, release, tmpl)
for path, tmpl in lists:
    mod = None
    for line in open(path, encoding='utf-8'):
        m = re.match(r'^(\S+\.(?:DLL|dll)):', line)
        if m: mod = m.group(1).upper(); continue
        m = re.match(r'\s+vtable (0x\w+)\s+AddRef (0x\w+) \(\+(0x\w+)\)\s+Release (0x\w+)', line)
        if m:
            v, a, o, r = (x.lower() for x in m.groups())
            vt[(mod, v)] = (a, o, r, tmpl, path)
hits = {}
for p in ('verify/refaudit/census_merged.tsv', 'verify/refaudit/census_le1_merged.tsv'):
    for r in csv.DictReader(open(p, encoding='utf-8'), delimiter='\t'):
        k = (r['module'].upper(), r['vtable'].lower())
        c = int(r['calls'])
        old = hits.get(k)
        if not old or c > old['calls']:
            hits[k] = dict(calls=c, objs=int(r['objs']), xobj=int(r['xobj']), maxsw=int(r['maxsw']), threads=r['threads'])
bodies = collections.defaultdict(lambda: dict(role=set(), vts=[], hit=[], tmpl=set(), off=set(), srcs=set()))
for (mod, v), (a, o, r, t, path) in vt.items():
    for body, role in ((a, 'AddRef'), (r, 'Release')):
        b = bodies[(mod, body)]
        b['role'].add(role); b['vts'].append(v); b['tmpl'].add(t if role=='Release' else 'inc'); b['off'].add(o); b['srcs'].add(path)
        if (mod, v) in hits and hits[(mod, v)]['calls'] > 0:
            b['hit'].append((v, hits[(mod, v)]))
print(len(vt), 'vtables', len(bodies), 'bodies')
# unlisted census vtables with hits
unl = [(k, h) for k, h in hits.items() if k not in vt and h['calls'] > 0]
print('census vtables not in lists with calls:', len(unl))
for k, h in sorted(unl): print('  ', k, h)
json.dump({f'{m}|{b}': dict(role=sorted(d['role']), vts=d['vts'], hit=[(v, h) for v, h in d['hit']], tmpl=sorted(d['tmpl']), off=sorted(d['off']), srcs=sorted(d['srcs'])) for (m, b), d in bodies.items()}, open(sys.argv[1], 'w'), indent=0)
