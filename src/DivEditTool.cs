using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Windows.Forms;

namespace DDFixTool
{
    // Third-party world editor "DivEdit" by Raan (maps, objects, NPCs of Divine Divinity; WPF + OpenGL, .NET 8 Desktop Runtime).
    // Like DGE the repository has NO licence: nothing is bundled or mirrored. On a click, after the user confirms, the author's release (.rar) is downloaded from GitHub,
    // checked against a pinned SHA-256 and unpacked with Windows' own tar.exe into %LOCALAPPDATA%\GameRemix\cache\divedit-<tag>\.
    // DivEdit WRITES into <game>\main\startup, so a one-time copy of that folder is made before the first start.
    static class DivEdit
    {
        public const string Tag = "v0.4.0", Repo = "https://github.com/Raan/DivEdit", Author = "Raan",
            Url = "https://github.com/Raan/DivEdit/releases/download/v0.4.0/DivEdit_v.0.4.0.rar",
            Sha256 = "a87a862d08075d43e50a232505ee2e0ae5efd232ee83433592c7422539a0ab8b", Exe = "DivEdit.exe";
        public const long Size = 11889053;

        public static string Dir { get { return Path.Combine(Fetcher.CacheRoot, "divedit-" + Tag); } }
        public static string ExePath { get { return Path.Combine(Dir, Exe); } }
        public static bool Ready { get { return Fetcher.CacheValid(Dir, Exe); } }   // the cached exe must still match the hash written when it was installed

        // returns an error text, or null when started ("" = cancelled by the user)
        public static string Run(IWin32Window owner, Core game)
        {
            if (Environment.OSVersion.Version.Major < 10) return U.R("Эта программа собрана под .NET 8 и работает только на Windows 10 и новее.", "This tool is built for .NET 8 and runs on Windows 10 and newer only.");
            if (!Ready)
            {
                string q = U.R("Скачать «DivEdit» " + Tag + " (" + (Size / 1048576.0).ToString("0.0") + " МБ) с GitHub автора (" + Author + ")?\n\n" + Repo + "\n\nПрограмма не входит в состав GameRemix: у автора нет лицензии, поэтому она скачивается только по вашему согласию.",
                               "Download “DivEdit” " + Tag + " (" + (Size / 1048576.0).ToString("0.0") + " MB) from the author's (" + Author + ") GitHub?\n\n" + Repo + "\n\nIt is not part of GameRemix: the author has no licence, so it is only downloaded with your consent.");
                if (MessageBox.Show(owner, q, "DivEdit", MessageBoxButtons.OKCancel, MessageBoxIcon.Question) != DialogResult.OK) return "";
                string err = Download(owner); if (err != null) return err.Length == 0 ? "" : U.R("Не удалось скачать: ", "Download failed: ") + err;
            }
            if (!Dge.RuntimeOk())
            {
                if (MessageBox.Show(owner, U.R("Для запуска нужен «.NET Desktop Runtime» версии 8 или новее (x64). Открыть страницу загрузки Microsoft?", "A “.NET Desktop Runtime” 8 or newer (x64) is required. Open the Microsoft download page?"), "DivEdit", MessageBoxButtons.OKCancel, MessageBoxIcon.Information) == DialogResult.OK) U.Open("https://dotnet.microsoft.com/download/dotnet/8.0");
                return "";
            }
            if (game != null && game.HasGame)
            {
                string bk = null; string be = WorkForm.Run(owner, "DivEdit", U.R("Копирую мир игры (main\\startup)…", "Copying the game world (main\\startup)…"), false, delegate(WorkForm w) { bk = BackupWorld(game); });   // off the UI thread
                if (be != null && be.Length > 0) return U.R("Не удалось сделать копию мира: ", "Could not back up the world: ") + be;
                if (bk != null) MessageBox.Show(owner, U.R("DivEdit записывает изменения прямо в игру (папка main\\startup). Копия до правок сохранена здесь:\n\n", "DivEdit writes its changes straight into the game (main\\startup). A copy from before any edits is kept here:\n\n") + bk + U.R("\n\nЗапуск занимает около минуты (окно будет белым и «не отвечает», занято около 1 ГБ памяти) — это нормально, подождите.", "\n\nStart-up takes about a minute (the window stays white and \"not responding\", about 1 GB of memory) — this is normal, please wait."), "DivEdit", MessageBoxButtons.OK, MessageBoxIcon.Information);
                SetGame(game.Dir);
            }
            try { ProcessStartInfo psi = new ProcessStartInfo(ExePath); psi.WorkingDirectory = Dir; psi.UseShellExecute = false; psi.EnvironmentVariables["DOTNET_ROLL_FORWARD"] = "Major"; Process.Start(psi); return null; }
            catch (Exception ex) { return ex.Message; }
        }

