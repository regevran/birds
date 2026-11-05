"""Runtime configuration for the trainer.

All paths are derived from the repository root. Tests can build a config from
a temporary root with ``Config.from_root``; normal runs use ``Config.default``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path


@dataclass(frozen=True)
class Config:
    """Filesystem locations and local-server defaults."""

    repo_root: Path
    data_dir: Path
    species_path: Path
    etymology_path: Path
    progress_dir: Path
    web_dir: Path
    host: str = "127.0.0.1"
    port: int = 8765

    @staticmethod
    def from_root(repo_root: Path) -> "Config":
        """Factory: build a Config rooted at ``repo_root``.

        This is deliberately a static factory, not a class or instance method:
        it takes only the root path and returns a new ``Config``. The host and
        port come from the dataclass defaults; use ``with_overrides`` to change
        them.
        """
        root = Path(repo_root).resolve()
        data_dir = root / "data" / "out"
        return Config(
            repo_root=root,
            data_dir=data_dir,
            species_path=data_dir / "israel_birds_final.json",
            etymology_path=data_dir / "etymology.json",
            progress_dir=root / "learn" / "data" / "progress",
            web_dir=root / "learn" / "src" / "web",
        )

    @staticmethod
    def default() -> "Config":
        """Build a configuration for the checked-out repository."""
        # config.py -> foundation -> trainer -> src -> learn -> repository
        return Config.from_root(Path(__file__).resolve().parents[4])

    def with_overrides(self, **changes: object) -> "Config":
        """Return a copy with selected fields replaced."""
        return replace(self, **changes)
