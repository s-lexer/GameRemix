#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "fx.h"
#include "fx_params.h"
#include "fx_glsl.h"
#include "fx_font.h"
#include "config.h"
#include "dd.h"
#include "hook.h"
#include "debug.h"

/* ---------- GL 1.x entry points not exported by opengl_utils ---------- */
typedef void (WINAPI *FX_PGLENABLE)(GLenum);
typedef void (WINAPI *FX_PGLBLENDFUNC)(GLenum, GLenum);
typedef void (WINAPI *FX_PGLDRAWARRAYS)(GLenum, GLint, GLsizei);
static FX_PGLENABLE fx_glEnable, fx_glDisable;
static FX_PGLBLENDFUNC fx_glBlendFunc;
static FX_PGLDRAWARRAYS fx_glDrawArrays;

static float g_v[FX_NP];             /* current values */
static float g_saved_start[FX_NP];  /* exact [current] snapshot on startup */
static BOOL g_quick_key_down[5];     /* Ctrl+Shift+1..5 edge detection */
static GLint g_loc[FX_NP]; static GLint g_loc_filter = -1; static float g_filter = 0.0f;   /* g_filter: the player's scaling filter, see u_filter in fx.glsl */
static GLuint g_prog = 0, g_ovl_prog = 0, g_ovl_vao = 0, g_ovl_tex = 0, g_hud_tex = 0;
static GLint g_ovl_rect_loc = -1;
static volatile LONG g_open = 0;
static int g_sel = 0, g_scroll = 0;
static BOOL g_dirty = TRUE, g_inited = FALSE;
static char g_toast[96]; static DWORD g_toast_until = 0;
static char g_cfg_path[MAX_PATH];
static int g_k_menu = VK_F10, g_k_fps = VK_F11, g_k_fx = VK_F9;   /* hotkeys: dd-fx.cfg [keys] menu= fps= fx= (virtual-key codes, decimal) */

/* rows: -1 header(section idx in aux), 0..FX_NP-1 param, 1000+ actions */
typedef struct { int type; int idx; } ROW;
static ROW g_rows[FX_NP + FX_NSEC + 8]; static int g_nrows = 0;

#define PANEL_W 520
#define LINE_H 16
#define MAX_PANEL_H 1400
static unsigned char g_panel[PANEL_W * MAX_PANEL_H * 4];
#define HUD_W 360
static unsigned char g_hud[HUD_W * 22 * 4];
static int g_panel_h = 0;

/* ---------- real light sources of the game (docs/recon/2026-11-07_lights_recon.md) ----------
   div.exe keeps no list of active lights: every frame it hands each one to the renderer DLL (slashN.dll) through
   renderer->vt[+0x48..+0x5c](LightRec*) (__thiscall, one stack arg, @0x40113e). We patch those 6 vtable slots, copy each record
   (position is already final and relative to the camera centre), convert it to game-frame pixels and publish the list on the
   game's Present (fx_game_present, game thread). The render thread takes a snapshot of the published list (fx_bloom). */
#define FXL_MAX 64
static float clampf(float v, float a, float b);
#define DD_RENDERER  0x746a58   /* void* renderer (vtable object), 0 until DllSlashedInit */
#define DD_LIGHTLIB  0x658c5c   /* int* lib: [0] entries {char* name, LightRec* rec, int type}, [1] count */
#define DD_FRAME_W   0x64d9b8
#define DD_FRAME_H   0x64d9bc
#define DD_WORLD     0x658d28   /* int: 1 = normal world frame */
#define DD_TWILIGHT  0x658c24   /* int* T: T[7] 0..320 (320 = full day), T[8] 0 day 1 dusk 2 night */
typedef struct { float sx, sy, rad, h, r, g, b, inten; int kind; } FXLIGHT;   /* kind: 0 lamp/fire, 1 world magic, 2 spell/effect, 3 shown by markers only (hero, monsters, gold, gems) */
typedef void* (__fastcall *FX_LIGHTFN)(void* self, void* edx, void* rec);     /* = __thiscall with one stack argument */
static CRITICAL_SECTION g_lcs; static volatile LONG g_lcs_state = 0;
static FXLIGHT g_lcol[FXL_MAX], g_lpub[FXL_MAX]; static int g_lncol = 0, g_lnpub = 0, g_lcalls = 0, g_lpub_calls = 0;
static float g_lpub_night = 0.0f; static int g_lpub_world = 1; static DWORD g_lpub_t = 0;
static int g_game = -1;   /* -1 not checked, 0 not div.exe 1.0.0.62 layout, 1 ok */
static void* g_lorig[6]; static void** g_lvt = NULL;
/* render-thread snapshot */
static float g_rs_lp[FXL_MAX * 4], g_rs_lc[FXL_MAX * 4]; static int g_rs_n = 0, g_rs_calls = 0, g_rs_world = 1; static float g_rs_night = 0.0f;
static signed char g_lcls[512]; static void* g_lcls_lib = NULL; static BOOL g_rs_fresh = FALSE;

static void lcs_enter(void)
{
    if (g_lcs_state != 2)
    {
        if (InterlockedCompareExchange(&g_lcs_state, 1, 0) == 0) { InitializeCriticalSection(&g_lcs); InterlockedExchange(&g_lcs_state, 2); }
        else while (g_lcs_state != 2) Sleep(0);
    }
    EnterCriticalSection(&g_lcs);
}
static void lcs_leave(void) { LeaveCriticalSection(&g_lcs); }

static BOOL readable(const void* p, size_t n)
{
    MEMORY_BASIC_INFORMATION mi;
    if (!VirtualQuery(p, &mi, sizeof(mi)) || mi.State != MEM_COMMIT || (mi.Protect & (PAGE_NOACCESS | PAGE_GUARD))) return FALSE;
    return (const char*)p + n <= (const char*)mi.BaseAddress + mi.RegionSize;
}

/* the game is div.exe with the known layout: the light call site @0x40113e = mov ecx,[0x746a58]; mov edx,[ecx] */
static BOOL game_ok(void)
{
    static const unsigned char sig[8] = { 0x8b, 0x0d, 0x58, 0x6a, 0x74, 0x00, 0x8b, 0x11 };
    if (g_game < 0)
        g_game = (GetModuleHandleA(NULL) == (HMODULE)0x400000 && readable((void*)0x40113e, 8) && memcmp((void*)0x40113e, sig, 8) == 0
                  && readable((void*)DD_RENDERER, 4) && readable((void*)DD_WORLD, 4)) ? 1 : 0;
    return g_game == 1;
}

/* light.lib name -> kind; names from static\light.lib / light.str */
static int kind_of_name(const char* n)
{
    static const char* lamp[] = { "Default Light", "Castle Light", "Witch Dungeon Light", "FirePlace", "Fire", "Burning Wagon light", NULL };
    static const char* wmagic[] = { "Orb Light", "Big blue light", "huge blue light", "Star Blue light", NULL };
    static const char* none[] = { "Money Light", "Red Gem", "Green Gem", "Yellow Gem", "Monster light", NULL };
    int i;
    if (!n) return 3;
    for (i = 0; lamp[i]; i++) if (strcmp(n, lamp[i]) == 0) return 0;
    for (i = 0; wmagic[i]; i++) if (strcmp(n, wmagic[i]) == 0) return 1;
    if (strncmp(n, "COS ", 4) == 0 || strcmp(n, "COS light") == 0) return 1;
    for (i = 0; none[i]; i++) if (strcmp(n, none[i]) == 0) return 3;
    if (strncmp(n, "Player", 6) == 0) return 3;
    return 2;   /* spells, explosions, summons ... */
}

/* lib index of a record (-1 = not a library record: the agent's own light, i.e. hero / monsters) and its kind */
static int rec_kind(const void* rec)
{
    int* lib = *(int**)DD_LIGHTLIB; int* arr; int n, i;
    if (!lib || !readable(lib, 8)) return 3;
    arr = (int*)lib[0]; n = lib[1];
    if (!arr || n <= 0 || n > 4096 || !readable(arr, (size_t)n * 12)) return 3;
    if (g_lcls_lib != (void*)arr) { memset(g_lcls, -2, sizeof(g_lcls)); g_lcls_lib = (void*)arr; }
    for (i = 0; i < n; i++)
        if ((const void*)arr[i * 3 + 1] == rec)
        {
            if (i < (int)sizeof(g_lcls) && g_lcls[i] != -2) return g_lcls[i];
            {
                const char* nm = (const char*)arr[i * 3]; int k = (nm && readable(nm, 1)) ? kind_of_name(nm) : 2;
                if (i < (int)sizeof(g_lcls)) g_lcls[i] = (signed char)k;
                return k;
            }
        }
    return 3;
}

static float rdnum(const void* p)   /* radii are ints in the parser, but accept a float if the int reading is absurd */
{
    int v = *(const int*)p; float f = *(const float*)p;
    if (v >= 0 && v <= 20000) return (float)v;
    if (f >= 0.0f && f <= 20000.0f) return f;
    return 0.0f;
}

