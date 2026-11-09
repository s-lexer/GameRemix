// "Install as if from scratch" (owner 07.11.2026, docs/TASK_install_monolith_2026-11-07.md): the program never patches on top of what an older version left; it rebuilds.
//   Journal  - GameData\install.txt (next to BakDir), one line per component: component|program_version|path=sha256;...|options. The source of truth for "what in the game folder is
//              ours and of which version". Written only after the files are in place, atomically (.tmp -> Replace).
//   div.exe  - the wanted set of exe patches (voice, dusk, the Graphics-page tables, tick80...) is kept in the journal ("exe" options). Every change = a copy of the VERIFIED original
//              (div.exe.orig, sha256 of 1.0.0.62) + every current table of the enabled patches -> one atomic replace of div.exe. Old forms of a patch (tick80_v*, the 0x13 sort key,
//              stray bytes of test builds, the 4096-byte interpolation tail) are only read ONCE, to learn which patches were on, then they vanish with the rebuild.
//   Embedded - our files in the game folder (gr-draw ddraw.dll + licences + shaders, dgVoodoo, the voice DLLs): a file that still has the sha we wrote is replaced when the program carries a
//              newer one; a file the user changed is left as it is (logged).
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

namespace DDFixTool
{
    class JournalRec
    {
        public string Comp = "", Ver = "", Opts = ""; public Dictionary<string, string> Files = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        public string Sha(string rel) { string s; return Files.TryGetValue(rel, out s) ? s : null; }
        public string Line() { List<string> f = new List<string>(); foreach (KeyValuePair<string, string> kv in Files) f.Add(kv.Key + "=" + kv.Value); return Comp + "|" + Ver + "|" + string.Join(";", f.ToArray()) + "|" + Opts; }
        public static JournalRec Parse(string ln)
        {
            string[] p = ln.Split('|'); if (p.Length < 4 || p[0].Trim().Length == 0) return null;
            JournalRec r = new JournalRec(); r.Comp = p[0].Trim(); r.Ver = p[1].Trim(); r.Opts = p[3].Trim();
            foreach (string kv in p[2].Split(';')) { int e = kv.LastIndexOf('='); if (e > 0) r.Files[kv.Substring(0, e)] = kv.Substring(e + 1).Trim().ToLowerInvariant(); }
            return r;
        }
    }

    partial class Core
    {
        // sha256 of div.exe 1.0.0.62 (the Russian and the English game ship the same file): the ONLY content div.exe.orig may ever hold
        public const string ExeOrigSha = "cd9f7a07c7a605c21052b3517346c7a63083063fb491276a3e4c9836c9b42a67";

