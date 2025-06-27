from enum import Enum
from typing import Any

from llama_index.core.embeddings import BaseEmbedding
from loguru import logger
from prefect import task

from flows.settings import settings


class LLMBackend(str, Enum):
    AWS = "aws"  # Bedrock
    OPENAI = "openai"
    OLLAMA = "ollama"


def embedding_model_info(embedding_model: BaseEmbedding) -> tuple[int, str]:
    """
    Get the model and embedding dimension and similarity function based on the
    embedding model.
    Args:
        embedding_model (BaseEmbedding): The embedding model instance to get information from.
    Returns:
        tuple: A tuple containing the embedding dimension and similarity function.
    """
    model_name = embedding_model.model_name

    if model_name == "text-embedding-3-small":
        embedding_dim = 1536
        similarity_function = "cosine"
    elif model_name == "text-embedding-3":
        embedding_dim = 1536
        similarity_function = "cosine"
    elif model_name == "cohere.embed-multilingual-v3":
        embedding_dim = 1024
        similarity_function = "cosine"
    else:
        raise ValueError(f"Unknown embedding model: {model_name}")

    return embedding_dim, similarity_function


@task(task_run_name="get_llm:[{llm_backend}]-{llm_id}")
def get_llm(
    llm_id: str,
    llm_backend: LLMBackend | str,
    ollama_base_url: str | None = settings.OLLAMA_BASE_URL,
) -> None | Any:
    # Init the LLM and embedding models
    try:
        llm_backend = LLMBackend(llm_backend)  # type: ignore
    except ValueError:
        raise ValueError(
            f"❌ Unknown LLM backend: {llm_backend}. "
            f"Please use one of {LLMBackend.__members__}"
        )

    logger.info(f"🔮 Getting ready {llm_backend.value} LLM ({llm_id})")

    if llm_backend == LLMBackend.OPENAI:
        from llama_index.llms.openai import OpenAI

        if not settings.OPENAI_API_KEY:
            raise ValueError(
                "❌ Missing OpenAI API key. Please pass it as an argument "
                "or set the OPENAI_API_KEY environment variable."
            )

        return OpenAI(
            model=llm_id,
            temperature=0,
            seed=42,
            api_key=settings.OPENAI_API_KEY.get_secret_value(),
        )

    if llm_backend == LLMBackend.OLLAMA:
        from llama_index.llms.ollama import Ollama

        if not ollama_base_url:
            raise ValueError(
                "❌ Missing Ollama base URL. Please pass it as an argument "
                "or set the OLLAMA_BASE_URL environment variable."
                "E.g.: OLLAMA_BASE_URL=http://localhost:11434"
            )

        return Ollama(
            model=llm_id,
            temperature=0,
            seed=42,
            base_url=ollama_base_url,
        )
    if llm_backend == LLMBackend.AWS:
        from llama_index.llms.bedrock_converse import BedrockConverse

        if not settings.AWS_ACCESS_KEY_ID or not settings.AWS_SECRET_ACCESS_KEY:
            raise ValueError(
                "❌ Missing AWS credentials. Please set the AWS_ACCESS_KEY_ID and "
                "AWS_SECRET_ACCESS_KEY environment variables."
            )
        if not settings.AWS_REGION:
            raise ValueError(
                "❌ Missing AWS region. Please set the AWS_REGION environment variable."
            )

        return BedrockConverse(
            model=llm_id,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID.get_secret_value(),
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY.get_secret_value(),
            region_name=settings.AWS_REGION,
            max_tokens=32768,
            timeout=120,
        )

    raise ValueError(
        f"❌ Unknown LLM backend: {llm_backend}. "
        f"Please use one of {LLMBackend.__members__}"
    )


@task(task_run_name="get_embedding_model:[{llm_backend}]-{embedding_model_id}")
def get_embedding_model(
    embedding_model_id: str,
    llm_backend: LLMBackend | str,
    ollama_base_url: str | None = settings.OLLAMA_BASE_URL,
):
    """Returns the embedding model and to use

    Args:
        llm_backend (LLMBackend | str): LLM backend to use. One of openai, ollama
        embedding_model_id (str): Embedding model ID to use.
        E.g.: text-embedding-3-small, nomic-embed-text, ...

    Raises:
        ValueError: If the LLM backend is not one of openai, ollama

    Returns:
        OpenAIEmbedding | OllamaEmbedding: Embedding model to use
        OpenAIEmbedding: If the LLM backend is openai
        OllamaEmbedding: If the LLM backend is ollama
    """
    logger.info(f"🧬 Embedding model ({embedding_model_id})")
    if llm_backend == LLMBackend.OPENAI:
        from llama_index.embeddings.openai import OpenAIEmbedding

        if not settings.OPENAI_API_KEY:
            raise ValueError(
                "❌ Missing OpenAI API key. Please pass it as an argument "
                "or set the OPENAI_API_KEY environment variable."
            )

        return OpenAIEmbedding(
            api_key=settings.OPENAI_API_KEY.get_secret_value(), model=embedding_model_id
        )

    elif llm_backend == LLMBackend.OLLAMA:
        from llama_index.embeddings.ollama import OllamaEmbedding

        if not ollama_base_url:
            raise RuntimeError(
                "❌ Missing Ollama base URL. Please provide it as a keyword argument "
                "or set the OLLAMA_BASE_URL environment variable."
            )

        return OllamaEmbedding(base_url=ollama_base_url, model_name=embedding_model_id)

    elif llm_backend == LLMBackend.AWS:
        from llama_index.embeddings.bedrock import BedrockEmbedding

        # When LLM_Backend == "aws", we know that the AWS credentials are set
        # but let's check them anyways
        if not settings.AWS_ACCESS_KEY_ID or not settings.AWS_SECRET_ACCESS_KEY:
            raise ValueError(
                "❌ Missing AWS credentials. Please set the AWS_ACCESS_KEY_ID and "
                "AWS_SECRET_ACCESS_KEY environment variables."
            )
        if not settings.AWS_REGION:
            raise ValueError(
                "❌ Missing AWS region. Please set the AWS_REGION environment variable."
            )
        return BedrockEmbedding(
            model_name=embedding_model_id,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID.get_secret_value(),
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY.get_secret_value(),
            region_name=settings.AWS_REGION,
        )

    else:
        raise ValueError(
            f"❌ Unknown LLM backend: {llm_backend}. "
            f"Please use one of {LLMBackend.__members__}"
        )
