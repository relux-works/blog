---
title: "Семантическое ядро вместо словаря фраз"
description: "Чему нас научил отклонённый rewrite промпта Caveman: стабильная test taxonomy вне runtime-контекста, назначение ID на этапе eval и проверка полноты evidence до публикации метрик."
slug: "semantic-core-instead-of-phrasebooks"
lang: "ru"
authors:
  - name: "Alexis Grigoryev"
    title: "CTO / Founding Engineer, Relux Works"
    links:
      - "https://www.linkedin.com/in/alexis-grigoryev-22bab159/"
  - name: "Ivan Oparin"
    title: "CEO / Founding Engineer, Relux Works"
    links:
      - "https://github.com/ivanopcode"
      - "https://www.linkedin.com/in/ivanoparin/"
aiSystems:
  - "OpenAI Codex"
  - "Claude Opus 5"
---

Мейнтейнер Caveman
[закрыл наш pull request с точным замечанием](https://github.com/JuliusBrussee/caveman/pull/944#issuecomment-5510147754):
тело skill является продуктом, rewrite должен пройти его собственный eval loop,
а идентификаторы вроде `CAV-SEM-07` в runtime-заголовках будут попадать в модель
на каждой сессии как чистый overhead. Исходный
[Caveman PR #944](https://github.com/JuliusBrussee/caveman/pull/944) объединял
31-процентный rewrite runtime skill, семантический контракт, model runs, отчёты,
generated mirrors и raw snapshots. Замечание было верным. Стабильные ID приносили
пользу, но находились по неправильную сторону интерфейса.

У этой ошибки общая форма. У стилевого skill для языковой модели есть две разные
аудитории. Модели при каждом вызове нужен небольшой набор поведенческих правил.
Инженерам нужны идентификаторы, матрицы покрытия, fixtures, отчёты и сравнения
между ревизиями. Если смешать эти аудитории, runtime-промпт начинает платить за
тестовую систему.

Статья отвечает на один вопрос: где должны жить стабильные идентификаторы test
taxonomy, чтобы отчёты могли ими пользоваться, а runtime-промпт никогда их не
нёс? Она описывает три маленьких Caveman follow-up PR, заменивших #944, и один
пример runtime-стороны из Pohuy. Поведение модели под этими skills здесь не
оценивается.

Предыдущая версия этой статьи описывала размеры candidate из #944 как результат,
доставленный в Caveman. Это были измерения unmerged-ветки. Текущая редакция исправляет
запись и описывает более узкий дизайн, который появился после ревью.

## Runtime-правила и evaluation metadata находятся в разных слоях

Семантическое ядро определяет поведение, которое должна применить модель:

- сжимать форму с сохранением технического содержания;
- сохранять отрицания, ограничения, числа, единицы, code, identifiers, APIs,
  commands и процитированные ошибки;
- сохранять язык пользователя и грамматические маркеры ролей;
- писать публичные и сохраняемые артефакты обычной прозой;
- отключать сжатый стиль, когда safety или упорядоченная recovery procedure
  требуют полной ясности.

Эти правила входят в runtime-контекст, потому что могут изменить ответ.

Evaluation metadata решает другую задачу. Стабильный идентификатор позволяет
отслеживать один invariant через переименованные cases, переставленные fixtures и
новые ревизии skill. Он поддерживает joins, coverage matrices, trends и группировку
ошибок. Модели не требуется видеть этот идентификатор, чтобы выполнить правило.

Практическая граница выглядит так:

| Задача | Представление в source | Попадает в runtime-промпт? |
| --- | --- | --- |
| Поведенческое правило | Ясный естественный язык | Да |
| Calibration example | Минимальный характерный пример | Иногда |
| Стабильный contract ID | Запись eval taxonomy | Нет |
| Связь case с invariant | Читаемые taxonomy keys | Нет |
| Coverage matrix и отчёт | Generated eval output | Нет |

## Назначаем ID при запуске evaluation

Дальше пример Caveman следует за одним invariant, exact preservation, от записи в
taxonomy через source case до аннотированной строки отчёта. Узкая замена в
[Caveman PR #1061](https://github.com/JuliusBrussee/caveman/pull/1061)
хранит стабильный ID только в eval taxonomy. В этом дизайне запись taxonomy
является единственным местом, где `CAV-SEM-02` написан руками; cases и runtime
skill проверяются на его отсутствие:

```json
{
  "id": "CAV-SEM-02",
  "key": "exact-preservation",
  "description": "Preserve polarity, limits, numbers, units, code, identifiers, APIs, commands, and quoted errors."
}
```

Source case ссылается на этот invariant по читаемому key и никогда по ID, поэтому
fixture можно ревьюить без таблицы соответствий:

```json
{
  "id": "polarity-and-limits",
  "taxonomy": ["exact-preservation"],
  "prompt": "Restate this retry policy without changing meaning: Do not retry more than 3 times. Retry only after 250 ms, except for HTTP 429."
}
```

При подготовке run или отчёта annotation step разрешает этот key. Ожидаемый
результат представляет собой тот же case с одним добавленным полем:

```json
{
  "id": "polarity-and-limits",
  "taxonomy": ["exact-preservation"],
  "contract_ids": ["CAV-SEM-02"],
  "prompt": "Restate this retry policy without changing meaning: Do not retry more than 3 times. Retry only after 250 ms, except for HTTP 429."
}
```

Между вторым и третьим примером изменилось только поле `contract_ids`, и появилось
оно на этапе evaluation. Отчёт получает стабильные машинные идентификаторы, а
runtime `SKILL.md` не содержит ни одного такого ID. Test suite проверяет эту границу
напрямую.

На граничных случаях resolver и оправдывает своё существование. Он останавливается
на duplicate taxonomy ID, duplicate case ID, неизвестном key, повторённом key,
malformed entry и source case со встроенным contract ID. Эти проверки нужны потому,
что опечатка в key должна остановить run. Молчаливый пропуск mapping создаст чистый
отчёт со скрытой дырой в покрытии.

Одна нумерация требований даёт мало. Taxonomy становится полезной, когда case может
относиться к нескольким invariants, а инженер видит получившуюся matrix.
Португальский prompt про migration покрывает одновременно `language-and-grammar` и
`exact-preservation`. Публичное описание security PR покрывает `artifact-boundary`
и `safety-clarity`. Список cases показывает набор промптов. Matrix между cases и
invariants показывает свойства с positive controls, negative controls,
пересекающимся покрытием или полным отсутствием evidence. Стабильные ID делают
сравнение долговечным между ревизиями. Читаемые keys оставляют fixtures доступными
для review. Annotation step соединяет эти представления в момент, когда
дополнительная metadata становится полезной.

## Полная evidence до красивых метрик

Целостная taxonomy не доказывает полноту run. Review исходного #944 также обнаружил,
что partial evidence могла пройти structural gate. Мы выделили эту проблему в
[Caveman PR #1062](https://github.com/JuliusBrussee/caveman/pull/1062).

Validator запускается до существующего token report и требует:

- snapshot metadata и непустой список prompts;
- оба comparison controls;
- хотя бы один skill arm;
- ровно один output на каждый prompt в каждом arm;
- raw outputs типа string;
- `n_prompts`, равный реальному числу prompts.

Evidence для этого validator является набором tests, и именно tests делают gate
заслуживающим доверия. В них committed snapshot служит positive control. Затем test
удаляет control, обрезает arm, заменяет raw output объектом, меняет `n_prompts`,
удаляет все skill arms и повреждает JSON. Checker становится доказательством только
после того, как известное нарушение заставило его упасть по ожидаемой причине.

## Изолируем generator от окружения оператора

Даже полная matrix может измерять не тот объект, если runner наследует локальную
настройку агента. Старый вызов Claude получал user и project settings вместе с MCP
configuration. Два инженера могли запустить одинаковые committed fixtures и незаметно
дать модели разные инструкции или tools.

[Caveman PR #1063](https://github.com/JuliusBrussee/caveman/pull/1063)
добавляет `--setting-sources ""` и `--strict-mcp-config` по уже используемому в
`caveman-compress` isolation pattern. Unit tests проверяют точные user prompt,
system prompt, model и isolation arguments без вызова модели.

Taxonomy, matrix validation и runner isolation являются отдельными контрактами.
Каждый можно рассматривать и мержить независимо. Поэтому replacement состоит из
трёх маленьких PR вместо ещё одного общего harness и prompt rewrite.

## Pohuy показывает runtime-сторону границы

Pohuy является отдельным примером, а не продолжением примера Caveman: он показывает,
что остаётся на runtime-стороне после того, как metadata оттуда вынесена. То же
разделение применимо к phrasebooks. Открытый
[Pohuy PR #21](https://github.com/smixs/pohuy/pull/21) предлагает runtime skill
размером 2 694 байта и 57 строк с нулём mandatory reference loads. Он сохраняет
explicit activation, три уровня интенсивности, tone semantics, artifact boundaries
и ясное safety behavior. Glossaries и collections of scenarios остаются optional
material.

Это точные измерения файла и контракта, а не универсальное утверждение о tokens или
качестве. Детерминированный harness в PR mutation-тестирует byte и line budgets,
activation boundaries, default level, reference loading, eval schema и safety
thresholds. Поведение модели всё равно требует отдельной evaluation.

## Что подтверждает текущая evidence

Три Caveman follow-up PR открыты на момент этой редакции. Их tests подтверждают
работу предложенных taxonomy mapping, fail-closed matrix validation и isolated
command construction. Они не доказывают semantic equivalence между моделями. Они
не обосновывают merge отклонённого runtime rewrite. Они не заявляют token savings
от самих идентификаторов.

Узкое утверждение сильнее, потому что его можно проверить: traceability metadata
добавляется во время evaluation, используется в отчётах и механически исключается
из runtime-промпта.

## Практическая последовательность

1. Описать behavioral invariants ясным языком.
2. Оставить в runtime-контексте только правила, влияющие на поведение модели.
3. Дать каждому invariant стабильный ID и читаемый key в eval-only manifest.
4. Разметить cases читаемыми keys.
5. Разрешать стабильные ID при подготовке run или report.
6. Отклонять unknown keys, duplicates, malformed cases и incomplete evidence.
7. Изолировать model runners от user settings, project settings и inherited tools.
8. Mutation-тестировать каждый gate известным нарушением.
9. Публиковать model, inputs, repetitions, controls, ограничения и unresolved cases.

У prompt optimization и evaluation design один инженерный принцип: информация должна
находиться на той границе, где её используют. Behavioral instructions нужны модели.
Taxonomy и traceability нужны тестовой системе. Отсюда следует конкретное решение:
contract ID, найденный в runtime-файле, является утечкой из тестовой системы, и
исправлением будет перенос его в eval manifest.
Явная граница экономит контекст и создаёт evidence, которой проще доверять.
