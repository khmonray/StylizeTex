# Stylized Texture Processor

Дополнение Blender читает изображение Base Color активного материала активного UV-развёрнутого меша, обрабатывает его, сохраняет новый PNG и по умолчанию подключает созданное изображение к материалу. Исходное изображение, исходный узел, а также не связанные с ним узлы и связи материала сохраняются. Эта документация описывает реализацию, существующую в репозитории; конкретное визуальное качество не гарантируется.

Автор: github.com/khmonray

## Реализованный объём: Phase 1 и Phase 2

Реализованный конвейер:

```text
Input image
    ↓
Scene-linear → sRGB conversion
    ↓
Micro Detail smoothing (Phase 2; skipped at 1.0)
    ↓
Color Simplification
    ↓
Hue Variation (Phase 2; skipped at 0.0)
    ↓
Painterly Variation (Phase 2; skipped at 0.0)
    ↓
Smooth low-frequency variation
    ↓
Contrast
    ↓
Saturation
    ↓
sRGB → scene-linear conversion
    ↓
New image + PNG
```

Phase 2 добавляет `Hue Variation`, `Brush Scale`, `Paint Variation` и `Micro Detail`. Нейтральные значения по умолчанию побитово сохраняют результат Phase 1: `hue_variation=0.0`, `paint_variation=0.0` и `micro_detail=1.0`. `Brush Scale` используется Painterly Variation и не влияет на результат, пока `Paint Variation` равен нулю.

Оператор создаёт новый блок данных изображения Blender и всегда записывает внешний PNG. По умолчанию он сразу подключает созданное изображение ко входу **Base Color** Principled BSDF активного материала. Исходные изображение и узел сохраняются; изменяется только эта связь Base Color.

Не реализованы: функции материалов Phase 3 (roughness, AO, curvature и генерация материала) и функции UX Phase 4 (preview, пресеты и пакетная обработка). Также не реализованы маски, затенение с учётом геометрии и экспорт GLB.

## Поддерживаемые версии Blender

- Тестовой версией Blender в репозитории является **5.2.1**.
- Текущие `bl_info` и `blender_manifest.toml` объявляют минимум **4.2.0**. Версии ниже 4.2 и версии, отличные от проверенной цели, не верифицированы.
- Манифест extension требует Blender 4.2 или новее. Классический legacy-путь установки — отдельный.

## Установка

### Legacy add-on ZIP

Используйте `build/stylized_texture_addon-legacy.zip`. Архив содержит корневую папку `stylized_texture_addon/` и литеральные метаданные `bl_info`, используемые классической системой add-on Blender.

1. В Blender откройте **Edit > Preferences > Add-ons**.
2. Нажмите **Install...** и выберите `stylized_texture_addon-legacy.zip`.
3. Включите **Stylized Texture Processor**.

### Blender extension ZIP

Используйте `build/stylized_texture_addon-extension.zip`. В корне этого архива находится `blender_manifest.toml`; архив предназначен для workflow extensions Blender.

Установите его через интерфейс Blender **Preferences > Get Extensions**, используя установку с диска, либо примените команды extension, соответствующие установленной версии Blender. Не устанавливайте extension-архив как классический add-on, если Blender ожидает пакет extension.

Скрипт упаковки использует команду Blender `extension build`, когда исполняемый файл Blender доступен; иначе он создаёт ручной ZIP с теми же файлами пакета.

## Интерфейс и использование

После включения дополнения откройте боковую панель 3D Viewport клавишей `N` и выберите вкладку **Stylized Texture**. Панель зарегистрирована в `View3D > Sidebar > Stylized Texture`.

Панель сгруппирована следующим образом:

- **Source**: активный объект и обнаруженное изображение Base Color.
- **Output**: `Resolution`, `Output Folder`, `Apply to Material` (по умолчанию `True`) и `Pack into .blend` (по умолчанию `False`).
- **Style / Color**: упрощение цвета, число цветовых уровней, контраст и насыщенность.
- **Style / Large Scale**: сила и масштаб вариации.
- **Style / Painterly**: масштаб мазка, вариация рисования, микродетали и вариация оттенка.
- **Style / Seed**: общий seed.
- Действия: **Process Texture**, **Randomize Style** и **Reset**. Если результат уже сохранялся, ниже действий показывается его последний путь.

