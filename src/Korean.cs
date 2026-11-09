// Korean language pack for the ENGLISH game (owner 09.11.2026). The pack (text.cmp, dialogtxt.dat, mono.cmp, itemgen.cmp + khangul.dll, the Hangul font hook) is embedded in the program:
// games/divine-divinity/payload/korean/ (built by games/divine-divinity/korean/build_payload.py, manifest korean.txt). khangul.dll is loaded by div.exe INSTEAD of VERSION.dll
// (patch=korean in gfx.txt renames the import: a table of div.exe like the others, so --sync keeps it) and patches the font code in memory; it passes the 3 VERSION.dll calls on.
// Install = copies of the verified English originals (GameData\korean\orig), the pack written over them, khangul.dll, "use8bitfont 0" in config.div, the exe patch; one journal line
// "korean" (install.txt) names what is ours. Revert = every file that still is ours goes back from the copy; a file changed by the player is left (logged).
// The Russian game keeps its texts in another form (localizations\german, other dialogue file): the pack does not fit it, the install refuses with a message and writes nothing.
using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Text;
using System.Text.RegularExpressions;

namespace DDFixTool
{
    partial class Core
    {
        class KoFile { public string Rel, Res, Sha, Orig; }
        static List<KoFile> koFiles; static string koDllRes, koDllSha;
        static void KoLoad()
        {
            if (koFiles != null) return;
            List<KoFile> l = new List<KoFile>();
            foreach (string ln in Encoding.UTF8.GetString(Res("korean_manifest")).Split('\n'))
            {
                string s = ln.Trim(); string[] p;
                if (s.StartsWith("file=")) { p = s.Substring(5).Split('|'); KoFile f = new KoFile(); f.Rel = p[0]; f.Res = p[1]; f.Sha = p[2]; f.Orig = p[3]; l.Add(f); }
                else if (s.StartsWith("embed=")) { p = s.Substring(6).Split('|'); koDllRes = p[1]; koDllSha = p[2]; }
            }
            koFiles = l;
        }
        static byte[] ResGz(string name)
        {
            using (GZipStream g = new GZipStream(new MemoryStream(Res(name)), CompressionMode.Decompress))
            using (MemoryStream o = new MemoryStream()) { g.CopyTo(o); return o.ToArray(); }
        }
        const string KoCfgMark = "// Korean build: TrueType fonts";
        string KoOrig(string rel) { return Path.Combine(KoDir, "orig", rel.Replace('\\', '_')); }
        public string KoDir { get { return Path.Combine(GameData, "korean"); } }

        // sha256 of a game file as the pack knows it; our "Sort" string of the Large windows kit in text.cmp is not counted (it comes and goes on its own)
        string KoNormSha(string rel)
        {
            string f = P(rel); if (!File.Exists(f)) return null;
            byte[] b = File.ReadAllBytes(f);
            if (rel.EndsWith("text.cmp", StringComparison.OrdinalIgnoreCase) && GfxDef.Dd != null && GfxDef.Dd.TextRecs.Count > 0)
            {
                try
                {
                    TextCmp tc = TextCmp.Parse(b); bool cut = false;
                    foreach (TextRecPatch t in GfxDef.Dd.TextRecs) { TextCmp.Rec r = tc.Get((uint)t.Table, (uint)t.Id); if (r != null && (CmpFile.Same(r.S1, TextBytes(t, true)) || CmpFile.Same(r.S1, TextBytes(t, false)))) { tc.Remove((uint)t.Table, (uint)t.Id); cut = true; } }
                    if (cut) return Net.Sha256Bytes(tc.ToBytes());
                }
                catch (Exception) { }
            }
            if (GfxDef.Dd != null && GfxDef.Dd.CmpEntries.Count > 0)   // global.cmp: the entry the Large windows kit edits in place counts as the original
            {
                try
                {
                    bool cut = false; b = (byte[])b.Clone();
                    foreach (CmpEntryPatch c in GfxDef.Dd.CmpEntries)
                    {
                        if (!string.Equals(c.File.Replace('/', '\\'), rel, StringComparison.OrdinalIgnoreCase)) continue;
                        long off; int sz; using (MemoryStream ms = new MemoryStream(b)) { if (!CmpFile.Find(ms, c.Entry, out off, out sz) || sz != c.Pat.Length) continue; }
                        byte[] cur = new byte[sz]; Array.Copy(b, off, cur, 0, sz); if (CmpFile.Same(cur, c.Pat)) { Array.Copy(c.Orig, 0, b, off, sz); cut = true; }
                    }
                    if (cut) return Net.Sha256Bytes(b);
                }
                catch (Exception) { }
            }
            return Net.Sha256Bytes(b);
        }
        // text.cmp bytes >= 0xC0 mean Cyrillic only in a Russian file; the Korean one (CP949) has them too: once the pack is installed the file is ours, not Russian
        bool RuText(TextCmp tc) { return tc.IsRussian() && JGet("korean") == null; }

