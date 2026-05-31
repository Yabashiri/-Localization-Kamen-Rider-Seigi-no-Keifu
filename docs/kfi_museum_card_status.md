# KFI museum card status, 2026-05-31

## Update, 2026-05-31

- Test body-only import is active for the pilot card:
  - `rebuilt_en/DATA/KFI_KIJIN_36.RSC` exists.
  - Only `tex_kfi_tx_3600a` and `tex_kfi_tx_3600b` pixel payloads were changed.
  - Binary check after import found no byte differences outside those two expected 256x256 payload spans.
- `KFI_NA_TEX.RSC` is still not imported into `rebuilt_en`; the shared museum name/index atlas remains untouched.
- A new test ISO was built for in-game inspection:
  - `build/out/kamen_rider_full_translation.iso`
  - size: `3915409408`
  - proportional jump bytes verified: `943b0d0800000000`
- Current visual expectation:
  - detail body text should appear on the `KFI_KIJIN_36` page;
  - detail title and museum index names remain original Japanese because the shared title/index atlas is deliberately untouched;
  - if the body area still shows a gray block or ghost text in game, the next fix should stay inside `tex_kfi_tx_3600a/b` alpha/index handling, not `KFI_NA_TEX.RSC`.

## In-game feedback iteration, 2026-05-31

- First in-game check showed:
  - `tex_kfi_tx_3600b` behaved mostly like a transparent overlay, but its text fill was too weak/gray.
  - `tex_kfi_tx_3600a` rendered empty index `0` as a black rectangle in game.
  - The title/index remained original Japanese as intended.
- Generator changed in `tools/kfi_museum_pilot.py`:
  - `tex_kfi_tx_3600a` now starts from the original texture and clears text pixels to paper index `202`, not transparent index `0`.
  - `tex_kfi_tx_3600a` text uses fixed fill/stroke indices `48`/`251`.
  - `tex_kfi_tx_3600b` text uses fixed fill/stroke indices `161`/`253`.
- Rebuilt and re-imported `rebuilt_en/DATA/KFI_KIJIN_36.RSC`.
- Binary check after the new import still shows no byte differences outside the two expected texture payload spans.
- A new test ISO was rebuilt at `build/out/kamen_rider_full_translation.iso`.
  - size: `3915409408`
  - proportional jump bytes verified: `943b0d0800000000`

## Iteration 3, 2026-05-31

- User requested future test ISOs to use separate names instead of overwriting `kamen_rider_full_translation.iso`.
- `tools/kfi_museum_pilot.py` changed again:
  - `tex_kfi_tx_3600b` fill index changed from pure black `161` to dark nonzero `185`, because pure black still vanished in game on the left material.
  - red artifact pixels inside the `tex_kfi_tx_3600a` mini-shot are remapped to nearest neutral opaque palette indices.
- Local check after generation:
  - red pixels in the `tex_kfi_tx_3600a` mini-shot: `0`.
  - `tex_kfi_tx_3600b` uses index `185` for fill and `253` for stroke.
  - rebuilt `KFI_KIJIN_36.RSC` still differs only inside the two expected texture payload spans.
- Separate test ISO:
  - `build/out/kamen_rider_museum_kfi36_iter3.iso`
  - size: `3915409408`
  - proportional jump bytes verified: `943b0d0800000000`

## Iteration 4, 2026-05-31

- In-game check of iter3 still showed:
  - red/warm lines in the mini-shot;
  - left `tex_kfi_tx_3600b` text not dark enough.
- `tools/kfi_museum_pilot.py` changed again:
  - `tex_kfi_tx_3600b` fill index changed from `185` to darker nonzero index `174`.
  - mini-shot cleanup now excludes warm replacement candidates too, not only bright red candidates.
- Local check after generation:
  - warm/red pixels in the `tex_kfi_tx_3600a` mini-shot: `0`.
  - rebuilt `KFI_KIJIN_36.RSC` still differs only inside the two expected texture payload spans.
