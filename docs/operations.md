# Запуск и эксплуатация

## Локальная разработка

Требуются Docker, uv 0.13.6 и Node 24.12.0. Python 3.12.16 закреплён
в .python-version; uv установит его при необходимости.

```sh
python3 -m uv sync --frozen
python3 -m uv run python scripts/dev_keys.py
docker compose -p infradeck-dev -f deploy/compose.dev.yaml up -d --wait
cp .env.example .env
```

В .env задайте собственный Telegram bot token/username/webhook secret. Не
используйте bot planerBot: один bot имеет один webhook. Приложение не читает
.env автоматически: импортируйте её только в локальную shell-сессию.

```sh
set -a
. ./.env
set +a
python3 -m uv run python -m infradeck.migrate
python3 -m uv run uvicorn infradeck.main:app --factory --host 127.0.0.1 --port 8187 --no-access-log
```

В другой shell: `npm ci --prefix apps/web`, `npm --prefix apps/web run dev`.
Откройте http://localhost:5187. Без Telegram не обходить OTP: для проверки
интерфейса используйте synthetic E2E harness (`make e2e`), который не является
production entrypoint. /api/docs доступны на backend /docs.

## Тесты

Создайте отдельные БД infradeck_test и infradeck_e2e в локальном контейнере:

```sh
docker exec infradeck-dev-postgres-1 createdb -U infradeck infradeck_test
docker exec infradeck-dev-postgres-1 createdb -U infradeck infradeck_e2e
make backend
make frontend
make e2e
```

Tests очищают только явно заданную TEST_DATABASE_URL/E2E_DATABASE_URL. Не задавать
общую БД. Harness слушает loopback8187/8188, ephemeral SSH и Vite5187; после
проверки процессы останавливаются. В production harness не устанавливается.

## Production checklist оператора

HTTPS reverse proxy → loopback/private API; static SPA fallback to index.html,
/api только к API. Body limit64KiB; HSTS, CSP default-src 'self'; script-src
'self'; style-src 'self' 'unsafe-inline' (Radix positioning); connect-src 'self';
object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'.
Не публиковать PostgreSQL, SSH proxy listener, harness или dev server.

Set INFRADECK_PRODUCTION=true и INFRADECK_ORIGIN=https://ваш-домен. Запустить
отдельным непривилегированным UID с mounted read-only key files и минимальными
DB privileges; deployment secret files и backup keys хранить отдельно от DB.
Обеспечить egress firewall для SSH: deny control-plane/metadata/management;
для private VM явно задать INFRADECK_PRIVATE_CIDRS и маршрут.

Для Telegram задать INFRADECK_TELEGRAM_PROXY=http://telegram-proxy:19840;
закрытый SSH tunnel аналогично planerBot: `ssh -NT -L 0.0.0.0:19840:PRIVATE_SQUID:3128`
в отдельной приватной container network, без ports mapping; отдельные key/known_hosts
InfraDeck read-only (key file доступен UID65532 контейнера, mode0600), StrictHostKeyChecking=yes, IdentitiesOnly=yes,
ExitOnForwardFailure=yes, ServerAliveInterval=30, ServerAliveCountMax=3,
ограниченный authorized_keys permitopen на Squid. Адреса/keys исходных проектов
не копировать. Пример compose overlay: [proxy.yaml](../deploy/proxy.yaml).

Зарегистрировать HTTPS webhook /api/telegram/webhook через setWebhook с
secret_token равным INFRADECK_TELEGRAM_WEBHOOK_SECRET и allowed_updates=['message'].
Это внешнее действие оператор выполняет после настройки своего bot/домена.
До регистрации проверить proxy token-free HTTPS HEAD api.telegram.org через
тот же connector, затем отдельная приёмка отправки на тестовый Telegram account.
Прямой fallback отсутствует; после отказа proxy пользователь видит ошибку, код
не считается отправленным. Не включать log тела Bot API запросов.

Перед upgrade: закрытый pg_dump плюс сохранение RSA/KEK/OTP keys; migration
отдельным управляемым шагом, затем API. Проверить health и login на staging.
Восстановление — новая изолированная БД + соответствующие key files; затем
проверить чтение credentials и test SSH. Не доказывать restore удалением production.

Релизная публикация только по immutable MAJOR.MINOR.PATCH tag коммита из main.
В этой задаче приложение не развёртывается на ваших VPS и реальный bot не меняется.
