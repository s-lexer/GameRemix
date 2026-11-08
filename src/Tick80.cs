// "FPS mod" = tick 80 (owner 07.11.2026): the world still steps 40 times a second, agents and the camera are shown at 80 (no interpolation). Docs/recon/2026-11-07_tick80.md section 5.
// The exe part is the byte patch "tick80" of gfx.txt (generated from patch_research/tick80_patch.py --frame by tools/make_exe_patches.py): hooks in .text, code and data in the first
// 4096 bytes of the .interp section of the frame, the agent table in the virtual tail of that section. It needs the frame (windows/glow/interp share it) and is NOT combinable with
// patch=interp (the same bytes: each sees the other as foreign, state "n/a"). Taking it out is byte for byte (SetBytePatch), the frame goes when nothing else lives in it.
// Settings the mode needs, put back EXACTLY on switching off (fps80_prev.txt in the game's data): gr-draw on with renderer=opengl, maxgameticks=-1 (0 = cnc-ddraw's "emulate 60 Hz"
// = the 60 FPS ceiling, docs/recon/2026-11-07_fps_cap.md), vsync=true, maxfps=-1 (monitor refresh); config.div "smooth 1" (the stock value; only a hand-made "smooth 0" is changed).
// Independent of Core.FpsEnabled (the frozen interpolation, src/Fps.cs).
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;

namespace DDFixTool
{
    partial class Core
    {
        const string Fps80Id = "tick80";
        static readonly string[] Fps80Keys = { "renderer", "maxgameticks", "vsync", "maxfps" };
        static readonly string[] Fps80Wants = { "opengl", "-1", "true", "-1" };
        static readonly string[] Fps80Defs = { "auto", "0", "true", "-1" };   // cnc-ddraw's own defaults: what comes back when there is no record
        string Fps80File { get { return Path.Combine(GameData, "fps80_prev.txt"); } }

        // game present, supported exe, the table exists and no wanted patch owns the same bytes (interp -> "n/a"; unknown bytes are rebuilt from the original, BytePatchState)
        public bool Fps80Avail { get { return HasGame && ExeSupported && GfxBytePatch(Fps80Id) != null && Fps80State() != "n/a"; } }
        public string Fps80State() { return BytePatchState(Fps80Id); }   // "on" / "off" / "mixed" / "n/a"

        public void SetFps80(bool on)
        {
            if (!HasGame) throw new InvalidOperationException(L.T("stNoGame")); if (GameRunning()) throw new InvalidOperationException(L.T("running"));
            string was = Fps80State();
            if (!on)
            {
                if (was == "n/a") { Log("fps80: nothing of ours in this exe, left alone"); return; }   // another build / interp: never touch it
                if (was != "off") SetBytePatch(Fps80Id, false);
                if (was != "off" || File.Exists(Fps80File)) Fps80Restore();
                Sync(); Log(L.T("reverted") + "fps mod (tick 80)"); return;
            }
            if (!HasGame || !ExeSupported || !Fps80Avail) throw new InvalidOperationException(L.T("stBadExe"));
            bool first = !File.Exists(Fps80File);
            if (first) Fps80Save();   // the values as they are now, before anything is written
            try
            {
                if (!Cnc) SetCnc(true);   // frames are limited inside the wrapper: gr-draw is a must (dgVoodoo steps aside)
                for (int i = 0; i < Fps80Keys.Length; i++) CncSet(Fps80Keys[i], Fps80Wants[i]);
                string cd = P("config.div");
                if (File.Exists(cd)) { string t = File.ReadAllText(cd, Encoding.Default); string n = Regex.Replace(t, @"(?m)^smooth[ \t]+\d+", "smooth 1"); if (n != t) File.WriteAllText(cd, n, Encoding.Default); }
                SetBytePatch(Fps80Id, true);   // last: a failure above leaves the exe untouched
            }
            catch (Exception) { if (first) { try { Fps80Restore(); } catch (Exception) { } } throw; }
            Sync(); Log(L.T("applied") + "fps mod (tick 80)");
        }

        void Fps80Save()
        {
            List<string> l = new List<string>(); l.Add("cnc=" + (Cnc ? "1" : "0"));
            for (int i = 0; i < Fps80Keys.Length; i++) l.Add(Fps80Keys[i] + "=" + (Cnc ? CncGet(Fps80Keys[i], Fps80Defs[i]) : Fps80Defs[i]));
            string cd = P("config.div");
            if (File.Exists(cd)) { Match m = Regex.Match(File.ReadAllText(cd, Encoding.Default), @"(?m)^smooth[ \t]+(\d+)"); if (m.Success && m.Groups[1].Value != "1") l.Add("smooth=" + m.Groups[1].Value); }
            Directory.CreateDirectory(GameData); File.WriteAllLines(Fps80File, l.ToArray(), Encoding.UTF8);
        }

        // the values of the record (no record = the wrapper's defaults) go back into ddraw.ini (only when the wrapper is still there) and config.div; then the record goes
        void Fps80Restore()
        {
            Dictionary<string, string> r = new Dictionary<string, string>();
            try { if (File.Exists(Fps80File)) foreach (string s in File.ReadAllLines(Fps80File, Encoding.UTF8)) { int k = s.IndexOf('='); if (k > 0) r[s.Substring(0, k)] = s.Substring(k + 1).Trim(); } } catch (IOException) { }
            if (Cnc && File.Exists(P("ddraw.ini"))) for (int i = 0; i < Fps80Keys.Length; i++) { string v; CncSet(Fps80Keys[i], r.TryGetValue(Fps80Keys[i], out v) && v.Length > 0 ? v : Fps80Defs[i]); }
            string cd = P("config.div"), sm; if (r.TryGetValue("smooth", out sm) && File.Exists(cd)) { string t = File.ReadAllText(cd, Encoding.Default); string n = Regex.Replace(t, @"(?m)^smooth[ \t]+\d+", "smooth " + sm); if (n != t) File.WriteAllText(cd, n, Encoding.Default); }
            try { File.Delete(Fps80File); } catch (IOException) { }
        }
    }
}
