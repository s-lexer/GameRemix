// "?" help for settings: one data store (shared/help/graphics.txt for every game + games/<id>/gfx/help.txt for the game), one window.
// Windows ask for a key: Help.Show(owner, "scale"). Format of the data: "## key" / title.ru / title.en / ru / en ("\n" in a text = line break).
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Text;
using System.Windows.Forms;

namespace DDFixTool
{
    static class Help
    {
        class Entry { public string TitleRu = "", TitleEn = "", Ru = "", En = ""; }
        static Dictionary<string, Entry> db;
        static void Parse(string text)
        {
            Entry cur = null;
            foreach (string raw in text.TrimStart('﻿').Replace("\r\n", "\n").Split('\n'))
            {
                string ln = raw.Trim(); if (ln.Length == 0 || ln[0] == '#' && !ln.StartsWith("##")) continue;
                if (ln.StartsWith("## ")) { cur = new Entry(); db[ln.Substring(3).Trim()] = cur; continue; }
                int eq = ln.IndexOf('='); if (cur == null || eq <= 0) continue; string k = ln.Substring(0, eq), v = ln.Substring(eq + 1).Replace("\\n", "\n");
                if (k == "title.ru") cur.TitleRu = v; else if (k == "title.en") cur.TitleEn = v; else if (k == "ru") cur.Ru = v; else if (k == "en") cur.En = v;
            }
        }
        static void Load()
        {
            if (db != null) return; db = new Dictionary<string, Entry>();
            foreach (string r in new string[] { "help_shared", "help_game" }) { try { Parse(Encoding.UTF8.GetString(Core.ResBytes(r))); } catch (Exception) { } }
        }
        public static bool Has(string key) { Load(); return db.ContainsKey(key); }
        public static void Get(string key, out string title, out string body)
        {
            Load(); Entry e; if (!db.TryGetValue(key, out e)) { title = key; body = ""; return; }
            title = L.Ru ? e.TitleRu : e.TitleEn; body = L.Ru ? e.Ru : e.En; if (title.Length == 0) title = key;
        }
        public static void Show(IWin32Window owner, string key) { using (HelpTextForm f = new HelpTextForm(key)) f.ShowDialog(owner); }
        // the small "?" button of a row (same look as the one on cnc-ddraw / dgVoodoo rows)
        public static EventHandler Click(IWin32Window owner, string key) { return delegate { Show(owner, key); }; }
    }

    class HelpTextForm : Form
    {
        public HelpTextForm(string key)
        {
            string title, body; Help.Get(key, out title, out body);
            Text = title; FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false; MinimizeBox = false; ShowInTaskbar = false;
            StartPosition = FormStartPosition.CenterParent; BackColor = Th.Bg; ForeColor = Th.Text; Font = Th.Body;
            RichTextBox rt = new RichTextBox(); rt.BorderStyle = BorderStyle.None; rt.BackColor = Th.Surf; rt.ForeColor = Th.Text; rt.ReadOnly = true; rt.DetectUrls = false; rt.Cursor = Cursors.Default; rt.TabStop = false;
            rt.Font = Th.F("Segoe UI", 10f, FontStyle.Regular); rt.Padding = new Padding(0);
            rt.SelectionColor = Th.Amber; rt.SelectionFont = Th.F("Segoe UI", 14f, FontStyle.Bold); rt.SelectedText = title + "\n\n";
            string[] paras = body.Split('\n');
            for (int i = 0; i < paras.Length; i++) { rt.SelectionColor = i == 0 ? Th.Text : Th.Muted; rt.SelectionFont = Th.F("Segoe UI", 10f, FontStyle.Regular); rt.SelectedText = paras[i] + (i < paras.Length - 1 ? "\n\n" : ""); }
            Size m = TextRenderer.MeasureText(title + "\n\n" + body.Replace("\n", "\n\n"), Th.F("Segoe UI", 10.5f, FontStyle.Regular), new Size(452, 0), TextFormatFlags.WordBreak | TextFormatFlags.NoPadding);
            int h = Math.Max(200, Math.Min(Fit.WorkArea().Height - 200, m.Height + 70)); rt.ScrollBars = m.Height + 70 > h ? RichTextBoxScrollBars.Vertical : RichTextBoxScrollBars.None;
            ClientSize = new Size(520, h + 84); rt.SetBounds(24, 20, 472, h); rt.SelectionStart = 0; rt.SelectionLength = 0;
            Btn ok = new Btn(); ok.Accent = true; ok.Text = U.R("Понятно", "Got it"); ok.SetBounds(24, h + 32, 472, 40); ok.Click += delegate { Close(); };
            Controls.AddRange(new Control[] { rt, ok }); KeyPreview = true; KeyDown += delegate(object s, KeyEventArgs e) { if (e.KeyCode == Keys.Escape) Close(); }; ActiveControl = ok;
        }
        protected override void OnHandleCreated(EventArgs e) { base.OnHandleCreated(e); Dark.Apply(Handle); if (Controls.Count > 0) Dark.Scroll(Controls[0]); }
    }
}
