// Safe editing of ini-like config files (dgVoodoo.conf, ddraw.ini): one key of one section, everything else stays byte-for-byte
// (encoding with/without BOM or ANSI, line endings, comments). A missing key or section is ADDED; a missing file is an error (never a silent "saved").
using System;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;

namespace DDFixTool
{
    static class IniEdit
    {
        public class Doc { public string Text; public Encoding Enc; public bool Bom; public string Eol = "\r\n"; }

        public static Doc Load(string path)
        {
            byte[] b = File.ReadAllBytes(path); Doc d = new Doc(); int skip = 0;
            if (b.Length >= 3 && b[0] == 0xEF && b[1] == 0xBB && b[2] == 0xBF) { d.Enc = new UTF8Encoding(false); d.Bom = true; skip = 3; }
            else if (b.Length >= 2 && b[0] == 0xFF && b[1] == 0xFE) { d.Enc = new UnicodeEncoding(false, false); d.Bom = true; skip = 2; }
            else if (b.Length >= 2 && b[0] == 0xFE && b[1] == 0xFF) { d.Enc = new UnicodeEncoding(true, false); d.Bom = true; skip = 2; }
            else
            {
                try { d.Enc = new UTF8Encoding(false, true); d.Text = d.Enc.GetString(b); d.Enc = new UTF8Encoding(false); }
                catch (ArgumentException) { d.Enc = Encoding.Default; }   // not valid UTF-8: the file is ANSI (cp1251 on a Russian system)
            }
            if (d.Text == null) d.Text = d.Enc.GetString(b, skip, b.Length - skip);
            d.Eol = d.Text.IndexOf("\r\n", StringComparison.Ordinal) >= 0 ? "\r\n" : (d.Text.IndexOf('\n') >= 0 ? "\n" : "\r\n");
            return d;
        }
        public static void Save(string path, Doc d)
        {
            byte[] body = d.Enc.GetBytes(d.Text), pre = d.Bom ? d.Enc.GetPreamble() : new byte[0], all = new byte[pre.Length + body.Length];
            Array.Copy(pre, all, pre.Length); Array.Copy(body, 0, all, pre.Length, body.Length);
            string tmp = path + ".ogf-tmp";
            try
            {
                File.WriteAllBytes(tmp, all);
                try { File.Replace(tmp, path, null); } catch (IOException) { File.Copy(tmp, path, true); }   // File.Replace needs the same volume and a writable target
            }
            finally { try { if (File.Exists(tmp)) File.Delete(tmp); } catch { } }
        }

        static bool Section(string t, string section, out int bodyStart, out int end)
        {
            Match h = Regex.Match(t, @"(?im)^[ \t]*\[" + Regex.Escape(section) + @"\][ \t]*\r?$");
            bodyStart = end = 0; if (!h.Success) return false;
            bodyStart = h.Index + h.Length; Match n = Regex.Match(t.Substring(bodyStart), @"(?m)^[ \t]*\["); end = n.Success ? bodyStart + n.Index : t.Length; return true;
        }

        public static string Get(string path, string section, string key, string def)
        {
            try
            {
                string t = Load(path).Text; int s, e; if (!Section(t, section, out s, out e)) return def;
                Match m = Regex.Match(t.Substring(s, e - s), @"(?im)^[ \t]*" + Regex.Escape(key) + @"[ \t]*=[ \t]*(.*?)[ \t]*\r?$"); return m.Success ? m.Groups[1].Value : def;
            }
            catch { return def; }
        }

        // sets key = val inside [section]; adds the key (or the whole section) when absent. Throws when the file cannot be read or written.
        public static void Set(string path, string section, string key, string val)
        {
            Doc d = Load(path); string t = d.Text; int s, e;
            if (!Section(t, section, out s, out e))
            {
                if (t.Length > 0 && !t.EndsWith("\n")) t += d.Eol;
                d.Text = t + (t.Length > 0 ? d.Eol : "") + "[" + section + "]" + d.Eol + key + "=" + val + d.Eol; Save(path, d); return;
            }
            string sec = t.Substring(s, e - s);
            Regex r = new Regex(@"(?im)^([ \t]*" + Regex.Escape(key) + @"[ \t]*=[ \t]*)(.*?)([ \t]*)(\r?)$");
            if (r.IsMatch(sec)) { string ns = r.Replace(sec, delegate(Match m) { return m.Groups[1].Value + val + m.Groups[3].Value + m.Groups[4].Value; }, 1); if (ns == sec) return; d.Text = t.Substring(0, s) + ns + t.Substring(e); }
            else
            {
                int p = sec.Length; while (p > 0 && " \t\r\n".IndexOf(sec[p - 1]) >= 0) p--;   // before the blank lines that close the section
                d.Text = t.Substring(0, s) + sec.Substring(0, p) + d.Eol + key + "=" + val + sec.Substring(p) + t.Substring(e);
            }
            Save(path, d);
        }
    }
}
