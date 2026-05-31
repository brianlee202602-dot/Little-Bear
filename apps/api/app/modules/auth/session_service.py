"""Auth session orchestration service."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.modules.auth.errors import AuthServiceError
from app.modules.auth.runtime import AuthRuntimeConfig
from app.modules.auth.schemas import AuthUser, LoginRecord, TokenPair
from app.modules.auth.utils import required_str_claim, status_error
from sqlalchemy import text
from sqlalchemy.orm import Session


class SessionService:
    """Coordinates login and refresh flows."""

    def __init__(
        self,
        *,
        password_verify: Callable[[str, str], bool],
        load_auth_runtime: Callable[[Session], AuthRuntimeConfig],
        load_login_record: Callable[..., LoginRecord],
        assert_user_can_login: Callable[[LoginRecord], None],
        record_failed_login: Callable[[Session, str, dict[str, Any]], None],
        load_user_context: Callable[[Session, str], AuthUser],
        record_successful_login: Callable[[Session, str], None],
        issue_token_pair: Callable[..., TokenPair],
        decode_token: Callable[..., dict[str, Any]],
        load_token_row: Callable[..., dict[str, Any]],
        assert_token_row_active: Callable[..., None],
    ) -> None:
        self._password_verify = password_verify
        self._load_auth_runtime = load_auth_runtime
        self._load_login_record = load_login_record
        self._assert_user_can_login = assert_user_can_login
        self._record_failed_login = record_failed_login
        self._load_user_context = load_user_context
        self._record_successful_login = record_successful_login
        self._issue_token_pair = issue_token_pair
        self._decode_token = decode_token
        self._load_token_row = load_token_row
        self._assert_token_row_active = assert_token_row_active

    def create_session(
        self,
        session: Session,
        *,
        username: str,
        password: str,
        enterprise_code: str | None,
        ip_address: str | None,
        user_agent: str | None,
    ) -> TokenPair:
        auth_runtime = self._load_auth_runtime(session)
        auth_config = auth_runtime.auth_config
        record = self._load_login_record(session, username, enterprise_code=enterprise_code)
        self._assert_user_can_login(record)

        if not self._password_verify(record.credential.password_hash, password):
            self._record_failed_login(session, record.user.id, auth_config)
            raise AuthServiceError(
                "AUTH_INVALID_CREDENTIALS",
                "username or password is invalid",
                status_code=401,
            )

        user = self._load_user_context(session, record.user.id)
        if user.status != "active":
            raise status_error(user.status)

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
        ip_address: str | None,
        user_agent: str | None,
    ) -> TokenPair:
        auth_runtime = self._load_auth_runtime(session)
        claims = self._decode_token(session, refresh_token, auth_runtime, token_type="refresh")
        refresh_jti = required_str_claim(claims, "jti")
        subject_user_id = required_str_claim(claims, "sub")
        enterprise_id = required_str_claim(claims, "enterprise_id")

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
            raise status_error(user.status)

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
