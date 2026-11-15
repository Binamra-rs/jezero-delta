"""Runtime settings (environment) and the project configuration (YAML)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

NASA_RAW_API_DEFAULT = "https://mars.nasa.gov/rss/api/"


def _load_dotenv(path: Path) -> None:
    """Load KEY=VALUE lines from backend/.env (local runs without Docker).

    Real environment variables always win; the file is optional.
    """
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv(REPO_ROOT / "backend" / ".env")


def _env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


@lru_cache
def load_project_config(path: str | None = None) -> dict[str, Any]:
    p = Path(path or os.environ.get("JEZERO_PROJECT_CONFIG", REPO_ROOT / "config/project.yaml"))
    with open(p, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    for key in ("crs", "boundary", "datasets", "layers", "routing", "tiles"):
        if key not in cfg:
            raise ValueError(f"project config missing '{key}'")
    return cfg


@dataclass(frozen=True)
class Settings:
    environment: str = "development"
    data_dir: Path = REPO_ROOT / "data"
    db_path: Path | None = None    # None → <data_dir>/jezero.sqlite3
    cors_origins: tuple[str, ...] = ("http://localhost:5173",)
    tile_cache_seconds: int = 86400
    route_rate_per_minute: int = 20
    write_rate_per_minute: int = 60
    nasa_raw_api_url: str = NASA_RAW_API_DEFAULT
    nasa_cache_seconds: int = 600
    nasa_timeout_seconds: float = 20.0
    sentry_dsn: str | None = None
    log_level: str = "INFO"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def database_path(self) -> Path:
        return self.db_path or self.data_dir / "jezero.sqlite3"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    env = _env("JEZERO_ENV", "development") or "development"
    origins = tuple(o.strip() for o in (_env("JEZERO_CORS_ORIGINS", "http://localhost:5173") or "").split(",") if o.strip())
    if env == "production" and any("localhost" in o or "127.0.0.1" in o for o in origins):
        raise RuntimeError("Production CORS origins must not include localhost")
    nasa_url = _env("JEZERO_NASA_RAW_API_URL", NASA_RAW_API_DEFAULT) or NASA_RAW_API_DEFAULT
    if not nasa_url.startswith("https://"):
        raise RuntimeError("JEZERO_NASA_RAW_API_URL must be an https URL")
    return Settings(
        environment=env,
        data_dir=Path(_env("JEZERO_DATA_DIR", str(REPO_ROOT / "data")) or ""),
        db_path=Path(p) if (p := _env("JEZERO_DB_PATH")) else None,
        cors_origins=origins,
        tile_cache_seconds=int(_env("JEZERO_TILE_CACHE_SECONDS", "86400") or 86400),
        route_rate_per_minute=int(_env("JEZERO_ROUTE_RATE_PER_MINUTE", "20") or 20),
        write_rate_per_minute=int(_env("JEZERO_WRITE_RATE_PER_MINUTE", "60") or 60),
        nasa_raw_api_url=nasa_url,
        nasa_cache_seconds=int(_env("JEZERO_NASA_CACHE_SECONDS", "600") or 600),
        nasa_timeout_seconds=float(_env("JEZERO_NASA_TIMEOUT_SECONDS", "20") or 20),
        sentry_dsn=_env("SENTRY_DSN") or None,
        log_level=_env("JEZERO_LOG_LEVEL", "INFO") or "INFO",
    )
