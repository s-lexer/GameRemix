// "Graphics" page, the part without windows: what the page can change (slots, fixes: DATA from games/<id>/gfx/gfx.txt), what is installed now, a plan of changes
// (order, layers, conflicts, download size) and its execution with a rollback to the previous state on failure. The same code serves the page and the CLI (--gfx).
using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;

namespace DDFixTool
{
    class GfxOpt
    {
        public string Slot = "", Value = "", SetId = "", NameRu = "", NameEn = "", Prev = "", Patch = "";   // Patch: a byte patch (gfx.txt patch=) that goes with this option; SetId ending in "@ui" = one set per interface skin ("windows-@ui" -> windows-c)
         public bool Optional, Hidden; public int ApproxMb;   // ApproxMb: the download size shown BEFORE the catalog is known (quick setup)   // Optional: shown only when the server offers the set
        public string Name { get { return L.Ru ? NameRu : L.Kor(NameEn); } }
        public bool PerSkin { get { return SetId.EndsWith("@ui"); } }
        public string SetPrefix { get { return PerSkin ? SetId.Substring(0, SetId.Length - 3) : SetId; } }   // "windows-"
    }
    class GfxSlot
    {
        public string Id = "", Kind = "", TitleRu = "", TitleEn = "", DescRu = "", DescEn = ""; public List<GfxOpt> Opts = new List<GfxOpt>();
        public string Title { get { return L.Ru ? TitleRu : L.Kor(TitleEn); } }
        public string Desc { get { return L.Ru ? DescRu : L.Kor(DescEn); } }
        public GfxOpt Find(string v) { foreach (GfxOpt o in Opts) if (o.Value == v) return o; return null; }
    }
    class GfxFix
    {
        public string Id = "", Kind = "", Arg = "", NameRu = "", NameEn = "", DescRu = "", DescEn = ""; public bool Default, Switch;   // Switch: default-on fix that still has a switch on the Graphics page (item glow). Default: part of the base set, applied without a switch (see Core.ApplyDefaultFixes)
        public string Name { get { return L.Ru ? NameRu : L.Kor(NameEn); } }
        public string Desc { get { return L.Ru ? DescRu : L.Kor(DescEn); } }
    }

