"""Session logging framework: session_logs/ directory structure and logging."""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_BASE_DIR = "session_logs"
SCRIPT_CATEGORIES = ("analysis", "organization", "deletion")


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_session_id():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


@dataclass
class SessionLogger:
    """Manages the session_logs/ directory structure and a per-session log."""

    base_dir: Path
    session_id: str
    events: list = field(default_factory=list)

    @classmethod
    def start(cls, base_dir=DEFAULT_BASE_DIR, session_id=None):
        """Create the session_logs/ structure and return a new SessionLogger."""
        base_dir = Path(base_dir)
        session_id = session_id or _new_session_id()

        for category in SCRIPT_CATEGORIES:
            (base_dir / "scripts" / category).mkdir(parents=True, exist_ok=True)
        (base_dir / "reports").mkdir(parents=True, exist_ok=True)

        logger = cls(base_dir=base_dir, session_id=session_id)
        logger.log(f"Session {session_id} started")
        return logger

    @property
    def log_file(self):
        return self.base_dir / f"session_{self.session_id}.log"

    @property
    def summary_file(self):
        return self.base_dir / f"session_{self.session_id}_summary.json"

    @property
    def reports_dir(self):
        return self.base_dir / "reports"

    def script_dir(self, category):
        """Return the session_logs/scripts/<category>/ directory."""
        if category not in SCRIPT_CATEGORIES:
            raise ValueError(
                f"Unknown script category {category!r}; expected one of {SCRIPT_CATEGORIES}"
            )
        return self.base_dir / "scripts" / category

    def log(self, message, level="INFO"):
        """Append a timestamped entry to the session log and event list."""
        timestamp = _now_iso()
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [{level}] {message}\n")
        self.events.append({"timestamp": timestamp, "level": level, "message": message})

    def write_summary(self):
        """Write the accumulated events to a JSON summary file and return its path."""
        with open(self.summary_file, "w", encoding="utf-8") as f:
            json.dump({"session_id": self.session_id, "events": self.events}, f, indent=2)
        return self.summary_file
