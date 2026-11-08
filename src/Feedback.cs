// Feedback window: message + optional e-mail + optional logs (zip) -> POST to https://gameremix.speectra.com/feedback.php
using System;
using System.Text.RegularExpressions;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Text;
using System.Threading;
using System.Windows.Forms;

namespace DDFixTool
{
    // minimal ZIP writer (deflate, no external libs: .NET 3.5 has no ZipFile)
    static class MiniZip
    {
        static uint[] tab;
        static uint Crc(byte[] d) { if (tab == null) { tab = new uint[256]; for (uint i = 0; i < 256; i++) { uint c = i; for (int k = 0; k < 8; k++) c = (c & 1) != 0 ? 0xEDB88320u ^ (c >> 1) : c >> 1; tab[i] = c; } } uint r = 0xFFFFFFFFu; foreach (byte b in d) r = tab[(r ^ b) & 0xFF] ^ (r >> 8); return ~r; }
        public static byte[] Build(List<KeyValuePair<string, byte[]>> files)
        {
            MemoryStream o = new MemoryStream(); BinaryWriter w = new BinaryWriter(o); List<long> offs = new List<long>(); List<uint> crcs = new List<uint>(); List<int> csz = new List<int>();
            DateTime n = DateTime.Now; ushort dt = (ushort)(((n.Year - 1980) << 9) | (n.Month << 5) | n.Day), tm = (ushort)((n.Hour << 11) | (n.Minute << 5) | (n.Second / 2));
            foreach (KeyValuePair<string, byte[]> f in files)
            {
                byte[] nm = Encoding.UTF8.GetBytes(f.Key), cmp; MemoryStream ms = new MemoryStream();
                using (DeflateStream z = new DeflateStream(ms, CompressionMode.Compress, true)) z.Write(f.Value, 0, f.Value.Length);
                cmp = ms.ToArray(); uint crc = Crc(f.Value); offs.Add(o.Position); crcs.Add(crc); csz.Add(cmp.Length);
                w.Write(0x04034b50u); w.Write((ushort)20); w.Write((ushort)0x800); w.Write((ushort)8); w.Write(tm); w.Write(dt); w.Write(crc); w.Write((uint)cmp.Length); w.Write((uint)f.Value.Length); w.Write((ushort)nm.Length); w.Write((ushort)0); w.Write(nm); w.Write(cmp);
            }
            long cd = o.Position;
            for (int i = 0; i < files.Count; i++)
            {
                byte[] nm = Encoding.UTF8.GetBytes(files[i].Key);
                w.Write(0x02014b50u); w.Write((ushort)20); w.Write((ushort)20); w.Write((ushort)0x800); w.Write((ushort)8); w.Write(tm); w.Write(dt); w.Write(crcs[i]); w.Write((uint)csz[i]); w.Write((uint)files[i].Value.Length);
                w.Write((ushort)nm.Length); w.Write((ushort)0); w.Write((ushort)0); w.Write((ushort)0); w.Write((ushort)0); w.Write(0u); w.Write((uint)offs[i]); w.Write(nm);
            }
            long cdl = o.Position - cd;
            w.Write(0x06054b50u); w.Write((ushort)0); w.Write((ushort)0); w.Write((ushort)files.Count); w.Write((ushort)files.Count); w.Write((uint)cdl); w.Write((uint)cd); w.Write((ushort)0);
            w.Flush(); return o.ToArray();
        }
    }

    partial class Core
    {
        public string StatusLine()
        {
            return "exeSupported=" + ExeSupported + " mode=" + Mode + " voice=" + VoiceOn + " dusk=" + DuskOn + " shortcut=" + ShortcutExists + " voicePatched=" + VoicePatched + " duskPatched=" + DuskPatched + " dllsFull=" + DllsFull
                + " bone=" + Bone + " launcher=" + Launcher + " dgv=" + Dgv + " fonts=" + FontState(0) + "," + FontState(1) + "," + FontState(2) + " fontStep=" + FontStep(0) + "," + FontStep(1) + "," + FontStep(2);
        }
        // fresh logs for the author: program log (tail), state, dgVoodoo.conf, config.div -> zip bytes
        // strip the Windows profile path / user name so the archive really holds no personal data
        static string Anon(string t)
        {
            try
            {
                string up = Environment.GetEnvironmentVariable("USERPROFILE"), un = Environment.UserName;
                if (!string.IsNullOrEmpty(up)) t = Regex.Replace(t, Regex.Escape(up), "~", RegexOptions.IgnoreCase);
                if (!string.IsNullOrEmpty(un) && un.Length > 2) t = Regex.Replace(t, Regex.Escape(un), "user", RegexOptions.IgnoreCase);
            }
            catch { }
            return t;
        }
        static byte[] Anon(byte[] b) { return Encoding.UTF8.GetBytes(Anon(Encoding.UTF8.GetString(b))); }
        public byte[] CollectLogs()
        {
            List<KeyValuePair<string, byte[]>> f = new List<KeyValuePair<string, byte[]>>();
            Action<string, byte[]> add = delegate(string n, byte[] b) { f.Add(new KeyValuePair<string, byte[]>(n, b)); };
            try
            {
                string lg = Path.Combine(App.DataDir, "log.txt");
                if (File.Exists(lg)) { byte[] b = File.ReadAllBytes(lg); if (b.Length > 300000) { byte[] t = new byte[300000]; Array.Copy(b, b.Length - 300000, t, 0, 300000); b = t; } add("log.txt", Anon(b)); }
            }
            catch { }
            StringBuilder s = new StringBuilder();
            s.AppendLine("GameRemix " + App.Version + "  " + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"));
            s.AppendLine("OS " + Environment.OSVersion + "  64bit=" + (IntPtr.Size == 8 || Environment.GetEnvironmentVariable("PROCESSOR_ARCHITEW6432") != null) + "  .NET " + Environment.Version + "  lang=" + (L.Ru ? "ru" : "en"));
            try { s.AppendLine("game " + (HasGame ? ExeVersionText : "not found")); if (HasGame) s.AppendLine("STATUS " + StatusLine()); } catch (Exception e) { s.AppendLine("status error: " + e.Message); }
            add("status.txt", Encoding.UTF8.GetBytes(Anon(s.ToString())));
            if (HasGame) foreach (string n in new string[] { "dgVoodoo.conf", "config.div" }) { try { if (File.Exists(P(n))) { byte[] fb = File.ReadAllBytes(P(n)); add(n, n.EndsWith(".conf") ? Anon(fb) : fb); } } catch { } }
            return MiniZip.Build(f);
        }
    }

