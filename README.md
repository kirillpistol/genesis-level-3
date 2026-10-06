# GENESIS — уровень 3: адаптер внешних данных v1

Данные приходят извне. Репозиторий не содержит датасетов, алгоритмов и секретов.
[Ядро](https://github.com/kirillpistol/pistol-genesis-ai) владеет mTLS, allowlist,
discovery и контрактами транспорта. [Уровень 2](https://github.com/kirillpistol/genesis-level-2)
определяет смысл записи и числовую оценку.

## Реализовано

level3_data.adapter.Adapter передаёт одну JSON-запись и ждёт ответ.
stream обрабатывает iterable последовательно без накопления списка результатов.
Автоматических повторов задач нет: timeout оставляет результат неизвестным.
Соединение создаёт allowlisted mTLS Client уровня 1, redirects запрещены.

Если три репозитория находятся рядом, из папки уровня 3 задайте
PYTHONPATH=../pistol-genesis-ai (PowerShell: $env:PYTHONPATH='../pistol-genesis-ai').
Пример с заранее установленным алгоритмом numeric на защищённом ядре:

```python
import json
from level1_core.discovery import client_from
from level3_data.adapter import Adapter

with open('../pistol-genesis-ai/.local-certs/client.json') as file:
    control = client_from(json.load(file))
control.request('https://localhost:8443', '/v1/algorithms/attach',
               {'api_version': '1.0', 'name': 'numeric'})
with open('../pistol-genesis-ai/.local-certs/data.json') as file:
    client = client_from(json.load(file))
adapter = Adapter(client, 'https://localhost:8443', 'numeric')
for result in adapter.stream(iter([10, 20, 30])):
    print(result)
```

Три синтетических числа в примере — проверка, не встроенный датасет.
Перед повторным attach проверьте /v1/status; повтор подключения отклоняется.

## Контракты

POST /v1/tasks: api_version="1.0", algorithm, data.
Ответ: api_version, algorithm, revision, result.
Схемы источником истины находятся в core contracts/v1.
Только точная версия 1.0; старые /tasks и архивные envelopes несовместимы.
Управляющие поля не расширяются произвольно; схемы данных задаёт алгоритм.

Записи до 65536 байт с учётом envelope; не отправляйте код, команды или пакеты
как исполняемые обновления. Адаптер ничего не устанавливает.
После переноса ядра создайте новый Adapter на разрешённый адрес приёмника.
Discovery обнаруживает разрешённые core endpoints, но не выбирает произвольные
источники данных и не переключает поток автоматически.

## Проверка и ограничения

```sh
python -m unittest discover -s tests -v
```

Конкретные коннекторы к внешним сервисам, event_id/deduplication, очереди,
автоматическое переключение после переноса пока отсутствует. Роли control/data реализованы ядром; записи отправляйте data-клиентом, attach — control-клиентом.
Хранение на стороне источника/потребителя контролирует пользователь.
Обучение и обмен состояниями отложены до проверки числового этапа.
[ADR](https://github.com/kirillpistol/pistol-genesis-ai/blob/main/docs/adr/0001-transport-boundaries-versioning.md).

## Correlation и CI

Adapter.send(record, correlation_id="source-123") передаёт ID в X-Correlation-ID
через транспорт ядра. Без аргумента transport создаёт UUID. Для stream используйте
обычный цикл send, если требуется один ID для всей операции; тела не логируются.

CI во всех трёх репозиториях запускает полный e2e и frozen/current совместимость
в обоих направлениях. В e2e Adapter получает записи из отдельного HTTP-сервера,
переключается на живой узел после переноса и проверяет числовой результат/MAE/RMSE.
Корреляция не является event_id и не даёт дедупликацию. Повторы задач, DLQ,
rate limits источника и durable очередь пока не реализованы.

## Распределённые данные только для своей связки

`level3_data.bound.BoundAdapter` принимает вручную утверждённые passport и manifest, получает NDJSON-части через PartClient по mTLS и точному allowlist, проверяет size/checksum и хеши записей перед отправкой. Ядро проверяет binding/version/source/part/index/hash и сертификат с разрешением на этот сектор. В памяти сборщика находится одна часть до 64 KiB; полного объединённого набора нет. Один сборщик на связку. После потерянного ответа повторный запуск использует подтверждённый cursor; автоматического retry задач нет.

`python -m level3_data.serve_parts` запускает read-only сервер заранее подготовленных файлов; `python -m level3_data.run_bound` запускает последовательную сборку. Разделяйте client_pins серверов частей по секторам; файлы и ключи не входят в Git. Вручную выпускайте новую data_version и утверждайте обновлённый manifest. Автошардирования, secret sharing и запуска сторонних программ нет.

Новые модули требуют соседнее ядро в PYTHONPATH. [Полный запуск](https://github.com/kirillpistol/pistol-genesis-ai#строгая-ручная-связка-рабочий-локальный-тест), [ADR-0003](https://github.com/kirillpistol/pistol-genesis-ai/blob/main/docs/adr/0003-manual-bindings.md).

## MESM
`level3_data.mesm.MesmClient` получает каталог, планы и HTML-отчёт локального MESM API по Bearer token. `python -m level3_data.run_mesm --help`: передача в установленный mesm_budget/1 через mTLS client_from (или явно --dev-local). Сверяет snapshot и город, не повторяет задачи. [Инструкция](https://github.com/kirillpistol/MESM/blob/main/docs/37_genesis_connection.md). `mesm_e2e.py --mesm-root <MESM>` проверяет всю связку с настоящим mTLS.
