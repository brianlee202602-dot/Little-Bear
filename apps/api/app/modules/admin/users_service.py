"""User administration service facade."""

from __future__ import annotations

from typing import Any

from app.modules.admin.user_department_service import AdminUserDepartmentService
from app.modules.admin.user_security_service import AdminUserSecurityService
from app.modules.admin.user_writer import AdminUserWriter
from app.modules.admin.users_reader import AdminUsersReader


class AdminUsersService:
    def __init__(self, core_service: Any) -> None:
        self._core_service = core_service

    def list_users(self, *args: Any, **kwargs: Any) -> Any:
        return self._reader().list_users(*args, **kwargs)

    def get_user(self, *args: Any, **kwargs: Any) -> Any:
        return self._reader().get_user(*args, **kwargs)

    def list_user_departments(self, *args: Any, **kwargs: Any) -> Any:
        return self._departments().list_user_departments(*args, **kwargs)

    def replace_user_departments(self, *args: Any, **kwargs: Any) -> Any:
        return self._departments().replace_user_departments(*args, **kwargs)

    def create_user(self, *args: Any, **kwargs: Any) -> Any:
        return self._writer().create_user(*args, **kwargs)

    def patch_user(self, *args: Any, **kwargs: Any) -> Any:
        return self._writer().patch_user(*args, **kwargs)

    def delete_user(self, *args: Any, **kwargs: Any) -> Any:
        return self._writer().delete_user(*args, **kwargs)

    def reset_user_password(self, *args: Any, **kwargs: Any) -> Any:
        return self._security().reset_user_password(*args, **kwargs)

    def unlock_user(self, *args: Any, **kwargs: Any) -> Any:
        return self._security().unlock_user(*args, **kwargs)

    def _reader(self) -> AdminUsersReader:
        return AdminUsersReader(self._core_service)

    def _departments(self) -> AdminUserDepartmentService:
        return AdminUserDepartmentService(self._core_service)

    def _writer(self) -> AdminUserWriter:
        return AdminUserWriter(self._core_service)

    def _security(self) -> AdminUserSecurityService:
        return AdminUserSecurityService(self._core_service)
