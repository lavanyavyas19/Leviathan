# app/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Leviathan Backend"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # Database (example; adjust if you don’t use one)
    DATABASE_URL: str = "sqlite:///./leviathan.db"

    # Paths (if you have ML models or data directories)
    DATA_DIR: str = "data"
    MODELS_DIR: str = "app/ml"

    class Config:
        env_file = ".env"  # loads values from .env file if present

# Create a single instance of Settings that can be imported anywhere
settings = Settings()

