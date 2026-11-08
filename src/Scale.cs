// "Interface size / picture scale": the game is rendered at a SMALLER resolution (monitor / scale) and cnc-ddraw stretches the WHOLE frame to the monitor,
// so the windows, text and the world all get bigger (the windows themselves are hard-coded in div.exe). Generic: limits of the game's renderer are data (ScaleLimits).
using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Text.RegularExpressions;

namespace DDFixTool
{
    // what the game's renderer accepts. Defaults = Divine Divinity (Software renderer, config.div width/height): nothing below the classic 800x600 (menus break),
    // nothing above 4K (not tested; the 2560x1440 case works with cnc-ddraw "resolutions=2"). Width is kept a multiple of 8 when the size has to be rounded (all classic modes are).
    class ScaleLimits { public int MinW = 800, MinH = 600, MaxW = 3840, MaxH = 2160, StepW = 8, StepH = 2; }

    class ScalePlan
    {
        public int Pct;                 // what was asked: 0 = auto, else 100..200
        public int EffPct;              // the percent really used (auto resolved, lowered/raised by the limits)
        public Size Mon, Game;          // monitor in real pixels, internal game resolution
        public double Factor;           // monitor width / game width
        public bool Integer;            // the stretch is a whole number (1x, 2x, 3x): the sharpest case
        public string Shader;           // ddraw.ini "shader"
        public List<string> Notes = new List<string>();   // codes, text via UiScale.NoteText
        public bool Auto { get { return Pct == 0; } }
    }

    static class UiScale
    {
        public static readonly int[] Steps = { 0, 100, 125, 150, 200 };   // 0 = auto
        public const string ShaderInteger = "Nearest neighbor";            // crispest text when the stretch is a whole number
        public const string ShaderFraction = "Shaders\\interpolation\\lanczos2-sharp.glsl";   // sharpest of the bundled smooth filters for 125% / 150%

        // 4K -> 200% (1920x1080, exactly x2), 1440p / 1600p -> 125%, 1080p and below -> 100%
        public static int AutoPct(Size m) { return m.Height >= 2000 ? 200 : (m.Height >= 1300 ? 125 : 100); }
        public static string PctText(int pct) { return pct == 0 ? (L.Ru ? "Авто" : "Auto") : pct + "%"; }
        // modes cnc-ddraw v7.1 reports with resolutions=2 (full list; the monitor's own size is always added). Checked with an EnumDisplayModes test (fx_shader/ddfx_src/fx/ddenum.c).
        static readonly int[][] CncStock = {
            new[]{320,200}, new[]{320,240}, new[]{512,384}, new[]{640,400}, new[]{640,480}, new[]{800,600}, new[]{1024,768}, new[]{1280,1024}, new[]{1600,1200}, new[]{1280,720},
            new[]{1024,600}, new[]{1280,960}, new[]{2048,1536}, new[]{960,600}, new[]{1440,900}, new[]{1680,1050}, new[]{1920,1200}, new[]{2560,1600},
            new[]{960,540}, new[]{1360,768}, new[]{1600,900}, new[]{1920,1080}, new[]{2560,1440}, new[]{1280,540}, new[]{1720,720}, new[]{2560,1080} };
        public static bool IsCncStockMode(Size s) { foreach (int[] m in CncStock) if (m[0] == s.Width && m[1] == s.Height) return true; return false; }
        public static bool TryParsePct(string s, out int pct)
        {
            pct = 0; if (s == null) return false; s = s.Trim().TrimEnd('%').ToLower();
            if (s == "auto") return true;
            return int.TryParse(s, out pct) && Array.IndexOf(Steps, pct) > 0;
        }
        public static bool TryParseSize(string s, out Size sz)
        {
            sz = Size.Empty; Match m = Regex.Match(s ?? "", @"^(\d{3,5})[xX×](\d{3,5})$"); if (!m.Success) return false;
            sz = new Size(int.Parse(m.Groups[1].Value), int.Parse(m.Groups[2].Value)); return sz.Width >= 320 && sz.Height >= 200;
        }

