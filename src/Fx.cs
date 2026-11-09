// "Effects and FPS": our build of cnc-ddraw (shared/cnc-ddraw/fx, MIT, sources in games/divine-divinity/fx_shader/ddfx_src) replaces the stock ddraw.dll while this is on.
// In the game: F11 = FPS counter, F9 = shaders on/off, F10 = the effects menu (the keys can be changed). Everything is off at the game start by default.
// State lives in the game folder: ddraw.dll (our build), ddraw.dll.stock-cnc (the stock one, comes back when this is turned off), dd-fx.cfg ([current] fx, show_fps; [keys] menu, fps, fx = virtual-key codes), ddraw.ini fx=true.
using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using System.Windows.Forms;
using System.Drawing;

namespace DDFixTool
{
    class FxState { public bool Shaders, Fps; public int KMenu = 121, KFps = 122, KFx = 120; }   // 121 = F10, 122 = F11, 120 = F9

    partial class Core
    {
        string FxCfgPath { get { return P("dd-fx.cfg"); } }
        string FxStockPath { get { return P("ddraw.dll.stock-cnc"); } }
        static bool FileHas(string f, string key)
        {
            try { if (!File.Exists(f)) return false; byte[] b = File.ReadAllBytes(f), k = Encoding.ASCII.GetBytes(key); for (int i = 0; i + k.Length <= b.Length; i++) { int j = 0; while (j < k.Length && b[i + j] == k[j]) j++; if (j == k.Length) return true; } } catch { }
            return false;
        }
        // "Smooth play" in our wrapper: one core, set by the wrapper itself. The profile [div] in the bundled ddraw.ini (made for Die by the Sword, same exe name) says singlecpu=false, so it is set there too.
        public void CncSingleCpu()
        {
            if (!HasGame || !Cnc || !File.Exists(P("ddraw.ini"))) return;
            string v = Launcher ? "true" : "false"; CncSet("singlecpu", v); IniEdit.Set(P("ddraw.ini"), "div", "singlecpu", v);
        }
        public bool FxAvail { get { return HasGame && Cnc; } }
        public FxState FxRead()
        {
            FxState s = new FxState(); if (!FxAvail) return s;
            if (File.Exists(FxCfgPath))
            {
                s.Shaders = IniEdit.Get(FxCfgPath, "current", "fx", "0").Trim() == "1"; s.Fps = IniEdit.Get(FxCfgPath, "current", "show_fps", "0").Trim() == "1";
                int v; if (int.TryParse(IniEdit.Get(FxCfgPath, "keys", "menu", "121"), out v) && v > 0 && v < 255) s.KMenu = v;
                if (int.TryParse(IniEdit.Get(FxCfgPath, "keys", "fps", "122"), out v) && v > 0 && v < 255) s.KFps = v;
                if (int.TryParse(IniEdit.Get(FxCfgPath, "keys", "fx", "120"), out v) && v > 0 && v < 255) s.KFx = v;
            }
            return s;
        }
        // our build of the wrapper is the only one we put in the game folder; "fx=true" in ddraw.ini keeps its hotkeys and FPS counter ready, the effects themselves start off.
        // s = what the game starts with (shaders, FPS) and the hotkeys
        // the wrapper in the game folder is our current build (byte for byte); an older build of ours (install.txt / cnc.inst) is swapped for it, somebody else's is never touched
        bool FxCurrent { get { try { return File.Exists(P("ddraw.dll")) && Net.Sha256File(P("ddraw.dll")) == Net.Sha256Bytes(CncRes("fxddraw.dll")); } catch (IOException) { return false; } } }
        public bool FxNeeded { get { return FxAvail && EmbOurs("grdraw", "ddraw.dll") && (!FxCurrent || CncGet("fx", "false").ToLower() != "true"); } }   // StartupSync
        public void FxApply(FxState s)
        {
            if (!HasGame) throw new InvalidOperationException(U.R("Игра не найдена.", "Game not found."));
            if (!Cnc) throw new InvalidOperationException(U.R("Сначала включите gr-draw на странице «Патчи и фиксы».", "Turn on gr-draw on the Patches page first."));
            if (GameRunning()) throw new InvalidOperationException(L.T("running"));
            if (!FxCurrent)   // a stock cnc-ddraw or an older build of ours put in by this program: swap it for the current build
            {
                if (!EmbOurs("grdraw", "ddraw.dll")) throw new InvalidOperationException(U.R("gr-draw в папке игры установлен не этой программой, поэтому подменять его нельзя. Выключите и включите gr-draw на странице «Патчи и фиксы».", "The gr-draw in the game folder was not installed by this program, so it cannot be swapped. Turn gr-draw off and on again on the Patches page."));
                AtomicWrite(P("ddraw.dll"), CncRes("fxddraw.dll"));
            }
            File.WriteAllBytes(P("ddfx LICENSE-DejaVu.txt"), FxLicBytes()); MarkAdd("ddfx LICENSE-DejaVu.txt"); JNote("grdraw", false);
            // Fresh installs receive the exact owner-approved shader profile. Never overwrite an existing cfg.
            if (!File.Exists(FxCfgPath)) { File.WriteAllBytes(FxCfgPath, Res("ccd_dd-fx.cfg")); MarkAdd("dd-fx.cfg"); }
            IniEdit.Set(FxCfgPath, "current", "fx", s.Shaders ? "1" : "0"); IniEdit.Set(FxCfgPath, "current", "show_fps", s.Fps ? "1" : "0");
            IniEdit.Set(FxCfgPath, "keys", "menu", s.KMenu.ToString()); IniEdit.Set(FxCfgPath, "keys", "fps", s.KFps.ToString()); IniEdit.Set(FxCfgPath, "keys", "fx", s.KFx.ToString());
            CncSet("fx", "true"); CncSingleCpu();
            try { if (File.Exists(FxStockPath)) File.Delete(FxStockPath); } catch { }   // left by 1.0.15
            Sync(); Log(L.T("applied") + "fx shaders=" + s.Shaders + " fps=" + s.Fps + " keys=" + s.KMenu + "," + s.KFps + "," + s.KFx);
        }
        // Quick setup must NOT silently replace a player's own [current] profile.
        // For a legacy skeleton cfg, fill only missing keys from the frozen owner-approved default.
        public void FxStartPreset()
        {
            if (!File.Exists(FxCfgPath)) return;
            string source = Encoding.UTF8.GetString(Res("ccd_dd-fx.cfg"));
            bool inCurrent = false;
            foreach (string raw in source.Split(new char[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries))
            {
                string line = raw.Trim();
                if (line.StartsWith("[", StringComparison.Ordinal))
                {
                    inCurrent = string.Equals(line, "[current]", StringComparison.OrdinalIgnoreCase);
                    continue;
                }
                if (!inCurrent || line.Length == 0 || line[0] == ';') continue;
                int pos = line.IndexOf('=');
                if (pos <= 0) continue;
                string key = line.Substring(0, pos).Trim(), val = line.Substring(pos + 1).Trim();
                if (IniEdit.Get(FxCfgPath, "current", key, null) == null)
                    IniEdit.Set(FxCfgPath, "current", key, val);
            }
        }
        public static string KeyName(int vk) { return ((Keys)vk).ToString(); }
    }

