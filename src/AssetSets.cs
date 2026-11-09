// Asset sets: ready-made packs of game files (enhanced graphics now, interface skins later) downloaded from OUR server, checked by SHA-256,
// swapped into the game folder atomically, with a backup of the originals and a one-click revert. Game-independent: everything that belongs to one
// game (id, folders, process name) is passed in; the format is described in docs/asset_sets.md.
//   manifest  <base>/<set>/manifest.txt   "OGF-ASSET-SET 1" + key=value lines + one file=... line per file
//   catalog   <base>/catalog.txt          "OGF-ASSET-CATALOG 1" + set=<id> lines
//   state     <profile>\games\<game>\assets\<set>\active.txt (record of what we replaced) and \orig\ (the original files)
using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Windows.Forms;

namespace DDFixTool
{
    delegate void AssetProgress(string text, long done, long total);

    // the player's files are not the originals this set was made for (or are not in a state we may touch)
    class AssetIncompatible : Exception { public AssetIncompatible(string m) : base(m) { } }

    class AssetFile
    {
        public string Path, Url, Enc, CSha, Sha; public long CSize, Size; public string[] Orig = new string[0];   // Orig empty = the file is NEW (not in the original game)
        public bool Gzip { get { return Enc == "gzip"; } }
        public bool IsNew { get { return Orig.Length == 0; } }
        static readonly Regex Hex = new Regex("^[0-9a-f]{64}$");
        public static AssetFile Parse(string v)
        {
            string[] p = v.Split('|'); if (p.Length != 8) throw new InvalidDataException("file=: 8 fields expected, got " + p.Length);
            AssetFile f = new AssetFile(); f.Path = NormPath(p[0].Trim()); f.Url = p[1].Trim(); f.Enc = p[2].Trim().ToLowerInvariant();
            if (f.Enc != "raw" && f.Enc != "gzip") throw new InvalidDataException("file=: enc must be raw or gzip: " + f.Path);
            if (!long.TryParse(p[3], out f.CSize) || !long.TryParse(p[5], out f.Size) || f.CSize <= 0 || f.CSize > int.MaxValue || f.Size <= 0 || f.Size > 4000000000L) throw new InvalidDataException("file=: bad size: " + f.Path);
            f.CSha = p[4].Trim().ToLowerInvariant(); f.Sha = p[6].Trim().ToLowerInvariant();
            if (!Hex.IsMatch(f.CSha) || !Hex.IsMatch(f.Sha)) throw new InvalidDataException("file=: bad sha256: " + f.Path);
            if (f.Enc == "raw" && (f.CSize != f.Size || f.CSha != f.Sha)) throw new InvalidDataException("file=: raw file must have equal packed and unpacked size/hash: " + f.Path);
            string o = p[7].Trim().ToLowerInvariant();
            if (o != "-" && o.Length > 0)
            {
                List<string> l = new List<string>(); foreach (string h in o.Split(',')) { string t = h.Trim(); if (!Hex.IsMatch(t)) throw new InvalidDataException("file=: bad original sha256: " + f.Path); if (!l.Contains(t)) l.Add(t); }
                f.Orig = l.ToArray();
            }
            if (f.Url.Length == 0) throw new InvalidDataException("file=: empty url: " + f.Path);
            return f;
        }
        public static readonly string[] Executable = { ".exe", ".dll", ".cmd", ".bat", ".com", ".scr", ".pif", ".cpl", ".ocx", ".sys", ".drv", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh", ".hta", ".lnk", ".url", ".msi", ".msp", ".ps1", ".psm1", ".reg", ".jar", ".inf", ".gadget", ".appref-ms", ".ini", ".cfg", ".conf" };   // ini/cfg/conf: game and graphics-wrapper settings (ddraw.ini, dgVoodoo.conf) are not asset data either
        // per game: where the files of a set may be (a prefix inside the game folder). Games not listed here: only the executable-type ban above.
        public static bool PathAllowedForGame(string game, string path)
        {
            if (game == "divine-divinity") { string l = path.ToLowerInvariant(); return l.StartsWith("static\\") || l.StartsWith("dat\\"); }   // picture archives and interface-skin files
            return true;
        }
        // relative path inside the game folder: backslashes, no drive, no "..", no reserved characters; never a name of ours
        public static string NormPath(string s)
        {
            s = s.Replace('/', '\\').Trim('\\'); if (s.Length == 0 || s.Length > 200) throw new InvalidDataException("bad path: " + s);
            foreach (string seg in s.Split('\\'))
            {
                if (seg.Length == 0 || seg == "." || seg == ".." || seg.EndsWith(".") || seg.EndsWith(" ") || seg.IndexOfAny(new char[] { '<', '>', ':', '"', '|', '?', '*' }) >= 0) throw new InvalidDataException("bad path: " + s);
                foreach (char c in seg) if (c < 32) throw new InvalidDataException("bad path: " + s);
            }
            string low = s.ToLowerInvariant();
            // a set carries game DATA, never code: nothing the system or the game's launcher could run (the manifest comes from a server and is not signed)
            string ext = System.IO.Path.GetExtension(low); if (ext.Length > 0 && Array.IndexOf(Executable, ext) >= 0) throw new InvalidDataException("bad path (executable type): " + s);
            if (low.EndsWith(".ogf-new") || low.EndsWith(".ogf-old") || low.EndsWith(".part") || low.EndsWith(".tmp")) throw new InvalidDataException("bad path: " + s);
            return s;
        }
    }

    class AssetManifest
    {
        public string Id = "", Game = "", Version = "", Kind = "graphics", NameRu = "", NameEn = "", DescRu = "", DescEn = "", SourceUrl = "", Alt = "";   // Alt: optional faster host of the payload files (flat names, see AltUrl); informational for older programs
        public int LayerSet = -1;   // stacking order: a set of a higher layer may sit on top of the files of a lower one (graphics 0, ui-skin 1); -1 = by kind
        public List<string> Requires = new List<string>(), Conflicts = new List<string>(); public List<string[]> Previews = new List<string[]>();   // previews: id|url|w|h
        public int Layer { get { return LayerSet >= 0 ? LayerSet : DefaultLayer(Kind); } }
        public static int DefaultLayer(string kind) { return kind == "ui-skin" ? 1 : 0; }
        public List<AssetFile> Files = new List<AssetFile>();
        public string Name { get { string n = L.Ru ? NameRu : L.Kor(NameEn); return n.Length > 0 ? n : (NameEn.Length > 0 ? NameEn : (NameRu.Length > 0 ? NameRu : Id)); } }
        public string Desc { get { string n = L.Ru ? DescRu : L.Kor(DescEn); return n.Length > 0 ? n : (DescEn.Length > 0 ? DescEn : DescRu); } }
        public long Download { get { long s = 0; foreach (AssetFile f in Files) s += f.CSize; return s; } }
        // flat file name on the alternative host (release assets have no folders): "2.1/static/x.gz" -> "2.1__static__x.gz"
        public string AltUrl(AssetFile f) { if (Alt.Length == 0) return null; string rel = f.Url.Replace('\\', '/'); int q = rel.IndexOf('?'); if (q >= 0) rel = rel.Substring(0, q); return Alt + rel.Replace("/", "__"); }
        public long Installed { get { long s = 0; foreach (AssetFile f in Files) s += f.Size; return s; } }

