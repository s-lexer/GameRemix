/* Minimal DirectDraw host used to test the ddfx fork without the game: ddtest.exe frame.raw W H [seconds]
   frame.raw = W*H RGB565 little endian. Fullscreen-exclusive 16bpp like Divine Divinity's Software renderer (cnc-ddraw makes it a window). */
#include <windows.h>
#include <ddraw.h>
#include <stdio.h>
static LRESULT CALLBACK wp(HWND h, UINT m, WPARAM w, LPARAM l) { if (m == WM_DESTROY) PostQuitMessage(0); return DefWindowProcA(h, m, w, l); }
int main(int argc, char** argv)
{
    int W = atoi(argv[2]), H = atoi(argv[3]), secs = argc > 4 ? atoi(argv[4]) : 20; WNDCLASSA wc = { 0 }; HWND hw; LPDIRECTDRAW dd; LPDIRECTDRAWSURFACE s; DDSURFACEDESC d; FILE* f; unsigned short* raw; DWORD t0; MSG msg; int y;
    wc.lpfnWndProc = wp; wc.hInstance = GetModuleHandleA(NULL); wc.lpszClassName = "ddtest"; wc.hCursor = LoadCursor(NULL, IDC_ARROW); RegisterClassA(&wc);
    hw = CreateWindowA("ddtest", "ddtest", WS_POPUP | WS_VISIBLE, 0, 0, W, H, NULL, NULL, wc.hInstance, NULL);
    if (DirectDrawCreate(NULL, &dd, NULL) != DD_OK) { printf("DirectDrawCreate failed\n"); return 1; }
    IDirectDraw_SetCooperativeLevel(dd, hw, DDSCL_EXCLUSIVE | DDSCL_FULLSCREEN | DDSCL_ALLOWREBOOT);
    if (IDirectDraw_SetDisplayMode(dd, W, H, 16) != DD_OK) { printf("SetDisplayMode failed\n"); return 2; }
    memset(&d, 0, sizeof(d)); d.dwSize = sizeof(d); d.dwFlags = DDSD_CAPS; d.ddsCaps.dwCaps = DDSCAPS_PRIMARYSURFACE;
    if (IDirectDraw_CreateSurface(dd, &d, &s, NULL) != DD_OK) { printf("CreateSurface failed\n"); return 3; }
    raw = (unsigned short*)malloc((size_t)W * H * 2); f = fopen(argv[1], "rb"); fread(raw, 2, (size_t)W * H, f); fclose(f);
    memset(&d, 0, sizeof(d)); d.dwSize = sizeof(d);
    if (IDirectDrawSurface_Lock(s, NULL, &d, DDLOCK_WAIT, NULL) != DD_OK) { printf("Lock failed\n"); return 4; }
    for (y = 0; y < H; y++) memcpy((char*)d.lpSurface + y * d.lPitch, raw + (size_t)y * W, W * 2);
    IDirectDrawSurface_Unlock(s, NULL);
    printf("ready %dx%d pitch %d\n", W, H, (int)d.lPitch); fflush(stdout);
    SetForegroundWindow(hw);
    t0 = GetTickCount();
    while (GetTickCount() - t0 < (DWORD)secs * 1000)
    {
        while (PeekMessage(&msg, NULL, 0, 0, PM_REMOVE)) { TranslateMessage(&msg); DispatchMessage(&msg); }
        memset(&d, 0, sizeof(d)); d.dwSize = sizeof(d);
        if (IDirectDrawSurface_Lock(s, NULL, &d, DDLOCK_WAIT, NULL) == DD_OK) { ((unsigned short*)d.lpSurface)[0] = raw[0]; IDirectDrawSurface_Unlock(s, NULL); }
        Sleep(12);
    }
    return 0;
}
