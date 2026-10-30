"""Project-scoped inventory and one-use connection proofs."""

import json
import secrets
import time
from typing import Any
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb
from pydantic import ValidationError

from infradeck.crypto import Vault, token_hash
from infradeck.db import Database
from infradeck.errors import Rejected
from infradeck.schemas import CheckResult, Connection, ProjectInput, ServerInput
from infradeck.ssh import SSH

SERVER_COLUMNS = "id,project_id,name,kind,host,port,username,method,fingerprint,checked_at"


def plaintext(connection: Connection) -> str:
    value = connection.model_dump()
    for field in ("password", "private_key", "passphrase", "certificate"):
        value[field] = getattr(connection, field).get_secret_value()
    return json.dumps(value)


class Inventory:
    def __init__(self, db: Database, vault: Vault, ssh: SSH):
        self.db, self.vault, self.ssh = db, vault, ssh

    def project(self, owner: UUID, project_id: UUID) -> dict[str, Any]:
        with self.db.transaction() as tx:
            row = tx.execute(
                "SELECT id,name,description FROM projects WHERE id=%s AND owner_id=%s",
                (project_id, owner),
            ).fetchone()
        if not row:
            raise Rejected("Проект не найден", 404)
        return row

    def projects(self, owner: UUID, offset: int) -> list[dict[str, Any]]:
        with self.db.transaction() as tx:
            return tx.execute(
                "SELECT id,name,description FROM projects WHERE owner_id=%s "
                "ORDER BY id LIMIT 100 OFFSET %s",
                (owner, offset),
            ).fetchall()

    def save_project(
        self, owner: UUID, data: ProjectInput, project_id: UUID | None = None
    ) -> dict[str, Any]:
        with self.db.transaction() as tx:
            if project_id:
                row = tx.execute(
                    "UPDATE projects SET name=%s,description=%s WHERE id=%s "
                    "AND owner_id=%s RETURNING id,name,description",
                    (data.name, data.description, project_id, owner),
                ).fetchone()
            else:
                row = tx.execute(
                    "INSERT INTO projects VALUES (%s,%s,%s,%s) RETURNING id,name,description",
                    (uuid4(), owner, data.name, data.description),
                ).fetchone()
        if not row:
            raise Rejected("Проект не найден", 404)
        return row

    def delete_project(self, owner: UUID, project_id: UUID) -> None:
        with self.db.transaction() as tx:
            count = tx.execute(
                "DELETE FROM projects WHERE id=%s AND owner_id=%s", (project_id, owner)
            ).rowcount
        if not count:
            raise Rejected("Проект не найден", 404)

    def servers(self, owner: UUID, project_id: UUID, offset: int) -> list[dict[str, Any]]:
        self.project(owner, project_id)
        with self.db.transaction() as tx:
            return tx.execute(
                f"SELECT {SERVER_COLUMNS} FROM servers WHERE project_id=%s "
                "AND owner_id=%s ORDER BY id LIMIT 100 OFFSET %s",
                (project_id, owner, offset),
            ).fetchall()

    def server(self, owner: UUID, project_id: UUID, server_id: UUID) -> dict[str, Any]:
        with self.db.transaction() as tx:
            row = tx.execute(
                "SELECT * FROM servers WHERE id=%s AND project_id=%s AND owner_id=%s",
                (server_id, project_id, owner),
            ).fetchone()
        if not row:
            raise Rejected("Сервер не найден", 404)
        return row

    def encryption_key(self, session: dict[str, Any]) -> dict[str, Any]:
        nonce, expires = secrets.token_urlsafe(32), time.time() + 60
        with self.db.transaction() as tx:
            tx.execute("DELETE FROM encryption_nonces WHERE expires_at<%s", (time.time(),))
            tx.execute(
                "INSERT INTO encryption_nonces VALUES (%s,%s,%s)",
                (token_hash(nonce), session["token"], expires),
            )
        return {"key": self.vault.public_key(), "nonce": nonce, "expires_at": expires}

    def check(
        self, session: dict[str, Any], project_id: UUID, compact: str, server_id: UUID | None = None
    ) -> CheckResult:
        owner = session["user_id"]
        self.project(owner, project_id)
        if server_id:
            self.server(owner, project_id, server_id)
        data = self.vault.unwrap(compact)
        nonce = data.get("nonce")
        if not isinstance(nonce, str) or set(data) != {"nonce", "connection"}:
            raise Rejected("Некорректные данные подключения")
        with self.db.transaction() as tx:
            used = tx.execute(
                "DELETE FROM encryption_nonces WHERE nonce=%s "
                "AND session_token=%s AND expires_at>%s RETURNING nonce",
                (token_hash(nonce), session["token"], time.time()),
            ).fetchone()
        if not used:
            raise Rejected("Данные подключения устарели. Повторите проверку", 409)
        try:
            connection = Connection.model_validate(data["connection"])
        except ValidationError:
            raise Rejected("Проверьте поля подключения") from None
        if not connection.fingerprint:
            raise Rejected("Сначала подтвердите SSH fingerprint")
        fingerprint = self.ssh.verify(connection)
        proof, expires = secrets.token_urlsafe(32), time.time() + 120
        aad = f"{owner}:{project_id}:{token_hash(proof)}"
        encrypted = self.vault.seal(plaintext(connection), aad)
        with self.db.transaction() as tx:
            tx.execute("DELETE FROM connection_checks WHERE expires_at<%s", (time.time(),))
            tx.execute(
                "INSERT INTO connection_checks VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (token_hash(proof), owner, project_id, server_id, Jsonb(encrypted), aad, expires),
            )
        return CheckResult(proof=proof, fingerprint=fingerprint, expires_at=expires)

    def save_server(
        self, owner: UUID, project_id: UUID, data: ServerInput, server_id: UUID | None = None
    ) -> dict[str, Any]:
        self.project(owner, project_id)
        if server_id:
            self.server(owner, project_id, server_id)
        if not data.proof and not server_id:
            raise Rejected("Сначала проверьте подключение")
        target_id = server_id or uuid4()
        with self.db.transaction() as tx:
            if data.proof:
                proof = tx.execute(
                    """DELETE FROM connection_checks WHERE proof=%s AND owner_id=%s
                    AND project_id=%s AND server_id IS NOT DISTINCT FROM %s AND expires_at>%s
                    RETURNING *""",
                    (token_hash(data.proof), owner, project_id, server_id, time.time()),
                ).fetchone()
                if not proof:
                    raise Rejected("Проверка устарела. Проверьте подключение повторно", 409)
                connection = Connection.model_validate_json(
                    self.vault.open(proof["encrypted"], proof["aad"])
                )
                aad = f"{owner}:{project_id}:{target_id}"
                encrypted = self.vault.seal(plaintext(connection), aad)
                values = (
                    data.name,
                    data.kind,
                    connection.host,
                    connection.port,
                    connection.username,
                    connection.method,
                    connection.fingerprint,
                    time.time(),
                    Jsonb(encrypted),
                    aad,
                )
                if server_id:
                    row = tx.execute(
                        f"""UPDATE servers SET name=%s,kind=%s,host=%s,port=%s,
                        username=%s,method=%s,fingerprint=%s,checked_at=%s,encrypted=%s,aad=%s
                        WHERE id=%s AND owner_id=%s RETURNING {SERVER_COLUMNS}""",
                        (*values, server_id, owner),
                    ).fetchone()
                else:
                    row = tx.execute(
                        f"""INSERT INTO servers(id,project_id,owner_id,name,kind,
                        host,port,username,method,fingerprint,checked_at,encrypted,aad)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        RETURNING {SERVER_COLUMNS}""",
                        (target_id, project_id, owner, *values),
                    ).fetchone()
            else:
                row = tx.execute(
                    f"UPDATE servers SET name=%s,kind=%s WHERE id=%s AND owner_id=%s "
                    f"RETURNING {SERVER_COLUMNS}",
                    (data.name, data.kind, server_id, owner),
                ).fetchone()
        if not row:
            raise Rejected("Сервер не найден", 404)
        return row

    def recheck(self, owner: UUID, project_id: UUID, server_id: UUID) -> dict[str, Any]:
        server = self.server(owner, project_id, server_id)
        connection = Connection.model_validate_json(
            self.vault.open(server["encrypted"], server["aad"])
        )
        self.ssh.verify(connection)
        with self.db.transaction() as tx:
            # Don't mark a concurrently replaced credential as checked.
            row = tx.execute(
                f"UPDATE servers SET checked_at=%s WHERE id=%s AND owner_id=%s "
                f"AND aad=%s RETURNING {SERVER_COLUMNS}",
                (time.time(), server_id, owner, server["aad"]),
            ).fetchone()
        if not row:
            raise Rejected("Сервер изменён. Повторите проверку", 409)
        return row

    def delete_server(self, owner: UUID, project_id: UUID, server_id: UUID) -> None:
        with self.db.transaction() as tx:
            count = tx.execute(
                "DELETE FROM servers WHERE id=%s AND project_id=%s AND owner_id=%s",
                (server_id, project_id, owner),
            ).rowcount
        if not count:
            raise Rejected("Сервер не найден", 404)