        public const int MaxFiles = 64; public const long MaxTotal = 8L * 1024 * 1024 * 1024;
        static readonly Regex IdRx = new Regex("^[a-z0-9][a-z0-9._-]{0,40}$"), VerRx = new Regex("^[0-9A-Za-z._-]{1,16}$");
        public static AssetManifest Parse(string text, string sourceUrl)
        {
            try { return ParseCore(text, sourceUrl); }
            catch (InvalidDataException ex) { throw new InvalidDataException(U.R("Описание набора повреждено или не принято (", "The set description is damaged or was not accepted (") + ex.Message + ")"); }   // technical detail stays in English
        }
        static AssetManifest ParseCore(string text, string sourceUrl)
        {
            AssetManifest m = new AssetManifest(); m.SourceUrl = sourceUrl ?? ""; bool head = false;
            foreach (string raw in text.TrimStart('﻿').Replace("\r\n", "\n").Split('\n'))
            {
                string ln = raw.Trim(); if (ln.Length == 0 || ln[0] == '#') continue;
                if (!head)
                {
                    Match h = Regex.Match(ln, @"^OGF-ASSET-SET\s+(\d+)$"); if (!h.Success) throw new InvalidDataException(U.R("Это не манифест набора.", "This is not an asset-set manifest."));
                    if (h.Groups[1].Value != "1") throw new InvalidDataException(U.R("Манифест новее программы: обновите программу.", "The manifest is newer than this program: update the program."));
                    head = true; continue;
                }
                int eq = ln.IndexOf('='); if (eq <= 0) continue;
                string k = ln.Substring(0, eq).Trim().ToLowerInvariant(), v = ln.Substring(eq + 1).Trim();
                if (k == "id") m.Id = v; else if (k == "game") m.Game = v; else if (k == "version") m.Version = v; else if (k == "kind") m.Kind = v.ToLowerInvariant();
                else if (k == "name.ru") m.NameRu = v; else if (k == "name.en") m.NameEn = v; else if (k == "desc.ru") m.DescRu = v; else if (k == "desc.en") m.DescEn = v;
                else if (k == "alt") { try { Uri au = new Uri(v); if (au.Scheme == Uri.UriSchemeHttps && Net.AssetHost(au.Host)) m.Alt = v.EndsWith("/") ? v : v + "/"; } catch (Exception) { } }   // ignored unless it is a known download host
                else if (k == "layer") { int ly; if (int.TryParse(v, out ly) && ly >= 0 && ly < 10) m.LayerSet = ly; }
                else if (k == "requires" || k == "conflicts") { foreach (string x in v.Split(',')) { string t = x.Trim().ToLowerInvariant(); if (IdRx.IsMatch(t)) (k == "requires" ? m.Requires : m.Conflicts).Add(t); } }
                else if (k == "preview") { string[] pp = v.Split('|'); if (pp.Length >= 2 && pp.Length <= 4) m.Previews.Add(pp); }
                else if (k == "file") { if (m.Files.Count >= MaxFiles) throw new InvalidDataException("too many files"); m.Files.Add(AssetFile.Parse(v)); }
                // anything else (size.download, size.installed, future keys) is informational and ignored: sizes are always recomputed from the file lines
            }
            if (!head) throw new InvalidDataException(U.R("Пустой манифест.", "Empty manifest."));
            m.Validate(); return m;
        }
        void Validate()
        {
            if (!IdRx.IsMatch(Id)) throw new InvalidDataException("manifest: bad id"); if (!IdRx.IsMatch(Game)) throw new InvalidDataException("manifest: bad game");
            if (!VerRx.IsMatch(Version)) throw new InvalidDataException("manifest: bad version"); if (!IdRx.IsMatch(Kind)) throw new InvalidDataException("manifest: bad kind");
            if (Files.Count == 0) throw new InvalidDataException("manifest: no files");
            Dictionary<string, bool> seen = new Dictionary<string, bool>(); long tot = 0;
            foreach (AssetFile f in Files) { if (!AssetFile.PathAllowedForGame(Game, f.Path)) throw new InvalidDataException(U.R("Набор содержит файл вне разрешённой папки игры: ", "The set has a file outside the allowed game folder: ") + f.Path); }
            foreach (AssetFile f in Files) { string k = f.Path.ToLowerInvariant(); if (seen.ContainsKey(k)) throw new InvalidDataException("manifest: duplicate path " + f.Path); seen[k] = true; tot += f.Size; }
            if (tot > MaxTotal) throw new InvalidDataException("manifest: too large");
        }
    }

    class AssetRecFile { public string Path, Applied, Orig; public long Size, Mtime; }   // Orig "-" = the file was new
    class AssetRec
    {
        public string Id = "", Version = "", Kind = "graphics", State = "applied", NameRu = "", NameEn = ""; public int Layer = -1;   // -1 = old record: by kind
        public int EffLayer { get { return Layer >= 0 ? Layer : AssetManifest.DefaultLayer(Kind); } } public List<AssetRecFile> Files = new List<AssetRecFile>();
        public string Name { get { string n = L.Ru ? NameRu : L.Kor(NameEn); return n.Length > 0 ? n : (NameEn.Length > 0 ? NameEn : (NameRu.Length > 0 ? NameRu : Id)); } }
    }
    class AssetQuick { public AssetRec Rec; public bool Intact; }   // Intact: every file still has the size and time we recorded (no hashing)
    class AssetState
    {
        public int Total, Applied, Orig, Other, Missing, Unknown;
        public bool IsApplied { get { return Total > 0 && Applied == Total; } }
        public bool IsOriginal { get { return Total > 0 && Orig == Total; } }
        public bool IsMixed { get { return !IsApplied && !IsOriginal && Unknown == 0; } }
        public string Word { get { return IsApplied ? "applied" : (IsOriginal ? "original" : (Unknown > 0 ? "unknown" : "mixed")); } }
    }

    class AssetSets
    {
        public readonly string GameDir, GameId, Root, Proc; public Action<string> Log = delegate { };
        AssetProgress prog = delegate { }; Func<bool> cancel = delegate { return false; }; string label = "";
        public AssetSets(string gameDir, string gameId, string dataRoot, string processName) { GameDir = gameDir; GameId = gameId; Root = dataRoot; Proc = processName; }

        // ---------------------------------------------------------------- addresses
        // ONE place for the address of the sets: switch the host here (and add it to Net.TrustedHosts); nothing else in the logic depends on the host
        public const string DefaultBase = "https://gameremix.pro/assets/";
        public static string BaseUrl(string gameId)
        {
            string o = Environment.GetEnvironmentVariable("OGF_ASSETS_URL");   // tests / staging: where the catalog of this game lives
            if (!string.IsNullOrEmpty(o)) return o.EndsWith("/") ? o : o + "/";
            return DefaultBase + gameId + "/";
        }
        string CacheDir(AssetManifest m) { return Path.Combine(Path.Combine(Path.Combine(Fetcher.CacheRoot, "assets"), GameId), m.Id + "-" + m.Version); }
        string SetRoot(string id) { return Path.Combine(Root, id); }
        string RecPath(string id) { return Path.Combine(SetRoot(id), "active.txt"); }
        string Bak(string id, string rel) { return Path.Combine(Path.Combine(SetRoot(id), "orig"), rel); }
        string Full(string rel) { return Path.Combine(GameDir, rel); }
        string ManDir { get { return Path.Combine(Root, "manifests"); } }

        // ---------------------------------------------------------------- small helpers
        public static string Fmt(long b)
        {
            if (b >= 1073741824L) return (b / 1073741824.0).ToString("0.0") + U.R(" ГБ", " GB");
            return Math.Max(1, (long)Math.Round(b / 1048576.0)) + U.R(" МБ", " MB");
        }
        static void Del(string p) { if (!File.Exists(p)) return; try { File.SetAttributes(p, FileAttributes.Normal); } catch { } File.Delete(p); }
        static void PruneEmpty(string dir)   // removes empty folders only; anything with a file in it stays
        {
            if (!Directory.Exists(dir)) return;
            foreach (string d in Directory.GetDirectories(dir)) PruneEmpty(d);
            if (Directory.GetFileSystemEntries(dir).Length == 0) Directory.Delete(dir);
        }
        static void WriteText(string path, string text)   // write beside, then replace: a crash never leaves a half-written record
        {
            Directory.CreateDirectory(Path.GetDirectoryName(path)); string tmp = path + ".tmp"; File.WriteAllText(tmp, text, new UTF8Encoding(false));
            if (File.Exists(path)) { try { File.Replace(tmp, path, null); return; } catch { Del(path); } }
            File.Move(tmp, path);
        }
        public bool Running() { if (Environment.GetEnvironmentVariable("OGF_TEST_NOGUARD") == "1") return false; try { return System.Diagnostics.Process.GetProcessesByName(Proc).Length > 0; } catch { return false; } }
        void Check() { if (cancel()) throw new CancelledEx(); }
        void Say(string t, long d, long tot) { prog(t, d, tot); }
        static HashAlgorithm NewSha() { try { return new SHA256CryptoServiceProvider(); } catch (Exception) { return SHA256.Create(); } }

