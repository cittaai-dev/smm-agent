from pydantic_settings import BaseSettings, SettingsConfigDict


class DBSettings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:dev@localhost:5432/smm"
    redis_url: str = "redis://localhost:6379"

    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")


class ApiSettings(BaseSettings):
    # Comma-separated list of allowed browser origins for CORS. The frontend
    # runs on a different origin (localhost:3000) than the API (localhost:8000)
    # even in local dev, so this must be explicit -- see dev_guidelines.md §13
    # (config over hardcoding).
    cors_origins: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_prefix="SMM_API_", env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


class LLMSettings(BaseSettings):
    openai_api_key: str = ""
    plan_model: str = "gpt-4.1-mini"
    synthesize_model: str = "gpt-4.1"
    repair_model: str = "gpt-4.1"
    synthesize_temperature: float = 0.2
    context_max_tokens: int = 6000
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    model_config = SettingsConfigDict(env_prefix="SMM_LLM_", env_file=".env", extra="ignore")


db_settings = DBSettings()
api_settings = ApiSettings()
llm_settings = LLMSettings()
