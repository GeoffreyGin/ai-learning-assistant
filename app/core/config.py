from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader. Existing environment variables always win."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    database_url: str
    upload_dir: Path
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    mastered_threshold: float = 0.80
    weak_threshold: float = 0.40
    mastery_min_evidence: int = 3

    @classmethod
    def from_environment(cls) -> Settings:
        _load_dotenv(Path(".env").resolve())
        data_dir = Path(os.environ.get("DATA_DIR") or "data").resolve()
        database_url = os.environ.get("DATABASE_URL") or f"sqlite:///{data_dir / 'knowledge.db'}"
        return cls(
            data_dir=data_dir,
            database_url=database_url,
            upload_dir=data_dir / "uploads",
            llm_base_url=os.environ.get("LLM_BASE_URL") or None,
            llm_api_key=os.environ.get("LLM_API_KEY") or None,
            llm_model=os.environ.get("LLM_MODEL") or None,
            mastered_threshold=float(os.environ.get("MASTERY_MASTERED_THRESHOLD") or "0.80"),
            weak_threshold=float(os.environ.get("MASTERY_WEAK_THRESHOLD") or "0.40"),
            mastery_min_evidence=int(os.environ.get("MASTERY_MIN_EVIDENCE") or "3"),
        )

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_base_url and self.llm_api_key and self.llm_model)