static void light_rec(int type, const void* rec)
{
    const int* ri = (const int*)rec; const float* rf = (const float*)rec; FXLIGHT L; int W, H, i, k; float dX, h, dZ;
    g_lcalls++;
    if (type != 0 && type != 5) return;                 /* shockwave / noise / periodic / polar: effects, not lamps */
    if (!readable(rec, 0x4c)) return;
    W = *(int*)DD_FRAME_W; H = *(int*)DD_FRAME_H;
    if (W <= 0 || H <= 0 || W > 8192 || H > 8192) return;
    dX = (float)ri[0]; h = (float)ri[1]; dZ = (float)ri[2];
    if (type == 0) L.rad = rdnum(rf + 12);              /* +0x30 maxrad */
    else { dX = (dX + ri[12]) * 0.5f; h = (h + ri[13]) * 0.5f; dZ = (dZ + ri[14]) * 0.5f; L.rad = rdnum(rf + 15); }   /* cylinder: middle of POSITION..POSITION2, +0x3c maxrad */
    if (L.rad < 4.0f || L.rad > 600.0f) return;          /* FD crystals etc. (1000) are not lamps */
    L.sx = W * 0.5f + dX + dZ * 0.5f; L.sy = H * 0.5f - dZ * 0.5f - h; L.h = h;
    if (L.sx < -L.rad || L.sx > W + L.rad || L.sy < -L.rad || L.sy > H + L.rad) return;
    L.r = clampf(rf[3], 0, 1); L.g = clampf(rf[4], 0, 1); L.b = clampf(rf[5], 0, 1);
    L.inten = ri[8] ? clampf(rf[9], 0.0f, 2.0f) : 1.0f;  /* +0x20 modulate -> +0x24 brightness (the game's own flicker) */
    if (!(L.inten == L.inten)) L.inten = 1.0f;
    k = rec_kind(rec); L.kind = k;
    for (i = 0; i < g_lncol; i++)                        /* the same light handed twice in a frame */
        if (fabsf(g_lcol[i].sx - L.sx) < 1.0f && fabsf(g_lcol[i].sy - L.sy) < 1.0f && fabsf(g_lcol[i].rad - L.rad) < 1.0f) return;
    if (g_lncol < FXL_MAX) g_lcol[g_lncol++] = L;
    else if (k < 3) for (i = 0; i < FXL_MAX; i++) if (g_lcol[i].kind == 3) { g_lcol[i] = L; break; }
}

static void light_hook(int type, void* rec)
{
    if (!rec) return;
    lcs_enter();
    __try { light_rec(type, rec); } __except (EXCEPTION_EXECUTE_HANDLER) {}
    lcs_leave();
}
#define FX_LHK(i) static void* __fastcall lhk##i(void* self, void* edx, void* rec) { light_hook(i, rec); return ((FX_LIGHTFN)g_lorig[i])(self, edx, rec); }
FX_LHK(0) FX_LHK(1) FX_LHK(2) FX_LHK(3) FX_LHK(4) FX_LHK(5)
static void* const g_lhk[6] = { (void*)lhk0, (void*)lhk1, (void*)lhk2, (void*)lhk3, (void*)lhk4, (void*)lhk5 };

/* (re)hooks the renderer vtable; cheap when already hooked. A renderer re-create (resolution change) gives a fresh vtable. */
static void lights_install(void)
{
    void* R = *(void**)DD_RENDERER; void** vt; int i; DWORD old;
    if (!R || !readable(R, 4)) return;
    vt = *(void***)R;
    if (!vt || !readable(vt + 18, 24)) return;
    for (i = 0; i < 6; i++) if (vt[18 + i] != g_lhk[i]) break;
    if (i == 6) return;
    if (!VirtualProtect(vt + 18, 24, PAGE_READWRITE, &old)) return;
    for (i = 0; i < 6; i++) if (vt[18 + i] != g_lhk[i]) { g_lorig[i] = vt[18 + i]; vt[18 + i] = g_lhk[i]; }
    VirtualProtect(vt + 18, 24, old, &old);
    if (g_lvt != vt) TRACE("ddfx: light hooks on renderer vtable %p\n", vt);
    g_lvt = vt;
}

/* game thread, on every Present-like call to the primary surface (Flip / Blt / BltFast / Unlock) */
void fx_game_present(void)
{
    DWORD now;
    if (!g_config.fx || !game_ok()) return;
    __try { lights_install(); } __except (EXCEPTION_EXECUTE_HANDLER) {}
    lcs_enter();
    now = GetTickCount();
    __try
    {
        int world = *(int*)DD_WORLD == 1; int* T = *(int**)DD_TWILIGHT; float night = 0.0f;
        if (T && readable(T, 9 * 4)) night = clampf(1.0f - (float)T[7] / 320.0f, 0.0f, 1.0f);
        g_lpub_world = world; g_lpub_night = night;
        if (!world) { g_lnpub = 0; g_lpub_calls = 0; g_lpub_t = now; }
        else if (g_lcalls > 0) { memcpy(g_lpub, g_lcol, sizeof(FXLIGHT) * g_lncol); g_lnpub = g_lncol; g_lpub_calls = g_lcalls; g_lpub_t = now; }
        else if (now - g_lpub_t > 250) { g_lnpub = 0; g_lpub_calls = 0; g_lpub_t = now; }   /* a second Present in the same frame keeps the list; a frame without lights clears it */
    }
    __except (EXCEPTION_EXECUTE_HANDLER) {}
    g_lncol = 0; g_lcalls = 0;
    lcs_leave();
}

/* render thread: copy of the published list for this frame's uniforms */
static int pidx(const char* key);
static void lights_snapshot(void)
{
    int i;
    if (!game_ok()) { g_rs_n = 0; g_rs_calls = 0; g_rs_world = 1; g_rs_night = 0.0f; return; }
    lcs_enter();
    g_rs_n = g_lnpub; g_rs_calls = g_lpub_calls; g_rs_world = g_lpub_world; g_rs_night = g_lpub_night;
    for (i = 0; i < g_rs_n; i++)
    {
        const FXLIGHT* L = &g_lpub[i];
        g_rs_lp[i * 4 + 0] = L->sx; g_rs_lp[i * 4 + 1] = L->sy; g_rs_lp[i * 4 + 2] = L->rad; g_rs_lp[i * 4 + 3] = L->h;
        g_rs_lc[i * 4 + 0] = L->r; g_rs_lc[i * 4 + 1] = L->g; g_rs_lc[i * 4 + 2] = L->b;
        {
            float it = clampf(L->inten, 0.0f, 2.0f);
            float vf = g_v[pidx("source_flicker")], vm = g_v[pidx("spell_pulse")];
            if ((L->kind == 0 && vf > 0.001f) || ((L->kind == 1 || L->kind == 2) && vm > 0.001f))
            {
                float time = (float)(GetTickCount() % 1000000) / 1000.0f;
                float phase = L->sx * 0.009f + L->sy * 0.013f + L->r * 1.83f + L->rad * 0.017f;
                float modulation;
                if (L->kind == 0) {
                    float w = 0.65f * sinf(time * 6.30f + phase) + 0.35f * sinf(time * 11.17f + phase * 1.7f);
                    modulation = max(0.55f, 1.0f + w * vf);
                } else {
                    float w = 0.65f * sinf(time * 3.2f + phase) + 0.35f * sinf(time * 5.1f + phase * 0.61f);
                    modulation = max(0.4f, 1.0f + w * vm * (L->kind == 2 ? 0.60f : 0.35f));
                }
                it *= modulation;
            }
            g_rs_lc[i * 4 + 3] = clampf(it, 0.0f, 2.0f) + 10.0f * L->kind;
        }
    }
    lcs_leave();
    g_rs_fresh = TRUE;
}

