# План обратного инжектора и тестовой сборки

## Контекст

Проект: PS2 `Kamen Rider - Seigi no Keifu (Japan)`.

Текущий DAT pipeline уже умеет:

```text
translation_en/DATA/.../*.json -> rebuilt_en/DATA/.../*.DAT
```

Для первого smoke test переведены:

```text
DATA/MENU/CONFIG_MSG.DAT
DATA/MENU/ITEM_GET_MSG.DAT
DATA/MENU/ITEM_MSG.DAT
```

Нужно автоматизировать следующий участок:

```text
rebuilt_en/DATA/.../*.DAT
  -> test_build/DATA/...
  -> rebuilt DATA.CVM
  -> rebuilt PS2 ISO
  -> PCSX2 smoke test
```

`game_dump/DATA.CVM` определен как CRI ROFS/CVM: в заголовке есть `CVMH` и `ROFS`.

## Текущий статус

На 2026-05-15:

- Рабочий полный ISO теперь собирается через сохранение оригинальной раскладки диска и замену `DATA.CVM` внутри исходного ISO.
- Исправлен стоп загрузки после `ELF Loading`: новая сборка должна сохранять оригинальный root layout и LBA `DATA.CVM`, а не пересобирать весь диск произвольным `mkisofs`.
- Английский текст в меню успешно выводится через существующие glyph-коды.
- Для латиницы найден и применен ELF-патч фиксированного шага glyph cursor: `afMsgDrawString` по умолчанию двигал X на `28.0`, для английского сейчас используем `14.0`.
- Текущий рабочий wrap для полной сборки: `--wrap-profile game`. Не использовать глобальный `--wrap-columns 20` для full build: он ломает разные UI-ширины одним общим правилом.
- Нижний textbox в event/cutscene сообщениях исправлен ELF-патчем в `tools/patch_elf_text_spacing.py`: отрицательное центрирование `(18 - maxLineLen) * 14` теперь clamp-ится к нулю для длинных английских строк.
- Проверено в PCSX2: длинные нижние строки вроде `That feeling right now... What / was it?` и `Kamen Rider, soon we will show / you our true power.` отображаются внутри бокса.
- `HINT.BIN` оказался не DAT-таблицей, а `CSVS` + Shift-JIS string pool. Для него добавлен отдельный builder `tools/hint_bin.py`.
- `stage_rebuilt_text.py` теперь накладывает не только `.DAT`, но и `.BIN`, чтобы `rebuilt_en/DATA/MENU/HINT.BIN` попадал в staging.
- `translation_en/` должен отслеживаться Git, это исходники перевода. Игнорировать нужно build outputs (`rebuilt_en/`, `build/`, `game_dump/`), а не JSON-переводы.
- `external_tools/cvm_tool_02/cvm_tool.exe` проверен: `info`, `split`, `mkcvm` работают без пароля.
- CVM round-trip без изменений побитово совпал с оригиналом:

```text
SHA-256: A65D7104F85AF0034D69FE219330429906810A1A9E63BFDF6DF516D959A2C9BF
```

- `external_tools/mkisofs-md5-2.01/MinGW/Gcc-4.4.5/mkisofs.exe` проверен: запускается, показывает version/help, собирает тестовый ISO.
- `external_tools/mkisofs-md5-2.01/Cygwin/Gcc-3.4.4/mkisofs.exe` выбран для полного PS2 ISO: MinGW-сборка падает на большом `DATA.CVM` с `Implementation botch`.
- `C:\PCSX2 2.3.222\pcsx2-qt.exe` найден.
- `game_dump/DATA/EXPORT_TXD` вынесен в `dump_jp/EXPORT_TXD`, чтобы `game_dump/DATA` хранил чистое дерево игры.
- Root-level `game_dump/DATA/*.TXD` не являются экспортом: они есть в оригинальном CVM и должны оставаться в `game_dump/DATA`.
- В Git уже добавлены wrappers:

```text
tools/stage_rebuilt_text.py
tools/build_data_iso.py
tools/build_data_cvm.py
tools/build_test_iso.py
tools/build_text_smoke_iso.py
tools/run_pcsx2_smoke.py
```

## Внешние сведения

По найденной документации CVM/ROFS фактически является ISO9660 volume со специальным CVM-заголовком. Для него существует `cvm_tool`, который умеет:

