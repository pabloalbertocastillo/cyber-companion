"""Versioned user configuration and private XDG paths."""
from __future__ import annotations
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from .core.validation import decode


def private_directory(path: Path) -> Path:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise ValueError("private directory must be owned by current user")
    path.chmod(0o700)
    return path


def runtime_dir() -> Path:
    value = os.environ.get("XDG_RUNTIME_DIR")
    if not value:
        raise ValueError("XDG_RUNTIME_DIR no está disponible; inicia dentro de tu sesión gráfica.")
    root = Path(value)
    if not root.is_dir() or root.stat().st_uid != os.getuid():
        raise ValueError("XDG_RUNTIME_DIR no pertenece al usuario actual")
    return private_directory(root / "cyber-companion")


def state_dir() -> Path:
    return private_directory(Path(os.environ.get("XDG_STATE_HOME", str(Path.home()/".local/state"))) / "cyber-companion")


def config_path() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home()/".config"))) / "cyber-companion/desktop.json"


@dataclass
class Settings:
    version: int = 1
    storage_paths: list[str] = field(default_factory=lambda: ["/"])
    sensors: list[str] = field(default_factory=lambda: ["system", "storage", "network", "media", "desktop", "session"])
    notifications: bool = True
    ollama_model: str = ""
    ollama_local_only_confirmed: bool = False

    @classmethod
    def load(cls, path: Path | None = None):
        path = path or config_path()
        if not path.exists():
            return cls()
        raw = decode(path.read_bytes())
        if type(raw) is not dict or set(raw) - set(cls.__dataclass_fields__):
            raise ValueError("unknown configuration fields")
        obj = cls(**raw)
        if type(obj.version) is not int or obj.version != 1:
            raise ValueError("unsupported configuration version")
        if type(obj.storage_paths) is not list or not 1 <= len(obj.storage_paths) <= 16 or any(type(p) is not str or not Path(p).is_absolute() for p in obj.storage_paths):
            raise ValueError("storage_paths must contain 1–16 absolute local mount paths")
        allowed = {"system", "storage", "network", "media", "desktop", "session", "virtualization"}
        if type(obj.sensors) is not list or any(type(x) is not str or x not in allowed for x in obj.sensors) or len(set(obj.sensors)) != len(obj.sensors):
            raise ValueError("invalid sensor list")
        if any(type(v) is not bool for v in (obj.notifications, obj.ollama_local_only_confirmed)):
            raise ValueError("invalid configuration boolean")
        if type(obj.ollama_model) is not str or len(obj.ollama_model) > 128:
            raise ValueError("invalid local model name")
        return obj
