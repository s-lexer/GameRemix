# Single source of truth for ddfx parameters: C header (fx_params.h) and offline tests are generated from this.
# (key, label_ru, label_en, min, max, step, default, kind)  kind: f=float b=bool e=enum(labels)
# ddfx 1.2: glow and warm light come from the game's real light sources (fx.c light hooks), not from pixel colour.
SECTIONS = [
 ('Общее', 'General', [
   ('fx', 'Эффекты вкл (F9)', 'Effects on (F9)', 0, 1, 1, 1, 'b')]),
 ('Свечение огней', 'Lamp glow', [
   ('fire_on', 'Свечение фонарей и огня', 'Lamp and fire glow', 0, 1, 1, 0, 'b'),
   ('fire_bloom', 'Сила (блум пламени)', 'Strength (flame bloom)', 0, 2, 0.05, 0.5, 'f'),
   ('halo', 'Ореол вокруг огня', 'Halo around the light', 0, 2, 0.05, 0.5, 'f'),
   ('fire_radius', 'Радиус свечения', 'Glow radius', 0.2, 3, 0.1, 1.0, 'f'),
   ('fire_v', 'Порог яркости пламени', 'Flame brightness threshold', 0.3, 1.0, 0.01, 0.65, 'f'),
   ('fire_s', 'Порог насыщ. (поиск по цвету)', 'Saturation threshold (colour search)', 0.3, 1.0, 0.01, 0.76, 'f'),
   ('flicker', 'Мерцание', 'Flicker', 0, 0.3, 0.01, 0.0, 'f')]),
 ('Тёплый свет', 'Warm light', [
   ('light_on', 'Освещение от огня', 'Light from fire', 0, 1, 1, 0, 'b'),
   ('light_str', 'Сила', 'Strength', 0, 3, 0.05, 0.4, 'f'),
   ('light_radius', 'Радиус', 'Radius', 0.3, 3, 0.1, 1.0, 'f'),
   ('light_tone', 'Тон (янтарь-красный)', 'Tone (amber-red)', 0, 1, 0.05, 0.3, 'f'),
   ('light_shape', 'Форма пятна (круг-эллипс)', 'Pool shape (circle-ellipse)', 0, 1, 0.1, 1.0, 'f'),
   ('light_drop', 'Доп. сдвиг пятна вниз', 'Extra downward pool shift', 0, 1, 0.1, 0.0, 'f'),
   ('day_level', 'Сила днём (доля от ночи)', 'Daytime strength (of night)', 0, 1, 0.05, 0.2, 'f'),
   ('light_sparse', 'Точечные (поиск по цвету)', 'Point sources (colour search)', 0, 1, 0.1, 0.8, 'f'),
   ('ambient', 'Доп. затемнение (необязательно)', 'Extra night darkening (optional)', 0, 0.7, 0.05, 0.0, 'f')]),
 ('Магия', 'Magic', [
   ('magic_on', 'Магические огни мира', 'World magic lights', 0, 1, 1, 0, 'b'),
   ('spell_lights', 'Огни заклинаний', 'Spell lights', 0, 1, 1, 0, 'b'),
   ('magic_bloom', 'Сила', 'Strength', 0, 2, 0.05, 0.5, 'f'),
   ('magic_v', 'Порог яркости (поиск по цвету)', 'Brightness threshold (colour search)', 0.3, 1.0, 0.01, 0.72, 'f'),
   ('magic_s', 'Порог насыщ. (поиск по цвету)', 'Saturation threshold (colour search)', 0.3, 1.0, 0.01, 0.5, 'f'),
   ('magic_green', 'Зелёная (поиск по цвету)', 'Green (colour search)', 0, 1, 1, 1, 'b')]),
 ('Экспериментальные FX', 'Experimental FX', [
   ('source_flicker', 'Разное мерцание огней', 'Independent flame flicker', 0, 0.35, 0.01, 0.0, 'f'),
   ('spell_pulse', 'Пульсация заклинаний', 'Spell and magic pulse', 0, 1, 0.05, 0.0, 'f'),
   ('heat_haze', 'Жар над пламенем', 'Heat shimmer above flames', 0, 1, 0.05, 0.0, 'f'),
   ('atmo_tint', 'Мягкий цвет дня и ночи', 'Subtle day and night colour', 0, 1, 0.05, 0.0, 'f'),
   ('light_mist', 'Светящаяся пыль у огней', 'Local illuminated mist', 0, 1, 0.05, 0.0, 'f'),
   ('magic_trails', 'Следы магических снарядов', 'Moving spell trails', 0, 1, 0.05, 0.0, 'f'),
   ('magic_echo', 'Затухание исчезнувшей магии', 'Vanishing magic echo', 0, 1, 0.05, 0.0, 'f'),
   ('magic_splash', 'Вспышки от магии', 'Colour splash from magic', 0, 1, 0.05, 0.0, 'f')]),
 ('Картинка', 'Picture', [
   ('exposure', 'Экспозиция', 'Exposure', -1, 1, 0.05, 0.0, 'f'),
   ('gamma', 'Гамма', 'Gamma', 0.6, 1.6, 0.02, 1.0, 'f'),
   ('contrast', 'Контраст', 'Contrast', -0.5, 1, 0.05, 0.0, 'f'),
   ('saturation', 'Насыщенность', 'Saturation', 0, 2, 0.05, 1.0, 'f'),
   ('warmth', 'Теплота тона', 'Warmth', -1, 1, 0.05, 0.0, 'f'),
   ('vignette', 'Виньетка', 'Vignette', 0, 1, 0.05, 0.0, 'f'),
   ('sharpen', 'Резкость', 'Sharpen', 0, 1, 0.05, 0.0, 'f'),
   ('vibrance', 'Живые цвета', 'Adaptive colour vibrance', 0, 2, 0.05, 0, 'f'),
   ('clarity', 'Детали текстур', 'Texture microcontrast', 0, 2, 0.05, 0, 'f'),
   ('cinema_tone', 'Киноцвет теней и света', 'Cinematic split toning', 0, 1, 0.05, 0, 'f'),
   ('shadow_lift', 'Подсветить тени', 'Lift dark details', 0, 1, 0.05, 0, 'f')]),
 ('Интерфейс', 'Interface', [
   ('ui_height', 'Защита панели (высота)', 'Panel protection (height)', 0, 0.4, 0.005, 0.115, 'f')]),
 ('Отладка', 'Debug', [
   ('show_lights', 'Метки источников света', 'Light source markers', 0, 1, 1, 0, 'b'),
   ('color_mask', 'Поиск огня по цвету (если огней нет)', 'Colour fire search (if no lights)', 0, 1, 1, 0, 'b'),
   ('debug', 'Маска (0 нет 1 огонь 2 магия 3 свет)', 'Mask view (0 off 1 fire 2 magic 3 light)', 0, 3, 1, 0, 'f'),
   ('show_fps', 'Счётчик FPS', 'FPS counter', 0, 1, 1, 0, 'b')]),
]
# presets override the neutral defaults above
PRESETS = [
 ('Нейтральный', 'Neutral', {}),
 ('Свечение', 'Glow', dict(fire_on=1, fire_bloom=0.7, halo=0.6, flicker=0.04, magic_on=1, magic_bloom=0.7)),
 ('Эмбиент', 'Ambient', dict(fire_on=1, fire_bloom=0.6, halo=0.5, flicker=0.05, light_on=1, light_str=0.55, ambient=0.05, magic_on=1, magic_bloom=0.6)),
 ('Ночь', 'Night', dict(fire_on=1, fire_bloom=1.10, halo=0.85, fire_radius=1.5, flicker=0.06, light_on=1, light_str=0.85, light_radius=1.15, light_shape=0.4, light_drop=0.0, ambient=0.0, magic_on=1, magic_bloom=0.85, contrast=0.0, vignette=0.0)),
 ('Полный', 'Full', dict(fire_on=1, fire_bloom=0.6, halo=0.5, flicker=0.05, light_on=1, light_str=0.55, ambient=0.0, magic_on=1, magic_bloom=0.6, contrast=0.05, saturation=1.05, vignette=0.03, sharpen=0.2)),
]
def defaults():
    return {p[0]: float(p[6]) for s in SECTIONS for p in s[2]}
def preset(i):
    d = defaults(); d.update({k: float(v) for k, v in PRESETS[i][2].items()}); return d
