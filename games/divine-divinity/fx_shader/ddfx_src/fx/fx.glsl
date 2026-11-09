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
uniform float u_vibrance, u_clarity, u_cinema_tone, u_shadow_lift;
uniform float u_ui_height;
uniform float u_source_flicker, u_spell_pulse, u_heat_haze, u_atmo_tint, u_light_mist;
uniform float u_magic_trails, u_magic_echo, u_magic_splash;
uniform float u_time;       /* seconds; shared with PRE to keep each lamp in phase */
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
/* Flicker and spell pulse are computed ONCE per light per frame on the CPU,
   encoded into u_lc.a intensity. Avoid costly trig in each pixel/each source. */
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

/* The game's UI occupies a bottom-centred ~670 x 103px panel. Do not use a hard
   8px fade on its top edge: ambient/vignette grading then creates a bright horizontal
   strip above the panel (owner screenshots 08.11.2026). Fade in over ~48px of WORLD
   instead, reaching full protection by the panel's own border; also feather X edges. */
float uiZone(vec2 uv01)
{
    vec2 p = uv01 * InputSize;
    float ph = u_ui_height * 900.0;
    float panelTop = InputSize.y - ph;
    float inY = smoothstep(panelTop - 48.0, panelTop, p.y);
    float inX = 1.0 - smoothstep(340.0, 390.0, abs(p.x - InputSize.x * 0.5));
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
        vec3 wsum = vec3(0.0); float near = 0.0; int sourceKind = 3;
        for (int i = 0; i < FXL; i++)
        {
            if (i >= u_ln) break;
            int k = lkind(i); float g = glowOn(k) * linten(i);
            if (g <= 0.0) continue;
            /* light.lib often locates a streetlamp at its base/pivot, not at either flame sprite.
               Search above the pivot, but only a narrow distance below it: do not bloom the illuminated pole/ground. */
            vec2 delta = pc - u_lp[i].xy;
            float rx = max(coreR(i) * 2.0, min(u_lp[i].z * 0.50, 75.0));
            float ry = delta.y < 0.0 ? max(coreR(i) * 2.0, min(u_lp[i].z * 0.90, 135.0)) : coreR(i) * 1.4;
            float d = length(vec2(delta.x / rx, delta.y / ry));
            /* The library anchor is often at the foot of a standing prop. An emissive ornament
               right at the anchor must not bloom like a flame; allow the flame pixels above it. */
            float abovePivot = 1.0 - smoothstep(-10.0, -1.0, delta.y);
            float w = (1.0 - smoothstep(0.65, 1.0, d)) * g * abovePivot;
            if (w > near) { near = w; wsum = lcolour(i, k); sourceKind = k; }
        }
        if (near > 0.0)
        {
            /* Bloom only compact flame cores. The ornament at the foot of the post is a broad
               hot-colour region; the two real flames are compact (219 pixel-mask measurements).
               Two 8-point circles distinguish those shapes without fixed map/sprite offsets. */
            float dense = 0.0;
            for (int ring = 0; ring < 2; ring++)
                for (int k = 0; k < 8; k++)
                {
                    float a = float(k) * 0.78539816339;
                    float radius = ring == 0 ? 10.0 : 16.0;
                    ivec2 q = clamp(ivec2(pc + vec2(cos(a), sin(a)) * radius), ivec2(0), lim);
                    vec3 dc = texelFetch(Texture, q, 0).rgb;
                    dense += smoothstep(0.30, 0.60, fireMask(dc)) * smoothstep(0.50, 0.85, max(dc.r, max(dc.g, dc.b)));
                }
            float isolated = 1.0 - smoothstep(0.8, 1.8, dense);
            for (int j = 0; j < 2; j++)
                for (int i = 0; i < 2; i++)
                {
                    ivec2 q = min(p + ivec2(i, j), lim);
                    vec3 c = texelFetch(Texture, q, 0).rgb;
                    float em = 1.0 - uiZone((vec2(q) + 0.5) / InputSize);
                    /* A light record alone is not evidence that every bright roof/pole pixel is a flame.
                       Require a fire/magic chroma signature for the emitted bloom. */
                    float emitter = sourceKind == 0 ? max(fireMask(c), fireSeed(c))
                                  : max(max(fireMask(c), fireSeed(c)), max(magicMask(c), magicSeed(c)));
                    float hot = isolated * emitter * smoothstep(u_fire_v - 0.15, u_fire_v + 0.15, max(c.r, max(c.g, c.b)));
                    acc.rgb += mix(c, wsum * luma(c), 0.35) * hot * near * em;
                    acc.a += hot * em;
                }
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
uniform sampler2D u_emitter; /* RAW PRE bloom mask, half-resolution, before blur: debug anchors follow actual flames */
uniform sampler2D u_light;   /* bloom chain, a wide level (1/8 size) */
uniform sampler2D u_light2;  /* bloom chain, the widest level used (1/16 size) */
uniform sampler2D u_scene;  /* 1x1: mean brightness of the frame (LUMA pass) */
/* CPU-tracked short-lived magic motion segments and vanishing glows (not fake impacts).
   The location and colour originate from real kind=2 game light records. */
#define FX_WOW_MAX 12
uniform int u_nt, u_ne;
uniform vec4 u_ta[FX_WOW_MAX]; /* x0,y0 -> x1,y1 */
uniform vec4 u_tc[FX_WOW_MAX]; /* rgb, intensity */
uniform vec4 u_ea[FX_WOW_MAX]; /* x,y, radius, elapsed fraction */
uniform vec4 u_ec[FX_WOW_MAX]; /* rgb, intensity */
uniform float u_bloom_ok;    /* 0 = the chain could not be made (no float FBO): glow and light are off */
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

    /* Local hot-air refraction 8-28px ABOVE real flame cores in the RAW PRE mask.
       Only a few pixels, no fullscreen displacement, and never on HUD/menus. */
    if (u_heat_haze > 0.001 && u_fire_on > 0.5 && u_bloom_ok > 0.5 && notui > 0.05)
    {
        float hot1 = COMPAT_TEXTURE(u_emitter, clamp(uv01 + vec2(0.0, 12.0) / InputSize, vec2(0.0), vec2(1.0))).a;
        float hot2 = COMPAT_TEXTURE(u_emitter, clamp(uv01 + vec2(0.0, 23.0) / InputSize, vec2(0.0), vec2(1.0))).a;
        float plume = clamp(max(hot1, hot2 * 0.65) * 4.0, 0.0, 1.0);
        if (plume > 0.01)
        {
            float wave = sin(pp.y * 0.27 + u_time * 5.0 + pp.x * 0.07);
            vec2 displaced = clamp(uv + vec2(wave * 1.7 * u_heat_haze * plume / TextureSize.x, 0.0), vec2(0.0), vec2(1.0));
            col = base = mix(base, scaled(displaced), u_heat_haze * plume * notui);
        }
    }

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
        /* Bloom follows actual flame pixels from PRE, never a synthetic point at light.lib's
           object pivot (a streetlamp pivot may be a full post-height below its two flames).
           The light record still controls the separate, gentler environmental light pool. */
        float ls = lstrength();
        vec3 pool = vec3(0.0); float poolA = 0.0;
        for (int i = 0; i < FXL; i++)
        {
            if (i >= u_ln) break;
            int k = lkind(i); float it = linten(i); vec3 c = lcolour(i, k);
            float lo = lightOn(k) * it;
            if (lo > 0.0)
            {
                float f = poolDist(pp, i);
                float a = clamp(1.0 - f * f, 0.0, 1.0); a *= a;
                pool += c * lo * a; poolA += lo * a;
            }
        }
        /* PRE emission is only a few pixels wide; stronger bloom is needed to make the
           flame halo visibly distinct even with ambient=0 (without darkening the scene).
           Still constrained to genuine emitters, not arbitrary bright textures. */
        vec3 glow = (1.0 - exp(-gl0.rgb * (7.0 + 4.0 * u_halo))) * fl * notui;
        col = 1.0 - (1.0 - col) * (1.0 - clamp(glow, 0.0, 1.0));
        /* Two lamps on one post (or nearby lamps) should add light, not blow a roof out to white.
           Saturate overlapping contributions; reduce added light on surfaces that are already bright. */
        vec3 boundedPool = 1.0 - exp(-max(pool, vec3(0.0)));
        float alreadyLit = smoothstep(0.35, 0.90, luma(base));
        vec3 pl = boundedPool * u_light_str * ls * fl * notui * (1.0 - 0.65 * alreadyLit);
        /* A bright existing flame / decorative highlight is not a diffuse receiving surface.
           Without this guard the shader amplifies the game's pre-lit ornament at the lamp pivot. */
        float basePeak = max(base.r, max(base.g, base.b));
        pl *= 1.0 - smoothstep(0.72, 0.95, basePeak);
        /* Reflective textures keep their detail and headroom: additive/multiplicative light alone clips bright roofs. */
        /* Raise DARK receiving surfaces locally; avoid whitening already-lit stone or wood.
           Unlike global exposure/ambient this term is zero outside the light radius. */
        col += (vec3(0.20) + col * 0.30) * (1.0 - clamp(col, 0.0, 1.0)) * pl;
        lightPool = 1.0 - exp(-max(poolA, 0.0));
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
    /* WOW magic: short streaks only on motion of actual dynamic kind=2 lights. No screen
       history texture and no trails for static lamps. Max 12 segments; branch entirely off
       for approved configs, and bound each segment with a cheap screen-space AABB. */
    if (u_magic_trails > 0.001 && u_nt > 0 && notui > 0.001)
    {
        vec3 streak = vec3(0.0);
        for (int i=0; i<FX_WOW_MAX; i++)
        {
            if (i>=u_nt) break;
            vec2 a=u_ta[i].xy, b=u_ta[i].zw;
            float pad=13.0;
            if (pp.x<min(a.x,b.x)-pad || pp.x>max(a.x,b.x)+pad ||
                pp.y<min(a.y,b.y)-pad || pp.y>max(a.y,b.y)+pad) continue;
            vec2 ab=b-a;
            float progress=clamp(dot(pp-a,ab)/max(dot(ab,ab),1.0),0.0,1.0);
            float distance=length(pp-(a+ab*progress));
            float core=exp(-0.5*pow(distance/2.7,2.0));
            float halo=exp(-0.5*pow(distance/8.5,2.0));
            float tail=0.25+0.75*progress;
            streak+=u_tc[i].rgb*(core*0.48+halo*0.10)*u_tc[i].a*tail;
        }
        col+=streak*u_magic_trails*(1.0-clamp(col,0.0,1.0))*notui;
    }
    /* Source disappearance is only a heuristic: a fading ring, NOT a confirmed hit.
       Single short pulse (about 0.3s), no explosion if scene/menu switches. */
    if (u_magic_echo > 0.001 && u_ne > 0 && notui > 0.001)
    {
        vec3 flashes=vec3(0.0);
        for (int i=0; i<FX_WOW_MAX; i++)
        {
            if (i>=u_ne) break;
            float age=clamp(u_ea[i].w,0.0,1.0), d=length(pp-u_ea[i].xy);
            float radius=7.0+30.0*age;
            if (d>radius+18.0) continue;
            float ring=exp(-0.5*pow((d-radius)/max(2.5,4.0+age*3.0),2.0));
            float soft=exp(-0.5*pow(d/(11.0+age*12.0),2.0));
            flashes+=u_ec[i].rgb*u_ec[i].a*(1.0-age)*(ring*0.45+soft*0.13);
        }
        col+=flashes*u_magic_echo*(1.0-clamp(col,0.0,1.0))*notui;
    }
    /* Local coloured diffuse light, tied to real active kind=2 records only.
       No constant full-screen bloom and no light cast through unknown occluders. */
    if (u_magic_splash > 0.001 && u_ln > 0 && notui > 0.001)
    {
        vec3 splash=vec3(0.0);
        for (int i=0; i<FXL; i++)
        {
            if(i>=u_ln)break;
            if(lkind(i)!=2)continue;
            vec2 delta=pp-u_lp[i].xy;
            float radius=clamp(u_lp[i].z*0.43,25.0,72.0);
            if(abs(delta.x)>radius || abs(delta.y)>radius) continue;
            float d=length(delta)/radius;
            float cover=pow(max(1.0-d*d,0.0),2.0)*linten(i);
            splash+=u_lc[i].rgb*cover*0.28;
        }
        col+=splash*u_magic_splash*(1.0-clamp(col,0.0,1.0))*notui;
    }
    /* Optional faint airborne motes only where a REAL light pool exists, never a full-screen fog.
       Small moving warm variation, bounded by original local-light coverage. */
    if (u_light_mist > 0.001 && u_ln > 0 && lightPool > 0.06)
    {
        float drift = (0.5 + 0.5 * sin(pp.x * 0.028 + pp.y * 0.019 + u_time * 0.36)) *
                      (0.5 + 0.5 * sin(pp.y * 0.044 - u_time * 0.22));
        float local = smoothstep(0.06, 0.52, lightPool) * (1.0 - smoothstep(0.45, 0.87, luma(base)));
        col += vec3(0.055, 0.040, 0.021) * u_light_mist * local * drift * notui;
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
    /* Optional temperature shift, not an ambient darkening pass. Original colour is the
       neutral reference. Never tint the status panel or unrendered world screens. */
    if (u_atmo_tint > 0.001)
    {
        vec3 nightTone = vec3(0.977, 0.993, 1.028);
        vec3 dayTone = vec3(1.020, 1.006, 0.988);
        vec3 tint = mix(dayTone, nightTone, u_night);
        col = mix(col, col * tint, clamp(u_atmo_tint * notui, 0.0, 1.0));
    }

    /* Adaptive colour affects the scene even without registered lights.
       Reduce amplification for already saturated pixels and keep game HUD intact. */
    if (u_vibrance > 0.001)
    {
        float mid = luma(col);
        float sat = max(col.r,max(col.g,col.b))-min(col.r,min(col.g,col.b));
        float headroom = 1.0-smoothstep(0.25,0.82,sat);
        vec3 vivid = mix(vec3(mid),col,1.0+u_vibrance*headroom*0.75);
        col = mix(col, clamp(vivid,0.0,1.0),notui);
    }
    /* Brighter shadow detail without lowering exposure elsewhere. */
    if (u_shadow_lift > 0.001)
    {
        float low = 1.0-smoothstep(0.12,0.70,luma(col));
        col += vec3(0.16,0.17,0.18)*low*u_shadow_lift*(1.0-clamp(col,0.0,1.0))*notui;
    }
    /* Cinematic split-tone: cool dark stone, warm light; protected UI. */
    if (u_cinema_tone > 0.001)
    {
        float lum = luma(col);
        float dark = 1.0-smoothstep(0.14,0.56,lum);
        float bright = smoothstep(0.42,0.88,lum);
        vec3 shift = vec3(-0.072,0.012,0.13)*dark+vec3(0.07,0.025,-0.052)*bright;
        col = clamp(col+shift*u_cinema_tone*notui,0.0,1.0);
    }
    /* Texture clarity uses nearby source luminance; only strong edges and non-HUD pixels. */
    if (u_clarity > 0.001 && notui > 0.01)
    {
        vec2 px = 1.0/TextureSize;
        float north=luma(scaled(clamp(uv+vec2(0.0,-px.y),vec2(0.0),vec2(1.0))));
        float south=luma(scaled(clamp(uv+vec2(0.0,px.y),vec2(0.0),vec2(1.0))));
        float west=luma(scaled(clamp(uv+vec2(-px.x,0.0),vec2(0.0),vec2(1.0))));
        float east=luma(scaled(clamp(uv+vec2(px.x,0.0),vec2(0.0),vec2(1.0))));
        float edge=luma(base)-0.25*(north+south+west+east);
        float mask=smoothstep(0.018,0.095,abs(edge))*(1.0-smoothstep(0.52,0.94,luma(base)));
        col=clamp(col+vec3(edge*3.2*u_clarity*mask*notui),0.0,1.0);
    }

    if (u_debug > 0.5)
    {
        float m1 = u_debug < 1.5 ? fireMask(base) : (u_debug < 2.5 ? magicMask(base) : lightPool);
        col = mix(base * 0.35, vec3(m1), 0.65) + vec3(m1 * 0.3, 0.0, 0.0);
    }

    /* Debug: an amber contour surrounds the *actual emitter pixels* in PRE, not the
       game's object pivot. This naturally shows two separate flames for a twin-lamp post.
       Grey dots are light.lib pivots (ground-pool origins); muted outlines show pool extents.
       Keeping them visually distinct avoids mistaking the pivot for a flame centre. */
    if (u_show_lights > 0.5)
    {
        float emitterRim = 0.0;
        float clearPivotGlow = 1.0;
        if (u_bloom_ok > 0.5)
        {
            vec2 s = 1.0 / InputSize;
            float core = COMPAT_TEXTURE(u_emitter, uv01).a;
            float near4 = 0.0, near8 = 0.0;
            for (int k = 0; k < 8; k++)
            {
                float a = float(k) * 0.78539816339;
                vec2 dir = vec2(cos(a), sin(a));
                near4 = max(near4, COMPAT_TEXTURE(u_emitter, clamp(uv01 + dir * 4.0 * s, vec2(0.0), vec2(1.0))).a);
                near8 = max(near8, COMPAT_TEXTURE(u_emitter, clamp(uv01 + dir * 8.0 * s, vec2(0.0), vec2(1.0))).a);
            }
            float rim = smoothstep(0.025, 0.15, near8) * (1.0 - smoothstep(0.025, 0.15, max(core, near4)));
            /* Gold traces indicate visible flames; not a guessed fixed offset from the post. */
            emitterRim = clamp(rim * 0.9, 0.0, 1.0);
        }
        for (int i = 0; i < FXL; i++)
        {
            if (i >= u_ln) break;
            int k = lkind(i);
            vec3 mc = k == 0 ? vec3(0.45, 0.52, 0.60) : (k == 1 ? vec3(0.18, 0.55, 0.65) : (k == 2 ? vec3(0.50, 0.27, 0.55) : vec3(0.35)));
            vec2 q = pp - u_lp[i].xy;
            float d = length(q);
            /* Wide hot ornaments can leave a few bloom edge pixels right at the pivot.
               Show the root only as grey, not as a second invented flame. */
            if (k == 0) clearPivotGlow *= smoothstep(34.0, 58.0, d);
            /* Small grey plus: debug pivot; never a yellow fake flame. */
            float pivot = (1.0 - smoothstep(0.3, 1.1, min(abs(q.x), abs(q.y)))) * step(d, 5.0);
            float e = poolDist(pp, i);
            float edge = (1.0 - smoothstep(0.0, 1.2 / max(u_lp[i].z * u_light_radius, 1.0), abs(e - 1.0)));
            col = mix(col, mc, clamp(pivot * 0.8 + edge * 0.24, 0.0, 1.0));
        }
        col = mix(col, vec3(1.0, 0.95, 0.1), emitterRim * clearPivotGlow);
    }

    FragColor = vec4(clamp(col, 0.0, 1.0), 1.0);
}
#endif
#endif
