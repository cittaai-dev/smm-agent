from pydantic_settings import BaseSettings, SettingsConfigDict


class DBSettings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:dev@localhost:5432/smm"
    redis_url: str = "redis://localhost:6379"

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")


class LLMSettings(BaseSettings):
    openai_api_key: str = ""
    plan_model: str = "gpt-4.1-mini"
    synthesize_model: str = "gpt-4.1"
    repair_model: str = "gpt-4.1"
    synthesize_temperature: float = 0.2
    context_max_tokens: int = 6000
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    model_config = SettingsConfigDict(env_prefix="SMM_LLM_", extra="ignore")


db_settings = DBSettings()
llm_settings = LLMSettings()
