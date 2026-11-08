using System;
using System.Collections.Generic;
using System.Drawing;
using System.Windows.Forms;

namespace DDFixTool
{
    // Shell for every NEW built-in tool (one format everywhere, same look as the main window and USBOperator):
    // dark window, rounded cards with a header, one-line rows on the main grid (icon | title | description | status | control),
    // a bottom strip with the status line, tool buttons and the RU/EN switch. A tool derives from ToolForm, builds cards in Build(Panel body)
    // and its footer buttons in BuildFoot(); every visible string goes through T(ru, en). Changing the language re-runs both.
    abstract class ToolForm : Form
    {
        protected const int M = 12;
        protected readonly Core Game; protected Panel Body; protected RPanel Foot; Label status; Seg lang; bool ru; List<Control> footTools = new List<Control>();
        protected abstract string TitleRu { get; }
        protected abstract string TitleEn { get; }
        protected abstract void Build(Panel body);
        protected virtual void BuildFoot() { }
        protected string T(string r, string e) { return ru ? r : e; }
        protected bool IsRu { get { return ru; } }

        protected ToolForm(Core game, Size client)
        {
            Game = game; ru = L.Ru;
            FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false; MinimizeBox = false; ShowInTaskbar = true;
            StartPosition = FormStartPosition.CenterScreen; Fit.To(this, client); BackColor = Th.Bg; ForeColor = Th.Text; Font = Th.Body;
            Body = new Panel(); Body.SetBounds(M, M, client.Width - 2 * M, client.Height - 3 * M - 56); Body.BackColor = Th.Bg;
            Foot = new RPanel(); Foot.SetBounds(M, client.Height - M - 56, client.Width - 2 * M, 56);
            status = new Label(); status.AutoSize = false; status.SetBounds(16, 8, 10, 40); status.ForeColor = Th.Muted; status.BackColor = Th.Surf; status.Font = Th.F("Segoe UI", 8.5f, FontStyle.Regular); status.UseMnemonic = false; status.TextAlign = ContentAlignment.MiddleLeft;
            lang = new Seg(); lang.Under = Th.Surf; lang.Items = new string[] { "RU", "EN" }; lang.SetBounds(Foot.Width - 14 - 66, 16, 66, 24); lang.Selected = ru ? 0 : 1;
            lang.Changed += delegate { ru = lang.Selected == 0; Rebuild(); };
            Foot.Controls.Add(status); Foot.Controls.Add(lang); Controls.Add(Body); Controls.Add(Foot);
            KeyPreview = true; KeyDown += delegate(object s, KeyEventArgs e) { if (e.KeyCode == Keys.Escape) Close(); };
        }
        protected override void OnShown(EventArgs e) { base.OnShown(e); Rebuild(); }
        protected override void OnHandleCreated(EventArgs e) { base.OnHandleCreated(e); Dark.Apply(Handle); if (AutoScroll) Dark.Scroll(this); }
        protected void Reload() { Rebuild(); }
        void Rebuild()
        {
            SuspendLayout(); Text = ru ? TitleRu : TitleEn;
            List<Control> old = new List<Control>(); foreach (Control c in Body.Controls) old.Add(c);
            foreach (Control c in old) { Body.Controls.Remove(c); c.Dispose(); }
            foreach (Control c in footTools) { Foot.Controls.Remove(c); c.Dispose(); } footTools.Clear(); footRight = 0;
            Build(Body); BuildFoot(); LayFoot(); ResumeLayout();
        }
        // footer buttons are placed right to left, left of the RU/EN switch; the status text takes the rest
        int footRight;
        void LayFoot() { status.Width = Math.Max(10, footRight > 0 ? footRight - 16 - 12 : Foot.Width - 120); }
        protected Btn FootBtn(string text, bool accent, int w, EventHandler h)
        {
            if (footRight == 0) footRight = lang.Left - 12; Btn b = new Btn(); b.Accent = accent; b.Under = Th.Surf; b.Pt = 9f; b.Text = text; b.SetBounds(footRight - w, 12, w, 32); b.Click += h;
            footRight -= w + 8; Foot.Controls.Add(b); footTools.Add(b); return b;
        }

