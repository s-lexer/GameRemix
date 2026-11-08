// Network + long-job helpers shared by every tool: TLS 1.2 only, https only (no downgrade through redirects), timeouts, size limits,
// streaming download with a running SHA-256, and WorkForm - a small modal "please wait" window that runs a job off the UI thread (progress + Cancel).
using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
using System.Net;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Windows.Forms;

namespace DDFixTool
{
    class CancelledEx : Exception { public CancelledEx() : base("cancelled") { } }

    static class Net
    {
        static string tlsErr; static bool tlsDone;
        // only TLS 1.2 (3072). Returns null when it is on, else a human-readable reason (never silently falls back to SSL3/TLS 1.0).
        public static string Tls()
        {
            if (tlsDone) return tlsErr;
            try
            {
                ServicePointManager.SecurityProtocol = (SecurityProtocolType)3072; ServicePointManager.DefaultConnectionLimit = 8;
                if (((int)ServicePointManager.SecurityProtocol & 3072) == 0) throw new NotSupportedException();
                tlsErr = null;
            }
            catch (Exception) { tlsErr = U.R("Не удаётся включить защищённое соединение TLS 1.2. На Windows 7 нужны обновление KB3140245 и .NET Framework 4.5 или новее.", "Cannot enable the secure TLS 1.2 connection. Windows 7 needs update KB3140245 and .NET Framework 4.5 or newer."); }
            tlsDone = true; return tlsErr;
        }

        public static HttpWebRequest Req(string url, string method, int timeoutMs)
        {
            Uri u = new Uri(url); if (u.Scheme != Uri.UriSchemeHttps && !LoopbackTestHttp(u)) throw new WebException(U.R("Разрешены только адреса https: ", "Only https addresses are allowed: ") + url);
            HttpWebRequest r = (HttpWebRequest)WebRequest.Create(u); r.Method = method; r.AllowAutoRedirect = false; r.KeepAlive = false; r.Timeout = timeoutMs; r.ReadWriteTimeout = timeoutMs; r.UserAgent = "GameRemix/" + App.Version;
            if (LoopbackTestHttp(u)) r.Proxy = null;
            else if (r.Proxy != null) r.Proxy.Credentials = CredentialCache.DefaultCredentials;   // corporate proxy that wants the Windows sign-in (407)   // the local test server is never sent through a system proxy
            r.CachePolicy = new System.Net.Cache.HttpRequestCachePolicy(System.Net.Cache.HttpRequestCacheLevel.BypassCache);   // never from / into the WinINet cache (the server sends "expires max"; downloads are hundreds of MB)
            return r;
        }
        // self-tests only: plain http to 127.0.0.1, and only while OGF_ASSETS_URL points the asset-set catalog at a local test server
        public static bool LoopbackTestHttp(Uri u) { return u.Scheme == Uri.UriSchemeHttp && u.IsLoopback && (!string.IsNullOrEmpty(Environment.GetEnvironmentVariable("OGF_ASSETS_URL")) || !string.IsNullOrEmpty(Environment.GetEnvironmentVariable("OGF_UPDATE_URL"))); }

        // GET that can start in the middle of a file (HTTP Range). Same redirect rules as Get. 200 = the whole body, 206 = from "from". 416 -> null (the range is not valid any more).
        public static HttpWebResponse GetFrom(string url, long from, int timeoutMs)
        {
            string err = Tls(); if (err != null) throw new WebException(err);
            for (int hop = 0; hop < 6; hop++)
            {
                HttpWebRequest rq = Req(url, "GET", timeoutMs); if (from > 0) rq.AddRange((int)from);   // .NET 3.5: int offsets (our files are below 2 GB)
                HttpWebResponse rs;
                try { rs = (HttpWebResponse)rq.GetResponse(); }
                catch (WebException ex) { HttpWebResponse er = ex.Response as HttpWebResponse; if (er != null && (int)er.StatusCode == 416) { er.Close(); return null; } if (er != null) er.Close(); throw; }   // an unclosed error response keeps one of the 2 connections per host busy
                int c = (int)rs.StatusCode;
                if (c >= 300 && c < 400)
                {
                    string loc = rs.Headers["Location"]; rs.Close();
                    if (string.IsNullOrEmpty(loc)) throw new WebException(U.R("Пустое перенаправление.", "Empty redirect."));
                    url = new Uri(new Uri(url), loc).AbsoluteUri; continue;
                }
                if (c != 200 && c != 206) { rs.Close(); throw new WebException("HTTP " + c); }
                return rs;
            }
            throw new WebException(U.R("Слишком много перенаправлений.", "Too many redirects."));
        }

