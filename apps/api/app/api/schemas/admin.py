"""管理后台 API 请求和响应模型聚合入口。"""

# ruff: noqa: F401,F403

from __future__ import annotations

from pydantic import BaseModel as _BaseModel

from app.api.schemas.admin_common import *
from app.api.schemas.admin_departments import *
from app.api.schemas.admin_documents import *
from app.api.schemas.admin_index_ops import *
from app.api.schemas.admin_knowledge import *
from app.api.schemas.admin_roles import *
from app.api.schemas.admin_users import *

for _schema in tuple(globals().values()):
    if (
        isinstance(_schema, type)
        and issubclass(_schema, _BaseModel)
        and _schema.__module__.startswith("app.api.schemas.admin_")
    ):
        _schema.__module__ = __name__
        _schema.model_rebuild(force=True)

del _schema
