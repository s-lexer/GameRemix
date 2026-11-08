// Self-update of the program: periodic check, "what's new", one-click install.
//   latest.txt (one line):  <version>|<https url of the exe>|<sha256 of the exe>      (the old form "<version>|<url>" is still read, but is NEVER installed: no checksum)
//   changelog.<ru|en>.txt next to latest.txt: same format as src/changelog.*.txt.
// Install = download to <exe>.new (https + trusted host, size limit, streaming SHA-256) -> compare with latest.txt -> Authenticode (WinVerifyTrust) + same publisher as the
// running program -> rename the running exe to <exe>.old, put the new one in its place -> start it, quit. Any failure puts <exe>.old back. The new instance deletes .old.
// The exe that is replaced is the file the USER started (OGF_STUB, the single-file launcher), else the running exe.
// Tests: OGF_UPDATE_URL points latest.txt at a local server (plain http to 127.0.0.1 is accepted ONLY then). OGF_TEST_ALLOW_UNSIGNED=1 skips the signature step, and only when
// (a) OGF_UPDATE_URL is a loopback address AND (b) the running program carries NO Authenticode signature at all. A signed (release) build ignores it completely.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Runtime.InteropServices;
using System.Security.Cryptography.X509Certificates;
using System.Text;
using System.Threading;
using System.Windows.Forms;

namespace DDFixTool
{
    class UpdateInfo
    {
        public string Version, Url, Sha256;   // Url/Sha256 may be null (old latest.txt)
        public bool CanInstall { get { return Url != null && Sha256 != null; } }
        public string ManualUrl { get { return Url ?? Updater.SitePage; } }
    }

    static class Updater
    {
        public const string SitePage = "https://gameremix.pro/";
        public const long MaxExe = 64L * 1024 * 1024;
        public static string UpdateUrl { get { string o = Environment.GetEnvironmentVariable("OGF_UPDATE_URL"); return !string.IsNullOrEmpty(o) ? o : App.UpdateUrl; } }
        static bool TestServer { get { string o = Environment.GetEnvironmentVariable("OGF_UPDATE_URL"); if (string.IsNullOrEmpty(o)) return false; try { return new Uri(o).IsLoopback; } catch { return false; } } }

        // ---- latest.txt ---------------------------------------------------------------------------------------------
        // null = not a valid update line (HTML of a captive portal, an error page, a foreign host...)
        public static UpdateInfo Parse(string text)
        {
            if (text == null) return null; string t = text.Trim(); if (t.Length == 0 || t.IndexOf('\n') >= 0 || t.IndexOf('\r') >= 0) return null;
            string[] p = t.Split('|'); if (p.Length > 3 || !App.ValidVersion(p[0].Trim())) return null;
            UpdateInfo u = new UpdateInfo(); u.Version = p[0].Trim();
            if (p.Length >= 2 && p[1].Trim().Length > 0) { u.Url = p[1].Trim(); if (!Net.TrustedUpdateUrl(u.Url)) return null; }
            if (p.Length == 3) { string h = p[2].Trim().ToLowerInvariant(); if (!System.Text.RegularExpressions.Regex.IsMatch(h, "^[0-9a-f]{64}$")) return null; u.Sha256 = h; }
            return u;
        }
        // newer version -> info; same/older -> null with err == null; trouble -> null with err
        // second address when the main site does not answer: the mirror (same format, same checks). Tests: OGF_UPDATE_URL2 (loopback only).
        public const string MirrorUrl = "https://gameremix.speectra.com/dl/latest.txt";
        static string usedUrl;   // the address that answered (the change log is taken from the same place)
        static string[] Sources()
        {
            string o = Environment.GetEnvironmentVariable("OGF_UPDATE_URL");
            if (!string.IsNullOrEmpty(o)) { string o2 = Environment.GetEnvironmentVariable("OGF_UPDATE_URL2"); return string.IsNullOrEmpty(o2) || !TestServer ? new string[] { o } : new string[] { o, o2 }; }
            return new string[] { App.UpdateUrl, MirrorUrl };
        }
        public static UpdateInfo Check(out string err, out bool bad)
        {
            err = null; bad = false; UpdateInfo found = null; string lastErr = null; bool lastBad = false;
            foreach (string src in Sources())
            {
                string res;
                try { string tls = Net.Tls(); if (tls != null) throw new Exception(tls); res = Net.GetString(src, 1024, 15000); }
                catch (Exception ex) { lastErr = ex.Message; lastBad = false; continue; }   // main site down -> the mirror
                UpdateInfo u = Parse(res); if (u == null) { lastBad = true; lastErr = null; continue; }
                usedUrl = src; return App.Newer(u.Version, App.Version) ? u : null;   // an older or equal version is never offered
            }
            err = lastErr; bad = lastBad && lastErr == null; return found;
        }
        // "what's new" of the offered version from the site; null when there is none
        public static string FetchChangelog(bool ru)
        {
            try { string b = usedUrl ?? UpdateUrl; b = b.Substring(0, b.LastIndexOf('/') + 1); string s = Net.GetString(b + "changelog." + (ru ? "ru" : "en") + ".txt", 200000, 15000); return Changelog.Versions(s).Count > 0 ? s : null; }
            catch { return null; }
        }

