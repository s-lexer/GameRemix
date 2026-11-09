// Fonts (game "fonts" folder) + embedded third-party tools. Part of DD_FixTool.
using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;

namespace DDFixTool
{
    partial class Core
    {
        // ---- fonts. Groups: 0 = general, 1 = books/diary, 2 = dialogs. Steps: 0 = original, 1 = larger, 2 = extra large (scaled by us, any language), 3 = the owner's Russian pack, 4 = that pack scaled (dialogs x1.25, books x1.3, general x1.4).
        //  general:  1 = every size uses the biggest font (size 1);  2 = size 1 scaled x1.4;  3 = pack fonts for sizes 2..5
        //  books:    1 = black1/black2 scaled x1.2;                  2 = x1.4;                3 = pack (embedded)
        //  dialogs:  1 = the game's biggest fonts (fontn1 ...);      2 = originals scaled x1.3;  3 = pack (embedded)
        //  Embedded files are built by analysis/build_fonts.py. Scaling keeps every colour; the UI offers {original, pack} in Russian and {original, larger, extra large} in English.
        string FontsDir { get { return P("fonts"); } }
        string FBak { get { return Path.Combine(BakDir, "fonts"); } }
        static readonly string[] FontCols = { "b", "go", "gr", "gra", "n", "or", "red", "yel" };
        public bool FontsAvail { get { return HasGame && Directory.Exists(FontsDir) && File.Exists(Path.Combine(FontsDir, "fontn1.fnt")); } }