        // ---------------------------------------------------------------- journal
        string JournalFile { get { return Path.Combine(GameData, "install.txt"); } }
        // strict = the caller rewrites the journal: a read error then throws (an empty list would drop every other component's line)
        List<JournalRec> JLoad() { return JLoad(false); }
        List<JournalRec> JLoad(bool strict)
        {
            List<JournalRec> l = new List<JournalRec>();
            try { if (File.Exists(JournalFile)) foreach (string s in File.ReadAllLines(JournalFile, Encoding.UTF8)) { if (s.Trim().Length == 0 || s.StartsWith("#")) continue; JournalRec r = JournalRec.Parse(s); if (r != null) l.Add(r); } }
            catch (IOException ex) { Log("install.txt: " + ex.Message); if (strict) throw; }
            return l;
        }
        public JournalRec JGet(string comp) { foreach (JournalRec r in JLoad()) if (r.Comp == comp) return r; return null; }
        void JPut(JournalRec rec) { JPutOrDrop(rec.Comp, rec); }
        void JDrop(string comp) { if (JGet(comp) != null) JPutOrDrop(comp, null); }
        void JPutOrDrop(string comp, JournalRec rec)
        {
            List<string> o = new List<string>(); o.Add("# GameRemix install journal: component|program_version|path=sha256;...|options");
            foreach (JournalRec r in JLoad(true)) if (r.Comp != comp) o.Add(r.Line());
            if (rec != null) { rec.Ver = App.Version; o.Add(rec.Line()); }
            Directory.CreateDirectory(GameData); AtomicWrite(JournalFile, Encoding.UTF8.GetBytes(string.Join("\r\n", o.ToArray()) + "\r\n"));
        }
        // write next to the target, then swap in one step: a crash leaves either the old file or the new one, never half of each.
        // ReplaceFile keeps the old file as .gr-old until the swap is done; when it fails half way (error 1176/1177: the target is gone) the new or the old file is moved back in.
        // File systems that refuse ReplaceFile: the old file is copied to .gr-old first, so a cut-off overwrite can be recovered by hand; .tmp is never deleted while the target is missing.
        public static void AtomicWrite(string path, byte[] data)
        {
            string tmp = path + ".tmp", old = path + ".gr-old"; File.WriteAllBytes(tmp, data);
            if (!File.Exists(path)) { File.Move(tmp, path); return; }
            try { File.Replace(tmp, path, old, true); TryDel(old); return; }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
            if (!File.Exists(path)) { if (File.Exists(tmp)) File.Move(tmp, path); else if (File.Exists(old)) File.Move(old, path); TryDel(old); return; }
            File.Copy(path, old, true); File.Copy(tmp, path, true); TryDel(tmp); TryDel(old);
        }
        static void TryDel(string f) { try { if (File.Exists(f)) File.Delete(f); } catch (Exception) { } }

        // ---------------------------------------------------------------- div.exe: the tables
        static BytePatch voiceBP, duskBP;
        static BytePatch Pt(string id, long off, byte[] o, byte[] p) { BytePatch b = new BytePatch(); b.Id = id; b.File = "div.exe"; b.Size = ExeSize; BytePoint t = new BytePoint(); t.Off = off; t.Orig = o; t.Pat = p; b.Points.Add(t); return b; }
        // every table of div.exe in a fixed order: voice and dusk (Program.cs), then the Graphics-page tables in the order of gfx.txt (old forms included, they are only read)
        static List<BytePatch> ExeTables()
        {
            if (voiceBP == null) { voiceBP = Pt("voice", VoiceOff, VoiceOrig, VoicePat); duskBP = Pt("dusk", DuskOff, new byte[] { DuskOrig }, new byte[] { DuskPat }); }
            List<BytePatch> l = new List<BytePatch>(); l.Add(voiceBP); l.Add(duskBP);
            if (GfxDef.Dd != null) foreach (BytePatch p in GfxDef.Dd.Patches.Values) if (string.Equals(p.File, "div.exe", StringComparison.OrdinalIgnoreCase)) l.Add(p);
            return l;
        }
        static BytePatch ExeTable(string id) { foreach (BytePatch p in ExeTables()) if (p.Id == id) return p; return null; }
        // an old shipped form of a patch ("tick80_v35c" -> "tick80"); interp_legacy -> the frame mode, which is FROZEN (Fps.cs): its tail is only taken out
        static string LegacyTarget(string id)
        {
            if (id == "interp_legacy") return FpsEnabled ? "interp" : "";
            int v = id.LastIndexOf("_v"); if (v > 0 && v + 2 < id.Length && char.IsDigit(id[v + 2]) && ExeTable(id.Substring(0, v)) != null) return id.Substring(0, v);
            return null;
        }
        // the frame (PE sections the others live in) is never wanted on its own: it comes with the patches that need it
        static bool Wantable(BytePatch p) { return LegacyTarget(p.Id) == null && p.Id != "frame" && !IsFrame(p.Id); }
        static bool IsFrame(string id) { foreach (BytePatch p in ExeTables()) if (p.Needs == id) return true; return false; }

