# Retrieval configuration
SIMILARITY_TOP_K_DEFAULT = 5
SIMILARITY_CUTOFF_DEFAULT = 0.3

# ChromaDB configuration
CHROMA_HOST_ENV_VAR = "CHROMA_HOST"
CHROMA_HOST_DEFAULT = "localhost"
CHROMA_PORT_ENV_VAR = "CHROMA_PORT"
CHROMA_PORT_DEFAULT = 8000

# Ollama configuration
OLLAMA_HOST_ENV_VAR = "OLLAMA_HOST"
OLLAMA_HOST_DEFAULT = "localhost:11434"

# The LLM backend
LLM_BACKEND_ENV_VAR = "LLM_BACKEND"
LLM_BACKEND_DEFAULT = "openai"  # or "ollama"
# The LLM model
LLM_MODEL_ENV_VAR = "LLM_MODEL"
LLM_MODEL_DEFAULT = "gpt-4o-mini"  # or "qwen2.5"
# The embedding model
EMBEDDING_MODEL_ENV_VAR = "EMBEDDING_MODEL"
EMBEDDING_MODEL_DEFAULT = "text-embedding-3-small"  # or "nomic-embed-text"

# openAI configuration
OPENAI_API_KEY_ENV_VAR = "OPENAI_API_KEY"
