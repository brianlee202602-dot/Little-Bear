"""对象存储端口与测试实现。"""

from app.modules.storage.service import InMemoryObjectStorage, MinioObjectStorage, ObjectStorage

__all__ = ["InMemoryObjectStorage", "MinioObjectStorage", "ObjectStorage"]
