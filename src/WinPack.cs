// "Large windows" kit, the part that is neither the exe patch (patch=windows) nor the asset set (archive 8 + flat.cmp): two small IN-PLACE edits of game data that are switched
// together with the exe patch (Core.SetBytePatch("windows")):
//   cmpentry  - an entry of a .cmp container replaced by an entry of the SAME size (the character-stats layout dat\statuspl.cmp inside dat\global.cmp: the game reads it from there);
//               the original bytes are part of the line (gfx.txt), so a revert needs no backup file and refuses to touch anything it does not recognise;
//   textrec   - one string added to text.cmp (the tooltip of the Sort button, table 10000 id 772); the text is chosen by the language of the file; a backup copy is kept once.
// plus the consistency check of the whole kit ("sprites in archive 8 >= highest sprite index used by the bmg files of flat.cmp"): a flat.cmp that names sprites the archive does not have
// crashes the backpack (RESEARCH_LOG 07.11 "падение рюкзака с набором предметов").
// Game independent: the file names, entry names and texts come from games/<id>/gfx/gfx.txt.
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;

namespace DDFixTool
{
    class CmpEntryPatch { public string File = "", Entry = ""; public byte[] Orig, Pat; }
    class TextRecPatch { public string Glob = "", RuText = "", OtherText = ""; public int Table, Id; }