        public string[] FontTargets(int cat)
        {
            List<string> l = new List<string>();
            if (cat == 0) { foreach (string c in FontCols) for (int k = 1; k <= 5; k++) l.Add("font" + c + k + ".fnt"); }
            else if (cat == 1) { l.Add("fontblack1.fnt"); l.Add("fontblack2.fnt"); }
            else { l.Add("dialog_white.fnt"); l.Add("dialog_yellow.fnt"); l.Add("dialog_red.fnt"); l.Add("dialog_grey.fnt"); }
            return l.ToArray();
        }
        // original content of a font: our backup, else the "name-.fnt" copy left by the old batch patch, else the file itself
        string FontOrig(string name)
        {
            string b = Path.Combine(FBak, name); if (File.Exists(b)) return b;
            string m = Path.Combine(FontsDir, Path.GetFileNameWithoutExtension(name) + "-.fnt"); if (File.Exists(m)) return m;
            return Path.Combine(FontsDir, name);
        }
        static byte[] Fx(string key)   // embedded gzip resource "fx_<key>"
        {
            using (MemoryStream gz = new MemoryStream(Res("fx_" + key)))
            using (GZipStream z = new GZipStream(gz, CompressionMode.Decompress))
            using (MemoryStream ms = new MemoryStream())
            { byte[] buf = new byte[65536]; int n; while ((n = z.Read(buf, 0, buf.Length)) > 0) ms.Write(buf, 0, n); return ms.ToArray(); }
        }
        static string ColOf(string t) { string r = t.Substring(4, t.Length - 9); return r; }   // fontgr3.fnt -> "gr"
        // what a target file holds at a given step (null = no such step for the group)
        public byte[] FontSrc(int cat, int step, string t)
        {
            try
            {
                if (step == 0) { string f = FontOrig(t); return File.Exists(f) ? File.ReadAllBytes(f) : null; }
                if (cat == 0)
                {
                    string col = ColOf(t); byte[] o1 = File.ReadAllBytes(FontOrig("font" + col + "1.fnt"));
                    if (step == 4) return col == "gra" ? Fx("g_gra.fnt") : Fx("ps_pg_" + col + ".fnt");
                    if (step == 2) return Fx("g_" + col + ".fnt");
                    if (step == 3 && !t.EndsWith("1.fnt") && col != "gra") return Fx("pg_" + col + ".fnt");
                    return o1;
                }
                if (cat == 1) return step == 4 ? Fx("ps_pk_" + t) : step == 3 ? Fx("pk_" + t) : Fx((step == 1 ? "bk1_" : "bk2_") + t);
                if (step == 4) return Fx("ps_dlg_" + t);
                if (step == 3) return Fx("dlg_" + t);
                if (step == 2) return Fx("dlg2_" + t);
                string src = t == "dialog_white.fnt" ? "fontn1.fnt" : t == "dialog_yellow.fnt" ? "fontyel1.fnt" : t == "dialog_red.fnt" ? "fontred1.fnt" : "fontgra1.fnt";
                return File.ReadAllBytes(FontOrig(src));
            }
            catch { return null; }
        }
        static bool SameBytes(string file, byte[] b)
        {
            if (b == null || !File.Exists(file) || new FileInfo(file).Length != b.Length) return false;
            byte[] x = File.ReadAllBytes(file); for (int i = 0; i < x.Length; i++) if (x[i] != b[i]) return false; return true;
        }
        // 0 original / custom, 1 larger, 2 extra large, -1 not available
        public int FontStep(int cat)
        {
            if (!FontsAvail) return -1;
            for (int step = 4; step >= 1; step--)
            {
                bool all = true;
                foreach (string t in FontTargets(cat)) if (!SameBytes(Path.Combine(FontsDir, t), FontSrc(cat, step, t))) { all = false; break; }
                if (all) return step;
            }
            return 0;
        }
        // MD5 of the 1.0.11 "redrawn" fonts (withdrawn: the game drew wrong letters; the glyph count in the header did not match the records). Not embedded any more; such files are
        // recognised only so they are never taken for the player's own fonts, and the Fonts window offers to put the original back.
        static readonly string[] BrokenRd = { "0945b3ae6395d6adfcf7351f7de7d946","24d3fc31d02f5da85bc1259f721c4d62","2b842e8a49c45d989f832e7b5d02d4ff","415672a22829dd8571e9b92bce363b81","45aec1e0fe470c51d0cf898a4504d86d","497f4c43f96f1f99eec320635f7f2bd4","61e273c75d768519aba19063b19c4811","7e2e1e2cf463fb06165483011f94976c","8d2e44aa47c82d9872508c719a07bad3","979b48abf539855cac688af2a15d919a","9c584b9bd15b684f3e83e4e08bf29937","a9a7e6d8cfebd1df75c54339d771651e","bc59d7fa8168ddea8945b6c10f883194","c2381650b302bc9d924651f2815e3903","c738bfe7126ba54027de55c989ed9cf3","dcd95decde1606ac5d624ade99ddf04e","ed51188a2ead9eba3fbc90cacc1a9c38","f96cde13edb818f421ec2792b0e9b895","fc2a0377d8c852d0404887cde96792eb" };
        static bool IsBrokenRd(string file)
        {
            try { if (!File.Exists(file)) return false; using (System.Security.Cryptography.MD5 m = System.Security.Cryptography.MD5.Create()) { string h = BitConverter.ToString(m.ComputeHash(File.ReadAllBytes(file))).Replace("-", "").ToLowerInvariant(); return Array.IndexOf(BrokenRd, h) >= 0; } }
            catch { return false; }
        }
        public bool FontIsBrokenRd(int cat) { if (!FontsAvail) return false; foreach (string t in FontTargets(cat)) if (IsBrokenRd(Path.Combine(FontsDir, t))) return true; return false; }
        // a file that is exactly one of OUR outputs (never counts as an original, never gets backed up as one)
        bool IsOursFile(int cat, string t, string cur)
        {
            if (IsBrokenRd(cur)) return true;
            for (int step = 1; step <= 4; step++)
            {
                if (step == 1 && cat == 0 && t.EndsWith("1.fnt")) continue;   // general step 1 leaves the size-1 fonts as they were
                if (SameBytes(cur, FontSrc(cat, step, t))) return true;
            }
            return false;
        }
        static bool SameFiles(string a, string b) { if (!File.Exists(a) || !File.Exists(b) || new FileInfo(a).Length != new FileInfo(b).Length) return false; return SameBytes(a, File.ReadAllBytes(b)); }
        // the group holds the player's OWN font files: not ours, not the original we backed up (a mixed / hand-edited state, shown separately in the UI)
        public bool FontIsCustom(int cat)
        {
            if (!FontsAvail || FontStep(cat) != 0) return false;
            foreach (string t in FontTargets(cat)) { string bak = Path.Combine(FBak, t), cur = Path.Combine(FontsDir, t); if (File.Exists(bak) && File.Exists(cur) && !SameFiles(cur, bak) && !IsOursFile(cat, t, cur)) return true; }
            return false;
        }
        // before a font file of the player's own is overwritten it is copied to backup\fonts_user (never silently lost)
        void KeepUserFont(string t, string cur)
        {
            string d = Path.Combine(BakDir, "fonts_user"); Directory.CreateDirectory(d); string dst = Path.Combine(d, t);
            for (int n = 2; File.Exists(dst) && !SameFiles(dst, cur); n++) dst = Path.Combine(d, Path.GetFileNameWithoutExtension(t) + "." + n + ".fnt");
            if (!File.Exists(dst)) File.Copy(cur, dst);
            Log("fonts: the player's own file " + t + " saved to " + d);   // silent on purpose (owner 06.11: no dialog); only the log
        }
        public int FontState(int cat) { int s = FontStep(cat); return s < 0 ? -1 : (s >= 1 ? 1 : 0); }
        public void SetFont(int cat, bool big) { SetFontStep(cat, big ? 1 : 0); }
        public void SetFontStep(int cat, int step)
        {
            if (!FontsAvail) throw new InvalidOperationException("fonts");
            foreach (string t in FontTargets(cat))   // backups first: step 1 reads original files that step 2 overwrites
            {
                string dst = Path.Combine(FBak, t), mark = Path.Combine(FontsDir, Path.GetFileNameWithoutExtension(t) + "-.fnt"), cur = Path.Combine(FontsDir, t);
                if (!File.Exists(dst))
                {   // the first time: the "original" is the old batch patch's copy, else the current file - but never a file that is already OUR output
                    string from = File.Exists(mark) ? mark : (File.Exists(cur) && !IsOursFile(cat, t, cur) ? cur : null);
                    if (from != null) { Directory.CreateDirectory(FBak); File.Copy(from, dst); }
                }
                else if (File.Exists(cur) && !SameFiles(cur, dst) && !IsOursFile(cat, t, cur)) KeepUserFont(t, cur);   // changed by the player after our backup: keep their copy
            }
            Dictionary<string, byte[]> src = new Dictionary<string, byte[]>();
            foreach (string t in FontTargets(cat)) { byte[] b = FontSrc(cat, step, t); if (b == null) throw new InvalidOperationException("font " + t); src[t] = b; }
            int n = 0;
            foreach (string t in FontTargets(cat)) { string tp = Path.Combine(FontsDir, t); if (!SameBytes(tp, src[t])) { File.WriteAllBytes(tp, src[t]); n++; } }
            Log((step > 0 ? L.T("applied") : L.T("reverted")) + "fonts[" + cat + "] step " + step + " x" + n);
        }
        // "revert everything": put back only what this tool changed
        public void RevertFonts()
        {
            if (!Directory.Exists(FBak)) return;
            List<string> fail = new List<string>();
            foreach (string f in Directory.GetFiles(FBak))
            {
                string t = Path.GetFileName(f), cur = Path.Combine(FontsDir, t);
                try
                {
                    if (File.Exists(cur) && !SameFiles(cur, f)) { int cat = Array.IndexOf(FontTargets(1), t) >= 0 ? 1 : (Array.IndexOf(FontTargets(2), t) >= 0 ? 2 : 0); if (!IsOursFile(cat, t, cur)) KeepUserFont(t, cur); }
                    File.Copy(f, cur, true);
                }
                catch (Exception ex) { fail.Add(t + ": " + ex.Message); }
            }
            if (fail.Count > 0) throw new IOException((U.R("Не все шрифты вернулись, резервные копии оставлены в ", "Not every font was restored, the backups are kept in ")) + FBak + ":\n" + string.Join("\n", fail.ToArray()));
            Directory.Delete(FBak, true); Log(L.T("reverted") + "fonts");
        }

