// Quick setup as a STEP-BY-STEP wizard in one window (owner 07.11.2026): monitor -> interface -> upscaling -> items -> large windows -> fonts -> FPS mod + item glow -> effect shaders -> Apply (9 steps, order by the owner 07.11 night; the old frame-mode interpolation stays FROZEN, see Fps.cs; the FPS mod is the tick-80 patch, src/Tick80.cs).
// Every step shows what changes (pictures of each variant, Before | After, or an honest scheme); defaults are picked beforehand, "Next" all the way is a complete setup.
// The wizard only COLLECTS the choice (WizResult); the work is done by MainForm.WizardApply in one progress window. Design rules: docs/design.md ("Быстрая настройка - мастер").
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
using System.Text;
using System.Windows.Forms;

namespace DDFixTool
{
    class WizResult
    {
        public int Preset; public bool UseCnc = true; public ScalePlan Plan; public int ScalePct;
        public string Ui = "c", Items = "redrawn", Pic = "orig"; public bool Bag, Fonts, Glow = true, Fps80, Shaders;   // Shaders: experimental, off by default (owner 07.11.2026)
        public bool Done; public string Summary = "";
    }

    // a card with a title and a short text; selected = amber frame. DESIGN BAN (owner 07.11.2026, docs/design.md): badges, check marks and "recommended" labels live in RESERVED places
    // of a fixed grid (Layout) and NEVER move or narrow the text of the card; all cards of a row share the same y of the title and of the text. Slots() = the grid the painting uses (self-test measures it).
    class WizCard : Control
    {
        public Image Img; public string Title = "", Sub = "", Badge = ""; public bool Sel, Compact; public event EventHandler Picked; bool hover; System.Windows.Forms.Timer hoverT;
        public const int CheckW = 30, BadgeH = 20, BadgeStrip = 36, SubLines = 3;
        public static Font SubFont { get { return Th.F("Segoe UI", 8.5f, FontStyle.Regular); } }
        // 0 title, 1 text, 2 badge (bottom strip, reserved even when empty), 3 check mark / star (top right, reserved), 4 picture
        public static Rectangle[] Layout(int w, int h, bool img, bool compact)
        {
            if (compact) return new Rectangle[] { new Rectangle(12, 0, w - 12 - CheckW - 6, h), Rectangle.Empty, Rectangle.Empty, new Rectangle(w - CheckW - 2, (h - 22) / 2, 22, 22), Rectangle.Empty };
            // "text always fits" (owner 07.11.2026): under a picture the text gets SubLines full lines; a picture that would leave less is made lower (drawn cropped, never squeezed)
            int ph = Math.Min((w - 24) * 350 / 600, h - 12 - 10 - 26 - SubLines * SubFont.Height - BadgeStrip);
            Rectangle ir = img ? new Rectangle(12, 12, w - 24, Math.Max(0, ph)) : Rectangle.Empty; int y = img ? ir.Bottom + 10 : 14;
            return new Rectangle[] { new Rectangle(14, y, w - 28 - CheckW, 22), new Rectangle(14, y + 26, w - 28, Math.Max(0, h - (y + 26) - BadgeStrip)), new Rectangle(14, h - BadgeStrip + 8, w - 28, BadgeH), new Rectangle(w - CheckW - 4, img ? 18 : 12, 22, 22), ir };
        }
        public Rectangle[] Slots() { return Layout(Width, Height, Img != null, Compact); }
        public WizCard() { SetStyle(ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw | ControlStyles.Selectable, true); TabStop = true; Cursor = Cursors.Hand; BackColor = Th.Bg; }
        protected override void Dispose(bool d) { if (hoverT != null) { hoverT.Stop(); hoverT.Dispose(); hoverT = null; } base.Dispose(d); }
        // hover only under the mouse (docs/design.md): a timer compares the real cursor with the control
        protected override void OnMouseEnter(EventArgs e) { hover = true; Invalidate(); if (hoverT == null) { hoverT = new System.Windows.Forms.Timer(); hoverT.Interval = 80; hoverT.Tick += delegate { if (!hover || !IsHandleCreated || !ClientRectangle.Contains(PointToClient(Cursor.Position))) { hover = false; hoverT.Stop(); Invalidate(); } }; } hoverT.Start(); base.OnMouseEnter(e); }
        protected override void OnMouseLeave(EventArgs e) { hover = false; if (hoverT != null) hoverT.Stop(); Invalidate(); base.OnMouseLeave(e); }
        protected override void OnEnabledChanged(EventArgs e) { hover = false; if (hoverT != null) hoverT.Stop(); Invalidate(); base.OnEnabledChanged(e); }
        protected override void OnMouseUp(MouseEventArgs e) { Focus(); if (Enabled && ClientRectangle.Contains(e.Location)) Pick(); base.OnMouseUp(e); }
        public void Pick() { if (Picked != null) Picked(this, EventArgs.Empty); }
        protected override bool IsInputKey(Keys k) { return k == Keys.Left || k == Keys.Right || k == Keys.Enter || k == Keys.Space || base.IsInputKey(k); }
        protected override void OnKeyDown(KeyEventArgs e) { if ((e.KeyCode == Keys.Space || e.KeyCode == Keys.Enter) && Enabled) { Pick(); e.Handled = true; } base.OnKeyDown(e); }
        protected override void OnGotFocus(EventArgs e) { Invalidate(); base.OnGotFocus(e); }
        protected override void OnLostFocus(EventArgs e) { Invalidate(); base.OnLostFocus(e); }
        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics; g.SmoothingMode = SmoothingMode.AntiAlias; g.Clear(Th.Bg); Rectangle[] L = Slots();
            Color fill = Sel ? Th.Mix(Th.Surf, Th.Amber, 0.12f) : (hover && Enabled ? Th.SurfHi : Th.Surf);
            Rectangle r = new Rectangle(1, 1, Width - 3, Height - 3);
            using (GraphicsPath p = Th.RR(r, Compact ? 8 : 10)) { using (SolidBrush b = new SolidBrush(fill)) g.FillPath(b, p); using (Pen pen = new Pen(Sel ? Th.Amber : (Focused ? Th.Muted : Th.Line), Sel ? 2f : 1f)) g.DrawPath(pen, p); }
            Color tc = Enabled ? Th.Text : Th.Faint;
            if (Img != null)
            {
                GraphicsState gs = g.Save(); using (GraphicsPath cp = Th.RR(L[4], 6)) g.SetClip(cp); g.InterpolationMode = InterpolationMode.HighQualityBicubic; g.PixelOffsetMode = PixelOffsetMode.HighQuality;
                Rectangle src = new Rectangle(0, 0, Img.Width, Img.Height);   // cover: the picture keeps its proportions, the slot crops it in the middle
                if (L[4].Width > 0 && L[4].Height > 0) { int sh = Img.Width * L[4].Height / L[4].Width; if (sh <= Img.Height) src = new Rectangle(0, (Img.Height - sh) / 2, Img.Width, sh); else { int sw = Img.Height * L[4].Width / L[4].Height; src = new Rectangle((Img.Width - sw) / 2, 0, sw, Img.Height); } }
                g.DrawImage(Img, L[4], src, GraphicsUnit.Pixel); g.Restore(gs);
                using (GraphicsPath cp = Th.RR(L[4], 6)) using (Pen pen = new Pen(Color.FromArgb(60, 255, 255, 255), 1f)) g.DrawPath(pen, cp);
            }
            if (Sel) { using (SolidBrush b = new SolidBrush(Th.Amber)) g.FillEllipse(b, L[3]); TextRenderer.DrawText(g, "\u2713", Th.F("Segoe UI Symbol", 9f, FontStyle.Bold), L[3], Th.OnAmber, TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding); }
            else if (Compact && Badge.Length > 0) TextRenderer.DrawText(g, "\u2605", Th.F("Segoe UI Symbol", 10f, FontStyle.Regular), L[3], Th.Amber, TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding);
            TextFit.Draw(g, this, Title, Th.F("Segoe UI Semibold", Compact ? 9.5f : (Img != null ? 10.5f : 11.5f), FontStyle.Regular), L[0], tc, TextFormatFlags.NoPadding | TextFormatFlags.EndEllipsis | TextFormatFlags.NoPrefix | (Compact ? TextFormatFlags.VerticalCenter : 0));
            if (!Compact)
            {
                TextFit.Draw(g, this, Sub, SubFont, L[1], Enabled ? Th.Muted : Th.Faint, TextFormatFlags.NoPadding | TextFormatFlags.WordBreak | TextFormatFlags.NoPrefix);
                if (Badge.Length > 0) Chip(g, Badge, L[2].X, L[2].Y, Th.Amber, Th.OnAmber);   // the reserved strip at the bottom: the same place on every card
            }
        }
        void Chip(Graphics g, string t, int x, int y, Color bg, Color fg)
        {
            Size sz = TextRenderer.MeasureText(g, t, Th.Small, new Size(300, 20), TextFormatFlags.NoPadding | TextFormatFlags.NoPrefix); Rectangle r = new Rectangle(x, y, sz.Width + 14, BadgeH - 2);
            using (GraphicsPath p = Th.RR(r, 6)) using (SolidBrush b = new SolidBrush(bg)) g.FillPath(b, p);
            TextFit.Draw(g, this, t, Th.Small, r, fg, TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding | TextFormatFlags.NoPrefix);
        }
    }

    // the sizes of the old and the large windows, to scale (a scheme, not a game screenshot: no picture of the large windows exists yet - docs/recon/INDEX.md)
    // Large windows: two mock-ups composed from the REAL sprites of the interface archive (tools/make_windows_preview.py; not game screenshots): the windows as they open now (on top of each other at (100,100))
    // and the kit (stats window at the left, backpack at the right with the centred pair [Close | Sort]). The chosen side has the amber frame.
    class SizeDiagram : Control
    {
        public bool Big; static Image imO, imB;
        public SizeDiagram() { SetStyle(ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true); BackColor = Th.Surf; }
        static Image Load(string id) { try { using (MemoryStream ms = new MemoryStream(Core.ResBytes("gfxprev_" + id))) using (Image src = Image.FromStream(ms)) return new Bitmap(src); } catch (Exception) { return null; } }
        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics; g.SmoothingMode = SmoothingMode.AntiAlias; g.InterpolationMode = InterpolationMode.HighQualityBicubic; g.Clear(Th.Surf);
            if (imO == null) imO = Load("winkit_orig"); if (imB == null) imB = Load("winkit_big");
            int gap = 28, w = (Width - gap) / 2, h = w * 520 / 800, y0 = 2; Rectangle[] rs = { new Rectangle(0, y0, w, h), new Rectangle(w + gap, y0, w, h) }; Image[] ims = { imO, imB };
            string[] cap = { U.R("Обычные окна", "Normal windows"), U.R("Крупные окна", "Large windows") };
            string[] sub = { U.R("Статус и рюкзак открываются друг на друге", "Stats and backpack open on top of each other"), U.R("Статус слева, рюкзак справа, «Закрыть | Сортировать»", "Stats at the left, backpack at the right, Close | Sort") };
            for (int i = 0; i < 2; i++)
            {
                bool hot = (i == 1) == Big; Rectangle r = rs[i];
                if (ims[i] != null) g.DrawImage(ims[i], r);
                using (Pen pen = new Pen(hot ? Th.Amber : Th.Line, hot ? 2f : 1f)) g.DrawRectangle(pen, r.X, r.Y, r.Width - 1, r.Height - 1);
                TextFit.Draw(g, this, cap[i], Th.F("Segoe UI Semibold", 9f, FontStyle.Regular), new Rectangle(r.X, r.Bottom + 4, r.Width, 18), hot ? Th.Amber : Th.Text, TextFormatFlags.NoPadding | TextFormatFlags.EndEllipsis);
                TextFit.Draw(g, this, sub[i], Th.Small, new Rectangle(r.X, r.Bottom + 21, r.Width, 16), Th.Muted, TextFormatFlags.NoPadding | TextFormatFlags.EndEllipsis);
            }
            TextRenderer.DrawText(g, "\u2192", Th.F("Segoe UI Symbol", 18f, FontStyle.Regular), new Rectangle(w, y0 + h / 2 - 20, gap, 40), Th.Amber, TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding);
        }
    }

    class WizardForm : Form
    {
        Core core; public WizResult R = new WizResult(); int step; Size real = Size.Empty; bool monPicked;
        static readonly string[] Ids = { "mon", "ui", "pic", "items", "bag", "fonts", "fx", "shaders", "apply" };
        public int Steps { get { return Ids.Length; } }
        Panel host = new Panel(); Label title = new Label(), sub = new Label(), counter = new Label(); Btn bBack, bNext, bCancel, bHelp; List<WizCard> cards = new List<WizCard>(); Dictionary<string, Image> imgs = new Dictionary<string, Image>();
        // step 0 controls
        Seg segMon, segWrap, segScale; Label lMon, lInfo, lScaleHead; bool bagTouched, fontsTouched;
        int[] scaleSteps = UiScale.Steps;
        const int W = 900, H = 640, BX = 24, BW = W - 48, BY = 96, BH = 456;

        public WizardForm(Core c)
        {
            core = c; Text = U.R("Быстрая настройка", "Quick setup"); FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false; MinimizeBox = false; ShowInTaskbar = false; StartPosition = FormStartPosition.CenterParent;
            BackColor = Th.Bg; ForeColor = Th.Text; Font = Th.Body; Fit.To(this, new Size(W, H));
            title.AutoSize = false; title.SetBounds(BX, 14, BW - 190, 28); title.Font = Th.F("Segoe UI Semibold", 14f, FontStyle.Regular); title.ForeColor = Th.Text; title.BackColor = Th.Bg; title.UseMnemonic = false;
            sub.AutoSize = false; sub.SetBounds(BX, 46, BW, 40); sub.Font = Th.F("Segoe UI", 9f, FontStyle.Regular); sub.ForeColor = Th.Muted; sub.BackColor = Th.Bg; sub.UseMnemonic = false;
            counter.AutoSize = false; counter.SetBounds(W - BX - 160 - 30, 18, 160, 20); counter.TextAlign = ContentAlignment.MiddleRight; counter.Font = Th.Small; counter.ForeColor = Th.Amber; counter.BackColor = Th.Bg;
            bHelp = new Btn(); bHelp.Under = Th.Bg; bHelp.Pt = 8f; bHelp.Text = "?"; bHelp.SetBounds(W - BX - 22, 17, 22, 22);
            host.SetBounds(BX, BY, BW, BH); host.BackColor = Th.Bg;
            bBack = new Btn(); bBack.Text = U.R("←  Назад", "←  Back"); bBack.SetBounds(BX, H - 62, 150, 44); bBack.Click += delegate { Go(step - 1); };
            bCancel = new Btn(); bCancel.Text = U.R("Отмена", "Cancel"); bCancel.SetBounds(BX + 162, H - 62, 130, 44); bCancel.Click += delegate { Close(); };
            bNext = new Btn(); bNext.Accent = true; bNext.Pt = 10f; bNext.SetBounds(W - BX - 240, H - 62, 240, 44); bNext.Click += delegate { if (step == Ids.Length - 1) Finish(); else Go(step + 1); };
            Controls.AddRange(new Control[] { title, sub, counter, bHelp, host, bBack, bCancel, bNext }); KeyPreview = true;
            KeyDown += delegate(object s, KeyEventArgs e) { if (e.KeyCode == Keys.Escape) Close(); };
            bHelp.Click += delegate { Help.Show(this, HelpKey()); };
            Defaults(); Go(0);
        }
        protected override void OnHandleCreated(EventArgs e) { base.OnHandleCreated(e); Dark.Apply(Handle); if (AutoScroll) Dark.Scroll(this); }
        protected override void Dispose(bool d) { if (d) foreach (Image im in imgs.Values) if (im != null) im.Dispose(); imgs.Clear(); base.Dispose(d); }
        protected override void OnShown(EventArgs e)
        {
            base.OnShown(e); Screen sc = Screen.FromControl(this); real = Core.ScreenPixels(sc);
            if (!monPicked) { R.Preset = Core.PresetForScreen(real.Width); MonitorChanged(true); }
            Go(step);
        }
        // ---- defaults: what "Next, Next, Next" gives; they follow the monitor class until the person touches the step
        void Defaults()
        {
            R.UseCnc = !(core.Dgv && !core.Cnc); int sv; Size sg; R.ScalePct = core.ScaleSaved(out sv, out sg) ? sv : 0;
            R.Ui = "c"; R.Items = "redrawn"; R.Pic = "orig"; R.Fps80 = core.Fps80Avail && R.UseCnc;   // owner 07.11.2026: the FPS mod is ON by default in quick setup (a dgVoodoo user keeps it off: the renderer is not swapped by "Next")
            R.Preset = Core.PresetForScreen(Screen.PrimaryScreen.Bounds.Width); MonitorChanged(true);
            GfxSel now = core.GfxCurrent(); if (now.Slot.ContainsKey("pic") && now.Slot["pic"] != "orig") R.Pic = now.Slot["pic"];
            LoadPrefs(now);
        }
        // the wizard remembers what the person chose (owner 07.11.2026): once it has been applied, the next opening starts from the REAL state on disk (what is applied now), plus the
        // monitor class / wrapper choice that cannot be read back from disk. No file yet (first run) = the recommended defaults above.
        static string PrefsFile(Core core) { return Path.Combine(core.GameData, "wizard_prefs.txt"); }
        void LoadPrefs(GfxSel now)
        {
            try
            {
                if (!File.Exists(PrefsFile(core))) return;
                Dictionary<string, string> kv = new Dictionary<string, string>();
                foreach (string ln in File.ReadAllLines(PrefsFile(core), Encoding.UTF8)) { int i = ln.IndexOf('='); if (i > 0) kv[ln.Substring(0, i).Trim()] = ln.Substring(i + 1).Trim(); }
                int pr; if (kv.ContainsKey("preset") && int.TryParse(kv["preset"], out pr) && pr >= 0 && pr <= 2) { R.Preset = pr; monPicked = true; }
                                string v;
                if (now.Slot.TryGetValue("ui", out v) && core.Gfx.Slot("ui").Find(v) != null) R.Ui = v;
                if (now.Slot.TryGetValue("items", out v) && (v == "redrawn" || v == "orig") && core.Gfx.Slot("items").Find(v) != null) R.Items = v;
                if (now.Slot.TryGetValue("pic", out v)) R.Pic = v;
                if (now.Slot.TryGetValue("bag", out v)) { R.Bag = v == "big"; bagTouched = true; }
                bool g; if (now.Fix.TryGetValue("glow", out g)) R.Glow = g; if (core.FxAvail) R.Shaders = core.FxRead().Shaders;
                if (core.FontsAvail) { R.Fonts = core.FontStep(0) == Core.FontLarge; fontsTouched = R.Fonts; }   // original fonts on disk do not pin the choice: 2K and 4K still get the larger ones
            }
            catch (Exception) { }
        }
        public static void SavePrefs(Core core, WizResult R)
        {
            try { Directory.CreateDirectory(core.GameData); File.WriteAllLines(PrefsFile(core), new string[] { "preset=" + R.Preset }, Encoding.UTF8); } catch (Exception) { }
        }
        void MonitorChanged(bool fromAuto)
        {
            ScalePlan p = PlanNow(); R.Plan = p;
            if (!bagTouched) R.Bag = R.Preset >= 1;
            if (!fontsTouched) R.Fonts = Core.PresetLargeFonts(R.Preset, p);
        }
        ScalePlan PlanNow() { return R.UseCnc && !real.IsEmpty ? core.PlanScale(R.ScalePct, Core.ClassMonitor(R.Preset, real)) : null; }
        string HelpKey() { switch (Ids[step]) { case "mon": return "quick_monitor"; case "ui": return "gfx_ui"; case "pic": return "gfx_pic"; case "fonts": return "gfx_fonts"; case "bag": return "gfx_bag"; case "fx": case "shaders": return "quick_fx"; case "items": return "gfx_items"; default: return "gfx_apply"; } }

        Image Img(string id)
        {
            if (id == null || id.Length == 0) return null; Image im; if (imgs.TryGetValue(id, out im)) return im;
            try { using (MemoryStream ms = new MemoryStream(Core.ResBytes("gfxprev_" + id))) using (Image src = Image.FromStream(ms)) im = new Bitmap(src); } catch (Exception) { im = null; }
            imgs[id] = im; return im;
        }
        string PrevOf(string slot, string val, int part) { GfxSlot s = core.Gfx.Slot(slot); GfxOpt o = s != null ? s.Find(val) : null; if (o == null) return null; string[] p = o.Prev.Split('+'); return part < p.Length ? p[part] : null; }

        // ---- navigation
        public void ShowStep(int to) { Go(to); }
        // logic check of the font step: both pictures exist and really differ (count of differing pixels); "none" = no game fonts here
        public string FontProbe()
        {
            Bitmap a = FontImg("font_0", 0) as Bitmap, b = FontImg("font_1", Core.FontLarge) as Bitmap; if (a == null || b == null) return "none"; int n = 0;
            for (int y = 0; y < a.Height; y += 2) for (int x = 0; x < a.Width; x += 2) if (a.GetPixel(x, y).ToArgb() != b.GetPixel(x, y).ToArgb()) n++;
            return "differing=" + n;
        }
        void Go(int to)
        {
            if (to < 0 || to >= Ids.Length) return; step = to; cards.Clear();
            Control[] old = new Control[host.Controls.Count]; host.Controls.CopyTo(old, 0); foreach (Control c in old) { host.Controls.Remove(c); c.Dispose(); }
            string id = Ids[step]; counter.Text = U.R("Шаг ", "Step ") + (step + 1) + U.R(" из ", " of ") + Ids.Length;
            host.SuspendLayout();
            if (id == "mon") StepMon(); else if (id == "ui") StepUi(); else if (id == "pic") StepPic(); else if (id == "fonts") StepFonts();
            else if (id == "bag") StepBag(); else if (id == "fx") StepFx(); else if (id == "shaders") StepShaders(); else if (id == "items") StepItems(); else StepApply();
            host.ResumeLayout();
            bBack.Visible = step > 0; bNext.Text = step == Ids.Length - 1 ? "✓  " + U.R("Применить", "Apply") : U.R("Далее  →", "Next  →"); Invalidate(true);
        }
        void Finish() { if (Core.GameRunning()) { MessageBox.Show(this, L.T("running"), L.T("warnTitle")); return; } R.Summary = Summary(); R.Done = true; Close(); }
        protected override bool ProcessCmdKey(ref Message msg, Keys k)
        {
            WizCard cur = ActiveControl as WizCard; int i = cur == null ? -1 : cards.IndexOf(cur);
            if (i >= 0 && (k == Keys.Left || k == Keys.Right)) { int j = i + (k == Keys.Left ? -1 : 1); if (j >= 0 && j < cards.Count && cards[j].Enabled) { cards[j].Focus(); cards[j].Pick(); } return true; }
            return base.ProcessCmdKey(ref msg, k);
        }
        void Head(string t, string s) { title.Text = t; sub.Text = s; }
        Label Lab(string t, int x, int y, int w, int h, bool amber) { Label l = new Label(); l.AutoSize = false; l.SetBounds(x, y, w, h); l.Text = t; l.UseMnemonic = false; l.BackColor = Th.Bg; l.ForeColor = amber ? Th.Amber : Th.Muted; l.Font = amber ? Th.Small : Th.F("Segoe UI", 9f, FontStyle.Regular); host.Controls.Add(l); return l; }
        WizCard Card(int x, int y, int w, int h, string t, string s, Image img, string badge, bool sel, EventHandler pick)
        {
            WizCard c = new WizCard(); c.SetBounds(x, y, w, h); c.Title = t; c.Sub = s; c.Img = img; c.Badge = badge; c.Sel = sel; c.Picked += pick; host.Controls.Add(c); cards.Add(c); return c;
        }
        // n cards in a row; selecting one clears the others
        delegate void Pick(int i);
        void Row(string[] titles, string[] subs, Image[] ims, string[] badges, int sel, int y, int h, Pick pick)
        {
            int n = titles.Length, gap = 14, w = (BW - gap * (n - 1)) / n; WizCard[] row = new WizCard[n];
            for (int i = 0; i < n; i++)
            {
                int k = i; row[i] = Card(i * (w + gap), y, w, h, titles[i], subs[i], ims == null ? null : ims[i], badges[i], i == sel, delegate { for (int j = 0; j < n; j++) { row[j].Sel = j == k; row[j].Invalidate(); } pick(k); });
            }
            if (sel >= 0 && sel < n) row[sel].TabIndex = 0;
        }
        string Mb(GfxOpt o) { return o != null && o.ApproxMb > 0 ? " " + U.R("· скачать ~", "· download ~") + o.ApproxMb + U.R(" МБ", " MB") : ""; }

        // ---- step 1: monitor, wrapper, interface size
        void StepMon()
        {
            Head(U.R("Монитор и игра", "Monitor and game"), U.R("Программа определила ваш монитор. От него зависят разрешение игры, обёртка, размер интерфейса и шрифты. Если всё верно, жмите «Далее».", "The program detected your monitor. The game resolution, the wrapper, the interface size and the fonts depend on it. If it is right, press Next."));
            lMon = Lab("", 0, 0, BW - 30, 20, true);
            segMon = new Seg(); segMon.Under = Th.Bg; segMon.Items = new string[] { "HD  1920×1080", "2K  2560×1440", "4K  3840×2160" }; segMon.SetBounds(0, 24, BW, 40); segMon.Selected = R.Preset; segMon.Changed += delegate { monPicked = true; R.Preset = segMon.Selected; MonitorChanged(false); StepMonInfo(); }; host.Controls.Add(segMon);
            Lab(U.R("ГРАФИЧЕСКАЯ ОБЁРТКА", "GRAPHICS WRAPPER"), 0, 78, 300, 18, true);
            segWrap = new Seg(); segWrap.Under = Th.Bg; segWrap.Items = new string[] { U.R("gr-draw ★ рекомендуется", "gr-draw ★ recommended"), "dgVoodoo" }; segWrap.SetBounds(0, 100, BW, 34); segWrap.Selected = R.UseCnc ? 0 : 1; segWrap.Changed += delegate { R.UseCnc = segWrap.Selected == 0; MonitorChanged(false); StepMonInfo(); }; host.Controls.Add(segWrap);
            lScaleHead = Lab(U.R("РАЗМЕР ИНТЕРФЕЙСА (МАСШТАБ КАРТИНКИ)", "INTERFACE SIZE (PICTURE SCALE)"), 0, 148, 400, 18, true);
            segScale = new Seg(); segScale.Under = Th.Bg; segScale.Items = new string[] { U.R("Авто", "Auto"), "100%", "125%", "150%", "200%" }; segScale.SetBounds(0, 170, BW, 34); segScale.Selected = Math.Max(0, Array.IndexOf(scaleSteps, R.ScalePct)); segScale.Changed += delegate { R.ScalePct = scaleSteps[segScale.Selected]; MonitorChanged(false); StepMonInfo(); }; host.Controls.Add(segScale);
            lInfo = new Label(); lInfo.AutoSize = false; lInfo.SetBounds(0, 218, BW, BH - 218); lInfo.BackColor = Th.Surf; lInfo.ForeColor = Th.Text; lInfo.Padding = new Padding(14); lInfo.UseMnemonic = false; host.Controls.Add(lInfo);
            StepMonInfo();
        }
        void StepMonInfo()
        {
            if (lMon == null || lInfo == null || lMon.IsDisposed) return; Screen sc = Screen.FromControl(this); int idx = Array.IndexOf(Screen.AllScreens, sc) + 1;
            lMon.Text = U.R("Ваш монитор", "Your monitor") + (Screen.AllScreens.Length > 1 ? " " + idx : "") + ": " + real.Width + "×" + real.Height + (monPicked ? "" : U.R(" — выбрано автоматически", " — picked automatically"));
            segScale.Visible = lScaleHead.Visible = R.UseCnc;
            lInfo.Text = Core.PresetNames[R.Preset] + "\n\n" + core.PresetSummary(R.Preset, R.UseCnc, R.Plan);
        }

        // ---- step 2: interface. ONE step: all 6 styles in one choice (the same as on the Graphics tab) + the Before | After slider (original against the chosen one)
        void StepUi()
        {
            Head(U.R("Интерфейс: рамки окон и кнопки", "Interface: window frames and buttons"), U.R("Выберите стиль внизу и ведите ползунок под картинками: слева — выбранный стиль, справа — оригинал. Те же 6 стилей, что на вкладке «Графика».", "Pick a style below and drag the slider under the pictures: your style on the left, the original on the right. The same 6 styles as on the Graphics tab."));
            string[] vals = { "orig", "e", "a", "b", "c", "d" }; GfxSlot sl = core.Gfx.Slot("ui");
            BeforeAfter ba = BA(0, 0, BW, new string[] { "inv_orig", "dlg_orig_f0" }, new string[] { PrevOf("ui", R.Ui, 0), (PrevOf("ui", R.Ui, 1) ?? "dlg_orig") + "_f0" }, new string[] { U.R("Инвентарь", "Inventory"), U.R("Разговор с NPC", "NPC dialogue") });
            // two rows of three plates (text always fits: in one row of six a plate left 87 px for the name, "Перерисованный" needs 110)
            int y = ba.Bottom + 8, gap = 8, w = (BW - gap * 2) / 3; WizCard[] pills = new WizCard[6]; Label desc = Lab("", 0, y + 2 * 44 + gap + 6, BW, 22, false);
            Action refresh = delegate
            {
                GfxOpt o = sl.Find(R.Ui); string v = R.Ui;
                ba.After = new Image[] { Img(PrevOf("ui", v, 0)), Img((PrevOf("ui", v, 1) ?? "dlg_orig") + "_f0") }; ba.CapAfter = v == "orig" ? U.R("После · без изменений", "After · unchanged") : U.R("После · ", "After · ") + o.Name; ba.Invalidate();
                desc.Text = o.Name + ": " + UiDesc(v) + Mb(o) + (v == "c" ? "  " + U.R("★ рекомендуем", "★ recommended") : "");
                for (int i = 0; i < 6; i++) { pills[i].Sel = vals[i] == v; pills[i].Invalidate(); }
            };
            for (int i = 0; i < 6; i++)
            {
                string v = vals[i]; WizCard c = Card(i % 3 * (w + gap), y + i / 3 * (44 + gap), w, 44, sl.Find(v).Name, "", null, v == "c" ? "\u2605" : "", false, delegate { R.Ui = v; refresh(); }); c.Compact = true; pills[i] = c;
            }
            refresh();
        }
        static string UiDesc(string v)
        {
            switch (v)
            {
                case "orig": return U.R("Как в игре из коробки: ничего не меняется.", "As in the box: nothing changes.");
                case "c": return U.R("Тот же вид, но чётче: рамки и кнопки в высоком разрешении.", "The same look, sharper: frames and buttons in high resolution.");
                case "e": return U.R("Полностью перерисованные окна в одном стиле.", "Fully redrawn windows in one style.");
                case "a": return U.R("Светлые пергаментные рамки.", "Light parchment frames.");
                case "b": return U.R("Тёмный металл с заклёпками.", "Dark metal with rivets.");
                default: return U.R("Тёмное стекло, современный вид.", "Dark glass, a modern look.");
            }
        }

        // ---- before | after helper for the on/off steps
        BeforeAfter BA(int x, int y, int w, string[] before, string[] after, string[] panes)
        {
            BeforeAfter b = new BeforeAfter(); int n = before.Length; b.SetBounds(x, y, w, (w - 8 * (n - 1)) / n * 350 / 600 + BeforeAfter.BarH + BeforeAfter.InfoH);
            Image[] bi = new Image[n], ai = new Image[n]; for (int i = 0; i < n; i++) { bi[i] = Img(before[i]); ai[i] = Img(after[i]); }
            b.Before = bi; b.After = ai; b.PaneTitles = panes; b.CapBefore = U.R("До · оригинал", "Before · original"); b.CapAfter = U.R("После · если включить", "After · if turned on"); host.Controls.Add(b); return b;
        }
        Seg OnOff(int x, int y, bool on, Action<bool> set)
        {
            Seg s = new Seg(); s.Under = Th.Bg; s.Items = new string[] { U.R("Выкл", "Off"), U.R("Вкл", "On") }; s.SetBounds(x, y, 150, 34); s.Selected = on ? 1 : 0; s.Changed += delegate { set(s.Selected == 1); }; host.Controls.Add(s); return s;
        }
        // ONE choice bar for every step with a choice (owner 07.11: "all choice buttons in the same place, the same size"): buttons 200x40 at x = 0, y = ChoiceY; the picture above it is never taller than ChoiceY - 14,
        // the explaining text sits under the bar at the same place on every step. Two bars side by side (the FPS / glow step) use x = 0 and x = BarX2 with the same size.
        const int ChoiceY = 344, ChoiceBtnW = 200, ChoiceH = 40, BarX2 = 452;
        Seg Choose(int x, string[] labels, int sel, Action<int> set)
        {
            Seg s = new Seg(); s.Under = Th.Bg; s.Items = labels; s.SetBounds(x, ChoiceY, ChoiceBtnW * labels.Length + 6, ChoiceH); s.Selected = sel; s.Changed += delegate { set(s.Selected); }; host.Controls.Add(s); return s;
        }
        Seg ChooseOnOff(int x, bool on, Action<bool> set) { return Choose(x, new string[] { U.R("Выкл", "Off"), U.R("Вкл", "On") }, on ? 1 : 0, delegate(int i) { set(i == 1); }); }
        Label Note(string text) { return Lab(text, 0, ChoiceY + ChoiceH + 10, BW, 62, false); }
        // ---- step 3: upscaling (Before | After + switch). Two frames under one slider: the inventory window as it is, and the SAME fragment enlarged 3x without smoothing, where the difference is clear
        void StepPic()
        {
            Head(U.R("Апскейлинг: чистые спрайты", "Upscaling: clean sprites"), U.R("Нейросеть очищает все спрайты игры: чётче края, меньше шума и «лесенки». Слева на картинках — «после», справа — оригинал: ведите ползунок. Правый кадр — тот же фрагмент, увеличенный в 3 раза.", "A neural network cleans all the game sprites: crisper edges, less noise and jaggies. On the pictures the result is on the left, the original on the right: drag the slider. The right frame is the same fragment enlarged 3 times."));
            BeforeAfter ba = BA(0, 0, BW, new string[] { "inv_orig", "up_orig" }, new string[] { PrevOf("pic", "v2", 0) ?? "inv_v2", "up_v2" }, new string[] { U.R("Окно инвентаря", "Inventory window"), U.R("Тот же фрагмент ×3", "The same fragment ×3") });
            GfxOpt o = core.Gfx.Slot("pic").Find("v2");
            ChooseOnOff(0, R.Pic != "orig", delegate(bool on) { R.Pic = on ? "v2" : "orig"; });
            Note(U.R("Апскейлинг «Чистая v2»", "Upscaling \"Clean v2\"") + Mb(o) + U.R(". Выкл — оригинальные спрайты. Умолчание: выключено (набор большой).", ". Off — the original sprites. Default: off (the set is big)."));
        }
        // ---- step 4: fonts. Two choices only: the game's own fonts (default) and larger ones; the pictures are REAL text drawn with the glyphs of the game's .fnt files (the same data as the Fonts window)
        void StepFonts()
        {
            Head(U.R("Шрифты", "Fonts"), U.R("Шрифты по умолчанию — как в игре; «Крупные» — увеличенный текст в диалогах, книгах и меню (удобно на большом мониторе). Ведите ползунок: слева — крупные, справа — по умолчанию. Другие наборы шрифтов — в окне «Шрифты» на вкладке «Графика».", "Default fonts are the game's own; \"Larger\" is bigger text in dialogues, books and menus (handy on a big monitor). Drag the slider: larger on the left, default on the right. Other font sets are in the Fonts window on the Graphics tab."));
            int pw = 456; Image f0 = FontImg("font_0", 0), f1 = FontImg("font_1", Core.FontLarge);
            BeforeAfter ba = new BeforeAfter(); ba.SetBounds((BW - pw) / 2, 0, pw, pw * 350 / 600 + BeforeAfter.BarH + BeforeAfter.InfoH); ba.Before = new Image[] { f0 }; ba.After = new Image[] { f1 }; ba.PaneTitles = new string[] { U.R("Текст игры: диалог, книга, меню", "Game text: dialogue, book, menu") };
            ba.CapBefore = U.R("По умолчанию", "Default"); ba.CapAfter = U.R("Крупные", "Larger"); host.Controls.Add(ba);
            Choose(0, new string[] { U.R("Шрифты по умолчанию", "Default fonts"), U.R("Крупные", "Larger") }, R.Fonts ? 1 : 0, delegate(int i) { fontsTouched = true; R.Fonts = i == 1; });
            Note(f0 == null ? U.R("Превью недоступно: шрифты игры не найдены. Выбор всё равно применится.", "Preview unavailable: the game fonts were not found. The choice still applies.") : U.R("Картинки — настоящие шрифты игры 1:1.", "The pictures are the game's real fonts, 1:1."));
        }
        Image FontImg(string key, int step)
        {
            Image im; if (imgs.TryGetValue(key, out im)) return im; Bitmap bm = null;
            try
            {
                if (core.HasGame && core.FontsAvail && core.FontSrc(0, step, "fontn3.fnt") != null)
                {
                    bm = new Bitmap(600, 350); bool ru = L.Ru;
                    using (Graphics g = Graphics.FromImage(bm))
                    {
                        g.Clear(Color.FromArgb(24, 21, 16)); Rectangle dlg = new Rectangle(10, 10, 580, 184), book = new Rectangle(10, 204, 300, 136), ui = new Rectangle(320, 204, 270, 136);
                        using (SolidBrush b = new SolidBrush(Color.FromArgb(46, 41, 34))) g.FillRectangle(b, dlg); using (SolidBrush b = new SolidBrush(Color.FromArgb(214, 196, 152))) g.FillRectangle(b, book); using (SolidBrush b = new SolidBrush(Color.FromArgb(36, 42, 42))) g.FillRectangle(b, ui);
                        FontLine(g, 2, step, "dialog_yellow.fnt", ru ? "Ну, ты готова отправиться в путь?" : "Well, are you ready to set off?", 24, 22);
                        FontLine(g, 2, step, "dialog_grey.fnt", ru ? "1. А куда мы отправимся?" : "1. Where are we going?", 24, 78); FontLine(g, 2, step, "dialog_grey.fnt", ru ? "2. Я скоро вернусь." : "2. I will be back soon.", 24, 108); FontLine(g, 2, step, "dialog_grey.fnt", ru ? "3. Я готова идти дорогой магии!" : "3. I am ready to walk the road of magic!", 24, 138);
                        FontLine(g, 1, step, "fontblack1.fnt", ru ? "Дневник: задание" : "Diary: quest", 24, 218); FontLine(g, 1, step, "fontblack2.fnt", ru ? "Найти кузнеца в деревне" : "Find the smith in the village", 24, 262);
                        FontLine(g, 0, step, "fontn3.fnt", ru ? "Золото: 1250" : "Gold: 1250", 334, 218); FontLine(g, 0, step, "fontn2.fnt", ru ? "Сила: 34   Ловкость: 28" : "Strength: 34   Dexterity: 28", 334, 262);
                    }
                }
            }
            catch (Exception) { if (bm != null) { bm.Dispose(); } bm = null; }
            imgs[key] = bm; return bm;
        }
        void FontLine(Graphics g, int cat, int step, string file, string text, int x, int y)
        {
            byte[] d = core.FontSrc(cat, step, file); if (d == null) return; MlFont f = MlFont.Parse(d); if (f.Glyphs.Count == 0) return;
            using (Bitmap b = f.Render(text)) { if (b != null) g.DrawImageUnscaled(b, x, y); }
        }
        // ---- step 5: large windows (to-scale scheme + switch)
        void StepBag()
        {
            Head(U.R("Крупные окна: рюкзак, торговля, характеристики", "Large windows: backpack, trade, stats"), U.R("Один комплект: рюкзак крупнее и с колесом мыши, торговля плитками с вкладками, широкое окно характеристик и новая кнопка «Сортировать» (Ctrl+C).", "One kit: a bigger backpack with the mouse wheel, trading with tiles and tabs, a wider stats window and a new Sort button (Ctrl+C)."));
            SizeDiagram sd = new SizeDiagram(); sd.SetBounds(0, 0, BW, 320); sd.Big = R.Bag; host.Controls.Add(sd);
            ChooseOnOff(0, R.Bag, delegate(bool on) { bagTouched = true; R.Bag = on; sd.Big = on; sd.Invalidate(); });
            GfxOpt o = core.Gfx.Slot("bag").Find("big");
            Note(U.R("Новое: кнопка «Сортировать» в рюкзаке (или Ctrl+C) раскладывает вещи по типам — оружие, броня, зелья, свитки, — у каждого типа своё место. Крупные окна" + Mb(o) + ". Картинки собраны из настоящих рисунков окон игры (не снимок экрана). Подходит для всех интерфейсов.", "New: the Sort button in the backpack (or Ctrl+C) arranges things by type - weapons, armour, potions, scrolls - each type has its own place. Large windows" + Mb(o) + ". The pictures are composed from the real window artwork of the game (not a screenshot). Fits every interface."));
        }
        // ---- step 6: the FPS mod and the item glow, on ONE page: two panels, two bars of the same size and place as on the other steps
        Control Info(int x, string title, string body)
        {
            Panel p = new Panel(); p.SetBounds(x, 0, BW - BarX2, ChoiceY - 14); p.BackColor = Th.Surf; host.Controls.Add(p);
            Label a = new Label(); a.AutoSize = false; a.SetBounds(18, 16, p.Width - 36, 26); a.Text = title; a.UseMnemonic = false; a.BackColor = Th.Surf; a.ForeColor = Th.Text; a.Font = Th.F("Segoe UI Semibold", 12f, FontStyle.Regular);
            Label b = new Label(); b.AutoSize = false; b.SetBounds(18, 52, p.Width - 36, p.Height - 68); b.Text = body; b.UseMnemonic = false; b.BackColor = Th.Surf; b.ForeColor = Th.Muted; b.Font = Th.F("Segoe UI", 9.5f, FontStyle.Regular);
            p.Controls.Add(a); p.Controls.Add(b); return p;
        }
        void StepFx()
        {
            Head(U.R("FPS-мод и подсветка предметов", "FPS mod and item glow"), U.R("Две необязательные вещи на одной странице: движение вдвое плавнее (экспериментально) и цветной ореол у редких предметов. Обе меняются потом на вкладке «Графика».", "Two optional things on one page: motion twice as smooth (experimental) and a coloured halo under rare items. Both can be changed later on the Graphics tab."));
            bool av = core.Fps80Avail;
            Info(0, U.R("FPS-мод (такт 80)", "FPS mod (80 Hz tick)"), U.R("Игра считает 40 шагов в секунду, поэтому ходьба на быстром мониторе выглядит ступенчато. FPS-мод показывает движение героя, NPC и камеры 80 раз в секунду, а ИИ, бой и скорость остаются прежними: игра не ускоряется.\n\nЭкспериментально: на изометрических диагоналях возможны мелкие рывки. Включён по умолчанию. Счётчик кадров в игре — клавиша F11.", "The game runs 40 steps a second, so walking looks stepped on a fast monitor. The FPS mod shows the movement of the hero, NPCs and camera 80 times a second, while AI, combat and speed stay the same: the game does not speed up.\n\nExperimental: small jerks are possible on isometric diagonals. On by default. The frame counter in the game: the F11 key.")
                + (R.UseCnc ? "" : U.R("\n\nПонадобится gr-draw: программа подключит его вместо dgVoodoo.", "\n\nNeeds gr-draw: the program turns it on instead of dgVoodoo.")) + (av ? "" : U.R("\n\nНедоступно для вашей версии игры.", "\n\nNot available for your game version.")));
            Info(BarX2, U.R("Подсветка редких предметов", "Glow of rare items"), U.R("Цветной ореол у редких предметов в рюкзаке: зелёные, жёлтые и золотые видны сразу. Подписи предметов на земле (Alt) тоже цветные.\n\nВключена по умолчанию.", "A coloured halo under rare items in the backpack: green, yellow and gold ones stand out at once. The item labels on the ground (Alt) are coloured too.\n\nOn by default."));
            Seg f = ChooseOnOff(0, R.Fps80 && av, delegate(bool on) { R.Fps80 = on; }); f.Enabled = av; if (!av) R.Fps80 = false;
            ChooseOnOff(BarX2, R.Glow, delegate(bool on) { R.Glow = on; });
            Lab(U.R("FPS-мод", "FPS mod"), 0, ChoiceY + ChoiceH + 10, 300, 20, true); Lab(U.R("ПОДСВЕТКА", "GLOW"), BarX2, ChoiceY + ChoiceH + 10, 300, 20, true);
        }
        // ---- step 8: effect shaders (our gr-draw build): experimental, OFF by default; on = the "Ambient" preset at game start (owner 07.11.2026)
        void StepShaders()
        {
            Head(U.R("Шейдеры эффектов (экспериментально)", "Effect shaders (experimental)"), U.R("Свечение огня и магии, тёплый свет вокруг огня, атмосфера в подземельях. В игре: F9 — включить или выключить, F10 — меню шейдеров (пресеты 1–5), F11 — счётчик кадров.", "Glow of fire and magic, warm light around fire, mood in dungeons. In the game: F9 turns them on or off, F10 opens the shader menu (presets 1-5), F11 shows the frame counter."));
            int pw = 456; BeforeAfter ba = new BeforeAfter(); ba.SetBounds((BW - pw) / 2, 0, pw, pw * 350 / 600 + BeforeAfter.BarH + BeforeAfter.InfoH); ba.Before = new Image[] { Img("fx_off") }; ba.After = new Image[] { Img("fx_on") };
            ba.PaneTitles = new string[] { U.R("Подземелье с факелами", "A dungeon with torches") }; ba.CapBefore = U.R("До · без шейдеров", "Before · no shaders"); ba.CapAfter = U.R("После · пресет «Эмбиент»", "After · \"Ambient\" preset"); host.Controls.Add(ba);
            Seg s = ChooseOnOff(0, R.Shaders && R.UseCnc, delegate(bool on) { R.Shaders = on; }); s.Enabled = R.UseCnc; if (!R.UseCnc) R.Shaders = false;
            Note(R.UseCnc ? U.R("Экспериментально: свечение иногда находит «огонь» не там (яркое золото, текст). По умолчанию выключено; включённые шейдеры работают сразу с пресетом «Эмбиент».", "Experimental: the glow sometimes finds \"fire\" in the wrong place (bright gold, text). Off by default; when on, they start with the \"Ambient\" preset.")
                : U.R("Шейдеры работают только с gr-draw (шаг «Монитор и игра»).", "The shaders work with gr-draw only (the Monitor and game step)."));
        }
        // ---- step 4: items
        void StepItems()
        {
            Head(U.R("Предметы: оружие, броня и вещи", "Items: weapons, armour and things"), U.R("Как выглядят предметы в рюкзаке. Нажмите на картинку, чтобы выбрать.", "How the items look in the backpack. Click a picture to choose."));
            string[] vals = { "orig", "redrawn" }; int n = vals.Length; string[] tx = new string[n], sb = new string[n], bd = new string[n]; Image[] im = new Image[n]; int sel = 1;
            string[] ds = { U.R("Как в игре из коробки.", "As in the box."), U.R("Предметы нарисованы заново нейросетью, слегка приглушены под стиль игры.", "Items redrawn by a neural network, slightly toned down to fit the game.") };
            for (int i = 0; i < n; i++) { GfxOpt o = core.Gfx.Slot("items").Find(vals[i]); tx[i] = o.Name; im[i] = Img(PrevOf("items", vals[i], 0)); sb[i] = ds[i] + Mb(o); bd[i] = vals[i] == "redrawn" ? U.R("★ рекомендуем", "★ recommended") : ""; if (R.Items == vals[i]) sel = i; }
            Seg bar = null;
            Row(tx, sb, im, bd, sel, 0, 330, delegate(int i) { R.Items = vals[i]; if (bar != null) bar.Selected = i; });   // a click on a picture and the bar below are the same choice
            bar = Choose(0, tx, sel, delegate(int i) { R.Items = vals[i]; for (int k = 0; k < cards.Count; k++) { cards[k].Sel = k == i; cards[k].Invalidate(); } });
            Note(U.R("Наборы скачиваются с нашего сервера при «Применить». Прежние предметы можно вернуть на вкладке «Графика». Подсветка редких предметов — на одной из следующих страниц.", "The sets are downloaded from our server on Apply. You can bring the old items back on the Graphics tab. The glow of rare items is on one of the next pages."));
        }
        // ---- last step: summary + apply
        string Summary()
        {
            List<string> l = new List<string>(); bool ru = L.Ru;
            l.Add(Core.PresetNames[R.Preset] + ", " + (R.UseCnc ? "gr-draw" : "dgVoodoo") + (R.UseCnc ? ", " + U.R("интерфейс ", "interface ") + UiScale.PctText(R.ScalePct) : ""));
            Func<string, string, string> nm = delegate(string slot, string v) { GfxOpt o = core.Gfx.Slot(slot).Find(v); return o == null ? v : o.Name; };
            l.Add(U.R("Интерфейс: ", "Interface: ") + nm("ui", R.Ui)); l.Add(U.R("Апскейлинг: ", "Upscaling: ") + (R.Pic == "orig" ? U.R("выкл", "off") : nm("pic", R.Pic)));
            l.Add(U.R("Шрифты: ", "Fonts: ") + (R.Fonts ? U.R("крупные", "larger") : U.R("оригинал", "original"))); l.Add(U.R("Крупные окна: ", "Large windows: ") + (R.Bag ? U.R("вкл", "on") : U.R("выкл", "off")));
            l.Add(U.R("Предметы: ", "Items: ") + nm("items", R.Items) + U.R(", подсветка ", ", glow ") + (R.Glow ? U.R("вкл", "on") : U.R("выкл", "off")));
            l.Add(U.R("FPS-мод (такт 80): ", "FPS mod (80 Hz tick): ") + (R.Fps80 ? U.R("вкл", "on") : U.R("выкл", "off")) + U.R(", шейдеры эффектов: ", ", effect shaders: ") + (R.Shaders ? U.R("вкл", "on") : U.R("выкл", "off")));
            l.Add(U.R("Озвучка, закат и рассвет, плавная работа, мелкие исправления: включены", "Voice, dusk and dawn, smooth play, small fixes: on"));
            return string.Join("\n", l.ToArray());
        }
        void StepApply()
        {
            Head(U.R("Всё готово — применить?", "All set — apply?"), U.R("Вот что будет настроено. Программа сделает всё одним действием и покажет ход работы; наборы картинок скачиваются с нашего сервера (нужен интернет, докачка и отмена работают). Игра должна быть закрыта. Всё можно вернуть кнопкой «Откатить всё».", "This is what will be set up. The program does it in one go and shows the progress; picture sets are downloaded from our server (internet needed; resume and cancel work). The game must be closed. Everything can be undone with \"Revert all\"."));
            Label l = new Label(); l.AutoSize = false; l.SetBounds(0, 0, BW, 300); l.BackColor = Th.Surf; l.ForeColor = Th.Text; l.Padding = new Padding(18); l.UseMnemonic = false; l.Font = Th.F("Segoe UI", 11f, FontStyle.Regular); l.Text = Summary().Replace("\n", "\n\n"); host.Controls.Add(l);
            l.Height = Math.Min(BH - 34, TextRenderer.MeasureText(l.Text, l.Font, new Size(BW - 36, 0), TextFormatFlags.WordBreak | TextFormatFlags.TextBoxControl | TextFormatFlags.NoPrefix).Height + 36 + 4);   // the summary is as tall as its text (text always fits)
            int mb = 0; foreach (string[] kv in new string[][] { new string[] { "ui", R.Ui }, new string[] { "pic", R.Pic }, new string[] { "items", R.Items } }) { GfxOpt o = core.Gfx.Slot(kv[0]).Find(kv[1]); if (o != null && o.SetId.Length > 0) mb += o.ApproxMb; }
            if (R.Bag) { GfxOpt o = core.Gfx.Slot("bag").Find("big"); if (o != null) mb += o.ApproxMb; }
            Lab(mb > 0 ? U.R("Скачать с сервера: примерно " + mb + " МБ.", "To download from the server: about " + mb + " MB.") : U.R("Скачивать ничего не нужно.", "Nothing to download."), 0, l.Bottom + 10, BW, 22, false);
        }
    }
}

