# Проверка инвариантов PoC

| Инвариант | Точка контроля | Уровень | Тест | Статус |
|---|---|---|---|---|
| Рискованное обращение не вызывает поиск и генератор | `SupportPipeline.process` до поиска | Модульный | `test_hard_risk_never_calls_retriever_or_external_generator` | Реализовано и проверено |
| Сырые PII не доходят до генератора и аудита | `assess_risk` → `generator.generate` | Модульный | `test_pii_boundary_and_audit_exclude_raw_ticket` | Реализовано и проверено |
| Нет основания — нет генерации | Проверка результата поиска | Интеграционный | `test_fastapi_no_evidence_returns_review` | Реализовано и проверено |
| Тайм-аут OpenRouter ведёт к оператору | `OpenRouterGenerator` и `SupportPipeline` | Интеграционный | `test_timeout_has_one_attempt_and_fastapi_fails_closed` | Реализовано и проверено |
| Ошибка 429/5xx или неверный ответ не дают черновик | Обработка ошибок OpenRouter | Модульный | `test_provider_failures_never_create_draft` | Реализовано и проверено |
| Синхронный путь не повторяет внешний запрос | Один вызов `http_client.post` | Интеграционный | `test_timeout_has_one_attempt_and_fastapi_fails_closed` | Реализовано и проверено |
| Тайм-аут и `max_tokens` ограничены | `load_config` | Модульный | `test_timeout_configuration_is_bounded` | Реализовано и проверено |
| Тикет остаётся недоверенными данными для LLM | Формирование сообщений `_messages` | Модульный | `test_openrouter_request_separates_policy_and_untrusted_ticket` | Реализовано и проверено |
| Рискованный результат возвращается как корректный ответ API | Контракт FastAPI | Интеграционный | `test_risky_ticket_returns_review_not_http_error` | Реализовано и проверено |
| Некорректный HTTP-ввод возвращает `422` | Валидация FastAPI | Интеграционный | `test_malformed_request_returns_validation_error` | Реализовано и проверено |
| Офлайн-режим не требует ключа или сети | `AppConfig()` и локальные адаптеры | Модульный | `test_default_configuration_keeps_offline_components` | Реализовано и проверено |
| Поисковый адаптер можно заменить без правки конвейера | Контракт `Retriever` | Модульный | `test_wiring_accepts_semantic_retriever_contract` | Реализовано и проверено |
| Qdrant возвращает доменное основание | `QdrantRetriever` с `:memory:` | Интеграционный | `test_qdrant_memory_vectors_return_domain_evidence` | Реализовано и проверено |
| Ошибка Qdrant не скрывается | Резервный лексический поиск | Модульный | `test_qdrant_query_failure_uses_explicit_lexical_fallback` | Реализовано и проверено |
| Ошибка записи аудита не завершает автоответ | `AuditLogger.write` до возврата результата | Модульный | `test_audit_persistence_failure_never_returns_draft_ready` | Реализовано и проверено |

Тесты не загружают модель FastEmbed и не требуют `.env`, ключа OpenRouter, внешнего Qdrant или сети. OpenRouter проверяется подставным HTTP-клиентом, поэтому тестируется контракт отказа, а не доступность провайдера. В PoC допускается ровно один синхронный внешний вызов с ограниченным тайм-аутом; очередь, повторные попытки и задержки между ними относятся к целевой асинхронной системе.
