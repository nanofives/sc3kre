"""List every window whose rect sits in the bottom bar band but in the MIDDLE x (over the info
fields, where only painted text should be) - these are the misplaced control widgets."""
import subprocess, frida, ctypes
from ctypes import wintypes
u=ctypes.WinDLL("user32")
out=subprocess.run(["tasklist","/FI","IMAGENAME eq SC3U.exe","/FO","CSV","/NH"],capture_output=True,text=True).stdout
pid=int(out.split(",")[1].strip('" '))
# client size
t=[]
CB=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
def cb(h,l):
    p=wintypes.DWORD();u.GetWindowThreadProcessId(h,ctypes.byref(p));c=ctypes.create_unicode_buffer(64);u.GetClassNameW(h,c,64)
    if p.value==pid and c.value=='Gonzo':t.append(h)
    return True
u.EnumWindows(CB(cb),0); r=wintypes.RECT();u.GetClientRect(t[0],ctypes.byref(r)); CW,CH=r.right,r.bottom
JS=r"""
function modBase(w){var m=Process.enumerateModules();for(var i=0;i<m.length;i++)if(m[i].name.toLowerCase()===w.toLowerCase())return m[i].base;return null;}
function rp(p,o){return p.add(o).readPointer();}
function root(){var gz=modBase("GZGraphicD.dll");return rp(rp(rp(gz.add(0x6cdb8),0),0x30),0x38);}
var OUT=[];
function walk(w,depth){
 if(depth>10) return;
 var head; try{head=rp(w,0x34);}catch(e){return;} if(head.isNull())return;
 var n; try{n=rp(head,0);}catch(e){return;} var g=0;
 while(!n.isNull() && !n.equals(head) && g++<400){
   var c; try{c=rp(n,8);}catch(e){break;}
   if(!c.isNull()){
     try{
       var e=[c.add(0x80).readS32(),c.add(0x84).readS32(),c.add(0x88).readS32(),c.add(0x8c).readS32()];
       var vt=rp(c,0); var mods=Process.enumerateModules(); var mod="?",rva=0;
       for(var i=0;i<mods.length;i++){ if(vt.compare(mods[i].base)>=0 && vt.compare(mods[i].base.add(mods[i].size))<0){mod=mods[i].name;rva=vt.sub(mods[i].base).toNumber();break;} }
       OUT.push({rect:e, mod:mod, rva:rva, ptr:c.toString()});
     }catch(e2){}
     walk(c,depth+1);
   }
   n=rp(n,0);
 }
}
rpc.exports={scan:function(){OUT=[];walk(root(),0);return OUT;}};
"""
s=frida.attach(pid);sc=s.create_script(JS);sc.load()
res=sc.exports_sync.scan()
print(f"client {CW}x{CH}; windows in bottom band (y2>{CH-70}) with middle x (120..{CW-200}):")
for k in res:
    x1,y1,x2,y2=k['rect']
    if y2 > CH-70 and x2-x1>0 and x2-x1<200 and x1>120 and x1<CW-200:
        print(f"  {k['mod']}+0x{k['rva']:x}  rect {k['rect']} ({x2-x1}x{y2-y1})  {k['ptr']}")
