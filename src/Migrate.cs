// Move of the user's data from the old name (OldGameFixer) to GameRemix. Rules:
//  - same volume: the folder is simply RENAMED to GameRemix (instant, atomic; a start never waits for a long copy). Different volume: the copy below.
//  - %APPDATA%\GameRemix is made by COPYING the old folder as a whole into a temporary sibling, checking every file (path + size), and renaming it into place;
//    only then the old folder is renamed to "OldGameFixer.migrated" (kept as a reserve: it holds backups of the game's original files). Nothing is deleted.
//  - if anything fails the old folder is simply used as it is (DataDir returns it), nothing is lost.
//  - %LOCALAPPDATA%: the folders cache / tools / fontpack are moved (same volume, cheap, they are re-downloadable anyway); "app" (unpacked program) is not.
//  - tests: OGF_DATA/OGF_LOCAL are the new folders, OGF_LEGACY_DATA/OGF_LEGACY_LOCAL the old ones; with OGF_DATA but without OGF_LEGACY_DATA nothing is migrated.
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Threading;

namespace DDFixTool
{
    static class Migrate
    {
        public const string OldName = "OldGameFixer", NewName = "GameRemix";
        public static string LegacyData
        {
            get
            {
                string o = Environment.GetEnvironmentVariable("OGF_LEGACY_DATA"); if (!string.IsNullOrEmpty(o)) return o;
                if (!string.IsNullOrEmpty(Environment.GetEnvironmentVariable("OGF_DATA"))) return null;   // tests: never touch the real profile
                return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), OldName);
            }
        }
        public static string LegacyLocal
        {
            get
            {
                string o = Environment.GetEnvironmentVariable("OGF_LEGACY_LOCAL"); if (!string.IsNullOrEmpty(o)) return o;
                if (!string.IsNullOrEmpty(Environment.GetEnvironmentVariable("OGF_LOCAL"))) return null;
                return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), OldName);
            }
        }
        public static string Status = "";   // what happened in this run (for --data-info and the log)

        static bool HasFiles(string d) { try { return Directory.Exists(d) && (Directory.GetFiles(d, "*", SearchOption.AllDirectories).Length > 0); } catch { return true; } }
        static Dictionary<string, long> Listing(string root)
        {
            Dictionary<string, long> r = new Dictionary<string, long>(StringComparer.OrdinalIgnoreCase);
            foreach (string f in Directory.GetFiles(root, "*", SearchOption.AllDirectories)) r[f.Substring(root.Length).TrimStart('\\')] = new FileInfo(f).Length;
            foreach (string d in Directory.GetDirectories(root, "*", SearchOption.AllDirectories)) r[d.Substring(root.Length).TrimStart('\\') + "\\"] = -1;   // empty folders count too
            return r;
        }
        static void CopyTree(string src, string dst)
        {
            Directory.CreateDirectory(dst);
            foreach (string f in Directory.GetFiles(src)) File.Copy(f, Path.Combine(dst, Path.GetFileName(f)), false);
            foreach (string d in Directory.GetDirectories(src)) CopyTree(d, Path.Combine(dst, Path.GetFileName(d)));
        }
        static string FreeName(string p) { string n = p; for (int i = 2; Directory.Exists(n) || File.Exists(n); i++) n = p + "." + i; return n; }
        static void Note(string target, string msg)
        {
            Status += (Status.Length > 0 ? "; " : "") + msg;
            try { File.AppendAllText(Path.Combine(target, "log.txt"), DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + "   migration: " + msg + "\r\n", Encoding.UTF8); } catch { }
        }

        // Returns the folder to use as the data folder.
        public static string Data(string target)
        {
            string legacy = LegacyData;
            if (legacy == null || !Directory.Exists(legacy)) return target;
            if (string.Equals(Path.GetFullPath(legacy).TrimEnd('\\'), Path.GetFullPath(target).TrimEnd('\\'), StringComparison.OrdinalIgnoreCase)) return target;
            Mutex mx = new Mutex(false, "Local\\GameRemix.Migrate");
            try
            {
                try { if (!mx.WaitOne(15000)) return Directory.Exists(target) ? target : legacy; } catch (AbandonedMutexException) { }
                if (HasFiles(target)) { Status = "new folder already has data, the old one is left as it is"; return target; }
                // same volume (almost always): ONE rename - instant and atomic, so a start never waits minutes for a copy of gigabytes of backups; nothing can be half-moved
                try
                {
                    if (string.Equals(Path.GetPathRoot(Path.GetFullPath(legacy)), Path.GetPathRoot(Path.GetFullPath(target)), StringComparison.OrdinalIgnoreCase))
                    {
                        if (Directory.Exists(target)) Directory.Delete(target, true);   // only empty folders here (HasFiles was false): left by something else or by an earlier run
                        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(target)));
                        Directory.Move(legacy, target);
                        Note(target, "data moved from " + legacy + " (one rename, nothing copied)"); SetFlag(target); return target;
                    }
                }
                catch (Exception ex) { Status = "rename failed (" + ex.Message + "), trying a checked copy"; }
                if (!Directory.Exists(legacy)) return target;
                string tmp = target + ".migrating";
                try
                {
                    if (Directory.Exists(tmp)) Directory.Delete(tmp, true);   // an unfinished copy of an earlier try (ours, never user data)
                    Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(target)));
                    CopyTree(legacy, tmp);
                    Dictionary<string, long> a = Listing(legacy), b = Listing(tmp);
                    if (a.Count != b.Count) throw new IOException("file count differs: " + a.Count + " / " + b.Count);
                    foreach (KeyValuePair<string, long> kv in a) { long n; if (!b.TryGetValue(kv.Key, out n) || n != kv.Value) throw new IOException("differs: " + kv.Key); }
                    if (Directory.Exists(target)) { if (HasFiles(target)) throw new IOException("the new folder got data meanwhile"); Directory.Delete(target, true); }   // empty folders only (possibly with empty sub-folders: the old "false" made every start copy again)
                    Directory.Move(tmp, target);
                }
                catch (Exception ex)
                {
                    try { if (Directory.Exists(tmp)) Directory.Delete(tmp, true); } catch { }
                    Status = "FAILED, the old folder is used as it is: " + ex.Message; return legacy;
                }
                string res = FreeName(legacy + ".migrated");
                try { Directory.Move(legacy, res); Note(target, "data copied from " + legacy + " (" + Listing(target).Count + " entries, checked); old folder kept as " + res); }
                catch (Exception ex) { Note(target, "data copied from " + legacy + " (checked); the old folder could not be renamed (" + ex.Message + "), it stays as a reserve"); }
                SetFlag(target);
                return target;
            }
            finally { try { mx.ReleaseMutex(); } catch { } mx.Close(); }
        }
        static void SetFlag(string target)
        {
            try
            {
                string f = Path.Combine(target, "settings.ini"); List<string> l = new List<string>();
                if (File.Exists(f)) foreach (string ln in File.ReadAllLines(f, Encoding.UTF8)) if (!ln.StartsWith("migrated=")) l.Add(ln);
                l.Add("migrated=1"); File.WriteAllLines(f, l.ToArray(), Encoding.UTF8);
            }
            catch { }
        }

        // %LOCALAPPDATA%: cache, tools, fontpack... (everything but "app") move to the new folder when it does not have them yet
        public static void Local(string target)
        {
            string legacy = LegacyLocal;
            try
            {
                if (legacy == null || !Directory.Exists(legacy)) return;
                if (string.Equals(Path.GetFullPath(legacy).TrimEnd('\\'), Path.GetFullPath(target).TrimEnd('\\'), StringComparison.OrdinalIgnoreCase)) return;
                foreach (string d in Directory.GetDirectories(legacy))
                {
                    string n = Path.GetFileName(d); if (string.Equals(n, "app", StringComparison.OrdinalIgnoreCase) || n.StartsWith("app", StringComparison.OrdinalIgnoreCase) && n.Length > 3 && char.IsDigit(n[3])) continue;
                    string to = Path.Combine(target, n); if (Directory.Exists(to) || File.Exists(to)) continue;
                    try { Directory.CreateDirectory(target); Directory.Move(d, to); Status += (Status.Length > 0 ? "; " : "") + "local " + n + " moved"; }
                    catch (Exception ex) { Status += (Status.Length > 0 ? "; " : "") + "local " + n + " not moved (" + ex.Message + ")"; }
                }
            }
            catch { }
        }
    }
}
