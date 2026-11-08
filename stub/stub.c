/* GameRemix single-file launcher (native, 32-bit, no CRT, Win7+ incl. x86).
   The managed program (built for .NET 3.5) and its .config are resources of this exe. On start they are written to
   %LOCALAPPDATA%\GameRemix\app and started, so the user ships and runs ONE file and the config the CLR needs
   (run on 4.x when present, else on the 3.5 that Windows 7 has built in) is always next to the program. */
#include <windows.h>

#pragma optimize("", off)
#pragma function(memset)
void *memset(void *d, int c, size_t n) { unsigned char *p = (unsigned char *)d; while (n--) *p++ = (unsigned char)c; return d; }   /* no CRT: the compiler emits memset calls */
#pragma optimize("", on)

/* the extracted file counts as current only when its CONTENT equals the resource byte for byte (a new build of the same size must still replace the old code) */
static BOOL SameContent(const WCHAR *p, const void *res, DWORD n) {
    WIN32_FILE_ATTRIBUTE_DATA d;
    HANDLE h; BYTE *buf; DWORD done = 0, got, i; BOOL same = TRUE;
    if (!GetFileAttributesExW(p, GetFileExInfoStandard, &d)) return FALSE;
    if (d.nFileSizeHigh != 0 || d.nFileSizeLow != n) return FALSE;
    h = CreateFileW(p, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) return FALSE;
    buf = (BYTE *)HeapAlloc(GetProcessHeap(), 0, 65536);
    if (!buf) { CloseHandle(h); return FALSE; }
    while (done < n && same) {
        DWORD want = n - done > 65536 ? 65536 : n - done;
        if (!ReadFile(h, buf, want, &got, NULL) || got != want) { same = FALSE; break; }
        for (i = 0; i < got; i++) if (buf[i] != ((const BYTE *)res)[done + i]) { same = FALSE; break; }
        done += got;
    }
    HeapFree(GetProcessHeap(), 0, buf); CloseHandle(h);
    return same;
}
static int UiRu(void) { return (GetUserDefaultUILanguage() & 0x3FF) == 0x19; }   /* LANG_RUSSIAN */
static BOOL Put(int id, const WCHAR *path) {
    HRSRC r = FindResourceW(NULL, MAKEINTRESOURCEW(id), MAKEINTRESOURCEW(10));
    if (!r) return FALSE;
    DWORD n = SizeofResource(NULL, r), w = 0;
    void *p = LockResource(LoadResource(NULL, r));
    if (SameContent(path, p, n)) return TRUE;                 /* already extracted by an earlier run (same bytes) */
    HANDLE h = CreateFileW(path, GENERIC_WRITE, FILE_SHARE_READ, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) return FALSE;              /* e.g. another version of the program is running from there */
    BOOL ok = WriteFile(h, p, n, &w, NULL) && w == n;
    CloseHandle(h);
    return ok;
}
static void MkDirs(WCHAR *p) {
    WCHAR *c;
    for (c = p + 3; *c; c++) if (*c == L'\\') { *c = 0; CreateDirectoryW(p, NULL); *c = L'\\'; }
    CreateDirectoryW(p, NULL);
}
static void AppendNum(WCHAR *s, DWORD v) {
    WCHAR t[12]; int i = 0, l = lstrlenW(s);
    do { t[i++] = (WCHAR)(L'0' + v % 10); v /= 10; } while (v);
    while (i) s[l++] = t[--i];
    s[l] = 0;
}
static void Fail(const WCHAR *m) { MessageBoxW(NULL, m, L"GameRemix - By Lex", MB_OK | MB_ICONERROR); ExitProcess(1); }

void start(void) {
    WCHAR self[MAX_PATH], home[MAX_PATH], dir[MAX_PATH], exe[MAX_PATH], cfg[MAX_PATH], *cmd;
    WCHAR *tail, *s;
    int tl;
    DWORD n, code = 1;
    STARTUPINFOW si; PROCESS_INFORMATION pi;

    GetModuleFileNameW(NULL, self, MAX_PATH);
    lstrcpyW(home, self);
    for (s = home + lstrlenW(home); s > home && *s != L'\\'; s--) ;
    *s = 0;                                                    /* folder the user started us from */
    if (s == home + 2 && home[1] == L':') { s[0] = L'\\'; s[1] = 0; }   /* X:\GameRemix.exe: the folder is "X:\", not the drive-relative "X:" */

    n = GetEnvironmentVariableW(L"LOCALAPPDATA", dir, MAX_PATH - 40);
    if (n == 0 || n >= MAX_PATH - 40) { n = GetTempPathW(MAX_PATH - 40, dir); if (n > 0 && dir[n - 1] == L'\\') dir[n - 1] = 0; }
    lstrcatW(dir, L"\\GameRemix\\app");
    MkDirs(dir);
    lstrcpyW(exe, dir); lstrcatW(exe, L"\\GameRemix.exe");
    { int tries; BOOL ok = FALSE;                              /* after a self-update the previous instance may still be closing: wait up to ~4 s for its file */
      for (tries = 0; tries < 16 && !(ok = Put(101, exe)); tries++) Sleep(250);
      if (ok) goto unpacked; }
    {                                                          /* locked: use a private folder for this run */
        AppendNum(dir, GetTickCount()); MkDirs(dir);
        lstrcpyW(exe, dir); lstrcatW(exe, L"\\GameRemix.exe");
        if (!Put(101, exe)) Fail(UiRu() ? L"Не удаётся распаковать программу (нет доступа на запись в %LOCALAPPDATA%)." : L"Cannot unpack the program (no write access to %LOCALAPPDATA%).");
    }
unpacked:
    lstrcpyW(cfg, exe); lstrcatW(cfg, L".config");
    Put(102, cfg);

    SetEnvironmentVariableW(L"OGF_HOME", home);               /* the program looks for the game next to the file the user ran */
    SetEnvironmentVariableW(L"OGF_STUB", self);

    /* arguments: everything after our own (possibly quoted) program name */
    tail = GetCommandLineW();
    if (*tail == L'"') { tail++; while (*tail && *tail != L'"') tail++; if (*tail) tail++; }
    else while (*tail && *tail != L' ' && *tail != L'\t') tail++;
    tl = lstrlenW(tail);
    cmd = (WCHAR *)HeapAlloc(GetProcessHeap(), 0, (lstrlenW(exe) + tl + 8) * sizeof(WCHAR));   /* any length of arguments */
    if (!cmd) Fail(UiRu() ? L"Не хватает памяти." : L"Out of memory.");
    cmd[0] = L'"'; cmd[1] = 0; lstrcatW(cmd, exe); lstrcatW(cmd, L"\""); lstrcatW(cmd, tail);

    memset(&si, 0, sizeof(si));
    si.cb = sizeof(si);
    if (!CreateProcessW(exe, cmd, NULL, NULL, FALSE, 0, NULL, NULL, &si, &pi)) Fail(UiRu() ? L"Не удаётся запустить программу." : L"Cannot start the program.");
    WaitForSingleObject(pi.hProcess, INFINITE);                /* keeps the exit code for command-line use */
    GetExitCodeProcess(pi.hProcess, &code);
    ExitProcess(code);
}
