from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://localhost/adsb_intel"

    # dump1090
    dump1090_url: str = "http://localhost:8080/data/aircraft.json"

    # API Keys
    anthropic_api_key: str = ""

    # App settings
    app_name: str = "ADS-B Flight Intelligence Platform"
    debug: bool = True

    # Anomaly detection thresholds
    rapid_descent_threshold: int = 4000  # ft/min
    speed_anomaly_threshold: float = 0.3  # 30% deviation from expected
    ghost_flight_timeout: int = 300  # seconds before marking as ghost

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
