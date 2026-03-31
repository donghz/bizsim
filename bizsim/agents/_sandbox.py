import builtins
import sys
from typing import Any


class SandboxImportError(ImportError):
    pass


FORBIDDEN_MODULES = {
    "sqlite3",
    "sqlalchemy",
    "psycopg2",
    "mysql",
    "requests",
    "urllib",
    "http.client",
    "smtplib",
    "os",
    "subprocess",
    "socket",
}

_original_import = builtins.__import__
_sandbox_active = False


def _guarded_import(name: str, *args: Any, **kwargs: Any) -> Any:
    if _sandbox_active:
        root_module = name.split(".")[0]
        if root_module in FORBIDDEN_MODULES:
            raise SandboxImportError(
                f"Import of forbidden module '{name}' is blocked in agent sandbox"
            )
    return _original_import(name, *args, **kwargs)


class SandboxFinder:
    def find_spec(self, fullname: str, path: Any, target: Any = None) -> None:
        root_module = fullname.split(".")[0]
        if root_module in FORBIDDEN_MODULES:
            raise SandboxImportError(
                f"Import of forbidden module '{fullname}' is blocked in agent sandbox"
            )
        return None


def install_sandbox() -> None:
    global _sandbox_active
    if not any(isinstance(x, SandboxFinder) for x in sys.meta_path):
        sys.meta_path.insert(0, SandboxFinder())
    if not _sandbox_active:
        builtins.__import__ = _guarded_import
        _sandbox_active = True