        // ---- which file is replaced -----------------------------------------------------------------------------------
        public static string TargetExe()
        {
            string o = Environment.GetEnvironmentVariable("OGF_UPDATE_TARGET"); if (TestServer && !string.IsNullOrEmpty(o)) return o;   // tests only (and only with a local server)
            string s = Environment.GetEnvironmentVariable("OGF_STUB"); if (!string.IsNullOrEmpty(s) && File.Exists(s)) return s;
            return Application.ExecutablePath;
        }
        // the same file on the other host (main <-> mirror; both hold dl/GameRemix-<ver>.exe), null = there is none. Tests: OGF_UPDATE_URL2 (loopback only), same file name.
        public static string AltUrl(string url)
        {
            try
            {
                if (TestServer)
                {
                    string o2 = Environment.GetEnvironmentVariable("OGF_UPDATE_URL2"); if (string.IsNullOrEmpty(o2) || !new Uri(o2).IsLoopback) return null;
                    string r = o2.Substring(0, o2.LastIndexOf('/') + 1) + url.Substring(url.LastIndexOf('/') + 1); return r == url ? null : r;
                }
                Uri u = new Uri(url); string h = u.Host.ToLowerInvariant();
                if (h == "gameremix.pro") return "https://gameremix.speectra.com" + u.AbsolutePath;
                if (h == "gameremix.speectra.com") return "https://gameremix.pro" + u.AbsolutePath;
            }
            catch { }
            return null;
        }
        public static void Cleanup()   // the new instance removes what the update left (the previous exe is still closing for a moment)
        {
            string t = TargetExe();
            Thread th = new Thread(delegate()
            {
                for (int i = 0; i < 15; i++)
                {
                    bool left = false;
                    foreach (string f in new string[] { t + ".old", t + ".new" }) { try { if (File.Exists(f)) { File.Delete(f); } } catch { left = true; } }
                    if (!left) return; Thread.Sleep(1000);
                }
            }); th.IsBackground = true; th.Start();
        }

