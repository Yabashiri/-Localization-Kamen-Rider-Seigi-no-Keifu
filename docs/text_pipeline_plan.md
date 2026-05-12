# Следующий этап локализации: чистый японский дамп и DAT round-trip

## Контекст

Проект: PS2 `Kamen Rider - Seigi no Keifu (Japan)`.
Цель локализации: английский перевод.
Кириллица не нужна.

Рабочий hybrid font mapping уже реализован и проверен:

```text
0x0000..0x00ff -> прямая page 0 из game_dump/DATA/FONT.TXT
0x0100..0x0dxx -> page * 0x100 + local_index из game_dump/DATA/EXPORT_TXD/FONT_data.json
```

Готово:

```text
tools/font_mapping.py
tools/make_font_map.py
tools/audit_font_usage.py
localization/font_maps/font_map.generated.json
localization/font_maps/font_map_corrected.json
reports/font_usage.tsv
reports/font_map_corrections.md
```

Последний аудит:

```text
DAT-like files: 249
Used glyph codes: 832
Control codes:
  0x8000 = END
  0x8100 = newline
Missing glyph codes: 0
Entries with unknown glyphs: 0
```

`font_map_corrected.json` является рабочей таблицей `code -> char`.
`game_dump/` не отслеживается Git и не должен попадать в репозиторий.

## Цель ближайшего этапа

Получить надежный pipeline:

```text
DAT -> японский JSON dump -> rebuilt DAT
```

Перед английским переводом нужно:

- создать чистый японский dump;
- реализовать encoder;
- проверить round-trip на оригинальном японском тексте.

Статус на 2026-05-12: этапы 4-5 выполнены.

- `tools/dump_all_text.py` дампит 249 DAT-like файлов в `dump_jp/DATA/...`.
- `tools/encode_all_text.py` собирает 249 файлов в `rebuilt_jp/DATA/...`.
- Проверка `DAT -> JSON -> DAT` дала 0 бинарных отличий относительно `game_dump/DATA`.
- В dump нет unknown glyph markers вида `[0x....]`.
- Для точного японского round-trip JSON содержит служебное поле `codes`; при заполненном `text_en` encoder кодирует перевод из текста.

## Этап 4. Создать чистый японский dump

### Задачи

Создать скрипт:

```text
tools/dump_all_text.py
```

Он должен:

1. Использовать `font_map_corrected.json` через `tools/font_mapping.py`.
2. Рекурсивно находить все DAT-like файлы тем же способом, что `audit_font_usage.py`.
3. Декодировать entries с control codes:

```text
0x8000 -> {END}
0x8100 -> \n
```

4. Дампить результат в:

```text
dump_jp/
```

с сохранением относительной структуры:

```text
dump_jp/
  DATA/MENU/ITEM_MSG.json
  DATA/MENU/CONFIG_MSG.json
  DATA/SCREVENT/MSG/EV001.json
```

Рекомендуемый формат JSON:

```json
[
  {
    "idx": 1,
    "text_jp": "『レバー』\n２つのでっぱりがついているレバー",
    "text_en": ""
  }
]
```

### Критерии готовности

- Все 249 DAT-like файлов дампятся.
- В дампе нет `[0x....]` для обычных glyph-кодов.
- `{END}` либо сохранен явно, либо корректно восстанавливается encoder-ом.
- `dump_jp/` добавлен в `.gitignore`, кроме `.gitkeep`, если dump не планируется коммитить.

## Этап 5. Round-trip encoder без перевода

### Задачи

Создать encoder:

```text
tools/encode_all_text.py
```

Он должен:

1. Читать JSON из `dump_jp/`.
2. Использовать reverse map из `font_map_corrected.json`.
3. Кодировать строки обратно в DAT-формат:

```text
u32 count

entry table:
  u16 idx
  u16 length
  u32 offset

string data:
  u16 code...
```

4. Поддерживать:

```text
\n -> 0x8100
{END} -> 0x8000
```

5. При отсутствии `{END}` в JSON либо добавлять его автоматически, либо строго валидировать формат. Лучше выбрать один режим и явно задокументировать.

6. Писать rebuilt DAT в отдельную папку, например:

```text
rebuilt_jp/
```

не изменяя `game_dump/`.

### Критерии готовности

- `DAT -> JSON -> DAT` работает для всех 249 файлов.
- Желательно: rebuilt DAT бинарно идентичны оригиналам.
- Если бинарная идентичность невозможна из-за пересборки offset/string area, различия должны быть объяснимы и семантически эквивалентны.
- Нет unknown chars при обратном кодировании.

## Этап 6. Подготовить английский translation dump

### Задачи

Создать рабочую папку:

```text
translation_en/
```

Формат записей:

```json
{
  "idx": 1,
  "text_jp": "『レバー』\n２つのでっぱりがついているレバー",
  "text_en": "Lever\nA lever with two protrusions."
}
```

Нужно сохранить:

- `idx`;
- порядок строк;
- переносы;
- управляющие токены;
- японский оригинал как reference.

### Английский шрифт

Для первого прототипа использовать существующие fullwidth latin glyphs:

```text
ＡＢＣ...Ｚ
ａｂｃ...ｚ
０１２３４５６７８９
```

Encoder может автоматически конвертировать ASCII в fullwidth:

```text
A -> Ａ
B -> Ｂ
0 -> ０
space -> fullwidth space or mapped space
```

Отдельно проверить доступность знаков:

```text
.,!?':-()/
```

Если символов нет:

- заменить на доступные аналоги;
- или позже добавить/перерисовать glyph.

## Этап 7. Тестовая вставка английского текста

### Задачи

Для первого теста перевести 2-3 небольших файла:

```text
DATA/MENU/CONFIG_MSG.DAT
DATA/SCREVENT/MSG/DOOR_CLOSE.DAT
DATA/SCREVENT/MSG/EV001.DAT
```

Собрать их обратно в отдельный output и проверить в игре/PCSX2.

### Что проверять

- игра не крашится;
- текст отображается;
- английские символы видны корректно;
- переносы строк работают;
- окна не переполняются критически;
- `{END}` и `0x8100` корректно обрабатываются.

## Этап 8. После DAT pipeline

Только после успешного текстового pipeline переходить к остальному:

1. Графический текст в `.TXD` / `.RSC`.
2. Меню и telop-текстуры:

```text
DATA/MENU/TELOP_*.TXD
DATA/MENU/SUB_*.RSC
DATA/MENU/OPT_*.RSC
DATA/EXPORT_TXD/MENU/
```

3. Видео `.PSS`, если в них есть вшитые японские титры.
4. Проверка упаковки обратно в `DATA.CVM` / ISO.

## Definition of Done для ближайшего блока

Блок считается завершенным, когда:

- есть `tools/dump_all_text.py`;
- есть чистый японский dump в `dump_jp/`;
- есть `tools/encode_all_text.py`;
- round-trip `DAT -> JSON -> DAT` работает для всех 249 DAT-like файлов;
- rebuilt output не меняет `game_dump/`;
- можно безопасно начинать английский перевод.
