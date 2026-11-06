@echo off
setlocal
cd /d "%~dp0"
set CL=
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars32.bat" >nul
if not exist out mkdir out
cl /nologo /std:c++20 /O2 /EHsc /MT /LD /DNDEBUG /DNOMINMAX /DWIN32 /D_WINDOWS /D_USRDLL /ISource\vendor\sc3k-gzcom-dll\src\gzcom-dll\include Source\Apache\ApacheDirector.cpp Source\vendor\sc3k-gzcom-dll\src\gzcom-dll\src\cRZBaseString.cpp Source\vendor\sc3k-gzcom-dll\src\gzcom-dll\src\cRZCOMDllDirector.cpp user32.lib /Foout\ /Feout\SC3KUApacheFlyover.dll
