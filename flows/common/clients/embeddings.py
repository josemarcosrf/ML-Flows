from typing import Callable

from flows.common.clients.llms import LLMBackend
from flows.settings import settings


def get_embedding_function(
    embedding_model_id: str,
    backend: str | LLMBackend,
    ollama_base_url: str | None = settings.OLLAMA_BASE_URL,
) -> Callable:
    if backend == LLMBackend.OLLAMA:
        from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

        if not ollama_base_url:
            raise RuntimeError(
                "❌ Missing Ollama host. Please provide it as a keyword argument "
                "or set the OLLAMA_BASE_URL environment variable."
                "E.g.: OLLAMA_BASE_URL=http://localhost:11434"
            )
        return OllamaEmbeddingFunction(
            url=f"{ollama_base_url}/api/embeddings",
            model_name=embedding_model_id,
        )
    elif backend == LLMBackend.OPENAI:
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

        if not settings.OPENAI_API_KEY:
            raise RuntimeError(
                "❌ Missing OpenAI API key. Please provide it as a keyword argument "
                "or set the OPENAI_API_KEY environment variable."
            )
        return OpenAIEmbeddingFunction(
            api_key=settings.OPENAI_API_KEY.get_secret_value(),
            model_name=embedding_model_id,
        )
    elif backend == LLMBackend.AWS:
        import boto3
        from botocore.client import Config

        from flows.common.clients.chroma import BedrockEmbeddingFunction

        if not settings.AWS_REGION:
            raise RuntimeError(
                "❌ Missing AWS region. Please set the AWS_REGION environment variable."
            )

        client = boto3.client(
            "bedrock-runtime",
            region_name=settings.AWS_REGION,
            config=Config(signature_version="v4"),
        )

        return BedrockEmbeddingFunction(client=client, model_id=embedding_model_id)

    else:
        raise ValueError(
            f"❌ Invalid LLM backend: {backend}. Please use one of {LLMBackend}"
        )