        // null = the pack can be installed (or is installed and may be switched off); otherwise the reason, in the language of the interface
        public string KoreanWhyNot()
        {
            if (!HasGame) return L.T("stNoGame");
            if (JGet("korean") != null) return null;
            if (!ExeSupported) return L.T("stBadExe");
            if (GameRussian) return U.R("Корейский перевод делается для английской версии игры (папка localizations\\english). У вас русская: её тексты и диалоги устроены иначе, перевод к ним не подходит — ничего не изменено.",
                "The Korean translation is made for the English version of the game (localizations\\english). Yours is the Russian one: its texts and dialogues are built differently, so the translation does not fit — nothing was changed.");
            KoLoad();
            foreach (KoFile f in koFiles)
            {
                string s = KoNormSha(f.Rel);
                if (s == null) return U.R("Не найден файл " + f.Rel + ": нужна английская версия игры.", "File not found: " + f.Rel + " (the English version of the game is needed).");
                if (s == f.Sha) return U.R("Корейские файлы уже лежат в папке игры (поставлены вручную): сначала верните английские, иначе программа не сможет их откатить.", "Korean files are already in the game folder (put in by hand): restore the English ones first, otherwise the program could not revert them.");
                if (s != f.Orig) return U.R("Файл " + f.Rel + " не оригинальный (другая версия игры или чужая правка): перевод не ставлю, чтобы ничего не испортить.", "The file " + f.Rel + " is not the original (another game version or a foreign edit): the translation was not installed so that nothing gets broken.");
            }
            return null;
        }
        // "off" / "on" / "mixed" / "n/a"
        public string KoreanState()
        {
            if (!HasGame) return "n/a"; KoLoad(); JournalRec j = JGet("korean"); string ex = BytePatchState("korean");
            if (j == null) return ex == "on" || ex == "mixed" ? "mixed" : "off";
            foreach (KoFile f in koFiles) { string s = j.Sha(f.Rel); if (s == null || KoNormSha(f.Rel) != s) return "mixed"; }
            string d = j.Sha("khangul.dll"); if (d == null || !File.Exists(P("khangul.dll")) || Net.Sha256File(P("khangul.dll")) != d) return "mixed";
            return ex == "on" ? "on" : "mixed";
        }

        void KoCfgSet(bool on)
        {
            string f = P("config.div"); if (!File.Exists(f)) { if (on) { File.WriteAllText(f, KoCfgMark + "\r\nuse8bitfont 0\r\n", Encoding.GetEncoding(28591)); } return; }
            Encoding en = Encoding.GetEncoding(28591); string t = en.GetString(File.ReadAllBytes(f));
            t = Regex.Replace(t, @"(?m)^" + Regex.Escape(KoCfgMark) + @"\r?\n", ""); t = Regex.Replace(t, @"(?m)^use8bitfont\s+\d+\s*\r?\n?", "");
            if (on) t = t.TrimEnd() + "\r\n\r\n" + KoCfgMark + "\r\nuse8bitfont 0\r\n";
            AtomicWrite(f, en.GetBytes(t));
        }

