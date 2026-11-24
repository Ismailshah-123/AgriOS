"""Local filesystem storage. The root comes from settings (STORAGE_PATH); every resolved
path is checked to stay inside it, and writes are atomic (temp file + rename)."""

import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from app.storage.base import StorageError, StoredObject, check_key


class LocalFileStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / check_key(key)).resolve()
        if not path.is_relative_to(self.root):  # defence in depth on top of the pattern
            raise StorageError("path escapes storage root")
        return path

    def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            os.replace(tmp, path)
        except OSError as exc:
            raise StorageError(f"write failed: {exc.__class__.__name__}") from exc

    def get(self, key: str) -> bytes:
        try:
            return self._path(key).read_bytes()
        except FileNotFoundError:
            raise
        except OSError as exc:
            raise StorageError(f"read failed: {exc.__class__.__name__}") from exc

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink(missing_ok=True)
        except OSError as exc:
            raise StorageError(f"delete failed: {exc.__class__.__name__}") from exc

    def list(self, prefix: str) -> list[StoredObject]:
        base = (self.root / prefix).resolve()
        if not base.is_relative_to(self.root) or not base.exists():
            return []
        out = []
        for p in base.rglob("*"):
            if p.is_file() and not p.name.startswith(".tmp-"):
                stat = p.stat()
                out.append(
                    StoredObject(
                        key=p.relative_to(self.root).as_posix(),
                        size=stat.st_size,
                        modified_at=datetime.fromtimestamp(stat.st_mtime, UTC),
                    )
                )
        return out
