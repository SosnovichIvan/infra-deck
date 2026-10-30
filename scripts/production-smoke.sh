#!/usr/bin/env bash
# Isolated verification only: fake credentials, no external bot/SSH traffic.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
export RELEASE_TAG=verification
export INFRADECK_CONFIG_DIR
INFRADECK_CONFIG_DIR="$(mktemp -d)"
export INFRADECK_SQUID_ADDRESS=squid.invalid
export INFRADECK_PROXY_SSH_TARGET=restricted@proxy.invalid
compose=(docker compose -p infradeck-production-smoke -f deploy/compose.production.yaml)
cleanup() {
    status=$?
    if [[ "$status" != 0 ]]; then
        "${compose[@]}" logs --tail 80 || true
    fi
    "${compose[@]}" --profile tools down -v --remove-orphans || true
    rm -rf "$INFRADECK_CONFIG_DIR"
    exit "$status"
}
trap cleanup EXIT
touch "$INFRADECK_CONFIG_DIR/api.env" "$INFRADECK_CONFIG_DIR/migration.env"
"${compose[@]}" build
docker run --rm -i --user 0:0 -e "HOST_UID=$(id -u)" -e "HOST_GID=$(id -g)" -v "$INFRADECK_CONFIG_DIR:/keys" \
    infradeck-api:verification python - <<'PY'
import os
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
root = Path('/keys')
for name in ('kek', 'otp'):
    (root / name).write_bytes(os.urandom(32))
(root / 'rsa.pem').write_bytes(rsa.generate_private_key(public_exponent=65537, key_size=3072).private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
for role in ('admin', 'owner', 'app'):
    (root / f'db_{role}_password').write_text('synthetic-only-password')
for name in ('proxy_key', 'proxy_known_hosts'):
    (root / name).write_text('unused: proxy is never started in this smoke test')
common = '''INFRADECK_ORIGIN=https://localhost
INFRADECK_PRODUCTION=true
INFRADECK_KEK_FILE=/run/secrets/kek
INFRADECK_RSA_FILE=/run/secrets/rsa
INFRADECK_OTP_KEY_FILE=/run/secrets/otp
INFRADECK_TELEGRAM_TOKEN=123456789:synthetic-only-token
INFRADECK_TELEGRAM_USERNAME=infradeck_test_bot
INFRADECK_TELEGRAM_WEBHOOK_SECRET=synthetic-only-webhook-secret-32-chars
INFRADECK_TELEGRAM_PROXY=http://telegram-proxy:19840
'''
for name, role in [('api.env', 'app'), ('migration.env', 'owner')]:
    (root / name).write_text(common + f'INFRADECK_DATABASE_URL=postgresql://infradeck_{role}:synthetic-only-password@db/infradeck\n')
for path in root.iterdir():
    uid = 70 if path.name.startswith('db_') else 10001
    gid = uid
    if path.name.endswith('.env'):
        uid, gid = int(os.environ['HOST_UID']), int(os.environ['HOST_GID'])
    os.chown(path, uid, gid)
    path.chmod(0o600)
PY
"${compose[@]}" up -d --wait db
"${compose[@]}" --profile tools run --rm --no-deps migrate
# Re-running the migration must preserve the already initialized schema.
"${compose[@]}" --profile tools run --rm --no-deps migrate
"${compose[@]}" up -d --no-deps --wait api
"${compose[@]}" up -d --no-deps --wait web
"${compose[@]}" exec -T api python - <<'PY'
import os
import psycopg
assert os.getuid() == 10001
with psycopg.connect(os.environ['INFRADECK_DATABASE_URL']) as db:
    assert db.execute('SELECT count(*) FROM projects').fetchone() == (0,)
    assert db.execute("SELECT rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname = current_user").fetchone() == (False, False, False)
    assert db.execute("SELECT has_schema_privilege(current_user, 'public', 'CREATE')").fetchone() == (False,)
PY
curl --fail --silent http://127.0.0.1:18080/ | grep -q 'id="root"'
curl --fail --silent http://127.0.0.1:18080/projects/example | grep -q 'id="root"'
curl --fail --silent http://127.0.0.1:18080/api/health | grep -q 'ok'
test "$(curl --silent --output /dev/null --write-out '%{http_code}' http://127.0.0.1:18080/api/auth/me)" = 401
echo 'Production images, migrations, least-privilege DB role, SPA and API smoke passed'
