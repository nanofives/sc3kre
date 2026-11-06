"""read AUDIO actor 131 state: tracked vehicle +0x88, cur volume +0xb4, mgr zoom +0xd0, ambience vol +0x2c"""
import frida, os
JS = r"""
var a = Process.getModuleByName('AUDIO.DLL').base;
var mgr = a.add(0x26f00).readPointer();
var act = mgr.add(0x190 + 131 * 4).readPointer();
send(JSON.stringify({mgr: mgr.toString(), init: mgr.add(0xc).readU32(), amb: mgr.add(0x2c).readS32(), zoom: mgr.add(0xd0).readS32(),
  view: mgr.add(0x9cc).readS32(), actor: act.toString(), tracked: act.isNull() ? null : act.add(0x88).readPointer().toString(),
  vol: act.isNull() ? null : act.add(0xb4).readS32(), x: act.isNull() ? null : act.add(0x98).readS32(),
  z: act.isNull() ? null : act.add(0xa0).readS32(), agl: act.isNull() ? null : act.add(0xa4).readS32()}));
"""
s = frida.attach(int(os.environ["SC3_PID"])); sc = s.create_script(JS)
sc.on('message', lambda m, d: print(m.get('payload', m))); sc.load(); sc.unload(); s.detach()
