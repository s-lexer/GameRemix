/*
  Divine Divinity FX (cnc-ddraw fork "ddfx"): fire / magic glow, warm light with ambient darkening, grading, sharpen, vignette.
  All parameters are runtime uniforms (u_*) edited from the in-game menu (F10).
  v3 (07.11.2026, ddfx 1.2): glow and warm light come from the game's real light sources (u_ln / u_lp / u_lc, hooked in fx.c), not from
  pixel colour; scaled by night (u_night); everything off outside the world view (u_world). The v2 colour search is kept only as a debug
  fallback (no lights + color_mask).
  v2 (07.11.2026): glow and light come from a real bloom chain (fx.c fx_bloom): PRE extracts the emitters at 1/2 size, DOWN x4 and UP x4
  (dual-filter blur, 16-bit float) give a smooth wide blur; FRAGMENT composites it. v1 sampled 24 rotated taps per pixel in one pass,
  which showed as dots around candles and torches.
  One file, several programs: the C code prepends "#version 130" and one of VERTEX / FRAGMENT / QUADV / PRE / DOWN / UP; the offline test renderer does the same.
*/
#if defined(VERTEX)

#if __VERSION__ >= 130
#define COMPAT_VARYING out
#define COMPAT_ATTRIBUTE in
#else
#define COMPAT_VARYING varying
#define COMPAT_ATTRIBUTE attribute
#endif

COMPAT_ATTRIBUTE vec4 VertexCoord;
COMPAT_ATTRIBUTE vec4 COLOR;
COMPAT_ATTRIBUTE vec4 TexCoord;
COMPAT_VARYING vec4 COL0;
COMPAT_VARYING vec4 TEX0;
uniform mat4 MVPMatrix;

void main()
{
    gl_Position = MVPMatrix * VertexCoord;
    COL0 = COLOR;
    TEX0.xy = TexCoord.xy;
}

#elif defined(QUADV)
/* full-target quad for the bloom passes, no vertex buffer: draw 4 vertices as a triangle strip */
out vec2 vuv;
void main()
{
    vec2 p = vec2(float(gl_VertexID & 1), float(gl_VertexID >> 1));
    vuv = p;
    gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}

#else

#if __VERSION__ >= 130
#define COMPAT_VARYING in
#define COMPAT_TEXTURE texture
out vec4 FragColor;
#else
#define COMPAT_VARYING varying
#define FragColor gl_FragColor
#define COMPAT_TEXTURE texture2D
#endif

uniform float u_fx;
uniform float u_fire_on, u_fire_bloom, u_fire_v, u_fire_s, u_fire_radius, u_flicker;
uniform float u_light_on, u_light_str, u_light_radius, u_light_tone, u_light_sparse, u_ambient;
uniform float u_magic_on, u_magic_bloom, u_magic_v, u_magic_s, u_magic_green;
uniform float u_exposure, u_gamma, u_contrast, u_saturation, u_warmth, u_vignette, u_sharpen;
uniform float u_ui_height;
uniform float u_debug;
uniform float u_halo, u_light_shape, u_light_drop, u_day_level, u_spell_lights, u_color_mask, u_show_lights;
uniform vec2 InputSize;

/* real light sources of the game (fx.c light hooks, ddfx 1.2), game-frame pixels, y down */
#define FXL 64
uniform int u_ln;            /* lights this frame; 0 = none (or not hooked) */
uniform vec4 u_lp[FXL];      /* x, y of the light, radius (light.lib maxrad), height above the ground */
uniform vec4 u_lc[FXL];      /* rgb, a = intensity (0..2, the game's flicker) + 10 * kind: 0 lamp/fire, 1 world magic, 2 spell, 3 marker only (hero, gold, gems) */
uniform float u_night;       /* 0 day .. 1 night (game twilight T[7]; underground = 1) */
uniform float u_world;       /* 1 world frame, 0 menu / journal / map / loading: everything off */

