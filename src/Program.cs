// DD Fix Tool - Divine Divinity fix pack (WinForms, .NET Framework 4.0+, C# 5, Windows 7+)
// Build: python src\build.py (D:\ARM\GameRemix)
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Windows.Forms;
using Microsoft.Win32;

namespace DDFixTool
{
    // ---------------------------------------------------------------- localisation
    static class L
    {
        public static bool Ru = CultureInfo.CurrentUICulture.TwoLetterISOLanguageName == "ru"; public static bool Forced;
        public static bool Ko = CultureInfo.CurrentUICulture.TwoLetterISOLanguageName == "ko";   // Korean interface: the English text is looked up in src/ko.txt (key = the English string); not found = English
        static readonly Dictionary<string, string[]> S = new Dictionary<string, string[]>();
        static void A(string k, string ru, string en) { S[k] = new string[] { ru, en }; }
        static L()
        {
            A("title", "GameRemix - By Lex", "GameRemix - By Lex");
            A("sub", "ФИКСЫ И ТВИКИ", "FIXES & TWEAKS");
            A("lblGame", "ПАПКА С ИГРОЙ", "GAME FOLDER");
            A("browse", "Обзор", "Browse");
            A("detect", "Найти", "Find");
            A("lblLog", "ЖУРНАЛ", "LOG");
            A("on", "ВКЛ", "ON");
            A("off", "ВЫКЛ", "OFF");
            A("bPlay", "Играть", "Play");
            A("bOpen", "Открыть", "Open");
            A("bRun", "Запуск", "Run");
            A("bRevert", "Откатить", "Revert");
            A("tagRu", "ТОЛЬКО RU", "RU ONLY");
            A("tagAll", "ЛЮБАЯ ВЕРСИЯ", "ANY VERSION");
            A("tagSecret", "СЕКРЕТ", "SECRET");
            A("tagTool", "ПРОГРАММА", "TOOL");

            A("c_full_t", "Озвучка и музыка + закаты", "Voice & music + dusk");
            A("c_full_d", "NPC снова говорят при каждом разговоре (а не один раз), музыка переключается по локациям. Заменяет OsirisDLL.dll и DivDialogSystem.dll, правит div.exe. Включает фикс закатов.",
                          "NPCs speak on every conversation (not just once) and music switches by location. Replaces OsirisDLL.dll and DivDialogSystem.dll and patches div.exe. Includes the dusk fix.");
            A("c_dusk_t", "Плавные закаты и рассветы", "Smooth dusk & dawn");
            A("c_dusk_d", "Вместо резкой смены дня и ночи — плавное затемнение вечером и осветление утром. Правит один байт в div.exe, ничего больше не трогает.",
                          "Smooth fade at dusk and dawn instead of an abrupt day/night switch. Patches one byte in div.exe, nothing else is touched.");
            A("c_bone_t", "Сложность «Lar's Bone»", "\"Lar's Bone\" difficulty");
            A("c_bone_d", "Секретный режим сложности. Включается пустым файлом dat\\bone.000 — карточка создаёт и удаляет его.",
                          "Hidden difficulty mode, enabled by an empty file dat\\bone.000 — this card creates and removes it.");
            A("c_smooth_t", "Плавная работа игры", "Smooth performance");
            A("c_smooth_d", "Запуск на одном ядре CPU и снятие режима совместимости Windows с div.exe (совет из обсуждения Steam): меньше лагов, быстрее загрузки. Создаёт ярлык «Divine Divinity (smooth)» на рабочем столе.",
                            "Single-core launch and Windows compatibility mode cleared from div.exe (Steam community advice): fewer stutters, faster loads. Creates a \"Divine Divinity (smooth)\" desktop shortcut.");
                        A("c_dgvon_t", "Графика dgVoodoo", "dgVoodoo graphics");
            A("c_dgvon_d", "Включает обёртку dgVoodoo (DDraw.dll и D3D*.dll в папке игры): современный вывод картинки на новых Windows. Выключение только переименовывает эти файлы, ничего не удаляет. Вместе с «Плавной работой» создаёт ярлык на рабочем столе — играть через него или кнопкой «Запустить игру».",
                           "Enables the dgVoodoo wrapper (DDraw.dll and D3D*.dll in the game folder): modern rendering on current Windows. Turning it off only renames those files, nothing is deleted. Together with Smooth performance it creates a desktop shortcut — play through it or the Start button.");
            A("lblTools", "ИНСТРУМЕНТЫ", "TOOLS");
            A("bAbout", "О программе", "About");
            A("aboutBody", "Divine Divinity — Fix Pack\r\n\r\nРазработчик: Lex Volkov\r\n5@1221.by / speectra.com", "Divine Divinity — Fix Pack\r\n\r\nDeveloper: Lex Volkov\r\n5@1221.by / speectra.com");
            A("c_smooth_nodgv", "  ⚠ dgVoodoo (DDraw.dll) в папке не найден.", "  ⚠ dgVoodoo (DDraw.dll) not found in the folder.");
            A("c_play_t", "Запустить игру", "Start the game");
            A("c_play_d", "Запускает игру с выбранными режимами (через DD.cmd, если включена «Плавная работа» или dgVoodoo).", "Starts Divine Divinity. Uses DD.cmd when Smooth performance is on.");
            A("c_cfg_t", "Конфигуратор игры", "Game config tool");
            A("c_cfg_d", "Официальный configtool.exe: режим Direct3D, разрешение, сглаживание.", "Official configtool.exe: Direct3D mode, resolution, smoothing.");
            A("c_dgv_t", "Настройки dgVoodoo", "dgVoodoo settings");
            A("c_dgv_d", "dgVoodooCpl.exe — обёртка DirectDraw/Direct3D для современных Windows: масштаб, MSAA, водяной знак.", "dgVoodooCpl.exe — DirectDraw/Direct3D wrapper for modern Windows: scaling, MSAA, watermark.");
            A("c_saves_t", "Папка сохранений", "Saves folder");
            A("c_saves_d", "Открывает savegames в Проводнике — удобно сделать копию перед экспериментами.", "Opens savegames in Explorer — handy for making a copy before experiments.");
            A("c_dir_t", "Папка игры", "Game folder");
            A("c_dir_d", "Открывает папку с игрой в Проводнике. Резервные копии лежат в _DD_FixTool_backup.", "Opens the game folder in Explorer. Backups live in _DD_FixTool_backup.");
            A("c_revert_t", "Откатить всё", "Revert everything");
            A("c_revert_d", "Возвращает оригинальные div.exe и DLL, убирает Lar's Bone и DD.cmd. Игра станет такой, как была до программы.", "Restores the original div.exe and DLLs, removes Lar's Bone and DD.cmd. The game goes back to how it was before this tool.");
            A("c_ext_d", "Дополнительная программа из папки tools. Ей передаётся путь к игре.", "Extra program from the tools folder. It receives the game folder path.");

            A("stNoGame", "Папка с игрой не выбрана — нажмите «Найти» или «Обзор».", "No game folder selected — press Find or Browse.");
            A("stBadExe", "div.exe не поддерживается: нужна версия 1.0.0.62 (19.04.2013, 2 461 696 байт). Исправления недоступны.", "Unsupported div.exe: need version 1.0.0.62 (2013-04-19, 2,461,696 bytes). Fixes are unavailable.");
            A("stOk", "Игра найдена, div.exe v1.0.0.62 — поддерживается.", "Game found, div.exe v1.0.0.62 — supported.");
            A("stPartial", "Файлы изменены вручную (частичное состояние) — выберите вариант, чтобы привести всё в порядок.", "Files were changed manually (partial state) — pick an option to normalise.");
            A("stAdmin", "  ·  от имени администратора", "  ·  running as administrator");
            A("running", "Игра запущена (div.exe). Закройте игру и повторите.", "The game (div.exe) is running. Close it and try again.");
            A("noRu", "Русская локализация (ddrus.*) в этой папке не найдена.\r\nФикс озвучки рассчитан только на русский перевод. Применить всё равно?", "Russian localisation (ddrus.*) not found in this folder.\r\nThe voice fix is intended for the Russian translation only. Apply anyway?");
            A("revertQ", "Откатить все исправления и вернуть оригинальные файлы?", "Revert all fixes and restore the original files?");
            A("needAdmin", "В эту папку нельзя записывать без прав администратора.\r\nПерезапустить программу от имени администратора?", "This folder cannot be written to without administrator rights.\r\nRestart the program as administrator?");
            A("warnTitle", "Внимание", "Warning");
            A("errTitle", "Ошибка", "Error");
            A("applied", "Применено: ", "Applied: ");
            A("reverted", "Откат: ", "Reverted: ");
            A("noBackup", "нет резервной копии, файл оставлен как есть: ", "no backup, file left as is: ");
            A("backup", "Резервная копия: ", "Backup: ");
            A("detected", "Найдена игра: ", "Game found: ");
            A("notDetected", "Игра автоматически не найдена — укажите папку вручную.", "Game not found automatically — please choose the folder.");
            A("choose", "Выберите папку с игрой Divine Divinity (где лежит div.exe)", "Select the Divine Divinity folder (containing div.exe)");
            A("notFoundExe", "В выбранной папке нет div.exe.", "div.exe not found in the selected folder.");
        }
        public static string T(string k) { string[] v; return S.TryGetValue(k, out v) ? (Ru ? v[0] : Kor(v[1])) : k; }
        static Dictionary<string, string> koTab; static List<string> koPre;
        public static string Kor(string en) { return Ko ? KoText(en) : en; }
        public static string KoText(string en)
        {
            if (en == null || en.Length == 0) return en; if (koTab == null) KoRead(); string k; if (koTab.TryGetValue(en, out k)) return k;
            foreach (string p in koPre) if (en.Length > p.Length && en.StartsWith(p, StringComparison.Ordinal)) return koTab[p] + en.Substring(p.Length);   // "Label: " + value
            return en;
        }
        static void KoRead()
        {
            Dictionary<string, string> t = new Dictionary<string, string>(StringComparer.Ordinal); List<string> pre = new List<string>();
            try
            {
                using (Stream s = Assembly.GetExecutingAssembly().GetManifestResourceStream("ko_ui")) using (StreamReader r = new StreamReader(s, Encoding.UTF8))
                {
                    string ln; while ((ln = r.ReadLine()) != null)
                    {
                        int e = ln.IndexOf('\t'); if (e <= 0) continue; string en = Unesc(ln.Substring(0, e)), ko = Unesc(ln.Substring(e + 1)); if (ko.Length == 0) continue; t[en] = ko;
                        if (en.EndsWith(": ") || en.EndsWith(" — ") || en.EndsWith("… ")) pre.Add(en);
                    }
                }
            }
            catch (Exception) { }
            pre.Sort(delegate(string a, string b) { return b.Length.CompareTo(a.Length); }); koTab = t; koPre = pre;
        }
        static string Unesc(string s)
        {
            if (s.IndexOf('\\') < 0) return s; StringBuilder b = new StringBuilder();
            for (int i = 0; i < s.Length; i++) { char c = s[i]; if (c == '\\' && i + 1 < s.Length) { char n = s[++i]; b.Append(n == 'n' ? '\n' : n == 't' ? '\t' : n == 'r' ? '\r' : n); } else b.Append(c); }
            return b.ToString();
        }
    }

    // ---------------------------------------------------------------- core logic (no UI)
    enum FixMode { None, Dusk, Full, Partial }

