from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


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
    ghost_flight_timeout: int = 300  # seconds before marking as ghost

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

    # Optional Langfuse export. Local trace IDs remain available when disabled.
    langfuse_enabled: bool = False
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = "https://cloud.langfuse.com"
    langfuse_environment: str = "development"
    langfuse_capture_content: bool = False

    # Data Ingestion URLs
    ntsb_data_url: str = "https://data.ntsb.gov/avdata/FileDirectory/DownloadFile?fileID=C%3A%5Cavdata%5Cavall.zip"
    ecfr_api_base_url: str = "https://www.ecfr.gov/api/versioner/v1"

@lru_cache()
def get_settings() -> Settings:
    return Settings()
