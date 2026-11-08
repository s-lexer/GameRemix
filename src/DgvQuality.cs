using System;
using System.Drawing;
using System.IO;
using System.Windows.Forms;

namespace DDFixTool
{
    // dgVoodoo quality: render scale, anti-aliasing, vertical sync. Edits [DirectX] of dgVoodoo.conf in the game folder (applied on change).
    class DgvQualityForm : ToolForm
    {
        static readonly string[] Scale = { "1x", "2x", "3x", "4x" }, Aa = { "appdriven", "2x", "4x", "8x" };
        public DgvQualityForm(Core c) : base(c, new Size(760, 330)) { }
        protected override string TitleRu { get { return "Качество графики (dgVoodoo)"; } }
        protected override string TitleEn { get { return "Graphics quality (dgVoodoo)"; } }
        string Conf { get { return Game.P("dgVoodoo.conf"); } }

        string Get(string key, string def) { return File.Exists(Conf) ? IniEdit.Get(Conf, "DirectX", key, def) : def; }
        // adds the key when missing, keeps the player's own conf (first edit is backed up), and only says "Saved" when it really was
        void Set(string key, string val)
        {
            try { Game.DgvSet(key, val); Status("Сохранено. Применится при следующем запуске игры.", "Saved. Applies on the next game start."); }
            catch (Exception ex) { Status("Не удалось записать: " + ex.Message, "Could not write: " + ex.Message); }
        }
        int Idx(string[] a, string v) { for (int i = 0; i < a.Length; i++) if (string.Equals(a[i], v, StringComparison.OrdinalIgnoreCase)) return i; return 1; }

        protected override void Build(Panel b)
        {
            RPanel c = Card(b, 0, 0, b.Width, b.Height, T("Качество графики", "Graphics quality"), Game.HasGame ? Game.Dir : T("Игра не найдена", "Game not found"));
            if (!Game.HasGame || !File.Exists(Conf))
            {
                Lay(c, 66, Row("◈", Th.Faint, "dgVoodoo", T("Не установлен в игру", "Not installed in the game"), new Label()));
                Label l = new Label(); l.AutoSize = false; l.SetBounds(14, 126, c.Width - 28, 40); l.ForeColor = Th.Muted; l.BackColor = Th.Surf; l.UseMnemonic = false;
                l.Text = T("Включите «dgVoodoo» на странице «Патчи и фиксы» и откройте это окно снова.", "Turn on “dgVoodoo” on the Patches page and reopen this window."); c.Controls.Add(l);
                Status("", ""); return;
            }
            Seg sc = Sg(Scale, Idx(Scale, Get("Resolution", "2x")), null); sc.Changed += delegate { Set("Resolution", Scale[sc.Selected]); };
            Seg aa = Sg(new string[] { T("Выкл", "Off"), "2x", "4x", "8x" }, Array.IndexOf(Aa, Get("Antialiasing", "appdriven").ToLower()) < 0 ? 0 : Array.IndexOf(Aa, Get("Antialiasing", "appdriven").ToLower()), null); aa.Changed += delegate { Set("Antialiasing", Aa[aa.Selected]); };
            Seg vs = Sg(new string[] { T("Выкл", "Off"), T("Вкл", "On") }, Get("ForceVerticalSync", "true").ToLower() == "true" ? 1 : 0, null); vs.Changed += delegate { Set("ForceVerticalSync", vs.Selected == 1 ? "true" : "false"); };
            Lay(c, 66, new SecHead(T("Изображение", "Image")),
                Hr(Row("⤢", Th.Amber, T("Масштаб", "Render scale"), T("Чётче на 4K; для Full HD — 2x", "Sharper on 4K; Full HD: 2x"), sc), "dgv_scale"),
                Hr(Row("◍", Th.Amber, T("Сглаживание", "Anti-aliasing"), T("MSAA: убирает «лесенку»", "MSAA: removes jaggies"), aa), "dgv_msaa"),
                Hr(Row("⇅", Th.Amber, T("Верт. синхронизация", "Vertical sync"), T("Без разрывов; при лагах выключите", "No tearing; turn off if it lags"), vs), "dgv_vsync"));
            BuildFoot2(sc, aa, vs);
            Status("Изменения применяются сразу и вступают в силу при следующем запуске игры.", "Changes apply immediately and take effect on the next game start.");
        }
        void BuildFoot2(Seg sc, Seg aa, Seg vs)
        {
            FootBtn(T("Рекомендуемые", "Recommended"), false, 150, delegate { Set("Resolution", "2x"); Set("Antialiasing", "8x"); Set("ForceVerticalSync", "true"); sc.Selected = 1; aa.Selected = 3; vs.Selected = 1; });
        }
    }
}
