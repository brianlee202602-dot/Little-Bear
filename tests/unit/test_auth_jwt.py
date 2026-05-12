from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt as pyjwt
import pytest
from app.shared.jwt import JwtError, decode_hs256, encode_hs256

SECRET = "s" * 32
OTHER_SECRET = "o" * 32
HS384_SECRET = "h" * 48


def test_hs256_jwt_round_trips_with_issuer_audience_and_type() -> None:
    token = encode_hs256(
        {
            "sub": "user_1",
            "jti": "access_1",
            "token_type": "access",
            "iss": "little-bear-rag",
            "aud": "little-bear-internal",
            "exp": int((datetime.now(UTC) + timedelta(minutes=5)).timestamp()),
        },
        SECRET,
    )

    claims = decode_hs256(
        token,
        SECRET,
        issuer="little-bear-rag",
        audience="little-bear-internal",
        token_type="access",
    )

    assert claims["sub"] == "user_1"
    assert claims["jti"] == "access_1"


def test_hs256_jwt_rejects_invalid_signature() -> None:
    token = encode_hs256(
        {
            "sub": "user_1",
            "jti": "access_1",
            "token_type": "access",
            "exp": int((datetime.now(UTC) + timedelta(minutes=5)).timestamp()),
        },
        SECRET,
    )

    with pytest.raises(JwtError) as exc_info:
        decode_hs256(token, OTHER_SECRET)

    assert exc_info.value.error_code == "JWT_SIGNATURE_INVALID"


def test_hs256_jwt_rejects_missing_exp() -> None:
    token = encode_hs256({"sub": "user_1", "jti": "access_1"}, SECRET)

    with pytest.raises(JwtError) as exc_info:
        decode_hs256(token, SECRET)

    assert exc_info.value.error_code == "JWT_EXP_MISSING"


def test_hs256_jwt_rejects_unsupported_algorithm() -> None:
    token = pyjwt.encode(
        {
            "sub": "user_1",
            "jti": "access_1",
            "exp": int((datetime.now(UTC) + timedelta(minutes=5)).timestamp()),
        },
        HS384_SECRET,
        algorithm="HS384",
    )

    with pytest.raises(JwtError) as exc_info:
        decode_hs256(token, HS384_SECRET)

    assert exc_info.value.error_code == "JWT_ALGORITHM_UNSUPPORTED"


def test_hs256_jwt_rejects_expired_token() -> None:
    token = encode_hs256(
        {
            "sub": "user_1",
            "jti": "access_1",
            "token_type": "access",
            "exp": int((datetime.now(UTC) - timedelta(minutes=1)).timestamp()),
        },
        SECRET,
    )

    with pytest.raises(JwtError) as exc_info:
        decode_hs256(token, SECRET)

    assert exc_info.value.error_code == "JWT_EXPIRED"