    partial class Core
    {
        public const long ExeSize = 2461696;
        const long VoiceOff = 0x71ACC; static readonly byte[] VoiceOrig = { 0xC7, 0x46, 0x14, 0, 0, 0, 0 }; static readonly byte[] VoicePat = { 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90 };
        const long DuskOff = 0x196B73; const byte DuskOrig = 0x74, DuskPat = 0xEB;
        const string LayersKey = @"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers";
        public const string CompatFlags = "~ RUNASADMIN DISABLEDXMAXIMIZEDWINDOWEDMODE";
        public string Dir, RawDir; public Action<string> Log = delegate { };
        public Action<string> Warn = delegate { };   // things the user must be told about after an action (the UI shows them; the CLI writes them to the log)

        public Core(string dir) { RawDir = dir ?? ""; Dir = NormPath(RawDir); if (HasGame && !App.ReadOnly) { try { MigrateLegacy(); } catch { } } }

        // one canonical spelling of a folder: full path, backslashes, long (not 8.3) names, no trailing slash (a drive root keeps its "\")
        [System.Runtime.InteropServices.DllImport("kernel32.dll", CharSet = System.Runtime.InteropServices.CharSet.Unicode)] static extern int GetLongPathName(string s, StringBuilder b, int n);
        public static string NormPath(string d)
        {
            if (string.IsNullOrEmpty(d)) return ""; d = d.Trim().Trim('"'); if (d.Length == 0) return "";
            try { d = Path.GetFullPath(d.Replace('/', '\\')); } catch { return d; }
            try { if (Directory.Exists(d)) { StringBuilder sb = new StringBuilder(1024); int n = GetLongPathName(d, sb, sb.Capacity); if (n > 0 && n < sb.Capacity) d = sb.ToString(); } } catch { }
            if (d.Length > 3) d = d.TrimEnd('\\');
            return d;
        }

        // ---- per-game data lives in the user's profile (%APPDATA%\GameRemix\games\dd-<hash of the normalised game path>), nothing of ours is left next to the game's exe.
        // Older versions hashed the path as typed (slashes, case, trailing "\"): if the new key has no data yet but an old key does, that folder is simply reused.
        string gameData;
        public string GameData { get { if (gameData == null) gameData = ResolveGameData(); return gameData; } }
        string ResolveGameData()
        {
            string root = Path.Combine(App.DataDir, "games"), nt = Path.Combine(root, "dd-" + PathTag(Dir));
            if (Dir.Length == 0 || (Directory.Exists(nt) && Directory.GetFileSystemEntries(nt).Length > 0)) return nt;
            foreach (string cand in new string[] { RawDir, RawDir.Replace('/', '\\'), RawDir.Replace('\\', '/'), Dir, Dir.Replace('\\', '/'), Dir + "\\", Dir.Replace('\\', '/') + "/" })
            {
                string p = Path.Combine(root, "dd-" + OldTag(cand));
                if (!string.Equals(p, nt, StringComparison.OrdinalIgnoreCase) && Directory.Exists(p) && Directory.GetFileSystemEntries(p).Length > 0) return p;
            }
            return nt;
        }
        static string Tag8(string s) { using (SHA1 h = SHA1.Create()) return BitConverter.ToString(h.ComputeHash(Encoding.UTF8.GetBytes(s))).Replace("-", "").Substring(0, 8).ToLowerInvariant(); }
        static string PathTag(string d) { return Tag8(NormPath(d).TrimEnd('\\').ToLowerInvariant()); }
        static string OldTag(string d) { return Tag8((d ?? "").TrimEnd('\\').ToLowerInvariant()); }   // how versions up to 1.0.9 keyed the folder
        public string CmdFile { get { return Path.Combine(GameData, "Play.cmd"); } }
        string LegacyBak { get { return P("_DD_FixTool_backup"); } }
        void MigrateLegacy()   // backups and DD.cmd used to be written into the game folder: move them into the profile
        {
            if (Directory.Exists(LegacyBak))
            {
                // the old folder is the only copy of the original files until EVERY file of it is in BakDir with the same size: top up what is missing (never overwrite), check, and only then delete
                try { MergeMissing(LegacyBak, BakDir); } catch (Exception ex) { Log("backups: copy to " + BakDir + " not finished (" + ex.Message + "), the old folder stays"); }
                if (AllPresent(LegacyBak, BakDir)) { Log("moved backups to " + BakDir); try { Directory.Delete(LegacyBak, true); } catch { } }
            }
            string old = P("DD.cmd"); if (File.Exists(old)) { try { File.Delete(old); if (!File.Exists(CmdFile)) WriteCmd(); if (File.Exists(LnkPath)) MakeShortcut(); } catch { } }   // the desktop shortcut pointed at the old DD.cmd
        }

        static void MergeMissing(string src, string dst)
        {
            Directory.CreateDirectory(dst);
            foreach (string f in Directory.GetFiles(src)) { string t = Path.Combine(dst, Path.GetFileName(f)); if (!File.Exists(t)) File.Copy(f, t, false); }
            foreach (string d in Directory.GetDirectories(src)) MergeMissing(d, Path.Combine(dst, Path.GetFileName(d)));
        }
        // every file of src exists in dst with the same size (empty folders are not data)
        static bool AllPresent(string src, string dst)
        {
            try
            {
                foreach (string f in Directory.GetFiles(src, "*", SearchOption.AllDirectories))
                {
                    string t = Path.Combine(dst, f.Substring(src.Length).TrimStart('\\'));
                    if (!File.Exists(t) || new FileInfo(t).Length != new FileInfo(f).Length) return false;
                }
                return true;
            }
            catch { return false; }
        }

        // ---- which game version is installed: only v1.0.0.62 (div.exe, 2 461 696 bytes) is known to carry our patch points
        public string ExeFileVersion { get { try { return (System.Diagnostics.FileVersionInfo.GetVersionInfo(Exe).FileVersion ?? "").Replace(", ", ".").Trim(); } catch { return ""; } } }
        public long ExeBytes { get { return HasGame ? new FileInfo(Exe).Length : 0; } }
        public string ExeVersionText { get { string v = ExeFileVersion; return (v.Length > 0 ? v : "?") + " (" + ExeBytes.ToString("N0") + " B)"; } }
        public string P(string rel) { return Path.Combine(Dir, rel); }
        public string Exe { get { return P("div.exe"); } }
        public string BakDir { get { return Path.Combine(GameData, "backup"); } }
        public bool HasGame { get { return Dir != null && Dir.Length > 0 && File.Exists(Exe); } }

        static bool Eq(byte[] a, byte[] b) { if (a.Length != b.Length) return false; for (int i = 0; i < a.Length; i++) if (a[i] != b[i]) return false; return true; }
        static byte[] ReadAt(string f, long off, int n) { using (FileStream fs = new FileStream(f, FileMode.Open, FileAccess.Read, FileShare.ReadWrite)) { fs.Position = off; byte[] b = new byte[n]; fs.Read(b, 0, n); return b; } }


        public bool ExeSupported
        {
            get
            {
                if (!HasGame || GfxDef.Dd == null) return false;
                if (!BytePatch.ExeLenOk(new FileInfo(Exe).Length)) return false;   // another build of the game (+ the frame / an older interpolation tail are ours)
                return OrigExe(false) != null;   // every change rebuilds the exe from the verified original (src/Install.cs): an exe with unknown bytes is fine as long as there is one
            }
        }
        public bool VoicePatched { get { return Eq(ReadAt(Exe, VoiceOff, 7), VoicePat); } }
        public bool DuskPatched { get { return ReadAt(Exe, DuskOff, 1)[0] == DuskPat; } }

        public static byte[] ResBytes(string name) { return Res(name); }
        static byte[] Res(string name)
        {
            using (Stream s = Assembly.GetExecutingAssembly().GetManifestResourceStream(name))
            using (MemoryStream ms = new MemoryStream()) { byte[] buf = new byte[65536]; int n; while ((n = s.Read(buf, 0, buf.Length)) > 0) ms.Write(buf, 0, n); return ms.ToArray(); }
        }
        static string Hash(byte[] b) { using (SHA1 h = SHA1.Create()) return BitConverter.ToString(h.ComputeHash(b)); }
        bool SameAsRes(string file, string res) { string f = P(file); return File.Exists(f) && Hash(File.ReadAllBytes(f)) == Hash(Res(res)); }
        bool OurVoiceFile(string file) { return SameAsRes(file, file) || EmbOurs("voice", file); }   // our DLL of this version or one an older version wrote (sha in install.txt)
        public bool DllsFull { get { return SameAsRes("OsirisDLL.dll", "OsirisDLL.dll") && SameAsRes("DivDialogSystem.dll", "DivDialogSystem.dll"); } }

        public FixMode Mode
        {
            get
            {
                if (!ExeSupported) return FixMode.Partial;
                bool v = VoicePatched, d = DuskPatched, dl = DllsFull;
                if (v && d && dl) return FixMode.Full;
                if (!v && d) return FixMode.Dusk;
                if (!v && !d) return FixMode.None;
                return FixMode.Partial;
            }
        }

        static void KeepPrev(string dst) { string pv = dst + ".prev"; try { if (File.Exists(pv)) File.Delete(pv); File.Move(dst, pv); } catch { File.Delete(dst); } }   // an "original" that turns out not to be one (no-CD exe, foreign patch) is not thrown away
        void Backup(string file)
        {
            string src = P(file); if (!File.Exists(src)) return;
            if (file == "div.exe") { OrigExe(true); return; }   // only ever the verified original 1.0.0.62 (src/Install.cs), never "whatever the exe is now"
            Directory.CreateDirectory(BakDir);
            string dst = Path.Combine(BakDir, file + ".orig");
            bool ours = OurVoiceFile(file);   // the current fix OR an older copy of ours (journal): never stored as the "original"
            if (File.Exists(dst) && !ours && Hash(File.ReadAllBytes(dst)) != Hash(File.ReadAllBytes(src))) { KeepPrev(dst); Log("game DLL changed since the last backup (reinstall?): backup refreshed: " + file); }   // the game's own file differs from the stored original
            if (File.Exists(dst)) return;
            if (ours) { Log("backup skipped (already our DLL): " + file); return; }
            File.Copy(src, dst);
            Log(L.T("backup") + dst);
        }
        bool Restore(string file)
        {
            string bak = Path.Combine(BakDir, file + ".orig");
            if (File.Exists(bak)) { File.Copy(bak, P(file), true); Log(L.T("reverted") + file); return true; }
            Log(L.T("noBackup") + file); return false;
        }
        // put the game's own voice DLLs back (only the ones that are ours); without a backup say so instead of pretending
        void RestoreOurDlls()
        {
            List<string> lost = new List<string>();
            foreach (string f in new string[] { "OsirisDLL.dll", "DivDialogSystem.dll" }) if (OurVoiceFile(f) && !Restore(f) && f != "OsirisDLL.dll") lost.Add(f);   // Steam ships our OsirisDLL as stock (no backup was ever made): not a loss
            JNote("voice", false);
            if (lost.Count > 0) Warn(L.Ru ? "Нет резервной копии оригинальных DLL озвучки (" + string.Join(", ", lost.ToArray()) + "): наши файлы остались в папке игры. Верните оригиналы через «Проверить целостность файлов» (Steam) или переустановку."
                                          : "There is no backup of the original voice DLLs (" + string.Join(", ", lost.ToArray()) + "): our files stay in the game folder. Restore the originals with \"Verify integrity of game files\" (Steam) or a reinstall.");
        }
        public bool OurDllAny { get { return HasGame && (SameAsRes("OsirisDLL.dll", "OsirisDLL.dll") || SameAsRes("DivDialogSystem.dll", "DivDialogSystem.dll")); } }
        public bool VoiceMixed { get { if (!HasGame) return false; if (!ExeSupported) return OurDllAny; return VoicePatched != DllsFull && (VoicePatched || OurDllAny); } }
        void PutVoiceDlls() { Backup("OsirisDLL.dll"); Backup("DivDialogSystem.dll"); File.WriteAllBytes(P("OsirisDLL.dll"), Res("OsirisDLL.dll")); File.WriteAllBytes(P("DivDialogSystem.dll"), Res("DivDialogSystem.dll")); JNote("voice", false); }
        static readonly string[] VoiceDusk = { "voice", "dusk" };