```text
cvm_tool split <file.cvm> <file.iso> <file.hdr>
cvm_tool mkcvm <file.cvm> <file.iso> <file.hdr>
```

Вариант с QuickBMS менее надежен для текущей задачи:

- обычный QuickBMS reimport требует, чтобы заменяемые файлы были меньше или равны оригиналам;
- наши smoke-test DAT уже больше оригиналов:

```text
CONFIG_MSG.DAT:    930 -> 1240
ITEM_GET_MSG.DAT: 1566 -> 1942
ITEM_MSG.DAT:     3222 -> 4884
```

- QuickBMS `reimport2` умеет добавлять более крупные файлы в конец архива и обновлять offsets/sizes, но срабатывает не для всех форматов и зависит от BMS-скрипта и устройства TOC.

Вывод: основной путь строить на `cvm_tool` + ISO rebuild. QuickBMS оставить как fallback/диагностику.

## Этап A. Зафиксировать внешние зависимости

Создать локальную папку, не отслеживаемую Git:

```text
external_tools/
```

Ожидаемые инструменты:

```text
external_tools/cvm_tool_02/cvm_tool.exe
external_tools/mkisofs-md5-2.01/MinGW/Gcc-4.4.5/mkisofs.exe
C:/PCSX2 2.3.222/pcsx2-qt.exe
```

Критерии готовности:

- `[done]` `cvm_tool.exe` запускается и показывает help/version;
- `[done]` выбран один инструмент для сборки DATA ISO: MinGW `mkisofs.exe`;
- `[done]` выбран один инструмент для сборки полного PS2 ISO: Cygwin `mkisofs.exe`;
- `[done]` путь к PCSX2 можно задать через `--pcsx2-exe` или `PCSX2_EXE`.

## Этап B. Проверить round-trip CVM без изменений

Цель: убедиться, что `DATA.CVM` можно разобрать и собрать обратно до начала инжекта.

Команды-кандидаты:

```text
cvm_tool split game_dump/DATA.CVM work_cvm/DATA.iso work_cvm/DATA.hdr
cvm_tool mkcvm work_cvm/DATA.roundtrip.CVM work_cvm/DATA.iso work_cvm/DATA.hdr
```

Проверки:

- `[done]` `DATA.roundtrip.CVM` создается без ошибок;
- `[done]` размер и SHA-256 совпадают с оригиналом;
- `[pending]` игра запускается с round-trip CVM, если подставить его в тестовую сборку.

Если `cvm_tool` требует пароль:

- поискать пароль в `SLPS_253.02`;
- проверить, открывает ли `split` файл без `-p`;
- зафиксировать пароль в локальном config, не в Git.

## Этап C. Автоматический staging DAT

Создать скрипт:

```text
tools/stage_rebuilt_text.py
```

Задача скрипта:

```text
game_dump/DATA + rebuilt_en/DATA -> build/stage/DATA
```

Поведение:

1. Создает чистый `build/stage/DATA`.
2. Копирует туда весь `game_dump/DATA`.
3. Накладывает все DAT из `rebuilt_en/DATA` по тем же относительным путям.
4. Печатает список замененных файлов и изменение размера.

Опции:

```text
--source-data game_dump/DATA
--rebuilt-data rebuilt_en/DATA
--output-data build/stage/DATA
--only DATA/MENU/CONFIG_MSG.DAT DATA/MENU/ITEM_GET_MSG.DAT DATA/MENU/ITEM_MSG.DAT
```

Критерии готовности:

- `[done]` smoke-test режим заменяет только 3 MENU DAT;
- `[done]` full режим может заменить все пересобранные `.DAT` и `.BIN`;
- `[done]` оригинальный `game_dump/` не изменяется во время staging.

## Этап C2. HINT.BIN

`DATA/MENU/HINT.BIN` не проходит через DAT encoder. Формат:

```text
CSVS header/table + Shift-JIS string pool + tail payload
```

Скрипт:

```text
tools/hint_bin.py
```

Команды:

```text
python tools/hint_bin.py dump
python tools/hint_bin.py build
```

Особенности:

- pointer values внутри таблицы хранятся как `string_offset - 8`;
- перенос строки в string pool хранится как буквальная последовательность `\n`, не как байт newline;
- builder обновляет pointers и размер `CSVS`, tail после string pool сохраняется;
- вывод builder кладет в `rebuilt_en/DATA/MENU/HINT.BIN`.

