"""API/worker use Storage; a remote adapter can stage objects into a local cache."""

from abc import ABC, abstractmethod
from pathlib import Path
import shutil
from backend.config import STORAGE_PATH


class Storage(ABC):
    @abstractmethod
    def path(self, project_id: str, key: str = "") -> Path: ...
    @abstractmethod
    def delete_project(self, project_id: str): ...


class LocalStorage(Storage):
    def __init__(self, root=STORAGE_PATH):
        self.root = Path(root).resolve()

    def path(self, project_id, key=""):
        p = (self.root / project_id / key).resolve()
        if not p.is_relative_to(self.root) or p == self.root:
            raise ValueError("Недопустимый путь")
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def delete_project(self, project_id):
        p = self.path(project_id)
        if p.exists():
            shutil.rmtree(p)


storage: Storage = LocalStorage()