    class FeedbackForm : Form
    {
        Core core; TextBox msg = new TextBox(); Field email = new Field(); Seg logs = new Seg(); Btn send = new Btn(); Label status = new Label();
        const string Url = "https://gameremix.speectra.com/feedback.php";
        public FeedbackForm(Core c)
        {
            core = c; Text = U.R("Обратная связь", "Feedback"); FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false; MinimizeBox = false; ShowInTaskbar = false;
            StartPosition = FormStartPosition.CenterParent; ClientSize = new Size(520, 480); BackColor = Th.Bg; ForeColor = Th.Text; Font = Th.Body;
            Label q = new Label(); q.AutoSize = false; q.SetBounds(24, 16, 472, 36); q.ForeColor = Th.Muted; q.BackColor = Th.Bg;
            q.Text = U.R("Нашли ошибку или есть идея? Напишите — автор читает всё.", "Found a bug or have an idea? Write it down — the author reads everything.");
            Panel box = new Panel(); box.SetBounds(24, 56, 472, 150); box.BackColor = Th.Inset; box.Padding = new Padding(10);
            msg.Multiline = true; msg.BorderStyle = BorderStyle.None; msg.BackColor = Th.Inset; msg.ForeColor = Th.Text; msg.Font = Th.Body; msg.ScrollBars = ScrollBars.None; msg.MaxLength = 4000; msg.SetBounds(10, 10, 452, 130);
            box.Controls.Add(msg);
            Label le = new Label(); le.AutoSize = false; le.SetBounds(24, 218, 472, 18); le.Font = Th.Small; le.ForeColor = Th.Amber; le.BackColor = Th.Bg; le.Text = U.R("E-MAIL ДЛЯ ОТВЕТА (НЕ ОБЯЗАТЕЛЬНО)", "E-MAIL FOR A REPLY (OPTIONAL)");
            email.Under = Th.Bg; email.SetBounds(24, 238, 472, 36); email.Hint = "name@example.com";
            Label ll = new Label(); ll.AutoSize = false; ll.SetBounds(24, 292, 330, 20); ll.ForeColor = Th.Text; ll.BackColor = Th.Bg; ll.Text = U.R("Приложить логи (по желанию)", "Attach logs (optional)");
            logs.Under = Th.Bg; logs.Items = new string[] { U.R("Выкл", "Off"), U.R("Вкл", "On") }; logs.SetBounds(412, 288, 84, 28); logs.Selected = 1;
            Label lh = new Label(); lh.AutoSize = false; lh.SetBounds(24, 318, 472, 48); lh.Font = Th.Small; lh.ForeColor = Th.Faint; lh.BackColor = Th.Bg;
            lh.Text = U.R("В архив попадают: журнал программы, версия Windows и игры, состояние фиксов, dgVoodoo.conf и config.div. Личных данных там нет.", "The archive holds: the program log, Windows and game versions, fix states, dgVoodoo.conf and config.div. No personal data.");
            status.AutoSize = false; status.SetBounds(24, 370, 472, 40); status.Font = Th.Small; status.ForeColor = Th.Muted; status.BackColor = Th.Bg; status.UseMnemonic = false;   // full width, up to three lines: an error with the mail address must not be cut
            send.Accent = true; send.Pt = 10f; send.Text = U.R("Отправить", "Send"); send.SetBounds(286, 424, 120, 40); send.Click += delegate { Send(); };
            Btn cl = new Btn(); cl.Text = U.R("Закрыть", "Close"); cl.SetBounds(416, 424, 80, 40); cl.Click += delegate { Close(); };
            Controls.AddRange(new Control[] { q, box, le, email, ll, logs, lh, status, send, cl }); KeyPreview = true; KeyDown += delegate(object s, KeyEventArgs e) { if (e.KeyCode == Keys.Escape) Close(); };
        }
        protected override void OnHandleCreated(EventArgs e) { base.OnHandleCreated(e); Dark.Apply(Handle); }

