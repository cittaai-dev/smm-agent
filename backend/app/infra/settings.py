from pydantic_settings import BaseSettings, SettingsConfigDict


class DBSettings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:dev@localhost:5432/smm"
    test_database_url: str = "postgresql+psycopg://postgres:dev@localhost:5432/smm_test"
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


class RerankSettings(BaseSettings):
    # Self-hosted cross-encoder, not a vendor API -- zero marginal cost per
    # call and no third external dependency on the query path. The real cost
    # is operational: sentence-transformers pulls in torch (a genuinely heavy
    # install) and the model itself is ~1GB on first download, so this is
    # off-able rather than assumed -- an environment without that budget
    # degrades to unreranked fused order (P5), not a hard failure.
    enabled: bool = True
    model_name: str = "BAAI/bge-reranker-base"

    model_config = SettingsConfigDict(env_prefix="SMM_RERANK_", env_file=".env", extra="ignore")


class CoreIngestSettings(BaseSettings):
    # L2/L3 escalation thresholds for Market Intel Core's L0-L3 ladder
    # (ingestion/router.py's ceiling=3 path) -- Brand Workspace never reads
    # these, it's pinned to ladder="L0-L1".
    l2_min_chars: int = 400
    l3_min_chars: int = 1200

    model_config = SettingsConfigDict(env_prefix="SMM_CORE_", env_file=".env", extra="ignore")


class EvalGateSettings(BaseSettings):
    # dual-kb.md's zero-LLM eval gate thresholds (app/eval/gate.py) -- config,
    # not hardcoded, so a real promotion decision can tune them without a
    # code change (dev_guidelines.md §13).
    max_citation_rejection_rate: float = 0.08
    max_degraded_ratio: float = 0.05
    max_l0_ratio: float = 0.15
    min_coverage_ratio: float = 0.75

    model_config = SettingsConfigDict(env_prefix="SMM_EVAL_", env_file=".env", extra="ignore")


class BridgeSettings(BaseSettings):
    # dual-kb.md §10's "measure first" answer to BRIDGE fanout cost: a fixed,
    # instrumented cap, not an open-ended search.
    max_run_chunks: int = 20
    max_core_matches_per_chunk: int = 3
    max_total_pairs: int = 60

    model_config = SettingsConfigDict(env_prefix="SMM_BRIDGE_", env_file=".env", extra="ignore")


class WebToolSettings(BaseSettings):
    timeout_seconds: float = 10.0
    max_retries: int = 2
    user_agent: str = "smm-agent-research/1.0"

    model_config = SettingsConfigDict(env_prefix="SMM_WEBTOOL_", env_file=".env", extra="ignore")


class CredentialSettings(BaseSettings):
    # Fernet key for data_source_credential.encrypted_api_key
    # (infra/crypto.py). This default is dev-only and deliberately obvious as
    # such -- any real deployment must set SMM_CREDENTIAL_ENCRYPTION_KEY to a
    # key generated via `Fernet.generate_key()`, never this one.
    encryption_key: str = "zH1qN3W8Y5vQvT6b0fJk2mR7sL9dP4cX1aE6gI3oU8s="

    model_config = SettingsConfigDict(env_prefix="SMM_CREDENTIAL_", env_file=".env", extra="ignore")


class RateLimitSettings(BaseSettings):
    # Per-brand, per-source, per-hour bucket (step5_trust_boundary.md Part D
    # §7) -- a default here, overridable per-credential
    # (DataSourceCredential.rate_limit_per_hour) at insert time.
    default_per_hour: int = 60

    model_config = SettingsConfigDict(env_prefix="SMM_RATE_LIMIT_", env_file=".env", extra="ignore")


class ApiRateLimitSettings(BaseSettings):
    # Step 6 Part A §2 -- per-caller (api-key or anon-bucket) request budget,
    # Redis-backed so it holds across replicas, separate concept from
    # RateLimitSettings above (that one throttles outbound data-source calls).
    requests_per_window: int = 60
    window_seconds: int = 60

    model_config = SettingsConfigDict(env_prefix="SMM_API_RATE_LIMIT_", env_file=".env", extra="ignore")


class CircuitBreakerSettings(BaseSettings):
    failure_threshold: int = 5
    reset_after_seconds: int = 30

    model_config = SettingsConfigDict(env_prefix="SMM_CIRCUIT_BREAKER_", env_file=".env", extra="ignore")


class CostBudgetSettings(BaseSettings):
    max_tokens_per_run: int = 40_000
    max_usd_per_run: float = 2.00
    warn_at_ratio: float = 0.8
    # Blended $/1k tokens, deliberately a single rate rather than a per-model
    # input/output split table -- good enough to enforce a budget ceiling;
    # exact accounting belongs to the provider's own billing dashboard, not
    # this app (dev_guidelines.md: don't build the general case before the
    # concrete need forces it).
    usd_per_1k_tokens: float = 0.01

    model_config = SettingsConfigDict(env_prefix="SMM_COST_", env_file=".env", extra="ignore")


db_settings = DBSettings()
api_settings = ApiSettings()
llm_settings = LLMSettings()
rerank_settings = RerankSettings()
core_ingest_settings = CoreIngestSettings()
eval_gate_settings = EvalGateSettings()
bridge_settings = BridgeSettings()
webtool_settings = WebToolSettings()
credential_settings = CredentialSettings()
rate_limit_settings = RateLimitSettings()
api_rate_limit_settings = ApiRateLimitSettings()
circuit_breaker_settings = CircuitBreakerSettings()
cost_budget_settings = CostBudgetSettings()
