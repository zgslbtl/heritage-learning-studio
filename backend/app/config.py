from __future__ import annotations

from pathlib import Path
from typing import List, Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration. Secrets are read from the server environment only."""

    model_config = SettingsConfigDict(
        env_file=(str(PROJECT_ROOT / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    environment: str = "development"
    deployment_mode: Literal["study", "beta"] = "study"
    storage_backend: Literal["local", "blob"] = "local"
    queue_backend: Literal["local", "vercel"] = "local"
    blob_read_write_token: Optional[str] = None
    blob_store_id: Optional[str] = None
    vercel_region: str = "hkg1"
    site_address: str = "localhost"
    public_origin: Optional[str] = "http://localhost:5173"
    cookie_secure: bool = False

    database_url: str = (
        "postgresql+asyncpg://heritage:heritage@127.0.0.1:5432/heritage"
    )
    admin_password: str = ""
    anon_code_pepper: str = ""
    auth_mode: Literal["email", "code"] = "email"

    data_dir: Path = Path("data")
    auto_bootstrap: bool = True
    image_worker_enabled: bool = True

    round_duration_seconds: int = 840
    t1_duration_seconds: int = 1440
    t2_duration_seconds: int = 1200
    session_ttl_hours: int = 24
    admin_session_hours: int = 8

    db_pool_size: int = 20
    db_max_overflow: int = 20
    db_null_pool: bool = False
    log_level: str = "INFO"

    text_model_base_url: Optional[str] = None
    text_model_name: Optional[str] = None
    text_model_api_key: Optional[str] = None
    text_model_timeout_seconds: float = 60.0
    text_temperature: float = 0.7
    text_max_output_tokens: int = 900
    text_model_thinking: Optional[Literal["enabled", "disabled"]] = None

    image_model_base_url: Optional[str] = None
    image_model_name: Optional[str] = None
    image_model_api_key: Optional[str] = None
    image_model_timeout_seconds: float = 120.0
    image_model_size: str = "1024x1024"
    image_model_response_format: Optional[Literal["url", "b64_json"]] = None
    image_model_watermark: Optional[bool] = None
    image_max_concurrency: int = 2
    # 0 means unlimited sequential generations for a round; a positive value
    # remains available as an operator cost cap.
    image_job_limit_per_round: int = 0
    image_prompt_optimizer_enabled: bool = True
    text_model_vision_enabled: bool = True
    image_reference_enabled: bool = True

    class_count: int = 4
    participants_per_class: int = 30

    # Required for browser-origin checks when set. Comma-separated list allowed.
    extra_allowed_origins: List[str] = Field(default_factory=list)

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def is_beta(self) -> bool:
        return self.deployment_mode == "beta"

    @property
    def enabled_class_ids(self) -> List[int]:
        if self.is_beta:
            return [0]
        return list(range(1, self.class_count + 1))

    def class_allowed(self, class_id: int) -> bool:
        return class_id in self.enabled_class_ids or (
            not self.is_production and not self.is_beta and class_id == 0
        )

    @property
    def allowed_origins(self) -> List[str]:
        values: List[str] = []
        if self.public_origin:
            values.append(self.public_origin.rstrip("/"))
        for item in self.extra_allowed_origins:
            if item:
                values.append(item.rstrip("/"))
        return values

    @property
    def text_configured(self) -> bool:
        return bool(
            self.text_model_base_url
            and self.text_model_name
            and self.text_model_api_key
        )

    @property
    def image_configured(self) -> bool:
        return bool(
            self.image_model_base_url
            and self.image_model_name
            and self.image_model_api_key
        )

    @property
    def codes_csv_path(self) -> Path:
        return self.data_dir / "private" / "access_codes.csv"

    @property
    def artifacts_dir(self) -> Path:
        return self.data_dir / "artifacts"

    @property
    def keyframes_dir(self) -> Path:
        return self.data_dir / "keyframes"

    @property
    def exports_dir(self) -> Path:
        return self.data_dir / "exports"

    def ensure_directories(self) -> None:
        for directory in (
            self.data_dir,
            self.data_dir / "private",
            self.artifacts_dir,
            self.keyframes_dir,
            self.exports_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
