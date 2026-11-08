// Patches of the "Graphics" page. Two kinds:
//   BytePatch  - generic: a list of (offset, expected original bytes, patched bytes) in ONE file; nothing is written unless every point holds the expected bytes
//                (original or already patched). The tables come from the game's data (games/<id>/gfx/gfx.txt), not from code.
//   DdFloor    - Divine Divinity only: the "black floor" hole in the cellar map (world.x1). Port of games/divine-divinity/patches/fix_black_floor/ddfix.py.
// Backups: div.exe is always rebuilt from the verified original (div.exe.orig, src/Install.cs) + the tables of the enabled patches; the floor fix keeps a full copy of
// main\startup\world.x1 and dynamic\world.x1 and a record of the files it changed (saves are put back cell by cell, the exact old values are known).
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

namespace DDFixTool
{
    class BytePoint { public long Off; public byte[] Orig, Pat, Alt; }   // Alt: a second "patched" variant (the language dependent label of the big windows: Pat = Russian, Alt = English)

    class BytePatch
    {
        public string Id = "", File = "", Needs = ""; public long Size; public List<BytePoint> Points = new List<BytePoint>();
        // Append: bytes this patch adds at the END of the file (legacy form of frame interpolation, +4096 bytes). AppendZero: a zero tail of that many bytes (the "frame": PE sections .cave/.glow/.interp
        // that the patches windows/glow/interp write into; its content is whatever those patches put there, so only its LENGTH is checked).
        // Needs: id of the patch whose tail this patch's points live in (points at offsets >= Size): while the file has no tail all of them count as original (zeros).
        // Grow = the longest tail of any patch: every patch of the same file accepts "Size" and "Size + Grow" (and Size + any other known tail, see Extra).
        public byte[] Append; public long AppendZero; public static long Grow; public static List<long> Extra = new List<long>();
        public static bool UseAlt;   // write the Alt variant of the points that have one (english game)
        public static bool ExeLenOk(long len) { if (len == Core.ExeSize) return true; if (Grow > 0 && len == Core.ExeSize + Grow) return true; foreach (long x in Extra) if (len == Core.ExeSize + x) return true; return false; }
        public long TailLen { get { return Append != null ? Append.Length : AppendZero; } }
        bool LenOk(long len)
        {
            if (len == Size) return true;
            if (TailLen > 0) return len == Size + TailLen;
            if (Size <= 0) return true; if (Grow > 0 && len == Size + Grow) return true; foreach (long x in Extra) if (len == Size + x) return true; return false;
        }
        public static byte[] Hex(string s)
        {
            if (s.Length == 0 || s.Length % 2 != 0) throw new FormatException("bad hex: " + s);
            byte[] b = new byte[s.Length / 2]; for (int i = 0; i < b.Length; i++) b[i] = Convert.ToByte(s.Substring(i * 2, 2), 16); return b;
        }
        // "4b280:8b:c3" -> point (hex offset, original bytes, patched bytes of the same length); "ba30:00:ed~77" has a second patched variant
        public static BytePoint ParsePoint(string s)
        {
            string[] p = s.Split(':'); if (p.Length != 3) throw new FormatException("bad patch point: " + s);
            BytePoint t = new BytePoint(); t.Off = Convert.ToInt64(p[0], 16); t.Orig = Hex(p[1]);
            int tl = p[2].IndexOf('~'); if (tl >= 0) { t.Alt = Hex(p[2].Substring(tl + 1)); t.Pat = Hex(p[2].Substring(0, tl)); } else t.Pat = Hex(p[2]);
            if (t.Orig.Length != t.Pat.Length || (t.Alt != null && t.Alt.Length != t.Pat.Length)) throw new FormatException("patch point lengths differ: " + s); return t;
        }
        byte[] Want(BytePoint t) { return UseAlt && t.Alt != null ? t.Alt : t.Pat; }
        static bool IsZero(byte[] b) { foreach (byte x in b) if (x != 0) return false; return true; }
        // 0 = every point original, 1 = every point patched, 2 = mixed original/patched (an unfinished or foreign change of ours), -1 = some point holds other bytes / wrong file
        public int State(string path)
        {
            try
            {
                FileInfo fi = new FileInfo(path); if (!fi.Exists || !LenOk(fi.Length)) return -1;
                using (FileStream fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
                {
                    byte[] b = new byte[fs.Length]; int got = 0; while (got < b.Length) { int n = fs.Read(b, got, b.Length - got); if (n <= 0) return -1; got += n; }
                    return State(b);
                }
            }
            catch (IOException) { return -1; }
        }
        public int State(byte[] b)
        {
            if (!LenOk(b.Length)) return -1; int orig = 0, pat = 0;
            foreach (BytePoint t in Points)
            {
                if (t.Off + t.Orig.Length > b.Length) { if (Needs.Length > 0 && b.Length == Size && IsZero(t.Orig)) { orig++; continue; } return -1; }   // no tail yet: nothing of ours there
                if (At(b, t.Off, t.Orig)) orig++; else if (At(b, t.Off, t.Pat) || (t.Alt != null && At(b, t.Off, t.Alt))) pat++; else return -1;
            }
            if (Append != null)   // the tail counts as one more point: absent = original, exactly ours = patched, anything else = foreign
            {
                if (b.Length == Size) orig++; else if (At(b, Size, Append)) pat++; else return -1;
            }
            else if (AppendZero > 0) { if (b.Length == Size) orig++; else pat++; }   // the frame: present = patched (length already checked)
            return pat == 0 ? 0 : (orig == 0 ? 1 : 2);
        }
        static bool At(byte[] b, long off, byte[] v) { if (off + v.Length > b.Length) return false; for (int i = 0; i < v.Length; i++) if (b[off + i] != v[i]) return false; return true; }
        // this patch put into the bytes (Core.ExeBuild: on a copy of the verified original). Every point must hold the original or the wanted bytes, else another patch owns them -> refused.
        public byte[] Apply(byte[] b)
        {
            if (TailLen > 0)
            {
                if (b.Length == Size) { byte[] g = new byte[Size + TailLen]; Array.Copy(b, g, b.Length); if (Append != null) Array.Copy(Append, 0, g, Size, Append.Length); b = g; }
                else if (b.Length != Size + TailLen) throw new InvalidOperationException("patch " + Id + ": the file already has another tail");
            }
            foreach (BytePoint t in Points)
            {
                byte[] want = Want(t); if (t.Off + want.Length > b.Length) throw new InvalidOperationException("patch " + Id + ": point beyond the end of the file");
                if (At(b, t.Off, want)) continue; if (!At(b, t.Off, t.Orig)) throw new InvalidOperationException("patch " + Id + " at 0x" + t.Off.ToString("x") + ": the bytes belong to another patch");
                Array.Copy(want, 0, b, t.Off, want.Length);
            }
            return b;
        }
        // in-place write, ONLY for files other than div.exe (div.exe is rebuilt from the original, Core.ExeChange). Writes only after every point was checked; points already in the wanted state are skipped.
        // Switching on: the tail first (code the hooks will jump to), then the points from the highest offset down (the hooks in .text come last); switching off: the reverse.
        public int Write(string path, bool patched)
        {
            int st = State(path);
            if (st < 0) throw new InvalidOperationException(U.R("Файл не подходит для правки (другая версия или чужие байты): ", "The file does not fit the patch (another version or foreign bytes): ") + System.IO.Path.GetFileName(path));
            int n = 0;
            using (FileStream fs = new FileStream(path, FileMode.Open, FileAccess.ReadWrite, FileShare.Read))
            {
                if (patched && TailLen > 0 && fs.Length == Size)
                {
                    fs.Position = Size; if (Append != null) fs.Write(Append, 0, Append.Length); else fs.SetLength(Size + AppendZero); n++;
                }
                int from = patched ? Points.Count - 1 : 0, to = patched ? -1 : Points.Count, step = patched ? -1 : 1;
                for (int i = from; i != to; i += step)
                {
                    BytePoint t = Points[i]; byte[] want = patched ? Want(t) : t.Orig;
                    if (t.Off + t.Orig.Length > fs.Length) { if (!patched && IsZero(t.Orig)) continue; throw new InvalidOperationException("patch point beyond the end of the file"); }
                    byte[] cur = new byte[t.Orig.Length]; fs.Position = t.Off; fs.Read(cur, 0, cur.Length);
                    if (Same(cur, want)) continue; fs.Position = t.Off; fs.Write(want, 0, want.Length); n++;
                }
                if (!patched && TailLen > 0 && fs.Length == Size + TailLen) { fs.SetLength(Size); n++; }
            }
            return n;
        }
        // the bytes with every point put back to the original (Core.FindOrig: the verified original derived from a patched exe when no copy is stored yet)
        public byte[] Unpatch(byte[] b)
        {
            foreach (BytePoint t in Points)
            {
                if (t.Off + t.Pat.Length > b.Length) continue; bool eq = true, eqa = t.Alt != null; for (int i = 0; i < t.Pat.Length; i++) { if (b[t.Off + i] != t.Pat[i]) eq = false; if (eqa && b[t.Off + i] != t.Alt[i]) eqa = false; }
                if (eq || eqa) Array.Copy(t.Orig, 0, b, t.Off, t.Orig.Length);
            }
            if (TailLen > 0 && b.Length == Size + TailLen) Array.Resize(ref b, (int)Size);   // the tail goes too
            return b;
        }
        static bool Same(byte[] a, byte[] b) { if (a.Length != b.Length) return false; for (int i = 0; i < a.Length; i++) if (a[i] != b[i]) return false; return true; }
    }

