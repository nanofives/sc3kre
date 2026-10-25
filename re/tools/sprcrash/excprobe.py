import os
import sys, os, time, json, ctypes
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "netmod"))
import frida, sc3io, sc3pause, nramp_cam
pid = int(sys.argv[1]); mode = sys.argv[2]; zoom = int(sys.argv[3])
h = sc3io.game_hwnd(pid)
sc3pause.require_running(pid, "excprobe")
js = nramp_cam.JS
if mode == "propagate":
    js = js.replace("'thiscall')", "{abi: 'thiscall', exceptions: 'propagate'})")
js = r"""
var exc = [];
Process.setExceptionHandler(function (d) {
  var m = Process.findModuleByAddress(d.address);
  var bt = [];
  try { bt = Thread.backtrace(d.context, Backtracer.ACCURATE).slice(0, 12).map(function (a) { var mm = Process.findModuleByAddress(a); return mm ? mm.name + '+0x' + a.sub(mm.base).toString(16) : a.toString(); }); } catch (e) {}
  exc.push({type: d.type, addr: m ? m.name + '+0x' + d.address.sub(m.base).toString(16) : d.address.toString(),
            mem: d.memory ? d.memory.operation + ' ' + d.memory.address : '', bt: bt});
  return false;
});
""" + js.replace("take: function () {", "exc: function () { var e = exc; exc = []; return e; },\n  take: function () {")
s = frida.attach(pid); sc = s.create_script(js); sc.load(); api = sc.exports_sync
for btn in ((772, 546), (666, 546)):
    sc3io.click(h, *btn); time.sleep(1.0)
    if api.hascam(): break
print("cam", api.hascam(), "exc so far", api.exc())
st = api.hascam()
api.queue({"k": "zoom", "v": zoom, "f": 1, "x": 128, "z": 128})
ctypes.windll.user32.PostMessageA(h, nramp_cam.WM_CAM, 0, 0)
time.sleep(3)
print("res", json.dumps(api.take()))
print("exc", json.dumps(api.exc(), indent=1))
s.detach()
