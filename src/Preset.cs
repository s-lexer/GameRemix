// Quick setup (presets by monitor), help windows for the graphics wrappers, game resolution helpers.
using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Text.RegularExpressions;
using System.Windows.Forms;

namespace DDFixTool
{
    partial class Core
    {
        // monitor class -> {game width, game height, dgVoodoo scale, anti-aliasing, font step (0 original / 1 larger)}
        // 4K runs the game at 1920x1080 and lets dgVoodoo scale x2 (exactly 3840x2160, UI stays large); 2K and HD run at the monitor's native size.
        // HD uses dgVoodoo Resolution=2x on purpose: the game is rendered at 3840x2160 and shrunk to the 1080p screen (SUPERSAMPLING: smoother edges, heavier for the GPU).
        // The summary says so, and the graphics window offers 1x for weak cards.
        public static readonly string[] PresetNames = { "HD (1920×1080)", "2K (2560×1440)", "4K (3840×2160)" };
        static readonly int[][] PresetData = { new int[] { 1920, 1080, 2, 4, 0 }, new int[] { 2560, 1440, 1, 4, 1 }, new int[] { 1920, 1080, 2, 2, 1 } };
        static readonly string[] PresetFiles = { "config.div", "slashed-d3d6.cfg", "slashed-software.cfg", "slashed.cfg" };
        string PresetDir { get { return Path.Combine(GameData, "preset"); } }
        string PresetTx { get { return Path.Combine(GameData, "preset_tx"); } }   // snapshot for rolling back a half-applied preset

        // the wizard's default for the fonts: larger from 2K up (the game then runs at a height of 1200+)
        public static bool PresetLargeFonts(int k, ScalePlan plan) { return k >= 1 || (plan != null && plan.Game.Height >= 1200); }
        public static int PresetForScreen(int w) { return w >= 3000 ? 2 : (w >= 2400 ? 1 : 0); }

        // the REAL pixel size of a monitor (not the DPI-virtualised one) via its current display mode
        [System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential, CharSet = System.Runtime.InteropServices.CharSet.Unicode)]
        struct DEVMODE
        {
            [System.Runtime.InteropServices.MarshalAs(System.Runtime.InteropServices.UnmanagedType.ByValTStr, SizeConst = 32)] public string dmDeviceName;
            public short dmSpecVersion, dmDriverVersion, dmSize, dmDriverExtra; public int dmFields; public int dmPositionX, dmPositionY, dmDisplayOrientation, dmDisplayFixedOutput;
            public short dmColor, dmDuplex, dmYResolution, dmTTOption, dmCollate;
            [System.Runtime.InteropServices.MarshalAs(System.Runtime.InteropServices.UnmanagedType.ByValTStr, SizeConst = 32)] public string dmFormName;
            public short dmLogPixels; public int dmBitsPerPel, dmPelsWidth, dmPelsHeight, dmDisplayFlags, dmDisplayFrequency, dmICMMethod, dmICMIntent, dmMediaType, dmDitherType, dmReserved1, dmReserved2, dmPanningWidth, dmPanningHeight;
        }
        [System.Runtime.InteropServices.DllImport("user32.dll", CharSet = System.Runtime.InteropServices.CharSet.Unicode)] static extern bool EnumDisplaySettings(string dev, int mode, ref DEVMODE dm);
        public static Size ScreenPixels(Screen sc)
        {
            try
            {
                DEVMODE dm = new DEVMODE(); dm.dmSize = (short)System.Runtime.InteropServices.Marshal.SizeOf(typeof(DEVMODE));
                if (EnumDisplaySettings(sc.DeviceName, -1, ref dm) && dm.dmPelsWidth > 0 && dm.dmPelsHeight > 0) return new Size(dm.dmPelsWidth, dm.dmPelsHeight);
            }
            catch { }
            return sc.Bounds.Size;
        }

