// "What's new": the change log is a plain text resource (src/changelog.ru.txt / changelog.en.txt):
//   ## 1.0.10 — date      version heading        ### Added      group heading        - item      bullet        # ...      comment
using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Text;
using System.Windows.Forms;

namespace DDFixTool
{
    static class Changelog
    {
        public static string Text(bool ru)
        {
            try
            {
                using (Stream s = System.Reflection.Assembly.GetExecutingAssembly().GetManifestResourceStream(ru ? "changelog_ru" : "changelog_en"))
                using (StreamReader r = new StreamReader(s, Encoding.UTF8)) return r.ReadToEnd();
            }
            catch { return ""; }
        }
        // versions that have an entry (used by the self-check and by the release scripts through the same format)
        public static List<string> Versions(string text)
        {
            List<string> l = new List<string>();
            foreach (string ln in text.Replace("\r", "").Split('\n')) if (ln.StartsWith("## ")) { string v = ln.Substring(3).Trim(); int i = v.IndexOfAny(new char[] { ' ', '—' }); l.Add(i > 0 ? v.Substring(0, i) : v); }
            return l;
        }
    }

    class ChangelogForm : Form
    {
        RichTextBox rt = new RichTextBox();
        void Add(string t, Color c, float pt, FontStyle st, int indent, int hang, int spaceAfter)
        {
            rt.SelectionStart = rt.TextLength; rt.SelectionLength = 0; rt.SelectionColor = c; rt.SelectionFont = Th.F("Segoe UI", pt, st); rt.SelectionIndent = indent; rt.SelectionHangingIndent = hang;
            rt.SelectedText = t + "\n";
        }
        public ChangelogForm() : this(Changelog.Text(L.Ru), "") { }
        public ChangelogForm(string text, string subtitle)
        {
            Text = U.R("Что нового", "What's new"); FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false; MinimizeBox = false; ShowInTaskbar = false;
            Rectangle wa = Screen.PrimaryScreen.WorkingArea; int h = Math.Min(600, Math.Max(360, wa.Height - 90));
            StartPosition = FormStartPosition.CenterParent; ClientSize = new Size(560, h); BackColor = Th.Bg; ForeColor = Th.Text; Font = Th.Body;
            rt.BorderStyle = BorderStyle.None; rt.BackColor = Th.Surf; rt.ForeColor = Th.Text; rt.ReadOnly = true; rt.DetectUrls = false; rt.ScrollBars = RichTextBoxScrollBars.Vertical; rt.SetBounds(24, 22, 512, h - 22 - 20 - 40 - 14);
            rt.Font = Th.F("Segoe UI", 10f, FontStyle.Regular); rt.Cursor = Cursors.Default;
            bool first = true;
            if (subtitle.Length > 0) Add(subtitle, Th.Faint, 9f, FontStyle.Regular, 0, 0, 0);
            foreach (string raw in text.Replace("\r", "").Split('\n'))
            {
                string ln = raw.TrimEnd(); if (ln.Length == 0 || ln.StartsWith("# ")) continue;
                if (ln.StartsWith("## ")) { Add(first ? "\n" + ln.Substring(3) : "\n" + ln.Substring(3), Th.Amber, 13f, FontStyle.Bold, 0, 0, 0); first = false; }
                else if (ln.StartsWith("### ")) Add(ln.Substring(4), Th.Green, 10f, FontStyle.Bold, 0, 0, 0);
                else if (ln.StartsWith("- ")) Add("•  " + ln.Substring(2), Th.Text, 9.5f, FontStyle.Regular, 14, 14, 0);
            }
            Btn bc = new Btn(); bc.Text = U.R("Закрыть", "Close"); bc.Accent = true; bc.SetBounds(24, h - 20 - 40, 512, 40); bc.Click += delegate { Close(); };
            Controls.AddRange(new Control[] { rt, bc }); KeyPreview = true; KeyDown += delegate(object s, KeyEventArgs e) { if (e.KeyCode == Keys.Escape) Close(); };
            rt.SelectionStart = 0; rt.SelectionLength = 0; ActiveControl = bc; Dark.Scroll(rt);
        }
        protected override void OnHandleCreated(EventArgs e) { base.OnHandleCreated(e); Dark.Apply(Handle); }
    }
}
