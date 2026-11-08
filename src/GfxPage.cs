// The "Graphics" page: a big Before | After preview, the choice of the game picture and the interface skin, the other graphics settings and the fixes in one place,
// and one bottom bar "Changes: ... [Apply] [Restore original]". Choosing changes NOTHING on disk; Apply does everything in one action (Core.GfxApply).
// Layout and controls: docs/design.md (section "Graphics"). Data: games/<id>/gfx/gfx.txt, help texts: Help.cs.
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.IO;
using System.Threading;
using System.Windows.Forms;

namespace DDFixTool
{
    // Before | After for one or more windows (inventory, dialogue): one divider fraction for all panes - one slider moves every preview together. Pictures are owned by the caller.
    class BeforeAfter : Control
    {
        public Image[] Before = new Image[0], After = new Image[0]; public string[] PaneTitles = new string[0]; public string CapBefore = "", CapAfter = ""; float split = 0.5f; bool drag; const int Gap = 8; public const int BarH = 30, InfoH = 32; public float Zoom = 1f; int PH { get { return Height - BarH - InfoH; } } int TL { get { return 14; } } int TR { get { return Width - 14; } }
        public BeforeAfter() { SetStyle(ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw | ControlStyles.Selectable, true); TabStop = true; BackColor = Th.Surf; }
        public float Split { get { return split; } set { split = Math.Max(0f, Math.Min(1f, value)); Invalidate(); } }
        int Panes { get { return Math.Max(1, Math.Max(Before.Length, After.Length)); } }
        Rectangle Pane(int i) { int n = Panes, w = (Width - Gap * (n - 1)) / n; return new Rectangle(i * (w + Gap), 0, w, PH); }
        void MoveTo(int x) { Split = (x - TL) / (float)Math.Max(1, TR - TL); }   // ONE slider under both pictures: the position on the track is the fraction in every picture
        protected override void OnMouseDown(MouseEventArgs e) { Focus(); if (e.Y >= PH) { drag = true; MoveTo(e.X); } base.OnMouseDown(e); }
        protected override void OnMouseMove(MouseEventArgs e) { if (drag) MoveTo(e.X); Cursor = drag || e.Y >= PH ? Cursors.Hand : Cursors.Default; base.OnMouseMove(e); }
        protected override void OnMouseUp(MouseEventArgs e) { drag = false; base.OnMouseUp(e); }
        protected override bool IsInputKey(Keys k) { return k == Keys.Left || k == Keys.Right || base.IsInputKey(k); }
        protected override void OnKeyDown(KeyEventArgs e) { if (e.KeyCode == Keys.Left) { Split = split - 0.05f; e.Handled = true; } else if (e.KeyCode == Keys.Right) { Split = split + 0.05f; e.Handled = true; } base.OnKeyDown(e); }
        protected override void OnGotFocus(EventArgs e) { base.OnGotFocus(e); Invalidate(); }
        protected override void OnLostFocus(EventArgs e) { base.OnLostFocus(e); Invalidate(); }
        void Chip(Graphics g, string t, int x, int y, bool right, Color fg)
        {
            if (t.Length == 0) return; Size sz = TextRenderer.MeasureText(g, t, Th.Small, new Size(400, 20), TextFormatFlags.NoPadding | TextFormatFlags.NoPrefix);
            Rectangle r = new Rectangle(right ? x - sz.Width - 16 : x, y, sz.Width + 16, 20);
            using (GraphicsPath p = Th.RR(r, 6)) using (SolidBrush b = new SolidBrush(Color.FromArgb(190, 20, 17, 12))) g.FillPath(b, p);
            TextFit.Draw(g, this, t, Th.Small, r, fg, TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding | TextFormatFlags.NoPrefix);
        }
        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics; g.SmoothingMode = SmoothingMode.AntiAlias; g.Clear(Th.Surf); int n = Panes, ph = PH;
            for (int i = 0; i < n; i++)
            {
                Rectangle pr = Pane(i); int sx = pr.X + 1 + (int)((pr.Width - 2) * split); Image bi = i < Before.Length ? Before[i] : null, ai = i < After.Length ? After[i] : null;
                using (GraphicsPath clip = Th.RR(new RectangleF(pr.X + 0.5f, 0.5f, pr.Width - 2, ph - 2), 10))
                {
                    GraphicsState st = g.Save(); g.SetClip(clip); g.InterpolationMode = InterpolationMode.HighQualityBicubic; g.PixelOffsetMode = PixelOffsetMode.HighQuality;
                    using (SolidBrush b = new SolidBrush(Color.FromArgb(24, 21, 16))) g.FillRectangle(b, pr);
                    Rectangle all = new Rectangle(pr.X + 1, 1, pr.Width - 2, ph - 2);
                    // the handle is a "quality" slider: far left = the whole picture is the original, far right = the whole picture is the new one;
                    // so the NEW picture fills from the left edge up to the divider and the original stays at the right of it
                    if (ai != null) { g.SetClip(new Rectangle(pr.X, 0, sx - pr.X, ph), CombineMode.Intersect); g.DrawImage(ai, all); g.ResetClip(); g.SetClip(clip); }
                    if (bi != null) { g.SetClip(new Rectangle(sx, 0, pr.Right - sx, ph), CombineMode.Intersect); g.DrawImage(bi, all); g.ResetClip(); g.SetClip(clip); }
                    else TextFit.Draw(g, this, U.R("нет картинки", "no picture"), Th.Body, new Rectangle(sx, 0, pr.Right - sx, ph), Th.Faint, TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter);
                    g.Restore(st);
                }
                using (GraphicsPath p = Th.RR(new RectangleF(pr.X + 0.5f, 0.5f, pr.Width - 2, ph - 2), 10)) using (Pen pen = new Pen(Focused ? Th.Amber : Th.Line, Focused ? 2f : 1f)) g.DrawPath(pen, p);
                if (i == 0) Chip(g, CapAfter, pr.X + 10, 10, false, Th.Amber); if (i == n - 1) Chip(g, CapBefore, pr.Right - 10, 10, true, Color.FromArgb(240, 236, 224));
                if (i < PaneTitles.Length) Chip(g, PaneTitles[i], pr.X + 10, ph - 30, false, Th.Muted);
                g.SetClip(new Rectangle(pr.X + 1, 1, pr.Width - 2, ph - 2));   // the line never leaves its own pane
                using (Pen sh = new Pen(Color.FromArgb(120, 0, 0, 0), 4f)) g.DrawLine(sh, sx, 1, sx, ph - 2);
                using (Pen ln = new Pen(Color.FromArgb(235, 255, 255, 255), 2f)) g.DrawLine(ln, sx, 1, sx, ph - 2);
                g.ResetClip();
            }
            PaintSize(g, ph + BarH);
            // the one slider: the handle moves the divider in both pictures: your choice at the left of it, the original at the right
            int cy = ph + BarH / 2 + 1, hx = TL + (int)((TR - TL) * split); TextFormatFlags tf = TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding | TextFormatFlags.EndEllipsis | TextFormatFlags.NoPrefix;
            using (Pen tr = new Pen(Th.Line, 4f)) { tr.StartCap = LineCap.Round; tr.EndCap = LineCap.Round; g.DrawLine(tr, TL, cy, TR, cy); }
            using (Pen tr = new Pen(Th.Amber, 4f)) { tr.StartCap = LineCap.Round; tr.EndCap = LineCap.Round; g.DrawLine(tr, TL, cy, hx, cy); }   // amber fills from the left up to the handle: the further right, the more of the new picture
            Rectangle hd = new Rectangle(hx - 13, cy - 13, 26, 26);
            using (SolidBrush b = new SolidBrush(Th.Amber)) g.FillEllipse(b, hd); using (Pen pen = new Pen(Focused ? Th.Text : Color.FromArgb(235, 255, 255, 255), 2f)) g.DrawEllipse(pen, hd);
            TextRenderer.DrawText(g, "\u25C0\u25B6", Th.F("Segoe UI Symbol", 7f, FontStyle.Regular), hd, Th.OnAmber, TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding);
        }
        void PaintSize(Graphics g, int y)
        {
            Rectangle mon = new Rectangle(6, y + 6, 44, 25); float z = Math.Max(1f, Zoom); int pct = (int)Math.Round(z * 100);
            using (Pen pen = new Pen(Th.Muted, 1.5f)) g.DrawRectangle(pen, mon);
            int iw = (int)((mon.Width - 4) / z), ih = (int)((mon.Height - 4) / z);
            using (SolidBrush b = new SolidBrush(Color.FromArgb(z > 1.001f ? 210 : 90, Th.Amber))) g.FillRectangle(b, mon.X + (mon.Width - iw) / 2, mon.Y + (mon.Height - ih) / 2, iw, ih);
            string t = z > 1.001f ? U.R("Размер интерфейса " + pct + "%: интерфейс и мир крупнее в " + (pct / 100f).ToString("0.##") + " раза, но в кадр попадает только " + (int)Math.Round(100 / z) + "% поля игры (жёлтый прямоугольник — что видно на мониторе)", "Interface size " + pct + "%: the interface and the world are " + (pct / 100f).ToString("0.##") + "x bigger, but only " + (int)Math.Round(100 / z) + "% of the game view fits (the amber box is what you see on the monitor)") : U.R("Размер интерфейса 100%: как в оригинале, виден весь кадр игры", "Interface size 100%: as in the original, the whole game view is visible");
            TextFit.Draw(g, this, t, Th.Small, new Rectangle(60, y, Width - 66, InfoH), Th.Muted, TextFormatFlags.VerticalCenter | TextFormatFlags.WordBreak | TextFormatFlags.NoPrefix | TextFormatFlags.EndEllipsis);
        }
        Rectangle Zoomed(Rectangle r) { if (Zoom <= 1.001f) return r; int w = (int)(r.Width * Zoom), h = (int)(r.Height * Zoom); return new Rectangle(r.X + (r.Width - w) / 2, r.Y + (r.Height - h) / 2, w, h); }   // the interface size: the picture is bigger, the field of view smaller
    }

    class GfxItem { public string Text = "", Status = "", Reason = ""; public Color StatusColor = Th.Faint; public bool Enabled = true; }

    // a vertical list of choices (radio dot, name, status at the right); disabled ones are grey and say why in a tip
    class GfxChoice : Control
    {
        public const int HeadH = 26, RowH = 27, ChipReserve = 84;   // the header chip ("★ for you" / "applied") sits in a RESERVED place at the right: the title has the same width with and without it (design ban on shifting text for badges)
        public string Title = "", Num = "", HiText = ""; public int Hi;   // Hi: 1 = picked by quick setup, not applied yet (amber chip in the header), 2 = applied (green chip)
        public List<GfxItem> Items = new List<GfxItem>(); int sel, hot = -1; Btn help; System.Windows.Forms.Timer hotT;
        public event Action<int> Picked; public event Action<int> Hover;   // Hover(-1) = left
        public GfxChoice() { SetStyle(ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw | ControlStyles.Selectable, true); TabStop = true; BackColor = Th.Surf; }
        public int Selected { get { return sel; } set { sel = value; Invalidate(); } }
        public int Wanted { get { return Items.Count * RowH + HeadH + 4; } }
        public void AddHelp(string key, IWin32Window owner)
        {
            help = new Btn(); help.Under = Th.Surf; help.Pt = 8f; help.Text = "?"; help.Size = new Size(22, 22); help.Location = new Point(Width - 22, 2); help.Anchor = AnchorStyles.Top | AnchorStyles.Right; Controls.Add(help); help.Click += Help.Click(owner, key);
        }
        int At(int y) { int i = (y - HeadH) / RowH; return y >= HeadH && i >= 0 && i < Items.Count ? i : -1; }
        protected override void OnMouseMove(MouseEventArgs e) { int i = At(e.Y); if (i != hot) { hot = i; Invalidate(); if (Hover != null) Hover(i); } if (hot >= 0) { if (hotT == null) { hotT = new System.Windows.Forms.Timer(); hotT.Interval = 80; hotT.Tick += delegate { if (hot >= 0 && (!IsHandleCreated || !ClientRectangle.Contains(PointToClient(Cursor.Position)))) { hot = -1; hotT.Stop(); Invalidate(); if (Hover != null) Hover(-1); } }; } hotT.Start(); } base.OnMouseMove(e); }   // hover only under the mouse: the timer checks the real cursor
        protected override void Dispose(bool d) { if (hotT != null) { hotT.Stop(); hotT.Dispose(); hotT = null; } base.Dispose(d); }
        protected override void OnMouseLeave(EventArgs e) { if (hot != -1) { hot = -1; Invalidate(); if (Hover != null) Hover(-1); } base.OnMouseLeave(e); }
        protected override void OnMouseDown(MouseEventArgs e) { Focus(); int i = At(e.Y); if (i >= 0 && Items[i].Enabled) Choose(i); base.OnMouseDown(e); }
        void Choose(int i) { if (i == sel) { if (Picked != null) Picked(i); return; } sel = i; Invalidate(); if (Picked != null) Picked(i); }
        protected override bool IsInputKey(Keys k) { return k == Keys.Up || k == Keys.Down || base.IsInputKey(k); }
        protected override void OnKeyDown(KeyEventArgs e)
        {
            int d = e.KeyCode == Keys.Up ? -1 : (e.KeyCode == Keys.Down ? 1 : 0);
            if (d != 0) { for (int i = sel + d; i >= 0 && i < Items.Count; i += d) if (Items[i].Enabled) { Choose(i); break; } e.Handled = true; }
            base.OnKeyDown(e);
        }
        protected override void OnGotFocus(EventArgs e) { base.OnGotFocus(e); Invalidate(); }
        protected override void OnLostFocus(EventArgs e) { base.OnLostFocus(e); Invalidate(); }
        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics; g.SmoothingMode = SmoothingMode.AntiAlias; g.Clear(Th.Surf);
            int tx = 2;
            if (Num.Length > 0)
            {
                Rectangle nb = new Rectangle(0, 3, 20, 20); tx = 28;
                using (GraphicsPath p = Th.RR(nb, 6)) using (SolidBrush b = new SolidBrush(Th.Amber)) g.FillPath(b, p);
                TextRenderer.DrawText(g, Num, Th.F("Segoe UI Semibold", 8.5f, FontStyle.Regular), nb, Th.OnAmber, TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding);
            }
            TextFit.Draw(g, this, Title, Th.F("Segoe UI Semibold", 10f, FontStyle.Regular), new Rectangle(tx, 0, Math.Max(20, Width - tx - 28 - (HiText.Length > 0 ? ChipReserve : 0)), HeadH), Th.Text, TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding | TextFormatFlags.EndEllipsis | TextFormatFlags.NoPrefix);
            if (Hi > 0 && HiText.Length > 0)
            {
                Color hc = Hi == 1 ? Th.Amber : Th.Green; Size hs = TextRenderer.MeasureText(g, HiText, Th.Small, new Size(300, 20), TextFormatFlags.NoPadding | TextFormatFlags.NoPrefix); Rectangle chip = new Rectangle(Width - 28 - hs.Width - 14, 4, hs.Width + 14, 18);
                using (GraphicsPath cp = Th.RR(chip, 6)) { using (SolidBrush b = new SolidBrush(Th.Mix(Th.Surf, hc, 0.18f))) g.FillPath(b, cp); using (Pen pen = new Pen(hc, 1f)) g.DrawPath(pen, cp); }
                TextFit.Draw(g, this, HiText, Th.Small, chip, hc, TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding | TextFormatFlags.NoPrefix);
            }
            for (int i = 0; i < Items.Count; i++)
            {
                GfxItem it = Items[i]; Rectangle r = new Rectangle(0, HeadH + i * RowH, Width, RowH - 2); bool on = i == sel;
                using (GraphicsPath p = Th.RR(new RectangleF(r.X + 0.5f, r.Y + 0.5f, r.Width - 1, r.Height - 1), 7))
                {
                    if (on || (i == hot && it.Enabled)) using (SolidBrush b = new SolidBrush(on ? Th.Mix(Th.Surf, Th.Amber, 0.16f) : Th.SurfHi)) g.FillPath(b, p);
                    using (Pen pen = new Pen(on ? Th.Amber : Th.Line, on ? 1.5f : 1f)) g.DrawPath(pen, p);
                }
                if (on && Focused) ControlPaint.DrawFocusRectangle(g, new Rectangle(r.X + 3, r.Y + 3, r.Width - 6, r.Height - 6));
                Rectangle dot = new Rectangle(r.X + 10, r.Y + r.Height / 2 - 6, 12, 12);
                using (Pen pen = new Pen(!it.Enabled ? Th.Faint : (on ? Th.Amber : Th.Muted), 1.5f)) g.DrawEllipse(pen, dot);
                if (on) using (SolidBrush b = new SolidBrush(Th.Amber)) g.FillEllipse(b, dot.X + 3, dot.Y + 3, 6, 6);
                Color tc = !it.Enabled ? Th.Faint : Th.Text; int nw = TextRenderer.MeasureText(it.Text, Th.F("Segoe UI", 9f, FontStyle.Regular), new Size(400, 20), TextFormatFlags.NoPadding).Width + 4;   // the name is never cut for the status: the status takes what is left (full text in the tip)
                int sw = it.Status.Length > 0 ? Math.Min(TextRenderer.MeasureText(it.Status, Th.F("Segoe UI", 8f, FontStyle.Regular), new Size(400, 20), TextFormatFlags.NoPadding).Width + 6, Math.Max(44, r.Width - 30 - 8 - nw - 6)) : 0;
                TextFit.Draw(g, this, it.Text, Th.F("Segoe UI", 9f, FontStyle.Regular), new Rectangle(r.X + 30, r.Y, r.Width - 30 - sw - 8, r.Height), tc, TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding | TextFormatFlags.EndEllipsis | TextFormatFlags.NoPrefix);
                if (sw > 0) TextFit.Draw(g, this, it.Status, Th.F("Segoe UI", 8f, FontStyle.Regular), new Rectangle(r.Right - sw - 8, r.Y, sw, r.Height), it.StatusColor, TextFormatFlags.VerticalCenter | TextFormatFlags.Right | TextFormatFlags.NoPadding | TextFormatFlags.EndEllipsis | TextFormatFlags.NoPrefix);
            }
        }
    }

    // a compact settings row of the Graphics page: title and state in two lines at the left, the control at the right, "?" beside the title
    class MiniRow : Control
    {
        public string Title = "", Status = ""; public Color StatusColor = Th.Faint; Control ctl; public Func<string[]> Tip; public event Action<MiniRow, bool> TipHover; bool inTip; Btn help; public bool Stacked; public int Hi;   // Hi: 1 = picked by quick setup (amber frame), 2 = applied (green frame)
          // Stacked: the control sits under the title (a wide control in a narrow column)
        public MiniRow() { SetStyle(ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true); Height = RowCtl.H; BackColor = Th.Inset; }
        public Control Ctl { get { return ctl; } set { ctl = value; Controls.Add(ctl); Place(); } }
        public virtual Rectangle TextRect { get { return new Rectangle(10, 0, Math.Max(0, (ctl != null && !Stacked ? ctl.Left : Width) - 18), Height); } }
        public void AddHelp(string key, IWin32Window owner)
        {
            help = new Btn(); help.Under = Th.Inset; help.Pt = 8f; help.Text = "?"; help.Size = new Size(22, 22); Controls.Add(help); help.Click += Help.Click(owner, key); Place();
        }
        void Place()
        {
            // "?" always in the same place (top right corner of the row); a side control sits left of it, a stacked one under the title
            int hx = help != null ? Width - 10 - help.Width : Width - 10;
            if (ctl != null) ctl.Location = Stacked ? new Point(10, Height - ctl.Height - 8) : new Point((help != null ? hx - 8 : Width - 10) - ctl.Width, (Height - ctl.Height) / 2);
            if (help != null) help.Location = new Point(hx, 8);
        }
        protected override void OnResize(EventArgs e) { base.OnResize(e); Place(); }
        protected override void OnMouseMove(MouseEventArgs e) { bool on = TextRect.Contains(e.Location) && Tip != null; if (on != inTip) { inTip = on; if (TipHover != null) TipHover(this, on); } base.OnMouseMove(e); }
        protected override void OnMouseLeave(EventArgs e) { if (inTip) { inTip = false; if (TipHover != null) TipHover(this, false); } base.OnMouseLeave(e); }
        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics; g.SmoothingMode = SmoothingMode.AntiAlias; g.Clear(Th.Surf);
            using (GraphicsPath p = Th.RR(new RectangleF(0.5f, 0.5f, Width - 1.5f, Height - 1.5f), 9)) using (SolidBrush b = new SolidBrush(Th.Inset)) g.FillPath(b, p);
            if (Hi > 0) using (GraphicsPath hp = Th.RR(new RectangleF(1f, 1f, Width - 3f, Height - 3f), 8)) { using (SolidBrush b = new SolidBrush(Th.Mix(Th.Inset, Hi == 1 ? Th.Amber : Th.Green, 0.12f))) g.FillPath(b, hp); using (Pen pen = new Pen(Hi == 1 ? Th.Amber : Th.Green, 1.5f)) g.DrawPath(pen, hp); }
            Color c = Enabled ? Th.Text : Th.Faint; int right = (ctl != null && !Stacked ? ctl.Left : Width) - 8; Font tf = Th.F("Segoe UI Semibold", 9f, FontStyle.Regular);
            TextFormatFlags fl = TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding | TextFormatFlags.EndEllipsis | TextFormatFlags.NoPrefix;
            if (Stacked)   // wide control under the title (Interface size): title on top, no state line
            {
                TextFit.Draw(g, this, Title, tf, new Rectangle(10, Height >= RowCtl.H ? 4 : 3, Math.Max(0, right - 38), Height >= RowCtl.H ? 20 : 18), c, fl);
                TextFit.Draw(g, this, Status, Th.F("Segoe UI", 8f, FontStyle.Regular), new Rectangle(10, Height >= RowCtl.H ? 24 : 21, Math.Max(0, right - 10), 15), StatusColor, fl);
                return;
            }
            // ONE line (owner 07.11): name at the left, the control at the right, WHAT IS ON in short words in the middle between them
            int tw = Math.Min(TextRenderer.MeasureText(Title, tf, new Size(400, 24), TextFormatFlags.NoPadding).Width + 2, Math.Max(0, right - 10));
            TextFit.Draw(g, this, Title, tf, new Rectangle(10, 0, tw, Height), c, fl);
            int zx = 10 + tw + 6, zw = Math.Max(0, right - zx);
            if (Status.Length > 0 && zw > 12) TextFit.Draw(g, this, Status, Th.F("Segoe UI", 8f, FontStyle.Regular), new Rectangle(zx, 0, zw, Height), StatusColor, fl | TextFormatFlags.HorizontalCenter);
        }
    }

    // a settings row in ONE look (owner 07.11): [ Off ] Name [ On ] with the state in small words under the name, "?" at the right; the active side is amber.
    // Selected: 0 = left, 1 = right, -1 = neither (something of your own). TitleClick: the name opens a window (Fonts), shown as "Name >".
    class TriRow : MiniRow
    {
        int sel; public int Selected { get { return sel; } set { if (sel != value) { sel = value; Invalidate(); } } } public string Left = "", Right = ""; public event EventHandler Changed; public Action TitleClick; public bool ReclickOn; /* pressing "On" again fires Changed too (Fonts: it opens the window every time) */ int hotCell = -1; System.Windows.Forms.Timer hotT;
        public const int CellW = 52, CellH = 28; public int Cw = CellW;   // Cw: half-button width (44 in the narrow Items column: its middle is then 90 px wide)
        public TriRow() { Cursor = Cursors.Default; }
        Rectangle CellRect(int i) { int rx = Width - 10 - 22 - 8 - Cw; return i == 0 ? new Rectangle(10, (Height - CellH) / 2, Cw, CellH) : new Rectangle(rx, (Height - CellH) / 2, Cw, CellH); }
        public Rectangle ZoneRect { get { return Zone; } }
        Rectangle Zone { get { return new Rectangle(10 + Cw + 6, 0, Math.Max(0, Width - 10 - 22 - 8 - Cw - 6 - (10 + Cw + 6)), Height); } }
        public override Rectangle TextRect { get { return Zone; } }
        int CellAt(Point p) { for (int i = 0; i < 2; i++) if (CellRect(i).Contains(p)) return i; return -1; }
        protected override void OnMouseMove(MouseEventArgs e)
        {
            int c = Enabled ? CellAt(e.Location) : -1; bool title = TitleClick != null && Enabled && Zone.Contains(e.Location);
            if (c != hotCell) { hotCell = c; Invalidate(); }
            Cursor = c >= 0 || title ? Cursors.Hand : Cursors.Default;
            if (hotCell >= 0) { if (hotT == null) { hotT = new System.Windows.Forms.Timer(); hotT.Interval = 80; hotT.Tick += delegate { if (hotCell >= 0 && (!IsHandleCreated || !ClientRectangle.Contains(PointToClient(Cursor.Position)))) { hotCell = -1; hotT.Stop(); Invalidate(); } }; } hotT.Start(); }   // hover only under the mouse
            base.OnMouseMove(e);
        }
        protected override void OnMouseLeave(EventArgs e) { if (hotCell != -1) { hotCell = -1; Invalidate(); } if (hotT != null) hotT.Stop(); base.OnMouseLeave(e); }
        protected override void OnMouseUp(MouseEventArgs e)
        {
            if (Enabled && e.Button == MouseButtons.Left)
            {
                int c = CellAt(e.Location);
                if (c >= 0) { if (c != sel || (ReclickOn && c == 1)) { sel = c; Invalidate(); if (Changed != null) Changed(this, EventArgs.Empty); } }
                else if (TitleClick != null && Zone.Contains(e.Location)) TitleClick();
            }
            base.OnMouseUp(e);
        }
        protected override void Dispose(bool d) { if (hotT != null) { hotT.Stop(); hotT.Dispose(); hotT = null; } base.Dispose(d); }
        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics; g.SmoothingMode = SmoothingMode.AntiAlias; g.Clear(Th.Surf);
            using (GraphicsPath p = Th.RR(new RectangleF(0.5f, 0.5f, Width - 1.5f, Height - 1.5f), 9)) using (SolidBrush b = new SolidBrush(Th.Inset)) g.FillPath(b, p);
            if (Hi > 0) using (GraphicsPath hp = Th.RR(new RectangleF(1f, 1f, Width - 3f, Height - 3f), 8)) { using (SolidBrush b = new SolidBrush(Th.Mix(Th.Inset, Hi == 1 ? Th.Amber : Th.Green, 0.12f))) g.FillPath(b, hp); using (Pen pen = new Pen(Hi == 1 ? Th.Amber : Th.Green, 1.5f)) g.DrawPath(pen, hp); }
            string[] lab = { Left, Right };
            for (int i = 0; i < 2; i++)
            {
                Rectangle r = CellRect(i); bool on = Selected == i, hot = hotCell == i && !on;
                using (GraphicsPath p = Th.RR(new RectangleF(r.X + 0.5f, r.Y + 0.5f, r.Width - 1f, r.Height - 1f), 7))
                {
                    using (SolidBrush b = new SolidBrush(!Enabled ? Th.Inset : (on ? Th.Amber : (hot ? Th.SurfHi : Th.Surf)))) g.FillPath(b, p);
                    using (Pen pen = new Pen(on && Enabled ? Th.Amber : Th.Line, 1f)) g.DrawPath(pen, p);
                }
                TextFit.Draw(g, this, lab[i], Th.F("Segoe UI Semibold", 8.5f, FontStyle.Regular), r, !Enabled ? Th.Faint : (on ? Th.OnAmber : Th.Muted), TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding | TextFormatFlags.NoPrefix);
            }
            Rectangle z = Zone; TextFormatFlags fl = TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding | TextFormatFlags.EndEllipsis | TextFormatFlags.NoPrefix;
            bool two = Status.Length > 0;
            TextFit.Draw(g, this, Title + (TitleClick != null ? " \u203A" : ""), Th.F("Segoe UI Semibold", 9f, FontStyle.Regular), new Rectangle(z.X, two ? 4 : 0, z.Width, two ? 20 : Height), Enabled ? Th.Text : Th.Faint, fl);
            if (two) TextFit.Draw(g, this, Status, Th.F("Segoe UI", 8f, FontStyle.Regular), new Rectangle(z.X, 23, z.Width, 16), StatusColor, fl);
        }
    }

    partial class MainForm
    {
        Label gfxSub; string gfxSubText = ""; Dictionary<string, AssetManifest> gfxMan; string gfxNote = ""; bool gfxLoading; GfxSel gfxSel = new GfxSel(); GfxSel gfxCur;
        GfxChoice chPic, chUi, chItems, chBag; TriRow rGfxBag, rGfxFonts; Dictionary<string, int> gfxHi = new Dictionary<string, int>(); Dictionary<string, string> gfxHiVal = new Dictionary<string, string>();   // quick setup step 2: slot -> 1 pending / 2 applied, and the value it picked
          TriRow rGfxUp; BeforeAfter gfxPrev; Label lGfxBar; Btn bGfxApply, bGfxRevert; Seg segScale; Dictionary<string, MiniRow> gfxRows = new Dictionary<string, MiniRow>();
        Dictionary<string, Image> prevCache = new Dictionary<string, Image>(); bool gfxBusy, gfxIniting; MiniRow rGfxScale; TriRow rGfxGlow; Btn bGfxFxOpen; Btn bGfxRender;
        int cntGfx;

        void DisposePrev() { if (gfxPrev != null) { gfxPrev.Before = new Image[0]; gfxPrev.After = new Image[0]; } foreach (Image im in prevCache.Values) if (im != null) im.Dispose(); prevCache.Clear(); }
        Image Prev(string id)
        {
            if (id == null || id.Length == 0) return null; Image im;
            if (prevCache.TryGetValue(id, out im)) return im;
            try { using (MemoryStream ms = new MemoryStream(Core.ResBytes("gfxprev_" + id))) using (Image src = Image.FromStream(ms)) im = new Bitmap(src); } catch (Exception) { im = null; }
            prevCache[id] = im; return im;
        }

        // quick setup, step 2: the sub-title says where the person is and what was picked; the picked rows are highlighted amber until Apply (then green "applied") or until they leave the tab
        static readonly string[][] QuickPick = { new string[] { "ui", "c" }, new string[] { "items", "redrawn" }, new string[] { "bag", "big" } };   // interface Original HD, items Redrawn, backpack Large
        public void GfxStep2(bool on) { GfxStep2(on, -1); }
        public void GfxStep2(bool on, int preset)   // preset: monitor class chosen in quick setup (0 HD, 1 2K, 2 4K); -1 = by the real monitor
        {
            if (gfxSub == null) return;
            if (on)
            {
                gfxHi.Clear(); gfxHiVal.Clear(); List<string> names = new List<string>(); string[] lab = { U.R("интерфейс", "interface"), U.R("предметы", "items"), U.R("окна", "windows") }; int k = 0;
                foreach (string[] q in QuickPick)
                {
                    GfxSlot sl = core.Gfx.Slot(q[0]); string qv = q[0] == "bag" ? (BigWindowsWanted(preset) ? "big" : "orig") : q[1]; GfxOpt o = sl != null ? sl.Find(qv) : null; if (o != null) { gfxSel.Slot[q[0]] = qv; gfxHi[q[0]] = (gfxCur != null && gfxCur.Slot.ContainsKey(q[0]) && gfxCur.Slot[q[0]] == qv) ? 2 : 1; gfxHiVal[q[0]] = qv; names.Add(lab[k] + " «" + o.Name + "»"); }
                    k++;
                }
                gfxSub.Text = U.R("Шаг 2 из 2 · Подсвечено: ", "Step 2 of 2 · Highlighted: ") + string.Join(", ", names.ToArray()) + U.R(". Нажмите «Применить».", ". Press Apply.");   // one line: the previews start right under it
                gfxSub.ForeColor = Th.Amber; gfxSub.Font = Th.F("Segoe UI Semibold", 8.5f, FontStyle.Regular); RefreshGfx(); return;
            }
            bool had = gfxHi.Count > 0; gfxHi.Clear(); gfxHiVal.Clear();
            gfxSub.Text = gfxSubText; gfxSub.ForeColor = Th.Muted; gfxSub.Font = Th.F("Segoe UI", 8.5f, FontStyle.Regular); if (had) RefreshGfx();
        }
        // large windows are on by default from 2K up (2560x1440 and more); HD / 1080p: off. preset: 0 HD, 1 2K, 2 4K, -1 = the monitor this window is on
        bool BigWindowsWanted(int preset) { return (preset >= 0 ? preset : Core.PresetForScreen(Core.ScreenPixels(Screen.FromControl(this)).Width)) >= 1; }
        // first time the Graphics page is shown (once per profile): on a 2K+ monitor "Large windows" is PRE-picked (not applied until Apply)
        public void GfxFirstDefaults()
        {
            if (!core.HasGame || App.Get("gfx_first") == "1") return; App.Set("gfx_first", "1");
            if (gfxHi.Count > 0 || !BigWindowsWanted(-1)) return; GfxSlot sl = core.Gfx.Slot("bag"); if (sl == null || sl.Find("big") == null) return;
            if (gfxCur != null && gfxCur.Slot.ContainsKey("bag") && gfxCur.Slot["bag"] == "big") return; gfxSel.Slot["bag"] = "big"; RefreshGfx();
        }
        // after Apply: what the quick setup picked and is now really in effect turns green "applied"; the rest loses its highlight
        void GfxHiAfterApply()
        {
            if (gfxHi.Count == 0) return; GfxSel cur = core.GfxCurrent(); List<string> keys = new List<string>(gfxHi.Keys);
            foreach (string k in keys) { if (cur.Slot.ContainsKey(k) && cur.Slot[k] == gfxHiVal[k]) gfxHi[k] = 2; else { gfxHi.Remove(k); gfxHiVal.Remove(k); } }
            if (gfxSub != null) { gfxSub.Text = gfxSubText; gfxSub.ForeColor = Th.Muted; gfxSub.Font = Th.F("Segoe UI", 8.5f, FontStyle.Regular); }
        }
        Panel BuildGfx()
        {
            Panel p = NewPage("gfx", true); RPanel c = Card(p); GfxDef def = core.Gfx;
            gfxSub = Head(c, U.R("Графика", "Graphics"), U.R("Картинка, интерфейс и исправления в одном месте. Выбор ничего не меняет, пока вы не нажмёте «Применить»", "Picture, interface and fixes in one place. Choosing changes nothing until you press Apply"), 0); gfxSubText = gfxSub.Text;
            DisposePrev(); gfxRows.Clear();
            // top: two previews (inventory, dialogue) under ONE Before | After slider; below: Interface | fonts, size, renderer | Game picture (rightmost)
            gfxPrev = new BeforeAfter(); gfxPrev.SetBounds(14, 62, c.Width - 28, (c.Width - 28 - 8) / 2 * 350 / 600 + BeforeAfter.BarH + BeforeAfter.InfoH); c.Controls.Add(gfxPrev);
            GfxSlot sPic = def.Slot("pic"), sUi = def.Slot("ui"), sIt = def.Slot("items"); int y0 = gfxPrev.Bottom + 6, colW = 214, itW = 220, midW = c.Width - 28 - colW - itW - 28, midX = 14 + colW + 14, itX = c.Width - 14 - itW;
            // columns: 1 Interface | 2 Upscaling (on/off), 3 Fonts, 4 Interface size, 5 Renderer, 6 Effects and FPS (all the same size) | 7 Items. The picture slot is a plain on/off switch now: its list (chPic) only holds the data and is not shown.
            chPic = new GfxChoice(); chPic.Title = sPic.Title; chBag = new GfxChoice(); chUi = new GfxChoice(); chUi.Title = sUi.Title; chItems = new GfxChoice(); chItems.Title = sIt != null ? sIt.Title : U.R("Предметы", "Items");
            chUi.SetBounds(14, y0, colW, GfxChoice.HeadH + 6 * GfxChoice.RowH + 4); chItems.SetBounds(itX, y0, itW, chUi.Height);
            chItems.AddHelp("gfx_items", this); chUi.AddHelp("gfx_ui", this);
            chPic.Picked += delegate(int i) { GfxPick("pic", i); }; chUi.Picked += delegate(int i) { GfxPick("ui", i); }; chItems.Picked += delegate(int i) { GfxPick("items", i); };
            chUi.Hover += delegate(int i) { GfxItemTip(chUi, "ui", i); }; chItems.Hover += delegate(int i) { GfxItemTip(chItems, "items", i); };
            c.Controls.Add(chUi); c.Controls.Add(chItems);
            const int RH = 44, RG = 6, STK = 58; int ry = y0 + 2;   // middle column: Upscaling, Fonts, Item glow, Large windows, Interface size (stacked, no state line); Renderer and Effects sit under the Items list (right column)
            // three rows in ONE look: [ Off ] Name [ On ]; the state in small words under the name; "?" at the right
            rGfxUp = GfxTri(U.R("Апскейлинг", "Upscaling"), "gfx_pic", c, midX, ry, midW, "pic", RH);
            rGfxUp.Changed += delegate { if (gfxIniting) return; List<GfxOpt> vis = GfxVisibleOpts(core.Gfx.Slot("pic")); if (vis.Count > 0) GfxPick("pic", rGfxUp.Selected == 1 ? vis.Count - 1 : 0); }; ry += RH + RG;
            rGfxFonts = GfxTri(U.R("Шрифты", "Fonts"), "gfx_fonts", c, midX, ry, midW, "fonts", RH);   // Off = the original fonts at once; On = opens the window with every font choice (the name opens it too)
            rGfxFonts.ReclickOn = true; Action openFonts = delegate { Dlg(delegate { return new FontForm(core); }); RefreshState(); RefreshGfx(); };   // the switch goes back to the real state when the window is closed without a choice
            rGfxFonts.TitleClick = openFonts;
            rGfxFonts.Changed += delegate { if (gfxIniting) return; if (rGfxFonts.Selected == 1) { openFonts(); return; }   // On = the window with the choices (they apply there)
                Guard(delegate { if (core.FontsAvail) for (int fc = 0; fc < 3; fc++) if (core.FontStep(fc) >= 0) core.SetFontStep(fc, 0); }); RefreshState(); RefreshGfx(); }; ry += RH + RG;
            rGfxGlow = GfxTri(U.R("Подсветка", "Item glow"), "gfx_glow", c, midX, ry, midW, "glow", RH);   // owner 07.11: right under Fonts, the same look (a default-on exe patch, applied with "Apply")
            rGfxGlow.Changed += delegate { if (gfxIniting) return; gfxSel.Fix["glow"] = rGfxGlow.Selected == 1; RefreshGfx(); }; ry += RH + RG;
            rGfxBag = GfxTri(U.R("Крупные окна", "Large windows"), "gfx_bag", c, midX, ry, midW, "bag", RH);   // On = the "big" value of the slot "bag", Off = "orig"
            rGfxBag.Changed += delegate { if (gfxIniting) return; List<GfxOpt> bv = GfxVisibleOpts(core.Gfx.Slot("bag")); if (bv.Count < 2) return; int want = rGfxBag.Selected == 1 ? 1 : 0; if (chBag.Items.Count > want && !chBag.Items[want].Enabled) { RefreshGfx(); return; } GfxPick("bag", want); }; ry += RH + RG;
            segScale = new Seg(); segScale.Under = Th.Inset; segScale.Items = new string[] { U.R("Авто", "Auto"), "100", "125", "150", "200" }; segScale.Size = new Size(midW - 20, 26);
            segScale.Changed += delegate { if (gfxIniting) return; int pct = UiScale.Steps[segScale.Selected]; int sv; Size g0; gfxSel.Scale = (core.ScaleSaved(out sv, out g0) && sv == pct) ? -1 : pct; RefreshGfx(); };
            rGfxScale = new MiniRow(); rGfxScale.Stacked = true; rGfxScale.Title = U.R("Размер интерфейса", "Interface size"); rGfxScale.Ctl = segScale; rGfxScale.SetBounds(midX, ry, midW, STK); rGfxScale.AddHelp("scale", this); gfxRows["scale"] = rGfxScale; ry += STK + RG;
            rGfxScale.Tip = delegate { return GfxTip("scale"); }; rGfxScale.TipHover += delegate(MiniRow s0, bool on) { if (!on) { tip.Hide(); return; } string[] t = s0.Tip(); if (t != null && t[1].Length > 0) tip.ShowFor(this, s0, s0.TextRect, t[0], t[1]); }; c.Controls.Add(rGfxScale);
            // renderer and effects: small rows like the others (name at the left, a small button at the right), under the Items list; no "?" (the windows explain themselves)
            // renderer and effects: ONE row of two buttons under the Interface list (the button is the name; no "?": the windows explain themselves). The item glow switch sits in the middle column under Fonts.
            { int bw = (colW - 8) / 2; Func<string, EventHandler, Btn> two = delegate(string txt, EventHandler h) { Btn b = new Btn(); b.Under = Th.Surf; b.Pt = 8.5f; b.Text = txt; b.Size = new Size(bw, RH); b.Click += h; return b; };
              bGfxRender = two(U.R("Рендер", "Renderer"), delegate { if (core.Cnc) Modeless(delegate { return new CncForm(core); }); else Modeless(delegate { return new DgvQualityForm(core); }); });
              bGfxFxOpen = two(U.R("Эффекты и FPS", "Effects and FPS"), delegate { Modeless(delegate { return new FxForm(core); }); });
              bGfxRender.Location = new Point(14, chUi.Bottom + 10); bGfxFxOpen.Location = new Point(14 + bw + 8, chUi.Bottom + 10); c.Controls.Add(bGfxRender); c.Controls.Add(bGfxFxOpen); }
            RPanel bar = new RPanel(); bar.SetBounds(0, MainH - 56, MainW, 56); p.Controls.Add(bar);
            lGfxBar = new Label(); lGfxBar.AutoSize = false; lGfxBar.SetBounds(14, 6, bar.Width - 14 - 14 - 140 - 10 - 150 - 10 - 28, 44); lGfxBar.Font = Th.F("Segoe UI", 9f, FontStyle.Regular); lGfxBar.ForeColor = Th.Muted; lGfxBar.BackColor = Th.Surf; lGfxBar.TextAlign = ContentAlignment.MiddleLeft; lGfxBar.UseMnemonic = false;
            bGfxApply = new Btn(); bGfxApply.Accent = true; bGfxApply.Pt = 10f; bGfxApply.Under = Th.Surf; bGfxApply.Text = U.R("Применить", "Apply"); bGfxApply.SetBounds(bar.Width - 14 - 140, 9, 140, 38); bGfxApply.Click += delegate { GfxApplyClick(false); };
            bGfxRevert = new Btn(); bGfxRevert.Under = Th.Surf; bGfxRevert.Pt = 9f; bGfxRevert.Text = U.R("Вернуть оригинал", "Restore original"); bGfxRevert.SetBounds(bGfxApply.Left - 10 - 150, 9, 150, 38); bGfxRevert.Click += delegate { gfxHi.Clear(); gfxHiVal.Clear(); GfxStep2(false); GfxApplyClick(true); };
            Btn hb = new Btn(); hb.Under = Th.Surf; hb.Pt = 8f; hb.Text = "?"; hb.SetBounds(bGfxRevert.Left - 8 - 22, 17, 22, 22); hb.Click += Help.Click(this, "gfx_apply");
            lGfxBar.Width = hb.Left - 8 - 14; bar.Controls.AddRange(new Control[] { lGfxBar, hb, bGfxRevert, bGfxApply });
            cntGfx = def.Slots.Count;
            gfxCur = null; return p;
        }
        TriRow GfxTri(string title, string helpKey, RPanel c, int x, int y, int w, string tipKey, int h)
        {
            TriRow r = new TriRow(); r.Title = title; r.Left = U.R("Выкл", "Off"); r.Right = U.R("Вкл", "On"); r.SetBounds(x, y, w, h); r.AddHelp(helpKey, this); gfxRows[tipKey] = r;
            r.Tip = delegate { return GfxTip(tipKey); };
            r.TipHover += delegate(MiniRow s0, bool on) { if (!on) { tip.Hide(); return; } string[] t = s0.Tip(); if (t != null && t[1].Length > 0) tip.ShowFor(this, s0, s0.TextRect, t[0], t[1]); };
            c.Controls.Add(r); return r;
        }
        MiniRow GfxRow(string title, Control ctl, string helpKey, RPanel c, int x, int y, int w, string tipKey) { return GfxRow(title, ctl, helpKey, c, x, y, w, tipKey, RowCtl.H); }
        MiniRow GfxRow(string title, Control ctl, string helpKey, RPanel c, int x, int y, int w, string tipKey, int h)
        {
            MiniRow r = new MiniRow(); r.Title = title; r.Ctl = ctl; r.SetBounds(x, y, w, h); r.AddHelp(helpKey, this); gfxRows[tipKey] = r;
            r.Tip = delegate { return GfxTip(tipKey); };
            r.TipHover += delegate(MiniRow s, bool on) { if (!on) { tip.Hide(); return; } string[] t = s.Tip(); if (t != null && t[1].Length > 0) tip.ShowFor(this, s, s.TextRect, t[0], t[1]); };
            c.Controls.Add(r); return r;
        }
        string[] GfxTip(string key)
        {
            if (key == "scale") { Size mon = Core.ScreenPixels(Screen.FromControl(this)); int pct = gfxSel.Scale >= 0 ? gfxSel.Scale : (segScale != null ? UiScale.Steps[segScale.Selected] : 0); ScalePlan pl = core.PlanScale(pct, mon); return new string[] { U.R("Размер интерфейса", "Interface size"), UiScale.Summary(pl, L.Ru) + (pl.Notes.Count > 0 ? "\n" + UiScale.Warnings(pl, L.Ru) : "") + (core.Cnc ? "" : "\n" + U.R("Нужен gr-draw: включите его на странице «Патчи и фиксы».", "Needs gr-draw: turn it on on the Patches & fixes page.")) }; }
            if (key.StartsWith("fix:")) { GfxFix f = core.Gfx.Fix(key.Substring(4)); string st = core.GfxFixState(f); return new string[] { f.Name, f.Desc + (st == "n/a" ? "\n" + U.R("Недоступно для вашей версии игры или файлов.", "Not available for your game version or files.") : "") }; }
            GfxSlot s = core.Gfx.Slot(key); return s != null ? new string[] { s.Title, s.Desc } : null;
        }

        // ---- data -> controls
        void LoadGfxCatalog()
        {
            if (gfxLoading || !core.HasGame) return; gfxLoading = true; AssetSets a = core.Assets;
            Thread t = new Thread(delegate()
            {
                Dictionary<string, AssetManifest> man = new Dictionary<string, AssetManifest>(); string note = "";
                try { foreach (AssetManifest m in a.LoadCatalog(out note)) man[m.Id] = m; } catch (Exception ex) { note = ex.Message; }
                try { BeginInvoke((MethodInvoker)delegate { gfxMan = man; gfxNote = note; gfxLoading = false; RefreshGfx(); }); } catch (InvalidOperationException) { }   // the window was closed meanwhile
            });
            t.IsBackground = true; t.Start();
        }
        void GfxPick(string slot, int i)
        {
            GfxSlot sl = core.Gfx.Slot(slot); GfxOpt o = GfxVisibleOpts(sl)[i]; gfxSel.Slot[slot] = o.Value;
            if (o.SetId.Length > 0 && gfxCur != null && gfxCur.Slot.ContainsKey(slot) && gfxCur.Slot[slot] == o.Value) { AssetManifest m; if (gfxMan != null && gfxMan.TryGetValue(m0Id(o), out m)) { AssetQuick q = GfxQuick(m.Id); if (q != null && q.Rec.Version != m.Version && !gfxSel.Reapply.Contains(m.Id)) gfxSel.Reapply.Add(m.Id); } }
            else gfxSel.Reapply.Remove(m0Id(o));
            RefreshGfx();
        }
        string m0Id(GfxOpt o) { return core.GfxSetId(o, gfxSel, gfxCur); }   // the set of an option (per-skin sets: for the skin chosen now)
        List<AssetQuick> gfxQuick = new List<AssetQuick>();
        AssetQuick GfxQuick(string id) { foreach (AssetQuick q in gfxQuick) if (q.Rec.Id == id) return q; return null; }
        // options of a slot that are offered now (an optional set shows only when the server has it)
        List<GfxOpt> GfxVisibleOpts(GfxSlot sl)
        {
            List<GfxOpt> l = new List<GfxOpt>(); foreach (GfxOpt o in sl.Opts) { if (o.Hidden && !(gfxCur != null && gfxCur.Slot.ContainsKey(sl.Id) && gfxCur.Slot[sl.Id] == o.Value)) continue; if (o.Optional && (gfxMan == null || !gfxMan.ContainsKey(o.SetId)) && !(gfxCur != null && gfxCur.Slot.ContainsKey(sl.Id) && gfxCur.Slot[sl.Id] == o.Value)) continue; l.Add(o); }
            return l;
        }
        void GfxItemTip(GfxChoice ch, string slot, int i)
        {
            if (i < 0) { tip.Hide(); return; } GfxItem it = ch.Items[i]; GfxOpt o = GfxVisibleOpts(core.Gfx.Slot(slot))[i];
            string body = it.Reason.Length > 0 ? it.Reason : (o.SetId.Length > 0 && gfxMan != null && gfxMan.ContainsKey(m0Id(o)) ? gfxMan[m0Id(o)].Desc : "");
            if (body.Length > 0) tip.ShowFor(this, ch, new Rectangle(0, GfxChoice.HeadH + i * GfxChoice.RowH, ch.Width, GfxChoice.RowH), o.Name, body);
        }

        void RefreshGfx()
        {
            if (gfxRows.Count == 0 || chPic == null) return; GfxDef def = core.Gfx; bool has = core.HasGame; gfxIniting = true;
            try
            {
                foreach (string hk in new List<string>(gfxHi.Keys)) { string cv = gfxCur != null && gfxCur.Slot.ContainsKey(hk) ? gfxCur.Slot[hk] : "", sv2 = gfxSel.Slot.ContainsKey(hk) ? gfxSel.Slot[hk] : cv; if (gfxHi[hk] == 1 ? sv2 != gfxHiVal[hk] : cv != gfxHiVal[hk]) { gfxHi.Remove(hk); gfxHiVal.Remove(hk); } }   // the person chose something else: no longer "picked for you"
                gfxCur = has ? core.GfxCurrent() : new GfxSel(); try { gfxQuick = has ? core.Assets.Quick() : new List<AssetQuick>(); } catch { gfxQuick = new List<AssetQuick>(); }
                foreach (KeyValuePair<string, string> kv in gfxCur.Slot) if (!gfxSel.Slot.ContainsKey(kv.Key)) gfxSel.Slot[kv.Key] = kv.Value; foreach (KeyValuePair<string, bool> kv in gfxCur.Fix) if (!gfxSel.Fix.ContainsKey(kv.Key)) gfxSel.Fix[kv.Key] = kv.Value;
                // choice lists
                foreach (string sid in new string[] { "pic", "ui", "items", "bag" })
                {
                    GfxSlot sl = def.Slot(sid); if (sl == null) continue; GfxChoice ch = sid == "pic" ? chPic : (sid == "ui" ? chUi : (sid == "bag" ? chBag : chItems)); List<GfxOpt> vis = GfxVisibleOpts(sl); ch.Items.Clear(); int selIdx = 0;
                    for (int i = 0; i < vis.Count; i++)
                    {
                        GfxOpt o = vis[i]; GfxItem it = new GfxItem(); it.Text = o.Name; AssetManifest m = null; bool known = o.SetId.Length == 0 || (gfxMan != null && gfxMan.TryGetValue(m0Id(o), out m));
                        bool isCur = gfxCur.Slot.ContainsKey(sid) && gfxCur.Slot[sid] == o.Value;
                        if (o.SetId.Length == 0) { it.Status = isCur ? U.R("Установлено", "Installed") : ""; it.StatusColor = Th.Green; }
                        else if (!known)   // the catalog is built in (gfx.txt: names, previews, approximate size); the server only supplies the files. Choosing and previewing work without it.
                        {
                            string mb = o.ApproxMb > 0 ? " · ~" + o.ApproxMb + U.R(" МБ", " MB") : "";
                            it.Status = gfxLoading || gfxMan == null ? U.R("проверка…", "checking…") : (gfxNote.Length > 0 ? (mb.Length > 0 ? mb.Substring(3) : U.R("нет связи", "offline")) : U.R("ещё нет", "not yet")); it.StatusColor = Th.Faint;
                            it.Reason = gfxLoading || gfxMan == null ? U.R("Проверяю, что есть на сервере наборов. Превью и выбор уже доступны.", "Checking what the sets server has. Preview and choice already work.") : (gfxNote.Length > 0 ? U.R("Нет связи с сервером наборов: превью работает, а скачать набор сейчас нельзя. «Применить» сообщит об этом.", "The sets server is not reachable: the preview works but the set cannot be downloaded now. Apply will tell you so.") : U.R("Набор ещё не выложен на сервер: превью работает, скачать пока нельзя.", "The set is not on the server yet: the preview works, the download is not possible yet."));
                        }
                        else
                        {
                            string w = GfxDefWord(o, m); if (w == "installed") { it.Status = U.R("Установлено", "Installed"); it.StatusColor = Th.Green; } else if (w == "outdated") { it.Status = U.R("Устарело", "Outdated"); it.StatusColor = Th.Amber; }
                            else if (w == "mixed") { it.Status = U.R("Смешанное", "Mixed"); it.StatusColor = Th.Amber; }
                            else if (w == "cached") { it.Status = U.R("Скачано", "Downloaded"); it.StatusColor = Th.Muted; }
                            else { it.Status = U.R("Не скачано (" + AssetSets.Fmt(m.Download) + ")", "To download · " + AssetSets.Fmt(m.Download)); it.StatusColor = Th.Faint; }
                        }
                        // does this option fit the rest of the choice?
                        if (it.Enabled && o.SetId.Length > 0) { GfxSel t = gfxSel.Copy(); t.Slot[sid] = o.Value; List<string> pr = core.GfxSetProblems(t, gfxMan, true); if (pr.Count > 0) { it.Enabled = false; it.Reason = string.Join("\n", pr.ToArray()); } }
                        if (!has) { it.Enabled = false; }
                        ch.Items.Add(it); if (gfxSel.Slot.ContainsKey(sid) && gfxSel.Slot[sid] == o.Value) selIdx = i;
                    }
                    ch.Selected = selIdx; ch.Enabled = has; if (ch.Items.Count > 0 && !ch.Items[selIdx].Enabled && gfxSel.Slot.ContainsKey(sid)) { }
                    ch.Height = ch.Wanted;
                }
                // upscaling switch: Off = original, On = the best picture set offered
                { List<GfxOpt> pv = GfxVisibleOpts(def.Slot("pic")); bool on = chPic.Items.Count > 1 && chPic.Selected > 0; rGfxUp.Selected = on ? 1 : 0; rGfxUp.Enabled = has && pv.Count > 1;
                  GfxItem top = chPic.Items.Count > 1 ? chPic.Items[chPic.Items.Count - 1] : null;
                  rGfxUp.Status = !has ? "" : (on ? chPic.Items[chPic.Selected].Text : U.R("оригинал", "original"));
                  rGfxUp.StatusColor = on ? (chPic.Items[chPic.Selected].StatusColor == Th.Green ? Th.Green : Th.Amber) : Th.Faint; }
                // large windows switch: the state in one short phrase (<= 20 characters)
                { bool bigSel = chBag.Items.Count > 1 && chBag.Selected == 1; bool bigNow = gfxCur.Slot.ContainsKey("bag") && gfxCur.Slot["bag"] == "big"; rGfxBag.Selected = bigSel ? 1 : 0; rGfxBag.Enabled = has && chBag.Items.Count > 1;
                  bool blocked = chBag.Items.Count > 1 && !chBag.Items[1].Enabled && !bigSel; string onT = U.R("рюкзак и торговля", "backpack and trade"), offT = U.R("обычные", "normal");
                  rGfxBag.Status = !has ? "" : (bigSel != bigNow ? (bigSel ? onT : offT) : (bigSel ? onT : (blocked ? U.R("недоступно", "unavailable") : offT)));
                  rGfxBag.StatusColor = bigSel != bigNow ? Th.Amber : (bigSel ? Th.Green : Th.Faint); }
                // quick setup highlight
                { string[] hs = { "ui", "items", "bag" }; GfxChoice[] hc = { chUi, chItems, null }; MiniRow[] hr = { null, null, rGfxBag };
                  for (int hi = 0; hi < 3; hi++)
                  {
                      int st; if (!gfxHi.TryGetValue(hs[hi], out st)) st = 0;
                      if (hc[hi] != null) { hc[hi].Hi = st; hc[hi].HiText = st == 1 ? U.R("★ для вас", "★ for you") : U.R("применено", "applied"); if (st > 0 && hc[hi].Items.Count > hc[hi].Selected && hc[hi].Selected >= 0) { GfxItem sit = hc[hi].Items[hc[hi].Selected]; sit.Status = st == 1 ? U.R("★ выбрано", "★ picked") : U.R("✓ применено", "✓ applied"); sit.StatusColor = st == 1 ? Th.Amber : Th.Green; } hc[hi].Invalidate(); }
                      if (hr[hi] != null) { hr[hi].Hi = st; if (st == 1) { hr[hi].Status = U.R("★ выбрано", "★ picked"); hr[hi].StatusColor = Th.Amber; } else if (st == 2) { hr[hi].Status = U.R("✓ применено", "✓ applied"); hr[hi].StatusColor = Th.Green; } }
                  } }
                // preview: before = original, after = what the choice looks like (skin over picture)
                string prev = null; foreach (string sid in new string[] { "pic", "ui" }) { GfxOpt o = def.Slot(sid).Find(gfxSel.Slot.ContainsKey(sid) ? gfxSel.Slot[sid] : "orig"); if (o != null && o.Value != "orig") prev = o.Prev; }
                string[] pa = (prev ?? "inv_orig+dlg_orig").Split('+'), pb = "inv_orig+dlg_orig".Split('+');   // one id per window: inventory, dialogue
                bool fbig = has && ((core.FontsAvail && (core.FontIsCustom(0) || core.FontIsCustom(1) || core.FontIsCustom(2))) || Math.Max(Math.Max(core.FontState(0), core.FontState(1)), core.FontState(2)) == 1);   // the dialogue text follows the chosen fonts: original sizes unless larger ones are on
                gfxPrev.Before = new Image[] { Prev(pb[0]), Prev(pb[1] + "_f0") }; gfxPrev.After = new Image[] { Prev(pa[0]), pa.Length > 1 ? Prev(pa[1] + (fbig ? "" : "_f0")) : null };
                gfxPrev.PaneTitles = new string[] { U.R("Инвентарь", "Inventory"), U.R("Разговор с NPC", "NPC dialogue") };
                gfxPrev.CapBefore = U.R("До · оригинал", "Before · original"); gfxPrev.CapAfter = prev == null ? U.R("После · без изменений", "After · unchanged") : U.R("После · ваш выбор", "After · your choice"); gfxPrev.Invalidate();
                // other rows
                int fs = has ? Math.Max(Math.Max(core.FontState(0), core.FontState(1)), core.FontState(2)) : -1; bool fcust = has && core.FontsAvail && (core.FontIsCustom(0) || core.FontIsCustom(1) || core.FontIsCustom(2));
                rGfxFonts.Enabled = has && core.FontsAvail; rGfxFonts.Selected = fcust ? -1 : (fs == 1 ? 1 : 0); rGfxFonts.Status = !rGfxFonts.Enabled ? U.R("недоступно", "unavailable") : (fcust ? U.R("свои шрифты", "your own fonts") : (fs == 1 ? U.R("крупнее оригинала", "larger than original") : U.R("оригинал", "original"))); rGfxFonts.StatusColor = fcust ? Th.Amber : (fs == 1 ? Th.Green : Th.Faint);
                int sv = 0; Size sg = Size.Empty; bool saved = false; if (has) saved = core.ScaleSaved(out sv, out sg);
                int shown = gfxSel.Scale >= 0 ? gfxSel.Scale : sv; segScale.Selected = Math.Max(0, Array.IndexOf(UiScale.Steps, shown)); { ScalePlan zp = (has && core.Cnc && (gfxSel.Scale >= 0 || saved)) ? core.PlanScale(shown, Core.ScreenPixels(Screen.FromControl(this))) : null; gfxPrev.Zoom = zp != null ? zp.EffPct / 100f : 1f; gfxPrev.Invalidate(); } rGfxScale.Enabled = segScale.Enabled = has && core.Cnc;
                rGfxScale.Status = "";   // no state line (owner 07.11): the row is shorter; the details are in the tip and in "?"
                rGfxScale.StatusColor = gfxSel.Scale >= 0 ? Th.Amber : (core.Cnc && saved ? Th.Green : Th.Faint);
                bGfxFxOpen.Enabled = has; bGfxRender.Enabled = has && (core.Dgv || core.Cnc);
                // item glow: a default-on exe patch (fix "glow"); Off | On, amber while the choice is not applied yet
                { GfxFix gf = def.Fix("glow"); string gst = gf == null || !has ? "n/a" : core.GfxFixState(gf); bool gnow = gst == "on"; bool gsel = gfxSel.Fix.ContainsKey("glow") ? gfxSel.Fix["glow"] : gnow;
                  rGfxGlow.Enabled = has && gf != null && gst != "n/a"; rGfxGlow.Selected = gsel ? 1 : 0;
                  rGfxGlow.Status = !has || gf == null ? "" : (gst == "n/a" ? U.R("недоступно", "unavailable") : (gsel != gnow ? (gsel ? U.R("ореол и цвет", "halo, colour") : U.R("оригинал", "original")) : (gsel ? U.R("ореол и цвет", "halo, colour") : U.R("оригинал", "original"))));
                  rGfxGlow.StatusColor = gsel != gnow ? Th.Amber : (gsel ? Th.Green : Th.Faint); }
                foreach (MiniRow r in gfxRows.Values) r.Invalidate();
                // bottom bar
                GfxPlan pl = has ? core.GfxMakePlan(gfxSel, gfxMan) : new GfxPlan(); string sum;
                if (!has) sum = U.R("Игра не найдена.", "Game not found.");
                else if (pl.Problems.Count > 0) sum = pl.Problems[0];
                else if (pl.UserEmpty) sum = U.R("Изменений нет. Выберите картинку или скин, затем нажмите «Применить».", "No changes. Choose a picture or a skin, then press Apply.");
                else sum = U.R("Изменения: ", "Changes: ") + pl.Summary(L.Ru) + (pl.Download > 0 ? " · " + U.R("загрузка ", "download ") + AssetSets.Fmt(pl.Download) : "");
                lGfxBar.Text = sum; lGfxBar.ForeColor = pl.Problems.Count > 0 ? Th.Red : (pl.UserEmpty ? Th.Muted : Th.Text);
                bool wants = false; foreach (KeyValuePair<string, string> kv in gfxSel.Slot) if (gfxCur.Slot.ContainsKey(kv.Key) && gfxCur.Slot[kv.Key] != kv.Value) wants = true;
                bGfxApply.Enabled = has && !gfxBusy && ((!pl.UserEmpty && pl.Problems.Count == 0) || (wants && pl.Problems.Count > 0));   // with a missing set Apply stays clickable and says honestly that it is not downloaded
                bool anyOn = false; foreach (KeyValuePair<string, string> kv in gfxCur.Slot) if (kv.Value != "orig") anyOn = true; bGfxRevert.Enabled = has && !gfxBusy && anyOn;   // the default fixes do not count: they are not the player's business
            }
            finally { gfxIniting = false; }
        }
        string GfxDefWord(GfxOpt o, AssetManifest m)
        {
            AssetQuick q = GfxQuick(m.Id); if (q != null) return !q.Intact ? "mixed" : (q.Rec.Version != m.Version ? "outdated" : "installed");
            return core.Assets.IsCached(m) ? "cached" : "notdl";
        }

        // quick setup: the picture/skin the player chose there. Isolated: a failure here (no network, game running, declined) never undoes the other settings.
        void QuickLook(string img, string skin)
        {
            string err; GfxSel sel = core.GfxQuickSel(img, skin, out err); if (err != null) return;
            if (Core.GameRunning()) { notes.Add(U.R("Внешний вид не применён: игра запущена. Повторите на вкладке «Графика».", "The look was not applied: the game is running. Repeat it on the Graphics tab.")); return; }
            Dictionary<string, AssetManifest> man = new Dictionary<string, AssetManifest>(); AssetSets a = core.Assets;
            string e1 = WorkForm.Run(this, U.R("Внешний вид", "Look"), U.R("Получаю список наборов…", "Getting the list of sets…"), false, delegate(WorkForm w) { string note; foreach (AssetManifest m in a.LoadCatalog(out note)) man[m.Id] = m; });
            GfxPlan pl = core.GfxMakePlan(sel, man);
            if (man.Count == 0 || pl.Problems.Count > 0) { notes.Add(U.R("Внешний вид не применён: ", "The look was not applied: ") + (pl.Problems.Count > 0 ? pl.Problems[0] : U.R("нет связи с сервером наборов.", "the sets server is not reachable.")) + U.R(" Повторите на вкладке «Графика».", " Repeat it on the Graphics tab.")); return; }
            if (pl.Empty) return;
            string q = U.R("Применить внешний вид?\r\n\r\n", "Apply the look?\r\n\r\n") + pl.Summary(L.Ru) + "\r\n\r\n" + (pl.Download > 0 ? U.R("Нужно скачать: " + AssetSets.Fmt(pl.Download) + " (с нашего сервера; можно отменить и продолжить позже).", "To download: " + AssetSets.Fmt(pl.Download) + " (from our server; you can cancel and continue later).") : U.R("Всё уже скачано.", "Everything is already downloaded."));
            if (MessageBox.Show(this, q, U.R("Внешний вид", "Look"), MessageBoxButtons.OKCancel, MessageBoxIcon.Question) != DialogResult.OK) return;
            Core c = core; string er = WorkForm.Run(this, U.R("Графика", "Graphics"), U.R("Подготовка…", "Preparing…"), true, delegate(WorkForm w) { c.GfxApply(pl, delegate(string t, long d, long tot) { w.Report(t, d, tot); }, delegate { return w.Cancelled; }); });
            gfxMan = man; gfxSel = new GfxSel();
            if (er != null && er.Length > 0) notes.Add(U.R("Внешний вид не применён: ", "The look was not applied: ") + er);
            else if (er != null) notes.Add(U.R("Установка внешнего вида отменена; можно продолжить на вкладке «Графика».", "The look installation was cancelled; you can continue on the Graphics tab."));
        }

        // Installed sets with a newer version on the server, for any game (its gfx.txt + the sets server). After start-up / game switch: ONE question, "No" is remembered
        // for exactly these versions (settings.ini setsupd_later). On "Play" (owner 07.11.2026): asked EVERY time while an update exists, "No" just starts the game.
        Dictionary<string, AssetManifest> setsMan;   // the server's manifests from the last start-up check (null: offline / not checked yet -> "Play" does not wait for the network)
        void OfferSetUpdates()
        {
            if (!core.HasGame || Core.GameRunning()) return; AssetSets a = core.Assets;
            Thread t = new Thread(delegate()
            {
                Dictionary<string, AssetManifest> man = new Dictionary<string, AssetManifest>(); List<AssetQuick> qs;
                try { string note; foreach (AssetManifest m in a.LoadCatalog(out note)) man[m.Id] = m; qs = a.Quick(); } catch (Exception) { return; }   // offline / no sets: nothing to offer
                try { BeginInvoke((MethodInvoker)delegate { setsMan = man; AskSetUpdates(man, qs, false); }); } catch (InvalidOperationException) { }   // the window was closed meanwhile
            });
            t.IsBackground = true; t.Start();
        }
        // false = do not start the game (the update was cancelled half way)
        bool AskSetUpdates(Dictionary<string, AssetManifest> man, List<AssetQuick> qs, bool atPlay)
        {
            List<string> ids = new List<string>(); string lines = "", key = "";
            foreach (AssetQuick q in qs) { AssetManifest m; if (!q.Intact || !man.TryGetValue(q.Rec.Id, out m) || m.Version == q.Rec.Version) continue; ids.Add(m.Id); lines += "• " + m.Name + "  " + q.Rec.Version + " → " + m.Version + "\r\n"; key += m.Id + ":" + m.Version + "+"; }
            if (ids.Count == 0 || (!atPlay && App.Get("setsupd_later") == key) || gfxBusy || busy || Core.GameRunning()) return true;
            GfxSel sel = new GfxSel(); sel.Reapply.AddRange(ids); sel.Monitor = Core.ScreenPixels(Screen.FromControl(this));
            GfxPlan pl = core.GfxMakePlan(sel, man); if (pl.Problems.Count > 0 || pl.Empty) return true;
            string q2 = U.R("Вышли новые версии установленных наборов:\r\n\r\n", "New versions of the installed sets are out:\r\n\r\n") + lines + "\r\n"
                + (pl.Download > 0 ? U.R("Нужно скачать: " + AssetSets.Fmt(pl.Download) + ".\r\n", "To download: " + AssetSets.Fmt(pl.Download) + ".\r\n") : "")
                + (atPlay ? U.R("Обновить перед игрой? «Нет» — играть с прежними версиями.", "Update before playing? \"No\" plays with the current versions.")
                          : U.R("Обновить сейчас? Остальные настройки не меняются. При сбое всё вернётся как было.", "Update now? Nothing else changes. On a failure everything goes back as it was."));
            if (MessageBox.Show(this, q2, U.R("Обновление наборов", "Set updates"), MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes) { if (!atPlay) App.Set("setsupd_later", key); return true; }
            gfxBusy = true; Core c = core; string err;
            try { err = WorkForm.Run(this, U.R("Обновление наборов", "Set updates"), U.R("Подготовка…", "Preparing…"), true, delegate(WorkForm w) { c.GfxApply(pl, delegate(string t, long d, long tot) { w.Report(t, d, tot); }, delegate { return w.Cancelled; }); }); }
            finally { gfxBusy = false; }
            if (err == null) Log(L.T("applied") + "set updates: " + pl.LogText());
            else if (err.Length > 0) { Log("set updates: " + err); MessageBox.Show(this, err, L.T("errTitle"), MessageBoxButtons.OK, MessageBoxIcon.Warning); }
            gfxMan = man; RefreshState(); RefreshGfx();
            return err == null || err.Length > 0;   // cancelled by the person: no game start
        }

        void GfxApplyClick(bool revert)
        {
            if (gfxBusy || !core.HasGame) return; tip.Hide();
            if (Core.GameRunning()) { MessageBox.Show(this, L.T("running"), L.T("warnTitle")); return; }
            GfxSel sel = revert ? core.GfxOriginalSel() : gfxSel; sel.Monitor = Core.ScreenPixels(Screen.FromControl(this));
            GfxPlan pl = core.GfxMakePlan(sel, gfxMan);
            if (pl.Problems.Count > 0) { MessageBox.Show(this, string.Join("\r\n", pl.Problems.ToArray()), L.T("warnTitle"), MessageBoxButtons.OK, MessageBoxIcon.Warning); return; }
            if (pl.UserEmpty) { MessageBox.Show(this, U.R("Ничего менять не нужно.", "Nothing to change."), App.Name, MessageBoxButtons.OK, MessageBoxIcon.Information); return; }
            string q = (revert ? U.R("Вернуть оригинал?\r\n\r\n", "Restore the original?\r\n\r\n") : U.R("Применить изменения?\r\n\r\n", "Apply the changes?\r\n\r\n")) + pl.Summary(L.Ru) + "\r\n\r\n"
                + (pl.Download > 0 ? U.R("Нужно скачать: " + AssetSets.Fmt(pl.Download) + " (с нашего сервера; можно отменить и продолжить позже).\r\n", "To download: " + AssetSets.Fmt(pl.Download) + " (from our server; you can cancel and continue later).\r\n") : "")
                + (pl.Installed > 0 ? U.R("В папке игры файлы займут до " + AssetSets.Fmt(pl.Installed) + "; копии оригиналов лягут в папку программы.\r\n", "Files in the game folder: up to " + AssetSets.Fmt(pl.Installed) + "; copies of the originals go to the program's folder.\r\n") : "")
                + U.R("Игра должна быть закрыта. При сбое всё вернётся как было.", "The game must be closed. On a failure everything goes back as it was.");
            if (MessageBox.Show(this, q, revert ? U.R("Вернуть оригинал", "Restore original") : U.R("Применить", "Apply"), MessageBoxButtons.OKCancel, MessageBoxIcon.Question) != DialogResult.OK) return;
            gfxBusy = true; Core c = core; string err;
            try { err = WorkForm.Run(this, U.R("Графика", "Graphics"), U.R("Подготовка…", "Preparing…"), true, delegate(WorkForm w) { c.GfxApply(pl, delegate(string t, long d, long tot) { w.Report(t, d, tot); }, delegate { return w.Cancelled; }); }); }
            finally { gfxBusy = false; }
            if (err == null) { Log(L.T("applied") + "graphics: " + pl.LogText()); if (!revert) core.ApplyDefaultFixes(false, false); }
            else if (err.Length == 0) MessageBox.Show(this, U.R("Отменено. Уже сделанные шаги остались, скачанное сохранено — можно продолжить позже.", "Cancelled. Steps already done stay; what was downloaded is kept - you can continue later."), App.Name, MessageBoxButtons.OK, MessageBoxIcon.Information);
            else { Log("graphics: " + err); MessageBox.Show(this, err, L.T("errTitle"), MessageBoxButtons.OK, MessageBoxIcon.Warning); }
            gfxSel = new GfxSel(); RefreshState(); if (!revert && err == null) GfxHiAfterApply(); else if (err != null) { gfxHi.Clear(); gfxHiVal.Clear(); if (gfxSub != null) { gfxSub.Text = gfxSubText; gfxSub.ForeColor = Th.Muted; gfxSub.Font = Th.F("Segoe UI", 8.5f, FontStyle.Regular); } } RefreshGfx();
        }
    }
}
