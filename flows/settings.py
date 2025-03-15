from pathlib import Path

from pydantic import field_validator, SecretStr
from pydantic_settings import BaseSettings
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
    # Default storage path for Prefect
    PREFECT_STORAGE_PATH: str = str(Path.home() / ".prefect" / "storage")

    # ChromaDB configuration
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000

    # Ollama configuration
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # LLM configuration
    LLM_BACKEND: str = "openai"  # or "ollama"
    LLM_MODEL: str = "gpt-4o-mini"  # or "qwen2.5"
    EMBEDDING_MODEL: str = "text-embedding-3-small"  # or "nomic-embed-text"
    VISION_MODEL: str | None = None

    # Retrieval configuration
    SIMILARITY_TOP_K: int = 5
    SIMILARITY_CUTOFF: float = 0.3

    # OpenAI configuration
    OPENAI_API_KEY: SecretStr | None = None

    # AWS credentials
    AWS_ACCESS_KEY_ID: SecretStr | None = None
    AWS_SECRET_ACCESS_KEY: SecretStr | None = None

    @field_validator("OPENAI_API_KEY")
    @classmethod
    def check_openai_api_key(cls, value, values):
        if values.data.get("LLM_BACKEND") == "openai" and not value:
            raise ValueError("OPENAI_API_KEY is required when LLM_BACKEND=openai")
        return value

    model_config = {"env_file": ".env"}


settings = Settings()
