/* prints the DirectDraw display modes the wrapper reports: ddenum.exe [W H] -> "FOUND" if W x H is in the list */
#include <windows.h>
#include <ddraw.h>
#include <stdio.h>
static int W, H, found, n;
static HRESULT WINAPI cb(LPDDSURFACEDESC d, LPVOID c) { n++; if ((int)d->dwWidth == W && (int)d->dwHeight == H) found = 1; printf("%lux%lu/%lu ", d->dwWidth, d->dwHeight, d->ddpfPixelFormat.dwRGBBitCount); return DDENUMRET_OK; }
int main(int argc, char** argv)
{
    LPDIRECTDRAW dd; W = argc > 2 ? atoi(argv[1]) : 0; H = argc > 2 ? atoi(argv[2]) : 0;
    if (DirectDrawCreate(NULL, &dd, NULL) != DD_OK) { printf("create failed\n"); return 1; }
    IDirectDraw_EnumDisplayModes(dd, 0, NULL, NULL, cb);
    printf("\n%d modes, %s\n", n, found ? "FOUND" : "not found"); return 0;
}