    // Larian/BMGui .cmp container: u32 count; per entry: u32 nameLen, name (XOR with a positional key), 0, u32 offset, u32 size, u32 0.
    static class CmpFile
    {
        static readonly int[] Key = { 0xf3, 0xbf, 0xaa, 0xf3, 0xd2, 0xbe, 0x9d, 0xd2, 0xfc, 0xf9, 0xb7, 0xe1, 0xfa, 0xb7, 0xeb, 0xfa, 0xcf, 0xcd, 0xcc, 0xcb, 0x9c, 0x9c, 0xb9 };
        public static string DecodeName(byte[] raw) { StringBuilder sb = new StringBuilder(); for (int i = 0; i < raw.Length; i++) sb.Append(i < Key.Length ? (char)(raw[i] ^ Key[i]) : '?'); return sb.ToString(); }
        static uint U32(Stream s) { byte[] b = new byte[4]; int g = 0; while (g < 4) { int n = s.Read(b, g, 4 - g); if (n <= 0) throw new EndOfStreamException(); g += n; } return BitConverter.ToUInt32(b, 0); }
        // the entry named `name` (case-insensitive, / = \): data offset and size; false = not there / not a container
        public static bool Find(Stream fs, string name, out long off, out int size)
        {
            off = 0; size = 0; string want = name.Replace('/', '\\').ToLowerInvariant();
            try
            {
                fs.Position = 0; uint n = U32(fs); if (n == 0 || n > 200000) return false;
                for (uint i = 0; i < n; i++)
                {
                    uint L = U32(fs); if (L == 0 || L > 1024) return false; byte[] raw = new byte[L]; if (fs.Read(raw, 0, (int)L) != L) return false; if (fs.ReadByte() != 0) return false;
                    uint o = U32(fs), sz = U32(fs); U32(fs);
                    if (DecodeName(raw).ToLowerInvariant() == want) { if (o + (long)sz > fs.Length) return false; off = o; size = (int)sz; return true; }
                }
            }
            catch (EndOfStreamException) { }
            return false;
        }
        // 0 = the entry holds `orig`, 1 = `pat`, -1 = anything else / not found
        public static int State(string path, string entry, byte[] orig, byte[] pat)
        {
            try
            {
                using (FileStream fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
                {
                    long off; int sz; if (!Find(fs, entry, out off, out sz) || sz != orig.Length || sz != pat.Length) return -1;
                    byte[] cur = new byte[sz]; fs.Position = off; if (fs.Read(cur, 0, sz) != sz) return -1;
                    if (Same(cur, orig)) return 0; if (Same(cur, pat)) return 1; return -1;
                }
            }
            catch (IOException) { return -1; }
        }
        public static void Write(string path, string entry, byte[] orig, byte[] pat, bool patched)
        {
            if (State(path, entry, orig, pat) < 0) throw new InvalidOperationException(U.R("Файл не подходит для правки записи: ", "The file does not fit the entry edit: ") + Path.GetFileName(path) + " / " + entry);
            using (FileStream fs = new FileStream(path, FileMode.Open, FileAccess.ReadWrite, FileShare.Read))
            {
                long off; int sz; Find(fs, entry, out off, out sz); byte[] want = patched ? pat : orig; byte[] cur = new byte[sz]; fs.Position = off; fs.Read(cur, 0, sz);
                if (Same(cur, want)) return; fs.Position = off; fs.Write(want, 0, sz);
            }
        }
        public static bool Same(byte[] a, byte[] b) { if (a.Length != b.Length) return false; for (int i = 0; i < a.Length; i++) if (a[i] != b[i]) return false; return true; }
        // names of all entries
        public static List<string> Names(string path)
        {
            List<string> r = new List<string>();
            using (FileStream fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
            {
                uint n = U32(fs); if (n > 200000) return r;
                for (uint i = 0; i < n; i++) { uint L = U32(fs); if (L == 0 || L > 1024) break; byte[] raw = new byte[L]; fs.Read(raw, 0, (int)L); fs.ReadByte(); U32(fs); U32(fs); U32(fs); r.Add(DecodeName(raw)); }
            }
            return r;
        }
        // data of one entry (null = not there)
        public static byte[] Read(string path, string entry)
        {
            using (FileStream fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
            { long off; int sz; if (!Find(fs, entry, out off, out sz)) return null; byte[] b = new byte[sz]; fs.Position = off; int g = 0; while (g < sz) { int n = fs.Read(b, g, sz - g); if (n <= 0) return null; g += n; } return b; }
        }
    }

    // localizations\<lang>\text.cmp: u32 nTables; table = u32 id, u32 count, records u32 id, u32 len, len bytes, 0, u32 len2, [len2 bytes + 0]  (1-byte code page; RU = cp1251, byte = glyph code)
    class TextCmp
    {
        public class Rec { public uint Id; public byte[] S1, S2; }
        public class Tab { public uint Id; public List<Rec> Recs = new List<Rec>(); }
        public List<Tab> Tabs = new List<Tab>();
        public static TextCmp Parse(byte[] d)
        {
            TextCmp t = new TextCmp(); int o = 0; Func<uint> u = delegate() { if (o + 4 > d.Length) throw new InvalidDataException("text.cmp: short"); uint v = BitConverter.ToUInt32(d, o); o += 4; return v; };
            uint nt = u(); if (nt > 1000) throw new InvalidDataException("text.cmp: tables");
            for (uint i = 0; i < nt; i++)
            {
                Tab tb = new Tab(); tb.Id = u(); uint c = u(); if (c > 1000000) throw new InvalidDataException("text.cmp: records");
                for (uint j = 0; j < c; j++)
                {
                    Rec r = new Rec(); r.Id = u(); uint l = u(); if (o + l + 1 > d.Length) throw new InvalidDataException("text.cmp: string"); r.S1 = new byte[l]; Array.Copy(d, o, r.S1, 0, l); o += (int)l + 1;
                    uint l2 = u(); if (o + l2 + (l2 > 0 ? 1 : 0) > d.Length) throw new InvalidDataException("text.cmp: string2"); r.S2 = new byte[l2]; Array.Copy(d, o, r.S2, 0, l2); o += (int)l2 + (l2 > 0 ? 1 : 0);
                    tb.Recs.Add(r);
                }
                t.Tabs.Add(tb);
            }
            if (o != d.Length) throw new InvalidDataException("text.cmp: trailing bytes"); return t;
        }
        public byte[] ToBytes()
        {
            MemoryStream ms = new MemoryStream(); BinaryWriter w = new BinaryWriter(ms); w.Write((uint)Tabs.Count);
            foreach (Tab tb in Tabs)
            {
                w.Write(tb.Id); w.Write((uint)tb.Recs.Count);
                foreach (Rec r in tb.Recs) { w.Write(r.Id); w.Write((uint)r.S1.Length); w.Write(r.S1); w.Write((byte)0); w.Write((uint)r.S2.Length); if (r.S2.Length > 0) { w.Write(r.S2); w.Write((byte)0); } }
            }
            w.Flush(); return ms.ToArray();
        }
        public Tab Table(uint id) { foreach (Tab t in Tabs) if (t.Id == id) return t; return null; }
        public Rec Get(uint table, uint id) { Tab t = Table(table); if (t == null) return null; foreach (Rec r in t.Recs) if (r.Id == id) return r; return null; }
        // string added / replaced, records stay sorted by id
        public void Put(uint table, uint id, byte[] text)
        {
            Tab t = Table(table); if (t == null) throw new InvalidDataException("text.cmp: no table " + table);
            Rec r = Get(table, id); if (r != null) { r.S1 = text; return; }
            r = new Rec(); r.Id = id; r.S1 = text; r.S2 = new byte[0]; t.Recs.Add(r); t.Recs.Sort(delegate(Rec a, Rec b) { return a.Id.CompareTo(b.Id); });
        }
        public bool Remove(uint table, uint id) { Tab t = Table(table); if (t == null) return false; Rec r = Get(table, id); if (r == null) return false; t.Recs.Remove(r); return true; }
        // Cyrillic (cp1251 0xC0..0xFF) among the first strings of the main table = a Russian file
        public bool IsRussian()
        {
            Tab t = Table(10000); if (t == null) return false; int n = 0;
            foreach (Rec r in t.Recs) { foreach (byte b in r.S1) if (b >= 0xC0) return true; if (++n >= 50) break; }
            return false;
        }
    }

    partial class Core
    {
        // ---- language of the game data (decides the label text "worn" / "надето" of the trade window and the tooltip text)
        public List<string> TextCmpFiles(string glob)
        {
            List<string> r = new List<string>(); int star = glob.IndexOf('*'); if (star < 0) { string f = P(glob); if (File.Exists(f)) r.Add(f); return r; }
            string pre = glob.Substring(0, star), post = glob.Substring(star + 1).TrimStart('\\', '/'); string root = P(pre.TrimEnd('\\', '/'));
            if (!Directory.Exists(root)) return r;
            foreach (string d in Directory.GetDirectories(root)) { string f = Path.Combine(d, post); if (File.Exists(f)) r.Add(f); }
            return r;
        }
        public bool GameRussian
        {
            get
            {
                try { foreach (TextRecPatch t in GfxDef.Dd.TextRecs) foreach (string f in TextCmpFiles(t.Glob)) { TextCmp tcr = TextCmp.Parse(File.ReadAllBytes(f)); if (RuText(tcr)) return true; } } catch (Exception) { }
                return false;
            }
        }
        string WinPackDir { get { return Path.Combine(GameData, "winpack"); } }
        static byte[] TextBytes(TextRecPatch t, bool ru) { return Encoding.GetEncoding(1251).GetBytes(ru ? t.RuText : t.OtherText); }

        // "on" / "off" / "mixed" / "n/a" of the data edits (not of the exe)
        public string WinPackDataState()
        {
            if (!HasGame || GfxDef.Dd == null) return "n/a"; int on = 0, off = 0, bad = 0;
            foreach (CmpEntryPatch c in GfxDef.Dd.CmpEntries) { string f = P(c.File); if (!File.Exists(f)) { bad++; continue; } int s = CmpFile.State(f, c.Entry, c.Orig, c.Pat); if (s == 1) on++; else if (s == 0) off++; else bad++; }
            foreach (TextRecPatch t in GfxDef.Dd.TextRecs)
                foreach (string f in TextCmpFiles(t.Glob))
                {
                    try
                    {
                        TextCmp tc = TextCmp.Parse(File.ReadAllBytes(f)); TextCmp.Rec r = tc.Get((uint)t.Table, (uint)t.Id);
                        if (r == null) off++; else if (CmpFile.Same(r.S1, TextBytes(t, RuText(tc)))) on++; else bad++;
                    }
                    catch (Exception) { bad++; }
                }
            if (bad > 0) return "n/a"; if (on > 0 && off > 0) return "mixed"; return on > 0 ? "on" : (off > 0 ? "off" : "n/a");
        }
        // switches the data edits together with the exe patch; every edit is checked first and only recognised content is touched
        public void SetWinPackData(bool on)
        {
            if (!HasGame || GfxDef.Dd == null) return;
            foreach (CmpEntryPatch c in GfxDef.Dd.CmpEntries)
            {
                string f = P(c.File); if (!File.Exists(f)) { Log("winpack: " + c.File + " not found, skipped"); continue; }
                int s = CmpFile.State(f, c.Entry, c.Orig, c.Pat);
                if (s < 0) { if (on) throw new InvalidOperationException(U.R("Запись «" + c.Entry + "» в " + c.File + " не совпадает с ожидаемой (другая версия игры или чужая правка).", "The entry \"" + c.Entry + "\" in " + c.File + " is not the expected one (another game version or a foreign edit).")); Log("winpack: " + c.Entry + " left alone"); continue; }
                CmpFile.Write(f, c.Entry, c.Orig, c.Pat, on); Log((on ? L.T("applied") : L.T("reverted")) + "cmp entry " + c.Entry);
            }
            foreach (TextRecPatch t in GfxDef.Dd.TextRecs)
                foreach (string f in TextCmpFiles(t.Glob))
                {
                    byte[] raw = File.ReadAllBytes(f); TextCmp tc;
                    try { tc = TextCmp.Parse(raw); if (!CmpFile.Same(tc.ToBytes(), raw)) throw new InvalidDataException("round trip"); }
                    catch (Exception ex) { if (on) throw new InvalidOperationException(U.R("Файл текстов не распознан (подсказка кнопки сортировки не добавлена): ", "The text file is not recognised (the tooltip of the Sort button was not added): ") + f + " (" + ex.Message + ")"); continue; }
                    TextCmp.Rec r = tc.Get((uint)t.Table, (uint)t.Id); byte[] mine = TextBytes(t, RuText(tc));
                    string bak = Path.Combine(WinPackDir, Path.GetFileName(Path.GetDirectoryName(f)) + "_" + Path.GetFileName(f) + ".orig");
                    if (on)
                    {
                        if (r != null && CmpFile.Same(r.S1, mine)) continue;           // already there
                        if (r != null) throw new InvalidOperationException(U.R("В тексте уже есть другая строка " + t.Table + "/" + t.Id + ": ", "The text file already has another string " + t.Table + "/" + t.Id + ": ") + f);
                        Directory.CreateDirectory(WinPackDir); if (!File.Exists(bak)) File.WriteAllBytes(bak, raw);
                        tc.Put((uint)t.Table, (uint)t.Id, mine); ReplaceFile(f, tc.ToBytes());
                    }
                    else
                    {
                        if (r == null) continue; if (!CmpFile.Same(r.S1, mine)) { Log("winpack: " + f + " string " + t.Id + " is not ours, left alone"); continue; }
                        tc.Remove((uint)t.Table, (uint)t.Id); byte[] outb = tc.ToBytes();
                        if (File.Exists(bak)) { byte[] ob = File.ReadAllBytes(bak); if (!CmpFile.Same(ob, outb)) Log("winpack: " + f + " differs from the backup copy besides our string (the game files were changed meanwhile); only our string was removed"); }
                        ReplaceFile(f, outb);
                    }
                    Log((on ? L.T("applied") : L.T("reverted")) + "text string " + t.Table + "/" + t.Id + " in " + f);
                }
        }
        static void ReplaceFile(string path, byte[] data)
        {
            string tmp = path + ".ogf-new"; File.WriteAllBytes(tmp, data);
            try { File.Replace(tmp, path, null); } catch (Exception) { File.Copy(tmp, path, true); File.Delete(tmp); }   // never delete the original first: a failed copy leaves the old file
        }

        // the kit must be all there or all gone: the sprites of archive 8 against what flat.cmp asks for. Returns problems (empty = fine).
        public List<string> WinPackConsistency()
        {
            List<string> bad = new List<string>(); if (!HasGame) return bad;
            string idx = P(@"static\imagelists\CPackedi.8c"), flat = P(@"dat\flat.cmp");
            if (!File.Exists(idx) || !File.Exists(flat)) return bad;
            long count = new FileInfo(idx).Length / 56; int max = MaxBmgSprite(flat, 8);
            if (max >= count) bad.Add(U.R("Окна рюкзака/торговли/характеристик (dat\\flat.cmp) просят картинку №" + max + ", а в архиве интерфейса их только " + count + ". Откатите «Крупные окна» (иначе рюкзак может вылететь).", "The backpack/trade/stats windows (dat\\flat.cmp) ask for picture #" + max + " but the interface archive has only " + count + ". Turn \"Large windows\" off (the backpack may crash otherwise)."));
            return bad;
        }
        // highest "image list <list> index N" of the bmg entries of flat.cmp (-1 = none / unreadable)
        public static int MaxBmgSprite(string flatCmp, int list)
        {
            int max = -1;
            try
            {
                Regex re = new Regex(@"image list " + list + @" index (\d+)");
                foreach (string n in CmpFile.Names(flatCmp))
                {
                    if (!n.ToLowerInvariant().EndsWith(".bmg")) continue; byte[] d = CmpFile.Read(flatCmp, n); if (d == null) continue;
                    foreach (Match m in re.Matches(Encoding.GetEncoding(1252).GetString(d))) { int v = int.Parse(m.Groups[1].Value); if (v > max) max = v; }
                }
            }
            catch (Exception) { return -1; }
            return max;
        }
    }
}