- Separate test ISO:
  - `build/out/kamen_rider_museum_kfi36_iter4.iso`
  - size: `3915409408`
  - proportional jump bytes verified: `943b0d0800000000`

## Stable test ISO update, 2026-05-31

- User asked to stop accumulating numbered ISO files.
- Future museum-card test builds should overwrite:
  - `build/out/kamen_rider_museum_kfi36_test.iso`
- Iter4 was worse in game:
  - `tex_kfi_tx_3600b` fill index `174` looked worse, so it was reverted to `185`.
  - red artifacts persisted because `tex_kfi_tx_3600a` appears to render low-alpha palette indices as visible color in game.
- `tools/kfi_museum_pilot.py` now treats the mini-shot as effectively opaque:
  - every low-alpha, red, or warm pixel inside `SHOT_RECT` is remapped to an opaque neutral palette index.
- Local check after generation:
  - mini-shot warm pixels: `0`.
  - mini-shot low-alpha pixels: `0`.
  - rebuilt `KFI_KIJIN_36.RSC` still differs only inside the two expected texture payload spans.
- Stable test ISO:
  - `build/out/kamen_rider_museum_kfi36_test.iso`
  - size: `3915409408`
  - proportional jump bytes verified: `943b0d0800000000`

## Best-known variant restored, 2026-05-31

- User identified the best in-game variant as the first post-black-rectangle fix:
  - `tex_kfi_tx_3600a` starts from the original texture and clears old text to paper index `202`.
  - `tex_kfi_tx_3600b` fill index is the original black index `161`.
  - `KFI_NA_TEX.RSC` remains untouched.
- `tools/kfi_museum_pilot.py` and `rebuilt_en/DATA/KFI_KIJIN_36.RSC` were restored to that variant.
- No new final ISO was built for this restore. Keep using this as the baseline for the next explicit test build.

## Current WIP candidate, 2026-05-31

- This candidate was built into the stable test ISO:
  - `build/out/kamen_rider_museum_kfi36_test.iso`
  - size: `3915409408`
  - proportional jump bytes verified: `943b0d0800000000`
- File-level analysis of `KFI_TX_3600.dff` found:
  - the mini-shot is entirely inside `tex_kfi_tx_3600a`;
  - the visible left text strip is only `tex_kfi_tx_3600b` UV `0.5..71.5`.
- `tools/kfi_museum_pilot.py` no longer edits the mini-shot pixels:
  - local source check against the original `tex_kfi_tx_3600a` reports `shot_changed_pixels 0`;
  - in game the mini-shot still contains visible red pixels, so this is not solved yet.
- Left `tex_kfi_tx_3600b` text now uses the original visible-strip black ink:
  - fill index `162`;
  - stroke index remains `253`;
  - no `185`/`161` dither pattern.
- `rebuilt_en/DATA/KFI_KIJIN_36.RSC` was regenerated/imported for this WIP candidate.
- Binary check still shows no byte differences outside the two expected texture payload spans.
- In-game check of `build/out/kamen_rider_museum_kfi36_test.iso` showed this is the current best-progress variant, not final:
  - right mini-shot still has red pixels and needs a proper palette/render-state investigation;
  - left-side text is much closer to black/readable, but still does not fully match the main text color;
  - body layout is acceptable and close to final.
- Remaining deliberate limitation:
  - title/header and museum index names are still original Japanese because `KFI_NA_TEX.RSC` remains untouched.

## Previous checkpoint, 2026-05-30

Задача остановлена по просьбе пользователя. Дальше не импортировать карточку в игру и не собирать ISO, пока не будет нормального превью из игровых ассетов.

## Состояние игры на 2026-05-30

- Активной подмены музейной карточки сейчас нет:
  - `rebuilt_en/DATA/KFI_KIJIN_36.RSC` отсутствует.
  - `rebuilt_en/DATA/KFI_NA_TEX.RSC` отсутствует.
  - `build/out/kamen_rider_full_translation.iso` отсутствует.