        // internal size for a factor f: exact when the division is whole and even, otherwise rounded (width to StepW, height follows the monitor's aspect)
        static Size Fit(double f, Size mon, ScaleLimits lim)
        {
            double w0 = mon.Width / f, h0 = mon.Height / f; int wi = (int)Math.Round(w0), hi = (int)Math.Round(h0);
            if (Math.Abs(w0 - wi) < 1e-6 && Math.Abs(h0 - hi) < 1e-6 && wi % 2 == 0 && hi % 2 == 0) return new Size(wi, hi);
            int w = (int)Math.Floor(w0 / lim.StepW) * lim.StepW; if (w < lim.StepW) w = lim.StepW;
            int h = (int)Math.Round(w * (double)mon.Height / mon.Width / lim.StepH) * lim.StepH; if (h < lim.StepH) h = lim.StepH;
            return new Size(w, h);
        }

        // pct: 0 = auto, 100/125/150/200
        public static ScalePlan Plan(int pct, Size mon, ScaleLimits lim)
        {
            ScalePlan p = new ScalePlan(); p.Pct = pct; p.Mon = mon; int use = pct == 0 ? UiScale.AutoPct(mon) : pct; double f = use / 100.0; p.EffPct = use;
            if (mon.Width < lim.MinW || mon.Height < lim.MinH)   // a monitor smaller than the game's minimum: no scaling at all
            {
                p.Game = new Size(mon.Width - mon.Width % 2, mon.Height - mon.Height % 2); p.Notes.Add("small"); f = 1; p.EffPct = 100;
            }
            else
            {
                Size g = Fit(f, mon, lim);
                if (g.Width < lim.MinW || g.Height < lim.MinH)   // too coarse for this monitor (e.g. 200% on 1366x768): the largest factor that still gives the minimum
                {
                    f = Math.Min(mon.Width / (double)lim.MinW, mon.Height / (double)lim.MinH); g = Fit(f, mon, lim);
                    g = new Size(Math.Max(g.Width, lim.MinW), Math.Max(g.Height, lim.MinH)); p.Notes.Add("min");
                }
                if (g.Width > lim.MaxW || g.Height > lim.MaxH)   // beyond what the renderer is known to take (5K / 8K, 100% on 4K): stretch more
                {
                    f = Math.Max(mon.Width / (double)lim.MaxW, mon.Height / (double)lim.MaxH); g = Fit(f, mon, lim);
                    g = new Size(Math.Min(g.Width, lim.MaxW), Math.Min(g.Height, lim.MaxH)); p.Notes.Add("max");
                }
                p.Game = g; p.EffPct = (int)Math.Round(100 * f);
            }
            double fw = mon.Width / (double)p.Game.Width, fh = mon.Height / (double)p.Game.Height; p.Factor = fw;
            double r = Math.Round(fw);
            p.Integer = r >= 1 && Math.Abs(fw - r) < 0.002 && Math.Abs(fh - r) < 0.002;
            p.Shader = p.Integer ? ShaderInteger : ShaderFraction;
            if (!p.Integer) p.Notes.Add("frac");
            if (mon.Width / (double)mon.Height > 2.0) p.Notes.Add("wide");
            if (p.Game.Width % 8 != 0) p.Notes.Add("odd8");
            if (p.Game.Width > 2560 || p.Game.Height > 1440) p.Notes.Add("big");
            return p;
        }