Статус:

- `[done]` dump/build для `HINT.BIN` добавлен;
- `[done]` `stage_rebuilt_text.py` умеет staged overlay для `.BIN`;
- `[in progress]` нужна ручная вычитка/укладка hint-текстов.

## Этап D. Пересборка ISO9660 payload для CVM

Нужно получить ISO из `build/stage/DATA`, который затем будет завернут в CVM через `cvm_tool mkcvm`.

Создать wrapper:

```text
tools/build_data_iso.py
```

Задачи:

1. Использовать выбранный ISO builder:

```text
external_tools/mkisofs-md5-2.01/MinGW/Gcc-4.4.5/mkisofs.exe
```

2. Сохранять порядок файлов по возможности близко к оригинальному.
3. Делать `build/stage/DATA.iso`.
4. Логировать команду и итоговый размер.

Подтвержденные параметры оригинального CVM ISO payload:

```text
System id: CRI ROFS
Volume id: SAMPLE_GAME_TITLE
Volume set id: SAMPLE_GAME_TITLE
Publisher id: PUBLISHER_NAME
Data preparer id: PUBLISHER_NAME
NO Joliet present
NO Rock Ridge present
Root contains /DATA
```

Команда-кандидат:

```text
mkisofs.exe
  -iso-level 2
  -l
  -sysid "CRI ROFS"
  -V SAMPLE_GAME_TITLE
  -volset SAMPLE_GAME_TITLE
  -publisher PUBLISHER_NAME
  -p PUBLISHER_NAME
  -graft-points
  -o build/stage/DATA.iso
  DATA=build/stage/DATA
```

Важно: `-iso-level 1` нельзя использовать как основной режим, потому что `mkisofs` массово сокращает длинные имена. `-iso-level 2 -l` все еще может быть недостаточен для некоторых очень длинных экспортных имен, поэтому экспортные артефакты не должны лежать внутри `game_dump/DATA`.

Открытый вопрос:

- насколько критичен порядок файлов внутри `DATA.CVM` для этой игры.
- насколько критично точное сохранение LBA для root/directories после пересборки `mkisofs`.

Минимальная первая проверка:

- собрать ISO с тем же деревом файлов;
- завернуть в CVM;
- запустить в PCSX2.

Если игра не читает данные:

- исследовать оригинальный file order в `DATA.CVM`;
- генерировать sort file для ISO builder;
- проверить LBA/sector alignment.

Статус:

- `[done]` wrapper `tools/build_data_iso.py` создан;
- `[done]` `build/stage/DATA.iso` собран из `build/stage/DATA`;
- `[done]` root payload содержит `/DATA`;
- `[done]` smoke-test DAT имеют ожидаемые размеры в staged tree.

## Этап E. Пересборка DATA.CVM

Создать wrapper:

```text
tools/build_data_cvm.py
```

Команда-кандидат:

```text
cvm_tool mkcvm build/stage/DATA.CVM build/stage/DATA.iso work_cvm/DATA.hdr
```

Поведение:

1. При необходимости сначала делает `split` оригинального `game_dump/DATA.CVM`, чтобы получить `DATA.hdr`.
2. Берет новый `DATA.iso`.
3. Создает `build/stage/DATA.CVM`.
4. Проверяет заголовок `CVMH`/`ROFS`.

Критерии готовности:

- `[done]` wrapper `tools/build_data_cvm.py` создан;
- `[done]` `DATA.CVM` создается автоматически из нового `DATA.iso`;
- `[done]` размер может отличаться от оригинала;
- `[done]` оригинальный `game_dump/DATA.CVM` не изменяется.

## Этап F. Сборка полного PS2 ISO

Создать wrapper:

```text
tools/build_test_iso.py
```

Задача:

```text
game_dump root + build/stage/DATA.CVM -> build/out/kamen_rider_text_smoke.iso
```

Файлы корня диска:

```text
MODULES/
DATA.CVM
MODULES.TRA
OPENING.PSS
PLAY_A.PSS
PLAY_B.PSS
PLAY_C.PSS
PLAY_D.PSS
SLPS_253.02
SYSTEM.CNF
```