- Значит текущие эксперименты с музейной записью находятся в инструментах/превью, а не в готовой сборке игры.
- Важное правило для следующей попытки: индекс/лист названий не трогать. Пользователь явно попросил не менять индекс.

## Что уже найдено по ассетам

- Пилотная запись: `game_dump/DATA/KFI_KIJIN_36.RSC`.
- Это карточка `ショッカー戦闘員(骨・覆面タイプ)`.
- Внутри `KFI_KIJIN_36.RSC` есть несколько встроенных TXD/DFF:
  - `KFI_CH_3600.dff` + `tex_kfi_ch_3600a/b`: персонаж.
  - `KFI_SH_3600.dff` + `tex_kfi_sh_3600a/b`: силуэт/тень.
  - `KFI_TX_3600.dff` + `tex_kfi_tx_3600a/b`: текстовая часть карточки и внутриигровая мини-картинка.
- Текстовая карточка разделена на два материала:
  - `tex_kfi_tx_3600b`: левая полоса, примерно экранные `x=288..359`, `y=119..375`.
  - `tex_kfi_tx_3600a`: основная часть, примерно экранные `x=359..615`, `y=119..375`.
- Заголовок записи берется не из `KFI_KIJIN_36.RSC`, а из общего `game_dump/DATA/KFI_NA_TEX.RSC` через `KFI_NA_3600.dff`.
- Индекс и заголовок используют общий атлас `KFI_NA_TEX.RSC` / `tex_kfi_na_005`, поэтому замена этого атласа ломает индекс. Пока этот файл не трогать.
- Фон, `INDEX`, стрелки и кнопки лежат в `KFI_BG_TEX.RSC` / `KFI_BG_DFF.RSC`.
  - Основной фон: `KFI_BG_0100.dff`.
  - Нижний `INDEX`: вероятно `KFI_BG_1300.dff` или `KFI_BG_1400.dff`.
  - Стрелки: `KFI_BG_0900..1200.dff`.
  - Линия/EXIT/сетка индекса тоже в `KFI_BG_0300..0800.dff`.

## Что сделано по превью

- Добавлен черновой инструмент `tools/kfi_asset_preview.py`.
- Он умеет:
  - читать встроенные TXD из RSC;
  - декодировать 8bpp PS2 texture + CLUT;
  - парсить DFF geometry/material/UV;
  - собирать страницу `KFI_KIJIN_36` из игровых ассетов;
  - опционально подставлять английскую текстуру, но это сейчас не использовать.
- Последний сгенерированный оригинальный превью-файл:
  - `build/museum_pilot_preview/asset_pipeline/kfi36_assets_original.png`
- Дополнительная диагностика:
  - `build/museum_pilot_preview/asset_pipeline/tx3600_raw_alpha_contact.png`
  - `build/museum_pilot_preview/kfi_bg_contact_sheet.png`

## Проблемы текущего превью

- Текущий рендерер DFF еще не идеален.
- Сначала он игнорировал frame matrix и поэтому рендерил персонажа/текст, но с сомнительным позиционированием.
- Потом была добавлена попытка учитывать полную frame matrix. После этого часть detail-ассетов ушла в отрицательные X-координаты, и текущий `kfi36_assets_original.png` может показывать только фон.
- Причина: у detail-ассетов есть родительская matrix с отражением по X. Для таких моделей экранная координата, судя по расчетам, должна считаться как `screen_x = -world_x * 10`, а для основного фона `KFI_BG_0100` остается `screen_x = world_x * 10`.
- Нужно доделать не импорт, а именно preview renderer: он должен корректно применять frame transform и потом выбирать правильную экранную проекцию для mirrored/non-mirrored DFF.
- Цвета тоже пока не финальные:
  - некоторые KFI-текстуры хранят темные линии как красноватые CLUT-цвета;
  - в игре они выглядят как серо-оливковые/черные через render state;
  - прямой RGBA dump дает красные точки и грязь, поэтому нужен нормальный preview color pipeline.
