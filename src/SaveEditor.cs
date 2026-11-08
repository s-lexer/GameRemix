using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Windows.Forms;

namespace DDFixTool
{
    // Divine Divinity savegame (data.000) hero attributes. Offsets were reverse-engineered from sample saves and cross-checked
    // byte-for-byte against the classic editor's output (games/divine-divinity/analysis/test_save_format.py).
    // Layout (T = offset of the first "AgentsV" tag, E = T + 0x6E0, S = offset of the first "SkillsV" tag), all values little-endian uint32:
    //   experience E; current Str/Dex/Int E-0x14/-0x10/-0xC, current Con E-4; base Str/Dex/Int E+0x10/+0x14/+0x18, base Con E+0x20;
    //   free attribute points T+0x44C; free skill points S+0x1C.
    class SaveData
    {
        public string Path; public byte[] Raw; int T, S;
        public static readonly string[] Names = { "Str", "Dex", "Int", "Con" };
        public class Skill { public string Name; public int Off; public uint Level, A; public uint LevelOrig; }
        public List<Skill> Skills = new List<Skill>();
        // skill record (found by scan, B = offset of the "level*20" field): B level*20; B-0x2c companion value (moves with B, floor 0); B+4 zero; B+0x2c name length; B+0x30 name (cp1251, NUL-terminated)
        void ScanSkills()
        {
            Skills.Clear(); int end = Math.Min(Raw.Length - 0x40, S + 0x13900);
            for (int b = S + 0x20; b < end; b++)
            {
                uint lv = U(b); if (lv > 2000 || lv % 20 != 0 || U(b + 4) != 0) continue;
                uint a = U(b - 0x2c); if (a > 2000 || a % 20 != 0) continue;
                uint len = U(b + 0x2c); if (len < 3 || len > 80 || b + 0x30 + len > Raw.Length || Raw[b + 0x30 + len - 1] != 0) continue;
                bool ok = true; for (int i = 0; i < len - 1; i++) if (Raw[b + 0x30 + i] < 32) { ok = false; break; }
                if (!ok) continue;
                Skills.Add(new Skill { Name = System.Text.Encoding.GetEncoding(1251).GetString(Raw, b + 0x30, (int)len - 1), Off = b, Level = lv / 20, LevelOrig = lv / 20, A = a });
            }
        }
        // like the classic editor: a level change moves B and its companion by 20 per level (companion not below 0) and takes/returns free skill points
        public void SetSkill(Skill k, uint level)
        {
            long d = ((long)level - k.Level) * 20; FreeSkill = (uint)Math.Max(0, (long)FreeSkill - (level - (long)k.Level)); k.A = (uint)Math.Max(0, (long)k.A + d); k.Level = level;
        }
        public uint Exp, FreeAttr, FreeSkill; public uint[] Cur = new uint[4], Base = new uint[4];
        int E { get { return T + 0x6E0; } }
        int[] CurOff { get { return new int[] { E - 0x14, E - 0x10, E - 0xC, E - 4 }; } }
        int[] BaseOff { get { return new int[] { E + 0x10, E + 0x14, E + 0x18, E + 0x20 }; } }
        uint U(int o) { return BitConverter.ToUInt32(Raw, o); }
        void P(int o, uint v) { byte[] b = BitConverter.GetBytes(v); Array.Copy(b, 0, Raw, o, 4); }
        static int Find(byte[] d, string tag) { byte[] t = System.Text.Encoding.ASCII.GetBytes(tag); for (int i = 0; i + t.Length <= d.Length; i++) { int j = 0; while (j < t.Length && d[i + j] == t[j]) j++; if (j == t.Length) return i; } return -1; }

