"""HS256 JWT 工具。

对外保留项目内的 JwtError 和 encode/decode API，内部使用 PyJWT 完成 JWT
结构解析、算法约束和签名校验，避免维护手写 JOSE 细节。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import jwt as pyjwt
from jwt import (
    DecodeError,
    ExpiredSignatureError,
    InvalidAlgorithmError,
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidSignatureError,
    InvalidTokenError,
    MissingRequiredClaimError,
    PyJWTError,
)


class JwtError(Exception):
    """JWT 解析或校验失败。"""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message


def encode_hs256(claims: dict[str, Any], secret: str) -> str:
    if not secret:
        raise JwtError("JWT_SIGNING_SECRET_MISSING", "jwt signing secret is missing")
    try:
        return pyjwt.encode(claims, secret, algorithm="HS256", headers={"typ": "JWT"})
    except PyJWTError as exc:
        raise JwtError("JWT_MALFORMED", "jwt claims cannot be encoded") from exc


def decode_hs256(
    token: str,
    secret: str,
    *,
    issuer: str | None = None,
    audience: str | None = None,
    token_type: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    if token.count(".") != 2:
        raise JwtError("JWT_MALFORMED", "jwt must contain header, payload and signature")
    if not secret:
        raise JwtError("JWT_SIGNING_SECRET_MISSING", "jwt signing secret is missing")

    try:
        claims = pyjwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={
                "require": ["exp"],
                "verify_exp": False,
                "verify_iat": False,
                "verify_nbf": False,
                "verify_aud": False,
                "verify_iss": False,
            },
        )
    except MissingRequiredClaimError as exc:
        raise JwtError("JWT_EXP_MISSING", "jwt exp claim is missing") from exc
    except ExpiredSignatureError as exc:
        raise JwtError("JWT_EXPIRED", "jwt has expired") from exc
    except InvalidSignatureError as exc:
        raise JwtError("JWT_SIGNATURE_INVALID", "jwt signature is invalid") from exc
    except InvalidAlgorithmError as exc:
        raise JwtError("JWT_ALGORITHM_UNSUPPORTED", "jwt algorithm is not supported") from exc
    except InvalidIssuerError as exc:
        raise JwtError("JWT_ISSUER_INVALID", "jwt issuer is invalid") from exc
    except InvalidAudienceError as exc:
        raise JwtError("JWT_AUDIENCE_INVALID", "jwt audience is invalid") from exc
    except DecodeError as exc:
        raise JwtError("JWT_MALFORMED", "jwt payload is malformed") from exc
    except InvalidTokenError as exc:
        raise JwtError("JWT_MALFORMED", "jwt token is invalid") from exc

    if not isinstance(claims, dict):
        raise JwtError("JWT_MALFORMED", "jwt claims must be an object")

    _validate_registered_claims(
        claims,
        issuer=issuer,
        audience=audience,
        token_type=token_type,
        now=now or datetime.now(UTC),
    )
    return claims


def _validate_registered_claims(
    claims: dict[str, Any],
    *,
    issuer: str | None,
    audience: str | None,
    token_type: str | None,
    now: datetime,
) -> None:
    exp = claims.get("exp")
    if not isinstance(exp, int | float):
        raise JwtError("JWT_EXP_MISSING", "jwt exp claim is missing")
    if int(exp) <= int(now.timestamp()):
        raise JwtError("JWT_EXPIRED", "jwt has expired")

    if issuer is not None and claims.get("iss") != issuer:
        raise JwtError("JWT_ISSUER_INVALID", "jwt issuer is invalid")

    if audience is not None:
        claim_aud = claims.get("aud")
        valid_audience = claim_aud == audience or (
            isinstance(claim_aud, list) and audience in claim_aud
        )
        if not valid_audience:
            raise JwtError("JWT_AUDIENCE_INVALID", "jwt audience is invalid")

    if token_type is not None and claims.get("token_type") != token_type:
        raise JwtError("JWT_TOKEN_TYPE_INVALID", "jwt token_type is invalid")