namespace DDFixTool
{
    partial class MainForm
    {
        // the wizard's last step: everything the person chose, in ONE progress window. Order: monitor / wrapper / sound / small fixes (ApplyPreset, all-or-nothing with its own rollback),
        // then the fonts, then the picture sets (GfxApply, cancellable; a set the server does not have is skipped with a note, the rest is applied).
        void WizardApply(WizResult r)
        {
            if (Core.GameRunning()) { MessageBox.Show(this, L.T("running"), L.T("warnTitle")); return; }
            Core c = core; List<string> skipped = new List<string>();
            string err = WorkForm.Run(this, U.R("Быстрая настройка", "Quick setup"), U.R("Подготовка…", "Preparing…"), true, delegate(WorkForm w)
            {
                w.Report(U.R("Монитор, обёртка, звук и исправления…", "Monitor, wrapper, sound and fixes…"), 0, 0);
                foreach (string x in c.ApplyPreset(r.Preset, r.UseCnc || r.Fps80, r.Plan)) skipped.Add(x);
                if (c.FontsAvail) for (int fc = 0; fc < 3; fc++) if (c.FontStep(fc) >= 0) c.SetFontStep(fc, r.Fonts ? Core.FontLarge : 0);
                // when on: always re-set (the preset above may have rewritten ddraw.ini / the wrapper)
                if (c.Fps80Avail && (r.Fps80 || c.Fps80State() == "on")) { try { c.SetFps80(r.Fps80); } catch (Exception ex) { skipped.Add(ex.Message); } }
                else if (r.Fps80 && !c.Fps80Avail) skipped.Add(U.R("FPS-мод не включён: он недоступен для вашей версии игры.", "The FPS mod was not turned on: it is not available for your game version."));
                // effect shaders (our gr-draw build): on = the "Ambient" preset at game start; off = off at game start (the menu stays, F9 still works)
                if (c.FxAvail && (r.Shaders || c.FxRead().Shaders)) { try { FxState fs = c.FxRead(); fs.Shaders = r.Shaders; c.FxApply(fs); if (r.Shaders) c.FxStartPreset(); } catch (Exception ex) { skipped.Add(ex.Message); } }
                if (w.Cancelled) throw new CancelledEx();
                w.Report(U.R("Получаю список наборов…", "Getting the list of sets…"), 0, 0);
                Dictionary<string, AssetManifest> man = new Dictionary<string, AssetManifest>(); string note; foreach (AssetManifest m in c.Assets.LoadCatalog(out note)) man[m.Id] = m;
                GfxSel cur = c.GfxCurrent(), sel = new GfxSel(); sel.Slot["ui"] = r.Ui; sel.Slot["pic"] = r.Pic; sel.Slot["items"] = r.Items; sel.Slot["bag"] = r.Bag ? "big" : "orig"; if (c.Gfx.Fix("glow") != null) sel.Fix["glow"] = r.Glow;
                foreach (string sid in new string[] { "ui", "pic", "items", "bag" })   // a set the server does not offer: that choice stays as it is, the rest goes on
                {
                    GfxOpt o = c.Gfx.Slot(sid).Find(sel.Slot[sid]); if (o == null || o.SetId.Length == 0) continue;
                    if (!man.ContainsKey(c.GfxSetId(o, sel, cur))) { sel.Slot.Remove(sid); skipped.Add(U.R("«" + o.Name + "» не применён: набора нет на сервере или нет связи. Повторите на вкладке «Графика».", "\"" + o.Name + "\" was not applied: the set is not on the server or there is no connection. Repeat it on the Graphics tab.")); }
                }
                GfxPlan pl = c.GfxMakePlan(sel, man);
                if (pl.Problems.Count > 0) { skipped.Add(string.Join(" ", pl.Problems.ToArray())); return; }
                if (pl.Empty) return;
                c.GfxApply(pl, delegate(string t, long d, long tot) { w.Report(t, d, tot); }, delegate { return w.Cancelled; });
            });
            gfxSel = new GfxSel(); gfxHi.Clear(); gfxHiVal.Clear(); if (gfxSub != null) { gfxSub.Text = gfxSubText; gfxSub.ForeColor = Th.Muted; gfxSub.Font = Th.F("Segoe UI", 8.5f, FontStyle.Regular); }
            foreach (string x in skipped) notes.Add(x);
            if (err == null) { WizardForm.SavePrefs(c, r); Log(L.T("applied") + "wizard: " + r.Summary.Replace("\n", "; ")); MessageBox.Show(this, U.R("Быстрая настройка выполнена.\r\n\r\n", "Quick setup is done.\r\n\r\n") + r.Summary.Replace("\n", "\r\n") + U.R("\r\n\r\nПрежние настройки можно вернуть кнопкой «Откатить всё».", "\r\n\r\nThe previous settings come back with \"Revert all\"."), App.Name, MessageBoxButtons.OK, MessageBoxIcon.Information); }
            else if (err.Length == 0) MessageBox.Show(this, U.R("Отменено. Уже сделанные шаги остались, скачанное сохранено — можно продолжить позже.", "Cancelled. Steps already done stay; what was downloaded is kept - you can continue later."), App.Name, MessageBoxButtons.OK, MessageBoxIcon.Information);
            else { Log(L.T("errTitle") + ": " + err); MessageBox.Show(this, err, L.T("errTitle"), MessageBoxButtons.OK, MessageBoxIcon.Warning); }
            RefreshState(); FlushNotes();
        }
    }
}
