from enum import Enum

from loguru import logger
from prefect import task

from flows.settings import settings


class LLMBackend(str, Enum):
    OPENAI = "openai"
    OLLAMA = "ollama"


def get_llm_backend() -> LLMBackend:
    """Returns the LLM backend to use"""
    return LLMBackend(settings.LLM_BACKEND)


@task(task_run_name="get_llm:[{llm_backend}]-{llm_model}")
def get_llm(llm_backend: LLMBackend | str, llm_model: str) -> None:
    # Init the LLM and embedding models
    try:
        llm_backend = LLMBackend(llm_backend)  # type: ignore
    except ValueError:
        raise ValueError(
            f"❌ Unknown LLM backend: {llm_backend}. "
            f"Please use one of {LLMBackend.__members__}"
        )

    logger.info(f"🔮 Getting ready {llm_backend.value} LLM ({llm_model})")
    if llm_backend == LLMBackend.OPENAI:
        from llama_index.llms.openai import OpenAI

        return OpenAI(model=llm_model, temperature=0, seed=42)

    if llm_backend == LLMBackend.OLLAMA:
        from llama_index.llms.ollama import Ollama

        return Ollama(model=llm_model, temperature=0, seed=42)


@task(task_run_name="get_embedding_model:[{llm_backend}]-{embedding_model}")
def get_embedding_model(llm_backend: LLMBackend | str, embedding_model: str, **kwargs):
    """Returns the embedding model and to use

    Args:
        llm_backend (LLMBackend | str): LLM backend to use. One of openai, ollama
        embedding_model (str): Embedding model to use.
        E.g.: text-embedding-3-small, nomic-embed-text, ...

    Raises:
        ValueError: If the LLM backend is not one of openai, ollama

    Returns:
        OpenAIEmbedding | OllamaEmbedding: Embedding model to use
        OpenAIEmbedding: If the LLM backend is openai
        OllamaEmbedding: If the LLM backend is ollama
    """
    logger.info(f"🧬 Embedding model ({embedding_model})")
    if llm_backend == LLMBackend.OPENAI:
        from llama_index.embeddings.openai import OpenAIEmbedding

        return OpenAIEmbedding(model=embedding_model)

    elif llm_backend == LLMBackend.OLLAMA:
        from llama_index.embeddings.ollama import OllamaEmbedding

        return OllamaEmbedding(model_name=embedding_model)

    else:
        raise ValueError(
            f"❌ Unknown LLM backend: {llm_backend}. "
            f"Please use one of {LLMBackend.__members__}"
        )
