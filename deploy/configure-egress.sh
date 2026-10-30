#!/usr/bin/env bash
# Source only the API's external interface; internal DB/proxy links stay private.
set -euo pipefail
public_ip="${1:?public VPS IP required}"
proxy_ip="${2:?proxy management IP required}"
api_ip="${3:-172.29.40.10}"
python3 - "$public_ip" "$proxy_ip" "$api_ip" <<'PY'
import ipaddress, sys
for value in sys.argv[1:]:
    assert ipaddress.ip_address(value).version == 4
PY
[[ "$EUID" = 0 ]] || exit 2
iptables -nL DOCKER-USER >/dev/null
if ! iptables -nL INFRADECK-EGRESS >/dev/null 2>&1; then
    iptables -N INFRADECK-EGRESS
fi
for destination in "$public_ip" "$proxy_ip" 127.0.0.0/8 169.254.0.0/16 168.63.129.16 100.100.100.200 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16; do
    if ! iptables -C INFRADECK-EGRESS -d "$destination" -j REJECT 2>/dev/null; then
        iptables -A INFRADECK-EGRESS -d "$destination" -j REJECT
    fi
done
if ! iptables -C DOCKER-USER -s "$api_ip" -j INFRADECK-EGRESS 2>/dev/null; then
    iptables -I DOCKER-USER 1 -s "$api_ip" -j INFRADECK-EGRESS
fi
# Packets addressed to the Docker host traverse INPUT, not FORWARD/DOCKER-USER.
if ! iptables -C INPUT -s "$api_ip" -j INFRADECK-EGRESS 2>/dev/null; then
    iptables -I INPUT 1 -s "$api_ip" -j INFRADECK-EGRESS
fi