        public static string NoteText(string code, bool ru)
        {
            switch (code)
            {
                case "small": return ru ? "Монитор меньше минимума игры (800×600): масштаб не применяется, игра идёт в размере монитора." : "The monitor is smaller than the game's minimum (800×600): no scaling, the game runs at the monitor's size.";
                case "min": return ru ? "Масштаб ограничен: меньше 800×600 игра не работает, взят максимально возможный для этого монитора." : "Scale limited: the game does not work below 800×600, the largest possible scale for this monitor is used.";
                case "max": return ru ? "Разрешение игры ограничено 3840×2160 (больше не проверялось), картинка растягивается сильнее." : "The game resolution is capped at 3840×2160 (not tested above), so the picture is stretched more.";
                case "frac": return ru ? "Дробный масштаб: текст и линии немного мягче, чем при целом (100% / 200%). Для лучшей чёткости выберите 200% (или 100%)." : "Fractional scale: text and lines are a little softer than at a whole number (100% / 200%). For the best sharpness pick 200% (or 100%).";
                case "wide": return ru ? "Ультраширокий монитор: игра рисуется в его пропорциях; на таких мониторах игра не проверялась (интерфейс прижат к центру/краям, возможны глюки)." : "Ultra-wide monitor: the game is drawn in its aspect; the game was not tested on such monitors (UI placement may be off).";
                case "odd8": return ru ? "Ширина игры не кратна 8 — такие размеры не проверялись на вашей версии игры." : "The game width is not a multiple of 8 — such sizes were not tested with this game version.";
                case "big": return ru ? "Разрешение игры выше 2560×1440: программная отрисовка сильно грузит процессор, не проверялось." : "A game resolution above 2560×1440: software rendering loads the CPU heavily, not tested.";
            }
            return code;
        }
        public static string Summary(ScalePlan p, bool ru)
        {
            string fac = p.Integer ? (ru ? "целое ×" : "whole ×") + (int)Math.Round(p.Factor) : (ru ? "дробное ×" : "fractional ×") + p.Factor.ToString("0.00", System.Globalization.CultureInfo.InvariantCulture);
            string flt = p.Integer ? (ru ? "«Чётко» — целый коэффициент, пиксель в пиксель" : "Sharp - a whole factor, pixel for pixel") : (ru ? "Lanczos — дробный коэффициент, сглаживание без «лесенки»" : "Lanczos - a fractional factor, smoothing without stair-steps");
            return (ru ? "Игра " : "Game ") + p.Game.Width + "×" + p.Game.Height + " → " + (ru ? "монитор " : "monitor ") + p.Mon.Width + "×" + p.Mon.Height
                 + " (" + (ru ? "размер " : "size ") + (p.Auto ? (ru ? "авто, " : "auto, ") : "") + p.EffPct + "%, " + fac + (ru ? ", фильтр " : ", filter ") + flt + ")";
        }
        public static string Warnings(ScalePlan p, bool ru)
        {
            List<string> l = new List<string>(); foreach (string n in p.Notes) l.Add(NoteText(n, ru)); return string.Join("\n", l.ToArray());
        }
    }

    partial class Core
    {
        // limits of the current game's renderer (Divine Divinity = defaults; another game would supply its own)
        public ScaleLimits ScaleLim { get { return new ScaleLimits(); } }
        string ScaleFile { get { return Path.Combine(GameData, "scale.txt"); } }   // last applied: pct;monW;monH;gameW;gameH

        // the monitor a preset class stands for: the real one when it matches the class, else the class's nominal size
        public static Size ClassMonitor(int k, Size detected)
        {
            if (PresetForScreen(detected.Width) == k) return detected;
            return k == 2 ? new Size(3840, 2160) : (k == 1 ? new Size(2560, 1440) : new Size(1920, 1080));
        }
        public ScalePlan PlanScale(int pct, Size mon) { return UiScale.Plan(pct, mon, ScaleLim); }

        // the saved choice (for the settings window): false = never applied
        public bool ScaleSaved(out int pct, out Size game)
        {
            pct = 0; game = Size.Empty;
            try
            {
                if (!File.Exists(ScaleFile)) return false; string[] a = File.ReadAllText(ScaleFile).Trim().Split(';');
                pct = int.Parse(a[0]); game = new Size(int.Parse(a[3]), int.Parse(a[4])); return true;
            }
            catch { return false; }
        }
        // "Filter: Auto" = the program picks it from the interface size (sharp for whole factors, Lanczos for fractional); a hand-picked filter turns it off
        string FilterAutoFile { get { return Path.Combine(GameData, "filter_auto.txt"); } }
        public bool FilterAuto { get { return File.Exists(FilterAutoFile); } set { try { if (value) { Directory.CreateDirectory(GameData); File.WriteAllText(FilterAutoFile, "1"); } else if (File.Exists(FilterAutoFile)) File.Delete(FilterAutoFile); } catch { } } }
        void ScaleSave(ScalePlan p) { FilterAuto = true; Directory.CreateDirectory(GameData); File.WriteAllText(ScaleFile, p.Pct + ";" + p.Mon.Width + ";" + p.Mon.Height + ";" + p.Game.Width + ";" + p.Game.Height); }