        // leftovers of older versions and test builds that no table knows, put back to the original bytes (in memory, on a copy):
        // (1) a 4096-byte ".interp" tail of unreleased test builds; (2) the low byte of the call at 0xAA95D left at 0x63 (the game died after loading a save, 07.11.2026);
        // (3) a ".glow" section header in the padding of an exe without the frame; (4) the sort key of the large windows of 1.0.18..1.0.23 (Ctrl+S / Ctrl+O -> Ctrl+C now)
        static byte[] ExeNormalize(byte[] src, List<string> notes)
        {
            byte[] b = (byte[])src.Clone(); long S = ExeSize;
            if (b.Length == S + 4096 && Ascii(b, 0x2a8, 7) == ".interp")
            {
                foreach (string id in new string[] { "interp_legacy", "interp", "frame" }) { BytePatch p = ExeTable(id); if (p == null) continue; foreach (BytePoint t in p.Points) if (t.Off + t.Orig.Length <= S) Array.Copy(t.Orig, 0, b, t.Off, t.Orig.Length); }
                Array.Resize(ref b, (int)S); notes.Add("interpolation tail of a test build");
            }
            if ((b.Length == S || b.Length == S + 40960) && b[0xAA95C] == 0xE8 && b[0xAA95D] == 0x63 && b[0xAA95E] == 0xBB && b[0xAA95F] == 0xFF && b[0xAA960] == 0xFF) { b[0xAA95D] = 0x7F; notes.Add("call at 0x4AB55C"); }
            if (b.Length == S && Ascii(b, 0x2D0, 5) == ".glow" && Ascii(b, 0x2A8, 5) != ".cave") { for (int i = 0; i < 0x18; i++) b[0x2D0 + i] = 0; notes.Add("stray section header"); }
            if (b.Length == S + 40960 && b[0x259E00] == 0x83 && b[0x259E01] == 0x7C && b[0x259E02] == 0x24 && b[0x259E03] == 0x0C && (b[0x259E04] == 0x13 || b[0x259E04] == 0x0F)) { b[0x259E04] = 0x03; notes.Add("old sort key"); }
            return b;
        }
        static string Ascii(byte[] b, int off, int n) { return off + n <= b.Length ? Encoding.ASCII.GetString(b, off, n) : ""; }

        // which patches an exe carries (any form): only for the ONE-TIME decision of a game that has no journal yet / an exe changed behind the program's back
        static List<string> ExeDetect(byte[] n, out bool legacy)
        {
            List<string> set = new List<string>(); legacy = false;
            foreach (BytePatch p in ExeTables()) if (Wantable(p) && p.State(n) >= 1) set.Add(p.Id);   // 2 = half written (a cut-off write of an older version): it was being switched on
            foreach (BytePatch p in ExeTables())
            {
                string t = LegacyTarget(p.Id); if (t == null || p.State(n) < 1) continue;
                if (t.Length == 0) { legacy = true; continue; }
                if (!set.Contains(t)) { set.Add(t); legacy = true; }
            }
            return set;
        }
        // original + every current table of the wanted patches; the frames they need go first. A point that holds neither the original nor the wanted bytes = two patches want
        // the same bytes (interp vs tick80): refused, nothing is written.
        static byte[] ExeBuild(byte[] orig, ICollection<string> set)
        {
            byte[] b = (byte[])orig.Clone(); List<BytePatch> all = ExeTables(); List<string> frames = new List<string>();
            foreach (BytePatch p in all) if (set.Contains(p.Id) && p.Needs.Length > 0 && !frames.Contains(p.Needs)) frames.Add(p.Needs);
            foreach (BytePatch p in all) if (frames.Contains(p.Id)) b = p.Apply(b);
            foreach (BytePatch p in all) if (set.Contains(p.Id) && !frames.Contains(p.Id)) b = p.Apply(b);
            foreach (string id in set) if (ExeTable(id) == null) throw new InvalidOperationException("unknown patch " + id);
            return b;
        }
        // every byte a table of ours (any form) or a known leftover may touch; the tail behind the original length is ours too
        static bool[] areas;
        static bool InOurAreas(byte[] a, byte[] b)
        {
            if (areas == null)
            {
                bool[] m = new bool[ExeSize];
                foreach (BytePatch p in ExeTables()) foreach (BytePoint t in p.Points) for (long i = t.Off; i < t.Off + t.Orig.Length && i < ExeSize; i++) m[i] = true;
                m[0xAA95D] = true; for (int i = 0x2A8; i < 0x2E8; i++) m[i] = true; areas = m;
            }
            int n = Math.Min(a.Length, b.Length); for (int i = 0; i < n && i < ExeSize; i++) if (a[i] != b[i] && !areas[i]) return false;
            return true;
        }

