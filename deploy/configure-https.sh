#!/usr/bin/env bash
# IP HTTPS bootstrap on an otherwise provisioned Ubuntu host. No app build.
set -euo pipefail
host="${1:?public IPv4 required}"
python3 - "$host" <<'PY'
import ipaddress, sys
assert ipaddress.ip_address(sys.argv[1]).version == 4
assert ipaddress.ip_address(sys.argv[1]).is_global
PY
[[ "$EUID" = 0 ]] || exit 2
install -d /var/www/infradeck-acme /etc/letsencrypt /var/lib/letsencrypt
cat > /etc/nginx/sites-available/infradeck <<'NGINX'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    server_tokens off;
    location /.well-known/acme-challenge/ { root /var/www/infradeck-acme; }
    location / { return 404; }
}
NGINX
rm -f /etc/nginx/sites-enabled/default
ln -sfn /etc/nginx/sites-available/infradeck /etc/nginx/sites-enabled/infradeck
nginx -t
systemctl reload nginx
docker run --rm \
    -v /etc/letsencrypt:/etc/letsencrypt \
    -v /var/lib/letsencrypt:/var/lib/letsencrypt \
    -v /var/www/infradeck-acme:/var/www/infradeck-acme \
    certbot/certbot:v5.4.0 certonly --non-interactive --agree-tos \
    --register-unsafely-without-email --preferred-profile shortlived \
    --webroot -w /var/www/infradeck-acme --ip-address "$host" --cert-name infradeck
cat > /etc/nginx/sites-available/infradeck <<'NGINX'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    server_tokens off;
    location /.well-known/acme-challenge/ { root /var/www/infradeck-acme; }
    location / { return 308 https://PUBLIC_HOST$request_uri; }
}
server {
    listen 443 ssl default_server;
    listen [::]:443 ssl default_server;
    server_name _;
    server_tokens off;
    ssl_certificate /etc/letsencrypt/live/infradeck/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/infradeck/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    client_max_body_size 64k;
    access_log off;
    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'" always;
    add_header X-Content-Type-Options nosniff always;
    add_header Referrer-Policy no-referrer always;
    add_header X-Frame-Options DENY always;
    location / {
        proxy_pass http://127.0.0.1:18080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto https;
        proxy_connect_timeout 5s;
        proxy_read_timeout 40s;
    }
}
NGINX
# Use the configured IP rather than reflecting an untrusted Host in redirects.
sed -i "s/server_name _;/server_name $host;/g; s/PUBLIC_HOST/$host/g" /etc/nginx/sites-available/infradeck
nginx -t
systemctl reload nginx
cat > /etc/systemd/system/infradeck-certificate.service <<'UNIT'
[Unit]
Description=Renew InfraDeck short-lived IP certificate
After=docker.service nginx.service
Requires=docker.service
[Service]
Type=oneshot
ExecStart=/usr/bin/docker run --rm -v /etc/letsencrypt:/etc/letsencrypt -v /var/lib/letsencrypt:/var/lib/letsencrypt -v /var/www/infradeck-acme:/var/www/infradeck-acme certbot/certbot:v5.4.0 renew --quiet --cert-name infradeck
ExecStartPost=/usr/sbin/nginx -t
ExecStartPost=/usr/bin/systemctl reload nginx
UNIT
cat > /etc/systemd/system/infradeck-certificate.timer <<'UNIT'
[Unit]
Description=Check InfraDeck IP certificate every six hours
[Timer]
OnCalendar=*-*-* 00,06,12,18:00:00
RandomizedDelaySec=15m
Persistent=true
[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl enable --now infradeck-certificate.timer
