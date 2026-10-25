"""Confidence counts of functions.csv, whole file and per module. Usage: py counts.py <functions.csv> [out.json]"""
import csv, io, json, sys, collections

rows = list(csv.DictReader(io.open(sys.argv[1], encoding='utf-8', newline='')))
tot = collections.Counter(r['confidence'] for r in rows)
per = collections.defaultdict(collections.Counter)
for r in rows:
    per[r['module']][r['confidence']] += 1
res = {'total': dict(tot), 'per_module': {m: dict(c) for m, c in sorted(per.items())}}
if len(sys.argv) > 2:
    json.dump(res, open(sys.argv[2], 'w'), indent=1)
print(json.dumps(res['total']))
