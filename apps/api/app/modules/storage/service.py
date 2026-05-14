"""对象存储端口定义。

P0 先定义最小读写删除接口，供导入链路保存原始对象、后续预览/citation 回溯复用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


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