        void NeedSpace(Dictionary<string, long> need)
        {
            foreach (KeyValuePair<string, long> kv in need)
            {
                long free;
                try { free = new DriveInfo(kv.Key).AvailableFreeSpace; } catch (Exception) { continue; }   // a network folder: cannot be measured, the write itself will tell
                if (free < kv.Value + 64L * 1048576) throw new IOException(U.R("Не хватает места на диске " + kv.Key + ": нужно ещё ", "Not enough free space on " + kv.Key + ": ") + Fmt(kv.Value + 64L * 1048576 - Math.Max(0, free)) + U.R(" (свободно " + Fmt(free) + ").", " more needed (" + Fmt(free) + " free)."));
            }
        }
        static void AddNeed(Dictionary<string, long> need, string path, long bytes)
        {
            string r = Path.GetPathRoot(Path.GetFullPath(path)).ToUpperInvariant(); long c; need.TryGetValue(r, out c); need[r] = c + bytes;
        }

        // ---------------------------------------------------------------- hashing with a (path,size,time) cache: a 500 MB archive is read once, not on every look
        class HcEntry { public long Size, Mtime; public string Sha; }
        Dictionary<string, HcEntry> hc; bool hcDirty;
        string HcFile { get { return Path.Combine(Root, "hashcache.txt"); } }
        void HcLoad()
        {
            if (hc != null) return; hc = new Dictionary<string, HcEntry>();
            try { if (File.Exists(HcFile)) foreach (string ln in File.ReadAllLines(HcFile, Encoding.UTF8)) { string[] p = ln.Split('|'); long s, t; if (p.Length == 4 && long.TryParse(p[1], out s) && long.TryParse(p[2], out t) && p[3].Length == 64) { HcEntry e = new HcEntry(); e.Size = s; e.Mtime = t; e.Sha = p[3]; hc[p[0]] = e; } } } catch { }
        }
        void HcSave()
        {
            if (!hcDirty || hc == null) return;
            try { List<string> l = new List<string>(); foreach (KeyValuePair<string, HcEntry> kv in hc) if (File.Exists(kv.Key)) l.Add(kv.Key + "|" + kv.Value.Size + "|" + kv.Value.Mtime + "|" + kv.Value.Sha); WriteText(HcFile, string.Join("\r\n", l.ToArray()) + "\r\n"); hcDirty = false; } catch { }
        }
        void HcPut(string path, string sha) { HcLoad(); FileInfo fi = new FileInfo(path); HcEntry e = new HcEntry(); e.Size = fi.Length; e.Mtime = fi.LastWriteTimeUtc.Ticks; e.Sha = sha; hc[path.ToLowerInvariant()] = e; hcDirty = true; }
        string HashCached(string path)
        {
            HcLoad(); FileInfo fi = new FileInfo(path); HcEntry e; if (!fi.Exists) return null;
            return hc.TryGetValue(path.ToLowerInvariant(), out e) && e.Size == fi.Length && e.Mtime == fi.LastWriteTimeUtc.Ticks ? e.Sha : null;
        }
        string Hash(string path)
        {
            string c = HashCached(path); if (c != null) return c;
            long len = new FileInfo(path).Length, done = 0;
            using (FileStream fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete)) using (HashAlgorithm h = NewSha())
            {
                byte[] buf = new byte[1048576]; int n;
                while ((n = fs.Read(buf, 0, buf.Length)) > 0) { Check(); h.TransformBlock(buf, 0, n, null, 0); done += n; Say(label + Path.GetFileName(path), done, len); }
                h.TransformFinalBlock(new byte[0], 0, 0); string sha = Net.Hex(h.Hash); HcPut(path, sha); return sha;
            }
        }

        // ---------------------------------------------------------------- records
        AssetRec ReadRec(string id)
        {
            string f = RecPath(id); if (!File.Exists(f)) return null;
            AssetRec r = new AssetRec(); r.Id = id;
            foreach (string raw in File.ReadAllLines(f, Encoding.UTF8))
            {
                int eq = raw.IndexOf('='); if (eq <= 0) continue; string k = raw.Substring(0, eq), v = raw.Substring(eq + 1);
                if (k == "version") r.Version = v; else if (k == "kind") r.Kind = v; else if (k == "layer") { int ly; if (int.TryParse(v, out ly)) r.Layer = ly; } else if (k == "state") r.State = v; else if (k == "name.ru") r.NameRu = v; else if (k == "name.en") r.NameEn = v;
                else if (k == "file")
                {
                    string[] p = v.Split('|'); AssetRecFile rf = new AssetRecFile();
                    if (p.Length != 5 || !long.TryParse(p[3], out rf.Size) || !long.TryParse(p[4], out rf.Mtime)) continue;
                    try { rf.Path = AssetFile.NormPath(p[0]); } catch (InvalidDataException) { continue; }   // a hand-edited record cannot point outside the game folder
                    rf.Applied = p[1]; rf.Orig = p[2]; r.Files.Add(rf);
                }
            }
            return r;
        }
        void WriteRec(AssetRec r)
        {
            StringBuilder sb = new StringBuilder("OGF-ASSET-ACTIVE 1\r\n");
            sb.Append("id=" + r.Id + "\r\nversion=" + r.Version + "\r\nkind=" + r.Kind + "\r\nlayer=" + r.EffLayer + "\r\nstate=" + r.State + "\r\nname.ru=" + r.NameRu + "\r\nname.en=" + r.NameEn + "\r\ntime=" + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + "\r\n");
            foreach (AssetRecFile f in r.Files) sb.Append("file=" + f.Path + "|" + f.Applied + "|" + f.Orig + "|" + f.Size + "|" + f.Mtime + "\r\n");
            WriteText(RecPath(r.Id), sb.ToString());
        }
        public List<AssetRec> ActiveRecs()
        {
            List<AssetRec> l = new List<AssetRec>(); if (!Directory.Exists(Root)) return l;
            foreach (string d in Directory.GetDirectories(Root)) { string id = Path.GetFileName(d); if (id == "manifests") continue; try { AssetRec r = ReadRec(id); if (r != null) l.Add(r); } catch { } }
            return l;
        }
        // no hashing: does the record still describe the files (same size and time)? used for the status text on the main page
        public List<AssetQuick> Quick()
        {
            List<AssetQuick> l = new List<AssetQuick>();
            List<AssetRec> recs = ActiveRecs();
            foreach (AssetRec r in recs)
            {
                AssetQuick q = new AssetQuick(); q.Rec = r; q.Intact = r.State == "applied" && r.Files.Count > 0;
                foreach (AssetRecFile f in r.Files) { if (CoveredByTop(recs, r, f.Path)) continue; FileInfo fi = new FileInfo(Full(f.Path)); if (!fi.Exists || fi.Length != f.Size || f.Mtime == 0 || fi.LastWriteTimeUtc.Ticks != f.Mtime) q.Intact = false; }
                l.Add(q);
            }
            return l;
        }

