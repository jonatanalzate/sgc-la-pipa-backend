from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    ip_whitelist_activa: bool = False  # False = whitelist desactivada (modo desarrollo)
    ips_rescate: str = ""  # IPs separadas por coma, nunca bloqueadas
    sysadmin_email: str | None = None
    sysadmin_password: str | None = None
    resend_api_key: str | None = None
    frontend_url: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