        // ---- building blocks (same look as the main window) ----
        protected RPanel Card(Panel host, int x, int y, int w, int h, string title, string sub)
        {
            RPanel c = new RPanel(); c.SetBounds(x, y, w, h); host.Controls.Add(c);
            Label t = new Label(); t.AutoSize = false; t.SetBounds(14, 12, w - 28, 24); t.Font = Th.F("Segoe UI Semibold", 12.5f, FontStyle.Regular); t.ForeColor = Th.Text; t.BackColor = Th.Surf; t.UseMnemonic = false; t.Text = title;
            Label s = new Label(); s.AutoSize = false; s.SetBounds(14, 36, w - 28, 18); s.Font = Th.F("Segoe UI", 8.5f, FontStyle.Regular); s.ForeColor = Th.Muted; s.BackColor = Th.Surf; s.UseMnemonic = false; s.Text = sub;
            c.Controls.Add(t); c.Controls.Add(s); return c;
        }
        protected RowCtl Hr(RowCtl r, string helpKey) { r.HelpClick = delegate { Help.Show(this, helpKey); }; return r; }   // adds the "?" of a settings row (texts: Help.cs)
        protected RowCtl Row(string glyph, Color gc, string title, string desc, Control ctl) { RowCtl r = new RowCtl(); r.Glyph = glyph; r.GlyphColor = gc; r.Title = title; r.Desc = desc; r.Ctl = ctl; return r; }
        // rows are always 44 high, section heads 22, gap 5
        protected int Lay(RPanel card, int top, params Control[] items)
        {
            int y = top; bool first = true;
            foreach (Control c in items) { if (c is SecHead && !first) y += 4; c.SetBounds(14, y, card.Width - 28, c is SecHead ? 22 : RowCtl.H); card.Controls.Add(c); y += c.Height + 5; first = false; }
            return y;
        }
        protected Btn Act(string text, EventHandler h) { Btn b = new Btn(); b.Under = Th.Inset; b.Text = text; b.Pt = 8.5f; b.Size = new Size(84, 28); b.Click += h; return b; }
        protected NumericUpDown Num(decimal max)
        {
            NumericUpDown n = new NumericUpDown(); n.Minimum = 0; n.Maximum = max; n.Size = new Size(84, 26); n.BackColor = Th.SurfHi; n.ForeColor = Th.Text; n.BorderStyle = BorderStyle.FixedSingle; n.TextAlign = HorizontalAlignment.Right; n.Font = Th.F("Segoe UI", 9.5f, FontStyle.Regular); return n;
        }
        protected Seg Sg(string[] items, int selected, EventHandler changed) { Seg s = new Seg(); s.Under = Th.Inset; s.Items = items; s.Size = new Size(Math.Max(84, 42 * items.Length), 28); s.Selected = selected; s.Changed += changed; return s; }
        protected void Status(string ruText, string enText) { status.Text = T(ruText, enText); }
    }

    // "Classic or New" chooser: shown when a tool has both versions. Returns true = new, false = classic, null = cancelled.
    class ToolChoiceForm : Form
    {
        public bool? Result;
        public ToolChoiceForm(string toolName)
        {
            Text = toolName; FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false; MinimizeBox = false; ShowInTaskbar = false;
            StartPosition = FormStartPosition.CenterParent; ClientSize = new Size(440, 190); BackColor = Th.Bg; ForeColor = Th.Text; Font = Th.Body;
            Label q = new Label(); q.AutoSize = false; q.SetBounds(24, 20, 392, 50); q.Text = U.R("Какую версию открыть? Новая переписана заново: русский и английский интерфейс, тема программы.", "Which version to open? The new one is rewritten: Russian and English UI, program theme."); q.ForeColor = Th.Muted; q.UseMnemonic = false;
            Btn n = new Btn(); n.Accent = true; n.Text = U.R("Новая", "New"); n.SetBounds(24, 90, 192, 44); n.Click += delegate { Result = true; Close(); };
            Btn c = new Btn(); c.Text = U.R("Классическая", "Classic"); c.SetBounds(224, 90, 192, 44); c.Click += delegate { Result = false; Close(); };
            Btn x = new Btn(); x.Text = U.R("Отмена", "Cancel"); x.SetBounds(24, 142, 392, 32); x.Click += delegate { Close(); };
            Controls.AddRange(new Control[] { q, n, c, x }); KeyPreview = true; KeyDown += delegate(object s, KeyEventArgs e) { if (e.KeyCode == Keys.Escape) Close(); };
        }
        protected override void OnHandleCreated(EventArgs e) { base.OnHandleCreated(e); Dark.Apply(Handle); }
    }

    // Registry of new tools: key = classic exe name; value builds the new form. Empty entries mean "classic only".
    static class NewTools
    {
        public static readonly Dictionary<string, Func<Core, Form>> Map = Init();
        static Dictionary<string, Func<Core, Form>> Init()
        {
            Dictionary<string, Func<Core, Form>> m = new Dictionary<string, Func<Core, Form>>(StringComparer.OrdinalIgnoreCase);
            m["SaveEditor.exe"] = delegate(Core c) { return new ToolSaveEditor(c); };
            return m;
        }
    }
}
