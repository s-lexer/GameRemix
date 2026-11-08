#ifndef FX_H
#define FX_H

/* ddfx: Divine Divinity FX layer for the cnc-ddraw fork. Config file dd-fx.cfg v1 (see docs). */

#include <windows.h>
#include "opengl_utils.h"

#define FX_VERSION "ddfx 1.2 (cnc-ddraw 7.1.0.0 fork)"

BOOL fx_wanted(void);                 /* ddraw.ini: fx=true */
GLuint fx_build_program(BOOL core_profile);
void fx_bloom(GLuint scene_tex, int w, int h);   /* bloom chain on the game frame, before the main pass (changes FBO and viewport) */
void fx_frame(GLuint program);        /* per frame: poll keys, set uniforms (program already in use) */
void fx_overlay(void);                /* per frame after the shader pass: menu / fps hud */
void fx_release(void);
void fx_game_present(void);           /* game thread, Present-like call to the primary surface: (re)hooks the game renderer's light calls, publishes this frame's light list */
BOOL fx_menu_open(void);              /* game input is blocked while TRUE */
BOOL fx_swallow_msg(UINT msg, WPARAM wp);   /* wndproc helper: TRUE = do not pass to the game */

#endif