        public static SaveData Open(string path)
        {
            SaveData s = new SaveData(); s.Path = path; s.Raw = File.ReadAllBytes(path);
            if (s.Raw.Length < 0x1000 || Find(s.Raw, "Divinity Save Game") != 4) throw new InvalidDataException("not a Divine Divinity save (data.000)");
            s.T = Find(s.Raw, "AgentsV"); s.S = Find(s.Raw, "SkillsV");
            if (s.T < 0 || s.S < 0 || s.E + 0x24 > s.Raw.Length || s.T + 0x450 > s.Raw.Length || s.S + 0x20 > s.Raw.Length) throw new InvalidDataException("unsupported save layout");
            s.Exp = s.U(s.E); s.FreeAttr = s.U(s.T + 0x44C); s.FreeSkill = s.U(s.S + 0x1C);
            for (int i = 0; i < 4; i++) { s.Cur[i] = s.U(s.CurOff[i]); s.Base[i] = s.U(s.BaseOff[i]); if (s.Cur[i] > 100000 || s.Base[i] > 100000) throw new InvalidDataException("unexpected attribute values: wrong layout"); }
            if (s.Exp > 2000000000) throw new InvalidDataException("unexpected experience value");
            s.ScanSkills();
            return s;
        }
        // changing a base attribute moves the current one by the same amount (as the game does) and returns/uses free points like the classic editor
        public void SetBase(int i, uint v, bool adjustFree)
        {
            long d = (long)v - Base[i]; Base[i] = v; Cur[i] = (uint)Math.Max(0, (long)Cur[i] + d);
            if (adjustFree) FreeAttr = (uint)Math.Max(0, (long)FreeAttr - d);
        }
        public void Write()
        {
            P(E, Exp); P(T + 0x44C, FreeAttr); P(S + 0x1C, FreeSkill);
            foreach (Skill k in Skills) { P(k.Off, k.Level * 20); P(k.Off - 0x2c, k.A); }
            int[] co = CurOff, bo = BaseOff; for (int i = 0; i < 4; i++) { P(co[i], Cur[i]); P(bo[i], Base[i]); }
            string bak = Path + ".bak_" + DateTime.Now.ToString("yyyyMMdd_HHmmss"); for (int n = 2; File.Exists(bak); n++) bak = Path + ".bak_" + DateTime.Now.ToString("yyyyMMdd_HHmmss") + "_" + n;
            if (Core.GameRunning()) throw new IOException(L.T("running"));   // the game keeps the save open / rewrites it on exit
            File.Copy(Path, bak, false);
            // atomic: the new bytes go to a temp file, then File.Replace swaps it in (the old file is never missing); if the swap is impossible the old one is parked and put back on failure
            string tmp = Path + ".tmp", old = Path + ".old_" + DateTime.Now.ToString("HHmmss");
            try
            {
                File.WriteAllBytes(tmp, Raw);
                try { File.Replace(tmp, Path, null); }
                catch (IOException)
                {
                    File.Move(Path, old);
                    try { File.Move(tmp, Path); } catch { try { if (!File.Exists(Path)) File.Move(old, Path); } catch { } throw; }
                    try { File.Delete(old); } catch { }
                }
            }
            finally { try { if (File.Exists(tmp)) File.Delete(tmp); } catch { } }
        }
    }

    class ToolSaveEditor : ToolForm
    {
        SaveData sd; string path; bool busy; ComboBox pick; List<string[]> saves = new List<string[]>();
        NumericUpDown[] nb = new NumericUpDown[4]; RowCtl[] rAttr = new RowCtl[4]; NumericUpDown nExp, nFree, nSk, nLvl; RowCtl rLvl; ListBox lbSk; Field search; List<SaveData.Skill> shown = new List<SaveData.Skill>();
        Btn bSave, bReload; RPanel left, right; Label subL, subR;
        public ToolSaveEditor(Core c) : base(c, new Size(1020, 700)) { }
        protected override string TitleRu { get { return "Редактор сохранений"; } }
        protected override string TitleEn { get { return "Save editor"; } }

        List<string[]> Saves()
        {
            List<string[]> l = new List<string[]>(); try { string dir = Game.P("savegames"); if (Directory.Exists(dir)) foreach (string d in Directory.GetDirectories(dir)) { string f = System.IO.Path.Combine(d, "data.000"); if (File.Exists(f)) l.Add(new string[] { System.IO.Path.GetFileName(d), f, File.GetLastWriteTime(f).ToString("yyyy-MM-dd HH:mm") }); } } catch { }
            l.Sort(delegate(string[] a, string[] b) { return string.CompareOrdinal(b[2], a[2]); }); return l;
        }
        string SkName(SaveData.Skill k) { return SkillNames.Display(k.Name, IsRu); }

