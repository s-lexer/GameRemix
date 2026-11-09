// UI of DD_FixTool: tiles, hover popup, About, Fonts dialog, folder picker, main window.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows.Forms;

namespace DDFixTool
{
    static class U
    {
        public static string R(string ru, string en) { return L.Ru ? ru : L.Kor(en); }
        public const TextFormatFlags Wrap = TextFormatFlags.WordBreak | TextFormatFlags.NoPadding | TextFormatFlags.NoPrefix;
        public static bool Open(string url) { try { Process.Start(new ProcessStartInfo(url) { UseShellExecute = true }); return true; } catch { return false; } }   // false = nothing was opened (no mail program, no browser)
        public static string Pl(int n, string one, string few, string many) { int m = Math.Abs(n) % 100, d = m % 10; if (!L.Ru) return n == 1 ? one : many; return m > 10 && m < 20 ? many : (d == 1 ? one : (d >= 2 && d <= 4 ? few : many)); }
        public const string Boosty = "https://boosty.to/lexxxxx/donate", Patreon = "https://www.patreon.com/cw/gameremix";
    }

    // A window that is taller than a short screen (768 px laptops) gets the working area's size and scrolls instead of being cut off.
    // The program stays DPI-unaware on purpose: every control is hand-drawn on a pixel grid, so Windows scales the whole window and its virtual working area shrinks with it.
    static class Fit
    {
        public static Rectangle WorkArea()
        {
            string o = Environment.GetEnvironmentVariable("OGF_WORKAREA");   // "WxH" - lets the layout be tested for a small screen
            if (!string.IsNullOrEmpty(o)) { string[] p = o.Split('x'); int w, h; if (p.Length == 2 && int.TryParse(p[0], out w) && int.TryParse(p[1], out h)) return new Rectangle(0, 0, w, h); }
            return Screen.FromPoint(Cursor.Position).WorkingArea;
        }
        public static void To(Form f, Size want)
        {
            f.ClientSize = want; Rectangle wa = WorkArea();
            int ncW = f.Width - f.ClientSize.Width, ncH = f.Height - f.ClientSize.Height, maxW = wa.Width - ncW - 8, maxH = wa.Height - ncH - 8, cw = want.Width, ch = want.Height;
            if (ch > maxH) { ch = maxH; cw = Math.Min(maxW, want.Width + SystemInformation.VerticalScrollBarWidth); }
            if (cw > maxW) { cw = maxW; ch = Math.Min(maxH, ch + SystemInformation.HorizontalScrollBarHeight); }
            if (cw < want.Width || ch < want.Height) { f.AutoScroll = true; f.AutoScrollMinSize = want; f.ClientSize = new Size(cw, ch); }
        }
    }

