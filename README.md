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
    client = client_from(json.load(file))
client.request('https://localhost:8443', '/v1/algorithms/attach',
               {'api_version': '1.0', 'name': 'numeric'})
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
роли control/data и автоматическое переключение после переноса пока отсутствуют.
Хранение на стороне источника/потребителя контролирует пользователь.
Обучение и обмен состояниями отложены до проверки числового этапа.
[ADR](https://github.com/kirillpistol/pistol-genesis-ai/blob/main/docs/adr/0001-transport-boundaries-versioning.md).
