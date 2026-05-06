"""轻量 HS256 JWT 工具。

项目当前不额外引入 PyJWT，P0 只需要 HMAC-SHA256 签发和校验 access/refresh/setup
形态的 JWT。这里集中处理 base64url、签名、exp/iat/aud/iss 校验，避免各模块各自拼接
JWT 字符串。
"""

from __future__ import annotations

import hashlib
import hmac
import json
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import UTC, datetime
from typing import Any


class JwtError(Exception):
    """JWT 解析或校验失败。"""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message


def encode_hs256(claims: dict[str, Any], secret: str) -> str:
    if not secret:
        raise JwtError("JWT_SIGNING_SECRET_MISSING", "jwt signing secret is missing")
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = ".".join((_b64_json(header), _b64_json(claims)))
    return f"{signing_input}.{_sign(signing_input, secret)}"


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

    signing_input, _, signature = token.rpartition(".")
    if not hmac.compare_digest(signature, _sign(signing_input, secret)):
        raise JwtError("JWT_SIGNATURE_INVALID", "jwt signature is invalid")

    try:
        header_segment, payload_segment = signing_input.split(".", maxsplit=1)
        header = json.loads(_b64_decode(header_segment))
        claims = json.loads(_b64_decode(payload_segment))
    except (ValueError, json.JSONDecodeError) as exc:
        raise JwtError("JWT_MALFORMED", "jwt payload is malformed") from exc

    if header.get("alg") != "HS256":
        raise JwtError("JWT_ALGORITHM_UNSUPPORTED", "jwt algorithm is not supported")
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


def _b64_json(value: dict[str, Any]) -> str:
    return _b64_encode(json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def _sign(signing_input: str, secret: str) -> str:
    digest = hmac.new(
        secret.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return _b64_encode(digest)


def _b64_encode(value: bytes) -> str:
    return urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64_decode(value: str) -> str:
    padding = "=" * (-len(value) % 4)
    return urlsafe_b64decode(f"{value}{padding}").decode("utf-8")
