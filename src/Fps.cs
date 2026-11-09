// FROZEN 07.11.2026 (owner): the frame mode (interpolation / tick 80) waits for an interpolation without artifacts (camera interpolation shows artifacts, tick 80 glitches on isometric
// diagonals; docs/recon/2026-11-07_release_review.md). FpsEnabled = false: no UI shows it, the wizard has no step for it, the defaults do not touch it, and nothing writes maxgameticks / vsync / maxfps
// because of it. The code stays for the lab: set the environment variable GAMEREMIX_FPS_LAB=1 (selftest, --fps in the command line). Taking an applied patch OUT (FpsOrig) always works.
// "Frame mode" (Patches & fixes + quick setup wizard): how many frames per second the game shows. One choice instead of several switches:
//   0 Original      - no interpolation, ddraw.ini as it was (the game's own 40 logic steps, the wrapper's 60 Hz emulation);
//   1 Monitor       - (default) frame interpolation patch of div.exe + gr-draw: vsync=true, maxfps=-1, maxgameticks=-1: as smooth as the monitor, no tearing;
//   2 Unlimited     - the patch + vsync=false, maxfps=0, maxgameticks=-1: hundreds of FPS, tearing is possible, the video card works at full load;
//   3 Own limit N   - the patch + vsync=false, maxfps=N, maxgameticks=-1.
// maxgameticks=0 in ddraw.ini is cnc-ddraw's "emulate 60 Hz vblank" - THE ceiling of 60 FPS (docs/recon/2026-11-07_fps_cap.md), so it must be -1 in modes 1-3.
// The patch (gfx.txt patch=interp, built from patch_research/interp_patch.py, docs/recon/2026-11-07_interp.md) is a prototype checked by emulation and by the owner on a test copy.
// Without gr-draw the patch is useless, so switching a mode on also turns gr-draw on (dgVoodoo steps aside, as always).
using System;
using System.Collections.Generic;
using System.IO;
using System.Drawing;
using System.Windows.Forms;

namespace DDFixTool
{
    partial class Core
    {
        public static readonly bool FpsEnabled = Environment.GetEnvironmentVariable("GAMEREMIX_FPS_LAB") == "1";   // FROZEN: false for everybody else
        public const int FpsOrig = 0, FpsMonitor = 1, FpsUnlimited = 2, FpsCustom = 3;
        public static readonly int[] FpsPresets = { 60, 120, 144, 165, 240 };
        public bool FpsAvail { get { return FpsEnabled && HasGame && ExeSupported && GfxBytePatch("interp") != null && BytePatchState("interp") != "n/a"; } }
        // current mode read from the disk; n = the limit of mode 3. -1 = unavailable (another build of the game / a half-made patch)
        public int FpsMode(out int n)
        {
            n = 0; if (!HasGame) return -1; string st = BytePatchState("interp"); if (st == "n/a" || st == "mixed") return -1; if (st == "off") return FpsOrig;
            if (!Cnc) return FpsMonitor;
            if (CncGet("vsync", "false").Trim().ToLower() == "true") return FpsMonitor;
            int v; if (!int.TryParse(CncGet("maxfps", "-1").Trim(), out v) || v < 0) return FpsMonitor; if (v == 0) return FpsUnlimited; n = v; return FpsCustom;
        }
        public static string FpsStatus(Core c) { int n; int m = c.FpsMode(out n); return m == FpsOrig ? "orig" : m == FpsMonitor ? "monitor" : m == FpsUnlimited ? "unlimited" : m == FpsCustom ? "custom" + n : "na"; }
        public static string FpsName(int mode, int n)
        {
            return mode == FpsMonitor ? U.R("по частоте монитора", "monitor refresh rate") : mode == FpsUnlimited ? U.R("без ограничения", "unlimited") : mode == FpsCustom ? U.R("свой лимит ", "own limit ") + n : mode == FpsOrig ? U.R("как в оригинале (40)", "as in the original (40)") : U.R("недоступно", "unavailable");
        }
        public void SetFpsMode(int mode, int n)
        {
            if (!HasGame) throw new InvalidOperationException(L.T("stNoGame")); if (GameRunning()) throw new InvalidOperationException(L.T("running"));
            if (mode == FpsOrig)
            {
                string was = BytePatchState("interp"); bool applied = was == "on" || was == "mixed";   // ddraw.ini is touched only to undo what the mode itself had set
                if (was != "off" && was != "n/a") SetBytePatch("interp", false);
                if (applied && Cnc && File.Exists(P("ddraw.ini"))) { CncSet("maxgameticks", "0"); CncSet("vsync", "true"); CncSet("maxfps", "-1"); }   // the wrapper's own defaults again
                Sync(); Log(L.T("applied") + "frame mode: original"); return;
            }
            if (!FpsEnabled) throw new InvalidOperationException("frame mode is frozen");
            if (!ExeSupported || !FpsAvail) throw new InvalidOperationException(L.T("stBadExe"));
            if (mode == FpsCustom && (n < 20 || n > 1000)) throw new ArgumentOutOfRangeException("n");
            if (!Cnc) SetCnc(true);   // the interpolation needs gr-draw (frames are limited inside the wrapper)
            SetBytePatch("interp", true);
            CncSet("renderer", "opengl"); CncSet("maxgameticks", "-1");
            if (mode == FpsMonitor) { CncSet("vsync", "true"); CncSet("maxfps", "-1"); }
            else if (mode == FpsUnlimited) { CncSet("vsync", "false"); CncSet("maxfps", "0"); }
            else { CncSet("vsync", "false"); CncSet("maxfps", n.ToString()); }
            Sync(); Log(L.T("applied") + "frame mode: " + FpsName(mode, n));
        }

