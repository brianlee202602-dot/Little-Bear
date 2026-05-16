"""对象存储端口定义。

P0 先定义最小读写删除接口，供导入链路保存原始对象、解析/清洗派生文本、
chunk 全量文本和后续预览/citation 回溯复用。
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


class ObjectStorage(Protocol):
    """对象存储最小端口。"""

    def put_object(
        self,
        *,
        object_key: str,
        content: bytes,
        content_type: str | None = None,
    ) -> None:
        ...

    def get_object(self, *, object_key: str) -> bytes:
        ...

    def delete_object(self, *, object_key: str) -> None:
        ...


@dataclass
class InMemoryObjectStorage:
    """测试/本地最小实现。"""

    objects: dict[str, bytes] = field(default_factory=dict)
    content_types: dict[str, str | None] = field(default_factory=dict)

    def put_object(
        self,
        *,
        object_key: str,
        content: bytes,
        content_type: str | None = None,
    ) -> None:
        self.objects[object_key] = content
        self.content_types[object_key] = content_type

    def get_object(self, *, object_key: str) -> bytes:
        return self.objects[object_key]

    def delete_object(self, *, object_key: str) -> None:
        self.objects.pop(object_key, None)
        self.content_types.pop(object_key, None)


@dataclass(frozen=True)
class MinioObjectStorage:
    """MinIO/S3 path-style 最小实现。

    这里使用 AWS Signature V4，避免为 P0 引入额外 SDK；生产部署如果需要 multipart、
    presigned URL 或复杂重试策略，再替换为正式 SDK adapter。
    """

    endpoint: str
    bucket: str
    access_key: str
    secret_key: str
    region: str = "us-east-1"
    object_key_prefix: str = ""
    timeout_seconds: float = 10.0

    def put_object(
        self,
        *,
        object_key: str,
        content: bytes,
        content_type: str | None = None,
    ) -> None:
        self._request(
            "PUT",
            object_key=object_key,
            content=content,
            content_type=content_type or "application/octet-stream",
        )

    def get_object(self, *, object_key: str) -> bytes:
        return self._request("GET", object_key=object_key)

    def delete_object(self, *, object_key: str) -> None:
        self._request("DELETE", object_key=object_key)

    def _request(
        self,
        method: str,
        *,
        object_key: str,
        content: bytes = b"",
        content_type: str | None = None,
    ) -> bytes:
        if not self.endpoint or not self.bucket:
            raise OSError("object storage endpoint and bucket are required")
        normalized_key = self._prefixed_key(object_key)
        canonical_uri = f"/{_uri_segment(self.bucket)}/{_uri_path(normalized_key)}"
        url = f"{self.endpoint.rstrip('/')}{canonical_uri}"
        parsed_url = urlparse(url)
        now = datetime.now(UTC)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        payload_hash = hashlib.sha256(content).hexdigest()
        headers = {
            "host": parsed_url.netloc,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
        }
        if content_type:
            headers["content-type"] = content_type
        signed_headers = ";".join(sorted(headers))
        canonical_headers = "".join(f"{key}:{headers[key]}\n" for key in sorted(headers))
        canonical_request = "\n".join(
            [
                method,
                canonical_uri,
                "",
                canonical_headers,
                signed_headers,
                payload_hash,
            ]
        )
        credential_scope = f"{date_stamp}/{self.region}/s3/aws4_request"
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                credential_scope,
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )
        signature = hmac.new(
            _signing_key(self.secret_key, date_stamp, self.region),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        request_headers = {
            key: value
            for key, value in {
                "Content-Type": content_type,
                "Host": headers["host"],
                "X-Amz-Content-Sha256": payload_hash,
                "X-Amz-Date": amz_date,
                "Authorization": (
                    "AWS4-HMAC-SHA256 "
                    f"Credential={self.access_key}/{credential_scope}, "
                    f"SignedHeaders={signed_headers}, Signature={signature}"
                ),
            }.items()
            if value is not None
        }
        request = Request(
            url,
            data=content if method == "PUT" else None,
            headers=request_headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                status = getattr(response, "status", 200)
                body = response.read()
        except HTTPError as exc:
            raise OSError(f"object storage returned HTTP {exc.code}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise OSError(f"object storage request failed: {exc.__class__.__name__}") from exc
        if status < 200 or status >= 300:
            raise OSError(f"object storage returned HTTP {status}")
        return body

    def _prefixed_key(self, object_key: str) -> str:
        key = object_key.strip().lstrip("/")
        prefix = self.object_key_prefix.strip().strip("/")
        return f"{prefix}/{key}" if prefix else key


def _signing_key(secret_key: str, date_stamp: str, region: str) -> bytes:
    date_key = hmac.new(f"AWS4{secret_key}".encode(), date_stamp.encode(), hashlib.sha256)
    date_region_key = hmac.new(date_key.digest(), region.encode("utf-8"), hashlib.sha256)
    date_region_service_key = hmac.new(date_region_key.digest(), b"s3", hashlib.sha256)
    return hmac.new(date_region_service_key.digest(), b"aws4_request", hashlib.sha256).digest()


def _uri_segment(value: str) -> str:
    return quote(value.strip("/"), safe="-_.~")


def _uri_path(value: str) -> str:
    return quote(value.strip("/"), safe="/-_.~")