#define FX_WOW_MAX 12
typedef struct { float x,y,r,g,b,rad; int used, age; } WOW_SOURCE;
typedef struct { float x,y,r,g,b,rad; DWORD birth; } WOW_ECHO;
static WOW_SOURCE g_wow_prev[FX_WOW_MAX];
static WOW_SOURCE g_wow_static_prev[FX_WOW_MAX];static int g_wow_static_n=0;
static int g_wow_prev_count=0, g_wow_nt=0, g_wow_ne=0;
static WOW_ECHO g_wow_echo[FX_WOW_MAX];
static float g_wow_ta[FX_WOW_MAX*4],g_wow_tc[FX_WOW_MAX*4],g_wow_ea[FX_WOW_MAX*4],g_wow_ec[FX_WOW_MAX*4];
static DWORD g_wow_last=0;
static void wow_reset(void)
{
    g_wow_prev_count=0;g_wow_nt=0;g_wow_ne=0;g_wow_last=0;g_wow_static_n=0;
    memset(g_wow_echo,0,sizeof(g_wow_echo));
}
static void wow_update(void)
{
    WOW_SOURCE curr[FX_WOW_MAX], anchors[FX_WOW_MAX]; int nc=0,na=0,i,j,idx;
    float cameraX=0.f,cameraY=0.f;int cameraN=0;
    DWORD now=GetTickCount(),dt=now-g_wow_last;
    BOOL trails=(g_v[pidx("magic_trails")]>0.001f),echo=(g_v[pidx("magic_echo")]>0.001f);
    g_wow_nt=0;g_wow_ne=0;
    if (!g_rs_world || g_v[pidx("fx")]<0.5f || (!trails && !echo) || (g_wow_last && dt>180))
        wow_reset();
    if (!g_rs_world || g_v[pidx("fx")]<0.5f || (!trails && !echo)) return;
    /* Estimate camera pan from at least two matching static lamp/world-magic anchors.
       This prevents every spell being drawn as moving when the player scrolls the map.
       With <2 consistent anchors, correction stays zero (conservative fallback). */
    for(i=0;i<g_rs_n && na<FX_WOW_MAX;i++)
    {
        int kind=(int)(g_rs_lc[i*4+3]/10.0f+0.01f);
        if(kind!=0 && kind!=1)continue;
        anchors[na].x=g_rs_lp[i*4];anchors[na].y=g_rs_lp[i*4+1];
        anchors[na].r=g_rs_lc[i*4];anchors[na].g=g_rs_lc[i*4+1];anchors[na].b=g_rs_lc[i*4+2];
        anchors[na].rad=g_rs_lp[i*4+2];anchors[na].used=0;++na;
    }
    if(g_wow_last && dt<=180)
    {
        for(i=0;i<na;i++)
        {
            float best=80.f*80.f;idx=-1;
            for(j=0;j<g_wow_static_n;j++)
            {
                float dx=anchors[i].x-g_wow_static_prev[j].x,dy=anchors[i].y-g_wow_static_prev[j].y;
                float dc=fabsf(anchors[i].r-g_wow_static_prev[j].r)+fabsf(anchors[i].g-g_wow_static_prev[j].g)+fabsf(anchors[i].b-g_wow_static_prev[j].b);
                float ds=fabsf(anchors[i].rad-g_wow_static_prev[j].rad);
                float d2=dx*dx+dy*dy;
                if(!g_wow_static_prev[j].used && dc<0.15f && ds<5.f && d2<best){best=d2;idx=j;}
            }
            if(idx>=0)
            {
                float dx=anchors[i].x-g_wow_static_prev[idx].x;
                float dy=anchors[i].y-g_wow_static_prev[idx].y;
                g_wow_static_prev[idx].used=1;
                if(cameraN==0){cameraX=dx;cameraY=dy;cameraN=1;}
                else if(fabsf(dx-cameraX/cameraN)<4.f && fabsf(dy-cameraY/cameraN)<4.f)
                    {cameraX+=dx;cameraY+=dy;cameraN++;}
            }
        }
        if(cameraN>=2){cameraX/=cameraN;cameraY/=cameraN;}
        else{cameraX=0.f;cameraY=0.f;}
    }
    /* Only dynamic spell/effect kind 2; static lamp kind 0/1 and marker kind 3 excluded.
       Motion matching is conservative: max 58px/frame after camera correction. */
    for(i=0;i<g_rs_n && nc<FX_WOW_MAX;i++)
    {
        float a=g_rs_lc[i*4+3],x=g_rs_lp[i*4],y=g_rs_lp[i*4+1];
        int kind=(int)(a/10.0f+0.01f);
        if(kind!=2 || a-20.0f < 0.03f) continue;
        if(x<-20.f || y<-20.f || x>8192.f || y>8192.f) continue;
        curr[nc].x=x;curr[nc].y=y;
        curr[nc].r=g_rs_lc[i*4];curr[nc].g=g_rs_lc[i*4+1];curr[nc].b=g_rs_lc[i*4+2];
        curr[nc].rad=g_rs_lp[i*4+2];curr[nc].used=0;curr[nc].age=1;
        ++nc;
    }
    for(i=0;i<g_wow_prev_count;i++)g_wow_prev[i].used=0;
    if(g_wow_last && dt<=180)
    {
        for(i=0;i<nc;i++)
        {
            float closest=58.f*58.f;idx=-1;
            for(j=0;j<g_wow_prev_count;j++)
            {
                float dx=curr[i].x-(g_wow_prev[j].x+cameraX),dy=curr[i].y-(g_wow_prev[j].y+cameraY);
                float col=fabsf(curr[i].r-g_wow_prev[j].r)+fabsf(curr[i].g-g_wow_prev[j].g)+fabsf(curr[i].b-g_wow_prev[j].b);
                float d2=dx*dx+dy*dy;
                if(!g_wow_prev[j].used && col<0.34f && d2<closest){closest=d2;idx=j;}
            }
            if(idx>=0)
            {
                g_wow_prev[idx].used=1;
                curr[i].age=g_wow_prev[idx].age<255 ? g_wow_prev[idx].age+1 : 255;
                if(trails && closest>4.f && g_wow_nt<FX_WOW_MAX)
                {
                    int n=g_wow_nt++;
                    g_wow_ta[n*4]=g_wow_prev[idx].x+cameraX;g_wow_ta[n*4+1]=g_wow_prev[idx].y+cameraY;
                    g_wow_ta[n*4+2]=curr[i].x;g_wow_ta[n*4+3]=curr[i].y;
                    g_wow_tc[n*4]=curr[i].r;g_wow_tc[n*4+1]=curr[i].g;g_wow_tc[n*4+2]=curr[i].b;
                    g_wow_tc[n*4+3]=1.f;
                }
            }
        }
        /* No real hit event hook yet: a disappeared source leaves a short fading afterimage,
           not an asserted impact. Do not ring at the viewport edge. */
        if(echo)
          for(j=0;j<g_wow_prev_count;j++)if(!g_wow_prev[j].used && g_wow_prev[j].age>=2)
          {
              WOW_SOURCE* o=&g_wow_prev[j];
              if(o->x<25.f||o->y<25.f||o->x>*(int*)DD_FRAME_W-25.f||o->y>*(int*)DD_FRAME_H-25.f)continue;
              for(idx=0;idx<FX_WOW_MAX;idx++)if(!g_wow_echo[idx].birth)break;
              if(idx<FX_WOW_MAX){
                  g_wow_echo[idx].x=o->x+cameraX;g_wow_echo[idx].y=o->y+cameraY;g_wow_echo[idx].r=o->r;g_wow_echo[idx].g=o->g;g_wow_echo[idx].b=o->b;
                  g_wow_echo[idx].rad=o->rad;g_wow_echo[idx].birth=now;
              }
          }
    }
    if(echo)
      for(i=0;i<FX_WOW_MAX;i++)if(g_wow_echo[i].birth)
      {
          float age=(now-g_wow_echo[i].birth)/340.f;
          if(age>=1.f){g_wow_echo[i].birth=0;continue;}
          if(g_wow_ne>=FX_WOW_MAX)break;
          idx=g_wow_ne++;
          g_wow_ea[idx*4]=g_wow_echo[i].x;g_wow_ea[idx*4+1]=g_wow_echo[i].y;
          g_wow_ea[idx*4+2]=g_wow_echo[i].rad;g_wow_ea[idx*4+3]=age;
          g_wow_ec[idx*4]=g_wow_echo[i].r;g_wow_ec[idx*4+1]=g_wow_echo[i].g;g_wow_ec[idx*4+2]=g_wow_echo[i].b;g_wow_ec[idx*4+3]=1.f;
      }
    for(i=0;i<nc;i++)g_wow_prev[i]=curr[i];
    for(i=0;i<na;i++)g_wow_static_prev[i]=anchors[i];
    g_wow_static_n=na;
    g_wow_prev_count=nc;g_wow_last=now;
}
static void wow_uniforms(GLuint prog)
{
    GLint l;
    if((l=glGetUniformLocation(prog,"u_nt"))!=-1)glUniform1i(l,g_wow_nt);
    if((l=glGetUniformLocation(prog,"u_ne"))!=-1)glUniform1i(l,g_wow_ne);
    if(g_wow_nt>0)
    {
       if((l=glGetUniformLocation(prog,"u_ta"))!=-1)glUniform4fv(l,g_wow_nt,g_wow_ta);
       if((l=glGetUniformLocation(prog,"u_tc"))!=-1)glUniform4fv(l,g_wow_nt,g_wow_tc);
    }
    if(g_wow_ne>0)
    {
       if((l=glGetUniformLocation(prog,"u_ea"))!=-1)glUniform4fv(l,g_wow_ne,g_wow_ea);
       if((l=glGetUniformLocation(prog,"u_ec"))!=-1)glUniform4fv(l,g_wow_ne,g_wow_ec);
    }
}