        // one-time copy of <game>\main\startup; returns its path when it was just made
        static string BackupWorld(Core game)
        {
            string src = game.P(@"main\startup"), dst = Path.Combine(game.GameData, @"divedit_backup\startup");
            if (!Directory.Exists(src) || Directory.Exists(dst)) return null;   // nothing to copy / the copy from before the first edit already exists
            // DivEdit writes straight into the game: no copy = no start. Every failure here is thrown (the caller shows it and does not launch the editor)
            long need = 0; foreach (string f in Directory.GetFiles(src, "*", SearchOption.AllDirectories)) need += new FileInfo(f).Length;
            try { string root = Path.GetPathRoot(Path.GetFullPath(dst)); DriveInfo di = new DriveInfo(root.Substring(0, 1)); if (di.AvailableFreeSpace < need + 256L * 1024 * 1024) throw new IOException(U.R("Не хватает места для копии мира (нужно ", "Not enough free space for the world backup (need ") + ((need + 256L * 1024 * 1024) / 1048576) + U.R(" МБ).", " MB).")); }
            catch (IOException) { throw; }
            catch (Exception) { }   // free space unknown (network path): the copy itself decides
            try { if (Directory.Exists(dst + ".tmp")) Directory.Delete(dst + ".tmp", true); CopyTree(src, dst + ".tmp"); Directory.Move(dst + ".tmp", dst); return dst; }
            catch { try { if (Directory.Exists(dst + ".tmp")) Directory.Delete(dst + ".tmp", true); } catch { } throw; }
        }
        static void CopyTree(string s, string d)
        {
            Directory.CreateDirectory(d);
            foreach (string f in Directory.GetFiles(s)) File.Copy(f, Path.Combine(d, Path.GetFileName(f)), true);
            foreach (string x in Directory.GetDirectories(s)) CopyTree(x, Path.Combine(d, Path.GetFileName(x)));
        }
        // DivEdit asks for div.exe on its first start; we hand it the game folder through its own config
        static void SetGame(string dir)
        {
            try
            {
                string ed = Path.Combine(Dir, "Editor"); Directory.CreateDirectory(ed); string cfg = Path.Combine(ed, "config.ini");
                if (File.Exists(cfg)) foreach (string ln in File.ReadAllLines(cfg)) if (ln.StartsWith("Game_directory ") && ln.Substring(15).TrimEnd('\\', '/').Equals(dir.TrimEnd('\\', '/'), StringComparison.OrdinalIgnoreCase)) return;
                File.WriteAllText(cfg, "//Created automatically, do not change!\r\nGame_directory " + dir.TrimEnd('\\', '/') + "\r\nWorld 0\r\nPosition 0 0\r\n", Encoding.Default);
            }
            catch { }
        }

        public static string Fetch() { return Download(null); }
        static string Download(IWin32Window owner)
        {
            string tar = Path.Combine(Environment.SystemDirectory, "tar.exe");
            if (!File.Exists(tar)) return U.R("Для распаковки нужен Windows 10 (1909+) или 11: в системе нет tar.exe.", "Unpacking needs Windows 10 (1909+) or 11: tar.exe is missing.");
            return Fetcher.Install(owner, "DivEdit", Url, Sha256, Size, Dir, Exe, delegate(FileStream fs, string tmp, string stage)
            {
                // tar reads the file we still hold open with a write lock, so the bytes that were verified are the bytes that get unpacked
                ProcessStartInfo psi = new ProcessStartInfo(tar, "-xf \"" + tmp + "\" -C \"" + stage + "\""); psi.UseShellExecute = false; psi.CreateNoWindow = true; psi.RedirectStandardError = true; psi.RedirectStandardOutput = true;
                System.Text.StringBuilder err = new System.Text.StringBuilder();
                using (Process p = new Process())
                {
                    p.StartInfo = psi; p.ErrorDataReceived += delegate(object s, DataReceivedEventArgs e) { if (e.Data != null && err.Length < 4000) err.AppendLine(e.Data); }; p.OutputDataReceived += delegate { };
                    p.Start(); p.BeginErrorReadLine(); p.BeginOutputReadLine();   // read asynchronously: a full pipe must not block tar
                    int waited = 0; while (!p.WaitForExit(500)) { waited += 500; if (waited > 180000) { try { p.Kill(); } catch { } return U.R("Распаковка не завершилась за 3 минуты и прервана.", "Unpacking did not finish in 3 minutes and was stopped."); } }
                    p.WaitForExit();
                    if (p.ExitCode != 0 && !File.Exists(Path.Combine(stage, Exe))) return U.R("Не удалось распаковать архив (нужна свежая сборка Windows 10/11): ", "Could not unpack the archive (a recent Windows 10/11 build is needed): ") + err.ToString().Trim();
                }
                return null;
            });
        }
    }
}
