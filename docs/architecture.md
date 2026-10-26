# Архитектура

Статус: proposed. Стартуем с модульного backend и отдельного host agent.
API и worker — два процесса одного control-plane, с общими бизнес-модулями.
Границы независимых микросервисов пока не обоснованы.

Путь данных: браузер → HTTPS API → PostgreSQL; worker → SSH bootstrap → узел;
агент → исходящий mTLS канал → agent API; telemetry → Prometheus-compatible
хранилище → Grafana; backend выдаёт frontend авторизованные сводки.
Worker использует durable jobs в PostgreSQL с lease, heartbeat и recovery.
Внешние side effects выполняются вне длинных DB-транзакций.

| Модуль | Владелец данных / контракт | Отказы и проверки |
| --- | --- | --- |
| Identity | users, sessions, tenant membership; register/login/logout | Brute force, expiry, CSRF, чужой объект |
| Inventory | hosts, services, deployments, dependencies, observations | Partial discovery, stale heartbeat, pagination |
| Credentials | credential references и envelope ciphertext; никогда UI plaintext | Rotation, KMS outage, чужой tenant, audit redaction |
| Bootstrap/jobs | InstallAgent, JobStatus, idempotency key и lease | SSH timeout, host key mismatch, worker crash, повтор |
| Agent gateway | Versioned enrollment/heartbeat/inventory/command contracts | Revocation, replay, out-of-order events, oversized batch |
| Observability | Dashboard bindings, metric queries, definitions пользователей | Нет данных, Grafana outage, tenant filter |
| Capacity | Версия rules, окно, evidence, recommendations | Пики, длительная перегрузка, sparse series, hysteresis |
| Migration | MigrationPlan, steps, approvals, checkpoints и recovery state | Потеря связи, повтор шага, partial cutover, restore |
| Audit | Actor, action, target, outcome, timestamp, correlation ID | Без секретов и payload с паролями |

Идентификатор tenant берётся из серверной сессии; объект всегда проверяется
по tenant/permissions. Владельцы модулей предоставляют application API;
модули не читают чужие внутренние таблицы. Agent никогда не имеет DB-доступа.

Предлагаемые сущности: User, Tenant, Membership, Host, CredentialRef,
AgentIdentity, Service, Deployment, Observation, DashboardBinding, Job,
MigrationPlan, MigrationRun, CapacityRecommendation, AuditEvent.
Все tenant-объекты имеют tenant_id и индексы для scoped queries.

API: OpenAPI — источник frontend types. Agent protocol версионируется отдельно,
с явным compatibility window; contracts хранят schemas и примеры без секретов.
Команда агента содержит command ID, target, expiry и allowlisted operation.
Повтор использует записанный результат; произвольный shell из UI запрещён.
Heartbeat не даёт агенту полномочий управлять другими узлами.

Перенос: draft → preflight → awaiting-confirmation → copying → validating →
cutover → completed; состояния failed/cancelled/recovery-required сохраняют
последний checkpoint. Повтор шага не повторяет внешний эффект. Необратимость
отмечается до подтверждения. После начала записи на target возврат требует
явного плана синхронизации/restore; обещать универсальный rollback нельзя.
Поддержка переносов появляется по одному adapter, сначала тестовый stateless
Compose-сервис, затем отдельно stateful с проверяемым backup/restore.

Capacity v1 — объяснимые threshold/window rules с hysteresis и cooldown.
CPU/RAM/disk оцениваются раздельно. Forecast вводится после накопления истории
и проверки ошибок прогноза; автоматическое увеличение мощности в MVP не входит.
