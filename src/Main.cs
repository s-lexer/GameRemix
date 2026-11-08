// GameRemix main window: sidebar (game picker, pages, footer) + pages of one-line rows. Rules: docs/design.md.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
using System.Net;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Windows.Forms;

namespace DDFixTool
{
    static class App
    {
        public const string Name = "GameRemix - By Lex", Version = "1.0.33";
        public const string UpdateUrl = "https://gameremix.pro/dl/latest.txt";   // one line: "<version>|<download url>|<sha256>"
        public const string Mail = "5@1221.by";
        public static Image Icon(string id) { using (MemoryStream ms = new MemoryStream(Core.ResBytes("icon_" + id))) return new Bitmap(Image.FromStream(ms)); }   // game icons ship inside the program, so they show even when the game is not installed
        public static bool ReadOnly;   // self-check mode (--shot ...): nothing is written to the user's data (settings, log, saved game path)
        // OGF_DATA redirects the per-user data folder (tests run against a scratch folder, never against the real profile)
        static string dataDir, localDir;
        public static string DataDir
        {
            get
            {
                if (dataDir == null)
                {
                    string o = Environment.GetEnvironmentVariable("OGF_DATA");
                    string d = !string.IsNullOrEmpty(o) ? o : Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "GameRemix");
                    if (!ReadOnly) d = Migrate.Data(d);   // OldGameFixer -> GameRemix (see Migrate.cs); returns the old folder when the copy failed
                    dataDir = d;
                }
                if (!ReadOnly || Directory.Exists(dataDir)) Directory.CreateDirectory(dataDir);
                return dataDir;
            }
        }
        // %LOCALAPPDATA%\GameRemix: unpacked program (app), cache, tools. OGF_LOCAL redirects it (tests).
        public static string LocalDir
        {
            get
            {
                if (localDir == null)
                {
                    string o = Environment.GetEnvironmentVariable("OGF_LOCAL");
                    string d = !string.IsNullOrEmpty(o) ? o : Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "GameRemix");
                    if (!ReadOnly) Migrate.Local(d);
                    localDir = d;
                }
                return localDir;
            }
        }
        public static void RotateLog()   // the log must not grow forever: over 1 MB -> keep the last ~256 KB (from a line start)
        {
            try
            {
                string f = Path.Combine(DataDir, "log.txt"); FileInfo fi = new FileInfo(f); if (!fi.Exists || fi.Length <= 1048576) return;
                byte[] b = File.ReadAllBytes(f); int keep = 262144, st = b.Length - keep; while (st < b.Length && b[st] != 10) st++; st++;
                byte[] t = new byte[Math.Max(0, b.Length - st)]; Array.Copy(b, st, t, 0, t.Length); File.WriteAllBytes(f, t);
            }
            catch { }
        }
        // settings live in the user's profile: %APPDATA%\GameRemix\settings.ini (key=value). Nothing is written next to the program.
        static string SetFile { get { return Path.Combine(DataDir, "settings.ini"); } }
        public static string Get(string k) { try { if (File.Exists(SetFile)) foreach (string ln in File.ReadAllLines(SetFile, Encoding.UTF8)) { int i = ln.IndexOf('='); if (i > 0 && ln.Substring(0, i) == k) return ln.Substring(i + 1); } } catch { } return null; }
        public static void Set(string k, string v)
        {
            if (ReadOnly) return;
            try
            {
                List<string> l = new List<string>(); if (File.Exists(SetFile)) foreach (string ln in File.ReadAllLines(SetFile, Encoding.UTF8)) { int i = ln.IndexOf('='); if (i > 0 && ln.Substring(0, i) != k) l.Add(ln); }
                l.Add(k + "=" + v); File.WriteAllLines(SetFile, l.ToArray(), Encoding.UTF8);
            }
            catch { }
        }
        public static bool Newer(string a, string b)   // is a newer than b
        {
            try { return new Version(a.Trim()) > new Version(b.Trim()); } catch { return false; }
        }
        public static bool ValidVersion(string v)   // N.N or N.N.N or N.N.N.N, digits only
        {
            return v != null && System.Text.RegularExpressions.Regex.IsMatch(v, @"^\d{1,4}(\.\d{1,4}){1,3}$");
        }
    }

    // a game known to the program. Only Ready ones have code behind them; the rest are the roadmap (see games/*/research)
    class GameDef
    {
        public string Id, Name, Mono; public int Fixes; public bool Ready;
        public GameDef(string id, string name, string mono, int fixes, bool ready) { Id = id; Name = name; Mono = mono; Fixes = fixes; Ready = ready; }
        public static readonly GameDef[] All = {
            new GameDef("dd", "Divine Divinity", "DD", 5, true), new GameDef("bd", "Beyond Divinity", "BD", 0, false), new GameDef("d2", "Diablo II", "D2", 0, false),
            new GameDef("f2", "Fallout 2", "F2", 0, false), new GameDef("g2", "Gothic II", "G2", 0, false), new GameDef("mp", "Max Payne", "MP", 0, false), new GameDef("iw", "Icewind Dale", "IW", 0, false) };
    }

    // ---------------------------------------------------------------- panels
    class RPanel : Panel
    {
        public Color Fill = Th.Surf; public int Radius = 12;
        public RPanel() { SetStyle(ControlStyles.UserPaint | ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true); BackColor = Th.Surf; }
        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics; g.SmoothingMode = SmoothingMode.AntiAlias; g.Clear(Th.Bg);
            using (GraphicsPath p = Th.RR(new RectangleF(0.5f, 0.5f, Width - 1.5f, Height - 1.5f), Radius))
            { using (SolidBrush b = new SolidBrush(Fill)) g.FillPath(b, p); using (Pen pen = new Pen(Th.Line)) g.DrawPath(pen, p); }
        }
    }

    class SecHead : Control
    {
        public SecHead(string text) { SetStyle(ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true); Text = text; Height = 22; BackColor = Th.Surf; }
        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics; g.Clear(Th.Surf);
            string t = Text.ToUpper(); Size sz = TextRenderer.MeasureText(g, t, Th.Small, new Size(Width, Height), TextFormatFlags.NoPadding | TextFormatFlags.NoPrefix);
            TextFit.Draw(g, this, t, Th.Small, new Rectangle(2, 0, sz.Width + 2, Height), Th.Faint, TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding | TextFormatFlags.NoPrefix);
            using (Pen p = new Pen(Th.Line)) g.DrawLine(p, sz.Width + 14, Height / 2, Width - 2, Height / 2);
        }
    }

    // ---------------------------------------------------------------- one-line row: icon | title | description | status | control (one grid for every row)
    class RowCtl : Control
    {
        public const int H = 44, IC = 32, TW = 176, SW = 92, CW = 92, Gp = 12, PadL = 10, PadR = 12;
        public string Glyph = "", Title = "", Desc = "", Status = ""; public Color StatusColor = Th.Faint, GlyphColor = Th.Muted;
        Control ctl; bool hover; public event Action<RowCtl, bool> DescHover; bool inDesc; Btn help;
        // small "?" at the right end of the title column; opens a help window
        public EventHandler HelpClick { set { if (help == null) { help = new Btn(); help.Under = Th.Inset; help.Pt = 8f; help.Text = "?"; help.Size = new Size(24, 24); help.Location = new Point(PadL + IC + Gp + TW - 26, (H - 24) / 2); Controls.Add(help); } help.Click += value; } }
        public RowCtl() { SetStyle(ControlStyles.UserPaint | ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true); Height = H; BackColor = Th.Inset; }
        public Control Ctl { get { return ctl; } set { ctl = value; Controls.Add(ctl); ctl.MouseEnter += delegate { SetHover(true); }; ctl.MouseLeave += delegate { RecheckHover(); }; PlaceCtl(); } }
        int CWid { get { return ctl != null && ctl.Width > CW ? ctl.Width : CW; } }
        int CtlX { get { return Width - PadR - CWid; } }
        int StX { get { return CtlX - Gp - SW; } }
        int DescX { get { return PadL + IC + Gp + TW + Gp; } }
        Rectangle DescR { get { return new Rectangle(DescX, 0, Math.Max(0, StX - Gp - DescX), H); } }
        void PlaceCtl() { if (ctl != null) ctl.Location = new Point(CtlX + (CWid - ctl.Width) / 2, (H - ctl.Height) / 2); }
        protected override void OnResize(EventArgs e) { base.OnResize(e); PlaceCtl(); }
        void SetHover(bool h) { if (h != hover) { hover = h; Invalidate(); } }
        void RecheckHover() { SetHover(ClientRectangle.Contains(PointToClient(Cursor.Position))); }
        protected override void OnMouseEnter(EventArgs e) { SetHover(true); base.OnMouseEnter(e); }
        protected override void OnMouseLeave(EventArgs e) { RecheckHover(); if (!hover) SetDesc(false); base.OnMouseLeave(e); }
        void SetDesc(bool on) { if (on != inDesc) { inDesc = on; if (DescHover != null) DescHover(this, on); } }
        bool Clipped { get { return TextRenderer.MeasureText(Desc, Th.F("Segoe UI", 8.5f, FontStyle.Regular), new Size(int.MaxValue, H), TextFormatFlags.NoPadding | TextFormatFlags.NoPrefix | TextFormatFlags.SingleLine).Width > DescR.Width; } }
        protected override void OnMouseMove(MouseEventArgs e) { SetDesc(Desc.Length > 0 && DescR.Contains(e.Location) && Clipped); base.OnMouseMove(e); }
        public Rectangle DescRect { get { return DescR; } }
        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics; g.SmoothingMode = SmoothingMode.AntiAlias; g.Clear(Th.Surf);
            Color fill = hover && Enabled ? Th.Mix(Th.Inset, Th.SurfHi, 0.45f) : Th.Inset;
            using (GraphicsPath p = Th.RR(new RectangleF(0.5f, 0.5f, Width - 1.5f, Height - 1.5f), 9))
            { using (SolidBrush b = new SolidBrush(fill)) g.FillPath(b, p); using (Pen pen = new Pen(hover ? Th.Line : fill)) g.DrawPath(pen, p); }
            Rectangle ir = new Rectangle(PadL, (H - IC) / 2, IC, IC);
            using (GraphicsPath p = Th.RR(ir, 8)) using (SolidBrush b = new SolidBrush(Th.A(Th.Tint, 12))) g.FillPath(b, p);
            TextRenderer.DrawText(g, Glyph, Th.F("Segoe UI Symbol", 11f, FontStyle.Regular), ir, GlyphColor, TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding | TextFormatFlags.NoPrefix);
            TextFormatFlags one = TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding | TextFormatFlags.NoPrefix | TextFormatFlags.EndEllipsis | TextFormatFlags.SingleLine;
            TextFit.Draw(g, this, Title, Th.F("Segoe UI Semibold", 9.5f, FontStyle.Regular), new Rectangle(PadL + IC + Gp, 0, TW, H), Th.Text, one);
            TextFit.Draw(g, this, Desc, Th.F("Segoe UI", 8.5f, FontStyle.Regular), DescR, Th.Muted, one);
            TextFit.Draw(g, this, Status, Th.F("Segoe UI Semibold", 8.5f, FontStyle.Regular), new Rectangle(StX, 0, SW, H), StatusColor, one | TextFormatFlags.HorizontalCenter);
        }
    }

    // ---------------------------------------------------------------- sidebar controls
    class NavItem : Control
    {
        public string Glyph = "", Label = "", Count = ""; public Color Chip = Th.Amber; public bool On; bool hover;
        public NavItem() { SetStyle(ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true); Cursor = Cursors.Hand; Height = 42; BackColor = Th.Bg; }
        protected override void OnMouseEnter(EventArgs e) { hover = true; Invalidate(); base.OnMouseEnter(e); }
        protected override void OnMouseLeave(EventArgs e) { hover = false; Invalidate(); base.OnMouseLeave(e); }
        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics; g.SmoothingMode = SmoothingMode.AntiAlias; g.Clear(Th.Bg);
            if (On || hover) using (GraphicsPath p = Th.RR(new RectangleF(0.5f, 0.5f, Width - 1.5f, Height - 1.5f), 9)) using (SolidBrush b = new SolidBrush(Th.A(Th.Tint, On ? 20 : 9))) g.FillPath(b, p);
            Rectangle cr = new Rectangle(10, 7, 28, 28);
            using (GraphicsPath p = Th.RR(cr, 8)) using (SolidBrush b = new SolidBrush(Chip)) g.FillPath(b, p);
            TextRenderer.DrawText(g, Glyph, Th.F("Segoe UI Symbol", 10f, FontStyle.Regular), cr, Color.White, TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding | TextFormatFlags.NoPrefix);
            TextFit.Draw(g, this, Label, Th.F("Segoe UI Semibold", 10f, FontStyle.Regular), new Rectangle(48, 0, Width - 48 - 36, Height), Th.Text, TextFormatFlags.VerticalCenter | TextFormatFlags.NoPrefix | TextFormatFlags.NoPadding | TextFormatFlags.EndEllipsis | TextFormatFlags.SingleLine);
            TextFit.Draw(g, this, Count, Th.F("Segoe UI", 9f, FontStyle.Regular), new Rectangle(Width - 36, 0, 26, Height), Th.Faint, TextFormatFlags.VerticalCenter | TextFormatFlags.Right | TextFormatFlags.NoPadding);
        }
    }

    // "Выбрана игра" card: the icon is taken from the game's exe
    class PickBtn : Control
    {
        public Image Icon; public string Mono = "", GameName = "", Small = ""; bool hover;
        public PickBtn() { SetStyle(ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true); Cursor = Cursors.Hand; Height = 56; BackColor = Th.Bg; }
        protected override void OnMouseEnter(EventArgs e) { hover = true; Invalidate(); base.OnMouseEnter(e); }
        protected override void OnMouseLeave(EventArgs e) { hover = false; Invalidate(); base.OnMouseLeave(e); }
        public static void DrawIcon(Graphics g, Image icon, string mono, Rectangle r)
        {
            if (icon != null) { g.InterpolationMode = InterpolationMode.NearestNeighbor; g.PixelOffsetMode = PixelOffsetMode.Half; g.DrawImage(icon, r); g.PixelOffsetMode = PixelOffsetMode.Default; g.InterpolationMode = InterpolationMode.HighQualityBicubic; return; }
            using (GraphicsPath p = Th.RR(r, 10)) using (Pen pen = new Pen(Th.Line) { DashStyle = DashStyle.Dash }) g.DrawPath(pen, p);
            TextRenderer.DrawText(g, mono, Th.F("Segoe UI Semibold", Math.Max(8f, r.Width / 3.4f), FontStyle.Regular), r, Th.Faint, TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding);
        }
        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics; g.SmoothingMode = SmoothingMode.AntiAlias; g.Clear(Th.Bg);
            using (GraphicsPath p = Th.RR(new RectangleF(0.5f, 0.5f, Width - 1.5f, Height - 1.5f), 12))
            { using (SolidBrush b = new SolidBrush(hover ? Th.SurfHi : Th.Surf)) g.FillPath(b, p); using (Pen pen = new Pen(Th.Line)) g.DrawPath(pen, p); }
            DrawIcon(g, Icon, Mono, new Rectangle(12, 12, 32, 32));
            TextFit.Draw(g, this, Small, Th.F("Segoe UI", 8f, FontStyle.Regular), new Rectangle(54, 9, Width - 54 - 28, 14), Th.Muted, TextFormatFlags.NoPadding | TextFormatFlags.EndEllipsis | TextFormatFlags.SingleLine);
            TextFit.Draw(g, this, GameName, Th.F("Segoe UI Semibold", 10.5f, FontStyle.Regular), new Rectangle(54, 24, Width - 54 - 28, 22), Th.Text, TextFormatFlags.NoPadding | TextFormatFlags.EndEllipsis | TextFormatFlags.SingleLine);
            TextRenderer.DrawText(g, "▾", Th.F("Segoe UI Symbol", 9f, FontStyle.Regular), new Rectangle(Width - 26, 0, 20, Height), Th.Faint, TextFormatFlags.VerticalCenter | TextFormatFlags.HorizontalCenter | TextFormatFlags.NoPadding);
        }
    }

    class GameTile : Control
    {
        public GameDef Def; public Image Icon; public bool Sel, Plus; public string Sub = ""; bool hover;
        public GameTile() { SetStyle(ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true); Cursor = Cursors.Hand; BackColor = Th.SurfHi; }
        protected override void OnMouseEnter(EventArgs e) { hover = true; Invalidate(); base.OnMouseEnter(e); }
        protected override void OnMouseLeave(EventArgs e) { hover = false; Invalidate(); base.OnMouseLeave(e); }
        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics; g.SmoothingMode = SmoothingMode.AntiAlias; g.Clear(Th.SurfHi);
            bool dim = Def != null && !Def.Ready;
            using (GraphicsPath p = Th.RR(new RectangleF(0.5f, 0.5f, Width - 1.5f, Height - 1.5f), 12))
            { using (SolidBrush b = new SolidBrush(Th.Inset)) g.FillPath(b, p); using (Pen pen = new Pen(Sel || hover ? Th.Amber : Th.Line, Sel ? 1.5f : 1f)) g.DrawPath(pen, p); }
            PickBtn.DrawIcon(g, Icon, Plus ? "+" : Def.Mono, new Rectangle((Width - 64) / 2, 18, 64, 64));
            TextFit.Draw(g, this, Plus ? U.R("Нет вашей игры?", "Your game missing?") : Def.Name, Th.F("Segoe UI Semibold", 9f, FontStyle.Regular), new Rectangle(6, 92, Width - 12, 20), dim ? Th.Muted : Th.Text, TextFormatFlags.HorizontalCenter | TextFormatFlags.NoPadding | TextFormatFlags.EndEllipsis | TextFormatFlags.SingleLine);
            TextFit.Draw(g, this, Sub, Th.F("Segoe UI", 8f, FontStyle.Regular), new Rectangle(6, 112, Width - 12, 16), Def != null && Def.Ready ? Th.Amber : Th.Faint, TextFormatFlags.HorizontalCenter | TextFormatFlags.NoPadding | TextFormatFlags.EndEllipsis | TextFormatFlags.SingleLine);
        }
    }

    // ---------------------------------------------------------------- main window (client 1020 x 700, fixed)
    partial class MainForm : Form
    {
        [DllImport("uxtheme.dll", CharSet = CharSet.Unicode)] static extern int SetWindowTheme(IntPtr h, string app, string ids);
        const int CW = 1020, CH = 700, M = 12, SideW = 204, MainX = M + SideW + 12, MainW = CW - MainX - M, MainH = CH - M * 2;
        Core core; bool busy; string page = "fix"; GameDef game = GameDef.All[0];
        bool pathUnavailable; string unavailPath = ""; List<string> pendingChoice; List<string> notes = new List<string>(); int cntFix, cntSec, cntTools; Btn bSend, bAssets; bool sendBusy;
        PickBtn pick; NavItem[] nav = new NavItem[5]; RPanel foot, pop; Btn bSup, bAbout, bFb, bUpd, bNew; Seg segLang, segTheme;
        readonly Dictionary<string, Panel> pages = new Dictionary<string, Panel>(); TipForm tip = new TipForm();
        Image gameIcon = App.Icon("dd"); Field reqBox; string newVer, newUrl, updText = ""; UpdateInfo upd; bool bootCheck = true; Btn bBadge; System.Windows.Forms.Timer updTimer; bool updBusy;
        Btn bPlay, bLnk, bQuick; Label lPath, lLnk; Btn bRevert;
        RowCtl rVer, rVoice, rDusk, rCnc, rDgv, rGfx, rFonts, rAssets, rSmooth, rBone, rSaves;
        Seg sVoice, sDusk, sDgv, sCnc, sSmooth, sBone; Btn bFonts;

        public MainForm(string initial)
        {
            Text = App.Name; BackColor = Th.Bg; ForeColor = Th.Text; Font = Th.Body; StartPosition = FormStartPosition.CenterScreen; DoubleBuffered = true;
            FormBorderStyle = FormBorderStyle.FixedSingle; MaximizeBox = false; Fit.To(this, new Size(CW, CH));   // 1020x700, or the screen's working area with scrolling when the screen is lower
            try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { }
            core = NewCore(""); Deactivate += delegate { tip.Hide(); }; FormClosing += delegate { tip.Close(); };
            MouseDown += delegate { HidePicker(); };
            string lg = App.Get("lang"); if (lg != null && !L.Forced) L.Ru = lg == "ru";
            string last = initial ?? LoadLast();
            if (last != null && last.Length > 0 && File.Exists(Path.Combine(Core.NormPath(last), "div.exe"))) SetPath(last, false);
            else if (last != null && last.Length > 0) { pathUnavailable = true; unavailPath = last; core = NewCore(last); Log("saved game folder is not available: " + last); }   // unplugged drive / network: keep the saved path, do NOT pick another install in its place
            else AutoDetect();
            BuildAll();
            Shown += delegate
            {
                if (TextFit.Probe) return;   // the text-fit self-test only paints the pages: no default fixes, no questions
                if (!App.ReadOnly)
                {
                    Updater.Cleanup();   // .old / .new left by the previous update
                    Thread t = new Thread(CheckUpdate); t.IsBackground = true; t.Start(false);
                    updTimer = new System.Windows.Forms.Timer(); updTimer.Interval = 6 * 3600 * 1000; updTimer.Tick += delegate { if (!updBusy) { Thread t2 = new Thread(CheckUpdate); t2.IsBackground = true; t2.Start(false); } }; updTimer.Start();   // and every ~6 hours while the window is open
                    RefreshNewBadge();   // "What's new" is not opened by itself: its button shows how many versions were not looked at yet
                }
                if (pendingChoice != null) { pendingChoice = null; ChooseFolder(); }   // several installs found on the first start: let the player pick
                DefaultFixes();
                if (!App.ReadOnly) { try { core.RepairShortcut(); } catch { } }
            };
        }

        public void ShotPage(string w) { if (w == "picker") TogglePicker(); else if (w == "gfxstep2") { GoPage("gfx"); GfxStep2(true); } else GoPage(w); Application.DoEvents(); }
        Core NewCore(string p) { Core c = new Core(p); c.Log = Log; c.Warn = delegate(string m) { notes.Add(m); }; return c; }
        void FlushNotes() { if (notes.Count == 0) return; string m = string.Join("\r\n\r\n", notes.ToArray()); notes.Clear(); MessageBox.Show(this, m, L.T("warnTitle"), MessageBoxButtons.OK, MessageBoxIcon.Warning); }
        // open a window inside protection: a failure while building it is reported, never crashes the program
        void Dlg(Func<Form> make) { tip.Hide(); try { using (Form f = make()) f.ShowDialog(this); } catch (Exception ex) { Log(L.T("errTitle") + ": " + ex); MessageBox.Show(this, ex.Message, L.T("errTitle"), MessageBoxButtons.OK, MessageBoxIcon.Error); } }
        void Modeless(Func<Form> make) { tip.Hide(); try { make().Show(this); } catch (Exception ex) { Log(L.T("errTitle") + ": " + ex); MessageBox.Show(this, ex.Message, L.T("errTitle"), MessageBoxButtons.OK, MessageBoxIcon.Error); } }
        protected override void OnHandleCreated(EventArgs e) { base.OnHandleCreated(e); Dark.Apply(Handle); if (AutoScroll) Dark.Scroll(this); }

        // ---- build ------------------------------------------------------------------------------------------------
        void BuildAll()
        {
            string keepReq = reqBox != null && reqBox.Box != null ? reqBox.Box.Text : "";   // a language switch must not eat a half-typed request
            BackColor = Th.Bg; ForeColor = Th.Text; tip.BackColor = Th.SurfHi; if (IsHandleCreated) Dark.Apply(Handle);   // a theme switch rebuilds everything with the new palette
            SuspendLayout();
            Control[] old = new Control[Controls.Count]; Controls.CopyTo(old, 0); foreach (Control c in old) { Controls.Remove(c); c.Dispose(); }
            DisposePrev(); pages.Clear(); Text = App.Name;
            Rectangle side = new Rectangle(M, M, SideW, MainH);
            pick = new PickBtn(); pick.SetBounds(side.X, side.Y, SideW, 56); pick.Click += delegate { TogglePicker(); };
            string[] nl = { U.R("Патчи и фиксы", "Patches & fixes"), U.R("Графика", "Graphics"), U.R("Секреты", "Secrets"), U.R("Инструменты", "Tools"), U.R("Запрос игры", "Game request") };
            string[] ng = { "✦", "◐", "☠", "⚙", "✉" }; string[] ids = { "fix", "gfx", "sec", "tools", "req" };
            Color[] cc = { Color.FromArgb(217, 138, 43), Color.FromArgb(70, 140, 214), Color.FromArgb(180, 70, 122), Color.FromArgb(58, 162, 143), Color.FromArgb(123, 111, 224) };
            for (int i = 0; i < 5; i++)
            {
                NavItem n = new NavItem(); n.Glyph = ng[i]; n.Label = nl[i]; n.Chip = cc[i]; n.SetBounds(side.X, side.Y + 56 + 14 + i * 44, SideW, 42); string id = ids[i];
                n.Click += delegate { HidePicker(); GoPage(id); }; nav[i] = n;
            }
            foot = new RPanel(); foot.SetBounds(side.X, side.Bottom - 217, SideW, 217);
            bSup = FootBtn(0, U.R("♥ Поддержать", "♥ Support")); bSup.Click += delegate { Dlg(delegate { return new SupportForm(); }); };
            bAbout = FootBtn(1, U.R("О программе", "About")); bAbout.Click += delegate { Dlg(delegate { return new AboutForm(); }); };
            bFb = FootBtn(2, U.R("Обратная связь", "Feedback")); bFb.Click += delegate { Dlg(delegate { return new FeedbackForm(core); }); };
            bUpd = FootBtn(3, U.R("Обновление", "Update")); bUpd.Width = SideW - 20 - 38;   // the rest of the row belongs to the "what's new" button
            bUpd.Click += delegate { if (upd != null) OpenUpdate(); else { updText = U.R("проверяю…", "checking…"); RefreshFoot(); Thread t = new Thread(CheckUpdate); t.IsBackground = true; t.Start(true); } };
            bNew = new Btn(); bNew.Under = Th.Surf; bNew.Text = "\u2261"; bNew.Pt = 13f; bNew.SetBounds(10 + bUpd.Width + 4, bUpd.Top, 34, 34);   // "≡" - a list of changes
            bNew.MouseEnter += delegate { tip.ShowFor(this, bNew, new Rectangle(0, 0, bNew.Width, bNew.Height), U.R("Что нового", "What's new"), bNew.Badge > 0 ? U.R("Новых версий в журнале, которые вы не смотрели: ", "Versions in the log you have not looked at: ") + bNew.Badge : ""); }; bNew.MouseLeave += delegate { tip.Hide(); };
            bNew.Click += delegate { Updater.MarkSeen(); bNew.Badge = 0; bNew.Invalidate(); tip.Hide(); Dlg(delegate { return new ChangelogForm(); }); };
            bUpd.MouseEnter += delegate { string st = upd != null ? U.R("Доступна новая версия ", "A new version is available: ") + newVer : (updText.Length > 0 ? updText : U.R("Нажмите, чтобы проверить", "Click to check")); tip.ShowFor(this, bUpd, new Rectangle(0, 0, bUpd.Width, bUpd.Height), U.R("Обновление", "Update") + " · v" + App.Version, st); }; bUpd.MouseLeave += delegate { tip.Hide(); };
            // two big switches in place of the old version line: theme (moon = dark, sun = light) and language
            segTheme = new Seg(); segTheme.Under = Th.Surf; segTheme.Items = new string[] { "\u263E", "\u2600" }; segTheme.SetBounds(10, 176, 90, 34); segTheme.Selected = Th.Light ? 1 : 0;
            segTheme.MouseEnter += delegate { tip.ShowFor(this, segTheme, new Rectangle(0, 0, segTheme.Width, segTheme.Height), U.R("Тема оформления", "Colour theme"), U.R("Слева тёмная, справа светлая", "Dark on the left, light on the right")); }; segTheme.MouseLeave += delegate { tip.Hide(); };
            segTheme.Changed += delegate { bool light = segTheme.Selected == 1; App.Set("theme", light ? "light" : "dark"); Th.Set(light); BeginInvoke((MethodInvoker)delegate { BuildAll(); }); };
            segLang = new Seg(); segLang.Under = Th.Surf; segLang.SetBounds(foot.Width - 10 - 90, 176, 90, 34); segLang.Selected = L.Ru ? 0 : 1;
            segLang.Changed += delegate { L.Ru = segLang.Selected == 0; App.Set("lang", L.Ru ? "ru" : "en"); BeginInvoke((MethodInvoker)delegate { BuildAll(); }); };
            foot.Controls.AddRange(new Control[] { bSup, bAbout, bFb, bUpd, bNew, segTheme, segLang });
            bBadge = new Btn(); bBadge.Accent = true; bBadge.Pt = 9.5f; bBadge.SetBounds(side.X, foot.Top - 50, SideW, 42); bBadge.Visible = false; bBadge.Click += delegate { OpenUpdate(); };   // "version X is available" above the footer
            pop = null;
            Controls.AddRange(new Control[] { pick, nav[0], nav[1], nav[2], nav[3], nav[4], foot, bBadge });
            Controls.Add(BuildFix()); Controls.Add(BuildGfx()); Controls.Add(BuildSec()); Controls.Add(BuildTools());
            GameDef.All[0].Fixes = cntFix;
            Controls.Add(BuildReq());
            if (keepReq.Length > 0) reqBox.Box.Text = keepReq;
            nav[0].Count = cntFix.ToString(); nav[1].Count = cntGfx.ToString(); nav[2].Count = cntSec.ToString(); nav[3].Count = cntTools.ToString(); nav[4].Count = LoadReqs().Count.ToString();   // all counters come from the data that was just built
            ResumeLayout(); RefreshState(); GoPage(page);
        }

        Btn FootBtn(int i, string t) { Btn b = new Btn(); b.Under = Th.Surf; b.Text = t; b.SetBounds(10, 10 + i * 41, SideW - 20, 34); return b; }

        Panel NewPage(string id, bool strip)
        {
            Panel p = new Panel(); p.SetBounds(MainX, M, MainW, MainH); p.BackColor = Th.Bg; p.Visible = false; pages[id] = p;
            RPanel card = new RPanel(); card.Name = "card"; card.SetBounds(0, 0, MainW, MainH - (strip ? 66 : 0)); p.Controls.Add(card);
            return p;
        }
        RPanel Card(Panel p) { return (RPanel)p.Controls["card"]; }
        Label Head(RPanel card, string title, string sub, int rightReserved)
        {
            Label t = new Label(); t.AutoSize = false; t.SetBounds(14, 14, card.Width - 28 - rightReserved, 24); t.Font = Th.F("Segoe UI Semibold", 12.5f, FontStyle.Regular); t.ForeColor = Th.Text; t.BackColor = Th.Surf; t.UseMnemonic = false; t.Text = title;
            Label s = new Label(); s.AutoSize = false; s.SetBounds(14, 38, card.Width - 28 - rightReserved, 18); s.Font = Th.F("Segoe UI", 8.5f, FontStyle.Regular); s.ForeColor = Th.Muted; s.BackColor = Th.Surf; s.UseMnemonic = false; s.Text = sub;
            card.Controls.Add(t); card.Controls.Add(s); return s;
        }
        // lay rows/sections out on the card list grid; rows are always 44 high, sections 22, gap 5
        void Lay(RPanel card, int top, params Control[] items)
        {
            int y = top; bool first = true;
            foreach (Control c in items)
            {
                if (c is SecHead && !first) y += 4;
                c.SetBounds(14, y, card.Width - 28, c is SecHead ? 22 : RowCtl.H); card.Controls.Add(c); y += c.Height + 5; first = false;
            }
        }
        RowCtl Row(string glyph, Color gc, string title, string desc, Control ctl)
        {
            RowCtl r = new RowCtl(); r.Glyph = glyph; r.GlyphColor = gc; r.Title = title; r.Desc = desc; r.Ctl = ctl;
            r.DescHover += delegate(RowCtl s, bool on) { if (!on) { tip.Hide(); return; } tip.ShowFor(this, s, s.DescRect, s.Title, s.Desc); };
            return r;
        }
        Seg OnOff(Action<bool> act)
        {
            Seg s = new Seg(); s.Under = Th.Inset; s.Items = new string[] { U.R("Выкл", "Off"), U.R("Вкл", "On") }; s.Size = new Size(84, 28);
            s.Changed += delegate { act(s.Selected == 1); }; return s;
        }
        Btn Act(string text, EventHandler h) { Btn b = new Btn(); b.Under = Th.Inset; b.Text = text; b.Pt = 8.5f; b.Size = new Size(84, 28); b.Click += h; return b; }
        Color Amb { get { return Th.Amber; } }

        Panel BuildFix()
        {
            Panel p = NewPage("fix", true); RPanel c = Card(p);
            bPlay = new Btn(); bPlay.Accent = true; bPlay.Pt = 10f; bPlay.Text = "▶  " + U.R("Играть", "Play"); bPlay.SetBounds(c.Width - 14 - 140, 14, 140, 38); bPlay.Click += delegate { Play(); };
            bLnk = new Btn(); bLnk.Under = Th.Surf; bLnk.Pt = 9f; bLnk.Text = "⧉  " + U.R("Создать ярлык со всеми фиксами", "Create shortcut with all fixes"); bLnk.SetBounds(bPlay.Left - 10 - 250, 14, 250, 38); bLnk.Click += delegate { CreateShortcut(); };
            c.Controls.Add(bPlay); c.Controls.Add(bLnk);
            bQuick = new Btn(); bQuick.Accent = true; bQuick.Under = Th.Surf; bQuick.Pt = 10f; bQuick.Text = "\u2726  " + U.R("Быстрая настройка", "Quick setup"); bQuick.SetBounds(bLnk.Left - 10 - 190, 14, 190, 38);
            bQuick.Click += delegate { tip.Hide(); WizResult wr = null; Dlg(delegate { WizardForm f = new WizardForm(core); f.FormClosed += delegate { wr = f.R; }; return f; }); if (wr != null && wr.Done) WizardApply(wr); };
            c.Controls.Add(bQuick);
            lPath = Head(c, U.R("Патчи и фиксы", "Patches & fixes"), "", 330); lPath.Cursor = Cursors.Hand; lPath.Click += delegate { ChooseFolder(); };
            lPath.SetBounds(14, 58, c.Width - 28, 18);   // its own line BELOW the button row (the buttons occupy y 14..52 over most of the width)
            sVoice = OnOff(delegate(bool on) { Guard(delegate { core.SetVoice(on); core.FixOptOut("voice", !on); }); });
            sDusk = OnOff(delegate(bool on) { Guard(delegate { core.SetDusk(on); core.FixOptOut("dusk", !on); }); });
            sDgv = OnOff(delegate(bool on) { Guard(delegate { core.SetDgv(on, true); }); });
            sCnc = OnOff(delegate(bool on) { Guard(delegate { core.SetCnc(on); }); });
            sSmooth = OnOff(delegate(bool on) { Guard(delegate { core.SetLauncher(on); core.FixOptOut("smooth", !on); }); });   // frame mode is FROZEN (07.11.2026, Fps.cs): "Smooth play" is the switch it was before
            bFonts = Act(U.R("Выбрать", "Choose"), delegate { Dlg(delegate { return new FontForm(core); }); RefreshState(); });
            rVoice = Row("♪", Amb, U.R("Озвучка и музыка", "Voice & music"), U.R("Голос и музыка не пропадают после диалога", "Voice and music no longer drop after a dialogue"), sVoice);
            rDusk = Row("☾", Amb, U.R("Закат и рассвет", "Dusk & dawn"), U.R("Плавная смена дня и ночи без скачков", "Smooth day and night, no sudden jumps"), sDusk);
            rDgv = Row("◈", Amb, "dgVoodoo", U.R("Другая обёртка: ускорение и MSAA", "Another wrapper: acceleration and MSAA"), sDgv);
            rCnc = Row("◇", Amb, "gr-draw  ★", U.R("Рекомендуется: лучшая картинка, без рамки", "Recommended: better picture, borderless"), sCnc);
            rDgv.HelpClick = delegate { Dlg(delegate { return new HelpForm(false); }); };
            rCnc.HelpClick = delegate { Dlg(delegate { return new HelpForm(true); }); };
            rDusk.HelpClick = Help.Click(this, "gfx_fix_dusk");
            Btn bGfx = Act(U.R("Настроить", "Adjust"), delegate { if (core.Cnc) Modeless(delegate { return new CncForm(core); }); else Modeless(delegate { return new DgvQualityForm(core); }); });
            rGfx = Row("◐", Amb, U.R("Качество графики", "Graphics quality"), U.R("Масштаб, сглаживание, режим окна, синхр.", "Scale, smoothing, window mode, sync"), bGfx);
            rFonts = Row("Aa", Amb, U.R("Шрифты", "Fonts"), U.R("Крупный текст, книги, диалоги, предпросмотр", "Larger text, books, dialogues, preview"), bFonts);
            bAssets = Act(U.R("Выбрать", "Choose"), delegate { ToolAssets(); });
            rAssets = Row("\u2726", Amb, U.R("Улучшенная графика", "Enhanced graphics"), U.R("Готовые наборы: чистые спрайты и интерфейс", "Ready sets: clean sprites and interface"), bAssets);
            rGfx.HelpClick = Help.Click(this, "gfx_render"); rFonts.HelpClick = Help.Click(this, "gfx_fonts"); rAssets.HelpClick = Help.Click(this, "gfx_pic");
            rSmooth = Row("\u21AF", Amb, U.R("Плавная работа", "Smooth play"), U.R("Один поток и флаги совместимости, без лагов", "Single core and compatibility flags, no stutter"), sSmooth);
            Btn bVer = Act(U.R("Подробнее", "Details"), delegate { Dlg(delegate { return new VersionForm(core); }); });
            rVer = Row("⚑", Amb, U.R("Версия игры", "Game version"), "", bVer);
            cntFix = new RowCtl[] { rVoice, rDusk, rDgv, rCnc, rFonts, rSmooth }.Length;   // the fixes of this page (the version row and the quality window are not fixes)
            Lay(c, 84, rVer, new SecHead(U.R("Звук и производительность", "Sound and performance")), rVoice, rSmooth, new SecHead(U.R("Графика", "Graphics")), rDusk, rCnc, rDgv, rGfx, rFonts);   // 6 rows + 2 heads must fit the 610 px card
            RPanel st = new RPanel(); st.SetBounds(0, MainH - 56, MainW, 56); p.Controls.Add(st);
            lLnk = new Label(); lLnk.AutoSize = false; lLnk.SetBounds(14, 8, st.Width - 14 - 150, 40); lLnk.Font = Th.F("Segoe UI", 8.5f, FontStyle.Regular); lLnk.ForeColor = Th.Muted; lLnk.BackColor = Th.Surf; lLnk.TextAlign = ContentAlignment.MiddleLeft;
            bRevert = new Btn(); bRevert.Under = Th.Surf; bRevert.Pt = 8.5f; bRevert.Text = U.R("Откатить всё", "Revert all"); bRevert.SetBounds(st.Width - 14 - 124, 12, 124, 32); bRevert.Click += delegate { RevertAll(); };
            st.Controls.Add(lLnk); st.Controls.Add(bRevert);
            return p;
        }

        Panel BuildSec()
        {
            Panel p = NewPage("sec", false); RPanel c = Card(p);
            Head(c, U.R("Секреты", "Secrets"), U.R("Скрытые режимы и данные игры", "Hidden modes and data of the game"), 0);
            sBone = OnOff(delegate(bool on) { Guard(delegate { core.SetBone(on); }); });
            rBone = Row("☠", Color.FromArgb(220, 110, 160), "Lar's Bone", U.R("Секретный сложный режим игры", "Hidden hard difficulty mode"), sBone);
            List<Control> items = new List<Control>(); items.Add(new SecHead(U.R("Сложность", "Difficulty"))); items.Add(rBone);
            items.Add(new SecHead(U.R("Статьи и секреты", "Articles and secrets")));
            foreach (Art a0 in Art.DivineDivinity())
            {
                Art a = a0; Btn rd = Act(U.R("Читать", "Read"), delegate { Dlg(delegate { return new ArticleForm(a); }); });
                items.Add(Row(a.Glyph, Amb, a.Title, a.Desc, rd));
            }
            string wiki = L.Ru ? "https://divinity.fandom.com/ru/wiki/Divinity_%D0%B2%D0%B8%D0%BA%D0%B8" : "https://divinity.fandom.com/wiki/Divinity_Wiki";
            items.Add(Row("\u2316", Amb, U.R("Divinity вики", "Divinity Wiki"), U.R("Энциклопедия серии: квесты, предметы, карты", "Series encyclopedia: quests, items, maps"), Act(U.R("Открыть", "Open"), delegate { U.Open(wiki); })));
            cntSec = 1 + Art.DivineDivinity().Length;   // Lar's Bone + the articles (the wiki link is not a secret)
            Lay(c, 66, items.ToArray());
            return p;
        }

        void Tool(List<Control> l, string glyph, string title, string desc, EventHandler h, Func<bool> en, out RowCtl row)
        {
            Btn b = Act(U.R("Открыть", "Open"), h); RowCtl r = Row(glyph, Th.Muted, title, desc, b); r.Status = U.R("встроен", "built in"); l.Add(r); row = r; toolRows.Add(r); toolEn.Add(en);
        }
        List<RowCtl> toolRows = new List<RowCtl>(); List<Func<bool>> toolEn = new List<Func<bool>>();
        Panel BuildTools()
        {
            Panel p = NewPage("tools", false); RPanel c = Card(p); toolRows.Clear(); toolEn.Clear();
            Head(c, U.R("Инструменты", "Tools"), U.R("Встроены в программу, ничего ставить не нужно", "Built in, nothing to install"), 0);
            List<Control> l = new List<Control>(); RowCtl r;
            Func<bool> has = delegate { return core.HasGame; };
            l.Add(new SecHead(U.R("Редакторы", "Editors")));
            Tool(l, "♞", U.R("Редактор сохранений", "Save editor"), U.R("Золото, статы, инвентарь · iZakaroN", "Gold, stats, inventory · iZakaroN"), delegate { Embedded("SaveEditor.exe"); }, has, out r);
            Tool(l, "⚔", U.R("Редактор предметов", "Items editor"), U.R("Оружие, броня, зелья · Igel", "Weapons, armour, potions · Igel"), delegate { Embedded("ItemsEditor.exe"); }, has, out r);
            Tool(l, "⚔", U.R("Редактор предметов 2", "Items editor 2"), U.R("DDIE: данные предметов, версия 2025", "DDIE: item data, 2025 version"), delegate { Embedded("DDIE.exe"); }, has, out r);
            Tool(l, "A", U.R("Редактор шрифтов", "Font editor"), U.R("Правка файлов шрифтов .fnt · Sormy", "Edit .fnt font files · Sormy"), delegate { Embedded("FontEditor.exe"); }, has, out r);
            Tool(l, "T", U.R("Компилятор текста", "Text compiler"), U.R("Сборка текстов локализации · Sormy", "Build localisation texts · Sormy"), delegate { Embedded("TextCompiler.exe"); }, has, out r);
            Tool(l, "✉", U.R("Компилятор диалогов", "Dialog compiler"), U.R("Сборка диалогов квестов и NPC · Sormy", "Build quest and NPC dialogues · Sormy"), delegate { Embedded("DialogCompiler.exe"); }, has, out r);
            Tool(l, "▦", U.R("Графика игры (DGE)", "Game graphics (DGE)"), U.R("Спрайты: экспорт и замена · Raan", "Sprites: export and replace · Raan"), delegate { Tool3rd(); }, has, out r); r.Status = Dge.Ready ? U.R("скачан", "downloaded") : U.R("с GitHub", "from GitHub");
            Tool(l, "\u25B2", U.R("Редактор мира (DivEdit)", "World editor (DivEdit)"), U.R("Карты, NPC · грузится долго · Raan", "Maps, NPCs · slow to load · Raan"), delegate { ToolDivEdit(); }, has, out r); r.Status = DivEdit.Ready ? U.R("скачан", "downloaded") : U.R("с GitHub", "from GitHub");
            l.Add(new SecHead(U.R("Настройка, папки и данные", "Setup, folders and data")));
            Tool(l, "⚙", U.R("Конфигуратор игры", "Game config"), U.R("Разрешение, звук и управление", "Resolution, sound and controls"), delegate { Start(core.P("configtool.exe"), "", core.Dir); }, delegate { return core.HasGame && File.Exists(core.P("configtool.exe")); }, out r); r.Status = U.R("из игры", "from game");
            Tool(l, "◇", U.R("Панель dgVoodoo", "dgVoodoo panel"), U.R("Тонкая настройка графики", "Fine graphics tuning"), delegate { Start(core.P("dgVoodooCpl.exe"), "", core.Dir); }, delegate { return core.HasGame && File.Exists(core.P("dgVoodooCpl.exe")); }, out r);
            Tool(l, "▣", U.R("Папки игры", "Game folders"), U.R("Открыть папку игры в проводнике", "Open the game folder in Explorer"), delegate { Start("explorer.exe", QuoteArg(core.Dir), null); }, has, out r); r.Status = "";
            Btn bk = Act(U.R("Создать", "Create"), delegate { BackupSaves(); }); rSaves = Row("⎘", Th.Muted, U.R("Копия сохранений", "Back up saves"), U.R("Копирует savegames в папку с датой", "Copies savegames to a dated folder"), bk); l.Add(rSaves);
            cntTools = toolRows.Count + 1;   // + the saves backup row
            Lay(c, 66, l.ToArray());
            return p;
        }

        Panel BuildReq()
        {
            Panel p = NewPage("req", false); RPanel c = Card(p);
            Head(c, U.R("Запрос игры", "Game request"), U.R("Напишите в одну строку, что и где починить", "One line: what to fix and where"), 0);
            reqBox = new Field(); reqBox.Under = Th.Surf; reqBox.Hint = U.R("Например: Gothic 2 — вылетает на Win11, нужен фикс разрешения", "E.g.: Gothic 2 — crashes on Win11, needs a resolution fix"); reqBox.SetBounds(14, 66, c.Width - 28 - 130, 38); reqBox.Box.MaxLength = 500;
            Btn send = new Btn(); bSend = send; send.Accent = true; send.Pt = 10f; send.Under = Th.Surf; send.Text = U.R("Отправить", "Send"); send.SetBounds(c.Width - 14 - 120, 66, 120, 38); send.Click += delegate { SendReq(); };
            c.Controls.Add(reqBox); c.Controls.Add(send);
            List<Control> l = new List<Control>(); List<string[]> reqs = LoadReqs();
            if (reqs.Count > 0)
            {
                l.Add(new SecHead(U.R("Мои запросы", "My requests")));
                for (int i = reqs.Count - 1; i >= 0 && l.Count < 3; i--) { RowCtl r = Row("➤", Color.FromArgb(106, 167, 232), U.R("Мой запрос", "My request"), reqs[i][1], new Label()); string stt = reqs[i].Length > 2 ? reqs[i][2] : "sent"; r.Status = stt == "sent" ? U.R("отправлен", "sent") : (stt == "mail" ? U.R("в письме", "in a mail") : U.R("не отправлен", "not sent")); r.StatusColor = stt == "fail" ? Th.Red : (stt == "mail" ? Th.Amber : Color.FromArgb(106, 167, 232)); r.Ctl.Visible = false; l.Add(r); }
            }
            l.Add(new SecHead(U.R("Сделано", "Done")));
            RowCtl done = Row("✓", Th.Green, "Divine Divinity", U.R(cntFix + " " + U.Pl(cntFix, "фикс", "фикса", "фиксов") + ", " + cntSec + " " + U.Pl(cntSec, "секрет", "секрета", "секретов") + ", " + cntTools + " " + U.Pl(cntTools, "инструмент", "инструмента", "инструментов"), cntFix + (cntFix == 1 ? " fix, " : " fixes, ") + cntSec + (cntSec == 1 ? " secret, " : " secrets, ") + cntTools + (cntTools == 1 ? " tool" : " tools")), new Label()); done.Status = U.R("готово", "done"); done.StatusColor = Th.Green; done.Ctl.Visible = false; l.Add(done);
            l.Add(new SecHead(U.R("В планах", "Planned")));
            string[][] plan = { new string[] { "Beyond Divinity", U.R("Те же баги озвучки и разрешения", "Same voice and resolution bugs") }, new string[] { "Diablo II", U.R("Современное разрешение и графика", "Modern resolution and graphics") }, new string[] { "Fallout 2", U.R("Широкий экран и вылеты на новых Windows", "Widescreen and crashes on new Windows") }, new string[] { "Gothic II", U.R("Графика и вылеты на Win10/11", "Graphics and crashes on Win10/11") }, new string[] { "Max Payne", U.R("Звук и мышь на Win10/11", "Sound and mouse on Win10/11") } };
            foreach (string[] g in plan)
            {
                string name = g[0]; Btn ask = Act(U.R("Запросить", "Request"), delegate { reqBox.Box.Text = name; reqBox.Box.Focus(); reqBox.Box.SelectionStart = reqBox.Box.Text.Length; });
                RowCtl r = Row("◌", Th.Faint, g[0], g[1], ask); r.Status = U.R("в плане", "planned"); l.Add(r);
            }
            Lay(c, 118, l.ToArray());
            return p;
        }

        // ---- pages / state ----------------------------------------------------------------------------------------
        public void GoPage(string id)
        {
            if (page == "gfx" && id != "gfx") GfxStep2(false);
            page = id; tip.Hide();
            foreach (KeyValuePair<string, Panel> kv in pages) kv.Value.Visible = kv.Key == id;
            if (id == "gfx") { RefreshGfx(); GfxFirstDefaults(); if (gfxMan == null) LoadGfxCatalog(); }
            string[] ids = { "fix", "gfx", "sec", "tools", "req" }; for (int i = 0; i < 5; i++) { nav[i].On = ids[i] == id; nav[i].Invalidate(); }
        }

        void SetRow(RowCtl r, Seg s, bool avail, bool on)
        {
            r.Enabled = avail; s.Enabled = avail; s.Selected = on ? 1 : 0;
            r.Status = !avail ? U.R("недоступно", "unavailable") : (on ? U.R("включено", "on") : U.R("выключено", "off")); r.StatusColor = on && avail ? Th.Green : Th.Faint; r.Invalidate();
        }
        void RefreshFoot()
        {
            if (bUpd == null) return;
            bUpd.Text = upd != null ? U.R("Обновить до ", "Update to ") + newVer : U.R("Обновление", "Update") + " · v" + App.Version; bUpd.Accent = upd != null; bUpd.Pulse = upd != null; bUpd.Invalidate();
            if (bBadge != null) { bBadge.Visible = upd != null; bBadge.Pulse = upd != null; if (upd != null) bBadge.Text = "\u2193  " + U.R("Доступна версия ", "Version available: ") + newVer; bBadge.Invalidate(); }
        }
        void RefreshState()
        {
            if (rVoice == null) return;
            bool has = core.HasGame, ok = has && core.ExeSupported;
            SetRow(rVoice, sVoice, has, ok && core.VoiceOn); if (has && core.VoiceMixed) { rVoice.Status = U.R("частично", "partial"); rVoice.StatusColor = Th.Amber; rVoice.Desc = U.R("Файлы озвучки в смешанном состоянии: включите и выключите заново", "Voice files are in a mixed state: switch it on and off again"); } else rVoice.Desc = U.R("Голос и музыка не пропадают после диалога", "Voice and music no longer drop after a dialogue");
            if (has && !ok && !core.VoiceMixed) { rVoice.Enabled = sVoice.Enabled = false; rVoice.Status = U.R("недоступно", "unavailable"); } else if (has && !ok) { rVoice.Enabled = sVoice.Enabled = true; }   // an unsupported exe: only switching OFF (taking our DLLs out) is possible
            rVoice.Invalidate(); SetRow(rDusk, sDusk, ok, ok && core.DuskOn); SetRow(rDgv, sDgv, has, has && core.Dgv); SetRow(rCnc, sCnc, has, has && core.Cnc); SetRow(rSmooth, sSmooth, has, has && core.Launcher); SetRow(rBone, sBone, has, has && core.Bone);
            rGfx.Enabled = rGfx.Ctl.Enabled = has && (core.Dgv || core.Cnc); rGfx.Status = rGfx.Enabled ? (core.Cnc ? "gr-draw" : "dgVoodoo") : U.R("нужна обёртка", "needs a wrapper"); rGfx.Invalidate();
            int fs = has ? Math.Max(Math.Max(core.FontState(0), core.FontState(1)), core.FontState(2)) : -1; int fa = has ? Math.Min(Math.Min(core.FontState(0), core.FontState(1)), core.FontState(2)) : -1;
            bool fcust = has && core.FontsAvail && (core.FontIsCustom(0) || core.FontIsCustom(1) || core.FontIsCustom(2));
            rFonts.Enabled = bFonts.Enabled = has && core.FontsAvail; rFonts.Status = !rFonts.Enabled ? U.R("недоступно", "unavailable") : (fcust ? U.R("свои", "custom") : (fa == 1 ? U.R("крупнее", "larger") : (fs == 1 ? U.R("частично", "partly") : U.R("оригинал", "original"))));
            rFonts.StatusColor = rFonts.Enabled && (fs == 1 || fcust) ? (fcust ? Th.Amber : Th.Green) : Th.Faint; rFonts.Invalidate();
            rAssets.Enabled = bAssets.Enabled = has;
            { bool good; string at = core.AssetsQuickText(out good); string nm = at.Contains(":") ? at.Substring(at.IndexOf(':') + 1) : "";
              rAssets.Desc = nm.Length > 0 ? U.R("Применён набор: ", "Applied set: ") + nm : U.R("Готовые наборы: чистые спрайты и интерфейс", "Ready sets: clean sprites and interface");
              rAssets.Status = !has ? U.R("недоступно", "unavailable") : (at.StartsWith("ok:") ? U.R("включено", "on") : (at.StartsWith("partial:") ? U.R("не завершено", "unfinished") : (at.StartsWith("changed:") ? U.R("изменено", "changed") : U.R("оригинал", "original"))));
              rAssets.StatusColor = at.StartsWith("ok:") ? Th.Green : (at.Length > 0 ? Th.Amber : Th.Faint); rAssets.Invalidate(); }
            rVer.Enabled = rVer.Ctl.Enabled = has;
            rVer.Desc = !has ? "" : (ok ? U.R("Найден div.exe " + core.ExeFileVersion + " — все фиксы подходят", "Found div.exe " + core.ExeFileVersion + " — every fix fits") : U.R("div.exe " + core.ExeVersionText + " — фиксы рассчитаны на 1.0.0.62", "div.exe " + core.ExeVersionText + " — fixes are made for 1.0.0.62"));
            rVer.Status = !has ? "" : (ok ? U.R("подходит", "fits") : U.R("не подходит", "does not fit")); rVer.StatusColor = ok ? Th.Green : Th.Red; rVer.Invalidate();
            bPlay.Enabled = has; bLnk.Enabled = has; bQuick.Enabled = has; bRevert.Enabled = has;
            for (int i = 0; i < toolRows.Count; i++) { bool en = toolEn[i](); toolRows[i].Enabled = en; toolRows[i].Ctl.Enabled = en; toolRows[i].Invalidate(); }
            rSaves.Enabled = rSaves.Ctl.Enabled = has && Directory.Exists(core.P("savegames"));
            string sub = pathUnavailable && !has ? U.R("Папка недоступна: " + unavailPath + " — подключите диск или нажмите и выберите другую", "Folder not available: " + unavailPath + " — plug the drive in or click to pick another")
                : (!has ? U.R("Игра есть в базе, на этом ПК не найдена — нажмите и укажите папку", "The game is in the base but not found on this PC — click and pick its folder") : (!ok ? U.R("версия не поддерживается (нужна 1.0.0.62)", "unsupported version (1.0.0.62 needed)") : ""));
            lPath.Text = sub; lPath.ForeColor = has && ok ? Th.Muted : (has ? Th.Red : Th.Amber);
            lLnk.Text = has ? (core.ShortcutExists ? U.R("Ярлык «с фиксами» есть на рабочем столе. «Играть» и ярлык запускают игру со всеми включёнными фиксами.", "The \"with fixes\" desktop shortcut exists. Play and the shortcut start the game with every enabled fix.") : U.R("Ярлыка «с фиксами» ещё нет. «Играть» запускает игру со всеми включёнными фиксами.", "No \"with fixes\" shortcut yet. Play starts the game with every enabled fix.")) : "";
            lLnk.Invalidate();
            pick.Icon = gameIcon; pick.Mono = game.Mono; pick.GameName = game.Name; pick.Small = U.R("Выбрана игра:", "Selected game:"); pick.Invalidate();
            RefreshFoot();
            if (page == "gfx") RefreshGfx();
        }

        // ---- actions ----------------------------------------------------------------------------------------------
        void Log(string s)
        {
            if (App.ReadOnly) return;
            try { File.AppendAllText(Path.Combine(App.DataDir, "log.txt"), DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + "   " + s + "\r\n", Encoding.UTF8); } catch { }
        }
        void OpenLog() { string f = Path.Combine(App.DataDir, "log.txt"); if (!File.Exists(f)) File.WriteAllText(f, "", Encoding.UTF8); Start("notepad.exe", "\"" + f + "\"", null); }

        void Guard(Action a)   // apply a change, never leave a switch out of step with the real state
        {
            if (busy) { RefreshState(); return; }
            if (Core.GameRunning()) { MessageBox.Show(this, L.T("running"), L.T("warnTitle")); RefreshState(); return; }
            busy = true;
            try { a(); }
            catch (UnauthorizedAccessException ex) { Log(L.T("errTitle") + ": " + ex.Message); if (!Core.IsAdmin()) AskElevate(); else MessageBox.Show(this, ex.Message, L.T("errTitle"), MessageBoxButtons.OK, MessageBoxIcon.Error); }
            catch (Exception ex) { Log(L.T("errTitle") + ": " + ex.Message); MessageBox.Show(this, ex.Message, L.T("errTitle"), MessageBoxButtons.OK, MessageBoxIcon.Error); }
            finally { busy = false; RefreshState(); }
            FlushNotes();
        }

        // the small fixes that are on by default (cellar floor, map panel): once per game on the first start; the player's "off" / "Revert all" is respected afterwards
        void DefaultFixes()
        {
            try { if (core.HasGame && !Core.GameRunning()) core.StartupSync(); } catch (Exception ex) { Log("start-up sync: " + ex.Message); }   // our embedded files refreshed, div.exe rebuilt to the current tables (src/Install.cs); every part logs its own failure
            try { if (core.HasGame && core.ExeSupported && !Core.GameRunning()) { core.ApplyPatchDefaults(false); foreach (string x in core.ApplyDefaultFixes(false, true)) notes.Add(x); FlushNotes(); RefreshState(); } }   // voice, dusk, smooth play: ON once per game
            catch (Exception ex) { Log("default fixes: " + ex.Message); }
            OfferSetUpdates();
        }

        void Play() { if (!core.HasGame) return; if (setsMan != null) { List<AssetQuick> q = null; try { q = core.Assets.Quick(); } catch (Exception) { } if (q != null && !AskSetUpdates(setsMan, q, true)) return; } Guard2(delegate { Start(core.WriteCmd(), "", core.Dir); }); }
        void RefreshNewBadge() { if (bNew == null) return; bNew.Badge = Updater.UnseenCount(); bNew.Invalidate(); }
        static string QuoteArg(string a) { int n = 0; for (int i = a.Length - 1; i >= 0 && a[i] == '\\'; i--) n++; return "\"" + a + new string('\\', n) + "\""; }   // a trailing backslash would escape the closing quote
        void CreateShortcut() { Guard2(delegate { core.CreateShortcut(); }); }
        void Guard2(Action a) { try { a(); } catch (Exception ex) { Log(L.T("errTitle") + ": " + ex.Message); MessageBox.Show(this, ex.Message, L.T("errTitle"), MessageBoxButtons.OK, MessageBoxIcon.Warning); } RefreshState(); FlushNotes(); }

        void BackupSaves()   // copying hundreds of save files is not done on the UI thread
        {
            string d = null; Core c = core;
            string err = WorkForm.Run(this, U.R("Копия сохранений", "Saves backup"), U.R("Копирую сохранения…", "Copying the saves…"), false, delegate(WorkForm w) { d = c.BackupSaves(); });
            if (err == null) MessageBox.Show(this, U.R("Копия сохранений готова:\r\n", "Saves backed up to:\r\n") + d, App.Name, MessageBoxButtons.OK, MessageBoxIcon.Information);
            else if (err.Length > 0) { Log(L.T("errTitle") + ": " + err); MessageBox.Show(this, err, L.T("errTitle"), MessageBoxButtons.OK, MessageBoxIcon.Warning); }
        }

        void RevertAll()
        {
            if (Core.GameRunning()) { MessageBox.Show(this, L.T("running"), L.T("warnTitle")); return; }
            if (MessageBox.Show(this, L.T("revertQ"), L.T("warnTitle"), MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes) return;
            // every step runs on its own (Core.RevertAll): a failure in one never stops the others; the result lists what did not work
            List<string> fails = new List<string>(); Core c = core;
            Guard(delegate { fails = c.RevertAll(); });
            if (fails.Count > 0) MessageBox.Show(this, U.R("Откат выполнен не полностью. Не удалось:\r\n\r\n", "Revert is incomplete. Failed:\r\n\r\n") + string.Join("\r\n", fails.ToArray()), L.T("warnTitle"), MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }

        void AskElevate()
        {
            if (MessageBox.Show(this, L.T("needAdmin"), L.T("warnTitle"), MessageBoxButtons.YesNo, MessageBoxIcon.Warning) != DialogResult.Yes) return;
            try { ProcessStartInfo psi = new ProcessStartInfo(Application.ExecutablePath, "--open " + QuoteArg(core.Dir)); psi.Verb = "runas"; psi.UseShellExecute = true; Process.Start(psi); Close(); }
            catch (System.ComponentModel.Win32Exception) { /* UAC cancelled */ }
        }

        void Start(string file, string args, string workDir)
        {
            try
            {
                bool isPath = file.IndexOf('\\') >= 0 || file.IndexOf('/') >= 0;
                if (isPath && !File.Exists(file)) { string m = U.R("Не найден файл: ", "File not found: ") + file; Log(L.T("errTitle") + ": " + m); MessageBox.Show(this, m, L.T("errTitle"), MessageBoxButtons.OK, MessageBoxIcon.Warning); return; }
                ProcessStartInfo psi = new ProcessStartInfo(file, args); psi.UseShellExecute = true; if (file.EndsWith(".cmd", StringComparison.OrdinalIgnoreCase)) psi.WindowStyle = ProcessWindowStyle.Hidden; if (!string.IsNullOrEmpty(workDir)) psi.WorkingDirectory = workDir;
                try { Process.Start(psi); }
                catch (System.ComponentModel.Win32Exception wx)
                {
                    if (wx.NativeErrorCode == 740)   // the game may carry the RUNASADMIN compat flag: offer to run elevated
                    {
                        if (MessageBox.Show(this, U.R("Для запуска нужны права администратора. Запустить от имени администратора?", "Administrator rights are needed to start it. Start as administrator?"), L.T("warnTitle"), MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes) return;
                        psi.Verb = "runas";
                        try { Process.Start(psi); } catch (System.ComponentModel.Win32Exception w2) { if (w2.NativeErrorCode != 1223) throw; }   // 1223 = the user declined the UAC prompt
                    }
                    else throw;
                }
            }
            catch (Exception ex) { Log(L.T("errTitle") + ": " + ex.Message); MessageBox.Show(this, U.R("Не удалось запустить:\r\n", "Could not start:\r\n") + ex.Message, L.T("errTitle"), MessageBoxButtons.OK, MessageBoxIcon.Warning); }
        }
        void ToolDivEdit()
        {
            tip.Hide(); string err = DivEdit.Run(this, core);
            if (err == null) Log(L.T("applied") + "DivEdit " + DivEdit.Tag); else if (err.Length > 0) { Log(L.T("errTitle") + ": " + err); MessageBox.Show(this, err, "DivEdit", MessageBoxButtons.OK, MessageBoxIcon.Warning); }
            BuildAll();
        }
        void ToolAssets()
        {
            tip.Hide(); if (!core.HasGame) return; List<AssetManifest> cat = new List<AssetManifest>(); string note = ""; Core c = core;
            string err = WorkForm.Run(this, U.R("Улучшенная графика", "Enhanced graphics"), U.R("Получаю список наборов…", "Fetching the list of sets…"), true, delegate(WorkForm w) { cat = c.Assets.LoadCatalog(out note); });
            if (err != null) { if (err.Length > 0) MessageBox.Show(this, err, L.T("errTitle"), MessageBoxButtons.OK, MessageBoxIcon.Warning); return; }
            Dlg(delegate { return new AssetsForm(core, cat, note); }); RefreshState();
        }
        void Tool3rd()
        {
            tip.Hide(); string err = Dge.Run(this, core.HasGame ? core.Dir : null);
            if (err == null) Log(L.T("applied") + "DGE " + Dge.Tag); else if (err.Length > 0) { Log(L.T("errTitle") + ": " + err); MessageBox.Show(this, err, "Divinity Graphics Extender", MessageBoxButtons.OK, MessageBoxIcon.Warning); }
            BuildAll();
        }
        void Embedded(string name)
        {
            Func<Core, Form> nf;
            if (NewTools.Map.TryGetValue(name, out nf))
            {
                tip.Hide(); bool? useNew; using (ToolChoiceForm ch = new ToolChoiceForm(name)) { ch.ShowDialog(this); useNew = ch.Result; }
                if (useNew == null) return;
                if (useNew.Value) { try { Form f = nf(core); f.Show(this); Log(L.T("applied") + name + " (new)"); } catch (Exception ex) { Log(L.T("errTitle") + ": " + ex.Message); } return; }
            }
            try
            {
                ProcessStartInfo psi = new ProcessStartInfo(Core.ToolPath(name)); psi.UseShellExecute = false; psi.WorkingDirectory = core.Dir; psi.EnvironmentVariables["DD_GAME_DIR"] = core.Dir;
                Process.Start(psi); Log(L.T("applied") + name);
            }
            catch (Exception ex) { Log(L.T("errTitle") + ": " + ex.Message); MessageBox.Show(this, ex.Message, L.T("errTitle"), MessageBoxButtons.OK, MessageBoxIcon.Error); }
        }

        // ---- game folder --------------------------------------------------------------------------------------------
        static string LoadLast() { try { string v = App.Get("path.dd"); if (v != null) return v.Trim(); string f = Path.Combine(App.DataDir, "last.txt"); if (File.Exists(f)) return File.ReadAllText(f).Trim(); string o = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), @"DD_FixTool\last.txt"); return File.Exists(o) ? File.ReadAllText(o).Trim() : null; } catch { return null; } }
        static void SaveLast(string p) { App.Set("path.dd", p); }

        // first start (nothing saved): one install is taken as it is, several -> the player chooses once the window is up, none -> "not found"
        void AutoDetect()
        {
            List<string> f = Finder.Find();
            if (f.Count == 0) { Log(L.T("notDetected")); return; }
            if (f.Count == 1 || App.ReadOnly) { Log(L.T("detected") + f[0]); SetPath(f[0], false); return; }
            Log("several installs found: " + string.Join(" | ", f.ToArray())); pendingChoice = f;
        }
        void ChooseFolder()
        {
            List<string> found = Finder.Find(); string p = null; bool browse = false;
            using (GameChoiceForm f = new GameChoiceForm(found, core.HasGame ? core.Dir : null)) { f.ShowDialog(this); p = f.Result; browse = f.Browse; }
            if (browse) p = FolderPicker.Pick(this, core.HasGame ? core.Dir : (Directory.Exists(unavailPath) ? unavailPath : null), L.T("choose"));
            if (p != null) { SetPath(p, true); DefaultFixes(); }
        }
        // the new folder is checked FIRST; only a real game folder replaces the current one (and is saved)
        bool SetPath(string p, bool refresh)
        {
            p = Core.NormPath((p ?? "").Trim());
            if (p.Length == 0 || !File.Exists(Path.Combine(p, "div.exe"))) { Log(L.T("notFoundExe") + " " + p); if (refresh) MessageBox.Show(this, L.T("notFoundExe"), L.T("warnTitle")); return false; }
            core = NewCore(p); pathUnavailable = false; SaveLast(p);
            if (refresh && !Core.IsAdmin() && !core.Writable()) AskElevate();
            if (refresh) RefreshState();
            return true;
        }

        // ---- game picker (overlay) -------------------------------------------------------------------------------------
        void HidePicker() { if (pop != null) { Controls.Remove(pop); pop.Dispose(); pop = null; } }
        void TogglePicker()
        {
            if (pop != null) { HidePicker(); return; }
            tip.Hide(); int cols = 4, gap = 10, tw = 140, th = 134, w = 14 * 2 + cols * tw + (cols - 1) * gap, h = 14 + 22 + 2 * th + gap + 14 + 2;
            pop = new RPanel(); pop.Fill = Th.SurfHi; pop.SetBounds(M, M + 62, w, h);
            Label t = new Label(); t.AutoSize = false; t.SetBounds(14, 12, w - 28, 18); t.Font = Th.F("Segoe UI Semibold", 8.5f, FontStyle.Regular); t.ForeColor = Th.Muted; t.BackColor = Th.SurfHi; t.Text = U.R("Выбор игры · нажмите на игру, чтобы выбрать или сменить её папку", "Choose a game · click it to pick or change its folder"); pop.Controls.Add(t);
            for (int i = 0; i < GameDef.All.Length + 1; i++)
            {
                GameTile g = new GameTile(); g.SetBounds(14 + (i % cols) * (tw + gap), 40 + (i / cols) * (th + gap), tw, th);
                if (i < GameDef.All.Length)
                {
                    GameDef d = GameDef.All[i]; g.Def = d; g.Sel = d == game; g.Icon = d.Id == "dd" ? gameIcon : null;
                    g.Sub = d.Ready ? (core.HasGame && d.Id == "dd" ? d.Fixes + " " + U.Pl(d.Fixes, U.R("фикс", "fix"), U.R("фикса", "fixes"), U.R("фиксов", "fixes")) : U.R("в базе · укажите папку", "in base · pick folder")) : U.R("скоро", "soon");
                    g.Click += delegate { HidePicker(); if (d.Ready) { game = d; ChooseFolder(); RefreshState(); } else { GoPage("req"); reqBox.Box.Text = d.Name; } };
                }
                else { g.Plus = true; g.Sub = U.R("запросить", "request"); g.Click += delegate { HidePicker(); GoPage("req"); reqBox.Box.Focus(); }; }
                pop.Controls.Add(g);
            }
            Controls.Add(pop); pop.BringToFront();
        }
        protected override bool ProcessCmdKey(ref Message msg, Keys k) { if (k == Keys.Escape && pop != null) { HidePicker(); return true; } return base.ProcessCmdKey(ref msg, k); }

        // ---- requests: written to a local list and sent by e-mail ---------------------------------------------------------
        static string ReqFile() { return Path.Combine(App.DataDir, "requests.txt"); }
        static List<string[]> LoadReqs()   // lines: date|text|state   (state: sent = reached the server, mail = a mail was opened, fail = nothing went; old lines have no state = sent)
        {
            List<string[]> r = new List<string[]>();
            try { if (File.Exists(ReqFile())) foreach (string ln in File.ReadAllLines(ReqFile(), Encoding.UTF8)) { string[] q = ln.Split('|'); if (q.Length >= 2 && q[0].Length > 0) r.Add(q.Length > 2 ? new string[] { q[0], q[1], q[2] } : new string[] { q[0], q[1], "sent" }); } } catch { }
            return r;
        }
        // goes through the same channel as the Feedback window (POST feedback.php); only when that fails a mail is opened - and then it is called "in a mail", not "sent"
        void SendReq()
        {
            string t = reqBox.Box.Text.Trim().Replace("|", "/").Replace("\r", " ").Replace("\n", " "); if (t.Length == 0) { reqBox.Box.Focus(); return; }
            if (t.Length > 500) t = t.Substring(0, 500);
            if (sendBusy) return; sendBusy = true; if (bSend != null) { bSend.Enabled = false; bSend.Text = "\u2026"; }
            string lang = L.Ru ? "ru" : "en", ver = App.Version;
            Thread th = new Thread(delegate()
            {
                string err; try { err = FeedbackForm.Post("[game request] " + t, "", ver, lang, null); } catch (Exception ex) { err = ex.Message; }
                try { BeginInvoke((MethodInvoker)delegate { ReqDone(t, err); }); } catch { }
            }); th.IsBackground = true; th.Start();
        }
        void ReqDone(string t, string err)
        {
            sendBusy = false; string state = "sent";
            if (err != null)
            {
                Log("request: server said: " + err);
                bool opened = U.Open("mailto:" + App.Mail + "?subject=" + Uri.EscapeDataString("GameRemix: " + U.R("запрос игры", "game request")) + "&body=" + Uri.EscapeDataString(t + "\r\n\r\nGameRemix " + App.Version));
                state = opened ? "mail" : "fail";
                if (!opened) MessageBox.Show(this, U.R("Запрос не отправлен: нет связи с сервером (" + err + ") и не открылась почтовая программа. Текст сохранён в поле — повторите позже или напишите на ", "The request was not sent: no connection (" + err + ") and no mail program opened. The text stays in the box — try later or write to ") + App.Mail, L.T("errTitle"), MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
            try { File.AppendAllText(ReqFile(), DateTime.Now.ToString("yyyy-MM-dd HH:mm") + "|" + t + "|" + state + "\r\n", Encoding.UTF8); } catch { }
            if (state != "fail") reqBox.Box.Text = "";
            page = "req"; BuildAll();
        }

        // ---- update: see Updater.cs. latest.txt = "<version>|<https url>|<sha256>"; anything else (HTML of a captive portal, an error page, a foreign host) = "could not check", never "up to date".
        void CheckUpdate(object manual)
        {
            string err; bool bad; UpdateInfo u = Updater.Check(out err, out bad);
            try
            {
                BeginInvoke((MethodInvoker)delegate
                {
                    bool man = (bool)manual; bool fresh = u != null && (upd == null || upd.Version != u.Version); bool boot = bootCheck; bootCheck = false;
                    upd = u; newVer = u != null ? u.Version : null; newUrl = u != null ? u.ManualUrl : null;
                    updText = u != null ? "" : (err != null ? (man ? (err.IndexOf("TLS") >= 0 ? U.R("нужен TLS 1.2 (Win7: KB3140245, .NET 4.5)", "TLS 1.2 needed (Win7: KB3140245, .NET 4.5)") : U.R("нет связи", "offline")) : "") : (bad ? (man ? U.R("не удалось проверить", "could not check") : "") : U.R("актуальная", "up to date")));
                    RefreshFoot();
                    if (u != null && fresh && App.Get("autoupdate") == "1" && u.CanInstall && !busy && !updBusy && !man && boot) { Log("auto-update to " + u.Version); OpenUpdate(true); }   // "install automatically": at the first check after start (the periodic ones only show the badge)
                });
            }
            catch { }
        }
        void OpenUpdate() { OpenUpdate(false); }
        void OpenUpdate(bool auto)
        {
            if (upd == null || updBusy) return; updBusy = true;
            try
            {
                using (UpdateForm f = new UpdateForm(upd, auto))
                {
                    tip.Hide(); f.ShowDialog(this);
                    if (f.Installed)
                    {
                        Log("updated to " + upd.Version + ", restarting");
                        try { Updater.Restart(Updater.TargetExe()); Application.Exit(); Environment.Exit(0); }
                        catch (Exception ex) { Log("restart failed: " + ex.Message); MessageBox.Show(this, U.R("Программа обновлена. Запустите её снова вручную.", "The program is updated. Please start it again by hand."), Text, MessageBoxButtons.OK, MessageBoxIcon.Information); }
                    }
                }
            }
            finally { updBusy = false; }
        }
    }

    class VersionForm : Form
    {
        public VersionForm(Core c)
        {
            bool ok = c.HasGame && c.ExeSupported;
            Text = U.R("Версия игры", "Game version"); FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false; MinimizeBox = false; ShowInTaskbar = false;
            StartPosition = FormStartPosition.CenterParent; ClientSize = new Size(520, 380); BackColor = Th.Bg; ForeColor = Th.Text; Font = Th.Body;
            RichTextBox rt = new RichTextBox(); rt.BorderStyle = BorderStyle.None; rt.BackColor = Th.Surf; rt.ForeColor = Th.Text; rt.ReadOnly = true; rt.ScrollBars = RichTextBoxScrollBars.Vertical; rt.SetBounds(24, 22, 472, 280);
            rt.Font = Th.F("Segoe UI", 9.5f, FontStyle.Regular);
            Action<string, Color, bool> add = delegate(string t, Color col, bool bold) { rt.SelectionStart = rt.TextLength; rt.SelectionColor = col; rt.SelectionFont = Th.F("Segoe UI", 9.5f, bold ? FontStyle.Bold : FontStyle.Regular); rt.SelectedText = t; };
            add(U.R("Найдено:  ", "Found:  "), Th.Faint, false); add("div.exe " + (c.HasGame ? c.ExeVersionText : "—") + "\n", ok ? Th.Green : Th.Red, true);
            add(U.R("Нужно:  ", "Needed:  "), Th.Faint, false); add(U.R("1.0.0.62 (div.exe 2 461 696 Б, 19.04.2013) — сборка Steam и GOG\n\n", "1.0.0.62 (div.exe 2,461,696 B, 2013-04-19) — the Steam and GOG build\n\n"), Th.Text, false);
            add(U.R("Что делают фиксы\n", "What the fixes do\n"), Th.Amber, true);
            add(U.R("Правят несколько байт в div.exe и заменяют две DLL. Адреса этих байт известны только для 1.0.0.62; в другой сборке они иные, поэтому программа не трогает файл, чтобы не сломать игру. Перед любой правкой делается копия оригинала, «Откатить всё» возвращает её.\n\n", "They change a few bytes in div.exe and replace two DLLs. The addresses are known for 1.0.0.62 only; other builds differ, so the program leaves the file alone rather than break the game. An original copy is made before any change and Revert all restores it.\n\n"), Th.Muted, false);
            add(ok ? U.R("Версия подходит — ничего делать не нужно.", "The version fits — nothing to do.") : U.R("Что делать\n", "What to do\n"), ok ? Th.Green : Th.Amber, true);
            if (!ok) add(U.R("Обновите игру до последней версии: Steam — «Проверить целостность файлов», GOG — GOG Galaxy или установщик обновления; другие издания — последний патч издателя. Не выходит — напишите автору версию и размер div.exe: добавим поддержку вашей сборки.", "Update the game to the latest version: Steam — verify file integrity, GOG — GOG Galaxy or the update installer; other editions — the publisher's last patch. If that is not possible, e-mail the author the version and size of div.exe and your build will be added."), Th.Muted, false);
            Btn w = new Btn(); w.Accent = !ok; w.Text = U.R("Написать автору", "E-mail the author"); w.SetBounds(24, 322, 232, 40); w.Click += delegate { U.Open("mailto:" + App.Mail + "?subject=" + Uri.EscapeDataString("GameRemix: " + U.R("версия игры", "game version")) + "&body=" + Uri.EscapeDataString("div.exe " + (c.HasGame ? c.ExeVersionText : "") + "\r\n")); };
            Btn cl = new Btn(); cl.Text = U.R("Закрыть", "Close"); cl.SetBounds(268, 322, 228, 40); cl.Click += delegate { Close(); };
            Controls.AddRange(new Control[] { rt, w, cl }); KeyPreview = true; KeyDown += delegate(object s, KeyEventArgs e) { if (e.KeyCode == Keys.Escape) Close(); }; rt.SelectionStart = 0; rt.SelectionLength = 0; ActiveControl = cl; Dark.Scroll(rt);
        }
        protected override void OnHandleCreated(EventArgs e) { base.OnHandleCreated(e); Dark.Apply(Handle); }
    }

    // pick a game folder: the installs found on this PC + "another folder..." (the current one is marked)
    class GameChoiceForm : Form
    {
        public string Result; public bool Browse;
        public GameChoiceForm(List<string> found, string current)
        {
            Text = U.R("Папка с игрой", "Game folder"); FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false; MinimizeBox = false; ShowInTaskbar = false;
            int n = Math.Min(found.Count, 6), h = 24 + 44 + (n > 0 ? 8 : 0) + n * 46 + 8 + 44 + 8 + 40 + 20;
            StartPosition = FormStartPosition.CenterParent; ClientSize = new Size(560, h); BackColor = Th.Bg; ForeColor = Th.Text; Font = Th.Body;
            Label q = new Label(); q.AutoSize = false; q.SetBounds(24, 18, 512, 40); q.ForeColor = Th.Muted; q.UseMnemonic = false;
            q.Text = n > 0 ? U.R("Найдены установки Divine Divinity. Выберите нужную или укажите другую папку.", "Divine Divinity installs were found. Pick one or choose another folder.") : U.R("Установка не найдена автоматически. Укажите папку с div.exe.", "No install was found automatically. Choose the folder with div.exe.");
            Controls.Add(q); int y = 64;
            for (int i = 0; i < n; i++)
            {
                string path = found[i]; bool cur = current != null && string.Equals(Core.NormPath(path), Core.NormPath(current), StringComparison.OrdinalIgnoreCase);
                Btn b = new Btn(); b.Text = (cur ? "\u2713  " : "") + path; b.Accent = false; b.Pt = 9f; b.SetBounds(24, y, 512, 40); b.Click += delegate { Result = path; Close(); }; Controls.Add(b); y += 46;
            }
            y += 8;
            Btn o = new Btn(); o.Text = U.R("Другая папка…", "Another folder…"); o.Accent = n == 0; o.SetBounds(24, y, 512, 44); o.Click += delegate { Browse = true; Close(); }; Controls.Add(o); y += 52;
            Btn c = new Btn(); c.Text = U.R("Отмена", "Cancel"); c.SetBounds(24, y, 512, 40); c.Click += delegate { Close(); }; Controls.Add(c);
            KeyPreview = true; KeyDown += delegate(object s, KeyEventArgs e) { if (e.KeyCode == Keys.Escape) Close(); };
        }
        protected override void OnHandleCreated(EventArgs e) { base.OnHandleCreated(e); Dark.Apply(Handle); }
    }

    // headless screenshots for self-checks: GameRemix.exe --shot fix|sec|tools|req|picker|about|fonts|tip|changelog|choose FILE [GAMEDIR] [--en]
    // Read-only by default: nothing is saved (no language, no game path, no log). Hooks that WRITE (preset, fontstep, savefmt, divedl, dgedl) need --allow-write.
    static class Shots
    {
        public static void Full(string file)
        {
            Rectangle r = Screen.PrimaryScreen.Bounds; Bitmap b = new Bitmap(r.Width, r.Height);
            using (Graphics g = Graphics.FromImage(b)) g.CopyFromScreen(r.Location, Point.Empty, r.Size);
            b.Save(file);
        }
        // --shot textfit OUT [GAME]: "text always fits" (docs/design.md). Every page of the main window, every wizard step and the tool windows that open without a game
        // (or on a copy) are built in RU and in EN, painted into a bitmap (DrawToBitmap runs every OnPaint, so every TextFit.Draw measures its text) and their Labels are measured;
        // OUT lists the overflows ("window / control / text / needed > available"), then the texts that needed a smaller font. rc 0 = no overflow. Nothing is written to the game.
        static void Paint(Form f, string where)
        {
            TextFit.Where = where; Application.DoEvents();
            using (Bitmap b = new Bitmap(Math.Max(1, f.Width), Math.Max(1, f.Height))) f.DrawToBitmap(b, new Rectangle(0, 0, f.Width, f.Height));
            TextFit.CheckTree(f);
        }
        static void Probe(Func<Form> make, string where, Action<Form, string> walk, StringBuilder err)
        {
            Form f = null;
            try
            {
                f = make(); f.StartPosition = FormStartPosition.Manual; f.Location = new Point(-6000, -6000); f.ShowInTaskbar = false; f.Show();
                for (int i = 0; i < 3; i++) Application.DoEvents();
                if (walk != null) walk(f, where); else Paint(f, where);
            }
            catch (Exception ex) { err.AppendLine("ERROR " + where + ": " + ex.Message); }
            finally { if (f != null) { try { f.Close(); f.Dispose(); } catch { } } }
        }
        static int TextFitAll(string outp, string game)
        {
            TextFit.Probe = true; StringBuilder err = new StringBuilder(); string[] pages = { "fix", "gfx", "gfxstep2", "sec", "tools", "req", "picker" };
            foreach (bool ru in new bool[] { true, false })
            {
                L.Ru = ru; string lg = ru ? "RU" : "EN";
                Probe(delegate { return new MainForm(game); }, lg + " main", delegate(Form f, string w) { MainForm mf = (MainForm)f; foreach (string p in pages) { mf.ShotPage(p); Paint(f, w + "/" + p); } }, err);
                Probe(delegate { return new WizardForm(new Core(game)); }, lg + " wizard", delegate(Form f, string w) { WizardForm wf = (WizardForm)f; for (int i = 0; i < wf.Steps; i++) { wf.ShowStep(i); Paint(f, w + "/step " + (i + 1)); } }, err);
                Probe(delegate { return new AboutForm(); }, lg + " about", null, err);
                Probe(delegate { return new SupportForm(); }, lg + " support", null, err);
                Probe(delegate { return new HelpForm(false); }, lg + " help", null, err);
                Probe(delegate { return new HelpForm(true); }, lg + " help cnc", null, err);
                Probe(delegate { return new CncForm(new Core(game)); }, lg + " cnc", null, err);
                Probe(delegate { return new DgvQualityForm(new Core(game)); }, lg + " dgvoodoo", null, err);
                Probe(delegate { return new FxForm(new Core(game)); }, lg + " fx", null, err);
                Probe(delegate { FxForm x = new FxForm(new Core(game)); return x; }, lg + " fx tab 2", delegate(Form f, string w) { ((FxForm)f).SetTab(1); Paint(f, w); }, err);
                Probe(delegate { return new FeedbackForm(new Core(game)); }, lg + " feedback", null, err);
                Probe(delegate { return new ToolSaveEditor(new Core(game)); }, lg + " save editor", null, err);
                Probe(delegate { return new VersionForm(new Core(game)); }, lg + " version", null, err);
                Probe(delegate { return new FontForm(new Core(game)); }, lg + " fonts", null, err);
                Probe(delegate { return new ChangelogForm(); }, lg + " changelog", null, err);
                Probe(delegate { return new ToolChoiceForm("SaveEditor"); }, lg + " tool choice", null, err);
                Probe(delegate { return new KeyPickForm(U.R("меню эффектов", "effects menu")); }, lg + " key pick", null, err);
                Probe(delegate { return new GameChoiceForm(new List<string>(new string[] { @"X:\GAMES\Divine Divinity", @"D:\Games\Divine Divinity (GOG)", @"C:\Program Files (x86)\Steam\steamapps\common\Divine Divinity" }), @"X:\GAMES\Divine Divinity"); }, lg + " game choice", null, err);
                foreach (Art art in Art.DivineDivinity()) { Art ar = art; Probe(delegate { return new ArticleForm(ar); }, lg + " article", null, err); }
            }
            StringBuilder o = new StringBuilder();
            o.AppendLine((TextFit.Over.Count == 0 && err.Length == 0 ? "ok" : "FAIL") + " overflow=" + TextFit.Over.Count + " shrunk=" + TextFit.Shrunk.Count);
            o.Append(err); foreach (string s in TextFit.Over) o.AppendLine("OVER " + s);
            foreach (string s in TextFit.Shrunk) o.AppendLine("SHRUNK " + s);
            foreach (KeyValuePair<string, int> kv in TextFit.Measured) o.AppendLine("MEASURED " + kv.Key + ": " + kv.Value);
            File.WriteAllText(outp, o.ToString(), Encoding.UTF8); return TextFit.Over.Count == 0 && err.Length == 0 ? 0 : 1;
        }
        static int Fail(string file, string msg) { try { if (file != null) File.WriteAllText(file, "ERROR " + msg, Encoding.UTF8); } catch { } return 2; }   // file == null: the second argument is a save file (savefmt) - never overwrite it with an error
        public static int Run(string[] a)
        {
            bool allow = Array.IndexOf(a, "--allow-write") >= 0; App.ReadOnly = !allow;
            Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false);
            string what = a[1], outp = a[2], errf = what == "savefmt" ? null : outp;
            L.Ru = Array.IndexOf(a, "--en") < 0; L.Forced = true;   // RU unless --en; the saved language is neither read nor changed
            bool writes = what == "preset" || what == "fx" || what == "fontstep" || what == "savefmt" || what == "divedl" || what == "dgedl";
            if (writes && !allow) return Fail(errf, "'" + what + "' changes files: add --allow-write (and use a COPY of the game)");
            try
            {
                if (what == "divedl") { string e = DivEdit.Fetch(); File.WriteAllText(outp, e == null ? "OK " + DivEdit.ExePath + " " + File.Exists(DivEdit.ExePath) : e); return 0; }
                if (what == "dgedl") { string e = Dge.Fetch(); File.WriteAllText(outp, e == null ? "OK " + Dge.ExePath + " " + File.Exists(Dge.ExePath) : e); return 0; }
                if (what == "savefmt") { SaveData sd = SaveData.Open(a[2]); if (a.Length > 3 && a[3] != "-" && !a[3].StartsWith("--")) { string[] v = a[3].Split(','); for (int i = 0; i < 4; i++) sd.SetBase(i, uint.Parse(v[i]), true); }
                    if (a.Length > 4 && !a[4].StartsWith("--")) { foreach (string kv in a[4].Split(',')) { string[] q = kv.Split(':'); sd.SetSkill(sd.Skills[int.Parse(q[0])], uint.Parse(q[1])); } } sd.Write(); return 0; }
                if (what == "preset")   // --shot preset OUT GAME K [cnc|dgv] [revert] --allow-write
                {
                    int k; if (a.Length < 5 || !int.TryParse(a[4], out k) || k < 0 || k > 2) return Fail(outp, "preset: K must be 0, 1 or 2");
                    Core c = new Core(a[3]); StringBuilder lg = new StringBuilder(); c.Log = delegate(string x) { lg.AppendLine(x); }; c.Warn = delegate(string x) { lg.AppendLine("WARN " + x); };
                    List<string> sk = c.ApplyPreset(k, a.Length > 5 && a[5] == "cnc"); if (Array.IndexOf(a, "revert") >= 0) c.RevertPreset();
                    File.WriteAllText(outp, "ok" + (sk.Count > 0 ? " skipped: " + string.Join("; ", sk.ToArray()) : "") + "\r\n" + lg); return 0;
                }
                if (what == "fx") { Core c = new Core(a[3]); FxState fs = c.FxRead(); fs.Shaders = false; fs.Fps = false; for (int i = 5; i < a.Length; i++) { if (a[i] == "shaders") fs.Shaders = true; if (a[i] == "fps") fs.Fps = true; if (a[i].StartsWith("key=")) { string[] k = a[i].Substring(4).Split(','); fs.KMenu = int.Parse(k[0]); fs.KFps = int.Parse(k[1]); fs.KFx = int.Parse(k[2]); } } c.FxApply(fs); FxState r = c.FxRead(); File.WriteAllText(outp, "shaders=" + r.Shaders + " fps=" + r.Fps + " keys=" + r.KMenu + "," + r.KFps + "," + r.KFx + " cnc=" + c.Cnc + "\r\n"); return 0; }
                if (what == "fontstep") { Core c = new Core(a[3]); StringBuilder fo = new StringBuilder(); for (int i = 4; i < a.Length; i++) { if (a[i].StartsWith("--")) continue; int cat = int.Parse(a[i].Substring(0, 1)), st = int.Parse(a[i].Substring(1)); if (cat < 0 || cat > 2) return Fail(outp, "fontstep: group must be 0..2"); c.SetFontStep(cat, st); fo.AppendLine(a[i] + " -> step " + c.FontStep(cat)); } File.WriteAllText(outp, fo.ToString()); return 0; }
                if (what == "wizsteps") { Core c = new Core(a.Length > 3 ? a[3] : ""); using (WizardForm w = new WizardForm(c)) { w.Show(); for (int i = 0; i < w.Steps; i++) { w.ShowStep(i); Application.DoEvents(); } string fp = w.FontProbe(); w.Close(); File.WriteAllText(outp, "ok fonts " + fp); return 0; } }   // logic check: every wizard step builds without an error (nothing is drawn to a file, nothing is written)
                if (what == "cardlayout")   // self-test of the design ban (docs/design.md): a badge / check mark / recommendation never moves or narrows the text of a card
                {
                    StringBuilder ol = new StringBuilder(); bool ok = true;
                    foreach (int kind in new int[] { 0, 1, 2 })   // 0 picture card, 1 text card, 2 compact pill
                    {
                        Rectangle[] r0 = null;
                        foreach (int v in new int[] { 0, 1, 2, 3 })   // none / badge / badge + selected / selected, long badge text
                        {
                            WizCard c = new WizCard(); c.SetBounds(0, 0, kind == 2 ? 135 : 272, kind == 0 ? 330 : (kind == 1 ? 190 : 44)); c.Compact = kind == 2; if (kind == 0) c.Img = new Bitmap(10, 10);
                            c.Title = "Title"; c.Sub = "Text of the card"; c.Badge = v == 0 || v == 3 ? "" : (v == 1 ? "\u2605 recommended" : "\u2605"); c.Sel = v >= 2;
                            Rectangle[] r = c.Slots(); if (r0 == null) r0 = r; else if (r[0] != r0[0] || r[1] != r0[1]) { ok = false; ol.AppendLine("kind " + kind + " variant " + v + ": title " + r[0] + " text " + r[1] + " differ from " + r0[0] + " " + r0[1]); }
                            if (kind != 2 && r[2].Bottom > c.Height) { ok = false; ol.AppendLine("badge strip outside the card, kind " + kind); }
                            if (kind != 2 && r[1].Bottom > r[2].Top) { ok = false; ol.AppendLine("text overlaps the badge strip, kind " + kind); }
                            if (r[3].Left < r[0].Right) { ok = false; ol.AppendLine("check mark overlaps the title, kind " + kind); }
                        }
                    }
                    File.WriteAllText(outp, (ok ? "ok" : "FAIL") + "\r\n" + ol); return ok ? 0 : 1;
                }
                if (what == "textfit") return TextFitAll(outp, a.Length > 3 && !a[3].StartsWith("--") ? a[3] : "");
                if (what == "logzip") { File.WriteAllBytes(outp, new Core(a.Length > 3 && !a[3].StartsWith("--") ? a[3] : "").CollectLogs()); return 0; }
            }
            catch (Exception ex) { return Fail(errf, ex.Message); }
            Form f; string game = a.Length > 3 && !a[3].StartsWith("--") ? a[3] : null;
            if (what == "about") f = new AboutForm();
            else if (what == "quick") f = new WizardForm(new Core(game ?? ""));
            else if (what == "help") f = new HelpForm(false);
            else if (what == "helpc") f = new HelpForm(true);
            else if (what == "cnc") f = new CncForm(new Core(game ?? ""));
            else if (what == "feedback") f = new FeedbackForm(new Core(game ?? ""));
            else if (what == "save") f = new ToolSaveEditor(new Core(game ?? ""));
            else if (what == "dgvq") f = new DgvQualityForm(new Core(game ?? ""));
            else if (what == "article") f = new ArticleForm(Art.DivineDivinity()[0]);
            else if (what == "version") f = new VersionForm(new Core(game ?? ""));
            else if (what == "fonts") f = new FontForm(new Core(game ?? ""));
            else if (what == "fxwin") f = new FxForm(new Core(game ?? ""));
            else if (what == "fxwin2") { FxForm fx0 = new FxForm(new Core(game ?? "")); fx0.SetTab(1); f = fx0; }
            else if (what == "changelog") f = new ChangelogForm();
            else if (what == "choose") f = new GameChoiceForm(new List<string>(new string[] { @"X:\GAMES\Divine Divinity", @"D:\Games\Divine Divinity (GOG)", @"C:\Program Files (x86)\Steam\steamapps\common\Divine Divinity" }), @"X:\GAMES\Divine Divinity");
            else if (what == "tip")
            {
                TipForm t = new TipForm(); f = new Form(); f.ClientSize = new Size(420, 220); f.BackColor = Th.Bg; f.Show();
                t.ShowFor(f, f, new Rectangle(20, 20, 18, 18), "Закат и рассвет", "Плавная смена дня и ночи без скачков."); t.Location = f.PointToScreen(new Point(20, 50)); Application.DoEvents();
                Bitmap bt = new Bitmap(t.Width, t.Height); t.DrawToBitmap(bt, new Rectangle(0, 0, t.Width, t.Height)); bt.Save(outp); return 0;
            }
            else if (Array.IndexOf(new string[] { "fix", "gfx", "gfxstep2", "sec", "tools", "req", "picker" }, what) >= 0) { MainForm mf = new MainForm(game); f = mf; f.StartPosition = FormStartPosition.Manual; f.Location = new Point(40, 40); f.TopMost = true; f.Show(); f.Activate(); mf.ShotPage(what); }
            else return Fail(outp, "unknown screen: " + what);
            f.StartPosition = FormStartPosition.Manual; f.Location = new Point(40, 40); f.TopMost = true; f.Show(); f.Activate();
            for (int i = 0; i < 8; i++) { Application.DoEvents(); System.Threading.Thread.Sleep(100); }
            Point o = f.PointToScreen(Point.Empty); Bitmap b = new Bitmap(f.ClientSize.Width, f.ClientSize.Height);
            using (Graphics g = Graphics.FromImage(b)) g.CopyFromScreen(o, Point.Empty, b.Size);
            b.Save(outp); return 0;
        }
    }
}