    class GfxDef
    {
        public string Game = ""; public List<GfxSlot> Slots = new List<GfxSlot>(); public List<GfxFix> Fixes = new List<GfxFix>(); public Dictionary<string, BytePatch> Patches = new Dictionary<string, BytePatch>();
        public List<CmpEntryPatch> CmpEntries = new List<CmpEntryPatch>(); public List<TextRecPatch> TextRecs = new List<TextRecPatch>();   // data edits that go with patch=windows (WinPack.cs)
        static GfxDef dd; public static GfxDef Dd { get { if (dd == null) dd = Parse(Encoding.UTF8.GetString(Core.ResBytes("gfx_def"))); return dd; } }
        public GfxSlot Slot(string id) { foreach (GfxSlot s in Slots) if (s.Id == id) return s; return null; }
        public GfxFix Fix(string id) { foreach (GfxFix f in Fixes) if (f.Id == id) return f; return null; }
        // lines: slot=id|kind|title.ru|title.en|desc.ru|desc.en   opt=slot|value|setId[?]|name.ru|name.en|preview   fix=id|kind|arg|name.ru|name.en|desc.ru|desc.en   patch=id|file|size|off:orig:new|...
        public static GfxDef Parse(string text)
        {
            GfxDef d = new GfxDef(); bool head = false;
            foreach (string raw in text.TrimStart('﻿').Replace("\r\n", "\n").Split('\n'))
            {
                string ln = raw.Trim(); if (ln.Length == 0 || ln[0] == '#') continue;
                if (!head) { if (!Regex.IsMatch(ln, @"^OGF-GFX\s+1$")) throw new InvalidDataException("gfx.txt: header"); head = true; continue; }
                int eq = ln.IndexOf('='); if (eq <= 0) continue; string k = ln.Substring(0, eq).Trim(), v = ln.Substring(eq + 1); string[] p = v.Split('|');
                if (k == "game") d.Game = v.Trim();
                else if (k == "slot" && p.Length >= 6) { GfxSlot s = new GfxSlot(); s.Id = p[0]; s.Kind = p[1]; s.TitleRu = p[2]; s.TitleEn = p[3]; s.DescRu = p[4]; s.DescEn = p[5]; d.Slots.Add(s); }
                else if (k == "opt" && p.Length >= 6)
                {
                    GfxSlot s = d.Slot(p[0]); if (s == null) continue; GfxOpt o = new GfxOpt(); o.Slot = p[0]; o.Value = p[1]; o.SetId = p[2]; if (o.SetId.EndsWith("?")) { o.Optional = true; o.SetId = o.SetId.TrimEnd('?'); }
                    o.NameRu = p[3]; o.NameEn = p[4]; o.Prev = p[5]; if (p.Length > 6) int.TryParse(p[6], out o.ApproxMb); if (p.Length > 7) o.Patch = p[7].Trim(); s.Opts.Add(o);
                }
                else if (k == "hide" && p.Length >= 2) { GfxSlot s = d.Slot(p[0]); GfxOpt o = s == null ? null : s.Find(p[1].Trim()); if (o != null) o.Hidden = true; }   // hide=<slot>|<value>: not offered any more, still recognised when it is installed
                else if (k == "fix" && p.Length >= 7) { GfxFix f = new GfxFix(); f.Id = p[0]; f.Kind = p[1]; f.Arg = p[2]; f.NameRu = p[3]; f.NameEn = p[4]; f.DescRu = p[5]; f.DescEn = p[6]; string fl = p.Length > 7 ? "," + p[7].Trim() + "," : ","; f.Default = fl.Contains(",default,") || fl.Contains(",switch,"); f.Switch = fl.Contains(",switch,"); d.Fixes.Add(f); }
                else if (k == "cmpentry" && p.Length >= 4) { CmpEntryPatch c = new CmpEntryPatch(); c.File = p[0].Trim(); c.Entry = p[1].Trim(); c.Orig = BytePatch.Hex(p[2].Trim()); c.Pat = BytePatch.Hex(p[3].Trim()); if (c.Orig.Length != c.Pat.Length) throw new FormatException("cmpentry: sizes differ"); d.CmpEntries.Add(c); }
                else if (k == "textrec" && p.Length >= 5) { TextRecPatch t = new TextRecPatch(); t.Glob = p[0].Trim(); t.Table = int.Parse(p[1]); t.Id = int.Parse(p[2]); t.RuText = p[3]; t.OtherText = p[4]; d.TextRecs.Add(t); }
                else if (k == "patch" && p.Length >= 4)
                {
                    BytePatch b = new BytePatch(); b.Id = p[0]; b.File = p[1]; b.Size = long.Parse(p[2]);
                    for (int i = 3; i < p.Length; i++)
                    {
                        if (p[i].StartsWith("append0:")) { b.AppendZero = long.Parse(p[i].Substring(8).Trim()); if (b.AppendZero > BytePatch.Grow) BytePatch.Grow = b.AppendZero; }
                        else if (p[i].StartsWith("append:")) { b.Append = BytePatch.Hex(p[i].Substring(7).Trim()); if (!BytePatch.Extra.Contains(b.Append.Length)) BytePatch.Extra.Add(b.Append.Length); }   // legacy tail (interp_legacy)
                        else if (p[i].StartsWith("needs:")) b.Needs = p[i].Substring(6).Trim();
                        else b.Points.Add(BytePatch.ParsePoint(p[i]));
                    }
                    d.Patches[b.Id] = b;
                }
            }
            if (!head) throw new InvalidDataException("gfx.txt: empty"); return d;
        }
    }