        // ---- Authenticode -----------------------------------------------------------------------------------------
        [StructLayout(LayoutKind.Sequential)] struct WtFile { public int cb; public IntPtr path; public IntPtr hFile; public IntPtr known; }
        [StructLayout(LayoutKind.Sequential)] struct WtData { public int cb; public IntPtr policy, sip; public int ui, revoke, union; public IntPtr file; public int state; public IntPtr hState, url; public int flags, uiCtx; }
        [DllImport("wintrust.dll", CharSet = CharSet.Unicode)] static extern int WinVerifyTrust(IntPtr hwnd, ref Guid action, IntPtr data);
        // 0 = the signature is valid and trusted by Windows; otherwise the HRESULT
        public static int WinTrust(string file)
        {
            Guid action = new Guid("00AAC56B-CD44-11d0-8CC2-00C04FC295EE");   // WINTRUST_ACTION_GENERIC_VERIFY_V2
            IntPtr pp = Marshal.StringToHGlobalUni(Path.GetFullPath(file)), pf = IntPtr.Zero, pd = IntPtr.Zero;
            try
            {
                WtFile fi = new WtFile(); fi.cb = Marshal.SizeOf(typeof(WtFile)); fi.path = pp;
                pf = Marshal.AllocHGlobal(Marshal.SizeOf(typeof(WtFile))); Marshal.StructureToPtr(fi, pf, false);
                WtData d = new WtData(); d.cb = Marshal.SizeOf(typeof(WtData)); d.ui = 2; d.union = 1; d.file = pf; d.revoke = 0;   // UI none, file, no revocation lookup (an offline PC must still verify)
                pd = Marshal.AllocHGlobal(Marshal.SizeOf(typeof(WtData))); Marshal.StructureToPtr(d, pd, false);
                return WinVerifyTrust(new IntPtr(-1), ref action, pd);
            }
            finally { Marshal.FreeHGlobal(pp); if (pf != IntPtr.Zero) Marshal.FreeHGlobal(pf); if (pd != IntPtr.Zero) Marshal.FreeHGlobal(pd); }
        }
        // subject of the signing certificate embedded in the file (null = not signed); says nothing about trust - WinTrust does
        public static string Signer(string file)
        {
            try { X509Certificate c = X509Certificate.CreateFromSignedFile(file); return c == null ? null : c.Subject; } catch { return null; }
        }
        // null = fine, else the reason. `cur` = the program being replaced.
        public static string CheckSignature(string newFile, string cur, out bool skipped)
        {
            skipped = false; string me = Signer(cur);
            if (me == null)
            {
                if (Environment.GetEnvironmentVariable("OGF_TEST_ALLOW_UNSIGNED") == "1" && TestServer) { skipped = true; return null; }   // test build + local test server only
                return U.R("Установка отменена: текущая программа не подписана (отладочная сборка), издателя обновления сравнить не с чем.", "Install cancelled: the running program is not signed (a debug build), so there is nothing to compare the publisher with.");
            }
            int rc = WinTrust(newFile);
            if (rc != 0)
            {
                bool sha2 = (uint)rc == 0x80096010 || (uint)rc == 0x800B0109 || (uint)rc == 0x80092026 || (uint)rc == 0x800B0004;   // Windows 7 without SHA-256 signature support
                return U.R("Подпись нового файла не прошла проверку Windows (код 0x" + rc.ToString("X8") + ")." + (sha2 ? " Если у вас Windows 7, установите обновление Windows KB4474419 (поддержка подписей SHA-256) и повторите." : ""),
                           "The signature of the new file failed the Windows check (code 0x" + rc.ToString("X8") + ")." + (sha2 ? " On Windows 7 install Windows update KB4474419 (SHA-256 signature support) and try again." : ""));
            }
            string ns = Signer(newFile);
            if (ns == null || !string.Equals(ns, me, StringComparison.OrdinalIgnoreCase)) return U.R("Издатель нового файла не совпадает с издателем программы.", "The publisher of the new file differs from the program's publisher.");
            return null;
        }

