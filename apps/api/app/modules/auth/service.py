"""Auth Service facade.

The auth module keeps AuthService as the external entry point while splitting
session orchestration, token lifecycle, user context loading and credentials.
"""

from __future__ import annotations

from typing import Any

from app.modules.auth.credential_service import CredentialService
from app.modules.auth.errors import AuthServiceError
from app.modules.auth.password_service import PasswordService
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
from app.modules.auth.session_service import SessionService
from app.modules.auth.token_service import TokenService
from app.modules.auth.user_context_loader import UserContextLoader
from app.modules.auth.utils import BASE_USER_SCOPES
from app.modules.config.errors import ConfigServiceError
from app.modules.config.service import ConfigService
from app.modules.secrets.service import SecretStoreError, SecretStoreService
from sqlalchemy.orm import Session


class AuthService:
    """Facade for local auth, JWT lifecycle and current user context."""

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
        self.credential_service = CredentialService(password_service=self.password_service)
        self.user_context_loader = UserContextLoader()
        self.token_service = TokenService()
        self.session_service = SessionService(
            password_verify=self.password_service.verify,
            load_auth_runtime=lambda session: self._load_auth_runtime(session),
            load_login_record=(
                lambda session, username, **kwargs: self._load_login_record(
                    session,
                    username,
                    **kwargs,
                )
            ),
            assert_user_can_login=lambda record: self._assert_user_can_login(record),
            record_failed_login=(
                lambda session, user_id, auth_config: self._record_failed_login(
                    session,
                    user_id,
                    auth_config,
                )
            ),
            load_user_context=lambda session, user_id: self._load_user_context(session, user_id),
            record_successful_login=(
                lambda session, user_id: self._record_successful_login(session, user_id)
            ),
            issue_token_pair=lambda session, **kwargs: self._issue_token_pair(
                session,
                **kwargs,
            ),
            decode_token=lambda session, token, auth_runtime, **kwargs: self._decode_token(
                session,
                token,
                auth_runtime,
                **kwargs,
            ),
            load_token_row=lambda session, jti, **kwargs: self._load_token_row(
                session,
                jti,
                **kwargs,
            ),
            assert_token_row_active=(
                lambda session, row, **kwargs: self._assert_token_row_active(
                    session,
                    row,
                    **kwargs,
                )
            ),
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
        return self.session_service.create_session(
            session,
            username=username,
            password=password,
            enterprise_code=enterprise_code,
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
        return self.session_service.refresh_session(
            session,
            refresh_token=refresh_token,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def authenticate_access_token(
        self,
        session: Session,
        *,
        access_token: str,
        required_scope: str | None = None,
        auth_runtime: AuthRuntimeConfig | None = None,
    ) -> AuthContext:
        return self.token_service.authenticate_access_token(
            session,
            access_token=access_token,
            required_scope=required_scope,
            auth_runtime=auth_runtime,
            load_auth_runtime=lambda inner_session: self._load_auth_runtime(inner_session),
            decode_token=(
                lambda inner_session, token, runtime, **kwargs: self._decode_token(
                    inner_session,
                    token,
                    runtime,
                    **kwargs,
                )
            ),
            load_token_row=(
                lambda inner_session, jti, **kwargs: self._load_token_row(
                    inner_session,
                    jti,
                    **kwargs,
                )
            ),
            assert_token_row_active=(
                lambda inner_session, row, **kwargs: self._assert_token_row_active(
                    inner_session,
                    row,
                    **kwargs,
                )
            ),
            load_user_context=(
                lambda inner_session, user_id: self._load_user_context(
                    inner_session,
                    user_id,
                )
            ),
        )

    def revoke_current_session(self, session: Session, *, access_token: str) -> None:
        self.token_service.revoke_current_session(
            session,
            access_token=access_token,
            load_auth_runtime=lambda inner_session: self._load_auth_runtime(inner_session),
            decode_token=(
                lambda inner_session, token, runtime, **kwargs: self._decode_token(
                    inner_session,
                    token,
                    runtime,
                    **kwargs,
                )
            ),
            load_token_row=(
                lambda inner_session, jti, **kwargs: self._load_token_row(
                    inner_session,
                    jti,
                    **kwargs,
                )
            ),
            assert_token_row_active=(
                lambda inner_session, row, **kwargs: self._assert_token_row_active(
                    inner_session,
                    row,
                    **kwargs,
                )
            ),
        )

    def change_current_password(
        self,
        session: Session,
        *,
        access_token: str,
        old_password: str,
        new_password: str,
    ) -> None:
        self.credential_service.change_current_password(
            session,
            access_token=access_token,
            old_password=old_password,
            new_password=new_password,
            load_auth_runtime=lambda inner_session: self._load_auth_runtime(inner_session),
            authenticate_access_token=(
                lambda inner_session, **kwargs: self.authenticate_access_token(
                    inner_session,
                    **kwargs,
                )
            ),
            load_credential=(
                lambda inner_session, user_id, **kwargs: self._load_credential(
                    inner_session,
                    user_id,
                    **kwargs,
                )
            ),
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
        return self.credential_service.load_login_record(
            session,
            username,
            enterprise_code=enterprise_code,
        )

    def _load_credential(
        self,
        session: Session,
        user_id: str,
        *,
        for_update: bool,
    ) -> CredentialRecord:
        return self.credential_service.load_credential(session, user_id, for_update=for_update)

    def _assert_user_can_login(self, record: LoginRecord) -> None:
        self.credential_service.assert_user_can_login(record)

    def _record_failed_login(
        self,
        session: Session,
        user_id: str,
        auth_config: dict[str, Any],
    ) -> None:
        self.credential_service.record_failed_login(session, user_id, auth_config)

    def _record_successful_login(self, session: Session, user_id: str) -> None:
        self.credential_service.record_successful_login(session, user_id)

    def _load_user_context(self, session: Session, user_id: str) -> AuthUser:
        return self.user_context_loader.load_user_context(session, user_id)

    def _load_roles(self, session: Session, user_id: str) -> tuple[AuthRole, ...]:
        return self.user_context_loader.load_roles(session, user_id)

    def _load_departments(self, session: Session, user_id: str) -> tuple[AuthDepartment, ...]:
        return self.user_context_loader.load_departments(session, user_id)

    def _issue_token_pair(
        self,
        session: Session,
        *,
        user: AuthUser,
        auth_runtime: AuthRuntimeConfig,
        ip_address: str | None,
        user_agent: str | None,
    ) -> TokenPair:
        return self.token_service.issue_token_pair(
            session,
            user=user,
            auth_runtime=auth_runtime,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def _insert_token_row(
        self,
        session: Session,
        *,
        jti: str,
        user: AuthUser,
        token_type: str,
        scopes: tuple[str, ...],
        expires_at,
        metadata: dict[str, Any],
    ) -> None:
        self.token_service.insert_token_row(
            session,
            jti=jti,
            user=user,
            token_type=token_type,
            scopes=scopes,
            expires_at=expires_at,
            metadata=metadata,
        )

    def _decode_token(
        self,
        session: Session,
        token: str,
        auth_runtime: AuthRuntimeConfig,
        *,
        token_type: str,
    ) -> dict[str, Any]:
        return self.token_service.decode_token(
            session,
            token,
            auth_runtime,
            token_type=token_type,
        )

    def _load_token_row(
        self,
        session: Session,
        jti: str,
        *,
        for_update: bool,
    ) -> dict[str, Any]:
        return self.token_service.load_token_row(session, jti, for_update=for_update)

    def _assert_token_row_active(
        self,
        session: Session,
        row: dict[str, Any],
        *,
        token_type: str,
        subject_user_id: str | None = None,
        enterprise_id: str | None = None,
    ) -> None:
        self.token_service.assert_token_row_active(
            session,
            row,
            token_type=token_type,
            subject_user_id=subject_user_id,
            enterprise_id=enterprise_id,
        )

    def _mark_token_expired(self, session: Session, jti: str) -> None:
        self.token_service.mark_token_expired(session, jti)


__all__ = ["BASE_USER_SCOPES", "AuthService"]