    // what the player wants (slot values, fixes on/off, picture scale); anything not mentioned stays as it is
    class GfxSel
    {
        public Dictionary<string, string> Slot = new Dictionary<string, string>(); public Dictionary<string, bool> Fix = new Dictionary<string, bool>();
        public int Scale = -1;   // -1 = leave the scale alone, 0 = auto, 100..200
        public Size Monitor = Size.Empty; public List<string> Reapply = new List<string>();   // set ids to install again (outdated)
        public GfxSel Copy() { GfxSel s = new GfxSel(); foreach (KeyValuePair<string, string> kv in Slot) s.Slot[kv.Key] = kv.Value; foreach (KeyValuePair<string, bool> kv in Fix) s.Fix[kv.Key] = kv.Value; s.Scale = Scale; s.Monitor = Monitor; s.Reapply.AddRange(Reapply); return s; }
    }
    class GfxStep
    {
        public string Kind = "", Id = "", Text = ""; public AssetManifest M; public bool On; public int Pct; public Size Monitor = Size.Empty; public bool Quiet;   // Quiet: a default fix - never shown to the player (only the log)   // Kind: revert-set | apply-set | fix | scale | patch (a byte patch that goes with a slot option)
    }
    class GfxPlan
    {
        public List<GfxStep> Steps = new List<GfxStep>(); public List<string> Problems = new List<string>(); public long Download, Installed; public Dictionary<string, AssetManifest> Man;
        public bool Empty { get { return Steps.Count == 0; } }
        public int UserSteps { get { int n = 0; foreach (GfxStep s in Steps) if (!s.Quiet) n++; return n; } }
        public bool UserEmpty { get { return UserSteps == 0; } }   // nothing the player has to know about: "No changes"
        // the text for the player (bottom bar, confirmations): the quiet steps never appear in it
        public string Summary(bool ru)
        {
            List<string> t = new List<string>(); foreach (GfxStep s in Steps) if (!s.Quiet && s.Text.Length > 0) t.Add(s.Text); return string.Join(", ", t.ToArray());
        }
        public string LogText() { List<string> t = new List<string>(); foreach (GfxStep s in Steps) t.Add(s.Kind + ":" + s.Id + (s.Kind == "fix" || s.Kind == "patch" ? (s.On ? "=on" : "=off") : "")); return string.Join(", ", t.ToArray()); }
    }

    partial class Core
    {
        public GfxDef Gfx { get { return GfxDef.Dd; } }

        // ---- what is installed now
        public GfxSel GfxCurrent()
        {
            GfxSel s = new GfxSel(); Dictionary<string, AssetRec> recs = new Dictionary<string, AssetRec>();
            try { foreach (AssetRec r in Assets.ActiveRecs()) recs[r.Id] = r; } catch { }
            foreach (GfxSlot sl in Gfx.Slots)
            {
                if (sl.Kind != "sets") continue; string v = "orig";
                foreach (GfxOpt o in sl.Opts) if (o.SetId.Length > 0 && GfxHasRec(o, recs)) v = o.Value;
                s.Slot[sl.Id] = v;
            }
            foreach (GfxFix f in Gfx.Fixes) s.Fix[f.Id] = GfxFixState(f) == "on";
            int pct; Size g; s.Scale = ScaleSaved(out pct, out g) ? pct : -1;
            return s;
        }
        static bool GfxHasRec(GfxOpt o, Dictionary<string, AssetRec> recs)
        {
            if (!o.PerSkin) return recs.ContainsKey(o.SetId);
            foreach (string id in recs.Keys) if (id.StartsWith(o.SetPrefix)) return true; return false;
        }
        // the set an option means for this choice: "windows-@ui" -> "windows-" + the chosen (or installed) interface skin
        public string GfxSetId(GfxOpt o, GfxSel sel, GfxSel cur)
        {
            if (!o.PerSkin) return o.SetId; string ui; if (sel == null || !sel.Slot.TryGetValue("ui", out ui)) ui = cur != null && cur.Slot.ContainsKey("ui") ? cur.Slot["ui"] : "orig";
            // the original interface has no archive 8 of its own: it is the one of the picture set (upscaling), so the kit comes in a form per picture ("windows-orig-v2"); a skin brings its own archive 8
            string pic; if (sel == null || !sel.Slot.TryGetValue("pic", out pic)) pic = cur != null && cur.Slot.ContainsKey("pic") ? cur.Slot["pic"] : "orig";
            return o.SetPrefix + ui + (ui == "orig" && pic != "orig" && pic.Length > 0 ? "-" + pic : "");
        }
        // "on" / "off" / "mixed" / "n/a"
        public string GfxFixState(GfxFix f)
        {
            if (!HasGame) return "n/a";
            if (f.Kind == "dusk") return !ExeSupported ? "n/a" : (DuskOn ? "on" : "off");
            if (f.Kind == "bytes") return BytePatchState(f.Arg);
            if (f.Kind == "floor") return FloorState();
            if (f.Kind == "floorsaves") { int t, x; return FloorSavesState(out t, out x); }
            return "n/a";
        }
        public static string FixStateWord(string st) { return st == "on" ? U.R("включено", "on") : (st == "off" ? U.R("выключено", "off") : (st == "mixed" ? U.R("частично", "partly") : U.R("недоступно", "unavailable"))); }