        // ---- install ---------------------------------------------------------------------------------------------
        static void Require(string reason, string en) { throw new WebException(U.R(reason, en)); }
        // returns null when the exe at `target` has been replaced (the caller restarts it); throws with a readable message otherwise. elevate: ask UAC when the folder is protected.
        public static void Install(UpdateInfo info, string target, bool elevate, Func<bool> cancelled, Action<string, long, long> progress)
        {
            if (info == null || !info.CanInstall) Require("Установка невозможна: в списке версий нет контрольной суммы. Скачайте файл вручную.", "Cannot install: the version list has no checksum. Download the file manually.");
            if (!Net.TrustedUpdateUrl(info.Url)) Require("Адрес обновления не из доверенного списка.", "The update address is not on the trusted list.");
            Mutex mx = new Mutex(false, "Local\\GameRemix.Update");
            bool have = false; try { have = mx.WaitOne(0); } catch (AbandonedMutexException) { have = true; }
            if (!have) { mx.Close(); Require("Обновление уже выполняется.", "An update is already running."); }
            try
            {
                if (!File.Exists(target)) Require("Не найден файл программы для замены.", "The program file to replace was not found.");
                string sg0 = Signer(target);   // refuse early, before the download
                if (sg0 == null && !(Environment.GetEnvironmentVariable("OGF_TEST_ALLOW_UNSIGNED") == "1" && TestServer)) Require("Установка отменена: текущая программа не подписана (отладочная сборка).", "Install cancelled: the running program is not signed (a debug build).");
                string dir = Path.GetDirectoryName(Path.GetFullPath(target)), nw = target + ".new"; bool needElev = false;
                try { using (new FileStream(nw, FileMode.Create, FileAccess.Write, FileShare.None)) { } }
                catch (Exception ex) { when_ok(ex, ref needElev); }
                if (needElev)
                {
                    string stage = Path.Combine(App.LocalDir, "update"); Directory.CreateDirectory(stage); nw = Path.Combine(stage, "GameRemix-" + info.Version + ".exe.new");
                    if (!elevate) Require("Папка программы защищена от записи. Скачайте новую версию вручную: " + info.ManualUrl, "The program folder is write-protected. Download the new version manually: " + info.ManualUrl);
                }
                try
                {
                    // the main address first, then the same file on the other host (the main site answered latest.txt but may fail to serve the exe)
                    List<string> urls = new List<string>(); urls.Add(info.Url); string alt = AltUrl(info.Url); if (alt != null && Net.TrustedUpdateUrl(alt)) urls.Add(alt);
                    Exception lastEx = null; bool okDl = false;
                    foreach (string u in urls)
                    {
                        try
                        {
                            string got;
                            using (FileStream fs = new FileStream(nw, FileMode.Create, FileAccess.Write, FileShare.None))
                            {
                                if (progress != null) progress(U.R("Скачиваю версию ", "Downloading version ") + info.Version + "…", 0, 0);
                                got = Net.Download(u, fs, MaxExe, cancelled, delegate(long d, long t) { if (progress != null) progress(U.R("Скачиваю версию ", "Downloading version ") + info.Version + "…", d, t); }, Net.TrustedUpdateUrl);
                            }
                            if (!string.Equals(got, info.Sha256, StringComparison.OrdinalIgnoreCase)) Require("Контрольная сумма скачанного файла не совпала. Файл отклонён.", "The checksum of the downloaded file does not match. The file was rejected.");
                            okDl = true; break;
                        }
                        catch (CancelledEx) { throw; }
                        catch (Exception ex) { lastEx = ex; try { if (File.Exists(nw)) File.Delete(nw); } catch { } }
                    }
                    if (!okDl) throw lastEx;
                    VerifyNew(nw, info.Sha256, target);
                    if (progress != null) progress(U.R("Заменяю программу…", "Replacing the program…"), 0, 0);
                    if (!needElev) Swap(target, nw, info.Sha256);
                    else RunElevated(nw, target, info.Sha256);
                }
                catch { try { if (File.Exists(nw)) File.Delete(nw); } catch { } throw; }
            }
            finally { try { mx.ReleaseMutex(); } catch { } mx.Close(); }
        }
        static void when_ok(Exception ex, ref bool needElev)
        {
            if (ex is UnauthorizedAccessException) { needElev = true; return; }   // a protected folder (Program Files...); other trouble (disk full, antivirus) is not solved by UAC
            if (ex is IOException) throw new IOException(U.R("Не удалось записать файл обновления рядом с программой: ", "Could not write the update file next to the program: ") + ex.Message);
            throw ex;
        }
        // size, MZ header, hash of what is on disk NOW, signature
        public static void VerifyNew(string nw, string sha, string cur)
        {
            FileInfo fi = new FileInfo(nw); if (fi.Length < 65536 || fi.Length > MaxExe) Require("Скачанный файл не похож на программу (размер).", "The downloaded file does not look like the program (size).");
            using (FileStream fs = File.OpenRead(nw)) { if (fs.ReadByte() != 'M' || fs.ReadByte() != 'Z') Require("Скачанный файл не похож на программу.", "The downloaded file does not look like the program."); }
            if (!string.Equals(Net.Sha256File(nw), sha, StringComparison.OrdinalIgnoreCase)) Require("Скачанный файл изменился после проверки. Файл отклонён.", "The downloaded file changed after the check. It was rejected.");
            bool skipped; string e = CheckSignature(nw, cur, out skipped); if (e != null) throw new WebException(e);
        }
        // exe -> exe.old, new -> exe; anything wrong puts the old one back
        public static void Swap(string target, string nw, string sha)
        {
            string old = target + ".old";
            try { if (File.Exists(old)) File.Delete(old); } catch { Require("Не удалось убрать предыдущий " + Path.GetFileName(old) + ".", "Could not remove the previous " + Path.GetFileName(old) + "."); }
            File.Move(target, old);   // a running exe can be renamed
            try
            {
                File.Move(nw, target);
                if (TestServer && Environment.GetEnvironmentVariable("OGF_TEST_FAIL_AFTER_MOVE") == "1") throw new IOException("test: failure after the move");   // proves the rollback (tests only)
                if (!string.Equals(Net.Sha256File(target), sha, StringComparison.OrdinalIgnoreCase)) throw new IOException("the file in place differs");
            }
            catch (Exception ex)
            {
                try { if (File.Exists(target)) File.Delete(target); } catch { }
                try { File.Move(old, target); } catch (Exception ex2) { throw new IOException("rollback failed: " + ex2.Message + " (the previous program is " + old + ")"); }
                throw new IOException(U.R("Не удалось заменить программу, прежняя версия возвращена: ", "Could not replace the program, the previous version was put back: ") + ex.Message);
            }
        }
        static void RunElevated(string nw, string target, string sha)
        {
            ProcessStartInfo psi = new ProcessStartInfo(Application.ExecutablePath, "--apply-update \"" + nw + "\" \"" + target + "\" " + sha); psi.UseShellExecute = true; psi.Verb = "runas";
            Process p;
            try { p = Process.Start(psi); }
            catch (System.ComponentModel.Win32Exception ex) { if (ex.NativeErrorCode == 1223) Require("Запрос прав администратора отклонён.", "The administrator prompt was declined."); throw; }
            p.WaitForExit();
            if (p.ExitCode != 0) throw new IOException(U.R("Замена с правами администратора не удалась (код " + p.ExitCode + ").", "The replacement with administrator rights failed (code " + p.ExitCode + ")."));
        }
        // start the new copy of the program; the caller quits right after
        public static void Restart(string target)
        {
            ProcessStartInfo psi = new ProcessStartInfo(target); psi.UseShellExecute = false; psi.WorkingDirectory = Path.GetDirectoryName(Path.GetFullPath(target));
            Process.Start(psi);
        }

