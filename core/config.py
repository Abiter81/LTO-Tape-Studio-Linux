"""Application configuration persistence (JSON-based)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


class AppConfig:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or (Path.home() / ".lto_tape_studio" / "config.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: Dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self._data = {}

    def save(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()