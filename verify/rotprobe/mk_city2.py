import sys,struct,json
sys.path.insert(0,'re/tools')
from occupant_layer import parse, GROUP
c,s0,s1,cnt,ver,recs=parse('../tree/Cities/RotProbe.sc3')
tg=json.load(open('../rot_targets.json'))
want={(a,b) for v in tg.values() for a,b,_ in v}
sel=[r for r in recs if (r['a'],r['b']) in want and r['sa']==2]
print(len(sel),[(r['a'],r['b'],r['rot'],hex(r['key'][2])) for r in sel])
body=bytearray(s1[:8])
for r in sel: body+=s1[r['off']:r['off']+r['len']]
c.section(GROUP,1,0xe0faadc7).data=body
c.section(GROUP,0,0x20631788).data=bytearray(s0[:8])+struct.pack('<II',len(sel),ver)
n=c.n
for x in range(n):
    for z in range(n):
        if c.zone_get(x,z): c.zone_set(x,z,0)
c.save('../tree/Cities/RotProbe2.sc3')