        // ---- "what's new" for an interval of versions ------------------------------------------------------------------
        // sections "## v" with from < v <= to
        public static string Slice(string text, string from, string to)
        {
            StringBuilder sb = new StringBuilder(); bool keep = false;
            foreach (string raw in (text ?? "").Replace("\r", "").Split('\n'))
            {
                if (raw.StartsWith("## "))
                {
                    string v = raw.Substring(3).Trim(); int i = v.IndexOfAny(new char[] { ' ', '—' }); if (i > 0) v = v.Substring(0, i);
                    keep = App.ValidVersion(v) && (from == null || App.Newer(v, from)) && (to == null || !App.Newer(v, to));
                }
                if (keep) sb.Append(raw).Append('\n');
            }
            return sb.ToString();
        }
        // "What's new" is never opened by itself. The button shows how many versions of the log the user has not looked at yet (a fresh install: none).
        // The last version looked at is "seenver" in settings.ini; opening the log sets it to the current version.
        public static int UnseenCount()
        {
            string seen = App.Get("seenver");
            if (seen == null && App.Get("migrated") == "1") seen = "1.0.9";   // data came from OldGameFixer = the user had 1.0.9 (it did not write seenver): this is an update, not a fresh install
            if (seen == null) { App.Set("seenver", App.Version); return 0; }
            int n = 0;
            foreach (string v in Changelog.Versions(Changelog.Text(L.Ru))) if (App.ValidVersion(v) && App.Newer(v, seen) && !App.Newer(v, App.Version)) n++;
            return n;
        }
        public static void MarkSeen() { if (App.Get("seenver") != App.Version) App.Set("seenver", App.Version); }

