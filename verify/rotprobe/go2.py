import sys,os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from cam import Cam
c=Cam([(718,508)])
tag=sys.argv[1]
c.go(13,100,3,0); c.shot('verify/rotprobe/L_%s_view0.png'%tag)
c.go(13,100,4,0); c.shot('verify/rotprobe/L_%s_view0_z4.png'%tag)
c.close()
