import sys,os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from cam import Cam
c=Cam([(718,508)])
Z=3
T={'92':[(12,133),(12,137),(12,147),(16,129)],'90':[(12,99),(12,103),(17,107),(17,111)]}
for t,L in T.items():
    for k,(a,b) in enumerate(L):
        c.go(a+1,b+1,Z,0); c.shot('verify/rotprobe/A_%s_rot%d_view0.png'%(t,k))
for v in range(4):
    for t,L in T.items():
        a,b=L[0]
        c.go(a+1,b+1,Z,v); c.shot('verify/rotprobe/B_%s_rot0_view%d.png'%(t,v))
c.close()
