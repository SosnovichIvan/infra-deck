# ADR 0002: первый релиз InfraDeck

2026-10-27. Статус: реализация согласованного пользователем объёма.

Первый релиз: регистрация, пароль + Telegram OTP (30 секунд), проекты CRUD,
серверы VPS/VM CRUD и проверка SSH. Agents, metrics, Grafana и migrations
сервисов остаются за пределами этого релиза. PostgreSQL 17; FastAPI/Python 3.12;
React/TypeScript/FSD, Tailwind, TanStack Query, Radix Select. Модульный монолит
предпочтён микросервисам: одна транзакционная область, нет независимых команд.

Identity владеет users, sessions, recovery_codes, telegram_updates и rate_limits.
Сессия enrollment/preauth не даёт доступа к проектам. Telegram /start принимает
одноразовую привязку через authenticated webhook. Challenge привязан к cookie,
OTP хранится только как HMAC с отдельным ключом вне БД, 5 попыток на preauth,
повторная отправка не сбрасывает бюджет. Один challenge потребляется под lock.
Сессии: hashed opaque token, HTTPOnly/Secure в production, SameSite=strict,
CSRF double-submit + server-bound token и Origin для mutating browser requests.
Коды восстановления одноразовые, выдаются только при первой полной авторизации.

Inventory владеет projects, servers, connection_checks и encryption_nonces.
Каждый запрос scoped по owner; UUID не является правом. Списки ограничены.
Проверка выполняет DNS policy и SSH вне DB-транзакции, а успешный результат
связывается с owner/project/server и зашифрованными параметрами. Save потребляет
короткоживущий proof атомарно. Изменение connection требует нового proof;
metadata update не читает и не меняет секреты. Delete удаляет только запись.

Credentials: JWE RSA-OAEP-256/A256GCM с nonce (one-use, session-bound, 60 sec).
At rest: случайный DEK/AES-GCM, DEK обёрнут отдельным KEK с version/AAD owner+check;
KEK и RSA private key монтируются файлами вне БД. File KEK — начальный adapter,
не заявление о готовой KMS-интеграции. Restore требует сохранения этих ключей.

SSH сначала показывает host fingerprint без аутентификации; после явного
подтверждения сверяет его повторно и выполняет login. Нет shell-команд.
DNS резолвится один раз на соединение; IP фиксируется, public-only по умолчанию;
private VM разрешаются CIDR policy оператора, metadata/loopback запрещены.
Timeout 10 sec, нет автоматических повторов. Ошибки очищаются от секретов.

Telegram использует явный HTTP CONNECT proxy и проверку TLS, как в planerBot.
В production proxy обязателен, direct fallback отсутствует. Webhook authenticates
secret header; duplicate update ID не повторяет привязку/ответ. Никаких реальных
токенов и сообщений в CI. Отдельный controlled Telegram stub для E2E.

Миграция 001 на пустой PostgreSQL; версия схемы и транзакция мигратора, повторный
upgrade сохраняет данные. Начальный релиз не поддерживает destructive downgrade.
Проверки: API/DB/SSH/Telegram integration, component coverage >=90% lines/branches
отдельно backend/frontend, Cypress через настоящий API+PostgreSQL+Telegram stub,
контракт OpenAPI и FSD graph. Обязательный aggregate Quality gate сохраняется.

Пересмотр: KMS при production provisioning; durable worker при появлении
долгих jobs; agent/monitoring отдельным ADR. Нагрузка/SLO пока не измерены.