        // ---------------------------------------------------------------- div.exe: the verified original
        string OrigPath { get { return Path.Combine(BakDir, "div.exe.orig"); } }
        static string Stamp(string f) { try { FileInfo fi = new FileInfo(f); return fi.Exists ? fi.Length + ":" + fi.LastWriteTimeUtc.Ticks : "-"; } catch (Exception) { return "?"; } }
        string origKey; byte[] origCache;
        // the bytes of the original div.exe 1.0.0.62 or null. Sources: the stored copy (also the .prev of versions up to 1.0.31, and an old copy with stray bytes of a test build, cleaned in
        // memory), else the game's exe with every known table taken out. store = write it to div.exe.orig when that file is not the verified original (a non-original there is kept aside
        // as .foreign: it may be the only copy of something; it is never used again).
        byte[] OrigExe(bool store)
        {
            string key = Stamp(Exe) + "|" + Stamp(OrigPath) + "|" + Stamp(OrigPath + ".prev");
            if (key != origKey) { origCache = FindOrig(); origKey = key; }
            if (store && origCache != null)
            {
                bool ok = false; try { ok = File.Exists(OrigPath) && Net.Sha256File(OrigPath) == ExeOrigSha; } catch (IOException) { }
                if (!ok)
                {
                    Directory.CreateDirectory(BakDir);
                    if (File.Exists(OrigPath)) { string a = OrigPath + ".foreign"; for (int i = 2; File.Exists(a); i++) a = OrigPath + ".foreign" + i; File.Move(OrigPath, a); Log("backup: div.exe.orig was not the original 1.0.0.62, kept aside as " + Path.GetFileName(a)); }
                    AtomicWrite(OrigPath, origCache); Log(L.T("backup") + OrigPath); origKey = "";
                }
            }
            return origCache;
        }
        byte[] FindOrig()
        {
            foreach (string f in new string[] { OrigPath, OrigPath + ".prev" })
            {
                try
                {
                    if (!File.Exists(f)) continue; byte[] b = File.ReadAllBytes(f); if (Net.Sha256Bytes(b) == ExeOrigSha) return b;
                    byte[] n = ExeNormalize(b, new List<string>()); if (n.Length == ExeSize && Net.Sha256Bytes(n) == ExeOrigSha) return n;
                }
                catch (IOException ex) { Log("backup " + Path.GetFileName(f) + ": " + ex.Message); }
            }
            try
            {
                if (!HasGame) return null; byte[] c = File.ReadAllBytes(Exe); if (!BytePatch.ExeLenOk(c.Length)) return null;
                // only the tables that are really in the exe (their state read BEFORE anything is taken out): tables overlap (interp_legacy and frame share the header at 0x2CC)
                byte[] u = ExeNormalize(c, new List<string>()); List<BytePatch> inIt = new List<BytePatch>(); foreach (BytePatch p in ExeTables()) if (p.State(u) >= 1) inIt.Add(p);
                foreach (BytePatch p in inIt) u = p.Unpatch(u);
                if (u.Length == ExeSize && Net.Sha256Bytes(u) == ExeOrigSha) return u;
            }
            catch (IOException ex) { Log("div.exe: " + ex.Message); }
            return null;
        }