int lkind(int i) { return int(u_lc[i].a / 10.0 + 0.01); }
float linten(int i) { return u_lc[i].a - 10.0 * float(lkind(i)); }
float lstrength() { return mix(u_day_level, 1.0, u_night); }
float glowOn(int k) { return k == 0 ? u_fire_on * u_fire_bloom : (k == 1 ? u_magic_on * u_magic_bloom : (k == 2 ? u_spell_lights * u_magic_bloom : 0.0)); }
float lightOn(int k) { return u_light_on * (k == 0 ? 1.0 : (k == 1 ? u_magic_on : (k == 2 ? u_spell_lights : 0.0))); }
vec3 lcolour(int i, int k)
{
    vec3 tint = mix(vec3(1.0, 0.62, 0.20), vec3(1.0, 0.36, 0.10), u_light_tone);
    return k == 0 ? mix(u_lc[i].rgb, tint, 0.5) : u_lc[i].rgb;   /* lamps: the game colour (often white "Default Light") pulled to warm */
}
/* size of the flame core on screen */
float coreR(int i) { return (4.0 + 8.0 * u_fire_radius) * sqrt(clamp(u_lp[i].z / 150.0, 0.3, 3.0)); }
/* ground distance from the pool centre in units of the light radius: circle, or the game's 3D metric seen in iso
   (a ground offset (x, y) on screen is dX = x + y, dZ = -2y in the renderer: (x+y)^2 + 4y^2, a tilted ellipse) */
float poolDist(vec2 p, int i)
{
    vec2 q = p - vec2(u_lp[i].x, u_lp[i].y + max(u_lp[i].w, 0.0) * u_light_drop);
    float dc = dot(q, q);
    float de = (q.x + q.y) * (q.x + q.y) + 4.0 * q.y * q.y;
    return sqrt(mix(dc, de, u_light_shape)) / max(u_lp[i].z * u_light_radius, 1.0);
}

/* the game's bottom panel only (centred, fixed size in game pixels: ~670 x ~103 at ui_height 0.115), not the whole bottom band:
   a full-width band left a visible edge across the screen when the picture is darkened (owner 07.11.2026) */
float uiZone(vec2 uv01)
{
    vec2 p = uv01 * InputSize;
    float ph = u_ui_height * 900.0;
    float inY = smoothstep(InputSize.y - ph - 6.0, InputSize.y - ph + 2.0, p.y);
    float inX = 1.0 - smoothstep(330.0, 342.0, abs(p.x - InputSize.x * 0.5));
    return inY * inX;
}

/* fire: orange (hue ~7..48 deg: red >= green, green well above blue, green/red <= ~0.8), saturated, bright;
   plus a hot yellow-white core. Yellow-green foliage (green >= red) and low-saturation gold/wood are rejected. */
float fireMask(vec3 c)
{
    float v = max(c.r, max(c.g, c.b));
    float mn = min(c.r, min(c.g, c.b));
    float s = (v - mn) / max(v, 0.001);
    float gr = (c.g - mn) / max(v - mn, 0.001);
    float orderok = step(c.g, c.r + 0.02) * step(c.b, c.g + 0.02);
    float hue = smoothstep(0.08, 0.20, gr) * (1.0 - smoothstep(0.76, 0.88, gr));
    float body = smoothstep(u_fire_v - 0.12, u_fire_v + 0.08, v) * smoothstep(u_fire_s - 0.07, u_fire_s + 0.07, s) * hue;
    float core = smoothstep(0.93, 0.99, v) * smoothstep(0.20, 0.40, s) * (1.0 - smoothstep(0.80, 0.95, gr)) * step(0.05, c.r - c.b);
    return orderok * max(body, core);
}

float magicMask(vec3 c)
{
    float v = max(c.r, max(c.g, c.b));
    float mn = min(c.r, min(c.g, c.b));
    float s = (v - mn) / max(v, 0.001);
    float bluedom = smoothstep(0.0, 0.08, c.b - max(c.r * 0.9, c.g * 0.95) + 0.02);
    float m = smoothstep(u_magic_v - 0.12, u_magic_v + 0.08, v) * smoothstep(u_magic_s - 0.10, u_magic_s + 0.08, s) * bluedom;
    float gdom = smoothstep(0.05, 0.20, c.g - max(c.r, c.b) * 1.15);
    m = max(m, u_magic_green * smoothstep(0.78, 0.92, v) * smoothstep(0.5, 0.7, s) * gdom);
    return m;
}

float luma(vec3 c) { return dot(c, vec3(0.299, 0.587, 0.114)); }

#if defined(PRE)
/* emitters at half size: each output texel = 2x2 game pixels, masked one by one (averaging first would dim a 1-pixel flame below the threshold).
   rgb = glow colour (fire + magic, already weighted by their strength), a = fire coverage (drives the warm light) */
