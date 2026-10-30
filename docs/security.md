# Безопасность первого релиза

Пароли: Argon2id (64 MiB, time_cost=3, parallelism=4), уникальный login,
подтверждение не сохраняется. Production параметры следует измерить на целевой VM.
Логин и пароль защищает HTTPS. SSH-реквизиты дополнительно передаются JWE
RSA-OAEP-256/A256GCM (jose/jwcrypto): published kid и одноразовый session nonce,
60 секунд, max envelope size; неизвестные алгоритмы/ключи отклоняются.

Cookie session — случайный 256-bit token, в БД только SHA256; Secure в production,
HttpOnly, SameSite=Strict, rotation после OTP; full TTL 12h, preauth 10min.
CSRF: server-bound token + strict Origin на mutation. Reverse proxy должен
ограничивать body и rate по IP, не доверять публичным X-Forwarded-For.
Код Telegram: CSPRNG 8 цифр включая начальный ноль, HMAC с отдельным secret вне
БД, TTL30 после успешной отправки, 5 попыток под row lock. Resend 30s, 5/5min,
общий бюджет не сбрасывается. Ошибка отправки не создаёт активный challenge.
До проверки нет full session. Повторный login отзывает предыдущие pending
challenges; logout инвалидирует серверную сессию. Recovery codes HMAC, one-use,
только после проверки пароля; коды не логируются.

Telegram /start привязывает только numeric ID из личного чата после проверки
webhook secret header. Enrollment link действует 10min и one-use; update ID
дедуплицируется в PostgreSQL. Смена Telegram-привязки не предоставляется в v1.
Production Telegram обязательно идёт через явный HTTP CONNECT proxy (TLS
verification сохраняется), без прямого fallback. См. [runbook](operations.md).

At rest: случайный AES256 DEK для каждой записи; ciphertext и wrapped DEK в
БД, AES256 KEK отдельно файлом; AAD owner/project/server. Version1 adapter —
файловый KEK, не Vault/KMS. RSA/KEK/OTP key files вне Git/образов/БД, mode0600.
Не терять ключи: DB backup без них не позволяет восстановить реквизиты.
Операторская ротация KEK/KMS — отдельная задача до соответствующего production
rollout; не перегенерировать ключи при обновлении контейнера.

SSH: fingerprint без authentication, явная сверка пользователем по доверенному
каналу, повторная проверка и pinned key при login. SSH config/agent выключены,
системные ключи процесса не используются; команды не исполняются. 12s timeout,
без retries. DNS-resolved IP фиксируется на соединение; loopback/link-local/
multicast/metadata запрещены. Private VM разрешаются только explicit CIDR policy
оператора. Firewall/egress deny на management/metadata сети требуется также
на уровне deployment. Повторная проверка использует сохранённый pinned key.
Обновление connection требует нового confirmed fingerprint и proof (120s).

Owner проверяется на всех project/server API; composite FK не допускает чужой
project. API response models не содержат ciphertext/private keys/passwords.
Validation и network errors возвращают очищенные сообщения. Request bodies,
Telegram text, cookies и secret env не должны попадать в proxy/APM logs.
Серверные журналы uvicorn access_log отключены в команде запуска из runbook.

Локальные tests используют synthetic bot token, local Telegram HTTP stub,
изолированную PostgreSQL и ephemeral SSH, никакой production отправки.
PR не делает deploy, publish, доступ к внешним VPS и production migration.