static void set_light_uniforms(GLuint prog)
{
    GLint l;
    if ((l = glGetUniformLocation(prog, "u_ln")) != -1) glUniform1i(l, g_rs_n);
    if (g_rs_n > 0)
    {
        if ((l = glGetUniformLocation(prog, "u_lp")) != -1) glUniform4fv(l, g_rs_n, g_rs_lp);
        if ((l = glGetUniformLocation(prog, "u_lc")) != -1) glUniform4fv(l, g_rs_n, g_rs_lc);
    }
    if ((l = glGetUniformLocation(prog, "u_night")) != -1) glUniform1f(l, g_rs_night);
    if ((l = glGetUniformLocation(prog, "u_world")) != -1) glUniform1f(l, g_rs_world ? 1.0f : 0.0f);
}

/* ---------- value helpers ---------- */
static int pidx(const char* key) { int i; for (i = 0; i < FX_NP; i++) if (strcmp(FX_PARAMS[i].key, key) == 0) return i; return -1; }
static float clampf(float v, float a, float b) { return v < a ? a : (v > b ? b : v); }
static void set_defaults(void) { int i; for (i = 0; i < FX_NP; i++) g_v[i] = FX_PARAMS[i].def; }

static void apply_kv(const char* k, int klen, const char* val)
{
    int i;
    for (i = 0; i < FX_NP; i++)
        if ((int)strlen(FX_PARAMS[i].key) == klen && _strnicmp(FX_PARAMS[i].key, k, klen) == 0)
        {
            g_v[i] = clampf((float)atof(val), FX_PARAMS[i].mn, FX_PARAMS[i].mx);
            return;
        }
}

/* "k=v,k=v" */
static void apply_list(const char* s)
{
    const char* p = s;
    while (*p)
    {
        const char* eq = strchr(p, '='); const char* comma = strchr(p, ',');
        if (!eq) break;
        apply_kv(p, (int)(eq - p), eq + 1);
        if (!comma) break;
        p = comma + 1;
    }
}

/* ---------- cfg file ---------- */
static char* read_file(const char* path, int* len)
{
    HANDLE h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, 0, NULL);
    DWORD sz, rd = 0; char* b;
    if (h == INVALID_HANDLE_VALUE) return NULL;
    sz = GetFileSize(h, NULL); b = (char*)malloc(sz + 1);
    if (!b) { CloseHandle(h); return NULL; }
    ReadFile(h, b, sz, &rd, NULL); b[rd] = 0; CloseHandle(h); if (len) *len = (int)rd; return b;
}

/* loads section [name] into g_v (on top of current g_v); returns TRUE if section found */
static BOOL cfg_load_section(const char* name)
{
    char* b = read_file(g_cfg_path, NULL), *line, *next; BOOL in = FALSE, found = FALSE;
    if (!b) return FALSE;
    for (line = b; line && *line; line = next)
    {
        char* e;
        next = strchr(line, '\n'); if (next) { *next = 0; next++; }
        while (*line == ' ' || *line == '\t') line++;
        e = line + strlen(line); while (e > line && (e[-1] == '\r' || e[-1] == ' ')) *--e = 0;
        if (*line == ';' || *line == '#' || !*line) continue;
        if (*line == '[') { in = (_strnicmp(line + 1, name, strlen(name)) == 0 && line[1 + strlen(name)] == ']'); if (in) found = TRUE; continue; }
        if (in) { char* eq = strchr(line, '='); if (eq) apply_kv(line, (int)(eq - line), eq + 1); }
    }
    free(b); return found;
}

/* rewrites the cfg: keeps other sections, replaces [name] with current values */
static void cfg_save_section(const char* name)
{
    char* b = read_file(g_cfg_path, NULL); char* out; size_t cap = 65536, n = 0; char* line, *next; BOOL skip = FALSE; int i; HANDLE h; DWORD wr;
    out = (char*)malloc(cap); if (!out) { free(b); return; }
    n += sprintf(out + n, "; ddfx config v1 (written by the in-game menu). Sections: [current] = used at start, [slot1]..[slot5] = user presets.\r\n; keys = parameter names, values are floats (bool 0/1).\r\n");
    if (b)
        for (line = b; line && *line; line = next)
        {
            char t[256];
            next = strchr(line, '\n'); if (next) { *next = 0; next++; }
            { char* e = line + strlen(line); while (e > line && e[-1] == '\r') *--e = 0; }
            if (line[0] == ';') continue;
            if (line[0] == '[') { skip = (_strnicmp(line + 1, name, strlen(name)) == 0 && line[1 + strlen(name)] == ']'); }
            if (skip || n + 300 > cap) continue;
            _snprintf(t, sizeof(t) - 1, "%s\r\n", line); t[sizeof(t) - 1] = 0; n += sprintf(out + n, "%s", t);
        }
    n += sprintf(out + n, "[%s]\r\n", name);
    for (i = 0; i < FX_NP; i++) n += sprintf(out + n, "%s=%.4g\r\n", FX_PARAMS[i].key, g_v[i]);
    h = CreateFileA(g_cfg_path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h != INVALID_HANDLE_VALUE)
    {
        BOOL ok = WriteFile(h, out, (DWORD)n, &wr, NULL);
        CloseHandle(h);
        /* Ctrl+Shift+1 must restore the latest explicitly SAVED [current], not
           an older launch snapshot, while changing quick looks never writes a file. */
        if (ok && wr == (DWORD)n && strcmp(name, "current") == 0)
            memcpy(g_saved_start, g_v, sizeof(g_v));
    }
    free(out); free(b);
}

static void toast(const char* s) { _snprintf(g_toast, sizeof(g_toast) - 1, "%s", s); g_toast_until = GetTickCount() + 2500; g_dirty = TRUE; }

static void load_preset(int slot) /* 0-based */
{
    char sec[16];
    set_defaults();
    _snprintf(sec, sizeof(sec) - 1, "slot%d", slot + 1);
    if (!cfg_load_section(sec)) apply_list(FX_PRESET_DEFS[slot]);
    g_v[pidx("fx")] = 1.0f;
    g_dirty = TRUE;
}

static void build_rows(void)
{
    int s, i; g_nrows = 0;
    for (s = 0; s < FX_NSEC; s++)
    {
        g_rows[g_nrows].type = -1; g_rows[g_nrows].idx = s; g_nrows++;
        for (i = 0; i < FX_NP; i++) if (FX_PARAMS[i].sec == s) { g_rows[g_nrows].type = 0; g_rows[g_nrows].idx = i; g_nrows++; }
    }
    g_rows[g_nrows].type = 1; g_rows[g_nrows].idx = 0; g_nrows++;  /* save */
    g_rows[g_nrows].type = 1; g_rows[g_nrows].idx = 1; g_nrows++;  /* reset */
    g_sel = 1;
}

BOOL fx_wanted(void) { return g_config.fx; }
BOOL fx_menu_open(void) { return g_open != 0; }

BOOL fx_swallow_msg(UINT msg, WPARAM wp)
{
    if (!g_config.fx) return FALSE;
    switch (msg)
    {
    case WM_KEYDOWN: case WM_KEYUP: case WM_SYSKEYDOWN: case WM_SYSKEYUP:
        if ((int)wp >= '1' && (int)wp <= '5' &&
            (real_GetAsyncKeyState(VK_CONTROL) & 0x8000) &&
            (real_GetAsyncKeyState(VK_SHIFT) & 0x8000)) return TRUE;
        if ((int)wp == g_k_fx || (int)wp == g_k_menu || (int)wp == g_k_fps) return TRUE;
        /* fall through */
    case WM_CHAR: case WM_SYSCHAR: case WM_DEADCHAR:
        return g_open != 0;
    case WM_LBUTTONDOWN: case WM_LBUTTONUP: case WM_LBUTTONDBLCLK: case WM_RBUTTONDOWN: case WM_RBUTTONUP: case WM_RBUTTONDBLCLK:
    case WM_MBUTTONDOWN: case WM_MBUTTONUP: case WM_MOUSEWHEEL:
        return g_open != 0;
    }
    return FALSE;
}

static void fx_init(void)
{
    HMODULE gl;
    if (g_inited) return;
    g_inited = TRUE;
    gl = GetModuleHandleA("opengl32.dll");
    fx_glEnable = (FX_PGLENABLE)GetProcAddress(gl, "glEnable"); fx_glDisable = (FX_PGLENABLE)GetProcAddress(gl, "glDisable");
    fx_glBlendFunc = (FX_PGLBLENDFUNC)GetProcAddress(gl, "glBlendFunc"); fx_glDrawArrays = (FX_PGLDRAWARRAYS)GetProcAddress(gl, "glDrawArrays");
    _snprintf(g_cfg_path, sizeof(g_cfg_path) - 1, "%sdd-fx.cfg", g_config.dll_path);
    set_defaults();
    cfg_load_section("current");
    memcpy(g_saved_start, g_v, sizeof(g_v));
    g_k_menu = GetPrivateProfileIntA("keys", "menu", VK_F10, g_cfg_path); g_k_fps = GetPrivateProfileIntA("keys", "fps", VK_F11, g_cfg_path); g_k_fx = GetPrivateProfileIntA("keys", "fx", VK_F9, g_cfg_path);
    if (g_k_menu < 1 || g_k_menu > 254) g_k_menu = VK_F10; if (g_k_fps < 1 || g_k_fps > 254) g_k_fps = VK_F11; if (g_k_fx < 1 || g_k_fx > 254) g_k_fx = VK_F9;
    build_rows();
}

