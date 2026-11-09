# GameRemix

[English](#english) · [Русский](#русский)

## English

A utility for configuring older games on Windows. The main supported game is currently **Divine Divinity**.

GameRemix brings together game fixes, graphics wrapper settings, interface scaling, fonts, graphics packs, and backups with rollback support.

Website and application download: **https://gameremix.pro/**.

### Source code

- `src/` — C# 3 / .NET Framework 3.5 application using Windows Forms.
- `shared/` — shared tools for preparing assets and graphics wrappers.
- `games/divine-divinity/` — game definitions, patch generators, and tools.
- `tools/` — checks and helper scripts.
- `docs/` — documentation for the application's features and interface.

The public branch contains a separate source snapshot. Local development history, internal settings, backup copies of game executables, saved games, and original game assets are not included.

### Building

Requirements: Windows, Python 3, the .NET Framework 3.5 compiler, and MSVC Build Tools for the launcher.

```text
python src/build.py
```

The command produces `dist/build/GameRemix.exe`, a single file built for the .NET Framework 4 (included in Windows 8–11; Windows 7 SP1 needs the .NET Framework 4.8).

**A clean clone is not sufficient for a complete build:** `src/build.py` also expects binary components and prepared resources in `games/divine-divinity/payload/`, `games/divine-divinity/gfx/`, and `shared/cnc-ddraw/`. These are not included in this snapshot; the build script lists the exact paths. This repository does not include the game itself. Release signing and publishing require the project owner's separate infrastructure.

### Third-party components

GameRemix uses third-party components, including cnc-ddraw and dgVoodoo. Their authorship and license terms are preserved; licenses for included third-party source code are located alongside that code. Publishing the source code in this repository does not itself grant a license to GameRemix's own code.

---

## Русский

Утилита для настройки старых игр на Windows. Сейчас основная поддерживаемая игра — **Divine Divinity**.

GameRemix объединяет исправления игры, настройку графических обёрток, масштабирование интерфейса, шрифты, наборы графики и резервные копии с откатом изменений.

Сайт и загрузка готовой программы: **https://gameremix.pro/**.

### Исходники

- `src/` — приложение на C# 3 / .NET Framework 3.5, Windows Forms.
- `shared/` — общие механизмы подготовки ассетов и графических обёрток.
- `games/divine-divinity/` — данные игры, генераторы патчей и инструменты.
- `tools/` — проверки и вспомогательные скрипты.
- `docs/` — описание механизмов и интерфейса.

Публичная ветка содержит отдельный снимок исходников. Локальная рабочая история, внутренние настройки, резервные копии игровых exe, сохранения и оригинальные ресурсы игры сюда не включены.

### Сборка

Нужны Windows, Python 3, компилятор .NET Framework 3.5 и MSVC Build Tools для запускателя.

```text
python src/build.py
```

Команда создаёт `dist/build/GameRemix.exe` — один файл под .NET Framework 4 (есть в Windows 8–11; для Windows 7 SP1 нужен .NET Framework 4.8).

**Чистого клона недостаточно для полной сборки:** `src/build.py` также ожидает бинарные компоненты и подготовленные ресурсы в `games/divine-divinity/payload/`, `games/divine-divinity/gfx/` и `shared/cnc-ddraw/`. Они не включены в этот снимок; точные пути перечислены в скрипте сборки. Репозиторий не содержит дистрибутив игры. Подпись и публикация релизов требуют отдельной инфраструктуры владельца проекта.

### Сторонние компоненты

GameRemix использует сторонние компоненты, включая cnc-ddraw и dgVoodoo. Их авторство и условия лицензирования сохраняются; лицензии включённых сторонних исходников находятся рядом с ними. Наличие исходников в репозитории само по себе не предоставляет лицензию на собственный код GameRemix.