        void Send()
        {
            string text = msg.Text.Trim(), mail = email.Box.Text.Trim();
            if (text.Length == 0) { msg.Focus(); return; }
            if (mail.Length > 0 && (mail.IndexOf('@') < 1 || mail.IndexOf(' ') >= 0)) { status.ForeColor = Th.Amber; status.Text = U.R("Проверьте e-mail или очистите поле.", "Check the e-mail or clear the field."); email.Box.Focus(); return; }
            send.Enabled = false; status.ForeColor = Th.Muted; status.Text = U.R("Отправляю…", "Sending…");
            bool withLogs = logs.Selected == 1; string ver = App.Version, lang = L.Ru ? "ru" : "en";
            Thread t = new Thread(delegate()
            {
                string err = null;
                try
                {
                    byte[] zip = withLogs ? core.CollectLogs() : null;
                    err = Post(text, mail, ver, lang, zip);
                }
                catch (Exception ex) { err = ex.Message; }
                try { BeginInvoke((MethodInvoker)delegate { Done(err); }); } catch { }
            });
            t.IsBackground = true; t.Start();
        }

        void Done(string err)
        {
            send.Enabled = true;
            if (err == null) { status.ForeColor = Th.Green; status.Text = U.R("Отправлено. Спасибо!", "Sent. Thank you!"); msg.Text = ""; }
            else { status.ForeColor = Th.Amber; status.Text = U.R("Не удалось отправить: ", "Could not send: ") + err.TrimEnd(' ', '.') + U.R(". Можно написать на ", ". You can write to ") + App.Mail; }
        }

        // server answers "ok" or "err:<code>"; show a translated sentence, never the raw code
        static string Err(string a)
        {
            if (a == "ok") return null;
            if (a.StartsWith("err:")) switch (a.Substring(4).Trim())
            {
                case "rate": return U.R("слишком часто, повторите через несколько минут", "too often, try again in a few minutes");
                case "email": return U.R("адрес e-mail не принят сервером", "the server did not accept the e-mail address");
                case "msg": return U.R("пустое или слишком длинное сообщение", "the message is empty or too long");
                case "logs": return U.R("архив логов слишком большой или повреждён", "the log archive is too large or damaged");
                case "method": return U.R("запрос отклонён сервером", "the request was rejected by the server");
                case "store": return U.R("сервер временно не может сохранить сообщение", "the server cannot store the message right now");
            }
            return U.R("неожиданный ответ сервера", "unexpected server reply");
        }
        internal static string Post(string text, string mail, string ver, string lang, byte[] zip)
        {
            string tls = Net.Tls(); if (tls != null) return tls;
            string b = "----ogf" + Guid.NewGuid().ToString("N");
            MemoryStream ms = new MemoryStream();
            Action<string, string> fld = delegate(string n, string v) { byte[] d = Encoding.UTF8.GetBytes("--" + b + "\r\nContent-Disposition: form-data; name=\"" + n + "\"\r\n\r\n" + v + "\r\n"); ms.Write(d, 0, d.Length); };
            fld("msg", text); fld("email", mail); fld("v", ver); fld("lang", lang);
            if (zip != null)
            {
                byte[] h = Encoding.UTF8.GetBytes("--" + b + "\r\nContent-Disposition: form-data; name=\"logs\"; filename=\"logs.zip\"\r\nContent-Type: application/zip\r\n\r\n"); ms.Write(h, 0, h.Length); ms.Write(zip, 0, zip.Length);
                byte[] nl = Encoding.UTF8.GetBytes("\r\n"); ms.Write(nl, 0, nl.Length);
            }
            byte[] end = Encoding.UTF8.GetBytes("--" + b + "--\r\n"); ms.Write(end, 0, end.Length);
            try
            {
                HttpWebRequest rq = Net.Req(Url, "POST", 30000); rq.ContentType = "multipart/form-data; boundary=" + b; rq.ContentLength = ms.Length;
                using (Stream s = rq.GetRequestStream()) { byte[] d = ms.ToArray(); s.Write(d, 0, d.Length); }
                using (HttpWebResponse rs = (HttpWebResponse)rq.GetResponse())
                {
                    int c = (int)rs.StatusCode; if (c >= 300 && c < 400) return U.R("сервер перенаправил запрос, отправка отклонена", "the server redirected the request, sending refused");
                    return Err(Net.ReadCapped(rs, 2048).Trim());
                }
            }
            catch (WebException ex)
            {
                if (ex.Response != null) { try { return Err(Net.ReadCapped(ex.Response, 2048).Trim()) ?? ex.Message; } catch { } }
                return ex.Message;
            }
            catch (Exception ex) { return ex.Message; }
        }
    }
}