Проверки:

- `[done]` `SYSTEM.CNF` указывает на `SLPS_253.02`;
- `[done]` ISO открывается PCSX2 при сборке через `tools/build_patched_iso.py`;
- `[done]` размер ISO разумный: `3,915,173,888` bytes;
- `[done]` root file order в wrapper выставлен по оригиналу из архива.

Актуальная рабочая сборка полного ISO:

```text
tools/build_patched_iso.py
```

Смысл: взять оригинальный ISO как контейнер, заменить внутри него `DATA.CVM`, а при необходимости заменить ELF `SLPS_253.02` на том же месте. Это сохраняет критичную для игры раскладку диска.

## Этап G. Smoke test в PCSX2

Создать wrapper:

```text
tools/run_pcsx2_smoke.py
```

Минимальная задача:

```text
pcsx2-qt.exe -batch build/out/kamen_rider_text_smoke.iso
```

Локальный найденный путь:

```text
C:\PCSX2 2.3.222\pcsx2-qt.exe
```

Wrapper:

```text
python tools/run_pcsx2_smoke.py build/out/kamen_rider_text_smoke.iso
```

Ручная проверка в игре:

- options/config descriptions;
- inventory item names/descriptions;
- item get/use messages.

Фиксировать в отчете:

```text
reports/menu_smoke_test.md
```

Что записывать:

- дата теста;
- имя ISO;
- какие DAT были внедрены;
- запуск/краш;
- видимость английских glyph;
- переполнения окон;
- проблемы переносов строк;
- скриншоты, если есть.

## Этап H. Единая команда

После проверки отдельных шагов создать один командный entrypoint:

```text
tools/build_text_smoke_iso.py
```

Целевая команда:

```text
python tools/build_text_smoke_iso.py --profile menu-smoke --run-pcsx2
```

Pipeline:

```text
encode_all_text.py
hint_bin.py build
stage_rebuilt_text.py
build_data_iso.py
build_data_cvm.py
patch_elf_text_spacing.py
build_patched_iso.py
run_pcsx2_smoke.py
```

Критерии готовности:

- `[done]` одной командой создается тестовый ISO;
- `[done]` `game_dump/` остается read-only source;
- `[done]` все outputs лежат в `build/`;
- `[done]` внешние инструменты задаются через config/env;
- ошибки внешних инструментов выводятся с понятным сообщением.

## Риски