Необходимый вход для **Process Texture**:

1. Работайте в Object Mode.
2. Выберите объект-меш с активной UV-картой.
3. Убедитесь, что у него есть активный материал.
4. В активном материале используйте узловой Principled BSDF, подключённый к активному Material Output.
5. Подключите узел **Image Texture** напрямую ко входу **Base Color** Principled BSDF.
6. Задайте параметры вывода и обработки на панели.
7. Нажмите **Process Texture**.

Валидатор принимает только прямую связь Image Texture → Principled BSDF Base Color. Он не ищет текстуру через color nodes, группы, mix-узлы или другие shader networks. Если после предыдущего запуска подключён созданный узел, обработка раскрывает его и читает сохранённый исходный источник, а не подаёт созданный результат обратно в конвейер. Оператор также проверяет папку вывода и показывает в интерфейсе ошибки пути или прав доступа; неожиданные исключения выводятся в Blender Console.

### Randomize Style

**Randomize Style** выбирает новое случайное seed операционной системы, отличное от текущего, а затем получает из этого seed ограниченный набор параметров стиля. Изменяется только whitelist стиля: `Color Steps`, `Color Simplification`, `Variation Strength`, `Variation Scale`, `Contrast`, `Saturation`, `Seed`, `Hue Variation`, `Brush Scale`, `Paint Variation` и `Micro Detail`. `Resolution`, `Output Folder` и последний путь результата сцены сохраняются.

Действие не обрабатывает изображение, не создаёт изображения или материалы Blender, не выполняет файловый ввод-вывод и не требует выбранного меша. Оно только меняет настройки; для создания результата отдельно нажмите **Process Texture**. Чистый randomizer детерминирован для заданного seed, а кнопка получает новый seed при каждом вызове.

### Применение и упаковка результата

При включённом **Apply to Material** (значение по умолчанию) обработка сразу подключает созданное изображение через один помеченный узел **Image Texture** ко входу **Base Color** Principled BSDF активного материала. Существующие исходные узел Image Texture и изображение сохраняются; изменяется только связь Base Color. Остальные узлы и связи не изменяются.

Повторная обработка использует тот же помеченный созданный узел и заменяет его созданное изображение, продолжая читать исходный источник. Созданные узлы не накапливаются, и предыдущий результат не подаётся обратно в обработку.

Отключите **Apply to Material**, чтобы оставить активный материал без изменений. Новый блок данных изображения и внешний PNG всё равно создаются, но созданное изображение не подключается.

Включите **Pack into .blend**, чтобы упаковать созданное изображение дополнительно к записи внешнего PNG; внешний файл создаётся всегда. Упаковка не сохраняет `.blend` автоматически. Сохраните `.blend` вручную, чтобы сохранить связь материала и упакованное изображение. Упаковка работает и для несохранённого blend; статус напоминает о необходимости сохранения.

## Поведение вывода

Результат — новое изображение и внешний PNG. Имя по умолчанию: `<object>_stylized_basecolor.png`; имена объектов очищаются для использования в файловой системе. Явный путь файла оператора имеет приоритет над настройкой папки вывода.

Если **Output Folder** пуст, дополнение последовательно использует папку исходного изображения, папку файла `.blend`, а затем временную папку Blender. Последний fallback используется для несохранённого blend, если пригодной папки исходного изображения нет. Существующий файл может быть перезаписан при совпадении вычисленного имени; уникальный суффикс к имени на диске не добавляется. Некорректный, недоступный или недоступный для записи путь отменяет обработку и вызывает ошибку. При каждом запуске создаётся новый блок данных изображения; при включённом применении он заменяет предыдущий созданный результат в материале, а исходное изображение и несвязанные данные материала сохраняются.

### Разрешение и соотношение сторон

Интерфейс предлагает `512`, `1024`, `2048` и `4096`. Выбранное значение — длина **наибольшей стороны**, а не принудительный размер квадратного изображения. Вторая сторона масштабируется пропорционально и округляется минимум до одного пикселя с помощью билинейной интерполяции. Например, источник 1024×512 при цели 2048 станет 2048×1024; квадратный источник останется квадратным.

