import sys,os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from cam import Cam
c=Cam([(718,508)]); c.go(13,100,3,1); c.go(13,100,3,0); c.close()