        // the file belongs to a set that sits on top of this one (a skin over the graphics set): its size/time are the upper set's business
        static bool CoveredByTop(List<AssetRec> recs, AssetRec r, string path)
        {
            foreach (AssetRec o in recs) { if (o.Id == r.Id || o.EffLayer <= r.EffLayer) continue; foreach (AssetRecFile g in o.Files) if (string.Equals(g.Path, path, StringComparison.OrdinalIgnoreCase)) return true; }
            return false;
        }
        // an interrupted swap (power loss, killed process): put the files that were moved aside back, remove half-written ones
        public void Recover()
        {
            foreach (AssetRec r in ActiveRecs())
            {
                bool changed = false;
                foreach (AssetRecFile f in r.Files)
                {
                    string full = Full(f.Path), old = full + ".ogf-old", nw = full + ".ogf-new";
                    try
                    {
                        if (r.State == "applying" && File.Exists(old)) { Del(full); File.Move(old, full); changed = true; Log("assets: restored " + f.Path + " after an interrupted swap"); }
                        else if (File.Exists(old)) Del(old);
                        Del(nw);
                    }
                    catch (Exception ex) { Log("assets: recover " + f.Path + ": " + ex.Message); }
                }
                if (r.State == "applying") { r.State = "applied"; foreach (AssetRecFile f in r.Files) f.Mtime = 0; WriteRec(r); }   // what is really there is decided by hashes, not by this record
                if (changed) Log("assets: interrupted change of '" + r.Id + "' rolled back");
            }
        }

        // ---------------------------------------------------------------- manifests
        string Resolve(AssetManifest m, string url)
        {
            Uri b = new Uri(m.SourceUrl), u = new Uri(b, url);
            bool sameHost = u.Scheme == b.Scheme && string.Equals(u.Host, b.Host, StringComparison.OrdinalIgnoreCase) && u.Port == b.Port;
            bool trusted = u.Scheme == Uri.UriSchemeHttps && Net.TrustedHost(u.Host);   // the files may also sit on another trusted host of ours (a mirror, a CDN domain)
            if (!sameHost && !trusted) throw new InvalidDataException(U.R("Адрес файла в манифесте ведёт на чужой сервер, отклонено.", "A file address in the manifest points to a foreign server, rejected."));
            return u.ToString();
        }
        static void CheckHost(string url)
        {
            Uri u = new Uri(url);
            if (Net.LoopbackTestHttp(u) || (!string.IsNullOrEmpty(Environment.GetEnvironmentVariable("OGF_ASSETS_URL")) && u.Scheme == Uri.UriSchemeHttps)) return;
            if (u.Scheme != Uri.UriSchemeHttps || !Net.TrustedHost(u.Host)) throw new WebException(U.R("Наборы берутся только с gameremix.pro.", "Asset sets come only from gameremix.pro."));
        }
        public AssetManifest FetchManifest(string id)
        {
            string url = BaseUrl(GameId) + id + "/manifest.txt"; CheckHost(url);
            string text = Net.GetString(url, 262144, 30000); AssetManifest m = AssetManifest.Parse(text, url);
            if (m.Id != id) throw new InvalidDataException("manifest: id differs from the address");
            if (m.Game != GameId) throw new InvalidDataException(U.R("Набор сделан для другой игры.", "The set was made for another game."));
            try { WriteText(Path.Combine(ManDir, id + ".txt"), "# " + url + "\r\n" + text); } catch { }
            return m;
        }
        public AssetManifest CachedManifest(string id)
        {
            string f = Path.Combine(ManDir, id + ".txt"); if (!File.Exists(f)) return null;
            try
            {
                string[] ln = File.ReadAllLines(f, Encoding.UTF8); string url = ln.Length > 0 && ln[0].StartsWith("# ") ? ln[0].Substring(2).Trim() : BaseUrl(GameId) + id + "/manifest.txt";
                AssetManifest m = AssetManifest.Parse(string.Join("\n", ln), url); return m.Game == GameId && m.Id == id ? m : null;
            }
            catch (Exception) { return null; }
        }
        // the sets this game offers; offline (or a broken catalog) -> the manifests seen before. note: why the list may be incomplete ("" = fine)
        public bool Offline;   // the last LoadCatalog could not reach the server (the list came from the cache)
        public List<AssetManifest> LoadCatalog(out string note)
        {
            List<AssetManifest> l = new List<AssetManifest>(); note = ""; Offline = false;
            try
            {
                string url = BaseUrl(GameId) + "catalog.txt"; CheckHost(url); string t = Net.GetString(url, 65536, 30000); bool head = false;
                foreach (string raw in t.TrimStart('﻿').Replace("\r\n", "\n").Split('\n'))
                {
                    string ln = raw.Trim(); if (ln.Length == 0 || ln[0] == '#') continue;
                    if (!head) { if (!Regex.IsMatch(ln, @"^OGF-ASSET-CATALOG\s+1$")) throw new InvalidDataException("catalog"); head = true; continue; }
                    if (ln.StartsWith("set=")) { try { l.Add(FetchManifest(ln.Substring(4).Trim())); } catch (Exception ex) { Log("assets: manifest " + ln + ": " + ex.Message); note = U.R("Часть наборов не удалось получить.", "Some sets could not be fetched."); } }
                }
                if (!head) throw new InvalidDataException("catalog");
                return l;
            }
            catch (Exception ex)
            {
                Log("assets: catalog: " + ex.Message); l.Clear(); Offline = true;
                note = U.R("Нет связи с сервером наборов — показаны ранее полученные. ", "The sets server is not reachable - showing what was fetched before. ") + ex.Message;
                if (Directory.Exists(ManDir)) foreach (string f in Directory.GetFiles(ManDir, "*.txt")) { AssetManifest m = CachedManifest(Path.GetFileNameWithoutExtension(f)); if (m != null) l.Add(m); }
                return l;
            }
        }

        // ---------------------------------------------------------------- state by hashes
        public AssetState StateOf(AssetManifest m, bool deep, AssetProgress p, Func<bool> c)
        {
            prog = p ?? delegate { }; cancel = c ?? delegate { return false; }; label = U.R("Проверка ", "Checking "); AssetState s = new AssetState(); s.Total = m.Files.Count;
            foreach (AssetFile f in m.Files)
            {
                string full = Full(f.Path);
                if (!File.Exists(full)) { if (f.IsNew) s.Orig++; else s.Missing++; continue; }
                string h = deep ? Hash(full) : HashCached(full);
                if (h == null) s.Unknown++; else if (h == f.Sha) s.Applied++; else if (Array.IndexOf(f.Orig, h) >= 0) s.Orig++; else s.Other++;
            }
            HcSave(); return s;
        }
        // bytes that still have to be downloaded for this set (what is already in the cache or already installed counts as done)
        public long NeedBytes(AssetManifest m)
        {
            long need = 0; string cd = CacheDir(m);
            foreach (AssetFile f in m.Files)
            {
                try
                {
                    if (File.Exists(Full(f.Path)) && HashCached(Full(f.Path)) == f.Sha) continue;
                    string cf = CachePath(cd, f); if (File.Exists(cf) && new FileInfo(cf).Length == f.CSize) continue;
                    long part = File.Exists(cf + ".part") ? new FileInfo(cf + ".part").Length : 0; need += Math.Max(0, f.CSize - part);
                }
                catch { need += f.CSize; }
            }
            return need;
        }
        public bool IsCached(AssetManifest m)
        {
            string cd = CacheDir(m); foreach (AssetFile f in m.Files) { string cf = CachePath(cd, f); if (!File.Exists(cf) || new FileInfo(cf).Length != f.CSize) return false; } return true;
        }
        static string CachePath(string dir, AssetFile f) { return Path.Combine(dir, f.CSha.Substring(0, 12) + "-" + Path.GetFileName(f.Path) + (f.Gzip ? ".gz" : "")); }

