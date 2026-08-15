from functools import lru_cache
import secrets

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


INSECURE_JWT_SECRETS = {
    "",
    "changeme",
    "secret",
    "replace-with-at-least-32-random-bytes",
    "changeme-insecure-default-secret-key-for-development-only",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql://localhost/adsb_intel"

    # dump1090
    dump1090_url: str = "http://localhost:8080/data/aircraft.json"
    replay_control_url: str = "http://replay:8081"

    # API Keys
    anthropic_api_key: str = ""

    # App settings
    app_name: str = "Aviation Intelligence Platform"
    debug: bool = True
    environment: str = "development"
    cors_allowed_origins: str = "http://localhost:5173,http://localhost:3000"

    # Optional OpenSky cross-source corroboration (disabled until explicitly enabled)
    opensky_enabled: bool = False
    opensky_client_id: str = ""
    opensky_client_secret: str = ""
    opensky_api_base_url: str = "https://opensky-network.org/api"
    opensky_auth_url: str = (
        "https://auth.opensky-network.org/auth/realms/opensky-network/"
        "protocol/openid-connect/token"
    )

    # Anomaly detection thresholds
    rapid_descent_threshold: int = 4000  # ft/min
    speed_anomaly_threshold: float = 0.3  # 30% deviation from expected
    track_loss_timeout: int = 300  # seconds before reporting continuity loss

    # ChromaDB Configuration
    chroma_persist_directory: str = "./data/chroma"

    # LLM Configuration (Groq or OpenAI compatible)
    llm_api_key: str = ""
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_model: str = "llama-3.3-70b-versatile"
    openai_api_key: str = ""  # Fallback

    # Agent Settings
    agent_max_iterations: int = 10
    agent_temperature: float = 0.1

    # Data Ingestion URLs
    ntsb_data_url: str = "https://data.ntsb.gov/avdata/FileDirectory/DownloadFile?fileID=C%3A%5Cavdata%5Cavall.zip"
    ecfr_api_base_url: str = "https://www.ecfr.gov/api/versioner/v1"

    # Authentication Settings
    jwt_secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(48))
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480  # 8 hours
    session_cookie_name: str = "adsb_session"

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() == "production"

    @property
    def allowed_origins(self) -> tuple[str, ...]:
        return tuple(
            origin.strip().rstrip("/")
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        )

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """Refuse to start production with an implicit or weak signing key."""
        if not self.is_production:
            return self

        explicitly_configured = "jwt_secret_key" in self.model_fields_set
        if (
            not explicitly_configured
            or self.jwt_secret_key.strip().lower() in INSECURE_JWT_SECRETS
            or len(self.jwt_secret_key.encode("utf-8")) < 32
        ):
            raise ValueError(
                "JWT_SECRET_KEY must be explicitly configured with at least "
                "32 bytes in production"
            )
        if not self.allowed_origins or "*" in self.allowed_origins:
            raise ValueError(
                "CORS_ALLOWED_ORIGINS must contain explicit production origins"
            )
        return self

@lru_cache()
def get_settings() -> Settings:
    return Settings()