        public string PresetSummary(int k, bool cnc) { return PresetSummary(k, cnc, null); }
        public string PresetSummary(int k, bool cnc, ScalePlan plan)
        {
            int[] d = PresetData[k]; bool ru = L.Ru; if (!cnc) plan = null;
            if (plan != null) { d = (int[])d.Clone(); d[0] = plan.Game.Width; d[1] = plan.Game.Height; d[4] = plan.Game.Height >= 1200 ? 1 : 0; }
            string up = plan != null ? "" : k == 2 ? (ru ? " (картинку растянет ×2 до 4K)" : " (the picture is scaled ×2 to 4K)") : "";
            string render = (d[0] * d[2]) + "×" + (d[1] * d[2]), ss = k != 2 && d[2] > 1 ? (ru ? ", суперсэмплинг: рисуется крупнее и сжимается до экрана — чётче, но тяжелее для видеокарты" : ", supersampling: drawn larger and shrunk to the screen — smoother, heavier for the GPU") : "";
            string gfx = cnc ? (ru ? "gr-draw: окно без рамки, мягкое масштабирование (OpenGL), пропорции сохраняются, верт. синхронизация; игра переводится в режим Software; настройки gr-draw начинаются с умолчаний" : "gr-draw: borderless window, soft scaling (OpenGL), aspect kept, vertical sync; the game is switched to Software mode; gr-draw settings start from defaults")
                                 : (ru ? "dgVoodoo: масштаб " + d[2] + "x (рендер " + render + ss + "), сглаживание " + d[3] + "x, верт. синхронизация (gr-draw выключается)" : "dgVoodoo: scale " + d[2] + "x (render " + render + ss + "), anti-aliasing " + d[3] + "x, vertical sync (gr-draw is turned off)");
            bool sup = HasGame ? ExeSupported : true;
            string snd = sup ? (ru ? "Звук, закат и рассвет: включены; плавная работа: включена" : "Voice and dusk fixes: on; smooth play: on")
                             : (ru ? "Звук, закат и рассвет: ПРОПУЩЕНО — версия игры не поддерживается (нужна 1.0.0.62); плавная работа: включена" : "Voice and dusk fixes: SKIPPED — the game version is not supported (1.0.0.62 needed); smooth play: on");
            string fw = FontWarn((plan != null ? d[4] : PresetData[k][4]) == 1 ? FontLarge : 0);
            string sc = plan != null ? UiScale.Summary(plan, ru) + (plan.Notes.Count > 0 ? "\n" + UiScale.Warnings(plan, ru) : "") + "\n" : "";
            return sc.Length > 0 ? sc + gfx + "\n" + snd + "\n" + (ru ? "Шрифты: " + (d[4] == 1 ? "крупнее" : "оригинал") : "Fonts: " + (d[4] == 1 ? "larger" : "original")) + (fw.Length > 0 ? "\n" + fw : "")
                      : ru ? "Игра: " + d[0] + "×" + d[1] + up + "\n" + gfx + "\n" + snd + "\nШрифты: " + (d[4] == 1 ? "крупнее" : "оригинал") + (fw.Length > 0 ? "\n" + fw : "") + "\nЯрлык «со всеми фиксами»: создаётся"
                      : "Game: " + d[0] + "×" + d[1] + up + "\n" + gfx + "\n" + snd + "\nFonts: " + (d[4] == 1 ? "larger" : "original") + (fw.Length > 0 ? "\n" + fw : "") + "\n\"With all fixes\" shortcut: created";
        }
        // the "larger" font step in this language - the same one the Fonts window offers (RU 3, EN 1), so every screen shows the same choice
        public static int FontLarge { get { return L.Ru ? 3 : 1; } }
        // the preset resets every font group: say so when the player chose something else by hand
        string FontWarn(int step)
        {
            try
            {
                if (!HasGame || !FontsAvail) return "";
                for (int c = 0; c < 3; c++) { int st = FontStep(c); if ((st > 0 && st != step) || FontIsCustom(c)) return U.R("Внимание: шрифты, выбранные вручную, будут заменены (свои файлы сохраняются в резервную копию).", "Note: fonts you chose by hand will be replaced (your own files are kept in the backup)."); }
            }
            catch { }
            return "";
        }

        // sets a key of [DirectX] in dgVoodoo.conf; keeps the user's original conf (first edit) and the file's encoding / line endings; adds the key when absent
        public void DgvSet(string key, string val)
        {
            string f = P("dgVoodoo.conf"); if (!File.Exists(f)) throw new FileNotFoundException(U.R("Нет файла dgVoodoo.conf в папке игры.", "dgVoodoo.conf is missing in the game folder."));
            BackupDgvConf(); IniEdit.Set(f, "DirectX", key, val);
        }
        static void CopyOver(string src, string dst)
        {
            try { File.Copy(src, dst, true); }
            catch (UnauthorizedAccessException) { if (File.Exists(dst)) File.SetAttributes(dst, FileAttributes.Normal); File.Copy(src, dst, true); }
        }
        static void CopyIfExists(string src, string dst) { if (File.Exists(src)) { Directory.CreateDirectory(Path.GetDirectoryName(dst)); File.Copy(src, dst, true); } }

