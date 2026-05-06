"""Setup JWT 的签发、校验和一次性消费。

setup JWT 只在系统未初始化或恢复初始化时使用。它不能访问普通业务 API，且新的
setup token 会吊销旧 token，初始化成功后会被标记为 used。
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.shared.jwt import JwtError, decode_hs256, encode_hs256
from app.shared.settings import get_settings
from sqlalchemy import text
from sqlalchemy.orm import Session

DEFAULT_SETUP_TOKEN_TTL_SECONDS = 30 * 60
SETUP_TOKEN_SCOPES = ("setup:validate", "setup:initialize")
_EPHEMERAL_SETUP_TOKEN_SIGNING_SECRET = secrets.token_urlsafe(32)


class SetupTokenError(Exception):
    """Setup bearer token 校验失败，带结构化错误码。"""

    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        status_code: int = 401,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


@dataclass(frozen=True)
class SetupTokenContext:
    setup_token_id: str
    jwt_jti: str
    token_hash: str
    scopes: tuple[str, ...]


@dataclass(frozen=True)
class IssuedSetupToken:
    token: str
    setup_token_id: str
    jwt_jti: str
    expires_at: datetime
    scopes: tuple[str, ...]


class SetupTokenService:
    """管理 setup token 的签发、校验、过期和一次性消费状态。"""

    def issue(
        self,
        session: Session,
        *,
        ttl_seconds: int = DEFAULT_SETUP_TOKEN_TTL_SECONDS,
        scopes: tuple[str, ...] = SETUP_TOKEN_SCOPES,
    ) -> IssuedSetupToken:
        if not set(SETUP_TOKEN_SCOPES).issubset(scopes):
            raise SetupTokenError(
                "SETUP_TOKEN_SCOPE_INVALID",
                "setup token must include setup validation and initialization scopes",
                status_code=400,
            )

        jwt_jti = f"setup_{uuid.uuid4().hex}"
        setup_token_id = str(uuid.uuid4())
        expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
        token = _build_setup_jwt(
            jwt_jti=jwt_jti,
            setup_token_id=setup_token_id,
            scopes=scopes,
            expires_at=expires_at,
        )
        token_hash = self.hash_token(token)

        # 始终先失效旧 token，保证同一时间只有一个 active setup token。
        self.revoke_active(session, reason="replaced_by_new_setup_token")
        session.execute(
            text(
                """
                INSERT INTO jwt_tokens(jti, token_type, status, scopes, expires_at, metadata_json)
                VALUES (
                    :jti, 'setup', 'active', :scopes, :expires_at,
                    '{"issuer":"setup_token_service"}'::jsonb
                )
                """
            ),
            {"jti": jwt_jti, "scopes": list(scopes), "expires_at": expires_at},
        )
        session.execute(
            text(
                """
                INSERT INTO setup_tokens(id, jwt_jti, token_hash, status, scopes, expires_at)
                VALUES (:id, :jwt_jti, :token_hash, 'active', :scopes, :expires_at)
                """
            ),
            {
                "id": setup_token_id,
                "jwt_jti": jwt_jti,
                "token_hash": token_hash,
                "scopes": list(scopes),
                "expires_at": expires_at,
            },
        )
        return IssuedSetupToken(
            token=token,
            setup_token_id=setup_token_id,
            jwt_jti=jwt_jti,
            expires_at=expires_at,
            scopes=scopes,
        )

    def validate(
        self,
        session: Session,
        token: str | None,
        *,
        required_scope: str,
    ) -> SetupTokenContext:
        if not token:
            raise SetupTokenError("SETUP_TOKEN_INVALID", "setup bearer token is required")
        if _looks_like_jwt(token) and not _verify_setup_jwt(token):
            raise SetupTokenError("SETUP_TOKEN_INVALID", "setup bearer token signature is invalid")

        # 数据库只保存 token_hash；明文 JWT 只在签发时返回或打印一次。
        token_hash = self.hash_token(token)
        row = session.execute(
            text(
                """
                SELECT
                    st.id::text AS setup_token_id,
                    st.jwt_jti,
                    st.status AS setup_status,
                    st.scopes AS setup_scopes,
                    jt.status AS jwt_status,
                    jt.token_type,
                    jt.scopes AS jwt_scopes,
                    (st.expires_at <= now() OR jt.expires_at <= now()) AS is_expired
                FROM setup_tokens st
                JOIN jwt_tokens jt ON jt.jti = st.jwt_jti
                WHERE st.token_hash = :token_hash
                FOR UPDATE OF st, jt
                """
            ),
            {"token_hash": token_hash},
        ).one_or_none()
        if row is None:
            raise SetupTokenError("SETUP_TOKEN_INVALID", "setup bearer token is invalid")

        data = row._mapping
        setup_status = data["setup_status"]
        jwt_status = data["jwt_status"]
        if setup_status == "used" or jwt_status == "used":
            raise SetupTokenError("SETUP_TOKEN_USED", "setup bearer token has already been used")
        if setup_status == "expired" or jwt_status == "expired" or data["is_expired"]:
            self._mark_expired(session, data["setup_token_id"], data["jwt_jti"])
            raise SetupTokenError("SETUP_TOKEN_EXPIRED", "setup bearer token has expired")
        if (
            data["token_type"] != "setup"
            or setup_status != "active"
            or jwt_status != "active"
        ):
            raise SetupTokenError("SETUP_TOKEN_INVALID", "setup bearer token is not active")

        setup_scopes = _normalize_scopes(data["setup_scopes"])
        jwt_scopes = _normalize_scopes(data["jwt_scopes"])
        if required_scope not in setup_scopes or required_scope not in jwt_scopes:
            raise SetupTokenError(
                "SETUP_TOKEN_INVALID",
                "setup bearer token does not include required scope",
            )

        return SetupTokenContext(
            setup_token_id=data["setup_token_id"],
            jwt_jti=data["jwt_jti"],
            token_hash=token_hash,
            scopes=tuple(sorted(set(setup_scopes))),
        )

    def consume(self, session: Session, token_context: SetupTokenContext) -> None:
        session.execute(
            text(
                """
                UPDATE setup_tokens
                SET status = 'used', used_at = now()
                WHERE id = :setup_token_id AND status = 'active'
                """
            ),
            {"setup_token_id": token_context.setup_token_id},
        )
        session.execute(
            text(
                """
                UPDATE jwt_tokens
                SET status = 'used', used_at = now()
                WHERE jti = :jwt_jti AND status = 'active'
                """
            ),
            {"jwt_jti": token_context.jwt_jti},
        )

    def revoke_active(self, session: Session, *, reason: str) -> None:
        session.execute(
            text(
                """
                UPDATE setup_tokens
                SET status = 'revoked', revoked_at = now(), revoked_reason = :reason
                WHERE status = 'active'
                """
            ),
            {"reason": reason},
        )
        session.execute(
            text(
                """
                UPDATE jwt_tokens
                SET status = 'revoked', revoked_at = now()
                WHERE token_type = 'setup' AND status = 'active'
                """
            )
        )

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _mark_expired(self, session: Session, setup_token_id: str, jwt_jti: str) -> None:
        session.execute(
            text(
                """
                UPDATE setup_tokens
                SET status = 'expired'
                WHERE id = :setup_token_id AND status = 'active'
                """
            ),
            {"setup_token_id": setup_token_id},
        )
        session.execute(
            text(
                """
                UPDATE jwt_tokens
                SET status = 'expired'
                WHERE jti = :jwt_jti AND status = 'active'
                """
            ),
            {"jwt_jti": jwt_jti},
        )


def _normalize_scopes(value: object) -> tuple[str, ...]:
    if isinstance(value, list | tuple):
        return tuple(str(item) for item in value)
    return ()


def _build_setup_jwt(
    *,
    jwt_jti: str,
    setup_token_id: str,
    scopes: tuple[str, ...],
    expires_at: datetime,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "jti": jwt_jti,
        "sid": setup_token_id,
        "typ": "setup",
        "token_type": "setup",
        "scope": " ".join(scopes),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return encode_hs256(payload, _setup_signing_secret())


def _verify_setup_jwt(token: str) -> bool:
    try:
        payload = decode_hs256(token, _setup_signing_secret())
    except JwtError:
        return False
    return payload.get("typ") == "setup" and payload.get("token_type", "setup") == "setup"


def _looks_like_jwt(token: str) -> bool:
    return token.count(".") == 2


def _setup_signing_secret() -> str:
    # 生产环境必须显式配置 SETUP_TOKEN_SIGNING_SECRET；本地未配置时才使用进程临时密钥。
    return get_settings().setup_token_signing_secret or _EPHEMERAL_SETUP_TOKEN_SIGNING_SECRET
