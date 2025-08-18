"""Configuration management for Ponderous application."""

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, validator


class DatabaseConfig(BaseModel):
    """Database configuration settings."""

    path: Path = Field(
        default_factory=lambda: Path.home() / ".ponderous" / "ponderous.db"
    )
    memory: bool = False
    read_only: bool = False
    threads: int = Field(default=4, ge=1, le=32)

    @validator("path")  # type: ignore[misc]
    def ensure_directory_exists(cls, v: Path) -> Path:
        """Ensure the database directory exists."""
        if not v.parent.exists():
            v.parent.mkdir(parents=True, exist_ok=True)
        return v


class MoxfieldConfig(BaseModel):
    """Moxfield API configuration."""

    base_url: str = "https://api2.moxfield.com/v2"
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 1.0
    rate_limit: float = 2.0  # requests per second


class EDHRECConfig(BaseModel):
    """EDHREC scraping configuration."""

    base_url: str = "https://edhrec.com"
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 2.0
    rate_limit: float = 1.5  # requests per second (respectful rate limiting)
    user_agent: str = "Ponderous/1.0.0 (MTG Collection Analyzer; +https://github.com/ponderous-mtg/ponderous)"


class AnalysisConfig(BaseModel):
    """Analysis engine configuration."""

    # Buildability scoring weights
    signature_card_weight: float = 3.0
    high_synergy_weight: float = 2.0
    staple_card_weight: float = 1.5
    basic_card_weight: float = 1.0

    # Completion thresholds
    min_completion_threshold: float = 0.7
    high_completion_threshold: float = 0.9

    # Performance settings
    max_commanders_to_analyze: int = 1000
    parallel_processing: bool = True
    cache_results: bool = True


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: Path | None = None
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5

    @validator("level")  # type: ignore[misc]
    def validate_log_level(cls, v: str) -> str:
        """Validate logging level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v.upper()


class PonderousConfig(BaseModel):
    """Main application configuration."""

    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    moxfield: MoxfieldConfig = Field(default_factory=MoxfieldConfig)
    edhrec: EDHRECConfig = Field(default_factory=EDHRECConfig)
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    # Application settings
    debug: bool = False
    config_dir: Path = Field(default_factory=lambda: Path.home() / ".ponderous")

    @validator("config_dir")  # type: ignore[misc]
    def ensure_config_directory_exists(cls, v: Path) -> Path:
        """Ensure the configuration directory exists."""
        v.mkdir(parents=True, exist_ok=True)
        return v

    @classmethod
    def _parse_database_env(cls, config_data: dict[str, Any]) -> None:
        """Parse database environment variables."""
        if db_path := os.getenv("PONDEROUS_DB_PATH"):
            config_data.setdefault("database", {})["path"] = Path(db_path)
        if db_memory := os.getenv("PONDEROUS_DB_MEMORY"):
            config_data.setdefault("database", {})["memory"] = db_memory.lower() in (
                "1",
                "true",
                "yes",
            )
        if db_threads := os.getenv("PONDEROUS_DB_THREADS"):
            config_data.setdefault("database", {})["threads"] = int(db_threads)

    @classmethod
    def _parse_api_env(cls, config_data: dict[str, Any]) -> None:
        """Parse API configuration environment variables."""
        # Moxfield configuration
        if mox_timeout := os.getenv("PONDEROUS_MOXFIELD_TIMEOUT"):
            config_data.setdefault("moxfield", {})["timeout"] = float(mox_timeout)
        if mox_rate_limit := os.getenv("PONDEROUS_MOXFIELD_RATE_LIMIT"):
            config_data.setdefault("moxfield", {})["rate_limit"] = float(mox_rate_limit)

        # EDHREC configuration
        if edh_timeout := os.getenv("PONDEROUS_EDHREC_TIMEOUT"):
            config_data.setdefault("edhrec", {})["timeout"] = float(edh_timeout)
        if edh_rate_limit := os.getenv("PONDEROUS_EDHREC_RATE_LIMIT"):
            config_data.setdefault("edhrec", {})["rate_limit"] = float(edh_rate_limit)

    @classmethod
    def _parse_logging_env(cls, config_data: dict[str, Any]) -> None:
        """Parse logging environment variables."""
        if log_level := os.getenv("PONDEROUS_LOG_LEVEL"):
            config_data.setdefault("logging", {})["level"] = log_level
        if log_file := os.getenv("PONDEROUS_LOG_FILE"):
            config_data.setdefault("logging", {})["file_path"] = Path(log_file)

    @classmethod
    def from_env(cls) -> "PonderousConfig":
        """Create configuration from environment variables."""
        config_data: dict[str, Any] = {}

        cls._parse_database_env(config_data)
        cls._parse_api_env(config_data)
        cls._parse_logging_env(config_data)

        # Debug mode
        if debug := os.getenv("PONDEROUS_DEBUG"):
            config_data["debug"] = debug.lower() in ("1", "true", "yes")

        return cls(**config_data)

    def save_to_file(self, path: Path | None = None) -> None:
        """Save configuration to TOML file."""
        if path is None:
            path = self.config_dir / "config.toml"

        try:
            import tomli_w
        except ImportError as e:
            raise ImportError(
                "tomli_w is required for saving config files. Install with: uv add tomli-w"
            ) from e

        with open(path, "wb") as f:
            tomli_w.dump(self.dict(), f)

    @classmethod
    def from_file(cls, path: Path) -> "PonderousConfig":
        """Load configuration from TOML file."""
        try:
            import tomli
        except ImportError as e:
            raise ImportError(
                "tomli is required for loading config files. Install with: uv add tomli"
            ) from e

        with open(path, "rb") as f:
            config_data = tomli.load(f)
        return cls(**config_data)


# Global configuration instance
_config: PonderousConfig | None = None


def get_config() -> PonderousConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = PonderousConfig.from_env()
    return _config


def set_config(config: PonderousConfig) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config