        // ---- compatibility of a whole choice: reasons (empty = fine)
        public List<string> GfxSetProblems(GfxSel sel, Dictionary<string, AssetManifest> man) { return GfxSetProblems(sel, man, false); }
        public List<string> GfxSetProblems(GfxSel sel, Dictionary<string, AssetManifest> man, bool ignoreMissing)   // only the sets: availability, requires/conflicts, files that do not fit together
        {
            List<string> bad = new List<string>(); List<AssetManifest> pick = new List<AssetManifest>(); List<GfxOpt> opts = new List<GfxOpt>(); GfxSel cur0 = null;
            foreach (GfxSlot sl in Gfx.Slots)
            {
                string v; if (sl.Kind != "sets" || !sel.Slot.TryGetValue(sl.Id, out v)) continue; GfxOpt o = sl.Find(v);
                if (o == null) { bad.Add(U.R("Неизвестное значение «" + v + "» у «" + sl.Id + "».", "Unknown value \"" + v + "\" for \"" + sl.Id + "\".")); continue; }
                if (o.SetId.Length == 0) continue; if (o.PerSkin && cur0 == null) cur0 = GfxCurrent(); AssetManifest m = null;
                if (o.PerSkin && man != null && man.Count > 0 && !man.ContainsKey(GfxSetId(o, sel, cur0))) { if (!ignoreMissing) bad.Add(U.R("«" + o.Name + "» пока не сделаны для выбранного интерфейса. Выберите «Оригинал», «Оригинал HD» или «Перерисованный».", "\"" + o.Name + "\" is not made for the chosen interface yet. Pick Original, Original HD or Redrawn.")); continue; }
                if (man == null || !man.TryGetValue(GfxSetId(o, sel, cur0), out m)) { if (!ignoreMissing) bad.Add(U.R("Набор «" + o.Name + "» ещё не скачан, а сервер наборов недоступен или набор ещё не опубликован. Подключитесь к интернету и повторите.", "The set \"" + o.Name + "\" is not downloaded yet, and the server is unreachable or the set is not published. Connect to the internet and try again.")); continue; }
                pick.Add(m); opts.Add(o);
            }
            for (int i = 0; i < pick.Count; i++)
            {
                AssetManifest a = pick[i];
                foreach (string c in a.Conflicts) foreach (AssetManifest b in pick) if (b.Id == c) bad.Add(U.R("«" + a.Name + "» не сочетается с «" + b.Name + "».", "\"" + a.Name + "\" cannot be combined with \"" + b.Name + "\"."));
                foreach (string r in a.Requires) { bool have = false; foreach (AssetManifest b in pick) if (b.Id == r) have = true; if (!have) bad.Add(U.R("«" + a.Name + "» требует набор «" + r + "».", "\"" + a.Name + "\" needs the set \"" + r + "\".")); }
                for (int j = 0; j < pick.Count; j++)
                {
                    AssetManifest lo = pick[i], up = pick[j]; if (i == j || lo.Layer >= up.Layer) continue;
                    foreach (AssetFile fu in up.Files) foreach (AssetFile fl in lo.Files)
                        if (string.Equals(fu.Path, fl.Path, StringComparison.OrdinalIgnoreCase) && Array.IndexOf(fu.Orig, fl.Sha) < 0 && !fu.IsNew)
                        { bad.Add(U.R("«" + up.Name + "» сделан для другой версии картинки, чем «" + lo.Name + "».", "\"" + up.Name + "\" was made for another picture version than \"" + lo.Name + "\".")); goto nextPair; }
                    nextPair:;
                }
                for (int j = i + 1; j < pick.Count; j++)   // same layer + same files: two sets would fight for one file
                    if (pick[j].Layer == a.Layer) foreach (AssetFile f1 in a.Files) foreach (AssetFile f2 in pick[j].Files) if (string.Equals(f1.Path, f2.Path, StringComparison.OrdinalIgnoreCase)) { bad.Add(U.R("«" + a.Name + "» и «" + pick[j].Name + "» заменяют одни и те же файлы.", "\"" + a.Name + "\" and \"" + pick[j].Name + "\" replace the same files.")); goto nextA; }
                nextA:;
            }
            return bad;
        }
        public List<string> GfxConflicts(GfxSel sel, Dictionary<string, AssetManifest> man)
        {
            List<string> bad = GfxSetProblems(sel, man);
            if (sel.Scale >= 0 && !Cnc) bad.Add(U.R("Размер интерфейса работает через gr-draw: сначала включите его.", "The interface size works through gr-draw: turn it on first."));
            foreach (GfxSlot sl in Gfx.Slots) { string v; if (sl.Kind != "sets" || !sel.Slot.TryGetValue(sl.Id, out v)) continue; GfxOpt o = sl.Find(v); if (o != null && o.Patch.Length > 0 && BytePatchState(o.Patch) == "n/a") bad.Add(U.R("«" + o.Name + "» не подходит для вашей версии игры (нужна div.exe 1.0.0.62).", "\"" + o.Name + "\" does not fit your game version (div.exe 1.0.0.62 is needed).")); }
            foreach (KeyValuePair<string, bool> kv in sel.Fix)
            {
                GfxFix f = Gfx.Fix(kv.Key); if (f == null) { bad.Add(U.R("Неизвестное исправление: ", "Unknown fix: ") + kv.Key); continue; }
                if (kv.Value && GfxFixState(f) == "n/a") bad.Add(U.R("Исправление «" + f.Id + "» недоступно для вашей версии игры или файлов.", "The fix \"" + f.Id + "\" is not available for your game version or files."));
            }
            return bad;
        }