    // ---------------------------------------------------------------- hover popup (themed, never takes focus, Win7+)
    class TipForm : Form
    {
        string title = "", body = "";
        public TipForm()
        {
            FormBorderStyle = FormBorderStyle.None; ShowInTaskbar = false; StartPosition = FormStartPosition.Manual; TopMost = true; DoubleBuffered = true; BackColor = Th.SurfHi;
        }
        protected override bool ShowWithoutActivation { get { return true; } }
        protected override CreateParams CreateParams { get { CreateParams cp = base.CreateParams; cp.ExStyle |= 0x08000000 | 0x80; return cp; } }
        public void ShowFor(Form owner, Control anchor, Rectangle r, string t, string b)
        {
            title = t; body = b;
            Size st = TextRenderer.MeasureText(t, Th.Semi, new Size(320, 0), U.Wrap), sb = b.Length > 0 ? TextRenderer.MeasureText(b, Th.Body, new Size(320, 0), U.Wrap) : Size.Empty;
            Size = new Size(Math.Max(st.Width, sb.Width) + 28, st.Height + (b.Length > 0 ? sb.Height + 8 : 0) + 22);
            Rectangle wa = Screen.FromControl(anchor).WorkingArea;
            Point p = anchor.PointToScreen(new Point(r.X, r.Bottom + 6));
            if (p.Y + Height > wa.Bottom) p = anchor.PointToScreen(new Point(r.X, r.Y - 6 - Height));
            if (p.X + Width > wa.Right) p.X = wa.Right - Width - 4; if (p.X < wa.Left) p.X = wa.Left + 4;
            Location = p; Invalidate();
            if (!Visible) Show(owner);
        }
        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics;
            using (Pen pen = new Pen(Th.AmberDeep)) g.DrawRectangle(pen, 0, 0, Width - 1, Height - 1);
            Size st = TextRenderer.MeasureText(title, Th.Semi, new Size(320, 0), U.Wrap);
            TextFit.Draw(g, this, title, Th.Semi, new Rectangle(14, 11, 320, st.Height), Th.Amber, U.Wrap);
            if (body.Length > 0) TextFit.Draw(g, this, body, Th.Body, new Rectangle(14, 11 + st.Height + 8, 320, Height - st.Height - 20), Th.Text, U.Wrap);
        }
    }

    class SupportForm : Form
    {
        public SupportForm()
        {
            Text = U.R("Поддержать автора", "Support the author"); FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false; MinimizeBox = false; ShowInTaskbar = false;
            StartPosition = FormStartPosition.CenterParent; ClientSize = new Size(420, 210); BackColor = Th.Bg; ForeColor = Th.Text; Font = Th.Body;
            Label q = new Label(); q.AutoSize = false; q.SetBounds(24, 20, 372, 44); q.Text = U.R("Спасибо, что пользуетесь программой! Выберите, где поддержать разработку:", "Thanks for using the program! Choose where to support the development:"); q.ForeColor = Th.Muted; q.UseMnemonic = false;
            Btn a = new Btn(); a.Accent = true; a.Pt = 10f; a.Text = "♥  Boosty"; a.SetBounds(24, 76, 372, 44); a.Click += delegate { U.Open(U.Boosty); Close(); };
            Btn b = new Btn(); b.Accent = true; b.Pt = 10f; b.Text = "♥  Patreon"; b.SetBounds(24, 128, 372, 44); b.Click += delegate { U.Open(U.Patreon); Close(); };
            Controls.AddRange(new Control[] { q, a, b }); KeyPreview = true; KeyDown += delegate(object s, KeyEventArgs e) { if (e.KeyCode == Keys.Escape) Close(); };
        }
        protected override void OnHandleCreated(EventArgs e) { base.OnHandleCreated(e); Dark.Apply(Handle); }
    }

    // ---------------------------------------------------------------- modern folder picker (IFileOpenDialog, Vista+); falls back to the old dialog
    static class FolderPicker
    {
        [ComImport, Guid("DC1C5A9C-E88A-4DDE-A5A1-60F82A20AEF7")] class FileOpenDialogRCW { }
        [ComImport, Guid("42F85136-DB7E-439C-85F1-E4075D135FC8"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        interface IFileDialog
        {
            [PreserveSig] int Show(IntPtr parent);
            void SetFileTypes(uint c, IntPtr t); void SetFileTypeIndex(uint i); void GetFileTypeIndex(out uint i);
            void Advise(IntPtr p, out uint c); void Unadvise(uint c);
            void SetOptions(uint o); void GetOptions(out uint o);
            void SetDefaultFolder(IShellItem si); void SetFolder(IShellItem si); void GetFolder(out IShellItem si); void GetCurrentSelection(out IShellItem si);
            void SetFileName([MarshalAs(UnmanagedType.LPWStr)] string n); void GetFileName([MarshalAs(UnmanagedType.LPWStr)] out string n);
            void SetTitle([MarshalAs(UnmanagedType.LPWStr)] string t); void SetOkButtonLabel([MarshalAs(UnmanagedType.LPWStr)] string t); void SetFileNameLabel([MarshalAs(UnmanagedType.LPWStr)] string t);
            void GetResult(out IShellItem si); void AddPlace(IShellItem si, int fdap); void SetDefaultExtension([MarshalAs(UnmanagedType.LPWStr)] string e);
            void Close(int hr); void SetClientGuid(ref Guid g); void ClearClientData(); void SetFilter(IntPtr f);
        }
        [ComImport, Guid("43826D1E-E718-42EE-BC55-A1E261C37BFE"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        interface IShellItem
        {
            void BindToHandler(IntPtr pbc, ref Guid bhid, ref Guid riid, out IntPtr ppv); void GetParent(out IShellItem si);
            void GetDisplayName(uint sigdn, [MarshalAs(UnmanagedType.LPWStr)] out string name); void GetAttributes(uint mask, out uint a); void Compare(IShellItem si, uint hint, out int order);
        }
        [DllImport("shell32.dll", CharSet = CharSet.Unicode, PreserveSig = false)]
        static extern void SHCreateItemFromParsingName(string path, IntPtr pbc, ref Guid riid, [MarshalAs(UnmanagedType.Interface)] out IShellItem si);

        public static string Pick(IWin32Window owner, string initial, string title)
        {
            try
            {
                IFileDialog d = (IFileDialog)new FileOpenDialogRCW();
                uint o; d.GetOptions(out o); d.SetOptions(o | 0x20 | 0x40 | 0x1000 /*PICKFOLDERS|FORCEFILESYSTEM|PATHMUSTEXIST*/);
                d.SetTitle(title);
                if (!string.IsNullOrEmpty(initial) && Directory.Exists(initial))
                {
                    Guid g = new Guid("43826D1E-E718-42EE-BC55-A1E261C37BFE"); IShellItem si;
                    try { SHCreateItemFromParsingName(initial, IntPtr.Zero, ref g, out si); d.SetFolder(si); } catch { }
                }
                int hr = d.Show(owner.Handle);
                if (hr != 0) return null;
                IShellItem res; d.GetResult(out res); string path; res.GetDisplayName(0x80058000, out path); return path;
            }
            catch (COMException) { }
            catch (InvalidCastException) { }
            using (FolderBrowserDialog f = new FolderBrowserDialog())
            { f.Description = title; if (Directory.Exists(initial)) f.SelectedPath = initial; return f.ShowDialog(owner) == DialogResult.OK ? f.SelectedPath : null; }
        }
    }

    // ---------------------------------------------------------------- About: selectable text, clickable links
    class AboutForm : Form
    {
        const string DivEditUrl = "https://github.com/Raan/DivEdit";
        RichTextBox rt = new RichTextBox(); List<int[]> spans = new List<int[]>(); List<string> urls = new List<string>();
        void Add(string text, Color c, float pt, FontStyle st, string url)
        {
            int start = rt.TextLength; rt.SelectionStart = start; rt.SelectionLength = 0;
            rt.SelectionColor = c; rt.SelectionFont = Th.F(url != null ? "Segoe UI" : "Segoe UI", pt, url != null ? st | FontStyle.Underline : st);
            rt.SelectedText = text;
            if (url != null) { spans.Add(new int[] { start, start + text.TrimEnd((char)10).Length }); urls.Add(url); }
        }
        public AboutForm()
        {
            Text = U.R("О программе", "About"); FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false; MinimizeBox = false; ShowInTaskbar = false;
            StartPosition = FormStartPosition.CenterParent; ClientSize = new Size(480, 522); BackColor = Th.Bg; ForeColor = Th.Text; Font = Th.Body;
            rt.BorderStyle = BorderStyle.None; rt.BackColor = Th.Surf; rt.ForeColor = Th.Text; rt.ReadOnly = true; rt.DetectUrls = false; rt.ScrollBars = RichTextBoxScrollBars.None; rt.Cursor = Cursors.IBeam;
            rt.SetBounds(24, 22, 432, 356); rt.Font = Th.F("Segoe UI", 10f, FontStyle.Regular);
            Add("GameRemix - By Lex\n", Th.Text, 17f, FontStyle.Bold, null);
            Add(U.R("Исправления и твики для старых игр в одной программе  ·  v", "Fixes and tweaks for old games in one program  ·  v") + App.Version + "\n\n", Th.Muted, 10f, FontStyle.Regular, null);
            Add(U.R("Разработчик:  ", "Developer:  "), Th.Faint, 10f, FontStyle.Regular, null); Add("Lex Volkov\n", Th.Text, 10f, FontStyle.Bold, null);
            Add(U.R("Почта:  ", "E-mail:  "), Th.Faint, 10f, FontStyle.Regular, null); Add("5@1221.by", Th.Amber, 10f, FontStyle.Regular, "mailto:5@1221.by"); Add("\n", Th.Text, 10f, FontStyle.Regular, null);
            Add(U.R("Сайт:  ", "Site:  "), Th.Faint, 10f, FontStyle.Regular, null); Add("speectra.com", Th.Amber, 10f, FontStyle.Regular, "https://speectra.com"); Add("\n\n", Th.Text, 10f, FontStyle.Regular, null);
            Add(U.R("Поддержать автора:\n", "Support the author:\n"), Th.Faint, 10f, FontStyle.Regular, null);
            Add("Boosty:  ", Th.Faint, 10f, FontStyle.Regular, null); Add(U.Boosty + "\n", Th.Amber, 10f, FontStyle.Regular, U.Boosty);
            Add("Patreon:  ", Th.Faint, 10f, FontStyle.Regular, null); Add(U.Patreon + "\n\n", Th.Amber, 10f, FontStyle.Regular, U.Patreon);
            Add(U.R("Для поддержки:  ", "For support:  "), Th.Faint, 10f, FontStyle.Regular, null); Add(U.R("открыть журнал программы", "open the program log"), Th.Amber, 10f, FontStyle.Regular, "ogf://log"); Add("\n\n", Th.Text, 10f, FontStyle.Regular, null);
            Add(U.R("Использованные работы\n", "Credits\n"), Th.Faint, 9f, FontStyle.Bold, null);
            Add(U.R("dgVoodoo2 — Dege · редакторы и компиляторы — Sormy, Igel, iZakaroN · идея патча шрифтов — Losti · фикс FPS — сообщество Steam · ",
                    "dgVoodoo2 — Dege · editors and compilers — Sormy, Igel, iZakaroN · font patch idea — Losti · FPS fix — Steam community · "), Th.Muted, 9f, FontStyle.Regular, null);
            Add("Divinity Graphics Extender — Raan", Th.Amber, 9f, FontStyle.Regular, Dge.Repo); Add(" · ", Th.Muted, 9f, FontStyle.Regular, null); Add("DivEdit — Raan", Th.Amber, 9f, FontStyle.Regular, DivEditUrl); Add(" · ", Th.Muted, 9f, FontStyle.Regular, null);
            Add("gr-draw — "+U.R("наш форк cnc-ddraw", "our fork of cnc-ddraw")+", FunkyFr3sh (MIT)", Th.Amber, 9f, FontStyle.Regular, "https://github.com/FunkyFr3sh/cnc-ddraw");
            rt.MouseMove += delegate(object s, MouseEventArgs e) { rt.Cursor = LinkAt(e.Location) >= 0 ? Cursors.Hand : Cursors.IBeam; };
            rt.MouseUp += delegate(object s, MouseEventArgs e) { if (e.Button == MouseButtons.Left && rt.SelectionLength == 0) { int i = LinkAt(e.Location); if (i >= 0) { if (urls[i] == "ogf://log") { string lf = System.IO.Path.Combine(App.DataDir, "log.txt"); if (System.IO.File.Exists(lf)) U.Open(lf); } else U.Open(urls[i]); } } };
            Btn bs = new Btn(); bs.Accent = true; bs.Text = "♥  Boosty"; bs.Pt = 10f; bs.SetBounds(24, 450, 138, 40); bs.Click += delegate { U.Open(U.Boosty); };
            Btn bp = new Btn(); bp.Accent = true; bp.Text = "♥  Patreon"; bp.Pt = 10f; bp.SetBounds(172, 450, 138, 40); bp.Click += delegate { U.Open(U.Patreon); };
            Btn bc = new Btn(); bc.Text = U.R("Закрыть", "Close"); bc.SetBounds(320, 450, 136, 40); bc.Click += delegate { Close(); };
            Label ua = new Label(); ua.AutoSize = false; ua.SetBounds(24, 392, 230, 40); ua.ForeColor = Th.Muted; ua.UseMnemonic = false; ua.TextAlign = ContentAlignment.MiddleLeft;
            ua.Text = U.R("Обновления программы", "Program updates");   // setting autoupdate=1 in settings.ini; by default the program asks
            Seg us = new Seg(); us.Items = new string[] { U.R("Спрашивать", "Ask"), U.R("Ставить сам", "Install") }; us.SetBounds(262, 395, 194, 34); us.Selected = App.Get("autoupdate") == "1" ? 1 : 0;
            us.Changed += delegate { App.Set("autoupdate", us.Selected == 1 ? "1" : "0"); };
            Controls.AddRange(new Control[] { rt, ua, us, bs, bp, bc }); AcceptButton = null; CancelButton = null;
            KeyPreview = true; KeyDown += delegate(object s, KeyEventArgs e) { if (e.KeyCode == Keys.Escape) Close(); };
            rt.SelectionStart = 0; rt.SelectionLength = 0; ActiveControl = bc;
        }
        // a link is hit only when the pointer is really over one of its characters (GetCharIndexFromPosition returns the NEAREST character, also for a click far beside the text)
        int LinkAt(Point p)
        {
            int idx = rt.GetCharIndexFromPosition(p); int lineH = TextRenderer.MeasureText("Ag", rt.Font).Height;
            for (int i = 0; i < spans.Count; i++)
                if (idx >= spans[i][0] && idx < spans[i][1])
                {
                    Point p0 = rt.GetPositionFromCharIndex(idx), p1 = idx + 1 <= rt.TextLength ? rt.GetPositionFromCharIndex(idx + 1) : p0;
                    int x1 = p1.Y == p0.Y && p1.X > p0.X ? p1.X : p0.X + TextRenderer.MeasureText("W", rt.Font).Width;   // the last character of a line: no next position on the same line
                    Rectangle r = new Rectangle(p0.X, p0.Y, Math.Max(1, x1 - p0.X), lineH);
                    if (r.Contains(p)) return i;
                }
            return -1;
        }
        [DllImport("dwmapi.dll")] static extern int DwmSetWindowAttribute(IntPtr h, int attr, ref int val, int size);
        protected override void OnHandleCreated(EventArgs e) { base.OnHandleCreated(e); Dark.Apply(Handle); }
    }

    static class Dark
    {
        [DllImport("uxtheme.dll", CharSet = CharSet.Unicode)] static extern int SetWindowTheme(IntPtr h, string app, string ids);
        public static void Scroll(Control c) { Action a = delegate { try { SetWindowTheme(c.Handle, Th.Light ? "Explorer" : "DarkMode_Explorer", null); } catch { } }; if (c.IsHandleCreated) a(); else c.HandleCreated += delegate { a(); }; }
        [DllImport("dwmapi.dll")] static extern int DwmSetWindowAttribute(IntPtr h, int attr, ref int val, int size);
        public static void Apply(IntPtr h)
        {
            try
            {
                int one = Th.Light ? 0 : 1; DwmSetWindowAttribute(h, 20, ref one, 4); DwmSetWindowAttribute(h, 19, ref one, 4);   // the dark title bar only for the dark theme
                int cap = Th.Bg.R | (Th.Bg.G << 8) | (Th.Bg.B << 16), txt = Th.Text.R | (Th.Text.G << 8) | (Th.Text.B << 16);
                DwmSetWindowAttribute(h, 35, ref cap, 4); DwmSetWindowAttribute(h, 36, ref txt, 4);
            }
            catch { }
        }
    }

    // ---------------------------------------------------------------- fonts: choose + preview (real glyphs of the game's .fnt files, 1:1)
    class FontPreview : Control
    {
        public Bitmap[][] Lines; public string[] Caps, Info; public int Sel; public bool Paper;   // one panel per choice; Paper = book fonts are drawn on parchment, as in the game
        public event Action<int> Picked;   // the player chose a card (click or arrow keys); owner rule 06.11: the choice is made ON the preview cards, there are no duplicate buttons
        int hot = -1;
        public FontPreview() { SetStyle(ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw | ControlStyles.Selectable, true); TabStop = true; BackColor = Th.Bg; }
        int CardAt(int x) { int n = Lines == null ? 0 : Lines.Length; if (n == 0) return -1; int w = (Width - 8 * (n - 1)) / n; int v = x / (w + 8); return v >= 0 && v < n && x - v * (w + 8) < w ? v : -1; }
        void Pick(int v) { if (!Enabled || v < 0 || Lines == null || v >= Lines.Length) return; if (v != Sel) { Sel = v; if (Picked != null) Picked(v); } Invalidate(); }
        protected override void OnEnabledChanged(EventArgs e) { base.OnEnabledChanged(e); Cursor = Enabled ? Cursors.Hand : Cursors.Default; Invalidate(); }
        protected override void OnMouseMove(MouseEventArgs e) { int v = CardAt(e.X); if (v != hot) { hot = v; Invalidate(); } base.OnMouseMove(e); }
        protected override void OnMouseLeave(EventArgs e) { hot = -1; Invalidate(); base.OnMouseLeave(e); }
        protected override void OnMouseDown(MouseEventArgs e) { if (Enabled) Focus(); Pick(CardAt(e.X)); base.OnMouseDown(e); }
        protected override bool IsInputKey(Keys k) { return k == Keys.Left || k == Keys.Right || k == Keys.Up || k == Keys.Down || base.IsInputKey(k); }
        protected override void OnKeyDown(KeyEventArgs e)
        {
            if (Lines != null && Enabled)
            {
                if (e.KeyCode == Keys.Left || e.KeyCode == Keys.Up) { Pick(Math.Max(0, Sel - 1)); e.Handled = true; }
                else if (e.KeyCode == Keys.Right || e.KeyCode == Keys.Down) { Pick(Math.Min(Lines.Length - 1, Sel + 1)); e.Handled = true; }
                else if (e.KeyCode == Keys.Enter || e.KeyCode == Keys.Space) { Pick(Sel); e.Handled = true; }
            }
            base.OnKeyDown(e);
        }
        protected override void OnGotFocus(EventArgs e) { base.OnGotFocus(e); Invalidate(); }
        protected override void OnLostFocus(EventArgs e) { base.OnLostFocus(e); Invalidate(); }
        protected override void Dispose(bool disposing)   // the preview bitmaps are GDI+ objects: they are released with the control
        {
            if (disposing && Lines != null) { foreach (Bitmap[] row in Lines) if (row != null) foreach (Bitmap b in row) if (b != null) b.Dispose(); Lines = null; }
            base.Dispose(disposing);
        }
        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics; g.SmoothingMode = SmoothingMode.AntiAlias; g.InterpolationMode = InterpolationMode.NearestNeighbor; g.PixelOffsetMode = PixelOffsetMode.Half; g.Clear(Th.Bg);
            if (Lines == null) return;
            int n = Lines.Length, w = (Width - 8 * (n - 1)) / n; Color fill = Paper ? Color.FromArgb(205, 187, 137) : Color.FromArgb(24, 21, 16), cap = Paper ? Color.FromArgb(92, 72, 40) : Color.FromArgb(150, 141, 122);   // the game's glyphs are light: the cards stay dark in every theme
            for (int v = 0; v < n; v++)
            {
                Rectangle r = new Rectangle(v * (w + 8), 0, w, Height - 1); bool sel = v == Sel;
                bool on = sel || (v == hot && Enabled);
                using (GraphicsPath p = Th.RR(new RectangleF(r.X + 0.5f, r.Y + 0.5f, r.Width - 1, r.Height - 1), 8))
                { using (SolidBrush b = new SolidBrush(fill)) g.FillPath(b, p); if (!on) using (Pen pen = new Pen(Th.Line, 1f)) g.DrawPath(pen, p); }
                if (on)   // ONE outline for every group and both themes, from FIXED colours (theme colours vanished on the dark cards in the light theme): [dark hairline][gold 2 px][contour in the colour opposite to the card]; the gold band is flanked by contrast on both sides on beige and dark cards alike
                {
                    float k = sel ? 1f : 0.55f; Color gold = Color.FromArgb(244, 190, 60), hair = Color.FromArgb(32, 22, 6), inner = Paper ? Color.FromArgb(70, 44, 10) : Color.FromArgb(255, 246, 220);
                    using (GraphicsPath p0 = Th.RR(new RectangleF(r.X + 0.5f, r.Y + 0.5f, r.Width - 1, r.Height - 1), 8)) using (Pen pen = new Pen(Th.Mix(fill, hair, k), 1f)) g.DrawPath(pen, p0);
                    using (GraphicsPath p1 = Th.RR(new RectangleF(r.X + 2f, r.Y + 2f, r.Width - 4, r.Height - 5), 7)) using (Pen pen = new Pen(Th.Mix(fill, gold, k), sel ? 2f : 1.5f)) g.DrawPath(pen, p1);
                    using (GraphicsPath p2 = Th.RR(new RectangleF(r.X + 3.5f, r.Y + 3.5f, r.Width - 7, r.Height - 8), 6)) using (Pen pen = new Pen(Th.Mix(fill, inner, sel ? 0.9f : 0.5f), 1f)) g.DrawPath(pen, p2);
                }
                if (sel && Focused && Enabled) ControlPaint.DrawFocusRectangle(g, new Rectangle(r.X + 6, r.Y + 6, r.Width - 12, r.Height - 12));
                TextFit.Draw(g, this, Caps[v], Th.Small, new Rectangle(r.X + 10, r.Y + 6, r.Width - 20, 14), sel && !Paper ? Color.FromArgb(222, 168, 66) : cap, TextFormatFlags.NoPadding);
                int y = r.Y + 24; bool any = false; Rectangle clip = new Rectangle(r.X + 5, r.Y + 22, r.Width - 10, r.Height - 44);   // never draws over the border, caption or the info line
                g.SetClip(clip);
                foreach (Bitmap b in Lines[v]) { if (b == null) continue; any = true; g.DrawImage(b, new Rectangle(r.X + 8, y, b.Width, b.Height)); y += b.Height + 3; }
                g.ResetClip();
                if (!any) TextFit.Draw(g, this, U.R("предпросмотр недоступен", "preview unavailable"), Th.Small, new Rectangle(r.X + 10, r.Y + 28, r.Width - 20, 16), cap, TextFormatFlags.NoPadding);
                TextFit.Draw(g, this, Info[v], Th.Small, new Rectangle(r.X + 10, r.Bottom - 20, r.Width - 20, 14), cap, TextFormatFlags.NoPadding);
            }
        }
    }

    // three groups. Russian: Original | Large (the owner's pack) | Extra large (that pack scaled). English: Original | Larger | Extra large (scaled from the game's own fonts).
    // The preview text follows the interface language and draws the real glyphs of what each choice would put into the game.
    class FontForm : Form
    {
        Core core; FontPreview[] pv = new FontPreview[3]; int[] cur = new int[3]; int[][] map = new int[3][]; bool[] touched = new bool[3];
        public FontForm(Core c)
        {
            core = c; Text = U.R("Шрифты", "Fonts"); FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false; MinimizeBox = false; ShowInTaskbar = false;
            StartPosition = FormStartPosition.CenterParent; BackColor = Th.Bg; ForeColor = Th.Text; Font = Th.Body;
            string[] names = { U.R("ОСНОВНЫЕ ШРИФТЫ (интерфейс, предметы)", "GENERAL FONTS (interface, items)"), U.R("ШРИФТЫ КНИГ И ДНЕВНИКА", "BOOK AND DIARY FONTS"), U.R("ШРИФТЫ ДИАЛОГОВ", "DIALOG FONTS") };
            string[] items = L.Ru ? new string[] { "Оригинал игры", "Крупные", "Сверхкрупные" } : (L.Ko ? new string[] { "원본", "크게", "매우 크게" } : new string[] { "Original", "Larger", "Extra large" }); string[] caps = L.Ru ? new string[] { "ОРИГИНАЛ ИГРЫ", "КРУПНЫЕ", "СВЕРХКРУПНЫЕ" } : (L.Ko ? new string[] { "원본", "크게", "매우 크게" } : new string[] { "ORIGINAL", "LARGER", "EXTRA LARGE" });
            int[] steps = L.Ru ? new int[] { 0, 3, 4 } : new int[] { 0, 1, 2 };
            string[][] samples = { new string[] { "fontn2.fnt", "fontn3.fnt", "fontn4.fnt", "fontn5.fnt" }, new string[] { "fontblack1.fnt", "fontblack2.fnt" }, new string[] { "dialog_white.fnt", "dialog_yellow.fnt", "dialog_red.fnt", "dialog_grey.fnt" } };
            string text = U.R("Привет, друг!", "Hello, friend!");
            Panel host = new Panel(); host.BackColor = Th.Bg; host.SetBounds(0, 0, 640, 100); Controls.Add(host);   // all groups live here; when the screen is low this panel scrolls
            Label note = new Label(); note.AutoSize = false; note.SetBounds(24, 8, 592, 30); note.Font = Th.Small; note.ForeColor = Th.Muted; note.BackColor = Th.Bg;
            note.Text = U.R("Нажмите на карточку, чтобы выбрать. Оригинал — шрифты самой игры; Крупные и Сверхкрупные — увеличенные шрифты из программы.", "Click a card to choose. Original: the game's own fonts; Larger / Extra large: bigger fonts from the program."); host.Controls.Add(note);
            int y = 40;
            for (int i = 0; i < 3; i++)
            {
                int k = i; cur[i] = core.FontStep(i); map[i] = steps; bool custom = core.FontIsCustom(i);
                string ltxt = custom ? U.R("ВАШИ ШРИФТЫ (не наши)", "YOUR OWN FONTS") : names[i]; int lw = Math.Min(480, TextRenderer.MeasureText(ltxt, Th.Small, new Size(600, 20), TextFormatFlags.NoPadding).Width + 4);   // the label is exactly as wide as its text: the "?" next to it must not lie under the label (a later control sits BELOW an earlier one in WinForms)
                Label l = new Label(); l.AutoSize = false; l.SetBounds(24, y + 6, lw, 18); l.Font = Th.Small; l.ForeColor = custom ? Th.Red : Th.Amber; l.BackColor = Th.Bg; l.UseMnemonic = false; l.Text = ltxt; host.Controls.Add(l);
                Btn fh = new Btn(); fh.Under = Th.Bg; fh.Pt = 8f; fh.Text = "?"; fh.Size = new Size(24, 24); fh.Location = new Point(24 + lw + 8, y + 3); fh.Click += delegate { Help.Show(this, "fonts_group"); }; host.Controls.Add(fh);   // the same "?" as on the Graphics page (24x24, Help.Show)
                int idx = 0; if (cur[i] > 0) { idx = (cur[i] == 1 || cur[i] == 3) ? 1 : items.Length - 1; for (int j = 0; j < steps.Length; j++) if (steps[j] == cur[i]) idx = j; }   // a state the other language doesn't list shows as its biggest choice
                pv[i] = new FontPreview(); pv[i].Paper = i == 1; pv[i].Lines = new Bitmap[items.Length][]; pv[i].Caps = new string[items.Length]; pv[i].Info = new string[items.Length]; int tall = 0;
                for (int st = 0; st < items.Length; st++)
                {
                    List<Bitmap> ls = new List<Bitmap>(); int hh = 0; string px = "";
                    foreach (string t in samples[i])
                    {
                        byte[] b = cur[i] >= 0 ? core.FontSrc(i, steps[st], t) : null; Bitmap bm = null;
                        if (b != null) { try { MlFont f = MlFont.Parse(b); if (f.Glyphs.Count > 0) bm = f.Render(text); } catch { bm = null; } }   // a broken font file = "preview unavailable", never a crash
                        if (bm != null) { hh += bm.Height + 3; px += (px.Length > 0 ? " · " : "") + bm.Height; }
                        ls.Add(bm);
                    }
                    pv[i].Lines[st] = ls.ToArray(); pv[i].Caps[st] = caps[st]; pv[i].Info[st] = px.Length > 0 ? px + " px" : ""; tall = Math.Max(tall, hh);
                }
                if (core.FontIsBrokenRd(i)) { idx = 0; touched[i] = true; }   // the withdrawn 1.0.11 "redrawn" files: the window proposes the original (Apply puts it back)
                pv[i].Sel = idx;
                pv[i].Picked += delegate(int v) { touched[k] = true; };
                pv[i].Enabled = cur[i] >= 0; pv[i].TabIndex = i;
                pv[i].SetBounds(24, y + 36, 592, Math.Max(60, tall + 24 + 24)); host.Controls.Add(pv[i]);
                y += 36 + pv[i].Height + 14;
            }
            int contentH = y + 4, maxH = Math.Max(300, Fit.WorkArea().Height - 160);   // buttons stay visible below; a low screen scrolls the groups
            if (contentH > maxH) { host.AutoScroll = true; host.Width = 640; host.Height = maxH; Dark.Scroll(host); } else host.Height = contentH;
            int by = host.Height + 6;
            Btn ap = new Btn(); ap.Accent = true; ap.Text = U.R("Применить", "Apply"); ap.Pt = 10f; ap.SetBounds(24, by, 290, 40);
            Btn cl = new Btn(); cl.Text = U.R("Закрыть", "Close"); cl.SetBounds(326, by, 290, 40); cl.Click += delegate { Close(); };
            ap.Click += delegate
            {
                if (Core.GameRunning()) { MessageBox.Show(this, L.T("running"), L.T("warnTitle")); return; }
                try { for (int i = 0; i < 3; i++) if (pv[i].Enabled && touched[i] && (map[i][pv[i].Sel] != cur[i] || core.FontIsBrokenRd(i))) { core.SetFontStep(i, map[i][pv[i].Sel]); cur[i] = core.FontStep(i); } Close(); }
                catch (Exception ex) { MessageBox.Show(this, ex.Message, L.T("errTitle"), MessageBoxButtons.OK, MessageBoxIcon.Error); }
            };
            Controls.AddRange(new Control[] { ap, cl }); ClientSize = new Size(640, by + 40 + 20);
        }
        protected override void OnHandleCreated(EventArgs e) { base.OnHandleCreated(e); Dark.Apply(Handle); }
    }
}
