"""Application configuration via Pydantic Settings with layered env support."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class _LLMSettings(BaseSettings):
    """LLM provider configuration."""

    model_config = SettingsConfigDict(env_prefix="SHADOWLINK_LLM_", env_file=".env", env_file_encoding="utf-8", extra="ignore")

    base_url: str = Field(default="https://api.openai.com/v1", description="OpenAI-compatible API base URL")
    model: str = Field(default="gpt-4o-mini", description="Default model name")
    api_key: str = Field(default="", description="API key (empty = local)")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1)
    timeout_seconds: int = Field(default=120, ge=1)
    streaming: bool = True


class _GRPCSettings(BaseSettings):
    """gRPC server configuration."""

    model_config = SettingsConfigDict(env_prefix="SHADOWLINK_GRPC_", env_file=".env", env_file_encoding="utf-8", extra="ignore")

    port: int = Field(default=50051, description="gRPC listen port")
    max_workers: int = Field(default=10, ge=1)
    max_message_length: int = Field(default=50 * 1024 * 1024, description="50 MB")
    reflection_enabled: bool = True


class _RAGSettings(BaseSettings):
    """RAG pipeline configuration."""

    model_config = SettingsConfigDict(env_prefix="SHADOWLINK_RAG_", env_file=".env", env_file_encoding="utf-8", extra="ignore")

    embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    embedding_device: str = Field(default="cpu")
    embedding_dimension: int = 384
    embedding_batch_size: int = 32
    faiss_index_path: str = Field(default="./data/faiss_index")
    default_top_k: int = 5
    default_chunk_size: int = 512
    default_chunk_overlap: int = 64
    rerank_enabled: bool = True
    rerank_model: str = Field(default="BAAI/bge-reranker-base")
    crag_quality_threshold: float = Field(default=0.5, ge=0.0, le=1.0)


class _AgentSettings(BaseSettings):
    """Agent engine configuration."""

    model_config = SettingsConfigDict(env_prefix="SHADOWLINK_AGENT_", env_file=".env", env_file_encoding="utf-8", extra="ignore")

    default_strategy: str = Field(default="react", description="Default agent strategy")
    max_iterations: int = Field(default=15, ge=1, le=50)
    reflection_enabled: bool = True
    plan_cache_enabled: bool = True
    plan_cache_ttl_seconds: int = 3600
    complexity_router_enabled: bool = True


class _MemorySettings(BaseSettings):
    """Agent memory system configuration."""

    model_config = SettingsConfigDict(env_prefix="SHADOWLINK_MEMORY_", env_file=".env", env_file_encoding="utf-8", extra="ignore")

    short_term_max_messages: int = Field(default=50, ge=5)
    long_term_enabled: bool = True
    long_term_storage_path: str = Field(default="./data/memory")
    episodic_enabled: bool = True
    semantic_enabled: bool = False  # requires external KG


class _FileProcessingSettings(BaseSettings):
    """File processing configuration."""

    model_config = SettingsConfigDict(env_prefix="SHADOWLINK_FILE_", env_file=".env", env_file_encoding="utf-8", extra="ignore")

    upload_dir: str = Field(default="./data/uploads")
    max_file_size_mb: int = Field(default=100, ge=1)
    ocr_enabled: bool = False
    ocr_language: str = "ch_sim+en"
    supported_extensions: list[str] = Field(
        default=[".pdf", ".docx", ".xlsx", ".pptx", ".md", ".txt", ".py", ".java", ".ts", ".js", ".png", ".jpg"]
    )


class Settings(BaseSettings):
    """Root application settings, aggregating all sub-settings."""

    model_config = SettingsConfigDict(
        env_prefix="SHADOWLINK_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── General ──
    version: str = "0.1.0"
    app_name: str = "shadowlink-ai"
    debug: bool = False
    env: str = Field(default="dev", description="dev | prod | test")
    log_level: str = Field(default="INFO", description="DEBUG | INFO | WARNING | ERROR")
    cors_origins: list[str] = Field(default=["*"])
    data_dir: str = Field(default="./data")

    # ── REST API ──
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # ── Sub-settings (nested) ──
    llm: _LLMSettings = Field(default_factory=_LLMSettings)
    grpc: _GRPCSettings = Field(default_factory=_GRPCSettings)
    rag: _RAGSettings = Field(default_factory=_RAGSettings)
    agent: _AgentSettings = Field(default_factory=_AgentSettings)
    memory: _MemorySettings = Field(default_factory=_MemorySettings)
    file_processing: _FileProcessingSettings = Field(default_factory=_FileProcessingSettings)


settings = Settings()