        // ---- the plan: what to revert (top layers first), what to apply (lowest first), fixes, scale
        public GfxPlan GfxMakePlan(GfxSel sel, Dictionary<string, AssetManifest> man)
        {
            GfxPlan pl = new GfxPlan(); pl.Man = man; GfxSel cur = GfxCurrent();
            pl.Problems.AddRange(GfxConflicts(sel, man));
            Dictionary<string, AssetRec> active = new Dictionary<string, AssetRec>(); List<AssetRec> recs = new List<AssetRec>();
            try { foreach (AssetRec r in Assets.ActiveRecs()) { active[r.Id] = r; recs.Add(r); } } catch { }
            List<string> target = new List<string>(); Dictionary<string, GfxOpt> optOf = new Dictionary<string, GfxOpt>();
            foreach (GfxSlot sl in Gfx.Slots) { string v; if (sl.Kind != "sets") continue; if (!sel.Slot.TryGetValue(sl.Id, out v)) v = cur.Slot.ContainsKey(sl.Id) ? cur.Slot[sl.Id] : "orig"; GfxOpt o = sl.Find(v); if (o != null && o.SetId.Length > 0) { string rid = GfxSetId(o, sel, cur); target.Add(rid); optOf[rid] = o; } }
            List<string> rv = new List<string>();
            foreach (AssetRec r in recs) if (!target.Contains(r.Id) || sel.Reapply.Contains(r.Id)) rv.Add(r.Id);
            bool grow = true;   // everything that sits on a set that goes back goes back too (and is applied again if it is still wanted)
            while (grow) { grow = false; foreach (AssetRec x in recs) { if (rv.Contains(x.Id)) continue; foreach (string rid in rv.ToArray()) { AssetRec lo = active[rid]; if (x.EffLayer > lo.EffLayer && Overlap(x, lo)) { rv.Add(x.Id); grow = true; break; } } } }
            rv.Sort(delegate(string a, string b) { return active[b].EffLayer.CompareTo(active[a].EffLayer); });
            foreach (string id in rv) { GfxStep s = new GfxStep(); s.Kind = "revert-set"; s.Id = id; bool wanted = target.Contains(id); s.Text = wanted ? "" : U.R("убрать «" + active[id].Name + "»", "remove \"" + active[id].Name + "\""); pl.Steps.Add(s); }
            List<AssetManifest> ap = new List<AssetManifest>();
            foreach (string id in target) { AssetManifest m; if (!active.ContainsKey(id) || rv.Contains(id)) { if (man != null && man.TryGetValue(id, out m)) ap.Add(m); } }
            ap.Sort(delegate(AssetManifest a, AssetManifest b) { return a.Layer.CompareTo(b.Layer); });
            foreach (AssetManifest m in ap)
            {
                GfxStep s = new GfxStep(); s.Kind = "apply-set"; s.Id = m.Id; s.M = m; s.Text = U.R("«" + m.Name + "»", "\"" + m.Name + "\""); pl.Steps.Add(s);
                pl.Download += Assets.NeedBytes(m); pl.Installed += m.Installed;
            }
            foreach (GfxSlot sl in Gfx.Slots)   // byte patches that belong to an option (backpack: exe patch): on while the option is chosen, off otherwise
            {
                string v; if (sl.Kind != "sets") continue; if (!sel.Slot.TryGetValue(sl.Id, out v)) v = cur.Slot.ContainsKey(sl.Id) ? cur.Slot[sl.Id] : "orig";
                foreach (GfxOpt o in sl.Opts)
                {
                    if (o.Patch.Length == 0) continue; bool want = o.Value == v; string st = BytePatchState(o.Patch);
                    if (want ? st == "on" : (st == "off" || st == "n/a")) continue;
                    GfxStep s = new GfxStep(); s.Kind = "patch"; s.Id = o.Patch; s.On = want; s.Text = want ? U.R("правка игры для «" + o.Name + "»", "game patch for \"" + o.Name + "\"") : ""; s.Quiet = !want; pl.Steps.Add(s);
                }
            }
            foreach (GfxFix f in Gfx.Fixes)
            {
                bool want; if (!sel.Fix.TryGetValue(f.Id, out want)) continue; bool now = cur.Fix.ContainsKey(f.Id) && cur.Fix[f.Id];
                string st = GfxFixState(f); if (want == now && !(want && st == "mixed")) continue;
                GfxStep s = new GfxStep(); s.Kind = "fix"; s.Id = f.Id; s.On = want; s.Quiet = f.Default && !f.Switch; s.Text = f.Default && !f.Switch ? "" : (want ? "" : U.R("выключить ", "turn off ")) + f.Name; pl.Steps.Add(s);
            }
            if (sel.Scale >= 0 && sel.Scale != (cur.Scale < 0 ? 0 : cur.Scale)) {   // never saved = shown (and meant) as Auto: choosing Auto again is no change
                 GfxStep s = new GfxStep(); s.Kind = "scale"; s.Id = "scale"; s.Pct = sel.Scale; s.Monitor = sel.Monitor; s.Text = U.R("размер интерфейса ", "interface size ") + UiScale.PctText(sel.Scale); pl.Steps.Add(s); }
            return pl;
        }
        static bool Overlap(AssetRec a, AssetRec b) { foreach (AssetRecFile f in a.Files) foreach (AssetRecFile g in b.Files) if (string.Equals(f.Path, g.Path, StringComparison.OrdinalIgnoreCase)) return true; return false; }