## Параметры

| Параметр | По умолчанию | Диапазон / варианты | Эффект |
| --- | ---: | --- | --- |
| Resolution | 2048 | 512, 1024, 2048, 4096 | Длина большей стороны; соотношение сторон сохраняется. |
| Output Folder | пусто | Путь к папке | Папка PNG; пусто использует описанную выше цепочку fallback. |
| Apply to Material | True | Логическое значение | Сразу подключает созданное изображение к Base Color; при False материал сохраняется без изменений. |
| Pack into .blend | False | Логическое значение | Упаковывает созданное изображение дополнительно к внешнему PNG; blend автоматически не сохраняется. |
| Color Steps | 8 | 2–32 | Число тональных групп для упрощения цвета. |
| Color Simplification | 0.70 | 0.0–1.0 | Сила упрощения цвета. |
| Variation Strength | 0.25 | 0.0–1.0 | Сила плавной низкочастотной вариации цвета. |
| Variation Scale | 0.15 | 0.01–1.0 | Относительный размер низкочастотных цветовых пятен. |
| Contrast | 1.05 | 0.0–3.0 | Множитель контраста относительно среднего серого. |
| Saturation | 0.90 | 0.0–3.0 | Множитель насыщенности. |
| Seed | 12345 | 0–2147483647 | Общий seed для детерминированной процедурной вариации. |
| Hue Variation | 0.0 | 0.0–1.0 | Ограниченное изменение оттенка цветных областей; нейтрально при 0.0. |
| Brush Scale | 0.15 | 0.01–1.0 | Относительный размер мазков; используется Painterly Variation. |
| Paint Variation | 0.0 | 0.0–1.0 | Вариация яркости, насыщенности и оттенка; нейтральна при 0.0. |
| Micro Detail | 1.0 | 0.0–1.0 | Доля сохраняемых мелких деталей; 1.0 — нейтральное значение/полная детализация, 0.0 — максимальное сглаживание. |

Нейтральные значения Phase 2 специально совместимы с Phase 1. Значения из старых или частичных объектов настроек синхронизируются терпимо: отсутствующие известные поля получают значения по умолчанию (или переданной базы), неизвестные поля игнорируются, а некорректные отдельные значения заменяются значением по умолчанию этого поля перед ограничением диапазона.

## Управление цветом и воспроизводимость

Конвейер обработки ожидает пиксели Blender как scene-linear float RGB/RGBA. Он переводит RGB в sRGB, выполняет операции в порядке, показанном выше, затем переводит RGB обратно в scene-linear. Alpha, если присутствует, сохраняется без изменений. Результат ограничивается диапазоном `[0, 1]` и сохраняется API изображения Blender как sRGB PNG.

Для одинаковых входных пикселей, настроек и seed результат обработки детерминирован. Phase 2 использует независимые детерминированные случайные потоки, полученные из общего seed для эффектов оттенка и painterly; существующий поток низкочастотной вариации Phase 1 остаётся неизменным. Изменение seed может дать другой процедурный результат. Это описание реализации, а не утверждение, что любая конфигурация color management даст одинаковый вид во всех display transform Blender.

## Рекомендуемый workflow

```text
Install the add-on
    ↓
Select a UV-mapped mesh
    ↓
Check its active material and direct Base Color image link
    ↓
Choose output resolution and folder
    ↓
Adjust Phase 1/Phase 2 parameters
    ↓
Optionally press Randomize Style
    ↓
Press Process Texture
    ↓
Inspect the new PNG
    ↓
Confirm the generated image is connected (or leave Apply to Material disabled)
    ↓
При необходимости включите Pack into .blend
    ↓
Save the .blend manually if the packed data or material link must persist
```

Плановый workflow в `document.txt` упоминает генерацию материала, AO, roughness, preview, пресеты, bake и экспорт GLB. Эти шаги данной версией репозитория не реализованы.

## Известные ограничения

