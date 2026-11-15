# GameRemix

[English](#english) · [Русский](#русский)

## English

GameRemix is a Windows utility for classic game fixes, graphics wrappers, UI scaling, fonts, graphics packs, and backups with rollback support. The main supported game is **Divine Divinity**.

Website and signed downloads: **https://gameremix.pro/**.

### Source-only verification build

Requirements: Windows, Python 3, .NET Framework 4.x compiler at `%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe`.

```powershell
git clone https://github.com/s-lexer/GameRemix.git
cd GameRemix
python src/build.py --source-only
```

Produces `dist/build/GameRemix-source-only.exe` from the actual C# sources without the missing proprietary and third-party resources. **This is a limited verification build, not a complete/functional release binary**. It does not prove that a distributed signed EXE is safe or byte-for-byte reproducible. [GitHub Actions checks compilation](.github/workflows/source-build.yml).

### Full-featured rebuild from an official signed release

For the published source snapshot (**1.0.39**), a complete application can now be compiled with **all 106 embedded resources**:

```powershell
git clone https://github.com/s-lexer/GameRemix.git
cd GameRemix
python src/build.py --from-release
```

Output: `dist/build/GameRemix-rebuilt-from-release.exe`. The tool downloads the official signed `GameRemix-1.0.39.exe` from gameremix.pro and verifies its **pinned SHA-256** before extracting its .NET manifest resources **without executing the downloaded program**. It then compiles the public C# sources with all resource streams. The cached release and extracted resources stay under ignored `dist/`, never in Git. A resource-by-resource SHA-256 comparison against the original release was performed successfully.

This provides a **complete unsigned rebuild for code inspection/testing**, not a bit-for-bit reproduction of the signed release. It still relies on the official EXE for binary resources; these are not independently built from source and must be independently audited if evaluating trust. No third-party/game binaries are separately republished in this repository. Do not represent the unsigned rebuild as the official signed distribution.

### Full build with manually supplied resources

```powershell
python src/build.py
```

A complete build requires additional resources in the paths listed in `src/build.py`. The script reports the missing inputs and fails rather than silently producing an incomplete release. Those files include original-game DLLs/fonts, game-derived resources, third-party editors, and dgVoodoo; they are **not** redistributed here. Users who are entitled to use these resources can provide them locally. The MIT-licensed cnc-ddraw build resources are included in `shared/cnc-ddraw/` with their license notices.

**Third-party rights matter:** [dgVoodoo's redistribution rules](https://www.dege.freeweb.hu/dgVoodoo2/ReadmeGeneral/) limit bundling its components in general-purpose launchers. This repository does not include the game itself.

The public branch is a **version 1.0.39 source snapshot**. Newer downloads may contain different source changes. Release signing/publishing are separate. Full byte-for-byte reproducibility has **not** been established.

### VirusTotal and independent verification

A VirusTotal detection **by itself neither proves malware nor a false positive**. Please report the exact file SHA-256, detection name, version, and VirusTotal report URL so it can be investigated.

```powershell
Get-FileHash .\GameRemix-1.0.39.exe -Algorithm SHA256
Get-AuthenticodeSignature .\GameRemix-1.0.39.exe | Format-List
```

Compare a hash against the publisher's official listing for the **same release version**. Verify the signature status and signer; do not turn off antivirus protection based on source availability.

### Source layout

- `src/` — C# / Windows Forms application and build script
- `shared/` — common tools and graphics-wrapper resources
- `games/divine-divinity/` — definitions, patch generators, and tools
- `tools/` — checks and helper scripts
- `docs/` — documentation

Third-party authorship and licensing remain in effect. Publishing the source does not automatically grant rights to separately owned GameRemix code.

---

## Русский

GameRemix — утилита для исправлений классических игр Windows, настройки графических обёрток, интерфейса, шрифтов и графических пакетов. Основная поддерживаемая игра — **Divine Divinity**.

Сайт и подписанные версии: **https://gameremix.pro/**.

### Проверочная сборка исходников

Нужны Windows, Python 3 и компилятор .NET Framework 4.x (`%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe`).

```powershell
git clone https://github.com/s-lexer/GameRemix.git
cd GameRemix
python src/build.py --source-only
```

Получится `dist/build/GameRemix-source-only.exe`. Режим собирает настоящий C#-код приложения, исключая отсутствующие игровые и сторонние ресурсы. **Это неполный проверочный бинар, не полноценная рабочая версия.** Его нельзя выдавать за релиз или использовать для доказательства отсутствия угроз в подписанном EXE. Компиляцию проверяет [GitHub Actions](.github/workflows/source-build.yml).

### Полная сборка с ресурсами из официального релиза

Теперь можно собрать **полную программу со всеми 106 ресурсами** из публичных исходников версии **1.0.39**:

```powershell
git clone https://github.com/s-lexer/GameRemix.git
cd GameRemix
python src/build.py --from-release
```

Результат: `dist/build/GameRemix-rebuilt-from-release.exe`. Скрипт скачивает официальный подписанный `GameRemix-1.0.39.exe` с gameremix.pro, сверяет **жёстко зафиксированный SHA-256**, извлекает встроенные .NET-ресурсы **без запуска скачанного приложения** и компилирует C#-код с этими ресурсами. Кэш находится в игнорируемой Git папке `dist/`. Проверено: все 106 ресурсов собранного и оригинального EXE совпали по SHA-256.

Это **полноценная по составу, но неподписанная** сборка, а не побайтовое воспроизведение подписанного релиза. Исходный EXE остаётся источником сторонних бинарных ресурсов: их происхождение и безопасность этим способом независимо не доказаны. Мы не публикуем игровые и сторонние бинарники отдельно. Не выдавайте пересобранный неподписанный файл за официальный подписанный релиз.

### Полная сборка с ресурсами, предоставленными вручную

```powershell
python src/build.py
```

Требуются дополнительные ресурсы из `src/build.py`. При их отсутствии скрипт перечисляет недостающие файлы и завершается ошибкой. Оригинальные DLL и шрифты игры, производные игровые ресурсы, сторонние редакторы и dgVoodoo не выкладываются — их нужно получать и использовать согласно правам правообладателей. Компоненты cnc-ddraw под лицензией MIT выложены с уведомлениями о лицензии. На [перераспространение dgVoodoo](https://www.dege.freeweb.hu/dgVoodoo2/ReadmeGeneral/) действуют отдельные ограничения, включая встраивание в универсальные лаунчеры.

Публичный репозиторий — **снимок кода версии 1.0.39**, а не обязательно текущего подписанного релиза. Побайтовая воспроизводимость полного релиза пока не подтверждена.

### VirusTotal

Срабатывание антивируса само по себе **не доказывает ни вредоносность, ни ложное срабатывание**. Для анализа нужны SHA-256, название детекта, версия и ссылка на VirusTotal.

```powershell
Get-FileHash .\GameRemix-1.0.39.exe -Algorithm SHA256
Get-AuthenticodeSignature .\GameRemix-1.0.39.exe | Format-List
```

Проверьте подпись и сравните хеш с официальной публикацией **той же версии**. Не отключайте антивирус без дополнительной проверки.