/* ---------- programs ---------- */
static GLuint build_pass(const char* define);
static void bl_bind_for_main(void);
static GLuint g_pre_prog, g_down_prog, g_up_prog, g_luma_prog;
static GLint g_loc_glow, g_loc_emit, g_loc_light, g_loc_light2, g_loc_scene, g_loc_bok, g_loc_time;
static BOOL g_core;
static char* make_src(const char* define)
{
    size_t n = strlen(FX_GLSL) + 64; char* s = (char*)malloc(n);
    if (!s) return NULL;
    _snprintf(s, n - 1, "#version 130\n#define %s\n%s", define, FX_GLSL); s[n - 1] = 0; return s;
}

GLuint fx_build_program(BOOL core_profile)
{
    char* vs, *fs; int i;
    fx_init(); g_core = core_profile;
    vs = make_src("VERTEX"); fs = make_src("FRAGMENT");
    g_prog = (vs && fs) ? oglu_build_program(vs, fs, core_profile) : 0;
    free(vs); free(fs);
    if (!g_prog) { TRACE("ddfx: shader build failed\n"); return 0; }
    g_loc_filter = glGetUniformLocation(g_prog, "u_filter");
    {   /* the player's scaling filter (ddraw.ini shader=) is kept: the effects are drawn on top of it */
        char sh[256]; int k; _snprintf(sh, sizeof(sh) - 1, "%s", g_config.shader); sh[255] = 0; for (k = 0; sh[k]; k++) if (sh[k] >= 'A' && sh[k] <= 'Z') sh[k] += 32;
        g_filter = strstr(sh, "catmull") ? 0.0f : strstr(sh, "lanczos") ? 3.0f : strstr(sh, "nearest") ? 1.0f : strstr(sh, "bilinear") ? 2.0f : 0.0f;
    }
    for (i = 0; i < FX_NP; i++) { char nm[64]; _snprintf(nm, sizeof(nm) - 1, "u_%s", FX_PARAMS[i].key); nm[63] = 0; g_loc[i] = glGetUniformLocation(g_prog, nm); }
    g_loc_glow = glGetUniformLocation(g_prog, "u_glow"); g_loc_emit = glGetUniformLocation(g_prog, "u_emitter"); g_loc_light = glGetUniformLocation(g_prog, "u_light"); g_loc_light2 = glGetUniformLocation(g_prog, "u_light2"); g_loc_scene = glGetUniformLocation(g_prog, "u_scene");
    g_loc_bok = glGetUniformLocation(g_prog, "u_bloom_ok"); g_loc_time = glGetUniformLocation(g_prog, "u_time");
    g_pre_prog = build_pass("PRE"); g_down_prog = build_pass("DOWN"); g_up_prog = build_pass("UP"); g_luma_prog = build_pass("LUMA");
    {
        static char ovs[] =
            "#version 130\nuniform vec4 rect;\nout vec2 uv;\nvoid main(){ vec2 p = vec2(float(gl_VertexID & 1), float(gl_VertexID >> 1));\n"
            " uv = vec2(p.x, 1.0 - p.y); gl_Position = vec4(mix(rect.xy, rect.zw, p), 0.0, 1.0); }\n";
        static char ofs[] =
            "#version 130\nuniform sampler2D tex;\nin vec2 uv;\nout vec4 oc;\nvoid main(){ oc = texture(tex, uv); }\n";
        char* v2 = _strdup(ovs), *f2 = _strdup(ofs);
        g_ovl_prog = oglu_build_program(v2, f2, core_profile); free(v2); free(f2);
        if (g_ovl_prog) { g_ovl_rect_loc = glGetUniformLocation(g_ovl_prog, "rect"); glUseProgram(g_ovl_prog); glUniform1i(glGetUniformLocation(g_ovl_prog, "tex"), 0); }
    }
    return g_prog;
}

/* ---------- input ---------- */
static BOOL fg_ours(void)
{
    DWORD pid = 0; HWND fg = GetForegroundWindow();
    if (!fg) return FALSE;
    GetWindowThreadProcessId(fg, &pid);
    return pid == GetCurrentProcessId();
}
static BOOL kdown(int vk) { return (real_GetAsyncKeyState(vk) & 0x8000) != 0; }

typedef struct { BOOL down; DWORD t0, last; } KS;
static KS g_ks[256];
/* returns TRUE on press and on auto-repeat */
static BOOL kpress(int vk, BOOL repeat)
{
    BOOL d = kdown(vk); KS* k = &g_ks[vk & 255]; DWORD now = GetTickCount(); BOOL fire = FALSE;
    if (d && !k->down) { k->t0 = now; k->last = now; fire = TRUE; }
    else if (d && repeat && now - k->t0 > 380 && now - k->last > 45) { k->last = now; fire = TRUE; }
    k->down = d; return fire;
}

static int sel_row_move(int dir)
{
    int n = g_sel;
    do { n += dir; } while (n >= 0 && n < g_nrows && g_rows[n].type < 0);
    return (n < 0 || n >= g_nrows) ? g_sel : n;
}

static void adjust(int idx, int dir, float mult)
{
    const FXPARAM* p = &FX_PARAMS[idx];
    if (p->kind == 1) { g_v[idx] = g_v[idx] > 0.5f ? 0.0f : 1.0f; }
    else
    {
        float st = p->st * mult, v = g_v[idx] + dir * st;
        v = floorf(v / p->st + 0.5f) * p->st;
        g_v[idx] = clampf(v, p->mn, p->mx);
    }
    g_dirty = TRUE;
}

/* Five quick A/B looks; they never write dd-fx.cfg. Every look starts with the
   profile captured at startup, so pressing a new shortcut is predictable. */