- Для `KFI_NA_TEX` отдельная странность: часть видимых пикселей имеет alpha `0`, но в игре видна. Для превью заголовка нужен forced opaque или более точная модель alpha test/blend.
- `KFI_SH_3600` может давать лишний контур вокруг персонажа. Нужно проверить, действительно ли этот слой виден на detail page, или его надо отключить/иначе смешивать.

## Что было не так в игре на скринах

- На скрине индекса были сломаны японские названия. Это произошло из-за замены `KFI_NA_TEX.RSC`.
  - Этот атлас общий для списка/индекса и заголовка detail page.
  - Поэтому даже попытка заменить только заголовок записи может портить список.
  - Исправление: не импортировать `KFI_NA_TEX.RSC`, пока нет отдельной стратегии для заголовков.
- На detail page английский текст появился как большой серый прямоугольник.
  - Это почти наверняка неправильная обработка alpha/palette у `tex_kfi_tx_3600a/b`.
  - Оригинальная текстовая область не является простым непрозрачным прямоугольником; она смешивается с фоном страницы.
  - Надо сохранять исходные alpha/CLUT-индексы фона и менять только пиксели текста, либо строго маппить новые пиксели в существующую палитру.
- Был виден ghost/дублирование текста со сдвигом.
  - Вероятная причина: две текстуры `3600a` и `3600b` были сгенерированы/импортированы не как точные UV-crop части одной страницы.
  - Нужно генерировать одну полную экранную раскладку, а потом нарезать ее ровно по DFF UV/material mapping для `a` и `b`.
- Красные точки/грязные цвета на превью и потенциально в игре связаны с CLUT/render state.
  - Нельзя оценивать результат только по сырому RGBA dump.
  - Но перед импортом нужен превью-рендер, который хотя бы приближенно имитирует внутриигровое смешивание.

## Что попробовать дальше

1. Довести `tools/kfi_asset_preview.py` до хорошего оригинального превью без локализации.
   - Сначала исправить screen projection для mirrored detail DFF.
   - Потом добавить нижние `INDEX`/стрелки через `KFI_BG_0900..1400`.
   - Потом решить, нужен ли `KFI_SH_3600` на detail page.
2. Сделать preview color pipeline.
   - Не использовать скрин как источник ассетов.
   - Скрин использовать только для визуального сравнения.
   - Для UI/бумаги нормализовать красноватые CLUT-линии в нейтральный темный цвет.
   - Для текстовой карточки проверить, какие palette indices отвечают за бумагу, тень, контур и основной текст.
3. После хорошего оригинала вернуться к локализации только body-текстуры.
   - Не трогать `KFI_NA_TEX.RSC`.
   - Работать только с `KFI_KIJIN_36.RSC` и только `tex_kfi_tx_3600a/b`.
   - Сохранять оригинальную мини-картинку.
   - Сохранять оригинальную палитру/alpha, новые буквы маппить в существующие темные индексы.
4. Перед импортом в игру каждый раз делать три проверки:
   - asset preview из RSC до импорта;
   - asset preview из RSC после импорта;
   - только потом сборка ISO и проверка в эмуляторе.

## Рабочие файлы на 2026-05-30

- `tools/kfi_asset_preview.py`: новый черновой asset-preview renderer.
- `tools/kfi_museum_pilot.py`: старый генератор английских текстур/вариантов.
- `tools/rsc_txd_import.py`: черновой импортер PNG в TXD/RSC.
- `tools/kfi_museum_isolated_preview.py`: вспомогательное превью.
- `tools/stage_rebuilt_text.py`: уже был изменен ранее в ходе пайплайна.

Ничего из текущей музейной карточки сейчас не считать готовым к коммиту или импорту.