        // ---- defaults of "Patches & fixes" (owner 07.11.2026): everything useful is ON without a click. Once per game (marker file); what the player switched off by hand
        // or with "Revert all" is remembered (fixes_optout.txt: voice, dusk, smooth, fps) and not switched on again. dgVoodoo users keep their wrapper (no frame mode for them).
        string Defaults2File { get { return Path.Combine(GameData, "fixes_default2.txt"); } }
        public void ApplyPatchDefaults(bool force)
        {
            if (!HasGame || GameRunning() || !ExeSupported) return;
            if (!force && File.Exists(Defaults2File)) return;
            Action<string, Action> one = delegate(string id, Action a) { if (force) FixOptOut(id, false); else if (FixOptedOut(id)) return; try { a(); } catch (Exception ex) { Log("default " + id + ": " + ex.Message); } };
            if (VoiceUseful) one("voice", delegate { if (!VoiceOn) SetVoice(true); });
            one("dusk", delegate { if (!DuskOn) SetDusk(true); });
            one("smooth", delegate { if (!Launcher) SetLauncher(true); });   // compat flags; with gr-draw the wrapper pins one core itself - kept on, it is the combination the interpolation was tried with
            if (FpsEnabled) one("fps", delegate { int n; if (FpsMode(out n) == FpsOrig && FpsAvail && (force || Cnc || !Dgv)) SetFpsMode(FpsMonitor, 0); });
            try { Directory.CreateDirectory(GameData); File.WriteAllText(Defaults2File, "1"); } catch { }
        }
    }
}

