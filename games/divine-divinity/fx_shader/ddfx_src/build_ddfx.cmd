@echo off
rem Builds the ddfx fork (MSVC 2022 BuildTools, x86, Release). Output: bin\Release\ddraw.dll
rem (re-generate headers first:  python fx\gen_header.py  and, once, python fx\gen_font.py <DejaVuSansMono.ttf>)
set MSB=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\MSBuild\Current\Bin\MSBuild.exe
"%MSB%" "%~dp0cnc-ddraw.vcxproj" -p:Configuration=Release -p:Platform=Win32 -p:PlatformToolset=v143 -v:m -nologo
