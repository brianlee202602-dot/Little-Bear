"""Auth JWT token lifecycle service."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from app.modules.auth.errors import AuthServiceError
from app.modules.auth.runtime import AuthRuntimeConfig
from app.modules.auth.schemas import AuthContext, AuthUser, TokenPair
from app.modules.auth.utils import (
    as_aware_utc,
    auth_code_for_jwt_error,
    effective_scopes,
    has_scope,
    json_metadata,
    normalize_scopes,
    required_str_claim,
    status_error,
    truncate_user_agent,
)
from app.shared.jwt import JwtError, decode_hs256, encode_hs256
from sqlalchemy import text
from sqlalchemy.orm import Session


class TokenService:
    """Issues, validates and revokes JWT-backed sessions."""

    def issue_token_pair(
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
            "user_agent": truncate_user_agent(user_agent),
        }
        self.insert_token_row(
            session,
            jti=access_jti,
            user=user,
            token_type="access",
            scopes=scopes,
            expires_at=access_expires_at,
            metadata=metadata,
        )
        self.insert_token_row(
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

    def insert_token_row(
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
                "metadata_json": json_metadata(metadata),
            },
        )

    def decode_token(
        self,
        session: Session,
        token: str,
        auth_runtime: AuthRuntimeConfig,
        *,
        token_type: str,
    ) -> dict[str, Any]:
        del session
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
                auth_code_for_jwt_error(exc.error_code),
                exc.message,
                status_code=401,
            ) from exc

    def load_token_row(
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

    def assert_token_row_active(
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
        expires_at = as_aware_utc(row["expires_at"])
        if expires_at <= datetime.now(UTC):
            self.mark_token_expired(session, row["jti"])
            raise AuthServiceError("AUTH_TOKEN_EXPIRED", "token has expired", status_code=401)
        if row["status"] == "expired":
            raise AuthServiceError("AUTH_TOKEN_EXPIRED", "token has expired", status_code=401)
        if row["status"] != "active":
            raise AuthServiceError("AUTH_TOKEN_INVALID", "token is not active", status_code=401)

    def mark_token_expired(self, session: Session, jti: str) -> None:
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

    def authenticate_access_token(
        self,
        session: Session,
        *,
        access_token: str,
        required_scope: str | None,
        auth_runtime: AuthRuntimeConfig | None,
        load_auth_runtime: Callable[[Session], AuthRuntimeConfig],
        decode_token: Callable[..., dict[str, Any]],
        load_token_row: Callable[..., dict[str, Any]],
        assert_token_row_active: Callable[..., None],
        load_user_context: Callable[..., AuthUser],
    ) -> AuthContext:
        auth_runtime = auth_runtime or load_auth_runtime(session)
        claims = decode_token(session, access_token, auth_runtime, token_type="access")
        access_jti = required_str_claim(claims, "jti")
        subject_user_id = required_str_claim(claims, "sub")
        enterprise_id = required_str_claim(claims, "enterprise_id")

        row = load_token_row(session, access_jti, for_update=False)
        assert_token_row_active(
            session,
            row,
            token_type="access",
            subject_user_id=subject_user_id,
            enterprise_id=enterprise_id,
        )

        token_scopes = normalize_scopes(claims.get("scopes"))
        user = load_user_context(session, subject_user_id)
        if user.status != "active":
            raise status_error(user.status)

        current_scopes = user.scopes
        if required_scope and (
            not has_scope(token_scopes, required_scope)
            or not has_scope(current_scopes, required_scope)
        ):
            raise AuthServiceError(
                "AUTH_SCOPE_FORBIDDEN",
                "current user does not include required scope",
                status_code=403,
                details={
                    "required_scope": required_scope,
                    "token_scope_allowed": has_scope(token_scopes, required_scope),
                    "current_scope_allowed": has_scope(current_scopes, required_scope),
                },
            )

        return AuthContext(
            user=user,
            token_jti=access_jti,
            token_type="access",
            scopes=effective_scopes(token_scopes, current_scopes),
            claims=claims,
        )

    def revoke_current_session(
        self,
        session: Session,
        *,
        access_token: str,
        load_auth_runtime: Callable[[Session], AuthRuntimeConfig],
        decode_token: Callable[..., dict[str, Any]],
        load_token_row: Callable[..., dict[str, Any]],
        assert_token_row_active: Callable[..., None],
    ) -> None:
        auth_runtime = load_auth_runtime(session)
        claims = decode_token(session, access_token, auth_runtime, token_type="access")
        access_jti = required_str_claim(claims, "jti")
        subject_user_id = required_str_claim(claims, "sub")
        enterprise_id = required_str_claim(claims, "enterprise_id")
        session_id = claims.get("sid")

        row = load_token_row(session, access_jti, for_update=True)
        assert_token_row_active(
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