        // returns the list of things that were skipped (shown to the user); on any failure the already applied steps are undone and the exception is thrown
        public List<string> ApplyPreset(int k, bool cnc) { return ApplyPreset(k, cnc, null); }
        // plan != null (cnc-ddraw only): the game runs at plan.Game and cnc-ddraw stretches the frame to the monitor (see Scale.cs); null = the class's own size
        public List<string> ApplyPreset(int k, bool cnc, ScalePlan plan)
        {
            if (!HasGame) throw new InvalidOperationException(U.R("Игра не найдена.", "Game not found."));
            if (k < 0 || k >= PresetData.Length) throw new ArgumentOutOfRangeException("k");
            int[] d = (int[])PresetData[k].Clone(); List<string> skipped = new List<string>(); if (!cnc) plan = null;
            if (plan != null) { d[0] = plan.Game.Width; d[1] = plan.Game.Height; d[4] = plan.Game.Height >= 1200 ? 1 : 0; }
            // 1. the originals "Revert all" must bring back - taken BEFORE anything is switched. While cnc-ddraw owns the renderer, the true slashed.cfg is its saved copy.
            PresetBackupOriginals();
            if (cnc && !File.Exists(Path.Combine(PresetDir, "cnc_saved.ini")) && !File.Exists(Path.Combine(PresetDir, "cnc_saved.none")))
            { if (File.Exists(CncSaved)) File.Copy(CncSaved, Path.Combine(PresetDir, "cnc_saved.ini")); else File.WriteAllText(Path.Combine(PresetDir, "cnc_saved.none"), "1"); }
            // 2. a snapshot of everything the steps below edit + the switches, for the rollback
            if (Directory.Exists(PresetTx)) Directory.Delete(PresetTx, true);
            Directory.CreateDirectory(PresetTx);
            foreach (string f in new string[] { "config.div", "slashed-d3d6.cfg", "slashed-software.cfg", "slashed.cfg", "dgVoodoo.conf", "ddraw.ini" }) CopyIfExists(P(f), Path.Combine(PresetTx, f));
            CopyIfExists(CncSaved, Path.Combine(PresetTx, "cnc_saved.ini"));
            string[] inst0 = File.Exists(DgvInst) ? File.ReadAllLines(DgvInst) : new string[0];
            bool sup = ExeSupported, v0 = sup && VoiceOn, d0 = sup && DuskOn, dgv0 = Dgv, cnc0 = Cnc, l0 = Launcher, s0 = ShortcutExists; int[] f0 = new int[3]; for (int c = 0; c < 3; c++) f0[c] = FontsAvail ? FontStep(c) : -1;
            try
            {
                if (!cnc && Cnc) SetCnc(false);   // gives the renderer choice back (slashed.cfg) before we set our own
                WriteResolution(d[0], d[1]);
                string sc = P("slashed.cfg"); if (!cnc && File.Exists(sc) && File.Exists(P("slash1.dll"))) File.WriteAllBytes(sc, new byte[] { 0, 0, 0, 0 });   // renderer: Direct3D 6
                if (sup) { if (VoiceUseful) SetVoice(true); SetDusk(true); } else skipped.Add(U.R("озвучка, закат и рассвет — версия игры не поддерживается", "voice, dusk and dawn — the game version is not supported"));
                if (cnc)
                {
                    if (!Cnc) { if (File.Exists(CncSaved)) File.Delete(CncSaved); }   // a fresh start from the bundled defaults, not from whatever was left from earlier use
                    else if (File.Exists(CncMark) && File.ReadAllText(CncMark).Contains("ddraw.ini") && File.Exists(P("ddraw.ini"))) File.WriteAllBytes(P("ddraw.ini"), CncRes("ddraw.ini"));
                    SetCnc(true);   // also switches the game to Software and turns dgVoodoo off
                    CncSet("windowed", "true"); CncSet("fullscreen", "true"); CncSet("maintas", "true"); CncSet("vsync", "true"); CncSet("maxfps", "-1");
                    CncSet("shader", "Shaders\\interpolation\\catmull-rom-bilinear.glsl"); CncSet("renderer", "opengl");
                    if (FileHas(P("ddraw.dll"), "dd-fx.cfg")) CncSet("fx", "true");   // our effects build stays on after the ini was rewritten
                    if (plan != null) WriteCncScale(plan);
                }
                else
                {
                    SetDgv(true, true);
                    DgvSet("Resolution", d[2] + "x"); DgvSet("Antialiasing", d[3] + "x"); DgvSet("ForceVerticalSync", "true");
                }
                SetLauncher(true);
                if (FontsAvail) for (int c = 0; c < 3; c++) if (FontStep(c) >= 0) SetFontStep(c, d[4] == 1 ? FontLarge : 0);
                CreateShortcut();
                if (plan != null) ScaleSave(plan); else if (File.Exists(ScaleFile)) File.Delete(ScaleFile);
            }
            catch (Exception ex)
            {
                List<string> undo = new List<string>();
                Log("preset failed, rolling back: " + ex.Message);
                try { if (Cnc != cnc0) SetCnc(cnc0); } catch (Exception e2) { undo.Add("gr-draw: " + e2.Message); }
                try { if (!cnc0) DgvUndoSince(inst0, dgv0); else if (Dgv) SetDgv(false, false); } catch (Exception e2) { undo.Add("dgVoodoo: " + e2.Message); }
                try { if (sup) { if (VoiceOn != v0) SetVoice(v0); if (DuskOn != d0) SetDusk(d0); } } catch (Exception e2) { undo.Add("voice/dusk: " + e2.Message); }
                try { if (Launcher != l0) SetLauncher(l0); } catch (Exception e2) { undo.Add("smooth: " + e2.Message); }
                try { for (int c = 0; c < 3; c++) if (f0[c] >= 0 && FontStep(c) != f0[c]) SetFontStep(c, f0[c]); } catch (Exception e2) { undo.Add("fonts: " + e2.Message); }
                foreach (string f in new string[] { "config.div", "slashed-d3d6.cfg", "slashed-software.cfg", "slashed.cfg", "dgVoodoo.conf", "ddraw.ini" })
                {
                    try
                    {
                        string snap = Path.Combine(PresetTx, f);
                        if (!File.Exists(snap)) continue;
                        if (f == "slashed.cfg" && Cnc) continue;   // cnc owns it right now
                        CopyOver(snap, P(f));
                    }
                    catch (Exception e2) { undo.Add(f + ": " + e2.Message); }
                }
                try { if (File.Exists(Path.Combine(PresetTx, "cnc_saved.ini"))) CopyOver(Path.Combine(PresetTx, "cnc_saved.ini"), CncSaved); } catch { }
                try { if (!s0 && ShortcutExists) RemoveShortcut(); } catch { }
                if (undo.Count == 0) { try { Directory.Delete(PresetTx, true); } catch { } }
                throw new InvalidOperationException((U.R("Быстрая настройка не завершена: ", "Quick setup did not finish: ")) + ex.Message + (undo.Count == 0 ? (U.R("\nУже сделанное отменено.", "\nWhat was already done has been undone.")) : (U.R("\nОтменить удалось не всё: ", "\nNot everything could be undone: ")) + string.Join("; ", undo.ToArray())), ex);
            }
            try { Directory.Delete(PresetTx, true); } catch { }
            foreach (string oid in new string[] { "voice", "dusk", "smooth" }) FixOptOut(oid, false);
            try { foreach (string x in ApplyDefaultFixes(true, false)) skipped.Add(x); } catch (Exception dx) { skipped.Add(dx.Message); }   // small fixes on by default; a failure here does not undo the preset
            Log(L.T("applied") + "preset " + PresetNames[k] + (cnc ? " gr-draw" : " dgVoodoo") + (plan != null ? " scale " + UiScale.Summary(plan, false) : "") + (skipped.Count > 0 ? " (skipped: " + string.Join("; ", skipped.ToArray()) + ")" : ""));
            return skipped;
        }
        // "Revert all": every step in its own try - a failure never stops the others; returns the failures (empty = everything went back)
        public List<string> RevertAll()
        {
            List<string> fails = new List<string>();
            Action<string, Action> step = delegate(string name, Action act) { try { act(); } catch (Exception ex) { Log("revert [" + name + "]: " + ex.Message); fails.Add(name + ": " + ex.Message); } };
            step(U.R("FPS-мод (такт 80)", "FPS mod (tick 80)"), delegate { string t8 = Fps80State(); if (t8 == "on" || t8 == "mixed" || File.Exists(Fps80File)) SetFps80(false); });
            step(U.R("частота кадров", "frame rate"), delegate { if (BytePatchState("interp") == "on" || BytePatchState("interp") == "mixed") SetFpsMode(FpsOrig, 0); });
            step(U.R("озвучка", "voice"), delegate { SetVoice(false); });   // on an unsupported div.exe this only takes our DLLs out
            step(U.R("закат и рассвет", "dusk"), delegate { SetDusk(false); });
            step("Lar's Bone", delegate { SetBone(false); });
            step(U.R("графическая обёртка", "graphics wrapper"), delegate { RevertDgv(); });
            step(U.R("быстрая настройка", "quick setup"), delegate { RevertPreset(); });
            step(U.R("плавная работа", "smooth play"), delegate { SetLauncher(false); });
            step(U.R("ярлык", "shortcut"), delegate { RemoveShortcut(); });
            step(U.R("корейский язык", "Korean language"), delegate { if (JGet("korean") != null || BytePatchState("korean") == "on") SetKorean(false); });
            step(U.R("шрифты", "fonts"), delegate { RevertFonts(); });
            step(U.R("улучшенная графика", "enhanced graphics"), delegate { RevertAssets(); });
            step(U.R("исправления игры", "game fixes"), delegate { RevertGfxFixes(); });
            step("div.exe", delegate { if (ExeSupported) ExeReset(); });   // whatever state the exe was in: the verified original (src/Install.cs)
            foreach (string oid in new string[] { "voice", "dusk", "smooth", "fps" }) FixOptOut(oid, true);   // "Revert all" is the player's decision: the defaults do not come back by themselves
            return fails;
        }
        // brings the originals back; the backup folder is deleted ONLY when every file went back, otherwise it stays (it holds the only copies) and an error is raised
        public void RevertPreset()
        {
            if (!Directory.Exists(PresetDir)) return;
            List<string> fail = new List<string>();
            foreach (string f in Directory.GetFiles(PresetDir))
            {
                string name = Path.GetFileName(f); if (name == "cnc_saved.ini" || name == "cnc_saved.none" || name == PresetIniName) continue;
                try
                {
                    if (name == "slashed.cfg" && Cnc) CopyOver(f, CncRenderPrev);   // cnc-ddraw owns the renderer now: its own revert will put this one back
                    else CopyOver(f, P(name));
                }
                catch (Exception ex) { fail.Add(name + ": " + ex.Message); }
            }
            try { string pre = Path.Combine(PresetDir, PresetIniName); if (File.Exists(pre) && Cnc && File.Exists(P("ddraw.ini"))) CopyOver(pre, P("ddraw.ini")); }   // cnc-ddraw stayed on: its ini as it was before
            catch (Exception ex) { fail.Add("ddraw.ini: " + ex.Message); }
            try
            {
                string ci = Path.Combine(PresetDir, "cnc_saved.ini"), cn = Path.Combine(PresetDir, "cnc_saved.none");
                if (File.Exists(ci)) { Directory.CreateDirectory(Path.GetDirectoryName(CncSaved)); CopyOver(ci, CncSaved); }
                else if (File.Exists(cn) && File.Exists(CncSaved)) File.Delete(CncSaved);
            }
            catch (Exception ex) { fail.Add("cnc settings: " + ex.Message); }
            if (fail.Count > 0)
                throw new IOException((U.R("Не все файлы вернулись (занят игрой или антивирусом?). Резервные копии сохранены в ", "Not every file could be restored (busy? antivirus?). The backups are kept in ")) + PresetDir + ":\n" + string.Join("\n", fail.ToArray()));
            Directory.Delete(PresetDir, true); try { if (File.Exists(ScaleFile)) File.Delete(ScaleFile); FilterAuto = false; } catch { } Log(L.T("reverted") + "preset");
        }
    }

    // short explanation of a graphics wrapper: what it is, pros, cons, when to pick it
    class HelpForm : Form
    {
        RichTextBox rt = new RichTextBox();
        void Add(string t, Color c, bool bold, float pt) { rt.SelectionStart = rt.TextLength; rt.SelectionLength = 0; rt.SelectionColor = c; rt.SelectionFont = Th.F("Segoe UI", pt, bold ? FontStyle.Bold : FontStyle.Regular); rt.SelectedText = t; }
        public HelpForm(bool cnc)
        {
            Text = cnc ? "gr-draw" : "dgVoodoo"; FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false; MinimizeBox = false; ShowInTaskbar = false;
            StartPosition = FormStartPosition.CenterParent; ClientSize = new Size(520, 460); BackColor = Th.Bg; ForeColor = Th.Text; Font = Th.Body;
            rt.BorderStyle = BorderStyle.None; rt.BackColor = Th.Surf; rt.ForeColor = Th.Text; rt.ReadOnly = true; rt.ScrollBars = RichTextBoxScrollBars.None; rt.DetectUrls = false; rt.Cursor = Cursors.Default; rt.SetBounds(24, 20, 472, 370); rt.Font = Th.F("Segoe UI", 10f, FontStyle.Regular);
            Add(cnc ? "gr-draw\n" : "dgVoodoo\n", Th.Text, true, 15f);
            Add(cnc ? U.R("Лёгкая обёртка только для DirectDraw (2D). Игра при этом идёт в режиме «Software» — программная отрисовка.\n\n", "A light wrapper for DirectDraw (2D) only. The game then runs in its \"Software\" mode — software rendering.\n\n")
                    : U.R("Подменяет DirectDraw и Direct3D игры современными средствами Windows. Игра идёт в своём штатном режиме Direct3D 6, как задумано, но на новых Windows.\n\n", "Replaces the game's DirectDraw and Direct3D with modern Windows rendering. The game runs in its normal Direct3D 6 mode, as intended, on new Windows.\n\n"), Th.Muted, false, 10f);
            Add(U.R("Плюсы\n", "Pros\n"), Th.Green, true, 10f);
            Add(cnc ? U.R("• картинка лучше: мягкое масштабирование шейдерами (чётко, плавно, мягко, FSR)\n• окно без рамки и оконный режим\n• лимит кадров, быстрый Alt+Tab, фиксы мыши\n• работает с многими другими 2D-играми\n\n", "• better picture: soft shader scaling (sharp, smooth, soft, FSR)\n• borderless and windowed mode\n• frame limiter, fast Alt+Tab, mouse fixes\n• works with many other 2D games\n\n")
                    : U.R("• аппаратное ускорение, сглаживание MSAA, масштаб\n• стабильно на Windows 10/11\n• режим игры не меняется, всё как в оригинале\n\n", "• hardware acceleration, MSAA, render scale\n• stable on Windows 10/11\n• the game's mode is unchanged, just like the original\n\n"), Th.Text, false, 10f);
            Add(U.R("Минусы\n", "Cons\n"), Th.Amber, true, 10f);
            Add(cnc ? U.R("• нет Direct3D: игра переводится в режим Software\n• ползунок гаммы в настройках игры не работает\n• выше нагрузка на процессор\n\n", "• no Direct3D: the game is switched to Software mode\n• the game's gamma slider does not work\n• higher CPU load\n\n")
                    : U.R("• нет окна без рамки: игра в полном экране\n• нет шейдеров-апскейлеров\n• Alt+Tab иногда медленный\n\n", "• no borderless window: the game is fullscreen\n• no upscaling shaders\n• Alt+Tab can be slow\n\n"), Th.Text, false, 10f);
            Add(U.R("Когда выбирать\n", "When to pick it\n"), Th.Amber, true, 10f);
            Add(cnc ? U.R("★ Рекомендуется по умолчанию: лучшая картинка, окно без рамки, шейдеры.", "★ Recommended by default: better picture, borderless window, shaders.") : U.R("Если gr-draw не подошёл или нужны аппаратное ускорение и сглаживание MSAA.", "If gr-draw does not suit you, or you want hardware acceleration and MSAA."), Th.Text, false, 10f);
            Add("\n\n" + U.R("Вместе они работать не могут: оба подменяют ddraw.dll. Включение одного само отключает другое.", "They cannot work together: both replace ddraw.dll. Turning one on turns the other off."), Th.Faint, false, 9f);
            Btn cl = new Btn(); cl.Text = U.R("Понятно", "Got it"); cl.Accent = true; cl.SetBounds(24, 404, 472, 40); cl.Click += delegate { Close(); };
            Controls.AddRange(new Control[] { rt, cl }); KeyPreview = true; KeyDown += delegate(object s, KeyEventArgs e) { if (e.KeyCode == Keys.Escape) Close(); };
            rt.SelectionStart = 0; rt.SelectionLength = 0; ActiveControl = cl;
        }
        protected override void OnHandleCreated(EventArgs e) { base.OnHandleCreated(e); Dark.Apply(Handle); }
    }
}
