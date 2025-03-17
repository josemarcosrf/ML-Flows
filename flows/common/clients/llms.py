import os
from enum import Enum

from loguru import logger
from prefect import task


class LLMBackend(str, Enum):
    OPENAI = "openai"
    OLLAMA = "ollama"


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

        if api_key := (os.getenv("OPENAI_API_KEY") or kwargs.get("openai_api_key")):
            return OpenAIEmbedding(api_key=api_key, model=embedding_model)
        else:
            raise RuntimeError(
                f"❌ Unknown LLM backend: {llm_backend}. "
                f"Please use one of {LLMBackend.__members__}"
            )

    elif llm_backend == LLMBackend.OLLAMA:
        from llama_index.embeddings.ollama import OllamaEmbedding

        if ollama_base_url := kwargs.get("ollama_base_url"):
            return OllamaEmbedding(base_url=ollama_base_url, model_name=embedding_model)
        else:
            raise RuntimeError(
                "❌ Missing Ollama host. Please provide it as a keyword argument "
                "or set the OLLAMA_BASE_URL environment variable."
                "E.g.: OLLAMA_BASE_URL=http://localhost:11434"
            )

    else:
        raise ValueError(
            f"❌ Unknown LLM backend: {llm_backend}. "
            f"Please use one of {LLMBackend.__members__}"
        )
