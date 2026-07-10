"""
配置管理 - 类似 Java 的 @ConfigurationProperties
"""
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API 配置
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = True

    # OpenAI 兼容 API 配置
    # 保留 MINIMAX_* 作为兼容别名，避免历史环境变量立即失效。
    openai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("OPENAI_API_KEY", "MINIMAX_API_KEY"),
    )
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias=AliasChoices("OPENAI_BASE_URL", "MINIMAX_BASE_URL"),
    )
    openai_model: str = Field(
        default="gpt-4o-mini",
        validation_alias=AliasChoices("OPENAI_MODEL", "MINIMAX_MODEL"),
    )
    openai_timeout_seconds: float = Field(
        default=60.0,
        validation_alias=AliasChoices("OPENAI_TIMEOUT_SECONDS", "MINIMAX_TIMEOUT_SECONDS"),
    )
    openai_wire_api: str = "chat_completions"  # chat_completions|responses
    openai_reasoning_effort: str = ""
    openai_disable_response_storage: bool = False
    google_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("GOOGLE_API_KEY", "GEMINI_API_KEY", "PALM_API_KEY"),
    )
    wordflow_remote_endpoint: str = (
        "https://62uqq9jku8.execute-api.us-east-1.amazonaws.com/prod/records"
    )
    enable_schedulers: bool = True

    # 硅基流动 Embedding API 配置
    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.cn"
    siliconflow_embedding_model: str = "BAAI/bge-m3"
    rag_vector_backend: str = "auto"  # auto|supabase_pgvector|chroma
    supabase_vector_table: str = "rag_embeddings"

    # 火山引擎/即梦 API 配置
    volcengine_api_key: str = ""
    volcengine_base_url: str = "https://ark.cn-beijing.volces.com"
    volcengine_model: str = "doubao-seedream-4-5-251128"
    cover_storage_dir: str = "./data/covers"
    cover_media_url_prefix: str = "/media/covers"
    cover_prompt_llm_timeout_seconds: float = 12.0

    # GitHub 趋势
    github_token: str = Field(
        default="",
        validation_alias=AliasChoices("GITHUB_TOKEN", "GITHUB_PERSONAL_ACCESS_TOKEN"),
    )
    github_trending_timezone: str = "Asia/Shanghai"
    github_trending_daily_hour: int = 9
    github_trending_daily_minute: int = 5

    # Linux.do 趋势（Discourse JSON）
    linuxdo_base_url: str = "https://linux.do"
    linuxdo_trending_timeout_seconds: float = 20.0
    linuxdo_trending_timezone: str = "Asia/Shanghai"
    linuxdo_trending_default_limit: int = 20
    linuxdo_trending_daily_hour: int = 9
    linuxdo_trending_daily_minute: int = 10
    linuxdo_refresh_cooldown_seconds: float = 90.0
    linuxdo_rss_429_retries: int = 2
    linuxdo_rss_429_default_retry_after_seconds: float = 6.0
    linuxdo_rss_429_jitter_seconds: float = 0.5
    linuxdo_summary_use_llm: bool = True
    linuxdo_summary_llm_trigger_chars: int = 500
    linuxdo_summary_llm_timeout_seconds: float = 8.0

    # 小红书热点（第三方已授权数据服务）
    xhs_trends_provider: str = "algovate_mcp"  # algovate_mcp|http_api
    xhs_trends_api_base_url: str = ""
    xhs_trends_api_key: str = ""
    xhs_trends_timeout_seconds: float = 12.0
    xhs_trends_timezone: str = "Asia/Shanghai"
    xhs_trends_lookback_days: int = 7
    xhs_trends_min_interactions: int = 100
    xhs_trends_default_limit: int = 10
    xhs_trends_cache_file: str = "./data/xhs_trends_cache.json"
    xhs_trends_categories_file: str = "./src/write_agent/config/xhs_trends_categories.json"
    xhs_mcp_url: str = "http://127.0.0.1:3000/mcp"
    xhs_mcp_timeout_seconds: float = 20.0
    xhs_mcp_browser_path: str = ""
    xhs_trends_max_keywords_per_category: int = 5
    xhs_trends_comment_detail_limit: int = 3
    xhs_trends_comment_enrichment_ttl_seconds: int = 1800
    xhs_mcp_detail_interval_seconds: float = 0.8
    xhs_mcp_detail_retries: int = 1
    xhs_mcp_detail_retry_backoff_seconds: float = 1.0

    # 数据库配置
    database_url: str = Field(
        default="sqlite:///./data/acceptance_write_agent.db",
        validation_alias=AliasChoices("SUPABASE_DB_URL", "DATABASE_URL"),
    )
    chroma_dir: str = "./data/chroma"

    # 日志配置
    log_level: str = "INFO"

    # 可观测性
    obs_enabled: bool = True
    obs_mode: str = "shadow"  # shadow|active
    obs_retention_days: int = 14
    obs_log_dir: str = "./data/observability"
    obs_token: str = ""
    obs_strict_dev: bool = True


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()