        // ---- savegame backup: copies savegames (and savegames2) to <game>\savegames_backup\<timestamp>
        public string BackupSaves()
        {
            string dst = Path.Combine(P("savegames_backup"), DateTime.Now.ToString("yyyy-MM-dd_HH-mm-ss")); int n = 0;
            foreach (string sd in new string[] { "savegames", "savegames2" })
                if (Directory.Exists(P(sd))) n += CopyDir(P(sd), Path.Combine(dst, sd));
            if (n == 0) throw new InvalidOperationException(U.R("Сохранений не найдено.", "No saves found."));
            Log(L.T("applied") + dst + " (" + n + ")"); return dst;
        }
        static int CopyDir(string src, string dst)
        {
            Directory.CreateDirectory(dst); int n = 0;
            foreach (string f in Directory.GetFiles(src)) { File.Copy(f, Path.Combine(dst, Path.GetFileName(f)), true); n++; }
            foreach (string d in Directory.GetDirectories(src)) n += CopyDir(d, Path.Combine(dst, Path.GetFileName(d)));
            return n;
        }

        // ---- embedded third-party tools (gzip resources "tool_<name>") unpacked to %LOCALAPPDATA%\DD_FixTool\tools
        public static string ToolPath(string name)
        {
            string d = Path.Combine(App.LocalDir, "tools");
            Directory.CreateDirectory(d);
            string f = Path.Combine(d, name);
            using (MemoryStream gz = new MemoryStream(Res("tool_" + name)))
            using (GZipStream z = new GZipStream(gz, CompressionMode.Decompress))
            using (MemoryStream ms = new MemoryStream())
            {
                byte[] buf = new byte[65536]; int n; while ((n = z.Read(buf, 0, buf.Length)) > 0) ms.Write(buf, 0, n);
                byte[] data = ms.ToArray();   // compared by content hash, not by size: a same-size but different file is replaced too
                bool same = false; try { same = File.Exists(f) && Net.Sha256File(f) == Net.Sha256Bytes(data); } catch { }
                if (!same) { try { File.WriteAllBytes(f, data); } catch (IOException) { if (!File.Exists(f)) throw; } }   // a copy that is running right now keeps its file
            }
            return f;
        }
    }
}