        // ---------------------------------------------------------------- div.exe: wanted set, rebuild
        // the patches that should be in div.exe. ours = the exe is what the program last wrote (journal), or differs from "original + detected set" only where our tables live.
        // talk = write what was found to the log (the actions; not the state queries of the interface)
        List<string> ExeWanted(byte[] cur, byte[] orig, out bool ours, bool talk)
        {
            JournalRec j = JGet("exe"); string sha = Net.Sha256Bytes(cur); ours = false;
            if (j != null && j.Sha("div.exe") == sha) { ours = true; return SplitSet(j.Opts); }
            List<string> notes = new List<string>(); byte[] n = ExeNormalize(cur, notes); bool legacy; List<string> det = ExeDetect(n, out legacy);
            BytePatch.UseAlt = !GameRussian; byte[] built = null; try { built = ExeBuild(orig, det); } catch (InvalidOperationException) { }
            bool clean = built != null && Eq(built, n);
            List<string> set = det;
            if (j != null && !clean && !legacy && sha != ExeOrigSha) { set = SplitSet(j.Opts); if (talk) Log("div.exe was changed outside the program (unknown bytes): the journal decides what is in it (" + JoinSet(set) + ")"); }   // unknown state: the journal is the truth
            else if (j != null && talk) Log("div.exe was changed outside the program: patches found in it: " + JoinSet(set));   // reinstall / Steam check (original) or an older version of the program
            ours = clean;   // an old form alone does not make the rest of the exe ours: somebody's own edit outside every table keeps it "not ours"
            try { ours = ours || InOurAreas(n, ExeBuild(orig, set)); } catch (InvalidOperationException) { ours = ours || legacy; }
            if (talk && (notes.Count > 0 || legacy)) Log("div.exe: old forms found (" + string.Join(", ", notes.ToArray()) + (legacy ? (notes.Count > 0 ? ", " : "") + "an older version of a patch" : "") + "): rebuilt from the original");
            return set;
        }
        static List<string> Keep(ICollection<string> set) { List<string> k = new List<string>(); foreach (BytePatch p in ExeTables()) if (set.Contains(p.Id) && Wantable(p)) k.Add(p.Id); return k; }   // fixed order, no frames, no old forms
        static List<string> SplitSet(string s) { List<string> l = new List<string>(); foreach (string x in s.Split(',')) if (x.Trim().Length > 0 && !l.Contains(x.Trim())) l.Add(x.Trim()); return l; }
        static string JoinSet(List<string> s) { return s.Count == 0 ? "none" : string.Join(",", s.ToArray()); }
        // the patches the program means to keep in div.exe now (null = no supported exe / no original)
        public List<string> ExeSetNow()
        {
            try { if (!HasGame) return null; byte[] cur = File.ReadAllBytes(Exe); if (!BytePatch.ExeLenOk(cur.Length)) return null; byte[] o = OrigExe(false); if (o == null) return null; bool ours; return Keep(ExeWanted(cur, o, out ours, false)); }
            catch (IOException) { return null; }
        }
        // could this patch be added to the wanted set (no other wanted patch uses its bytes)?
        public bool ExeCanAdd(string id)
        {
            List<string> s = ExeSetNow(); byte[] o = OrigExe(false); if (s == null || o == null) return false; if (!s.Contains(id)) s.Add(id);
            BytePatch.UseAlt = !GameRussian; try { ExeBuild(o, s); return true; } catch (InvalidOperationException) { return false; }
        }
        // THE one way the program changes div.exe: wanted set +on -off (clear = start from nothing), rebuilt from the verified original, one atomic replace, then the journal.
        // Switching OFF never fails on an exe the program cannot rebuild (another build, no original): it is left alone and logged.
        void ExeChange(string[] on, string[] off, bool clear)
        {
            if (!HasGame) throw new InvalidOperationException(L.T("stNoGame")); if (GameRunning()) throw new InvalidOperationException(L.T("running"));
            bool adding = on != null && on.Length > 0;
            byte[] cur = File.ReadAllBytes(Exe);
            if (!BytePatch.ExeLenOk(cur.Length)) { if (adding) throw new InvalidOperationException(L.T("stBadExe")); Log("div.exe: another build of the game, left alone"); return; }   // never replaced by our original
            byte[] orig = OrigExe(true);
            if (orig == null) { if (adding) throw new InvalidOperationException(L.T("stBadExe")); Log("div.exe: no verified original to rebuild from, left alone"); return; }
            bool ours; List<string> set = clear ? new List<string>() : ExeWanted(cur, orig, out ours, true);
            if (off != null) foreach (string x in off) set.Remove(x);
            if (on != null) foreach (string x in on) if (!set.Contains(x)) set.Add(x);
            ExeWrite(orig, set, cur);
        }
        void ExeWrite(byte[] orig, List<string> set, byte[] cur)
        {
            BytePatch.UseAlt = !GameRussian;   // the label of the big windows has a Russian and an English form
            List<string> keep = Keep(set); byte[] nb;
            try { nb = ExeBuild(orig, keep); }
            catch (InvalidOperationException ex) { throw new InvalidOperationException(U.R("Эти правки div.exe нельзя включить вместе (они меняют одни и те же байты): ", "These div.exe patches cannot be on together (they change the same bytes): ") + JoinSet(keep) + " (" + ex.Message + ")"); }
            if (!Eq(nb, cur))
            {
                if (!InOurAreas(ExeNormalize(cur, new List<string>()), nb) || cur.Length > nb.Length && !BytePatch.ExeLenOk(cur.Length))   // somebody's own edit outside our tables: the rebuild drops it, a copy stays
                {
                    Directory.CreateDirectory(BakDir); string a = Path.Combine(BakDir, "div.exe.foreign-" + DateTime.Now.ToString("yyyyMMdd-HHmmss"));
                    File.WriteAllBytes(a, cur); Log("div.exe had changes outside the program's patches: a copy is kept as " + a);
                }
                AtomicWrite(Exe, nb); Log(L.T("applied") + "div.exe rebuilt from the original: " + JoinSet(keep));
            }
            JournalRec r = new JournalRec(); r.Comp = "exe"; r.Files["div.exe"] = Net.Sha256Bytes(nb); r.Opts = string.Join(",", keep.ToArray()); JPut(r);
        }
        // start-up: an exe written by an older version (old tables / forms) or by this one before the tables changed is rebuilt to the current tables. An exe with changes outside
        // every table of ours (somebody's own edit) is NOT touched here (logged); it is rebuilt from the original only when the player changes a fix.
        void ExeSync()
        {
            if (GfxDef.Dd == null) return; byte[] cur = File.ReadAllBytes(Exe); if (!BytePatch.ExeLenOk(cur.Length)) return;
            byte[] orig = OrigExe(false); if (orig == null) { if (JGet("exe") != null) Log("div.exe: no verified original (div.exe.orig) to rebuild from"); return; }
            bool ours; List<string> set = Keep(ExeWanted(cur, orig, out ours, true)); JournalRec j = JGet("exe");
            if (!ours) { Log("div.exe holds changes outside the program's patches: left as is (it is rebuilt from the original on the next change of a fix)"); return; }
            if (set.Count == 0 && j == null && Eq(cur, orig)) return;   // a game the program never patched: nothing to record
            BytePatch.UseAlt = !GameRussian; byte[] nb = ExeBuild(orig, set);
            if (Eq(nb, cur) && j != null && j.Sha("div.exe") == Net.Sha256Bytes(cur) && j.Opts == string.Join(",", set.ToArray())) return;   // already the current tables, recorded
            OrigExe(true); ExeWrite(orig, set, cur);
        }
        public void ExeReset() { ExeChange(null, null, true); }   // "Revert all": the original, whatever state the exe was in