        // ---------------------------------------------------------------- apply
        public void Apply(AssetManifest m, AssetProgress progress, Func<bool> cancelled)
        {
            prog = progress ?? delegate { }; cancel = cancelled ?? delegate { return false; }; label = U.R("Проверка ", "Checking ");
            try { ApplyCore(m); } finally { HcSave(); }
        }
        void ApplyCore(AssetManifest m)
        {
            if (m.Game != GameId) throw new InvalidDataException(U.R("Набор сделан для другой игры.", "The set was made for another game."));
            if (Running()) throw new InvalidOperationException(L.T("running"));
            string tls = Net.Tls(); if (tls != null) throw new WebException(tls);
            Recover();
            AssetRec prev = ReadRec(m.Id);
            // sets of the same kind replace each other (one graphics pack at a time); another kind may live beside it unless it owns the same file
            foreach (AssetRec o in ActiveRecs())
            {
                if (o.Id == m.Id) continue;
                bool overlap = false; foreach (AssetFile f in m.Files) foreach (AssetRecFile rf in o.Files) if (string.Equals(f.Path, rf.Path, StringComparison.OrdinalIgnoreCase)) overlap = true;
                bool stacks = overlap && o.Kind != m.Kind && o.EffLayer < m.Layer;   // a skin goes on top of the graphics set that owns the same archives (its list of originals names that set's files; checked below)
                if (o.Kind == m.Kind || (overlap && !stacks)) { Log("assets: '" + o.Id + "' is replaced by '" + m.Id + "'"); RevertWithTop(o); }
            }

            // 1. are the player's files the originals this set was made for?
            int n = m.Files.Count; string[] cur = new string[n], baseSha = new string[n]; List<string> bad = new List<string>(); long checkedBytes = 0;
            for (int i = 0; i < n; i++)
            {
                AssetFile f = m.Files[i]; string full = Full(f.Path), bak = Bak(m.Id, f.Path); Check();
                cur[i] = File.Exists(full) ? Hash(full) : null; checkedBytes += f.Size;
                if (f.IsNew)
                {
                    if (cur[i] != null && cur[i] != f.Sha) bad.Add(f.Path + U.R(" (в папке уже есть другой файл)", " (another file is already there)"));
                    continue;
                }
                if (File.Exists(bak))
                {
                    string bs = Hash(bak);
                    if (Array.IndexOf(f.Orig, bs) < 0) throw new AssetIncompatible(U.R("Резервная копия оригинала повреждена или от другой версии игры: ", "The backup of the original is damaged or from another game version: ") + bak + U.R("\r\nНичего не изменено. Верните оригиналы (Steam: «Проверить целостность файлов»), удалите эту папку и повторите.", "\r\nNothing was changed. Restore the originals (Steam: \"Verify integrity of game files\"), delete that folder and try again."));
                    if (cur[i] != null && cur[i] != f.Sha && Array.IndexOf(f.Orig, cur[i]) < 0) bad.Add(f.Path + U.R(" (изменён после применения набора)", " (changed after the set was applied)"));
                    baseSha[i] = bs;
                }
                else
                {
                    if (cur[i] == null) bad.Add(f.Path + U.R(" (нет файла)", " (missing)"));
                    else if (Array.IndexOf(f.Orig, cur[i]) < 0) bad.Add(f.Path + (cur[i] == f.Sha ? U.R(" (набор уже стоит, но нашей копии оригинала нет)", " (the set is there but we have no backup of the original)") : U.R(" (другая версия файла)", " (another version of the file)")));
                    else baseSha[i] = cur[i];
                }
            }
            if (bad.Count > 0)
            {
                string show = string.Join("\r\n", bad.GetRange(0, Math.Min(6, bad.Count)).ToArray()) + (bad.Count > 6 ? "\r\n…" : "");
                throw new AssetIncompatible(U.R("Набор не подходит к вашим файлам игры (другая версия или файлы уже изменены):\r\n", "The set does not fit your game files (another version or the files were changed):\r\n") + show + U.R("\r\n\r\nНичего не изменено и не скачано.", "\r\n\r\nNothing was changed or downloaded."));
            }
            List<int> todo = new List<int>(); for (int i = 0; i < n; i++) if (cur[i] != m.Files[i].Sha) todo.Add(i);
            if (todo.Count == 0)   // already there: only make sure our record exists
            {
                if (prev == null) { Log("assets: the files of '" + m.Id + "' are in place but have no backup of the originals"); throw new AssetIncompatible(U.R("Файлы набора уже стоят, но резервной копии оригиналов нет — откатить будет нечем.", "The set's files are already there but there is no backup of the originals to revert to.")); }
                Log("assets: '" + m.Id + "' is already applied"); StampRec(prev, m); return;
            }

            // 2. room on the disks (game folder: new files; profile: backup of the originals; cache: the download)
            Dictionary<string, long> need = new Dictionary<string, long>(); string cd = CacheDir(m);
            foreach (int i in todo)
            {
                AssetFile f = m.Files[i]; AddNeed(need, Full(f.Path), f.Size);
                if (!f.IsNew && !File.Exists(Bak(m.Id, f.Path))) AddNeed(need, Bak(m.Id, f.Path), cur[i] == null ? 0 : new FileInfo(Full(f.Path)).Length);
                string cf = CachePath(cd, f); if (!File.Exists(cf)) AddNeed(need, cf, f.CSize - (File.Exists(cf + ".part") ? new FileInfo(cf + ".part").Length : 0));
            }
            NeedSpace(need);

            // 3. download (resumable) into the cache and verify
            long totalDl = 0; foreach (int i in todo) totalDl += m.Files[i].CSize; long doneDl = 0; string[] cached = new string[n];
            foreach (int i in todo)
            {
                AssetFile f = m.Files[i]; string cf = CachePath(cd, f); cached[i] = cf; Check();
                bool ok = File.Exists(cf) && new FileInfo(cf).Length == f.CSize && Hash(cf) == f.CSha;
                if (!ok)
                {
                    Del(cf); string part = cf + ".part"; long before = doneDl; string nm = Path.GetFileName(f.Path);
                    Action<long, long> dp = delegate(long d, long t) { Say(U.R("Загрузка ", "Downloading ") + nm + " - " + Fmt(before + d) + " / " + Fmt(totalDl), before + d, totalDl); };
                    string alt = m.AltUrl(f);
                    if (alt != null) { try { Net.DownloadResume(alt, part, f.CSize, cancel, dp); } catch (Exception ex) { if (cancel()) throw; Log("assets: alternative host failed (" + ex.Message + "), using the main one: " + nm); Net.DownloadResume(Resolve(m, f.Url), part, f.CSize, cancel, dp); } }
                    else Net.DownloadResume(Resolve(m, f.Url), part, f.CSize, cancel, dp);
                    label = U.R("Проверка ", "Checking "); string got = Hash(part);
                    if (got != f.CSha) { Del(part); throw new IOException(U.R("Контрольная сумма скачанного файла не совпала, файл отброшен: ", "The checksum of the downloaded file does not match, it was discarded: ") + nm); }
                    File.Move(part, cf);
                }
                doneDl += f.CSize;
            }

            // 4. unpack next to the target (same disk: the swap below is a rename) and verify the result
            List<string> staged = new List<string>(), madeBak = new List<string>(); long stagedBytes = 0, totalStage = 0; foreach (int i in todo) totalStage += m.Files[i].Size;
            List<int> moved = new List<int>(), placed = new List<int>(); bool swapping = false;
            try
            {
                foreach (int i in todo)
                {
                    AssetFile f = m.Files[i]; string full = Full(f.Path), nw = full + ".ogf-new"; Check(); Directory.CreateDirectory(Path.GetDirectoryName(full)); Del(nw); staged.Add(nw);
                    using (FileStream src = new FileStream(cached[i], FileMode.Open, FileAccess.Read, FileShare.Read))
                    using (FileStream o = new FileStream(nw, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                    using (HashAlgorithm h = NewSha())
                    {
                        Stream rd = f.Gzip ? (Stream)new GZipStream(src, CompressionMode.Decompress) : src; byte[] buf = new byte[1048576]; int k; long sz = 0;
                        while ((k = rd.Read(buf, 0, buf.Length)) > 0)
                        {
                            Check(); sz += k; if (sz > f.Size) throw new IOException(U.R("Распакованный файл больше заявленного, отклонён.", "The unpacked file is larger than declared, rejected."));
                            o.Write(buf, 0, k); h.TransformBlock(buf, 0, k, null, 0); stagedBytes += k; Say(U.R("Подготовка ", "Preparing ") + Path.GetFileName(f.Path), stagedBytes, totalStage);
                        }
                        h.TransformFinalBlock(new byte[0], 0, 0); o.Flush();
                        if (sz != f.Size || Net.Hex(h.Hash) != f.Sha) throw new IOException(U.R("Распакованный файл не совпал с контрольной суммой: ", "The unpacked file does not match its checksum: ") + Path.GetFileName(f.Path));
                    }
                }

                // 5. the backup of the originals (only when there is none yet - a backup is never rewritten, and never made from something that is not an original)
                long bakBytes = 0, bakTotal = 0; foreach (int i in todo) if (!m.Files[i].IsNew && !File.Exists(Bak(m.Id, m.Files[i].Path)) && cur[i] != null) bakTotal += new FileInfo(Full(m.Files[i].Path)).Length;
                foreach (int i in todo)
                {
                    AssetFile f = m.Files[i]; string bak = Bak(m.Id, f.Path); if (f.IsNew || File.Exists(bak) || cur[i] == null) continue; Check();
                    Directory.CreateDirectory(Path.GetDirectoryName(bak)); string tmp = bak + ".tmp"; Del(tmp); string nm = Path.GetFileName(f.Path);
                    using (FileStream s = new FileStream(Full(f.Path), FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete)) using (FileStream d = new FileStream(tmp, FileMode.CreateNew, FileAccess.Write, FileShare.None)) using (HashAlgorithm h = NewSha())
                    {
                        byte[] buf = new byte[1048576]; int k;
                        while ((k = s.Read(buf, 0, buf.Length)) > 0) { Check(); d.Write(buf, 0, k); h.TransformBlock(buf, 0, k, null, 0); bakBytes += k; Say(U.R("Резервная копия ", "Backing up ") + nm, bakBytes, bakTotal); }
                        h.TransformFinalBlock(new byte[0], 0, 0); d.Flush();
                        if (Net.Hex(h.Hash) != baseSha[i]) throw new IOException(U.R("Резервная копия не совпала с оригиналом (файл менялся во время копирования?): ", "The backup does not match the original (the file changed while copying?): ") + nm);
                    }
                    File.Move(tmp, bak); madeBak.Add(bak);
                }

                // 6. swap. From here on the change is not cancellable; any failure puts every file back.
                Say(U.R("Установка…", "Installing…"), 0, 0);
                AssetRec rec = new AssetRec(); rec.Id = m.Id; rec.Version = m.Version; rec.Kind = m.Kind; rec.Layer = m.Layer; rec.NameRu = m.NameRu; rec.NameEn = m.NameEn; rec.State = "applying";
                for (int i = 0; i < n; i++) { AssetRecFile rf = new AssetRecFile(); rf.Path = m.Files[i].Path; rf.Applied = m.Files[i].Sha; rf.Orig = m.Files[i].IsNew ? "-" : baseSha[i]; rec.Files.Add(rf); }
                WriteRec(rec); swapping = true;
                int failAt = -1; string fsw = Environment.GetEnvironmentVariable("OGF_ASSETS_FAILSWAP"); if (fsw == null || !int.TryParse(fsw, out failAt)) failAt = -1;   // test hook: fail after N files were swapped
                foreach (int i in todo)
                {
                    string full = Full(m.Files[i].Path), old = full + ".ogf-old"; Del(old);
                    if (File.Exists(full)) { File.Move(full, old); moved.Add(i); }
                    if (failAt >= 0 && placed.Count == failAt) throw new IOException("test: swap failure injected");
                    File.Move(full + ".ogf-new", full); placed.Add(i);
                }
                foreach (AssetRecFile rf in rec.Files) { FileInfo fi = new FileInfo(Full(rf.Path)); rf.Size = fi.Length; rf.Mtime = fi.LastWriteTimeUtc.Ticks; HcPut(Full(rf.Path), rf.Applied); }
                rec.State = "applied"; WriteRec(rec); swapping = false;
                foreach (int i in todo) { try { Del(Full(m.Files[i].Path) + ".ogf-old"); } catch (Exception ex) { Log("assets: leftover " + m.Files[i].Path + ".ogf-old: " + ex.Message); } }
                Log(L.T("applied") + "asset set " + m.Id + " " + m.Version + " (" + todo.Count + " files)");
            }
            catch (Exception)
            {
                List<string> undo = new List<string>();
                for (int k = placed.Count - 1; k >= 0; k--) { try { Del(Full(m.Files[placed[k]].Path)); } catch (Exception e2) { undo.Add(m.Files[placed[k]].Path + ": " + e2.Message); } }
                for (int k = moved.Count - 1; k >= 0; k--) { string full = Full(m.Files[moved[k]].Path); try { if (File.Exists(full + ".ogf-old")) File.Move(full + ".ogf-old", full); } catch (Exception e2) { undo.Add(m.Files[moved[k]].Path + ": " + e2.Message); } }
                foreach (string s in staged) { try { Del(s); } catch { } }
                if (undo.Count == 0)
                {
                    if (swapping) { try { if (prev != null) WriteRec(prev); else Del(RecPath(m.Id)); } catch { } }
                    if (prev == null) foreach (string b in madeBak) { try { Del(b); } catch { } }   // a backup made by this failed try; an earlier one is never touched
                    try { string sd = SetRoot(m.Id); if (prev == null && !File.Exists(RecPath(m.Id))) PruneEmpty(sd); } catch { }
                }
                else Log("assets: rollback incomplete (" + string.Join("; ", undo.ToArray()) + "); it is finished at the next start");
                throw;
            }
        }
        void StampRec(AssetRec r, AssetManifest m)   // the same files again: refresh sizes/times, name and state
        {
            r.Version = m.Version; r.Kind = m.Kind; r.Layer = m.Layer; r.NameRu = m.NameRu; r.NameEn = m.NameEn; r.State = "applied";
            foreach (AssetRecFile rf in r.Files) { FileInfo fi = new FileInfo(Full(rf.Path)); if (fi.Exists) { rf.Size = fi.Length; rf.Mtime = fi.LastWriteTimeUtc.Ticks; } }
            WriteRec(r);
        }

        // ---------------------------------------------------------------- revert
        public void Revert(string id, AssetProgress progress, Func<bool> cancelled)
        {
            prog = progress ?? delegate { }; cancel = cancelled ?? delegate { return false; }; label = U.R("Проверка ", "Checking ");
            try
            {
                if (Running()) throw new InvalidOperationException(L.T("running"));
                Recover(); AssetRec r = ReadRec(id);
                if (r == null) { Log("assets: '" + id + "' is not applied"); return; }
                RevertWithTop(r);
            }
            finally { HcSave(); }
        }
        // every applied set, each on its own: one failure does not stop the others; the failures are reported together
        public void RevertAll(AssetProgress progress, Func<bool> cancelled)
        {
            prog = progress ?? delegate { }; cancel = cancelled ?? delegate { return false; }; label = U.R("Проверка ", "Checking ");
            try
            {
                if (!Directory.Exists(Root)) return;
                if (Running()) throw new InvalidOperationException(L.T("running"));
                Recover(); List<string> fails = new List<string>();
                List<AssetRec> all = ActiveRecs(); all.Sort(delegate(AssetRec a, AssetRec b) { return b.EffLayer.CompareTo(a.EffLayer); });   // the top layer first: a skin goes back before the graphics under it
                foreach (AssetRec r in all) { try { if (ReadRec(r.Id) != null) RevertRec(ReadRec(r.Id)); } catch (CancelledEx) { throw; } catch (Exception ex) { fails.Add(r.Id + ": " + ex.Message); } }
                if (fails.Count > 0) throw new IOException(string.Join("\r\n", fails.ToArray()));
            }
            finally { HcSave(); }
        }
        // a set that other sets sit on (same files, higher layer) can only go back after them
        void RevertWithTop(AssetRec r)
        {
            List<AssetRec> tops = new List<AssetRec>();
            foreach (AssetRec o in ActiveRecs()) { if (o.Id == r.Id || o.EffLayer <= r.EffLayer) continue; foreach (AssetRecFile f in r.Files) { bool hit = false; foreach (AssetRecFile g in o.Files) if (string.Equals(f.Path, g.Path, StringComparison.OrdinalIgnoreCase)) hit = true; if (hit) { tops.Add(o); break; } } }
            tops.Sort(delegate(AssetRec a, AssetRec b) { return b.EffLayer.CompareTo(a.EffLayer); });
            foreach (AssetRec o in tops) { Log("assets: '" + o.Id + "' goes back first (it sits on '" + r.Id + "')"); RevertRec(o); }
            RevertRec(ReadRec(r.Id) ?? r);
        }
        public void RevertRecPublic(string id) { AssetRec r = ReadRec(id); if (r != null) RevertWithTop(r); }
        void RevertRec(AssetRec rec)
        {
            List<string> fail = new List<string>(); List<AssetRecFile> todo = new List<AssetRecFile>(), done = new List<AssetRecFile>(); long totalBytes = 0, bytes = 0;
            foreach (AssetRecFile rf in rec.Files)
            {
                string full = Full(rf.Path), bak = Bak(rec.Id, rf.Path); Check();
                string cs = File.Exists(full) ? Hash(full) : null;
                if (rf.Orig == "-")   // a file the set added
                {
                    if (cs == null) done.Add(rf); else if (cs == rf.Applied) todo.Add(rf); else fail.Add(rf.Path + U.R(" (изменён после применения, не трогаю)", " (changed after the set was applied, left alone)"));
                    continue;
                }
                if (cs != null && cs == rf.Orig) { done.Add(rf); continue; }   // already the original (reinstall, integrity check)
                if (cs != null && cs != rf.Applied) { fail.Add(rf.Path + U.R(" (изменён после применения, не трогаю)", " (changed after the set was applied, left alone)")); continue; }
                if (!File.Exists(bak)) { fail.Add(rf.Path + U.R(" (нет резервной копии)", " (no backup)")); continue; }
                if (Hash(bak) != rf.Orig) { fail.Add(rf.Path + U.R(" (резервная копия повреждена)", " (the backup is damaged)")); continue; }
                todo.Add(rf); totalBytes += new FileInfo(bak).Length;
            }
            Dictionary<string, long> need = new Dictionary<string, long>(); foreach (AssetRecFile rf in todo) if (rf.Orig != "-") AddNeed(need, Full(rf.Path), new FileInfo(Bak(rec.Id, rf.Path)).Length);
            NeedSpace(need);
            List<string> staged = new List<string>(); List<AssetRecFile> moved = new List<AssetRecFile>(), placed = new List<AssetRecFile>();
            try
            {
                foreach (AssetRecFile rf in todo)
                {
                    if (rf.Orig == "-") continue; string full = Full(rf.Path), nw = full + ".ogf-new"; Check(); Directory.CreateDirectory(Path.GetDirectoryName(full)); Del(nw); staged.Add(nw);
                    using (FileStream s = new FileStream(Bak(rec.Id, rf.Path), FileMode.Open, FileAccess.Read, FileShare.Read)) using (FileStream d = new FileStream(nw, FileMode.CreateNew, FileAccess.Write, FileShare.None)) using (HashAlgorithm h = NewSha())
                    {
                        byte[] buf = new byte[1048576]; int k;
                        while ((k = s.Read(buf, 0, buf.Length)) > 0) { Check(); d.Write(buf, 0, k); h.TransformBlock(buf, 0, k, null, 0); bytes += k; Say(U.R("Возврат ", "Restoring ") + Path.GetFileName(rf.Path), bytes, totalBytes); }
                        h.TransformFinalBlock(new byte[0], 0, 0); d.Flush(); if (Net.Hex(h.Hash) != rf.Orig) throw new IOException(U.R("Копия оригинала не прошла проверку: ", "The copy of the original failed verification: ") + rf.Path);
                    }
                }
                foreach (AssetRecFile rf in todo)
                {
                    string full = Full(rf.Path), old = full + ".ogf-old"; Del(old);
                    if (File.Exists(full)) { File.Move(full, old); moved.Add(rf); }
                    if (rf.Orig != "-") { File.Move(full + ".ogf-new", full); placed.Add(rf); }
                }
            }
            catch (Exception)
            {
                for (int k = placed.Count - 1; k >= 0; k--) { try { Del(Full(placed[k].Path)); } catch { } }
                for (int k = moved.Count - 1; k >= 0; k--) { string full = Full(moved[k].Path); try { if (File.Exists(full + ".ogf-old")) File.Move(full + ".ogf-old", full); } catch { } }
                foreach (string s in staged) { try { Del(s); } catch { } }
                throw;
            }
            foreach (AssetRecFile rf in todo) { try { Del(Full(rf.Path) + ".ogf-old"); } catch { } if (rf.Orig != "-") { try { HcPut(Full(rf.Path), rf.Orig); } catch { } } }
            if (fail.Count == 0)
            {
                try { Directory.Delete(SetRoot(rec.Id), true); } catch (Exception ex) { Log("assets: cleanup " + rec.Id + ": " + ex.Message); }
                Log(L.T("reverted") + "asset set " + rec.Id);
                return;
            }
            rec.Files.RemoveAll(delegate(AssetRecFile f) { return todo.Contains(f) || done.Contains(f); });   // what went back is no longer ours; the rest keeps its record and backup
            WriteRec(rec);
            throw new IOException(U.R("Не все файлы набора «" + rec.Name + "» вернулись:\r\n", "Not every file of the set \"" + rec.Name + "\" went back:\r\n") + string.Join("\r\n", fail.ToArray()) + U.R("\r\n\r\nРезервные копии сохранены. Верните оригиналы проверкой целостности файлов (Steam) или переустановкой.", "\r\n\r\nThe backups are kept. Restore the originals with the integrity check (Steam) or a reinstall."));
        }
    }

    // ---------------------------------------------------------------- the Divine Divinity side: where its data lives, the "Revert all" step
    partial class Core
    {
        public const string AssetsGameId = "divine-divinity";
        AssetSets assets;
        public AssetSets Assets { get { if (assets == null) { assets = new AssetSets(Dir, AssetsGameId, Path.Combine(GameData, "assets"), "div"); assets.Log = delegate(string s) { Log(s); }; } return assets; } }
        public void RevertAssets() { if (HasGame) Assets.RevertAll(null, null); }
        // text for the status column / description on the main page, without hashing
        public string AssetsQuickText(out bool good)
        {
            good = false; if (!HasGame) return "";
            try
            {
                List<AssetQuick> q = Assets.Quick(); if (q.Count == 0) return "";
                AssetQuick a = q[0]; foreach (AssetQuick x in q) if (!x.Intact) a = x;
                good = a.Intact; return a.Intact ? "ok:" + a.Rec.Name : (a.Rec.State == "applying" ? "partial:" + a.Rec.Name : "changed:" + a.Rec.Name);
            }
            catch { return ""; }
        }
    }

    // choose a set: the original or one of the downloadable packs; apply / revert with a progress window
    class AssetsForm : ToolForm
    {
        List<AssetManifest> sets; string note; AssetState[] st; bool[] cached; long[] need; bool anyActive; bool busy;
        static Size SizeFor(int n) { int rows = Math.Max(1, n) + 1; return new Size(880, 12 + 66 + rows * 49 + 78 + 12 + 56 + 12 + 14); }
        public AssetsForm(Core c, List<AssetManifest> offered, string why) : base(c, SizeFor(offered.Count)) { sets = offered; note = why ?? ""; }
        protected override string TitleRu { get { return "Улучшенная графика"; } }
        protected override string TitleEn { get { return "Enhanced graphics"; } }
        protected override void BuildFoot() { FootBtn(T("Закрыть", "Close"), false, 120, delegate { Close(); }); }

        protected override void OnShown(EventArgs e) { base.OnShown(e); Detect(); }
        // hash the files once (cached afterwards): which set is really installed
        void Detect()
        {
            st = new AssetState[sets.Count]; cached = new bool[sets.Count]; need = new long[sets.Count]; anyActive = false; AssetSets a = Game.Assets;
            string err = WorkForm.Run(this, T("Улучшенная графика", "Enhanced graphics"), T("Проверяю файлы игры…", "Checking the game files…"), true, delegate(WorkForm w)
            {
                for (int i = 0; i < sets.Count; i++) { st[i] = a.StateOf(sets[i], true, delegate(string t, long d, long tot) { w.Report(t, d, tot); }, delegate { return w.Cancelled; }); cached[i] = a.IsCached(sets[i]); need[i] = a.NeedBytes(sets[i]); if (!st[i].IsOriginal) anyActive = true; }
            });
            if (err != null) { st = null; if (err.Length > 0) Status("Не удалось проверить файлы: " + err, "Could not check the files: " + err); }
            Reload();
        }
        protected override void Build(Panel body)
        {
            int rows = Math.Max(1, sets.Count) + 1;
            RPanel card = Card(body, 0, 0, body.Width, 66 + rows * 49 + 78, T("Улучшенная графика", "Enhanced graphics"), T("Готовые наборы с нашего сервера. Оригиналы сохраняются, откат одной кнопкой", "Ready-made sets from our server. Originals are kept, one-click revert"));
            List<Control> l = new List<Control>(); bool known = st != null;
            Btn bOrig = Act(T("Откатить", "Revert"), delegate { DoRevert(); }); bOrig.Enabled = known && anyActive && !busy;
            RowCtl ro = Row("◎", Th.Muted, T("Оригинал", "Original"), T("Графика игры без изменений", "The game's own graphics, unchanged"), bOrig);
            ro.Status = !known ? "…" : (anyActive ? "" : T("сейчас", "current")); ro.StatusColor = Th.Green; l.Add(ro);
            for (int i = 0; i < sets.Count; i++)
            {
                int k = i; AssetManifest m = sets[i]; AssetState s = known ? st[i] : null; bool on = s != null && s.IsApplied;
                Btn b = Act(on ? T("Откатить", "Revert") : T("Применить", "Apply"), delegate { if (on) DoRevert(); else DoApply(k); }); b.Enabled = known && !busy && (on || s.IsOriginal || s.IsMixed);
                RowCtl r = Row("✦", Th.Amber, m.Name, ShortDesc(m), b);
                if (!known) r.Status = "…";
                else if (on) { r.Status = T("применён", "applied"); r.StatusColor = Th.Green; }
                else if (s.IsMixed) { r.Status = T("частично", "partly"); r.StatusColor = Th.Amber; }
                else { r.Status = cached[k] ? T("скачан", "downloaded") : T("не скачан", "not downloaded"); r.StatusColor = cached[k] ? Th.Muted : Th.Faint; }
                l.Add(r);
            }
            if (sets.Count == 0) { RowCtl r = Row("✦", Th.Faint, T("Наборов нет", "No sets"), T("Список не получен, проверьте подключение", "The list was not received, check the connection"), new Label()); r.Ctl.Visible = false; l.Add(r); }
            int y = Lay(card, 66, l.ToArray());
            Label n = new Label(); n.AutoSize = false; n.SetBounds(14, y + 4, card.Width - 28, 66); n.Font = Th.F("Segoe UI", 8.5f, FontStyle.Regular); n.ForeColor = Th.Muted; n.BackColor = Th.Surf; n.UseMnemonic = false;
            n.Text = T("Набор заменяет файлы графики в папке игры (static\\imagelists). Оригиналы остаются в папке программы, «Откатить» возвращает их. Скачивание можно отменить и продолжить позже. Игру перед этим нужно закрыть.",
                       "A set replaces the graphics files in the game folder (static\\imagelists). The originals stay in the program's folder and \"Revert\" brings them back. A download can be cancelled and continued later. Close the game first.");
            card.Controls.Add(n);
            if (note.Length > 0 && st == null) Status(note, note);
        }
        static string ShortDesc(AssetManifest m) { return m.Desc + " · " + AssetSets.Fmt(m.Installed); }

        void Run(string title, string first, bool cancellable, Action<WorkForm> job, string okRu, string okEn)
        {
            if (Core.GameRunning()) { MessageBox.Show(this, L.T("running"), L.T("warnTitle")); return; }
            busy = true; string err;
            try { err = WorkForm.Run(this, title, first, cancellable, job); } finally { busy = false; }
            if (err == null) { Status(okRu, okEn); }
            else if (err.Length == 0) Status("Отменено. Скачанное сохранено — продолжится с того же места.", "Cancelled. What was downloaded is kept and continues from there.");
            else { Game.Log("assets: " + err); MessageBox.Show(this, err, L.T("errTitle"), MessageBoxButtons.OK, MessageBoxIcon.Warning); Status("Не получилось. Подробности в окне сообщения.", "Did not work. See the message."); }
            Detect();
        }
        void DoApply(int i)
        {
            AssetManifest m = sets[i]; AssetSets a = Game.Assets; long dl = a.NeedBytes(m);
            string q = T("Применить набор «" + m.Name + "»?\r\n\r\n", "Apply the set \"" + m.Name + "\"?\r\n\r\n")
                + (dl > 0 ? T("Нужно скачать: " + AssetSets.Fmt(dl) + " (с нашего сервера, можно отменить и продолжить позже).\r\n", "To download: " + AssetSets.Fmt(dl) + " (from our server; you can cancel and continue later).\r\n") : T("Всё уже скачано.\r\n", "Everything is already downloaded.\r\n"))
                + T("В папке игры файлы займут " + AssetSets.Fmt(m.Installed) + "; копия оригиналов для отката (до " + AssetSets.Fmt(m.Installed) + ") ляжет в папку программы в профиле.\r\nИгра на это время должна быть закрыта.",
                    "The game folder will use " + AssetSets.Fmt(m.Installed) + "; a copy of the originals for revert (up to " + AssetSets.Fmt(m.Installed) + ") goes to the program's folder in your profile.\r\nThe game must be closed.");
            if (MessageBox.Show(this, q, T("Улучшенная графика", "Enhanced graphics"), MessageBoxButtons.OKCancel, MessageBoxIcon.Question) != DialogResult.OK) return;
            Run(T("Улучшенная графика", "Enhanced graphics"), T("Подготовка…", "Preparing…"), true, delegate(WorkForm w) { a.Apply(m, delegate(string t, long d, long tot) { w.Report(t, d, tot); }, delegate { return w.Cancelled; }); },
                "Набор применён. Запускайте игру как обычно.", "The set is applied. Start the game as usual.");
        }
        void DoRevert()
        {
            AssetSets a = Game.Assets;
            Run(T("Улучшенная графика", "Enhanced graphics"), T("Возвращаю оригиналы…", "Restoring the originals…"), true, delegate(WorkForm w) { a.RevertAll(delegate(string t, long d, long tot) { w.Report(t, d, tot); }, delegate { return w.Cancelled; }); },
                "Оригинальная графика возвращена.", "The original graphics are back.");
        }
    }
}
