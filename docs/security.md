# Безопасность

Это требования к реализации, а не заявление о готовой защите приложения.

Учётные записи: login + password, registration дополнительно password confirmation.
Пароли хешируются Argon2id с индивидуальной salt; параметры выбираются и
проверяются на целевой машине. Подтверждение пароля не сохраняется.
Сессии серверные, cookie Secure/HttpOnly/SameSite, rotation и expiry;
state-changing запросы защищаются от CSRF. Rate limit входа/регистрации,
ограничение длины входов и одинаковые ошибки аутентификации.

Передача: HTTPS для всего browser API. Логин и пароль входа защищены TLS;
самодельное browser hashing не заменяет хеширование пароля на сервере.
Для SSH/API credentials применяется дополнительно стандартный JWE envelope
через проверенную библиотеку и опубликованный versioned public encryption key.
Алгоритмы allowlisted, key ID/expiry проверяются, request ID и tenant связываются
с authenticated request и защищаются от replay. Ключ API не хранится в JS как
секрет. Этот слой не защищает от XSS и не является E2E от самого backend:
worker должен расшифровать credential для выполнения разрешённой операции.

Хранение: envelope encryption с AEAD, отдельный data key, key version и AAD
(tenant/host/credential ID). KEK находится в KMS/Vault вне БД и её backups.
Backend получает минимум права decrypt по роли; frontend получает только
masked metadata. Нужны rotation, revoke, re-encryption и restore test с KMS.
Нельзя хранить plaintext, общий статический ключ в Git или secrets в логах,
traces, errors, crash dumps и тестовых артефактах. Backups зашифрованы отдельно.

Установка агента: адрес/порт/SSH account проходят policy validation; host key
pinning, сверка fingerprint по доверенному каналу. Worker изолирован от
control-plane credentials, cloud metadata endpoints и внутренних management
сетей; private VM допускаются только через явную network policy. Запрещены
shell interpolation и blind trust-on-first-use. Доступ bootstrap ограничен
установкой конкретного проверенного пакета; root не используется для постоянной
работы агента. Обновления подписаны, версия и digest проверяются.

Agent: одноразовый короткоживущий enrollment token, привязка tenant/host,
mTLS после enrollment, rotation/revocation, persistent command IDs и replay
protection. Исходящее соединение облегчает NAT/private VM. Привилегированные
операции выделены в минимальный helper с allowlist; метрики работают без root.

Grafana: dashboard UID не является авторизацией. Backend проверяет tenant,
ограничивает datasource queries и не отправляет Grafana admin tokens в browser.
Начальный вариант — авторизованная ссылка; iframe только после отдельной
проверки SSO, CSP/frame policy и изоляции данных. Anonymous dashboards запрещены.

Миграция: права на оба узла, preflight, подтверждение плана, secret references,
backup/restore evidence и точка cutover. Не удалять source до проверки target
и истечения retention. Stateful данные требуют отдельного consistency protocol.

До выпуска обязательны негативные тесты: чужой tenant/host/dashboard,
неверный host key, подмена команды, expired/replayed enrollment, утечка секретов,
недоступный KMS, повтор cutover, отказ посередине операции и восстановление.
