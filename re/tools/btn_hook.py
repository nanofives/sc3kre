"""Hook the minimize button's dispatch (vt+0x130) and count how many synthetic clicks reach it."""
import subprocess, frida, ctypes, time
from ctypes import wintypes
import sys as _s, pathlib as _p; _s.path.insert(0, str(_p.Path(__file__).resolve().parent)); import sc3io as _sc3io
u=ctypes.WinDLL("user32")
out=subprocess.run(["tasklist","/FI","IMAGENAME eq SC3U.exe","/FO","CSV","/NH"],capture_output=True,text=True).stdout
pid=int(out.split(",")[1].strip('" '))
t=[]
CB=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
def cb(h,l):
    p=wintypes.DWORD();u.GetWindowThreadProcessId(h,ctypes.byref(p));c=ctypes.create_unicode_buffer(64);u.GetClassNameW(h,c,64)
    if p.value==pid and c.value=='Gonzo':t.append(h)
    return True
u.EnumWindows(CB(cb),0);hwnd=t[0];r=wintypes.RECT();u.GetClientRect(hwnd,ctypes.byref(r));CW,CH=r.right,r.bottom
JS=r"""
var HITS=0, POS=null;
function mb(w){var m=Process.enumerateModules();for(var i=0;i<m.length;i++)if(m[i].name.toLowerCase()===w.toLowerCase())return m[i].base;return null;}
function rp(p,o){return p.add(o).readPointer();}
function root(){var gz=mb("GZGraphicD.dll");return rp(rp(rp(gz.add(0x6cdb8),0),0x30),0x38);}
function R(p,o){return [p.add(o).readS32(),p.add(o+4).readS32(),p.add(o+8).readS32(),p.add(o+12).readS32()];}
rpc.exports={
 hook:function(CW,CH){
   var rr=root();var head=rp(rr,0x34);var n=rp(head,0);var g=0;var btn=null;
   while(!n.isNull()&&!n.equals(head)&&g++<400){var c=rp(n,8);if(!c.isNull()){try{var v=R(c,0x14);
    var wp=v[2]-v[0],hp=v[3]-v[1];if(wp>0&&wp<=200&&hp>0&&hp<=200&&v[2]>=CW-60&&v[3]>=CH-60){btn=c;POS=v;break;}}catch(e){}}n=rp(n,0);}
   if(!btn)return {ok:false};
   var vt=rp(btn,0); 
   [0xe4,0x130].forEach(function(slot){ try{var fn=rp(vt,slot); Interceptor.attach(fn,{onEnter:function(a){
     // only count when THIS btn is the 'this'
     if(a[0].equals(btn)) HITS++;
   }});}catch(e){} });
   return {ok:true, pos:POS, btn:btn.toString()};
 },
 stat:function(){var h=HITS;HITS=0;return {hits:h,pos:POS};}
};
"""
s=frida.attach(pid);sc=s.create_script(JS);sc.load()
h=sc.exports_sync.hook(CW,CH)
if not h.get("ok"): print("btn not found"); raise SystemExit
v=h["pos"]; cx,cy=(v[0]+v[2])//2,(v[1]+v[3])//2
print(f"client {CW}x{CH}; button {v}; center ({cx},{cy}); hooked vt+0xe4,+0x130")
pt=wintypes.POINT(cx,cy); u.ClientToScreen(hwnd,ctypes.byref(pt))
_sc3io.raise_without_focus(hwnd); time.sleep(0.3)
for i in range(10):
    sc.exports_sync.stat()
    # was SetCursorPos + mouse_event: posted messages hit the same handler without the cursor
    _sc3io.click(hwnd, cx, cy); time.sleep(0.35)
    st=sc.exports_sync.stat()
    print(f"  click {i+1}: handler entered {st['hits']} time(s); btn now {st['pos']}")