        // ---- run the plan. Each step is atomic by itself; if one fails everything before it is put back (sets come from the cache), the error is passed on.
        public void GfxApply(GfxPlan pl, AssetProgress progress, Func<bool> cancel)
        {
            if (!HasGame) throw new InvalidOperationException(L.T("stNoGame")); if (GameRunning()) throw new InvalidOperationException(L.T("running"));
            if (pl.Problems.Count > 0) throw new InvalidOperationException(string.Join("\r\n", pl.Problems.ToArray()));
            GfxSel before = GfxCurrent(); int prevScale = before.Scale;
            bool wasOk = WinPackConsistency().Count == 0;
            try { GfxRun(pl, progress, cancel); if (wasOk) { List<string> inc = WinPackConsistency(); if (inc.Count > 0) throw new InvalidOperationException(inc[0]); } }   // the windows kit must end up whole (sprites >= what flat.cmp asks for)
            catch (CancelledEx) { throw; }
            catch (Exception ex)
            {
                Log("graphics: step failed: " + ex.Message + " - going back to the previous state");
                string note;
                try
                {
                    GfxSel back = before.Copy(); back.Scale = prevScale >= 0 && prevScale != GfxCurrent().Scale ? prevScale : -1;
                    GfxPlan bp = GfxMakePlan(back, pl.Man); bp.Problems.Clear(); GfxRun(bp, null, null); note = U.R("\r\n\r\nПрежнее состояние возвращено.", "\r\n\r\nThe previous state was restored.");
                }
                catch (Exception e2) { Log("graphics: rollback incomplete: " + e2.Message); note = U.R("\r\n\r\nВернуть прежнее состояние полностью не удалось: ", "\r\n\r\nThe previous state could not be fully restored: ") + e2.Message; }
                throw new IOException(ex.Message + note, ex);
            }
        }
        void GfxRun(GfxPlan pl, AssetProgress progress, Func<bool> cancel)
        {
            foreach (GfxStep s in pl.Steps)
            {
                if (cancel != null && cancel()) throw new CancelledEx();
                if (s.Kind == "revert-set") Assets.Revert(s.Id, progress, cancel);
                else if (s.Kind == "apply-set") Assets.Apply(s.M, progress, cancel);
                else if (s.Kind == "patch") SetBytePatch(s.Id, s.On);
                else if (s.Kind == "scale") ApplyScale(s.Pct, s.Monitor.IsEmpty ? ScreenPixels(System.Windows.Forms.Screen.PrimaryScreen) : s.Monitor);
                else if (s.Kind == "fix")
                {
                    GfxFix f = Gfx.Fix(s.Id);
                    if (f.Kind == "dusk") SetDusk(s.On); else if (f.Kind == "bytes") SetBytePatch(f.Arg, s.On); else if (f.Kind == "floor") SetFloor(s.On); else if (f.Kind == "floorsaves") SetFloorSaves(s.On);
                    if (f.Default) FixOptOut(f.Id, !s.On);   // switched off by the player: not turned on again by itself
                }
            }
        }
        // "Revert to original": every set off, the page's fixes off; scale/fonts/render have their own windows and stay
        public GfxSel GfxOriginalSel()
        {
            GfxSel s = new GfxSel(); foreach (GfxSlot sl in Gfx.Slots) if (sl.Kind == "sets") s.Slot[sl.Id] = "orig"; foreach (GfxFix f in Gfx.Fixes) s.Fix[f.Id] = false; return s;
        }

