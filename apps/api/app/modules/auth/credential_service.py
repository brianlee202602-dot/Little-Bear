"""Auth credential and password management."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from app.modules.auth.errors import AuthServiceError
from app.modules.auth.password_service import PasswordPolicy, PasswordService
from app.modules.auth.runtime import AuthRuntimeConfig
from app.modules.auth.schemas import AuthContext, AuthUser, CredentialRecord, LoginRecord
from app.modules.auth.utils import as_aware_utc, status_error
from sqlalchemy import text
from sqlalchemy.orm import Session


class CredentialService:
    """Loads credentials, records login attempts, and updates passwords."""

    def __init__(self, *, password_service: PasswordService) -> None:
        self.password_service = password_service

    def load_login_record(
        self,
        session: Session,
        username: str,
        *,
        enterprise_code: str | None = None,
    ) -> LoginRecord:
        normalized_username = username.strip()
        normalized_enterprise_code = enterprise_code.strip() if enterprise_code else None
        if not normalized_username:
            raise AuthServiceError(
                "AUTH_INVALID_CREDENTIALS",
                "username or password is invalid",
                status_code=401,
            )
        enterprise_filter = ""
        params = {"username": normalized_username}
        if normalized_enterprise_code is not None:
            enterprise_filter = "AND lower(e.code) = lower(:enterprise_code)"
            params["enterprise_code"] = normalized_enterprise_code
        rows = session.execute(
            text(
                f"""
                SELECT
                    u.id::text AS user_id,
                    u.enterprise_id::text AS enterprise_id,
                    u.username,
                    u.display_name,
                    u.email,
                    u.phone,
                    u.status AS user_status,
                    uc.password_hash,
                    uc.password_alg,
                    uc.failed_login_count,
                    uc.locked_until,
                    uc.force_change_password
                FROM users u
                JOIN enterprises e ON e.id = u.enterprise_id
                JOIN user_credentials uc ON uc.user_id = u.id
                WHERE lower(u.username) = lower(:username)
                  {enterprise_filter}
                  AND u.deleted_at IS NULL
                LIMIT 2
                """
            ),
            params,
        ).all()
        if not rows:
            raise AuthServiceError(
                "AUTH_INVALID_CREDENTIALS",
                "username or password is invalid",
                status_code=401,
            )
        if len(rows) > 1:
            raise AuthServiceError(
                "AUTH_ENTERPRISE_REQUIRED",
                "enterprise code is required for duplicated username",
                status_code=400,
                details={"username": normalized_username},
            )

        data = rows[0]._mapping
        return LoginRecord(
            user=AuthUser(
                id=data["user_id"],
                enterprise_id=data["enterprise_id"],
                username=data["username"],
                display_name=data["display_name"],
                email=data["email"],
                phone=data["phone"],
                status=data["user_status"],
            ),
            credential=CredentialRecord(
                password_hash=data["password_hash"],
                password_alg=data["password_alg"],
                failed_login_count=int(data["failed_login_count"] or 0),
                locked_until=data["locked_until"],
                force_change_password=bool(data["force_change_password"]),
            ),
        )

    def load_credential(
        self,
        session: Session,
        user_id: str,
        *,
        for_update: bool,
    ) -> CredentialRecord:
        query = """
            SELECT
                password_hash,
                password_alg,
                failed_login_count,
                locked_until,
                force_change_password
            FROM user_credentials
            WHERE user_id = :user_id
        """
        if for_update:
            query += " FOR UPDATE"
        row = session.execute(text(query), {"user_id": user_id}).one_or_none()
        if row is None:
            raise AuthServiceError(
                "AUTH_CREDENTIAL_MISSING",
                "user credential is missing",
                status_code=500,
            )
        data = row._mapping
        return CredentialRecord(
            password_hash=data["password_hash"],
            password_alg=data["password_alg"],
            failed_login_count=int(data["failed_login_count"] or 0),
            locked_until=data["locked_until"],
            force_change_password=bool(data["force_change_password"]),
        )

    def assert_user_can_login(self, record: LoginRecord) -> None:
        if record.user.status != "active":
            raise status_error(record.user.status)
        locked_until = record.credential.locked_until
        if locked_until is not None and as_aware_utc(locked_until) > datetime.now(UTC):
            raise AuthServiceError(
                "AUTH_ACCOUNT_LOCKED",
                "account is temporarily locked",
                status_code=423,
                details={"locked_until": as_aware_utc(locked_until).isoformat()},
            )

    def record_failed_login(
        self,
        session: Session,
        user_id: str,
        auth_config: dict[str, Any],
    ) -> None:
        limit = int(auth_config.get("login_failure_limit", 5))
        lock_minutes = int(auth_config.get("lock_minutes", 15))
        session.execute(
            text(
                """
                UPDATE user_credentials
                SET
                    failed_login_count = failed_login_count + 1,
                    locked_until = CASE
                        WHEN failed_login_count + 1 >= :limit
                        THEN now() + (:lock_minutes * interval '1 minute')
                        ELSE locked_until
                    END,
                    updated_at = now()
                WHERE user_id = :user_id
                """
            ),
            {"user_id": user_id, "limit": limit, "lock_minutes": lock_minutes},
        )

    def record_successful_login(self, session: Session, user_id: str) -> None:
        session.execute(
            text(
                """
                UPDATE user_credentials
                SET failed_login_count = 0, locked_until = null, updated_at = now()
                WHERE user_id = :user_id
                """
            ),
            {"user_id": user_id},
        )
        session.execute(
            text("UPDATE users SET last_login_at = now(), updated_at = now() WHERE id = :user_id"),
            {"user_id": user_id},
        )

    def change_current_password(
        self,
        session: Session,
        *,
        access_token: str,
        old_password: str,
        new_password: str,
        load_auth_runtime: Callable[[Session], AuthRuntimeConfig],
        authenticate_access_token: Callable[..., AuthContext],
        load_credential: Callable[..., CredentialRecord],
    ) -> None:
        auth_runtime = load_auth_runtime(session)
        auth_config = auth_runtime.auth_config
        auth_context = authenticate_access_token(
            session,
            access_token=access_token,
            required_scope="auth:password:update:self",
            auth_runtime=auth_runtime,
        )
        credential = load_credential(session, auth_context.user.id, for_update=True)
        if not self.password_service.verify(credential.password_hash, old_password):
            raise AuthServiceError(
                "AUTH_INVALID_CREDENTIALS",
                "old password is invalid",
                status_code=401,
            )
        self.password_service.validate_policy(
            new_password,
            PasswordPolicy.from_auth_config(auth_config),
        )
        password_hash = self.password_service.hash(new_password)
        session.execute(
            text(
                """
                UPDATE user_credentials
                SET
                    password_hash = :password_hash,
                    password_alg = 'argon2id',
                    password_updated_at = now(),
                    force_change_password = false,
                    failed_login_count = 0,
                    locked_until = null,
                    updated_at = now()
                WHERE user_id = :user_id
                """
            ),
            {"user_id": auth_context.user.id, "password_hash": password_hash},
        )
        session.execute(
            text(
                """
                UPDATE jwt_tokens
                SET status = 'revoked', revoked_at = now()
                WHERE subject_user_id = :user_id
                  AND status = 'active'
                  AND jti <> :current_jti
                """
            ),
            {"user_id": auth_context.user.id, "current_jti": auth_context.token_jti},
        )
