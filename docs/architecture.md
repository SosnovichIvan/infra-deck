# Архитектура первого релиза

Подробное решение: [ADR 0002](adr/0002-first-release.md). Исходный
[ADR 0001](adr/0001-initial-architecture.md) описывает дальнейшее развитие.

React/TypeScript/FSD в apps/web → same-origin /api FastAPI → PostgreSQL 17.
Identity владеет пользователями/сессиями/OTP/Telegram enrollment/recovery;
Inventory владеет проектами/серверами/connection proofs. Credentials adapter
обеспечивает JWE и at-rest AEAD, SSH adapter делает bounded authentication без
команд. Отдельного worker и агента в первом релизе нет: SSH проверка ограничена
12 секундами, не требует durable job. Синхронные endpoint functions работают
в threadpool; AsyncSSH и Telegram adapter имеют собственный bounded lifecycle.

OpenAPI экспортируется scripts/export_openapi.py в contracts/openapi.json;
TypeScript types генерируются openapi-typescript. Поля Connection описывают
расшифрованное содержимое envelope, а не открытый HTTP payload.

Frontend: app (providers/routes), pages/auth/projects/servers, shared/api/ui.
TanStack Query владеет серверными данными; формы — локальным draft; секреты
не попадают в localStorage/URL. Logout удаляет кэш данных предыдущего владельца.
Граф импортов проверяется scripts/check-frontend.mjs.

Таблицы и инварианты: users 1:N sessions/projects/recovery_codes; projects 1:N
servers/checks с composite FK owner; sessions 1:N encryption_nonces с cascade.
Telegram ID/login уникальны; sessions token, nonce и proof хешированы; срок
проверяется на сервере; one-use consume в transaction. Индексы owner/project/id
обслуживают bounded lists ORDER BY id LIMIT 100 OFFSET; запросы не делают N+1.
Объём и SLO пока не измерены; keyset pagination потребуется при большом реестре.

Мигратор serializes upgrade PostgreSQL advisory lock, применяет SQL атомарно.
001 — новая схема, production данных предыдущего runtime нет. Повторный upgrade
проверяется с данными; rollback восстанавливает DB backup и соответствующие key
files в отдельную среду. Destructive downgrade не поддерживается.
