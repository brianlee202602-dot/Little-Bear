from __future__ import annotations

import pytest
from app.modules.auth.errors import AuthServiceError
from app.modules.auth.password_service import PasswordPolicy, PasswordService


def test_password_policy_accepts_strong_password() -> None:
    PasswordService().validate_policy(
        "StrongPass_123",
        PasswordPolicy(
            min_length=12,
            require_uppercase=True,
            require_lowercase=True,
            require_digit=True,
            require_symbol=True,
        ),
    )


def test_password_policy_rejects_missing_digit() -> None:
    with pytest.raises(AuthServiceError) as exc_info:
        PasswordService().validate_policy(
            "StrongPassword_",
            PasswordPolicy(
                min_length=12,
                require_uppercase=True,
                require_lowercase=True,
                require_digit=True,
                require_symbol=True,
            ),
        )

    assert exc_info.value.error_code == "AUTH_PASSWORD_WEAK"