uniform sampler2D Texture;
/* a real light has a clipped core: fire = yellow-white (red at the top, green > 0.78), magic = blue/green at the top with little saturation.
   Gold, hair, item highlights, health bars, butterflies, UI trim stop below it, so only pixels within 3 px of such a core emit (owner 07.11.2026:
   items, NPCs, trees, the inventory, the map lit up). Measured on raw game frames: lamps, candles, torches kept; panel icons, books, bars dropped. */
float fireSeed(vec3 c) { return step(0.96, c.r) * step(0.78, c.g) * step(0.08, c.r - c.b); }
float magicSeed(vec3 c) { float v = max(c.r, max(c.g, c.b)); return step(0.95, v) * step(c.r, max(c.g, c.b) - 0.05) * step(min(c.r, min(c.g, c.b)), v * 0.75); }
void main()
{
    ivec2 p = ivec2(gl_FragCoord.xy) * 2;
    ivec2 lim = ivec2(InputSize) - 1;
    vec4 acc = vec4(0.0);
    if (u_world < 0.5) { FragColor = acc; return; }
    if (u_ln > 0)
    {
        /* light list: only bright pixels at a real light's core emit (lamp flame, candle, fireplace); everything else is dark */
        vec2 pc = vec2(p) + 1.0;
        vec3 wsum = vec3(0.0); float near = 0.0;
        for (int i = 0; i < FXL; i++)
        {
            if (i >= u_ln) break;
            int k = lkind(i); float g = glowOn(k) * linten(i);
            if (g <= 0.0) continue;
            float d = length(pc - u_lp[i].xy) / (coreR(i) * 2.0);
            float w = (1.0 - smoothstep(0.5, 1.0, d)) * g;
            if (w > near) { near = w; wsum = lcolour(i, k); }
        }
        if (near > 0.0)
            for (int j = 0; j < 2; j++)
                for (int i = 0; i < 2; i++)
                {
                    ivec2 q = min(p + ivec2(i, j), lim);
                    vec3 c = texelFetch(Texture, q, 0).rgb;
                    float em = 1.0 - uiZone((vec2(q) + 0.5) / InputSize);
                    float hot = smoothstep(u_fire_v - 0.15, u_fire_v + 0.15, max(c.r, max(c.g, c.b)));
                    acc.rgb += mix(c, wsum * luma(c), 0.35) * hot * near * em;
                    acc.a += hot * em;
                }
        FragColor = acc * 0.25 * lstrength();
        return;
    }
    if (u_color_mask < 0.5) { FragColor = acc; return; }
    /* debug fallback (no lights recorded and color_mask on): ddfx 1.1 colour search */
    float fs = 0.0, ms = 0.0;
    for (int j = -3; j <= 4; j++)
        for (int i = -3; i <= 4; i++)
        {
            vec3 c = texelFetch(Texture, clamp(p + ivec2(i, j), ivec2(0), lim), 0).rgb;
            fs = max(fs, fireSeed(c)); ms = max(ms, magicSeed(c));
        }
    for (int j = 0; j < 2; j++)
        for (int i = 0; i < 2; i++)
        {
            ivec2 q = min(p + ivec2(i, j), lim);
            vec3 c = texelFetch(Texture, q, 0).rgb;
            float em = 1.0 - uiZone((vec2(q) + 0.5) / InputSize);
            /* only near-white-hot pixels emit: a flame tops out at full brightness, blond hair or gold at ~0.8-0.9 lit up like a lamp */
            float hot = smoothstep(0.82, 0.97, max(c.r, max(c.g, c.b)));
            float f = fireMask(c) * hot * fs, m = magicMask(c) * ms;
            vec3 fc = mix(c, vec3(1.0, 0.55, 0.20) * luma(c), 0.4);
            vec3 mc = mix(c, vec3(0.45, 0.65, 1.0) * luma(c), 0.3);
            acc.rgb += (fc * f * u_fire_bloom * u_fire_on + mc * m * u_magic_bloom * u_magic_on) * em;
            acc.a += f * em;
        }
    FragColor = acc * 0.25;
}

#elif defined(LUMA)
/* mean brightness of the world area (1x1 target, once a frame): ambient darkening is for dark places (dungeons, rooms), not for daylight */
uniform sampler2D Texture;
void main()
{
    float acc = 0.0;
    for (int j = 0; j < 18; j++)
        for (int i = 0; i < 32; i++)
        {
            vec2 uv = (vec2(float(i), float(j)) + 0.5) / vec2(32.0, 18.0) * vec2(1.0, 0.86);
            acc += luma(texelFetch(Texture, ivec2(uv * InputSize), 0).rgb);
        }
    FragColor = vec4(acc / 576.0);
}

