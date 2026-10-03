"""Agent action logging (spec §24): every tool call is inspectable and persisted."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class ActionLogger:
    """Collects actions for the API response and appends them to data/agent.log."""

    log_path: Path
    entries: list[dict] = field(default_factory=list)

    def log(self, tool: str, detail: str) -> None:
        self.entries.append({"tool": tool, "detail": detail})
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        line = f"{datetime.now().isoformat(timespec='seconds')} [{tool}] {detail}\n"
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(line)