static void quick_value(const char* key, float value)
{
    int i=pidx(key);
    if(i>=0)g_v[i]=clampf(value,FX_PARAMS[i].mn,FX_PARAMS[i].mx);
}
static void quick_look(int slot)
{
    memcpy(g_v,g_saved_start,sizeof(g_v));
    quick_value("fx",1);
    quick_value("show_lights",0);
    quick_value("debug",0);
    if(slot==0){toast("FX 1: MY SAVED LOOK");g_dirty=TRUE;return;}
    quick_value("ambient",0);
    quick_value("vignette",0);
    quick_value("fire_on",1);
    quick_value("light_on",1);
    quick_value("magic_on",1);
    quick_value("spell_lights",1);
    if(slot==1)
    {
       quick_value("vibrance",1.15f);quick_value("clarity",0.65f);
       quick_value("saturation",1.28f);quick_value("contrast",0.12f);
       quick_value("shadow_lift",0.32f);quick_value("exposure",0.08f);
       quick_value("fire_bloom",1.5f);quick_value("light_str",0.90f);
       toast("FX 2: VIVID WORLD");
    }
    else if(slot==2)
    {
       quick_value("vibrance",0.95f);quick_value("clarity",0.5f);
       quick_value("saturation",1.35f);quick_value("shadow_lift",0.24f);
       quick_value("magic_bloom",1.65f);quick_value("spell_pulse",0.92f);
       quick_value("magic_trails",1);quick_value("magic_echo",1);
       quick_value("magic_splash",1);quick_value("light_str",1.0f);
       toast("FX 3: MAGIC WOW");
    }
    else if(slot==3)
    {
       quick_value("vibrance",0.65f);quick_value("clarity",0.5f);
       quick_value("cinema_tone",0.95f);quick_value("shadow_lift",0.40f);
       quick_value("saturation",1.23f);quick_value("contrast",0.18f);
       quick_value("atmo_tint",0.6f);quick_value("light_str",0.85f);
       quick_value("exposure",0.05f);quick_value("source_flicker",0.23f);
       toast("FX 4: CINEMA");
    }
    else
    {
       quick_value("vibrance",1.5f);quick_value("clarity",1.15f);
       quick_value("cinema_tone",0.8f);quick_value("shadow_lift",0.43f);
       quick_value("saturation",1.52f);quick_value("contrast",0.23f);
       quick_value("exposure",0.10f);quick_value("fire_bloom",1.95f);
       quick_value("halo",1.4f);quick_value("light_str",1.2f);
       quick_value("light_radius",1.25f);quick_value("magic_bloom",1.85f);
       quick_value("spell_pulse",0.95f);quick_value("magic_trails",1);
       quick_value("magic_echo",1);quick_value("magic_splash",1);
       quick_value("heat_haze",0.65f);quick_value("light_mist",0.7f);
       quick_value("source_flicker",0.27f);
       toast("FX 5: ULTRA WOW");
    }
    g_dirty=TRUE;
}
static void poll_input(void)
{
    BOOL fg = fg_ours(); int i; BOOL shift, ctrl, alt; float mult;
    if (!fg) return;
    shift = kdown(VK_SHIFT); ctrl = kdown(VK_CONTROL); alt = kdown(VK_MENU);
    mult = shift ? 5.0f : (ctrl ? 0.2f : 1.0f);
    for(i=0;i<5;i++)
    {
        BOOL down=kdown('1'+i), combo=shift && ctrl && !alt;
        if(combo && down && !g_quick_key_down[i])quick_look(i);
        g_quick_key_down[i]=down;
    }
    if (kpress(g_k_fps, FALSE)) { int ix = pidx("show_fps"); g_v[ix] = g_v[ix] > 0.5f ? 0.0f : 1.0f; g_dirty = TRUE; }
    if (kpress(g_k_fx, FALSE)) { int ix = pidx("fx"); g_v[ix] = g_v[ix] > 0.5f ? 0.0f : 1.0f; toast(g_v[ix] > 0.5f ? FXS_FXON : FXS_FXOFF); }
    if (kpress(g_k_menu, FALSE)) { InterlockedExchange(&g_open, !g_open); g_dirty = TRUE; }
    if (!g_open) return;
    if (shift && ctrl && !alt) return; /* Quick preset combo is not F10 Shift+slot save. */
    if (kpress(VK_ESCAPE, FALSE)) { InterlockedExchange(&g_open, 0); g_dirty = TRUE; return; }
    if (kpress(VK_UP, TRUE)) { g_sel = sel_row_move(-1); g_dirty = TRUE; }
    if (kpress(VK_DOWN, TRUE)) { g_sel = sel_row_move(1); g_dirty = TRUE; }
    if (kpress(VK_PRIOR, TRUE)) { for (i = 0; i < 8; i++) g_sel = sel_row_move(-1); g_dirty = TRUE; }
    if (kpress(VK_NEXT, TRUE)) { for (i = 0; i < 8; i++) g_sel = sel_row_move(1); g_dirty = TRUE; }
    if (g_rows[g_sel].type == 0)
    {
        int ix = g_rows[g_sel].idx;
        if (kpress(VK_LEFT, TRUE)) adjust(ix, -1, mult);
        if (kpress(VK_RIGHT, TRUE)) adjust(ix, 1, mult);
        if (kpress(VK_RETURN, FALSE) || kpress(VK_SPACE, FALSE)) { if (FX_PARAMS[ix].kind == 1) adjust(ix, 1, 1); }
        if (kpress(VK_BACK, FALSE)) { g_v[ix] = FX_PARAMS[ix].def; g_dirty = TRUE; }
    }
    else if (g_rows[g_sel].type == 1 && (kpress(VK_RETURN, FALSE) || kpress(VK_SPACE, FALSE)))
    {
        if (g_rows[g_sel].idx == 0) { cfg_save_section("current"); toast(FXS_SAVED); }
        else { set_defaults(); toast(FXS_RESETMSG); g_dirty = TRUE; }
    }
    if (kpress('S', FALSE)) { cfg_save_section("current"); toast(FXS_SAVED); }
    if (kpress('R', FALSE)) { set_defaults(); toast(FXS_RESETMSG); g_dirty = TRUE; }
    for (i = 0; i < 5; i++)
        if (kpress('1' + i, FALSE) || kpress(VK_NUMPAD1 + i, FALSE))
        {
            char m[96];
            if (shift) { char sec[16]; _snprintf(sec, sizeof(sec) - 1, "slot%d", i + 1); cfg_save_section(sec); _snprintf(m, sizeof(m) - 1, "%s %d", FXS_SLOT, i + 1); }
            else { load_preset(i); _snprintf(m, sizeof(m) - 1, "%s %d: %s", FXS_LOADED, i + 1, FX_PRESET_NAMES[i]); }
            toast(m);
        }
}

/* ---------- software text / panel ---------- */
static int glyph_of(unsigned cp)
{
    if (cp >= 32 && cp < 127) return (int)cp - 32;
    if (cp >= 0x410 && cp < 0x450) return 95 + (int)(cp - 0x410);
    if (cp == 0x401) return 159;
    if (cp == 0x451) return 160;
    return '?' - 32;
}

static void blend_px(unsigned char* buf, int bw, int x, int y, int bh, unsigned col, int a)
{
    unsigned char* p; int r, g, b;
    if (x < 0 || y < 0 || x >= bw || y >= bh || a <= 0) return;
    p = buf + (y * bw + x) * 4; r = col & 255; g = (col >> 8) & 255; b = (col >> 16) & 255;
    p[0] = (unsigned char)((p[0] * (255 - a) + r * a) / 255); p[1] = (unsigned char)((p[1] * (255 - a) + g * a) / 255);
    p[2] = (unsigned char)((p[2] * (255 - a) + b * a) / 255); p[3] = (unsigned char)(p[3] + (255 - p[3]) * a / 255);
}
static void fill_rect(unsigned char* buf, int bw, int bh, int x0, int y0, int x1, int y1, unsigned col, int a)
{
    int x, y; for (y = y0; y < y1; y++) for (x = x0; x < x1; x++) blend_px(buf, bw, x, y, bh, col, a);
}
#define RGB_(r, g, b) ((unsigned)(r) | ((unsigned)(g) << 8) | ((unsigned)(b) << 16))

static int draw_text(unsigned char* buf, int bw, int bh, int x, int y, const char* s, unsigned col)
{
    const unsigned char* p = (const unsigned char*)s;
    while (*p)
    {
        unsigned cp = *p++;
        if (cp >= 0xC0 && cp < 0xE0 && *p) { cp = ((cp & 0x1F) << 6) | (*p++ & 0x3F); }
        else if (cp >= 0xE0 && p[0] && p[1]) { cp = ((cp & 0x0F) << 12) | ((p[0] & 0x3F) << 6) | (p[1] & 0x3F); p += 2; }
        {
            const unsigned char* g = FX_FONT[glyph_of(cp)]; int gx, gy;
            for (gy = 0; gy < FXF_H; gy++) for (gx = 0; gx < FXF_W; gx++) blend_px(buf, bw, x + gx, y + gy, bh, col, g[gy * FXF_W + gx]);
        }
        x += FXF_W;
    }
    return x;
}

static int visible_rows(void)
{
    int vh = g_ddraw.render.viewport.height; int n = (int)((vh * 0.9f - 64) / LINE_H);
    if (n > g_nrows) n = g_nrows; if (n < 8) n = 8; return n;
}

static void value_str(int idx, char* out, size_t n)
{
    const FXPARAM* p = &FX_PARAMS[idx];
    if (p->kind == 1) { _snprintf(out, n - 1, "%s", g_v[idx] > 0.5f ? FXS_ON : FXS_OFF); }
    else if (strcmp(p->key, "debug") == 0) { int d = (int)(g_v[idx] + 0.5f); _snprintf(out, n - 1, "%s", d == 0 ? FXS_DBG0 : d == 1 ? FXS_DBG1 : d == 2 ? FXS_DBG2 : FXS_DBG3); }
    else _snprintf(out, n - 1, "%.3g", g_v[idx]);
    out[n - 1] = 0;
}

