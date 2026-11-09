// cnc-ddraw (FunkyFr3sh, MIT, https://github.com/FunkyFr3sh/cnc-ddraw): alternative DirectDraw wrapper (GDI / OpenGL / Direct3D 9, borderless, shaders).
// It is a drop-in "ddraw.dll" in the game folder, exactly like dgVoodoo's DDraw.dll, so the two can NEVER be on together: turning one on turns the other off.
using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Text;
using System.Text.RegularExpressions;
using System.Drawing;
using System.Windows.Forms;

namespace DDFixTool
{
    partial class Core
    {
        string CncMark { get { return Path.Combine(BakDir, "cnc.inst"); } }                      // files we put into the game folder (relative paths)
        string CncSaved { get { return Path.Combine(GameData, @"cnc\ddraw.ini"); } }           // user settings kept while cnc-ddraw is off
        string CncRenderPrev { get { return Path.Combine(GameData, @"cnc\slashed.prev"); } }    // the game's renderer choice before we switched it to Software
        string CncOther { get { return P("ddraw.dll.ogfbak"); } }                                  // some other ddraw.dll that was in the way
        static byte[] CncRes(string n)
        {
            using (MemoryStream gz = new MemoryStream(Res("ccd_" + n)))
            using (GZipStream z = new GZipStream(gz, CompressionMode.Decompress))
            using (MemoryStream ms = new MemoryStream()) { byte[] buf = new byte[65536]; int k; while ((k = z.Read(buf, 0, buf.Length)) > 0) ms.Write(buf, 0, k); return ms.ToArray(); }
        }
        static bool IsCncDll(string f) { try { return IsCncDllStrict(f); } catch { return false; } }
        static bool IsCncDllStrict(string f)   // throws when the file cannot be read (locked)
        {
            {
                if (!File.Exists(f)) return false; byte[] b = File.ReadAllBytes(f), key = Encoding.ASCII.GetBytes("cnc-ddraw");
                for (int i = 0; i + key.Length <= b.Length; i++) { int j = 0; while (j < key.Length && b[i + j] == key[j]) j++; if (j == key.Length) return true; }
            }
            return false;
        }
        public bool Cnc { get { return HasGame && IsCncDll(P("ddraw.dll")); } }
        public bool CncAvail { get { return HasGame; } }

        // cnc.inst = what we put into the game folder, one relative path per line; lines starting with "@" are notes ("@moved=<file>": the other ddraw.dll we parked as *.ogfbak)
        string CncIniUser { get { return Path.Combine(BakDir, "ddraw.ini.user"); } }   // the user's own ddraw.ini as it was before our first edit
        void WriteMark(List<string> made, string moved)
        {
            List<string> l = new List<string>(made); if (moved != null) l.Add("@moved=" + moved);
            Directory.CreateDirectory(BakDir); File.WriteAllLines(CncMark, l.ToArray());
        }
        void ReadMark(out List<string> made, out string moved)
        {
            made = new List<string>(); moved = null; if (!File.Exists(CncMark)) return;
            foreach (string ln in File.ReadAllLines(CncMark)) { string t = ln.Trim(); if (t.Length == 0) continue; if (t.StartsWith("@moved=")) moved = t.Substring(7); else if (!t.StartsWith("@")) made.Add(t); }
        }
        void MarkAdd(string name) { if (!File.Exists(CncMark)) return; List<string> made; string moved; ReadMark(out made, out moved); if (!made.Contains(name)) { made.Add(name); WriteMark(made, moved); } }

