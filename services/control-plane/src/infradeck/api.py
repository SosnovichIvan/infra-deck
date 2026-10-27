"""HTTP adapters and application composition. No persistence queries in routes."""

import hmac
import secrets
from typing import Annotated, Any, cast
from uuid import UUID

from aiogram.types import Update
from fastapi import Depends, FastAPI, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from infradeck.config import Settings
from infradeck.crypto import Vault
from infradeck.db import Database
from infradeck.errors import Rejected
from infradeck.identity import Identity
from infradeck.inventory import Inventory
from infradeck.schemas import (
    AuthState,
    CheckRequest,
    CheckResult,
    Code,
    Connection,
    EncryptionKey,
    Fingerprint,
    Login,
    Me,
    Probe,
    Project,
    ProjectInput,
    Recovery,
    Register,
    Server,
    ServerInput,
)
from infradeck.ssh import SSH
from infradeck.telegram import Telegram


def create_app(
    settings: Settings, identity: Identity | None = None, inventory: Inventory | None = None
) -> FastAPI:
    if identity is None or inventory is None:
        db = Database(settings.database_url.get_secret_value())
        vault = Vault(
            settings.kek_file.read_bytes(),
            settings.rsa_file.read_bytes(),
            settings.otp_key_file.read_bytes(),
        )
        identity = Identity(db, vault, Telegram(settings), settings.telegram_username)
        inventory = Inventory(db, vault, SSH(settings.private_cidrs))
    auth, hosts = identity, inventory
    app = FastAPI(title="InfraDeck API", version="0.1.0")

    @app.exception_handler(Rejected)
    async def rejected(request: Request, exc: Rejected) -> JSONResponse:
        return JSONResponse({"detail": exc.message}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Pydantic error inputs can contain passwords/private keys. Never return them.
        return JSONResponse({"detail": "Проверьте формат и длину полей"}, status_code=422)

    @app.middleware("http")
    async def security(request: Request, call_next: Any) -> Response:
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            try:
                if int(request.headers.get("content-length", "0")) > 65536:
                    return JSONResponse({"detail": "Слишком большой запрос"}, status_code=413)
            except ValueError:
                return JSONResponse({"detail": "Некорректный запрос"}, status_code=400)
            if request.url.path != "/api/telegram/webhook":
                csrf = request.cookies.get("csrf", "")
                if (
                    request.headers.get("origin") != settings.origin
                    or not csrf
                    or not hmac.compare_digest(csrf, request.headers.get("x-csrf-token", ""))
                ):
                    return JSONResponse(
                        {"detail": "Обновите страницу и повторите запрос"}, status_code=403
                    )
                token = request.cookies.get("session", "")
                if token:
                    try:
                        current = await run_in_threadpool(
                            auth.session, token, ("enrollment", "preauth", "full")
                        )
                    except Rejected:
                        return JSONResponse({"detail": "Войдите заново"}, status_code=401)
                    if not hmac.compare_digest(current["csrf"], csrf):
                        return JSONResponse({"detail": "Обновите страницу"}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        return cast(Response, response)

    def cookie(
        response: Response, key: str, value: str, http_only: bool = True, max_age: int = 43200
    ) -> None:
        response.set_cookie(
            key,
            value,
            httponly=http_only,
            secure=settings.production,
            samesite="strict",
            max_age=max_age,
            path="/",
        )

    def authenticated(request: Request) -> dict[str, Any]:
        return auth.session(request.cookies.get("session", ""))

    Session = Annotated[dict[str, Any], Depends(authenticated)]

    def finish(response: Response, result: tuple[str, AuthState], old: str = "") -> AuthState:
        token, state = result
        if old:
            auth.logout(old)
        current = auth.session(token, ("enrollment", "preauth", "full"))
        cookie(response, "session", token, max_age=43200 if state.state == "authenticated" else 600)
        cookie(response, "csrf", current["csrf"], False)
        return state

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/auth/csrf")
    def csrf(request: Request, response: Response) -> dict[str, str]:
        value = secrets.token_urlsafe(32)
        try:
            value = auth.session(
                request.cookies.get("session", ""), ("enrollment", "preauth", "full")
            )["csrf"]
        except Rejected:
            response.delete_cookie("session")
        cookie(response, "csrf", value, False)
        return {"csrf": value}

    @app.post("/api/auth/register", response_model=AuthState)
    def register(data: Register, request: Request, response: Response) -> AuthState:
        return finish(
            response,
            auth.register(data, request.client.host if request.client else ""),
            request.cookies.get("session", ""),
        )

    @app.post("/api/auth/login", response_model=AuthState)
    def login(data: Login, request: Request, response: Response) -> AuthState:
        return finish(
            response,
            auth.login(data, request.client.host if request.client else ""),
            request.cookies.get("session", ""),
        )

    @app.post("/api/auth/send-code", response_model=AuthState)
    def send_code(request: Request) -> AuthState:
        return auth.send_code(request.cookies.get("session", ""))

    @app.post("/api/auth/verify", response_model=AuthState)
    def verify(data: Code, request: Request, response: Response) -> AuthState:
        return finish(response, auth.verify(request.cookies.get("session", ""), data.code))

    @app.post("/api/auth/recover", response_model=AuthState)
    def recover(data: Recovery, request: Request, response: Response) -> AuthState:
        return finish(response, auth.verify(request.cookies.get("session", ""), data.code, True))

    @app.post("/api/auth/logout", status_code=204)
    def logout(request: Request, response: Response) -> None:
        auth.logout(request.cookies.get("session", ""))
        response.delete_cookie("session")
        response.delete_cookie("csrf")

    @app.get("/api/auth/me", response_model=Me)
    def me(session: Session) -> dict[str, Any]:
        return {"id": session["user_id"], "login": session["login"]}

    @app.post("/api/telegram/webhook")
    def telegram_webhook(request: Request, data: dict[str, Any]) -> dict[str, bool]:
        if not hmac.compare_digest(
            request.headers.get("x-telegram-bot-api-secret-token", ""),
            settings.telegram_webhook_secret.get_secret_value(),
        ):
            raise Rejected("Доступ запрещён", 403)
        try:
            update = Update.model_validate(data)
        except ValidationError:
            raise Rejected("Некорректное событие") from None
        message = update.message
        if message and message.from_user and message.text and message.chat.type == "private":
            parts = message.text.split()
            if len(parts) == 2 and parts[0] == "/start" and len(parts[1]) <= 64:
                auth.bind_telegram(
                    update.update_id, message.chat.id, message.from_user.id, parts[1]
                )
        return {"ok": True}

    @app.get("/api/projects", response_model=list[Project])
    def projects(session: Session, offset: int = Query(default=0, ge=0, le=100000)) -> Any:
        return hosts.projects(session["user_id"], offset)

    @app.post("/api/projects", response_model=Project, status_code=201)
    def create_project(data: ProjectInput, session: Session) -> Any:
        return hosts.save_project(session["user_id"], data)

    @app.get("/api/projects/{project_id}", response_model=Project)
    def project(project_id: UUID, session: Session) -> Any:
        return hosts.project(session["user_id"], project_id)

    @app.put("/api/projects/{project_id}", response_model=Project)
    def edit_project(project_id: UUID, data: ProjectInput, session: Session) -> Any:
        return hosts.save_project(session["user_id"], data, project_id)

    @app.delete("/api/projects/{project_id}", status_code=204)
    def delete_project(project_id: UUID, session: Session) -> None:
        hosts.delete_project(session["user_id"], project_id)

    @app.get("/api/encryption-key", response_model=EncryptionKey)
    def encryption_key(session: Session) -> Any:
        return hosts.encryption_key(session)

    @app.post("/api/projects/{project_id}/probe", response_model=Fingerprint)
    def probe(project_id: UUID, data: Probe, session: Session) -> Fingerprint:
        hosts.project(session["user_id"], project_id)
        auth.limit("ssh:" + str(session["user_id"]), 15)
        return Fingerprint(fingerprint=hosts.ssh.probe(data.host, data.port))

    @app.post("/api/projects/{project_id}/checks", response_model=CheckResult)
    def check(project_id: UUID, data: CheckRequest, session: Session) -> CheckResult:
        auth.limit("ssh:" + str(session["user_id"]), 15)
        return hosts.check(session, project_id, data.jwe, data.server_id)

    @app.get("/api/projects/{project_id}/servers", response_model=list[Server])
    def servers(
        project_id: UUID, session: Session, offset: int = Query(default=0, ge=0, le=100000)
    ) -> Any:
        return hosts.servers(session["user_id"], project_id, offset)

    @app.post("/api/projects/{project_id}/servers", response_model=Server, status_code=201)
    def create_server(project_id: UUID, data: ServerInput, session: Session) -> Any:
        return hosts.save_server(session["user_id"], project_id, data)

    @app.put("/api/projects/{project_id}/servers/{server_id}", response_model=Server)
    def edit_server(project_id: UUID, server_id: UUID, data: ServerInput, session: Session) -> Any:
        return hosts.save_server(session["user_id"], project_id, data, server_id)

    @app.delete("/api/projects/{project_id}/servers/{server_id}", status_code=204)
    def delete_server(project_id: UUID, server_id: UUID, session: Session) -> None:
        hosts.delete_server(session["user_id"], project_id, server_id)

    @app.post("/api/projects/{project_id}/servers/{server_id}/recheck", response_model=Server)
    def recheck(project_id: UUID, server_id: UUID, session: Session) -> Any:
        auth.limit("ssh:" + str(session["user_id"]), 15)
        return hosts.recheck(session["user_id"], project_id, server_id)

    schema = app.openapi()
    schema["components"]["schemas"]["Connection"] = Connection.model_json_schema()
    app.openapi_schema = schema
    return app