    // ---------------------------------------------------------------- Divine Divinity: black floor in the cellar (world.x1, map 1)
    // row 527, columns 130..134 hold the "Darkness" tile (274) although the neighbouring rows are cellar floor (2445..2452). The fix rewrites the 16-bit "down texture"
    // of those five cells; file size, offset tables, objects and every other byte stay as they are (10 bytes change).
    static class DdFloor
    {
        const int Rows = 1024, Cols = 512, Dark = 274;
        static readonly int[][] Cells = { new int[] { 527, 130, 2447 }, new int[] { 527, 131, 2446 }, new int[] { 527, 132, 2451 }, new int[] { 527, 133, 2446 }, new int[] { 527, 134, 2449 } };
        public const string Startup = @"main\startup\world.x1", Dynamic = @"dynamic\world.x1";

        static uint U32(FileStream fs, long pos) { byte[] b = new byte[4]; fs.Position = pos; if (fs.Read(b, 0, 4) != 4) throw new InvalidDataException("short"); return BitConverter.ToUInt32(b, 0); }
        static int U16(FileStream fs, long pos) { byte[] b = new byte[2]; fs.Position = pos; if (fs.Read(b, 0, 2) != 2) throw new InvalidDataException("short"); return BitConverter.ToUInt16(b, 0); }
        static long CellOff(FileStream fs, int y, int x)
        {
            long row = U32(fs, 4L * y); if (row + 1024 + 2L * Cols > fs.Length) throw new InvalidDataException("row offset out of range");
            return row + 1024 + U16(fs, row + 2L * x);   // per-row u16 offset table
        }
        // light structural check, as in ddfix.py: size window, trailer 103, header, consistent cell offsets of the cells we touch
        static void Check(FileStream fs)
        {
            if (fs.Length < 9000000 || fs.Length > 11000000) throw new InvalidDataException("size " + fs.Length);
            byte[] t = new byte[4]; fs.Position = fs.Length - 4; fs.Read(t, 0, 4); if (t[0] != 103 || t[1] != 0 || t[2] != 0 || t[3] != 0) throw new InvalidDataException("not a world file (trailer)");
            if (U32(fs, 0) != 4096) throw new InvalidDataException("bad header");
            foreach (int[] c in Cells)
            {
                long o = CellOff(fs, c[0], c[1]); fs.Position = o + 6; int n = fs.ReadByte(); long nxt = CellOff(fs, c[0], c[1] + 1);
                if (n < 0 || nxt != o + 16 + 8L * n) throw new InvalidDataException("cell table inconsistent");
            }
        }
        // per file: "absent", "skip" (not a map we know), "orig", "fixed", "partial", "other"
        public static string State(string path)
        {
            if (!File.Exists(path)) return "absent";
            try
            {
                using (FileStream fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
                {
                    Check(fs); int fixedN = 0, origN = 0;
                    foreach (int[] c in Cells) { int v = U16(fs, CellOff(fs, c[0], c[1])); if (v == c[2]) fixedN++; else if (v == Dark) origN++; else return "other"; }
                    return fixedN == Cells.Length ? "fixed" : (origN == Cells.Length ? "orig" : "partial");
                }
            }
            catch (Exception) { return "skip"; }
        }
        // on = write the floor tiles, off = put the Darkness tile back. Cells already in the wanted state are left alone; unexpected values -> nothing is written.
        public static int Write(string path, bool on)
        {
            string st = State(path); if (st == "orig" && !on || st == "fixed" && on) return 0;
            if (st != "orig" && st != "fixed" && st != "partial") throw new InvalidOperationException(U.R("Карта не подходит для правки (другая карта или чужие значения): ", "The map does not fit the fix (another map or foreign values): ") + path);
            int n = 0;
            using (FileStream fs = new FileStream(path, FileMode.Open, FileAccess.ReadWrite, FileShare.Read))
                foreach (int[] c in Cells)
                {
                    long o = CellOff(fs, c[0], c[1]); int cur = U16(fs, o), want = on ? c[2] : Dark; if (cur == want) continue;
                    fs.Position = o; fs.Write(BitConverter.GetBytes((ushort)want), 0, 2); n++;
                }
            return n;
        }
        public static List<string> SaveMaps(string gameDir)
        {
            List<string> l = new List<string>();
            try { foreach (string d in Directory.GetDirectories(gameDir, "savegames*")) foreach (string s in Directory.GetDirectories(d)) { string f = System.IO.Path.Combine(s, "world.x1"); if (File.Exists(f)) l.Add(f); } }
            catch (IOException) { }
            return l;
        }
    }