    // press a key to choose it (Esc cancels)
    class KeyPickForm : Form
    {
        public int Vk;
        public KeyPickForm(string what)
        {
            Text = U.R("Клавиша", "Key"); FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false; MinimizeBox = false; ShowInTaskbar = false; StartPosition = FormStartPosition.CenterParent; ClientSize = new Size(380, 120); BackColor = Th.Bg; ForeColor = Th.Text; Font = Th.Body;
            Label l = new Label(); l.AutoSize = false; l.SetBounds(20, 18, 340, 84); l.BackColor = Th.Bg; l.ForeColor = Th.Text; l.UseMnemonic = false; l.TextAlign = ContentAlignment.MiddleCenter; l.Font = Th.F("Segoe UI", 10f, FontStyle.Regular);
            l.Text = what + "\n\n" + U.R("Нажмите нужную клавишу (Esc — отмена)", "Press the key you want (Esc cancels)"); Controls.Add(l);
            KeyPreview = true; KeyDown += delegate(object s, KeyEventArgs e)
            {
                e.Handled = true; e.SuppressKeyPress = true; int k = e.KeyValue;
                if (e.KeyCode == Keys.Escape) { Close(); return; }
                if (k == 16 || k == 17 || k == 18 || k == 91 || k == 92 || k == 13 || k == 32) return;   // modifiers, Enter and Space are used by the game or the effects menu
                Vk = k; Close();
            };
        }
        protected override void OnHandleCreated(EventArgs e) { base.OnHandleCreated(e); Dark.Apply(Handle); }
    }