#elif defined(DOWN)
/* dual-filter downsample: centre x4 + 4 diagonal neighbours */
uniform sampler2D Src;
uniform vec2 SrcTexel;
in vec2 vuv;
void main()
{
    vec2 h = SrcTexel;
    vec4 s = COMPAT_TEXTURE(Src, vuv) * 4.0;
    s += COMPAT_TEXTURE(Src, vuv + vec2(-h.x, -h.y));
    s += COMPAT_TEXTURE(Src, vuv + vec2(h.x, -h.y));
    s += COMPAT_TEXTURE(Src, vuv + vec2(-h.x, h.y));
    s += COMPAT_TEXTURE(Src, vuv + vec2(h.x, h.y));
    FragColor = s / 8.0;
}

#elif defined(UP)
/* dual-filter upsample (tent of 8 taps) of the smaller level, blended into this level's downsample: Scatter 0 = only this level (tight), 1 = only the wide one */
uniform sampler2D Src;     /* the smaller level, already upsampled */
uniform sampler2D Cur;     /* this level's downsample */
uniform vec2 SrcTexel;
uniform float Scatter;
in vec2 vuv;
void main()
{
    vec2 h = SrcTexel * 0.5;
    vec4 s = COMPAT_TEXTURE(Src, vuv + vec2(-h.x * 2.0, 0.0));
    s += COMPAT_TEXTURE(Src, vuv + vec2(-h.x, h.y)) * 2.0;
    s += COMPAT_TEXTURE(Src, vuv + vec2(0.0, h.y * 2.0));
    s += COMPAT_TEXTURE(Src, vuv + vec2(h.x, h.y)) * 2.0;
    s += COMPAT_TEXTURE(Src, vuv + vec2(h.x * 2.0, 0.0));
    s += COMPAT_TEXTURE(Src, vuv + vec2(h.x, -h.y)) * 2.0;
    s += COMPAT_TEXTURE(Src, vuv + vec2(0.0, -h.y * 2.0));
    s += COMPAT_TEXTURE(Src, vuv + vec2(-h.x, -h.y)) * 2.0;
    FragColor = mix(COMPAT_TEXTURE(Cur, vuv), s / 12.0, Scatter);
}

#elif defined(FRAGMENT)

uniform int FrameCount;
uniform vec2 OutputSize;
uniform vec2 TextureSize;
uniform sampler2D Texture;
uniform sampler2D u_glow;    /* bloom chain, level 0 after the up passes (1/2 size) */
uniform sampler2D u_light;   /* bloom chain, a wide level (1/8 size) */
uniform sampler2D u_light2;  /* bloom chain, the widest level used (1/16 size) */
uniform sampler2D u_scene;  /* 1x1: mean brightness of the frame (LUMA pass) */
uniform float u_bloom_ok;    /* 0 = the chain could not be made (no float FBO): glow and light are off */
uniform float u_time;        /* seconds, wraps every ~17 min */
uniform float u_filter;      /* the scaling filter the player chose (from ddraw.ini shader=): 0 catmull-rom, 1 nearest, 2 bilinear, 3 lanczos2 */
COMPAT_VARYING vec4 TEX0;

vec3 catmull(vec2 uv)
{
    vec2 sp = uv * TextureSize;
    vec2 t1 = floor(sp - 0.5) + 0.5;
    vec2 f = sp - t1;
    vec2 w0 = f * (-0.5 + f * (1.0 - 0.5 * f));
    vec2 w1 = 1.0 + f * f * (-2.5 + 1.5 * f);
    vec2 w2 = f * (0.5 + f * (2.0 - 1.5 * f));
    vec2 w3 = f * f * (-0.5 + 0.5 * f);
    vec2 w12 = w1 + w2;
    vec2 o12 = w2 / w12;
    vec2 inv = 1.0 / TextureSize;
    vec2 t0 = (t1 - 1.0) * inv;
    vec2 t3 = (t1 + 2.0) * inv;
    vec2 t12 = (t1 + o12) * inv;
    float a = w12.x * w0.y, b = w0.x * w12.y, c = w12.x * w12.y, d = w3.x * w12.y, e = w12.x * w3.y;
    vec3 r = COMPAT_TEXTURE(Texture, vec2(t12.x, t0.y)).rgb * a;
    r += COMPAT_TEXTURE(Texture, vec2(t0.x, t12.y)).rgb * b;
    r += COMPAT_TEXTURE(Texture, t12).rgb * c;
    r += COMPAT_TEXTURE(Texture, vec2(t3.x, t12.y)).rgb * d;
    r += COMPAT_TEXTURE(Texture, vec2(t12.x, t3.y)).rgb * e;
    return max(r / (a + b + c + d + e), 0.0);
}