        public void SetCnc(bool on)
        {
            if (on) CncOn(); else CncOff();
            Sync();
        }
        // switching ON is all-or-nothing: whatever fails half-way, the game folder, the renderer choice and dgVoodoo go back to what they were
        void CncOn()
        {
            if (Cnc) return;   // already on (ours, or the user's own cnc-ddraw which we never touch)
            bool dgvWas = Dgv, dgvMark = File.Exists(DgvMark); List<string> made = new List<string>(); string moved = null;
            try
            {
                if (dgvWas) SetDgv(false, false);   // both replace ddraw.dll: dgVoodoo steps aside (its files are only renamed *.dgvoff, nothing is lost)
                Directory.CreateDirectory(BakDir);
                if (File.Exists(P("ddraw.dll")) && !Cnc)   // some other ddraw.dll is in the way: park it under a name that never overwrites anything
                {
                    string n = "ddraw.dll.ogfbak"; for (int i = 2; File.Exists(P(n)); i++) n = "ddraw.dll.ogfbak" + i;
                    File.Move(P("ddraw.dll"), P(n)); moved = n; WriteMark(made, moved);
                }
                WriteMark(made, moved);   // from here on the mark exists: a crash leaves something Revert can undo
                File.WriteAllBytes(P("ddraw.dll"), CncRes("fxddraw.dll")); made.Add("ddraw.dll"); WriteMark(made, moved);   // ONE build of the wrapper: ours (a stock cnc-ddraw 7.1 until "fx" is turned on in ddraw.ini)
                File.WriteAllBytes(P("ddfx LICENSE-DejaVu.txt"), FxLicBytes()); made.Add("ddfx LICENSE-DejaVu.txt");
                if (!File.Exists(P("ddraw.ini")))
                {
                    if (File.Exists(CncSaved)) File.Copy(CncSaved, P("ddraw.ini")); else File.WriteAllBytes(P("ddraw.ini"), CncRes("ddraw.ini"));
                    made.Add("ddraw.ini"); WriteMark(made, moved);
                    if (!File.Exists(CncSaved)) { CncSet("windowed", "true"); CncSet("fullscreen", "true"); CncSet("maintas", "true"); }   // first start: borderless full screen, proportions kept
                }
                else BackupCncIni();   // an ini of the user's own: we may edit it, so keep their version
                foreach (KeyValuePair<string, byte[]> sh in CncShaders())   // a shader the player already has stays his (not in the mark, never refreshed)
                {
                    string dst = P(sh.Key); if (!File.Exists(dst)) { Directory.CreateDirectory(Path.GetDirectoryName(dst)); File.WriteAllBytes(dst, sh.Value); made.Add(sh.Key); }
                }
                File.WriteAllBytes(P("cnc-ddraw LICENSE.txt"), CncLicBytes()); made.Add("cnc-ddraw LICENSE.txt");
                WriteMark(made, moved); JNote("grdraw", false);
                CncSingleCpu();
                CncSet("fx", "true");   // hotkeys and the FPS counter of our build are ready (the effects start off)
                CncGameRenderer(true);
                Log(L.T("applied") + "gr-draw");
            }
            catch (Exception ex)
            {
                Log("gr-draw: switching on failed, rolling back: " + ex.Message);
                try { CncGameRenderer(false); } catch { }
                for (int i = made.Count - 1; i >= 0; i--) { try { File.Delete(P(made[i])); } catch { } }
                try { if (moved != null && File.Exists(P(moved)) && !File.Exists(P("ddraw.dll"))) File.Move(P(moved), P("ddraw.dll")); } catch { }
                try { string sd = P("Shaders"); if (Directory.Exists(sd)) { foreach (string d in Directory.GetDirectories(sd)) if (Directory.GetFileSystemEntries(d).Length == 0) Directory.Delete(d); if (Directory.GetFileSystemEntries(sd).Length == 0) Directory.Delete(sd); } } catch { }
                try { if (File.Exists(CncMark)) File.Delete(CncMark); } catch { } try { JDrop("grdraw"); } catch { }
                try { if (dgvWas) { DgvRestoreRenamed(); if (dgvMark) File.WriteAllText(DgvMark, "1"); } } catch { }   // only the renames are undone - nothing new is installed
                throw;
            }
        }
        // switching OFF touches only what the mark says is ours. A cnc-ddraw without our mark belongs to the user and stays.
        void CncOff()
        {
            if (!File.Exists(CncMark)) { if (Cnc) Warn(U.R("gr-draw в папке игры установлен не этой программой — он остался на месте.", "The gr-draw in the game folder was not installed by this program — it stays where it is.")); return; }
            List<string> made; string moved; ReadMark(out made, out moved);
            try { if (File.Exists(P("ddraw.ini")) && made.Contains("ddraw.ini")) { Directory.CreateDirectory(Path.GetDirectoryName(CncSaved)); File.Copy(P("ddraw.ini"), CncSaved, true); } } catch { }   // keep our ini's settings for next time
            bool ours = false; try { ours = IsCncDllStrict(P("ddraw.dll")); } catch (IOException) { ours = made.Contains("ddraw.dll"); }   // unreadable = locked: it is ours if the mark says so, and the delete below fails loudly
            if (ours)   // first the dll: if it is locked, nothing else changes and the mark stays so that a retry works
            {
                try { File.Delete(P("ddraw.dll")); }
                catch (Exception ex) { throw new IOException((U.R("Не удалось убрать ddraw.dll (занят? закройте игру): ", "Could not remove ddraw.dll (in use? close the game): ")) + ex.Message); }
            }
            List<string> left = new List<string>();
            foreach (string f in made) { if (string.Equals(f, "ddraw.dll", StringComparison.OrdinalIgnoreCase)) continue; try { if (File.Exists(P(f))) File.Delete(P(f)); } catch { left.Add(f); } }
            try { string sd = P("Shaders"); if (Directory.Exists(sd)) { foreach (string d in Directory.GetDirectories(sd)) if (Directory.GetFileSystemEntries(d).Length == 0) Directory.Delete(d); if (Directory.GetFileSystemEntries(sd).Length == 0) Directory.Delete(sd); } } catch { }
            string park = moved != null ? moved : (File.Exists(CncOther) ? "ddraw.dll.ogfbak" : null);
            if (park != null && File.Exists(P(park)))
            {
                if (!File.Exists(P("ddraw.dll"))) { try { File.Move(P(park), P("ddraw.dll")); } catch (Exception ex) { left.Add("@keep"); Warn((U.R("Не удалось вернуть прежний ddraw.dll: ", "Could not put the previous ddraw.dll back: ")) + ex.Message); } }
                else Warn(L.Ru ? "Прежний ddraw.dll сохранён как " + park + " (в папке уже лежит другой ddraw.dll)." : "The previous ddraw.dll is kept as " + park + " (another ddraw.dll is already there).");
            }
            try { CncGameRenderer(false); } catch (Exception ex) { Log("renderer: " + ex.Message); Warn((U.R("Не удалось вернуть прежний режим отрисовки игры (slashed.cfg): ", "Could not restore the game's renderer choice (slashed.cfg): ")) + ex.Message); }
            left.Remove("@keep");
            if (left.Count == 0) { File.Delete(CncMark); JDrop("grdraw"); } else { WriteMark(left, null); JNote("grdraw", false); Warn((U.R("Часть файлов gr-draw не удалена: ", "Some gr-draw files were not removed: ")) + string.Join(", ", left.ToArray())); }
            Log(L.T("reverted") + "gr-draw");
        }
        void BackupCncIni()
        {
            if (File.Exists(CncIniUser) || !File.Exists(P("ddraw.ini"))) return;
            List<string> made; string mv; ReadMark(out made, out mv); if (made.Contains("ddraw.ini")) return;
            Directory.CreateDirectory(BakDir); File.Copy(P("ddraw.ini"), CncIniUser); Log(L.T("backup") + CncIniUser);
        }
        // Divine Divinity picks its renderer DLL from slashed.cfg (0 = Direct3D 6 / slash1, 1 = Glide, 2 = DirectX, 3 = Software / slash4). cnc-ddraw implements DirectDraw only:
        // with Direct3D selected the game asks for IDirect3D3 and dies inside slash1.dll (found with cnc-ddraw's debug log, 06.11.2026). So cnc-ddraw means "Software", and back again.
        // Errors are NOT swallowed: the caller decides (switching on rolls back, switching off warns).
        void CncGameRenderer(bool on)
        {
            string cfg = P("slashed.cfg");
            if (on)
            {
                if (!File.Exists(cfg) || !File.Exists(P("slash4.dll"))) return;
                byte[] cur = File.ReadAllBytes(cfg); if (cur.Length >= 4 && cur[0] == 3 && cur[1] == 0) return;
                Directory.CreateDirectory(Path.GetDirectoryName(CncRenderPrev)); if (!File.Exists(CncRenderPrev)) File.Copy(cfg, CncRenderPrev);
                File.WriteAllBytes(cfg, new byte[] { 3, 0, 0, 0 }); Log(L.T("applied") + "renderer: Software");
            }
            else if (File.Exists(CncRenderPrev)) { File.Copy(CncRenderPrev, cfg, true); File.Delete(CncRenderPrev); Log(L.T("reverted") + "renderer"); }
        }
        // full revert: cnc-ddraw out, and the user's own ddraw.ini back if we ever edited it
        public void RevertCnc()
        {
            SetCnc(false);
            if (File.Exists(CncIniUser)) { File.Copy(CncIniUser, P("ddraw.ini"), true); File.Delete(CncIniUser); Log(L.T("reverted") + "ddraw.ini"); }
        }