        // Downloads exactly `expected` bytes into `part`, continuing a partial file left by an earlier attempt. On a dropped connection the partial file STAYS (the next call resumes it)
        // and an exception is thrown; the caller checks the hash of the finished file. Retries a few times while each attempt makes progress.
        public static void DownloadResume(string url, string part, long expected, Func<bool> cancelled, Action<long, long> progress)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(part));
            Exception last = null; long prev = -1;
            for (int attempt = 0; attempt < 5; attempt++)
            {
                long have = File.Exists(part) ? new FileInfo(part).Length : 0;
                if (have > expected) { File.Delete(part); have = 0; }
                if (have == expected) return;
                if (have <= prev) break;   // the last attempt got nowhere: give up, keep what there is
                prev = have;
                try
                {
                    using (HttpWebResponse rs = GetFrom(url, have, 30000))
                    {
                        if (rs == null) { File.Delete(part); prev = -1; continue; }   // 416: start over
                        int code = (int)rs.StatusCode; long from = have;
                        if (code == 200 && have > 0) from = 0;   // the server ignored the range: it sends everything again
                        if (code == 206)
                        {
                            string cr = rs.Headers["Content-Range"] ?? ""; System.Text.RegularExpressions.Match m = System.Text.RegularExpressions.Regex.Match(cr, @"^bytes\s+(\d+)-");
                            if (!m.Success || long.Parse(m.Groups[1].Value) != have) throw new WebException(U.R("Сервер вернул не тот фрагмент файла.", "The server returned the wrong part of the file."));
                        }
                        if (rs.ContentLength >= 0 && from + rs.ContentLength != expected) throw new WebException(U.R("Размер файла на сервере не совпал с манифестом.", "The file size on the server does not match the manifest."));
                        using (FileStream fs = new FileStream(part, from == 0 ? FileMode.Create : FileMode.Append, FileAccess.Write, FileShare.Read))
                        using (Stream s = rs.GetResponseStream())
                        {
                            byte[] buf = new byte[65536]; long total = from; int n;
                            while ((n = s.Read(buf, 0, buf.Length)) > 0)
                            {
                                if (cancelled != null && cancelled()) throw new CancelledEx();
                                total += n; if (total > expected) throw new WebException(U.R("Файл больше ожидаемого, загрузка отклонена.", "The file is larger than expected, download rejected."));
                                fs.Write(buf, 0, n); if (progress != null) progress(total, expected);
                            }
                            fs.Flush();
                        }
                    }
                }
                catch (CancelledEx) { throw; }
                catch (Exception ex) { last = ex; }
            }
            long got = File.Exists(part) ? new FileInfo(part).Length : 0;
            if (got != expected) throw new WebException(U.R("Загрузка прервана (получено ", "The download was interrupted (received ") + (got / 1048576.0).ToString("0.0") + U.R(" из ", " of ") + (expected / 1048576.0).ToString("0.0") + U.R(" МБ). Нажмите ещё раз — докачается с этого места.", " MB). Try again - it continues from here.") + (last != null ? " " + last.Message : ""));
        }

        // GET with manual redirects (max 5), every hop must stay on https
        public static HttpWebResponse Get(string url, int timeoutMs) { return Get(url, timeoutMs, null); }
        // allow: checked for the first address and for EVERY redirect hop (a download must not be bounced to a foreign host)
        public static HttpWebResponse Get(string url, int timeoutMs, Func<string, bool> allow)
        {
            string err = Tls(); if (err != null) throw new WebException(err);
            for (int hop = 0; hop < 6; hop++)
            {
                if (allow != null && !allow(url)) throw new WebException(U.R("Адрес не из доверенного списка: ", "The address is not on the trusted list: ") + url);
                HttpWebResponse rs;
                try { rs = (HttpWebResponse)Req(url, "GET", timeoutMs).GetResponse(); }
                catch (WebException ex) { if (ex.Response != null) ex.Response.Close(); throw; }
                int c = (int)rs.StatusCode;
                if (c >= 300 && c < 400)
                {
                    string loc = rs.Headers["Location"]; rs.Close();
                    if (string.IsNullOrEmpty(loc)) throw new WebException(U.R("Пустое перенаправление.", "Empty redirect."));
                    url = new Uri(new Uri(url), loc).AbsoluteUri; continue;
                }
                if (c != 200) { rs.Close(); throw new WebException("HTTP " + c); }
                return rs;
            }
            throw new WebException(U.R("Слишком много перенаправлений.", "Too many redirects."));
        }

        // small text answer (update line, server reply): size-capped
        public static string GetString(string url, int maxBytes, int timeoutMs)
        {
            using (HttpWebResponse rs = Get(url, timeoutMs)) return ReadCapped(rs, maxBytes);
        }
        public static string ReadCapped(WebResponse rs, int maxBytes)
        {
            if (rs.ContentLength > maxBytes) throw new WebException(U.R("Ответ сервера слишком большой.", "The server reply is too large."));
            using (Stream s = rs.GetResponseStream())
            {
                MemoryStream ms = new MemoryStream(); byte[] buf = new byte[4096]; int n;
                while ((n = s.Read(buf, 0, buf.Length)) > 0) { ms.Write(buf, 0, n); if (ms.Length > maxBytes) throw new WebException(U.R("Ответ сервера слишком большой.", "The server reply is too large.")); }
                return Encoding.UTF8.GetString(ms.ToArray());
            }
        }

        // streaming download into dst; returns the lowercase hex SHA-256 of what was written
        public static string Download(string url, Stream dst, long maxBytes, Func<bool> cancelled, Action<long, long> progress) { return Download(url, dst, maxBytes, cancelled, progress, null); }
        public static string Download(string url, Stream dst, long maxBytes, Func<bool> cancelled, Action<long, long> progress, Func<string, bool> allow)
        {
            using (HttpWebResponse rs = Get(url, 30000, allow))
            {
                long len = rs.ContentLength; if (len > maxBytes) throw new WebException(U.R("Файл больше ожидаемого, загрузка отклонена.", "The file is larger than expected, download rejected."));
                using (Stream s = rs.GetResponseStream())
                using (SHA256 h = SHA256.Create())
                {
                    byte[] buf = new byte[65536]; long total = 0; int n;
                    while ((n = s.Read(buf, 0, buf.Length)) > 0)
                    {
                        if (cancelled != null && cancelled()) throw new CancelledEx();
                        total += n; if (total > maxBytes) throw new WebException(U.R("Файл больше ожидаемого, загрузка отклонена.", "The file is larger than expected, download rejected."));
                        dst.Write(buf, 0, n); h.TransformBlock(buf, 0, n, null, 0); if (progress != null) progress(total, len);
                    }
                    if (len > 0 && total != len) throw new WebException(U.R("Файл скачан не полностью.", "The file was not downloaded completely."));
                    h.TransformFinalBlock(new byte[0], 0, 0); dst.Flush();
                    return Hex(h.Hash);
                }
            }
        }
        public static string Hex(byte[] b) { StringBuilder sb = new StringBuilder(); foreach (byte x in b) sb.Append(x.ToString("x2")); return sb.ToString(); }
        public static string Sha256File(string f) { using (FileStream fs = new FileStream(f, FileMode.Open, FileAccess.Read, FileShare.ReadWrite)) using (SHA256 h = SHA256.Create()) return Hex(h.ComputeHash(fs)); }
        public static string Sha256Bytes(byte[] b) { using (SHA256 h = SHA256.Create()) return Hex(h.ComputeHash(b)); }

        // our download hosts: gameremix.pro (main) and gameremix.speectra.com (mirror/reserve); the old oldgamefixer.speectra.com is NOT trusted
        // the list of trusted hosts (downloads, update line, asset sets). A new host (a mirror, a CDN domain) is added with AddTrustedHost - no other code changes.
        static readonly System.Collections.Generic.List<string> TrustedHosts = new System.Collections.Generic.List<string> { "gameremix.pro", "gameremix.speectra.com" };
        // hosts that may carry the PAYLOAD of an asset set (never the update line or manifests): every file is pinned by SHA-256 in the manifest, so a CDN is safe here
        static readonly string[] AssetHosts = { "github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com", "github-releases.githubusercontent.com" };
        public static bool AssetHost(string host) { string h = (host ?? "").ToLowerInvariant(); return TrustedHost(h) || Array.IndexOf(AssetHosts, h) >= 0; }
        public static bool TrustedHost(string host) { string h = (host ?? "").ToLowerInvariant(); lock (TrustedHosts) return TrustedHosts.Contains(h); }
        public static void AddTrustedHost(string host) { string h = (host ?? "").Trim().ToLowerInvariant(); if (h.Length == 0 || h.IndexOfAny(new char[] { '/', ':', ' ', '*' }) >= 0) throw new ArgumentException("host"); lock (TrustedHosts) if (!TrustedHosts.Contains(h)) TrustedHosts.Add(h); }

        // the update line "N.N.N|https://..." must be exactly that, and the address must belong to us
        public static bool TrustedUpdateUrl(string url)
        {
            try
            {
                Uri u = new Uri(url); if (LoopbackTestHttp(u)) return true; if (u.Scheme != Uri.UriSchemeHttps) return false; string h = u.Host.ToLowerInvariant();
                return TrustedHost(h);
            }
            catch { return false; }
        }
    }

    // third-party tools we may not redistribute (no licence): downloaded on request from the author's GitHub, SHA-256 pinned, cached under %LOCALAPPDATA%\GameRemix\cache.
    // The cache is trusted only while the extracted exe still matches the hash written at install time (.ogf-sha256) - otherwise it is fetched again.
    static class Fetcher
    {
        public static string CacheRoot { get { string o = Environment.GetEnvironmentVariable("OGF_CACHE"); return !string.IsNullOrEmpty(o) ? o : Path.Combine(App.LocalDir, "cache"); } }
        static string okKey, okVal;
        public static bool CacheValid(string dir, string exeName)
        {
            try
            {
                string ep = Path.Combine(dir, exeName), mf = Path.Combine(dir, ".ogf-sha256"); if (!File.Exists(ep) || !File.Exists(mf)) return false;
                FileInfo fi = new FileInfo(ep); string key = ep + "|" + fi.Length + "|" + fi.LastWriteTimeUtc.Ticks, want = File.ReadAllText(mf).Trim().ToLowerInvariant();
                if (okKey == key && okVal == want) return true;
                if (Net.Sha256File(ep) != want) return false;
                okKey = key; okVal = want; return true;
            }
            catch { return false; }
        }
        // extract: (verified download, still open and write-locked; the temp path; the empty staging folder) -> error text or null
        public static string Install(IWin32Window owner, string title, string url, string sha256, long approxSize, string dir, string exeName, Func<FileStream, string, string, string> extract)
        {
            return WorkForm.Run(owner, title, U.R("Загрузка… ", "Downloading… ") + title, true, delegate(WorkForm w)
            {
                string tlsErr = Net.Tls(); if (tlsErr != null) throw new Exception(tlsErr);
                string tmp = Path.Combine(Path.GetTempPath(), "ogf_dl_" + Guid.NewGuid().ToString("N") + ".bin"), stage = dir + ".tmp"; FileStream fs = null;
                try
                {
                    fs = new FileStream(tmp, FileMode.Create, FileAccess.ReadWrite, FileShare.Read);   // nobody can write into it while we verify and unpack it
                    string got = Net.Download(url, fs, approxSize * 12 / 10 + 1048576, delegate { return w.Cancelled; }, delegate(long d, long t) { w.Report(U.R("Загрузка… ", "Downloading… ") + (d / 1048576.0).ToString("0.0") + (t > 0 ? " / " + (t / 1048576.0).ToString("0.0") : "") + U.R(" МБ", " MB"), d, t); });
                    if (got != sha256) throw new Exception(U.R("Контрольная сумма файла не совпала, загрузка отклонена.", "The file checksum does not match, download rejected."));
                    w.Report(U.R("Распаковка…", "Unpacking…"), 0, 0);
                    if (Directory.Exists(stage)) Directory.Delete(stage, true);
                    Directory.CreateDirectory(stage);
                    string er = extract(fs, tmp, stage); if (er != null) throw new Exception(er);
                    string ep = Path.Combine(stage, exeName); if (!File.Exists(ep)) throw new Exception(U.R("В архиве не найден ", "Not found in the archive: ") + exeName);
                    File.WriteAllText(Path.Combine(stage, ".ogf-sha256"), Net.Sha256File(ep));
                    if (Directory.Exists(dir)) Directory.Delete(dir, true);
                    Directory.CreateDirectory(Path.GetDirectoryName(dir)); Directory.Move(stage, dir);
                }
                finally
                {
                    if (fs != null) fs.Close();
                    try { if (File.Exists(tmp)) File.Delete(tmp); if (Directory.Exists(stage)) Directory.Delete(stage, true); } catch { }
                }
            });
        }
    }

    // modal progress window: the job runs on a worker thread, the window shows what it reports and offers Cancel (when the job allows it)
    class WorkForm : Form
    {
        public volatile bool Cancelled; public string Error; volatile bool finished; volatile string text = ""; long done, total;
        Action<WorkForm> job; Thread th; Label lbl = new Label(); Panel bar = new Panel(); Btn cancel; System.Windows.Forms.Timer tm = new System.Windows.Forms.Timer(); bool canCancel;

        WorkForm(string title, string label, bool cancellable, Action<WorkForm> j)
        {
            job = j; canCancel = cancellable; text = label;
            Text = title; FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false; MinimizeBox = false; ShowInTaskbar = false; ControlBox = false;
            StartPosition = FormStartPosition.CenterParent; ClientSize = new Size(440, 150); BackColor = Th.Bg; ForeColor = Th.Text; Font = Th.Body;
            lbl.AutoSize = false; lbl.SetBounds(24, 20, 392, 40); lbl.ForeColor = Th.Text; lbl.UseMnemonic = false;
            bar.SetBounds(24, 70, 392, 10); bar.BackColor = Th.Inset; bar.Paint += PaintBar;
            cancel = new Btn(); cancel.Text = U.R("Отмена", "Cancel"); cancel.SetBounds(24, 96, 392, 38); cancel.Visible = cancellable; cancel.Click += delegate { Cancelled = true; cancel.Enabled = false; text = U.R("Отменяю…", "Cancelling…"); };
            Controls.AddRange(new Control[] { lbl, bar, cancel });
            tm.Interval = 100; tm.Tick += delegate { lbl.Text = text; bar.Invalidate(); if (finished) { tm.Stop(); DialogResult = DialogResult.OK; Close(); } };
        }
        public void Report(string t, long d, long tot) { if (t != null) text = t; Interlocked.Exchange(ref done, d); Interlocked.Exchange(ref total, tot); }
        void PaintBar(object s, PaintEventArgs e)
        {
            long d = Interlocked.Read(ref done), t = Interlocked.Read(ref total); Graphics g = e.Graphics; g.Clear(Th.Inset);
            if (t > 0) using (SolidBrush b = new SolidBrush(Th.Amber)) g.FillRectangle(b, 0, 0, (int)(bar.Width * Math.Min(1.0, (double)d / t)), bar.Height);
            else { int w = 80, x = (int)((Environment.TickCount / 8) % (bar.Width + w)) - w; using (SolidBrush b = new SolidBrush(Th.Amber)) g.FillRectangle(b, Math.Max(0, x), 0, Math.Min(w, bar.Width - Math.Max(0, x)), bar.Height); }
        }
        protected override void OnShown(EventArgs e)
        {
            base.OnShown(e); lbl.Text = text; tm.Start();
            th = new Thread(delegate() { try { job(this); } catch (CancelledEx) { Error = ""; } catch (Exception ex) { Error = ex.Message; } finally { finished = true; } }); th.IsBackground = true; th.Start();
        }
        protected override void OnHandleCreated(EventArgs e) { base.OnHandleCreated(e); Dark.Apply(Handle); }
        protected override void OnFormClosing(FormClosingEventArgs e) { if (!finished) { e.Cancel = true; if (canCancel) { Cancelled = true; text = U.R("Отменяю…", "Cancelling…"); } } base.OnFormClosing(e); }

        // returns null on success, "" when cancelled, else the error text. owner == null: runs inline (headless self-checks)
        public static string Run(IWin32Window owner, string title, string label, bool cancellable, Action<WorkForm> job)
        {
            WorkForm f = new WorkForm(title, label, cancellable, job);
            if (owner == null) { try { job(f); } catch (CancelledEx) { return ""; } catch (Exception ex) { return ex.Message; } return null; }
            using (f) f.ShowDialog(owner);
            return f.Error;
        }
    }
}