- `[low]` CVM может использовать пароль или нестандартный TOC. Текущий `DATA.CVM` читается без пароля, round-trip совпадает.
- ISO rebuild может нарушить порядок/LBA файлов. Поэтому рабочий путь сейчас не пересобирает root ISO с нуля, а патчит оригинальный ISO.
- Игра может ожидать конкретный размер `DATA.CVM`.
- QuickBMS reimport не подходит как основной путь из-за увеличения DAT.
- PCSX2 CLI может отличаться между версиями.
- `mkisofs` может переименовать файлы при неподходящих ISO options; это уже проявилось на `-iso-level 1`.
- Apostrophe glyph (`'`, `’`, `‘`, `` ` ``) в текущей font map не найден. Encoder сейчас пропускает эти символы, чтобы сборка не падала. Для финального качества лучше переписывать фразы без апострофов или добавить glyph/font mapping отдельно.
- `+` и `%` мапятся на fullwidth fallbacks (`＋`, `％`).
- Японские даты вида `１１月` надо переводить смыслом: `November`, а не `Month 11`.
- Плейсхолдеры вроде `Check this place` нельзя оставлять в `translation_en`; это временный черновик, который должен быть заменен нормальным переводом.

## Памятка сборки

Полная пересборка текущего перевода:

```text
python tools\encode_all_text.py --input-root translation_en --output-root rebuilt_en --wrap-profile game
python tools\hint_bin.py build
python tools\stage_rebuilt_text.py
python tools\build_data_iso.py
python tools\build_data_cvm.py
python tools\patch_elf_text_spacing.py --advance 14
python tools\build_patched_iso.py --patched-elf build/stage/SLPS_253.02 --output-iso build/out/kamen_rider_full_translation.iso
```

Проверка ELF spacing patch внутри итогового ISO:

```text
6041033c
```

Это ожидаемые 4 байта инструкции для `advance 14.0` на текущем месте патча.

Проверка ELF scenario anchor clamp внутри итогового ISO:

```text
232085002a0880000019040023186400231864000b180100000883446008804606080046
```

Это патч `afScenarioMsgKind`: короткие строки центрируются как раньше, а для
строк длиннее 18 glyph отрицательная X-поправка clamp-ится к нулю.

Важно: ELF-only diagnostic ISO с оригинальным `game_dump/DATA.CVM` не содержит
перевода. Для проверки переведенных строк нужен именно full build с новым
`build/stage/DATA.CVM`.

Если нужен быстрый menu smoke:

```text
python tools\build_text_smoke_iso.py --profile menu-smoke --patch-latin-spacing --latin-advance 14
```

## Журнал 2026-05-12

Сделано:

- прочитан внешний tutorial и проверен исходный чистый ISO;
- выяснено, что ранний нерабочий ISO стопорился после `ELF Loading` из-за некорректной сборки/раскладки ISO, а не из-за текста;
- рабочий build path переведен на patch-in-place поверх оригинального ISO;
- меню успешно локализовано сначала через uppercase, затем через lowercase;
- найдена причина больших пробелов между латинскими буквами: fixed X advance `28.0` в `afMsgDrawString`;
- добавлен `tools/patch_elf_text_spacing.py`, рабочий параметр сейчас `--advance 14`;
- добавлен word-wrap английских `text_en` в `tools/encode_all_text.py`;
- текущий wrap возвращен/оставлен на `20`;
- добавлены fallbacks для части ASCII punctuation;
- апострофы временно пропускаются encoder-ом из-за отсутствующего glyph;
- `HINT.BIN` вынесен в отдельный Shift-JIS builder;
- `stage_rebuilt_text.py` расширен на `.BIN`;
- `translation_en/` перестал быть ignored, потому что это исходники перевода.

Текущие открытые проблемы:

- нужна ручная вычитка длинных фраз и переносов;
- часть экранов может требовать отдельной укладки, потому что разные UI используют разные ширины окна;
- `HINT.BIN` и DAT-тексты имеют разные encoding pipeline;
- плейсхолдеры и машинные переводы должны быть вычищены в JSON до финального билда.

## Журнал 2026-05-15

Сделано:

- найдена причина смещения нижнего event/cutscene textbox: в `afScenarioMsgKind`
  игра добавляла к X `(18 - maxLineLen) * 14`, что для длинного английского
  текста становилось отрицательным сдвигом влево;
- `tools/patch_elf_text_spacing.py` расширен: вместе с `--advance 14` он теперь
  патчит scenario centering clamp;
- подтвержден рабочий full build с переводом через `--wrap-profile game`;
- проверено в PCSX2: длинные нижние строки больше не уезжают влево и остаются
  в нужном боксе.

Проверенная сборка:

```text
build/out/kamen_rider_full_translation.iso
iso_size 3915411456
advance_14 6041033c OK
scenario_anchor_clamp 232085002a0880000019040023186400231864000b180100000883446008804606080046 OK
```

## Ближайший следующий шаг

После очередной правки `translation_en` собрать ISO командой из "Памятка сборки" и проверить в PCSX2:

```text
build/out/kamen_rider_full_translation.iso
```

Уже выполненные проверки:

- `[done]` `build/stage/DATA.iso` собран;
- `[done]` root CVM payload содержит `/DATA`;
- `[done]` `DATA/MENU/CONFIG_MSG.DAT`, `ITEM_GET_MSG.DAT`, `ITEM_MSG.DAT` имеют smoke-test размеры;
- `[done]` `build/stage/DATA.CVM` читается через `cvm_tool info`;
- `[done]` `DATA.CVM` начинается с `CVMH` и содержит `ROFS`;
- `[done]` `build/out/kamen_rider_text_smoke.iso` собран и открывается `isoinfo`.

## Definition of Done

Блок считается завершенным, когда:

- есть документированный способ получить `DATA.hdr` из оригинального `DATA.CVM`;
- CVM round-trip без изменений запускается в PCSX2;
- smoke-test DAT автоматически накладываются в staging tree;
- автоматически создается новый `DATA.CVM`;
- автоматически создается новый PS2 ISO;
- ISO запускается в PCSX2;
- `reports/menu_smoke_test.md` содержит результаты первого теста.
