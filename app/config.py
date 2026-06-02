from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./data/store_intel.db"
    data_dir: Path = Path(__file__).resolve().parent.parent / "data"
    pos_csv: str = "pos_transactions.csv"
    store_layout_json: str = "store_layout.json"
    stale_feed_minutes: int = 10
    conversion_window_minutes: int = 5
    dwell_emit_interval_ms: int = 30000

    class Config:
        env_prefix = "STORE_INTEL_"


settings = Settings()
