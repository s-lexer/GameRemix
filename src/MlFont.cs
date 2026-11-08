// Reader for the game's ML_FONT_01 (.fnt) files: just enough to draw real text for the font preview. Format notes: games/divine-divinity/analysis/mlfont.py
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Text;

namespace DDFixTool
{
    class MlGlyph { public int A, W, H; public List<KeyValuePair<int, ushort[]>>[] Rows; }

    class MlFont
    {
        public Dictionary<int, MlGlyph> Glyphs = new Dictionary<int, MlGlyph>();
        static ushort U16(byte[] d, int p) { return (ushort)(d[p] | (d[p + 1] << 8)); }
        static int U32(byte[] d, int p) { return d[p] | (d[p + 1] << 8) | (d[p + 2] << 16) | (d[p + 3] << 24); }

        public static MlFont Parse(byte[] d)
        {
            MlFont f = new MlFont(); int s = 0x9a + 223 * 4;
            try
            {
                while (s + 34 <= d.Length)
                {
                    int A = U32(d, s + 16), code = U16(d, s + 20), B = U32(d, s + 22), C = U32(d, s + 26), w = U16(d, s + 30), h = U16(d, s + 32);
                    int nxt = s + B + 23, p = s + 34, pix = s + 22 + C; if (B <= 0 || nxt <= s) break;
                    if (w < 0 || w > 256 || h < 0 || h > 128 || A < 0 || A > 256) { s = nxt; continue; }   // a damaged record: skipped, it must not allocate absurd sizes
                    MlGlyph g = new MlGlyph(); g.A = A; g.W = w; g.H = h; g.Rows = new List<KeyValuePair<int, ushort[]>>[h];
                    for (int y = 0; y < h; y++) g.Rows[y] = new List<KeyValuePair<int, ushort[]>>();
                    bool allZero = pix - p == 8 * h; if (allZero) for (int i = p; i < pix; i++) if (d[i] != 0) { allZero = false; break; }
                    if (!allZero)
                    {
                        int prev = 0; bool skipped = false; List<int[]> rows = new List<int[]>();   // per row: start,count pairs flattened + byte offset
                        for (int y = 0; y < h; y++)
                        {
                            if (!skipped && prev == 0 && p + 6 <= pix && U16(d, p) != 0 && U16(d, p + 2) == 0 && U16(d, p + 4) == 0) { p += 6; skipped = true; }
                            if (y == h - 1)
                            {
                                int n = ((pix - p) / 2 - 1) / 2; int[] pre = new int[Math.Max(0, 2 * n)];
                                for (int i = 0; i < pre.Length; i++) pre[i] = U16(d, p + 2 * i);
                                rows.Add(Pack(pre, prev)); break;
                            }
                            int[] fnd = null; int np = 0;
                            for (int n = 0; n < 8 && fnd == null; n++)
                            {
                                if (p + 4 * n + 8 > d.Length) break;
                                int[] pre = new int[2 * n]; for (int i = 0; i < 2 * n; i++) pre[i] = U16(d, p + 2 * i);
                                int nn = U16(d, p + 4 * n), off = U16(d, p + 4 * n + 4) + (U16(d, p + 4 * n + 6) << 16), cnt = 0;
                                if (n > 0) { cnt = pre[1]; for (int i = 3; i < 2 * n; i += 2) cnt += pre[i]; }
                                if (nn == n && off - prev == 2 * cnt) { fnd = Pack(pre, prev); np = p + 4 * n + 8; prev = off; }
                            }
                            if (fnd == null) break; rows.Add(fnd); p = np;
                        }
                        for (int y = 0; y < rows.Count && y < h; y++)
                        {
                            int[] r = rows[y]; int q = pix + r[r.Length - 1]; int k = (r.Length - 1) / 2; if (k == 0) continue; int x0 = r[0];
                            for (int i = 0; i < k; i++)
                            {
                                int c = i == 0 ? r[1] : r[2 * i + 1], st = i == 0 ? x0 : x0 + r[2 * i]; ushort[] cols = new ushort[c];
                                for (int j = 0; j < c && q + 2 <= d.Length; j++, q += 2) cols[j] = U16(d, q);
                                g.Rows[y].Add(new KeyValuePair<int, ushort[]>(st, cols));
                            }
                        }
                    }
                    f.Glyphs[code] = g; s = nxt;
                }
            }
            catch { }
            return f;
        }
        static int[] Pack(int[] pre, int off) { int[] r = new int[pre.Length + 1]; Array.Copy(pre, r, pre.Length); r[pre.Length] = off - 0; return r; }

        // text on a transparent bitmap (cp1251 codes, like the game)
        // returns null when the text cannot be drawn (damaged or absurd glyph sizes)
        public Bitmap Render(string text)
        {
            try
            {
                byte[] b = Encoding.GetEncoding(1251).GetBytes(text); int w = 2, h = 1;
                foreach (byte c in b) { MlGlyph g; if (Glyphs.TryGetValue(c, out g)) { w += g.A; h = Math.Max(h, g.H); } else w += 6; }
                if (w > 4096 || h > 128 || w < 1) return null;
                Bitmap bmp = new Bitmap(w + 2, h, System.Drawing.Imaging.PixelFormat.Format32bppArgb); int x = 2;
                foreach (byte c in b)
                {
                    MlGlyph g; if (!Glyphs.TryGetValue(c, out g)) { x += 6; continue; }
                    for (int y = 0; y < g.H && y < h; y++) foreach (KeyValuePair<int, ushort[]> run in g.Rows[y])
                        for (int j = 0; j < run.Value.Length; j++)
                        {
                            int px = x + run.Key + j; if (px < 0 || px >= bmp.Width) continue; int v = run.Value[j];
                            bmp.SetPixel(px, y, Color.FromArgb(255, (v >> 11 & 31) * 255 / 31, (v >> 5 & 63) * 255 / 63, (v & 31) * 255 / 31));
                        }
                    x += g.A;
                }
                return bmp;
            }
            catch (Exception) { return null; }
        }
    }
}
