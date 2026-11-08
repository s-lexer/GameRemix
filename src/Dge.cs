using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Security.Cryptography;
using System.Text;
using System.Windows.Forms;

namespace DDFixTool
{
    // Third-party tool "Divinity Graphics Extender" by Raan (extract / replace sprites of the CPackedi.*c archives).
    // The repository has NO licence, so we do not bundle or mirror it: on a click, after the user confirms, the official release zip is
    // downloaded from the author's GitHub, checked against a pinned SHA-256 and unpacked into %LOCALAPPDATA%\GameRemix\cache\dge-<tag>\.
    // It needs the .NET 8 Desktop Runtime (Windows 10+), which the user installs if missing.
    static class Dge
    {
        public const string Tag = "v0.10", Repo = "https://github.com/Raan/Divinity_Graphics_Extender", Author = "Raan",
            Url = "https://github.com/Raan/Divinity_Graphics_Extender/releases/download/v0.10/DGE.v0.10.zip",
            Sha256 = "84fef4326dbb06316ab4f6f10bb0561ead9d5d19bdda5a485121b1cd6b55a8c7", Exe = "Div_Ggraphics_Extender.exe";
        public const long Size = 2081643;

        public static string Dir { get { return Path.Combine(Fetcher.CacheRoot, "dge-" + Tag); } }
        public static string ExePath { get { return Path.Combine(Dir, Exe); } }
        public static bool Ready { get { return Fetcher.CacheValid(Dir, Exe); } }   // the cached exe must still match the hash written when it was installed

        internal static bool RuntimeOk()
        {
            foreach (string pf in new string[] { Environment.GetEnvironmentVariable("ProgramW6432"), Environment.GetEnvironmentVariable("ProgramFiles"), Environment.GetEnvironmentVariable("ProgramFiles(x86)") })
            {
                if (string.IsNullOrEmpty(pf)) continue;
                try { string d = Path.Combine(pf, @"dotnet\shared\Microsoft.WindowsDesktop.App"); if (Directory.Exists(d)) foreach (string v in Directory.GetDirectories(d)) { int mj; string nm = Path.GetFileName(v); int dot = nm.IndexOf('.'); if (dot > 0 && int.TryParse(nm.Substring(0, dot), out mj) && mj >= 8) return true; } } catch { }
            }
            return false;
        }

        // returns an error text, or null when started
        public static string Run(IWin32Window owner, string gameDir)
        {
            if (Environment.OSVersion.Version.Major < 10) return U.R("Эта программа собрана под .NET 8 и работает только на Windows 10 и новее.", "This tool is built for .NET 8 and runs on Windows 10 and newer only.");
            if (!Ready)
            {
                string q = U.R("Скачать «Divinity Graphics Extender» " + Tag + " (" + (Size / 1048576.0).ToString("0.0") + " МБ) с GitHub автора (" + Author + ")?\\n\\n" + Repo + "\\n\\nПрограмма не наша: мы её не храним и не меняем. Проверяется контрольная сумма файла.",
                               "Download “Divinity Graphics Extender” " + Tag + " (" + (Size / 1048576.0).ToString("0.0") + " MB) from the author's (" + Author + ") GitHub?\\n\\n" + Repo + "\\n\\nThe tool is not ours: we neither host nor modify it. The file checksum is verified.").Replace("\\n", "\n");
                if (MessageBox.Show(owner, q, "Divinity Graphics Extender", MessageBoxButtons.OKCancel, MessageBoxIcon.Question) != DialogResult.OK) return "";
                string err = Download(owner); if (err != null) return err.Length == 0 ? "" : U.R("Не удалось скачать: ", "Download failed: ") + err;
            }
            if (!RuntimeOk())
            {
                if (MessageBox.Show(owner, U.R("Для запуска нужен «.NET Desktop Runtime» версии 8 или новее (x64). Открыть страницу загрузки Microsoft?", "The “.NET Desktop Runtime” 8 or newer (x64) is required. Open the Microsoft download page?"), "Divinity Graphics Extender", MessageBoxButtons.OKCancel, MessageBoxIcon.Information) == DialogResult.OK) U.Open("https://dotnet.microsoft.com/download/dotnet/8.0");
                return "";
            }
            try { ProcessStartInfo psi = new ProcessStartInfo(ExePath); psi.WorkingDirectory = Dir; psi.UseShellExecute = false; psi.EnvironmentVariables["DOTNET_ROLL_FORWARD"] = "Major"; if (!string.IsNullOrEmpty(gameDir)) psi.EnvironmentVariables["DD_GAME_DIR"] = gameDir; Process.Start(psi); return null; }
            catch (Exception ex) { return ex.Message; }
        }

        public static string Fetch() { return Download(null); }
        static string Download(IWin32Window owner)
        {
            return Fetcher.Install(owner, "Divinity Graphics Extender", Url, Sha256, Size, Dir, Exe, delegate(FileStream fs, string tmp, string stage)
            {
                byte[] data = new byte[fs.Length]; fs.Position = 0; int off = 0, r; while (off < data.Length && (r = fs.Read(data, off, data.Length - off)) > 0) off += r;   // the verified, write-locked bytes
                Unzip(data, stage); return null;
            });
        }

        // minimal zip reader (stored / deflate), no external libraries (.NET 3.5)
        static void Unzip(byte[] z, string dest)
        {
            int eocd = -1; for (int i = z.Length - 22; i >= 0 && i > z.Length - 70000; i--) if (z[i] == 0x50 && z[i + 1] == 0x4b && z[i + 2] == 5 && z[i + 3] == 6) { eocd = i; break; }
            if (eocd < 0) throw new InvalidDataException("not a zip");
            int n = BitConverter.ToUInt16(z, eocd + 10), p = BitConverter.ToInt32(z, eocd + 16); string root = Path.GetFullPath(dest) + Path.DirectorySeparatorChar; long sum = 0;
            for (int e = 0; e < n; e++)
            {
                int method = BitConverter.ToUInt16(z, p + 10), csize = BitConverter.ToInt32(z, p + 20), usize = BitConverter.ToInt32(z, p + 24), nl = BitConverter.ToUInt16(z, p + 28), xl = BitConverter.ToUInt16(z, p + 30), cl = BitConverter.ToUInt16(z, p + 32), lho = BitConverter.ToInt32(z, p + 42);
                string name = Encoding.UTF8.GetString(z, p + 46, nl).Replace('/', '\\'); p += 46 + nl + xl + cl;
                if (name.EndsWith("\\")) continue;
                if (usize < 0 || usize > 300000000 || (sum += usize) > 600000000) throw new InvalidDataException("zip too large");   // zip-bomb guard
                string full = Path.GetFullPath(Path.Combine(dest, name)); if (!full.StartsWith(root, StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("bad path in zip");
                int ds = lho + 30 + BitConverter.ToUInt16(z, lho + 26) + BitConverter.ToUInt16(z, lho + 28); Directory.CreateDirectory(Path.GetDirectoryName(full)); byte[] outb = new byte[usize];
                if (method == 0) Array.Copy(z, ds, outb, 0, usize);
                else if (method == 8) { using (DeflateStream d = new DeflateStream(new MemoryStream(z, ds, csize), CompressionMode.Decompress)) { int off = 0; while (off < usize) { int r = d.Read(outb, off, usize - off); if (r <= 0) break; off += r; } if (off != usize) throw new InvalidDataException("short entry"); } }
                else throw new InvalidDataException("unsupported zip method");
                File.WriteAllBytes(full, outb);
            }
        }
    }
}
