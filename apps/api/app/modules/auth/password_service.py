"""密码哈希和密码策略校验。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.modules.auth.errors import AuthServiceError

try:  # pragma: no cover - 依赖缺失路径由运行环境触发
    from argon2 import PasswordHasher
    from argon2.exceptions import VerificationError, VerifyMismatchError
except ImportError:  # pragma: no cover
    PasswordHasher = None  # type: ignore[assignment]
    VerifyMismatchError = VerificationError = Exception  # type: ignore[assignment,misc]


@dataclass(frozen=True)
class PasswordPolicy:
    min_length: int
    require_uppercase: bool
    require_lowercase: bool
    require_digit: bool
    require_symbol: bool

    @classmethod
    def from_auth_config(cls, auth_config: dict[str, Any]) -> PasswordPolicy:
        return cls(
            min_length=int(auth_config.get("password_min_length", 12)),
            require_uppercase=bool(auth_config.get("password_require_uppercase", True)),
            require_lowercase=bool(auth_config.get("password_require_lowercase", True)),
            require_digit=bool(auth_config.get("password_require_digit", True)),
            require_symbol=bool(auth_config.get("password_require_symbol", False)),
        )


class PasswordService:
    """封装密码 hash 校验，避免业务流程直接接触 argon2 细节。"""

    def verify(self, password_hash: str, password: str) -> bool:
        if PasswordHasher is None:
            raise AuthServiceError(
                "AUTH_PASSWORD_HASHER_UNAVAILABLE",
                "argon2-cffi is required to verify password",
                status_code=503,
                retryable=True,
            )
        try:
            return bool(PasswordHasher().verify(password_hash, password))  # type: ignore[operator]
        except VerifyMismatchError:
            return False
        except VerificationError as exc:
            raise AuthServiceError(
                "AUTH_PASSWORD_HASH_INVALID",
                "stored password hash cannot be verified",
                status_code=500,
                details={"error_type": exc.__class__.__name__},
            ) from exc

    def hash(self, password: str) -> str:
        if PasswordHasher is None:
            raise AuthServiceError(
                "AUTH_PASSWORD_HASHER_UNAVAILABLE",
                "argon2-cffi is required to hash password",
                status_code=503,
                retryable=True,
            )
        return str(PasswordHasher().hash(password))  # type: ignore[operator]

    def validate_policy(self, password: str, policy: PasswordPolicy) -> None:
        if len(password) < policy.min_length:
            raise AuthServiceError(
                "AUTH_PASSWORD_WEAK",
                "password does not meet length policy",
                status_code=400,
                details={"min_length": policy.min_length},
            )
        if policy.require_uppercase and not any(char.isupper() for char in password):
            raise AuthServiceError(
                "AUTH_PASSWORD_WEAK",
                "password requires uppercase letter",
                status_code=400,
            )
        if policy.require_lowercase and not any(char.islower() for char in password):
            raise AuthServiceError(
                "AUTH_PASSWORD_WEAK",
                "password requires lowercase letter",
                status_code=400,
            )
        if policy.require_digit and not any(char.isdigit() for char in password):
            raise AuthServiceError("AUTH_PASSWORD_WEAK", "password requires digit", status_code=400)
        if policy.require_symbol and not any(not char.isalnum() for char in password):
            raise AuthServiceError(
                "AUTH_PASSWORD_WEAK",
                "password requires symbol",
                status_code=400,
            )
