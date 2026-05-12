"""Auth Service P0 实现。

P0 目标是支撑管理后台登录和后续配置管理 API：本地账号密码登录、access/refresh
JWT 签发、refresh rotation、当前用户加载和会话吊销。资源级权限仍由后续
Permission Service 承担，这里只做 token 类型、jti 状态和 scope 粗校验。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.modules.auth.errors import AuthServiceError
from app.modules.auth.password_service import PasswordPolicy, PasswordService
from app.modules.auth.runtime import (
    GLOBAL_AUTH_RUNTIME_CONFIG_PROVIDER,
    AuthRuntimeConfig,
    AuthRuntimeConfigProvider,
)
from app.modules.auth.schemas import (
    AuthContext,
    AuthDepartment,
    AuthRole,
    AuthUser,
    CredentialRecord,
    LoginRecord,
    TokenPair,
)
from app.modules.config.errors import ConfigServiceError
from app.modules.config.service import ConfigService
from app.modules.secrets.service import SecretStoreError, SecretStoreService
from app.shared.jwt import JwtError, decode_hs256, encode_hs256
from sqlalchemy import text
from sqlalchemy.orm import Session

BASE_USER_SCOPES = ("auth:session", "auth:password:update:self")


class AuthService:
    """本地账号认证、JWT 生命周期和当前用户上下文。"""

    def __init__(
        self,
        *,
        password_service: PasswordService | None = None,
        config_service: ConfigService | None = None,
        secret_store: SecretStoreService | None = None,
        runtime_config_provider: AuthRuntimeConfigProvider | None = None,
    ) -> None:
        self.password_service = password_service or PasswordService()
        self.config_service = config_service or ConfigService()
        self.secret_store = secret_store or SecretStoreService()
        self.runtime_config_provider = (
            runtime_config_provider or GLOBAL_AUTH_RUNTIME_CONFIG_PROVIDER
        )

    def create_session(
        self,
        session: Session,
        *,
        username: str,
        password: str,
        enterprise_code: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TokenPair:
        auth_runtime = self._load_auth_runtime(session)
        auth_config = auth_runtime.auth_config
        record = self._load_login_record(session, username, enterprise_code=enterprise_code)
        self._assert_user_can_login(record)

        if not self.password_service.verify(record.credential.password_hash, password):
            self._record_failed_login(session, record.user.id, auth_config)
            raise AuthServiceError(
                "AUTH_INVALID_CREDENTIALS",
                "username or password is invalid",
                status_code=401,
            )

        user = self._load_user_context(session, record.user.id)
        if user.status != "active":
            raise _status_error(user.status)

        self._record_successful_login(session, user.id)
        return self._issue_token_pair(
            session,
            user=user,
            auth_runtime=auth_runtime,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def refresh_session(
        self,
        session: Session,
        *,
        refresh_token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TokenPair:
        auth_runtime = self._load_auth_runtime(session)
        claims = self._decode_token(session, refresh_token, auth_runtime, token_type="refresh")
        refresh_jti = _required_str_claim(claims, "jti")
        subject_user_id = _required_str_claim(claims, "sub")
        enterprise_id = _required_str_claim(claims, "enterprise_id")

        row = self._load_token_row(session, refresh_jti, for_update=True)
        self._assert_token_row_active(
            session,
            row,
            token_type="refresh",
            subject_user_id=subject_user_id,
            enterprise_id=enterprise_id,
        )

        user = self._load_user_context(session, subject_user_id)
        if user.status != "active":
            raise _status_error(user.status)

        pair = self._issue_token_pair(
            session,
            user=user,
            auth_runtime=auth_runtime,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        session.execute(
            text(
                """
                UPDATE jwt_tokens
                SET status = 'used', used_at = now(), replaced_by_jti = :replaced_by_jti
                WHERE jti = :jti AND status = 'active'
                """
            ),
            {"jti": refresh_jti, "replaced_by_jti": pair.refresh_jti},
        )
        return pair

    def authenticate_access_token(
        self,
        session: Session,
        *,
        access_token: str,
        required_scope: str | None = None,
        auth_runtime: AuthRuntimeConfig | None = None,
    ) -> AuthContext:
        auth_runtime = auth_runtime or self._load_auth_runtime(session)
        claims = self._decode_token(session, access_token, auth_runtime, token_type="access")
        access_jti = _required_str_claim(claims, "jti")
        subject_user_id = _required_str_claim(claims, "sub")
        enterprise_id = _required_str_claim(claims, "enterprise_id")

        row = self._load_token_row(session, access_jti, for_update=False)
        self._assert_token_row_active(
            session,
            row,
            token_type="access",
            subject_user_id=subject_user_id,
            enterprise_id=enterprise_id,
        )

        token_scopes = _normalize_scopes(claims.get("scopes"))
        user = self._load_user_context(session, subject_user_id)
        if user.status != "active":
            raise _status_error(user.status)

        current_scopes = user.scopes
        if required_scope and (
            not _has_scope(token_scopes, required_scope)
            or not _has_scope(current_scopes, required_scope)
        ):
            raise AuthServiceError(
                "AUTH_SCOPE_FORBIDDEN",
                "current user does not include required scope",
                status_code=403,
                details={
                    "required_scope": required_scope,
                    "token_scope_allowed": _has_scope(token_scopes, required_scope),
                    "current_scope_allowed": _has_scope(current_scopes, required_scope),
                },
            )

        return AuthContext(
            user=user,
            token_jti=access_jti,
            token_type="access",
            scopes=_effective_scopes(token_scopes, current_scopes),
            claims=claims,
        )

    def revoke_current_session(self, session: Session, *, access_token: str) -> None:
        auth_runtime = self._load_auth_runtime(session)
        claims = self._decode_token(session, access_token, auth_runtime, token_type="access")
        access_jti = _required_str_claim(claims, "jti")
        subject_user_id = _required_str_claim(claims, "sub")
        enterprise_id = _required_str_claim(claims, "enterprise_id")
        session_id = claims.get("sid")

        row = self._load_token_row(session, access_jti, for_update=True)
        self._assert_token_row_active(
            session,
            row,
            token_type="access",
            subject_user_id=subject_user_id,
            enterprise_id=enterprise_id,
        )
        if not isinstance(session_id, str) or not session_id:
            session.execute(
                text(
                    """
                    UPDATE jwt_tokens
                    SET status = 'revoked', revoked_at = now()
                    WHERE jti = :jti
                      AND subject_user_id = :subject_user_id
                      AND enterprise_id = :enterprise_id
                      AND status = 'active'
                    """
                ),
                {
                    "jti": access_jti,
                    "subject_user_id": subject_user_id,
                    "enterprise_id": enterprise_id,
                },
            )
            return

        session.execute(
            text(
                """
                UPDATE jwt_tokens
                SET status = 'revoked', revoked_at = now()
                WHERE status = 'active'
                  AND subject_user_id = :subject_user_id
                  AND enterprise_id = :enterprise_id
                  AND metadata_json ->> 'session_id' = :session_id
                """
            ),
            {
                "session_id": session_id,
                "subject_user_id": subject_user_id,
                "enterprise_id": enterprise_id,
            },
        )

    def change_current_password(
        self,
        session: Session,
        *,
        access_token: str,
        old_password: str,
        new_password: str,
    ) -> None:
        auth_runtime = self._load_auth_runtime(session)
        auth_config = auth_runtime.auth_config
        auth_context = self.authenticate_access_token(
            session,
            access_token=access_token,
            required_scope="auth:password:update:self",
            auth_runtime=auth_runtime,
        )
        credential = self._load_credential(session, auth_context.user.id, for_update=True)
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
        # 改密后吊销该用户其它 active token，保留当前 access token 到自然过期。
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

    def _load_auth_runtime(self, session: Session) -> AuthRuntimeConfig:
        try:
            return self.runtime_config_provider.get(
                session,
                config_service=self.config_service,
                secret_store=self.secret_store,
            )
        except ConfigServiceError as exc:
            raise AuthServiceError(
                exc.error_code,
                exc.message,
                status_code=503,
                retryable=exc.retryable,
                details=exc.details,
            ) from exc
        except SecretStoreError as exc:
            raise AuthServiceError(
                "AUTH_JWT_SIGNING_KEY_UNAVAILABLE",
                "jwt signing key cannot be loaded",
                status_code=503,
                retryable=True,
                details={"error_type": exc.__class__.__name__},
            ) from exc
        except RuntimeError as exc:
            raise AuthServiceError(
                "AUTH_JWT_SIGNING_KEY_MISSING",
                str(exc),
                status_code=503,
                retryable=True,
            ) from exc

    def _load_login_record(
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

    def _load_credential(
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

    def _assert_user_can_login(self, record: LoginRecord) -> None:
        if record.user.status != "active":
            raise _status_error(record.user.status)
        locked_until = record.credential.locked_until
        if locked_until is not None and _as_aware_utc(locked_until) > datetime.now(UTC):
            raise AuthServiceError(
                "AUTH_ACCOUNT_LOCKED",
                "account is temporarily locked",
                status_code=423,
                details={"locked_until": _as_aware_utc(locked_until).isoformat()},
            )

    def _record_failed_login(
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

    def _record_successful_login(self, session: Session, user_id: str) -> None:
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

    def _load_user_context(self, session: Session, user_id: str) -> AuthUser:
        user_row = session.execute(
            text(
                """
                SELECT
                    id::text AS user_id,
                    enterprise_id::text AS enterprise_id,
                    username,
                    display_name,
                    email,
                    phone,
                    status
                FROM users
                WHERE id = :user_id AND deleted_at IS NULL
                """
            ),
            {"user_id": user_id},
        ).one_or_none()
        if user_row is None:
            raise AuthServiceError("AUTH_USER_NOT_FOUND", "user is not found", status_code=401)

        user_data = user_row._mapping
        roles = self._load_roles(session, user_id)
        departments = self._load_departments(session, user_id)
        scopes = _merge_scopes(roles)
        return AuthUser(
            id=user_data["user_id"],
            enterprise_id=user_data["enterprise_id"],
            username=user_data["username"],
            display_name=user_data["display_name"],
            email=user_data["email"],
            phone=user_data["phone"],
            status=user_data["status"],
            roles=roles,
            departments=departments,
            scopes=scopes,
        )

    def _load_roles(self, session: Session, user_id: str) -> tuple[AuthRole, ...]:
        rows = session.execute(
            text(
                """
                SELECT
                    r.id::text AS role_id,
                    r.code,
                    r.name,
                    r.scope_type,
                    rb.scope_id::text AS scope_id,
                    r.is_builtin,
                    r.status,
                    r.scopes
                FROM role_bindings rb
                JOIN roles r ON r.id = rb.role_id
                WHERE rb.user_id = :user_id
                  AND rb.status = 'active'
                  AND r.status = 'active'
                ORDER BY r.code
                """
            ),
            {"user_id": user_id},
        ).all()
        return tuple(
            AuthRole(
                id=row._mapping["role_id"],
                code=row._mapping["code"],
                name=row._mapping["name"],
                scope_type=row._mapping["scope_type"],
                scope_id=row._mapping["scope_id"],
                is_builtin=bool(row._mapping["is_builtin"]),
                status=row._mapping["status"],
                scopes=_normalize_scopes(row._mapping["scopes"]),
            )
            for row in rows
        )

    def _load_departments(self, session: Session, user_id: str) -> tuple[AuthDepartment, ...]:
        rows = session.execute(
            text(
                """
                SELECT
                    d.id::text AS department_id,
                    d.code,
                    d.name,
                    d.status,
                    udm.is_primary
                FROM user_department_memberships udm
                JOIN departments d ON d.id = udm.department_id
                WHERE udm.user_id = :user_id
                  AND udm.status = 'active'
                ORDER BY udm.is_primary DESC, d.code
                """
            ),
            {"user_id": user_id},
        ).all()
        return tuple(
            AuthDepartment(
                id=row._mapping["department_id"],
                code=row._mapping["code"],
                name=row._mapping["name"],
                status=row._mapping["status"],
                is_primary=bool(row._mapping["is_primary"]),
            )
            for row in rows
        )

    def _issue_token_pair(
        self,
        session: Session,
        *,
        user: AuthUser,
        auth_runtime: AuthRuntimeConfig,
        ip_address: str | None,
        user_agent: str | None,
    ) -> TokenPair:
        now = datetime.now(UTC)
        access_jti = f"access_{uuid.uuid4().hex}"
        refresh_jti = f"refresh_{uuid.uuid4().hex}"
        session_id = f"sess_{uuid.uuid4().hex}"
        auth_config = auth_runtime.auth_config
        access_ttl = int(auth_config.get("access_token_ttl_minutes", 30)) * 60
        refresh_ttl = int(auth_config.get("refresh_token_ttl_minutes", 10080)) * 60
        access_expires_at = now + timedelta(seconds=access_ttl)
        refresh_expires_at = now + timedelta(seconds=refresh_ttl)
        issuer = auth_runtime.jwt_issuer
        audience = auth_runtime.jwt_audience
        scopes = tuple(sorted(set(user.scopes)))
        role_codes = tuple(sorted(role.code for role in user.roles))

        common_claims = {
            "sub": user.id,
            "enterprise_id": user.enterprise_id,
            "auth_type": "local",
            "iss": issuer,
            "aud": audience,
            "iat": int(now.timestamp()),
            "sid": session_id,
            "scopes": list(scopes),
            "roles": list(role_codes),
        }
        access_claims = {
            **common_claims,
            "jti": access_jti,
            "token_type": "access",
            "exp": int(access_expires_at.timestamp()),
        }
        refresh_claims = {
            **common_claims,
            "jti": refresh_jti,
            "token_type": "refresh",
            "exp": int(refresh_expires_at.timestamp()),
        }
        access_token = encode_hs256(access_claims, auth_runtime.jwt_signing_secret)
        refresh_token = encode_hs256(refresh_claims, auth_runtime.jwt_signing_secret)

        metadata = {
            "issuer": issuer,
            "audience": audience,
            "auth_type": "local",
            "session_id": session_id,
            "ip_address": ip_address,
            "user_agent": _truncate_user_agent(user_agent),
        }
        self._insert_token_row(
            session,
            jti=access_jti,
            user=user,
            token_type="access",
            scopes=scopes,
            expires_at=access_expires_at,
            metadata=metadata,
        )
        self._insert_token_row(
            session,
            jti=refresh_jti,
            user=user,
            token_type="refresh",
            scopes=scopes,
            expires_at=refresh_expires_at,
            metadata=metadata,
        )
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="Bearer",
            expires_in=access_ttl,
            refresh_expires_in=refresh_ttl,
            access_jti=access_jti,
            refresh_jti=refresh_jti,
            access_expires_at=access_expires_at,
            refresh_expires_at=refresh_expires_at,
        )

    def _insert_token_row(
        self,
        session: Session,
        *,
        jti: str,
        user: AuthUser,
        token_type: str,
        scopes: tuple[str, ...],
        expires_at: datetime,
        metadata: dict[str, Any],
    ) -> None:
        session.execute(
            text(
                """
                INSERT INTO jwt_tokens(
                    jti, enterprise_id, subject_user_id, token_type,
                    status, scopes, expires_at, metadata_json
                )
                VALUES (
                    :jti, :enterprise_id, :subject_user_id, :token_type,
                    'active', :scopes, :expires_at, CAST(:metadata_json AS jsonb)
                )
                """
            ),
            {
                "jti": jti,
                "enterprise_id": user.enterprise_id,
                "subject_user_id": user.id,
                "token_type": token_type,
                "scopes": list(scopes),
                "expires_at": expires_at,
                "metadata_json": _json_metadata(metadata),
            },
        )

    def _decode_token(
        self,
        session: Session,
        token: str,
        auth_runtime: AuthRuntimeConfig,
        *,
        token_type: str,
    ) -> dict[str, Any]:
        if not token:
            raise AuthServiceError(
                "AUTH_TOKEN_INVALID",
                "bearer token is required",
                status_code=401,
            )
        try:
            return decode_hs256(
                token,
                auth_runtime.jwt_signing_secret,
                issuer=auth_runtime.jwt_issuer,
                audience=auth_runtime.jwt_audience,
                token_type=token_type,
            )
        except JwtError as exc:
            raise AuthServiceError(
                _auth_code_for_jwt_error(exc.error_code),
                exc.message,
                status_code=401,
            ) from exc

    def _load_token_row(
        self,
        session: Session,
        jti: str,
        *,
        for_update: bool,
    ) -> dict[str, Any]:
        query = """
            SELECT
                jti,
                enterprise_id::text AS enterprise_id,
                subject_user_id::text AS subject_user_id,
                token_type,
                status,
                scopes,
                expires_at,
                metadata_json
            FROM jwt_tokens
            WHERE jti = :jti
        """
        if for_update:
            query += " FOR UPDATE"
        row = session.execute(text(query), {"jti": jti}).one_or_none()
        if row is None:
            raise AuthServiceError("AUTH_TOKEN_INVALID", "token is not registered", status_code=401)
        return dict(row._mapping)

    def _assert_token_row_active(
        self,
        session: Session,
        row: dict[str, Any],
        *,
        token_type: str,
        subject_user_id: str | None = None,
        enterprise_id: str | None = None,
    ) -> None:
        if row["token_type"] != token_type:
            raise AuthServiceError("AUTH_TOKEN_INVALID", "token type is invalid", status_code=401)
        if subject_user_id is not None and row["subject_user_id"] != subject_user_id:
            raise AuthServiceError(
                "AUTH_TOKEN_INVALID",
                "token subject is invalid",
                status_code=401,
            )
        if enterprise_id is not None and row["enterprise_id"] != enterprise_id:
            raise AuthServiceError(
                "AUTH_TOKEN_INVALID",
                "token enterprise is invalid",
                status_code=401,
            )
        expires_at = _as_aware_utc(row["expires_at"])
        if expires_at <= datetime.now(UTC):
            self._mark_token_expired(session, row["jti"])
            raise AuthServiceError("AUTH_TOKEN_EXPIRED", "token has expired", status_code=401)
        if row["status"] == "expired":
            raise AuthServiceError("AUTH_TOKEN_EXPIRED", "token has expired", status_code=401)
        if row["status"] != "active":
            raise AuthServiceError("AUTH_TOKEN_INVALID", "token is not active", status_code=401)

    def _mark_token_expired(self, session: Session, jti: str) -> None:
        session.execute(
            text(
                """
                UPDATE jwt_tokens
                SET status = 'expired'
                WHERE jti = :jti AND status = 'active'
                """
            ),
            {"jti": jti},
        )


def _merge_scopes(roles: tuple[AuthRole, ...]) -> tuple[str, ...]:
    scopes: set[str] = set(BASE_USER_SCOPES)
    for role in roles:
        scopes.update(role.scopes)
    return tuple(sorted(scopes))


def _has_scope(scopes: tuple[str, ...], required_scope: str) -> bool:
    if "*" in scopes or required_scope in scopes:
        return True
    prefix = required_scope.split(":", maxsplit=1)[0]
    return f"{prefix}:*" in scopes


def _effective_scopes(
    token_scopes: tuple[str, ...],
    current_scopes: tuple[str, ...],
) -> tuple[str, ...]:
    if "*" in token_scopes and "*" in current_scopes:
        return ("*",)
    if "*" in token_scopes:
        return tuple(sorted(set(current_scopes)))
    if "*" in current_scopes:
        return tuple(sorted(set(token_scopes)))

    effective: set[str] = set()
    for scope in current_scopes:
        if _has_scope(token_scopes, scope):
            effective.add(scope)
    for scope in token_scopes:
        if _has_scope(current_scopes, scope):
            effective.add(scope)
    return tuple(sorted(effective))


def _normalize_scopes(value: object) -> tuple[str, ...]:
    if isinstance(value, list | tuple):
        return tuple(str(item) for item in value)
    return ()


def _required_str_claim(claims: dict[str, Any], name: str) -> str:
    value = claims.get(name)
    if not isinstance(value, str) or not value:
        raise AuthServiceError("AUTH_TOKEN_INVALID", f"token claim is missing: {name}")
    return value


def _status_error(status: str) -> AuthServiceError:
    if status == "locked":
        return AuthServiceError("AUTH_ACCOUNT_LOCKED", "account is locked", status_code=423)
    if status == "disabled":
        return AuthServiceError("AUTH_USER_DISABLED", "user is disabled", status_code=403)
    return AuthServiceError("AUTH_USER_DISABLED", "user is not active", status_code=403)


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _truncate_user_agent(value: str | None) -> str | None:
    if value is None:
        return None
    return value[:256]


def _json_metadata(value: dict[str, Any]) -> str:
    import json

    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _auth_code_for_jwt_error(error_code: str) -> str:
    if error_code == "JWT_EXPIRED":
        return "AUTH_TOKEN_EXPIRED"
    return "AUTH_TOKEN_INVALID"