        public void SetKorean(bool on)
        {
            if (!HasGame) throw new InvalidOperationException(L.T("stNoGame")); if (GameRunning()) throw new InvalidOperationException(L.T("running"));
            KoLoad(); JournalRec j = JGet("korean");
            if (on) { string why = KoreanWhyNot(); if (why != null) throw new InvalidOperationException(why); }
            else if (j == null) { if (BytePatchState("korean") == "on") SetBytePatch("korean", false); return; }
            bool wp = WinPackDataState() == "on";   // the Sort label of the Large windows kit sits in text.cmp: taken out first, put back at the end
            if (wp) SetWinPackData(false);
            try
            {
                if (on)
                {
                    Directory.CreateDirectory(Path.Combine(KoDir, "orig"));
                    foreach (KoFile f in koFiles)
                    {
                        string bak = KoOrig(f.Rel), cs = KoNormSha(f.Rel);
                        if (!File.Exists(bak)) { if (cs != f.Orig) throw new InvalidOperationException(f.Rel + ": not the original"); File.Copy(P(f.Rel), bak); }
                        else if (cs != f.Orig && cs != f.Sha && (j == null || cs != j.Sha(f.Rel))) throw new InvalidOperationException(U.R("Файл изменён вне программы: ", "The file was changed outside the program: ") + f.Rel);
                    }
                    string cbak = Path.Combine(KoDir, "orig", "config.div"); if (!File.Exists(cbak) && File.Exists(P("config.div"))) File.Copy(P("config.div"), cbak);
                    foreach (KoFile f in koFiles) AtomicWrite(P(f.Rel), ResGz(f.Res));
                    AtomicWrite(P("khangul.dll"), Res(koDllRes)); KoCfgSet(true);
                    JournalRec r = new JournalRec(); r.Comp = "korean"; r.Opts = "ko";
                    foreach (KoFile f in koFiles) r.Files[f.Rel] = f.Sha;
                    r.Files["khangul.dll"] = koDllSha; r.Files["config.div"] = Net.Sha256File(P("config.div")); JPut(r);
                    SetBytePatch("korean", true);
                    Log(L.T("applied") + "Korean language pack");
                }
                else
                {
                    SetBytePatch("korean", false);   // the exe first: never a game that asks for khangul.dll when the file is gone
                    foreach (KoFile f in koFiles)
                    {
                        string cur = P(f.Rel), bak = KoOrig(f.Rel);
                        if (KoNormSha(f.Rel) != j.Sha(f.Rel)) { Log("Korean: " + f.Rel + " was changed outside the program, left as is"); continue; }
                        if (File.Exists(bak) && Net.Sha256File(bak) == f.Orig) AtomicWrite(cur, File.ReadAllBytes(bak)); else Log("Korean: no original copy of " + f.Rel + ", left as is");
                    }
                    string dll = P("khangul.dll"); if (File.Exists(dll) && Net.Sha256File(dll) == j.Sha("khangul.dll")) TryDel(dll); else if (File.Exists(dll)) Log("Korean: khangul.dll was changed outside the program, left as is");
                    TryDel(P("khangul.log")); KoCfgSet(false);
                    string cbak = Path.Combine(KoDir, "orig", "config.div"); string cj = j.Sha("config.div");
                    if (File.Exists(cbak) && File.Exists(P("config.div")) && cj != null && Net.Sha256File(P("config.div")) == cj) AtomicWrite(P("config.div"), File.ReadAllBytes(cbak));
                    JDrop("korean"); Log(L.T("reverted") + "Korean language pack");
                }
            }
            catch (Exception)
            {
                if (on && j == null) { try { KoRollback(); } catch (Exception ex2) { Log("Korean: rollback failed: " + ex2.Message); } }
                throw;
            }
            finally { if (wp) { try { SetWinPackData(true); } catch (Exception ex3) { Log("Korean: the Sort label of the Large windows could not be put back: " + ex3.Message); } } }
        }
        // a failed first install: whatever was written goes back from the copies (the journal line is dropped, the exe patch taken out)
        void KoRollback()
        {
            try { if (BytePatchState("korean") == "on" || BytePatchState("korean") == "mixed") SetBytePatch("korean", false); } catch (Exception ex) { Log("Korean rollback (exe): " + ex.Message); }
            foreach (KoFile f in koFiles) { string bak = KoOrig(f.Rel); if (File.Exists(bak) && Net.Sha256File(bak) == f.Orig && KoNormSha(f.Rel) == f.Sha) AtomicWrite(P(f.Rel), File.ReadAllBytes(bak)); }
            string dll = P("khangul.dll"); if (File.Exists(dll) && Net.Sha256File(dll) == koDllSha) TryDel(dll);
            KoCfgSet(false); string cbak = Path.Combine(KoDir, "orig", "config.div"); if (File.Exists(cbak) && File.Exists(P("config.div"))) AtomicWrite(P("config.div"), File.ReadAllBytes(cbak));
            JDrop("korean");
        }
        // start-up: the program carries a newer pack than the one in the game and every file is still ours -> written again (a file the player changed stops the refresh)
        void KoreanRefresh()
        {
            JournalRec j = JGet("korean"); if (j == null) return; KoLoad(); bool newer = false;
            foreach (KoFile f in koFiles)
            {
                string s = KoNormSha(f.Rel), js = j.Sha(f.Rel);
                if (js == null && s == f.Orig) { newer = true; continue; }   // a file the older pack did not carry (books and diary came later), still the original
                if (s != js) { Log("Korean: " + f.Rel + " is not as recorded, not refreshed"); return; }
                if (js != f.Sha) newer = true;
            }
            if (j.Sha("khangul.dll") != koDllSha) newer = true;
            if (newer) { Log("start-up: Korean pack updated to the program's current copy"); SetKorean(true); }
        }
    }
}