static void render_panel(void)
{
    int vis = visible_rows(), i, y; int H = 22 + 2 * LINE_H + vis * LINE_H + 8;
    /* One hotkey should display only a small notice, not the full options panel. */
    if (!g_open)
    {
        H=52;g_panel_h=H;memset(g_panel,0,PANEL_W*H*4);
        fill_rect(g_panel,PANEL_W,H,0,0,PANEL_W,H,RGB_(14,14,20),215);
        fill_rect(g_panel,PANEL_W,H,0,0,PANEL_W,2,RGB_(220,170,70),255);
        draw_text(g_panel,PANEL_W,H,10,7,g_toast,RGB_(160,235,145));
        draw_text(g_panel,PANEL_W,H,10,27,"CTRL+SHIFT+1..5 LOOKS   F9 BEFORE/AFTER",RGB_(175,175,195));
        return;
    }
    if (H > MAX_PANEL_H) H = MAX_PANEL_H;
    g_panel_h = H; memset(g_panel, 0, PANEL_W * H * 4);
    fill_rect(g_panel, PANEL_W, H, 0, 0, PANEL_W, H, RGB_(14, 14, 20), 215);
    fill_rect(g_panel, PANEL_W, H, 0, 0, PANEL_W, 2, RGB_(220, 170, 70), 255);
    draw_text(g_panel, PANEL_W, H, 10, 5, FXS_TITLE, RGB_(240, 200, 110));
    draw_text(g_panel, PANEL_W, H, 10, 22, FXS_HELP1, RGB_(150, 150, 165));
    draw_text(g_panel, PANEL_W, H, 10, 22 + LINE_H, FXS_HELP2, RGB_(150, 150, 165));
    if (g_sel < g_scroll) g_scroll = g_sel; if (g_sel >= g_scroll + vis) g_scroll = g_sel - vis + 1;
    if (g_scroll < 0) g_scroll = 0;
    y = 22 + 2 * LINE_H + 6;
    for (i = g_scroll; i < g_nrows && i < g_scroll + vis; i++, y += LINE_H)
    {
        ROW* r = &g_rows[i]; BOOL sel = (i == g_sel);
        if (sel) fill_rect(g_panel, PANEL_W, H, 4, y, PANEL_W - 4, y + LINE_H, RGB_(70, 60, 30), 220);
        if (r->type == -1) { draw_text(g_panel, PANEL_W, H, 10, y, FX_SECTIONS_RU[r->idx], RGB_(240, 190, 90)); fill_rect(g_panel, PANEL_W, H, 10 + 9 * (int)strlen(FX_SECTIONS_RU[r->idx]) / 2, y + 8, PANEL_W - 14, y + 9, RGB_(90, 80, 50), 255); }
        else if (r->type == 0)
        {
            const FXPARAM* p = &FX_PARAMS[r->idx]; char v[48]; unsigned col = sel ? RGB_(255, 255, 255) : RGB_(205, 205, 215);
            draw_text(g_panel, PANEL_W, H, 22, y, p->ru, col);
            if (p->kind == 0 && strcmp(p->key, "debug") != 0)
            {
                float f = (g_v[r->idx] - p->mn) / (p->mx - p->mn);
                fill_rect(g_panel, PANEL_W, H, 330, y + 6, 430, y + 10, RGB_(50, 50, 60), 255);
                fill_rect(g_panel, PANEL_W, H, 330, y + 6, 330 + (int)(100 * clampf(f, 0, 1)), y + 10, sel ? RGB_(240, 190, 80) : RGB_(150, 130, 80), 255);
            }
            value_str(r->idx, v, sizeof(v));
            draw_text(g_panel, PANEL_W, H, 440, y, v, (p->kind == 1 && g_v[r->idx] > 0.5f) ? RGB_(120, 230, 130) : col);
        }
        else
        {
            const char* t = r->idx == 0 ? FXS_SAVE : FXS_RESET; draw_text(g_panel, PANEL_W, H, 22, y, t, sel ? RGB_(255, 255, 255) : RGB_(130, 200, 255));
        }
    }
    if (g_nrows > vis)
    {
        int sh = (H - 60) * vis / g_nrows, sy = 54 + (H - 60 - sh) * g_scroll / (g_nrows - vis);
        fill_rect(g_panel, PANEL_W, H, PANEL_W - 6, sy, PANEL_W - 3, sy + sh, RGB_(120, 100, 60), 255);
    }
    if (GetTickCount() < g_toast_until) draw_text(g_panel, PANEL_W, H, 10, H - 18, g_toast, RGB_(130, 235, 140));
}

/* ---------- overlay draw ---------- */
static GLuint mk_tex(void)
{
    GLuint t = 0; glGenTextures(1, &t); glBindTexture(GL_TEXTURE_2D, t);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST); glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE); glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    return t;
}

static void draw_quad(GLuint tex, int w, int h, int px, int py, int scale)
{
    float vw = (float)g_ddraw.render.viewport.width, vh = (float)g_ddraw.render.viewport.height;
    float x0 = px / vw * 2 - 1, x1 = (px + w * scale) / vw * 2 - 1;
    float y1 = 1 - py / vh * 2, y0 = 1 - (py + h * scale) / vh * 2;
    glBindTexture(GL_TEXTURE_2D, tex);
    glUniform4f(g_ovl_rect_loc, x0, y0, x1, y1);
    fx_glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
}

static LARGE_INTEGER g_qf, g_qlast; static int g_frames = 0; static float g_fps = 0; static DWORD g_fps_t = 0; static BOOL g_hud_dirty = TRUE;

void fx_frame(GLuint program)
{
    int i; LARGE_INTEGER now;
    if (!program || program != g_prog) return;
    poll_input();
    for (i = 0; i < FX_NP; i++) if (g_loc[i] != -1) glUniform1f(g_loc[i], g_v[i]);
    if (g_loc_filter != -1) glUniform1f(g_loc_filter, g_filter);
    if (g_loc_time != -1) glUniform1f(g_loc_time, (float)(GetTickCount() % 1000000) / 1000.0f);
    if (!g_rs_fresh) lights_snapshot();   /* fx_bloom did not run this frame: take it here */
    g_rs_fresh = FALSE;
    wow_update();
    set_light_uniforms(program);
    wow_uniforms(program);
    bl_bind_for_main();
    g_frames++; now.QuadPart = GetTickCount();
    if (GetTickCount() - g_fps_t >= 500)
    {
        DWORD t = GetTickCount(); g_fps = g_frames * 1000.0f / (t - g_fps_t + 1); if (g_fps_t == 0) g_fps = 0; g_fps_t = t; g_frames = 0; g_hud_dirty = TRUE;
    }
}

void fx_overlay(void)
{
    BOOL want_panel = g_open || GetTickCount() < g_toast_until, want_hud = g_v[pidx("show_fps")] > 0.5f || g_v[pidx("show_lights")] > 0.5f; int scale;
    static BOOL toast_prev = FALSE;
    if (!g_prog || !g_ovl_prog || !fx_glBlendFunc) return;
    if (toast_prev && !want_panel) { toast_prev = FALSE; }
    if (!want_panel && !want_hud) return;
    scale = g_ddraw.render.viewport.height >= 1700 ? 2 : 1;
    glUseProgram(g_ovl_prog);
    if (!g_ovl_vao) glGenVertexArrays(1, &g_ovl_vao);
    glBindVertexArray(g_ovl_vao);
    fx_glEnable(GL_BLEND); fx_glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
    glActiveTexture(GL_TEXTURE0);
    glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
    if (want_panel)
    {
        if (!g_ovl_tex) { g_ovl_tex = mk_tex(); g_dirty = TRUE; }
        if (g_dirty || GetTickCount() < g_toast_until + 50)
        {
            if (g_open) render_panel(); else { int H = 4 * LINE_H; g_panel_h = H; memset(g_panel, 0, PANEL_W * H * 4); fill_rect(g_panel, PANEL_W, H, 0, 0, PANEL_W, H, RGB_(14, 14, 20), 215); draw_text(g_panel, PANEL_W, H, 10, 24, g_toast, RGB_(130, 235, 140)); }
            glBindTexture(GL_TEXTURE_2D, g_ovl_tex); glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, PANEL_W, g_panel_h, 0, GL_RGBA, GL_UNSIGNED_BYTE, g_panel);
            g_dirty = FALSE;
        }
        draw_quad(g_ovl_tex, PANEL_W, g_panel_h, 16 * scale, 16 * scale, scale);
    }
    if (want_hud)
    {
        char b[96]; BOOL fps = g_v[pidx("show_fps")] > 0.5f, lt = g_v[pidx("show_lights")] > 0.5f; int w = lt ? HUD_W : 120;
        if (!g_hud_tex) { g_hud_tex = mk_tex(); g_hud_dirty = TRUE; }
        if (g_hud_dirty || lt)
        {
            memset(g_hud, 0, sizeof(g_hud)); fill_rect(g_hud, w, 22, 0, 0, w, 22, RGB_(10, 10, 14), 200);
            int n = fps ? _snprintf(b, sizeof(b) - 1, "FPS %.0f  ", g_fps) : 0;
            if (lt) _snprintf(b + n, sizeof(b) - 1 - n, "lights %d/%d night %.2f%s", g_rs_n, g_rs_calls, g_rs_night,
                              g_game != 1 ? " no-game" : (!g_lvt ? " no-hook" : (g_rs_world ? "" : " menu")));
            b[sizeof(b) - 1] = 0;
            draw_text(g_hud, w, 22, 8, 3, b, RGB_(120, 235, 130));
            glBindTexture(GL_TEXTURE_2D, g_hud_tex); glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, 22, 0, GL_RGBA, GL_UNSIGNED_BYTE, g_hud); g_hud_dirty = FALSE;
        }
        draw_quad(g_hud_tex, w, 22, g_ddraw.render.viewport.width - ((w + 10) * scale), 8 * scale, scale);
    }
    fx_glDisable(GL_BLEND);
    glBindVertexArray(0);
    glBindTexture(GL_TEXTURE_2D, 0);
}

/* ---------- bloom chain (fx.glsl PRE / DOWN / UP): level 0 = 1/2 of the game frame, each next level half of it ---------- */
#define FX_NL 5
static GLuint g_bl_vao = 0;
#define FX_NT (2 * FX_NL + 1)
#define FX_LUMA (2 * FX_NL)
static GLuint g_bl_fbo[FX_NT], g_bl_tex[FX_NT];   /* [0..NL-1] downsample, [NL..2NL-1] upsample result (the smallest level has none: its down is used), [LUMA] 1x1 mean brightness */
static int g_bl_w[FX_NL + 1], g_bl_h[FX_NL + 1], g_bl_srcw = 0, g_bl_srch = 0;
static BOOL g_bl_ok = FALSE, g_bl_fresh = FALSE;   /* g_bl_fresh: the chain was drawn for this frame */

