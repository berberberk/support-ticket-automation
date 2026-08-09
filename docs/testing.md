# Проверка инвариантов PoC

| Инвариант | Точка контроля | Уровень | Тест | Статус |
|---|---|---|---|---|
| Hard-risk не вызывает внешний генератор или поиск | `SupportPipeline.process` до retrieval | unit | `test_hard_risk_never_calls_retriever_or_external_generator` | IMPLEMENTED + TESTED |
| Сырые PII не доходят до генератора | `assess_risk` → `generator.generate` | unit | `test_pii_boundary_and_audit_exclude_raw_ticket` | IMPLEMENTED + TESTED |
| Сырые PII не попадают в аудит | `AuditLogger.write` получает только метаданные | unit | `test_pii_boundary_and_audit_exclude_raw_ticket` | IMPLEMENTED + TESTED |
| Нет evidence — нет генерации | retrieval gate | integration | `test_fastapi_no_evidence_returns_review` | IMPLEMENTED + TESTED |
| Тайм-аут OpenRouter ведёт к HITL | `OpenRouterGenerator` / `SupportPipeline` | integration | `test_timeout_has_one_attempt_and_fastapi_fails_closed` | IMPLEMENTED + TESTED |
| 429/5xx и некорректный ответ не дают черновик | OpenRouter error handling | unit | `test_provider_failures_never_create_draft` | IMPLEMENTED + TESTED |
| Синхронный путь не повторяет запрос | один `http_client.post` | integration | `test_timeout_has_one_attempt_and_fastapi_fails_closed` | IMPLEMENTED + TESTED |
| Тайм-аут и `max_tokens` ограничены | `load_config` | unit | `test_timeout_configuration_is_bounded` | IMPLEMENTED + TESTED |
| Prompt-like текст остаётся недоверенными данными | `_messages` | unit | `test_openrouter_request_separates_policy_and_untrusted_ticket` | IMPLEMENTED + TESTED |
| Risky-результат остаётся HTTP 200 | FastAPI-контракт | integration | `test_risky_ticket_returns_review_not_http_error` | IMPLEMENTED + TESTED |
| Некорректный HTTP-ввод даёт 422 | Pydantic validation | integration | `test_malformed_request_returns_validation_error` | IMPLEMENTED + TESTED |
| Офлайн-режим не требует ключа/сети | `AppConfig()` и локальные адаптеры | unit | `test_default_configuration_keeps_offline_components` | IMPLEMENTED + TESTED |
| Ретривер заменяем без изменения конвейера | `Retriever` contract | unit | `test_wiring_accepts_semantic_retriever_contract` | IMPLEMENTED + TESTED |
| Qdrant хранит/ищет векторы и возвращает Evidence | `QdrantRetriever` + `:memory:` | integration | `test_qdrant_memory_vectors_return_domain_evidence` | IMPLEMENTED + TESTED |
| Ошибка Qdrant не маскируется | `QdrantRetriever.retrieve` fallback | unit | `test_qdrant_query_failure_uses_explicit_lexical_fallback` | IMPLEMENTED + TESTED |
| Сбой записи аудита не завершает автоответ | `AuditLogger.write` до возврата результата | unit | `test_audit_persistence_failure_never_returns_draft_ready` | IMPLEMENTED + TESTED |

Тесты не загружают FastEmbed-модель, не требуют `.env`, ключа OpenRouter, внешнего Qdrant или интернета. Реальный FastEmbed и реальный OpenRouter остаются ручными smoke-проверками. В PoC внешний вызов — ровно один синхронный запрос с ограниченным тайм-аутом; retries/backoff относятся к асинхронному worker целевой архитектуры.