        public void SetMode(FixMode m)
        {
            if (!ExeSupported) throw new InvalidOperationException(L.T("stBadExe"));
            if (m == FixMode.Full) { PutVoiceDlls(); ExeChange(VoiceDusk, null, false); Log(L.T("applied") + "voice+music+dusk"); }
            else if (m == FixMode.Dusk) { RestoreOurDlls(); ExeChange(new string[] { "dusk" }, new string[] { "voice" }, false); Log(L.T("applied") + "dusk"); }
            else if (m == FixMode.None) { RestoreOurDlls(); ExeChange(null, VoiceDusk, false); Log(L.T("reverted") + "div.exe"); }
        }

        // ---- independent switches: voice+music (DLLs + div.exe) and dusk/dawn (one byte of div.exe)
        public bool VoiceOn { get { return ExeSupported && VoicePatched && DllsFull; } }
        // the game has voiced dialogues at all (localizations\<lang>\voice.cmp; the Russian edition keeps them in localizations\german). The English version has none, so the voice fix has nothing to fix there.
        public bool VoiceUseful { get { try { return HasGame && Directory.Exists(P("localizations")) && Directory.GetFiles(P("localizations"), "voice.cmp", SearchOption.AllDirectories).Length > 0; } catch { return false; } } }
        public bool DuskOn { get { return ExeSupported && DuskPatched; } }
        public void SetVoice(bool on)
        {
            if (!on && HasGame && !ExeSupported) { RestoreOurDlls(); Log(L.T("reverted") + "voice+music (DLLs only: unsupported div.exe)"); return; }   // revert must work on any build: take our DLLs out, never touch an unknown exe
            if (!ExeSupported) throw new InvalidOperationException(L.T("stBadExe"));
            if (on) { PutVoiceDlls(); ExeChange(new string[] { "voice" }, null, false); Log(L.T("applied") + "voice+music"); }
            else { RestoreOurDlls(); ExeChange(null, new string[] { "voice" }, false); Log(L.T("reverted") + "voice+music"); }
        }
        public void SetDusk(bool on)
        {
            if (!on && HasGame && !ExeSupported) return;   // nothing of ours can be in an unsupported exe
            if (!ExeSupported) throw new InvalidOperationException(L.T("stBadExe"));
            if (on) ExeChange(new string[] { "dusk" }, null, false); else ExeChange(null, new string[] { "dusk" }, false); Log((on ? L.T("applied") : L.T("reverted")) + "dusk");
        }

        // ---- bone
        public bool Bone { get { return File.Exists(P(@"dat\bone.000")); } }
        public void SetBone(bool on)
        {
            string f = P(@"dat\bone.000");
            if (on) { Directory.CreateDirectory(P("dat")); if (!File.Exists(f)) File.Create(f).Close(); Log(L.T("applied") + @"dat\bone.000"); }
            else if (File.Exists(f)) { File.Delete(f); Log(L.T("reverted") + @"dat\bone.000"); }
        }

