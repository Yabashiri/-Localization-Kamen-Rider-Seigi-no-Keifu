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
external_tools/cvm_tool/cvm_tool.exe
external_tools/iso/mkisofs.exe или external_tools/iso/ImgBurn/...
external_tools/pcsx2/pcsx2-qt.exe
```

Критерии готовности:

- `cvm_tool.exe` запускается и показывает help/version;
- выбран один инструмент для сборки PS2 ISO;
- путь к PCSX2 можно задать через config/env.

## Этап B. Проверить round-trip CVM без изменений

Цель: убедиться, что `DATA.CVM` можно разобрать и собрать обратно до начала инжекта.

Команды-кандидаты:

```text
cvm_tool split game_dump/DATA.CVM work_cvm/DATA.iso work_cvm/DATA.hdr
cvm_tool mkcvm work_cvm/DATA.roundtrip.CVM work_cvm/DATA.iso work_cvm/DATA.hdr
```

Проверки:

- `DATA.roundtrip.CVM` создается без ошибок;
- размер и заголовок выглядят ожидаемо;
- игра запускается с round-trip CVM, если подставить его в тестовую сборку.

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

- smoke-test режим заменяет только 3 MENU DAT;
- full режим может заменить все пересобранные DAT;
- оригинальный `game_dump/` не изменяется.

## Этап D. Пересборка ISO9660 payload для CVM

Нужно получить ISO из `build/stage/DATA`, который затем будет завернут в CVM через `cvm_tool mkcvm`.

Создать wrapper:

```text
tools/build_data_iso.py
```

Задачи:

1. Использовать выбранный ISO builder.
2. Сохранять порядок файлов по возможности близко к оригинальному.
3. Делать `build/stage/DATA.iso`.
4. Логировать команду и итоговый размер.

Открытый вопрос:

- насколько критичен порядок файлов внутри `DATA.CVM` для этой игры.

Минимальная первая проверка:

- собрать ISO с тем же деревом файлов;
- завернуть в CVM;
- запустить в PCSX2.

Если игра не читает данные:

- исследовать оригинальный file order в `DATA.CVM`;
- генерировать sort file для ISO builder;
- проверить LBA/sector alignment.

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

- `DATA.CVM` создается автоматически;
- размер может отличаться от оригинала;
- оригинальный `game_dump/DATA.CVM` не изменяется.

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
DATA.CVM
MODULES/
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

- `SYSTEM.CNF` указывает на `SLPS_253.02`;
- ISO открывается PCSX2;
- размер ISO разумный;
- root file order при необходимости повторяет оригинал.

## Этап G. Smoke test в PCSX2

Создать wrapper:

```text
tools/run_pcsx2_smoke.py
```

Минимальная задача:

```text
pcsx2-qt.exe -batch build/out/kamen_rider_text_smoke.iso
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
stage_rebuilt_text.py
build_data_iso.py
build_data_cvm.py
build_test_iso.py
run_pcsx2_smoke.py
```

Критерии готовности:

- одной командой создается тестовый ISO;
- `game_dump/` остается read-only source;
- все outputs лежат в `build/`;
- внешние инструменты задаются через config/env;
- ошибки внешних инструментов выводятся с понятным сообщением.

## Риски

- CVM может использовать пароль или нестандартный TOC.
- ISO rebuild может нарушить порядок/LBA файлов.
- Игра может ожидать конкретный размер `DATA.CVM`.
- QuickBMS reimport не подходит как основной путь из-за увеличения DAT.
- PCSX2 CLI может отличаться между версиями.

## Definition of Done

Блок считается завершенным, когда:

- есть документированный способ получить `DATA.hdr` из оригинального `DATA.CVM`;
- CVM round-trip без изменений запускается в PCSX2;
- smoke-test DAT автоматически накладываются в staging tree;
- автоматически создается новый `DATA.CVM`;
- автоматически создается новый PS2 ISO;
- ISO запускается в PCSX2;
- `reports/menu_smoke_test.md` содержит результаты первого теста.