        // ---- command line (tests and scripts) ------------------------------------------------------------------------------
        // --data-info [--game DIR] | --verify-sig FILE [--against FILE] | --update-check | --update-install [--target FILE] [--no-restart] | --apply-update NEW TARGET SHA
        static StringBuilder outSb = new StringBuilder(); static void Out(string t) { outSb.AppendLine(t); }
        public static int Cli(string[] a0)
        {
            string logf = null; List<string> al = new List<string>();
            for (int i = 0; i < a0.Length; i++) { if (a0[i] == "--log" && i + 1 < a0.Length) logf = a0[++i]; else if (a0[i] == "--lang" && i + 1 < a0.Length) { L.Ru = a0[++i] == "ru"; } else al.Add(a0[i]); }
            int rc = CliRun(al.ToArray());
            if (logf != null) { try { File.WriteAllText(logf, outSb.ToString(), new UTF8Encoding(true)); } catch { } }
            return rc;
        }
        static int CliRun(string[] a)
        {
            string c = a[0];
            if (c == "--unseen") { int n = UnseenCount(); Out("UNSEEN " + n); if (a.Length > 1 && a[1] == "--mark") { MarkSeen(); Out("UNSEEN-AFTER-OPEN " + UnseenCount()); } return 0; }
            if (c == "--version") { Out("VERSION " + App.Version); Console.Out.Write(App.Version); return 0; }   // deploy.sh compares this with the version it is about to publish
            if (c == "--data-info")
            {
                string d = App.DataDir, l = App.LocalDir; Out("DATA " + d); Out("LOCAL " + l); Out("MIGRATION " + (Migrate.Status.Length > 0 ? Migrate.Status : "none"));
                for (int i = 1; i + 1 < a.Length; i++) if (a[i] == "--game") { Core g = new Core(a[i + 1]); Out("SHORTCUT-REPAIRED " + g.RepairShortcut()); }
                return 0;
            }
            if (c == "--verify-sig")
            {
                if (a.Length < 2) { Out("ERROR --verify-sig FILE"); return 2; }
                int rc = WinTrust(a[1]); string s = Signer(a[1]); Out("TRUST " + (rc == 0 ? "ok" : "0x" + rc.ToString("X8"))); Out("SIGNER " + (s ?? "none"));
                if (a.Length >= 4 && a[2] == "--against") { string e = CheckSignature(a[1], a[3], out _skip); Out("PUBLISHER " + (e == null ? (_skip ? "skipped-test" : "same") : "REFUSED " + e)); }
                return 0;
            }
            if (c == "--apply-update")   // run elevated by Install: a[1]=new file, a[2]=target, a[3]=sha256
            {
                try { if (a.Length < 4) return 2; VerifyNew(a[1], a[3], a[2]); Swap(a[2], a[1], a[3]); return 0; } catch (Exception ex) { try { File.AppendAllText(Path.Combine(App.DataDir, "log.txt"), DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + "   apply-update: " + ex.Message + "\r\n", Encoding.UTF8); } catch { } return 1; }
            }
            if (c == "--update-check" || c == "--update-install")
            {
                string err; bool bad; UpdateInfo u = Check(out err, out bad);
                if (err != null) { Out("UPDATE error=" + err); return 1; }
                if (bad) { Out("UPDATE bad-answer"); return 1; }
                if (u == null) { Out("UPDATE none"); return 2; }
                Out("UPDATE available version=" + u.Version + " url=" + (u.Url ?? "-") + " sha256=" + (u.Sha256 ?? "-") + " install=" + (u.CanInstall ? "yes" : "no"));
                if (c == "--update-check") return 0;
                string target = null; bool noRestart = false;
                for (int i = 1; i < a.Length; i++) { if (a[i] == "--target" && i + 1 < a.Length) target = a[++i]; else if (a[i] == "--no-restart") noRestart = true; }
                if (target != null) Environment.SetEnvironmentVariable("OGF_UPDATE_TARGET", target);
                try { Install(u, TargetExe(), false, null, null); Out("UPDATE installed target=" + TargetExe()); if (!noRestart) Restart(TargetExe()); return 0; }
                catch (Exception ex) { Out("UPDATE failed: " + ex.Message); return 1; }
            }
            return 2;
        }
        static bool _skip;
    }

