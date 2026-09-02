"""Describe the modal (focus) window that is blocking clicks, so it can be dismissed.

The dispatcher discards clicks outside the focus window `[CONFIRMED @ GZWIND 0x10020818]`, and
posted ESC/ENTER do not clear this one. Clicks INSIDE it are processed, so list its children with
absolute rects and pick the close/OK control.
"""
import json
import subprocess

import frida

JS = r"""
function ri(p,o){return p.add(o).readS32();}
function rp(p,o){return p.add(o).readPointer();}
function rd(p,o){return [ri(p,o),ri(p,o+4),ri(p,o+8),ri(p,o+12)];}
function modBase(w){var m=Process.enumerateModules();for(var i=0;i<m.length;i++)if(m[i].name.toLowerCase()===w.toLowerCase())return m[i].base;return null;}
function sym(a){var m=Process.enumerateModules();for(var i=0;i<m.length;i++)if(a.compare(m[i].base)>=0&&a.compare(m[i].base.add(m[i].size))<0)return m[i].name+"+0x"+a.sub(m[i].base).toString(16);return a.toString();}
function sink(){var gz=modBase("GZGraphicD.dll");return rp(rp(gz.add(0x6cdb8),0),0x30);}
rpc.exports={dlg:function(){
 var s=sink(), f=rp(s,0x30);
 if(f.isNull())return {ok:true,foc:null};
 var out={ok:true,foc:f.toString(),vt:sym(rp(f,0)),ABS:rd(f,0x14),LOCAL:rd(f,0x80),kids:[]};
 function walk(w,d){
  if(d>4)return;
  var head,n; try{head=rp(w,0x34);}catch(e){return;}
  if(head===null||head.isNull())return;
  try{n=rp(head,0);}catch(e){return;}
  var g=0;
  while(!n.isNull()&&!n.equals(head)&&g<80){g++;
   var c=rp(n,8);
   if(!c.isNull()){
    try{ out.kids.push({p:c.toString(),vt:sym(rp(c,0)),ABS:rd(c,0x14),d:d,
                        flags:"0x"+ri(c,0xa0).toString(16)}); }catch(e){}
    walk(c,d+1);
   }
   n=rp(n,0);}
 }
 walk(f,0);
 return out;}};
"""

out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq SC3U.exe", "/FO", "CSV", "/NH"],
                     capture_output=True, text=True).stdout
pid = int(out.split(",")[1].strip('" '))
dev = frida.get_local_device()
s = dev.attach(pid)
sc = s.create_script(JS)
sc.load()
r = sc.exports_sync.dlg()
if not r.get("foc"):
    print("no focus window - clicks are not blocked")
    raise SystemExit(0)
print(f"modal {r['foc']} {r['vt']}")
print(f"  ABS   {r['ABS']}")
print(f"  LOCAL {r['LOCAL']}")
print(f"  children: {len(r['kids'])}")
for k in r["kids"]:
    a = k["ABS"]
    w, h = a[2] - a[0], a[3] - a[1]
    print(f"    {k['p']} d={k['d']} ABS {a} {w}x{h} flags={k['flags']} {k['vt']}")
