"""Identity use cases. All challenge transitions are serialized by session locks."""

import hmac
import secrets
import time
from typing import Any
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from psycopg.errors import UniqueViolation

from infradeck.crypto import Vault, digest, token_hash
from infradeck.db import Database
from infradeck.errors import Rejected
from infradeck.schemas import AuthState, Login, Register
from infradeck.telegram import Telegram

PASSWORDS = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
DUMMY = PASSWORDS.hash(secrets.token_urlsafe(32))


class Identity:
    def __init__(self, db: Database, vault: Vault, telegram: Telegram, username: str):
        self.db, self.vault, self.telegram, self.username = db, vault, telegram, username

    def limit(self, scope: str, maximum: int, window: int = 60) -> None:
        now = time.time()
        with self.db.transaction() as tx:
            row = tx.execute(
                """INSERT INTO rate_limits VALUES (%s,%s,1)
                ON CONFLICT(scope) DO UPDATE SET
                hits=CASE WHEN rate_limits.window_start < %s THEN 1 ELSE rate_limits.hits+1 END,
                window_start=CASE WHEN rate_limits.window_start < %s THEN %s
                             ELSE rate_limits.window_start END RETURNING hits""",
                (token_hash(scope), now, now - window, now - window, now),
            ).fetchone()
        if row and row["hits"] > maximum:
            raise Rejected("Слишком много попыток. Повторите позже", 429)

    def session(self, token: str, kinds: tuple[str, ...] = ("full",)) -> dict[str, Any]:
        with self.db.transaction() as tx:
            row = tx.execute(
                """SELECT s.*,u.login,u.telegram_id FROM sessions s JOIN users u
                ON u.id=s.user_id WHERE token=%s AND expires_at>%s""",
                (token_hash(token), time.time()),
            ).fetchone()
        if not row or row["kind"] not in kinds:
            raise Rejected("Войдите в аккаунт", 401)
        return row

    def _create_session(self, user_id: Any, enrollment: bool) -> tuple[str, AuthState]:
        token, csrf, binding = secrets.token_urlsafe(32), secrets.token_urlsafe(32), None
        now = time.time()
        if enrollment:
            binding = secrets.token_urlsafe(32)
        with self.db.transaction() as tx:
            # Starting a new password-authenticated attempt revokes previous unfinished attempts.
            tx.execute("DELETE FROM sessions WHERE user_id=%s AND kind!='full'", (user_id,))
            tx.execute(
                """INSERT INTO sessions(token,user_id,kind,csrf,expires_at,
                enrollment_token,enrollment_expires) VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (
                    token_hash(token),
                    user_id,
                    "enrollment" if enrollment else "preauth",
                    csrf,
                    now + 600,
                    token_hash(binding) if binding else None,
                    now + 600,
                ),
            )
        if binding:
            return token, AuthState(
                state="enrollment", telegram_url=f"https://t.me/{self.username}?start={binding}"
            )
        return token, AuthState(state="otp")

    def register(self, data: Register, ip: str) -> tuple[str, AuthState]:
        self.limit("register:" + ip, 5, 3600)
        if data.password.get_secret_value() != data.confirmation.get_secret_value():
            raise Rejected("Пароли не совпадают")
        user_id = uuid4()
        try:
            hashed = PASSWORDS.hash(data.password.get_secret_value())
            with self.db.transaction() as tx:
                tx.execute(
                    "INSERT INTO users VALUES (%s,%s,%s,NULL,%s)",
                    (user_id, data.login.lower(), hashed, time.time()),
                )
        except UniqueViolation:
            raise Rejected("Не удалось зарегистрироваться с этим логином", 409) from None
        return self._create_session(user_id, True)

    def login(self, data: Login, ip: str) -> tuple[str, AuthState]:
        self.limit("login-ip:" + ip, 20)
        self.limit("login-user:" + data.login.lower(), 5)
        with self.db.transaction() as tx:
            user = tx.execute(
                "SELECT * FROM users WHERE login=%s", (data.login.lower(),)
            ).fetchone()
        try:
            PASSWORDS.verify(
                user["password_hash"] if user else DUMMY, data.password.get_secret_value()
            )
        except VerificationError:
            raise Rejected("Неверный логин или пароль", 401) from None
        if not user:
            raise Rejected("Неверный логин или пароль", 401)
        return self._create_session(user["id"], user["telegram_id"] is None)

    def send_code(self, token: str) -> AuthState:
        session = self.session(token, ("enrollment", "preauth"))
        user_id, now = session["user_id"], time.time()
        self.limit("otp-send:" + str(user_id), 5, 300)
        code = f"{secrets.randbelow(100000000):08d}"
        with self.db.transaction() as tx:
            row = tx.execute(
                "SELECT * FROM sessions WHERE token=%s FOR UPDATE", (token_hash(token),)
            ).fetchone()
            if not row or not session["telegram_id"]:
                raise Rejected("Сначала привяжите Telegram", 409)
            if row["attempts"] >= 5:
                raise Rejected("Лимит попыток исчерпан. Войдите заново", 429)
            if row["last_sent"] + 30 > now:
                raise Rejected("Повторная отправка доступна через 30 секунд", 429)
            tx.execute(
                """UPDATE sessions SET kind='preauth',otp_digest=NULL,
                otp_expires=NULL,last_sent=%s WHERE token=%s""",
                (now, row["token"]),
            )
        # Network is outside transaction. No active challenge exists during delivery.
        self.telegram.send(
            session["telegram_id"],
            f"InfraDeck: код входа {code}. Действует 30 секунд. Никому не сообщайте код.",
        )
        expires = time.time() + 30
        with self.db.transaction() as tx:
            changed = tx.execute(
                """UPDATE sessions SET otp_digest=%s,otp_expires=%s,
                enrollment_token=NULL WHERE token=%s AND last_sent=%s AND expires_at>%s""",
                (
                    digest(self.vault.otp_key, row["token"] + code),
                    expires,
                    row["token"],
                    now,
                    time.time(),
                ),
            ).rowcount
        if not changed:
            raise Rejected("Сессия устарела. Войдите заново", 401)
        return AuthState(state="otp", expires_at=expires)

    def verify(self, token: str, code: str, recovery: bool = False) -> tuple[str, AuthState]:
        self.session(token, ("preauth",))
        raw, now = secrets.token_urlsafe(32), time.time()
        failure = False
        codes: list[str] = []
        with self.db.transaction() as tx:
            row = tx.execute(
                "SELECT * FROM sessions WHERE token=%s FOR UPDATE", (token_hash(token),)
            ).fetchone()
            if not row or row["kind"] != "preauth" or row["expires_at"] <= now:
                raise Rejected("Сессия устарела. Войдите заново", 401)
            # Lock user as well: first-login recovery issuance must be unique across sessions.
            tx.execute("SELECT id FROM users WHERE id=%s FOR UPDATE", (row["user_id"],))
            valid = False
            if row["attempts"] < 5:
                if recovery:
                    valid = bool(
                        tx.execute(
                            """DELETE FROM recovery_codes WHERE user_id=%s
                        AND digest=%s RETURNING digest""",
                            (row["user_id"], digest(self.vault.otp_key, code)),
                        ).fetchone()
                    )
                else:
                    valid = bool(
                        row["otp_expires"]
                        and row["otp_expires"] > now
                        and row["otp_digest"]
                        and hmac.compare_digest(
                            row["otp_digest"], digest(self.vault.otp_key, row["token"] + code)
                        )
                    )
            if not valid:
                tx.execute(
                    "UPDATE sessions SET attempts=attempts+1 WHERE token=%s", (row["token"],)
                )
                failure = True
            else:
                existing = tx.execute(
                    "SELECT 1 FROM recovery_codes WHERE user_id=%s LIMIT 1", (row["user_id"],)
                ).fetchone()
                if not existing and not recovery:
                    codes = [secrets.token_hex(12) for _ in range(8)]
                    for item in codes:
                        tx.execute(
                            "INSERT INTO recovery_codes VALUES (%s,%s)",
                            (row["user_id"], digest(self.vault.otp_key, item)),
                        )
                tx.execute("DELETE FROM sessions WHERE token=%s", (row["token"],))
                tx.execute(
                    "INSERT INTO sessions(token,user_id,kind,csrf,expires_at) "
                    "VALUES (%s,%s,'full',%s,%s)",
                    (token_hash(raw), row["user_id"], secrets.token_urlsafe(32), now + 43200),
                )
        if failure:
            raise Rejected("Код неверен, истёк или лимит попыток исчерпан", 401)
        return raw, AuthState(state="authenticated", recovery_codes=codes)

    def logout(self, token: str) -> None:
        with self.db.transaction() as tx:
            tx.execute("DELETE FROM sessions WHERE token=%s", (token_hash(token),))

    def bind_telegram(self, update_id: int, chat_id: int, user_id: int, binding: str) -> None:
        if chat_id != user_id or user_id <= 0:
            raise Rejected("Привязка доступна только в личном чате")
        try:
            with self.db.transaction() as tx:
                fresh = tx.execute(
                    "INSERT INTO telegram_updates VALUES (%s,%s) "
                    "ON CONFLICT DO NOTHING RETURNING id",
                    (update_id, time.time()),
                ).fetchone()
                if not fresh:
                    return
                row = tx.execute(
                    """SELECT * FROM sessions WHERE enrollment_token=%s
                    AND enrollment_expires>%s AND kind='enrollment' FOR UPDATE""",
                    (token_hash(binding), time.time()),
                ).fetchone()
                if not row:
                    return
                changed = tx.execute(
                    "UPDATE users SET telegram_id=%s WHERE id=%s "
                    "AND telegram_id IS NULL RETURNING id",
                    (user_id, row["user_id"]),
                ).fetchone()
                if changed:
                    tx.execute(
                        "UPDATE sessions SET enrollment_token=NULL WHERE token=%s", (row["token"],)
                    )
        except UniqueViolation:
            raise Rejected("Telegram уже привязан к другому аккаунту", 409) from None
        if changed:
            self.telegram.send(chat_id, "Telegram привязан к InfraDeck. Вернитесь в браузер.")