        // the game's own resolution: config.div (text) and the two slashed*.cfg (int32 at 0x0C / 0x10; the software one is what cnc-ddraw uses)
        void WriteResolution(int w, int h)
        {
            string cd = P("config.div");
            if (File.Exists(cd)) { string t = File.ReadAllText(cd, System.Text.Encoding.Default); t = Regex.Replace(t, @"(?m)^width\s+\d+", "width " + w); t = Regex.Replace(t, @"(?m)^height\s+\d+", "height " + h); File.WriteAllText(cd, t, System.Text.Encoding.Default); }
            foreach (string cfgName in new string[] { "slashed-d3d6.cfg", "slashed-software.cfg" })
            {
                string dc = P(cfgName);
                if (File.Exists(dc)) { byte[] b = File.ReadAllBytes(dc); if (b.Length >= 0x14) { BitConverter.GetBytes(w).CopyTo(b, 0x0C); BitConverter.GetBytes(h).CopyTo(b, 0x10); File.WriteAllBytes(dc, b); } }
            }
        }
        // cnc-ddraw: borderless full screen, aspect kept (black bars instead of stretching), the filter that fits the stretch
        void WriteCncScale(ScalePlan p)
        {
            CncSet("windowed", "true"); CncSet("fullscreen", "true"); CncSet("maintas", "true"); CncSet("shader", p.Shader); CncSet("renderer", "opengl"); if (FileHas(P("ddraw.dll"), "dd-fx.cfg")) CncSet("fx", "true");
            // The game checks its config.div resolution against the list of modes cnc-ddraw reports; a size that is not in that list (2048x1152, 1707x960...) makes it ask
            // "reset configuration?" and, after "No", quit silently. cnc-ddraw can add ONE custom mode (inject_resolution), so do that for every size that is not a stock mode.
            CncSet("inject_resolution", UiScale.IsCncStockMode(p.Game) ? "" : p.Game.Width + "x" + p.Game.Height);
        }

        // The originals "Revert all" must bring back, taken once (before the first change). Shared by quick setup and the scale setting.
        void PresetBackupOriginals()
        {
            Directory.CreateDirectory(PresetDir);
            foreach (string f in PresetFiles)
            {
                string dst = Path.Combine(PresetDir, f); if (File.Exists(dst)) continue;
                string srcf = f == "slashed.cfg" && File.Exists(CncRenderPrev) ? CncRenderPrev : P(f);
                if (File.Exists(srcf)) File.Copy(srcf, dst);
            }
            string pre = Path.Combine(PresetDir, PresetIniName);   // the ddraw.ini that is in the game folder right now (cnc-ddraw on): comes back on revert while cnc-ddraw stays on
            if (!File.Exists(pre) && Cnc && File.Exists(P("ddraw.ini"))) File.Copy(P("ddraw.ini"), pre);
        }
        const string PresetIniName = "ddraw.ini.pre";

        // Applies ONLY the scale (cnc-ddraw must be on): resolution in config.div / slashed*.cfg + ddraw.ini. All-or-nothing; the originals go to the preset backup (Revert all).
        public ScalePlan ApplyScale(int pct, Size mon)
        {
            if (!HasGame) throw new InvalidOperationException(L.Ru ? "Игра не найдена." : "Game not found.");
            if (!Cnc) throw new InvalidOperationException(L.Ru ? "Масштаб картинки работает через gr-draw: сначала включите его." : "The picture scale works through gr-draw: turn it on first.");
            ScalePlan p = PlanScale(pct, mon);
            PresetBackupOriginals();
            string[] files = { "config.div", "slashed-d3d6.cfg", "slashed-software.cfg", "ddraw.ini" }; Dictionary<string, byte[]> snap = new Dictionary<string, byte[]>();
            foreach (string f in files) if (File.Exists(P(f))) snap[f] = File.ReadAllBytes(P(f));
            try { WriteResolution(p.Game.Width, p.Game.Height); WriteCncScale(p); ScaleSave(p); }
            catch (Exception ex)
            {
                List<string> undo = new List<string>();
                foreach (KeyValuePair<string, byte[]> kv in snap) { try { File.WriteAllBytes(P(kv.Key), kv.Value); } catch (Exception e2) { undo.Add(kv.Key + ": " + e2.Message); } }
                throw new InvalidOperationException((L.Ru ? "Масштаб не применён: " : "The scale was not applied: ") + ex.Message + (undo.Count > 0 ? "\n" + string.Join("; ", undo.ToArray()) : ""), ex);
            }
            Log(L.T("applied") + "scale " + UiScale.Summary(p, false));
            return p;
        }
    }
}