static void uni2f(GLint l, float a, float b) { float v[2]; v[0] = a; v[1] = b; glUniform2fv(l, 1, v); }   /* opengl_utils loads only glUniform2fv */

static GLuint build_pass(const char* define)
{
    char* vs = make_src("QUADV"), *fs = make_src(define); GLuint p = (vs && fs) ? oglu_build_program(vs, fs, g_core) : 0;
    free(vs); free(fs); if (!p) TRACE("ddfx: bloom pass %s failed\n", define); return p;
}

static void bl_free(void)
{
    if (g_bl_srcw) { glDeleteTextures(FX_NT, g_bl_tex); if (glDeleteFramebuffers) glDeleteFramebuffers(FX_NT, g_bl_fbo); }
    g_bl_srcw = g_bl_srch = 0; g_bl_ok = FALSE;
}

/* (re)makes the level textures for a w x h game frame; FALSE = no float render target, effects run without glow and light */
static BOOL bl_alloc(int w, int h)
{
    int i;
    if (w == g_bl_srcw && h == g_bl_srch) return g_bl_ok;
    bl_free(); g_bl_srcw = w; g_bl_srch = h; g_bl_ok = TRUE;
    glGenFramebuffers(FX_NT, g_bl_fbo); glGenTextures(FX_NT, g_bl_tex); g_bl_w[FX_NL] = g_bl_h[FX_NL] = 1;
    for (i = 0; i < FX_NL; i++) { g_bl_w[i] = max(1, (w + (2 << i) - 1) >> (i + 1)); g_bl_h[i] = max(1, (h + (2 << i) - 1) >> (i + 1)); }
    for (i = 0; i < FX_NT; i++)
    {
        int l = i == FX_LUMA ? FX_NL : i % FX_NL;
        glBindTexture(GL_TEXTURE_2D, g_bl_tex[i]);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR); glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE); glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA16F, g_bl_w[l], g_bl_h[l], 0, GL_RGBA, GL_FLOAT, NULL);
        glBindFramebuffer(GL_FRAMEBUFFER, g_bl_fbo[i]);
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, g_bl_tex[i], 0);
        if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE) g_bl_ok = FALSE;
    }
    glBindFramebuffer(GL_FRAMEBUFFER, 0); glBindTexture(GL_TEXTURE_2D, 0);
    if (!g_bl_ok) TRACE("ddfx: float FBO not available, glow and light off\n");
    return g_bl_ok;
}

static void bl_target(int i) { int l = i == FX_LUMA ? FX_NL : i % FX_NL; glBindFramebuffer(GL_FRAMEBUFFER, g_bl_fbo[i]); glViewport(0, 0, g_bl_w[l], g_bl_h[l]); }

static void bl_set(GLuint prog, const char* name, int unit, GLuint tex)
{
    glActiveTexture(GL_TEXTURE0 + unit); glBindTexture(GL_TEXTURE_2D, tex); glUniform1i(glGetUniformLocation(prog, name), unit);
}

/* runs the chain on the game frame (scene_tex, w x h used of it); the caller sets its own framebuffer and viewport afterwards */
void fx_bloom(GLuint scene_tex, int w, int h)
{
    int i; float scatter;
    g_bl_fresh = FALSE;
    lights_snapshot();
    if (!g_prog || !g_pre_prog || !g_down_prog || !g_up_prog || !g_luma_prog) return;
    if (!g_rs_world) return;   /* menu / journal / map / loading: no effects */
    if (g_v[pidx("fx")] < 0.5f || (g_v[pidx("fire_on")] < 0.5f && g_v[pidx("magic_on")] < 0.5f && g_v[pidx("spell_lights")] < 0.5f && g_v[pidx("light_on")] < 0.5f && g_v[pidx("debug")] < 2.5f && g_v[pidx("show_lights")] < 0.5f)) return;
    if (!bl_alloc(w, h)) return;
    if (!g_bl_vao) glGenVertexArrays(1, &g_bl_vao);
    glBindVertexArray(g_bl_vao);
    /* PRE: the frame -> level 0 */
    glUseProgram(g_pre_prog);
    for (i = 0; i < FX_NP; i++) { char nm[64]; GLint l; _snprintf(nm, sizeof(nm) - 1, "u_%s", FX_PARAMS[i].key); nm[63] = 0; l = glGetUniformLocation(g_pre_prog, nm); if (l != -1) glUniform1f(l, g_v[i]); }
    uni2f(glGetUniformLocation(g_pre_prog, "InputSize"), (float)w, (float)h);
    /* PRE and final compositing must see the SAME phase for independent lamp flicker. */
    glUniform1f(glGetUniformLocation(g_pre_prog, "u_time"), (float)(GetTickCount() % 1000000) / 1000.0f);
    set_light_uniforms(g_pre_prog);
    bl_set(g_pre_prog, "Texture", 0, scene_tex);
    bl_target(0); fx_glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
    /* LUMA: mean brightness of the frame -> 1x1 */
    glUseProgram(g_luma_prog);
    uni2f(glGetUniformLocation(g_luma_prog, "InputSize"), (float)w, (float)h);
    bl_set(g_luma_prog, "Texture", 0, scene_tex);
    bl_target(FX_LUMA); fx_glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
    /* DOWN: level i-1 -> level i */
    glUseProgram(g_down_prog);
    for (i = 1; i < FX_NL; i++)
    {
        bl_set(g_down_prog, "Src", 0, g_bl_tex[i - 1]);
        uni2f(glGetUniformLocation(g_down_prog, "SrcTexel"), 1.0f / g_bl_w[i - 1], 1.0f / g_bl_h[i - 1]);
        bl_target(i); fx_glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
    }
    /* UP: (level i+1 up) + level i down -> level i up; "Radius" of the glow = how much of the wider levels is kept */
    scatter = clampf(0.45f + 0.2f * (g_v[pidx("fire_radius")] - 1.0f), 0.1f, 0.9f);
    glUseProgram(g_up_prog);
    glUniform1f(glGetUniformLocation(g_up_prog, "Scatter"), scatter);
    for (i = FX_NL - 2; i >= 0; i--)
    {
        bl_set(g_up_prog, "Src", 0, i == FX_NL - 2 ? g_bl_tex[FX_NL - 1] : g_bl_tex[FX_NL + i + 1]);
        bl_set(g_up_prog, "Cur", 1, g_bl_tex[i]);
        uni2f(glGetUniformLocation(g_up_prog, "SrcTexel"), 1.0f / g_bl_w[i + 1], 1.0f / g_bl_h[i + 1]);
        bl_target(FX_NL + i); fx_glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
    }
    glActiveTexture(GL_TEXTURE1); glBindTexture(GL_TEXTURE_2D, 0);
    glActiveTexture(GL_TEXTURE0); glBindTexture(GL_TEXTURE_2D, 0);
    glBindVertexArray(0);
    glBindFramebuffer(GL_FRAMEBUFFER, 0);
    g_bl_fresh = TRUE;
}

/* binds the chain for the main pass (units 2..4) */
static void bl_bind_for_main(void)
{
    BOOL on = g_bl_ok && g_bl_fresh;
    if (g_loc_bok != -1) glUniform1f(g_loc_bok, on ? 1.0f : 0.0f);
    if (!on) return;
    glActiveTexture(GL_TEXTURE2); glBindTexture(GL_TEXTURE_2D, g_bl_tex[FX_NL + 0]); if (g_loc_glow != -1) glUniform1i(g_loc_glow, 2);
    glActiveTexture(GL_TEXTURE3); glBindTexture(GL_TEXTURE_2D, g_bl_tex[FX_NL + 2]); if (g_loc_light != -1) glUniform1i(g_loc_light, 3);
    glActiveTexture(GL_TEXTURE4); glBindTexture(GL_TEXTURE_2D, g_bl_tex[FX_NL + 3]); if (g_loc_light2 != -1) glUniform1i(g_loc_light2, 4);
    glActiveTexture(GL_TEXTURE5); glBindTexture(GL_TEXTURE_2D, g_bl_tex[FX_LUMA]); if (g_loc_scene != -1) glUniform1i(g_loc_scene, 5);
    glActiveTexture(GL_TEXTURE6); glBindTexture(GL_TEXTURE_2D, g_bl_tex[0]); if (g_loc_emit != -1) glUniform1i(g_loc_emit, 6);
    glActiveTexture(GL_TEXTURE0);
}

void fx_release(void)
{
    bl_free();
    g_prog = 0; g_ovl_prog = 0; g_ovl_vao = 0; g_ovl_tex = 0; g_hud_tex = 0; g_pre_prog = g_down_prog = g_up_prog = g_luma_prog = 0; g_bl_vao = 0;
}