        // ---- ddraw.ini: edit keys of the [ddraw] section only (IniEdit keeps encoding and line endings; a missing key is added; a missing ini is created from the bundled template)
        public string CncGet(string key, string def) { return File.Exists(P("ddraw.ini")) ? IniEdit.Get(P("ddraw.ini"), "ddraw", key, def) : def; }
        public void CncSet(string key, string val)
        {
            string f = P("ddraw.ini");
            if (!File.Exists(f)) { File.WriteAllBytes(f, CncRes("ddraw.ini")); MarkAdd("ddraw.ini"); }
            IniEdit.Set(f, "ddraw", key, val);
        }
    }

    // cnc-ddraw settings: window mode, scaling filter, aspect ratio, vsync, renderer. Edits [ddraw] of ddraw.ini in the game folder (applied on change, effective on the next game start).
    class CncForm : ToolForm
    {
        static readonly string[] Shaders = { "Nearest neighbor", "Bilinear", "Shaders\\interpolation\\catmull-rom-bilinear.glsl", "Shaders\\interpolation\\fsr.glsl", UiScale.ShaderFraction };
        static readonly string[] Renderers = { "auto", "opengl", "direct3d9", "gdi" };
        public CncForm(Core c) : base(c, new Size(880, 800)) { }
        protected override string TitleRu { get { return "Настройки gr-draw"; } }
        protected override string TitleEn { get { return "gr-draw settings"; } }
        void Set(string key, string val)
        {
            try { Game.CncSet(key, val); Status("Сохранено. Применится при следующем запуске игры.", "Saved. Applies on the next game start."); }
            catch (Exception ex) { Status("Не удалось записать: " + ex.Message, "Could not write: " + ex.Message); }
        }
        bool B(string key, bool def) { return Game.CncGet(key, def ? "true" : "false").ToLower() == "true"; }
        Seg OnOffSeg(string key, bool def) { Seg s = Sg(new string[] { T("Выкл", "Off"), T("Вкл", "On") }, B(key, def) ? 1 : 0, null); s.Changed += delegate { Set(key, s.Selected == 1 ? "true" : "false"); }; return s; }
        int ModeIdx() { bool w = B("windowed", false), f = B("fullscreen", false); return w && f ? 0 : (w ? 2 : 1); }
        int ShaderIdx() { string v = Game.CncGet("shader", "").ToLower(); for (int i = 0; i < Shaders.Length; i++) if (v == Shaders[i].ToLower()) return i; if (v.Contains("fsr")) return 3; if (v.Contains("lanczos")) return 4; if (v.Contains("nearest")) return 0; if (v.Contains("bilinear") && !v.Contains("catmull")) return 1; return 2; }

