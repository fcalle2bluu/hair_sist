from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Hair Sist - Salón de Belleza"
    database_url: str = "postgresql+psycopg://hair:hair@localhost:5433/hair_sist"
    secret_key: str = "cambia-esta-clave"
    access_token_expire_minutes: int = 60 * 8
    timezone: str = "America/La_Paz"
    slot_minutes: int = 15
    currency_symbol: str = "Bs"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]


settings = Settings()