        protected override void Build(Panel b)
        {
            int lw = 480; sd = null; saves = Saves();
            left = Card(b, 0, 0, lw, b.Height, T("Редактор сохранений", "Save editor"), ""); subL = (Label)left.Controls[1];
            right = Card(b, lw + M, 0, b.Width - lw - M, b.Height, T("Навыки", "Skills"), ""); subR = (Label)right.Controls[1];
            // --- left: save, attributes, points
            pick = new ComboBox(); pick.DropDownStyle = ComboBoxStyle.DropDownList; pick.FlatStyle = FlatStyle.Flat; pick.BackColor = Th.SurfHi; pick.ForeColor = Th.Text; pick.Width = 230; pick.Font = Th.F("Segoe UI", 9f, FontStyle.Regular);
            foreach (string[] sv in saves) pick.Items.Add(sv[0] + "  ·  " + sv[2]);
            pick.SelectedIndexChanged += delegate { if (!busy && pick.SelectedIndex >= 0) LoadFile(saves[pick.SelectedIndex][1]); };
            Btn browse = Act(T("Обзор…", "Browse…"), delegate { using (OpenFileDialog o = new OpenFileDialog()) { o.Title = T("Выберите data.000", "Choose data.000"); o.Filter = "data.000|data.000|*.*|*.*"; if (o.ShowDialog(this) == DialogResult.OK) LoadFile(o.FileName); } });
            string[] ru = { "Сила", "Ловкость", "Интеллект", "Телосложение" }, en = { "Strength", "Dexterity", "Intelligence", "Constitution" }; string[] gl = { "✊", "➶", "✦", "♥" };
            List<Control> items = new List<Control>();
            items.Add(new SecHead(T("Сохранение", "Save game")));
            items.Add(Row("⎘", Th.Muted, T("Сохранение", "Save"), T("Из папки savegames игры", "From the game's savegames folder"), pick));
            items.Add(Row("⌕", Th.Muted, T("Другой файл", "Another file"), T("Выбрать data.000 вручную", "Pick a data.000 by hand"), browse));
            items.Add(new SecHead(T("Характеристики", "Attributes")));
            for (int i = 0; i < 4; i++) { nb[i] = Num(9999); int k = i; nb[i].ValueChanged += delegate { OnBase(k); }; rAttr[i] = Row(gl[i], Th.Amber, T(ru[i], en[i]), T("Базовое значение; текущее меняется вместе с ним", "Base value; the current one moves with it"), nb[i]); items.Add(rAttr[i]); }
            nFree = Num(99999); nSk = Num(99999); nExp = Num(2000000000); nExp.Width = 92;
            items.Add(new SecHead(T("Очки и опыт", "Points and experience")));
            items.Add(Row("◆", Th.Amber, T("Очки характеристик", "Attribute points"), T("Свободные очки для распределения", "Free points to distribute"), nFree));
            items.Add(Row("★", Th.Amber, T("Очки навыков", "Skill points"), T("Свободные очки для навыков", "Free points for skills"), nSk));
            items.Add(Row("✧", Th.Amber, T("Опыт", "Experience"), T("Общий опыт героя", "Total experience of the hero"), nExp));
            Lay(left, 66, items.ToArray());
            // --- right: search + list + level
            search = new Field(); search.Under = Th.Surf; search.Hint = T("Найти навык", "Find a skill"); search.SetBounds(14, 66, right.Width - 28, 38); right.Controls.Add(search);
            nLvl = Num(5); rLvl = Row("⚑", Th.Amber, T("Уровень навыка", "Skill level"), "", nLvl); rLvl.Status = T("от 0 до 5", "0 to 5"); rLvl.SetBounds(14, right.Height - 14 - RowCtl.H, right.Width - 28, RowCtl.H); right.Controls.Add(rLvl);
            lbSk = new ListBox(); lbSk.DrawMode = DrawMode.OwnerDrawFixed; lbSk.ItemHeight = 34; lbSk.BorderStyle = BorderStyle.None; lbSk.BackColor = Th.Inset; lbSk.IntegralHeight = false; lbSk.SetBounds(14, 112, right.Width - 28, rLvl.Top - 8 - 112); right.Controls.Add(lbSk); Dark.Scroll(lbSk);
            lbSk.DrawItem += DrawSkill; lbSk.SelectedIndexChanged += delegate { OnSkillPick(); }; nLvl.ValueChanged += delegate { OnLevel(); };
            search.Box.TextChanged += delegate { FillSkills(); };
            bSave = FootBtn(T("Сохранить", "Save"), true, 150, delegate { DoSave(); });
            bReload = FootBtn(T("Перечитать", "Reload"), false, 130, delegate { if (path != null) LoadFile(path); });
            Enable(false);
            if (path != null) LoadFile(path); else if (saves.Count > 0) { busy = true; pick.SelectedIndex = 0; busy = false; LoadFile(saves[0][1]); } else Status("Сохранения не найдены. Нажмите «Обзор…».", "No saves found. Press “Browse…”.");
        }
        void DrawSkill(object sender, DrawItemEventArgs e)
        {
            if (e.Index < 0 || e.Index >= shown.Count) return; SaveData.Skill k = shown[e.Index]; bool sel = (e.State & DrawItemState.Selected) != 0; Graphics g = e.Graphics; g.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
            Rectangle r = e.Bounds; using (SolidBrush bg = new SolidBrush(Th.Inset)) g.FillRectangle(bg, r);
            Rectangle rr = new Rectangle(r.X + 2, r.Y + 2, r.Width - 4, r.Height - 4);
            using (System.Drawing.Drawing2D.GraphicsPath p = Th.RR(rr, 8)) using (SolidBrush bg2 = new SolidBrush(sel ? Th.SurfHi : Th.Inset)) g.FillPath(bg2, p);
            TextFit.Draw(g, (Control)sender, SkName(k), Th.F("Segoe UI", 9f, FontStyle.Regular), new Rectangle(r.X + 14, r.Y, r.Width - 14 - 110, r.Height), k.Level > 0 ? Th.Text : Th.Muted, TextFormatFlags.VerticalCenter | TextFormatFlags.EndEllipsis | TextFormatFlags.NoPrefix | TextFormatFlags.NoPadding);
            int cx = r.Right - 14 - 5 * 16;
            for (int i = 0; i < 5; i++)
            {
                Rectangle d = new Rectangle(cx + i * 16, r.Y + (r.Height - 10) / 2, 10, 10);
                if (i < k.Level) using (SolidBrush ab = new SolidBrush(Th.Amber)) g.FillEllipse(ab, d); else using (Pen lp = new Pen(Th.Line)) g.DrawEllipse(lp, d);
            }
        }
        void Enable(bool on) { foreach (NumericUpDown n in nb) n.Enabled = on; nFree.Enabled = nSk.Enabled = nExp.Enabled = on; bSave.Enabled = on; lbSk.Enabled = on; nLvl.Enabled = on && lbSk.SelectedIndex >= 0; }
        void LoadFile(string f)
        {
            try
            {
                sd = SaveData.Open(f); path = f; busy = true;
                for (int i = 0; i < 4; i++) { nb[i].Value = Math.Min(nb[i].Maximum, sd.Base[i]); RefreshCur(i); }
                nFree.Value = Math.Min(nFree.Maximum, sd.FreeAttr); nSk.Value = Math.Min(nSk.Maximum, sd.FreeSkill); nExp.Value = Math.Min(nExp.Maximum, sd.Exp); busy = false;
                subL.Text = f; subR.Text = sd.Skills.Count + T(" навыков", " skills"); FillSkills(); Enable(true); Status("Загружено. Перед записью рядом создаётся копия data.000.bak_дата.", "Loaded. A data.000.bak_date copy is made next to the file before saving.");
            }
            catch (Exception ex) { busy = false; sd = null; Enable(false); Status("Не удалось открыть: " + ex.Message, "Could not open: " + ex.Message); }
        }
        void RefreshCur(int i) { rAttr[i].Status = T("сейчас ", "now ") + sd.Cur[i]; rAttr[i].StatusColor = Th.Muted; rAttr[i].Invalidate(); }
        void FillSkills()
        {
            if (sd == null) return; string q = search.Box.Text.Trim().ToLower(); SaveData.Skill keep = lbSk.SelectedIndex >= 0 && lbSk.SelectedIndex < shown.Count ? shown[lbSk.SelectedIndex] : null;
            shown.Clear(); lbSk.BeginUpdate(); lbSk.Items.Clear();
            foreach (SaveData.Skill k in sd.Skills) if (q.Length == 0 || SkName(k).ToLower().Contains(q)) { shown.Add(k); lbSk.Items.Add(k.Name); }
            lbSk.EndUpdate(); int ix = keep == null ? -1 : shown.IndexOf(keep); if (ix >= 0) lbSk.SelectedIndex = ix; else OnSkillPick();
        }
        void OnSkillPick()
        {
            if (sd == null) return; busy = true;
            if (lbSk.SelectedIndex < 0 || lbSk.SelectedIndex >= shown.Count) { nLvl.Enabled = false; subR.Text = sd.Skills.Count + T(" навыков", " skills"); }
            else { SaveData.Skill k = shown[lbSk.SelectedIndex]; nLvl.Maximum = Math.Max(5, k.Level); nLvl.Value = k.Level; nLvl.Enabled = true; subR.Text = SkName(k); }
            rLvl.Invalidate(); busy = false;
        }
        void OnLevel()
        {
            if (busy || sd == null || lbSk.SelectedIndex < 0) return; SaveData.Skill k = shown[lbSk.SelectedIndex]; busy = true;
            sd.SetSkill(k, (uint)nLvl.Value); nSk.Value = Math.Min(nSk.Maximum, sd.FreeSkill); lbSk.Invalidate(); busy = false;
        }
        void OnBase(int i)
        {
            if (busy || sd == null) return; busy = true;
            sd.SetBase(i, (uint)nb[i].Value, true); RefreshCur(i); nFree.Value = Math.Min(nFree.Maximum, sd.FreeAttr); busy = false;
        }
        void DoSave()
        {
            if (sd == null) return;
            try { sd.FreeAttr = (uint)nFree.Value; sd.FreeSkill = (uint)nSk.Value; sd.Exp = (uint)nExp.Value; sd.Write(); Status("Сохранено (копия .bak рядом).", "Saved (.bak copy next to it)."); }
            catch (Exception ex) { Status("Ошибка записи: " + ex.Message, "Write error: " + ex.Message); }
        }
    }
}
