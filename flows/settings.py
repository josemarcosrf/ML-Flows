from pathlib import Path

from pydantic import field_validator, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from tabulate import tabulate


def print_settings(settings: BaseSettings):
    """Print the settings in a tabular format"""
    print(
        tabulate(
            [
                (key, value)
                for key, value in dict(settings).items()
                if not key.startswith("_")
            ],
            headers=["Setting", "Value"],
            tablefmt="fancy_grid",
        )
    )


class Settings(BaseSettings):
    # Lgging configuration
    LOG_LEVEL: str = "DEBUG"
    LOG_LEVEL_FILE: str = "INFO"

    # Prefect configuration
    PREFECT_API_URL: str = "http://localhost:4200/api"
    PREFECT_STORAGE_PATH: str = str(Path.home() / ".prefect" / "storage")

    # PDF => Markdown service (Ray serve service)
    MARKER_PDF_BASE_URL: str = "http://localhost:8000/marker"

    # PDF => Markdown service (Ray serve service)
    DOCLING_BASE_URL: str | None = None
    DOCLING_VIS_MODEL_ID: str = "ds4sd/SmolDocling-256M-preview"

    # Ollama configuration
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # Redis configuration (pub/sub)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # Vector store configuration
    VECTOR_STORE_BACKEND: str = "mongo"  # Options: "mongo"

    # ChromaDB configuration
    CHROMA_HOST: str | None = None
    CHROMA_PORT: int | None = None
    CHROMA_COLLECTION: str | None = None

    # MongoDB
    MONGO_URI: str | None = None
    MONGO_DB: str | None = None
    MONGO_DOC_COLLECTION: str = "documents"
    MONGO_RESULTS_COLLECTION: str = "results"
    MONGO_VECTOR_COLLECTION: str = "embeddings"
    MONGO_VECTOR_INDEX_NAME: str = "vector_index"

    # LLM configuration
    LLM_BACKEND: str = "openai"
    LLM_MODEL: str = "gpt-4o-mini"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    VISION_MODEL: str | None = None

    # Indexing configuration
    CHUNK_SIZE: int = 1500
    CHUNK_OVERLAP: int = 500

    # Retrieval configuration
    SIMILARITY_TOP_K: int = 5
    SIMILARITY_CUTOFF: float = 0.3

    # OpenAI configuration
    OPENAI_API_KEY: SecretStr | None = None

    # AWS credentials
    AWS_ACCESS_KEY_ID: SecretStr | None = None
    AWS_SECRET_ACCESS_KEY: SecretStr | None = None
    AWS_REGION: str | None = None

    @field_validator("VECTOR_STORE_BACKEND", mode="before")
    @classmethod
    def check_vector_store_backend(cls, value):
        valid_backends = ["chroma", "mongo"]
        if value not in valid_backends:
            raise ValueError(
                f"VECTOR_STORE_BACKEND must be one of {valid_backends}, got {value}"
            )
        return value

    @field_validator("LLM_BACKEND", mode="before")
    @classmethod
    def check_llm_backend(cls, value):
        valid_backends = ["openai", "ollama", "aws"]
        if value not in valid_backends:
            raise ValueError(
                f"LLM_BACKEND must be one of {valid_backends}, got {value}"
            )
        return value

    @field_validator("CHROMA_HOST", "CHROMA_PORT", "CHROMA_COLLECTION", mode="before")
    @classmethod
    def check_chroma_config(cls, value, values):
        if values.data.get("VECTOR_STORE_BACKEND") == "chroma":
            if not value:
                raise ValueError(
                    "CHROMA_HOST and CHROMA_PORT are required for ChromaDB"
                )
            return value
        return None

    @field_validator("MONGO_URI", "MONGO_DB", mode="before")
    @classmethod
    def check_mongo_uri(cls, value, values):
        if values.data.get("VECTOR_STORE_BACKEND") == "mongo" and not value:
            raise ValueError(
                "MONGO_URI and MONGO_DB are required for MongoDB vector store"
            )
        return value

    @field_validator("OPENAI_API_KEY")
    @classmethod
    def check_openai_api_key(cls, value, values):
        if values.data.get("LLM_BACKEND") == "openai" and not value:
            raise ValueError("OPENAI_API_KEY is required when LLM_BACKEND=openai")
        return value

    @field_validator(
        "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", mode="before"
    )
    @classmethod
    def check_aws_credentials(cls, value, values):
        if values.data.get("LLM_BACKEND") == "aws" and not value:
            raise ValueError(
                "AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and AWS_REGION are required "
                "when LLM_BACKEND=aws"
            )
        return value

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