- Рассматриваются только активный объект, активный материал, активный output, Principled BSDF и прямое изображение Base Color.
- Для валидации нужна UV-карта, хотя сама обработка работает с изображением, а не запекает координаты меша.
- Функции материалов Phase 3 — roughness, AO, curvature и генерация материала — не реализованы.
- Preview, пресеты и пакетная обработка Phase 4 не реализованы.
- Цель материала ограничена прямой связью Image Texture → Principled BSDF Base Color; текстуры через другие shader networks отклоняются.
- Упаковка не сохраняет `.blend` автоматически; пользователь должен сохранить его вручную.
- За один вызов **Process Texture** обрабатывается одно изображение.
- Запись на диск использует детерминированное имя и может перезаписать существующий файл с тем же именем.
- Объявленный минимум Blender — 4.2.0; совместимость вне проверенного Blender 5.2.1 не верифицирована.
- Визуальное качество не гарантируется; пригодность изображения и результат нужно оценивать в целевом материале.

## Архитектура

```text
stylized_texture_addon/
├── __init__.py                 registration, legacy metadata, safe extension loading
├── operators/
│   ├── process.py              validation, resize, pipeline, image creation, PNG save
│   ├── randomize.py            Randomize Style operator
│   └── reset.py                restore UI defaults
├── panels/main_panel.py        View3D sidebar panel and UI grouping
├── properties/settings.py      Blender RNA properties and defaults
├── processing/
│   ├── settings.py             Blender-independent settings and tolerant adapter
│   ├── pipeline.py             Phase 1/Phase 2 pipeline and color-space handling
│   ├── randomize.py             deterministic style sampling and whitelist
│   ├── seeding.py              independent Phase 2 RNG streams
│   ├── resize.py               bilinear resize and aspect-preserving fit
│   ├── color.py                color conversions and color operations
│   ├── hue.py                  hue variation
│   ├── painterly.py            painterly variation
│   ├── micro_detail.py         detail smoothing
│   ├── variation.py            deterministic low-frequency field
│   └── validate.py              NumPy array validation
├── utils/
│   ├── materials.py           marker-based generated-image material assignment and cleanup
│   ├── validation.py           Blender scene/input validation
│   ├── images.py               Blender image pixel conversion and PNG I/O
│   └── paths.py                output path and filename resolution
└── blender_manifest.toml       Blender extension metadata
```

## Тесты, команды и артефакты

Собрать оба архива:

```text
python scripts/package.py
```

Собрать один архив:

```text
python scripts/package.py --legacy-only
python scripts/package.py --extension-only
python scripts/package.py --blender /path/to/blender
```

Запустить общий runner (упаковка, чистые Python-тесты и Blender-тесты при наличии Blender):

```text
python scripts/run_tests.py
python scripts/run_tests.py --python python --blender /path/to/blender
python scripts/run_tests.py --skip-pure --skip-blender
```

Запустить чистые тесты напрямую:

```text
python -m unittest discover -s tests -p "test_*.py" -v
```

Чистые тесты покрывают регрессию Phase 1, HSV/hue Phase 2, обработку micro-detail и painterly, детерминированные seed, адаптацию настроек и выбор параметров Randomize Style. В Blender-тестах есть набор `blender-materials` для проверки применения материала, упаковки и отката, а также циклов регистрации, обработки, неизменности исходных данных/материала, сохранения настроек и отсутствия обработки у Randomize Style, загрузки без metadata, legacy-установки, установки/валидации extension и синтетических A/B/C-артефактов.

Создаваемые артефакты упаковки: `build/stylized_texture_addon-legacy.zip` и `build/stylized_texture_addon-extension.zip`. Тестовые визуальные артефакты: `build/artifacts/A_original.png`, `build/artifacts/B_stylized.png` и `build/artifacts/C_material_view.png`.

Фактическая совместимость с конкретной версией Blender требует запуска этих тестов с соответствующим исполняемым файлом; тестовой целью репозитория является Blender 5.2.1.

## Changelog

См. [`CHANGELOG.md`](CHANGELOG.md) — запись о реализации и [`CHANGELOG.ru.md`](CHANGELOG.ru.md) — перевод на русский.
