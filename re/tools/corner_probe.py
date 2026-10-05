"""Find the minimize/corner button (small root-child near bottom-right) and print its visual (+0x14)
and hit (+0x80) rects, to confirm they stay in sync after a resize."""
import subprocess, frida, ctypes
from ctypes import wintypes
u=ctypes.WinDLL("user32")
out=subprocess.run(["tasklist","/FI","IMAGENAME eq SC3U.exe","/FO","CSV","/NH"],capture_output=True,text=True).stdout
pid=int(out.split(",")[1].strip('" '))
t=[]
CB=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
def cb(h,l):
    p=wintypes.DWORD();u.GetWindowThreadProcessId(h,ctypes.byref(p));c=ctypes.create_unicode_buffer(64);u.GetClassNameW(h,c,64)
    if p.value==pid and c.value=='Gonzo':t.append(h)
    return True
u.EnumWindows(CB(cb),0);r=wintypes.RECT();u.GetClientRect(t[0],ctypes.byref(r));CW,CH=r.right,r.bottom
JS=r"""
function modBase(w){var m=Process.enumerateModules();for(var i=0;i<m.length;i++)if(m[i].name.toLowerCase()===w.toLowerCase())return m[i].base;return null;}
function rp(p,o){return p.add(o).readPointer();}
function root(){var gz=modBase("GZGraphicD.dll");return rp(rp(rp(gz.add(0x6cdb8),0),0x30),0x38);}
function R(p,o){return [p.add(o).readS32(),p.add(o+4).readS32(),p.add(o+8).readS32(),p.add(o+12).readS32()];}
rpc.exports={find:function(CW,CH){
  var out=[]; var r=root(); var head=rp(r,0x34); if(head.isNull())return out;
  var n=rp(head,0); var g=0;
  while(!n.isNull()&&!n.equals(head)&&g++<400){ var c=rp(n,8);
    if(!c.isNull()){ try{ var v=R(c,0x14);
      var wpx=v[2]-v[0], hpx=v[3]-v[1];
      // small widget anchored bottom-right of the CURRENT client
      if(wpx>0&&wpx<=200&&hpx>0&&hpx<=200 && v[2]>=CW-60 && v[3]>=CH-60){
        out.push({vis:v, hit:R(c,0x80), ptr:c.toString()});
      } }catch(e){} }
    n=rp(n,0); }
  return out;
}};
"""
s=frida.attach(pid);sc=s.create_script(JS);sc.load()
res=sc.exports_sync.find(CW,CH)
print(f"client {CW}x{CH}; bottom-right small widgets:")
for k in res:
    sync = "IN SYNC" if k['vis'][:2]==k['hit'][:2] else "STALE!!"
    print(f"  vis {k['vis']}  hit {k['hit']}  {sync}")
