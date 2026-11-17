#!/bin/bash
# usage: ARM=x CITY="..." trace_arm.sh [env K=V...]  all mods unless LIST set
cd /c/Users/maria/Desktop/Proyectos/Simcity
py -3.12 verify/leak1024/rotmem.py "$ARM" --n 0 --keep --wait 150 --city "$CITY" --env "$@" >/dev/null 2>&1
PID=$(cat dev/leak1024/last_pid)
echo "arm $ARM: pid $PID city $CITY env $*"
(cd re/tools && py -3.12 -c "import sc3wait; sc3wait.run_after_load($PID, timeout=90)")
(cd re/tools && SC3_PID=$PID py -3.12 -c "import sc3io,time; h=sc3io.game_hwnd($PID); [(sc3io.click(h,666,546),time.sleep(3)) for _ in range(${ZIN:-0})]")
sleep 5
py -3.12 verify/leak1024/rot_trace.py --pid $PID --n 8
grep -h "SPR_IMGREF" dev/leak1024/inst/sc3perf.log
taskkill //PID $PID //F >/dev/null 2>&1
