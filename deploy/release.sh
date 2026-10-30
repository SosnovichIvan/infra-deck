#!/usr/bin/env bash
# Run as root after installing Docker/Compose and provisioning /etc/infradeck.
# This script neither generates nor replaces production keys.
set -euo pipefail
tag="${1:?MAJOR.MINOR.PATCH tag required}"
[[ "$tag" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]] || exit 2
[[ "$EUID" = 0 ]] || { echo 'Run as root' >&2; exit 2; }
exec 9>/run/lock/infradeck-deploy.lock
flock -n 9 || { echo 'Another InfraDeck deployment is active' >&2; exit 1; }
export INFRADECK_CONFIG_DIR=/etc/infradeck
export RELEASE_TAG="$tag"
set -a
# Root-owned file: only nonsecret Compose parameters, no shell input from a PR.
. /etc/infradeck/compose.env
set +a
install -d -m 700 /opt/infradeck/releases /var/backups/infradeck
release="/opt/infradeck/releases/$tag"
if [[ ! -d "$release/.git" ]]; then
    git clone --branch "$tag" --single-branch https://github.com/SosnovichIvan/infra-deck.git "$release"
fi
cd "$release"
git fetch origin main
git merge-base --is-ancestor HEAD FETCH_HEAD
test "$(git describe --tags --exact-match)" = "$tag"
test -z "$(git status --porcelain --untracked-files=no)"
python3 - "$tag" <<'PY'
import json, sys, tomllib
assert tomllib.load(open('pyproject.toml', 'rb'))['project']['version'] == sys.argv[1]
assert json.load(open('apps/web/package.json'))['version'] == sys.argv[1]
PY
compose=(docker compose -p infradeck -f deploy/compose.production.yaml)
"${compose[@]}" config -q
"${compose[@]}" build --pull
if docker inspect infradeck-db-1 >/dev/null 2>&1; then
    umask 077
    docker exec infradeck-db-1 pg_dump -U postgres -Fc infradeck > "/var/backups/infradeck/pre-$tag-$(date -u +%Y%m%dT%H%M%SZ).dump"
fi
"${compose[@]}" up -d --wait db telegram-proxy
bash deploy/configure-egress.sh "${INFRADECK_PUBLIC_IP:?public IP required}" \
    "${INFRADECK_PROXY_SSH_TARGET#*@}" "${INFRADECK_API_EGRESS_IP:-172.29.40.10}"
"${compose[@]}" --profile tools run --rm --no-deps migrate
"${compose[@]}" up -d --wait api web
curl --fail --silent --max-time 10 http://127.0.0.1:18080/api/health >/dev/null
origin="$(sed -n 's/^INFRADECK_ORIGIN=//p' /etc/infradeck/api.env)"
curl --fail --silent --proto '=https' --max-time 10 "$origin/api/health" >/dev/null
ln -sfn "$release" /opt/infradeck/current
cat > /etc/systemd/system/infradeck-egress.service <<UNIT
[Unit]
Description=InfraDeck API egress restrictions
After=docker.service
Requires=docker.service
PartOf=docker.service
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/opt/infradeck/current/deploy/configure-egress.sh $INFRADECK_PUBLIC_IP ${INFRADECK_PROXY_SSH_TARGET#*@} ${INFRADECK_API_EGRESS_IP:-172.29.40.10}
[Install]
WantedBy=docker.service
UNIT
systemctl daemon-reload
systemctl enable --now infradeck-egress.service
bash deploy/backup.sh
cat > /etc/systemd/system/infradeck-backup.service <<'UNIT'
[Unit]
Description=InfraDeck PostgreSQL backup
After=docker.service
Requires=docker.service
[Service]
Type=oneshot
ExecStart=/opt/infradeck/current/deploy/backup.sh
UNIT
cat > /etc/systemd/system/infradeck-backup.timer <<'UNIT'
[Unit]
Description=Daily InfraDeck PostgreSQL backup
[Timer]
OnCalendar=*-*-* 03:30:00
RandomizedDelaySec=15m
Persistent=true
[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl enable --now infradeck-backup.timer
docker image inspect "infradeck-api:$tag" "infradeck-web:$tag" "infradeck-proxy:$tag" \
    --format '{{.RepoTags}} {{.Id}}' > "/opt/infradeck/releases/$tag/images.txt"
echo "InfraDeck $tag passed private and HTTPS health checks"
