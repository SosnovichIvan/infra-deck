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

## Production на отдельном Ubuntu VPS

Для v1 используются Docker/Compose и host nginx. [Production compose](../deploy/compose.production.yaml)
публикует только loopback18080; host nginx принимает HTTPS. API/web/tunnel работают
без root, read-only и без capabilities; PostgreSQL, API и proxy port не публикуются.
DB init создаёт отдельные роли owner для миграций и app с DML без CREATE/superuser.
PR smoke проверяет те же Dockerfiles на синтетических credentials; proxy не подключает.

Оператор устанавливает docker.io, docker-compose-v2, nginx, git, openssl и ca-certificates.
Вне Git, в root-only /etc/infradeck, создаются (без перезаписи существующих):

- api.env и migration.env с Settings выше; DSN различается ролями infradeck_app/infradeck_owner;
- kek и otp — по 32 случайных байта, rsa.pem — RSA3072 PKCS8; owner UID10001, mode0600;
- db_admin_password, db_owner_password, db_app_password — независимые случайные пароли, UID70/mode0600;
- proxy_key — отдельный restricted SSH key UID65532/mode0600 и проверенный proxy_known_hosts;
- compose.env с INFRADECK_SQUID_ADDRESS, INFRADECK_PROXY_SSH_TARGET и INFRADECK_PUBLIC_IP; без production адресов в репозитории.

API paths: /run/secrets/kek, /run/secrets/rsa, /run/secrets/otp. Production env-файлы
root0600. SSH account proxy разрешает только local forwarding к приватному Squid,
без shell/TTY/agent/remote forwarding. При отказе tunnel startup не проходит.

Для публичного IPv4 без домена [configure-https.sh](../deploy/configure-https.sh)
выпускает short-lived IP certificate Certbot5.4 через HTTP01 webroot и задаёт
nginx TLS/CSP/body limit. Скрипт предназначен для отдельного сервера: заменяет
стандартный nginx default site. Timer infradeck-certificate проверяет renewal
каждые 6 часов с reload nginx после успешной проверки. Открыты 22/80/443;
DB/18080/19840 снаружи недоступны. Источник: [Let's Encrypt IP certificates](https://letsencrypt.org/2026/03/11/shorter-certs-certbot).

GitHub repository secrets: INFRADECK_VPS_HOST, INFRADECK_DEPLOY_SSH_KEY,
INFRADECK_DEPLOY_KNOWN_HOSTS. Bot token INFRADECK_TELEGRAM_TOKEN хранится отдельно;
он также должен быть установлен в VPS env, из Actions secrets прочитать его нельзя.
Environment production используется для deployment, INFRADECK_DEPLOY_ENABLED=true
включает job. Требования PR/release route сохраняются.

После feature→develop→main и создания числового version tag workflow проверяет
main ancestry и версии manifest, собирает artifacts, затем по pinned SSH запускает
[release.sh](../deploy/release.sh). Скрипт повторно проверяет tag/main, сериализует
deploy lock, строит images только из release checkout, делает pre-upgrade pg_dump,
запускает DB/tunnel, миграции и API/web, проверяет private/HTTPS health и меняет current symlink.
Отдельный configure-egress.sh ограничивает внешний интерфейс API: запрещены обращения
к самому control plane, proxy management IP, metadata и private адресам. Это не затрагивает
внутренние DB/proxy связи или остальные containers; правила восстанавливает systemd unit
после Docker restart. Для private VM потребуется явно согласовать allowed routes и firewall.
Production credentials/keys никогда не попадают в build context. При неудаче
миграции новая API не запускается; DDL forward-only. Ошибки следующих шагов не
обещают автоматического rollback: повторить исправленный release либо восстановить
backup в отдельной БД; не делать destructive down migrations. Старые images/checkouts
сохраняются, глобальный Docker prune не применяется.

Проверки после выкладки: HTTPS certificate/headers, /api/health, SPA и /api/auth/me401,
token-free Telegram HEAD через тот же proxy, getMe для проверки bot identity, setWebhook
с secret_token и getWebhookInfo без вывода token/secret. Реальная доставка OTP требует
регистрации тестового пользователя владельцем; это отдельная проверка от synthetic CI.
Не помещать пароли/OTP в logs. Отдельно сохранять key material вне DB backup и VPS,
проверять restore на изолированной БД, следить за результатами certificate timer.
