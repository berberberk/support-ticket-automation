# Мониторинг

## Реализовано в PoC

- потокобезопасные in-process счётчики запросов, решений, hard-risk, retrieval, генератора и ошибок аудита;
- `GET /metrics` возвращает компактный JSON без текста тикетов, PII, ключей и prompt content;
- локальный `benchmark.py` измеряет только детерминированный hot path: нормализацию, правила риска и классификацию;
- наблюдения отказов retrieval и генератора доступны через счётчики, но не заменяют production-мониторинг.

Это endpoint PoC. В целевой системе эквивалентные сигналы экспортируются в реальный мониторинг; локальные счётчики не подходят для нескольких процессов или экземпляров.

## Целевой мониторинг

- Prometheus/Grafana или эквивалент для агрегирования метрик и алертов;
- distributed traces и специализированная LLM-трассировка/оценка, например Langfuse или OpenTelemetry;
- мониторинг ML-качества по delayed labels и выборочной операторской разметке;
- доставка алертов и эксплуатационные регламенты.

Ни Prometheus/Grafana, ни Langfuse, ни OpenTelemetry в PoC не реализованы.

## Технические метрики

| Метрика | Назначение |
|---|---|
| Fast path p50/p95/p99 latency | Контроль целевого времени классификации и маршрутизации: p95 должен укладываться в ориентир `<=500 мс`. |
| Error rate и throughput | Видеть сбои и фактическую нагрузку, включая всплески до `≈33,3 тикета/с`. |
| Queue depth и oldest-message age | Контролировать backlog и угрозу SLA первого ответа. |
| LLM timeout/error rate и retry rate | Отделять проблемы внешнего генератора от проблем маршрутизации. |
| Operator escalation rate | Контролировать нагрузку на операторов и изменение abstention-политики. |
| Audit-write failures | Не допускать потери обязательного аудита автоматических решений. |

Для peak из кейса ориентир составляет `≈33,3 тикета/с`. Локальный микрозамер показывает только производительность детерминированного PoC на конкретной машине; он не является нагрузочным тестом и не доказывает готовность к production-нагрузке.

## ML-метрики

- **Routing:** macro-F1, per-class recall, распределение confidence и abstention rate.
- **Risk:** recall рискованных классов, false-negative rate и доля пропущенных рисков, подтверждённых оператором.
- **Retrieval:** Recall@K и MRR на размеченном evaluation-наборе, evidence-missing rate.
- **Generation:** groundedness, unsupported-answer rate, unsafe response rate, operator acceptance/edit rate.

## Бизнес-метрики

Отслеживаются нагрузка и время обработки оператором, SLA первого ответа, CSAT, reopen rate и доля автоматизации/принятия черновиков. В качестве исходных ориентиров используются SLA 15 минут, CSAT 4,2/5, reopen rate 9% и ручная обработка стоимостью 150 ₽ или около 8 минут на тикет. Цель автоматизации не должна достигаться ценой ухудшения SLA, CSAT, reopen rate или safety-показателей.

## Стартовые алерты

| Сигнал | Начальная реакция |
|---|---|
| Fast-path p95 выше 500 мс устойчивое окно | Проверить горячий путь и масштабирование; длительность окна — initial pilot assumption. |
| Возраст oldest queue message угрожает SLA 15 минут | Включить retrieval/template fallback или направить новые тикеты оператору. Порог до SLA — initial pilot assumption. |
| Подтверждённый оператором missed-risk | Немедленно остановить расширение автодействий и проверить правила/версию модели. |
| Всплеск LLM timeout/error или retry относительно rolling baseline | Переключить fallback и ограничить новые LLM-вызовы. |
| Cost per ticket или LLM-call share выше rolling baseline | Проверить routing, cache/template/retrieval-only bypass и лимиты токенов. Численный порог — initial pilot assumption. |
| Любая ошибка записи аудита | Не считать автоматическое решение завершённым; в PoC ошибка прерывает запрос, а безопасный retry/manual review относится к целевой архитектуре. |

Численные operational thresholds, которых нет в условии, являются стартовыми assumptions для пилота и подлежат настройке по измерениям.

## Input shift и деградация модели

Input shift отслеживается по изменению долей тем, каналов, языков и длины текста, OOV/score distributions и incident-driven category mix. Изменившийся поток сам по себе не доказывает деградацию модели.

Model-quality degradation подтверждается delayed labels или sampled human review: например, per-class recall/F1 ухудшается при стабильном входном распределении. При input shift сначала проверяются трафик, инцидент, правила и актуальность данных; при подтверждённой деградации качества выполняются rollback/version comparison, recalibration или retraining.

## Стоимость LLM

Для production-дизайна считаются LLM calls per ticket, input/output tokens, cost per ticket, total daily cost, доля тикетов, дошедших до LLM, и cache/template/retrieval-only bypass rate. Повторяющиеся безопасные случаи должны обходить LLM через routing и шаблоны; алерты на cost per ticket и LLM-call share предотвращают неконтролируемый рост стоимости.

## Проверка исходной задачи

Оптимизация считается успешной только если вместе с offline ML-метриками снижаются нагрузка и время операторов, SLA первого ответа не ухудшается, CSAT и reopen rate остаются не хуже baseline, а unsafe/risky misses находятся в принятой пилотом safety-зоне. Эти показатели проверяются на delayed labels, sampled review и продуктовых данных, а не только на score модели.