    partial class Core
    {
        // ---- the byte patches and the floor fix of the Graphics page (tables: Gfx.Def)
        public BytePatch GfxBytePatch(string id) { BytePatch p; return GfxDef.Dd.Patches.TryGetValue(id, out p) ? p : null; }
        string BytePatchFile(BytePatch p) { return P(p.File); }
        // state of a byte patch: "off" / "on" / "mixed" / "n/a". For div.exe "n/a" = it cannot be put in (another build of the game, no verified original, or a wanted patch owns
        // the same bytes); unknown bytes at its points are no dead end any more (the exe is rebuilt from the original): "mixed" when the program wants it, "off" otherwise
        public string BytePatchState(string id)
        {
            BytePatch p = GfxBytePatch(id); if (p == null || !HasGame) return "n/a";
            bool exe = string.Equals(p.File, "div.exe", StringComparison.OrdinalIgnoreCase); if (exe && !ExeSupported) return "n/a";
            int s = p.State(BytePatchFile(p));
            if (s < 0 && exe) { List<string> w = ExeSetNow(); if (w != null) { if (w.Contains(id)) return "mixed"; if (ExeCanAdd(id)) return "off"; } }
            return s == 0 ? "off" : (s == 1 ? "on" : (s == 2 ? "mixed" : "n/a"));
        }
        // div.exe: the wanted set changes and the exe is rebuilt from the original (Core.ExeChange, src/Install.cs); the frame comes and goes with the patches that need it.
        // Another file (none today): written in place, point by point.
        public void SetBytePatch(string id, bool on)
        {
            BytePatch p = GfxBytePatch(id); if (p == null) throw new InvalidOperationException("unknown patch " + id);
            bool exe = string.Equals(p.File, "div.exe", StringComparison.OrdinalIgnoreCase);
            if (!exe)
            {
                string f = BytePatchFile(p); if (!on && p.State(f) < 0) { Log("patch " + id + ": nothing of ours in this file, left alone"); return; }
                int n = p.Write(f, on); Log((on ? L.T("applied") : L.T("reverted")) + "patch " + id + " (" + n + " points)"); return;
            }
            if (on) ExeChange(new string[] { id }, null, false); else ExeChange(null, new string[] { id }, false);
            Log((on ? L.T("applied") : L.T("reverted")) + "patch " + id);
            if (id == "windows")   // the in-place data edits of the kit (stats layout, tooltip); if they cannot be made the exe patch goes back too (the kit is all or nothing)
            {
                try { SetWinPackData(on); }
                catch (Exception) { if (on) { try { ExeChange(null, new string[] { id }, false); } catch (Exception ex2) { Log("windows: could not take the exe patch back: " + ex2.Message); } } throw; }
            }
        }

