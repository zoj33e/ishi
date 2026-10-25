"""Runtime config from env vars / repo-root `.env` (written by scripts/setup_engine.ps1)."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    katago_bin: Path | None = Field(default=None, alias="ISHI_KATAGO_BIN")
    katago_model: Path | None = Field(default=None, alias="ISHI_KATAGO_MODEL")
    katago_human_model: Path | None = Field(default=None, alias="ISHI_KATAGO_HUMAN_MODEL")
    katago_config: Path | None = Field(default=None, alias="ISHI_KATAGO_CONFIG")
    db_path: Path = Field(default=REPO_ROOT / "data" / "ishi.db", alias="ISHI_DB_PATH")
    anthropic_api_key: SecretStr | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    llm_model: str = Field(default="claude-haiku-5-5", alias="ISHI_LLM_MODEL")
    llm_enabled: bool = Field(default=True, alias="ISHI_LLM_ENABLED")
    default_locale: str = Field(default="th", alias="ISHI_DEFAULT_LOCALE")

    @property
    def katago_configured(self) -> bool:
        return all(
            p is not None and p.exists()
            for p in (self.katago_bin, self.katago_model, self.katago_config)
        )

    def katago_command(self) -> list[str]:
        assert self.katago_bin and self.katago_model and self.katago_config
        cmd = [
            str(self.katago_bin),
            "analysis",
            "-config",
            str(self.katago_config),
            "-model",
            str(self.katago_model),
        ]
        if self.katago_human_model is not None:
            cmd += ["-human-model", str(self.katago_human_model)]
        return cmd


@lru_cache
def get_settings() -> Settings:
    return Settings()