float lanczosW(float x)
{
    x = abs(x);
    if (x < 0.0001) return 1.0;
    if (x >= 2.0) return 0.0;
    return 2.0 * sin(3.14159265 * x) * sin(1.57079633 * x) / (9.8696044 * x * x);
}
vec3 lanczos(vec2 uv)
{
    vec2 sp = uv * TextureSize;
    vec2 t = floor(sp - 0.5) + 0.5;
    vec2 f = sp - t;
    vec3 acc = vec3(0.0); float ws = 0.0;
    for (int j = -1; j <= 2; j++)
        for (int i = -1; i <= 2; i++)
        {
            vec2 d = vec2(float(i), float(j)) - f;
            float w = lanczosW(d.x) * lanczosW(d.y);
            acc += w * COMPAT_TEXTURE(Texture, (t + vec2(float(i), float(j))) / TextureSize).rgb; ws += w;
        }
    return max(acc / ws, 0.0);
}
vec3 scaled(vec2 uv)
{
    if (u_filter > 2.5) return lanczos(uv);
    if (u_filter > 1.5) return COMPAT_TEXTURE(Texture, uv).rgb;
    if (u_filter > 0.5) return COMPAT_TEXTURE(Texture, (floor(uv * TextureSize) + 0.5) / TextureSize).rgb;
    return catmull(uv);
}