        // ---------------------------------------------------------------- embedded files: gr-draw, dgVoodoo, voice DLLs
        class EmbFile { public string Rel; public Func<byte[]> Data; }
        static byte[] Utf8(string s) { return new UTF8Encoding(false).GetBytes(s); }   // what File.WriteAllText writes
        static byte[] FxLicBytes() { return Utf8(Encoding.UTF8.GetString(CncRes("fxlic.txt"))); }
        static byte[] CncLicBytes() { return Utf8(Encoding.UTF8.GetString(CncRes("LICENSE.txt")) + "\r\ncnc-ddraw https://github.com/FunkyFr3sh/cnc-ddraw\r\n"); }
        static List<KeyValuePair<string, byte[]>> CncShaders()
        {
            List<KeyValuePair<string, byte[]>> l = new List<KeyValuePair<string, byte[]>>(); byte[] sh = CncRes("shaders.bin"); int p = 0; int cnt = sh[p] | (sh[p + 1] << 8); p += 2;
            for (int i = 0; i < cnt; i++)
            {
                int nl = sh[p] | (sh[p + 1] << 8); p += 2; string name = Encoding.UTF8.GetString(sh, p, nl); p += nl; int dl = BitConverter.ToInt32(sh, p); p += 4;
                byte[] d = new byte[dl]; Array.Copy(sh, p, d, 0, dl); l.Add(new KeyValuePair<string, byte[]>(name, d)); p += dl;
            }
            return l;
        }
        static List<EmbFile> EmbFiles(string comp)
        {
            List<EmbFile> l = new List<EmbFile>();
            Action<string, Func<byte[]>> add = delegate(string rel, Func<byte[]> d) { EmbFile e = new EmbFile(); e.Rel = rel; e.Data = d; l.Add(e); };
            if (comp == "grdraw")
            {
                add("ddraw.dll", delegate { return CncRes("fxddraw.dll"); }); add("ddfx LICENSE-DejaVu.txt", FxLicBytes); add("cnc-ddraw LICENSE.txt", CncLicBytes);
                foreach (KeyValuePair<string, byte[]> kv in CncShaders()) { byte[] d = kv.Value; add(kv.Key, delegate { return d; }); }
            }
            else if (comp == "dgv") foreach (string f in new string[] { "DDraw.dll", "D3DImm.dll", "dgVoodooCpl.exe" }) { string r = "dgv_" + f; add(f, delegate { return Res(r); }); }   // dgVoodoo.conf: settings, edited by the program and the player
            else if (comp == "voice") foreach (string f in new string[] { "OsirisDLL.dll", "DivDialogSystem.dll" }) { string r = f; add(f, delegate { return Res(r); }); }
            return l;
        }
        // which files of a component are the program's (the mark files of the versions before the journal: cnc.inst / dgv.inst)
        bool EmbMarked(string comp, string rel)
        {
            if (comp == "grdraw") { List<string> made; string mv; ReadMark(out made, out mv); return made.Exists(delegate(string s) { return string.Equals(s, rel, StringComparison.OrdinalIgnoreCase); }); }
            if (comp == "dgv") return InstHas(rel);
            return false;
        }
        // the journal line of a component from what is in the game folder now: a file equal to the program's copy is ours; a file still equal to the sha the journal had is ours (an older
        // copy); anything else is not. missingKeep: a file that is not there keeps its line (dgVoodoo parks its dlls as *.dgvoff while off).
        void JNote(string comp, bool missingKeep)
        {
            try
            {
                JournalRec old = JGet(comp), r = new JournalRec(); r.Comp = comp;
                foreach (EmbFile e in EmbFiles(comp))
                {
                    string f = P(e.Rel), os = old == null ? null : old.Sha(e.Rel);
                    if (!File.Exists(f)) { if (missingKeep && os != null) r.Files[e.Rel] = os; continue; }
                    if (comp == "grdraw" && !EmbMarked(comp, e.Rel)) continue;   // a shader the player had before gr-draw is not ours even when equal
                    string cs = Net.Sha256File(f); if (cs == Net.Sha256Bytes(e.Data()) || cs == os) r.Files[e.Rel] = cs;
                }
                if (r.Files.Count > 0) JPut(r); else JDrop(comp);
            }
            catch (Exception ex) { Log("install.txt (" + comp + "): " + ex.Message); }
        }
        bool EmbOurs(string comp, string rel)   // the file in the game folder is one the program wrote (now or in an older version)
        {
            string f = P(rel); if (!File.Exists(f)) return false; JournalRec j = JGet(comp); string js = j == null ? null : j.Sha(rel);
            if (js != null) return js == Net.Sha256File(f);
            if (j != null) return false;   // the journal knows this component and has no line for the file: not ours (changed by the player)
            return comp == "grdraw" && EmbMarked(comp, rel) && (rel != "ddraw.dll" || IsCncDll(f));   // before the journal: the mark of gr-draw names the files (FxMark of 1.0.31)
        }
        // our file still as we wrote it + the program carries another one -> replaced; changed by the player -> left, logged. Missing shaders of an installed gr-draw (new in this version) are added.
        void EmbRefresh(string comp)
        {
            JournalRec j = JGet(comp); int n = 0;
            bool grOurs = comp == "grdraw" && EmbMarked(comp, "ddraw.dll") && IsCncDll(P("ddraw.dll"));
            foreach (EmbFile e in EmbFiles(comp))
            {
                string f = P(e.Rel);
                if (!File.Exists(f)) { if (grOurs && e.Rel.StartsWith("Shaders", StringComparison.OrdinalIgnoreCase)) { Directory.CreateDirectory(Path.GetDirectoryName(f)); AtomicWrite(f, e.Data()); MarkAdd(e.Rel); n++; Log(L.T("applied") + e.Rel + " (new in this version)"); } continue; }
                byte[] want = e.Data(); string cs = Net.Sha256File(f); if (cs == Net.Sha256Bytes(want)) continue;
                if (EmbOurs(comp, e.Rel)) { AtomicWrite(f, want); n++; Log(L.T("applied") + e.Rel + " updated to the program's current copy"); }
                else if (j != null && j.Sha(e.Rel) != null || EmbMarked(comp, e.Rel)) Log(e.Rel + ": changed outside the program, left as is");
            }
            JNote(comp, comp == "dgv");
            if (n > 0) Log(L.T("applied") + comp + ": " + n + " file(s) refreshed");
        }
        // start-up (and --sync): embedded files, then div.exe. Each part on its own: a failure is logged, never silent, and never stops the others.
        public void StartupSync()
        {
            if (!HasGame || App.ReadOnly || GameRunning()) return;
            try { if (Cnc) EmbRefresh("grdraw"); } catch (Exception ex) { Log("start-up: gr-draw files: " + ex.Message); }
            try { if (Dgv) EmbRefresh("dgv"); } catch (Exception ex) { Log("start-up: dgVoodoo files: " + ex.Message); }
            try { if (!VoiceUseful && (VoicePatched || OurDllAny)) { SetVoice(false); Log("start-up: voice fix taken out (this game has no voiced dialogues)"); } else EmbRefresh("voice"); } catch (Exception ex) { Log("start-up: voice DLLs: " + ex.Message); }   // English version: put the original DLLs and exe bytes back
            try { if (FxNeeded) FxApply(FxRead()); } catch (Exception ex) { Log("start-up: effects build: " + ex.Message); }
            try { KoreanRefresh(); } catch (Exception ex) { Log("start-up: Korean pack: " + ex.Message); }
            try { ExeSync(); } catch (Exception ex) { Log("start-up: div.exe: " + ex.Message); }
        }
    }
}