        // ---- smooth launch (affinity + compat flags), dgVoodoo switch, desktop shortcut
        string StateFile { get { return Path.Combine(BakDir, "state.txt"); } }
        string DgvMark { get { return Path.Combine(BakDir, "dgv.on"); } }
        static readonly string[] DgvSwitch = { "DDraw.dll", "D3DImm.dll", "D3D8.dll", "D3D9.dll" };
        static readonly string[] DgvOwn = { "DDraw.dll", "D3DImm.dll", "dgVoodooCpl.exe", "dgVoodoo.conf" };   // bundled copy (embedded resources dgv_*)
        string DgvInst { get { return Path.Combine(BakDir, "dgv.inst"); } }
        public bool Launcher   // smooth: compat flags set by this tool
        {
            get { using (RegistryKey k = Registry.CurrentUser.OpenSubKey(LayersKey)) { object v = k == null ? null : k.GetValue(Exe); return v != null && v.ToString() == CompatFlags; } }
        }
        public bool DgvAvail { get { return HasGame; } }
        public bool Dgv { get { return File.Exists(P("DDraw.dll")) && !Cnc; } }   // cnc-ddraw is also a ddraw.dll
        // ---- desktop shortcut, bound to ONE install: it points at this install's Play.cmd, and never overwrites a shortcut that belongs to another install
        static string DesktopDir { get { string o = Environment.GetEnvironmentVariable("OGF_DESKTOP"); return !string.IsNullOrEmpty(o) ? o : Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory); } }
        const string LnkName = "Divine Divinity - with fixes";   // English for everyone (owner 07.11.2026); the Russian-named shortcut of 1.0.9..1.0.22 is taken out as an old one
        string OldLnkPath { get { return Path.Combine(DesktopDir, "Divine Divinity (smooth).lnk"); } }
        string RuLnkPath { get { return Path.Combine(DesktopDir, "Divine Divinity — с фиксами.lnk"); } }
        static string LnkTarget(string lnk)
        {
            try
            {
                Type t = Type.GetTypeFromProgID("WScript.Shell"); object sh = Activator.CreateInstance(t);
                object l = t.InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, sh, new object[] { lnk });
                return (string)l.GetType().InvokeMember("TargetPath", BindingFlags.GetProperty, null, l, null);
            }
            catch { return null; }
        }
        // Play.cmd of this install as the pre-GameRemix versions wrote it (%APPDATA%\OldGameFixer\games\dd-x\Play.cmd): shortcuts made then still point there until RepairShortcut re-points them
        string LegacyCmdFile { get { string lg = Migrate.LegacyData; string nw = App.DataDir; if (lg == null || !CmdFile.StartsWith(nw, StringComparison.OrdinalIgnoreCase)) return null; return lg.TrimEnd('\\') + CmdFile.Substring(nw.TrimEnd('\\').Length); } }
        bool LnkIsMine(string lnk) { string t = LnkTarget(lnk); string lc = LegacyCmdFile; return t != null && (string.Equals(t, CmdFile, StringComparison.OrdinalIgnoreCase) || string.Equals(t, P("DD.cmd"), StringComparison.OrdinalIgnoreCase) || (lc != null && (string.Equals(t, lc, StringComparison.OrdinalIgnoreCase) || string.Equals(t, lc.Replace(Migrate.OldName, Migrate.OldName + ".migrated"), StringComparison.OrdinalIgnoreCase)))); }
        // after the move of the data folder a desktop shortcut of ours still has the old target: point it at the new Play.cmd (no duplicate, same name)
        public bool RepairShortcut()
        {
            try
            {
                if (!HasGame || !File.Exists(CmdFile)) return false;
                foreach (string l in new string[] { LnkPath, OldLnkPath, RuLnkPath })
                {
                    if (!File.Exists(l)) continue; string t = LnkTarget(l);
                    if (t != null && !string.Equals(t, CmdFile, StringComparison.OrdinalIgnoreCase) && LnkIsMine(l) && !string.Equals(t, P("DD.cmd"), StringComparison.OrdinalIgnoreCase)) { MakeShortcut(); Log("shortcut re-pointed to " + CmdFile); return true; }
                }
            }
            catch { }
            return false;
        }   // DD.cmd: the pre-1.0.9 launcher inside the game folder
        string LnkPath
        {
            get
            {
                string plain = Path.Combine(DesktopDir, LnkName + ".lnk");
                if (!File.Exists(plain) || LnkIsMine(plain)) return plain;
                string t = LnkTarget(plain);
                bool otherAlive = t != null && t.Length > 0 && File.Exists(t);   // belongs to another existing install: keep it, ours gets its own name
                return otherAlive ? Path.Combine(DesktopDir, LnkName + " (" + PathTag(Dir) + ").lnk") : plain;
            }
        }
        public bool ShortcutExists { get { if (!HasGame) return false; string l = LnkPath; if (File.Exists(l) && LnkIsMine(l)) return true; return (File.Exists(OldLnkPath) && LnkIsMine(OldLnkPath)) || (File.Exists(RuLnkPath) && LnkIsMine(RuLnkPath)); } }
        void MakeShortcut()
        {
            string lnkp = LnkPath;
            try
            {
                Type t = Type.GetTypeFromProgID("WScript.Shell"); object sh = Activator.CreateInstance(t);
                object lnk = t.InvokeMember("CreateShortcut", System.Reflection.BindingFlags.InvokeMethod, null, sh, new object[] { lnkp });
                Type lt = lnk.GetType();
                Action<string, object> set = delegate(string n, object v) { lt.InvokeMember(n, System.Reflection.BindingFlags.SetProperty, null, lnk, new object[] { v }); };
                set("TargetPath", CmdFile); set("WorkingDirectory", Dir); set("IconLocation", P("div.exe") + ",0"); set("WindowStyle", 7);
                set("Description", "Divine Divinity + fixes");
                lt.InvokeMember("Save", System.Reflection.BindingFlags.InvokeMethod, null, lnk, null);
                Log(L.T("applied") + lnkp);
            }
            catch (Exception e) { Log("shortcut: " + e.Message); throw new IOException((U.R("Не удалось создать ярлык: ", "Could not create the shortcut: ")) + e.Message); }
        }
        // Play.cmd starts the game the way the enabled fixes need (single core when "smooth" is on); the Play button and the shortcut both use it.
        // Written in the console's OEM code page so cmd reads Cyrillic folders right; if the path does not fit that code page, UTF-8 without BOM + chcp 65001.
        // '%' is doubled (cmd would expand it), the folder is always full and quoted, a UNC folder goes through pushd (cd cannot enter it).
        [System.Runtime.InteropServices.DllImport("kernel32.dll")] static extern uint GetOEMCP();
        public string CmdText(bool utf8)
        {
            string d = Dir.Replace("%", "%%");
            string cd = Dir.StartsWith(@"\\") ? "pushd \"" + d + "\"" : "cd /d \"" + d + "\"";
            return "@echo off\r\n" + (utf8 ? "chcp 65001 >nul\r\n" : "") + cd + "\r\nstart \"\" " + (Launcher && !Cnc ? "/affinity 2 " : "")   /* with our cnc-ddraw build the single core is set by the wrapper itself (singlecpu in ddraw.ini) */ + "\"div.exe\"\r\n";
        }
        public string WriteCmd()
        {
            Directory.CreateDirectory(GameData);
            byte[] bytes;
            try { Encoding oem = Encoding.GetEncoding((int)GetOEMCP()); string t = CmdText(false); bytes = oem.GetString(oem.GetBytes(t)) == t ? oem.GetBytes(t) : null; if (bytes == null) throw new ArgumentException(); }
            catch (Exception) { bytes = new UTF8Encoding(false).GetBytes(CmdText(true)); }
            File.WriteAllBytes(CmdFile, bytes);
            return CmdFile;
        }
        public void CreateShortcut()
        {
            WriteCmd();
            try { if (File.Exists(OldLnkPath) && LnkIsMine(OldLnkPath)) File.Delete(OldLnkPath); } catch { } try { if (File.Exists(RuLnkPath) && LnkIsMine(RuLnkPath)) File.Delete(RuLnkPath); } catch { }
            MakeShortcut();
        }
        public void RemoveShortcut()
        {
            if (File.Exists(CmdFile)) File.Delete(CmdFile);
            try { if (File.Exists(P("DD.cmd"))) File.Delete(P("DD.cmd")); } catch { }
            try { string l = LnkPath; if (File.Exists(l) && LnkIsMine(l)) File.Delete(l); } catch { }
            try { if (File.Exists(OldLnkPath) && LnkIsMine(OldLnkPath)) File.Delete(OldLnkPath); } catch { } try { if (File.Exists(RuLnkPath) && LnkIsMine(RuLnkPath)) File.Delete(RuLnkPath); } catch { }
        }
        // keep Play.cmd in step with the switches (never creates it by itself)
        void Sync() { if (File.Exists(CmdFile)) WriteCmd(); }

        // ---- dgVoodoo
        string DgvRen { get { return Path.Combine(BakDir, "dgv.ren"); } }              // native files of the user that we only renamed to *.dgvoff
        string DgvConfBak { get { return Path.Combine(BakDir, "dgVoodoo.conf.user"); } } // the user's own dgVoodoo.conf as it was before our first edit
        bool InstHas(string f) { return File.Exists(DgvInst) && Array.IndexOf(File.ReadAllLines(DgvInst), f) >= 0; }
        // dgVoodoo lists only its stock modes to the game; a config.div size outside the list (2048x1152 from 125% scale, 3840x2160...) makes the game quit silently.
        public void DgvEnsureResolution()
        {
            string cf = P("dgVoodoo.conf"), cd = P("config.div"); if (!File.Exists(cf) || !File.Exists(cd)) return;
            string t = File.ReadAllText(cd, System.Text.Encoding.Default);
            System.Text.RegularExpressions.Match w = System.Text.RegularExpressions.Regex.Match(t, @"(?m)^width\s+(\d+)"), h = System.Text.RegularExpressions.Regex.Match(t, @"(?m)^height\s+(\d+)");
            if (!w.Success || !h.Success) return;
            string want = w.Groups[1].Value + "x" + h.Groups[1].Value;
            if (IniEdit.Get(cf, "DirectXExt", "ExtraEnumeratedResolutions", "").Trim() == want) return;
            BackupDgvConf(); IniEdit.Set(cf, "DirectXExt", "ExtraEnumeratedResolutions", want);
        }
        // before the FIRST edit of a dgVoodoo.conf that is not ours: keep a copy, "Revert all" puts it back
        public void BackupDgvConf()
        {
            string cf = P("dgVoodoo.conf"); if (!File.Exists(cf) || File.Exists(DgvConfBak) || InstHas("dgVoodoo.conf")) return;
            Directory.CreateDirectory(BakDir); File.Copy(cf, DgvConfBak); Log(L.T("backup") + DgvConfBak);
        }
        // *.dgvoff -> back under their own names (only renames; installs nothing)
        void DgvRestoreRenamed()
        {
            foreach (string f in DgvSwitch) { string a = P(f); if (!File.Exists(a) && File.Exists(a + ".dgvoff")) File.Move(a + ".dgvoff", a); }
            if (File.Exists(DgvRen)) File.Delete(DgvRen);   // everything we renamed is back in place
        }
        // undo the INSTALL part of a failed multi-step action: remove the files listed in dgv.inst that were not listed before, give the renamed ones back
        public void DgvUndoSince(string[] inst0, bool wasOn)
        {
            if (File.Exists(DgvInst))
            {
                List<string> keep = new List<string>(inst0 ?? new string[0]);
                foreach (string f in File.ReadAllLines(DgvInst)) { string n = f.Trim(); if (n.Length == 0 || keep.Contains(n) || Path.GetFileName(n) != n || Array.IndexOf(DgvOwn, n) < 0) continue; try { File.Delete(P(n)); File.Delete(P(n) + ".dgvoff"); } catch { } }
                if (keep.Count == 0) { File.Delete(DgvInst); JDrop("dgv"); } else { File.WriteAllLines(DgvInst, keep.ToArray()); JNote("dgv", true); }
            }
            if (wasOn) DgvRestoreRenamed();
        }
        public void SetDgv(bool on, bool mark)
        {
            if (on && Cnc) SetCnc(false);          // one ddraw.dll only: cnc-ddraw steps aside
            if (!on && Cnc) return;                // dgVoodoo is already off (cnc-ddraw owns ddraw.dll); never rename its dll
            Directory.CreateDirectory(BakDir);
            if (on)
            {
                DgvRestoreRenamed();
                List<string> made = new List<string>();
                foreach (string f in DgvOwn)   // clean system: put the bundled dgVoodoo copy in (never overwrites existing files)
                    if (!File.Exists(P(f))) { File.WriteAllBytes(P(f), Res("dgv_" + f)); made.Add(f); }
                if (made.Count > 0)   // the list is written BEFORE anything else can fail: Revert must know what is ours
                {
                    List<string> old = File.Exists(DgvInst) ? new List<string>(File.ReadAllLines(DgvInst)) : new List<string>();
                    foreach (string f in made) if (!old.Contains(f)) old.Add(f);
                    File.WriteAllLines(DgvInst, old.ToArray());
                    Log(L.T("applied") + "dgVoodoo (" + string.Join(", ", made.ToArray()) + ")");
                }
                JNote("dgv", true);
                try   // older bundled conf forced 16x filtering: it smeared the bitmap fonts (bold glyphs with a dark fringe)
                {
                    string cf = P("dgVoodoo.conf");
                    if (File.Exists(cf) && IniEdit.Get(cf, "DirectX", "Filtering", "") == "16") { BackupDgvConf(); IniEdit.Set(cf, "DirectX", "Filtering", "appdriven"); }
                }
                catch (Exception ex) { Log("dgVoodoo.conf: " + ex.Message); }
                try { DgvEnsureResolution(); } catch (Exception ex) { Log("dgVoodoo.conf (modes): " + ex.Message); }
            }
            else
            {
                List<string> ren = File.Exists(DgvRen) ? new List<string>(File.ReadAllLines(DgvRen)) : new List<string>();
                foreach (string f in DgvSwitch)
                {
                    string a = P(f), b = a + ".dgvoff";
                    if (File.Exists(a)) { if (File.Exists(b)) File.Delete(b); File.Move(a, b); if (!ren.Contains(f)) ren.Add(f); }
                }
                if (ren.Count > 0) File.WriteAllLines(DgvRen, ren.ToArray());
            }
            if (on && mark) File.WriteAllText(DgvMark, "1"); else if (File.Exists(DgvMark)) File.Delete(DgvMark);
            Log((on ? L.T("applied") : L.T("reverted")) + "dgVoodoo");
            Sync();
        }
        // full revert: remove what this tool installed, give back what it only renamed. A game that never had dgVoodoo from us is left alone - revert never installs anything.
        public void RevertDgv()
        {
            RevertCnc();
            bool touched = false;
            if (File.Exists(DgvInst))
            {
                foreach (string f in File.ReadAllLines(DgvInst))
                {
                    string n = f.Trim(); if (n.Length == 0) continue;
                    if (Path.GetFileName(n) != n || Array.FindIndex(DgvOwn, delegate(string o) { return string.Equals(o, n, StringComparison.OrdinalIgnoreCase); }) < 0) { Log("dgv.inst: skipped a foreign name: " + n); continue; }   // only the exact files we ship
                    File.Delete(P(n)); File.Delete(P(n) + ".dgvoff");
                }
                File.Delete(DgvInst); touched = true; JDrop("dgv");
            }
            if (File.Exists(DgvRen))   // the user's own dgVoodoo files that we renamed to *.dgvoff: back under their names
            {
                foreach (string f in File.ReadAllLines(DgvRen))
                {
                    string n = f.Trim(); if (Array.IndexOf(DgvSwitch, n) < 0) continue; string a = P(n);
                    if (!File.Exists(a) && File.Exists(a + ".dgvoff")) { File.Move(a + ".dgvoff", a); Log(L.T("reverted") + n + " (.dgvoff)"); }
                }
                File.Delete(DgvRen); touched = true;
            }
            if (File.Exists(DgvConfBak)) { File.Copy(DgvConfBak, P("dgVoodoo.conf"), true); File.Delete(DgvConfBak); Log(L.T("reverted") + "dgVoodoo.conf"); touched = true; }
            if (File.Exists(DgvMark)) File.Delete(DgvMark);
            if (touched) { Log(L.T("reverted") + "dgVoodoo"); Sync(); }
        }
        public void SetLauncher(bool on)
        {
            if (on)
            {
                Directory.CreateDirectory(BakDir);
                if (!File.Exists(StateFile))
                {
                    string prev = null;
                    using (RegistryKey k = Registry.CurrentUser.OpenSubKey(LayersKey)) { object v = k == null ? null : k.GetValue(Exe); if (v != null && v.ToString() != CompatFlags) prev = v.ToString(); }   // flags that are already OURS (state.txt lost) are not "the user's previous value"
                    File.WriteAllText(StateFile, prev == null ? "NONE" : "PREV=" + prev, Encoding.UTF8);
                }
                using (RegistryKey k = Registry.CurrentUser.CreateSubKey(LayersKey)) k.SetValue(Exe, CompatFlags, RegistryValueKind.String);
                Log(L.T("applied") + "smooth");
            }
            else
            {
                using (RegistryKey k = Registry.CurrentUser.CreateSubKey(LayersKey))
                {
                    string st = File.Exists(StateFile) ? File.ReadAllText(StateFile, Encoding.UTF8) : "NONE";
                    if (st.StartsWith("PREV=")) k.SetValue(Exe, st.Substring(5), RegistryValueKind.String);
                    else if (k.GetValue(Exe) != null) k.DeleteValue(Exe, false);
                }
                if (File.Exists(StateFile)) File.Delete(StateFile);
                Log(L.T("reverted") + "smooth");
            }
            CncSingleCpu();
            Sync();
        }

        public static bool IsAdmin()
        {
            try { return new System.Security.Principal.WindowsPrincipal(System.Security.Principal.WindowsIdentity.GetCurrent()).IsInRole(System.Security.Principal.WindowsBuiltInRole.Administrator); } catch { return false; }
        }
        public bool Writable()
        {
            try { string f = P("_dd_write_test.tmp"); File.WriteAllText(f, "x"); File.Delete(f); return true; } catch { return false; }
        }
        public static bool GameRunning()
        {
            if (Environment.GetEnvironmentVariable("OGF_TEST_NOGUARD") == "1") return false;   // self-test only: another div.exe (a pilot copy) may be running on the dev PC
            try { return Process.GetProcessesByName("div").Length > 0; } catch { return false; }
        }
        public bool RussianPresent { get { return File.Exists(P("ddrus.exe")) || File.Exists(P("ddrus.ins")) || File.Exists(P("ddrus.log")); } }
    }

    // ---------------------------------------------------------------- game folder detection
    static class Finder
    {
        static void Add(List<string> r, string d)
        {
            if (string.IsNullOrEmpty(d)) return;
            try
            {
                d = d.Trim().Trim('"');
                if (d.Length == 0) return;
                if (d.Length > 3) d = d.TrimEnd('\\', '/');
                if (!File.Exists(Path.Combine(d, "div.exe"))) return;
                foreach (string x in r) if (string.Equals(x, d, StringComparison.OrdinalIgnoreCase)) return;
                r.Add(d);
            }
            catch { }
        }
        static void ScanUninstall(List<string> r, RegistryKey root, string sub)
        {
            try
            {
                using (RegistryKey k = root.OpenSubKey(sub))
                {
                    if (k == null) return;
                    foreach (string n in k.GetSubKeyNames())
                        using (RegistryKey s = k.OpenSubKey(n))
                        {
                            object dn = s == null ? null : s.GetValue("DisplayName");
                            if (dn == null || dn.ToString().ToLowerInvariant().IndexOf("divine divinity") < 0) continue;
                            object il = s.GetValue("InstallLocation"); if (il != null) Add(r, il.ToString());
                            object us = s.GetValue("UninstallString"); if (us != null) { try { Add(r, Path.GetDirectoryName(us.ToString().Trim('"'))); } catch { } }
                        }
                }
            }
            catch { }
        }
        public static List<string> Find()
        {
            List<string> r = new List<string>();
            // 1. program location, parent, current dir
            string home = Environment.GetEnvironmentVariable("OGF_HOME");   // set by the single-file launcher: the folder the user ran the program from
            if (!string.IsNullOrEmpty(home)) { Add(r, home); try { Add(r, Directory.GetParent(home.TrimEnd('\\')).FullName); } catch { } }
            string me = AppDomain.CurrentDomain.BaseDirectory;
            Add(r, me); try { Add(r, Directory.GetParent(me.TrimEnd('\\')).FullName); } catch { }
            Add(r, Environment.CurrentDirectory);
            // 2. uninstall entries (GOG / Steam / retail)
            ScanUninstall(r, Registry.LocalMachine, @"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall");
            ScanUninstall(r, Registry.LocalMachine, @"SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall");
            ScanUninstall(r, Registry.CurrentUser, @"Software\Microsoft\Windows\CurrentVersion\Uninstall");
            // 3. GOG
            try
            {
                using (RegistryKey k = Registry.LocalMachine.OpenSubKey(@"SOFTWARE\Wow6432Node\GOG.com\Games") ?? Registry.LocalMachine.OpenSubKey(@"SOFTWARE\GOG.com\Games"))
                    if (k != null) foreach (string n in k.GetSubKeyNames()) using (RegistryKey s = k.OpenSubKey(n))
                            { object gn = s.GetValue("gameName"); if (gn != null && gn.ToString().ToLowerInvariant().IndexOf("divine divinity") >= 0) { object p = s.GetValue("path"); if (p != null) Add(r, p.ToString()); } }
            }
            catch { }
            // 4. Steam libraries
            try
            {
                string sp = null;
                using (RegistryKey k = Registry.CurrentUser.OpenSubKey(@"Software\Valve\Steam")) if (k != null && k.GetValue("SteamPath") != null) sp = k.GetValue("SteamPath").ToString();
                if (sp != null)
                {
                    sp = sp.Replace('/', '\\');
                    Add(r, Path.Combine(sp, @"steamapps\common\Divine Divinity"));
                    string vdf = Path.Combine(sp, @"steamapps\libraryfolders.vdf");
                    if (File.Exists(vdf))
                        foreach (string line in File.ReadAllLines(vdf))
                        {
                            if (line.ToLowerInvariant().IndexOf("\"path\"") < 0) continue;
                            int q2 = line.LastIndexOf('"'); if (q2 < 1) continue; int q1 = line.LastIndexOf('"', q2 - 1); if (q1 < 0) continue;
                            string lib = line.Substring(q1 + 1, q2 - q1 - 1).Replace(@"\\", @"\");
                            Add(r, Path.Combine(lib, @"steamapps\common\Divine Divinity"));
                        }
                }
            }
            catch { }
            // 5. typical folders on every fixed drive
            string[] rel = { @"Divine Divinity", @"Games\Divine Divinity", @"GAMES\Divine Divinity", @"GOG Games\Divine Divinity", @"Program Files (x86)\Divine Divinity",
                @"Program Files\Divine Divinity", @"Program Files (x86)\GOG Galaxy\Games\Divine Divinity", @"Program Files (x86)\Steam\steamapps\common\Divine Divinity",
                @"Steam\steamapps\common\Divine Divinity", @"SteamLibrary\steamapps\common\Divine Divinity", @"Games\SteamLibrary\steamapps\common\Divine Divinity",
                @"Program Files (x86)\Larian Studios\Divine Divinity", @"Larian Studios\Divine Divinity" };
            try
            {
                foreach (DriveInfo di in DriveInfo.GetDrives())
                {
                    if (di.DriveType != DriveType.Fixed && di.DriveType != DriveType.Removable) continue;
                    if (!di.IsReady) continue;
                    foreach (string x in rel) Add(r, Path.Combine(di.RootDirectory.FullName, x));
                }
            }
            catch { }
            return r;
        }
    }

    // ---------------------------------------------------------------- UI: theme + custom controls
    static class Th
    {
        // palette: charred oak, parchment, candle amber (the tavern / torchlight world of the game)
        // Two palettes, switched at run time (Th.Set + a rebuild of the pages): dark = charred oak + candle, light = warm parchment (not clinical white).
        // OnAmber is the text colour ON an amber fill (accent button, selected segment); Tint is the hover veil (white on dark, black on light).
        // Light contrasts (WCAG): Text on Surf 14:1, Muted 6.6:1, Faint 4.6:1, Amber 5.3:1 on Surf, OnAmber on Amber 5.6:1, Green 5.2:1, Red 6:1.
        public static Color Deep = Color.FromArgb(24, 21, 16), Bg = Color.FromArgb(34, 30, 24), Surf = Color.FromArgb(47, 42, 34), SurfHi = Color.FromArgb(60, 54, 44), Inset = Color.FromArgb(39, 35, 28);
        public static Color Line = Color.FromArgb(74, 66, 53), Text = Color.FromArgb(240, 230, 206), Muted = Color.FromArgb(188, 178, 154), Faint = Color.FromArgb(140, 131, 112);
        public static Color Amber = Color.FromArgb(222, 168, 66), AmberDeep = Color.FromArgb(150, 108, 36), Green = Color.FromArgb(132, 170, 108), Red = Color.FromArgb(205, 92, 70);
        public static Color OnAmber = Color.FromArgb(34, 30, 24), Tint = Color.White; public static bool Light;
        static Th() { try { Set(App.Get("theme") != "dark"); } catch { Set(true); } }   // light unless the user picked dark (owner 08.11.2026)
        public static void Set(bool light)
        {
            Light = light;
            if (light)
            {
                Deep = Color.FromArgb(221, 212, 192); Bg = Color.FromArgb(236, 229, 214); Surf = Color.FromArgb(248, 244, 234); SurfHi = Color.FromArgb(229, 220, 200); Inset = Color.FromArgb(241, 235, 221);
                Line = Color.FromArgb(206, 196, 172); Text = Color.FromArgb(42, 36, 26); Muted = Color.FromArgb(96, 86, 68); Faint = Color.FromArgb(110, 100, 80);
                Amber = Color.FromArgb(146, 88, 6); AmberDeep = Color.FromArgb(190, 140, 50); Green = Color.FromArgb(58, 110, 40); Red = Color.FromArgb(176, 52, 34); OnAmber = Color.FromArgb(255, 250, 238); Tint = Color.Black;
            }
            else
            {
                Deep = Color.FromArgb(24, 21, 16); Bg = Color.FromArgb(34, 30, 24); Surf = Color.FromArgb(47, 42, 34); SurfHi = Color.FromArgb(60, 54, 44); Inset = Color.FromArgb(39, 35, 28);
                Line = Color.FromArgb(74, 66, 53); Text = Color.FromArgb(240, 230, 206); Muted = Color.FromArgb(188, 178, 154); Faint = Color.FromArgb(140, 131, 112);
                Amber = Color.FromArgb(222, 168, 66); AmberDeep = Color.FromArgb(150, 108, 36); Green = Color.FromArgb(132, 170, 108); Red = Color.FromArgb(205, 92, 70); OnAmber = Color.FromArgb(34, 30, 24); Tint = Color.White;
            }
        }
        static readonly Dictionary<string, Font> fonts = new Dictionary<string, Font>();
        public static Font F(string fam, float pt, FontStyle st)
        {
            string k = fam + pt + st; Font f;
            if (!fonts.TryGetValue(k, out f)) { f = new Font(fam, pt, st, GraphicsUnit.Point); fonts[k] = f; }
            return f;
        }
        public static Font Body { get { return F("Segoe UI", 9f, FontStyle.Regular); } }
        public static Font Semi { get { return F("Segoe UI Semibold", 10.5f, FontStyle.Regular); } }
        public static Font Small { get { return F("Segoe UI Semibold", 7.5f, FontStyle.Regular); } }
        public static Font Glyph { get { return F("Segoe UI Symbol", 15f, FontStyle.Regular); } }
        public static Color A(Color c, int a) { return Color.FromArgb(a, c); }
        public static Color Mix(Color a, Color b, float t) { return Color.FromArgb((int)(a.R + (b.R - a.R) * t), (int)(a.G + (b.G - a.G) * t), (int)(a.B + (b.B - a.B) * t)); }
        public static GraphicsPath RR(RectangleF r, float rad)
        {
            GraphicsPath p = new GraphicsPath(); float d = rad * 2;
            p.AddArc(r.X, r.Y, d, d, 180, 90); p.AddArc(r.Right - d, r.Y, d, d, 270, 90);
            p.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90); p.AddArc(r.X, r.Bottom - d, d, d, 90, 90); p.CloseFigure(); return p;
        }
        public const TextFormatFlags TF = TextFormatFlags.NoPadding | TextFormatFlags.NoPrefix | TextFormatFlags.EndEllipsis | TextFormatFlags.Left;
    }

    // "Text always fits" (owner 07.11.2026, docs/design.md): EVERY interface text is drawn through TextFit.Draw. It measures the text with the same flags and width as DrawText;
    // if it does not fit the rectangle, the font goes down in 0.5 pt steps to MinPt (never outside the rectangle). Still too big at the minimum: drawn anyway (with an ellipsis)
    // and recorded in Over (window / control / text / needed x available). Order for a real fix: give it room -> wrap into a reserved area -> only then a smaller font.
    // The self-test "--shot textfit" builds every window in RU and EN, paints it (DrawToBitmap) and fails on any record in Over; Shrunk lists the texts that needed a smaller font.
    static class TextFit
    {
        public const float MinPt = 7.5f;
        public static bool Probe; public static string Where = ""; public static readonly Dictionary<string, int> Measured = new Dictionary<string, int>();   // self-test: texts measured per window (proves every window was really painted)
        public static readonly List<string> Over = new List<string>(), Shrunk = new List<string>(); static readonly Dictionary<string, bool> seen = new Dictionary<string, bool>();
        const TextFormatFlags NoMeasure = TextFormatFlags.EndEllipsis | TextFormatFlags.PathEllipsis | TextFormatFlags.WordEllipsis | TextFormatFlags.ModifyString | TextFormatFlags.HorizontalCenter | TextFormatFlags.Right | TextFormatFlags.VerticalCenter | TextFormatFlags.Bottom;
        // the size the text needs with these flags: one line = its natural width; with WordBreak = the height of the text wrapped to the rectangle's width (a word longer than the width shows as a wider need)
        public static Size Need(IDeviceContext dc, string t, Font f, int width, TextFormatFlags fl)
        {
            bool wrap = (fl & TextFormatFlags.WordBreak) != 0 && (fl & TextFormatFlags.SingleLine) == 0;
            Size proposed = new Size(wrap ? Math.Max(1, width) : int.MaxValue, int.MaxValue);
            return dc != null ? TextRenderer.MeasureText(dc, t, f, proposed, fl & ~NoMeasure) : TextRenderer.MeasureText(t, f, proposed, fl & ~NoMeasure);
        }
        public static bool Fits(Size need, Size have) { return need.Width <= have.Width && need.Height <= have.Height; }
        static Font Smaller(Font f, float pt) { return Th.F(string.IsNullOrEmpty(f.OriginalFontName) ? f.Name : f.OriginalFontName, pt, f.Style); }
        static string Who(Control owner) { if (owner == null) return "?"; Form fm = owner.FindForm(); return (fm != null ? (fm.Text.Length > 0 ? fm.Text : fm.GetType().Name) : "-") + " / " + owner.GetType().Name + (owner.Name.Length > 0 ? ":" + owner.Name : ""); }
        public static void Note(List<string> to, Control owner, string t, Size need, Size have)
        {
            string k = (Where.Length > 0 ? Where + " / " : "") + Who(owner) + " / \"" + t.Replace("\r", "").Replace("\n", "\\n") + "\" / " + need.Width + "x" + need.Height + " > " + have.Width + "x" + have.Height;
            string key = (to == Over ? "O" : "S") + k; if (!seen.ContainsKey(key)) { seen[key] = true; to.Add(k); }
        }
        // the font to draw with: the given one if the text fits, else the largest smaller step that fits, else the minimum (overflow recorded)
        public static Font Pick(IDeviceContext dc, Control owner, string t, Font f, Size have, TextFormatFlags fl, out bool fits)
        {
            fits = true; if (string.IsNullOrEmpty(t)) return f;
            if (Probe) { int n; Measured.TryGetValue(Where, out n); Measured[Where] = n + 1; }
            if (have.Width <= 0 || have.Height <= 0) return f;
            Size need = Need(dc, t, f, have.Width, fl); if (Fits(need, have)) return f;
            Size first = need;
            for (float pt = f.SizeInPoints - 0.5f; pt >= MinPt - 0.01f; pt -= 0.5f)
            {
                Font s = Smaller(f, pt); need = Need(dc, t, s, have.Width, fl);
                if (Fits(need, have)) { if (Probe) Note(Shrunk, owner, t + " @" + pt + "pt", first, have); return s; }
            }
            fits = false; Font min = f.SizeInPoints > MinPt ? Smaller(f, MinPt) : f;
            if (Probe) Note(Over, owner, t, Need(dc, t, min, have.Width, fl), have);
            return min;
        }
        public static void Draw(Graphics g, Control owner, string t, Font f, Rectangle r, Color c, TextFormatFlags fl)
        {
            if (string.IsNullOrEmpty(t)) return; bool fits; Font use = Pick(g, owner, t, f, r.Size, fl, out fits);
            TextRenderer.DrawText(g, t, use, r, c, fits ? fl : fl | TextFormatFlags.EndEllipsis);
        }
        // the self-test walk: standard Labels (their own painting does not come through Draw) and controls sticking out of their parent
        public static void CheckTree(Control root)
        {
            foreach (Control c in root.Controls)
            {
                if (!c.Visible) continue;
                Label l = c as Label;
                if (l != null && l.Text.Length > 0)
                {
                    if (l.AutoSize) { if (l.Right > root.ClientSize.Width && !(root is ScrollableControl && ((ScrollableControl)root).AutoScroll)) Note(Over, l, l.Text, new Size(l.Right, l.Height), root.ClientSize); }
                    else
                    {
                        TextFormatFlags fl = TextFormatFlags.WordBreak | TextFormatFlags.TextBoxControl | (l.UseMnemonic ? 0 : TextFormatFlags.NoPrefix);
                        Size have = new Size(l.ClientSize.Width - l.Padding.Horizontal, l.ClientSize.Height - l.Padding.Vertical), need = Need(null, l.Text, l.Font, have.Width, fl);
                        if (!Fits(need, have)) Note(Over, l, l.Text, need, have);
                        if (Probe) { int n; Measured.TryGetValue(Where, out n); Measured[Where] = n + 1; }
                    }
                }
                if (!(c is Form)) CheckTree(c);
            }
        }
    }

    class Btn : Control
    {
        public bool Accent; public float Pt = 9f; public Color Under = Th.Bg; bool hover, down; public int Badge; System.Windows.Forms.Timer pulseT, hoverT;
        // Pulse: a slow soft glow (fill and outline), used while an update is waiting; a timer runs only while it is on
        public bool Pulse { get { return pulseT != null; } set { if (value == Pulse) return; if (value) { pulseT = new System.Windows.Forms.Timer(); pulseT.Interval = 60; pulseT.Tick += delegate { if (Visible) Invalidate(); }; pulseT.Start(); } else { pulseT.Stop(); pulseT.Dispose(); pulseT = null; Invalidate(); } } }
        protected override void Dispose(bool d) { if (pulseT != null) { pulseT.Stop(); pulseT.Dispose(); pulseT = null; } if (hoverT != null) { hoverT.Stop(); hoverT.Dispose(); hoverT = null; } base.Dispose(d); }   // Badge > 0: an amber circle with the number in the top right corner
        public Btn() { SetStyle(ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw | ControlStyles.Selectable, true); SetStyle(ControlStyles.StandardClick | ControlStyles.StandardDoubleClick, false); TabStop = true; Cursor = Cursors.Hand; BackColor = Th.Bg; }
        // "hover only under the mouse" (docs/design.md): WinForms does not always send MouseLeave (a modal window opened by the click, a tip, a control that got disabled) and the highlight stayed on a button the mouse had left;
        // while hovered, a short timer checks the REAL cursor position and drops the highlight the moment the cursor is outside
        protected override void OnMouseEnter(EventArgs e) { hover = true; Invalidate(); if (hoverT == null) { hoverT = new System.Windows.Forms.Timer(); hoverT.Interval = 80; hoverT.Tick += delegate { if (!hover || !IsHandleCreated || !ClientRectangle.Contains(PointToClient(Cursor.Position))) { hover = false; down = false; hoverT.Stop(); Invalidate(); } }; } hoverT.Start(); base.OnMouseEnter(e); }
        protected override void OnMouseLeave(EventArgs e) { hover = false; down = false; if (hoverT != null) hoverT.Stop(); Invalidate(); base.OnMouseLeave(e); }
        protected override void OnEnabledChanged(EventArgs e) { hover = false; down = false; if (hoverT != null) hoverT.Stop(); base.OnEnabledChanged(e); }
        protected override void OnVisibleChanged(EventArgs e) { hover = false; down = false; if (hoverT != null) hoverT.Stop(); base.OnVisibleChanged(e); }
        protected override void OnMouseDown(MouseEventArgs e) { down = true; Focus(); Invalidate(); base.OnMouseDown(e); }
        protected override void OnMouseUp(MouseEventArgs e) { bool was = down; down = false; Invalidate(); base.OnMouseUp(e); if (was && ClientRectangle.Contains(e.Location)) OnClick(EventArgs.Empty); }
        protected override bool IsInputKey(Keys k) { return k == Keys.Enter || k == Keys.Space || base.IsInputKey(k); }
        protected override void OnKeyDown(KeyEventArgs e) { if (e.KeyCode == Keys.Enter || e.KeyCode == Keys.Space) { OnClick(EventArgs.Empty); e.Handled = true; } base.OnKeyDown(e); }
        protected override void OnGotFocus(EventArgs e) { Invalidate(); base.OnGotFocus(e); }
        protected override void OnLostFocus(EventArgs e) { Invalidate(); base.OnLostFocus(e); }
        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics; g.SmoothingMode = SmoothingMode.AntiAlias; g.Clear(Under);
            Color f = Accent ? Th.Amber : Th.Surf; if (!Enabled) f = Th.Inset; else if (hover) f = Accent ? Th.Mix(Th.Amber, Color.White, 0.14f) : Th.SurfHi; if (down) f = Th.Mix(f, Color.Black, 0.15f);
            float pu = pulseT != null && Enabled ? (float)(Math.Sin(Environment.TickCount / 1000.0 * 2 * Math.PI / 2.2) + 1) / 2 : 0f; if (pu > 0) f = Th.Mix(f, Color.White, 0.05f + 0.17f * pu);
            using (GraphicsPath p = Th.RR(new RectangleF(0.5f, 0.5f, Width - 1.5f, Height - 1.5f), 7))
            {
                using (SolidBrush b = new SolidBrush(f)) g.FillPath(b, p);
                using (Pen pen = new Pen(Focused ? Th.Amber : (Accent ? Th.Amber : Th.Line), Focused ? 1.5f : 1f)) g.DrawPath(pen, p);
                if (pu > 0) using (Pen glow = new Pen(Color.FromArgb((int)(150 * pu), Th.Amber), 3f)) g.DrawPath(glow, p);
            }
            TextFit.Draw(g, this, Text, Th.F("Segoe UI Semibold", Pt, FontStyle.Regular), new Rectangle(4, 0, Width - 8, Height), !Enabled ? Th.Faint : (Accent ? Th.OnAmber : Th.Text), TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding);
            if (Badge > 0)
            {
                int d = 17; Rectangle br = new Rectangle(Width - d - 1, 1, d, d); string bt = Badge > 9 ? "9+" : Badge.ToString();
                using (SolidBrush ring = new SolidBrush(Under)) g.FillEllipse(ring, br.X - 2, br.Y - 2, d + 4, d + 4);
                using (SolidBrush bb = new SolidBrush(Th.Amber)) g.FillEllipse(bb, br);
                TextRenderer.DrawText(g, bt, Th.F("Segoe UI Semibold", 7.5f, FontStyle.Regular), br, Th.OnAmber, TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding);
            }
        }
    }

    class Seg : Control
    {
        public string[] Items = { "RU", "EN" }; public Color Under = Th.Bg; int sel; public event EventHandler Changed;
        public int Selected { get { return sel; } set { sel = value; Invalidate(); } }
        public Seg() { SetStyle(ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true); Cursor = Cursors.Hand; BackColor = Th.Bg; Size = new Size(92, 30); }
        protected override void OnMouseUp(MouseEventArgs e) { int n = Items.Length; int i = Math.Max(0, Math.Min(n - 1, (int)((e.X - 3) / ((Width - 6) / (float)n)))); if (i != sel) { sel = i; Invalidate(); if (Changed != null) Changed(this, EventArgs.Empty); } base.OnMouseUp(e); }
        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics; g.SmoothingMode = SmoothingMode.AntiAlias; g.Clear(Under);
            RectangleF r = new RectangleF(0.5f, 0.5f, Width - 1.5f, Height - 1.5f);
            using (GraphicsPath p = Th.RR(r, 8)) { using (SolidBrush b = new SolidBrush(Th.Inset)) g.FillPath(b, p); using (Pen pen = new Pen(Th.Line)) g.DrawPath(pen, p); }
            float w = (Width - 6) / (float)Items.Length;
            RectangleF ar = new RectangleF(3 + sel * w, 3, w, Height - 7);
            using (GraphicsPath p = Th.RR(ar, 6)) using (SolidBrush b = new SolidBrush(Enabled ? Th.Amber : Th.Faint)) g.FillPath(b, p);
            for (int i = 0; i < Items.Length; i++)
                TextFit.Draw(g, this, Items[i], Th.F("Segoe UI Semibold", 8.5f, FontStyle.Regular), new Rectangle((int)(3 + i * w) + 2, 3, (int)w - 4, Height - 7), i == sel ? Th.OnAmber : Th.Muted, TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding);
        }
    }

    class Field : Control
    {
        public TextBox Box = new TextBox(); public Color Under = Th.Bg;
        public Field()
        {
            SetStyle(ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true); BackColor = Th.Bg;
            Box.BorderStyle = BorderStyle.None; Box.BackColor = Th.Inset; Box.ForeColor = Th.Text; Box.Font = Th.F("Segoe UI", 10f, FontStyle.Regular);
            Controls.Add(Box); Box.GotFocus += delegate { Invalidate(); }; Box.LostFocus += delegate { Invalidate(); };
        }
        [System.Runtime.InteropServices.DllImport("user32.dll", CharSet = System.Runtime.InteropServices.CharSet.Unicode)] static extern IntPtr SendMessage(IntPtr h, int msg, IntPtr w, string l);
        string hint = ""; public string Hint { get { return hint; } set { hint = value; if (Box.IsHandleCreated) SendMessage(Box.Handle, 0x1501, (IntPtr)1, hint); } }
        protected override void OnHandleCreated(EventArgs e) { base.OnHandleCreated(e); Box.HandleCreated += delegate { SendMessage(Box.Handle, 0x1501, (IntPtr)1, hint); }; if (Box.IsHandleCreated) SendMessage(Box.Handle, 0x1501, (IntPtr)1, hint); }
        protected override void OnLayout(LayoutEventArgs e) { Box.SetBounds(12, (Height - Box.Height) / 2, Width - 24, Box.Height); base.OnLayout(e); }
        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics; g.SmoothingMode = SmoothingMode.AntiAlias; g.Clear(Under);
            using (GraphicsPath p = Th.RR(new RectangleF(0.5f, 0.5f, Width - 1.5f, Height - 1.5f), 7))
            { using (SolidBrush b = new SolidBrush(Th.Inset)) g.FillPath(b, p); using (Pen pen = new Pen(Box.Focused ? Th.Amber : Th.Line, 1f)) g.DrawPath(pen, p); }
        }
    }

    // ---------------------------------------------------------------- entry point (+ headless CLI for tests / automation)
    // last resort for anything nobody caught: write it to the log and tell the user in plain words instead of the system "Continue / Quit" box
    static class Crash
    {
        static bool busy;
        public static void Handle(Exception ex, bool fatal)
        {
            if (busy) return; busy = true;
            try
            {
                try { File.AppendAllText(Path.Combine(App.DataDir, "log.txt"), DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + "   UNHANDLED: " + (ex == null ? "(unknown)" : ex.ToString()) + "\r\n", Encoding.UTF8); } catch { }
                string m = ex == null ? "" : ex.Message;
                MessageBox.Show(U.R("Произошла непредвиденная ошибка:\r\n\r\n", "An unexpected error occurred:\r\n\r\n") + m + U.R("\r\n\r\nПодробности записаны в журнал программы («О программе» → открыть журнал). Если ошибка повторяется — отправьте её автору через «Обратная связь».\r\n\r\n",
                    "\r\n\r\nDetails are in the program log (\"About\" → open the log). If it keeps happening, send it to the author with \"Feedback\".\r\n\r\n") + (fatal ? U.R("Программа будет закрыта.", "The program will close.") : U.R("Можно продолжать работу.", "You can keep working.")),
                    App.Name, MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            catch { }
            busy = false;
            if (fatal) Environment.Exit(1);
        }
    }

    static class Program
    {
        [STAThread]
        static int Main(string[] args)
        {
            string initial = null;
            if (args.Length > 1 && args[0] == "--open") initial = args[1];
            else if (args.Length > 1 && args[0] == "--screen") { Shots.Full(args[1]); return 0; }
            else if (args.Length > 1 && args[0] == "--tool") { try { Console.Out.Flush(); File.WriteAllText(args.Length > 2 ? args[2] : "tool.txt", Core.ToolPath(args[1]), Encoding.UTF8); return 0; } catch (Exception ex) { File.WriteAllText(args.Length > 2 ? args[2] : "tool.txt", "ERR " + ex, Encoding.UTF8); return 1; } }
            else if (args.Length > 2 && args[0] == "--shot") { return Shots.Run(args); }
            else if (args.Length > 0 && Array.IndexOf(new string[] { "--version", "--unseen", "--data-info", "--verify-sig", "--update-check", "--update-install", "--apply-update" }, args[0]) >= 0) return Updater.Cli(args);
            else if (args.Length > 0 && args[0].StartsWith("--")) return Cli(args);
            App.RotateLog();
            Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false);
            Application.SetUnhandledExceptionMode(UnhandledExceptionMode.CatchException);
            Application.ThreadException += delegate(object s, System.Threading.ThreadExceptionEventArgs e) { Crash.Handle(e.Exception, false); };
            AppDomain.CurrentDomain.UnhandledException += delegate(object s, UnhandledExceptionEventArgs e) { Crash.Handle(e.ExceptionObject as Exception, true); };
            Application.Run(new MainForm(initial));
            return 0;
        }

        // --assets list|status|apply ID|revert ID. Output lines: ASSET id=.. version=.. download=.. installed=.. | ASSET-STATUS id=.. state=original|applied|mixed|unknown ... | ASSETS active=..
        static void AssetsCli(Core c, string act, string id, StringBuilder sb)
        {
            AssetSets a = c.Assets; AssetProgress quiet = delegate { };
            if (act == "list")
            {
                string note; List<AssetManifest> l = a.LoadCatalog(out note); if (note.Length > 0) sb.AppendLine("WARN " + note);
                foreach (AssetManifest m in l) sb.AppendLine("ASSET id=" + m.Id + " version=" + m.Version + " kind=" + m.Kind + " files=" + m.Files.Count + " download=" + m.Download + " installed=" + m.Installed + " name=" + m.Name);
            }
            else if (act == "apply") a.Apply(a.FetchManifest(id), quiet, null);
            else if (act == "revert") a.Revert(id, quiet, null);
            // status after every action: the hashes decide what is installed
            List<string> act2 = new List<string>(); foreach (AssetRec r in a.ActiveRecs()) act2.Add(r.Id + (r.State == "applied" ? "" : "(" + r.State + ")"));
            if (act == "status" || act == "apply" || act == "revert")
            {
                List<AssetManifest> known = new List<AssetManifest>(); string note2 = "";
                if (id != null) { AssetManifest m0 = a.CachedManifest(id); if (m0 != null) known.Add(m0); }
                else known = a.LoadCatalog(out note2);
                foreach (AssetManifest m in known) { AssetState s = a.StateOf(m, true, null, null); sb.AppendLine("ASSET-STATUS id=" + m.Id + " state=" + s.Word + " applied=" + s.Applied + " original=" + s.Orig + " other=" + s.Other + " missing=" + s.Missing + " total=" + s.Total + " cached=" + a.IsCached(m)); }
            }
            sb.AppendLine("ASSETS active=" + (act2.Count == 0 ? "none" : string.Join(",", act2.ToArray())));
        }

        // --game DIR [--set none|dusk|full] [--voice|--dusk|--dgv|--cnc|--launcher|--bone|--shortcut on|off] [--font N:big|N:orig] [--backup-saves] [--status] [--sync] [--log FILE] [--lang ru|en]
        // Strict: a missing value, a value other than on/off, an unknown flag -> message + exit code 2 (flags) / 3 (game running) / 4 (no rights); nothing is changed then.
        static int Cli(string[] a)
        {
            bool sync = false; string dir = null, cnc = null, voice = null, dusk = null, shortcut = null, set = null, bone = null, launcher = null, fps = null, fps80 = null, korean = null, defs = null, dgv = null, font = null, log = null, preset = null, wrapper = "cnc", scale = null, monitor = null, gfxImage = null, gfxSkin = null; bool bak = false, status = false, revertAll = false; string assetsAct = null, assetsId = null, gfxAct = null, gfxArg = null;
            List<string> errs = new List<string>(), warns = new List<string>();
            for (int i = 0; i < a.Length; i++)
            {
                string f = a[i];
                if (f == "--backup-saves") { bak = true; continue; }
                if (f == "--status") { status = true; continue; }
                if (f == "--sync") { sync = true; continue; }   // what the program does at start-up: embedded files refreshed, div.exe rebuilt to the current tables (src/Install.cs)
                if (f == "--revert-all") { revertAll = true; continue; }
                if (f == "--assets")   // --assets list | status | apply <id> | revert <id>
                {
                    if (i + 1 >= a.Length || a[i + 1].StartsWith("--")) { errs.Add("ERROR missing value for --assets"); continue; }
                    assetsAct = a[++i];
                    if (assetsAct == "apply" || assetsAct == "revert") { if (i + 1 >= a.Length || a[i + 1].StartsWith("--")) errs.Add("ERROR --assets " + assetsAct + " needs a set id"); else assetsId = a[++i]; }
                    else if (assetsAct != "list" && assetsAct != "status") errs.Add("ERROR --assets must be list, status, apply <id> or revert <id>, got: " + assetsAct);
                    continue;
                }
                if (f == "--gfx")   // --gfx list | status | revert | apply slot=value,...   (slots/fixes: games/<id>/gfx/gfx.txt)
                {
                    if (i + 1 >= a.Length || a[i + 1].StartsWith("--")) { errs.Add("ERROR missing value for --gfx"); continue; }
                    gfxAct = a[++i];
                    if (gfxAct == "apply") { if (i + 1 >= a.Length || a[i + 1].StartsWith("--")) errs.Add("ERROR --gfx apply needs slot=value,..."); else gfxArg = a[++i]; }
                    else if (gfxAct != "list" && gfxAct != "status" && gfxAct != "revert") errs.Add("ERROR --gfx must be list, status, revert or apply slot=value,..., got: " + gfxAct);
                    continue;
                }
                bool known = Array.IndexOf(new string[] { "--game", "--set", "--bone", "--launcher", "--fps", "--fps80", "--korean", "--defaults", "--dgv", "--font", "--log", "--cnc", "--voice", "--dusk", "--shortcut", "--lang", "--preset", "--wrapper", "--scale", "--monitor", "--gfx-image", "--gfx-skin" }, f) >= 0;
                if (!known) { warns.Add("WARN unknown argument ignored: " + f); continue; }
                if (i + 1 >= a.Length || a[i + 1].StartsWith("--")) { errs.Add("ERROR missing value for " + f); continue; }
                string v = a[++i];
                if (f == "--game") dir = v; else if (f == "--set") set = v; else if (f == "--bone") bone = v; else if (f == "--launcher") launcher = v; else if (f == "--fps") fps = v; else if (f == "--fps80") fps80 = v; else if (f == "--korean") korean = v; else if (f == "--defaults") defs = v; else if (f == "--dgv") dgv = v; else if (f == "--font") font = v;
                else if (f == "--log") log = v; else if (f == "--cnc") cnc = v; else if (f == "--voice") voice = v; else if (f == "--dusk") dusk = v; else if (f == "--shortcut") shortcut = v; else if (f == "--preset") preset = v; else if (f == "--wrapper") wrapper = v; else if (f == "--scale") scale = v; else if (f == "--gfx-image") gfxImage = v; else if (f == "--gfx-skin") gfxSkin = v; else if (f == "--monitor") monitor = v;
                else if (f == "--lang") { if (v == "ru" || v == "en" || v == "ko") { L.Ru = v == "ru"; L.Ko = v == "ko"; } else errs.Add("ERROR --lang must be ru, en or ko, got: " + v); }
            }
            Action<string, string> onoff = delegate(string n, string v) { if (v != null && v != "on" && v != "off") errs.Add("ERROR " + n + " must be on or off, got: " + v); };
            onoff("--voice", voice); onoff("--dusk", dusk); onoff("--dgv", dgv); onoff("--cnc", cnc); onoff("--launcher", launcher); onoff("--bone", bone); onoff("--shortcut", shortcut); onoff("--fps80", fps80); onoff("--korean", korean);
            int fpsMode = -1, fpsN = 0; if (fps != null) { string fl = fps.ToLowerInvariant(); if (fl == "orig" || fl == "off") fpsMode = Core.FpsOrig; else if (fl == "monitor") fpsMode = Core.FpsMonitor; else if (fl == "unlimited") fpsMode = Core.FpsUnlimited; else if (int.TryParse(fl, out fpsN) && fpsN >= 20 && fpsN <= 1000) fpsMode = Core.FpsCustom; else errs.Add("ERROR --fps must be orig, monitor, unlimited or a number 20..1000, got: " + fps); }   // frame mode
            if (set != null && set != "none" && set != "dusk" && set != "full") errs.Add("ERROR --set must be none, dusk or full, got: " + set);
            int pk = -1; if (preset != null && (!int.TryParse(preset, out pk) || pk < 0 || pk > 2)) errs.Add("ERROR --preset must be 0 (HD), 1 (2K) or 2 (4K), got: " + preset);
            if (wrapper != "cnc" && wrapper != "dgv") errs.Add("ERROR --wrapper must be cnc or dgv, got: " + wrapper);
            int spct = 0; Size msize = Size.Empty;
            if (scale != null && !UiScale.TryParsePct(scale, out spct)) errs.Add("ERROR --scale must be auto, 100, 125, 150 or 200, got: " + scale);
            if (monitor != null && !UiScale.TryParseSize(monitor, out msize)) errs.Add("ERROR --monitor must be WIDTHxHEIGHT (e.g. 2560x1440), got: " + monitor);
            if (monitor != null && scale == null && gfxAct == null) errs.Add("ERROR --monitor only makes sense with --scale");
            int fcat = 0; bool fbig = false;
            if (font != null) { System.Text.RegularExpressions.Match m = System.Text.RegularExpressions.Regex.Match(font, @"^([0-2]):(big|orig)$"); if (!m.Success) errs.Add("ERROR --font must be N:big or N:orig with N = 0..2, got: " + font); else { fcat = int.Parse(m.Groups[1].Value); fbig = m.Groups[2].Value == "big"; } }
            if (gfxImage != null && gfxImage != "none" && gfxImage != "orig" && gfxImage != "v2") errs.Add("ERROR --gfx-image must be none, orig or v2, got: " + gfxImage);
            if (gfxSkin != null && Array.IndexOf(new string[] { "none", "orig", "a", "b", "c", "d" }, gfxSkin.ToLowerInvariant()) < 0) errs.Add("ERROR --gfx-skin must be none, orig, A, B, C or D, got: " + gfxSkin);
            if (dir == null && errs.Count == 0) errs.Add("ERROR --game DIR is required");
            StringBuilder sb = new StringBuilder(); int rc = 0;
            foreach (string w in warns) sb.AppendLine(w);
            if (errs.Count > 0) { foreach (string e in errs) sb.AppendLine(e); if (log != null) File.WriteAllText(log, sb.ToString(), Encoding.UTF8); return 2; }
            try
            {
                Core c = new Core(dir); c.Log = delegate(string s) { sb.AppendLine(s); }; c.Warn = delegate(string s) { sb.AppendLine("WARN " + s); };
                if (!c.HasGame) throw new Exception(L.T("stNoGame"));
                bool change = korean != null || (assetsAct == "apply" || assetsAct == "revert") || gfxAct == "apply" || gfxAct == "revert" || (gfxImage != null && gfxImage != "none") || (gfxSkin != null && gfxSkin != "none") || set != null || fps != null || fps80 != null || defs != null || voice != null || dusk != null || shortcut != null || bone != null || launcher != null || dgv != null || cnc != null || font != null || bak || preset != null || revertAll || scale != null || sync;
                if (change && Core.GameRunning()) { sb.AppendLine("ERROR " + L.T("running")); rc = 3; }
                else if (change && !Core.IsAdmin() && !c.Writable()) { sb.AppendLine("ERROR " + L.T("needAdmin").Split('\r')[0]); rc = 4; }
                else
                {
                    if (sync) c.StartupSync();
                    if (revertAll) { List<string> fl = c.RevertAll(); foreach (string x in fl) sb.AppendLine("REVERT-FAILED " + x); if (fl.Count > 0) rc = 1; }
                    ScalePlan plan = null; bool scaleInPreset = scale != null && preset != null && wrapper == "cnc";
                    if (scaleInPreset) { Size real = msize.IsEmpty ? Core.ScreenPixels(Screen.PrimaryScreen) : msize; plan = c.PlanScale(spct, Core.ClassMonitor(pk, real)); }
                    if (preset != null) { List<string> sk = c.ApplyPreset(pk, wrapper == "cnc", plan); foreach (string x in sk) sb.AppendLine("PRESET-SKIPPED " + x); }
                    if (scale != null && preset != null && wrapper != "cnc") sb.AppendLine("SCALE-SKIPPED the picture scale needs gr-draw (--wrapper cnc)");
                    if (set != null) c.SetMode(set == "full" ? FixMode.Full : set == "dusk" ? FixMode.Dusk : FixMode.None);
                    if (voice != null) c.SetVoice(voice == "on");
                    if (dusk != null) c.SetDusk(dusk == "on");
                    if (shortcut != null) { if (shortcut == "on") c.CreateShortcut(); else c.RemoveShortcut(); }
                    if (bone != null) c.SetBone(bone == "on");
                    if (launcher != null) c.SetLauncher(launcher == "on");
                    if (fpsMode >= 0) c.SetFpsMode(fpsMode, fpsN);
                    if (korean != null) c.SetKorean(korean == "on");   // the Korean language pack for the English game (src/Korean.cs)
                    if (fps80 != null) c.SetFps80(fps80 == "on");   // tick 80 (src/Tick80.cs)
                    if (defs != null) { c.StartupSync(); c.ApplyPatchDefaults(defs == "force"); }   // the start-up defaults of Patches & fixes (voice, dusk, smooth play, frame mode): once per game; force = like the wizard
                    if (dgv != null) c.SetDgv(dgv == "on", true);
                    if (cnc != null) c.SetCnc(cnc == "on");
                    if (scale != null && preset == null) plan = c.ApplyScale(spct, msize.IsEmpty ? Core.ScreenPixels(Screen.PrimaryScreen) : msize);
                    if (plan != null) { sb.AppendLine("SCALE pct=" + plan.Pct + " eff=" + plan.EffPct + " mon=" + plan.Mon.Width + "x" + plan.Mon.Height + " game=" + plan.Game.Width + "x" + plan.Game.Height + " integer=" + plan.Integer + " shader=" + plan.Shader + " notes=" + string.Join(",", plan.Notes.ToArray())); }
                    if (font != null) c.SetFont(fcat, fbig);
                    if (bak) c.BackupSaves();
                    if (assetsAct != null) AssetsCli(c, assetsAct, assetsId, sb);
                    if (gfxAct != null) Core.GfxCli(c, gfxAct, gfxArg, msize, sb);
                    if ((gfxImage != null && gfxImage != "none") || (gfxSkin != null && gfxSkin != "none"))   // quick setup look: isolated, a failure here is reported but the preset above stays
                    {
                        try
                        {
                            string ge; GfxSel gs = c.GfxQuickSel(gfxImage, gfxSkin, out ge); if (ge != null) throw new InvalidOperationException("unknown value " + ge);
                            Dictionary<string, AssetManifest> gm = new Dictionary<string, AssetManifest>(); string gn; foreach (AssetManifest m in c.Assets.LoadCatalog(out gn)) gm[m.Id] = m;
                            GfxPlan gp = c.GfxMakePlan(gs, gm); if (gp.Problems.Count > 0) throw new InvalidOperationException(string.Join("; ", gp.Problems.ToArray()));
                            sb.AppendLine("GFX-PLAN steps=" + gp.Steps.Count + " download=" + gp.Download); c.GfxApply(gp, delegate { }, null); sb.AppendLine("GFX-RESULT ok");
                        }
                        catch (Exception gx) { sb.AppendLine("GFX-FAILED " + gx.Message); rc = 1; }
                    }
                }
                sb.AppendLine("STATUS exeSupported=" + c.ExeSupported + " mode=" + c.Mode + " voice=" + c.VoiceOn + " dusk=" + c.DuskOn + " shortcut=" + c.ShortcutExists + " voicePatched=" + c.VoicePatched + " duskPatched=" + c.DuskPatched + " dllsFull=" + c.DllsFull + " bone=" + c.Bone + " fps=" + Core.FpsStatus(c) + " optouts=" + string.Join("+", new string[] { c.FixOptedOut("voice") ? "voice" : "", c.FixOptedOut("dusk") ? "dusk" : "", c.FixOptedOut("smooth") ? "smooth" : "", c.FixOptedOut("fps") ? "fps" : "" }) + " launcher=" + c.Launcher + " dgv=" + c.Dgv + " cnc=" + c.Cnc + " fonts=" + c.FontState(0) + "," + c.FontState(1) + "," + c.FontState(2) + " fontStep=" + c.FontStep(0) + "," + c.FontStep(1) + "," + c.FontStep(2) + " fontCustom=" + c.FontIsCustom(0) + "," + c.FontIsCustom(1) + "," + c.FontIsCustom(2) + " voiceMixed=" + c.VoiceMixed);
                sb.AppendLine("FPS80 state=" + c.Fps80State() + " avail=" + c.Fps80Avail);
                sb.AppendLine("KOREAN state=" + c.KoreanState() + " why=" + (c.KoreanWhyNot() ?? "ok"));
            }
            catch (Exception ex) { sb.AppendLine("ERROR " + ex.Message); rc = 1; }
            if (log != null) File.WriteAllText(log, sb.ToString(), Encoding.UTF8);
            return rc;
        }
    }
}
