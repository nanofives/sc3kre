"""dlg_text.py - read-only: print the strings held by every visible text widget in the game's dialogs.

For each visible root child with vtable SIMUI+0xa4d64 (dialog frame), walks its children and, for each one, scans the
first 0x200 bytes for pointers to readable ASCII or UTF-16 strings (>= 3 printable chars). Prints dialog, child class
and the strings. Attaches, reads, detaches; sends no input. Honours SC3_PID like every sc3io tool.

    SC3_PID=<pid> py -3.12 re/tools/dlg_text.py
"""
from __future__ import annotations

import pathlib
import sys

import frida

sys.path.insert(0, r"C:\Users\maria\Desktop\Proyectos\Simcity\re\tools")
import sc3io  # noqa: E402

JS = r"""
var mods=Process.enumerateModules();
function mb(w){for(var i=0;i<mods.length;i++)if(mods[i].name.toLowerCase()===w.toLowerCase())return mods[i].base;return null;}
function cls(vt){for(var i=0;i<mods.length;i++){var m=mods[i];if(vt.compare(m.base)>=0&&vt.compare(m.base.add(m.size))<0)return m.name+"+0x"+vt.sub(m.base).toString(16);}return vt.toString();}
function rp(p,o){return p.add(o).readPointer();}
function kids(w){var out=[];try{var h=rp(w,0x34);if(h.isNull())return out;var n=rp(h,0),g=0;while(!n.isNull()&&!n.equals(h)&&g++<400){var c=rp(n,8);if(!c.isNull())out.push(c);n=rp(n,0);}}catch(e){}return out;}
function strs(o){var out=[];for(var off=0;off<0x200;off+=4){try{var p=rp(o,off);if(p.compare(ptr(0x10000))<0)continue;
  var a=null,u=null;try{a=p.readCString(120);}catch(e){} try{u=p.readUtf16String(120);}catch(e){}
  function ok(s){return s&&s.length>=3&&/^[\x20-\x7e\u00a0-\u00ff\u00bf\u00a1\n\r]+$/.test(s);}
  if(ok(u))out.push("+0x"+off.toString(16)+" W:"+u); else if(ok(a))out.push("+0x"+off.toString(16)+" A:"+a);
  // one level deeper (string objects)
  for(var o2=0;o2<0x10;o2+=4){try{var q=rp(p,o2);if(q.compare(ptr(0x10000))<0)continue;var u2=null,a2=null;
    try{u2=q.readUtf16String(120);}catch(e){} try{a2=q.readCString(120);}catch(e){}
    if(ok(u2))out.push("+0x"+off.toString(16)+"->+0x"+o2.toString(16)+" W:"+u2); else if(ok(a2))out.push("+0x"+off.toString(16)+"->+0x"+o2.toString(16)+" A:"+a2);}catch(e){}}
 }catch(e){}}return out;}
rpc.exports={d:function(){var gz=mb("GZGraphicD.dll"),su=mb("SIMUI.DLL");var win=rp(gz.add(0x6cdb8),0);var sink=rp(win,0x30);var root=rp(sink,0x38);
  var res={modal:sink.add(0x194).readS32(),dlgs:[]};var ks=kids(root);
  for(var i=0;i<ks.length;i++){var c=ks[i];if(!rp(c,0).equals(su.add(0xa4d64)))continue;if(!(c.add(0xa0).readU32()&1))continue;
    var d={p:c.toString(),kids:[]};var kk=kids(c);for(var j=0;j<kk.length;j++){d.kids.push({cls:cls(rp(kk[j],0)),s:strs(kk[j])});}
    res.dlgs.push(d);}
  return res;}};
"""


def main() -> int:
    s = frida.attach(sc3io.game_pid())
    sc = s.create_script(JS)
    sc.load()
    r = sc.exports_sync.d()
    s.detach()
    print("modal depth (sink+0x194):", r["modal"])
    for d in r["dlgs"]:
        print("dialog", d["p"])
        for k in d["kids"]:
            if k["s"]:
                print("  ", k["cls"])
                for t in k["s"]:
                    print("     ", t)
    return 0


if __name__ == "__main__":
    sys.exit(main())
