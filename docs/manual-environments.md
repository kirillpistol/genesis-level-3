# Окружение L3 и обмен заданиями — общий механизм

Компоненты заранее размещает оператор. `verify_environment` проверяет паспорт, точную зависимость от L2 и хеши компонентов. «Сборка» здесь — проверка готового состава, без установки, распаковки архивов, выполнения сетевого кода или запуска сторонних приложений. Источники данных остаются в отдельных вручную утверждённых manifests; окружение не объединяет базы.

`contracts/v1/environment.json`: environment_format=level3-environment/1, environment_id, environment_version, binding_id, passport_sha256, adapter_contract=bound-stream/1, level2_package_sha256, components. components — относительные пути и SHA256. environment_sha256 вычисляется `level1_core.bindings.digest(descriptor)`. Корневые каталоги и descriptors утверждает оператор, хеши сами по себе не являются цифровой подписью. Лимиты компонентов соответствуют L2.

Предварительная проверка (в PYTHONPATH должны быть все три соседних репозитория):

```sh
python -m level3_data.verify_environment --directory /approved/environment --environment environment.json --passport passport.json --package-directory /approved/package --package package.json
```

`JobRunner` использует существующий BoundAdapter и транспорт ядра. Контракт job.json: job_format=bound-job/1, job_id, binding_id, passport_sha256, environment_sha256, expected_cursor, max_records=1..64, correlation_id. Ядро должно уже иметь выбранную связку; runner не имеет control роли и не выбирает её самостоятельно. Точный cursor предотвращает повтор ранее принятой порции. Проверка компонентов выполняется перед каждым заданием. Один collector на связку; mutex ограничивает только данный экземпляр runner, распределённой аренды нет.

```sh
python -m level3_data.run_job --client-config data-client.json --parts-config parts-client.json --passport passport.json --manifest manifest.json --directory /approved/environment --environment environment.json --package-directory /approved/package --package package.json --job job.json
```

Ответ bound-job-result/1: job_id, binding_id, correlation_id, environment_sha256, processed, checkpoint={passport_sha256,next_record}, complete, last_result. Ответ ограничен 64 KiB; последнее значение, без накопления результатов всей порции. На завершённом потоке возвращается processed=0, complete=true. При потерянном ACK исключение сохраняется: прочитайте `/v1/bindings/status`, вручную согласуйте expected_cursor и повторите с подтверждённой позиции. Ни automatic retry задач, ни durable exactly-once нет. Если ответ слишком большой после принятия записи, тоже сверяйте cursor.

Новые contracts — локальные форматы обмена и Python/CLI API, не новые HTTP endpoints ядра. JSON schemas документируют формат; реализация проверяет использованные поля явно, не подключает универсальный JSON Schema engine. Snapshot и существующий /v1 остаются прежними. Подключение нового сектора требует ручного паспорта, собственного L2, схемы данных и адаптера; конкретные прикладные данные в этом дополнении отсутствуют.
