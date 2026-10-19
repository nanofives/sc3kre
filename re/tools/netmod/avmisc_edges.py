"""avmisc_edges.py - avlanes.check of every avmisc avenue edge against avcore 21700, ENGLISH and English-UK (run from re/tools)."""
import sys
sys.path.insert(0,'.')
from netmod import avlanes as A, lanekit as LK
g=LK.Game()
av='netmod/examples/avenue_lanes/avl_21700.lanes.json'
rb=lambda p:'netmod/examples/big_roundabout/%d.lanes.json'%p
hw=lambda p:'netmod/examples/highway_avenue/hwave_%d.lanes.json'%p
cases=[(av,0,rb(20605),0,'W'),(rb(20606),0,av,2,'E'),(rb(20622),0,av,2,'E'),(av,3,rb(20626),0,'S'),
       (rb(20628),0,av,2,'E'),(av,3,rb(20628),0,'S'),(rb(20625),0,av,2,'E'),(av,3,rb(20627),0,'S'),
       (hw(21850),0,av,3,'S'),(av,1,hw(21851),0,'N')]
n=0
for a,sa,b,sb,side in cases:
    for lang in ('ENGLISH','English-UK'):
        p=A.check(a,sa,b,sb,side,g,lang)
        n+=len(p)
        print(a.split('/')[-1][:14],sa,'->',b.split('/')[-1][:14],sb,side,lang,'OK' if not p else p)
print('problems',n)
