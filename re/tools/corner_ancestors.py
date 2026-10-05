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
function mb(w){var m=Process.enumerateModules();for(var i=0;i<m.length;i++)if(m[i].name.toLowerCase()===w.toLowerCase())return m[i].base;return null;}
function rp(p,o){return p.add(o).readPointer();}
function root(){var gz=mb("GZGraphicD.dll");return rp(rp(rp(gz.add(0x6cdb8),0),0x30),0x38);}
function R(p,o){return [p.add(o).readS32(),p.add(o+4).readS32(),p.add(o+8).readS32(),p.add(o+12).readS32()];}
rpc.exports={f:function(CW,CH){var rr=root();var head=rp(rr,0x34);var n=rp(head,0);var g=0;var btn=null;
 while(!n.isNull()&&!n.equals(head)&&g++<400){var c=rp(n,8);if(!c.isNull()){try{var v=R(c,0x14);
  var wp=v[2]-v[0],hp=v[3]-v[1];if(wp>0&&wp<=200&&hp>0&&hp<=200&&v[2]>=CW-60&&v[3]>=CH-60){btn=c;break;}}catch(e){}}n=rp(n,0);}
 if(!btn)return {ok:false};
 var chain=[]; var cur=btn; var hops=0;
 while(!cur.isNull() && hops++<12){ chain.push({abs:R(cur,0x14),loc:R(cur,0x80),ptr:cur.toString()}); cur=rp(cur,0x3c); }
 return {ok:true, chain:chain};
}};
"""
s=frida.attach(pid);sc=s.create_script(JS);sc.load();res=sc.exports_sync.f(CW,CH)
if not res.get("ok"): print("button not found")
else:
  print(f"client {CW}x{CH}; button->ancestors (click y must be within each abs rect):")
  for i,k in enumerate(res["chain"]):
    print(f"  hop{i} abs {k['abs']} loc {k['loc']}")
