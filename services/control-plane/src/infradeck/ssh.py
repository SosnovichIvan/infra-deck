"""Bounded, pinned SSH authentication; never executes a shell command."""

import asyncio
import ipaddress

import asyncssh
import dns.exception
import dns.resolver

from infradeck.errors import Rejected
from infradeck.schemas import Connection


class SSH:
    def __init__(self, private_cidrs: str = ""):
        self.networks = [
            ipaddress.ip_network(cidr.strip()) for cidr in private_cidrs.split(",") if cidr.strip()
        ]

    def address(self, host: str, port: int) -> str:
        try:
            addresses = [str(ipaddress.ip_address(host))]
        except ValueError:
            addresses = []
            for family in ("A", "AAAA"):
                try:
                    addresses.extend(
                        str(record)
                        for record in dns.resolver.resolve(host, family, lifetime=3, search=False)
                    )
                except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
                    continue
                except dns.exception.DNSException:
                    raise Rejected("Не удалось определить адрес сервера") from None
        result = []
        for address in addresses:
            ip = ipaddress.ip_address(address)
            forbidden = (
                ip.is_loopback
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_unspecified
                or ip.is_reserved
                or str(ip) == "168.63.129.16"
                or getattr(ip, "ipv4_mapped", None)
            )
            if forbidden or not (ip.is_global or any(ip in network for network in self.networks)):
                raise Rejected("Адрес не разрешён сетевой политикой")
            result.append(str(ip))
        if not result:
            raise Rejected("Не удалось определить адрес сервера")
        return result[0]

    async def _key(self, address: str, port: int) -> asyncssh.SSHKey:
        key = await asyncssh.get_server_host_key(address, port, config=None)
        if key is None:
            raise Rejected("Сервер не предоставил SSH-ключ")
        return key

    async def _run(self, host: str, port: int, connection: Connection | None) -> str:
        try:
            async with asyncio.timeout(12):
                address = await asyncio.to_thread(self.address, host, port)
                key = await self._key(address, port)
                fingerprint = key.get_fingerprint()
                if connection is not None:
                    if fingerprint != connection.fingerprint:
                        raise Rejected("SSH-ключ сервера изменился. Сверьте fingerprint")
                    client_keys = []
                    if connection.method != "password":
                        private = asyncssh.import_private_key(
                            connection.private_key.get_secret_value(),
                            passphrase=connection.passphrase.get_secret_value() or None,
                        )
                        if connection.method == "certificate":
                            cert = asyncssh.import_certificate(
                                connection.certificate.get_secret_value()
                            )
                            client_keys.append(asyncssh.load_keypairs([(private, cert)])[0])
                        else:
                            client_keys.append(asyncssh.load_keypairs([private])[0])
                    elif not connection.password.get_secret_value():
                        raise Rejected("Введите пароль SSH")
                    async with asyncssh.connect(
                        address,
                        config=None,
                        port=port,
                        username=connection.username,
                        password=(
                            connection.password.get_secret_value()
                            if connection.method == "password"
                            else None
                        ),
                        client_keys=client_keys,
                        known_hosts=([key], [], []),
                        agent_path=None,
                        preferred_auth=(
                            "password" if connection.method == "password" else "publickey"
                        ),
                        connect_timeout=10,
                        login_timeout=10,
                    ):
                        pass
                return fingerprint
        except (asyncssh.Error, OSError, TimeoutError, ValueError):
            raise Rejected("Не удалось подключиться по SSH. Проверьте доступ и реквизиты") from None

    def probe(self, host: str, port: int) -> str:
        return asyncio.run(self._run(host, port, None))

    def verify(self, connection: Connection) -> str:
        return asyncio.run(self._run(connection.host, connection.port, connection))