        string FloorDir { get { return Path.Combine(GameData, "floorfix"); } }
        string FloorRec { get { return Path.Combine(FloorDir, "record.txt"); } }
        List<string> FloorRecLoad() { List<string> l = new List<string>(); try { if (File.Exists(FloorRec)) foreach (string s in File.ReadAllLines(FloorRec, Encoding.UTF8)) if (s.Trim().Length > 0) l.Add(s.Trim()); } catch { } return l; }
        void FloorRecAdd(string rel) { List<string> l = FloorRecLoad(); if (!l.Exists(delegate(string s) { return string.Equals(s, rel, StringComparison.OrdinalIgnoreCase); })) { l.Add(rel); Directory.CreateDirectory(FloorDir); File.WriteAllLines(FloorRec, l.ToArray(), Encoding.UTF8); } }
        string[] FloorMain { get { return new string[] { P(DdFloor.Startup), P(DdFloor.Dynamic) }; } }
        // "off" / "on" / "mixed" / "n/a" for the start map (+ the current-game map), and for the player's saves ("" total = no saves)
        public string FloorState()
        {
            int fx = 0, or = 0, n = 0;
            foreach (string f in FloorMain) { string s = DdFloor.State(f); if (s == "absent") continue; n++; if (s == "fixed") fx++; else if (s == "orig") or++; else if (s != "partial") return "n/a"; }
            if (n == 0) return "n/a"; return fx == n ? "on" : (or == n ? "off" : "mixed");
        }
        public string FloorSavesState(out int total, out int fixedN)
        {
            total = 0; fixedN = 0; int or = 0;
            foreach (string f in DdFloor.SaveMaps(Dir)) { string s = DdFloor.State(f); if (s == "skip" || s == "other" || s == "absent") continue; total++; if (s == "fixed") fixedN++; else if (s == "orig") or++; }
            if (total == 0) return "n/a"; return fixedN == total ? "on" : (or == total ? "off" : "mixed");
        }
        public void SetFloor(bool on)
        {
            if (!HasGame) throw new InvalidOperationException(L.T("stNoGame")); if (GameRunning()) throw new InvalidOperationException(L.T("running"));
            List<string> todo = new List<string>();
            foreach (string f in FloorMain) { string s = DdFloor.State(f); if (s == "absent") continue; if (s == "skip" || s == "other") { if (on) throw new InvalidOperationException(U.R("Карта не подходит для правки: ", "The map does not fit the fix: ") + f); else continue; } todo.Add(f); }
            if (todo.Count == 0 && on) throw new InvalidOperationException(U.R("Файл карты не найден в папке игры.", "The map file was not found in the game folder."));
            foreach (string f in todo)   // a full copy first (made once, never overwritten)
            {
                string rel = f.Substring(Dir.Length).TrimStart('\\'); string bak = Path.Combine(FloorDir, rel.Replace('\\', '_') + ".bak");
                if (on && !File.Exists(bak) && DdFloor.State(f) == "orig") { Directory.CreateDirectory(FloorDir); File.Copy(f, bak); Log(L.T("backup") + bak); }
                int n = DdFloor.Write(f, on); if (on && n > 0) FloorRecAdd(rel);
                Log((on ? L.T("applied") : L.T("reverted")) + "floor fix " + rel + " (" + n + " cells)");
            }
        }
        public void SetFloorSaves(bool on)
        {
            if (!HasGame) throw new InvalidOperationException(L.T("stNoGame")); if (GameRunning()) throw new InvalidOperationException(L.T("running"));
            int done = 0, skipped = 0;
            foreach (string f in DdFloor.SaveMaps(Dir))
            {
                string s = DdFloor.State(f); if (s == "skip" || s == "other") { skipped++; continue; }
                string rel = f.Substring(Dir.Length).TrimStart('\\'); int n = DdFloor.Write(f, on); if (on && n > 0) FloorRecAdd(rel); if (n > 0) done++;
            }
            Log((on ? L.T("applied") : L.T("reverted")) + "floor fix in saves: " + done + " files" + (skipped > 0 ? ", skipped (unknown map): " + skipped : ""));
        }
        // ---- small fixes that are ON by default (map floor hole, map panel): no switches in the UI. Applied with the base set (first run on a game, quick setup, Apply on the
        // Graphics page); never again on their own after the player switched them off / used "Revert all" (opt-out in the game's data); quick setup turns them on again.
        string OptOutFile { get { return Path.Combine(GameData, "fixes_optout.txt"); } }
        string DefaultsDoneFile { get { return Path.Combine(GameData, "fixes_default.txt"); } }
        List<string> OptOuts() { List<string> l = new List<string>(); try { if (File.Exists(OptOutFile)) foreach (string x in File.ReadAllLines(OptOutFile)) if (x.Trim().Length > 0) l.Add(x.Trim()); } catch { } return l; }
        public bool FixOptedOut(string id) { return HasGame && OptOuts().Contains(id); }
        public void FixOptOut(string id, bool out_)
        {
            try { List<string> l = OptOuts(); bool has = l.Contains(id); if (out_ && !has) l.Add(id); else if (!out_ && has) l.Remove(id); else return; Directory.CreateDirectory(GameData); File.WriteAllLines(OptOutFile, l.ToArray(), Encoding.UTF8); } catch { }
        }
        // force = quick setup (clears the opt-out); onlyFirst = the automatic start-up run (once per game). Returns what could not be done (the rest is still applied).
        public List<string> ApplyDefaultFixes(bool force, bool onlyFirst)
        {
            List<string> skipped = new List<string>(); if (!HasGame || GameRunning()) return skipped;
            if (onlyFirst && File.Exists(DefaultsDoneFile)) return skipped;
            foreach (GfxFix f in Gfx.Fixes)
            {
                if (!f.Default) continue; if (force) FixOptOut(f.Id, false); else if (FixOptedOut(f.Id)) continue;
                string st = GfxFixState(f); if (st == "on" || st == "n/a") continue;   // n/a = another build of the game or no such file: nothing to do, nothing forced
                try { if (f.Kind == "bytes") SetBytePatch(f.Arg, true); else if (f.Kind == "floor") SetFloor(true); else continue; Log(L.T("applied") + "default fix " + f.Id); }
                catch (Exception ex) { Log("default fix " + f.Id + ": " + ex.Message); }   // the log only: the player is not told about the small fixes
            }
            try { Directory.CreateDirectory(GameData); File.WriteAllText(DefaultsDoneFile, "1"); } catch { }
            return skipped;
        }
        // "Revert all": everything the program changed in the maps and the exe on the Graphics page (the files the record names + the start map)
        public void RevertGfxFixes()
        {
            if (!HasGame) return;
            List<string> fails = new List<string>();
            foreach (GfxFix bf in Gfx.Fixes) if (bf.Kind == "bytes") { try { string bs = BytePatchState(bf.Arg); if (bs == "on" || bs == "mixed") SetBytePatch(bf.Arg, false); } catch (Exception ex) { fails.Add(bf.Arg + ": " + ex.Message); } }   // map panel, item glow
            foreach (GfxSlot sl in Gfx.Slots) foreach (GfxOpt o in sl.Opts) if (o.Patch.Length > 0) { try { string ps = BytePatchState(o.Patch); if (ps == "on" || ps == "mixed") SetBytePatch(o.Patch, false); } catch (Exception ex) { fails.Add(o.Patch + ": " + ex.Message); } }   // exe patches that belong to a slot option (backpack)
            foreach (string rel in FloorRecLoad()) { string f = P(rel); try { string s = DdFloor.State(f); if (s == "fixed" || s == "partial") DdFloor.Write(f, false); } catch (Exception ex) { fails.Add(rel + ": " + ex.Message); } }
            foreach (string f in FloorMain) { try { string s = DdFloor.State(f); if (s == "fixed" || s == "partial") DdFloor.Write(f, false); } catch (Exception ex) { fails.Add(f + ": " + ex.Message); } }
            foreach (GfxFix f in Gfx.Fixes) if (f.Default) FixOptOut(f.Id, true);   // "Revert all" is a decision of the player: the fixes do not come back by themselves
            if (fails.Count > 0) throw new IOException(string.Join("; ", fails.ToArray()));
            try { if (Directory.Exists(FloorDir)) Directory.Delete(FloorDir, true); } catch { }
            Log(L.T("reverted") + "graphics fixes (map, floor)");
        }
    }
}