namespace DDFixTool
{
    // "Frame mode" window (opened from Patches & fixes): the four modes, one button each; a choice is applied at once (the game must be closed)
    class FpsForm : ToolForm
    {
        NumericUpDown num; int curMode, curN;
        public FpsForm(Core c) : base(c, new Size(880, 560)) { }
        protected override string TitleRu { get { return "Режим кадров"; } }
        protected override string TitleEn { get { return "Frame mode"; } }
        void Choose(int mode)
        {
            try
            {
                int n = num != null ? (int)num.Value : 144; Game.SetFpsMode(mode, n); Game.FixOptOut("fps", mode == Core.FpsOrig);
                Status("Сохранено. Применится при следующем запуске игры.", "Saved. Applies on the next game start.");
            }
            catch (Exception ex) { Status(ex.Message, ex.Message); MessageBox.Show(this, ex.Message, T("Режим кадров", "Frame mode")); }
            Reload();
        }
        protected override void Build(Panel body)
        {
            curMode = Game.FpsMode(out curN); bool avail = Game.FpsAvail;
            RPanel c = Card(body, 0, 0, body.Width, body.Height, T("Режим кадров", "Frame mode"), avail ? T("Игра считает 40 шагов в секунду; программа достраивает промежуточные кадры. Нужна обёртка gr-draw — она включится сама.", "The game runs 40 steps per second; the program adds in-between frames. Needs the gr-draw wrapper — it turns on by itself.") : T("Недоступно: нужна div.exe 1.0.0.62", "Unavailable: div.exe 1.0.0.62 is needed"));
            string[] nm = { T("По частоте монитора  ★", "Monitor refresh rate  ★"), T("Без ограничения", "Unlimited"), T("Свой лимит", "Own limit"), T("Как в оригинале (40)", "As in the original (40)") };
            string[] ds = { T("Плавно, без разрывов (верт. синхр.); рекомендуется", "Smooth, no tearing (vsync); recommended"), T("Сотни кадров; возможны разрывы и нагрузка", "Hundreds of FPS; tearing and load are possible"), T("Своё число кадров, без верт. синхронизации", "Your own FPS, no vertical sync"), T("Без плавных кадров, ddraw.ini по умолчанию", "No smooth frames, default ddraw.ini") };
            int[] modes = { Core.FpsMonitor, Core.FpsUnlimited, Core.FpsCustom, Core.FpsOrig }; string[] gl = { "\u25C9", "\u221E", "\u270E", "\u25CB" };
            List<Control> l = new List<Control>(); l.Add(new SecHead(T("Режим", "Mode")));
            for (int i = 0; i < 4; i++)
            {
                int m = modes[i]; Btn b = Act(T("Выбрать", "Choose"), delegate { Choose(m); }); b.Enabled = avail || m == Core.FpsOrig;
                RowCtl r = Row(gl[i], Th.Amber, nm[i], ds[i], b); bool on = curMode == m; r.Status = on ? (m == Core.FpsCustom ? T("выбрано · ", "chosen · ") + curN : T("выбрано", "chosen")) : ""; r.StatusColor = Th.Green; r.Enabled = b.Enabled; if (i == 0) Hr(r, "fps_mode"); l.Add(r);
            }
            l.Add(new SecHead(T("Значение своего лимита", "Value of your own limit")));
            num = Num(1000); num.Minimum = 20; num.Value = Math.Max(20, Math.Min(1000, curN > 0 ? curN : 144));
            l.Add(Row("#", Th.Amber, T("Кадров в секунду", "Frames per second"), T("Любое число от 20 до 1000; потом «Выбрать» у «Свой лимит»", "Any number 20-1000; then press Choose on Own limit"), num));
            Seg pre = Sg(new string[] { "60", "120", "144", "165", "240" }, Math.Max(0, Array.IndexOf(Core.FpsPresets, (int)num.Value)), null); pre.Changed += delegate { num.Value = Core.FpsPresets[pre.Selected]; };
            l.Add(Row("\u2630", Th.Amber, T("Быстрый выбор", "Quick pick"), T("Частые значения: 60, 120, 144, 165, 240", "Common values: 60, 120, 144, 165, 240"), pre));
            Lay(c, 66, l.ToArray());
            Status("Нужна обёртка gr-draw: при выборе режима она включится сама (dgVoodoo уступит место).", "The gr-draw wrapper is needed: it turns on by itself when you pick a mode (dgVoodoo steps aside).");
        }
        protected override void BuildFoot() { FootBtn(T("Закрыть", "Close"), true, 110, delegate { Close(); }); }
    }
}
