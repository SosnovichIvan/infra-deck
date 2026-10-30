#!/usr/bin/env bash
# Must run inside a disposable Linux network namespace; never in the host netns.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
[[ "$(readlink /proc/self/ns/net)" != "$(readlink /proc/1/ns/net)" ]] || {
    echo 'Use unshare --net for this test' >&2; exit 2;
}
ip link set lo up
ip addr add 172.29.40.10/32 dev lo
ip addr add 203.0.113.10/32 dev lo
iptables -N DOCKER-USER
python3 - <<'PY'
import socket
with socket.socket() as server, socket.socket() as client:
    server.bind(('203.0.113.10', 0)); server.listen()
    client.bind(('172.29.40.10', 0))
    client.settimeout(2)
    client.connect(server.getsockname())
PY
bash "$root/deploy/configure-egress.sh" 203.0.113.10 203.0.113.11
bash "$root/deploy/configure-egress.sh" 203.0.113.10 203.0.113.11
test "$(iptables -S INPUT | grep -c '172.29.40.10/32 -j INFRADECK-EGRESS')" = 1
iptables -C DOCKER-USER -s 172.29.40.10 -j INFRADECK-EGRESS
python3 - <<'PY'
import socket
with socket.socket() as server:
    server.bind(('203.0.113.10', 0)); server.listen()
    with socket.socket() as client:
        client.bind(('172.29.40.10', 0)); client.settimeout(2)
        try:
            client.connect(server.getsockname())
        except OSError:
            pass
        else:
            raise AssertionError('API can reach control-plane host through INPUT')
    # Other sources keep working; the rule is specific to the API egress IP.
    with socket.create_connection(server.getsockname(), timeout=2):
        pass
print('INPUT isolation, FORWARD attachment, source scope and idempotence passed')
PY