    // "Update available" window: what's new in that version + Update / Later / manual download. The install runs in a progress window.
    class UpdateForm : Form
    {
        delegate void AddFn(string x, Color c, float pt, FontStyle st, int ind);
        public bool Installed; bool autoRun;
        public UpdateForm(UpdateInfo info) : this(info, false) { }
        public UpdateForm(UpdateInfo info, bool auto)
        {
            autoRun = auto;
            Text = U.R("Обновление", "Update"); FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false; MinimizeBox = false; ShowInTaskbar = false;
            Rectangle wa = Screen.PrimaryScreen.WorkingArea; int h = Math.Min(560, Math.Max(380, wa.Height - 90));
            StartPosition = FormStartPosition.CenterParent; ClientSize = new Size(560, h); BackColor = Th.Bg; ForeColor = Th.Text; Font = Th.Body;
            Label t = new Label(); t.AutoSize = false; t.SetBounds(24, 18, 512, 26); t.Font = Th.F("Segoe UI Semibold", 13f, FontStyle.Regular); t.ForeColor = Th.Text; t.UseMnemonic = false;
            t.Text = U.R("Доступна версия ", "Version available: ") + info.Version;
            Label s = new Label(); s.AutoSize = false; s.SetBounds(24, 46, 512, 18); s.Font = Th.F("Segoe UI", 9f, FontStyle.Regular); s.ForeColor = Th.Muted; s.UseMnemonic = false;
            s.Text = U.R("У вас ", "You have ") + App.Version + (info.CanInstall ? "" : U.R(" · автоматическая установка недоступна для этой версии", " · automatic install is not available for this version"));
            RichTextBox rt = new RichTextBox(); rt.BorderStyle = BorderStyle.None; rt.BackColor = Th.Surf; rt.ForeColor = Th.Text; rt.ReadOnly = true; rt.DetectUrls = false; rt.ScrollBars = RichTextBoxScrollBars.Vertical; rt.SetBounds(24, 76, 512, h - 76 - 20 - 40 - 12 - 40 - 12);
            rt.Font = Th.F("Segoe UI", 9.5f, FontStyle.Regular); rt.Cursor = Cursors.Default;
            AddFn add = delegate(string x, Color c, float pt, FontStyle st, int ind) { rt.SelectionStart = rt.TextLength; rt.SelectionLength = 0; rt.SelectionColor = c; rt.SelectionFont = Th.F("Segoe UI", pt, st); rt.SelectionIndent = ind; rt.SelectionHangingIndent = ind; rt.SelectedText = x + "\n"; };
            add(U.R("Что нового", "What's new"), Th.Faint, 9f, FontStyle.Regular, 0); add(U.R("Загружаю описание…", "Loading the description…"), Th.Muted, 9.5f, FontStyle.Regular, 0);
            Btn up = new Btn(); up.Accent = true; up.Text = info.CanInstall ? U.R("Обновить", "Update") : U.R("Скачать вручную", "Download manually"); up.SetBounds(24, h - 20 - 40 - 12 - 40, 512, 40);
            Btn lt = new Btn(); lt.Text = U.R("Позже", "Later"); lt.SetBounds(24, h - 20 - 40, 512, 40); lt.Click += delegate { Close(); };
            EventHandler go = delegate
            {
                if (!info.CanInstall) { U.Open(info.ManualUrl); Close(); return; }
                up.Enabled = false; lt.Enabled = false;
                string target = Updater.TargetExe(); bool el = !autoRun; autoRun = false;   // the automatic run at start-up never raises a UAC prompt by itself: it shows the window with the button instead
                string err = WorkForm.Run(this, U.R("Обновление", "Update"), U.R("Подготовка…", "Preparing…"), true, delegate(WorkForm w) { Updater.Install(info, target, el, delegate { return w.Cancelled; }, delegate(string txt, long d, long tot) { w.Report(txt, d, tot); }); });
                if (err == null) { Installed = true; DialogResult = DialogResult.OK; Close(); return; }
                up.Enabled = true; lt.Enabled = true;
                if (err.Length > 0) MessageBox.Show(this, err + "\n\n" + U.R("Можно скачать файл вручную: ", "You can download the file manually: ") + info.ManualUrl, L.T("errTitle"), MessageBoxButtons.OK, MessageBoxIcon.Warning);
            };
            up.Click += go;
            Controls.AddRange(new Control[] { t, s, rt, up, lt }); KeyPreview = true; KeyDown += delegate(object sk, KeyEventArgs e) { if (e.KeyCode == Keys.Escape && lt.Enabled) Close(); };
            ActiveControl = up; Dark.Scroll(rt);
            Shown += delegate
            {
                if (auto && info.CanInstall) BeginInvoke((MethodInvoker)delegate { go(up, EventArgs.Empty); });
                Thread th = new Thread(delegate()
                {
                    string txt = Updater.FetchChangelog(L.Ru); string sl = txt == null ? null : Updater.Slice(txt, App.Version, info.Version);
                    try
                    {
                        BeginInvoke((MethodInvoker)delegate
                        {
                            rt.Clear(); add(U.R("Что нового", "What's new"), Th.Faint, 9f, FontStyle.Regular, 0);
                            if (string.IsNullOrEmpty(sl) || Changelog.Versions(sl).Count == 0) { add(U.R("Описание изменений для этой версии не опубликовано.", "No change description is published for this version."), Th.Muted, 9.5f, FontStyle.Regular, 0); return; }
                            foreach (string raw in sl.Replace("\r", "").Split('\n'))
                            {
                                string ln = raw.TrimEnd(); if (ln.Length == 0 || ln.StartsWith("# ")) continue;
                                if (ln.StartsWith("## ")) add("\n" + ln.Substring(3), Th.Amber, 12f, FontStyle.Bold, 0);
                                else if (ln.StartsWith("### ")) add(ln.Substring(4), Th.Green, 10f, FontStyle.Bold, 0);
                                else if (ln.StartsWith("- ")) add("•  " + ln.Substring(2), Th.Text, 9.5f, FontStyle.Regular, 14);
                            }
                            rt.SelectionStart = 0; rt.SelectionLength = 0;
                        });
                    }
                    catch { }
                }); th.IsBackground = true; th.Start();
            };
        }
        protected override void OnHandleCreated(EventArgs e) { base.OnHandleCreated(e); Dark.Apply(Handle); }
    }
}