void main()
{
    vec2 uv = TEX0.xy;
    vec2 inv = 1.0 / TextureSize;
    vec2 uv01 = uv * TextureSize / InputSize;

    vec3 base = scaled(uv);
    if (u_fx < 0.5 || u_world < 0.5)   /* menus, journal, map, loading: the plain picture */
    {
        FragColor = vec4(base, 1.0);
        return;
    }

    vec3 col = base;
    float ui = uiZone(uv01);
    float notui = 1.0 - ui;
    vec2 pp = uv01 * InputSize;

    if (u_sharpen > 0.001)
    {
        vec3 lap = 4.0 * base - catmull(uv + vec2(inv.x, 0.0)) - catmull(uv - vec2(inv.x, 0.0)) - catmull(uv + vec2(0.0, inv.y)) - catmull(uv - vec2(0.0, inv.y));
        col += lap * (-u_sharpen * 0.5) * notui;
    }

    /* slow smooth flicker: two drifting waves in screen space (no cells, no hard edges), time-based so it does not depend on the frame rate */
    float fl = 1.0;
    if (u_flicker > 0.0)
    {
        float t = u_time;
        float n = 0.6 * sin(t * 7.3 + pp.x * 0.013 + pp.y * 0.009) + 0.4 * sin(t * 12.1 - pp.x * 0.021 + pp.y * 0.017);
        fl = 1.0 + u_flicker * n;
    }

    vec4 gl0 = COMPAT_TEXTURE(u_glow, uv01) * u_bloom_ok;
    float lightPool;
    if (u_ln > 0)
    {
        /* real lights: halo at each light core + bloom of its flame pixels (PRE), warm radial pool on the ground around it */
        float ls = lstrength();
        vec3 halo = vec3(0.0), pool = vec3(0.0); float poolA = 0.0;
        for (int i = 0; i < FXL; i++)
        {
            if (i >= u_ln) break;
            int k = lkind(i); float it = linten(i); vec3 c = lcolour(i, k);
            float g = glowOn(k) * it;
            if (g > 0.0)
            {
                float d = length(pp - u_lp[i].xy) / coreR(i);
                halo += c * g * (0.55 * exp(-0.5 * d * d) + 0.12 * exp(-0.6 * d));
            }
            float lo = lightOn(k) * it;
            if (lo > 0.0)
            {
                float f = poolDist(pp, i);
                float a = clamp(1.0 - f * f, 0.0, 1.0); a *= a;
                pool += c * lo * a; poolA += lo * a;
            }
        }
        vec3 glow = ((1.0 - exp(-gl0.rgb * 4.0)) + halo * u_halo * ls) * fl * notui;
        col = 1.0 - (1.0 - col) * (1.0 - clamp(glow, 0.0, 1.0));
        vec3 pl = pool * u_light_str * ls * fl * notui;
        col *= 1.0 + pl * (1.6 - luma(base));
        col += pl * 0.03;
        lightPool = clamp(poolA, 0.0, 1.0);
    }
    else
    {
        /* no list (or colour search for debugging): ddfx 1.1 */
        vec4 lw = mix(COMPAT_TEXTURE(u_light, uv01), COMPAT_TEXTURE(u_light2, uv01), clamp((u_light_radius - 0.3) / 1.7, 0.0, 1.0)) * u_bloom_ok;
        float selfm = max(fireMask(base), magicMask(base));
        vec3 glow = (1.0 - exp(-gl0.rgb * 4.0)) * mix(1.0, fl, u_fire_on) * (1.0 - 0.6 * selfm) * notui;
        col = 1.0 - (1.0 - col) * (1.0 - clamp(glow, 0.0, 1.0));
        float cov = lw.a * u_color_mask;
        float gate = mix(1.0, 1.0 - smoothstep(0.05, 0.20, cov), u_light_sparse);
        lightPool = (1.0 - exp(-cov * 160.0)) * gate;
        vec3 tint = mix(vec3(1.0, 0.62, 0.20), vec3(1.0, 0.36, 0.10), u_light_tone);
        float pool = lightPool * u_light_str * fl * notui * u_light_on;
        col *= 1.0 + tint * pool * (1.6 - luma(base));
        col += tint * pool * 0.03;
    }
    /* ambient: at night (and underground) the world away from the lights gets darker, so the light pools read as light; daylight is left as it is */
    col *= 1.0 - u_ambient * u_night * (1.0 - clamp(lightPool * 1.5, 0.0, 1.0)) * notui;

    /* picture grading, off in the interface band */
    vec3 g = col;
    g *= exp2(u_exposure);
    if (abs(u_warmth) > 0.001) g *= vec3(1.0 + 0.12 * u_warmth, 1.0, 1.0 - 0.12 * u_warmth);
    float l2 = luma(g);
    g = mix(vec3(l2), g, u_saturation);
    if (abs(u_contrast) > 0.001)
    {
        float sc = l2 * l2 * (3.0 - 2.0 * l2);
        g *= mix(1.0, (sc + 0.001) / (l2 + 0.001), u_contrast);
    }
    g = pow(max(g, 0.0), vec3(1.0 / max(u_gamma, 0.1)));
    vec2 d = (uv01 - 0.5) * vec2(1.0, 0.85);
    g *= 1.0 - u_vignette * smoothstep(0.35, 0.85, length(d));
    col = mix(g, col, ui);

    if (u_debug > 0.5)
    {
        float m1 = u_debug < 1.5 ? fireMask(base) : (u_debug < 2.5 ? magicMask(base) : lightPool);
        col = mix(base * 0.35, vec3(m1), 0.65) + vec3(m1 * 0.3, 0.0, 0.0);
    }

    /* markers: a ring + cross at every recorded light, a thin ring at the pool edge; yellow lamp, cyan world magic, magenta spell, grey hero / gold / gems */
    if (u_show_lights > 0.5)
    {
        for (int i = 0; i < FXL; i++)
        {
            if (i >= u_ln) break;
            int k = lkind(i);
            vec3 mc = k == 0 ? vec3(1.0, 0.9, 0.1) : (k == 1 ? vec3(0.2, 0.9, 1.0) : (k == 2 ? vec3(1.0, 0.3, 1.0) : vec3(0.6)));
            vec2 q = pp - u_lp[i].xy; float d = length(q);
            float m = (1.0 - smoothstep(0.6, 1.4, abs(d - 6.0)));
            m = max(m, (1.0 - smoothstep(0.4, 1.0, min(abs(q.x), abs(q.y)))) * step(d, 12.0) * step(2.5, d));
            float e = poolDist(pp, i);
            m = max(m, 0.6 * (1.0 - smoothstep(0.0, 1.2 / max(u_lp[i].z * u_light_radius, 1.0), abs(e - 1.0))));
            col = mix(col, mc, m);
        }
    }

    FragColor = vec4(clamp(col, 0.0, 1.0), 1.0);
}
#endif
#endif