        // ---- quick setup / CLI --gfx-image --gfx-skin: "none" keeps, anything else is the value of an option (orig, v2, a..d); null error text = fine
        public GfxSel GfxQuickSel(string image, string skin, out string err)
        {
            err = null; GfxSel s = new GfxSel();
            foreach (string[] kv in new string[][] { new string[] { "pic", image }, new string[] { "ui", skin } })
            {
                if (kv[1] == null || kv[1].ToLowerInvariant() == "none") continue; GfxOpt o = Gfx.Slot(kv[0]).Find(kv[1].ToLowerInvariant());
                if (o == null) { err = kv[0] + ": " + kv[1]; return s; } s.Slot[kv[0]] = o.Value;
            }
            return s;
        }
        // ---- CLI: --gfx list | status | apply slot=value,... | revert
        public static GfxSel GfxParse(Core c, string arg, out List<string> errs)
        {
            errs = new List<string>(); GfxSel s = new GfxSel();
            foreach (string part in (arg ?? "").Split(new char[] { ',' }, StringSplitOptions.RemoveEmptyEntries))
            {
                int eq = part.IndexOf('='); if (eq <= 0) { errs.Add("ERROR --gfx apply: expected slot=value, got: " + part); continue; }
                string k = part.Substring(0, eq).Trim(), v = part.Substring(eq + 1).Trim(); GfxSlot sl = c.Gfx.Slot(k); GfxFix fx = c.Gfx.Fix(k);
                if (k == "scale") { int pct; if (UiScale.TryParsePct(v, out pct)) s.Scale = pct; else errs.Add("ERROR scale must be auto, 100, 125, 150 or 200, got: " + v); }
                else if (sl != null && sl.Kind == "sets") { if (sl.Find(v) == null) { errs.Add("ERROR " + k + ": unknown value " + v); continue; } s.Slot[k] = v; }
                else if (fx != null) { if (v != "on" && v != "off") errs.Add("ERROR " + k + " must be on or off, got: " + v); else s.Fix[k] = v == "on"; }
                else if (k == "reapply") s.Reapply.AddRange(v.Split('+'));
                else errs.Add("ERROR --gfx: unknown key " + k);
            }
            return s;
        }
        public static void GfxCli(Core c, string act, string arg, Size monitor, StringBuilder sb)
        {
            AssetSets a = c.Assets; string note; Dictionary<string, AssetManifest> man = new Dictionary<string, AssetManifest>();
            { foreach (AssetManifest m in a.LoadCatalog(out note)) man[m.Id] = m; if (note.Length > 0) sb.AppendLine("WARN " + note); }
            if (act == "apply" || act == "revert")
            {
                GfxSel sel; List<string> errs = new List<string>();
                if (act == "revert") sel = c.GfxOriginalSel(); else sel = GfxParse(c, arg, out errs);
                if (errs.Count > 0) throw new InvalidOperationException(string.Join("; ", errs.ToArray()));
                sel.Monitor = monitor; GfxPlan pl = c.GfxMakePlan(sel, man);
                sb.AppendLine("GFX-PLAN steps=" + pl.Steps.Count + " user=" + pl.UserSteps + " download=" + pl.Download + " installed=" + pl.Installed + " problems=" + pl.Problems.Count + " summary=[" + pl.Summary(L.Ru) + "]");
                foreach (GfxStep s in pl.Steps) sb.AppendLine("GFX-STEP " + s.Kind + " " + s.Id + (s.Kind == "fix" || s.Kind == "patch" ? " on=" + s.On : (s.Kind == "scale" ? " pct=" + s.Pct : "")));
                foreach (string p in pl.Problems) sb.AppendLine("GFX-PROBLEM " + p);
                if (pl.Problems.Count > 0) throw new InvalidOperationException(U.R("Выбор несовместим или недоступен, ничего не изменено.", "The choice is incompatible or unavailable; nothing was changed."));
                c.GfxApply(pl, delegate { }, null); sb.AppendLine("GFX-RESULT ok");
            }
            GfxSel now = c.GfxCurrent(); Dictionary<string, AssetQuick> quick = new Dictionary<string, AssetQuick>(); foreach (AssetQuick q in a.Quick()) quick[q.Rec.Id] = q;
            foreach (GfxSlot sl in c.Gfx.Slots)
            {
                if (sl.Kind != "sets") { sb.AppendLine("GFX-SLOT id=" + sl.Id + " kind=" + sl.Kind + (sl.Id == "scale" ? " current=" + (now.Scale < 0 ? "none" : UiScale.PctText(now.Scale)) : "")); continue; }
                sb.AppendLine("GFX-SLOT id=" + sl.Id + " kind=sets current=" + now.Slot[sl.Id]);
                foreach (GfxOpt o in sl.Opts)
                {
                    string rsid = o.SetId.Length > 0 ? c.GfxSetId(o, null, now) : ""; AssetManifest m = null; if (o.SetId.Length > 0) man.TryGetValue(rsid, out m);
                    string st = o.SetId.Length == 0 ? (now.Slot[sl.Id] == "orig" ? "current" : "available") : (m == null ? "unavailable" : GfxOptWord(c, o, m, quick, now));
                    sb.AppendLine("GFX-OPT slot=" + sl.Id + " value=" + o.Value + " set=" + (o.SetId.Length == 0 ? "-" : rsid) + " status=" + st + " name=" + o.NameEn.Replace(" ", "_") + " preview=" + o.Prev + " approxMb=" + o.ApproxMb + (m != null ? " download=" + a.NeedBytes(m) + " installed=" + m.Installed : ""));
                }
            }
            if (c.HasGame && c.Gfx.Patches.ContainsKey("windows")) sb.AppendLine("GFX-WINPACK exe=" + c.BytePatchState("windows") + " data=" + c.WinPackDataState() + " problems=" + c.WinPackConsistency().Count + " glow=" + c.BytePatchState("glow") + " interp=" + c.BytePatchState("interp") + " frame=" + c.BytePatchState("frame") + " tick80=" + c.BytePatchState("tick80") + " exelen=" + new System.IO.FileInfo(c.Exe).Length + " ru=" + c.GameRussian);
            foreach (GfxFix f in c.Gfx.Fixes) sb.AppendLine("GFX-FIX id=" + f.Id + " state=" + c.GfxFixState(f) + " default=" + f.Default + " optout=" + c.FixOptedOut(f.Id));
        }
        // installed | outdated | mixed | cached | notdl
        public static string GfxOptWord(Core c, GfxOpt o, AssetManifest m, Dictionary<string, AssetQuick> quick, GfxSel now)
        {
            AssetQuick q; if (quick.TryGetValue(m.Id, out q)) return !q.Intact ? "mixed" : (q.Rec.Version != m.Version ? "outdated" : "installed");
            return c.Assets.IsCached(m) ? "cached" : "notdl";
        }
    }
}
