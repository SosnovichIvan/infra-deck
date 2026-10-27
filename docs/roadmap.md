# Задачи первого релиза

- [x] Контракты API, модель данных и первая PostgreSQL migration.
- [x] Регистрация, Argon2id, tenant/owner isolation, CSRF/session cookies.
- [x] Привязка Telegram через authenticated webhook и numeric Telegram ID.
- [x] Логин/пароль + одноразовый 30-секундный Telegram OTP, форма и resend.
- [x] Серверные лимиты, atomic one-use OTP, delivery failure, recovery codes.
- [x] Проекты: список карточек, создание, редактирование, удаление.
- [x] Серверы в проекте: CRUD, VPS/VM, password/key/certificate.
- [x] SSH host key confirmation, authentication, short-lived one-use proof.
- [x] JWE browser envelope, session nonce, AEAD storage, redacted outputs.
- [x] Dark/light Tailwind UI, shared selects, responsive and keyboard interaction.
- [x] Локальные unit/integration/contract/browser проверки и блокирующий CI (см. quality).
- [ ] Получить успешный удалённый Quality gate в PR.
- [ ] Подключить собственный Telegram bot/webhook/proxy и выполнить production приёмку.
- [ ] Выпустить версионный тег из main после успешного PR-процесса.

Эксплуатационная настройка требует отдельных секретов InfraDeck; credentials
из planerBot/vpn_proxy_server не копируются. Работы над будущими agents,
Grafana, resource telemetry и migrations сервисов не входят в этот выпуск.
