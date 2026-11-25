import sys,struct,json
sys.path.insert(0,'re/tools')
from occupant_layer import parse, GROUP
src='../../../Cities/Europolis.sc3'
c,s0,s1,cnt,ver,recs=parse(src)
out={}
d=bytearray(c.section(GROUP,1,0xe0faadc7).data)
for t in (0x92,0x90):
    cand=[r for r in recs if r['key'][2]==t and r['rot']==0 and r['sa']==2 and r['sb']==2]
    best=None
    for r in cand:
        near=[q for q in cand if abs(q['a']-r['a'])<=14 and abs(q['b']-r['b'])<=14]
        if len(near)>=4: best=near[:4]; break
    print(hex(t),[(q['a'],q['b']) for q in best])
    for i,q in enumerate(best):
        p=struct.unpack_from('<I',d,q['off'])[0]
        p=(p&0x3fffffff)|(i<<30)
        struct.pack_into('<I',d,q['off'],p)
        out.setdefault(hex(t),[]).append((q['a'],q['b'],i))
c.section(GROUP,1,0xe0faadc7).data=d
c.save('../tree/Cities/RotProbe.sc3')
json.dump(out,open('../rot_targets.json','w'))
