# Highload и надёжность

- Классификация и маршрутизация работают синхронно на лёгком fast path; retrieval и подготовка черновика выполняются асинхронно и не блокируют ответ горячего пути.
- Всплеск `20k / 10 минут ≈ 33,3 тикета/с` буферизуется очередью; при росте queue depth/age применяется bounded backpressure, retrieval/template fallback или операторская обработка.
- При 10-минутной недоступности LLM маршрутизация продолжается, тикеты не теряются, retries ограничены, а безопасный fallback или HITL заменяет внешнюю генерацию.
- Для side effects используются атомарный claim `PENDING -> PROCESSING`, завершение `SENT/COMPLETED` и один `operation_id` на все retries.

# Privacy, safety и risk

- PII минимизируется или redacted до передачи внешнему сервису; исходный тикет остаётся в доверенном контуре, а лишние raw PII не попадают в аудит.
- Hard-risk, low-confidence, отсутствие evidence и unsafe/ungrounded draft переводят тикет в HITL; автоматическое закрытие таких случаев запрещено.
- Ticket text и retrieved content — untrusted data, retrieval ограничен approved sources, произвольные tools/actions в PoC отсутствуют; это layered mitigation prompt injection, а не гарантия устранения риска.
- Audit trail хранит версии компонентов, evidence, причины и решения оператора без ненужного raw текста, чтобы автоматические решения можно было проверять и воспроизводить.
