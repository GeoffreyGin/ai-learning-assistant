from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    database_url: str
    upload_dir: Path

    @classmethod
    def from_environment(cls) -> "Settings":
        data_dir = Path(os.environ.get("DATA_DIR", "data")).resolve()
        database_url = os.environ.get("DATABASE_URL", f"sqlite:///{data_dir / 'knowledge.db'}")
        return cls(data_dir=data_dir, database_url=database_url, upload_dir=data_dir / "uploads")

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