    class FxForm : ToolForm
    {
        FxState st; int tab;   // tab: 0 = effects and the FPS counter, 1 = FPS mod (tick 80)
        public void SetTab(int t) { tab = t; Reload(); }
        public FxForm(Core c) : base(c, new Size(880, 470)) { }
        protected override string TitleRu { get { return "Эффекты и FPS"; } }
        protected override string TitleEn { get { return "Effects and FPS"; } }
        // every change is written to the game folder at once; the line at the bottom says exactly what was saved (owner 08.11.2026: "I can't tell whether it applied")
        void Save(FxState n, string ru, string en)
        {
            try { Game.FxApply(n); st = n; Done(true, "Сохранено: " + ru, "Saved: " + en); }
            catch (Exception ex) { Done(false, ex.Message, ex.Message); MessageBox.Show(this, ex.Message, T("Эффекты и FPS", "Effects and FPS")); }
            Reload();
        }
        static string Key(int vk) { return Core.KeyName(vk); }
        FxState Copy() { FxState n = new FxState(); n.Shaders = st.Shaders; n.Fps = st.Fps; n.KMenu = st.KMenu; n.KFps = st.KFps; n.KFx = st.KFx; return n; }
        Btn KeyBtn(int vk, string what, Action<FxState, int> set)
        {
            Btn b = Act(Core.KeyName(vk), delegate
            {
                KeyPickForm f = new KeyPickForm(what); f.ShowDialog(this); if (f.Vk == 0) return;
                FxState n = Copy(); set(n, f.Vk);
                if (n.KMenu == n.KFps || n.KMenu == n.KFx || n.KFps == n.KFx) { Status("Эта клавиша уже занята другим действием.", "That key is already used by another action."); return; }
                Save(n, what + " — клавиша " + Key(f.Vk) + ".", what + " — key " + Key(f.Vk) + ".");
            });
            return b;
        }
        protected override void Build(Panel body)
        {
            st = Game.FxRead(); RPanel c = Card(body, 0, 0, body.Width, body.Height, tab == 1 ? T("FPS-мод", "FPS mod") : T("Эффекты и счётчик FPS", "Effects and FPS counter"), tab == 1 ? T("Движение героя, NPC и камеры вдвое чаще; игра не ускоряется", "Hero, NPC and camera move twice as often; the game does not speed up") : Game.FxAvail ? T("Работает вместе с выбранным фильтром масштабирования; в игре всё выключено, пока не нажмёте клавишу", "Works together with the chosen scaling filter; everything is off in the game until you press a key") : T("Нужен gr-draw", "Needs gr-draw"));
            Seg tb = Sg(new string[] { T("Эффекты", "Effects"), T("FPS-мод", "FPS mod") }, tab, null); tb.Under = Th.Surf; tb.Size = new Size(240, 28); tb.Location = new Point(c.Width - 14 - 240, 12);
            tb.Changed += delegate { if (tab != tb.Selected) { tab = tb.Selected; Reload(); } }; c.Controls.Add(tb); tb.BringToFront();
            if (tab == 1) { BuildFps(c); return; }
            if (!Game.FxAvail)
            {
                Lay(c, 66, Row("◇", Th.Faint, "gr-draw", T("Не включён в игре", "Not turned on in the game"), new Label()));
                Label l = new Label(); l.AutoSize = false; l.SetBounds(14, 126, c.Width - 28, 40); l.ForeColor = Th.Muted; l.BackColor = Th.Surf; l.UseMnemonic = false;
                l.Text = T("Включите «gr-draw» на странице «Патчи и фиксы» и откройте это окно снова.", "Turn on “gr-draw” on the Patches page and reopen this window."); c.Controls.Add(l); Status("", ""); return;
            }
            string[] oo = { T("Выкл", "Off"), T("Вкл", "On") };
            Seg sh = Sg(oo, st.Shaders ? 1 : 0, null);
            sh.Changed += delegate { FxState n = Copy(); n.Shaders = sh.Selected == 1; Save(n, n.Shaders ? "шейдеры включатся при следующем запуске игры." : "шейдеры будут выключены при запуске игры (в игре их включает " + Key(n.KFx) + ").", n.Shaders ? "the shaders turn on at the next game start." : "the shaders stay off at the game start (" + Key(n.KFx) + " turns them on in the game)."); };
            Seg fp = Sg(oo, st.Fps ? 1 : 0, null);
            fp.Changed += delegate { FxState n = Copy(); n.Fps = fp.Selected == 1; Save(n, n.Fps ? "счётчик FPS будет виден при следующем запуске игры." : "счётчик FPS будет скрыт при запуске игры (показать — " + Key(n.KFps) + ").", n.Fps ? "the FPS counter shows at the next game start." : "the FPS counter is hidden at the game start (" + Key(n.KFps) + " shows it)."); };
            RowCtl rSh = Row("✦", Th.Amber, T("Шейдеры эффектов", "Effect shaders"), T("Тёплый свет от огней и магии; выкл по умолчанию", "Warm light from fires and magic; off by default"), sh);
            RowCtl rFp = Row("⏱", Th.Amber, T("Счётчик FPS", "FPS counter"), T("Число кадров в секунду в углу экрана", "Frames per second in the corner"), fp);
            OnOff(rSh, st.Shaders); OnOff(rFp, st.Fps);
            Btn kM = KeyBtn(st.KMenu, T("Меню шейдеров", "Shader menu"), delegate(FxState n, int v) { n.KMenu = v; });
            Btn kX = KeyBtn(st.KFx, T("Шейдеры: включить / выключить", "Shaders: on / off"), delegate(FxState n, int v) { n.KFx = v; });
            Btn kF = KeyBtn(st.KFps, T("Счётчик FPS: показать / скрыть", "FPS counter: show / hide"), delegate(FxState n, int v) { n.KFps = v; });
            Lay(c, 66,
                new SecHead(T("При запуске игры", "When the game starts")),
                rSh, rFp,
                new SecHead(T("Клавиши в игре (нажмите кнопку и затем новую клавишу)", "In-game keys (press the button, then the new key)")),
                Row("⌨", Th.Amber, T("Меню шейдеров", "Shader menu"), T("Настройка эффектов прямо в игре", "Tune the effects in the game"), kM),
                Row("⌨", Th.Amber, T("Шейдеры вкл / выкл", "Shaders on / off"), T("Сравнить картинку «до» и «после»", "Compare before and after"), kX),
                Row("⌨", Th.Amber, T("Счётчик FPS", "FPS counter"), T("Показать или скрыть счётчик", "Show or hide the counter"), kF));
            Status("Всё сохраняется сразу и действует со следующего запуска игры. Клавиши по умолчанию: F9, F10, F11.", "Everything is saved at once and works from the next game start. Default keys: F9, F10, F11.");
        }
        // the status column of a row: what the game starts with, as a coloured word
        void OnOff(RowCtl r, bool on) { r.Status = on ? T("включено", "on") : T("выключено", "off"); r.StatusColor = on ? Th.Green : Th.Faint; }
        // tab 2: the FPS mod = our "tick 80" exe patch (Core.SetFps80, src/Tick80.cs): the world still runs 40 steps a second, what is SHOWN moves 80 times a second
        void BuildFps(RPanel c)
        {
            bool av = Game.Fps80Avail; string s = Game.Fps80State(); string[] oo = { T("Выкл", "Off"), T("Вкл", "On") };
            Seg sw = Sg(oo, s == "on" ? 1 : 0, null); sw.Enabled = av;
            sw.Changed += delegate
            {
                bool on = sw.Selected == 1;
                try { Game.SetFps80(on); Done(true, on ? "Сохранено: FPS-мод включён, заработает при следующем запуске игры." : "Сохранено: FPS-мод выключен, файл игры возвращён к исходному.", on ? "Saved: the FPS mod is on and works from the next game start." : "Saved: the FPS mod is off, the game file is back to the original."); }
                catch (Exception ex) { Done(false, ex.Message, ex.Message); MessageBox.Show(this, ex.Message, T("FPS-мод", "FPS mod")); }
                Reload();
            };
            string d = !av ? T("Недоступно для вашей версии игры", "Not available for your game version") : (s == "on" ? T("Включён: 80 кадров движения в секунду", "On: 80 frames of motion a second") : T("Выключен: 40 кадров, как в оригинале", "Off: 40 frames, as in the original"));
            RowCtl rf = Hr(Row("⏱", av ? Th.Amber : Th.Faint, T("FPS-мод", "FPS mod"), d, sw), "fps80"); if (av) OnOff(rf, s == "on");
            int y = Lay(c, 66, new SecHead(T("Такт 80 Гц", "80 Hz tick")), rf);
            Label l = new Label(); l.AutoSize = false; l.SetBounds(14, y + 6, c.Width - 28, 150); l.ForeColor = Th.Muted; l.BackColor = Th.Surf; l.UseMnemonic = false; l.Font = Th.F("Segoe UI", 9f, FontStyle.Regular);
            l.Text = T("FPS-мод убирает рывки при движении героя, NPC и камеры на быстрых мониторах, в том числе с VA-матрицей. Движение отображается 80 раз в секунду, а ИИ, бой и скорость остаются прежними: игра не ускоряется.\n\nВключайте при закрытой игре. Выключение возвращает файл игры к исходному.\n\nЕсли нужно, программа сама подключит gr-draw: без него частота кадров упирается в 60.",
                "The FPS mod removes stutter when the hero, NPCs and camera move on high refresh rate monitors, including VA panels. Movement is displayed 80 times a second, while AI, combat and game speed stay the same: the game does not speed up.\n\nTurn it on with the game closed. Turning it off brings the game file back to the original.\n\nIf needed the program turns on gr-draw itself: without it the frame rate stops at 60.");
            c.Controls.Add(l);
            Status(av ? "Сохраняется сразу при переключении и действует со следующего запуска игры." : "Недоступно: нужна поддерживаемая версия div.exe.", av ? "Saved at once when switched; works from the next game start." : "Not available: a supported div.exe is needed.");
        }
        protected override void BuildFoot()
        {
            FootBtn(T("Закрыть", "Close"), true, 110, delegate { Close(); });
            if (tab == 0) FootBtn(T("Клавиши по умолчанию", "Default keys"), false, 190, delegate { if (!Game.FxAvail) return; FxState n = Copy(); n.KMenu = 121; n.KFps = 122; n.KFx = 120; Save(n, "клавиши по умолчанию F9, F10, F11.", "default keys F9, F10, F11."); });
        }
    }
}