        protected override void Build(Panel b)
        {
            RPanel c = Card(b, 0, 0, b.Width, b.Height, T("Настройки gr-draw", "gr-draw settings"), Game.HasGame && Game.Cnc ? T("Другая обёртка вместо dgVoodoo", "Alternative wrapper instead of dgVoodoo") : T("Игра не найдена", "Game not found"));
            if (!Game.HasGame || !Game.Cnc || !File.Exists(Game.P("ddraw.ini")))
            {
                Lay(c, 66, Row("◇", Th.Faint, "gr-draw", T("Не включён в игре", "Not turned on in the game"), new Label()));
                Label l = new Label(); l.AutoSize = false; l.SetBounds(14, 126, c.Width - 28, 40); l.ForeColor = Th.Muted; l.BackColor = Th.Surf; l.UseMnemonic = false;
                l.Text = T("Включите «gr-draw» на странице «Патчи и фиксы» и откройте это окно снова.", "Turn on “gr-draw” on the Patches page and reopen this window."); c.Controls.Add(l);
                Status("", ""); return;
            }
            Seg mode = Sg(new string[] { T("Без рамки", "Borderless"), T("Полный экран", "Fullscreen"), T("Окно", "Windowed") }, ModeIdx(), null);
            mode.Width = 270;
            mode.Changed += delegate
            {
                if (mode.Selected == 0) { Set("windowed", "true"); Set("fullscreen", "true"); }
                else if (mode.Selected == 1) { Set("windowed", "false"); Set("fullscreen", "true"); }
                else { Set("windowed", "true"); Set("fullscreen", "false"); Set("border", "true"); }
            };
            Seg ren = null;
            Seg flt = Sg(new string[] { T("Авто", "Auto"), T("Чётко", "Sharp"), T("Плавно", "Smooth"), T("Мягко", "Soft"), "FSR", "Lanczos" }, Game.FilterAuto ? 0 : ShaderIdx() + 1, null);
            flt.Width = 400;
            flt.Changed += delegate
            {
                int spc; Size sgm; Game.ScaleSaved(out spc, out sgm);
                if (flt.Selected == 0) { Game.FilterAuto = true; Set("shader", Game.PlanScale(spc, Core.ScreenPixels(Screen.FromControl(this))).Shader); }   // Auto: from the interface size
                else { Game.FilterAuto = false; Set("shader", Shaders[flt.Selected - 1]); }
                Set("renderer", "opengl"); ren.Selected = 1;   // shaders need the OpenGL renderer: the "Renderer" segment follows the ini
            };
            ren = Sg(new string[] { T("Авто", "Auto"), "OpenGL", "Direct3D 9", "GDI" }, Math.Max(0, Array.IndexOf(Renderers, Game.CncGet("renderer", "auto").ToLower())), null);
            ren.Width = 270; ren.Changed += delegate { Set("renderer", Renderers[ren.Selected]); if (ren.Selected != 1) Status("Фильтр масштабирования работает только на OpenGL — выберите OpenGL, если нужен фильтр.", "The scaling filter only works on OpenGL — pick OpenGL if you want the filter."); };
            Size mon = Core.ScreenPixels(Screen.FromControl(this)); int savedPct; Size savedGame; bool has = Game.ScaleSaved(out savedPct, out savedGame);
            Seg scl = Sg(new string[] { T("Авто", "Auto"), "100%", "125%", "150%", "200%" }, has ? Math.Max(0, Array.IndexOf(UiScale.Steps, savedPct)) : 0, null); scl.Width = 340;
            Label sum = new Label(); sum.AutoSize = false; sum.UseMnemonic = false; sum.ForeColor = Th.Muted; sum.BackColor = Th.Surf; sum.Font = Th.Small;
            Action show = delegate { ScalePlan pl = Game.PlanScale(UiScale.Steps[scl.Selected], mon); sum.Text = UiScale.Summary(pl, IsRu) + (pl.Notes.Count > 0 ? "\n" + UiScale.Warnings(pl, IsRu) : ""); };
            scl.Changed += delegate
            {
                try
                {
                    ScalePlan pl = Game.ApplyScale(UiScale.Steps[scl.Selected], mon); show();
                    ren.Selected = 1; flt.Selected = 0; mode.Selected = 0;   // the rows follow the ini
                    Status("Размер интерфейса сохранён. Применится при следующем запуске игры.", "Interface size saved. Applies on the next game start.");
                }
                catch (Exception ex) { Status("Не удалось применить: " + ex.Message, "Could not apply: " + ex.Message); }
            };
            show();
            Seg asp = OnOffSeg("maintas", false), vs = OnOffSeg("vsync", false), adj = OnOffSeg("adjmouse", true), dev = OnOffSeg("devmode", false);
            string[] fpsV = { "-1", "60", "30", "0" }; int fi = Array.IndexOf(fpsV, Game.CncGet("maxfps", "-1")); if (fi < 0) fi = 0;
            Seg fps = Sg(new string[] { T("Экран", "Screen"), "60", "30", T("Без лимита", "Unlimited") }, fi, null); fps.Width = 300; fps.Changed += delegate { Set("maxfps", fpsV[fps.Selected]); };
            int ly = Lay(c, 66, new SecHead(T("Окно и изображение", "Window and image")),
                Hr(Row("▭", Th.Amber, T("Режим", "Mode"), T("Окно игры", "Game window"), mode), "window_mode"),
                Hr(Row("⤢", Th.Amber, T("Размер интерфейса", "Interface size"), T("Игра рисуется меньше, кадр растягивается на монитор", "Smaller frame, stretched"), scl), "scale"),
                Hr(Row("◐", Th.Amber, T("Фильтр масштабирования", "Scaling filter"), T("Авто — по размеру интерфейса", "Auto: by size"), flt), "filter"),
                Hr(Row("⧉", Th.Amber, T("Сохранять пропорции", "Keep aspect ratio"), T("Чёрные поля вместо растяжения", "Black bars instead of stretching"), asp), "keep_aspect"),
                new SecHead(T("Производительность", "Performance")),
                Hr(Row("⇅", Th.Amber, T("Верт. синхронизация", "Vertical sync"), T("Без разрывов; даёт небольшую задержку", "No tearing; adds a little input lag"), vs), "vsync"),
                Hr(Row("◔", Th.Amber, T("Лимит кадров", "Frame limit"), T("По монитору", "By monitor"), fps), "fps_limit"),
                Hr(Row("⚙", Th.Amber, T("Отрисовка", "Renderer"), T("Движок", "Engine"), ren), "renderer"),
                new SecHead(T("Мышь", "Mouse")),
                Hr(Row("↔", Th.Amber, T("Чувствительность", "Sensitivity"), T("Под масштаб картинки", "Follows the picture scale"), adj), "mouse_sens"),
                Hr(Row("⇱", Th.Amber, T("Курсор выходит за окно", "Free cursor"), T("Удобно со вторым монитором", "Handy with a second monitor"), dev), "cursor_free"));
            sum.SetBounds(14, ly + 2, c.Width - 28, 78); c.Controls.Add(sum);
            FootBtn(T("Рекомендуемые", "Recommended"), false, 150, delegate
            {
                Set("windowed", "true"); Set("fullscreen", "true"); Set("maintas", "true"); Set("vsync", "true"); Set("shader", "Shaders\\interpolation\\catmull-rom-bilinear.glsl"); Set("renderer", "opengl");
                mode.Selected = 0; asp.Selected = 1; vs.Selected = 1; flt.Selected = 2; ren.Selected = 1; fps.Selected = 0; Set("maxfps", "-1"); adj.Selected = 1; Set("adjmouse", "true"); dev.Selected = 0; Set("devmode", "false");
                try { ScalePlan pl = Game.ApplyScale(0, mon); scl.Selected = 0; flt.Selected = pl.Integer ? 0 : 4; show(); } catch (Exception ex) { Status("Не удалось применить размер: " + ex.Message, "Could not apply the size: " + ex.Message); }
            });
            Status("Изменения применяются сразу и вступают в силу при следующем запуске игры.", "Changes apply immediately and take effect on the next game start.");
        }
    }
}
